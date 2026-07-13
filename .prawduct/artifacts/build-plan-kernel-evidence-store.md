---
artifact: build-plan
version: 2
scope: kernel-evidence-store
depends_on:
  - artifact: kernel-v3-evidence-design.md
  - artifact: kernel-redesign-discovery.md
  - artifact: kernel-inventory-2026-07-12.md
last_validated: 2026-07-12
---

# Build Plan — Kernel v3, Plan 1: Evidence Store & Deterministic Review Data Plane

First constituent plan of GOV-4C7X. Ships the SHA-keyed evidence store (C1),
the coverage algebra, and the deterministic Critic data plane (C2, review
path), cutting the Stop-hook Critic gate and the PR gate over to coverage
composition. Fixes, by design rather than patch: CRT-J4PM, CRT-5D8Q, CRT-W2NV,
CRT-4B7X, the worktree/host-container evidence split, and the stale-evidence
warning class. Design decisions live in `kernel-v3-evidence-design.md` (D1–D9)
— this plan does not restate them; chunks cite them.

## Requirements Confidence

**Level:** Medium

**Why:** Problem, success criteria, and scope are each one sentence (discovery
§1–2, owner-answered Q1–Q4). What keeps this off High is mechanism, not
requirements: tree-SHA keying is designed but not yet spiked, and the design
carries two owner-vetoable decisions.

**Open assumptions / unknowns:**
- [ASSUMPTION: store lives under `<git-common-dir>/prawduct/` (D1) | MED
  impact | owner can override to a config-knob location, same semantics]
- [ASSUMPTION: temp-index `write-tree` capture works in every supported
  topology — worktrees, containers, headless (D3) | HIGH impact | chunk 01
  spikes it first; owner can veto the keying approach]
- [ASSUMPTION: no back-compat for v2 evidence records — consumers start with
  an empty store; in-flight branches re-review once (discovery §7, Q3) | MED
  impact | owner already accepted at discovery]

**What would raise confidence:** owner skim of D1/D3 (5 minutes); the chunk 01
write-tree spike (~30 minutes, first Done-when step).

## Status

