# cordyceps — addressed MCP corpus

## Provenance header

- **Repo:** `/Users/brookstalley/source/cordyceps` (read-only in this pass; nothing modified, staged, committed or branched)
- **Branch:** `develop`
- **Commit read:** `f07eb79373cd84583a67ae0c6090c931c30ca7a6` (`2026-08-29 15:30:03 -0600`, *"Merge feature PRs automatically once CI and review are clean"*)
- **Every `PROVENANCE:` below is relative to that commit.** Symbols and headings are the anchors; a
  parenthetical line number is a hint only and is not load-bearing.
- **One exception, flagged everywhere it is used:** `.prawduct/reflections.md` is **gitignored**
  (`.gitignore:53`) and therefore is NOT at this SHA. Citations to it are citations to the working
  tree of this machine on the date read (2026-09-18). Same for `.prawduct/.test-evidence.json`
  (`.gitignore:43`). I use them only where nothing tracked carries the fact, and say so inline.

**What this file is.** A re-mining of the same source as
`.prawduct/artifacts/mcp-mining/cordyceps-server.md`, which held 68 well-phrased rules with zero
provenance. Every rule from that capture appears here — none was dropped — with a place in the tree
attached, or with `PROVENANCE: UNADDRESSED` and the reason. Rules the first pass missed are added.
Numbers carried forward from the first pass were re-derived; several did not survive.

