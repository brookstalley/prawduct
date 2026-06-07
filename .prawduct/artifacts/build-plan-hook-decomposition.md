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

Context: Chunks 1-5 built + Critic-clean. Ch.1-2 merged via #74; ch.3 (`lib/buildplan_refs.py`) via
**#75**; ch.4 (`lib/compliance.py`) via **#76** — both develop. ch.5 (`lib/coverage.py`) committed on
`refactor/hook-decomp-coverage` off develop. Hook now **3,757 lines** (was 4,942 at plan start). Full
suite 884 green; `resolve-base`/`verify-coverage`/`check-pr-doc-only`/`check-pr-trivial` smoke-clean via
the real CLI through the new `_coverage()` accessor. Checkboxes stay `[ ]` until release; develop-merge
tracked by the change-log entry.

**Ch.5 scope correction (two plan deviations, both validated against the code before building):**
(1) `cmd_verify_coverage` + `cmd_check_cumulative_critic` bodies were **deferred to Chunk 6** — they
depend on `_validate_evidence_schema` / `validate_critic_findings` / `_CRITIC_MODE_CUMULATIVE`, all
Chunk-6 (`gates`) symbols; with the DAG running `coverage ← gates`, moving them now would be a
`coverage → gates → bin` back-import. They stay resident, calling the moved helpers via `_coverage()`,
and move with `gates`. (2) `_read_bool_yaml_key` **stays in the hook** — it is a parity-pinned inline
import-light mirror of `lib.core.read_bool_yaml_key` (`TestBoolKeyCallSiteParity`), the same class as
`_read_str_yaml_key`; the plan's deliverable listing it to move was an over-specification. Net ch.5
move: the 6 remaining helpers (`_git_ref_exists`, `_resolve_base_branch`, `_coverage_resolve_base`,
`_coverage_changed_files`, `_pr_diff_is_doc_only`, `_pr_diff_is_trivial`) + `_BASE_BRANCH_KEY` /
`_DEFAULT_BASE_CANDIDATES` + the two gates-free PR fast-path commands (now `coverage.check_pr_doc_only`
/ `coverage.check_pr_trivial`, hook keeps thin `cmd_*` wrappers). `test_views.py` needs no change
(its `_read_bool_yaml_key` parity test still pins the hook mirror); `test_plugin_runtime.py`
source-inspection repointed to the `_coverage()._resolve_base_branch` wiring.

**Next: Chunk 6 (`lib/gates.py`)** — stop-gate logic + test-evidence commands, **plus the two deferred
coverage/critic gate commands** (`cmd_verify_coverage`, `cmd_check_cumulative_critic`). Imports
`gitstate`, `coverage`, `compliance`. The proven pattern: write `lib/<mod>.py` (verbatim move,
AST-verify identical) → add the lazy accessor → rewire resident call sites → repoint coupled tests →
full suite + CLI smoke → `/prawduct:critic chunk`. Enabled follow-up filed: STH-2K8R (critic_mode
mirror consolidation).

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

### Chunk 6: Extract `lib/gates.py`

- **Deliverable:** `tests_are_current`, `_validate_evidence_schema` (+evidence/critic-mode
  constants), `_read_gates_waived`, `validate_critic_findings`, `_compute_verify_resolutions_scope`,
  `_verify_resolutions_gate_check`, `_count_build_plan_chunks`, `_critic_session_satisfies_gate`,
  `_has_build_plan_in_state`, and the bodies of `cmd_stop` / `cmd_test_status` /
  `cmd_validate_evidence` / `cmd_test_evidence` (hook keeps thin wrappers). **Plus the two
  coverage/critic gate commands deferred from Chunk 5** — `cmd_verify_coverage` (needs
  `_validate_evidence_schema`) and `cmd_check_cumulative_critic` (needs `validate_critic_findings` +
  `_CRITIC_MODE_CUMULATIVE`); both also consume `coverage` helpers, so they belong here where
  `gates → coverage` + gates-internal are both legal. Imports `gitstate`, `coverage`, `compliance`.
  **cmd_stop is hot-path + lib-free today** — its lazy import of `gates` must degrade gracefully
  (a broken `gates` import must not crash session end); keep the gate's fail-safe posture.
- **Tests repoint:** `test_critic_gate_fallthrough.py` (`validate_critic_findings`), `test_cumulative_gate.py`,
  evidence/stop tests as needed.
- **Done when:** moved; `stop`/`test-status`/`validate-evidence`/`test-evidence` pass; suite green;
  `/prawduct:critic chunk`; committed.

### Chunk 7: Extract `lib/briefing.py`

- **Deliverable:** the SessionStart briefing assembly — `staleness_scan`, `_extract_dependency_names`,
  `_get_product_name`, `_get_current_branch`, `_parse_wip`, `_parse_all_wip_branches`,
  `_has_active_build_plan_file`, `_get_active_work`, `_get_work_in_progress`, `_detect_worktrees`,
  `_get_other_branch_wip`, `assemble_session_briefing`, `_extract_critical_rules`,
  `generate_subagent_briefing`, `_git_session_commits`, `_summarize_critic_findings`,
  `generate_session_handoff`, `_check_previous_session_gates`. Imports `gitstate`, `gates`,
  `buildplan_refs`. **Hot path + lib-free today** — `cmd_clear` must still produce a briefing if the
  `briefing` import fails (degrade to a minimal briefing, or accept a hard dep with a clear error);
  decide + test the degradation. The hook keeps `cmd_clear`/`cmd_stop`/`main()` + the inline mirror.
- **Done when:** moved; `prawduct-hook clear` produces an identical briefing (golden compare); the
  hook is a thin dispatcher (~700 lines); suite green; **`/prawduct:critic final`** (last chunk —
  Coherence/Design/Learnings/Backlog cross-checks); committed.

## Verification strategy

Every chunk: (a) full `pytest` suite green (the behavior contract); (b) product-layer smoke of the
affected subcommand via the real CLI (`prawduct-hook clear` / `stop` / `verify-coverage` / etc.) —
moves are invisible to tests only if the CLI still behaves; (c) `/prawduct:critic chunk` (final on
Chunk 7). Chunk 7 adds a golden-output compare of the briefing before/after to prove byte-identity.
