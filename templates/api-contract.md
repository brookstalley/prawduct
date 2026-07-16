<!-- API Contract Template
     Tier: 1 (Source of Truth)
     Owner: Artifact Generator

     Usage: Copy to your project's artifacts/ as api-contract.md. Generate this
     when classification.structural.exposes_programmatic_interface is set.

     "API" here means ANY programmatic interface this product exposes for others
     to call — not just an HTTP/REST service. It includes a network service
     (REST, GraphQL, gRPC, message/event stream), a library / SDK / module
     (public functions, types, language bindings/FFI — versioned by semver), an
     on-device or platform↔app interface (OS framework API, app extension point,
     plugin interface, IPC/message bus), and a CLI (flags, exit codes, and
     output format ARE a contract). The decisions below apply to all of them;
     pick the examples that fit your surface and ignore the rest. Don't assume
     HTTP.

     Proportionate to risk: a low-risk internal interface gets a half-page; a
     public, multi-consumer one gets the full treatment. Skip sections that
     don't apply — say so and move on.

     Three sections are RECORDED decisions the framework tracks — mirror them
     into project-state design_decisions (api_versioning_approach,
     api_error_model_approach): the versioning scheme, the deprecation/
     compatibility policy, and the error model. "None — internal-only" is a
     valid recorded decision; a deferral must be dated and carry a revisit
     trigger. This is force-the-decision, not mandate-versioning.
-->
---
artifact: api-contract
version: 1
depends_on:
  - artifact: product-brief
  - artifact: data-model
  - artifact: security-model
last_validated: null
---

# API Contract

## Direction

<!-- Normative statements that BIND future work — not descriptions of current behavior. Each
     entry: a bold **Statement.**, then `Why:` (required), `Status:` (steady-state | in-transition
     + its tracking item), and optional `Retroactivity:` / `Rulings:` lines. Norms bind;
     descriptions track — see `docs/norms.md` for the anatomy, the normative-vs-descriptive test,
     and the lifecycle rules. This is the artifact's norm home; when the product has declared
     none, delete this whole section — an empty `## Direction` heading reads as ratified norms
     to the advisory probes; record `norm_registry_ratified: none — no norms to ratify` in
     `project-state.yaml` instead. Don't restate the rules here. -->

## Overview & Surface Type

<!-- What KIND of interface is this, and who consumes it?
     - Surface type (pick one or more; it shapes every decision below):
         · Network service — REST/HTTP, GraphQL, gRPC, message/event stream
         · Library / SDK / module — public functions, types, FFI/bindings
         · On-device / platform↔app — OS framework API, extension point,
           plugin interface, IPC / message bus
         · CLI — commands, flags, exit codes, stdout/stderr format
     - Consumers: internal | external | both (mirror classification.structural).
       External consumers raise the stakes on every decision below.
     - Where the canonical contract lives: OpenAPI/SDL/.proto for a network
       service; the typed public signatures (+ semver) for a library; the
       platform's interface definition (e.g. an IDL / protocol declaration) for
       an on-device API; the documented flag/output spec for a CLI. -->

## Operations

<!-- The operations/functions/endpoints/commands this interface exposes. For
     each: purpose, the entity it acts on, and whether it is safe/idempotent.
     Group by resource or module; don't restate every field (that's the schema
     below). -->

## Inputs & Outputs

<!-- The argument/request and return/response shapes. Reference the Data Model
     entities rather than restating them. Note required vs. optional,
     nullability, default semantics, and — for operations returning collections
     — pagination / batching (cursor vs. offset; max size). -->

## Error Model   <!-- recorded decision → api_error_model_approach -->

<!-- ONE consistent way failures are reported — what a consumer's error handling
     depends on. The shape depends on the surface:
     - Network service: a typed error envelope (e.g. an RFC-7807 problem object,
       a gRPC status, GraphQL errors) with a stable machine-readable code.
     - Library / SDK: the exception/error-type hierarchy or result type, and
       which errors are part of the contract vs. internal.
     - CLI: exit-code scheme + stderr format.
     - On-device / IPC: the error message/result contract across the boundary.
     In all cases: a documented, stable code vocabulary (not just a string), and
     no leaking of stack traces, internal identifiers, or PII (see Security). -->

## Versioning   <!-- recorded decision → api_versioning_approach -->

