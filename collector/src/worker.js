// The prawduct stats collector: a Cloudflare Worker that accepts anonymous
// stats reports and publishes them once a day as one sorted bundle.
//
// The collector exists to serve two goals, and the second outranks the first:
// collect telemetry that improves prawduct, and know nothing about the
// contributor. So this file:
//
// - imports nothing, so every line that runs is in this file;
// - reads no request header except content-type and content-length, and never
//   touches the request's cf object;
// - never logs (there is no console call anywhere in it);
// - stores a report as one R2 object whose body is its canonical bytes, under a
//   key made of its content hash and a random suffix, with no metadata, so
//   neither the key nor the object says who sent it or in what order;
// - publishes a day's reports sorted by their bytes, so a bundle's order says
//   nothing about when any report arrived.

// --- the allowlist ------------------------------------------------------------

// A copy of collector/schema.json, which is itself a byte-for-byte copy of
// plugin/lib/contribution_schema.json. A test pins this object to that file.
export const SCHEMA = {
  schema: 1,
  about:
    "The allowlist for an anonymous prawduct stats report. A report may carry only these keys. Every value is an integer, a number on the field's step, one of the field's enum values, or one of the volume bands below, so no field can hold text. A field naming floor_on is left out of the report when that denominator is under floor.",
  floor: 5,
  bands: ["0", "1-9", "10-49", "50-199", "200+"],
  fields: {
    schema: { type: "integer", min: 1, max: 1, required: true },
    iso_year: { type: "integer", min: 2025, max: 2100, required: true },
    iso_week: { type: "integer", min: 1, max: 53, required: true },
    plugin_major: { type: "integer", min: 0, max: 999, required: true },
    plugin_minor: { type: "integer", min: 0, max: 999, required: true },
    dev: { type: "enum", values: [false, true], required: true },

    sessions: { type: "band" },
    scopes: { type: "band" },
    reviews: { type: "band" },

    rounds_per_scope_median: { type: "number", step: 0.5, min: 0, max: 100, floor_on: "scopes" },
    rounds_per_scope_p90: { type: "number", step: 0.5, min: 0, max: 100, floor_on: "scopes" },
    review_minutes_median: { type: "number", step: 1, min: 0, max: 600, floor_on: "measured_reviews" },
    review_minutes_per_scope_median: { type: "number", step: 1, min: 0, max: 6000, floor_on: "measured_scopes" },
    estimated_only_review_share: { type: "number", step: 0.05, min: 0, max: 1, floor_on: "reviews" },
    empty_verify_round_share: { type: "number", step: 0.05, min: 0, max: 1, floor_on: "verify_rounds" },
    rereview_same_interval_share: { type: "number", step: 0.05, min: 0, max: 1, floor_on: "reviews" },
    rereview_same_head_share: { type: "number", step: 0.05, min: 0, max: 1, floor_on: "reviews" },
    stops_blocked_per_session: { type: "number", step: 0.1, min: 0, max: 100, floor_on: "sessions" },
    guard_refusals_per_session: { type: "number", step: 0.1, min: 0, max: 100, floor_on: "sessions" },
    transfer_grants_per_session: { type: "number", step: 0.1, min: 0, max: 100, floor_on: "sessions" },

    blocking_per_review: { type: "number", step: 0.1, min: 0, max: 100, floor_on: "reviews" },
    warning_per_review: { type: "number", step: 0.1, min: 0, max: 100, floor_on: "reviews" },
    note_per_review: { type: "number", step: 0.1, min: 0, max: 100, floor_on: "reviews" },
    blocking_acted_on_rate: { type: "number", step: 0.05, min: 0, max: 1, floor_on: "answered_blocking" },
    warning_acted_on_rate: { type: "number", step: 0.05, min: 0, max: 1, floor_on: "answered_warning" },
    note_acted_on_rate: { type: "number", step: 0.05, min: 0, max: 1, floor_on: "answered_note" },
    blocking_fixed_per_scope: { type: "number", step: 0.1, min: 0, max: 100, floor_on: "scopes" },
    warning_fixed_per_scope: { type: "number", step: 0.1, min: 0, max: 100, floor_on: "scopes" },
    red_test_run_share: { type: "number", step: 0.05, min: 0, max: 1, floor_on: "test_runs" },
  },
};

