---
schema: 1
type: fix
scope: chunk-proposal-silence
date: 2026-10-26
title: A boundary review that certifies no chunks says so
closes: [brookstalley/prawduct#1081]
---

#1081. At a plan's boundary `cumulative`, `critic-begin` proposed no chunks although every chunk's
work was on the branch. Omitting `--chunks` then certified nothing, nobody was told, and three
plans in one product were archived with `unbuilt_at_archive` on shipped work. There were three
causes, and each is fixed.

### Chunk 01: the proposal reads more, and says when it reads nothing

- **Subjects.** `plan_status`'s subject walk now matches a chunk id in any case, and accepts
  `chunk NN:` (the id followed by a colon) as a fourth carrying form. Prose such as "carried to
  Chunk 04" still names nothing. A subject carries the plan's scope as `<type>(<scope>):` or as
  its whole first word (`<scope> chunk 01: …`), so the reporter's subjects now certify. A word
  that merely starts with the scope does not count.
- **Bare Deliverables names.** The record lint skips a bare name, and no repo-relative diff path
  can equal one; a root-level file is the only bare name that is also a path. When every
  Deliverables token of an unproposed chunk is such a name, the dispatch notes that only a commit
  subject can find the chunk, and says to write paths from the repo root or pass `--chunks`. No
  bare name matches by basename, because a wrong certification is never reviewed again.
- **Where the builder reads.** The proposal's notes print inside the forked critic, so they never
  reached the main agent. Now, when a `final` or `cumulative` review certifies no chunk while the
  plan has open ones, `critic-consolidate` ends the relayed `NEXT-ACTION:` line, and its copy in
  `.critic-findings.json`, by naming those chunks and the `--chunks` remedy.

### Chunk 02: this change record

#1082 (should a review's commit span certify chunks it does not name?) is a separate design
question and is not addressed here.

## Consumer note
A `final` or `cumulative` Critic review that certifies no chunk while your plan still has open
ones now says so at the end of its `NEXT-ACTION:` line, naming the chunks and the `--chunks` flag
to pass. Before this, such a review left the chunks open without a word, and they were archived
as unbuilt at release. Commit subjects now name a chunk in any case, including
`<scope> chunk 01: …`. When a chunk's Deliverables are all bare file names (`page.js` rather than
`src/page.js`), the dispatch says only a commit subject can find it: write Deliverables paths
from the repo root.
