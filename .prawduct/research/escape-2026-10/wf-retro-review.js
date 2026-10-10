export const meta = {
  name: 'retro-review',
  description: 'Opus blind review of make_items.py items with Opus verification, plus optional catch-class labelling (args: root, items, catchFiles); the study ran it for wave 1 and wave 2',
  phases: [{ title: 'Review' }, { title: 'Verify' }, { title: 'CatchClass' }],
}
const RUBRIC = `A DEFECT is code in this diff that, on a plausible input or state, produces wrong output, loses or corrupts data, crashes, hangs, leaks or opens a security hole, or silently reports success for something that failed.
Each finding: file:line in the diff; a concrete failure scenario (inputs or state -> what happens -> what should happen); severity high (silent wrong results, data loss/corruption, security, crash on a common path) or medium (wrong behaviour on an edge case a user or caller would plausibly hit).
NOT defects: style, naming, docs, refactors, performance without a correctness effect, speculative "might" findings without a concrete scenario, anything this diff did not introduce or change. A missing test is a test_gap, never a defect.`
const FIND = {
  type: 'object',
  properties: {
    defects: { type: 'array', items: { type: 'object', properties: {
      location: { type: 'string' }, severity: { type: 'string', enum: ['high', 'medium'] },
      scenario: { type: 'string' } }, required: ['location', 'severity', 'scenario'] } },
    test_gaps: { type: 'array', items: { type: 'string' } },
  },
  required: ['defects', 'test_gaps'],
}
const VERDICT = {
  type: 'object',
  properties: { verdicts: { type: 'array', items: { type: 'object', properties: {
    index: { type: 'integer' }, verdict: { type: 'string', enum: ['real', 'not_real', 'uncertain'] },
    severity: { type: 'string', enum: ['high', 'medium', 'n/a'] }, why: { type: 'string' } },
    required: ['index', 'verdict', 'severity', 'why'] } } },
  required: ['verdicts'],
}
const CATCH = {
  type: 'object',
  properties: { edges: { type: 'array', items: { type: 'object', properties: {
    id: { type: 'string' },
    is_defect: { type: 'boolean' },
    earliest_catch: { type: 'string', enum: ['code_review', 'unit_test', 'integration_test', 'production_only'] },
    domain: { type: 'string', enum: ['internal_logic', 'external_library_or_api', 'config_or_deploy', 'concurrency_or_distributed', 'data_or_schema', 'ui', 'other'] },
    why: { type: 'string' } }, required: ['id', 'is_defect', 'earliest_catch', 'domain', 'why'] } } },
  required: ['edges'],
}
const ROOT = args.root
const review = (item) => `You are reviewing one code change for correctness defects, as part of a research study.

Directory: ${ROOT}/${item}/
- change.diff — the change to review (against its parent).
- tree/ — the full source after the change, for context. Read and grep it as needed to understand callers, types and invariants.

Do not run, build or test anything, and do not modify any file. Read only inside ${ROOT}/${item}/.

${RUBRIC}

Be rigorous and concrete: trace the actual code paths. Report every real defect you find; report none if there are none. Precision matters as much as recall — a finding you cannot back with a concrete scenario should not be reported.`
const verify = (item, defects) => `You are independently verifying reported defects in one code change, for a research study. Reviewers are often wrong; your job is to check each claim against the code.

Directory: ${ROOT}/${item}/ — change.diff is the change, tree/ is the full source after it. Do not run anything or modify any file. Read only inside that directory.

Defect definition:
${RUBRIC}

Reported defects (index: location — severity — scenario):
${defects.map((d, i) => `${i}: ${d.location} — ${d.severity} — ${d.scenario}`).join('\n')}

For EACH index: trace the code. "real" = the scenario actually happens given the code (callers, guards, types). "not_real" = something prevents it (cite the line) or it is not a defect under the definition. "uncertain" = cannot be settled by reading. Give the severity you would assign if real (else n/a).`
const catchPrompt = (f) => `Research study. Read the file ${f} fully (it is large; use the Read tool in parts). It holds EDGEs: in each, a LATER change corrected code that an EARLIER change had added, with the later change's messages, its diff, and a classifier's one-line summary of the defect.

For each EDGE id decide:
- is_defect: was the earlier code genuinely wrong (not a requirement change)? If false, still fill the other fields with your best guess.
- earliest_catch: the cheapest practice that would most plausibly have caught the defect BEFORE merge:
  code_review = a careful reader of the earlier diff plus the repo could see it without running anything;
  unit_test = a test of the code in isolation with fakes/mocks would have failed;
  integration_test = it only shows when running against the real dependency, service, database, library version, deploy config or multiple processes;
  production_only = it needed real traffic, real data, scale, timing or user behaviour to surface.
- domain: where the defect lives.
Be honest: if a careful reviewer would have needed knowledge of an external system's runtime behaviour that is not in the repo, it is not code_review. One-sentence why. Do not run anything.`
phase('Review')
const reviews = pipeline(
  args.items,
  (it) => agent(review(it), { label: `review:${it}`, phase: 'Review', schema: FIND, model: 'opus' }),
  async (r, it) => {
    if (!r) return { item: it, defects: null, verdicts: null }
    if (!r.defects.length) return { item: it, defects: [], test_gaps: r.test_gaps, verdicts: [] }
    const v = await agent(verify(it, r.defects), { label: `verify:${it}`, phase: 'Verify', schema: VERDICT, model: 'opus' })
    return { item: it, defects: r.defects, test_gaps: r.test_gaps, verdicts: v ? v.verdicts : null }
  },
)
const catches = parallel(args.catchFiles.map((f, i) => () =>
  agent(catchPrompt(f), { label: `catch-${i}`, phase: 'CatchClass', schema: CATCH, model: 'opus' })))
const [rv, cc] = await Promise.all([reviews, catches])
return { reviews: rv, catchclass: cc.filter(Boolean).flatMap(c => c.edges) }