<!-- How a consumer knows which version they call, and how new versions are
     introduced — recorded, including a deliberate "none". The mechanism is
     surface-specific:
     - Network service: URI path (/v1), header / media-type, or query param.
     - Library / SDK: semantic versioning on the package + signature stability.
     - On-device / platform: interface version negotiation / capability flags.
     - CLI: documented flag/output versioning and deprecation.
     The cost asymmetry is the point: for most surfaces a version handle is
     cheap up front but a coordinated breaking change once consumers exist.
     Record: the mechanism, the granularity (whole-surface vs. per-operation),
     and the status — active (versioned now) | deferred. A DEFERRAL must be
     dated and carry a revisit trigger (e.g. "add a version handle before the
     first external consumer — review by <date>"), not an open-ended "until
     external consumers exist" with no owner — that note is how an interface
     ships unversioned for a year and then pays the retrofit. -->

## Deprecation & Compatibility   <!-- part of api_versioning_approach -->

<!-- How the interface evolves without breaking consumers — the half of
     versioning that prevents needing a new version at all.
     - Evolution rules (the practice that makes new versions rare): additive
       changes only; tolerant reader; never remove or repurpose an existing
       field/parameter/return; tolerate unknown enum values. Document which you
       follow.
     - Deprecation/sunset policy: how a breaking change is signalled (deprecation
       headers, `@deprecated` annotations, schema directives, changelog, CLI
       warnings), the support window, and how consumers are notified.
     - Backward-compatibility commitment, per stability tier (below). -->

## Surface Inventory & Stability Tiers

<!-- Which parts of the surface are a stable public contract vs. internal.
     - Inventory: list the public-contract operations vs. internal/admin/private
       ones (exported vs. unexported, public vs. private interfaces, hidden
       flags). Undocumented or forgotten surface is a real risk — for network
       APIs this is OWASP API9 "Improper Inventory Management", the same
       zombie-endpoint failure this contract exists to prevent; for a library
       it's "accidentally public" internals consumers come to depend on.
     - Stability tier per surface: experimental | stable | deprecated. Tiers set
       the compatibility promise — experimental may break; stable cannot without
       a version bump. -->

## Conventions

<!-- Wire/interface conventions — small choices that are expensive to change
     once consumers depend on them. Pick and document those that apply:
     - Timestamps: ISO-8601, UTC, explicit offset.
     - Money / amounts: minor units (integer) or decimal string — NEVER a float.
       Currency explicit.
     - Naming/casing — consistent across the surface (field casing for a
       service; naming conventions for a library).
     - IDs/handles: opaque where exposure matters (sequential integer IDs enable
       enumeration on a network API — see Security / BOLA).
     - Enums as named values (not magic ints); null vs. absent semantics. -->

## Security

<!-- API-specific security, on top of the Security Model (authentication and
     authorization live THERE — this section names the API-DESIGN failure modes
     at the boundary). Address the ones that fit the surface:
     - Network/service API: reference the OWASP API Security Top 10 — especially
       broken object-level authorization (BOLA/IDOR, API1: authorize the
       OBJECT, not just the caller — the #1 API risk), mass assignment
       (over-permissive request binding), and excessive data exposure (return
       only what's needed; don't rely on the client to filter).
     - Library / SDK / on-device: input validation & sanitization at the
       surface, privilege/capability scoping (don't hand callers more authority
       than they need), and not exposing unsafe internals through the public
       API.
     - Resource / rate limits and input/payload-size bounds where a caller can
       drive cost. -->

## Conditional Patterns

<!-- Only if they apply — omit otherwise. Map each to your surface:
     - Async / long-running operations: network → 202 + a status resource or
       callback; library/platform → futures / async / completion handlers — not
       a held-open call.
     - Concurrency / consistency: network → conditional requests (ETag +
       If-Match) or a version field; library → the thread-safety / reentrancy
       contract; on-device → the actor/queue model.
     - Events / callbacks the interface emits: network → webhooks (delivery
       guarantee → consumer idempotency, retry/backoff, payload signing, replay,
       and a version story for the payloads); in-process → listeners/observers /
       platform notifications.
     - Consumer correlation: return a request-id / trace handle (ties to the
       Observability Strategy).
     - Cross-origin/cross-process access controls (e.g. CORS for browser
       clients) where the boundary is reachable by untrusted callers. -->
