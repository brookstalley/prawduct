# Consumer build metrics — method, and the 2026-09-18 reading

**Derivation:** `tools/measure-consumer-overhead.py` — every number below is
reproducible from it. Cite the command, not the digits; the corpus grows and the
digits go stale silently.

    tools/measure-consumer-overhead.py ../discodon --prs

**Related:** the `consumer-overhead-2026-09` program and its 2026-09-16 triage
(`.prawduct/artifacts/consumer-overhead-program-2026-09.md`), which as of
2026-09-18 live on the unmerged branch `docs/consumer-overhead-program`, not on
develop. That program measures *review round economy* and sets targets against it.
This document is wider and shallower: it asks what a consumer's whole build
economy looks like across framework versions, so a later run can tell whether a
framework change moved anything a consumer would feel.

---

## Why this exists

The triage's baseline was produced by a query that lived in a scratchpad and is
gone. That makes its figures unfalsifiable and its comparison un-repeatable — the
exact failure mode the framework warns about elsewhere. The script is the fix: the
methodology is executable, so "re-measure after WS1 ships" is one command rather
than a re-derivation that may or may not match.

## What it measures

Windows are one per prawduct **minor** series, boundaries taken from this repo's
release tags on `main`. Patch releases land hours apart, which is finer than a
consumer can respond to; the minor series is the coarsest grouping that still
tracks a change in what the framework asks of consumers.

| Table | Question |
|---|---|
| A — effort and output | How much engaged wall clock, and how many lines of what kind, per window? |
| B — Critic | How many runs, how many hours, how many findings, how severe? |
| C — PR layer | How much does the PR gate cost, and what does it catch? |
| D — defect signal | Are fix commits closing review findings or product bugs? |
| E — testing | Is test volume tracking code volume? |
| VALIDATION | Is this window's phase attribution trustworthy at all? |

Engaged wall clock is derived by clustering commits and ledger events into
sessions (any gap over 90 minutes ends one) and crediting 20 minutes before each
session's first event. Time inside a session is attributed to the category of the
event that *ends* each interval.

## Four cautions, each of which produced a wrong answer first

1. **`duration_seconds` in the ledger is self-reported by the reviewing model**,
   not a measured clock — 74 distinct values across discodon's 1,318 review
   events, mostly round. The VALIDATION table exists to decide when to believe it.
2. **Interval attribution is biased by commit density.** In a window with few
   commits, coding time gets absorbed into whichever governance event came next.
   Read naively, discodon's measured split says Critic *fell* from 65% of engaged
   time to 17%. It did not. The VALIDATION ratio is 2.96–4.61 in the sparse v2.x
   and v3.0 windows and 0.94–1.16 in the dense v3.2+ ones — where measurement is
   sound, the self-report is corroborated within 16%, and that is what licenses
   using the self-report in the windows where measurement is not sound.
3. **A backfilled event kind is not a cadence.** All 594 discodon
   `learning.written` events carry timestamps inside 12.8 minutes on 2026-09-18.
   The script detects and flags this rather than averaging it into a rate.
4. **The review-driven fix classifier is a wide heuristic.** Matching the full
   commit body versus its first 600 characters moves the per-window product-bug
   rate by up to 60%. The *shape* is robust to that choice; the level is a band.

Windows are also confounded with what the consumer happened to be building, and a
consumer pinned to `ref: main` with `autoUpdate` picks up a release at its next
session, so each boundary is fuzzy by up to one session.

---

## Reading of 2026-09-18 — discodon

Measured 2026-09-18 over 2026-06-11 → 2026-09-18 (plugin-distribution era; before
that discodon ran file-synced framework files and has no ledger).

