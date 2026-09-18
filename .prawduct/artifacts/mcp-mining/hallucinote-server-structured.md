# hallucinote — full-fidelity capture (106 rule blocks)

**Provenance:** verbatim final report of the `Mine hallucinote MCP knowledge` coordinator agent
(task `ae2d6f3c14b76513a`, returned 2026-09-17), which dispatched two miners and states it verified
their flagged claims against the tree. Extracted from the agent transcript, not retyped.

**Relationship to `hallucinote-server.md`:** same mining, different rendering. That file is the
curated/compressed reading captured earlier; this one carries the per-rule `FIRE-SITE / LAYER /
KIND / EVIDENCE / PROVENANCE / VOLATILE / TENSION` block that the corpus schema
(`../mcp-knowledge-corpus-design.md` §3) is built on — and that §10.4's verification debt needs, since
a rule with no address cannot be re-derived. Neither file supersedes the other; the compressed one
is the better read, this one is the auditable record.

**Counts disagree three ways and none is re-derived.** The agent's own summary says *"Total distinct
rules found: 78 — L0 ×4, L1 ×25, L2 ×21, L3 ×20, L4 ×8"*; its body carries 106 `**RULE:**` blocks
(L0 4 · L1 29 · L2 21 · L3 24 · L4 28 — only L2 matches). The compressed file's headline says 92.
Re-derive with `grep -c '^LAYER: ' <this file>`; do not quote the 78. Treated as a finding, not
reconciled here.

**Unverified.** Every `file:line`, symbol and number below is an agent's claim about another repo;
none has been resolved against hallucinote's tree from here. See README.md.

**Amended 2026-09-18 — the relationship above is right and incomplete.** "Neither supersedes the
other" is true, but it reads as though the two files hold the same rules in two renderings. They do
not. The compressed file is **missing roughly eight rules** that are here, including the entire L0
observability rule; and it **re-files three rules to better layers** than this capture gave them
(schema-in-one-module and action-surface-fan-out L4→L2, three-causes-of-a-version-mismatch L4→L3).
So: author from **this** file for content, read **that** one for phrasing and layer assignment. The
gap list and its probe command are in that file's header.

**Verification in flight (2026-09-18).** An audit resolving every `PROVENANCE:` line below against
hallucinote's tree is being written to `hallucinote-verification.md` — per-rule verdicts
(RESOLVED / MOVED / NOT-FOUND / CONTRADICTED / UNVERIFIABLE), a constants audit, and a durable
anchor for each citation stated as a bare line number. **Until that file exists and is read, treat
every citation below as an unresolved claim, and do not lift a rule into the corpus on the strength
of its address alone.** This file is deliberately left exactly as the mining coordinator wrote it —
it is the record under audit, so the verdicts live beside it rather than in it.

---

Both miners returned; I verified their flagged claims against the tree. Findings below.

---

# MCP engineering rules mined from `hallucinote`

## L0 — whether/when to build one

**RULE:** Before committing to an MCP server for a desktop app, check whether the app is scriptable only from inside its own process — if so, you are not building one deployable, you are building two, and the vendoring step, version handshake and host-restart requirement are all forced, not chosen.
FIRE-SITE: Scoping an MCP server for a GUI application (DAW, IDE, CAD tool, browser).
LAYER: L0 · KIND: constraint · EVIDENCE: designed-untested (reasoned, with 18 months of downstream cost visible) — `architecture.md` §"Why this topology and not a simpler one": *"everything awkward downstream (the vendoring step, the version handshake, the restart requirement) descends from that one constraint."*
PROVENANCE: `.prawduct/artifacts/architecture.md:50-58`
VOLATILE: none · TENSION: precondition for every fingerprint/re-vendor rule below.

**RULE:** Keep pure computation out of the MCP surface when you own a source of truth for it — wrapping the host's version buys you an untestable black box and per-document state, while owning the math gives cross-target uniformity for free.
FIRE-SITE: Deciding whether a capability becomes a tool or stays in your engine.
LAYER: L0 · KIND: decision-point · EVIDENCE: measured(design rationale) — quantize/swing/groove deliberately shipped as zero actions: *"(a) Live's quantize is a black box we can't unit-test; (b) keeping the timing math in our space gives uniform behavior across all DAW targets; (c) groove templates as DB rows are portable across songs, unlike Live's per-set Groove Pool."*
PROVENANCE: `docs/archive/mcp-tool-design.md` §4.2, §14 item 7
VOLATILE: none · TENSION: none.

**RULE:** Do not move large binaries through the protocol — write them to disk and exchange paths plus a JSON summary.
FIRE-SITE: Designing a tool that produces audio, video, images, or model artifacts.
LAYER: L0 · KIND: stance · EVIDENCE: measured — renders are 48 kHz/32-bit-float per surface, *"~23 MB per surface-minute … gigabytes per take"*; the render tool returns `captures_dir` + `manifest_path`, the analyze tool returns a summary + `report_path`. No lesson about in-band transfer exists in this corpus because they never attempted it.
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/server.py` `_sweep_stale_takes`; `handlers/jobs.py` `status_result`
VOLATILE: none · TENSION: none.

**RULE:** For a single-user local server, decide explicitly that there is no fleet to observe — then name the substitutes (a `preflight` diagnostic subcommand, an audit-event table, the client's own connection log) instead of leaving observability undesigned.
FIRE-SITE: Writing the observability section of an MCP server's design.
LAYER: L0 · KIND: decision-point · EVIDENCE: designed-untested — ratified norm *"No telemetry… there is no fleet to observe"*, with `python -m hallucinote_mcp.cli preflight` named as *"the supported install-state diagnostic … the first thing to ask for in a bug report."*
PROVENANCE: `.prawduct/artifacts/observability-strategy.md`; `.prawduct/artifacts/api-contract.md:162`
VOLATILE: none · TENSION: depends on the connection-log rule (L3) for the one thing preflight cannot see.

---

## L1 — agent-interface design

**RULE:** Check your target clients' tool caps before choosing a tool count — Cursor caps at 40 and drops the overflow silently, so a 52-tool server is partly invisible with no error emitted anywhere.
FIRE-SITE: Registering tool number 41; auditing why an agent "can't see" a tool.
LAYER: L1 · KIND: diagnostic · EVIDENCE: measured(third-party) — *"Cursor caps at 40 tools (silent drops above); Copilot caps at 128. AbletonMCP at 52 exceeds Cursor's cap."*
PROVENANCE: `docs/archive/mcp-tool-design.md` §1.2
VOLATILE: Cursor 40 / Copilot 128 caps (2025). · TENSION: none.

**RULE:** Treat ~10K tokens of tool definitions as a hard ceiling and collapse to an action-dispatch surface below it — accuracy degrades as a cliff, not a slope (10 tools perfect, 20 near-perfect, ~107 total collapse).
FIRE-SITE: Arguing against "just one more tool".
LAYER: L1 · KIND: constraint · EVIDENCE: measured(third-party) — Speakeasy Pet Store: *"at 107 tools both large and small models failed completely, and task success collapsed."* GitHub Copilot 40→13 tools gave *"2 to 5 percentage point improvement across SWE-Lancer and SWEbench-Verified, plus a 400ms latency reduction."* This repo went 52 → 13.
PROVENANCE: `docs/archive/mcp-tool-design.md` §1.2; `.prawduct/artifacts/api-contract.md:113-120`
VOLATILE: the 10–20 band is model-generation-dependent. · TENSION: contradicted in practice by the next rule.

**RULE:** Ratify the tool count as a *band*, not a number, and expect the budget to leak to the next capability after the consolidation ships — the leak is not the consolidation failing, it is the budget having no owner.
FIRE-SITE: Adding a tool after a consolidation.
LAYER: L1 · KIND: diagnostic · EVIDENCE: measured(this repo) — the design doc budgets **10** tools and ≤200 tokens of description each; `schema.TOOLS` ships **13** (`ableton_render`, `ableton_analysis`, `ableton_probe` were all added post-design; `probe` appears in neither design doc). The ≤200-token-per-description criterion appears never to have been measured — `ableton_analysis`'s summary string alone runs ~110 words before its flattened param schema.
PROVENANCE: `docs/archive/mcp-tool-design.md` §4.1/§16 vs `hallucinote_mcp/src/hallucinote_mcp/schema.py:16-30` (verified: 13)
VOLATILE: none · TENSION: contradicts the rule above — report both.

**RULE:** When you report "N tools became M", state the reduction in *tool-list width* separately from what happened to the *action count* — consolidation shrinks selection space and usually grows the operation surface.
FIRE-SITE: Writing the headline number in a README or design doc.
LAYER: L1 · KIND: constraint · EVIDENCE: measured — the same sentence claims *"~84% reduction in selection-space width"* for 52→10 tools and records *"Total: ~94 actions in 10 tools"*. Operations nearly doubled.
PROVENANCE: `docs/archive/mcp-tool-design.md` §4.1
VOLATILE: none · TENSION: none.

**RULE:** Do not put action parameters behind a `params={...}` envelope — synthesize each tool's schema as `action` plus the flattened union of every action's params, all keyword-only and optional, so the wire shape matches every example string you publish.
FIRE-SITE: Implementing action dispatch on FastMCP/pydantic.
LAYER: L1 · KIND: pattern · EVIDENCE: broke-in-production — the documented call shape and the accepted call shape had silently diverged: the flat form *"removes the agent-hostile `params={...}` envelope that pydantic's `extra='ignore'` silently demanded under the old `(action, params)` wrapper."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/server.py:1-17`, `_register_tool`
VOLATILE: pydantic `extra='ignore'` default. · TENSION: makes the next rule mandatory.

**RULE:** Once the schema is a flattened union, the dispatcher must reject params that are unknown *for the chosen action* — the flattening is what makes cross-action params structurally acceptable to the client.
FIRE-SITE: Writing the param validator.
LAYER: L1 · KIND: constraint · EVIDENCE: designed-untested, plus a shipped guard — `_collect_tool_params` raises on a same-name/different-type collision across actions (*"rename one to avoid a flat-schema collision"*), and `validate_params` rejects unknowns *"to fail loudly on typos rather than silently dropping data."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/server.py:703-733`; `dispatcher.py:193`
VOLATILE: none · TENSION: depends on the flattened-union rule.

**RULE:** Give every error four recovery fields — `valid_actions`, `required`/`optional`, a runnable `example`, and a `hint` naming the self-service next call — because the error is not a log line, it is the next turn's input.
FIRE-SITE: Writing any error return in a dispatcher.
LAYER: L1 · KIND: pattern · EVIDENCE: designed-untested (ratified norm, uniformly implemented) — *"an error is not a log line read by a human hours later; it is the next turn's input, and its structure decides whether the agent recovers or flails. A bare error string is a defect here in a way it wouldn't be in a human-operated system."*
PROVENANCE: `.prawduct/artifacts/api-contract.md:63-80, 184-196`; `hallucinote_mcp/src/hallucinote_mcp/dispatcher.py:437-538`
VOLATILE: none · TENSION: none.

**RULE:** Generate `action='help'` from the same metadata object the dispatcher validates against, and special-case it as pure metadata that needs no backend — help that is written separately drifts, and help that needs the backend is unavailable exactly when it is needed.
FIRE-SITE: Adding a discovery surface.
LAYER: L1 · KIND: pattern · EVIDENCE: designed-untested — `help_for_tool` renders from `schema.actions_for`; dispatch returns help before any Live check: *"Help is special-cased: pure metadata, no Live access required."* `register_help_actions()` back-fills any tool that forgot one, and `Action.__post_init__` refuses a `help` action that sets an executor.
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/dispatcher.py:245-290`; `schema.py:290-310`
VOLATILE: none · TENSION: none.

**RULE:** An error must carry the state that makes the follow-up diagnostic call unnecessary — if you say "this may not be loadable here", also list what is already there.
FIRE-SITE: Writing a failure hint for a mutation that collided with existing state.
LAYER: L1 · KIND: pattern · EVIDENCE: broke-in-production — `device.py:572` hinted *"the item may not be loadable on this parent (e.g. instrument on a return)"* when the real cause was a same-class device already at that position. The plausible-but-wrong hint cost a round-trip *and* misdirected the diagnosis. Fix: list the parent's existing `class_name`s in the error.
PROVENANCE: `docs/archive/v11-requirements.md` Arc 1 "A2-resid"
VOLATILE: none · TENSION: none.

