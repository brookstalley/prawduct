---
artifact: build-plan
version: 2
scope: small-batch-2026-09-02
branch: fix/small-batch-2026-09-02
depends_on:
  - artifact: backlog-service-api-contract
partition: serial — four independent items, but they are S-sized and share one Critic pass; delegating four briefs costs more coordination than the work saves, and Chunks 01 and 02 touch adjacent code in `plugin/lib/backlog/`
last_validated: 2026-09-02
---

## Requirements Confidence

**Level:** High for Chunks 01, 02, 04. Medium for Chunk 03.

**Why:** Chunks 01 and 02 are defects with reproductions in hand and fixes whose homes
were located in the code before planning. Chunk 04 has a body naming its own affected
files and expected outcome. Chunk 03 is a vocabulary reconciliation whose *decision*
— which of two names survives — is not yet made.

**Open assumptions / unknowns:**
- ~~[ASSUMPTION: Chunk 03 resolves toward `untriaged`…]~~ **RESOLVED 2026-09-02, and neither
  way.** The assumption presupposed that one name had to win. Reading `query.py` showed the two
  denote different sets, so both stay and the containment is documented instead. Recorded rather
  than deleted: the assumption was the reason the chunk was ordered last, and it turned out the
  question itself was mis-posed.

**What would raise confidence:** An owner ruling on Chunk 03's name before it is built.
The chunk is ordered last of the three code chunks so the ruling can arrive late.

## Status

- [x] Chunk 01: A bare issue number resolves against `--repo`
- [x] Chunk 02: a discarded block edit is reported, not swallowed
- [x] Chunk 03: state the quarantine ⊂ untriaged containment
- [ ] Chunk 04: A failing cache warm leaves a durable record
Context: Chunks 01 and 02 built and committed (ad1f23d1, bad2ee70) on a green suite.
Both were the OWED prawduct defects from the 2026-09-02 triage; Chunk 01's also bit this
session. Chunk 02 was DESCOPED mid-build — its planned fix would have breached a recorded
invariant — and the real gap is filed as #751 (`unmerge`, design). Next: Chunk 03, which
needs its naming decision made. The cumulative Critic runs after Chunk 04, covering all
four. #609 was considered for this batch and DROPPED: its blocker (`constraints.txt` on
the unmerged `feature/upstream-dependency-policy`) was re-verified live and still holds.

## Verification Strategy

Each chunk carries a reproduction that fails before the change and passes after. Chunks
01, 02 and 04 are verified additionally by running the real CLI against this repo's own
backlog cache — the product check, not only the unit one, since all three defects are
about what an operator sees at the command line. Chunk 03 is prose; its verification is
that the two documents no longer name one query two ways, checked by grep.

## Build Chunks

### Chunk 01: A bare issue number resolves against `--repo`

- **Description:** `normalize_id` accepts four ID spellings, none of them a bare `322`
  or `#322`, so a fully-disambiguating `--repo owner/repo` still cannot resolve the
  number an operator reads off a GitHub URL. Two failure modes: `322` falls through
  every form to "unrecognized ID spelling", and `#322` reaches the short-form branch
  with an empty left side and reports `malformed repo in '#322'` — which names the
  wrong defect, since the input contains no repo at all. The previous session worked
  around this for an entire triage pass by hand-spelling `prawduct#N`; it also broke
  this session's first `cache-query resolve` call.
- **Depends on:** none
- **Artifacts consumed:** `backlog-service-api-contract.md` (ID spellings)
- **Deliverables:** `plugin/lib/backlog/ids.py` — thread a `default_repo` through
  `normalize_id` and add the bare-number form; `plugin/lib/backlog/cachequery.py`
  (`resolve`) and `plugin/lib/backlog/cli.py:949` — pass the `default_repo` that
  `_repo_defaults` already computes and that this one call site drops
- **Tests:** unit — `322`, `#322`, and `  #322  ` each resolve against a `default_repo`;
  each still fails with a *useful* message when no default repo is available; the ID-1
  idempotence property still holds for the new form; a bare number with no digits
  (`#abc`) still reports the number defect, not the repo one
- **Acceptance criteria:** `prawduct-hook backlog cache-query resolve 322 --repo
  brookstalley/prawduct` resolves; so does `#322`; omitting `--repo` produces a message
  naming the missing repo rather than a malformed one
- **Type:** bugfix
- **Critic mode:** chunk
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed and chunk marked `[x]` in Status

### Chunk 02: a discarded block edit is reported, not swallowed

- **Description:** `backlog merge` has no inverse. `--superseded-by` sets the field but
  no value clears it, unlike `--refs`, `--revisit` and `--closed-by`, which all clear on
  an empty value. Worse, `update --body` with the line stripped returns `ok` and the
  adapter silently RE-SERIALIZES the field from its parsed state, so the operator is
  told the write succeeded and nothing changed. This is not cosmetic:
  `cachequery.py` calls `ids.resolve_redirect` on every resolve and walks
  `superseded_by`, so a reopened item carrying a stale pointer silently redirects
  lookups to the wrong issue. The previous session had to repair #304 with a raw
  `gh issue edit`, outside the adapter. Reproduced before building: the update
  returns `ok` with an empty `warnings` list and the field intact.
