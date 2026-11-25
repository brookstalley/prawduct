# Issue #745 — backlog-service: a deleted soft facet decodes as absent, not as lost: Design

`status: draft · stage: design · area: backlog-service · added: 2026-11-24 · issue:
https://github.com/brookstalley/prawduct/issues/745`

Scope: **leg 1 only.** Legs 2 (missing `stage:`, ENC-5(c)) and 3 (zero blocks) shipped on develop
in 1e40d9d4 and are pinned by `tests/test_backlog_decode_degradations.py`. The 2026-11-18 triage
restaged the item to design for one choice: **where does the evidence of a prior facet value come
from?** This document makes that choice and specifies the build.

## Problem

`decode_item` (`plugin/lib/backlog/encode.py`) reads `kind`/`area`/`effort`/`impact`/`source`
with `facet_value(labels, facet)`. If someone removes `area:critic` in the GitHub UI, the item
decodes with `area: None`, which looks the same as an item that never had an area. Nobody is told
that a value was lost. `_degradation_warnings` leaves this leg out on purpose, and its docstring
gives the reason: decode sees only the issue JSON, and a removed label leaves no trace there. A
warning built from that JSON alone would fire on every item that never had the facet. Many items
legitimately have no facet: `effort`/`impact` are optional at filing, and #1154 has neither today.

## Options considered

| Option | Evidence source | Verdict |
|---|---|---|
| A. Echo facets into the `prawduct:` block at write time | the block | **Rejected.** Data Model §1.2 (M5) rules these fields "label-authoritative, block-unmirrored". An echo is a second home that drifts on every legitimate UI relabel (`area:x` → `area:y` would read as a loss of `x`), so it needs its own reconciler. The hook-surface rules already learned this: "Observable beats stored", "Denormalized/derived fields maintained by independent actors drift". It would also leave every existing item with no echo, so nothing would be caught on them until each one is rewritten. |
| B. Compare against the local cache at `get` | `item` table in `backlog-cache.sqlite3` | **Rejected.** The cache "originates nothing" (`cache.py` header) and is rebuilt from the provider by `replace_items`, so after any `sync` the prior value is gone before `get` could compare against it. It has no `kind` column. It exists only in clones that run a cache. The answer would depend on when that clone last synced, so two clones could give different answers to the same question. |
| C. Read the issue's native timeline at `get` | GitHub `labeled`/`unlabeled` events | **Chosen.** It is the field Data Model §1.1 already names as `history` (CC4, native, append-only). The provider maintains it, so there is no write path, no drift and no backfill, and it covers every existing item. The transport already has `list_timeline` (used by `export`). |

## Design (option C)

### D1. Where it fires: `get`, and only `get`

`core.get_item` is the single-item drill-down read. It already pays extra provider reads for
`list_comments` (DM5) and `resolve_survivor`. The timeline check goes there, after
`decode_item`. `decode_item` stays pure: it decodes the JSON it is given and does no I/O, so
`list`, `pick`, `sync` and the post-write re-decode in `update_item`/`set_status` are unchanged
and pay nothing. A per-item timeline read on `list` would be N extra paged calls against the
80/min cap. That is a sweep's job (see Q2), not a read's.

### D2. When it fetches

Fetch the timeline only when both of these hold:

1. `encode.is_prawduct_issue(issue)`. A plain repo issue has no encoding to have damaged. This is
   the same gate `_degradation_warnings` uses.
2. At least one of `encode.OPEN_FACETS` decodes to `None`.

An item with all five facets set costs nothing. One paged call is the ceiling otherwise.

### D3. The evidence rule

For each absent facet `F`, take the timeline events whose `event` is `labeled` or `unlabeled` and
whose label name carries the `F:` prefix. Match through `encode.label_has_prefix`, which is
case-insensitive like every other facet read. Then look at the **last** such event:

- **`unlabeled`** → the facet was set and then removed. Warn:
  `` the `area:` label was removed (last value `area:critic`, by @actor on 2026-11-20); it decodes as
  absent, not as never set ``
- **`labeled`**, while the label is not on the issue now → the label was renamed or deleted
  repo-wide (see V2). Warn with the same consequence clause, naming the last value seen.
- **no such event** → never set. No warning.

There is no actor filter, because the adapter never produces a trailing `unlabeled` for a soft
facet. Verified on develop at b4659521: the only `remove_label` call sites are
`core.py:723` (status strip), `core.py:1190` (the facet swap, which runs *after* the add of the new
value) and `core.py:1209` (tags). Nothing in `plugin/lib/backlog/` replaces an issue's label set
wholesale. `add_labels` POSTs, which is additive. So a swap that crashes partway leaves two
values, never zero. A trailing `unlabeled` on an absent facet therefore comes from a human or a
non-prawduct automation. The warning names the actor so the reader can tell which. If a
clear-a-facet op is ever added, it must either leave a trace this rule can recognise or own a
carve-out here. A test pins that the rule's premise holds (T5).

The returned item is unchanged, which follows the issue's own constraint: "the loss becomes
visible, not that decode starts guessing." The last value goes into the warning text only. It is
not restored into `item[F]`.

