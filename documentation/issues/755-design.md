# Issue #755 — Backlog-Service: No Durable Record When a Detached Refresh Fails: Design

`status: draft · stage: design · area: backlog-service · added: 2026-09-17 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/755`

No separate requirements pass — the issue's own Problem/Proposed change/Acceptance/Scope-out
sections are the requirements; this document resolves them into file-by-file changes.

## Root cause

`sync.spawn_warm` and `snapshot.spawn_refresh` are the same D6 shape (fire-and-forget detached
subprocess) over the same `transport.spawn_detached` mechanism, but only one of the two stores an
attempt has a durable outcome:

- **`sync.py`** wraps every write path in `_recording()`, which calls
  `cache.record_sync_attempt(conn, scope, attempted_at=..., failure=...)` on **both** exits —
  success clears `cursor.last_error`, failure stamps it. `cache.sync_health()` reads it back.
  (#625 fixed the one caller, `cli._run_sync`, that had been bypassing this — see `_record_attempt`'s
  docstring in `sync.py`.)
- **`snapshot.py`** has no equivalent. `query.refresh_counts()`'s own docstring says the quiet part
  out loud: "On a backend failure it returns the error envelope and writes **nothing**." There is no
  cursor-like row in the JSON snapshot store at all — `write()` only ever runs on success.

So `briefing._backlog_pending_line`'s `elif warmed:` branch (`briefing.py:1253-1256`) cannot tell
"the warm just fired, give it a session" from "the warm has been firing and failing for a week" —
both look identical from the only state it can see (`snap is None`, `warmed is True`). It prints
`Backlog: counts warming for {scope}` forever, exactly the case #625 scoped for the cache side and
left standing for the snapshot side.

## Summary of what ships

1. `snapshot.py` gains `record_attempt()` (write) and `refresh_health()` (read) — the same
   `last_attempt_at`/`last_error` pair `cache.py` already carries on `cursor`, adapted to a JSON
   file. `write()` itself is extended to stamp the same two fields on success, so a success and a
   failure both leave one attempt record behind.
2. `core.py` gains `failure_text()`, promoted out of `sync.py`'s private `_failure_of()` so
   `query.refresh_counts` can build the same envelope-to-string it already builds for the cache side,
   instead of a second copy.
3. `query.refresh_counts()` calls `snapshot.record_attempt()` on its failure exit (today: silent
   early return) — the success exit already gets a record for free from `write()`'s extension.
4. `briefing._backlog_pending_line()` reads `refresh_health()` alongside the snapshot and
   distinguishes three states instead of two: has-counts (unchanged, now with a failing-refresh
   annotation when relevant), never-had-counts-but-warming, and never-had-counts-and-stuck.
5. A regression test drives a real failing `refresh_counts` call (via the existing `FakeGitHub`
   `set_unreachable(True)` fixture) and asserts a durable record survives it — pinning acceptance
   criterion 3 ("a new detached refresh cannot ship without an outcome record") the same way
   `test_backlog_cli.py`'s cache-side tests already pin the cache's half.

## Section 1 — `plugin/lib/backlog/snapshot.py`: attempt record

**Data model.** Each scope's entry in `backlog-counts.json` gains two fields, sibling to `counts`/
`fetched_at`:

```json
{"counts": {...}, "fetched_at": "...", "last_attempt_at": "...", "last_error": null}
```

Additive and tolerant: `read()` only ever looks at `"counts"`/`"fetched_at"`, so an old snapshot
predating these keys (or a fresh one that never got a successful write) renders exactly as it does
today — no migration, matching the `untriaged` key's precedent (`briefing.py`'s
`_untriaged_qualifier` docstring).

**Refactor `write()` to share the atomic-dump step**, so `record_attempt()` doesn't duplicate the
tempfile/`os.replace` dance:

