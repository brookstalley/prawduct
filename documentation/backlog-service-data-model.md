# Backlog Service — Data Model

`status: draft v1 — drilled down from backlog-service-prd.md §7/§7a/§16 (2026-07-16) · source: planning session · stage: design`

**Parent:** `documentation/backlog-service-prd.md` (PRD v4) and, through it,
`documentation/backlog-service-requirements.md` (DM1–7, Q1–5). This doc fixes the **field-level
GitHub encoding** the PRD deliberately left to "the next level," plus the **optional-cache schema**.

**Design rule (the lock-in learning).** A persisted schema's requirements are *its consumers' future
queries*, not GitHub's mechanism. Every field below cites the query (Q1–Q5, ready-work,
stale-verification, provenance) or the requirement (DM/CC/TF/XP) that justifies it. A field no
consumer queries is not added (the retired-`git_sha` precedent — a dead-read field becomes a misread
field). **Encoding validation is advisory and tolerant** (DM1): a natural variant of the same meaning
(`[]` vs absent, `null` vs unset) normalizes, never hard-fails; the hard fail is reserved for genuine
ambiguity (unknown *status*, malformed ID).

**Altitude & foreign-API note.** This is *design intent* — which GitHub primitive encodes which
concept, and the round-trip block's shape — not the exact REST/GraphQL JSON field names. Those are a
`verify-api` step at build time (planning "Foreign API Verification"): read the live payloads before
writing handlers; the shapes below are the contract the probe confirms, not an assumption to build on.

---

## 1. Entities

The system of record is **GitHub Issues**; entities are *projections* onto GitHub primitives. The
optional cache (§6) is a projection of the same fields for the queries GitHub can't serve
read-your-writes (Q1-fulltext, Q3).

### 1.1 Item (the central entity — one GitHub issue)