### A — effort and output

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
v3.5      5.4    16    53.3   9.90    13278    22715    32599     1322   18.8
```

### B — Critic (hours self-reported)

```
series    runs   hours  %engaged  runs/day  find/run  blk/run  blocking
v2.1        92     7.2      14.7      7.13      1.77     0.02         2
v2.2        54     5.1      14.2      5.00      2.48     0.04         2
v2.3        72     6.9      10.8      7.83      3.00     0.01         1
v3.0        60     6.4      18.0     16.67      3.40     0.05         3
v3.1       188    22.1      18.3     16.07      4.95     0.15        28
v3.2       238    31.8      20.7     19.83      6.94     0.30        71
v3.3       148    21.1      18.3     15.91      6.26     0.49        73
v3.4       193    28.3      19.5      8.08      5.99     0.37        71
v3.5        95    14.0      26.3     17.59      5.05     0.37        35
```

### C — PR layer

```
series   merged  reviews  hours  findings  blocking  median open h
v2.1         80       31    2.5        31         0          0.004
v2.2         18        6    0.6         9         0          0.003
v2.3         94       30    3.2        53         0          0.011
v3.0         28        9    0.7         9         0          0.018
v3.1         65       25    2.9        55         0          0.006
v3.2         83       22    3.6        82         0          0.006
v3.3         94       21    3.5        66         0          0.004
v3.4         56       23    5.3        71         0          0.007
v3.5         11       11    2.4        31         0          0.076
```

### D — defect signal, and E — testing

```
series   fix cmts  review-drv  prod-bug  prod/1k code  blocking/1k code   test:code
v2.1           39          18        21          1.98              0.19       1.03
v2.2            7           4         3          0.38              0.26       1.36
v2.3           40          29        11          0.70              0.06       1.24
v3.0           18          15         3          0.51              0.51       1.29
v3.1          132          95        37          0.97              0.74       1.51
v3.2          268         223        45          1.00              1.57       1.31
v3.3          256         169        87          2.22              1.86       1.51
v3.4          154         119        35          0.69              1.41       1.38
v3.5           79          60        19          1.43              2.64       1.71
```

### Era aggregate

| | v2.1–v2.3 | v3.2–v3.5 | change |
|---|---|---|---|
| Engaged hours | 149 | 467 | — |
| Lines written per hour | 695 | 1,170 | +68% |
| Critic runs | 218 | 674 | — |
| Critic hours / engaged | 13% | 20% | +54% |
| Findings per run | 2.35 | 6.25 | +166% |
| Blocking per 1k code lines | 0.15 | 1.69 | **+11×** |
| Product-bug fixes per 1k code lines | 1.03 | 1.26 | +22% (inside the classifier's band) |

## What the reading says

**Throughput rose and the review layer got harsher; the underlying defect rate
barely moved.** Output per engaged hour is up 68%. Blocking findings per thousand
code lines rose elevenfold. Product-bug fixes per thousand code lines moved 1.03 →
1.26 — a 22% rise that sits inside the classifier's own ±60% band, in a series
that ranges 0.38–2.22 with no monotone trend and its peak in the middle (v3.3).

The discontinuity is **v3.1**, not a gradual drift: 5 blocking findings across all
of v2.x and 8 through v3.0, then 28 in the v3.1 window alone and 71–73 per window
after.

Two readings fit, and this data does not choose between them — the Critic got
better at catching defects that previously shipped, or it got stricter about
things that were never defects. The near-flat downstream fix rate is weak evidence
for the first: if v2.x had been shipping an order of magnitude more real bugs, the
later windows should show a *falling* product-fix rate as that debt drained.

**Code is a minority of what gets written, and a shrinking one.** Per-window
shares of all lines produced:

| | code | test | governance | docs |
|---|---|---|---|---|
| v2.1 | 36.9% | 38.0% | 24.5% | 0.7% |
| v3.0 | 27.8% | 35.8% | 35.2% | 1.2% |
| v3.2 | 27.6% | 36.2% | 32.9% | 3.3% |
| v3.4 | 28.8% | 39.7% | 28.9% | 2.6% |
| v3.5 | 18.8% | 32.2% | 46.3% | 2.7% |

Tests are the largest single class in every window (32–45%). Code fell from 36.9%
to a stable 27.5–28.8% band across v3.0–v3.4, then to 18.8% in v3.5, where
governance reached 46.3% — within 5 points of code and tests *combined* (51.0%),
and its highest share on record. One 5.4-day window is not a trend, but it is the
figure to watch on the next run.

### Corroboration from a second consumer

Run against `../bankmachine` on the same day, so the framework version is the only
thing held in common:

```
series    runs   hours  %engaged  find/run  blk/run  blocking
v3.4       157    18.2      21.9      4.43     0.67       105
v3.5        64     6.2      19.7      2.25     0.41        26
```

Critic share of engaged time (19.7–21.9%) lands in the same band as discodon's
v3.2–v3.4 (18.3–20.7%), and the blocking rate per run is *higher* than discodon's
in both windows (0.67 and 0.41 against 0.37 and 0.37). A different product, a
different codebase, the same era: the blocking-rate rise is a framework-wide
property, not a discodon one.

---

## Three findings about the framework

1. **`prawduct-hook review-stats` pools Critic and PR reviews** under one `reviews`
   count and one duration total. Verified by arithmetic against discodon's full
   ledger: `review-stats` reports 1,318 reviews = 1,140 Critic + 178 PR, and its
   warning/note totals are exactly the two sets summed. 14.7% of that pooled
   duration is PR review, so a figure labelled "Critic hours" taken from it
   overstates Critic by 17.3%. The 2026-09-16 triage's per-repo "Hours" column is
   pooled on this basis — reproducing its discodon row needs critic+PR
   (665 runs / 98.2h against its published 651 / 96.1h, the residue being its
   earlier cutoff on the same day).
2. **The PR gate has never produced a blocking finding.** Across all 178 PR
   reviews in discodon's plugin era: 145 warnings, 262 notes, zero blocking. The
   scan returns non-zero on that field, so this is a real zero. Median PR open time
   is 11–65 seconds in every window through v3.4 and 4.6 minutes in v3.5 — review
   happens before the PR exists, and the PR itself is bookkeeping. Whatever the PR
   reviewer is worth, it is not gatekeeping.
3. **Learnings are written in one backfill, not continuously.** All 594 discodon
   `learning.written` events landed inside 12.8 minutes on 2026-09-18. Any
   per-window learning rate is an artifact of that day.

## What would change the picture

- **Separating Critic and PR hours in `review-stats`** would make every figure
  downstream of it comparable to this one. Until then the two sources disagree by
  construction and the disagreement looks like a measurement error.
- **A measured review duration** would retire caution 1 outright. The ledger
  already records `ts` at write time; a dispatch timestamp beside it would make
  the self-report checkable on every run rather than only in dense windows.
- **Re-running after the `consumer-overhead-2026-09` workstreams ship** is the
  point of committing this. The command above, same repos, and the `find/run` and
  `blk/run` columns are where a change in review economy would show.