**Why this source matters.** The only non-C-family-of-Python server in the corpus, so it separates
language accidents from practice. In wide production use with external reporters filing real issues
(#13, #14, #15, #27, #28, #29, #30, #33 all appear as change-log `**Why:**` lines). And it is
embedded in a long-running GUI host (Rhino 8 / Grasshopper) whose API is reachable only from that
host's UI thread — which forces stateless HTTP instead of stdio, and makes its transport and liveness
material the richest in the corpus.

**Prior distillation exists and should be credited, not duplicated:**
`src/Cordyceps/Knowledge/McpTestingGuide.md` (62 lines at this commit — `wc -l`), correctly scoped as
an agent-executed acceptance script. It does not cover transport, lifecycle, concurrency, id echo,
coercion, capability negotiation, or install/client integration.

---

## How to count the rules in this file

```sh
F=.prawduct/artifacts/mcp-mining/cordyceps-server-structured.md
grep -c '^\*\*RULE:\*\*' "$F"                      # total rules
for L in L0 L1 L2 L3 L4; do printf '%s %s\n' "$L" "$(grep -c "^LAYER: $L\$" "$F")"; done
grep -c '^PROVENANCE: UNADDRESSED' "$F"            # unaddressed
grep -c '^PROVENANCE: CONTRADICTED' "$F"           # contradicted
grep -co 'UNSOURCED' "$F"                          # lines mentioning an unsourced number
```

**Result of those commands at time of writing: 95 rules — L0 2, L1 28, L2 26, L3 33, L4 6 — with
`FIRE-SITE`, `LAYER`, `KIND`, `EVIDENCE`, `PROVENANCE`, `VOLATILE` and `TENSION` present on all 95.**

**Zero rules are `PROVENANCE: UNADDRESSED` and zero are `PROVENANCE: CONTRADICTED`,** and that needs
saying rather than assuming: all 68 rules in the first pass turned out to be addressable, and none was
wrong *as a rule*. What was wrong was arithmetic. Four numbers the first pass stated did not survive
re-derivation (the instructions' line count, the host-free module and test-line counts, the
verification-queue ratio, and the provenance of the 49% figure) and two quoted strings are not in the
tree at all. Because the rule survives in each case and only its evidence moved, the correction lives
in that rule's **`VOLATILE:`** field with the re-derivation command beside it — not in `PROVENANCE:`.
Search `CONTRADICTED` and `UNSOURCED` to find all of them, or read the summary table at the end.

---

# L0 — applicability

**RULE:** When the system you want an agent to drive exposes its API only from inside its own
long-lived process, host the MCP server as a plugin in that process rather than as a separate
process — and accept that every transport decision downstream is then forced, not chosen.
FIRE-SITE: Deciding, before any code, whether "an MCP server for X" means a standalone binary or an
in-process extension. You are about to reach for stdio because every MCP example uses it.
LAYER: L0
KIND: decision-point
EVIDENCE: measured — the whole server is a Grasshopper component: `<TargetExt>.gha</TargetExt>`,
`<OutputType>Library</OutputType>`, and the listener lifecycle is owned by `SolveInstance`, which
Grasshopper calls on its UI thread. `GrasshopperContext`'s summary states the constraint flatly: *"All
Grasshopper operations must run on the UI thread."*
PROVENANCE: `src/Cordyceps/Cordyceps.csproj` `<PropertyGroup>` (TargetExt/OutputType);
`src/Cordyceps/CordycepsComponent.cs` `SolveInstance`; `src/Cordyceps/Core/GrasshopperContext.cs`
class summary
VOLATILE: none
TENSION: forces every L3 rule in this file — stdio is unavailable, so the HTTP rules are consequences
of this one, not independent preferences.

**RULE:** When the host has no headless mode, decide up front that a whole class of behaviour will
only ever be operator-verified, and build the queue for it in the same breath as the code — because
the alternative is silently shipping that class unverified.
FIRE-SITE: Writing the test plan for a server embedded in a GUI application, when you notice the
thing you most want to assert needs the app running with a human in front of it.
LAYER: L0
KIND: constraint
EVIDENCE: measured — 14 queue entries (`VRF-001`…`VRF-014`), and the stated reason is structural:
*"Why this needs a human: ... the host glue — applying the plan to a live ... "*. `project-preferences.md`
says the same as policy: *"document-touching behavior is verified live in Rhino — the Grasshopper host
cannot be exercised off the UI thread in a unit test."*
PROVENANCE: `.prawduct/operator-verification.md` `## VRF-001` … `## VRF-014`;
`.prawduct/artifacts/project-preferences.md` `## Testing` → "Coverage expectations"
VOLATILE: the count 14 grows with every host-bound chunk — re-derive with
`grep -c '^## VRF-' .prawduct/operator-verification.md`
TENSION: depends on the queue rule below (L3, "Maintain an explicit append-only queue…"), which this
repo's own data shows decaying into a write-only list.

---

# L1 — agent-interface design

**RULE:** Ride a small always-on status block on every tool response, injected at one choke point in
the server and never by the tools themselves, so an agent can see a busy or wedged host without
spending a call.
FIRE-SITE: You are adding a health or progress signal and about to give it its own tool, or about to
ask 18 tool files to each append it.
LAYER: L1
KIND: pattern
EVIDENCE: measured — one injection site: `WithStatus` is called on both the success and the error
return of `HandleToolCallAsync`, and its own docstring states the reason: *"Doing it here rather than
in each tool is what makes the block always-on: 19 tool files cannot drift out of sync with one they
never mention."* (The docstring's "19" is wrong — there are 18 files under `Tools/Unified/`; see
Doc-vs-code #3.)
PROVENANCE: `src/Cordyceps/McpServer.cs` `WithStatus`, called from `HandleToolCallAsync` (both
returns); `src/Cordyceps/Core/StatusEnvelope.cs` `ToCompactJson`
VOLATILE: "19 tool files" in the docstring; the real count is `ls src/Cordyceps/Tools/Unified/*.cs | wc -l` = 18
TENSION: spends context budget on every single response — in direct tension with the L1 context-budget
rule below and with the `instructions` rule; the mitigation is that the compact block omits every
field that equals the healthy reading.

**RULE:** Provide exactly one liveness action that answers entirely from cached state and never
touches the host — the only call guaranteed to return when everything else is stuck — and say so in
the server instructions, not just in the action's own help.
FIRE-SITE: An agent reports "the server stopped responding" and you cannot tell it apart from "the
work is slow." You are about to add a timeout.
LAYER: L1
KIND: pattern
EVIDENCE: incident — *"a caller could not tell a busy solver from a dead bridge: one measured outage
was ~32 minutes of total silence from a read-only probe. The ambiguity caused the retries that
triggered the dialog, so the two are one problem."* The fix is one line of dispatch:
`ActionConnection() => StatusEnvelope.ProbeResult(SolverState.Shared.Derive())` — no `ExecuteOnUiThread`
anywhere in it.
PROVENANCE: `.prawduct/change-log.md` `## 2026-08-21: bridge liveness, solution safety, status
envelope (issues #30, #29)` → `**Why:**`; `src/Cordyceps/Tools/Unified/GhInspectTool.cs`
`ActionConnection`; `src/Cordyceps/McpServer.cs` `GetServerInstructions` → the `BUSY IS NOT DEAD`
block
VOLATILE: **the ~32-minute figure is self-reported prose, not a record in this tree.** It appears
twice (`CHANGELOG.md` `## [1.5.0]` → `### Fixed` → *"one measured case: ~32 minutes of silence from a
read-only probe"*, and the change-log entry above). The primary observation lives in GitHub issue #29,
outside the repo. Treat the *shape* (tens of minutes of total silence) as the durable fact.
TENSION: none — but see the L3 rule about the probe deliberately not counting itself, without which
this action reports the wrong state.

**RULE:** Give the agent the three states it can act on differently — busy so wait / blocked so a
human must clear it / healthy so this is a real tool error — and attach the ACTION to each state, not
just the state name.
FIRE-SITE: Designing the payload of a health probe. You have `healthy: true|false` and are about to
ship it.
LAYER: L1
KIND: pattern
EVIDENCE: measured — the truth table is one `switch` with a sentence per cell, and the rationale is in
the field's own docstring: *"a modal dialog needs a human, which is the one thing an unattended agent
cannot summon. This inference is the whole reason the heartbeat exists."* Each hint ends in an
imperative (*"Wait and retry"*, *"needs a human to dismiss it — ... Do not keep retrying"*, *"treat any
error as a real tool error"*).
PROVENANCE: `src/Cordyceps/Core/SolverState.cs` `BuildHint` (the `switch (status.Ui)`) and
`HostStatus.ModalInferred` docstring; agent-facing copy at
`src/Cordyceps/Knowledge/CommonErrorsGuide.md` `## Is It Busy, Or Is It Dead?` (the 4-row table)
VOLATILE: none
TENSION: none

**RULE:** When the host is busy, REFUSE the action with a structured result that carries when the
busy state started — do not queue it and do not block on it.
FIRE-SITE: An action cannot run right now. You are choosing between a hidden queue, a blocking wait,
and an error.
LAYER: L1
KIND: decision-point
EVIDENCE: incident — the refusal's docstring gives both rejected options and why: *"Refusing beats
queueing or blocking: a hidden queue gives the caller no completion signal, and blocking reproduces
exactly the unbounded silence this feature exists to remove."* The incident behind it: *"Every MCP call
refreshed the bridge component by expiring it immediately; landing mid-solve, that raised
Grasshopper's modal breakpoint dialog, which stops the canvas and blocks every later call until a
human clicks Close — fatal unattended."* Two call sites: `ActionRecompute` and `ActionStatus`.
PROVENANCE: `src/Cordyceps/Core/StatusEnvelope.cs` `BusyResult`;
`src/Cordyceps/Tools/Unified/GhDocumentTool.cs` `ActionRecompute`;
`src/Cordyceps/Tools/Unified/GhInspectTool.cs` `ActionStatus`; `.prawduct/change-log.md`
`## 2026-08-21: bridge liveness, solution safety, status envelope (issues #30, #29)` → `**Why:**`
VOLATILE: none
TENSION: none

**RULE:** A liveness probe that reports a wedged host returns SUCCESS — reporting the bad state is
the probe working. Reserve failure for actions that refused to do their job.
FIRE-SITE: Writing the probe's return shape, and `success` feels like it should mirror `healthy`.
LAYER: L1
KIND: constraint
EVIDENCE: measured — `ProbeResult` unconditionally `AddFirst(new JProperty("success", true))`, with the
docstring *"Always a success, however unhealthy the host is — the probe's job is to report a wedged
host, so reporting one is the probe working, not failing."* Pinned by
`ProbeResult_IsAlwaysASuccess_EvenWhenTheHostIsBlocked`.
PROVENANCE: `src/Cordyceps/Core/StatusEnvelope.cs` `ProbeResult`;
`src/Cordyceps.Tests/StatusEnvelopeTests.cs` `ProbeResult_IsAlwaysASuccess_EvenWhenTheHostIsBlocked`
VOLATILE: none
TENSION: sits against the error-contract rule (`success:false` ⇒ `isError:true`) — this is the one
place where a bad-news payload must NOT be an error, and the distinction is *who* failed.

**RULE:** Make any cross-cutting result injection total: it must never throw and never damage the
payload — a non-object, malformed, help-text, trailing-garbage or already-occupied result must each
come back usable.
FIRE-SITE: You are about to re-serialize someone else's tool result to add a field to it.
LAYER: L1
KIND: constraint
EVIDENCE: measured — the class docstring states the bargain: *"A liveness feature that can break an
unrelated tool result is worse than no liveness feature."* `Inject` returns the input unchanged for
null/blank, non-JSON, non-object, and both-keys-taken; the outer `WithStatus` catch returns
`resultText` on anything else. Enumerated by **20** `Inject_*` tests.
PROVENANCE: `src/Cordyceps/Core/StatusEnvelope.cs` class summary and `Inject`;
`src/Cordyceps/McpServer.cs` `WithStatus` (the `prawduct:allow` catch);
`src/Cordyceps.Tests/StatusEnvelopeTests.cs` — the `Inject_*` region
VOLATILE: the count 20 — re-derive with
`grep -c 'public void Inject_' src/Cordyceps.Tests/StatusEnvelopeTests.cs` (the first pass said
"~20 enumerated tests"; it is exactly 20 at this commit, out of 35 `[Fact]`s in the file)
TENSION: none

**RULE:** When your envelope's key is already taken on someone else's payload, move aside to a
declared fallback key; when both are taken, inject nothing. Never overwrite the caller's data to make
room for a diagnostic.
FIRE-SITE: Naming the field your cross-cutting block occupies, on a server where tool payloads are
authored freely.
LAYER: L1
KIND: pattern
EVIDENCE: measured — `StatusKey = "status"`, `FallbackStatusKey = "host_status"`, with the fallback's
docstring *"Overwriting the tool's data to make room for a diagnostic would be a silent data loss, so
the block moves aside instead."* Both branches pinned:
`Inject_WhenStatusKeyIsTaken_MovesAsideRatherThanOverwriting`,
`Inject_WhenBothKeysAreTaken_ReturnsTheInputUnchanged`, plus `Inject_Twice_DoesNotStackBlocks`.
PROVENANCE: `src/Cordyceps/Core/StatusEnvelope.cs` `StatusKey` / `FallbackStatusKey` / `Inject`;
`src/Cordyceps.Tests/StatusEnvelopeTests.cs` same-named tests
VOLATILE: none
TENSION: none

**RULE:** Emit an optional diagnostic field only when it differs from the default reading — otherwise
it is noise on every response and invisible on the one that matters.
FIRE-SITE: Adding a field to a block that rides on hundreds of responses per session.
LAYER: L1
KIND: pattern
EVIDENCE: measured — `ToCompactJson` emits `solving_since`, `modal_inferred`, `hint` and
`solving_document` conditionally, and `solving_document` carries the reasoning inline: *"Named only
when a DIFFERENT file is the one solving — otherwise it is noise on every response, and when it does
appear it is the thing the caller needs to know."* Pinned by
`ToCompactJson_WhenHealthy_OmitsTheHintAndModalFlag`.
PROVENANCE: `src/Cordyceps/Core/StatusEnvelope.cs` `ToCompactJson`;
`src/Cordyceps.Tests/StatusEnvelopeTests.cs` `ToCompactJson_WhenHealthy_OmitsTheHintAndModalFlag`
VOLATILE: none
TENSION: with the "never let an ABSENT field read as agreement" rule below — they are opposites and
the discriminator is whether absence is *derivable*: absence of `modal_inferred` means "not inferred"
(safe); absence of `verified` would mean "unknown" (unsafe), which is why that one is spelled out.

**RULE:** Report the resource that is actually BLOCKING separately from the resource the call acted
on, whenever several workspaces share one serializing resource — naming the wrong one sends the agent
looking in the wrong place.
FIRE-SITE: Your status block says "busy" and the agent has just inspected the file it is working in
and found it idle.
LAYER: L1
KIND: pattern
EVIDENCE: measured — `HostStatus.SolvingDocumentName`'s docstring: *"Several definitions share the
single Rhino UI thread, so a solve in a file the agent is not touching still blocks it, and naming
the wrong file would send it looking in the wrong place."* `BuildHint` names the solving document, not
the focused one. Pinned by `ToCompactJson_WhenADifferentDocumentIsSolving_NamesIt`.
PROVENANCE: `src/Cordyceps/Core/SolverState.cs` `HostStatus.SolvingDocumentName` and `BuildHint`
(`solvingDoc` local); `src/Cordyceps.Tests/StatusEnvelopeTests.cs`
`ToCompactJson_WhenADifferentDocumentIsSolving_NamesIt`
VOLATILE: none
TENSION: none — **this rule is absent from the first pass.**

**RULE:** Use `initialize`'s `instructions` as the agent's operating manual: a tool/action index, a
failure-triage table, and the domain traps that destroy work — and treat that string as the
highest-drift-risk prose in the repo.
FIRE-SITE: An agent keeps using your server wrongly in a way no individual tool's help could have
prevented, because the mistake is about which tool to reach for.
LAYER: L1
KIND: pattern
EVIDENCE: measured — the string is 37 lines / 3,589 characters and contains exactly those three
things: the 7-tool action index, the `BUSY IS NOT DEAD` triage block with three actionable states, and
a trap in shouting caps: *"CRITICAL: Inside a cluster editor, NEVER advise the user to press F5 or use
Grasshopper's native recompute. It will destroy cluster inputs."* Its drift risk is institutionalised —
it is row 2 of a MANDATORY audit table.
PROVENANCE: `src/Cordyceps/McpServer.cs` `GetServerInstructions`; `CLAUDE.md`
`## Documentation Audit (MANDATORY)` → row "Server instructions"
VOLATILE: **the first pass said "~60 lines". That is CONTRADICTED at this commit: 37 lines.**
Re-derive with `sed -n '643,679p' src/Cordyceps/McpServer.cs | wc -lc` → `37 3589`, or robustly
`awk '/return @"Cordyceps/,/^";$/' src/Cordyceps/McpServer.cs | wc -lc`. Both numbers age on every edit.
TENSION: direct tension with the consolidation rule below — the instructions and the `tools/list`
schemas spend the same per-session context budget, and this repo pays for both.

**RULE:** Consolidate a wide API into a few tools that dispatch on an `action` parameter plus a
mandatory `action='help'` returning per-action required/optional/example/tips — but know you are
trading a short tool list for a wide flat parameter union, and that the real saving is moving
per-action detail out of `tools/list` into a runtime call.
FIRE-SITE: You have 100+ operations and are deciding between 100+ MCP tools and a handful of
dispatching ones.
LAYER: L1
KIND: decision-point
EVIDENCE: measured, both directions, at this commit:
- 7 tools (`grep -rlc 'McpServerToolType' src/Cordyceps/Tools/ | wc -l`), 115 declared actions
  (`grep -rc '= new ActionInfo' src/Cordyceps/Tools/Unified/*.cs` summed).
- The cost: `gh_canvas` declares **37** parameters and `rhino_render` **43**, almost all optional, in
  one flat `inputSchema`. Full row: `gh_canvas` 37, `rhino_render` 43, `rhino_scene` 28,
  `gh_document` 14, `gh_inspect` 8, `gh_wire` 8, `gh_script` 5 — **143 parameters across 7 schemas.**
- The saving: `help` is handled *before* validation and is the only place per-action detail lives —
  `tools/list` emits only `{name, description, inputSchema{type, properties, required}}`.
PROVENANCE: `src/Cordyceps/Tools/Unified/GhCanvasTool.cs` `GhCanvas` signature (the `[Description]`
parameter list) and its `ToolInfo` dictionary; `src/Cordyceps/Tools/Unified/RhinoRenderTool.cs`
`RhinoRender` signature; `src/Cordyceps/Core/UnifiedToolHelpers.cs` `GenerateHelp` and
`ActionInfo`; `src/Cordyceps/McpServer.cs` `HandleToolsList`
VOLATILE: 37 / 43 / 143 / 115 all move with every new action. Re-derive the parameter counts with
`awk '/\[McpServerTool,/{f=1} f&&/^        public string /{p=1} p{print} p&&/\)$/{exit}' <tool file> | grep -c '\[Description('`
TENSION: with the `instructions` rule (same budget), and with the L2 schema-typing rule (a 43-parameter
union is exactly where a wrong JSON-Schema type is least visible).

**RULE:** Make action matching case-insensitive in exactly the same way the dispatcher is, and write
a second test that the mixed-case path still enforces required parameters — that second test is what
catches a lazy fix.
FIRE-SITE: A client sends `action='Add'` and gets "Unknown action: 'Add'" while the dispatcher would
have handled it.
LAYER: L1
KIND: diagnostic
EVIDENCE: measured — `ValidateAction` tries the exact key, then `action.ToLowerInvariant()`, with the
comment *"Case-insensitive like the dispatch (which lowercases)"*. Both tests exist:
`MatchesActionCaseInsensitively_LikeDispatch` (`[InlineData("aDd")]` among others) and
`EnforcesRequiredParams_ForMixedCaseAction`.
PROVENANCE: `src/Cordyceps/Core/UnifiedToolHelpers.cs` `ValidateAction`;
`src/Cordyceps.Tests/UnifiedToolHelpersTests.cs` `MatchesActionCaseInsensitively_LikeDispatch`,
`EnforcesRequiredParams_ForMixedCaseAction`
VOLATILE: none
TENSION: none

**RULE:** Treat a present-but-null required parameter as missing, and make every validation error
carry `availableActions`, `required` and the action's `example` — the error message is the agent's
recovery path, not a log line.
FIRE-SITE: Writing the "you didn't give me X" branch. You are about to return a bare string.
LAYER: L1
KIND: pattern
EVIDENCE: measured — the predicate is `!providedParams.ContainsKey(p) || providedParams[p] == null`;
the missing-action and unknown-action errors both carry `availableActions` plus
`hint = "Use action='help' to see all {tool} actions"`; the missing-param error carries `required`,
`optional` and `example`. Pinned by `TreatsNullValuedRequiredParam_AsMissing`.
PROVENANCE: `src/Cordyceps/Core/UnifiedToolHelpers.cs` `ValidateAction`;
`src/Cordyceps.Tests/UnifiedToolHelpersTests.cs` `TreatsNullValuedRequiredParam_AsMissing`
VOLATILE: none
TENSION: none

**RULE:** When the server resolves an ambient "active" target that a human can retarget out from
under the agent, name the resolved target on EVERY response and say in the docs that it follows the
human's focus.
FIRE-SITE: Your tool signature has no target parameter because there is an obvious current one.
LAYER: L1
KIND: pattern
EVIDENCE: incident, found by a user's question rather than by review — *"'Grasshopper can have
multiple documents open — should we return the active one?' exposed that every tool resolves through
`Instances.ActiveCanvas?.Document`, so a human switching canvas tabs silently retargets the whole MCP
surface. That is a latent user-affecting bug (now GHD-5R7Q) that neither the issues, the Critic, nor I
had surfaced."* The resolver is real: `GetActiveDocument() => Instances.ActiveCanvas?.Document`. The
fix is the unconditional `document` member plus instructions prose: *"'document' is the .gh file the
call acted on; check it, because tools follow whichever canvas tab the human focused."*
PROVENANCE: `src/Cordyceps/Core/GrasshopperContext.cs` `GetActiveDocument`;
`src/Cordyceps/Core/StatusEnvelope.cs` `ToCompactJson` (`["document"]`);
`src/Cordyceps/Core/SolverState.cs` `HostStatus.DocumentName` docstring;
`src/Cordyceps/McpServer.cs` `GetServerInstructions` → `STATUS BLOCK` paragraph.
The user-question narrative is in `.prawduct/reflections.md`
`## 2026-08-21 — issues-2026-08-21: liveness, data modifiers, script write cascade` — **gitignored,
not at this SHA.**
VOLATILE: none
TENSION: none

**RULE:** Validate then mutate, and never let a parse failure read as an empty collection.
FIRE-SITE: Any handler that takes a JSON-encoded list and then changes durable state.
LAYER: L1
KIND: constraint
EVIDENCE: incident, and the highest-yield single rule here by defect count — *"The 2026-07-02 janitor
audit found one defect CLASS behind most of its 10 HIGH findings, recurring across
independently-written actions: mutate the document first, then discover the operation can't complete
(layer_delete moved objects before the current-layer check; place_image deleted the old frame before
the new add; configure wiped params from JSON that failed to parse and was silently read as `[]`)."*
The worst instance shipped `success: true` while destroying every wire: *"A syntax error in the
`inputs`/`outputs` JSON was previously read as an empty list, which cleared every custom parameter and
destroyed all wires while reporting `success:true`."* The remedy is the `TryParse(out result, out error)`
shape.
PROVENANCE: `.prawduct/learnings.md` `## Validate-then-mutate, and never conflate "unparseable" with
"empty"`; `CHANGELOG.md` `## [1.5.0]` → `### Fixed` → *"`gh_script(action='configure')` no longer wipes
parameters on malformed JSON"*; the shape at `src/Cordyceps/Core/ScriptParamDefs.cs` `TryParse` and
`src/Cordyceps/Core/ParseHelpers.cs` `TryDeserializeList` / `TryDeserializeArray` (both return the
error rather than a null-collapsed empty)
VOLATILE: **"10 HIGH findings" is sourced but does not match the plan.** `learnings.md` says 10; the
build plan's `### Chunk 03: HIGH code bugs` lists **6** (`H1`…`H6`), and the change-log entry says
*"Chunk 03 HIGH bugs (6)"*. Most likely reading: the survey found 10, six were approved into the chunk.
Carry the *class*, not the digit.
TENSION: none

**RULE:** Every per-id loop returns per-id results, with overall `success:false` when anything
failed — for an agent-facing server a false success is not a cosmetic lie, it is the agent building
confidently on destroyed state.
FIRE-SITE: A bulk handler returns a count. You are about to report the count and stop.
LAYER: L1
KIND: constraint
EVIDENCE: incident — *"any per-id loop returns per-id results with overall `success=false` when
something failed (the `ActionDelete` pattern) — silent skips reported as `success:true` were the single
most common bug."* Two sweeps were needed: *"`gh_canvas(action='preview'/'enable')` report per-id
results — Unresolvable ids (and components that don't support preview/enable) were silently skipped
with `success:true`"* and *"Bulk operations report what they didn't do — `rhino_scene`
delete/hide/show/set_layer/set_name/set_color/select and `rhino_render` light_set/light_delete now
return `notFound`/`notSelectable`/`failed` arrays and fail when nothing was affected, instead of
`success:true` with a zero count."*
PROVENANCE: `.prawduct/learnings.md` `## Validate-then-mutate, and never conflate "unparseable" with
"empty"`; `CHANGELOG.md` `## [1.5.0]` → `### Fixed`, the two bullets quoted;
`.prawduct/artifacts/build-plan-janitor-2026-07-02.md` `### Chunk 03` `H3` and `### Chunk 05`
VOLATILE: none
TENSION: none

**RULE:** Never let an ABSENT field read as agreement — emit an explicit `*Skipped` / `*Unavailable`
with a reason, and give the two opposite meanings of a false result DIFFERENT KEYS.
FIRE-SITE: You are writing the "could not determine" branch of a verification and the cheap move is
to leave the field out.
LAYER: L1
KIND: constraint
EVIDENCE: incident, and the cost is measured in a reporter's time — issue #33: *"A reporter on a real
149-object definition found `gh_script(action='set')` returning `success/codeSet:true`, `get`
round-tripping the new source, and the component executing its previous program regardless"*, and the
fix's own vocabulary decision: *"`rebuildSkipped` (no hooks — normal) is a different key from
`rebuildFailed` (a hook threw — probably still running the old program), and an unreadable program
yields `verificationSkipped` / `runningSourceUnavailable` rather than an omitted field, because an
absent `verified` read as agreement is the very failure being fixed."* The code says the same:
*"Every branch says something. An outcome that cannot be determined is reported as such rather than by
omitting the field."*
**Corollary, and the reason the reporter's own check could not help them: a clean read round-trip is
never proof a write took effect.** *"`get` could not see the divergence it was being used to rule out:
`TryGetSource` returns the *stored* text, while Rhino's own `GetText()` prefers the built code's — so
the clean round-trip the reporter checked was never evidence."*
PROVENANCE: `src/Cordyceps/Core/ScriptProgram.cs` `DescribeWrite` (and its `<remarks>`),
`DescribeRead`, `AddDivergence`; `.prawduct/change-log.md` `## 2026-08-27: writing a script's source
now recompiles it (issue #33)` → `**Why:**` and `**What:**` (c)
VOLATILE: none
TENSION: with the "emit an optional field only when it differs from the default" rule above — resolved
by asking whether absence is derivable.

**RULE:** Use ONE vocabulary for the same fact at the read surface and the write surface, so an agent
that learned a key from one response finds it in the other.
FIRE-SITE: You have just named a field in a write response and the read response already has a
different name for the same condition.
LAYER: L1
KIND: pattern
EVIDENCE: measured — `sourceDiverged` / `runningSource` / `divergenceNote` are emitted by a single
private `AddDivergence` shared by `DescribeWrite` and `DescribeRead`, with the docstring *"the same
vocabulary at both surfaces, so an agent that learned `sourceDiverged` from one response finds it in
the other."* The tool's own tips restate it: *"When code is written ... `rebuilt`/`rebuildSkipped` and
`verified`/`runningSource` mean exactly what they do for `action='set'`."*
PROVENANCE: `src/Cordyceps/Core/ScriptProgram.cs` `AddDivergence`;
`src/Cordyceps/Tools/Unified/GhScriptTool.cs` `ToolInfo` → the `set` / `configure` / `get` `Tips`
VOLATILE: none
TENSION: none — **absent from the first pass.**

**RULE:** Document the failure mode your verification provably CANNOT catch, rather than letting a
`verified: true` imply more than it means.
FIRE-SITE: You just shipped a verification. Someone is about to trust it for a case it cannot see.
LAYER: L1
KIND: stance
EVIDENCE: incident — the C# `RunScript`-never-invoked trap costs a *"full false-positive regression
report and a production rollback to 1.4.12"*, and the guide row says the quiet part out loud:
*"`verified:true` is truthful here and *cannot* catch this: the stored and running text are identical,
so there is no divergence to see. Python 3 does surface it ... but a C# script gives no signal at
all."* The same stance appears as a change-log section heading: `**What no test here can reach.**`
PROVENANCE: `src/Cordyceps/Knowledge/CommonErrorsGuide.md` `## Script Errors` — the row beginning
*"Outputs stay null with `verified:true`"*; `src/Cordyceps/Knowledge/Prompts/SetupScriptComponent.md`
(the *"Write the body as top-level statements"* note); `.prawduct/change-log.md`
`## 2026-08-29: document the silently-never-invoked RunScript trap (issue #33)` and
`## 2026-08-27: writing a script's source now recompiles it (issue #33)` → `**What no test here can
reach.**`
VOLATILE: none
TENSION: none

**RULE:** When you cannot report a failure synchronously, say WHERE it will appear instead of saying
nothing.
FIRE-SITE: You have just discovered the host discards the diagnostic you wanted to return.
LAYER: L1
KIND: pattern
EVIDENCE: designed-untested, with the unreachability established by reading the host assemblies —
*"Reporting compile diagnostics from the write call was in the first cut of the plan and is not
reachable on public API: `ReBuild()` → `PreBuild(kind)` → `Context.TryBuildCode(runContext, out _)`
discards the `Diagnosis` ... Build errors keep surfacing where they do today: on the component at the
next solve, via `gh_inspect(action='status')`. Said in the help text, the errors guide and the
changelog rather than left for a user to discover."* The pointer ships in the instructions:
*"compile errors surface on the component — check gh_inspect(action='status') after writing code"*.
PROVENANCE: `.prawduct/change-log.md` `## 2026-08-27: writing a script's source now recompiles it
(issue #33)` → `**Descoped, explicitly.**`; `src/Cordyceps/McpServer.cs` `GetServerInstructions`
(the `gh_script` line); `src/Cordyceps/Knowledge/Prompts/SetupScriptComponent.md`
VOLATILE: none
TENSION: none — **absent from the first pass.**

**RULE:** Validate a long-wait action's preconditions in ONE up-front hop, before the poll loop.
FIRE-SITE: An action with a `wait`/`timeout` parameter. The precondition check is naturally inside the
loop.
LAYER: L1
KIND: diagnostic
EVIDENCE: incident — *"`rhino_render(action='render', wait>0)` burned the full timeout then reported
success on a non-Raytraced viewport."* The fix is one pre-hop with the reason in the comment:
*"Validate up front (single UI-thread hop) so a missing view or a non-Raytraced display mode fails
immediately instead of burning the whole timeout in the poll loop and then reporting success."* The
refusal is actionable, naming the remedy: *"Switch first with `action='display', mode='Raytraced'`."*
PROVENANCE: `src/Cordyceps/Tools/Unified/RhinoRenderTool.cs` `ActionRender` (the `precheckError`
block); `CHANGELOG.md` `## [1.5.0]` → `### Fixed` → *"Wrong-target operations now fail loudly instead
of confirming"*; `.prawduct/artifacts/build-plan-janitor-2026-07-02.md` `### Chunk 05` → *"render
wait>0: up-front doc/view/Raytraced validation before the poll loop"*
VOLATILE: none
TENSION: none

**RULE:** For long work, expose a pollable progress reading plus an optional bounded wait that
returns `timedOut: true` with the current progress — and know that if you poll by marshaling onto the
same resource your liveness signal measures, the two compete.
FIRE-SITE: Choosing between MCP progress notifications and a poll/wait pair for an operation that
takes minutes.
LAYER: L1
KIND: decision-point
EVIDENCE: measured — no progress notifications exist (`grep -rn 'progressToken\|_meta' src/ --include='*.cs'`
returns nothing; the only `notifications/` case in `DispatchMethodAsync` is
`notifications/initialized`). The wait returns `{success:true, timedOut:true, currentPass, waitedMs}`
on budget expiry and `{success:true, timedOut:false, currentPass, isComplete, waitedMs}` on
satisfaction. **The unreconciled tension is visible in the code:** `WaitForRender`'s loop does
`Thread.Sleep(100)` and calls `_context.ExecuteOnUiThread` once per poll — and
`ExecuteOnUiThread` is exactly the choke point that increments `BeginUiWork`, the counter the modal
inference reads.
PROVENANCE: `src/Cordyceps/Tools/Unified/RhinoRenderTool.cs` `ActionRender` / `WaitForRender`;
`src/Cordyceps/McpServer.cs` `DispatchMethodAsync`; `src/Cordyceps/Core/GrasshopperContext.cs`
`ExecuteOnUiThread` (`SolverState.Shared.BeginUiWork()`)
VOLATILE: the 100 ms poll interval (`Thread.Sleep(100)` in `WaitForRender`)
TENSION: with the whole liveness cluster — a poll loop that occupies the measured resource is
indistinguishable from the work it is polling.

**RULE:** Make the server's own in-host infrastructure INVISIBLE — identical "not found" for a
protected object as for a nonexistent one — and enumerate every bypass route, because the guard is
only as wide as the call sites that ask for it.
FIRE-SITE: Your server plants objects in the user's document and an agent can see, rename or delete
them.
LAYER: L1
KIND: pattern
EVIDENCE: measured — the invisibility is stated as the design: *"This makes infrastructure completely
invisible - the LLM gets the same error whether the component doesn't exist or is protected."* The
protected set is computed transitively (the bridge component, everything wired to its inputs or
outputs, and any group containing one of those). **The transferable part is the bypass enumeration:**
*"`gh_canvas` group actions ... let infrastructure-protection be bypassed via
`group_rename`/`group_color`/`group_remove`/`group_add`."*
PROVENANCE: `src/Cordyceps/Core/ToolHelpers.cs` `GetCordycepsInfrastructureIds`,
`TryGetUnprotectedComponent`, `IsProtectedId`; `src/Cordyceps/Tools/Unified/GhCanvasTool.Groups.cs`
(the four `TryGetUnprotectedComponent*` call sites); `CHANGELOG.md` `## [1.5.0]` → `### Fixed` →
*"Wrong-target operations now fail loudly instead of confirming"*;
`.prawduct/artifacts/build-plan-janitor-2026-07-02.md` `### Chunk 04` → *"Group protection"*
VOLATILE: none
TENSION: none

**RULE:** Return generated binaries as `{filePath, hint}` rather than base64 — and do not hardcode
one client's tool name in the hint.
FIRE-SITE: A tool produced an image and you are about to inline it in the response.
LAYER: L1
KIND: pattern
EVIDENCE: measured — all three capture paths return `new { success = true, filePath = actualPath,
width, height, hint = "Use Read tool to view image" }`, and no base64 encoding exists anywhere in the
tree. The precondition that makes this sound is the transport's own: the listener binds only
`localhost`/`127.0.0.1` and `ValidateOrigin` rejects every non-localhost origin, so client and server
are necessarily co-located. **The defect in the pattern as shipped:** `"Use Read tool to view image"`
names Claude Code's `Read` tool inside a client-agnostic surface.
PROVENANCE: `src/Cordyceps/Tools/Unified/GhDocumentTool.Capture.cs` — the three result objects
carrying `filePath` + `hint`; co-location established by `src/Cordyceps/McpServer.cs` `Start`
(`Prefixes.Add`) and `ValidateOrigin`
VOLATILE: none
TENSION: the first pass attached the quote *"only where client and server are co-located"* to this
rule. **That phrase is UNSOURCED: it does not occur anywhere in this tree**
(`grep -rn -i 'co-located\|colocated\|same machine'` → no hits). The precondition is real but
*implicit* in the localhost binding; the quote belongs to a sibling repo, not this one.

**RULE:** Wrap each action in ONE host undo record, and when the host's begin-record call returns a
"already recording" sentinel, close only the record your own call opened.
FIRE-SITE: A bulk mutation. The user presses Ctrl-Z and gets one object back out of fifty.
LAYER: L1
KIND: pattern
EVIDENCE: incident, user-felt, with the host semantics verified rather than assumed — *"No code path
called `RhinoDoc.BeginUndoRecord`/`EndUndoRecord`, so each per-object mutation was its own undo step —
Ctrl-Z after a bulk MCP `set_layer` reverted one object of fifty."* And: *"verify-api probe
(MetadataLoadContext on RhinoCommon 8.0.23304.9001) confirmed `uint BeginUndoRecord(string)` /
`bool EndUndoRecord(uint)` and that Begin returns 0 when a record is already active — nesting-safe by
skipping End on 0."* The wrapper is 12 lines and brackets **28** doc-mutating actions
(`grep -rc 'WithUndoRecord(' src/Cordyceps/Tools/` summed = 28). Exclusions are decisions, not
oversights: *"`script` (native commands own their records), select/deselect (selection isn't
undoable), camera/zoom/display/view_load (viewport state), reads."*
PROVENANCE: `src/Cordyceps/Core/ToolHelpers.cs` `WithUndoRecord` (the `#region Undo Records`);
`.prawduct/change-log.md` `## 2026-07-02: Rhino undo records around mutating actions (reliability
chunk 05)`; `.prawduct/artifacts/api-notes-rhinocommon.md` (cited by the code as the record of the
probe)
VOLATILE: 28 — re-derive with `grep -rc 'WithUndoRecord(' src/Cordyceps/Tools/ | awk -F: '{s+=$2} END{print s}'`
TENSION: none

**RULE:** Give every tool method only primitive parameters (string / int / double / bool) and pass
structured input as a JSON string — then the coercion problem lives in one place instead of per-tool.
FIRE-SITE: Designing a new tool's signature and reaching for a DTO.
LAYER: L1
KIND: constraint
EVIDENCE: measured — stated as step 4 of the how-to (*"All parameters should be primitive types
(string, int, double, bool)"*), and every bulk parameter in the tree is a JSON string
(`ids`, `moves`, `items`, `inputs`, `outputs`). `ConvertJsonValue` handles exactly
string/int/long/double/float/bool and falls through to a string for everything else.
PROVENANCE: `CLAUDE.md` `### Adding or Modifying Tools`;
`src/Cordyceps/Tools/Unified/GhCanvasTool.cs` `GhCanvas` signature (`string ids`, `string moves`);
`src/Cordyceps/Core/JsonTypeConverter.cs` `ConvertJsonValue`
VOLATILE: none
TENSION: with the JSON-string-parse rule ("a parse failure is NEVER an empty collection") — this
design *creates* the parse boundary that rule exists to guard.

**RULE:** When you want to discourage a capability, change the propensity in every guidance surface
and keep the capability — do not remove it.
FIRE-SITE: You have decided the agent should stop doing something it is currently told to do.
LAYER: L1
KIND: stance
EVIDENCE: measured — *"The rename capability stays (explicit user/agent use); only the propensity
changes."* Executed across five surfaces at once: server instructions gain *"do NOT rename components
while building"*, `BestPracticesGuide` #2 flipped, `GettingStartedGuide` de-nicknamed, the
`CreateParametricGeometry` prompt's rename step became `group_create`, and the `rename`/`add`
`ActionInfo` tips carry discouragement notes. Plus a verification step that the code does not do it
unprompted: *"(b) Verified no code path auto-applies nicknames unprompted."*
PROVENANCE: `.prawduct/change-log.md` `## 2026-07-02: stop encouraging component renames — annotate
via groups (reliability chunk 06)`; `src/Cordyceps/Tools/Unified/GhCanvasTool.cs` `ToolInfo` →
`["rename"]` and `["add"]` `Tips`; `src/Cordyceps/McpServer.cs` `GetServerInstructions` → `Key points`
VOLATILE: none
TENSION: none — **absent from the first pass.**

**RULE:** Treat the agent-facing documentation surfaces as a checklist executed on every change, and
expect the drift to be toward plausible-but-nonexistent API — because those docs are written by the
same kind of model that would hallucinate it.
FIRE-SITE: You changed a tool. You are about to commit without opening the guides.
LAYER: L1
KIND: pattern
EVIDENCE: incident — the checklist is a 7-row MANDATORY table with a per-row trigger, prefaced by
*"AI agents only know what we tell them — if a feature isn't documented in the right places, it
doesn't exist to users."* The v1.5.0 audit's findings are the generalisable part, every one of them a
plausible non-existence: bulk-wire examples using *"the nonexistent `source`/`target`"* keys instead of
`sourceId`/`sourceParam`/`targetId`/`targetParam`; *"the documented `operation='list'` and `param=`
never existed"*; canvas-layout documenting *"nonexistent `right`/`bottom` fields"*; `action='list'` help
naming *"the real `typeFilter` parameter (was `type`, which the tool does not accept)"*; a
*"nonexistent `search_components` tool"*; and undo/redo *"advertised as working while
permanently-stubbed"*. Spacing guidance had also forked (60–80 px in two guides vs 150 px in the
instructions) and was unified at 150/70.
PROVENANCE: `CLAUDE.md` `## Documentation Audit (MANDATORY)` (the table);
`CHANGELOG.md` `## [1.5.0]` → `### Documentation` → *"Agent-facing docs corrected to match the real
tool contract"*; `.prawduct/artifacts/build-plan-janitor-2026-07-02.md` `### Chunk 02`
VOLATILE: none
TENSION: none

---

# L2 — protocol semantics

**RULE:** Return every failure of a KNOWN tool as a normal result with `isError: true` and a
`{"success": false, "error": …}` body; reserve JSON-RPC protocol errors for request-level problems.
FIRE-SITE: A tool body threw. You are in the `catch` at the MCP boundary.
LAYER: L2
KIND: constraint
EVIDENCE: incident — *"`McpServer.HandleToolCallAsync` hardcoded the transport `isError` flag to
`false`, so tool results carrying `{"success": false}` were reported to MCP clients as successes; and
tool-body exceptions escaped as raw JSON-RPC `-32603` protocol errors (only `GhScriptTool` caught
them), so the 7 tools behaved inconsistently."* Both halves now route through one host-free formatter;
the boundary catch carries an explicit waiver naming the contract.
PROVENANCE: `src/Cordyceps/Core/McpResultFormatter.cs` `IsErrorResult` / `FormatExceptionResult`;
`src/Cordyceps/McpServer.cs` `HandleToolCallAsync` (the `prawduct:allow prawduct/broad-except`
catch); `.prawduct/change-log.md` `## 2026-06-20: Honor the MCP error contract at the server boundary
(MCP-4R2K)`
VOLATILE: none
TENSION: with the probe rule at L1 — `success:false` ⇒ `isError:true` holds for actions, and the
liveness probe is the deliberate exception because it reports rather than acts.

**RULE:** Put the "is this tool known?" check OUTSIDE the error-converting try, so tool-identity
errors stay protocol errors and everything downstream of identity becomes a structured result.
FIRE-SITE: Laying out the boundary handler. The natural shape is one big try.
LAYER: L2
KIND: pattern
EVIDENCE: measured — the lookup and its `throw new Exception($"Unknown tool: {name}")` sit above the
`try`, with the comment *"Unknown tool stays a protocol error (the client addressed a tool that
doesn't exist); everything past this point concerns a KNOWN tool, so failures become structured
{success:false} tool results instead."*
PROVENANCE: `src/Cordyceps/McpServer.cs` `HandleToolCallAsync` — the `_tools.FirstOrDefault` /
`if (tool == null) throw` block preceding the `try`
VOLATILE: none
TENSION: **with `McpTestingGuide.md`, which contradicts it** — see Doc-vs-code #1. The guide also
classes a missing required parameter as a protocol error; the code converts that one to a structured
result, because the missing-parameter `throw` is *inside* the try.

**RULE:** Compute `isError` from the FINAL text the caller receives, after any envelope or status
injection — never from the tool's pre-injection return value.
FIRE-SITE: You have added a cross-cutting field to tool results and the error flag is computed one
line earlier.
LAYER: L2
KIND: pattern
EVIDENCE: measured — the ordering is explicit and commented: *"Status is folded in FIRST so isError is
computed from the payload the caller actually receives."* The code reads
`var resultText = WithStatus(...); ... isError = Core.McpResultFormatter.IsErrorResult(resultText)`.
Pinned from the other side by `Inject_KeepsTheResultParseableByTheErrorDetector` and
`BusyResult_SurvivesTheChokePointInjection`.
PROVENANCE: `src/Cordyceps/McpServer.cs` `HandleToolCallAsync` (final return);
`src/Cordyceps.Tests/StatusEnvelopeTests.cs` `Inject_KeepsTheResultParseableByTheErrorDetector`,
`BusyResult_SurvivesTheChokePointInjection`
VOLATILE: none
TENSION: none

**RULE:** Classify a result as an error only when the payload parses as a JSON object whose `success`
member is the boolean `false` — unparseable text, a JSON array, an absent `success` and the *string*
`"false"` are all non-errors. Be liberal on input coercion and strict on contract interpretation; that
asymmetry is the design.
FIRE-SITE: Writing the error detector, and the tempting shortcut is `text.Contains("\"success\":false")`.
LAYER: L2
KIND: constraint
EVIDENCE: measured — the docstring enumerates the whole truth table, and there are **9 dedicated test
methods** (11 cases with `[InlineData]`) each pinning a distinct wrong answer:
`ReturnsTrue_WhenSuccessIsFalse`, `…WithErrorAndExtraFields`, `ReturnsFalse_WhenSuccessIsTrue`,
`…_WithData`, `…WhenSuccessFieldAbsent`, `…WhenSuccessIsStringNotBoolean`, `…WhenNotJson`,
`…WhenJsonArrayNotObject`, `…WhenNullOrWhitespace` (3 rows). The `JsonException` catch is narrow, and
carries the reason non-JSON is *not* an error: *"an `action='help'` or plain-text payload"*.
PROVENANCE: `src/Cordyceps/Core/McpResultFormatter.cs` `IsErrorResult`;
`src/Cordyceps.Tests/McpResultFormatterTests.cs` — the `IsErrorResult` tests
VOLATILE: 9 — re-derive with
`grep -cE 'public void Returns(True|False)_' src/Cordyceps.Tests/McpResultFormatterTests.cs`
TENSION: none

**RULE:** Assert that your own exception formatter round-trips through your own error detector — the
two are one contract in two functions and nothing else checks that they agree.
FIRE-SITE: You have a `FormatExceptionResult` and an `IsErrorResult` in the same file and have tested
each.
LAYER: L2
KIND: pattern
EVIDENCE: measured — one test exists for exactly this: `Output_IsRecognizedAsError_RoundTrip`.
PROVENANCE: `src/Cordyceps.Tests/McpResultFormatterTests.cs` `Output_IsRecognizedAsError_RoundTrip`;
the two functions at `src/Cordyceps/Core/McpResultFormatter.cs`
VOLATILE: none
TENSION: none

**RULE:** Log the full exception operator-side and send only the message to the client — two
audiences, one catch.
FIRE-SITE: The boundary catch. You have one exception and two consumers.
LAYER: L2
KIND: pattern
EVIDENCE: incident, arriving as a review finding — *"every silent `catch` swallow in `src/Cordyceps/`
now logs with context or is narrowed to the expected exception type, and the MCP tool-boundary catch
logs the full exception (type + stack) operator-side."* In code:
`DebugLog.WriteLine($"Tool '{name}' threw: {ex}", "ERROR", 0)` followed by
`FormatExceptionResult(ex)`, which serializes `cause.Message` only. The comment states the split
outright.
PROVENANCE: `src/Cordyceps/McpServer.cs` `HandleToolCallAsync` (the catch body);
`src/Cordyceps/Core/McpResultFormatter.cs` `FormatExceptionResult`; `.prawduct/change-log.md`
`## 2026-06-20: Backlog batch — docs sync, test coverage, code-quality cleanup` → `(CQ-5J9N)`
VOLATILE: none
TENSION: none

**RULE:** Unwrap reflection's invocation wrapper before reporting an exception message, or every tool
failure reads as "Exception has been thrown by the target of an invocation."
FIRE-SITE: Your dispatcher calls tools via reflection and every error message is identical.
LAYER: L2
KIND: diagnostic
EVIDENCE: measured — `FormatExceptionResult` explicitly unwraps: *"Unwraps reflection's
`TargetInvocationException` to report the real cause's message"*, and both branches are pinned
(`UnwrapsTargetInvocationException_ToInnerMessage`,
`UsesOuterMessage_WhenTargetInvocationExceptionHasNoInner`).
PROVENANCE: `src/Cordyceps/Core/McpResultFormatter.cs` `FormatExceptionResult`;
`src/Cordyceps.Tests/McpResultFormatterTests.cs` the two named tests
VOLATILE: none
TENSION: none — **absent from the first pass.**

**RULE:** Compute the response id BEFORE dispatching the method. An id bug is a
mutation-duplication bug.
FIRE-SITE: Building the JSON-RPC response after the handler returns. This is where every
straightforward implementation puts it.
LAYER: L2
KIND: constraint
EVIDENCE: incident, and the consequence is the point — *"JSON-RPC response ids are echoed losslessly
(large/fractional/string ids no longer destroy the response after the tool already executed, which
caused clients to retry and double-apply mutations)"*. The code carries the same sentence as a
standing instruction: *"Callers compute `EchoId` BEFORE dispatching the method: echoing up front means
a malformed id can never destroy the response after the tool's side effects ran (which would make the
client retry and double-apply)."* In `HandleMcpPostAsync` the `EchoId` call precedes the
`DispatchMethodAsync` try.
PROVENANCE: `src/Cordyceps/Core/JsonRpcEnvelope.cs` class summary (final `<para>`) and `EchoId`;
`src/Cordyceps/McpServer.cs` `HandleMcpPostAsync` (ordering of `responseId` vs `result`);
`CHANGELOG.md` `## [1.5.0]` → `### Fixed` → *"MCP protocol robustness"*
VOLATILE: none
TENSION: none. Invisible in testing (ids are usually small ints), catastrophic in production,
one-line fix — which is why it is worth stating as a rule rather than leaving to review.

**RULE:** Echo the id by preserving the client's literal form, not a parsed value — `1.0` stays
`1.0`, a 23-digit integer survives, and a date-shaped *string* id is never reinterpreted.
FIRE-SITE: You are about to `GetInt64()` the request id, or you are swapping JSON libraries.
LAYER: L2
KIND: constraint
EVIDENCE: measured — the mechanism is `request.GetProperty("id").Clone()` (a `JsonElement`, which
re-serializes from its original text), documented as *"long, fractional (1.0 stays 1.0, not 1),
string, and null ids round-trip exactly as the client sent them"*. Pinned by **8** numeric rows —
`1`, `1.0`, `1.00`, `1e2`, `-0`, `9223372036854775808` (2⁶³), `12345678901234567890123`,
`0.30000000000000004` — and **3** string rows (`2026-08-21T14:02:11Z`, `2026-08-21`,
`/Date(1600000000000)/`). The date-string test states the stake: *"Some JSON libraries parse
date-shaped strings into date values on read and re-emit them in a normalized form ... the client
cannot match the response to its request, so it retries a call whose side effects have already run."*
PROVENANCE: `src/Cordyceps/Core/JsonRpcEnvelope.cs` `EchoId`;
`src/Cordyceps.Tests/JsonRpcWireFormatTests.cs` `NumericIdKeepsItsExactLiteralForm`,
`DateShapedStringIdIsEchoedVerbatim`; also `src/Cordyceps.Tests/JsonRpcEnvelopeTests.cs`
`FractionalWholeIdStaysFractional`, `LargeInt64IdRoundTrips`, `EchoIdSurvivesSourceDocumentDisposal`
VOLATILE: 8 + 3 — re-derive with
`grep -c '\[InlineData' <the two test methods>`; the first pass's "8 + 3" is confirmed exactly
TENSION: the *mechanism* is `Clone()`, not raw-text capture. The first pass said "preserving its raw
literal text"; that describes the observable behaviour correctly (System.Text.Json re-emits a number
element from its source span) but names the wrong mechanism. Stated as a behaviour, it holds.

**RULE:** Treat only an ABSENT `id` as a notification. An explicit `"id": null` still gets a
response.
FIRE-SITE: Writing the notification check. `id == null` is the obvious predicate and it is wrong.
LAYER: L2
KIND: constraint
EVIDENCE: measured — `IsNotification` returns
`!hasId || id.ValueKind == JsonValueKind.Undefined`, documented against the spec: *"JSON-RPC 2.0: a
request is a notification (MUST NOT receive a response) only when the `id` property is absent."*
Pinned by `AbsentIdIsNotification`, `ExplicitNullIdIsNotANotification`,
`AnyPresentIdIsNotANotification` (rows `1`, `"abc"`, `0`, `false` — `0` and `false` being the
falsy traps), `NullIdSurvivesWhenWritingNull`, `NotificationBuildOmitsIdEntirely`.
PROVENANCE: `src/Cordyceps/Core/JsonRpcEnvelope.cs` `IsNotification`;
`src/Cordyceps.Tests/JsonRpcEnvelopeTests.cs` the five named tests
VOLATILE: none
TENSION: none

**RULE:** Emit a null result as an explicit `"result": null` — a response with neither result nor
error is malformed, and a null-omitting serializer setting is exactly what produces it.
FIRE-SITE: You just added `DefaultIgnoreCondition = WhenWritingNull` (or an equivalent) to tidy your
output.
LAYER: L2
KIND: constraint
EVIDENCE: measured, and the mechanism here is an accident that had to be discovered and then
defended — the envelope survives because it is a `Dictionary<string, object>`, which the
POCO-scoped condition does not govern. The code carries the warning: *"WhenWritingNull does NOT drop a
null "result" here, despite how it reads ... That is the behavior we want — JSON-RPC 2.0 requires a
response to carry either "result" or "error" ... Pinned by JsonRpcWireFormatTests; do not "fix" this
to omit nulls."* And the comment it replaced said the opposite: *"Doing so corrected a comment in
`JsonRpcEnvelope` that claimed `WhenWritingNull` drops a null `result`; it does not, and the emitted
null is required."*
PROVENANCE: `src/Cordyceps/Core/JsonRpcEnvelope.cs` `SerializerOptions` (the comment block above it)
and `Build`; `src/Cordyceps.Tests/JsonRpcWireFormatTests.cs`
`NullResultIsEmittedExplicitly_NotOmitted`; `.prawduct/change-log.md` `## 2026-08-21: System.Text.Json
to Newtonsoft conversion dropped (issue #28 finding)`
VOLATILE: none
TENSION: none. The durable form of this: *a comment that confidently states the opposite of the
behaviour is worse than no comment, because someone "fixing" the inconsistency breaks the wire format.*

**RULE:** Write characterization tests for your serializer's EMERGENT byte properties — compactness,
absence of a naming policy, non-ASCII escaping — because a library swap changes what every client
parses while every behavioural test stays green.
FIRE-SITE: A proposal to swap JSON libraries, or a "harmless" serializer-options change.
LAYER: L2
KIND: pattern
EVIDENCE: measured — an entire test class exists for it, and states why: *"several of its properties
are emergent behavior of the serializer rather than anything the code states explicitly. A serializer
swap, or an options change as small as adding a null-handling setting, would alter them silently —
every existing envelope test would still pass, because none of them look at these particular bytes."*
Properties pinned: explicit null result, error-excludes-result, verbatim string ids, exact numeric
literals, no newline / no `", "` / no `": "`, member names verbatim (`ToolCount` stays `ToolCount`),
and `\uXXXX` escaping that still round-trips (`Wandstärke` → `Wandstärke` → `Wandstärke`).
The class earned its keep immediately: the swap it was written for was dropped when recon found
*"five behavior traps in what the issue framed as mechanical ... Three were untested, so the
reporter's 'all 56 tests pass' could not have caught a regression in them."*
PROVENANCE: `src/Cordyceps.Tests/JsonRpcWireFormatTests.cs` class summary and all 6 test methods;
`.prawduct/change-log.md` `## 2026-08-21: System.Text.Json to Newtonsoft conversion dropped (issue #28
finding)`
VOLATILE: none
TENSION: none

**RULE:** When re-serializing a payload you did not author, disable the parser's helpful conversions
and reject trailing content.
FIRE-SITE: You are parsing someone else's JSON only to add a field and write it back out.
LAYER: L2
KIND: constraint
EVIDENCE: measured — `ParsePreservingText` sets `DateParseHandling.None` and
`FloatParseHandling.Double`, then throws if `reader.Read()` finds more: *"Trailing content means this
was not a single JSON document; treating it as one would silently truncate the caller's payload."* The
motivation is stated as a wire-format guarantee for a tool that never asked for a status block.
Pinned by `Inject_DoesNotReinterpretDateLikeStrings`, `Inject_PreservesNumericPayloads`,
`Inject_PreservesUnicodeAndEscapes`, `Inject_IntoTrailingGarbage_ReturnsItUnchanged`.
PROVENANCE: `src/Cordyceps/Core/StatusEnvelope.cs` `ParsePreservingText`;
`src/Cordyceps.Tests/StatusEnvelopeTests.cs` the four named tests
VOLATILE: none
TENSION: none

**RULE:** Coerce across types at the parameter boundary — accept `"300"` and `300.0` for an integer
parameter, and reject a true fraction with a message naming WHY. Incidental strictness at a
model-output seam is a latent fail-close.
FIRE-SITE: A client sends `"300"` where your schema says integer and your server 500s.
LAYER: L2
KIND: pattern
EVIDENCE: incident, from an external reporter (#13) — *"MCP clients that send string-encoded numbers
(e.g., `"300"` instead of `300`) no longer cause errors."* The rejection message names the reason:
`"Cannot convert number '{element}' to int: not a whole number in the int range"`, replacing a raw
`FormatException`.
PROVENANCE: `src/Cordyceps/Core/JsonTypeConverter.cs` `ConvertJsonValue` (the `int` and `long`
branches); `CHANGELOG.md` `## [1.4.9]` → `### Fixed` → *"Type marshaling"*; commit `306f35d`
*"Fix type marshaling for MCP clients sending string-encoded numbers (#13)"*
VOLATILE: none
TENSION: with the "strict bool" rule below — the asymmetry is deliberate and stated (see next rule).

**RULE:** Make number→bool coercion total (nonzero is true, for any numeric) while keeping STRING
booleans on a strict grammar that errors on garbage — a number is unambiguous about truthiness, a
garbage string is not.
FIRE-SITE: A client sends `1.5` or `2^40` where you expect a bool and your int parse throws.
LAYER: L2
KIND: decision-point
EVIDENCE: measured, recorded as a deliberate deviation — *"`JsonTypeConverter` number→bool is
deliberate C-truthiness (`GetDouble() != 0`, tested): JSON numbers for bools get numeric semantics
(0/nonzero), while STRING booleans use the strict true/false/1/0/yes/no grammar that errors on
garbage. Rationale: a number is unambiguous about truthiness; a garbage string is not."* Both halves
are in the tree: `ConvertJsonValue`'s bool branch (`element.GetDouble() != 0`, with the comment naming
the old `GetInt32` failure on `1.5` and `2^40`) and `ParseHelpers.TryParseBool` (the
`true/1/yes` / `false/0/no` switch with `default: return false`). The incident that forced the strict
half: *"garbage boolean strings silently mapped to true/false in `enable`/`preview`/`solver`."*
PROVENANCE: `src/Cordyceps/Core/JsonTypeConverter.cs` `ConvertJsonValue` (bool branch);
`src/Cordyceps/Core/ParseHelpers.cs` `TryParseBool` (and `ParseBool` beside it, the defaulting
variant, with its docstring saying when each is right); `.prawduct/change-log.md`
`## 2026-07-02: janitor full reliability audit …` → `**Deliberate deviations recorded**`
VOLATILE: none
TENSION: with the coercion rule above; resolved by the ambiguity argument, which is the transferable
part.

**RULE:** Make a 64-bit upper bound EXCLUSIVE of 2⁶³ — the max value rounds *up* in double, so an
inclusive bound admits it and the cast overflows to the minimum instead of rejecting.
FIRE-SITE: Writing a range guard for a `long` parameter fed from a JSON number.
LAYER: L2
KIND: diagnostic
EVIDENCE: measured — the code is `d < 9223372036854775808.0` with the reason inline: *"Upper bound is
exclusive: long.MaxValue rounds UP to 2^63 as a double, so d <= long.MaxValue would admit 2^63 and
overflow on the cast."*
PROVENANCE: `src/Cordyceps/Core/JsonTypeConverter.cs` `ConvertJsonValue` — the `long` branch
VOLATILE: none
TENSION: none. Language-specific (absent in Python), but the class — *a float comparison against an
integer type's own limit is not the guard you think it is* — is not.

**RULE:** Map integer CLR types to `"integer"` and floats to `"number"` in generated schemas, and
audit the parameters you already declared as strings.
FIRE-SITE: Auto-generating `inputSchema` from method signatures.
LAYER: L2
KIND: diagnostic
EVIDENCE: measured — `GetJsonType` distinguishes `int`/`long` → `"integer"` from `double`/`float` →
`"number"`, changed together with a sweep of parameters that had been declared `string`:
*"Normalize 17 string params to native numeric types across GhDocumentTool, GhInspectTool,
RhinoSceneTool, and RhinoRenderTool"*.
PROVENANCE: `src/Cordyceps/Core/JsonTypeConverter.cs` `GetJsonType`; commit `306f35d` message;
`CHANGELOG.md` `## [1.4.9]` → `### Changed` → *"Accurate MCP schema types"* and
*"JSON Schema integer distinction"*
VOLATILE: **the digit disagrees with itself in the tree.** The commit message says *17*; the
`CHANGELOG.md` bullet enumerates *19* names (`lens`, `wait`, `timeout`, `azimuth`, `sunAltitude`,
`intensity`, `latitude`, `longitude`, `groundAltitude`, `shadowIntensity`, `spotAngle`, `xMin`, `yMin`,
`xMax`, `yMax`, `limit`, `padding`, `width`, `height`). Both are in this tree; neither is derivable
from HEAD, because the parameters are correctly typed now. Reported as Doc-vs-code #5.
TENSION: with the wide-flat-union rule at L1 — a 43-parameter schema is the worst place for a wrong
type, and the best argument for generating the schema rather than writing it.

**RULE:** Parse every numeric that arrives on the wire with an invariant culture. A server-side locale
bug only reproduces on the affected user's machine.
FIRE-SITE: `double.TryParse(s, out x)` anywhere in a handler.
LAYER: L2
KIND: constraint
EVIDENCE: incident — *"Camera/light coordinate strings (`"10.5,0,3.2"`) and `gh_canvas(action='set')`
slider values were parsed with the OS culture, corrupting values on comma-decimal locales (e.g.
`10.5` → `105` on a German system)."* Two failure shapes, not one: value corruption, and
mis-splitting, which the code names — *"current-culture parsing on comma-decimal locales would
mis-split "10.5,0,3.2" catastrophically."* Every numeric parse in the tree now passes
`CultureInfo.InvariantCulture` (`grep -rn 'TryParse' src/Cordyceps --include='*.cs'` against
`InvariantCulture`), and one test names the condition:
`ParsesInvariantCulture_EvenUnderCommaDecimalLocale`.
PROVENANCE: `src/Cordyceps/Core/ParseHelpers.cs` `TryParseXyz` (docstring + the three
`double.TryParse` calls); `src/Cordyceps/Core/JsonTypeConverter.cs` `ConvertJsonValue` (four
`CultureInfo.InvariantCulture` parses); `src/Cordyceps.Tests/ParseHelpersTests.cs`
`ParsesInvariantCulture_EvenUnderCommaDecimalLocale`; `CHANGELOG.md` `## [1.5.0]` → `### Fixed` →
*"Coordinates and slider values parse correctly on all locales"*
VOLATILE: none
TENSION: none

**RULE:** Emit ISO-8601 UTC with an invariant culture for every timestamp on the wire, and emit a
genuine JSON `null` — not an empty string — for an absent value.
FIRE-SITE: Serializing a nullable timestamp or an optional name into a diagnostic block.
LAYER: L2
KIND: pattern
EVIDENCE: measured — `Iso()` is `value.ToUniversalTime().ToString("o", CultureInfo.InvariantCulture)`
or `JValue.CreateNull()`; `Str()` exists solely for the null distinction, with the reason: *"Newtonsoft
types a `JValue((string)null)` as `String`, which reads back as a present-but-empty member; consumers
checking for absence deserve a real null."* Pinned by
`ToFullJson_WithNoHeartbeat_EmitsNullsRatherThanThrowing`.
PROVENANCE: `src/Cordyceps/Core/StatusEnvelope.cs` `Iso` and `Str`;
`src/Cordyceps.Tests/StatusEnvelopeTests.cs` `ToFullJson_WithNoHeartbeat_EmitsNullsRatherThanThrowing`
VOLATILE: none
TENSION: none — **absent from the first pass.**

**RULE:** Declare the capabilities you implement and nothing more — and declare the negative
explicitly (`listChanged: false`) rather than omitting the capability, because an unimplemented
`listChanged` is a promise clients act on.
FIRE-SITE: Filling in the `capabilities` object of `initialize`.
LAYER: L2
KIND: constraint
EVIDENCE: measured — `capabilities = new { tools = new { }, resources = new { subscribe = false,
listChanged = false }, prompts = new { listChanged = false } }`, and the server really does implement
`tools/list`, `tools/call`, `resources/list`, `resources/read`, `prompts/list`, `prompts/get`, `ping`
and nothing else (`DispatchMethodAsync`'s switch). **The gap, at this commit:** `protocolVersion` is
the hardcoded string `"2025-06-18"` and there is no negotiation — the client's requested version is
never read from `paramsEl`, because `HandleInitialize()` takes no arguments.
PROVENANCE: `src/Cordyceps/McpServer.cs` `HandleInitialize` and `DispatchMethodAsync`
VOLATILE: `"2025-06-18"` — a literal that will age and that nothing in the test suite pins
TENSION: none

**RULE:** Report the INFORMATIONAL version in `serverInfo.version`, not a normalized build version —
otherwise a tester asked to verify a fix cannot confirm which build they are running, which is the
whole point of a pre-release.
FIRE-SITE: Wiring `serverInfo.version` from whatever the platform hands you.
LAYER: L2
KIND: diagnostic
EVIDENCE: incident, found while shipping a fix an external reporter had to confirm — *"the assembly
version drops the pre-release tag, so every 1.5.0 pre-release reports an identical 1.5.0.0 and a
tester cannot confirm which build they are on — the thing pre-releases exist to let them do."* The
helper's docstring gives the mechanism: *"it has four numeric fields, so a pre-release built with
`-p:Version=1.5.0-rc.2` reports the same `1.5.0.0` as `rc.1` did."* The project stamps a
`SourceRevisionId` so the informational string also identifies the build.
PROVENANCE: `src/Cordyceps/Core/BuildVersion.cs` `Describe` (and the class summary);
`src/Cordyceps/McpServer.cs` `HandleInitialize` (the comment above the `Assembly` read);
`src/Cordyceps/Cordyceps.csproj` `<SourceRevisionId>`; `.prawduct/change-log.md`
`## 2026-08-27: writing a script's source now recompiles it (issue #33)` → `**What:**` (d)
VOLATILE: none
TENSION: none

**RULE:** Ship agent-facing domain knowledge as MCP resources under stable `scheme://` URIs, pointed
at from the initialize instructions, and optimize it for LLM reading rather than human reading.
FIRE-SITE: You have written a guide for agents and are about to paste it into a tool description.
LAYER: L2
KIND: pattern
EVIDENCE: measured, and the reduction is re-derivable — 12 `gh://docs/*` + `gh://patterns/*` URIs are
registered from embedded markdown, plus a dynamic `gh://component/{name}` provider; the instructions'
first line is `READ FIRST: gh://docs/getting-started (use resources/read)` and its last is the
resource list. The optimisation, and what it consisted of: *"Converted verbose prose to tables
throughout / Removed redundant tool parameter listings (use `action='help'`) / Eliminated basic
Grasshopper knowledge LLMs already have / Consolidated duplicate workflow instructions / Optimized
for LLM consumption, not human reading."*
PROVENANCE: `src/Cordyceps/Resources/ResourceRegistry.cs` `Initialize` (the
`RegisterEmbeddedResource` calls) and the `gh://component/` provider;
`src/Cordyceps/McpServer.cs` `GetServerInstructions` (first and last lines);
`CHANGELOG.md` `## [1.4.5]` → `### Changed` → *"Knowledge base optimization"*; commit `02b800d`
*"Optimize knowledge base for LLM token efficiency"*
VOLATILE: **the "49% (1648 → 835 lines)" figure — re-derived, and it does not land where the tree
says it does.** Re-derivation:
```sh
for r in 02b800d^ 02b800d HEAD; do printf '%s ' "$r"; git ls-tree -r $r --name-only \
  | grep 'Knowledge.*\.md$' | while read f; do git show $r:"$f" | wc -l; done \
  | awk '{s+=$1} END{print s}'; done
# 02b800d^ 1636   02b800d 835   HEAD 1361
```
So the reduction is real and 49.0% — but the "before" is **1636**, not 1648; and the corpus has since
grown back to **1361**, 63% of the way. Worse for the citation: `git merge-base --is-ancestor 02b800d
v1.4.5` fails — commit `02b800d` landed 21 seconds *after* the `Release v1.4.5` commit, so the change
the `## [1.4.5]` section claims first shipped in **v1.4.6**. Reported as Doc-vs-code #4.
TENSION: the reduction was partly funded by *"removed redundant tool parameter listings (use
`action='help'`)"* — i.e. it spent the same budget the consolidation rule at L1 spends. Counting it as
a saving twice would be double-counting.

**RULE:** Ship embedded agent-facing knowledge as assembly resources, so the plugin stays one
downloadable file and the docs cannot drift from the binary a user installed.
FIRE-SITE: Deciding where the markdown your `resources/read` serves actually lives at runtime.
LAYER: L2
KIND: pattern
EVIDENCE: measured — 17 `<EmbeddedResource Include="Knowledge\…" />` entries in the csproj, read back
by logical name (`"Knowledge.GettingStartedGuide.md"`) in the registry. The distribution unit is a
single `.gha`, which the README links at a stable release-asset URL.
PROVENANCE: `src/Cordyceps/Cordyceps.csproj` `<!-- Embedded documentation resources -->` ItemGroup;
`src/Cordyceps/Resources/ResourceRegistry.cs` `RegisterEmbeddedResource`; `README.md`
`### Manual install`
VOLATILE: 17 — `grep -c 'EmbeddedResource Include="Knowledge' src/Cordyceps/Cordyceps.csproj`
TENSION: none — **absent from the first pass.**

**RULE:** Render an unfilled prompt-template placeholder as an explicit `[argname]` marker, never as
the bare argument name — a bare name masquerades as prose mid-sentence and the agent acts on it.
FIRE-SITE: Your prompt template has `{goal}` and the caller supplied no `goal`.
LAYER: L2
KIND: diagnostic
EVIDENCE: incident — the docstring records both the fix and the shipped defect: *"The bracketed marker
was chosen so the reading agent sees an intentional slot to fill in, rather than the bare argument
name masquerading as prose mid-sentence (the old behavior rendered an unfilled `{goal}` as the literal
word "goal")."* The plan called it out as a bug to FIX during extraction, not a refactor:
*"PromptRegistry.GetPrompt: extract substitution as pure static; FIX the placeholder bug (unfilled
{goal} currently renders as literal "goal")."*
PROVENANCE: `src/Cordyceps/Core/PromptTemplate.cs` `Render` (the declared-args loop);
`.prawduct/artifacts/build-plan-janitor-2026-07-02.md` `### Chunk 06`; tests at
`src/Cordyceps.Tests/PromptTemplateTests.cs`
VOLATILE: the first pass quoted the shipped output as `"Accomplish goal now."` — **UNSOURCED**; that
exact sentence does not occur in the tree. The mechanism it illustrates is sourced by the docstring
above.
TENSION: none

