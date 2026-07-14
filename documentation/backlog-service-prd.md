# Backlog Service — Product Requirements & High-Level Design (PRD)

`status: draft v2 — adversarial pass + owner feedback folded (cache = optional/read-through; gh-vs-http reopened as a spike) · added: 2026-07-14 · source: planning session · stage: design`

**Parent:** `documentation/backlog-service-requirements.md` — the problem, the 8-project evidence
sweep, and the adopt-vs-build decision that selected **GitHub Issues as system of record + a
deterministic prawduct adapter**. This PRD specs the *chosen* system: what it does, the shape that
makes it coherent, and how its capabilities are prioritized. Requirement IDs below (DM1, AG4, …)
trace to that parent — this doc designs against them rather than restating them.

**Planning altitude (read this first).** This is the **top level of a layered plan**: *what the
system must do* and *the shape that makes it hang together* — deep enough to be confident, no deeper.
It **does not** partition v1-vs-later, sequence chunks, or fix field-level schemas (that is the next
level, §16). **Priorities (P0–P3) rank importance, not release timing** — a P3 ships in the first
slice if it is cheap; a P1 may land later if it is expensive. We will *build* a thin slice, but we
spec the whole system so the slice is cut from a coherent whole.

---

## 1. Vision

A backlog a fleet of agents and one human can trust: **one live source of truth per project, mutated
only by deterministic code, reachable from every checkout, and free.** The backlog stops being a
merge-prone markdown file an LLM edits by hand and becomes GitHub Issues fronted by a thin prawduct
adapter — so item state is never stale-by-checkout, CRUD costs zero model tokens, and every adopter
already owns the backend.

## 2. Users & personas

| Persona | Who | Needs from the system |
|---|---|---|
| **Project agent** | a Claude session working a repo | file / query / pick / update / claim / comment in one non-interactive call, zero model tokens, never blocked by the network |
| **Consumer agent** | a session in a *downstream* product | file *upstream* against another project with provenance, no upstream checkout |
| **Human** (owner + collaborators) | Brooks; future collaborators | browse, prioritize, comment, decide in a UI they already have (GitHub) — no new tool to learn or pay for |
| **Background worker** | unattended triage / dedup / reconciliation | bulk read + batch mutate dozens of items per pass without rate-limit pain |
| **Anonymous filer** | a third party, no relationship to the owner | file a bug against a *public* project (a GitHub account is the only barrier) |

## 3. Core flows

1. **File** — `title` + `body` → one call → new item with ID, returns immediately; similar-item candidates returned advisory-async.
2. **Pick next work** — stage-aware, dependency-aware ("ready items whose blockers are all closed, unclaimed"); routes early-stage items to discovery, not code.
3. **Update / claim / comment** — field-wise update, atomic-ish claim, threaded comment.
4. **Grooming sweep** — background worker: bulk re-stamp / close / relabel / merge in few paced calls; dozens of concurrent readers.
5. **File upstream** — item lands in another project's backlog in a `submitted` triage state with source/version/session provenance.
6. **Browse & decide** — human, in GitHub's issue UI + Projects board — no bespoke UI built.
7. **Migrate** — one-time per project: `backlog.md` (+ archive) → issues, IDs and bodies preserved.
8. **Export** — any time: issues → plain files (backup + exit).

## 4. Success criteria

- File/query in **one non-interactive call, p95 < 2 s, zero model tokens** on the CRUD path.
- Two agents in parallel worktrees + a human in a browser mutate concurrently with **no lost updates and no merge conflicts, ever.**
- **Every checkout sees the same live state** — the observed "66 closed items shown as open" worktree becomes structurally impossible.
- A consumer files upstream **with no local checkout and no drop-box** of the target.
- discodon's ~317 open items **migrate with IDs preserved**, and grooming gets *cheaper*.
- **$0/month**, with **no per-project cost** as the portfolio grows.

## 5. Governing invariants (violate any and the design is wrong)