```python
def _atomic_dump(path: Path, data: dict) -> dict:
    """The tempfile + os.replace write shared by write() and record_attempt().
    Returns {"status": "written", "path"} or {"status": "error", "reason"} — never raises."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(data, handle)
            os.replace(tmp, path)
        finally:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
    except OSError as exc:
        return {"status": "error", "reason": f"{type(exc).__name__}"}
    return {"status": "written", "path": str(path)}


def write(path: Path, scope: str, counts: dict, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    fetched_at = _iso(now)
    data = _load(path)
    # A success clears any standing failure — mirrors cache.record_sync_attempt's
    # "the two columns move together" contract (#755): a good refresh must not
    # leave a stale error sitting beside fresh counts.
    data["scopes"][scope] = {
        "counts": counts,
        "fetched_at": fetched_at,
        "last_attempt_at": fetched_at,
        "last_error": None,
    }
    result = _atomic_dump(path, data)
    if result["status"] != "written":
        return result
    return {"status": "written", "path": result["path"], "fetched_at": fetched_at}
```

**New: `record_attempt()`** — the failure-side write. Unlike `cache.record_sync_attempt` (UPDATE-only
by design, because a minted row would falsely claim "this scope has synced"), the JSON store has no
existence-implies-succeeded concern: `read()` already gates on `"counts" not in entry`, so an
attempt-only entry (no `counts` yet) correctly keeps reading as "no snapshot" while still being
visible to `refresh_health()`. That asymmetry from `cache.py` is deliberate, not an oversight — call
it out in the docstring so a future reader doesn't "fix" it into matching the cursor table.

```python
def record_attempt(path: Path, scope: str, *, error: str, now: datetime | None = None) -> dict:
    """Stamp a FAILED refresh attempt, leaving `counts`/`fetched_at` untouched.

    The failure-side half of the pair `write()` completes on success. Never
    clobbers a prior good snapshot (#755's own acceptance: the last good counts
    must survive) — only `last_attempt_at`/`last_error` move. Unlike
    `cache.record_sync_attempt`, this MAY create the scope's entry: a snapshot
    that has never once succeeded still deserves a record of "it has been
    tried, and it is failing" (the exact case this issue is filed against), and
    there is no cursor-table existence check here for a minted entry to corrupt.
    Best-effort — a failure to record a failure must not raise.
    """
    now = now or datetime.now(timezone.utc)
    attempted_at = _iso(now)
    data = _load(path)
    entry = data["scopes"].setdefault(scope, {})
    entry["last_attempt_at"] = attempted_at
    entry["last_error"] = error
    return _atomic_dump(path, data)
```

**New: `refresh_health()`** — the read half, mirroring `cache.sync_health`'s shape and its "a
non-`None` `last_error` is the live claim the most recent attempt failed" semantics, plus a visible
age on the attempt itself (parallel to `read()`'s `age_seconds` on the counts):

```python
def refresh_health(path: Path, scope: str, *, now: datetime | None = None) -> dict | None:
    """`{"last_attempt_at", "last_error", "attempt_age_seconds"}` for scope, or
    `None` if no attempt has ever been recorded — including a scope `read()`
    has never heard of. Touches no network (same BLOCK-5 contract as `read()`).
    """
    entry = _load(path)["scopes"].get(scope)
    if not isinstance(entry, dict) or "last_attempt_at" not in entry:
        return None
    now = now or datetime.now(timezone.utc)
    return {
        "last_attempt_at": entry.get("last_attempt_at"),
        "last_error": entry.get("last_error"),
        "attempt_age_seconds": _age_seconds(entry.get("last_attempt_at"), now),
    }
```

## Section 2 — `plugin/lib/backlog/core.py`: shared `failure_text()`

Promote `sync.py`'s private `_failure_of()` (currently duplicating the "error envelope → one string"
shape query.refresh_counts now also needs) into `core.py`, unchanged in behavior:

```python
def failure_text(result: dict) -> str | None:
    """The failure text of an error envelope, or None when it succeeded.
    Shared by every writer that stamps an attempt outcome (sync.py, snapshot.py)."""
    if not isinstance(result, dict) or result.get("status") != "error":
        return None
    err = result.get("error") or {}
    code, message = err.get("code"), err.get("message")
    return f"{code}: {message}" if code and message else (message or code or "error")
```

