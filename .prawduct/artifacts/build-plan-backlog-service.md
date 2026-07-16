---
artifact: build-plan
version: 2
scope: backlog-service
depends_on:
  - artifact: backlog-service-requirements   # documentation/backlog-service-requirements.md (draft v3, owner-reviewed 2026-07-14)
  - artifact: backlog-service-prd            # documentation/backlog-service-prd.md (draft v3, owner decisions O1–O4 resolved)
last_validated: 2026-07-16
---

# Build Plan — Backlog Service (GitHub Issues + thin deterministic adapter), P0 slice

Implements the P0 core of `documentation/backlog-service-prd.md` (BKL-5D2C): a thin **online**
CLI over GitHub Issues — no cache, no queue — plus the importer/export pair and governance
integration. The PRD's tiering (§11, §16) is the spine: only **S1** (confirm HTTP + auth spec)
and **S2** (migration dry-run) gate this slice, and both are front-loaded (Chunk 01 / Chunk 05).
P1+ layers are deferred explicitly (see "Deferred scope"), never silently.

## Requirements Confidence

**Level:** High

**Why:** Problem, success criteria, and scope are each one sentence, confirmed across two
owner-reviewed documents: requirements draft v3 (evidence from a 16-checkout sweep; owner
decisions 1–3) and PRD draft v3 (O1–O4 resolved 2026-07-14, adversarial pass folded). The two
remaining unknowns are scoped and gated in-plan: S1 residuals (HTTP confirmation + auth-flow
spec) are Chunk 01 step 0; S2 (migration fidelity) is Chunk 05's dry-run. GitHub API details are
volatile — every chunk touching a new endpoint family carries its own `verify-api` step; nothing
is built from recalled API shapes.

**Open assumptions / unknowns:**
- [ASSUMPTION: CLI entry point is new `bin/prawduct-backlog` beside `prawduct-hook`; flat lib
  modules (`backlog_github` / `backlog_service` / `backlog_service_cmd` / `backlog_migrate`)
  because `lib/backlog.py` (file-mode parser) occupies the package name | LOW impact | user can
  override naming]
- [ASSUMPTION: this slice authenticates with the user-token bootstrap (`gh auth token` /
  `GH_TOKEN`), per D8's "legitimate low-ceremony bootstrap"; the GitHub App identity upgrade is a
  follow-on plan | MED impact | user can pull App auth forward]
- [ASSUMPTION: backend selection lives in `.prawduct/project-state.yaml` under a `backlog:` key
  (`backend: file|github`, `repo: owner/name`), default `file` | LOW impact | user can relocate]
- [ASSUMPTION: GV2 briefing counts come from a small age-stamped counts file refreshed by a
  detached subprocess — a stamp with visible age, not the deferred cache layer | MED impact |
  user can defer to "counts on demand" instead]
- [ASSUMPTION: live-write verification uses a throwaway scratch repo; no real project's issues
  are mutated during this plan — actual portfolio migration (cordyceps → discodon/scriob) is a
  post-plan rollout step per PRD parent phasing | LOW impact]

**What would raise confidence:** N/A at plan level; Chunk 01's probes are the cheapest concrete
step for the S1 residuals and run first.

## Status

- [x] Chunk 01: S1 settlement — live-API probes + field-level design artifacts
- [ ] Chunk 02: Walking skeleton — create/get/list round-trip through the new CLI
- [ ] Chunk 03: Mutation surface — update, close, comment, claim, verification stamp
- [ ] Chunk 04: Query & pick — ready-work, filters, changed-since cursor
- [ ] Chunk 05: Importer + export — S2 migration dry-run on discodon
- [ ] Chunk 06: Governance integration — skill service-mode, briefing, provisioning, docs
Context: Chunk 01 complete (S1 settled, design keystone landed; Critic final → 0 blocking). Next: Chunk 02.

## Scaffolding

### Project Initialization

None — this lands inside the existing plugin repo. No new runtime dependencies: the GitHub
client is **stdlib HTTP** (`urllib.request`), synchronous, per project preferences (no
third-party HTTP dependency exists today and none is introduced).

### Dependencies

Runtime: Python stdlib only (urllib, json, subprocess for the `gh auth token` bootstrap —
list-form args, never `shell=True`). Dev: existing pytest stack (pytest, pytest-xdist,
pytest-timeout). No additions to `pyproject.toml` runtime deps.

### Build & Test Configuration

