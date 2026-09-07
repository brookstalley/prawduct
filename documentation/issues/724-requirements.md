# Issue #724 — Critic: 27 Rounds / 4.5h on One Branch — Round-Cost Reduction: Requirements

`status: draft · stage: requirements · area: critic · added: 2026-09-07 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/724`

Related: the review-wall-clock P0 norm (`nonfunctional-requirements.md`); the evidence store's
`guard-refusal` kind (`plugin/lib/evidence.py`), which several requirements below extend rather
than replace; sibling round-cost/evidence items #334 (single-latest-fact view), #598 (stale
findings report retirement), #585 (verify-mode demotion count).

## Problem

One feature branch took 27 Critic rounds and ~4.5 review-wall-clock hours to reach a PR gate.
Per the issue's own `review-stats` output, `verify-resolutions` mode is 59% of all rounds and 40%
of all review time, and 64% of those rounds (≈51 of 80) returned zero findings. The issue names
two real defects the review caught that nothing else would have — this document does not question
that value. It grounds eight proposed cost-reducing changes (R1–R8) against the current codebase
to determine which are genuinely open gaps, which already exist in some form, and which reopen a
decision this repo already made and reverted for a stated reason.

## Grounding facts

Re-verified against the current tree (2026-09-07). Organized by the issue's own R-numbering so
each recommendation's disposition is traceable.

**Dispatch architecture, load-bearing for every item below.** The Critic is a `context: fork`
skill (`plugin/skills/critic/SKILL.md:1-9`) with a hard split between deterministic code and
model judgment. Dispatch is `prawduct-hook classify-diff-risk` then `prawduct-hook critic-begin
--mode <mode> …` (`SKILL.md:53`), whose Python body is `critic_consolidate.begin_review`
(`plugin/lib/critic_consolidate.py:1350-1360`). Mode resolution is `infer-critic-mode`
(`plugin/lib/critic_mode.py`), precedence explicit arg > plan field > inferred (`verify-resolutions
> cumulative > final > chunk`). Consolidation (`critic-consolidate`) is the sole writer of the
review fact, `.critic-findings.json`, and the ledger event — a reviewer authors neither. The
finding schema validated by `validate_partial` is fixed and small: `{name, goal, severity,
recommendation, files?}` (`critic_consolidate.py:1876-1941`); the persisted body is `{fid, goal,
severity, title, recommendation}` (`.prawduct/artifacts/data-model.md:113-115`). **No finding
field is machine-checkable today** — "Scope: instance | class" is prose inside `recommendation`,
not a validated key.

**A generic pre-dispatch refusal sink already exists and is reused twice.**
`evidence.append_guard_refusal` (`plugin/lib/evidence.py:266-329`), kind `guard-refusal` (one of
`KNOWN_KINDS`, `evidence.py:84`), is documented as "a guard that declines to spend something
before spending it… safe by construction," built specifically so a control's yield is
observable and falsifiable per the NFR P0 norm (`nonfunctional-requirements.md:22`). Two guards
already use it: `critic-dispatch-free-interval` (R1, below) and `base-advance-transfer` (R7,
below). This is the ready-made home for every *new* pre-dispatch guard R2, R3, and R6 want —
none of them need a new sink, only a new caller.

### R1 — AST-diff / "prose-only delta" skip before `verify-resolutions`

A structurally identical mechanism already exists and already runs at dispatch time, keyed on
*path* rather than AST content: `coverage_algebra.judgeable_files` (`plugin/lib/
coverage_algebra.py:63-99`) is called inside `begin_review` — `if not force and not
judgeable_files(files_changed) and not pending_actionable:` refuses with `kind: "no-review-
needed"`, exit 3, and a recorded `guard-refusal` under `critic-dispatch-free-interval`
(`critic_consolidate.py:1684-1710`). It was measured before shipping: "62 of 492 review facts
(12.6%, ~5.2 opus-hours) covered entirely non-judgeable intervals" (`critic_consolidate.py:1667`).
This is R1's proposed *mechanism* — skip dispatch, exit 3, record the free edge — already live.

