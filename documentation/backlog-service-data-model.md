# Backlog Service — Data Model

`status: draft v3 — build-plan coherence sweep (2026-07-16, from the §16(6) Build-plan drill-down review): §8 open-Q5 added — the export on-disk file layout is deferred to the export build chunk (bounded by the NFR §8 fidelity contract), resolving PRD §8.9/MG2's over-promise that this doc "pins the on-disk representation." Prior v3 — coherence touch-up (2026-07-16, §5): field-home added for two operation-idempotency markers (`split-op:` and `source-key:`), the field homes for the split / file-upstream keys the Test-Specs review made the API contract pin (§2.3/§2.4). Prior v3 — GV3 coherence (2026-07-16): added a closed_by field to Item §1.1 — GV3's ship-traceability handle had no field home, surfaced by the API-contract independent review; native close-ref authoritative on close-on-merge, the block field the manual-close fallback, and the bidirectional drift sweep is a janitor list+timeline scan (API contract §2.6). Prior v2 — independent-review fold (2026-07-16): B1 fixed (open-state transitions are now crash-safe via an idempotent set-status op + decoder precedence); ready-work restated as list-then-fan-out (M1); cache gains an ETag validator (M2) + a briefing-counts snapshot reconciling GV2 (M3); Q4 routed to query-side fan-out, not the per-clone cache (M4); a single authority fixed per field + corrected write-cost attribution (M5); verification encoding resolved to one authority (M6); dead node_id cache column dropped (m1); redirect facet added to the taxonomy (m2); duplicate→target timeline read stated (m3); block evolution is additive-only-forever (m4); duplicated-block rule (m5). Prior v1: initial drill-down from PRD §7/§7a. · source: planning session · stage: design`

**Parent:** `documentation/backlog-service-prd.md` (PRD v4) and, through it,
`documentation/backlog-service-requirements.md` (DM1–7, Q1–5). This doc fixes the **field-level
GitHub encoding** the PRD left to "the next level," plus the **optional-cache schema**.

**Design rule (the lock-in learning).** A persisted schema's requirements are *its consumers' future
queries*, not GitHub's mechanism. Every field cites the query (Q1–Q5, ready-work, stale-verification,
provenance) or requirement (DM/CC/TF/XP) that justifies it. A field no consumer queries is not added
(the retired-`git_sha` precedent — a dead-read field becomes a misread field). **Encoding validation is
advisory and tolerant** (DM1): a natural variant of the same meaning normalizes, never hard-fails; the
hard fail is reserved for genuine ambiguity (unknown *status*, malformed ID).

**One authority per field (M5).** Every field has exactly **one** authoritative encoding; a value is
mirrored to a second location **only where the mirror serves a distinct consumer** (see §1.2). This
bounds write-amplification. *Write-cost note (corrected):* only **creating an issue or a comment** is a
GitHub "content-creation" against the tight **~500/hr** cap; label add/remove, body PATCH, and
state changes are ordinary calls against the **5k/hr core** limit + latency (AG5). So mirroring costs
*latency + core budget*, not the scarce content budget — except a mirror that takes the form of a
*comment*, which does spend it (why verification-as-a-comment is dropped, §1.2/M6).

**Altitude & foreign-API note.** This is *design intent* — which GitHub primitive encodes which
concept — not the exact REST/GraphQL JSON field names. Those are a `verify-api` step at build
(planning "Foreign API Verification"): read the live payloads before writing handlers.

---

## 1. Entities

System of record = **GitHub Issues**; entities are *projections* onto GitHub primitives. The optional
cache (§6) projects the same fields for the queries GitHub can't serve read-your-writes.

### 1.1 Item (one GitHub issue)

