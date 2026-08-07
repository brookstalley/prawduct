# Issue #221 — Worktree-fork state pollution: Design

`status: draft · stage: design · area: worktree · added: 2026-08-07 · source:
scheduled backlog session · issue: https://github.com/brookstalley/prawduct/issues/221`

Builds on `documentation/issues/221-requirements.md` (Decisions 1–5, requirements WT1–WT6). This
document resolves the requirements doc's named design-stage scope-out ("the exact detection/marker
mechanism and its storage location") and specifies file-by-file changes an implementation chunk can
follow directly.

Also resolves the open question the issue's second comment (2026-08-05, filed while building #594)
left unsettled: whether to consume `PostToolUse`/`CwdChanged` harness events as the marker's write
trigger. **Decision: yes, with a fail-open posture that costs nothing if the events never fire** —
see §2.

## Summary of what ships

1. **WT4** — a session-scoped **active-worktree marker** at
   `<git-common-dir>/prawduct/worktree-sessions/<epoch>.json`, keyed by a session epoch derived the
   same way `evidence.py._session_epoch()` already does (no new harness session-identity dependency).
2. **WT3** — the marker is written by a new `prawduct-hook record-active-worktree` subcommand,
   invoked by a new `PostToolUse` hook entry matching `EnterWorktree`/`ExitWorktree`. Consuming these
   events is a **detection source**, not a dependency on a harness *change* — see Decision 3 in the
   requirements doc and §2 below for why this doesn't violate WT3.
3. **WT1, WT2** — a new pre-dispatch guard, `_check_worktree_drift`, added to `main()` beside the
   two existing pre-dispatch guards (`_check_binary_skew`, `_check_ephemeral_worktree`), so every
   command inherits it automatically.
4. **WT5** — the guard reuses the existing `_ephemeral_command_writes` classifier to decide which
   commands it protects — no new enumerated skill list.
5. **WT6** — no change to `building.md` / `learnings.md`.

## 1. The session epoch (shared key, no new harness dependency)

**Where:** new function in `plugin/lib/gitstate.py`, exported for reuse by both the new
`record-active-worktree` command and the new guard.

**Mechanism:** `evidence.py:_session_epoch()` (`plugin/lib/evidence.py:96-105`) already derives a
session-identity string from `.prawduct/.session-start`'s mtime, specifically because the framework
has no harness-supplied session id available to every call site. That constraint is identical here:
the **writer** (a `PostToolUse` hook) receives `session_id` in its stdin JSON, but the **reader** (a
bare `prawduct-hook backlog add` invoked from inside a fork) receives no stdin JSON at all — it is a
plain CLI call. A key only the writer can produce is useless. `.session-start`'s mtime is readable by
both: the writer resolves it via `CLAUDE_PROJECT_DIR` (still pinned to the launch dir, unchanged by
`EnterWorktree`); the reader resolves it via the same env var, because a fork's `CLAUDE_PROJECT_DIR`
is *also* the unchanged launch-dir pin — the exact quantity this whole item is about.

Promote the logic to a shared helper rather than duplicating it:

```python
# plugin/lib/gitstate.py

def session_epoch(project_dir: Path) -> str | None:
    """Session-identity string derived from `.session-start`'s mtime.

    Moved here from evidence.py so record-active-worktree and the worktree-
    drift guard can share it without evidence.py depending on either. Nullable
    when no session marker exists (headless probes, fixtures) — never invented.
    """
    marker = get_prawduct_dir(project_dir) / ".session-start"
    try:
        mtime = marker.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
```

`evidence.py._session_epoch()` becomes a thin re-export (`from .gitstate import session_epoch as
_session_epoch`) so its existing callers and the module's public contract are unchanged.

**Known limitation, carried rather than solved here:** two Claude Code sessions launched
concurrently from the *same* launch directory (not the "two different worktrees" case WT4 requires
protecting — a third case neither the source issue nor the requirements doc names) share one
`.prawduct/.session-start` file and therefore one epoch. This is a pre-existing property of
`evidence.py`'s attribution mechanism, not a regression introduced here, and this item's scope is
the launch-dir-vs-worktree mismatch, not general concurrent-session identity. Recorded in Scope-out
(§7) rather than silently absorbed.