// The largest report schema 1 allows is under 800 bytes in canonical form, and
// under 1 KiB pretty-printed. 4 KiB admits every valid report however it is
// spaced, and refuses anything that could only be padding or abuse before it
// is parsed.
export const MAX_BODY_BYTES = 4096;

// Steps are decimal fractions that binary floats carry inexactly. The client
// (contribution._STEP_EPSILON) uses the same tolerance.
const STEP_EPSILON = 1e-6;

// --- strict JSON -----------------------------------------------------------------

// JSON.parse cannot tell 1 from 1.0, and the allowlist must: Python reads 1.0
// as a float, which an integer field refuses. So the body is parsed here, by
// the same grammar Python's json module accepts, minus NaN and Infinity (which
// the allowlist refuses anyway). Objects become Maps, which keep the first
// position and the last value of a repeated key, as a Python dict does.

export class JsonNumber {
  constructor(value, isInt) {
    this.value = value;
    this.isInt = isInt;
  }
}

class JsonSyntaxError extends Error {}

const NUMBER_RE = /-?(?:0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?/y;

export function parseJson(text) {
  let i = 0;
  const fail = () => {
    throw new JsonSyntaxError("invalid JSON");
  };
  const ws = () => {
    while (i < text.length) {
      const c = text[i];
      if (c === " " || c === "\t" || c === "\n" || c === "\r") i++;
      else break;
    }
  };
  const literal = (word, value) => {
    if (text.startsWith(word, i)) {
      i += word.length;
      return value;
    }
    return fail();
  };
  const string = () => {
    i++; // opening quote
    let out = "";
    for (;;) {
      if (i >= text.length) fail();
      const c = text[i];
      const code = c.charCodeAt(0);
      if (c === '"') {
        i++;
        return out;
      }
      if (code < 0x20) fail();
      if (c !== "\\") {
        out += c;
        i++;
        continue;
      }
      const e = text[i + 1];
      i += 2;
      if (e === '"' || e === "\\" || e === "/") out += e;
      else if (e === "b") out += "\b";
      else if (e === "f") out += "\f";
      else if (e === "n") out += "\n";
      else if (e === "r") out += "\r";
      else if (e === "t") out += "\t";
      else if (e === "u") {
        const hex = text.slice(i, i + 4);
        if (!/^[0-9a-fA-F]{4}$/.test(hex)) fail();
        out += String.fromCharCode(parseInt(hex, 16));
        i += 4;
      } else fail();
    }
  };
  const number = () => {
    NUMBER_RE.lastIndex = i;
    const m = NUMBER_RE.exec(text);
    if (!m) fail();
    i += m[0].length;
    return new JsonNumber(Number(m[0]), m[1] === undefined && m[2] === undefined);
  };
  const value = () => {
    ws();
    const c = text[i];
    if (c === "{") {
      i++;
      const map = new Map();
      ws();
      if (text[i] === "}") {
        i++;
        return map;
      }
      for (;;) {
        ws();
        if (text[i] !== '"') fail();
        const key = string();
        ws();
        if (text[i] !== ":") fail();
        i++;
        map.set(key, value());
        ws();
        if (text[i] === ",") {
          i++;
          continue;
        }
        if (text[i] === "}") {
          i++;
          return map;
        }
        fail();
      }
    }
    if (c === "[") {
      i++;
      const list = [];
      ws();
      if (text[i] === "]") {
        i++;
        return list;
      }
      for (;;) {
        list.push(value());
        ws();
        if (text[i] === ",") {
          i++;
          continue;
        }
        if (text[i] === "]") {
          i++;
          return list;
        }
        fail();
      }
    }
    if (c === '"') return string();
    if (c === "t") return literal("true", true);
    if (c === "f") return literal("false", false);
    if (c === "n") return literal("null", null);
    return number();
  };
  const result = value();
  ws();
  if (i !== text.length) fail();
  return result;
}

// --- validation -------------------------------------------------------------------

// The same rules as contribution.validate, in the same order. Each problem is
// a rule name only: a refusal never repeats what was sent.

function kindOf(v) {
  if (typeof v === "boolean") return "bool";
  if (v instanceof JsonNumber) return v.isInt ? "int" : "float";
  if (typeof v === "number") return Number.isInteger(v) ? "int" : "float";
  if (typeof v === "string") return "str";
  if (v === null) return "null";
  return "other";
}

function plain(v) {
  return v instanceof JsonNumber ? v.value : v;
}

function isNumber(v) {
  // Booleans are never numbers here, as Python's bool-is-int is refused there.
  return v instanceof JsonNumber && Number.isFinite(v.value);
}

function fieldProblem(spec, v, bands) {
  if (spec.type === "enum") {
    const ok = spec.values.some((allowed) => kindOf(allowed) === kindOf(v) && plain(v) === allowed);
    return ok ? null : "enum";
  }
  if (spec.type === "band") {
    return typeof v === "string" && bands.includes(v) ? null : "band";
  }
  if (spec.type === "integer" || spec.type === "number") {
    if (!isNumber(v)) return "not-number";
    if (spec.type === "integer" && !v.isInt) return "not-integer";
    if (!(spec.min <= v.value && v.value <= spec.max)) return "range";
    if (spec.step !== undefined) {
      const q = v.value / spec.step;
      if (Math.abs(q - Math.round(q)) > STEP_EPSILON) return "step";
    }
    return null;
  }
  return "unknown-type";
}

export function validate(report, schema = SCHEMA) {
  if (!(report instanceof Map)) return ["not-object"];
  const fields = schema.fields;
  const has = (k) => Object.prototype.hasOwnProperty.call(fields, k);
  const problems = [];
  for (const key of report.keys()) if (!has(key)) problems.push("unknown-key");
  for (const [name, spec] of Object.entries(fields)) {
    if (spec.required && !report.has(name)) problems.push("missing-key");
  }
  for (const [name, v] of report) {
    if (!has(name)) continue;
    const problem = fieldProblem(fields[name], v, schema.bands);
    if (problem) problems.push(problem);
  }
  return problems;
}

// --- canonical bytes ----------------------------------------------------------------

// Sorted keys, no whitespace: Python's
// json.dumps(report, sort_keys=True, separators=(",", ":")), which is what the
// client computes and shows the contributor before sending.
//
// A stepped number is written as the client's to_step writes it: snapped to
// its step, rounded to one decimal more than the step has, and as an integer
// when it is whole. For every value the client can produce this is the value
// itself, and a value the allowlist admits within its tolerance (0.35000000001)
// is stored as the grid value it stands for (0.35).

function stepDecimals(step) {
  return Math.max(0, -Math.floor(Math.log10(step))) + 1;
}

function formatNumber(spec, n) {
  let value = n.value;
  if (spec.step !== undefined) {
    const snapped = Math.round(value / spec.step) * spec.step;
    value = Number(snapped.toFixed(stepDecimals(spec.step)));
  }
  if (Object.is(value, -0)) value = 0;
  // Every admitted value is in [0, 6000] and on a step of at least 0.05, so
  // String() gives the same shortest round-trip digits as Python's repr, with
  // no exponent.
  return String(value);
}

function formatString(s) {
  // ensure_ascii: anything outside printable ASCII is escaped, as Python does.
  let out = '"';
  for (const c of s) {
    const code = c.codePointAt(0);
    if (c === '"') out += '\\"';
    else if (c === "\\") out += "\\\\";
    else if (c === "\n") out += "\\n";
    else if (c === "\r") out += "\\r";
    else if (c === "\t") out += "\\t";
    else if (c === "\b") out += "\\b";
    else if (c === "\f") out += "\\f";
    else if (code < 0x20 || code > 0x7e) {
      for (let k = 0; k < c.length; k++) out += "\\u" + c.charCodeAt(k).toString(16).padStart(4, "0");
    } else out += c;
  }
  return out + '"';
}

// The canonical text of a report that has already passed validate().
export function canonicalize(report, schema = SCHEMA) {
  const keys = [...report.keys()].sort();
  const parts = keys.map((key) => {
    const v = report.get(key);
    let text;
    if (typeof v === "boolean") text = v ? "true" : "false";
    else if (typeof v === "string") text = formatString(v);
    else if (v instanceof JsonNumber) text = formatNumber(schema.fields[key], v);
    else text = "null";
    return formatString(key) + ":" + text;
  });
  return "{" + parts.join(",") + "}";
}

// parse + validate + canonicalize. {ok: true, canonical} or {ok: false, rule}.
export function admit(text, schema = SCHEMA) {
  let report;
  try {
    report = parseJson(text);
  } catch (err) {
    if (err instanceof JsonSyntaxError || err instanceof RangeError) return { ok: false, rule: "json" };
    throw err;
  }
  const problems = validate(report, schema);
  if (problems.length) return { ok: false, rule: problems[0] };
  return { ok: true, canonical: canonicalize(report, schema) };
}

// --- HTTP helpers -------------------------------------------------------------------

function refuse(rule) {
  return new Response(JSON.stringify({ refused: rule }), {
    status: 400,
    headers: { "content-type": "application/json" },
  });
}

function status(code, extra) {
  return new Response(null, { status: code, headers: extra || {} });
}

function isJsonMediaType(value) {
  if (value === null) return false;
  return value.split(";")[0].trim().toLowerCase() === "application/json";
}

// The body, as text, or null when it is longer than the cap. Reads at most
// MAX_BODY_BYTES + 1 bytes whatever content-length claims.
async function boundedText(request) {
  const declared = request.headers.get("content-length");
  if (declared !== null && Number(declared) > MAX_BODY_BYTES) return null;
  if (request.body === null) return "";
  const reader = request.body.getReader();
  const chunks = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX_BODY_BYTES) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }
  const bytes = new Uint8Array(size);
  let at = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, at);
    at += chunk.byteLength;
  }
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return undefined;
  }
}

