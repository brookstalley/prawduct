# Assessment — why one small change costs an hour, and what to change

**Date:** 2026-09-17 · **Status:** discovery, not yet planned · **Author:** Fable session, from four
read-only sweeps (gates in `plugin/lib` + `plugin/bin`, every agent-facing prose surface, the open
backlog, and eight governed product repos' ledgers and reflections) plus this repo's own ledger.
Every number is derived from a store; the command that re-derives it is named beside it.

**Owner's framing this answers:** downstream users report that one small change turns into an hour
of tests, multiple Critics and suites. Quality must hold, but the owner explicitly authorizes trading
*a minor drop in quality* for *a large wall-clock saving*. That authorization is the new fact — the
three prior efficiency plans (`archive/build-plan-review-proportionality.md` v2.1.0,
`build-plan-tactical-efficiency.md` 2026-08, `build-plan-review-loop-termination.md` 2026-09) were
each constrained to "nothing that ships removes a control" and attacked the round-count at the
composition layer. The complaint survived them because the settings that generate it are
*philosophy stated as defaults in prose*, not mechanics.

## 1. Where the hour actually goes

The hour is real and measured, but it is mostly **review**, not tests.

**Product ledgers** (`prawduct-hook review-stats` run in each repo, 2026-09-17):

| repo | reviews | review wall-clock | median cumulative | verify-resolutions share of rounds | VR actionable |
|---|---|---|---|---|---|
| discodon | 1,294 | 163.7 h | 780 s | 60% | 41% |
| samsung-frame-art-loader | 289 | 40.5 h | 900 s | 69% | 50% |
| hallucinote | 289 | 34.6 h | 660 s | 54% | 31% |
| bankmachine | 248 | 28.3 h | 640 s | 63% | 26% |
| puzzles | 115 | 13.4 h | 810 s | 46% | 14% |
| swordfishing (Swift) | 86 | 13.3 h | 900 s | 58% | 28% |
| scriob | 93 | 8.8 h | 420 s | 42% | 38% |
| cordyceps (C#) | 65 | 5.8 h | 450 s | 33% | 18% |

Eight repos: 2,479 reviews, ~308 hours of reviewer wall-clock. Measured suite runtimes in the same
repos are 2–9 minutes (hallucinote ~2 min, bankmachine 6.6 min, discodon ~2 min declared / ~9 min
sequential pre-commit gate). **One cumulative round costs more than the whole suite in every repo.**

**A small change, priced from discodon's medians:** chunk review 300 s + cumulative 780 s +
1.5 verify rounds × 300 s ≈ 25 min of review, plus one or two suite runs, plus the agent's fix time
between rounds. That is the hour, and 60–70% of it is review.

**This repo's own ledger** (`.prawduct/.governance-ledger.jsonl`, 982 reviews, 110 h): 159 scopes,
median 4 reviews per scope, median 21 review-minutes per scope. **Scopes whose first review touched
five or fewer files: median 5 reviews, 20 minutes** — small scopes buy as many rounds as large ones.
261 of 501 verify-resolutions rounds returned zero findings (1,151 minutes). 43 scopes ran three or
more consecutive verify rounds.

**The mechanical fixes have not moved the verify treadmill.** Reviews since the v3.5.0 cut
(2026-09-13, ledgers read 2026-09-17; siblings on 3.5.0 / 3.5.1-dev):

| repo | reviews | minutes | verify-resolutions | of which zero-finding |
|---|---|---|---|---|
| discodon | 86 | 787 | 59 | 42 |
| bankmachine | 78 | 489 | 40 | 34 |
| puzzles | 70 | 550 | 36 | 31 |
| swordfishing | 7 | 62 | 3 | 3 |

138 verify rounds in four days, 110 of them (80%) returning nothing — a higher zero-yield share than
the all-time 52%. Re-derive: read each repo's `.prawduct/.governance-ledger.jsonl`, filter
`event` starting `review` and `ts >= 2026-09-13`, split on `review.mode`.

**Suite-side waste is redundant runs, not long runs.** Three documented instances of running the
same green twice (discodon TEV-9K2M — `test-evidence record` refuses an external run when
`test_command` is declared; "two five-minute runs at a PR boundary, for the same green";
"the whole suite ran instead of the one-test proof"). Twelve of 28 governed repos declare no
`test_command` at all, so they cannot even use the evidence gate.

## 2. Answers to the three questions

**Q1 — Do our testing instructions cause the over-rigor?** Partly, and less than the review
instructions do. The test prose is already mostly language-neutral. Three things do push rigor up:

- `building.md` "Establish a clean baseline: run the full suite" — every session, before any work.
  The framework's only concept of a targeted run is the *delegate* verification ceiling; the main
  agent's inner loop has no ceiling vocabulary at all, so `test_command:` (one maximal invocation)
  is the only thing it can name. `delegation-and-verification-cost-discovery.md` measured this:
  894 suite invocations, 362 unscoped whole-suite — "verification, not editing, is the wall-clock".
- The Critic's severity table applies **product floors per change**: "changed behavior has test
  coverage → BLOCKING if untested", "error paths tested → WARNING", "real dependencies not mocks →
  WARNING", and `templates/test-specifications.md`'s floor ("at least one E2E test per core flow")
  is read by a reviewer as a bar for the chunk in front of it.
- The discipline directives printed at `test-evidence record` ("a mutation you did not watch go red
  applied nothing", "green is evidence only about what could have made it red") ship to every
  product at every record — they are this repo's hardest-won rules, delivered as if universal.

**Q2 — Do we tell the Critic and test infra what stage we are at?** No. Nothing in `plugin/` —
no gate, predicate, config key, or prose sentence — distinguishes inner-loop work from release-boundary
work (grep for `stage`, `pre-release`, `unit-level`, `inner loop` in methodology and critic skills
returns nothing). Specifically:

- The reviewer subagent (`agents/critic-reviewer.md`) is told **nothing** about size, stage, or
  severity semantics; size arrives as a freeform `Signals: [summary]` bracket; the computed risk
  `tier` is documented as inert.
- `goals-1-3.md`, the file the chunk and verify-resolutions reviewer reads, has 22 BLOCKING rules,
  25 WARNING rules and **no proportionality clause**. The one size calibration in the Critic
  ("Trivial (1-2 files) → quick coherence check") lives in `review-protocol.md`, which that reviewer is
  forbidden to open. Every restraint sentence ("once a pass returns zero BLOCKING the review is over",
  the round budget, "yield does not decay") lives in `review-cycle.md`, loaded **only by the heavy
  modes**.
- Severity is a static table keyed on defect class. "Untested behavior → BLOCKING" fires identically
  on a config helper mid-chunk and a payment ledger at PR.

**Q3 — Is it philosophy?** Yes, and it is written down. The framework's stated failure direction is
*up*: "Every layer fails safe to thoroughness"; "under-declaring Type is safe (worst case: redundant
Critic work)"; "the depth varies; the habits don't"; "a repo that declares none is never reviewed
*less* than before". Under the ratified norm (`nonfunctional-requirements.md`: review wall-clock is
P0; proportionality ratchets both ways), *redundant review is not the safe direction — it is a cost*.
The defaults still encode the old belief:

| default | what it does to a product | file |
|---|---|---|
| No `risk_surfaces:` declared → coordinator at **5+ files** | every 5-file change in every product pays three reviewers × 4–10 min | `critic_consolidate.py:_derive_roster` |
| No plan / unsure → `final` | a planless two-line fix infers the full seven-goal review | `critic_mode.infer_mode` rule 4 |
| Missing `Type:` → `code`; missing mode → `final` | the fully-armed protocol is the silent option | `planning.md` |
| Digest + scaffolded `CLAUDE.md` anchor | zero proportionality sentences; "Run the Critic after medium+ work" with medium undefined there | `session-digest.md`, `migrate_plugin.STATIC_ANCHOR` |

Product owners have already routed around this by hand: hallucinote's standing policy "minimize
Critic except at major milestones — explicitly do NOT want a Critic run per test/fix"; six repos
wrote "never the full suite" delegate ceilings; discodon: "Doc-only PRs still get the full rigor …
caught zero drift"; bankmachine: a five-round arc ending `4, 3, 1, 0, 0`.

## 3. Recommendation — three philosophy shifts, all language-agnostic

The mechanism track is well covered by open items (#167 refuse-when-zero-blocking, #653 per-tree
evidence, #680/TEV-9K2M external ingest, #776 budget dead on trunk, #292 defer chunk reviews on
short plans, #164/#561 Swift/C# blind spots). What is missing is the **policy that authorizes them
to trade**, stated once and read by every reviewer.

**Shift A — Name two stages and key severity on them.** *Inner loop* = chunk and verify-resolutions
reviews, before the PR. *Boundary* = cumulative + PR review at entry to `develop` (where the owner
already ruled the testing burden sits, #747). In the inner loop, BLOCKING means "ships broken or
weakens a test"; coverage completeness, error-path tests, real-dependency tests, E2E floors, design,
prose, and records are **observations** carried to the boundary, where they become findings against
the whole bundle. The framework already knows the stage (mode + interval); it only has to say it in
the manifest and in `goals-1-3.md`, and give the reviewer subagent a stage + size line instead of a
freeform bracket. Quality cost: a coverage gap found at the boundary instead of mid-chunk — same
catch, later. Wall-clock: removes most mid-chunk fix→verify cycles.

**Shift B — Flip the failure direction of the defaults.** Retire "fails safe to thoroughness" and
"under-declaring is safe" as sentences; replace with: *both directions are errors; the inner loop
defaults cheap, the boundary defaults deep.* Concretely: unsure/planless → `chunk`, not `final`; a
product with no `risk_surfaces:` gets a single reviewer until it declares (onboarding and doctor ask
once, the way #719 asks for the toolchain); the digest and the scaffolded anchor each carry one
proportionality sentence. Quality cost: a product that never declares risk surfaces loses the
coordinator on 5–11-file changes; the boundary cumulative still runs. Wall-clock: 3× reviewer cost
removed from the most common product change size.

**Shift C — Give the inner loop a verification ceiling, not just delegates.** Extend the delegate
rule to the main agent: *while building, run the narrowest thing that proves the change; the declared
suite runs at Verify and at the boundary.* Declared in the product's own words in
`project-preferences.md` (the pattern six repos already invented), so it works for `swift test`,
`dotnet test`, `node --test` and `pytest` alike. Pair it with fixing the redundant-run defects and with
asking the 12 undeclared repos for a `test_command`. Move the mutation/red-verify directives from
"printed at every record" to the boundary. Quality cost: none at the boundary; inner-loop greens are
narrower and say so. Wall-clock: the redundant and unscoped suite runs, which the cost-discovery
measured as the dominant non-review term.

**Then measure and retire.** The two-way ratchet's removal arm runs on judgment until 2026-12-01
(#732 stopgap). Use `review-stats` per-mode actionable rate before/after as the evidence the norm
asks for, and retire the inner-loop checks whose yield stays near zero.

**Expected effect:** on the discodon medians a small change drops from ~25 min of review to one
chunk review plus the boundary cumulative it already owes — roughly half — and the suite-side
redundancy goes to zero. The ledger will state the real number.

## 4. Rulings not to re-derive (found in the backlog sweep)

- AST/content-equivalence gating is **unsound here** (#367, built, reviewed with 10 blocking, reverted).
- The trivial fast-path (fileset as detector) was built and retired; a skip-gate needs the *most*
  adversarial coverage (#292, #291).
- The `cumulative` incremental scoping was proposed and withdrawn on a concrete miss (#716 round 4).
- Language-agnosticism is settled: prawduct consumes verdicts, never re-implements tooling; an
  unknown language must fire, not go dark (#561's classify-by-exclusion).

## 5. Off-topic but pending

- #818 (norm-lifecycle `dead-why` re-fires after owner re-affirmation) is the one untriaged upstream
  report. Unrelated to this theme.
- `bin/test-reference-verify` is Python-only and feeds a BLOCKING Goal 1 check that reads as satisfied
  on Swift/C# repos having inspected nothing (#164). `_PRODUCT_CODE_SUFFIXES` omits `.cs`/`.tsx` (#561).
  Both belong in any plan that claims Swift/web/C# support.
