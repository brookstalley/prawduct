# Issue #836 — backlog-service: `get` returns a null `updated_at`, blocking CAS on `update`: Requirements

`status: draft · stage: requirements · area: backlog-service · added: 2026-09-27 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/836`

Related: #835 (found in the same investigation — `link --edge related` writes only one side of an
edge; independent defect, no overlap with this item's fix). #745 (named in the issue's own
`related:` block; not opened by this document — no dependency found).

## Problem

`update --if-updated-at <ts>` is the optimistic compare-and-set (CAS) guard on `update`
(`core.update_item`, CC2 — api-contract.md §2 "Concurrency / consistency"): the caller reads an
item, later writes it back with the `updated_at` it read, and a live mismatch returns a retryable
`conflict` instead of clobbering a concurrent edit. The paired read the CLI otherwise offers for
this — `get <id> --json`, whose `data` is exactly the item projection `update` returns on success —
does not carry `updated_at` at all: `jq -r '.data.updated_at'` against a `get` response reads
`null`. The CAS token the write consumes is not obtainable from the read the dance is built around.
It exists elsewhere (`cache-query resolve` returns it, because the cache stores the column
directly), but nothing states that, so a caller doing the documented read-then-write sequence gets a
silent `null` and has no path to the working value without already knowing the cache exists and
querying it separately.

The issue's own evidence names this as a verbatim instance of a standing learnings rule: *"When a
skill/runbook has the model do a read-then-write CLI dance… verify the READ actually SURFACES the
field the write consumes."* It further predicts, and reports as confirmed, that this class survives
static review (prose-vs-code) and is caught only by performing the dance live.

## Grounding facts

Re-verified against the current tree (`develop`, 2026-09-27):

- **`get_item` (`plugin/lib/backlog/core.py:294-363`) returns `item, warnings = encode.decode_item(issue,
  canonical_id=nid.canonical)` unmodified into `ok(item, warnings)`.** `issue` here is the raw
  transport payload — `issue.get("updated_at")` on it is populated (it is exactly the value CC2
  compares against three lines later, at `core.py:845`, and the value the `conflict` error's
  `actual_updated_at` detail is built from at `core.py:851`). The gap is not in the transport; it is
  that `get`'s response is the *decoded* item, and decoding drops the field before it reaches the
  caller.
- **`encode.decode_item` (`plugin/lib/backlog/encode.py:1053-1128`) has no `updated_at` key, and no
  `created_at` key, anywhere in the item dict it builds.** The dict is built as a literal with 20
  named fields (`id`, `number`, `node_id`, `title`, `body`, `status`, `stage`, `kind`, `area`,
  `effort`, `impact`, `source`, `assignee`, `tags`, `affected`, `working_branch`, `automated`,
  `url`, `comments_count`, `labels`, `id_aliases`, `superseded_by`, `block_version`, `refs`,
  `revisit`, `closed_by`, `reviewed`) — neither timestamp is among them. This is why `get --json`
  reports `null` rather than a KeyError under `jq`: the key is simply absent from the payload, and
  `jq` renders a missing key as `null`.
