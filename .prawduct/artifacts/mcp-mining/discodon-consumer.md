# discodon — 48 rules (the CONSUMER's view)

**Why this source outranks the others:** discodon is an MCP *client/bridge*, not a server. It is the
only source that observed servers it did not write. Every defensive line in its bridge is a scar
left by some server behaving badly.

**Headline ratio:** ~2/3 of its rules defend against **legal-but-hostile** behaviour (size, latency,
no progress, session leaks, name collisions, frozen schemas, blocking handlers). Only three defend
against outright spec violations. *The spec is largely respected in the wild; what breaks
integrations is legal behaviour that ignores the consumer's budgets.*

Evidence split: broke-in-production 18 · measured 26 · designed-untested 4.
Pins: `fastmcp==3.4.2`, `mcp 1.28.1`, protocol `2025-06-18`.

## A. Tool surface and schema

- **Emit explicit `"type": "object"` at every `inputSchema` root**, even when empty. Consumers patch
  it in (`if "type" not in input_schema`) because real servers advertise `{"properties": …}` with no
  type and the Anthropic tool-definition API rejects it. L2/constraint.
- **Keep one server at ≤ ~20 tools or ship a server-side filter.** `DEFAULT_MAX_TOOLS = 20`, and past
  it the consumer **silently slices** after one log line the agent never sees. Tools 21+ do not exist
  to the model, in advertised order. L1/constraint.
- **Front-load the first ~120 chars of every description.** The bridge hard-clips at
  `[:117] + "..."` when rendering the roster into the prompt. L1/constraint.
- **Ship a non-empty description** — a missing one becomes `MCP tool: {name}`, nothing inferred. L1.
- **Do not set `additionalProperties: false` if you want to be proxyable.** It converts every
  intermediary from a pass-through into a schema-rewriter or takes a 422; priced as "medium change
  wanting a build plan + Critic pass". L2/decision-point. broke-in-production.
- **Declare read-only vs mutating per tool**, or a gating proxy hardcodes your action names and goes
  stale. Their fallback: treat unclassified as mutating. L2/pattern.
