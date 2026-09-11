# Issue #669 — Backlog-Service: Nothing Requires `affected:` Paths, So the Walk Is Blind: Design

`status: draft · stage: design · area: backlog-service · added: 2026-09-10 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/669`

**No separate requirements doc exists for #669, and none is needed.** The issue body already states
the problem (measured: 165/174 open items created since 2026-08-01 carry no `affected:`, so
`cachequery.items_affecting` silently misses ~95% of the open backlog), the expected behavior ("the
pass either covers the open backlog, or reports how much of it it could not see"), and three
candidate directions, explicitly leaving the choice among them — and the adapter-contract shape that
choice implies — as the open question `stage: design` exists to resolve. That is what this document
does.

## Grounding facts

Re-verified against the current tree (2026-09-10):

- **`affected` cannot be set at filing time at all.** `_run_file`'s flag parser
  (`plugin/lib/backlog/cli.py:507-511`) accepts only `repo, title, body, stage, kind, area, effort,
  impact, source, refs` — no `affected`. `core.file_item` (`core.py:108-119`) takes only `refs` as
  "the one block field settable here" at create time; `affected` and `working-branch` are validated
  and written exclusively inside `_prepare_new_fields` (`core.py:663-693`), which only `update`
  calls (`cli.py:735-760`). So an author who wants `affected:` on a new item must file, then run a
  **second** command (`update <id> --affected p1,p2`) — a step the issue's own 165/174 figure says
  is almost never taken. This is a structural gap, not a habit gap: the flag the issue-standard doc
  (`plugin/skills/backlog/adapter-mode.md:248-250`) documents as *the* way to set `affected` is
  unreachable from `file`.
- **`--refs` already crossed this exact line, on purpose.** `adapter-mode.md:263`: "`file` also
  takes `--refs` so a new item can carry its governing-doc link from birth." `file_item` validates
  it with `encode.check_block_value("refs", refs)` (`core.py:135-138`) before the create call. This
  is the precedent this design extends to `affected` — not a new architectural move, the second
  instance of one already made.
- **The reason `affected`/`working-branch` route through a different mechanism than facets is
  documented and does not bear on filing.** `core.py:637-646`: they are "body-block fields," not
  label-swap facets — `_UPDATE_FACETS` strips every other label with the prefix (right for `area`,
  wrong for a set-valued field). That distinction is about *how* the value is written (block field
  vs. label), not about *when* (create vs. update-only). Nothing in the comment argues against a
  create-time block write; `refs` already is one.
- **Validation is already create-time-safe.** `encode.validate_affected` (`encode.py:668-693`) is a
  pure function of the entries list — no dependency on the item existing. Calling it from
  `file_item` needs no new validation path, only the same call `_prepare_new_fields` already makes.
- **The lint architecture forbids a blocking body/field check.** `issuefmt.py:15`: "The four §1
  TITLE checks BLOCK; every body and label lint stays WARN-only." `affected` is a block field, not a
  body section — it is not even routed through `_lint_body` today — but the invariant is general:
  only title shape may refuse a write. Candidate 1 from the issue body ("a lint... flagging **or
  refusing**") is therefore only available in its WARN form; the refusing form would need a
  documented exception to an invariant three other rules currently rely on, which is out of
  proportion to this item.
- **No git-diff-against-branch helper exists in this module today.** `plugin/lib/backlog/` has no
  import of `gitstate` or any git-diff call — the cache/store/transport layers are deliberately git-
  free (SEC-1: `gh`/store only). `gitstate.py` (used elsewhere: `coverage.py`, `buildplan_refs.py`)
  already has `current_branch` (`gitstate.py:371`) and the primitives `coverage.resolve_merge_base_tree`
  builds on. A branch-diff default for `file` would be the **first** place `plugin/lib/backlog/`
  reads git state — worth naming because it is a real boundary crossing, not a detail.
- **`items_affecting`'s envelope already has a place for a coverage figure.** `_serve` (`cachequery.py:162-187`)
  merges whatever `query(conn)` returns into the wrapped envelope; `items_affecting`'s `query`
  (`cachequery.py:395-416`) already returns `{"items", "changed_paths", "open_only"}` — a sibling
  key costs nothing structurally. The module's own stated invariant, "unavailable is never empty"
  (`cachequery.py:8-11`), is exactly the property a silent 95%-blind answer violates; a coverage
  figure is that invariant applied to *this* answer's completeness, not just the store's freshness.
- **`_open_placeholders()`/`OPEN_STATUSES`** (referenced `cachequery.py:409-410`) already define "open"
  for this query, so counting "open items with non-empty `affected`" reuses the exact predicate the
  match itself uses — no second definition of open to drift from the first.

## Decisions

### Decision 1 — adopt candidate 2 (default `affected` from the filing branch's diff), scoped to same-repo self-filing

This is the only candidate that satisfies the issue's own framing: "backfilling 165 items leaves
item 166 off the list... fix it at creation." A lint (candidate 1) or a coverage report (candidate
3) both describe the gap after the fact; only a construction-time default closes it for every future
`file` call without relying on the author to remember a second command.

**Scope of the default — same-repo only.** `file`'s `--repo` may name any repo; the branch that is
checked out locally has no necessary relationship to a filing that targets a different one (e.g.
`brookstalley/prawduct` filing against an unrelated tracker would never happen in practice, but the
CLI does not forbid it). The default only fires when `--repo` resolves to the same `owner/repo` the
local checkout's `origin` remote names — computed via `gitstate` helpers already used elsewhere for
comparable checks (`ids.parse_repo` on the resolved remote). Off that path, `affected` stays unset,
exactly as today, and Decision 2's coverage report is what tells a reader how much of the backlog
that leaves untagged.

**What "the filing branch's changed files" means.** Reuse `coverage.resolve_merge_base_tree`'s
existing merge-base resolution (`coverage.py`, already used by `critic_consolidate.begin_review`'s
`cumulative` branch) to get `merge_base(default_branch, HEAD)`, then:

```
git diff --name-only <merge_base> HEAD        # committed work on this branch
+ git status --porcelain (uncommitted paths)   # via gitstate.git_status_output, already parsed
```

union, deduplicated, **normalized through `encode.normalize_affected`** (the same normalizer
`validate_affected` already calls) so the default and an explicit `--affected` produce identically
shaped entries. An empty union (filing from a clean default branch, e.g. an external bug report)
leaves `affected` unset — never an error, since a genuinely branch-less filing is a normal case
(most `source:user`/`source:critic` items in the corpus are filed this way).

**Explicit `--affected` always wins.** The default only fires when the flag is absent, matching the
existing "`None` means not named" convention `_prepare_new_fields`'s docstring states
(`core.py:667-671`). A caller who explicitly passes `--affected ''` gets exactly that — cleared/
unset — same as `update` already treats an empty value as "clear," not "default."

**Cap.** A branch diff can be large (a merge, a rename-heavy refactor). Cap the union at a fixed
count (reuse `_AFFECTED_MAX` if one exists in `encode.py`; if not, 25 — generous for the actual
shape of a filing branch's diff, which per the module's own docstrings is typically one chunk's
worth of files) and when the cap is hit, **do not silently truncate**: fall back to leaving
`affected` unset for that create and say why in the response's `notes`/`warnings` (same channel
`file_item` already uses for facet warnings, `core.py` late in the function). A capped, silently-
truncated `affected` would assert coverage of files it does not name — worse than the status quo,
which at least reports nothing rather than an incomplete something.