- **G1 — Code, never a model, in the data plane.** All CRUD is deterministic code. Model judgment is reserved for triage *decisions*, never data plumbing.
- **G2 — Never block a session.** A backend failure must never hang, crash, or corrupt: it **degrades cleanly** — writes fail fast with a clear, retryable error (an offline write-queue is an *optional* enhancement, §8.1); reads serve from the read-through cache when warm, else return a clear "unavailable" with guidance. Gates and hooks that read backlog state must tolerate "unavailable" gracefully. *Never-block means never-hang/corrupt + graceful degradation — not "always works offline."*
- **G3 — One live view, and freshness beats latency.** GitHub is the single source of truth; every checkout reads the same current state. Any cached read carries **visible age**, and a read that drives a decision **revalidates** (cheap conditional request) rather than trusting the cache. **The cache must never silently serve stale data — silent staleness is the exact failure this project exists to kill.** (This is why the cache is subordinate and optional, §6.)
- **G4 — Adopter-reproducible & free.** Any adopter can stand this up at $0 — including adopters in private repos the owner cannot access. No backend, and no *client dependency*, bespoke to one machine (see the gh-vs-http spike, §11-S1).
- **G5 — Cheap exit.** Full-fidelity export to plain files any time; the backlog is never hostage to a vendor or server. Export doubles as backup.

## 6. Target architecture

The center of gravity is deliberately small. **The minimal viable system is a thin *online* CLI over
GitHub with no cache and no queue** — and it already delivers the #1 win (trust / one-live-view) for
free, because it always reads live. Everything else is an *optional* layer earning its keep for a
specific workload.

```
  /prawduct:backlog skill (GV1)     MCP server          human → GitHub web UI
            │                          │                       │
            ▼                          ▼                       │
       prawduct backlog CLI ─────► core library (lib/backlog/) │
        (flags, JSON+human)         - deterministic CRUD (G1)  │
                                    - return-value errors      │
                                    - sync only (no asyncio)   │
                                            │                  │
                                            ▼                  │
                                     GitHub client  ───────────┼──► GitHub Issues
                                     (gh CLI *or* HTTP —        │    (SOURCE OF TRUTH)
                                      SPIKE §11-S1)             │
              ─────────── optional layers (off by default) ────────────
              • read-through cache (SQLite, per-clone, gitignored,
                git-common-dir keyed): warm reads + offline reads,
                VISIBLE AGE, revalidate-on-decision (G3). Earns its
                keep for read-amplification (48-agent sweeps) + offline.
              • offline write-queue: queue-and-flush writes made while
                GitHub was unreachable (enhancement over fail-fast+retry).
              • bulk prefetch (since-cursor, Q2): warms the cache for a
                heavy sweep in one pass instead of a miss-storm.
```