- [x] Chunk 01: Evidence store walking skeleton — append in one worktree, read from another
- [x] Chunk 02: Coverage algebra + the one non-judgeable predicate
- [x] Chunk 03: Deterministic dispatch — code-written manifest, fact-appending consolidate
- [x] Chunk 04: Gate cutover — Stop gate and PR gate answer by composition
- [x] Chunk 05: Prose surfaces — protocols, methodology, digest
- [ ] Chunk 06: Upgrade posture + end-to-end scenarios (cumulative)
Context: Owner approved D1/D3 2026-07-12; D3 spike PASSED same day (plain
repo + linked worktree; non-mutating, untracked captured, ignored excluded,
verbatim commit preserves tree, odb shared). Chunks 01–02 shipped 2026-07-13
(commits 4ee9f7f, 62d9843; chunk 01 Critic final 0-blocking with all 6
warnings fixed; chunk 02 Critic chunk-mode clean). Chunk 03 shipped
2026-07-13 (Critic chunk-mode: 0 blocking/0 warning/1 note → CRT-6Q2N):
the open point closed by SINGLE-PASS UNIFICATION — every mode flows
begin(manifest) → partial(s) → consolidate, single-pass roster is
["reviewer"], resolutions ride the verify-resolutions partial's payload and
only that mode's dispatch may carry them (decisions recorded in the design
doc's D5/D8 chunk-03 refinements). Sessions still govern via the INSTALLED
v2.3.3 plugin — in-repo data-plane changes stay inert until release; verify
with repo-local bin/ only. Next: Chunk 04 (gate cutover).
Chunk 03 shipped notes for chunks 04-05: (a) the Critic SKILL's
allowed-tools pins `Bash(prawduct-hook critic-begin)` EXACTLY — chunk 05
must widen it to `critic-begin *` or the `--mode` dispatch is uncallable;
(b) single-pass unification means SKILL steps 7-8 (hand-written findings,
ledger-append, critic-end) are replaced by "write your one `reviewer`
partial, run critic-consolidate"; (c) the v2 verify-resolutions helpers
(`compute-verify-resolutions-scope`, `_record_covers_head` call sites,
`extends_cumulative` chain) are now bypassed by begin_review's fact-anchored
derivation — chunk 04 deletes them at their sites; (d) D3 caveat surfaced
while testing: a pre-commit review vouches for the commit only when the
commit includes exactly the captured state — selective commits (leaving
captured-but-uncommitted files behind) produce a coverage gap; chunk 04's
gate message must name the v-r remedy, and the trajectory review should
watch this friction in practice.
Chunk 04 shipped 2026-07-13 (Critic final via coordinator, escalate tier:
0 blocking / 4 warning / 7 note — all warnings fixed pre-commit: memoized
diff_fn on the gate hot path, stale-comment sweep, plan/registry
reconciliation). Both gates now answer by composition: PR gate = Q1
(merge-base tree → HEAD tree), Stop gate = Q2 (`.session-base-tree` marker
→ captured working tree, with head-fallback and merge-base-fallback
degradations recorded as D6 chunk-04 refinements). gates.py 1531→~1060
LOC (success criterion 5 on track); repros CRT-J4PM + CRT-5D8Q pass
end-to-end in `tests/scenarios/test_kernel_v3_gate_cutover.py`; 1690 tests.
Backlog: CRT-5D8Q + CRT-4B7X archived (ship-in-pr); GOV-2R8W (porcelain
firing guard vs Q2 span) + GOV-6H4P (advisory-surface coarseness) filed.
Notes for chunks 05-06: (e) `hooks/gates.json` critic entry stamped
`since: 3.0.0` — release prep must re-stamp if the breaking release numbers
differently; (f) `lib/critic_mode.py`'s `extends_cumulative` chain arm +
its dangling `_chain_anchor` docstring ref are chunk-06 vestige-sweep scope
(recorded in design D6 refinements); (g) new session file
`.prawduct/.session-base-tree` rides the gitignore contract (core list +
hook mirror + this repo's .gitignore) — product docs mentioning session
files may need the addition in chunk 05. Next: Chunk 05 (prose surfaces) —
then the after-chunk-04 trajectory review checkpoint: gates.py IS
shrinking, and every deleted check has a named still-blocks regression.
Chunk 05 shipped 2026-07-13 (Critic chunk-mode doc-only: 0 blocking /
0 warning / 1 note). All prose surfaces describe the composition data
plane; §3-deleted-mechanism greps return zero across skills/, methodology/,
CLAUDE.md, docs/, agents/, templates/; net governance-prose −171 est
tokens across the touched set (pr/review-protocol −421 paid for
building.md's new evidence-model section +204; budgets: building 4434<4600,
review-protocol 3320<3350). Cascade exceeded the deliverables enumeration
per the acceptance criterion (Critic note, deliberate): agents/
critic-reviewer.md (covers-HEAD claim died with the staleness refusal),
docs/governance-telemetry.md (pr-scoped/pr-full → `pr`),
docs/project-structure.md + CLAUDE.md layout ("checked by the Stop hook" →
derived-view), and five prose-pinning test files renegotiated in the open
(record-audit pins → stays-deleted guards; CRT-6F2N ordering pin re-anchored
to the Getting Started flow). Critic SKILL allowed-tools: +critic-begin *,
+critic-consolidate, +evidence *; −compute-verify-resolutions-scope,
−ledger-append (consolidate is the only ledger writer for reviews).
No product-doc session-file inventory needed .session-base-tree (checked).
1689 tests (one net consolidation in the renegotiated PR-scoping class).
Next: Chunk 06 (upgrade posture + e2e scenarios, cumulative-final).

## Scaffolding

No project initialization — this is the existing framework repo (Python +
stdlib only, per discovery §7 assumption; no new dependencies). New modules
follow house conventions: return-value error handling (`status`/`reason`
dicts), exceptions escape only at CLI boundaries, subprocess list-form, plain
dicts for JSON (project-preferences.md).

### Build & Test Configuration

Existing `tests/` suite via the repo's `test_command`. New tests follow the
sibling pattern (`tests/test_evidence_store.py` next to
`test_governance_ledger.py` etc.). Gate-behavior changes get scenario tests
under `tests/scenarios/` like the existing ones.

### Verification Strategy

Every chunk is verified against the **repo-local** `python3 bin/prawduct-hook`
(never the PATH/plugin-cache binary — learned rule). Chunks 01 and 06 verify
across two real worktrees of a scratch clone (the topology the store exists
to fix). Chunk 04 replays the CRT-J4PM and CRT-5D8Q reproduction sequences
end-to-end as the acceptance bar — discovery success criterion 2 verbatim.

## Project Structure

```
lib/
├── evidence.py            # new — store: locate, append, iterate, dedupe, schema check (D1, D2)
├── coverage_algebra.py    # new — pure composition functions + gate verdicts (D6)
├── critic_consolidate.py  # changed — appends facts, regenerates cache (D7, D8)
├── critic_marker.py       # changed — critic-begin writes the dispatch manifest (D8)
├── gates.py               # changed (shrinks) — gates delegate to coverage_algebra
└── coverage.py            # changed (shrinks) — donates the surviving non-judgeable predicate
```

### Module Boundaries

`coverage_algebra.py` is pure (facts in, verdict out — no I/O, no git);
`evidence.py` owns all store I/O; only `evidence.py` and git helpers touch
disk. Gates call `coverage_algebra` with facts loaded via `evidence`; nothing
else reads `evidence.jsonl` directly. `.critic-findings.json` is written by
`critic_consolidate` only and read by no gate (D7).

## Build Chunks

### Chunk 01: Evidence store walking skeleton — append in one worktree, read from another

- **Description:** Prove the architecture's keystone claims before anything
  builds on them: store location resolution (D1), the record envelope with
  per-record schema version (D2), atomic concurrent append, iterate with
  id-dedupe and the D9 error postures (torn tail self-heals; interior
  corruption excludes loudly; schema-ahead record blocks with remedy), and
  the D3 tree-capture spike (temp-index `write-tree`, verified non-mutating,
  in a linked worktree and a plain clone). Exposed for humans/doctor as
  `prawduct-hook evidence <status|list>` — the stable allowlistable surface
  (R4).
- **Depends on:** none
- **Artifacts consumed:** `kernel-v3-evidence-design.md` D1–D3, D9
- **Deliverables:** new `lib/evidence.py`, `evidence` subcommand dispatch in
  `bin/prawduct-hook`, new `tests/test_evidence_store.py`
- **Tests:** unit — envelope round-trip, id-dedupe, each D9 error path (one
  test per enumerated path), concurrent-append interleaving; integration —
  append from worktree A, read from worktree B of a scratch clone;
  write-tree capture leaves index/working tree untouched (assert via
  `git status --porcelain` before/after)
- **Acceptance criteria:** a fact appended in one worktree is read, deduped,
  and schema-checked from a second worktree; every D9 path produces its
  designed outcome and nothing else; the spike confirms (or refutes → stop,
  revisit D3) tree capture in both topologies
- **Critic mode:** final
  <!-- Override: architectural keystone — D1/D2/D3 harden here before four
       chunks build on them. -->
- **Done when:**
  0. D3 spike run first; result recorded in this plan's Context line
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: Coverage algebra + the one non-judgeable predicate

- **Description:** Pure composition (D6): facts → edges, edge-validity
  (judgeable changed files ⊆ reviewed files), free edges from the single
  shared non-judgeable predicate, path existence, and the unresolved-blocking
  join over resolution facts (D5). The predicate consolidation is the
  CRT-5D8Q fix: `lib/coverage.py`'s survivor becomes the only implementation;
  the divergent copies are deleted at their sites in chunk 04.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `kernel-v3-evidence-design.md` D4–D6; inventory §3
  (the three divergent doc-only sites)
- **Deliverables:** new `lib/coverage_algebra.py` (including
  `is_judgeable_path`, THE canonical predicate — it lives in the pure module,
  not `lib/coverage.py` as first drafted; the divergent copies in
  `lib/coverage.py`/`lib/gates.py` are deleted at their sites in chunk 04),
  new `tests/test_coverage_algebra.py`
- **Tests:** table-driven composition cases — direct span, two-fact chain,
  doc-only free-edge tail, partial edge (under-reviewed file set) must NOT
  compose, rebase gap must NOT compose, squash-merge tree-identity must
  compose, blocking-finding-without-resolution fails the verdict,
  resolution fact flips it; predicate parity cases pinning the CRT-5D8Q
  metadata boundary to one answer
- **Acceptance criteria:** the CRT-J4PM composition scenario (chunk reviews +
  cumulative + later `final`, no matching labels) yields a passing verdict as
  pure-function input/output; CRT-5D8Q's two boundary questions get one
  answer from one predicate
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: Deterministic dispatch — code-written manifest, fact-appending consolidate

- **Description:** The C2 cutover at the defect site (D8). `critic-begin`
  derives the roster from mode via protocol config and writes the dispatch
  manifest itself (review id, base/head trees, files snapshot) — the model
  never authors it. `critic-consolidate` merges partials against that
  manifest (missing role = loud block naming the role), appends the review
  fact (idempotent by id — the CRT-4B7X race dies here), and regenerates
  `.critic-findings.json` as a derived cache carrying its source fact id
  (D7). verify-resolutions consolidation appends resolution facts (D5).
  Tolerant-encoding rule honored: `[]`/omitted collapse in normalization,
  fail-closed reserved for genuine ambiguity (learned rule).
- **Depends on:** Chunk 02
- **Artifacts consumed:** `kernel-v3-evidence-design.md` D5, D7, D8
  (including the chunk-03 refinements recorded there: single-pass
  unification closes the resolution-fact open point; roster/size rule;
  per-mode base derivation; no staleness refusal at consolidation)
- **Deliverables:** changed `lib/critic_consolidate.py` (begin-side
  manifest AND fact append + cache regen + resolution facts — both ends of
  the `.critic-partials` contract live in one module; `lib/critic_marker.py`
  stays the marker-only guard, unchanged), `critic-begin --mode` CLI in
  `bin/prawduct-hook`, `evidence.tree_diff` (public tree-to-tree diff the
  chunk-04 gates will inject as `diff_fn`), updated
  `tests/test_critic_consolidate.py`, manifest tests alongside
- **Tests:** unit — manifest derivation per mode, missing-partial block
  names the role, double-consolidate appends one fact, cache carries fact
  id and is temp+rename atomic, resolution-fact append; regression — the
  CRT-W2NV omitted-key shape can no longer occur (no model-written field to
  omit): assert consolidate never reads a model-authored manifest path
- **Acceptance criteria:** a full simulated review cycle (begin → partials →
  consolidate) produces exactly one fact and one cache regardless of
  consolidate firing once or twice; removing any partial blocks loudly with
  the role name; nothing in the write path parses model-authored JSON except
  the partials' judgment payload
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: Gate cutover — Stop gate and PR gate answer by composition

- **Description:** The Stop-hook Critic gate asks Q2 and the PR gate asks Q1
  (design §1), both via `coverage_algebra` over store facts. Delete, at
  their sites: mode-label acceptance in `check-cumulative-critic`,
  `extends_cumulative` chain logic, `_record_covers_head`, mtime-vs-
  `.session-start` freshness for review evidence, the stale-evidence warning
  class, and the two now-redundant doc-only predicate copies (chunk 02's
  survivor takes over). Gate messages stay attributed, actionable,
  copy-pasteable (`hooks/gates.json` entries updated). Scope changes by
  structural pattern — every site that branches on review-record labels or
  review-file mtimes — not by line number.
- **Depends on:** Chunk 03
- **Artifacts consumed:** `kernel-v3-evidence-design.md` D6; inventory §3
  (gate-semantics table), §6 (do-not-reverse list)
- **Deliverables:** changed `lib/gates.py` (net LOC down — success criterion
  5), changed `lib/coverage.py`, updated `hooks/gates.json`, updated
  `tests/test_cumulative_gate.py`, `tests/test_critic_gate_fallthrough.py`,
  scenario tests for the two repros
- **Tests:** scenario — CRT-J4PM repro (cumulative + chunk history, then
  gate at HEAD: passes with no re-run) and CRT-5D8Q repro (metadata-boundary
  deadlock: cannot occur — one predicate) run end-to-end against
  `bin/prawduct-hook`; negative — a genuinely unreviewed judgeable change
  still BLOCKS (every deleted check gets a still-blocks regression, per the
  reused-predicate learning); a schema-ahead fact makes the gate block with
  the C7 remedy, never pass
- **Acceptance criteria:** discovery success criterion 2 verbatim — the
  CRT-J4PM and CRT-5D8Q reproduction scenarios pass without a re-run; no
  gate reads `.critic-findings.json` or any single-slot review file; grep
  for the deleted symbols returns nothing at their gate sites (the
  `lib/critic_mode.py` inference mirror's `extends_cumulative` arm is
  non-gate code, recorded in the design doc's chunk-04 refinements as
  chunk-06 vestige-sweep scope)
- **Critic mode:** final
  <!-- Override: this is the highest-blast-radius chunk — gate semantics for
       every governed repo change here. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 05: Prose surfaces — protocols, methodology, digest

- **Description:** The project-wide-concept cascade, enumerated up front
  (planning.md rule): `skills/critic/review-protocol.md` +
  `skills/critic/review-cycle.md` (record-audit and chain prose deleted;
  coverage-composition described), `skills/critic/SKILL.md` allowed-tools
  (gains `evidence`), `skills/pr/SKILL.md` + `skills/pr/review-protocol.md`
  (gate description), `methodology/building.md` (evidence model section),
  `methodology/session-digest.md`, root `CLAUDE.md` (Critic section),
  `templates/` only if a knob changed (none expected). Several carry
  token-budget guardrail tests — trim to fit rather than raising budgets.
  Prose deleted here is the §3 deletion list from the design; no new
  compensating prose (July 2 guardrail).
- **Depends on:** Chunk 04
- **Artifacts consumed:** `kernel-v3-evidence-design.md` §3
- **Deliverables:** the enumerated files above; updated
  `tests/test_critic_skill_metadata.py` if allowed-tools assertions pin the
  list
- **Tests:** existing token-budget and skill-metadata guardrails pass;
  doc-consistency greps (no surviving reference to deleted mechanisms)
- **Acceptance criteria:** every §3-deleted mechanism has zero prose
  references left; net governance-prose tokens down on the touched files
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 06: Upgrade posture + end-to-end scenarios

- **Description:** The C9-for-this-plan proof and the full-bundle review.
  Empty-store lazy init means no migration commit for any consumer — verify
  by simulating a v2.3.3-era repo (stale `.critic-findings.json`, old ledger
  present) waking on the new version: gates must ignore the old files and
  block-with-remedy toward a fresh review, never misread them as current
  (C3/C9 tier 3). Two-worktree and two-sequential-session scenarios exercise
  discovery success criterion 3. Sweep vestiges this plan orphaned
  (gitignore entries whose writers died stay listed only if a reader
  remains). Change-log entries for the release ride here.
- **Depends on:** Chunk 05
- **Artifacts consumed:** `kernel-redesign-discovery.md` §2 (success
  criteria 1–4), C9
- **Deliverables:** new `tests/scenarios/test_kernel_v3_upgrade.py`
  (name per existing scenario conventions), vestige removals, change-log
  entries tagged `kernel-evidence-store`
- **Tests:** scenario — old-state repo on new plugin blocks loudly with
  remedy; worktree A reviews / worktree B passes the gate; session 1
  reviews / session 2 passes with no stale warning
- **Acceptance criteria:** discovery success criteria 1–4 each have a named
  passing test or a recorded pointer to the chunk that proved them
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings
     resolved
  3. Chunk marked `[x]` in Status

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can do:** run `prawduct-hook evidence status` in any worktree
and see the shared store — the program's central claim (evidence composes
across checkouts) made tangible before any gate changes.

## Governance Checkpoints

**Commit & PR cadence:** feature branch `feature/kernel-v3-evidence-store`
off develop; commit per chunk after its Critic review passes; single PR at
the end gated on chunk 06's cumulative review (`/prawduct:pr create` when the
owner asks). Ships as one breaking plugin release per Q3.

- Before chunk 01: owner design review of D1/D3 (the two vetoable keystones).
- After chunk 01: architecture confirmed or D3 revisited — nothing downstream
  starts on an unproven keying mechanism.
- After chunk 04: trajectory review — is `gates.py` actually shrinking, and
  did any deleted check lose a still-blocks regression? (July 2 guardrail:
  the fix program must not itself get overbuilt.)
- After chunk 06 (cumulative): full-bundle review; success criteria 1–4
  traced; confirm no silent scope growth into later plans' territory (test
  evidence, PR facts, C8).
