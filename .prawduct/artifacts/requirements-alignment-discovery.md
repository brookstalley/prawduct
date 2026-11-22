---
artifact: discovery
scope: requirements-alignment
depends_on:
  - artifact: nonfunctional-requirements   # Direction: review wall-clock P0; new controls emit their yield
---

# Discovery: Aligning Agent and Owner on Goals

## Goals

**Product.** An owner hands work to an agent, including long autonomous runs while they are away,
and comes back to what they meant. Every clarification the work needs is asked together, up front,
before a plan is written. The owner welcomes questions; what they cannot afford is a six-hour build
that stops every fifteen minutes. Questions will still arise during implementation, and prawduct's
job then is to make sure the agent has enough context to answer them well itself.

Owners using prawduct want great, scalable, long-lived products, so an agent deciding on its own
favours the **most durable** choice, not the most reversible one:

1. **Do it right.**
2. **Do it in line with the product's other choices** at the product, architecture, and technology
   levels, including the backlog. Backlog items are the richest record of where the product is
   going.
3. **Stop and ask only when the stakes really are high**: the choice is irreversible, spends real
   money, takes on large tech debt, or costs work out of proportion to its benefit.

**Before building is the one place for an explicit clarify, ask, or acknowledge.** Ceremony is
still to be avoided there.

**Architecture.** Three properties have to hold for that:

1. *Goals outlive the session.* Every session starts cold. Today an agent mid-build reconstructs
   intent from plans and briefs that an earlier agent wrote, which is how an inference becomes an
   "owner ruling" a week later. What the owner wants, and why, has to be written down where the
   building agent reads it.
2. *The owner's words stay distinguishable from the agent's inferences*, wherever goals are
   recorded. This is natural language ("you said…", "I'm assuming…"), not a schema.
3. *Goals reach every decision point*: when the plan is written, when the agent decides something
   mid-build, and when the work is reviewed. Today the Critic reviews against the plan, so a plan
   that faithfully implements a misread goal passes.

