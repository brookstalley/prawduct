---
artifact: build-plan
version: 1
scope: backlog-cache-write-path
depends_on:
  - artifact: cache-spec             # documentation/backlog-service-cache-spec.md §6.1 (the contract this plan builds)
  - artifact: data-model             # documentation/backlog-service-data-model.md §1 (read-your-writes), §6 (cache schema, `cursor`)
  - artifact: security-model         # documentation/backlog-service-security-model.md §3 (F4 fetch-time auth, F5 content sensitivity)
  - artifact: nonfunctional-requirements  # documentation/backlog-service-nfr.md §4 (per-op rate budget: search is cache-served read-your-writes), §5 (freshness), §6 (degradation)
  - artifact: test-specifications    # documentation/backlog-service-test-specifications.md (QRY-*, OPS-*)
governed_by:
  # This plan is a delta on the corpus `build-plan-backlog-cache.md` already dispositioned
  # norm-by-norm. Repeating all thirty would be transcription, not judgment, so what follows is
  # the set this change's write path actually moves — plus the two whose disposition it CHANGES.
  # Every other norm's disposition there carries over unexamined-because-untouched: this plan adds
  # no column, no dependency, no egress site, and no CLI surface.
  - artifact: data-model
    dispositions:
      - "Derived views are disposable and never authoritative → conforms, and this plan strengthens the reason. A mirror writes only what the provider already returned, so the cache still originates nothing. The invariant that protects it is rebuild-equivalence, which is why Chunk 01 mirrors through the SAME decode a rebuild uses rather than patching columns directly — a bespoke `UPDATE item SET status=?` would make the store a second author on that column"
      - "Every issue written to the backlog store conforms to the issue standard's §1 title rules on every write path → untouched. This plan adds no write path to the PROVIDER; it mirrors the result of the existing ones, all of which already pass `core._title_refusal`. A mirrored title is whatever the provider stored, which is by construction what the title gate admitted"
      - "Two stores, two lifetimes → conforms, unchanged: the mirror writes the same per-clone gitignored store, at the same location, that sync writes"
  - artifact: architecture
    dispositions:
      - "Every fact has one home; every other mention is a reference to it → conforms, and it is THE norm this plan is judged against. The provider stays the home. The mirror is a reference that arrives earlier than it used to, not a second origin — which is exactly why it may never advance the watermark or the coverage stamp: those record a claim about a FETCH, and a mirror is not one. Chunk 01's tests assert both negatives directly"
      - "Authority fails closed; advice fails soft → conforms, and this plan's fail-soft edge is new. A mirror is advice about the local store; when it fails the WRITE has already succeeded remotely, so failing the command would be failing closed on the wrong thing. It degrades to a warning, and the warning is emitted rather than swallowed"
      - "Goals and verification bind; prescribed method is advice → binding here: after a successful write, a subsequent cache read reflects it; the store never claims coverage it lacks; no additional provider request is spent. Advice: the callback seam, and which module each piece lands in"
  - artifact: security-model
    dispositions:
      - "Fetch-time vs read-time authorization (F4) → conforms and stays vacuous. A mirrored issue was fetched and written by the same identity in the same command, into the same one-repo store; no cross-owner content enters, so the widening analysis F4 holds in reserve is not triggered"
      - "Untrusted governance state is data, not instructions → conforms, unchanged. A mirror stores the same body a sync would have stored moments later; it neither widens nor narrows what reaches a reader, and adds no new surfacing site"
  - artifact: nonfunctional-requirements
    dispositions:
      - "Proportionality ratchets both ways: adding a control names the yield it expects AND emits that yield observably → conforms. The yield is named (a read after a write is correct rather than confidently wrong) and observable in two ways: the mirrored row is visible to any cache query, and a mirror that FAILS says so in the write's warnings. **The ratchet also runs down here** — this plan adds no new op, no new flag, and no new scheduled work; the mirror rides commands that already run"
      - "Review wall-clock is a P0 constraint → conforms: three chunks, three reviews, with the last a `cumulative-final` rather than a `final` plus a `cumulative`"
      - "Freshness (NFR §5) — staleness bound, visible age → conforms, in the conservative direction. A mirror makes the store MORE correct than its reported age implies (the age still measures the last confirmed fetch), never less. The coverage stamp is the one number a reader acts on and this plan never moves it"
  - artifact: api-contract
    dispositions:
      - "Additive-first evolution: flag names, exit-code meanings and `--json` keys are never repurposed → conforms with nothing removed. No flag, op or exit code changes. Write envelopes may gain a WARNING when the mirror fails, which the warnings list already carries for other causes; no key changes meaning"
      - "Exit codes are the contract; errors are attributed, never raised as stack traces across the boundary → conforms, and it is load-bearing at the new seam: `sqlite3.Error` inside a mirror is caught and turned into a warning on an otherwise-`ok` envelope, never allowed to convert a successful write into a failure"
  - artifact: project-preferences
    dispositions:
      - "Error handling: return-value based; `lib/` functions return `status`/`reason` dicts → conforms; the mirror returns an envelope its caller folds into warnings"
      - "Backlog filing: fix, don't file — file only when orthogonal AND medium+ → conforms; #627 is this plan's tracking item and everything it names is fixed here"
      - "Feature branch for medium+ work; merge commit never squash → conforms — `fix/backlog-cache-write-path`"
