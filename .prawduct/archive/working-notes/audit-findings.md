# Audit Findings — Prawduct Framework

Created: 2026-02-19
Author: External audit (Claude Opus 4.6, unprompted analysis)
Scope: Full repository audit — architecture, skills, governance, testing, adoption, systemic risks

---

## Executive Summary

Prawduct is a meta-framework that teaches an LLM how to be a product thinker, architect, and quality enforcer. Built in 10 days (170 commits), it demonstrates genuine insight into the failure modes of LLM-assisted development. The core thesis — that the bottleneck isn't code generation but *product thinking* — is correct and timely.

The framework shows signs of its rapid evolution. Governance infrastructure has grown to rival productive content in weight and complexity. The system is heavily self-referential, which creates both its greatest strength (dogfooding) and its greatest risk (insularity).

---

## What's Working Well

1. **Structural characteristics model** — the concerns→shapes→characteristics evolution is genuinely elegant. Five composable booleans solve the "where does earbud firmware fit?" problem without enumeration.
2. **Principles document** — HR1-HR10 are specific, actionable, and non-obvious. One of the best articulations of LLM-assisted development governance available.
3. **Critic-as-subagent pattern** — independent review context for quality checks is an innovation the broader LLM tooling ecosystem should adopt.
4. **Change log with retrospectives** — honest, insightful post-mortems on directional changes. Excellent engineering practice.
5. **Observation system** — even at C8a maturity, provides a genuine learning loop most frameworks lack entirely.
6. **"Generality Over Enumeration" principle** — philosophically rigorous and practically effective, with demonstrated self-application (three rounds of de-enumeration).

---

## Findings by Area

### 1. Product Vision & Positioning

**Assessment: Strong thesis, unclear market.**

The vision nails the problem. The solution is sound. But:

- **Target persona is too broad.** "Anyone building software with LLM assistance" ranges from non-technical hobbyists to senior engineers. The governance machinery will overwhelm the former; the latter may bristle at the paternalism. The sweet spot appears to be mid-level developers building real products who lack product/architecture experience — but this isn't stated.
- **"Not a code generator" is a positioning problem.** Users will expect end-to-end delivery. The Builder exists but the framework's identity as "the thinking before and around code" may frustrate expectations.
- **No competitive landscape.** Cursor rules, Aider conventions, Copilot Workspace, and the growing "vibe coding" guardrail ecosystem are unaddressed. The answer is probably "those tools are shallow pattern-matching; this is structured product methodology" — but it needs to be said.

**Recommendation:** Sharpen positioning around a specific persona. Write a Jobs-to-Be-Done analysis. Address the competitive landscape honestly.

### 2. Architecture & Design

**Assessment: Thoughtful with real elegance, but complexity approaching a critical threshold.**

**Strengths:** Layered design (Conversation→Production→Quality), skills as inspectable markdown, hooks as mechanical enforcement that survive context compaction.

**Concerns:**

- **Token budget pressure.** CLAUDE.md (~6k tokens) + Orchestrator + stage file + project-state.yaml = 15-20k tokens of framework overhead before the user speaks. For a ~200k context window, that's 10% consumed by process. The Critic-as-subagent migration was a good move, but this is systemic.
- **Six lifecycle hooks on every tool call.** Each hook is a shell→Python→JSON parse→state read→classify→decide→state write→trace chain. On builds with hundreds of edits, this latency compounds. There's no measurement of this overhead anywhere.
- **project-state.yaml is a monolith despite splits.** 644 lines with multiple concerns co-located. The compaction tool was itself non-compliant until enforcement was added — if the framework can't keep its own state lean, user products will fare worse.
- **C7 (Trajectory Monitor) is "v1.5" but its job is being done ad hoc.** Session-health-check, governance hooks, and the Critic all detect drift piecemeal. No unified trajectory view exists.

**Recommendation:** Instrument hook latency. Set a per-session token budget for framework overhead and enforce it. Consider whether project-state.yaml should become a directory of small files rather than a monolith with compaction.

### 3. Skills & Agent System

**Assessment: The skill design is the best part of the framework.**

