---
schema: 1
type: fix
scope: briefing-banner
date: 2026-10-27
title: The banner names a downgrade, and the briefing stops nagging merged plans
closes: [brookstalley/prawduct#1104, brookstalley/prawduct#1106]
---

#1104. The session-start banner printed `↑ Prawduct updated: vA → vB` for any version change, so
moving from develop's 3.8.0-dev.2 to the 3.8.0-dev.1 beta read as an upgrade with nothing listed.
`render_delta` now compares the versions with `version_tuple`:
- a lower version prints `↓ Prawduct downgraded: vA → vB` and "changes after vB are no longer
  running", and still relays. It lists nothing: the plugin that runs after a downgrade is the
  older one, whose changelog and gates hold nothing from the range rolled back;
- a move where either side does not parse, or both sort equal, prints `Prawduct changed`, since a
  direction would come from the parser rather than the versions;
- an upgrade is unchanged.

#1106. The briefing's stale-plan scan told every session to "fix the frontmatter, or create the
branch" for a plan whose branch had been merged and deleted and that is waiting for its release.
It trusted chunk state, so any chunk-state defect (#1065, #1079) reached that message. The scan now
also asks `plan status`'s lifecycle (`plan_lifecycle.observe`) and stays silent for a plan that is
merged-unreleased, released or superseded.

Reusing the lifecycle exposed a gap in it. Its last inference, "the branch is gone and a change
record for the scope is pending, so it merged", also fired for a plan committed only on an
unmerged branch, or never committed: `plan new` writes the fragment with the plan, so a plan with
a mistyped `branch:` read as merged. The inference now holds only when the plan is in a base ref's
tree, which is where any merge (merge commit, squash or rebase) leaves it. So the briefing still flags the mistyped branch, and `plan status`,
`plan check-claims` and doctor no longer call that plan release-pending.

## Consumer note
After a version rollback, the session banner now says `↓ Prawduct downgraded` instead of
announcing an update. A build plan that merged and is waiting for its
release no longer gets the "not a branch in this repo … Fix the frontmatter" line in the session
briefing. A plan that is not in the base branch's tree (committed only on an unmerged branch,
or not committed yet) and whose `branch:` names a branch that does not exist still gets it. `plan status` and `plan check-claims` now report that plan as
`unknown` rather than merged-unreleased.
