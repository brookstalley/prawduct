# Migration scrub — owner decisions (recorded 2026-07-18; decisions 5–6 added 2026-07-20)

Owner checkpoint held at the end of the 2026-07-18 session (BKL-8N5K shipped, Critic clean).
**The live migration itself is HELD** — owner decision, not a blocker. Everything below is
**confirmed** and carries forward to the owner-run migration session (BKL-6M4T), which should
execute against these decisions without re-asking, re-confirming only if the source has drifted.

**Exception — decision 6 is NOT owner-confirmed.** It is builder-proposed and marked sign-off owed.
The "execute without re-asking" rule above covers decisions 1–5 only; 6 must be put to the owner
before it is acted on.

> ## ⚠ THE SOURCE HAS DRIFTED — do not execute the dispositions below without re-surveying first
>
> Checked 2026-07-31. The "re-confirming only if the source has drifted" condition above **has
> fired.** Do not read this section's approved dispositions as a current plan.
>
> **What still holds.** As at the last check, *every* recorded disposition below survived: each
> merge pair still resolved, and no drop had become a no-op through its target being disposed some
> other way. Some merge survivors have since moved `open → promoted` — that is **in-flight, not
> gone**, and folding a duplicate into in-flight work is exactly as sound, so it is not a reason to
> re-open those decisions. Re-check rather than trust this paragraph: it describes a past run.
>
> **What does not.** The open corpus has grown substantially since the snapshot these were derived
> against, and every item filed since is **outside every disposition here — never surveyed for
> staleness or duplication at all.** The per-item survey behind the decisions (gists, DUP clusters,
> staleness evidence) covers the smaller corpus only. That coverage gap, not a wrong plan, is what
> makes this section unsafe to execute as written.
>
> **The survey that closes this gap EXISTS and is CONFIRMED — see § "Survey 2" below (owner ruling
> 2026-07-31).** Every open item filed since the snapshot was read in full and dispositioned; the
> approved status flips, merges and drop were applied to the markdown source. **So the coverage gap this
> block was raised for is closed.** What this block still binds is the *pre-existing* dispositions above:
> they were derived against the smaller corpus and are unchanged. Read § Survey 2 for the current state
> before executing anything, and note that `verdict: CURRENT` will still not print until `SNAPSHOT` is
> advanced — see the last subsection of § Survey 2 for why that is a property of the instrument, not a
> sign the survey is incomplete.
>
> **This block states shapes, never counts — every count here would move with the next filing, and
> a stale one reads as current.** For any number at all, run the instrument:
>
>     python3 tests/spikes/backlog_scrub_drift.py
>
> It re-derives the drift, re-checks every merge and drop recorded below against today's backlog,
> and lists the unsurveyed items by id. It prints `verdict: dispositions are CURRENT` only when the
> recorded set covers the whole open corpus — which is the actual precondition for the migration
> session, and the thing this artifact previously asked a reader to eyeball.

## Decisions

1. **Live run: HELD** (2026-07-18). Target when it runs: `brookstalley/prawduct` (public — the
   owner has NOT yet given the explicit public-visibility yes; re-confirm sign-off at the top of
   the migration session).
2. **Restructure scope: open survivors only.** The ~78 keep-items get the issue-standard
   restructure (title + template body + `kind:` backfill via a v1 plan, `import --restructure`);
   the 121 archive items import verbatim. Note: zero source items carry `kind:` today.
3. **Dispositions: all 18 approved** (apply after import — import-then-dispose; nothing
   hard-deleted).
4. **MIG-M4-REMOVE: import as-is** (content-digest idempotency key, no alias; `get` won't
   resolve it — accepted for shipped history).

   **Consequences superseded 2026-07-28 (v3.2.0 Chunk 05c / BKL-72AS); the decision itself stands.**
   "Import as-is, do not rename" is unchanged — and is now the *cheaper* option rather than the
   accepted-cost one. What no longer holds is the parenthetical: the id-shape regexes only ever
   accepted a single hyphen, which is why this item could not carry an alias. They now accept
   multi-segment ids, so `MIG-M4-REMOVE` imports **with** a permanent `id:MIG-M4-REMOVE` alias,
   keyed on that alias rather than a content digest, and `get` **does** resolve it.

   *Why this had to change rather than stay accepted:* commit `7565787` (07-28) made an unaliasable
   item an exit-4 conflict in `verify-migration`. Under the original consequences this decision and
   that gate could not both be satisfied — the decision said "import it with no alias," the gate said
   "no alias, stop." Widening the shape was the only remedy that did not require unwinding this
   decision or decision 5. Verified live: the source now parses with zero unaliasable items.
