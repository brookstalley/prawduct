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
> list: the cheap protocol route is a fraction of the full one (the ~26k figure is closest to the
> full-protocol payload, slightly over-counted). The distinction matters for the conclusion, not just the arithmetic —
> `verify-resolutions` is 58% of review volume and pays the SMALL one, so a single ceiling over the
> union would have priced a payload nobody loads while letting the inner stage double unnoticed.
> The control shipped is THREE ceilings keyed by ROUTE — `tests/test_reviewer_payload_budget.py`,
> which derives its member lists from `SKILL.md`'s routing prose so a protocol file cannot join the
> dispatch without joining a sum. Keyed by route rather than stage because `review-cycle.md` puts
> `final` in the inner stage while routing it to the full protocol, and because single-pass modes
> dispatch no subagent. The readings live in that module, dated; do not copy them here, since they
> moved once inside the bundle that introduced them. The growth claim in the table below is
> unaffected and stands.

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

---

## 8. Addendum, 2026-09-20 — the instrument, corrected

Measured the day after §1–§7, against the **evidence store** (`.git/prawduct/evidence.jsonl`, 966
review facts, 115.3h) rather than the governance ledger. Re-derive everything below with
`python3 .prawduct/research/review-cost-2026-09-20/verify_population.py` — the numbers live in that
script's output, not in this prose, and where the two disagree the script is right.

Nothing in §1–§7 is retracted. Both of its headline claims (§2's *41 of 83 scopes found zero
blocking*, §3's *18% of verify rounds find a blocking finding*) count **blocking** severity, and
blocking is never demoted — so both survive the correction below untouched.

### 8.1 Empty-rate trends are not comparable across 2026-09-16, and one was already circulating

A `verify-resolutions` pass demotes everything below BLOCKING into `observations`. That array
**began being written on 2026-09-16** — 0 facts carry it in July, 0 in August, 46 of 116 in
September. So a "produced nothing" rate computed from `findings` alone measures *when the field
started being populated*, not what reviewers found:

| month | verify rounds | no `findings` | carrying `observations` | truly empty |
|---|---|---|---|---|
| 2026-07 | 186 | 46 | 0 | 46 |
| 2026-08 | 300 | 170 | 0 | 170 |
| 2026-09 | 116 | 96 (83%) | 46 | **58 (50%)** |

A session note dated 2026-09-20 had already promoted the contaminated series — *"the zero-finding
rate is RISING: 26% (Jul) → 57% (Aug) → 84% (Sep); in September 81 of 97 verify rounds returned
nothing"* — as the measured case for the next intervention. 38 of those rounds returned content
that the demotion rule had moved one field over. **Read the table columnwise, never across rows.**

The same confound reverses a second reading. Splitting September at the 09-19 interventions shows
nothing-at-all falling 56% → 7% — which is not an effect, because 31% of pre-window facts carry the
`observations` array against 100% of post-window facts. Attributing that drop to #831/#833 would
have credited a recording change to a mechanism.

`telemetry.py:261-270` is not at fault and needs no change: it reports `observations` separately,
and distinguishes `None` ("not recorded") from `0` ("recorded, none demoted") on purpose. The tool
answered correctly; three consecutive consumer-side readings of it did not.

### 8.2 The clean window: 2026-09, the only month where the field is populated

| | rounds | clock | share of the month's 23.8h |
|---|---|---|---|
| verify-resolutions, total | 116 | 10.1h | 43% |
| — nothing at all | 58 | 4.6h | 19% |
| — observations only (nothing that gates) | 38 | 3.3h | 14% |
| — some finding | 20 | 2.2h | 9% |

**A third of all September review clock went to verify rounds that produced nothing which gates.**
That is the cost §2 identified, re-measured on an uncontaminated window, and it is real.

### 8.3 Two levers ruled out on measurement

**Delta size does not separate the wasteful rounds from the productive ones.** The 58 nothing-at-all
rounds spread evenly across delta sizes (14 at 1–2 files, 14 at 3–4, 18 at 5–9, 11 at 10+). Round
*cost* does scale with the delta (210s at one file → 520s at 20+), so the temptation is a size-keyed
refusal or discount — but there is no population for it to aim at. Combined with the already-recorded
result that marginal blocking yield does not decay by round index, **no observable feature of a
verify round predicts whether it will find anything.** That is the same wall #167 hit from the
evidence-strength side, reached independently from the population side.

**The roster question is not identifiable from observational data.** §5.1 deferred it for want of an
instrument and §7 recorded that roster size is not recorded. That is true of the ledger and **false
of the evidence store**, which carries `roster` on all 966 facts — so the question is askable. It
still cannot be answered: roster size is assigned with tier (158 of 178 three-reviewer cumulatives
are `escalate`), with diff size (median 19 files against 8), and with calendar month, all at once.
The one tier-and-size-matched cell holds n=5 and sits entirely in 2026-07. Settling this needs a
**randomised roster on standard-tier cumulative**, not a further scan. Filing that as an experiment
is a real option; another measurement pass is not.

### 8.4 What this changes about the next act

Every remaining lever in §5.1's sequence has now either shipped (#831, #833, #829, the route-keyed
payload ceilings), been withdrawn after review (#167, 2026-09-20 — advisory-strength evidence used
for authority), or been ruled out above. The three that shipped all act on the **fix/accept
decision** rather than on the round, and they landed on 2026-09-19 and 2026-09-20 — which is 15
verify rounds of post-intervention data, confounded as §8.1 shows.

So the honest next act is **a measurement window, not a fourth mechanism**: let the shipped
interventions accumulate a population that the corrected instrument can read, and re-run the script
above. Designing another lever now would be designing against a number nobody can yet compute.

### 8.5 What this addendum cannot say

- **The pre-2026-09-16 "truly empty" counts are overstated by an unknown amount** — rounds that
  produced only observations are indistinguishable there from rounds that produced nothing, so the
  46 and 170 above are upper bounds. The *level* in September is measured; the *trend* into it
  is not recoverable.
- **"Produced nothing that gates" is not "was not worth running."** A verify round that confirms a
  fix is correct has done its job; the argument here is about how many of them the coverage model
  requires, never about whether any given one was sound.
- **n=15 post-intervention.** Nothing in §8.4 is an effect estimate; it is a statement that the
  effect is not yet estimable.
