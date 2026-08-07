# Backlog Service — Read-Through Cache (W1): Requirements & Spec

`status: draft v1 (2026-08-07) — owner design session. Combines requirements (the consumer
query inventory, §2) and specification (§3–§8) in one document deliberately: the consumers are
enumerable and small, so splitting them across two files would put the requirement and the
schema it constrains in different places. · source: owner design session · stage: requirements`

**Parent:** `documentation/backlog-service-prd.md`, `documentation/backlog-service-data-model.md`
(entities, IDs, `set-status`), `documentation/backlog-service-api-contract.md` (operation surface,
error vocabulary). This document specifies the **W1 read-through cache** those imply, and the
provider-neutral domain model it materializes. It references their entities rather than restating
them.

**Governing norms** — `.prawduct/artifacts/architecture.md` § Direction (*local-first*; *never
re-implements*; *never specific to Python*; *authority fails closed, advice fails soft*; *every
fact has one home*), `.prawduct/artifacts/data-model.md` § Direction (*derived views are
disposable and never authoritative*), `.prawduct/artifacts/nonfunctional-requirements.md`
§ Direction (*proportionality ratchets both ways*).

---

## 1. Why this exists

Seven backlog readers went dormant at the GitHub Issues cutover. Each announces its own
dormancy rather than reporting silently — that was shipped deliberately, and it is the correct
interim state, not a defect. The owner decision of 2026-07-19 was that every dormant reader is
served by **one persisted format** rather than each minting a bespoke projection and migrating
off it later. This document specifies that format.

The enumeration and count of dormant readers has one home: `DORMANT_CHECKS` in
`plugin/lib/backlog_probes.py`. Do not restate the list elsewhere.

## 2. Requirements — what the consumers actually query

*A persisted format's requirements are its consumers' future queries, elicited from those
consumers rather than inferred from the mechanism.* The seven are enumerated with file pins, so
this inventory is exhaustive rather than sampled.

| # | Consumer | Query it needs |
|---|---|---|
| 1 | Critic backlog reconciliation walk | all **open** items with id, title, body |
| 2 | C-B1 missing metadata | items **created since** a ref/timestamp |
| 3 | C-B2 dedup evidence | **count and ids by `area`** |
| 4 | C-B3 missing hygiene step | **open items by `area`**, joined to the changed-file set |
| 5 | C-B4 dangling id | **does this id resolve** — including through aliases, including dead items |
| 6 | PR R-1 resolved items | same as #1 |
| 7 | PR R-2 closes/status disagreement | **status by id**, alias-resolving |
| 8 | Janitor: group by area | items grouped by `area` |
| 9 | Janitor: dedup candidates | **text search within an area** (the FTS requirement) |
| 10 | Janitor: stale items | open items not updated in >90d — from provider `updated_at` (§2.1) |
| 11 | Janitor: unstaged items | open items with no `stage` |
| 12 | Janitor: neglected hygiene | items in the `promoted` state whose owning chunk shipped |
| 13 | `revisit-due` probe | *retired — see §2.1, not restored* |
| 14 | `dead-why` probe | **id → is-dead**, alias-resolving |
| 15 | `stalled-transition` probe | id → **live? + date floor**, from provider `updated_at` |

**The union is small.** Open-item listing with text; grouping and counting by `area`; id
resolution through aliases including dead items; creation-time filtering; text search scoped to
an area; and two date predicates. That is the whole schema surface. The cache does not need to
be elaborate, and it should not become so.

### 2.1 What the consumer pass found — restoring the cache is not sufficient

Three consumers are blocked on defects the cache does not touch, and two should not be restored
at all. **This is the load-bearing output of the requirements pass.**

**Design rule that resolves most of this: observable beats stored.** Where a signal can be
derived from something the provider or git already maintains, do not store a field for it — a
stored field can be forgotten, can lie, and needs a write path. This is the same reasoning that
chose `working-branch` over a stored claim timestamp (§3).

- **Consumer 10 (stale items) drops its stored dependency.** It reads `reviewed`/`added` today;
  the provider's `updated_at` is always present, free, and cannot be forgotten. Use it. The
  semantics differ slightly — `updated_at` moves on any edit, `reviewed` meant deliberate
  re-confirmation — and for a staleness *nag* the derived signal is the better of the two.
