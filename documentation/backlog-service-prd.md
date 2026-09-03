# Backlog Service — Product Requirements & High-Level Design (PRD)

`status: draft v4 (+ build-plan coherence sweep 2026-07-16, from the §16(6) Build-plan drill-down review: §8.9/MG2 export-representation pointer corrected — the fidelity contract is NFR §8, the serialized fields are Data Model §1.1/§1.3/§2, and the on-disk layout is a build-time decision, not a Data Model altitude decision) (+ coherence touch-up 2026-07-16, from the §16(5) Test-Specs review): §9 semantic-search rate promoted unverified→**verified** (10/min, GA 2026-04-02, independent of code-search, per NFR §9); the "no clean issue-delete" phrasing tightened to the load-bearing "never **reuses** numbers" (delete is an admin-only destructive action) at §9/§11-S1/§13-M6. Prior v4 — independent-review pass folded (2026-07-16): a fresh-eyes design critic + a GitHub-fact verifier reviewed v3. Folded: slice-scope reframed to what the cacheless online slice truly delivers — one live *view* (kills stale-views, pain #2) + zero-conflict + zero-token CRUD + online-consistent pick — NOT the #1 stale-*content* pain, which needs TF2/TF3 + the one-time migration scrub (B1/M7); Q1 split so ready-work/pick runs online-consistent in the slice (M8); minimal persisted counts admitted to the P0 floor (GV2/M3); write budget corrected to 80/min AND ~500/hr — ~10× tighter, sizes the migration (fact #3); two-axis write-order + reconciliation (CC1/M5); rollback redefined as idempotent resumable import (MG1/M6); default claim-TTL so pick can't starve (CC3/M11); ID immutability boundary on transfer (D4/M4); export fidelity contract (G5/M10); migration reframed prawduct-first + pre-migration scrub (owner, 2026-07-16). Resolved O5 — P0-slice auth/transport (owner, 2026-07-16): the adapter **inherits the session's GitHub auth**, **`gh` is the required portable transport** (the only thing that survives local + cloud-proxy), raw HTTP an optional fast-path where a real token is in hand, App an optional per-owner upgrade; this narrows S1 to the cloud-proxy *optimization* test + ETag + the M6 facts (core transport decided). Four requirements written back to the parent (CC5/PV4/GV6/MG4). Prior v3: owner-feedback pass (O1–O4/D3–D9); prior v2: cache = optional/read-through, gh-vs-http reopened. · added: 2026-07-14 · source: planning session · stage: design`

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
adapter — so item state is never stale-*by-checkout*, CRUD costs zero model tokens, and every adopter
already owns the backend. *Precisely (B1):* one-live-view kills stale **views** (the portfolio's #2
pain); stale **content** (the #1 pain — `ready` items already shipped) is attacked by verification +
grooming (TF2/TF3) plus a one-time pre-migration scrub, not by centralization alone.

## 2. Users & personas

> **SUPERSEDED THROUGHOUT — the claim primitive (W1, 2026-08-07).** This PRD specifies *claim* as a
> first-class capability in the places listed below, and it is retired on the Issues backend:
> `claim` / `unclaim`, `pick --claim`, the stored `claimed_at`, the staleness TTL and the reap tier
> are all gone, replaced by `working-branch: owner/repo@branch` — a pushed branch says someone is on
> the item, and its own last commit answers what the TTL was guessing at. No timestamp is stored, no
> expiry is configured, nothing is reaped. Strong consistency is **not** claimed and never was: this
> makes a double-take *visible* rather than impossible. The retirement is scoped to the **Issues
> adapter**; the markdown backend keeps `accepted-by:`, which has none of the three mechanisms.
> `backlog-service-requirements.md` CC3 carries the reasoning in full. Affected here: the actor table
> (§actors), capabilities 2–3, the field-mapping table (**claim / assignee**), the ready-work
> definition, the P0/P1 scope lines, the M11 risk fold, and the §13 scope-out note. They are left
> in place rather than rewritten — this is the parent document and its record of what was specified
> is what makes the supersession legible — but nothing below marked *claim* is the shipped design.


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
- discodon's ~317 open items **migrate with IDs preserved** (prawduct's own backlog migrates *first* — dogfood — and both are *scrubbed* before import, §8.9); grooming gets *cheaper* **once the optional read-cache lands** — the 48-reader sweep is a cache-served workload (§9); the cacheless slice is rate-safe only for low-fan-out use.
- **$0/month**, with **no per-project cost** as the portfolio grows.

## 5. Governing invariants (violate any and the design is wrong)

- **G1 — Code, never a model, in the data plane.** All CRUD is deterministic code. Model judgment is reserved for triage *decisions*, never data plumbing.
- **G2 — Never block a session.** A backend failure must never hang, crash, or corrupt: it **degrades cleanly** — writes fail fast with a clear, retryable error (an offline write-queue is an *optional* enhancement, §8.1); reads serve from the read-through cache when warm, else return a clear "unavailable" with guidance. Gates and hooks that read backlog state must tolerate "unavailable" gracefully. *Never-block means never-hang/corrupt + graceful degradation — not "always works offline."*
- **G3 — One live view, and freshness beats latency.** GitHub is the single source of truth; every checkout reads the same current state. Any cached read carries **visible age**, and a read that drives a decision **revalidates** (cheap conditional request) rather than trusting the cache. **The cache must never silently serve stale data — silent staleness is the exact failure this project exists to kill.** (This is why the cache is subordinate and optional, §6.)
- **G4 — Adopter-reproducible & free.** Any adopter can stand this up at $0 — including adopters in private repos the owner cannot access. No backend, and no client dependency *bespoke to one machine* — **`gh` is a required tool (O5), but it is standard, free, and `brew`/`apt`-installable, not bespoke**; the App stays optional (§11-S1).
- **G5 — Cheap exit.** Full-fidelity export to plain files any time; the backlog is never hostage to a vendor or server. Export doubles as backup. *("Full-fidelity" = a cheap **dump** that also serializes the native graph — dependencies, sub-issues, timeline, assignees; re-import into a *non-GitHub* backend is non-trivial, so cheap means cheap-out, not lossless one-liner re-import — fidelity contract in §8.9/MG2, M10.)*

