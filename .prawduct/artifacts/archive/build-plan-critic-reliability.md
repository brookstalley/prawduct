---
artifact: build-plan
version: 2
scope: critic-reliability
branch: fix/critic-reliability
depends_on:
  - artifact: architecture
  - artifact: nonfunctional-requirements
governed_by:
  # Seeded via `prawduct-hook jurisdiction --artifacts-only` 2026-08-19; curated to
  # the two artifacts whose Direction norms actually reach this cycle.
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms — this cycle STRENGTHENS the norm's mechanism clause. That clause already says a session boundary is not refused but retains a live marker; Chunk 02 widens retention to cover a complete-roster review whose marker has expired, and makes a sweep that does act say so. No mutation site moves."
      - "authority fails closed; advice fails soft → conforms — the expiry announcement produces no verdict, so it takes the fail-soft posture per the norm's own generalisation (a command's failure posture follows what it produces). The `critic-begin` refusal on a complete roster is unchanged and stays fail-closed."
      - "every fact has one home → conforms — the announcement copy routes through `pending_roster_reading()`, already the single home for what a pending roster MEANS; Chunk 02 adds no second statement of it. The TTL constant keeps its one home in `critic_marker`."
      - "goals and verification bind; prescribed method is advice → conforms — Deliverables below read as advisory; the acceptance criteria bind."
      - "local-first governance coordination → conforms — Chunk 01 replaces one git invocation with a file copy, moving further toward the substrate the norm names, and adds no network or daemon."
      - "prawduct is written in Python and must never be specific to Python → conforms — Chunk 01 touches git plumbing and file I/O only; no language classification, no per-suffix table, no parser."
      - "prawduct guides and reviews; it never implements → inapplicable because this cycle changes prawduct's own governance runtime, which the norm's Scope paragraph explicitly excludes (prawduct-the-product is built normally)."
      - "the plugin writes nothing into a governed repo except its own state and reconciled seams → conforms — the temp index and the copied `.git/index` are the plugin's own scratch state; the session's real index and working tree stay untouched, which is `capture_tree`'s existing R1 invariant and is preserved."
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is a P0 constraint → conforms, and Chunk 01 IMPROVES it — tree capture currently costs 25-39s on a bind mount and times out at 15s, which is unit-cost paid before a review can even start."
      - "proportionality ratchets both ways — a new control names the yield it expects AND emits it observably → conforms. Chunk 02 adds no blocking control: the announcement IS its own observable emission, so it cannot become a control that fires unmeasured. The roster check in the sweep is a skip condition, not a gate."
      - "state-file growth past its size threshold is advisory → inapplicable because this cycle adds no state file and changes no size threshold."
last_validated: 2026-08-19
lifecycle: completed
archived: 2026-08-20
released_in: v3.4.0
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Requirements Confidence

**Level:** High

