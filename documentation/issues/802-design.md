# Issue #802 — plan-backfill: A Rolled Change Log Strands a Refused Plan Forever: Design

`status: draft · stage: design · area: release · added: 2026-09-14 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/802`

No separate requirements document exists for this item — the issue body itself (Problem /
Reproduction / Expected / Root cause) is the requirements input, and the owner's 2026-09-12 triage
comment named the actual unit of work directly: *"Deciding where archived change-log text lives is
the actual unit of work, and it is shared with #793... Sequence the location decision first; both
items collapse to small edits after it."* This document makes that decision and designs the small
edit it unblocks. It does **not** design #793's own PR-flow wiring (out of scope below) — only the
archive convention and location decision #793 depends on, plus the fix #802's own `affected:` list
names (`plugin/lib/plan_backfill.py`, `plugin/lib/change_log.py`).

Grounding re-verified against `develop`, 2026-09-14.

## 1. The location decision (the "larger point")

**`.prawduct/change-log-history.md`**, beside `change-log.md`. This is not a fresh coinage: #793's
own issue text already names this exact filename ("moving shipped entries into
`change-log-history.md` at each release") while describing a manual practice this repo has followed
by hand (the trimmed-entries comment in `project-state.yaml`'s `change_log_history:` block records
the same instinct at a smaller scale, though that YAML key is a *different*, pre-existing concept —
a compact narrative summary — and this item does not touch it). Adopting the name #793 already uses
avoids a second rename once that item builds its own PR-flow integration.

**Format and ordering mirror `change-log.md` exactly** — same `## YYYY-MM-DD: title` +
`<!-- prawduct: ... -->` entry shape, same newest-first convention (`change-log.md`'s own
`.gitattributes merge=union` rationale, `gitattributes_probes.py`'s module docstring: "every branch
writes its entry at the TOP of that file"). Archived batches are **prepended** to
`change-log-history.md`'s top, never appended to its bottom and never inserted mid-file — this
keeps the file internally newest-first (most recently archived batch on top) and keeps every write
an addition to existing content, never a rewrite of it, the same append-only shape Goal 4's own
rule already assumes for change-log content (`review-protocol.md:85`, "Changelog entries
(`change-log.md`, `change_log_history`)... are append-only").

## 2. What gets archived, and why this predicate

**Every entry carrying a `release=` tag** — the same mechanical test `plan_backfill.shipped_scopes`
already uses to decide a *plan's* shipped status, and, concretely, the same thing #802's own
reproduction section describes the reporter doing by hand at step 4 ("the roll moves every
`release=`-tagged entry into the archive file"). This is not a new rule invented for this design; it
is the rule the incident that reported this bug was already following, made mechanical.

**Untagged entries are left alone, by design — not a gap.** The existing size-nudge
(`oversized_state_probes.py`'s `oversized-change-log` advice) already tells an operator "older
entries can go once they are in git — nothing here derives from them" for untagged entries, and that
advice stays correct and unchanged: nothing reads them, so deleting one is safe and archiving one
gains nothing a `git log` doesn't already have. Scoping this item to tagged entries only keeps the
fix to exactly what #802 and #793 both describe (tag-derived state going missing), rather than
redesigning the file's whole size problem, which is not what either issue asks for.

## 3. `change_log.py` — the split primitive

```python
# plugin/lib/change_log.py, beside CHANGE_LOG_REL_PATH

CHANGE_LOG_HISTORY_REL_PATH = ".prawduct/change-log-history.md"


def split_shipped_entries(content: str) -> tuple[str, str]:
    """Partition change-log markdown into (kept_text, archived_block).

    ``archived_block`` is every entry carrying a `release=` tag (§2), each
    entry's full text — header through the line before the next H2 or EOF —
    concatenated in the SAME relative order they appear in ``content``
    (newest-first, since that is the file's own convention). ``kept_text`` is
    ``content`` with those spans removed, everything else (including untagged
    entries) preserved byte-for-byte.

    Reuses `parse_change_log`'s existing `line_number` per entry to find each
    entry's span rather than re-deriving H2 boundaries a second time — the same
    reasoning `plan_backfill.py`'s own module docstring gives for composing
    existing readers instead of pushing new parsing into either leaf module.
    """
```

Entry spans: `parse_change_log(content)` already gives each entry's 1-indexed header line in
document order; an entry's span is `[line_number, next_entry.line_number)` (or EOF for the last
entry). No change to `parse_change_log`, `ChangeLogEntry`, or the tag-line parser — this is a pure
read-then-slice built on the existing output, so none of the merge-attribute / `unconsumed_tag_lines`
machinery `gitattributes_probes.py` depends on changes shape.

**Malformed dates are never archived.** An entry whose title doesn't match `_ENTRY_DATE_RE`
(`plan_backfill.py`'s own date pattern, not duplicated — see §5) is left in the live file regardless
of its tags; `shipped_scopes` already treats an undated tagged entry as "oldest" and therefore weak
(§5's grounding), so leaving it live rather than archiving it blind is the same fail-safe direction
that function already takes, applied one step earlier.

## 4. `prawduct-hook archive-change-log [--apply] [--json]`

Mirrors `plan-backfill`'s preview-then-`--apply` shape exactly (same two-phase convention, same
"one confirmation covers the whole set" release-process language, `release-process.md:173-207`):

```python
def cmd_archive_change_log(project_dir: Path, argv: list[str]) -> int:
    """Preview or apply moving release-tagged change-log entries into history.

    Dry run (default): reports each entry that WOULD move (date, title,
    release=), and the resulting kept/archived byte counts — read-only, no
    disk write. `--apply` performs `split_shipped_entries` (§3) and writes
    BOTH files: the trimmed change-log.md, and change-log-history.md with the
    archived block PREPENDED (created fresh, with a one-line header comment,
    if it does not yet exist). `--json` emits the structured list for the
    release runbook / doctor to relay. A change-log with zero release-tagged
    entries is a no-op, reported and exits 0 — same "nothing to do is not an
    error" convention as plan-backfill on a product with no release tags.
    """
```

Registered beside `archive-plan`/`plan-backfill` in the command dispatch table and usage string
(`prawduct-hook:6931`-area, `:7480`/`:7538`-area — three edit sites, same shape as those two
commands' own registration).

**No new containment or refusal logic is needed.** Unlike `archive-plan`, this command never
chooses *which* file a thing lands in per-invocation (there is exactly one destination,
`CHANGE_LOG_HISTORY_REL_PATH`, a plugin-defined constant, not an operator-supplied path) — so
`plan_archive.py`'s path-escape guard has no analogous risk here to re-verify.

## 5. The fix `plan_backfill.py` and #802's `affected:` list actually name

**One-line change at the single call site** (`plan_backfill.py:197-201`, `survey()`): build the text
`shipped_scopes` reads from **both** files, not the live one alone —

```python
def _combined_change_log_text(prawduct_dir: Path) -> str:
    """Live + archived change-log text, concatenated for shipped_scopes (#802).

    Order between the two doesn't matter to shipped_scopes's own logic — it
    resolves each scope by comparing entry DATES (shipped_scopes's own
    docstring: "decided by date, not by document position"), not by which file
    or position an entry came from — so this need not preserve either file's
    internal ordering relative to the other, only concatenate both wholesale.
    Each file's own internal newest-first order is preserved within itself.
    """
    parts = []
    for rel in (change_log.CHANGE_LOG_HISTORY_REL_PATH, CHANGE_LOG_REL):
        try:
            parts.append((prawduct_dir / rel).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            pass
    return "\n".join(parts)
```

`survey()`'s existing `text = (prawduct_dir / CHANGE_LOG_REL).read_text(...)` (with its existing
try/except degrading to `""`) is replaced by `text = _combined_change_log_text(prawduct_dir)` — same
degrade-to-empty behavior when a file is missing or unreadable (a repo that has never run
`archive-change-log` has no history file, `read_text` raises `OSError`, that source contributes
nothing, and behavior is identical to today). **This is the entire fix for the bug #802 reports**:
`shipped_scopes` itself needs no change (§ Grounding below confirms its date-comparison logic is
already correct over a combined entry set — it was only ever missing entries the old text-source
omitted, never computing incorrectly on the ones it saw).

`versions = any(entry.tags.get("release") for entry in change_log.parse_change_log(text))` (the
sibling line just below, `:203-205`) uses the same `text` and is correct unchanged once `text` is
the combined source — a product with all its shipped tags now in history rather than the live file
must still report `has_release_tags=True`, which this automatically gives it.

**Grounding for "no change needed in `shipped_scopes` itself."** Its docstring states the rule
explicitly: a scope is shipped only if no *later* entry for it is untagged, decided by **date**, not
by document position — `newest_tagged` / `newest_untagged` are built by scanning
`parse_change_log(change_log_text)` and comparing `_ENTRY_DATE_RE` matches, never by which file or
line an entry occupies. An archived entry and a live one compared through this same loop resolve
exactly as they would if both still lived in one file, **provided the archiver never duplicates an
entry across both files** — true by construction, since `split_shipped_entries` (§3) *removes* each
archived entry from `kept_text` in the same operation that adds it to the archived block.

## 6. Release-process wiring (this repo's own release checklist only)

`documentation/release-process.md` step 3 ("Tag the shipped entries") is where a scope's `release=`
tag is written — the earliest point at which an entry becomes archivable. Step 4 already runs
`plan-backfill` (`:173-207`) and, per §5, now works correctly whether or not `archive-change-log` has
run first — so this addition is a **new step 3.5**, not a reordering of the existing two, and
`plan-backfill`'s own step is untouched:

> **3.5. Archive the change log's shipped entries.** `prawduct-hook archive-change-log` (preview),
> then `--apply`. Moves every entry step 3 just tagged (plus any tagged in an earlier, unarchived
> release) into `.prawduct/change-log-history.md`, keeping the live file bounded. Order relative to
> step 4 does not matter (§5) — placed here because it is the natural continuation of "which entries
> just became shipped," the same question step 3 just answered.

This repo's own `release-process.md` is the only wiring this design makes — **wiring
`archive-change-log --apply` into `/prawduct:pr` Create Step 1d for trunk-based products is #793's
own item**, not duplicated here: #793 is already `stage:ready`, already names the exact Step 1d
edit, and this design supplies the one thing it was missing (a command that actually exists to
call). Building #793's skill-file edit inside this item would blur two issues' `closed-by:`
provenance for no benefit — the command lands here, the trunk call site lands there.

## 7. `.gitattributes` — extend the existing recommendation, not a new probe

`change-log-history.md` inherits the exact same prepend-conflict shape `change-log.md` has (§1) — a
release cut on one branch and a release cut on another both prepend to the same first lines. Rather
than a parallel probe module, `gitattributes_probes.py`'s existing
`probe_change_log_union_merge` (`:80-...`) is **generalized to a small table of (path, recommended
line) pairs** instead of the one hardcoded `CHANGE_LOG_REL_PATH` / `UNION_MERGE_LINE` pair, each
checked the same way (on-disk existence → `git check-attr merge` → tracked-check, unchanged
three-state fail-soft logic) and each firing its own independently-dismissable advisory `type`
(`change-log-union-merge`, `change-log-history-union-merge`) — same reasoning
`oversized_state_probes.py`'s module docstring already gives for "one advisory per file": a repo can
accept the state of one file and act on the other.

This is scope-adjacent, not core to #802's fix (the bug reports a data-loss-shaped defect;
`.gitattributes` hygiene is a hardening nudge), so it is a **SHOULD**, buildable in the same chunk or
deferred to a fast-follow without blocking §3–§6 — named here so a build session doesn't have to
re-derive that the existing probe is the right extension point rather than a new module.

## 8. Files touched (build-time)

| File | Change |
| --- | --- |
| `plugin/lib/change_log.py` | new `CHANGE_LOG_HISTORY_REL_PATH`, `split_shipped_entries()` (§3) |
| `plugin/lib/plan_backfill.py` | new `_combined_change_log_text()`; `survey()`'s text source swapped (§5) |
| `plugin/bin/prawduct-hook` | new `cmd_archive_change_log`; dispatch table + usage string entries (§4) |
| `plugin/lib/gitattributes_probes.py` | generalize to a (path, line) table; second advisory type (§7, SHOULD) |
| `documentation/release-process.md` | new step 3.5 (§6) |
| `.prawduct/change-log-history.md` | created at first `--apply` (not committed empty ahead of time — matches `plan-backfill`'s own "nothing until there's something to archive" convention) |
| `tests/` | new coverage — see §9 |

## 9. Testing strategy → acceptance mapping

- **`split_shipped_entries` unit tests**: a text with a mix of tagged/untagged entries splits
  correctly; entry order within the archived block matches source order; an undated tagged entry
  stays in `kept_text` (§3's fail-safe); an entry whose tag line is itself malformed
  (`tag_conflicts` non-empty) is still archived if it resolved a `release` value — conflicts don't
  block archiving, they're a `validate_change_log_tags` concern, orthogonal to this split.
- **`_combined_change_log_text` / `survey()` regression** (the actual bug fix, §5): reproduce #802's
  exact reproduction steps as a fixture — a `scope: alpha` entry tagged `release=v1.0.0`, moved into
  `change-log-history.md`, live `change-log.md` left with no `alpha` entry at all; assert
  `shipped_scopes` still resolves `alpha → v1.0.0`, and that `plan_backfill.survey()` now proposes
  the plan for archiving (the exact scenario the issue reports as broken today). A second fixture
  reproduces the reuse hazard `shipped_scopes`'s own docstring warns about, across the file split: an
  archived tagged `alpha` entry (old date) plus a live UNTAGGED `alpha` entry (newer date) still
  withholds the scope — pins that §5's "no change needed in `shipped_scopes`" claim holds under the
  adversarial case its own docstring names, not just the easy case.
- **`archive-change-log` CLI tests**: dry run lists the right entries and writes nothing; `--apply`
  moves them, prepends (not appends) to a fresh history file, and prepends again correctly on a
  second `--apply` against an existing history file; a product with zero release tags reports
  no-op and exits 0; `--json` shape.
- **`.gitattributes` probe generalization** (§7, if built in this chunk): both paths' advisories fire
  and dismiss independently; existing `change-log.md`-only test coverage still passes against the
  generalized table (no regression on the shipped path).
- **Release-process step 3.5** (§6): no automated test — a documentation-only addition, verified by
  reading the diff, consistent with how prose-only release-process edits are graded elsewhere in this
  repo's own convention (e.g. the #715 design's §6 treatment of prose edits).

## 10. Scope-out

- **#793's own Step 1d / trunk-flow wiring** — that item's to build, not duplicated here (§6).
- **Archiving untagged entries, or any file-size reduction for them** — the existing size-nudge's
  "older entries can go, nothing derives from them" advice already covers that safely; not this
  item's problem (§2).
- **`project-state.yaml`'s `change_log_history:` block** — a pre-existing, unrelated concept (a
  compact narrative summary embedded in state, not a markdown archive file); not touched, not
  renamed, no collision with `CHANGE_LOG_HISTORY_REL_PATH` since one is a YAML key and the other a
  file path.
- **A doctor health check for the new file's presence/health** — no acceptance criterion in #802 or
  #793 asks for one, and `change-log-history.md`'s absence is not unhealthy (a product that has never
  released has nothing to archive); adding a check would be inventing a norm neither issue stated.

## 11. Evidence / references

- Issue #802 — Problem, Reproduction (the exact "roll moves every `release=`-tagged entry" phrasing
  §2 adopts as the archiving predicate), Expected, Root cause, and the 2026-09-12 triage comment
  naming the archive-location decision as the shared blocking question.
- Issue #793 — the `change-log-history.md` name (§1) and the "moving shipped entries... at each
  release" framing this design's predicate (§2) satisfies; its own Step 1d wiring, explicitly left
  unbuilt here (§6).
- `plugin/lib/plan_backfill.py:65-120` (`shipped_scopes` — date-based, not position-based resolution,
  the reuse hazard its own docstring names) and `:197-205` (`survey()`'s text read, §5's edit site);
  its module docstring's "module boundary" note, the precedent for composing existing readers rather
  than adding new parsing.
- `plugin/lib/change_log.py:44-56` (`CHANGE_LOG_REL_PATH`, module docstring on tag semantics),
  `:179-243` (`parse_change_log`, `ChangeLogEntry.line_number` — the span-finding primitive §3
  reuses without modification).
- `plugin/lib/plan_archive.py:329-389` (`archive_destination`, `refusal_reason` — the
  preview/`--apply` convention §4 mirrors; confirms no analogous containment guard is needed here,
  §4).
- `plugin/lib/gitattributes_probes.py` (full module) — the existing `merge=union` recommendation
  pattern §7 generalizes, its three-state fail-soft git-ask logic, and its own stated reasoning for
  why the plugin never writes `.gitattributes` itself.
- `plugin/lib/oversized_state_probes.py` (`_MEASURED`, `oversized-change-log`'s advice bullets) — the
  existing size-nudge whose untagged-entry advice §2 confirms stays correct and unchanged.
- `plugin/skills/critic/review-protocol.md:85` — "Changelog entries... are append-only", grounding
  §1's prepend-only (never rewrite) design for `change-log-history.md`.
- `documentation/release-process.md:146-207` (steps 3–4) — the exact release-moment steps §6's new
  step 3.5 sits between, and the "one confirmation covers the whole set" convention §4 borrows.
- `.prawduct/change-log.md` (18,602 lines at HEAD, newest-first, oldest entries from 2026-03) — the
  live measurement confirming the file this item bounds is not a hypothetical size concern.
