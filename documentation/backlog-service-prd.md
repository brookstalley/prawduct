# Backlog Service — Product Requirements & High-Level Design (PRD)

`status: draft v1 — whole-system spec at planning altitude, awaiting owner confidence · added: 2026-07-14 · source: planning session · stage: design`

**Parent:** `documentation/backlog-service-requirements.md` — the problem, the 8-project evidence
sweep, and the adopt-vs-build decision that selected **GitHub Issues as system of record + a
deterministic prawduct adapter**. This PRD specs the *chosen* system: what it does, the shape that
makes it coherent, and how its capabilities are prioritized. Requirement IDs below (DM1, AG4, …)
trace to that parent — this doc does not restate the requirement rows, it designs against them.

**Planning altitude (read this first).** This is the **top level of a layered plan**. It covers
*what the system must do* and *the shape that makes it hang together* — deep enough to be confident,
no deeper. It is Product-Brief + high-level architecture + a priority-tagged capability spec. It
**does not** partition v1-vs-later, sequence chunks, or fix field-level schemas — those are the next
level (§15). **Priorities (P0–P3) rank importance, not release timing** — a P3 capability ships in
the first slice if it is cheap or free; a P1 may land later if it is expensive. We will *build* a
thin vertical slice, but we spec the whole system so the slice is cut from a coherent whole.

---

## 1. Vision

A backlog that a fleet of agents and one human can trust: **one live source of truth per project,
mutated only by deterministic code, reachable from every checkout, and free.** The backlog stops
being a merge-prone markdown file an LLM edits by hand and becomes GitHub Issues fronted by a thin
prawduct adapter — so item state is never stale-by-checkout, CRUD costs zero model tokens, and every
adopter already owns the backend.

## 2. Users & personas

| Persona | Who | Needs from the system |
|---|---|---|
| **Project agent** | a Claude session working a repo | file / query / pick / update / claim / comment in one non-interactive call, zero model tokens on the CRUD path, never blocked by the network |
| **Consumer agent** | a session in a *downstream* product | file an item *upstream* against another project with provenance, no upstream checkout |
| **Human** (owner + collaborators) | Brooks; future collaborators | browse, prioritize, comment, decide — in a UI they already have (GitHub), no new tool to learn or pay for |
| **Background worker** | unattended triage / dedup / reconciliation jobs | bulk read + batch mutate dozens of items per pass without rate-limit pain or ceremony |
| **Anonymous filer** | a third party with no relationship to the owner | file a bug against a *public* project (a GitHub account is the only barrier) |

## 3. Core flows (what actually happens)

1. **File** — agent/human: `title` + `body` → one call → new item with ID, returns immediately;
   similar-item candidates returned advisory-async (never blocks).