**Components**
- **Core library** (`lib/backlog/…`, Python 3.10+, **sync**, **return-value errors** per project conventions). The only place CRUD logic lives; CLI/MCP/skill are thin fronts.
- **GitHub client** — **`gh` CLI vs direct HTTP is an open spike (§11-S1)**; latency is *not* the deciding factor. Whichever wins, list-form subprocess / no `shell=True` if `gh`; stdlib HTTP + explicit token handling if HTTP.
- **Read-through cache (optional)** — SQLite, per-clone, **gitignored**, `git-common-dir`-keyed (shared across a clone's worktrees, as the evidence store is). *Derived personal state, never the truth* (the "shared-answer vs personal-nag state live in separate stores" learning). Fetch-on-miss, serve-on-hit with visible age, revalidate when a read drives a decision. **Optional:** the system is correct without it (online-only), just slower and online-only.
- **Offline write-queue (optional)** — append-only local log of mutations made while offline; flushed on reconnect; each entry atomic. An enhancement over the P0 floor (fail-fast + retry).
- **Sync / prefetch** — synchronous; a detached **subprocess** (not an async task) may warm the cache at session start so the briefing never waits (G2/GV2). Staleness is re-evaluated against GitHub's cursor, never inferred from a leftover marker (learning).
- **Fronts** — `prawduct backlog` CLI (JSON + human, AG6); MCP server (thin); `/prawduct:backlog` skill (unchanged UX, GV1).

## 7. Data-model mapping (design intent, not the field-level schema)

prawduct item ↔ GitHub issue. Native features where they fit; labels the portable baseline; a small
structured body block for exact round-trip of non-native fields.

| prawduct concept | GitHub encoding | Notes / requirement |
|---|---|---|
| title / body | issue title / body | body carries a fenced `prawduct:` block for exact round-trip |
| **status** (submitted→open→in-progress→shipped/dropped) | open/closed **+ state-reason** (completed=shipped, not-planned=dropped) **+ `status:` label** for submitted/in-progress | two axes must survive (DM2) |
| **stage** (idea→…→ready) | **`stage:` label** | load-bearing: `pick` routing enforces requirements-precede-code |
| area / effort / impact / source | **labels**; org **Issue Fields** where the owner is an org (enhancement) | soft per-project vocabularies (DM1); labels fit them; org Fields unavailable on personal accounts |
| **stable ID** `PFX-XXXX` | **alias** (label `id:…` + body block); GitHub's number is transport | **D4 is reconsidered (§10)** — keep minting PFX forever, or use repo-prefixed GitHub numbers going forward and keep PFX only as migration aliases? |
| relationships: blocks/blocked-by · parent/child · related | **native dependencies** (GA 8/2025) · **sub-issues** (GA 4/2025) · references | ready-work query needs blockers queryable (DM3) |
| comments | issue comments | threaded, attributed, timestamped (DM5) |
| **claim / assignee** | issue **assignee** (human or agent identity) | atomic-take + verify; residual race accepted (CC3) |
| verification stamp | marker comment or `verified:YYYY-MM-DD` encoding | "premise re-checked against code" is one call + queryable (TF2) |
| mutation history / audit | issue **timeline/events** (native) | replaces git's free audit log (CC4) |
| attachments | **release-asset upload wrapped** by the adapter | GitHub has no public attachment API — the one real gap (DM6) |

**Encoding validation is advisory and tolerant** (DM1): unknown values are *flagged*, never rejected
(a fail-closed validator here is a latent fail-close — learning on tolerating natural encoding
variants). **Two adversarial gaps this table surfaces** (see §13): a repo's *existing* Issues/labels
may collide with prawduct's taxonomy, and a human editing in the GitHub UI can introduce label/state
drift the adapter must reconcile.

### 7a. Persisted-schema decision research (mandated by the lock-in learning)

The schema's requirements are **the queries the data must answer over time** (fields are derived from
these next level down, not invented from the mechanism). When the optional cache is present, it is a
projection of exactly these queries:

- structured filter over every DM1 field + full-text over title/body/comments (Q1)
- changed-since cursor (Q2) — the primitive for incremental cache refresh and sweeps
- top-k similar items for dedup at 500+ items (Q3)
- cross-project rollup (Q4) · counts derived on read (Q5)
- **ready-work**: open, blockers all closed, unclaimed, `stage: ready` (DM3+CC3+DM2)
- **stale-verification**: open items unverified in N days (TF2)
- provenance: items by `source:<product>` in `submitted` state (XP2)

## 8. Capability specification (what the system must do — priority-tagged)

Priority = importance (P0 core / P1 important / P2 valuable / P3 nice-to-have), **not** sequencing.

### 8.1 Agent ergonomics & data plane
- **[P0]** Deterministic CRUD — CLI + library, flags, no interactive prompts, no model in the loop (AG1, G1).
- **[P0]** One-call create; every field defaultable/backfillable; filing never blocks on classification (AG2).
- **[P0]** Never-block **floor**: a backend failure never hangs/crashes/corrupts; writes fail fast with a retryable error; gates/hooks tolerate "unavailable" (AG4, G2).
- **[P0]** JSON + human output (AG6).
- **[P1]** Read-through cache — warm reads + offline reads, visible age, revalidate-on-decision (accelerator, not core).
- **[P1]** Dedup-on-create advisory + async — returns ID immediately + candidates (AG3).
- **[P1]** Latency target: warm reads < 500 ms (from cache), create/update p95 < 2 s (AG5) — *a target, it does not mandate a mirror.*
- **[P2]** MCP surface over the same core library.
- **[P2, optional]** Offline write-queue (enhancement over fail-fast+retry).
- **[P2, optional]** Bulk prefetch (since-cursor) to warm the cache for heavy sweeps.

