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

# Release Plan — v3.2.0, Backlog Service Go-Live

**Owner decisions (2026-07-20):** wide release — *"We can't ship a partial product. And if prawduct's
own backlog migrates to gh issues, we have to bring in all that implies."* Version: **v3.2.0**
(A2 decided).

This plan enumerates what blocks that release and the order to clear it. It is a **release plan**,
not a build plan — Chunk 06's build spec already lives in `build-plan-backlog-service.md` and is not
restated here.

## ⚠️ First: the code lives on `feature/backlog-service-relayout`, not `develop`

> **SUPERSEDED 2026-07-24 — the relayout branch has since landed.** `feature/backlog-service-relayout`
> merged to develop via **PR #137 (2026-07-23)**; develop now carries the backlog-service code (its
> `plugin/lib/backlog` tree is byte-identical to relayout's, `e25f555`). The subsequent upstream-filing
> design also landed (PRs #138/#139). The instruction below describes the *pre*-#137 state — do v3.2.0
> work on **develop** (or a feature branch off it), not by "landing the relayout branch." Retained for
> history. Current branch state: `build-plan-v3.2.0-golive.md` § Prerequisites.

**Read this before running any command in this plan.** On 2026-07-21 the v3.1.1 hotfix set
`develop`'s tree to `v3.1.0` + an allowlist, deliberately withholding every backlog-service path.
All of it — `plugin/lib/backlog/**`, `plugin/skills/backlog/**`, `plugin/lib/backlog_probes.py`, the
`documentation/backlog-service-*` set, `tests/test_backlog_*`, `tests/fakes/`, `tests/fixtures/`,
`tests/spikes/` — was first stranded on **`feature/backlog-service`** at commit **`7fc00e1`** (`R`),
then **restored and relaid-out under `plugin/`** on **`feature/backlog-service-relayout`**, which is
where v3.2.0 work resumes and which heads for `develop`. Nothing was lost and no history was rewritten.

**Resuming means landing `feature/backlog-service-relayout` onto `develop`** — the substantial
conflict resolution has already been done on that branch (the restoration plus the `plugin/`
relayout), so what remains is a normal feature-branch merge. Do v3.2.0 work on top of
`feature/backlog-service-relayout` (or on `develop` once it lands), not on a fresh branch off the
pre-relayout `develop`.

**Path names in this plan describe the `feature/backlog-service-relayout` tree** (everything under
`plugin/`), not the pre-relayout root paths. Where the branch and `main` differ — most visibly
`plugin/lib/backlog/legacy.py` (a package on the branch) vs `plugin/lib/backlog.py` (the single
module v3.1.1 shipped) — the branch form is the one this plan means.

Recorded here rather than only in `release-plan-v3.1.1-hotfix.md` because that plan expires with its
release, and this is the document someone opens six weeks from now. (Critic finding, 2026-07-21: the
only pointer to where the migration went lived in the expiring plan.)

## Ship list — what must land before v3.2.0

The checkable form. Detail and rationale for each line are in the sections below; this list is the
thing to iterate on and check off. **Blocked-by is the load-bearing column** — the plan's whole shape
is that one discovery spike gates the end of the chain while everything else runs beside it.

| # | must land | blocked by | state |
|---|---|---|---|
| 1 | `--archive-scope` decision for prawduct's own migration (A1) | — | ☑ **decided 2026-07-20: `all`** |
| 2 | Merge PR #134 (`skills-cutover-awareness`) — change-log conflict expected | — | ☑ **merged 2026-07-20** (`43dda9c`) |
| 3 | VRF-005 · VRF-007 · VRF-008 drained against `samsung-frame-art-loader` | — | ☐ unblocked today |
| 4 | **`BKL-9XQ2` discovery spike** — consent (1a/1b), evidence+PII, label taxonomy | — | ☐ **critical path** |
| 5 | SPIKE-S2 live dry-run on a throwaway repo (C1) | ~~1~~ (met) | ☐ run it with `--archive-scope all` |
| 6 | MG4 scrub workflow (C2) | — | ☐ |
| 7 | `BKL-4W7H` — PFX read-resolution + alias idempotency (C3) | — | ☐ in flight (`promoted`) |
| 8 | `BKL-6X5D` part (b) — Pacer meters REST points (C7) | — | ☐ **blocker** (A1 = `all` promoted it; no longer conditional) |
| 9 | The real prawduct migration (C4) | ~~1~~ (met), 5, 6, 7, **8** | ☐ *(8-before-9 is **decision 6 — ratified 2026-07-23: accept**; C7 lands before C4 so the archive leg runs fully metered on the real repo)* |
| 10 | Briefing/gates repoint through the adapter (C5) | 9 | ☐ |
| 11 | **MG5** — drop-box retirement + `report-bug` upstream filing (C6) | **4**, 10 | ☐ |
| 12 | VRF-006 — the migration is its own acceptance evidence | 9 | ☐ |
| 13 | Version bump `VERSION` + `plugin.json` → 3.2.0 | 1–12 | ☐ release trigger |
| 14 | Change-log: flip **every** unreleased entry `status=shipped` + `release=v3.2.0` | 13 | ☐ enumerate, don't sample |
| 15 | `regen-views --check` → `regen-views` | 14 | ☐ fail-closed pre-flight |
| 16 | Tag `v3.2.0`, push, confirm the version-delta banner | 15 | ☐ |
| 17 | VRF-002 · VRF-003 | promotion | ☐ **post-release by construction** |
| 18 | `BKL-2Q7F` — the scrub runbook never selects/creates/provisions the target repo | — | ☐ **blocker** |
| 19 | `BKL-8V3D` — `adapter-mode.md:96` promises an `--apply`/dry-run contract that does not exist | — | ☐ **blocker** |
| 20 | `BKL-5N9W` — narrow the wildcard `Bash(prawduct-hook backlog *)` grant to the ops the skill drives | — | ☐ **blocker** |
| 21 | `BKL-6J2X` — hold the migration-required advisory until the path is proven | 18, 19, 20 | ☐ **blocker** |

Nothing above is optional-by-default: item 8 **was** conditional on A1 and is now firm, and item 17
is deliberately *after* the tag. Everything else lands before v3.2.0 ships.

**Items 18–21 were found on 2026-07-20 while scoping the v3.1.1 hotfix** (`release-plan-v3.1.1-hotfix.md`),
and they are why that release ships from `v3.1.0`'s tree rather than from `develop`. Together they
form one chain, which is the reason they gate rather than merely annoy: the `warn` advisory fires for
**every** un-migrated repo and routes to `/prawduct:backlog scrub`; `skills/backlog/SKILL.md` is
`disable-model-invocation: false` with a wildcard adapter grant; the runbook it reaches never binds
`--repo`; and the one safety property the instructions cite — a dry-run — **does not exist in
`plugin/lib/backlog/`**. An agent can walk that path unprompted and write 100–250 real issues into a real
repo, believing a dry-run guarded it. `BKL-8V3D` is the same defect class as the `--archive-scope
open` backup claim (prose asserting a safety property the code does not implement); a guard test
pinning instruction-surface flag claims to flags the CLI actually parses would close the class rather
than the instance.

**A1 resolved 2026-07-20 — `all`** (recorded with rationale in
`artifacts/migration-scrub-decisions.md` decision 5). What it settles beyond item 8: **item 5 is now
unblocked** and measures the path prawduct actually takes. Item 9 is *not* unblocked — clearing A1
satisfied only one of its blockers and **added** item 8, so it now waits on 5, 6, 7 and 8.
The deciding argument was not archive completeness but **default-path coverage**: `all` is the
flag's default, so `open` for the dogfood would have shipped the default unexercised by the only
migration prawduct runs itself. A secondary find during the decision — `open`'s documented
preservation story was false at **ten claim sites across seven files**, naming the MG2 export, which
dumps the migrated repo post-import — is fixed on `fix/archive-scope-preservation-claim`; the residual product gap
(`open` puts the skipped archive outside post-cutover `list` and add-time dedup) is **`BKL-4Z7M`**,
adopter-facing and not release-gating now that prawduct takes `all`.

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
`plugin/lib/backlog/ids.py`. MG5 is the change that *instructs* it.

## Sizing (snapshot, not a fact)

prawduct's own backlog at `964d03b` on `develop`: **108 open · 2 promoted · 144 archive**, no
separate archive file, across **29 distinct PFX prefixes** (`ADR ADV BKL BLD BRF COV
CRT DOC ENV GOV JAN JNT LRN MET MIG PR PRR REL SCN SEC STH STN SYN TEL TPL TST VWS WMK WT`).

**Treat every count here as a dated snapshot, never as a constant.** On 2026-07-20 four discodon
checkouts reported 384 / 389 / 349 / 319 open and the canonical one moved between two reads twenty
minutes apart — a live instance of the stale-views pain this project exists to kill. A count is
re-derived at the moment it is used, or it is not used. The 29 prefixes are the more durable datum:
they are the multi-prefix absorption stress the dogfood was chosen to provide.

*(A worked example of getting this wrong, left in deliberately. On 2026-07-20 this line was
"corrected" from 144 to **143** and a parenthetical was added explaining the delta as same-day drift.
Both halves were false, and two independent reviewers caught it: `## Archive` is byte-identical
between `f8b38f7` and `964d03b`, so nothing drifted — the re-derivation used an id pattern
(`PFX-XXXX`) narrower than the data, silently dropping `MIG-M4-REMOVE`, the one archive item whose id
has three segments. The lesson is not "recount more carefully": **a re-derived number that disagrees
with a recorded one is evidence the new derivation is wrong, and calls for reconciling the two, never
for narrating the gap.** Writing the drift story was the actual failure; the arithmetic was
downstream of it.)*

## Blockers

### A — Owner decisions (cheap, unblock everything downstream, do first)

| id | decision | why it gates |
|---|---|---|
| **A1** | ~~`--archive-scope` for prawduct's own migration~~ — **decided 2026-07-20: `all`** | Resolved. It determined whether `BKL-6X5D` part (b) is a release blocker; `all` **promotes it in** (item 8). The archive leg is one paced create plus one **unpaced** close per item, the half-metered stretch part (b) exists to close. Rationale and the code that backs it: `artifacts/migration-scrub-decisions.md` decision 5. |
| **A2** | ~~Release version~~ — **decided 2026-07-20: v3.2.0** | The bump *is* the release trigger (`VERSION` + `plugin.json`). A minor bump for a subsystem going live, consistent with the standing "version conservatively" preference. |
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
| C1 | SPIKE-S2 live dry-run on a throwaway repo (step 0) | ~~A1~~ (met — run it with `--archive-scope all`) |
| C2 | MG4 scrub workflow — model-surfaced candidates → owner-confirmed dispositions | — |
| C3 | `BKL-4W7H` (PFX read-resolution + alias idempotency) — must-fix-before-done | — |
| C4 | The real prawduct migration (bulk import) | ~~A1~~ (met), C1, C2, C3, **C7** *(decision 6 — **ratified 2026-07-23: C7 before C4**)* |
| C5 | Briefing/gates repoint through the adapter | C4 |
| C6 | **MG5** — drop-box retirement + `report-bug` files upstream, carrying `Found in: prawduct vX.Y.Z` from `prawduct-hook version` (provenance, not model recall) | **B1**, C5 |
| C7 | `BKL-6X5D` part (b) — Pacer meters REST points for the create+close stretch | — (in scope: A1 = `all`) |

`plugin/lib/backlog/legacy.py` (`plugin/lib/backlog.py` on `main` at v3.1.1 — the package split
lives on `feature/backlog-service-relayout`) is **not** retired here — it stays as the shared markdown read path for
un-migrated portfolio repos (MG3/GV7).

### D — Verification

| id | item | when |
|---|---|---|
| D1 | **VRF-005** (Chunk 02 live two-axis status), **VRF-007** (`/prawduct:backlog` end-to-end), **VRF-008** (dormancy) | **Now** — `samsung-frame-art-loader` is cut over and `--plugin-dir` is a proven path |
| D2 | **VRF-006** — the prawduct migration itself | Is C4's acceptance evidence |
| D3 | **VRF-002**, **VRF-003** | **Post-release by construction.** VRF-002 states it: *"they can't be exercised pre-release"* — the plugin loads from cache, so a new agent type and hook are not live until the version ships. Run immediately after promotion with a rollback plan; do not hold the release for them. |

### E — Release mechanics

1. ~~Merge **PR #134**~~ — **done 2026-07-20** (`43dda9c`). The predicted conflict landed in both
   `change-log.md` and `backlog.md`, and was purely additive in each (both sides prepended entries at
   the head; neither modified the other's). Resolved by keeping both sides and verifying the result
   was the exact set union — the check worth repeating on the next such merge, since "kept both" is
   itself a coverage claim.
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
  now firmly in scope because A1 landed on `all`.

## Burn-down order

The critical path is **B1 → C6 → release**, and B1b is the only genuinely unknown-duration item.
Everything else parallelizes around it.

1. **Done — A1 + A2 both decided 2026-07-20** (`all`; v3.2.0); **E1 done** — PR #134 merged (`43dda9c`),
   its predicted change-log conflict resolved as additive bookkeeping. Still now, in parallel: D1 (three live verifications
   against samsung — unblocked today, and they de-risk C4 by exercising the adapter end-to-end
   before a real migration depends on it).
2. **Start immediately, longest pole:** B1 discovery spike. B1b first — if the evidence/PII answer is
   hard, everything downstream slips and it is better to know in week one.
3. **Parallel to B1:** C1, C2, C3 — none depend on the consent policy. C1's dry-run also settles the
   real pacing constants the NFR §9 S2 obligation now demands (measured with `--archive-scope all`,
   volume lever disabled, so the run proves pacing rather than a small input).
4. **After B1 lands:** C4 → C5 → C6, in order. C7 is in scope (A1 = `all`) and does not wait on B1.
   **Decision 6 — ratified 2026-07-23** (owner: *"whatever is more efficient; we won't ship
   incomplete"*): land **C7 before C4**. Both are blockers regardless, so wall-clock is identical
   either way — the only lever is ordering, and C7-first is strictly safer at equal cost: the real
   migration's archive leg (one paced create + one *unpaced* close per item) then runs fully metered
   instead of proving the rate-limit gap on prawduct's own public repo, where a throttled/half-done
   archive is not cleanly reversible (MG1 — GitHub has no issue-delete, numbers never reused). The
   "beside" alternative was declined: it buys no parallelism here (same builder does both) and only
   earns the freedom to run the real migration without the safeguard C7 exists to provide.
5. **Then:** E2–E5, then D3 post-promotion.

**Sequencing rule worth stating once:** do **not** retire the drop-box before MG5's replacement is
live and B1's policy binds at the adapter. `BKL-0QR1` already resolved retirement to lockstep; B1
adds the second condition. A gate recorded only on the gating item is how a gate gets walked past,
which is why `BKL-0QR1` now carries a `GATED by BKL-9XQ2` backlink.
