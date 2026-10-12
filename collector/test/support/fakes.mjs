// An in-memory stand-in for the one Cloudflare binding the collector uses, an
// R2 bucket, shaped to the Workers binding API as documented
// (https://developers.cloudflare.com/r2/api/workers/workers-api-reference/):
//
// - get(key) -> R2ObjectBody | null, with body, text(), json(), etag,
//   httpEtag, customMetadata, httpMetadata and uploaded;
// - put(key, value, {httpMetadata, customMetadata, onlyIf}) -> R2Object, or
//   null when an onlyIf precondition fails. Two preconditions are modelled,
//   the two the worker uses: Headers {"if-none-match": "*"} (the key must be
//   absent) and R2Conditional {etagMatches: <etag>} (the object must be the
//   one read). Any other precondition throws, so the worker can't come to
//   rely on one the fake would get wrong. A quoted etag in an R2Conditional
//   throws too: a third-party report says workerd rejects it;
// - every object has an etag, unquoted, and an httpEtag, quoted. The etag is
//   an MD5 of the body, so writing the same bytes again keeps the same etag.
//   That is the cautious assumption: a worker that needed every write to
//   change the etag would fail here instead of in production;
// - delete(key | keys[]) -> void, at most 1,000 keys per call;
// - list({prefix, cursor, limit}) -> {objects, truncated, cursor}, in lexical
//   key order. A page may hold fewer than `limit` objects, so the fake's page
//   size can be lowered to force pagination.

import { createHash } from "node:crypto";

function failsPrecondition(onlyIf, entry) {
  if (onlyIf instanceof Headers) {
    const names = [...onlyIf.keys()];
    if (names.length !== 1 || onlyIf.get("if-none-match") !== "*") {
      throw new Error(`fake R2: unmodelled precondition headers ${names}`);
    }
    return entry !== undefined;
  }
  const keys = Object.keys(onlyIf);
  if (keys.length !== 1 || keys[0] !== "etagMatches") {
    throw new Error(`fake R2: unmodelled R2Conditional ${keys}`);
  }
  const etag = onlyIf.etagMatches;
  if (typeof etag !== "string" || etag === "") throw new TypeError("fake R2: etagMatches must be an etag");
  if (etag.startsWith('"') || etag.startsWith("W/")) {
    throw new TypeError("Conditional ETag should not be wrapped in quotes");
  }
  return entry === undefined || entry.etag !== etag;
}

export class FakeR2Bucket {
  constructor({ pageSize = 1000 } = {}) {
    this.objects = new Map();
    this.pageSize = pageSize;
    this.puts = [];
    this.deletes = [];
    this.lists = 0;
    // Set to a function(key, op) that throws, to simulate a failed call.
    this.fail = null;
  }

  view(entry) {
    return {
      key: entry.key,
      size: entry.text.length,
      etag: entry.etag,
      httpEtag: `"${entry.etag}"`,
      uploaded: entry.uploaded,
      customMetadata: { ...entry.customMetadata },
      httpMetadata: { ...entry.httpMetadata },
      get body() {
        return new Response(entry.text).body;
      },
      text: async () => entry.text,
      json: async () => JSON.parse(entry.text),
    };
  }

  async get(key) {
    if (this.fail) this.fail(key, "get");
    const entry = this.objects.get(key);
    return entry === undefined ? null : this.view(entry);
  }

  async put(key, value, options = {}) {
    if (this.fail) this.fail(key, "put");
    if (options.onlyIf !== undefined && failsPrecondition(options.onlyIf, this.objects.get(key))) return null;
    const text = typeof value === "string" ? value : new TextDecoder().decode(value);
    const entry = {
      key,
      text,
      etag: createHash("md5").update(text).digest("hex"),
      // R2 stamps every object with its upload time, and so does the fake.
      // The worker can't prevent it; the tests check it never copies it.
      uploaded: new Date(),
      httpMetadata: options.httpMetadata || {},
      customMetadata: options.customMetadata || {},
      options: Object.keys(options),
    };
    this.objects.set(key, entry);
    this.puts.push(key);
    return this.view(entry);
  }

  async delete(keys) {
    const list = Array.isArray(keys) ? keys : [keys];
    if (list.length > 1000) throw new Error("fake R2: at most 1000 keys per delete");
    for (const key of list) {
      if (this.fail) this.fail(key, "delete");
      this.objects.delete(key);
      this.deletes.push(key);
    }
  }