## 6. Target architecture

The center of gravity is deliberately small. **The minimal viable system is a thin *online* CLI over
GitHub with no cache and no queue** — and it already delivers, for free because it always reads live:
**one live *view* (kills the stale-views pain, #2), zero merge conflicts (#3), zero-token deterministic
CRUD, and — once Q1 is split (§8.3) — an online, read-your-writes-consistent `pick`.** It does **not**
by itself deliver the #1 pain (stale/wrong *content*): that needs verification + grooming (TF2/TF3,
P1) and the one-time pre-migration scrub (§8.9). The slice is necessary but not sufficient for the top
pain — an honest scope, not a re-scope (B1). Everything else is an *optional* layer earning its keep
for a specific workload.

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
| **status** (submitted→open→in-progress→shipped/dropped) | open/closed **+ state-reason** (completed=shipped, not-planned=dropped; GitHub now also emits `duplicate` — decoder stays fail-open) **+ `status:` label** for submitted/in-progress | two axes must survive (DM2); compound transitions are multi-call → canonical write-order + self-healing reconciliation (CC1, §8.2, M5) |
| **stage** (idea→…→ready) | **`stage:` label** | load-bearing: `pick` routing enforces requirements-precede-code |
| area / effort / impact / source | **labels**; org **Issue Fields** where the owner is an org (**GA 2026-07-02**, org-only — an enhancement, currently dead for the all-personal portfolio) | soft per-project vocabularies (DM1); labels fit them; org Fields unavailable on personal accounts |
| **stable ID** (`owner/repo#number` canonical; `repo#number` short — **same-owner contexts only**) | GitHub's issue **number** is the ID going forward; migrated `PFX-XXXX` become permanent **alias labels** (`id:…`) + body-block entries so old refs resolve | **D4/O4 (§10)** — canonical form is GitHub's own cross-ref syntax; **immutable except on `gh issue transfer`, which renumbers → redirect via the same alias machinery** (M4); absorbs the portfolio's 27–58 hand-minted prefixes/project (DM4); no *new* PFX minted |
| relationships: blocks/blocked-by · parent/child · related | **native dependencies** (GA 8/2025) · **sub-issues** (GA 4/2025) · references | ready-work query needs blockers queryable (DM3) |
| comments | issue comments | threaded, attributed, timestamped (DM5) |
| **claim / assignee** | issue **assignee** (human or agent identity) | atomic-take + verify; residual race accepted (CC3) |
| verification stamp | marker comment or `verified:YYYY-MM-DD` encoding | "premise re-checked against code" is one call + queryable (TF2) |
| mutation history / audit | issue **timeline/events** (native) | replaces git's free audit log (CC4) |
| attachments | robust default: **release-asset wrap** *or* **dedicated attachments-branch** written via the git-data API (both deterministic, no PR) | GitHub has **no public attachment API** (verified 2026-03; the native `user-attachments` inline-upload endpoint is browser/session-cookie only — non-G1, an *attended-only* enhancement). Inline rendering **on private repos** is the open axis → **S5** (DM6/D9/O3) |

**Encoding validation is advisory and tolerant** (DM1): unknown values are *flagged*, never rejected
(a fail-closed validator here is a latent fail-close — learning on tolerating natural encoding
variants). **Two adversarial gaps this table surfaces** (now first-class parent requirements, §15): a
repo's *existing* Issues/labels may collide with prawduct's taxonomy (**GV6**), and a human editing in
the GitHub UI can introduce label/state drift the adapter must reconcile (**CC5**).

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
- **[P0]** Atomic mutations; a crashed client never half-writes (CC1). *Create is one atomic call; compound status transitions touch ≥2 GitHub primitives across two axes (§7) — so the adapter commits a **canonical write-order** + an **idempotent, self-healing reconciliation** (labels re-derived from open/closed + state-reason where derivable), and §16 Test Specs carry a partial-transition-recovery case (M5).*
- **[P1]** No lost updates — optimistic concurrency (compare-and-set on state/updated-at), clean-fail-for-retry (CC2).
- **[P1]** Claims consistent-enough — assignee atomic-take + verify; staleness visible; reaping is policy (CC3). *A **default claim-staleness TTL** (visible-age on the assignee timestamp) auto-unclaims/flags abandoned claims so the P0 `pick` can't silently starve as fleet agents die mid-work; human override stays the policy (M11).*
- **[P1]** Every mutation records actor identity, kept as per-item history (CC4).
- **[P1]** Verification first-class & cheap — record + query "premise re-checked" (TF2).
- **[P1]** Mass grooming is a supported workload (TF3).
- **[P1]** Human-UI drift reconciliation — tolerate + reconcile label/state changes a human makes directly in GitHub (**CC5**; distinct from GV3 item↔ship reconciliation — this is encoding↔direct-edit).

