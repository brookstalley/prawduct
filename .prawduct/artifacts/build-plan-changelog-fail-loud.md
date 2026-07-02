---
artifact: build-plan
version: 2
scope: changelog-fail-loud
depends_on:
  - artifact: framework-efficiency-review-2026-07-02
last_validated: 2026-07-02
---

# Build Plan — changelog-fail-loud (Wave 1 Plan B, VWS-6R4T)

Parent requirement: `.prawduct/artifacts/framework-efficiency-review-2026-07-02.md`
(Wave 1 Plan B, Overbuilt #2). Backlog: VWS-6R4T (related REL-3M7K; the item's named
overlaps REL-9F2T, VWS-4D8J, VWS-7N3K are all already shipped/archived — nothing to fold).

## Requirements Confidence

**Level:** High

**Why:** Owner-accepted parent artifact names the failure class with evidence (~12 of 71
learnings, trenchant's entire lifespan); the code paths (`lib/views.py` tag parse/flip,
`bin/prawduct-hook` regen-views handler) are small, pure, and fully test-covered. A
pre-plan probe against the real change-log (124 entries, 38 scoped plans) confirmed:
no roster validation exists anywhere today; zero exact-match violations among
plan-resolvable entries (so the new validator lands green); 26 shipped-scope entries
have no plan file and are legitimately historical (the existing exemption is correct);
`regen-views --check` is referenced by two learnings but does not exist.

**Open assumptions / unknowns:**
- [ASSUMPTION: The parent's "consider shrinking the vocabulary (one scope identifier,
  statusless-until-release as the only lifecycle)" is **descoped** to its own backlog
  item rather than built here. Rationale: it deletes `status=merged` + `stamp-merged`
  machinery that shipped 3 weeks ago (v2.1.1) and works; the cascade touches the PR
  skill, release process doc, several learnings, and tests (the enumerate-the-surfaces
  rule says that is its own plan); and roster validation makes the existing vocabulary
  safe, removing the P0 urgency. Owner was asked 2026-07-02 (no response — AFK);
  recommendation applied. | HIGH impact | user can override]
- [ASSUMPTION: "Errors loudly on non-matches" means regen-views **fails closed**: on
  any validation error it prints ERROR lines and exits 2 *without writing any view*
  (no silent partial flips — partial application is the bug class). Error set: (a)
  `chunks=` ID not in the resolved plan's Status roster after normalization — for ANY
  entry whose `scope=` resolves to a plan file, shipped included, because release-prep
  flips entries to `shipped` *before* running regen-views, so a shipped-exempt
  validator would never fire at the moment it matters; (b) unrecognized `status=`
  value (promoted from warning — warnings are effectively blocking); (c) unreleased
  (statusless-tagged or merged) scope with no plan file (promoted from warning); (d)
  duplicate `scope:` across plan files (promoted — resolution is ambiguous); (e)
  conflicting scalar keys across multiple tag lines (the first-wins repair can pick
  the wrong value). Mere tag-line multiplicity without conflicts stays a warning (the
  union repair is correct output). Shipped scopes with NO plan file remain exempt
  (historical/retired plans). | MED impact | user can override]
- [ASSUMPTION: Tolerant matching = a `normalize_chunk_id()` applied uniformly to both
  sides of every comparison (the shipped-set flip in `collect_shipped_chunks` /
  `regenerate_status_section` AND the new validator): casefold; purely-numeric IDs
  compare by integer value (`1` ≡ `01`); `_` and `-` unify. Normalization must be
  proven collision-free against the real change-log before landing (probe shows
  numeric IDs and letter IDs A–E; no expected collisions). | MED impact | user can
  override]
- [ASSUMPTION: `regen-views --check` = compute + validate, write nothing. Exit 0 when
  validation passes (pending writes are normal at release time, reported not erred);
  exit 2 with ERROR lines on any validation failure. This makes the two existing
  learnings that already tell operators to "confirm via `regen-views --check`" true
  instead of stale. | LOW impact | user can override]
- [ASSUMPTION: REL-3M7K (root CHANGELOG.md headline + green-suite gate at release-prep)
  stays its own item — different mechanism (banner parse / release-prep process), not
  the tag DSL. Noted as related, not folded. | LOW impact | user can defer]

**What would raise confidence:** Owner's answer on the vocabulary-shrink descope
(assumption 1) — the plan proceeds on the recommendation either way.

## Status

- [ ] Chunk 01: Fail-loud tag validation — roster check, tolerant chunk IDs, `--check`
Context: Chunk 01 built 2026-07-02; suite 1529/0; live checks pass (--check clean on
HEAD, regen idempotent, scratch corruption errors loudly exit 2 nothing written,
chunks=1 vs Chunk 01 tolerant-validates). Checkbox flips at release via regen-views
(entry statusless on branch). Next: cumulative Critic, then /prawduct:pr when asked.

## Scaffolding

