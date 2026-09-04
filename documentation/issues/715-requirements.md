# Issue #715 — Governance: Make the Artifacts Directory Root Configurable: Requirements

`status: draft · stage: requirements · area: governance · added: 2026-09-04 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/715`

## Problem

`.prawduct/artifacts/` is hardcoded across the plugin. A product's durable specifications
(architecture, data model, security model, API contract, build plans) are the product's own
long-lived documentation, but prawduct forces them into a dotdir named after the toolchain.
Consumers reasonably want them in a first-class, browsable directory (`docs/`, `docs/specs`) that
reads as theirs and survives a `.prawduct` strip for distribution. There is no config knob for it
today. Reported from a consumer repo (bl-eng-client-delivery): "`.prawduct` may be stripped for
distribution, and the durable artifacts are ours, not prawduct's."

## Grounding facts

Re-verified against the current tree (2026-09-04):

- **The two modules that do the riskiest work with the artifacts path are already
  parameterized on it — the gap is entirely at the call sites, not in the consumers.**
  `plan_index.py`'s scanning functions (`branch_claiming_plans`, `iter_scoped_plan_candidates`,
  `unreadable_candidates`, etc.) all take `artifacts_dir: Path` as an argument and never
  hardcode a literal. `plan_archive.py`'s `archive_destination` and `refusal_reason` do the same;
  `refusal_reason` (`plan_archive.py:373-389`) already resolves *both* the plan path and the
  artifacts dir with `.resolve()` before comparing with `is_relative_to()` — a containment guard
  hardened specifically because a lexical `..` comparison once let
  `archive-plan .prawduct/artifacts/../../README.md` escape the tree (the comment at
  `plan_archive.py:373-379` documents that incident). This guard is root-agnostic by
  construction: it contains a plan under *whatever* `artifacts_dir` it is given, so plugging a
  configured non-default root through it needs no new guard logic, only a correct value to pass
  in.
- **Six call sites in `bin/prawduct-hook` construct the path directly instead of going through a
  resolver:**
  - `prawduct-hook:1402` — `prawduct_dir / "artifacts" / "project-preferences.md"` (preferences
    staleness check).
  - `prawduct-hook:4264` — `project_dir / ".prawduct" / "artifacts"` (archive-plan dry-run/real
    path).
  - `prawduct-hook:4904` — `project_dir / ".prawduct" / "artifacts"` (coverage-scaffold).
  - `prawduct-hook:5421` — `plan_index.display_path(plan_path, prawduct_dir / "artifacts")`.
  - `prawduct-hook:5990` — `(prawduct_dir / "artifacts").glob("*.md")`.
  - `prawduct-hook:6054` — `artifacts_root = prawduct_dir / "artifacts"` (work-model corpus
    filter).
- **Two `lib/` modules hardcode the path at a level above the already-parameterized scanners:**
  - `lib/norm_index_scaffold.py:34` — `PREFERENCES_REL = ".prawduct/artifacts/project-preferences.md"`,
    a module-level constant read by the coverage-scaffold nudge.
  - `lib/init_product.py` — the artifacts path is hardcoded three times: the module docstring's
    scaffolded-file list (`:16-17`), the scaffold-file tuple entries `(".prawduct/artifacts/…",
    "…")` (`:55-56`), and `_SCAFFOLD_DIRS = (".prawduct", ".prawduct/artifacts",
    ".prawduct/.pr-reviews")` (`:59`). This is also the acceptance criterion "Onboarding
    (`init-product`) can set it" — onboarding currently has no path to scaffold anywhere else.
  - `lib/briefing.py:855` mentions `.prawduct/artifacts/` only inside a doc/log string (advisory
    text), not a path construction — no code change needed there, only wording if the string
    should describe the configured root (Requirement ARD-7).