### 8.3 Query
- **[P1]** Changed-since cursor (Q2) — engine for incremental refresh + sweeps.
- **[P0-reachable]** **Structured** field/label filters, sort, paginate (Q1-structured) — the Issues REST **list** endpoint is read-your-writes consistent, so these run **online in the cacheless slice**; this is what carries the ready-work query behind `pick` (GV1). *(M8 — split from the search path below.)*
- **[P1]** **Full-text** filter (Q1-fulltext) — served from cache to avoid GitHub's search-index lag (not read-your-writes; §9, §13).
- **[P1]** Lexical similarity for dedup (Q3, lexical) — *cache-based, read-your-writes consistent.*
- **[P2]** Semantic similarity for dedup (Q3, semantic — GitHub hybrid search GA 4/2026).
- **[P2]** Cross-project queries + rollup (Q4). *O1 (federated multi-owner):* native Projects v2 rollup only spans **one owner**; **cross-owner** rollup is **query-side fan-out + merge** in our layer, not a GitHub-native feature.
- **[P1]** Counts/rollups derived on read (Q5).

### 8.4 Cross-project flow
*(Post-slice: these + anonymous filing ride the public/foreign identity plane (§8.5/O5) — not slice-1 content.)*
- **[P1]** File upstream directly — no upstream checkout, no drop-box, no git (XP1). *The **general** case (arbitrary cross-owner targets, private repos, foreign-identity auth-by-target-owner) is **W3**. The **fixed-target, public-repo subset** — filing a prawduct bug into prawduct's own public issues — ships **with the migration** as the drop-box's 1:1 replacement (§8.9/MG5), since it needs no new auth plane. Retiring the `incoming-bugs/` drop-box is gated on that replacement being live, not on full XP1.*
- **[P1]** Provenance + `submitted` triage landing (XP2).
- **[P2]** Anonymous filing on public projects (PV3) — **with abuse handling (PV4)**; enablement gated on the retro-governance path (`MET-6T4K`).
- *XP3 (private submit-without-read) is **out** — owner-descoped.*

### 8.5 Privacy, access & auth
- **[P0]** Per-project visibility inherits repo access — structural, free (PV1).
- **[P0]** Agents authenticate with real, scoped, revocable credentials — not a shared secret (PV2). *Portfolio identity model (O2/D8):* **GitHub App installed across owned orgs** (per-owner rate bucket, scoped, revocable, `[bot]` attribution) + a **user token** (`gh`/OAuth/PAT) for public/foreign repos the fleet isn't a member of. *P0-slice auth **resolved (O5, §11):*** the slice **inherits the session's `gh`/token identity** via **`gh` as the required portable transport** — local = the human's terminal identity; cloud = proxied user (`proxy-injected`); Actions = the Claude App bot — so "authed as the user" is strictly true only locally. Per-**agent** attribution rides in the payload (assignee/marker), since no transport carries agent-level actor identity, and the adapter validates identity early and attributes off the **API identity**, not git-push. *Token scope:* `repo` minimum (local probe 2026-07-16 confirmed); `project`/`read:project` needed for Projects-v2 rollup (Q4) — GV5 onboarding provisions/validates scopes. Governs rate-limit headroom, §9/§13.
- **[P2]** Public submission surface, per-project choice (PV3).

### 8.6 Automation enablement
- **[P1]** Batch operations — update/label/merge N items in few idempotent calls (AU2).
- **[P2]** Merge & split first-class (preserve bodies, leave redirect) (AU3).
- **[P2]** Events (webhooks) or cheap polling (AU1).

### 8.7 Governance integration
- **[P0]** `/prawduct:backlog` keeps its UX contract; stage-aware `pick` survives (GV1). *Its ready-work query is Q1-structured (open, blockers closed, unclaimed, `stage: ready`) — served **online, consistent** off the REST list endpoint, so `pick` needs no cache in the slice (M8).*
- **[P0]** Session briefing reads counts from cache/online, refreshed async — start never waits (GV2). *Even the cacheless slice keeps a **minimal persisted counts file** (a degenerate cache with visible age) so "start never waits" holds without a blocking round-trip; the detached refresh (D6) writes it (M3).*
- **[P0]** Zero-cost per-project provisioning via onboard/doctor — one command or none (GV5), **including the label taxonomy + coexistence with the repo's existing Issues (§13).**
- **[P1]** Traceability replaces atomicity — record `closed-by`; reconciliation sweep detects drift both directions (GV3). *(General retro-governance is out — §14.)*
- **[P0]** Adopter-reproducible backend shipped inside the plugin (GV4, G4).

### 8.8 Data model
- **[P0]** Structured, queryable metadata; soft per-project enums (DM1).
- **[P0]** Two axes: status + stage, not flattened (DM2).
- **[P0]** Stable, cross-project-unambiguous IDs; permanent redirects on merge; legacy-alias absorption (DM4). *Resolved (D4/O4, §10):* `owner/repo#number` canonical / `repo#number` short (**same-owner only** — ambiguous under O1 federation otherwise); migrated `PFX-XXXX` kept only as permanent aliases; no new PFX minted. *Immutability boundary (M4):* the canonical ID is immutable **except on `gh issue transfer`** (renumbers) → transfer leaves a redirect via the same alias machinery; store the node-id too (its stability across transfer is undocumented → prove in S2).
- **[P1]** Relationships queryable (DM3) · **[P1]** threaded comments (DM5) · **[P1]** nothing hard-deleted (DM7).
- **[P1]** Attachments (DM6) — **inline screenshots are a top use case** (owner, 2026-07-14), so not a P2 rough-edge. Robust default: release-asset wrap *or* attachments-branch via git-data API (both no-PR, G1-clean); native inline-upload is attended-only; inline-on-private gated by **S5** (D9). *(≥10 MB via the same wrap.)*

