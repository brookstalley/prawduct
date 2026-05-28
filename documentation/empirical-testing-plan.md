# Backlog & Prompts — Empirical Testing Plan & Design State

**Status:** Checkpoint as of 2026-05-27. Active phase: empirical validation against real codebases, before pivoting to build plans.

**Audience:** Future-you (or future-Claude) picking this up after `/clear`. This document is self-contained — read it cold and resume testing without needing the chat history that produced it.

---

## 1. How to use this document

You're here because two big framework features are designed, decisions are locked, and the next step is empirical validation before writing build plans. The requirements docs are stable but contain assumptions that need real-world testing.

This document does three things:
1. **§2-§4 checkpoint what's decided** so you don't re-litigate.
2. **§5 lists six empirical opens** to test against real codebases — what to test, why, method, success criteria.
3. **§6 explains the test-repo conventions** and how to record results so they're durable.

If you're resuming a partially-complete testing pass: scan §5 to find which opens are still pending (or have stale results), then jump to the relevant subsection.

---

## 2. Where we are

**Phase complete:**
- Two requirements docs written and iterated through a structured decision walkthrough (7 critical decisions + 4 soft spots).
- All walkthrough decisions reflected in the requirements docs (v0.1 of locked decisions).
- Two research files produced and integrated into the prompts requirements.

**Phase active:**
- Empirical validation against real codebases. Six opens (§5) to test before locking the build plan.

**Phase deferred:**
- Build plans for both features. Won't start until empirical results are in and design has been adjusted if needed.

