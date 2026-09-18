# discodon — the CONSUMER's view, addressed

## Provenance header

| | |
|---|---|
| **Repo** | `/Users/brookstalley/source/discodon` |
| **Branch** | `feat/eval-candidate-kind-seam` |
| **Commit at start of read (`git rev-parse HEAD`)** | `9d54e8f8f6d364f0c4c4c40a36f559ff48c54266` |
| **Commit at end of read** | `77d104432dfcb8348a6d1ef5755b574ca330a8ed` |
| **Tracked files** | 2,961 (`git ls-files | wc -l`) |
| **Read date** | 2026-09-18 |
| **Supersedes** | `discodon-consumer.md` (same directory) — every rule there appears here |

**HEAD moved four times during this read** and that is worth stating rather than papering over.
Another session is actively committing on that branch; `9d54e8f8f` was HEAD when the read opened and
`77d104432` when it closed (via `d8a970639`, `99c8b06cf`, `ce7797b80`). Citations below were
therefore gathered across a five-commit window, so each was re-checked against the far end:

```
git -C /Users/brookstalley/source/discodon diff --stat \
  9d54e8f8f6d364f0c4c4c40a36f559ff48c54266 77d104432dfcb8348a6d1ef5755b574ca330a8ed \
  -- discodon/web/mcp discodon/tools/mcp_bridge_tool.py discodon/tools/mcp_registry.py \
     tools/mcp_bridge discodon/config/sections/mcp.py documentation/MCP_SERVER.md \
     tests/unit/mcp_bridge tests/unit/tools tests/unit/web tests/fixtures tests/integration \
     discodon/core/network.py discodon/web/app.py discodon/operations/timeouts.py \
     discodon/eval/classifier.py discodon/config/sections/eval.py \
     .prawduct/artifacts/mcp-scaling-strategy.md .prawduct/artifacts/mcp-tool-design.md \
     .prawduct/artifacts/mcp-client-tools-design.md .prawduct/artifacts/api-contract.md \
     .prawduct/backlog.md .prawduct/backlog-archive.md .prawduct/learnings-detail.md
```

**Two cited files did change** in the final commit: `discodon/web/mcp/eval/classifier.py` (−31 lines)
and `tests/unit/web/test_mcp_eval_tool.py` (which nothing here cites). The one symbol this document
cites from `classifier.py` — `MALFORMED_SNAPSHOT_ID` — **survives at HEAD**, verified directly, and
the deletion contained neither it nor the `(none recorded)` rendering also referenced. Everything
else this document cites is byte-identical across the whole window.

That near-miss is worth recording, because it is this pass's own rule paying for itself:
`MALFORMED_SNAPSHOT_ID` **moved from line 1196 to 1165**. A citation reading `classifier.py:1196`
would now be silently wrong and still look precise. The symbol anchor survived the edit; the line
number would not have. Quote the opening SHA, and re-resolve any symbol before relying on it.

Every `PROVENANCE:` path below is anchored on a **symbol or a heading**. Line numbers appear only as
parenthetical hints. `.claude/worktrees/` holds other sessions' checkouts and is excluded from every
search and every citation.

## Why this source is different

discodon is the only source in this corpus that is **not** an MCP server. It is three things at once,
and the distinction matters for every rule below:

| Surface | Path | Role |
|---|---|---|
| **The consumer** | `discodon/tools/mcp_bridge_tool.py`, `discodon/tools/mcp_registry.py` | Connects arbitrary third-party MCP servers to an LLM entity's tool loop. This is the view no server author has. |
| **The stdio bridge** | `tools/mcp_bridge/` | A client of discodon's own server AND a server to Claude Code. Every client-behaviour finding lives here. |
| **Its own server** | `discodon/web/mcp/` | Consumed by Claude Code. The tool-facade and result-shaping lessons live here. |

**Read the two consumers as a natural experiment.** They face the same problems and resolve several
of them in *opposite* directions (tool list while disconnected, `structuredContent`, whether the
caller is told a truncation happened). Where they disagree, that disagreement is the finding, and it
is recorded as a `TENSION`.

## How to read a rule

Rules are filed by the layer at which they must **fire**, not by what they are about. Because this
is the consumer side, most rules fire while someone designs a **server**: the rule is what the
server author must do, and the evidence is what this client does to them if they don't.

- **L0 applicability** — whether to build a server at all; what to plumb MCP into.
- **L1 agent-interface design** — naming, granularity, intent-shaped tools, teaching errors, result
  shaping, context budget. Survives MCP itself.
- **L2 protocol semantics** — tools vs resources vs prompts, schemas, capability negotiation, versioning.
- **L3 transport & operations** — stdio/HTTP/SSE, timeouts, concurrency, lifecycle, secrets.
- **L4 client/host integration** — per-client quirks, config, discovery, install UX. Most volatile.

Evidence tiers: `measured` (a number or observed behaviour in this tree) · `measured(third-party)`
(a benchmark or vendor claim this repo cites — the source is named) · `designed-untested` (reasoned
in a design doc, never verified) · `incident` (something broke and this is the fix).

---

# A. Tool surface and schema

**RULE:** Emit an explicit `"type": "object"` at the root of every tool's `inputSchema`, even when the schema has no properties.
FIRE-SITE: You are writing the JSON Schema for a tool's parameters and the root object already has `properties`, so adding `"type"` looks redundant.
LAYER: L2
KIND: constraint
EVIDENCE: measured — the consumer patches it in unconditionally: `if "type" not in input_schema: input_schema = {"type": "object", **input_schema}`. The patch exists because the Anthropic tool-definition API rejects a schema without it, so a server that omits it is unusable through this bridge and every other bridge onto the same API.
PROVENANCE: `discodon/tools/mcp_bridge_tool.py` `McpBridgeTool.tool_definitions`
VOLATILE: none — the requirement is in the receiving API, not in a discodon constant.
TENSION: none.

**RULE:** Keep one server at or under ~20 tools, or ship a server-side filter, because a consumer that caps will drop your overflow without telling anyone.
FIRE-SITE: You are adding the twenty-first tool to a server, or deciding between one fat tool and fifteen thin ones.
LAYER: L1
KIND: constraint
EVIDENCE: measured — `DEFAULT_MAX_TOOLS = 20`, commented "Safety cap: warn and truncate if a server exposes more tools than this." The overflow is dropped by `filtered = filtered[: self._max_tools]` after a single `log.warning("McpBridgeTool[%s]: server exposes %d tools, capping at %d", ...)`. That warning goes to the Python logger. **Nothing on the agent-visible path mentions it**: `describe_state` renders `f"{len(self._remote_tools)} capabilities:"` — the POST-cap count, stated as fact — `tool_definitions` emits only the survivors, and the `refresh` action's own success text is `f"Reconnected. {len(self._remote_tools)} tools available: ..."`. Tools 21+ do not exist to the model, and the model is told a confident number that is not the server's number.
PROVENANCE: `discodon/tools/mcp_bridge_tool.py` `DEFAULT_MAX_TOOLS`, `McpBridgeTool._apply_filter_and_cap`, `McpBridgeTool.describe_state`, `McpBridgeTool.tool_definitions`, `McpBridgeTool._refresh`; per-server override default in `discodon/tools/mcp_registry.py` (`max_tools` defaults to `20` at three sites) and documented in `documentation/TOOLS.md` § MCP Bridge and `config/mcp_servers.yaml`
VOLATILE: **20** is this consumer's number and is operator-overridable per server (`max_tools`, `admin_only=True`). It is not an ecosystem constant — see the TENSION.
TENSION: Directly contradicted as a *number* by other sources in this corpus (Cursor reported at 40, Copilot at 128). The transferable part is not 20; it is that **the cap is silent**, which is the same in all three.

**RULE:** Front-load the first ~120 characters of every tool description; assume everything after that is invisible when an agent chooses.
FIRE-SITE: You are writing a tool description and the important qualifier ("read-only", "requires confirm", "expensive") is in the second sentence.
LAYER: L1
KIND: constraint
EVIDENCE: measured — `if len(tool_desc) > 120: tool_desc = tool_desc[:117] + "..."` when rendering the remote roster into the persona's live-state prompt section.
PROVENANCE: `discodon/tools/mcp_bridge_tool.py` `McpBridgeTool.describe_state`
VOLATILE: **120** / **117** are literals in `describe_state`, unnamed and untested.
TENSION: **This clip is narrower than the old capture implied.** `tool_definitions` passes `tool.description` through UNCLIPPED to the Anthropic tool definition. So the full description does reach the model's tool schema; it is the *prompt-side roster* — the thing the persona reads to decide what it has — that is clipped. Both surfaces exist and only one clips, which is itself the rule: a description has more than one reader in a single consumer.

**RULE:** Ship a non-empty description on every tool; nothing will be inferred from the name.
FIRE-SITE: You are registering a tool whose name you think is self-explanatory.
LAYER: L1
KIND: constraint
EVIDENCE: measured — `"description": tool.description or f"MCP tool: {tool.name}"`. The fallback is a literal prefix, not a generated summary; and in the prompt roster the fallback is the string `"no description"`.
PROVENANCE: `discodon/tools/mcp_bridge_tool.py` `McpBridgeTool.tool_definitions` and `McpBridgeTool.describe_state`
VOLATILE: none.
TENSION: none.

**RULE:** Do not set `additionalProperties: false` on a tool schema you want an intermediary to be able to proxy.
FIRE-SITE: You are tightening a tool schema, or you are designing a proxy/bridge that wants to inject a routing parameter into someone else's schema.
LAYER: L2
KIND: decision-point
EVIDENCE: designed-untested — recorded as a *cost to design for*, not as an incident: "Discodon tool schemas are additionalProperties:false, so injected deployment/confirm params MUST be stripped before forwarding or upstream 422s (bridge stops passing schemas verbatim, starts rewriting them)". Priced in the same sentence as "Medium change (session-pool refactor + hot-path schema rewriting) -> wants a build plan + Critic pass."
PROVENANCE: `.prawduct/backlog.md` item **[MCP-9K3T]** ("MCP bridge: per-call deployment routing"), the "Other costs to design for" paragraph; the closed schemas themselves are at `tools/mcp_bridge/bridge_tools.py` in the two `BRIDGE_LOCAL_TOOLS` schemas (`"additionalProperties": False`)
VOLATILE: none.
TENSION: The old capture tagged this **broke-in-production**. It did not break — the feature that would have hit the 422 has never been built (`status: open · stage: idea`). Corrected to `designed-untested`; the 422 is a prediction from reading the schemas, and it is a sound one.

**RULE:** Do not expect a consumer to honour your read-only/mutating classification — a consumer that discovers your tool set at runtime cannot verify a claim like that, and the safe ones therefore treat every tool as mutating.
FIRE-SITE: You are annotating tools with a read-only hint, or you are arguing that a destructive tool is safe because it is marked as such.
LAYER: L2
KIND: stance
EVIDENCE: measured — refused twice, independently, in this one repo. (1) The eval seam: "The action set is whatever the remote server advertises at connect time, so there is nothing to enumerate and therefore nothing to classify. Every action here actuates under eval — a candidate driving arbitrary remote MCP tools for real is not something an eval run can defend, and a per-server opt-in would be a policy this seam has no way to check." (2) The routing design explicitly rejected classification-based gating: "Avoid the alternative of gating only mutations (would couple the generic proxy to Discodon action semantics)", choosing instead to require `confirm='PROD'` on **every** non-local call.
PROVENANCE: `discodon/tools/mcp_bridge_tool.py` `McpBridgeTool._actuation_unenumerable` (with its class-attribute comment) and `McpBridgeTool.act`; `.prawduct/backlog.md` item **[MCP-9K3T]**, "KEY DESIGN CONSTRAINT" paragraph
VOLATILE: none.
TENSION: **This INVERTS the old capture's rule**, which read "Declare read-only vs mutating per tool, or a gating proxy hardcodes your action names and goes stale." The coupling problem it names is real and is exactly what [MCP-9K3T] refuses; but the remedy discodon reached for is not a per-tool declaration — it is to stop believing declarations and gate uniformly. The old rule is kept below as CONTRADICTED so the reversal is visible.

**RULE:** (CONTRADICTED, retained) Declare read-only vs mutating per tool, or a gating proxy hardcodes your action names and goes stale.
FIRE-SITE: as above.
LAYER: L2
KIND: pattern
EVIDENCE: measured — the tree contains the diagnosis this rule rests on and then declines the prescription.
PROVENANCE: CONTRADICTED — `.prawduct/backlog.md` **[MCP-9K3T]** names the staleness/coupling hazard ("would couple the generic proxy to Discodon action semantics") as a reason **not** to gate on classification; `discodon/tools/mcp_bridge_tool.py` `McpBridgeTool._actuation_unenumerable` states that a per-server opt-in "would be a policy this seam has no way to check." The "fallback: treat unclassified as mutating" half survives and is correct — it is the *only* thing either site does.
VOLATILE: none.
TENSION: Superseded by the rule immediately above.

**RULE:** Namespace your tool names against every other server a host may load — a duplicate name across two servers is a silent dispatch HANG, not an error.
FIRE-SITE: You are choosing a tool name like `search`, `status`, `run` or `help`.
LAYER: L4
KIND: constraint
EVIDENCE: measured(third-party — Anthropic, `anthropics/claude-code#50319`) for the client behaviour; measured (this tree) for the defence. The comment: "Collision check: bridge-local tool names must not shadow upstream tool names (claude-code#50319 — duplicates produce silent dispatch hangs). Runs on every refresh (initial connect + each 5-min refresh + every reconnect) and raises RuntimeError **outside** the refresh broad-except above so a collision fails loudly instead of being logged as a transient refresh warning."
PROVENANCE: `tools/mcp_bridge/bridge.py` `UpstreamState.refresh_tools` (the `bridge_tools.assert_no_collisions` call and its comment); `tools/mcp_bridge/bridge_tools.py` `assert_no_collisions`; pinned by `tests/unit/mcp_bridge/test_bridge_tools.py` (asserts `"50319" in str(exc_info.value)` — the issue number is in the *exception message*, so the diagnosis travels with the failure); documented in `tools/mcp_bridge/README.md`
VOLATILE: **claude-code#50319** — a client bug that may be fixed, after which the hang becomes an error and the defence becomes belt-and-braces.
TENSION: none.

**RULE:** Keep tool parameters flat scalars (`str | int | bool | null`) and pass structured data as JSON strings; then accept both a dict and a JSON string on the way in.
FIRE-SITE: You are about to declare a nested object or array-of-objects parameter.
LAYER: L1
KIND: stance
EVIDENCE: designed-untested — "**Types:** All parameters are `str | None`, `int | None`, or `bool | None`. Complex data passes as JSON strings. This matches Cordyceps' approach and avoids MCP client compatibility issues." The listed anti-pattern is "**Deep parameter nesting** — use flat params with clear names instead." The stated compatibility problem is never named or reproduced anywhere in the tree. The *consumer* half is implemented: `parse_json_param` accepts "a dict ... or a JSON string (the common case)".
PROVENANCE: `.prawduct/artifacts/mcp-scaling-strategy.md` § "3. Parameter Conventions"; `.prawduct/artifacts/mcp-tool-design.md` § "Anti-Patterns"; `discodon/web/mcp/validation.py` `parse_json_param`
VOLATILE: none.
TENSION: **Cross-repo provenance note** — this rule cites *Cordyceps*, another source in this corpus, as its warrant ("matches Cordyceps' approach"). It is therefore NOT independent evidence. If Cordyceps' own capture rests on discodon, the corpus has a citation loop and the underlying compatibility claim is unsourced in both. Check before treating two sources as two measurements.

**RULE:** Accept `"true"`/`"false"` strings for a boolean parameter and REFUSE any other string — and once your schema widens to accept strings for one action's sake, add a validator in front of every coercer, because a lenient coercer's `False` is indistinguishable from omission.
FIRE-SITE: You are widening a parameter's type to accept strings, or you are writing a `coerce_bool`-shaped helper.
LAYER: L1
KIND: diagnostic
EVIDENCE: measured — the reasoning is written out at the validator: "`coerce_bool` answers `False` for every string it does not recognise, so a typo reads as 'not requested' and is indistinguishable from the caller having left the parameter off. That is tolerable while the tool schema types the parameter `bool` and rejects a stray string before the handler sees it; **it stops being tolerable once the schema widens to accept strings for some other action's sake**, which is what happened to `full` when `get_result` gained section selectors." And the empty string is deliberately one meaning only: "The empty string is ACCEPTED, as 'not supplied' ... One wire value must not mean 'omitted' on one action and 'malformed' on another when the two share a parameter name on a single tool." The concrete damage the pair prevents is spelled out at the section parser: "`full='spans'` would render the compact view and report no problem, so an operator would read 'this result has no spans' off a request that was never honoured."
PROVENANCE: `discodon/web/mcp/validation.py` `coerce_bool` and `validate_bool_flag`; `discodon/web/mcp/eval/results.py` `_FULL_TRUE` / `_FULL_FALSE` (and their comment)
VOLATILE: none.
TENSION: Depends on the rule that a truncation must announce itself (§ D) — both exist because a *silently unhonoured request* is the failure mode, not a wrong answer.

---
# D. Response size and truncation — the highest-value category

**RULE:** Default a large read to a truncated render and put the rest behind a NAMED opt-in; make the withheld parts selectable by name rather than all-or-nothing when they differ in size by orders of magnitude.
FIRE-SITE: You are writing a `get_<thing>` tool that returns everything it knows, and the thing has one section an operator actually opens and several that are large.
LAYER: L1
KIND: pattern
EVIDENCE: measured — "Measured on one real result: **249,942 characters** total, of which the turn trace was **74%**, the OTel spans **24%**, and the per-dimension judge reasoning an operator usually opens a result for **under 2%**. All-or-nothing made reading that 2% cost the other 98% — which overflows an MCP client's token budget and **spills the reply to a file, i.e. the detail is technically returned and practically unreadable**."
PROVENANCE: `discodon/web/mcp/eval/results.py` `GET_RESULT_SECTIONS` (the module-level `#:` comment above it) and `_SECTION_LABELS`
VOLATILE: 249,942 / 74% / 24% / <2% are one measurement on one result at one point in time; nothing re-derives them and no command in the tree reproduces them.
TENSION: none.

**RULE:** When you truncate, say how much was dropped AND name the exact call that returns the whole value — and emit that notice once per response, not once per item.
FIRE-SITE: You are appending an ellipsis, or adding a `[truncated]` marker, to a field in a tool result.
LAYER: L1
KIND: pattern
EVIDENCE: measured — the marker is `…(+N chars — <opt_in>)`, and `N` is counted against what was KEPT, not against the limit: "A bare trailing ellipsis reads as the end of the value rather than as a clip, so a reader cannot tell a short value from a shortened one ... The marker therefore states how much was removed and, when the caller supplies one, the exact call that returns the whole value." On the count: "the rstrip removes trailing whitespace when the cut lands mid-gap, so a limit-based count under-reports ... A marker whose own number is short is the same defect as a bare ellipsis, one degree quieter." The per-response form is a separate helper: `"\n⚠ {truncated} of {total} message{plural} truncated at {_DEFAULT_MSG_LIMIT} chars — re-run with `full=true` for complete bodies."`, described as "Loud, consolidated notice ... Names the exact opt-in call so an agent reading clipped output learns the full value exists and how to get it — a *read* affordance, also advertised in the tool schema, not a safety-gate bypass hint."
PROVENANCE: `discodon/web/mcp/formatters.py` `abbreviate` (inline marker; returns a plain string) and `discodon/web/mcp/logs_tool.py` `_truncation_footer` + `_DEFAULT_MSG_LIMIT` (consolidated footer; adapters return `(rendered, was_clipped)`). The two shapes and why both exist are settled in `abbreviate`'s own `Note:` block.
VOLATILE: `abbreviate`'s default `limit=120`; `_DEFAULT_MSG_LIMIT = 600`.
TENSION: none.

**RULE:** Clamp an out-of-range numeric argument to your ceiling rather than refusing it, and say in the response body that you clamped — a silent clamp makes the caller read your timeout message as the operation having failed.
FIRE-SITE: You are validating a caller-supplied `duration`, `limit` or `timeout` against a maximum, and a refusal looks like the principled choice.
LAYER: L1
KIND: pattern
EVIDENCE: measured — two parameters clamp, and **the announcement is on the path the agent reads**, not in a log. `duration` (on `watch.social` / `watch.persona` / `watch.c2`) goes through `_resolve_watch_duration`, which returns `(effective_seconds, clamp_note)`; the note is a parenthetical `" (requested {requested}s, capped at {ceiling}s)"` that `_format_watch_body` renders as an italic banner **above** the body (`f"_{label} {clamp_note.strip()}_\n\n{body}"`). `timeout` (on `watch.send_command`) clamps to `mcp.command_timeout_max_ms` with the same note shape. The reason is written at the site: "Say so when the request was not honoured verbatim — the same rule the capture handlers follow. **A silent clamp is what makes a caller read 'no response within timeout' as the command failing, when in fact it was never given the time asked for.**" On the empty-result path the note is not a footnote but the explanation: "Here the clamp is the explanation, not a footnote: without it, a caller reads this as the command having failed when it was never given the time it asked for." The clamp is also **bidirectional** and announced in both directions: below the floor it returns `1, f" (requested {requested}s, raised to 1s minimum)"`. It is advertised in the parameter help too: "Requests above the cap are clamped and the response notes the clamp."
PROVENANCE: `discodon/web/mcp/watch_tool.py` `_resolve_watch_duration`, `_format_watch_body`, `_handle_send_command`, `_WATCH_DURATION_PARAM_DESC`, `_ACTIONS["send_command"]`; ceilings at `discodon/config/sections/mcp.py` `McpConfig.watch_capture_max_s` (default 120) and `McpConfig.command_timeout_max_ms` (default 30_000); pinned by `tests/unit/web/test_mcp_watch_tool.py` (`test_persona_clamps_duration_with_explicit_note`, `test_c2_clamps_duration_with_explicit_note`, `test_clamps_over_cap_with_note`, `test_clamps_zero_to_minimum`, plus a no-clamp-no-note case)
VOLATILE: `watch_capture_max_s` 120 s and `command_timeout_max_ms` 30,000 ms are operator-set hot config, not constants; `_WATCH_DURATION_DEFAULT = 5`, `_SEND_COMMAND_DEFAULT_MS = 5000`.
TENSION: Another source in this corpus **refuses** an out-of-range value and quotes the ceiling instead. Both are defensible and the disagreement is about who pays: a refusal costs a round-trip the agent spends guessing a smaller number, a clamp costs the risk that the caller never notices. discodon's answer is only sound *because* the note is in the result body — a clamp without the note is strictly worse than a refusal, and the code says so. **Also note the one gap in discodon's own version:** when the caller supplies nothing, the default is itself clamped silently — `return min(_WATCH_DURATION_DEFAULT, ceiling), ""` returns an empty note. Defensible (nobody asked for anything) but it means an operator who lowers the ceiling below 5 s gets shortened captures with no notice at all.

