---
artifact: build-plan
version: 2
scope: backlog-cache
depends_on:
  - artifact: cache-spec             # documentation/backlog-service-cache-spec.md (W1 requirements + spec)
  - artifact: data-model             # documentation/backlog-service-data-model.md §6 (cache schema), §7 (schema versioning)
  - artifact: security-model         # documentation/backlog-service-security-model.md §3 (F4 fetch-time auth, F5 content sensitivity)
  - artifact: nonfunctional-requirements  # documentation/backlog-service-nfr.md §3.3 (rebuild burst), §4 (latency), §5 (freshness), §6 (degradation), §8 (ops)
  - artifact: test-specifications    # documentation/backlog-service-test-specifications.md (QRY-1/3/5, SEC-8, OPS-*)
governed_by:
  # Every norm in each artifact gets a line — "that one doesn't apply" is an
  # interpretation, and it belongs where a reviewer can disagree with it.
  - artifact: data-model
    dispositions:
      - "Derived views are disposable and never authoritative — no gate reads a view to reach a verdict → conforms, and it is the LOAD-BEARING norm for this plan. Spec §5 states the binding form: W1 may never back a blocking verdict. Every consumer restored here is NOTE / WARNING / advisory level, so the constraint is satisfiable today; Chunk 06 carries the check that keeps it satisfiable, and the `regen-views-is-advice` ruling gives the precedence — a view writer emits no verdict, so the fail-closed half never attaches"
      - "Two stores, two lifetimes: shared committed answers vs per-clone gitignored nags and caches → conforms — the cache is per-clone and uncommitted, at `<git-common-dir>/prawduct/` beside the evidence store and the counts snapshot (spec §5). It sits on the cache side of the split by construction: inside `.git`, so there is no `.gitignore` contract to get wrong"
      - "A fact written by a newer schema than the reader is surfaced as a loud block, never silently dropped → inapplicable because the cache holds no facts, and the cache's own answer is already recorded elsewhere: `backlog-service-data-model.md` §7 says a `schema_version` mismatch triggers rebuild-from-GitHub, because a cache rebuild is always safe and never a data-loss migration. Opposite disposition, different subject, and NOT a decision this plan gets to make over again"
      - "`backlog_service_repo` selects which backlog store is authoritative; once set, `.prawduct/backlog.md` is frozen history → conforms, and this plan is what finally makes the frozen half harmless. Every consumer restored in Chunks 05–06 reads the cache, never the markdown file; the dormancy lines they replace exist precisely because reading frozen markdown looked like live state"
      - "Every issue written to the backlog store conforms to the issue standard's §1 title rules on every write path → conforms — Chunk 03 adds fields to the body block and to labels, and touches no title. `normalize_title(title, area)` is unchanged"
      - "Governance verdicts computed from the append-only fact ledger, never mutable model-written state → inapplicable because no verdict is computed here; this is the backlog adapter, not the Critic data plane"
      - "Facts are immutable and append-only; a state change is a new fact → inapplicable because nothing here writes to the evidence store"
  - artifact: architecture
    dispositions:
      - "Local-first: governance coordination is process-spawn + atomically-written files + the git object database, no third-party dependencies in the governance runtime; an opt-in backlog backend may take a network surface provided it stays off by default, degrades to the markdown backend, and carries no governance verdict → conforms on all four counts, and it is worth spelling out because SQLite is a new persistence shape here. (a) `sqlite3` is stdlib — no dependency enters. (b) The cache is not governance coordination: it carries no verdict (the data-model norm above), so WAL is not being introduced as a coordination substrate for governance. (c) Off by default — no cache exists until `backlog_service_repo` is set. (d) Degrades: an absent, corrupt, or schema-ahead cache rebuilds, and a consumer that cannot reach one reports unavailable rather than reporting clean"
      - "Every fact has one home; every other mention is a reference to it → conforms, and the cache needs its single-home story stated because it duplicates provider state by design. **The provider is the home. The cache originates nothing.** The rebuild-equivalence invariant (drop, rebuild, compare — spec §5) is the mechanical form of that claim, and Chunk 01 ships it as a test rather than a promise. A cache-only field would be a second home, which is why the invariant's failure mode is exactly 'a field that does not survive rebuild'. The norm also bit this plan during authoring — see the Requirements Confidence note on the corpus"
      - "Prawduct is written in Python and must never be specific to Python → conforms — the cache schema is prawduct-vocabulary text and dates; nothing in it is language-shaped. Spec §3's insistence that the schema speak prawduct rather than GitHub is the same discipline one axis over"
      - "Authority fails closed; advice fails soft → conforms — every cache reader is advice and fails soft, which the derived-views norm's precedence ruling requires. The one place fail-soft has teeth: soft must mean *reported* unavailable, never silently empty (`review-cycle.md`'s `null` is not a zero rule; NFR §6's read-degrades-never-hangs row). Chunk 01 establishes the distinction; Chunk 06 is where it would be lost"
      - "Goals and verification bind; prescribed method is advice → conforms. Binding: the consumer inventory of spec §2 is satisfied, the cache backs no blocking verdict, rebuild-equivalence holds, and the NFR §5 freshness rows hold. Advice: the chunk ordering, and which module each piece lands in. A builder who finds a better route takes it and records why"
      - "The plugin writes nothing into a governed repo except its own `.prawduct/` state, the shared evidence store, and the files it must reconcile → conforms — the cache lands inside `.git`, which is not the governed working tree, and the same place `lib/evidence.py` and `snapshot.py` already write"
      - "An independent reviewer never mutates the session it reviews → inapplicable because nothing here runs on the Critic data plane"
      - "Prawduct guides and reviews; it never implements — it writes no product code, config or tooling, and never re-implements what a product's own tooling already does → conforms, and it needs stating rather than skipping because this plan builds prawduct's first SQLite persistence layer, which is exactly the shape that looks like a violation. It is not one, on the norm's own terms. The norm's **Scope** line settles the first half explicitly: it governs prawduct-the-framework's relationship to the products it governs, and 'prawduct-the-product — this repo — is a product like any other and is built normally' (owner ruling 2026-07-29, which names conflating the two a category error). The cache is this repo's own backlog infrastructure; it is not written into, or on behalf of, any governed product. The **re-implementation corollary** is the half worth actually checking, and it is where a cache could genuinely offend — so: `sqlite3` is stdlib rather than a hand-rolled store; FTS5 is SQLite's own index rather than a written tokenizer; WAL and the busy timeout are the engine's concurrency primitives rather than a lock protocol; `PRAGMA user_version` is SQLite's native schema-version slot rather than a version table; and the one place a wheel was nearly reinvented — an age computation duplicated between `cache` and `cachequery` — was collapsed to one home during review rather than kept. What the cache does NOT re-implement is the provider: it never becomes a second source of truth, which is the rebuild-equivalence invariant's whole job"
  - artifact: security-model
    dispositions:
      - "Untrusted governance state — backlog, learnings, recalled memories, fetched references — is data, not instructions; content never carries authority to direct the agent or the framework → conforms, and it is LIVE here rather than theoretical. The cache stores issue bodies verbatim, Chunk 04 puts an FTS index over them, and Chunk 06 restores consumers that surface item text into agent-read findings (the Critic's walk already emits 'Backlog item appears resolved: [item text]'). The exposure is not new — `list` carries the same bodies today — but this work widens it from items a reader happened to open to every open body, indexed. The treatment is restated at each restore site in Chunk 06 rather than assumed to be inherited"
      - "A governed product's content never leaves that product's own repository and owner; the backlog adapter reaches exactly the repo named in `backlog_service_repo` → conforms, and the single-repo scoping decision in Chunk 01 strengthens it: the cache holds items from exactly one repo, so there is no cross-owner content to leave anywhere. No new egress site is added — sync reaches the provider only through `transport.py`"
      - "A destructive or irreversible operation requires explicit owner approval at the OPERATION level → inapplicable because nothing here is destructive. The rebuild path drops and re-derives a cache whose every row exists in the provider; losing it costs a re-fetch, not data. This is exactly the property that lets `backlog-service-data-model.md` §7 answer a schema mismatch with rebuild rather than migration"
  - artifact: nonfunctional-requirements
    dispositions:
      - "Proportionality ratchets both ways: a control that has fired repeatedly and never produced a blocking finding is removed by default; adding a control names the yield it expects AND emits that yield observably → conforms, and this is the second load-bearing norm. It cuts both ways here and the plan honours both directions. **Removal:** three enumerated consumers are retired rather than restored (spec §2.1 — `revisit-due`, janitor checks 6 and 7), which is the ratchet running down; and Chunk 05 retires the whole claim / `claimed_at` / TTL-reap mechanism, which is the ratchet running down on a *control* rather than a check — a stored expiry policy replaced by an observable one, per spec §3. **Addition:** every consumer restored in Chunks 05–06 is a control being re-added, so each names its expected yield in the same edit that restores it. `tags` is held to the same standard, and `backlog-service-data-model.md` §6 states the schema-level form of the same rule — every column is a Q-projection, no dead fields"
      - "Review wall-clock is a P0 constraint → conforms, and the plan is shaped by it. Six chunks means six reviews, which is the cost this norm asks to be deliberate about; the alternative of three fat chunks trades run-count for unit-cost on a chunk too large to review in one pass, which is the worse trade. Chunk 06's `cumulative-final` is one review, not a `final` plus a `cumulative`"
      - "State-file growth past its size threshold is an advisory warning, never a hard block → inapplicable because the cache is not a state file and has no size threshold; it is uncommitted and rebuildable, so growth costs disk, not merge conflicts or review payload"
  - artifact: api-contract
    dispositions:
      - "Persisted data that outlives a plugin version is independently schema-versioned with forward-incompatibility detection → conforms — the cache carries `schema_version` and detects a mismatch, per `backlog-service-data-model.md` §7. The norm's 'a schema-ahead fact blocks loudly' clause is scoped to facts and does not reach here; the cache's detection resolves to rebuild-and-report. An earlier draft of this plan proposed amending the norm to say so, which was wrong twice over — the question was already answered in the backlog-service data model, and `snapshot.py` already ships the behaviour"
      - "Exit codes are the contract; errors are attributed, never raised as stack traces across the boundary → conforms — cache commands follow the existing scheme, and `sqlite3.Error` is caught and returned as a `status`/`reason` dict per the preferences error-handling norm, never allowed to escape"
      - "Additive-first evolution: flag names, exit-code meanings, and `--json` keys are never repurposed; readers tolerate unknown keys → conforms on the additions, WITH ONE NAMED REMOVAL a reviewer should weigh rather than skim. The additions are clean: Chunk 03 adds `affected`, `tags`, and `working-branch` to the body block, which is already additive-only-forever by `Block.fields` preserving every unknown key in source order (ENC-4), and which `backlog-service-data-model.md` §7 binds explicitly — a genuine semantics change mints a new key, never a `v:` reinterpretation. No existing key changes meaning. **The removal:** Chunk 05 deletes the shipped `claim` / `unclaim` ops and `pick`'s `--claim` / `--claim-ttl` flags (owner ruling). The norm forbids REPURPOSING and this is not that — no removed name is reused for anything, `claimed_at` keys already written stay readable as unknown keys, and exit code 4 keeps its `conflict` meaning through `update`'s CAS path. But a removal from a released CLI surface is a breaking change the norm's letter does not cover, and the argument for it is the owner's: `working-branch` ships in the SAME release, and every in-tree consumer of the removed ops is retired in the same chunk. An out-of-tree caller scripting `prawduct-hook backlog claim` breaks with no deprecation window — accepted, because the op is release-current rather than long-established and the release notes carry it"
  - artifact: project-preferences
    dispositions:
      - "Sync-only architecture (no `async def`, no `asyncio`) → conforms — concurrency is SQLite WAL plus a busy timeout, which is DB-lock based, exactly as the preference anticipates. Test-enforced"
      - "Error handling: return-value based; `lib/` functions return `status`/`reason` dicts, exceptions escape only at boundaries → conforms, and it is the specific discipline `sqlite3` most invites violating"
      - "`from __future__ import annotations`, PEP 604 annotations, test location, class-based grouping, naming → conforms — test-enforced, nothing here asks for an exception"
      - "pytest-xdist `-n auto --dist loadfile` with same-directory state grouping → conforms, and it constrains the concurrency tests specifically: `loadfile` puts one file's tests on one worker, so a test asserting two writers do not corrupt the store must spawn its own processes. Relying on xdist to supply the contention would produce a test that passes because nothing concurrent happened"
      - "Runtime dependency (opt-in): the `gh` CLI, required only once `backlog_service_repo` is set → conforms — sync reaches the provider only through `transport.py`, which remains the sole egress"
      - "Backlog filing: fix, don't file — file only when orthogonal AND medium+ → conforms — the backlog corrections this plan implies (#550's reshaping, #564's disposition) are done in-chunk rather than filed as new items"
      - "Feature branch for medium+ work; PR creation and merge both wait_for_user; merge commit never squash → conforms — this is L-effort work on `feat/backlog-cache`"