### 8.2 Truth, freshness & integrity
- **[P0]** Single live view; freshness beats latency; visible age; no silent staleness (TF1, G3).
- **[P0]** Atomic mutations; a crashed client never half-writes (CC1).
- **[P1]** No lost updates — optimistic concurrency (compare-and-set on state/updated-at), clean-fail-for-retry (CC2).
- **[P1]** Claims consistent-enough — assignee atomic-take + verify; staleness visible; reaping is policy (CC3).
- **[P1]** Every mutation records actor identity, kept as per-item history (CC4).
- **[P1]** Verification first-class & cheap — record + query "premise re-checked" (TF2).
- **[P1]** Mass grooming is a supported workload (TF3).
- **[P1]** Human-UI drift reconciliation — tolerate + reconcile label/state changes a human makes directly in GitHub (adversarial §13).

### 8.3 Query
- **[P1]** Changed-since cursor (Q2) — engine for incremental refresh + sweeps.
- **[P1]** Structured filters + full-text, sort, paginate (Q1) — *served from cache to avoid GitHub search-index lag (§13).*
- **[P1]** Lexical similarity for dedup (Q3, lexical) — *cache-based, read-your-writes consistent.*
- **[P2]** Semantic similarity for dedup (Q3, semantic — GitHub hybrid search GA 4/2026).
- **[P2]** Cross-project queries + Projects v2 rollup (Q4) — *limited across owners (§13).*
- **[P1]** Counts/rollups derived on read (Q5).

### 8.4 Cross-project flow
- **[P1]** File upstream directly — no upstream checkout, no drop-box, no git (XP1).
- **[P1]** Provenance + `submitted` triage landing (XP2).
- **[P2]** Anonymous filing on public projects (PV3) — **with abuse handling (§13).**
- *XP3 (private submit-without-read) is **out** — owner-descoped.*

### 8.5 Privacy, access & auth
- **[P0]** Per-project visibility inherits repo access — structural, free (PV1).
- **[P0]** Agents authenticate with real, scoped, revocable per-machine/agent credentials — not a shared secret (PV2). *(Identity model = O2; it also governs rate-limit headroom, §9/§13.)*
- **[P2]** Public submission surface, per-project choice (PV3).

### 8.6 Automation enablement
- **[P1]** Batch operations — update/label/merge N items in few idempotent calls (AU2).
- **[P2]** Merge & split first-class (preserve bodies, leave redirect) (AU3).
- **[P2]** Events (webhooks) or cheap polling (AU1).

### 8.7 Governance integration
- **[P0]** `/prawduct:backlog` keeps its UX contract; stage-aware `pick` survives (GV1).
- **[P0]** Session briefing reads counts from cache/online, refreshed async — start never waits (GV2).
- **[P0]** Zero-cost per-project provisioning via onboard/doctor — one command or none (GV5), **including the label taxonomy + coexistence with the repo's existing Issues (§13).**
- **[P1]** Traceability replaces atomicity — record `closed-by`; reconciliation sweep detects drift both directions (GV3). *(General retro-governance is out — §14.)*
- **[P0]** Adopter-reproducible backend shipped inside the plugin (GV4, G4).

### 8.8 Data model
- **[P0]** Structured, queryable metadata; soft per-project enums (DM1).
- **[P0]** Two axes: status + stage, not flattened (DM2).
- **[P0]** Stable human-readable cross-project IDs; permanent redirects on merge; legacy-alias absorption (DM4). *(Ongoing-ID strategy = D4, §10.)*
- **[P1]** Relationships queryable (DM3) · **[P1]** threaded comments (DM5) · **[P1]** nothing hard-deleted (DM7).
- **[P2]** Attachments ≥ 10 MB (DM6) — release-asset wrap.

### 8.9 Migration & exit
- **[P0]** One-shot importer: IDs, metadata, bodies, sections preserved verbatim; existing IDs stay valid (MG1). **Highest-risk operation — own design + dry-run + rollback (§13).**
- **[P0]** Full-fidelity export to files, scriptable, any time (MG2, G5).
- **[P0]** Per-project adoption; file + service backlogs coexist across the portfolio, never within one project (MG3).

## 9. Non-functional targets (concretized)
- **Cost (NF1):** **$0/month.** GitHub Issues, labels, org Fields free; no server. No per-project cost.
- **Ops (NF2):** near-zero — GitHub hosts the store; the only optional local part is a cache file.
- **Rate limits (NF3):** GitHub gives ~5k/hr core, tightest **80 writes/min** and **10 semantic searches/min**. The *warm-cache* read path never touches GitHub; the budget is spent on **writes + sync**. **Adversarial caveat (§13):** a *cold* cache or write-heavy sweep across a fleet **sharing one token** hits a single bucket — headroom depends on the identity model (O2): per-agent tokens spread the limit, a shared token concentrates it. **Also:** GitHub's search index is not read-your-writes consistent — Q1/Q3 that must see just-written items run against the cache, not GitHub search.

