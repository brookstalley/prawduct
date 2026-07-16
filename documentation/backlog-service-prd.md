# Backlog Service — Product Requirements & High-Level Design (PRD)

`status: draft v3 — owner-feedback pass folded (2026-07-14): identity resolved (GitHub App across owned orgs + user token for public/foreign filing — O2/D8); ID strategy resolved (repo-prefixed GitHub numbers, owner/repo#number canonical, PFX → migration alias — O4/D4); attachments reprioritized + inline-on-private spike added (O3/D9/S5); org model clarified to federated multi-owner (O1/D3); cache-freshness spike (S4) re-scoped to gate the cache layer, not the slice; §11 spikes re-tiered by what they gate — only S1 (→ HTTP decision) and S2 (migration dry-run / first slice) gate the core, S3 (tuning)/S4/S5 settle with their layer or feature. Prior v2: cache = optional/read-through, gh-vs-http reopened as a spike. · added: 2026-07-14 · source: planning session · stage: design`

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
- **GitHub client** — **HTTP is the leaning default; `gh` survives only as a bootstrap (D8/§11-S1)** — auth, not latency, is the deciding factor (App installation tokens are JWT-based; `gh` can't mint them cleanly). Whichever wins, list-form subprocess / no `shell=True` if `gh`; stdlib HTTP + explicit token handling if HTTP.
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
| **stable ID** (`owner/repo#number` canonical; `repo#number` short) | GitHub's issue **number** is the ID going forward; migrated `PFX-XXXX` become permanent **alias labels** (`id:…`) + body-block entries so old refs resolve | **D4/O4 resolved (§10)** — `owner/repo#number` is GitHub's own cross-ref syntax (auto-links, globally unique, disambiguates same-named repos across owners); no *new* PFX minted |
| relationships: blocks/blocked-by · parent/child · related | **native dependencies** (GA 8/2025) · **sub-issues** (GA 4/2025) · references | ready-work query needs blockers queryable (DM3) |
| comments | issue comments | threaded, attributed, timestamped (DM5) |
| **claim / assignee** | issue **assignee** (human or agent identity) | atomic-take + verify; residual race accepted (CC3) |
| verification stamp | marker comment or `verified:YYYY-MM-DD` encoding | "premise re-checked against code" is one call + queryable (TF2) |
| mutation history / audit | issue **timeline/events** (native) | replaces git's free audit log (CC4) |
| attachments | robust default: **release-asset wrap** *or* **dedicated attachments-branch** written via the git-data API (both deterministic, no PR) | GitHub has **no public attachment API** (verified 2026-03; the native `user-attachments` inline-upload endpoint is browser/session-cookie only — non-G1, an *attended-only* enhancement). Inline rendering **on private repos** is the open axis → **S5** (DM6/D9/O3) |

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
- **[P2, optional]** Offline write-queue (enhancement over fail-fast+retry). *Consequence of O4/D4:* since the ID is GitHub's number (assigned only after create returns), a queued create takes a **provisional local ID reconciled to `repo#number` on flush** — the one real cost of dropping prawduct-minted PFX.
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
- **[P2]** Cross-project queries + rollup (Q4). *O1 (federated multi-owner):* native Projects v2 rollup only spans **one owner**; **cross-owner** rollup is **query-side fan-out + merge** in our layer, not a GitHub-native feature.
- **[P1]** Counts/rollups derived on read (Q5).

### 8.4 Cross-project flow
- **[P1]** File upstream directly — no upstream checkout, no drop-box, no git (XP1).
- **[P1]** Provenance + `submitted` triage landing (XP2).
- **[P2]** Anonymous filing on public projects (PV3) — **with abuse handling (§13).**
- *XP3 (private submit-without-read) is **out** — owner-descoped.*

### 8.5 Privacy, access & auth
- **[P0]** Per-project visibility inherits repo access — structural, free (PV1).
- **[P0]** Agents authenticate with real, scoped, revocable credentials — not a shared secret (PV2). *Identity model resolved (O2/D8):* **GitHub App installed across owned orgs** (per-owner rate bucket, scoped, revocable, `[bot]` attribution) + a **user token** (`gh`/OAuth/PAT) for public/foreign repos the fleet isn't a member of. Per-**agent** attribution rides in the payload (assignee/marker), since neither transport carries agent-level actor identity. Governs rate-limit headroom, §9/§13.
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
- **[P0]** Stable, cross-project-unambiguous IDs; permanent redirects on merge; legacy-alias absorption (DM4). *Resolved (D4/O4, §10):* `owner/repo#number` canonical / `repo#number` short; migrated `PFX-XXXX` kept only as permanent aliases; no new PFX minted.
- **[P1]** Relationships queryable (DM3) · **[P1]** threaded comments (DM5) · **[P1]** nothing hard-deleted (DM7).
- **[P1]** Attachments (DM6) — **inline screenshots are a top use case** (owner, 2026-07-14), so not a P2 rough-edge. Robust default: release-asset wrap *or* attachments-branch via git-data API (both no-PR, G1-clean); native inline-upload is attended-only; inline-on-private gated by **S5** (D9). *(≥10 MB via the same wrap.)*

### 8.9 Migration & exit
- **[P0]** One-shot importer: IDs, metadata, bodies, sections preserved verbatim; existing IDs stay valid (MG1). **Highest-risk operation — own design + dry-run + rollback (§13).**
- **[P0]** Full-fidelity export to files, scriptable, any time (MG2, G5).
- **[P0]** Per-project adoption; file + service backlogs coexist across the portfolio, never within one project (MG3).

## 9. Non-functional targets (concretized)
- **Cost (NF1):** **$0/month.** GitHub Issues, labels, org Fields free; no server. No per-project cost.
- **Ops (NF2):** near-zero — GitHub hosts the store; the only optional local part is a cache file.
- **Rate limits (NF3):** GitHub gives ~5k/hr core, tightest **80 writes/min** and **10 semantic searches/min**. The *warm-cache* read path never touches GitHub; the budget is spent on **writes + sync**. *Identity model resolved (O2/D8):* a **GitHub App installation gets its own bucket per owner** — **5,000/hr baseline, +50/hr per repo and per user beyond 20, cap 12,500** (verified) — so each owned org's heavy traffic (sweeps, grooming, migration) is isolated in its own bucket rather than concentrated in the human's personal quota. Public/foreign filing runs on a user token but is **low-volume**, so concentration there is moot. S3 measures a real cold sweep + write-heavy grooming under this model. **Also:** GitHub's search index is not read-your-writes consistent — Q1/Q3 that must see just-written items run against the cache, not GitHub search.

## 10. Key design decisions
- **D1 — GitHub Issues as system of record; Projects v2 only for cross-repo rollup.** (Parent doc's Build/Adopt/Buy.)
- **D2 — GitHub client (`gh` vs HTTP): reopened, then narrowed toward HTTP by D8 (§11-S1).** Latency is *not* the pivot; dependency footprint, auth/identity, and cache revalidation are — and App-token auth (D8) is what tips it to HTTP, with `gh` surviving only as a bootstrap.
- **D3 — Labels are the baseline encoding; org Issue Fields an enhancement.** Portfolio spans personal accounts (no Fields); labels fit soft vocabularies. **O1 clarified (2026-07-14):** the model is **federated multi-owner** — one human sign-in's *existing* access across many owners is leveraged; the goal is *not* org consolidation and *not* per-repo credential sprawl. Org consolidation stays an optional enhancement (it unlocks typed Fields + native single-owner rollup); cross-owner rollup is query-side (§8.3-Q4). **Adds a label-taxonomy governance need (§13).**
- **D4 — Ongoing ID strategy: RESOLVED (O4, 2026-07-14) → repo-prefixed GitHub numbers.** GitHub's issue number is the ID going forward. **Canonical form `owner/repo#number`** — deliberately GitHub's own cross-reference syntax, so an ID *is* a live auto-link, is globally unique, and disambiguates same-named repos across unrelated owners (O1). **Short form `repo#number`** when project config makes the owner unambiguous (like short vs full git SHAs — one authority, context-scoped abbreviation, *not* two ID systems). CLI accepts `repo#number` / `repo-number` / `repo/number` and normalizes. Migrated **`PFX-XXXX` become permanent alias labels + body-block entries** (old refs resolve forever); **no new PFX minted** — this collapses two minting authorities into one, resolving adversarial finding §13-3. *Two named costs:* (a) no pre-GitHub ID → offline creates use a provisional local ID reconciled on flush (§8.1); (b) cross-repo `gh issue transfer` reassigns the number → also store the issue node-id (stable) or re-resolve.
- **D5 — Cache is optional, read-through, gitignored, git-common-dir keyed, revalidate-on-decision.** The core is correct without it (online-only). Reverses v1's mandatory-mirror stance per owner feedback + §13.
- **D6 — Sync is synchronous; background refresh is a detached subprocess** (no-asyncio convention); staleness re-evaluated against the cursor.
- **D7 — GitHub-native throughout, with a clean internal seam + export as the exit** — no premature multi-backend abstraction. *(State the requirement breadth explicitly — "a GitHub-hosted repo" — rather than letting today's client shape it, per the "one instance colonizes the requirement" learning.)*
- **D8 — Identity model: GitHub App across owned orgs + user token for the public/foreign plane (O2, 2026-07-14).** Derived from which goals each mechanism *can't* meet: the public/foreign plane (upstream/anonymous filing on repos the fleet isn't a member of) **structurally requires a user token** — you can't install an App you don't own — so a user credential can never be retired. A **fine-grained PAT can't be the "spans my orgs" credential** (single resource-owner, verified). So the scoped, safe realization of "leverage one sign-in across my orgs" is a **GitHub App installed per owned org** (per-owner rate bucket, scoped, revocable, `[bot]` attribution); `gh`/user creds are a legitimate low-ceremony *bootstrap* that upgrades to the App when rate/attribution bite. Implies a **credential-resolution layer keyed by target owner**. **Couples to S1:** App auth (JWT→installation token) fits HTTP, not `gh` — this nudges S1 toward HTTP for auth-bearing calls.
- **D9 — Attachments: release-asset (or attachments-branch) is the deterministic default; native inline is attended-only (O3, 2026-07-14).** The only mechanism that renders screenshots natively-inline *and* respects private-repo access is the `user-attachments` flow — and it's **browser/session-cookie auth, undocumented** (verified; `gh-image`/`gh-attach` both fall back to release-mode for CI), so it can't be the G1 data plane; it's an opt-in *attended* "pretty images" mode at most. Robust, API-only, PR-free options: **release-asset wrap** (release clutter, containable under a reserved tag) and **attachments-branch via git-data API** (off-main → untouched by the strip-`.prawduct`-from-main plan; no working tree, no PR). The tiebreaker — **does either render *inline* on a *private* repo?** — is **S5**. Leaning release-asset pending S5. Rejected: storing images under `.prawduct/issues/` on `main` (stripped from releases *and* forces commit+PR).

## 11. Open decisions & spikes to settle

**Spikes & pre-build questions — tiered by what they gate.** A spike earns "settle before build" only if its answer changes the design of the *next* increment (§16: core lib → CLI → one GitHub round-trip → importer dry-run). By that test only two items gate the core; the rest gate a later optional layer or a feature, or are runtime tuning that rides along with the build. (S-labels are stable — they're referenced in §8/§9/§12/§13 — only the grouping changed.)

**Tier 1 — gates the thin slice (settle or prove first):**
- **S1 — `gh` CLI vs direct HTTP → RESOLVED (2026-07-16): direct HTTP confirmed, auth flow specced.**
  Live probes (captured in `.prawduct/artifacts/api-notes-github-issues.md`) confirmed every P0
  endpoint family over plain stdlib-style HTTPS with a user token (`Authorization: Bearer`),
  including ETag/conditional-GET (304 on match, single + list endpoints) for the future cache
  layer. `gh` survives only as the token bootstrap (`gh auth token` fallback behind `GH_TOKEN`) —
  the auth flow and the owner-keyed App-upgrade seam are specced in
  `.prawduct/artifacts/security-model-backlog-service.md`. *(Prior analysis retained below in
  §10-D2/D8; latency was a footnote, and stayed one.)*
- **S2 — Migration dry-run** on discodon (317 open + 1,754-line archive): body-fidelity, ID aliasing, relationship reconstruction, archive-as-closed-issues volume/noise, rollback. Migration is the riskiest single op — and **this is not throwaway spike code; it *is* the thin slice's proving increment** (§16 already lists "importer dry-run"). Doing it first de-risks the foundational adopt-GitHub bet (MG1: existing IDs stay valid) at the earliest point.

**Tier 2 — gates a later optional layer or feature (settle when you build it, not before the core):**
- **S3 — Rate limits under the App-installation model** (O2/D8) — **runtime tuning, not design-gating.** Its answer is a *number* that changes pacing constants (batch size, backoff), not architecture: the design is already rate-limit-defensive (cache-first reads bypass GitHub; writes are the only budget; GitHub hard-caps writes at 80/min ≈ 4,800/hr, under the 5k App baseline). Measure a cold sweep + write-heavy grooming *during* the build and tune; the migration write-burst it worries about overlaps S2's volume analysis.
- **S4 — Cache freshness protocol** — **travels with the optional cache; does not gate the slice.** The **principle** (visible age + revalidate-on-decision, G3) is locked now; the **protocol** is settled only when perf data justifies building the optional cache (D5). Online-only, every read is live, so revalidation is trivially satisfied. When built: how a read "revalidates on decision" cheaply (conditional request / per-item since) without defeating the cache.
- **S5 — Attachment inline rendering on private repos** (gates the O3 default, D9) — a real spike, but it gates the **attachments feature**, not the architecture. Cheap experiment: on one private repo, embed (a) a release-asset download URL and (b) an attachments-branch raw URL via `![]()` and observe which renders inline for an authenticated viewer. Decides release-asset vs attachments-branch; if *neither* renders inline on private, inline-on-private is achievable only via the attended native flow. Settle when attachments are built.

**Owner decisions — all resolved 2026-07-14:**
- **O1 — Org model → RESOLVED: federated multi-owner (D3).** Not consolidation, not per-repo credentials — leverage one sign-in's existing multi-owner access; cross-owner rollup is query-side (§8.3-Q4).
- **O2 — Agent identity → RESOLVED: GitHub App across owned orgs + user token for public/foreign (D8).** Not "PAT vs App as a start" — a fine-grained PAT can't span orgs, and the public/foreign plane forces a user token regardless; the App is the scoped realization of "one identity across my orgs."
- **O3 — Attachment strategy → RESOLVED: release-asset (or attachments-branch), native-inline attended-only; reprioritized up (D9).** Gated by S5. `.prawduct/issues/`-on-main rejected.
- **O4 — Ongoing ID strategy → RESOLVED: repo-prefixed GitHub numbers, `owner/repo#number` canonical, PFX → migration alias (D4).**

## 12. Risks & mitigations
| Risk | Mitigation |
|---|---|
| **Cache re-creates the staleness we exist to kill** | cache optional + read-through + **visible age + revalidate-on-decision**; never silently serves stale (G3/D5) |
| GitHub **search index lag** (not read-your-writes) | dedup/query that must see just-written items runs against the cache, not GitHub search (§9) |
| **Rate-limit concentration** across the fleet | **GitHub App installation gives a per-owner bucket** (5k–12.5k/hr, D8) isolating each owned org's traffic; public/foreign filing is low-volume on a user token; sweeps paced + batched; warm reads from cache (NF3) |
| GitHub rate limits under mass grooming | warm-cache reads bypass GitHub; writes/semantic paced; batch idempotent |
| No public attachment API (native inline is browser/session-only) | robust default = release-asset wrap *or* attachments-branch via git-data API (both no-PR, G1); native inline as an attended-only enhancement; **S5** settles inline-on-private (D9) |
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
| 3 | over-complication | Two ID systems forever may be redundant | **Resolved** (2026-07-14) — D4/O4: repo-prefixed GitHub numbers going forward, PFX → migration alias only; two minting authorities collapsed to one |
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
3. **Security Model** — auth per D8 (App installation tokens + user-token public/foreign plane; credential-resolution keyed by target owner), token scope/revocation, provenance trust, **public-submission abuse** (§13-7).
4. **API contract** — CLI/MCP surface: operations, return-value error model, versioning/compat.
5. **Test Specifications** — incl. migration guard-sweep + offline/never-block behaviors.
6. **Build plan** — thin vertical slice first (core lib → CLI → one GitHub round-trip → importer dry-run), architecture proven before widening. `.prawduct/artifacts/`.

Only two §11 items gate the core: **S1** (confirm HTTP + auth spec) and **S2** (the migration dry-run — which *is* the slice's first increment). **S3/S4/S5** settle with their layer or feature, not before. Until this level is agreed, no build plan and no field-level schema.
