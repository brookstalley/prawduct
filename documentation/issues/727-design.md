# Issue #727 — Backlog template item-shape example is indented, parser needs column 0: Design

`status: draft · stage: design · area: backlog · added: 2026-08-30 · source: scheduled backlog
session · issue: https://github.com/brookstalley/prawduct/issues/727`

No separate requirements doc exists for this item — it was filed as a bug report with a verified
root cause and file/line citations already in hand (root cause confirmed by reading
`lib/backlog/legacy.py:40`), which is the requirements-stage work for a bug of this shape. This
document picks the fix from the issue's own "Suggested fix" and specifies it exactly.

## Root cause (restated from the issue, verified)

`plugin/templates/backlog.md`'s `== Item shape ==` example — the only column-0-bullet-shaped
content in the whole file — is nested two spaces inside the file's single leading HTML comment
(lines 3–63). `lib/backlog/legacy.py`'s `ITEM_RE = re.compile(r"^- (.+)$")` anchors an item's
bullet at column 0 on purpose (so indented body bullets don't false-positive as new items). An
author who reads the template and pattern-matches its example — the only model available in a
freshly scaffolded product with no prior backlog — writes real items at the same two-space
indent the template showed them, and every one of those items is invisible to the parser. The
failure is silent: an all-indented file parses to zero items, `backlog import` creates nothing,
and `verify-migration` compares an empty source set against an empty alias set, finds them
consistent, and exits 0.

## Scope for this item

The issue names three independent fix directions plus one adjacent hardening. This item (labeled
`effort: S`) ships the first two — they are the ones that close the authoring trap at its source,
require no code change, and are what "cheapest and highest-value" in the issue's own wording
describes:

1. **De-indent the template's example** so it is actually column-0, matching the parser.
2. **State the column-0 constraint explicitly**, so a reader who does deviate has a rule to check
   against, not just an example to eyeball.

**The adjacent "cheap hardening" the issue suggests — have `init-product` scaffold a correct
example — needs no separate change.** `lib/init_product.py:53` maps
`(".prawduct/backlog.md", "backlog.md")`: it copies `templates/backlog.md` verbatim into every new
product. Fixing the template fixes every future scaffold in the same edit; there is no second
copy to chase.

**Out of scope, left for a follow-up item:** direction 3, "refuse the empty case rather than
passing it" (hardening `import_backlog`/`verify_migration` in `migrate.py` to warn when a
non-trivial-byte-count source parses to zero items). The issue itself calls this "the part that
matters most" for turning the *class* of failure non-silent, but it is a behavior change to two
gate functions plus their tests — `effort: M` at least, not `S` — and it is independent of the
template fix: fixing the template closes *this* instance of the trap without it, and the gate
hardening would still be worth having even if no template had ever been wrong (any hand-authored
or externally-generated backlog can hit the same empty-vs-empty blindness). Recommend filing it
as its own backlog item rather than folding it into this one — consistent with the item-shape
title standard's own atomicity test ("would a single change close all of these?" — no: the
template fix and the gate hardening are two different changes with two different blast radii).

## Exact change — `plugin/templates/backlog.md`

**One file changes.** No other copy of this example exists in the repo (`documentation/backlog-
system-requirements.md` §4.1's own item-shape example is already column-0, inside a fenced code
block — confirmed by reading it; it is not part of this defect).

The whole `== Item shape ==` sub-block (current lines 18–63, ending at the comment's closing
`-->`) is uniformly indented two spaces past the heading. Dedent every line in that span by
exactly two spaces — preserving all *relative* nesting (the four-space/ten-space/twelve-space
sub-explanations under "ID format" and "Metadata bar" all shift down by the same two, so their
relationship to each other is untouched) — and insert one new instruction paragraph immediately
after the `== Item shape ==` heading, before the example bullet.

Full replacement text for current lines 16–63 (`== Item shape ==` through the comment's closing
`-->`), verified byte-for-byte against the current file by scripting the dedent rather than
hand-counting spaces:

```markdown
== Item shape ==

**Items begin at column 0 — `- ` with no leading whitespace.** Everything indented under an
item (the metadata bar, the body) is read as part of it; an item bullet that is itself
indented is invisible to the parser and silently drops out of the backlog.

- **[PFX-XXXX]** One-line title
  `effort: M · impact: M · area: stop-hook · source: reflection · added: 2026-05-29 · status: open`

  Free-form body of any length — a single sentence or multi-paragraph analysis
  with file refs, fix-shape, and open questions. The author chooses what fits.

ID format `[PFX-XXXX]`:
  PFX = 2–3 uppercase letters naming the work-space the item was filed from.
        Derive a sensible prefix from the item's area; reuse existing ones so
        related items share a prefix. Starter vocabulary (extend freely):
          STH stop-hook · CRT critic · SYN sync · LLM prompt/LLM · BKL backlog
          MIG migration · JNT janitor · MET methodology · DOC docs · TST tests
        A project may optionally declare its prefix vocabulary as
        `backlog_prefixes:` in project-state.yaml for validation — not required.
  XXXX = 4-char random alphanumeric (base36). Random IDs avoid cross-branch
         collisions; ~1.7M combinations per prefix.

Metadata bar (one backticked, dot-separated line; required on new items):
  effort: S | M | L     S = <30 min · M = hours · L = multi-chunk
  impact: S | M | L     S = cosmetic · M = quality-of-life · L = user-felt/structural
  area:   <tag>         free-form topic tag; reuse existing tags to enable grouping
  source: builder | critic | reflection | janitor | user
  added:  YYYY-MM-DD
  status: open | promoted | shipped | dropped
Optional, on the same line (distinct concepts — keep them straight):
  related:   PFX-XXXX, PFX-XXXX   cross-references to related items
  closes:    PFX-XXXX             this item supersedes another backlog item (item → item)
  closed-by: <chunk-id | scope/branch | tag>  what shipped this item (item → release), set on
                                  status=shipped; a handle that exists before the commit —
                                  never a bare commit SHA (dangles on --amend) or unassigned PR#
  reviewed:  YYYY-MM-DD           last-touched timestamp (auto-set on any update)
  accepted-by: @actor             soft claim "someone is on this" so others don't
                                  double-pick; pick/list exclude claimed items.
                                  Does NOT auto-expire; auto-cleared on ship/drop.
                                  Not a lock (backlog.md is eventually-consistent).
  stage: <lifecycle>              idea | research | requirements | design | ready.
                                  Where the item sits in the feature lifecycle;
                                  only `ready` is implementable. Absent/early =>
                                  pick routes to discovery/planning, not code.
  refs: <doc#section>, <doc>      links to governing artifacts (requirements /
                                  arch / design docs). Distinct from `related:`
                                  (which is item -> item).

Legacy items (no metadata) remain valid — tools treat them as
`effort: ? · impact: ? · area: untagged · status: open` and rank them lower.
Run `/backlog migrate` to add structure at your own pace; nothing is forced. -->
```

Everything before line 16 (the file header and the comment's opening `/backlog` command list) and
everything from `## Open` onward is untouched.

## Why dedent the whole sub-block rather than only the example bullet

De-indenting only the three example lines (bullet, metadata bar, body) and leaving "ID format",
"Metadata bar", and "Legacy items" at their current two-space indent would nest the *explanation*
of the item shape one level deeper than the *example* it explains — backwards, and confusing on
its own terms. A uniform two-space dedent of the whole sub-block keeps every existing relative
indent (the `PFX =` / `XXXX =` lines, their own sub-indented continuations, the metadata-field
table) exactly as related to each other as before; only the absolute column shifts, and only by
the two spaces that were the defect.

## Files touched

| File | Change |
|---|---|
| `plugin/templates/backlog.md` | Dedent lines 18–63 by 2 spaces; insert one new instruction paragraph after the `== Item shape ==` heading |

No change to `lib/backlog/legacy.py`, `lib/init_product.py`, or any other file — `ITEM_RE`'s
column-0 anchor is correct as-is (the issue's own root-cause section agrees: "The parser's
contract is deliberate and correct"); the defect was the template disagreeing with it, not the
parser.

## Verification

This is a documentation/template fix with a mechanically checkable acceptance test — no new
automated test is being added (none of the existing suites assert this file's content beyond the
`NON_READER_ALLOWLIST` entry in `test_cutover_prose_coherence.py`, which this change does not
touch), so verification is direct reproduction of the bug's own repro steps against the fixed
file:

1. `grep -cE '^- ' plugin/templates/backlog.md` → must return `1` (the example bullet now at
   column 0), where it returned `0` before.
2. `grep -n -i "column" plugin/templates/backlog.md` → must return at least one match (the new
   instruction paragraph), where it returned none before.
3. Extract the example between the `== Item shape ==` heading and the next blank line, run it
   through `lib.backlog.legacy.parse_backlog`, and confirm it yields exactly one item with
   `pfx="PFX"` (or however the placeholder id parses) rather than zero — the direct regression
   test for the reported failure.
4. `pytest tests/test_cutover_prose_coherence.py` stays green unmodified — confirms the
   `templates/backlog.md` allowlist entry and surrounding prose-coherence checks are unaffected.
5. Read the fixed file rendered (GitHub markdown view, where the comment is invisible) to confirm
   nothing outside the comment changed — `## Open`, `## Promoted`, `## Archive` and their own
   short comments are untouched.

## Follow-up (not this item)

File a separate backlog item for direction 3 — hardening `import_backlog` and `verify_migration`
(`lib/backlog/migrate.py`) to warn or refuse when a source file with a non-trivial byte count
parses to zero items, rather than treating empty-vs-empty as a clean pass. That item should also
decide whether the same non-trivial-but-zero signal belongs in `verify-migration`'s five-list exit
model (a sixth list, or a distinct exit code) or as a pre-check ahead of it — a decision this
item's narrower template fix does not need to make.