- **Consumer 15 (stalled-transition) likewise** takes its date floor from `updated_at` rather
  than stored metadata dates.
- **Consumer 13 (`revisit-due`) is retired, not restored.** A query cannot substitute for it —
  `revisit:` encodes *"this exception was granted until date X"*, which is intent, not state, and
  two exceptions granted the same day with different clocks are indistinguishable to any
  age-based query. It is retired for a different reason: **exception clocks have already migrated
  to prose in the governing artifact**, walked by the janitor's Norm Health sweep.
  `nonfunctional-requirements.md`'s own live exception records the decision — *"That trigger is
  prose here and on the item, not a `revisit:` field, because the Issues backend has no write
  path for one"* — and notes `probe_revisit_due` "fires on dated values and is dark post-cutover
  regardless." It is a markdown-era vestige.
- **#529 (`promoted` has no Issues-backend equivalent) blocks consumer 12.** The status value
  the check keys on does not exist on this backend. This one is a real prerequisite.
- **Janitor checks 6 and 7 are retired, not restored.** Counting unstructured legacy items and
  proposing an `## Archive` split are meaningless once Issues is system of record — the
  janitor's own prose already says so. Restoring them would ship advice a reader could act on to
  no effect. Under the proportionality norm, removal is the default for a control with no
  remaining yield.

**Net: W1 restores twelve of the enumerated consumers; one (12) waits on #529; three (13, and
janitor 6/7) are retired.** Any plan claiming to "restore the dormant checks" without this split
is overstating.

**The write-path gap is no longer a W1 prerequisite.** An earlier revision of this document made
#550 (`refs`/`reviewed`/`revisit`/`closed-by` unwritable; see also #564 for `revisit`
specifically — the two may be duplicates and are worth a dedup pass) a hard blocker on the
strength of consumers 10, 13 and 15. Applying *observable beats stored* removes all three. #550
remains a genuine defect, and the **new `affected` field (§3) will need a write path** — the same
underlying gap — but nothing that exists today waits on it.

### 2.2 One consumer gets better, not merely restored

Consumer 4 (C-B3) and consumer 1 today require a reviewer to read item text and infer whether
the diff touches it. With the `affected` field (§3) indexed, that becomes a set intersection
against the changed files. That is the one place this work produces a capability the markdown
backend never had, and it is the strongest argument for `affected` over leaving `refs` as free
text.

## 3. Domain model — vocabulary

The cache schema is stated in **prawduct's** vocabulary, not the provider's. This is what lets
the ten restored consumers bind to prawduct semantics and never learn what GitHub is.

**Carried unchanged** from the existing model: `stage` (idea/research/requirements/design/ready),
`status` (submitted/open/in-progress/shipped/dropped), `kind`, `area`, `effort`, `impact`,
`source`, `added`, `reviewed`, `revisit`, `closed-by`, `related`, and the link edges.

**Decided this session:**

- **`impact` only — no `severity`.** `impact` subsumes it and additionally expresses the benefit
  of a new feature, which `severity` cannot. One axis.
- **No `size`** — duplicate of `effort`.
- **`kind` already carries** bug/feature/docs as an open soft enum. No new field.
- **`refs` splits into two fields.** Today `refs` is free text mixing governance artifacts with
  code paths and prose annotations, so it can never be matched against a changed-file set.
  - `refs` — governance artifacts: what governs this item, why it exists.
  - **`affected`** *(new)* — a structured path list, no prose. Annotations belong in the body.
    Consumers: 1 and 4.
- **`tags` added alongside `area`.** Not redundant: `area` is exactly-one and wired to the title
  by `normalize_title(title, area)`, the §1 prefix enforced since v3.2.7 — it is taxonomy, and
  it is what makes a list scannable. `tags` is folksonomy: open, multi-valued, per-team, and the
  place ad-hoc metadata belongs. Maps natively to labels on every candidate provider.
  - **Binding rule: nothing ever gates on `tags`.** No check, gate, or verdict may read them.
    That is what makes synonym drift (`perf`/`performance`/`speed`) harmless rather than
    corrosive, and it must be stated before someone builds a check on them.
