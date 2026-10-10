export const meta = {
  name: 'rework-fix-classification',
  description: 'Classify sampled rework edges as defect fix vs planned evolution (Sonnet, with an Opus agreement check)',
  phases: [{ title: 'Classify' }],
}
const SCHEMA = {
  type: 'object',
  properties: {
    edges: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          label: { type: 'string', enum: ['fix', 'evolution', 'unclear'] },
          severity: { type: 'string', enum: ['high', 'medium', 'low', 'n/a'] },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
          reason: { type: 'string' },
        },
        required: ['id', 'label', 'severity', 'confidence', 'reason'],
      },
    },
  },
  required: ['edges'],
}
const prompt = (f) => `You are classifying code changes for a research study. Read the file ${f} (use the Read tool; it is large, read it fully in parts if needed).

It contains several EDGEs. In each, a LATER change rewrote source lines that an EARLIER change had added. For each EDGE decide:

- "fix": the later change corrects something the earlier code got WRONG — wrong output, crash, data loss, broken edge case, security hole, a behaviour that did not do what it was meant to. A fix for a bug found in review, by a user, by a test, or by the author later all count.
- "evolution": the later change extends, refactors, renames, restructures, changes requirements, tunes, or adds features; the earlier code was not wrong for what it set out to do.
- "unclear": you genuinely cannot tell.

Judge from the diff and messages, not from keywords alone ("fix" in a message can mean a review nit; a prose message can describe a real bug). If the later change does both, label "fix" only if correcting wrong behaviour is a substantial part of it.
For "fix", give severity: high = silent wrong results, data loss/corruption, security, crash on a common path; medium = wrong behaviour on a plausible edge case; low = cosmetic/minor. For evolution/unclear use "n/a".
Return one entry per EDGE id, with a one-sentence reason. Do not run any code.`
// args: {dir, batches}: the `build_batches.py edges` output directory and its batch count (12 in the study).
const files = Array.from({ length: args.batches }, (_, i) => `${args.dir}/batch-${String(i).padStart(2, '0')}.txt`)
const jobs = files.map((f, i) => ({ f, model: 'sonnet', tag: `sonnet-${i}` }))
jobs.push({ f: files[0], model: 'opus', tag: 'opus-0' }, { f: files[5], model: 'opus', tag: 'opus-5' })
phase('Classify')
const out = await parallel(jobs.map(j => () =>
  agent(prompt(j.f), { label: j.tag, phase: 'Classify', schema: SCHEMA, model: j.model })
    .then(r => r && { tag: j.tag, model: j.model, edges: r.edges })))
return out.filter(Boolean)