// --- R2 layout ------------------------------------------------------------------------
//
// pending/<sha256 of the bytes>-<128 random bits>  one accepted report each
// claims/current.json                              the flush in progress, if any
// bundles/<YYYY-MM-DD>.jsonl                       a day's published reports
// bundles/index.json                               {"days": [...]}
//
// Only bundles/ is ever served.

export const PENDING_PREFIX = "pending/";
export const CLAIM_KEY = "claims/current.json";
export const INDEX_KEY = "bundles/index.json";
export const bundleKey = (day) => `bundles/${day}.jsonl`;
const DAY_RE = /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/;

// The most reports one flush claims. A flush spends about one R2 call per
// report plus a dozen more, and the Free plan allows 1,000 calls to Cloudflare
// services per invocation. Anything beyond the cap stays pending for the next
// flush.
export const MAX_CLAIM = 900;
// R2's delete takes at most 1,000 keys per call.
const DELETE_BATCH = 1000;

function hex(bytes) {
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function randomHex(n) {
  return hex(crypto.getRandomValues(new Uint8Array(n)));
}

// The content hash groups identical reports; the random suffix keeps two of
// them apart, so both are counted. Neither part depends on when the report
// arrived or who sent it, and R2 lists keys in lexical order, so a listing's
// order is no arrival order either.
export async function pendingKey(canonical) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonical));
  return PENDING_PREFIX + hex(new Uint8Array(digest)) + "-" + randomHex(16);
}