- **`working-branch`** *(new)* — replaces the "claimed-by" concept. If populated, someone is
  working the item.
  - Chosen because **staleness becomes observable rather than stored**: the branch's last commit
    is the activity signal, so no claim timestamp and no expiry policy are needed. Merge
    self-resolves the claim, and it gives record-keeping at merge and close for free.
  - Provider-neutral by substrate — branches are git, which every backend shares, and
    `architecture.md`'s local-first norm already names the git object database as coordination
    substrate.
  - **Must mean a pushed ref.** An unpublished branch is an invisible claim, which fails at the
    only job the field has.
  - **Must name the repo.** `backlog_service_repo` can differ from the code repo.
  - Many items per branch is normal and expected (#612 and #614 shared one).

## 4. Identity and aliases

**No synthetic prawduct-native id is minted.** An earlier draft proposed one; it buys nothing an
alias chain does not. On a provider migration the new record carries the old id as an alias and
every historical citation — `(#614)` in a commit message, `#249` in the change-log — keeps
resolving.

Three rules:

1. **One id per item** — whatever the provider assigned at creation.
2. **An alias set that accumulates and never drops an entry.**
3. **All resolution goes through the alias table. Nothing parses an id string as live provider
   coordinates.**

Rule 3 is the actual defect found. `#618`'s block stores `related: [brookstalley/prawduct#249,
…]`. Parsed as owner/repo/number at read time, a migration must rewrite every edge and a missed
rewrite breaks the graph silently. Resolved through aliases, those strings keep working
untouched. Consumers 5, 7 and 14 all depend on this.

**Provider tagging is asymmetric:**
- **Live ref: untagged.** It inherits the product's configured backend; per-item tagging is
  redundant while one backend is configured at a time.
- **Aliases: tagged** (`github:brookstalley/prawduct#249`). After a migration a foreign-era id
  sits beside a live one, and `owner/repo#number` is **not** GitHub-unique — GitLab uses
  `group/project#123` and Gitea is GitHub-shaped by design. Those are precisely the self-hosted
  options motivating provider neutrality. Tagging aliases is what stops resolution degrading
  into shape-parsing, which rule 3 forbids.

The machinery already exists — `id_aliases`, the `id:PFX` alias label, and the label↔block
self-heal in `lib/backlog/core.py` — built for the markdown→Issues cutover. It needs pointing at
provider ids rather than legacy PFX ids.

**As built (W1 Chunk 04): the alias *table* is the cache's `item_alias`, and labels stay PFX-only.**
The asymmetry is deliberate rather than a partial job. A label is the *live* path's index — what
lets `core.resolve_ref` find an item by alias with one search against the provider — and a
hand-minted `PFX` has no other coordinates, so without a label it is unfindable. A **provider**
alias does have coordinates: it is a real `owner/repo#number` that `item_alias` resolves without
asking the provider anything. Minting labels for it would add a write path, a self-heal obligation
and a 50-character label budget to buy a second index over a set that is already indexed. So the
grammar for both spellings lives in `lib/backlog/ids.py` (`provider_alias`, `parse_provider_alias`,
`is_alias_token`) and the resolution — live id, then alias, then redirect, in a documented order
that is reported rather than guessed — lives in `lib/backlog/cachequery.py`. Rule 3 holds where it
matters: a stored citation resolves through the table, never by being parsed as live coordinates.

## 5. Cache semantics

- **A cache, never truth.** `data-model.md` § Direction: *derived views are disposable and never
  authoritative — no gate reads a view to reach a verdict.* Today's counts file already states
  the same: *a degenerate cache, subordinate to GitHub and never treated as truth.*
- **Therefore: W1 may never back a blocking verdict.** Satisfiable today — every one of the
  enumerated consumers is NOTE, WARNING or advisory level. Anything that later wants to *block*
  on backlog state must read the provider live. Without this rule W1 quietly converts a ratified
  norm into a violation.
