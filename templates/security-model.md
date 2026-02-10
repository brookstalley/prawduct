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
depended_on_by:
  - artifact: test-specifications
  - artifact: operational-spec
last_validated: null
---

# Security Model

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
     - High-risk: fine-grained permissions, audit trails -->

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
