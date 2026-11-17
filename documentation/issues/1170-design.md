# Issue #1170 — critic: consolidation lists one defect as several findings: Design

`status: draft · stage: design · area: critic · added: 2026-11-17 · source: scheduled design pass ·
issue: https://github.com/brookstalley/prawduct/issues/1170`

Related: #166 (shipped the advisory grouping this design extends, and the ruling that a fuzzily
dropped finding is worse than an over-count), #1130 (the Critic-vs-native comparison that
over-counts Critic-only findings), #1160 (a verify pass that raises B instead of resolving A), #847
(a class finding closed at the instance it named).

Everything under "What the code does today" was read from `develop` at `0fcedff2`. The four miss
shapes in the table were run against `likely_duplicate_groups` with synthetic titles. The observed
reviews (R-1/R-5/R-6, R-2/R-4, and the testament R-4/R-5) were **not** examined: their findings
live in the evidence store of the clone that ran them, which is not in the repository. So the
issue's first acceptance box, "the reason the existing grouping missed the observed cases is
stated", is not ticked by this document. Build step 1 ticks it.

## Summary

Consolidation already detects likely duplicates and renders each group as one defect line. Two
things keep that from helping:

1. **The result never reaches the builder on the three-reviewer path.** With a coordinator roster,
   `critic-consolidate` runs under the `SubagentStop` hook, so its stdout is read by nobody. The
   builder reads `.critic-findings.json`, where the grouping is a bare `likely_duplicate_groups`
   key that no code and no prose reads. This holds for every three-reviewer review, which is the
   only roster that produces cross-reviewer duplicates, so it applies to all three observed cases
   whatever the matcher returned.
2. **The matcher reads titles only, and refuses on file attribution.** One defect described under
   three goals is commonly given three differently worded titles, or attributed to the code file by
   one reviewer and to its test by another. Each of those returns no group.

The design fixes delivery first, then widens the matcher, and keeps both advisory. Every finding
keeps its own `fid`, its own entry in the fact, and its own resolution. Nothing is merged or
dropped, so a wrong group can cost a reader one confusing line and nothing else.

## What the code does today

All in `plugin/lib/critic_consolidate.py`.

- `merge_findings` keys on `(goal, name, files)`. Reviewers hold disjoint goals, so two reviewers
  meeting one defect always produce two findings. This is deliberate and stays.
- `likely_duplicate_groups(findings)` pairs findings whose goals differ and whose file sets are not
  disjoint, then groups a pair when either holds:
  - Jaccard over significant **title** words is at least `DUPLICATE_SIMILARITY` (0.4), or
  - the file sets are **identical**, the shorter title has at least `DUPLICATE_MIN_WORDS` (3)
    significant words, and the overlap coefficient is at least `DUPLICATE_CONTAINMENT` (0.6).
  Grouping is transitive (union-find). The recommendation text is never read.
- The groups are used in two places:
  - the `consolidated:` summary printed by the consolidate command, with a count of distinct
    findings and one line per group from `_render_duplicate_groups`;
  - the `likely_duplicate_groups` key of the record that becomes `.critic-findings.json`.
- The last line the command prints is `NEXT-ACTION: ` plus the record's `next_action`. The comment
  above it says why: when a reviewing fork runs the command, everything else it prints "dies
  there", and that one line is the part both protocol files tell the fork to relay. `next_action`
  does not mention groups.
- `plugin/skills/critic/coordinator.md` step 3: the `SubagentStop` hook runs `critic-consolidate`
  as each reviewer finishes. That is the three-reviewer path.
- A search of `plugin/` for `likely_duplicate` finds only `critic_consolidate.py`. No skill,
  methodology file or other module reads the key.
- `account_for_prior_blockers_directive` lists the blockers a verify pass must answer one `fid` per
  line, and says a resolution "is recorded per finding". It has no notion of a group.
- `stats.py` counts a finding as raised once per `fid`.

### Why a real duplicate returns no group

Each row was run against the current function. All four return `[]`.

| Shape | Why it misses |
|---|---|
| Same title, one reviewer cites the code file and the other its test | Disjoint file sets skip the pair before any text is compared |
| Same files, same recommendation, titles worded from each goal's angle | Only titles are compared; the shared recommendation is not read |
| Overlapping but not identical files, reworded titles | Jaccard is below 0.4 and the containment route needs identical files |
| Same goal, different wording | Same-goal pairs are skipped |