- **Location: `<git-common-dir>/prawduct/`**, beside the evidence store and the counts snapshot.
  Never committed — so the merge-conflict problem that plagued `backlog.md` cannot recur; shared
  by every worktree of a clone; no `.gitignore` contract to get wrong; isolated between repos by
  construction. (Note `snapshot.py`'s docstring contemplates W1 as a *working-tree* SQLite file;
  this specification places it in `git-common-dir` instead, which also disposes of the
  content-borne-secret concern that motivated the remark.)
- **Zero cache-only fields.** Every domain field has a backend representation: `tags` → labels,
  facets → labels, structured fields → the body block, `status` → state/state_reason, `area` →
  the title prefix. `affected` and `working-branch` live in the body block.
- **The invariant: drop the cache, rebuild from the backend, compare.** Any difference is a
  cache-only field, which is data loss on rebuild.
- **That same test is the provider-adequacy test.** If the cache rebuilds completely from a given
  backend, that backend's mapping is complete. One invariant proves both properties; no separate
  portability suite is needed.
  - **Its reach is exactly the columns the cache holds, and W1 gave up one on purpose.** `tags` has
    no cache column (Chunk 04 — no consumer query reads it, so the no-dead-fields rule took it), so
    a backend unable to represent tags would pass the invariant. That is the accepted cost of not
    carrying a dead field, and it is small on this particular field: `tags` → labels is the mapping
    every candidate provider satisfies most trivially, and the live `--tag` filter exercises it end
    to end. The zero-cache-only-fields half above is untouched — a field the cache does not store
    cannot become a cache-only one.

## 6. Sync

- **Server-side `updated_at` watermark.** Fetch only items updated since the watermark and
  upsert. GitHub's REST issues endpoint takes `since`; JQL has the equivalent.
  **GitHub's `since` semantics, verified live against the backing repo (2026-08-07), not
  recalled** — the four answers this design rests on:
  1. **`since` filters on `updated_at`, not `created_at`.** In a probe window, 9 of 32 returned
     items had been *created* before the window and none had `updated_at` before it.
  2. **It is inclusive** (`updated_at >= since`): `since` set to an item's exact `updated_at`
     returns that item; one second later does not. So a re-issued query always re-reads the
     boundary item — the overlap margin below is belt-and-braces, not the only guard.
  3. **`since` and `state` are independent AND filters.** Same window: 24 open + 8 closed = 32
     with `state=all`. **A close is therefore only visible with `state=all`** — the sync query
     must not use the `state=open` default, or the bullet below is false and closed items keep
     a stale open row forever. This is the single most load-bearing fact in this section.
  4. **The list endpoint supports `ETag`/`If-None-Match`, and a 304 costs zero rate-limit
     points.** Measured from each response's own `X-RateLimit-Used` header, **with a positive
     control**: three unconditional 200s stepped it 134 → 135 → 136, and three conditional
     requests then held it at 136. Read the header, not the `rate_limit` endpoint — polling
     that reported `used: 0` for *both* arms of this experiment, which looks like a confirming
     result and is actually a dead instrument. The validator is **query-specific** —
     `(state, since, per_page, page)` each change it.
- **Timestamps come from server values, never the local clock.** Overlap the watermark window by
  a margin and make upserts idempotent, so an item updated at the boundary is re-read rather than
  missed.
- **The watermark lives with the cache**, uncommitted. Its absence means full sync, which makes
  rebuild the safe default rather than a special case.
- **Two different validators, and conflating them is a defect.** The list ETag above validates
  *the query*; `item.etag` (Data Model §6) validates *one item's endpoint*, and they are not
  interchangeable — verified live: a list ETag replayed against `GET /issues/{n}` returns 200,
  while that item's own ETag returns 304, and the list response body carries no per-item
  validator (only `node_id`, excluded as a dead read). **Sync therefore cannot populate
  `item.etag` from a list fetch and must not try.** Sync's validator belongs with the cursor,
  which is the thing whose identity the query has; `item.etag` is written by the decision-path
  read that actually issues a single-item request, and stays NULL until one does.
- **The no-op sync is free, and that is what the cursor-scoped ETag buys.** When a sync returns
  nothing new the cursor does not advance, so the next sync re-issues a *byte-identical* query,
  matches the stored validator, and gets a 304 at zero rate cost. Once items do come back the
  cursor advances, the query changes, and the next request is an unconditional 200 — the 304
  path is the steady state, not the general case.
