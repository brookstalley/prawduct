# Framework Efficiency Review — 2026-07-02

**Status:** Accepted by owner (Brooks) 2026-07-02. This is the parent requirement document
for the P0–P2 fix program (waves 1–3). Future sessions picking up any wave item should read
this file in full before planning — it carries the evidence and rationale the backlog
one-liners cannot.

**Method:** Seven parallel read-only audit agents over (1) methodology docs + templates,
(2) skills/, (3) hooks + lib enforcement code, (4) this repo's reflections/backlog/incoming-bugs,
(5) scriob + scriob2 + cordyceps + trenchant `.prawduct/` state, (6) discodon (heaviest
consumer) `.prawduct/` state, (7) a sweep of ~18 other governed repos. Synthesized by the
main session. Owner confirmed the findings "100% confirm intuitions."

---

## Verdict

The methodology core works: the Critic and independent PR reviewer demonstrably catch real
ship-blockers in every active consumer repo, disproportionately the "tests green, still
broken" class. The overbuild is in everything wrapped around that core: bookkeeping
machinery (test-evidence freshness, change-log tag DSL, derived views, mode/type taxonomy)
generates more findings, learnings, and wall-clock than the code it governs, and every gate
misfire has historically been answered with suppression infrastructure (waivers, pragmas,
carveouts, stopword dictionary) rather than trigger-narrowing.

Key numbers:
- ~15,500 LOC of enforcement Python for 4 Stop-hook blockers + 1 advisory nudge.
- ~88% of this repo's own backlog (44 of 50 open items at review time) is governance-machinery
  self-maintenance.
- ~30% of consumer learnings are about surviving prawduct (cordyceps ~55%); reflections skew
  40–50% framework-process content by volume.
- ~31,000 tokens of governance prose loaded across a maximal cycle; 14 distinct
  "read X before Y" obligations, most buried mid-file.
- Test-evidence freshness redesigned 5×; trivial fast-path built 2026-05-22, fully retired
  2026-06-08; Stop hook reworked 6+ times, never stabilized.

Owner's recorded direction is consistent across the reflection history: "think greenfield,"
"simplify, don't refactor," "high-confidence fixes only," "warnings are effectively blocking"
(so false positives can never be fixed by severity demotion).

---

## Evidence highlights (with sources)

### What works — keep it
- **Critic/PR-reviewer catches** (consumer repos): crash-loop `NameError` (discodon
  voice_bridge, ~2026-04-16), crypto vuln disguised as 4% xdist flake (discodon-ts TR-3),
  plaintext password persistence (TangleClaw), data-loss SQL path (`c.persona.*` vs
  `c.behaviors.PersonaComponent.*`, discodon), unreachable feature surfaces, uv.lock missing
  from commit (scriob). PR reviewer independently caught bugs the Critic missed at least
  twice (discodon-evals: Discord cutoff filter, AsyncRouterServer deadlock) — **independence
  is load-bearing; keep two reviewers.**
- **Stop-gate escape hatches** are in-message and copy-pasteable — misfires recover cleanly.
- **Stop-gate defer for background work** (STH-3W7F) is the right pattern.
- Learnings.md as a retrieval surface stays product-focused and useful in every active repo.

### Overbuilt (ranked by frustration evidence)
1. **test-evidence / verify-coverage subsystem.** #1 friction in EVERY consumer repo.
   Stale-evidence warnings on nearly every Critic review for 2.5 months (discodon,
   2026-04-13 "by-design noise but adds up"); ~7 min/chunk byte-identical duplicate suite
   runs (scriob PRW-8T4N); verify-coverage false-BLOCKINGs on prose/docs (incoming bug
   2026-06-11: cheapest resolution is a path-embedding fake test — "trains the corner-cutting
   it exists to prevent"); pytest-only assumption walls out .NET (cordyceps) and Swift
   (trenchant). Freshness signal reworked 5× (fingerprint → removed → reintroduced → removed
   → git_sha → retired TST-4K2P → session-timestamp). Session-timestamp is the settled
   answer; residual gap: review protocols still let reviewers eyeball staleness.
2. **change-log / regen-views derived-view DSL.** Literal-string parser contracts
   (`scope=` name vs version, `chunks=` zero-padding, `status=` lifecycle, `### Chunk N:`
   colon form) whose failures are partial and SILENT. Produced ~12 of this repo's 71
   learnings, two duplicate incoming bugs in consecutive versions (regen-views null-plan,
   2026-06-24/25), broke for trenchant's entire lifespan (lib ModuleNotFoundError — operator
   hand-maintained the derived views; also crashed check-operator-verification), and the
   template's `- [ ]` boxes invite the hand-flip the Critic then catches (3rd recurrence,
   cordyceps 2026-06-24).