last_validated: 2026-08-08
---

## Requirements Confidence

**Level:** High

**Why:** All three questions are answered by documents that already existed before this plan.
**Problem:** no backlog write path touches the cache, so a read after a write is confidently wrong
(#627, with the op-by-op sweep in its body). **Success:** Data Model §1's stated property —
the cache serves "the queries GitHub can't serve *read-your-writes*" — becomes true, which is the
thing W1 asserted and did not build. **Scope:** Cache Spec §6.1's eligible-op table, whose
excluded rows each carry a reason (`reconcile-labels` derives its alias index from the body, not
the labels it restores; `comment`'s table was removed at schema v7; `provision` touches no item).

**One correction made during authoring, recorded because it was nearly the plan's framing.** The
first draft presented read-your-writes as a NEW requirement this work adds. It is not — Data Model
§1 asserts it and NFR §4 prices `search` on it. Planning it as new would have put a fresh
requirement in a build plan with no parent, which is the invention half of Principle 6; and it
would have understated the defect, because "a property two parent documents already claim" is a
stronger reason to fix it before release than "a nice improvement". The learnings rule that caught
this is the one about specs that delta a parent corpus reading COMPLETE — the same rule that bit
the original W1 plan.

**The one thing rated Medium, called out rather than buried:** whether any op OUTSIDE the
enumerated set can change cached state. The sweep behind #627 was exhaustive over `_WRITE_OPS`
(ten ops, each traced to the columns it can move), so the risk is not an unexamined op — it is a
FUTURE op added without a mirror. Chunk 02 pins that with a partition test over `_WRITE_OPS`,
the same shape the ephemeral-worktree guard already uses to make an unclassified new op fail
something.

**Critic mode:** `chunk` for 01 and 02; `cumulative-final` for 03.

---

## Chunk 01: The mirror primitive — and the three negatives that keep it honest

**Deliverables**

- `cache.absorb_rows(conn, rows, *, fetched_at, evict=None)` — upsert rows and evict departed ids
  in one transaction, touching **neither** `cursor.since`/`cursor.etag` **nor**
  `cursor.coverage_confirmed_at`. The incremental sibling `apply_incremental` writes the cursor by
  design; this one must not, and the difference is the whole point of a separate function rather
  than a `write_cursor=False` flag on the existing one (a flag makes the dangerous case reachable
  by typo).
- `sync.absorb_issue(project_dir, *, owner, repo, issue, now=None)` — decode ONE provider issue
  through the existing `_rows_from_issues` path and apply it. Opens the store with `create=False`.
  Returns an `ok`/`error` envelope; never raises.
- Docstrings carrying the three invariants inline as reasons, not as references to this plan.

**Acceptance criteria**

- A mirrored row equals what a full rebuild writes for the same issue, column for column —
  asserted by rebuilding into a second store and comparing, not by re-listing the columns in the
  test (a test that enumerates columns passes a schema change it should have caught).
- Mirroring does not move `cursor.since`, `cursor.etag`, or `cursor.coverage_confirmed_at` —
  each asserted individually, with the cursor pre-seeded to a known value.
- Mirroring into a project with **no store** creates nothing: `cache_path` still absent afterward,
  and the returned envelope says why. (The failure this prevents: a one-item store that answers
  `open-items` authoritatively and wrongly.)
- The derived indexes travel with the row — `item_affected` and `item_alias` re-derive, and FTS
  finds the mirrored text where FTS5 is available.
- An issue that decodes as out-of-scope evicts its row rather than upserting it.
- A `sqlite3.Error` inside the mirror returns an `error` envelope rather than propagating.

**Done when** — acceptance criteria pass, full suite green, `/prawduct:critic`, chunk committed.

---

## Chunk 02: Wire the eligible write paths, and make a future op fail something

**Deliverables**

- `core.file_item`, `core.set_status`, `core.update_item` and `core.link`/`unlink` take an injected
  `absorb: Callable[[dict, str, str], None] | None`, called with the authoritative post-write
  issue each already holds **plus the item's resolved `owner`/`repo`**, typed as `core.Absorb`.
  (`_related` takes no callback in the shipped shape — it *returns* the updated issue, or `None`
  when the write was an idempotent no-op, and `_mutate_edge` mirrors it. Better than threading a
  callback two levels down, because "there was nothing to mirror" becomes a value rather than a
  branch inside the writer.) `core` imports neither
  `cache` nor `sync` — the seam keeps it provider-only and the callback testable without a store.
- ~~**The scope guard**~~ — **shipped early, in Chunk 01. Nothing left to build here.** It was
  specified for this chunk, then subsumed by the fix for Chunk 01's blocking finding: requiring a
  `cursor` row for the scope answers "was this store ever synced?" and "does this store hold this
  repo?" with one check. The shipped API is **`cache.cursor_scopes(conn)`** returning the covered
  scopes (`None` on a read failure, which is a distinct answer from `[]`), with the membership test
  at the `sync.absorb_issue` call site — *not* the `cache.holds_scope(conn, scope)` this plan named
  before the code existed, which a builder would grep for and never find. Cache Spec §6.1 carries
  the rule; `test_a_mirror_skips_an_item_outside_the_stores_scope` carries the behaviour.
  **Chunk 02 must not re-add a comparison against the caller's `--repo`** — that is the weaker
  check this replaced, and a command run wholly against another backlog satisfies it vacuously.
  What Chunk 02 still owes is only the callback's `owner`/`repo` arguments, which come from `nid`
  rather than from the issue JSON: `nid` has already resolved them, and re-deriving from
  `repository_url` would be a second, weaker spelling of a fact core already holds.
- `cli.py` binds the callback for `file`, `status`, `update`, `link`, `unlink`.
- **`merge` does NOT inherit it for free** — corrected during Chunk 01, where the plan had claimed
  it would. `migrate.merge` calls `core.set_status` itself (`migrate.py:1747`) with no callback to
  forward, so `merge` must take and thread one. The good half of the original claim survives: it
  closes its source *through* `set_status`, whose final `get_issue` already reflects the
  `superseded_by` body written a step earlier, so one mirror at that point carries both the
  redirect and the closed status. `migrate.py:1352` (`import`'s per-item status write) stays
  callback-free deliberately — the post-import sync in Chunk 03 covers the whole run at once.
- A mirror failure appends a warning to the write's envelope; the write still reports `ok`.
- A partition test over `_WRITE_OPS`: every op is classified mirrors / does-not-mirror with a
  recorded reason, so an op added without a decision fails a test rather than silently shipping
  a stale read.

**Acceptance criteria**

- Through the CLI, against a fake transport and a real store: `file` then `cache-query resolve`
  finds the new id; `status --to shipped` then a cache read reports `shipped`; `update` moving
  `stage`/`area`/`affected`/`working-branch` is reflected, including in `item_affected`;
  `link --edge related` updates the mirrored body; `merge` leaves the source mirrored as dropped
  and redirected.
- **No additional provider request is spent** — asserted by counting transport calls with the
  mirror on and off and comparing, which is the positive control the learnings rule demands rather
  than an assertion that the count equals a number I typed.
- A store that cannot be written leaves the write `ok` — asserted end to end, not against an
  injected stub, because a stub returns an envelope and so can only prove the envelope is handled,
  never that nothing *raises* on the way there.
  **[DEPARTURE from this criterion as first written | it said "missing, or locked … with a warning
  naming the cause, asserted for both". A MISSING store now passes silently: a repo with no cache
  is not a degraded mirror, it is a repo not using one, and every read already reports that
  condition with the command that fixes it — warning per write would restate a known condition
  where nothing is wrong and nothing is lost, since the next sync picks the item up by watermark.
  Written from the mechanism at plan time rather than from the caller's experience. Cache Spec §6.1
  carries the rule; `test_an_absent_store_is_silent` carries the behaviour | user can
  veto/override]**
- A write to an item in a repo other than the store's scope mirrors **nothing** and warns about
  nothing: the store is unchanged and the envelope carries no mirror warning.
- `core` write functions still work with `absorb=None`, and no `core` module imports the store.

**Done when** — acceptance criteria pass, full suite green, `/prawduct:critic`, chunk committed.

---

## Chunk 03: `import`, the reader-facing surfaces, and the coherence sweep

**Deliverables**

- After a successful `import`, an incremental sync when a store exists (a bulk create holds no
  single issue to mirror). Skipped, with a reason, when there is no store.
- `plugin/skills/backlog/cache-reads.md`, `adapter-mode.md` and any surface stating the store's
  freshness contract: state that a local write is reflected immediately and that the visible age
  still measures the last confirmed FETCH — the two are different claims and a reader who conflates
  them will misread a young age as coverage.
- `documentation/backlog-service-test-specifications.md` gains the cases this plan pins.
- Change-log entry (statusless, no `release=` tag — release-pending is statusless by design),
  `#627` closed via `/prawduct:backlog`, learnings entry if the cycle produced a durable rule.

**Acceptance criteria**

- `import` against a warm store leaves every imported item cache-visible; against no store it
  reports the skip rather than creating one.
- The prose surfaces state the write-reflection contract without a fourth copy of the invocation
  rules — routed to `cache-reads.md` the way Chunk 06 of the parent plan routed the others, and
  `tests/test_cutover_prose_coherence.py` still passes.
- No document still describes the cache as refreshed only by `sync` and the session-start warm.

**Done when** — acceptance criteria pass, full suite green, `/prawduct:critic cumulative`
(serving as this plan's final review), chunk committed.

---

## Status

- [x] Chunk 01: The mirror primitive — and the three negatives that keep it honest
- [x] Chunk 02: Wire the eligible write paths, and make a future op fail something
- [ ] Chunk 03: `import`, the reader-facing surfaces, and the coherence sweep

**Context:** Branch `fix/backlog-cache-write-path` off `develop`, baseline 4214 passed / 7 skipped.
Tracking item **#627**. The requirement's home is `documentation/backlog-service-cache-spec.md`
§6.1, added at plan time; it restates a property Data Model §1 and NFR §4 already assert rather
than adding a new one. This lands before v3.2.8 cuts — `backlog-cache` is the release-pending
scope the fix belongs to.

**Chunk 01 shipped `3434305`** (fixes `9fa0a0d`), suite 4227 passed / 7 skipped at that point. Review
`rev-20260808T062229Z-56ca858e` returned 1 blocking / 1 warning / 1 note, all three fixed in the
chunk's own commit.

**The blocking finding is the one thing a Chunk 02 builder most needs to know, because the guard it
produced is now load-bearing in two directions.** `open_store(create=False)` proves a *file*
exists, not that a sync ever ran — `_ensure_schema` commits the schema in its own transaction, so a
rebuild whose `replace_items` step then fails leaves a schema-only store with `item` and `cursor`
both empty. One mirrored row into that serves, through `cachequery._freshness`'s row-stamp
fallback, a payload of **one item aged 0.0 seconds** (measured directly, not reasoned about). So
`sync.absorb_issue` requires a `cursor` row for its scope, and that single check also *is* the
cross-repo scope guard Chunk 02 was going to add at the binding: no row at all → unsynced, error;
a row for another scope → silent `skipped: out-of-scope`. **Chunk 02 must not re-add a scope
comparison against the caller's `--repo`** — that is the weaker check the store-side one replaced,
and duplicating it would put the decision in two places with the wrong one winning on a command
run wholly against another backlog.

Also settled in Chunk 01, so Chunk 02 can rely on it: `absorb_rows` catches the parse errors its
index re-derivation can raise, not only `sqlite3.Error`, so `absorb_issue`'s "never raises" is
literally true and the callback seam does not need its own wrapper for that. **That sentence is
load-bearing for the next chunk, so it is tested rather than asserted** — the verify round's
blocking finding was that I had written it while exercising only the `sqlite3` arm that already
worked. `test_a_mirror_failure_comes_back_as_an_envelope` is now parametrized over all five arms of the catch.

The verify round also left two things recorded rather than fixed, both cheap and both taken in the
same commit: `cursor_scopes` distinguishes `None` (unreadable) from `[]` (never synced), because
sending an operator to run a sync when the store is not answering points them at the wrong repair;
and this plan's Chunk 02 section no longer names a `holds_scope` function that was never built.

**Left open deliberately:** the record-lint's four `governed-by-gap` counts against this plan
(3 of 7 data-model norms dispositioned, 3 of 8 architecture, 2 of 3 security-model, 2 of 3
api-contract). The `governed_by` preamble states the position — this is a delta on a corpus already
dispositioned norm-by-norm in `build-plan-backlog-cache.md`, and re-transcribing thirty unchanged
judgments is not judgment. The lint wants each absent norm to say "inapplicable, because —" in its
own words. Accepted as a record-only gap rather than fixed.
