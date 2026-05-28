# Open 4 — Critic adaptive classification + applicability reasoning: Results

Tests whether the Critic in `llm-prompt` mode can produce sensible findings with traceable reasoning when given a chunk diff, a prompt-strategy artifact, and the failure-mode catalog. Success requires findings that match what a thoughtful human reviewer would surface, reasoning trails per finding, no flagrant misapplications, and (for multi-model chunks) correct per-model check differentiation.

Per the empirical-testing-plan §5 Open 4 method, this open requires four test chunks. This file records the first one — the **Category B (runtime-instruction) chunk**, which was added to the test method in the v0.2 spec update. Chunks 1-3 (Category A: Haiku-classifier, Opus-agent, multi-model role) are pending and require Critic-mode-llm-prompt implementation to run as an end-to-end test.

The Category B chunk is runnable *now* as a manual desk review because:
- The applicable failure-mode subset is statically determined by §7.3 Rule A (the catalog is tagged)
- The artifact (this skill) exists
- The "Critic" can be approximated by a careful manual application of the catalog

---

## Run 2026-05-28 — Chunk 4 (Category B)

### Test artifact

**Role under review:** Prawduct's own Critic skill (`agents/critic/SKILL.md`, 207 lines)

Hypothetical inventory entry the artifact would declare:
```
### critic-skill
- **Kind:** runtime-instruction
- **Vendor:** Anthropic (Claude Code runtime)
- **Model:** claude-* (runtime-determined — whatever the user's Claude Code is configured with)
- **Role description:** Independent quality reviewer invoked via /critic; reviews diffs against principles, requirements, learnings, and framework-specific checks
- **Prompt location:** agents/critic/SKILL.md (companion files: agents/critic/review-cycle.md, agents/critic/framework-checks.md)
- **Best practices applied:** TBD
- **Status:** v1 (in production)
- **Critic severity:** NOTE
```

### Applicable failure-mode subset (per §7.3 Rule A)

`kind: runtime-instruction` → only entries tagged `Applies-to (kind): both` apply. Excluded by Rule A: FM-1, FM-5 through FM-11, FM-14, FM-15, FM-18, FM-19 through FM-25 (18 entries, all api-call-specific).

Applicable: **FM-2, FM-3, FM-4, FM-12, FM-13, FM-16, FM-17, FM-26, FM-27, FM-28** (10 entries).

`Prompt location: <file path>` → Rule B does NOT fire; content-shape checks apply.

### Findings

#### Finding 1 — FM-13 confirms existing backlog item

**Failure mode:** FM-13 (Tool/function execution without confirmation gate)
**Severity:** NOTE (confirms existing backlog item)
**Pattern detected:** The Critic skill is documented as having a restricted tool surface (line 4 comment: "Tools: Read, Glob, Grep, git, wc, Write, Agent. NO test execution, NO builds"). The restriction is enforced via the framework's `allowed-tools` config, not via the prompt text. The existing backlog already flags that `Bash(git *)` is too broad — permits state-mutating verbs (checkout/stash/reset/branch).
**Reasoning:** Applied FM-13 because: kind=runtime-instruction AND the skill dispatches to tools without confirmation gates. The applicability is "confirmation gate" — and for a runtime-instruction artifact, the "confirmation gate" is the framework's `allowed-tools` enforcement. The current allowlist is too coarse.
**Empirical note:** The catalog independently surfaced an issue already in the backlog. This is a positive validation of FM-13's `Applies-to (kind): both` tagging — the failure mode does apply to runtime-instruction artifacts when "tool execution" means "what tools the runtime is allowed to dispatch under this prompt."
**Fix-shape:** Narrow `Bash(git *)` to read-only git verbs (`Bash(git status:*)`, `Bash(git diff:*)`, `Bash(git log:*)`, `Bash(git rev-parse:*)`, etc.). This is the existing backlog item; no new action needed.

#### Finding 2 — FM-12 forward-looking blocker

**Failure mode:** FM-12 (Untrusted input concatenated into system/instruction context)
**Severity:** NOTE *currently* — will become BLOCKING when LLM-mode lands
**Pattern detected:** The current Critic skill does not ingest external content beyond the project's own files (own code, own state, own git diff). FM-12 does not fire on the current artifact. However, the prompt-management-requirements §7.4 specifies that the new `llm-prompt` Critic mode will have `WebFetch` and `WebSearch` access with open scope, and §15 Q5 (lean a+c) requires explicit `<untrusted>` wrapping of fetched content before Critic processing.
**Reasoning:** Applied FM-12 because: kind=runtime-instruction AND a future build plan will extend this skill to ingest untrusted web content. The applicability becomes hard the moment that change lands.
**Fix-shape:** When the prompts-feature build plan implements `llm-prompt` mode, the SKILL.md content must include: (a) explicit instruction to wrap fetched content in `<untrusted>` tags before reasoning over it, (b) a prose reminder to treat fetched content as data rather than instructions. Document as a precondition for the build plan, not a current fix.
**Empirical observation about temporal applicability:** The catalog needs a way to express "this failure mode is currently dormant on this artifact but becomes applicable when feature X ships." Possible mechanism: a per-finding `applies-when:` field in the artifact, populated by the Critic. Worth filing as a meta-observation.

