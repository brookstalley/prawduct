---
artifact: build-plan
version: 2
scope: governance-prose-diet
depends_on:
  - artifact: architecture
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms (the plan strengthens the statement of this invariant; it changes no mechanism)"
      - "authority fails closed; advice fails soft → conforms (no gate semantics change; prose only)"
      - "local-first governance coordination → inapplicable because this plan touches no runtime surface"
      - "the plugin writes nothing into a governed repo except its own state → inapplicable because this plan edits framework files in the framework repo"
last_validated: 2026-07-26
---

## Requirements Confidence

**Level:** Medium

**Why:** The problem is measured, not inferred — every hard rule is stated on 4-7 surfaces,
CLAUDE.md is 190 lines against its own ~150-line check, and the two most load-bearing
methodology files sit within 10 tokens of their ceilings. What is *not* certain is which
restatements are load-bearing. Chunk 03 is the judgment-heavy one; 01, 02, and 04 are
mechanical.

**Open assumptions / unknowns:**

- `[ASSUMPTION: cutting a rule from N surfaces to one canonical home plus pointers will not
  degrade adherence, because the gates — not the repetition — are what bind | HIGH impact |
  user can veto; this is the central bet of the whole plan]`
  Supporting evidence: "read building.md before code" is stated on 5 surfaces and is still
  named the #1 governance failure, so the 5th restatement is demonstrably not what works.
- `[ASSUMPTION: architecture prose leaving CLAUDE.md belongs in .prawduct/artifacts/architecture.md,
  not plugin/docs/ | MED impact | user can override]`
  Forced by mechanism, not taste: `_work_model_corpus_paths` (`plugin/bin/prawduct-hook`:3555) globs
  *top-level* `docs/`/`methodology/`, neither of which exists in this repo, so the corpus here
  is `.prawduct/artifacts/*.md` + `CLAUDE.md`. Moving prose to `plugin/docs/` would drop its
  vocabulary from the work-model index and start firing the orphan-term tripwire on terms that
  are currently known.
- `[ASSUMPTION: the full session digest must stay self-sufficient; only the slim digest may
  dedupe against this repo's CLAUDE.md | HIGH impact | user can correct]`
  Products receive `session-digest.md` while their CLAUDE.md is a thin anchor
  (`plugin/lib/init_product.py`:153), so a rule removed from the full digest reaches no product at
  all (learnings: "a new framework-wide DEFAULT must land in the session digest").

**What would raise confidence:** Chunk 03 landing with a clean Critic pass — it is the only
chunk where a removal could silently drop a binding rule.

## Status

<!-- views_enabled: true — these checkboxes are a DERIVED VIEW (lib/views.py). Do not hand-flip.
     Each chunk lands a change-log entry tagged `chunks=NN | scope=governance-prose-diet` with
     NO `status=` — that is the normal release-pending state, and the checkbox correctly stays
     `[ ]` until the work releases. `status=shipped` means RELEASED, not chunk-complete; it is
     the release that stamps it and `regen-views` that flips the box. The `Context:` line below
     is author-curated and regen never touches it — that is where chunk progress is recorded. -->

- [ ] Chunk 01: CLAUDE.md diet — architecture out, emphasis-escalation out, line-count guard in
- [ ] Chunk 02: The two session digests — Opus-5 alignment, slim dedupe, sentence density
- [ ] Chunk 03: Cross-surface rule consolidation — one canonical home per rule
- [ ] Chunk 04: Ratchet the token budgets down; land the deferred Goal 4 document-size check

Context: Plan written 2026-07-26 on `feature/governance-prose-diet` (off develop). Parents:
DOC-8L3F (CLAUDE.md line count), MET-7R4J (cross-surface redundancy residue), plus the
Opus-5 prompting alignment the owner requested.

**Chunk 01 complete** (`26534ec`) — CLAUDE.md 190 → 150 lines, 3,043 → 1,617 est tokens;
always-loaded payload 3,573 → 2,147. Critic `chunk` + `verify-resolutions`: 0 blocking,
0 warnings. Carried forward into Chunk 02: one NOTE — the `LIMIT = 150` comment in
`tests/test_v5_methodology.py` cites `plugin/methodology/building.md:83` by line number, which
Chunk 04 will itself invalidate; restate it in the quoted-heading form the class docstring
already uses.

