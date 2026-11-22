# Issue #1207 — evidence: disposition facts never travel to other clones: Design

`status: draft · stage: design · area: governance · added: 2026-11-22 · issue:
https://github.com/brookstalley/prawduct/issues/1207`

Requirements: [`1207-requirements.md`](1207-requirements.md) (R1–R15, A1–A7). Related: #606 (the
ledger holds reviews, never outcomes), #1052 (the notes transport), #1063 (opt-out preference, open),
#1058 (stats double-count ingested reviews, open).

**Owner rulings this design is built to (2026-11-22).** Disposition facts, all three actions
(accept, file, fixed), travel between clones on the same footing as resolutions. Q1 (backfill):
dispositions recorded before the change are sent. Q2 (budget sweeps) is not ruled; D10 carries the
requirements' recommendation as a proposal. Q3 is answered by this document existing. *The
`.prawduct/owner-rulings.md` on `develop` at `8b1847e2` does not yet hold the 2026-11-22 entry (its
top entry is 2026-11-18). It must be committed before this design is cited as ruled.*

## Research (read against `develop` at `8b1847e2`; nothing below was run unless it says so)

- **There is one writer, and it never attaches.** `dispositions.record` is the only code that appends
  a `disposition` fact. Its callers are `disposition_cmd` (the CLI) and `auto_accept` (the budget
  sweep, from `critic_consolidate._refuse_over_budget`). Neither calls `evidence_notes.attach`. Every
  other transported kind attaches where it is written: `critic_consolidate._attach_note`, and the two
  `plan` writers in `prawduct-hook` (~8998, ~9318).
- **The transport has one owner, and adding the kind to `TRANSPORTED_KINDS` is not enough.**
  `evidence_notes.attach`, `reconcile` → `unattached`, `ingest` → `_parse`, and `evidence status`'s
  count all filter on `evidence.TRANSPORTED_KINDS`. But `unattached` picks an anchor per kind:
  reviews on `review_anchor`, resolutions on their `verified_by` review's anchor, and *everything
  else* on the chunk-fact rule (counted when `actor.branch` is the checked-out branch, re-attached on
  HEAD). A disposition added to the set without its own branch there would be re-attached on HEAD,
  the wrong commit, and one recorded from a scratch branch would never count as missing.
- **Store order is not the same in two clones, and the merge makes it worse.** `disposition_index`
  keeps the last fact in store order, and `prior_dispositions` walks the store reversed. Ingest
  appends note lines in the order it reads them, and `evidence sync` merges notes with
  `cat_sort_uniq`, which sorts the lines. An envelope line starts `{"schema": 1, "kind": …, "id": …`,
  so a merged note holds `disp:R:R-1:10` ahead of `disp:R:R-1:2`, and a clone ingesting it holds the
  older answer last. (Read from `envelope_line` and the merge strategy; not run.)
- **Two clones answering one finding mint one id.** `record` computes `disp:<review>:<fid>:<seq>` with
  `seq = len(history) + 1`, stepping past ids already held. Two clones that have not seen each other
  both mint `:1`, and `(kind, id)` dedupe keeps whichever each saw first. The same applies within
  one clone today: the module docstring accepts that two racing answers "resolve to one recorded
  answer", and the loser's caller is told `recorded`.
- **`(kind, id)` is the identity in four places**: `read_facts`' dedupe (keep first),
  `ingest`'s `held` set, `attach`'s `present` check (`_keys_in`), and `unattached`'s note comparison.
- **No gate reads a disposition.** `coverage_algebra.resolution_index` filters `kind == "resolution"`.
  `plan_status._blocking_clear` reads the census, but passes a blocking row only in
  `dispositions.RESOLVED_STATES` (fixed, waived, waived-inherited). `accepted` is not in that set.
  `answered_lint_results` answers a BLOCKING lint result only with a `waived` resolution.