**Implementation.** Deliberately open until the design below is confirmed. The five backlog items
filed from the audit (#970–#974) are fixes for symptoms; they get re-cut against this design rather
than built as filed.

## Audience

Owners in general, but expert ones, at roughly this owner's depth in product management,
requirements, and engineering. They write terse, high-context requests and want autonomy, not
tutoring. The agent's job is to surface its own reading and the forks in it, not to teach.
**Near-term and North Star coincide here**; a novice-owner mode is not a goal.

## Constraints

- **The session digest is full** (about 9,500 characters of a 10,000 wall). Anything every
  repo must see is paid for by rewriting what is there, not by adding.
- **Review wall-clock is a P0 norm**, and **every new control must emit observable yield**
  (`nonfunctional-requirements.md` § Direction). A new review round per plan is a cost to justify,
  not a default.
- **Mechanical work must not get slower.** A bug with a repro, "continue", or a PR operation gets
  no new step.
- **The owner is often away while work runs.** Nothing may depend on them answering mid-build.
- **Natural language over schema.** Agents reason well over a sentence like "home use for now,
  thousands of anonymous users eventually" and badly over fields filled because a slot existed.
  Structure goes only where a mechanism must read it.

## Why: the evidence

Measured 2026-10-08 over Claude Code transcripts since 2025-09 (960 owner requests across 17
projects; data and extraction scripts outside git at `.prawduct/.req-audit-2026-10-08/`).

The rework the audit found sorts by the level where alignment broke, and it is almost never the
level prawduct reviews:

| Level | Example |
|---|---|
| Product | postarr: who uses it and where was never asked, so a public feed for up to 1,000 Apple TVs came up only when the owner raised it |
| Architecture | prawduct's core.md: the goal (an index) was lost when the work became "a 16KB byte cap" |
| Constraints | puzzles: an example in a reference image became the rule "round ends". samsung: the agent invented a spending cap and wrote it into the brief |
| Implementation | rarely. This is what the Critic is built to catch |

Other measurements: agents asked before building on 24 of 138 substantive governed requests. Of
286 questions asked, 158 were about process or design choices, and about a quarter of the
requirements questions came up mid-build. In 22 sampled underspecified requests, 9 led to rework,
each traced to an inference the owner never saw.

Framework causes (source checked 2026-10-09):
- Discovery's feature-level "three questions" are product-level only, answered after the agent has
  decided what it is building.
- The asking bar leans against the owner ("Infer aggressively"; ask only when "consequential and
  genuinely unverifiable"; Principle 20's cost-of-asking sentence).
- The "Before Building" check exists only in this repo's CLAUDE.md, never in a product repo.
- `[ASSUMPTION … | user can override]` has no answered state.
- `scope.accommodate`, the North Star tier, is written at discovery and read by nothing.

## Proposed Design (for owner confirmation)

**An alignment pass before building.** Before substantial work, the agent judges two things: how
clear the goals already are, from the request, the brief, and the backlog, and how much work and
risk lie ahead. It then takes one of four responses and **always says which one, in a line**,
because the acknowledgement is how the owner catches a misreading before it is built:

| Situation | Response |
|---|---|
| Clear by nature, however large: a mechanical bug fix where the bug and its repro define success | **Proceed.** Restate the target in a sentence and go. |
| A backlog item or spec already answers the goal and requirement questions | **Proceed, citing it.** Restate the goals from the item, name anything it leaves open and the inference made there, and go. |
| Mostly clear, but a high-level goal or a key architecture choice is missing | **Ask, in one batch.** Lead with the agent's own reading, so the owner corrects rather than authors. |
| A lot of work, and the goals or requirements are not understood | **Hold up.** "This is a lot of work and I don't understand the goals yet. Shall we discuss, or do you want me to use best judgment?" |

- **The written form scales with the response.** A sentence for Proceed. For Ask or Hold up, a
  short statement of the goals at the product and architecture levels, the constraints, and the
  tradeoffs the agent would accept, saying plainly what the owner said and what the agent is
  inferring. A page of goals is quicker to correct than a plan, and a plan quicker than code.
- **Best judgment is a legitimate answer to Hold up.** When the owner chooses it, the agent
  proceeds with its inferences written down, and the boundary review puts them in front of the
  owner.
- **The goals persist as the plan's opening**, so a cold session mid-build reads them before the
  chunks. The product's near-term and North Star live once in the brief, in prose, and every
  pass cites them.
- **Mid-build, the agent decides rather than asks.** It applies the durable-choice order in Goals
  above and records the decision in one line, naming the goal or prior choice that settled it.
  It stops only for the high-stakes cases listed there. A decision the goals didn't settle
  counts as a miss by the alignment pass, and gets flagged for the boundary.
- **The boundary review judges against the goals**, not only the plan. It lists the agent's
  mid-build decisions for the owner, and it treats a goal that was inferred and never put to the
  owner as a finding.
- **Yield is the owner's own two measures**, taken from transcripts: questions that interrupted a
  build, and owner corrections after one. The audit script measures both today, which satisfies
  the norm requiring every new control to emit observable yield, without adding a new ledger kind.

**What becomes of the filed items:**
- **#972** (plan template) becomes the plan's goals opening.
- **#970** (provenance) is absorbed into the pass's said-versus-inferred language. It no longer
  needs a tag schema.
- **#971** (intake in every repo) becomes a rewrite of the digest's rigor paragraph that points at
  the pass.
- **#973** (North Star) becomes near-term and North Star in prose, in the brief, cited by every
  pass.
- **#974** (brief coherence) stays, because the brief is the product-level goals statement and
  must not contradict itself.
- **New: the Critic reviews against goals.**

## Settled 2026-10-09

The owner approved this design with the two corrections above: choose the most durable option,
not the most reversible, and use the four responses for latitude before building. Two of the
agent's proposals were not contested:

- The pass is triggered by any substantial request, not only by work that has a plan. The four
  responses keep it cheap where the work is clear.
- A mid-build decision that went against the owner's intent is a miss by the alignment pass, and
  it feeds reflection. It is the main signal for improving the pass.

## Yield re-run 2026-11

Run 2026-11-22 for #981, two days after the planned date, on the owner's ruling of that day. The
after-windows end `--until 2026-11-22`, which includes 2026-11-21, so they use every transcript on
disk. Each comparison also gives the `--until 2026-11-20` run the item specified. The two agree to
within a few tenths of a point, and the verdict rests on neither alone.

**Script.** Every window was run at blob `2b4635842c9a34379fec7fc395d55171383a3445`
(`git rev-parse HEAD:tools/measure-alignment-yield.py` at develop `8b1847e2`), with
`python3 -I tools/measure-alignment-yield.py … --json`, the default glob
`~/.claude*/projects/*/*.jsonl`, and the default `--min-chars 60`. The baseline counters
(`requests`, `substantive`, `asked_first`, `mid_build_asks`, `corrections`) count the same way at
this blob as at `cfe1bb3d`, the commit that carried the measure when the baseline was read. Since
then the script has only gained `goal_questions`. The recorded baseline was read with the default
glob, so it covered every config directory, as this run does. Which of the two 2026-10-09 commits
produced the recorded figures is not recorded.

### Health (read before any rate)

| Run | transcripts | lines_unparsed | turns_without_timestamp | transcripts_unreadable | transcripts_without_owner_turns |
|---|---|---|---|---|---|
| every window | 1016 | 0 | 0 | 0 | 94 |

The script tallies health over every transcript it opens, whatever the window, so every run prints
the same line: `health: transcripts_without_owner_turns 94`. Step 2's per-window comparison
therefore cannot be read off the script's output. Bucketing transcripts by their first timestamp
gives the per-window rates. Before 2026-10-09: 53 of 451 transcripts had no owner turns (0.118).
From 2026-10-09 to 2026-11-22: 32 of 545 (0.059). The after-window rate is half the baseline's,
not twice it, so step 2 does not call for a parser fix.

Health missed one parser fault, which turned up only when the leads were read by hand. Claude
Code's compaction summary ("This session is being continued from a previous conversation…",
flagged `isCompactSummary`) arrives as a user record. The script counts it as an owner request.
The after-window holds 52 of them and the baseline window none. They make up 26 of the 44
after-window correction leads (26 of the 39 ending 2026-11-20) and 20 of the 992 substantive
requests. The script was not changed. The figures below are the script's, and the compaction-excluded
figures are given beside them, computed in scratch by importing the pinned script and filtering
those records.

### Baseline check: pruned

`python3 -I tools/measure-alignment-yield.py --until 2026-10-09 --json`, governed total: 1752
requests, **442 substantive** (recorded 963, 54% fewer), 68 asked first, 121 mid-build asks, 7
correction leads.

The shortfall is far beyond the 5% limit. Transcripts were pruned. Claude Code's default 30-day
retention has cleared every config directory except one that has been idle since August. Only that
directory's July and August transcripts are left for the baseline window. From September to
2026-10-15, three user records survive, all on one day. So the primary comparison is against the **recorded**
figures (140 / 963 / 349 / 18), as step 3 directs. The surviving July and August subset is shown
next to them. It is not like-with-like: different months and a different mix of projects.

### Alignment pass (step 4)

Commands: `--until 2026-10-09` against `--since 2026-10-09 --until 2026-11-22` (and
`--until 2026-11-20`). Governed totals:

| Window | substantive | asked_first | mid_build_asks | correction leads | genuine on reading |
|---|---|---|---|---|---|
| Recorded baseline (read 2026-10-09) | 963 | 140 | 349 | 18 | not recorded |
| Surviving baseline (read today) | 442 | 68 | 121 | 7 | 3 (+1 borderline) |
| 2026-10-09 to 11-22 | 992 | 32 | 170 | 44 | 3 (+2 borderline) |
| 2026-10-09 to 11-20 | 923 | 28 | 159 | 39 | 3 (+2 borderline) |
| 2026-10-09 to 11-22, compaction excluded | 972 | 32 | 170 | 18 | 3 (+2 borderline) |

| Rate | Recorded | Surviving | After to 11-22 | After to 11-20 | Change against recorded / surviving (to 11-22) |
|---|---|---|---|---|---|
| asked-first (`asked_first / substantive`) | 14.5% | 15.4% | 3.2% | 3.0% | −11.3 / −12.2 points |
| mid-build asks per 100 substantive | 36.2 | 27.4 | 17.1 | 17.2 | −53% / −37% |
| correction leads per 100 (raw) | 1.87 | 1.58 | 4.44 | 4.23 | +137% / +181%, mostly compaction summaries |
| corrections per 100, genuine on reading | — | 0.68 | 0.30 | 0.33 | — / −56%, on 3 cases against 3 |

**How the correction leads were read.** A lead counts as genuine when the owner says the work the
agent just built or proposed is wrong and must change. Examples: a wrong default the agent ran on,
an output whose form misses the brief, a diagram element placed wrong, a design balance the owner
rejects. A lead is false when the matched word does other work: the owner correcting themselves
("I was wrong"), a hedge ("correct me if I'm wrong"), a product-behaviour bug report, an
instruction ("don't revert", "bring undo back"), or a compaction summary narrating the agent's own
earlier errors. Borderline means the owner disputes a factual claim or a sentence the agent wrote,
not built work. Surviving baseline: 3 genuine, 1 borderline (a dropped scope item) and 3 false, of
7 leads. After to 11-22: 3 genuine, 2 borderline and 39 false (26 of them compaction summaries), of
44. All five genuine-or-borderline after-window leads fall before 2026-11-20.

### Goal grounding (step 5)

Commands: `--since 2026-10-09 --until 2026-10-22` against `--since 2026-10-22 --until 2026-11-22`
(and `--until 2026-11-20`).

| Window | requests | goal_questions | per 100 requests |
|---|---|---|---|
| 2026-10-09 to 10-22 | 15 | 0 | — (pruning left 15 requests) |
| 2026-10-22 to 11-22 | 2855 | 1 | 0.035 |
| 2026-10-22 to 11-20 | 2658 | 0 | 0 |
| For context, before 2026-10-09 (surviving) | 1752 | 1 | 0.057 |

Pruning emptied the pre-change window, so step 5's comparison cannot be made. Both hits were read
by hand, the 2026-11-21 one and the July one in the surviving baseline. Both are genuine: in each,
the owner, in a product repo, asks the agent to step back and make sure the work's aim is
understood before going on. One hit in about 2,900 requests after the change is too few to show
anything either way.

### Verdict

**Moved, by the letter of the criterion, but the evidence is weak.** Mid-build asks per 100
substantive fell 53% against the recorded baseline, and 37% against the surviving one, past the
20% bar. The rise in asked-first that the pass exists for did not happen: it fell about 11 points,
from 14.5% to 3.2%. Genuine corrections per 100 also fell, but on 3 cases against 3, which shows
nothing. Three things undercut the reading:

1. **The agent asks less overall, not only less mid-build.** AskUserQuestion calls per 100
   substantive (asked first plus mid-build) were 50.8 recorded, 42.8 surviving, and 20.4 after. A
   cruder scratch lead counts turns that built nothing and ended on a question the owner answered
   before a build. It too fell, from 25.6 to 13.4 per 100 substantive. So the pass's "ask in one
   batch" is not showing up as asking in prose instead. The fall in interruptions matches the
   pass's "decide well alone" half. Its "ask up front" half is not visible in these figures.
2. **The baseline is pruned,** so the comparison is with recorded totals from a window this run
   cannot re-read, and the after-window's mix of projects is not the baseline's.
3. **Correction leads are polluted by compaction summaries** in the after-window. Excluding them,
   the raw lead rate is 1.85 per 100, level with the recorded 1.87.

The owner-side outcome is the favourable reading: interruptions roughly halved and genuine
corrections did not rise. Whether the asked-first collapse means the pass needs reworking is the
owner's call. The criterion as written does not require a rework item.

Measurement follow-up: the script counts `isCompactSummary` records as owner turns, and it tallies
health over all transcripts rather than per window. Transcript retention also prunes any baseline
older than 30 days, so the next re-run should snapshot its baseline counts, or the transcripts,
when the baseline is first read.
