# Issue #715 — Governance: Make the Artifacts Directory Root Configurable: Requirements

`status: draft · stage: requirements · area: governance · added: 2026-08-25 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/715`

## Problem

`.prawduct/artifacts/` is hardcoded across the plugin. A product's durable specifications —
architecture, data model, security model, API contract — are the product's own long-lived
documentation, but prawduct forces them to live inside a dotdir named after the toolchain.
Reported from a consumer repo (bl-eng-client-delivery): "`.prawduct` may be stripped for
distribution, and the durable artifacts are ours, not prawduct's." There is no knob —
`project-state.yaml` carries `backlog_service_repo` and `active_build_plan`, but nothing names
where the artifacts subtree itself lives. The documented workaround (symlinking
`.prawduct/artifacts` to a real directory elsewhere) works but breaks on `core.symlinks=false`
checkouts and cannot cover per-file build-plan paths at all, because `archive-plan` resolves the
plan outside the artifacts dir and refuses (issue body, "Current workaround").

## Grounding facts

Re-verified against the current tree (2026-08-25):

- **No single resolver exists today — every reader constructs the path itself, in one of three
  shapes.** `plugin/lib/core.py:305` (`_branch_claimed_plan`): `artifacts_dir = prawduct_dir /
  "artifacts"`. `plugin/bin/prawduct-hook:1402`: `prefs_path = prawduct_dir / "artifacts" /
  "project-preferences.md"`. `plugin/bin/prawduct-hook:4264` and `:4904`: `artifacts_dir =
  project_dir / ".prawduct" / "artifacts"` — built straight from `project_dir`, bypassing even the
  existing `get_prawduct_dir` helper, so a future `.prawduct/`-only override would not reach these
  two sites either. `plugin/lib/norm_index_scaffold.py:34`: `PREFERENCES_REL =
  ".prawduct/artifacts/project-preferences.md"` — a fully literal repo-relative string, not built
  from any resolver at all. Further construction sites: `plugin/bin/prawduct-hook:5421` (plan
  display-path base), `:5990` and `:6054` (learnings/ratification corpus gathering).
- **The existing convention for a cross-module resolver is a small helper duplicated per module,
  not a single shared import.** `get_prawduct_dir(project_dir)`
  (`plugin/lib/gitstate.py:21-24`) is two lines returning `project_dir / ".prawduct"`, and its
  docstring says why it is copied rather than imported: "local copy of the hook's bootstrap helper
  so this module stays self-contained (lib never imports from bin/)." Any new `artifacts_dir`
  resolver inherits the same lib/bin import-direction constraint and should follow the same
  duplicated-helper shape rather than invent a new sharing mechanism.
- **The closest existing precedent for "an optional `project-state.yaml` key, defaulting, read via
  `read_str_yaml_key`" is `active_build_plan`, and it also documents the exact directional pitfall
  this design must not repeat.** `core.py:178-179`: `BUILD_PLAN_POINTER_KEY = "active_build_plan"`
  / `DEFAULT_BUILD_PLAN_REL = "artifacts/build-plan.md"`; `resolve_build_plan_path`
  (`core.py:328-361`) reads the pointer via `read_str_yaml_key(prawduct_dir /
  "project-state.yaml", BUILD_PLAN_POINTER_KEY)`, relative to `.prawduct/`, and falls back to the
  default when unset. Its docstring records a shipped incident: the pointer is `.prawduct/`-relative,
  but "the natural repo-relative spelling (`.prawduct/artifacts/x-plan.md`) is accepted by
  stripping the prefix — that spelling once shipped and silently disabled the gates for a work
  cycle (STH-5P2W)." That incident is direct evidence that a relative-path key with an ambiguous
  base is a defect this codebase has already paid for once.
- **`read_str_yaml_key`** (`core.py:195-`) already fails soft to `None` on a missing key, an empty
  value, or the literal YAML null (`null`/`~`) — the exact contract `artifacts_dir:` needs so an
  unset key reads identically to a repo that predates the feature.
- **The containment guard this item must reuse, not reinvent, already exists and already
  documents why a naive version failed.** `plan_archive.refusal_reason`
  (`plugin/lib/plan_archive.py:345-389`) resolves *both* `plan_path` and `artifacts_dir` via
  `.resolve()` before calling `is_relative_to` (`:380-385`), with the comment explaining that the
  first cut compared paths lexically and `archive-plan .prawduct/artifacts/../../README.md`
  "wrote the stamped copy outside the tree and unlinked the original — at exit 0." Any
  configured root outside `.prawduct/` must be checked through this same resolve-both-sides
  pattern, not a new one.
- **`project-state.yaml` itself is not proposed to move.** It is always read at `prawduct_dir /
  "project-state.yaml"` (`core.py:360`, and every `get_prawduct_dir(project_dir) /
  "project-state.yaml"` call site in `prawduct-hook`) — only the artifacts subtree becomes
  relocatable; the state file that names where it lives stays under `.prawduct/`.