**RULE:** Do not use a bare `token` key for a secret in any tool parameter or tool result — use `access_token` / `refresh_token` / `api_key`, because a consumer's redaction cannot afford to match the bare word.
FIRE-SITE: You are naming a field that will hold a credential, and `token` is the obvious name.
LAYER: L3
KIND: constraint
EVIDENCE: measured — the omission is deliberate and documented as a convention imposed on tool authors: "CONVENTION — bare `token` is NOT in the set because it would catch innocuous telemetry fields like `token_count`, `continuation_token`, `token_id`. MCP tools MUST therefore not use bare `token` as a secret-holding key; use `access_token`, `refresh_token`, or `api_key` instead so redaction catches them automatically. The tool catalog review is the primary safeguard; this helper is defense-in-depth." An unredacted value lands in a **200-entry in-memory ring buffer** and is **broadcast over WebSocket** to any subscriber of the `mcp.requests` channel.
PROVENANCE: `discodon/web/mcp/request_log.py` module docstring, `_REDACT_KEY_SUBSTRINGS`, `_MAX_ENTRIES` (200), `_MAX_DETAIL_BYTES` (8192), `McpRequestLog.add` (the `self._broadcast_fn("mcp.requests", entry.to_dict())` call) and `McpRequestLog.set_broadcast`
VOLATILE: the contents of `_REDACT_KEY_SUBSTRINGS` (12 substrings at this commit); `_MAX_ENTRIES = 200`; `_MAX_DETAIL_BYTES = 8192`.
TENSION: The rule is a **consumer imposing a naming convention on servers to compensate for a lossy redaction heuristic**. That is the honest shape of it: the redaction is substring-based and deliberately permissive ("we'd rather over-redact (e.g. `password_hash`) than under-redact"), and bare `token` is the one place the heuristic had to lose. A server author has no way to discover this convention except by reading this file.

**RULE:** Return an id in full wherever the next call will consume it, and abbreviate only where an id labels a row in a list being scanned.
FIRE-SITE: You are rendering a UUID into a tool result and an 8-character prefix looks tidier.
LAYER: L1
KIND: pattern
EVIDENCE: incident — "`classifier_snapshot_create` returns the snapshot's whole id, because `classifier_snapshot_update` / `_delete` match `snapshot_id` exactly and refuse an abbreviated one (`MALFORMED_SNAPSHOT_ID`) — same reason `list_runs` and `campaign_list` print theirs in full. The result tables still abbreviate: there an id labels a row in a list being scanned, not a value being copied into the next call — recover the full one from `classifier_snapshots`." The self-own behind it is that the truncated prefixes callers pasted had been copied off *the server's own abbreviated display*.
PROVENANCE: `documentation/MCP_SERVER.md` § `eval` — Eval System (the "Out of scope / classifier" paragraph); `discodon/web/mcp/formatters.py` `truncate_id` (the display helper, default `length=8`); the refusal code at `discodon/web/mcp/eval/classifier.py` (`MALFORMED_SNAPSHOT_ID`, commented "ids are matched exactly, so a prefix matches")
VOLATILE: `truncate_id`'s default length of 8.
TENSION: Depends on the id-canonicalization rule in § C — they are the two halves of one defect, and the server caused its own bug reports by displaying something un-pasteable.

**RULE:** When a result is the only copy that will ever exist — generated and not persisted — render it verbatim with no truncation and no opt-in to pass.
FIRE-SITE: You are applying your standard truncation policy uniformly, including to a tool whose output is not stored anywhere.
LAYER: L1
KIND: decision-point
EVIDENCE: measured — "**`classifier_snapshot_generate` renders its cases verbatim by default, with no `full=` to pass** — the opposite call from `classifier_snapshots`, and the difference is persistence: generated cases are not saved, so the reply is the only copy that will ever exist and there is no id to look one up by afterwards. A truncated case could not be fed to `classifier_snapshot_create`, which is the action's only workflow; ask for a smaller `count` if the output is longer than you want to read."
PROVENANCE: `documentation/MCP_SERVER.md` § `eval` — Eval System (the "Out of scope / classifier" paragraph)
VOLATILE: none.
TENSION: Directly opposes the default-to-truncated rule at the top of this section. The discriminator is **persistence**, not size — which is the useful part: size decides *how much* to withhold, persistence decides *whether you may withhold at all*.

---

# F. Capability caching and refresh — the client-behaviour findings

