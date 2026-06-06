---
artifact: build-plan
version: 2
scope: work-model
depends_on: []
last_validated: null
---

# Build Plan — Work Model (catching undocumented requirements)

Implements the ship-now core of the work model. Design lineage: `docs/work-model.md` (kernel) →
`docs/work-model-spec.md` (spec) → `docs/work-model-delta.md` (delta vs. current prawduct, the
build-ready source of truth). Two independent reviews shaped it (`docs/work-model-review.md`).

**Problem.** A fluent agent can design a new domain model *in conversation* and flow it into code
with no requirements artifact, and prawduct never stops it — it polices requirement *loss* (Complete
Delivery) but not requirement *absence*.

**Success.** When a user introduces a domain term no artifact covers, an **external, deterministic**
pre-turn nudge surfaces it ("locate/write the parent before designing"). Proven by replaying the real
scriob prompt that triggered the original failure.

**Out of scope (deferred, each behind named evidence — see spec Part C).** The LLM-in-hook classifier;
the PreToolUse parent-coverage floor + seeded `boundary-patterns.md`; the Critic pre-code plan-review.

**Requirements confidence: High** on the ship-now core, except B3's *catch-efficacy*, which Chunk 1's
real-scriob replay test is designed to empirically resolve (it may show the deterministic diff is
insufficient → that is the evidence that unlocks the deferred LLM classifier).

## Status

- [x] Chunk 1: Catch logic (pure, no session risk). `lib/work_model_index.py` + tests, incl. the
  real-scriob replay. Proves/disproves the keystone before any live-hook wiring. **Critic mode:** chunk
- [ ] Chunk 2: Wiring (touches the live runtime). `prawduct-hook build-index` + `user-prompt-submit`
  subcommands; index at `.prawduct/.work-model-index.json` (gitignored); `hooks.json` UserPromptSubmit
  entry + SessionStart index build; `.prawduct/`-gate + fail-soft. **Critic mode:** chunk
- [ ] Chunk 3: Parent-map + prose. Extend `hooks/digest.py` with a dynamic capped parent-map; A1–A3
  prose (principles.md/CLAUDE.md §6 mirror clause, building.md tripwires, discovery.md sentence,
  session-digest.md one-liners under `test_token_budget`=3120); `vocabulary:` frontmatter convention.
  **Critic mode:** final

Context: Chunk 1 done — catch logic built; the real-scriob replay PROVES the deterministic catch fires
(belief/canonical/conflicting/sincerity), with honest false-positive noise documented (the evidence the
deferred LLM classifier is gated on). Critic (chunk): 0 blocking; 3 process warnings (stale evidence,
chunk-heading format, unset active_build_plan pointer) all addressed + verified. Next: Chunk 2 wiring,
on path A (deterministic-only).

## Chunk detail

### Chunk 1: Catch logic
- **Deliverable:** `lib/work_model_index.py` (pure functions, no I/O): `extract_vocabulary(text)`
  (conservative — markdown headings + bold + frontmatter `vocabulary:`), `build_index(texts)`,
  `salient_terms(prompt)`, `find_orphan_terms(prompt, index)`, `format_nudge(orphans)`. Plus
  `tests/test_work_model_index.py`.
- **Done when:**
  1. Unit tests cover extract/build/salient/orphan/format.
  2. **The real-scriob replay test** feeds the actual turn-7/8 prompt (belief/lie/sincerity/canonical/
     source) against a verification-domain index and asserts the nudge **fires** — and *records which
     terms it caught*. (Honest gate: if it can't fire without rigging the stoplist, that's the
     evidence the deterministic approach is insufficient.)
  3. A **false-positive characterization test**: a routine in-domain prompt yields few/no orphans —
     documenting the noise behavior in both directions (the make-or-break risk).
  4. Full suite green; `/prawduct:critic` final; reflection captured.
- **Risk:** the keystone may prove too blunt (jargon vs. concept). That outcome is *information*, not
  failure — it unlocks the deferred LLM classifier. Build honestly; don't tune the stoplist to pass.

### Chunk 2: Wiring
- **Deliverable:** thin `cmd_build_index` / `cmd_user_prompt_submit` in `bin/prawduct-hook` wrapping the
  lib; write/read `.prawduct/.work-model-index.json`; gitignore it; `hooks.json` UserPromptSubmit entry +
  SessionStart index build. Every new hook: gate on `.prawduct/` existence + fail-soft (try/except with
  `prawduct:allow prawduct/broad-except` — mirror `digest.py`).
- **Self-hosted-runtime caution:** these hooks govern THIS session. Verify each change doesn't disrupt
  the running session's governance before trusting it ("am I sawing the branch I'm on?", learnings).
- **Done when:** hook JSON-contract tests (orphan→nudge, clean→no injection, non-prawduct-repo→silent,
  error→fail-soft); suite green; Critic chunk; reflection.

### Chunk 3: Parent-map + prose
- **Deliverable:** `digest.py` appends a dynamic, capped parent-map (governing docs + 1-line scope) read
  from `.prawduct/artifacts/` + `project-state.yaml`; A1–A3 edits; frontmatter convention documented.
- **Done when:** parent-map cap test + `test_token_budget` stays green; principle/methodology edits land;
  suite green; Critic final; reflection.