| Field | Type / values | GitHub encoding | Justified by |
|---|---|---|---|
| `id` | `owner/repo#number` (canonical); `repo#number` (short, same-owner only) | issue **number** (immutable except on transfer, §5) | DM4 · every ref |
| `node_id` | opaque string | issue **node-id** | DM4 (transfer-stable fallback — *verify in S2*) |
| `title` | string | issue **title** | AG2, Q1 |
| `body` | markdown + one fenced `prawduct:` block (§2) | issue **body** | AG2, DM1 round-trip |
| `status` | `submitted \| open \| in-progress \| shipped \| dropped` | open/closed **+ `state_reason` + `status:` label** (§4) | DM2, ready-work |
| `stage` | `idea \| research \| requirements \| design \| ready` (soft) | **`stage:` label** | DM2, ready-work, GV1 `pick` |
| `area` `effort` `impact` `source` `kind` | soft per-project enums | **labels** (`area:`, `effort:`, …); org **Issue Fields** where owner is an org (GA, org-only) | DM1, Q1 |
| `added` `reviewed` | date | timeline/events; `reviewed` mirrored to `prawduct:` block for Q-speed | DM1, TF2 (stale-verification) |
| `assignee` / claim | GitHub user or agent identity | issue **assignee** + `claimed-at` in block | CC3, ready-work |
| `verification` | `{by, on}` list | marker comment **or** `verified:YYYY-MM-DD` label + block | TF2 (stale-verification query) |
| `relationships` | see §1.3 | native dependencies / sub-issues / refs | DM3, ready-work |
| `provenance` | see §1.5 | `prawduct:` block + `source:<product>` label | XP2 |
| `history` | append-only | issue **timeline/events** (native) | CC4 (replaces git's audit log) |

*Soft enums (DM1):* a `stage:`/`kind:` value the project hasn't declared is **flagged, not rejected**
(scriob's `kind:` on 158 items is the precedent). Validation writes an advisory, never blocks the write.

### 1.2 Comment
Threaded, attributed, timestamped → **native issue comments** (DM5). No projection needed; the cache
mirrors comment text only for Q1-fulltext / Q3 similarity.

### 1.3 Relationship
| Kind | GitHub encoding | Query need |
|---|---|---|
| `blocks` / `blocked-by` | **native issue dependencies** (GA 8/2025, ≤50/type) | ready-work ("blockers all closed") — *must be queryable*, DM3 |
| parent / child | **native sub-issues** (GA 4/2025, ≤8 levels) | split (AU3), rollup |
| `related` · `superseded-by` | issue **references** / `superseded-by:` in block + redirect label | DM3, merge redirect (AU3/DM7) |

### 1.4 Claim (not a separate row — Item facet)
`assignee` = atomic take; `claimed-at` timestamp in the block gives **visible staleness**; a **default
claim-staleness TTL** (§4) drives auto-unclaim/flag so `pick` can't starve (CC3, M11). Residual
double-take race is accepted (CC3) — take-and-verify, not a mutex.

### 1.5 Provenance (upstream submissions — Item facet)
`{source_product, source_version, session_ref, submitted_at}` in the `prawduct:` block + a
`source:<product>` label for Q4/XP2 filtering. **Provenance is untrusted until triaged** (a submitter
sets its own claimed source) — lands in `status: submitted` (see Security Model §5).

### 1.6 Attachment
No public GitHub attachment API (verified). Encoding: **release-asset wrap** (default) *or*
**attachments-branch via git-data API** — both no-PR, deterministic (G1). Item block stores
`attachments: [{name, url, kind}]`. Native inline-upload is attended-only; inline-on-private gated by
S5 (D9/DM6).

---

## 2. The `prawduct:` body block (exact round-trip of non-native fields)

Native features encode what they fit; a **single fenced block** at the end of the issue body carries
what GitHub has no native slot for, so export/round-trip is lossless (MG2). Tolerant parse: unknown
keys are preserved verbatim (forward-compat), missing keys default.

````
```prawduct
v: 1                         # block schema version (§7 — never deferred silently)
id_aliases: [BKL-7M4Q]       # migrated PFX; old refs resolve forever (DM4)
stage: ready                 # mirrored from label for one-read parse
reviewed: 2026-07-16         # TF2 stale-verification without a timeline scan
claimed_at: 2026-07-16T…Z    # CC3 visible staleness
verified: [{by: …, on: …}]   # TF2
provenance: {source: scriob, version: …, session: …}   # XP2
superseded_by: owner/repo#123                            # merge redirect (DM7/AU3)
attachments: [{name, url, kind}]                         # DM6
```
````

The block is the **authority for non-native fields**; labels/native features are the authority for
what they encode. On conflict (a human edits a label directly, CC5), reconciliation prefers the
native/label value and re-stamps the block (labels are cheap to re-derive; §4).

---

## 3. Label taxonomy (namespaced — GV6 coexistence)

All prawduct labels are **namespaced with a `<facet>:` prefix** so they never collide with a repo's
existing labels (GV6): `stage:`, `status:`, `kind:`, `area:`, `effort:`, `impact:`, `source:`,
`id:`, `verified:`. Provisioned + reconciled by `/prawduct:onboard`/`doctor` (GV5). **Non-prawduct
issues/labels are out-of-scope, not malformed** — the adapter ignores issues lacking any `stage:`/`id:`
marker rather than treating them as broken backlog items.

---

## 4. State machines

**Two orthogonal axes (DM2) — never flattened.**

**status** = `open/closed` × `state_reason` × `status:` label:
- `submitted` → open + `status:submitted` (triage landing, XP2)
- `open` → open, no `status:` label
- `in-progress` → open + `status:in-progress` (+ assignee)
- `shipped` → **closed + `state_reason: completed`**
- `dropped` → **closed + `state_reason: not_planned`**
- (`state_reason: duplicate` from a human "close as duplicate" is decoded as `dropped` + `superseded_by`; decoder stays **fail-open** on unknown reasons)

**stage** = `stage:` label only: `idea → research → requirements → design → ready`. Load-bearing:
`pick` only routes `stage: ready` items to code (else to discovery) — DM2/GV1.

**Compound-transition integrity (CC1/M5).** `in-progress → shipped` = *two* non-atomic calls (PATCH
state=closed/completed; remove `status:in-progress`). GitHub has no multi-attribute transaction, so:
1. **Canonical write order:** mutate the **open/closed + state_reason** axis *first* (the authority),
   then reconcile the `status:` label.
2. **Self-healing reconciliation:** the `status:` label is *derived* from open/closed+state_reason
   wherever derivable, so a crash between calls leaves a stale label that the next read re-derives —
   no contradictory item survives. (Open question §8: whether `status:` is needed at all for
   shipped/dropped, since state_reason already carries them — likely only `submitted`/`in-progress`
   need a label.)

Ready-work query (the `pick` engine): `state=open AND stage:ready AND no open blockers AND unassigned
(or claim past TTL)` — all **structured**, served **online read-your-writes** off the REST list
endpoint (Q1-structured, M8), no cache required.

---

## 5. Identifiers

- **Canonical `owner/repo#number`** — GitHub's own cross-ref syntax (auto-links, globally unique,
  disambiguates same-named repos across owners, O1). **Short `repo#number` only in same-owner
  contexts** (ambiguous under federation otherwise).
- **Immutable except on `gh issue transfer`**, which renumbers → transfer writes a **redirect** via
  the same `id:` alias machinery + a `superseded_by`-style forward. Store `node_id` as the
  transfer-stable fallback (*undocumented across transfer → prove in S2, don't assume*).
- **Migrated `PFX-XXXX` → permanent `id:PFX-XXXX` alias labels** + `id_aliases` block entries; old
  refs resolve forever. **No new PFX minted.** Absorbs the portfolio's 27–58 hand-minted prefixes per
  project (DM4) — prawduct's own `BKL/ADR/ADV/MET/CRT…` is the multi-prefix stress case (§8.9/S2).

---

## 6. Optional cache schema (projection — off by default)

The cache is **derived personal state, never the truth** (D5); it exists only where GitHub can't serve
a query read-your-writes or offline. SQLite, per-clone, **gitignored**, `git-common-dir`-keyed (shared
across a clone's worktrees, like the evidence store). **Every table/index is a Q-projection** — no
field the queries don't need:

| Table / index | Serves | Notes |
|---|---|---|
| `item(id, node_id, title, body, status, stage, area, effort, impact, source, assignee, added, reviewed, updated_at, **fetched_at**)` | Q1-structured, ready-work, Q5 counts | `fetched_at` = **visible age** (G3); a decision-driving read revalidates |
| `item_fts(title, body)` (FTS5) | Q1-fulltext, Q3 lexical | the read-your-writes path GitHub search lacks (§9) |
| `comment(item_id, body, author, created_at)` | Q1-fulltext, Q3 | text mirror only |
| `relationship(src, kind, dst)` | ready-work (blockers), Q4 rollup | mirrors native deps/sub-issues |
| `cursor(scope, since)` | Q2 incremental refresh | the primitive for cheap sweeps + prefetch |

Counts/rollups are **derived on read** (Q5), never persisted (the D14 discipline; dead-persisted
counts are the retired-`git_sha` failure mode). The cache **never silently serves stale** (G3): age is
visible and a decision-read revalidates via conditional request.

---

## 7. Schema versioning (never deferred on a one-word note)

The scriob precedent (697 commits unversioned → coordinated breaking retrofit) makes this explicit,
not silent:
- **`prawduct:` block** carries `v:` (currently `1`); readers tolerate higher/unknown keys (forward-
  compat) and a `migrate` **legend-refresh** reconciles the block's known-key set additively.
- **Cache** carries `schema_version`; a mismatch triggers a rebuild-from-GitHub (cache is derived, so
  a rebuild is always safe — never a data-loss migration).
- **Adding an optional field reaches onboarded repos only via a migrate/triage refresh** (the
  templates-are-scaffold-only learning): wire both the per-item backfill and the legend refresh.

---

## 8. Constraints, invariants & open questions

**Invariants:** nothing hard-deleted by normal operation (DM7 — merge/split/drop preserve bodies +
leave redirects); tolerant validation (DM1 — flag, don't reject); two axes never flattened (DM2);
cache is subordinate + age-visible (G3/D5).

**Open questions (for the build / verify-api, not blockers to this altitude):**
1. Does `status:` need a label for `shipped`/`dropped`, or does `state_reason` alone suffice? (Fewer
   labels = fewer compound-transition calls = cheaper under the ~500/hr write cap.) — decide at build.
2. Exact REST/GraphQL JSON shapes for dependencies, sub-issues, `state_reason`, timeline events —
   **`verify-api` probe before writing handlers** (do not draft from docs).
3. `node_id` stability across `gh issue transfer` — **prove in S2**.
4. Attachment default (release-asset vs attachments-branch) — **S5** settles inline-on-private.

## 9. Traceability
Every DM1–7 and Q1–Q5 is represented: DM1→§1.1/§3; DM2→§4; DM3→§1.3; DM4→§5; DM5→§1.2; DM6→§1.6;
DM7→§8. Q1-structured→§4 ready-work + §6; Q1-fulltext/Q3→§6 (`item_fts`); Q2→§6 (`cursor`); Q4→§6
(`relationship`) + `source:` labels; Q5→§6 (derived-on-read). ready-work→§4; stale-verification (TF2)→
§1.1 `verification` + block `reviewed`; provenance (XP2)→§1.5.
