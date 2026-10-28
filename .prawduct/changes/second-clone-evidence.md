---
schema: 1
type: fix
scope: second-clone-evidence
date: 2026-10-28
title: A second clone works from the review evidence it ingested
closes: [brookstalley/prawduct#1057]
---

Found by running the full two-clone loop, which no field repo had done yet. A fresh clone that
ingests another clone's review notes already composes the same PR-gate verdict. Three surfaces
still read only what the clone itself wrote:

- **Inference asked a proxy.** Rule 2, rule 4's clean-tree redirect and an explicit mode's
  redirect named a `cumulative` unless `.critic-findings.json` recorded a cumulative at exactly
  HEAD. That cache is absent in a fresh clone, and it holds a verify pass after a cumulative
  followed by a clean verify, so both cases bought a review the PR gate did not need. Each now
  also asks the gate's own answer, `gates.branch_coverage_verdict`, using the inference's one
  store read. A covered branch on a clean tree answers `deferred` (no review owed), not an empty
  `chunk`; mid-plan, the "nothing unreviewed" answer is unchanged.
- **verify-resolutions could not run in a second clone (#1057).** Its dispatch finds the prior
  review through the cache's `fact_id`, and its reviewer joins resolutions to that same file. After
  `evidence_notes.ingest` appends records, the cache now names the newest review on this branch
  (`critic_consolidate.derive_branch_cache`): written if missing, re-pointed if it named another
  branch's review or an older one, left as written if it already names that review, and untouched
  while a review is in flight. Branch position decides "newest", because `ts` is to the second and
  ingest appends in note-read order. It uses consolidation's own `fact_to_cache_record`
  projection, carries a verify anchor's unresolved blockers, renders only this reader's schema,
  and validates before replacing anything. A failure is reported and never fails the ingest.
  Session start, `evidence ingest` and `evidence sync` all say what happened.
- **`evidence status` understated its range.** Its count of facts with no note covers this
  branch's commits only, and the line now says so: after a sync it read 0 while thousands of
  older facts had no note.

## Consumer note
- In a second clone of your repo, a review that ran in another clone now counts the way it does
  there. Inference no longer asks for a `cumulative` the PR gate already considers covered, and
  `/prawduct:critic verify-resolutions` works on fixes to it. Run `prawduct-hook evidence sync`
  (or start a session) to pull the other clone's reviews in.
- `evidence status`'s no-note count now says it covers only this branch's commits.
