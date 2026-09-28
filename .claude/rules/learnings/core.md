# Learnings — core

**Apply a rule below where it bears on the decision in front of you, and cite it where it changed what you did.**

Each rule is one line of at most 250 characters. This file is capped, so a new rule is paid for by merging or retiring one.

- A review finding names an instance; the defect is a class. Say in one sentence why it broke — if that sentence covers sites outside your diff, fix the class through one owner. Tell: your second fix of one class in two rounds.
- A check never seen to return non-zero proves nothing — before trusting a zero, a clean sweep or 'X costs nothing', feed the instrument a case it must catch. Tell: the result confirmed what you hoped, first try.
- A coverage, completeness or absence claim ('X now handles Y', 'no Y', 'all') holds only when its falsifying query returns nothing — query the concept in more than your own words, over the unsliced set; a count of sites fixed is not that.
- Open what a criterion, plan or stated reason names before building to it or citing it — a description inherits its author's blind spot, and a gate's behaviour lives in the function returning its verdict. Tell: you could comply without opening it.
- Enumerate a set by query, never memory, and bound it by the property that justifies it, not a location: grep the thing's shape for copies and its name and wrappers for dependents. Tell: the boundary is a path, the rationale a verb.
- Before implementing against a mechanism, search the backlog for its name — an open item may already redefine or retire it.
- A fix for a review finding is a CODE commit: test it, red-verify it, and dispatch a delta review of the fix — correction work feels low-risk, so the verification reflex relaxes exactly where the last round proved it shouldn't
- A governance change cannot supply its own authority: when an agent amends a binding norm mid-build, land the owner's confirmation somewhere the amendment isn't — a change that is its own only witness reads as laundering
- When defense-in-depth is the reason a risk needn't be verified, check the defense is REACHABLE from the failure — a guard downstream of the thing that fails never runs (`endswith` check behind a matcher that never fired)
- Uncommitted work in a worktree this session did NOT launch in is another session's territory — leave it alone; adopting sibling WIP collides with a possibly-live session and writes into clone-shared governance state
- When surfacing model-proposed candidates for owner confirm-or-correct, triage by decision-worthiness first: surface real forks individually, bulk-confirm the rest — a flat dump buries decisions and trains rubber-stamping
- A mechanism change is done when every artifact DESCRIBING it agrees: search for the claim, not the tokens you edited, across prose, tests, templates and registries, and delete superseded sentences and removed names rather than adding beside them.
- A channel that is produced and never consumed is a DEFECT, not an inefficiency — name the consumer in the same change that adds the producer, or don't produce
- File a backlog item the moment you decide it should exist — routing it to the handoff is not filing it, and a crash or exhausted context loses an unwritten handoff.
- A text-anchored edit changes a NEIGHBORHOOD, not a point — inserting at a `def` lands between the next function and its decorator; adding `else` to try/except strands the fallback. Both stay green: re-read the enclosing block after anchored edits.
- A rule you must RECALL at the right moment is its weakest form — if it governs a queryable claim, mechanise it (test, lint, rendered table); recall fails hardest on rules just written or read. Tell: this cycle's catches all came from mechanisms.
- Verify a chunk against the PLAN's deliverable list, not the files you edited — work concentrates in one file and "done" gets judged from what's in front of you. Tell: a Tests/Deliverables line names several files and your edits concentrated in one
