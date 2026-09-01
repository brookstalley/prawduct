# Issue #715 — Governance: Make the Artifacts Directory Root Configurable: Design

`status: draft · stage: design · area: governance · added: 2026-08-26 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/715`

Builds on `documentation/issues/715-requirements.md` (Decisions 1–6, requirements ART-1–ART-8).
That document scoped two things to design: the exact enumeration of every hand-built artifacts-path
construction site (ART-4), and the exact edit list for doctor/janitor/methodology prose (ART-7,
Decision 6). This document resolves both by re-walking the tree, and **corrects one shape decision
along the way**: Decision 2 proposed "a small helper duplicated per module, mirroring
`get_prawduct_dir`." Reading `gitstate.get_prawduct_dir`'s actual callers shows that helper is
**not** duplicated per module — every other `lib/` module imports it once from `gitstate.py`
(`from . import gitstate; gitstate.get_prawduct_dir(project_dir)`), and only `bin/prawduct-hook`
carries a second copy, because the hook needs it at bootstrap, before `lib/` is even on `sys.path`.
`get_artifacts_dir` has no equivalent bootstrap need — every call site that will need it already has
`lib/core.py` reachable (directly or via the hook's existing lazy `_core()` accessor) — so this
design places **one** implementation in `core.py`, imported everywhere, with **no** duplicate in the
hook. §2 makes the case in full; it is the one place this document deviates from the requirements
doc's Decisions rather than merely resolving what it deferred.

Grounding facts re-verified against current `develop` (2026-08-26, one day after the requirements
pass): the enumeration below is a fresh `grep -n '"artifacts"'` / `grep -rln '\.prawduct/artifacts'`
sweep, not a re-read of the prior document's citations — it finds several construction sites the
requirements doc's "further construction sites" list did not name (`briefing.py`, `buildplan_refs.py`,
`compliance.py`, `coverage_probes.py`, `norm_probes.py`, `plan_backfill.py`, `record_lint.py`,
`risk.py`, `lifecycle_repair.py`'s `ARTIFACTS_REL`, `release_readiness.py`'s `_ARTIFACTS_REL_DIR`).
None of this is drift from the requirements pass — ART-4 asked for exactly this enumeration and
named it a design-pass deliverable, not a requirements-pass one.

## 1. Summary of what ships

1. **ART-1, ART-2, ART-3** — one resolver, `get_artifacts_dir(project_dir)`, added to `plugin/lib/core.py`
   beside `resolve_build_plan_path` (§2). Reads `artifacts_dir:` from `project-state.yaml` via the
   existing `read_str_yaml_key`, interpreted relative to the **project root** (Decision 1), defaulting
   to `.prawduct/artifacts` when unset/empty/YAML null.
2. **ART-4** — every hand-built artifacts-path construction site in `bin/` and `lib/` (22 sites across
   14 files, enumerated in §3) replaced by a call through the resolver. No per-module duplicate; each
   site either already imports `core` (or a name from it) or gains that one import.
3. **ART-5** — `plan_archive.refusal_reason`'s existing resolve-both-sides containment guard is
   re-verified by test against a root outside `.prawduct/`; no guard code changes (§4).
4. **ART-6** — `init_product()` gains an `artifacts_dir:` onboarding path: a new `--artifacts-dir`
   flag on `prawduct-hook init-product`, shape-validated the same way `--backlog-repo` is, recorded
   into the freshly-scaffolded `project-state.yaml`, and used to build the scaffold's directory list
   and template destinations instead of the literal `_SCAFFOLD_DIRS` tuple (§5).
5. **ART-7** — the exact prose edit list for `methodology/planning.md` § Where Artifacts Live and
   every doctor/janitor check naming the literal path (§6).
6. **ART-8 (SHOULD)** — Doctor Health Check #5 gains one sentence: a symlinked `.prawduct/artifacts`
   alongside an unset `artifacts_dir:` suggests migrating to the native key (§7).

## 2. The resolver — `plugin/lib/core.py`

