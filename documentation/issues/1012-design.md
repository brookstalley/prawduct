# Issue #1012 — Change-log: One Fragment File per Change: Design

`status: draft · stage: design · area: release · added: 2026-10-19 · source: scheduled backlog
session · issue: https://github.com/brookstalley/prawduct/issues/1012`

Builds on `1012-requirements.md` (FRG1–FRG8 and Decisions 1–6; carried onto this branch unchanged from the
earlier session branch `claude/youthful-galileo-gs99al`). The owner has
not yet advanced the issue's stage label, so this design is **conditional on the requirements as
drafted**; every place it departs from them is flagged "Departs from FRG…". It answers the five
"Open for design" questions and fixes the module layout, the cut algorithm, the migration, and the
chunking.

## Grounding facts (re-verified 2026-10-19)

- **`type` is already a free vocabulary with synonyms.** Across the live log and archive:
  `feature` 103, `fix` 203, `feat` 30, `bugfix` 26, `chore` 25, `refactor` 18, `docs` 15,
  `governance` 2, `perf` 2, `improvement` 1. `change_log.py` does not validate it at all
  (`validate_change_log_tags` checks only `release=` shape and tag conflicts), and the template's
  grammar block does not document `type=`. The requirements' "the set `change_log.py` already
  accepts" does not exist; the design has to define it.
- **The release-time edit to `plugin/CHANGELOG.md` is adjudicated, not mechanical.** Runbook step
  10 renames the open `## vX.Y.Z-dev` section and asks a human to confirm its first non-empty line
  is the *release headline*; the banner reads that first physical line (runbook note near `:616`).
  Per-scope paragraphs follow. So the cut can render per-scope bodies, but cannot invent the
  headline.
