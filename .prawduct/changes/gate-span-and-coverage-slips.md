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

The span now drops a commit only when three things are all true. First, another session's
transcript in this checkout's host transcript folder was written since this session started
(only file times are read). Second, this session's own transcript, named in the Stop payload,
shows no tool call and no `!` command running when the commit was made. Third, this session
wrote none of the commit's files: none is one its Edit, Write, MultiEdit or NotebookEdit calls
targeted, and none was last written, before the commit, while one of its tool calls or `!` commands ran (#1184,
`stop-span-bash-authorship`).

The third test is there because the first two say who ran `git commit`, and the gates ask who
wrote the change. A user who commits the session's edits from a terminal between turns runs it
with no tool call open, and those files would otherwise leave the span and disarm the
reflection and Critic gates. A `!git commit` is not a tool call either. The transcript records
its input as a user message opening `<bash-input>`, stamped when entered, and its output as one
opening `<bash-stdout>`, stamped when it ended. The time between the two counts as this session
acting, and a `!` command with no output yet counts as running. Background commands and agents
count as running until the end, because they outlive their call. A worktree delegate's commits
fall inside the call that ran it, so merged-back delegate work still counts. Edited files are
matched as files of this checkout, with both paths resolved, so an edit in another checkout
saves nothing.

A dropped commit is not silent. `session_work_span` returns a `dropped` list with each commit's
sha, files and the reason, and the Stop hook writes one line naming them. That line goes to
stderr and, when another gate blocks, into the block text. It repeats on every turn while the
commit is in the span, so it is not shown to the user at a clean Stop.

Every case that cannot be settled keeps the commit counted:

- the payload has no transcript path, or the transcript is missing;
- no other session wrote beside this one;
- the transcript has no tool call, has a result for a call it never opened, or has a broken line
  before its last one;
- the commit predates the transcript's first record;
- git cannot list the commit's files.

**Cost.** The transcript is read only when another session was writing. Otherwise the added
cost is one folder listing, and only once HEAD's tree has moved. A long session's transcript
reaches tens of MB, so what was parsed is kept in `.prawduct/.session-activity.json`, a new
gitignored session file. Entries are keyed by transcript path, device, inode and byte offset.
Each Stop then parses only the bytes appended since the last Stop, plus 256 bytes before the
offset to confirm the file was not rewritten. A replaced, truncated or rewritten transcript, or
a missing or unreadable cache, costs one full read and never a different answer. The cache
grows with the number of tool calls and edited paths, not with tool output. It keeps at most 8
transcripts and evicts the least recently read. Over this machine's 17 largest transcripts and
`!`-mode transcripts (up to 47.8 MB), a read resumed from the cache gave the same answer as a
full read. Each cache entry was 4–123 KB. A Stop with nothing appended took 1–4 ms against
50–170 ms for a full read. The commits made while this session was idle add one batched
`git diff-tree`. The readers live in the host seam (`lib/host.py`: `other_session_wrote_since`,
`session_tool_activity`, and the event's new `transcript_path`). `gates.session_work_span`
takes the path, and `cmd_stop` passes it.

What is still counted: uncommitted or untracked files another session leaves in the shared
checkout, and the readers that run without a Stop payload (the briefing, and the `clear-verdict`
observation). The Critic gate's imported-history excuse is also unchanged.

`tests/test_reflection_gate.py` (`TestAnotherSessionInThisCheckout`) pins both directions in a
real repo: #1071's repro is silent, and this session's own commit and a merged-back delegate
commit still block with the other session's commit beside them. It also pins each case that
keeps the commit counted, and that the transcript is not opened when no other session wrote.
`TestADropAsksWhoAuthoredTheWork` pins a terminal commit of an edited file and a `!git commit`
as counted, and a foreign commit as dropped and named at Stop. `TestTheTranscriptReadIsBounded`
counts the bytes a second Stop reads from the transcript. Each guard was seen to fail with that
guard removed. `tests/test_host_seam.py` pins the two readers, the payload field, and that a
read resumed from the cache at any byte gives the full read's answer. The readers were also run over this machine's real transcripts:
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
longer asked for a reflection just because the other session committed. A session whose commit
touches a file it wrote is still asked, including when you commit that work yourself from a
terminal or with `!git commit`. A file it wrote is one its edit tools (Edit, Write, MultiEdit,
NotebookEdit) named, or one last written before the commit while it had a tool call or `!` command running: through
Bash, a delegate subagent or a background command. A file last written by someone else while
this session ran nothing is not its own. A commit left out this way is named on one line in the
Stop hook's output and recorded once as an `other-session-commit` observation that
`prawduct-hook stats` counts.
`update_gitignore` adds `.prawduct/.session-activity.json` to your `.gitignore` at the next
session start.