**Files that constitute current state:**
- `documentation/backlog-system-requirements.md` — full backlog feature spec (v0.1)
- `documentation/prompt-management-requirements.md` — full prompt-management feature spec (v0.2 as of 2026-05-28; expanded to cover Category A api-call and Category B runtime-instruction)
- `documentation/research/llm-failure-modes.md` — 28 statically-detectable LLM-app failure modes, each tagged with `Applies-to (kind)` (api-call/both)
- `documentation/research/vendor-prompt-sources.md` — vendor URL directory across 9 topics × 4 vendor families
- `documentation/empirical-testing-plan.md` — this file
- `documentation/research/open-1-detection-results.md` — Open 1 results (qualitative pass on metallm/discodon/prawduct, 2026-05-28)
- `documentation/research/open-2-role-grouping-results.md` — Open 2 desk-review on metallm inventory (PASS at ~30 min edit cost, 2026-05-28)
- `documentation/research/open-4-critic-reasoning-results.md` — Open 4 Category B chunk (manual catalog application to prawduct's own Critic skill, 2026-05-28)
- `documentation/research/open-6-model-tier-registry.md` — model-tier registry draft + 100% coverage check against test repos (2026-05-28)
- `documentation/post-sync-advisory-spec.md` — shared advisory infrastructure spec (referenced by both feature requirements)

---

## 3. What's locked (decisions both docs share)

These are the architectural shapes that survived the critical pass and the walkthrough. Do not re-design them without explicit reason — they're load-bearing.

### Cross-cutting
- **Migration architecture:** post-sync advisory mechanism — sync detects signals, writes advisories to a tracked store, session briefing surfaces them, user invokes opt-in commands. NOT behind `prawduct-doctor`.
- **Skill vs agent split:** heavy operations (`/backlog`, `/llm-strategy`) are agent-backed (separate context, loaded only when invoked). Light reference lookups (`/llm-guide`) stay as skills. This was added after the walkthrough — skill prompt token budget would otherwise be painful.
- **Critic input set fully specified:** strategy artifact + failure-mode catalog (framework + project-local) + vendor sources directory + open web access + role classification + review guidelines.

### Backlog
- **Item shape:** `[PFX-XXXX]` (2-3 letter area prefix + 4-char random alphanumeric) + one-line metadata bar + free-form body of any length. Body length is author's call — sentence or multi-paragraph, both fine.
- **Collisions:** accepted as rare; humans dedup if they ever notice.
- **Metadata:** soft on new items (Critic NOTE only, never BLOCKING). Legacy items remain valid indefinitely.
- **Grouping:** `area:` tags + tool views. No file sections.
- **Lifecycle:** explicit `/backlog update PFX-XXXX status=...` calls. Framework does NOT scan plans or change-logs for inference.
- **Backlog hygiene step:** strongly advised at chunk close in build plans. Agent owns the judgment. NOT structurally enforced.
- **Migration:** existing free-form items stay valid until explicit `/backlog migrate`. External backlog files (TODO.md etc.) never auto-imported — detected and advised.

### Prompts
- **Structural characteristic:** `uses_llm_inference` becomes the 7th, gates artifact + methodology hooks.
- **Artifact required:** before any *prompting work* (writing prompts, templates, dispatch, fixtures, evals). NOT required for pure API/plumbing chunks (OpenRouter setup, auth, retries, rate limits).
- **Inventory unit:** role (one LLM-call purpose). A single role may declare multiple models with relationships (primary/fallback/escalation/A/B).
- **Critic mode `llm-prompt`:** adaptive. Reads inventory, classifies each role by usage class, applies relevant failure modes using *guidelines, not a matrix*. Each finding includes a reasoning trail.
- **Web research:** open scope (vendor docs, academic, industry, practitioner, domain-specific). Critic-judged cadence (no fixed sampling). Vendor sources directory is a starting point, not an allowlist. Fetched content treated as untrusted.
- **Verification hints:** optional. When present, Critic uses them and blocks on drift. When absent, Critic trusts the artifact.
- **Severity:** Critic findings default NOTE; project can promote per-role to BLOCKING.
- **LLM-detection by code semantics, not SDK enumeration:** the detection step should reason about prompt-shaped strings, HTTP requests to LLM API hostnames, model-name patterns, token-counting libraries, message/tool-use structure — not match against an enumerated SDK list. Probably the detection step itself is an LLM call. **This is the most important locked principle for testing — see Open 1.**

---

## 4. Open questions deferred to build plans

These came up during the critical pass but don't need to block the empirical phase. Recording so they're not forgotten.

### Cross-cutting
- ~~**Post-sync advisory infrastructure schema** — both features depend on this. Schema, runtime location, lifecycle, dismissal, session-briefing format all currently hand-waved. Needs its own short spec before build plans.~~ **Drafted 2026-05-28 in `documentation/post-sync-advisory-spec.md` (v0.1)**. Open questions Q1-Q5 in that spec remain; not blocking on build plans.
- **Stop-hook integration with new gates** — does stop-hook know about LLM-mode Critic? Unclear; needs spec.
- **Session briefing growth** — already long; both features add advisories. Combined readability matters.
- **CLAUDE.md template updates** — small but real growth.

### Backlog
- **`Promoted` state may not earn its complexity.** Open + Archive might be sufficient. Watch in testing.
- **Prefix vocabulary balkanization** without a registry — soft project-level vocabulary in `project-state.yaml` would help.
- **`/backlog list` default 90-day filter** may hide long-lived items.
- **Multi-author concurrent dedup** misses (back-to-back adds in same session don't see each other).
- **`/backlog dismiss-advisory` consistency** across features.

### Prompts
- **Multi-model role routing logic** not statically verifiable by Critic.
- **"Best practices applied" free-form vs controlled vocabulary** — Critic matching against catalog is brittle if phrasing varies.
- **`status: tbd` ambiguity** — designed-for-later vs migration-probe-filed. Same field, different meaning.
- **No "why" field in role inventory** — only what + how. Decision rationale missing.
- **Cost & latency targets** in artifact go stale; no update mechanism.
- **Failure-mode catalog versioning** when both framework and project-local update — merge semantics.
- **Schema migration on `prompt-strategy.md`** across framework versions.
- **`/llm-guide --refresh` doesn't actually refresh** content — just liveness-checks URLs. Confusing name.

These items return when build plans start. Don't try to resolve them now.

---

## 5. Empirical opens to test

Six opens. Order is by build-plan-blocking risk — higher-risk first. Each open is self-contained: question, why it matters, test method, success criteria, result-recording location.

### [partial] Open 1: LLM-usage detection by code semantics

**Question.** Can an agent reliably detect that code uses LLM inference from semantics alone — without import-list matching — and roughly characterize the usage shape?

**Why it matters.** The migration probe and `/llm-strategy detect` both depend on this. If it works, the framework gracefully handles any LLM pattern (SDK, bespoke HTTP, OpenRouter, LangChain, raw API calls). If it fails, we need a fallback we don't currently have.

**Test method.**
1. Identify candidate test repos covering:
   - A multi-vendor LLM codebase (discodon-shape)
   - A codebase using HTTP directly with no vendor SDK (bespoke wrapper) — if available
   - A LangChain or LiteLLM-using codebase — if available
   - A non-LLM codebase that has adjacent terminology ("agent", "model", "generate", "summary") — false-positive check
2. Spawn an agent with `Read` + `Grep` + `Glob` access pointed at each repo.
3. Prompt the agent to identify LLM-using code from semantics, NOT from an SDK enumeration. The agent should consider:
   - Prompt-shaped strings (long, instructional, "you are", "respond with", "given the following")
   - HTTP requests to known LLM API hostnames (api.openai.com, api.anthropic.com, generativelanguage.googleapis.com, openrouter.ai, etc.)
   - Model-name string patterns (claude-*, gpt-*, gemini-*, llama-*, mistral-*, qwen-*, etc.)
   - Token-counting library usage (tiktoken, anthropic.count_tokens, gpt-tokenizer, etc.)
   - Message/role/tool-use shape in request bodies
   - Streaming-response handling
4. Output: list of `(file, line, suspected role, evidence)` records per repo.

**Success criteria.**
- Detects ≥80% of true LLM call sites in the LLM-using repos
- False positives ≤10% in the non-LLM repo
- Evidence cited per detection is concrete (file path + matching pattern), not hand-wavy

**Where to record results.** `documentation/research/open-1-detection-results.md` — one section per repo with hit list, false positives, edge cases observed.

**First run completed:** 2026-05-28, against `../metallm` (develop @ ba26c59), `../discodon` (fix/empty-room-playback @ 3f4295602), and prawduct itself (main @ 2cb29be) as the false-positive check. Results in the file above. Outcome: qualitative pass on all three success criteria; status `[partial]` pending hand-labeled ground-truth precision/recall on one repo. Three-class migration taxonomy (Shape α / β / γ) emerged from the run and is now in `prompt-management-requirements.md` §11.3.

---

### [partial] Open 2: Role grouping for `/llm-strategy detect`

**Prereq:** Open 1 detection output. The metallm Shape β inventory in `open-1-detection-results.md` is essentially Open 2's deliverable — Open 2 wrap-up reduces to "review whether that draft would ship with ≤30 min of human edits."

**Desk-review run completed:** 2026-05-28 against the metallm inventory. PASS at ~30 min estimated edit cost. Results in `documentation/research/open-2-role-grouping-results.md`. Tool-shipping run (end-to-end with the actual `/llm-strategy detect` implementation) pending the prompts-feature build plan.

**Question.** Given LLM call sites identified (Open 1's output), can the agent group them into a usable role inventory — naming roles, attaching each call site to a role, drafting per-role metadata?

**Why it matters.** This is the most magical piece of the prompt-management feature. If the first draft is gibberish, the whole migration story collapses; users would have to write the inventory by hand, defeating the tool.

**Test method.**
1. On the multi-vendor real codebase (test repo from Open 1), feed the detected call sites into a role-grouping agent.
2. Agent should produce a draft inventory in the shape defined in `prompt-management-requirements.md` §5.2:
   - Role name (inferred from function names, file context, surrounding logic)
   - Vendor + model (extracted from config, imports, or constants)
   - Prompt location (file path or inline reference)
   - Best practices currently applied (inferred from code patterns: caching, structured output, refusal handling, etc.)
   - Status: tbd (since we're drafting)
3. Compare draft to ground truth (what the user would write by hand for the same codebase).

**Success criteria.**
- Roles named usefully (a human reading the inventory understands the role's purpose)
- Related call sites grouped under the right role
- Vendor + model populated correctly where evidence exists
- User would accept draft with ≤30 min of edits, not require full rewrite

**Where to record results.** `documentation/research/open-2-role-grouping-results.md` — drafted inventory per repo, side-by-side with human-corrected version, time spent on corrections.

---

### [ ] Open 3: `/backlog migrate` time per item

**Note:** This is the only open that needs no external test repos — the flagship backlog (`.prawduct/backlog.md`, 43 items) is the test bed. Natural warmup; can run in parallel with sourcing repos for Opens 1, 2, 6.

**Question.** Realistically, how long does it take a user to walk through ~50 legacy backlog items in batched migration?

**Why it matters.** Requirements estimate 30 min per 50 items. If the real number is 2 hours, migration feels hostile and users skip it. The flagship backlog (43 items in this repo) is the obvious test bed.

**Test method.**
1. Read this repo's `.prawduct/backlog.md` (43 unstructured items as of 2026-05-27).
2. Simulate the proposed batch UX manually:
   - Batch of 10 items
   - For each: title + first 2 body lines, inferred metadata (source, area, added date), prompt for effort/impact
3. Time the walkthrough. Note friction points: inference accuracy, body-reading time, batch fatigue.

**Success criteria.** ≤45 min total for 43 items, including pauses to read multi-paragraph bodies.

**Where to record results.** `documentation/research/open-3-migration-time-results.md` — time per batch, friction observations, suggestions for batch-size or UX tweaks.

---

### [partial] Open 4: Critic adaptive classification + applicability reasoning

**Chunk 4 (Category B) completed:** 2026-05-28. Manual catalog application to prawduct's own `agents/critic/SKILL.md`. Results in `documentation/research/open-4-critic-reasoning-results.md`. Rule A narrowing worked cleanly (none of 18 api-call-only failure modes false-positived); FM-13 independently confirmed an existing backlog item (positive catalog validation); FM-16 surfaced a real gap (no regression-fixture suite for Critic output). Chunks 1-3 (Category A: Haiku-classifier, Opus-agent, multi-model role) pending Critic-mode-`llm-prompt` implementation.

**Question.** Given a real chunk diff (touching an LLM role), a prompt-strategy artifact, and the failure-mode catalog, can the Critic produce sensible findings with traceable reasoning?

**Why it matters.** The adaptive Critic is the core promised value of the LLM-prompt feature. If classification is incoherent or applicability reasoning fails, the whole "LLM-aware Critic" story degrades.

**Test method.**
1. Hand-construct four test chunks (or extract from real history):
   - A Haiku-classifier chunk (small + single-shot + Anthropic; `kind: api-call`)
   - An Opus-agent chunk (frontier + agentic + tool-use; `kind: api-call`)
   - A multi-model role chunk (primary + fallback in same role; `kind: api-call`)
   - A runtime-instruction chunk — edits to prawduct's own `agents/critic/SKILL.md` or a similar shipped skill (`kind: runtime-instruction`). Tests §7.3 Rule A narrowing: the Critic should skip api-call-only failure modes (caching, max_tokens, temperature, etc.) and apply the `both`-tagged subset (prompt structure, security, eval).
2. Build a minimal prompt-strategy artifact describing each test role.
3. Spawn a Critic agent with the failure-mode catalog and review guidelines from `prompt-management-requirements.md` Appendix A.
4. Feed each chunk to the Critic and capture: findings emitted, reasoning trail per finding, applied failure modes.

**Success criteria.**
- Findings match what a thoughtful human reviewer would surface (judge subjectively, but be consistent)
- Reasoning trail explains *why* each failure mode was applied to this role
- No flagrant misapplications (e.g., FM-3 Anthropic XML check fired on a GPT-5 prompt)
- Multi-model chunk correctly applies different checks per model in the role

**Where to record results.** `documentation/research/open-4-critic-reasoning-results.md` — findings + reasoning trails per chunk, plus a "would a human reviewer agree" assessment.

---

### [ ] Open 5: Critic web research wall time + self-budget

**Question.** In a realistic LLM-mode Critic review of a 3-5 role project, how many web fetches does the Critic want, and how long does the full review take?

**Why it matters.** Open-scope research + judgment-driven cadence + multi-role projects could yield 20-40 fetches per review with 8-15 min wall time. Without measurement, we can't tell if the Critic spontaneously self-limits or runs unbounded.

**Test method.**
1. Use the test scenario from Open 4 (or expand to 4-5 roles).
2. Run the Critic in LLM-mode with `WebSearch` + `WebFetch` enabled.
3. Instrument: count fetches, log URLs, measure wall time, capture Critic's stated reasoning for each fetch decision ("I'm fetching X because Y").
4. Observe whether Critic self-limits ("further research has diminishing returns") or pulls until done.

**Success criteria.**
- Wall time ≤2x current Critic baseline (so ≤8 min for the flagship)
- Fetches stop on diminishing returns, not at arbitrary cap
- URLs fetched are relevant to findings produced (no fetches that didn't inform a finding)

**Where to record results.** `documentation/research/open-5-web-research-results.md` — fetch log, wall time, self-limiting observations.

---

### [x] Open 6: Model-tier registry coverage

**Prereq:** Open 1 detection output (extracts model IDs from the test repos as input to the coverage check).

**Completed:** 2026-05-28. Registry drafted at `documentation/research/open-6-model-tier-registry.md` covering Anthropic / OpenAI / Google / Open-Local across small / mid / frontier tiers plus non-chat modalities (image-gen, STT, embeddings) and aggregator-mediation. Coverage 100% (9/9 specific model IDs in metallm + discodon classified). Quarterly refresh schedule begins.

**Question.** Drafting a per-vendor model-tier table (small/mid/frontier), does it cover the models real projects use without leaving gaps?

**Why it matters.** Critic classification of role tier depends on this. Gaps mean Critic falls back to training-data knowledge that goes stale fast.

**Test method.**
1. From the candidate test repos, extract every model name in use (via Open 1's detection or direct grep).
2. Draft a tier table per vendor: small / mid / frontier — with current models in each tier (as of 2026-05).
3. Cross-check each model in the test repos against the table.
4. Identify gaps (model present in repo, not in table) and ambiguity (model that could fit two tiers — e.g., `gpt-oss-120b` — frontier-quality on benchmarks but open-weight cheap-to-run).

**Success criteria.** ≥95% of models in the test repos have a clear tier classification in the table.

**Where to record results.** `documentation/research/open-6-model-tier-registry.md` — the drafted tier table itself + coverage report against test repos. This file becomes the registry that ships in the framework.

---

## 6. Test repo conventions

### Where to put test repos

Place test repos under `~/source/` (the user's convention) and reference them by absolute path in result files. Do NOT copy them into this repo — they're external references.

### 6.1 Test repo registry

Repos used across opens. Populated as repos are chosen and used; lets a resumer find "which repo backed which open" without opening N results files.

| Repo | Path | Branch / HEAD at last run | Description | Used by opens |
|---|---|---|---|---|
| metallm | `../metallm` | develop @ `ba26c59` (2026-05-28) | Multi-vendor LLM via LangChain + LangGraph; DB-backed model registry; PostgreSQL-encrypted provider keys; mixed inline + DB prompts | Open 1 |
| discodon | `../discodon` | `fix/empty-room-playback` @ `3f4295602` (2026-05-28) | Multi-role persona/agent system via OpenRouter; Cosmos DB-backed prompts + entity behavior; template renderer with placeholder resolution | Open 1 |
| prawduct (self) | `.` | main @ `2cb29be` (2026-05-28) | False-positive check + Category B (runtime-instruction) reference case | Open 1, planned Open 4 (Category B chunk) |

Add new rows as opens consume new repos.

### How to invoke each test

Each open's "test method" describes the steps. For Opens 1, 2, 5 use background agents (long-running, isolated context). For Opens 3, 4, 6 the work is short enough for foreground.

### How to record results

Each open writes a single results file in `documentation/research/open-N-*.md`. Conventions:
- Date the run at the top
- Identify the test repos used (paths + brief description)
- Capture raw observations before interpretation
- End with a verdict: did we hit the success criteria? what surprised us?

If you re-run an open with new repos, append to the existing file (don't overwrite). Most recent run goes at the top with a clear `## Run YYYY-MM-DD` header.

### Tracking which opens are done

Update §5 in this file: each open header gets a status tag — `[ ]` pending, `[partial]` ran but more data needed, `[x]` done.

---

## 7. Resume procedure (read this if picking up cold)

If you're picking this up after `/clear` or in a new session:

1. Read this file end-to-end. It's self-contained.
2. Skim `documentation/backlog-system-requirements.md` and `documentation/prompt-management-requirements.md` for the architectural shapes. Don't re-derive — just refresh.
3. Skim `documentation/research/llm-failure-modes.md` and `vendor-prompt-sources.md` briefly so you remember what they are.
4. Check §5 above for open status. Pick the next `[ ]` or `[partial]` open.
5. For the chosen open, read its subsection in §5, set up the test, run it, record results in the open's results file.
6. Update the open's status tag in §5 when complete.

If you finish all six opens, the next phase is: **revisit §4's deferred questions, draft post-sync advisory infrastructure spec, then build plans.**

---

## 8. Quick reference — what's in each file

| File | Purpose | Read when |
|---|---|---|
| `documentation/empirical-testing-plan.md` | This file. Checkpoint + test plan. | Start here, always. |
| `documentation/backlog-system-requirements.md` | Full backlog feature spec, v0.1 locked. | Designing test, writing build plan. |
| `documentation/prompt-management-requirements.md` | Full prompts feature spec, v0.2 (Category A + B). | Designing test, writing build plan. |
| `documentation/research/llm-failure-modes.md` | 28 statically-detectable LLM-app failure modes, kind-tagged. | Open 4 testing; Critic skill content. |
| `documentation/research/vendor-prompt-sources.md` | Vendor URL directory across 9 topics × 4 vendor families. | Open 5; `/llm-guide` content. |
| `documentation/research/open-1-detection-results.md` | First-pass detection results across 3 repos; migration taxonomy α / β / γ. | Resuming Open 1 or 2; designing detect tool. |
| `documentation/research/open-2-role-grouping-results.md` | Desk-review of metallm inventory ship-readiness. | Resuming Open 2; tuning detect tool output. |
| `documentation/research/open-4-critic-reasoning-results.md` | Category B Critic dogfood; Rule A narrowing validation. | Resuming Open 4; authoring constructed test chunks. |
| `documentation/research/open-6-model-tier-registry.md` | Per-vendor model tiers + retired models + coverage report. | Critic adaptive applicability reasoning; quarterly refresh. |
| `documentation/post-sync-advisory-spec.md` | Shared advisory infrastructure spec (schema, lifecycle, CLI). | Writing the infrastructure build plan; either feature's build plan. |

---

## Status log

| Date | Event |
|---|---|
| 2026-05-27 | Initial checkpoint. Requirements docs at v0.1. Six empirical opens defined, all pending. |
| 2026-05-28 (early) | Open 1 first qualitative run on metallm, discodon, prawduct. Results in `documentation/research/open-1-detection-results.md`. Status [partial] pending ground-truth labeling. Three-shape migration taxonomy emerged (α / β / γ) and folded into `prompt-management-requirements.md` v0.2 §11.3. Category B (runtime-instruction) added to spec scope; failure-mode catalog tagged with `Applies-to (kind)` per §7.3 Rule A. Open 4 test method extended to include a Category B chunk. |
| 2026-05-28 (later) | Autonomous continuation: Open 2 desk-review on metallm inventory (PASS ~30 min edits); Open 6 model-tier registry drafted + 100% coverage; Open 4 Chunk 4 (Category B) manual catalog application to prawduct's Critic skill (Rule A narrowing validated; FM-13 confirmed existing backlog item; FM-16 surfaced unfilled regression-fixture gap); post-sync advisory infrastructure drafted at `documentation/post-sync-advisory-spec.md` v0.1 (unblocks both feature build plans). Open 1 [partial], Open 2 [partial], Open 3 [ ], Open 4 [partial], Open 5 [ ], Open 6 [x]. |