**RULE:** Lead your error-recovery guide with "retrying this call with the same params will fail the same way", then enumerate the exceptions by name — an unannotated error reads as transient and agents default to retry.
FIRE-SITE: Authoring the agent-facing error reference.
LAYER: L1 · KIND: pattern · EVIDENCE: designed-untested — shipped guide's first paragraph, with *"Two replies are exceptions to that rule, and both are about Live being busy rather than about your call."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/resources/guides/error-recovery.md:1-10`
VOLATILE: none · TENSION: depends on the escalation/busy rules (L3).

**RULE:** Return the identity of whatever a mutating action created — a prose confirmation costs one follow-up call per object.
FIRE-SITE: Writing the return value of any create/duplicate/load action.
LAYER: L1 · KIND: pattern · EVIDENCE: measured — `duplicate_clip_to_arrangement` returned only *"Duplicated session clip to arrangement on track N"*: *"For a 49-clip rebuild: 49 wasted round-trips."* `load_instrument_or_effect` returned a device list that was *empty*, so the caller *"can't programmatically confirm what loaded."*
PROVENANCE: `docs/archive/mcp-requirements.md` §6, §10
VOLATILE: none · TENSION: none.

**RULE:** Ship a single-item read and a filter parameter alongside every bulk read — "did my write land?" is an inner-loop step and pays the full bulk cost every time without one.
FIRE-SITE: Designing a `get_*`/`list` action over an entity with many attributes.
LAYER: L1 · KIND: pattern · EVIDENCE: broke-in-production(open bug, 2026-09-11) — `ableton_device(get_parameters)` is all-or-nothing; no singular form exists (confirmed: `"unknown action 'get_parameter'"`). An EQ Eight has **84 parameters** and `detail='summary'` still returns all of them. One mixing pass: *"~420 parameter rows, and I wanted about six."*
PROVENANCE: `incoming-bugs/2026-09-11-get-parameters-has-no-single-param-read-and-no-band-filter.md`
VOLATILE: none · TENSION: none.

**RULE:** A capped read returns an explicit `truncated` flag plus the parameter that subdivides the walk, and says in its own description that it is not for per-turn use — never truncate silently.
FIRE-SITE: Writing a list/inventory/tree action over an unbounded corpus.
LAYER: L1 · KIND: pattern · EVIDENCE: designed-untested — `ableton_browser(inventory)` returns `{scope, walk_depth, entries, count, truncated}`, *"subdivide via path_prefix; never silently truncates"*, description carries *"NOT for per-turn use; use 'search' to find content interactively."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/actions/browser.py:205-220`
VOLATILE: none · TENSION: none.

**RULE:** Put a soft cap with a non-blocking `warning` on any payload channel whose cost is the agent's context, and name the out-of-band path in the warning.
FIRE-SITE: Accepting an inline array/blob parameter.
LAYER: L1 · KIND: pattern · EVIDENCE: designed-untested (concrete threshold) — above ~32 notes both `create` and `replace_notes` attach a warning: *"large inline arrays cost agent context and bypass the Hallucinote DB (the next full push overwrites a clip authored only inline)"*, routing to code + a CLI so *"the array never enters the agent's context."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/resources/guides/conventions.md:108-117`
VOLATILE: ~32 is a judgement call. · TENSION: none.

**RULE:** Dispatch a bulk plan out of the agent's context — a CLI that talks to your backend directly and returns one summary — rather than having the agent emit N tool calls.
FIRE-SITE: A planner that produces many calls; any "apply this plan" surface.
LAYER: L1 · KIND: pattern · EVIDENCE: measured — the ten-phase push planner's calls were agent-dispatched; *"for large songs that's a context ceiling."* `push_cli execute` dispatches via `hallucinote_mcp.client.send` *"so bytes never enter the agent's context."*
PROVENANCE: `CHANGELOG.md:1047-1053`
VOLATILE: none · TENSION: the same client path must therefore carry the read-timeout policy (see ENV-9P4T rule, L3).

**RULE:** Delegate a start+poll loop to a subagent that returns only the terminal summary — polling is the cost the pattern imposes on the caller's context, and it is the only cost that grows with job length.
FIRE-SITE: Shipping the skill/recipe that drives an async tool pair.
LAYER: L1 · KIND: pattern · EVIDENCE: designed-untested — `/render-analyze` spawns one subagent for render-start→poll→analyze-start→poll and returns only the MixReport summary + `report_path`: *"Driving both poll loops yourself fills your context with `running…` statuses."*
PROVENANCE: `skills/render-analyze/SKILL.md`
VOLATILE: host must support subagents. · TENSION: depends on the start+poll rule (L3).

**RULE:** A write that returns `ok`, returns the new value, and reads back correct is still not evidence of effect — identify the host's *mode* parameters that decide whether a control is in circuit, expose them, and refuse or warn at the call site.
FIRE-SITE: Wrapping any third-party API with mode-gated controls.
LAYER: L1 · KIND: diagnostic · EVIDENCE: broke-in-production(open bug, 2026-09-11) — EQ Eight's `B` filter set is only in circuit in L/R or M/S mode. Three B-band writes returned ok, read back at the new value, and did nothing: expected ≈ −2.3 dB, measured **+0.08 dB**. Cost *"three renders (~30 min of realtime capture) and one confidently wrong diagnosis."* The gating `Mode` parameter *does not appear in `get_parameters` output at all* — *"the B parameters are reachable and the switch that gives them meaning is not."*
PROVENANCE: `incoming-bugs/2026-09-11-eq-eight-b-band-writes-are-silent-no-ops.md`
VOLATILE: Live 12.x EQ Eight. · TENSION: none.

**RULE:** Never expose a parameter without exposing the parameter that decides whether it is in circuit.
FIRE-SITE: Deciding what a `get_parameters`-style read filters out.
LAYER: L1 · KIND: constraint · EVIDENCE: broke-in-production — same bug, fix #2: *"Expose EQ Eight's `Mode` … It does not appear in `get_parameters` output at all, so an agent cannot even check which set is live."*
PROVENANCE: as above
VOLATILE: none · TENSION: none.

**RULE:** In a handler that performs more than one write from separate validations, resolve and validate everything before writing anything — a raise mid-sequence returns an error the agent reads as "nothing changed" while the host is half-mutated.
FIRE-SITE: Any handler with two `setattr`/write calls and a `raise` path between them.
LAYER: L1 · KIND: constraint · EVIDENCE: broke-in-production(RTE-1K9T) — `set_output_routing` wrote `output_routing_type` and *then* resolved the optional channel; an unknown channel raised after the reroute had applied, so *"the MCP response was an error, but the session's output was now silently pointing at the new bus."* Test discipline recorded: assert the **first object is untouched** — *"a response-only assertion passes even when the session half-mutated."*
PROVENANCE: `.prawduct/learnings-detail.md:539-543`
VOLATILE: none · TENSION: none.

**RULE:** Refuse a call whose underlying primitive is a destructive toggle — do not pass the toggle through.
FIRE-SITE: Wrapping a native set/create call that is idempotent-by-toggling.
LAYER: L1 · KIND: pattern · EVIDENCE: broke-in-production — *"`cue_create: a cue already exists at position_beats=X` — Live's `set_or_delete_cue` is a TOGGLE that would silently DELETE; use `cue_delete` first if you want to replace."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/resources/guides/error-recovery.md`
VOLATILE: none · TENSION: none.

**RULE:** When a tool's name misdescribes its semantics, the response message is lying too — fix both and repeat the correction in four places (tool help, server primer, a resource, and the error when misuse is detected).
FIRE-SITE: Discovering a tool whose verb doesn't match its implementation.
LAYER: L1 · KIND: diagnostic · EVIDENCE: broke-in-production — `add_notes_to_clip` called `clip.set_notes(...)` (a full replace) and responded *"Added N notes to clip"*. *"Name + response message both lie. Agents call it expecting append behavior, get silent destruction of existing notes. I only avoided the trap by reading the remote script source."* Renamed to `replace_notes`, response now *"Set N notes on clip (replaced previous content)"*. Governing principle: *"Repetition beats subtle."*
PROVENANCE: `docs/archive/mcp-requirements.md` §1; `docs/archive/mcp-tool-design.md` §3 principle 8
VOLATILE: none · TENSION: none.

**RULE:** Put your own scars in the agent-facing docs as an explicit anti-pattern gallery — the gotcha that burned you is the one the next agent repeats.
FIRE-SITE: Writing the server's guide resources.
LAYER: L1 · KIND: stance · EVIDENCE: designed-untested (adopted from a sibling project's Don't/Do table plus changelog scars) — *"These are not hypotheticals; they're scars."*
PROVENANCE: `docs/archive/mcp-tool-design.md` §2.5
VOLATILE: none · TENSION: none.

**RULE:** Never persist a provider-local opaque id as the portable identity of a resource.
FIRE-SITE: Choosing what to store when capturing host state for later replay.
LAYER: L1 · KIND: constraint · EVIDENCE: broke-in-production(high severity) — `captured_session.json` carried `instrument_uri` like `"query:Drums#FileId_5418"`: *"Devon's browser does not have FileId_5418 (it's an id local to Maya's library). On push, `ableton_device(action='load')` will fail to find the instrument, or load something different. The whole sound of the song depends on instruments that don't survive a cross-machine handoff."*
PROVENANCE: `docs/archive/pre-v1-walkthrough.md` §7, §9 item 9
VOLATILE: none · TENSION: none.

**RULE:** Scope a display-name lookup to the canonical category root, and fail loudly naming the collision rather than falling back to a default — a user-saved item with the same name matches first and loads the wrong class silently.
FIRE-SITE: Resolving a host resource by human-readable name.
LAYER: L1 · KIND: diagnostic · EVIDENCE: broke-in-production — loading `kind='Drum Rack'` *"empirically loaded an `InstrumentGroupDevice`"* because a user-saved Instrument Rack preset named "Drum Rack" matched before the canonical node. Sibling case: a GM-default pitch fallback *"silently substituted the wrong sound"* (cowbell on metal).
PROVENANCE: `docs/archive/v11-requirements.md` Arc 4 D3, Arc 1 A3; `hallucinote_mcp/src/hallucinote_mcp/device_names.py:13`
VOLATILE: none · TENSION: none.

**RULE:** Accept the host's own internal class name as valid input (or auto-fall-back to its de-suffixed form) — rejecting the platform's canonical identifier is a bug the agent cannot reason around.
FIRE-SITE: Validating a `kind`/`class` parameter against a browser vocabulary.
LAYER: L1 · KIND: permission · EVIDENCE: broke-in-production — `kind='AnalogDevice'` was rejected *"even though `AnalogDevice` IS Live's internal `class_name`."*
PROVENANCE: `docs/archive/v11-requirements.md` Arc 4 D1
VOLATILE: none · TENSION: none.

**RULE:** Pin idempotency per *phase* of a sync tool and test the push→edit→push loop — one append-only phase doubles the target on every re-run.
FIRE-SITE: Shipping a "push my state to the host" tool users will run twice.
LAYER: L1 · KIND: constraint · EVIDENCE: broke-in-production(review finding) — *"Arrangement-clip placements are append-only on re-push… this means iterative push doubles the arrangement every time. Critical and easy to miss in casual testing."* The skill documented upsert semantics for the probe-and-link phase only.
PROVENANCE: `docs/archive/pre-v1-walkthrough.md` §4.3
VOLATILE: none · TENSION: none.

**RULE:** An MCP server that injects its own infrastructure into the user's document must make that infrastructure invisible to the document model *and* detect when a saved document carries a mis-placed copy.
FIRE-SITE: Adding a measurement tap, marker, or helper object into user state.
LAYER: L1 · KIND: constraint · EVIDENCE: broke-in-production(SNP-8R4K) — the `HallucinoteAnalyzer` tap must be the chain's terminal device; a set where authored devices loaded after it *"emits silently-wrong numbers."* Identity is centralised in one predicate consumed at every Live↔model boundary, plus a pure detector for the stale-set signature.
PROVENANCE: `src/hallucinote/analyzer_identity.py`; `src/hallucinote/analyzer_staleness.py`
VOLATILE: none · TENSION: none.

**RULE:** Check who reads each discovery surface — a message aimed at a human must not be written in call syntax the human cannot type.
FIRE-SITE: Writing the closing message of an install skill or a post-setup hand-off.
LAYER: L1 · KIND: diagnostic · EVIDENCE: broke-in-production(walkthrough finding) — the install skill printed *"try: `ableton_session(action='help')`"* to an end user. *"Maya can't type MCP calls. She types English."* Related: *"The MCP getting-started guide is great context for Claude — but the user doesn't see it."*
PROVENANCE: `docs/archive/pre-v1-walkthrough.md` §1.2, §1.4
VOLATILE: none · TENSION: none.

**RULE:** Pin every count you state about your own surface with a test — including the one in the install dialog, which is the count a user reads *before* installing and the one no README regex matches.
FIRE-SITE: Writing "N tools" / "N resources" anywhere.
LAYER: L1 · KIND: pattern · EVIDENCE: broke-in-production — four prose surfaces claim the tool count (server PRIMER, project README, package README, `marketplace.json`). Three were pinned by regexes matching *"N unified tools"*; `marketplace.json` says *"N Ableton Live tools"*, so it matched none and could drift on the most public surface. Fixed by `test_marketplace_manifest_tool_count_matches_actual_registry`, *"verified by mutating the manifest to 99 and watching the test fail."*
PROVENANCE: `hallucinote_mcp/tests/unit/test_server.py:59-143`
VOLATILE: none · TENSION: none.

---

## L2 — protocol semantics

**RULE:** Do not ship agent-facing workflows as MCP prompts in Claude Code — prompts surface only as user-typed slash commands, so the agent can never invoke one autonomously; ship a client-side skill, and use resources if you need cross-client reach.
FIRE-SITE: Deciding whether a multi-step recipe is a prompt, a tool, or a skill.
LAYER: L2 · KIND: permission (myth-buster) · EVIDENCE: broke-in-production — **all seven** prompts shipped in v0.9.0 were deleted in the next release: *"MCP prompts surface only as user-facing slash commands in Claude Code; the agent could never reach them autonomously. There is no assistant-callable `prompts/get` path."* The cost is stated and accepted: *"Other MCP clients that DO support assistant-callable prompts lose access… The cross-client path would be MCP resources (`ableton://recipes/<name>`) rather than prompts."*
PROVENANCE: `CHANGELOG.md:1057-1072`; `docs/archive/mcp-tool-design.md` §6, §6.2
VOLATILE: Claude Code's prompt-surfacing model (v0.9→v1.0 era, 2026). · TENSION: none.