2. **Pick next work** — agent: stage-aware, dependency-aware query ("ready items whose blockers are
   all closed, unclaimed") → routes early-stage items to discovery, not code.
3. **Update / claim / comment** — agent/human: field-wise update, atomic claim, threaded comment.
4. **Grooming sweep** — background worker: bulk re-stamp / close / relabel / merge N items in few
   paced calls; dozens of concurrent *readers* served entirely from the local mirror.
5. **File upstream** — consumer agent: item lands in another project's backlog in a `submitted`
   triage state, carrying source product + version + session provenance.
6. **Browse & decide** — human: GitHub's issue UI, search, and Projects board — no bespoke UI built.
7. **Migrate** — one-time per project: `backlog.md` (+ archive) → issues, IDs and bodies preserved.
8. **Export** — any time: issues → plain files (backup + exit).

## 4. Success criteria (how we know it worked)

- An agent files or queries in **one non-interactive call, p95 < 2 s, zero model tokens** on the CRUD path.
- Two agents in parallel worktrees + a human in a browser mutate concurrently with **no lost updates and no merge conflicts, ever.**
- **Every checkout/worktree/branch sees the same live state** — the observed "66 closed items shown as open" worktree becomes structurally impossible.
- A consumer files upstream **with no local checkout and no drop-box** of the target project.
- discodon's ~317 open items **migrate with IDs preserved**, and grooming sweeps get *cheaper*.
- **$0/month**, and no per-project cost as the portfolio grows.

## 5. Governing invariants (violate any and the design is wrong)

- **G1 — Code, never a model, in the data plane.** All CRUD is deterministic code (CLI/lib/MCP).
  Model judgment is reserved for triage *decisions*, never data plumbing. (Same doctrine as kernel
  v3; the deterministic-data-plane learning.)
- **G2 — Never block a session.** A dead or unreachable backend must never block a session, gate, or
  hook: writes queue locally and flush later; reads fall back to the local mirror with visible age.
- **G3 — One live view.** GitHub is the single source of truth per project; every checkout reads the
  same current state. Any cache says how old it is — silent staleness is the failure we are killing.
- **G4 — Adopter-reproducible & free.** Whatever this prescribes, any adopter can stand up at $0 —
  including adopters in private repos the owner cannot access. No backend bespoke to one machine.
- **G5 — Cheap exit.** Full-fidelity export to plain files at any time; the backlog is never hostage
  to a vendor or a server. Export doubles as backup.

## 6. Target architecture

A thin, synchronous, deterministic adapter over GitHub Issues, with a local mirror that absorbs read
latency and offline gaps.

```
  /prawduct:backlog skill (GV1)        MCP server              human → GitHub web UI
            │                              │                          │
            ▼                              ▼                          │
       prawduct backlog CLI  ──────►  core library (lib/backlog/)     │
        (flags, JSON+human out)        - deterministic CRUD (G1)      │
                                       - return-value errors          │
                                       - sync only (no asyncio)       │
                             ┌─────────────┴──────────────┐           │
                             ▼                             ▼           │
                    local mirror (SQLite)          GitHub client      │
                    - per-clone, gitignored        - `gh api` REST +  │
                    - git-common-dir keyed           GraphQL over     │
                    - warm reads < 500ms             list-form subproc│
                    - write-ahead queue (offline)  - auth via gh      │
                             │                             │          │
                             └────────► sync engine ◄──────┘          ▼
                              since-cursor reconcile + queue flush  GitHub Issues
                              (on-demand; detached-subproc refresh)  (source of truth)
```

**Components**

- **Core library** (`lib/backlog/…`, Python 3.10+, sync, return-value errors per project
  conventions). The only place CRUD logic lives; CLI/MCP/skill are thin fronts over it.
- **GitHub client** — `gh api` (REST + GraphQL) invoked as **list-form subprocess** (no `shell=True`,
  no token handling — `gh` owns auth). One code path for reads, writes, and bulk GraphQL since-cursor
  pulls. **Recommended** over a direct-HTTP client: it satisfies the sync-only + subprocess-safety
  conventions and removes token management; the residual cost is process-spawn latency on writes
  (~50–150 ms), which sits comfortably inside the p95 < 2 s write budget. Warm reads never pay it —
  they hit the mirror in-process.
- **Local mirror (SQLite)** — a per-clone, **gitignored**, `git-common-dir`-keyed projection of the
  project's issues (shared across a clone's worktrees, exactly as the evidence store is). Serves warm
  reads, structured queries, counts, and offline reads. It is *derived personal state*, never the
  truth — matching the "shared-answer vs personal-nag state live in separate stores" learning.
- **Write-ahead queue** — append-only local log (JSONL, evidence-store style) of mutations made while
  GitHub was unreachable; flushed on next sync; each entry atomic (a crash cannot half-write).
- **Sync engine** — pulls issues changed since the last checkpoint (since-cursor, Q2) into the mirror
  and flushes the queue. Runs on demand before any read that needs freshness; a detached background
  **subprocess** (not an async task) refreshes at session start so the briefing never waits (G2/GV2).
  Staleness is re-evaluated against GitHub's cursor, never inferred from a leftover marker (learning).
- **Fronts** — `prawduct backlog` CLI (JSON + human output, AG6); an MCP server (thin); the
  `/prawduct:backlog` skill (unchanged UX, GV1).

## 7. Data-model mapping (design intent, not the field-level schema)

prawduct item ↔ GitHub issue. Native GitHub features are used where they fit; labels are the portable
baseline; a small structured body block carries what must round-trip exactly.