The fourth row is not a cross-reviewer case (goals are disjoint between reviewers), so this design
leaves it alone: a reviewer folding its own restatements is `review-protocol.md`'s rule ("A
finding's subject is never another finding").

## Design

### D1. The grouping reaches the builder

One function owns the sentence, and the two surfaces the builder reads carry it.

- **`next_action` names the groups.** When groups exist, the sentence gains one clause:
  `R-1+R-5+R-6 and R-2+R-4 each look like one defect filed by more than one reviewer: fix each
  once, and resolve every id.` This is the one line that travels on both paths (relayed by a
  fork, read from the findings file after a hook-run consolidate), so it is where the fact has to
  be. The clause is built by a new `duplicate_groups_clause(groups)` next to
  `_render_duplicate_groups`, and `next_action_line` takes the groups as a parameter.
- **Each grouped finding says so in the findings file.** A finding in a group gets an additive
  `same_defect_as: ["R-5", "R-6"]` key (the other members). A builder reading one entry sees the
  link without cross-referencing a list at the bottom of the file. `likely_duplicate_groups` stays
  as the list form; both are computed from the fact's findings at render time, so nothing is added
  to the persisted fact and an ingesting clone computes the same answer.
- **`building.md` "Resolve findings" gains one sentence** telling the builder that a group is
  dispositioned once and resolved per id. That gives the key a named reader.
- The stdout rendering stays as it is for the inline path.

### D2. The matcher reads more than the title

Still pairwise, still cross-goal, still transitive, still advisory. Two routes are added to the two
that exist.

- **Recommendation route.** Identical file sets, and Jaccard over significant words of the
  **recommendation** at or above a bar. Two reviewers who would have the builder make the same edit
  to the same files are describing one defect, whatever they titled it. The word floor
  (`DUPLICATE_MIN_WORDS`) applies to the shorter recommendation.
- **Disjoint-files route.** Today a disjoint file pair is skipped outright. Instead it is compared
  on title at a **higher** bar than the 0.4 used when files overlap. A near-identical title on a
  code file and on its test is evidence of one defect; a loosely similar one is two findings about
  one subsystem, which is the reason the skip exists.

**The bars are calibrated, not chosen here.** #166 set 0.4 by replaying the repo's recorded
reviews and spot-checking every surfaced pair. The same procedure sets the two new bars, over the
whole corpus and not only the cases that prompted this:

1. Replay every recorded review with findings through the old and new matcher.
2. For each candidate bar, list the pairs the new routes add. Spot-check all of them if under 40,
   otherwise a sample of 40.
3. Pick the lowest bar at which every checked pair is a real duplicate. If no bar clears that, the
   route is not shipped.
4. Record the corpus size, the pairs added and the pairs checked in the constant's comment, as the
   existing constants do.

A false group is cheaper after D1 than a miss, but not free: the `next_action` clause tells the
builder to fix once. So the bar is "every checked pair is real", the same standard as #166, and not
a looser one.

### D3. A verify pass sees a group as one judgment