// --- the public Worker ----------------------------------------------------------------

async function postReport(request, env) {
  if (!isJsonMediaType(request.headers.get("content-type"))) return refuse("content-type");
  const text = await boundedText(request);
  if (text === null) return refuse("too-large");
  if (text === undefined) return refuse("json");
  const verdict = admit(text);
  if (!verdict.ok) return refuse(verdict.rule);
  try {
    // The canonical bytes and nothing else: no options, so no metadata.
    await env.BUNDLES.put(await pendingKey(verdict.canonical), verdict.canonical);
  } catch { // prawduct:allow prawduct/broad-except -- system boundary: any storage failure is a retryable 503, and its message is never surfaced
    return status(503);
  }
  return status(204);
}

async function getObject(env, key, contentType) {
  const object = await env.BUNDLES.get(key);
  if (object === null) return status(404);
  return new Response(object.body, {
    status: 200,
    headers: { "content-type": contentType, "cache-control": "public, max-age=300" },
  });
}

export async function route(request, env) {
  const path = new URL(request.url).pathname;
  if (path === "/v1/report") {
    return request.method === "POST" ? postReport(request, env) : status(405, { allow: "POST" });
  }
  if (path === "/" + INDEX_KEY) {
    return request.method === "GET" ? getObject(env, INDEX_KEY, "application/json") : status(405, { allow: "GET" });
  }
  const m = /^\/bundles\/([^/]+)\.jsonl$/.exec(path);
  if (m && DAY_RE.test(m[1])) {
    return request.method === "GET"
      ? getObject(env, bundleKey(m[1]), "application/x-ndjson")
      : status(405, { allow: "GET" });
  }
  return status(404);
}

