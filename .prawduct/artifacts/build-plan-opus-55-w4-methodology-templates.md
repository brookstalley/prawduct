---
artifact: build-plan
version: 1
scope: opus-55-w4-methodology-templates
branch: feature/opus-55-w4-methodology-templates
partition: "01's template half (`plugin/templates/**`, plus `test_v5_templates.py` and `test_operator_verification.py`) goes to one isolated-worktree delegate, in parallel with the main agent's methodology half. The two halves touch disjoint prose files. Every other test either half breaks belongs to the integrator, and the delegate reports the edits it needs there instead of making them. The probes run in a second background agent that writes only to the scratchpad. W3 set the precedent."
depends_on:
  - artifact: opus-55-prompt-audit-2026-09
governed_by:
  - artifact: architecture
    dispositions:
      - "every fact has one home → conforms, and it is the point of B-10/B-11, B-14, B-24, B-34, B-36, B-38, B-39 and B-40: a second copy of a fact becomes a pointer to its home, or goes"
      - "goals and verification bind; prescribed method is advice → conforms, and it is #341's point: B-17, B-18 and B-19 restate chunk shape, file-list deliverables and phase choreography as advice, and keep acceptance criteria as the contract"
      - "the plugin writes nothing into a governed repo except… → conforms: templates change for new scaffolds only. Onboarded repos keep what they have, as the owner ruled for A-16"
      - "an independent reviewer never mutates the session it reviews → inapplicable, because no reviewer surface changes"
      - "authority fails closed; advice fails soft → inapplicable, because no gate verdict, exit code or advisory changes; only prose and its test pins move"
      - "prawduct guides and reviews, it never implements → inapplicable"
      - "local-first governance coordination → inapplicable"
      - "written in Python, never specific to Python → inapplicable"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall clock is P0 → conforms: one chunk, one boundary review"
      - "proportionality ratchets both ways → conforms: the wave deletes text and adds no control"
      - "review rigor is stage-keyed → inapplicable, because no severity rule changes"
      - "state-file growth is an advisory, never a block → inapplicable"
  - artifact: program-purpose-and-cession
    dispositions:
      - "prose-test taxonomy: a doc test pins budgets, refs, interface tokens and render consistency, never a sentence → conforms: a pin on a sentence this wave rewrites is retired, or re-anchored on structure or on the interface token it protects. Any absence guard kept is a recorded [DECISION], as W3's were"
      - "model plan (Fable coherence before the cycle lands) → conforms: owed once, before W6 lands"
---

# Build Plan: Opus 5.5 prompt audit — W4, methodology and templates

## Problem