`sync.py`'s `_failure_of` becomes a thin re-export (or its three call sites switch to
`core.failure_text` directly) — cosmetic, not behavior-changing, and keeps one implementation for a
shape now used by two writers rather than growing a second copy the next reviewer has to notice are
supposed to stay identical.

## Section 3 — `plugin/lib/backlog/query.py`: `refresh_counts()` records both exits

```python
def refresh_counts(
    transport: Transport, *, project_dir: Path, owner: str, repo: str, now: datetime | None = None,
) -> dict:
    result = counts(transport, owner=owner, repo=repo)
    scope = f"{owner}/{repo}"
    path = snapshot.snapshot_path(project_dir)

    if result.get("status") != "ok":
        # #755: a failing refresh must leave a durable record too, not only a
        # succeeding one — this is the exit that previously wrote nothing at all.
        if path is not None:
            snapshot.record_attempt(path, scope, error=core.failure_text(result), now=now)
        return result  # backend down — do NOT clobber the last good snapshot

    data = dict(result["data"])
    warnings = list(result.get("warnings") or [])

    if path is None:
        warnings.append("counts not persisted: not inside a git repository")
        data["persisted"] = False
        data["fetched_at"] = None
    else:
        written = snapshot.write(path, scope, result["data"], now=now)
        if written.get("status") == "written":
            data["persisted"] = True
            data["fetched_at"] = written.get("fetched_at")
        else:
            warnings.append(f"counts not persisted: {written.get('reason')}")
            data["persisted"] = False
            data["fetched_at"] = None
    return ok(data, warnings)
```

Only the new failure-path block is added; the success path is unchanged (it already routes through
`write()`, which Section 1 extends to stamp the same attempt fields for free).

## Section 4 — `plugin/lib/briefing.py`: `_backlog_pending_line` tells stuck from warming

```python
scope = read_str_yaml_key(prawduct_dir / "project-state.yaml", "backlog_service_repo")
if scope:
    from .backlog import encode, snapshot  # noqa: PLC0415

    path = snapshot.snapshot_path(project_dir)
    snap = snapshot.read(path, scope, now=now) if path else None
    health = snapshot.refresh_health(path, scope, now=now) if path else None
    failing = bool(health and health.get("last_error"))
    warmed = _spawn_snapshot_warm(project_dir, scope, popen=popen)
    _spawn_cache_warm(project_dir, scope, popen=popen)

    line = None
    if snap and isinstance(snap.get("counts"), dict):
        by_status = snap["counts"].get("by_status") or {}
        pending = sum(by_status.get(status, 0) for status in encode.OPEN_STATUSES)
        if pending:
            age = _humanize_age(snap.get("age_seconds"))
            line = (
                f"Backlog: {pending} pending{_untriaged_qualifier(snap['counts'])} "
                f"on {scope} (snapshot {age}; /prawduct:backlog to triage)"
            )
            if failing:
                # The warm-then-always-failing case #625 scoped for the cache side:
                # a growing snapshot age alone is easy to misread as "quiet", not
                # "broken". Say so, using the same command a stuck operator needs.
                attempt_age = _humanize_age(health.get("attempt_age_seconds"))
                line += (
                    f" — refresh failing ({attempt_age}); run `prawduct-hook backlog "
                    f"refresh-counts --repo {scope}` to see the error"
                )
    elif failing:
        # #755's motivating case: never had counts, and the recorded attempt
        # says why — "warming" would be a standing falsehood at this point.
        line = (
            f"Backlog: counts stuck for {scope} — background refresh keeps failing "
            f"({health['last_error']}); run `prawduct-hook backlog refresh-counts "
            f"--repo {scope}` (/prawduct:backlog to triage)"
        )
    elif warmed:
        line = f"Backlog: counts warming for {scope} (/prawduct:backlog to triage)"
    else:
        line = (
            f"Backlog: counts unavailable for {scope} — background refresh "
            f"could not start; run `prawduct-hook backlog refresh-counts "
            f"--repo {scope}` (/prawduct:backlog to triage)"
        )
    return line