Existing `tests/` layout and pytest config in `pyproject.toml`; `python3 -m pytest -q` runs
everything. All new `lib/`/`tests/` files carry `from __future__ import annotations` (test-enforced).
Tests never touch the network: the HTTP transport is a seam faked with shapes captured by
`verify-api` probes (fakes built *after* capture, never before).

### Scaffold Verification

After Chunk 02: `bin/prawduct-backlog --help` exits 0 from a repo-local invocation (never the
PATH/plugin-cache copy), and `python3 -m pytest -q tests/test_backlog_service*.py` passes.

### Verification Strategy

Beyond tests, each chunk is exercised the way its users (agents) would use it: hand-drive the
CLI against a **scratch private repo** created for this plan — file, mutate, query, claim, and
observe JSON + human output and failure behavior (kill the network; confirm fast, clear,
retryable errors — the never-block floor). Chunk 05 is verified two ways: a **read-only dry-run
manifest over discodon's real `backlog.md` + `backlog-archive.md`** (reviewed by the owner
before any live migration anywhere), and a live import→export round-trip on the scratch repo
diffed for fidelity. Rate/latency observations (S3) are recorded during Chunk 05's write bursts
and tune pacing constants — they are runtime tuning, not design gates.

## Project Structure

```
bin/
├── prawduct-hook            # existing governance kernel CLI (untouched)
└── prawduct-backlog         # NEW: thin dispatcher for the backlog service CLI
lib/
├── backlog.py               # existing file-mode parser (untouched; reused by the importer)
├── backlog_github.py        # NEW: sync stdlib-HTTP GitHub client — auth, ETag, rate headers
├── backlog_service.py       # NEW: core ops — CRUD/query/claim, ID normalize, encoding map
├── backlog_service_cmd.py   # NEW: command layer — flags, JSON + human output
└── backlog_migrate.py       # NEW: importer (file → issues) + exporter (issues → files)
skills/backlog/SKILL.md      # existing skill — gains the service-mode path in Chunk 06
```

### Module Boundaries

- `backlog_github.py` is the **only** module that speaks HTTP; it knows nothing of prawduct
  semantics (labels in, labels out). Return-value errors (`status`/`reason` dicts); exceptions
  escape only at the `bin/` boundary. Sync only — background refresh is a detached subprocess,
  never asyncio (D6).
- `backlog_service.py` owns the prawduct↔GitHub encoding (the D7 seam): status/stage two-axis
  mapping, `prawduct:` body block, ID forms. It never formats output.
- `backlog_service_cmd.py` owns flags and rendering; no encoding logic.
- `lib/backlog.py` (file mode) is not modified; MG3 coexistence is backend *selection*, not
  code sharing — except the importer, which consumes its parser read-only.
- State the requirement breadth as "a GitHub-hosted repo", not this client's shape — the seam
  exists so GitHub doesn't colonize the interface (D7 + the one-instance learning).

## Build Chunks

### Chunk 01: S1 settlement — live-API probes + field-level design artifacts

- **Description:** Settle S1 (HTTP confirmed, auth flow specced) and lock the persisted
  encodings **before any code**. The label taxonomy + `prawduct:` body block is a persisted
  format — a lock-in decision — so its fields are derived from the queries it must answer (PRD
  §7a), not from the mechanism. Probes run against the live GitHub REST API and capture actual
  shapes; every later chunk's fakes trace to these captures.
- **Depends on:** none
- **Artifacts consumed:** `documentation/backlog-service-prd.md` §7/§7a/§10/§11-S1,
  `documentation/backlog-service-requirements.md` DM1–DM7
- **Deliverables:**
  - new `.prawduct/artifacts/data-model-backlog-service.md` — namespaced label taxonomy
    (`pb:` prefix or equivalent — collision-safe against existing repo labels), two-axis
    status/stage encoding incl. `state_reason` mapping (completed=shipped, not_planned=dropped),
    fenced `prawduct:` body-block schema (exact round-trip fields), ID grammar
    (`owner/repo#number` canonical, `repo#number` short, `repo-number`/`repo/number` accepted;
    node-id stored against transfer renumbering), `id:PFX-XXXX` alias-label scheme
  - new `.prawduct/artifacts/api-contract-backlog-cli.md` — operations, flags, JSON + human
    output shapes, exit codes, the return-value error model, and the CLI versioning,
    deprecation, and compatibility decisions (each recorded, not silent)
  - new `.prawduct/artifacts/security-model-backlog-service.md` — token sources (`GH_TOKEN` →
    `gh auth token` fallback), storage/scope/revocation posture, credential resolution keyed by
    target owner, and the D8 App-upgrade path (specced as the seam this slice plugs into, not built)
  - new `.prawduct/artifacts/api-notes-github-issues.md` — captured live response shapes
  - `documentation/backlog-service-prd.md` §11 edited: S1 flipped to resolved with pointer
  - `design_decisions.api_versioning_approach` + `api_error_model_approach` recorded in
    `.prawduct/project-state.yaml`