last_validated: 2026-08-07
---

## Requirements Confidence

**Level:** High

**Why:** Problem, success, and scope are each statable in one sentence and all three are already
written down: seven backlog readers went dormant at the Issues cutover and one persisted cache
serves them all (#621); success is spec §2's fifteen-query inventory with §2.1's restorable/retired
split; scope excludes a second provider adapter (spec §8). The consumer sweep behind §2.1 was
exhaustive with file pins, not a sample — the specific thing that usually makes a persisted format
Medium.

**A correction made during authoring, recorded because it is the plan's main risk of recurring.**
The first draft cited only `backlog-service-cache-spec.md` and proposed amending an
`api-contract.md` norm to cover the cache's schema-versioning. Both were wrong: W1 already has a
reviewed design corpus — the cache's exact table schema (`data-model.md` §6), its schema-versioning
answer (§7), two security findings written about it specifically (F4, F5), NFR freshness and
latency rows (§§4, 5), and a test catalogue (QRY-1/3/5, SEC-8, OPS-1..3). The cache spec is
deliberately a *delta* on that corpus and says so in its own header. Running "has this repo already
decided it?" against `.prawduct/artifacts/` and not against `documentation/` is what produced a
proposed amendment to a decision that already had a home. **Every chunk below cites the corpus
rather than re-deriving it**, and a builder who finds themselves designing a table column should
check §6 first.

**Open assumptions / unknowns:**

- ~~`[ASSUMPTION: W1 adds working-branch and does NOT retire the existing claim / claimed_at /
  TTL-reap machinery]`~~ — **RESOLVED, owner ruling 2026-08-07: W1 DOES retire it.** Spec §3's
  "`working-branch` replaces the claimed-by concept" is literal. The reasoning is the one the
  assumption did not weigh: **W1 ships as a single atomic release**, so the interval in which two
  mechanisms for one concept coexist is a handful of unreleased commits that no operator ever runs
  — maintaining both across it is work spent on a state that never exists in the field. Chunk 05
  grows accordingly and `pick`'s contract changes there; the scope is enumerated in that chunk.
- `[ASSUMPTION: tags ships in Chunk 03 with a named consumer (a `--tag` filter on
  `/prawduct:backlog list` / `find`), not as a bare field | MED impact | user can override]` —
  `tags` appears in none of spec §2's fifteen consumer queries, and spec §3 forbids anything gating
  on it. `data-model.md` §6's every-column-is-a-Q-projection rule (the retired-`git_sha`
  precedent) would reject a `tags` column with no query behind it. So `tags` either ships with the
  filter that consumes it or it leaves W1.