```

`health` is read **before** the warm fires, same reasoning the existing comment gives for reading
`snap` first: "the warm's outcome decides what the no-snapshot line may honestly claim, so its result
is never discarded" — a `health` read one warm-cycle stale is what the line describes, since the warm
just fired for *this* session hasn't reported back yet.

## Files touched

| File | Change |
|---|---|
| `plugin/lib/backlog/snapshot.py` | New `_atomic_dump()`, `record_attempt()`, `refresh_health()`; `write()` extended to stamp `last_attempt_at`/`last_error` |
| `plugin/lib/backlog/core.py` | New `failure_text()` (promoted from `sync.py`'s `_failure_of`) |
| `plugin/lib/backlog/sync.py` | `_failure_of` calls become `core.failure_text` (or a thin alias) — no behavior change |
| `plugin/lib/backlog/query.py` | `refresh_counts()` calls `snapshot.record_attempt()` on the failure exit |
| `plugin/lib/briefing.py` | `_backlog_pending_line()` reads `refresh_health()`, adds the stuck branch and the failing-refresh annotation |
| `tests/test_backlog_governance.py` | New `TestSnapshot`/`TestRefreshCounts` cases (below) |
| `tests/test_briefing_functions.py` | New `TestBacklogPendingLine` cases (below) |

## Test plan

Following the existing files' own style — real `FakeGitHub` transport, real JSON files under
`tmp_path`, no mocking of the snapshot module itself (`test_backlog_governance.py`'s
`TestSnapshot`/`TestRefreshCounts` classes are the direct precedent; `test_briefing_functions.py`'s
`TestBacklogPendingLine` is the other).

`tests/test_backlog_governance.py`:

1. **`TestSnapshot.test_record_attempt_creates_entry_with_no_counts`** — `record_attempt` on a scope
   never written before → `refresh_health()` returns the error and attempt age; `read()` still
   returns `None` (no counts exist).
2. **`TestSnapshot.test_record_attempt_preserves_existing_counts`** — write good counts, then
   `record_attempt(error=...)` for that scope → `read()` still returns the untouched counts and
   `fetched_at`; `refresh_health()` shows the new error. This is the direct pin for acceptance
   criterion 1 combined with the "never clobber" invariant the issue's Scope-out inherits from #625.
3. **`TestSnapshot.test_write_after_record_attempt_clears_the_error`** — `record_attempt(error=...)`
   then `write()` for the same scope → `refresh_health()["last_error"]` is `None` again. Pins "the
   two columns move together," the same property `cache.record_sync_attempt`'s docstring states for
   the cache side.
4. **`TestRefreshCounts.test_backend_down_leaves_a_durable_attempt_record`** — extends the existing
   `test_backend_down_returns_unavailable_and_does_not_clobber` fixture (`fake.set_unreachable(True)`,
   real `query.refresh_counts` call, no mocking of `snapshot`): after the failing call,
   `snapshot.refresh_health(path, SCOPE)["last_error"]` is non-`None` and names the failure, mirroring
   `test_backlog_cli.py`'s `last_error` assertions for the cache side (`assert "unavailable" in
   last_error` style, not a substring of an internal exception type). This is the acceptance-criterion-3
   regression pin: a future refactor of `refresh_counts` that drops the new call fails this test, not
   only a code-review re-read.
5. **`TestRefreshCounts.test_backend_recovery_clears_a_prior_failure`** — fail once (as in 4), then
   succeed → `refresh_health()["last_error"]` is `None` again, via the `write()` extension in Section 1
   rather than a second explicit call.

`tests/test_briefing_functions.py` (`TestBacklogPendingLine`):

1. **`test_post_cutover_never_synced_and_failing_reads_stuck_not_warming`** — no snapshot written;
   call `snapshot.record_attempt(path, scope, error="unavailable: gh auth failed")` directly (as the
   detached child would have), then call `_backlog_pending_line`. Assert the line contains `"stuck"`
   and the recorded error text, and does **not** contain `"warming"` — the direct sibling of the
   already-existing `test_post_cutover_warm_that_never_starts_does_not_claim_warming`, same shape,
   different exit.
2. **`test_post_cutover_stale_snapshot_and_failing_annotates_the_pending_line`** — write good counts
   with an old `now`, then `record_attempt(error=...)` with a newer `now`; call
   `_backlog_pending_line` at a `now` past both. Assert the existing `"N pending on {scope}"` text is
   still present (never regress the has-counts path) **and** the line also names the failing refresh.
3. **`test_post_cutover_recorded_failure_cleared_by_a_later_success_stays_silent`** — record a
   failure, then `snapshot.write()` a fresh success at a later `now`; assert the resulting line
   matches the pre-#755 has-counts shape exactly (no stuck/failing text) — the "cleared" half of the
   pair, so a fixed-but-still-warm operator doesn't see a stale accusation.

## Open items for the build chunk (not resolved here)

- Exact wording of the stuck-line and the failing-annotation (cosmetic; kept close to the existing
  "counts unavailable ... could not start" sibling line's register for consistency).
- Whether `sync.py`'s `_failure_of` is deleted outright in favor of `core.failure_text` or kept as a
  one-line alias during the transition — either is fine; the design only requires one implementation
  to review, not one particular deletion timeline.

## Acceptance (carried from the issue, now with an implementation path)

- [ ] A failing `refresh-counts` leaves a durable attempt/error record — `snapshot.record_attempt()`
      called from `query.refresh_counts()`'s failure exit; pinned by `TestRefreshCounts` case 4.
- [ ] The briefing says stuck, not warming, after repeated failure — `_backlog_pending_line`'s new
      `elif failing:` branch; pinned by `TestBacklogPendingLine` case 1, with case 2 covering the
      has-counts variant the issue's own wording ("warming... at EVERY session start") implies should
      also stop reading as silently fine.
- [ ] A new detached refresh cannot ship without an outcome record — `write()` and `record_attempt()`
      are the only two ways a caller can complete a refresh attempt in this design, and both now stamp
      the pair; `TestRefreshCounts` cases 4–5 regression-pin that neither path can regress to writing
      nothing without a test going red.

## Evidence / references

- `plugin/lib/backlog/sync.py:56-99` (`_recording`, `_record_attempt`, `_failure_of`) — the shipped
  precedent this design mirrors for the snapshot store.
- `plugin/lib/backlog/cache.py:960-1006` (`record_sync_attempt`, `sync_health`) — the exact two-column
  shape and "moves together" contract adapted here to a JSON file instead of a SQLite row, and the
  UPDATE-only-vs-may-create asymmetry called out explicitly in Section 1.
- `plugin/lib/backlog/snapshot.py` (`_load`, `write`, `read`, `_age_seconds`) — the store this design
  extends; `write()`'s "merges into the scope-keyed map" comment is the precedent for treating the new
  fields as additive.
- `plugin/lib/backlog/query.py:399-441` (`refresh_counts`) — the docstring already states the gap
  ("writes **nothing**" on failure) this design closes.
- `plugin/lib/briefing.py:1206-1267` (`_backlog_pending_line`), `:1300-1307` (`_spawn_snapshot_warm`) —
  the read-before-warm ordering this design preserves, and the exact branch (`elif warmed:`) the issue
  names.
- `tests/test_backlog_governance.py:73-177` (`TestSnapshot`, `TestRefreshCounts`) — the fixture style
  (`_make_repo`, `FakeGitHub.set_unreachable`) the new cases extend rather than replace.
- `tests/test_briefing_functions.py:1574-1729` (`TestBacklogPendingLine`) — in particular
  `test_post_cutover_warm_that_never_starts_does_not_claim_warming`, the direct sibling regression
  test for the "never claim warming falsely" property this design's stuck branch generalizes.
- `tests/test_backlog_cli.py:657-742` — the cache-side "drive a real failure through the real path,
  then read the health record" test shape this design's `TestRefreshCounts` cases follow instead of
  mocking `snapshot`.
- Issue #625 (`brookstalley/prawduct#625`) — the cache-side fix this issue's own Problem section says
  covered only "one member" of the same two-warm shape.
