# Adversarial Surface Taxonomy

This file defines the **finite list of code patterns that warrant adversarial review** when `adversarial.enabled: true` for a project.

The taxonomy is extracted from `methodology/adversarial.md` into its own file so projects can extend it. The framework default lives here; per-project additions go in `.prawduct/adversarial-surfaces.md` (when present, the project file unions with the framework default — never replaces).

## Framework Default

| Surface | Examples |
|---|---|
| **http_endpoint** | Any function reachable via HTTP from outside the trust boundary. REST endpoints, GraphQL resolvers, webhook receivers. |
| **auth** | Login, token validation, permission checks, session management, password handling, MFA flow. |
| **crypto** | Signing, hashing, encryption, key derivation, random generation, certificate validation. |
| **parser** | JSON, XML, YAML, custom DSLs, regex against user input, file format decoders, query language interpreters. |
| **file_io_user_paths** | Upload handlers, path resolution from user input, traversal-prone code, archive extraction. |
| **sql_construction** | Any string concatenation or interpolation into a SQL query (regardless of ORM presence). |
| **process_invocation** | `child_process`, `exec`, shell-out, subprocess spawning, command construction from user input. |
| **network_io_external** | HTTP clients to external services, webhooks outbound, callbacks, third-party API integration. |
| **concurrency** | Locks, queues, semaphores, async coordination, shared mutable state across goroutines/threads/tasks. |
| **resource_allocator** | Memory allocation patterns, file handle management, socket pools, connection pools, thread pools. |
| **input_validator** | Form validation, schema checks, type coercion at trust boundaries, allow/deny lists. |
| **i18n_text** | Encoding, normalization (NFC/NFD), sorting under locale, RTL text handling, mixed-script content. |
| **time_arithmetic** | TZ conversion, DST transitions, leap seconds, locale-dependent date/number formatting, year boundaries. |
| **serialization** | Bytes ↔ objects boundaries, network protocol parsing, custom file format encoding/decoding. |

## Per-Project Extension

A project can add domain-specific surfaces by creating `.prawduct/adversarial-surfaces.md` with the same table format. Examples of when to extend:

- **Financial-tech project**: add `monetary_arithmetic` (currency conversion, rounding, fixed-point math).
- **Healthcare project**: add `patient_data_handling` (PII boundary, audit-logged access).
- **Cryptocurrency project**: add `key_management`, `transaction_signing`, `consensus_voting`.
- **IoT/embedded**: add `device_messaging`, `firmware_update_path`.

Per-project surfaces are unioned with the framework default — they do not replace it. To suppress a framework surface that genuinely doesn't apply (rare), document the suppression in `.prawduct/project-state.yaml` under `adversarial.suppressed_surfaces: [...]`.

## When the Taxonomy Is Consulted

Three points (per `methodology/adversarial.md`'s defense-in-depth section):

1. **Planning** — when writing build-plan chunks, identify which entries each chunk will touch; declare in chunk's `attack_surfaces` field.
2. **Building** — at chunk-end, builder verifies actual diff against this taxonomy; compares to chunk's declaration.
3. **Critic** — independent inspection during review; flags surfaces touched but not acknowledged.

## Evolving the Taxonomy

The framework default is intentionally bounded. Adding a category requires evidence:

- A pattern of edge-case bugs across multiple projects in the same surface category.
- A recognized industry pattern (e.g., OWASP top 10 entries that don't already map cleanly).
- A new technology category that's distinct enough that existing categories miss its attack profile.

Propose additions via PR to `methodology/adversarial-surfaces.md` with a short rationale and 2-3 example projects/findings that motivated the addition. Avoid taxonomy bloat — every category added increases the cognitive load on planning, building, and Critic.
