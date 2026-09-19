# Issue #834 — Governance: Derive the Change-Log Entry at Merge, Not by Hand: Requirements

`status: draft · stage: requirements · area: governance · added: 2026-09-19 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/834`

Related: #830 (severity → channel), #831 (mechanical fix/accept + round-cost surfacing), #833
(bound over-fixing rules), #724 (the 27-round report), #829, #832 — the same governance-ledger scan
this item's sibling program comes from. None of #829–#833 has a `documentation/issues/` doc yet
(checked directly); this item does not depend on any of them shipping first, but a design pass
should stay aware `scope=` is also the join key #830/#831 read off the same ledger.

## Problem

**1,113 of 4,321 findings (25.8%) mention the change log**, across 886 commits touching it: 289
tag/scope/release-pairing, 239 entry missing, 217 body/narrative coverage, 368 other. The entry is
hand-authored today, checked only for *presence* at PR-create time, and every tag/scope defect is a
transcription error a human made copying data the repository already has elsewhere (the PR's own
narrative, the branch's own governing scope, the issues the work closes). The owner asked whether
the change log is positive ROI at all; the proposed answer is to keep the artifact — the narrative
is what release notes are for, and `check-releasability` plus the scope→plan join depend on the
`scope=`/`release=` tags surviving — but stop hand-deriving data from sources the repo already
holds.

## Grounding facts

Re-verified against the current tree (2026-09-19):

- **Two distinct change-log files exist, and this item targets the product-facing one.**
  `.prawduct/change-log.md` (`CHANGE_LOG_REL_PATH = ".prawduct/change-log.md"`,
  `plugin/lib/change_log.py:54`) is this framework's own governed-product log. `plugin/CHANGELOG.md`
  is the separate, hand-synced *consumer-facing* digest shipped inside the plugin
  (`plugin/CHANGELOG.md:1-11`, "never lands in a consuming repo's tree... the release process keeps
  the two in sync"). `plugin/templates/change-log.md` is the template every onboarded product gets —
  this item changes how that file is populated, not the plugin's own digest.
- **The entry grammar is two machine-read tag keys only.** Per the template's own doc comment
  (`plugin/templates/change-log.md:14-28`): a `## YYYY-MM-DD: title` header, a
  `<!-- prawduct: scope=... | release=... -->` tag line, then free prose. `scope` is a rollup id
  matching a build plan's `scope:` frontmatter; `release`'s **absence** is what marks an entry
  release-pending — any value at all, including a placeholder, silently unships the scope
  (template `:23-28`; the exact failure `validate_change_log_tags` now guards against,
  `plugin/lib/change_log.py:272-297`, citing a real incident where `release=unreleased` hid a whole
  branch from v3.2.8). `chunks=`/`status=` are retired and read as inert (template `:30-34`). A real
  entry in this repo's own log (`.prawduct/change-log.md:115-117`) additionally carries a `type=`
  key the template does not document — an existing drift between documented and actual grammar,
  worth resolving (not necessarily by this item) rather than compounding.
- **`check-releasability` reads only the tag line, never the body.**
  `plugin/lib/release_readiness.py:754` (`check_releasability`): reads `.prawduct/change-log.md`,
  fails closed if unreadable (`:761-766`) or a tag is malformed (`:778-786`, delegating to
  `validate_change_log_tags`); computes `release_pending_entries` as tagged entries with no
  `release=` (`:101-119`); an entry with a `scope=`-less pending tag is a **hard failure**
  (`unclassifiable-pending-entry`, `:122-135, 812-828`) — exactly the "tag/scope-pairing" defect
  class the issue's 289-count names. Every pending `scope=` must then appear in the release-plan
  artifact's `## Release classification` table as `ships` or `withheld` with a live backlog id
  (`:163-225, 213-221`); duplicate-scope and missing-build-plan checks are warnings only
  (`_duplicate_scope_warnings` `:362-380`, `_plan_coverage_warnings` `:383-410`). This gate is fully
  mechanical against `scope=`/`release=` — a derived entry only has to get the tag line right to
  satisfy it, which is exactly the 12%-of-findings elimination the issue claims.
- **"Scope→plan pairing" is the existing join `scope=` must keep serving.** The tag's `scope=`
  value is the shared key across build-plan frontmatter `scope:`, the change-log tag, and the
  release-classification table rows, resolved via `plugin/lib/buildplan_refs.py`
  (`resolve_branch_plan`, `_scope_plan_map`) and `plugin/lib/plan_index.py`
  (`build_scope_to_plan_map`, `duplicate_scope_errors`). This is machinery that already resolves
  "which plan governs this branch" — the authoritative source for `scope=`, not free-text parsing
  of a commit message.
- **A presence-only gate exists today at PR-create time, before any merge.**
  `plugin/lib/coverage.py:1020-1165` (`check-change-log-entry`, dispatched at
  `plugin/skills/pr/SKILL.md:69-76` Step 1c): a judgeable diff must add a new `## ` header to
  `.prawduct/change-log.md` relative to the merge base, or the PR is refused (`no-entry`,
  `entry-edited-not-added`, `no-base`, `git-failed`, `:1049-1054`). It checks presence of a new
  section only — never content, never the tag line. **This gate runs before the merge this item's
  derivation happens at**, so the two are in direct tension unless reconciled (see Decisions).
- **`Closes #N` is inert on this repo's own branch model.** Feature branches merge to `develop`,
  not the repository's default branch (`main`) — GitHub only fires closing keywords on a merge to
  the *default* branch. This is explicitly documented three times as a known limitation
  (`plugin/skills/pr/SKILL.md:84, :207, :227`; `plugin/skills/pr/review-protocol.md:192`). Issue
  linkage today is a **separate, manual** step: `/prawduct:backlog update <id> status=shipped
  closed-by=<scope>` (`SKILL.md:82-86`), and that call's *timing* is backend-dependent — atomic with
  the merge on the Markdown backend (a file edit riding the branch), but not necessarily atomic on
  the Issues backend, which this repository now runs on (per this session's own task: "use the
  GitHub issues backend"). Any derivation of "closed issues" at merge must go through this same
  backend-aware call or its underlying resolution, not through GitHub's own inert keyword mechanism.
- **The PR body is hand-drafted, with no machine draft supplied.** `plugin/skills/pr/SKILL.md`
  Step 5 (`:~207`) has the author write the description from "work context and the review's findings
  summary — the reviewer supplies no draft." This is the only point in the current flow where a
  human writes free prose about the change — the narrative source this item must read from, since
  no other artifact carries it.
- **The closest existing precedent for "read commits + change-log + backlog ids in one
  deterministic pass" is `pr-review-payload`, and it *consumes* an already-authored entry rather
  than deriving one.** Per this framework's own 2026-09-18 change-log entry
  (`.prawduct/change-log.md:115-170`), `prawduct-hook pr-review-payload` assembles base, commits,
  diffstat, work description, test-status, build-plan Status boxes, the change-log entry, and every
  backlog id the commits or that entry cite — already resolved. It reads the entry; it does not
  write one. This is the nearest existing pattern to model a derivation step on, not a mechanism to
  route around.
- **No GitHub Actions workflow touches PR bodies, merges, or issues.**
  `.github/workflows/` holds only `tests.yml` (push/PR) and `verify-release.yml` (tag push, and by
  its own header comment "never publishes" — verifies a cut release's artifacts only). PR
  creation/merge is entirely `gh` CLI inside `/prawduct:pr` (`SKILL.md:6` allowed-tools:
  `Bash(gh pr *)`, `Bash(gh repo view *)`, `Bash(gh issue view *)`; merge is `gh pr merge --merge`,
  `:226`) — no `mcp__github__*` tool grants, no Action trigger. There is currently no hook point that
  fires *at* merge at all; "derive at merge" is new wiring, not a rename of an existing step.
- **No `release-tooling`/`release_verification` module exists under that name.** Searched
  `plugin/lib/release*` (only `release_readiness.py`) and grepped both terms repo-wide: not found.
  Issues #575/#578 (cited in some sibling discussions as "release-tooling") have no
  `documentation/issues/` doc to cross-check against.

## Decisions

**1. Derivation happens at merge, and supersedes the pre-merge presence gate for products that
adopt it — it does not run alongside it as a second, contradictory check.** `check-change-log-entry`
(`coverage.py:1020-1165`) exists to catch a PR with no entry *before* merge; once the entry is
generated *at* merge, requiring one to already exist beforehand is either redundant or actively
wrong (it would block every PR under this scheme). This item's acceptance is "derived without
hand-authoring," so the PR-create-time gate must be told the entry is expected to be absent (or must
stop firing) for a product that has turned derivation on. The exact mechanism (a project-preference
flag the gate reads, or the gate retired once merge-time derivation is universal) is a design
question; the requirement here is only that the two checks must not both be live and disagree.

**2. `scope=` is derived through the existing scope→plan resolution machinery, not by parsing the
merge commit as free text.** The issue's own phrasing ("the merge commit... carries the scope") is
the *informal* framing; the *authoritative* source already resolved by `buildplan_refs.py` /
`plan_index.py` is the build plan governing the branch. Deriving `scope=` from that resolution
(rather than re-deriving it from commit-message text with a second, parallel parser) keeps exactly
one source of truth for the join key `check-releasability` and the classification table already
depend on.

**3. `release=` is never written by this derivation.** Per the template's own contract, absence of
`release=` is what marks an entry release-pending, and stamping any value at merge time would
silently unship the scope before a release actually cuts it (the exact v3.2.8 incident
`validate_change_log_tags`'s own docstring cites). This item derives the entry in its
release-pending state; the existing, separate release-cut mechanism stamps `release=` later. This
item does not touch that mechanism.

**4. Issue linkage is derived from the same backlog-id resolution `pr-review-payload` already
performs (ids cited by commits and by the entry), routed through the backend-aware
`/prawduct:backlog update ... closed-by=<scope>` call — never through GitHub's `Closes #N`
keyword.** The keyword is inert on this repo's own branch model (Grounding facts), so building on it
would silently fail exactly where this item is meant to help. Reusing the existing resolution logic
means this item adds no second way of discovering which issues a change closes.

**5. The narrative body is lifted from the PR's own description, verbatim or near-verbatim — this
item does not invent a second place to write prose.** The PR body is already the only point in the
flow where a human writes free text about the change (Grounding facts); requiring a *second*,
separately-worded narrative in the change-log entry would reintroduce hand-authoring by another
name. Exact extraction rules (whether the whole body is used, or a specific section within it) are a
design question, not a requirements one — but the source is fixed here.

**6. This item does not replace the change log with bare issue links.** Restated from the issue's
own Scope-out: the narrative is the half of the artifact that pays, and it survives unchanged in
kind — only its authorship moves from human transcription to machine assembly of data the human
already wrote (the PR body) or already declared (the branch's governing scope, the closed issues).

## Requirements

MUST unless marked SHOULD.

- **CLG1** At merge, a change-log entry is appended to `.prawduct/change-log.md` (or the equivalent
  product path) with no hand-authoring step required from the PR author beyond writing the PR
  description that already exists in the current flow.
- **CLG2** The derived entry's tag line carries `scope=` resolved via the existing scope→plan
  machinery (`buildplan_refs.py`/`plan_index.py`, Decision 2), matching the `scope:` frontmatter of
  the build plan governing the merged branch.
- **CLG3** The derived entry's tag line MUST NOT carry `release=` — the entry is created in the
  release-pending state (Decision 3); a separate, already-existing mechanism stamps `release=` at
  release-cut time, unmodified by this item.
- **CLG4** The derived entry's body carries the narrative from the PR's own description
  (Decision 5) — the author is not asked to write the change twice in two different formats.
- **CLG5** Issues the change closes are linked in the derived entry using the same resolution
  `pr-review-payload` already performs over commits and the entry (Decision 4), routed through the
  existing backend-aware `/prawduct:backlog update ... closed-by=<scope>` call — never through
  GitHub's `Closes #N` keyword, which is inert on this repo's branch model.
- **CLG6** `check-releasability` (`release_readiness.py:754`) passes unmodified against derived
  entries — this item changes how the tag line and body are produced, not what the gate reads or how
  it validates `scope=`/`release=`.
- **CLG7** The scope→plan join (`_duplicate_scope_warnings`, `_plan_coverage_warnings`,
  `build_scope_to_plan_map`) continues to resolve correctly against derived entries — a derived
  `scope=` must be indistinguishable, to every existing reader, from a hand-authored one.
- **CLG8** The pre-merge presence gate (`check-change-log-entry`, `coverage.py:1020-1165`) does not
  end up in permanent disagreement with merge-time derivation for a product that has adopted it —
  either it is told to expect no pre-merge entry, or it is retired for that product. (Design decides
  which; Decision 1 fixes only that both cannot silently coexist unreconciled.)
- **CLG9 (SHOULD)** The derived tag grammar does not introduce a third recognized key beyond
  `scope=`/`release=` without also updating `plugin/templates/change-log.md`'s doc comment — the
  existing undocumented `type=` drift (Grounding facts) is not a precedent to extend casually.

## Acceptance

- [ ] A PR merged through the normal flow produces a change-log entry with no hand-authored tag line
      or hand-transcribed issue links, per CLG1/CLG2/CLG5.
- [ ] The derived entry's `scope=` matches the governing build plan's frontmatter and contains no
      `release=`, per CLG2/CLG3.
- [ ] `check-releasability` and the scope→plan warnings pass on a derived entry exactly as they do
      on a hand-authored one, per CLG6/CLG7.
- [ ] The pre-merge presence gate and merge-time derivation do not both fire in contradiction on the
      same PR, per CLG8.
- [ ] Issue links in the derived entry resolve correctly on the Issues backlog backend, not only the
      Markdown one, given CLG5's backend-aware routing.

## Scope-out (this item)

- Replacing the change log with bare links to closed issues — explicitly considered and rejected by
  the source issue; the narrative is what makes the artifact worth having.
- Stamping `release=` at merge, or any change to the release-cut mechanism that stamps it today
  (Decision 3) — that mechanism is untouched.
- Making GitHub's `Closes #N` keyword functional on this repo's branch model (e.g., by changing the
  default branch or the gitflow shape) — out of scope; this item routes around the limitation rather
  than removing it.
- Resolving the undocumented `type=` tag-key drift (Grounding facts) — noted for awareness (CLG9),
  not required to close this item.
- The exact extraction rule for how much of the PR body becomes the entry body, the exact wording of
  the derived header, and whether/how the pre-merge presence gate is retired vs. reconciled
  (Decision 1 / CLG8) — design-stage.
- Any change to `plugin/CHANGELOG.md`, the separate consumer-facing digest — this item concerns the
  per-product `.prawduct/change-log.md` mechanism template-shipped to onboarded repos.

## Evidence / references

- `plugin/lib/change_log.py:54` (`CHANGE_LOG_REL_PATH`), `:272-297` (`validate_change_log_tags`,
  including the documented `release=unreleased` / v3.2.8 incident this item's Decision 3 avoids
  repeating).
- `plugin/templates/change-log.md:1-35` — the full entry-grammar doc comment: recognized keys,
  retired keys, the `scope=`/`release=` contract.
- `.prawduct/change-log.md:115-170` — a real entry, including the undocumented `type=` key (Grounding
  facts) and the `pr-review-payload` description this item's Decision 4/5 model derivation on.
- `plugin/lib/release_readiness.py:754-870` (`check_releasability`), `:101-135`
  (`release_pending_entries`, `unclassifiable_pending_entries`), `:163-225`
  (`parse_classification`), `:362-410` (`_duplicate_scope_warnings`, `_plan_coverage_warnings`).
- `plugin/lib/buildplan_refs.py` (`resolve_branch_plan`, `_scope_plan_map`) and
  `plugin/lib/plan_index.py` (`build_scope_to_plan_map`, `duplicate_scope_errors`) — the scope→plan
  join this item's derived `scope=` must keep serving (Decision 2).
- `plugin/lib/coverage.py:1020-1165` — `check-change-log-entry`, the pre-merge presence gate this
  item must reconcile with (Decision 1 / CLG8).
- `plugin/skills/pr/SKILL.md:6, :69-76, :82-86, :207, :226-227` — allowed-tools (no MCP GitHub
  grants), the Step 1c presence gate, the backend-aware backlog-close call and its timing note, PR
  description authorship, and the merge strategy.
- `plugin/skills/pr/review-protocol.md:192` — corroborating note that `Closes #N` is inert on this
  repo's branch model.
- `.github/workflows/tests.yml`, `.github/workflows/verify-release.yml` — confirms no existing
  workflow reads PR bodies, merges, or issues.
- GitHub issue #834 — problem statement, proposed change, and acceptance criteria this document
  grounds.
