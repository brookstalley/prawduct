---
artifact: data-model
version: 1
scope: backlog-service
depends_on:
  - artifact: backlog-service-prd            # §7 mapping intent, §7a query list, D4 IDs
  - artifact: backlog-service-requirements   # DM1–DM7
  - artifact: api-notes-github-issues        # every encoding fact below is capture-backed
last_validated: 2026-07-16
---

# Data Model — Backlog Service (prawduct item ↔ GitHub issue)

The persisted encodings: label taxonomy, two-axis state mapping, the `prawduct:` body block, and
the ID grammar. **Fields are derived from the §7a queries the data must answer** (coverage table
at the end), not from GitHub's mechanism — this is a lock-in surface; reversal cost is a portfolio
migration. Encoding facts (label limits, `state_reason` cycle, list-item field inventory) are
live captures in `api-notes-github-issues.md`, not recall.

## 1. Label taxonomy — the `pb:` namespace

**Grammar:** `pb:<facet>:<value>` — value verbatim (spaces are legal in label names; captured).
The entire `pb:` prefix is reserved for prawduct; provisioning (GV5, onboard/doctor) treats any
existing `pb:*` label it didn't create as a collision to report, never clobber.

**Why `pb:` and not `prawduct:`:** labels cap at **50 characters, case-insensitive uniqueness**
(captured). Alias labels carry migrated IDs (`pb:id:HALLU-7Q2X`); the 6-char prefix leaves 44 for
values vs 12+38 — headroom for the portfolio's 27–58 hand-invented prefixes and spaced values
(`pb:source:planning session`). Short also keeps the GitHub label picker legible, where the
namespace sorts as one block.

**P0 facet roster** (provisioned idempotently by onboard/doctor — GV5; colors fixed so re-runs are no-ops):

| Facet | Values (soft enum — DM1) | Color | Notes |
|---|---|---|---|
| `pb:stage:` | idea, research, requirements, design, ready | `0e8a16` | load-bearing for `pick` (DM2) |
| `pb:status:` | submitted, in-progress | `fbca04` | ONLY the two open sub-states; see §2 |
| `pb:area:` | per-project | `1d76db` | |
| `pb:effort:` | S, M, L, XL | `c5def5` | |
| `pb:impact:` | S, M, L, XL | `f9d0c4` | |
| `pb:source:` | per-project / product name | `d4c5f9` | provenance (XP2) |
| `pb:kind:` | per-project (scriob facet) | `bfdadc` | observed portfolio facet |
| `pb:owner:` | per-project (scriob facet) | `e6b8a2` | observed portfolio facet |
| `pb:id:` | `<PFX-XXXX>` migrated alias | `ededed` | one per migrated item; permanent |

**Validation is advisory and tolerant** (DM1 + the tolerant-validator learning): unknown facets
and unknown values are *flagged* in command output (`"warnings":[…]`), and a flagged-unknown is
still written — never rejected, never silently promoted to "known". Per-project extension is
just using a new `pb:<facet>:<value>` label; no registry edit required.

Non-`pb:` labels on an issue are **ignored and preserved** — humans and other tooling own that
space (§13 coexistence). A fresh repo's 9 default labels (captured roster) never collide with
`pb:*`.

## 2. Two-axis state encoding (DM2 — never flattened)

**status** (workflow): submitted → open → in-progress → shipped / dropped
**stage** (maturity): `pb:stage:<v>` label, orthogonal, unchanged by status transitions.

| prawduct status | GitHub `state` | `state_reason` | `pb:status:` label |
|---|---|---|---|
| submitted | open | — | `pb:status:submitted` |
| open | open | — | *(none)* |
| in-progress | open | — | `pb:status:in-progress` |
| shipped | closed | `completed` | *(removed on close)* |
| dropped | closed | `not_planned` | *(removed on close)* |

**Decode is total** (every GitHub state must map — humans edit in the UI, §13 drift):

- `state=open` → status from `pb:status:` label; no label → **open**. `state_reason` is ignored
  on open items — captured fact: reopening sets `state_reason: "reopened"`, so reason is *not*
  a reliable open-axis signal.
- `state=closed` + `completed` → **shipped**; + `not_planned` → **dropped**.
- `state=closed` + `null`/`reopened`-era values → **shipped**, with advisory flag
  `closed_without_reason` (human closed in the UI pre-dating our writes; reconciliation may
  re-stamp). Shipped is the benign default — dropped implies an explicit decision.
