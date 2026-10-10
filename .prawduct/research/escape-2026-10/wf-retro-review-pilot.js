export const meta = {
  name: 'retro-review-pilot',
  description: 'Blind retro-review pilot: Sonnet reviews 28 items (Opus also on 8 calibration items), Opus verifies every finding',
  phases: [{ title: 'Review' }, { title: 'Verify' }],
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

For EACH index: trace the code. "real" = the scenario actually happens given the code (callers, guards, types). "not_real" = something prevents it (cite the line) or it is not a defect under the definition. "uncertain" = cannot be settled by reading. Several indices may describe the same defect; judge each on its own. Give the severity you would assign if real (else n/a).`
phase('Review')
const results = await pipeline(
  args.items,
  async (it) => {
    const models = it.calibrate ? ['sonnet', 'opus'] : ['sonnet']
    const rs = await parallel(models.map(m => () =>
      agent(review(it.item), { label: `review:${it.item}:${m}`, phase: 'Review', schema: FIND, model: m })
        .then(r => r && { model: m, ...r })))
    return rs.filter(Boolean)
  },
  async (reviews, it) => {
    const all = reviews.flatMap(r => r.defects.map(d => ({ ...d, model: r.model })))
    if (!all.length) return { item: it.item, reviews, defects: [], verdicts: [] }
    const v = await agent(verify(it.item, all), { label: `verify:${it.item}`, phase: 'Verify', schema: VERDICT, model: 'opus' })
    return { item: it.item, reviews, defects: all, verdicts: v ? v.verdicts : null }
  },
)
return results
