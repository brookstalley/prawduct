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
lifecycle: completed
archived: 2026-08-10
released_in: v3.3.0
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

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

- [ ] Chunk 01: Cache store — schema, rebuild, visible age, and the rebuild-equivalence invariant
- [ ] Chunk 02: Incremental sync — cursor watermark and conditional revalidation
- [ ] Chunk 03: The three new domain fields and their write path
- [ ] Chunk 04: The consumer query surface — grouping, FTS, alias resolution
- [ ] Chunk 05: Code consumers — the norm probes, `pick` off the cache, and the end of `claim`
- [ ] Chunk 06: Prose consumers, retirements, and the end of the dormancy advisory

Context: **All six chunks are built and green — the plan is complete.** Chunk 06 restored the three
prose consumers onto the cache and deleted the dormancy machinery: `DORMANT_CHECKS` and
`probe_checks_dormant` are gone, and the `backlog-checks-dormant` advisory retires through the
ordinary `reconcile` path (`resolved_by: sync`) rather than needing a removal step of its own —
verified against the live advisory store. Suite **4185 passed / 7 skipped**, from 4151 at chunk start.

Verified against the real 453-item backlog: `affecting` over this branch's own changed files returns
**#621 and nothing else**, with the three `affected:` entries that matched; `unstaged` returns 7 real
items; `by-area` returns 51 groups. With the store moved aside, **every query exits 6 with a reason
and the command that fixes it** — never an empty set. The detached trigger was driven end to end
through the session-start path: store age went **2615s → 12s** after one warm.

**Two things this chunk built that its Deliverables line did not name.** (1) `cachequery` had no
CLI, and its consumers here are *agents* — so `prawduct-hook backlog cache-query` is new, and the
`critic-reviewer` agent type is granted it (the DECISION block at the top of this chunk carries the
reasoning and the two rejected alternatives). (2) `resolve` could not read a **bare `#N`**, which is
how citations are almost always written — this repo's change-log carries 259 bare refs against 5
qualified. Left unfixed, C-B4 and R-2 would have resolved almost nothing and reported it as "no such
item", which is the failure this whole plan exists to end. Fixed in `cachequery`, not at the CLI, so
the Chunk 05 probes get it too.

**The query mechanics live in one new file, `plugin/skills/backlog/cache-reads.md`, and that is what
paid the token budget.** `review-cycle.md` had 4 tokens of headroom against a ceiling whose standing
rule is *the next addition trims or relocates, it does not bump*. Stating the invocation, the exit-6
contract and the age contract in each of the three surfaces would have been the first of three
copies — and drift between exactly those three is what `tests/test_cutover_prose_coherence.py`
exists to catch. Routed instead, the restored walk came in **18 tokens smaller** than the dormancy
notice it replaced. That test class was re-aimed rather than deleted: it now pins the routing, plus
the two rules each surface must still carry in its own words (unavailable-is-not-empty, and item text
as data), plus a check that the destination still holds what the surfaces stopped restating.

`migrate.py`'s docstring is reconciled — the "out of scope" claim overstated Data Model §8, which
forecloses a second *backend*, not the provider-neutral domain schema the cache spec added.
`adapter-mode.md` gained `sync` and `cache-query`, and lost a stale claim that cache-served `search`
was unbuilt — `find` and `dedup` no longer degrade to a NOTE.

