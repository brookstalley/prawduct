---
scenario: static-personal-site  # Ad-hoc test — not a defined scenario
date: 2026-02-10
evaluator: claude-interactive
framework_version: 7f85d26
result:
  pass: N/A
  partial: N/A
  fail: N/A
  unable_to_evaluate: N/A
  notes: "No formal rubric exists for this scenario. This was an ad-hoc test of the framework on a minimal static site to stress-test proportionality."
skills_updated:
  - skills/orchestrator/SKILL.md
  - skills/artifact-generator/SKILL.md
  - skills/domain-analyzer/SKILL.md
  - skills/review-lenses/SKILL.md
notes: "First test of framework on a product simpler than the family-utility baseline. Exposed four framework gaps, all addressed."
---

# Ad-Hoc Evaluation: Static Personal Site

## Scenario

User requested a one-page static HTML/CSS personal site for a job search. Product: minimal, no backend, no JavaScript, no interactivity. This is simpler than any of the five defined test scenarios.

## Purpose

Test whether the framework handles products at the low end of complexity gracefully, or whether its universal artifact set and process stages add disproportionate overhead.

## What Happened

The full pipeline ran: Stage 0 (classification) → Stage 0.5 (validation, skipped for low-risk) → Stage 1 (discovery, 2 rounds) → Stage 2 (product definition) → Stage 3 (artifact generation with phased review).

Seven universal artifacts were generated. All passed cross-artifact consistency checks and all four review lenses.

## Findings

### 1. No framework self-critique during use (blocking gap — now fixed)

The framework had no mechanism to prompt reflection on its own proportionality during product use. The Critic existed for post-hoc governance of framework changes, but nothing asked "is this step helping?" while running the pipeline. The user identified this gap.

**Fix:** Added Framework Reflection Protocol to the Orchestrator — self-critique at every stage transition.

### 2. Disproportionate artifacts for minimal products (warning — now fixed)

The security model, data model, and operational spec were mostly documenting the absence of their domains. A static site has no auth, no entities with relationships, and no operational complexity. The framework produced full artifacts anyway.

**Fix:** Added Applicability Assessment to the Artifact Generator — brief assessment before each artifact, with guidance to produce minimal artifacts when a domain is genuinely absent.

### 3. Risk profile missed execution quality bar (note — now fixed)

All standard risk factors (user count, data sensitivity, failure impact, technical complexity, regulatory exposure) came back low. But the product had genuinely medium stakes on design execution quality — a mediocre personal site during a job search has real consequences. The framework had no way to capture this.

**Fix:** Added "execution quality bar" as a sixth risk factor in the Domain Analyzer. Informational only (doesn't inflate overall risk), but available for downstream stages to calibrate design attention.

### 4. Review lenses didn't report framework proportionality (note — now fixed)

When a lens reviewed an artifact that was mostly documenting absence, it had no structured way to report "this artifact was disproportionate for this product type." Framework observations were implicit, not captured.

**Fix:** Added Framework Proportionality Observations section to the Review Lenses — a brief addendum to each lens application noting when artifacts or lens applications are disproportionate.

## What Worked Well

- **Discovery pacing was appropriate.** 1-2 rounds for low-risk, aggressive inference, batched questions. The user was not held hostage to process.
- **Classification was accurate.** UI Application + Content domain + Low risk was correct.
- **Proactive expertise added value.** Mobile responsiveness, ceramics gallery framing (craft not art portfolio), accessibility defaults — all surfaced considerations the user hadn't raised.
- **The Product Brief and Test Specifications were substantive.** Even for a minimal product, these artifacts carried their weight.
- **Review lenses caught one meaningful design risk.** The ceramics framing challenge (ensuring it reads as "depth of craft" not "art portfolio") was a genuine design execution concern.

## Recommendation for Framework

Consider whether a "static content" product shape (or sub-shape) warrants recognition. Static sites are a common product type that falls awkwardly into "UI Application" — they have a UI but no application logic, no state, and no interactivity. The current framework handles them via proportionality rules (which work), but explicit recognition could streamline artifact selection.

This is a Phase 2 consideration — the proportionality fixes in this session are sufficient for now.