**RULE:** Move to resources anything taking no per-call parameter or only a slow-changing identifier — resources are model-*pulled*, not model-*selected*, so they cost nothing in the tool-selection space; keep the parameterized form of the same read as a tool.
FIRE-SITE: Triaging which reads stay tools.
LAYER: L2 · KIND: decision-point · EVIDENCE: designed-untested — conversion table: `get_browser_tree` → `ableton://browser/{category}`; `list_external_plugins` → `ableton://plugins/installed`; `get_session_info` → `ableton://session/snapshot` *"(kept as tool too for 'give me this slice' usage)"*.
PROVENANCE: `docs/archive/mcp-tool-design.md` §2.3, §5.3
VOLATILE: none · TENSION: none.

**RULE:** Let a resource fan out into several handler calls — a resource read composes multiple backend calls without burning per-call agent turns, which is the composition a "snapshot" action would otherwise cost.
FIRE-SITE: Someone proposes a new `snapshot`/`overview` action.
LAYER: L2 · KIND: pattern · EVIDENCE: designed-untested — `ableton://session/snapshot` calls `handle_tool_call` three times (`session(info)` + `track(list)` + `return(list)`): *"the composition happens here (resource layer) rather than as a new action because resources can fan-out into multiple handler calls without burning per-call agent turns."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/resources/__init__.py:113-131`
VOLATILE: none · TENSION: none.

**RULE:** Publish a known-gaps resource — the canonical list of what NOT to attempt with the workaround for each — and point every teaching error at it.
FIRE-SITE: Deciding what reference material the server exposes.
LAYER: L2 · KIND: pattern · EVIDENCE: designed-untested — `ableton://guides/gaps`: *"The canonical list of CURRENT API gaps and their workarounds. The server returns teaching errors that point here — don't waste a turn discovering them."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/resources/guides/gaps.md`
VOLATILE: none · TENSION: none.

**RULE:** Publish capability as a tri-state matrix (SUPPORTED / NOT_IMPLEMENTED / UNSUPPORTED_IN_HOST), rendered from one typed in-code table that the runtime stubs and teaching errors also derive from — a binary "supported/not" cannot tell the agent whether to wait or to route around permanently.
FIRE-SITE: Exposing a feature × object-kind surface that is sparse.
LAYER: L2 · KIND: pattern · EVIDENCE: designed-untested (cross-consumer drift test) — *"Tri-state, because a binary 'supported / not' is a lie."* Cells also carry `determination: static | probe`, so device-specific verdicts are re-probed at runtime and a frozen "no" can't outlive a host update. A test asserts resource, stub responder and teaching error all resolve from the same `Cell`.
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/node_features.py:1-60`
VOLATILE: `DEFAULT_LIVE_VERSION = "12.4"` for the static verdicts. · TENSION: none.

**RULE:** Keep a blocked capability present in the surface as a tool returning a teaching "blocked" response rather than omitting it — omission surprises agents who never read the gap doc.
FIRE-SITE: Deciding whether to register a tool whose backend doesn't exist yet.
LAYER: L2 · KIND: decision-point · EVIDENCE: designed-untested — *"`ableton_note` exists even though blocked | Stable surface for agents; 'blocked' responses teach the gap | Alternative: omit until gap #4 lands; problem: surprises agents who don't read the gap doc."* Shipped registration still reads *"(gap #4 blocked)"*.
PROVENANCE: `docs/archive/mcp-tool-design.md` §15; `server.py:187`
VOLATILE: none · TENSION: none.

**RULE:** Never annotate a polymorphic MCP parameter as `typing.Any` — pydantic emits `anyOf: [{}, {"type":"null"}]`, and the empty `{}` branch tells the client nothing about serialization, so it emits strings unquoted and the payload dies in the *client's own* JSON parse before any request reaches you.
FIRE-SITE: Typing a genuinely polymorphic param (a generic `value`, a passthrough payload).
LAYER: L2 · KIND: constraint · EVIDENCE: broke-in-production, reproduced **6/6** — `{"value": SC Alien Duck}` / `^ never quoted` / `InputValidationError: could not be parsed as JSON`. Impact: device renaming had **no working path at all**, which mattered because `replay_capture` keys devices by `display_name` (three Compressors on one track were indistinguishable). Fix is an explicit union over every JSON type, pinned by `test_annotated_param_type_any_is_explicit_not_fallback`.
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/server.py:37-53`; `incoming-bugs/archives/2026-09-10-sidechain-authoring-blockers.md` §4
VOLATILE: JSON Schema `anyOf` handling in the client's tool-arg serializer (Claude Code, 2026-09). · TENSION: depends on the coercion rule below.

**RULE:** In that union, order `bool` before `int` (bool is an int subclass) and keep `int` as its own branch so an integer is never widened to float.
FIRE-SITE: Writing the union; debugging "the native API rejected my value".
LAYER: L2 · KIND: constraint · EVIDENCE: broke-in-production — *"Live's C++ setters reject a float where the signature wants an int."* Both hazards are invisible in Python and fatal at the native boundary. The dispatcher carries the mirror guard: an `int`-typed param explicitly rejects `bool`.
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/server.py:46-51`; `dispatcher.py:207-213`
VOLATILE: none · TENSION: none.

**RULE:** Recover the JSON type of a string-valued arg by parsing it as a JSON literal — and gate the parse on the target's *current* type, so a string-valued property isn't corrupted.
FIRE-SITE: Handling a schema-typed `any` param.
LAYER: L2 · KIND: pattern · EVIDENCE: broke-in-production — *"a client with no type information to work from serializes every scalar as a string, so `value=5` arrives as `"5"` and `setattr` hands a `str` to a Boost.Python setter whose C++ signature takes an `int`; Live rejects the write outright (`did not match C++ signature`)."* The `current` gate is why *"a track named `"808"` keeps its name instead of being handed the integer 808."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/handlers/probe.py:221-244`
VOLATILE: client string-coercion behaviour. · TENSION: is the mitigation for the `Any` rule.

**RULE:** Push `description`, `minimum`/`maximum` and `enum` into the generated JSON Schema via `Annotated[..., Field(...)]`, not just the Python type — the payoff is the agent pruning impossible calls before dispatch instead of round-tripping through your error.
FIRE-SITE: Translating an internal param spec into the MCP-visible schema.
LAYER: L2 · KIND: pattern · EVIDENCE: broke-in-production(gap found in review) — *"Agents saw `Optional[int]` for `cc_number` (no 0–127 bound), `Optional[str]` for `target_kind` (no seven-value enum), and no descriptions."* Runtime-data enums go in `json_schema_extra`, not `Literal[...]`, because the dispatcher stays the rejection authority.
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/server.py:68-96`
VOLATILE: FastMCP/pydantic schema derivation. · TENSION: none.

**RULE:** Version two halves of one source tree by a **content fingerprint**, never semver — semver communicates compatibility to a consumer who *chose* their version, and the only question here is "are these byte-identical?", which a hand-maintained number answers badly because bumping it is exactly what gets forgotten.
FIRE-SITE: Adding a version/staleness signal between a server and code it deploys elsewhere.
LAYER: L2 · KIND: decision-point · EVIDENCE: broke-in-production — the fingerprint exists because of *"the W2-5 root cause behind hours of debugging when chunks A/B/C/D's source updates hadn't propagated into Live's User Library"*; `architecture.md` calls it *"the worst debugging session in this project's history."* A prior signature field was a hardcoded label that *"structurally cannot detect staleness."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/__init__.py:1-16`; `.prawduct/artifacts/api-contract.md:39-56`
VOLATILE: none · TENSION: costs a forced re-vendor on every wire edit.

**RULE:** The hashed path set must equal the code that is **both shipped to and executed in** the remote runtime — over-inclusion trains users to ignore re-vendor demands; a contract-only hash under-prompts exactly when they need the fix.
FIRE-SITE: Editing the fingerprint path list.
LAYER: L2 · KIND: constraint · EVIDENCE: broke-in-production(MCP-7F2K) — `handlers/` was hashed wholesale and contained a `runs_server_side=True` module that never runs in the host, so *"a read-side analysis fix flipped the handshake and nagged every user to re-vendor."* The rejected alternative is the instructive half: hashing only the declared contract *"would suppress re-vendor for Live-side handler bug fixes — Live would keep running the old, buggy vendored handler with no prompt to update."* Fix relocated server-only code into a top-level package excluded **by construction, not by list maintenance**, locked by `test_server_side_isolation.py`.
PROVENANCE: `.prawduct/artifacts/mcp-fingerprint-design.md`; `hallucinote_mcp/src/hallucinote_mcp/__init__.py:24-52`
VOLATILE: none · TENSION: creates the silent-drift hole the next rule closes.