The methodology guides and the artifact templates misfire on Opus 5.5 in five ways. The evidence
and the replacement text are in `opus-55-prompt-audit-2026-09/slice-B.md`, and the owner ruled on
2026-09-28 (the audit's § Rulings):

- **Early stops.** Three lines license ending the turn when there is work in hand: the "just go"
  shade of `YOUR TURN` (B-9), a chunk boundary read as the end of the turn (B-16), and a "hard
  stop" that means "run the review first" (B-35). W1's A-1 now contradicts them.
- **Self-verification.** The builder is told to scrub its own diff while the Critic runs (B-1),
  to review every artifact phase through five perspectives (B-19), to "verify artifacts are
  current" as its own step (B-36), and to redo a delegate's sweep (B-10 to B-12).
- **Delegation as the default.** Tangents are "offered first" to a delegate (B-13), a third
  copy of the default re-asks it of every backlog candidate (B-14), independence alone counts as
  the ordinary yes (B-15), and a subagent is mandated for a consumer grep (B-2).
- **Method written as binding (#341).** Chunk shape (B-17), file-list deliverables in the
  template (B-18) and phase choreography (B-19).
- **Fossils and register.** Issue ids, incident stories, dead component names and version
  fossils ship into every product's artifacts (B-3 to B-8, B-30 to B-33, B-38 to B-40). Bold and
  caps carry emphasis in most sentences (B-27, B-28, B-37). A duplicated constant drifts (B-34).
  Wave 3's weaker-model scaffolding carries its own contradiction (B-23, B-25, B-26).

## Success

- **Every decision carries its slice-B replacement, or a recorded departure.** The Decisions line
  below lists them. Each replacement is located by its `evidence:` string, not by line number,
  because W1 to W3b moved lines.
- **The handoff's carried W4 items are done:**
  - `building.md`'s "Disposition them ALL in ONE pass…" takes W2's de-shout, matching
    `gates.FIX_ORDER` ("run one … in one commit"). The slice's "leave it" rested on the runtime
    directive still shouting, and W2 changed that.
  - `delegation.md`'s brief checklist names the budgets the owned files sit under.
  - The template's "Commit & PR cadence" line points at `planning.md`'s short-plan tick rule.
- **B-21 and B-22 are decided by the probe** (P2 below). They are applied if the new text keeps
  every critical domain concern the old text surfaced. Otherwise they stay held, with the result
  recorded in the audit.
- **Ceilings are lowered in the same commit** for each trimmed guide in
  `test_v5_methodology.py`. `.claude/rules/learnings/authoring.md` stays under its
  `learnings_budgets` entry after B-20's list lands there.
- **The suite passes.**
  - Every sentence pin a rewrite breaks is retired or re-pointed, per the prose-test taxonomy.
  - Each `"<lit>" not in` assertion in `tests/` is checked against the edited files at
    `origin/develop`. A negative pin on a phrase this wave deletes goes vacuously green.
  - After each deletion, `plugin/` and `documentation/` are grepped for the deleted section's
    heading and lead phrases, and for any other surface stating the same rule (by the state, not
    the words). A sentence another wave owns is fixed now only if this wave made it false.
- **#341 and #779 are closed** (`/prawduct:backlog update <id> status=shipped`) when this wave
  merges. #779 is the scaffolded backlog legend's chunk-id `closed-by:`, fixed by B-5.
- **The probes have run, each confirming the model id it ran on** from `modelUsage` in
  `claude -p --output-format json`. The Agent tool's `sonnet` alias cannot reach Sonnet 5.5, and
  `claude -p --model claude-sonnet-5-5` can (checked 2026-09-28). Each probe has an old-text
  control, and a control that doesn't show the targeted failure is recorded as "no regression":
  - **P1, the owed W3 rerun on Sonnet 5.5.** W3's two reviewer probes (C-1 PR reviewer; C-22/C-23
    Critic reviewer), with W3's scenarios. Old text from `7cec305a`; new text from `develop` at
    `fa235fe0`, which is what ships.
  - **P2, the B-21/B-22 discovery probe on Sonnet 5.5.** One high-risk idea and one low-risk
    idea, old `discovery.md` against `discovery.md` with B-21 and B-22 applied. The critical
    concerns for each idea are listed before the runs. The failure targeted is a critical
    domain concern the old text raised and the new text missed, or a low-risk interview that
    balloons without the quotas.
  - **P3, the delegate floor probe on Sonnet 5.5.** A delegate gets a removal task under a brief
    written to the old and to the new `delegation.md` checklist (B-12). The failure targeted is a
    "Done" returned with no falsifying evidence.
  - **P4, the early-stop probe on the session model** (Opus 5.5; main-agent surface). A scratch
    repo carries a three-chunk short plan whose reviews are deferred to the boundary. The old and
    new `building.md` and `session-hygiene.md` ride the system prompt. The failure targeted is a
    turn that ends at a chunk boundary with the next chunk ready. This is the longer multi-step
    task W1's probe could not run. If its control also fails to stop early, per-wave probing is
    re-examined in the audit.

## Out of scope

- B-41, a flag. B-21 and B-22 if P2 does not release them.
- The session digest (`methodology/session-digest.md`, W1's) and every skill (W5). A skill
  sentence is fixed now only if this wave made it false.
- Any change to what a gate decides, to a severity rule, or to a parsed field's format.
- F6's rounds-per-PR comparison. Too few PRs have shipped since W3 to measure it.

## Requirements Confidence: High

Every decision has replacement text and a ruling. These are the inferences:

- [DECISION: one chunk, with the template half delegated inside it | methodology isn't a risk
  surface, so the plan would be short either way. One chunk gives one boundary review, and review
  run count is the P0 lever | owner can veto]
- [DECISION: P1's new text is `develop` at `fa235fe0`, not `deb4cf71` as the handoff says |
  `deb4cf71` predates W3's review fixes and W3b's split, so it is not what ships | owner can veto]
- [DECISION: B-21 and B-22 are applied in this wave if P2 shows no loss of critical domain
  coverage on Sonnet 5.5, without a second sitting | the F5 ruling holds them "until a Sonnet 5.5
  discovery probe, which W4's plan carries", which reads as the probe releasing them | owner can
  veto and hold them regardless]
- [DECISION: `delegation.md`'s brief checklist gains a budgets clause, which the audit does not
  enumerate | W3's delegate edited files under ceilings it was never told about, and the handoff
  carried the fix to this wave | owner can veto]
- [ASSUMPTION: `claude -p` with `--append-system-prompt-file` is a fair stand-in for a governed
  session reading the guide, for P4 | MED impact: a real session gets the digest and the hooks too,
  so P4 measures the guide text alone | owner can correct]

## Found while applying

- **Sonnet 5.5 is reachable, just not through the Agent tool.** `claude -p --model
  claude-sonnet-5-5 --output-format json` ran it, and `modelUsage` confirmed the id (2026-09-28).
  The owed floor probes run that way.
- **B-14 keeps the tangent route.** Its replacement dropped every mention of mid-cycle work from
  `building.md`'s delegation section. `TestAdHocDelegation` pins that concept: a builder mid-chunk
  must be pointed at the guide.
  [DECISION: the section names "a plan's chunks, or a tangent that arrives mid-cycle" as what the
  guide judges. It drops the old push ("asked again of … anything you were about to backlog") and
  keeps the route | the ruling applies replacement text unless it drops something a reader acts
  on | owner can veto]
- **B-17 states #341's acceptance criterion outright:** "a builder who finds a better route takes
  it and records why". The slice's "a forecast, not a contract" implied it without saying it, and
  F7 closes #341 on these rewrites.
- **Closing #341 moves a norm.** `architecture.md`'s "Goals and verification bind; prescribed
  method is advice" was `in-transition`, with #341 (GOV-4T9P) as its tracking ref and a stopgap
  expiring 2026-12-01.
  [DECISION: the migration completes on this branch, so the norm goes to steady-state in the same
  change. The Status and Stopgap lines go. The Retroactivity line records the three migrated
  sites and "no residual sites". The Enforcement row in `project-preferences.md` drops its
  `in-transition` tag. The statement, Why, Scope and Decision are untouched: this is the
  lifecycle step `norms.md` § Birth defines, not an amendment. The authority is the owner's F7
  ruling ("#341 closes with wave 4") | owner can veto]
- **B-27's bold cut stopped at 96 spans,** from 122 (planning.md: 80 from 96). The slice's "roughly
  60" was an estimate. The rule it states (keep run-in labels and defined terms, drop mid-sentence
  emphasis) is what was applied, and what remains is run-in labels, the Size and Type lists, and
  the major-decision properties.
- **The `building.md` FIX_ORDER de-shout broke two pins:**
  - `test_resolve_findings_dispositions_rather_than_mandating_fixes` now pins the rule's new
    sentence.
  - `test_suite_at_boundary` pinned B-27's bold `**once**`. It now pins the plain form, and keeps
    the old negative beside the new one.
- **The template delegate's recorded departures,** all vetoable. Its report was re-derived: the
  added text was read in the integrated diff, not taken from the summary.
  - [DECISION: B-3 also covers `dependency-manifest.yaml`, which carries the same dead `Tier:` and
    `Owner: Artifact Generator (C3)` lines the slice's site list missed]
  - [DECISION: B-4 also namespaces the bare `/pr create` and `/backlog …` forms in
    `project-state.yaml`'s comments]
  - [DECISION: B-18's new sentence merges into the existing existence-check sentence of the
    Build Chunks comment. Placed beside it, the comment said so twice]
  - [DECISION: B-30 says `superseded_by: <what replaced it, or why it stopped>`, because a
    descoped plan is also superseded. It also says "review before you tick it", because on a
    short plan the earlier boxes are ticked at commit]
  - [DECISION: B-38 also cuts the OSHA/S1000D and "AWS-prescribed" citations, which are the same
    evidence class. `docs/runbook-authoring.md` holds them]
  - [DECISION: the cadence line says the last chunk commits before its `cumulative`. The old
    "commit per chunk after its Critic review passes" was false for Chunk 03]
- **Found by the delegate:**
  - `documentation/backlog-system-requirements.md:169` said `closed-by: <chunk-id|tag>`, which
    disagreed with the skill before this wave. It is fixed here, because a pre-existing defect
    gets no exception.
  - `project-state.yaml`'s version fossils ("v1.4+") are B-4-class, but no decision lists them.
- **`plugin/docs/discipline.md` anchored two rows on sentences this wave rewrote:** row 4 on B-2
  and row 9 on B-24. The anchors now name the new sentences. The file is W6's, but this wave made
  the anchors false, so this wave corrected them.
- **The negative-pin scan came back clean.** Across 760 `"<lit>" not in` literals, the only ones
  this wave removed from its files were common words asserted against runtime strings, not these
  files.

## Status

- [x] Chunk 01: methodology and templates (B-1 to B-20, B-23 to B-40, the handoff's W4 items, P1 to P4)

## Chunk 01: methodology and templates

**Type:** cumulative-final
**Decisions:**
- **Methodology (main agent):** B-1, B-2, B-8, B-9, B-10, B-11, B-12, B-13, B-14, B-15, B-16,
  B-17, B-19, B-20, B-23, B-24, B-25, B-26, B-27, B-28, B-31, B-33, B-34, B-35, B-36, B-39, B-40,
  B-21 and B-22 (released by P2). Also the handoff's `building.md` FIX_ORDER de-shout and
  delegation budgets clause.
- **Templates (delegate):** B-3, B-4, B-5, B-6, B-7, B-18, B-29, B-30, B-32, B-37, B-38, and the
  handoff's cadence-line pointer.

**Files:**
- Methodology: `plugin/methodology/building.md`, `plugin/methodology/planning.md`,
  `plugin/methodology/discovery.md`, `plugin/methodology/reflection.md`,
  `plugin/methodology/delegation.md`, `plugin/methodology/session-hygiene.md`,
  `.claude/rules/learnings/authoring.md` (B-20's list).
- Templates: `plugin/templates/build-plan.md`, `plugin/templates/backlog.md`,
  `plugin/templates/change-log.md`, `plugin/templates/operator-verification.md`,
  `plugin/templates/runbook.md`, `plugin/templates/project-preferences.md`, and the eight
  artifact templates B-3 and B-29 list.

**Tests:** find them by running, not by reading notes. Grep `tests/` for each edited file's name
and each rewritten phrase, then run what the grep finds **without `-x`**. A pin can be built
from a constant, and a literal grep can't see it. So far the grep finds these:
- Delegate-owned: `test_v5_templates.py`, `test_operator_verification.py`.
- Integrator-owned: `test_v5_methodology.py`, `test_short_plan_deferral.py`,
  `test_critic_consolidate.py`, `test_cutover_prose_coherence.py`,
  `test_plugin_methodology_digest.py`, `test_path_reference_resolution.py`, and every other test
  the run turns red.

**Cumulative review (`rev-20260929T013200Z-3de15477`): 1 blocking, 3 warnings, 8 notes.** Every
fix was made in one pass.
- **R-1 (blocking):** `building.md` also has a hard ceiling (`TestBuildingMethodology`), and it
  wasn't lowered. It now is. No other W4 guide has one.
- **R-2/R-4:** the template `project-state.yaml` still carried B-22's quotas. It now points at
  `discovery.md` "Risk Calibration".
- **R-5:** the fix-order pin now asserts `gates.FIX_ORDER` verbatim, which is render consistency
  with the runtime directive, and was red-verified. The negative pin I added on a phrase that never
  existed is gone.
- **R-6:** the build-plan template's chunk-shape comment is advice now, as in `planning.md`.
- **R-7:** B-25's replacement had dropped the 3-4-file size. It's restored as small, and the risk
  sentence still lifts it to medium.
  [DECISION: departs from the ruled text, because the ruled text left a size with no answer,
  which decides whether a Critic review runs | owner can veto]
- **R-8:** `planning.md`'s partition paragraph points at the delegation test instead of
  restating it without B-15's size qualifier.
- **R-9:** the template's version fossils are cut. "v1.7 ships only legacy-backlog-format" was also
  false, because the backlog probes exist.
- **R-10:** B-24's "file the rest" contradicted `core.md`'s fix-the-class rule. Post-Fix now
  fixes the class through its one owner when it can be changed here.
  [DECISION: departs from the ruled text, because two rules the builder reads disagreed | owner
  can veto]
- **Accepted:** R-3 (record-lint relay, correct), R-11 and R-12. #341 and #779 close at merge.
  R-1's suggestion to derive every hard ceiling from its recorded reading is not taken here: it
  changes a mechanism across eight Critic-file tests W4 doesn't own.

**P1–P3 outcome (2026-09-28, Sonnet 5.5).** Each subject ran `claude -p --model
claude-sonnet-5-5 --setting-sources project --strict-mcp-config`. That drops the user-level
prawduct plugin, which was checked: with it, a subject quotes the digest; with these flags, it
quotes nothing. All 24 graded runs have `modelUsage` = `claude-sonnet-5-5`. There were two
samples per arm, and each probe's grading criteria were fixed before its runs.
- **P1, C-1 (PR reviewer).** Old text from `7cec305a`, new from `fa235fe0`. The bundle was
  a 47-file rename interleaved with a currency split, plus a 95-file variant added after the
  runs began.
  - **Change-log entry that narrates branch history:** 4 of 4 in both arms.
  - **Oversize:** old 0 of 4, new 1 of 4 (a partial NOTE). On a single-concern mechanical bundle,
    neither text makes Sonnet 5.5 treat size as a defect.
  - **An unplanted rollback defect** (a down-migration that drops the currency column): new 4 of
    4, old 0 of 4. Two old-arm runs also routed findings to the backlog, which C-1 removed.
  - **Result:** no regression, and a recall gain on the unplanted defect.
- **P1, C-22/C-23 (Critic reviewer).** The case was a trivial-sized extraction with a
  substring-only test.
  - **Both arms:** 2 of 2 rated it WARNING, with no other finding.
  - **Result:** no regression. W3's one new-text BLOCKING did not recur.
- **P2, B-21/B-22 (discovery).** Ten critical concerns were fixed beforehand for a pediatric
  SMS-reminder app.
  - **High risk:** the old arm raised 9 and 10 of them, and the new arm 10 and 10.
  - **Low risk** (a household chore rotation): first-round questions were old 5 and 6, new 6 and
    4. Neither arm ballooned.
  - **Result: released, and applied in this wave.** Both arms ran without tools, so B-22's
    search-depth line was not exercised. The probed text lacked B-39's discovery edit, which does
    not touch domain concerns.
- **P3, B-10 to B-12 (delegate).** A removal of `legacy_parse` with one caller hidden behind a
  `getattr` and a config default.
  - **Old brief:** 2 of 2 reported Done with no evidence, and each left the hidden caller broken
    (1 failed / 8 passed).
  - **New brief:** 2 of 2 returned the grep output, found the caller, and left the suite at 9
    passed.
  - **Re-derived:** the main agent reran the four repos' suites.
  - **Result: helps.** This is the first probe across W1–W4 where the control shows the targeted
    failure and the treatment fixes it.
- **Setup gaps:** the first P3 batch was void (two delegates wrote to one repo) and was rerun.
  The Critic arms' prompt sizes differ (old about 16.4k words, new about 9.6k), because W3b split
  the file.

**P4 outcome (2026-09-28, early stop, Opus 5.5):**
- **Setup.** A scratch repo carried a three-chunk short plan (a temperature-conversion CLI) and
  the task "Let's build the plan". The arms:
  - A: the pre-W1 digest and the pre-W4 guides, the full control.
  - B: the current digest and the pre-W4 guides.
  - C: the current digest and the W4 guides.
- **All six isolated runs built all three chunks in one turn** (two per arm; `modelUsage`:
  `claude-opus-5-5`). Each committed per chunk, ticked every box, and closed on
  `YOUR TURN` / `SAFE TO CLEAR`, asking for a real decision (a PR, or the assumptions it had
  made), not "shall I continue?".
- **The control never stopped early, so the result is "no regression".** It is not evidence that
  A-1, B-9, B-16 or B-35 help.
- **A first batch was confounded and discarded.** The user's globally installed prawduct plugin
  loaded into every `claude -p` subject: its SessionStart hook injected the current digest and
  wrote `.prawduct/` markers, so arm A was not isolated. The rerun disabled the plugin with
  `--settings '{"enabledPlugins":{"prawduct@prawduct":false}}'`. That batch also finished 6 of 6.
- **This is the fourth wave whose control failed to show the targeted failure** (W1, W2, W3,
  W4), and W4's was the longer multi-step task the handoff asked for. The audit's
  "one behavioural probe per wave" is re-examined in its § Rulings: the probes can show a
  regression, and they have not shown a benefit.

**Done when:**
1. Each Success bullet holds, and the suite passes.
2. P1 to P4 have run. Results are recorded in this plan and in the audit's § Rulings (P1, P2).
3. Committed, then one `/prawduct:critic cumulative` over the branch, with blocking findings
   resolved.
4. Chunk marked `[x]`.
