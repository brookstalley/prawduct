---
artifact: build-plan
version: 2
scope: v3.2.0-golive
depends_on:
  - artifact: release-plan-backlog-service-golive
  - artifact: build-plan-backlog-service
  - artifact: backlog-service-requirements
  - artifact: backlog-service-upstream-filing
governed_by:
  - artifact: security-model
    dispositions:
      - "A destructive/irreversible operation requires explicit owner approval at the OPERATION level, not per granular action (amended 2026-07-24, owner ruling) → conforms. Chunk 06's migration takes one informed owner confirmation at scrub Step 0 — target repo named and bound, volume known, MG1 irreversibility stated — and then performs its ~900 writes without re-prompting. Under the norm's PRIOR absolute form ('no destructive action without an explicit --apply step') Chunk 06 would have been a departure, and the adapter's absent dry-run contract (BKL-8V3D) an unrecorded one; the amendment is what makes the disposition honest rather than the disposition straining to fit the old text."
      - "Chunk 06 telemetry obligation (BKL-8K2N) → the operation-level approval is only informed if the operator can see what the approved run is doing: pacing counters now ride every import exit path (success and both resumable cuts) and every blocking sleep announces itself, so a paced run is distinguishable from a wedged one."
      - "A governed product's content never leaves its own repo/owner; any cross-owner/public-plane filing surface is an owner decision (Status: in-transition, tracks BKL-7Q4M) → conforms + amendment proposed (Chunk 08 is the reviewed design the norm waits on; it moves in-transition→steady-state when §5's contract test replaces the interim egress test)"
  - artifact: architecture
    dispositions:
      - "The adapter never manages a token — `gh` owns the credential → conforms (Chunk 02/08 resolve the session `gh` identity; no managed token introduced)"
      - "Authority fails closed; advice fails soft → conforms, but on DIFFERENT evidence than originally cited (corrected 2026-07-24, cumulative Critic). The original rationale — 'the file-upstream/migration guards refuse-and-explain on any failed check' — cited evidence that does not exist: file-upstream is unbuilt (Chunk 08) and there is no adapter-side migration guard at all. What actually backs the disposition: advice fails soft (every advisory probe is non-blocking, and the briefing degrades visibly rather than serving stale markdown as live), and authority fails closed where authority exists (transport errors are typed and refuse rather than falling back; `_cost` raises on an unclassified verb). The conclusion stands; the stated reason did not."
  - artifact: api-contract
    dispositions:
      - "Exit codes are the contract; stable prefix vocabulary → conforms (new error vocab `filing-disabled`/`target-not-pinned`/`self-file`/`approval-mismatch` are additive, exit-class-typed)"
last_validated: 2026-07-24
---

## Requirements Confidence

**Level:** High (for the release scope) — with two narrow exceptions called out below.

**Why:** The long-pole discovery (BKL-9XQ2/BKL-7Q4M consent, evidence/PII, label taxonomy) is
settled as requirements (`backlog-service-requirements.md` XP4–XP7) and a reviewed, owner-approved
design (`backlog-service-upstream-filing.md`, 0 blocking, 2026-07-23). Every other ship-list item is
`stage: ready` or already built. The release scope, order, and blockers are enumerated in
`release-plan-backlog-service-golive.md`; this plan turns that ship list into buildable chunks.

**Open assumptions / unknowns:**
- [ASSUMPTION: BKL-6X5D part (b) — the Pacer REST-point metering fix-shape (meter 5/write + 1/read
  vs 900/min) is correct and needs only a ~30-min design confirmation at Chunk 04 step 0, not a fresh
  discovery pass | MED impact | user can veto — if the metering model is wrong, Chunk 04 grows]
- [RESOLVED 2026-07-24: `feature/backlog-service-relayout` already merged to develop (PR #137,
  2026-07-23) — no longer an assumption. develop's `plugin/lib/backlog` tree is byte-identical to
  relayout's; the code is on develop.]
- [ASSUMPTION: v3.2.0's canonical upstream target is `brookstalley/prawduct` (the string already
  hardcoded at `plugin/lib/migrate_plugin.py:39`), promoted to a single pinned constant in Chunk 02 |
  LOW impact | user can override the target]

**What would raise confidence:** the Chunk 04 design confirmation (part b), and Chunk 01's merge
completing cleanly. Neither blocks authoring the rest of the plan.

## Status