**RULE:** Run **two** fingerprints with different blocking postures — a narrow hard one over the executed wire surface that refuses, and a wide advisory one over everything you ship that only recommends — and name which one a verdict came from.
FIRE-SITE: Narrowing a fingerprint; writing the install/preflight report.
LAYER: L2 · KIND: pattern · EVIDENCE: broke-in-production(RND-2R9K, then fixed) — a Live-executed change to `analyzer/setup.py` sat outside the hashed set, so *"the version handshake reports `matched` against a STALE vendored Remote Script."* The advisory `vendored_content_fingerprint` is *"deliberately wider than the handshake's `_FINGERPRINT_PATHS` … It must never gate anything."* Preflight surfaces `matches_vendored_content` + `differing_paths` beside `matches_mcp_server`; the install skill treats it as *"a recommendation, never a refusal."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/install_paths.py:144-166`; `.prawduct/learnings.md:331`
VOLATILE: none · TENSION: resolves the previous rule's cost.

**RULE:** Normalize line endings before hashing (and skip normalization for files containing a NUL byte) — without it the same source tree fingerprints differently depending on how it was checked out, and the handshake refuses semantically identical code.
FIRE-SITE: Writing the hash helper.
LAYER: L2 · KIND: constraint · EVIDENCE: designed-untested, self-defending — *"without this, the same source tree produces different fingerprints depending on how it was checked out."* NUL-sniffing exists so a future non-Python entry doesn't get `b"\r\n"` silently corrupted. Both hashers share one helper *"so the two can never drift on line endings or on how a path is keyed into the hash."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/__init__.py:96-131`
VOLATILE: git `autocrlf`. · TENSION: none.

**RULE:** Never format a content fingerprint so it reads like a VCS identifier, and test any recovery recipe your error prints by *executing* it against a fixture.
FIRE-SITE: Choosing a version-string format; writing version-mismatch recovery text.
LAYER: L2 · KIND: diagnostic · EVIDENCE: broke-in-production — a refusal read `0.1.0+c9abab64204b` vs `0.1.0+ad27853ce72a` and the recovery text said the suffix *"is the commit it was vendored from … `git worktree add /tmp/hallucinote-pin <sha>`"*. `git cat-file -t` rejects both. The message now says outright it is *"a fingerprint of the package's CONTENT, not a git commit — `git cat-file -t` will reject it, and no checkout of it exists"*, guarded by `test_version_mismatch_recovery_pin_recipe_actually_pins`, **which runs the printed recipe**.
PROVENANCE: `incoming-bugs/archives/2026-09-09-version-pin-recovery-sha-is-a-content-fingerprint.md`
VOLATILE: none · TENSION: none.

**RULE:** Carry your version on every request so a stale counterpart reports as version drift rather than a spray of "unknown action" errors.
FIRE-SITE: Designing the wire envelope between two separately-installed halves.
LAYER: L2 · KIND: pattern · EVIDENCE: broke-in-production — strict equality is deliberate: *"the cost of a false positive (re-run install) is tiny compared to the cost of a false negative (silent 'unknown action' errors that take minutes to diagnose — the exact failure mode that motivated this check)."* An empty field means *"MCP server too old to handshake"* and gets its own branch.
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/wire.py:35-52, 216-290`
VOLATILE: none · TENSION: none.

**RULE:** Give a strict version handshake a per-call, opt-in bypass that attaches a loud warning to its own response, and name the flag in the refusing error's `hint` so it is discoverable through the error path.
FIRE-SITE: Shipping a strict wire gate on a protocol you also develop against daily.
LAYER: L2 · KIND: permission · EVIDENCE: designed-untested (3 end-to-end TCP integration tests) — added because *"every server-side Python edit currently requires reinstall + Live restart before any introspection call."* The bypass is uniform by design: *"We don't pretend introspection-vs-mutation can be safely distinguished at the dispatcher layer."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/wire.py:293-340`; `.prawduct/change-log-archive.md:3855-3866`
VOLATILE: none · TENSION: qualifies the strict-equality rule above.

**RULE:** Return still-running work as `ok=True` plus a machine-readable `code` discriminator and a job handle — and serialize `code` on the success path too, or a consumer cannot tell a completed call from an escalated one.
FIRE-SITE: Designing the response envelope for a backend that can outrun its ceiling.
LAYER: L2 · KIND: pattern · EVIDENCE: designed-untested, with a named regression it prevents — *"An escalation is ok=True by design — the work is observable, not failed — so if `code` only survived on errors, a consumer would have no machine-readable way to tell a handle to still-running work from a completed operation, and the difference is whether the thing it asked for has happened yet."* The client's response deserializer carries the same note about not dropping `code` on the ok path.
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/wire.py:130-150, 205-213`; `client.py:_response_from_dict`
VOLATILE: none · TENSION: depends on the escalation rule (L3).

**RULE:** Signal internal control flow with a structured flag that is deliberately *not* serialized to the wire — never by parsing your own error text downstream, and never by leaking server internals to the client.
FIRE-SITE: Deciding how a validating front-half tells a forwarding layer "this needs the backend".
LAYER: L2 · KIND: pattern · EVIDENCE: designed-untested — `Response.needs_remote` is *"intentionally not serialized to the wire — it would leak server-internal detail to the MCP client."* The dispatcher comment: *"Signal 'forward me' with a structured flag, not by parsing error text downstream."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/wire.py:100-112`; `dispatcher.py:565`
VOLATILE: none · TENSION: none.

**RULE:** Stamp every result with the content identity of the code that produced it plus a `stale` flag versus disk — a long-lived server process serves cached imports, so a report can be produced by pre-edit code with nothing in the payload saying so.
FIRE-SITE: Returning any analysis/measurement result from a long-lived server.
LAYER: L2 · KIND: pattern · EVIDENCE: broke-in-production — *"The MCP server caches imported analysis modules, so an edit to `hallucinote.audio` isn't picked up until `/mcp` respawns the subprocess."* The signature is **frozen at import** (the code actually loaded) and compared against a per-call disk recompute: *"Hashing only on-disk source would report 'fresh' while the process runs old code."* Surfaced to the agent as `analysis_code = {signature, stale}` with the tip *"run `/mcp` to respawn before trusting the report."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/server_side/analysis.py:247-256`; `.prawduct/learnings-detail.md:121-126`
VOLATILE: none · TENSION: same mechanism as `stale_server_process_hint` (L4).

**RULE:** Tool names and action names are permanently stable — alias, never rename. But if your installer deploys both halves together and a handshake makes "old client meets new server" unreachable, ship **no** compatibility shims at all.
FIRE-SITE: Wanting to fix a bad action name.
LAYER: L2 · KIND: decision-point · EVIDENCE: designed-untested (two documents, one conditioned on deployment topology) — the general policy is *"Tool names never change. Actions never change (deprecated, yes; renamed, no)"* with the deprecation warning returned **in the result**. The conditioned override: *"there is no window in which an old client meets a new server — the handshake makes that state unreachable. So a wire-shape change does not need a back-compat path, and adding one is actively discouraged (it is code with no caller, which decays)."* The retired synchronous `render` was **hard-deleted**, not stubbed.
PROVENANCE: `docs/archive/mcp-tool-design.md` §3/§8.2; `.prawduct/artifacts/api-contract.md:88-100`
VOLATILE: none · TENSION: the two halves of this rule disagree unless the topology precondition holds — state the precondition.

---

## L3 — transport & operations

**RULE:** Anything that can exceed the host's tool-call timeout gets `start` (returns a job handle immediately) + `status` (long-polls) — progress notifications do **not** reset the host's wall clock, there is no wake-on-done, and the limit is transport-agnostic, so changing transport is not a fix.
FIRE-SITE: Designing a tool whose cost scales with user content.
LAYER: L3 · KIND: pattern · EVIDENCE: broke-in-production — the synchronous `render` action was **retired**. *"A synchronous call that outruns it returns a false failure — the agent sees an error while the work actually finished server-side."* Verified against current docs plus an open client bug, not recalled: *"Confirmed identical across stdio, HTTP+SSE, and Streamable HTTP — so changing transport changes nothing (HTTP/SSE even imposes a 60s first-byte minimum). Transport is considered & rejected."*
PROVENANCE: `.prawduct/artifacts/plans/MCP-ASYNC-RENDER-ANALYZE/archive/build-plan.md` §Design Pivot; `handlers/jobs.py:1-20`
VOLATILE: Claude Code bug #58687 (progress notifications don't extend the timeout); per-server `timeout` = 60000 ms here. · TENSION: none.

**RULE:** Size the long-poll window comfortably under the host tool-call timeout, keep the socket read timeout just above the long-poll, define the window **once** for every status handler, and raise all three together.
FIRE-SITE: Tuning a long-poll.
LAYER: L3 · KIND: constraint · EVIDENCE: designed-untested (explicit ladder) — 45 s long-poll under a 60 s host timeout *"leaving ~15s for forward + serialize"*; `_STATUS_READ_TIMEOUT` 60 s sits above it *"so the socket never severs the wait"*. `DEFAULT_STATUS_LONG_POLL_S` lives in `jobs.py` shared by render and analyze — *"one knob, not two that drift."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/handlers/jobs.py:36-50`; `client.py:_STATUS_READ_TIMEOUT`
VOLATILE: 45 s / 60 s / 60000 ms. · TENSION: violated by this repo's own device-load ceilings — see the ladder rule below.

**RULE:** Make every tool wrapper `async` and push the blocking dispatch through `anyio.to_thread` — FastMCP runs a synchronous tool **inline on the event loop**, so one blocking `def` freezes every other in-flight call for the whole wait.
FIRE-SITE: Adding a tool handler; reviewing a diff that turns `async def` back into `def`.
LAYER: L3 · KIND: constraint · EVIDENCE: broke-in-production(found by a chunk review, verified in `mcp==1.26.0`) — *"`func_metadata.call_fn_with_arg_validation` does `return fn(**args)` for a sync fn, no `to_thread`."* The design's hard requirement ("a concurrent unrelated call must not hang behind a running job") *"was unmet for BOTH render and analyze… The single-agent start→poll→poll flow never noticed (the polling agent is the sole caller and intends to wait), but the guarantee was hollow."* Ratified as availability, not style: *"Reverting a handler to plain `def` is a whole-server availability bug."* Pinned by `test_status_longpoll_does_not_block_concurrent_tool_calls` and `test_tool_wrappers_are_async_*`.
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/server.py:786-812`; api-notes §"Dispatch fix"
VOLATILE: FastMCP's inline-sync-tool execution model; `mcp==1.26.0`. · TENSION: creates the concurrency the next rule must handle.

**RULE:** The next ceiling after the event loop is the thread-pool limiter, not the loop — `anyio.to_thread.run_sync` draws from a default capacity of **40**; raise the limiter rather than re-architecting.
FIRE-SITE: Scaling an async-wrapper server past a handful of concurrent callers.
LAYER: L3 · KIND: diagnostic · EVIDENCE: designed-untested (forward-note) — *"Each in-flight `status` long-poll occupies one thread for up to ~45s, so the 41st concurrent tool call would queue behind the busy threads (the loop itself stays free — this is a thread-pool bound, not the inline-block bug)."*
PROVENANCE: api-notes §"Forward-note"
VOLATILE: anyio default 40. · TENSION: depends on the async-wrapper rule.

**RULE:** The moment your dispatch becomes concurrent, a check-then-create busy guard becomes a real race — make the claim atomic under one lock.
FIRE-SITE: Adding an "only one at a time" guard.
LAYER: L3 · KIND: constraint · EVIDENCE: measured (32-thread atomicity test) — *"the busy guard became a real race once dispatch is concurrent, so the `active()`-then-`create()` check was replaced with an atomic `JobRegistry.create_if_idle()` (one lock acquisition; exactly one of N concurrent starts claims the slot)."* The now-dead `active()` and its two self-tests were deleted rather than kept.
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/handlers/jobs.py:230-260`
VOLATILE: none · TENSION: depends on the async-wrapper rule.

