// An in-memory stand-in for the one Cloudflare binding the collector uses, an
// R2 bucket, shaped to the Workers binding API as documented
// (https://developers.cloudflare.com/r2/api/workers/workers-api-reference/):
//
// - get(key) -> R2ObjectBody | null, with body, text(), json(),
//   customMetadata, httpMetadata and uploaded;
// - put(key, value, {httpMetadata, customMetadata, onlyIf}) -> R2Object, or
//   null when an onlyIf precondition fails. Only "if-none-match: *", the one
//   precondition the worker uses, is modelled;
// - delete(key | keys[]) -> void, at most 1,000 keys per call;
// - list({prefix, cursor, limit}) -> {objects, truncated, cursor}, in lexical
//   key order. A page may hold fewer than `limit` objects, so the fake's page
//   size can be lowered to force pagination.

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
    const onlyIf = options.onlyIf;
    if (onlyIf !== undefined) {
      const ifNoneMatch = onlyIf instanceof Headers ? onlyIf.get("if-none-match") : undefined;
      if (ifNoneMatch !== "*") throw new Error("fake R2: unmodelled precondition");
      if (this.objects.has(key)) return null;
    }
    const text = typeof value === "string" ? value : new TextDecoder().decode(value);
    const entry = {
      key,
      text,
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