**R1's specific instrument — AST-equivalence on `.py` files — was already built and explicitly
reverted.** `is_judgeable_path`'s docstring (`coverage_algebra.py:72-88`) states: *"Ruled
2026-07-29, after building the exception and reverting it: content equivalence cannot relax
this… 'the change is only a comment' is not a safe exception in THIS repo."* Two independent,
concrete reasons are on record: (1) `waivers.py`'s `prawduct:allow <scope>/<rule-id> -- reason`
source-comment pragma, enforced by `compliance.py:193-199`, means adding a waiver comment to an
existing `except Exception:` suppresses a compliance check while leaving the AST byte-identical —
exactly the class of change Goal 3 requires a reviewer to judge (`review-protocol.md:81`); (2)
"tests assert over `.py` prose" — a docstring edit can break a test, so AST equality does not even
guarantee test-suite equivalence. The same ruling was made independently a second time at a
different call site: `coverage.diagnose_base_advance_transfer`'s docstring states "any edit at
all to a branch file, comments included, denies [the transfer]" (`coverage.py:393-402`). The
module's stated remedy is different from R1's: *"the sound way to stop paying for behaviour-
neutral edits is to make review cheap, not skippable"* (`coverage_algebra.py:88`) — i.e. shrink
`verify-resolutions`'s payload (already underway via the goals-1-3 split, `SKILL.md:23-27`), not
exempt the dispatch.

### R2 — Machine-checkable `do_not` field on findings

Greenfield: no `do_not` key exists in `validate_partial`'s schema or the persisted body (both
cited above). The closest existing precedent for "cheap regex pass over changed files, no
reviewer dispatch" is `compliance_canary` (`plugin/lib/compliance.py:155-199`) — the Stop-hook's
session-end canary that regex-scans for broad-except, missing tests, and reason-less waivers,
explicitly "best-effort… every probe fails open." It establishes the *pattern* (cheap pre-dispatch
regex pass) but is a fixed, hardcoded four-check set, not a per-finding, reviewer-authored field.
Any new field is an additive change to the existing `review` kind's body — no `KNOWN_KINDS`
change needed — but must respect the store's ratified forward-compat rule: "a fact written by a
newer schema than the reader is surfaced as a loud block, never silently dropped"
(`data-model.md:80-82`), and every existing reader that walks `findings[]` (coverage_algebra,
dispositions.py, telemetry.py) must tolerate an old fact lacking the field.

### R3 — Preconditions run before dispatch, not as a mid-round finding

Mixed: some preconditions are already pre-dispatch; evidence freshness is not.

**Already pre-dispatch:** the in-flight guard refuses before deriving any interval when a
critic-active marker is live or a complete roster sits on disk (`critic_consolidate.py:1398-
1438`, `kind: "review-in-flight"`); working-tree dirtiness at cumulative dispatch is computed in
code and surfaced as a manifest `notes` entry, not discovered by a reviewer
(`critic_consolidate.py:1494-1498`), and `verify-resolutions` has similar intent-aware anchor
logic (`critic_consolidate.py:1512-1593`).