- `pb:status:` label present on a **closed** issue → ignored for decode, advisory flag
  `stale_status_label` (our close op removes it; a UI close doesn't).
- Multiple `pb:stage:` labels → decode as the **minimum** by maturity order + advisory flag
  `conflicting_stage_labels`. Minimum is the conservative choice: a conflicted item must not
  spuriously qualify for ready-work.
- Both `pb:status:` labels present (human-UI drift) → decode as **in-progress** + advisory flag
  `conflicting_status_labels`. In-progress wins because it is the claim-adjacent state — the
  costly mistake is routing an actively-worked item back into triage, not the reverse.

Encode transitions always write both sides in one PATCH (`state`, `state_reason`, `labels`) —
atomic per issue (CC1 rides on GitHub's single-resource atomicity).

## 3. The `prawduct:` body block — exact round-trip fields

A single fenced code block, language tag `prawduct`, flat `key: value` lines (string values,
no nesting), placed at the **end** of the body. Everything above it is the item's body verbatim
(MG1: byte-fidelity). One block per issue; if a human introduces a second, the **first wins**
and decode flags `multiple_prawduct_blocks` (advisory).

````
```prawduct
id: BKL-5D2C
added: 2026-07-13
reviewed: 2026-07-15
verified: 2026-07-16 brookstalley
closed-by: PR #71
related: prawduct#42, SOL-K3PN
superseded-by: brookstalley/prawduct#180
node: I_kwDOTasGxM8AAAABJFNT7A
```
````

| Key | Written by | Semantics |
|---|---|---|
| `id:` | importer | migrated legacy ID (`PFX-XXXX`); pairs with the `pb:id:` alias label |
| `added:` | importer / create | original added date — GitHub's `created_at` is the *migration* date for imported items, so the true date must ride in-band |
| `reviewed:` | importer / update | last triage stamp (portfolio convention) |
| `verified:` | `verify` op | TF2 stamp: `YYYY-MM-DD <actor>` — see §5 |
| `closed-by:` | close op / importer | ship-traceability handle (GV3): branch/PR/release |
| `related:` | importer / update | comma-separated ID refs (any accepted grammar form) — GitHub has no native structured "related" |
| `superseded-by:` | merge (P1) / importer | permanent redirect target (DM4); the superseded issue closes as dropped, body preserved (DM7) |
| `node:` | importer only | GitHub `node_id`, stable across cross-repo transfer renumbering (D4 cost b). **Primary store is the created-issues journal** — it records `node_id` for *every* imported item at zero write cost (it's in the create response). The body-block `node:` rides along opportunistically when the relationship second-pass PATCHes an item anyway. Live creates write no `node:` (an extra PATCH per create for a rare-event guard — the create's JSON output carries `node_id` for consumers that persist refs) |
| *anything else* | importer | **passthrough**: unknown metadata-bar keys are preserved verbatim, original order, never dropped (DM1 soft vocabularies, MG1 fidelity) |

**Importer key-mapping rule (deterministic — the importer implements exactly this):** a metadata-bar key maps
to a **label** iff it is a §1 roster facet (`area, effort, impact, source, kind, owner`);
`stage`/`status` map per §2; the §3 table's round-trip keys map to **block fields**; every other
key is **block passthrough** verbatim. No cardinality judgment, no config knob in P0 — the
allowlist *is* the rule.

Native features hold what they hold natively — nothing is duplicated into the block:
blocked-by/blocks → **dependencies endpoints**; parent/child → **sub-issues**; comments →
**issue comments**; claim → **assignee**; audit trail → **timeline** (CC4).

## 4. ID grammar (D4/O4 — one minting authority)

Canonical: **`owner/repo#number`** (GitHub's own cross-ref syntax — auto-links in every GitHub
surface). All forms normalize to canonical; every command echoes canonical in JSON output.

| Form | Rule | Example |
|---|---|---|
| `owner/repo#N` | canonical, always unambiguous | `brookstalley/prawduct#42` |
| `repo#N` | short form; owner resolved from project config (`backlog.repo`). If `repo` ≠ the configured repo's name, error `ambiguous_id` — cross-repo refs must carry the owner | `prawduct#42` |
| `repo/N` | accepted; final segment all-digits, else it's an `owner/repo` fragment → error | `prawduct/42` |
| `repo-N` | accepted; split at **last** hyphen, right side must be all-digits, **and the left side must equal the configured repo's name** — otherwise the token resolves as a legacy alias. The all-digits test discriminates from typical aliases (`REL-3M7K`), but "no alias has an all-digit suffix" is unverified against the portfolio corpus, so the importer's dry-run **flags any legacy prefix whose aliases would collide with this grammar** (e.g. an alias literally named `<repo>-1234`); a genuinely colliding token errors `ambiguous_id` rather than silently picking a side | `prawduct-42` |
| `PFX-XXXX` | legacy alias: resolved via one `list?labels=pb:id:PFX-XXXX&state=all` call | `BKL-5D2C` |
| bare `N` / `#N` | **rejected** (`ambiguous_id`) — too easy to collide with effort counts, PR numbers in prose | |

**Alias scheme:** each migrated item gets a permanent `pb:id:<PFX-XXXX>` label (uppercase as
minted; uniqueness is case-insensitive — captured) plus the body-block `id:` entry. Aliases
never transfer to new items; **no new PFX is ever minted**. Label-count cost at discodon scale
(~435 aliases — an estimate over *all* migrated items: the 317 open items plus the archived
items that migrate as closed issues, not the open-only 317 the PRD counts elsewhere; the
archive-derived component is confirmed by the Chunk 05 dry-run) is accepted: namespaced labels
sort as one collapsed block in the picker, and labels are the only server-side-filterable alias
store that is read-your-writes consistent (GitHub search is not — PRD §13-6).

**PR numbers:** issues and PRs share the number space, and a PR is addressable via the issues
API (captured: probe PR took #4, carries a `pull_request` key). `get` on a PR-numbered ID
returns `not_found` with reason `is_pull_request` — a PR is never a backlog item.

## 5. Verification stamp (TF2)

`verify` = **one write**: PATCH the body block's `verified:` field to `YYYY-MM-DD <actor>`.
Latest-wins (no stamp history in-band — GitHub's edit timeline preserves the audit trail for
free, CC4). Queryable with zero extra calls: list responses carry full bodies (captured), so
stale-verification = parse `verified:` from each open item's block, filter by cutoff.

Rejected alternative — marker comment per stamp: doubles the write cost at the portfolio's
observed grooming volume (25+ stamps/day), and answering "unverified in N days" would need a
per-item comments fetch (N+1 reads online-only). The basic comment primitive remains for
actual drill-down discussion.

## 6. Claim encoding (CC3)

Claim = native assignee, **take-and-verify**: POST assignee, then GET and confirm the assignee
list contains exactly the claimant. The verify step is load-bearing, not paranoia — captured:
assigning a nonexistent user returns **201 and silently does nothing**. Competing claimers both
201; the read-back disambiguates; the loser backs off with `conflict` (residual race between
read-back and next mutation is documented and accepted — far smaller than today's advisory
`accepted-by:` prose).

## 7. §7a coverage check — every query answerable on paper (P0 = online list API)

All queries run against `GET /repos/{o}/{r}/issues` (+ per-item endpoints), **never GitHub
search** (not read-your-writes consistent). List items carry `state_reason`, full `body`,
full `labels`, `assignees`, `issue_dependencies_summary`, `sub_issues_summary` (captured) —
so every P0 query is list + client-side predicate, no N+1.

| §7a query | Answered by |
|---|---|
| Q1 structured filter over DM1 fields | server-side: `labels` (AND), `state`, `assignee` params; remaining facets client-side over the same list response. Full-text over title/body: client-side scan (bodies in list). Comments full-text: per-item `comments` fetch when explicitly requested (P0-acceptable; cache layer is the P1 accelerator) |
| Q2 changed-since cursor | `since=` param — captured as a strict `updated_at` cursor with proven exclusion; cursor value = max `updated_at` seen, echoed by the CLI for the next call. **Same-second caveat**: strict exclusion at second granularity can permanently skip an item mutated in the cursor's boundary second — cursor consumers send `cursor − 1 s` and dedupe on `(id, updated_at)`; the CLI's `--since` applies this rewind itself so callers can echo the cursor verbatim |
| Q3 top-k similar (dedup) | P1 (deferred); P0 stopgap = advisory lexical title match over a live `list`, superseded by the deferred dedup layer |
| Q4 cross-project rollup | P2 (deferred) — query-side fan-out over per-repo lists |
| Q5 counts derived on read | client-side count over the filtered list; never persisted |
| ready-work (DM3+CC3+DM2) | Two steps, because the captured semantics demand it. **Pre-filter** from list items (no extra calls): `state=open` + `pb:stage:ready` + `assignees == []`. **Verify blockers per candidate**: candidates with `total_blocked_by > 0` get one `GET …/dependencies/blocked_by` — read-your-writes (captured) — and qualify iff every listed blocker is `closed`. The summary's `blocked_by` count is **eventually consistent near mutations** (captured: stale for minutes after a reopen), so it is a hint, never the qualifying test. Candidates with `total_blocked_by == 0` skip the fetch; a *just-added first* blocker could lag into that bucket for seconds — a documented residual window, same class as the claim race (CC3) |
| stale-verification (TF2) | open list + parse `verified:` from body block + cutoff — bodies in list, zero extra calls |
| provenance (XP2) | `labels=pb:source:<product>,pb:status:submitted` — server-side AND |

## 8. Constraints & invariants

- **Nothing hard-deletes** (DM7): drop = close as `not_planned`; merge closes the superseded
  item with body intact + `superseded-by:`; labels (incl. aliases) stay on closed issues.
- **Encode→decode round-trip is lossless** for every cell of the §2 matrix and every §3 key —
  a matrix test enforces DM2 never flattens.
- **Body outside the block is never touched** by any op except explicit body update (MG1
  fidelity discipline applies to live ops, not just import).
- **One writer shape**: all mutations go through `backlog_service.py` encode; nothing else
  formats labels or blocks (the D7 seam — GitHub never colonizes the interface).
