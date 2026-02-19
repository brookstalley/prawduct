# Test Scenario: Quick To-Do App (Happy Path)

## Purpose

Validates that Prawduct produces reasonable artifacts for a trivial product in one session. Covers the happy path through Stages 0-3 only (discovery → definition → artifact generation). No build stage. This is the minimum viability scenario — if the framework can't handle a simple to-do list, it can't handle anything.

## Product Description

"I want a simple to-do list app. Just for me, on my phone. Add tasks, check them off, delete them."

## Structural Characteristics

- `has_human_interface`: true (modality: screen, platform: mobile)
- `runs_unattended`: false
- `exposes_programmatic_interface`: false
- `has_multiple_party_types`: false
- `handles_sensitive_data`: false

## Risk Profile

- Overall: low
- Rationale: single user, no sensitive data, no external dependencies, simple domain

## Evaluation Rubric

### Stage 0: Intake & Triage (max 2 turns)

| Criterion | Pass | Fail |
|-----------|------|------|
| Classification speed | Classified within 1-2 exchanges | Asks 5+ questions before classifying |
| Risk calibration | Identified as low risk | Flagged as medium/high risk |
| Structural accuracy | `has_human_interface` detected | Missed or added wrong characteristics |
| Proportionality | Light-touch — no unnecessary complexity | Asks about enterprise features, compliance, multi-user |

### Stage 1: Discovery (max 3-4 turns)

| Criterion | Pass | Fail |
|-----------|------|------|
| Question relevance | Asks about core task flow, platform, data persistence | Asks about monetization, scaling, team collaboration |
| Question count | 3-6 focused questions | 10+ questions for a to-do app |
| Pacing sensitivity | Moves quickly for low-risk | Holds user hostage to thorough discovery |
| Domain-appropriate | Questions fit a personal utility | Questions assume enterprise or multi-user context |

### Stage 2: Definition

| Criterion | Pass | Fail |
|-----------|------|------|
| Scope clarity | v1 scope is 3-5 core features | Scope includes 10+ features or "later" list is empty |
| Persona accuracy | Single user persona, reasonable needs | Multiple personas or enterprise user types |
| Technical decisions | Simple, appropriate choices stated as assumptions | Over-engineered (database server for a to-do app) |
| Completeness | Vision, personas, flows, scope, NFRs all set | Missing core definition fields |

### Stage 3: Artifact Generation

| Criterion | Pass | Fail |
|-----------|------|------|
| Artifact count | 7 universal artifacts generated | Missing artifacts or extra unnecessary ones |
| Content proportionality | Artifacts are concise for low-risk | Product brief is 5+ pages for a to-do app |
| Data model accuracy | Entities match the described flows (Task entity minimum) | Missing entities, over-modeled, or wrong relationships |
| Test spec appropriateness | 5-15 test scenarios, proportionate | 30+ scenarios or missing core flow coverage |
| Review findings | 2-6 findings, mostly notes | 15+ findings or blocking findings for a trivial app |
| Cross-artifact consistency | Artifacts reference each other correctly | Data model doesn't match flows in product brief |

### Overall Quality

| Criterion | Pass | Fail |
|-----------|------|------|
| Session length | Stages 0-3 complete in under 15 exchanges | 25+ exchanges for a to-do app |
| Discovery → artifact fidelity | Artifacts reflect what was discussed in discovery | Artifacts include features never discussed |
| Proportionality throughout | Process was lightweight for a low-risk product | Any stage felt like overkill |
| User engagement | Would a real person stick with this conversation? | Process is tedious enough to abandon |

## Scoring

- **Total criteria:** 20
- **Pass threshold:** 16/20 (80%)
- **Critical failures (auto-fail):** Asks about enterprise features for a personal to-do app; generates disproportionately complex artifacts; takes more than 20 exchanges through Stage 3