- **The data model's own Item table never lists `updated_at` as a projected field of the entity `get`
  returns.** `documentation/backlog-service-data-model.md` §1.1 ("Item (one GitHub issue)") is a
  field-by-field table (`id`, `node_id`, `title`, `body`, `status`, `stage`, `area/effort/impact/
  source/kind`, `tags`, `affected`, `working-branch`, `reviewed`/verification, `assignee`,
  `relationships`, `provenance`, `history`, `comments`, `closed_by`) — `updated_at` is not a row.
  It is referenced only in prose, twice, as the *authority* for two unrelated things: the CAS
  comparand (§1.2, "a second, forgeable copy would answer nothing" — the sentence arguing `reviewed`
  should NOT get a stored mirror, using native `updated_at` as the reason it's unnecessary) and the
  stale-items sweep's date source (§1.2, same paragraph; also `core.py:733-734`, `:926-928`). Neither
  mention states that `get` projects it. The API contract (`documentation/backlog-service-api-contract.md`
  §2/§4.1) names `update`'s CAS as "optimistic CAS on state/`updated_at`" but likewise never states
  that `get`'s response carries the comparand the caller needs to perform that CAS. **The design gap
  predates this bug**: the data model specifies the CAS mechanism's write side in detail and is
  silent on the read side it depends on.
- **The cache path already carries the field correctly**, which is why `cache-query resolve` answers
  where `get` doesn't: `cache.py`'s `item` table has an `updated_at` column (data-model §6, the W1
  cache schema row), populated from the same native field, and `cachequery.py:795-797` includes
  `"updated_at": row["updated_at"]` in its own row projection. The inconsistency is specifically that
  the **live, authoritative** read (`get`) omits a field the **derived, optionally-stale** cache read
  (`cache-query resolve`) includes.
- **`created_at` has the identical gap and the identical two-line prose-only mention**
  (`core.py:733`, data-model §1.2 "for which the native `created_at` is a better answer than any
  stored copy"), but no open issue or acceptance criterion names it, and #836's own repro, Actual,
  and Expected sections are scoped to `updated_at` only.
- **The CAS write side already degrades safely on conflict**: `core.update_item`'s `conflict` error
  (`core.py:844-853`) returns both `expected_updated_at` and `actual_updated_at` in its `details`,
  so a caller who *does* reach a conflict (via any source for the expected value) can recover the
  current value from the refusal itself. The gap this item closes is specifically the **first** read
  in the dance — before any write has been attempted — which has no such fallback.
- **No test in the suite asserts `get`'s JSON response carries `updated_at`.** `tests/test_backlog_core.py`
  exercises CC2 (`test_cc2_stale_updated_at_is_conflict_retryable`, `test_cc2_fresh_updated_at_succeeds`,
  lines 684-698) by reading `fake.get_issue(...)["updated_at"]` directly off the **fake transport**,
  never through `core.get_item`/`encode.decode_item` — exactly the gap the learnings rule predicts: a
  test built from the same mental model as the code (comparand obtained from the transport layer) does
  not exercise the path a real caller uses (comparand obtained from a CLI read).

## Decisions

**1 (new). Fix the read side, not the write side.** `update`'s CAS mechanism (CC2) is correct and
unchanged by this item — the defect is that its paired read cannot supply the token it consumes.
Grounded above: the write already handles conflict and non-conflict cases correctly once it has an
`expected_updated_at`; nothing about `update_item` needs to change.

**2 (new). Scope is `updated_at` only, per the issue; `created_at`'s identical gap is named but not
required here.** The issue's Actual/Expected/Acceptance are stated entirely in terms of
`updated_at`, and no acceptance criterion or repro touches `created_at`. Both fields share one
root cause (`decode_item`'s field literal omits provider timestamps) and the cheapest fix touches
both at once, but requiring `created_at` here would be answering a question this issue never asked.
Design decides whether to fix both in one change (Requirement BLG-836-3 leaves this open) or file a
sibling item for `created_at`.

**3 (new). The projected field is a plain top-level key on the item, matching the shape of every
other native-authoritative field already in `decode_item`'s literal** (`id`, `number`, `status`,
etc.) — not a nested structure, and not exposed only through a new flag. The issue's Expected states
"`get` surfaces `updated_at`," and every existing consumer of `get --json` already reads the item as
a flat dict; a CAS token gated behind an opt-in flag would reproduce the same discoverability
failure this issue reports (the fallback that already exists, `cache-query resolve`, is
"undiscoverable without already knowing it" per the issue's own Problem statement).

## Requirements

MUST unless marked SHOULD. Prefix `BLG-836`, scoped to this item alone.

- **BLG-836-1** `encode.decode_item` MUST include `updated_at` (the native provider value, the same
  one `core.update_item`'s CC2 compares against) as a top-level key in the item dict it returns, so
  every caller of `get_item` — and therefore `get`/`show` at the CLI — carries it (Decision 1, 3).
- **BLG-836-2** The value returned MUST be byte-identical to the value `core.update_item`'s CAS check
  compares against for the same item at the same instant (i.e., both read the same raw transport
  `issue["updated_at"]`, with no reformatting or truncation introduced in `decode_item`) — a caller
  round-tripping `get`'s output straight into `update --if-updated-at` MUST succeed against an
  unmodified item.
- **BLG-836-3** Whether `created_at` is fixed in the same change is a design-stage decision (Decision
  2); if design defers it, it MUST be filed as its own item rather than silently left with the
  Grounding-facts gap unrecorded anywhere.
- **BLG-836-4** At least one test MUST exercise the fix through the same path a real caller uses —
  `core.get_item` (or the CLI's `get`) against a fake/stub transport, asserting the returned item's
  `updated_at` equals the transport's `updated_at` — not solely a test reading the transport layer
  directly (Grounding facts: the existing CC2 tests do the latter and did not catch this).
- **BLG-836-5** The fix MUST NOT change `update_item`'s CAS semantics, its `conflict` error shape, or
  any other decoded-item field (Decision 1) — this is an additive field on the read side only.
- **BLG-836-6** Design MUST decide whether `documentation/backlog-service-data-model.md` §1.1's Item
  table is amended to list `updated_at` (and, if BLG-836-3 includes it, `created_at`) as a projected
  field with its authority and justifying consumer (matching every other row's shape) — leaving the
  table silent on a field the mechanism now depends on would reproduce the documentation gap that
  let this bug ship undetected (Grounding facts).

## Acceptance

- [ ] `get <id> --json` (and `show`, its alias) returns a non-null `data.updated_at` for any item
      that has one at the provider.
- [ ] The value returned by `get` for an item, fed directly into
      `update <id> --if-updated-at <that value> --<some field> <value>` with no intervening edit,
      succeeds (does not return `conflict`).
- [ ] A test exercises this through `core.get_item` (or the CLI dispatch), not only through direct
      transport-layer assertions.
- [ ] `update_item`'s CAS behavior, conflict details, and every other field of the decoded item are
      unchanged.
- [ ] The data-model documentation gap (§1.1 not listing `updated_at`) is either closed in this
      change or explicitly deferred with its own tracking note (Requirement BLG-836-6).

## Scope-out (this item)

- #835 (`link --edge related` one-sided write) — a distinct defect found in the same investigation,
  with its own issue and no shared fix surface.
- Any change to `update_item`'s CAS logic, retry behavior, or the `conflict` error shape — CC2 is
  correct today and is not being redesigned (Decision 1).
- `list` and `pick`'s item projections — this item's repro, Actual, and Expected are scoped to
  `get`; whether `list`/`pick` should also carry `updated_at` is not raised by the issue and is not
  decided here.
- `created_at`'s identical gap, unless design elects to fold it in under BLG-836-3.
- Any change to `cache-query resolve`, which already surfaces the field correctly and is not part of
  the defect.

## Evidence / references

- `plugin/lib/backlog/core.py:294-363` (`get_item`) — the read path returning the decoded item with
  no `updated_at`, and `:844-853` (CC2 CAS check + `conflict` details) — the write-side consumer of
  the field this item's fix must match exactly.
- `plugin/lib/backlog/encode.py:1053-1128` (`decode_item`) — the field literal omitting `updated_at`
  and `created_at`, the single point this item's fix touches.
- `plugin/lib/backlog/cachequery.py:795-797` — the cache-side projection that already includes
  `updated_at`, confirming the value is available and correctly named upstream; the fix mirrors this
  shape into the live read path rather than inventing a new one.
- `plugin/lib/backlog/cli.py:775` (`_run_update`, `expected_updated_at=flags.get("if-updated-at")`)
  — the CLI flag the fixed `get` output must round-trip into without transformation.
- `documentation/backlog-service-data-model.md` §1.1 (Item table) — the entity projection this
  item's fix (and possibly its documentation, BLG-836-6) extends; §1.2 — the two prose-only mentions
  of native `updated_at` as an authority, neither of which states `get` projects it.
- `documentation/backlog-service-api-contract.md` §2 (`get`/`update` rows), §4.1 ("optimistic
  compare-and-set on state/`updated_at`") — the contract naming the mechanism this item makes
  usable from its own documented read.
- `tests/test_backlog_core.py:684-698` (`test_cc2_stale_updated_at_is_conflict_retryable`,
  `test_cc2_fresh_updated_at_succeeds`) — the existing CC2 coverage, which reads
  `fake.get_issue(...)["updated_at"]` at the transport layer and would not have caught this gap;
  Requirement BLG-836-4's target for the missing case.
- `.claude/rules/learnings/core.md` — "When a skill/runbook has the model do a read-then-write CLI
  dance… verify the READ actually SURFACES the field the write consumes" — the standing rule the
  issue cites as predicting this exact class, and the reason BLG-836-4 requires a live-path test
  rather than a static one.
