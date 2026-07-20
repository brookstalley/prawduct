---
artifact: release-plan
version: 1
scope: backlog-service-golive
depends_on:
  - artifact: build-plan-backlog-service
  - artifact: backlog-service-prd
  - artifact: backlog-service-requirements
last_validated: 2026-07-20
---

# Release Plan — Backlog Service Go-Live

**Owner decision (2026-07-20):** wide release. *"We can't ship a partial product. And if prawduct's
own backlog migrates to gh issues, we have to bring in all that implies."*

This plan enumerates what blocks that release and the order to clear it. It is a **release plan**,
not a build plan — Chunk 06's build spec already lives in `build-plan-backlog-service.md` and is not
restated here.

## Why the consent policy is on the critical path, not beside it

`BKL-9XQ2` (upstream-filing consent) reads like a governance side-quest. It is not. PRD §8.9:

> Migrating prawduct's backlog makes prawduct's own **public** GitHub repo the live upstream target,
> so the drop-box's file-drop channel is retired.

The migration is *what makes upstream filing live*. Chunk 06 retires the drop-box and ships MG5's
replacement in the same breath. So the release cannot ship without an answer to "may an agent file
an issue, as the user, into a public repo?" — the design put that question on the critical path
before anyone noticed it was there.

Reinforcing this, verified in code 2026-07-20: the capability already exists and is merely
*uninstructed* — `skills/backlog/SKILL.md` grants `Bash(prawduct-hook backlog *)` (wildcard) and
`--repo owner/repo` is shape-validated only, with no owner constraint anywhere in
`lib/backlog/ids.py`. MG5 is the change that *instructs* it.

## Sizing (snapshot, not a fact)

prawduct's own backlog at `f8b38f7` on `develop`, 2026-07-20T14:54Z: **108 open · 2 promoted · 144
archive**, no separate archive file, across **29 distinct PFX prefixes** (`ADR ADV BKL BLD BRF COV
CRT DOC ENV GOV JAN JNT LRN MET MIG PR PRR REL SCN SEC STH STN SYN TEL TPL TST VWS WMK WT`).

**Treat every count here as a dated snapshot, never as a constant.** On 2026-07-20 four discodon
checkouts reported 384 / 389 / 349 / 319 open and the canonical one moved between two reads twenty
minutes apart — a live instance of the stale-views pain this project exists to kill. A count is
re-derived at the moment it is used, or it is not used. The 29 prefixes are the more durable datum:
they are the multi-prefix absorption stress the dogfood was chosen to provide.

## Blockers

### A — Owner decisions (cheap, unblock everything downstream, do first)

| id | decision | why it gates |
|---|---|---|
| **A1** | `--archive-scope` for prawduct's own migration: `all` or `open` | **Determines whether `BKL-6X5D` part (b) is a release blocker.** `open` ≈ 110 creates, no archive stretch, part (b) stays deferred. `all` ≈ 254 creates **plus 144 unpaced closes** — that is exactly the half-unmetered create-then-close stretch part (b) describes, so choosing `all` promotes B-tier work into this release. MG4b requires this be an explicit owner choice at scrub time regardless. |
| **A2** | Release version | The bump *is* the release trigger (`VERSION` + `plugin.json`). Backlog service going live is a subsystem landing; weigh against the standing "version conservatively" preference. |
| **A3** | `BKL-9XQ2` policy shape | Follows the B1 spike; listed here so it is not mistaken for a build task. |

### B — Discovery: `BKL-9XQ2` (the long pole)

`stage: research`, release-gating, capture-only in activity. Three sub-questions, unequal difficulty:

- **B1a — consent, two obligations.** Disclosure *at install* (a user who does not know the
  capability exists cannot evaluate a prompt) **and** consent *at file* (three-state preference:
  always / ask / never, default **ask**, regardless of repo visibility). Design constraint already
  established: this must bind at the **adapter**, not in skill prose — prose is what MG5 rewrites, so
  a prose-only guard is deleted by its own trigger.
- **B1b — evidence & data exfiltration.** Owner-flagged as genuinely unsolved. Security §3/§4 exist
  but were written for the adapter's own artifacts, not the consumer→public direction where the repo
  contents *are* the sensitive material. Prior art to start from, not to reuse. **This is the
  schedule risk in the whole plan** — it is a research question with an unknown answer, and
  everything else is execution.
- **B1c — label taxonomy** for issues arriving from consuming repos. Likely prawduct defines once and
  consumers adhere; unresolved. Adjacent to `GV6` (taxonomy provisioning) and `BKL-3T7X` / `BKL-7F3D`
  (issue standard, Issue Forms).