- **Namespace tool names — a collision across two servers is a silent dispatch HANG, not an error.**
  (claude-code#50319.) The bridge raises at registration, deliberately outside its best-effort
  catch, and re-checks on connect, every refresh and every reconnect. L4/constraint.
- **Keep params flat `str|int|bool|null`; pass structures as JSON strings** — "avoids MCP client
  compatibility issues". Consumers must then accept dict *or* JSON string. L1/stance.
- **Accept `"true"`/`"false"` strings for booleans and REJECT other strings.** A coercer answering
  False for anything unrecognised makes a typo indistinguishable from omission. Empty string is
  deliberately "omitted", so one wire value never means two things. L1/diagnostic.

## B. The fat-tool / action-dispatch pattern — four independent scars

- **Refuse a parameter the dispatched action does not declare; never accept-and-drop.** A union
  signature forwards everything and unrecognised params die in `**kwargs`: `list_runs` given a
  `campaign_id` returned *every run in the universe*. "A filter taken and not applied is the same
  confident-wrong answer as a malformed id reported as an empty result." L1/constraint.
- **Pin mechanically that ∪(action params) == facade schema properties, both directions.** Three
  invisible failures: params declared by a handler but not the facade (silently unreachable);
  handlers reading undeclared params (now refused their own argument); six schema params no action
  declared (dead, and worse under the refusal — every action rejects them). L1/diagnostic.
- **Default every facade parameter to `null`.** A non-`None` default arrives at every action as a
  supplied value, so one of them refuses every call. Corollary: an omitted param arrives PRESENT and
  None, so `kwargs.get(name, default)` is dead code and the param is mandatory in fact whatever help
  says. L1/constraint.
- **Make `action='help'` authoritative and source it from the dispatcher's own registry** — the
  schema alone cannot say which action accepts what, because it is the union. L1/pattern.

## C. Results, errors, content blocks

- **Report tool failure as `isError: true`, never an exception** — anything that raises lands in the
  consumer's broad catch and **costs a full session teardown + reconnect**. L2/constraint.
- **Never return zero content blocks** — consumers invent `"No content returned"` because empty
  `content: []` is indistinguishable from a successful no-op. L2/constraint.
- **Put every load-bearing fact in a TextContent block.** Images flatten to `"[Image: image/png]"`,
  ResourceLinks to `"[Link: … — …]"`. Nothing in the image survives. L2/constraint.
- **Duplicate `structuredContent` into text** — a naive text-only proxy drops it, and the sibling
  bridge in the same repo does exactly that. L2/constraint.
- **A tool that can return binary must still return failures as text** — and widening a return
  annotation to a union **deletes your `outputSchema`** under fastmcp. "An image cannot carry a
  failure." L2/decision-point.
- **Give every error a machine-readable code in a fixed position** (`Error (CODE): message`).
  A bare `"Error: …"` matched nothing, so rejected calls logged `status=ok`. 101 code-less returns
  across 17 modules; miscoding is as bad — `Error (VALIDATION):` matched no entry in
  `_USER_INPUT_ERROR_CODES` (which holds `validation_error`), so a user typo logged as a system bug.
- **Canonicalize ids before matching and refuse unrecoverable ones.** Exact-match partition keys mean
  a non-canonical id matches nothing and reads as "this universe has spent nothing". 19 actions
  across four tools were unguarded. Note the self-own: truncated prefixes copied off *the server's
  own abbreviated display*. L1/diagnostic.

## D. Response size — the highest-value category

- **Default to a truncated render with a named opt-in.** One measured result was **249,942
  characters** — trace 74%, spans 24%, the judge reasoning anyone actually opens it for under 2%.
  All-or-nothing made reading the 2% cost the other 98% and overflow the client's budget.
- **When you truncate, say how much was dropped and name the exact call that returns the whole
  value — once per response, not per item.** "A bare trailing ellipsis reads as the end of the value
  rather than as a clip." Marker: `…(+N chars — <opt_in>)`, N counted against what was KEPT.
- **Clamp an out-of-range value rather than refusing, and say you clamped** — a bare refusal costs a
  round-trip the agent spends guessing a smaller number. L1/pattern.
- **Never use a bare `token` key for a secret.** Consumer redaction deliberately omits it (it would
  catch `token_count`, `continuation_token`); a bare `token` lands unredacted in a 200-entry ring
  buffer and a WebSocket broadcast. Use `access_token`/`api_key`. L4/constraint.

## E. Long-running, progress, wedged-vs-slow

- **Emit progress for anything over ~30s.** `analysis_generate` ran ~12 min silently; separately it
  **returned ~30 minutes after the work completed and stored normally** ($0.8005 spent) — "a
  response-path hang, not a work hang… indistinguishable from a runaway generation, which is the
  state an operator is most likely to react to expensively (kill it, retry, pay again)."
- **Size timeouts per tool class, and never cancel work you have already billed for.** A generation
  inheriting a 120s default written for quick reads was cancelled mid-flight on a 22-run campaign:
  **billed, nothing stored**, signal was "timed out after 120s". Fix: `generation_action_timeout_s
  = 900.0`, documented as a deliberate over-estimate rather than a measurement.
- **Keep any advertised max duration strictly below your dispatch timeout, with margin.** At shipped
  defaults both were 120, so a maximal capture raced its own budget and lost — "the caller would get
  'timed out' for a capture doing exactly what it was asked". Noted at three other call sites.
  Margin constant: 15.0s.
- **A timeout reply must say whether work was CANCELLED or is STILL RUNNING** — opposite
  instructions. `detached`: nothing can interrupt it, it may land writes long after the caller was
  told it timed out. `queued`: dropped, and telling the caller it will run later would leave them
  waiting for a result that can never arrive. L3/diagnostic.
- **Never run a blocking handler on the transport's event loop.** Production head-of-line blocking:
  `classifier_run` **wrote all 29 results then never returned** while three queued calls made zero
  progress until all were cancelled. Isolated on a dedicated pool, because on the default executor
  stuck workers starve `/healthz` and `/readyz` and Kubernetes reads the pod as dead.
- **Assume the consumer has NO timeout on your call.** The third-party path is unbounded and filed
  open: "a hung third-party server cancels the entire entity turn."
- **Close the transport when your session dies.** A session that died between 300s refresh ticks
  stayed a stale handle for up to 5 minutes: every call returned "Session terminated" while health
  reported `upstream_connected=True, reconnect_attempts=0, last_error=null`. The fix treats ANY
  exception as session death — so a transient error on a healthy session now costs a full reconnect.
- **Fail fast with machine-readable diagnostics when unavailable** — pinned at **<100ms** against a
  former 5-second opaque wait; payload must carry profile, backend, last_error, last_error_at,
  reconnect_attempts and a named next command. Placeholders are `"(none recorded)"`/`"(never)"`,
  with a test asserting no raw Python `None` leaks.
- **Distinguish "process not listening" from "session not established"** — separate 1s TCP probe,
  separate message, separate remedy, re-probed each call.

## F. Capability caching and refresh — the client-behaviour findings

- **Send `tools/list_changed` on ANY definition change** — name, description or `inputSchema` — not
  just when the name set changes. A backend deploy that changed a schema but kept the name left
  Claude Code validating against the stale schema and rejecting the new parameter with "Additional
  properties are not allowed". Fingerprint now hashes `{name, description, inputSchema}`.
- **Treat a published parameter schema as FROZEN. Add a required parameter under a new tool name.**
  *The single most important client-behaviour finding in the corpus.* They built the entire correct
  server half — full-definition fingerprinting, list_changed on any delta, force-notify on reconnect
  — and recorded that it **"did not help."** The client keeps the schema it registered. Measured
  twice; a required `confirm` param became unreachable and a destructive operator command had to be
  run outside MCP. Final remedy was a `restart_required: true` field — telling the operator, not a
  mechanism. L4/constraint.
- **Answer `tools/list` immediately even when your backend is not ready, then push list_changed.**
  Claude Code calls it during init; not-ready yields an empty list. Cap the wait (10s) and serve
  cached rather than stall.
- **Do not suppress notifications you think are redundant, and do not send them when nothing
  changed.** Both directions pinned; reconnect force-notifies even a byte-identical list.
- **Expect consumers to serve your LAST-KNOWN tool list while you are down** — so a tool you remove
  stays visible until you return. (The two consumers in this one repo do opposite things here.)
- **Provide a client-invocable re-discovery action; do not assume anyone polls.**

## G. Transport, sessions, startup

- **stdio: write NOTHING to stdout but JSON-RPC.** All logging to stderr; no `print()` anywhere.
- **A stdio server must survive its own crashes in-process** — Claude Code does not respawn cleanly
  on non-zero exit (claude-code#15904, **closed as not planned** — "the bridge is permanent"). They
  `os.execv` themselves, rate-capped at 5 restarts/60s, with history in an env var because execv
  preserves the environment and resets every Python structure.
- **Stateful HTTP sessions never end on their own — ship an idle timeout, never default it off.**
  Measured 2026-08-05: **1,153 live sessions accumulated at ~1 per 3 seconds, ~154 KiB each, zero
  terminations in six hours → OOMKilled.** Default now 1800s; 0 documented as unbounded growth.
- **Choose stateful only if you push server-initiated notifications.** Their single reason was
  persistent SSE streams; everything above is the price of that one feature.
- **Log `Mcp-Session-Id` per request and name the CAUSE when a session ends.** Gotcha: `initialize`
  carries no session header — it is assigned one, so read it off the response.
- **Never present an unexpanded `${VAR}` as a credential; detect it explicitly.** Hosts do not
  reliably expand env vars in server config. Both ends check `token.startswith("${")`.
- **Make a 401 say WHICH 401 it is.** A bare `None` on non-200 made "offline", "unauthorized" and
  "this route is not reachable with a bearer" one answer — and the third was silently true of prod
  for the endpoint's entire life. A 2026-06-17 investigation closed it as "not a code defect",
  "exactly the wrong conclusion a silent None invites."
- **Treat HTTP 200 as "a response arrived", not "it worked"** — pinned with a 200 whose body is
  `"<html>"` (proxy/login interception).
- **Do not require interactive OAuth** — an unattended agent cannot complete a browser redirect.
- **Isolate per-session state** — one consumer process may hold several concurrent sessions for
  different principals.

## H. What consumers do TO you

- **Expect to be disabled, not retried, after one failed probe** — recorded `unreachable` and skipped
  on subsequent boots until a human re-probes.
- **Expect an HTTP URL resolving to a private address to be refused outright** (SSRF protection).
- **Expect your whole connection lifecycle wrapped in a broad catch** — a startup failure gets you
  *disabled, not diagnosed*, and your connection error string is the entire diagnostic surface an
  operator ever sees.
- **If your MCP server is a second adapter over an existing API, gate on FACT parity, not formatting
  parity** — one eval result read `usage: null` over REST and "partial — derived at read" over MCP,
  "and nothing noticed because each surface looked complete from inside itself."

## Constants inventory (dated ecosystem facts — candidates for the cited-facts surface)

Consumer: max tools **20** · description clip **120 chars** · reconnect attempts **1** · call
timeout **none** (filed open). Bridge: tool refresh **300s** · reconnect delay **3s** · restart cap
**5 per 60s** · port probe **1.0s** · upstream HTTP **connect 30s / read 120s** · SSE timeout
**unbounded** · list_tools readiness wait **10s** · fast-fail **<100ms** (vs a former 5s). Server:
action timeout **120s** (documented as never profiled) · generation **900s** · session idle
**1800s** · sync workers **8** · dispatch margin **15s** · request-log field cap **8 KB** · log
message cap **600 chars**.

Named client bugs: claude-code **#15904** (no clean stdio respawn, closed not-planned),
**#50319** (duplicate tool names → silent `tools/call` hangs).

## The finding about fixtures

Their test fixture server is 37 lines, 3 tools, and **completely well-behaved** — no slowness, no
hangs, no oversized responses, no non-text blocks, no malformed frames, no schema mutation. *Every
adversarial server behaviour in that repo was discovered in production and then pinned with a mock,
never simulated in advance.* That is itself a rule: **the misbehaviours that cost the most were the
ones nobody thought to build a fixture for.**