- **Readers of disposition facts** (by `grep` for `disposition_index`, `disposition_facts`,
  `disposition_history`, `prior_dispositions`, `census`, `finding_state`): `census` (and through it
  `render-dispositions`, the briefing's branch-findings line, `plan_status._blocking_clear` and the
  over-budget census), `prior_dispositions` (the dispatch manifest), `answered_lint_results` (lint
  re-raise suppression), `auto_accept`, `stats.finding_outcome` (and through it `stats`,
  `review-stats` via `telemetry._read_dispositions`, and `contribute`'s acted-on rates). Nothing in
  `lib/backlog/`, `contribution.py`, `aggregate.py` or `consumer_digest.py` reads a disposition's text.
- **The round budget is mostly not per worktree.** `_round_budget_verdict` counts
  `coverage.branch_review_ids(scope=…)`. That is the branch's lineage whenever `merge_base..HEAD`
  holds commits (`BOUND_LINEAGE`), and that set is the same in every clone that has synced the
  branch's reviews. Only an empty span falls back to this worktree's reviews (`BOUND_WORKTREE`), and
  the sweep's reason then says "in this worktree". The requirements' Q2 premise holds only for that
  fallback.
- **Measured on this repo's store (run, read-only, 2026-11-22):** 2,313 disposition facts (2,166
  accept, 71 file, 76 fixed; 7 with an owner ruling; 1 budget sweep), about 1.44 MB of lines next to
  1.73 MB of resolutions that already travel. 26 findings have more than one answer. On all 26, the
  winner by the key D4 picks and the winner by store order are the same, so no answer recorded
  so far changes when the key changes. No two answers to one finding share a `ts`. Every
  disposition's review is in the store and has an anchor.
- **The notes ref today (run):** 107 notes, 1.87 MB, pushed to `origin` (a public repository). 339
  of the store's dispositions answer reviews anchored on an annotated commit: about 208 KB, over 76
  reviews. That is the most a backfill could ever add to the ref here (+11%). See D7 for what it
  sends in practice.
- **Prior art:** `git branch -r --no-merged origin/develop | grep -i -e 1207 -e dispos -e evidence`
  returns nothing.

## Decisions

### D1 — The one writer attaches (R1, R2, R3)

`dispositions.record` attaches the fact it just appended, by calling `evidence_notes.attach` with the
anchor of the review the disposition answers (`evidence.review_anchor` of the review fact named by
`body.finding.review_id`). `record` already reads the store and joins the finding, so the review fact
is available without another read. This covers observations too (R3), because an observation lives
on the same review fact and has the same anchor.

- `record`'s result gains `note: {status, reason}` from `attach`. A failed attach does not fail the
  record: the fact is in the store, `evidence status` counts it, and the next `evidence sync`
  reconciles it, as `_attach_note` already works for resolutions.
- `disposition_cmd` prints a NOTE on `note.status == "error"`, worded like `_attach_note`'s, and exits 0.
- `auto_accept` returns an `unsent` count. It reaches the agent inside the `swept` block that
  `_refuse_over_budget` already returns to `critic-begin`, a CLI the agent reads, not a hook.
- Cost: two local git calls per disposition (the note read and the append), no network. A sweep of N
  findings pays 2N calls. This store holds one sweep disposition in its whole history, so the
  sweep is not batched.

### D2 — `unattached` knows where a disposition hangs (R2, R4)

`evidence_notes.unattached` gains a `disposition` branch next to the `resolution` one, with
`anchor = anchors.get(body.finding.review_id)`. A disposition whose review is not held, or is not on
this branch's commits, is not counted as missing, as with a resolution. `reconcile` needs no change,
because it attaches whatever `unattached` returns.

### D3 — `TRANSPORTED_KINDS` and its comment (R1, R8)

`disposition` joins the set. The comment loses "a builder's disposition" from its list of what stays
local, and gives one reason for each kind that does stay local:

- `guard-refusal`: a control's firing in this clone. Its yield query is per clone, by the ruling in
  `append_guard_refusal`'s docstring.
