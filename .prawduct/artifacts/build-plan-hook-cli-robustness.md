<!-- Build Plan: hook-cli-robustness (v2.1.7)
     Tier: 1 (Source of Truth)
     A bundle of five independent, ready, S-effort robustness fixes to the
     framework's own hook CLI + governance libs. Highest-ROI structure: one
     chunk → one cumulative Critic pass → one PR, amortizing the (P0) review
     wall-clock across five correctness wins.
-->
---
artifact: build-plan
version: 2
scope: v2.1.7
depends_on: []
last_validated: null
---

## Requirements Confidence

**Level:** High

**Why:** Each of the five fixes has a one-sentence problem, a one-sentence success criterion, and a bounded scope — all sourced from recent Critic/builder/reviewer notes and verified against the actual code sites this session (exact functions located, fix-shapes confirmed buildable, test classes already exist for four of five surfaces).

**Open assumptions / unknowns:**
- `[ASSUMPTION: STH-5R2Q includes ALL flag-only handlers (cmd_audit_learnings, cmd_repo_disable, AND the hot-path cmd_clear) via one shared _reject_unknown_args helper | MED impact | user can correct — e.g. exclude cmd_clear if the SessionStart hook is found to pass tokens the helper would reject]`
- `[ASSUMPTION: BLD-4K7P skips intentionally-gitignored missing paths via `git check-ignore` inside _verify_chunk_refs (project_dir already in hand; subprocess fires only on the rare missing-ref path) rather than a hardcoded managed-prefix list | LOW impact | user can override to a static prefix set]`
- `[ASSUMPTION: TST-3E8V also broadens the error-message wording from "executable not found" to a launch-failure message that fits PermissionError too | LOW impact | user can defer the wording change]`
- `[ASSUMPTION: REL-7P3X strips only a leading origin/ before comparing — it does NOT switch cmd_stamp_merged to _resolve_base_branch (the divergence is deliberate, on record in the 2026-06-10 ch.02 Critic findings) | LOW impact | user can override]`

**What would raise confidence:** N/A (High).

## Status

- [ ] Chunk 01: Hook-CLI robustness bundle (5 fixes)

Context: Plan authored 2026-06-21 from backlog triage; user approved the 5-fix scope. Not yet built. All five sites located and fix-shapes verified this session — see per-deliverable notes below. Next: read `/prawduct:building`, then implement Chunk 01.

## Build Chunks

### Chunk 01: Hook-CLI robustness bundle (5 fixes)

- **Description:** Five independent robustness/correctness fixes to `bin/prawduct-hook` and two `lib/` modules. They share no logic — they are bundled to ship under one cumulative Critic review and one PR, not because they interact. Each is a few lines plus focused test coverage.

- **Depends on:** none

- **Artifacts consumed:** this plan; `.prawduct/learnings.md` (arg-parsing fail-closed convention, atomic-write convention).

