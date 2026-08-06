<!-- Security Model Template
     Tier: 1 (Source of Truth)
     Owner: Artifact Generator (C3)

     Usage: Copy this template to your project's artifacts/ directory.
     The security model must be proportionate to the product's risk profile.
     A low-risk family utility gets simple, lightweight security. A B2B
     financial platform gets comprehensive controls. If you're writing about
     OAuth and RBAC for a family score tracker, you've over-engineered it.
-->
---
artifact: security-model
version: 1
depends_on:
  - artifact: product-brief
  - artifact: data-model
last_validated: null
---

# Security Model

<!-- OPTIONAL norm home ("Direction"). To record a norm, add a `## Direction` heading here with
     entries — each: a bold **Statement.**, then `Why:` (required), `Status:` (steady-state |
     in-transition + its tracking item), and optional `Retroactivity:` / `Rulings:` lines.
     Normative statements BIND future work — not descriptions of current behavior. Norms bind;
     descriptions track — see /prawduct:methodology norms for the anatomy, the
     normative-vs-descriptive test, and the lifecycle rules. Add the heading ONLY with a real
     entry: a bare `## Direction` heading reads as ratified norms to the advisory probes. A
     product with no norms to declare leaves this comment as-is — "none to ratify" is recorded
     owner-confirmed through the doctor's Norm Ratification Flow (/prawduct:doctor), never as a
     side effect of authoring this artifact. Don't restate the rules here.
     The upstream dependency intake policy (the `## Upstream Dependencies` section below) is
     norm-shaped and lands HERE as an entry — it binds what future work may take in, rather
     than describing what the product already does. -->

## Authentication

<!-- How do users identify themselves?
     Proportionate to risk:
     - Low-risk family app: device-level identification, simple name picker
     - Medium-risk: email/password, social login
     - High-risk: MFA, OAuth, SSO
     Source: classification.risk_profile, product_definition.users -->

## Authorization

<!-- Who can access what? What data is shared vs. private?
     Define access rules for each entity/resource from the Data Model.
     Proportionate to risk:
     - Low-risk: minimal or no access control (everyone in the family sees everything)
     - Medium-risk: role-based access
     - High-risk: fine-grained permissions, audit trails

     If the product exposes an API (exposes_programmatic_interface), check the
     OWASP API Top 10 *design* failure modes — distinct from the authentication above:
     - Broken object-level authz (BOLA): every object access verifies the caller may see THAT object, not just that they're authenticated
     - Mass assignment: bind only client-settable fields; never let a request set internal/privileged attributes
     - Excessive data exposure: return only the fields the consumer needs; don't rely on the client to filter
     See the api-contract artifact's Security checklist (templates/api-contract.md). -->

## Data Privacy

<!-- What data is collected? How is it stored? Who can see it?
     Address:
     - Data classification (what's sensitive, what's not)
     - Storage approach (local, cloud, encrypted?)
     - Data retention (how long is data kept?)
     - Regulatory requirements (GDPR, COPPA, etc.) if applicable -->

## Abuse Prevention

<!-- What could go wrong if someone acts maliciously?
     Proportionate to risk:
     - Low-risk family app: minimal abuse vectors (maybe input validation)
     - Medium-risk: rate limiting, input sanitization, spam prevention
     - High-risk: fraud detection, content moderation, account takeover prevention -->

## Upstream Dependencies

<!-- On what terms does code someone else releases enter this product?

     The six clauses, the three enforcement tiers, and the per-ecosystem mapping
     are the framework's, stated once in `docs/upstream-dependency-policy.md` in
     the prawduct plugin (not a path in this repo — it ships with the plugin).
     Do NOT restate them here — read them there and record THIS product's answers:

     - The chosen values, where they depart from the framework defaults, and why.
       The defaults themselves live in the spec; read them there rather than
       trusting a second copy that has drifted.
     - The declared trusted parties, EACH WITH ITS WHY. A bare list is not a
       register: a trusted party is an accepted risk, and the why is what makes it
       auditable and revisitable later.
     - The per-surface tier record — for each place upstream code enters (not only
       package manifests: base images, CI actions, submodules, vendored code,
       install scripts, extensions, model weights), which enforcement tier was
       actually REACHED. "Enforced at tier 3" is honest; a claim of coverage the
       product does not have is worse than no policy at all.

     This is norm-shaped — it BINDS future work, so it belongs in `## Direction`
     above as an entry with its Why, not as loose prose here. Each declared trusted
     party reads naturally as its own named entry.

     Proportionate to risk:
     - Low-risk: record the framework defaults and the intake surfaces; move on.
     - Medium-risk: name the trusted parties and the tier reached per surface.
     - High-risk: add the install-time-execution allowlist with reasons, and a
       named owner for the security fast path.

     A product that genuinely incorporates no upstream code records that in one
     line. Mirror the decision into `project-state.yaml` under
     `design_decisions.upstream_dependency_policy` — AND set the top-level
     `upstream_dependency_policy_decided` fact, which is the one that resolves the
     ambient nudge. Both, not either: the block is what the health check grades and
     the flat fact is all the advisory can see, so filling only the block leaves you
     decided and still being nagged for a mirror nobody asked you to set. -->
