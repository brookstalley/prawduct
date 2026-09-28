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
      - "every fact has one home → conforms: the thresholds and the liveness classes live in `stranded_work.py`; the briefing, the subcommand and the advisory all render its report. Chunk 03 also gives `git worktree list` parsing one home (`gitstate.worktree_records`), replacing three copies"
      - "an independent reviewer never mutates the session it reviews → inapplicable, because no reviewer path changes"
      - "goals and verification bind; prescribed method is advice → conforms: Success binds; the chunk Done-when lists are method, and Chunk 03 records the departures the boundary review forced"
  - artifact: nonfunctional-requirements
    dispositions:
      - "proportionality ratchets both ways: a new control names its yield and emits it observably → conforms (from Chunk 03): the stranded-branch signal is an advisory, so the advisory store records each firing, dismissal and resolution per branch. Expected yield: stranded reviewed work found before someone rebuilds it (#898/#818, #640). The worktree-count briefing line is orientation, not a control — it gates and asks nothing"
      - "review wall-clock is P0 → inapplicable, because no review path changes"
      - "state-file growth is an advisory warning, never a hard block → inapplicable, because no state file's size behaviour changes"
      - "review rigor is stage-keyed → inapplicable, because no review path changes"
  - artifact: api-contract
    dispositions:
      - "whole-surface semantic versioning; no per-subcommand version → conforms: `worktrees` ships under the next patch; its `--json` carries a `schema_version` because agents parse it"
      - "exit codes are the contract; errors attributed, never stack traces → conforms: 0 = report produced (even partial — degraded signals are named in it), 2 = usage error; a probe failure is a field in the report, never a traceback"
      - "additive-first evolution → conforms: a new subcommand; no existing flag, exit code or key changes"
  - artifact: security-model
    dispositions:
      - "untrusted governance state is data, not instructions → conforms: the scan never reads transcript CONTENT, only file modification times; nothing it surfaces is a directive"
      - "a destructive operation requires owner approval at the operation level → conforms: the scan destroys nothing; the line tells the agent to report, and deletion stays an owner decision"
      - "a governed product's content leaves its repository only through a pinned, owner-approved surface → conforms: no network call; the remote comparison reads remote-tracking refs already on disk"
  - artifact: data-model
    dispositions:
      - "two stores, two lifetimes: committed answers vs per-clone gitignored nags → conforms: the stranded-branch advisory is a per-clone nag in the advisory store; a dismissal stays in this clone"
      - "facts are immutable and append-only; governance verdicts from the fact ledger → inapplicable, because nothing here writes or reads review facts"
      - "derived views are never authoritative → conforms: the briefing line and the table are views of a fresh scan; no gate reads either"
      - "a newer-schema fact is a loud block → inapplicable, because no fact is written; `worktrees --json` carries its own `schema_version`"
      - "a governance document reaches a terminal state, never deleted → conforms: this plan is archived when its work ships"
      - "backlog issues conform to §1 title rules; backlog_service_repo selects the store → inapplicable, because nothing here writes the backlog"
---

# Build Plan: stranded-work

## Problem

Finished work gets stranded where nobody sees it. Observed: #898 and #818 sat reviewed on a
local-only branch for a day while the next triage session planned to build #898 from scratch
(2026-09-28), and #640's fix sat unmerged on a local branch 281 commits behind develop until a
later PR re-applied it (2026-09-19). Separately, a clone accumulates worktrees (7 in this one)
with no signal of which have a live agent and which were abandoned.

## Success

- Each stranded branch raises its own session-start **advisory** (from Chunk 03), naming the
  branch: dismissible with a reason, and resolved on its own once the branch is pushed or
  deleted. A branch checked out nowhere is nobody's live work, so naming it is safe.
- Sibling **worktrees** appear only as counts in one briefing line, e.g.
  `Worktrees: 3 idle 7+ days (1 with uncommitted changes) · 1 other has an agent active …`,
  naming no path or branch (owner ruling on #410, reaffirmed 2026-09-28: counts plus a
  command). No line when every count is zero; a line saying so when the scan could not run.
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

(A `[DECISION]` exempting the line from yield emission stood here until Chunk 03. Its two premises were false — the ledger is gitignored, and reflogs record neither briefing lines nor a deleted branch — and routing branches through the advisory roster removed the need for it.)

