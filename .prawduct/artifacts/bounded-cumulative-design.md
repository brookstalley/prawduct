---
artifact: design
scope: bounded-cumulative
drawn: 2026-09-22
status: decisions recorded 2026-09-22 (owner) — NOT to be built until the data is in: #885 and the ~2-week consumer re-baseline
parent: .prawduct/artifacts/cumulative-latency-discovery.md (driver 1)
---

# Bounded repeat cumulative (lever 1)

## Problem

A `cumulative` review always spans merge-base → HEAD (`critic_consolidate.begin_review`, the
`cumulative` branch). A long-lived branch that runs several cumulatives re-reviews the whole bundle
each time. On discodon's `eval-campaigns` branch, three cumulatives in five hours all used base
`9aa8135`. They covered 70, then 110, then 128 subject files. Only 65, 56 and 35 of those files had
changed since the previous cumulative. The discovery found that span size accounts for most of
discodon's roster-3 gap (driver 1). The reviewer's output tokens grow with the span, and wall
clock follows output tokens at R² 0.98.

**Success:** a repeat cumulative on an unchanged base rates only what changed since the last
cumulative, at full boundary rigor. The PR gate's verdict does not change, and the loss of
cross-chunk findings is small and measured rather than assumed.

**Out of scope:** driver 2 (shipped as lever 2, #886), driver 3's auto-loaded context (#652),
the first cumulative on a branch, and the base-advanced case (see Decision 4).

## What already exists, and why this is not `extends_cumulative` again

The v2 `extends_cumulative` chain (#466, deleted under #418 in the kernel-v3 cutover) was **gate**
machinery. It let the PR gate accept a cumulative plus a verify-resolutions chain. The evidence
store replaced it, because coverage now composes any review facts by tree. That composition is
also why this design needs no gate change. A fact over `T1 → HEAD` composes with the prior
cumulative's fact over `base → T1`. `coverage_algebra.review_edges` accepts it as long as every
judgeable file in its `files_changed` is in its `files_reviewed`, which holds by construction when
both are the delta.

What is missing is at **dispatch**: `begin_review` always sets the cumulative interval to the whole
branch, even when a boundary review already rated most of it. The builder cannot avoid this.
Discodon's three slow rows were `explicit-args` dispatches at chunks 11 and 11c. Many of its
earlier repeats were `rule-2` inferences. Each was a correct request for a boundary review, and
each paid for the whole span.

## Measured trade (dated reading, 2026-09-22)

Method: for every cumulative in the ledger, find the most recent earlier cumulative whose reviewed
commit is an ancestor of this one. Then split this review's findings by file location: **delta** (touches a file
changed since the earlier cumulative), **old-only** (touches only files the earlier one already
rated) or **no files**. Old-only is the set a bounded review would not have had as subject. This
reading was taken with an ad-hoc script. Chunk 1 below lands it as a tool, and until then these
digits cannot be re-derived.

| repo | repeat cumulatives | same base as prior | subject files → delta files (same base) | blocking: delta / old-only | warning: delta / old-only |
|---|---|---|---|---|---|
| discodon | 300 | 93 | 4292 → 2413 (−44%) | 135 / 7 | 1699 / 193 |
| bankmachine | 67 | 28 | 772 → 415 (−46%) | 47 / 11 | 273 / 63 |
| prawduct | 220 | 66 | 2227 → 1505 (−32%) | 135 / 15 | 1101 / 107 |

The finding counts cover every repeat row, not only the same-base ones. Restricted to the same
base, blocking old-only is 3 of 54 on discodon, 7 of 25 on bankmachine and 3 of 35 on prawduct.

The 33 old-only BLOCKING findings, read one by one, fall into three classes:

| class | n | example | kept by this design? |
|---|---|---|---|
| Machine relay (record-lint, test evidence, change-log presence, learnings budget) | 20 | `record-lint: chunk-ref-missing` on a plan the delta did not touch | **Yes.** Record-lint keeps grading the whole bundle (Decision 3) |
| Stale prose: the delta changed behaviour, and an earlier-changed file still describes the old one | 9 | *principles.md still teaches `chunks=`*; *README still routes the key backup through shell history* | **Mostly.** The interaction sweep (Decision 2) targets exactly this |
| Code that an earlier cumulative already saw | 4 | *tests/spikes still imports the deleted `lib.views`*; *compare_digest sweep incomplete* | Partly. One is delta-caused and sweepable; the others are a second look at old code |

So the expected BLOCKING loss is about 4 in 355 (about 1%), and part of that was a re-sample of
code the earlier cumulative had passed. Warnings lose more: 9–19% sat on old-only files. Those
are advisory at the PR gate.

**Limits of this measure.** Location is a proxy. A bounded reviewer still reads old files as
oracle and may raise the same finding from there. A delta finding may also have needed the whole
bundle in view to be seen. The wall-clock saving is **not** predicted here: the discovery's fits
link output tokens to files sublinearly (r 0.62) and cannot turn 128 → 35 files into seconds. That
measurement is Chunk 4's job.

## Design

### The anchor: the boundary frontier

`critic-begin --mode cumulative` looks for a **boundary frontier**. This is the newest review fact
that meets all of the following:

1. It has `stage == boundary`, which today means mode `cumulative`.
2. Its `base_tree` equals the current merge-base tree (`coverage.resolve_merge_base_tree`), so the
   base has not moved.
3. Its `head_commit` is an ancestor of HEAD. This is the same lineage guard as verify-resolutions
   (#288), for the same reason: the store is shared across worktrees.
4. Its `head_tree` differs from HEAD's tree. If it does not, the bundle is already
   boundary-reviewed and today's behaviour stands.
5. `coverage_verdict(merge_base_tree → head_tree)` is `covered`, with no unresolved blocker at or
   before the frontier.

Condition 5 keeps the full span as the only route around a **superseded** blocker. The gate
messages already point there: "only a spanning cumulative can clear them" (`gates.py`, the
superseded-remedy text). If the path to the frontier is not clean, the dispatch falls back to a
full span, and the builder's instruction stays true without any change to that text.

When a frontier exists, the interval is `frontier.head_tree → HEAD tree`. Otherwise the interval is
merge-base → HEAD, as today. The manifest and the fact record `span: bounded | full`, plus
`bounded_from: <fact id>` when bounded, so review-stats and the ledger can split the two.

### What the reviewer gets

- **Subject:** judgeable files changed in the delta. `files_changed` holds the delta only, which
  keeps the edge valid.
- **Oracle:** the delta's own oracle, plus every other file the bundle (merge-base → HEAD) changed.
  The reviewer reads these and does not rate them.
- **Protocol:** `review-protocol.md`, all seven goals, boundary severities. That is unchanged.
- **One addition, bounded mode only (Decision 2):** an interaction sweep, described in the next
  section. Its hits are rated even when the file is outside the subject set, an exception to the
  findings-eligible contract.

### The interaction sweep: a text search computed in code, not a call graph

The owner's concern with Decision 2 was cost and reach. Mapping callers in a large app is slow, and
in a dynamic LLM app the "call" is often configuration: a tool name in YAML or in a prompt, with no
code path to follow. So the sweep does not map calls:

1. **`critic-begin` computes it**, the way it already computes record-lint, and relays the answer
   in the manifest. The reviewer reads a hit list. It does not go exploring.
2. **Vanished tokens.** It takes the identifiers and string literals on the delta's removed lines
   that no longer appear anywhere in those files at HEAD. Those are names the delta retired or
   renamed.
3. **One `git grep -F` per token over the whole tree**, in any file type. It is plain text search,
   so it finds a tool name in config, a prompt template or a README as easily as in code. That
   makes it a better fit for dynamic apps than call analysis, not a worse one.
4. **Capped.** It uses a fixed token budget and a fixed hit budget. Past either cap, the manifest
   says "wide reach: N sites for `token`" and the reviewer records one observation instead of
   reading every site. Cost is bounded by the delta, not by the app's size.

**What it cannot see:** a behaviour change under an unchanged name. *"The Critic skill still
instructs agents that /clear sweeps the marker"* retired no token. That class stays with reviewer
judgment, limited to prose that mentions a name the delta touched. How many of the nine stale-prose
losses a vanished-token scan would have caught is **not measured**. Chunk 1 replays the scan on
them. If it catches few, Decision 2 reopens before any build.

For comparison, today's full-span cumulative, by its stated contract, does not rate files outside the bundle at all. A
stale tool name in config that the branch never touched is missed now too. The sweep adds reach
the full span lacks. It does not only make up for what bounding gives away.

### Unchanged

The PR gate (`check-cumulative-critic`), the Stop gate, composition, mode inference (a bounded
cumulative is still `cumulative`, so `boundary_review_on_chain` and rule 2 read it as before),
verify-resolutions, the base-advance transfer, and the PR reviewer. The PR reviewer still reads
the whole bundle once, at PR time, but for release readiness, not the code goals.

## Decisions (owner, 2026-09-22)

All six were decided as recommended. Decision 2 was approved with the cost and reach concern that
the section above answers. Decision 4 came with a question, answered under it. Decision 6 was
restated as app policy.

1. **Default or opt-in?** **Default-on.**, with an explicit override (`/prawduct:critic
   cumulative full` → `explicit-args` rationale) for a builder who wants a fresh whole-bundle look.
   An opt-in lever saves nothing unless someone remembers to use it, and `rule-2` inference
   dispatches cumulatives with nobody there to ask.
2. **The interaction sweep: rated, or advisory?** **Rated**, computed as above (findings eligible on any file
   it reaches), because the stale-prose class is 9 of the 33 losses and a blocker in it is
   still real. The risk is that it grows back into a whole-bundle review. The sweep is scoped to
   what the delta changed, so its size tracks the delta. **Rated means amending a stated contract:**
   `SKILL.md` step 5 and `review-cycle.md` § Evidence and Composition say `files_reviewed` is the
   findings-eligible set and `files_oracle` is "read, not rated". The sweep would be a named
   exception to that. It would not widen `files_reviewed`, which prices the edge. The advisory
   alternative keeps the contract and turns these losses into observations.
3. **Record-lint's span.** **It keeps grading merge-base → HEAD** while the review is
   bounded. It is machine work that costs no reviewer tokens, and it produced 20 of the 33
   old-only blockers.
4. **Base advanced since the frontier.** **Full span in v1.** It was 25 of 118 real discodon
   repeats. The delta `T1 → HEAD` then includes the base's own changes, which are not this
   branch's work.

   *Owner's question: can this be reduced without losing quality?* Yes, by applying a rule the repo
   has already ratified one file at a time. `coverage.diagnose_base_advance_transfer` grants a
   whole span with no review when the branch's own diff is byte-identical across the advance and
   the suite has run on the new tree. The per-file version splits the branch's judgeable files
   into two sets:
   - **Transferred:** the branch's patch for the file is byte-identical to the one the frontier
     rated (same blob at HEAD and T1, same blob at the old and new base). This is exactly what the
     transfer already accepts.
   - **Subject:** everything else. That covers new work since T1, conflict resolutions, and every
     file the base advance also touched. Those overlap files are where semantic merge conflicts
     sit, so this is stricter than the transfer.

   Interaction between the advance and disjoint branch files is priced the way the transfer prices
   it: by the suite on the new tree, not by a review. A full re-read of an unchanged patch would not
   catch it either.

   **The cost is a gate change**, and that is why it is v2. `review_edges` requires every judgeable
   changed file to be in `files_reviewed`. So the fact needs a `files_transferred` set that
   composition accepts only when the byte conditions can be re-checked from trees the fact
   records. Deciding whether it is worth building needs the overlap rate on real advances, which
   the Chunk 1 tool can report.
5. **Roster.** **Derived from the delta**, as `_derive_roster` would with the bounded
   `files_changed`. A risk surface touched earlier was already boundary-reviewed with the larger
   roster. This saves more only when the delta has fewer than 12 judgeable files and touches no
   risk surface: discodon's 35-file delta would still get three reviewers.
6. **A forced full span before the PR?** **No. That is app policy, not framework policy.** The
   framework ships the `full` override. A product that wants a whole-branch review, for example as
   part of its develop → main promotion, can require it in its own process. Chunk 4's yield
   comparison is still how the framework default gets revisited.

## Build shape (not yet: waits on #885 and the re-baseline)

1. **Measurement tool.** `tools/measure-repeat-cumulative-yield.py` with tests, which is the
   script behind the table above. It lands first so the before-numbers are re-derivable. It also
   reports two things the decisions above depend on: whether a vanished-token scan would have
   caught each of the nine stale-prose losses (Decision 2), and the file-overlap rate on
   base-advanced repeats (Decision 4's v2).
2. **Frontier and interval.** `coverage.boundary_frontier` (conditions 1–5, each with a reason
   when it declines, following `gates.covered_frontier`), the bounded branch in `begin_review`,
   `span` / `bounded_from` on the manifest, fact and ledger, record-lint on the bundle span, the
   vanished-token sweep with its caps, and the `full` override token in `infer-critic-mode`. Tests: each condition declining on its own, fact
   composition to the PR gate, and a superseded blocker forcing a full span.
3. **Protocol.** The bounded-mode paragraph and the interaction sweep in `review-protocol.md`, the
   Per-Mode table row in `review-cycle.md`, and the reviewer prompt naming the span and its
   frontier.
4. **Measure.** A review-stats split by `span`, the yield tool re-run on consumers after they
   update, and the Decision 6 revisit.

**Falsifies the lever:** bounded rows on discodon that do not come in well under the full rows of
similar total bundle size, or bounded rows whose later full span or PR review finds blockers on
old-only files at a rate well above the ~1% measured here.