| prawduct concept | GitHub encoding | Notes / requirement |
|---|---|---|
| title / body | issue title / body | body carries a fenced `prawduct:` block for exact round-trip of non-native fields |
| **status** (submitted→open→in-progress→shipped/dropped) | open/closed **+ state-reason** (completed=shipped, not-planned=dropped) **+ `status:` label** for submitted/in-progress | two axes must survive (DM2) |
| **stage** (idea→…→ready) | **`stage:` label** | load-bearing: `pick` routing enforces requirements-precede-code |
| area / effort / impact / source | **labels** (`area:x`, `effort:M`, `impact:L`, `source:p`); **org Issue Fields** where the repo's owner is an org (enhancement) | soft, per-project vocabularies (DM1); labels fit them better than shared field defs; org Fields are personal-account-unavailable, so labels are baseline |
| **stable ID** `PFX-XXXX` | **preserved as an alias** (label `id:BKL-7M4Q` + the `prawduct:` body block); GitHub's issue number is the transport key | IDs never change; refs in change-logs/commits/learnings must keep resolving (DM4). **Recommended: keep minting human `PFX-XXXX` IDs** — GitHub numbers aren't project-prefixed for cross-project unambiguity |
| relationships: blocks/blocked-by · parent/child · related | **native issue dependencies** (GA 8/2025) · **sub-issues** (GA 4/2025) · issue references | ready-work query needs blockers queryable (DM3) |
| comments | issue comments | threaded, attributed, timestamped (DM5) |
| **claim / assignee** | issue **assignee** (human or agent identity) | atomic-take + verify; residual race accepted (CC3) |
| verification stamp | structured marker comment or `verified:YYYY-MM-DD` encoding | "premise re-checked against code" is one call + queryable (TF2) |
| mutation history / audit | issue **timeline/events** (native) | replaces git's free audit log (CC4) |
| attachments | **release-asset upload pattern wrapped** by the adapter | GitHub has no public attachment API — the one real gap (DM6) |

**Encoding validation is advisory and tolerant** (DM1): unknown label/field values are *flagged*,
never rejected; a fail-closed validator here would be a latent fail-close at the data seam (learning
on tolerating natural encoding variants — `[]` vs omitted, etc.).

### 7a. Persisted-schema decision research (mandated by the lock-in learning)

Two formats lock in — the GitHub encoding and the SQLite mirror — so the schema's requirements are
**the queries the data must answer over time**, enumerated now (fields are derived from these next
level down, not invented from the mechanism):

- structured filter over every DM1 field + full-text over title/body/comments (Q1)
- changed-since cursor (Q2) — the primitive the mirror and sweeps are built on
- top-k similar items for dedup at 500+ items (Q3)
- cross-project rollup ("open governance items anywhere"; "what consumers filed against prawduct this month") (Q4)
- counts/rollups derived on read, never persisted (Q5)
- **ready-work**: open items whose blockers are all closed, unclaimed, `stage: ready` (DM3+CC3+DM2)
- **stale-verification**: open items unverified in N days (TF2)
- provenance: items by `source:<product>` in `submitted` state (XP2)

## 8. Capability specification (what the system must do — priority-tagged)

Priority = importance (P0 core / P1 important / P2 valuable / P3 nice-to-have), **not** sequencing.

### 8.1 Agent ergonomics & data plane
- **[P0]** Deterministic CRUD — CLI + library, flags, no interactive prompts, no model in the loop (AG1, G1).
- **[P0]** One-call create; every field defaultable/backfillable; filing never blocks on classification (AG2).
- **[P0]** Non-blocking under failure — queue writes, mirror-served reads, never gate a session (AG4, G2).
- **[P0]** JSON + human output modes (AG6).
- **[P1]** Latency: warm reads < 500 ms (mirror); create/update p95 < 2 s (AG5).
- **[P2]** MCP surface over the same core library.
- **[P1]** Dedup-on-create advisory + asynchronous — returns ID immediately + candidate duplicates (AG3).

### 8.2 Truth, freshness & integrity
- **[P0]** Single live view; cache age always visible (TF1, G3).
- **[P0]** Atomic mutations; a crashed client never half-writes (CC1).
- **[P1]** No lost updates — optimistic concurrency (compare-and-set on state/updated-at), clean-fail-for-retry (CC2).
- **[P1]** Claims strongly consistent enough — assignee atomic-take + verify; staleness visible; reaping is policy (CC3).
- **[P1]** Every mutation records actor identity, kept as per-item history (CC4).
- **[P1]** Verification first-class & cheap — record + query "premise re-checked" (TF2).
- **[P1]** Mass grooming is a supported workload, not an abuse pattern (TF3).

