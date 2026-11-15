---
schema: 1
type: fix
scope: gate-span-and-coverage-slips
date: 2026-11-15
title: another session's commits in the same checkout no longer count as this session's work, and excused paths report each free step's files
closes: [brookstalley/prawduct#1071, brookstalley/prawduct#1159]
---
**Another session's commits (#1071).** The Stop hook decides whether a session changed
judgeable code from what changed since the session started. When a second session committed in
the same checkout, its commits landed in that span. Both sessions move the one HEAD, so the
reflog read that already drops pulled, merged and switched-to history could not tell them apart.
A session that wrote nothing could then be blocked by the reflection gate, and by the Critic
gate's trigger, which reads the same span.

The span now drops a commit only when two things are both true. First, another session's
transcript in this checkout's host transcript folder was written since this session started
(only file times are read). Second, this session's own transcript, named in the Stop payload,
shows no tool call running when the commit was made. git runs in a session only from a tool
call, so a commit made between this session's calls was not made by it. Background commands and
agents count as running until the end, because they outlive their call. A worktree delegate's
commits fall inside the call that ran it, so merged-back delegate work still counts.

Every case that cannot be settled keeps the commit counted:

- the payload has no transcript path, or the transcript is missing;
- no other session wrote beside this one;
- the transcript has no tool call, has a result for a call it never opened, or has a broken line
  before its last one;
- the commit predates the transcript's first record.

Reading the transcript happens only when another session was writing. Otherwise the added cost
is one folder listing, and only once HEAD's tree has moved. The readers live in the host seam
(`lib/host.py`: `other_session_wrote_since`, `session_tool_activity`, and the event's new
`transcript_path`). `gates.session_work_span` takes the path, and `cmd_stop` passes it.

What is still counted: uncommitted or untracked files another session leaves in the shared
checkout, and the readers that run without a Stop payload (the briefing, and the `clear-verdict`
observation). The Critic gate's imported-history excuse is also unchanged.

`tests/test_reflection_gate.py` (`TestAnotherSessionInThisCheckout`) pins both directions in a
real repo: #1071's repro is silent, and this session's own commit and a merged-back delegate
commit still block with the other session's commit beside them. It also pins each case that
keeps the commit counted, and that the transcript is not opened when no other session wrote.
Each guard was seen to fail with that guard removed. `tests/test_host_seam.py` pins the two
readers and the payload field. The readers were also run over this machine's real transcripts:
42 files, a 7.8 MB one in 70 ms, and the only unreadable ones were sessions with no tool calls.

**Coverage algebra slips (#1159).** `excused_gap_verdict` returned paths whose free steps lacked
`files` when free edges came from tree keys, the form every gate uses. That broke the documented
`{kind: free, src, dst, files}` shape. Covered and blocked excused paths now fill those files in
the same way `coverage_verdict` does for its own path. Nothing read them yet. A test asserts the
shape in both free-edge forms, and the generated-graph test checks each free step's files. The
`_merge_base_verdict` docstring now says the pairwise free-edge probe lives in the evidence graph
rather than in `_find_path`.

## Consumer note
If you run two Claude Code sessions in the same checkout, a session that changed nothing is no
longer asked for a reflection just because the other session committed. A session that commits
its own code is still asked.
