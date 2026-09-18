# cordyceps — 60 rules (C# server, wide production use, embedded in a GUI host)

**Why this source matters:** the only non-Python server, so it separates language accidents from
real practices; and it is in wide use with strong user reviews, so its practices survived contact
with users rather than only with their author. Embedded in a long-running GUI app (Rhino/
Grasshopper), which forces stateless Streamable HTTP rather than stdio — the inverse of every
sibling, and the reason its transport rules are the richest here.

Prior distillation exists: `src/Cordyceps/Knowledge/McpTestingGuide.md`, 62 lines, correctly scoped
as an *agent-executed acceptance script*. Credit rather than duplicate. What it does NOT cover, and
where a corpus adds value: transport/lifecycle, concurrency, id echo, coercion, capability
negotiation, install/client integration.

## Error contract (L2)

- **Return every failure of a KNOWN tool as a normal result with `isError: true`** and a
  `{"success": false, "error": …}` body; reserve JSON-RPC protocol errors for request-level problems
  (unknown tool, unparseable envelope). broke-in-production: `isError` was hardcoded `false`, so
  every failure looked like a success; only 1 of 7 tools caught its own exceptions.
- **Place the "is this tool known?" check OUTSIDE the error-converting try**, so tool-identity errors
  stay protocol errors and everything downstream of identity becomes a structured result.
- **Compute `isError` from the FINAL text the caller receives**, after any envelope/status injection
  — never from the tool's pre-injection return value.
- **Classify as error only when the payload parses as an object whose `success` is boolean `false`**
  — unparseable text, a JSON array, absent `success` and the *string* `"false"` are all non-errors.
  9 dedicated test cases, each a distinct wrong answer. (Deliberately liberal on input coercion,
  strict on contract interpretation — that asymmetry is the design.)
- **Assert your own exception formatter round-trips through your own error detector.**
- **Log the full exception operator-side, send only `ex.Message` to the client** — two audiences,
  one catch. broke-in-production via Critic warning.

## JSON-RPC wire format (L2) — the highest-consequence cluster

- **Compute the response id BEFORE dispatching the method.** broke-in-production: large/fractional/
  string ids "no longer destroy the response after the tool already executed, **which caused clients
  to retry and double-apply mutations**". *An id bug is a mutation-duplication bug.* Invisible in
  testing (ids are usually small ints), catastrophic in production, one-line fix.
- **Echo the id by preserving its raw literal text, not its parsed value** — `1.0` stays `1.0`,
  `12345678901234567890123` survives, a date-shaped *string* id is never reinterpreted. 8 + 3
  pinned cases including `1.00`, `1e2`, `-0`, `2^63`, `0.30000000000000004`, `/Date(1600000000000)/`.
