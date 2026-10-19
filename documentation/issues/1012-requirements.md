# Issue #1012 — Change-log: One Fragment File per Change: Requirements

`status: draft · stage: requirements · area: release · added: 2026-10-18 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/1012`

Related: #834 (derive the entry from the PR body — same cost, different mechanism; see Decision 5),
#857 (union-merge resurrection audit — fragments retire its change-log case), #783 / #303 (tag
conventions that change shape under frontmatter), #733 (consumer digest — same note surface).
Owner approved the fragment direction on 2026-10-17; this document settles the details discovery
was left.

## Problem

Every branch writes the same two shared files, and merge machinery plus review time goes into
getting those edits through:

- **`.prawduct/change-log.md`** — each branch prepends at the top. `.gitattributes` sets
  `merge=union` to avoid the conflict, and that driver duplicates relocated entries (#857: a
  develop sync brought back 396 archived entries with no conflict raised).
- **`plugin/CHANGELOG.md`** — each branch edits the rolling `## vX.Y.Z-dev.N` section, whose
  heading is renumbered on every merge.
- **Hand-written tags.** `scope=`, `release=` and `type=` ride in a `<!-- prawduct: … -->` HTML
  comment that nothing validates structurally. #834 measured 289 tag/scope/release-pairing and
  239 entry-missing findings among 4,321 review findings.

## Grounding facts

Checked against the tree on 2026-10-18:

- The live log is small (11 `##` entries, 265 lines); older entries are moved verbatim to
  `.prawduct/change-log-archive/YYYY-MM.md` by `change_log_archive.py`. The archive is already a
  directory of append-only files, so fragments are not a new storage idea.
- `change_log.py` owns the grammar: `CHANGE_LOG_REL_PATH`, `parse_change_log`, `parse_tag_line`,
  `validate_change_log_tags`, `RETIRED_TAG_KEYS`. `release_readiness.py` (`check_releasability`,
  `release_pending_entries`) enumerates release-pending scopes from the **absence** of `release=`.
- `release=unreleased` (any non-version value) hides a scope from the pending set; the validator
  already guards it. A fragment format must keep that guard.
- `.prawduct/` paths are non-judgeable (`coverage_algebra.is_judgeable_path`), so a fragment under
  `.prawduct/changes/` does not reopen cumulative review.
- Consumers touching the ledger (grep for `change-log.md` / `CHANGE_LOG_REL_PATH`): `init_product`,
  `migrate_plugin`, `onboarding_probes`, `oversized_state_probes`, `gitattributes_probes`,
  `record_lint`, `release_readiness`, `plan_backfill`, `lifecycle_repair`, `pr_payload`,
  `coverage*`, the pr / critic / doctor / janitor / migrate / onboard skills, the release runbooks
  and `documentation/release-process.md`. `banner.py parse_changelog` reads `plugin/CHANGELOG.md`
  only.
- The pr skill's Step 1c writes the entry after the last Critic review and Step 1d adds
  `release=` on a trunk base. Nothing may require a post-merge commit (Step 1d rule), so the
  fragment is written in the branch, never at merge.

## Requirements

**FRG1 — One file per change.** A branch records its change as one new file
`.prawduct/changes/<scope>.md`. The filename stem equals the `scope` value; two branches cannot
share a scope, so they cannot edit the same file. Editing a fragment after it merges (a reopen) is
an edit to that one file.

**FRG2 — Structured frontmatter, machine-validated.** The file opens with YAML frontmatter:

| key | required | rule |
|---|---|---|
| `type` | yes | one of the existing change types (`feature`, `bugfix`, `chore`, `docs`, `governance`, …; the set is the one `change_log.py` already accepts) |
| `scope` | yes | matches the filename stem and the governing build plan's `scope:` |
| `date` | yes | `YYYY-MM-DD` |
| `title` | yes | non-empty one-line headline |
| `release` | no | **absent until the cut**; when present, must be a version (`vX.Y.Z[.N][-suffix]`) — the `release=unreleased` guard carries over unchanged |
| `issues` | no | list of issue refs the change closes |

Unknown keys, a retired key (`chunks`, `status`), a wrong-typed value, or frontmatter that does
not parse are refused by `validate_change_log_tags`' successor with a named reason. Refusal is
mechanical at PR Step 1c, not a reviewer finding.

**FRG3 — Body sections.** The body is prose with two sections: the entry narrative (the existing
`**Why:** …` body, which must name every chunk shipped) and an optional `## Consumer note`
section: the user-facing text for `plugin/CHANGELOG.md`. A fragment with no Consumer note is
valid and contributes nothing to the public digest. A scope that ships user-visible behavior
without one is a `release_readiness` warning (it is today's "scope with no release note" finding,
now checkable).