- `[ASSUMPTION: janitor checks 6 and 7 are retired by this work rather than by a separate
  proportionality sweep | LOW impact | user can defer]` — spec §9 leaves this open. Retiring them
  inside Chunk 06 costs almost nothing and avoids leaving two dormancy lines behind after the thing
  they waited for has landed.
- `[ASSUMPTION: pick stays advisory — claiming happens at branch creation, not by pick writing the
  branch name | MED impact, RAISED by the claim retirement | user can override]` — spec §9's own
  recommendation. It leaves the pick-window race unsolved but visible as two branches on one item,
  which spec §7's deferral of backend races already accepts. **The retirement makes this assumption
  carry more weight than when it was written:** with `claim` gone, `pick --claim` gone, and nothing
  auto-populating `working-branch`, W1 has *no* automatic claim of any kind. An actor who picks and
  forgets to record the branch is invisible to the next picker. That is the intended trade — the
  claim it replaces was itself soft, and a stamp nobody refreshes was never a lock — but it is now
  the only thing standing between two actors and one item, so it should be a decision rather than a
  side effect of the retirement.
- **Unverified, by design:** the exact `since` semantics on the GitHub REST issues endpoint. Spec
  §6 says to verify at design time rather than from recall; Chunk 02 carries it as a `verify-api`
  step rather than as an assumption.

**What would raise confidence:** the one assumption that changed a chunk's size is answered. What
remains is the `pick`-advisory question above, which changes no chunk's size but does change what
W1 promises about double-picks.

## Status

- [x] Chunk 01: Cache store — schema, rebuild, visible age, and the rebuild-equivalence invariant
- [ ] Chunk 02: Incremental sync — cursor watermark and conditional revalidation
- [ ] Chunk 03: The three new domain fields and their write path
- [ ] Chunk 04: The consumer query surface — grouping, FTS, alias resolution
- [ ] Chunk 05: Code consumers — the norm probes, `pick` off the cache, and the end of `claim`
- [ ] Chunk 06: Prose consumers, retirements, and the end of the dormancy advisory

Context: **Chunk 01 shipped `05d09f3`** (Critic `rev-20260807T145538Z`: 1 blocking + 5 others, all
fixed; verify-resolutions clean). Suite 3929 passed / 7 skipped. Rebuild-equivalence verified against
the live 450-item backlog — build → drop → rebuild → compare identical on every domain field; warm
read 46ms against NFR §4's <500ms. Tracking item **#621**; **#230** is discharged by Chunks 02 + 05.

**Next up: Chunk 02**, which starts with its `verify-api` step (`since` semantics) *before* any fake
is built.

**#529 blocks one consumer, not this plan.** #621's `blocked-by #529` edge was **dropped by owner
ruling (2026-08-07)**: a blocker that suppresses a whole item from ranked ready-work because one of
fifteen consumers waits on it is a false blocker. What #529 actually blocks is consumer 12, a
sliver of Chunk 06, and that carve-out is written down in that chunk where the work is. #621 is
`stage: ready` and now surfaces by rank rather than only by name.

**The `claim` machinery is retired by this work** (owner ruling, 2026-08-07 — see Requirements
Confidence). It lands in Chunk 05, code and prose together.

Next: Chunk 01.

## Scaffolding

### Dependencies

None added. `sqlite3` is stdlib — which is what keeps the local-first norm's
no-third-party-dependencies clause satisfied, and not an accident of convenience: a cache needing a
driver would have made the norm the deciding constraint on the storage choice.

### Build & Test Configuration

Existing: `pytest`, xdist `-n auto --dist loadfile`. Cache tests are **flat files under `tests/`,
named `test_backlog_cache*.py`** — the repo's convention is one file per capability
(`test_backlog_query.py`, `test_backlog_encode.py`, …), enforced by
`tests/preferences/test_test_location.py`, and there is no `tests/backlog/` package. (An earlier
draft of this plan said there was; corrected on inspection rather than discovered mid-build.)
**The concurrency tests are the exception that needs stating:** `--dist loadfile` schedules one
file's tests onto one worker, so a test asserting that two writers do not corrupt the store must
spawn its own processes.