- **Treat only an ABSENT `id` as a notification** — explicit `"id": null` still gets a response.
- **Emit a null result as explicit `"result": null`** — a response with neither result nor error is
  malformed, and null-omission serializer settings are exactly what produces it. (C#-specific
  mechanism: the envelope survives by accident of being a `Dictionary`, and a code comment
  confidently claimed the opposite — "someone 'fixing' the inconsistency would have broken the wire
  format".)
- **Write characterization tests for your serializer's EMERGENT byte properties** — compactness,
  absence of a naming policy, non-ASCII escaping — because a library swap changes what every client
  parses while every behavioural test stays green.

## Argument coercion (L2)

- **Coerce across types at the parameter boundary** — accept `"300"` and `300.0` for integer params,
  and reject a true fraction with a message naming *why* ("not a whole number"). broke-in-production
  (#13): strictness here is a latent fail-close at a model-output seam.
- **Make number→bool coercion total** (nonzero is true, any numeric), not routed through an int
  parse that throws on `1.5` or `2^40`.
- **Make a 64-bit upper bound EXCLUSIVE of 2^63** — the max value rounds *up* in double, so an
  inclusive bound casts to minimum instead of rejecting. (Language-specific; absent in Python.)
- **Map integer types to `"integer"` and floats to `"number"` in generated schemas** — 17 named
  params had been declared `string`.
- **Parse every wire numeric with an invariant culture** — broke-in-production: camera coordinates
  "corrupting values on comma-decimal locales (`10.5` → `105` on a German system)". A *server-side
  locale* bug, so it only reproduces on the affected user's machine.

## Liveness — the strongest material in this repo (L1/L3)

- **Ride a small always-on status block on EVERY tool response**, injected at one choke point, never
  by the tools — so an agent can see a busy or wedged host without spending a call. Originated from
  a *user's* one-line question; neither open issue asked for it.
- **Provide one liveness action answering entirely from cached state that never touches the host** —
  the only call guaranteed to return when everything else is stuck — and document it as such in the
  server instructions. broke-in-production: "a busy solver and a dead bridge were indistinguishable —
  both produced silence until the client timed out, and the natural reaction (retry, or issue another
  `recompute`) actively made things worse". A read-only probe measured **~32 minutes of silence**
  during one solve.
- **Give the agent the three states it can act on differently** — *busy, wait* / *blocked, a human
  must clear it* / *healthy, so this is a real tool error* — and attach the action, not just the
  state. "A modal dialog needs a human, which is the one thing an unattended agent cannot summon."
- **When the host is busy, REFUSE with a structured result carrying `solving_since`** — do not queue
  (no completion signal) and do not block (reproduces the unbounded silence). Stacking recomputes is
  what raised the modal dialog that froze the canvas.
- **A liveness probe reporting a wedged host returns `success: true`** — reporting the bad state *is*
  the probe working. Only actions that refuse to run return false.
- **Make cross-cutting result injection TOTAL** — never throws, never damages the payload:
  non-object JSON, help text, malformed JSON, trailing garbage and both key names taken must each
  return the caller's result unchanged. ~20 enumerated tests. *"A liveness feature that can break an
  unrelated tool result is worse than no liveness feature."*
- **When your envelope key is taken, move aside to a fallback key; when both are taken, inject
  nothing.**
- **When re-serializing a payload you did not author, disable the parser's helpful conversions**
  (date detection, float representation) and reject trailing content.
- **A signal is only as trustworthy as what the REST of the system does to it.** *The single most
  transferable lesson here.* The heartbeat was verified never to block and was still wrong, because
  ordinary tool calls starve the same thread it measures — a healthy host mid-bake reported a modal
  dialog and told the agent to fetch a human. Found by two independent reviewers, not the author.
- **Do not gate such an inference on in-flight request count** — that counts the probe's own request
  and disables the inference permanently. Instrument the *resource*, and keep the probe out by
  construction.
- **Track host occupancy as a depth counter, not a flag, always paired in `finally`** — a leaked
  increment suppresses the inference for the process lifetime.
- **Emit an optional diagnostic field only when it differs from the default reading** — otherwise
  noise on every response and invisible when it matters.

## Lifecycle and shutdown (L3)

- **Free the port synchronously but drain in-flight handlers on a BACKGROUND task** — a synchronous
  drain on the host's UI thread can never succeed for exactly the handlers it protects, because
  those handlers are blocked waiting for that same thread. Previously froze the host ~2 seconds.
- **Snapshot the in-flight set before draining** — tasks tracked after the drain begins are not
  awaited, so a steady request stream cannot hang shutdown. (Its first test shipped *vacuous* and
  was caught by review.)
- **Capture shared teardown-able state into a local and null-guard at the request boundary**,
  returning "server is shutting down; the request was not processed".
- **When the host's invoke API cannot be cancelled, bound the LOCK ACQUIRE instead of the host call**
  — waiters fail fast with an actionable error while the wedged holder stays wedged. Verified by
  reflection that no bounded overload exists; timeout 120s. Residual documented rather than fixed.
- **Add a re-entrancy guard that runs inline when already on the host thread** — re-marshaling
  deadlocks, and taking the shared lock there deadlocks against a worker already in the invoke.
- **Model the lifecycle as one explicit state enum, not a conjunction of booleans** — teardown needs
  a `Stopping` phase to live in.
- **Release the port on EVERY path that ends the session, including host document close** —
  broke-in-production: closing the file left an orphaned server holding the port, so reopening
  failed **permanently** until the host restarted.
- **Bound every process-lifetime store an agent can grow, evict oldest-first, and REPORT what was
  evicted** plus the cap in every listing. Full document serializations had accumulated unbounded.

## HTTP transport (L3/L4) — forced here, so unusually well explored

- **Validate the `Origin` header against localhost** — a locally-bound HTTP MCP server is reachable
  from any web page the user visits (DNS rebinding).
- **Bind BOTH `localhost` and `127.0.0.1`** — clients disagree about which they dial.
- **Reject a request with no declared `Content-Length` (411)** — a chunked body bypasses your size
  cap entirely, so the cap is decorative until you require a declared length.
- **Accept `*/*` and `application/*`**, not only literal `application/json` — a strict check 406s
  working clients.
- **In stateless mode answer GET/DELETE `/mcp` with 405** rather than half-implementing sessions,
  and expose liveness on a separate plain `GET /health` a monitor can poll.
- **Make the health endpoint answer from CACHED state and say plainly that `"status": "ok"` means
  only the HTTP endpoint answered** — it previously read live host state on the worker thread and
  "returns nothing useful precisely when the host is wedged".
- **Surface an actionable bind failure**, distinguishing "another instance of us owns the port" from
  "a foreign process owns it". Users previously saw a bare "NOT RUNNING".

## Agent-facing surface (L1)

- **Use `initialize`'s `instructions` as the agent's operating manual** — tool/action index, failure
  triage table, and the domain traps that destroy work ("Inside a cluster editor, NEVER advise the
  user to press F5"). ~60 lines. *Also flagged as the highest-drift-risk string in the repo.*
- **Consolidate a wide API into few tools with an `action` param plus a mandatory `action='help'`**
  returning per-action required/optional/example/tips — **but know you are trading a small tool list
  for a wide flat parameter union.** Measured both ways: 7 tools / 100+ actions, 49% token reduction
  (1648→835 lines) on the docs; and `gh_canvas` declares **37** parameters, `rhino_render` **43**,
  all optional, in one schema. The real saving is moving per-action detail out of `tools/list` into
  a runtime `help` call. Direct tension with the `instructions` rule — both spend the same budget.
- **Make action matching case-insensitive exactly as the dispatcher is**, and test that the
  mixed-case path still enforces required params (that second test catches a lazy fix).
- **Treat a present-but-null required parameter as missing**, and make every validation error carry
  `availableActions`, `required` and the action's `example` — the error is the agent's recovery path.
- **Name the document/workspace each call acted on, on every response**, when the server resolves an
  ambient "active" target a human can retarget out from under the agent. Found by a user's question:
  every tool resolved through `ActiveCanvas`, so switching tabs silently retargeted the whole surface.
- **Validate then mutate; a parse failure is NEVER an empty collection.** *Highest-yield single rule
  by defect count* — one class behind most of a 10-HIGH-finding audit, across independently written
  actions. Worst instance: `configure` wiped every parameter and destroyed all wires from JSON that
  failed to parse and was read as `[]` — **while returning `success: true`**.
- **Every per-id loop returns per-id results** (`notFound`/`notSelectable`/`failed`) with overall
  `success: false` when anything failed. "Silent skips reported as `success:true` were the single
  most common bug." For an agent-facing server this is uniquely severe: the agent has no eyes, so a
  false success is not a cosmetic lie, it is the agent building confidently on destroyed state.
- **Never let an ABSENT field read as agreement** — emit explicit `*Skipped`/`*Unavailable` with a
  reason, and distinguish the two opposite meanings of a false result (`rebuildSkipped` benign vs
  `rebuildFailed` "probably still running the old program"). Issue #33: setting source stored text
  without recompiling, so the component kept executing its **previous program** while `set` reported
  success and `get` round-tripped the new text. Cost a reporter a full false-positive regression
  report. **Corollary: a clean read round-trip is never proof a write took effect** — the read may be
  served by a different store than the one that executes.
- **Document the failure mode your verification provably CANNOT catch**, rather than letting
  `verified: true` imply more than it means.
- **Validate a long-wait action's preconditions in one up-front hop** — `wait>0` burned the full
  timeout then reported success on a wrong-mode viewport.
- **For long work, expose a pollable progress reading plus an optional bounded wait returning
  `timedOut: true` with current progress** — they deliberately do NOT use MCP progress
  notifications. Unreconciled tension: the 100ms poll loop marshals to the host thread and competes
  with the liveness heartbeat.
- **Make the server's own in-host infrastructure INVISIBLE** — identical "not found" for a protected
  object as for a nonexistent one, extended transitively to anything wired to it. The real lesson is
  the enumeration of bypass routes (`group_rename`/`group_color`/`group_remove`/`group_add`).
- **Return generated binaries as `{filePath, hint}`, never base64** — "only where client and server
  are co-located". Independently rediscovered with the same precondition. *Note their hint string
  hardcodes a specific client's tool name — client-coupled prose in a client-agnostic surface.*
- **Wrap each action in ONE host undo record**, and when the host's begin-record returns a
  "already recording" sentinel, only close the record your own call opened. Undoing a bulk operation
  previously reverted one object at a time.

## Capability and version reporting (L2/L4)

- **Declare capabilities you implement and nothing more** — an unimplemented `listChanged` is a
  promise clients act on. (`protocolVersion` is hardcoded `"2025-06-18"` with no negotiation — a gap.)
- **Report the INFORMATIONAL version in `serverInfo.version`**, not a normalized assembly version —
  a tester asked to verify a fix otherwise cannot confirm which build they are running, defeating
  the point of pre-releases.
- **Ship agent-facing domain knowledge as MCP resources with stable `scheme://` URIs**, pointed at
  from the initialize instructions, optimized for LLM reading — **measured 49% token reduction** by
  converting prose to tables, removing parameter listings reachable via `action='help'`, and
  "eliminating basic Grasshopper knowledge LLMs already have".
- **Render an unfilled prompt-template placeholder as `[argname]`, never the bare argument name** —
  a bare name masquerades as prose mid-sentence and the agent acts on it. Shipped output was
  `"Accomplish goal now."`
- **Keep ERROR-level logs reaching the operator regardless of verbosity, buffer all levels
  regardless of the gate, and expose the buffer as a tool action the agent can read.**

## Testing (L3)

- **Extract every pure decision at the MCP boundary into a host-free module** linked into the test
  project — and treat "this feels like host glue" as the signal to extract, not to skip. An audit
  found ~10 helpers untestable only because they sat in host-coupled files; the Critic caught that
  the `verified`-field emission decision — *which was the fix itself* — sat where no test could
  reach it. 21 host-free modules now carry ~2,100 lines of tests against zero live-host coverage.
- **De-silence catches in those modules by NARROWING the exception type, not by adding logging**
  (the logger is literally uncompilable there).
- **A test claiming a TIMING contract must drive real concurrency** — a background task plus a
  `TaskCompletionSource` that deliberately never completes. Standing in an already-completed task
  passes vacuously, and one such test shipped.
- **Disable suite parallelization when asserting timing/concurrency on a small CI runner** — passed
  locally and on one PR, failed twice on the next with no relevant change.
- **Maintain an explicit append-only queue of what only a running host can confirm**, with repro
  steps and the expected pre-fix symptom. *Their own file records 6 of 8 entries sat `pending`
  behind a disabled gate — a write-only queue. The rule needs an enforcing read or it decays.*
- **Treat the agent-facing documentation surfaces as a checklist executed on every change.** One
  1.5.0 audit found: bulk-wire examples using nonexistent connection keys, a documented `operation=
  'list'` that never existed, response fields that don't exist, a `search_components` tool that
  doesn't exist, and undo/redo advertised as working while permanently stubbed. **Generalizable
  finding: agent-facing docs drift toward plausible-but-nonexistent API, because they are written by
  the same model that would hallucinate it.**

## Doc-vs-code findings (worth reporting back to that repo)

1. `McpTestingGuide.md` says a missing required parameter is a JSON-RPC protocol error; the code
   returns a structured tool result for it (changed in 1.5.0, guide not updated). **A tester
   following the guide would file a false regression.**
2. `CLAUDE.md` and `boundary-patterns.md` describe an HTTP+SSE server with SSE sessions. There is no
   SSE — the code is stateless Streamable HTTP, GET/DELETE return 405. Both files are the primary
   architecture briefing a new agent reads.