**Why:** All three problems are reported with reproductions, and every claimed defect was
verified against the code this session rather than taken from the reports. The design
question each item left open has been answered with evidence (see Open assumptions and
Chunk 02's Description). Scope is bounded to two files.

Backlog items: **#675** (Chunk 01), **#692** and **#690** (Chunk 02). All three carry
`tag:3.3.5-era` — this plan is one of two delaying the v3.3.5 cut, by owner decision
2026-08-19.

**Open assumptions / unknowns:**

- [RESOLVED 2026-08-19: copying `.git/index` preserves stat data and `git add -A` then
  re-hashes only genuinely-changed paths — measured, not assumed, by
  `.prawduct/research/tree-capture-2026-08-19/measure.py` (sections A and B: the copy is
  materially faster on this repo's own tree, on a local disk, and both seeds write the
  identical tree). The fallback-to-timeout-override-alone contingency is not needed.
  Section C added a condition the assumption did not anticipate — see Chunk 01.]
- [ASSUMPTION: a missing or locked `.git/index` (fresh clone, concurrent git) is rare
  enough to handle by falling back to `read-tree HEAD` rather than failing | MED impact |
  user can override]
- [ASSUMPTION: the v3.3.5 bundle wants the narrow safety fix for #692 and not the TTL
  re-price its own acceptance criteria ask for | HIGH impact | owner confirmed 2026-08-19]

## Status

- [x] Chunk 01: Tree capture stops re-hashing the world — and cleans up after a timeout
- [x] Chunk 02: An expiring marker announces itself, and never discards a self-heal

Context: **Both chunks are built, reviewed and committed (2026-08-19).** The plan's single
`cumulative` (`Type: cumulative-final`) ran at Chunk 02 and covered the whole branch: 2
blocking, 3 warnings, 11 notes, all dispositioned in one pass, and the follow-up
`verify-resolutions` verified all five blocking/warning resolutions with zero new findings.
Backlog: #675, #692 and #690 are closed on GitHub with their reasoning in close comments
(#692 as a recorded disposition, not an implementation — the TTL was deliberately not
re-priced). #699 was filed for a gap found on the way: `adapter-mode.md` claims a close
records `closed_by` and no write path exists, so the scope handle on those three closes is
prose, not machine-readable.

Each chunk corrected its own spec as it was built and the corrections are in the
Descriptions below — the wedge is not in `.git`, the index copy must preserve mtime, a
shared reading has to be true at the surface that just acted, and the retention rule had a
second home. None should be re-litigated.

Nothing remains but the PR, which is the owner's call (`/prawduct:pr`).

## Verification Strategy

Beyond tests, each chunk is exercised through the governed path rather than only read —
the two defects in this branch's sibling scope (`clear-cadence`) were both found by
*using* the tool and missed by reading it.

- **Chunk 01:** run `/prawduct:critic` end-to-end in this repo and confirm `critic-begin`
  captures a tree. The bind-mount case cannot be reproduced here (no bind mount), so the
  acceptance criteria measure the *mechanism* — re-hash volume and elapsed capture time on
  a large tree — rather than the symptom, and the reporter's environment is the operator
  verification.
- **Chunk 02:** drive a real dispatch to a retained-marker state and read the announcement
  as an operator would, checking it says what happened and what to do.

## Build Chunks

### Chunk 01: Tree capture stops re-hashing the world — and cleans up after a timeout

- **Description:** `capture_tree` seeds a fresh temp index with `read-tree HEAD`, whose
  entries carry zeroed stat data, so the following `git add -A` must re-hash **every**
  tracked file. On a bind mount each read pays mount-RPC latency and the capture blows
  through the hardcoded 15s timeout — every `critic-begin` fails, so no review can record
  and the PR gate becomes structurally unsatisfiable. Each timeout also kills `git add -A`
  mid-operation, leaving `.git/index.lock` behind so a *later, unrelated* `git commit` <!-- prawduct:allow prawduct/chunk-ref-missing -- the ORIGINAL report's claim, quoted so the correction below has something to correct; the path is absent by design -->
  fails pointing at git rather than at prawduct. Three defects, one site: the cost, the
  unconfigurable budget, and the wedge. Fix the cost first — copying the repo's existing
  `.git/index` preserves stat data, so `add -A` re-hashes only what actually changed —
  then keep the budget override and the lock cleanup as the belt to that braces.

  **Correction, from building it (2026-08-19): the wedge is real but it is not in
  `.git`.** `capture_tree` runs every git call with `GIT_INDEX_FILE` pointed at its temp
  index, and git takes its index lock *next to the index it was given* — so a capture
  killed mid-`add` leaves `<tempdir>/prawduct-idx-XXXX.lock`, never `.git/index.lock`. <!-- prawduct:allow prawduct/chunk-ref-missing -- the correction itself: this path is what the fix does NOT produce, and saying so is the record's whole value -->
  Reproduced directly (kill a real `git add -A` mid-operation under `GIT_INDEX_FILE`: no
  `.git/*.lock` appears), and there is exactly one `git add` call site in the plugin, so
  no other prawduct path can produce one either. The leak this chunk closes is therefore
  temp-directory litter — one stale lock per timeout — and the report's `.git/index.lock` <!-- prawduct:allow prawduct/chunk-ref-missing -- same correction; a future reader of #675 must not believe this fix addressed that path -->
  is NOT attributable to this code path. Recorded rather than quietly re-scoped: whatever
  the reporter saw has another cause, and a future reader of #675 should not believe this
  fix addressed it.

  **A second requirement surfaced from measurement, and it is a correctness one.** The
  copy must preserve the index's **mtime** (`shutil.copy2`, not `copyfile`). Git's stat
  cache skips a file whose size and mtime still match its entry, and the only thing that
  catches a same-tick, same-size edit is the racily-clean rule — *an entry whose mtime is
  not older than the index FILE's own may have changed since it was recorded, so re-read
  it.* A copy stamped with the current time makes every entry look comfortably older than
  its index, silences that rule, and lets `add -A` skip the re-hash: the captured tree
  then carries the file's PREVIOUS content and the review vouches for a tree that never
  existed. This is a fail-open in the evidence store, strictly worse than the timeout it
  was traded for, and it was found only because the first implementation flaked in the
  suite. Section C of the derivation runs the race; the deterministic pin is
  `test_same_second_same_size_edit_is_still_captured`.
- **Depends on:** none
- **Artifacts consumed:** `nonfunctional-requirements.md` § Performance (the P0
  review-wall-clock constraint this defect is paid out of)
- **Deliverables:** `plugin/lib/evidence.py` — `capture_tree` seeds from a **metadata-
  preserving** copy of `.git/index` (the mtime is load-bearing, see Description) with a
  `read-tree HEAD` fallback when that file is absent, unreadable, or only partly copied;
  `_GIT_TIMEOUT` becomes an env-overridable default (`PRAWDUCT_GIT_TIMEOUT`), refusing a
  malformed override rather than silently restoring the default; a failed capture removes
  the temp-index lock **it created** and names the remedy in its error string; the capture
  result reports **which seed it used**, and a fallback says so on stderr, because a
  silent degradation to `read-tree` is indistinguishable from the fix not being enough —
  the operator raises the budget, gets a slow-but-working capture, and closes the bug
  while the fix never engaged. A refused `PRAWDUCT_GIT_TIMEOUT` is announced once per
  process for the same reason: it fails every `run_git`, and two advisory callers read a
  nonzero rc as an honest 'no answer' and go quiet.
  `.prawduct/research/tree-capture-2026-08-19/measure.py` — the committed derivation
  behind the cost claim, the seed-agreement claim, and the mtime claim
- **Tests:** unit — the seed reads the repo's own index; the fallback path when the copy
  cannot happen at all and when it dies part-way (a truncated index git would reject);
  the env override reaches the subprocess call and a malformed value is refused rather
  than silently defaulted; a capture failure leaves no lock behind and its message names
  the remedy; a fallback names itself in the result and on stderr, and a refused override
  is announced once and only once; a same-tick, same-size edit is still captured (the
  racily-clean pin, with
  every timestamp forced so the race is not left to the machine's speed); a
  `--skip-worktree` entry still agrees with a verbatim commit. Integration —
  `capture_tree` on a tree with an uncommitted change still returns the correct tree SHA
  and leaves the session's real index untouched (the existing R1 invariant, re-asserted
  against the new seeding path)
- **Acceptance criteria:** capture returns an identical tree SHA to the current
  implementation for the same working tree (the change is a cost fix, not a semantic one),
  including for an edit made within one filesystem tick of the index write; elapsed
  capture time on this repo's tree improves measurably against the `read-tree` path,
  recorded by a committed derivation rather than a quoted figure; a forced timeout leaves
  no lock file behind and says how to raise the budget; no degraded path is silent
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: An expiring marker announces itself, and never discards a self-heal

- **Description:** Two reported defects in one mechanism, both created by the unreleased
  `clear-cadence` change that made the 30-minute TTL the **sole** liveness verdict at a
  session boundary.

  **#692 — the TTL is not re-priced, and the reason is recorded.** The item asks for a
  value "grounded in the review-stats distribution." That grounding is unavailable, and
  saying so is a deliverable: `duration_seconds` is self-reported by the reviewing agent
  and a coordinator review records `max()` across partials, while marker **wall-clock age**
  — the quantity the TTL governs — spans dispatch + every reviewer + consolidation +
  coordinator turn latency, so it is strictly longer than any self-report. No recorded
  review exceeds the TTL, and that margin is not evidence. The derivation is committed at
  `.prawduct/research/critic-liveness-2026-08-19/measure.py`; cite the command, never its
  digits. So the number stays and the **silence** goes: a boundary sweep that acts on an
  expired marker says so. Separately, `write_marker`'s docstring speaks of renewing your
  own protection while nothing renews a marker mid-review — the claim is reconciled to the
  code, not the code to the claim.

  **#690 — the sweep skips a complete roster.** The Stop hook's abandoned-review backstop
  is gated on `marker_present()` (deliberately no TTL) and *self-heals* a review whose
  reviewers all reported but whose consolidation never ran. An expired marker is exactly
  the state that reaches it, and the boundary sweep deletes that marker first. The item
  declined an in-place fix on hot-path cost; measured, `pending_state()` is a single
  `is_file()` and an early return with **zero git subprocesses** — not what the
  SessionStart budget constrains. The blocker is discharged by measurement, and that
  measurement is section B of the same committed script.

  **The known trap, named up front:** the marker's record outlives every in-session
  signal, and prior case law (findings R-3 and R-10, two reviewers independently) is that
  reasoning about the `clear` guard does **not** clear a cross-session reader. Enumerate
  every reader of the marker and the findings record explicitly — `briefing`'s findings
  summary among them — rather than deriving their safety.

  **Second correction, from the review (2026-08-19): the retention rule had two homes and
  only one was taught.** `boundary_sweep` learned to keep a complete roster; `review_active`
  kept unlinking an expired marker as a side effect of *answering*, and a bare
  `prawduct-hook clear` — the invocation this whole guard exists for — asked it and destroyed
  exactly the review the boundary now protects. Two reviewers found it independently, from
  opposite goals. The fix is a construction, not a second branch: `review_active` is now a
  pure predicate, one function decides whether a marker may go, and both surfaces that meet
  one without forcing route through the same call plus its notices. The deliverable's own
  acceptance criterion was false at a surface the chunk never opened, which is the shape to
  look for — a rule added to the site that motivated it, while its siblings keep the old one.

  **Correction, from building it (2026-08-19): sharing a reading means it has to be true
  at the surface that just ACTED.** The swept notice composes through
  `pending_roster_reading()` as specified — and the `incomplete` reading it inherited said
  "a `/clear` retains the marker; it does not release it", which was true of every surface
  that existed when it was written and is false at the one this chunk adds. Read as an
  operator, the sweep notice therefore said *waiting is safe* three lines above *the marker
  is gone and no gate will raise this again*. The clause now names its condition rather
  than asserting the retention flat. Found by running the announcement, not by reading it —
  which is what this plan's Verification Strategy predicted for this branch's scope.
- **Depends on:** none (independent of Chunk 01; ordered second only by release risk)
- **Artifacts consumed:** `architecture.md` § Direction (the reviewer-non-mutation norm,
  whose Mechanism clause describes the retention this chunk widens)
- **Deliverables:** `plugin/lib/critic_marker.py` — the boundary sweep consults
  consolidation state and retains a marker whose roster is complete; the acting path emits
  a notice instead of unlinking silently; `write_marker`'s renewal language reconciled to
  what the code does. `plugin/lib/critic_consolidate.py` — the notice composes through
  `pending_roster_reading()` rather than restating it. A recorded decision, in this plan
  and in the change-log entry, for why the TTL was not re-priced.
- **Tests:** unit — expired marker + complete roster is RETAINED (the self-heal case);
  expired marker + incomplete roster is swept AND announces; live marker is untouched and
  silent; a corrupt-but-fresh marker still survives (the existing decided-by-age rule).
  **Every test injecting a fixed clock must put every actor in that clock domain** — a
  single real-clock participant turns fixed-timestamp + TTL into a deterministic failure
  at stamp+TTL wall time. Enumeration test — the readers of the marker and the findings
  record are listed and each is exercised, rather than argued safe.
- **Acceptance criteria:** a review that outruns the TTL cannot lose its marker without a
  signal; a complete roster survives a session boundary so the Stop hook's self-heal still
  reaches it; `write_marker`'s docstring and its behavior agree; the no-re-price decision
  is recorded where a future reader of #692 will find it
- **Type:** cumulative-final
  <!-- Last chunk of a plan shipping as one PR: this chunk's review IS the single
       `/prawduct:critic cumulative` — commit first, then run it once. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run once and blocking findings resolved
  3. Chunk marked `[x]` in Status