## 10. Key design decisions
- **D1 — GitHub Issues as system of record; Projects v2 only for cross-repo rollup.** (Parent doc's Build/Adopt/Buy.)
- **D2 — GitHub client (`gh` vs HTTP): REOPENED as a spike (§11-S1).** Latency is *not* the pivot; dependency footprint, auth/identity, and cache revalidation are.
- **D3 — Labels are the baseline encoding; org Issue Fields an enhancement.** Portfolio spans personal accounts (no Fields); labels fit soft vocabularies. Org consolidation is a later owner option (O1), not a blocker. **Adds a label-taxonomy governance need (§13).**
- **D4 — Ongoing ID strategy: RECONSIDERED.** Keep minting human `PFX-XXXX` forever (refs continuity + cross-project unambiguity) *vs* use repo-prefixed GitHub numbers going forward and keep `PFX-XXXX` only as migration aliases (less parallel machinery). Open — see §11-O4.
- **D5 — Cache is optional, read-through, gitignored, git-common-dir keyed, revalidate-on-decision.** The core is correct without it (online-only). Reverses v1's mandatory-mirror stance per owner feedback + §13.
- **D6 — Sync is synchronous; background refresh is a detached subprocess** (no-asyncio convention); staleness re-evaluated against the cursor.
- **D7 — GitHub-native throughout, with a clean internal seam + export as the exit** — no premature multi-backend abstraction. *(State the requirement breadth explicitly — "a GitHub-hosted repo" — rather than letting today's client shape it, per the "one instance colonizes the requirement" learning.)*

## 11. Open decisions & spikes to settle

**Spikes (must investigate before build — the answer changes the design):**
- **S1 — `gh` CLI vs direct HTTP.** Criteria, in priority order: (1) **adopter dependency footprint** — does requiring `gh` violate G4 for minimal/CI environments? (2) **auth & per-agent identity** — `gh` reuses existing creds (great solo) but is awkward for scoped per-agent tokens; HTTP gives per-agent token control (PV2/CC4) but we handle tokens. (3) **cache revalidation** — HTTP ETags/conditional-GET vs `gh`. (4) **API-change insulation** — `gh` shields us; HTTP tracks drift. Deliverable: a recommendation with evidence, tied to O2. *(Latency is a footnote, not a criterion.)*
- **S2 — Migration dry-run** on discodon (317 open + 1,754-line archive): body-fidelity, ID aliasing, relationship reconstruction, archive-as-closed-issues volume/noise, rollback. Migration is the riskiest single op.
- **S3 — Rate limits under the *real* identity model** (S1/O2): measure a cold sweep + write-heavy grooming against one token vs per-agent tokens.
- **S4 — Cache freshness protocol**: how a read "revalidates on decision" cheaply (conditional request / per-item since) without defeating the cache.

**Owner decisions:**
- **O1 — Org consolidation?** Unlocks typed Issue Fields + native cross-repo Projects. Not required.
- **O2 — Agent identity:** fine-grained PATs per machine vs a GitHub App installation (affects PV2, CC4, and NF3 headroom). Recommend GitHub App for fleet attribution; PAT is the low-ceremony start.
- **O3 — Attachment strategy:** release-asset wrap vs orphan-branch (P2).
- **O4 — Ongoing ID strategy (D4):** mint PFX forever vs GitHub-numbers-going-forward + PFX-as-migration-alias.

## 12. Risks & mitigations
| Risk | Mitigation |
|---|---|
| **Cache re-creates the staleness we exist to kill** | cache optional + read-through + **visible age + revalidate-on-decision**; never silently serves stale (G3/D5) |
| GitHub **search index lag** (not read-your-writes) | dedup/query that must see just-written items runs against the cache, not GitHub search (§9) |
| **Shared-token rate-limit concentration** across the fleet | per-agent identity (O2) spreads the bucket; sweeps paced + batched; reads from cache (NF3) |
| GitHub rate limits under mass grooming | warm-cache reads bypass GitHub; writes/semantic paced; batch idempotent |
| No attachment API | wrap release-asset upload (O3); accept rough edges |
| Claim double-pick race | assignee take-and-verify; documented residual race, not a mutex (CC3) |
| GitHub outage | never-block floor (fail-fast+retry); optional queue + cache degrade gracefully (G2) |
| Vendor lock-in | cheap full-fidelity export (G5/MG2) |
| **Migration drops an already-shipped part / breaks a guard** | import against the **spec roster** not the open-work list; canonical checkout only; wire backfill **and** legend-refresh; sweep guards **with tests** (learnings) |
| **Label taxonomy drift** across repos / **collision with existing Issues** | GV5 provisions + reconciles the taxonomy; namespace prawduct's labels; coexistence design (§13) |
| **Public-submission spam** (PV3) | abuse handling in the Security Model (§16); PV3 is per-project opt-in |
| Human-UI edits create unexpected state | advisory-tolerant validation + reconciliation sweep (§8.2) |

## 13. Adversarial review (self, 2026-07-14) — findings & disposition
| # | Category | Finding | Disposition |
|---|---|---|---|
| 1 | over-complication | Cache/queue were in the core; the minimal viable system is a thin *online* CLI that already delivers the trust win | **Folded** — cache/queue now optional layers (§6, D5) |
| 2 | user-need | Over-indexed on latency (minor pain) with a mirror that risks re-creating staleness (major pain) | **Folded** — freshness-beats-latency (G3); AG5 no longer mandates a mirror |
| 3 | over-complication | Two ID systems forever may be redundant | **Open** — D4/O4 |
| 4 | missing | Label taxonomy governance (provisioning, cross-repo consistency, collision) | **Folded** — GV5 + risk; Data/Ops next level |
| 5 | missing | Coexistence with a repo's *existing* Issues on adoption | **Folded** — GV5 + risk; adoption design next level |
| 6 | missing | GitHub search not read-your-writes consistent → dedup/query miss recent items | **Folded** — cache-based query/dedup (§9, §8.3) |
| 7 | missing | Public-submission abuse/spam (PV3) | **Folded** — flagged for Security Model (§16) |
| 8 | understated | Shared-token rate limits concentrate across the fleet | **Folded** — NF3 caveat + O2 + S3 |
| 9 | understated | Migration is the riskiest single op | **Folded** — MG1 note + S2 |
| 10 | user-need | Human-in-GitHub-UI drift (feature + drift source; no stage affordances) | **Folded** — §8.2 reconciliation; UX gap noted |

*Not yet independently reviewed.* An independent Critic/fresh-eyes pass is available before the next level if desired (Principle 14).

## 14. Explicitly out of scope
- **Retro-governance / onboarding out-of-compliance PRs / existing-repo onboarding** — its own future spec; parked in `MET-6T4K`. GV3 does the minimal reconciliation sweep; the general capability is separate.
- **Autonomous assign-to-agent *execution*** (issue→PR autopilot) — parked in `MET-6T4K`. (Assignee-as-*claim* is in scope, CC3.)
- **The triage intelligence itself** — AU1–AU3 enable it; the workers are separate work.
- **PM-suite ceremonies** — sprints, velocity, time tracking, roadmapping, real-time presence.
- **Moving change-log / learnings / build plans** out of git.

## 15. Traceability
Every §8 capability cites its parent requirement ID; every requirement ID in
`backlog-service-requirements.md` appears in §8 (coverage check passed at v1; re-run before sign-off).

## 16. What "drilling down" produces next (only after confidence in this level)
1. **Data Model** — field-level GitHub encoding + optional-cache schema (fields derived from §7a).
2. **Non-Functional Requirements** — latency/rate-limit/cost budgets made testable.
3. **Security Model** — auth (O2), token scope/revocation, provenance trust, **public-submission abuse** (§13-7).
4. **API contract** — CLI/MCP surface: operations, return-value error model, versioning/compat.
5. **Test Specifications** — incl. migration guard-sweep + offline/never-block behaviors.
6. **Build plan** — thin vertical slice first (core lib → CLI → one GitHub round-trip → importer dry-run), architecture proven before widening. `.prawduct/artifacts/`.

Plus the spikes (§11 S1–S4) that gate the design. Until this level is agreed, no build plan and no field-level schema.