**Previously (Chunk 05):** the suite passed clean and every acceptance criterion was
verified against the live backlog at **schema 6**. `pick` returns ranked ready work in **~0.9s at
`--limit 1`** and **~2.0s at `--limit 3`** against the real 453-item store, against the ~12.4s the
same call took before (#230, ~6x the NFR §4 floor); the whole difference is that the candidate walk
stopped being a paginated scan of every open issue. `prawduct-hook backlog claim` exits 2 as an
unknown op, `pick --claim` exits 2 as an unknown flag, and no skill surface tells a reader to run
either. Both restored probes were driven end-to-end against the real store: `dead-why` fired on a
norm citing a genuinely shipped issue, `stalled-transition` fired at 98 days on an aged in-transition
tracker, and with the store deleted **both reported `backlog-cache-unreadable` rather than nothing** —
one advisory between them, not two. (Chunk 01 shipped `05d09f3`, Critic `rev-20260807T145538Z`
clean; Chunk 02 `fbdf273`, cumulative `rev-20260807T155720Z-e9acddfa` then verify
`rev-20260807T162342Z-98cc1462` at 0/0/0; Chunk 03 `a4276f3`, cumulative
`rev-20260807T171120Z-485805c5` at 0 blocking then verify `rev-20260807T173116Z-bb6a879f` at
0/0/0; Chunk 04 `c373768`, review `rev-20260807T190710Z-0b730657` at 0 blocking / 2 warnings /
3 notes, all five dispositioned and fixed in the chunk's own commit.) Tracking item **#621**; **#230**
is discharged by Chunks 02 + 05.

**The `relationship` table is gone, which is the decision Chunk 04 left standing and this chunk had to
make rather than inherit.** It was the natural home for blocker edges, and blocker edges are the one
predicate ready-work must never answer from the store: a blocker can live in another repo, this cache
holds exactly one, so a cached edge could record only that a dependency *existed*. The table could
therefore never gain the consumer it was shaped for — and an empty table shaped like the answer is
worse than no table, because the next builder wires the fan-out to it and the cross-repo case fails
silently. The no-dead-fields rule and the correctness argument pointed the same way. Schema **v6**.
`comment` stays, on the opposite reasoning: nothing forbids a consumer arriving, so it keeps the
trigger comment `tags` had before its removal. `item_updated_at` was named a dead-weight candidate in
the previous handoff and is **not** — a function-over-column filter cannot use it, but `stale_items`
orders by `updated_at` and an index serves an ORDER BY.

**`pick` revalidates before it reads, and that is where never-silently-stale finally has teeth.** One
conditional request, free in the steady state; when it fails the store is still served and both the
failure and the store's visible age ride out as warnings. The blocker fan-out stays live, so the
QRY-2 negative holds *structurally* rather than by discipline: a stale store cannot let a blocked
item through because it is never asked. That negative is asserted directly, with revalidation forced
to fail so the cache is provably stale.

**The restoration surfaced a real defect in `dead-why` that dormancy had hidden.** Pointed at this
repo's own norms it fired three times on `observability-strategy.md`, every hit a `Status:
steady-state … transitioned when <item> closed` line — the transition's own record, the healthiest
state a norm reaches, reported as rotting rationale. The `Status:` arm now counts only while the
status still reads `in-transition`, which is also exactly the case `stalled-transition` hands to it.
The `Why:` arm is untouched. **The tripwire caught it, not a unit test**, and it caught it only
because the probe was pointed at real data for the first time since the cutover.

`--include-working` landed on `pick` (a real CLI flag: the exclusion is served by the query) and on
`list` **as a rendering rule in the skill**, which is where its predecessor `--include-claimed` always
lived. `[DECISION: no `--include-working` on the CLI `list` op | `working_branch` is a body-block
field the provider cannot filter on, so a CLI-side default exclusion would have to post-filter a page
— and `list`'s `count`/`has_more` contract is explicitly built on the raw page length, so the flag
would make the pagination signal lie. The skill already holds the row-rendering rules and each item
carries `working_branch` in its envelope | user can veto/override]`

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

  **[DECISION: the `etag` this chunk writes is the cursor's, not the item's — verify-api,
  2026-08-07.]** This chunk's original text said "the `etag` column earns its keep here; sync is
  where it is written," meaning `item.etag`. The verify-api step falsified the mechanism: sync
  reads the *list* endpoint, whose ETag is query-scoped, and a list ETag replayed against
  `GET /issues/{n}` returns **200** where that item's own ETag returns **304** — the list body
  carries no per-item validator at all (only `node_id`, already excluded as a dead read). Writing
  the list validator into `item.etag` would have made Chunk 05's revalidation silently useless:
  every conditional read would miss, spend a full request, and look like it was working. So the
  two validators are separated — `cursor` gains an `etag` column for the list query, and
  `item.etag` stays NULL until a decision-path read issues a single-item request in Chunk 05.
  NFR §5's never-silently-stale row is still what both serve. Recorded in `cache-spec.md` §6 and
  `data-model.md` §6; this is the design change, not a note about one.

  **The cursor-scoped ETag is also what makes this chunk's own acceptance criterion cheap.** "A
  sync following a no-op interval fetches zero pages" is satisfiable without it, but with it the
  no-op sync additionally costs **zero rate-limit points** (measured, not assumed). The mechanism
  is that a no-op does not advance the cursor, so the next query is byte-identical and the stored
  validator still applies; once real items come back the cursor moves, the query changes, and the
  validator is void by construction rather than by expiry.

  **Sync must query `state=all`.** Verified: `since` and `state` are independent AND filters, so
  the `list_issues` default of `state="open"` would filter out exactly the closes that spec §6's
  "no scheduled deletion sweep" decision depends on `since` catching. A close would leave a stale
  open row in the cache forever. This is a one-word argument at the call site and a silent,
  permanent wrong answer if missed.
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
- **Deliverables:** new `plugin/lib/backlog/sync.py`; `since` + conditional-request support on
  `transport.GhTransport.list_issues` (including the `gh`-exits-1-on-304 handling below); the
  `cursor(scope, since, etag)` schema, stored with the cache, uncommitted, its absence meaning
  full rebuild
- **Tests:** catalogue — **QRY-5** (sync/cursor); new — `test_a_crash_between_fetch_and_commit_
  loses_nothing_on_re_run` (the advance-after-commit atomicity argument, cut exactly at the row
  write), `test_the_window_reaches_back_past_the_newest_stamp_seen` (boundary overlap),
  `test_syncing_twice_over_the_same_window_changes_nothing` (idempotent double-upsert),
  `test_a_close_is_observed_because_the_window_is_not_state_scoped` and
  `test_a_quiet_interval_fetches_no_pages_at_all` (the two verify-api findings with teeth), and
  `test_the_watermark_is_a_provider_stamp_never_the_local_clock`. The first, fourth and fifth were
  each confirmed to fail under a targeted mutation — split transaction, `state="open"`, and a
  discarded validator respectively — rather than assumed to be load-bearing because they are green.
  All
  clock-dependent tests inject one clock shared by every actor in the scenario; a single real-clock
  participant turns a fixed-timestamp test into a scheduled failure at stamp-plus-TTL wall time
- **Acceptance criteria:** a sync following a no-op interval fetches zero pages; an item edited
  since the last sync appears with its new state; killing the process between fetch and commit
  loses nothing on re-run; a rebuild of this repo's backlog paces under the core budget as NFR §3.3's
  cache-rebuild row expects
- **Foreign API:** github-rest-issues (`GET /repos/{owner}/{repo}/issues`, `since`)
- **Done when:**
  0. ~~verify-api~~ **DONE 2026-08-07** — answers written into `cache-spec.md` §6 (the durable
     home) and summarised in the DECISION above. Four results, all live-verified: `since` filters
     `updated_at` inclusively; `since` × `state` are independent ANDs so **closes need
     `state=all`**; the list endpoint honours `If-None-Match` and a 304 is rate-free; the list and
     per-item validators are **not** interchangeable. One further mechanical fact the fakes must
     reproduce: **`gh` exits 1 on a 304**, printing `gh: HTTP 304` to stderr with empty stdout, so
     `_api` has to read that as a successful not-modified rather than a failure. Fakes are built
     against these, and were not built before this step
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

  **[DECISION: the three fields' substrates, spellings and validation — 2026-08-07.]** The plan
  named the fields; it did not pin how each is carried, and every one of these is a persisted-format
  choice, which is lock-in measured by reversal cost. Five, in the order they bite:

  1. **`tags` → `tag:<value>` labels, namespaced like every other prawduct label.** Cache Spec §3
     says tags "map natively to labels"; Data Model §3 says *every* prawduct label is
     `<facet>:`-namespaced so it can never collide with a repo's existing labels (GV6). Bare
     folksonomy labels would break GV6 on the first repo that already has a `perf` label. `tag`
     therefore joins `KNOWN_FACETS` (provisioned on demand, like the other open facets — never in
     `base_labels()`, which is closed vocabularies only) and `NAMESPACED_LABEL_PREFIXES`, which
     widens `is_prawduct_issue`: an issue carrying only a `tag:` label is now ours. That is the
     intended reading, not a side effect.
  2. **`tag` is the one MULTI-valued facet**, so it cannot ride `_UPDATE_FACETS`. That loop is a
     label *swap* — add the new value, strip every other label with the same prefix — which is
     exactly right for `area` (exactly-one, wired to the title) and exactly wrong for a folksonomy.
     `update <id> tags=a,b` therefore sets the full tag set (add the missing, strip the absent),
     which is the only semantics that lets a caller *remove* a tag; `tags=` (empty) clears them.
  3. **`affected` and `working-branch` live in the body block** (Cache Spec §5), and the block's key
     convention is snake_case (`id_aliases`, `claimed_at`, `superseded_by`). So the block keys are
     `affected` and `working_branch`, while the domain/CLI spelling stays `working-branch`
     (`--working-branch`). One mapping, stated once in `encode.py` beside the accessor, because the
     alternative — kebab in the block — puts one odd key among six snake ones forever, and block
     keys are additive-only-forever (Data Model §7): the spelling chosen here is the spelling
     always.
  4. **`working-branch` is `owner/repo@branch`, and "pushed" is verified against the provider, not
     against the local clone.** Repo-qualified because `backlog_service_repo` can differ from the
     code repo (Cache Spec §3); `@` because `owner/repo` cannot contain one, so a first-`@` split is
     unambiguous even for `feat/a/b` branch names. The pushed-ref check is a new
     `transport.branch_exists` — **verify-api done live 2026-08-07** against the backing repo:
     `GET /repos/{owner}/{repo}/branches/{branch}` returns 200 with `.name` for a pushed branch
     (including slash-bearing ones, un-escaped in the path) and 404 `Branch not found` otherwise,
     which `_map_failure` already maps to `not_found`. **Rejected: checking the local clone's
     remote-tracking refs.** It is free and offline, but it answers "did *this* clone last fetch a
     ref by that name" — which is a stale proxy in both directions, and it cannot answer at all for
     a repo this machine has not cloned. The field's one job is making a claim visible to *other*
     agents, so the check has to run where they would look.
  5. **The "`affected` index" is a table, not an index on a column, and both exist.** `item` gains
     three columns (`affected`, `tags`, `working_branch`) carrying the verbatim domain values —
     those are what rebuild-equivalence compares and what a reader sees. Beside them sits
     `item_affected(item_id, path)` with an index on `path`: an index on the joined text column
     could not serve the actual query, because the intersection runs *entry-contains-changed-file*
     (`plugin/lib/` matches `plugin/lib/core.py`) and `WHERE ? LIKE path || '%'` uses no index. The
     query instead expands each changed path into its ancestor prefixes and matches by equality,
     which the index does serve. **This is the `item_fts` shape exactly** — a derived index table
     beside the column it indexes, written in the same transaction, rebuilt from the same provider
     rows — so it is not a second home for the fact, for the same reason FTS is not. Its consumer
     (`cachequery`) lands in Chunk 04, which already declares `Depends on: Chunks 01, 03`; this
     chunk ships the storage, the ancestor-expansion matcher, and the test that proves the shape
     answers a real changed-file set.

  **[DECISION: the SEC-2 allowlist grows a THIRD category, not three more facets — 2026-08-07.]**
  This chunk's Deliverables say to name all three fields in `_UPDATE_FACETS`. Taken literally that
  is wrong on mechanism: `_UPDATE_FACETS` is the label-swap loop, so it would write `affected:…` and
  `working-branch:…` labels for two fields the spec puts in the body block, and would single-value
  the one field that is deliberately multi-valued. The *intent* — all three pass through the SEC-2
  mass-assignment allowlist, and the widening reads as a decision rather than as a diff nobody
  mentioned — is honoured exactly: the allowlist becomes
  `_UPDATE_DIRECT | _UPDATE_FACETS | _UPDATE_MULTI_FACETS | _UPDATE_BLOCK_FIELDS`, each name written
  down, each with its own writer. The Deliverables line below is corrected in place rather than left
  to be discovered as a divergence.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `documentation/backlog-service-cache-spec.md` §3;
  `documentation/backlog-service-data-model.md` §§6, 7
- **Deliverables:** `affected` / `tags` / `working-branch` in `plugin/lib/backlog/encode.py`
  (`decode_item`, the `Block` accessors, the normalize/validate pair for each, and the
  ancestor-expansion matcher); the three `item` columns plus the `item_affected` index table in
  `plugin/lib/backlog/cache.py` at schema **v4**, populated by `plugin/lib/backlog/sync.py`; the
  write path in `plugin/lib/backlog/core.py` — which means **naming all three in the SEC-2
  mass-assignment allowlist**, a deliberate widening of a security control that should read as a
  decision rather than as a diff nobody mentioned, and which per the DECISION above is
  `_UPDATE_MULTI_FACETS` + `_UPDATE_BLOCK_FIELDS` beside `_UPDATE_FACETS` rather than three more
  facets; `transport.branch_exists` for the pushed-ref check; the `--tag` filter on `list` in
  `plugin/lib/backlog/query.py` and `plugin/lib/backlog/cli.py` (with `--tags` / `--affected` /
  `--working-branch` on `update`); and the registry rows all of that owes —
  `documentation/backlog-service-data-model.md` §§1.1, 2, 3, 6, `cli._HELP`, and the backlog
  skill's `adapter-mode.md`
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

- **Carried in from Chunk 03's review** (`rev-20260807T171120Z-485805c5`, 0 blocking). Four findings
  land here because this is the chunk whose consumers bind to them, and riding a commit that is
  being made anyway costs no extra review round. **All four are answered — see "As built" below for
  what each became:** (1) the coverage stamp, (2) `tags` removed, (3) the intersection exposed as
  `cachequery.items_affecting`, (4) `optimize` after a rebuild.

  1. **The visible age has been over-reporting since Chunk 02, and this chunk's consumers are the
     ones that will bind to it.** `_freshness` answers with `MIN(item.fetched_at)`, which was the
     whole story while every sync rewrote every row. Incremental sync stamps only the window, so that
     number is the fetch time of the least-recently-*edited* item and grows without bound while syncs
     succeed — a store synced ten seconds ago can honestly report an age of weeks. The 304 path is
     worse: it returns before touching the store, so `cursor.fetched_at` does not advance either and
     nothing records that coverage was confirmed. **Model the two facts separately**: leave row
     provenance where it is, add a per-scope *coverage-confirmed-at* stamp that every successful sync
     including the not-modified one advances, and serve age from that with row provenance as the
     fallback. Whatever is chosen, restate it at `cachequery._freshness`, whose current docstring
     ("the honest promise is the worst row in it") is the rebuild-era argument and no longer
     describes the number. A column change means **schema v5** — bump it (`cache.py`'s comment says
     why, pre-release included).
  2. **`item.tags`' removal trigger fires in this chunk.** The column has no consumer query; the
     `--tag` filter is served live off the provider's label query. Its stated justification is the
     provider-adequacy half of rebuild-equivalence, which is genuine but is not a Q-projection.
     Answer it deliberately here — either a cache-served tag query appears, or the column comes out —
     rather than letting it survive unremarked.
  3. **The `item_affected` intersection has no `cachequery` wrapper.** The storage, the ancestor
     expansion (`encode.path_ancestors`) and the SQL shape all shipped and are proven by test and by
     a live run, but consumers 1 and 4 cannot reach them. Expose it here.
  4. **One `optimize` after a rebuild is the cheap moment.** Nothing runs `VACUUM` or FTS5's
     `optimize`, and `--rebuild` deletes rather than drops, so a long-lived clone's file only grows
     and FTS segments accumulate. Small and self-healing, but this chunk is already in the FTS code.


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

  **As built.** Eight functions carry the union, each naming the consumers it serves, and the two
  invariants they inherit — unavailable is never empty, every payload carries a visible age — are
  asserted *across the whole surface* rather than once per function, so a query added later without
  going through `_serve` fails rather than quietly opting out. One function serves consumers 5, 7,
  14 and 15 together: all four ask the same lookup a different question (*resolves? / status? /
  dead? / how long since it moved?*), and splitting them would be four resolutions of one id.

  `[DECISION: `item.tags` is REMOVED — the trigger the column's own comment named fired |
  Chunk 03 shipped `tags` with its justification stated as explicitly *not* a consumer query: it was
  carried because rebuild-equivalence doubles as the provider-adequacy test, so a domain field the
  cache never stores is one that test never exercises. The named trigger was "the first release of
  the query surface that ships no cache-served tag query takes the column", and this is that
  release: `list --tag` is served **live** off the provider's label filter and none of spec §2's
  fifteen consumers asks about a tag. The alternative — inventing a cache-served tag query to
  justify the column — would be manufacturing a requirement to protect a field, which is the defect
  one rung up from the one the rule prevents. Two things make removal the cheap side rather than the
  brave one: a cache is **rebuildable**, so re-adding the column later costs a version bump and a
  re-fetch rather than a migration, which is exactly why the usual persisted-format lock-in argument
  for keeping it does not apply here; and `tags` → labels is the mapping every candidate provider
  satisfies most trivially, which the live `--tag` filter exercises end to end anyway. What is lost
  is precise and small: rebuild-equivalence no longer mechanically covers this one field. The test
  asserts the removal from **both** ends — absent from the store, still filterable on the provider —
  because half of it would be indistinguishable from the field having been lost | user can
  veto/override]`

  `[DECISION: the visible age is served from a per-scope coverage stamp, and the 304 path writes |
  `cursor.fetched_at` becomes `cursor.coverage_confirmed_at`, renamed *and widened*, and the
  widening is the substantive half. A rename alone would have left the not-modified sync where it
  was — returning before touching the store — and that is the path where the over-reporting was
  worst, because a quiet interval makes it the steady state rather than an edge. A 304 establishes
  something specific: the provider has nothing newer than the watermark, so the store is **current**,
  not merely un-refreshed. **Rejected: keeping both columns.** A separate write-stamp beside the
  coverage stamp would have had no reader — `item.fetched_at` already ages the rows — so it would
  have been the dead column this same chunk removed one table over. `_freshness` keeps row
  provenance as its fallback, which no writer produces and which exists so a *reader* never claims
  "never synced" about a store whose rows are visibly there. (**Superseded reason, kept because the
  conclusion outlived it:** this said "every write path stamps the cursor in the same transaction
  as its rows". The local-write mirror added by `build-plan-backlog-cache-write-path.md` is a
  writer that deliberately does not — a mirror is not a fetch — so the state is now unreachable
  because that mirror refuses to run against a scope with no cursor row, not because no such writer
  exists. `cachequery._freshness` carries the current statement) | user can veto/override]`

  `[DECISION: the alias index is `item_alias(alias, ref, item_id)`, and labels stay PFX-only |
  Spec §4 rule 3 says all resolution goes through the alias table, so it is a table — a lookup
  rather than a scan that parses every body — derived from the stored `item.body` in the same
  transaction, the `item_affected` / `item_fts` shape exactly. Two parts needed deciding. **`ref`
  exists because the two ends of a resolution are spelled differently on purpose:** an alias is
  stored *tagged* (`github:owner/repo#249`, since `owner/repo#number` is not GitHub-unique — GitLab
  and Gitea share the shape), while a historical citation in a change-log is written *untagged*.
  Matching untagged against the tagged column takes `LIKE '%:' || ?`, whose leading wildcard no index
  can serve — the same unindexable direction `item_affected` exists to invert, inverted the same way:
  derive the equality key at write time. **Labels are NOT extended to provider aliases.** A label is
  the *live* path's index, and a hand-minted PFX has no other coordinates, so without one it is
  unfindable; a provider alias is a real `owner/repo#number` that `item_alias` resolves without
  asking the provider anything. Minting labels for it would add a write path, a self-heal obligation
  and a 50-character label budget to buy a second index over an already-indexed set. **No UNIQUE on
  `alias`:** uniqueness is an integrity constraint, not a storage one, and a store that refused to
  hold a violation could not report it as `alias_collision` | user can veto/override]`

  **A latent defect fixed here rather than filed, because this chunk's own version bump would have
  shipped it.** `sqlite_master` lists an FTS5 virtual table *after* its own shadow tables, so
  `_drop_objects` — walking that listing — deleted `item_fts_config` and then found `item_fts`
  unconstructible (`vtable constructor failed`). The bare `except OperationalError: continue`
  swallowed it, `create_schema` reported the consequence as "SQLite built without FTS5", and the
  store was left holding an `item_fts` that `has_fts()` called present and every query raised on —
  so consumer 9 would have reported `unavailable` forever after any schema bump, with a reason
  telling the reader to go and rebuild their interpreter. Three seams, because one fix would have
  left the others able to hide the next one: virtual tables drop first; survivors are returned and
  refused rather than swallowed; and only a genuine `no such module` counts as missing FTS5, every
  other DDL failure being re-raised. The regression test asserts through `search`, not through
  `has_fts` — the function that returned the wrong answer cannot be the one that proves it right.

  **QRY-3 is discharged in part, and the remainder is named rather than left to look covered.**
  The catalogue row has two halves. The **cache-served / read-your-writes** half is this chunk's and
  is done: a just-written item is found by `cachequery.search` at the moment GitHub's own index would
  still miss it, which is the whole reason this query is cache-served rather than delegated. The
  **`--semantic` capability probe** half is not — it is a `search` *CLI op* with a live provider
  probe, and no chunk of this plan delivers one (`cachequery` is a library surface; Chunks 05–06
  bind probes and skill prose, not a new op). Recording the split here because a catalogue row
  ticked whole on half the evidence is the exact defect this plan keeps naming, and a later reader
  asking "is QRY-3 covered?" should find the answer rather than infer it from a green suite.

  **Two smaller shapes worth naming.** Date predicates compare **instants, not strings**
  (`strftime('%s', …)` on both sides): the provider stamps `...Z` while Python's `isoformat()` writes
  `...+00:00`, so one moment has two spellings and the lexicographic answer between them is not the
  chronological one — the same rule `sync._watermark_from` records, and it costs the `item_updated_at`
  index, which at hundreds of rows is orders of magnitude inside the NFR §4 budget where a wrong
  boundary answer would not be. And FTS search **quotes every term into a phrase**, because search
  text is a caller's arbitrary string on its way to a dedup check and unquoted FTS5 is a small
  language — a title containing `AND`, `*` or `:` would otherwise either steer the query or fail it
  with a syntax error the caller could not have anticipated.
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
  `plugin/skills/backlog/SKILL.md`'s `allowed-tools` grant, plus `adapter-mode.md`'s claim/unclaim op
  mapping and its `--assignee none` exclusion. Chunk 06 owns prose that *restores dormant consumers*;
  splitting this one across that boundary would leave a commit where the CLI has no `claim` op and the
  skill still grants and documents one.

  **This paragraph named two more SKILL.md surfaces — its `accepted-by:` section and the
  `list --include-claimed` flag — and was corrected as built.** Those are the *markdown* backend's,
  and the retirement's whole argument is about the Issues adapter (a release-current op, three coupled
  mechanisms collapsing into one). `accepted-by:` has none of those mechanisms, and `working-branch`
  needs a pushed ref a local-only repo has not got. See the Context block and the corrected
  Deliverables below; the plan is edited rather than followed here, and the reasoning is the Critic's
  (R-16).

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
  **OPS-1 is discharged here; OPS-3 is carried to Chunk 06, and the split is not a blanket
  deferral.** Chunk 01 named this chunk as their home. OPS-1 — *cost is O(1) in project count* — has
  a complete subject now: the per-project footprint is two local files inside the clone, and
  `TestTheCostSurface` builds two independent projects and asserts the Nth adds the same rebuildable
  pair inside its own clone and nothing shared, global or in the working tree. **OPS-3 does not have
  a complete subject yet**, and that is why it moves rather than being written thin: its text is
  *"the detached refresh is a subprocess, not a daemon"*, and no detached refresh exists until Chunk
  06's DECISION block builds one. Writing it now would assert a property of a component that is not
  there, which is the catalogue-row-describing-a-check-nobody-built defect this plan names twice.
  Chunk 06's Tests line carries it.

  **Three things this chunk did that its Deliverables line did not name, each recorded here rather
  than left to be found as a divergence.** (1) **The three `lib/norm_probes.py` rows left
  `DORMANT_CHECKS`.** Chunk 06 empties that list; but two of those checks are restored *here* and the
  third is retired *here*, so leaving their rows would have shipped a commit whose session briefing
  announced seven dormant checks when four were dormant. A row belongs there only while its check is
  waiting. (2) **`_extract_ids` learned the issue-ref spelling** (`#621`, `owner/repo#621`). The PFX
  pattern was the only one it knew, and post-cutover Direction sections cite provider ids — a probe
  reading only PFX would have scanned every artifact, found nothing to resolve, and looked exactly
  like a clean bill of health. (3) **`dead-why`'s `Status:` arm narrowed to in-flight transitions**,
  which is a defect the restoration surfaced against this repo's real norms and is written up in the
  plan Context.
- **Depends on:** Chunk 04
- **Artifacts consumed:** `documentation/backlog-service-cache-spec.md` §§2.1, 3, 6;
  `documentation/backlog-service-nfr.md` §§4, 5
- **Deliverables:** `probe_dead_why` and `probe_stalled_transition` in
  `plugin/lib/norm_probes.py` reading `cachequery`; `probe_revisit_due` removed along with its
  registry row; `pick` in `plugin/lib/backlog/query.py` sourcing candidates from the cache and
  excluding on `working-branch`; `--include-working` on `pick` and `list` replacing
  `--include-claimed`; the claim machinery removed from `plugin/lib/backlog/core.py`,
  `plugin/lib/backlog/cli.py`, `plugin/lib/backlog/query.py` and `plugin/lib/backlog/encode.py`;
  the claim prose removed from `plugin/skills/backlog/adapter-mode.md` and from
  `plugin/skills/backlog/SKILL.md`'s **adapter-facing** parts only — the markdown backend keeps
  `accepted-by:`/`--include-claimed`, for the reason recorded in the Context block;
  `tests/test_backlog_claim.py` deleted; `cachequery.ready_items`
  (the candidate query, whose named consumer is `pick` — spec §2 inventories the *dormant* readers and
  `pick` never was one); the `relationship` table dropped and `SCHEMA_VERSION` bumped to 6
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
  skills tells a reader to run it — **"the skills" means the adapter surface**; the markdown
  backend's own way of taking an item is out of this retirement's scope
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. #230 updated `status=shipped` with the measured before/after, via `/prawduct:backlog update`
     — **done 2026-08-07**: shipped, with a comment carrying the measurements (~12.4s → ~0.9s at
     `--limit 1`, ~2.0s at `--limit 3` on a 453-item corpus) and the correction that neither route the
     item anticipated is what removed the cost. Recorded here because a remote write leaves no trace
     in the changeset, so the only evidence a later reader has is this line
  3. `documentation/backlog-service-data-model.md` and
     `documentation/backlog-service-api-contract.md` reconciled where they specify `claim` /
     `unclaim` / `claimed_at` — a retired operation still specified is a second home for a decision
     that no longer holds. **The sweep did not stop at the two this line names, and the line was the
     reason it nearly did**: `-test-specifications.md` (CRASH-6, the error-code coverage row, QRY-2's
     setup), `-nfr.md` (the rate and latency budgets) and `-requirements.md` (CC3, GV1) specify the
     same retired op, and a rule about second homes does not stop at the homes someone remembered to
     enumerate
  4. `/prawduct:critic` run and blocking findings resolved
  5. Committed and chunk marked `[x]` in Status

### Chunk 06: Prose consumers, retirements, and the end of the dormancy advisory

- **[DECISION: the cache gets a trigger, and it lands here — 2026-08-07, from Chunk 03's review.]**
  Chunk 03's review found that the store's only writer reachable from outside a test is a human
  typing `prawduct-hook backlog sync`: nothing schedules it and no hook spawns it, while NFR §8's
  "the detached refresh is a subprocess, not a supervised daemon" describes a component no chunk
  delivered. This chunk binds prose consumers to the store, several of them **restricted-tool forks**
  (the Critic's reconciliation walk, the PR reviewer's checks) that cannot execute a sync at all — so
  `cachequery`'s "run `prawduct-hook backlog sync`" would reach a reader who cannot act on it. As
  planned, W1 would ship consumers whose freshness has no owner: age visible, nothing making it
  small. **Resolution: give sync the same detached-spawn trigger `refresh-counts` already uses**
  (`transport.spawn_detached`, warmed from the session-start path), and document the op in
  `adapter-mode.md` where an agent will meet it. Accepting manual refresh instead is the alternative,
  and it is *not* free — it has to be written down in the same places, because an undocumented
  manual-refresh assumption is what produced this finding.


- **[DECISION: the prose consumers reach the cache through a new read-only `cache-query` CLI op, and
  the `critic-reviewer` agent type is granted it — 2026-08-07, owner-chosen.]** `cachequery` is a
  *library* surface, and every consumer bound so far (the norm probes, `pick`) was in-process Python.
  This chunk's three consumers are **agents**, so the module had no reachable door for them. The
  janitor holds `Bash(python3 *)` and the PR reviewer is an ordinary `Agent`, so both could reach a
  CLI op immediately; the blocker was the Critic, whose Backlog Reconciliation walk belongs to the
  **sustainability reviewer** — a `critic-reviewer` agent whose `tools` deliberately stop at
  read-only git, because that narrowness *is* the no-execution enforcement.

  So the op is added (`prawduct-hook backlog cache-query <query>`: reads the local store, no network,
  no writes, no session mutation) and `Bash(prawduct-hook backlog cache-query *)` joins the reviewer's
  tools. **The reviewer's own prose is corrected in the same edit** — it claimed "no way to run tests,
  builds, or any executable", and shipping the grant while leaving that sentence standing would be a
  doc making a false claim about its own enforcement.

  **Rejected: the coordinator pre-fetches the open set into the dispatch prompt** (no new tool at
  all). It fails on C-B4: a dangling-id check resolves ids the reviewer *discovers while reading the
  diff*, which no pre-fetch can enumerate, so the check would silently degrade to "only ids in the
  pasted block" — a reader that matches nothing, which is this plan's whole subject.

  **Rejected: `critic-begin` computes a backlog block into the dispatch manifest** beside
  `record_lint`. It is the most faithful to *the checks the machine already ran* and costs the
  reviewer nothing at review time, but it is strictly **additive** rather than alternative: the
  janitor and the PR reviewer still need the CLI op, so the manifest route would make the same
  queries' second home — against *every fact has one home* — and it moves backlog querying onto the
  Critic data plane, which this plan's `governed_by` dispositions state it does not touch. Worth
  revisiting only if reviewer round-trips become the measured wall-clock cost.

  `ready_items` is **not** exposed on the op: its only consumer is `pick`, which is already a CLI op,
  so exposing it would give one query two operator-facing doors.

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

  **Janitor checks 6 and 7: scoped to the markdown backend, not retired.** ~~Retired, not
  restored.~~ Counting unstructured legacy items and proposing an `## Archive` split are meaningless
  *once Issues is system of record*, so as written they would be advice a reader could act on to no
  effect. **That argument names one backend, and the first pass let it reach the other** — the
  cumulative review caught it (R-12) as a repeat of the Chunk 05 `accepted-by:` correction. On the
  markdown backend check 7 is the only surface that proposes a split and check 6 is the janitor half
  of the `migrate` nudge, so they run there and stand down post-cutover. A retirement is one act per
  substrate the thing lives on.

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
- **Tests:** catalogue — **OPS-3** (no server required for correctness), carried from Chunk 05
  because its subject is the detached sync trigger this chunk's DECISION block builds: exercise the
  full CRUD + query + `pick` surface in one process with nothing detached ever having run, and assert
  correctness does not depend on it. (OPS-1 was discharged in Chunk 05.) new — the advisory no longer
  fires post-cutover; the probe registry has no dangling
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

     **Both done 2026-08-07.** Annotated the way Chunk 05 annotated its own #230, and for the same
     reason: a remote write leaves no trace in the changeset, so without a line here a later reader
     cannot tell an omission from an unrecorded completion. (The cumulative review flagged exactly
     that — it read a store synced ~70 seconds before the writes landed, and said so.)

     `[DECISION: #564 is dispositioned as NEITHER — it stays open with its rationale corrected |
     This step offered two answers and the evidence supports a third. §2.1 retired the
     `revisit-due` **probe**, which is a fact about a *read* path; #564 is about a *write* path,
     and scheduling it for retirement conflated the two — the same "argument names one substrate,
     the change reached another" error Chunk 05's review cost two blocking findings for.
     `docs/norms.md` § *Exceptions expire* still states on **both** backends that "the clock always
     lives on a backlog item" carrying `revisit:`, so the norm names a mechanism this backend does
     not have, and #564 is the only tracker for that. Folding is also unavailable: #550 explicitly
     scoped `reviewed` and `revisit` **out** on 2026-08-07, so there is nothing left to fold into.
     What did change is the justification, and that is recorded on the item — it is no longer "the
     probe needs data" but "a live norm names a mechanism this backend lacks" | user can
     veto/override]`
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