**FRG4 — Release cut assembles; branches never touch shared files.** `prawduct-hook` gains a cut
command (name decided in design) that, for the fragments with no `release`:
1. stamps `release: vX.Y.Z` into each,
2. appends their narratives, newest first, into the archive month files (verbatim, as
   `change_log_archive.py` does today),
3. renders `plugin/CHANGELOG.md`'s `## vX.Y.Z` section from the Consumer notes, and
4. moves stamped fragments out of `.prawduct/changes/` (the directory then holds exactly the
   release-pending set — the same set `check-releasability` enumerates today).
Step 2 of this is the only writer of the archive and of `plugin/CHANGELOG.md`; no feature branch
edits either. The rolling `-dev.N` heading and its renumbering conflicts disappear.

**FRG5 — Merge safety without `merge=union`.** Two branches that each add a fragment merge with
no conflict on any change-record file. The `merge=union` line for `.prawduct/change-log.md` and
`probe_change_log_union_merge` are retired for repos that have migrated (FRG7); a repo that has
not migrated keeps both. A test merges two real branches and asserts a clean result.

**FRG6 — Readers read fragments.** `release_readiness` (`release_pending_entries`, classification
coverage, duplicate-scope and unclassifiable-pending checks), `record_lint`, `pr_payload`, the
Critic cross-checks and `plan_backfill` read the fragment set. The pairing check shrinks:
filename = scope removes duplicate and missing-scope entries by construction. Readers support
**both** shapes for one release (legacy single-file log plus fragments) so migration is not a
flag day.

**FRG7 — Consumer migration.** Every onboarded product carries the single-file ledger. Migration:
- New products: `init_product` scaffolds `.prawduct/changes/` and a template fragment; no
  `change-log.md` ledger.
- Existing repos: `/prawduct:migrate` and `/prawduct:doctor` convert **release-pending** entries
  (no `release=`) into fragments; shipped entries stay in the legacy log/archive untouched. The
  conversion is one commit, reversible by `git revert`, and idempotent.
- `doctor` reports a repo that has both shapes with pending entries in the legacy file.
- Tested on fixtures: empty log, pending-only, mixed pending/shipped, a `release=unreleased`
  entry (must be flagged, not silently converted), entry with two tag lines.

**FRG8 — Python only.** No external changelog tool (changie, towncrier). The implementation is
stdlib plus the repo's existing frontmatter reader.

## Decisions

1. **Consumer note is a section of the fragment, not a second file.** Two files per change would
   recreate the pairing defect class (scope present in one, absent in the other) one level down;
   one file makes the pairing structural. Cost: a fragment is edited once for two audiences, which
   is the point.
2. **Filename carries the scope.** Uniqueness is then enforced by the filesystem rather than by a
   duplicate-scope warning.
3. **Release-pending is "a file in `.prawduct/changes/` with no `release`".** Same semantics as
   today's absence rule, so `check-releasability`'s model does not change; only its reader does.
4. **Archive stays verbatim.** The cut renders fragments into the existing archive format so
   `change_log_archive.py` invariants and historical entries are untouched; no re-parse of
   history.
5. **#834 is complementary, not superseded.** Fragments remove shared-file conflicts and make
   tags structural; #834 removes hand-authoring of the narrative. After this lands, #834
   becomes "draft the fragment from the PR body at Create Step 5", which is simpler because the
   target is a single new file. Sequence: #1012 first. Note #834 is currently `stage:ready`;
   its design assumes the single-file log and needs a one-line rebase onto fragments.
6. **#857's change-log audit case is closed by this change** for migrated repos; the audit stays
   for any other union-merged record.

## Out of scope

Adopting an external tool; the release versioning policy; rewriting or re-parsing archived
history; changing `plugin/CHANGELOG.md`'s consumer-facing prose style; #733's product-declared
digest (shares the Consumer-note surface, but is a separate feature).

## Acceptance (maps to the issue's checklist)

- [ ] This document and the design that follows settle schema (FRG2), layout (FRG1) and the
      open question (Decision 1).
- [ ] Two-branch merge test: clean, no `merge=union` involved (FRG5).
- [ ] Cut command produces archive + `plugin/CHANGELOG.md` section and stamps `release` (FRG4).
- [ ] Malformed or missing `type`/`scope`/`title` is refused by a mechanical check (FRG2).
- [ ] `release_readiness` and Critic cross-checks read fragments (FRG6).
- [ ] Tested migration for onboarded repos (FRG7).

## Open for design

- Cut command name and whether it replaces runbook Phase 1 steps 2–3 wholesale.
- Exact `type` set (reconcile with the undocumented-in-template `type=` drift #834 noted).
- Whether dual-shape reader support has an expiry release.
- Trunk-base repos: the closing PR stamps `release` itself (pr skill Step 1d) — confirm the cut
  command and Step 1d share one stamping function.
- How a reopened (already-released) scope is recorded under FRG1 (new fragment with a suffixed
  scope vs. editing the archived entry), per #783.