### Decision 2 — also adopt candidate 3 (self-reported coverage), as the honesty backstop

Decision 1 closes the gap for same-repo filings with an active branch diff going forward; it cannot
help the 165 pre-existing items, filings against a different repo, filings from a clean branch, or
capped diffs. The issue's own "Expected" is explicit that either full coverage or an honest partial
answer satisfies it — Decision 1 provides the former where it can, this provides the latter
everywhere else, and the two together mean `items_affecting` never again returns a confident answer
built from an unstated fraction of the backlog.

Add a `coverage` key to `items_affecting`'s returned dict:

```python
{"open_considered": N, "open_with_affected": M}
```

computed with one extra `COUNT` query inside the same `query(conn)` closure, scoped identically to
the match (`open_only` respected, same `OPEN_STATUSES`) so the figure answers "of the population
this call could have matched against, how much of it was even eligible" — not the whole store,
which would counts items the caller was never asking about (e.g. `open_only=False` callers should
not have a closed-item's missing `affected` count against them). No `pct` field computed
server-side; a consumer that wants a percentage has both integers already, and a division prawduct
performs is one more place a display convention could drift from another (the module has this
pattern already — `_freshness` returns raw seconds, not a formatted "3 hours ago").

**Who reads it.** `cli.py`'s human-readable rendering path near line 2035 (where `working_branch`
already gets a conditional `bits.append`) gets one more line, e.g. `coverage: 42/174 open items
carry affected: paths (24%)` — computed at render time from the two integers, not stored pre-
formatted. `--json` callers get the two raw integers and decide for themselves. This mirrors the
existing `working_branch` line's own pattern exactly (`cli.py:2035-2041`), so there is one rendering
idiom for "an advisory fact about this answer's shape," not two.

**Not blocking, never a refusal.** `unavailable is never empty` is a statement about the *store*
being reachable, not about whether every item is tagged. `coverage < 100%` is a fact about the
backlog's filing history, not a store failure — it rides the same successful envelope
`items_affecting` already returns, exactly as `_freshness`'s `age` rides a successful envelope today
rather than degrading it.

### Decision 3 — do NOT adopt candidate 1 in blocking form; add a narrow WARN-only nudge instead