### 8.9 Migration & exit
- **[P0]** One-shot importer: IDs, metadata, bodies, sections preserved verbatim; existing IDs stay valid (MG1). **Highest-risk operation.** GitHub has **no ordinary issue-delete** (only a destructive admin action) **and never reuses numbers**, so "rollback" is a fiction — recovery is instead an **idempotent, resumable import keyed on the `id:PFX` alias label (skip-if-exists)** with a durable checkpoint; abandoning a bad run = close-as-not-planned + re-run into the same repo with dedup. S2 proves **resumability + idempotency**, not just body-fidelity (M6).
- **[P0]** **Pre-migration scrub (MG4)** — don't carry stale/obsolete/duplicate items into the new store (that would re-seed the #1 stale-content pain). Groom live items (close dead-premise/already-shipped, merge dupes); decide **archive scope** — keep the historical archive in the git-tracked source markdown rather than minting a closed issue per ancient item. *(Corrected 2026-07-20: this line previously named "the MG2 export file" as where a skipped archive lives. It cannot be — `export` dumps the **migrated repo**, so it runs after import and by construction never contains what `--archive-scope open` excluded. The preservation mechanism is the git-tracked source file, which is the migration runbook's step-0 backup. The tradeoff an operator is owed is stated with the lever, in `skills/backlog/migration-scrub.md`'s archive-scope decision step.)* The shipped lever is the binary `--archive-scope {all,open}` (MG4b); a quantified *recent-shipped window* between the two poles is the adopter-scale refinement tracked by BKL-6X5D, not built. This is a write-**volume** lever, **not** the rate ceiling — the Pacer holds the ~500/hr budget by pacing creates across time whatever the volume (§9). Crediting the archive scope as the rate-budget keeper is the mis-attribution BKL-6X5D was filed to correct; **dispose, never hard-delete** (DM7); model-assisted, **owner-confirmed** dispositions, then deterministic import (AG1/G1). **prawduct migrates first** (dogfood; smaller blast radius than discodon; stress-tests multi-prefix absorption — `BKL/ADR/ADV/MET/CRT…` in one repo) and runs the scrub for real; **adopters get an optional advisory pre-scan** (flag likely-stale via TF2 + likely-dup via Q3; skippable).
- **[P0]** **Issue-structure normalization (MG6)** — the scrub's model pre-pass also **restructures each item to the GitHub issue standard** (`documentation/backlog-service-issue-standard.md`): a ≤72 `area:`-prefixed title + a template-structured body + a `kind:` label, with the **original title/body preserved verbatim** (`original_*` block fields + the MG2 export). Owner reviews the restructured set **in aggregate** (sample + full before/after diff), **not** per-item — it must scale to hundreds. **No auto-split**: a non-atomic item is flagged for owner *manual* split (splitting deliberately mints IDs), so **1 PFX = 1 issue** (MG1/MIG-2) holds. Model in the pre-pass/decision, **never the data plane** (MIG-5). *This revises MG1: bodies are restructured to the standard, not byte-verbatim — the original is preserved instead; IDs/sections still preserved verbatim.* The **same standard** governs net-new `file` (serializer + WARN-only linter) and consumer UI filing (YAML Issue Forms). Owner-decided 2026-07-17.
- **[P0]** Full-fidelity export to files, scriptable, any time (MG2, G5). *Fidelity contract (M10):* the flat files must serialize the **native graph** too — dependencies, sub-issue trees, timeline/events (audit, CC4), assignee history — not just the body block; exit *reconstruction* into a fresh backend is non-trivial for that graph, so "cheap exit" means cheap *dump*, not lossless one-liner re-import. *Where each piece is pinned:* the **fidelity contract** is NFR §8 (+ M10); the **serialized fields** are Data Model §1.1 (timeline/history), §1.3 (relationships), §2 (body block); the concrete **on-disk file layout** is a build-time decision in the export chunk (build plan Chunk 05), bounded by the fidelity contract — *not* a queried lock-in schema, since re-import is explicitly out of scope (Data Model §8 open-Q5).
- **[P0]** Per-project adoption; file + service backlogs coexist across the portfolio, never within one project (MG3). *Migrating prawduct's backlog also removes `backlog.md` from the strip-`.prawduct`-from-main plan; prawduct then reads its own governance counts through the adapter — a dogfood risk the G2 never-block floor covers.*
- **[P0]** **Retire the `incoming-bugs/` drop-box in lockstep with a minimal same-repo replacement — never before it (MG5).** Migrating prawduct's backlog makes prawduct's own **public** GitHub repo the live upstream target, so the drop-box's file-drop channel is retired — but *only together with* its 1:1 replacement: `/prawduct:report-bug`, when a reachable channel exists, files a GitHub **issue** into prawduct's own repo (labeled `untriaged-upstream`) via the adapter's create path in place of writing a file, and the receiving-side `untriaged-upstream-reports` advisory counts labeled open issues instead of `incoming-bugs/*.md`. This is deliberately a **fixed-target, public-repo issue-create** — a subset of XP1 that needs no new auth (any authenticated user may open an issue on a public repo). The **full** XP1/XP2 surface — arbitrary cross-owner targets, private repos, foreign-identity auth-by-target-owner — **stays W3**; do not pull it forward. The existing no-channel fallback (report-bug's local capture + point at the canonical issue tracker) is unchanged.

