# Consumer build metrics

How much governance costs a governed product repo, measured per prawduct version. The numbers below are a reading taken 2026-09-18; re-derive them with `tools/measure-consumer-overhead.py` rather than trusting the digits, which go stale as the corpus grows.

Anyone editing this doc should read [Hazards](#hazards-for-whoever-updates-this) first. They are at the bottom because the findings are what a person came for.

---

## Summary

1. **Review cost per run roughly doubled.** Critic went 4.7 → 8.9 minutes per run across v2.1 → v3.5; PR review went 4.9 → 13.1 minutes. Both rose monotonically, with no reversal in any window. This is the cleanest trend in the data — every other metric here is noisy by comparison.
2. **Verify-resolutions share is not moving toward its target.** The [consumer-overhead program](#related-work) targets VR ≤ 45% of Critic runs against a 55–66% baseline. bankmachine went 64.2% → 61.3%. discodon went the wrong way, 66.7% → 76.5%, under v3.5.0 — the release that shipped the review stopping rule.
3. **The PR reviewer has never produced a blocking finding.** 178 PR reviews in discodon's plugin era: 145 warnings, 262 notes, zero blocking. It now costs 13 minutes per review, up from 5. Median PR open time is 11–65 seconds through v3.4, so the review runs before the PR exists and the PR is bookkeeping.
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

Numbered by how badly each one burns you. Each of these produced a wrong answer before it was caught.

1. **Interval attribution is biased by commit density, and can invert a trend.** Read naively, discodon's measured split says Critic *fell* from 65% of engaged time to 17%. It rose, 13% → 20%. Commit density tripled over the period, so the instrument's resolution is itself a function of the variable being measured. The VALIDATION table exists for this: its ratio is 2.96–4.61 in the sparse v2.x and v3.0 windows and 0.94–1.16 in the dense v3.2+ ones. Where that ratio is near 1, believe the measured split. Where it is not, use the self-reported durations.
2. **`duration_seconds` is self-reported by the reviewing model, not a measured clock.** 74 distinct values across discodon's 1,318 review events, mostly round. It is corroborated within 16% wherever commits are dense enough to check it, which is what licenses using it elsewhere.
3. **A repo without conventional-commit prefixes reports 0 fix commits and 0 test commits.** That reads as "no bugs, no tests" and means "not measurable this way." bankmachine is such a repo. The tool measures the convention and prints `—` instead of `0`; do not undo that.
4. **The tags do not tell you what version a consumer ran.** These consumers run dev builds from a local checkout. Use `--marker`, and remember it dates only the most recent transition — periods before it are "at most" that version.
5. **A backfilled event kind is not a cadence.** All 594 discodon `learning.written` events landed inside 12.8 minutes on 2026-09-18. The tool detects and flags this; do not average it into a rate.
6. **The review-driven fix classifier is a wide heuristic.** Matching the full commit body versus its first 600 characters moves the product-bug rate by up to 60%. The shape holds either way; the level is a band.
7. **Windows are confounded with what the consumer was building**, and a consumer pinned to `ref: main` with `autoUpdate` picks up a release at its next session, so each boundary is fuzzy by up to one session.

---

## Related work

The `consumer-overhead-2026-09` program and its 2026-09-16 triage set targets for review round economy. As of 2026-09-18 both live on the unmerged branch `docs/consumer-overhead-program` at `.prawduct/artifacts/consumer-overhead-program-2026-09.md`, not on develop. That program is narrower and deeper than this doc: it targets VR share specifically, where this asks what a consumer's whole build economy looks like.

That triage set its baseline with a query that lived in a scratchpad and is gone, which is why its figures cannot be re-derived and this tool exists.

---

## Open questions

1. **Should `review-stats` report Critic and PR separately?** Recommend yes. Every overhead figure downstream of it is currently pooled, and the two have different costs and very different yields — one of them has never blocked anything.
2. **Is the PR reviewer worth 13 minutes a review?** No recommendation; this needs a judgment about what it is for. It has produced 407 non-blocking findings in discodon's plugin era, so "it catches nothing" is false. "It gates nothing" is true.
3. **Should the ledger record a dispatch timestamp beside the write timestamp?** Recommend yes. It would retire hazards 1 and 2 outright and make review duration checkable on every run rather than only where commits are dense.
4. **Why did minutes per run double?** Unknown. Longer diffs, more goals per review, larger rosters and slower models are all consistent with the data here, and this tool cannot separate them.