Test names below cite the existing catalogue in
`documentation/backlog-service-test-specifications.md` where one already covers the case. New tests
are named only where the catalogue has no row — the cache spec's three new fields and the consumer
restorations, which postdate it.

### Verification Strategy

Beyond tests, each chunk is exercised the way its consumers will be. Chunks 01–02: build the cache
against this repo's real backlog (178 open items), drop it, rebuild, diff — the invariant is also
the smoke test — and measure the warm read against NFR §4's <500 ms accelerated target. Chunk 04:
run each restored query against the real corpus and read the answers, because a query returning a
plausible wrong set is exactly what a unit test with three fixtures does not catch. Chunks 05–06:
run `/prawduct:janitor` and a Critic review on a branch with real changes and confirm the restored
checks produce findings a reader would act on — "emits its yield observably" is not satisfied by
the check merely running.

## Project Structure

```
plugin/lib/backlog/
├── cache.py       # new — store: open, schema, rebuild-on-mismatch, upsert, WAL config
├── cachequery.py  # new — the consumer query surface over the store
├── sync.py        # new — cursor watermark, conditional revalidation, full rebuild
├── encode.py      # + affected / tags / working-branch decode; − claimed_at
├── transport.py   # + `since` on list_issues
├── core.py        # + the three fields' write path (SEC-2 allowlist); − claim / unclaim / TTL
├── cli.py         # − claim / unclaim ops, − pick --claim / --claim-ttl
└── query.py       # pick reads the cache; excludes on working-branch; − _claim_eligibility
```

### Module Boundaries

`cache.py` owns the connection and the schema and knows nothing about GitHub. `sync.py` is the only
module holding both a transport and a store. `cachequery.py` reads the store and never writes it.
Consumers (probes, skills, `pick`) call `cachequery.py` and never open a connection themselves —
the same shape that makes `transport.py` the sole egress.

## Build Chunks

### Chunk 01: Cache store — schema, rebuild, visible age, and the rebuild-equivalence invariant

- **Description:** The thin vertical slice: provider → decode → store → read → one consumer. Ships
  the schema from `data-model.md` §6 (`item`, `item_fts`, `comment`, `relationship`, `cursor`) —
  **taken from there, not designed here** — the connection discipline (WAL, busy timeout,
  `schema_version`), the full rebuild path, and exactly one consumer query (consumer 1: all open
  items with id, title, body).

  `briefing_counts` stays where it is. `data-model.md` §6 lists it as a cache table, but the slice
  shipped it as the standalone JSON file `snapshot.py` owns, and spec §5 places the SQLite cache
  *beside* the counts snapshot rather than absorbing it. Leaving it alone keeps the session-start
  read in-process and network-independent (BLOCK-5), which folding it into SQLite would put behind
  a connection open. Record the divergence from §6's table list rather than letting it read as an
  oversight.

  Four properties are established here because they are cheap now and expensive to retrofit.
  **(a) Rebuild-equivalence** — drop, rebuild, compare; any difference is a cache-only field, which
  is data loss on rebuild and a second home for a fact (spec §5). The same invariant is the
  provider-adequacy test, so no separate portability suite is ever needed. **(b) Visible age** —
  every cache-served payload carries a non-null `fetched_at`-derived age (NFR §5). **(c)
  Unavailable is not empty** — a consumer that cannot reach the cache reports unavailable; it never
  returns an empty set that reads as a clean bill of health (NFR §6 read-degrades-never-hangs).
  **(d) Schema-ahead rebuilds and reports** — per `data-model.md` §7, not a fresh decision.
- **Depends on:** none
- **Artifacts consumed:** `documentation/backlog-service-cache-spec.md` §§2, 5, 7;
  `documentation/backlog-service-data-model.md` §§6, 7;
  `documentation/backlog-service-security-model.md` §3;
  `documentation/backlog-service-nfr.md` §§5, 6, 8
- **Deliverables:** new `plugin/lib/backlog/cache.py`; the store at
  `<git-common-dir>/prawduct/backlog-cache.sqlite3`, resolved the way `snapshot.snapshot_path`
  already resolves so the path rule keeps one home; full rebuild driven through the existing
  `query._all_issues` + `encode.decode_item` path; consumer 1's query
- **Tests:** catalogue — **SEC-8** (reconciled, see the decision below) and **OPS-2** (the cache is a
  new local artifact, so its disk-not-dollars row is this chunk's to discharge, and
  `TestCachePath` does). **OPS-1 and OPS-3 are DESCOPED from this chunk, not dropped:** OPS-1
  ("cost is O(1) in project count") onboards an Nth project and asserts the recurring-cost surface,
  and OPS-3 ("no server required for correctness") exercises the full CRUD + query + `pick` surface
  with no daemon running. Both are portfolio- and deployment-scope assertions about the whole
  adapter; a store module cannot discharge either, and writing something cache-shaped under their
  names would be exactly the catalogue-row-describing-a-check-nobody-built defect this plan keeps
  naming. They belong to the surface Chunk 05 completes (`pick` off the cache) — carried there
  rather than left implied here. New — schema
  creation, schema-ahead discard-and-report, absent-store rebuild, corrupt-store rebuild,
  `sqlite3.Error` returned as a `status`/`reason` dict rather than raised, rebuild-equivalence over
  a fixture corpus, and a concurrency test spawning two writer processes (see the xdist note)
