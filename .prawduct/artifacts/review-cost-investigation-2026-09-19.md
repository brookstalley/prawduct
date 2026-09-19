---
artifact: investigation
scope: review-cost
date: 2026-09-19
tracking: brookstalley/prawduct#167
---

# Why a small amount of work takes hours

Measured 2026-09-19 from `.prawduct/.governance-ledger.jsonl` after a session in which landing two
finished branches took ~3 hours. Every figure below re-derives from that ledger; the commands are in
§6 so nothing here has to be trusted.

## 1. The headline

**911 Critic reviews, 101 hours, 313 blocking findings — 19.4 minutes per blocking finding.**

Per-round cost has risen every month since June, monotonically, and no intervention has touched it:

| month | rounds/scope | min/round |
|---|---|---|
| 2026-06 | 3.7 | **4.8** |
| 2026-07 | 4.8 | **5.8** |
| 2026-08 | 8.1 | **7.4** |
| 2026-09 | 4.7 | **7.6** |

Rounds-per-scope spiked in August and came back down — the review-stages work paying off. Nothing
has addressed the per-round cost, which is +58% since June.

## 2. The dominant lever is `verify-resolutions`, not the roster

| mode | n | min/rev | blocking/rev | **min per blocking finding** |
|---|---|---|---|---|
| `chunk` | 108 | 4.8 | 0.47 | **10.2** |
| `cumulative` | 219 | 11.3 | 0.63 | **17.9** |
| `final` | 51 | 7.8 | 0.41 | 19.0 |
| `verify-resolutions` | **533** | 5.0 | **0.19** | **26.3** |

`verify-resolutions` is **58% of all review volume at the worst yield of any mode**. Concentration is
severe: 490 verify rounds across 83 scopes, and the top twelve scopes burned **~30 hours** between
them — one spent **27 verify rounds to find 4 blocking findings**.

**41 of the 83 scopes with two or more verify rounds found ZERO blocking findings across all of
them.** Half of the repeat-verify population is pure cost.

**Why the volume exists.** `verify-resolutions` is mostly a *coverage-bookkeeping* mechanism, not a
review: every judgeable fix commit reopens `check-cumulative-critic`, and the cheapest thing that
closes it again is priced as a full review round. The round is bought to extend a fact, not because
anyone judged that review was needed.

## 3. The loop driver: fixes are defective 18% of the time

**95 of 533 verify rounds (18%) found at least one BLOCKING finding** — meaning the fix they were
verifying was itself broken. That is what turns one round into three.

**23% of all findings (943 of 4,084) invoke a class / every-site framing.** Today's branch hit the
specific shape three consecutive rounds: a CLASS finding, closed at the instance the review named.
Round 4 found two blocking in round 3's fix; round 5 found one in round 4's; round 6 was needed to
confirm. Each one was a finding that had *enumerated its own members* and been fixed at fewer of
them than it listed.

This is the cheapest thing to attack, because the failure has a name, a tell, and a mechanical
remedy.

## 4. Per-round cost: per-file budgets, no aggregate

A Critic reviewer reads **~112 KB / ~26k tokens of governance prose before it sees one line of
diff**: `review-cycle.md` (11,105 tokens), `review-protocol.md` (4,312), `SKILL.md` (3,649),
`goals-1-3.md` (2,609), `framework-checks.md` (1,116), plus the agent definition.

Every one of those files carries a token budget and every budget is green. **Nothing prices the
sum:**

| month | budgeted files | total tokens |
|---|---|---|
| 2026-07 | 3 | 10,214 |
| 2026-08 | 10 | 42,349 |
| 2026-09 | 11 | **46,964 (4.6x)** |

There is an aggregate assertion for the injected *session* shape. There is none for what a reviewer
reads. So every raise is scrutinised individually and approved on its merits — this session added
one, `core.md` 100→102 KB, with a carefully argued reason — while the sum quadruples and no gate
ever sees it. That is why "it keeps getting slower" is true and why no single decision looks wrong.

## 5. Interventions, ranked by measured size

**A. Make a class finding's members mechanical (cheapest, attacks the 18%).**
23% of findings are class-shaped and they are what produce consecutive rounds. Candidate: a class
finding must carry its members as a checkable list, and the verify pass grades *each member* rather
than the instance. Today that would have collapsed rounds 3, 4 and 5 into one.

**B. #167 — refuse a full re-round when zero blocking findings remain (biggest volume lever).**
Already filed, at `stage: design`, and it targets exactly the 58%. **It is blocked on a design flaw
already recorded upstream:** since `cdcac17d` a verify pass demotes everything below BLOCKING into
`observations`, so a clean anchor's `findings` is empty *by construction* and D3's subset test can
never fire — measured 0 of 22 post-2026-09-16 rounds. The intent is right; the predicate needs
redesigning against the current demotion behaviour. **Do not build D3 as written.**

**C. An aggregate ceiling on the reviewer payload.**
Stops 4.6x becoming 9x. Does not shrink anything today, so it is prevention rather than relief. It
is a maintainer-side cap on our own prose whose purpose is to remove cost, not the consumer-facing
kind of tax the 2026-09-19 ruling refused.

**D. Roster narrowing — smaller than it looked, and currently unmeasurable.**
The ledger does not record roster size. The only proxy (`likely_duplicate_groups`, which populates
only when duplicates are found) gives a LOWER BOUND of 50 of 219 cumulatives. The 0.55-vs-0.78
yield figure in `plugin/CHANGELOG.md` was measured on the **fallback** population, not the
risk-surface escalator that fires on this repo. **Instrument roster size first; do not act on the
fallback measurement.**

## 6. Re-derive everything here

```
prawduct-hook review-stats
python3 - <<'PY'   # per-mode yield, concentration, and the 18%
import json, pathlib, collections
rows=[json.loads(l) for l in pathlib.Path(".prawduct/.governance-ledger.jsonl").read_text().splitlines() if l.strip()]
rev=[r for r in rows if r.get("event")=="review.critic"]
# ... group by (review.mode), sum duration_seconds, count severity=="blocking"
PY
```

## 7. What this measurement CANNOT say

- **Roster size is not recorded.** Every claim about three-reviewer cost is inference (§5D).
- **Durations mix measured and self-reported.** The code-read clock reached `review.pr` on
  2026-09-18 and `review.critic` on 2026-09-19; everything before is the reviewing model's
  recollection, and 23% of those are exactly `300`. Trends across months are therefore directional,
  not precise. `review-stats` reports the two populations separately for this reason.
- **"Blocking finding" is self-rated severity**, not defects that would have shipped. A mode with
  low blocking/rev may be catching things reviewers correctly rate lower, not finding nothing.
- **Yield per minute is not value per minute.** The three rounds this branch spent on a class
  finding found real defects each time; the argument is that ONE round should have found them.