- **`get_prawduct_dir(project_dir)` is the existing precedent for exactly this shape of
  resolver, and it is already duplicated on purpose across the bin/lib boundary.** It's defined
  identically in `bin/prawduct-hook:67-68` and `lib/gitstate.py:21-24`; the `lib/gitstate.py`
  docstring states the reason: "Local copy of the hook's bootstrap helper so this module stays
  self-contained (`lib` never imports from `bin/`)." `bin/prawduct-hook` itself calls through
  `_gitstate().get_prawduct_dir(project_dir)` at `:5643` rather than always using its own inline
  copy — i.e. the codebase already has a working pattern for "one canonical implementation in
  `lib/`, reached from `bin/` via the `lib` module," which a new `get_artifacts_dir` resolver
  should follow rather than inventing a third shape.
- **The config-value precedent this item should reuse is `backlog_service_repo`.** It is read
  with `core.read_str_yaml_key(prawduct_dir / "project-state.yaml", "backlog_service_repo")`
  (`briefing.py:933`) — presence, not truthiness, gates behavior. `read_str_yaml_key`
  (`lib/core.py:195-`) is a dependency-free scalar reader (no PyYAML) already used for exactly
  this "optional override in project-state.yaml" shape.
- **The documentation-shape precedent for a declared, never-inferred optional root is
  `build_plan_ref_root`** (`plugin/templates/project-state.yaml:232-251`): unset means "the repo
  root is the only root"; the comment states the fallback rule for an invalid value explicitly
  ("A value that escapes the repo, doesn't exist, or isn't a directory is ignored"). A new
  `artifacts_dir:` template entry should follow this documented shape rather than inventing new
  validation prose.
- **`active_build_plan`'s convention is the wrong analogy to copy.** Its value is documented as
  "a path relative to `.prawduct/`" (`project-state.yaml:222-224`). `artifacts_dir` must NOT
  inherit that convention silently — the whole point of this item is letting the root live
  *outside* `.prawduct/` (e.g. `docs/specs`), so the declared value must be interpreted relative
  to the **project root**, not `.prawduct/`.
- **The reported workaround (symlinking `.prawduct/artifacts` to `../docs/specs`) is already
  independently confirmed to work**, with two named caveats: a checkout with `core.symlinks=false`
  materializes the link as a broken text file, and per-file symlinks specifically fail for build
  plans because `archive-plan` resolves the plan path and refuses it as outside the artifacts dir
  it was told about — which is exactly the `plan_archive.py:373-389` guard above working as
  designed against a symlink it was never pointed at, not a bug the guard needs to accommodate.

## Decisions

**1. One resolver in `lib/`, reached by `bin/prawduct-hook` the same way `get_prawduct_dir`
already is.** A new function (e.g. `get_artifacts_dir(project_dir)`) is added to `lib/` (the
`get_prawduct_dir` neighborhood — `lib/gitstate.py` or `lib/core.py`, a design-stage call) and
`bin/prawduct-hook` calls it via the module rather than re-deriving the join inline. This
mirrors an already-working pattern in this codebase (Grounding facts) instead of introducing a
new one, and satisfies "a single shared resolver" without deciding upfront whether `bin/` also
needs its own duplicate copy — that duplication exists for `get_prawduct_dir` only because `lib/`
cannot depend on `bin/`, which is equally true here, so the same shape applies if a duplicate
turns out to be needed.

**2. `artifacts_dir:` is relative to the project root, not `.prawduct/`.** This is the opposite
convention from `active_build_plan`, chosen deliberately: the motivating use case is a root that
lives *outside* `.prawduct/` entirely (`docs/specs`), so keying off `.prawduct/` would make the
common case require `../docs/specs` — awkward and error-prone. The template comment must state
this contrast explicitly so an author doesn't assume the `active_build_plan` convention transfers.

**3. Default and fallback mirror `build_plan_ref_root`, not a new fail-closed path.** Unset/null →
`.prawduct/artifacts` (today's behavior; every existing repo is unaffected, matching the issue's
own proposed change). A declared value that doesn't resolve to an existing directory is reported
and ignored (falls back to the default), the same behavior `build_plan_ref_root` already
documents for its own invalid-value case — no new validation semantics are designed for this item.
Whether an existing directory must also exist *before* first use, or may be created lazily by
onboarding/scaffolding, is a design-stage question — the requirement is only that the resolver's
fallback-on-invalid behavior is consistent with the existing `build_plan_ref_root` precedent.

