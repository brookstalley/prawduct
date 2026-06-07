---
artifact: build-plan
version: 2
scope: hook-decomp
depends_on: []
last_validated: null
---

# Build Plan — `bin/prawduct-hook` Decomposition (STH-9V4K)

Splits the 4,942-line `bin/prawduct-hook` monolith into cohesive `lib/` modules, leaving the
hook a thin CLI dispatcher (bootstrap + the inline build-plan mirror + `cmd_*` wrappers +
`main()`). This is a **behavior-preserving refactor** — the 875-test suite is the contract; every
chunk stays green; no assertion is weakened. Repointing a test's *import* to the code's new home
is not weakening it (the assertions are unchanged).

**Problem (STH-9V4K, janitor).** One file carries many distinct concerns — git/state probes,
session briefing, stop gates, build-plan parsing, coverage/base resolution, compliance canary —
which hinders readability. Re-verified 2026-06-03 at 4,369 lines; now 4,942.

**Success.** Each concern lives in its own `lib/` module; the hook drops to a thin dispatcher
(~700 lines); the suite stays green; the deliberate hot-path design invariants (below) are
preserved. The janitor's readability pressure is resolved at the structural level.

**Out of scope.** No behavior changes, no new features, no signature changes except where a
cohesive move requires an internal one (noted per chunk). The inline build-plan-resolution mirror
(`_BUILD_PLAN_POINTER_KEY`, `_DEFAULT_BUILD_PLAN_REL`, `_read_str_yaml_key`,
`_resolve_build_plan_path`) STAYS in the hook — it is a deliberate import-light/robustness mirror
of `lib/core`, pinned by `TestProductHookMirrorParity`. **`_read_bool_yaml_key` likewise STAYS** —
it is the same class of intentional inline import-light mirror of `lib.core.read_bool_yaml_key`,
pinned by `TestBoolKeyCallSiteParity` (the original Chunk-5 deliverable listed it to move, but the
code's explicit mirror contract overrides — discovered + corrected during ch.5 build). Likewise
`_SESSION_GITIGNORED_PATHS` + `_untrack_session_files` (session-start git mutation, parity-pinned
mirror) stay in the hook.

## Requirements Confidence

**Level:** High

Behavior-preserving refactor of well-understood, well-tested code with a documented parent
(STH-9V4K). The one real design question — how to extract hot-path logic without regressing the
hook's lib-independence invariant — is resolved (Chunk 1 below). Dependency order is derived from
an AST call-graph, not guessed.

### Design constraints discovered (the reason for Chunk 1 + the chunk order)

1. **Two hot paths are deliberately lib-independent.** The hook never imports `lib` at module top
   level; every `lib` use is lazy + `try/except ImportError`-guarded; the SessionStart briefing's
   core read path and the entire `cmd_stop` gate are inline "so the hot path stays robust even on
   an incomplete plugin install." But `lib/__init__.py` *eager-imports* the heavy modules
   (`advisory_store`, `views`, `operator_verification`, `critic_mode`, `audit_learnings_cmd`), so
   `from lib import <anything>` costs ~34ms and couples session-start to every heavy module's
   importability. **Chunk 1 fixes this** (slim `__init__.py` to lazy `__getattr__`) so any later
   `from lib import gitstate` loads only `gitstate.py` — isolated, ~1ms, robust. Without Chunk 1,
   extracting the briefing/gates would regress the invariant.

2. **The 6 concern clusters form a dependency cycle** (`briefing → gates → coverage →
   buildplan_refs → briefing`) driven by one mis-homed helper: `_parse_build_plan_status` lives in
   the briefing cluster but is build-plan parsing. **Reassigning it to `buildplan_refs`** makes the
   whole thing a clean DAG: `gitstate` (leaf) ← `buildplan_refs` ← `coverage` ← `gates` ←
   `briefing`; `compliance` ← `gitstate`.

3. **Incremental extraction must be leaf-first.** A `lib/` module cannot call code still sitting in
   the hook (that would be a `lib → bin` back-import). So each module is extracted only after the
   modules it depends on. Order is forced: `gitstate` first (most depended-upon), `briefing` last.

4. **Test coupling repoints to the new home.** Tests load the extensionless hook via
   `SourceFileLoader` and call `_hook._helper` directly. When a helper moves to `lib/`, its test is
   repointed to `from lib import <module>` (the right thing — test the code where it lives), NOT
   shimmed back through the hook. `cmd_*` wrappers stay in the hook, so `_hook.cmd_clear` etc. keep
   working. A few source-inspection tests in `test_plugin_runtime.py` pin symbols
   (`_resolve_base_branch`) — updated alongside the move.

### Delegation pattern (every extraction follows this)

The hook's hot-path callers (still-inline briefing/gates and the `cmd_*` wrappers) call the
extracted module via the established lazy-import idiom (mirrors `_waivers_module()` /
`cmd_advisory`): seed `sys.path` with `_plugin_root()`, `from lib import <module>` *inside the
using function* (keeps the hook's top level lib-free, preserving the AST-checked invariant). After
Chunk 1, that import is cheap and isolated.

## Status

*Derived view (`views_enabled`): `[x]` means **shipped** (merged to develop). Each chunk ships as
its own PR (one module per PR, per the decomposition decision). Checkboxes flip automatically when
each PR merges via `/prawduct:pr` + regen-views.*

- [ ] Chunk 1: Slim `lib/__init__.py` to lazy `__getattr__` (enabling; no module extraction). **Critic mode:** chunk
- [ ] Chunk 2: Extract `lib/gitstate.py` — read-only git/state probes (leaf). **Critic mode:** chunk
- [ ] Chunk 3: Extract `lib/buildplan_refs.py` — chunk-ref parsing + trivial classification (+ `_parse_build_plan_status`). **Critic mode:** chunk
- [ ] Chunk 4: Extract `lib/compliance.py` — compliance canary + file classifiers. **Critic mode:** chunk
- [ ] Chunk 5: Extract `lib/coverage.py` — coverage/base/cumulative + PR doc-only/trivial gates. **Critic mode:** chunk
- [ ] Chunk 6: Extract `lib/gates.py` — stop-gate logic + test-evidence commands. **Critic mode:** chunk
- [ ] Chunk 7: Extract `lib/briefing.py` — staleness + session/subagent briefing + handoff. **Critic mode:** final

Context: **All 7 chunks built — the decomposition is complete (pending release).** Ch.1-2 merged via
#74; ch.3 (`lib/buildplan_refs.py`) #75; ch.4 (`lib/compliance.py`) #76; ch.5 (`lib/coverage.py`) #77;
ch.6 (`lib/gates.py`) #78 — all develop. Ch.7 (`lib/briefing.py`) committed on
`refactor/hook-decomp-briefing` off develop. Hook now **1,911 lines** (was 4,942 at plan start — a
**61% reduction**; ch.6 left it at 2,793). Full suite 947 green (884 + 6 extraction + 57 briefing unit tests);
`clear`/`stop` smoke-clean via the real CLI through the lazy `lib` accessors. Checkboxes stay `[ ]`
until the develop→main release flips them via `status=shipped` change-log tags + regen-views.

**Ch.6 scope (decided with the user — "helpers to gates, cmd_stop stays" — after a dependency scan
resolved a Chunk-6-vs-Chunk-7 contradiction):** `cmd_stop`'s body **stays resident** — it is the
deliberately-inline hot-path gate (constraint 1 + Chunk 7) and uses the hook-resident gate-attribution
machinery (`_gate_attribution`/`_load_gate_registry`/`_plugin_manifest_version`) shared with
`cmd_clear`, so moving it would be a `gates → bin` back-import. `cmd_test_evidence` also stays (needs
`_plugin_root`). Moved to `lib/gates.py`: the 9 gate helpers (`tests_are_current`,
`_validate_evidence_schema`, `_read_gates_waived`, `validate_critic_findings`,
`_compute_verify_resolutions_scope`, `_verify_resolutions_gate_check`, `_count_build_plan_chunks`,
`_critic_session_satisfies_gate`, `_has_build_plan_in_state`) + **reassigned** `_has_active_build_plan_file`
(gate-used, was nominally ch.7) and `_is_trivial_fileset_eligible` + 9 evidence/critic-mode constants
+ the 4 self-contained gate command bodies as `test_status`/`validate_evidence`/`check_cumulative_critic`/
`verify_coverage` (hook keeps thin `cmd_*` wrappers). Sanctioned rewrites: `get_prawduct_dir`→`gitstate.`,
`_resolve_build_plan_path`→`core.resolve_build_plan_path`, `_read_bool_yaml_key`→`core.read_bool_yaml_key`,
accessor calls→sibling imports. Resident callers (`cmd_stop`, `_check_previous_session_gates`,
`staleness_scan`, `cmd_compute_verify_resolutions_scope`) rewired to `_gates().<fn>`. Tests:
`test_critic_mode_inference.py` repointed (`validate_critic_findings`→`lib.gates`, dead hook loader
removed); `test_plugin_runtime.py` namespacing test now scans the runtime command surface
(hook + `lib/gates`/`lib/coverage`) so a bare command form can't hide in a relocated body.

**Chunk 7 done — the decomposition is complete.** `lib/briefing.py` extracted (the proven pattern:
source-extract → AST-verify identical → add the lazy `_briefing()` accessor → rewire `cmd_clear`'s 5
call sites → full suite + golden briefing compare + CLI smoke → `/prawduct:critic final`). Degradation
decided: no new shim — `cmd_clear`'s call sites are already broad-caught, so a `lib.briefing` import
failure degrades to a skipped briefing without blocking session start (ch.2–6 precedent; pinned by a
new test). Enabled follow-up still open: STH-2K8R (critic_mode mirror consolidation). Remaining: the
develop→main release that flips all checkboxes `[x]` (`status=shipped` tags + regen-views).

## Chunk detail

### Chunk 1: Slim `lib/__init__.py` (enabling)

- **Deliverable:** `lib/__init__.py` rewritten so importing any submodule does NOT eager-import the
  heavy modules. Replace the eager `from .X import (...)` re-export blocks with a PEP-562
  module-level `__getattr__(name)` that maps each currently-flattened export name → its submodule
  and lazy-imports on first access. Submodule imports (`from lib import views`, `from lib import
  gitstate`, `from lib.advisory_store import run_sync_advisories`) already resolve natively and need
  no entry. `__dir__` returns the export set for introspection.
- **Why:** makes every `from lib import <submodule>` isolated + cheap (~1ms vs ~34ms) so later
  chunks can extract hot-path logic without regressing the lib-independence invariant (constraint 1).
- **Preserve exactly** the current package-level flattened API: every name in today's eager
  `from .core / .advisory_store / .advisory_cmd / .critic_mode / .audit_learnings_cmd /
  .operator_verification import (...)` lists must still resolve via `from lib import <name>` and
  `lib.<name>`. `from . import views` / `from . import waivers` become native submodule access.
- **Done when:**
  1. `__getattr__` covers every current flattened export; `AttributeError` for unknown names.
  2. A test asserts the isolation property: importing a leaf submodule (e.g. `lib.core`) does NOT
     put a heavy module (`lib.views`) in `sys.modules`. (New: `tests/test_lib_lazy_imports.py`.)
  3. A test asserts every previously-flattened name is still reachable via `from lib import <name>`.
  4. Full suite green (875). `/prawduct:critic chunk`; blocking findings resolved. Committed.

### Chunk 2: Extract `lib/gitstate.py` (leaf — read-only probes)

- **Deliverable:** new `lib/gitstate.py` containing the read-only git/state probes + their
  module-level constants, moved verbatim: `git_status_output`, `git_has_changes`, `_is_metadata_path`
  (+`_METADATA_PREFIXES`), `git_has_session_changes`, `_session_changes_are_doc_only`,
  `git_has_code_changes`, `_is_framework_tooling`, `_has_product_code` (+`_PRODUCT_CODE_SUFFIXES`),
  `_has_product_definition_work` (+`_DOC_ROOTS`), `_discovery_uncaptured`, `_read_advisory_store`,
  `_git_head_sha`, `_get_session_changed_files`. Needs `get_prawduct_dir` — add a tiny local copy in
  gitstate (it is `project_dir / ".prawduct"`; the hook keeps its own — trivial, not worth a shared
  import that re-couples). Hook callers rewired to `gitstate.<fn>` via the lazy idiom.
- **Excluded (stay in hook):** `_untrack_session_files` + `_SESSION_GITIGNORED_PATHS` (session-start
  git mutation + parity-pinned mirror); `_is_source_file/_is_test_file/_is_dependency_file` → move
  with `compliance` (Chunk 4, their only caller).
- **Tests repoint:** `test_discovery_capture_nudge.py` (`_discovery_uncaptured`, `_has_product_code`,
  `_has_product_definition_work`) → `from lib import gitstate`. `cmd_clear` accesses unchanged.
- **Done when:** 1. functions moved, hook delegates lazily; 2. tests repointed; 3. full suite green;
  4. briefing still produced (run `prawduct-hook clear` smoke); 5. `/prawduct:critic chunk` clean;
  committed.

### Chunk 3: Extract `lib/buildplan_refs.py`

- **Deliverable:** `_looks_like_file_path`, `_parse_build_plan_chunk_refs`, `_parse_build_plan_chunk_type`,
  `_parse_build_plan_chunk_trivial_rationale`, `_classify_trivial_change` (+`_TRIVIAL_PROTECTED_PATHS`),
  `_current_chunk_id_from_status`, `_verify_chunk_refs`, **and `_parse_build_plan_status`** (reassigned
  from briefing to break the cycle — constraint 2). Imports `gitstate` for `_is_metadata_path` /
  `git_status_output`. The inline mirror (`_read_str_yaml_key`, `_resolve_build_plan_path`) stays in
  the hook; buildplan_refs takes its own small reads or receives paths.
- **Tests repoint:** `test_build_plan_resolution.py` (`_parse_build_plan_chunk_refs`, `_verify_chunk_refs`),
  `test_trivial_fileset_gate.py` (`_TRIVIAL_PROTECTED_PATHS`, `_classify_trivial_change`).
- **Done when:** moved; briefing's `_parse_build_plan_status` callers rewired to `buildplan_refs`;
  suite green; `/prawduct:critic chunk`; committed.

### Chunk 4: Extract `lib/compliance.py`

- **Deliverable:** `compliance_canary`, `_check_broad_exceptions`, `_check_invalid_waivers`,
  `_waivers_module`, plus the file classifiers `_is_source_file`/`_is_test_file`/`_is_dependency_file`
  (their only caller is the canary). Imports `gitstate` for `_get_session_changed_files`.
- **Tests repoint:** `test_waivers.py` (`_check_broad_exceptions`, `_check_invalid_waivers`).
- **Done when:** moved; `cmd_stop` calls `compliance.compliance_canary` lazily; suite green;
  `/prawduct:critic chunk`; committed.

### Chunk 5: Extract `lib/coverage.py` — **AS BUILT** (scope corrected from the original plan)

- **Deliverable (as built):** `_git_ref_exists`, `_resolve_base_branch`, `_coverage_resolve_base`,
  `_coverage_changed_files`, `_pr_diff_is_doc_only`, `_pr_diff_is_trivial` (+ `_BASE_BRANCH_KEY` /
  `_DEFAULT_BASE_CANDIDATES`), and the bodies of the two **gates-free** PR fast-path commands as
  `check_pr_doc_only` / `check_pr_trivial` (hook keeps thin `cmd_*` wrappers). Imports `buildplan_refs`
  (`_classify_trivial_change`) and `core` (`read_str_yaml_key` — the canonical twin of the hook's
  `_read_str_yaml_key` mirror; sanctioned rewrite). `gitstate` is **not** needed in the reduced scope.
- **Deferred to Chunk 6 (back-import avoidance):** `cmd_verify_coverage` + `cmd_check_cumulative_critic`
  bodies — they call `_validate_evidence_schema` / `validate_critic_findings` / `_CRITIC_MODE_CUMULATIVE`
  (Chunk-6 `gates` symbols). DAG is `coverage ← gates`, so they move with `gates`. They stay resident
  for now, reaching the moved helpers via `_coverage()`.
- **Kept in hook (corrected):** `_read_bool_yaml_key` — parity-pinned inline mirror of
  `lib.core.read_bool_yaml_key` (`TestBoolKeyCallSiteParity`), same class as `_read_str_yaml_key`.
- **Tests repoint (as built):** `test_views.py` unchanged (its `_read_bool_yaml_key` parity test
  still pins the hook mirror). `test_plugin_runtime.py` source-inspection repointed:
  `"def _resolve_base_branch(" in src` → `"_coverage()._resolve_base_branch(" in src` (the wrapper
  wiring; the resolver now lives in `lib/coverage`). The CLI behavioral tests
  (`resolve-base`/`check-pr-*` via subprocess) are unchanged and exercise the move end-to-end.
- **Done when:** ✅ moved; `resolve-base`/`verify-coverage`/`check-pr-*` subcommands pass; suite green
  (884); `/prawduct:critic chunk`; committed.

### Chunk 6: Extract `lib/gates.py` — **AS BUILT** (scope decided with the user; cmd_stop stays)

A dependency scan before building surfaced a **Chunk-6-vs-Chunk-7 contradiction**: Chunk 6 said "move
the bodies of cmd_stop … (hook keeps thin wrappers)", but Chunk 7 + constraint 1 say the hook keeps
`cmd_stop` inline. The facts resolved it — `cmd_stop` uses the hook-resident gate-attribution machinery
(`_gate_attribution`/`_load_gate_registry`/`_plugin_manifest_version`, shared with `cmd_clear`), so
moving its body to `gates` would be a `gates → bin` back-import. User chose: **move the helpers, keep
`cmd_stop` resident.**

- **Deliverable (as built):** moved to `lib/gates.py` — the 9 gate helpers (`tests_are_current`,
  `_validate_evidence_schema`, `_read_gates_waived`, `validate_critic_findings`,
  `_compute_verify_resolutions_scope`, `_verify_resolutions_gate_check`, `_count_build_plan_chunks`,
  `_critic_session_satisfies_gate`, `_has_build_plan_in_state`), the 9 evidence/critic-mode constants,
  **reassigned** `_has_active_build_plan_file` (gate-used probe, was nominally ch.7) +
  `_is_trivial_fileset_eligible`, and the 4 self-contained gate command bodies as `test_status` /
  `validate_evidence` / `check_cumulative_critic` / `verify_coverage` (the deferred ch.5 pair +
  test-status/validate-evidence; hook keeps thin `cmd_*` wrappers). Imports `gitstate` / `coverage` /
  `buildplan_refs` + `core` (`read_bool_yaml_key`, `resolve_build_plan_path`). Sanctioned rewrites:
  `get_prawduct_dir`→`gitstate.`, `_resolve_build_plan_path`→`core.resolve_build_plan_path`,
  `_read_bool_yaml_key`→`core.read_bool_yaml_key`, accessor calls→sibling imports.
- **Stay resident:** `cmd_stop` (hot-path gate + attribution machinery) and `cmd_test_evidence`
  (needs `_plugin_root`). Both call the moved helpers via the new lazy `_gates()` accessor. Because
  `cmd_stop` is reached only through `main()` dispatch and already uses sibling accessors un-wrapped
  (ch.2–5 precedent), an import failure surfaces there, not at module top — the lib-free top-level
  invariant is preserved; no separate degradation shim was needed.
- **Resident callers rewired** to `_gates().<fn>`: `cmd_stop`, `_check_previous_session_gates`,
  `staleness_scan`, `cmd_compute_verify_resolutions_scope`.
- **Tests (as built):** `test_critic_mode_inference.py` repointed (`validate_critic_findings` →
  `lib.gates`; now-dead `_load_prawduct_hook` helper removed). `test_plugin_runtime.py`
  namespacing test extended to scan the runtime command surface (hook + `lib/gates` + `lib/coverage`)
  so a bare command form can't hide in a relocated body. (The plan's `test_critic_gate_fallthrough.py`
  / `test_cumulative_gate.py` needed no change — they drive `stop` via subprocess, exercising the
  rewired path end-to-end.)
- **Done when:** ✅ moved; `stop`/`test-status`/`validate-evidence`/`verify-coverage`/
  `check-cumulative-critic` pass via the real CLI; suite green (884); `/prawduct:critic chunk`;
  committed. Hook 3,785 → 2,793.

### Chunk 7: Extract `lib/briefing.py` — **AS BUILT** (final chunk)

- **Deliverable (as built):** new `lib/briefing.py` holds **17** functions moved verbatim —
  `_extract_dependency_names`, `staleness_scan`, `_get_product_name`, `_get_current_branch`,
  `_parse_wip`, `_parse_all_wip_branches`, `_get_active_work`, `_get_work_in_progress`,
  `_detect_worktrees`, `_get_other_branch_wip`, `assemble_session_briefing`, `_extract_critical_rules`,
  `generate_subagent_briefing`, `_git_session_commits`, `_summarize_critic_findings`,
  `generate_session_handoff`, `_check_previous_session_gates`. (`_has_active_build_plan_file`, the 18th
  name this chunk originally listed, was already reassigned to `lib/gates` in ch.6 as a gate-used
  probe.) `briefing` is the top of the DAG — imports `gitstate` / `gates` / `buildplan_refs` + `core`
  (`resolve_build_plan_path`); nothing imports it. Sanctioned rewrites: `get_prawduct_dir`→
  `gitstate.get_prawduct_dir`, `_resolve_build_plan_path`→`core.resolve_build_plan_path`, accessor
  calls (`_gitstate()`/`_gates()`/`_buildplan_refs()`)→sibling imports.
- **Degradation decided (the chunk's one design question): no new shim.** `cmd_clear` stays resident
  and reaches the briefing via a new lazy `_briefing()` accessor; its 5 call sites are each already
  wrapped in a broad catch, so a `lib.briefing` import failure surfaces at the call site (not the
  hook's lib-free top level), degrades to a skipped briefing (stderr NOTE), and the session still
  starts (markers + baseline written, returns 0) — the ch.2–6 precedent. A minimal-briefing fallback
  would be new behavior the behavior-preserving refactor does not call for.
- **Tests (as built):** new `tests/test_briefing_extraction.py` exercises the public surface directly
  from `lib.briefing` (coverage preference; nothing referenced these symbols before) and pins the
  degradation contract (`cmd_clear` survives a monkeypatched `_briefing()` `ImportError`).
  `test_plugin_runtime.py`'s no-bare-command-forms sweep now also scans `lib/briefing` (the most
  command-hint-dense surface) so a bare form can't hide once the `/prawduct:*` hints leave the hook. No
  symbol repoints needed (the briefing was tested only behaviorally, via the `clear` CLI).
- **Done when:** ✅ moved; AST-verified all 17 byte-identical after the sanctioned rewrites; golden
  `assemble_session_briefing` output byte-identical before/after; suite green (947 — incl. 57 new
  per-branch briefing unit tests added after the PR review surfaced the inherited thin internal
  coverage); `clear`/`stop`
  smoke-clean via the real CLI; `/prawduct:critic final`; committed. Hook **2,793 → 1,911** (whole
  decomposition: 4,942 → 1,911, −61%). The hook is now a thin dispatcher (bootstrap + parity-pinned
  inline mirrors + lazy `lib` accessors + `cmd_*` wrappers + `cmd_clear`/`cmd_stop`/`main`); the
  original "~700 lines" target was set before ch.5/ch.6 deliberately kept `cmd_stop`, the
  attribution machinery, and the import-light mirrors resident.

## Verification strategy

Every chunk: (a) full `pytest` suite green (the behavior contract); (b) product-layer smoke of the
affected subcommand via the real CLI (`prawduct-hook clear` / `stop` / `verify-coverage` / etc.) —
moves are invisible to tests only if the CLI still behaves; (c) `/prawduct:critic chunk` (final on
Chunk 7). Chunk 7 adds a golden-output compare of the briefing before/after to prove byte-identity.