`account_for_prior_blockers_directive` prints grouped blockers on one line:
`<review_id>/R-1 (+R-5, R-6: likely the same defect) — <title>`, followed by the existing
instruction, which already says a finding fixed by another's edit is still its own `resolutions`
entry. The rule that every id needs its own resolution does not change. What changes is that the
reviewer is told the three ids are probably one check, which also removes one way a verify pass
raises a new finding for a defect it was asked to resolve (#1160's entry condition).

Groups here are computed from the anchored review's findings with the same function. Carried
blockers from different reviews are not grouped across reviews.

### D4. Counts

- `stats.py` keeps counting per `fid`. Raised and fixed counts per severity feed yield measures
  that compare reviews over time, and changing their meaning mid-series would make the trend
  unreadable. Instead the per-review block gains an additive `distinct` count
  (`distinct_finding_count`), so a reader of #1130's comparison can use it.
- #1130's comparison is done by the builder working from both lists, not by code. The `next_action`
  clause from D1 is what corrects that count: the builder is told which ids are one defect before
  comparing.

### Not chosen

- **Collapse a group into one finding in the write path.** This is what #166 ruled out. A wrong
  collapse removes a finding from the fact, and from the gate, with nothing in the output to show
  it happened.
- **One finding with an `also_filed_as` list (lossless merge).** It keeps every reviewer's words,
  but one `fid` would stand for several judgments. The coverage algebra, resolution facts,
  `verify-resolutions` and `stats.py` all join on `fid`, so each would need a rule for a finding
  whose members disagree on severity or get resolved separately. D1 to D3 give the builder the same
  "one defect, three attributions" reading with no change to what a `fid` means. See Q1.
- **Ask a model to judge duplicates at consolidation.** Consolidation is code-only by contract
  ("no model authors a file the data plane trusts").

## Changes by site

| Site | Change |
|---|---|
| `critic_consolidate.py` `likely_duplicate_groups` | Two routes added; recommendation words read; disjoint-file pairs compared at the higher bar |
| `critic_consolidate.py` constants | Two new bars, each with its calibration record |
| `critic_consolidate.py` `next_action_line` and its caller in the findings-record builder | Take groups; append `duplicate_groups_clause` |
| `critic_consolidate.py` findings-record builder | `same_defect_as` on grouped entries |
| `critic_consolidate.py` `account_for_prior_blockers_directive` and its caller | Grouped line form |
| `stats.py` per-review block | Additive `distinct` |
| `plugin/methodology/building.md` "Resolve findings" | One sentence: a group is fixed once and resolved per id |
| `.prawduct/artifacts/api-contract.md`, `.prawduct/artifacts/data-model.md` | Describe `same_defect_as` beside the findings record's other additive keys. No shipped prose describes `likely_duplicate_groups` today, so there is no sentence to replace |

## Build order

1. **Diagnose the observed cases.** In the clone that ran them, print for every cross-goal pair of
   the 2026-11-13/14 reviews: both goals, the file relation (identical, overlapping, disjoint),
   title Jaccard, title containment, recommendation Jaccard, and whether the pair grouped. State
   in the issue which rule each observed pair failed. If a pair grouped, the miss was delivery
   alone and D2 is judged on the corpus replay, not on these cases.
2. Copy the observed findings (goal, title, recommendation, files) into the test file as fixtures.
3. D1, with tests. It is independent of the diagnosis and is the part known to apply.
4. D2, calibrated as above.
5. D3, D4.

## Tests

Each is seen red against the current code before the change.

- The observed R-1/R-5/R-6 and R-2/R-4 findings, verbatim, group as `[[R-1, R-5, R-6], [R-2, R-4]]`.
  The testament R-4/R-5 pair groups.
- A hook-run consolidate (no reader of stdout): the `next_action` in `.critic-findings.json` names
  each group, and each grouped entry carries `same_defect_as` listing the others. Control: a review
  with no groups has neither the clause nor the key.
- Recommendation route: same files, same recommendation, unrelated titles group. Controls: the
  same pair with different files does not; a recommendation under the word floor does not.
- Disjoint-files route: the same title on a code file and its test groups. Control: two titles
  that group at 0.4 with overlapping files do not group with disjoint files.
- The existing tests stay, including `test_nothing_is_dropped_or_reordered` and
  `test_containment_needs_identical_files_not_merely_overlapping`.
- The fact body written for a review with groups is identical to today's, key for key. Every `fid`
  is present in the fact and in the findings file.
- A verify dispatch whose anchor has a grouped blocker prints the group on one line and still
  names every id. Consolidation still refuses a pass that omits one of them without a finding.
- `building.md` and the code agree: a test reads the "Resolve findings" sentence and the clause
  text for the shared instruction (fix once, resolve every id).

## Open questions for the owner

- Q1. Advisory grouping delivered properly (this design), or the lossless merge? This design keeps
  the per-id resolution, so a three-way duplicate still costs three `resolutions` entries, though
  one fix and one judgment. The merge removes that at the cost of redefining `fid` in four readers.
- Q2. If step 1 shows the matcher did group the observed cases and delivery was the whole miss,
  ship D1 and D3 alone and leave D2 for a case that needs it?
- Q3. `stats.py`: additive `distinct` beside the per-`fid` counts (proposed), or switch the raised
  counts to distinct defects and accept a break in the series?