- **Tests:** none (design chunk); probe scripts are scratch, not committed
- **Acceptance criteria:** S1 resolved in the PRD; all four artifacts exist and the data model
  answers every §7a query on paper; conditional-request (ETag) behavior confirmed and noted for
  the future cache layer
- **Foreign API:** github-rest-issues
- **Type:** doc-only
- **Critic mode:** final
  <!-- Override: this chunk lands the schema/contract keystone every later chunk builds on. -->
- **Done when:**
  0. verify-api — probe the live API: issue create/get/list/update, issue comments
     (create/list), labels CRUD, `state_reason`, assignee set/verify, dependencies (blocked-by)
     + sub-issues endpoints, `since` param, ETag/conditional GET; capture shapes in
     new `.prawduct/artifacts/api-notes-github-issues.md`
  1. Acceptance criteria met
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: Walking skeleton — create/get/list round-trip through the new CLI

- **Description:** Thin slice through every layer: CLI → command layer → core → HTTP client →
  a real GitHub issue and back. Proves the architecture (and the never-block floor) before
  widening. One-call create: `title` + `body` suffice; every other field defaultable (AG2).
- **Depends on:** Chunk 01
- **Artifacts consumed:** `data-model-backlog-service.md`, `api-contract-backlog-cli.md`,
  `security-model-backlog-service.md`, `api-notes-github-issues.md`