**RULE:** Derive the client-visible tool name from the method name by one pure rule, and pin the real
names as a contract test — because the derivation silently renames the entire tool surface.
FIRE-SITE: Renaming a method, or "improving" the naming converter.
LAYER: L2
KIND: constraint
EVIDENCE: measured — `McpNaming.ToSnakeCase` is 10 lines and host-free, with the stake in its summary:
*"any change here silently renames every tool"*. The contract test pins all seven pairs explicitly and
says why: *"A regression here silently renames the entire MCP tool surface for every client, so these
pairs are pinned explicitly."*
PROVENANCE: `src/Cordyceps/Core/McpNaming.cs` `ToSnakeCase`;
`src/Cordyceps.Tests/McpNamingTests.cs` `RealToolNames_MapToPinnedMcpNames`;
`src/Cordyceps/McpServer.cs` `ConvertToSnakeCase` (the forwarder)
VOLATILE: none
TENSION: none — **absent from the first pass.**

**RULE:** Evolve a published tool/action contract additively, with a deprecation registry — never a
silent rename or removal.
FIRE-SITE: You want to rename an action because the old name was badly chosen.
LAYER: L2
KIND: stance
EVIDENCE: designed-untested (stated as the boundary's own policy, with a mechanism that exists) —
*"Tool names ..., the per-tool `action` vocabulary, parameter names/types/`[Description]`s, and the
JSON response shape (`{ success, ... }`). **Breaking any of these breaks installed users' agent
workflows** ... Evolve with additive actions and `Core/DeprecationRegistry.cs`, never silent renames or
removals."*
PROVENANCE: `.prawduct/artifacts/boundary-patterns.md` `### MCP Tool / Action Contract`;
`src/Cordyceps/Core/DeprecationRegistry.cs` (class summary — *"Registry for tracking deprecated
components and their upgrade paths"*)
VOLATILE: none
TENSION: `DeprecationRegistry` tracks deprecated *Grasshopper components*, not deprecated
*Cordyceps actions* — the artifact names it as the mechanism for the latter. The stance is sound; the
mechanism it points at does not yet do that job.

---

# L3 — transport & operations

**RULE:** Validate the `Origin` header against localhost. A locally-bound HTTP MCP server is
reachable from any web page the user visits.
FIRE-SITE: You bound to 127.0.0.1 and concluded that made you safe.
LAYER: L3
KIND: constraint
EVIDENCE: measured — `ValidateOrigin` is the FIRST thing `HandleRequestAsync` does after logging, and
it 403s any `Origin` whose host is neither `127.0.0.1` nor `localhost`, and also 403s a malformed one
(`catch (UriFormatException)`). The threat is named: *"Validate Origin header to prevent DNS rebinding
attacks."*
PROVENANCE: `src/Cordyceps/McpServer.cs` `ValidateOrigin`, called from `HandleRequestAsync`
VOLATILE: none
TENSION: an absent `Origin` header is allowed through (`return null` at the end) and the CORS
response then echoes `"*"` — the guard binds browsers, which always send `Origin`, and not a local
script.

**RULE:** Bind BOTH `localhost` and `127.0.0.1` — clients disagree about which they dial.
FIRE-SITE: One MCP client connects and another gets connection refused on the same port.
LAYER: L3
KIND: diagnostic
EVIDENCE: measured — two prefixes added back to back, with the comment *"(bind to both IPv4 and
IPv6)"*: `Prefixes.Add($"http://localhost:{port}/")` and `Prefixes.Add($"http://127.0.0.1:{port}/")`.
The README's own three client recipes all use `127.0.0.1`, which is why the `localhost` prefix is the
non-obvious half.
PROVENANCE: `src/Cordyceps/McpServer.cs` `Start` (the `HttpListener` prefix block); `README.md`
`## Usage` step 2 (the three client configs)
VOLATILE: none
TENSION: none

**RULE:** Reject a request that declares no `Content-Length` (411). A chunked body bypasses your size
cap entirely, so the cap is decorative until you require a declared length.
FIRE-SITE: You just added a body-size cap and feel protected.
LAYER: L3
KIND: diagnostic
EVIDENCE: measured — the check precedes the cap and states the hole: *"ContentLength64 < 0 means no
Content-Length header (e.g. chunked transfer), which would bypass the cap entirely — require a
declared length (411)."* Cap is `10 * 1024 * 1024` with a 413 above it.
PROVENANCE: `src/Cordyceps/McpServer.cs` `HandleMcpPostAsync` (the `MAX_BODY_SIZE` block)
VOLATILE: the 10 MB cap (`const long MAX_BODY_SIZE` in `HandleMcpPostAsync`)
TENSION: none

**RULE:** Accept `*/*` and `application/*`, not only the literal media type — a strict `Accept` check
406s working clients.
FIRE-SITE: You implemented the spec's Accept requirement literally and a client stopped working.
LAYER: L3
KIND: diagnostic
EVIDENCE: measured — `!accept.Contains("application/json") && !accept.Contains("*/*") &&
!accept.Contains("application/*")` → 406, with the comment *"Wildcards ("*/*", "application/*") accept
JSON too."* Listed in the fix sweep as *"`Accept: */*` is accepted"*.
PROVENANCE: `src/Cordyceps/McpServer.cs` `HandleMcpPostAsync` (the `accept` check);
`CHANGELOG.md` `## [1.5.0]` → `### Fixed` → *"MCP protocol robustness"*
VOLATILE: none
TENSION: none

**RULE:** In stateless mode answer GET and DELETE on the MCP endpoint with 405 rather than
half-implementing sessions, and put liveness on a separate plain `GET /health` a monitor can poll.
FIRE-SITE: A client opens a GET on your `/mcp` endpoint expecting an event stream.
LAYER: L3
KIND: decision-point
EVIDENCE: measured — `if (path == "/mcp")` handles POST and returns `response.StatusCode = 405` for
everything else, commented *"GET and DELETE return 405 in stateless mode"*; `/` and `/health` route to
`HandleHealthCheckAsync`. There is no SSE anywhere: `grep -rn 'text/event-stream\|EventStream'
src/ --include='*.cs'` returns nothing, and the class summary says *"Streamable HTTP transport ...
with stateless mode."*
PROVENANCE: `src/Cordyceps/McpServer.cs` `HandleRequestAsync` (the `/mcp` and `/health` branches) and
the `McpServer` class summary
VOLATILE: none
TENSION: **the repo's two primary architecture briefings contradict this** — see Doc-vs-code #2.

**RULE:** Make the health endpoint answer from CACHED state, and say plainly that `"status": "ok"`
means only that the HTTP endpoint answered.
FIRE-SITE: Writing a health endpoint that reads live application state to decide what to report.
LAYER: L3
KIND: constraint
EVIDENCE: incident — the docstring is the finding: *"It previously read `Instances.ActiveCanvas?.Document`
directly on this HTTP worker thread — a Grasshopper read off the UI thread, and one that returns
nothing useful precisely when the host is wedged."* And the conflation is called out at the field:
*""ok" means the HTTP endpoint answered. Whether the HOST is healthy is the three-layer block below —
conflating the two is what made a wedged Rhino indistinguishable from a healthy one."*
PROVENANCE: `src/Cordyceps/McpServer.cs` `HandleHealthCheckAsync` (docstring + the `["status"]`
comment); `src/Cordyceps/Core/StatusEnvelope.cs` `ToFullJson`; `.prawduct/change-log.md`
`## 2026-08-21: bridge liveness, solution safety, status envelope (issues #30, #29)` → `**What:**` (f)
VOLATILE: none
TENSION: none

**RULE:** Surface an actionable bind failure, distinguishing "another instance of us owns the port"
from "a foreign process owns it."
FIRE-SITE: Your server didn't start and the UI says "NOT RUNNING."
LAYER: L3
KIND: diagnostic
EVIDENCE: incident — *"a failed listener bind was swallowed and returned a silently-dead server, so
the component now records an actionable `StartError` surfaced as a canvas error + Status output (no
more bare "NOT RUNNING")."* Two distinct paths exist, and that is the transferable part: the
own-instance case is caught *before* binding, from the plugin's own `_portOwners` registry
(*"Port {port} is already in use by another Cordyceps component. Change this component's port input to
use a different port."*), while the foreign case is an `HttpListenerException` at bind time, given its
own branch: *"The port may be in use by another application — choose a different port (the HttpPort
input) or close the process holding it."*
PROVENANCE: `src/Cordyceps/McpServer.cs` `Start` (the `StartError` ternary on `HttpListenerException`);
`src/Cordyceps/CordycepsComponent.cs` `SolveInstance` (the `_portOwners` check and the
`AddRuntimeMessage` branches); `.prawduct/change-log.md` `## 2026-06-24: gh_script(set) flags a
silently-broken Script component (issue #15)` → the `solidity-hardening` sub-entry, **Chunk 02**
VOLATILE: default port 26929 (`DEFAULT_PORT` in `McpServer`, the component's input default, and four
places in `README.md`)
TENSION: none

**RULE:** Free the port synchronously but drain in-flight handlers on a BACKGROUND task — a
synchronous drain on the host's UI thread can never succeed for exactly the handlers it protects,
because those handlers are blocked waiting for that same thread.
FIRE-SITE: Writing `Stop()`. The drain belongs right there, before you release shared state.
LAYER: L3
KIND: diagnostic
EVIDENCE: incident, and it is the sharpest deadlock-shaped rule here — *"`McpServer.Stop()` always
runs on the UI thread (component port-change, `RemovedFromDocument`, `DocumentContextChanged`), while
an in-flight handler is a worker blocked in `RhinoApp.InvokeAndWait` waiting for that same UI thread —
so the synchronous `DrainWithin(2s)` could never succeed for exactly the handlers it protects: a
guaranteed ~2s Rhino UI stall whenever teardown overlapped a request, and the drain's "handlers finish
against a still-valid context" comment was wrong for that case."* The split is now explicit in code:
transition to `Stopping`, cancel the CTS, stop and close the listener (port free), then `Task.Run` the
listener wait + `DrainWithin` + context release.
PROVENANCE: `src/Cordyceps/McpServer.cs` `Stop` (the `Task.Run` block and the MCP-3D8V comment above
it); `.prawduct/change-log.md` `## 2026-07-02: Stop() drain moved off the UI thread (reliability chunk
03)`; `CHANGELOG.md` `## [1.5.0]` → `### Changed` → *"Server teardown no longer stalls the Rhino UI"*
VOLATILE: the 2-second budget — `const int SHUTDOWN_TIMEOUT_SECONDS = 2` in `McpServer`
TENSION: none. The general shape: *a drain that runs on the resource the drained work is waiting for
is a deadlock wearing a timeout.*

**RULE:** Snapshot the in-flight set before draining, so a steady request stream cannot hang
shutdown — and test it with real concurrency plus a deterministic seam, not a sleep.
FIRE-SITE: Your drain re-reads the live set each iteration.
LAYER: L3
KIND: pattern
EVIDENCE: measured — `DrainWithin` takes `var pending = _tasks.Keys.ToArray()` first, documented as
*"Tasks tracked after this call begins are not awaited (a fixed snapshot is taken), so a steady stream
of new requests cannot make shutdown hang."* The test drives it for real: a background `Task.Run`
drain, an `OnDrainSnapshot` internal seam that fires the moment the snapshot is captured, a second
handler tracked only after that signal, and a never-completing `TaskCompletionSource`. Its comment
names the alternative it rejects: *"Deterministic seam: DrainWithin signals right after it captures
its snapshot ... no sleep-and-hope timing."* **Its first version shipped vacuous and review caught
it:** *"The Chunk-02 `DrainWithin_TakesSnapshot...` test shipped vacuous and the Critic (chunk mode,
Goal 1 test-quality) caught it; the fix was a background-drain + mid-wait-tracked-TCS rewrite."*
PROVENANCE: `src/Cordyceps/Core/InFlightRequests.cs` `DrainWithin` and `OnDrainSnapshot`;
`src/Cordyceps.Tests/InFlightRequestsTests.cs`
`DrainWithin_TakesSnapshot_IgnoresTasksTrackedAfterItStarts`; `.prawduct/learnings.md`
`## A test naming a race/snapshot/ordering contract must actually exercise concurrency`
VOLATILE: none
TENSION: none

