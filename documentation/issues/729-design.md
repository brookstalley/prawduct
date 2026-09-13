# Issue #729 — Import Downgrades `promoted` to `open`, the Gate Certifies It: Design

`status: draft · stage: design · area: backlog · added: 2026-09-02 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/729`

No separate requirements doc exists for this item — it was filed as a bug report with a verified
root cause, file/line citations, and four concrete suggested fixes already in hand (the reporter
read `migrate.py::_target_status`, `encode.STATUS_VALUES`, and `templates/backlog.md:41`
directly), which is the requirements-stage work for a bug of this shape (same posture as #727's
design doc). This document picks and specifies the fix.

Two pieces of related history ground the decisions below:

- **#529** (closed 2026-09-01, `not_planned`, `superseded_by: #729`) is the predecessor that first
  found this class, on prawduct's own migration. Its fold-comment supersedes it into this item and
  adds the load-bearing fact this design leans on: `migrate._block_for` already preserves an
  unrecognized `status:` value verbatim in the issue's `prawduct:` block, so **the data was never
  lost — only left undecoded.** #529 also raised an open question this design must answer:
  *"`in-progress` looks like a free fix, but it is not obviously right — `promoted` in \[that]
  corpus meant 'code landed, awaiting the release flip', which is nearer shipped-pending than
  actively-being-worked."* Resolved in Decision 1.
- **#672**, filed nine days before #729 by the same reporter, states the identical architectural
  concern one layer down in the Critic's coverage machinery: *"the gate's expectation is derived
  from the same code as the outcome it is checking."* #729's own suggested fix 2 restates it
  verbatim for this domain. Decision 3 is the fix for that shared root, applied here.

## Root cause (restated, verified against current `develop`)

