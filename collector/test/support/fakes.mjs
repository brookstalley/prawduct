// In-memory stand-ins for the Cloudflare bindings the collector uses, shaped
// to the APIs as documented (README § Docs consulted):
//
// - R2: bucket.get(key) -> R2ObjectBody | null, with body, text(), json(),
//   customMetadata, httpMetadata; bucket.put(key, value, {httpMetadata,
//   customMetadata}) -> R2Object.
// - Durable Object SQLite storage: storage.sql.exec(query, ...bindings) ->
//   cursor with toArray() and one(); storage.transactionSync(fn). Backed by
//   node's built-in SQLite, so the worker's SQL runs against a real engine.
// - Durable Object namespace: namespace.getByName(name) -> stub with
//   fetch(request), which calls the instance's fetch handler.

import { DatabaseSync } from "node:sqlite";
import { PendingReports } from "../../src/worker.js";

export class FakeSqlStorage {
  constructor() {
    this.db = new DatabaseSync(":memory:");
    this.sql = {
      exec: (query, ...bindings) => {
        const statement = this.db.prepare(query);
        const isRead = /^\s*SELECT/i.test(query);
        const rows = isRead ? statement.all(...bindings).map((r) => ({ ...r })) : (statement.run(...bindings), []);
        return {
          toArray: () => rows,
          one: () => {
            if (rows.length !== 1) throw new Error(`expected exactly one row, got ${rows.length}`);
            return rows[0];
          },
        };
      },
    };
  }

  transactionSync(fn) {
    this.db.exec("BEGIN");
    try {
      const result = fn();
      this.db.exec("COMMIT");
      return result;
    } catch (err) {
      this.db.exec("ROLLBACK");
      throw err;
    }
  }

  // Everything the database holds: each table's definition and every row, as
  // one string, for "nothing but X is stored" assertions.
  dump() {
    const tables = this.db.prepare("SELECT name, sql FROM sqlite_master").all();
    const parts = [];
    for (const t of tables) {
      parts.push(t.sql || "");
      if (t.sql && /^CREATE TABLE/i.test(t.sql)) {
        for (const row of this.db.prepare(`SELECT * FROM "${t.name}"`).all()) parts.push(Object.values(row).join(" | "));
      }
    }
    return parts.join("\n");
  }

  rows(table) {
    return this.db.prepare(`SELECT * FROM "${table}"`).all().map((r) => ({ ...r }));
  }
}

function objectBody(entry) {
  return {
    key: entry.key,
    size: entry.text.length,
    customMetadata: { ...entry.customMetadata },
    httpMetadata: { ...entry.httpMetadata },
    get body() {
      return new Response(entry.text).body;
    },
    text: async () => entry.text,
    json: async () => JSON.parse(entry.text),
  };
}

export class FakeR2Bucket {
  constructor() {
    this.objects = new Map();
    this.puts = [];
    // Set to a function(key) that throws to simulate a failed write.
    this.failPut = null;
  }

  async get(key) {
    const entry = this.objects.get(key);
    return entry === undefined ? null : objectBody(entry);
  }

  async put(key, value, options = {}) {
    if (this.failPut) this.failPut(key);
    const text = typeof value === "string" ? value : new TextDecoder().decode(value);
    const entry = {
      key,
      text,
      httpMetadata: options.httpMetadata || {},
      customMetadata: options.customMetadata || {},
    };
    this.objects.set(key, entry);
    this.puts.push(key);
    return objectBody(entry);
  }

  text(key) {
    const entry = this.objects.get(key);
    return entry === undefined ? undefined : entry.text;
  }
}

export class FakeDurableObjectNamespace {
  constructor(env) {
    this.env = env;
    this.instances = new Map();
    this.storages = new Map();
    // Every request a stub forwarded, for "no header crosses" assertions.
    this.received = [];
  }

  getByName(name) {
    return {
      fetch: async (request) => {
        this.received.push(request.clone());
        return this.instance(name).fetch(request);
      },
    };
  }

  instance(name) {
    if (!this.instances.has(name)) {
      const storage = this.storages.get(name) || new FakeSqlStorage();
      this.storages.set(name, storage);
      this.instances.set(name, new PendingReports({ storage }, this.env));
    }
    return this.instances.get(name);
  }

  // A restart: the in-memory instance goes, its storage stays.
  evict(name) {
    this.instances.delete(name);
  }
}

export function makeEnv() {
  const env = { BUNDLES: new FakeR2Bucket() };
  env.PENDING = new FakeDurableObjectNamespace(env);
  return env;
}

export function storageOf(env) {
  env.PENDING.instance("pending");
  return env.PENDING.storages.get("pending");
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