Existing repo — no scaffold. Tests: `pytest tests/test_views.py` (full suite before
commit).

### Verification Strategy

Beyond tests, run against this repo's real state (self-hosting caution — this edits
the machinery that will flip THIS plan's own Status at release):
1. `prawduct-hook regen-views --check` on HEAD exits 0 (the 124-entry change-log and
   38 scoped plans validate clean — matches the pre-plan probe).
2. `prawduct-hook regen-views` on HEAD is a no-op/idempotent (flip behavior unchanged
   by normalization on already-consistent data).
3. In a scratch copy: corrupt one entry's `chunks=` to a nonexistent ID → regen-views
   prints a loud ERROR naming the entry, the bad ID, and the plan's actual roster, and
   exits 2 with NO files written; `chunks=1` against a `Chunk 01:` roster flips
   correctly (tolerance proven live).

## Build Chunks

### Chunk 01: Fail-loud tag validation — roster check, tolerant chunk IDs, `--check`

- **Description:** Kill the silent-partial-flip class in the change-log→views DSL.
  Three moves:
  1. `lib/views.py` — add `normalize_chunk_id()` and apply it to both sides of every
     chunk-ID comparison (shipped set + Status-roster match), so zero-padding /
     case / separator variants stop being silent no-flips. Add
     `validate_chunk_roster(change_log_content, artifacts_dir)` (pure, mirrors the
     existing validators): for every entry whose `scope=` resolves to a plan file,
     every `chunks=` ID must match that plan's Status-section roster after
     normalization; returns one error string per miss naming entry title/line, the
     unmatched ID, and the plan's actual roster. Split
     `validate_tag_line_multiplicity`'s conflict case out as an error.
  2. `bin/prawduct-hook` `cmd_regen_views` — restructure the advisory block into a
     validate-then-apply sequence: run all validators BEFORE `apply_regen`; any
     ERROR-class finding prints loudly and exits 2 with nothing written (fail
     closed). Promotions per plan assumption (b)-(e); mere multiplicity stays
     WARNING. Add the `--check` flag: compute + validate + print planned actions,
     write nothing, exit 0 valid / 2 on violations. Update the usage string.
  3. `docs/release-process.md` — add `--check` to step 4 as the pre-flight
     ("run `regen-views --check` first; fix any ERROR before the real run"), and
     update the two stderr-WARNING sentences that the promotions make stale.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/framework-efficiency-review-2026-07-02.md`
- **Deliverables:** edits to `lib/views.py`, `bin/prawduct-hook`,
  `tests/test_views.py`, `tests/test_hook_regen_views.py` (or the existing hook-test
  home for regen-views), `docs/release-process.md`
- **Tests:**
  - Normalization: `1`≡`01`≡` 01`, `A`≡`a`, `foo_bar`≡`foo-bar`; non-numeric IDs
    unaffected by zero-strip; no collisions across the real change-log's ID corpus
    (regression: flips on the repo's own change-log are byte-identical pre/post).
  - Roster validator: miss on a resolvable scope → error naming entry/ID/roster;
    shipped scope with no plan file → no error (historical exemption); statusless
    and merged and shipped entries with resolvable plans all validated; tolerant
    match suppresses the former zero-padding false miss.
  - Fail-closed wiring: a roster miss makes regen-views exit 2 and write NO view
    files (plan Status, release-notes, scope_rollups all untouched); status-typo,
    unreleased-no-plan, duplicate-scope, scalar-conflict all exit 2; multiplicity
    alone still exits 0 with a WARNING.
  - `--check`: clean repo exits 0 and prints planned actions without writing;
    violation exits 2; never writes in either case.
- **Acceptance criteria:**
  - Full pytest suite passes.
  - Live checks per Verification Strategy (idempotent on HEAD, loud on scratch
    corruption, tolerance proven live).
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed and chunk marked `[x]` in Status
  3. `/prawduct:critic cumulative` run against `merge-base...HEAD`, blocking
     findings resolved — this IS the chunk's review and the `/prawduct:pr create` gate
  4. Backlog: VWS-6R4T updated via `/prawduct:backlog` (shrink-descope recorded on
     the item; new item filed for the vocabulary shrink; REL-3M7K noted related)

## Early Feedback Milestone

**Milestone chunk:** 01 (single-chunk plan)
**What the user can do:** Run `regen-views --check` before a release and get a loud,
named error for any tag that would silently fail to flip; write `chunks=1` against a
`Chunk 01:` plan and have it just work.

## Governance Checkpoints

**Commit & PR cadence:** Commit the chunk, then one `/prawduct:critic cumulative`
(the chunk review AND the PR gate), then `/prawduct:pr` per the wave rules (own
feature branch off develop, ships at next version bump). `active_build_plan` stays
pointed at the release-pending gate-noise plan until the release ships (gitflow plan
lifecycle); this plan is scope-resolved via its frontmatter.
