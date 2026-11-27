# Issue #1244 — test-evidence: Critic flags determinism cause sites a diff adds: Requirements

`status: draft · stage: requirements · area: methodology (test-evidence, critic) · added: 2026-11-27 ·
source: user, the measured leg of #1243 split out by the owner ruling of 2026-11-24 · issue:
https://github.com/brookstalley/prawduct/issues/1244`

Related: #1243 (closed 2026-11-25: the rule, the static detector, the janitor sweep), #1096 (the
test-evidence ledger, design stage, the issue's stated blocker), #1088 (flakes touched by covered
code, the other consumer of per-test run data), #1091 (narrow testament runs).

## What exists today (read on `main` at `e9c06c0`, not recalled)

- **The static half shipped with #1243.** `plugin/lib/determinism_lint.py` compares base and head
  source and reports five check ids a change *introduces*: `test-scope-conftest`,
  `test-scope-autouse`, `test-scope-init` (blocking at the merge boundary) and `test-clock-fake`,
  `test-clock-import` (warning). A site is keyed by what it is, never by line number; a rename
  introduces nothing; `prawduct:allow prawduct/test-scope -- reason` waives one. Severities live in
  `record_lint.py` beside the other record-lint checks. The catalogue (P1–P8) has one home,
  `plugin/docs/test-determinism.md`.
- **A reader of runner-reported causes already exists, as an advisory.**
  `plugin/lib/testament_cache_probes.py` reads testament's per-worktree cacheability snapshot
  (envelope `v: 1`, `root`, `commit`, `selection`, `suite`, `rows[].causes[]` each with `kind`,
  `site` (`path:function`), `scope`, `alone`) and raises one session-start advisory per suite whose
  *whole* set of sole-blocker causes is non-empty. It sanitises every token (kinds and scopes plain
  words, sites `path:function`), never carries testament's free text, and says "could not look"
  rather than "nothing to report" when the snapshot is narrowed, unknown-version, unreadable or off
  this branch's history. It reports what *exists*, not what a diff *added*, and nothing records
  the list with a run.
- **The run record has no place for it.** `evidence.append_test_run` writes a `test-run` fact
  (`tree`, counts, `source`, `head`, `degraded`, capped `failed_tests`). #1096 designs additive,
  optional body fields on that same kind (`scope`, `outcomes`, `env`); none is built
  (`grep -n outcomes plugin/lib/evidence.py` names only an unrelated comment).
- **`test-run` facts do not travel.** `evidence.TRANSPORTED_KINDS` is
  `{review, resolution, disposition, chunk-imported, chunk-retracted}`. A cause list stored on a
  run is therefore visible only in the clone that ran the suite.
- **Binding constraints already ruled** (`.prawduct/owner-rulings.md`, 2026-11-24): nothing in
  the determinism work may depend on testament, and #1244's check "runs only when the project's
  runner reports per-test causes, doing nothing otherwise". The #1243 build plan
  (`.prawduct/artifacts/archive/build-plan-test-determinism.md`, Architecture) adds: measured
  causes "join the same check ids rather than adding a parallel vocabulary".

## Problem

The static detector reads what a diff's own lines say. A cause the runner observes at run time —
a clock read three calls below a fixture, a subprocess a shared helper starts, a file the tests
read that setup wrote into the tree — is invisible to it, and to a reviewer reading the diff. The
runner sees it; prawduct throws that observation away except as a whole-repo advisory that cannot
say which change caused which cause. So a change can make hundreds of tests uncacheable or
unrepeatable, pass every gate, and surface only as a larger number in next session's advisory,
with no link back to the change.

Who meets it: any governed product whose runner reports per-test determinism causes. Today that
is testament; the measured costs that motivated #1243 (36–49% of each big product's results
uncacheable over 2026-11-17 to 11-24) came from it.

## Goals

- G1. When the runner reports causes, a cause site present after a change and absent before it
  reaches the review as a finding, attributed to that change.
- G2. Where the runner reports nothing, or there is nothing to compare against, the review says
  it could not compare. It never reports "no new causes" from missing data.
- G3. No dependency on any one runner. testament is the first source, not the definition.
- G4. One vocabulary. A measured finding and a static finding for the same pattern carry the
  same check id, severity rule and waiver, and do not appear twice for one site.
- G5. The change is measured: before/after cacheable share and closure breadth on two governed
  products, each figure with the command that re-derives it.

## Non-goals

