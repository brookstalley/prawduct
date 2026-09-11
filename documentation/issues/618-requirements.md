# Issue #618 — Coverage: Consume a Reference Index for Blast Radius: Requirements

`status: draft · stage: requirements · area: coverage · added: 2026-08-13 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/618`

Related: siblings #249 (socket 1 — diff coverage), #619 (socket 3 — diff-scoped mutation), #620
(socket 4 — API diff, already at requirements/design); GOV-2R8K, the single home of the shared
four-socket contract (`.prawduct/artifacts/change-evidence-design.md`), which this document must
not restate.

## Problem

Nothing in the framework today answers "what else does this change put at risk?" A reviewer sees
the changed lines and never their dependents — the only instrument that speaks to this question at
all is a Python-only symbol grep scoped to the tests tree, built for an unrelated purpose. Socket 2
is the instrument for exactly this gap: a reference index (SCIP, or a floor fallback) that reports,
for each changed symbol, its dependent set — zero test-runtime cost, which under the review-wall-
clock norm makes it preferred over the dynamic sockets rather than merely cheaper. The design
rationale, the four-socket contract shape, and the default report-only posture all live in
`change-evidence-design.md` and are not re-derived here; this document grounds socket 2's
acceptance criteria against the current codebase and resolves the decisions the design doc left
open where they are scoped to this socket alone.

## Grounding facts

Re-verified against the current tree (2026-08-13):

- **The floor fallback the design doc names already exists, is regex-based, and is scoped to the
  tests tree by construction.** `plugin/bin/test-reference-verify` is a standalone script (not a
  `gates.py` function), invoked from `verify_coverage` (`plugin/lib/gates.py:1236-1238,1272-1277`)
  and from `prawduct-hook`'s evidence-record path (`plugin/bin/prawduct-hook:3085-3115`). Symbol
  extraction is one compiled regex, `_PY_SYMBOL_RE` matching top-level `def`/`async def`/`class`
  lines (`test-reference-verify:64-66`); "referenced" is a pure substring test, `_has_reference`
  (`test-reference-verify:199-207`), against cached test-file contents — no AST on either end. The
  default search root is `tests_dirs` (`--tests-dir`, default `["tests"]`; `test-reference-verify:
  334`), and `_discover_tests` walks only that tree for `test_*.py`/`*_test.py` files
  (`test-reference-verify:167-179`) — exactly the "pointed at the tests tree" the design doc
  contrasts socket 2's floor against (`change-evidence-design.md:130-132`).
- **This mechanism is a named, ratified Python-specificity violation, not a neutral utility to
  extend.** `architecture.md:78`'s Retroactivity list names `test-reference-verify`
  (`_PY_SYMBOL_RE`, `_is_python_file`) as "Confirmed violating" the never-Python-specific norm,
  calling it out by name as feeding "a BLOCKING Goal 1 check that therefore passes silently on
  Swift/Rust/C#, the most serious instance found." Reusing this mechanism's *logic* for socket 2's
  floor — rather than a new, portable indexer — inherits that open violation; it does not resolve
  it. Non-Python and symbol-less files are already reported `changes_unjudged`, never silently
  passed (`test-reference-verify:239-246`), and any generalized floor must preserve that behavior
  rather than widen the violation's blast radius (no pun intended) by treating a wider search scope
  as if it were now portable.
- **The design doc's own open question already anticipates this tension.** "The retirement path for
  `test-reference-verify` once socket 1 exists… leaving it in place alongside a working socket
  would be two homes for one fact" (`change-evidence-design.md:308-310`). Socket 2 reusing the same
  mechanism as its floor is a second consumer of the violating site, which sharpens rather than
  defers that open question — it does not create a second, independent retirement plan.
- **`test-reference-verify`'s output shape is a five-field JSON record**, not a dependent-set
  report: `verifier`, `coverage_level` (always `"referenced"`), `tests_executed`,
  `changes_referenced`, `changes_unjudged` (`test-reference-verify:271-277`), printed to stdout or
  merged into `.test-evidence.json`. It answers "was this symbol referenced by any test," which is
  a different question from socket 2's "who are this symbol's dependents, and does the diff touch
  them" (`change-evidence-design.md:134-135`) — the floor reuses the *reference-finding* logic, not
  the artifact shape.