**RULE:** Capture shared teardown-able state into a local at the request boundary and null-guard it,
returning a structured "server is shutting down; the request was not processed."
FIRE-SITE: Your handler reads a field that teardown nulls, and you have an intermittent NRE.
LAYER: L3
KIND: pattern
EVIDENCE: incident — *"the teardown race that let an in-flight handler NRE on a nulled `_context` is
closed by capturing `_context` once and returning a structured "shutting down" result."* In code:
`var ctx = _context; if (ctx == null) { … FormatExceptionResult(new InvalidOperationException("MCP
server is shutting down; the request was not processed.")) … isError = true }`. The field is
`volatile` with a comment naming both writers and the reader.
PROVENANCE: `src/Cordyceps/McpServer.cs` `HandleToolCallAsync` (the `ctx` capture) and the
`private volatile GrasshopperContext _context` declaration; `.prawduct/change-log.md`
`## 2026-06-24: gh_script(set) flags a silently-broken Script component (issue #15)` →
`solidity-hardening` **Chunk 02**
VOLATILE: none
TENSION: this guard is what makes detaching an over-budget handler safe — the background drain's
comment cites it by name.

**RULE:** When the host's invoke API cannot be cancelled, bound the LOCK ACQUIRE instead of the host
call — waiters fail fast with an actionable error while the wedged holder stays wedged. Verify the
absence of a bounded overload rather than assuming it.
FIRE-SITE: One hung operation has made every subsequent request hang, and the host API takes no
timeout.
LAYER: L3
KIND: decision-point
EVIDENCE: incident, with the impossibility verified by reflection rather than assumed —
*"`GrasshopperContext.ExecuteOnUiThread` could wedge every later request forever behind one hung UI
operation (infinite-loop script, modal) with no recovery but a Rhino restart ... `verify-api` confirmed
`InvokeAndWait` exposes no native timeout/cancellation (notes in `api-notes-rhinocommon.md`), so the
timeout bounds waiters, not the holder."* The residual is documented rather than hidden, in the
constant's own docstring: *"this bounds the *waiters*, not the holder of a wedged operation."* And the
refusal is actionable: *"Document is busy: another operation held the Rhino/Grasshopper document lock
for more than {timeout} seconds. Rhino may be running a long operation or be wedged (e.g. an
infinite-loop script component). If this persists, restart Rhino."*
PROVENANCE: `src/Cordyceps/Core/GrasshopperContext.cs` `DOCUMENT_LOCK_TIMEOUT_SECONDS` docstring;
`src/Cordyceps/Core/DocumentLock.cs` `Run` and `DocumentBusyException`;
`.prawduct/artifacts/api-notes-rhinocommon.md` (cited as the probe record)
VOLATILE: 120 seconds — `const int DOCUMENT_LOCK_TIMEOUT_SECONDS = 120` in `GrasshopperContext`
TENSION: none