## 2. The marker: location, schema, write path

**Location:** `<git-common-dir>/prawduct/worktree-sessions/<epoch>.json`, where `<epoch>` is the
value from §1 with `:` replaced by `-` (filesystem-safe). Same subdirectory convention as the
evidence store (`evidence.py:STORE_SUBDIR = "prawduct"`) and the same rationale (D1 in
`.prawduct/artifacts/build-plan-kernel-evidence-store.md`): the one location every worktree of a
clone already shares, never committed, no gitignore contract, isolated between unrelated repos by
`git_common_dir()`'s existing equality test.

One file per epoch (not one shared file per repo) is what satisfies WT4: two sessions concurrently
active in two different worktrees of the same repo have two different launch-dir `.session-start`
files and therefore two different epochs, so they write two different marker files and cannot
clobber each other. A session-boundary `clear --session-start` rewrites `.session-start`'s mtime,
which changes the epoch — the old marker becomes unreachable from the new epoch and is orphaned,
not read as live. This mirrors `critic_marker.py`'s session-boundary self-heal (CRT-3X9D) applied to
a second, distinct invariant, as Decision 1 in the requirements doc anticipates.

**Schema:**

```json
{
  "schema": 1,
  "active_worktree": "/abs/path/to/worktree-toplevel",
  "updated_at": "2026-08-07T12:00:00Z",
  "event": "EnterWorktree",
  "session_id": "abc123-or-null"
}
```

`session_id` is carried when the writing hook's payload has one, purely for attribution/debugging —
never used as a lookup key (§1 explains why it can't be: the reader can't reproduce it).

**Write path — `prawduct-hook record-active-worktree`:**

```python
# plugin/bin/prawduct-hook

def cmd_record_active_worktree(stdin_payload: dict) -> int:
    """PostToolUse hook target for EnterWorktree/ExitWorktree. Best-effort,
    always exits 0 — this hook must never block the tool call it observes."""
    tool_name = stdin_payload.get("tool_name")
    new_cwd = stdin_payload.get("cwd")
    launch_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
    epoch = _gitstate().session_epoch(launch_dir)
    if epoch is None or not new_cwd:
        return 0  # no session marker yet, or payload missing the field — no-op

    marker_dir = _marker_dir(launch_dir)  # <git-common-dir>/prawduct/worktree-sessions/
    if marker_dir is None:
        return 0  # not a git repo — nothing to guard

    if tool_name == "ExitWorktree":
        _clear_worktree_marker(marker_dir, epoch)
        return 0

    top = _gitstate()._git_toplevel(Path(new_cwd))
    if top is None:
        return 0
    _write_worktree_marker(marker_dir, epoch, active_worktree=top,
                            event=tool_name, session_id=stdin_payload.get("session_id"))
    return 0
```

**hooks.json wiring** — new `PostToolUse` block, added after `SubagentStop`:

```json
"PostToolUse": [
  {
    "matcher": "EnterWorktree|ExitWorktree",
    "hooks": [
      {
        "type": "command",
        "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/bin/prawduct-hook\" record-active-worktree",
        "statusMessage": "Prawduct: tracking active worktree…"
      }
    ]
  }
]
```

**Why this doesn't violate WT3 / Decision 3.** The requirements doc forbids depending on the
harness *changing* how a fork's `cwd`/`CLAUDE_PROJECT_DIR` is set — that would leave every install
predating the change exposed indefinitely. Consuming an existing (or as-yet-unverified) `PostToolUse`
matcher is different in kind: it is a detection **source** for a marker prawduct itself writes and
reads, exactly the requirement's own wording. If the harness never fires the event, or fires it with
a different payload shape, `record-active-worktree` fails open (returns 0, writes nothing) and the
system is exactly as protected as it is today — no regression, just no improvement. **Nothing in the
guard (§3) depends on the marker existing.** This is the same fail-open posture `get_project_dir`
and `_check_ephemeral_worktree` already use for a broken/absent `lib/` import.

