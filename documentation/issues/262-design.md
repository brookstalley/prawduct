# Issue #262 — Cross-project review-telemetry aggregation: Design

`status: draft · stage: design · area: governance/telemetry · added: 2026-08-04 · source:
scheduled backlog session · issue: https://github.com/brookstalley/prawduct/issues/262`

Builds on `documentation/issues/262-requirements.md` (Decisions 1–3, requirements TEL1–TEL6). This
document resolves the requirements doc's named design-stage scope-out items — the exact CLI
surface, the cross-project rollup shape, and the `/prawduct:janitor` wiring — and specifies file-
by-file changes an implementation chunk can follow directly.

## Summary of what ships

1. **TEL1** — `plugin/lib/ledger.py`'s event envelope gains a `plugin` field.
2. **TEL2** — `prawduct-hook review-stats --json` gains a top-level `plugin_versions` field.
3. **TEL3–TEL6** — a new `prawduct-hook aggregate-review-stats` command.
4. Documentation and `/prawduct:janitor` wiring for the new surface.

## 1. Ledger envelope: the `plugin` field (TEL1)

**Where:** `plugin/lib/ledger.py`, `ledger_append()`, the `event = {...}` construction
(currently `plugin/lib/ledger.py:260-274`).

**Mechanism:** reuse `evidence.py`'s existing `_plugin_version()` (`plugin/lib/evidence.py:88-94`
— reads `plugin/VERSION`, returns the stripped text or `None`, never invents a value). `evidence.py`
imports only `gitstate` at module scope (confirmed: no `ledger` import anywhere in `evidence.py`),
so `ledger.py` importing from `evidence.py` introduces no cycle. Add a module-level import:

```python
from .evidence import _plugin_version
```

alongside the existing `from . import gitstate` / `from .core import resolve_build_plan_path` at
the top of `ledger.py` — module-level, not lazy, because there is no cycle to avoid (unlike the
existing lazy `gates`/`coverage`/`views` imports in this file, each of which exists specifically to
break a real cycle or defer a heavy submodule).

**Envelope change:** add one key to the dict built in `ledger_append`:

```python
event = {
    "schema_version": LEDGER_SCHEMA_VERSION,
    "event": event_kind,
    "ts": ...,
    "duration_seconds": duration,
    "project": project_dir.resolve().name,
    "scope": scope,
    "chunk": chunk,
    "plugin": _plugin_version(),
    "actor": {"role": _EVENT_ROLES[event_kind], "model": actor_model},
    "git": {...},
    "review": record,
}
```

Placed after `chunk` and before `actor` — envelope fields stay grouped (identity/attribution
fields together, ahead of the nested `actor`/`git`/payload blocks), matching the existing visual
grouping in the dict literal.

**Compatibility:** additive envelope key. `LEDGER_SCHEMA_VERSION` (currently `1`) does **not**
bump — the module docstring's existing contract is "consumers skip unknown event kinds and unknown
fields," and every reader (`_read_events` in `telemetry.py`, `iter_events_newest_first`,
`review_event_exists`) already reads events as loosely-typed dicts via `.get()`, so a new optional
key is invisible to every non-updated reader. A ledger line written before this ships simply lacks
`plugin`; every reader treats a missing key as `None`, never a parse error — this is the same
posture `duration_seconds` and `actor.model` already use ("nullable, never invented").