- `test-run`: a suite result is a fact about the machine and environment that ran it.
- `session-start`: a session boundary of this clone, used as the per-session denominator.

### D4 — "Newest answer wins" by a key every clone computes the same way (R6)

`answer_key(fact) = (seq, id)`. Here `seq` is the integer after the `disp:<review_id>:<fid>:` prefix,
which is built from the fact's own body, up to the next `:`. An id that does not parse gets `seq = 0`,
which ranks below every well-formed answer and never raises, so `disp:bogus:1` still reads. A
finding's winner is its fact with the greatest key. `disposition_index`, `disposition_history`
(sorted ascending by key) and `record`'s no-op check all use this one function. `prior_dispositions`
takes each finding's winner from the index, and orders entries newest-first by the winner's
`(ts, id)`. That order decides only which entries survive truncation.

**Why `seq` comes first, not `ts`.** `record` mints `seq` as one more than the highest it has seen
(D5), so an answer given after seeing another one always outranks it, in every clone, whatever the
machines' clocks say. The requirements suggested `ts` with the id as tie-break. That fails twice:

- Clock skew between two machines would let a correction lose to the answer it corrected.
- Two clones that record the same answer get the same id (D5) with two different `ts` values, and
  each clone keeps the copy it saw first. A `ts` comparison against a third answer could then go
  differently in each clone, which is the divergence R6 exists to remove.

Concurrent answers (same `seq`, recorded without seeing each other) are ordered by id. That is
arbitrary, but every clone computes it the same way. Who wins a genuine conflict was never decidable
from the record. What matters is that every clone agrees.

### D5 — An id that cannot collide across clones (R7)

New ids are `disp:<review_id>:<fid>:<seq>:<tag>`:

- `tag` is the first 12 hex characters of SHA-256 over the canonical body (`json.dumps(body,
  sort_keys=True, separators=(",", ":"))`).
- `seq` is `max(seq over the finding's history) + 1`, then steps past held ids as today. The old
  `len(history) + 1` can land *below* a held answer once a superseded line has been pruned (history
  `[:3]` alone gives 2), and under D4 that new answer would lose.

The properties that follow:

- Different answers get different ids, so both are kept in every store, the census shows D4's
  winner, and `disposition_history` shows both. This is A4.
- The same answer at the same `seq` in two clones gets one id, which is one fact. That is the right
  outcome, because it is one answer.
- Accept → file → accept still appends a third fact, because `seq` differs. That is the trap
  `test_reverting_to_an_earlier_answer_still_appends` pins against a purely content-keyed id.
- A race inside one clone keeps both answers instead of silently losing one. The docstring sentence
  that accepted the loss is rewritten.
- Legacy ids (`disp:R:F:N`, no tag) still parse. Nothing parses the id shape outside `dispositions.py`
  (grep for `disp:`), and `api-contract.md` does not name the shape.

Rejected options:

- **Dedupe that compares bodies.** `(kind, id)` is the identity in four places (Research). Changing it
  for one kind changes the store's contract, and `attach` would still call a same-id,
  different-body line `present` and never send it.
- **Writer identity in the id** (host or worktree). It would publish the machine identity that
  `sent_envelope` deliberately strips.

### D6 — Ids that already collided (R7, residual)

Two clones that answered the same finding before this change both hold a legacy `disp:R:F:1` with
different bodies. Each keeps its own. Facts are immutable, so this cannot converge without a new
answer. `ingest` counts the incoming disposition lines whose `(kind, id)` it already holds with a
different body, and says so in its `reason`: "N disposition(s) share an id with a different answer
recorded here before #1207; re-answer the finding to converge". `evidence ingest` and `evidence sync`
print that reason, and `/prawduct:pr` runs `sync`, so it has a reader. The remedy is the ordinary
one: a new answer mints `max + 1` and wins everywhere. How often this happens cannot be measured from
one clone.

### D7 — Backfill, per the Q1 ruling (send)