**4. The per-plan containment guard needs no new logic — only proof it composes with a
configured root.** `plan_archive.py`'s `resolve()` + `is_relative_to()` check (Grounding facts)
already takes `artifacts_dir` as a parameter and contains correctly against whatever it is
handed. This item's acceptance is that the guard is exercised — and verified — against a
configured root outside `.prawduct/`, not that new containment code is written.

**5. Onboarding writes the key only when the operator declares a non-default root.** A fresh
`init-product` run at the default keeps `project-state.yaml` free of the new key, preserving the
"every existing repo unaffected" guarantee end-to-end (default installs behave byte-for-byte as
before, not merely "the effective path is the same").

## Requirements

MUST unless marked SHOULD.

- **ARD-1** `artifacts_dir` is read from `.prawduct/project-state.yaml` via the existing
  `read_str_yaml_key` helper, defaulting to `.prawduct/artifacts` when absent or null (Decision 3,
  Grounding facts — `backlog_service_repo` precedent).
- **ARD-2** The declared value is resolved relative to the **project root**, never relative to
  `.prawduct/` (Decision 2) — the template comment states this contrast with
  `active_build_plan` explicitly.
- **ARD-3** One shared resolver function computes the effective artifacts directory; it is
  defined once in `lib/` and reached from `bin/prawduct-hook` through the module, following the
  existing `get_prawduct_dir` / `_gitstate()` pattern rather than a new ad hoc shape (Decision 1).
- **ARD-4** No remaining hardcoded `.prawduct/artifacts` or `prawduct_dir / "artifacts"`
  construction survives in `bin/prawduct-hook` (the six sites at `:1402`, `:4264`, `:4904`,
  `:5421`, `:5990`, `:6054`) or in `lib/` (`norm_index_scaffold.py:34`'s `PREFERENCES_REL`;
  `init_product.py`'s scaffold-file tuples and `_SCAFFOLD_DIRS` at `:55-56`, `:59`) — every one
  replaced with a call through the shared resolver.
- **ARD-5** Plan discovery (`plan_index.py` call sites), archive containment
  (`plan_archive.py` call sites), the coverage-scaffold and norm-index-scaffold paths, and
  critic dispatch's plan/artifact lookups all receive the resolver's output rather than a literal
  path — each of the call sites enumerated in ARD-4 is updated and each caller of
  `plan_index`/`plan_archive` functions is confirmed to pass the resolved value through (not just
  the sites that construct the literal today).
- **ARD-6** The existing per-plan containment guard (`plan_archive.py`'s `resolve()` +
  `is_relative_to()` check) is exercised against a configured root outside `.prawduct/` and
  confirmed to still refuse an out-of-tree plan path and still accept an in-tree one — a
  regression/behavioral test, not new guard code (Decision 4).
- **ARD-7** `methodology/planning.md`'s "Where Artifacts Live" section, and any doctor/janitor
  check wording that currently asserts the literal `.prawduct/artifacts` path, are reworded to
  describe "the configured artifacts root (default `.prawduct/artifacts`)" — including the
  `briefing.py:855` advisory string if it is user-facing guidance rather than an internal-only
  comment.
- **ARD-8** `init-product` accepts a declared root at onboarding time and, when it differs from
  the default: (a) scaffolds the template files (`project-preferences.md`,
  `boundary-patterns.md`, etc.) under that root instead of `.prawduct/artifacts`, and (b) appends
  `artifacts_dir: <path>` to the newly created `project-state.yaml`, mirroring
  `_append_backlog_service_repo`'s append-when-absent shape (`init_product.py:86-96`) (Decision
  5).
- **ARD-9** A default (unset-key) onboarding run writes no `artifacts_dir` line at all — not an
  explicit line holding the default value — so an untouched `project-state.yaml` is
  byte-for-byte what it is today (Decision 5).