- **No activation trigger is named for socket 2, unlike socket 4.** The design doc's per-socket
  section for socket 2 states only "Posture: report-only, always" (`change-evidence-design.md:
  136-137`) with no gating structural characteristic, in contrast to socket 4's explicit reliance on
  `exposes_programmatic_interface`. Confirming by contrast: socket 1's `verify_coverage` is invoked
  unconditionally by the Critic every chunk/verify-resolutions review (`plugin/skills/critic/
  goals-1-3.md:19`), with `coverage_required` (`plugin/templates/project-state.yaml:338`, read via
  `read_bool_yaml_key`, `gates.py:1253`) deciding only enforce-vs-skip *inside* the function, not
  whether it runs. `coverage_probes.py`'s `TRIGGERED_ARTIFACTS` (`coverage_probes.py:103-113`)
  governs only strategy-*artifact* generation (e.g. `api-contract.md`), not gate/check activation —
  there is no structural-characteristic gate for coverage or reference checks anywhere in that
  module. This is consistent with socket 2 applying to every product, always, with no presence flag
  to check.
- **The nearest declaration precedent, `test_command`/`test_commands`, is unchanged.**
  `plugin/templates/project-state.yaml:359-388` remains the "declare it — don't wrap it" contract
  already cited by #620's requirements pass. `coverage_required: false` now sits at
  `project-state.yaml:338` (COVERAGE EVIDENCE section header at line 326), with commentary at
  `:332-334` explicitly naming `bin/test-reference-verify` as "the reference verifier" emitting
  "the floor" — directly the mechanism socket 2's floor reuses. A repo-wide search of the template
  for `index`/`SCIP`/`reference` finds no existing per-language index or reference-lookup
  declaration key (only an unrelated `relationship: reference` enum at line 56 and the coverage-
  evidence commentary at 329-334) — socket 2's declaration surface is greenfield.
- **The evidence store cannot accept a socket-2 fact today, same open state as socket 4.**
  `plugin/lib/evidence.py:78`: `KNOWN_KINDS = frozenset({"review", "resolution", "disposition",
  "guard-refusal"})`; `append_fact` rejects any other kind outright (`evidence.py:131-136`).
  `test-run`/`pr-review`/`promotion` remain reserved-but-unimplemented (module docstring, `evidence.
  py:19-20`), and `.prawduct/artifacts/data-model.md:26-27,57` still calls extending the store to
  subsume that evidence "design direction, not yet a ratified norm." No socket-2/"blast-radius"/
  "reference" kind exists, reserved or otherwise.