- **The prose surface is much larger than the ~44 Python references the issue counted.** `grep`
  across `plugin/skills/` and `plugin/methodology/` for `.prawduct/artifacts` / `"artifacts"`
  turns up 27 markdown files, including doctor Health Checks #5, #8, #10, #11, #14, #15
  (`plugin/skills/doctor/SKILL.md`) and janitor's Template Currency, Stale-plan, and Norm-Health
  themes (`plugin/skills/janitor/SKILL.md`), each naming the literal `.prawduct/artifacts` path in
  its check text — not just code paths that need a resolver call, but check *descriptions* readers
  act on.
- **Onboarding scaffolds the directory and its contents by a literal tuple, not through any
  resolver.** `plugin/lib/init_product.py:59`: `_SCAFFOLD_DIRS = (".prawduct",
  ".prawduct/artifacts", ".prawduct/.pr-reviews")`; `:55-56` list the two seeded template
  destinations as literal `.prawduct/artifacts/...` strings.
- **No implementation exists today.** No `project-state.yaml` key named `artifacts_dir` exists in
  any template, and no `prawduct-hook` or `lib/` function resolves one — this is greenfield wiring
  onto the `active_build_plan` / `get_prawduct_dir` precedents, not a rework of an existing
  resolver.

## Decisions

**1. `artifacts_dir:` is interpreted relative to the project root, not `.prawduct/`.** The
`active_build_plan` pointer is `.prawduct/`-relative because a build plan legitimately lives
*inside* the artifacts tree it points into. `artifacts_dir` is the opposite case by construction —
the entire premise of the issue is a consumer who wants the artifacts tree to live *outside*
`.prawduct/` entirely (`docs/`, `docs/specs/`). A `.prawduct/`-relative interpretation would force
every such value to start with `../`, which is exactly the lexical-traversal shape the
`plan_archive` containment guard exists to be suspicious of (Grounding facts). Project-root-relative
lets `artifacts_dir: docs/specs` say what it means directly, and the STH-5P2W incident
(Grounding facts) is the standing argument against also accepting a second, ambiguous spelling the
way the build-plan pointer does — this key supports exactly one base, not two.

**2. The resolver is a duplicated small helper, one per module, mirroring `get_prawduct_dir`.**
Consistent with the existing convention (Grounding facts) and the `lib` cannot import `bin`
constraint it exists to respect. It signature-matches `get_prawduct_dir`: `get_artifacts_dir(project_dir:
Path) -> Path`, reading `artifacts_dir:` from `project_dir / ".prawduct" / "project-state.yaml"`
(via `read_str_yaml_key`) and defaulting to `project_dir / ".prawduct" / "artifacts"` when unset,
empty, or YAML null.

**3. Every hand-built artifacts path in `plugin/bin` and `plugin/lib` is replaced by a call
through the resolver, including the two sites that do not currently go through
`get_prawduct_dir` at all** (`prawduct-hook:4264`, `:4904`, built from `project_dir` directly) and
the one fully-literal string (`norm_index_scaffold.py:34`). A partial migration — some sites
resolver-driven, some still literal — reintroduces exactly the split-source-of-truth failure mode
the issue exists to close, silently, for whichever sites are missed.

**4. Containment/traversal guards are re-verified against the existing `resolve()`-both-sides
pattern, not rewritten.** `plan_archive.refusal_reason` already resolves both sides before
comparing; the design pass's job is confirming that pattern holds unchanged when `artifacts_dir`
points outside `.prawduct/`, not designing a new guard.

**5. Onboarding (`init-product`) accepts the value at scaffold time**, writing `artifacts_dir:`
into the generated `project-state.yaml` when given a non-default root, and building
`_SCAFFOLD_DIRS` / template destinations from the resolver rather than the current literal tuple —
so a new repo can choose its root once, at creation, instead of only reconfiguring after onboarding.

**6. Prose (methodology + doctor/janitor check text) is updated to describe "the configured
artifacts root," not re-audited artifact-by-artifact in this document.** The Grounding facts
above establish the surface is large (27 files); enumerating every line to edit is a design-pass
deliverable — this document fixes the standard those edits must meet (ART-7) rather than the
list itself.

## Requirements

MUST unless marked SHOULD.

- **ART-1** `project-state.yaml` gains an optional `artifacts_dir:` scalar. Absent, empty, or the
  YAML null literal (`null`/`~`) resolves to the current default `.prawduct/artifacts` —
  every existing repo's behavior is unchanged (Decision 2).
- **ART-2** `artifacts_dir:`, when set, is interpreted relative to the **project root** (Decision
  1) — never relative to `.prawduct/`, and no second accepted spelling is introduced.
- **ART-3** A resolver function (`get_artifacts_dir(project_dir)` or equivalent), duplicated per
  module needing it in the shape of `get_prawduct_dir` (Decision 2), is the sole place that reads
  `artifacts_dir:` and computes the default fallback.
- **ART-4** No remaining call site in `plugin/bin/` or `plugin/lib/` constructs an artifacts path
  by hand — every site named in Grounding facts (`core.py:305`, `prawduct-hook:1402,4264,4904,
  5421,5990,6054`, `norm_index_scaffold.py:34`) is replaced by a call through the resolver
  (Decision 3).