**Why one implementation in `core.py`, not a duplicate per module (deviation from Decision 2's
literal wording).** Grounding: `gitstate.get_prawduct_dir` (`gitstate.py:21-24`) is genuinely
duplicated exactly **once**, in `bin/prawduct-hook:67-68` — every `lib/` module that needs it
imports the `gitstate.py` copy (`buildplan_refs.py:48`, `briefing.py:43`, `compliance.py:26`,
`risk.py:56`, all call `gitstate.get_prawduct_dir(project_dir)`). The hook's copy exists because
`get_prawduct_dir` is needed at the hook's own bootstrap — resolving `.prawduct/` to decide whether
a repo is even governed, before `_plugin_root()` has seeded `sys.path` and any `lib/` import is
possible (`prawduct-hook:55-68`). `get_artifacts_dir` has no such bootstrap caller: every site named
in §3 already has `project_dir` (or `prawduct_dir`) resolved and `lib/` importable — the hook's own
sites reach it through the existing lazy `_core()` accessor (`prawduct-hook:217-232`), the same way
`cmd_clear` already reaches `atomic_write_text`. So the "duplicated helper" pattern this design
follows is `get_prawduct_dir`'s **actual** shape (one canonical copy, one bootstrap exception) — not
literally one copy per module, which no existing helper in this codebase does.

`core.py`'s top level is stdlib-only by existing convention (comment at `core.py:304`,
"core's top level stays stdlib-only"); `get_artifacts_dir` respects it — it calls only
`read_str_yaml_key`, already defined earlier in the same file, and needs no new import:

```python
# plugin/lib/core.py, placed immediately after resolve_build_plan_path (current :329-366)

# Optional project-state pointer naming the artifacts subtree root. UNLIKE
# BUILD_PLAN_POINTER_KEY, this is interpreted relative to the PROJECT ROOT, not
# `.prawduct/` (#715 Decision 1) — the entire premise of this key is a root that
# moves OUTSIDE `.prawduct/`, so a `.prawduct/`-relative spelling would force every
# such value to start with `../`, the exact traversal shape the STH-5P2W incident
# documented at resolve_build_plan_path (above) argues against accepting twice.
ARTIFACTS_DIR_POINTER_KEY = "artifacts_dir"
DEFAULT_ARTIFACTS_DIR_REL = ".prawduct/artifacts"


def get_artifacts_dir(project_dir: Path) -> Path:
    """Resolve the product's artifacts root.

    `artifacts_dir:` in `.prawduct/project-state.yaml`, resolved relative to
    ``project_dir`` when set; the conventional `.prawduct/artifacts` when unset,
    empty, or the YAML null literal (`read_str_yaml_key` already folds all three
    to ``None``). **The sole authority every reader calls through** (#715/ART-3) —
    no remaining `prawduct_dir / "artifacts"` or `project_dir / ".prawduct" /
    "artifacts"` construction anywhere in `bin/` or `lib/` (ART-4). Supports
    exactly one accepted spelling, project-root-relative — unlike
    `resolve_build_plan_path`'s pointer, no `.prawduct/`-relative dual spelling is
    accepted (Decision 1).

    Callers holding only `prawduct_dir` (not `project_dir`) pass
    `prawduct_dir.parent` — deterministic, since `get_prawduct_dir(project_dir)`
    is always exactly `project_dir / ".prawduct"`.
    """
    state_path = project_dir / ".prawduct" / "project-state.yaml"
    value = read_str_yaml_key(state_path, ARTIFACTS_DIR_POINTER_KEY)
    if not value:
        return project_dir / DEFAULT_ARTIFACTS_DIR_REL
    return project_dir / value
```