### 8.3 Query
- **[P0]** Changed-since cursor (Q2) — engine for mirror + sweeps.
- **[P1]** Server-/mirror-side structured filters + full-text, sort, paginate (Q1).
- **[P1]** Lexical similarity for dedup (Q3, lexical).
- **[P2]** Semantic similarity for dedup (Q3, semantic — GitHub hybrid search GA 4/2026).
- **[P2]** Cross-project queries + Projects v2 rollup board (Q4).
- **[P1]** Counts/rollups derived on read (Q5).

### 8.4 Cross-project flow
- **[P1]** File upstream directly — no upstream checkout, no drop-box, no git (XP1).
- **[P1]** Provenance + `submitted` triage landing state (XP2).
- **[P2]** Anonymous filing on public projects (PV3) — GitHub account, no relationship.
- *XP3 (private submit-without-read) is **out** — owner-descoped; do not let it drive design.*

### 8.5 Privacy, access & auth
- **[P0]** Per-project visibility inherits repo access — structural, free (PV1).
- **[P0]** Agents authenticate with real, scoped, revocable per-machine/agent credentials — not a shared secret (PV2).
- **[P2]** Public submission surface, per-project choice (PV3).

### 8.6 Automation enablement
- **[P1]** Batch operations — update/label/merge N items in few idempotent calls (AU2).
- **[P2]** Merge & split as first-class primitives (preserve bodies, leave redirect) (AU3).
- **[P2]** Events (webhooks) or cheap polling for background workers (AU1).

### 8.7 Governance integration
- **[P0]** `/prawduct:backlog` keeps its UX contract as a thin wrapper; stage-aware `pick` survives (GV1).
- **[P0]** Session briefing reads counts from the mirror, refreshed async — start never waits on network (GV2).
- **[P0]** Zero-cost per-project provisioning via onboard/doctor — one command or none (GV5).
- **[P1]** Traceability replaces atomicity — record `closed-by`; reconciliation sweep detects drift both directions (GV3). *(General retro-governance is out — §13.)*
- **[P0]** Adopter-reproducible backend shipped inside the plugin (GV4, G4).

### 8.8 Data model
- **[P0]** Structured, queryable metadata as first-class fields; soft per-project enums (DM1).
- **[P0]** Two axes: status + stage, not flattened (DM2).
- **[P0]** Stable human-readable cross-project IDs; permanent redirects on merge; legacy-alias absorption (DM4).
- **[P1]** Relationship types queryable (DM3).
- **[P1]** Threaded attributed comments (DM5).
- **[P1]** Nothing hard-deleted by normal operation (DM7).
- **[P2]** Attachments ≥ 10 MB (DM6) — release-asset wrap.

### 8.9 Migration & exit
- **[P0]** One-shot importer: IDs, metadata, bodies, sections preserved verbatim; existing IDs stay valid (MG1).
- **[P0]** Full-fidelity export to files, scriptable, any time (MG2, G5).
- **[P0]** Per-project adoption; file + service backlogs coexist across the portfolio, never within one project (MG3).

## 9. Non-functional targets (concretized)
- **Cost (NF1):** **$0/month.** GitHub Issues, labels, and org Fields are free; no server. Well under the ~$10/mo portfolio ceiling, and — critically — **no per-project cost** as projects multiply.
- **Ops (NF2):** near-zero — GitHub hosts the store; the only local moving part is the mirror (a file).
- **Rate limits (NF3):** GitHub gives ~5k/hr core, tightest **80 writes/min** and **10 semantic searches/min**. Design lives inside them by construction: **reads are served from the mirror** (read amplification — dozens of concurrent grooming readers — never touches GitHub); the backend budget is spent on **writes and sync only**, paced under the write cap; semantic dedup paced under 10/min. Target ≥ 10× headroom on the ~200 writes/day/project workload.