**Not pre-dispatch, as the issue describes:** evidence freshness is checked via `prawduct-hook
test-status` at **SKILL.md step 5** — *after* `critic-begin` has already succeeded and a reviewer
is already spending context: *"run `prawduct-hook test-status`… exit 1 = stale → WARNING in your
review"* (`SKILL.md:66`, `goals-1-3.md:62`). The underlying check (`gates.test_status`,
`plugin/lib/gates.py:1201-1218`) is a cheap timestamp/JSON comparison (evidence-store operations
profile at ~0.06s, `plugin/CHANGELOG.md:21`) — cheap enough to run pre-dispatch exactly like
`classify-diff-risk` already does, but wired to fire inside the round instead. Gate-state
re-checking before dispatch is advisory prose only (`review-cycle.md:282-290`, "never infer that
coverage is needed from gate output printed *before* your fix commits") — nothing in
`critic-begin` enforces it.

### R4 — Class-scoped findings must enumerate every instance

Partially shipped as reviewer prose plus a verify-mode directive, not as schema. A prior release
already added "Scope: instance | class" to the rendered finding (`plugin/CHANGELOG.md:41-59`,
`review-protocol.md:124,167`): *"An unbounded class closes only by a construction… never by a
longer list."* At verify time, `RESOLUTION_IS_A_CLAIM_DIRECTIVE` (`critic_consolidate.py:448-
466`) already instructs the reviewer to *"re-run the finding's own reason as a search before you
write `fixed`."* But none of this is machine-checkable: `Scope:` is free text inside
`recommendation`, absent from both schemas cited under R1/R2's dispatch section, and nothing
re-runs a "declared search" automatically — the re-run is delegated to the reviewer's judgment,
not stored and replayed. The framework's own authors already named this exact gap as deferred
work: *"if a review… produces a site-naming finding that does not answer instance-or-class, the
answer becomes machine-checkable"* (`plugin/CHANGELOG.md:57`). A known constraint: *"chunk-mode
reviews do not carry the rule yet — their instruction payload is at its size ceiling"*
(`plugin/CHANGELOG.md:59`), and `chunk` already "missed its 1-2 min target in 30 of 30 recorded
runs" (`SKILL.md:51`).

### R5 — Prose/NOTE findings default to accept, not an imperative fix

Terminology correction: **there is no `Remedy:` field on a finding anywhere in the schema.** The
field is `Recommendation:` in the rendered template and `recommendation` in the JSON key
(`review-protocol.md:166-169`; `critic_consolidate.py:1925`; `data-model.md:114`). "Remedy" in
this codebase names *gate-level* remedies (`gates.blocking_remedy_lines`, `gates.transfer_remedy`)
and disposition/guard remedies — never an individual finding's structural field. The behavior R5
wants is already ratified protocol, independent of any field rename: ACCEPT is stated twice as
"the default disposition for anything that gates nothing and that no one will realistically
action" (`review-cycle.md:136-141`; `goals-1-3.md:12`, "fixing one re-opens the gate and costs a
round"), and `review-protocol.md:125` already prescribes exactly three outcomes for stale prose
— delete, make relational, or pin with a test — while explicitly forbidding the two moves that
manufacture rounds: *"Never recommend rewording the narration or adding a comment that explains
the history; both ship the sentence the next round finds stale."* The recording mechanism already
exists and is structured: `prawduct-hook disposition <review-id> <fid> --accept "<reason>"`
appends a `disposition` fact and never weakens a gate (`dispositions.py:23-27,296-399`). What
genuinely doesn't exist is any structural constraint on the `recommendation` field itself — it is
unstructured prose (`critic_consolidate.py:1880`), so a reviewer remains free to phrase a NOTE as
an imperative fix instruction and nothing in the schema stops it.

### R6 — Structural round-cost justification before spend

The literal prose the issue quotes exists today: `coverage.count_branch_rounds`
(`coverage.py:568-643`) and `coverage.format_branch_rounds` (`coverage.py:646-706`) render *"name
what round {n+1} will do differently before you spend it — a merge or genuinely new work is a
good answer, 'one more fix commit' is not"* (`coverage.py:701-705`). **Critical gap: this message
only fires on the `uncovered` gate outcome, never on `blocked`.** In `gates.check_cumulative_
critic` (`gates.py:1354` on), the `blocked` branch — unresolved BLOCKING findings pending fix,
the ordinary fix→commit→verify-resolutions loop — prints findings and remedy lines and returns 1
immediately (`gates.py:1488-1505`), *before* reaching the round-tally code; `format_branch_
rounds` is only reached in the `uncovered` fallthrough after a base-advance-transfer attempt
(`gates.py:1507-1574`). **The round-cost challenge, as currently wired, cannot have fired during
the repeated-`verify-resolutions`-against-`blocked` loop the issue's 27-round branch almost
certainly ran.** A CLI precedent for a new flag exists: `--force` is parsed as a no-value boolean
ahead of the `flags` dict loop in `cmd_critic_begin` (`plugin/bin/prawduct-hook:1532-1556`),
alongside existing value-flags (`--chosen-by`, `--tier`, `--scope`) threaded the same way. No
existing mechanism validates or rejects a justification string by pattern — `format_branch_
rounds` names good/bad answers in prose but gates on nothing.

### R7 — Name the missing input when a cheap check can't run

The exact message quoted in the issue is `coverage.diagnose_base_advance_transfer`'s
(`coverage.py:369-566`) `_survivors` helper setting `degraded = "a candidate tree could not be
diffed"` (`coverage.py:517`) or `"a candidate span could not be diffed"` (`coverage.py:536`) on a
failed git diff. **The general principle R7 asks for — don't silently fall through to an
expensive full review — is already implemented for this exact check**: `gates.py:1579-1582`
prints the narrower, cheaper remedy (`transfer_remedy`, "a suite run, not a review") *before* any
generic uncovered remedy, "because the reader acts on the first one they meet, and this is the
cheapest of all of them" (`gates.py:1575-1578`). The real, narrow gap: `degraded` is computed
inside `diagnose_base_advance_transfer` but never returned — the function's documented return
shape only exposes `advance_files: None` as the caller-visible degraded signal
(`coverage.py:421-432`) — so today the operator sees a generic "unavailable" verdict, not which
specific input (candidate tree SHA, git object) was unreadable.

### R8 — Bounded in-session reviewer re-check instead of a fresh dispatch

This runs directly against a stated design principle and a documented harness constraint that
already broke a prior version of the same idea. Independence is stated twice verbatim: *"You have
NOT seen the builder's reasoning or decision-making. That independence is the point"*
(`SKILL.md:21`; `critic-reviewer.md:9-10`, same wording). Separately, the entire manifest/partial/
consolidate architecture exists *because* the harness does not support resuming a backgrounded
subagent: `critic_consolidate.py:19-24` documents that a Claude Code harness change made `Agent`
subagents background-by-default, so a coordinator that persisted findings after dispatch "silently
never did" — the fix was the decoupled, file-based consolidation pipeline this system now runs.
`SKILL.md:70` states the resulting rule: *"Once the reviewers are dispatched you are done; there
is no resume-to-aggregate."* `verify-resolutions` is this framework's actual, already-shipped
answer to the same cost problem R8 names: cheap fresh dispatch anchored to the *prior review
fact* via `fact_id` (not conversation memory, `review-cycle.md:100-104`), narrowed to goals 1-3
only, rating only BLOCKING to avoid manufacturing new work
(`VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE`, `critic_consolidate.py:525-`).

### Cross-cutting — `architecture.md`'s "prawduct never implements" norm

`architecture.md:79` — *"Prawduct guides and reviews; it never implements… a bare-except check
belongs to ruff or clippy, not to a prawduct gate."* This bears on R1 (a general-purpose AST-
normalization engine reads as implementing a static-analysis tool — a second, independent reason
to be skeptical beyond the reverted COV-3M8Q ruling) and R2 (a **bespoke, per-finding** pattern in
the shape of `compliance_canary`'s four hardcoded checks is defensible under this norm; a
general-purpose regex/linter-replacement engine would not be). Every new guard this document
approves (R3, R6, R7) must record through `evidence.append_guard_refusal` so its yield is
observable and queryable (`evidence list --kind guard-refusal`), per the NFR P0 norm that "a
control that has fired repeatedly and never produced a blocking finding is removed by default…
adding a control names the yield it expects and emits it observably" (`nonfunctional-
requirements.md:22-27`) — otherwise none of them can ever be justified or retired on evidence.

## Decisions

**1. R1 is not adopted as specified.** AST-equivalence dispatch-skipping was built and reverted on
2026-07-29 for a documented, concrete exploit (the `prawduct:allow` waiver pragma leaves AST
byte-identical while suppressing a compliance check) and a documented collateral risk (docstring-
asserting tests). Re-litigating COV-3M8Q needs a narrower soundness argument than the one that
already failed — e.g. excluding any file whose diff touches a `prawduct:allow` pragma or whose
docstrings are asserted on by tests — which is materially more machinery than R1 as written, for a
saving the codebase's own authors already redirected toward payload-shrinking instead (Grounding
facts, `coverage_algebra.py:88`). This item does not reopen that ruling; it redirects R1's goal to
Requirement RND-1 below, which is the already-endorsed path.

**2. R2 ships as a bespoke, per-finding field, not a general pattern-matching engine.** This keeps
it inside `architecture.md:79`'s "never implements" boundary — closer in shape to `compliance_
canary`'s framework-specific checks than to a linter replacement — and treats it as an additive
extension of the existing `review` kind's body, subject to the store's forward-compat rule.

**3. R3 ships narrowly: move the existing `test-status` freshness check into `begin_review`,
reusing the `guard-refusal` sink two guards already use.** This is a same-shape change to an
already-precedented site (`judgeable_files`'s placement in `begin_review`), not new architecture.
Gate-state re-checking (the second half of R3) is scoped out of this item — see Scope-out — because
"the gate is satisfied" is not detectable without running the gate itself, which is a different
cost trade-off than a cheap freshness stat and needs its own design pass.

**4. R4 ships as a schema extension, gated on the chunk-mode payload constraint.** The instance/
class scope and its declared search become validated, optional fields on a finding (`scope:
"instance" | "class"`, `search: <string>`), additive per `data-model.md:80-82`. Chunk mode may omit
them given its documented size ceiling (`plugin/CHANGELOG.md:59`) — this item does not force chunk
mode to carry the field.

**5. R5 is retargeted from a field rename to a template constraint.** Since no `Remedy:` field
exists to rename, the fix is to constrain the *shape* of `recommendation` for NOTE-severity
findings — a conditional-accept phrasing convention enforced at consolidation time (not a new
schema key) — rather than to introduce `accept_unless:` as a section header.

**6. R6 ships as (a) a validated `--because <string>` flag on `critic-begin`, threaded the same
way `--chosen-by`/`--tier`/`--scope` already are, recorded via the `guard-refusal`-adjacent sink
for observability, and (b) a fix to `gates.check_cumulative_critic` so the round-tally challenge
also fires on repeated `blocked` verdicts, not only on the `uncovered` fallthrough.** Without (b),
this item would ship a challenge that still cannot fire in the loop the issue's branch actually
ran.

**7. R7 ships narrowly: thread the already-computed `degraded` reason string through `diagnose_
base_advance_transfer`'s return value into `transfer_remedy`'s message.** The broader claim in R7
— "don't silently default to a full expensive review" — is already this function's behavior
(Grounding facts) and is not re-litigated here.

**8. R8 is not adopted.** It reverses two deliberate choices at once — reviewer independence
stated as a design point, and the decoupled-persistence architecture built specifically to survive
a harness limitation (fork-resume loss) that is outside prawduct's control. `verify-resolutions`
is this framework's already-shipped, cheaper-payload answer to the same cost problem. If revisited
later, that item must confront the independence trade-off and the fork-resume-loss defect class by
name, and justify why session continuity beats further payload-shrinking of `verify-resolutions`
— out of scope here.

## Requirements

MUST unless marked SHOULD.

- **RND-1** No AST-equivalence or content-normalization dispatch-skip is added for `verify-
  resolutions` or any mode; `judgeable_files`'s path-based free-interval guard remains the sole
  dispatch-skip mechanism (Decision 1). Cost reduction for prose-cascade deltas is pursued instead
  through payload-shrinking of `verify-resolutions`'s goal set and instructions, per `coverage_
  algebra.py:88`'s own stated remedy — tracked as follow-on design work, not required by this item.
- **RND-2** A new optional, validated `do_not` field is added to the finding schema
  (`validate_partial` and the persisted review-fact body): a list of `{pattern, reason}` entries a
  reviewer may attach to a finding, expressing a fix-diff regex the verify pass checks before
  dispatching a reviewer (Decision 2).
- **RND-3** Before a reviewer is dispatched for `verify-resolutions`, the verify pass greps the fix
  diff against every open finding's `do_not` patterns; a violation is rejected at guard cost — no
  reviewer spent — with the violated pattern and its `reason` quoted back (RND-2's consumer).
- **RND-4** `do_not` is per-finding and reviewer-authored, never a general-purpose static-analysis
  ruleset prawduct maintains or ships pre-populated (Decision 2; the "never implements" norm).
- **RND-5** `test-status` evidence-freshness checking moves from SKILL.md step 5 (inside an
  already-dispatched round) to inside `begin_review`, before a reviewer is spent. A stale-evidence
  refusal is recorded via the existing `guard-refusal` sink, mirroring `critic-dispatch-free-
  interval`'s placement and recording (Decision 3).
- **RND-6** A finding may declare `scope: "instance" | "class"` and, when `scope: "class"`, a
  `search:` string naming the query that enumerates every member. The field is optional and
  additive; an existing fact lacking it is read as `scope: unknown`, never coerced to `instance`
  (Decision 4).
- **RND-7** At `verify-resolutions`, when a prior finding's persisted `scope` is `"class"` and
  carries a `search:`, the verify pass re-runs that stored search (not merely the sites originally
  named) before accepting a resolution — mechanizing `RESOLUTION_IS_A_CLAIM_DIRECTIVE`'s existing
  prose instruction rather than leaving it to reviewer judgment alone (Decision 4).
- **RND-8 (SHOULD)** Chunk-mode findings may omit `scope`/`search` given the mode's documented
  payload ceiling; this item does not require extending chunk mode's instruction budget to carry
  them (Decision 4; `plugin/CHANGELOG.md:59`).
- **RND-9** For NOTE-severity findings, the consolidation step templates `recommendation` into a
  conditional-accept shape (e.g. leading with the condition under which the note is actioned)
  rather than an unqualified imperative instruction, reducing the pull toward an unnecessary fix
  commit that Grounding facts document as already-costed in practice (Decision 5).
- **RND-10** `critic-begin` accepts a `--because <string>` flag for `verify-resolutions` dispatches
  once branch round count exceeds the same threshold `count_branch_rounds`/`format_branch_rounds`
  already use; a value matching a closed set of rejected patterns (e.g. "one more fix commit", "a
  fix", empty string) is refused outright, and an accepted value is recorded via the guard-refusal-
  adjacent sink for later query (Decision 6).
- **RND-11** `gates.check_cumulative_critic`'s round-tally challenge (`format_branch_rounds`) is
  reachable from the `blocked` outcome on repeated rounds against the same open findings, not only
  from the `uncovered` fallthrough — closing the gap where the challenge could not fire in the
  exact fix→verify→fix→verify loop the issue's branch ran (Decision 6).
- **RND-12** `diagnose_base_advance_transfer`'s `degraded` reason string is threaded through the
  function's return value and surfaced in `transfer_remedy`'s message, naming the specific input
  (candidate tree/span) that could not be diffed, rather than only the generic "unavailable"
  verdict (Decision 7).
- **RND-13** No change is made to reviewer independence or to the manifest/partial/consolidate
  dispatch architecture; a fresh, independent dispatch remains the only path to a new review
  finding (Decision 8).
- **RND-14** Every new guard added by this item (RND-3, RND-5, RND-10) records its firing through
  `evidence.append_guard_refusal` or an equivalent observable sink, so its yield can be queried and
  the control can be justified or retired on evidence per the NFR P0 norm (Grounding facts,
  cross-cutting).

## Acceptance

- [ ] No AST-diff or content-equivalence dispatch-skip exists anywhere in the codebase; `judgeable_
      files` remains the only free-interval guard.
- [ ] A finding can carry `do_not` patterns; a fix diff violating one is rejected before any
      reviewer is dispatched, with the pattern and reason shown.
- [ ] `do_not` entries are authored per-finding by a reviewer; no bundled, prawduct-maintained
      pattern set ships.
- [ ] Evidence-staleness refusal happens inside `critic-begin`, before dispatch, and is recorded as
      a `guard-refusal` fact — `SKILL.md`'s step 5 `test-status` instruction is removed or reduced
      to a redundant sanity check.
- [ ] A finding can declare `scope` and, for `scope: "class"`, a `search`; old facts read as
      `scope: unknown` without error.
- [ ] At `verify-resolutions`, a class-scoped finding's stored `search` is re-run mechanically
      before its resolution is accepted.
- [ ] A NOTE-severity finding's rendered recommendation is conditional-accept shaped, not a bare
      imperative.
- [ ] `critic-begin --because <reason>` is required past the existing round-count threshold for
      `verify-resolutions`; a pattern-matched non-answer is refused without spending a round.
- [ ] The round-tally challenge fires on a `blocked` verdict with repeated rounds against the same
      findings, not only on the `uncovered` fallthrough.
- [ ] A failed base-advance-transfer diff names the specific input that could not be diffed.
- [ ] Reviewer independence and the fork-resume-loss-driven dispatch architecture are unchanged.
- [ ] Every new guard's firings are queryable via the evidence store.

## Scope-out (this item)

- Reopening COV-3M8Q (the 2026-07-29 AST/content-equivalence ruling) — Decision 1 redirects R1's
  goal to payload-shrinking instead, tracked as separate follow-on design work.
- A general-purpose, prawduct-maintained static-analysis or linting engine of any kind — `do_not`
  stays bespoke and reviewer-authored (Decision 2, the "never implements" norm).
- Gate-state re-checking before dispatch (the second half of the original R3 ask) — detecting "the
  gate would already be satisfied" without running the gate is a different cost trade-off from a
  cheap freshness stat and needs its own design pass (Decision 3).
- Session-continuity / in-session reviewer re-checks (R8) — reverses reviewer independence and
  the fork-resume-loss-driven architecture; not adopted (Decision 8).
- Any change to the manifest/partial/consolidate dispatch pipeline, `critic-reviewer.md`'s
  independence framing, or the goals-1-3 payload split itself.
- The exact rejected-pattern list for `--because` (RND-10) and the exact round-count threshold at
  which it activates — design-time decisions once the mechanism (Decision 6) is fixed.
- Extending chunk mode's instruction budget to carry `scope`/`search` (RND-8 explicitly allows
  chunk mode to omit them).

## Evidence / references

- `plugin/skills/critic/SKILL.md:1-9,21,51,53,66,70` — fork-skill framing, independence statement,
  chunk-mode payload-ceiling measurement, dispatch call order, the pre-dispatch `test-status` step
  this item moves, and the no-resume-to-aggregate rule.
- `plugin/lib/critic_consolidate.py:19-24,448-466,525,1350-1360,1398-1438,1494-1498,1512-1593,
  1667,1684-1710,1876-1941` — the fork-resume-loss defect class and the resulting architecture;
  `RESOLUTION_IS_A_CLAIM_DIRECTIVE`; `VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE`; `begin_review`'s
  in-flight guard, tree-dirtiness notes, verify-resolutions anchor logic, the free-interval guard's
  measured yield and its `guard-refusal` recording; the finding schema `validate_partial` enforces.
- `plugin/lib/coverage_algebra.py:63-99` — `judgeable_files`/`is_judgeable_path`, the free-interval
  predicate and its 2026-07-29 AST-equivalence ruling and reversal, cited verbatim in Grounding
  facts R1.
- `plugin/lib/coverage.py:369-566,568-643,646-706` — `diagnose_base_advance_transfer` (the
  `degraded` local this item surfaces), `count_branch_rounds`/`format_branch_rounds` (the existing
  round-cost challenge prose and its `uncovered`-only reachability).
- `plugin/lib/gates.py:1201-1218,1354-1582` — `test_status`; `check_cumulative_critic`'s `blocked`
  vs. `uncovered` branches and where `format_branch_rounds` is (and isn't) reached; the transfer-
  remedy-before-generic-remedy ordering.
- `plugin/lib/evidence.py:84,191-196,266-329` — `KNOWN_KINDS`, its fail-closed rejection of
  unregistered kinds, and `append_guard_refusal`, the sink every new guard in this item reuses.
- `plugin/lib/compliance.py:155-199,193-199` — `compliance_canary`'s bespoke, hardcoded regex
  checks, the precedent shape for `do_not` (Decision 2), and the `prawduct:allow` waiver pragma
  that motivated COV-3M8Q's reversal.
- `.prawduct/artifacts/data-model.md:80-82,113-115` — the review fact's persisted finding body
  shape and its additive-only, loud-not-silent forward-compatibility rule.
- `plugin/skills/pr/review-cycle.md:100-104,136-141,156-203,210-220,282-290` — `verify-resolutions`
  anchoring via `fact_id`; ACCEPT as the stated default disposition; the goals-1-3-only rating
  rule; the `disposition --accept` recording command; the advisory (non-enforced) gate re-check
  guidance.
- `plugin/skills/pr/review-protocol.md:81,124-125,166-169` — Goal 3's suppression-judging scope;
  the instance/class "Scope:" convention and its construction-only closure rule; the three-way
  stale-prose remedy rule this item's RND-9 mechanizes.
- `plugin/lib/dispositions.py:23-27,296-399` — the `disposition` fact recorder and its never-
  weakens-a-gate guarantee.
- `plugin/bin/prawduct-hook:1532-1556` — `cmd_critic_begin`'s existing `--force` boolean-flag and
  `--chosen-by`/`--tier`/`--scope` value-flag parsing, the precedent RND-10's `--because` reuses.
- `plugin/lib/telemetry.py:175-198,362-391,442-485` and `.prawduct/.governance-ledger.jsonl` (via
  `_read_events`) — `review-stats`'s aggregation, the source of the issue's cited 136-review/
  by-mode/actionable-rate figures; per-worktree scope noted for context.
- `.prawduct/artifacts/architecture.md:79` — "prawduct guides and reviews; it never implements,"
  the norm bounding RND-2/RND-4's bespoke-not-general design.
- `.prawduct/artifacts/nonfunctional-requirements.md:18-27` — the review-wall-clock P0 norm and
  the observable-yield/retire-on-evidence requirement every new guard (RND-14) must satisfy.
- `plugin/skills/critic-reviewer.md:9-10` — the independence statement mirrored from `SKILL.md`,
  cited against R8.
- `plugin/CHANGELOG.md:21,33,41-59,57` — the evidence-store operations latency profile; the
  base-advance-transfer guard's shipping note; the prior release that added the instance/class
  scope convention and its own named deferred-work item (machine-checkable scope), which RND-6/
  RND-7 build.
- Issue #724 — problem statement, telemetry, R1–R8 proposals, and the builder's own self-assessed
  contribution this document does not restate.
