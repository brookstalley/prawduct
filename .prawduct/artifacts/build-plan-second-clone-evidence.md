---
artifact: build-plan
version: 2
scope: second-clone-evidence
branch: fix/second-clone-evidence
base: develop
working-branches: []
last_validated: 2026-10-28
depends_on:
  - brookstalley/prawduct#1057
governed_by:
  - artifact: data-model
    dispositions:
      - "derived views are disposable and never authoritative → conforms: ingest becomes a second writer of .critic-findings.json, the writer-posture case the norm says returns only if a view writer does; it is advice (every failure comes back as an error/invalid status the ingest reports, and never fails the ingest), it re-points the view only at the newest review on this branch and leaves a cache already naming it as written, renders with the same fact_to_cache_record projection, validates before replacing, and no gate reads what it writes"
  - .prawduct/artifacts/architecture.md
  - .prawduct/artifacts/api-contract.md
partition: serial — one chunk; the three fixes share the findings cache and the coverage answer
---

# Build Plan — A second clone works from the evidence it ingested

## Goals

**Response taken:** Proceed. The owner asked on 2026-10-28 to fix findings 1-3 of the two-clone
transport tests (recorded in that session's forward notes) before the 3.8.0 cut. 3tears — public,
two committers — is the first repo where review evidence will cross real clones.

**Problem:** a fresh clone that ingests another clone's review facts composes the same PR-gate
verdict, but three surfaces still read only what this clone wrote itself:

1. `critic_mode._fresh_cumulative_covers_head` (inference rule 2, and rule 4's redirect) asks the
   single-slot `.critic-findings.json` whether a `cumulative` was recorded at exactly HEAD. With no
   cache — a fresh clone — it recommends a cumulative even when the PR gate is satisfied. The same
   proxy misfires in the primary checkout after a cumulative followed by a clean verify pass (the
   cache then holds the verify), which corrects the session's first diagnosis: the cause is the
   proxy, not worktree matching.
2. #1057: `critic_consolidate._prior_review_fact` finds a verify pass's anchor only through the
   cache's `fact_id`, and the verify reviewer joins its resolutions to "the prior findings record",
   which is that file. A fresh clone has neither, so verify-resolutions cannot run there.
3. `evidence status` reports "0 transported fact(s) with no note on their commit" over the branch
   range only, and does not say so; after a sync it read 0 while ~6,258 older facts had no note.

**Success:**
- Inference does not recommend a cumulative when the PR gate's own answer
  (`gates.branch_coverage_verdict`) is `covered` or `transferred`, in any clone.
- After an ingest that appended records, the findings cache names the newest review on this branch
  (as consolidation would have written it), so inference, the verify dispatch and the verify
  reviewer all work there — including a clone whose cache named another branch's review or an
  older one. A cache already naming that review is left as written; a review in flight keeps the
  slot; a failure is reported and never fails the ingest. *(Widened at the boundary review from
  "only when no cache exists", which left #1057 open for a clone that had switched branches.)*
- A covered branch on a clean tree is told no review is owed (`deferred`), not handed an empty
  `chunk` or a needless `cumulative`.
- `evidence status` names the range its no-note count covers.

**Decisions:**
- Re-derive the cache at ingest, the one place facts arrive (session start, `evidence ingest`,
  `evidence sync` all go through `evidence_notes.ingest`), rather than teach each cache reader a
  store fallback: the verify reviewer reads the file and cannot fall back.
- Rule 2 keeps its cache check and adds the gate's answer — it only ever fires less.

## Chunks

### Chunk 01: second-clone evidence

- **Type:** cumulative-final
- **Description:** the three fixes above, the change fragment, and wherever a doc states rule 2's
  condition or the status line.
- **Deliverables:** `critic_mode` rule-2 freshness; `evidence_notes.ingest` deriving the cache;
  `evidence status` wording; tests; `.prawduct/changes/second-clone-evidence.md`; a `ships` row.
- **Tests:** rule 2 silent when coverage composes and no cache exists, and still firing when
  uncovered or blocked (controls); a covered clean branch answers `deferred`, and a named `chunk`
  there stands; after ingest the cache names the newest branch review — written when missing,
  re-pointed from another branch's or an older review, left as written when already current,
  untouched while a review is in flight, never pointed off the branch, never rendered from a newer
  schema, and a derivation failure reported without failing the ingest; "newest" by branch
  position in both fact orders; a verify-resolutions dispatch in such a clone finds its anchor;
  status wording; the ingest and sync output lines.
- **Acceptance criteria:** Success bullets 1-3.
- **Done when:**
  1. Acceptance criteria met and tests pass, each new guard seen red
  2. The two-clone loop re-run on a scratch clone shows inference, verify dispatch and status
     behaving as Success says
  3. Committed, then the boundary `cumulative`