**Chunk 02 complete** — three opus-5 edits landed in both digests; full-digest stance
consolidated 9 bars → 8; slim stance went from a run-on paragraph to 7 bullets; both dropped the
`STOP … ANY code` caps (MET-7R4J sub-item 2). Chunk 01's carried NOTE discharged. Critic `chunk`:
0 blocking, 1 warning, 3 notes — all resolved; `verify-resolutions` confirmed all four and raised
two prose warnings on the fix delta (a 11-vs-12 disagreement between records, and a provenance
claim the cited file contradicted), both corrected before commit. Digests grew slightly (1,589 →
1,661; 530 → 562) — this chunk bought readability, not shrinkage. Always-loaded now **2,183**
(CLAUDE.md 1,621 + slim 562), down from 3,573.

**Chunk 03 complete** — the reverse gap adjudicated (both rules promoted to the slim digest) and
co-load duplicates removed from five surfaces (six touched; the slim digest is additions-only).
`review-protocol.md` 3,526 → 3,497 (ceiling 3,530) and `building.md` 4,591 → 4,546 (ceiling
4,600); `critic/SKILL.md` 1,771 → 1,609. Always-loaded rose 2,183 → **2,272**, entirely from the
adjudication's +89 — the one deliberate wrong-way move in this plan. Critic `chunk`: 0 blocking,
2 warnings, 1 note, all three resolved. It caught the pass keeping the *less* accurate copy of the
mode-resolution rule, and a five-vs-six surface-count disagreement between the plan and the
change-log — the same records-from-memory defect class as Chunk 02's 11-vs-12, recurring on the
very next chunk despite the learning committed in `de2278e`.

Carried forward into Chunk 04:
- The Goal 4 draft is at `scratchpad/goal4-document-size.md`, rescued from the previous session's
  scratchpad before it aged out. The bullet swap is +17 exactly (59 → 76); composing it and
  measuring the whole file gives **3,513, i.e. 17 tokens of margin** under the 3,530 ceiling —
  real but thin, so any rewording of the draft must be re-measured on the composed file. (Adding
  the bullet delta to the file estimate gives 3,514/16: close, but two truncated estimates summed
  is not a measurement. Same distinction the sentence above makes, one level up.)
- The ratchet must set each ceiling from the **post-Chunk-04** actual, not from these numbers, or
  it will block its own check.

Next: Chunk 04 — the budget ratchet and the deferred Goal 4 check.

## Problem, Success, Scope

**Problem.** The always-loaded governance payload is 3,617 tokens (CLAUDE.md 3,043 + slim
digest 574) and restates every hard rule 4-7 times. A `final` Critic review loads ~26,000
tokens of protocol before reading one line of diff. The repetition is not free — it is paid
on every session — and it is not working: the most-repeated rule guards the failure the
framework calls its #1.

**Success.**
1. CLAUDE.md project content ≤ 150 lines, guarded by a test.
2. Each of the 12 measured hard rules has exactly one canonical statement; other surfaces
   point rather than restate.
3. The three Opus-5 alignment edits are landed, including the Goal 4 document-size check that
   had no headroom.
4. Token-budget ceilings in `tests/test_v5_methodology.py` move **down** to the new actuals —
   the diet is locked in, per MET-7R4J.
5. Full suite green; no gate semantics change.

**Out of scope** (named, not silently dropped):
- `plugin/docs/runbook-authoring.md` (21,663 tokens — the single largest doc). On-demand,
  read only when authoring runbooks. A separate diet if the owner wants one.
- `.prawduct/learnings.md` compaction (13,133 tokens, loaded by every `final` review). This
  is MET-6W3J and touches accumulated wisdom — different risk class, different item.
- Skill files: `backlog` (5,733), `janitor` (5,318 — JNT-9R2K), `doctor` (4,067), `pr` (3,840).
- The `effort:` experiment on `agents/critic-reviewer.md` — needs a measured sweep, not prose.

## Surfaces This Plan Touches

<!-- planning.md: enumerate up front; several carry token-budget guardrail tests, so the trim
     is anticipated rather than discovered at chunk close (which is exactly what happened on
     the first pass at this work). -->