**Empirical verification is a precondition of implementation, not of this design.** The issue's
2026-08-05 comment explicitly flagged that `PostToolUse`/`CwdChanged` firing was "documentation, not
measurement." The build-plan chunk that implements this section's first done-when step MUST be
"observe `PostToolUse` with matcher `EnterWorktree` actually fire in a real session, with `cwd` and
`session_id` present in the payload, before the guard chunk is written" — if the event does not fire
as documented, this section's mechanism does not activate, but §3's guard (which only ever *reads*
the marker) degrades to a no-op rather than a crash, so the two chunks can still ship independently.

## 3. The guard: `_check_worktree_drift`

**Where:** `plugin/bin/prawduct-hook`, a new function beside `_check_binary_skew` and
`_check_ephemeral_worktree`, wired into `main()` at the same pre-dispatch site
(`plugin/bin/prawduct-hook:5599-5616`):

```python
if _check_binary_skew(command, project_dir) != 0:
    return 1
if _check_ephemeral_worktree(command, sys.argv[2:], project_dir) != 0:
    return 1
if _check_worktree_drift(command, sys.argv[2:], project_dir) != 0:
    return 1
```

This is the WT1 "shared choke point": one call site upstream of every `cmd_*` dispatch, matching the
two guards it sits beside rather than inventing a third pattern. `get_project_dir()` itself is left
unchanged — the guard reads the marker *in addition to* the already-resolved `project_dir`, rather
than folding drift-detection into the resolver, because `resolve_project_dir()` is a pure,
side-effect-free path function reused by both `bin` and `lib` callers (its own docstring: "never
raises"); a guard that can refuse and print needs a different shape than a resolver that never does.

```python
def _check_worktree_drift(command: str, argv: list[str], project_dir: Path) -> int:
    """0 to proceed; 1 when a command would mutate .prawduct/ state in a
    worktree that isn't this session's actual active one.

    Fail-open by construction (WT2's "never silent," not "always correct"):
    no marker, no epoch, or an unreadable marker all proceed as today.
    """
    if not _ephemeral_command_writes(command, argv, project_dir):
        return 0  # WT5: same "does this command mutate .prawduct/" classifier
                   # the ephemeral-worktree guard already uses — no new list.

    epoch = _gitstate().session_epoch(_launch_dir())
    if epoch is None:
        return 0
    active = _read_worktree_marker(_marker_dir(_launch_dir()), epoch)
    if active is None:
        return 0  # no EnterWorktree observed this session — nothing to check
    if active == project_dir.resolve():
        return 0  # resolved dir already matches the tracked active worktree

    print(
        f"BLOCKED: refusing `{command}` — this session's active worktree is "
        f"{active}, but this command resolved to {project_dir}. A `context: "
        "fork` skill's working directory does not follow EnterWorktree "
        "mid-session, so this write would land in the wrong working copy. "
        "Launch (or `/clear`) the session inside the worktree, or run the "
        "equivalent command from the main-loop Bash tool instead of a skill "
        "fork.",
        file=sys.stderr,
    )
    return 1