// The UTC day a flush runs on names its bundle.
export function flushDay(scheduledTime) {
  return new Date(scheduledTime).toISOString().slice(0, 10);
}

export default {
  async fetch(request, env) {
    return route(request, env);
  },

  // A failed flush throws, so the cron run is marked failed; whatever it had
  // claimed is finished by the next run.
  async scheduled(controller, env) {
    await flush(env.BUNDLES, flushDay(controller.scheduledTime));
  },
};

// --- the daily flush -----------------------------------------------------------------------
//
// 1. Claim: list up to MAX_CLAIM pending keys and write them, with a random
//    claim id and the day, to claims/current.json, only if no claim exists.
// 2. Publish: unless the day's bundle already carries this claim id in its
//    custom metadata, merge the claimed reports into it, sort, and write it
//    with the id. Add the day to the index.
// 3. Clean up: delete the claimed pending objects, then the claim.
//
// A run that finds a claim finishes it instead of taking a new one, and the id
// on the bundle stops a claim from being merged twice. So a report is
// published once even if a run dies between the bundle write and the deletes.

async function listPending(bucket, max) {
  const keys = [];
  let cursor;
  do {
    const page = await bucket.list({ prefix: PENDING_PREFIX, cursor });
    for (const object of page.objects) keys.push(object.key);
    cursor = page.truncated ? page.cursor : undefined;
  } while (cursor !== undefined && keys.length < max);
  return keys.slice(0, max);
}

async function readClaim(bucket) {
  const object = await bucket.get(CLAIM_KEY);
  return object === null ? null : object.json();
}

async function takeClaim(bucket, day) {
  const keys = await listPending(bucket, MAX_CLAIM);
  if (keys.length === 0) return null;
  const claim = { id: randomHex(16), day, keys: keys.sort() };
  // Create-only: if another run claimed first, finish its claim instead.
  const created = await bucket.put(CLAIM_KEY, JSON.stringify(claim), {
    httpMetadata: { contentType: "application/json" },
    onlyIf: new Headers({ "if-none-match": "*" }),
  });
  return created === null ? readClaim(bucket) : claim;
}

async function publish(bucket, claim) {
  const key = bundleKey(claim.day);
  const existing = await bucket.get(key);
  if (existing === null || (existing.customMetadata || {}).claim !== claim.id) {
    const lines = existing === null ? [] : (await existing.text()).split("\n").filter((line) => line !== "");
    for (const pending of claim.keys) {
      const object = await bucket.get(pending);
      if (object === null) continue;
      const text = await object.text();
      // Only canonical, allowlisted bytes are ever published, whatever else
      // may have been written under pending/.
      const verdict = admit(text);
      if (verdict.ok && verdict.canonical === text) lines.push(text);
    }
    // Nothing claimed survived re-admission and there is no bundle to keep.
    if (lines.length === 0) return;
    // Canonical bytes are ASCII, so code-unit order is byte order.
    lines.sort();
    await bucket.put(key, lines.join("\n") + "\n", {
      httpMetadata: { contentType: "application/x-ndjson" },
      customMetadata: { claim: claim.id },
    });
  }
  const index = await bucket.get(INDEX_KEY);
  const days = index === null ? [] : (await index.json()).days;
  if (!days.includes(claim.day)) {
    days.push(claim.day);
    days.sort();
    await bucket.put(INDEX_KEY, JSON.stringify({ days }), {
      httpMetadata: { contentType: "application/json" },
    });
  }
}

export async function flush(bucket, day) {
  const claim = (await readClaim(bucket)) || (await takeClaim(bucket, day));
  if (claim === null) return;
  await publish(bucket, claim);
  for (let i = 0; i < claim.keys.length; i += DELETE_BATCH) {
    await bucket.delete(claim.keys.slice(i, i + DELETE_BATCH));
  }
  // Drop the claim only if it is still this one.
  const current = await readClaim(bucket);
  if (current !== null && current.id === claim.id) await bucket.delete(CLAIM_KEY);
}

