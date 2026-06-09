<!-- Build Plan: review-fixes
     Source: full-framework review (2026-06-09 session) — three parallel review agents
     (methodology, skills, hooks/lib) + main-session verification of the two
     highest-impact code claims. The remaining (lower-value) findings were filed
     to .prawduct/backlog.md in the same session; this plan covers only the
     highest-value fixes. For HOW to build, read `/prawduct:building` first.
-->
---
artifact: build-plan
version: 2
scope: review-fixes
depends_on: []
last_validated: 2026-06-09
---

## Requirements Confidence

**Level:** Medium

**Why:** Chunks 1 and 3 fix verified, reproduced bugs (High on their own); Chunks 2 and 4 each embed one design decision the user has not yet confirmed.

**Open assumptions / unknowns:**
- [ASSUMPTION: the work-model probe stays enabled and is fixed via precision work (corpus widening + common-English floor + firing threshold) rather than being removed outright | MED impact | user can override]
- [ASSUMPTION: the session-digest/CLAUDE.md duplication is resolved by a slim digest variant emitted when the governed repo is the prawduct framework itself — product repos (thin-anchor CLAUDE.md) keep the full digest, which is their only carrier of framework defaults | MED impact | user can override toward trimming the framework CLAUDE.md instead]
- [ASSUMPTION: Gate 3 result caching (TTL'd `gh pr list` cache) is deferred to backlog item STH scope; the no-changes short-circuit alone removes the per-turn network call for the common case | LOW impact | user can defer]
- [ASSUMPTION: the `pyproject.toml` version drift (2.0.15 vs VERSION 2.0.17) is folded into Chunk 1 as a one-line sync | LOW impact]

**What would raise confidence:** User confirmation (or veto) of the two MED-impact assumptions above before Chunks 2 and 4 begin.

## Status

- [x] Chunk 1: Hot-path correctness fixes (core.py path, Gate 3 network call, porcelain parsing)
- [x] Chunk 2: Work-model probe precision
- [ ] Chunk 3: Review-gate soundness (PR-5K8D fileset + Critic marker placement)
- [ ] Chunk 4: Always-loaded context dedup (framework-repo slim digest)
Context: Chunk 1 built on `feature/review-fixes` (2026-06-09): all four fixes in, 1037 tests pass, 17 new regression tests. Timing evidence for the Gate 3 short-circuit: a no-change `stop` on a feature branch in a scratch repo completes in 0.29s wall with no `gh` invocation (recording-mock test pins the absence of the call). Critic (final) found one BLOCKING — the `active_build_plan` pointer in project-state.yaml was written repo-relative but resolves `.prawduct/`-relative, silently disabling plan governance; fixed, and the un-blinded ref-verifier then caught a backticked retired-path mention in this plan (also fixed). Chunk 2 built same day (Critic chunk-mode x2: pass, then 1 warning + 2 notes, all resolved — count drift fixed, sentence-boundary determiner reset added, wordlist license posture recorded in `lib/common_words.py`): frequency floor is the top-4,000 of the google-10000-english list (not "a few KB" — the observed false-positive term *efficiency* ranks #3283, forcing the cutoff; 30KB accepted and documented in `lib/common_words.py`), plus firing threshold and corpus widening; 14 new tests, 1051 pass; all four observed false-positive prompt classes verified silent live against this repo's hook, "add OAuth login to the settings page" still fires. Two extra precision bugs found and fixed during build: contraction tokens minting orphan non-words ("let's" -> "let'"), and requirement verbs reporting themselves as the orphan ("extend X" flagging *extend*). Next: Chunk 3 (review-gate soundness; PR-5K8D + CRT-6F2N promoted in).

## Scaffolding

Not applicable — existing repo; no new project initialization, dependencies, or test infrastructure. `pytest` from the repo root runs the full suite.

### Verification Strategy

Beyond tests: exercise the hooks as the harness does — run `bin/prawduct-hook user-prompt-submit` / `stop` / `clear --session-start` against this repo and confirm injected output and latency by inspection (Chunk 1 and 2 acceptance criteria name the specific probe prompts).

## Project Structure

Unchanged — fixes land in existing modules (`lib/`, `bin/prawduct-hook`, `hooks/digest.py`, `skills/`, `methodology/`). Tests go in `tests/` (structural tests enforce this).

## Build Chunks

### Chunk 1: Hot-path correctness fixes

- **Description:** Fix the three verified bugs in the enforcement layer, plus the version-drift one-liner.
  1. **`lib/core.py` path depth** — `FRAMEWORK_DIR` uses `parent.parent.parent` (the retired file-sync three-level tools layout's depth) and resolves one level above the repo; `TEMPLATES_DIR` points at a nonexistent path and `PRAWDUCT_VERSION` silently reads `"dev"` (verified). Fix to `parent.parent`; remove the now-dead workaround/fallback in `lib/init_product.py` (its `except OSError` fallback currently falls back to the broken value); keep the flat-API exports working (`lib/__init__.py`, contract-pinned by `tests/test_lib_lazy_imports.py`).
  2. **Stop-hook Gate 3 network call** — `bin/prawduct-hook` cmd_stop runs `gh pr list` on every assistant turn on any feature branch even with zero session changes, because the gate is conditioned only on `not doc_only` and `doc_only` is False when `has_changes` is False (verified). Short-circuit Gate 3 on `not has_changes`.
  3. **Porcelain quoted-path parsing** — `lib/gitstate.py` parses `git status --porcelain` with `line.split()[-1]`, mangling git-quoted paths containing spaces and rename (`R old -> new`) lines; a doc-only session touching `my doc.md` fails the doc-only classification and can be falsely blocked by the Critic/reflection gates. The correct parsing (quote-stripping, `->` handling) already exists in `lib/gates.py` (`_classify_trivial_change` area) — extract a shared helper and use it in all three `gitstate.py` parse sites.
  4. **`pyproject.toml`** version `2.0.15` → sync with `VERSION` (2.0.17).
- **Depends on:** none
- **Artifacts consumed:** this plan; review findings recorded in the session transcript and backlog items
- **Deliverables:** edits to `lib/core.py`, `lib/init_product.py`, `lib/gitstate.py`, `bin/prawduct-hook`, `pyproject.toml`; a shared porcelain-parse helper (location: `lib/gitstate.py` or `lib/gates.py`, whichever avoids an import cycle)
- **Tests:** regression test per bug: (a) `FRAMEWORK_DIR`/`TEMPLATES_DIR`/`PRAWDUCT_VERSION` resolve correctly from the installed layout (extend `tests/test_lib_lazy_imports.py` or a new module); (b) cmd_stop makes no `gh` subprocess call when the session has no changes (subprocess mock); (c) porcelain parsing handles quoted space-paths and renames in `git_has_session_changes` / `_session_changes_are_doc_only` / `_get_session_changed_files` — the quoted-path case currently has zero coverage.
- **Acceptance criteria:** full suite passes; `python3 -c "import lib.core; print(lib.core.PRAWDUCT_VERSION)"` prints the real version (not `dev`); a no-changes `stop` invocation on a feature branch completes with no network call (verify by mock and by timing); a doc-only change to a space-containing `.md` path classifies as doc-only.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run (inference picks `chunk`) and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 2: Work-model probe precision

- **Description:** The UserPromptSubmit work-model probe (`lib/work_model_index.py` + the hook's user-prompt-submit path) flags ordinary English as "terms not found in any governing artifact" — observed firing on "thanks, looks good"-class prompts and on this review session's own prompts (e.g. flagging *efficiency, improve, quality, performance*, and "+644 more" on harness notifications). Each misfire injects ~80 tokens of tripwire text, training the model to ignore the one real catch. Fix precision:
  1. **Widen the vocabulary corpus** beyond artifact headings/bold/frontmatter — include `CLAUDE.md`, `docs/`, and `methodology/` headings so framework-domain words stop reading as orphans.
  2. **Add a common-English frequency floor** — an embedded small wordlist (few KB) so high-frequency English words (*thank, look, good, again, typo, improve, development, …*) are never flagged regardless of corpus.
  3. **Raise the firing threshold** — emit the warning only when the prompt is requirement-shaped (imperative build/add/implement-class verbs present) or when ≥2 non-common orphan terms co-occur; never fire on prompts that are questions/acknowledgments.
  4. **Measure precision** — `tests/test_work_model_index.py` pins mechanics but not false-positive rate; add a precision test over a fixture corpus of ~15 conversational prompts (must produce zero warnings) and ~5 genuine new-requirement prompts (must still fire).
- **Depends on:** none (parallel-safe with Chunk 1; commit order per plan)
- **Artifacts consumed:** this plan; `documentation/` work-model specs (`docs/work-model.md`, `docs/work-model-enforcement.md`) for the probe's intended contract
- **Deliverables:** edits to `lib/work_model_index.py` and the user-prompt-submit path in `bin/prawduct-hook`; new `lib/common_words.py` (or a data file under `lib/`) for the frequency floor; extended tests in `tests/test_work_model_index.py`
- **Tests:** precision fixture corpus (see Description item 4); corpus-widening unit tests; threshold-behavior tests (1 orphan + non-imperative → silent; 2 orphans → fires; imperative + 1 orphan → fires)
- **Acceptance criteria:** the three observed false-positive prompts from this session produce no warning; a genuine undocumented-requirement prompt ("add OAuth login to the settings page") still fires; full suite passes
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 3: Review-gate soundness

- **Description:** Two governance-gate fixes from the review:
  1. **PR-5K8D (promoted from backlog)** — `check-pr-doc-only` treats `skills/*.md` as docs, but fork-skill prose is behavioral logic (this repo's own learning), so governance-logic changes can skip the independent PR reviewer. Align the doc-only fileset with the trivial gate's protected paths (`skills/`, `methodology/`, `templates/`, `CLAUDE.md` are never doc-only); update the Step 1b note in `skills/pr/SKILL.md`; tests in `lib/coverage.py`'s test module pin the new bounds.
  2. **CRT-6F2N (promoted from backlog)** — `skills/critic/SKILL.md` step 1 runs `critic-begin` before the `Type: designer-handoff` early exit is ruled out, so a designer-handoff invocation leaves `.critic-active` set until the 30-minute TTL expires (benign but wrong by design). Either move `critic-begin` after the designer-handoff check or pair the early exit with an explicit `critic-end` — prefer whichever keeps the skill's step numbering stable. Check `tests/test_critic_skill_metadata.py` and `tests/test_critic_session_guard.py` for pinned step structure.
- **Depends on:** none
- **Artifacts consumed:** this plan; backlog item PR-5K8D (refs: `skills/pr/SKILL.md`, `lib/coverage.py`); `skills/critic/review-cycle.md` (designer-handoff contract)
- **Deliverables:** edits to `lib/coverage.py` (or wherever `check-pr-doc-only` resolves), `skills/pr/SKILL.md`, `skills/critic/SKILL.md`; tests
- **Tests:** doc-only check returns non-doc-only for a diff touching `skills/x/SKILL.md`; still doc-only for `docs/*.md`-only diffs; marker-lifecycle test if the critic-begin ordering is testable at the hook layer (else the skill prose change is pinned by the existing metadata tests)
- **Acceptance criteria:** a `skills/`-touching branch can no longer take the doc-only fast path (gate exercised in test); designer-handoff invocation leaves no `.critic-active` marker; full suite passes; backlog updated at chunk close via `/prawduct:backlog update PR-5K8D status=shipped closed-by=review-fixes-ch3` and `update CRT-6F2N status=shipped closed-by=review-fixes-ch3`
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 4: Always-loaded context dedup (framework-repo slim digest)

- **Type:** cumulative-final
- **Description:** In this repo the always-injected session digest (~1.4k tokens, re-injected on every compaction) duplicates 40–50% of the always-loaded CLAUDE.md nearly 1:1 (principles roster, Critic/Stop explanation, attribution rule, waiver pragma). The digest is the legitimate and only carrier of those rules for *product* repos (thin-anchor CLAUDE.md), so the fix must not gut it: per the plan-level assumption, `hooks/digest.py` detects when the governed repo is the prawduct framework itself (e.g. `.claude-plugin/plugin.json` present at repo root with `name: prawduct`, or equivalent unambiguous marker) and emits a slim variant — pointers to CLAUDE.md sections instead of restated rules — keeping the full digest for every product repo. Enumerated surfaces (cascade): `hooks/digest.py`, `methodology/session-digest.md` (document the two variants), the digest token-budget tests (`tests/test_plugin_methodology_digest.py`, `tests/test_v5_methodology.py` budgets), and `tests/test_briefing_functions.py` if briefing asserts digest presence. Out of scope (recorded descope): trimming redundancy *within* CLAUDE.md/methodology files — that's the filed methodology-redundancy backlog item.
- **Depends on:** Chunk 1 (avoid concurrent edits to hook entry points)
- **Artifacts consumed:** this plan; `methodology/session-digest.md`
- **Deliverables:** edits to `hooks/digest.py`, `methodology/session-digest.md`, budget tests
- **Tests:** slim variant emitted in a fixture framework repo; full variant emitted in a fixture product repo; slim-variant token budget pinned (~≤50% of full); existing digest tests updated with rationale per the renegotiate-the-contract learning
- **Acceptance criteria:** SessionStart in this repo injects the slim digest (verify by running `hooks/digest.py` here); a scaffolded product fixture still gets the full digest verbatim; full suite passes
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic final` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status
  4. `/prawduct:critic cumulative` run against `merge-base...HEAD` and blocking findings resolved — the structural gate for `/prawduct:pr create`

## Early Feedback Milestone

**Milestone chunk:** Chunk 1
**What the user can do:** Immediately feel the difference in-session — no `gh` network stall at turn end, correct version in the banner path, and (after Chunk 2) prompts free of false-positive work-model warnings.

## Governance Checkpoints

**Commit & PR cadence:** Commit per chunk after `/prawduct:critic` passes; PR via `/prawduct:pr` after Chunk 4's `final` AND `cumulative` reviews pass. Feature branch off develop.

- After Chunk 1: quick trajectory check — confirm the shared porcelain helper didn't create an import cycle and hook latency didn't regress.
- After Chunk 4: cumulative Critic against `merge-base...HEAD` (the `/pr create` gate).