## Status

- [ ] Chunk 01: scan + `worktrees` subcommand
- [ ] Chunk 02: briefing line + docs
- [ ] Chunk 03: stranded branches become an advisory; one worktree parser; review fixes

## Chunk 01: scan + `worktrees` subcommand

**Foreign API:** Claude Code transcript directory layout.
**Done when:**
0. verify-api — confirm the encoding and the per-root layout against real directories on this machine (path containing `.`, `/`, `-`), and record what was observed in the change-log entry.
1. new `plugin/lib/stranded_work.py`: `scan(project_dir, *, now, config_roots=None) -> Report`; pure classification separated from the git/stat probes so it tests without a repo.
2. `prawduct-hook worktrees [--json]`, registered as read-only in the hook's command sets.
3. Tests: each signal wins in turn; each class boundary; no-remote repo reports no branches; a branch contained in a remote ref other than the base (main vs develop) is NOT stranded; the probe never writes a sibling's index (mtime unchanged); every probe failure degrades, never raises; multiple config roots, newest wins.

## Chunk 02: briefing line + docs

**Done when:**
1. `assemble_session_briefing` renders the line from the Chunk 01 report; nothing when all counts are zero.
2. Tests: the line names no path/branch (extend the #410 guard, don't duplicate it); positive control that it appears; zero-state silence; a scan failure omits the line.
3. Docs: `plugin/CHANGELOG.md` rolling entry; `.prawduct/change-log.md`; any doc enumerating hook subcommands or briefing lines (grep, don't recall).
4. `/prawduct:critic cumulative`.

## Chunk 03: stranded branches become an advisory; one worktree parser; review fixes

**Type:** cumulative-final
**Why this chunk exists:** the boundary review (rev-20260928T144218Z-e80497b2) found #843's
design — `documentation/issues/843-design.md`, never consulted while planning — already rules
this signal belongs in the advisory roster ("a visible, dismissible signal, not a refusal",
owner 2026-09-19). Owner decision 2026-09-28: stranded BRANCHES move to the advisory roster
(dismissible, self-resolving, firings recorded by the advisory store — which also retires the
yield-emission `[DECISION]`); WORKTREE counts stay a briefing line (orientation, not a nag);
the three `git worktree list` parsers become one, as #843 Decision 4 specifies. This ships
#843's local-only arm; #843 stays open for its plan-ticked + never-PR'd arm (network).
**Done when:**
1. `gitstate.worktree_records(project_dir)` — moved from `adhoc_delegate_probes._worktree_records`
   (#843 Decision 4); `adhoc_delegate_probes`, `briefing._detect_worktrees` and `stranded_work`
   all read it. Prunable/detached handled once.
2. `evidence.run_git` decodes with `errors="surrogateescape"` — a non-UTF-8 ref or filename
   no longer raises through every caller (the blocking finding's class, not its instance).
   `stranded_work` uses `run_git` with `GIT_OPTIONAL_LOCKS=0`, not a private runner.
3. New probe `stranded-branch` (feature `branch-landing`, as #843 names it): one advisory per
   stranded branch, naming it, `recommended_action` a read-only `git log`. Registered in
   `probe_families.register_all`. The briefing line drops its branch clause.
4. Scan-level fixes: `rev-list --count` only in `prawduct-hook worktrees`, with `refs/heads/<name>`
   (no ref/path ambiguity); a total time budget; a MISSING worktree's branch counts as not
   checked out; `briefing_line` says so when the scan could not run instead of going silent;
   the scan call in `briefing.py` cannot take down the briefing (test with a raising scan).
5. Wording: the briefing line defers to advisories and the user rather than forbidding every
   touch of another worktree (the delegate-worktree advisory legitimately directs cleanup).
6. Tests: every git-call failure path; `--json` keys pinned; the advisory fires, names the
   branch, and resolves when the branch is pushed or deleted.
7. Plan frontmatter: dispositions for every Direction norm in the three governing artifacts;
   the yield `[DECISION]` removed (the advisory store now records firings).
8. `documentation/issues/843-design.md` + #843 comment: what shipped here, what stays open.
9. `/prawduct:critic cumulative`.