  async list(options = {}) {
    this.lists++;
    const prefix = options.prefix || "";
    const limit = Math.min(options.limit || 1000, 1000, this.pageSize);
    const keys = [...this.objects.keys()].filter((k) => k.startsWith(prefix)).sort();
    const from = options.cursor === undefined ? 0 : keys.filter((k) => k <= options.cursor).length;
    const page = keys.slice(from, from + limit);
    const truncated = from + limit < keys.length;
    return {
      objects: page.map((k) => this.view(this.objects.get(k))),
      truncated,
      ...(truncated ? { cursor: page[page.length - 1] } : {}),
      delimitedPrefixes: [],
    };
  }

  text(key) {
    const entry = this.objects.get(key);
    return entry === undefined ? undefined : entry.text;
  }

  keys(prefix = "") {
    return [...this.objects.keys()].filter((k) => k.startsWith(prefix)).sort();
  }

  entries(prefix = "") {
    return this.keys(prefix).map((k) => this.objects.get(k));
  }
}

// --- scripting overlapping runs ------------------------------------------------
//
// Two flushes interleave only where they await R2. A run is given its own view
// of the shared bucket, and a pause point stops that run just before one call,
// until the test releases it. So a test can replay one exact interleaving,
// deterministically, rather than hoping Promise.all produces it.

function gate() {
  let open;
  const promise = new Promise((resolve) => {
    open = resolve;
  });
  return { promise, open };
}

// Pause the first `op` whose key satisfies `key` (a string or a predicate).
// For delete the key is the array of keys; for list it is the prefix.
// `reached` resolves when the run arrives there; `release()` lets it go on.
export function pauseAt(op, key) {
  const reached = gate();
  const released = gate();
  let hit = false;
  return {
    matches(o, k) {
      return !hit && o === op && (typeof key === "function" ? key(k) : k === key);
    },
    async pass() {
      hit = true;
      reached.open();
      await released.promise;
    },
    reached: reached.promise,
    release: released.open,
  };
}

// Optionally `fail(op, key)` throws to simulate this run crashing at a call.
export function runView(bucket, { pauses = [], fail = null } = {}) {
  const wrap = (op) => async (...args) => {
    const first = args[0];
    const key = op === "list" ? (first || {}).prefix : first;
    for (const point of pauses) if (point.matches(op, key)) await point.pass();
    if (fail) fail(op, key);
    return bucket[op](...args);
  };
  return { get: wrap("get"), put: wrap("put"), delete: wrap("delete"), list: wrap("list") };
}

export function makeEnv(options) {
  return { BUNDLES: new FakeR2Bucket(options) };
}

export const BASE = "https://collector.example";

export function post(body, headers = { "content-type": "application/json" }) {
  return new Request(`${BASE}/v1/report`, { method: "POST", headers, body });
}

// A minimal TOML reader for the subset wrangler.toml uses: [table],
// [[array.of.tables]], dotted headers, and key = string | number | boolean |
// array of strings, with # comments.
export function parseToml(text) {
  const root = {};
  let current = root;
  const walk = (path, makeArrayEntry) => {
    let node = root;
    path.forEach((part, i) => {
      const last = i === path.length - 1;
      if (last && makeArrayEntry) {
        if (!Array.isArray(node[part])) node[part] = [];
        const entry = {};
        node[part].push(entry);
        node = entry;
        return;
      }
      if (Array.isArray(node[part])) node = node[part][node[part].length - 1];
      else {
        if (node[part] === undefined) node[part] = {};
        node = node[part];
      }
    });
    return node;
  };
  const value = (raw) => {
    raw = raw.trim();
    if (raw.startsWith('"')) return JSON.parse(raw.slice(0, raw.indexOf('"', 1) + 1));
    if (raw.startsWith("[")) return JSON.parse(raw.slice(0, raw.lastIndexOf("]") + 1));
    const bare = raw.split("#")[0].trim();
    if (bare === "true") return true;
    if (bare === "false") return false;
    if (/^-?[0-9.]+$/.test(bare)) return Number(bare);
    throw new Error(`unsupported TOML value: ${raw}`);
  };
  for (const rawLine of text.split("\n")) {
    const line = rawLine.trim();
    if (line === "" || line.startsWith("#")) continue;
    let m = /^\[\[([^\]]+)\]\]$/.exec(line);
    if (m) {
      current = walk(m[1].trim().split("."), true);
      continue;
    }
    m = /^\[([^\]]+)\]$/.exec(line);
    if (m) {
      current = walk(m[1].trim().split("."), false);
      continue;
    }
    m = /^([A-Za-z0-9_]+)\s*=\s*(.+)$/.exec(line);
    if (!m) throw new Error(`unsupported TOML line: ${line}`);
    current[m[1]] = value(m[2]);
  }
  return root;
}