## 9. Non-functional targets (concretized)
- **Cost (NF1):** **$0/month.** GitHub Issues, labels, org Fields free; no server. No per-project cost.
- **Ops (NF2):** near-zero — GitHub hosts the store; the only optional local part is a cache file.
- **Rate limits (NF3):** GitHub gives ~5k/hr core, tightest **80 content-creations/min *and* ~500/hr** (a *secondary* limit — verified 2026-07-16; the migration write-burst must pace across **time**, not just per-minute) and a separate **search-endpoint limit** (~30/min general search, ~10/min code-search; the semantic/hybrid figure is now **verified — 10/min, GA 2026-04-02, independent of the code-search cap** (NFR §9); v3's earlier "conflated with code-search" suspicion was wrong). The *warm-cache* read path never touches GitHub; the budget is spent on **writes + sync**. *Identity model resolved (O2/D8):* a **GitHub App installation gets its own bucket per owner** — **5,000/hr baseline, +50/hr per repo and per user beyond 20, cap 12,500** (verified) — so each owned org's heavy traffic (sweeps, grooming, migration) is isolated in its own bucket rather than concentrated in the human's personal quota — **but (i) the ~500 content-creations/hr *secondary* cap still binds inside any bucket** (the **Pacer** is what holds that ceiling — it paces creates across the clock whatever the volume, NFR §3; the §8.9 scrub reduces write *volume*, which shortens the run but is not what keeps it compliant), and **(ii) the P0 slice runs on the *user token* (O5), so until the App is adopted this isolation doesn't apply and writes land on the personal bucket** — tolerable for a personal portfolio at ~200 writes/day, though the migration burst is the stress point. Public/foreign filing runs on a user token but is **low-volume**, so concentration there is moot. S3 measures a real cold sweep + write-heavy grooming under this model. **Also:** GitHub's search index is not read-your-writes consistent — Q1/Q3 that must see just-written items run against the cache, not GitHub search.

## 10. Key design decisions
- **D1 — GitHub Issues as system of record; Projects v2 only for cross-repo rollup.** (Parent doc's Build/Adopt/Buy.)
- **D2 — GitHub client (`gh` vs HTTP): reopened, then narrowed toward HTTP by D8 (§11-S1).** Latency is *not* the pivot; dependency footprint, auth/identity, and cache revalidation are — and App-token auth (D8) is what tips it to HTTP, with `gh` surviving only as a bootstrap.
- **D3 — Labels are the baseline encoding; org Issue Fields an enhancement.** Portfolio spans personal accounts (no Fields); labels fit soft vocabularies. **O1 clarified (2026-07-14):** the model is **federated multi-owner** — one human sign-in's *existing* access across many owners is leveraged; the goal is *not* org consolidation and *not* per-repo credential sprawl. Org consolidation stays an optional enhancement (it unlocks typed Fields + native single-owner rollup); cross-owner rollup is query-side (§8.3-Q4). **Adds a label-taxonomy governance need (§13).**
- **D4 — Ongoing ID strategy: RESOLVED (O4, 2026-07-14) → repo-prefixed GitHub numbers.** GitHub's issue number is the ID going forward. **Canonical form `owner/repo#number`** — deliberately GitHub's own cross-reference syntax, so an ID *is* a live auto-link, is globally unique, and disambiguates same-named repos across unrelated owners (O1). **Short form `repo#number`** when project config makes the owner unambiguous (like short vs full git SHAs — one authority, context-scoped abbreviation, *not* two ID systems). CLI accepts the spellings Data Model §5 enumerates (the grammar's home — it has grown since this decision was recorded) and normalizes each to the canonical form. Migrated **`PFX-XXXX` become permanent alias labels + body-block entries** (old refs resolve forever); **no new PFX minted** — this collapses two minting authorities into one, resolving adversarial finding §13-3. *Two named costs:* (a) no pre-GitHub ID → offline creates use a provisional local ID reconciled on flush (§8.1); (b) cross-repo `gh issue transfer` reassigns the number → also store the issue node-id (stable) or re-resolve.
- **D5 — Cache is optional, read-through, gitignored, git-common-dir keyed, revalidate-on-decision.** The core is correct without it (online-only). Reverses v1's mandatory-mirror stance per owner feedback + §13.
- **D6 — Sync is synchronous; background refresh is a detached subprocess** (no-asyncio convention); staleness re-evaluated against the cursor.
- **D7 — GitHub-native throughout, with a clean internal seam + export as the exit** — no premature multi-backend abstraction. *(State the requirement breadth explicitly — "a GitHub-hosted repo" — rather than letting today's client shape it, per the "one instance colonizes the requirement" learning.)*
- **D8 — Identity model: GitHub App across owned orgs + user token for the public/foreign plane (O2, 2026-07-14).** Derived from which goals each mechanism *can't* meet: the public/foreign plane (upstream/anonymous filing on repos the fleet isn't a member of) **structurally requires a user token** — you can't install an App you don't own — so a user credential can never be retired. A **fine-grained PAT can't be the "spans my orgs" credential** (single resource-owner, verified). So the scoped, safe realization of "leverage one sign-in across my orgs" is a **GitHub App installed per owned org** (per-owner rate bucket, scoped, revocable, `[bot]` attribution); `gh`/user creds are a legitimate low-ceremony *bootstrap* that upgrades to the App when rate/attribution bite. Implies a **credential-resolution layer keyed by target owner**. **Couples to S1:** App auth (JWT→installation token) fits HTTP, not `gh` — this nudges S1 toward HTTP for auth-bearing calls. **Resolved by O5 (2026-07-16):** the App is *optional* (not in the P0 slice), and cloud Claude Code sessions proxy the token as `proxy-injected` (breaking raw-HTTP-from-env) — so the slice **inherits the session's auth with `gh` as the required portable transport**; raw HTTP is an optional fast-path. See O5 / §11-S1.
- **D9 — Attachments: release-asset (or attachments-branch) is the deterministic default; native inline is attended-only (O3, 2026-07-14).** The only mechanism that renders screenshots natively-inline *and* respects private-repo access is the `user-attachments` flow — and it's **browser/session-cookie auth, undocumented** (verified; `gh-image`/`gh-attach` both fall back to release-mode for CI), so it can't be the G1 data plane; it's an opt-in *attended* "pretty images" mode at most. Robust, API-only, PR-free options: **release-asset wrap** (release clutter, containable under a reserved tag) and **attachments-branch via git-data API** (off-main → untouched by the strip-`.prawduct`-from-main plan; no working tree, no PR). The tiebreaker — **does either render *inline* on a *private* repo?** — is **S5**. Leaning release-asset pending S5. Rejected: storing images under `.prawduct/issues/` on `main` (stripped from releases *and* forces commit+PR).

## 11. Open decisions & spikes to settle

**Spikes & pre-build questions — tiered by what they gate.** A spike earns "settle before build" only if its answer changes the design of the *next* increment (§16: core lib → CLI → one GitHub round-trip → importer dry-run). By that test only two spikes gate the core (**S1, S2**); the owner decision **O5** (P0-slice auth/transport) is now **resolved** (owner-decisions block below), which narrows S1. The rest gate a later optional layer or a feature, or are runtime tuning that rides along with the build. (S-labels are stable — they're referenced in §8/§9/§12/§13 — only the grouping changed.)

**Tier 1 — gates the thin slice (settle or prove first):**
- **S1 — `gh` CLI vs direct HTTP — NARROWED by O5 (core transport decided; residual is optimization + fact-confirmation).** O5 settles the core: **`gh` is the required portable transport** (the only thing that survives local + the cloud proxy that injects `proxy-injected`), with raw HTTP an optional fast-path where a real token is in hand (ETag/conditional-GET, tracks API drift). Residual, none of it gating the core transport: **(a)** *does the cloud proxy intercept arbitrary HTTPS to `api.github.com`, or only `gh`?* — decides whether the raw-HTTP fast-path is available in cloud (an **optimization**; must be run in a *cloud* session, not observable locally); **(b)** confirm **ETag/conditional-GET** for cheap revalidation; **(c)** confirm the **issue-number-non-reuse** fact M6 leans on (deletion is admin-only and destructive, not an ordinary op — so the load-bearing fact is non-reuse, not "no delete"). Local probe (2026-07-16) confirmed the local half: `gh` present, real token from `hosts.yml`, no env override; and a live drift instance — `gh`'s "git protocol: ssh" vs an HTTPS `origin`, so push credential ≠ `gh` token (adapter attributes off the API identity, not git-push). *(Latency is a footnote.)*
- **S2 — Migration dry-run** on discodon (317 open + 1,754-line archive): body-fidelity, ID aliasing, relationship reconstruction, archive-as-closed-issues volume/noise, rollback. Migration is the riskiest single op — and **this is not throwaway spike code; it *is* the thin slice's proving increment** (§16 already lists "importer dry-run"). Doing it first de-risks the foundational adopt-GitHub bet (MG1: existing IDs stay valid) at the earliest point.

**Tier 2 — gates a later optional layer or feature (settle when you build it, not before the core):**
- **S3 — Rate limits under the App-installation model** (O2/D8) — **mostly runtime tuning, with one load-bearing constant.** Most of its answer is *numbers* that set pacing constants (batch size, backoff). **But the corrected write budget — 80/min *and* ~500 content-creations/hr (fact #3), ~10× tighter than v3's "≈4,800/hr" and *not* relieved by the App's per-owner bucket (it's a secondary limit) — makes migration write-pacing genuinely gating for S2**, not a later optimization: the discodon import (317 open + a 1,754-line archive) can exceed 500 creates/hr and must pace across time — which the Pacer does (§9/NFR §3); the §8.9 scrub trims the archive to reduce *volume*, shortening the run rather than holding the ceiling. Measure a cold sweep + write-heavy grooming during the build and tune the rest.
- **S4 — Cache freshness protocol** — **travels with the optional cache; does not gate the slice.** The **principle** (visible age + revalidate-on-decision, G3) is locked now; the **protocol** is settled only when perf data justifies building the optional cache (D5). Online-only, every read is live, so revalidation is trivially satisfied. When built: how a read "revalidates on decision" cheaply (conditional request / per-item since) without defeating the cache.
- **S5 — Attachment inline rendering on private repos** (gates the O3 default, D9) — a real spike, but it gates the **attachments feature**, not the architecture. Cheap experiment: on one private repo, embed (a) a release-asset download URL and (b) an attachments-branch raw URL via `![]()` and observe which renders inline for an authenticated viewer. Decides release-asset vs attachments-branch; if *neither* renders inline on private, inline-on-private is achievable only via the attended native flow. Settle when attachments are built.

**Owner decisions — all resolved 2026-07-14:**
- **O1 — Org model → RESOLVED: federated multi-owner (D3).** Not consolidation, not per-repo credentials — leverage one sign-in's existing multi-owner access; cross-owner rollup is query-side (§8.3-Q4).
- **O2 — Agent identity → RESOLVED: GitHub App across owned orgs + user token for public/foreign (D8).** Not "PAT vs App as a start" — a fine-grained PAT can't span orgs, and the public/foreign plane forces a user token regardless; the App is the scoped realization of "one identity across my orgs."
- **O3 — Attachment strategy → RESOLVED: release-asset (or attachments-branch), native-inline attended-only; reprioritized up (D9).** Gated by S5. `.prawduct/issues/`-on-main rejected.
- **O4 — Ongoing ID strategy → RESOLVED: repo-prefixed GitHub numbers, `owner/repo#number` canonical, PFX → migration alias (D4).**
- **O5 — P0-slice auth & transport → RESOLVED (owner, 2026-07-16; raised by the review as B2, sharpened by a Claude-Code-auth check + local probe).** D8 resolved the *portfolio* identity model, but not *what the buildable slice authenticates as, or over which transport.* Findings behind the call: **(i)** locally the adapter inherits the session's `gh`/token identity — same as the human's terminal, no separate Claude-Code identity (probe-confirmed); **(ii)** a registered App has a private key + a "whose App does an adopter use?" problem that strains GV4/GV5; **(iii)** *cloud* Claude Code sessions don't mount `~/.config/gh` — they proxy the token as the placeholder `proxy-injected`, so **raw HTTP reading the env token breaks in cloud** while `gh` keeps working; **(iv)** in GitHub *Actions* the actor is the **Claude App bot**, not the user; **(v)** `git push` identity can differ from `gh` identity (confirmed live in the probe — `gh` protocol ssh vs an HTTPS remote). **Decision:** the adapter **inherits the session's GitHub auth** (never manages its own credential); **`gh` is the required, portable *default* transport** — the one thing that survives local + cloud-proxy — with raw HTTP an *optional fast-path* where a real token is in hand (this narrows S1). `gh` **is an accepted required client dependency** for the slice: G4 is met because `gh` is free, standard, `brew`/`apt`-installable, and most adopters already have it — not a backend bespoke to one machine. The App stays an **optional per-owner rate/attribution upgrade**, never required to adopt. Per-agent/actor attribution rides in the payload (CC4) regardless; the adapter validates identity early (`gh api user` vs `git config user.email`) and attributes off the **API identity**, not git-push. *Owner-confirmed; revisit only if the `gh`-as-hard-dependency trade bites a real adopter.*

## 12. Risks & mitigations
| Risk | Mitigation |
|---|---|
| **Cache re-creates the staleness we exist to kill** | cache optional + read-through + **visible age + revalidate-on-decision**; never silently serves stale (G3/D5) |
| **Slice mistaken for solving the #1 (content-trust) pain** | §1/§4/§6 state it honestly: the online slice kills stale **views** (#2) + conflicts (#3) + gives online `pick`; stale **content** needs TF2/TF3 (P1) + the one-time scrub (B1/M7) |
| **Cloud/Actions identity ≠ local `gh`** | adapter inherits the session's auth, never manages its own; `gh` is the portable transport across local + cloud-proxy; records the *actual* actor + validates identity early (O5) |
| GitHub **search index lag** (not read-your-writes) | dedup/query that must see just-written items runs against the cache, not GitHub search (§9) |
| **Rate-limit concentration** across the fleet | **GitHub App installation gives a per-owner bucket** (5k–12.5k/hr, D8) isolating each owned org's traffic — **but only once adopted (O5); the P0 slice's user token lands on the personal bucket**, and the **~500 content-creations/hr *secondary* cap binds inside every bucket** (fact #3) → migration/grooming pace across time + the scrub trims write volume (§8.9); public/foreign filing is low-volume; warm reads from cache (NF3) |
| GitHub rate limits under mass grooming | warm-cache reads bypass GitHub; writes/semantic paced; batch idempotent |
| No public attachment API (native inline is browser/session-only) | robust default = release-asset wrap *or* attachments-branch via git-data API (both no-PR, G1); native inline as an attended-only enhancement; **S5** settles inline-on-private (D9) |
| Claim double-pick race | assignee take-and-verify; documented residual race, not a mutex (CC3) |
| GitHub outage | never-block floor (fail-fast+retry); optional queue + cache degrade gracefully (G2) |
| Vendor lock-in | cheap full-fidelity export (G5/MG2) |
| **Migration drops an already-shipped part / breaks a guard** | import against the **spec roster** not the open-work list; canonical checkout only; **idempotent resumable import keyed on the `id:` alias (no "rollback" on GitHub, M6)**; **pre-migration scrub disposes stale/dupes so they never enter the store (MG4)**; wire backfill **and** legend-refresh; sweep guards **with tests** (learnings) |
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

### 13a. Independent review (fresh-eyes design critic + GitHub-fact verifier, 2026-07-16) — folded into v4
| # | Sev | Finding | Disposition in v4 |
|---|---|---|---|
| B1 | high | §6 mislabeled one-live-view as "the #1 win (trust)"; parent ranks stale *content* #1, stale *views* #2 | **Folded** — §1/§4/§6 reworded to the slice's true scope; #1 pain → TF2/TF3 + scrub |
| B2 | high | P0-slice auth undecided; App collides with GV4/GV5; cloud proxy + Actions-App complicate it | **Resolved O5** (owner): `gh` required as portable transport, inherit session auth, App optional; S1 narrowed |
| M3 | major | GV2 "start never waits" needs persistence the no-cache slice lacks | **Folded** — minimal persisted counts file in the P0 floor |
| M4 | major | number-as-ID mutates on transfer (vs DM4 "never change"); short form ambiguous under O1 | **Folded** — immutability-except-transfer + redirect; short form same-owner-only |
| M5 | major | CC1 "no half-write" unattainable for two-axis status (multi-call transitions) | **Folded** — canonical write-order + self-healing reconciliation; §16 recovery test |
| M6 | major | MG1 "rollback" impossible (delete is admin-only/destructive, numbers never reused) | **Folded** — idempotent resumable import keyed on `id:` alias; S2 proves it |
| M7 | major | §9/§4 rate-safety for 48-agent grooming silently assumes the P1 cache | **Folded** — §4/§9 caveat: grooming-cheaper is cache-gated |
| M8 | major | GV1 `pick` (P0) filed under Q1 (P1/cache); structured vs search consistency conflated | **Folded (a win)** — Q1 split; ready-work runs online-consistent, rescues `pick` in the slice |
| M9 | major | §15 forward traceability false — 3 §8 capabilities have no parent ID | **Folded** — CC5/PV4/GV6 written back to parent; §15 re-run |
| M10 | major | G5 "cheap full-fidelity exit" vs D7 native-graph use | **Folded** — export fidelity contract stated (G5/§8.9) |
| M11 | major | CC3 reaping undefined → P0 `pick` can starve in a fleet | **Folded** — default claim-staleness TTL |
| fact-3 | major | write budget is 80/min **and ~500/hr**, not "≈4,800/hr" (~10× tighter) | **Folded** — NF3/S3/§12 corrected; sizes migration + scrub |
| facts 10/12/13 | minor | `state_reason: duplicate`; node-id-transfer undocumented; Issue Fields now GA | **Folded** — §7 notes; prove node-id in S2 |

*Independent review folded (2026-07-16, Principle 14):* a fresh-eyes design critic + a GitHub-fact verifier reviewed v3; confirmed findings are folded above and inline. Backward traceability re-checked (every parent ID → §8); the three v3 forward gaps are closed by writing CC5/PV4/GV6 back to the parent, plus MG4 for the scrub (§15). A further independent pass is available before the build plan if desired.

## 14. Explicitly out of scope
- **Retro-governance / onboarding out-of-compliance PRs / existing-repo onboarding** — its own future spec; parked in `MET-6T4K`. GV3 does the minimal reconciliation sweep; the general capability is separate.
- **Autonomous assign-to-agent *execution*** (issue→PR autopilot) — parked in `MET-6T4K`. (Assignee-as-*claim* is in scope, CC3.)
- **The triage intelligence itself** — AU1–AU3 enable it; the workers are separate work.
- **PM-suite ceremonies** — sprints, velocity, time tracking, roadmapping, real-time presence.
- **Moving change-log / learnings / build plans** out of git.

## 15. Traceability
Every §8 capability cites its parent requirement ID; every requirement ID in
`backlog-service-requirements.md` appears in §8. **Re-run 2026-07-16:** backward direction (parent → §8)
holds for DM1–7, AG1–6, CC1–5, TF1–3, Q1–5, XP1–3, PV1–4, AU1–3, GV1–6, MG1–4, NF1–3. The three v3
forward gaps (human-UI-drift, submission-abuse, label-taxonomy — capabilities that traced only to §13)
are closed by adding **CC5, PV4, GV6** to the parent; the owner-directed scrub adds **MG4**. §8 now
cites these (CC5→§8.2, PV4→§8.4, GV6→§8.7, MG4→§8.9).

## 16. What "drilling down" produces next (only after confidence in this level)
1. **Data Model** — field-level GitHub encoding + optional-cache schema (fields derived from §7a). → **drafted (2026-07-16):** `documentation/backlog-service-data-model.md`.
2. **Non-Functional Requirements** — latency/rate-limit/cost budgets made testable. → **drafted (2026-07-16):** `documentation/backlog-service-nfr.md` (per-operation rate-budget model built on the M5 content-vs-core split; every target paired with a measurement + S2/S3/build-probe owner; floor-vs-accelerated throughout).
3. **Security Model** — auth per D8 **+ the O5 slice-auth/transport decision** (inherit session auth; `gh` portable transport; App as optional upgrade; credential-resolution keyed by target owner), token scope/revocation, provenance trust, **public-submission abuse (PV4)**. → **drafted (2026-07-16):** `documentation/backlog-service-security-model.md`.
4. **API contract** — CLI/MCP surface: operations, return-value error model, versioning/compat. → **drafted (2026-07-16):** `documentation/backlog-service-api-contract.md` (records `api_error_model_approach` + `api_versioning_approach`).
5. **Test Specifications** — incl. migration guard-sweep + offline/never-block behaviors. → **drafted (2026-07-16):** `documentation/backlog-service-test-specifications.md` (five test layers — deterministic L1 / verify-api shape-contract L2 / build-measurement L3 / one-time spike L4 / live-smoke+behavioral L5; the transport-seam-fake isolation decision; a coverage matrix over every catalogued obligation; records `test_isolation_approach`).
6. **Build plan** — thin vertical slice first (core lib → CLI → one GitHub round-trip → **prawduct-first scrub + importer dry-run**, §8.9/MG4), architecture proven before widening. → **drafted + promoted (2026-07-16):** `.prawduct/artifacts/archive/build-plan-backlog-service.md` (v2 — draft v1 → two-reviewer fold → v2 + 3-debt coherence sweep; 6-chunk thin slice + W1–Wg roadmap; `active_build_plan` set, gate armed; pending owner sign-off before Chunk 01).

Two §11 spikes gate the core — **S1** (now narrowed by O5: confirm ETag + the M6 number-non-reuse fact + the cloud-proxy *optimization* test — the core transport, required-`gh`, is decided) and **S2** (the migration dry-run — the slice's first increment, run **prawduct-first** and after the scrub). **O5** (P0-slice auth/transport) is **resolved** (`gh` required, inherit session auth, App optional). **S3** carries one load-bearing constant (the ~500/hr write cap that paces migration); **S4/S5** settle with their layer/feature. Until this level is agreed, no build plan and no field-level schema.