- [ ] Chunk 01: Live verification (VRF-005/007/008) — the relayout merge already landed (PR #137)
- [ ] Chunk 02: BKL-8V3D — the adapter's mutation-safety claim made honest (doc + guard test) — built 2026-07-24, `[ ]` until release
- [ ] Chunk 03: Scrub + grant safety rails (repo-selection/confirm, provisioning, grant narrowing, advisory hold) — built 2026-07-24 (ONB-3F9P full close), `[ ]` until release
- [ ] Chunk 04: Pacer REST-point metering for the create+close archive stretch (C7) — built 2026-07-24, `[ ]` until release
- [ ] Chunk 05: SPIKE-S2 live dry-run + MG4 scrub workflow (C1 + C2) — live dry-run run 2026-07-24 (VRF-009, §9 S2 settled), `[ ]` until release
- [ ] Chunk 05b: `pick` honesty + fan-out cost, ahead of the migration — built 2026-07-28, `[ ]` until release
- [ ] Chunk 06: The real prawduct migration + VRF-006 (C4) — irreversible, operator-run
- [ ] Chunk 07: Briefing/gates repoint through the adapter (C5) — scoping audit 2026-07-24 finds all four original done-whens already satisfied; the chunk's real content is now the **advisory lift** (done-when #5, owner decision BKL-7D3V) — ~~DEFERRED out of v3.2.0 2026-07-28~~ **BACK IN 2026-07-28 (same day), by the hard-cutover ruling**: the advisory lift is the mechanism that tells the fleet to migrate, and a hard cutover that never announces itself is not a cutover. Deferring it was correct under "07/08 add governed surface"; it is wrong under a hard cutover
- [ ] Chunk 08: MG5 / upstream filing — file-upstream op, report-bug rewrite, drop-box retirement (splittable 08a/08b) — **DEFERRED out of v3.2.0 2026-07-28** (same reason; the § Direction norm amendment it carries defers with it)
- [ ] Chunk 09: Release mechanics — version bump, change-log flip, regen-views, tag; VRF-002/003 post-tag — **re-scoped 2026-07-28** to cover Chunks 01–06 only

Context: Plan authored 2026-07-24 from `release-plan-backlog-service-golive.md` + the upstream-filing
design; `active_build_plan` now points here. **Correction 2026-07-24:** the relayout merge (the old
Chunk 01) was already done — PR #137 landed it on develop 2026-07-23 — so Chunk 01 is now
verification-only (see Prerequisites). **Chunk 02 built 2026-07-24** (BKL-8V3D honest fix + guard test;
suite 2551 passed). **Chunk 03 built 2026-07-24** — the four safety rails (BKL-2Q7F scrub-runbook
target-binding + provision; ONB-3F9P *full* close incl. the `init-product --backlog-repo` + onboard/
doctor provisioning legs, owner decision; BKL-5N9W grant narrowing + metadata test; BKL-6J2X advisory
held). Critic chunk-mode clean (0/0/0); suite 2563 passed. **Chunk 04 built 2026-07-24** — the Pacer now
meters total REST points (900/min; 5/write, 1/read) across create **and** close via the
`_PacingTransport` decorator, closing the create-then-close metering gap (BKL-6X5D part b); suite 2571
passed. **Chunk 05 offline half prepped 2026-07-24** — the MG4 scrub workflow (done-when #2) was already
complete; the SPIKE-S2 harness is now instrumented to measure the paced `--archive-scope all` burst
(`Pacer` counters → recorded facts) and its standalone-run import regression fixed, so the operator
dry-run is turnkey (Critic chunk-mode 0/0/1; suite 2572). **Chunk 05 live half landed 2026-07-24** —
recorded as VRF-009 (`verified`); §9 S2 settled in the negative (the point ceiling is a non-binding
safety belt under the serial importer, not the governor). See the Chunk 05 body for the tally and the
three residuals that are explicitly not blockers.

**Correction 2026-07-28:** this paragraph read "Next: **Chunk 05 live half**" for four days after that
half had landed — the chunk body and `operator-verification.md` (VRF-009 `verified`) both already said
so. The § Status summary drifted from the chunk bodies it summarizes, which is the same two-trackers
failure the § below diagnoses, reproduced *inside* the surviving tracker. Next is **Chunk 01** — VRF-005
/007/008 drained against `samsung-frame-art-loader`, plus the BKL-4W7H `promoted → shipped` flip — then
**Chunk 06** (the irreversible real migration).

**Release scope narrowed 2026-07-28 (owner decision).** v3.2.0 stops after **Chunk 06**. Chunks 07
(advisory lift) and 08 (upstream filing) *add* governed surface and are deferred behind a
deletion-only simplification pass; Chunk 09's release mechanics re-scope to whatever Chunk 06 leaves.
Rationale: the framework's own open backlog went 50 → 169 items in the 26 days since the
2026-07-02 efficiency review, ~120 of that from Critic findings on governance machinery. Chunk 06 is
the one remaining chunk that reduces that load rather than adding to it.

## Where v3.2.0's state lives — one tracker, and why the other surfaces disagree

**This document is the single live tracker for v3.2.0** (established 2026-07-24). Four surfaces describe
this release and they had drifted apart; each now has one job:

| Surface | Job | How to read it |
|---|---|---|
| **This build plan** | **Live state** — what is done, what is next, what the critical path is | Authoritative. § Status is the answer |
| `release-plan-backlog-service-golive.md` | **Decision record** — A1/A2, decision 6, the re-derived-count lesson, the drop-box sequencing rule | Its state columns were reconciled 2026-07-24 and are **not maintained**; it is no longer a tracker |
| The tree | **Ground truth** | Beats both plans. Two chunks (05's MG4 workflow, 07's briefing repoint) were found **already built** when read against the tree |
| `.prawduct/backlog.md` | **Item lifecycle** | Deliberately lags this release — see below |

**Why the backlog reads as though nothing is done.** This release adopted a `[ ]`-until-release
convention: chunks build and verify, but the `status=shipped` flip rides the release PR (Chunk 09). So
BKL-2Q7F, BKL-8V3D, BKL-5N9W, BKL-6J2X, BKL-6X5D(b) and ONB-3F9P all read `status: open` while their
work is built, verified, and sitting on this branch, and BKL-4W7H reads `promoted` with its code already
on develop. **That is intended, not drift** — but it means the backlog alone will tell a reader that
every release blocker is outstanding. The reconciliation is § "Deferred to Chunk 09"; that list is the
mechanism that keeps the convention honest, and it is why the list has to be appended to at each
deferral rather than reconstructed at release.

**The failure mode this table exists to prevent.** By 2026-07-24 the release plan and this plan
contradicted each other on the critical path — the release plan said the long pole was the `BKL-9XQ2`
discovery, which had already been settled on 2026-07-23. Two live trackers for one release always drift;
the fix was to stop having two, not to re-tick the stale one.

**Reading order for a chunk that has not been built yet: read the tree first.** Chunks 05 and 07 were
both authored from the release plan rather than from the code, and both described work that was already
done. Chunks 06 and 08 should get a scoping read against the tree as step 0 before any building.

## Prerequisites & branch reality (read before Chunk 02)

**The backlog-service code is on develop as of PR #137 (merged 2026-07-23).** The relayout branch
already landed: `feature/backlog-service-relayout` merged to develop, so develop now carries
backlog-service **Chunks 01–05**, **BKL-4W7H** (built offline, cumulative-Critic 0 blocking), and
**BKL-8P2R** (shipped) — develop's `plugin/lib/backlog` tree is byte-identical to relayout's (`e25f555`,
verified 2026-07-24). The subsequent upstream-filing design also landed (PRs #138/#139). **Do v3.2.0
work on develop** (or a feature branch cut from it) — the earlier "land the relayout branch first"
instruction is already satisfied. `release-plan-backlog-service-golive.md` § "First: the code lives on…"
recorded the *pre*-#137 state and is now superseded (annotated there).

**Governance posture.** Chunks 02, 03, 07, 08 touch `plugin/skills/**` and/or `plugin/lib/backlog/**`
(governance-protected surfaces) → full Critic + `/prawduct:pr` review. Chunks 05 and 06 are
operator-in-the-loop (live GitHub side effects); the operator runs the live steps, Claude drives the
tooling. Read `/prawduct:methodology building` before the first code chunk (Chunk 02).

**Chunk sizing (owner, 2026-07-24): keep chunks whole; split only if a Critic pass runs large.** Chunk
03 (four safety-rail blockers) and Chunk 08 (upstream filing) each stay a single chunk. If, at build,
either exceeds one clean Critic pass, split reactively — 08 along the marked 08a/08b seam; 03 by peeling
the advisory-hold (BKL-6J2X) off the three it gates on.

---

## Build Chunks

### Chunk 01: Live verification (the relayout merge already landed)

**Goal:** Exercise the already-landed service end-to-end against a real consuming repo before any
migration depends on it. **There is no branch to land here** — `feature/backlog-service-relayout` merged
to develop via PR #137 (2026-07-23); develop carries Chunks 01–05 + BKL-4W7H + BKL-8P2R (verified
2026-07-24). This chunk is the verification that was bundled with that merge.

**Covers:** ship-list item 3 (VRF-005/007/008). BKL-8P2R already `shipped`; BKL-4W7H's slice merged via
PR #137 → flip `promoted → shipped` (backlog bookkeeping via `/prawduct:backlog`).
**Depends on:** —
**Type:** operator verification (no code change in this chunk)
**Critic mode:** n/a (verification only — nothing to review)

**Done when:**
1. **VRF-005** (Chunk 02 live two-axis status), **VRF-007** (`/prawduct:backlog` end-to-end), **VRF-008**
   (dormancy) drained against `samsung-frame-art-loader` via `--plugin-dir`. Record results to
   `.prawduct/operator-verification.md`.
2. BKL-4W7H flipped `promoted → shipped` (its offline code is on develop via PR #137).

**Verification:** the three VRFs are the acceptance evidence; they de-risk the adapter before Chunk 06's
irreversible migration builds on it.

---

### Chunk 02: BKL-8V3D — the adapter's mutation-safety claim, made honest

**Goal:** `skills/backlog/adapter-mode.md:96` tells the model "mutations follow the adapter's own
`--apply`/dry-run … contracts (you never invent a mutation path)" — but no such flag exists in
`lib/backlog/`. The migration's *real* preview is `restructure-preview` (cli.py:563); file-upstream's
preview lands with that op (Chunk 08). Correct the false claim and pin the defect class shut with a test.

**Covers:** ship-list item 19 (BKL-8V3D).
**Depends on:** — (independent; the code is on develop)
**Type:** code (doc surface + guard test)
**Critic mode:** chunk

**[DECISION — build-time re-scope (2026-07-24) | the planning-altitude "shared adapter guard" keystone
did not survive the code. The adapter is stateless about the product's own repo (callers pass `--repo`;
no `backlog_service_repo` read — `context.py`), so the migration guard (pins to the runtime
`backlog_service_repo`, whose value only Chunk 03's skill step records) and the file-upstream guard
(pins to a fixed constant, and replaces the egress test) share **no** adapter mechanism. So: BKL-2Q7F's
adapter-side guard folds into **Chunk 03** (built with the skill step that records the target); the
upstream target-pin + no-self-file + preview-by-default stay in **Chunk 08** (with the egress-test
replacement — a `brookstalley/prawduct` literal in `lib/backlog/` before then reddens
`test_no_upstream_content_egress.py`, which must stay green until Chunk 08). Chunk 02 is now BKL-8V3D
only. | user can veto the re-scope]**

**Done when:**
1. `adapter-mode.md`'s Write-operations section no longer claims a generic adapter `--apply`/dry-run
   contract; it names the real mechanism — `restructure-preview` for the migration/import mutation, with
   a forward ref to file-upstream's own preview (Chunk 08).
2. A guard test asserts no backlog instruction surface (`skills/backlog/*.md`) promises an adapter
   mutation-safety flag (`--apply`/`--dry-run`) that the CLI does not parse — closing the defect *class*
   (release-plan item 18–21 note), not just this instance.
3. Offline suite green; `test_no_upstream_content_egress.py` still green (untouched); BKL-8V3D → shipped.

**Verification:** run the new guard test red first (against the pre-fix doc) to prove it catches the
class, then green after the correction.

---

### Chunk 03: Scrub + grant safety rails

**Goal:** Make the scrub/migration *skill* path safe — a scrub run must never write issues into an
unconfirmed repo, and the migration-required advisory must not route repos to a path that isn't proven.

**Covers:** ship-list items 18 (BKL-2Q7F — skill **and** adapter legs; the adapter-side target guard
folded here from Chunk 02, built with the skill step that records `backlog_service_repo` + ONB-3F9P
provisioning sibling), 20 (BKL-5N9W), 21 (BKL-6J2X).
**Depends on:** — *(corrected 2026-07-24, cumulative-Critic blocking finding: this originally read "Chunk 02
(the target-pin lives at the adapter; the runbook binds to it)". **There is no adapter target-pin, and
Chunk 02 never built one** — its own DECISION block records that the shared-adapter-guard keystone "did
not survive the code" and moved the pin to Chunk 08. The runbook's Step 0 confirmation is the whole
guard.)*
**Type:** code (skills/ + lib/) — governance-protected → full Critic + PR

**Done when:**
1. **BKL-2Q7F** — `skills/backlog/migration-scrub.md` gains a top-of-runbook **target-repo selection +
   owner-confirmation** step that records `backlog_service_repo` before any adapter call; every
   subsequent step reads the *bound* repo, not a re-templated `--repo <owner/repo>` placeholder (the
   six placeholders, anchored by step+op).
2. **ONB-3F9P sibling** — a `provision` (label-taxonomy) step with exactly one owner across the
   onboard/doctor/scrub entry paths (resolve the provisioning-owner gap together, not per-path).
3. **BKL-5N9W** — narrow the wildcard `Bash(prawduct-hook backlog *)` grant in `skills/backlog/SKILL.md`
   to the ops the skill actually drives, in **both** invocation forms (JNT-4R2M dual-form rule); scope
   or gate the scrub-only ops (`import`/`merge`/`provision`) behind the Chunk-03 confirmation step. Pin
   the resulting list with a metadata test. (Defense-in-depth, not the primary guard — **the runbook's
   Step 0 target confirmation is**; CRT-9V4T caveat. *Corrected 2026-07-24: this read "the adapter
   target-pin from Chunk 02 is" — no such pin exists or was ever built.*)
4. **BKL-6J2X** — hold the `backlog-service-migration-required` advisory
   (`lib/backlog_probes.py:277-291`) until the path is proven: it does not route to `/prawduct:backlog
   scrub` until Chunks 02–03 land and 18–20 are closed.
5. Offline suite green; the four items marked `status=shipped`.

**Built 2026-07-24** (Critic chunk-mode clean 0/0/0; suite 2563). Four build-time interpretation calls,
recorded so a later reader isn't surprised:
- **Done-when #1 — "records `backlog_service_repo`" means *bind the target*, not *flip the scalar*.**
  Setting the `backlog_service_repo` project-state scalar at the top of the runbook would freeze the
  markdown backend before any issue exists, contradicting the runbook's own "don't cut over before the
  import is verified" invariant. So Step 0 records the owner-confirmed target as a *scrub decision* and
  every step binds to it as `<target>`; the scalar flip stays at Step 6 (cutover). Renumbered 0–6.
- **Done-when #2 / ONB-3F9P — taken to a *full* close (owner decision, 2026-07-24), not just the
  scrub-side sibling.** Provisioning now has one owner per entry path: onboard provisions at adoption
  (new `init-product --backlog-repo` records the backend, offline + shape-only; onboard SKILL runs
  `provision`), doctor reconciles as a repair (Health Check #12, post-cutover only), scrub provisions
  at migration (Step 0). The onboard legs needed `init_product.py`/`bin` code — built here rather than
  split.
- **Done-when #3 — `merge` left OUT of the everyday grant** (prompts), with `import`/`provision`/
  `reconcile-labels`. It is dual-use (dedup also folds), but its blast radius (closes an issue) puts it
  with the migration set; post-cutover dedup is degraded anyway.
- **Done-when #4 — the advisory is held *at registration* (a no-op wrapper), not by gutting the
  probe.** `probe_migration_required`'s firing logic and its direct-call tests stay intact; lifting the
  hold is a one-line swap in `register()`. Kept the roster at six probes.
- **Done-when #5 — status flips deferred to release (Chunk 09)**, per this release's
  `[ ]`-until-release convention (mirroring Chunk 02's BKL-8V3D). The work is built + verified; the
  `status=shipped` flip rides the release PR, not this chunk.

---

### Chunk 04: Pacer REST-point metering for the create+close archive stretch (C7)

**Goal:** Close the metering gap so prawduct's own `--archive-scope all` migration runs fully inside the
900 REST-pts/min ceiling — the archive stretch is create+close (2 writes/item) but only the create is
paced today.

**Covers:** ship-list item 8 (BKL-6X5D part (b)). **Firm blocker; lands before Chunk 06** (release-plan
decision 6, ratified 2026-07-23: C7 before C4).
**Depends on:** Chunk 01
**Type:** code

**Done when:**
0. **Design confirmation (~30 min)** — confirm the fix-shape: meter *total* REST points (5/write, 1/read)
   against 900/min in the Pacer, adding a paced `before_write`/close path (today only
   `pacer.before_create()` is "the only paced call", `migrate.py:787`). Advance BKL-6X5D → `stage: ready`.
   If the model is wrong, this step surfaces it before code.
1. The Pacer meters total REST points across create **and** close, not just creates; the archive stretch
   stays ≤900 pts/min without relying on incidental `gh`-subprocess latency (which the raw-HTTP fast-path
   would forfeit).
2. **NFR §9 S2 obligation** satisfied: measure the burst with `--archive-scope all` (volume reduction
   disabled, so the run proves the Pacer, not a small input) and answer whether the create-then-close
   stretch breaches 900 pts/min.
3. The unbuilt window *quantification* (i) stays deferred (adopter-scale, BKL-4Z7M-adjacent) — this
   chunk is part (b) only. Say so; don't silently pull it in.
4. Offline suite green; BKL-6X5D part (b) marked `status=shipped`.

**Built 2026-07-24** (suite 2571; +8 tests). Design confirmed (Done-when #0): GitHub's point model
(900/min; 5 pts/write, 1 pt/read) verified against current docs before code — the fix-shape's constants
are correct, so the chunk did not grow. Build-time interpretation calls, recorded:
- **The metering seam is a transparent transport decorator (`_PacingTransport`), not a `before_write`
  threaded through `core.set_status`.** The close write lives in `core.set_status` (shared with the
  interactive `set` path); because the migration passes its transport *into* `set_status`, wrapping the
  transport meters the close's reads+writes with zero signature changes — and it is non-fragile (a new
  transport call is auto-metered; an unclassified one raises), killing the "only paced call" gap the item
  names. The content-cap `before_create()` stays put (orthogonal window, no double-count).
- **Done-when #2 (S2) is satisfied *by construction + a deterministic throttle test*, not a live
  measurement.** The live `--archive-scope all` burst measurement is Chunk 05's operator dry-run (which
  depends on this chunk's metering); NFR §3.3 + §9 updated so S2 now reads as the *live confirmation* of
  the paced burst, not a discovery of whether it breaches.
- **Done-when #4 status flip deferred to release (Chunk 09)**, per this release's `[ ]`-until-release
  convention (mirroring Chunks 02/03). Part (i) window quantification stays deferred (adopter-scale) —
  not pulled in.

---

### Chunk 05: SPIKE-S2 live dry-run + MG4 scrub workflow (C1 + C2)

**Goal:** Prove the migration path on a throwaway repo and build the one-time pre-migration scrub, so the
real run (Chunk 06) is a rehearsed, owner-confirmed act.

**Covers:** ship-list items 5 (C1 SPIKE-S2), 6 (C2 MG4 scrub).
**Depends on:** ~~Chunk 02 (target-pin)~~ *(no such pin — corrected 2026-07-24)*, Chunk 03 (scrub safety rails), Chunk 04 (metering — so the dry-run
measures the real paced behavior)
**Type:** code + operator verification (live GitHub side effects on a throwaway repo)
**Foreign API:** `gh` (real issue create/close) — `verify-api` step 0 already met in Chunk 02; re-confirm
non-collaborator label behavior here is out of scope (that's Chunk 08's XP6 item).

**Done when:**
1. **SPIKE-S2** live dry-run on a throwaway copy of prawduct's repo, run with `--archive-scope all` and
   the volume lever disabled — settles the real pacing constants NFR §9 S2 now requires.
2. **MG4 scrub workflow** built: model-surfaced stale/dup candidates → owner-confirmed dispositions; the
   model is in the *decision*, never the data plane (G1/MIG-5). Runbook binds `--repo` via Chunk 03's step.
3. Dry-run results recorded to `.prawduct/operator-verification.md`; no unintended writes to any real repo.

**Offline prep 2026-07-24** (the *code* half; the live dry-run + recording stay the operator's — Type is
"code + operator verification"). Done-when #2 (the MG4 scrub *workflow*) was already satisfied —
`skills/backlog/migration-scrub.md` + Chunk 03's Step 0 target-bind cover every clause; no re-author. The
genuine offline gap was the SPIKE-S2 harness (`tests/spikes/s2_migration.py`): it could not measure the
paced burst done-when #1 needs, nor even import standalone (a `ModuleNotFoundError` regression from the
v3.1.1 relocation, GOV-4H7T — fixed). Now instrumented — `--archive-scope {all|open}` (default `all`) +
an injected `Pacer` whose counters (`rest_points_charged` / `rest_point_waits` / `archive_burst_wall_
seconds` / budgets) land in the recorded facts — so the operator run is turnkey and will *settle* NFR §9
S2's pacing constants, not just record volume.

**Live half landed 2026-07-24** (done-when #1 + #3 met; recorded as **VRF-009** in
`operator-verification.md`). Ran `--archive-scope all` against the private throwaway
`brookstalley/prawduct-s2-dryrun-20260724` — live tally **148 open / 147 closed / 295 total** (exact),
`fidelity_ok`, 294 aliases minted / 0 new PFX, `resume_created_duplicates: 0`. **§9 S2 settled in the
negative:** `rest_point_waits: 0` **and** `content_creation_waits: 0` — under the *serial* importer the
Pacer budgets (80/min, 500/hr, 900 pts/min) never bind; serial `gh` round-trip latency caps the burst at
~500 pts/min (5,360 pts over ~18 min wall), so the point ceiling is a non-binding safety belt, not the
governor. (This *corrects* the pre-run forecast that 147 archived items would breach 900/min — that
conflated total volume with per-minute rate; the ceiling would bind only under parallelized writes.)
**Still open (not blockers for #1/#3):** MIG-3 relationships not exercised (source has no native graph),
PROBE-LAT absolute value contaminated by post-burst backoff ~~(shape confirmed batched-not-N+1)~~
**— that parenthetical is RETRACTED (2026-07-28): the shape was never confirmed and could not have
been. The probe varies `limit`, and `pick` applied `limit` only after fanning out over every eligible
issue, so the reading was flat by construction. The fan-out was N+1 REST throughout; Chunk 05b bounded
it —**, ID-4
node_id-across-transfer not run (`--transfer-to` omitted). Chunk stays `[ ]` (release convention); no
`chunks=05` change-log tag until release (Chunk 09).

---

### Chunk 05b: `pick` honesty + fan-out cost, ahead of the migration

**Goal:** Fix two `pick` defects that Chunk 06 would otherwise make permanent and universal across the
whole migrated backlog. Added 2026-07-28, after a pre-Chunk-06 read of the migration path.

**Covers:** the `pick`-path slice of BKL-3N8Q (not the whole item — its foreign-API verification half
stays open) and the PROBE-LAT N+1 that VRF-009 recorded but did not fix.
**Depends on:** —  ·  **Type:** code (bugfix)  ·  **Critic mode:** chunk (`plugin/lib/backlog/**` is
governance-protected → full Critic + `/prawduct:pr`)

**Why it gates Chunk 06.** The importer maps `related:` to **no native edge** — it is carried in the
issue body (`migrate.py`), and the only native-relationship code in that module is the *export* path.
So after the migration every item reads back **zero** native dependencies, permanently. Two consequences,
both of which get worse the moment the backlog is 170 issues instead of a test fixture:

1. **`pick` reported absence of data as a verified all-clear.** `_why` emitted "no open blockers"
   unconditionally, so post-migration every item would carry a confident all-clear derived from a field
   the migration guarantees is empty. This is BKL-3N8Q's failure mode — filed there as *occasional*,
   made *universal and permanent* by the migration.
2. **The dependency fan-out ran over every eligible issue before `limit` was applied.** One REST read
   per open ready item on every `pick`, regardless of `--limit`.

**Done when:**
1. `_why` distinguishes **"no blockers recorded"** (empty read) from **"all N blockers closed"**
   (verified clear). ✅
2. The fan-out is taken lazily in rank order and stops at `limit`. Ranking does not depend on blocker
   state, so the result set is provably unchanged — only the cost differs. ✅
3. Tests pin both, including that laziness does not under-fill when a top-ranked candidate is blocked. ✅
4. The four surfaces describing the old mechanism are corrected: the `query` module docstring,
   `documentation/backlog-service-data-model.md`, `documentation/backlog-service-api-contract.md`, and
   `build-plan-backlog-service.md` (whose "batched-GraphQL" claim was already false — there is no
   GraphQL in `plugin/lib/backlog/`, as VRF-009 records). ✅

**Deliberately NOT done:** mapping `related:` → native `blocked_by` at import. Most `related:` links are
"see also", not blocking, so synthesizing native edges from them would manufacture false blockers across
the entire backlog — strictly worse than recording none. If native blocking relationships are wanted
post-migration they should be authored deliberately via `link`, not inferred from prose.

**Verification:** suite **2728 passed, 7 skipped** (JUnit-backed, recorded 2026-07-28). Backlog flip owed
at Chunk 09 — see § Deferred to Chunk 09.

---

### Chunk 06: The real prawduct migration + VRF-006 (C4) — IRREVERSIBLE, operator-run

**Goal:** Migrate prawduct's own backlog to GitHub Issues, `--archive-scope all`, fully metered. This is
the dogfood and its own acceptance evidence. GitHub has no issue-delete and never reuses numbers (MG1) —
this is why Chunks 02–05 gate it.

**Covers:** ship-list items 9 (C4), 12 (VRF-006); closes BKL-6M4T, BKL-8K2N.
**Depends on:** Chunk 02, Chunk 04, Chunk 05 (and Chunk 03's safety rails must be live)
**Type:** code (cutover) + operator verification — **operator runs the live migration**
**Critic mode:** cumulative (the migration is the keystone act; review the whole trajectory)

**Done when:**
1. MG4 scrub run for real (owner-confirmed dispositions) against prawduct's backlog.
2. Bulk import (`backlog.md` + archive → issues), idempotent/resumable, keyed on the id:PFX alias with
   BKL-4W7H's self-healing fallback; the archive leg runs one paced create + one *metered* close per item.
3. **VRF-006** — the migration itself is the acceptance evidence: post-migration `get`/`list`/`pick`
   resolve real PFX ids; counts reconcile; no duplicates on a re-run.
4. The `backlog-service-migration-required` advisory resolves *as a consequence* (not separate work).
5. Recorded to `.prawduct/operator-verification.md` with a rollback note (per MG1, rollback = close, not
   delete).

---

### Chunk 07: Briefing / gates repoint through the adapter (C5)

**Goal:** Now that prawduct's backlog is on Issues, make the SessionStart briefing and the gates read
through the adapter instead of the frozen markdown.

**Covers:** ship-list item 10 (C5).
**Depends on:** Chunk 06
**Type:** code (lib/ + hooks)

**Done when:**
1. Briefing/gate reads go through the adapter using **snapshot.read + detached refresh** (never sync
   counts on the hot path); the 30s-timeout default is fixed (BKL-8P2R's shipped contract).
2. Authority fails closed, advice fails soft: on adapter auth/unavailable failure the briefing surfaces a
   clear NOTE and never silently serves stale markdown as live.
3. A real-slowness never-block test (G2) covers the degraded path.
4. Offline suite green.

**Scoping audit 2026-07-24 (offline, code-read — no code written): all four done-whens appear ALREADY
SATISFIED on develop. Chunk 07 is very likely verification-only, like Chunk 01.** Confirm before
building; do not re-author what is already there (the Chunk 05 done-when-#2 lesson — the MG4 workflow
was already complete and nearly got rewritten).

- **#1 —** `lib/briefing.py:675-720` (`_backlog_pending_line`) is already cutover-aware: post-cutover it
  reads the `briefing_counts` snapshot with visible age and fires the **detached** warm
  (`snapshot.spawn_refresh`); pre-cutover it parses markdown as before. Its docstring states the
  never-block property structurally — "the briefing path touches **no network, ever** … satisfied
  structurally, not by a timeout." BKL-8P2R's 30s default is in place (`lib/backlog/transport.py:258`).
- **#2 —** the fail-visible path exists and is deliberate: the snapshot is read *before* the warm is
  fired precisely so the no-snapshot line can only claim what is true, with a distinct line for
  "warming" vs "the warm never started" (the code names the standing-falsehood failure it avoids, G3).
- **#3 —** `tests/test_briefing_functions.py:692` — `test_never_blocks_even_with_a_hanging_backend`,
  asserting `elapsed < 2.0` against a hanging backend, plus `:673`
  `test_post_cutover_no_snapshot_degrades_visibly`.
- **#4 —** suite green (2572 passed / 7 skipped, 2026-07-24).

**On the chunk title's "gates" half:** `lib/gates.py` contains **zero** backlog references. The backlog
readers outside `/prawduct:backlog` are the `DORMANT_CHECKS` set (`lib/backlog_probes.py:307`) — the
Critic's reconciliation walk + hygiene checks, the PR reviewer's two consistency checks, the janitor's
Backlog Health block, and the three `norm_probes` time-domain probes. The `backlog-checks-dormant`
advisory explicitly defers restoring those to **W1 (the read-through cache)**, not to this chunk, and
that advisory already ships. So there is no unbuilt "gate repoint" work hiding behind the title in this
release — the honest-dormancy posture *is* the v3.2.0 answer.

**Consequence for the critical path:** if this holds, the tail is `06 → (07 ≈ free) → 08 → 09`, and 08
becomes the only substantial chunk left after the migration. **Chunk 07 therefore absorbs the advisory
lift below** — it has the capacity, it is post-migration (so the proof exists), and putting a fleet-wide
behavior change in a code chunk gets it a Critic review, which parking it in Chunk 09's release ceremony
would not.

**Done when (added 2026-07-24):**
5. **Lift the `backlog-service-migration-required` hold (BKL-6J2X → BKL-7D3V).** Register
   `probe_migration_required` directly in `lib/backlog_probes.py` `register()` in place of
   `_probe_migration_required_held`, delete the no-op wrapper, and flip
   `tests/test_backlog_probes.py::TestMigrationRequiredProbe::test_held_out_of_live_roster`
   (`:215-225`) back to asserting the **live roster** surfaces the advisory — it currently pins the
   held behavior. *(Named, not line-numbered: the name survives the edits that shift line numbers,
   which is the drift this very chunk is correcting in BKL-6J2X's `refs:`.)*
   Update the module docstring and the `register()` docstring, which both describe the hold.

**[DECISION — owner, 2026-07-24: the advisory SHIPS LIFTED in v3.2.0. | BKL-7D3V]** BKL-6J2X's recorded
lift condition — (i) BKL-2Q7F/BKL-8V3D/BKL-5N9W resolved, (ii) the path proven on one real end-to-end
run — is discharged by Chunks 02–03 and Chunk 06 respectively, so the hold's own precondition is met and
the owner elected to lift rather than carry it forward. Recorded here so it is a decision, not the
probe's default deciding (BKL-6J2X's own instruction).

**Recorded dissent, so a later reader sees the trade rather than assuming it was unexamined:** the
audit's recommendation was to ship held and let the consumer `CHANGELOG.md` headline carry discovery.
Two costs come with lifting, and they are now live risks rather than hypotheticals:
- **BKL-8W2M is unbuilt** (`stage: requirements` — a *product decision* before it is code). There is no
  declared terminal-markdown state, so a repo that will never host on GitHub — no remote, non-GitHub
  forge, or an owner who simply does not want an Issues tracker — has **no way to resolve** a `warn` it
  receives every session, and advisory dismissal is per-user, so a fresh clone re-nags. **This promotes
  BKL-8W2M from someday-work to the item that makes the lift survivable**; it should be scheduled
  immediately behind v3.2.0 if it does not make the release. BKL-4C9P is its sibling.
- **The proof is n=1 on prawduct-shaped data.** VRF-009 ran against a copy of prawduct's own backlog,
  and Chunk 06 migrates that same backlog. No consumer-shaped backlog has been migrated. Draining
  Chunk 01's VRF-005/007/008 against a real consuming repo is the cheapest thing that narrows this gap
  and it is unblocked today.

---

### Chunk 08: MG5 / upstream filing — file-upstream op · report-bug rewrite · drop-box retirement

**Goal:** Ship the drop-box's 1:1 replacement per the owner-approved upstream-filing design
(`backlog-service-upstream-filing.md`). The drop-box is retired **only together with** its live
replacement — never before (lockstep). Kept as **one chunk**; split along the 08a (adapter op + contract
test) / 08b (skill rewrite + drop-box retirement + norm amendment) seam **only if it runs large**
(sizing policy above). The Done-when list is grouped by that seam so the split is mechanical if needed.

**Covers:** ship-list item 11 (C6/MG5); closes BKL-7Q4M, BKL-9XQ2, BKL-0QR1.
**Depends on:** *(revised 2026-07-24 — BKL-4T9C amendment)* **08a: nothing.** The no-self-file check no
longer keys on `backlog_service_repo` alone (it resolves identity from the git remote too and fails
closed), so the check is live without the migration — which was the only hard reason 08 sat behind
06/07. 08a is buildable and testable offline against `tests/fakes/fake_github.py`. **08b: Chunk 06** —
the drop-box↔replacement lockstep (§7) and the `untriaged-upstream-reports` repoint still want the live
target. Note the `[XP6 verify]` step (done-when #4) needs a live throwaway issue regardless, so the
chunk cannot *complete* entirely offline. *(No longer on Chunk 02 either: the target-pin/preview it was
to reuse is built here — Chunk 02 re-scope, 2026-07-24.)*
**Type:** code (skills/ + lib/) — governance-protected → full Critic + PR
**Exposed API:** `prawduct-hook backlog file-upstream` — the preview/`--approve`/digest contract and the
error vocab (`filing-disabled`, `target-not-pinned`, `self-file`, `approval-mismatch`) are recorded in
`api-contract.md` §2.4 (design §8 coherence edit).
**Visual change:** yes — the `report-bug` verbatim-payload review is operator-facing; queue a VRF entry.

**Done when (08a — adapter):**
1. **`file-upstream` op** — preview-by-default (renders the exact §2 payload, computes
   `payload-digest`, sends nothing); a second `--approve sha256:<digest>` call sends only if **all five
   §5 checks** hold: preference ≠ `never-file`, target pinned + no-self-file (**built here** — the fixed
   canonical-upstream pin + self-file refusal; promote `migrate_plugin.py:39`'s literal to a constant and
   replace `test_no_upstream_content_egress.py` in the same breath), approval matches the bytes,
   authenticated `gh` identity. Any failure → structured error, files nothing.
   **Note (BKL-4T9C, 2026-07-24):** the amended no-self-file check resolves identity from the git remote
   **as well as** `backlog_service_repo`, and fails closed when neither resolves. **No git-remote
   resolver exists yet** — `lib/gitstate.py` has no `remote get-url` helper, and `lib/backlog/context.py`
   is execution-context only (its sole repo comparison is the Actions-only `GITHUB_REPOSITORY` vs
   `PRAWDUCT_PR_HEAD_REPO` fork check — env-sourced, not git-sourced). Budget a small helper
   (`git remote get-url origin` → `owner/repo` via `ids.parse_repo`) plus its unresolvable / malformed /
   no-remote cases, all of which must fail **closed**.
2. **Label-less payload (§2)** — `[prawduct]` title prefix + fixed body sections + the *trimmed*
   `prawduct:` provenance block (`v`/`found_in`/`source-key:` only; the product-name-bearing `source:`
   field is **not** emitted). `found_in` sourced from `prawduct-hook version`, `(unknown)` if unreadable.
3. **XP7 contract test** asserting the five checks; it **replaces**
   `tests/preferences/test_no_upstream_content_egress.py` (the interim test stays live until this lands;
   the norm is amended, never weakened).
4. **[XP6 verify]** confirm current GitHub non-collaborator label behavior on a throwaway issue — do not
   ship on recall (design §9).

**Done when (08b — skill + retirement + coherence):**
5. **`report-bug` rewrite** — step 3 becomes L1-recompose → `file-upstream` preview → (ask-user) show
   payload + confirm-synthetic-code gate → approve → send. `Found in:` unchanged (already sourced). The
   inert-fallback changes to submit-or-nothing: **no local capture** of an upstream bug; the tracker-URL
   pointer stays as the no-reachable-path fallback.
6. **Consent preference** — add `Upstream filing: ask-user | always-file | never-file` (default
   `ask-user`) to `project-preferences.md`, mirroring `PR merge strategy`.
7. **Drop-box + probe retirement** — retire the `bug-inbox` resolver, `.bug-inbox` pointer,
   `incoming-bugs/`, and repoint the `untriaged-upstream-reports` probe
   (`lib/upstream_probes.py`) from `incoming-bugs/*.md` to the §6 intake count (open issues whose title
   carries the `[prawduct]` convention, no triage label — exact query pinned here at build).
8. **§8 coherence edits** (do at build so nothing drifts): api-contract §2.4 (preview/approve/digest +
   five-check refusal set + error vocab); security-model §1a/§5 (attended-only + intake reconciliation);
   data-model §5 (`source-key:` trimmed-upstream-block note).
9. **§ Direction norm amendment** — `security-model.md` § Direction: `Status: in-transition →
   steady-state`, asserting the XP7 contract (target-pinned, authenticated, refuses-without-approval,
   no-self-file). Amended, never weakened.
10. VRF entry appended to `.prawduct/operator-verification.md` for the review flow.

---

### Chunk 09: Release mechanics — bump · change-log · regen · tag

**Goal:** Ship v3.2.0. The version bump *is* the release trigger.

**Covers:** ship-list items 13–17.
**Depends on:** Chunks 01–07 + 05b *(re-cut twice on 2026-07-28: "01–08" → "01–06 + 05b" at the
narrowing, then → "01–07 + 05b" when the hard-cutover ruling returned Chunk 07. Chunk 08 stays out —
depending on it would make Chunk 09 permanently unsatisfiable.)*
**Type:** code (version + change-log) + release ceremony

**Done when:**
1. Bump `VERSION` + `.claude-plugin/plugin.json` → 3.2.0 (A2). **Both files** — note they live under
   `plugin/` (`plugin/VERSION`, `plugin/.claude-plugin/plugin.json`), not at the repo root.
2. Flip **every** unreleased change-log entry to `status=shipped` + `release=v3.2.0` — enumerate, don't
   sample (REL-2N8K lesson). The running enumeration is § "Deferred to Chunk 09" below.
3. `prawduct-hook regen-views --check` (fail-closed pre-flight) → then `regen-views` for real.
4. Tag `v3.2.0`, push, confirm the version-delta banner.
5. **Consumer-facing release note** — add the v3.2.0 headline to `plugin/CHANGELOG.md`. This is the
   surface the version-delta SessionStart banner shows a repo on upgrade, and v3.1.1's headline
   explicitly primed consumers for it ("The GitHub-Issues backlog service is deliberately **not** in
   this release — it ships when it is"). It must state: the service is here; **your backlog does not
   migrate automatically**; the command to run when you want it. ~~and — per the v2.3.2 precedent for
   `stamp-merged` — that agent memory / learnings saying "write to `incoming-bugs/`" are obsolete
   (Chunk 08 retires the drop-box)~~ — **STRUCK 2026-07-28: Chunk 08 is deferred, so the drop-box is
   NOT retired in v3.2.0.** Announcing it would be false to the fleet, and would invalidate a path that
   still works in every consumer's agent memory while its replacement is unbuilt. `incoming-bugs/`
   remains the upstream path in v3.2.0 — say nothing about it. Also name the two surfaces that ship unproven-live: MIG-3
   relationship reconstruction (in-process test evidence only — neither the SPIKE-S2 source nor
   prawduct's own backlog has a native graph) and ID-4 node_id-across-transfer (VRF-009).
   **Appended 2026-07-28 — three fleet-visible governance changes landed after this list was first
   enumerated (2026-07-24), and "enumerate, don't sample" binds this list to its own rule:**
   `janitor` is now `disable-model-invocation: true`, so the model can no longer self-invoke it (a
   `norm_probes.py` advisory still points its `recommended_action` there — user invocation is
   unaffected, model-initiated is not); `pr`'s grant narrows `Bash(gh *)` → `Bash(gh pr *)`; and
   janitor/pr/runbook lose their backlog grants entirely. Consumers who scripted around any of these
   need to know before upgrading, not after.
6. **Post-tag by construction:** VRF-002, VRF-003 (a new agent type + hook aren't live until the version
   ships) — run immediately after promotion with a rollback plan; do not hold the release for them.
7. **OWNER RELEASE GATE (stated 2026-07-28) — nothing reaches `main` until the owner has exercised the
   candidate locally in sibling repos via `--plugin-dir`.** This is a **blocking precondition on the
   develop→main promotion**, not a post-tag check and not a step Claude can discharge: the owner runs it,
   the owner clears it. Record the result in `.prawduct/operator-verification.md` as the release's
   go/no-go evidence, naming which sibling repos were exercised and what was checked.

   *Why it binds here.* This release changes fleet-visible governance — `janitor` becomes
   `disable-model-invocation: true`, `pr`'s `Bash(gh *)` narrows to `Bash(gh pr *)`, three skills lose
   their backlog grants, and (Chunk 06) the backlog moves to Issues. Every one of those is invisible in
   this repo's own suite and only shows up when a *consuming* repo loads the candidate plugin. `--plugin-dir`
   is the only mechanism that exercises that path before publication.

8. **OWNER RELEASE GATE (stated 2026-07-28) — "GitHub Issues is working great."** Consumer-facing
   go-live is blocked until the backlog service is genuinely usable day-to-day, not merely migrated.
   **Not yet a verifiable criterion — it must be sharpened before it can gate anything** (an
   unverifiable gate either blocks forever or gets waved through). Candidate acceptance set, owner to
   confirm: Chunk 01 VRFs drained · Chunk 06 migration + VRF-006 (`get`/`list`/`pick` resolve real PFX
   ids, counts reconcile, no duplicates on re-run) · the four go-live blockers flipped · **and a
   dogfood period where `/prawduct:backlog` is the only path used, with no fallback to markdown.**

   **SHARPENED BY OWNER RULING 2026-07-28 — this gate is FUNCTIONAL COMPLETENESS, not performance.**
   Verbatim: *"all functional requirements working great. NFRs like performance can lag to a later
   release. But we cannot be functionally broken for any supported scenario."*

   So the criterion is: **for every supported scenario, no functional requirement is broken, unproven
   against the real API, or silently wrong.** Two direct consequences:

   - **`BKL-2K8V` (pick ~12.4 s at 209 issues, ~6× the NFR §4 floor) does NOT gate this release.**
     It is an NFR and explicitly deferred by the ruling. W1 (raw-HTTP fast-path / scoped query) stays
     out of v3.2.0. Record the number in the release note as a known, accepted characteristic rather
     than letting a dogfood session rediscover it as a surprise.
   - **What DOES gate: anything verified only against the in-process fake.** `BKL-3N8Q` records that
     the relationship/timeline foreign-API shapes are **fake-verified only** and the `verify-api` step
     has never run. That is precisely the "functionally broken for a supported scenario" case the
     ruling names — if a real payload shape differs from the fake, `pick` reports blocked items as
     ready with a confident verdict, and no test in the suite can see it.

   **The acceptance set is therefore a supported-scenario functional audit, not a feature checklist.**
   Enumerate the scenarios v3.2.0 claims to support, and for each name the functional requirements it
   depends on and how each is verified (real API vs. fake). Upstream filing is **out of scope**:
   Chunk 08 is deferred, so it is not a supported scenario in v3.2.0 and the `incoming-bugs/` drop-box
   remains the path.

   **OWNER RULING 2026-07-28 — HARD CUTOVER. A release does not support both markdown and GitHub
   Issues.** Verbatim: *"we can't support both markdown and gh in a release... it will be chaos. it's
   a hard cutover."* This reverses the scenario list above and changes v3.2.0's shape:

   - **"Stay on markdown" is NOT a supported scenario.** Drop it from the audit. Two hours ago this
     plan recorded the opposite (BKL-8W2M's permanent migration nag read as a functional break of a
     supported scenario); under a hard cutover that advisory is *correct behaviour*, not a defect.
     BKL-8W2M's fix-shape inverts accordingly — re-read it before working it.
   - **CHUNK 07 RETURNS TO v3.2.0, reversing this morning's deferral.** Its remaining content is the
     **advisory lift** (BKL-7D3V / BKL-6J2X) — the mechanism that drives the fleet to migrate. A hard
     cutover *requires* it: with the hold in place, the release ships a cutover it never tells anyone
     to perform. (Chunk 07's four original repoint done-whens were already satisfied per the
     2026-07-24 scoping audit, so what returns is small.) **Chunk 08 stays deferred** — upstream
     filing is unrelated to the cutover.
   - **This is a BREAKING release for every governed repo.** Every consumer must migrate on upgrade;
     GitHub has no issue-delete, so per-repo it is one-way. The release note and the fleet advisory
     must both say so plainly, and the migration runbook stops being an optional path.

   **OPEN QUESTION — blocks the audit's scenario list, owner to answer.** What happens to a governed
   repo that *cannot* host GitHub Issues — not on GitHub, a different forge, or local-only? Under a
   hard cutover with no markdown fallback, such a repo has no supported configuration at all. Either
   (a) v3.2.0 declares GitHub a hard prerequisite for governance and says so in the release note, or
   (b) markdown survives as an explicitly-declared terminal state for non-GitHub repos — which is a
   narrow, *declared* dual-support, materially different from the drifting dual-support the ruling
   rejects. This is not a detail: it decides whether the release breaks an entire class of consumer.

9. **OWNER RELEASE GATE (stated 2026-07-28) — "duplicate review and other friction is sorted."**
   Tracked by **CRT-8N5V** (parent) with **COV-3M8Q** and **GOV-6D4Q**. Also **not yet verifiable** as
   stated. Candidate criterion: a work cycle of ordinary size completes on **one** review round, with
   the round count observed rather than asserted.

   **Confidence note — this has recurred once already.** `CRT-4J8W` (shipped 2026-06-10,
   `gate-soundness ch.05`) was the owner's prior escalation on the same symptom — "review phase ran
   30+ min wall clock for ~5 min of work" — and named the same "re-review treadmill" mechanism. It was
   fixed at the gate-chaining level and the failure returned. **A prose-only fix (`67fe565`) should
   therefore not be treated as discharging this gate**; CRT-8N5V's remaining-scope item 2 (structural
   enforcement — `critic-begin` refusing a round when the gate already passes with no blocking
   outstanding) is the part that binds regardless of whether the prose is read.

   *Relation to REL-8P6M.* That item's finding is that the release runbook's Phase 1 has **no
   releasability gate** — it asks only "is anything unreleased?", never "is everything fit to ship?" This
   done-when is the owner supplying that missing gate by hand for v3.2.0. **REL-8P6M should generalize it
   into the runbook** rather than leaving it as a one-release instruction that the next release re-derives
   or forgets — which is the same expiring-artifact failure REL-8P6M already records against
   `release-plan-v3.1.2-pruned.md`.

#### Deferred to Chunk 09 — the running enumeration

This release adopted a `[ ]`-until-release convention: chunks build and verify their work but defer the
backlog `status=shipped` flip to here. That convention only survives contact with Chunk 09 if the
deferrals are **accumulated as they happen** — REL-2N8K is precisely the lesson that a release-time
re-derivation from memory samples instead of enumerating. **Append to this list at every deferral.**

**Backlog status flips owed** (via `/prawduct:backlog update`, never hand-edits):

| Item(s) | Deferred by | Flip |
|---|---|---|
| BKL-4W7H | Chunk 01 | `promoted` → `shipped` *(still pending — Chunk 01 not yet drained)* |
| BKL-8V3D | Chunk 02 | → `shipped` |
| BKL-2Q7F · ONB-3F9P · BKL-5N9W · BKL-6J2X | Chunk 03 | → `shipped` |
| BKL-6X5D part (b) | Chunk 04 | → `shipped` *(part (i) stays deferred — adopter-scale, not pulled in)* |
| — | Chunk 05 | *(no backlog IDs — C1/C2)* |
| BKL-3N8Q — **partial, do NOT flip to shipped** | Chunk 05b | Append a note recording that the `pick`-path half (the vacuous "no open blockers" verdict) is fixed, and **narrow the item's remaining scope** to its foreign-API verification half — `list_blocked_by`/`list_sub_issues`/`list_timeline` are still shape-verified against the fake only, which is the half that needs the unrun `verify-api` step. Its `refs:` line-anchors into `query.py` (`:180`, `:368-369`) are stale after this chunk; re-anchor by symbol (`pick`, `_why`, `_blocker_clause`) per this repo's own preference. **Its id is cited by `project-state.yaml design_decisions.infrastructure_dependencies.integration_test_strategy` — do not renumber.** |
| BKL-6M4T · **BKL-8K2N** | Chunk 06 | → `shipped` — *(BKL-8K2N added 2026-07-28: it was in no flip list and no chunk's `closes` line, while its own body reads **GATES CHUNK 06** and ~95 lines of its work already shipped in `aaf068f`. Nothing would have flipped it. Its remaining half is the progress heartbeat — without it the ~900-issue irreversible run emits nothing for 18–40 min, since `rest_point_waits: 0` means the throttle announcements never fire and the runbook invokes import without `--json`.)* |
| **BKL-7D3V** · **BKL-6J2X** | Chunk 07 | → `shipped` — **ACTIVE AGAIN (2026-07-28, hard-cutover ruling).** Struck as out-of-release earlier the same day, then restored when the ruling put Chunk 07 back: the advisory lift closes the decision item **and** retires the hold it discharges, and a hard cutover needs that advisory firing. *(Corrected 2026-07-24: this row read "no backlog IDs" while the traceability table already credited Chunk 07 with closing BKL-7D3V.)* |
| ~~BKL-7Q4M · BKL-9XQ2 · BKL-0QR1 · **BKL-4T9C**~~ | Chunk 08 | **DO NOT FLIP — out of v3.2.0 (deferred 2026-07-28).** Same reasoning as the Chunk 07 row. Note BKL-7Q4M is still marked a **3.2.0 release blocker** in its own body — that designation predates the narrowing and is now stale; reconcile it via `/prawduct:backlog` rather than reading it as a contradiction of this row. |

**Unreleased change-log entries owed `status=shipped | release=v3.2.0`** (verified against the tree
2026-07-24 — re-grep `scope=v3.2.0-golive` at Chunk 09, since chunks 05b and 06 will add more; the
original reason read "chunks 06–08", which the 2026-07-28 narrowing falsified — the re-grep is correct
either way, but its stated reason was not):

1. Chunk 05 offline prep — *also needs `chunks=05` added*; the tag was deliberately withheld until the
   live half landed (it has, VRF-009), so Chunk 09 adds it rather than minting a second entry.
2. Chunk 04 (`chunks=04`)
3. Chunk 03 (`chunks=03`)
4. `verify-chunk-refs` branch-name false-positive fix — a rider fix, correctly carries **no** `chunks=`
5. Chunk 02 (`chunks=02`)
6. The 2026-07-28 develop-integration fix entry (git-ref carveout + the REST-point floor sweep) — a
   rider fix, correctly carries **no** `chunks=`

**One owed entry does NOT exist yet, so the Chunk 09 re-grep cannot recover it.** Commit `aaf068f`
(BKL-8K2N — pacing observability: run-summary counters + the two blocking-sleep announcements) shipped
~95 lines of production code across `plugin/lib/backlog/cli.py` and `plugin/lib/backlog/migrate.py`
and has **no change-log entry**. **It carried two things, and this note used to name only one:** the
same commit also landed the `security-model.md` § Direction **norm amendment** (destructive-action
approval moves from the absolute `--apply`/dry-run form to operation-level, owner ruling 2026-07-24).
The decision itself is properly recorded in the artifact, so the norm-amendment check passes — but the
release note derives from the *change log*, so authoring the owed entry from a note that named only
the pacing half would drop a governance change out of the v3.2.0 record entirely. A `scope=v3.2.0-golive` re-grep only finds entries that were written,
so this one must be *authored* at Chunk 09, not swept up. Raised by the 2026-07-28 verify-resolutions
pass (its R-5 / R-23 restated); tracked so the gap is visible to the step that would otherwise miss it.

---

## Critical path & parallelization

*Re-cut twice on 2026-07-28: first for the narrowed release (07/08 deferred; 05b added), then again
when the hard-cutover ruling returned 07.*

```
01 ──┬─► 02 ──┬─► 03 ──┐
     │        │        ├─► 05 ─► 05b ─► 06 ─► 07 ─► 09   ← v3.2.0 ends here
     └─► 04 ──┴────────┘

                                  (deferred, a later release)  08
```

- **Critical path:** `01 → 02 → (03 ∥ 04) → 05 → 05b → 06 → 07 → 09`.
- **Chunk 08 is out of v3.2.0** (owner decision 2026-07-28) — it adds governed surface and waits behind
  the deletion-only simplification pass (GOV-6D4Q). It keeps its chunk body and its Chunk 09 flip row
  so a later release picks it up unchanged.
- **Chunk 07 was deferred and then restored the same day.** Under "07/08 add governed surface" the
  deferral was right; under the hard-cutover ruling it is wrong, because 07's remaining content is the
  advisory that *tells the fleet to migrate*. A hard cutover that never announces itself is not one.
  It sits after 06 deliberately: the advisory should start driving migrations only once prawduct's own
  has proven the path.
- **05b** (the `pick` honesty + fan-out fix) sits between 05 and 06 deliberately: both defects it
  fixes become permanent and backlog-wide the moment 06 runs.
- With the B1 discovery already settled, the **real migration (06)** is the long pole, not MG5.
- **Runs in parallel:** Chunk 04 (Pacer) alongside 02/03; the Chunk 01 VRF-005/007/008 verifications
  (no code — the relayout merge is done) alongside 02.
- **Operator-gated (live side effects):** 05 (throwaway repo), 06 (the real, irreversible migration).
  The operator runs the live steps.

## Traceability to the release-plan ship list

| Ship-list item(s) | Chunk | Backlog IDs closed |
|---|---|---|
| 3 (VRF-005/007/008) | 01 | relayout merged via PR #137; BKL-8P2R already shipped, BKL-4W7H → flip to shipped |
| 19 · 18 (adapter leg) | 02 | BKL-8V3D |
| 18 (skill leg) · 20 · 21 | 03 | BKL-2Q7F, ONB-3F9P, BKL-5N9W, BKL-6J2X |
| 8 | 04 | BKL-6X5D part (b) |
| 5 · 6 | 05 | — (C1/C2) |
| 9 · 12 | 06 | BKL-6M4T |
| 10 · 21 (lift leg) | 07 | BKL-7D3V (the ship-lifted decision); BKL-6J2X's hold retired (C5; BKL-8P2R contract honored) |
| 11 | 08 | BKL-7Q4M, BKL-9XQ2, BKL-0QR1 |
| 13–17 | 09 | — (release ceremony) |

Items 1, 2, 7 (A1, PR #134, BKL-4W7H) are already done/merged-pending; A2/A3 owner decisions are recorded.