#### Finding 3 — FM-16 real gap

**Failure mode:** FM-16 (No pinned-fixture eval set for each LLM-using function)
**Severity:** WARNING
**Pattern detected:** The framework's tests cover Critic *metadata* (`tests/test_critic_skill_metadata.py`) and *mode inference* (`tests/test_critic_mode_inference.py`) but NOT the Critic's *review output quality* on canonical diffs. There's no "given this golden chunk, the Critic should produce these findings" regression suite. Changes to SKILL.md, review-cycle.md, or framework-checks.md could regress review quality silently.
**Reasoning:** Applied FM-16 because: kind=runtime-instruction AND the skill *is* an LLM-using function (the LLM is Claude-the-runtime). Regression strategy is unaddressed for review-output quality.
**Fix-shape:** Backlog item — design a fixture set of 5-10 representative chunk diffs with expected finding shapes (severity + goal + presence of specific patterns). Run as a CI gate on changes to skill files. Could use LLM-as-judge with a pinned judge model for fuzzy comparison of free-form findings text against expected shapes.

#### Finding 4 — FM-27/FM-28 small-model variant gap

**Failure modes:** FM-27 (CoT prompting on small models), FM-28 (Frontier-model patterns on small models)
**Severity:** NOTE
**Pattern detected:** The Critic skill is dense (207 lines for SKILL.md + ~21KB across companion files). Multi-goal structured reasoning (Goals 1-7, framework-specific checks, learnings cross-check, backlog reconciliation) implicitly assumes a Sonnet/Opus-class runtime. The framework doesn't declare a minimum runtime tier and doesn't ship a small-model fallback variant.
**Reasoning:** Applied FM-27/28 jointly because: kind=runtime-instruction AND the prompt is multi-stage + reasoning-intensive, with no per-tier variant. A user running Claude Code with a Haiku-class default model would get degraded Critic output.
**Fix-shape:** Either (a) declare "Critic requires Sonnet 4.5+ runtime; behavior on smaller models is undefined" in the skill description, or (b) author a `critic-simple.md` variant for small-model use that focuses on Goals 1-3 only and omits framework-specific / learnings / reconciliation steps. (a) is cheaper; (b) is more useful.

#### Finding 5 — FM-3 marginal XML structure

**Failure mode:** FM-3 (Plain-text role/data mixing — Claude XML recommendation)
**Severity:** NOTE
**Pattern detected:** The skill is markdown with headers + lists + code fences. Anthropic's prompt-engineering docs recommend XML structure for high-stakes Claude prompts. Markdown headers provide structural delimiting; XML tagging would be marginally tighter. One specific place to consider: the subagent prompt template (line 147) is a blockquote with substitution markers but no XML wrapping:
```
> "Critic review subagent (`<NAME>`). Read `[critic path]` for goal definitions. Review ONLY <GOALS>. Project: `[dir]`. Changed files: [list]. Signals: [summary]. NO tests — code analysis only. Report using the Critic output format."
```
Could be `<subagent-prompt name="<NAME>" goals="<GOALS>">...</subagent-prompt>` for clarity.
**Reasoning:** Applied FM-3 because: kind=runtime-instruction AND Vendor=Anthropic. The applicability is real but the impact is marginal — markdown is structurally adequate.
**Fix-shape:** Defer. Not worth disrupting a working skill for marginal structural improvement. File as an aesthetic NOTE.

#### Failure modes that did NOT apply (or applied with no finding)

- **FM-2 (Instructions after long context):** Imperative content ("Review Goals") starts at line 42 of 207 (~20% in). Auxiliary content (output format, review cycle, extension) trails. Pattern not present.
- **FM-4 (Few-shot examples mis-placed):** Not a few-shot prompt; examples in the text are illustrative within instructions, not few-shot exemplars.
- **FM-17 (Free-text substring assertions):** Tests of the framework's handling assert on JSON-shape outputs (`.critic-findings.json`), not free-text. Structurally correct.
- **FM-26 (No agent step-count circuit breaker):** The Critic is not an agentic loop. It's a single-pass review (or 3-way fan-out + aggregate). No recursion. No step-count concern.