- **Acceptance criteria:** `uv run pytest -q` passes; against this repo's live backlog, build →
  drop → rebuild → compare is identical on every domain field; a store deleted mid-read produces
  `unavailable`, not `[]`; every cache-served payload carries a non-null age

  `[DECISION: W1's cache holds items from exactly one repo — the one named in
  `backlog_service_repo` | security F4 is the reason. The cache is `git-common-dir`-keyed and can
  in principle hold items from several repos, but authorization happens at FETCH time by the
  fetching identity, not at READ time by the reading identity — so a broad-identity fetch could
  later be read by a narrower one in the same clone. Spec §7's "shared, never copied" decision,
  which is right for the multi-agent claiming story, makes that exposure larger rather than
  smaller, and the spec does not engage F4 at all. Scoping the store to one repo makes the finding
  VACUOUS rather than mitigated: with no cross-owner entries there is no cross-boundary read to
  revalidate against. It costs nothing this plan wanted — `relationship` is already within-repo
  only and cross-repo blockers are already read live (`data-model.md` §6, and Chunk 05), and Q4
  cross-project rollup was never cache-served. If a later release wants a multi-repo cache, F4's
  full rule — entries scoped to the fetching identity's access set, cross-repo entries revalidate
  on read — comes back into force and is a design change, not a config flag | user can
  veto/override]`

  `[DECISION: SEC-8's mechanism is superseded; its threat is not | SEC-8 tests that
  `/prawduct:doctor` flags an un-ignored cache, on the premise that the cache is a working-tree
  file where gitignore is the only defence and "gitignore is not enforcement." Spec §5 puts the
  store inside `.git`, where it cannot be committed at all — `add -f` and a differing global ignore
  both stop being reachable. The defence becomes structural, so the doctor check has nothing left
  to catch and would be a control with no expected yield, which the proportionality norm removes by
  default. F5's other half is untouched and still binds: the cache is as sensitive as its
  most-sensitive stored body, it has no access control at rest, and the export path carries the
  same sensitivity as its source repo | user can veto/override]`

  `[DECISION: the `item` table ships WITHOUT `assignee` and WITHOUT `reviewed`, both of which
  `data-model.md` §6 lists | §6's own binding rule is that every column is a Q-projection with no
  dead fields, and the retired-`git_sha` row is the precedent for removing one. Each of these lost
  its serving query, for a different reason, and neither loss was visible when §6 was written.
  **`reviewed`** served "TF2 (`reviewed` date-range)" — consumer 10; spec §2.1 moved consumer 10
  onto the provider's `updated_at` under *observable beats stored*, and no other consumer reads it.
  **`assignee`** served ready-work's claimed-item exclusion — which is the machinery TODAY'S OWNER
  RULING retires (Chunk 05). After that, `pick` excludes on `working-branch` (Chunk 03) and nothing
  queries the assignee at all. A human assigning in the GitHub UI is still free to; prawduct simply
  stops reading assignment as meaning. Keeping either column would ship exactly the dead field §6
  forbids, and a dead column in a persisted schema is the cheap-now/expensive-later shape the
  lock-in rule warns about. `kind` is likewise absent — §6 omits it and none of the fifteen
  consumer queries asks for it, so its absence is confirmed rather than corrected. The columns that
  DO survive each name a consumer: `id`/`title`/`body`/`status` (1, 6, 7, 14), `stage` (11), `area`
  (3, 4, 8, 9), `created_at` (2 — the provider timestamp, replacing §6's `added`, which is a block
  field with no write path), `updated_at` (10, 15), `effort`/`impact`/`source` (`pick` ranking and
  `list` filters, Chunk 05), `etag` (Chunk 02 revalidation), `fetched_at` (visible age) | user can
  veto/override]`

  SEC-8's mechanism has **two** homes, and both are reconciled in this chunk: the catalogue row in
  `documentation/backlog-service-test-specifications.md`, and NFR §8's *operational sliver* row,
  which states the same `/prawduct:doctor` gitignore check as one of the two residual ops burdens
  (its `Local artifacts are disk, not dollars` row in §2 and the §7 capacity row also say
  "gitignored"). Leaving either behind is the second-home defect this plan keeps naming.
  **As built — two module placements moved earlier than this plan put them**, both to honour the
  stated module boundary rather than to widen scope. `cachequery.py` was listed as a Chunk 04
  deliverable, but the boundary says consumers never open a connection themselves; shipping
  consumer 1's query inside `cache.py` would have created the first violation of a rule this plan
  spends a paragraph on, so `cachequery.py` exists from Chunk 01 with exactly one query and grows
  in Chunk 04. `sync.py` was listed as Chunk 02's, but Chunk 01 needs *something* to drive the
  rebuild and the boundary reserves transport-plus-store to `sync.py` — so it exists with only the
  full-rebuild path, which is precisely what Chunk 02's own text assumes ("the Chunk 01 rebuild
  stays as the rebuild path"). One further correction: `query._all_issues` became public
  `query.all_issues`, because `sync.py` is a legitimate second caller and importing another
  module's underscore-private is worse than the rename.

  **Two Critic findings changed the code rather than the record.** `replace_items` now writes the
  rows *and* the scope's cursor in **one** transaction — an earlier shape committed them separately
  while the docstring claimed otherwise, which would have handed Chunk 02 a satisfied-looking
  guarantee its stated correctness argument depends on. And `cache.store_status` was deleted: a
  public function with no caller, no test and no deliverable, which also opened its own connection
  against the module boundary. `cache.age_seconds` went with it for the same reason, leaving one
  home for the age computation.

  **A defect the fixture corpus could not have caught, found in live verification.** Consumer 1's
  query first read `status = 'open'` literally, which silently drops `submitted` and `in-progress`
  items — the live ones a PR reviewer most wants. It now uses `encode.OPEN_STATUSES`, derived from
  the status encoding's single source of truth, so a new sub-state is included the day it is added.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. SEC-8 reconciled in the test-specification catalogue **and** in NFR §8's operational-sliver
     row (plus the §2 / §7 "gitignored" mentions); the `briefing_counts` divergence from
     `data-model.md` §6 recorded there
  3. `/prawduct:critic` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

### Chunk 02: Incremental sync — cursor watermark and conditional revalidation

- **Description:** Replace the full scan with the `cursor(scope, since)` watermark `data-model.md`
  §6 already specifies. Fetch only items updated since the cursor, upsert idempotently, overlap the
  window by a margin so a boundary write is re-read rather than missed. Timestamps come from server
  values, never the local clock. The Chunk 01 rebuild stays as the rebuild path — first build,
  schema bump, corruption — and is explicitly not a deletion sweep; per spec §6 there is no
  scheduled deletion sweep at all, since `since` catches closes and hard deletion and transfer-out
  are accepted-risk invisible (owner decision).

  **The ordering constraint is the whole correctness argument:** the cursor advances only after the
  upserts it covers have committed, in the same transaction. Advancing first and upserting second
  loses every item in the window on a crash, and no actor is guaranteed to re-run that specific
  transition — the case where idempotent-re-run convergence is not enough and the write has to be
  atomic instead.

  **The `etag` column earns its keep here.** NFR §5's never-silently-stale row requires that no
  cache read be served past its validator without a revalidation option, and `data-model.md` §6
  carries `etag` as the conditional-request column that makes it possible. Sync is where it is
  written; Chunk 05 is where a decision-driving read consumes it.
  **Four demoted observations carried from Chunk 01's verify pass** — none is owed work, all ride
  this chunk's commit if you touch the code anyway. (a) `full_rebuild`'s envelope carries both
  `since` and `fetched_at` with the same value and nothing reads `since`; this chunk either gives it
  a reader or drops it, since a channel produced and never consumed is a defect. (b)
  `test_age_falls_back_to_the_oldest_stamp_not_the_newest` calls `cache.oldest_fetched_at` directly
  rather than going through `cachequery._freshness`, so it no longer exercises the fallback its name
  describes — and that fallback has no production path at all until this chunk's upsert-only sync
  exists, which is exactly when it becomes testable end to end. (c) Chunk 01's `Tests:` enumeration
  does not name the rows-and-watermark atomicity test, though the DECISION block records it. (d) The
  verify dispatch inferred chunk 02 from Status because it carried no `--chunk`; pass `--chunk 02`
  on this chunk's review.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `documentation/backlog-service-cache-spec.md` §6;
  `documentation/backlog-service-data-model.md` §6;
  `documentation/backlog-service-nfr.md` §§3.3, 5
