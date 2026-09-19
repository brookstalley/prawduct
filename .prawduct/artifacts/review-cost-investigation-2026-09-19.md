---
artifact: investigation
scope: review-cost
date: 2026-09-19
tracking: brookstalley/prawduct#167
---

# Why a small amount of work takes hours

> **Read #724 first — this is a third derivation, not a discovery.** The headline below
> (`verify-resolutions` is the largest addressable cost) was already filed on 2026-09-18 as
> **#724**, from a single-branch measurement, and again from a repo-wide scan of 1,020 reviews that
> produced **#830, #831, #832, #833** and sized **#167**. This document adds a whole-ledger
> derivation reaching the same number — which #724's own reconciliation note calls corroboration
> rather than duplication — plus two findings I did not see in that program: the **per-round cost
> trend** (§1) and the **missing aggregate budget** (§4).
>
> It was written without finding that program, because the search ran on "roster", "freshness" and
> "branch audit" and never on "verify-resolutions" or "review cost". That is the rule about
> searching the backlog before deriving, failed on vocabulary — and it is the meta-problem the
> document is about, biting the attempt to describe it.

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

> **CORRECTION, 2026-09-19 (#850 build, review-cost-decision Chunk 03).** That sum is wrong,
> because the payload is **stage-keyed and no reviewer loads all five files**. `SKILL.md` routes a
> `chunk` / `verify-resolutions` reviewer to `goals-1-3.md` and tells it to read *"nothing else —
> not the two files below"*; only `final` / `cumulative` opens the seven-goal protocol, the
> lifecycle table and the framework checks. Measured from the dispatch path rather than from this
> list: **inner 8,743 tokens, boundary 22,714** (the ~26k figure is the boundary payload, slightly
> over-counted). The distinction matters for the conclusion, not just the arithmetic —
> `verify-resolutions` is 58% of review volume and pays the SMALL one, so a single ceiling over the
> union would have priced a payload nobody loads while letting the inner stage double unnoticed.
> The control shipped is two stage-keyed ceilings: `tests/test_reviewer_payload_budget.py`, which
> derives its member list from `SKILL.md`'s routing prose so a sixth protocol file cannot join the
> dispatch without joining a sum. The growth claim in the table below is unaffected and stands.

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

## 5. The program that already exists, and where this fits

Filed 2026-09-18 from a repo-wide scan (1,020 reviews, 114h). **Read these before building
anything.**

| item | state | what |
|---|---|---|
| **#724** | open | the parent report. R1–R4, R7, R8 are unclaimed and still live there |
| **#831** | open | make fix/accept mechanical and SHOW THE ROUND COST at the decision |
| **#833** | open | bound "no pre-existing exception" and "deep context is a FIX signal" to blocking severity |
| **#830** | open | severity selects the CHANNEL — notes are 53% of findings and 0% of what gates |
| **#167** | open | refuse a full re-round when zero blocking remain (D3 unbuildable as written — see §5.1) |
| **#262** | open | aggregate review cost and yield across governed products |
| **#832** | **closed NOT_PLANNED** | suppress remedies on NOTEs — **declined deliberately**; do not re-propose |
| **#829** | shipped | verify-resolutions no longer emits new non-blocking findings (verified live 2026-09-19) |

**#832's closing reasoning is the steer for everything else here**, and it is the owner's: the lever
*"removes information rather than changing an incentive"*, and is *"satisfiable by rating WARNING
instead"*, which displaces work up a severity while every metric reads as success. Prefer levers
that **add cost information** over levers that suppress finding content.

## 5.1 Recommended sequence

**1. #831 — show the round cost at the decision.** The single largest avoidable cost measured
today. `cost-of-commit` already knows that the FIRST non-blocking fix on a judgeable file buys a
whole ~5-minute round and the next thirteen cost nothing — and that fact is invisible at the moment
the fix/accept call is made. On 2026-09-19 that call was made ~30 times across two branches without
it. It adds information rather than removing it, which is the direction #832's closure endorses.

**2. #833 — bound the over-fixing rules to blocking.** Pairs with #831 and is nearly free: #831
shows the price, #833 removes the pull. Both correct about blockers, both harmful about notes.
Note the constraint in its own Scope-out: these are ratified rules, so the amendment needs a
recorded decision and a witness that is not the amendment itself.

**3. Convergence — `fix/reviewer-rule-over-instance`, then #847.** 18% of verify rounds find a
BLOCKING finding, meaning the fix they verify is itself broken; that is what turns one round into
three. **#640 is CLOSED while its fix sits unmerged on that branch** (#843), and it is the
REPORTING half of #847's resolution half. Land the branch first — smallest of the four stranded,
and the prerequisite. Verified 2026-09-19: `rule-unenforced` appears nowhere on `develop`.

**4. #167 — needs a redesign, not a build.** Since `cdcac17d` a verify pass demotes everything
below BLOCKING into `observations`, so a clean anchor's `findings` is empty by construction and
D3's subset test can never fire (0 of 22 measured). The intent is right; the predicate is not.

**5. The aggregate payload ceiling (§4) — not in the program, filed separately.** Prevention, not
relief: it shrinks nothing today and stops 4.6x becoming 9x.

**Deliberately NOT first: the roster.** The ledger does not record roster size, and the yield figure
that would justify narrowing was measured on the fallback population, not the risk-surface
escalator. Instrument before acting. Counter-evidence worth keeping: on 2026-09-19 two reviewers of a
three-reviewer roster independently found the same defect from different goals with no visibility
into each other.

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