No new mechanism. `evidence sync` already runs `reconcile` before it pushes. With D2, `reconcile`
finds this branch's dispositions that have no note and attaches them, including ones recorded before
the change. So every branch still in flight is sent whole at its next sync, which is the ruling.

What this does **not** reach: dispositions answering reviews on branches already merged. `reconcile`
is bounded to `merge_base..HEAD`, and resolutions have had that bound since #1052, which did no
archive-wide backfill either. At most 339 dispositions here (about 208 KB) could be sent by such a
sweep. Whether to add one is open question 2. A disposition recorded *after* a branch merged is
attached locally by D1 and pushed with the whole local ref at the next sync from any branch. A
receiver gets it only through `evidence ingest --all`, exactly as for a resolution recorded at that
point.

### D8 — What each reader does after

| Reader | Change in code | Effect in a clone that did not write the answer |
|---|---|---|
| `census` / `render-dispositions` / PR-payload and change-entry census | none beyond D4 (it calls `disposition_index`) | shows the answer instead of `undispositioned`; the same winner in every clone |
| Briefing "Branch findings" line | none (census) | undispositioned-warning count drops to the true one |
| `prior_dispositions` (dispatch manifest) | D4 winner, deterministic order | lists another clone's ACCEPT/FILE under the existing scope, file and 15-entry limits (A2) |
| `answered_lint_results` | none (index) | a lint WARNING accepted or filed elsewhere is not re-raised; BLOCKING still needs a `waived` resolution |
| `auto_accept` | none (index) | skips findings already answered elsewhere |
| `stats.finding_outcome` → `stats`, `review-stats`, `contribute` | none (index) | acted-on rates count the answer; still one outcome per `(review, fid)` |
| `coverage_algebra`, `plan_status._blocking_clear`, PR and Stop gates | none | unchanged (D9) |
| `evidence status` | none | its unattached count now includes dispositions |
| Ingest's findings-cache re-derive | none | runs when only dispositions arrived and finds the cache `current` |

One cost that is not a behaviour change: `disposition` is not in `OBSERVATIONAL_KINDS`, so every
disposition appended, locally today and by ingest after this change, changes `coverage_fingerprint`
and misses the verdict memo once. `tree_key_memo` keeps that recompute cheap (`verdict_cache`'s
docstring: 0.01 s with keys in hand). Whether `disposition` belongs in that set is a separate
question, not answered here.

### D9 — Nothing that travels lifts a gate (R9, R10, R12, R13, R15)

- **R9.** Unchanged code. It is pinned by extending `TestDispositionNeverUnblocks` with dispositions
  that arrived by `ingest`, including an ACCEPT carrying an `owner_ruling` on a BLOCKING finding. The
  case asserts the coverage verdict, `_blocking_clear` and `answered_lint_results["blocking"]`.
- **R10.** A `fixed` disposition is checked against `is_judgeable_path` only in `record`. Ingest
  appends it as it stands, and `finding_state` maps it to `fixed-unreviewed` in every clone. A
  re-check at ingest would be a second judge of one claim.
- **R12.** In a clone with no notes ref, `attach` creates the local ref, as consolidation already does
  for every review, and nothing is pushed without `evidence sync`. #1063, when it lands, should put
  its switch in `attach`, `reconcile` and `sync`; dispositions then honour it through D1 with no
  site of their own.
- **R13** (read, not run; T8 pins it). A plugin from before this change skips dispositions in `_parse`
  (counted as "of a kind not transported"), ignores them in `unattached`, and keeps them through the
  `cat_sort_uniq` merge, so they reach newer clones. If an old plugin shares a store with a new one,
  it mints `len + 1`, which is still above every held `seq`, so its answer still wins under D4. Its
  own display uses store order until it upgrades. That difference is in display only.
- **R15.** `stats` maps each `(review_id, fid)` to one outcome and never counts a disposition as an
  event, so an ingested answer, or two answers in conflict, counts once. #1058's duplicate counting
  of reviews is not touched.

