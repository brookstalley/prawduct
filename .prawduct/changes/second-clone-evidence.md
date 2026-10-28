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

- **Inference asked a proxy.** Rule 2 (and rule 4's clean-tree redirect) recommended a
  `cumulative` unless `.critic-findings.json` recorded a cumulative at exactly HEAD. That cache is
  absent in a fresh clone, and it holds a verify pass after a cumulative followed by a clean
  verify, so both cases bought a review the PR gate did not need. `critic_mode` now also asks the
  gate's own answer, `gates.branch_coverage_verdict`, and stays silent when it is `covered` or
  `transferred`. It can only fire less than before.
- **verify-resolutions could not run in a second clone (#1057).** Its dispatch finds the prior
  review through the cache's `fact_id`, and its reviewer joins resolutions to that same file. When
  `evidence_notes.ingest` appends records to a clone with no findings cache, it now derives one
  (`critic_consolidate.derive_missing_cache`) from the review anchored furthest along the branch.
  Branch position decides "newest", because `ts` is to the second and ingest appends in note-read
  order. It uses consolidation's own `fact_to_cache_record` projection and carries a verify
  anchor's unresolved blockers, and an existing cache is never replaced. Session start,
  `evidence ingest` and `evidence sync` all go through ingest and say when it happens.
- **`evidence status` understated its range.** Its count of facts with no note covers this
  branch's commits only, and the line now says so: after a sync it read 0 while thousands of
  older facts had no note.

## Consumer note
- In a second clone of your repo, a review that ran in another clone now counts the way it does
  there. Inference no longer asks for a `cumulative` the PR gate already considers covered, and
  `/prawduct:critic verify-resolutions` works on fixes to it. Run `prawduct-hook evidence sync`
  (or start a session) to pull the other clone's reviews in.
- `evidence status`'s no-note count now says it covers only this branch's commits.