- **No scheduled deletion sweep.** `since` catches closes — *given `state=all` above* — and
  closed ≠ deleted; only hard deletion and transfer-out are invisible, and both are rare. Owner
  decision — accepted risk.
- **A full-scan rebuild path still exists** for first build, schema change, and lost or corrupt
  cache. It is a rebuild path, not a deletion sweep.
- **W1 discharges #230.** `pick`'s ~12.4s full scan at ~6× the NFR floor is explicitly W1-gated;
  incremental sync is its fix. Rate accounting lands on #331 (the REST-point meter under-counts
  paged reads).

## 7. Concurrency — local, and a first-class requirement

**Multiple agents across multiple worktrees of one repo is the normal case here, and collision is
likely rather than theoretical** (owner, 2026-08-07). The shared-cache location makes this a
design requirement, not an edge case.

- **WAL mode and a busy timeout are configuration, not race-solving.** Without them concurrent
  access produces lock errors and corruption, not a rare interleaving. Configure deliberately.
- **Shared, never copied.** `<git-common-dir>` is shared across worktrees by construction, so
  there is nothing to distribute. Copying per-worktree would give each agent an unclaimed view of
  the queue and *break `working-branch`* — the exact collision the field prevents — plus N
  watermarks, N syncs, N× API cost, and drift. (The `.env` analogy does not carry: `.env` is a
  working-tree file; this is deliberately outside the working tree.)
- **Claim visibility is the payoff.** Sharing is what makes multi-agent claiming work at all.

**Deferred, deliberately:** races *against the backend* — two clients racing a claim or an
update. `[DECISION: note backend races, do not solve them | no observed occurrence, and a control
with no named expected yield is the ratchet the proportionality norm exists to stop | revisit
trigger: an observed collision | user can veto/override]`

## 8. Provider neutrality — scope

`[DECISION: design so as not to preclude a second provider | the backlog's tight coupling to
GitHub is acceptable today but should not become structural, and the cache is the one place the
seam is free — after it, seven readers would bind to a provider-shaped schema | user can
veto/override]`

**This decision is "avoid precluding" — explicitly NOT:**
- not "implement multiple providers today" — no second adapter is in scope;
- not "keep `backlog.md` around forever" — the markdown backend's retirement is unaffected.

**It reverses a recorded position.** `lib/backlog/migrate.py` states that re-import into a
non-GitHub backend is *"out of scope"* and that the export is *"a backup/inspection dump, not a
queried lock-in schema."* That statement is superseded for the cache schema specifically; the
export format's scope is untouched.

**Where the seam is and is not.** `lib/backlog/transport.py` is already "the sole egress to
GitHub" with a `Transport` interface, but it abstracts *how* you talk (subprocess vs HTTP), not
*what about* — its vocabulary is `get_issue(owner, repo, number)`. The domain seam is one level
up, at the cache. Honest limit: `encode.py`, `issuefmt.py` and `ids.py` carry GitHub-shaped
assumptions that a second provider would still have to face. The free part is the cache schema's
vocabulary — which happens to be the part with ten consumers attached.

## 9. Dependencies and open questions

**Prerequisites** (§2.1): **#529** blocks consumer 12 and is the only hard dependency. **#550**
is *not* a prerequisite — *observable beats stored* removed all three consumers that appeared to
need it — but the new `affected` field needs a write path from the same family, so it is a
dependency of §3 rather than of the restoration work.

**Open:**
- Whether #550 and #564 are duplicates (both describe a missing `revisit` write path). Worth a
  dedup pass before either is worked.
- Whether `pick` writes the intended branch name or claiming happens at branch creation
  (recommendation: the latter; `pick` stays advisory, which leaves the pick-window race
  unsolved but visible as two branches on one item).
- Whether janitor checks 6 and 7 are retired by this work or by a separate proportionality sweep.
- The exact `since` semantics on **non-GitHub** providers — a design-time verification, not a
  recall. GitHub's are now closed: verified live 2026-08-07 and written into §6, including the
  `state=all` requirement that the no-deletion-sweep decision turns out to rest on.