A refusing lint on `affected` would need the file to carry a documented exception to the "only §1
title checks block" invariant (`issuefmt.py:15`) — a bigger architectural move than this item's
`impact:L`/`effort:M` warrants, especially once Decision 1 makes the common case (same-repo filing
from an active branch) self-filling and therefore nothing to nudge about.

The residual worth nudging: a same-repo filing where Decision 1's default resolved to **empty**
(clean branch, or the diff was empty for a reason other than "no code change yet" — e.g. filed from
`develop` itself, mid-triage, describing a defect rather than fixing one). Add one `LintFinding`
next to the existing `bug-missing-env` precedent (`issuefmt.py`, `_lint_body`'s bug-only branch,
same WARN-only shape):

```
LintFinding("affected-missing", "no affected: paths and none could be inferred from the "
            "current branch — set --affected if this item is scoped to specific files")
```

emitted from `file_item` itself (not `_lint_body`, since `affected` is a block field `lint()` never
sees) into the same `warnings` list the facet-enum loop already appends to (`core.py`, the `_FILE_FACETS`
loop a few lines below the title refusal) — one more entry in a list callers already read, not a new
channel. Fires only when Decision 1's default was attempted and came back empty; a cross-repo filing
where the default never runs at all stays silent, since prompting for a field the CLI cannot even
attempt to fill would be advice with no actionable next step at that call site.

## What ships

1. **`plugin/lib/backlog/cli.py`** — `_run_file`'s `valued` set gains `"affected"`
   (`cli.py:507-511`); the `file_item(...)` call gains `affected=flags.get("affected")`, plus a new
   same-repo branch-diff helper call when the flag is absent (see item 3).
2. **`plugin/lib/backlog/core.py`**:
   - `file_item` gains an `affected: str | None = None` parameter, validated via
     `encode.validate_affected` exactly as `_prepare_new_fields` validates it for `update`
     (reuse, not reimplement — extract the three-line validate-and-format block if duplication
     would otherwise appear twice).
   - the `affected-missing` `LintFinding`-shaped warning (Decision 3), appended to `warnings` when
     applicable.
3. **New: `plugin/lib/backlog/branchdefault.py`** (or a function in an existing module if a home
   fits better at implementation time) — `default_affected(project_dir, owner, repo) -> list[str] |
   None`: resolves the local remote, compares to `(owner, repo)`, and if they match, computes the
   merge-base + working-tree union described in Decision 1, capped and normalized. Returns `None`
   (not `[]`) whenever the default does not apply or resolves empty, so the caller's "was a default
   attempted" and "did it find nothing" stay distinguishable — the same `None`-means-not-named
   convention `_prepare_new_fields` already documents.
4. **`plugin/lib/backlog/cachequery.py`** — `items_affecting`'s `query(conn)` (`cachequery.py:395-416`)
   gains the `coverage` count query and key (Decision 2).
5. **`plugin/lib/backlog/cli.py`** — the human-readable render path near `cli.py:2035` gains the
   `coverage:` line for `affecting` results, mirroring the existing `working_branch` line.
6. **`plugin/skills/backlog/adapter-mode.md`** — the `affected` bullet (`:248-250`) documents that
   `file` now also accepts `--affected`, auto-defaults it for a same-repo filing when omitted, and
   that `affecting`'s answer now carries a `coverage` figure — mirroring how the `refs` bullet
   already documents `file`'s support for it.

## Test plan (shape, not exhaustive)

- `file` with explicit `--affected` → stored verbatim, normalized, no default attempted.
- `file` with `--affected ''` → cleared/unset explicitly, default not attempted (explicit wins).
- `file` with no `--affected`, same-repo, branch diff non-empty → default populates `affected`, and
  the create's response can distinguish "explicit" from "defaulted" (a `notes` entry, so a caller
  that wants to know does not have to guess from silence).
- `file` with no `--affected`, cross-repo `--repo` → no default attempted, no `affected-missing`
  warning (nothing actionable at that call site).
- `file` with no `--affected`, same-repo, clean/no diff → `affected` unset, `affected-missing`
  warning present.
- Diff exceeding the cap → `affected` unset (not truncated), a warning naming the cap and count.
- `affecting` on a scope with 0 tagged items → `coverage: {"open_considered": N, "open_with_affected": 0}`,
  not an `unavailable` envelope (empty coverage is a fact, not a store failure).
- `affecting`'s `coverage.open_considered` respects `open_only` the same way the match itself does.

## Scope-out

Backfilling the 165 existing untagged items (the issue's own "Proposed direction" rules this out:
"backfilling... leaves item 166 off the list"). Any change to `encode.validate_affected`'s format
rules (the issue's own Scope-out: "the format rules are fine... this is about paths being absent,
not malformed"). Extending the branch-diff default to `update` (item text can change independent of
code across an item's life in a way a *create*-time snapshot does not need to track — a separate
design question if it turns out to matter).