- **Deliverables:** new `lib/backlog_github.py`, new `lib/backlog_service.py`, new
  `lib/backlog_service_cmd.py`, new `bin/prawduct-backlog` (dispatcher mirrors
  `bin/prawduct-hook`'s bootstrap, including the fail-open-on-lib-ImportError rule), new
  `tests/test_backlog_service_core.py`, new `tests/test_backlog_github_client.py`
- **Tests:** unit — ID grammar normalization (all four accepted forms + reject ambiguity),
  request construction (auth header, list-form subprocess for token bootstrap), error mapping
  (timeout/DNS/5xx/403-rate-limit → distinct retryable `status`/`reason` dicts); integration —
  add/get/list against the faked transport using captured shapes; never-block floor — transport
  failure returns fast with a clear retryable error, correct exit code, no traceback, nothing
  half-written
- **Acceptance criteria:** against the scratch repo, `prawduct-backlog add|get|list` round-trips
  a real issue with the body block intact, in JSON and human modes; with the network cut, every
  command fails fast (< 2 s) with a retryable error
- **Foreign API:** github-rest-issues (shapes from Chunk 01; re-probe only if a call fails
  against the live scratch repo — capture the corrected shape before touching the fake)
- **Exposed API:** prawduct-backlog-cli (versioning + error-model decisions recorded in Chunk 01)
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: Mutation surface — update, close, comment, claim, verification stamp

- **Description:** The rest of the write path: field-wise update, close/reopen with the two-axis
  state mapping, claim as assignee take-and-verify (atomic-ish; residual race documented, CC3),
  and the TF2 verification stamp — "premise re-checked against code" as one call — plus the
  basic comment primitive (`comment add|list`) the stamp rides on. The full DM5 comment surface
  is P1 and deferred (see Deferred scope); GitHub's native comments give threading/attribution
  by construction, so nothing here forecloses it. Trust/staleness is the portfolio's #1 measured
  pain; the stamp write-side lands here, its staleness query in Chunk 04.
- **Depends on:** Chunk 02
- **Artifacts consumed:** `data-model-backlog-service.md` (state matrix, stamp encoding)
- **Deliverables:** update/close/reopen/comment/claim/verify ops in `lib/backlog_service.py` +
  flags in `lib/backlog_service_cmd.py`, new `tests/test_backlog_service_mutations.py`
- **Tests:** unit — full status/stage matrix survives encode→decode round-trip (DM2: two axes
  never flatten); claim race (fake returns competing assignee → clean back-off with clear
  reason); advisory validation flags unknown label values but **never rejects a write** (DM1;
  tolerant-validator learning — unknown values are flagged, and flagged-unknown never silently
  defaults to allowed); integration — mutate→read-back cycles one step past the immediate
  post-state
- **Acceptance criteria:** on the scratch repo: close an item as shipped and as dropped and both
  axes read back correctly; two simulated claimers produce exactly one holder and one clean
  back-off; a verification stamp is written and readable in one call each
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: Query & pick — ready-work, filters, changed-since cursor

- **Description:** The read path `pick` needs: structured filters over DM1 fields, the
  ready-work query (open ∧ `stage:ready` ∧ unclaimed ∧ all blockers closed — DM3+CC3+DM2),
  changed-since cursor (Q2), stale-verification query (TF2), counts derived on read (Q5).
  Queries run against the **issues list API, not GitHub search** — search is not
  read-your-writes consistent and there is no cache in this slice to hide behind (PRD §13-6).
- **Depends on:** Chunk 03
- **Artifacts consumed:** `data-model-backlog-service.md` (§7a query list — this chunk is its
  coverage check), `api-contract-backlog-cli.md`
- **Deliverables:** query/ready/changed-since/stale-verification/count ops across
  `lib/backlog_service.py` + `lib/backlog_service_cmd.py`, new `tests/test_backlog_service_query.py`
- **Tests:** unit — filter composition, pagination, blocker-resolution logic (blocked-by fetch +
  closed check), cursor round-trip; integration — every §7a query answerable against faked data;
  early-stage items excluded from ready-work (stage routing is load-bearing, Principle 6)
- **Acceptance criteria:** on the scratch repo seeded with a blocker chain: `ready` returns only
  the unblocked, unclaimed, `stage:ready` item; `--since <cursor>` enumerates exactly the items
  mutated after the checkpoint
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 05: Importer + export — S2 migration dry-run on discodon

- **Description:** The riskiest single operation (MG1), built as S2 — the slice's proving
  increment. Import reads `backlog.md` + `backlog-archive.md` through the existing
  `lib/backlog.py` parser (read-only reuse) and maps to issues with **verbatim body fidelity**:
  metadata bar → labels + body block, `PFX-XXXX` → permanent `id:` alias label + body-block
  entry, relationships reconstructed in a second pass after all items exist, archive → closed
  issues with correct `state_reason`. `--dry-run` emits a complete manifest (every item, its
  target encoding, every warning) with **zero writes**. Import targets the **spec roster, not
  the open-work list, on the canonical checkout only** (migration learnings). A created-issues
  journal makes rollback deterministic. Export (MG2) is the mirror: issues → plain files, full
  fidelity, scriptable — backup and exit in one command.
- **Depends on:** Chunk 03 (mutation ops); Chunk 04 not required
- **Artifacts consumed:** `data-model-backlog-service.md` (alias + body-block schema),
  requirements MG1–MG3
- **Deliverables:** new `lib/backlog_migrate.py` + cmd wiring (`import --dry-run|--execute`,
  `export`, `rollback`), new `tests/test_backlog_migrate.py` (fixtures reuse
  `tests/test_backlog_parser.py` corpus incl. legacy-format variants)
- **Tests:** unit — fidelity round-trip on fixture backlogs (body verbatim, every metadata field
  survives), alias mapping, relationship reconstruction incl. dangling refs (flagged, not
  dropped), dry-run purity (assert the transport is never invoked); integration — import→export
  on fixtures diffs clean; rollback from journal closes/labels exactly the created set
- **Acceptance criteria:** dry-run manifest over discodon's real files is complete and
  warning-triaged, and the owner has reviewed it before any live migration anywhere; live
  import→export round-trip on the scratch repo diffs clean against the source fixtures; write
  burst is paced under 80 writes/min with observed rate-limit headroom recorded (S3 data point)
- **Foreign API:** github-rest-issues (import write paths; re-verify bulk-create + label-create
  behavior against the live scratch repo before the discodon dry-run is trusted)
- **Critic mode:** final
  <!-- Override: migration fidelity is the plan's highest-risk surface — full review before
       anything real migrates. -->
- **Done when:**
  0. verify-api — confirm create/label/close behavior under a paced burst on the scratch repo;
     correct captured shapes if drift found
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 06: Governance integration — skill service-mode, briefing, provisioning, docs

- **Description:** Wire the service into prawduct governance without breaking file-mode
  (MG3: backends coexist across the portfolio, never within one project). Backend selection is
  a `backlog:` key in `.prawduct/project-state.yaml` (default `file`). This chunk introduces a
  project-wide concept, so its surfaces are enumerated up front (planning rule): (1)
  `skills/backlog/SKILL.md` — service-mode path; pick/add/find/list/update UX contract
  unchanged, stage-aware routing intact (GV1); dedup-on-create degrades to a cheap lexical
  title match over a live `list` call, advisory-only, until the P1 dedup layer ships; (2)
  `lib/briefing.py` — counts read from an age-stamped counts file refreshed by a detached
  subprocess; session start never waits; unreachable service renders "backlog: unavailable
  (retryable)" and **no gate or hook fails** on it (GV2/G2); (3) onboard/doctor provisioning —
  create the namespaced label taxonomy idempotently, detect collisions with the repo's existing
  labels/issues and report instead of clobbering (GV5, §13 coexistence); (4) new
  `docs/backlog-service.md` — operator doc: setup, auth bootstrap, migration runbook, export;
  (5) `templates/backlog.md` — legend note pointing file-mode products at service-mode.
- **Depends on:** Chunks 02–05
- **Artifacts consumed:** all Chunk 01 artifacts; requirements GV1–GV5
- **Deliverables:** the five surfaces above (docs file is new; the rest are edits), new
  `tests/test_backlog_backend_selection.py`, new `tests/test_backlog_briefing_degradation.py`
- **Tests:** unit — backend routing (file project untouched by service code paths and vice
  versa; both-configured is a flagged config error), provisioning idempotency (doctor re-run
  is a no-op), collision detection; integration — briefing with service unreachable renders
  within its timeout with visible age on last-known counts, no hang, no gate failure
- **Acceptance criteria:** a service-mode scratch project round-trips the full skill UX
  (add → pick → claim → update → close) against GitHub while a file-mode project in the same
  plugin install behaves exactly as today; session briefing under a cut network starts cleanly
- **Type:** cumulative-final
  <!-- Last chunk: commit first, then one `/prawduct:critic cumulative` over
       merge-base...HEAD — it is also the PR gate. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## Early Feedback Milestone

**Milestone chunk:** 02
**What the user can do:** file and list real backlog items on a live GitHub repo from the CLI —
and see the never-block floor behave under a cut network.

## Deferred scope (explicit, not silent)

Each deferral is a PRD-tiered P1/P2 layer that earns its own follow-on plan; none is required
for the P0 invariants (G1–G5) to hold:

- **Read-through cache + S4 freshness protocol** (P1, D5) — online-only is correct, just slower;
  build when read-amplification or offline need is observed.
- **Offline write-queue + provisional IDs** (P2, §8.1) — the floor (fail-fast + retry) ships in
  Chunk 02.
- **Dedup-on-create advisory (AG3/Q3)** beyond Chunk 06's lexical stopgap; semantic search (P2).
- **CC2 optimistic concurrency** (compare-and-set on updated-at) — claims' take-and-verify ships
  in Chunk 03; general lost-update protection is P1 follow-on.
- **DM5 full comment surface** (P1) — threaded drill-down UX beyond Chunk 03's basic
  `comment add|list` primitive; GitHub's native comments keep threading/attribution available.
- **GitHub App identity (D8 full)** — per-owner rate buckets, `[bot]` attribution; this slice
  runs the sanctioned user-token bootstrap. Pull forward when rate/attribution bite.
- **XP1/XP2 upstream filing + drop-box retirement; PV3 anonymous surface + abuse handling.**
- **Attachments (DM6) + S5 inline-on-private spike; MCP surface; batch ops (AU2/AU3); Q4
  cross-project rollup; org Issue Fields enhancement.**
- **Actual portfolio migration** (cordyceps, then discodon + scriob) — operational rollout
  gated on Chunk 05's owner-reviewed dry-run, run per the parent doc's phasing, not this plan.

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic review passes (per-chunk commit
scopes `chunk`-mode reviews). Chunk 06's cumulative review makes the branch PR-ready;
`/prawduct:pr create` runs when the user asks.

- After Chunk 01 (`final`): schema/contract keystone review — the §7a coverage check on paper
  before any code consumes the encodings.
- After Chunk 02: architecture confirmation — CLI → core → client seam, never-block floor real.
- After Chunk 05 (`final`): migration-fidelity review + owner sign-off on the discodon dry-run
  manifest before any real project migrates.
- After Chunk 06 (cumulative): full-bundle review — MG3 coexistence proven both directions,
  GV1 UX contract intact, briefing degradation observed, deferred-scope list still honest.