**RULE:** Treat a published parameter schema as FROZEN. To add a required parameter, publish a new tool name — do not change the existing tool's schema and expect a notification to fix it.
FIRE-SITE: You are adding a required parameter to a shipped tool, and you have already implemented `tools/list_changed` correctly so you believe you are covered.
LAYER: L4
KIND: constraint
EVIDENCE: incident, measured **twice**. This repo built the entire correct server half — full-definition fingerprinting, `list_changed` on any delta, force-notify on reconnect — and then wrote the outcome into the code that reports it: "The bridge's half of the schema problem is done ... **The CLIENT half is not ours to fix** — Claude Code keeps the parameter schema it loaded for an already-registered tool, so a parameter that exists only on the new profile is unreachable through the bridge until the MCP server is reloaded. That was measured twice: once during ER-1 close-out (the local `eval` action list was correct while its schema still carried prod's parameters, so the required `confirm` could not be passed and **the operator nuke had to be run outside MCP**), and again at the v2.3.15 eval acceptance, where **only a bridge restart cleared it**." The two measurements in their original records: (1) 2026-05-15 — "Claude Code's cached tool *schema* for `mcp__discodon__eval` retained the prod parameter list (had `reference`, `description`, etc. — no `confirm`) ... so the operator nuke had to be run via `pipenv run python` instead of MCP. The bridge advertises 'no Claude Code restart needed' for profile switch, but only the action list re-syncs — parameter schemas don't." (2) 2026-07-26 / v2.3.15 — the `eval` tool gained a `campaign_id` param and "Claude Code kept validating calls against the stale schema and rejected the new parameter (**'Additional properties are not allowed'**)". The final remedy is a `restart_required: true` field — **telling the operator, not a mechanism.**
PROVENANCE: `tools/mcp_bridge/bridge_tools.py` `_schema_change_report` (its docstring is the finding, in full); `.prawduct/backlog.md` item **[MCP-CNY8]** (orig #1186, 2026-05-15) and its "Cross-reference (2026-07-26)" paragraph; `.prawduct/change-log-archive/2026-07.md` § "2026-07-26: MCP bridge — notify Claude Code on tool SCHEMA changes, not just name changes" (scope=`mcp-bridge-notify-on-schema-change`, release v2.3.16); operator-facing statement at `documentation/MCP_SERVER.md` § `bridge_set_environment` — Switch Active Profile, the paragraph headed "**Read `tool_schemas_changed` before assuming the switch is complete.**"
VOLATILE: This is a **Claude Code** behaviour at the versions observed (around v2.3.15, mid-2026) and **[MCP-CNY8]** is still `status: open`. If the client starts adopting in-place schema changes, the whole rule collapses to "notify and you are fine."
TENSION: **This is the strongest evidence in the corpus about what a server may safely refactor**, and it is in direct tension with every "just emit `list_changed`" reading of the spec. Note the phrase "did not help" in the old capture is a **paraphrase, not a quote** — the tree's own words are "notifying / re-publishing alone doesn't refresh the client in place" and "this change removes the *bridge-side silence*, not the client-side adoption gap." Same substance, and the honesty of the original is worth preserving: the server half was necessary, just not sufficient.

**RULE:** Send `tools/list_changed` on ANY change to a tool definition — name, description OR `inputSchema` — not merely when the set of names changes.
FIRE-SITE: You are writing the "did the tool list change?" comparison in a proxy or a dynamic server, and comparing names is the obvious cheap check.
LAYER: L2
KIND: constraint
EVIDENCE: incident — the fingerprint is `{name, description, inputSchema}` over a name-sorted list, serialised with `sort_keys=True`. The comment at the notify site carries the incident: "Comparing names only left Claude Code on a stale schema when a backend deploy changed a tool's `inputSchema` without renaming it (e.g. the eval tool gaining a `campaign_id` param): the periodic refresh saw equal names and suppressed the notification, so the client kept validating calls against the old schema and rejected the new parameter." The regression test was red-verified: "(verified: fails on the names-only logic, passes on the fix)".
PROVENANCE: `tools/mcp_bridge/bridge.py` `UpstreamState._tools_signature` and `UpstreamState.refresh_tools`; also `UpstreamState.tool_schemas` for the narrower parameter-schema-only comparison ("The unit a caller cares about across a profile switch is the PARAMETER schema, not the tool set"); pinned by `tests/unit/mcp_bridge/test_bridge.py::test_refresh_notifies_on_schema_change` ("Regression: comparing only tool names suppressed `tools/list_changed`")
VOLATILE: none.
TENSION: Necessary but not sufficient — see the frozen-schema rule above. Emitting this correctly is what made the client-side gap *visible*, which is its real value.

**RULE:** Do not suppress a notification you believe is redundant, and do not send one when nothing changed — pin both directions.
FIRE-SITE: You are adding a "nothing changed, skip the notify" short-circuit, or a "always notify, it's cheap" one.
LAYER: L2
KIND: constraint
EVIDENCE: measured — one expression carries both: `if (force_notify or self._tools_signature(new_tools) != old_signature) and self._on_tools_changed`. `force_notify` exists specifically so a reconnect notifies even a byte-identical list: "Send `tools/list_changed` even if the tool set is identical. Used after reconnect so Claude Code knows the server is back."
PROVENANCE: `tools/mcp_bridge/bridge.py` `UpstreamState.refresh_tools` (the `force_notify` parameter and the notify condition)
VOLATILE: none.
TENSION: none.

**RULE:** Answer `tools/list` immediately even when your backend is not ready — serve a cached or empty list, cap any wait, and push `list_changed` when you do come up.
FIRE-SITE: You are writing a proxy's `list_tools` handler and it is tempting to await upstream readiness.
LAYER: L4
KIND: pattern
EVIDENCE: measured — the handler probes the upstream port first; if nothing is listening it returns the cached list immediately, and if the port is open it waits `asyncio.wait_for(upstream._ready.wait(), timeout=10.0)` and on `TimeoutError` logs "Upstream not ready after 10s — returning cached tool list" and serves the cache anyway. The general lesson is recorded separately: "When building stdio proxy bridges, Claude Code calls `list_tools` during initialization. If upstream hasn't connected yet, the list is empty. Start immediately and send `notifications/tools/list_changed` once upstream connects."
PROVENANCE: `tools/mcp_bridge/bridge.py` `main.list_tools` (the nested `@server.list_tools()` handler and its docstring); `.prawduct/learnings-detail.md` entry "**Send `tools/list_changed` when upstream tools change.**"
VOLATILE: the **10.0 s** readiness wait (a literal in `list_tools`, unnamed); the 1 s port probe in `_probe_port`.
TENSION: none.

**RULE:** Expect a consumer to keep serving your LAST-KNOWN tool list while you are down — so a tool you remove stays visible, and callable, until you come back.
FIRE-SITE: You are removing or renaming a tool and reasoning about what happens during the deploy window.
LAYER: L4
KIND: constraint
EVIDENCE: measured — and **the two consumers in this one repo do the opposite thing**, which is the finding. The stdio bridge serves the cache: "if not yet connected, probes the upstream port. If nothing is listening, serves the cached tool list (empty on first start, **last-known after a restart**)." The entity-facing consumer serves nothing: `tool_definitions` opens with `if not self._connected: return []`, and `stop()` does `self._remote_tools = []`.
PROVENANCE: `tools/mcp_bridge/bridge.py` `main.list_tools`; `discodon/tools/mcp_bridge_tool.py` `McpBridgeTool.tool_definitions` and `McpBridgeTool.stop`
VOLATILE: none.
TENSION: A server author cannot assume either behaviour. The transferable rule is that **both are in the wild**, so a removal must be safe under "still advertised and called" AND a remote outage must be safe under "silently has no tools this turn."

**RULE:** Provide a client-invocable re-discovery action; do not assume anything polls you.
FIRE-SITE: You are relying on a consumer's periodic refresh to pick up a change.
LAYER: L1
KIND: pattern
EVIDENCE: measured — the consumer synthesises one unconditionally: it appends a `{catalog_key}__refresh` tool definition with the description "Reconnect to the MCP server and refresh the list of available tools", and `act` special-cases `"refresh"` before anything else. On the bridge side the equivalents are the bridge-local `bridge_health` and `bridge_set_environment` tools, which "run inside the bridge process (not proxied), so they keep working with upstream unreachable."
PROVENANCE: `discodon/tools/mcp_bridge_tool.py` `McpBridgeTool.tool_definitions` (the appended refresh action) and `McpBridgeTool.act`; `McpBridgeTool._refresh`; `tools/mcp_bridge/bridge_tools.py` `BRIDGE_LOCAL_TOOLS`
VOLATILE: the periodic interval it compensates for — `TOOL_REFRESH_INTERVAL = 300`.
TENSION: none.

**RULE:** When you report whether something changed, make "I could not tell" a THIRD value distinct from "unchanged" — and say in the message what the reader should do under the unknown.
FIRE-SITE: You are returning a boolean or a list for "did X change?" and a timeout is one of the paths into it.
LAYER: L4
KIND: diagnostic
EVIDENCE: measured — `_schema_change_report` returns `"tool_schemas_changed": None` when no post-switch refresh was observed, with the text: "The new profile's tool list had not been published within {n}s, so whether any parameter schema changed is **UNKNOWN — not 'unchanged'**. If a call is refused for a parameter the action's help documents, reload the MCP server rather than assuming the argument is wrong." Restated for the operator: "`null` means the new tool list had not arrived within the wait — unknown, not unchanged."
PROVENANCE: `tools/mcp_bridge/bridge_tools.py` `_schema_change_report` (the `if not refreshed` branch); `documentation/MCP_SERVER.md` § `bridge_set_environment` — Switch Active Profile
VOLATILE: `_TOOL_REFRESH_TIMEOUT_S`, interpolated into the message.
TENSION: none. This is a NEW rule the previous pass missed entirely.

**RULE:** Emit an advisory ONLY when the condition it names actually holds — a restart hint on every operation is one the operator learns to skip.
FIRE-SITE: You are adding a caveat to a tool's response and it is cheaper to emit it unconditionally.
LAYER: L1
KIND: stance
EVIDENCE: measured — "So this names the condition rather than claiming to have fixed it. **Reporting it only when a schema ACTUALLY changed matters as much as reporting it at all**: a restart hint on every switch is one an operator learns to skip, and most switches do not change a schema."
PROVENANCE: `tools/mcp_bridge/bridge_tools.py` `_schema_change_report` (docstring, second paragraph)
VOLATILE: none.
TENSION: In tension with fail-loud instincts, and resolved by precision rather than by volume. Generalises well past MCP.

---
# L0. Applicability — what a consumer can and cannot do with you at all

These four rules fire *before* anyone writes a tool. They are the part of the consumer's view that no
server author can see, and the previous pass captured none of them.

**RULE:** Accept that a consumer which discovers your tool set at runtime cannot put your tools in a dry-run, eval or simulation mode — if you want to be exercisable under test, the affordance has to be yours, not theirs.
FIRE-SITE: You are asking why a consumer refuses to include your server in its offline/replay/eval path, or you are designing a server you expect to be testable inside someone else's harness.
LAYER: L0
KIND: constraint
EVIDENCE: measured — the bridge declares itself unenumerable and therefore always-actuating, and the comment says exactly why: "The action set is whatever the remote server advertises at connect time, so there is nothing to enumerate and therefore nothing to classify. Every action here actuates under eval — a candidate driving arbitrary remote MCP tools for real is not something an eval run can defend, and a per-server opt-in would be a policy this seam has no way to check." The connection itself is excluded from measured runs: `_eval_startup = EvalStartup.UNSTARTED`, because "this repo cannot say what the far side does, so a measured cell does not open the connection."
PROVENANCE: `discodon/tools/mcp_bridge_tool.py` `McpBridgeTool._actuation_unenumerable`, `McpBridgeTool._eval_startup`, and `McpBridgeTool.act` (which forfeits the base dispatcher's mute and re-applies it off the same declaration)
VOLATILE: none.
TENSION: Depends on the read-only/mutating inversion in § A — same root cause, different consequence.

**RULE:** Expect a consumer to attribute cost to "MCP" as a whole and not to your server — if per-server spend matters to your users, you must report it in-band.
FIRE-SITE: You are pricing a server, or explaining a usage bill, and assuming the host can tell your calls apart from another server's.
LAYER: L0
KIND: constraint
EVIDENCE: measured — the metering declaration refuses to be more precise than it can be: "The bridge reaches an unbounded set of remote MCP servers, so one declaration cannot name which was called. `"mcp"` is the honest ceiling: it says the spend left this process and refuses to attribute it more precisely than is true. Nothing here reports a weighted unit, and nothing should — a per-server identity would have to come from the bridge at call time, not from a class attribute."
PROVENANCE: `discodon/tools/mcp_bridge_tool.py` `McpBridgeTool.metered_provider`
VOLATILE: none.
TENSION: none.

**RULE:** Assume one bad server cannot be allowed to take the host down, and therefore that your startup failure will be absorbed rather than surfaced — your connection error string is the entire diagnostic surface anyone will ever see.
FIRE-SITE: You are deciding how much detail to put in a connect-time exception message.
LAYER: L0
KIND: constraint
EVIDENCE: measured — the design intent is in the module docstring: "The `Client(...)` constructor and `__aenter__` can both raise. `McpBridgeTool.start` catches those at the connection boundary and stores the failure on `self._connection_error` rather than re-raising — **a single bad MCP server cannot take an entity down at start.**" The stored string is then the whole surface: `describe_state` renders `f"({self._connection_error or 'not connected'})"` into the persona's prompt, and every failed `act` returns `f"MCP server '{self.name}' is not connected: {self._connection_error or 'unknown error'}"`.
PROVENANCE: `discodon/tools/mcp_bridge_tool.py` module docstring; `McpBridgeTool.start` (both broad-except arms), `McpBridgeTool.describe_state`, `McpBridgeTool.act`
VOLATILE: none.
TENSION: none.

**RULE:** Expect a consumer to record you as `unreachable` on a failed probe and to carry that verdict forward, rather than retrying you.
FIRE-SITE: You are reasoning about what happens to your server's registration after one bad deploy window.
LAYER: L0
KIND: constraint
EVIDENCE: measured — on the failure arm, `start` fires the registry callback with `capabilities=[], verification_status="unreachable"`; on success it fires the same callback with the discovered capability list. The write itself is best-effort and swallowed at debug level, so a failure to record the failure is invisible.
PROVENANCE: `discodon/tools/mcp_bridge_tool.py` `McpBridgeTool.start` (the `verification_status="unreachable"` branch) and the `registry_callback` contract in `McpBridgeTool.__init__`'s docstring; the persisted side is `discodon/tools/mcp_registry.py` `save_registry_entry`
VOLATILE: none.
TENSION: See § H — whether an `unreachable` entry is actually SKIPPED on later boots, or merely labelled, is resolved there.

---
# L0/L2 addenda — decisions taken before the first tool was written

**RULE:** Expect to be modelled as ONE unit of attachment per server, not per tool — so the tools you ship together are the tools a user gets together, and a user who wants one of them gets all of them.
FIRE-SITE: You are deciding whether two loosely-related capabilities belong on one server or two.
LAYER: L2
KIND: decision-point
EVIDENCE: designed-untested — "We map one McpBridgeTool instance = one MCP server connection, which returns all that server's tools via `tool_definitions()`. **Rationale:** ... One connection per server, not per tool — **MCP sessions are stateful**. Simpler config: attach `"github"`, get all GitHub tools."
PROVENANCE: `.prawduct/artifacts/mcp-client-tools-design.md` § "One McpBridgeTool Per MCP Server (Not Per Remote Tool)"; implemented as described (`McpBridgeTool.__init__` docstring: "One instance = one MCP server connection")
VOLATILE: none.
TENSION: Interacts with the ~20-tool cap in § A: because attachment is per server, a server's tool count is a property of the whole attachment and cannot be paid down by the user selecting a subset — except through the whitelist below.

**RULE:** Assume an administrator will whitelist a subset of your tools as a SECURITY control, not only as a size control — so group tools so that a coherent safe subset exists.
FIRE-SITE: You are mixing read and destructive tools on one server, or naming tools so a whitelist has to be enumerated rather than reasoned about.
LAYER: L2
KIND: constraint
EVIDENCE: designed-untested — "**Tool filtering:** Admins can whitelist specific MCP tools even when the server exposes more. Prevents personas from discovering sensitive actions on shared servers." Implemented as an exact-name set: `_parse_filter` splits on commas and `_apply_filter_and_cap` keeps `[t for t in tools if t.name in self._tool_filter]` — so the whitelist is by literal name, with no pattern support, and a renamed tool silently drops out of an existing whitelist.
PROVENANCE: `.prawduct/artifacts/mcp-client-tools-design.md` § "7. Security" ("Tool filtering" paragraph); `discodon/tools/mcp_bridge_tool.py` `_parse_filter` and `McpBridgeTool._apply_filter_and_cap`
VOLATILE: none.
TENSION: Renaming a tool is therefore *not* a safe refactor for any deployed whitelist — it fails closed (the tool disappears) rather than open, which is the right direction but is silent: the filter logs only `log.info` and only when something was skipped.

**RULE:** Expect your credential to be handled as an opaque admin-only secret that a headless process holds for the whole session — one field, encrypted at rest, forwarded as a bearer on every call.
FIRE-SITE: You are designing how a user supplies and rotates your server's credential.
LAYER: L3
KIND: constraint
EVIDENCE: measured — the consumer's only credential path is a single bearer token forwarded to `Client(auth=...)`: "auth_token: Optional bearer token forwarded to fastmcp's `Client(auth=...)`", declared as a `field_type="secret"`, `admin_only=True` config field, with the design stating "**Auth tokens:** Stored encrypted ... `admin_only` fields. Transmitted over HTTPS only." There is no refresh step, no rotation hook, and no per-call credential seam anywhere on the consumer side.
PROVENANCE: `discodon/tools/mcp_bridge_tool.py` `McpBridgeTool.__init__` (the `auth_token` arg) and `McpBridgeTool.config_schema` (the `auth_token` `ToolConfigField`); `.prawduct/artifacts/mcp-client-tools-design.md` § "7. Security" ("Auth tokens" paragraph) and § "R4: Authentication"
VOLATILE: none.
TENSION: A credential that expires mid-session has nowhere to be refreshed here — `auth_token` is captured in `__init__` and `update_config` explicitly excludes it ("Transport-level fields (`server_url`, `server_command`, `auth_token`) require a stop / start cycle to take effect"), so an expiring token costs a full teardown. The OAuth prohibition that the old capture bundled into this rule is filed on its own in § G, where its provenance problem is recorded.

**RULE:** Do not expect a consumer to push data to your tools or to subscribe to them — a tool surface is pull-only at the consumer.
FIRE-SITE: You are designing a tool you expect to be able to notify its caller between invocations.
LAYER: L2
KIND: constraint
EVIDENCE: designed-untested — "`ToolCapability.ACT` only — MCP tools don't push perceptions (the MCP spec has no subscription/notification mechanism for tools)." Implemented: `capabilities` returns `[ToolCapability.ACT]` and `perceive` returns `[]` with the docstring "No perceptions — MCP servers are pull-only via `act`."
PROVENANCE: `.prawduct/artifacts/mcp-client-tools-design.md` § "No Changes to Tool Base Class or PersonaComponent"; `discodon/tools/mcp_bridge_tool.py` `McpBridgeTool.capabilities` and `McpBridgeTool.perceive`
VOLATILE: none.
TENSION: The parenthetical warrant is **overstated**: MCP does have `notifications/tools/list_changed` (which this very repo both sends and consumes) and resource subscriptions. What is true is narrower — there is no mechanism for a *tool* to push a data payload to a client between calls, and this consumer has no seam for one. Carry the narrow claim, not the doc's wording. Logged as drift below.

---
# B. The fat-tool / action-dispatch facade — five scars, not four

This is the pattern where one registered tool takes an `action` parameter and dispatches to N
handlers. Everything here is discodon's own server, so these rules fire on a server author — but the
consumer's interest is direct: a facade is what a server ships **instead of** twenty tools, so these
are the failure modes you buy when you dodge the cap in § A.

**RULE:** Refuse a parameter the dispatched action does not declare; never accept it and drop it.
FIRE-SITE: You are writing an action-dispatch facade whose one registered signature is the union of every action's parameters, and unrecognised arguments land in `**kwargs`.
LAYER: L1
KIND: constraint
EVIDENCE: incident — "It exists because the union signature made any action accept any sibling's filter and drop it: `list_runs` given a `campaign_id` returned every run in the universe, and an operator-facing tip once advertised a `rubric_dim` filter no surface accepts. **A filter taken and not applied is the same confident-wrong answer as a malformed id reported as an empty result.**" The mechanism's own docstring states the shape: "Every MCP tool registers ONE function whose signature is the union of every action's parameters, and forwards all of them to whichever handler is dispatched — where an unrecognised one lands in `**kwargs` and is dropped."
PROVENANCE: `discodon/web/mcp/dispatch.py` `_reject_undeclared_params` (called from `dispatch_action` before the handler runs); the incident and the quote at `.prawduct/artifacts/mcp-tool-design.md` § "The parameter contract, and why it binds"; operator-facing restatement at `documentation/MCP_SERVER.md` § "Available Tools"; pinned by `tests/unit/web/test_mcp_dispatch.py` `TestUndeclaredParamRefusal` and `tests/unit/web/test_mcp_facade_schema_contract.py::TestUndeclaredParamsAreRefused::test_a_sibling_actions_filter_is_refused_rather_than_ignored`
VOLATILE: `_UNIVERSALLY_ACCEPTED_PARAMS = frozenset({"action", "action_name"})` — the exemption set.
TENSION: **The rule is unimplementable without an exemption clause**, which the old capture omitted: a facade with a `help` action must universally accept `action` and `action_name`, justified as "a tool that declares it per-action would be declaring the same row 60 times." And the refusal keys on `value is not None`, not on presence — "A param whose value is `None` was not supplied by the caller — the tool signature defaults it — so it is never an error." That is *why* the all-defaults-`None` rule below exists: **these are one mechanism, not two rules that happen to co-occur.**

**RULE:** Pin all THREE views of "what does this action take" against each other — the compiled schema, the declared metadata, and what the handler actually reads — and pin the two extra copies nobody thinks of: the WIRE schema a client validates against, and the facade's hand-written forward list.
FIRE-SITE: You have just written a facade and are deciding what to test about its parameters.
LAYER: L1
KIND: diagnostic
EVIDENCE: measured — each direction is a derived scan over all 14 facades, not a spot check. "There are three views of 'what params does this action take' — the facade's compiled schema, the action metadata's declared `params`, and what the handler actually reads — and the tool is only honest when all three agree." The two extra copies: the compiled `tool.parameters` is not what a client enforces — "it validates against the `inputSchema` of the MCP `Tool` the server serialises for `tools/list`, and that is one more transformation away" — and the wire test also asserts `additionalProperties is False`; separately the forward-list scan catches "the one drift none of the tests above can see: the schema publishes it, the action declares it, the handler reads it — and it arrives as `None` on every call, because the facade never passed it." The forwarding scan also catches a copy-paste that a name-set comparison cannot: a keyword forwarded from a *different* signature param (`persona_overrides=tool_config_overrides`).
PROVENANCE: `tests/unit/web/test_mcp_facade_schema_contract.py` — module docstring plus `test_declared_action_params_are_reachable`, `test_every_param_a_handler_reads_is_declared`, `test_the_schema_advertises_no_param_without_an_action`, `test_every_facade_param_is_on_the_wire_schema`, `test_every_facade_param_is_forwarded_to_the_dispatcher` (helper `_dispatch_forwards`); contract stated at `.prawduct/artifacts/mcp-tool-design.md` § "The parameter contract, and why it binds"
VOLATILE: **The "six schema params no action declared" is historical and NOT reproducible.** The docstring names exactly six (`entity`'s `include_goals` / `include_wisdom` / `include_todos` / `include_notes` / `update_entity_id`, and `prompt_graph`'s `version_number`); all six were deleted rather than declared, "none having ever had a reader." `test_the_schema_advertises_no_param_without_an_action` now asserts the orphan set is **empty**, so nothing in the tree produces 6 today — the number lives only in that docstring. Verified gone: `for p in include_goals include_wisdom include_todos include_notes update_entity_id version_number; do grep -rn "$p" discodon/web/mcp/ | wc -l; done` → `0 0 0 0 0 2`, and both `version_number` hits are attribute reads (`version.version_number`), not facade params.
TENSION: The old capture said "both directions" and named three failure classes; the tree pins **five** directions. `_dispatch_forwards` also documents its own blind spot honestly — a `**mapping` splat "reports every signature param as forwarded rather than none of them" — so "pin it mechanically" must carry that the mechanism is an AST scan with a known escape hatch.

**RULE:** Default every facade parameter to `null` — no exceptions — and never take a default from `kwargs.get(name, default)`; key the default on the VALUE instead.
FIRE-SITE: You are giving a facade parameter a sensible default like `limit: int = 50`, or writing `kwargs.get("limit", 50)` in a handler.
LAYER: L1
KIND: constraint
EVIDENCE: measured (AST/signature scans over all 14 facades) on two named incidents. "**Every facade param defaults to `None` — no exceptions.** ... This is a hard constraint, not a style note ... A non-`None` default is supplied on every call, so a single `limit: int = 50` makes every action of that tool refuse every request. (This guidance previously read 'sensible defaults for optional params', which is now the way to break a tool.)" The corollary incident: "`classifier_snapshot_create` advertised `source_tool` and `classification_rationale` as optional and, on both, handed `None` to a `ClassifierSnapshot` field typed `str`, so omitting either returned a raw pydantic `string_type` refusal. **Two of its three documented optionals were mandatory in fact**, and its unit tests never saw it because a direct Python call to the handler genuinely omits the key."
PROVENANCE: `tests/unit/web/test_mcp_facade_schema_contract.py` `test_every_facade_param_defaults_to_none` and `test_no_handler_takes_its_default_from_a_kwargs_get` (helper `_kwargs_get_defaults`); `.prawduct/artifacts/mcp-tool-design.md` § "Consistent Parameter Patterns"; worked instance at `discodon/web/mcp/eval_tool.py`, the comment above `min_absolute_change` / `min_relative_change`; the named substitutes are `coerce_str` / `coerce_bool` / `parse_int` / `parse_float` in `discodon/web/mcp/validation.py`
VOLATILE: none.
TENSION: Three things the old phrasing lost, all of them the reason this is a test and not a convention. (1) **The rule exists because the repo's own prior guidance said the opposite** — "Enforced here rather than remembered, because the repo's own MCP tool-design guidance used to advise the opposite." (2) The substitutes are named, not left to the reader: those four helpers "all key on the VALUE, so they land the documented default for an omitted param and for an explicit null alike" — a rule that forbids `kwargs.get(name, default)` without naming the replacement is half a rule. (3) **The defect is structurally invisible to handler-level tests**, because a direct Python call genuinely omits the key; it exists only on the dispatch path. The only two offenders in the repo were `eval`'s `min_absolute_change` / `min_relative_change`, and they were the reason the refusal above "could not ship until they moved their `0.0` floor into the handler."

**RULE:** Make the dispatcher's own registry the single source for `action='help'` — and pin the SCHEMA/REGISTRY agreement, because that is what makes help authoritative; do not merely pin the help text.
FIRE-SITE: You are documenting a facade's per-action parameters, or writing a help action.
LAYER: L1
KIND: pattern
EVIDENCE: designed-untested for the authority claim; measured for the description single-sourcing. "Every tool registers one function whose schema is the union of all its actions' parameters, **so the schema alone cannot tell you which action accepts which** — passing a sibling action's filter used to be accepted and silently dropped, and the answer came back looking complete (`list_runs` given a `campaign_id` returned every run in the universe). ... `action='help'` is the authoritative per-action parameter list." `format_action_help(tool_name, _ACTIONS, action_name)` reads the identical mapping the dispatcher validates against, so help and refusal cannot disagree — but **by construction, not by assertion**: no test asserts the co-sourcing. What is tested is narrower: that an action's *description* matches the canonical `CommandDeclaration.description` rather than a hand-maintained duplicate, for 6 mapped `prompt` actions and 14 mapped `system` actions, with `test_unmapped_action_keeps_handwritten_description` recording that the migration is "opt-in, not all-or-nothing."
PROVENANCE: `documentation/MCP_SERVER.md` § "Available Tools" (the authority claim and the union argument); generator at `discodon/web/mcp/formatters.py` `format_action_help`, driven by each tool's `_ACTIONS` dict — the same dict `dispatch_action` reads; description layer at `discodon/web/mcp/declaration_help.py` `apply_declaration_descriptions` + `get_static_command_registry`, tested in `tests/unit/web/test_mcp_help_from_declarations.py`
VOLATILE: the 6/14 mapped-action counts, which move as the opt-in migration proceeds.
TENSION: The honest form is one step back from the old capture's: the union schema is not a per-action contract, so make the registry the single source and derive help from it — **and it is the schema/registry agreement (the rule above) that makes help authoritative**, which is the part that is tested. Nothing asserts that an agent reading the schema and an agent reading help reach the same answer.

**RULE:** When one registry serves both discovery and the parameter contract, hide an action with a FLAG — never by omitting it — because absence from that registry means "accepts no parameters" and makes the action uncallable.
FIRE-SITE: You are keeping a diagnostic action out of the help listing.
LAYER: L1
KIND: constraint
EVIDENCE: designed-untested (nothing asserts a hidden action is still dispatchable) — "`hidden` keeps a diagnostic action out of the listing without keeping it out of the registry. **The distinction is load-bearing**: `dispatch_action` derives a call's accepted parameters from this same metadata, so an action that is merely unlisted still needs its entry — one that is absent from it accepts no parameters at all and cannot be called. Named help (`action_name=`) still resolves a hidden action, since a caller who knows the name has already discovered it."
PROVENANCE: `discodon/web/mcp/formatters.py` `format_action_help` (the `hidden` comment)
VOLATILE: none.
TENSION: The generalisation is worth more than the instance: **the moment a documentation registry becomes an enforcement registry, "leave it out of the docs" silently becomes "revoke it."** This rule is entirely absent from the old capture and is unguarded in the tree.

**RULE:** Split a facade on whether an agent would use its actions in ONE workflow — never on parameter or action count — and write the reassessment thresholds as something someone actually runs.
FIRE-SITE: You are deciding whether a tool has grown too big, and reaching for a count.
LAYER: L1
KIND: decision-point
EVIDENCE: measured(third-party — the **Cordyceps** project, cited by this repo and not measured here): "The cordyceps project validated this empirically: consolidating 12 tools to 7 reduced knowledge base tokens by 49%." And: "The Cordyceps project ran 30+ actions / 40+ params on single tools (`rhino_render`) without issues. **Parameter count is not the splitting criterion — cognitive coherence is.**" Stated reassessment triggers: "If any single tool exceeds 50 actions" and "If help output for a single tool exceeds 4000 tokens".
PROVENANCE: `.prawduct/artifacts/mcp-scaling-strategy.md` § "1. Group by Semantic Domain" ("When to split" / "When NOT to split") and § "When to reassess this strategy"; `.prawduct/artifacts/mcp-tool-design.md` § "Problem" and § "Reference"
VOLATILE: 12→7 tools / 49% is third-party and not reproducible from this tree. The 50-action and 4000-token triggers are stated policy.
TENSION: **The 50-action trigger is tripped today and has gone unevaluated.** `eval` has 62 registered actions (`grep -c "@eval_action(" discodon/web/mcp/eval/*.py` summed → 62) against a strategy table that still records 46. Only the splitting criterion is safe to carry as validated; the reassessment-trigger half is a rule this repo states and does not run, which is itself the lesson. Also **cross-repo**: like the flat-params rule in § A, the warrant is Cordyceps, so treat the two as one source, not two.

---

# C. Results, errors and content blocks

**RULE:** Pick ONE channel for "this call failed" and make every layer read it — and if you pick the text, the machine-readable code in the text is not optional.
FIRE-SITE: You are deciding whether a handler's expected failure should raise, set `isError`, or return a string.
LAYER: L2
KIND: decision-point
EVIDENCE: measured — and this repo is a **counterexample** to the naive rule. `grep -rn "isError" discodon/` returns **zero hits**: discodon's MCP server never sets `isError` on anything. An *anticipated* failure is a normal successful tool result whose text begins `Error (CODE):`; an *unanticipated* exception propagates (`dispatch_action`'s broad-except does `log.exception(... status=error ...)` then `raise`). The reason is stated: "Every helper here returns a string rather than raising, so the dispatcher can only tell a rejection from a successful answer by inspecting the return value." The only `isError=True` producers in the whole tree are in the **bridge** and are used for transport failures — upstream not connected, app not listening, `call_tool` raised — never for a tool's own refusal.
PROVENANCE: `discodon/web/mcp/dispatch.py` `dispatch_action` (the `except Exception:` arm, waived `# prawduct:ok-broad-except — dispatch boundary; logs and re-raises`) and `discodon/web/mcp/eval/registry.py` `translate_eval_errors`; the stated reason at `discodon/web/mcp/validation.py` `mcp_error_text`; the `isError` producers at `tools/mcp_bridge/bridge.py` `UpstreamState.forward_call` / `_handle_call_tool` and `tools/mcp_bridge/bridge_tools.py` `_text_result`
VOLATILE: none.
TENSION: **The old capture's rule "Report tool failure as `isError: true`, never an exception" is CONTRADICTED by this repo's server**, which does neither. Its consumer-side cost claim is separately true and is kept below. Do not merge the two on discodon's evidence: this repo deliberately put the machine-readable signal *inside the text* and that choice is what *creates* the coded-error problem below.

**RULE:** (consumer-side half, CONFIRMED) Never let an exception escape a tool handler to a consumer — anything that raises lands in a broad catch and costs a full session teardown and reconnect.
FIRE-SITE: You are letting a handler raise because the consumer "will show the error anyway."
LAYER: L2
KIND: constraint
EVIDENCE: measured — a raised exception out of `call_tool` sets `self._connected = False`, calls `_safe_disconnect()` (a full `__aexit__`), rebuilds the `Client`, re-runs `list_tools`, re-applies the filter and cap, and only then retries the call once. On the bridge the same shape flips `connected=False` and fires `RECONNECT_SIGNAL`. A returned error string costs none of that.
PROVENANCE: `discodon/tools/mcp_bridge_tool.py` `McpBridgeTool.act` (the `except Exception` arm and the `_try_reconnect` retry) and `McpBridgeTool._try_reconnect`; `tools/mcp_bridge/bridge.py` `UpstreamState.forward_call`
VOLATILE: none.
TENSION: See the rule above — the two consumers agree that raising is expensive; the server disagrees with the corpus about *which* non-raising channel to use.

**RULE:** Give every error a machine-readable code in a fixed position (`Error (CODE): message`) — and register that code in the set that decides whose fault it was, because visibility and attribution are separate obligations.
FIRE-SITE: You are writing `return "Error: ..."` in a handler, or inventing a new error code.
LAYER: L1
KIND: diagnostic
EVIDENCE: incident, measured by an AST scan pinned in both directions. "A bare `Error: ...` matches nothing, so the request logs `status=ok` and a rejected call is indistinguishable in the logs from a served one. That is the defect this function exists to close; do not add a validator here that returns a bare `Error:` string." The attribution half: "an MCP error string carries a code — `Error (CODE): message` — so the dispatcher can see it, and a caller-input code is added to `_USER_INPUT_ERROR_CODES` so it is attributed correctly ... **visibility and attribution are separate obligations and fixing only the first trades one dishonest log for another.**" The miscoding incident: "The bespoke one emitted `Error (VALIDATION):` — a code no `_USER_INPUT_ERROR_CODES` entry matches (it carries `validation_error` and `validation_failed`, not `validation`), so `_classify_error_origin` defaulted it to `internal_state` and an operator passing `theme='blue'` was logged at WARNING as a system bug."
PROVENANCE: parser at `discodon/web/mcp/dispatch.py` `_API_ERROR_PREFIX_RE` (`^Error \(([A-Z_][A-Z0-9_]*)\):`), consumed in `dispatch_action`'s return-value inspection; classifier at `_USER_INPUT_ERROR_CODES` and `_classify_error_origin` (same file); builders at `discodon/web/mcp/validation.py` `mcp_error_text`, `discodon/web/mcp/formatters.py` `api_error_text` / `service_error_text`, `discodon/web/mcp/eval/registry.py` `translate_eval_errors`; inventory at `tests/unit/web/test_mcp_error_code_inventory.py` (`CODELESS_ERROR_SITES`, `_measure`, `test_codeless_error_inventory_matches_the_pinned_measurement`, `DELIBERATELY_INTERNAL_CODES`, `test_every_literal_error_code_is_deliberately_classified`, `test_the_two_classifications_do_not_overlap`); durable record at `.prawduct/artifacts/api-contract.md` § "MCP, as built"; the miscoding at `discodon/web/mcp/eval/analyses.py` `handle_analysis_chart`
VOLATILE: **"101 code-less returns" is SOURCED BUT SUPERSEDED — not unsourced, and not invented.** It is the title of backlog item **[MCP-J8QF]** ("101 code-less MCP error returns across 17 modules — 21 of them inside registered eval actions"). But that number is one point on a moving measurement the item itself documents, and the item's title disagrees with its own body. The full history, all of it in the tree: pinned at **104 sites / 18 modules / 23 eval** on 2026-07-20 ("**The pinned measurement (2026-07-20): 104 sites across 18 modules**"); a partial paydown on 2026-07-26 dropped it "from **104→102 sites** across **18→17 modules**, and the eval subset from **23→21**"; the title says **101**, which matches neither; commit `bd6e32a3b` and `.prawduct/artifacts/api-contract.md` record **95 across 17** at full closure; and at HEAD the scan returns `{}` — 0 sites, 0 modules ("**Closed 2026-09-02 (#2327): the inventory is empty.**"). **Quote none of these as "the number"** — the figure is a pinned-by-equality AST measurement that moved four times by design, and the honest citation is the mechanism (`tests/unit/web/test_mcp_error_code_inventory.py`, "Pinned by **equality**, not as a ceiling — a rise means new code shipped a code-less error; a fall means debt was paid and the number is lowered, which is the only thing that forces the documented total to stay honest"). The historical figure is re-derivable without checking anything out, by running `test_mcp_error_code_inventory._measure`'s logic over `git show bd6e32a3b^:<path>` for each `git ls-tree -r --name-only bd6e32a3b^ -- discodon/web/mcp`: **total 95, modules 17**, per module `telemetry_tool 15, scenario_tool 12, config_tool 9, decision_tool 9, eval/classifier 7, system_tool 7, eval/runs 6, budget_tool 5, logs_tool 5, entity_tool 4, prompt_tool 4, resolvers 4, eval_tool 3, c2_tool 2, dispatch 1, graph_tool 1, eval/results 1`. **And "17" is ambiguous — the corpus must not inherit the collision**: `api-contract.md`'s own sentence uses 17 for *modules* and, one clause later, 17 for *sites inside registered eval actions*; both readings are individually true, which is what makes the sentence dangerous, and the eval subset has separately been 23, 21 and 17 at different dates. Any rule carrying 17 must say *of what*, and *when*.
TENSION: Depends on the channel choice above — this rule is only necessary *because* the failure signal lives in the text. It also carries a rule about durable claims that the repo states about itself: "**a durable claim whose scope is wider than the mechanism backing it.** An exhaustive list in prose has no way to stay true; the fix is to make the assertion checkable rather than to correct it a fourth time" — the prior wrong versions being "the eval half is fixed", a commit titled "on every tool" that closed every *validator*, and "16 eval sites against a real 23" (which "came from counting only `return "Error: …"` and missing the `return None, "Error: …"` form the parse helpers use").

**RULE:** A code deliberately left OUT of the caller-input set needs its own explicit registration with its reason — because an unlisted code falls into the same bucket as a wrongly-unlisted one, and no exclusion list may be keyed on a name.
FIRE-SITE: You are adding an error code and deciding whether it is the caller's fault.
LAYER: L1
KIND: constraint
EVIDENCE: measured — "Each has to earn its place here, because the default for an unlisted code is the same `internal_state` an unregistered caller-input code silently falls into — the whole failure this pair of sets exists to make impossible to reach by accident." The direction of the asymmetry is argued, not assumed: `NOT_FOUND` stays internal because it is "ambiguous between a typo'd id and a resolver claiming something exists that the handler then cannot find, and that second case is a real bug that must not be buried at INFO ... false-WARN on a typo is the cheaper error." And the suppression-list lesson: the guard "shipped with one — `{"code", "validation"}`, described as placeholders quoted in prose about the convention. `validation` was not a placeholder ... **The exclusion is the only reason the guard was green on the very defect it was built to catch.** The other entry, `code`, was dead ... So the list contributed nothing but the blind spot."
PROVENANCE: `tests/unit/web/test_mcp_error_code_inventory.py` `DELIBERATELY_INTERNAL_CODES` (14 codes at this commit, each with its own comment), `test_the_two_classifications_do_not_overlap`, and the "There is deliberately NO exclusion list here" comment block; the asymmetry argued at `discodon/web/mcp/dispatch.py`, the comment above `_USER_INPUT_ERROR_CODES`
VOLATILE: the 14 entries in `DELIBERATELY_INTERNAL_CODES`; the 16 literal + derived members of `_USER_INPUT_ERROR_CODES` (`invalid_params`, `validation_error`, `invalid_request`, `missing_required`, `unknown_action`, `unknown_parameter`, `missing_parameter`, `invalid_enum`, `invalid_json`, `invalid_integer`, `invalid_number`, `invalid_type`, `empty_list`, `invalid_full`, `invalid_run_ids`, `validation_failed`, unioned with `{f"malformed_{p}" for p in UUID_PARAMS | LIST_ID_PARAMS}` "so a parameter added there classifies here in the same edit").
TENSION: none. Absent from the old capture.

**RULE:** Canonicalize an id before matching it, refuse the ones you cannot recover, and rewrite the caller's argument in place rather than merely inspecting it.
FIRE-SITE: You are matching a caller-supplied UUID against an exact-match store key.
LAYER: L1
KIND: diagnostic
EVIDENCE: measured, on named prod instances. "An id that is not the canonical lower-case hyphenated form — a truncated prefix off a read surface, an unhyphenated paste, upper case — matches nothing, so the read comes back empty and the caller is told there is no data when the truth is that they asked the wrong question. On a cost surface (`budget hierarchy`) that reads as '**this universe has spent nothing**'; on `decision list` as 'this entity has no decisions'." The self-own is in the operator-facing refusal string itself: "Note that read surfaces ABBREVIATE ids for display, marking it with a trailing '...', so an id copied off a table is usually the truncated one; `list_runs` and `campaign_list` print theirs in full." And in the canonicalizer's comment: "every renderer abbreviates (`truncate_id` emits `id[:8] + "..."`, the web client slices to eight and appends '…'), so `60cbbbb5...` is the shape a caller actually pastes — more common than the bare prefix, since it is what is on the screen."
PROVENANCE: `discodon/web/mcp/validation.py` `canonicalize_uuid`, `canonicalize_uuid_members`, `canonical_uuid_or_raise`, `canonical_uuid_members_or_raise` (all envelopes on `_canonicalize_one`), message owner `_truncated_uuid_message`, floor `_UUID_PREFIX_MIN_HEX = 8`, declared sets `UUID_PARAMS` / `NON_UUID_ID_PARAMS` / `LIST_ID_PARAMS`; dispatch-time guard at `discodon/web/mcp/dispatch.py` `_DISPATCH_GUARDED_UUID_PARAMS` and `_canonicalize_declared_uuids`; enumerated by `tests/unit/web/test_mcp_uuid_guard.py` (module docstring, `_RESOLVING_ACTIONS`, `test_every_declaring_action_is_in_exactly_one_of_the_two_states`, `TestTheGuardRefusesAtDispatch`) and `tests/unit/web/test_mcp_facade_schema_contract.py` (`TestEveryUuidParameterIsGuarded`, `test_every_declared_id_parameter_is_classified`, `test_no_classified_id_parameter_is_a_phantom`, `TestEveryListValuedIdParameterIsGuarded`, `TestAnIdParameterThatDoesNotEndInId`)
VOLATILE: **19 actions across four tools — REPRODUCED at HEAD.** Command: AST-parse each `discodon/web/mcp/*_tool.py` (excluding `eval_tool.py`), walk its literal `_ACTIONS` dict, count actions with `universe_id ∈ params`, partitioned on whether `universe_id ∈ resolves` → **19 guarded across exactly four tools**: `budget_tool` (hierarchy, history), `decision_tool` (runs, timeline), `scenario_tool` (create, delete, edit, estimate_cost, eval_history, evaluate, interpret, list, regenerate_entity, retry_attaches, show), `telemetry_tool` (cost, quality, query, trends); 8 resolve it instead. The set that *was* unguarded is now the set the dispatcher guards, which is why the number survived. The `8`-hex floor is sourced to measurement, not intuition: "every instance measured on prod (`60cbbbb5`, `c8e6340f`, `802b2066`) is exactly that group."
TENSION: Four refinements the old capture flattened, the last two being the reusable ones. (1) The decomposition is *recoverable* (a valid UUID in non-canonical form — "Validation alone cannot fix [it] because the value is valid — it has to be rewritten") vs *not recoverable* (a truncated prefix, where "Recovering the full id would mean a prefix search against the store, which is a lookup rather than a canonicalisation"); and "**The kwargs are rewritten in place, not merely inspected.** Checking and discarding leaves the larger half of the defect." (2) **The opt-out must be a declaration, never an omission** — `"resolves": ["universe_id"]` — because "an action that has to remember the guard is an action that can be added without it, and the audit that found one handler missing it found more than half the surface in the same state"; the enumerating test makes the third state (declared, guarded by neither) "unreachable by construction rather than merely unpopulated", and `_RESOLVING_ACTIONS` is duplicated in the test on purpose "so the test asserts the population rather than reading the declaration and agreeing with itself." (3) **Membership is declared because both heuristics were falsified against known instances**: inferring from help text "picks up `"Campaign UUID"` but misses `subject_id`, whose text reads 'entity id' — and that is one of the parameters the silent-empty defect was measured on"; inferring from the `_id` suffix "sweeps in name-shaped ids like `finding_id`" and misses `run_a` / `run_b`, which "carry no `_id` suffix, so the drift canary ... could not see them and they survived #2077's audit unguarded. **A parameter whose value is a UUID belongs here whatever it is called.**" (4) **Blast radius depends on whether the guarded id is READ or WRITTEN** — `LIST_ID_PARAMS`: "the declaration was right while the application was wrong for a release. Both names were declared here, so the drift canary counted them classified — and `@eval_action` intersected the action's params with `UUID_PARAMS` alone, so neither was ever handed to a guard. The consequence was not hypothetical: `campaign_add_runs` durably persists whatever run id it is given into campaign membership, so **a truncated one became stored state rather than one empty answer** (pacepace/discodon#2078)." A classification set and a guard set sharing a *name* but not an *application* is the generalisable defect.

**RULE:** Widening a tool's return annotation to a union DELETES its `outputSchema` under fastmcp — decide whether the structured wrapper was load-bearing and write the answer down beside the annotation.
FIRE-SITE: You are changing a handler's return type from `str` to `str | Image` so it can return a chart.
LAYER: L2
KIND: decision-point
EVIDENCE: incident (observed as a transport-level validation failure), with the cost recorded in three places and tested in none. "Returns: A fastmcp `Image` the client renders, or an error string when the arguments are wrong — the dispatcher recognises the error prefix, and **an image cannot carry a failure.**" The cost: "The union is what makes that possible: FastMCP derives the tool's `outputSchema` from this annotation, and a bare `-> str` makes returning an image a validation failure rather than an image. The cost of the union is that the tool no longer declares an `outputSchema`, so a text reply arrives as content without the `{"result": ...}` structured wrapper it used to also carry. The text content itself is unchanged, which is what clients read." Operator-facing: "the former bare `str` made returning an image a transport-level validation failure. The consequence is recorded rather than hidden — the `eval` tool no longer declares an `outputSchema`".
PROVENANCE: `discodon/web/mcp/eval/analyses.py` `handle_analysis_chart` (docstring); `discodon/web/mcp/eval_tool.py` — the facade's `-> str | Image` annotation and its docstring; `documentation/MCP_SERVER.md` § `eval` — Eval System (the `analysis_chart` paragraph); acknowledged in `discodon/web/mcp/dispatch.py` `dispatch_action`'s Returns clause
VOLATILE: **This is FastMCP-specific**, not an MCP-protocol fact — `fastmcp==3.4.2` (`pyproject.toml`). A corpus rule must name the library or it will be applied where it is false.
TENSION: The tree's framing is a **priced trade, not a prohibition**: the union was chosen, the loss of `structuredContent` accepted, and the acceptance written down three times ("recorded rather than hidden"). **And nothing tests it** — no assertion that `eval`'s published tool lacks an `outputSchema`, nor that any other facade still has one, so a future narrowing that re-breaks `analysis_chart`, or a widening that silently drops another tool's `outputSchema`, would pass every gate. That is a real gap on a surface where everything else here is pinned. Adjacent measured number the rule does not need but which explains the design: "a rendered chart is roughly 75k base64 characters", which is why charts are opt-in per finding rather than folded into `analysis_get`.

**RULE:** A proxy must forward the whole result object, not re-render its text — and if you are the server, duplicate anything load-bearing out of `structuredContent` into a text block, because one of the two consumers in this repo drops it.
FIRE-SITE: You are writing a proxy's call-forwarding path, or relying on `structuredContent` to carry a fact.
LAYER: L2
KIND: constraint
EVIDENCE: measured — **the two consumers do opposite things, and the old capture named the wrong one.** The stdio bridge forwards verbatim: `forward_call` does `return await self.session.call_tool(name, arguments)` and `test_forward_structured_content_passes_through` builds a `CallToolResult(content=[TextContent(...)], structuredContent={"k": "v"})` and asserts `result.structuredContent == {"k": "v"}`; sibling tests pin `ImageContent` and `EmbeddedResource` pass-through the same way, and the docs claim "Tool calls are forwarded transparently, preserving all MCP content types." The entity-facing consumer drops it: `_extract_text(result)` iterates **only** `result.content`, and `grep -rn structuredContent discodon/` returns no hits at all.
PROVENANCE: the forwarder at `tools/mcp_bridge/bridge.py` `UpstreamState.forward_call` and `_handle_call_tool`, pinned by `tests/unit/mcp_bridge/test_bridge.py::test_forward_structured_content_passes_through`; the dropper at `discodon/tools/mcp_bridge_tool.py` `_extract_text`; doc claim at `documentation/MCP_SERVER.md` § "Connection Architecture"
VOLATILE: none.
TENSION: **The old capture's attribution is CONTRADICTED.** It said "the sibling bridge in the same repo does exactly that [drops it]" — `tools/mcp_bridge/bridge.py` does the opposite and has a test pinning it. The naive text-only renderer is `discodon/tools/mcp_bridge_tool.py`'s `_extract_text`, the consumer-side tool that lets a persona call third-party servers. Two surfaces with confusingly similar names; the rule picked the wrong one. The substance survives intact and is arguably strengthened: a server facing an unknown consumer must assume the `_extract_text` shape.

**RULE:** Put every load-bearing fact in a TextContent block — an image flattens to a label and nothing inside it survives.
FIRE-SITE: You are returning a chart, table image, or diagram as the answer.
LAYER: L2
KIND: constraint
EVIDENCE: measured — `_extract_text` renders `ImageContent` as `f"[Image: {block.mimeType}]"` and `ResourceLink` as `f"[Link: {label} — {block.uri}]"`; an `EmbeddedResource` survives only if `hasattr(block.resource, "text")`, else it becomes `f"[Embedded resource: {block.resource.uri}]"`; anything else becomes `str(block)`. The server side holds the same discipline for its own reasons: `analysis_get` "lists each chart's **values as drawn** ... so the claim is checkable on a text surface."
PROVENANCE: `discodon/tools/mcp_bridge_tool.py` `_extract_text`; pinned by `tests/unit/tools/test_mcp_bridge_tool.py` `TestExtractText::test_image_content` / `::test_resource_link` / `::test_mixed_content` and `TestMcpBridgeToolAct::test_act_with_image_result` / `::test_act_with_resource_link_result`; the server-side counterpart at `documentation/MCP_SERVER.md` § `eval` — Eval System (the `analysis_get` paragraph)
VOLATILE: none.
TENSION: No *rule* states this on the server side — it holds by construction (every facade returns `str`, or `Image` for the one chart action). The consumer's flattening is the measured half.

**RULE:** Never return zero content blocks — an empty `content: []` is indistinguishable from a successful no-op, so a consumer will invent text for you.
FIRE-SITE: You are returning early from a handler with nothing to say.
LAYER: L2
KIND: constraint
EVIDENCE: measured, **but only as a consumer defending itself** — there is no server-side norm or test for this anywhere in the tree. `_extract_text` ends `return "\n".join(parts) if parts else "No content returned"`, pinned by `assert _extract_text(result) == "No content returned"`.
PROVENANCE: `discodon/tools/mcp_bridge_tool.py` `_extract_text`; pinned by `tests/unit/tools/test_mcp_bridge_tool.py` `TestExtractText::test_empty_content`
VOLATILE: the literal `"No content returned"`.
TENSION: Weakly sourced as a *server discipline*. What the tree actually demonstrates is that a consumer will substitute a string of its own choosing, which the model then reads as the tool's answer — that is the transferable claim and it is enough.

**RULE:** A refusal must name what the action DOES accept, and its log line must name the offending parameter while keeping its VALUE out.
FIRE-SITE: You are writing the message for a rejected argument.
LAYER: L1
KIND: pattern
EVIDENCE: measured — the built string is "`{action}` does not accept {offending}, so passing {them/it} would have changed nothing about the answer. Accepted: {accepted}. Use action='help' for details.", with the test comment "a refusal an operator cannot act on just moves the guessing one step later." The log half has a non-obvious warrant: "The returned text names them, so a calling agent self-corrects and the problem never surfaces. **A maintainer watching a RATE of these has only the log**, and without the names cannot tell which doc, runbook or tools/ script is generating them without reproducing the call." Values are excluded deliberately — "a param value can carry an id or a secret" — and the test asserts the negative: `assert "sekrit" not in line, "parameter VALUES must never reach the log line"`. A third discipline rides along: a refusal landing before any work still emits the shared status shape with real zeros, because "every other status line in this module carries the field, and a reader that parses them cannot be asked to special-case one shape."
PROVENANCE: `discodon/web/mcp/dispatch.py` `_reject_undeclared_params` (message and Returns clause) and `dispatch_action` (the `params=` and `duration_ms=0.0` log arguments); `discodon/web/mcp/validation.py` `_missing_parameter_error` (the single-owner discipline) and `_truncated_uuid_message`; pinned by `tests/unit/web/test_mcp_dispatch.py` `TestUndeclaredParamRefusal::test_an_undeclared_param_is_refused_with_the_canonical_code`, `::test_the_refusal_log_names_the_offending_params`, `::test_the_refusal_logs_as_a_caller_error_not_a_bug`
VOLATILE: none.
TENSION: The "an agent self-corrects, so the problem never surfaces" half generalises well past MCP: **a refusal a machine consumer silently fixes is invisible to operators by design**, so the log is the only channel and must be built for aggregation rather than for reading one line. Note also the single-owner rule for the message itself: `_missing_parameter_error` is "The single owner of that sentence. `validate_required` and `validate_present` differ only in which values they count as absent — the operator-visible text must not also differ, or the same condition reads two ways depending on which helper a handler happened to call."

**RULE:** Gate a destructive action on a `confirm` that ECHOES the target's id, not on a metadata hint a client may ignore.
FIRE-SITE: You are marking a destructive tool with `destructiveHint` and considering that sufficient.
LAYER: L1
KIND: pattern
EVIDENCE: measured — no read-only/mutating classification exists anywhere on this server (`readOnlyHint`, `destructiveHint`, tool annotations, a `read_only` field: **zero hits**). The action metadata schema is `description` / `params` / `required` / `example` / `tips` / `hidden` / `resolves` / `long_running`, and `long_running` selects a timeout budget, not a safety class. What guards destruction instead is per-action and un-ignorable: "seven of the eight eval actions declaring it require it to **echo an id exactly**", the eighth being `nuke_all_eval_data` with the constant `'yes-delete-everything'`. On `classifier_snapshot_delete` the echo is required **unconditionally** — "a case with zero stored results is gated exactly as hard as one with thirty" — because the results are recomputable and the case is hand-authored prose "that nothing regenerates, and a never-evaluated case is the one most likely to have been written minutes ago."
PROVENANCE: `discodon/eval/curation.py` `require_delete_confirmation` (cited from `discodon/eval/service.py` at its three call sites); `documentation/MCP_SERVER.md` § `eval` — Eval System (the `classifier_snapshot_delete` paragraph); the bridge's own case-sensitive equivalent at `tools/mcp_bridge/bridge_tools.py` (`confirm == profile.upper()`, "typing `'prod'` lowercase or `'Prod'` is the kind of slip we want to catch")
VOLATILE: the `'yes-delete-everything'` literal; the seven-of-eight split.
TENSION: Reinforces the read-only/mutating inversion in § A from the other end — this server does not *offer* a classification either, and what it built instead cannot be satisfied by a client that ignores metadata. Absent from the old capture.

---
# E. Long-running work, progress, wedged-vs-slow

The highest-incident cluster in the source, and the one where the previous pass's phrasing needed the
most correction — three of its rules state a number or a category the tree does not hold.

**RULE:** Give a long-running action a status channel a caller can poll INDEPENDENTLY of the call's return — the test is categorical (does an equivalent of `get_run` exist for this work?), not durational.
FIRE-SITE: You are shipping a tool whose work takes minutes and whose only output is the eventual return value.
LAYER: L1
KIND: constraint
EVIDENCE: incident, twice, three weeks apart, with no instrumentation on either. "`analysis_generate` publishes no progress. The call ran ~12 minutes and the MCP client eventually aborted it on a 1800s idle timeout **after the generation had already succeeded and been stored** ... **Runs have `get_run` for exactly this; generations have no equivalent, so a caller cannot distinguish a working generation from a hung one.**" Logged as "**Second observation of the same failure**."
PROVENANCE: `.prawduct/artifacts/eval-smoke-2026-08-20-v2.3.45.md` § "One further observation"; `.prawduct/artifacts/archive/build-plan-eval-smoke-2026-08-20.md`, row "Progress observation"; the first observation at `.prawduct/backlog.md` item **[MCP-H3ZP]**
VOLATILE: **"~30s" is INVENTED and must be dropped.** The threshold does not exist anywhere in the tree in any form — no constant, no config field, no doc rule. Stronger: there is no MCP progress mechanism at all to hang a threshold on — `grep -rn "report_progress\|notifications/progress\|progressToken\|progress_token" discodon tools tests documentation .prawduct` returns zero hits in any source path (the only `report_progress` hits are backlog item **[RES-PG4R]**, an unbuilt research-tool sub-tool unrelated to MCP). A duration threshold is the one framing the source **rejects**: the whole point of the second incident is that the WORK finished and the RESPONSE hung, so no duration on the work would have fired.
TENSION: Splits from the rule below, which the old capture fused into it.

**RULE:** A response-path hang is INDISTINGUISHABLE from a runaway generation, and that ambiguity is what makes an operator pay twice — so a billable action must publish its intent before it spends.
FIRE-SITE: You are deciding whether a tool that spends money needs a pre-spend log line or an in-flight marker.
LAYER: L1
KIND: diagnostic
EVIDENCE: incident — "The 15:49Z generation **completed and stored normally** (**$0.8005**) ... The **MCP call did not return for ~30 minutes afterward.** This is a **response-path hang, not a work hang** ... from the caller's side it is **indistinguishable from a runaway generation**, which is exactly the state an operator is most likely to react to expensively (kill it, retry it, and pay again)." The mitigation that does exist: "The call's scale (model + approx input tokens + output cap) is logged before it runs; there is no pre-run dollar estimate because **cost is only observed, never priced**." And the number of billable attempts is bounded at one chokepoint: "one generator call over the campaign's bundle, and a SECOND one if anything refuses the first output ... **so two calls is the ceiling, not the norm.**"
PROVENANCE: `.prawduct/backlog.md` item **[MCP-H3ZP]** ("MCP `analysis_generate` did not return for ~30 minutes after the generation completed and stored normally", `status: open · stage: research`); the pre-spend discipline at `discodon/web/mcp/eval/analyses.py` `handle_analysis_generate` (its `tips=[...]`); the attempt bound at `discodon/eval/analysis/generator.py` `_reject_incomplete_generation` — refuse a provider-truncated result *before* the soundness chain, because a salvageable partial "regenerates into the same cap and bills a second full generation to fail the same way"
VOLATILE: **$0.8005** — reproduced (`grep -rn "0\.8005" .prawduct` → exactly one hit, MCP-H3ZP). **~30 min** — reproduced (MCP-H3ZP, title and body). **~12 min** and **1800s** — reproduced, but they belong to the OTHER incident: $0.8005/~30 min is 2026-07-30 (`eval-bundle-confounds`); ~12 min/1800s is 2026-08-20 (v2.3.45 smoke). The old capture fused two observations into one.
TENSION: **[MCP-H3ZP]** is at `stage: research` with the deliverable *identify the hanging leg* — no fix exists. Its own lead notes the observed non-return was "roughly **twice**" the 900s generation budget, so either the budget does not cover the hanging leg or the hang is downstream of cancellation. **And the 1800s abort in the second observation is probably not the client at all** — see the drift report; if the server's own session reaper is the terminator, the diagnosis changes and so does the fix.

**RULE:** Size timeouts per tool CLASS, and declare the class beside the action rather than keeping a list of slow actions in the dispatcher.
FIRE-SITE: You are giving every action on a facade the same timeout, or maintaining a set of "these are the slow ones" next to the dispatch loop.
LAYER: L3
KIND: pattern
EVIDENCE: measured — the incident: "**Prediction confirmed — empirically, not just by measurement (2026-07-29).** A real paid regeneration of campaign `c8e6340f` was **cancelled at 121s, billed, and stored nothing**." Restated at the config: "`analysis_generate` spends real provider money on one generator call over a whole campaign's bundle, and inherited a 120s default written for quick reads. On a 22-run campaign it was cancelled mid-flight — the call was billed, nothing was stored, and **the only signal was 'timed out after 120s'**." The replacement is honest about its own status: "The 900s default is a **deliberate over-estimate rather than a measurement** — the dispatcher logs duration_ms on success, so tighten it once real generations have reported." The declaration site is the reusable half: `eval_action(..., long_running=...)`, "Declared here, beside the action, because **a list of slow actions kept in the dispatcher drifts as actions are added**."
PROVENANCE: `discodon/config/sections/mcp.py` `McpConfig.action_timeout_s` (120.0) and `McpConfig.generation_action_timeout_s` (900.0), plus that module's closing docstring paragraph; the declaration at `discodon/web/mcp/eval/registry.py` `eval_action`; the incident at `.prawduct/backlog-archive.md` § "Shipped 2026-07-30 — eval-generator-false-nulls", item **[EVL-TD4S]**; the governing ruling at `.prawduct/artifacts/project-preferences.md` § Architecture Patterns, bullet "Operational limits are config, never constants"
VOLATILE: 120.0 / 900.0 are hot config defaults. **The cancellation was measured at 121s, not 120s** — one second past the budget, which is what makes it evidence rather than inference. The **22-run** campaign is corroborated independently at `.prawduct/artifacts/build-plan-eval-report-presentation.md` ("analysis `83672866`, 22 runs, $0.7278").
TENSION: `long_running` is load-bearing for a **second, unrelated** concern in the same decorator — it also gates `_translate_provider_errors`, because "a provider error stringifies as its whole response body, account id included." One declaration, two consumers; know that before copying the pattern. The parent ruling is broader and worth carrying whole: "**A timeout, budget, retry count, cap or threshold that governs whether real work is allowed to finish MUST live in a config section with `reload="hot"`, and MUST be read per operation rather than captured at import.** An import-time read defeats hot reload while looking configured, which is worse than a plain constant because it reads as done."

**RULE:** (SPLIT OUT — NOT BUILT) Never cancel work you have already been billed for; a larger budget makes cancellation less likely and does not make it safe.
FIRE-SITE: You are raising a timeout to stop cancelling paid work and calling the problem solved.
LAYER: L3
KIND: constraint
EVIDENCE: designed-untested — the tree states plainly that this half is unbuilt: "A larger budget makes the 121s cancellation less likely; it does not make cancellation-after-spend safe. A cancelled generation **still bills**, and **nothing today prevents or even detects a retry re-spending — no request key, no in-flight marker, no post-hoc reconciliation between billed generations and stored analyses.**" The archive is blunter: "Archived on the owner's call that the observed path was the item; the general request-key/reconciliation design is unbuilt and unowned."
PROVENANCE: `.prawduct/backlog-archive.md` § "Shipped 2026-07-30 — eval-generator-false-nulls", item **[EVL-TD4S]** (the scope-honesty paragraph)
VOLATILE: none.
TENSION: **The old capture shipped these two halves as one settled fix.** They have opposite evidence states: sizing is built and measured, never-cancel-billed-work is neither. And the successor tracker the archive hands it to **does not exist** — see the drift report; this is the one money-losing path in the cluster and it is currently invisible to the backlog.

**RULE:** Keep any advertised maximum strictly inside your dispatch budget — and fix it by RAISING the outer bound, reading both sides live, never by lowering the inner ceiling.
FIRE-SITE: You are setting a caller-visible maximum duration and a dispatch timeout, and they are equal or close.
LAYER: L3
KIND: constraint
EVIDENCE: designed-untested for this site (a derivation, never observed firing) + incident for the precedent it cites. "At the shipped defaults the two are *equal* (both 120), so a maximal capture would race its own dispatch budget and lose: **the caller would get 'timed out' for a capture that was doing exactly what it was asked to do.**" The precedent's real incident: "That is exactly how the pre-IQ-3 120s placeholder failed: it sat below the then-150s structural max, so a resolve taking the retry-then-normalize path **died while succeeding**."
PROVENANCE: `discodon/web/mcp/watch_tool.py` `_DISPATCH_BUDGET_MARGIN_S` (15.0) and `_dispatch_budget_s`; the two 120s at `discodon/config/sections/mcp.py` `McpConfig.action_timeout_s` (120.0) and `McpConfig.watch_capture_max_s` (120); the precedent at `discodon/operations/timeouts.py` `_budget_music_resolve` (and the module docstring, `_budget_tool_restart`, `_budget_eval_cell`); general form at `.prawduct/artifacts/project-preferences.md` § Architecture Patterns
VOLATILE: **15.0** reproduced (`_DISPATCH_BUDGET_MARGIN_S`, consumed once). **Both 120s** reproduced — `grep -n "default=120" discodon/config/sections/mcp.py` returns two hits on two different fields, so "both were 120" is literally true. **"Noted at three other call sites" is CONTRADICTED as a category.** The canonical sentence occurs exactly three times in `discodon/operations/timeouts.py` (verified by multiline count at ~72, ~381, ~521) but **none of the three is a call site** — one is the module docstring and two are budget-formula docstrings, with no `operation_timeout(...)` invocation at any of them. The phrase count also *undercounts* the real population: `_budget_eval_cell` states the same rule in different words ("Must sit ABOVE the inner async-delivery drain timeout") and is invisible to any grep for the canonical sentence. Read it as "three other places in `operations/timeouts.py`, none of them a call site, and a fourth that says it differently."
TENSION: **The word "margin" undersells the mechanism and the old phrasing points at the wrong fix.** `_dispatch_budget_s` is `max(action_timeout_s, inner_ceiling + 15.0)` — it **raises, never lowers**, because "an operator who has deliberately raised `action_timeout_s` keeps their value." A rule phrased as "keep the advertised max below the dispatch timeout" reads as *lower the advertised max*, which is not what the tree does. The general form is better: "**A derived ceiling clamps against the live value, and fits inside it.** If a limit is bounded by another ... read the bound live — a copied constant silently breaks the moment an operator lowers the source — and leave headroom, since a ceiling equal to its bound cannot return inside it." Note the inner ceiling here is itself a `max` over two knobs in **different units** (seconds and milliseconds), so a unit slip in either silently moves the outer budget.

**RULE:** A timeout reply must say which of THREE things happened — cancelled-while-queued, still-running-detached, or genuinely-cancelled-async — because elapsed time cannot distinguish them; detect the difference with a flag the worker sets, not with a duration.
FIRE-SITE: You are writing the message a caller gets when your dispatch budget expires.
LAYER: L3
KIND: diagnostic
EVIDENCE: measured, with the interpreter version named. "a work item still PENDING in the pool queue is cancelled rather than run. **Measured on CPython 3.14.6**: the queued handler never executed, not even after the busy worker freed." The two opposite instructions: `detached` — "It ran off the event loop, so this reply frees the caller without interrupting a blocking call already in flight — **that work may still complete and store its result.**" `queued` — "It never started and has been CANCELLED, not delayed: every one of the {n} `mcp.sync_handler_workers` slots was busy for the whole budget, so the call expired waiting in the queue and was dropped when the budget cancelled it. **Nothing ran and nothing was written — re-issue it.** Raise `mcp.sync_handler_workers` if this recurs under concurrent load." The detection mechanism: a `threading.Event` (`handler_started`) set *inside* the pooled callable, because "A sync timeout has two entirely different causes and **the duration cannot tell them apart**."
PROVENANCE: `discodon/web/mcp/dispatch.py` `dispatch_action`, the `except OperationTimeoutError` branch (the `handler_started` Event, the `disposition` computation, the two `detail` arms, and `_configured_sync_workers()`); pinned by `tests/unit/web/test_mcp_dispatch.py` `test_a_queued_call_is_cancelled_not_merely_delayed`, `test_a_call_that_never_got_a_worker_is_not_reported_as_detached`, `test_the_timeout_reply_says_the_work_was_not_cancelled`, `test_an_async_timeout_does_not_claim_detachment`
VOLATILE: CPython **3.14.6** — the queued-item-is-cancelled behaviour is an interpreter observation, not a documented guarantee.
TENSION: **There are three dispositions, not two**: `disposition = "async" if handler_is_async else ("queued" if queued_out else "detached")`. The async arm deliberately emits an *empty* detail, because a cancelled await really is cancelled and claiming detachment would be the same lie pointing the other way. Two further things the old capture dropped: (1) the **symmetry of the harm** is what makes this a rule — telling a detached caller it was cancelled invites them to read a later write as a ghost result, while telling a queued caller it will run later leaves them "waiting for a result that can never arrive instead of re-issuing the call, which is the one thing that recovers it"; (2) the `queued` detail interpolates the **live pool width**, not the config value, because `sync_handler_workers` is `reload="restart"` and the config value after a hot reload describes the *next* boot — "The saturation message quotes a number an operator is about to act on, so it has to be the second one." **A reply that names a knob must name the knob's current value, not its declared one.**

**RULE:** Also put the disposition in the LOG line, because the cause of a saturated pool lives in a global knob rather than in the failing request and therefore has no signal pointing at it.
FIRE-SITE: You are logging a timeout and the caller-facing message already explains it.
LAYER: L3
KIND: diagnostic
EVIDENCE: designed, with the operator action named — "`disposition` is the one thing this line adds beyond the shared shape, and it is the field that makes a saturated pool diagnosable at all ... The second is not a fact about this action — it says `mcp.sync_handler_workers` is too low for the concurrent load, which is the knob an operator would otherwise have no signal pointing at. **Grep a rate of `disposition=queued` to size it.**"
PROVENANCE: `discodon/web/mcp/dispatch.py` `dispatch_action` (the `disposition=` field on the timeout `log.error`)
VOLATILE: the three disposition values.
TENSION: Generalises past timeouts: **a failure whose cause lives in a global knob rather than in the failing request must emit a field that aggregates, or the knob will be tuned by guesswork.** Same dispatcher applies the pattern twice more (`params=` names only, values redacted). Absent from the old capture.

**RULE:** Never run a blocking handler on the transport's event loop — put the uninterruptible class on a dedicated pool, and do not conclude from that that the shared executor is now safe.
FIRE-SITE: You are registering a handler that is a plain `def` and doing blocking IO.
LAYER: L3
KIND: constraint
EVIDENCE: incident, production v2.3.42 — "Observed on production v2.3.42 as head-of-line blocking: a `classifier_run` **wrote all 29 of its results and then never returned**, while **three** later `eval` calls queued behind it made no progress at all until every one of them was cancelled." The isolation reasoning, verified end to end: "a fired budget returns control to the caller but **CANNOT kill the thread**, so a wedged handler holds its worker until it unwedges. On the default executor those stuck workers would starve every other `asyncio.to_thread` user in this process — including the `/healthz` and `/readyz` probes, which `web/app.py` runs through `run_in_executor(None, ...)`, and **which Kubernetes reads as the pod being dead.**"
PROVENANCE: `discodon/web/mcp/dispatch.py` module docstring § "Why a sync handler never runs on the event loop" (the incident), the comment block above `_sync_handler_pool` (the healthz reasoning), and `_get_sync_handler_pool()`; pool width at `discodon/config/sections/mcp.py` `McpConfig.sync_handler_workers` (default 8, `reload="restart"`); the starvation target verified at `discodon/web/app.py` `healthz()` / `readyz()` — `grep -n "run_in_executor" discodon/web/app.py` returns `run_in_executor(None, run_health_checks)` and `run_in_executor(None, readiness_check)`, both on the default executor at the two probe routes
VOLATILE: 29 results, three queued calls, v2.3.42 — all reproduced, and v2.3.42 is corroborated independently at `discodon/eval/analysis/generator.py` `_reject_incomplete_generation` and `tests/unit/eval/test_analysis_generator.py`, both of which name the same prod session and explicitly disclaim it as *not* their path's doing. 8 workers reproduced.
TENSION: **The tree is more careful than the rule about what the isolation does NOT cover, and that caveat is the reusable half.** "Read the scope of that containment precisely. It covers SYNC handlers, which are the class a fired budget cannot interrupt. Several ASYNC MCP handlers still reach the default executor through their own `asyncio.to_thread` calls, alongside the probes — a timeout genuinely cancels those, so they do not pile up the way a wedged sync handler does. **The invariant is 'the uninterruptible class is isolated', not 'MCP never touches the shared executor'.**" Two live residuals the fix created and the tree volunteers: (1) an unfinished audit — two shared objects were checked (the Entity API's per-caller REQ socket pool, connection-per-operation storage) but "**The other tools' handlers were not individually audited** ... nobody walked all fourteen. A handler that caches into a module global, or holds a client with per-call state, would be unsafe here and would not have been caught." (2) The fix **imposed a first ceiling** rather than tightening one: "moving sync handlers under `action_timeout_s` did not tighten an existing ceiling, it imposed a first one on **~51 handlers at once** ... Which of those handlers can legitimately exceed 120s HAS NOT BEEN MEASURED ... `results_pivot` is the known candidate — it is the call that demonstrably wedged prod v2.3.42 — but 'wedged the loop' is evidence of blocking, not of duration, and nobody has timed it." Profiling is filed as **#2320**, open.

**RULE:** A non-daemon worker pool must be torn down at the end of the process lifespan — and "cancelled" describes the caller, never the thread.
FIRE-SITE: You are adding a `ThreadPoolExecutor` and reasoning about shutdown, or diagnosing a hang that survives your shutdown call.
LAYER: L3
KIND: constraint
EVIDENCE: designed, and notable as a *corrected* claim: "**What it does not buy, and the docstring used to claim it did:** a handler already EXECUTING still holds interpreter exit. CPython's `concurrent.futures.thread` registers `_python_exit` via `threading._register_atexit` and joins every thread still in `_threads_queues`; a worker inside a blocking call stays there until that call returns, whatever `wait=False` says. So the wait moves from here to interpreter shutdown rather than disappearing. **Anyone diagnosing a hang that survives this call must NOT rule these threads out — that wrong turn is why the claim is corrected rather than softened.**"
PROVENANCE: `discodon/web/mcp/dispatch.py` `shutdown_sync_handler_pool()`; the lifespan shutdown block in `discodon/web/app.py`; pinned by `tests/unit/web/test_mcp_dispatch.py` `test_the_lifespan_releases_the_sync_handler_pool` and `test_the_lifespan_releases_the_classifier_write_pool`
VOLATILE: CPython-internal symbols (`_python_exit`, `_threads_queues`, `threading._register_atexit`) — private API, may move.
TENSION: The reusable content is the **correction discipline**, not the teardown: a docstring asserted a guarantee the mechanism cannot provide, and the fix restates it precisely *and names the wrong diagnostic turn the false claim would have caused* rather than hedging the sentence. The same precision appears three times for this one mechanism, all converging on "the CALLER stops waiting, the thread does not stop." Absent from the old capture.

**RULE:** Size a dedicated pool from the same number that bounds the fan-out it serves, and WIDEN it by dropping the old executor rather than shutting it down.
FIRE-SITE: You are choosing a worker count, or making a pool width hot-reloadable.
LAYER: L3
KIND: pattern
EVIDENCE: designed, with a real bug found and fixed inside the mechanism — "Sized from the same number that bounds the fan-out, so the pool can never be narrower than the concurrency it serves — **a smaller pool would silently serialise the writes and read as the semaphore not working.**" And on widening: "The old pool is DROPPED, not shut down, and that distinction is a bug this widen path had. A concurrent `run_classifier_eval` captured the old executor in its own local before the reload, so shutting it down here makes its next `submit` raise `RuntimeError: cannot schedule new futures after shutdown` — swallowed by the per-case guard and reported as an unstored row, so **a raised ceiling overlapping a run would silently cost that run its remaining writes.** This docstring already names that hazard as the reason not to NARROW; the widen path was doing it anyway."
PROVENANCE: `discodon/eval/classifier.py` the `_write_pool` comment block and `_get_write_pool(width)`; the sibling it cites is `discodon/web/mcp/dispatch.py`'s sync-handler pool
VOLATILE: pool width == `classifier_concurrency` (default 8, `ge=1, le=32`, `reload="hot"`); the default executor is sized `min(32, cpu_count + 4)` → 6 on a 2-core pod.
TENSION: Two pools, one hazard, two *different* sizing strategies (a fixed config knob vs. derived-from-fan-out). The transferable defect is the self-caught one: **a docstring can name a hazard as the reason not to do X while the code does X one branch over.** Absent from the old capture.

**RULE:** Assume your consumer has NO timeout on your call — and if you ARE the consumer, wrap the outbound call, because an unbounded third-party wait does not degrade one call, it takes the whole turn.
FIRE-SITE: You are awaiting a third-party MCP server's `call_tool`, or reasoning about how long your own tool may take.
LAYER: L3
KIND: constraint
EVIDENCE: incident-free — a code-walk finding, filed open, never observed firing. "Highest-value consumer: `mcp_bridge_tool.py` — `await self._client.call_tool(action, parameters, raise_on_error=False)` sits inside `async def act` with no `operation_timeout` wrapper, so **a hung third-party server cancels the entire entity turn** instead of failing one call; the post-reconnect retry is equally unbounded, and the fix must wrap **both**. **Not already satisfied by the existing `mcp_action` op** ... that is the INBOUND MCP server-dispatch budget and does not cover this outbound bridge call — don't close this item against it."
PROVENANCE: `.prawduct/backlog.md` item **[LLM-ZB4L]** (`status: open · stage: ready`); the two unwrapped awaits at `discodon/tools/mcp_bridge_tool.py` `McpBridgeTool.act` (the primary call and the post-reconnect retry inside the `except`)
VOLATILE: verified independently rather than taken from the item — `grep -n "timeout" discodon/tools/mcp_bridge_tool.py` returns **zero hits in the entire 617-line file**: no timeout, no `operation_timeout`, no `wait_for`. The item's own line numbers are stale; see the drift report.
TENSION: **The old capture's phrasing inverts the role that makes this finding valuable.** "Assume the consumer has no timeout on your call" is server-side advice; what this repo actually learned is the mirror — **discodon is the consumer with no timeout**, and the blast radius is the whole entity turn, not one degraded call. Both rules are real; only the second has teeth, because a third party you do not control decides how long your turn takes. The item also carries a trap worth preserving: an existing `mcp_action` budget *looks* like it covers this and does not (inbound dispatch vs outbound call), so a plausible close would leave the hang in place. The surrounding code is not careless — both call sites degrade to `ActionResult(success=False, ...)` with a reason; it is specifically the **unbounded wait** that survives, which is exactly the failure a broad except cannot see.

**RULE:** Flip your connected flag and signal a reconnect from the CALL path, not only from the refresh timer — and note that treating any exception as session death is only affordable because your reconnect is cheap.
FIRE-SITE: You are relying on a periodic health/refresh tick to notice a dead session.
LAYER: L3
KIND: pattern
EVIDENCE: incident — "without this, a session that died between `TOOL_REFRESH_INTERVAL` ticks (300s) stays in the bridge as a stale handle for up to 5 minutes; every forward_call returns 'Session terminated' while `bridge_health` reports `upstream_connected=True`. The reconnect itself is cheap (~3s) so **a false-positive on a transient error costs at most a few seconds of unavailability — much better than the worst case.**"
PROVENANCE: `tools/mcp_bridge/bridge.py` `UpstreamState.forward_call` (docstring holds the incident, the fix and the price), `TOOL_REFRESH_INTERVAL` (300), `RECONNECT_DELAY` (3); pinned by `tests/unit/mcp_bridge/test_bridge.py` `test_call_failure_flips_connected_and_signals_reconnect` and `test_call_failure_self_heal_works_for_any_exception_type`; operator-facing at `documentation/MCP_SERVER.md` § Troubleshooting ("The bridge will reconnect on its own (~3s)")
VOLATILE: 300 and ~3s both reproduced. **The old capture's `reconnect_attempts=0, last_error=null` detail is an INFERENCE, not a recorded symptom** — the incident names exactly one field, `upstream_connected=True`. The other two are *consistent* with the tree (the connection manager resets all three on a successful connect, and `_health_payload` emits `"last_error": upstream.last_error` raw, so a healthy-then-dead session really would render JSON `null`) but no record states them. Cite `upstream_connected=True` and say the rest was derived.
TENSION: **The tradeoff is a precondition, not a footnote.** "Treat ANY exception as session death" is deliberate, pinned by a test whose name is the decision — and it is affordable *only because* reconnect is 3s against a 300s worst case, a 100:1 ratio the docstring works out explicitly. Ported to a system where reconnect costs 30s, the same rule is wrong. That precondition is the transferable content, and the old capture stated the cost without the price that justifies it.

**RULE:** Fail fast with a machine-readable diagnostic when you are unavailable — carry profile, backend, last error, last error time, attempt count and a NAMED next command, and pin the latency.
FIRE-SITE: You are writing the reply for "the thing I proxy is not up."
LAYER: L3
KIND: pattern
EVIDENCE: measured for the latency bound — `assert elapsed < 0.1, f"call_tool blocked for {elapsed:.3f}s — fast-fail regressed"`, which is the strongest form because it goes red if the property regresses. The payload substitutes placeholders rather than leaking sentinels: `last_error = upstream.last_error or "(none recorded)"`, `last_error_at = ... if upstream.last_error_at else "(never)"`, closing with "Run bridge_health for full state, or start the Discodon backend." A companion assertion: `assert "None" not in text  # no raw Python None leaks`.
PROVENANCE: `tools/mcp_bridge/bridge.py` `_disconnect_error_text()` (payload builder) and `_handle_call_tool()` (the fast-fail branch); pinned by `tests/unit/mcp_bridge/test_bridge.py` `TestHandleCallToolFastFail::test_disconnected_returns_structured_error_under_100ms` and `::test_disconnected_with_no_error_recorded`; `tools/mcp_bridge/README.md` § "Resilience behavior"
VOLATILE: **`<100ms` reproduced as a live assertion. The "former 5-second opaque wait" is UNSOURCED** — it appears twice as prose (README § Resilience behavior, and `_handle_call_tool`'s docstring "no 5s wait") and nowhere as a value: no constant, no test, and `git log -S "sleep(5" -- tools/mcp_bridge/bridge.py` returns no commit that removed one. So the *improvement* is verified and the *baseline* it improves on is folklore. Do not quote "5s → <100ms" as a measured 50×.
TENSION: Two corrections to the old phrasing. (1) `"(none recorded)"` / `"(never)"` are **inline string literals, not constants** — nothing else can reference them, nothing pins their spelling, and the no-None test would pass on any non-empty substitute. They *should* be shared, because `discodon/web/mcp/eval/classifier.py`'s rendering uses the same `(none recorded)` string for an unrelated purpose, so the phrase is already a de facto convention nothing enforces. (2) The payload is **two surfaces with different conventions**: the human-readable string substitutes placeholders, while `bridge_tools._health_payload` (the `bridge_health` JSON) emits `"last_error": upstream.last_error` raw — `None` → JSON `null`. So "no raw Python `None` leaks" is true of the surface the test reads and **false of the sibling**, which is incidentally the surface the stale-session symptom above is described against.

**RULE:** Distinguish "the process is not listening" from "the session is not established" — separate probe, separate message, separate remedy — and make the sticky bad state self-clearing.
FIRE-SITE: You are writing one "not available" message for every way your upstream can be absent.
LAYER: L3
KIND: diagnostic
EVIDENCE: designed-untested as a *diagnosis* (no incident recorded for the confusion it prevents); the probe itself is well covered including the recovery transition. `async def _probe_port(host, port) -> bool: """Return True if host:port accepts a TCP connection within 1s."""` with `asyncio.wait_for(asyncio.open_connection(host, port), timeout=1.0)`. The two remedies genuinely differ: "Discodon is not running (nothing listening on {host}:{port}). Start the app with `python discodon.py`, then reconnect MCP." versus the session-level "Bridge upstream not connected." plus a state block — i.e. *start the app* versus *wait ~3s, the bridge reconnects itself*.
PROVENANCE: `tools/mcp_bridge/bridge.py` `_probe_port` and its two callers, `_handle_call_tool()` and the `list_tools()` registration inside `main()`; pinned by `tests/unit/mcp_bridge/test_bridge.py` `TestProbePort::test_returns_true_for_listening`, `::test_returns_false_when_nothing_listening`, `TestHandleCallToolFastFail::test_app_down_path_returns_existing_message`, `::test_app_down_clears_when_port_recovers`; operator-facing as separate rows with separate fixes at `documentation/MCP_SERVER.md` § Troubleshooting
VOLATILE: **1s** reproduced (`timeout=1.0`, the only timeout in the function).
TENSION: **"Re-probed each call" is true only in the not-listening state.** The probe is gated on `if upstream._app_down:` — a call arriving while `_app_down` is False never probes at all and falls straight to the `not upstream.connected` branch (plus one probe in `list_tools()` when `_ready` is unset). The accurate statement is *re-probed on every call while the process is believed down, so the down-state clears itself on the first call after recovery* — which is what `test_app_down_clears_when_port_recovers` pins, and it is a **better** rule than the one stated, because the point is that a sticky bad state must be self-clearing. There is also a **third** state completing the taxonomy, which the old capture missed: `list_tools()` serves the cached last-known list when the port is down ("Tools list intentionally preserved as last-known cache, so Claude Code retains tool visibility during brief restarts") rather than reporting an empty set. Three states — process absent, session absent, session present — with a deliberately different degradation for each.

**RULE:** A stateful HTTP session never ends on its own — ship an idle timeout and never default it off; and when the gauge climbs, fix the LEAK, not the metric.
FIRE-SITE: You are choosing `stateless_http=False`, or watching a session gauge climb and reaching for a sweeper.
LAYER: L3
KIND: constraint
EVIDENCE: measured against production, with the instrument named. "Measured against production on **2026-08-05**: **1,153** live sessions accumulated at roughly **one per three seconds**, **~154 KiB** each, and **zero terminations in six hours**." At the config: "**0 disables reaping, which is unbounded growth**: a streamable-HTTP session ends only on an explicit client DELETE or on this timeout, and a client that drops its connection without one leaves the session resident forever. Left unset, sessions reached 1,153 live on 2026-08-05 and the process was **OOMKilled**." The diagnosis, which is the transferable half: the teardown was **correct and simply unreachable** — "The session-scoped teardown that releases those is correct and always has been; without a timeout there was simply no path that ever reached it." And the trap: "The build plan's own premise ('the caller is inside a teardown that is evidently not reached') pointed at a broken teardown, whose natural repair is a sweeper over the leaked dict — **which would have flattened the gauge while every leaked session, transport and task stayed resident.**"
PROVENANCE: `discodon/web/mcp/server.py` `apply_session_idle_timeout()` (docstring carries every number); `discodon/config/sections/mcp.py` `McpConfig.session_idle_timeout_s` (default 1800.0, `ge=0.0`, `reload="restart"`, plus a runtime `log.warning("MCP session idle timeout disabled — sessions will accumulate without bound")` when set to 0); `.prawduct/learnings-detail.md` § "Lifecycle & resource leaks (demoted from learnings.md 2026-08-05)"; operator row at `documentation/MCP_SERVER.md` § Troubleshooting; the anti-sweeper warning now lives as a comment in `discodon/web/mcp/channel_bridge.py`
VOLATILE: every digit reproduced from two independent records that agree — 1,153 ✓, ~1 per 3 s ✓, ~154 KiB ✓, zero terminations in six hours ✓, 2026-08-05 ✓, OOMKilled ✓ (learnings adds "22 seconds before an OOMKill"), 1800.0 ✓, 0-documented-as-unbounded ✓. **The best-evidenced rule in the corpus.**
TENSION: Two things the old capture dropped. (1) **Why the tests did not catch it**: "two unit tests asserted register/unregister symmetry and passed throughout — **because each test ends the session itself**." The test supplied the termination production never does. (2) **The shipped fix is unverified by observation and known to be so.** It sets a FastMCP internal by name (`manager.session_idle_timeout = timeout_s`), and backlog **[MCP-73BN]** holds a dependabot bump because of it: "a renamed attribute ... is a plain attribute assignment that succeeds, and it then logs *'MCP session idle timeout set to 1800s'* anyway. **The success log is not evidence of success.**" Confirming it by observation requires quieting every client for >1800 s, which is why **[OBS-TSSH]** travels with it. So: a measured incident, a shipped fix, and a protection that cannot currently be verified.

**RULE:** Choose stateful only if you push server-initiated notifications — and know that this repo chose it for one feature and learned the price afterwards, never having compared the alternative.
FIRE-SITE: You are picking `stateless_http` and it looks like a transport detail.
LAYER: L3
KIND: decision-point
EVIDENCE: designed — a constraint recorded, never a comparison performed. "It uses Streamable HTTP transport in **stateful** mode (`stateless_http=False`) because stateful sessions are required for the channel bridge's persistent SSE streams." And the link to the cost, made by the tree itself: "Persisting across requests is what makes an idle timeout load-bearing rather than tidy: a stateful session outlives the request that made it and is released only by an explicit client `DELETE` or by `apply_session_idle_timeout`. **See that function for what the absence of one cost.**"
PROVENANCE: `discodon/web/mcp/server.py` module docstring and `create_mcp_app()` (the `mcp.http_app(..., stateless_http=False, ...)` call and the comment above its return)
VOLATILE: none.
TENSION: **The old capture reads this as a decision framework; the tree records a constraint already taken with no alternative ever weighed** — no document compares stateless against stateful, no rejected-option note, no cost estimate made before the OOMKill. The honest form is weaker but more useful: *this repo has one reason for stateful, and it learned the price 1,153 sessions later.* The sequence is the lesson. And ripping statefulness out is not a config flip — the same factory patches the FastMCP low-level server to capture each session's write stream and declares an experimental `claude/channel` capability during the initialise handshake, so the SSE push is wired through session identity rather than bolted beside it.

**RULE:** A keepalive interval longer than your graceful-shutdown budget guarantees a cancelled-mid-stream error at EVERY shutdown — signal the stream to end rather than waiting for the keepalive to expire.
FIRE-SITE: You are setting an SSE keepalive, or dismissing "ASGI callable returned without completing response" as shutdown noise.
LAYER: L3
KIND: constraint
EVIDENCE: incident (a dated audit) — "Without this signal, SSE generators block on `queue.get()` with a 30s keepalive timeout and exceed uvicorn's 25s `timeout_graceful_shutdown` budget — uvicorn then cancels them mid-stream, producing the noisy 'Cancel N running task(s)' + 'ASGI callable returned without completing response' pair." The transport-level twin: "Stash the StreamableHTTPASGIApp so `WebService.drain()` can cancel its session manager's task group BEFORE uvicorn's graceful-shutdown timer starts waiting on long-poll requests ... (2026-05-04 audit)."
PROVENANCE: `discodon/web/mcp/channel_tool.py` `signal_shutdown()`; the `app.state.mcp_streamable_app` stash in `discodon/web/app.py` `create_app()`
VOLATILE: 30 s keepalive vs 25 s graceful-shutdown budget — both reproduced in the cited docstrings; `30 > 25` is the whole defect.
TENSION: Same arithmetic as the dispatch-budget rule above (an outer bound below an inner one) at the shutdown boundary instead — and it fires on **every** shutdown rather than on a maximal request, so it presents as log noise and is therefore learned as normal. The fix is two-layer: signal the application queues *and* cancel the transport's task group before the timer starts. The fallback is honest about degrading — a full queue drops the sentinel and "Worst case it falls back to the existing 30s keepalive path", i.e. the defect, by name. Absent from the old capture.

**RULE:** Treat a config bound of `0` or `1` as a correctness statement, not a range — document what the boundary value does and refuse the one that hangs silently.
FIRE-SITE: You are writing `ge=0` on a concurrency or timeout field.
LAYER: L3
KIND: constraint
EVIDENCE: designed, reasoned from mechanism — "Bounds are correctness, not taste. `0` would construct a semaphore no job can ever acquire — **every eval job would hang forever with no error raised and no log line** — so the floor is 1, which is the meaningful 'no concurrency' setting. The ceiling of 16 is 8× the default ... If a latency curve has not bent by 16, the finding is that the loop is not the bottleneck — the answer is never a larger number here." And a refusal rather than a clamp: `raise ValueError(f"max_concurrency must be at least 1, got {max_concurrency}")`, because "a silent clamp to 1 would" hide the caller's mistake.
PROVENANCE: `discodon/config/sections/eval.py` `EvalConfig.max_concurrent_jobs`; `discodon/eval/classifier.py` `run_classifier_eval`'s `max_concurrency` guard; the contrasting case at `discodon/config/sections/mcp.py` `McpConfig.session_idle_timeout_s` (`ge=0.0`, where 0 is meaningful **and** dangerous)
VOLATILE: `max_concurrent_jobs` default 2 (`ge=1, le=16`); `classifier_concurrency` default 8 (`ge=1, le=32`); `session_idle_timeout_s` `ge=0.0` with 0 = disabled.
TENSION: **The sharp end is the deliberate asymmetry between neighbouring fields**: concurrency floors at 1 because 0 hangs silently, while the idle timeout *permits* 0 and documents it as unbounded growth plus a runtime warning. Same boundary value, opposite decisions, each justified from what the mechanism does at that value — a blanket "validate your ranges" rule loses exactly that. Note also `reload="restart"` is chosen honestly rather than worked around: "`asyncio.Semaphore` cannot be resized after construction ... That is the honest contract, not a limitation being worked around." Absent from the old capture.

**RULE:** Changing how many things run at once re-scopes every measurement taken afterwards — gate the concurrency knob on your aggregation being able to separate contended runs from clean ones.
FIRE-SITE: You are raising a concurrency limit on a system whose latency numbers someone reads.
LAYER: L0
KIND: constraint
EVIDENCE: owner ruling, reasoned — "**Do not raise this until eval latency aggregation honours the `execution_mode` covariate.** Running jobs concurrently makes every latency observation taken afterwards a mixture of contended and clean measurements that nothing downstream can separate — **the corpus is quietly spoiled rather than visibly broken.** Owner ruling; the operator-facing form of it is in `documentation/DEPLOYING.md`."
PROVENANCE: `discodon/config/sections/eval.py` `EvalConfig.max_concurrent_jobs` (the ruling in its description)
VOLATILE: none.
TENSION: **The strongest unclaimed rule in the source.** Every other concurrency rule here is about liveness — will the service stay up, will the probes answer. This one is about **measurement validity**, and its failure mode is the one nobody notices: nothing breaks, nothing logs, and the corpus is silently a mixture. It is also a genuine cross-cutting constraint filed where nobody looks for one: a performance knob gated on an *analysis* capability. Absent from the old capture.

**RULE:** Cap and truncate every stored diagnostic field, redact BEFORE you truncate, and carry a flag saying you truncated.
FIRE-SITE: You are persisting a request body, an error detail or a model response into a log or a row.
LAYER: L3
KIND: pattern
EVIDENCE: designed — `_MAX_ENTRIES = 200`; `_MAX_DETAIL_BYTES = 8192  # 8KB per detail field`; `detail_truncated: bool = False  # True if either detail field was truncated`. The ordering constraint is explicit: redaction runs "before the 8 KB truncation in `_truncate_detail`", with the note that a redacted body "still survives the 8KB cap correctly". The cap is justified from what the field is FOR: "Cap on stored `failure_detail`. Reasoning preambles run long and the point of keeping the text is triage, which the first few hundred characters settle (`THINKING PROCESS:` is legible in the first twenty)."
PROVENANCE: `discodon/web/mcp/request_log.py` `_MAX_ENTRIES`, `_MAX_DETAIL_BYTES`, `_truncate_detail()`, the `detail_truncated` field, and the module docstring's ordering note; `discodon/eval/classifier.py` `_FAILURE_DETAIL_LIMIT` (500)
VOLATILE: 200 entries, 8192 bytes/field, 500 chars.
TENSION: Three rules bundled, and the middle one is the one people miss: **carry a `truncated` flag**, because otherwise a truncated payload is indistinguishable from a short one — the same class of defect as `(none recorded)` vs `None` above, and the same as the bare-ellipsis defect in § D. And **redact before you truncate**, or a secret can survive at the boundary and the redaction silently does nothing.

---
# G. Transport, sessions, startup, auth

**RULE:** On stdio, write NOTHING to stdout but JSON-RPC — and put a test behind it, because compliance held by one `basicConfig` line is a convention, not a guard.
FIRE-SITE: You are adding a `print()` for debugging in a stdio server, or reviewing one.
LAYER: L3
KIND: constraint
EVIDENCE: designed-untested — the code complies and the rule is nowhere stated. `logging.basicConfig(level=logging.INFO, stream=sys.stderr)` is the whole of the tree's commitment; the fatal-config path writes to stderr explicitly (`sys.stderr.write(f"[bridge] {profile.token_env} not found in {ENV_PATH}. ...")`). Verified: `grep -rn "print(\|sys\.stdout\|stdout" tools/mcp_bridge/` → **no matches** (the only "print" substring in the package is `fingerprint` inside `_tools_signature`'s docstring). But `grep -rni "stdout" documentation/ tools/mcp_bridge/ .prawduct/change-log.md` finds stdout discipline documented only for *other* subsystems — `tools/testlock.py` ("Print a wrapper message to stderr so it never pollutes the command's stdout"), `documentation/TESTING.md`, `documentation/MUSIC.md` / `RADIO.md` for Liquidsoap — **never for the MCP bridge.**
PROVENANCE: `tools/mcp_bridge/bridge.py` module-level `logging.basicConfig(...)` (~line 68) and `current_runtime_config` (the `sys.stderr.write` path)
VOLATILE: none.
TENSION: **Splits into two**: the code complies, and nothing would go red if a future edit added a `print()` or flipped the stream. The contrast the repo draws elsewhere is the finding — `testlock.py` has the sentence, the bridge does not. The rule also flattens *who* the discipline protects: stderr here is not merely "not stdout", it is the bridge's **only** diagnostic channel, since the bridge is spawned by Claude Code and its log is the operator's sole window.

**RULE:** A stdio server must recover from its own crash by REPLACING its process, not by re-entering in place — carry the restart history in an environment variable, because `execv` preserves the environment and resets every Python structure.
FIRE-SITE: You are deciding whether an unhandled exception in a stdio MCP server can be left to the host.
LAYER: L4
KIND: pattern
EVIDENCE: measured(third-party — Anthropic, via this repo's own unverified assertion) for the premise; measured for the mechanism. `os.execv(sys.executable, [sys.executable, "-m", "tools.mcp_bridge.bridge"])`, with `RESTART_HISTORY_ENV = "_DD_MCP_BRIDGE_RESTART_HISTORY"`, `RESTART_WINDOW_SECONDS = 60`, `RESTART_MAX = 5`. The env-var rationale, verbatim: "History lives in `RESTART_HISTORY_ENV` (an environment variable) so it survives `os.execv` — **execv preserves the environment but resets every Python-side data structure.**" The disposition is in the tree: "([anthropics/claude-code#15904](...), **closed as not planned** — the bridge is permanent)".
PROVENANCE: `tools/mcp_bridge/bridge.py` `_run_with_restart`, `_execv_self`, `_record_restart_and_within_budget`, and the `RESTART_*` constants; `documentation/MCP_SERVER.md` § "Connection Architecture" (the "closed as not planned" disposition and "the bridge is permanent", which also appears in `bridge.py`'s module docstring); `tools/mcp_bridge/README.md` § "Resilience behavior"; pinned by `tests/unit/mcp_bridge/test_bridge.py` `TestRunWithRestart::test_sixth_crash_within_window_skips_execv_and_exits`, `::test_first_crash_within_budget_records_one_entry`, `::test_old_restart_history_pruned`, `::test_record_returns_false_at_cap`
VOLATILE: 5 / 60s / the env-var name all reproduced and pinned. **`claude-code#15904` and its "closed as not planned" disposition are this repo's own assertion about an upstream issue** — no fetched artifact, no date of checking. Treat as unverified-third-party, not as measured.
TENSION: **"Survive its own crashes IN-PROCESS" is exactly backwards** — `_run_with_restart`'s own docstring says "Recovery is **process-replacement, not in-process re-entry**", which is *why* the history must live in the environment. The recovery is also bounded to `except Exception`: `KeyboardInterrupt` and `SystemExit` deliberately propagate, so "survive its own crashes" is false for the `SystemExit` that `current_runtime_config` raises on a missing token — which is the bug the diagnostic-safety rule below had to work around. **And #15904 is cited for two DIFFERENT upstream behaviours**; see the drift report.

**RULE:** A diagnostic command of last resort must catch `SystemExit` from its own config resolver, not just `Exception` — the operator most likely to call it is the one whose config is broken.
FIRE-SITE: You are wrapping a health/status command's config load in `except Exception`.
LAYER: L3
KIND: constraint
EVIDENCE: incident — "`current_runtime_config` documents that it *exits the process* when the profile's token env var is unset or unexpanded, and **`SystemExit` derives from `BaseException`, so `except Exception` misses exactly the failure this function names first.** An operator whose token env var is missing is the operator most likely to be calling `bridge_health` — and until this was fixed the call took the bridge down instead of answering." It dragged a second defect out with it: "The same gap made `test_connection_pending_is_absent_once_the_session_is_up` read the developer's real `.env` and fail on any clone without one."
PROVENANCE: `tools/mcp_bridge/bridge_tools.py` `_current_runtime_config_safe`; the `Raises: SystemExit` clause on `tools/mcp_bridge/bridge.py` `current_runtime_config`; found while fixing the token-label defect (change-log v2.3.41, § "Found while fixing it")
VOLATILE: none.
TENSION: Closes a loop with the `${VAR}` rule below — that guard's chosen failure posture (`sys.exit(1)`) is precisely what made the diagnostic un-callable. **The two are one mechanism seen from each end**, and neither is visible from the other's file. Absent from the old capture.

**RULE:** Never present an unexpanded `${VAR}` as a credential — detect it explicitly at both ends, and prefer removing the dependency on host expansion altogether.
FIRE-SITE: You are documenting `"env": {"TOKEN": "${MY_TOKEN}"}` in an install snippet.
LAYER: L4
KIND: constraint
EVIDENCE: designed, one side tested. Exactly two `startswith("${")` sites, one per end. Bridge: `if not token or token.startswith("${"): sys.stderr.write(f"[bridge] {profile.token_env} not found in {ENV_PATH}. Generate one in the Discodon web UI (/mcp page) and add it to .env.\n"); sys.exit(1)`. Server: `if not token or token.startswith("${"): return _TokenValidationResult("DD_MCP_TOKEN is not set in your shell environment. The .mcp.json references ${DD_MCP_TOKEN} but it was not resolved. ...")`. And the stronger move: "Reading `.env` directly means the bridge doesn't depend on Claude Code's launching shell environment — **no direnv, no `${VAR}` expansion in `.mcp.json`.**"
PROVENANCE: `tools/mcp_bridge/bridge.py` `current_runtime_config`; `discodon/web/mcp/auth.py` `_validate_bearer`; design statement at `documentation/MCP_SERVER.md` § "How It Works" and § Prerequisites ("No direnv setup is required for MCP")
VOLATILE: none.
TENSION: **The tree went further than detection — it removed the dependency** (`load_dotenv(ENV_PATH, override=True)`), so the bridge-side `${` check is now a guard against a stale `.env` value rather than against host non-expansion. The two ends also differ in **failure posture**, which the old capture flattened: the bridge **exits the process**, the server returns a 401 body. That asymmetry has already bitten once (see the rule above), and the server-side remedy string is now stale advice — see the drift report.

**RULE:** Make a 401 say WHICH 401 it is — and pin your unauthenticated surface, because the only other way to reason about it is to read it.
FIRE-SITE: You are returning `None` on any non-200 from a probe, or adding a route that a bearer token is supposed to reach.
LAYER: L3
KIND: diagnostic
EVIDENCE: incident, with a recorded wrong disposition and its reversal. The 2026-06-17 close: "`bridge_health.token_label` was investigated and left as-is (**not a code defect** — the bridge already fetches it via `/api/v1/mcp/token/whoami`; `null` = unlabeled token; operator remedy is to label the token)." The 2026-08-14 reversal: "**This supersedes the note closing the 2026-06-17 voice-failure entry** ... **It was a code defect; a silent `None` is what made the wrong conclusion the reasonable one.**" The collapse: "'offline', 'bad token' and 'that route is not reachable with a bearer here' were one indistinguishable answer." The root cause: "`AuthMiddleware` enforces a session cookie on every `/api/v1/` path outside `_PUBLIC_PATHS` / `_PUBLIC_PREFIXES`. The route was in neither, so every bearer call got the middleware's generic `401 {"error": "Authentication required"}` **before the handler ran**" — and "The handler was dead code and its docstring described auth it did not have."
PROVENANCE: `tools/mcp_bridge/bridge_tools.py` `_fetch_token_label` (returns `(label, reason)`), surfaced via `_health_payload`'s `token_label_error`; the incident at `.prawduct/change-log-archive/2026-08.md` § "2026-08-14: the token-identity probe was never reachable, and nothing said so" (scope `mcp-token-whoami-bearer`, release v2.3.41); the superseded disposition at `.prawduct/change-log-archive.md`, closing sentence of § "2026-06-17: Operator alerts + introspection for terminal voice failures"; discovery at `.prawduct/artifacts/eval-smoke-2026-08-14-v2.3.40.md` finding E; the surface now pinned by `TestPublicAuthSurface`; operator-facing at `documentation/MCP_SERVER.md` § `bridge_health` — MCP Bridge State
VOLATILE: **2026-06-17** reproduced as the change-log heading date; fix dated 2026-08-14, v2.3.41.
TENSION: **The rule's title names the symptom; the finding is a level deeper and has TWO legs, only one of which the old capture carried.** Leg 1 (carried): the consumer collapsed non-200 into `None`. Leg 2 (missing): **the unauthenticated surface was unpinned** — `_PUBLIC_PATHS`/`_PUBLIC_PREFIXES` had no test, so "the only way to reason about the unauthenticated surface was to read it", and the fix pins them verbatim. The two rejected alternatives are load-bearing and were also lost: moving the route would break the bridge's URL, and teaching the middleware to defer to any `Authorization` header "would have let a bearer skip cookie auth on **every** admin route, including the ones that do no bearer check of their own." Finally, the mechanism is not what the title suggests: `_fetch_token_label` distinguishes the two 401s by **quoting the server's own body** (`detail = response.text.strip()[:200]`), not by status code. And prefer the tree's phrasing to the old capture's paraphrase — "a silent `None` is what made the wrong conclusion the reasonable one" excuses the reasoner rather than merely indicting the sentinel.

**RULE:** Enumerate every outcome of an HTTP probe as a distinct reason — a 200 carrying the wrong body included.
FIRE-SITE: You are writing `if response.status_code != 200: return None`.
LAYER: L3
KIND: pattern
EVIDENCE: measured — the contract is "the `(label, reason)` contract across **200 / session-401 / bearer-401 / 404 / transport failure / unparseable body / 200-without-label / `SystemExit`**", eight cases. The 200-with-non-JSON case: `monkeypatch.setattr(bridge_tools.httpx, "AsyncClient", _fake_client(_FakeResponse(200, text="<html>")))`, then `assert label is None; assert "unparseable JSON" in error`.
PROVENANCE: `tools/mcp_bridge/bridge_tools.py` `_fetch_token_label`; pinned by `tests/unit/mcp_bridge/test_bridge_tools.py` `TestFetchTokenLabel::test_unparseable_body_is_reported_not_swallowed` and its seven siblings; the eight-case contract stated in the v2.3.41 change-log entry
VOLATILE: none.
TENSION: **The old capture read a motive into a fixture.** It framed this as "treat HTTP 200 as 'a response arrived', not 'it worked' — pinned with a 200 whose body is `"<html>"` (proxy/login interception)". The test exists and the body is `"<html>"`, but **nothing in the tree mentions a proxy, a captive portal or login interception** — not the test name, not the test body, not `_fetch_token_label`'s docstring, not the change-log. The test's stated subject is JSON parseability and the code path it pins is `except ValueError` around `response.json()`. `"<html>"` is the cheapest non-JSON string a test author reaches for. The real design intent is the eight-case exhaustive-outcome contract, which is a **stronger** rule than the one inferred, so keep it and drop the proxy story.

**RULE:** Log the session id on every request, and read it off the RESPONSE for `initialize`, which carries none inbound because it is assigned one.
FIRE-SITE: You are extracting `Mcp-Session-Id` from request headers and wondering why `initialize` has none.
LAYER: L3
KIND: diagnostic
EVIDENCE: incident (the rule is written as the retroactive-proof argument), mechanism unit-tested. The field's docstring: "the identifier the transport's own lifecycle lines carry ('Session <id> idle timeout', 'Session <id> crashed', 'Terminating session: <id>'). Without it, a session ending has at least three indistinguishable causes ... `None` only for a request that carries no session: an unauthenticated probe, or **the `initialize` that is ASSIGNED one, which is read off the response instead.**" The mechanism reads the request header before dispatch, then inside `logging_send`, on `http.response.start`, `if session_id is None: session_id = _header_value(message.get("headers") or (), _SESSION_ID_HEADER)`.
PROVENANCE: `discodon/web/mcp/request_log.py` `McpRequestEntry.session_id` (its `#:` docstring carries the whole rule) and `_SESSION_ID_HEADER`, extracted in `McpRequestLoggingMiddleware`'s `logging_send` closure; pinned by four cases in `tests/unit/web/test_mcp_request_log.py` — request-header only, response-header only (`b"assigned-on-init"`), and the both-present case asserting request wins (`b"from-request"` over `b"from-response"`)
VOLATILE: none.
TENSION: **The two halves have different owners and the old phrasing fused them.** "Log the session id per request" is this module. "**Name the CAUSE when a session ends" is NOT implemented here** — the lifecycle lines quoted in the docstring are the *transport's* (FastMCP/`mcp`), which this repo does not author; discodon's contribution is making those lines *joinable* to a request stream after the fact ("the proof is retroactive and free"). So the rule overstates ownership: discodon made the cause **attributable**, it did not make the transport **name** it. Note also the `None` semantics are three-way, not two: no session at all, an unauthenticated probe, or `initialize` — and only the third is recoverable from the response.

**RULE:** Do not require interactive OAuth — an unattended agent cannot complete a browser redirect.
FIRE-SITE: You are choosing your server's credential flow.
LAYER: L3
KIND: constraint
EVIDENCE: designed-untested — the rule is **enacted and never argued**. The whole auth path is `secrets.token_urlsafe(48)` minted in the web UI, SHA-256-hashed for storage, pasted into `.env`, presented as `Authorization: Bearer`. `grep -rni "oauth" discodon/web/mcp/ tools/mcp_bridge/` → **zero hits**; the only OAuth in the repo is a Discord bot-invite and a GitHub web login, both unrelated to MCP.
PROVENANCE: UNADDRESSED — the tree enacts bearer-token-only auth and never states, argues, or rejects the alternative, so there is no sentence to cite. Nearest positive evidence for what was built instead: `documentation/MCP_SERVER.md` § Prerequisites + § "1. Generate a Token" + § "2. Add to `.env`"; `discodon/web/mcp/token.py` `generate_mcp_token`; `discodon/web/mcp/auth.py` `McpBearerAuthMiddleware`
VOLATILE: the 48-byte token length.
TENSION: **Honest status: this is a correct DESCRIPTION of what was built and a fabrication as a rule this repo holds.** Nothing states it, weighs OAuth against bearer, or records a rejection. Its warrant is the *shape* of the artifact — a copy-once token an operator pastes into a file a headless process reads — not any sentence in the tree. There IS one place the tree touches the question and it points the other way: `discodon/web/mcp/server.py` `find_streamable_endpoint`'s docstring anticipates adopting FastMCP-native auth — "Switching to FastMCP-native `auth=` wraps it in `RequireAuthMiddleware`, the `isinstance` stops matching, and both callers degrade — so that change has to teach this walk to recurse one wrapper layer" — i.e. a live migration hazard recorded against the auth choice, not a principled rejection of interactive flows.

**RULE:** Isolate per-SESSION state — and then carry the PRINCIPAL into every fan-out, because a server-initiated notification with no user predicate is a cross-tenant delivery.
FIRE-SITE: You are broadcasting a server-initiated notification to connected sessions.
LAYER: L3
KIND: constraint
EVIDENCE: measured. Per-session state exists and is correct: `self._write_streams: dict[int, ObjectSendStream] = {}  # id(stream) → stream`, registered and unregistered symmetrically around the patched `low_level.run`. Per-request principal exists: `request.scope["mcp_user_id"] = result.record.user_id`. **But the fan-out is principal-blind**: `push_notification` iterates `for stream_id, write_stream in self._write_streams.items(): await write_stream.send(message)` with no user predicate, and returns "the number of sessions notified." `grep -rn "mcp_user_id\|mcp_token_label"` over the tree finds exactly **one** consumer — `request_log.py`, i.e. **audit only**. No authorization, no scoping, no routing reads it.
PROVENANCE: `discodon/web/mcp/channel_bridge.py` `ChannelBridge` (per-session write-stream capture), `patch_mcp_server_for_channel`, and `ChannelBridge.push_notification`; `discodon/web/mcp/auth.py` `McpBearerAuthMiddleware.dispatch`; `discodon/web/mcp/user_tokens.py` `UserTokenStore` (process-wide, one `threading.Lock`)
VOLATILE: none.
TENSION: **Splits, and the second half is CONTRADICTED.** (a) Per-session state IS isolated — keyed on `id(write_stream)`, torn down symmetrically. (b) Per-PRINCIPAL state is **not** — a web-UI channel message goes to *every* connected MCP session regardless of whose token opened it. The tree knows the singleton is an assumption and says so on a *different* axis: "#233 (2026-04-30): single-instance assumption is correct today (one claude.channel surface per process). **Re-evaluate when adding a second message SOURCE (e.g., Slack)**" — a second *sender*, not a second *principal*. So the repo ships multi-principal token management (`list_for_user`, `revoke_all(user_id)`, "Each user generates their own tokens") over a single-principal notification path, and the recorded trigger will not fire when the real condition arrives. **This is the most substantive gap found** and is owed back as a report.

**RULE:** Commit the credential's ADDRESS, never the credential — and make the environment-switch confirmation case-sensitive.
FIRE-SITE: You are adding a second deployment target to a client config.
LAYER: L4
KIND: pattern
EVIDENCE: designed, tested. `profiles.toml` commits `token_env = "DD_MCP_LOCAL_TOKEN"` / `"DD_MCP_PROD_TOKEN"` and never a value; `.active-profile` is gitignored state written atomically — "Writes are atomic — a crash mid-write leaves the previous valid file intact, never a half-written truncated file" (`mkstemp` + `os.replace` with orphan cleanup). The guard: switching to any non-`local` profile requires `confirm == profile.upper()` **case-sensitively** — "typing `'prod'` lowercase or `'Prod'` is the kind of slip we want to catch."
PROVENANCE: `tools/mcp_bridge/profiles.py` `Profile` (`token_env: str`) and `tools/mcp_bridge/profiles.toml`; `tools/mcp_bridge/state.py` `write_active_profile`; `tools/mcp_bridge/README.md` § Layout; the confirm guard at `tools/mcp_bridge/bridge_tools.py`
VOLATILE: the two profile names.
TENSION: The composition is the rule — committed env-var NAME + gitignored pointer + uppercase echo — which makes prod-vs-local a one-tool-call operation that is still hard to do by accident. Absent from the old capture.

**RULE:** Do not share one event between "reconnect the session" and "the environment changed" — a consumer that clears the event at the top of its loop will eat the other consumer's wake-up.
FIRE-SITE: You are reusing an `asyncio.Event` for a second kind of wake-up.
LAYER: L3
KIND: constraint
EVIDENCE: measured (both failure directions reasoned, both pinned). "`upstream_connection_manager` clears `RECONNECT_SIGNAL` at the top of every iteration, so a second waiter on the same event would race it and lose the wake-up roughly half the time." And the other direction: "`forward_call` fires the latter when it finds the upstream session dead, which says nothing about this stream and **would tear down a healthy one.**"
PROVENANCE: `tools/mcp_bridge/bridge_tools.py` `RECONNECT_SIGNAL` / `PROFILE_SWITCH_SIGNAL` (the `#:` comment on the latter); consumers at `tools/mcp_bridge/bridge.py` `sse_subscriber` and `upstream_connection_manager`; pinned by `TestSseRelayHonoursAProfileSwitch::test_a_switch_tears_the_stream_down_and_reconnects_on_the_new_profile` and its control `::test_a_dead_upstream_session_does_not_tear_down_a_healthy_relay`
VOLATILE: "roughly half the time" is an estimate, not a measurement.
TENSION: `sse_subscriber` carries the sharper sub-rule with a control test to match: "**The EVENT decides, not which task finished first** ... reading 'the switch task is done' as 'the profile switched' would reconnect on that with no switch behind it, in a loop with no delay to slow it down." Absent from the old capture.

**RULE:** Redact before you truncate in a request log, key redaction on FIELD-NAME substrings, and place the logging middleware outermost so it sees auth failures.
FIRE-SITE: You are adding request logging to an authenticated transport.
LAYER: L3
KIND: pattern
EVIDENCE: designed — order in the `finally`: `redacted_params = _redact_sensitive_values(params_json.encode("utf-8"))` then `request_params, req_trunc = _truncate_detail(redacted_params)`, on both the request and the response path. The middleware is deliberately outermost ("listed first in the MCP sub-app's `middleware=[...]` list, marked `# outermost`") and "captures every request — **including auth failures**".
PROVENANCE: `discodon/web/mcp/request_log.py` module docstring, `_REDACT_KEY_SUBSTRINGS`, `_redact_sensitive_values`, `_walk_and_redact`, applied in `McpRequestLoggingMiddleware`; ordering relative to auth set in `discodon/web/mcp/server.py` `create_mcp_app`
VOLATILE: the 12 substrings in `_REDACT_KEY_SUBSTRINGS`.
TENSION: The ordering is the non-obvious part — truncating first can split a token across the boundary and leave a prefix unredacted. And the outermost placement is exactly *why* it handles the requests most likely to carry a bad credential. See also the bare-`token` rule in § D, which is the hole this heuristic had to leave.

**RULE:** Do not set `follow_redirects=True` on a client carrying a static `Authorization` header without checking your HTTP library's cross-origin redirect behaviour.
FIRE-SITE: You are constructing an HTTP client for an MCP transport and enabling redirect following.
LAYER: L3
KIND: constraint
EVIDENCE: designed-untested, and **not closeable read-only**. Both MCP client constructions set `follow_redirects=True`, and they differ in WHERE the bearer sits: the connection manager puts it on the **client** (`httpx.AsyncClient(headers={"Authorization": f"Bearer {cfg.token}"}, timeout=httpx.Timeout(30.0, read=120.0), follow_redirects=True)`) so it rides every hop httpx follows; the SSE relay puts it on the **request** (`httpx.AsyncClient(timeout=None, follow_redirects=True)`).
PROVENANCE: `tools/mcp_bridge/bridge.py` `upstream_connection_manager` and `_relay_sse_stream`
VOLATILE: `httpx.Timeout(30.0, read=120.0)` and `timeout=None` reproduced; the pinned httpx version is in `uv.lock`.
TENSION: **Reported as an open question, not a finding — no vulnerability is being asserted.** Whether httpx strips `Authorization` on a cross-origin redirect is a library-version question that cannot be answered from this tree without running code, and the repo states nothing about it. What makes it worth a minute: the prod profile URL is an operator-controlled host, and the two clients differ in where the bearer sits, so they may already behave differently on the same redirect. Checking the pinned httpx either closes this immediately or turns it into a real item.
STATUS: provisional — unresolved; not closeable by reading, needs the pinned httpx checked

---

# H. What consumers do TO you

**RULE:** Expect one failed probe to disable you for every subsequent boot — a consumer that records `unreachable` may gate registration on an ALLOWLIST, so anything that is not exactly `active` never gets dialled again.
FIRE-SITE: You are reasoning about what a bad deploy window costs your server's registration.
LAYER: L0
KIND: constraint
EVIDENCE: measured — the skip exists and it is an allowlist, not a denylist: `if entry.get("verification_status") != "active": log.debug("MCP registry: skipping '%s' (status: %s)", name, entry.get("verification_status")); continue`, with the function's own docstring stating "Only registers entries with `verification_status == 'active'`." The write side fires on the **first** exception — there is no attempt counter and no retry before the write: `self._registry_callback(..., capabilities=[], verification_status="unreachable")`.
PROVENANCE: write side at `discodon/tools/mcp_bridge_tool.py` `McpBridgeTool.start` (the `except` arm); read/skip at `discodon/tools/mcp_registry.py` `_register_from_servers_dict` (shared by `register_mcp_servers_from_registry` and its async sibling); default at `save_registry_entry` (`verification_status: str = "active"`); human re-entry at `discodon/web/routes/mcp_registry.py` `register_server` and `discodon/web/mcp/system_tool.py` `_handle_mcp_registry_register`; pinned on both sides by `tests/unit/tools/test_mcp_bridge_tool.py::test_start_failure_marks_unreachable` and `tests/unit/tools/test_mcp_registry.py`
VOLATILE: none.
TENSION: Three corrections the old phrasing needs. (1) **The skip is not de-registration** — `if ToolCatalog.has(name): continue` runs FIRST, so a server already registered this process (from YAML, or an earlier `active` boot) stays live regardless of status; the skip governs *new* registration only. (2) "**Until a human re-probes" is right but the mechanism is a re-REGISTER**, not a re-probe: both entry points probe-then-save and neither passes `verification_status`, so it defaults to `"active"`; there is no "retry this one entry" affordance. (3) **YAML-curated servers are exempt** — `register_mcp_servers_from_config` never reads `verification_status`, so a `config/mcp_servers.yaml` entry is re-registered every boot no matter how often it fails. **The tree has two policies split by provenance** (`source: "yaml"` vs `"discovered"`/`"web"`), where a reader of the rule would expect one.

**RULE:** Expect only an IP-LITERAL private-address check on the registration surface — a hostname that resolves to a private address is not caught, and the connection path is not checked at all.
FIRE-SITE: You are relying on a consumer's SSRF guard, or writing one.
LAYER: L3
KIND: constraint
EVIDENCE: measured — the guard blocks a malformed URL (`except ValueError: return True`), the schemes `file` / `ftp` / `gopher`, the hostname `"localhost"` or empty, and — **only when the hostname parses as an IP literal** — `addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved`. The pass-through is explicit and commented: "hostname is a DNS name -- allow (we can't resolve here without blocking)", restated in the docstring as "DNS hostnames are allowed through since we can't resolve them without blocking."
PROVENANCE: `discodon/core/network.py` `is_private_url`; MCP call sites at `discodon/web/routes/mcp_registry.py` `register_server` (422, "URL must not point to a private/internal address") and `discodon/web/mcp/system_tool.py` `_handle_mcp_registry_register` (`INVALID_PARAMS`); pinned by `tests/unit/core/test_network.py`
VOLATILE: the blocked scheme list.
TENSION: **CONTRADICTED on its load-bearing word.** The old rule says "an HTTP URL **resolving to** a private address"; the code **never resolves**, so `http://internal.corp.example/mcp` pointing at 10.0.0.5 passes and only a bare IP literal is caught. This is a documented, deliberate limitation rather than an oversight, but the rule as phrased promises DNS-rebinding/alias protection the tree does not provide. Two further scope limits: (1) **the guard is on the registration surface only** — `is_private_url` has zero callers on the connection path (`McpBridgeTool.start` / `_try_reconnect` / `_build_transport` never consult it, nor does `register_mcp_servers_from_config`), so a private URL arriving by YAML, a pre-existing DB entry, or `from_config` on a per-persona attached tool is dialled unchecked; `config/mcp_servers.yaml`'s own commented example is `http://localhost:8765/mcp`, a URL this guard would reject, shipped as the documented happy path for the door the guard does not cover. (2) It also refuses `0.0.0.0` and bare `http:///path`, which "private address" does not describe.

**RULE:** Expect your whole connection lifecycle wrapped in a broad catch — and expect the error text to reach the MODEL while being dropped on the way to the human.
FIRE-SITE: You are deciding how much detail to put in a connect-time exception, and assuming an operator will see it.
LAYER: L0
KIND: constraint
EVIDENCE: measured. The catch is there four times over (`start`, `_try_reconnect`, `_refresh`, `act`), each with a `prawduct:ok-broad-except` waiver naming the transport-diversity reason, and the policy is stated in the module docstring. But the **operator** surfaces show `verification_status` / URL / capability-count / source and **never** the error string: `rows.append([name, entry.get("server_url", "?"), status, str(len(caps)), source])`. The registry document written by `save_registry_entry` has **no field for it** — its ten fields are `server_url, display_name, description, transport_type, auth_required, capabilities, source, first_seen, last_verified, verification_status`.
PROVENANCE: the catches at `discodon/tools/mcp_bridge_tool.py` `McpBridgeTool.start` / `_try_reconnect` / `_refresh` / `act`, policy in that module's docstring; the operator surfaces at `discodon/web/mcp/system_tool.py` `_handle_mcp_registry_list` and `web/src/pages/mcp/McpRegistryTab.tsx`; the persisted field set at `discodon/tools/mcp_registry.py` `save_registry_entry`; the contrast at `discodon/tools/mcp_bridge_tool.py` `McpBridgeTool.describe_state`
VOLATILE: none.
TENSION: **The old capture has the direction backwards, and the truth is stronger than the claim.** It said the connection error string "is the entire diagnostic surface an operator ever sees." In fact the string reaches the **persona prompt** and the **tool result** — where it is prose in a prompt and nothing acts on it — and is **discarded** on the way to the human, where it would be actionable. So "a startup failure gets you disabled, not diagnosed" is correct and understated: the diagnosis is generated and then thrown away at exactly the boundary where it mattered. The contrast inside the same repo is the argument: the bridge's own failure surface (`_disconnect_error_text`, `bridge_health`) carries `last_error` + `last_error_at` + `reconnect_attempts` deliberately, and the registry — its consumer-facing twin — carries none of it. Same class as the silent-`None` 401 one layer out: there a `None` collapsed three causes, here a persisted enum collapses every cause.

**RULE:** If your MCP server is a second adapter over an existing API, gate on FACT parity, not formatting parity — and derive both sides' answers from ONE fixture.
FIRE-SITE: You are adding an MCP surface beside a REST one and relying on "they both call the same service."
LAYER: L1
KIND: pattern
EVIDENCE: incident — "Until now, parity was a *convention* — both adapters call one shared service — and **a convention is what `EVL-U4KZ` slipped through**: `resolve_result_usage` acquired exactly one caller, so the same eval result read `usage: null` over REST and 'partial — derived at read' over MCP, **and nothing noticed because each surface looked complete from inside itself.**" The rule: "What it pins is that the facts reach both surfaces — not that they are formatted alike. REST returns JSON and MCP returns Markdown; demanding identical *renderings* would be a false contract, and the interesting failure is a fact present on one surface and absent from the other."
PROVENANCE: `tests/integration/eval/test_rest_mcp_parity.py` (module docstring); the incident at `.prawduct/backlog-archive.md` item **[EVL-U4KZ]**; closing work at `.prawduct/artifacts/archive/build-plan-eval-read.md`, Chunk 01 (the gate) and Chunk 01b (the defect)
VOLATILE: none.
TENSION: Three things the old capture left on the table, all of which make the rule more useful. (1) **The gate's construction is the transferable part**: "both answers are derived from **one** fixture, so the test cannot drift into asserting two hand-written expectations that happen to agree" — the failure mode a parity test most easily becomes. (2) The fixture avoids a second trap deliberately: `CAMPAIGN_ID = "camp-parity"` is "**Deliberately not UUID-shaped** ... MCP canonicalizes a UUID-shaped `campaign_id` and REST does not, so a real UUID here would compare the canonicalizer rather than whether both adapters forward the scope." (3) **The gate is known to be partial and the tree says where**: "`test_rest_mcp_parity.py` asserts cells are `isinstance(value, str)`. `delta_table` is the only compiled type whose rows carry pre-formatted strings, so **the gate passes on the one type that cannot exhibit the defect and never inspects the three that can.**" A rule that says "gate on fact parity" without that caveat sells a gate that green-lights the cases it cannot see.

---
# Meta. What the test surface reveals about what was foreseen

**RULE:** Simulate the misbehaviour classes you can ENUMERATE, and recognise that the ones you cannot enumerate are the ones that will cost you — content shapes are listable from the type system, timing and framing are not.
FIRE-SITE: You are writing a fixture server, or deciding whether your integration tests cover a hostile upstream.
LAYER: L1
KIND: stance
EVIDENCE: measured. The stdio fixture is **37 lines** (`wc -l tests/fixtures/mcp_time_server.py`) with **3 tools** (three `@server.tool()`: `get_time()` returning `datetime.now(UTC).isoformat()`, `echo(message: str)`, `add(a: int, b: int)`) — all synchronous, all returning `str`, no delays, no error paths, no non-text content, no schema mutation. It is exercised over real pipes: "Launches tests/fixtures/mcp_time_server.py as a child process and exercises McpBridgeTool over real stdio pipes and JSON-RPC protocol", marked `xdist_group("mcp_live_serial")` and `heavy` ("real MCP stdio subprocess is 6-10s per test"). **But adversarial CONTENT behaviour is simulated in advance, with mocks, in the same PR as the feature** — non-text blocks across `TestMcpBridgeToolAct::test_act_with_image_result`, `::test_act_with_resource_link_result`, and `TestExtractText::test_image_content` / `::test_resource_link` / `::test_mixed_content` / `::test_empty_content`, built on helpers constructing `mcp_types.ImageContent(type="image", data="base64data", mimeType=...)` and `mcp_types.ResourceLink(...)`; the same class on the bridge side in `TestUpstreamStateForwardCall::test_forward_image_content_passes_through` / `::test_forward_embedded_resource_passes_through` / `::test_forward_structured_content_passes_through`; oversized descriptions in `TestMcpBridgeToolDescribe::test_describe_truncates_long_descriptions`; and arbitrary far-side exception types in `test_call_failure_self_heal_works_for_any_exception_type`, which loops `for exc in (ConnectionError("boom"), TimeoutError("slow"), ValueError("bad"))`. Timing: `git log -S "test_forward_embedded_resource_passes_through"` → `2e12e2786 MCP Bridge Maturation (MCB-1..MCB-3)` — the PR that built the mechanism, i.e. written **with** the code, not after an incident. **What is genuinely not simulated anywhere: a SLOW server, a HANGING server, an OVERSIZED response body, and a MALFORMED JSON-RPC frame.** `grep -rn "asyncio.sleep\|TimeoutError\|asyncio.wait_for"` over the MCP test tree finds sleeps only in the bridge's own profile-switch/reconnect timing tests, never as a stand-in for a slow upstream.
PROVENANCE: `tests/fixtures/mcp_time_server.py` (and its only consumer, `tests/integration/test_mcp_live.py` `_SERVER_SCRIPT`); the content-shape mocks in `tests/unit/tools/test_mcp_bridge_tool.py` and `tests/unit/mcp_bridge/test_bridge.py`; the in-process `FastMCP` servers built inline in `TestMcpBridgeToolIntegration` and `tests/integration/test_mcp_e2e.py`
VOLATILE: 37 lines and 3 tools both reproduced exactly.
TENSION: **The old capture's second half is CONTRADICTED.** It claimed "Every adversarial server behaviour in that repo was discovered in production and then pinned with a mock, never simulated in advance." Content-shape misbehaviour *was* simulated in advance, in the feature's own PR. The error was scoping the claim to the **fixture** when the repo's simulation lives in **mocks**, and the fixture is only one of three simulation surfaces. The corrected finding is sharper than the original because its boundary is principled rather than accidental: **content shapes are enumerable from `mcp.types`, so they got fixtures; timing and framing are not enumerable, so they got none — and every incident in § E is a timing incident.** That correlation is the real lesson, and it survives the correction intact.

---

# Constants inventory

Every figure here is cited to the symbol that defines it. A figure with no defining symbol is marked
**UNSOURCED** and must not be quoted as measured.

## The consumer (`discodon/tools/mcp_bridge_tool.py`, `discodon/tools/mcp_registry.py`)

| Value | Figure | Defining symbol |
|---|---|---|
| Max tools per server | **20** | `DEFAULT_MAX_TOOLS`; also `max_tools` defaults at three sites in `mcp_registry.py`, one of which (`_register_from_servers_dict`) **hardcodes 20 and ignores any entry value** |
| Description clip (prompt roster only) | **120** → `[:117] + "..."` | inline literals in `McpBridgeTool.describe_state` — unnamed, untested |
| Reconnect attempts per call | **1** | `McpBridgeTool.act` calls `_try_reconnect()` once |
| Outbound call timeout | **none** | `grep -n "timeout" discodon/tools/mcp_bridge_tool.py` → **zero hits in 617 lines**; filed open as **[LLM-ZB4L]** |
| Display id truncation | **8** | `formatters.truncate_id(id_str, length=8)` |
| Truncated-UUID refusal floor | **8** hex | `validation._UUID_PREFIX_MIN_HEX`, sourced to three measured prod ids |

## The bridge (`tools/mcp_bridge/`)

| Value | Figure | Defining symbol |
|---|---|---|
| Tool refresh interval | **300 s** | `TOOL_REFRESH_INTERVAL` |
| Reconnect delay | **3 s** | `RECONNECT_DELAY` |
| Restart cap | **5 per 60 s** | `RESTART_MAX`, `RESTART_WINDOW_SECONDS`; history in `RESTART_HISTORY_ENV` = `_DD_MCP_BRIDGE_RESTART_HISTORY` |
| Port probe | **1.0 s** | `_probe_port`'s `asyncio.wait_for(..., timeout=1.0)` |
| Upstream HTTP | **connect 30 s / read 120 s** | `httpx.Timeout(30.0, read=120.0)` in `upstream_connection_manager` |
| SSE relay timeout | **unbounded** | `httpx.AsyncClient(timeout=None, ...)` in `_relay_sse_stream` |
| `tools/list` readiness wait | **10.0 s** | inline literal in `main.list_tools` — unnamed |
| Fast-fail latency | **< 100 ms** | pinned live: `assert elapsed < 0.1` in `TestHandleCallToolFastFail` |
| Former opaque wait | **5 s — UNSOURCED** | prose only, in `README.md` § "Resilience behavior" and `_handle_call_tool`'s docstring. No constant, no test, and `git log -S "sleep(5" -- tools/mcp_bridge/bridge.py` finds no commit that removed one. **Do not quote "5 s → <100 ms" as a measured 50×.** |
| Profile-switch poll / timeouts | `_PROFILE_SWITCH_POLL_S`, `_PROFILE_SWITCH_TIMEOUT_S`, `_TOOL_REFRESH_TIMEOUT_S` | symbols exist in `bridge_tools.py`; values not transcribed here |

## The server (`discodon/web/mcp/`, `discodon/config/sections/mcp.py`)

| Value | Figure | Defining symbol |
|---|---|---|
| Action timeout | **120.0 s** | `McpConfig.action_timeout_s` — hot, read per dispatch, "documented as sized for the ordinary case" |
| Generation action timeout | **900.0 s** | `McpConfig.generation_action_timeout_s` — self-declared "a deliberate over-estimate rather than a measurement" |
| C2 command ceiling | **30,000 ms** | `McpConfig.command_timeout_max_ms` — hot, read per call |
| Watch capture ceiling | **120 s** | `McpConfig.watch_capture_max_s` — hot, read per call; equal to `action_timeout_s`, which is the racing defect |
| Dispatch budget margin | **15.0 s** | `watch_tool._DISPATCH_BUDGET_MARGIN_S`, consumed once in `_dispatch_budget_s` |
| Sync handler workers | **8** | `McpConfig.sync_handler_workers` — `reload="restart"`, pool built once |
| Session idle timeout | **1800.0 s** | `McpConfig.session_idle_timeout_s` — `reload="restart"`; `0` documented as unbounded growth |
| Request-log ring | **200 entries** | `request_log._MAX_ENTRIES` |
| Request-log detail cap | **8192 bytes** | `request_log._MAX_DETAIL_BYTES` |
| Active-client window | **1800 s** | `request_log._CLIENT_WINDOW_S` |
| Log message cap | **600 chars** | `logs_tool._DEFAULT_MSG_LIMIT` |
| Stored failure detail cap | **500 chars** | `classifier._FAILURE_DETAIL_LIMIT` |
| Default abbreviation limit | **120 chars** | `formatters.abbreviate(value, limit=120, ...)` |
| Watch default / C2 default | **5 s** / **5000 ms** | `watch_tool._WATCH_DURATION_DEFAULT`, `_SEND_COMMAND_DEFAULT_MS` |

## Library and protocol pins

| Pin | Value | Source |
|---|---|---|
| fastmcp | **3.4.2** | `pyproject.toml` (`"fastmcp==3.4.2"`), with the comment "Validate `from fastmcp import FastMCP/Client` before bumping further" |
| mcp | **1.28.1** | `uv.lock`, `[[package]] name = "mcp"` |
| MCP protocol revision | **not pinned — UNSOURCED as a pin** | The old capture recorded `2025-06-18`. Nothing in this repo pins a protocol revision; the string appears once in the tree, inside a spec URL in a references list (`.prawduct/artifacts/design-eval-world-contract.md`). Do not carry it as a pin. |

## Measured incident figures

| Incident | Figures | Source |
|---|---|---|
| Session leak → OOMKill, 2026-08-05 | **1,153** live sessions · **~1 per 3 s** · **~154 KiB** each · **zero** terminations in six hours · OOMKill **22 s** later | `server.apply_session_idle_timeout` docstring + `McpConfig.session_idle_timeout_s` + `.prawduct/learnings-detail.md` — two independent records that agree |
| Oversized result | **249,942** chars · trace **74%** · spans **24%** · reasoning **<2%** | `eval/results.py` `GET_RESULT_SECTIONS` comment — one measurement, no reproducing command |
| Billed-then-cancelled generation, 2026-07-29 | cancelled at **121 s** on a **22-run** campaign, billed, nothing stored | `.prawduct/backlog-archive.md` **[EVL-TD4S]**; the 22 runs corroborated at `build-plan-eval-report-presentation.md` ("analysis `83672866`, 22 runs, $0.7278") |
| Response-path hang, 2026-07-30 | **$0.8005** spent · **~30 min** non-return | `.prawduct/backlog.md` **[MCP-H3ZP]** |
| Silent generation, 2026-08-20 | **~12 min** · aborted at **1800 s** | `.prawduct/artifacts/eval-smoke-2026-08-20-v2.3.45.md` — **and the 1800 s is probably the server's own reaper, not the client; see drift** |
| Head-of-line blocking, prod v2.3.42 | **29** results written then no return · **three** queued calls starved · a first ceiling imposed on **~51** handlers | `dispatch.py` module docstring; profiling filed as **#2320**, open |
| Code-less error inventory | **95** sites across **17** modules — **not 101** | commit `bd6e32a3b`; `.prawduct/artifacts/api-contract.md`. At HEAD the scan returns `{}`. |
| `universe_id` guard population | **19** actions across **four** tools | reproduced at HEAD by AST scan of each `*_tool.py`'s `_ACTIONS` literal |

## Named client bugs

| Issue | Claim | Status of the claim |
|---|---|---|
| `anthropics/claude-code#15904` | no clean stdio respawn on non-zero exit; **closed as not planned**; "the bridge is permanent" | This repo's own assertion; no fetched artifact, no date of checking. **And the same issue is cited for a second, different behaviour** — see drift. |
| `anthropics/claude-code#50319` | duplicate tool names across servers → silent `tools/call` hangs | Cited in five places; **no disposition stated**, so weaker-sourced than #15904. Load-bearing enough that a test asserts `"50319" in str(exc_info.value)`. |

---

# Verification summary

## Rule count by layer

Re-derive from the file itself:

```
FILE=.prawduct/artifacts/mcp-mining/discodon-consumer-structured.md
grep -c '^\*\*RULE' "$FILE"                                  # total rules
grep -oE '^LAYER: L[0-4]' "$FILE" | sort | uniq -c            # by layer
grep -oE '^KIND: [a-z-]+' "$FILE" | sort | uniq -c            # by kind
grep -c '^PROVENANCE: UNADDRESSED' "$FILE"                    # unaddressed
grep -c 'CONTRADICTED' "$FILE"                                # lines mentioning a contradiction
grep -c 'UNSOURCED' "$FILE"                                   # lines carrying an unsourced figure
```

(Counts are stated in the report accompanying this file rather than transcribed here, so that the
commands above remain the only authority and cannot drift from a hand-typed number.)

## Rules that could not be addressed

| Rule | Why |
|---|---|
| "Do not require interactive OAuth" | `PROVENANCE: UNADDRESSED` — the tree **enacts** bearer-token-only auth and never states, argues, or rejects the alternative. Zero `oauth` hits in `discodon/web/mcp/` or `tools/mcp_bridge/`. The rule is a correct description of the artifact and a fabrication as a rule this repo holds. Its only warrant is the shape of the credential flow. |

## Rules carried forward as CONTRADICTED

| Rule | What the tree actually says |
|---|---|
| Declare read-only vs mutating per tool | Both sites that faced the question **refused** classification-based gating and gate uniformly instead. Retained above as a CONTRADICTED stub beneath its replacement. |
| Report tool failure as `isError: true` | `grep -rn "isError" discodon/` → **zero hits**. The server returns coded error strings in *successful* results and lets unexpected exceptions propagate. Only the bridge sets `isError`, and only for transport failures. |
| `additionalProperties: false` "broke in production" | It has never broken — the feature that would hit the 422 is unbuilt (`status: open · stage: idea`). Re-tiered to `designed-untested`. |
| "the sibling bridge in the same repo does exactly that [drops `structuredContent`]" | Inverted. `tools/mcp_bridge/bridge.py` forwards it verbatim **with a test pinning it**; the dropper is `discodon/tools/mcp_bridge_tool.py`'s `_extract_text`. |
| "Expect an HTTP URL **resolving to** a private address to be refused" | The check never resolves. Only IP literals are caught; a DNS name pointing at 10.0.0.5 passes, deliberately and documented. And the guard is on the registration surface only — zero callers on the connection path. |
| "your connection error string is the entire diagnostic surface an operator ever sees" | Backwards. The string reaches the model (prompt, tool result) and is **dropped** before the operator surfaces, which show only `verification_status`. The persisted registry doc has no field for it. |
| "every adversarial server behaviour was discovered in production, never simulated in advance" | Content-shape misbehaviour **was** simulated in advance, in the feature's own PR. Timing and framing were not — which is the sharper, principled version of the claim. |
| "noted at three other call sites" (dispatch margin) | Three occurrences exist; **none is a call site** (a module docstring and two budget-formula docstrings), and the count misses a fourth site that states the rule in different words. |
| Emit progress for anything over **~30 s** | The threshold does not exist in the tree in any form, and there is no MCP progress mechanism to hang it on. The tree's rule is **categorical** ("runs have `get_run`, generations have no equivalent"), and a duration test is the framing its own incident refutes. |
| "Treat HTTP 200 as 'a response arrived'" pinned against **proxy/login interception** | The test exists with a `"<html>"` 200 body, but nothing in the tree mentions a proxy or captive portal. The real subject is an eight-case exhaustive-outcome contract — a stronger rule. |
| "Size timeouts per tool class **and** never cancel work you have already billed for" | Two halves with opposite evidence states shipped as one settled fix. The second is unbuilt and unowned, and its successor tracker does not exist. |
| **101** code-less error returns | Not a contradiction but a **supersession** — the figure is real (**[MCP-J8QF]**'s title) and four measurements stale. See the UNSOURCED table and § C. |

## Figures returned as UNSOURCED

| Figure | Where the old capture used it |
|---|---|
| **~30 s** progress threshold | § E — invented; no constant, no doc rule, no mechanism |
| **5 s** former opaque wait | § E — prose in two places, no constant, no test, no removing commit |
| protocol **`2025-06-18`** | pins line — not a pin anywhere; appears once inside a spec URL |
| **101** code-less error returns | § C — **not unsourced: SUPERSEDED.** It is the title of **[MCP-J8QF]**, whose own body records 104→102 and whose closure records 95, with the inventory now empty. A pinned-by-equality measurement that moved four times; cite the mechanism, never a digit. |
| **six** orphan schema params | § B — historical, enumerable from a docstring, no longer reproducible (the pin now asserts empty) |
| **"three other call sites"** | § E — three occurrences, zero call sites |
| `reconnect_attempts=0, last_error=null` in the stale-session symptom | § E — an inference; the record names only `upstream_connected=True` |

---

# Doc-vs-code drift in discodon itself

**These are bug reports owed back to that repo. They are NOT corpus material and no rule above rests
on them.** Nothing in discodon was modified; this is a list of places its own records disagree with
its code or with each other. Ordered roughly by consequence.

1. **`EVL-D2WN` is cited twice as the live tracker for billed-vs-stored reconciliation and does not exist.** `.prawduct/backlog-archive.md` closes **[EVL-TD4S]** by handing its unbuilt half to a successor — "**Successor filed 2026-07-30 — `EVL-D2WN`** ... **Read `EVL-D2WN`, not this paragraph, for the live state**" — and `.prawduct/change-log-archive/2026-07.md` routes to it too. A full-tree search returns **only those two prose mentions and no item**. So the one money-losing path in the timeout cluster was closed by redirection to a tracker that was never filed, and both pointers instruct the reader not to rely on the paragraph that is now the only record. Invisible to `pick`.

2. **`ChannelBridge`'s recorded re-evaluation trigger does not cover the principal axis.** The singleton comment says "single-instance assumption is correct today (one claude.channel surface per process). Re-evaluate when adding a second message **source** (e.g., Slack)." The assumption that actually binds is narrower: `push_notification` fans out to every captured write stream with **no principal predicate**, so it is only correct while there is one *principal* — a property of deployment, not of code. `McpBearerAuthMiddleware` already resolves a distinct `mcp_user_id` per request and `UserTokenStore` is explicitly multi-user. The repo ships multi-principal token management over a single-principal notification path, and the recorded trigger will not fire when the real condition (a second concurrent operator) arrives. Fix: restate the trigger on the principal axis, and either key `_write_streams` by `user_id` or state in prose that channel notifications are deliberately broadcast-to-all.

3. **`claude-code#15904` is cited for two different upstream behaviours.** `documentation/MCP_SERVER.md` § Connection Architecture attributes to it "Claude Code's HTTP MCP client does not auto-reconnect when the server restarts" — the justification for the proxy existing. `tools/mcp_bridge/bridge.py` and `README.md` attribute to the same issue "Claude Code does not respawn stdio MCP servers cleanly when the child exits non-zero" — the justification for `execv`. Distinct behaviours on distinct transports; at most one is what the issue says. Two load-bearing decisions rest on one citation that cannot support both.

4. **The 1800 s abort attributed to "the MCP client" is probably the server's own reaper.** `.prawduct/artifacts/eval-smoke-2026-08-20-v2.3.45.md` says "the MCP client eventually aborted it on a 1800s idle timeout". `McpConfig.session_idle_timeout_s` defaults to `1800.0`, applied server-side by `apply_session_idle_timeout`, which shipped **2026-08-05 — fifteen days before** the observation. A server reaping its own stateful session at 1800 s idle explains the abort completely, and the coincidence of digits is addressed nowhere. This is not tidiness: **[MCP-H3ZP]** sits at `stage: research` with the deliverable *identify the hanging leg*, reasoning about the 900 s generation budget without considering that the **session**, not the call, may have been reaped. If the reaper is the terminator, the diagnosis and the fix both change. Worth recording the tension the tree has nowhere noted: a legitimately long generation and an idle-session reaper are in direct conflict, because a stateful session with one in-flight 12-minute call may look idle to a reaper that counts requests.

5. **Stale remedy in the server-side `${VAR}` refusal.** `discodon/web/mcp/auth.py` `_validate_bearer` returns "DD_MCP_TOKEN is not set in your shell environment ... Fix: install direnv (brew install direnv), run 'direnv allow' ... then restart Claude Code." Every element is contradicted by the current design as documented in `documentation/MCP_SERVER.md`: § Prerequisites says "No direnv setup is required for MCP", § How It Works says "no direnv, no `${VAR}` expansion in `.mcp.json`", and the env var is per-profile (`DD_MCP_LOCAL_TOKEN` / `DD_MCP_PROD_TOKEN`), not `DD_MCP_TOKEN`, which appears nowhere in `profiles.toml`. The dispatch-time log line has the same problem ("direnv likely not active"). An operator following this installs a tool the bridge does not use and restarts a client that did not need restarting. Same middleware whose *other* stale docstring caused item 6's incident.

6. **`mcp-scaling-strategy.md` § "6. Error Format" teaches the exact form the repo now bans.** It still reads "All errors return strings starting with `"Error: "`", with three code samples. That is the code-less shape `test_mcp_error_code_inventory.py` pins at `{}` and `mcp_error_text`'s docstring forbids. A new-action author following the strategy doc writes the defect and is caught only by the inventory canary. `api-contract.md` has the correct version; the strategy doc was never updated (`last_validated: 2026-05-11`, ~4 months before the fix).

7. **The strategy doc's tool table is off by 8 tools and ~160 actions, and its own reassessment trigger is tripped.** § 1 shows a 6-row table totalling 87 actions. The server registers **14** tools totalling **247** actions (AST over each `*_tool.py`'s `_ACTION_HANDLERS` literal plus `grep -c "@eval_action("`): entity 44, eval 62, system 35, prompt_graph 16, decision 14, scenario 12, prompt 11, budget 9, c2 9, telemetry 9, config 8, logs 7, channel 6, watch 5. Missing from the table entirely: `prompt`, `prompt_graph`, `budget`, `decision`, `scenario`, `telemetry`, `channel`, `config`. Consequently § "When to reassess this strategy" — "If any single tool exceeds 50 actions" — **fires today on `eval` (62) and has gone unevaluated**, because the table a reader would check says 46. Step 7 of the doc's own "Adding New Tools" checklist is "Update this strategy doc's tool table." The same file's header undersells its subject by 10× ("from 5 tools / 70 actions to 10+ tools / 200+ actions").

8. **`mcp-scaling-strategy.md` § 3 states the defaults rule in the weaker, pre-incident form.** "All parameters (except `action`) have defaults. Use `None` as 'not provided' sentinel" permits a non-`None` default so long as *some* default exists — which is exactly what `test_every_facade_param_defaults_to_none` refuses. `mcp-tool-design.md` carries the corrected hard constraint and annotates the reversal. And § 2's dispatch sample predates every guard in `dispatch_action` (no timeout, no UUID canonicalisation, no undeclared-param refusal, an uncoded unknown-action string) while reading as the current contract.

9. **The unknown-action reply is the only refusal on the surface with no machine-readable code.** `dispatch_action` returns `f"Unknown action '{action}'. Available actions: {known}..."` — no `Error (CODE):` prefix, so `_API_ERROR_PREFIX_RE` misses it and the call logs `status=ok`: the #2327 defect, on the one path that is not a returned-string-from-a-handler. The inventory scanner cannot see it because it only counts returns whose prefix *starts with* `Error`. `_USER_INPUT_ERROR_CODES` already reserves `unknown_action` "forward-compat" — the code exists and the emitter does not use it. A real hole in the canary's coverage rather than a false claim in the artifact.

9b. **`[MCP-J8QF]` is still `status: open` with a title that disagrees with its own body, for work `api-contract.md` records as closed.** The item's metadata line reads `status: open · stage: ready · reviewed: 2026-08-03`, while `.prawduct/artifacts/api-contract.md` says "**Closed 2026-09-02 (#2327): the inventory is empty.**" and the inventory test now pins `{}`. Separately, the item's own title says **101** sites while its body's most recent measurement says **102** ("dropping the pinned measurement from **104→102 sites** across **18→17 modules**, and the eval subset from **23→21**") — so the title was never updated by the paydown that updated everything else, and the body explicitly notes `api-contract.md` and the test "were updated in lockstep". A shipped-but-not-closed item whose headline number is stale in the one field a reader quotes. This is also the origin of the wider corpus's "101", so closing it is worth more than tidiness.

10. **`api-contract.md` says "Four sites emit it" above a five-row table**, and **uses "17" for two different sets one clause apart** ("All 95 code-less error returns across the 17 MCP modules — the 17 inside registered eval actions included"). Both readings of 17 are individually true, which is what makes the sentence dangerous — and this is the sentence the artifact holds up as its example of a claim made checkable.

11. **`discodon/operations/timeouts.py` § "Registered ops without consumers in this PR" is a stale section, and the backlog says so.** The heading names a long-merged PR and lists six ops as "the pre-built shape of the next migration batch". **[LLM-ZB4L]** contradicts it: "the mechanism shipped (C7), the migration didn't ... `llm_request` is unchanged ... with no `operation_timeout('llm_request')` call site anywhere in the tree." A forward-looking section that stopped being forward-looking now reads as "these will be adopted shortly" — and it is the docstring a reader consults before deciding whether the registry covers their call, which is the exact mistake **[LLM-ZB4L]** warns against.

12. **`watch_tool._dispatch_budget_s` cites "three other call sites" for a failure documented at zero call sites**, and the phrase-count misses a fourth site that words it differently (`_budget_eval_cell`). Two cheap fixes: call them what they are, and either normalise `_budget_eval_cell`'s wording or note it as the exception.

13. **`discodon/web/mcp/dispatch.py` says "~18 MCP tools"; the server registers and advertises 14.** `create_mcp_server` makes exactly 14 `register_*_tool` calls and its `instructions` string opens "Discodon MCP server. Fourteen tools available:". The same docstring's concurrency-audit note says "nobody walked all fourteen", so the file disagrees with itself four paragraphs apart. The 14 is load-bearing (it is the agent-facing promise); the ~18 is not, which is why it will not get fixed on its own.

14. **The bridge's "5-second opaque hang" baseline has no derivation.** Asserted in `README.md` § Resilience behavior and `_handle_call_tool`'s docstring; no constant, no test, and `git log -S "sleep(5" -- tools/mcp_bridge/bridge.py` finds no commit that removed one. The `<100 ms` side is pinned by a live assertion, so the improvement is verified while its baseline is folklore.

15. **`discodon/web/mcp/eval/analysis.py` is an 8-line stub whose docstring promises work that landed in its near-homonym.** It reads "New actions for the v1 surface land in subsequent ER-1 sub-commits..." while the analysis surface is live in the sibling `analyses.py` (9 `@eval_action` registrations including `analysis_generate`). Two files one character apart, one live and one still promising the other's contents — an active hazard for anyone navigating by filename. Delete the stub or point it at `analyses.py`.

16. **`[LLM-ZB4L]`'s cited line numbers are stale by ~30 lines** (`:162`/`:178` for calls now at 192/208). Symbols and reasoning intact, so this is precision rot — but the item's whole value is telling the next reader where to wrap, and a `file:line` that no longer resolves reads as evidence of having been checked. Anchor on `McpBridgeTool.act` and "the post-reconnect retry inside the except".

17. **`ChannelBridge.register_write_stream`'s docstring describes a symmetry the function does not have.** Documented "Called when an MCP session is created" / "...ends"; the comment inside `patch_mcp_server_for_channel` — its only caller — spends a paragraph denying exactly that (the `finally` runs only when `original_run` returns, which for a stateful streamable-HTTP session happens on an explicit client DELETE or a transport idle timeout and nothing else). Low severity (the accurate account is ten lines away) but the misleading sentence is what a reader hits first, and the caller's comment is not reachable from `help(ChannelBridge)`.

18. **`eval_tool.py`'s facade comment says "all 60 of them"; there are 62.** Also `test_mcp_dispatch.py` ("declaring it 60 times is not a contract") and `dispatch.py`'s `_UNIVERSALLY_ACCEPTED_PARAMS` comment. Cosmetic in all three — no argument turns on the digit — but it is a hand-maintained count in four places and it has already drifted.

19. **The tool cap `20` has four independent copies and only one of them is the named constant.** `DEFAULT_MAX_TOOLS = 20` is defined in `discodon/tools/mcp_bridge_tool.py`; `discodon/tools/mcp_registry.py` imports `McpBridgeTool` but **not** the constant, and spells `20` as a bare literal at three sites — `_parse_server_entry` (`entry.get("max_tools", 20)`), `_make_server_tool_class` (`server_config.get("max_tools", 20)`), and `_register_from_servers_dict` (`"max_tools": 20`). Changing the constant therefore moves the per-persona default and leaves all three registry paths at 20. Low severity and worth stating precisely rather than as more than it is: the DB-registry path's hardcode sets only a *default* — `_make_server_tool_class` still exposes `max_tools` as an `admin_only` config field and `update_config` honours it, so an admin can still raise it per entity — and `save_registry_entry` persists no `max_tools` field at all, so no registry entry can carry one for that path to override. The finding is the duplicated literal, not a lost operator setting.