- **Gitflow already self-converges the `release=` tag at the cut** (`pr/SKILL.md` Step 1d and the
  merge step: "release tags additionally self-converge at the release — it tags every unreleased
  entry"). Fragments make that a loop over files instead of an edit of the single shared log.
- **`change_log_archive.py` is content-agnostic about history**: `split` / `select` / `apply`
  operate on `## ` blocks, with `invariant_violations` comparing a before/after fingerprint of
  entry headers and tag lines. Rendering a fragment into a block in the existing grammar lets the
  archive reuse that machinery unchanged (FRG4 / Decision 4).
- **`.prawduct/` is non-judgeable**, so adding `.prawduct/changes/*.md` does not reopen cumulative
  review (`coverage_algebra.is_judgeable_path`). Step 1c's `check-change-log-entry` currently
  demands a new `## ` header in the log versus the merge base (`coverage.py` `no-entry`,
  `entry-edited-not-added`); under fragments it must demand a new file.

## Design decisions

### D1 — Module: `plugin/lib/change_fragments.py` is the single owner

One new module owns the fragment format; no other module parses a fragment. Public surface:

| function | role |
|---|---|
| `FRAGMENT_DIR_REL = ".prawduct/changes"` | the layout constant (cf. `CHANGE_LOG_REL_PATH`) |
| `parse_fragment(text, *, filename) -> Fragment` | frontmatter + body split; raises `FragmentError(code, detail)` |
| `validate_fragment(fragment) -> list[str]` | schema errors, one per violation |
| `load_pending(root) -> list[Fragment]` | every file in the dir (all are pending after a cut, see D4) |
| `render_entry(fragment) -> str` | the legacy `## date: title` + tag line + body block, for the archive |
| `render_consumer_section(fragments) -> str` | the `plugin/CHANGELOG.md` per-scope text |
| `legacy_entries_as_fragments(text)` | migration reader (D6) |

`Fragment` is a frozen dataclass: `scope, type, date, title, release, issues, narrative, consumer_note`.
Frontmatter is read with the repo's existing frontmatter reader (the one `plan_index` uses) so
there is no second YAML dialect; unknown keys are an error, not preserved (this **departs from the
legacy parser's "preserve unknown keys"** deliberately — the point of the move is that the tag
surface stops being open-ended; a new key is a schema change made in `change_fragments.py`).

`change_log.py` keeps `RETIRED_TAG_KEYS`, `RELEASE_VALUE_RE` and the legacy parser for the dual-shape
window; `change_fragments` imports `RELEASE_VALUE_RE` rather than copying it, so the
`release=unreleased` guard has one definition.

### D2 — Schema (settles FRG2 and the open `type` question)

```
---
type: feature          # closed set, below
scope: change-log-fragments   # == filename stem; == build plan `scope:`
date: 2026-10-19
title: One fragment per change
issues: [1012]         # optional, ints
release: v3.8.0        # optional; absent = pending; must match RELEASE_VALUE_RE
---
<narrative: names every chunk shipped>

## Consumer note
<optional; user-facing text>
```

**`type` is a closed set of seven: `feature`, `fix`, `chore`, `docs`, `refactor`, `perf`,
`governance`.** Synonyms normalise at migration, never silently at read: `feat → feature`,
`bugfix → fix`, `improvement → feature`. Reasoning: five distinct spellings of two concepts across
~400 entries is exactly the drift a closed set exists to stop, and no reader keys on `type` today
(grep of `plugin/lib` finds none), so narrowing costs nothing. A fragment using a non-member is
refused with `bad-type:<value>` naming the set. Legacy archived entries keep their original
spelling — history is not rewritten.

Other rules: `scope` must equal the filename stem (`scope-mismatch`); filename stems are
lowercase `[a-z0-9][a-z0-9-]*` so they are also safe as a path component on every platform
(`bad-scope-slug`); `date` must parse; `title` must be non-empty and single-line; the narrative
must be non-empty. `chunks` / `status` are refused with the existing retired-key message.

### D3 — Consumer note is a section of the same file (answers the issue's open question)

Confirmed as in requirements Decision 1. The parse rule is exact: the **first line that is
exactly `## Consumer note`** splits narrative from note; a second such heading is an error
(`duplicate-consumer-note`). A narrative that needs its own `##` headings must use `###`. A missing
note on a `feature` or `fix` whose `scope` is classified `ships` in the release plan is a
`release_readiness` **warning** (`missing-consumer-note`), not an error: internal-only features
exist, and a hard error would teach authors to write filler.

### D4 — The cut: `prawduct-hook cut-change-log --release vX.Y.Z [--apply]`

Name decided: it cuts the *change record*; `archive-change-log` keeps meaning "bound the live
log". Dry-run by default, `--apply` writes — the same two-mode shape as `archive-change-log`.
Algorithm, in an order chosen so a failure leaves a re-runnable state:

1. **Validate first, write nothing.** Load every fragment; any `validate_fragment` error or a
   `release` already set aborts with the full error list. Compute the plan and print it.
2. **Render archive blocks** with `render_entry`, newest `date` first (ties by scope), each tagged
   `release=vX.Y.Z`. Append to `.prawduct/change-log-archive/YYYY-MM.md` bucketed by the entry
   `date`'s month (the existing `_compose_bucket`). Idempotence key: a block with the same
   `(date, scope)` already in the target bucket is skipped, not duplicated — this is what makes a
   re-run after a partial failure safe.
3. **Render `plugin/CHANGELOG.md`**: insert the per-scope consumer notes into the open
   `## vX.Y.Z-dev` section *under* its existing headline line, then leave the rename to
   `## vX.Y.Z` and the headline adjudication to the runbook (step 10 stays a human step). The cut
   never writes a headline; it refuses (`no-headline`) if the open section has none, matching the
   banner's reading rule.
4. **Remove** the cut fragments (`git rm`-equivalent; the history is the audit trail). The
   directory holds only pending fragments again.

Steps 2–4 run as one transaction over a staging copy, written with `os.replace` per file after
all renders succeed; if any render fails nothing is written. The `invariant_violations`
fingerprint check from `change_log_archive` is applied to each touched archive bucket as it is
today.

**Stamping on trunk** (open question: shared stamping function). On a trunk base Step 1d stamps
`release` into the closing PR's own fragment. Both paths call
`change_fragments.stamp_release(fragment_path, version)`, which validates against
`RELEASE_VALUE_RE` and rewrites only the frontmatter line. On trunk the fragment then lives with
`release` set and is **removed at the next cut or by the same PR's merge-time archive**: to keep
"directory = pending set" true, the trunk path calls the same `cut` machinery for a one-fragment
set instead of stamping in place. This **departs from FRG4's "cut stamps then moves"** only in
that trunk uses the cut for a set of one; there is a single code path and `release` is therefore
never observed on a file in the directory, which lets `load_pending` treat *every* file as pending
and makes a stray `release:` in the directory an error (`released-fragment-in-pending-dir`).

### D5 — Reopens (answers #783 interaction)

A reopened scope is a **new fragment with a new scope**: `<original>-reopen-N` where N is the
count of existing archive entries whose scope is `<original>` or `<original>-reopen-*`, plus one.
The new fragment carries `reopens: <original-scope>` — one added optional frontmatter key
(schema addendum to D2). Editing the archived entry is rejected: the archive is verbatim and
append-only. This also resolves #783's "no tag convention" because the convention is now a field
that validates (`reopens` must name a scope present in the archive or the pending set,
`unknown-reopen-target`).

### D6 — Dual-shape window and migration

**Readers.** `release_readiness.release_pending_entries` becomes
`pending_scopes(root) -> list[PendingScope]` returning the union of (a) legacy-log entries with a
`scope=` and no `release=` and (b) fragments. A scope appearing in both is a hard error
(`scope-in-both-shapes`) — it is the migration's bug signature. Callers named in FRG6 switch to
`pending_scopes`; none reads either file directly any more, which is the single-owner fix for a
class (a reader that knows the storage shape) rather than for each caller. **Expiry:** the
legacy branch of `pending_scopes` is deleted one minor release after `doctor` reports no repo
shape drift in this repo's own telemetry; the requirement is recorded as a named backlog item at
build time rather than a date here, because the gate is "no migrated-by-hand stragglers", not time.

**Migration** (`prawduct-hook migrate-change-log`, called by `/prawduct:migrate` and offered by
`/prawduct:doctor`): for each legacy entry with a tag line and no `release=`, write
`.prawduct/changes/<scope>.md` (type normalised per D2, `title`/`date` from the `## ` header,
narrative = body, no consumer note) and remove the entry from `change-log.md`; shipped entries
and untagged entries are left alone. Refusals, each a named code and no write: an entry with
`release=<non-version>` (`unreleased-placeholder` — the v3.2.8 incident class; the author
decides), two entries sharing a scope (`duplicate-scope`), an entry with two tag lines
(`multi-tag-line`), a `scope` that fails the slug rule. One commit, `git revert`-able, idempotent
(second run finds nothing to convert). New products: `init_product` scaffolds the directory with a
`.gitkeep` and a template fragment under `plugin/templates/change-fragment.md`, and no
`change-log.md`. Once a repo has no pending legacy entries, `gitattributes_probes` stops requiring
the `merge=union` line and a repo with fragments and no pending legacy entries gets an advisory
to remove it; `probe_change_log_union_merge` is gated on "legacy ledger still has pending
entries", not deleted, until the window closes.

### D7 — Gate wiring

- **PR Step 1c** (`coverage.check-change-log-entry`): in a repo with `.prawduct/changes/`, require
  the branch to add exactly one new fragment (or edit one it already added); run
  `validate_fragment`; surface its error codes as the probe's refusal. The legacy `no-entry` path
  stays for unmigrated repos. This makes FRG2's "refused mechanically" literal.
- **`check-releasability`**: the pending set, the `unclassifiable-pending-entry` check (now
  impossible by construction, kept as a defence for the legacy branch) and the classification
  coverage all read `pending_scopes`.
- **`record_lint`**: lints the fragment directory with the same `validate_fragment`; the
  retired-key probe collapses into it.
- **Critic cross-check and `pr_payload`**: read `load_pending` instead of grepping the log.
- **`banner.py`**: unchanged — it reads only `plugin/CHANGELOG.md`.

### D8 — #834 interaction

No change to the requirements' Decision 5. Concretely: #834's derivation target becomes "write
the fragment's `title`, `scope`, `issues` and narrative skeleton from the PR body and the active
build plan's `scope:`" at Create Step 5; its design should be rebased once this lands. Build
order is #1012 first because the fragment gives #834 a single new-file target and removes its
merge-with-existing-section problem.

## Alternatives rejected

- **Two files per change (consumer note separate).** Recreates the scope-present-in-one-absent-in-
  the-other pairing defect; rejected in requirements Decision 1, and nothing in the grounding
  facts argues otherwise.
- **Keep `merge=union` and only add validation.** Does not address the #857 resurrection class,
  and validation of an HTML-comment line still has no structural anchor.
- **Open `type` vocabulary with a warning.** Preserves the synonym drift measured above; a closed
  set costs one normalisation table at migration.
- **Cut stamps in place and leaves fragments until a later sweep.** Makes "directory = pending
  set" false and forces every reader to filter by `release`.
- **Generate the `plugin/CHANGELOG.md` headline.** The headline is the release's one-sentence
  adjudication (the banner shows it); a generated one would be filler and the runbook's human
  confirmation step would become rubber-stamping.

## Build plan sketch (chunks)

1. **Format core** — `change_fragments.py` (`parse`/`validate`/`render_*`/`stamp_release`),
   template, unit tests including a red-verified case per error code (feed each validator a case
   it must refuse — core.md: a check never seen to fail proves nothing). Done when every code in
   D2/D3 has a failing fixture.
2. **Readers** — `pending_scopes`, switch `release_readiness`, `record_lint`, `pr_payload`,
   `plan_backfill`, Critic cross-check; Step 1c probe. Done when the existing
   `release_readiness` test corpus passes unchanged against both shapes.
3. **Cut command** — `cut-change-log`, transactional, idempotent; trunk Step 1d calls it. Done
   when a two-branch merge test (real `git merge`, no union driver) is clean and a cut over a
   fixture produces byte-identical archive output to the legacy renderer.
4. **Migration + scaffolding** — `migrate-change-log`, `init_product`, doctor/migrate/onboard
   skill text, `gitattributes_probes`. Done when all five fixtures in FRG7 pass and the second
   run is a no-op.
5. **Docs and runbooks** — `release-process.md`, both runbooks (Phase 1 steps 1–3 and step 10
   replaced by the cut command), the template grammar comment, PR skill Steps 1c/1d. Per the
   describing-artifacts rule in core.md, search for the *claim* ("release-pending is the absence of
   `release=`"; "append at the top"), not the edited tokens.

## Risks and open items

- **Dev-track consumers mid-migration** read a plugin that supports both shapes; a consumer pinned
  to an older plugin that reads only the legacy log would see an empty pending set after
  migration and report "nothing to cut". Mitigation: `migrate-change-log` refuses unless the
  installed plugin version is the one that introduced dual-shape readers, and `doctor` checks
  the same. Needs a version constant at build time.
- **Cut transaction on Windows** (`os.replace` across files is not atomic as a set). The staging
  copy plus idempotence key in D4 step 2 is the recovery story; confirm it is sufficient or add a
  `.cut-in-progress` marker.
- **Whether `issues:` is worth carrying.** Nothing reads it yet; per core.md ("a channel produced
  and never consumed is a defect") it ships only if chunk 2 gives it a consumer — the natural one
  is #834's close-the-items step. Otherwise drop it from D2.
- **Owner confirmation needed** on the closed `type` set (D2) and the `reopens` key (D5); both are
  new vocabulary.