- **ART-5** Path-traversal / containment guards (`plan_archive.refusal_reason`'s
  resolve-both-sides comparison) hold, re-verified by test, against a configured root outside
  `.prawduct/` — a plan path escaping the *configured* root via `..` is refused exactly as it is
  today against the default root (Decision 4).
- **ART-6** `init-product` can set `artifacts_dir:` at scaffold time and builds its scaffold
  directory list and template destinations from the resolver, not the current literal
  `_SCAFFOLD_DIRS` tuple (Decision 5).
- **ART-7** `methodology/planning.md` § Where Artifacts Live, and each doctor/janitor
  check description naming the literal `.prawduct/artifacts` path in its check text (Grounding
  facts: doctor Health Checks #5, #8, #10, #11, #14, #15; janitor's Template Currency, Stale-plan,
  and Norm-Health themes), describe "the configured artifacts root" rather than the literal
  default path (Decision 6). The design pass enumerates the exact edit list.
- **ART-8 (SHOULD)** Doctor detects the documented symlink workaround (`.prawduct/artifacts`
  present as a symlink) once the native key ships, and suggests migrating to `artifacts_dir:`
  rather than leaving both mechanisms to coexist indefinitely with no cross-check between them.

## Acceptance

- [ ] `artifacts_dir:` read from `project-state.yaml`, defaulting to `.prawduct/artifacts`, and
      interpreted relative to the project root when set.
- [ ] A single shared resolver pattern (one small function per module, mirroring
      `get_prawduct_dir`); no remaining hardcoded `.prawduct/artifacts` or
      `project_dir / ".prawduct" / "artifacts"` constructions in `bin/` or `lib/`.
- [ ] Plan discovery, coverage checks, norm-index scaffold, archive containment, and critic
      dispatch all honour it.
- [ ] Path traversal / containment guards hold against a configured root outside `.prawduct/`,
      verified by test against the existing `plan_archive` resolve-both-sides pattern.
- [ ] `methodology/planning.md` § Where Artifacts Live and the doctor/janitor checks describe the
      configured root, not a literal path.
- [ ] Onboarding (`init-product`) can set it.

## Scope-out

- Migrating existing repos' artifacts automatically — the knob plus documentation is enough;
  moving files is the operator's act.
- Per-artifact path overrides. One root, not a map.
- Relocating `project-state.yaml` itself — it stays at `.prawduct/project-state.yaml` regardless
  of where `artifacts_dir` points (Grounding facts).
- Accepting a `.prawduct/`-relative spelling of `artifacts_dir:` alongside the project-root-relative
  one — Decision 1 resolves this to a single accepted base, not the build-plan pointer's dual
  acceptance.
- The exact enumeration of every markdown line to reword in doctor/janitor/methodology — ART-7
  fixes the standard; the design pass produces the list.

## Evidence / references

- `plugin/lib/gitstate.py:21-24` — `get_prawduct_dir`, the duplicated-small-helper precedent the
  new resolver's shape follows.
- `plugin/lib/core.py:178-179,328-361` — `BUILD_PLAN_POINTER_KEY` / `DEFAULT_BUILD_PLAN_REL` /
  `resolve_build_plan_path`, the closest existing "optional pointer key, defaulting" precedent,
  including the STH-5P2W dual-spelling incident Decision 1 argues against repeating.
- `plugin/lib/core.py:195-` — `read_str_yaml_key`, the shared reader `artifacts_dir:` will use.
- `plugin/lib/core.py:305` — `_branch_claimed_plan`'s `prawduct_dir / "artifacts"` construction.
- `plugin/lib/plan_archive.py:345-389` — `refusal_reason`, the resolve-both-sides containment
  guard to re-verify (Decision 4) rather than reinvent, including the docstring's account of the
  lexical-comparison defect it replaced.
- `plugin/lib/norm_index_scaffold.py:34` — `PREFERENCES_REL`, the fully-literal repo-relative
  string with no resolver involvement at all.
- `plugin/lib/init_product.py:16-17,55-56,59` — onboarding's literal template destinations and
  `_SCAFFOLD_DIRS` tuple.
- `plugin/bin/prawduct-hook:1402,4264,4904,5421,5990,6054` — further hand-built artifacts-path
  construction sites, including two (`:4264`, `:4904`) that bypass `get_prawduct_dir` entirely.
- `plugin/methodology/planning.md:45-47` — § Where Artifacts Live, the prose this item must
  update to describe the configured root.
- `plugin/skills/doctor/SKILL.md` Health Checks #5, #8, #10, #11, #14, #15; `plugin/skills/janitor/SKILL.md`
  Template Currency / Stale-plan / Norm-Health themes — check text naming the literal path
  (Grounding facts; exact edit list is a design-pass deliverable per Decision 6).
- Issue #715 — problem statement, current symlink-workaround analysis, proposed change, and
  acceptance criteria this document grounds.
