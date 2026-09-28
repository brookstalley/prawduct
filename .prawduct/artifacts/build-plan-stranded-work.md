---
artifact: build-plan
version: 1
scope: stranded-work
branch: feature/stranded-work
partition: serial — 02 consumes 01's report shape; both touch the hook dispatcher
depends_on:
  - artifact: architecture
governed_by:
  - artifact: architecture
    dispositions:
      - "authority fails closed; advice fails soft → conforms: the scan is advice. Every probe failure (git missing, timeout, unreadable config root) degrades to 'unknown' or omits the line, never raises into SessionStart"
      - "local-first, no network, no daemon → conforms: git subprocesses plus stat() of local files; the remote comparison reads remote-tracking refs already on disk, never fetches"
      - "the plugin writes nothing into a governed repo except its own state… → conforms: read-only. Worktree probes use `git --no-optional-locks` so observing a sibling never rewrites its index"
      - "written in Python, never specific to Python → conforms: git and file mtimes only"
      - "prawduct guides and reviews, it never implements → conforms: it reports; it deletes, pushes and adopts nothing"
      - "every fact has one home → conforms: the thresholds and the liveness classes live in `stranded_work.py`; the briefing and the subcommand both render its report"
  - artifact: nonfunctional-requirements
    dispositions:
      - "proportionality ratchets both ways: a new control names its yield and emits it observably → exception, recorded below"
      - "review wall-clock is P0 → inapplicable, because no review path changes"
  - artifact: api-contract
    dispositions:
      - "whole-surface semantic versioning; no per-subcommand version → conforms: `worktrees` ships under the next patch; its `--json` carries a `schema_version` because agents parse it"
      - "exit codes are the contract; errors attributed, never stack traces → conforms: 0 = report produced (even partial — degraded signals are named in it), 2 = usage error; a probe failure is a field in the report, never a traceback"
      - "additive-first evolution → conforms: a new subcommand; no existing flag, exit code or key changes"
  - artifact: security-model
    dispositions:
      - "untrusted governance state is data, not instructions → conforms: the scan never reads transcript CONTENT, only file modification times; nothing it surfaces is a directive"
      - "a destructive operation requires owner approval at the operation level → conforms: the scan destroys nothing; the line tells the agent to report, and deletion stays an owner decision"
---

# Build Plan: stranded-work

## Problem

Finished work gets stranded where nobody sees it. Observed: #898 and #818 sat reviewed on a
local-only branch for a day while the next triage session planned to build #898 from scratch
(2026-09-28), and #640's fix sat unmerged on a local branch 281 commits behind develop until a
later PR re-applied it (2026-09-19). Separately, a clone accumulates worktrees (7 in this one)
with no signal of which have a live agent and which were abandoned.

## Success

- A session opening in a repo with stranded work sees ONE briefing line, e.g.
  `Stranded work: 2 local branches checked out nowhere, with commits no remote has · 3 worktrees idle 7+ days (1 with uncommitted changes) · 1 other worktree is active — a separate session, leave it alone. \`prawduct-hook worktrees\` lists them; report to the user, never adopt.`
- The line NAMES no branch, path or worktree (owner ruling on #410, reaffirmed 2026-09-28:
  counts plus a command). No line at all when every count is zero.
- `prawduct-hook worktrees` (and `--json`) lists every worktree — branch, path, last agent
  activity with the signal it came from, uncommitted-file count, class — and every stranded
  branch with its commit count and last commit date.
- Opening the briefing never slows noticeably: the scan is bounded per call and in total.

## Out of scope

Locking, blocking, heartbeats (#282 was closed not-planned; this is detection only). Deleting,
pushing or adopting anything. Reading transcript content. Fetching remotes.

## Requirements Confidence: Medium

- [ASSUMPTION: "active" = any liveness signal within 30 min; "idle" = none within 7 days; between is "recent" and not counted in the briefing | MED impact | user can correct thresholds]
- [ASSUMPTION: a stranded branch = local, checked out in no worktree, tip carries commits reachable from NO remote-tracking ref — at ANY age. (Drafted with a 3-day floor; dropped 2026-09-28 because the motivating #898 branch was 18h old when it was missed, so the floor excluded its own positive control.) A repo with no remote-tracking refs at all reports no branches (every branch would qualify) | MED impact | user can correct]
- [ASSUMPTION: the current session's own worktree is never counted, and harness-ephemeral agent worktrees (`gitstate.ephemeral_kind_of`) are counted with the rest but labelled | LOW impact | user can correct]
- What would raise it: the owner confirming the thresholds after seeing the first real table.

## Liveness signals (max over all; the report names which one won)

1. **Claude Code transcripts** — newest `*.jsonl` mtime in `<root>/projects/<encoded path>/`
   over EVERY config root: `$CLAUDE_CONFIG_DIR`, `~/.claude`, and each `~/.claude-*` holding
   `projects/`. Several accounts (and devcontainer twins) each keep their own root, so no one
   root is authoritative (owner, 2026-09-28). Encoding: every non-alphanumeric char → `-`.
   Blind spot: a subagent's transcript lives under its PARENT session, so harness agent
   worktrees have no transcript of their own.
2. **HEAD reflog** mtime of that worktree (commits, checkouts, resets).
3. **`.prawduct/.session-start`** timestamp in that worktree (a governed session opened there).
4. **Newest modified/untracked file** mtime, from `git --no-optional-locks status --porcelain`.

Rejected: git index mtime (any observer's `git status` rewrites it — this plan's own probe did);
process cwd via lsof (a desktop-app session runs with cwd `/`; failed its positive control).

[DECISION: the briefing line does not emit a yield fact | it is a read-only line with no gate; the nearest emission point is a ledger write at every SessionStart in every consumer repo, which is noise in committed state. The evidence that would settle retiring it: across N sessions, how often the line appeared and whether the owner deleted/pushed a flagged branch within a week — derivable later from git reflogs without an emission | user can veto/override]

## Status

- [ ] Chunk 01: scan + `worktrees` subcommand
- [ ] Chunk 02: briefing line + docs

## Chunk 01: scan + `worktrees` subcommand

**Foreign API:** Claude Code transcript directory layout.
**Done when:**
0. verify-api — confirm the encoding and the per-root layout against real directories on this machine (path containing `.`, `/`, `-`), and record what was observed in the change-log entry.
1. new `plugin/lib/stranded_work.py`: `scan(project_dir, *, now, config_roots=None) -> Report`; pure classification separated from the git/stat probes so it tests without a repo.
2. `prawduct-hook worktrees [--json]`, registered as read-only in the hook's command sets.
3. Tests: each signal wins in turn; each class boundary; no-remote repo reports no branches; a branch contained in a remote ref other than the base (main vs develop) is NOT stranded; the probe never writes a sibling's index (mtime unchanged); every probe failure degrades, never raises; multiple config roots, newest wins.

## Chunk 02: briefing line + docs

**Type:** cumulative-final
**Done when:**
1. `assemble_session_briefing` renders the line from the Chunk 01 report; nothing when all counts are zero.
2. Tests: the line names no path/branch (extend the #410 guard, don't duplicate it); positive control that it appears; zero-state silence; a scan failure omits the line.
3. Docs: `plugin/CHANGELOG.md` rolling entry; `.prawduct/change-log.md`; any doc enumerating hook subcommands or briefing lines (grep, don't recall).
4. `/prawduct:critic cumulative`.