- **Depends on:** none
- **Artifacts consumed:** `backlog-service-api-contract.md` (update flags)
- **[DECISION: the planned fix was WRONG and is descoped. Do NOT add a
  `--superseded-by` flag.]** The plan inherited "mirror the three clearing flags"
  from the previous session's handoff. Reading the code first falsified it:
  `core.py`'s `_UPDATE_BLOCK` comment records `superseded_by` as *deliberately*
  not writable — "owned by link/unlink and merge — a bare field write would bypass
  their invariants (edge symmetry, redirect)". A clearing flag would punch through
  a recorded invariant to fix an ergonomics complaint. What the handoff actually
  found is two separate problems: a **silent failure** (this chunk) and a
  **missing inverse for `merge`** (filed, not built — it needs an `unmerge` that
  owns the invariant the way `merge` does, which is an M with a design question,
  not the S this chunk was scoped as).
- **Deliverables:** `plugin/lib/backlog/core.py` — `update_item` reports a
  discarded block edit instead of swallowing it. Pasting a body with a block line
  removed returned `ok`, silently re-appended the stored block, and said nothing;
  the operator was told a write succeeded that did not happen. Only a *pasted*
  block is reported: a body with no block at all cannot distinguish "I deleted it"
  from "I never included it", so it stays silent rather than guessing.
- **Tests:** unit — a discarded block edit is reported (the regression that would have
  caught the original defect); an unchanged pasted block is NOT warned about, so the
  notice stays rare enough to read; a body with no block is NOT warned about, since
  that case is ambiguous
- **Acceptance criteria:** an operator whose block edit was discarded is told so, and
  told which flags do edit block fields. (The original criterion — restoring a
  reopened item through the adapter with no raw `gh` call — is NOT met and is not
  this chunk's to meet; it needs the `unmerge` op filed above.)
- **Type:** bugfix
- **Critic mode:** chunk
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed and chunk marked `[x]` in Status

### Chunk 03: state the quarantine ⊂ untriaged containment

- **Description:** Backlog item #544. `list --untriaged` and the anonymous-filing
  **quarantine** surface in `documentation/backlog-service-api-contract.md` §9 are the
  same query under two names, and neither document mentions the other. §9 says an
  anonymous filing "lands unlabeled = quarantined and is surfaced by a `submitted`-intake
  `list` query, not by a bespoke endpoint" — which is exactly what `--untriaged` does.
  Data Model §3 and the PROV-2 / SEC-7 test specs reconcile against §9's wording, so the
  vocabulary has forked across four surfaces.
- **Depends on:** none
- **Artifacts consumed:** `documentation/backlog-service-api-contract.md` §9, Data Model §3
- **[DECISION: keep BOTH names — the item's premise was wrong.]** #544 assumed one query
  under two names. Reading the code first falsified it. **Quarantine** is defined by
  AUTHOR (Security §6/F7 — a *non-collaborator's* unlabeled filing); **`--untriaged`**
  selects on LABEL only, returning every unlabeled issue whoever filed it (`query.py`,
  the PROV-2 scope inversion — no author or collaborator predicate exists on that path).
  Quarantine is a strict SUBSET, presently served by its superset. Picking one name would
  have deleted the author boundary that makes quarantine a security concept rather than a
  hygiene one. So the reconciliation is to state the containment on every surface, not to
  collapse it. The direction is worth recording: the standing query over-includes, so no
  anonymous filing is missed — a precision gap, not a hole.
- **Deliverables:** the containment stated in `documentation/backlog-service-api-contract.md`
  §9, `documentation/backlog-service-data-model.md` §3,
  `documentation/backlog-service-security-model.md` §6/F7 (which now marks its own query
  *specified, not yet implemented*), and `plugin/skills/backlog/adapter-mode.md`; the
  unbuilt author predicate filed as #752 rather than assumed away
- **Tests:** none — prose only, and no code changed. Verified by grep across the four
  surfaces, and by reading `query.py` to confirm the absent predicate rather than inferring it.
- **Acceptance criteria:** no surface presents the two as the same query, and each one a
  reader could land on states the containment and which set the shipped query returns
- **Type:** trivial
- **Trivial because:** documentation reconciliation with no behavior change; the decision
  it records is the deliverable, and no code path moves
- **Done when:**
  1. The name is chosen — recorded as a `[DECISION: …]` here, with the reason
  2. Acceptance criteria met
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: A failing cache warm leaves a durable record

- **Description:** Backlog item #625. `briefing._spawn_cache_warm` spawns the
  session-start sync detached with stderr to `DEVNULL`, and only a *successful* sync
  stamps `cursor.coverage_confirmed_at`. Every `log_diag` on that path writes into a
  black hole, so a warm that failed once is indistinguishable from one failing for a
  week. Cold start is covered; the uncovered case is warm-then-always-failing, where
  reads keep succeeding with stale answers and the only signal is an `age_seconds` judged
  against no named threshold.
- **Depends on:** none
- **Artifacts consumed:** `plugin/skills/backlog/cache-reads.md`
- **Deliverables:** a persisted failure record on the cursor (`last_error`,
  `last_attempt_at`) in `plugin/lib/backlog/sync.py` and `plugin/lib/backlog/cache.py`;
  surfaced by `plugin/lib/backlog/cachequery.py`; named in
  `plugin/skills/backlog/cache-reads.md` so a reader knows to look for it
- **Tests:** unit — a failed sync writes the record and leaves `coverage_confirmed_at`
  untouched; a later *successful* sync clears it (the multi-hop case: one step beyond
  the immediate post-state); `cache-query` surfaces the record in both human and JSON
  modes; a reader with a healthy cursor sees no failure noise
- **Acceptance criteria:** with `gh` auth revoked, a cache read still answers, and its
  output names the failure and when it started — distinguishable from a merely old store
- **Type:** feature
- **Critic mode:** cumulative
  <!-- Last chunk: its review is the one cumulative pass covering all four chunks. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status