| Field | Type / values | **Authority** (one per field) | Justified by |
|---|---|---|---|
| `id` | `owner/repo#number` (canon); `repo#number` (short, same-owner) | issue **number** (immutable except transfer, §5) | DM4 · every ref |
| `node_id` | opaque | issue **node-id** (entity-level transfer fallback; *not* cached, m1) | DM4 (verify transfer-stability in S2) |
| `title` | string | issue **title** | AG2, Q1 |
| `body` | markdown + one `prawduct:` block (§2) | issue **body** | AG2, round-trip |
| `status` | `submitted \| open \| in-progress \| shipped \| dropped` | open/closed **+ `state_reason`** (closed) **+ `status:` label** (open sub-states) — §4 | DM2, ready-work |
| `stage` | `idea…ready` (soft) | **`stage:` label only** (not mirrored to block) | DM2, ready-work, `pick` |
| `area` `effort` `impact` `source` `kind` | soft enums | **labels** (org Fields where owner is an org) | DM1 (`kind` = the soft-enum extension, not a DM1-named field) |
| `reviewed` / verification | date (`{by, on}` designed, unbuilt) | **`prawduct:` block `reviewed`** — the live encoding; `<actor>` comes from the API identity on the write, not the block. `verified` `{by, on}` + **cache `reviewed`** (the TF2 date-range query) stay designed-but-unbuilt (zero live items). *No label, no marker-comment* (M6). See §2 "`reviewed` vs `verified`" | TF2 |
| `assignee` / claim | user/agent + `claimed_at` | issue **assignee** (claim) + block `claimed_at` (visible staleness) | CC3, ready-work |
| `relationships` | §1.3 | native dependencies / sub-issues / refs | DM3, ready-work |
| `provenance` | §1.5 | block (detail) + `source:<product>` label (the coarse XP2/Q4 filter) | XP2 |
| `history` | append-only | issue **timeline/events** (native) | CC4 |
| `closed_by` | branch/PR/release handle | native **timeline close-ref** (close-on-merge) + block **`closed-by`** (manual-close fallback — hyphenated in the block; see §2) | GV3 |

*Soft enums (DM1):* an undeclared `stage:`/`kind:` value is **flagged, not rejected** (scriob's `kind:`
on 158 items). `added` is display/sort metadata (sort-by-date under Q1), not a standalone query key.

*`closed_by` (GV3, added v3):* the ship-**traceability** handle that replaces git's ship-atomicity. On a
close-on-merge it is **authoritative from the native `closed` timeline event** (the closing PR/commit
ref, no new stored field), with the block **`closed-by`** (hyphenated — §2) only as the **manual-close** fallback (a bare
`status`→shipped otherwise carries no handle). The GV3 bidirectional drift sweep (*shipped-but-PR-died* ·
*merged-but-item-open*) is a janitor `list`+timeline scan, not a stored projection — see API contract
§2.6.

### 1.2 Field authority & justified mirrors
- **Native/label-authoritative, block-unmirrored:** `status`, `stage`, `area/effort/impact/kind`,
  `assignee`. Changing them is a label/state call (core budget), never a content-creation.
- **Block-authoritative, unmirrored:** `verified` (designed, unbuilt), `claimed_at`, `attachments`, `superseded_by`,
  `automated`/`worker` (the unattended-actor marker — Security §1a/CC4; self-asserted like all block
  fields, trustworthy for audit only insofar as the acting API identity is), and the four
  **editorial** fields `refs`/`revisit`/`closed-by`/`reviewed` (§2).
- **Writable vs import-only, within the block.** Block-authoritative does not mean writable — the
  two axes are independent and conflating them is what left the editorial fields stranded for a
  whole cutover. Writable through `update`: the four editorial fields. Writable only through the op
  that owns the invariant: `claimed_at` (claim/unclaim), `related` (link/unlink), `superseded_by`
  (merge). **Import-only, deliberately and permanently:** `id_aliases` and `v` (identity and schema
  version — MG2 alias loss), `original_title`/`original_body` (write-once MG6 provenance),
  `automated`/`worker` (caller-settable attribution *is* the SEC-6 forgery they guard against),
  `provenance` (untrusted until triaged — Security §5), and `added` — for which the native
  `created_at` is a better answer than any stored copy, being unforgeable and never in need of
  update.
- **Two justified mirrors** (each side serves a *distinct* consumer, not the same value twice):
  - `id:` — the **label** makes old refs *queryable/resolvable*; the **block `id_aliases`** is the
    export round-trip record.
  - `source:` — the **label** is the coarse Q4/XP2 *filter*; the **block provenance** is the detail.