### D10 — Budget sweeps (Q2): proposed, awaiting the owner

**Proposed: sweep ACCEPTs travel like any other ACCEPT.** On a branch with commits, the budget
counts the branch's lineage, which every synced clone shares, so "this work bought N rounds on this
branch's lineage" is true there too. In the empty-span fallback the reason already says "in this
worktree". The trade-off: in another clone, a sweep ACCEPT nobody weighed by hand suppresses a
re-raise through `prior_dispositions`, as it already does in the clone that wrote it. Keeping sweeps
local would need a marker field, or a match on the reason text, and would rebuild the divergence
this item removes. *Awaiting owner confirmation.*

## Security model and norms (R11)

- **`security-model.md` § Direction, the product-content norm: not touched.** The norm governs
  content leaving "that product's own repository and owner". `evidence sync` pushes only to the
  product's own push remote (`gitstate.push_remote`), and the security model lists it under the
  network-sites posture, not as a cross-owner surface.
- **Upstream filing (`project-preferences.md`): not touched.** `file-upstream` composes its own payload,
  and no disposition text enters it (grep of `lib/backlog/`).
- **Stats upload (`project-preferences.md`): not touched.** `contribute` sends `stats.aggregate`
  numbers on a committed allowlist that can express no text. Ingested dispositions change the values
  of the acted-on rates, not what kind of value is sent.
- **What is newly on the remote.** Free-text accept reasons, owner-ruling text, backlog ids, and the
  path lists of free fixes. Anyone who can fetch the product's remote can read them. This repo's
  remote is public, so for this repo that means anyone. Findings text and waiver rationales already
  travel the same way. The outbound entry is amended to name the four fields. The inbound entry gets
  the one sentence R11 asks for: an ingested disposition reaches the census, the briefing and the
  reviewer's prior-dispositions block, and no gate.
- **`core.md`'s shared-surface rule applies even though no norm does.** The rule is to check a
  surface's visibility, and grep the payload for private names, before the first write after
  reading private sources. Measured: 6 of this store's 2,313 dispositions mention the directory name
  of another governed product (names deliberately not recorded here). 71 review facts are in the same
  class and already travel. Because of D7's bound, those 6 are sent only if their reviews are on a
  branch being synced. Operator step, not code: before the first sync from this repo after the
  change ships, list what `reconcile` would attach and grep it.
- **#606: honoured.** A disposition still has one home, the store. The note is a copy and a locator,
  as for every transported kind (`data-model.md`). The ledger still holds no outcome. Its docstring
  sentence is rewritten, not supplemented.

## Test plan (each case seen red before its fix)

| # | Case | Red today because |
|---|---|---|
| T1 (A1) | Two-clone harness (`tests/test_evidence_sync.py` `_clone`): ACCEPT, FILE, `--fixed` in A; sync A; ingest B; B's census shows accepted, filed, fixed-unreviewed | `attach` skips the kind |
| T2 (A2) | B's `prior_dispositions` for the cited file and scope lists A's ACCEPT | nothing arrives |
| T3 (A3) | The same fact set appended in two orders, including `:2` against `:10` and a note sorted as `cat_sort_uniq` sorts it, gives one index, one history and one census | store order |
| T4 (A4) | A and B each answer one finding differently, sync both ways: same winner in both, two-entry history in both | both mint `disp:R:F:1` |
| T5 | B ingests A's answer and re-answers with an earlier envelope `ts` (injected via `append_envelope`): B's answer wins in both | store order, and a `ts` key would also fail |
| T6 | A disposition whose attach failed is reconciled onto its review's anchor, not HEAD, including one written from a scratch branch | the else branch in `unattached` |
| T7 (A5) | Ingested ACCEPT with `owner_ruling` on a BLOCKING finding: coverage verdict, `_blocking_clear` and lint-blocking suppression are unchanged. Red-verified by mutating `_PASSING` to admit `accepted` | (mutation) |
| T8 (R13) | With `TRANSPORTED_KINDS` patched to the old set, ingest of a note carrying dispositions returns `ok`, appends none, and names the skip | — (pins the claim) |
| T9 (R12) | No remote and no ref: `record` succeeds. A forced attach error gives `recorded` with `note.status == "error"`, the CLI prints the NOTE and exits 0 | no `note` key |
| T10 (R15) | `stats` and `review-stats` count an ingested answer once, and a conflicting pair once | — (pins the claim) |
| T11 (D6) | Held legacy `disp:R:F:1` with body X, incoming with body Y: ingest's reason counts 1 | no count |
| T12 (D5) | Pruned history `[:3]` alone: the new answer mints a `seq` above 3 and wins | `len + 1 = 2` |
| T13 | `auto_accept` in B skips a finding A answered | nothing arrives |