**RULE:** Put the per-(tool, action) read-timeout policy at the lowest chokepoint every receive route shares, with auto-resolution when the caller doesn't pass one — a policy installed at one call site leaves every other route on the bare default.
FIRE-SITE: Fixing a timeout on a long-held call; adding a second dispatch path to the same backend.
LAYER: L3 · KIND: pattern · EVIDENCE: broke-in-production(ENV-9P4T; a review declared the first fix resolved) — the first fix added the entry to `server.py`'s table, which only the agent-forward route reads. The feature's *primary* consumer, `push_cli execute`, called `client.send(req)` with no timeout, hit the 15 s default and talked to the backend directly: a 16-bar fade ≈ 32 s → `socket.timeout` → classed `connection_lost` → halt, *"discarding the only verification this write-only surface has"* while the host kept recording. The dev smoke driver's hard-coded 180 s override was simultaneously the proof and the mask. Corollary recorded: *"A test/dev harness's hard-coded override is a RED FLAG, not a convenience."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/client.py:30-120`; `.prawduct/learnings-detail.md:527-531`
VOLATILE: none · TENSION: none.

**RULE:** A caller-side read timeout must **exceed** the callee's own ceiling by a real margin covering admission wait, serialization and travel — a timeout that merely *matches* the ceiling always expires first, which makes the callee's teaching message provably unreachable.
FIRE-SITE: Setting any pair of timeouts that bound the same operation from opposite ends.
LAYER: L3 · KIND: constraint · EVIDENCE: broke-in-production — *"The pairing this table used to carry (120/120, 90/90, and the implicit 15/15 default) made Live's timeout message — 'IT IS STILL RUNNING on Live's main thread … Do not retry immediately' — provably unreachable. The agent got a bare `FrameError` ('socket read timed out') instead, losing the one instruction that stops it deepening the queue behind an operation Live cannot cancel."* A test pins `_LIVE_REPLY_MARGIN_S` > the admission wait.
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/client.py:63-84`
VOLATILE: `_LIVE_REPLY_MARGIN_S = 5.0`, `_BUSY_ADMIT_WAIT_S = 2.0`. · TENSION: **this repo violates its own rule one layer out** — see the next entry.

**RULE:** The timeout ladder must be monotonic *all the way out to the host* — host tool-call timeout > your socket read timeout > the backend's ceiling — or the outermost rung silently eats every teaching error below it.
FIRE-SITE: Raising an inner ceiling above a default you did not set.
LAYER: L3 · KIND: diagnostic · EVIDENCE: measured(my own verification against the tree — reported as a **finding**, not a practice) — `plugin.json` declares `"timeout": 60000` (60 s per tool call), but `client.py` sets `ableton_render(ensure_loaded)` **180 s**, `ableton_device(load)` **125 s**, `ableton_device(get_parameters)` **95 s**, and `actions/device.py` sets Live-side ceilings of **120 s** and **90 s**. For those three actions the host cuts the call at 60 s first, so neither the socket's structured `FrameError` nor the Live-side `work_escalated` handle can ever reach the agent — the exact false-failure class the synchronous `render` was retired for. Corroborating: the 2026-09-10 live sitting recorded victims dying as *"bare `FrameError: socket read timed out after 20.0s` … No `work_escalated`, no job id, no `LiveBusyError`."* The comment justifying the 120 s ceiling (*"Live blocks for tens of seconds instantiating [the .amxd]"*) was re-measured at **1.95 s cold / 0.89 s warm** and never revisited.
PROVENANCE: `.claude-plugin/plugin.json:32`; `hallucinote_mcp/src/hallucinote_mcp/client.py:100-112`; `actions/device.py:169,216`; `.prawduct/operator-verification.md:168-176`
VOLATILE: 60000 ms host timeout; Live 12.4.5 load measurements. · TENSION: contradicts the margin rule above; both are true, at different rungs.

**RULE:** A timeout on an uncancellable operation is not a cancellation — hold the admission gate with the **runner**, released only by the callback's own completion, never by the waiter giving up, and never by a timer.
FIRE-SITE: Building any watchdog over a single-threaded, uninterruptible backend.
LAYER: L3 · KIND: pattern · EVIDENCE: designed-untested (deep rationale, extensively fake-tested) — *"If the admission gate were released at that moment, it would refuse callers who arrive *while* we wait and admit callers who arrive *after* we stop — open exactly when a retry would stack more work behind an operation Live cannot abandon."* No timed auto-clear exists on purpose: *"clearing on a timer is the same defect on a delay."* The escape hatch is an explicit operator `abandon_bout` whose response says the work may still be running.
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/remote_script/dispatch.py:1-35, 400-470`
VOLATILE: none · TENSION: its reach is bounded by the "watchdog only fires on paths that reach it" finding below.

**RULE:** Return a slow call as a **handle, not a failure** — `ok=True`, a job id, the elapsed time, and text that explicitly forbids retry while naming the consequence of retrying.
FIRE-SITE: Writing the ceiling-exceeded path.
LAYER: L3 · KIND: pattern · EVIDENCE: designed-untested — shipped text: *"This call has NOT failed and has NOT finished — it is still running on Live's main thread and cannot be cancelled. Poll it with `ableton_session(action='bout_status', job_id=…)` … Do NOT retry the original call: another call now queues behind the one still executing, which is how a slow operation becomes an unresponsive Live."* Not logged at exception level, *"kept ahead of the broad catch so it never reads as 'the action is broken'."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/dispatcher.py:590-630`
VOLATILE: none · TENSION: none.

**RULE:** Refuse a concurrent caller after a bounded admission wait rather than queueing it — a thread-per-connection server has no other throttle, and a refusal means "never attempted", so nothing is in an unknown state.
FIRE-SITE: Fronting a single-threaded backend from a concurrent server.
LAYER: L3 · KIND: pattern · EVIDENCE: **measured live** — 12 concurrent `device.load` calls produced 5 `LiveBusyError` refusals naming the running operation and its elapsed time, arriving at **2.3–2.8 s** (consistent with the 2.0 s admission wait); *"No queue formed; the other 7 completed normally."* Rationale: *"The TCP server spawns a thread per connection with no admission control, so nothing else throttles that pile-up: one slow operation becomes an unresponsive Live."*
PROVENANCE: `.prawduct/operator-verification.md:209-217`; `remote_script/dispatch.py:145-160`
VOLATILE: `_BUSY_ADMIT_WAIT_S = 2.0`; Live 12.4.5. · TENSION: none.

**RULE:** A watchdog in your own code can only fire on paths that reach it — when the *host* blocks rather than your call being slow, your request never reaches the ceiling and the caller gets an undifferentiated socket timeout. Verify a fence against the condition in the original report, not the condition your fakes can model.
FIRE-SITE: Shipping a watchdog over a third-party process you cannot instrument.
LAYER: L3 · KIND: diagnostic · EVIDENCE: **broke-in-production, measured live 2026-09-10 (Live 12.4.5)** — three operator wedges (Preferences open, held menu, held fader, ~20 s each) did *not* block the scheduler. A real mp3 export did: *"exactly one break in served calls, 09:45:05 → 09:46:06, a 61.5 s gap — four times the 15 s ceiling."* Two in-flight calls died as bare `FrameError` at 20 s. *"The worker never reaches the wait, so the ceiling is unreachable by construction rather than mis-tuned."* Conclusion: *"The fence bounds a slow Live API call; it does nothing about a blocked Live, which is the condition that produced the original beachball. From the client the shipped fix is invisible."* Four of six verification boxes were **UNREACHABLE** because the triggering condition can no longer be produced. Filed as #531.
PROVENANCE: `.prawduct/operator-verification.md:155-240`
VOLATILE: Live 12.4.5 scheduler. · TENSION: bounds the two escalation rules above; **also contradicts a shipped agent-facing claim** — see Disagreements.

**RULE:** Back an in-memory job registry with a crash-resilient on-disk heartbeat, and make the unknown-job error distinguish "wrong id" from "the server restarted".
FIRE-SITE: Designing job state for a start+poll surface.
LAYER: L3 · KIND: pattern · EVIDENCE: designed-untested (with the failure it prevents named) — `status.json` is written at start, refreshed each poll, and written terminally *"whether the render succeeded or raised"*, because *"manifest.json is the only completion signal today, forcing fragile dir-watching."* The unknown-job error names recent job ids, or says *"no render jobs have been started in this server process"*; the action tip states *"job state lives in the server process, so it resets when the MCP server restarts."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/handlers/render.py:186-215, 1276-1290`
VOLATILE: none · TENSION: none.

**RULE:** Keep the running heartbeat out of the terminal payload — mirror only *running* progress into the job's `progress`, and reflect the terminal write through `state` + `result`.
FIRE-SITE: Wiring a status writer into a job record.
LAYER: L3 · KIND: constraint · EVIDENCE: designed-untested, pinned — `test_terminal_heartbeat_does_not_leak_into_progress` asserts `job.progress == {"state": "running", "current_beat": 8}` and `"manifest_path" not in job.progress` after a terminal write.
PROVENANCE: `hallucinote_mcp/tests/unit/test_async_render.py:169-192`
VOLATILE: none · TENSION: none.

**RULE:** Name every job kind explicitly in the terminal-payload branch — a bare `else` hands one kind's key names to the next kind someone adds.
FIRE-SITE: Building the terminal result shape for a multi-kind job registry.
LAYER: L3 · KIND: constraint · EVIDENCE: designed-untested, pinned — *"Every kind is named: a bare `else` would hand one kind's key names to the next kind that gets added."* Pinned by `test_main_thread_status_does_not_borrow_analyzes_terminal_keys`. Per-kind facts ride a `detail` dict on **both** start and status *"rather than one per-kind field apiece: three kinds through a two-way `if kind ==` branch is how the fourth becomes unwritable."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/handlers/jobs.py:116-160`
VOLATILE: none · TENSION: none.

**RULE:** An advisory the backend raised without refusing must be allowlisted onto the status payload *and* relayed by whatever orchestrates the poll — and only present when there is one, so "nothing to say" and "said nothing" are different payloads.
FIRE-SITE: Adding a non-fatal warning to a long-running job's result.
LAYER: L3 · KIND: constraint · EVIDENCE: designed-untested — *"This allowlist is the ONLY path from a render result to a caller, so a handler that adds an advisory and stops here has added nothing."* The `/render-analyze` subagent brief repeats it: *"keep `warning` whenever the status carries it… dropping it here is the one place the operator can no longer learn the capture is not the mix as authored."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/handlers/jobs.py:135-152`; `skills/render-analyze/SKILL.md`
VOLATILE: none · TENSION: none.

**RULE:** Know that going start+poll moves input-validation errors from the call's return to the poll — decide deliberately whether `start` validates synchronously or `status` carries the diagnosis, and say which in the action tips.
FIRE-SITE: Converting a synchronous action to start+poll.
LAYER: L3 · KIND: decision-point · EVIDENCE: designed-untested (they chose the poll and documented it) — shipped tip: *"Input errors (typo'd slug, no captures dir) surface via status as `state='failed'` with the teaching error — start returns a handle first, then status carries the diagnosis."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/server_side/analysis_actions.py:281-284`
VOLATILE: none · TENSION: none.

**RULE:** Explicitly clear the socket timeout when you mean "block indefinitely" — `socket.create_connection`'s *connect* timeout carries over to reads and will silently bound them.
FIRE-SITE: Implementing an unbounded read.
LAYER: L3 · KIND: constraint · EVIDENCE: designed-untested (named in the docstring) — *"Without the explicit clear, `socket.create_connection`'s connect timeout would carry over and bound the read at 15 s even when the caller intends to wait."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/wire.py:400-425`
VOLATILE: Python socket semantics. · TENSION: none.

**RULE:** Use TCP with 4-byte length-prefixed JSON for a local bridge, not UDP — UDP's 64 KB datagram cap cannot carry a browser tree or a session snapshot; cap the declared length and reject anything above it as a corrupt stream.
FIRE-SITE: Choosing the transport between an MCP server and an in-process host plugin.
LAYER: L3 · KIND: decision-point · EVIDENCE: designed-untested, with the scratch-note correction recorded in the code — *"TCP (not UDP, despite some early scratch notes saying otherwise)"*; 16 MiB cap *"guards runaway prefixes."* Port chosen to differ from the legacy fork's *"so both can coexist while a user migrates."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/wire.py:1-30`
VOLATILE: none · TENSION: the design doc says UDP — see Disagreements.

