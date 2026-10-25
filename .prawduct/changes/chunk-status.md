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
verdict. It is now a query over the review facts the Critic already writes: a chunk is done when
a review fact names it with no unresolved blocking finding; dropped when the plan's `dropped:`
line says so with a reason; open otherwise. `plan_status` is the one walker, `prawduct-hook plan
status` renders it, and the Stop gate arms on the branch's binding and disarms on coverage, with
no box to tick and no last-box exception. Review facts name the set of chunks they certify
(`critic-begin --chunks`). Existing ticked boxes are imported as `chunk-imported` facts by
`doctor`, marked imported rather than evidenced. Draft — Chunk 06 finalises this narrative and the
note against what shipped.

## Consumer note

- `prawduct-hook critic-begin --chunks 01,03` names the chunks a review certifies; `--chunk` stays
  as a one-element alias for one release. The review fact carries `chunks`, `chunks_proposed` (the
  set the framework derived from the diff and the chunks' deliverables) and `chunk` (= `chunks[0]`,
  for old readers, one release).
- New fact kind `chunk-imported` (observational). New subcommands: `plan status [<path>] [--json]`
  (the chunk table), `plan import-status <path> [--apply] [--remove-block]` (MG2; the block is
  removed only on request until #1052 ships transport — facts are per-clone until then), `plan
  check-claims` (every live plan's `branch:`/`working-branches:` names a branch that exists).
- The Stop hook no longer reads `project-state.yaml` `build_plan.chunks[].status` (ST7) or counts
  boxes; it arms when the checkout is bound to a live plan (or the binding is broken).
- `test-evidence record` from a scratch worktree now appends a `test-run` fact with
  `narrowed: true` to the shared store and writes no per-worktree JSON; `test-status` lists those
  runs by tree.
- The `unticked-committed-chunk` briefing token is retired; its successor reports built-but-not-done
  from `plan status`.
- Template: `## Status` leaves `templates/build-plan.md`; `dropped:` joins the frontmatter legend.