## 10. Key design decisions (with rationale)
- **D1 — GitHub Issues as system of record; Projects v2 only for cross-repo rollup.** The 2024-era build-justifying gap closed by GitHub's 2025–26 shipping; GV4 + private-repo adopters + $0 make it the only option satisfying the whole set (parent doc's Build/Adopt/Buy).
- **D2 — Client = `gh api` (REST+GraphQL) via list-form subprocess.** Satisfies sync-only + subprocess-safety conventions, removes token handling; mirror absorbs read latency. *(Recommended; residual: spawn latency on writes — within budget.)*
- **D3 — Labels are the baseline encoding; org Issue Fields an enhancement.** Portfolio spans two owners incl. personal accounts (no Fields); labels also fit soft per-project vocabularies. Org consolidation is a later owner option, not a blocker.
- **D4 — Keep minting human `PFX-XXXX` IDs** as aliases alongside GitHub's number — refs continuity + cross-project unambiguity (DM4).
- **D5 — Mirror = SQLite, gitignored, git-common-dir keyed** — mirrors the evidence-store pattern and the shared-vs-personal-state learning.
- **D6 — Sync is synchronous; background refresh is a detached subprocess** — the no-asyncio convention; staleness re-evaluated against the cursor, never a cached blocker.
- **D7 — GitHub-native throughout, with a clean internal seam + export as the exit** — no premature multi-backend abstraction, but §8.9 export keeps lock-in cheap. *(Watch the "one instance colonizes the general requirement" learning: the adapter requirement is "a GitHub-hosted repo"; state that breadth explicitly rather than letting today's `gh` shape it silently.)*

## 11. Open decisions for the owner
- **O1 — Org consolidation?** Consolidating repos under a GitHub org unlocks typed Issue Fields and native cross-repo Projects. Not required (labels baseline). Decide at leisure.
- **O2 — Agent identity model:** fine-grained PATs per machine vs a GitHub App installation. Affects PV2 attribution granularity and revocation. Recommend GitHub App for fleet attribution; PAT is the low-ceremony start.
- **O3 — Attachment strategy:** release-asset wrap vs orphan-branch blobs. Both API-supported; release-asset is simpler. (P2, low urgency.)
- **O4 — Dedup engine:** lexical-only (mirror FTS) vs adopt GitHub's hybrid semantic search. Recommend lexical first; semantic is a drop-in P2.

## 12. Risks & mitigations
| Risk | Mitigation |
|---|---|
| GitHub rate limits under mass grooming | mirror serves all reads; writes/semantic paced; batch + idempotent (NF3, AU2) |
| `gh` spawn latency on the hot path | warm reads from in-process mirror; only cold writes pay it, within p95 budget |
| No attachment API | wrap release-asset upload (D3/O3); accept slightly rough edges |
| Claim double-pick race | assignee take-and-verify; documented residual race, far smaller than today's; not a mutex (CC3) |
| GitHub outage | never-block queue + mirror (G2); degrade to offline, flush on recovery |
| Vendor lock-in | cheap full-fidelity export (G5/MG2); most-portable format in the industry |
| Importer silently drops an already-shipped part | import against the **spec roster**, not the open-work list; canonical checkout only; wire backfill **and** legend-refresh (migration learnings) |
| Stage/label encoding drift across migration | sweep the guards **with tests**, not just prose; a guard with no test carries a stale literal through cutover |

## 13. Explicitly out of scope
- **Retro-governance / onboarding out-of-compliance PRs / existing-repo onboarding** — its own future spec; parked in backlog `MET-6T4K`. This PRD only *references* it (GV3 does the minimal reconciliation sweep; the general retroactive-cycle capability is separate).
- **Autonomous assign-to-agent *execution*** (issue→PR autopilot) — governance tension parked in `MET-6T4K`. (Assignee-as-*claim* is in scope, §8.2/CC3.)
- **The triage intelligence itself** — AU1–AU3 enable it; the workers are separate prawduct work.
- **PM-suite ceremonies** — sprints, velocity, time tracking, roadmapping, real-time presence.
- **Moving change-log / learnings / build plans** out of git — they stay; items link to them via refs.

## 14. Traceability
Every §8 capability cites its parent requirement ID; every requirement ID in
`backlog-service-requirements.md` appears in §8 (coverage check to run before sign-off). This PRD is
the child of that requirements doc and the parent of the next-level artifacts (§15).

## 15. What "drilling down" produces next (only after confidence in this level)
Per the layered process: once this PRD is agreed, the next level generates —
1. **Data Model** — the field-level GitHub encoding + mirror schema (fields derived from §7a queries).
2. **Non-Functional Requirements** artifact — latency/rate-limit/cost budgets made testable.
3. **Security Model** — auth (O2), token scope/revocation, provenance trust, public-submission abuse.
4. **API contract** — the CLI/MCP surface: operations, error model (return-value), versioning/compat.
5. **Test Specifications** — incl. the migration guard-sweep and offline/never-block behaviors.
6. **Build plan** — a thin vertical slice first (core lib → CLI → mirror → one GitHub round-trip →
   importer dry-run), proving the architecture end-to-end before widening. `.prawduct/artifacts/`.

Until then, no build plan and no field-level schema — this level is the thing to get confident in.