3. **Governance prose volume + triplication.** Critic complex ~8,600 words / 4 files;
   mode×type matrix written 3× (planning.md:97-137, templates/build-plan.md:222-281 comments,
   critic skill); 9 stances encoded 3× (principles → agent-stance.md → digest);
   build-plan template 2,774 words with ~200 fillable and ZERO filled example; a known
   parser-bug narrative ships inside the starter template (build-plan.md:22-29). Five
   cross-doc contradictions documented (Critic-per-chunk vs 1-3-chunk session cap; PR
   default vs template Done-when; final-mode default trigger stated 3 ways; reflection
   cadence enforced-per-session vs prescribed-per-chunk; discovery question counts vs
   "not a state machine"). Compressed Fable-ese ("the `cumulative` that IS a
   `cumulative-final` plan's last-chunk review", building.md:284) won't parse on Opus.
4. **Two-reviewer OVERLAP machinery** (not the reviewers): the "Critic Record — Evidence,
   Not Truth" audit protocol (pr/review-protocol.md:19-27), extends_cumulative chain,
   verify-resolutions scope math, "don't re-scan" scoping prose — ~2k words existing only
   to deduplicate two overlapping scopes.
5. **Enforcement that fights itself.** Work-model tripwire counts refactor/rename/remove as
   requirement verbs (lib/work_model_index.py:120-126) and its corpus globs only top-level
   docs — fired on the owner's own review prompt twice, including this review's. 82
   broad-except allow-pragmas mean gate bugs silently fail OPEN while docs claim
   fail-closed. Trivial gate hard-codes prawduct's own dir names as blast radius in product
   repos and has no waiver key (KNOWN_WAIVER_KEYS lacks "trivial"). Critic Stop gate accepts
   any schema-valid fresh findings file EVEN WITH unresolved blockings (gates.py:300-311 —
   schema check only). Reflection gate = len >= 50 chars.

### Underspecified (ranked)
1. **Environment assumptions**: repo-root Python, single checkout, main-based. Violated by
   engine/ subdirs (scriob), .NET/Swift (cordyceps/trenchant — no evidence path, meaningless
   coverage floor), git worktrees ("following one prawduct rule forces you off-protocol on
   another" — incoming bug 2026-06-20), devcontainers (discodon), gitflow (silent wrong-base
   on every first PR unless base_branch: known).
2. **Scoping blind spot**: "every reviewer checks work AS SCOPED, never whether the
   requirement should EXIST" — metallm, documented 4×; scriob shipped 697 commits with an
   unversioned API on an unchallenged one-word deferral. No review stage pressure-tests
   scope or whether a named concern was ever built.
3. **Gates enforce proxies, not outcomes** (see overbuild #5); coverage / cumulative-critic /
   operator-verification / test-freshness are skill-invoked only — never hook-enforced.
4. **Judgment offloads with no weaker-model scaffolding**: "detect domain concerns
   dynamically, no hardcoded lists" (discovery.md:100); no root-cause stopping rule; 3-4-file
   size-classification dead zone; no red-baseline protocol; no merge-conflict procedure.
   Actual weak-model failures cluster in SUBAGENT quality (premature "Done", over-broad
   allowlists, 5-15% inventory undercounts — discodon learnings).
5. **Memory triple-track**: reflections.md is write-heavy/read-never (discodon: 7,645 lines,
   nothing retrieves from it); metallm's reflection loop froze in March while learnings
   thrived; blobdrop's framework-observations/ created and never written. Converge to:
   learnings + learnings-detail durable, .session-reflected ephemeral, retire per-repo
   reflections.md accumulation. (Owner flagged this convergence candidate directly.)
6. **NEW (from the program-planning conversation, 2026-07-02):**
   a. **No plan-decomposition guidance.** building.md's size ladder ("Large: full discovery +
      planning + chunked build") reads as an instruction to build ONE big chunked plan; there
      is no guidance on plan lifetime limits, splitting heterogeneous work, ship-per-wave, or
      structuring a program of work. Had the owner said "build all P0-P2," an Opus session
      would have complied with one monolithic plan — the methodology endorses the bad shape.
      The long-lived-plan frictions were in learnings for weeks without flowing back into
      planning.md (a Close the Learning Loop failure).
   b. **No persistence contract for rich review/research output.** Cross-session surfaces
      (build-plan Context line, backlog one-liners, auto-generated .session-handoff.md) are
      all thin. This document exists because the workaround is manual: write an artifact,
      link every backlog item to it. The gap: research/review outputs have no first-class
      home and no guarantee a future session finds them.

### Structural diagnosis
Learnings.md already says it: "Governance complexity breeds governance complexity — after 11
independent additions, hooks alone exceeded the skill files they protected." Pattern: gate
misfires → suppression layer added (waiver DSL, allow-pragmas, common-words floor, carveouts)
→ suppression layer accretes its own bugs and learnings. Habituation cost is measured:
scriob reflections routinely open Critic results with "both known gate false positives."
Proposed principle amendment: **the third rework of a mechanism is a deletion signal, not a
patch signal** (supported 3×: fingerprint, trivial fast-path, stop hook).

---

## The fix program — waves and recommendations

Structure decided with owner 2026-07-02: NOT one large build plan. Three waves of small,
independently-shippable plans (each 1-2 chunks, own feature branch, ships at next version
bump). Rationale: long-lived plans are a documented friction source; the work is
heterogeneous (prose vs gate behavior vs design); value ships per wave; self-hosting risk
(editing gates that govern the editing session) favors small blast radius. Everything in
Wave 1 is high-confidence; Wave 2's memory-convergence and worktree items need a short
design note first (owner's "high-confidence fixes only" rule gates them).

### Wave 1 — kill the recurring taxes (P0)
- **Plan A: gate-noise.** (1) One line in BOTH review protocols (skills/critic/review-protocol.md,
  skills/pr/review-protocol.md): freshness is the `test-status` exit code; reviewers must
  never infer staleness from anything else. (2) Tripwire: drop
  refactor/rename/redesign/rework/remove/replace from REQUIREMENT_VERBS
  (lib/work_model_index.py:120-126); include doc subdirectories in the corpus
  (bin/prawduct-hook:2661-2675 globs only top-level).
- **Plan B: changelog-fail-loud.** regen-views validates every change-log tag against the
  plan roster at write/check time and errors loudly on non-matches (no silent partial
  flips); tolerant chunk-ID matching (zero-padding, separator). Consider shrinking the
  vocabulary: one scope identifier, statusless-until-release as the only lifecycle.
- **Plan C: prose-diet.** Single-source the mode/type matrix (methodology only; template
  gets a pointer); strip build-plan template to a FILLED example + brief comments; fold
  agent-stance.md into the digest; fold the 4 one-line delegator skills
  (building/discovery/planning/reflection) into /prawduct:methodology; delete
  implementation narration (hook internals, bug IDs, withdrawn-model chains) from files
  weaker models parse; reconcile the 5 documented contradictions. Target: halve the ~31k
  token cycle load.

### Wave 2 — outcome gaps (P1)
- **Scope check in review**: one mandated question in cumulative/PR protocols — "does this
  capability trace to a documented requirement, and is it reachable/consumed end-to-end?"
  (the metallm blind spot; costs a paragraph).
- **Outcome-checking Critic gate**: findings file must show zero unresolved blocking
  findings, not merely valid schema (lib/gates.py:300-311, critic_findings_satisfy_session_gate).
- **Environments plan**: supported worktree story; gitflow base detection that doesn't
  require knowing base_branch: exists; non-Python coverage floor goes SILENT (not noisy)
  for languages it can't see; document --from-counts as the paved non-pytest path.
- **Reviewer-dedup deletion**: keep both reviewers; PR reviewer becomes a fresh full-scope
  release review; DELETE the record-audit protocol, extends_cumulative chain, and
  "don't re-scan" scoping prose.
- **Memory convergence** (design note first): learnings + learnings-detail durable;
  .session-reflected ephemeral (distilled or discarded at session end); retire per-repo
  reflections.md accumulation. Changes the onboarded-repo contract → needs migrate path.
- **Plan-shape guidance in planning.md** (from finding 6a): mechanical heuristics — one plan
  per scope tag; split when change types differ; a plan that won't ship within ~3 sessions
  is a program → backlog items + per-wave plans; the planner must push back on
  monolithic-plan requests. Include parallelization guidance: when a program's plans have
  disjoint file ownership, recommend parallel worktree-isolated execution (the
  disjoint-ownership learning already exists in learnings.md but planning.md never surfaces
  it at plan time); dependencies and shared files force sequencing.
- **Advisor-first stance, made structural** (owner directive 2026-07-02): "lean into
  prawduct's role as advisor/expert rather than merely an implementor of whatever the user
  asks for — there's a tone thing here that might benefit all models." Two parts:
  (a) TONE — when Plan C (prose-diet) rewrites the digest, reframe the stance block from a
  trait list into a lead position: the agent's first duty on any substantive ask is the
  expert take (risks, stronger/simpler alternative, recommendation), compliance second.
  (b) STRUCTURE — attach advisory obligations to checkpoints models already hit, because
  tone exhortations decay on weaker models: plan creation (plan-shape pushback, above),
  backlog pick (is this still worth doing?), discovery start (what the user hasn't thought
  of — already present), "build X" requests (the Before-Building check gains an explicit
  "should this be built as asked?" line). Advisorship that lives only in adjectives will
  not survive Opus under context pressure; advisorship attached to gates will.
- **Persistence contract for review/research artifacts** (from finding 6b): a first-class
  home (e.g. .prawduct/artifacts/ with a naming convention) + backlog items link to their
  parent artifact + pick surfaces it. Possibly just a convention + template + one line in
  planning.md; avoid building machinery.

### Wave 3 — weaker-model scaffolding (P2)
- Filled example chunk in the build-plan template; domain-concern checklist seeded by
  structural characteristics; root-cause stopping rule; 3-4-file size tiebreak;
  red-baseline protocol.
- Subagent-output verification rule in building.md ("a subagent's 'Done' on a removal is a
  claim to verify" — already a discodon learning).
- Trivial gate: add waiver key + product-relative blast radius, or retire it (its sibling
  fast-path already proved fileset-as-detector unsound).
- Consider principle amendment: third rework of a mechanism = deletion signal.

---

## For the future agent picking this up

- Read this file in full, then the wave's backlog items (each links back here).
- The seven audit-agent raw reports are NOT persisted (session transcripts only) — this
  document is the durable record; file:line cites above point at the primary evidence.
- Consumer evidence lives in sibling repos' .prawduct/ (scriob, scriob2, cordyceps,
  trenchant, discodon especially); incoming-bugs/archive/ holds the 16 upstream reports.
- Wave 1 plans are high-confidence: proceed to planning without re-running discovery.
- Wave 2's memory-convergence and worktree items: write the short design note FIRST and
  confirm with the owner before building.
- Guardrail from the owner: the fix program itself must not get overbuilt. Prefer deletion
  over patching; prefer convention over machinery; warnings are effectively blocking, so a
  false-positive class is never fixed by severity demotion.