5. **`--archive-scope`: `all`** (owner, **2026-07-20** — release-plan decision A1). The full
   archive imports as closed issues.

   *Why this is dated 07-20 and not 07-18:* the lever did not exist on 07-18. This artifact was
   written at `03cbcf7` (07-17 22:24) and last touched at `7b6a5a6` (07-17 22:59); `--archive-scope`
   shipped at `7cbdf08` (07-18 14:27), sixteen hours later. Decision 2's phrase "the 121 archive
   items import verbatim" is about **restructure** scope — whether migrated items get rewritten —
   and was never an archive-scope choice. `skills/backlog/migration-scrub.md` had back-attributed
   an `all` decision to this file; that citation now points here, where the decision genuinely is.

   **Rationale (verified in code, not recalled):**
   - `all` is the flag's **default** (`cli.py` `_archive_scope_flag`). Choosing `open` for the
     dogfood would ship the default path unexercised by the one migration prawduct runs itself.
   - `open`'s preservation story was mis-stated at ten claim sites across seven files (it named the MG2 export,
     which dumps the migrated repo post-import and cannot hold what the lever excluded). Corrected
     on this branch. The true cost of `open` — skipped items are git history, not live
     backlog, because the skill stops reading the source file after cutover — is a real loss of
     the whole archive as precedent and dedup surface (144 items at `964d03b`; re-derive at use).
   - Owner framing for the release: *"We can't ship a partial product."*

   **Consequence, accepted at decision time:** `all` makes **`BKL-6X5D` part (b)** (pace the
   status/close writes) a **v3.2.0 release blocker** — item 8 on the ship list, previously
   conditional. An archived item costs a paced create plus an **unpaced** close
   (`_reconcile_status` → `core.set_status`, no pacer), so the archive leg of the real migration
   is exactly the half-metered stretch part (b) describes.
6. **Part (b) lands *before* the bulk import, not beside it** (2026-07-20 — **builder-proposed,
   owner sign-off owed**; flagged by Critic review as a plan decision that does not follow
   mechanically from A1 and so must not ride in on its authority).

   A1 makes part (b) a release blocker; it does **not** by itself dictate the order. C4's blockers
   went from `A1, C1, C2, C3` to `C1, C2, C3, C7`, which is a separate call. The alternative,
   stated plainly so it is vetoable: **run the migration first with the close leg unpaced**, and
   land part (b) afterwards — cheaper to sequence, and the run would probably survive, since today
   the close leg is throttled only incidentally by subprocess latency.

   Recommendation: **land part (b) first.** The bulk import is irreversible (GitHub never reuses
   issue numbers, so there is no rollback — only re-run into the same repo), which makes it the one
   run that should not double as part (b)'s proof case. A secondary-rate-limit trip mid-import is
   recoverable but costly, and the SPIKE-S2 dry-run (C1) cannot substitute: it measures a throwaway
   repo, not prawduct's 144-item archive leg.

   Owner may overrule; if so, C4's blocked-by drops C7 and the release plan's burn-down step 4
   reverts to running them in parallel.

## Approved dispositions (owner-confirmed 2026-07-18)

Merges (fold duplicate → survivor via `merge`, redirect-before-close):

| Duplicate | Survivor | Reason |
|---|---|---|
| BKL-7M4Q | BKL-5D2C | superseded by the adapter's crash-safe CC1 mutation design |
| BKL-8T3W | BKL-5D2C | becomes GV3 reconciliation in the backlog service |
| CRT-6J4P | CRT-8H3R | same mode-inference ancestor-guard fix; bodies cross-reference |
| WMK-4Q9T | GOV-4C7X | owner-decided deletion; the kernel program carries it |
| STH-4D2X | STH-5D8J | same trivial-gate surface; 5D8J's patch-vs-retire decision moots it |

Drops (`status … dropped` after import; bodies preserved):

