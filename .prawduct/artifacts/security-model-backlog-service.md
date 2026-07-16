---
artifact: security-model
version: 1
scope: backlog-service
depends_on:
  - artifact: backlog-service-prd            # D8 identity model, PV1/PV2
  - artifact: api-notes-github-issues
last_validated: 2026-07-16
---

# Security Model — Backlog Service (P0 slice: user-token bootstrap)

This slice runs D8's sanctioned **low-ceremony bootstrap**: one user credential for all targets.
The GitHub App identity (per-owner rate buckets, `[bot]` attribution) is a follow-on plan — what
lands here is the **seam it plugs into**, so the upgrade is a new resolver arm, not a refactor.

## Authentication — token sources & resolution

Resolution order (first hit wins), performed **per invocation**, nothing persisted by us:

1. **`GH_TOKEN`** env var; if unset, **`GITHUB_TOKEN`** (the CI-conventional alias) — in that
   order, matching `gh`'s own precedence.
2. **`gh auth token`** — subprocess, list-form argv, never `shell=True`; 2 s timeout; a missing
   `gh` binary or non-zero exit falls through silently to step 3.
3. **Fail**: `error.kind: auth`, message names both sources and the fix
   (`export GH_TOKEN=… or gh auth login`), exit 1, non-retryable. Never a prompt (AG1).

Captured (api-notes): a `gho_` user token authenticates as `Authorization: Bearer <token>`;
classic-PAT scope floor is `repo` (private repos); fine-grained equivalent: Issues RW +
Metadata R on the target repos.

**Credential resolution is keyed by target owner** — the D8 seam:

```
resolve_credential(owner: str) -> {kind: "user", token: str}
```

P0 implements exactly one arm: every owner resolves to the user token above. The App upgrade
adds an arm (`kind: "app"`, JWT → installation-token exchange, cached per owner with expiry,
per-owner rate bucket) behind the same signature, selected by a `backlog.auth.<owner>: app`
config key. Nothing outside `backlog_github.py` sees which arm answered — callers get a token
and headers, never a mechanism.

## Authorization

Entirely **GitHub's, inherited structurally** (PV1): repo visibility = backlog visibility; the
adapter adds no ACL layer and must not pretend to one. Consequences made explicit:

- Whoever holds the token acts *as that user* — mutations attribute to the human's account
  (CC4 actor identity = token identity in P0; per-agent attribution rides in payload fields
  like `verified: … <actor>` and claims, per D8, until the App's `[bot]` identity lands).
- Cross-owner writes (upstream filing) work exactly where the user's own access reaches —
  the federated multi-owner model (O1), not a shared secret (PV2: the token is real, scoped
  to the user, revocable at github.com or `gh auth logout`).
- The CLI passes GitHub's authorization answers through honestly (`auth` / `not_found`);
  it never retries a 401/403-permission response. Permission 403s are distinguished from
  rate-limit 403s by the api-contract's discriminator (`retry-after` header or
  `x-ratelimit-remaining: 0` → `rate_limited`; otherwise `auth`).

## Data Privacy

- **Data at rest lives in GitHub Issues** — visibility governed by repo visibility; the P0
  slice keeps **no local store** (no cache, no queue). The only local artifacts are the
  importer's dry-run manifest and created-issues journal (plain files in the repo/scratch
  path the operator chose — they contain item titles/IDs, no credentials).
- **Tokens are never persisted, logged, echoed, or embedded** — not in argv (env/subprocess
  only), not in JSON output, not in error text or `detail`. A regression test guards this:
  force an auth failure and assert the token string appears nowhere in any output stream.
- Probe/scratch hygiene: captured artifacts in this repo contain no tokens (verified for
  `api-notes-github-issues.md`).

## Abuse Prevention & Operational Limits

- **Rate limits:** user-token bucket is 5,000/hr core (captured); the 80 writes/min ceiling is GitHub's documented secondary limit (not provoked in probes).
  Import paces under 80 writes/min with headroom recorded (S3); normal CRUD is single-digit
  calls. Rate exhaustion surfaces as `rate_limited` + `retry_after` — never an internal
  retry loop (G2).
- **Destructive-operation guards:** `import` requires explicit `--execute` (default is
  dry-run manifest with zero writes — asserted by test); `rollback` acts only on the journal's
  created set; `export` is read-only. No operation deletes anything (DM7: closes, never
  deletes).
- **Injection surface:** no `shell=True` anywhere; the one subprocess (`gh auth token`) has a
  fixed argv. All GitHub-bound strings are JSON-encoded by the client; label/ID inputs are
  validated by the grammar before they reach a URL path (URL-encoding applied; path traversal
  impossible by construction).
- **Anonymous/public filing (PV3)** is P1+ scope; nothing in this slice opens a public surface.

## Revocation & incident posture

Revoking the user token (GitHub settings / `gh auth logout`) severs everything instantly —
nothing cached, nothing queued, no second credential exists in P0. The App upgrade narrows
blast radius further (per-owner installations, revocable per org); until then the accepted
risk is: one user token, user-scoped power, same posture as the developer's own `gh` CLI.