- **Deliverables:** new `plugin/lib/backlog/sync.py`; `since` support on
  `transport.GhTransport.list_issues`; the cursor stored with the cache, uncommitted, its absence
  meaning full rebuild
- **Tests:** catalogue — **QRY-5** (sync/cursor); new — cursor advance-after-commit under a
  simulated crash between fetch and upsert, boundary-overlap re-read, idempotent double-upsert. All
  clock-dependent tests inject one clock shared by every actor in the scenario; a single real-clock
  participant turns a fixed-timestamp test into a scheduled failure at stamp-plus-TTL wall time
- **Acceptance criteria:** a sync following a no-op interval fetches zero pages; an item edited
  since the last sync appears with its new state; killing the process between fetch and commit
  loses nothing on re-run; a rebuild of this repo's backlog paces under the core budget as NFR §3.3's
  cache-rebuild row expects
- **Foreign API:** github-rest-issues (`GET /repos/{owner}/{repo}/issues`, `since`)
- **Done when:**
  0. verify-api — confirm what `since` actually filters on (updated-at vs created-at), whether it
     interacts with `state`, whether closed items are returned, and the `etag`/304 behaviour on the
     list endpoint. Read the endpoint's behaviour against the live repo; do not draft against
     recall. The fakes are built after this step, never before
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: The three new domain fields and their write path

- **Description:** `affected` (structured path list, no prose), `tags` (folksonomy, multi-valued,
  maps to labels), and `working-branch` (a pushed ref, repo-qualified) — decode, cache columns, and
  the write path they need. **These three are the cache spec's addition to `data-model.md` §6, the
  one place this plan extends the corpus rather than consuming it**, so §6's table gains three
  columns and the every-column-is-a-Q-projection rule applies to each.

  This chunk produces spec §2.2's one genuine capability gain: with `affected` indexed, consumers 1
  and 4 become a set intersection against the changed-file set instead of a reviewer reading item
  text and inferring.

  Three constraints ride along. **`working-branch` must mean a pushed ref** — an unpublished branch
  is an invisible claim, which fails at the only job the field has — and **must name the repo**,
  because `backlog_service_repo` can differ from the code repo. **Nothing may ever gate on `tags`**;
  that binding rule is what makes synonym drift harmless rather than corrosive, and it must be
  stated before someone builds a check on them. And **`tags` ships with its consumer** or it does
  not ship — see the open assumption.

  The write path is the #550 family. Applying spec §2.1 shrinks #550 rather than satisfying it:
  `reviewed` and `revisit` drop out entirely (consumer 10 takes its date signal from provider
  `updated_at`; the revisit probe is retired), leaving `refs` and `closed-by` plus the new fields.
  Record that reshaping on the item here — an item whose scope silently moved is the same defect as
  a fact with two homes.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `documentation/backlog-service-cache-spec.md` §3;
  `documentation/backlog-service-data-model.md` §§6, 7
- **Deliverables:** `affected` / `tags` / `working-branch` in `plugin/lib/backlog/encode.py`
  (`decode_item` and the `Block` accessors); the three cache columns and the `affected` index; the
  write path in `plugin/lib/backlog/core.py` — which means **naming all three in the SEC-2
  mass-assignment allowlist** (`_UPDATE_FACETS`), a deliberate widening of a security control that
  should read as a decision rather than as a diff nobody mentioned; the `--tag` filter on `list` in
  `plugin/lib/backlog/query.py` and `plugin/lib/backlog/cli.py`
- **Tests:** new (the catalogue predates these fields) — round-trip through the block for each
  field; an unpublished or repo-unqualified `working-branch` rejected at the write; `affected`
  rejects prose; rebuild-equivalence still holds with all three populated, which is the Chunk 01
  invariant becoming load-bearing rather than trivial
- **Acceptance criteria:** all three fields survive a write → drop → rebuild cycle; a real item
  carrying an `affected` list intersects correctly against a real changed-file set; `list --tag`
  returns the tagged items
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `data-model.md` §6's table updated with the three columns and each one's serving query
  3. #550 updated to its reshaped scope (`refs`, `closed-by`, and the new fields; `reviewed` and
     `revisit` removed with the reason), via `/prawduct:backlog update`
  4. `/prawduct:critic` run and blocking findings resolved
  5. Committed and chunk marked `[x]` in Status

### Chunk 04: The consumer query surface — grouping, FTS, alias resolution

- **Description:** The rest of spec §2's query union: grouping and counting by `area`, text search
  scoped to an area (the FTS requirement), creation-time filtering, the two `updated_at` date
  predicates, and id resolution through the alias table including dead items.

  **Alias resolution is the real defect this chunk fixes**, not a convenience. Spec §4 rule 3: all
  resolution goes through the alias table; nothing parses an id string as live provider
  coordinates. #618's block stores `related: [brookstalley/prawduct#249, …]`, and parsed as
  owner/repo/number at read time a migration must rewrite every edge — with a missed rewrite
  breaking the graph silently. Consumers 5, 7 and 14 all depend on this. The machinery exists
  (`id_aliases`, the `id:PFX` alias label, the label↔block self-heal in `core.py`, built for the
  markdown→Issues cutover); it needs pointing at provider ids rather than legacy PFX ids. Aliases
  are tagged (`github:owner/repo#n`), the live ref untagged — the asymmetry is what stops
  resolution degrading into shape-parsing, since `owner/repo#number` is not GitHub-unique (GitLab
  and Gitea share the shape, and they are precisely the self-hosted options motivating neutrality).

  FTS is the read-your-writes path GitHub search lacks (`data-model.md` §6), which is why it is
  cache-served rather than delegated.
- **Depends on:** Chunks 01, 03
- **Artifacts consumed:** `documentation/backlog-service-cache-spec.md` §§2, 4;
  `documentation/backlog-service-data-model.md` §§5, 6