- **ARD-10 (SHOULD)** The `plugin/templates/project-state.yaml` comment block for `artifacts_dir:`
  follows the documentation shape already established for `build_plan_ref_root` (declared, never
  inferred; explicit fallback-on-invalid rule stated) rather than a new prose convention
  (Grounding facts).

## Acceptance

- [ ] `artifacts_dir:` read from `project-state.yaml`, defaulting to `.prawduct/artifacts`, and
      interpreted relative to the project root (not `.prawduct/`).
- [ ] A single shared resolver; zero remaining hardcoded `.prawduct/artifacts` constructions in
      `bin/` (6 sites) or `lib/` (`norm_index_scaffold.py`, `init_product.py`).
- [ ] Plan discovery, coverage checks, norm-index scaffold, archive containment, and critic
      dispatch all honour the resolver's output.
- [ ] The existing plan-containment guard is proven (by test) to hold against a configured root
      outside `.prawduct/` — no new guard logic required, only verification.
- [ ] `methodology/planning.md` § Where Artifacts Live and the doctor/janitor wording describe the
      configured root, not a literal path.
- [ ] `init-product` can set a non-default root at onboarding; a default-root run leaves
      `project-state.yaml` unchanged from today's shape.

## Scope-out (this item)

- Migrating existing repos' artifacts automatically — the knob plus documentation is enough;
  moving files is the operator's act (issue's own scope-out).
- Per-artifact path overrides — one root, not a map (issue's own scope-out).
- New validation semantics for an invalid `artifacts_dir` value beyond mirroring
  `build_plan_ref_root`'s existing "ignored, falls back" behavior (Decision 3) — a stricter or
  fail-closed policy is a separate decision if evidence later shows the lenient fallback causes
  silent misconfiguration.
- New containment-guard code — `plan_archive.py`'s guard is already root-agnostic; this item
  verifies it, it does not rewrite it (Decision 4).
- Deciding the exact `lib/` module (`gitstate.py` vs. `core.py` vs. a new module) the resolver
  lives in, and whether `bin/prawduct-hook` needs its own duplicate copy the way
  `get_prawduct_dir` does — both are design-stage calls once the actual import graph is checked
  (Decision 1).

## Evidence / references

- `plugin/lib/plan_index.py` — scanning functions already take `artifacts_dir: Path`; no literal
  path construction found in this module.
- `plugin/lib/plan_archive.py:329-343` — `archive_destination`, parameterized on `artifacts_dir`.
- `plugin/lib/plan_archive.py:345-393`, esp. `:373-389` — `refusal_reason`'s `.resolve()` +
  `is_relative_to()` containment guard and the documented incident (a lexical `..` bypass) that
  hardened it.
- `plugin/bin/prawduct-hook:1402,4264,4904,5421,5990,6054` — the six hardcoded call sites.
- `plugin/lib/norm_index_scaffold.py:34` — `PREFERENCES_REL` module-level constant.
- `plugin/lib/init_product.py:16-17,55-56,59,86-96` — onboarding's hardcoded scaffold paths and
  the `_append_backlog_service_repo`-shaped precedent for appending a config key when absent.
- `plugin/lib/briefing.py:855,917-936` — the doc-string-only mention, and the
  `backlog_service_repo` / `read_str_yaml_key` config-read precedent (`:933`).
- `plugin/bin/prawduct-hook:67-68`, `plugin/lib/gitstate.py:21-24`, `plugin/bin/prawduct-hook:5643`
  — the `get_prawduct_dir` dual-definition precedent and its `_gitstate()`-mediated call path.
- `plugin/lib/core.py:195-` — `read_str_yaml_key`.
- `plugin/templates/project-state.yaml:222-251` — the `active_build_plan` (relative-to-`.prawduct/`)
  and `build_plan_ref_root` (declared-never-inferred, explicit invalid-value fallback)
  documentation precedents.
- Issue #715 — problem statement, consumer report, current workaround and its two caveats,
  proposed change, and acceptance criteria this document grounds.