```

`_launch_dir()` is `Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()`, factored out since
both `record-active-worktree` and this guard need it.

**Why reusing `_ephemeral_command_writes` satisfies WT5 without a new list.** WT5 names
`advisory`/`backlog`/`critic` explicitly and folds `operator-verification` in "as a direct
consequence of WT1." `_ephemeral_command_writes` (`plugin/bin/prawduct-hook:5415-5445`) already
classifies exactly `advisory`, `backlog` (markdown-backend ops only — the service-backend carve-out
in `_backlog_is_service_backed` is correct here too: a network write against `--repo owner/repo`
cannot land in the wrong worktree), and the `critic-*` commands as writes, using the same allowlist
philosophy the ephemeral-worktree guard's comment documents (permissive-default, semantic, not
mechanically pinned). `operator-verification`'s mutating commands fall through to the classifier's
`return True` default (fail-closed for unlisted commands) and are covered automatically — matching
WT5's framing that this is free, not separate work.

**Refusal is unconditional, no override env var.** `_check_ephemeral_worktree` has
`_EPHEMERAL_OVERRIDE_ENV` because its refusal can trigger on a legitimate, intentional ephemeral
worktree with no better home for the write. This guard's refusal has no legitimate case to override:
if the marker and the resolved dir disagree, the write target is, by construction, not the worktree
the session believes it is in. The fix named in the message (launch/`/clear` in the worktree, or use
the main-loop Bash tool) is always available and is exactly `building.md:15`'s existing documented
mitigation (WT6) — the guard is what fires when someone doesn't follow it.

## 4. Marker read/write helpers

`plugin/lib/gitstate.py` gains three small functions alongside `session_epoch` (§1), following the
existing `atomic_write_text` (`core.py:124`) convention `critic_marker.py` uses:

```python
def worktree_marker_dir(project_dir: Path) -> Path | None:
    common = git_common_dir(project_dir)
    if common is None:
        return None
    return common / "prawduct" / "worktree-sessions"

def write_worktree_marker(marker_dir: Path, epoch: str, *, active_worktree: Path,
                           event: str, session_id: str | None) -> None:
    marker_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": 1,
        "active_worktree": str(active_worktree),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event": event,
        "session_id": session_id,
    }
    from .core import atomic_write_text
    atomic_write_text(marker_dir / f"{_safe_epoch(epoch)}.json", json.dumps(payload))

def clear_worktree_marker(marker_dir: Path, epoch: str) -> None:
    try:
        (marker_dir / f"{_safe_epoch(epoch)}.json").unlink()
    except FileNotFoundError:
        pass

def read_worktree_marker(marker_dir: Path | None, epoch: str) -> Path | None:
    """Resolve path, or None on any absence/corruption — fail-open per §3."""
    if marker_dir is None:
        return None
    try:
        data = json.loads((marker_dir / f"{_safe_epoch(epoch)}.json").read_text())
        return Path(data["active_worktree"]).resolve()
    except (OSError, ValueError, KeyError, TypeError):
        return None