### D4. Failure posture

A timeline fetch that raises `TransportError`/`OSError`/`JSONDecodeError` degrades the same way the
comment fetch beside it does (ERR-6). It logs a diagnostic line and adds one warning: "the
label history could not be read, so a removed `<facets>` label would not be reported". The
warning names its consequence ("degraded advice names its consequence"). The `get` still succeeds.
A 410 here does not fire `on_gone`, because the issue read already succeeded.

### D5. Transport shape

`GhTransport.list_timeline` reduces each event to `{event, actor, created_at}` today, so the
label name is dropped. Add `label: {"name": ...}` when the raw event carries one. This is an
additive key. `export`'s dump gains the field too, which only improves its "full-fidelity" claim.
No pinned consumer reads the reduced key set: `export` serialises the whole dict, and
`tests/test_backlog_pagination.py` counts events. `FakeGitHub.list_timeline` already returns stored
events verbatim, so the tests seed `state.timeline[number]` with the real shape.

### D6. Single owner

One function, `encode.facet_loss_warnings(issue, labels, timeline) -> list[str]`, owns the rule. It
is pure and takes the timeline as data, so it can be tested without a transport and a later
janitor sweep (Q2) can reuse it. `core.get_item` owns only the fetch and the failure posture. The
"deliberately not here" paragraph in `_degradation_warnings`' docstring and the matching sentence
in the test module's docstring are rewritten to point to the new owner. They must not be left
beside it, per the core rule "A mechanism change is done when every artifact DESCRIBING it agrees".

## Verify-api (before build; record full output)

- **V1.** On a scratch issue in the live repo, add and then remove an `area:` label in the UI.
  Record the raw `issues/{n}/timeline` entries, every field, and confirm `label.name` and `actor`
  are present on `labeled`/`unlabeled`.
- **V2.** Rename a repo label that a scratch issue carries, then delete one. Record what the
  timeline shows for each: the old name, the new name, or no event at all. D3's second branch is
  designed for "no event". If GitHub instead rewrites historical names to the new name, the
  rename case reads as "set and present" and needs no warning. Either way, the result decides
  whether that branch ships or is cut.
- **V3.** Check that a label removed by a GitHub Action appears with the bot as `actor`, so the
  warning's attribution is honest.

## Tests

- T1. Absent facet with a trailing `unlabeled` → exactly one warning naming the facet, the last
  value and the actor. `item[F] is None` (the value is unchanged).
- T2. Absent facet, no facet events → no warning (the never-set control).
- T3. Swap history (`labeled area:a`, `labeled area:b`, `unlabeled area:a`) with `area:b` present →
  no fetch at all, because nothing is absent (D2). Same history with `area:b` later unlabeled →
  the warning names `area:b`.
- T4. Every facet set → `list_timeline` is not called (the fake's `calls` list). A plain repo issue
  → not called.
- T5. Premise pin: drive `update_item` through every facet edit against the fake and assert that no
  absent facet ends with a trailing `unlabeled`. This is the test that fails when a future clear op
  breaks D3's no-actor-filter reasoning.
- T6. Timeline fetch raises → `get` returns `ok`, with the consequence warning (D4).
- T7. Red-verify: with `facet_loss_warnings` stubbed to return `[]`, T1 and T6 fail. Before trusting
  the green, feed the instrument a case it must catch.

## Out of scope

- Restoring a lost value. Decode does not guess (issue body, "Expected").
- Leg 1 of #231, the close-as-duplicate redirect. It needs GraphQL.
- `list`/`pick` surfacing of losses (Q2).

## Open questions for the owner

1. **Should the same evidence sharpen the shipped missing-stage warning?** Today it says "never
   staged *or* removed" because the JSON cannot tell. At `get`, the same timeline read could make
   it definite, and an absent `stage:` would join D2's fetch trigger. Recommended: yes, in this
   build. It costs no extra call when any soft facet is already absent, and one call otherwise.
2. **Does a janitor sweep belong?** A `list`-wide pass could find every silently de-faceted item
   (N timeline reads, rate-limited) by reusing `facet_loss_warnings`. Recommended: not now. File it
   only if `get`-time warnings show the loss is common.
3. **Effort/impact.** This document uses the item's existing `effort:S`. D1–D6 are roughly one chunk
   plus the V1–V3 probe.

## Grounding

Read on develop at b4659521: the issue body and the 2026-11-18 triage comment;
`plugin/lib/backlog/encode.py` (`OPEN_FACETS`, `facet_value`, `_degradation_warnings`,
`decode_item`); `plugin/lib/backlog/core.py` (`get_item`, the facet swap in `update_item`, every
`remove_label` call site); `plugin/lib/backlog/transport.py` (`list_timeline`, both the base and
`GhTransport`); `plugin/lib/backlog/cache.py` (header and `item` schema);
`tests/fakes/fake_github.py` (`list_timeline`); `tests/test_backlog_decode_degradations.py`;
`documentation/backlog-service-data-model.md` §1.1–1.2. Not verified: the GitHub timeline's
behaviour on label rename/delete and the bot-actor shape (V1–V3). Those were not probed for this
document.
