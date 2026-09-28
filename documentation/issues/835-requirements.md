# Issue #835 — backlog-service: `link --edge related` writes only the source item: Requirements

`status: draft · stage: requirements · area: backlog-service · added: 2026-09-28 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/835`

Related: #836 (closed sibling from the same 2026-09-18 investigation, already shipped
— `documentation/issues/836-requirements.md` — no overlap: that item is `get`'s missing
`updated_at`, this one is `related`'s one-sided write). #724 (the item this bug was found
against; load-bearing evidence below, no `documentation/issues/` doc of its own). #751
("backlog-service: merge has no inverse" — a different asymmetry in the same relationship
surface, not opened by this document; noted in Scope-out).

## Problem

`link <id> --edge related <target>` and its `unlink` counterpart are meant to be a single
logical operation on an undirected edge between two items, but the implementation writes only
the **source** item's body block. The target is never touched. The edge is therefore
discoverable by reading the source and invisible by reading the target: `get 835 --json` shows
`related: [...836...]`, but `get 836 --json` (before this fix) shows nothing pointing back.

This was found by doing the work, not by reading code or writing a test: filing #829–#836 on
2026-09-18 wrote nine `related` edges naming #724, and only a later read of #724 itself revealed
that none of them had landed there. #724 had no `prawduct:` block at all until an unrelated body
edit created one for other reasons.

## Grounding facts

Re-verified against the current tree (`develop`, 2026-09-28).

- **The five typed edges are not uniform, and `related` is the one exception.**
  `_EDGE_TYPES = ("blocks", "blocked-by", "parent", "child", "related")` (`core.py:1054`).
  `blocks`/`blocked-by` are native GitHub issue dependencies (`_dep`, `core.py:1154-1164`,
  calling `transport.add_blocked_by`/`remove_blocked_by`); `parent`/`child` are native
  sub-issues (`_sub`, `core.py:1167-1177`, calling `transport.add_sub_issue`/`remove_sub_issue`).
  Both pairs are a single provider-side API call each, and GitHub's own graph makes the edge
  queryable from either end — there is no "one-sided" state possible for them, so this bug is
  structurally confined to `related`. `related` has **no native GitHub edge** (`core.py:1049-1053`
  comment, restated at `:1133-1138`); it is carried as a `related: [id, id, ...]` list inside the
  item's own `prawduct:` body block (`encode.upsert_block_field`), which is why it is the one edge
  type whose "both ends" is two independent writes rather than one API call.