**RULE:** Add a re-entrancy guard that runs inline when you are already on the host thread —
re-marshaling deadlocks, and taking the shared lock there deadlocks against a worker already inside
the invoke.
FIRE-SITE: A host callback calls your own marshaling helper and the process freezes.
LAYER: L3
KIND: diagnostic
EVIDENCE: measured — both overloads open with `if (!RhinoApp.InvokeRequired) return action();` and the
comment gives both deadlocks: *"Re-marshaling via InvokeAndWait from the UI thread would deadlock, and
acquiring the document lock here could deadlock against a worker thread already blocked in
InvokeAndWait."*
PROVENANCE: `src/Cordyceps/Core/GrasshopperContext.cs` `ExecuteOnUiThread<T>` and
`ExecuteOnUiThread(Action)` (the guard at the top of each)
VOLATILE: none
TENSION: the inline path skips both the document lock AND `BeginUiWork`, so re-entrant work is neither
serialized nor counted. Deliberate — it is already inside a counted outer call — but it means the
depth counter measures marshaling events, not UI-thread time.

**RULE:** Model the lifecycle as one explicit state enum, not a conjunction of booleans — teardown
needs a `Stopping` phase to live in.
FIRE-SITE: You are adding a fourth boolean to describe what your server is doing.
LAYER: L3
KIND: pattern
EVIDENCE: incident, and the trigger was a *planned* feature that the old encoding could not
represent — *"`McpServer` lifecycle was reconstructed from three interdependent signals (`IsRunning` +
`StartError` + `_context`); upcoming teardown-topology work (chunk 03) adds a real Stopping window,
which that combinatorial encoding can't represent safely."* The enum comes with a predicate table
rather than inline conditions (*"so `McpServer` guards and the tests share one definition instead of
each hand-coding the rules"*): `CanStart` from `Stopped|Failed` only, `CanStop` from `Running` only,
and `IsRunning` becomes derived.
PROVENANCE: `src/Cordyceps/Core/ServerState.cs` `ServerState` enum and `ServerStateTransitions`;
`src/Cordyceps/McpServer.cs` `_state` / `IsRunning` / the `CanStart`/`CanStop` guards in `Start` and
`Stop`; `src/Cordyceps.Tests/ServerStateTransitionsTests.cs`; `.prawduct/change-log.md`
`## 2026-07-02: ServerState enum as lifecycle single source of truth (reliability chunk 02)`
VOLATILE: none
TENSION: none

**RULE:** Release the port on EVERY path that ends the session, including the host's document-close
hook — not just the one obvious teardown callback.
FIRE-SITE: Your server's teardown is wired to one lifecycle event and you have not enumerated the
others.
LAYER: L3
KIND: diagnostic
EVIDENCE: incident, and the failure was permanent — *"Previously the server only shut down when the
component was deleted from the canvas; closing the `.gh` file left an orphaned server holding the
port, so reopening the same file failed permanently with "port is already in use by another Cordyceps
component" until Rhino restarted."* The host's behaviour is the trap, and the code names it:
*"Grasshopper does NOT call RemovedFromDocument when a document is closed/unloaded, so without this
hook a closed document left the server running and the port owned."* Both hooks now funnel into one
`ReleaseServer`, and the reopen path schedules a solution so the single startup path restarts it.
PROVENANCE: `src/Cordyceps/CordycepsComponent.cs` `DocumentContextChanged` (docstring + the
`Close`/`Unloaded` and `Open`/`Loaded` arms) and `ReleaseServer`; `CHANGELOG.md` `## [1.5.0]` →
`### Fixed` → *"Closing a Grasshopper document now stops the MCP server"*
VOLATILE: none
TENSION: none

**RULE:** Bound every process-lifetime store an agent can grow, evict oldest-first, and REPORT what
was evicted along with the cap in every listing.
FIRE-SITE: A dictionary keyed by an agent-chosen name, living as long as the host process.
LAYER: L3
KIND: pattern
EVIDENCE: incident, compounded by a docs decision — *"`GhDocumentTool._snapshots` was an unbounded
process-lifetime dictionary of full document serializations — and with undo/redo formally cut, every
documented mutation workflow ("snapshot before changes, revert to restore") funnels into it, so memory
grew for the life of the Rhino session."* The bound is 20, oldest-first, with same-name re-save
replacing in place and refreshing its age; the response gained `maxSnapshots` + `evicted`, and the
eviction is also logged at level 0 *"so an operator debugging a [missing snapshot] "*. The cap even
reaches the instructions: *"snapshot_delete (max 20 snapshots kept; oldest evicted)"*.
PROVENANCE: `src/Cordyceps/Core/SnapshotStore.cs` class summary and `MaxSnapshots`;
`src/Cordyceps/Tools/Unified/GhDocumentTool.cs` — the `_snapshots` field, the `evicted` return and the
`["snapshot"]` `ActionInfo` description; `src/Cordyceps/McpServer.cs` `GetServerInstructions`
(`gh_document` line); `.prawduct/change-log.md` `## 2026-07-02: bounded snapshot store +
snapshot_delete (reliability chunk 04)`
VOLATILE: cap 20 (`MaxSnapshots` in `GhDocumentTool`); log ring cap 500
(`const int MaxEntries = 500` in `DebugLog`)
TENSION: none. Same pattern twice in this tree — `LogBuffer` (500 entries) and `SnapshotStore` (20),
the second explicitly *"(LogBuffer pattern)"*.

**RULE:** A signal is only as trustworthy as what the REST of the system does to it — verifying that
your probe never blocks is not verifying that what it reports is true.
FIRE-SITE: You have just proved your new health signal is cheap and non-blocking, and are about to
ship it.
LAYER: L3
KIND: stance
EVIDENCE: incident, found by two independent reviewers rather than by the author — *"The liveness
heartbeat was starved not by the probe (which never marshals) but by ordinary tool calls, which all
run ON the UI thread via `InvokeAndWait` — so a long bake or capture made a healthy host report a
modal dialog that was not there, and the attached guidance told the agent to stop and fetch a human.
When adding an inferred signal, enumerate every OTHER code path that can move its inputs, not just the
read path."* The fix made the inference three conditions, and the code insists the third is not
cosmetic: *"The third condition is not a refinement, it is load-bearing."*
PROVENANCE: `.prawduct/learnings.md` `## A signal is only as trustworthy as what the REST of the
system does to it`; `src/Cordyceps/Core/SolverState.cs` `HostStatus.ModalInferred` docstring and
`Derive` (`modalInferred = ui == UiLiveness.Blocked && !solving && !uiWorkInProgress`);
`.prawduct/change-log.md` `## 2026-08-21: bridge liveness …` → `**Modal inference is guarded on three
conditions, not two**`
VOLATILE: none
TENSION: none. The single most transferable item in this corpus.

**RULE:** Do not gate such an inference on in-flight request count — that counts the probe's own
request and disables the inference permanently. Instrument the RESOURCE, and keep the probe out by
construction.
FIRE-SITE: You have the false-positive above and the obvious fix is "don't infer while requests are
in flight."
LAYER: L3
KIND: diagnostic
EVIDENCE: incident, recorded as the trap in the obvious fix — *"note the trap in the obvious fix:
gating the inference on in-flight HTTP requests would have counted the probe's own request and
disabled it permanently — the correct signal was UI-thread occupancy, recorded at
`GrasshopperContext`'s marshaling choke point, which the probe deliberately never enters."* The
"by construction" half is asserted at the counter: *"Deliberately NOT called by the connection probe:
the probe never touches the UI thread, so counting it would make the inference report "busy with our
own work" during the very call asking whether a human is needed."* And it is true of the code —
`ActionConnection` contains no `ExecuteOnUiThread`. Note that `InFlightRequests` **is** still reported
(`in_flight_requests` in the full block) — it is data, not a gate.
PROVENANCE: `.prawduct/learnings.md` `## A signal is only as trustworthy as what the REST of the
system does to it`; `src/Cordyceps/Core/SolverState.cs` `BeginUiWork` docstring;
`src/Cordyceps/Tools/Unified/GhInspectTool.cs` `ActionConnection`;
`src/Cordyceps/Core/StatusEnvelope.cs` `ToFullJson` (`["in_flight_requests"]`)
VOLATILE: none
TENSION: none

**RULE:** Track host occupancy as a DEPTH COUNTER, not a flag, always paired in a `finally` — a
leaked increment suppresses the inference for the process lifetime.
FIRE-SITE: Recording "we are currently busy" from concurrent handlers.
LAYER: L3
KIND: pattern
EVIDENCE: measured — the field's docstring gives both the why and the failure mode: *"A depth, not a
flag, because concurrent HTTP handlers each marshal independently and the last one to finish must be
the one that clears it"* and *"always pair with `EndUiWork` in a finally — a leaked increment
suppresses modal inference for the rest of the session, which is the failure mode this counter exists
to prevent."* Both `ExecuteOnUiThread` overloads wrap `InvokeAndWait` in `try/finally` around
`BeginUiWork`/`EndUiWork`, and `EndUiWork` additionally floors at zero
(`if (Interlocked.Decrement(...) < 0) Interlocked.Exchange(..., 0)`).
PROVENANCE: `src/Cordyceps/Core/SolverState.cs` `_uiWorkDepth`, `BeginUiWork`, `EndUiWork`;
`src/Cordyceps/Core/GrasshopperContext.cs` both `ExecuteOnUiThread` overloads (the `finally`)
VOLATILE: none
TENSION: none

**RULE:** Make the heartbeat's landing BE the evidence: queue the stamp onto the watched resource and
never wait for it, so a wedged resource leaves the stamp stale instead of blocking the timer.
FIRE-SITE: Implementing a liveness heartbeat for a single-threaded resource. `Invoke…AndWait` from
the timer is the natural call.
LAYER: L3
KIND: pattern
EVIDENCE: measured — the rule is stated twice, once per side. At the producer: *"The stamp *landing* is
the evidence that the UI thread is draining its queue, which is why this queues and never waits: a
wedged UI thread must leave the heartbeat stale, not block the timer."* At the consumer: *"Called from
the Rhino UI thread — the stamp landing is itself the evidence that the UI thread is draining its
queue, so this must never be called from a worker thread or the signal means nothing."* Mechanism is
`RhinoApp.InvokeOnUiThread` (queue) inside a `System.Threading.Timer` at 1 s.
PROVENANCE: `src/Cordyceps/CordycepsComponent.cs` `StampHeartbeat` and `HEARTBEAT_INTERVAL_MS`;
`src/Cordyceps/Core/SolverState.cs` `Heartbeat()` / `Heartbeat(Guid?, string)`
VOLATILE: 1000 ms tick (`HEARTBEAT_INTERVAL_MS`), 5 s staleness window
(`DefaultHeartbeatStaleAfter = TimeSpan.FromSeconds(5)`) — the window's docstring explains the
relationship: *"Comfortably longer than the tick interval ... but short enough that a caller learns
about a wedged host in seconds rather than minutes."*
TENSION: none — **absent from the first pass**, though it is the mechanism the first pass's liveness
rules all depend on.

**RULE:** Give a single-outstanding gate an EXPIRY. An unconditional "only one queued at a time" flag
freezes your heartbeat forever the first time a queued stamp is dropped.
FIRE-SITE: Debouncing a queued-work token with a boolean, so a wedged consumer cannot accumulate a
backlog.
LAYER: L3
KIND: diagnostic
EVIDENCE: designed-untested (reasoned, with the failure named, and no test names the constant) — *"How
long an unrun heartbeat stamp blocks further ones. A wedged UI thread must not accumulate a stamp per
second, but the gate must also expire: if a queued stamp is ever dropped (host teardown, a torn-down
message loop) an unconditional gate would leave the heartbeat frozen and report a perfectly healthy
host as blocked forever."* Mechanism is a ticks-valued claim with a `CompareExchange`, cleared in a
`finally` inside the queued action and also on a queue-failure catch.
PROVENANCE: `src/Cordyceps/CordycepsComponent.cs` `HEARTBEAT_QUEUE_GATE`, `_heartbeatQueuedTicks`,
`StampHeartbeat`
VOLATILE: 30 seconds (`HEARTBEAT_QUEUE_GATE`)
TENSION: 30 s is 6× the 5 s staleness window, so a dropped stamp shows as "blocked" for up to 25 s
before the gate expires. Nothing in the tree reconciles the two constants.
**Absent from the first pass.**

**RULE:** Make cached liveness state self-correcting: an end-event for something never started is a
no-op, and a resource that disappears mid-operation is forgotten outright — a stuck "busy" flag
reports a healthy system as permanently busy.
FIRE-SITE: Your state machine is fed by host events you do not control and one of them can be missed.
LAYER: L3
KIND: pattern
EVIDENCE: measured — three places say it. `EndSolution`: *"Ending a document that was never marked
solving is a no-op: the state must be self-correcting, because a missed start event must not make a
later end throw, and a stuck "solving" flag would report a healthy bridge as permanently busy."*
`ForgetDocument`: *"Without this, a document unloaded mid-solve (so its `SolutionEnd` never arrives)
would be reported as solving forever."* And `SolutionWatcher.Unwatch` calls `ForgetDocument` with the
same comment. Both event handlers also swallow-and-log rather than throwing into the host's dispatch,
with a waiver explaining why: *"a throw here would abort the user's solve."*
PROVENANCE: `src/Cordyceps/Core/SolverState.cs` `EndSolution`, `ForgetDocument`;
`src/Cordyceps/Core/SolutionWatcher.cs` `Unwatch`, `OnSolutionStart`, `OnSolutionEnd`
VOLATILE: none
TENSION: none — **absent from the first pass.**

**RULE:** Key shared-resource state by the thing the host raises events for, and watch the whole
event source — not just the instance you are embedded in.
FIRE-SITE: Subscribing to host events, and the natural scope is "my own document/session/window."
LAYER: L3
KIND: diagnostic
EVIDENCE: incident, and it arrived as a subagent CONTRADICTING its own spec and being right —
*"Track A was specified to subscribe to solution events per bridge instance and instead watched
`GH_DocumentServer` globally — correctly, because documents share one Rhino UI thread and a solve in a
definition containing no bridge component would otherwise read as "UI blocked, nothing solving",
producing a false "a human must intervene"."* The code carries the reasoning: *"if that solve went
unrecorded, the status model would see a blocked UI with nothing solving and wrongly report a modal
dialog needing a human."* Every subscription is paired (`DocumentRemoved` detaches and forgets;
`Stop()` detaches everything).
PROVENANCE: `src/Cordyceps/Core/SolutionWatcher.cs` class summary and `Watch`/`Unwatch`;
`src/Cordyceps/Core/SolverState.cs` class summary (*"Solve state is keyed by document id because
Grasshopper raises `SolutionStart`/`SolutionEnd` per document"*); `.prawduct/learnings.md`
`## Give worktree subagents the WHY behind a constraint, not just the constraint`
VOLATILE: none
TENSION: none — **absent from the first pass.**

**RULE:** When several concurrent operations could be the one blocking, report the EARLIEST — that is
the one the caller has been waiting on longest — and keep the original start time across a re-entered
begin event.
FIRE-SITE: `solving_since` on a system where two solves can overlap, or where the host re-raises a
start event.
LAYER: L3
KIND: pattern
EVIDENCE: measured — `ActiveSolve` picks the minimum `StartedUtc` with the docstring *"the one that
started first, since that is the one a caller has been waiting on longest"*; `BeginSolution`'s
`AddOrUpdate` update-branch keeps `existing.StartedUtc`, documented as *"so `solving_since` reports
how long the caller has actually been waiting rather than restarting the clock on a nested or
re-raised event."*
PROVENANCE: `src/Cordyceps/Core/SolverState.cs` `ActiveSolve`, `BeginSolution`
VOLATILE: none
TENSION: none — **absent from the first pass.**

**RULE:** When a component publishes a callback into shared registry state, cache the delegate
instance and withdraw only if you are still the registered one — a replacement that started meanwhile
must keep working.
FIRE-SITE: Restart-in-place, where the old instance's teardown runs after the new one's startup.
LAYER: L3
KIND: diagnostic
EVIDENCE: measured — two halves, each with its reason in the tree. The cache: *"Cached so publish and
withdraw hand the status registry the SAME delegate instance — the registry compares by reference, and
converting a method group creates a fresh delegate every time, which would leave a stopped server's
provider registered forever."* The conditional withdraw: `ClearServerSnapshot` is
`Interlocked.CompareExchange(ref _serverSnapshot, null, provider)`, i.e. *"Only clears if `provider`
is still the registered one, so a server shutting down cannot unpublish its replacement."* The
`Stop()` teardown calls it in its `finally`.
PROVENANCE: `src/Cordyceps/McpServer.cs` `_statusProvider` (its docstring) and `Stop`'s `finally`;
`src/Cordyceps/Core/SolverState.cs` `PublishServerSnapshot`, `ClearServerSnapshot`
VOLATILE: none
TENSION: none — **absent from the first pass.** Two independent failure modes in one small pattern:
leak-forever (method-group conversion) and clobber-the-successor (unconditional clear).

**RULE:** Stop the background timer when nothing owns the resource any more — a heartbeat outliving
its last reader keeps threads alive in the host for nothing.
FIRE-SITE: You started a process-wide timer on first use and never wrote the other half.
LAYER: L3
KIND: pattern
EVIDENCE: measured — `StopHeartbeatIfIdle`'s docstring: *"Stop the heartbeat once no component owns a
port — nothing reads it then, and a timer outliving the last server would keep the plugin's threads
alive."* Called from `ReleaseServer` under the lock, paired with `EnsureHeartbeat` in `SolveInstance`;
the watcher is detached in the same path, *"outside the lock, because the watcher takes its own and
nothing should hold two at once."*
PROVENANCE: `src/Cordyceps/CordycepsComponent.cs` `EnsureHeartbeat`, `StopHeartbeatIfIdle`,
`ReleaseServer`
VOLATILE: none
TENSION: none — **absent from the first pass.**

**RULE:** Defer a host refresh you trigger from a request rather than expiring inline — an inline
invalidation landing mid-operation can raise a modal dialog that blocks every later call, and a burst
then coalesces into one refresh.
FIRE-SITE: Your server touches host state on every request to update a status display.
LAYER: L3
KIND: diagnostic
EVIDENCE: incident, and this is the root of the entire liveness cluster — *"Every MCP call refreshed
the Cordyceps component by expiring it immediately. When that landed while a solution was running,
Grasshopper raised its modal breakpoint dialog ("The 'Cordyceps (MCP)' object expired during a
solution"), which stops the canvas solving and makes every subsequent MCP call time out until a human
clicks Close — fatal for unattended sessions. The refresh is now deferred to after the current
solution, so the condition cannot arise from an MCP-initiated call. A burst of calls also coalesces
into a single recompute instead of one per call."* In code: `RefreshComponent` queues onto the UI
thread and calls `document.ScheduleSolution(REFRESH_SOLUTION_DELAY_MS, d => SafeExpire(instance))`
instead of `ExpireSolution(true)`, and it is called from `McpServer.RecordCommand` — i.e. on every
request.
PROVENANCE: `src/Cordyceps/CordycepsComponent.cs` `RefreshComponent` and
`REFRESH_SOLUTION_DELAY_MS`; `src/Cordyceps/McpServer.cs` `RecordCommand`;
`CHANGELOG.md` `## [1.5.0]` → `### Fixed` → *"MCP calls can no longer freeze the canvas with a "object
expired during a solution" dialog"*
VOLATILE: 10 ms (`REFRESH_SOLUTION_DELAY_MS`)
TENSION: **the modal inference cannot detect this particular dialog, and that is recorded rather than
hidden** — *"`modal_inferred` does not fire for issue #30's own dialog, which appears *inside* a solve
and so reads as "busy solving". The deferred refresh prevents that dialog at the source; the inference
catches every other modal. Recorded in VRF-012 so a verifier does not test for the wrong thing."*
**Absent from the first pass**, which mined the detection layer and missed the prevention layer.

**RULE:** Extract every pure decision at the MCP boundary into a host-free module linked into the
test project — and treat "this feels like host glue" as the signal to extract, not the excuse to skip.
FIRE-SITE: You are writing a decision inside a file that imports the host SDK, and a unit test can
never reach it.
LAYER: L3
KIND: pattern
EVIDENCE: measured, and the most damning instance is that the FIX ITSELF was unreachable — *"New pure
decision logic goes in a host-free `Core/` file linked into the test project WITH tests in the same
chunk, even when it feels like host glue — the audit found ~10 helpers untestable only because they
sat in host-coupled files."* At this commit: **27** `Core/*.cs` files are linked into
`Cordyceps.Tests` out of 34 (the 7 unlinked are the genuinely host-coupled ones: `ComponentRegistry`,
`DebugLog`, `DeprecationRegistry`, `GrasshopperContext`, `PluginRegistry`, `SolutionWatcher`,
`ToolHelpers`), carrying **5,400 lines** of test code and **579** passing tests against zero live-host
coverage. Each linked file's summary states the constraint, e.g. *"Host-independent (no
Grasshopper/Rhino references, no `DebugLog`) so the transitions and the modal inference are
unit-tested."*
PROVENANCE: `src/Cordyceps.Tests/Cordyceps.Tests.csproj` — the `<!-- Link source files directly … -->`
ItemGroup; `.prawduct/learnings.md` `## Validate-then-mutate, and never conflate "unparseable" with
"empty"` and `## Code linked into `Cordyceps.Tests` must stay host-free`;
`.prawduct/artifacts/build-plan-janitor-2026-07-02.md` `### Chunk 06`
VOLATILE: **the first pass's "21 host-free modules ... ~2,100 lines of tests" is CONTRADICTED at this
commit.** Re-derive:
```sh
grep -c 'Compile Include' src/Cordyceps.Tests/Cordyceps.Tests.csproj     # 27
ls src/Cordyceps.Tests/*Tests.cs | xargs wc -l | tail -1                 # 5400 total
```
The 579 figure is from `.prawduct/.test-evidence.json` (`"passed": 579`, `2026-08-29T20:51:12Z`) —
**gitignored, not at this SHA**; the tracked progression is 53 → 68 → 137 → 149 → 169 → 224 → 370 →
389 → 399 → 406 → 550 across the change-log entries.
TENSION: the Critic finding that motivated the rule is worth carrying verbatim, because it is about
the act of fixing: *"the Critic caught that the `verified`-field emission decision — which was the fix
itself — sat where no test could reach it."*

**RULE:** In a module you have deliberately kept dependency-free, de-silence a `catch` by NARROWING
the exception type, not by adding logging — the logger is literally uncompilable there.
FIRE-SITE: A review says "this catch swallows silently," and you reach for the log call.
LAYER: L3
KIND: constraint
EVIDENCE: incident — *"`Core/DebugLog.cs` uses `RhinoApp.WriteLine`, so it is host-coupled and not
linkable. Therefore: when de-silencing a `catch` (or adding any logging) in one of those linked files,
you can't add a `DebugLog` call — it won't compile in the test project. Narrow the catch to the
expected exception type instead (e.g. `GetParam` → `FormatException`/`InvalidCastException`/
`OverflowException`/`JsonException`). Narrowing is usually the better fix anyway: unexpected errors
surface instead of being swallowed."* Visible in the code: `UnifiedToolHelpers.GetParam` catches
exactly `when (ex is FormatException or InvalidCastException or OverflowException or JsonException)`;
`McpResultFormatter.IsErrorResult` catches only `JsonException`; `StatusEnvelope.Inject` only
`JsonException`.
PROVENANCE: `.prawduct/learnings.md` `## Code linked into `Cordyceps.Tests` must stay host-free — can't
call `DebugLog``; `src/Cordyceps/Core/UnifiedToolHelpers.cs` `GetParam`;
`src/Cordyceps/Core/McpResultFormatter.cs` `IsErrorResult`; `src/Cordyceps/Core/DebugLog.cs`
(the `RhinoApp.WriteLine` that makes it unlinkable)
VOLATILE: none
TENSION: the host-coupled files keep broad catches, each carrying a `prawduct:allow
prawduct/broad-except` waiver whose comment names the boundary and the reason — 11 in the tree
(`grep -rc 'prawduct:allow prawduct/broad-except' src/ --include='*.cs'`), every one at a host callback or a protocol
boundary. The pattern *"broad catch allowed only where an escaping exception would take the host
down, and only with the reason written at the catch"* is itself a rule worth carrying.

**RULE:** A test that claims a TIMING contract must drive real concurrency — a background task plus a
completion source that deliberately never completes during the assertion window.
FIRE-SITE: You have named a test `…_TakesSnapshot_…` or `…_DrainsWithinBudget` and stood in an
already-completed task.
LAYER: L3
KIND: constraint
EVIDENCE: incident — *"a test whose name claims a *timing* contract ... must drive it with real
concurrency ... Standing in an *already-completed* task makes the test pass vacuously — it would still
pass if the implementation re-read live state — which is false confidence, worse than no test. The
Chunk-02 `DrainWithin_TakesSnapshot...` test shipped vacuous and the Critic ... caught it."* Eight
`TaskCompletionSource` uses across the file, including the never-completing `late` and `stillRunning`
gates.
PROVENANCE: `.prawduct/learnings.md` `## A test naming a race/snapshot/ordering contract must actually
exercise concurrency`; `src/Cordyceps.Tests/InFlightRequestsTests.cs`
`DrainWithin_TakesSnapshot_IgnoresTasksTrackedAfterItStarts`,
`DrainWithin_FaultCoincidingWithTimeout_ReturnsFalse`
VOLATILE: none
TENSION: with the parallelization rule below — real concurrency tests are exactly what a contended CI
runner flakes.

**RULE:** Disable suite parallelization when you assert timing or concurrency on a small CI runner —
and treat a flaky required check as unacceptable rather than as noise.
FIRE-SITE: A timing test passes locally and on one PR, then fails twice on the next with no relevant
change.
LAYER: L3
KIND: decision-point
EVIDENCE: incident, with the runner size named — *"Under xUnit's default parallel collections, those
tests contend for the **2-core CI runner's** thread pool — a sibling test's `Thread.Sleep`/blocking
`Wait` can starve a `ContinueWith(..., TaskScheduler.Default)` continuation past its budget, so
`build-test` flakes (passed locally + on #21, failed twice on #22 with no relevant change). Since
`build-test` is the **required check for strict `main` protection**, a flaky gate is unacceptable. The
suite is sub-second, so serial execution costs ~nothing."* The trade is written at the assembly
attribute itself: *"No assertion is weakened — the contracts still run, just without the contention
that made a valid assertion flaky."*
PROVENANCE: `src/Cordyceps.Tests/AssemblyInfo.cs` (the comment above
`[assembly: CollectionBehavior(DisableTestParallelization = true)]`); `.prawduct/learnings.md`
`## Test parallelization is disabled on purpose — don't re-enable it naively`;
`.prawduct/artifacts/project-preferences.md` `## Testing` → "Parallelization"
VOLATILE: "2-core runner", "sub-second suite" — both age; the suite is now 5,400 lines / 579 tests
TENSION: with the real-concurrency rule above. The resolution stated here is the useful part: make the
timing tests deterministic (an internal seam) *before* re-enabling parallelism, rather than choosing
between them.

**RULE:** Record the decision at the catch site when a contract is genuinely undecided, and pin it
with a regression test even when today's behaviour is unchanged — so the contract stops depending on
an undocumented platform nuance.
FIRE-SITE: You find a `return true` in an exception handler and cannot tell whether it is right.
LAYER: L3
KIND: pattern
EVIDENCE: measured — *"`InFlightRequests.DrainWithin` returned `true` on any `AggregateException`,
which could mask a drain-budget timeout coinciding with a handler fault — the combination was
undecided and untested."* The fix changes the return to `pending.All(t => t.IsCompleted)` and says
plainly that this is defensive: *"Empirically `Task.WaitAll` only throws here when they all did (a
timeout returns false instead of throwing), so this check's false branch is unreachable today — it is
a defensive assertion that keeps the contract independent of that undocumented BCL nuance, not a path
any test can reach."* The comment then names the two tests that DO characterize the observable
contract — which is what stops the note from being an excuse.
PROVENANCE: `src/Cordyceps/Core/InFlightRequests.cs` `DrainWithin` (the `catch (AggregateException)`
comment); `src/Cordyceps.Tests/InFlightRequestsTests.cs`
`DrainWithin_FaultCoincidingWithTimeout_ReturnsFalse`,
`DrainWithin_FaultedPlusLateCompleting_WithinBudget_ReturnsTrue`; `.prawduct/change-log.md`
`## 2026-07-02: DrainWithin fault-vs-timeout contract pinned (reliability chunk 01)`
VOLATILE: none
TENSION: none — **absent from the first pass.**

**RULE:** Keep ERROR-level logs reaching the operator regardless of the verbosity setting, buffer
every level regardless of the gate, and expose the buffer as a tool action the agent can read.
FIRE-SITE: Your log has a verbosity dial and the operator missed the one message that mattered.
LAYER: L3
KIND: pattern
EVIDENCE: measured — three separable decisions, each in code. `DebugLog.Error` passes
`messageLevel: 0` with the reason *"so errors always reach the Rhino command line regardless of the
configured DebugLevel (warnings stay at level 1)"*. `LogBuffer.Add` stores unconditionally and
*returns* the emission decision — *"Every message is stored regardless of level; the return value
tells the caller whether the message passes the level gate for console emission"* — which is also the
seam that made it testable (*"shipped as a host-free `LogBuffer` whose `Add()` returns the emission
decision, with `RhinoApp.WriteLine` staying in the wrapper — simpler seam, same testability
outcome"*). And `gh_inspect(action='log')` reads it back with an optional `clear`.
PROVENANCE: `src/Cordyceps/Core/DebugLog.cs` `Error` and `WriteLine`;
`src/Cordyceps/Core/LogBuffer.cs` `Add`, `GetEntries`;
`src/Cordyceps/Tools/Unified/GhInspectTool.cs` `ActionLog`; `.prawduct/change-log.md`
`## 2026-07-02: janitor full reliability audit …` → `**Deliberate deviations recorded**`
VOLATILE: 500-entry ring (`const int MaxEntries = 500` in `DebugLog`)
TENSION: none

**RULE:** Maintain an explicit append-only queue of what only a running host can confirm, with repro
steps and the expected pre-fix symptom — and give it a READ, or it decays into a write-only list.
FIRE-SITE: You are about to write "verified live in Rhino" into a commit message you have no way to
substantiate.
LAYER: L3
KIND: pattern
EVIDENCE: measured, and the decay is measurable in this very tree. The queue's form is good: each
entry carries `**Status:**`, `**Added:**`, `**Where to verify:**`, `**Why this needs a human:**` and a
numbered `**Verify:**` list, and one entry even records a known limitation so a verifier does not test
for the wrong thing (*"Known limitation to confirm, not a bug: `modal_inferred` will NOT fire for the
#30 dialog"*). **The decay: 14 of 14 entries are `pending`, and the gate that would read them is
off.**
```sh
grep -c '^## VRF-' .prawduct/operator-verification.md            # 14
grep -c '^\*\*Status:\*\* pending' .prawduct/operator-verification.md  # 14
grep -n 'operator_verification_required' .prawduct/project-state.yaml  # false
```
PROVENANCE: `.prawduct/operator-verification.md` `## VRF-001` … `## VRF-014` (and the `## VRF-012`
known-limitation note); `.prawduct/project-state.yaml` `operator_verification_required: false`
VOLATILE: **the first pass said "6 of 8 entries sat pending". CONTRADICTED at this commit: 14 of 14.**
The direction is the finding — the queue grew and the pending fraction went to 100%.
TENSION: with the L0 rule that a headless-hostless system MUST have such a queue. Both are true, which
is the point: the queue is necessary and, unread, worthless.

---

# L4 — client/host integration

**RULE:** Ship per-client configuration recipes, including a stdio↔HTTP bridge for clients that
only speak stdio — an HTTP MCP server is not installable by half your clients without one.
FIRE-SITE: Your README says "point your MCP client at http://127.0.0.1:PORT/mcp" and a user's client
has no HTTP transport.
LAYER: L4
KIND: pattern
EVIDENCE: measured — three collapsible recipes, and they are genuinely different shapes: Claude
Desktop gets `{"command": "npx", "args": ["-y", "mcp-remote", "http://127.0.0.1:26929/mcp"]}` with the
reason stated (*"Claude Desktop uses stdio transport, so it needs the `mcp-remote` bridge. Requires
Node.js."*) plus both OS config-file paths and a restart instruction; Claude Code gets a one-line
`claude mcp add --transport http …`; Cursor/VS Code get `{"type": "streamable-http", "url": …}`.
PROVENANCE: `README.md` `## Usage` step 2 — the three `<details>` blocks
VOLATILE: the bridge package name `mcp-remote`, the `--transport http` flag spelling, the
`"type": "streamable-http"` key — all client-side and all likely to move
TENSION: none. **Absent from the first pass**, which mined the transport and skipped the install UX.

**RULE:** Make the platform's package manager the recommended install path and keep the raw-file
download as the documented secondary, with the OS-specific unblock step spelled out for the manual
path only.
FIRE-SITE: Writing install instructions for a plugin whose host has a package manager you are not
using.
LAYER: L4
KIND: pattern
EVIDENCE: measured — `### Rhino Package Manager (recommended)` is three steps and states what it buys:
*"The Package Manager downloads the plugin, places it in the right folder, and unblocks it for you —
and future updates are one click."* `### Manual install` then carries the step the package manager
absorbs, per OS: *"Windows: right-click → Properties → check "Unblock""* and *"macOS: clear the
quarantine flag (e.g. `xattr -dr com.apple.quarantine <path-to-Cordyceps.gha>`)"*. The scoping is deliberate:
*"Clarified that file-unblocking (Windows) / quarantine-clearing (macOS) is only needed for manual
installs."*
PROVENANCE: `README.md` `## Installation`; `CHANGELOG.md` `## [1.5.0]` → `### Changed` →
*"README install instructions"*
VOLATILE: the `xattr` incantation
TENSION: none — **absent from the first pass.**

**RULE:** Point every download link at a stable "latest release asset" URL, never a branch-raw path —
and do not track the built binary, or the file at that path is the last *released* build and a tester
who swaps it in reports a false negative.
FIRE-SITE: Someone asks for a build of your development branch and you look for a file to hand them.
LAYER: L4
KIND: diagnostic
EVIDENCE: incident, with three distinct failures from one root — *"The tracked copy only refreshed at
release time, so on `develop` it was always the last *released* build. A tester who swapped it in
would run code with none of the branch's fixes and report a false negative (this nearly happened on
issues #27/#29/#30)."* And: *"`release.sh publish` shipped `releases/Cordyceps.gha` straight from the
working tree into both the Yak package and the GitHub Release asset without building it."* And the
churn: *"the binary embeds a build timestamp via `SourceRevisionId`, so every `dotnet build`/`dotnet
test` produces a different one, and while it was tracked each of those restamped it into `git
status`."* The fixes: `releases/` gitignored, `publish` runs `build_gha` before `prepare_dist`, the
README link moved *"from `raw/main/releases/...` to `/releases/latest/download/Cordyceps.gha`"* with a
`check_readme` grep pinning the new path, and CI uploads a per-commit artifact *"so any commit is
obtainable without a toolchain"*.
PROVENANCE: `README.md` `### Manual install` (the `releases/latest/download/Cordyceps.gha` link);
`src/Cordyceps/Cordyceps.csproj` `<SourceRevisionId>` and the `CopyToReleases` target;
`.prawduct/learnings.md` `## The built `.gha` is a build output, not a tracked file — don't
reintroduce it`; `.prawduct/change-log.md` `## 2026-08-25: the release publishes the binary it built
(release-artifact provenance)`
VOLATILE: the asset filename `Cordyceps.gha`; the 90-day CI retention
TENSION: none — **absent from the first pass.**

**RULE:** Keep the version string in lockstep across the build file, the package manifest and the
changelog, and make the release script bump all of them — a manifest nobody bumps drifts silently.
FIRE-SITE: Your release script bumps one file and you have three.
LAYER: L4
KIND: diagnostic
EVIDENCE: incident — *"A release version must match across `src/Cordyceps/Cordyceps.csproj`
`<Version>`, the tracked root `manifest.yml`, and `CHANGELOG.md`. The root `manifest.yml` is the yak
source-of-truth that `scripts/release.sh` → `prepare_dist` copies into the (gitignored) `dist/`. It
silently drifted to 1.4.0 while shipping 1.4.9 because `release.sh` only bumped the csproj — fixed by
adding `update_manifest_version` to the script."*
PROVENANCE: `.prawduct/learnings.md` `## Version lives in three places; keep them in lockstep`;
`src/Cordyceps/Cordyceps.csproj` `<Version>` (1.5.0 at this commit); `manifest.yml`;
`.prawduct/change-log.md` `## 2026-06-20: Janitor maintenance pass`
VOLATILE: 1.5.0
TENSION: none — **absent from the first pass.**

**RULE:** Make the non-shippable build configuration fail loudly, so the artifact a user loads is the
one your CI tested.
FIRE-SITE: A user reports behaviour you cannot reproduce, and they are running a Debug build of your
plugin.
LAYER: L4
KIND: constraint
EVIDENCE: measured — `<Configurations>Release</Configurations>` plus an MSBuild target that errors
before the build: `<Error Text="Only Release builds are supported. Use 'dotnet build -c Release'." />`
under `Condition=" '$(Configuration)' != 'Release' "`. Enforcement is assigned, not aspirational:
*"Release configuration required for builds (Debug blocked) | Build target |
`src/Cordyceps/Cordyceps.csproj` (Debug build fails)"*.
PROVENANCE: `src/Cordyceps/Cordyceps.csproj` `BlockDebugBuilds` target;
`.prawduct/artifacts/project-preferences.md` `## Enforcement` table; `CLAUDE.md` `## Build Commands`
VOLATILE: none
TENSION: none — **absent from the first pass.**

**RULE:** Two JSON libraries in one server is acceptable when the split is deliberate and scoped —
but pin the wire format before you plan to converge them, and cost the convergence against the
runtime you actually ship on, not the one that motivated the change.
FIRE-SITE: A reviewer says "you have two JSON libraries" and you agree it should be one.
LAYER: L4
KIND: decision-point
EVIDENCE: incident, recorded as a decision NOT to build — *"The conversion's sole justification was a
net48 assembly-load conflict: on `net48` System.Text.Json arrives as a package needing `System.Memory`
>= 4.0.1.2 and `Unsafe` 6.0.0.0, while Rhino 7 already holds older versions in-process for Roslyn,
.NET Framework binds by exact version, and a `.gha` cannot inject binding redirects. net48 was
declined, and on .NET 8 System.Text.Json IS the BCL — no package, no transitive versions, nothing to
conflict. The residual "one JSON library" argument points the other way on this runtime."* The split
is scoped in writing: *"System.Text.Json used only in type-conversion code and tests"* / Newtonsoft
for payloads. And the recon found the cost: *"five behavior traps in what the issue framed as
mechanical ... Three were untested, so the reporter's "all 56 tests pass" could not have caught a
regression in them."*
PROVENANCE: `.prawduct/change-log.md` `## 2026-08-21: System.Text.Json to Newtonsoft conversion
dropped (issue #28 finding)`; `.prawduct/artifacts/project-preferences.md` `## Tooling` → "Key
libraries"; visible in code: `JsonRpcEnvelope`/`JsonTypeConverter` use `System.Text.Json`,
`McpResultFormatter`/`StatusEnvelope`/every tool use `Newtonsoft.Json`
VOLATILE: the net48/Rhino 7 framing — the whole argument turns on a target that was declined
TENSION: none — **absent from the first pass.** The transferable shape: *a dependency-hygiene argument
inherited from a platform you decided not to support usually reverses on the platform you did.*

---

# Doc-vs-code drift in cordyceps — bug reports owed back to that repo, not corpus material

All six are at `f07eb79373cd84583a67ae0c6090c931c30ca7a6`.

1. **`McpTestingGuide.md` states the error contract backwards for one case, and a tester following it
   would file a false regression.** The guide says: *"Reserve JSON-RPC protocol errors (e.g. code
   `-32603`) for request-level problems like an unknown tool **or a missing required parameter**, not
   for tool-execution failures."* But in `McpServer.HandleToolCallAsync` the missing-parameter throw
   (`throw new InvalidOperationException($"Missing required parameter: {param.Name}")`) is *inside*
   the `try` whose catch returns a structured `{success:false}` result with `isError:true` — only the
   unknown-tool throw sits outside it. Carried over from the first pass and re-confirmed.
   *Anchor:* `src/Cordyceps/Knowledge/McpTestingGuide.md` `## Part 5: Error Handling`, final paragraph,
   vs `src/Cordyceps/McpServer.cs` `HandleToolCallAsync`.

2. **The two primary architecture briefings a new contributor or agent reads describe an SSE server
   that does not exist.** `CLAUDE.md`: *"**McpServer.cs** - HTTP/SSE server implementing the MCP
   protocol ... and manages SSE sessions for streaming responses."* `boundary-patterns.md`: *"over
   HTTP+SSE (default port 26929)."* The code is stateless Streamable HTTP: GET and DELETE on `/mcp`
   return 405, `grep -rn 'text/event-stream\|EventStream' src/ --include='*.cs'` returns nothing, and
   the class summary says *"Streamable HTTP transport ... with stateless mode."* Carried over from the
   first pass and re-confirmed.
   *Anchors:* `CLAUDE.md` `## Architecture` → `### Core Components` → the `McpServer.cs` paragraph;
   `.prawduct/artifacts/boundary-patterns.md` `### MCP Tool / Action Contract` → `**Consumer:**`.

3. **NEW — a count in two docstrings is off by one, in the rationale for the design.**
   `StatusEnvelope`'s class summary says *"without touching any of the 19 tool files"* and
   `McpServer.WithStatus`'s says *"19 tool files cannot drift out of sync with one they never
   mention."* `ls src/Cordyceps/Tools/Unified/*.cs | wc -l` → **18**. Harmless in effect, but it is
   the number carrying the argument for the choke-point design, and a corpus reader will copy it.
   *Anchors:* `src/Cordyceps/Core/StatusEnvelope.cs` class summary;
   `src/Cordyceps/McpServer.cs` `WithStatus` docstring.

4. **NEW — `CHANGELOG.md` attributes the 49% knowledge-base reduction to a release that does not
   contain it.** The `## [1.4.5]` → `### Changed` → *"Knowledge base optimization - 49% token
   reduction (1648 → 835 lines)"* bullet describes commit `02b800d`, which is dated 21 seconds after
   the `Release v1.4.5` commit and is **not** an ancestor of the `v1.4.5` tag
   (`git merge-base --is-ancestor 02b800d v1.4.5` → non-zero; `git tag --contains 02b800d` lists
   v1.4.6 and later). At the `v1.4.5` tag the Knowledge corpus is still 1636 lines. Also: the "before"
   figure 1648 does not reproduce — `wc -l` over the same file set at `02b800d^` gives **1636**.
   *Anchor:* `CHANGELOG.md` `## [1.4.5]` → `### Changed`; commit `02b800d`.

5. **NEW — a count disagrees with itself across the commit and the changelog for the same change.**
   Commit `306f35d`'s message says *"Normalize **17** string params to native numeric types"*; the
   `CHANGELOG.md` `## [1.4.9]` → `### Changed` → *"Accurate MCP schema types"* bullet enumerates
   **19** parameter names. One of the two is wrong and neither is derivable from HEAD.
   *Anchors:* commit `306f35d` message; `CHANGELOG.md` `## [1.4.9]` → `### Changed`.

6. **NEW — `boundary-patterns.md` presents a closed bug as pending, inside the paragraph that tells a
   contributor what the boundary's live risk is.** *"(The pending `gh_script` language bug is a live
   example: the docs/templates show Python bodies without the `#! python 3` directive the host now
   requires.)"* That bug is GHS-7K2P, fixed by `Core/ScriptDirective` with 28 unit tests, and the
   directive-less-body case additionally got a `languageWarning` (issue #15). Both shipped; the
   `CommonErrorsGuide` covers them.
   *Anchor:* `.prawduct/artifacts/boundary-patterns.md` `### Embedded Documentation Contract`, final
   parenthesis.

**Governance-only, mentioned for completeness rather than as a bug in the product:**
`.prawduct/artifacts/build-plan-reliability.md` `## Status` still shows all six chunks unticked for
work merged in PR #26. The file's own `Context:` paragraph explains why and calls it out, and
`learnings.md` and two change-log entries discuss it — so it is a known, documented state, not a
silent one.

---

# What the first pass got wrong, in one place

| First pass said | This pass found | Disposition |
|---|---|---|
| header: *"60 rules"* | the body holds **68** bullets | miscount in its own title |
| server instructions *"~60 lines"* | **37** lines / 3,589 chars | CONTRADICTED |
| *"21 host-free modules ... ~2,100 lines of tests"* | **27** linked modules, **5,400** lines | CONTRADICTED |
| *"6 of 8 entries sat pending"* | **14 of 14** pending, gate still `false` | CONTRADICTED (worse, not better) |
| *"49% token reduction (1648 → 835 lines)"* | 49.0% real; before is **1636**, not 1648; shipped in **v1.4.6**, not v1.4.5; corpus now back to **1361** | sourced + re-derivable, with three corrections |
| *"~32 minutes of silence"* | self-reported prose in two tracked files; the measurement itself is in GitHub #29, outside the repo | sourced to prose only |
| *"37 parameters ... 43"* | exactly 37 and 43 | CONFIRMED |
| *"9 dedicated test cases"* | 9 test methods / 11 cases | CONFIRMED |
| *"~20 enumerated tests"* | exactly 20 `Inject_*` | CONFIRMED |
| *"28 doc-mutating actions"* | 28 `WithUndoRecord` call sites | CONFIRMED |
| *"8 + 3 pinned cases"* | 8 numeric + 3 string `[InlineData]` rows | CONFIRMED |
| *"17 named params"* | commit says 17, changelog enumerates 19 | sourced but self-inconsistent |
| *"10-HIGH-finding audit"* | `learnings.md` says 10; the plan's chunk holds 6 | sourced, with the discrepancy named |
| *"only where client and server are co-located"* (quoted) | phrase absent from the tree | UNSOURCED quote; precondition real but implicit in the localhost binding |
| *"Shipped output was `\"Accomplish goal now.\"`"* | string absent from the tree | UNSOURCED illustration; the mechanism is sourced |
| *"`protocolVersion` is hardcoded ... a gap"* | `"2025-06-18"` literal, `HandleInitialize()` takes no params | CONFIRMED |
| echo the id *"by preserving its raw literal text"* | mechanism is `JsonElement.Clone()` | behaviour right, mechanism misnamed |