| Item | Reason |
|---|---|
| MIG-6B0R | file-sync-era strip list; premise self-obsoleted |
| TST-4P8H | 5/6 named tests deleted with the file-sync engine; no active flakes |
| CRT-9V4T | superseded by CRT-3X9D structural no-execution binding |
| ADR-7X2M | RFC targets removed pre-2.0 layout; self-flagged needs-rework (re-file fresh if wanted) |
| REL-5K8M | inert since reviewer tiering was removed (v3.0.1) |
| STH-4B7Q | no repro; operator-verification surface reworked in v2.0.0 |
| CRT-6T1V | discodon-sourced Apr 2026, no movement |
| CRT-1B6Q | discodon-sourced Apr 2026, no movement |
| CRT-5N3F | discodon-sourced Feb–Apr 2026, no movement |
| STH-7B5N | Apr 2026, no movement |
| CRT-8D2W | premise half-obsoleted (build plans now tracked; worktree flow exists) |
| WMK-1P4Q | mooted by the kernel program's index-machinery deletion |
| WMK-7D3R | mooted by the kernel program's index-machinery deletion |

Everything else (~78 open + 121 archive): **keep** (LRN-3F8K explicitly kept — its dangling-sentinel
error is live and small).

## Survey 2 — the unsurveyed set (proposed and **OWNER-CONFIRMED 2026-07-31**, one row held)

Closes the coverage gap the ⚠ block above names. Every open item filed since `964d03b` was read in
full through `lib.backlog.legacy.parse_backlog` and screened for staleness and duplication (MG4/G1 —
the model proposed, the owner decided, the data plane applied a confirmed set).

> ### ✅ OWNER RULING — 2026-07-31
>
> - **§ A — all seven status flips APPROVED** and applied to the markdown source.
> - **§ B — two of three merges APPROVED**: `BKL-6J2X → BKL-7D3V` and `BKL-4M6T → GOV-2K7R`.
>   **`BLD-5R7K → SCN-6V3D` is HELD** — see the row for why.
> - **§ C — `COV-3M8Q` APPROVED as a drop**, against the recommendation to keep. The ratified goal it
>   served (review wall-clock is P0) stays tracked by `CRT-8N5V` and `CRT-3W6P`; the goal is not
>   dropped with the item.
> - **§ D — the 80 keeps stand.**
>
> These were applied **pre-migration, to the markdown source** — not as post-import dispositions. That
> is a deliberate departure from decision 3's "apply after import" and it is the cheaper order for this
> class: a corrected source migrates once, correctly, instead of migrating wrong and being repaired
> across ~10 extra writes. Decision 3's ordering still governs the original 18 dispositions, which are
> genuine scrub actions on items that must exist as issues before they can be closed or folded.

**On counts in this section.** The ⚠ block forbids corpus counts because they drift. The counts below
are **not** corpus counts — they describe a *fixed decision set* taken at merge commit `a232407`
(91 items). They do not move with the next filing. The live corpus figures stay where they belong:
in the instrument.

**Staleness could not fire on this set, and that is a finding.** Every unsurveyed item was filed
between 2026-07-19 and 2026-07-31 — none is older than twelve days, so the "unmoved for a long time"
criterion has no purchase. The two axes that *can* fire are **superseded-by-shipped-work** and
**duplicate/shared-root**. Screened on those, the corpus is unusually clean: **zero drops on staleness
grounds.** These are overwhelmingly Critic-sourced findings against live machinery, each carrying its
own verification and, very often, its own explicit dedup ruling. A survey that manufactured drops here
would be discarding live defects.

### A. Status reconciliation — 7 items whose work SHIPPED and whose flip never ran

