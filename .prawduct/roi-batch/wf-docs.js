export const meta = {
  name: 'roi-batch-docs',
  description: 'Build the 5 docs/methodology ROI backlog fixes (MET-4K8Z, MET-1T5W, MET-8N2C, MET-2D9K, DOC-2W9P) into the working tree — methodology and documentation lanes in parallel. Build half only: no commits, no Critic.',
  phases: [
    { title: 'Build', detail: 'methodology-prose agent + documentation-paths agent, file-disjoint' },
  ],
}

const GUARDRAILS = `

HARD CONSTRAINTS — a SECOND workflow (code lane) is editing this same working tree concurrently:
- Edit ONLY the files in YOUR file set below. Touch nothing else (the code lane owns lib/, bin/, skills/, tests/).
- Do NOT git commit / git add / switch branches / stash. Leave changes uncommitted in the tree.
- Do NOT edit .prawduct/backlog.md, .prawduct/change-log.md, .prawduct/project-state.yaml,
  .prawduct/learnings*.md, or .prawduct/.session-handoff.md — the launching session reconciles those.
- Do NOT invoke /critic or any skill. The launching session runs the Critic afterward.
- Read each item's full entry in .prawduct/backlog.md before editing.`

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['items', 'filesChanged', 'changesMade', 'guardrailResult', 'summary'],
  properties: {
    items: { type: 'string', description: 'which backlog IDs this agent handled' },
    filesChanged: { type: 'array', items: { type: 'string' } },
    changesMade: { type: 'string', description: 'bullet list of edits, one per item' },
    guardrailResult: { type: 'string', description: 'token-budget / doc guardrail test result, or "n/a"' },
    summary: { type: 'string', description: 'any caveat for the cumulative Critic' },
  },
}

phase('Build')

const tasks = [
  {
    label: 'methodology (MET-4K8Z/1T5W/8N2C/2D9K)',
    prompt: `Make four prose fixes to methodology/. Read each backlog entry first.
1. MET-1T5W — add a short "Forward-references" paragraph to methodology/planning.md documenting the build-plan convention of prefixing a not-yet-created file path with the word "new" (e.g. new \`skills/foo/bar.md\`) so the Critic's ref-drift check treats it as a forward ref. Currently this is only in the build-plan template's inline comment.
2. MET-8N2C — methodology/planning.md (~line 118): change "the first item in its Done-when" to "prepended as step 0 in its Done-when (so existing step numbering is preserved across chunks with and without a foreign API)", matching the worked example's "step 0" wording a few lines below.
3. MET-2D9K — add a methodology/planning.md section paralleling the build-plan \`Visual change:\` field, so the prose documents it like the other build-plan fields.
4. MET-4K8Z — promote the "8-surface cascade -> anticipate token-budget pressure in chunk plans" pattern into methodology prose (planning.md or building.md, wherever chunk-planning guidance lives). It recurred again this session (token-budget guardrail tests bit on the waiver-pragma work), so it has earned promotion from observation to guidance.
YOUR FILE SET: methodology/planning.md, methodology/building.md ONLY.
CRITICAL — token-budget guardrails: methodology files have size-budget guardrail tests (grep tests/ for the building.md / review-protocol size assertions). After editing, RUN them. If a budget would bust, TRIM surrounding prose to fit — never weaken the budget test.
SCOPED TEST: run the methodology token-budget guardrail test(s) you find, -q.${GUARDRAILS}`,
  },
  {
    label: 'documentation (DOC-2W9P)',
    prompt: `Fix backlog item DOC-2W9P. Read its full entry first.
PROBLEM: documentation/post-sync-advisory-spec.md (around lines 197/218/276/296/434/435) and documentation/governance-tax-followups.md section 3 still illustrate the advisory/probe layout with retired file-sync paths (tools/lib/probes/..., tools/product-hook, prawduct-setup.py, run_sync).
FIX: repoint those illustrative paths to plugin-native equivalents — lib/advisory_store.py, hooks/hooks.json, bin/prawduct-hook — so the design archive matches today's plugin layout. These are internal design docs (not user-facing prose); keep the surrounding explanation intact, change only the stale paths.
YOUR FILE SET: documentation/post-sync-advisory-spec.md, documentation/governance-tax-followups.md ONLY.
SCOPED TEST: none (prose only). If you find a doc-path guardrail test, run it.${GUARDRAILS}`,
  },
]

const results = await parallel(tasks.map(t => () =>
  agent(t.prompt, { label: t.label, phase: 'Build', schema: SCHEMA })
))

log(`docs lane: ${results.filter(Boolean).length}/${tasks.length} agents done (uncommitted, in working tree)`)
return { lane: 'docs', results }