### 1.3 Comment · 1.4 Claim · 1.5 Provenance · 1.6 Attachment
- **Comment** → native issue comments (DM5); cache mirrors text only for Q1-fulltext/Q3.
- **Claim** (Item facet) → `assignee` atomic take; block `claimed_at` = visible staleness; **default
  claim-staleness TTL** drives auto-unclaim/flag so `pick` can't starve (CC3, M11). Residual double-take
  race accepted (take-and-verify).
- **Provenance** (Item facet) → `{source_product, source_version, session_ref, submitted_at}` in the
  block + `source:<product>` label. **Untrusted until triaged** — the block is attacker-controllable
  self-assertion wherever the actor has write (Security Model §5/F3); lands in `status: submitted`.
- **Attachment** → **release-asset wrap** (default) *or* **attachments-branch via git-data API** (both
  no-PR, G1); block `attachments: [{name,url,kind}]`; native inline attended-only; inline-on-private → S5.

---

## 2. The `prawduct:` body block (exact round-trip of non-native fields)

A **single fenced block** at the end of the body carries what GitHub has no native slot for, so
export round-trips losslessly (MG2). **Block-authoritative fields only** — it does *not* mirror
`stage`/`status` (those are label/state-authoritative, §1.2). Tolerant parse: unknown keys preserved
verbatim (forward-compat); missing keys default. **Exactly one block per issue** — the parser takes the
**last** fenced `prawduct` block and flags any earlier one (the BKL-7M4Q duplicated-paragraph origin +
CC5 human edits make a doubled/misplaced block plausible; last-block-wins is deterministic, m5).

````
```prawduct
v: 1                         # block schema version (§7 — additive-only-forever)
id_aliases: [BKL-7M4Q]       # migrated PFX; old refs resolve forever (label + here)
verified: [{by: …, on: …}]   # DESIGNED, UNBUILT — zero live items; `reviewed:` below is TF2's live encoding
claimed_at: 2026-07-16T…Z    # CC3 visible staleness
provenance: {source: scriob, version: …, session: …}   # XP2 detail (label = coarse filter)
superseded_by: owner/repo#123                            # merge/duplicate redirect (DM7/AU3)
attachments: [{name, url, kind}]                         # DM6
automated: true                                          # unattended-actor marker (Security §1a, CC4)
worker: prawduct-hook                                    # the unattended worker id (paired with `automated`)
original_title: Add the harbor map overlay               # pre-migration title, verbatim (MG6 — only when the scrub changed it)
original_body: "line one\nline two"                      # pre-migration body, verbatim; JSON-string-encoded to one line
refs: requirements-x.md#section, arch-y.md               # governing docs (item→doc; `related`/`superseded_by` are item→item)
revisit: 2027-01-01 | <event trigger text>               # norm-exception / stopgap expiry clock
closed-by: fix/some-branch                               # manual-close ship handle (§1.1 `closed_by`; NOTE the hyphen)
reviewed: 2026-08-02                                     # TF2 re-confirmation date — see § Editorial fields below
```
````

