export const meta = {
  name: 'rework-cause-classification',
  description: 'Classify why 127 evolution rework edges happened (planned / late requirement / refactor / environment surprise), Opus',
  phases: [{ title: 'Classify' }],
}
const SCHEMA = {
  type: 'object',
  properties: { edges: { type: 'array', items: { type: 'object', properties: {
    id: { type: 'string' },
    cause: { type: 'string', enum: ['planned_next_step', 'late_requirement', 'refactor_cleanup', 'environment_surprise', 'unclear'] },
    avoidable_by_discovery: { type: 'string', enum: ['yes', 'no', 'unclear'] },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    why: { type: 'string' } },
    required: ['id', 'cause', 'avoidable_by_discovery', 'confidence', 'why'] } } },
  required: ['edges'],
}
const prompt = (f) => `Research study on why code gets rewritten. Read the file ${f} fully (use the Read tool, in parts if needed). It holds EDGEs. In each, a LATER change rewrote source lines an EARLIER change had added, within 30 days. These edges were already judged NOT to be bug fixes: the earlier code was not wrong for what it set out to do. Your job is to say WHY it was rewritten.

cause:
- planned_next_step: the rewrite continues work that was already intended when the earlier code was written: the next phase, chunk or milestone of a known plan, filling in a deliberate stub, an anticipated extension.
- late_requirement: a need, constraint, use case, consumer, scale, policy or behaviour that surfaced AFTER the earlier code landed, and that would have changed how the earlier code was designed had it been known then (for example "it must also handle X", "users actually need Y", "this must work for Z too", a contract change forced by a new consumer).
- refactor_cleanup: restructuring, renaming, deduplication, moving or tidying with no change in what is required.
- environment_surprise: an external system, library, platform or deploy environment behaved differently from what the earlier code assumed (not a logic bug, but a wrong assumption about the outside world).
- unclear: genuinely cannot tell.

avoidable_by_discovery: could a reasonable up-front requirements/discovery conversation (asking about users, scale, environments, consumers, constraints before building) plausibly have surfaced what drove this rewrite, so the earlier code would have been built right the first time? "yes" only when the driver was knowable in principle before building. planned_next_step and refactor_cleanup are normally "no".

Judge from the diffs and messages together. Do not reward or penalise a commit-message style: a message naming a plan or chunk is not by itself proof the rewrite was planned, and a plain message is not proof it wasn't. One-sentence why per edge. Do not run anything.`
// args: {dir, batches}: the `build_batches.py cause` output directory and its batch count (10 in the study).
const files = Array.from({ length: args.batches }, (_, i) => `${args.dir}/batch-${String(i).padStart(2, '0')}.txt`)
phase('Classify')
const out = await parallel(files.map((f, i) => () =>
  agent(prompt(f), { label: `cause-${i}`, phase: 'Classify', schema: SCHEMA, model: 'opus' })))
return out.filter(Boolean).flatMap(r => r.edges)