- **`_related` (`core.py:1180-1205`) operates on exactly one item.** It takes `nid` (the item being
  written) and `target_canonical` (the *value* to add/remove from `nid`'s list) — there is no
  parameter or code path that touches the target item's own block. `_mutate_edge`'s `related`
  branch (`core.py:1133-1141`) calls it exactly once, on `nid`:
  ```
  written = _related(transport, nid, tid.canonical, add=add)
  if written is not None:
      _mirror(absorb, written, nid.owner, nid.repo)
  ```
  `tid` (the already-resolved target `NormalizedId`, `core.py:1113-1119`) is never passed to
  `_related` a second time with the roles reversed.
- **The op is idempotent by contract and this stays true for a symmetric write.** API contract
  §2.3 rates `link`/`unlink` "yes" for idempotent (DM3, `documentation/backlog-service-api-contract.md:96`).
  `_related` already handles this per-item: `current = set(...)`, `.add`/`.discard`, and a no-op
  detected by `new_body == old_body` returning `None` rather than re-writing an unchanged body
  (`core.py:1195-1204`). The same per-item idempotency applies unchanged to a second call on the
  target — nothing about it is set-specific.
- **`tid` already carries everything a second write needs, at no extra resolution cost.**
  `_mutate_edge` resolves both `nid` and `tid` up front via `resolve_ref` (`core.py:1108-1119`),
  including cross-repo targets (`default_repo`/`--repo`, `NormalizedId.owner`/`.repo`/`.number`).
  A target-side write is `_related(transport, tid, nid.canonical, add=add)` — the same function,
  the mirrored argument order, no new resolution or validation needed. The existing self-link
  guard (`nid.canonical == tid.canonical`, `core.py:1120-1121`) already rules out the one case
  where writing "both ends" would collide with itself.
- **The local mirror already degrades safely for a target in scope nothing the current store
  covers**, which matters because a `related` target is very often cross-repo (this project's own
  edges point at issues in other consumer repos as often as within one). `_mirror`
  (`core.py:79-95`) is a thin `if absorb is None: return` guard around an injected callback; the
  CLI's bound `absorb` (`cli.py:1485-1520`) calls `sync.absorb_issue`, which already tags an
  out-of-store-scope write `details["mirror"] = "absent"` and reports it as a **warning**, never a
  failure — "an item outside the store's scope is likewise a correct write this cache was never
  meant to hold" (`cli.py:1472-1479`). Calling `_mirror` a second time for the target, with the
  target's own `owner`/`repo`, reuses this existing degrade-safely path; it does not need new
  scope-detection logic.
- **The local cache has no `related` column to keep in sync — the mirror problem is smaller than
  it first looks.** `item` table schema (`cache.py:131-146`): `id`, `title`, `body`, `status`,
  `stage`, `area`, `effort`, `impact`, `source`, `created_at`, `updated_at`, `affected`,
  `working_branch`, `fetched_at`. There is no `related` field; `related` is read out of the raw
  `body` column at query time (`encode.parse_list`/`parse_block` over the stored body text, the
  same decode `get_item` runs live). So once the target's body is written on the provider and
  mirrored, the target's cache row's `related` list is correct automatically — there is no second,
  separately-shaped sync path to build.
- **A structurally identical bidirectional-consistency problem was already solved once in this
  codebase, for `closed_by`, and solved by *accepting* that drift needs a periodic sweep rather
  than a synchronous double-write.** `documentation/backlog-service-api-contract.md`'s C1 fold
  (top-of-file changelog, `:3`): `closed_by` is "native-timeline-authoritative on close-on-merge, an
  optional handle on manual close, and the bidirectional drift sweep is a janitor workflow." That
  precedent is for a *different* kind of asymmetry (one native field two closing paths can leave
  stale) and is not a reason to prefer a sweep over a synchronous write here — `related` has no
  native timeline to reconcile against, and the fix is cheap (one more call, already idempotent,
  already mirror-safe) — but it is the precedent to point at if this item's Scope-out (backfilling
  the nine already-broken edges from #829–#836) is picked up later.
- **No existing test exercises the target side.** `tests/test_backlog_link.py` covers self-link
  rejection, bad-id rejection, source-side storage (`test_related_stored_in_block_list`),
  source-side unlink (`test_related_unlink_removes_from_list`), and a multi-block merge case
  (`test_related_keeps_edges_from_an_earlier_block`) — all read back the **source** item's body
  only (`core.py` test file, lines 130-198). None reads the target item back after a `link`/`unlink`
  call, which is why this class shipped and stayed shipped through #835's own filing (#829–#836
  were filed *using* the broken op).
- **Error handling is a single boundary today, and a second write changes what "the op failed"
  can mean.** `_mutate_edge`'s body is one `try` covering both writes it currently makes plus
  resolution (`core.py:1107-1147`); a `TransportError` from anywhere in it returns
  `from_transport_error(exc)` (ERR-6, `core.py:1-10`, "never swallowed"). Today that boundary is
  safe because there is only one provider write to fail. Adding a second, independent provider
  write means the boundary can now be crossed *after* the first write has already landed on the
  provider — the same "the mutation already happened, don't tell the caller to retry into a
  duplicate" shape `cli.py:1467-1470` documents for the mirror, but here for a real provider write,
  not a local one, which is a stronger case.

## Decisions