**RULE:** Use short-lived per-request connections rather than a pooled one — no reconnect logic, no shared-socket race under concurrency, no head-of-line blocking, and loopback latency makes the cost negligible.
FIRE-SITE: Designing the server↔host-plugin connection.
LAYER: L3 · KIND: decision-point · EVIDENCE: designed-untested, load-bearing for the async fix — *"Short-lived connections (per request) keep the model simple."* Cited as a precondition when adopting concurrent dispatch: *"De-risked before adopting: `client.send` opens a fresh socket per call (no shared-socket race under true concurrency)."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/client.py:1-13`; api-notes §"Dispatch fix"
VOLATILE: none · TENSION: precondition for the async-wrapper rule.

**RULE:** Keep the server stdlib-only **at module import time** and lazy-import the heavy engine at call time — and if the package is also loaded by a constrained embedded interpreter, machine-check the whole load chain for stdlib modules that interpreter lacks.
FIRE-SITE: Adding any module-scope import.
LAYER: L3 · KIND: constraint · EVIDENCE: broke-in-production — a handler had `import sqlite3` at module top; **Live 12.x's embedded Python ships without the `_sqlite3` C extension**, and the cascade aborted the entire Control Surface load. Symptom: *"Live shows the surface in the dropdown but the MCP bridge on 127.0.0.1:9878 never starts"* — with no stack trace in the UI, only `Log.txt`. Worst part: the import was **dead code** under `from __future__ import annotations`, *"so it cost nothing and broke everything."* Fix is an AST walk of the load chain (runtime import would fail for the wrong reason, and the host Python *having* sqlite3 is why the bug is invisible at test time).
PROVENANCE: `hallucinote_mcp/tests/unit/test_remote_script_import_safety.py:1-60`; `CHANGELOG.md:731-735`
VOLATILE: Live 12.x missing `_sqlite3`. · TENSION: none.

**RULE:** Resolve paths, defaults and identifiers on the side that has the context, *before* forwarding — the process that executes your call may have a different cwd, a read-only filesystem, and none of your dependencies importable.
FIRE-SITE: Accepting a path or a resolvable identifier on a forwarded action.
LAYER: L3 · KIND: constraint · EVIDENCE: broke-in-production — *"the render worker runs inside Live's process whose cwd is `/` (read-only on macOS), so relative paths like `songs/<slug>/captures/<ts>` fail with OSError [Errno 30]."* The MCP server also picks the timestamp *"rather than letting the handler do it"* to avoid time-of-check/time-of-use drift between the announced and created directory. Same constraint drives `_attach_render_db_seq` (*"the render handler runs inside Live's vendored env (no hallucinote package), so the seq is read HERE"*) and the audit-event write.
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/server.py:493-560`
VOLATILE: macOS read-only `/`. · TENSION: none.

**RULE:** Put a seatbelt in front of any large-output write whose destination came from a resolver — a resolver that is wrong plus `mkdir(parents=True)` invents a whole plausible tree and fills it, and nothing downstream looks wrong.
FIRE-SITE: Writing a tool that creates directories from a derived default.
LAYER: L3 · KIND: pattern · EVIDENCE: broke-in-production — *"the capture is written, so nothing downstream looks wrong until analysis reports the song 'isn't built' and the operator discovers ~290 MB parked in a phantom `songs/<slug>/`."* The guard is scoped so it can never block legitimate work: only the *derived default*, only when the resolver is available, only on a missing directory.
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/server.py:424-490`
VOLATILE: none · TENSION: none.

**RULE:** On stdio, stdout is the wire — route your own logging, and any subprocess you spawn, to stderr; and if your host injects hook stdout into the model's context, that channel has the same discipline in reverse.
FIRE-SITE: Adding a `print`, a logger, or a `subprocess.run` anywhere in a stdio server or its hooks.
LAYER: L3 · KIND: constraint · EVIDENCE: designed-untested, two concrete instances — `serve.py` pins `logging.basicConfig(stream=sys.stderr)`; the SessionStart pre-warm hook states *"a hook's plain stdout IS injected into Claude's context, so EVERY branch keeps human/progress/skip chatter on stderr"* and routes `uv sync`'s own stdout to stderr (`stdout=sys.stderr`) so the success branch's stdout is a clean JSON object.
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/cli/serve.py:33-38`; `hooks/prewarm_mcp_env.py:1-30, 85-92`
VOLATILE: SessionStart `additionalContext` contract. · TENSION: none.

---

## L4 — client/host integration

