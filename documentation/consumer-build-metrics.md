# Consumer build metrics

How much governance costs a governed product repo, measured per prawduct version. The numbers below are a reading taken 2026-09-18; re-derive them with `tools/measure-consumer-overhead.py` rather than trusting the digits, which go stale as the corpus grows.

Anyone editing this doc should read [Hazards](#hazards-for-whoever-updates-this) first. They are at the bottom because the findings are what a person came for.

---

## Summary

1. **Review cost per run roughly doubled.** Critic went 4.7 → 8.9 minutes per run across v2.1 → v3.5; PR review went 4.9 → 13.1 minutes. Both rose monotonically, with no reversal in any window. **Every one of those minutes is the reviewing model's own estimate, not a clock** ([hazard 2](#hazards-for-whoever-updates-this)). A direct clock read on 2026-09-22 found the estimates run high, worst on short reviews (hazard 2). So the size of this rise is not established. For the Critic it is at least partly real: discodon's largest cumulatives clock at 953–1011s.
2. **Verify-resolutions share is not moving toward its target.** The [consumer-overhead program](#related-work) targets VR ≤ 45% of Critic runs against a 55–66% baseline. bankmachine went 64.2% → 61.3%. discodon went the wrong way, 66.7% → 76.5%, under v3.5.0 — the release that shipped the review stopping rule. [Why](#why-the-verify-resolutions-share-is-not-moving): that stopping rule does not count verify-resolutions, and the ceiling it does count sits at the 90th percentile of what a scope spends.
3. **The PR reviewer has never produced a blocking finding.** 178 PR reviews in discodon's plugin era: 145 warnings, 262 notes, zero blocking. Its reviewers *report* 13 minutes per review, up from 5. Where a PR review is clocked, it takes about a minute: medians of 77s in this repo (19 reviews), 76s in bankmachine (2) and 99s in hallucinote (1), measured 2026-09-21/22. discodon's PR reviews carry no clock yet, so its 13 minutes is unverified in either direction. Median PR open time is 11–65 seconds through v3.4, so the review runs before the PR exists and the PR is bookkeeping.
4. **`prawduct-hook review-stats` pools Critic and PR reviews** into one `reviews` count and one duration total. For discodon's full ledger, 14.7% of that pooled duration is PR review, so a figure labelled "Critic hours" taken from it reads 17.3% high. The program's baseline table is pooled on this basis.
5. **Blocking findings per 1k code lines rose 11×; the product-bug fix rate did not follow.** Either the Critic got better at catching what used to ship, or it got stricter about things that were never defects. This data does not separate the two.
6. **Code is a minority of output and shrinking.** Tests are the largest single class in every window. Code fell from 36.9% of lines written to a steady 27.5–28.8%, then to 18.8% in the v3.5 window.

Open questions, with recommendations, are at the [end](#open-questions).

---

## Early signal: v3.5.0 and 3.5.1-dev

**v3.5.1 is not the number these dev builds are heading for.** The 2026-09-15 ruling that named it was re-taken on 2026-09-20 and the release is being cut as **v3.6.0** (minor), so the `3.5.1-dev.N` builds below are a prerelease family whose release number changed under them rather than a line with a successor. At the time these figures were taken there was no tag and `main` was exactly `v3.5.0` (`45902920`); for the current state re-derive rather than reading this sentence — `git tag --list 'v*' --sort=-v:refname | head -3`. Two consumers are running unreleased dev builds from a local checkout, and they are running *different* builds — discodon on `3.5.1-dev.1`, bankmachine on `3.5.1-dev`. Treat this as two samples of a version family, not two samples of a version.

`.prawduct/.prawduct-version` records the last plugin version a repo's banner saw. The banner rewrites it only when the version differs, so its mtime dates the transition:

```
tools/measure-consumer-overhead.py ../discodon --marker
```

| Repo | Last-seen version | Since |
|---|---|---|
| discodon | `3.5.1-dev.1` | 2026-09-17 18:54 −0600 |
| bankmachine | `3.5.1-dev` | 2026-09-13 08:55 −0600 |
| cordyceps | `3.4.1-dev.2` | 2026-08-27 11:26 −0600 |

Measure a period the tags cannot delimit with `--since` / `--until`:

```
tools/measure-consumer-overhead.py ../bankmachine --since 2026-09-13T08:55:57-06:00
```

| Repo | Period | Days | Runs | VR % | Min/run | Find/run | Blk/run | Critic % engaged |
|---|---|---|---|---|---|---|---|---|
| bankmachine | v3.4 era | 24.2 | 159 | 64.2% | 6.9 | 4.37 | 0.66 | 21.7% |
| bankmachine | 3.5.1-dev | 4.6 | 62 | 61.3% | 5.9 | 2.32 | 0.42 | 19.8% |
| discodon | v3.4 era | 23.7 | 192 | 66.7% | 8.8 | 5.90 | 0.36 | 19.7% |
| discodon | v3.5.0 | 4.9 | 85 | 76.5% | 8.9 | 5.01 | 0.36 | 25.9% |
| discodon | 3.5.1-dev.1 | 0.5 | 10 | 70.0% | 8.4 | 5.40 | 0.40 | 26.9% |

The two consumers disagree. bankmachine improved on every axis: findings per run down 47%, blocking per run down 36%, minutes per run down 14%, Critic share of engaged time down. discodon improved on none — VR share up 10 points under v3.5.0, Critic share of time up 6 points to the highest of any window here, minutes per run flat.

With two repos moving opposite ways on three of four metrics, no framework-level effect is visible above per-repo variation yet. bankmachine's drop is large enough to be interesting and small enough to be a change in what it was building.

**Do not cite discodon's 3.5.1-dev row.** It covers 12 hours and 10 reviews, and 26,968 of its 27,742 written lines are governance — code is 2.8% of output against 28–37% everywhere else. That window holds a change-log archive rollover and the learnings backfill, not a normal build. It is in the table for completeness.

---

## Why the verify-resolutions share is not moving

A reading taken **2026-09-21** over every governed ledger on this machine — **20 ledgers across
11 products** — 2,248 Critic reviews since 2026-08-01, against 248 scopes. The corpus size is
printed by the command, so the completeness claim in that first sentence is checkable rather than
asserted; it was not, and it was wrong (hazard 10). Re-derive rather than trusting the digits:

```
tools/measure-review-loop-economy.py
```

The short answer is that the v3.5.0 review round budget is aimed elsewhere, and this is a property
of its design rather than a defect in it.

| Mode | Runs | Share of runs | Hours* | Share of hours* | Counts against the budget? |
|---|---|---|---|---|---|
| verify-resolutions | 1474 | 66% | 137.2 | 47% | **no** |
| cumulative | 605 | 27% | 136.0 | 46% | yes |
| chunk | 127 | 6% | 13.2 | 4% | yes |
| final | 42 | 2% | 7.7 | 3% | yes |

\* self-reported by the reviewing model — hazard 2. Only 23 of the 2,248 rows carry a measured
dispatch interval, so lean on the run counts, which are one row per real dispatch.

Three facts set the ceiling's reach. The tool reads the first two **parameters** from the plugin
rather than restating them (`REVIEW_ROUND_BUDGET_DEFAULT`, `FULL_ROUND_MODES`), so a change to
either lands here without anyone remembering to update prose. **It does not read the plugin's
counting PREDICATE, and that is the load-bearing limit of this section**: `analyse` pools a scope's
whole history, while `_round_budget_verdict` counts only the rounds `count_branch_rounds` admits —
within the branch's lineage span, or, where that span is empty, within the current worktree. Those
bounds are narrower than "the whole history", so the reach below is an upper bound for that reason
as well as the one stated after it. The bound itself changed in v3.6.1-dev (#776), one commit
behind this reading, which is the concrete form of the risk: parameters track, predicates do not.

1. **`FULL_ROUND_MODES` is every mode except `verify-resolutions`.** The 66% of runs that are
   verify rounds are neither counted toward the ceiling nor refused by it.
2. **The ceiling is 6 full rounds per scope, and the 90th percentile of full rounds per scope is
   6.** Only 31 of 248 scopes (12%) ever reach it. The median scope spends 2 full rounds and 3
   verify rounds.
3. **10% of reviews record no scope at all.** `_round_budget_verdict` returns `unavailable` for
   those, and unavailable never refuses — deliberately, since a stopping rule whose count cannot
   be derived must fail toward selling the round.

Together those bound what the control can ever touch at **118h of 294h (40%)**, and only past a
scope's sixth full round. That 40% is an **upper bound, not a saving**: it counts every hour in
scopes that ever hit the ceiling, including the rounds spent before it would have fired.

One more bound, worth stating because widening the corpus (hazard 10) made it live: the per-scope
key is `(directory name, scope)` — the ledger's grandparent directory, not its path and not the
clone — so it does **not** group worktrees the way the product count does. That cuts both ways. A
scope worked in both a checkout and its worktree **splits** into two cells, so neither reaches the
ceiling when their sum would, and `scopes at the ceiling` is understated; and two ledgers whose
directories happen to share a name would **merge**, overstating a scope's rounds. On this machine
the split is the live one and the merge is hypothetical, so the net is downward and the reach
figure is not threatened — but a later reading that keys on the clone should expect the 12% to
rise, and should not assume the key is unique.

### The largest addressable block is repeat cumulatives

**322 of 534 cumulative runs (60%) are the second-or-later cumulative on a scope already reviewed
cumulatively**, across 110 of 212 scopes. **Neither denominator is the one printed above it, and
for two different reasons.** 534 is the mode table's 605 cumulative runs minus the 71 that record no
scope, since a repeat is a question about a scope and those rows have none (hazard 8) — re-deriving
against 605 gives 53% and answers a different question. 212 is not a scoped subset of anything: all
248 corpus scopes are scoped by construction, and 212 is how many of them ran a cumulative at all,
which is the only population in which a *repeat* cumulative is possible. Cumulative is the most expensive mode per run, so this is
the biggest single block of re-review in the corpus — larger than everything the chunk and final
modes cost together, and it sits outside what the round budget reaches until the sixth round.

This is the target of the consumer-overhead program's WS5 (#672, coverage composing by tree while
its gates key on identity), which that program ranks fifth.

### What each consumer is actually running

```
tools/measure-review-loop-economy.py        # the MARKERS table
```

Read with hazard 4 in view: the marker holds the version a repo saw **most recently**, and its
mtime dates that transition. It is not a history, so it cannot tell you what a repo ran before.

As of 2026-09-21 the fifteen markers sit on ten different plugin versions, and v3.6.0 (tagged
2026-09-20) is on none of them. Twelve are `-dev` snapshots spanning `3.3.5-dev` to `3.6.1-dev`;
the other three are released versions — `scriob` on `3.0.4`, and two worktrees on `3.3.4`, the
oldest dating to 2026-07-16. Both halves follow from the install shape rather than from anyone's neglect:
the marketplace is a `directory` source pointing at this repo's checkout with `autoUpdate` on, so a
consumer snapshots whatever version string that checkout happens to carry at the moment it is next
opened — a development version most of the time, a release only if it opened on one. A repo not
opened for two months stays where it was. Any claim of the form "consumers now get X" is a claim
about when they were last opened.

---

## The full reading, 2026-09-18

discodon, 2026-06-11 → 2026-09-18. Before 2026-06-11 it ran file-synced framework files and has no ledger.

The endpoint is pinned so these tables stay reproducible — the newest window is open-ended and grows every time the consumer commits. Drop `--until` to read it forward.

```
tools/measure-consumer-overhead.py ../discodon --prs --until 2026-09-18T13:00:00Z
```

### Effort and output

```
series   days  sess   hours  h/day    code+    test+     gov+  lines/h  code%
v2.1     12.9    31    48.8   3.78    10588    10902     7033      589   36.9
v2.2     10.8    22    35.9   3.33     7825    10669     4771      660   33.0
v2.3      9.2    37    64.1   6.96    15667    19448    15403      796   30.7
v3.0      3.6    14    35.4   9.87     5870     7553     7429      596   27.8
v3.1     11.7    36   121.1  10.36    38002    57334    40998     1141   27.5
v3.2     12.0    34   153.4  12.81    45116    59070    53611     1064   27.6
v3.3      9.3    17   115.4  12.38    39187    58996    34612     1192   28.5
v3.4     23.9    57   144.8   6.06    50480    69447    50664     1209   28.8
v3.5      5.4    16    53.3   9.85    13278    22715    32601     1321   18.8
```

Lines written per engaged hour went 695 → 1,170 between the v2.1–v2.3 and v3.2–v3.5 eras, up 68%.

Share of all lines written, by class:

| | code | test | governance | docs |
|---|---|---|---|---|
| v2.1 | 36.9% | 38.0% | 24.5% | 0.7% |
| v3.0 | 27.8% | 35.8% | 35.2% | 1.2% |
| v3.2 | 27.6% | 36.2% | 32.9% | 3.3% |
| v3.4 | 28.8% | 39.7% | 28.9% | 2.6% |
| v3.5 | 18.8% | 32.2% | 46.3% | 2.7% |

In v3.5, governance reached 46.3% — within 5 points of code and tests combined, and its highest share on record. One 5.4-day window is not a trend, but it is the figure to watch next run.

### Critic

```
series    runs   hours  min/run  %engaged  runs/day  find/run  blk/run  blocking
v2.1        92     7.2      4.7      14.7      7.13      1.77     0.02         2
v2.2        54     5.1      5.6      14.2      5.00      2.48     0.04         2
v2.3        72     6.9      5.8      10.8      7.83      3.00     0.01         1
v3.0        60     6.4      6.4      18.0     16.67      3.40     0.05         3
v3.1       188    22.1      7.1      18.3     16.07      4.95     0.15        28
v3.2       238    31.8      8.0      20.7     19.83      6.94     0.30        71
v3.3       148    21.1      8.5      18.3     15.91      6.26     0.49        73
v3.4       193    28.3      8.8      19.5      8.08      5.99     0.37        71
v3.5        95    14.0      8.9      26.3     17.59      5.05     0.37        35
```

The break is at v3.1, not a gradual drift: 5 blocking findings across all of v2.x and 8 through v3.0, then 28 in the v3.1 window alone and 71–73 per window after.

### PR layer

```
series   merged  reviews  hours  min/review  findings  blocking  median open h
v2.1         80       31    2.5         4.9        31         0          0.004
v2.2         18        6    0.6         5.7         9         0          0.003
v2.3         94       30    3.2         6.4        53         0          0.011
v3.0         28        9    0.7         4.8         9         0          0.018
v3.1         65       25    2.9         7.0        55         0          0.006
v3.2         83       22    3.6         9.8        82         0          0.006
v3.3         94       21    3.5        10.0        66         0          0.004
v3.4         56       23    5.3        13.7        71         0          0.007
v3.5         11       11    2.4        13.1        31         0          0.076
```

### Defect signal

```
series   fix cmts  review-drv  prod-bug  prod/1k code  blocking/1k code
-----------------------------------------------------------------------
v2.1           39          18        21          1.98              0.19
v2.2            7           4         3          0.38              0.26
v2.3           40          29        11          0.70              0.06
v3.0           18          15         3          0.51              0.51
v3.1          132          95        37          0.97              0.74
v3.2          268         223        45          1.00              1.57
v3.3          256         169        87          2.22              1.86
v3.4          154         119        35          0.69              1.41
v3.5           79          60        19          1.43              2.64
```

Product-bug fixes per 1k code lines went 1.03 → 1.26 between the two eras, a 22% rise inside the classifier's own ±60% band, in a series ranging 0.38–2.22 with no monotone trend and its peak in the middle at v3.3.

### Testing

```
series   test cmts  test+ lines  test:code
------------------------------------------
v2.1             5        10902       1.03
v2.2             0        10669       1.36
v2.3             2        19448       1.24
v3.0             2         7553       1.29
v3.1            25        57334       1.51
v3.2            36        59070       1.31
v3.3            54        58996       1.51
v3.4            27        69447       1.38
v3.5            13        22715       1.71
```

### Era aggregate

| | v2.1–v2.3 | v3.2–v3.5 | Change |
|---|---|---|---|
| Engaged hours | 149 | 467 | — |
| Lines written per hour | 695 | 1,170 | +68% |
| Critic runs | 218 | 674 | — |
| Critic hours / engaged | 13% | 20% | +54% |
| Findings per run | 2.35 | 6.25 | +166% |
| Blocking per 1k code lines | 0.15 | 1.69 | +11× |
| Product-bug fixes per 1k code lines | 1.03 | 1.26 | +22% |

---

## How to re-run

Windows are one per prawduct **minor** series, taken from this repo's release tags on `main`. Patch releases land hours apart, which is finer than a consumer can respond to.

| Flag | Use |
|---|---|
| *(none)* | Full history from the consumer's plugin migration. |
| `--prs` | Add merged-PR cadence. Needs `gh` authenticated; slower. |
| `--since` / `--until` | Isolate a period the tags cannot delimit, such as a dev build. |
| `--marker` | Print the consumer's last-seen plugin version and when it changed. |
| `--json` | Full report, for scripting. |
| `--show-classification` | Print how each changed path was bucketed. Run this before citing `code` numbers for a consumer with an unusual layout. |

Four sources, three independent of each other: the consumer's `.prawduct/.governance-ledger.jsonl`, its git history classified by path, this repo's release tags, and optionally GitHub for PR cadence.

Engaged wall clock comes from clustering commits and ledger events into sessions — any gap over 90 minutes ends one — plus 20 minutes credited before each session's first event. Time inside a session is attributed to the category of the event ending each interval.

---

## Hazards for whoever updates this

Every one of these produced a wrong answer before it was caught, so read all of them — the numbers are identifiers, **not a ranking**. They used to be ordered by how badly each one burns, and new hazards are appended rather than inserted, so the claim went stale the first time one was added: hazard 10 moved every published digit in § *Why the verify-resolutions share is not moving*, which is a worse burn than several above it. Renumbering would break every citation, so the ordering claim goes instead of the order.

1. **Interval attribution is biased by commit density, and can invert a trend.** Read naively, discodon's measured split says Critic *fell* from 65% of engaged time to 17%. It rose, 13% → 20%. Commit density tripled over the period, so the instrument's resolution is itself a function of the variable being measured. The VALIDATION table exists for this: its ratio is 2.96–4.61 in the sparse v2.x and v3.0 windows and 0.94–1.16 in the dense v3.2+ ones. Where that ratio is near 1, believe the measured split. Where it is not, use the self-reported durations.
2. **`duration_seconds` is self-reported by the reviewing model, not a measured clock.** 74 distinct values across discodon's 1,318 review events, mostly round. It was corroborated within 16% in discodon's commit-dense windows, and that was once read as licensing it elsewhere. **That licence is withdrawn.** Since `critic-begin` and `pr-review-dispatch --begin` started marking dispatch, the clock can be read directly on the same rows. Read that way on 2026-09-22, **the estimate runs high, and worst on short reviews.** This repo's PR review clocks at a median of 77s against 240s estimated on the same 19 rows (about 3×), and its verify-resolutions at 171s against 300s. Its cumulatives clock at 362s against a 720s estimated median, and on individual cumulative rows the ratio runs 1.2–2.4×. On discodon's verify-resolutions rounds, which really take about five minutes, the two are level (286s against 280s, n=10). The 16% agreement was a property of discodon's durations, not of the estimate. The estimate is not a constant either: on discodon's two largest cumulatives it read 1500s and 1260s, against 953s and 1011s clocked on the same rows (`.prawduct/artifacts/cumulative-latency-discovery.md`). The overstatement was smaller there than on short reviews, but those reviews really are long. So an estimated trend can be part real and part inflation, and only the clock separates the two. Use the measured population wherever it exists: `prawduct-hook review-stats --json` reports `duration_measured` and `duration_self_reported` separately, per role and mode, under `by_role_model_mode`.
3. **A repo without conventional-commit prefixes reports 0 fix commits and 0 test commits.** That reads as "no bugs, no tests" and means "not measurable this way." bankmachine is such a repo. The tool measures the convention and prints `—` instead of `0`; do not undo that.
4. **The tags do not tell you what version a consumer ran.** These consumers run dev builds from a local checkout. Use `--marker`, and remember it dates only the most recent transition — periods before it are "at most" that version.
5. **A backfilled event kind is not a cadence.** All 594 discodon `learning.written` events landed inside 12.8 minutes on 2026-09-18. The tool detects and flags this; do not average it into a rate.
6. **The review-driven fix classifier is a wide heuristic.** Matching the full commit body versus its first 600 characters moves the product-bug rate by up to 60%. The shape holds either way; the level is a band.
7. **Windows are confounded with what the consumer was building**, and a consumer pinned to `ref: main` with `autoUpdate` picks up a release at its next session, so each boundary is fuzzy by up to one session.
8. **A review with no `scope` is not a scope.** Pooling the ~10% of scope-less rows under one key per repo invents a single enormous scope, pushes it past the round ceiling, and overstates the ceiling's reach. The first pass of the 2026-09-21 reading did exactly that and reported 14% of scopes at the ceiling and 64% repeat cumulatives; excluding them — which is what `_round_budget_verdict` itself does, returning `unavailable` — gives 12% and 60%. `measure-review-loop-economy.py` counts them separately and `TestAScopelessRowIsNeverAScope` pins it.
9. **A sentence written off a printed table describes the rows you looked at.** The 2026-09-21 reading first wrote that every marker was a `-dev` snapshot spanning `3.3.4` to `3.5.1-dev.2` — which is the MARKERS table with its first and last rows cut off. Three of the fifteen are released versions (`3.0.4`, and `3.3.4` twice), the oldest from 2026-07-16. The conclusion survived the correction and the warrant did not, which is the worse direction: conclusions get re-derived by the next reader, warrants get copied. Partition with `--json` rather than reading a sorted list, and count the set before writing "every".
10. **A one-level glob reads as complete and is not.** The first cut of `find_ledgers` globbed `*/.prawduct/.governance-ledger.jsonl`, which cannot see a worktree ledger INSIDE a repo (`<repo>/.claude/worktrees/<name>/`) or a clone parked under a hidden directory. It found 17 of this machine's 20 ledgers, and the excluded set was not a random sample — it was exactly the delegated work. The published reading undercounted by 23 reviews and 3 scopes and reported "13 repos" for what is 11 products across 20 ledgers, while the prose above it claimed "every governed ledger on this machine". The corpus size is now printed on the CORPUS line so the completeness claim is checkable, and `TestTheCorpusIsBoundedByPropertyNotByDepth` pins the depth with a control proving the old predicate would have missed the fixture.

---

## Related work

The `consumer-overhead-2026-09` program and its 2026-09-16 triage set targets for review round economy. As of 2026-09-18 both live on the unmerged branch `docs/consumer-overhead-program` at `.prawduct/artifacts/consumer-overhead-program-2026-09.md`, not on develop. That program is narrower and deeper than this doc: it targets VR share specifically, where this asks what a consumer's whole build economy looks like.

That triage set its baseline with a query that lived in a scratchpad and is gone, which is why its figures cannot be re-derived and this tool exists.

Measured against that branch on **2026-09-21**: its WS0 (cut the release) and WS2 (learnings-v2, #744) have since shipped, and #292 and #767 — which it placed out of scope and deferred respectively — shipped in v3.6.0. Its workstream table therefore describes a state the tree has moved past; re-derive with `git log --oneline develop..docs/consumer-overhead-program` and by resolving each issue it names before planning from it. [Why the verify-resolutions share is not moving](#why-the-verify-resolutions-share-is-not-moving) bears directly on its WS1/WS5 ranking.

---

## Open questions

1. **Should `review-stats` report Critic and PR separately?** Recommend yes. Every overhead figure downstream of it is currently pooled, and the two have different costs and very different yields — one of them has never blocked anything.
2. **Is the PR reviewer worth 13 minutes a review?** Owner, 2026-09-22: no — 13 minutes would be far too much. But a clocked review takes about a minute ([summary 3](#summary)), and `/prawduct:pr` runs it concurrently with the cumulative Critic, so at the PR boundary it adds almost no wall clock. The question is re-opened only if discodon's first clocked PR reviews come back long. Originally: no recommendation; this needs a judgment about what it is for. It has produced 407 non-blocking findings in discodon's plugin era, so "it catches nothing" is false. "It gates nothing" is true.
3. **Should the ledger record a dispatch timestamp beside the write timestamp?** Done: both review kinds now carry one where their dispatch was marked, and the round price quoted to agents (`telemetry.round_price`) prefers it. Originally: recommend yes. It would retire hazards 1 and 2 outright and make review duration checkable on every run rather than only where commits are dense.
4. **Why did minutes per run double?** First ask how much of it is real — see summary 1: the doubling was measured in estimates, and the clock confirms long cumulatives on discodon but has not yet been read across the history. `.prawduct/artifacts/cumulative-latency-discovery.md` has the clocked drivers for the recent rows. Originally: unknown. Longer diffs, more goals per review, larger rosters and slower models are all consistent with the data here, and this tool cannot separate them.