The six skills are well-differentiated and well-scoped. Domain Analyzer's universal dimensions, Artifact Generator's three-layer approach, and the Critic's applicability table are all well-designed.

**Concerns:**

- **Builder skill needs cognitive guardrails, not domain recipes.** At 239 lines, the Builder is the thinnest skill with the hardest job. However, the right investment is NOT stack-specific instructions ("how to translate to React") — the model knows that, and static instructions would be worse than its training data. The right investment is **implementation-time reasoning protocols** that address LLM-specific failure modes during code generation:
  - Silent requirement dropping under context pressure (re-read spec after implementing N of M requirements)
  - Self-confirming test patterns (test passes first try on non-trivial logic = verify it exercises failure paths)
  - Ambiguity swallowing (cross-artifact constraints conflict at implementation time → surface, don't silently choose)
  - State tracking across files (implementation spans multiple files → verify consistency)

  These are cognitive guardrails for a specific kind of agent doing a specific kind of task — the same shape as the Domain Analyzer's discovery dimensions or the Critic's check architecture. They should grow from observed build failures (via the observation system), not from imagination.

- **Review Lenses / Critic overlap.** Both evaluate quality with significant instruction overlap. The backlog item "Critic-Review Lenses bidirectional integration" acknowledges this isn't resolved.
- **Skill interaction is all Orchestrator-mediated.** No direct skill-to-skill communication limits real-time adaptation.

**Recommendation:** Watch the Builder closely during real product builds. The failure modes that emerge won't be "the LLM didn't know how to write React" — they'll be reasoning-process gaps. Capture those as Builder instructions when the observation system surfaces them. Consider whether Review Lenses should be absorbed into the Critic's check applicability table.

### 4. Governance System

**Assessment: Impressive engineering, bordering on over-governance.**

**Strengths:** Mechanical enforcement surviving compaction, structured evidence over keyword matching, three-tier DCP proportionality, session tracing.

**Concerns:**

- **Governance-to-content ratio is 3.5:1.** Tools (governance + utilities): ~8,800 lines. Skills (actual methodology): ~2,500 lines. This was recognized internally ("Governance infrastructure exceeded instruction content") but the ratio remains high.
- **Self-referential governance loop.** Changes to governance → trigger governance hooks → require Critic review → produce findings → governance stop validates → governance tracker records. A bug in the governance module can lock the entire system. The `.session-governance.json.bak` file suggests this has already happened.
- **HR9 floor is high.** Even with proportionality (cosmetic/functional/directional), the structural overhead (hooks, state files, observation capture) is constant regardless of product risk level.
- **No escape hatch.** No `--skip-governance`, no expert mode, no acknowledged bypass. Every serious development tool has one (git `--force`, ESLint `eslint-disable`). The absence isn't principled — it's a bet that governance never blocks legitimate work, which the observation backlog contradicts.

**Recommendation:** Add a lightweight "acknowledged bypass" mechanism that logs the bypass, requires explicit user confirmation, and captures it as an observation. Preserves learning without blocking expert users. Measure and publish governance overhead per session.

### 5. Self-Improvement System

**Assessment: Most novel aspect, most incomplete.**

**Strengths:** Observation-as-side-effect philosophy is excellent. 93 observations with RCA demonstrate the system works.

**Concerns:**

- **C8 is 1/5 built.** Observer works. Pattern detection is partial. Validation, Incorporation, and Retirement are not built. Human must triage all observations.
- **93 observations in 10 days (~9/day).** Backlog will overwhelm triage capacity within a month without automated pattern grouping.
- **Contribution pipeline untested at scale.** The GitHub issue mechanism is plumbed but unused in multi-product context.

**Recommendation:** Prioritize C8b (Pattern Extractor) over new features. Consider whether 17 observation types with full RCA is capturing more metadata than can be acted on.

### 6. Testing & Validation

**Assessment: Sophisticated methodology, thin coverage.**

**Strengths:** Scenario-based evaluation with concrete rubrics. Governance module unit tests (996 lines).

**Concerns:**

- **3 scenarios for "every product type."** No API-only, no multi-party platform, no `handles_sensitive_data` product, no mobile app. Enormous gaps.
- **No automated regression testing.** Evaluation requires manual LLM execution. Regressions can ship undetected between evaluations.
- **Multiple re-runs of family-utility** in eval-history suggest overfitting to test scenarios.

**Recommendation:** Add 3+ scenarios immediately (API-only, multi-party, sensitive-data). Invest in smoke-test automation ("does the framework produce all expected artifacts for scenario X?").

### 7. Developer Experience & Adoption

**Assessment: Optimized for its creator, not for new users.**

- **Installation requires multiple steps** (clone framework, run init, understand hooks, understand framework-path).
- **No quick start.** No `prawduct new my-app` → working project in 30 seconds.
- **CLAUDE.md is instruction-dense** before the user reaches New User Orientation.
- **No examples of finished products.** No way to assess output quality before committing.

**Recommendation:** Create a `prawduct new` command for zero-friction setup. Build and showcase 2-3 complete products. Write a 5-minute quickstart that gets to first artifact without requiring governance system understanding.

### 8. Code Quality

**Assessment: Generally high with some concerning patterns.**

- **Shell/Python interleaving.** Entry point is bash calling Python. Several large shell scripts (session-health-check.sh at 966 lines) do heavy string processing that Python would handle better. Historical artifact of incremental evolution.
- **prawduct-init.py at 1,490 lines.** Handles setup, repair, migration, schema versioning, hook merging, gitignore management. Should be multiple modules.
- **No type hints** on the Python governance module beyond dataclasses.
- **`__pycache__` present** in the repository.

**Recommendation:** Migrate large shell scripts to Python. Add type hints to governance module. Split prawduct-init.py into a package.

---

## Systemic Risks

### Complexity Spiral
Self-referential governance creates a ratchet: observations → work → governance → traces → observations. 75 commits in 3 days (Feb 15-18) — mostly governance and meta-process — suggest the framework spends more energy governing itself than improving product-building capability.

### Context Window Arms Race
Framework overhead + project state + codebase context compete for the same window. Compaction treats symptoms. The real question: can a single-context LLM architecture scale to large products, or does the framework need multi-agent orchestration with dedicated context per concern?

### Single-Runtime Dependency
Deep integration with Claude Code's hooks, file tools, and `$CLAUDE_PROJECT_DIR`. The v1.5 "agent agnosticism" backlog item acknowledges this, but current architecture would require substantial rewriting for Cursor/Aider/etc.

### Uncanny Valley of Governance
Too heavy for hobbyists, too light for enterprise (no RBAC, no multi-user, no audit trails beyond local files). Proportionality is implemented at question/review depth, but structural overhead (hooks, state, observations) is constant regardless of product risk.

---

## Prioritized Recommendations

| # | Recommendation | Rationale |
|---|---------------|-----------|
| 1 | **Measure and cap governance overhead** (tokens, latency, gate blocks per session) | Can't improve what you can't measure; overhead is the #1 adoption risk |
| 2 | **Grow Builder from observed build failures** — cognitive guardrails for LLM implementation failure modes, not stack recipes | Spec-to-code gap is where value is delivered; guardrails should emerge from the observation system |
| 3 | **Add an acknowledged bypass mechanism** | Governance without escape hatches drives away power users |
| 4 | **Create a zero-friction quickstart** | Setup ceremony kills adoption before value is demonstrated |
| 5 | **Add 3+ test scenarios** (API-only, multi-party, sensitive-data) | 3 scenarios for "every product type" is insufficient validation |
| 6 | **Prioritize C8b (Pattern Extractor)** | Observation volume will overwhelm manual triage within weeks |
| 7 | **Migrate large shell scripts to Python** | 966-line bash is a maintenance liability |
| 8 | **Resolve Review Lenses / Critic overlap** | Two quality-evaluation skills with unclear boundaries creates confusion |
| 9 | **Sharpen target persona** | "Anyone building software with LLMs" is too broad to serve well |
| 10 | **Build and showcase complete products** | Nothing sells a framework like seeing what it produces |