- Any testament-side change (#975, #976, #979–#982 live in that repo), and per-product cleanup.
- Reporting causes that already exist. That is the advisory and the janitor sweep (#1243).
- Making any test-evidence gate (Stop, PR) read causes. A cause list never changes whether the
  suite vouches for a tree.
- Transporting `test-run` facts to other clones. G2 covers the clone that lacks a base list.
- Closure breadth as a per-change finding. It is a success measure here (G5), not a check; see Q3.

## Requirements

**Recording (the producer)**

- R1. A runner-neutral input. The recorder accepts a cause list as a minimal data primitive: per
  cause, `kind`, `site`, `scope`, and the count of tests it alone blocks. testament's
  cacheability snapshot is one adapter onto that primitive, not the format
  (hook-surface learnings: expose the primitive, not one ecosystem's file). Design decides
  whether the primitive is a flag on `test-evidence record`, a file alongside `--from-junit`, or
  read from the runner's state directory as the probe does.
- R2. The list is stored with the run it came from, on the `test-run` fact, as an additive,
  optional body field. Absence means "the runner reported none or was not asked"; a run whose
  runner reported zero causes stores an explicit empty list, so the two are distinguishable
  (hook-surface learnings: a value naming the absence is its opposite). Older readers ignore the
  field.
- R3. Only a whole-suite run records a list that can serve as a base or a head. A narrowed run's
  list is either not stored or stored marked narrow and never compared, matching the probe's
  "a `-k` run is not the project's state".
- R4. The list is bound to the tree the run met, by the same tree capture the fact already uses.
  A snapshot whose commit or tree does not match the run being recorded is refused, not attached.
- R5. Every token is sanitised before it is stored, by the rules the probe already applies, and
  through one shared function, not a second copy. Free-text fields (`hint`, `why`) are never
  stored. The store is read into reviewer context, so it is a governance surface.

**Comparing (the consumer)**

- R6. At review, the Critic's mechanical layer finds the head run (newest whole-suite run that
  met the reviewed tree) and the base run (newest whole-suite run that met the base tree), and
  reports each cause whose key `(kind, site, scope)` is in head and not in base. Keyed by site,
  never by rank or count, so a cause that merely blocks more tests is not "introduced".
- R7. A site in a renamed file compares against its old path, as `determinism_lint` does, so a
  move introduces nothing.
- R8. Each introduced cause maps onto an existing check id from `determinism_lint.CHECKS` where
  one fits (e.g. a clock or randomness read in a fake or conftest → `test-clock-fake`). A cause
  kind with no existing id gets one new id under the same `test-` family, added to
  `record_lint`'s severity table and to `docs/test-determinism.md`; design enumerates testament's
  current kinds against P1–P8 and names the mapping. An unknown kind is reported as an
  observation, never dropped and never blocking.
- R9. One site, one finding. When the static detector and the measured comparison both report
  the same site under the same id, the review shows one finding naming both sources.
- R10. The `prawduct:allow prawduct/test-scope -- reason` waiver on the site's line drops a
  measured finding exactly as it drops a static one.
- R11. "Could not compare" is a reported state with its reason: no head run with a list, no
  base run with a list (the normal case in a fresh clone or CI, since `test-run` facts do not
  travel), a narrowed list, or an unknown envelope version. It reaches the review as an
  observation, never as a pass and never as a blocker.
- R12. Cost: the comparison reads two facts and no source. It runs no test and no runner
  command (the Critic's no-execution contract).

**Every description agrees**

- R13. `plugin/docs/test-determinism.md` gains the measured channel: what it reads, when it
  cannot compare, and the id mapping. The build plan's forward reference to #1244 is left as
  history (archived). `plugin/skills/critic/goals-1-3.md` and `review-protocol.md` say measured
  findings arrive mechanically, like the static ones, and a reviewer does not re-derive them.
  Design finds other descriptions by searching for the claim ("the runner reports", "measured",
  "cacheability"), not only these tokens.

**Measuring (G5)**

- R14. On two governed products, record cacheable share of tests and closure breadth
  (non-test modules in ≥90% of closures) after this ships, against #1243's 2026-11-24 baseline.
  Each figure is written with the command that re-derives it, never as a bare number (authoring
  learnings). The record lives in `documentation/` beside this file, and names no figure the
  command cannot reproduce.

## Acceptance

- A1. With a runner that reports causes, a whole-suite run's `test-run` fact carries the
  sanitised list; with one that reports none, the field is absent; with zero causes, it is empty.
- A2. Fixture test: base and head facts differ by one cause site; the review reports exactly that
  site under its mapped id. Seen to fail with the comparison disabled (core learnings: a check
  never seen to return non-zero proves nothing).
- A3. Fixture tests for each R11 reason produce "could not compare" with that reason, and none
  produces a finding or a pass.
- A4. A cause in a renamed file, a cause whose `alone` count grew, and a waived site each produce
  no finding.
- A5. A site both detectors report produces one finding.
- A6. R14's record exists with its commands.

## Risks

- **Base availability.** Most reviews may say "could not compare", because few clones run the
  whole suite on the base tree. If so the check is real but rarely fires. Q2 asks how to get a
  base list.
- **Runner noise.** A cause may appear or vanish between runs for reasons unrelated to the diff
  (environment, cache warmth). A flapping site reads as introduced. Design checks testament's
  stability on two consecutive runs of an unchanged tree before trusting the comparison.
- **Attribution.** "Absent in base, present in head" names the site, not the line that caused
  it; the cause may sit in an unchanged file the diff now reaches. The finding text must say
  so, rather than imply the site's own line changed.

## Open questions for the owner

- Q1. **Is the #1096 gate needed?** The issue says "Blocked by #1096". This item needs only one
  additive field on today's `test-run` fact (R2) and two fact reads (R6). It uses none of
  #1096's composition, flaky guard or narrow overlay. Recommended: unblock it, and have #1096's
  schema slice adopt the field rather than introduce it. The alternative keeps it waiting on an
  L-effort design still at design stage.
- Q2. **Where does the base list come from?** Options: (a) only a base run this clone already
  recorded, else "could not compare" (simplest, may rarely fire); (b) the runner's own history,
  if it keeps one per commit (not verified for testament; the probe reads one snapshot per
  worktree), read through the same adapter; (c) transport
  `test-run` cause lists with reviews. Recommended: (a) now, (b) as the testament adapter's
  second source if A2–A3 show (a) rarely compares. (c) widens what is published and is its own
  decision.
- Q3. **Severity of a measured cause with no static twin.** Recommended: the mapped id's existing
  severity (warning for clock/randomness; blocking only where the id is already blocking), and
  observation at the inner stage, matching the #1243 table. The alternative, warning for every
  measured finding regardless of id, is simpler but splits one id's severity by source, against
  G4.
