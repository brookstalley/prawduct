export const meta = {
  name: 'roi-batch-code',
  description: 'Build the 4 code/test ROI backlog fixes (CRT-3M8Q, BLD-4Q9X, TST-2R7H, MIG-8C3V) into the working tree — file-disjoint, in parallel. Build half only: no commits, no Critic.',
  phases: [
    { title: 'Build', detail: 'one agent per fix: root-cause, fix, regression test, scoped pytest' },
  ],
}

const GUARDRAILS = `

HARD CONSTRAINTS — a SECOND workflow (docs lane) is editing this same working tree concurrently:
- Edit ONLY the files in YOUR file set below. Touch nothing else.
- Do NOT git commit / git add / switch branches / stash. Leave changes uncommitted in the tree.
- Do NOT edit .prawduct/backlog.md, .prawduct/change-log.md, .prawduct/project-state.yaml,
  .prawduct/learnings*.md, or .prawduct/.session-handoff.md — the launching session reconciles those.
- Do NOT invoke /critic or any skill. The launching session runs the Critic afterward.
- Run ONLY the scoped pytest file(s) named in your task — NEVER the full suite (other lanes'
  edits are in flight and would cause spurious failures). The launching session runs the full suite.
- Test discipline (Tests Are Contracts): add a regression test that FAILS before your fix and
  PASSES after. Fix the code, never weaken a test.
- Read the item's full entry in .prawduct/backlog.md before implementing.`

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['item', 'rootCause', 'filesChanged', 'testsAdded', 'scopedTestResult', 'summary'],
  properties: {
    item: { type: 'string' },
    rootCause: { type: 'string', description: 'one-sentence root cause' },
    filesChanged: { type: 'array', items: { type: 'string' } },
    testsAdded: { type: 'string', description: 'name(s) of regression test(s) added' },
    scopedTestResult: { type: 'string', description: 'the scoped pytest result line, e.g. "14 passed"' },
    summary: { type: 'string', description: 'what changed and any caveat for the cumulative Critic' },
  },
}

phase('Build')

const tasks = [
  {
    label: 'CRT-3M8Q',
    prompt: `Fix backlog item CRT-3M8Q (build half only).
PROBLEM: the build plan's per-chunk **Critic mode:** override is inert — /critic infers the mode and a plan-mandated mode (e.g. 'final') is silently ignored (observed running as inferred 'chunk').
FIX (preferred shape — testable, no reliance on Skill-tool $ARGUMENTS threading): make critic-mode inference honor the active build plan's CURRENT chunk **Critic mode:** field as a successive override. The logic lives in lib/critic_mode.py (and the 'infer-critic-mode' path in bin/prawduct-hook that calls it). When the active chunk declares a valid mode, return it with a mode_chosen_by rationale like "plan-override: <mode>". Then document the now-honored override in skills/critic/SKILL.md and skills/critic/review-cycle.md prose.
YOUR FILE SET: lib/critic_mode.py, bin/prawduct-hook, skills/critic/SKILL.md, skills/critic/review-cycle.md, tests/test_critic_mode_inference.py.
TEST: add a regression case in tests/test_critic_mode_inference.py — a plan whose active chunk says 'Critic mode: final' makes inference return 'final' with mode_chosen_by reflecting the plan override.
SCOPED TEST: python3 -m pytest tests/test_critic_mode_inference.py -q${GUARDRAILS}`,
  },
  {
    label: 'BLD-4Q9X',
    prompt: `Fix backlog item BLD-4Q9X (build half only).
PROBLEM: 'scope: null' in build-plan frontmatter is treated identically to 'key absent', so _detect_active_scope falls through to change-log inference and wrongly inherits a prior 'scope=' tag — silently overriding the author's explicit opt-out and flipping chunk checkboxes.
FIX: in lib/views.py, make _parse_build_plan_frontmatter_scope distinguish "key absent" from "key present with null/empty" (a sentinel, or a (present: bool, value: str|None) tuple). Have _detect_active_scope SKIP change-log inference when the key was explicitly null.
YOUR FILE SET: lib/views.py, tests/test_views.py.
TEST: add a regression case in tests/test_views.py — a plan with 'scope: null' PLUS a change-log containing a prior 'scope=' tagged entry must NOT inherit that scope (inference suppressed); contrast with key-absent which still infers.
SCOPED TEST: python3 -m pytest tests/test_views.py -q${GUARDRAILS}`,
  },
  {
    label: 'TST-2R7H',
    prompt: `Fix backlog item TST-2R7H (build half only — this one ADDS test coverage).
GOAL: pin that ONLY 'designer-handoff' Type skips the stop-hook Critic gate; the Types code / doc-only / cleanup / cumulative-final all FALL THROUGH to the default gate (gate still fires). Today only the explicit designer-handoff skip branch is tested, so a refactor broadening the skip-list (e.g. {"designer-handoff","doc-only"}) would silently regress.
FIRST: locate the gate-skip logic in bin/prawduct-hook (READ ONLY — do not edit it) and the existing test covering the designer-handoff skip, to mirror its fixture style.
YOUR FILE SET: the stop-gate test file you locate. Do NOT use tests/test_critic_mode_inference.py or tests/test_views.py (reserved for other lanes). If no clean home exists, create new tests/test_critic_gate_fallthrough.py.
TEST: add a parametrized TestNonHandoffTypesFallThroughToGate over the four non-handoff Types asserting the gate is NOT skipped.
SCOPED TEST: python3 -m pytest <the test file you added/edited> -q${GUARDRAILS}`,
  },
  {
    label: 'MIG-8C3V',
    prompt: `Fix backlog item MIG-8C3V (build half only).
PROBLEM: migrate's CLAUDE.md transform (apply_claude_anchor -> _drop_generator_comments in lib/migrate_plugin.py) leaves a double blank line at the top of the migrated file after stripping the framework generator comments.
FIX: collapse 3+ consecutive newlines to 2 in the assembled CLAUDE.md (or drop the blank line left adjacent to removed generator comments). Cosmetic, no semantic change.
YOUR FILE SET: lib/migrate_plugin.py, tests/test_plugin_migrate.py.
TEST: add a regression case in tests/test_plugin_migrate.py asserting the migrated CLAUDE.md has no leading double blank line (no triple-newline run; no double blank between the H1 and the first product section).
SCOPED TEST: python3 -m pytest tests/test_plugin_migrate.py -q${GUARDRAILS}`,
  },
]

const results = await parallel(tasks.map(t => () =>
  agent(t.prompt, { label: t.label, phase: 'Build', schema: SCHEMA })
))

log(`code lane: ${results.filter(Boolean).length}/${tasks.length} fixes built (uncommitted, in working tree)`)
return { lane: 'code', results }