- `plugin/templates/backlog.md:41` documents the **markdown** status vocabulary as
  `open | promoted | shipped | dropped`. `encode.STATUS_VALUES` (the **service** vocabulary,
  `encode.py`'s `_STATUS_ENCODING`) is `submitted | open | in-progress | shipped | dropped`.
  `promoted` is real, load-bearing, actively-documented vocabulary (`SKILL.md`'s `update`,
  `add`'s three-way offer, `/backlog pick`'s exclusion rule) that the service encoder simply does
  not recognize.
- `migrate.py:636-647` (`_target_status`) tests the item's `status:` metadata against
  `encode.STATUS_VALUES` only — no alias step — misses `promoted`, falls past the archived-section
  check (the item isn't archived), and returns `"open"`.
- `migrate.py:1380+` (`verify_migration`) derives its *expected* status for each source record
  from `record.status`, which was set by `_record_from_item` calling this exact same
  `_target_status` at parse time. Import and verify share one computation, so the gate can only
  ever confirm the code agrees with itself — confirmed by reading both call sites; there is no
  second, independent path.
- `migrate.py:668-681` (`_block_for`) skips writing `status:` into the block **only** when the
  value is in `STATUS_VALUES` (i.e., was consumed as the status axis). `promoted` fails that test,
  so it falls to `block[key] = value` and is preserved verbatim — confirming #529's fold-comment.

## Decision 1 — `promoted` maps to `in-progress`; no third status is introduced

`plugin/skills/backlog/adapter-mode.md`'s "Status vocabulary bridge" table already states this
mapping for agents calling `status --to` by hand:

```
| `promoted` (in an active build plan) | **`in-progress`** |
```

and `SKILL.md`'s three-way offer already drives it in practice: *delegate it* sets
`status <id> --to in-progress` on the Issues backend. This is not a new interpretation invented
for this fix — it is the meaning the framework's own current vocabulary already assigns
`promoted`: `SKILL.md`'s `update` doc calls it "typically... when starting work on an item," and
`/backlog pick` excludes it as "already in flight." That is "actively being worked," which is
exactly `in-progress`.

**This answers the open question in #529 rather than sidestepping it.** #529's corpus used `promoted`
to mean "code landed, awaiting the release flip" — nearer shipped-pending. But shipped-pending has
no encoding in the service's five-value axis (Data Model closes that set deliberately), and
inventing a sixth value to carry one historical corpus's usage would misdocument what `promoted`
means going forward, when every other place in this codebase that defines the word (SKILL.md,
adapter-mode.md, the `pick` exclusion) already means "in flight," not "shipped, pending release."
The fix teaches the importer the framework's own already-declared meaning; it does not need to
also be right about every past author's private usage. The raw word survives undecoded in the
block regardless (Decision 2 note below), so a corpus with genuinely divergent historical usage is
still inspectable, just not silently reinterpreted for the operator.

## Decision 2 — the mapping is a small alias table in `encode.py`, shared for meaning only

A single `LEGACY_STATUS_ALIASES` dict + `canonical_status()` lookup function in `encode.py` (the
module that already owns `STATUS_VALUES`/`_STATUS_ENCODING`, the vocabulary's one home). Both
`_target_status` (import) and the new `_source_expected_status` (verify — Decision 3) call this
same function, because the **meaning** of `promoted` must never drift between the two sides. What
must *not* be shared is the surrounding procedural logic — that is exactly the coupling Decision 3
removes.

**`_block_for` is deliberately left unchanged.** It still preserves `status: promoted` verbatim in
the block even after this fix teaches the importer to decode it, because now *both* facts are true
on the migrated issue at once: the native `status:in-progress` label (correctly decoded, drives
every query) and the original word (provenance — this item was `promoted` in the markdown, for an
operator or a future migration-scrub reader who wants to know that). Suppressing the block field
once the value becomes decodable would delete real information for zero benefit; nothing downstream
depends on its absence.

## Decision 3 — `verify_migration` computes its expected status independently of `_target_status`

The fix for the shared-root problem #672 names and #729's own suggested fix 2 calls "the more
valuable of the two \[status] fixes — it addresses a class rather than an instance." A new
`_source_expected_status(record)` is added beside `_target_status`, operating **only** on two new
raw fields captured on `ImportRecord` at parse time — never calling `_target_status` and never
reading `record.status`:

- `status_source: str` — the item's raw `status:` metadata, unstripped-of-meaning, `""` if absent.
- `archived_section: bool` — whether the item's section matched `_is_archived` at parse time.

`_source_expected_status` re-derives the expected status from those two facts directly. This
duplicates `_target_status`'s ~3-line shape deliberately — true independence, not a refactor that
would restore the exact coupling being fixed — and both functions meet only at
`encode.canonical_status`, the one point of intentional sharing (Decision 2). A future defect
introduced into `_target_status`'s procedural logic (a bad conditional, a mis-ordered check) can no
longer make `verify_migration` silently agree with it, because verify's expectation is computed by
a different function reading different (raw, pre-coercion) inputs.

## Decision 4 — reject rather than coerce, mirroring `preflight_titles` exactly

An explicit `status:` value that is neither canonical nor a known alias, on a **non-archived**
item, is no longer silently written as `open`. A new `preflight_statuses(records)` — same shape,
same place in the sequence, same all-or-nothing refusal as the existing `preflight_titles` — runs
before the first write and refuses the whole corpus if any offender exists, naming every one.

**Scoped to the non-archived case only, deliberately narrower than "any invalid status."** An
archived-section item with an invalid/stale `status:` already resolves sensibly to `"dropped"` via
`_target_status`'s existing section-fallback — that branch is correct today, is not what #729's
evidence is about (its motivating case is an *open* item silently downgraded), and hard-refusing a
corpus over a harmless archived-item quirk would be a usability regression with no correctness
gain. The check fires only where the old code's silence was actually misleading: a *non-archived*
item with an unrecognized status, which used to read as ordinary `open` with no signal anything
was lost.

**Whole-corpus fail-fast, not a per-item skip, even though the issue's own wording says "failing
... for that item."** This repo already has exactly one idiom for "a pre-write property this
migration cannot tolerate": `preflight_titles`, chosen there because it costs zero writes and
reports the complete offender list in the first second rather than discovering problems one row at
a time mid-run. A second, differently-shaped idiom for the same class of problem (bad source
vocabulary) would be inconsistent for no offsetting benefit — `promoted` itself, the one case
observed in practice, is now a recognized alias (Decision 1), so a genuine offender under this
check is expected to be rare (a typo, not a documented word), which is exactly when a single
sharp refusal beats a partial run.

An item with **no** `status:` field at all is unaffected — that is the existing, correct
default-to-`open` path and is not touched by this check.

## Decision 5 — `status_mismatch`'s remedy text states the overwrite direction and risk

The issue's Symptom 5 is that the current advisory text ("re-run the import, which reconciles the
status axis on already-migrated items too") steers an operator who just hand-corrected a
`promoted` item into reverting their own fix, because it never says import overwrites the *target*
with the *source* — the wrong direction when the target was the one deliberately corrected. This
is the "at minimum-minimum" bar the issue itself sets as acceptable (Section 5 below is the literal
text change) — full drift-vs-correction disambiguation is not attempted, because
`verify_migration` has no way to know *why* the two differ, only that they do.

## Section 1 — `encode.py`: the alias table

```python
#: Legacy (markdown-only) status words that map onto a canonical service value — the single
#: source of truth for "this word from the old vocabulary means this axis value here"
#: (`adapter-mode.md`'s Status vocabulary bridge table, made machine-real). `promoted` (an
#: active build plan) means "actively being worked," matching that already-documented bridge
#: and `SKILL.md`'s `update`/`pick` usage — see #729 Decision 1. No other legacy word currently
#: needs translation.
LEGACY_STATUS_ALIASES: dict[str, str] = {"promoted": "in-progress"}


def canonical_status(raw: str) -> str | None:
    """`raw` (a markdown `status:` value) resolved to a canonical service status: itself if
    already canonical, its mapped value if a known legacy alias (`LEGACY_STATUS_ALIASES`),
    else `None` — genuinely unrecognized by either vocabulary. The one function both
    `migrate._target_status` (the importer's transform) and `migrate._source_expected_status`
    (verify's independent check, #729 Decision 3) call, so the *meaning* of a legacy word can
    never drift between the two — only how each side handles a non-match may differ."""
    raw = (raw or "").strip()
    if raw in STATUS_VALUES:
        return raw
    return LEGACY_STATUS_ALIASES.get(raw)
```

Placed directly after `STATUS_VALUES`'s definition, before `STATUS_OPEN_LABELS`.

## Section 2 — `migrate.py`: `ImportRecord` gains two raw fields

```python
__slots__ = ("pfx", "title", "body", "status", "labels", "block", "status_source", "archived_section")

def __init__(
    self,
    *,
    pfx: str | None,
    title: str,
    body: str,
    status: str,
    labels: list[str],
    block: dict,
    status_source: str,
    archived_section: bool,
) -> None:
    self.pfx = pfx
    self.title = title
    self.body = body
    self.status = status
    self.labels = labels
    self.block = block
    self.status_source = status_source
    self.archived_section = archived_section
```

`_record_from_item` (the sole construction site, `migrate.py:625-633`) is updated to compute and
pass both:

```python
def _record_from_item(item: legacy.BacklogItem, pfx: str | None) -> ImportRecord:
    title = _ID_MARKER_RE.sub("", item.title).strip()
    status_source = (item.metadata.get("status") or "").strip()
    archived_section = _is_archived(item.section)
    status = _target_status(item)
    labels = _labels_for(item, status)
    block = _block_for(item, pfx)
    return ImportRecord(
        pfx=pfx, title=title, body=item.body, status=status, labels=labels, block=block,
        status_source=status_source, archived_section=archived_section,
    )
```

`_target_status` itself simplifies to use the shared alias lookup (Decision 1/2 — this is the
literal fix for the reported bug):

```python
def _target_status(item: legacy.BacklogItem) -> str:
    """The two-axis status *target* for an imported item: the explicit `status:` metadata —
    itself if canonical, or its legacy-alias mapping (`encode.canonical_status`, e.g.
    `promoted` -> `in-progress`) — else inferred from the section (`## Archive` -> closed).
    An unrecognized, non-archived value never reaches here: `preflight_statuses` refuses the
    whole import first (#729 Decision 4)."""
    canonical = encode.canonical_status((item.metadata.get("status") or "").strip())
    if canonical is not None:
        return canonical
    if _is_archived(item.section):
        return "dropped"
    return "open"
```

## Section 3 — `migrate.py`: `preflight_statuses` + `import_items` wiring

New function, placed directly after `preflight_titles` (mirrors its shape exactly):

```python
def preflight_statuses(records: list[ImportRecord]) -> list[dict]:
    """Every record whose explicit `status:` metadata is neither a canonical service value nor
    a known legacy alias (`encode.canonical_status`), and whose section is not archived — in
    source order. Pure — no transport, no model, no I/O.

    Mirrors `preflight_titles`'s place and shape: the whole record set is checked before the
    first write, so a corpus carrying a status word the importer cannot decode fails loudly, in
    the first second, naming every offender — never guessed into `open` and discovered later by
    reconciling counts (#529, #729).

    Scoped to non-archived records only: an archived item with an unrecognized status already
    resolves correctly via the section fallback (`_target_status`) and is not this check's
    concern. A record with no explicit `status:` at all (`status_source == ""`) is not an
    offender either — that is the existing, correct default-to-`open` path.
    """
    offenders: list[dict] = []
    for index, record in enumerate(records):
        if (
            record.status_source
            and not record.archived_section
            and encode.canonical_status(record.status_source) is None
        ):
            offenders.append(
                {
                    "index": index,
                    "key": record.key_label(),
                    "title": record.title,
                    "status": record.status_source,
                }
            )
    return offenders
```

`import_items` calls it immediately after the existing `preflight_titles` gate, same refusal
shape (`migrate.py`, top of the function body, ~line 940):

```python
    offenders = preflight_titles(records)
    if offenders:
        return core.error(... )  # unchanged
    status_offenders = preflight_statuses(records)
    if status_offenders:
        return core.error(
            "validation",
            f"{len(status_offenders)} of {len(records)} item(s) carry a `status:` value the "
            "importer does not recognize — nothing was written. Either it is a typo (fix it in "
            "the source and re-run), or it is a legacy word that needs a mapping "
            "(`encode.LEGACY_STATUS_ALIASES`) — see the offending values below.",
            details={
                "unrecognized_statuses": status_offenders,
                "total_source": len(records),
                "created": [],
                "skipped": [],
                "resumable": False,
            },
        )
```

Because `import_backlog` calls `import_items` for every real import, this covers the write path
with one call site, matching `preflight_titles`'s placement exactly.

## Section 4 — `migrate.py`: `_source_expected_status` + `verify_migration`

New function, placed beside `_target_status`:

```python
def _source_expected_status(record: ImportRecord) -> str:
    """The status `verify_migration` expects a record to hold on the target — computed
    INDEPENDENTLY of `_target_status` (the importer's own transform), by design: the fix for
    "the gate's expectation is derived from the same code as the outcome it is checking" (#729
    Decision 3; #672 names the identical root one layer down in the Critic's coverage
    machinery). Reads only `record.status_source`/`record.archived_section` — the two raw facts
    captured at parse time, before any coercion — never `record.status` itself and never calls
    `_target_status`. Meets `_target_status` only at `encode.canonical_status`, which is correct
    to share (it is the single source of truth for what a legacy WORD means, not for how the
    importer APPLIES it)."""
    canonical = encode.canonical_status(record.status_source)
    if canonical is not None:
        return canonical
    return "dropped" if record.archived_section else "open"
```

`verify_migration`'s `status_mismatch` comparison (`migrate.py:1506-1511`) changes its one
comparison operand from `r.status` to this independent computation:

```python
    status_mismatch = [
        f"{r.pfx} (source: {_source_expected_status(r)}, target: {aliased[r.pfx]})"
        for r in records
        if r.pfx and r.pfx in aliased and r.pfx not in ambiguous
        and aliased[r.pfx] != _source_expected_status(r)
    ]
```

No other line in `verify_migration` changes. `records` here already comes from
`collect_records`/`apply_archive_scope`, both unchanged by this item — only the field they
populate on each `ImportRecord` (Section 2) is new.

## Section 5 — `migrate.py`: `_incompleteness_remedy`'s `status_mismatch` text

**Before** (`migrate.py:1579-1585`):

```python
    if status_mismatch:
        parts.append(
            f"the {len(status_mismatch)} item(s) in `status_mismatch` are on the target "
            "at the WRONG status — the issue exists and is keyed, but a status "
            "reconcile never landed (see `status_unreconciled` in the import result); "
            "re-run the import, which reconciles the status axis on already-migrated "
            "items too"
        )
```

**After:**

```python
    if status_mismatch:
        parts.append(
            f"the {len(status_mismatch)} item(s) in `status_mismatch` are on the target at a "
            "DIFFERENT status than the source records for them — either a reconcile never "
            "landed (see `status_unreconciled` in the import result), or the target was "
            "deliberately corrected by hand since import. Re-running the import OVERWRITES "
            "the target's status with the source's: right in the first case, WRONG in the "
            "second — it silently reverts a hand correction (e.g. a status the importer "
            "mis-decoded and you later fixed with `status --to`). Check which case you are in "
            "before re-running; if the target was deliberately corrected, update the source's "
            "`status:` to match instead, or leave it — do not re-run just to clear this line"
        )
    )
```

This is the issue's own "minimum-minimum" bar (Decision 5) — it states the direction and the risk
explicitly; it does not attempt to mechanically distinguish the two cases, which `verify_migration`
has no way to do from a single scan.

## Section 6 — `cli.py` / `restructure.py`: `restructure-preview` surfaces the same offenders

`restructure-preview` does not call `import_items` (it is offline, no transport — `cli.py:1094+`),
so it separately calls `migrate.preflight_titles` today (`cli.py:1142`) to show the operator what
the real import would refuse. It must do the same for status offenders, or a preview can read
clean on a corpus the import will hard-refuse — the exact failure mode `render_preview`'s own
docstring already calls out for titles ("a false statement in the owner's aggregate pre-approval
artifact... is worse than any crash").

`cli.py::_run_restructure_preview`, immediately after the existing `preflight_offenders` line:

```python
    preflight_offenders = migrate.preflight_titles(applied["records"])
    status_offenders = migrate.preflight_statuses(applied["records"])
```

`restructure.render_preview` gains a required keyword `status_blocking: list[dict]` (same
no-default contract as `blocking`, for the same reason — an omitted argument must fail loudly
rather than silently print zero). Rendered in its own line + detail block directly after the
existing title-blocking section, same format:

```python
    lines.append(
        f"- **statuses the import will refuse (unrecognized `status:` value): "
        f"{len(status_blocking)}**"
    )
    if status_blocking:
        lines.append("")
        lines.append(
            "> ⚠️ **This plan cannot be imported as-is.** The import refuses any non-archived "
            "item whose `status:` value it cannot decode, before its first write. Fix these "
            "in the source and re-preview:"
        )
        for item in status_blocking[:20]:
            lines.append(f">   - `{item.get('title')}` — status: `{item.get('status')}`")
        if len(status_blocking) > 20:
            lines.append(f">   - … (+{len(status_blocking) - 20} more)")
```

`cli.py`'s call site passes it through and adds two mirroring fields to the preview's `data`
envelope, alongside the existing `preflight_blocking`/`nonconforming_titles`:

```python
    preview = restructure.render_preview(
        applied, source_label=source_label, collisions=collisions,
        blocking=preflight_offenders, status_blocking=status_offenders,
    )
    ...
    data = {
        ...
        "preflight_blocking": len(preflight_offenders),
        "nonconforming_titles": preflight_offenders,
        "status_preflight_blocking": len(status_offenders),
        "unrecognized_statuses": status_offenders,
        ...
    }
```

## Files touched

| File | Change |
|---|---|
| `plugin/lib/backlog/encode.py` | New `LEGACY_STATUS_ALIASES` + `canonical_status()` (Section 1) |
| `plugin/lib/backlog/migrate.py` | `ImportRecord` gains `status_source`/`archived_section` (Section 2); `_target_status` simplified to use `canonical_status` (Section 2); new `preflight_statuses` + its call in `import_items` (Section 3); new `_source_expected_status` + `verify_migration`'s one-line comparison change (Section 4); `_incompleteness_remedy`'s `status_mismatch` text (Section 5) |
| `plugin/lib/backlog/restructure.py` | `render_preview` gains required `status_blocking` param + its rendered section (Section 6) |
| `plugin/lib/backlog/cli.py` | `_run_restructure_preview` computes and threads `status_offenders` (Section 6) |

No change to `plugin/templates/backlog.md` — its documented markdown vocabulary
(`open | promoted | shipped | dropped`) is already correct for the markdown side; the divergence
this item fixes is the importer's failure to translate it, not a documentation error (Decision 1).

## Verification

No new automated test file is specified here (design-stage scope, not a build-plan chunk) — an
implementation chunk should add unit coverage for: `encode.canonical_status("promoted")` ==
`"in-progress"`; `canonical_status("open")` == `"open"`; `canonical_status("bogus")` is `None`;
`_target_status` on a `promoted` item returns `"in-progress"`; `preflight_statuses` flags a
non-archived unrecognized status and does **not** flag an archived one or an empty one;
`_source_expected_status` matches `_target_status`'s output for every valid/alias/archived/empty
case (a parity test, not a shared-implementation test — it must call the two functions
separately); `verify_migration`'s `status_mismatch` reports `in-progress` as the expected value for
an already-migrated `promoted` item currently sitting at plain `open` on the target (the exact
motivating repro from the issue).

Acceptance, carried from the issue's own "Suggested fix" numbering:

- [ ] **Fix 1 (reconcile vocabularies)** — `promoted` decodes to `in-progress` at import time;
      `templates/backlog.md` is left as-is (already correct) — Decision 1, Section 1/2.
- [ ] **Fix 2 (gate independent of the transform)** — `verify_migration`'s `status_mismatch` is
      computed by `_source_expected_status`, which never calls `_target_status` or reads
      `record.status` — Decision 3, Section 4.
- [ ] **Fix 3 (no unqualified re-import advice)** — the `status_mismatch` remedy text states the
      overwrite direction and the hand-correction risk before advising a re-run — Decision 5,
      Section 5.
- [ ] **Fix 4 (reject rather than coerce)** — a non-archived item with an unrecognized `status:`
      refuses the whole import (and is surfaced in `restructure-preview`), rather than silently
      becoming `open` — Decision 4, Section 3/6.
- [ ] The motivating repro — a `promoted` item already migrated as plain `open` — is caught by
      `verify-migration` as a `status_mismatch` (`source: in-progress, target: open`) once this
      ships, and the corrected remedy text tells the operator what re-running will and will not do.

## Evidence / references

- `plugin/lib/backlog/migrate.py:636-647` (`_target_status`), `:668-681` (`_block_for`),
  `:1380-1519` (`verify_migration`, `status_mismatch` derivation), `:1579-1585`
  (`_incompleteness_remedy`) — read in full to confirm the shared-function root cause and the
  block-preservation fact.
- `plugin/lib/backlog/encode.py:55-70` (`_STATUS_ENCODING`/`STATUS_VALUES`) — confirms the service
  vocabulary has no `promoted` and no sixth "shipped-pending" value.
- `plugin/templates/backlog.md:41` — confirms the markdown vocabulary documents `promoted` and is
  not itself wrong (Decision 1).
- `plugin/skills/backlog/adapter-mode.md:161-168` — the already-documented, already-used
  `promoted` → `in-progress` bridge table this design's mapping matches exactly, rather than
  inventing.
- `plugin/skills/backlog/SKILL.md:85,100,117` — `promoted`'s active, current meaning
  ("in flight," excluded from `pick`), grounding Decision 1's resolution of #529's open question.
- `plugin/lib/backlog/migrate.py:918-950` (`preflight_titles`) — the existing idiom
  `preflight_statuses` mirrors exactly (Decision 4).
- `plugin/lib/backlog/restructure.py:224-284` (`render_preview`) and
  `plugin/lib/backlog/cli.py:1094-1170` (`_run_restructure_preview`) — the preview path's
  existing title-preflight wiring, mirrored for status offenders (Section 6).
- Issue #529 (closed 2026-09-01, `superseded_by: #729`) — predecessor finding, the block-
  preservation fact, and the shipped-pending ambiguity Decision 1 resolves.
- Issue #672 — the identical "gate derives its expectation from the code it is checking" concern,
  independent evidence this codebase already recognizes the failure class Decision 3 fixes.