- **Deliverables:** new `plugin/lib/backlog/cachequery.py` covering the enumerated union; the FTS
  index; alias resolution repointed onto provider ids in `plugin/lib/backlog/ids.py`
- **Tests:** catalogue — **QRY-3** (`search` cache-served, read-your-writes on a just-written item);
  new — one test per enumerated query, each asserting its result SET is non-empty where the fixture
  makes it so, because a query test that only checks shape goes green when nothing was looked at;
  alias resolution through a two-hop chain, through a dead item, and for an id resolving to
  nothing; a `related:` edge surviving a simulated provider migration untouched
- **Acceptance criteria:** every query in spec §2's union answerable from the cache alone; a
  historical `#249` citation still resolves after its record carries a new live id; each query run
  against this repo's real corpus returns an answer a reader would accept
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 05: Code consumers — the norm probes, `pick` off the cache, and the end of `claim`

- **Description:** Bind the code-side consumers, and retire the mechanism `working-branch` replaces.
  Two norm probes come back and one is retired:
  `probe_dead_why` (consumer 14 — id → is-dead, alias-resolving) and `probe_stalled_transition`
  (consumer 15 — id → live? + date floor, from provider `updated_at`) lose their `post_cutover`
  early return; `probe_revisit_due` is **retired, not restored**. The retirement is not a scoping
  convenience: `revisit:` encodes *this exception was granted until date X*, which is intent rather
  than state, and two exceptions granted the same day with different clocks are indistinguishable
  to any age-based query — so no query could substitute for it. It is retired because exception
  clocks already migrated to prose in the governing artifact, walked by the janitor's Norm Health
  sweep, and `nonfunctional-requirements.md`'s own live exception records that decision. A
  markdown-era vestige.

  `pick` then reads its candidate set from the cache instead of scanning, which discharges **#230**
  (~12.4s at ~6× the NFR floor, explicitly W1-gated). **Two things do not change, and the second is
  negative-asserted in the catalogue.** Rate accounting stays on **#331** — and before claiming a
  rate ceiling was the constraint, check whether serial round-trip latency already capped
  throughput below it. And the blocker fan-out still reads live: a cross-repo blocker must be
  judged from live state, `data-model.md` §6 scopes `relationship` to within-repo for exactly this
  reason, and **QRY-2** asserts the negative directly — a stale cache must not let a blocked item
  be picked. That is also the sharpest instance of the derived-views norm in this plan: `pick` is
  the closest thing here to a decision-driving read, so it is where the never-silently-stale
  revalidation from Chunk 02 has to actually fire.

  **The claim mechanism is retired here, whole** (owner ruling — Requirements Confidence). Removed:
  `core.claim` / `core.unclaim` / `DEFAULT_CLAIM_TTL_SECONDS`; `query._claim_eligibility`, the
  reap-vs-free ranking tier, and the `_why` claim clauses; the `claim` / `unclaim` CLI ops and
  `pick`'s `--claim` / `--claim-ttl` flags; `encode.Block.claimed_at` and its `decode_item` row;
  `tests/test_backlog_claim.py`. **The prose goes in this chunk with the code, not in Chunk 06** —
  `plugin/skills/backlog/SKILL.md`'s `accepted-by:` section, its `allowed-tools` grant, the
  `list --include-claimed` flag and the pick-exclusion rule, plus `adapter-mode.md`'s claim/unclaim
  op mapping and its `--assignee none` exclusion. Chunk 06 owns prose that *restores dormant
  consumers*; splitting this one across that boundary would leave a commit where the CLI has no
  `claim` op and the skill still grants and documents one.

  Three things the retirement deliberately does **not** do, each because a norm says otherwise.
  **Exit code 4 stays** — `claim_conflict` retires as a *value*, but code 4 is `conflict` and
  `update`'s optimistic-CAS path still returns it; retiring one producer of a contract code is not
  repurposing the code, which is the thing api-contract's additive-first norm forbids. **No data
  migration** — `claimed_at` stamps already written into issue bodies become unknown keys, which
  `Block.fields` preserves in source order forever (ENC-4). They are inert, and rewriting bodies to
  delete an inert key is a write with no yield. **`assignee` becomes unwritable by prawduct** — it
  was reachable only through `claim` (core.py's SEC-2 allowlist comment says so), so it returns to
  native/protected. GitHub's own UI still assigns; prawduct stops reading assignment as meaning,
  which is the point of moving the signal to a branch.

  `[DECISION: pick excludes an item whose `working-branch` is populated — full stop. No TTL, no
  reap tier, and no read of the branch's commit history | the tempting translation of the old
  predicate ("unassigned ∨ claim past TTL") is to age the *branch* instead of the stamp, and it is
  wrong twice. It puts a git call — against a ref in a possibly-different, possibly-unfetched repo —
  inside `pick`'s hot path, which is the NFR §4 budget this very chunk exists to fix (#230, ~12.4s
  at ~6× the floor); and it reintroduces a stored expiry policy under a new name, when spec §3's
  whole argument for `working-branch` is that *staleness becomes observable rather than stored*.
  Observable means the signal is available to a reader, not that `pick` must consult it: `pick`
  surfaces the branch name in `why` and the human judges whether a three-week-old branch is
  abandoned. The asymmetry backs it — a wrongly-excluded item costs one `--include-working` flag, a
  wrongly-included one costs two people on one item | user can veto/override]`
- **Depends on:** Chunk 04
- **Artifacts consumed:** `documentation/backlog-service-cache-spec.md` §§2.1, 3, 6;
  `documentation/backlog-service-nfr.md` §§4, 5
- **Deliverables:** `probe_dead_why` and `probe_stalled_transition` in
  `plugin/lib/norm_probes.py` reading `cachequery`; `probe_revisit_due` removed along with its
  registry row; `pick` in `plugin/lib/backlog/query.py` sourcing candidates from the cache and
  excluding on `working-branch`; `--include-working` on `pick` and `list` replacing
  `--include-claimed`; the claim machinery removed from `plugin/lib/backlog/core.py`,
  `plugin/lib/backlog/cli.py`, `plugin/lib/backlog/query.py` and `plugin/lib/backlog/encode.py`;
  the claim prose removed from `plugin/skills/backlog/SKILL.md` and
  `plugin/skills/backlog/adapter-mode.md`; `tests/test_backlog_claim.py` deleted
- **Tests:** catalogue — **QRY-2** (ready-work correctness, including the negative: a stale cache
  must not let a blocked item be picked); **OPS-1** and **OPS-3**, carried here from Chunk 01, which
  could not discharge them: both assert properties of the whole deployed adapter (cost is O(1) in
  project count; correctness holds with no daemon running), and this is the chunk where the full
  CRUD + query + `pick` surface is finally cache-backed and therefore assertable end to end; new —
  each restored probe fires on a real trigger and
  stays quiet on a clean corpus, each reports unavailable rather than empty when the cache is
  missing, and `pick` returns the same candidate set from the cache as from a live scan on the same
  corpus. For the retirement: an item with a populated `working-branch` is absent from `pick` and
  present under `--include-working` with its branch shown; an item whose body still carries a legacy
  `claimed_at` key round-trips through a write with the key intact and is **not** excluded by it
  (the ENC-4 inert-key claim, asserted rather than assumed); and a grep-style test that no `claim`
  op, flag, or `allowed-tools` grant survives in the skill prose — the half-retirement this chunk's
  code/prose pairing exists to prevent is exactly what a passing unit suite would not catch
- **Acceptance criteria:** `pick` completes under the NFR floor on this repo's live backlog; both
  restored probes produce a finding on a seeded trigger; no probe returns `[]` for a reason other
  than "nothing matched"; `prawduct-hook backlog claim` exits as an unknown op and nothing in the
  skills tells a reader to run it
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. #230 updated `status=shipped` with the measured before/after, via `/prawduct:backlog update`
  3. `documentation/backlog-service-data-model.md` and
     `documentation/backlog-service-api-contract.md` reconciled where they specify `claim` /
     `unclaim` / `claimed_at` — a retired operation still specified is a second home for a decision
     that no longer holds
  4. `/prawduct:critic` run and blocking findings resolved
  5. Committed and chunk marked `[x]` in Status

### Chunk 06: Prose consumers, retirements, and the end of the dormancy advisory

- **Description:** The last consumers are prose contracts in the skills, and this is the chunk that
  deletes the dormancy machinery. Restored: the Critic's Backlog Reconciliation walk and C-B1–C-B4
  in `plugin/skills/critic/review-cycle.md`; the PR reviewer's R-1 and R-2 in
  `plugin/skills/pr/review-protocol.md`; the janitor's Backlog Health checks 1–5 in
  `plugin/skills/janitor/SKILL.md`. Each loses its "check the backend first / emit the dormancy
  line" branch and gains a cache-backed query — except the one #529 still blocks, below.

  **One of those five does not come back yet.** Consumer 12 — the neglected-hygiene check, items
  in the `promoted` state whose owning chunk shipped — is blocked by **#529**: the `promoted`
  status value it keys on has no Issues-backend equivalent, so the query has nothing to ask for.
  It keeps its dormancy line while the other four lose theirs, and the line names #529 rather than
  the cache, since the cache is no longer what it waits for. Restoring it alongside the others
  would ship a check that silently matches nothing, which is the failure this whole plan exists to
  end.

  **Retired, not restored: janitor checks 6 and 7.** Counting unstructured legacy items and
  proposing an `## Archive` split are meaningless once Issues is system of record — the janitor's
  own prose already says so — and restoring them would ship advice a reader could act on to no
  effect. Removal is the default for a control with no remaining yield.

  Three obligations that are easy to lose here, all norm-driven. **Every restored check names the
  yield it expects, in the same edit that restores it** — a re-added control is an added control,
  and one whose findings are printed and forgotten can never be retired on evidence, only defended
  on principle. **Every restored check distinguishes "ran, found nothing" from "could not run"** —
  the whole reason these seven were made to announce their own dormancy is that a silent reader and
  a clean bill of health are indistinguishable, and restoring them in a form that returns empty on
  an unreachable cache would rebuild that exact failure in a new costume. **And every restored
  check treats item text as data, not instructions** — this is where cached issue bodies re-enter
  agent-read prose at scale, so the security norm gets restated at the site rather than assumed
  inherited.

  Then the dormancy machinery goes: `DORMANT_CHECKS` empties and `probe_checks_dormant` is removed
  with it, retiring the `backlog-checks-dormant` advisory.
- **Depends on:** Chunk 05
- **Artifacts consumed:** `documentation/backlog-service-cache-spec.md` §§2, 2.1;
  `documentation/backlog-service-security-model.md` §3
- **Deliverables:** `plugin/skills/critic/review-cycle.md`, `plugin/skills/pr/review-protocol.md`,
  `plugin/skills/janitor/SKILL.md`; `DORMANT_CHECKS` and `probe_checks_dormant` removed from
  `plugin/lib/backlog_probes.py`; the advisory's registry row removed
- **Tests:** new — the advisory no longer fires post-cutover; the probe registry has no dangling
  row. Note the token-budget guardrails on the skill files: three prose surfaces are being edited
  and each carries a size test, so anticipate the trim rather than discovering it at chunk close
- **Acceptance criteria:** a Critic review and a `/prawduct:janitor` run on a branch with real
  changes each produce backlog findings a reader would act on; deleting the cache makes those same
  runs say so rather than reporting clean; the session briefing no longer carries the dormancy
  advisory
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. #621 updated `status=shipped`; #564 dispositioned (spec §2.1 makes it a duplicate of a retired
     concern — retire it or fold it into #550, and record which), via `/prawduct:backlog`
  3. `migrate.py`'s docstring reconciled — it still says re-import into a non-GitHub backend is
     "out of scope," which spec §8 supersedes for the cache schema; a contradicting second home
  4. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  5. Chunk marked `[x]` in Status

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can do:** build the cache against the real 178-item backlog and query open items
out of it — the first evidence the approach holds, and the first time drop-rebuild-compare is a
fact about this repo rather than a claim in a spec.

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic review passes. Chunk 06's `cumulative`
review makes the branch PR-ready and is `/prawduct:pr create`'s gate.

- **After Chunk 01** — architecture validation, and the one that matters most: confirm
  rebuild-equivalence actually holds against the live backlog before four more chunks build on the
  assumption that the cache originates nothing. Also re-read `data-model.md` §6 against what was
  built, since this chunk is where drift from the corpus would start.
- **After Chunk 03** — the persisted schema is complete. Last cheap moment to change a field: past
  here every consumer binds to it. Check spec §5's zero-cache-only-fields invariant against what
  was actually built.
- **After Chunk 06 (cumulative)** — full-bundle review. Verify the three things this plan is most
  likely to have gotten wrong: that no restored consumer can reach a blocking verdict from the
  cache, that every restored consumer reports unavailable rather than empty, and that the F4
  single-repo scoping decision actually held rather than eroding into a multi-repo store nobody
  re-authorized.