**Editorial fields (`refs` · `revisit` · `closed-by` · `reviewed`) — writable, not import-only.**
These four carry a human/agent *judgment about the item* that GitHub has no native slot for. They
entered the block through the importer's preserve-unknown-keys rule (§7 additive-only-forever) and
were **write-once for the whole cutover**: the only writers were the importer and the ops owning one
field apiece, so `update --body` carrying an edited block returned ok and discarded the edit. They
are now written by `update --refs/--revisit/--closed-by/--reviewed` and `file --refs` (#550).
Usage when that landed, across 388 blocks: `reviewed` 300 · `refs` 270 · `closed-by` 149 ·
`revisit` 6.

**`closed-by` is hyphenated in the block** while §1.1 names the field `closed_by` and the item
projection exposes `closed_by`. That is deliberate and must not be "harmonised": 149 live items
spell it with a hyphen and none with an underscore, so renaming the block key would orphan every
one. The hyphen→underscore hop happens in `encode.decode_item` and only there.

**Block values are single-line by construction, and this is a security property, not a formatting
one.** The block is line-based and the parser reads *every* line inside the fence as a field, so a
value carrying any separator `str.splitlines()` recognises does not store a multi-line value — it
injects sibling fields, reaching `automated`/`worker` (SEC-6 attribution forgery) and `id_aliases`
(MG2 permanent-alias loss) past any key-level allowlist. `encode.check_block_value` rejects such
values at every write op, and derives its predicate from `splitlines()` itself rather than
enumerating separators, so guard and parser cannot drift. Rejected rather than escaped:
`format_text` would make any value safe but JSON-quotes it on disk, forking `closed-by` into two
spellings against the items that carry it bare.

**`reviewed` vs `verified` — one concept, two fidelities (resolved 2026-08-02).** §1.1's
`reviewed`/verification row and the block's `reviewed:` date are **not** competing fields. TF2 asks
for *"premise re-checked against code by `<actor>` on `<date>`"*, and TF3 counts `reviewed:` stamps
as the observed workload — so `reviewed:` **is** TF2's stamp, in its date-only form. The richer
`verified: [{by, on}]` shape sketched above remains designed-but-unbuilt: **zero live items carry
it.** The live encoding is therefore the `reviewed:` date, with the `<actor>` half supplied by the
GitHub API identity on the write (native, unforgeable, in the issue timeline) rather than
self-asserted in the block — which is strictly better than storing it, since every block field is
forgeable by any write-capable actor. Build `verified` only if a use case needs multiple retained
verification events per item; a single latest-re-confirmation does not.

**`reviewed` is never stamped as a side effect of another edit.** Native `updated_at` already
records that an item was touched. A `reviewed:` that moved on every write would be a self-asserted
copy of it; the field's entire value is that a label fix moves `updated_at` **without** asserting
anyone re-read the item, which is the distinction the >90d staleness sweep depends on.

**`original_title` / `original_body` (MG6 restructure preservation).** Written by the importer only
when an owner-confirmed restructure plan changed the item at create (issue-standard §5); absent
otherwise. The block is line-based, so `original_body` (multi-line) is **JSON-string-encoded** to a
single line (`encode.format_text` / recover verbatim with `encode.parse_text`) — the escaping also
guarantees the stashed text can never open/close a fence line inside the block. `original_title` is
single-line and stored raw. Both are write-once migration provenance, not consumed by any read path.

Every block field is **self-asserted** and forgeable by any write-capable actor (Security Model §5);
only the GitHub **API identity** is trustworthy for attribution.

---

## 3. Label taxonomy (namespaced — GV6 coexistence)

All prawduct labels are **`<facet>:`-namespaced** so they never collide with a repo's existing labels
(GV6): `stage:`, `status:`, `kind:`, `area:`, `effort:`, `impact:`, `source:`, `id:`, `verified:`,
and **`superseded-by:`** (the redirect facet used by merge/transfer, §1.3/§5 — m2). Provisioned +
reconciled by `/prawduct:onboard`/`doctor` (GV5). **Non-prawduct issues/labels are out-of-scope, not
malformed** — the adapter ignores issues carrying no `stage:`/`id:` marker (but see the
anonymous-quarantine reconciliation, Security Model §6/F7: an unlabeled non-collaborator filing *is*
the quarantine state, surfaced to triage, not silently ignored).

---

## 4. State machines

**Two orthogonal axes (DM2), never flattened.**

**status** — closed states carry meaning in `state_reason`; open sub-states carry it **only** in the
`status:` label (there is nothing else to encode them):
- `submitted` → open + `status:submitted` · `open` → open, no `status:` label · `in-progress` →
  open + `status:in-progress` (+ assignee)
- `shipped` → **closed + `state_reason: completed`** · `dropped` → **closed + `state_reason:
  not_planned`**
- human "close as duplicate" → `state_reason: duplicate`, decoded as `dropped` + `superseded_by`
  **read from the `marked_as_duplicate` timeline event** (state_reason names the *kind*, not the
  *target* — m3); decoder stays **fail-open** on unknown reasons.

**stage** = `stage:` label only: `idea → research → requirements → design → ready`. Load-bearing:
`pick` routes only `stage: ready` to code (else discovery) — DM2/GV1.

**Crash-safe transitions (B1 — delivers the CC1 "a crashed client never half-writes" guarantee).**
Because open sub-states live *only* in the `status:` label, a naive
remove-then-add is not crash-safe (a crash strands zero or two labels). So status changes go through
one idempotent op:

> **`set-status(item, target)`** — (1) if `target` is closed, set open/closed+`state_reason` *first*
> (the authority); (2) **add** `status:target` *before* removing any other `status:` label (never a
> zero-label window); (3) remove the other `status:` labels. Re-running is a no-op.

**Decoder precedence** resolves the transient/torn state deterministically: for an **open** issue,
`in-progress > submitted > (none = open)`; multiple `status:` labels → highest wins and reconciliation
removes the losers; for a **closed** issue, `state_reason` is authoritative and any `status:` label is
meaningless → reconciliation strips it. So a crash mid-transition always reads as a *valid* state and
self-heals on the next write — no contradictory item survives (this closes v1's false "wherever
derivable" claim).

**Ready-work query (the `pick` engine)** = `state=open AND stage:ready AND unassigned` — **these three
are REST *list*-endpoint filters**, served **online, read-your-writes** in one call (M8 stands). But
the remaining two predicates are **not** list filters and force a **per-candidate fan-out** (M1):
- **the blocker predicate** — native dependencies aren't a list parameter → one dependency fetch per
  candidate. **Implemented as N+1 REST, not GraphQL** (corrected 2026-07-28: there is no GraphQL
  anywhere in `plugin/lib/backlog/`; the original "GraphQL sub-connection or N+1 REST" wording left the
  cheaper option open and it was never taken). The fetch is therefore taken **lazily in rank order and
  stops at `limit`**, so the cost is O(limit + blocked-skipped), not O(eligible).
- The candidate's `why` reports **"no blockers recorded"** when the dependency read comes back empty —
  *not* "no open blockers". An empty read is absence of data, and for any backlog migrated out of
  markdown it is empty **by construction**: `related:` is carried in the issue body and mapped to no
  native edge, so an all-clear phrasing would assert a verified result about a permanently empty field.
- **"claim past TTL"** — `claimed_at` (block / assignment event) isn't list-range-filterable → per-item
  check on the reaping path.

So `pick` is **list-then-fan-out**: online and consistent (no cache needed), but O(candidates) reads,
not one call — cheap at portfolio scale, but the latency/read cost is real and paced under the core
limit. (A cross-repo blocker's state is only reliably seen online — a per-clone cache can misjudge it.)

---

## 5. Identifiers

- **Canonical `owner/repo#number`** — GitHub's own cross-ref syntax; **short `repo#number` same-owner
  only** (ambiguous under federation).
- **Immutable except `gh issue transfer`** (renumbers) → transfer writes a **`superseded-by:` redirect**
  via the alias machinery; store `node_id` as the transfer-stable fallback (*undocumented → prove S2*).
- **Migrated `PFX-XXXX` → permanent `id:PFX-XXXX` alias labels** + `id_aliases` block entries; old refs
  resolve forever; **no new PFX**. Absorbs 27–58 hand-minted prefixes/project (DM4); prawduct's own
  `BKL/ADR/ADV/MET/CRT…` is the multi-prefix stress case (S2).
- **Digit-suffix disambiguation** — a digit-suffix token (`ADR-12`) matches both the shell
  `repo-number` spelling and the PFX alias grammar. Precedence (deterministic, documented — never a
  silent guess): with a target repo present, the **alias wins when an item carries it** (an exact,
  uniqueness-checked match — MG1 outranks a guess at a repo name); the `repo-number` reading stands
  when no item does; a double-claimed alias is `alias_collision`, never a pick. The `#` spellings
  (`repo#number`, `owner/repo#number`) never match the alias grammar — they are the unambiguous
  escape hatch (API contract §3).
- **Alias uniqueness is an integrity constraint** — an `id:PFX` alias must resolve to **exactly one**
  live item; the importer/adapter rejects (flags) a *second* item claiming an existing alias, so ref
  resolution can't be hijacked by a colliding `id:` label (Security Model §5/F3).
- **Operation-idempotency markers** (parallel machinery to `id:`/`superseded-by:`, but idempotency-only,
  never identity) — a resumable compound op stamps its outputs with a marker derived from the call's own
  arguments, so a re-run finds and skips what it already produced (API contract §2.3/§2.4):
  - **`split-op:<token>#<index>`** — `token` = a digest of *(parent canonical id, ordered child specs)*;
    stamped on each child so a resumed `split` skips children already made and creates only the missing.
  - **`source-key:<digest>`** — `digest` = *(submitter identity, source item ref / title+body digest)*;
    stamped on a `file-upstream` item so a re-file returns the existing item rather than duplicating.
  - **`import-key:<digest>`** — `digest` = *(title, body)* of an **id-less** imported item (one with no
    hand-minted `PFX`); the importer's skip-if-exists key for items that have no `id:PFX` alias to key on,
    so an id-less item is still resumable/non-duplicating. **Idempotency-only, never an identity** — it is
    deliberately *not* an `id:` alias (a synthetic value must never be mistaken for a real ref).
  These are self-derived from the call (like the `id:PFX` skip-if-exists), findable via the same
  label/marker lookup; encoding (label vs block entry) is a build-time detail.

---

## 6. Optional cache schema (projection — off by default)

**Derived personal state, never the truth** (D5) — exists only where GitHub can't serve a query
read-your-writes or offline. SQLite, per-clone, **gitignored**, `git-common-dir`-keyed. **Every column
is a Q-projection** (no dead fields — the retired-`git_sha` rule). *Security note (F4/F5):* the cache is
**as sensitive as its most-sensitive stored body** (issue bodies carry pasted secrets), and it
authorizes at **fetch** time — cross-repo entries must **revalidate on read** (Security Model §3/§4).

| Table / index | Serves | Notes |
|---|---|---|
| `item(id, title, body, status, stage, area, effort, impact, source, assignee, added, reviewed, updated_at, **etag**, fetched_at)` | Q1-structured, ready-work, Q5, TF2 (`reviewed` date-range) | `etag`/validator = the **conditional-request** column G3's revalidation needs (M2); `fetched_at` = visible age. **No `node_id`** (dead-read, m1) |
| `item_fts(title, body)` (FTS5) | Q1-fulltext, Q3 lexical | the read-your-writes path GitHub search lacks |
| `comment(item_id, body, author, created_at)` | Q1-fulltext, Q3 | text mirror |
| `relationship(src, kind, dst)` | ready-work blockers (per-clone) | *within one repo*; cross-repo blockers checked online |
| `cursor(scope, since)` | Q2 incremental refresh | primitive for sweeps/prefetch |
| `briefing_counts(scope, counts_json, fetched_at)` | **GV2** — session-start counts | the **P0 persisted-counts floor** the PRD admits (M3): a degenerate cache w/ visible age so "start never waits"; distinct from the always-derived Q5 read path |

*On-disk (build decision, slice):* the SQLite `item`/`item_fts`/… tables arrive with the read-through
cache (**W1**). The **slice ships only the `briefing_counts` floor**, and as a *degenerate* cache it is a
small **JSON file** — `<git-common-dir>/prawduct/backlog-counts.json` (the same clone-shared,
never-committed home as the evidence store; a scope-keyed map of `{counts, fetched_at}`,
`schema`-versioned so an unreadable file is discarded and re-derived, never migrated). Not SQLite until
W1 needs the query tables. The reader (session start) reads it **in-process** — zero-latency,
network-independent (BLOCK-5); the writer is `refresh-counts` (inline or the D6 detached warm).

**Q4 (cross-project rollup) is NOT cache-served** — the cache is per-clone (one project). Q4 is
**query-side fan-out + merge across owners** (PRD §8.3-Q4, M4), not a cache or GitHub-native feature.
**Counts:** Q5 rollups are derived on read; the *only* persisted count is the `briefing_counts`
snapshot (GV2), which carries visible age and is never treated as truth. The cache **never silently
serves stale** (G3): age visible; a decision-driving read revalidates via conditional request (`etag`).

---

## 7. Schema versioning (never deferred on a one-word note)

- **`prawduct:` block** carries `v:` (currently `1`); readers tolerate unknown/higher keys
  (forward-compat) and a `migrate` **legend-refresh** reconciles the known-key set **additively**.
  **Block evolution is additive-only, forever** — a key's *meaning* is never redefined in place (that
  would silently mis-decode under old readers, the scriob breaking-retrofit precedent, m4); a genuine
  semantics change mints a *new* key and deprecates the old, never a `v:1→v:2` reinterpretation.
- **Cache** carries `schema_version`; a mismatch triggers **rebuild-from-GitHub** (cache is derived, so
  a rebuild is always safe — never a data-loss migration).
- **Adding an optional field** reaches onboarded repos only via a migrate/triage refresh (templates are
  scaffold-only): wire both the per-item backfill and the legend refresh.

---

## 8. Constraints, invariants & open questions

**Invariants:** nothing hard-deleted (DM7 — merge/split/drop preserve bodies + leave redirects);
tolerant validation (DM1); two axes never flattened (DM2); one authority per field (§1.2); alias
uniqueness (§5); cache subordinate + age-visible + fetch-time-scoped (G3/D5/F4).

**Open questions (build / `verify-api`, not altitude blockers):**
1. Exact REST/GraphQL shapes for dependencies, sub-issues, `state_reason`, timeline events —
   **`verify-api` probe before writing handlers**.
2. `node_id` stability across transfer — **prove in S2**.
3. Attachment default (release-asset vs attachments-branch) — **S5** (inline-on-private).
4. Ready-work fan-out cost at scale — measure in S2 alongside the migration write-burst.
5. Export **on-disk file layout** — **resolved** (the export build chunk), bounded by the NFR §8
   fidelity contract. **Layout:** a destination directory holding **one `item-<number>.json` per
   in-scope item** plus an **`export-manifest.json`** (`{schema, repo, exported_at, count, items}`).
   Each item file carries the decoded projection (`id`/`node_id`/`title`/`body`/`status`/`stage`/
   `labels`/`assignees`), the verbatim `prawduct:` **block**, `id_aliases`, `superseded_by`, the
   **native graph** (`relationships.blocked_by` / `relationships.sub_issues` as refs, and the
   `timeline`), and a `schema` version. JSON (diffable, greppable, tool-agnostic). **Not a queried
   lock-in schema** — re-import into a non-GitHub backend is out of scope (MG2/M10), so the layout is a
   build choice bounded only by fidelity, versioned (`EXPORT_SCHEMA_VERSION`) so a future bump is a
   clean re-dump, never a data migration. (Resolves PRD §8.9/MG2's forward pointer, which previously
   over-promised that this doc "pins the on-disk representation".)

*(v1's open question "does `status:` need a label for shipped/dropped" is now **resolved**: shipped/
dropped are `state_reason`-authoritative with **no** `status:` label; only the open sub-states
submitted/in-progress carry one — §4.)*

## 9. Traceability
DM1→§1.1/§3; DM2→§4; DM3→§1.3; DM4→§5; DM5→§1.3; DM6→§1.6; DM7→§8. Q1-structured→§4 ready-work + §6;
Q1-fulltext/Q3→§6 (`item_fts`); Q2→§6 (`cursor`); **Q4→query-side fan-out (NOT the cache), §6 note**;
Q5→§6 (derived-on-read + the `briefing_counts` GV2 exception). ready-work→§4 (list-then-fan-out);
stale-verification (TF2)→§1.1 block `reviewed` (live; `verified` + cache `reviewed` designed-but-unbuilt); provenance (XP2)→§1.5 + `source:` label
(the XP2 filter — *not* Q4); **GV3→§1.1 `closed_by`**, block key `closed-by` (native close-ref authoritative, block fallback;
drift sweep is a janitor scan, API contract §2.6).