- **Deliverables:**

  1. **STH-5R2Q — flag-only subcommands reject unknown args.** Flag-only handlers detect options via `"--flag" in argv` and silently ignore everything else (this masked a real test bug where `tmp_path` was passed positionally and the live repo was audited — `bin/prawduct-hook` `cmd_audit_learnings`). Add a small shared helper in `bin/prawduct-hook` (e.g. `_reject_unknown_args(argv, allowed_flags, cmd_name)`) that prints a `<cmd>: unknown argument <arg>` message to stderr and returns nonzero, matching the existing fail-closed style in `lib/ledger.py` / `lib/telemetry.py` / `lib/risk.py`. Apply it to every flag-only handler — those whose only inputs are recognized `--` flags and which accept no positionals. Scope by that structural shape, not by a line list. (See MED-impact assumption about `cmd_clear`.)

  2. **TST-3E8V — widen launch-failure catch in `cmd_test_evidence`.** In `bin/prawduct-hook` `cmd_test_evidence`, the `subprocess.run(run_argv, ...)` for a declared `test_command` is wrapped in `except FileNotFoundError` only, so a non-executable target raises `PermissionError` and tracebacks. Widen the catch to `OSError` (both are subclasses) so any OS-level launch failure takes the same clean exit-2 path; make the message fit both the missing and non-executable cases.

  3. **REL-7P3X — normalize origin/-prefixed base_branch in `cmd_stamp_merged`.** In `bin/prawduct-hook` `cmd_stamp_merged`, the branch guard compares the raw configured `base_branch` to the local `git rev-parse --abbrev-ref HEAD`. An origin/develop value (project-state.yaml's own comment calls it "preferred") would make the guard refuse permanently. Strip a single leading origin/ from the configured value before the equality check. Do not route through `_resolve_base_branch` (deliberate divergence — see assumption).

  4. **STH-9T4F — atomic writes for two remaining governance-state sites.** Convert `lib/critic_marker.py` (the critic-active marker payload write) and `lib/operator_verification.py` (the queue rewrite) from `Path.write_text(...)` to `core.atomic_write_text(...)`, importing `from .core import atomic_write_text` (mirrors `lib/advisory_store.py`). Rationale: readers fail open; a torn write misfires governance silently.

  5. **BLD-4K7P — `verify-chunk-refs` skips non-path tokens.** In `lib/buildplan_refs.py`, the backticked-token existence check (`_looks_like_file_path` / `_verify_chunk_refs`) flags false "missing-ref" positives on template placeholders (`<inbox>/<kebab-slug>.md`), URLs (`https://…`), and intentionally-gitignored managed paths (`.prawduct/.bug-inbox`). Extend `_looks_like_file_path` to reject tokens containing `<`/`>` or `://` (siblings of the existing glob-metachar exclusion), and skip gitignored missing paths in `_verify_chunk_refs` (see LOW-impact assumption). The `new`-prefix convention then remains needed only for genuinely-created files.

- **Deliverable files:** `bin/prawduct-hook`, `lib/critic_marker.py`, `lib/operator_verification.py`, `lib/buildplan_refs.py`, plus the test files below.

- **Tests:** extend, don't weaken, the existing classes; add a case per fix.
  - STH-5R2Q → `tests/test_plugin_runtime.py` (`TestAuditLearningsSubcommand`) + `tests/test_audit_learnings.py` (`TestAuditLearningsCLI`): an unknown positional/flag is rejected nonzero; recognized flags still pass.
  - TST-3E8V → `tests/test_plugin_runtime.py` (`TestTestEvidenceKnobs`): a non-executable `test_command` target takes the clean exit-2 path (no traceback).
  - REL-7P3X → `tests/test_views.py` (`TestStampMergedCommand`): an origin/develop configured base, current branch `develop`, stamps rather than refuses.
  - STH-9T4F → `tests/test_operator_verification.py` and the critic-marker test surface: assert the write goes through `atomic_write_text` (no-temp-file-left-behind / tmp-then-rename behavior), mirroring how `advisory_store` atomicity is tested.
  - BLD-4K7P → `tests/test_build_plan_resolution.py` (sibling of `TestVerifyChunkRefsGlobPaths`): `<…>`, `https://…`, and a gitignored managed path are NOT reported missing; a genuinely-missing real path still is.

- **Acceptance criteria:**
  1. Full suite green: `python3 -m pytest -q` (baseline 1352 tests; net new tests added, none removed/weakened).
  2. Each of the five fixes has at least one new test that fails before the fix and passes after.
  3. No new broad `except` without a `# prawduct:allow` waiver (TST-3E8V widens to `OSError`, which is specific and intentional — note it inline if a linter flags breadth).

- **Type:** cumulative-final
  <!-- Single-chunk plan shipped as one PR: the chunk's own review IS the one
       `/prawduct:critic cumulative` against `develop...HEAD`, which is the
       `/prawduct:pr create` gate. Commit the chunk first, then run cumulative
       once — no separate `final`. -->

- **Done when:**
  1. Acceptance criteria met and tests pass.
  2. Committed (chunk marked `[x]` in Status via the change-log entry).
  3. `/prawduct:critic cumulative` run against `develop...HEAD` and blocking findings resolved — this is the chunk's review AND the `/prawduct:pr create` gate.
  4. Backlog hygiene: mark STH-5R2Q, TST-3E8V, REL-7P3X, STH-9T4F, BLD-4K7P `status=shipped` via `/prawduct:backlog` (note CRT-9L2F as the natural post-release follow-up, unblocked once v2.1.7 ships).

## Early Feedback Milestone

**Milestone chunk:** Chunk 01 (single chunk — the bundle is self-contained).
**What the user can do:** Run the hardened hook CLI; observe that misused subcommands fail loudly, an origin/-prefixed base stamps correctly, governance markers survive a torn write, and legitimate build plans stop drawing false missing-ref findings.

## Governance Checkpoints

**Commit & PR cadence:** One chunk → commit → one `/prawduct:critic cumulative` (the chunk's review AND the PR gate) → `/prawduct:pr create`. Patch release → **v2.1.7**.

- After Chunk 01: cumulative Critic review (all 7 goals over `develop...HEAD`) — the single independent-review gate for the bundle before the PR opens.