Existing tests renegotiated in the open:

- `TestRedisposition`: ids gain the tag. The revert and pruned cases keep their invariants.
- `test_ledger_holds_no_outcomes.py::test_its_transport_claim_matches_the_transported_kinds`:
  renamed to the new contract, and asserts the new sentence and `"disposition" in TRANSPORTED_KINDS`.
- `test_every_kind_outside_the_transported_set_is_skipped`: must keep a non-empty local set (A6).

A7 (the falsifying search) is a done-when check, not a test.

## Chunking

1. **Convergence, in one clone.** `dispositions.py`: `answer_key`, the D5 id and `seq`, and the index,
   history, `prior_dispositions` and no-op check reading one winner. The module docstring's "store
   order" and race sentences are rewritten. In `data-model.md`, the disposition-body text "last-recorded
   wins … sequenced id" is rewritten to D4/D5. Tests T3, T4 at store level, T5 at store level, T12,
   and the `TestRedisposition` updates. This chunk ships alone safely: the measured history keeps
   every winner.
2. **Transport.** `TRANSPORTED_KINDS` and its comment (D3); `record` attaches and reports (D1), and
   `disposition_cmd` and `_refuse_over_budget` say so; `unattached`'s branch (D2); ingest's
   legacy-collision count (D6); the `evidence_notes` module docstring's anchor paragraph; the
   `ledger.py` paragraph and its pinned test, which go red in this chunk; and `security-model.md`'s
   outbound and inbound sentences, in this chunk so nothing is sent before it is stated (G5). Tests
   T1, T2, T4 and T5 across two clones, T6–T11, T13.
3. **Every description agrees (R14).** `governance-telemetry.md` ("dispositions stay in their clone");
   `review-cycle.md` ("Review and resolution facts reach other clones"); `data-model.md` "Reach beyond
   the clone" (kind list and anchor rule). Then the falsifying search for the claim in other words
   over `plugin/`, `tests/`, `documentation/` and `.prawduct/artifacts/` ("stay in their clone",
   "stays in that clone", "about the clone that wrote", "local to", "per clone"). From this
   document's own search, `evidence.py`'s guard-refusal paragraph and `evidence_notes.attach`'s skip
   reason remain true and stay.

After merge, and before the first sync from this repo: the operator scan above.

## Risks

- **A wrong answer now spreads** (requirements). The remedy is the existing one: a new answer, which
  D4 makes win everywhere.
- **Conflicts are silent.** The census shows the winner and does not flag a finding with two
  concurrent answers. `disposition_history` shows both. A visible flag can be added later if T4-shaped
  conflicts turn up in practice.
- **The tag lengthens ids** by 13 characters per line, about 2% of an average disposition line (about
  620 bytes).

## Open questions for the owner

1. **Q2, budget sweeps (D10).** Proposed: they travel like any ACCEPT. Confirm, or rule that they stay
   local.
2. **Archive-wide backfill (D7).** Recommended: none. The Q1 ruling is met for every branch in flight,
   resolutions never had one, and the most it could add here is 339 dispositions (about 208 KB),
   answering reviews of work already merged. Say if you want a one-time `reconcile --all` anyway; it
   would be its own item and would also cover resolutions.
