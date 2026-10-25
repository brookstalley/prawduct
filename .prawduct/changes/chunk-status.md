---
schema: 1
type: feature
scope: chunk-status
date: 2026-10-25
title: chunk status derives from review facts
closes: [brookstalley/prawduct#1051, brookstalley/prawduct#1050]
---

Wave 2 of #1050. Whether a build-plan chunk is done was a hand-ticked `## Status` box, read by
23 sites with four different answers to "is the plan finished", six of them deciding a gate
verdict. It is now a query over the review facts the Critic already writes: a chunk is **done**
when a review fact names it with no unresolved blocking finding and its anchor commit is in the
branch's history; **dropped** when the plan's frontmatter `dropped:` lists it as `- <id>: <reason>`
(reason required); **open** otherwise. `plugin/lib/plan_status.py` is the one walker
(`chunk_states`, `is_finished`, `current_chunks`, `gate_arms`), every consumer takes its answer,
and the old readers are deleted — `buildplan_refs.py` alone lost ~700 lines, and a pin test scans
every module and the hook for a box regex or a Status walk outside the two permitted files.
`prawduct-hook plan status` renders the table; the handoff, the briefing and the PR payload print
the same rows from one renderer. The Stop gate arms on the branch's binding and disarms on
coverage: no box to tick, no last-box exception, and a commit or an edit before the review cannot
disarm it. Review facts name the set of chunks they certify (`critic-begin --chunks`), with the
code-derived proposal recorded beside the declaration. Existing ticked boxes are imported as
`chunk-imported` facts by `doctor`, marked imported rather than evidenced; until a plan is
migrated the same reader derives the identical answer from its boxes in memory. The `## Status`
block leaves the template; `data-model.md` records the owner's 2026-10-24 amendment of DV3 — a
commit still marks the end of coding, not governance; the fact written at the governance event is
now the carrier. Also ships: `plan check-claims` (BR3, deferred from Wave 1 — every live plan's
claimed branch exists, is release-pending, or is missing), delegate test runs recorded as narrowed
facts (DG2), and the `record_lint` repo-relative path fix.

## Consumer note

- `prawduct-hook critic-begin --chunks 01,03` names the chunks a review certifies (comma list,
  repeatable; omitted, the review certifies exactly the code-derived proposal); `--chunk` stays as
  a one-element alias for one release. The review fact carries `chunks`, `chunks_proposed` and
  `chunk` (= `chunks[0]`, one release, for old readers). An id the plan does not declare is refused
  (`unknown-chunk`, exit 1); an id outside the proposal is recorded with a `WARNING:` note.
- New fact kind `chunk-imported` (observational for coverage; authoritative for chunk completion).
  New subcommands: `plan status [<path>] [--json]`; `plan import-status <path> [--apply]
  [--remove-block]` (MG2 — the block is removed only on request until #1052 ships transport, because
  facts are per-clone until then; refusal codes in `api-contract.md`); `plan check-claims [--json]`
  (outcomes `exists` / `release-pending` / `missing`; a merged plan retained for release is
  release-pending, not a defect).
- Build-plan frontmatter gains `dropped:` — a block sequence of `- <id>: <reason>`; a reasonless or
  unparseable entry leaves the chunk open with the cause in `plan status`'s `reason` column.
- The Stop hook no longer reads `project-state.yaml` `build_plan.chunks[].status` (ST7) or counts
  boxes; it arms when the checkout is bound to a live plan or the binding is broken. On a short
  plan, commits whose subject names `Chunk <id>` (or touch the chunk's deliverables) are what make
  it the last chunk; a git-derived signal can arm the gate, never disarm it.
- `test-evidence record` from a scratch worktree now appends a `test-run` fact with
  `narrowed: true` and `ceiling` to the shared store and writes no per-worktree JSON; a narrowed
  fact never vouches for the suite. `test-status` lists those runs by tree after its verdict line.
- The `unticked-committed-chunk` briefing token is retired; its successor is `built-not-done`
  ("built, not done — run the Critic"), printed at `/clear` and by `handoff preview` for the
  bound plan's chunks that are committed but not yet certified.
- Template: `## Status` leaves `templates/build-plan.md`; a minted plan carries none. Prose: the
  rule lives once in `methodology/planning.md`; the digest, the template and the skills reference
  it. `work_unit.live_declarations` is public (`_live_declarations` aliased one release).
