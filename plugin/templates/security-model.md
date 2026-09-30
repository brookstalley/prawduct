<!-- Security Model Template

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

<!-- OPTIONAL norm home. To record a norm, add a `## Direction` heading with entries (a bold
     **Statement.**, then `Why:`, `Status:`, optional `Retroactivity:` / `Rulings:`) — anatomy
     and rules: /prawduct:methodology norms. Add the heading only with a real entry: the
     advisory probes read a bare `## Direction` heading as ratified norms. With no norms, leave
     this comment; "none to ratify" is recorded through /prawduct:doctor, not here. -->

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