### Findings summary

| Severity | Count | Failure modes |
|---|---|---|
| BLOCKING | 0 | — |
| WARNING | 1 | FM-16 |
| NOTE | 4 | FM-13 (confirms backlog), FM-12 (forward-looking), FM-27/28 (joint), FM-3 (marginal) |
| Did not apply | 4 | FM-2, FM-4, FM-17, FM-26 |

---

## Verdict against Open 4 success criteria

| Criterion | Status | Notes |
|---|---|---|
| Findings match what a thoughtful human reviewer would surface | **PASS** (qualitative) | Each finding is defensible; FM-13 independently confirmed an existing backlog item, which is positive validation. |
| Reasoning trail explains *why* each FM applied to this role | **PASS** | Every finding includes a "Reasoning" paragraph naming the rule(s) applied (Rule A narrowing + per-FM justification). |
| No flagrant misapplications | **PASS** | FM-2/4/17/26 correctly did not apply. FM-3 applies marginally and is severity-appropriate. The Rule A narrowing correctly excluded the 18 api-call-only entries — none surfaced as a finding. |
| Multi-model chunk correctly applies different checks per model | **N/A** (single-role chunk; deferred to Chunks 1-3) | — |

---

## Empirical observations

1. **Rule A narrowing worked cleanly.** None of the 18 `api-call`-tagged failure modes produced false-positive findings on the runtime-instruction chunk. The catalog tagging from Step 3 of today's edit pass holds up empirically.

2. **The catalog confirmed an existing backlog item (FM-13).** This is the strongest signal of catalog usefulness — independent application of a published catalog surfaces an issue we already knew about. Validates the `both` tagging on FM-13.

3. **Temporal applicability is a real concern (FM-12).** The catalog as currently structured assumes static applicability. But Critic skills evolve: the prompt-management build plan will add web fetching to `llm-prompt` mode, at which point FM-12 transitions from "does not apply" to "BLOCKING." The Critic needs to either (a) emit forward-looking NOTEs that anticipate planned changes, or (b) the planning process needs to surface "feature X will activate failure mode Y on artifact Z" during chunk design. **Worth filing as a meta-observation for the prompts-feature build plan.**

4. **FM-27/FM-28 surface a design question.** The framework doesn't declare a minimum runtime tier for the Critic. Real users on Haiku-class default models would get degraded review. Either declare the requirement or ship a small-model variant.

5. **FM-16 is a real, currently-unfilled gap.** No regression-test fixture set for the Critic's output. This is exactly the kind of finding the catalog should produce on a Category B artifact — and we didn't have one filed in the backlog yet. **Worth filing as a backlog item.**

6. **The 10-entry applicable subset is the right size for a runtime-instruction review.** Took ~15 minutes of focused manual application; an agentic Critic could do it faster. The full 28-entry catalog would have included 18 false-positive considerations (each requiring "does this apply?" then rejecting). Rule A narrowing is doing real work.

7. **One catalog gap surfaced:** FM-3's `Applies-to (kind): both` is correct but the *severity* of the application differs sharply between a Category A Claude-API call (where XML structure has measurable effect on output quality) and a Category B markdown skill (where markdown headers serve a similar structural role with marginal difference). The catalog might benefit from a "Strength of applicability per kind" note: "FM-3 fires strongly for api-call kind; fires weakly for runtime-instruction kind where markdown structural delimiting is acceptable." Could be a future refinement to the catalog tagging.

---

## Outstanding work / next runs

- **Chunks 1, 2, 3 (Category A: Haiku-classifier, Opus-agent, multi-model role)** — require Critic-mode-`llm-prompt` implementation to run as end-to-end tests. Could be approximated as manual desk reviews but the value of the desk-review approach is lower for Category A (the catalog's api-call entries are heavily about API-surface patterns that need actual code under review, not just a chunk description).
- **Backlog items to file from this run:**
  - FM-16-class: design a fixture-based regression suite for Critic output quality
  - FM-27/28-class: declare Critic minimum runtime tier or author a small-model variant
  - Meta: design "forward-looking applicability" mechanism in the Critic's finding output (see observation 3)
  - Meta: consider per-kind strength qualifier on catalog entries (see observation 7)

---

## Status

- [partial] Open 4 first run 2026-05-28 — Category B chunk (the prawduct Critic skill) complete; reasoning traceable; FM-13 cross-validation with the existing backlog. Chunks 1-3 (Category A) pending Critic-mode implementation.
