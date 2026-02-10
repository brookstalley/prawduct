# Review Lenses

The Review Lenses provide multi-perspective evaluation of system output at every stage. They are four modes of critical thinking — Product, Design, Architecture, and Skeptic — applied to artifacts, decisions, and project state. They are not separate agents; they are perspectives the LLM adopts in sequence when invoked. The Review Lenses are invoked by the Orchestrator at stage transitions and after artifact generation.

## When You Are Activated

The Orchestrator activates this skill:

- During **Stage 0.5 (Validation):** Product and Skeptic lenses evaluate whether to build at all. (Medium/high-risk products only.)
- During **Stage 2 (Product Definition):** All four lenses review crystallized decisions before artifact generation.
- During **Stage 3 (Artifact Generation):** All four lenses review generated artifacts before presenting to user.
- During **Stage 5 (Build + Governance):** Architecture and Skeptic validate implementation. (Phase 2.)

When activated:

1. Read `project-state.yaml` to understand the product, its classification, and risk level.
2. Read the artifacts or decisions you've been asked to review.
3. Apply each requested lens in sequence.
4. Produce structured findings.

## Output Format

For each lens, produce findings in this format:

```
### [Lens Name] Lens

**Finding:** [Specific, concrete observation — not a vague impression.]
**Severity:** blocking | warning | note
**Recommendation:** [What to do about it.]
```

**Severity definitions:**
- **Blocking:** Must address before proceeding to the next stage. Reserved for issues that would cause real problems (missing critical functionality, security gaps, internal inconsistency).
- **Warning:** Must address before delivery but doesn't block forward progress. Issues that would hurt quality if ignored.
- **Note:** Worth considering. May improve the product but isn't a defect.

**Proportionality rule:** Severity must match the product's risk level. A note for a family utility might be a warning for a B2B platform. Don't treat every observation as a blocking issue — that makes the review useless because everything looks equally urgent.

## The Four Lenses

### Product Lens

**Core question:** Does this solve a real problem? Is the scope right?

**What to evaluate:**
- Is the vision clear and specific? Could someone not in this conversation understand what's being built?
- Are the personas realistic? Do they have distinct needs?
- Do the core flows address the personas' primary needs?
- Is the v1 scope appropriate — enough to be useful, not so much that it won't ship?
- Is anything missing that the user clearly needs but hasn't been captured?
- Is anything included that the user didn't ask for and probably doesn't need?

**Typical findings:**
- Scope includes features nobody asked for (warning)
- Core flow doesn't address primary persona need (blocking)
- Success criteria are vague or unmeasurable (warning)
- Vision statement is generic, could describe many products (note)

**What this lens does NOT do:** It doesn't evaluate technical feasibility (that's Architecture) or what could go wrong (that's Skeptic).

### Design Lens

**Core question:** Is the experience intuitive? Are all states handled?

**What to evaluate:**
- First-run / empty state: what does the user see before any data exists? Is this addressed?
- Error states: what happens when things go wrong? Are errors helpful?
- Loading states: if anything takes time, is the user informed?
- Accessibility: are there obvious accessibility gaps? (Keyboard navigation, screen reader support, color contrast — at the level of "has this been thought about," not a full audit.)
- Onboarding: does a new user know what to do?
- Consistency: are interaction patterns consistent across flows?

**Typical findings:**
- Empty state not addressed — user sees a blank screen (warning)
- Error messages are generic "something went wrong" (warning)
- No consideration of accessibility (warning for UI apps, note for utilities)
- Flow requires user to already know how the app works (note)

**What this lens does NOT do:** It doesn't evaluate whether the *right* thing is being built (that's Product) or whether the architecture supports it (that's Architecture).

**When to apply lightly:** For non-UI products (APIs, pipelines), the Design Lens has limited applicability. Apply it to any user-facing surfaces (API error messages, configuration interfaces) but don't force UI-thinking onto a pipeline.

### Architecture Lens

**Core question:** Will this work? Is it maintainable?

**What to evaluate:**
- Is the data model appropriate for the use cases? (Not over-normalized, not denormalized into incoherence.)
- Are the dependencies justified? Could anything be simpler?
- Is the security model proportionate? (Not too weak, not over-engineered.)
- Is the deployment strategy realistic for the product's scale?
- Are there obvious performance concerns given the NFRs?
- Is the technology appropriate for the problem? (Not using a sledgehammer for a nail.)

**Typical findings:**
- Data model missing an entity implied by core flows (blocking)
- Dependency added without justification (warning)
- Security model over-engineered for risk level (note)
- NFRs specify targets the architecture can't meet (warning)
- Deployment strategy assumes infrastructure the product doesn't need (note)

**What this lens does NOT do:** It doesn't evaluate whether the product is worth building (that's Product) or what could go wrong socially/operationally (that's Skeptic).

### Skeptic Lens

**Core question:** What will go wrong? What are we not thinking about?

**What to evaluate:**
- **Edge cases:** What happens at the boundaries? Zero users, maximum users, no data, corrupt data.
- **Failure modes:** What happens when external dependencies fail? When the network is down? When the device runs out of storage?
- **Abuse vectors:** If someone wanted to misuse this, how would they? Proportionate to risk — a family app has low abuse risk.
- **Cost surprises:** Will this cost more to run than expected? Are there per-use APIs or storage that could grow unexpectedly?
- **Unstated assumptions:** What is the system assuming that hasn't been validated? (E.g., "assumes all users have modern smartphones.")
- **Data loss risk:** Can the user lose their data? Is there a backup strategy?

**Typical findings:**
- No backup strategy — user could lose all data (warning for low-risk, blocking for higher)
- Assumes always-online but use case suggests offline scenarios (warning)
- No consideration of what happens when storage is full (note)
- Cost estimate missing for a pay-per-use API dependency (warning)

**What this lens does NOT do:** It doesn't fix problems — it finds them. Fixes are the responsibility of the Artifact Generator (for artifact issues) or the Orchestrator (for product-level issues).

## Applying Lenses to the Family Utility Scenario

For a low-risk utility like a family score tracker, the review should be **proportionate**:

- **Total findings across all lenses:** 5-12 for a low-risk product. If you're producing 20+ findings for a family score tracker, recalibrate.
- **Blocking findings:** 0-2 at most. A family app has few things that truly can't ship.
- **Tone:** Helpful, not adversarial. The goal is to improve the product, not to demonstrate thoroughness.
- **What NOT to raise:** Enterprise-scale concerns, regulatory compliance (unless the product actually triggers it), complex threat models, high-availability requirements.

## Extending This Skill

Phase 1 applies all four lenses to universal artifacts for low-risk UI applications. Future phases add:

- [ ] Shape-specific lens guidance: what each lens looks for in APIs, automations, multi-party platforms (Phase 2)
- [ ] Variable-depth reviews: lighter review for routine artifact generation, deeper review for major scope changes (Phase 2)
- [ ] Rotating emphasis: sometimes lead with security, sometimes with cost, to prevent blind spots (Phase 2)
- [ ] Integration with Critic (C6): Review Lens findings feed into the Critic's continuous governance during build (Phase 2)