**1. `related` becomes a symmetric write: `link`/`unlink --edge related` write both the source
item's and the target item's `prawduct:` block in one logical call.** This is the issue's own
preferred resolution ("either both ends carry the edge, or the op's output says it wrote one
end... the second is weaker, it depends on recall"). Nothing in the Grounding facts makes the
strong form expensive: `tid` is already resolved, `_related` is already a one-item function ready
to be called a second time with roles reversed, and both idempotency and mirroring already hold
per-item.

**2. This item does not touch `blocks`/`blocked-by`/`parent`/`child`.** Those four are native
provider edges, queryable from either end by construction (Grounding facts) — there is no
one-sided state for them to have, and the failure this item fixes cannot occur there.

**3. The two provider writes are sequential and not transactional; the target write's failure
after a successful source write is a distinct, reportable outcome, not folded into the same
undifferentiated `TransportError` result as a failure before anything was written.** There is no
multi-issue transaction available from a REST issues API, so "both ends or neither" cannot be
made atomic. What can be done cheaply: keep writing source-then-target (preserves today's
observable order for the source-only regression tests), and when the target write raises after
the source write already returned a written issue, report that the source side is already
changed rather than returning a bare error that reads as "nothing happened" — mirroring the
reasoning `cli.py:1467-1470` already applies to the (weaker) mirror-write case, one level up, to a
real provider write.

**4. A second `_mirror` call is made for the target write, addressed with the target's own
`owner`/`repo`**, reusing the existing `absorb` callback and its existing out-of-scope/cross-repo
degrade-to-warning behavior (Grounding facts) — no new mirror-side logic.

**5. Backfilling the edges this bug already wrote one-sided (#829, #831, #832, #833, #835, #836 →
#724, per the issue's own repro) is out of this item's scope**, per Decision-adjacent Grounding
fact on the `closed_by` sweep precedent — named explicitly rather than silently dropped, since a
`related` value one-sided today will stay one-sided after this fix ships until either hand-fixed
or a future sweep (Scope-out).

## Requirements

MUST unless marked SHOULD.

- **REL1** `link <id> --edge related <target>` writes `related` into **both** the source item's
  and the target item's `prawduct:` body block, in a single `link` call — verified independently
  by reading each item back.
- **REL2** `unlink <id> --edge related <target>` removes `related` from **both** blocks in a
  single `unlink` call.
- **REL3** The per-item idempotency `_related` already provides (a repeat write that changes
  nothing returns `None`/no-op rather than re-writing) holds independently on each side: a `link`
  call repeated after a full success is a no-op on both sides; a `link` call repeated after a
  **partial** success (source written, target not) completes the missing side without erroring or
  duplicating the already-written side.
- **REL4** `blocks`, `blocked-by`, `parent`, `child` are unchanged by this item (Decision 2).
- **REL5** The existing self-link guard and unknown-edge/bad-id validation (`core.py:1102-1121`)
  run before either write, unchanged, and still short-circuit both writes on failure.
- **REL6** If the target-side write fails after the source-side write already succeeded, the
  result distinguishes this from a failure before any write happened — the caller can tell "the
  source now carries the edge, the target does not yet" from "nothing changed" without a
  follow-up `get` (Decision 3). The exact shape (an `error` envelope with a detail key, a partial
  `ok` with a warning, or something else) is a design-stage decision, not fixed here.
- **REL7** Each write (source and target) is independently offered to the local mirror via the
  existing `absorb`/`_mirror` path, addressed with that write's own `owner`/`repo`, reusing the
  existing out-of-scope/cross-repo degrade-to-warning behavior (Decision 4) — no new mirror-scope
  logic is introduced.
- **REL8 (SHOULD)** The CLI/MCP-facing help text for `link`/`unlink` (`cli.py:164-168`) is updated
  if REL6's chosen error/warning shape introduces a new observable detail an operator would need
  to recognize; not required if the shape is a strict subset of today's envelope vocabulary.

## Acceptance

- [ ] `link A --edge related B` (both in the same repo) leaves `related` containing `B` in `A`'s
      block **and** `related` containing `A` in `B`'s block, each confirmed via an independent
      `get`.
- [ ] The equivalent cross-repo case (`A` and `B` in different repos, or `--repo` targeting a
      different default) writes both sides correctly, and each side's mirror attempt degrades to
      a warning (never a failure) when that side's repo has no local store in scope, unchanged
      from today's single-sided behavior.
- [ ] `unlink A --edge related B` removes the edge from both blocks, confirmed the same way.
- [ ] Calling `link A --edge related B` twice in a row is a no-op the second time on both sides
      (no duplicate list entries, no unnecessary body write).
- [ ] A test simulates the target-side write raising after the source-side write has already
      landed, and asserts the source-side change is not lost and is distinguishable in the result
      from a pre-write failure (REL6).
- [ ] `blocks`/`blocked-by`/`parent`/`child` link/unlink tests are unaffected (regression, not new
      coverage) — confirming Decision 2's scope boundary held.
- [ ] `tests/test_backlog_link.py`'s existing source-side assertions
      (`test_related_stored_in_block_list`, `test_related_unlink_removes_from_list`,
      `test_related_preserves_the_prawduct_block`, `test_related_keeps_edges_from_an_earlier_block`)
      continue to pass unmodified in their source-side assertions, extended (not replaced) with
      target-side assertions.

## Scope-out (this item)

- Backfilling the nine `related` edges already written one-sided before this fix (#829, #831,
  #832, #833, #835, #836 → #724) — a data-repair concern, not a code-behavior concern; the
  `closed_by` bidirectional-drift-sweep precedent (Grounding facts) is the shape such a repair
  could take if picked up separately.
- `blocks`/`blocked-by`/`parent`/`child` — native, already symmetric, out of scope (Decision 2).
- #751 ("merge has no inverse, so a reopen keeps redirecting") — a different asymmetry on a
  different mechanism (`merge`, not `link --edge related`); not opened or resolved by this item.
- The exact wire shape of REL6's partial-failure signal (new error code, warning-on-`ok`, a
  `details` key on the existing `error` envelope) — design-stage.
- Any change to how `related` is displayed or queried (`cache-query`, `get --json` rendering) —
  this item is about what gets written, not how it is read back; reads already work correctly
  once both sides are written.

## Evidence / references

- `plugin/lib/backlog/core.py:1-10` (op envelope / ERR-6 convention), `:1047-1054` (`_EDGE_TYPES`),
  `:1057-1088` (`link`/`unlink`), `:1091-1151` (`_mutate_edge`, the single write site and its one
  `try` boundary), `:1154-1177` (`_dep`/`_sub`, the native-edge comparison), `:1180-1205`
  (`_related`, the one-item write function).
- `plugin/lib/backlog/cli.py:164-168` (`link`/`unlink` help text), `:1149` (unknown-edge error
  message), `:1465-1520` (the CLI's bound `absorb`, its mirror-failure-is-a-warning contract and
  the `mirror: absent` out-of-scope marker).
- `plugin/lib/backlog/cache.py:131-146` (`item` table schema — no `related` column; confirms
  `related` is read from stored `body` text, not a separately-synced field).
- `tests/test_backlog_link.py:1-219` (existing source-side-only coverage for `related`, self-link
  and bad-id rejection).
- `documentation/backlog-service-api-contract.md:3` (C1 fold — the `closed_by`
  bidirectional-drift-sweep precedent), `:96` (`link`/`unlink` idempotency rating, DM3).
- GitHub issue #835 — problem statement, repro, and the "both ends, or the op says it wrote one
  end" framing this document adopts as Decision 1.
- GitHub issue #724 — the item the one-sided write was found against; its lack of a
  `documentation/issues/` doc means its own issue body/comments are the only record of the
  original repro context.