```

No TTL like `critic_marker.py`'s `CRITIC_ACTIVE_TTL_SECONDS`: staleness here is bounded by the epoch
itself changing at the next session boundary (§2), not by wall-clock age, so an explicit TTL would be
redundant. Orphaned marker files (a session that entered a worktree and was never cleanly
`/clear`ed) are not actively pruned — a light disk-hygiene gap, not a correctness one, and pruning is
scoped out (§7) rather than solved here.

## 5. Files touched

| File | Change |
| --- | --- |
| `plugin/lib/gitstate.py` | add `session_epoch`, `worktree_marker_dir`, `write_worktree_marker`, `clear_worktree_marker`, `read_worktree_marker` |
| `plugin/lib/evidence.py` | `_session_epoch` becomes a re-export of `gitstate.session_epoch` |
| `plugin/bin/prawduct-hook` | add `cmd_record_active_worktree`, `_check_worktree_drift`, `_launch_dir`; wire both into `main()` (new `record-active-worktree` subcommand + new pre-dispatch guard call) |
| `plugin/hooks/hooks.json` | new `PostToolUse` block, matcher `EnterWorktree\|ExitWorktree` |
| `tests/` | new coverage — see §6 |

## 6. Testing strategy → Acceptance mapping

The requirements doc's acceptance criteria are behavioral (they describe a repro), so the build
chunk needs both a marker-mechanics unit layer and a guard-integration layer:

- **Marker read/write round-trip** (`test_gitstate.py` or new `test_worktree_marker.py`): write,
  read, clear, and corrupt-file fail-open cases for the four helpers in §4 — no git repo required
  beyond a `tmp_path` fixture with `git init` for `git_common_dir()`.
- **`_check_worktree_drift` unit tests** (`test_prawduct_hook.py`, beside the existing
  `_check_ephemeral_worktree`/`_check_binary_skew` tests): no marker → proceeds; marker matches
  resolved dir → proceeds; marker disagrees → refuses with exit 1 and both paths named in the
  message; command not in the write set → proceeds regardless of marker state (proves WT5's reuse
  of `_ephemeral_command_writes` is load-bearing, not decorative).
- **Two-epoch isolation test** — the direct WT4 acceptance criterion: two distinct epochs writing
  markers to the same `marker_dir` never read each other's `active_worktree`.
- **`record-active-worktree` payload-shape tests**: missing `cwd`, missing `session_id`, malformed
  JSON stdin, `ExitWorktree` clearing an existing marker — all exit 0 (never blocks the tool call).
- **Acceptance criterion 3** ("the fix requires no change to the harness to take effect") is not a
  unit test — it's satisfied by construction (§2's fail-open posture) and should be recorded as a
  design-time guarantee in the chunk's Critic review rather than asserted in code.
- **Acceptance criterion 1** (the source issue's literal repro) needs the empirical-verification
  step from §2 before it can be exercised end-to-end in a real session; until then, the unit layers
  above cover the guard and marker mechanics exhaustively, and the repro is the operator-verification
  entry that closes the loop (matching the pattern issue #183 is separately trying to keep from
  going write-only).

## 7. Scope-out (unchanged from requirements, plus one addition)

Carries forward the requirements doc's scope-out list verbatim (exact marker mechanism now
specified above resolves that one item; the rest — harness `EnterWorktree` behavior changes,
`operator-verification`-specific work beyond the free WT1 coverage, migrating products off the
markdown backlog backend, reconciling already-diverged backlog state — are unchanged).

Added by this design pass:

- **Concurrent sessions sharing one launch directory** (§1's named limitation) — a pre-existing
  `evidence.py` attribution property, not something this item's marker mechanism regresses or is
  positioned to fix.
- **Pruning orphaned marker files** (§4) — disk hygiene, not correctness; no user-visible symptom
  motivates it yet.
- **The empirical verification of `PostToolUse`/`EnterWorktree` firing** (§2) — a precondition the
  implementing chunk must run and record, not a design-stage decision; if it fails, §3's guard still
  ships (it degrades to today's behavior, not a regression) and this item's `PostToolUse` half moves
  back to the backlog pending a different detection source.

## 8. Evidence / references

- `documentation/issues/221-requirements.md` — Decisions 1–5, requirements WT1–WT6, this design's
  starting point.
- `plugin/lib/evidence.py:96-105` (`_session_epoch`) — the session-identity pattern §1 generalizes;
  `plugin/lib/evidence.py:70-82` (`store_path`) — the shared-git-common-dir location convention §2
  reuses.
- `plugin/lib/critic_marker.py` — the CRT-3X9D mutation-site guard and session-boundary self-heal
  pattern §2's marker lifecycle mirrors.
- `plugin/bin/prawduct-hook:5415-5445` (`_ephemeral_command_writes`), `:5490-5545`
  (`_check_ephemeral_worktree`), `:5561-5593` (`_check_binary_skew`), `:5599-5616` (`main`'s
  pre-dispatch guard site) — the precedent §3's guard is modeled on directly.
- `.prawduct/artifacts/build-plan-ephemeral-worktrees.md` (Scope-out) — names "Issue #221's
  cross-worktree mismatch guard (WT1–WT6)" as "a different predicate needing a session-scoped
  marker. Explicitly not started here," and separately floats a `PostToolUse:Write` matcher for a
  sibling detection gap — corroborates both this item's marker approach and that `PostToolUse` is
  already in the framework's design vocabulary, not a novel dependency.
- `.prawduct/artifacts/kernel-redesign-discovery.md:250-253` — lists `PreToolUse`/`WorktreeCreate`/
  `Remove` among available hook events, supporting §2's premise that `PostToolUse` is a real,
  documented harness surface.
- Issue #221 comment (2026-08-05) — the `PostToolUse`/`CwdChanged` proposal this design adopts,
  including its own caveat that firing was "documentation, not measurement" (§2's precondition).