No traversal filtering on `value` here — `artifacts_dir:` is first-party repo configuration (the
operator's own choice, written by them or by `init-product` on their explicit flag), not
adversarial input, and the whole premise of the key is that it legitimately points **outside**
`.prawduct/`. The containment boundary that matters is the existing one at the *plan* level
(§4) — a plan path escaping the *configured* artifacts root via `..` — not this resolver refusing
values that are, by design, allowed to be anywhere.

## 3. Call-site migration (ART-4)

Every current construction site, re-verified 2026-08-26. "Import" is what each site needs to reach
`core.get_artifacts_dir` (or the bare name, inside `core.py` itself) — most already import something
from `core` for an unrelated reason and need no new import line, only the call-site edit.

**`bin/prawduct-hook`** (reaches the resolver via the existing lazy `_core()`, §2):

| Line | Current | Replacement |
| --- | --- | --- |
| `1510` | `prefs_path = prawduct_dir / "artifacts" / "project-preferences.md"` | `prefs_path = _core().get_artifacts_dir(project_dir) / "project-preferences.md"` |
| `4529` (`cmd_archive_plan`) | `artifacts_dir = project_dir / ".prawduct" / "artifacts"` | `artifacts_dir = _core().get_artifacts_dir(project_dir)` |
| `5169` (`cmd_coverage_scaffold`) | `artifacts_dir = project_dir / ".prawduct" / "artifacts"` | `artifacts_dir = _core().get_artifacts_dir(project_dir)` |
| `5686` (plan display-path base) | `plan_index.display_path(plan_path, prawduct_dir / "artifacts")` | `plan_index.display_path(plan_path, _core().get_artifacts_dir(project_dir))` |
| `6256` (`_work_model_corpus_paths`) | `paths = sorted((prawduct_dir / "artifacts").glob("*.md"))` | `paths = sorted(_core().get_artifacts_dir(project_dir).glob("*.md"))` |
| `6320` (`cmd_jurisdiction`, `--artifacts-only`) | `artifacts_root = prawduct_dir / "artifacts"` | `artifacts_root = _core().get_artifacts_dir(project_dir)` |

All six sites already have `project_dir` in local scope (each is inside a `cmd_*` function or a
helper that takes it as a parameter) — no signature changes in the hook.

**`plugin/lib/core.py`** (no import needed — same file as the resolver):

| Line | Current | Replacement |
| --- | --- | --- |
| `306` (`_branch_claimed_plan`) | `artifacts_dir = prawduct_dir / "artifacts"` | `artifacts_dir = get_artifacts_dir(prawduct_dir.parent)` |

**Modules that already import a name from `core` or `import core`** (add `get_artifacts_dir` to the
existing import list; edit the call sites):

| File | Import today | Sites (line: current) |
| --- | --- | --- |
| `briefing.py` | `from .core import (BUILD_PLAN_POINTER_KEY, AmbiguousPlanBranchError, atomic_write_text, read_str_yaml_key, resolve_build_plan_path)` (`:46-52`) | `181`: `arch_path = prawduct_dir / "artifacts" / "architecture.md"`; `218`: `dep_manifest = prawduct_dir / "artifacts" / "dependency-manifest.md"`; `265`: `plan_index.branch_claiming_plans(prawduct_dir / "artifacts")`; `279`: `plan_index.display_path(claim_path, prawduct_dir / "artifacts")`; `1102`: `prefs_path = prawduct_dir / "artifacts" / "project-preferences.md"` — each becomes `get_artifacts_dir(project_dir)` (`.../ "architecture.md"` etc. appended where a filename follows); all five sites have `project_dir` in scope already (each begins its function with `prawduct_dir = gitstate.get_prawduct_dir(project_dir)`) |
| `buildplan_refs.py` | `from .core import read_str_yaml_key, resolve_build_plan_path` (`:49`) | `571`: `plan_index.build_scope_to_plan_map(prawduct_dir / "artifacts")` inside `_scope_plan_map(prawduct_dir)` — only `prawduct_dir` in scope, becomes `core.get_artifacts_dir(prawduct_dir.parent)` (needs `from . import core` too, since only names were imported before); `670`: `plan_index.branch_claiming_plans(prawduct_dir / "artifacts")` inside a function taking `prawduct_dir` — same substitution |
| `lifecycle_repair.py` | `from . import buildplan_refs, core, plan_index` (`:76`) | `98`: `ARTIFACTS_REL = ".prawduct/artifacts"` (module constant — removed, it can no longer be a fixed string); `611`: `artifacts_dir = root / ARTIFACTS_REL` → `artifacts_dir = core.get_artifacts_dir(root)` (the function already takes a `root: Path` parameter that is a project dir — confirmed by its sibling call `plan_index.iter_scoped_plan_candidates(artifacts_dir)` at `:508` operating on the same shape) |
| `norm_index_scaffold.py` | `from . import core` (`:32`) | `34`: `PREFERENCES_REL = ".prawduct/artifacts/project-preferences.md"` (module constant — removed); `98`: `path = Path(project_dir) / PREFERENCES_REL` → `path = core.get_artifacts_dir(Path(project_dir)) / "project-preferences.md"` |

**Modules that import `gitstate` but not `core`** (add `from . import core`):

| File | Sites |
| --- | --- |
| `compliance.py` | `176-177`: `prawduct_dir = gitstate.get_prawduct_dir(project_dir); manifest_path = prawduct_dir / "artifacts" / "dependency-manifest.md"` → `manifest_path = core.get_artifacts_dir(project_dir) / "dependency-manifest.md"` (the `gitstate.get_prawduct_dir` call becomes dead here and is removed — nothing else in this branch needs `prawduct_dir`) |
| `risk.py` | `136` (`_boundary_pattern_paths(prawduct_dir)`): `path = prawduct_dir / "artifacts" / "boundary-patterns.md"` → `path = core.get_artifacts_dir(prawduct_dir.parent) / "boundary-patterns.md"` (only `prawduct_dir` in scope at this call site — `.parent`, per §2's derivation rule) |

**Modules that import neither today** (add `from . import core`):

| File | Sites |
| --- | --- |
| `plan_backfill.py` | `195` (`survey(prawduct_dir)`), `265` (`backfill(prawduct_dir, ...)`): both `artifacts_dir = prawduct_dir / "artifacts"` → `artifacts_dir = core.get_artifacts_dir(prawduct_dir.parent)` — neither function takes `project_dir` |
| `record_lint.py` | `651` (`_resolve_artifact(project_dir, prawduct_dir, name)` — takes **both**): `canonical = prawduct_dir / "artifacts" / f"{name}.md"` → `canonical = core.get_artifacts_dir(project_dir) / f"{name}.md"` (uses the already-available `project_dir` param directly, `prawduct_dir` stays used for nothing else in this function — confirm at implementation time whether the param becomes unused and drop it if so) |
| `release_readiness.py` | `40`: `_ARTIFACTS_REL_DIR = ".prawduct/artifacts"` (module constant — removed); `287`, `313`, `337`: each `artifacts = project_dir / _ARTIFACTS_REL_DIR` → `artifacts = core.get_artifacts_dir(project_dir)` (all three functions already take `project_dir`) |
| `coverage_probes.py` | `131`: `_ARTIFACTS_REL = (".prawduct", "artifacts")` (module constant — removed); `144`: `codebase.root.joinpath(*_ARTIFACTS_REL) / artifact_filename` → `core.get_artifacts_dir(codebase.root) / artifact_filename` (`codebase.root` is the project dir — `advisory_store.make_codebase`, `:431-433`) |
| `norm_probes.py` | `291` (`_artifact_paths(codebase)`): `artifacts = codebase.root / ".prawduct" / "artifacts"` → `artifacts = core.get_artifacts_dir(codebase.root)`; `697`: `_read_text(codebase.root / ".prawduct" / "artifacts" / "project-preferences.md")` → `_read_text(core.get_artifacts_dir(codebase.root) / "project-preferences.md")` |
| `init_product.py` | Already imports `from . import core` (`:38`) — see §5, handled separately (scaffold-time, not read-time) |

**Explicitly NOT a construction site (stays literal) — `core.py:111`**,
`RETIRED_GITIGNORE_ENTRIES = [".prawduct/artifacts/build-plan.md"]`. This is a historical string
match against **existing** `.gitignore` files from before this feature shipped — no repo could have
both a pre-existing retired ignore line at the old default path *and* a non-default `artifacts_dir:`
(the key did not exist when the line could have been written), so making this configurable would
detect nothing an old repo actually has. `update_gitignore` (`core.py:461-`) stays exactly as it is.

**22 sites total** (6 hook + 1 core.py + 5 briefing.py + 2 buildplan_refs.py + 1 lifecycle_repair.py
+ 1 norm_index_scaffold.py + 1 compliance.py + 1 risk.py + 2 plan_backfill.py + 1 record_lint.py +
3 release_readiness.py + 1 coverage_probes.py + 2 norm_probes.py), across 13 `lib/` files plus the
hook. `plan_index.py` needs **no** change — every one of its functions already takes `artifacts_dir:
Path` as a parameter rather than constructing it (`display_path`, `branch_claiming_plans`,
`build_scope_to_plan_map`, `iter_scoped_plan_candidates` — confirmed by reading the module), so it
inherits the fix through its callers automatically. This satisfies ART-4's acceptance line
("Plan discovery, coverage checks, norm-index scaffold, archive containment, and critic dispatch all
honour it") without `plan_index.py` itself needing to know a root is configurable.

## 4. Containment guard re-verification (ART-5)

No code change: `plan_archive.refusal_reason` (`plan_archive.py:345-389`) already resolves both
`plan_path` and `artifacts_dir` via `.resolve()` before `is_relative_to` (`:380-385`), and both its
callers (`cmd_archive_plan` at `prawduct-hook:4537-4538`, `4573-4575`) already pass whatever
`artifacts_dir` they computed — after §3's edit, that is `_core().get_artifacts_dir(project_dir)`,
which may now resolve outside `.prawduct/`. The guard's own logic does not reference `.prawduct/`
anywhere — it compares `plan_path` against whatever `artifacts_dir` it is given — so the change in
§3 is sufficient; this section is purely a test obligation (§8): confirm by test that
`refusal_reason` still refuses a plan path outside a **configured, non-default** root exactly as it
does against the default one today, and that `archive_destination` (`:330-342`, the sibling function
computing where an archived plan lands) places it correctly under a non-default root too — it is a
pure path computation with no `.prawduct/`-specific logic, so no change is expected there either,
only test coverage confirming it.

## 5. Onboarding — `init_product.py` (ART-6)

**Where the artifacts root is decided, and why before any directory is created.** `init_product()`
(`init_product.py:145-320`) currently builds `_SCAFFOLD_DIRS` and the two artifacts-template
destinations in `_STATE_TEMPLATES` (`:51-59`) from literal strings, and only writes
`project-state.yaml` itself partway through the function (inside the `_STATE_TEMPLATES` loop,
`:220-226`). A CLI-supplied non-default root has to be **decided before that loop runs** — the
scaffold's own directories and template destinations must be built from it — and only **recorded**
into `project-state.yaml` afterward, the same order `backlog_repo_recorded` already uses
(`_record_backlog_service_repo`, `:263-267`, runs after the state file exists). Unlike
`backlog_repo`, though, the artifacts root affects *where things get written in the same call* — so
this cannot simply mirror `_record_backlog_service_repo`'s append-after-the-fact shape; the value
has to be resolved once, up front, and threaded through both the scaffold-dir list and the state-file
append.

```python
# plugin/lib/init_product.py

def _validate_artifacts_dir(value: str) -> str | None:
    """Shape-check a --artifacts-dir value. Returns the cleaned relative string,
    or None if the value cannot be a project-root-relative directory (#715/ART-2).

    Deliberately permissive beyond the shape check — a value that already starts
    with ``.prawduct/`` (unusual, e.g. nesting the root one level deeper) is
    still a valid project-root-relative path and is not special-cased here; the
    only true rejects are absolute paths and traversal, both of which name
    something OTHER than a directory under this project root.
    """
    cleaned = value.strip().strip("/")
    if not cleaned:
        return None
    if Path(cleaned).is_absolute():
        return None
    if ".." in Path(cleaned).parts:
        return None
    return cleaned
```

`init_product()` gains an `artifacts_dir: str | None = None` keyword, validated the same way
`backlog_repo` is (shape-only, offline, a bad value becomes a `warnings` entry and is dropped, never
raised — `:176-185`'s pattern). The resolved relative string — the validated value, or the constant
`core.DEFAULT_ARTIFACTS_DIR_REL` (`.prawduct/artifacts`, §2) when absent or invalid — replaces the
literal in both places that currently use it:

- `_SCAFFOLD_DIRS` (`:59`) becomes a function `_scaffold_dirs(artifacts_root_rel: str) -> tuple[str, ...]`
  returning `(".prawduct", artifacts_root_rel, ".prawduct/.pr-reviews")`.
- `_STATE_TEMPLATES`'s two artifacts-rooted entries (`:55-56`) are built from `artifacts_root_rel`
  instead of the literal `.prawduct/artifacts/...` prefix; the other three (`project-state.yaml`,
  `backlog.md`, `change-log.md`) are unaffected — they live directly under `.prawduct/`, not the
  artifacts subtree.

After `project-state.yaml` is rendered (still the first entry in `_STATE_TEMPLATES`'s loop, so it
exists before anything else touches it) and only when `apply` is true and a non-default value was
requested, a new `_record_artifacts_dir(project_dir, artifacts_root_rel)` — the same
append-if-absent shape as `_record_backlog_service_repo` (`:85-111`) — writes:

```
artifacts_dir: docs/specs
```

into `project-state.yaml`. On a **dry run**, `artifacts_root_rel` is still used to compute
`created_dirs` / `created` correctly (mirroring `backlog_service_repo_recorded`'s dry-run
"report what would be recorded" rule, `:312-318`) — nothing is written, but the plan the caller sees
names the real destination.

**CLI wiring** (`init_product.py:340-410`, mirroring `--backlog-repo` line for line): `_parse_argv`
gains an `artifacts_dir` return slot and two branches (`--artifacts-dir` / `--artifacts-dir=`,
beside `:370-373`'s `--backlog-repo` handling); `run()`'s usage strings
(`:390-393`, `:401-404`) gain `[--artifacts-dir <path>]`; the call into `init_product()`
(`:411-` onward, not fully shown above but following the same shape as the `backlog_repo` pass-through)
passes it through. `prawduct-hook`'s own usage line (`:6201`,
`"...init-product <target> --name <name> [--backlog-repo owner/repo] [--apply] [--json]|"`) gains the
same flag.

**Not addressed here:** whether `/prawduct:onboard`'s interactive flow *asks* the user for a custom
root is a skill-prose decision, not a code change this item makes — the plumbing exists once this
ships; a future skill-prose pass can offer it. This item's ART-6 acceptance is "onboarding *can* set
it," which the flag satisfies without requiring the interactive skill to prompt for it yet.

## 6. Prose edits (ART-7, Decision 6)

Re-verified 2026-08-26. The wording convention: **first mention in a document** spells it out —
`"the artifacts root (`.prawduct/artifacts` by default, or wherever `artifacts_dir:` in
project-state.yaml points)"` — subsequent mentions in the same document say **"the artifacts root"**
or **"the configured artifacts root."** This mirrors how `resolve_build_plan_path`'s own pointer is
introduced once and referred to briefly thereafter in the surrounding prose.

**`plugin/methodology/planning.md`** — three mentions, all in scope (the requirements doc named only
§ Where Artifacts Live; the other two are updated alongside it so the document does not contradict
itself by describing a configurable root in one place and a fixed path two paragraphs away):

- `:13` — `"Each is a file in `.prawduct/artifacts/` (see \"Where Artifacts Live\")."` → first
  mention, full wording.
- `:47` (§ Where Artifacts Live itself) — `"Write all generated artifacts to `.prawduct/artifacts/`
  — ..."` → `"Write all generated artifacts to the artifacts root — ..."` (already forward-references
  the section title; the first-mention wording lands at `:13` instead, since it now comes first).
- `:53` — `"...a one-line `(not relevant — <reason>)` stub in `.prawduct/artifacts/<name>` **is**
  coverage..."` → `"...in the artifacts root, as `<name>`, **is** coverage..."`.

**`plugin/skills/doctor/SKILL.md`** — four checks:

- `:50` (Check #5) — `"`.prawduct/` has `project-state.yaml`, `learnings.md`, `backlog.md`,
  `change-log.md`, and `artifacts/`."` → `"...and the artifacts root (`artifacts/` by default,
  wherever `artifacts_dir:` points)."` — first mention in this document.
- `:53` (Check #8) — `"...must NOT ignore retired entries (`.prawduct/artifacts/build-plan.md` —
  ...)"` stays **literal** — this names the historical retired-entry string (§3's "explicitly not a
  construction site"), not a live path a reader should reinterpret as configurable.
- `:55` (Check #10) — `"`## Direction` sections in `.prawduct/artifacts/*.md`"` →
  `"`## Direction` sections in the artifacts root's `*.md` files"`.
- `:61` (Check #14) — `"...which enumerates `project-state.yaml`, `learnings.md`, `backlog.md`,
  `change-log.md` and `artifacts/`..."` → `"...and the artifacts root..."` (cross-references Check
  #5's wording, not a fresh explanation).

**`plugin/skills/janitor/SKILL.md`** — four mentions across three themes:

- `:170` (Lifecycle Convergence, "Stale build plans") — `"a plan in `.prawduct/artifacts/` whose
  work is over"` → `"a plan in the artifacts root whose work is over"` — first mention.
- `:174` (Norm Health) — `"`## Direction` sections in `.prawduct/artifacts/*.md`"` → same
  substitution as doctor Check #10.
- `:202` (Template Currency survey step) — `"`project-preferences.md` (if present in
  `.prawduct/artifacts/`)"` → `"...(if present in the artifacts root)"`.
- `:284` (Build Planning Flow) — `"write a build plan to `.prawduct/artifacts/build-plan.md`"` →
  `"write a build plan to `build-plan.md` in the artifacts root"`.

**Out of scope for this item** (named explicitly so a future reviewer does not read the omission as
missed): `plugin/CHANGELOG.md` (history — never rewritten for current behavior),
`plugin/templates/build-plan.md` and other template bodies (illustrative example content, not check
text — a template's own prose describing where *it* will land is arguably still accurate once
resolved, and touching template bodies is not named in ART-7), `plugin/docs/norms.md` and the
`skills/backlog`, `skills/critic`, `skills/learnings`, `skills/pr`, `skills/runbook` SKILL.md files
that mention the path descriptively rather than as check text a doctor/janitor run relays. ART-7's
acceptance line names doctor/janitor checks and planning.md's one section specifically; widening it
to every markdown file in the plugin that happens to contain the substring is scope creep this
design declines, consistent with Decision 6's own framing ("the design pass enumerates the exact
edit list" for the surface ART-7 actually names).

## 7. Doctor Check #5 addition (ART-8, SHOULD)

Appended to Check #5's existing sentence (`doctor/SKILL.md:50`), not a new numbered check — it is a
refinement of the same "core state present" read, not an independent condition:

> Additionally: if `.prawduct/artifacts` is a symlink and `artifacts_dir:` is unset in
> `project-state.yaml`, report **degraded** — this is the documented pre-native-key workaround
> (issue #715) — and suggest replacing the symlink with a real directory at the target and setting
> `artifacts_dir:` to point at it instead, since the symlink workaround breaks on
> `core.symlinks=false` checkouts and cannot cover per-file build-plan paths (`archive-plan` refuses
> across it). Detection is a plain `Path.is_symlink()` check on `.prawduct/artifacts` — read-only,
> no repair applied for them (consistent with every other Check #5 sub-finding).

## 8. Files touched

| File | Change |
| --- | --- |
| `plugin/lib/core.py` | new `ARTIFACTS_DIR_POINTER_KEY`, `DEFAULT_ARTIFACTS_DIR_REL`, `get_artifacts_dir()` (§2); `_branch_claimed_plan` call-site edit (§3) |
| `plugin/bin/prawduct-hook` | 6 call-site edits via `_core()` (§3); `init-product` CLI wiring for `--artifacts-dir` (§5) |
| `plugin/lib/briefing.py` | import + 5 call-site edits (§3) |
| `plugin/lib/buildplan_refs.py` | import + 2 call-site edits (§3) |
| `plugin/lib/lifecycle_repair.py` | remove `ARTIFACTS_REL`, 1 call-site edit (§3) |
| `plugin/lib/norm_index_scaffold.py` | remove `PREFERENCES_REL`, 1 call-site edit (§3) |
| `plugin/lib/compliance.py` | import + 1 call-site edit (§3) |
| `plugin/lib/risk.py` | import + 1 call-site edit (§3) |
| `plugin/lib/plan_backfill.py` | import + 2 call-site edits (§3) |
| `plugin/lib/record_lint.py` | 1 call-site edit (§3) |
| `plugin/lib/release_readiness.py` | remove `_ARTIFACTS_REL_DIR`, 3 call-site edits (§3) |
| `plugin/lib/coverage_probes.py` | import + remove `_ARTIFACTS_REL`, 1 call-site edit (§3) |
| `plugin/lib/norm_probes.py` | import + 2 call-site edits (§3) |
| `plugin/lib/init_product.py` | `_validate_artifacts_dir`, `_record_artifacts_dir`, `_scaffold_dirs()`, `init_product()` signature + flow, `_parse_argv`/`run()` CLI wiring (§5) |
| `plugin/lib/plan_archive.py` | none (§4) — test-only |
| `plugin/methodology/planning.md` | 3 line edits (§6) |
| `plugin/skills/doctor/SKILL.md` | 3 line edits + Check #5 addition (§6, §7) |
| `plugin/skills/janitor/SKILL.md` | 4 line edits (§6) |
| `tests/` | new coverage — see §9 |

## 9. Testing strategy → acceptance mapping

- **`get_artifacts_dir` unit tests** (new `test_core_artifacts_dir.py` or alongside existing
  `core.py` tests): unset/empty/`null`/`~` → default `.prawduct/artifacts`; a set value → that value
  resolved against `project_dir` (not `.prawduct/`); a value nested under `.prawduct/` still resolves
  correctly (not special-cased, per §5); a value that happens to look like it should be
  `.prawduct/`-relative (starts with `.prawduct/`) is honored literally, project-root-relative — this
  is the STH-5P2W-shaped regression to pin (ART-2).
- **Call-site regression tests** (per file touched in §3, extending each module's existing test
  suite): construct a repo fixture with `artifacts_dir: custom/root` set, run the function, assert it
  reads/writes under `custom/root` and not `.prawduct/artifacts`. At minimum one test per file in §3's
  tables, not one per call site — files with multiple sites (`briefing.py`, `release_readiness.py`)
  share a fixture across their sites' tests.
- **Containment guard test** (ART-5, §4): `plan_archive.refusal_reason` and
  `plan_archive.archive_destination` against an `artifacts_dir` outside the repo's `.prawduct/`
  (e.g. `docs/specs`) — a plan inside it archives normally; a plan path with `..` escaping it is
  refused, exactly as the existing default-root tests already assert (parametrize the existing test
  over both roots rather than writing a second copy).
- **`init_product` tests** (ART-6, §5): `--artifacts-dir docs/specs --apply` creates
  `docs/specs/project-preferences.md` and `docs/specs/boundary-patterns.md`, not
  `.prawduct/artifacts/...`; `project-state.yaml` records `artifacts_dir: docs/specs`; an invalid
  value (absolute path, `../escape`) is dropped with a `warnings` entry and the scaffold falls back
  to the default root; dry run reports the requested destination without writing anything (mirrors
  the existing `backlog_repo` dry-run test shape).
- **Doctor Check #5 addition** (ART-8, §7): a fixture with `.prawduct/artifacts` as a real symlink
  and `artifacts_dir:` unset reports degraded with the suggested fix; a fixture with the native key
  set (whether or not a symlink happens to also be present, which should not occur in practice) does
  not re-flag it.
- **Prose edits** (§6) are verified by reading the diff against the exact line list above — no
  automated test covers prose; a stale mention outside the enumerated lines is out of scope by
  construction (§6's explicit "out of scope" list), so a review pass confirming no OTHER
  `.prawduct/artifacts` literal remains in the six edited files (a `grep` after the edit, not a
  written test) is the acceptance check for those two files specifically.

## 10. Scope-out (unchanged from requirements)

Carries the requirements doc's scope-out list forward verbatim: no automatic migration of existing
repos' artifacts, no per-artifact path overrides (one root, not a map), `project-state.yaml` itself
stays at `.prawduct/project-state.yaml` regardless of where `artifacts_dir` points, no
`.prawduct/`-relative second accepted spelling. Nothing new is scoped out by this design pass beyond
the one item explicitly deferred forward: **whether `/prawduct:onboard`'s interactive flow prompts
for a custom root** (§5) is left to a future skill-prose item — this design ships the plumbing
(`--artifacts-dir` on `init-product`) without requiring the interactive skill to surface it yet.

## 11. Evidence / references

- `documentation/issues/715-requirements.md` — Decisions 1–6, requirements ART-1–ART-8, this
  design's starting point; names the two design-pass deliverables (ART-4's enumeration, ART-7's edit
  list) this document resolves, and the shape Decision 2 proposed for the resolver, which §2 revises
  with evidence from the actual import graph.
- `plugin/lib/gitstate.py:21-24` (`get_prawduct_dir`) and its callers (`buildplan_refs.py:48`,
  `briefing.py:43`, `compliance.py:26`, `risk.py:56`, each calling
  `gitstate.get_prawduct_dir(project_dir)`) — the evidence that this helper is imported once, not
  duplicated per module, grounding §2's deviation from Decision 2's literal wording.
- `plugin/bin/prawduct-hook:55-68` (`get_prawduct_dir`'s one real duplicate, and why — bootstrap,
  before `sys.path` is seeded), `:217-232` (`_core()`, the existing lazy accessor every hook call
  site in §3 reaches the resolver through).
- `plugin/lib/core.py:176-180,329-366` (`BUILD_PLAN_POINTER_KEY`/`DEFAULT_BUILD_PLAN_REL`/
  `resolve_build_plan_path`, the closest existing precedent and the STH-5P2W incident Decision 1
  argues against repeating), `:195-230` (`read_str_yaml_key`, reused unchanged), `:304-306`
  (`_branch_claimed_plan`, the one call site inside `core.py` itself).
- `plugin/lib/plan_archive.py:330-389` (`archive_destination`, `refusal_reason` — the containment
  guard §4 re-verifies rather than changes).
- `plugin/lib/init_product.py:51-59` (`_STATE_TEMPLATES`, `_SCAFFOLD_DIRS`), `:85-111`
  (`_record_backlog_service_repo`, the append-after-scaffold shape `_record_artifacts_dir` mirrors),
  `:145-320` (`init_product`, §5's edit target), `:340-410` (`_parse_argv`/`run`, the CLI shape
  `--artifacts-dir` mirrors from `--backlog-repo`).
- `plugin/lib/advisory_store.py:124-135,431-433` (`Codebase.root`, `make_codebase` — confirms
  `codebase.root` is the project dir for `coverage_probes.py`/`norm_probes.py`'s sites).
- `plugin/lib/core.py:76-111` (`GITIGNORE_ENTRIES`, `RETIRED_GITIGNORE_ENTRIES` — the evidence for
  §3's "explicitly not a construction site" call on the retired `build-plan.md` gitignore literal).
- `plugin/methodology/planning.md:13,47,53`; `plugin/skills/doctor/SKILL.md:50,53,55,61`;
  `plugin/skills/janitor/SKILL.md:170,174,202,284` — the exact prose sites §6 edits, re-verified by
  `grep -n` against current `develop` rather than carried over from the requirements pass.
- Issue #715 — problem statement, current symlink-workaround analysis (grounding §7's ART-8), and
  acceptance criteria both documents jointly ground.