**RULE:** A plugin manifest's per-server `timeout` governs **tool execution**, not the startup handshake — the spawn window is `MCP_TIMEOUT` (env var, ms, default 30000), a plugin manifest cannot set it, and the only channel that reaches a plugin-provided server's spawn is `env` in the user's `settings.json`.
FIRE-SITE: Shipping an MCP server whose first launch builds or downloads anything; debugging "my tools didn't appear".
LAYER: L4 · KIND: constraint · EVIDENCE: **measured, broke-in-production** — INS-7V2D shipped `"timeout": 60000` as the mitigation for a cold `uv sync` of ~70 MiB (numpy/scipy/librosa). The connection log proved it never applied: *"Starting connection with timeout of 30000ms … Connection timeout triggered after 30004ms."* Failure mode is a **silent tool drop** (CC#60224), not an error. Fix raises `MCP_TIMEOUT` to a 180000 ms floor via settings `env`; a genuinely cold cache then connected on first launch. Warm handshake measured **~2.3 s**.
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/mcp_config.py:1-40`; `.prawduct/learnings-detail.md:501-518`; `.prawduct/operator-verification.md:1216-1243`
VOLATILE: `MCP_TIMEOUT` default 30000 ms; CC#60224; plugin `timeout` semantics. · TENSION: `plugin.json` still carries the now-inert 60000 — see the ladder finding (L3).

**RULE:** A SessionStart pre-warm hook is not the mitigation for a slow startup — it races the spawn and cannot block it. Make it best-effort, never fail the session, and give it a real job: telling the user a cold build is in progress.
FIRE-SITE: Designing the cold-start story for a plugin-bundled server.
LAYER: L4 · KIND: permission (myth-buster) · EVIDENCE: broke-in-production(root-cause correction) — *"SessionStart hooks RACE the MCP spawn and cannot block it."* The shipped hook is explicitly *"Belt-and-suspenders, not load-bearing… NEVER fails the session"*, uses a lock-file diff so it is a no-op when warm, and emits `additionalContext` telling the agent how to explain a failed `/mcp` entry. Pinned by 9 tests including `test_missing_uv_never_fails_the_session` and `test_failed_sync_never_fails_the_session_and_retries_next_time`.
PROVENANCE: `hooks/prewarm_mcp_env.py`; `.prawduct/learnings.md:247-257`
VOLATILE: hook-vs-spawn ordering (2026-06). · TENSION: depends on the `MCP_TIMEOUT` rule being the real fix.

**RULE:** When tools vanish or misbehave at startup, read the client's own connection log before theorizing — it prints the timeout actually in force, which immediately tells you whether the config you set is the one being applied.
FIRE-SITE: Debugging a stdio server whose stdout the client owns.
LAYER: L4 · KIND: diagnostic · EVIDENCE: measured — the `MCP_TIMEOUT` misdiagnosis was resolved from `~/Library/Caches/claude-cli-nodejs/<proj>/mcp-logs-*/`, which printed a literal `30000ms` against a config asserting 60000. *This is the project's only named answer to "how do you observe a stdio server you cannot print to."*
PROVENANCE: `.prawduct/learnings-detail.md:513-518`
VOLATILE: macOS log path. · TENSION: none.

**RULE:** Launch a distributed MCP server through a locked, project-pinned runner from the distribution root — never a bare PATH console-script name, which decouples the running server from the installed version.
FIRE-SITE: Writing the `mcpServers` block in a plugin manifest.
LAYER: L4 · KIND: pattern · EVIDENCE: broke-in-production(INS-7V2D) — the bare `command: hallucinote-mcp` *"decoupled the running server from the plugin version and needed the install skill's abs-path-override hack."* Contract pinned by `test_launch_uses_uv_not_a_bare_path_binary`: *"NEVER revert to the PATH-dependent bare console-script."*
PROVENANCE: `.claude-plugin/plugin.json:25-33`; `hallucinote_mcp/tests/unit/test_plugin_manifest.py:32-54`
VOLATILE: `uv run --frozen --all-packages --project`. · TENSION: none.

**RULE:** Redirect the runner's environment into the host's writable plugin-data directory — the plugin root is read-only and ephemeral, so the venv cannot live there and must survive updates.
FIRE-SITE: Same manifest edit.
LAYER: L4 · KIND: constraint · EVIDENCE: designed-untested, pinned — `UV_PROJECT_ENVIRONMENT=${CLAUDE_PLUGIN_DATA}/venv`, asserted by `test_env_redirects_venv_into_persistent_plugin_data`: *"read-only ROOT, persistent DATA."*
PROVENANCE: `.claude-plugin/plugin.json:30`; `test_plugin_manifest.py:56-65`
VOLATILE: `CLAUDE_PLUGIN_ROOT` / `CLAUDE_PLUGIN_DATA`. · TENSION: none.

**RULE:** Before claiming a lockfile-pinned install works, verify the lockfile is actually git-tracked — `git ls-files --error-unmatch <file>`. Local generation plus a local launch proves nothing about what leaves your disk.
FIRE-SITE: Shipping a plugin that builds its env from a committed lock.
LAYER: L4 · KIND: diagnostic · EVIDENCE: broke-in-production(caught in review, pre-ship) — *"The lock generated + verified perfectly locally — but `.gitignore` excluded `uv.lock` ('ambient, not a tracked lock'), so a real `/plugin install` would ship without it and `--frozen` would fail."* The same check surfaced a stale pre-workspace second lock hiding under the same ignore rule. False-green trap named: *"a contract test asserting `X.exists()` passes locally until X is committed."* Separately, the lock drifted unnoticed across three releases (*"v1.6.1 shipped with the lock still recording 0.9.0"*) until `uv lock --check` was added to CI.
PROVENANCE: `.prawduct/learnings-detail.md:489-493`; `docs/release-process.md:219-226`
VOLATILE: `uv run --frozen`; uv single-root-lock rule. · TENSION: none.

**RULE:** For any format the *harness* parses — hook manifests, plugin-manifest keys, settings shapes — take ground truth from a known-working example in the installed plugin cache, not from docs or a research agent; a wrong hook fails silently.
FIRE-SITE: Authoring `hooks.json`, `plugin.json`, or a settings block.
LAYER: L4 · KIND: diagnostic · EVIDENCE: broke-in-production(caught pre-ship) — a guide agent returned exec-form `{"type":"command","command":"bash","args":[...]}`; the installed plugin's own `hooks.json` showed the shell-form that CC version actually runs (one `command` string, no `args`). *"Following the agent's guess would have shipped a hook that never ran"* — *"a wrong hook silently never fires (no error), which is the worst failure mode to debug."* Generalization recorded: an agent's confidence about an environment-specific format is uncorrelated with the version you target.
PROVENANCE: `.prawduct/learnings-detail.md:495-499`
VOLATILE: CC hook manifest form (2026-06). · TENSION: none.

**RULE:** Perform every install/uninstall filesystem mutation in tested, atomic Python invoked as a CLI subcommand — never hand-authored shell in a skill body.
FIRE-SITE: Writing an install script that copies, deletes or JSON-edits on a user's machine.
LAYER: L4 · KIND: constraint · EVIDENCE: broke-in-production(real install, 2026-06-03) — `rsync_exclude_args()` correctly returned `--exclude=*.pyc`, but pasted unquoted into zsh the glob failed to match and **zsh aborted the whole line *after* the preceding `rm -rf` + `mkdir` + stub-write had run**, leaving a half-installed Control Surface. *"Only the agent's vigilance caught it."* Audit also found ~8 permission-prompting Bash calls with no single reviewable destructive moment, zero unit tests over any mutation, and three hand-maintained platform variants reconciled only by a SKILL.md string-drift test. Fix: stage → verify staged tree → move-aside-then-move-in swap with rollback, on every platform (Windows can't `os.replace` onto a non-empty dir). *"A crash leaves only collectable `.staging`/`.backup` dross; the live target is always the complete old or complete new install."* Pinned by `test_install_skill_has_no_handauthored_mutation_shell`.
PROVENANCE: `.prawduct/artifacts/install-hardening-design.md`; `skills/ableton-mcp-install/SKILL.md`
VOLATILE: none · TENSION: none.

**RULE:** Anchor a copy-exclude to the source root when the same filename exists at two levels — an unanchored exclude strips both and silently breaks the install.
FIRE-SITE: Writing the vendor/copy ignore predicate.
LAYER: L4 · KIND: constraint · EVIDENCE: designed-untested, load-bearing — *"`server.py` exists both at the package root (FastMCP-dependent — Live's embedded Python can't import it) and inside `remote_script/` (the Control Surface entrypoint Live LOADS). An unanchored 'server.py' exclude strips both."* One `vendor_ignore` definition feeds the copy, the completeness check and the advisory fingerprint *"so adding an exclude changes all three at once instead of leaving one describing a tree that is no longer shipped."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/install_paths.py:30-95`
VOLATILE: none · TENSION: none.

**RULE:** Re-raise on directory-walk errors in anything that feeds a completeness or drift check — `os.walk` swallows them by default, which silently shrinks the file list and makes two partial trees agree.
FIRE-SITE: Writing the walk behind a fingerprint or a verification.
LAYER: L4 · KIND: constraint · EVIDENCE: designed-untested (with the exact silent failure named) — *"an unreadable directory present on BOTH sides makes the two fingerprints agree and the advisory reports 'nothing to say' over a Live that is running stale code: the exact silence this module exists to end."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/install_paths.py:110-126`
VOLATILE: none · TENSION: none.

**RULE:** Fingerprint binary artifacts you install by raw bytes and skip the overwrite prompt when they match — re-running an installer must not re-prompt over a byte-identical file.
FIRE-SITE: An installer that copies a binary asset the user might have customized.
LAYER: L4 · KIND: pattern · EVIDENCE: broke-in-production(INS-4H8M) — *"Re-running install used to blindly re-prompt to overwrite an identical device."* The `.amxd` gets a raw-byte fingerprint (explicitly *not* line-ending-normalized — `test_fingerprint_does_not_normalize_line_endings`), and the skill branches on `matches: true` → skip entirely / `false` → confirm then `--force`.
PROVENANCE: `skills/ableton-mcp-install/SKILL.md` §3d; `hallucinote_mcp/tests/unit/test_ins_4h8m.py`
VOLATILE: none · TENSION: none.

**RULE:** Have the installer read the **running** server's identity from a no-backend-dependency resource and thread it through every install decision — the shell running your installer may import a different copy of your package than the copy the host actually launched.
FIRE-SITE: Writing an install flow that vendors, verifies or fingerprints "the package".
LAYER: L4 · KIND: constraint · EVIDENCE: broke-in-production(INS-3W8P) — *"In a coexistence setup — the marketplace plugin and a `--plugin-dir` dev checkout whose versions diverge — those are different copies, and vendoring the wrong one re-creates a handshake mismatch that blocks every push until corrected (it cost multiple Live-restart cycles on 2026-06-13)."* `ableton://server/info` returns `{version, base_version, fingerprint, package_root, python, project_root}` with *"deliberately NO Live dependency: install runs with Live closed."* Preflight **withholds** a verdict rather than compute one against a reference it knows is wrong: *"a comparison whose reference the report itself flags as the wrong one is worse than no comparison: it is the shape an operator acts on."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/resources/__init__.py:200-240`; `cli/preflight.py:19-52`
VOLATILE: none · TENSION: none.

**RULE:** Expose the server's own `sys.executable` so the agent runs your CLI in the *same* environment as the bridge — guaranteed version-synced, no env to build, and it works on a read-only install root.
FIRE-SITE: Shipping a CLI alongside an MCP server that an agent will shell out to.
LAYER: L4 · KIND: pattern · EVIDENCE: designed-untested — `ableton://server/info`'s `python` field: *"The agent runs engine commands as `"<python>" -m hallucinote.cli <command>` … so they execute in the SAME env as the bridge — guaranteed version-synced, works on a read-only plugin root, no clone/PyPI/separate-env."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/resources/__init__.py:225-233`; `docs/running-the-engine.md`
VOLATILE: none · TENSION: none.

**RULE:** An agent that installs an update *through* the MCP connection it just replaced cannot verify its own work — the running subprocess holds the pre-update code, so make the completion gate a user-performed reconnect, not a claim.
FIRE-SITE: Writing the hand-off of an install/update skill.
LAYER: L4 · KIND: constraint · EVIDENCE: designed-untested (explicit, in bold) — *"if you (the agent) ran this skill through the live `hallucinote-mcp` connection, you just replaced the code that connection runs. Your current bridge is now stale… You cannot do this yourself; the user must reconnect. **Do not report the install as working until they have.** The completion gate is a `/mcp` reconnect, not a vibe."*
PROVENANCE: `skills/ableton-mcp-install/SKILL.md` §5a
VOLATILE: none · TENSION: none.

**RULE:** Diagnose a version mismatch from the side that holds the third fact — the running process's in-memory fingerprint versus a *fresh* recompute of its own on-disk source — because the detecting side can only guess "the other half is stale".
FIRE-SITE: Writing version-mismatch remediation text.
LAYER: L4 · KIND: diagnostic · EVIDENCE: designed-untested, three named causes — *"the Remote Script side sees only two facts… But there is a third fact only the server side holds: its on-disk source."* When they differ the remediation swaps to "respawn the server", saying explicitly that *"re-vendoring … and restarting Live will NOT help a stale process."* Returns `None` on an unreadable tree: *"'cannot diagnose' rather than asserting staleness on noise."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/__init__.py:170-210`; `server.py:_refine_version_mismatch`
VOLATILE: none · TENSION: none.

**RULE:** Document which failures a client reconnect fixes and which need a full host restart — for code injected into a third-party app that caches modules at launch, "reconnect the MCP server" is not "reload the code".
FIRE-SITE: Writing upgrade notes or a failure-recovery table.
LAYER: L4 · KIND: constraint · EVIDENCE: broke-in-production (repeated in every release note) — *"MCP server → `/mcp` respawns the subprocess. Sufficient for engine changes; not for Live-side changes."* / *"Remote Script → Same symptom as Live being down, but Live looks fine — the classic confusing case… fully quit and reopen Live (Live caches Control Surface modules at startup — `/mcp` alone will not reload it)."* Inverse case also recorded: a schema fix in `server.py` *"Requires an MCP server restart, NOT a re-vendor — `server.py` is not in `_FINGERPRINT_PATHS`."*
PROVENANCE: `.prawduct/artifacts/architecture.md:66-76`; `.prawduct/operator-verification.md:147-153`
VOLATILE: Live 12.x Control-Surface caching. · TENSION: none.

**RULE:** Ship a three-state re-vendor verdict with every release (`required` / `recommended` / `not required`), derived mechanically from a diff against the hashed set and against the wider shipped set.
FIRE-SITE: Cutting a release of a server with a second deployed half.
LAYER: L4 · KIND: pattern · EVIDENCE: designed-untested (two greps, exceptions named) — the hard grep answers *"will the host refuse the call?"*, but *"a release that changes only those leaves the fingerprint still and the vendored copy stale, so a 'not required' verdict derived from the grep alone would be wrong."* One exception: hits confined to `server_side/` still read `not required`. Verdict goes in the release commit body and change-log *"so consumers know without having to diff."*
PROVENANCE: `docs/release-process.md:159-194`
VOLATILE: none · TENSION: depends on the two-tier fingerprint rule.

**RULE:** Batch every pending live-gated check into one re-vendor/restart sitting, and record per fix whether it needs a re-vendor, a server restart, or nothing — until the deployed copy is replaced, those verdicts are *unknowable*, not passing.
FIRE-SITE: Closing out a branch with changes to the remotely-executed half.
LAYER: L4 · KIND: pattern · EVIDENCE: measured — *"An expensive restart/reload cycle only pays off if you batch every fix into it"*; batching saved 3 Live-restart cycles in one session, and one historical run burned *"three re-vendor cycles as the chain-load fix iterated."* Every verification entry carries an explicit `Fingerprint flip: YES/NO` line.
PROVENANCE: `.prawduct/operator-verification.md:43-46, 425-435`; `.prawduct/learnings.md:339`
VOLATILE: none · TENSION: none.

**RULE:** Enumerate every config *scope* a server can be registered in before writing an uninstaller — and handle the plugin-provided case, which has no config entry at all.
FIRE-SITE: Writing uninstall/cleanup.
LAYER: L4 · KIND: constraint · EVIDENCE: designed-untested, three scopes shipped — project `.mcp.json`, global `~/.claude.json` top-level, and `projects.<cwd>.mcpServers` (the `claude mcp add` scope). Plus: *"If `hallucinote-mcp` is plugin-provided (no config-file entry — `remove-mcp-config` reports `removed: []`), there's nothing to delete here."* Config writes are temp-file + `os.replace` because *"`~/.claude.json` carries the user's whole project history — a partial write would be costly"*, and a malformed file is **refused**, never clobbered.
PROVENANCE: `skills/ableton-mcp-uninstall/SKILL.md`; `hallucinote_mcp/src/hallucinote_mcp/mcp_config.py`
VOLATILE: CC config scopes. · TENSION: none.

**RULE:** Make the uninstaller's symmetric env cleanup conservative — remove a value only when it still equals what you wrote — and document the manual cleanup path, because the uninstaller ships inside the thing being uninstalled.
FIRE-SITE: Writing the reverse of an install-time settings mutation.
LAYER: L4 · KIND: constraint · EVIDENCE: designed-untested, with the limitation stated rather than hidden — a user value above the floor is left alone (`kept-custom`); a pre-existing value *below* the floor was raised on install so it reads as ours and is removed rather than restored, *"because a value below the floor is exactly the cold-start-timeout failure this package exists to prevent, so reverting to it on uninstall would reinstate the bug."* The skill's last section is a full manual-cleanup recipe *"If the package was already `pip uninstall`'d."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/mcp_config.py:160-205`; `skills/ableton-mcp-uninstall/SKILL.md`
VOLATILE: none · TENSION: none.

**RULE:** Do the engine work in a git worktree and leave the checkout your remote half was installed from alone — a branch switch changes the fingerprint with no local edits, and in-session tools keep working off cached code, which makes the failure look intermittent.
FIRE-SITE: Switching branches in a checkout an installed MCP server imports from.
LAYER: L4 · KIND: diagnostic · EVIDENCE: broke-in-production — *"Check out a branch whose copy of any of those files differs, even with no local edits, and every CLI probe refuses with a version mismatch… The MCP tools inside a running session keep working, because that server process already has the old code in memory, which makes the failure look intermittent."* Related: an editable install inside a worktree *"would repoint the SHARED install the live `--plugin-dir` MCP server serves"* — pin `pythonpath` in pytest config instead.
PROVENANCE: `docs/known-issues.md:17-23`; `.prawduct/learnings.md:309`
VOLATILE: none · TENSION: none.

**RULE:** Pin an environment *before Python starts* — there is no `--pin` flag possible, because a process that mutates `sys.path` after import has already imported the wrong package.
FIRE-SITE: Designing a way to run against a specific installed copy.
LAYER: L4 · KIND: constraint · EVIDENCE: broke-in-production(worked-out recovery) — the shipped recipe copies the vendored package, copies back the install-stripped `cli/` and `server.py` (*neither of which is fingerprinted, so the pin keeps the remote half's fingerprint*), and exports `PYTHONPATH`. *"There is no `--pin` flag."*
PROVENANCE: `hallucinote_mcp/src/hallucinote_mcp/resources/guides/error-recovery.md` §"Engine version drift"
VOLATILE: none · TENSION: none.

**RULE:** To reproduce a wire-typing bug, drive the raw wire; to reproduce a schema-serialization bug, drive the real client — the choice of instrument *is* the finding, and the wrong one structurally cannot produce the shape.
FIRE-SITE: Writing a live repro or acceptance check for a typing/coercion defect.
LAYER: L4 · KIND: diagnostic · EVIDENCE: measured, both directions in one corpus — #508 verified over the raw wire *"because the MCP client coerces JSON numbers and so cannot reproduce the untyped-client shape the bug needs"*; #537's `Any`/`anyOf` bug could *only* be tested through the real client, because the failure was in the client's own serializer.
PROVENANCE: `.prawduct/operator-verification.md:147-153, 425-445`
VOLATILE: CC client JSON coercion (2026-09). · TENSION: none.

**RULE:** For a two-channel CLI seam behind an agent skill (JSON on stdout, human text on stderr), declare in the boundary doc whether each stderr message is **contract** (the consumer must relay it) or **diagnostic** — adding, moving or silencing one is then a contract change.
FIRE-SITE: Wrapping a CLI behind a skill or a tool; adding a warning print.
LAYER: L4 · KIND: pattern · EVIDENCE: broke-in-production(near-miss, named) — *"A wrapper that consumes stdout and drops stderr silently swallows the message telling the user their pull must be baked or the next build refuses — which reintroduces exactly the surprise BAK-7D2V exists to remove."* Explicit rule attached: *"If you add a new stderr message, say here whether it is contract (relay) or diagnostic (log)."*
PROVENANCE: `.prawduct/artifacts/boundary-patterns.md:123-153`
VOLATILE: none · TENSION: none.

**RULE:** Skip post-install hooks and `register` console scripts — modern Python packaging has degraded them, and a documented invocation is functionally identical.
FIRE-SITE: Designing MCP-server install.
LAYER: L4 · KIND: permission · EVIDENCE: designed-untested — *"post-install hooks are increasingly discouraged in modern Python packaging (uv ignores them, `pip install --no-deps` skips them, PEP 660 editable installs are inconsistent), and a register console script is functionally identical to a documented invocation."*
PROVENANCE: `docs/archive/mcp-tool-design.md` §10.5
VOLATILE: PEP 660 / uv behaviour. · TENSION: contradicted by a code block in the same section — see Disagreements.

**RULE:** Put the tool/action schema in one module imported by *both* halves — drift becomes structurally impossible rather than test-detected — and keep them in one repo so a capability is one PR, not two plus a version pin.
FIRE-SITE: Standing up a server plus an in-host agent that must agree on a vocabulary.
LAYER: L4 · KIND: pattern · EVIDENCE: designed-untested (held through the whole project) — *"Imported by both server + Remote Script. Single source of truth. No drift, no sync tests required."* Monorepo chosen for the same reason: *"Monorepo: one PR per chunk. Separate repos: two PRs per chunk + version pinning + drift risk."*
PROVENANCE: `docs/archive/mcp-tool-design.md` §10.1, §10.2
VOLATILE: none · TENSION: none.

**RULE:** Make ~60–70% of actions declarative (navigation path + op kind + value schema) with a handler escape hatch, so adding a capability is a schema edit and `help` regenerates for free.
FIRE-SITE: Designing the dispatcher for a server wrapping a large, regular host object model.
LAYER: L4 · KIND: pattern · EVIDENCE: designed-untested, with rejected alternatives recorded — *"Most Live operations are one of three shapes: property read / property write / method call."* Alternatives: *"Pure declarative (insufficient for snapshot/render/etc.); pure imperative (loses the 'add new actions without touching dispatcher' property)."* The shipped `LiveOp` supports one arithmetic form (`{name-1}` for 1-based→0-based) and a `result_template` so a write whose natural return is `None` still gets a structured result.
PROVENANCE: `docs/archive/mcp-tool-design.md` §10.3-10.4; `hallucinote_mcp/src/hallucinote_mcp/schema.py:57-94`
VOLATILE: none · TENSION: none.

**RULE:** Treat an action-surface change as a fan-out edit with a fixed checklist — help metadata, server instructions, guides, resource registry, error guide, changelog — and enforce it.
FIRE-SITE: Adding or renaming an action.
LAYER: L4 · KIND: pattern · EVIDENCE: designed-untested (adopted contract) — *"if the action surface changes, all seven targets get updated together."*
PROVENANCE: `docs/archive/mcp-tool-design.md` §2.6
VOLATILE: none · TENSION: none.

---

# Summary

**Total distinct rules found: 78** — L0 ×4, L1 ×25, L2 ×21, L3 ×20, L4 ×8 by primary layer (several L4 entries carry L2/L3 weight).

**Volume of MCP-relevant material read: ~95,000 words.** The core file set (`mcp-fingerprint-design.md`, the MCP-ASYNC plan + api-notes, both archive design docs, `api-contract.md`, `architecture.md`, both install skills, both hooks, the whole `hallucinote_mcp` server package, the four agent-facing guides) measures **71,328 words** by `wc -w`; add ~15K of tests and ~10K of changelog/learnings/operator-verification slices. `docs/archive/mcp-tool-design.md` (8.5K) and `mcp-requirements.md` (7.3K) are the two largest single artifacts.

## The 3 most valuable / non-obvious

1. **The two-tier fingerprint.** Hashing content instead of semver is the easy half. The hard-won half is the *scoping*, with a documented failure in **both** directions: hash too much (`handlers/` included server-only code) and a read-side fix nags every user to re-vendor until they learn to ignore the prompt; hash only the declared contract and a real remote bug fix ships with no prompt at all. The resolution — a narrow **blocking** hash over "shipped AND executed remotely", plus a wide **advisory** hash over everything shipped, with the advisory forbidden from ever gating — is a design nobody arrives at from first principles. Its supporting details (CRLF normalization, NUL-sniffing, `os.walk` re-raise so two partial trees can't agree, exclusion *by construction* via a separate package rather than by list maintenance) are each a bug someone ate.

2. **`MCP_TIMEOUT` is not the manifest's `timeout`.** A whole failure class — tools silently missing after install, no error anywhere — traced to a field that reads exactly like the fix and governs a different thing. Measured, not inferred: `Starting connection with timeout of 30000ms` against a config asserting 60000. And the follow-on is what makes it a *rule* rather than a fact: the manifest **cannot** set it, so the only channel is the user's `settings.json` `env`, which means an install flow, a symmetric uninstall, and a documented conservative-restore policy — and a SessionStart pre-warm hook, the obvious alternative, races the spawn and cannot be the mitigation.

3. **A polymorphic param typed `Any` kills the call inside the client.** `typing.Any` → `anyOf: [{}, {"type":"null"}]`, and the empty branch leaves the client with no type to serialize against, so strings go out unquoted and die in the client's own JSON parse — the server never sees a request, so nothing in your logs or tests can find it. Reproduced 6/6; it removed an entire capability (device renaming) for months. The fix is counter-intuitive twice over: spell out *every* JSON branch (a scalars-only union would have broken dict-valued assignment), and order `bool` before `int` while keeping `int` distinct, because bool is an int subclass and a widened float is rejected by the native setter.

*Runner-up, and the sharpest single sentence in the corpus:* a timeout on an uncancellable operation is a report that **you stopped waiting**, not that **the work stopped** — so the honest reply is `ok=True` + a job handle + "do not retry", the admission gate is released by the runner and never by the waiter, and there is deliberately no timed auto-clear because "clearing on a timer is the same defect on a delay."

## Tracked themes

- **Long-running operations:** the whole `start`/`status` pattern, above. Key framing: a synchronous call that outruns the host timeout is a **false failure** — the agent sees an error while the work completed server-side. The synchronous `render` was hard-deleted, not deprecated.
- **Progress reporting:** MCP progress notifications are **received but do not reset or extend** the tool-call timeout (Claude Code #58687), and there is no wake-on-done. Progress is therefore reported two ways that actually work: a long-polling `status` returning a `progress` dict, and a crash-resilient `status.json` heartbeat on disk that survives a server restart.
- **Version/capability reporting:** content fingerprint in `__version__`; `server_version` on every request with a three-branch handshake (match / missing / mismatch); an `ableton://server/info` resource with no backend dependency; `analysis_code = {signature, stale}` stamped on results so a report produced by cached pre-edit code says so; a tri-state capability matrix published as a resource; a documented three-state re-vendor verdict per release.
- **Large binary transfer:** deliberately never attempted. Renders write gigabytes of WAVs to disk; tools exchange `captures_dir` / `report_path` plus a JSON summary. Worth carrying into the corpus as *a reasoned avoidance*, not a gap.
- **Transport choice:** explicitly **considered and rejected as a lever**. The host tool-call timeout was verified identical across stdio, HTTP+SSE and Streamable HTTP (HTTP/SSE additionally imposes a 60 s first-byte minimum), so changing transport changes nothing. Separately, the internal server↔host bridge is TCP with 4-byte length-prefixed JSON, short-lived per-request connections — UDP rejected for its 64 KB datagram cap.

## Where sources disagree (report these, don't resolve them silently)

- **The fence's reach.** `actions/session.py:358` still ships the tip *"Safe to call while the main thread is fenced"*, and `conventions.md` calls `bout_status`/`abandon_bout` *"the two calls that always work."* The 2026-09-10 live sitting: `bout_status` **timed out at 30 s** inside a real host block. *"That holds against a bout-fenced main thread and fails against a genuinely blocked one. Only the first condition was ever tested."* The agent-facing over-claim is still in the tree.
- **The timeout ladder.** `plugin.json`'s 60 s per-tool-call timeout is *shorter* than three of the five inner socket ceilings (180 s / 125 s / 95 s) and two Live-side ceilings (120 s / 90 s) — the exact defect `client.py`'s own `_LIVE_REPLY_MARGIN_S` docstring describes, one rung further out. The comment justifying the 120 s ceiling was re-measured at 1.95 s and never revisited.
- **Fork vs greenfield.** `mcp-requirements.md` specifies 15 PRs (A–O) landing in a *fork* of an upstream project. `mcp-tool-design.md` §10.1 says *"100% greenfield… We do not read upstream source code."* ~250 lines of superseded execution plan were never marked as such.
- **UDP vs TCP.** `mcp-tool-design.md` §10.2 says the Remote Script opens a **UDP** server; shipped `wire.py` is TCP and calls the doc out by name.
- **Prompts, `NOTICE`, and post-install hooks** are each contradicted *within* `mcp-tool-design.md` (§6 reverses prompts, §11 still schedules them; §10.1 says no `NOTICE`, §11 and §15 say ship one; §10.5's prose forbids a post-install hook and its own code block three lines later shows one).
- **`mcp-requirements.md` is a status header over a frozen body** — top-of-file status marks gaps resolved while §17/§17b below still read in present tense as broken. Anything quoted from a "Current state (2026-05-01)" paragraph is a stale snapshot.

## Claims the code contradicts (findings, not practices)

- **Tool budget:** the design budgets 10 tools and ≤200 tokens of description each. Shipped: **13** tools (verified against `schema.TOOLS`), with `ableton_probe` appearing in neither design doc. The per-description token criterion appears never to have been measured.
- **No benchmark was ever run.** §16 asks for "agent task-success rate on a fixed benchmark… baseline first, then measure post-migration." No baseline, benchmark file or post-migration measurement exists anywhere in the corpus. **Every consolidation number in that document is borrowed** (Speakeasy, GitHub Copilot, a sibling project's README) — treat "95% smaller tool-list response" and "~10K → ~2K tokens" as third-party claims, not hallucinote measurements.
- **Batched `updates=[...]`** is promised as an anti-pattern remedy in §13 item 7. Verified absent — only `cue_create_batch` and `perform_batch` exist. The batch principle landed on two actions, not as a convention.
- **`ableton_annotation`** is fully specced in `v11-requirements.md` Arc 2 B2 with five actions. Verified absent from the shipped registration — the whole annotations subsystem was retired (its templated resource slot is now an empty tuple with the plumbing kept).
- **`db_writes=True` provenance machinery** exists in `schema.py` and `dispatcher.py` with validation and an `auto_request` context manager, but no shipped action declares it — a producer with no consumer.
