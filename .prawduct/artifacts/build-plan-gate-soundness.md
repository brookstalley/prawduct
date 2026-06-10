---
artifact: build-plan
version: 2
scope: gate-soundness
depends_on: []
last_validated: 2026-06-10
---

# Build Plan — Gate Soundness (producer/consumer reconciliation)

**Problem.** Four framework gates have pass conditions the documented workflow cannot
reach, so product agents (scriob session 2026-06-09, PR #43) burn cycles on trial-and-error
and ultimately neutralize the gates (scriob commit 4ca5bd3 unions the full branch diff into
`changes_referenced`, making verify-coverage vacuous). Evidence: scriob's
`scripts/test-evidence.sh` (90-line workaround), its learnings entries
"verify-coverage diffs the WHOLE branch" (confirmations=3), "check-cumulative-critic needs a
cumulative-mode record at HEAD", "A tracked pointer must never reference a gitignored file".

**Success.** A product on a supported repo shape (root-pytest, monorepo multi-tree, uv-managed
venv) can satisfy every gate by following the documented happy path, with zero wrapper scripts:
the coverage gate only blocks on files the verifier can judge; `test-evidence record` honors a
declared test command and test dirs; build plans are tracked (and stay tracked); the
cumulative-gate ordering rule is stated where agents will read it before paying a re-review.

**Out of scope.** (a) A verify-resolutions→cumulative gate-chain extension (document the
ordering instead; build the chain only if re-review cost recurs after the doc fix). (b) Work-model
probe precision (in flight on `feature/review-fixes`). (c) Migrating scriob itself (its wrapper
shrinks/disappears when it adopts the new knobs; follow-up, not this plan). (d) Any change to
`coverage_required` default (stays opt-in/false).

## Requirements Confidence

**Level:** High

**Why:** Every requirement traces to a concrete observed failure with the defective code
identified by line; the fixes were reviewed against both producer and consumer sites before
planning.

**Open assumptions / unknowns:**
- [ASSUMPTION: non-Python files, symbol-less Python files, and deleted files are classified
  `changes_unjudged` (the stem-fallback match is dropped — it is noise in both directions) |
  MED impact | user can override]
- [ASSUMPTION: `tests_dirs:` is a whitespace-separated top-level scalar (matches the hook's
  dependency-free column-0 YAML reader; a YAML list would need a new parser) | LOW impact |
  user can override]
- [ASSUMPTION: `test_command:` must contain a `{junit_xml}` placeholder; the hook substitutes
  its temp path and errors clearly when the placeholder is absent (explicit contract over
  magical flag injection) | MED impact | user can override]
- [ASSUMPTION: existing repos get build plans un-ignored via `update_gitignore` retired-entry
  removal on the next `init-product`/`doctor` run, with an advisory to `git add`; no forced
  auto-add | MED impact | user can override]

**What would raise confidence:** N/A.

## Status

<!-- views_enabled: checkboxes are derived from scope=gate-soundness change-log entries by
     regen-views at release; do not hand-edit. -->

- [ ] Chunk 01: Coverage gate honesty — `changes_unjudged`
- [ ] Chunk 02: test-evidence configurability — `test_command:` + `tests_dirs:`
- [ ] Chunk 03: Build plans are tracked artifacts
- [ ] Chunk 04: Cumulative-gate ordering guidance + plan-lifecycle note
Context: ALL FOUR CHUNKS BUILT AND CUMULATIVE-REVIEWED 2026-06-10 (checkboxes flip at
release via scope=gate-soundness change-log tags). Branch feature/gate-soundness off
origin/develop (ed2dcb6), 6 commits, cumulative Critic at b14f7b9: 0 blocking / 1 warning
(resolved doc-only post-review, gate re-verified satisfied) / 3 notes (1 fixed doc-only,
1 filed as TST-3E8V, 1 closed by reassessing CRT-8D2W). 1047 tests pass. PR-ready
(feature/gate-soundness → develop) — PR not yet created. Two declared deviations recorded
in ch.2 (shlex, not shell) and ch.3 (update-gitignore subcommand).

## Chunks

### Chunk 01: Coverage gate honesty — `changes_unjudged`

The F4a producer (`bin/test-reference-verify`) symbol-greps Python only, but the F4b consumer
(`lib/gates.py::verify_coverage`) compares the **whole** branch diff + untracked files against
`changes_referenced` — so configs, docs, fixtures, symbol-less `__init__.py`, and deletions fail
the gate by construction (scriob: 3 recurrences, then gate neutralized). Fix at both sites:

- **Producer** (`bin/test-reference-verify`): classify each changed file —
  *judged* (Python file or python-shebang script with ≥1 extracted symbol → appears in
  `changes_referenced` when referenced, else is a legitimate gap) vs *unjudged* (non-Python,
  Python with zero symbols, deleted in diff) → new evidence field `changes_unjudged` (sorted
  list). Drop the filename-stem fallback for non-Python files (noise both directions). Docstring
  updated to describe the contract.
- **Schema** (`lib/gates.py::_validate_evidence_schema` / `_EVIDENCE_*`): `changes_unjudged`
  optional list-of-str; absent ⇒ empty (back-compat with product-authored evidence and
  `executed`-level verifiers, which keep today's behavior).
- **Consumer** (`lib/gates.py::verify_coverage`): `missing = changed − referenced − unjudged −
  {files absent on disk}`. Unjudged files reported as a single informational stdout line
  (count + level disclaimer), never `missing-coverage`. Failure output unchanged for judged
  files.
- **Hook placeholder record** (`bin/prawduct-hook::cmd_test_evidence` base record): add
  `"changes_unjudged": []` so the pre-overlay record stays schema-complete.
- **Protocol prose**: `skills/critic/review-protocol.md` F4b/Goal-1 wording — confirm the
  Critic quotes only `missing-coverage:` stderr lines as findings; adjust only if it instructs
  otherwise (minimal diff; token-budget guardrails apply).

- **Type:** code
- **Done when:**
  1. Tests in `tests/test_reference_verifier.py` (classification: `.md`→unjudged, symbol-less
     `.py`→unjudged, deleted→unjudged, referenced/unreferenced Python unchanged) and the
     verify-coverage gate tests (unjudged+doc changes pass; judged-missing still exits 1;
     deleted file not missing; legacy evidence without the field keeps old behavior) pass with
     the full suite.
  2. /prawduct:critic run and blocking findings resolved.
  3. Committed; tagged change-log entry (`chunks=01 | scope=gate-soundness`).

### Chunk 02: test-evidence configurability — `test_command:` + `tests_dirs:`

`cmd_test_evidence` hardcodes `sys.executable -m pytest` from the repo root and the verifier
defaults to a single `tests/` dir — broken on uv-managed venvs, root-configless monorepos, and
multi-tree test layouts (scriob's entire wrapper exists for this).

- **Knobs** (top-level scalars in `project-state.yaml`, read via the existing column-0 reader):
  - `test_command:` — full canonical invocation containing `{junit_xml}`; when set, the hook
    runs it from the repo root instead of `sys.executable -m pytest`; missing placeholder
    → exit 2 with a message naming the contract. Extra CLI pytest args are rejected (exit 2)
    when `test_command` is set — the declared command IS the invocation.
    **Deviation (declared at build, Critic ch.2):** execution is `shlex.split` list-form, NOT
    `shell=True` as originally planned — the repo's subprocess-safety guardrail bans the shell
    (injection surface), and the contract is cleaner: shell composition belongs in a script the
    command points at. Substitution happens per-token after splitting; a missing executable is
    a clean exit-2.
  - `tests_dirs:` — whitespace-separated dirs (default `tests`); passed through to the verifier
    overlay.
- **Verifier** (`bin/test-reference-verify`): `--tests-dir` repeatable (`action="append"`,
  default `["tests"]`); discovery unions across dirs; one run covers all trees (kills the
  two-temp-file union dance).
- **Hook overlay**: pass each configured dir as a repeated `--tests-dir`.
- **Docs**: `templates/project-state.yaml` (if the template carries gate knobs — mirror however
  `coverage_required`/`base_branch` are documented there) + a line in
  `methodology/building.md` "Verify" or the existing test-evidence guidance naming the knobs.

- **Type:** code
- **Done when:**
  1. Tests: knob parsing, `{junit_xml}` substitution + missing-placeholder error, repeatable
     `--tests-dir` discovery union, default unchanged when knobs absent. Full suite passes.
  2. /prawduct:critic run and blocking findings resolved.
  3. Committed; tagged change-log entry (`chunks=02 | scope=gate-soundness`).

### Chunk 03: Build plans are tracked artifacts

The framework gitignores `.prawduct/artifacts/build-plan.md` (`lib/core.py::GITIGNORE_ENTRIES`)
while tracked `project-state.yaml` points `active_build_plan:` at it and `skills/pr/SKILL.md`
step 7 mandates retaining it through a gitflow release-pending window — a tracked pointer to a
gitignored file on every multi-clone repo (scriob PR #43 cross-clone regression). Worse,
`bin/prawduct-hook::_untrack_session_files` force-`git rm --cached`s it at every session start,
actively reverting any product that tracks its plan. A build plan is a durable, multi-session,
release-spanning artifact — not session state.

- Remove `.prawduct/artifacts/build-plan.md` from `GITIGNORE_ENTRIES` (`lib/core.py`) and from
  `_SESSION_GITIGNORED_PATHS` (`bin/prawduct-hook`) — the mirror-parity test
  (`tests/test_build_plan_resolution.py`) keeps them in sync.
- `lib/core.py::update_gitignore`: new retired-entries removal — drop the
  `.prawduct/artifacts/build-plan.md` line from existing `.gitignore`s (report via the existing
  `unignored` mechanism so `init-product`/`doctor` advise `git add`).
- Remove the entry from this repo's own `.gitignore`.
- Prose touchpoints: `methodology/planning.md` "Where Artifacts Live" (plans are tracked) only
  if it currently implies otherwise; scriob-shaped repos heal on next `doctor` run.
  **Deviation (declared at build, Critic ch.3):** "heal on next doctor run" required a new thin
  `prawduct-hook update-gitignore` subcommand — `init-product` early-exits on already-scaffolded
  repos, and session hooks must never edit a tracked file (the no-noise guarantee), so on-demand
  repair was the only sound delivery path. Doctor health-check 8 + onboard step 4 surface the
  `unignored` advice; `init_product.run` prints it in both text and `--json` modes.

- **Type:** code
- **Done when:**
  1. Tests: GITIGNORE_ENTRIES no longer contains the path; update_gitignore removes a
     pre-existing build-plan ignore line and reports it; untrack loop no longer touches build
     plans; parity test green. Full suite passes.
  2. /prawduct:critic run and blocking findings resolved.
  3. Committed; tagged change-log entry (`chunks=03 | scope=gate-soundness`).

### Chunk 04: Cumulative-gate ordering guidance + plan-lifecycle note

The natural loop (cumulative review → fix → verify-resolutions) can never satisfy
`check-cumulative-critic`; the rule "land all non-.md fixes, then run cumulative once, last" is
currently only learnable by paying a full re-review (scriob: ~4-10 min). And the
"don't repoint `active_build_plan` while the prior plan is release-pending" rule lives only in
the PR-merge flow, invisible at planning time.

- `lib/gates.py::check_cumulative_critic` `wrong-mode` stderr: append one sentence —
  verify-resolutions cannot certify the bundle; fix everything, commit, then run
  `/prawduct:critic cumulative` once, last.
- `skills/pr/SKILL.md` Step 2 (cumulative gate): add the sequencing rule (2-3 lines max;
  token budgets).
- `methodology/building.md` "Cumulative-Critic gate" paragraph: fold the sequencing into the
  existing prose (minimal diff).
- `methodology/planning.md` (Build Planning intro or Status guidance): one sentence — when
  authoring a new plan while the prior plan is release-pending (gitflow), leave
  `active_build_plan` pointing at the pending plan until the release ships (cross-ref
  pr/SKILL.md step 7).

- **Type:** cumulative-final
- **Done when:**
  1. Gate-message test updated/added; prose edits within token budgets; full suite passes.
  2. /prawduct:critic run (final + cumulative per Type) and blocking findings resolved.
  3. Committed; tagged change-log entry (`chunks=04 | scope=gate-soundness`).

## Verification Strategy

Beyond unit tests: exercise the real commands in a throwaway fixture repo — (ch.1/2) a two-tree
monorepo fixture where `prawduct-hook test-evidence record` + `verify-coverage` go green with
docs/config changes present and red when a judged Python file lacks any test reference;
(ch.3) `update_gitignore` on a `.gitignore` carrying the old entry, then confirm a tracked plan
survives a simulated session start. This repo itself (root pytest, knobs absent) is the
no-knob regression case — the suite and `prawduct-hook test-evidence record` must behave
identically before and after.