**This is the highest-value output of the survey, and it is not a keep/drop/merge call.** These items
are `status: open` only because v3.2.0 adopted a `[ ]`-until-release convention and deferred the
`status=shipped` flip to Chunk 09. The plan says so in its own words (§ "Where v3.2.0's state lives"):
*"BKL-2Q7F, BKL-8V3D, BKL-5N9W, BKL-6J2X, BKL-6X5D(b) and ONB-3F9P all read `status: open` while their
work is built… That is intended, not drift."* **v3.2.0, v3.2.1 and v3.2.2 have all shipped and the
reconciliation never ran.** Migrating today mints seven GitHub issues describing finished work — and
`GOV-3D6X` predicted exactly this ("Chunk 09's list does not currently *contain* these flips, so
following the plan literally at release would leave them behind").

Each was verified **against the tree**, not read off its own annotation:

| Item | Verification performed | Proposed |
|---|---|---|
| **BKL-2Q7F** | `migration-scrub.md` Step 0 (target selection + owner confirm + `provision`) present; all seven `--repo` occurrences carry `<target>` | `shipped` |
| **BKL-5N9W** | `skills/backlog/SKILL.md` grants 12 everyday ops explicitly; `import`/`merge`/`provision`/`reconcile-labels` absent, with the rationale stated in-file | `shipped` |
| **BKL-8V3D** | `adapter-mode.md` now reads "No generic preview-or-apply flag sits over those mutations"; `tests/test_backlog_instruction_surface.py` exists | `shipped` |
| **BKL-72AS** | Run live through the production parser: `MIG-M4-REMOVE` parses, `is_pfx` → True, **0 unaliasable items** in the whole corpus | `shipped` |
| **BKL-8K2N** | `migrate.pacing_summary` rides every import exit path; the `≥` floor marker and its "drop only when BKL-3H7W lands" rationale are in `cli.py` | `shipped` |
| **ONB-3F9P** | All three legs built — `init-product --backlog-repo`, onboard's `provision` step **and** grant, doctor's `reconcile-labels` grant + Health Check #12. **Its own "[partially built]" status pointer is stale** | `shipped` |
| **BKL-3N8Q** | Both halves closed — `pick` blocker-honesty in `query.py`, foreign-API shapes verified live by **VRF-010 (`verified`, 2026-07-28)** | `shipped` |

**D4 applies: the `status=shipped` call stays explicit and owner-made — never inferred from an audit.**
That is why these are proposed rather than flipped.

### B. Merges — 3, all where one fix closes both

| Duplicate | Survivor | Reason |
|---|---|---|
| BKL-6J2X | **BKL-7D3V** | Two records of one advisory decision. BKL-6J2X asked that the hold be *"recorded as a release-plan decision"*; BKL-7D3V **is** that record ("the deliverable above is therefore satisfied"). Both residuals are the same single implementation — Chunk 07 done-when #5 (register the real probe, delete the held no-op, flip the pinning test, correct two docstrings). Chunk 07 never ran, so the survivor stays open carrying it |
| BKL-4M6T | **GOV-2K7R** | Same defect twice: a security-adjacent grant narrowing shipped unpinned while its sibling in the same fix got a test. GOV-2K7R names BKL-4M6T as "the same shape" and asks for the **class** fix — extend the skill-metadata test family so no skill frontmatter carries a bare wildcard. One test family closes both |
| ~~BLD-5R7K~~ | ~~**SCN-6V3D**~~ | **HELD — owner, 2026-07-31. Not applied; both items stay open and untouched.** The technical case stands: same function (`resolve_chunk_progress`), same silent degradation to the known-wrong checkbox reading, same discarded `ChunkProgress.git_derived` signal, overlapping candidate surfaces. What held it is that BLD-5R7K carries a genuinely **separable** second leg — documenting the commit-convention precondition in the build-plan template and `building.md` — which a fold into SCN-6V3D (`ready`, scoped to "pick the surface that reports") could lose. Re-propose only with that leg either carried explicitly into the survivor or split into its own item first |

**Near-matches deliberately NOT merged.** The corpus has already adjudicated these and recorded the
reasoning; re-merging would re-litigate settled calls: `CRT-9K2P`/`CRT-2X7R`/`CRT-7P5J` (one root — a
single-latest-fact view standing in for the store — on three surfaces; fixing any one leaves the other
two standing), `CRT-3F7T`+`CRT-9K2P` ("work them together"), `CRT-4X2N` vs `CRT-6R3W` (instance sweep vs
rule sweep — "must not be deduped"), `BLD-ZQ2V` vs `BLD-5R7K` ("do not merge" — different question, not
different quality of answer), `CRT-8Q6R` vs `CRT-3F7M`, `LRN-8P3W`+`LRN-3F8K` and `GOV-5N8R`+`CRT-6R3W`
(class/instance pairs). **Schedule together, do not fold.**

One of those rulings is now vindicated: `BKL-6T3P` declined to fold into `BKL-8V3D` precisely because
BKL-8V3D looked closable and folding a live defect into it would have made it un-archivable for an
unrelated reason. Section A proposes exactly that closure. BKL-6T3P correctly carries the residual.

### C. Drop — 1, approved against the recommendation

| Item | Reason | Proposed |
|---|---|---|
| **COV-3M8Q** | Both of its named routes are now closed. The content-equivalence route was **RULED OUT 2026-07-29** (built, reviewed at 10 blocking with all three reviewers finding the same hole, reverted); the route it then pointed at — record-mechanization Chunk 03, per-mode reviewer payload — **shipped in v3.2.2**. What remains is the bare observation with no live route. **Counter-argument, stated so the drop is not taken cheaply:** the treadmill itself is unfixed (`is_judgeable_path` still classifies by extension, so a docstring-only `.py` edit still demands a full cycle) and the governing goal is ratified. Other items hold that line — `CRT-8N5V`, `CRT-3W6P` | **`dropped` — owner, 2026-07-31.** The counter-argument was put and not taken; recorded here so the drop reads as a decision made against a stated case, not a case nobody made |

### D. Keep — the remaining 80

Everything not named above. No staleness signal and no duplication signal survived screening. Rather
than restate 80 near-identical reasons, the grounds are: each is a recent, independently-verified defect
against live machinery, most carrying explicit dedup rulings from prior sessions.

Two keeps worth flagging because new evidence has arrived since filing, without changing the
disposition:

- **CRT-8Q6R** (the hardcoded 4-minute cache-warm interval, sized against an *assumed* 5-minute prompt
  cache TTL). The item's own first candidate fix is *"drop it entirely if the harness already handles
  cache retention"*. Evidence unavailable at filing: sessions now run under a documented **1-hour**
  prompt-cache TTL, which is precisely the case the item names as wasteful — "it burns readouts to
  defend a cache that was never at risk." **Keep, but the constant is now demonstrably mis-sized**; the
  requirement (a waiting session must not idle silently) is what survives, not the number. Note the
  cadence is pinned by two tests, so re-scoping costs two edits.
- **GOV-7W3D** (6 of 10 `## Direction` norms undispositioned). Its deadline was *"before Chunk 06 runs"*
  and v3.2.0 shipped without Chunk 06, so the trigger has been overtaken rather than met. The plan file
  is retained (Chunks 06/07 unbuilt), so the item is live — but its bound needs restating.

### What this section changes about running the scrub

The instrument's verdict **cannot** flip to `CURRENT` by recording dispositions. `backlog_scrub_drift.py`
derives "unsurveyed" as *open items filed since `SNAPSHOT = "964d03b"`*, so on a growing corpus that set
is non-empty forever. **Advancing `SNAPSHOT` to the commit this survey was taken at (`a232407`) is the
step that closes the loop** — and neither the spike's docstring nor this artifact said so. Advance it
only once these dispositions are confirmed; advancing it first would silently declare an unreviewed
corpus surveyed.

## Migration-session runbook pointer

`skills/backlog/migration-scrub.md` (steps 0–4, incl. 2b restructure pre-pass). Sequence:
re-confirm sign-off → author the v1 restructure plan for the keep set → `restructure-preview` →
owner batch approval → `import --restructure` (git history of the source is the pre-import
backup) → `export` backup **after** the import (it dumps the migrated repo — running it before
backs up nothing; ordering corrected 2026-07-18 per the holistic review) → apply the merges/drops
above (all disposition commands take `--repo`) → verify counts + spot-check → activate the
BKL-8P2R cutover (`backlog_service_repo: owner/repo` in project-state.yaml — the repoint code
shipped 2026-07-18) → **do NOT retire `legacy.py`** (GV7/MG3 — it is the shared markdown read path
and retires only at portfolio-wide migration; retiring it here also disables the next repo's
migration, which reads through `legacy.parse_backlog`) → retire `incoming-bugs/` in lockstep with the report-bug MG5
repoint → `/prawduct:critic cumulative` → slice PR. The full item survey (per-item gists, DUP
clusters, staleness evidence) was produced 2026-07-18; regenerate it if the source drifts
materially before the run.

**Pre-run gate added 2026-07-18 (holistic Fable review):** the run is BLOCKED until the two
transport/pagination defects are fixed and live-verified read-only against the real repo (>30
labels, 127+ PRs): (1) `--paginate` multi-document JSON parsing in `list_labels`/`list_timeline`/
`list_sub_issues`; (2) client-side PR filtering breaking the `len(batch) < per_page` pagination
terminators in `_all_issues`/`iter_alias_issues`/`_scan_all`. Source-count note: the survey's
"96 open" is now 94 open + 1 promoted + 122 archive = 217 (BKL-8N5K shipped to Archive in the
same session — explained drift; the three `status: resolved` archive items were normalized to
`shipped` on 2026-07-18 so they migrate as completed, not `not_planned`).