**Test change:** `tests/test_governance_ledger.py` pins the envelope field-by-field (per its module
docstring, "Envelope correctness is the schema contract... so it is pinned field by field here").
Add one assertion: the appended event's `"plugin"` key equals `plugin/VERSION`'s stripped content
(read the file directly in the test, not via the production helper, to keep the pin independent of
the implementation it's checking).

## 2. Per-project `plugin_versions` (TEL2)

**Where:** `plugin/lib/telemetry.py`.

**Row extraction — `_extract_row()` (currently lines 136–160):** add one field, reading the new
envelope key:

```python
"plugin": event.get("plugin") if isinstance(event.get("plugin"), str) else None,
```

placed alongside the other envelope-level reads (`role`, `model`, `scope`) at the top of the
function — same non-invented-value posture as `role`/`model`.

This is the single hook point: because `aggregate_review_stats()` and the future cross-project
aggregator (§3) both consume the row list `_extract_row` produces, adding `plugin` here makes it
available to both without a second read path.

**Aggregation — new helper:**

```python
def _plugin_versions(rows: list[dict]) -> dict:
    """Distinct plugin versions seen, plus how many rows carried none."""
    known = sorted({r["plugin"] for r in rows if r["plugin"]})
    unlabeled = sum(1 for r in rows if not r["plugin"])
    return {"known": known, "unlabeled_events": unlabeled}
```

Returns an object rather than a bare list so "zero versions because zero events" and "some events,
none labeled" stay distinguishable from each other and from a genuinely single-version project —
directly satisfies the requirements doc's acceptance criterion ("degrades to null/unknown, not a
crash or a guessed version").

**Wiring into `aggregate_review_stats()` (currently lines 212–241):** add one line to the returned
dict, positioned after `skipped` and before `overall` (grouping the "what shape is this data"
metadata — schema, counts, skip reasons, version provenance — ahead of the actual stat groupings):

```python
return {
    "schema_version": REPORT_SCHEMA_VERSION,
    "events_total": len(rows),
    "skipped": dict(skipped),
    "plugin_versions": _plugin_versions(rows),
    "overall": _group_stats(rows),
    ...
}
```

**Schema version bump:** this is a new top-level key in the `--json` contract, so per the module
docstring ("key changes bump `REPORT_SCHEMA_VERSION`") — bump `REPORT_SCHEMA_VERSION` from `1` to
`2`. Update the pinned schema-version assertion in `tests/test_review_stats.py` and add a
docstring/comment note at the bump site (existing convention — see the `_canonical_model` comment
explaining why *that* change did NOT bump the version, for contrast).

**Human rendering (`_render_human`, lines 257–289):** add one line after the `events:` line:

```python
plugin_line = (
    f"plugin: {', '.join(report['plugin_versions']['known']) or '(none recorded)'}"
    + (f", {report['plugin_versions']['unlabeled_events']} event(s) unlabeled"
       if report['plugin_versions']['unlabeled_events'] else "")
)
```

**Doc update:** `plugin/docs/governance-telemetry.md`'s "The `--json` contract" section lists
top-level keys in order — insert `plugin_versions` into that list (after `skipped`, matching the
code), and add the envelope field to the JSON example block in "The event ledger" section (`"plugin":
"3.2.3"` alongside the existing example fields).

## 3. `aggregate-review-stats` (TEL3–TEL6)

### CLI surface

```
prawduct-hook aggregate-review-stats <path> [<path> ...] [--from-file <list-path>] [--json]
```

- **Positional `<path>` arguments** and **`--from-file`** are both accepted and additive (an
  operator can name a couple of paths inline and pull the rest from a saved list); duplicates
  (by resolved absolute path) collapse to one entry.
- **`--from-file <list-path>`**: one path per line; blank lines and lines starting with `#` are
  skipped (comment convention, no precedent to match elsewhere in this repo, chosen for
  readability of a hand-maintained list). Paths in the file are interpreted the same way positional
  paths are (see below) — relative to the invoking shell's CWD, not relative to the list file's own
  location. This asymmetry (list-relative would arguably be less surprising for a portable list
  file) is deliberately simple for v1; not solved here because TEL5 already rules out prawduct
  persisting or portability-managing this file — it is entirely the operator's own artifact.
- **No paths supplied at all** (neither positional nor a non-empty `--from-file`): usage error,
  exit 1 — mirrors `review_stats`'s "Exit 1 only on bad arguments" contract.
- **`--json`**: same on/off flag semantics as `review-stats --json`.
- Unknown flags: exit 1 with a usage message (matches every other subcommand's argument-loop
  posture in this file).

### Path resolution and per-path outcomes

Each named path is treated as a **project directory** — mirroring how `review_stats(project_dir,
argv)` already treats its single `project_dir` argument (`plugin/lib/telemetry.py:306-307`:
`gitstate.get_prawduct_dir(project_dir)` then `ledger_path(prawduct_dir)`). For each resolved path,
one of three outcomes:

| Condition | Outcome |
|---|---|
| Path does not exist, or is not a directory | Skipped — `reason: "invalid-path"` |
| Path resolves to a project dir, but `.prawduct/.governance-ledger.jsonl` does not exist | Skipped — `reason: "no-ledger"` |
| Ledger file exists but `path.read_text()` raises `OSError` | Skipped — `reason: "unreadable-ledger"` |
| Ledger file exists and is readable | **Included** — full per-project report attached (§below), even if every line in it turns out corrupt (that degenerate case is visible through the existing `skipped` counts inside that project's own report, not through the aggregate's skip list) |

This treats a **missing ledger** as a skip (not a zero-event project), per the requirements doc's
explicit framing (TEL3: "erroring per-path... on a missing or unreadable ledger — same 'skip with
counts, never silent' posture"). This is a deliberate difference from `review-stats` on a single
project, where a missing ledger is an honest "no review history yet" (exit 0, not an error) — the
distinction matters here because an operator who explicitly *named* N products is asking "give me
these N projects' numbers," and a project that has never produced a review event is arguably not
answering that question the same way a genuinely-read empty history would. Recorded as an explicit
design choice, not an oversight, since it reads as inconsistent with `review-stats` at first
glance.

No path is ever discovered — every project in the output was named by the operator, satisfying
TEL3/TEL5's opt-in posture directly.

### Per-project report body

Each included path's report is **`aggregate_review_stats(events, skipped)`** — the exact existing
per-project function (§2), unchanged — wrapped with two path-identifying fields the bare function
doesn't know:

```python
{
    "project": project_dir.resolve().name,
    "path": str(project_dir.resolve()),
    **aggregate_review_stats(events, skipped),
}
```

This is the same "wrap the pure aggregation with header fields the function can't know itself"
pattern `review_stats()` already uses for `project`/`generated_at` (`plugin/lib/telemetry.py:
314-321`) — reused, not reinvented. Because it's the exact same function, a single project's number
in the cross-project view and that same project's own local `review-stats --json` output are
**always identical** by construction — no second aggregation logic to drift out of sync with the
first.

### Cross-project rollups

The requirements doc (TEL3) asks for wall-clock and actionable-finding rate "by mode, model, and
project." The **project** axis is already the `projects` list above (each entry's `overall` stat
block *is* that project's own wall-clock/actionable-rate). Two more axes are computed by pooling
every included project's rows and grouping once each — **not** a combined mode×model×project tuple
(which would explode combinatorially across a real fleet and mostly render as sparse single-row
groups); two flat, independent rollups answer "which mode costs the most across everything I run"
and "is the deeper model tier paying off across everything I run" directly, which is the stated
motivating question (Decision 1's proportionality-tuning framing):

```python
def aggregate_cross_project(all_rows: list[dict]) -> dict:
    by_mode: dict[str, list[dict]] = {}
    by_model: dict[str | None, list[dict]] = {}
    for row in all_rows:
        by_mode.setdefault(row["mode"], []).append(row)
        by_model.setdefault(row["model"], []).append(row)
    return {
        "by_mode": [
            {"mode": mode, **_group_stats(rows)}
            for mode, rows in sorted(by_mode.items())
        ],
        "by_model": [
            {"model": model, **_group_stats(rows)}
            for model, rows in sorted(by_model.items(), key=lambda kv: kv[0] or "")
        ],
    }
```

`all_rows` is the concatenation of every included project's `_extract_row()` output (the same rows
each project's own `aggregate_review_stats` call already built — computed once per project, reused
for both that project's entry and the pooled rollups, not re-derived). `_group_stats` is the
existing shared stat-block function (§ unchanged, `plugin/lib/telemetry.py:163-185`) — reused
exactly as-is, so the pooled numbers are computed the identical way single-project numbers are.

**Plugin-version skew stays visible (TEL4) by construction, not by a fourth rollup**: `by_mode`
and `by_model` pool `duration`/`severities`, never `plugin` — there is no code path that could
blend plugin versions into either number. Skew is visible instead through each project's own
`plugin_versions` field in the `projects` list (§2, inherited unchanged) — an operator comparing
two projects' rows in the same `by_model` bucket can already see, project by project, whether they
ran on the same plugin version, without the aggregator making that judgment for them.

### Top-level output shape

```
schema_version      AGGREGATE_SCHEMA_VERSION (new constant, starts at 1)
generated_at         ISO-8601 UTC, computed once for the whole run
projects_requested   count of distinct resolved paths (post dedup)
projects_included    count of paths that produced a report
projects_skipped     [{"path": str, "reason": "invalid-path"|"no-ledger"|"unreadable-ledger"}]
by_mode               [{mode, ...stat block}]
by_model              [{model, ...stat block}]
projects              [{"project", "path", "plugin_versions", ...same body as a single
                          `review-stats --json` report (minus its own top-level
                          `project`/`generated_at`, superseded by this entry's)}]
```

`projects` sorted by `project` name (ties broken by `path`) for deterministic output —
`by_mode`/`by_model` sorted by key — so two runs over the same inputs produce byte-identical JSON,
which matters for anything downstream that diffs or caches this output later (out of scope here,
but a stable sort costs nothing now and forecloses a future flaky-diff bug).

### Human rendering

Mirrors `_render_human`'s structure: a `projects_requested`/`projects_included`/`projects_skipped`
summary line (skip reasons named, never just a count — same "never silent" posture), then one
summary line per project (name, reviews, actionable %, plugin versions — reusing `_fmt_stats`),
then `by mode:` / `by model:` sections using the same `_fmt_stats` line format already shared by
every other grouping in this file.

### New public functions in `telemetry.py`

- `AGGREGATE_SCHEMA_VERSION = 1` — separate constant from `REPORT_SCHEMA_VERSION`; the two reports
  are different machine contracts (nesting `projects[].schema_version` inside a wrapper that has
  its own), so they version independently. A future key change to one must not force a version
  bump on the other.
- `_resolve_project_report(path: Path) -> tuple[dict | None, str | None]` — returns
  `(report, None)` on success or `(None, skip_reason)` on failure; the single per-path decision
  point the table above describes.
- `_read_path_list_file(path: Path) -> list[str]` — the `--from-file` parser (comment/blank-line
  skip).
- `aggregate_cross_project(all_rows: list[dict]) -> dict` — the pooled `by_mode`/`by_model`
  rollup shown above.
- `aggregate_review_stats_multi(paths: list[Path]) -> dict` — orchestrates the above three into
  the top-level shape; the function `aggregate_review_stats_cmd` (CLI entry, below) calls.
- `aggregate_review_stats_cmd(argv: list[str]) -> int` — argument parsing (paths, `--from-file`,
  `--json`) plus human/JSON rendering, the direct analog of `review_stats()`'s CLI body
  (`plugin/lib/telemetry.py:292-330`). Takes no `project_dir` — unlike every other `cmd_*`/`*_cmd`
  function in this codebase, this command's subject is never the invoking project; passing one
  in would misleadingly suggest it's used.

### `bin/prawduct-hook` wiring

**Thin wrapper**, mirroring `cmd_review_stats` (`plugin/bin/prawduct-hook:3683-3702`) exactly,
including its lib-import-failure handling:

```python
def cmd_aggregate_review_stats(argv: list[str]) -> int:
    """Aggregate review-stats across operator-named product directories.
    Thin wrapper — body lives in `lib.telemetry.aggregate_review_stats_cmd`
    (TEL-7A4X). Never touches the invoking project's own state — every
    project it reads was named explicitly by the operator."""
    lib_root = _plugin_root()
    if lib_root not in sys.path:
        sys.path.insert(0, lib_root)
    try:
        from lib import telemetry  # noqa: PLC0415
    except ImportError:
        print(
            "aggregate-review-stats unavailable (could not import the plugin "
            "lib/ from ${CLAUDE_PLUGIN_ROOT})",
            file=sys.stderr,
        )
        return 1

    return telemetry.aggregate_review_stats_cmd(argv)
```

**Dispatch** (`main()`, alongside the existing `elif command == "review-stats":` at
`plugin/bin/prawduct-hook:5147-5148`):

```python
elif command == "aggregate-review-stats":
    return cmd_aggregate_review_stats(sys.argv[2:])
```

**Not added to `_DATA_PLANE_COMMANDS`** (`plugin/bin/prawduct-hook:4985-4991`) — like
`review-stats`, this is a read-only report; it writes nothing to the invoking project's governance
state, so a binary-skew mismatch degrades to the same advisory `NOTE:` every other read-only
command gets, never a `BLOCKED:` refusal.

**`_USAGE` string** (`plugin/bin/prawduct-hook:4695`): extend the existing `review-stats` line —

```python
"review-stats [--json]|"
"aggregate-review-stats <path>... [--from-file <list>] [--json]|"
"classify-diff-risk [<base>]|"
```

## 4. `/prawduct:janitor` wiring

**Where:** `plugin/skills/janitor/SKILL.md`, Step 1 ("Orient"), directly after the existing
`review-stats` line (currently `plugin/skills/janitor/SKILL.md:188`).

Per requirements Decision 1, this is *not* a new step and *not* a standalone skill section — it
rides the existing per-project `review-stats` sentence, extended one sentence, since janitor
sessions are already where an operator has multiple product checkouts in mind:

> Run `prawduct-hook review-stats` for the project's review cost / actionable-finding history
> (`docs/governance-telemetry.md`) — findings-dense paths and low-yield review tiers are
> maintenance signals. When this sweep is one of several product checkouts under review, `prawduct-hook
> aggregate-review-stats <path>...` folds their histories into one cross-project view — pass the
> checkouts you already have in mind; nothing is discovered automatically (`docs/governance-telemetry.md`).

No new persisted state, no registry file — satisfies TEL5 directly; the skill passes through
whatever paths the operator names in the moment, the same way the sentence above does.

## Files touched

| File | Change |
|---|---|
| `plugin/lib/ledger.py` | Import `_plugin_version` from `.evidence`; add `"plugin"` to the envelope dict (TEL1) |
| `plugin/lib/telemetry.py` | `_extract_row` gains `plugin`; new `_plugin_versions()`, wired into `aggregate_review_stats()`; `REPORT_SCHEMA_VERSION` 1→2; `_render_human` gains the plugin line; new `AGGREGATE_SCHEMA_VERSION`, `_resolve_project_report`, `_read_path_list_file`, `aggregate_cross_project`, `aggregate_review_stats_multi`, `aggregate_review_stats_cmd` (TEL2–TEL6) |
| `plugin/bin/prawduct-hook` | New `cmd_aggregate_review_stats`; dispatch case; `_USAGE` line |
| `plugin/docs/governance-telemetry.md` | Document the `plugin` envelope field, `plugin_versions` report field, and the new `aggregate-review-stats` command + its `--json` contract |
| `plugin/skills/janitor/SKILL.md` | One added sentence in Step 1 |
| `tests/test_governance_ledger.py` | Pin the new `plugin` envelope field |
| `tests/test_review_stats.py` | Pin `REPORT_SCHEMA_VERSION == 2`; add `plugin_versions` coverage (known versions, unlabeled count, missing-field case) |
| `tests/test_aggregate_review_stats.py` (new) | See test plan below |

## Test plan (`tests/test_aggregate_review_stats.py`)

Following `tests/test_review_stats.py`'s existing fixture style (sterile `HOME`/`PATH`/
`PYTHONDONTWRITEBYTECODE` env, hand-built ledger fixture files, no real git needed):

1. **Happy path** — two fixture project directories, each with a small ledger (some events
   carrying `plugin`, some not). `aggregate-review-stats <p1> <p2> --json` → `projects_included ==
   2`, `projects_skipped == []`, each project's embedded report matches what `review-stats --json`
   run directly against that same directory produces (the identity §3 claims — assert it, don't
   just assert it by construction).
2. **Invalid path** — a third argument pointing at a nonexistent directory → appears in
   `projects_skipped` with `reason: "invalid-path"`; the other two still succeed (no abort).
3. **No ledger yet** — a fourth fixture directory that is a valid project dir (has `.prawduct/`)
   but no `.governance-ledger.jsonl` → `reason: "no-ledger"`, not silently a zero-event project.
4. **`--from-file`** — a list file mixing real paths, a `# comment`, and a blank line → resolves
   to the same result as passing the real paths positionally; combined with one positional path
   already given, the duplicate collapses to one project entry.
5. **Plugin-version skew visible, never blended** — project A's events all carry `"plugin":
   "3.2.0"`, project B's carry `"plugin": "3.2.3"` (plus one event with no `plugin` key at all) →
   each project's own `plugin_versions.known` shows its own version(s); the `by_mode`/`by_model`
   rollups contain no `plugin` key at all (structurally cannot blend what they never carry) —
   asserted by checking the rollup entries' key sets.
6. **No paths supplied** — bare `aggregate-review-stats` (no positional args, no `--from-file`) →
   exit 1, stderr usage message.
7. **Determinism** — same two-project input run twice → byte-identical `--json` output (pins the
   sort-by-name / sort-by-key ordering).
8. **`AGGREGATE_SCHEMA_VERSION` pin** — same pattern `test_review_stats.py` uses for
   `REPORT_SCHEMA_VERSION`: a key-set assertion on the top-level shape, forcing a conscious bump on
   any future key change.

## Open items for the build chunk (not resolved here)

- Exact wording/formatting of the human-readable render (`_render_human`-equivalent for the
  aggregate) — cosmetic, left to implementation.
- Whether `aggregate_review_stats_multi` should cap the number of paths it accepts in one run —
  no cap proposed; ledgers are "unbounded-but-tiny" per `ledger.py`'s own docstring, and the
  operator already had to type or list every path, which self-limits practical scale.

## Acceptance (carried from requirements, now with an implementation path)

- [ ] `plugin/lib/ledger.py` writes a `plugin` field on every new event (TEL1) — pinned by
      `tests/test_governance_ledger.py`.
- [ ] `review-stats --json` surfaces `plugin_versions` (TEL2) — pinned by
      `tests/test_review_stats.py`, `REPORT_SCHEMA_VERSION == 2`.
- [ ] `aggregate-review-stats <path>...` / `--from-file` produces a cross-project view that never
      auto-discovers a path (TEL3, TEL5) — pinned by `tests/test_aggregate_review_stats.py`.
- [ ] Plugin-version skew is visible per project and never silently pooled (TEL4) — pinned by
      `tests/test_aggregate_review_stats.py` test 5.
- [ ] `--json` output has a stable, versioned top-level shape (TEL6) — `AGGREGATE_SCHEMA_VERSION`,
      pinned by test 8.