- **Two live seams exist for composing socket 2's verdict into the Critic's review payload.** (1)
  The manifest `.prawduct/.critic-partials/manifest.json`, the code-written scope object
  (`files_changed`, `files_reviewed`, review interval; built by `cmd_critic_begin`, `plugin/bin/
  prawduct-hook:1134-1268`; read by the reviewer per `plugin/skills/critic/goals-1-3.md:14-15`) is a
  natural place to attach a dependent-set summary as an additional field, computed once at
  critic-begin time. (2) A live `prawduct-hook` subcommand run during review is the existing,
  simpler precedent: `goals-1-3.md:19` — "Run `prawduct-hook test-status` and `prawduct-hook
  verify-coverage` (Goal 1). Nothing else executes" — with Goal 1's "Symbol coverage" bullet
  instructing the reviewer to run `verify-coverage` and quote its stderr verbatim (`goals-1-3.md:
  61`); a socket-2 command could plug in the same way. `goals-1-3.md` is explicitly self-contained
  and forbids opening `review-cycle.md`/`review-protocol.md` (`goals-1-3.md:3-4`), and `chunk`/
  `verify-resolutions` reviews read only `goals-1-3.md` (`review-cycle.md:38`) — so whichever seam
  is chosen, the protocol file that documents it must be `goals-1-3.md` itself (or duplicated into
  it) for chunk-level reviews to see it at all.
- **No implementation of socket 2 exists anywhere.** Word-boundary searches for `\bSCIP\b`,
  `reference index`, and `[Ss]ocket 2\b` match only `change-evidence-design.md` and #620's own
  requirements/design docs (which reference the design doc's socket enumeration, not an
  implementation). `blast radius` matches 40 files but all are the unrelated generic idiom (e.g.
  `tests/test_lifecycle_repair.py:92`, describing retired-key scope). This is genuinely greenfield
  work, consistent with the design doc's own "Status: target design, not current reality" header.

## Decisions

Scoped to socket 2 alone — none of these reopen the shared four-socket contract, which stays owned
by `change-evidence-design.md`.

**1. Socket 2 has no activation gate — it applies to every product, unconditionally, always
report-only.** The design doc states this directly ("Posture: report-only, always") and names no
trigger, unlike socket 4's `exposes_programmatic_interface`. No new structural-characteristic flag
is introduced for this socket.

**2. The floor fallback generalizes `test-reference-verify`'s existing regex/substring mechanism to
a whole-repo search scope, unchanged in kind — and this is explicitly a stopgap, not a fix.**
Widening the search root from `tests_dirs` to all callers reuses the same `_PY_SYMBOL_RE`/
substring-match logic the Retroactivity list already names as a confirmed Python-specificity
violation. The floor must continue to report `changes_unjudged` for non-Python and symbol-less
files exactly as it does today — a wider search scope does not make the mechanism more portable,
and the requirements below must not claim it does. Retiring or replacing this mechanism is the
design doc's own open question (lines 308-310) and is not re-litigated per-socket here.

**3. A declared producer is an opaque invocation or result-artifact path — prawduct validates no
per-ecosystem indexer name and maintains no enum of "supported" SCIP tools.** This mirrors
`test_command`'s "declare it — don't wrap it" contract exactly, the same precedent #620's
requirements used for socket 4's producer declaration.

**4. The minimal verdict primitive is fixed by the design doc, not deferred: for each changed
symbol, its dependent set, with dependents the diff also touches distinguished
(`change-evidence-design.md:134-135`).** Unlike socket 4 (whose primitive was explicitly left to
design), socket 2's shape is already stated plainly enough to require directly. The exact
serialization (field names, whether SCIP occurrence ranges or bare symbol names) is left open.

**5. The Critic-integration seam is left open between the two live candidates found in Grounding
facts — a manifest.json field computed at critic-begin, or a live `prawduct-hook` subcommand
invoked during review the way `verify-coverage` already is.** Whichever is chosen, it must be
documented in `goals-1-3.md` itself (not only `review-protocol.md`) for chunk-level and
verify-resolutions reviews — the majority of Critic invocations — to see it, per that file's
self-containment constraint. Design must pick one and state why.

**6. Where the verdict is persisted, if anywhere, is deferred, identically to socket 4's Decision
5.** If it lands in the shared evidence store, a new `kind` is added deliberately to `evidence.py`'s
`KNOWN_KINDS` rather than assumed; a dedicated per-product file is equally viable. This item states
the constraint (additive-only fields; loud, never silent, handling of a schema-ahead record) without
picking the store.

## Requirements

MUST unless marked SHOULD.

- **CE2-1** Socket 2 activates for every product unconditionally — no structural-characteristic
  flag gates it, and it is always report-only, with no blocking key of its own (Decision 1;
  contrast socket 4's opt-in blocking boolean).
- **CE2-2** A product may declare a primary producer as an opaque SCIP-index-query invocation or
  result-artifact path; prawduct validates no ecosystem-specific tool name and ships no per-language
  enum or allowlist of "supported" indexers (Decision 3).
- **CE2-3** When no producer is declared, socket 2 falls back to a floor built by widening
  `test-reference-verify`'s existing regex/substring reference-matching mechanism from the tests
  tree to all repo callers (Decision 2). This floor MUST continue to report non-Python and
  symbol-less files as `changes_unjudged`, never silently passed, exactly as the mechanism already
  does — widening its search scope does not change its portability.
- **CE2-4** The verdict is, for each changed symbol, its dependent set with diff-touched dependents
  distinguished, matching the design doc's stated shape verbatim (Decision 4). Its exact
  serialization is out of this document's scope (design-stage).
- **CE2-5** A product with no declared producer and an inapplicable floor (e.g. a language the floor
  cannot parse) reports a distinct *unchecked* state for that symbol — never coalesced with an
  empty dependent set, which would misread as "no dependents" rather than "not evaluated" —
  mirroring `test-reference-verify`'s existing `changes_unjudged` handling and the same
  unchecked-never-passed precedent #620's requirements established for socket 4.
- **CE2-6** The verdict composes into the Critic's review payload through one of the two candidate
  seams named in Decision 5, documented in `goals-1-3.md` so chunk-level and verify-resolutions
  reviews see it — the choice and its rationale are a design-stage deliverable, not resolved here.
- **CE2-7** Whatever storage this socket's verdict lands in, if any, respects additive-only field
  evolution and loud (never silent) handling of a schema-ahead or malformed record, consistent with
  `data-model.md`'s existing forward-incompatibility rules; if it lands in the shared evidence
  store, a new `kind` is added deliberately to `evidence.py`'s `KNOWN_KINDS` rather than assumed
  (Decision 6).
- **CE2-8** Once built, a reviewer facing a changed symbol sees its dependent count and which
  dependents the diff also touches, without manually grepping callers — the demonstrable case the
  design doc's yield argument rests on (`change-evidence-design.md:41-55`), with zero test-runtime
  cost and no test suite invoked.

## Acceptance

- [ ] For each changed symbol the dependent set is reported, marking which of them the diff also
      touches.
- [ ] Report-only, always — this socket has no blocking key.
- [ ] Zero test-runtime cost: no producer runs during the product's test suite.
- [ ] A missing or inapplicable producer reports *unchecked* for the affected symbols, never
      coalesced with an empty (zero-dependent) verdict.
- [ ] No per-language symbol table or SCIP indexer ships in prawduct as part of this item; the floor
      fallback reuses `test-reference-verify`'s existing mechanism, generalized in search scope
      only, and continues to report non-Python files as unchecked.

## Scope-out (this item)

- The shared four-socket contract, its rationale, blind spots, and adoption/rollout mechanics —
  `change-evidence-design.md`'s territory, per the issue's own scope-out.
- Sockets 1, 3 and 4 (#249, #619, #620) — sibling items with their own requirements passes.
- Whether all four sockets share one `project-state.yaml` declaration surface or four
  (`change-evidence-design.md` Open Question #1) — cross-socket, not decided for socket 2 in
  isolation; whichever socket's design lands first should settle it, or it is settled directly on
  the design doc, exactly as #620's requirements scoped this out for socket 4.
- The exact declaration key name, the verdict's serialization format, the Critic-integration seam
  choice (Decision 5), and the evidence-storage choice (Decision 6) — all explicitly deferred to the
  design pass.
- Retiring `test-reference-verify` or otherwise resolving its Python-specificity violation in
  general — tracked by the Python-specificity migration (LNG-5W8R) and the design doc's own
  retirement open question (lines 308-310); this item only widens that mechanism's existing search
  scope for socket 2's floor, it does not fix the violation.
- Whether socket 2's grep floor has a tolerable false-positive rate on common symbol names, or
  whether "no producer → unchecked" is the better default than a noisy floor — the design doc's own
  Open Question, explicitly carried forward, not resolved here.
- Selecting or wiring a specific SCIP indexer for any particular ecosystem — a product's own
  declaration, per the socket contract.

## Evidence / references

- `.prawduct/artifacts/change-evidence-design.md` — the shared four-socket design; §"Socket 2 —
  Blast radius (reference index)" (lines 127-142), the defect table (30-39), adoption sections
  (197-301), Open Questions (303-318).
- `plugin/bin/test-reference-verify:64-66,167-179,199-207,239-246,271-277,334` — the existing
  reference-finding mechanism (`_PY_SYMBOL_RE`, `_discover_tests`, `_has_reference`), its
  `changes_unjudged` handling, its output shape, and its default `tests_dirs` search root.
- `plugin/lib/gates.py:1236-1238,1253-1254,1272-1277` — `verify_coverage`'s call sites into
  `test-reference-verify` and its `coverage_required` gating.
- `plugin/bin/prawduct-hook:1134-1268,3085-3115` — `cmd_critic_begin` (the manifest a socket-2
  field could attach to) and the evidence-record path that shells out to `test-reference-verify`.
- `.prawduct/artifacts/architecture.md:66,74,78,79` — the Direction norms grounding "prawduct
  implements no differ, maintains no matrix," and the Retroactivity paragraph naming
  `test-reference-verify` as a confirmed-violating site feeding a BLOCKING gate.
- `plugin/templates/project-state.yaml:326,332-334,338,359-388` — the COVERAGE EVIDENCE section,
  `coverage_required`, and `test_command`/`test_commands`, the closest existing producer-declaration
  precedent.
- `plugin/lib/coverage_probes.py:103-113` — `TRIGGERED_ARTIFACTS`, confirming it governs artifact
  generation, not gate/check activation, supporting Decision 1 (no activation gate for socket 2).
- `plugin/lib/evidence.py:19-20,78,131-136` — the evidence store envelope, `KNOWN_KINDS`, and its
  fail-closed rejection of unregistered kinds.
- `.prawduct/artifacts/data-model.md:26-27,57` — the reserved-but-unratified `test-run`/`pr-review`/
  `promotion` kinds, the open question `change-evidence-design.md` inherits and this item does not
  resolve.
- `plugin/skills/critic/goals-1-3.md:3-4,14-15,19,61` — the self-contained chunk/verify-resolutions
  protocol, the manifest it reads, the "nothing else executes" constraint, and the existing
  `verify-coverage` live-invocation precedent.
- `plugin/skills/critic/review-cycle.md:38` — confirms `chunk`/`verify-resolutions` reviews read
  only `goals-1-3.md`, grounding the requirement that Decision 5's chosen seam be documented there.
- `documentation/issues/620-requirements.md` — the sibling socket-4 requirements pass this document
  follows in structure and mirrors for shared open questions (evidence storage, declaration-surface
  count).