| Surface | Tokens | Guard |
|---|---|---|
| `CLAUDE.md` | 3043 | none yet — Chunk 01 adds one |
| `plugin/methodology/session-digest.md` | 1721 | digest pointer tests |
| `plugin/methodology/session-digest-slim.md` | 574 | pointer tests + 10,000-char inline limit |
| `plugin/methodology/building.md` | 4591 | **budget <4600** |
| `plugin/skills/critic/review-protocol.md` | 3526 | **budget <3530** |
| `plugin/skills/critic/review-cycle.md` | 4206 | budget |
| `plugin/skills/critic/SKILL.md` | 1771 | budget |
| `plugin/agents/critic-reviewer.md` | 833 | — |
| `plugin/skills/pr/SKILL.md`, `pr/review-protocol.md` | 3840 / 2447 | — |
| `plugin/docs/principles.md` | 2678 | — |
| `.prawduct/artifacts/architecture.md` | — | destination for Chunk 01 |
| `.prawduct/cross-cutting-concerns.md` | — | registry row |
| `tests/test_v5_methodology.py`, `test_plugin_methodology_digest.py` | — | the ratchet |

## Build Chunks

### Chunk 01: CLAUDE.md diet
**Type:** doc-only

Move architecture and reference description out of `CLAUDE.md` into
`.prawduct/artifacts/architecture.md` — the kernel-v3 data-plane paragraph, the evidence-store
mechanics, and the Project Layout tree. Keep every line that tells the agent what to *do*.
Drop the emphasis-escalation caps (MET-7R4J residue sub-item 2: "**STOP. Read this before
writing ANY code**"), which also misstate Critic timing.

Classify every span by consumer before moving it (learnings — machine-read metadata stays
where its reader looks). Known consumers: the work-model corpus
(`plugin/bin/prawduct-hook`:3555) and `plugin/lib/briefing.py`:589.

`[DECISION: this chunk also converts three instruction-bearing rules to pointers — the
reflection protocol, the single-use-branch consequence, and "run critic-consolidate before
reading findings" — rather than deferring all consolidation to Chunk 03 | because each is
stated 4-7x and its canonical home is the file an agent reads at the binding moment
(`plugin/methodology/reflection.md`, `plugin/skills/pr/SKILL.md` step 4,
`plugin/methodology/building.md` + the session digest); leaving them in CLAUDE.md would have
made the 150-line target unreachable without cutting genuine instruction | user can veto;
Chunk 03 should treat these three as already adjudicated, not re-open them]`

**Done when:**
1. CLAUDE.md project content ≤ 150 lines.
2. Moved prose lives in `architecture.md`; no content lost, only relocated.
3. New guard test pins the CLAUDE.md line count (test the bound, don't just trim — learnings:
   an untested governance bound rots silently).
4. Full suite green.
5. `/prawduct:critic` passes with no blocking findings.

### Chunk 02: The two session digests
**Type:** doc-only

Land the three Opus-5 alignment edits (already drafted, currently uncommitted): the
`verify-your-own-work` → `show-evidence` reword, the delegation floor with its Critic
exemption, and the document-size bar. Then fix what makes the digests hard to read: 53.8 and
50.2 average words per sentence, the worst of any surface. Consolidate the stance block —
12 bars is past the point where a stance is weighed rather than skimmed.

The full digest stays self-sufficient (products); only the slim digest dedupes against
CLAUDE.md.

**Done when:**
1. Three Opus-5 edits landed in both digests as appropriate.
2. Average sentence length in both digests under 30 words.
3. Slim digest carries no rule CLAUDE.md already states; full digest still stands alone.
4. Digest pointer tests and the 10,000-char inline limit still pass.
5. `/prawduct:critic` passes with no blocking findings.

`[CORRECTION: the 53.8 / 50.2 "average words per sentence" figures that motivated criterion 2
were a measurement artifact. The splitter did not break markdown bullets or ·-separated
rosters, so it scored whole list blocks as single sentences. Re-measured with list markers
stripped, the real baseline was 26.9 (full) and 33.1 (slim) — meaning the FULL digest already
met criterion 2 before this chunk touched it, and only the slim digest genuinely failed.
Post-chunk: 22.1 and 19.1. The prose improvement is real but smaller than the plan claimed, and
the remaining "130-word sentence" is the principles roster — a list, not prose. Recorded rather
than quietly restated: the criterion was written on bad data.]`

### Chunk 03: Cross-surface rule consolidation
**Type:** doc-only

The judgment-heavy chunk. For each of the 12 measured rules, pick one canonical home and
convert the rest to pointers. Proposed homes: `critic-consolidate` → critic SKILL;
merge/attribution conventions → pr SKILL; backlog mechanics → backlog SKILL; tests-are-contracts
→ principles.md; norms → docs/norms.md.

Removal discipline: a rule may lose a *restatement* but never its canonical statement, and
never its gate. Where a surface's copy is the one an agent actually reads at the moment it
must comply, that copy is the canonical one and the others go.

**Done when:**
1. Each of the 12 rules resolves to exactly one canonical statement *per co-loaded surface set*
   (see the CORRECTION below).
2. No rule lost its gate; no gate semantics changed.
3. `building.md` and `review-protocol.md` gain measurable headroom (this funds Chunk 04).
4. Full suite green.
5. `/prawduct:critic` passes with no blocking findings.

`[CORRECTION: the "12 measured rules" census was never persisted — it lived only in the planning
session's context, and the plan cited its count without its contents. Re-derived at HEAD, and the
re-derivation showed the plan's counting method was wrong: raw occurrence counts treat every
statement as redundancy, but CLAUDE.md and the full session digest are NEVER both loaded (framework
= CLAUDE.md + slim; product = full digest), and `critic-reviewer.md` is read by a subagent that
never sees `SKILL.md`. Those are one rule reaching disjoint audiences — the correct state is one
statement PER audience, not one globally. The criterion that finds real redundancy is **co-load**:
two statements compete only when a single session holds both. Under it, most of the measured "4-7x"
collapses to legitimate audience coverage, and the genuine duplication is overwhelmingly WITHIN
single files. Done-when 1 is amended accordingly. The plan's central ASSUMPTION is unaffected —
pointers still replaced restatements — but its problem statement overstated the redundancy.]`

`[DECISION: the reverse gap is closed by promoting BOTH rules to the slim digest (option 1 of the
three the checkpoint named) | because the slim digest's stated charter is "hardest rules CLAUDE.md
does not restate" and both qualify exactly — their absence was an oversight in its construction,
not a deliberate placement. Both are Critic-gated (`review-protocol.md` Goal 1 "no pre-existing
exception", Goal 4 durable-artifact drift), but a gate fires at review time, after the defect is
written; "no pre-existing exception" binds at session baseline and the durable-artifact rule binds
at writing time, so gate-only placement misses the moment. The durable-artifact rule earned it
empirically: three violations landed in this cycle's own records (see the Chunk 02 reflection).
Cost +89 est tokens on the always-loaded payload — accepted deliberately | user can veto: the
alternative is accepting on-demand-only placement in building.md and relying on the gates]`

`[NOTE: the general form of the asymmetry — that a consolidation pass must check reach, not only
duplication — is NOT built here. It is a new requirement with no parent in this plan, and doing it
properly means a Critic check (structural, per Principle 22) competing for the same budget Chunk 04
is spending. Filed to the backlog instead.]`

### Chunk 04: Ratchet the budgets, land the deferred check
**Type:** cumulative-final

Lower the token ceilings in `tests/test_v5_methodology.py` to the new actuals plus a small
margin — down, never up (MET-7R4J). Land the Goal 4 **Document size** check in
`review-protocol.md` using the headroom Chunk 03 created; draft is in this session's
scratchpad. Update the `.prawduct/cross-cutting-concerns.md` "Agent stance / conduct" row to
record the now-real Critic mapping.

**Done when:**
1. Every touched budget ceiling is lower than it was at plan start.
2. Goal 4 document-size check landed and within budget.
3. Registry row accurate.
4. Full suite green.
5. `/prawduct:critic cumulative` passes with no blocking findings.

## Verification Strategy

Beyond the suite: after Chunks 01-02, start a fresh session in a scratch clone and read what
the agent actually receives at SessionStart — the diet is only real if the injected payload
shrank. Measure with the same script used to size this plan (word-count × 1.3, matching
`tests/test_v5_methodology.py`'s `estimate_tokens`).

## Governance Checkpoints

- After Chunk 01 — does "move description out, keep instruction in" hold as a rule, or did
  CLAUDE.md need some of what left?
- After Chunk 03 — the removal chunk. Re-read the 12 rules as a fresh agent would and confirm
  each is still findable at the moment it binds.

**Known input to Chunk 03, surfaced by Chunk 02's review (pre-dates this plan).** The
consolidation so far has run one direction only — checking that nothing is stated *twice*.
The reverse gap is real: **"There is no 'pre-existing' exception"** and **"Durable artifacts are
self-contained"** sit on the *full* digest's hardest-rules list and appear in neither CLAUDE.md
nor the slim digest, so a **framework-repo** session receives neither in always-loaded context —
they live only in `building.md`, which is read on demand. Chunk 03 adjudicates: promote both to
the slim digest, accept the on-demand-only placement deliberately, or record why the framework
repo needs them less than products do. Do not let the dedup pass close without answering this —
a consolidation that only ever *removes* will silently widen a gap like this.