Known collision to resolve in the spike: `ask` collides with Security §1a (unattended operation, no
human present). The answer needs pinning as *don't file*, not *file anyway*.

### C — Build: Chunk 06

Prerequisite state verified 2026-07-20: `BKL-8P2R` **shipped**, `BKL-8N5K` (MG6 restructure pre-pass)
**shipped**, `BKL-4W7H` **promoted** (in flight), `BKL-6M4T` and `BKL-0QR1` **open**.

| id | work | blocked by |
|---|---|---|
| C1 | SPIKE-S2 live dry-run on a throwaway repo (step 0) | A1 |
| C2 | MG4 scrub workflow — model-surfaced candidates → owner-confirmed dispositions | — |
| C3 | `BKL-4W7H` (PFX read-resolution + alias idempotency) — must-fix-before-done | — |
| C4 | The real prawduct migration (bulk import) | A1, C1, C2, C3 |
| C5 | Briefing/gates repoint through the adapter | C4 |
| C6 | **MG5** — drop-box retirement + `report-bug` files upstream, carrying `Found in: prawduct vX.Y.Z` from `prawduct-hook version` (provenance, not model recall) | **B1**, C5 |
| C7 | `BKL-6X5D` part (b) — Pacer meters REST points for the create+close stretch | **only if A1 = `all`** |

`lib/backlog/legacy.py` is **not** retired here — it stays as the shared markdown read path for
un-migrated portfolio repos (MG3/GV7).

### D — Verification

| id | item | when |
|---|---|---|
| D1 | **VRF-005** (Chunk 02 live two-axis status), **VRF-007** (`/prawduct:backlog` end-to-end), **VRF-008** (dormancy) | **Now** — `samsung-frame-art-loader` is cut over and `--plugin-dir` is a proven path |
| D2 | **VRF-006** — the prawduct migration itself | Is C4's acceptance evidence |
| D3 | **VRF-002**, **VRF-003** | **Post-release by construction.** VRF-002 states it: *"they can't be exercised pre-release"* — the plugin loads from cache, so a new agent type and hook are not live until the version ships. Run immediately after promotion with a rollback plan; do not hold the release for them. |

### E — Release mechanics

1. Merge **PR #134** (`skills-cutover-awareness`) — expect a change-log conflict with the merged #135.
2. Bump `VERSION` + `.claude-plugin/plugin.json` (A2).
3. Flip **every** unreleased change-log entry to `status=shipped` + add `release=vX.Y.Z`. v2.0.14
   shipped 8 of 10 entries by skipping this (`REL-2N8K`) — enumerate, don't sample.
4. `prawduct-hook regen-views --check` (fail-closed pre-flight) → then for real.
5. Tag, push, confirm the version-delta banner.

### F — Accepted risks / explicitly not blockers

- The `backlog-service-migration-required` advisory resolves *as a consequence* of C4 — it is not
  separate work.
- The full XP1 cross-owner / foreign-identity / private-target plane stays **W3**. MG5 ships only the
  fixed-target public-repo subset. Do not let B1's discovery pull W3 forward.
- `BKL-6X5D` window *quantification* stays deferred (adopter-scale); only part (b) is in scope, and
  only under A1 = `all`.

## Burn-down order

The critical path is **B1 → C6 → release**, and B1b is the only genuinely unknown-duration item.
Everything else parallelizes around it.

1. **Now, in parallel with everything:** A1 + A2 (owner, minutes). D1 (three live verifications
   against samsung — unblocked today, and they de-risk C4 by exercising the adapter end-to-end
   before a real migration depends on it). E1 (merge #134).
2. **Start immediately, longest pole:** B1 discovery spike. B1b first — if the evidence/PII answer is
   hard, everything downstream slips and it is better to know in week one.
3. **Parallel to B1:** C1, C2, C3 — none depend on the consent policy. C1's dry-run also settles the
   real pacing constants the NFR §9 S2 obligation now demands (measured with `--archive-scope all`,
   volume lever disabled, so the run proves pacing rather than a small input).
4. **After B1 lands:** C4 → C5 → C6, in order. C7 only if A1 = `all`.
5. **Then:** E2–E5, then D3 post-promotion.

**Sequencing rule worth stating once:** do **not** retire the drop-box before MG5's replacement is
live and B1's policy binds at the adapter. `BKL-0QR1` already resolved retirement to lockstep; B1
adds the second condition. A gate recorded only on the gating item is how a gate gets walked past,
which is why `BKL-0QR1` now carries a `GATED by BKL-9XQ2` backlink.
