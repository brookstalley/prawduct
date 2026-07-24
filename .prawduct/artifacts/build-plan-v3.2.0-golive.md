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
      - "A governed product's content never leaves its own repo/owner; any cross-owner/public-plane filing surface is an owner decision (Status: in-transition, tracks BKL-7Q4M) → conforms + amendment proposed (Chunk 08 is the reviewed design the norm waits on; it moves in-transition→steady-state when §5's contract test replaces the interim egress test)"
  - artifact: architecture
    dispositions:
      - "The adapter never manages a token — `gh` owns the credential → conforms (Chunk 02/08 resolve the session `gh` identity; no managed token introduced)"
      - "Authority fails closed; advice fails soft → conforms (the file-upstream/migration guards refuse-and-explain on any failed check; never a silent fallback)"
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
- [ ] Chunk 04: Pacer REST-point metering for the create+close archive stretch (C7)
- [ ] Chunk 05: SPIKE-S2 live dry-run + MG4 scrub workflow (C1 + C2)
- [ ] Chunk 06: The real prawduct migration + VRF-006 (C4) — irreversible, operator-run
- [ ] Chunk 07: Briefing/gates repoint through the adapter (C5)
- [ ] Chunk 08: MG5 / upstream filing — file-upstream op, report-bug rewrite, drop-box retirement (splittable 08a/08b)
- [ ] Chunk 09: Release mechanics — version bump, change-log flip, regen-views, tag; VRF-002/003 post-tag

Context: Plan authored 2026-07-24 from `release-plan-backlog-service-golive.md` + the upstream-filing
design; `active_build_plan` now points here. **Correction 2026-07-24:** the relayout merge (the old
Chunk 01) was already done — PR #137 landed it on develop 2026-07-23 — so Chunk 01 is now
verification-only (see Prerequisites). **Chunk 02 built 2026-07-24** (BKL-8V3D honest fix + guard test;
suite 2551 passed). **Chunk 03 built 2026-07-24** — the four safety rails (BKL-2Q7F scrub-runbook
target-binding + provision; ONB-3F9P *full* close incl. the `init-product --backlog-repo` + onboard/
doctor provisioning legs, owner decision; BKL-5N9W grant narrowing + metadata test; BKL-6J2X advisory
held). Critic chunk-mode clean (0/0/0); suite 2563 passed. Next: Chunk 04 (Pacer REST-point metering)
and Chunk 05 (SPIKE-S2 dry-run + scrub workflow), with the Chunk 01 VRFs (operator/live) in parallel.

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
**Depends on:** Chunk 02 (the target-pin lives at the adapter; the runbook binds to it)
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
   the resulting list with a metadata test. (Defense-in-depth, not the primary guard — the adapter
   target-pin from Chunk 02 is; CRT-9V4T caveat.)
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

---

### Chunk 05: SPIKE-S2 live dry-run + MG4 scrub workflow (C1 + C2)

**Goal:** Prove the migration path on a throwaway repo and build the one-time pre-migration scrub, so the
real run (Chunk 06) is a rehearsed, owner-confirmed act.

**Covers:** ship-list items 5 (C1 SPIKE-S2), 6 (C2 MG4 scrub).
**Depends on:** Chunk 02 (target-pin), Chunk 03 (scrub safety rails), Chunk 04 (metering — so the dry-run
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

---

### Chunk 06: The real prawduct migration + VRF-006 (C4) — IRREVERSIBLE, operator-run

**Goal:** Migrate prawduct's own backlog to GitHub Issues, `--archive-scope all`, fully metered. This is
the dogfood and its own acceptance evidence. GitHub has no issue-delete and never reuses numbers (MG1) —
this is why Chunks 02–05 gate it.

**Covers:** ship-list items 9 (C4), 12 (VRF-006); closes BKL-6M4T.
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

---

### Chunk 08: MG5 / upstream filing — file-upstream op · report-bug rewrite · drop-box retirement

**Goal:** Ship the drop-box's 1:1 replacement per the owner-approved upstream-filing design
(`backlog-service-upstream-filing.md`). The drop-box is retired **only together with** its live
replacement — never before (lockstep). Kept as **one chunk**; split along the 08a (adapter op + contract
test) / 08b (skill rewrite + drop-box retirement + norm amendment) seam **only if it runs large**
(sizing policy above). The Done-when list is grouped by that seam so the split is mechanical if needed.

**Covers:** ship-list item 11 (C6/MG5); closes BKL-7Q4M, BKL-9XQ2, BKL-0QR1.
**Depends on:** Chunk 07 (repoint — MG5 is post-migration, lockstep). *(No longer on Chunk 02: the
target-pin/preview it was to reuse is built here — Chunk 02 re-scope, 2026-07-24.)*
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
**Depends on:** Chunks 01–08
**Type:** code (version + change-log) + release ceremony

**Done when:**
1. Bump `VERSION` + `.claude-plugin/plugin.json` → 3.2.0 (A2).
2. Flip **every** unreleased change-log entry to `status=shipped` + `release=v3.2.0` — enumerate, don't
   sample (REL-2N8K lesson).
3. `prawduct-hook regen-views --check` (fail-closed pre-flight) → then `regen-views` for real.
4. Tag `v3.2.0`, push, confirm the version-delta banner.
5. **Post-tag by construction:** VRF-002, VRF-003 (a new agent type + hook aren't live until the version
   ships) — run immediately after promotion with a rollback plan; do not hold the release for them.

---

## Critical path & parallelization

```
01 ──┬─► 02 ──┬─► 03 ──┐
     │        │        ├─► 05 ─► 06 ─► 07 ─► 08 ─► 09
     └─► 04 ──┴────────┘
```

- **Critical path:** `01 → 02 → (03 ∥ 04) → 05 → 06 → 07 → 08 → 09`.
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
| 10 | 07 | — (C5; BKL-8P2R contract honored) |
| 11 | 08 | BKL-7Q4M, BKL-9XQ2, BKL-0QR1 |
| 13–17 | 09 | — (release ceremony) |

Items 1, 2, 7 (A1, PR #134, BKL-4W7H) are already done/merged-pending; A2/A3 owner decisions are recorded.
