# Migration scrub — owner decisions (recorded 2026-07-18; decisions 5–6 added 2026-07-20)

Owner checkpoint held at the end of the 2026-07-18 session (BKL-8N5K shipped, Critic clean).
**The live migration itself is HELD** — owner decision, not a blocker. Everything below is
**confirmed** and carries forward to the owner-run migration session (BKL-6M4T), which should
execute against these decisions without re-asking, re-confirming only if the source has drifted.

~~**Exception — decision 6 is NOT owner-confirmed.** It is builder-proposed and marked sign-off owed.
The "execute without re-asking" rule above covers decisions 1–5 only; 6 must be put to the owner
before it is acted on.~~ **DISCHARGED 2026-07-31 — see decision 6.** All six decisions are now
owner-confirmed, and decision 1's separate public-visibility sign-off is given.

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

1. **Live run: HELD** (2026-07-18). Target when it runs: `brookstalley/prawduct` (public). ~~The
   owner has NOT yet given the explicit public-visibility yes; re-confirm sign-off at the top of
   the migration session.~~

   **PUBLIC-VISIBILITY SIGN-OFF GIVEN — owner, 2026-07-31.** Verbatim: *"this is a public repo, and
   fine that our issues are public."* So the blocking condition on this decision is discharged and the
   migration session does **not** need to re-ask it. Recorded here rather than left to a transcript
   because it is consent to an irreversible public disclosure: under decision 5 (`--archive-scope all`)
   the whole corpus — open *and* archive — becomes public GitHub issues, and GitHub has no ordinary
   issue-delete and never reuses numbers (MG1). What remains held is the **run**, not the permission.
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

   **DISCHARGED 2026-07-31 — owner sign-off given, and events had already answered it.** The owner
   confirmed the recommendation. It is recorded as discharged rather than merely approved because the
   ordering question is **moot in substance**: part (b) **BUILT 2026-07-24** in v3.2.0 Chunk 04 — the
   Pacer now meters total REST points across create *and* close via `_PacingTransport` — so it landed
   before the bulk import exactly as this decision asked, and the bulk import has not run. The open
   sign-off was therefore a record lagging reality, not a live fork.

   **`BKL-6X5D` the ITEM is NOT closed by this**, and the distinction matters: part (b) is done, part
   (a)'s doc-coherence legs closed 2026-07-20, but the item's remaining leg — **quantifying the archive
   window** (an N-months / throughput formula between the `{all,open}` poles) — is live adopter-scale
   work with no bearing on prawduct's own run, which decision 5 settles at `all`.

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
> - **§ C — TWO drops APPROVED.** `COV-3M8Q`, against the recommendation to keep (the ratified goal it
>   served stays tracked by `CRT-8N5V` and `CRT-3W6P`), and `CRT-8Q6R`, which moved from § D to § C when
>   its own "check this first" condition was finally checked and came back against it.
> - **§ D — 80 keeps stand.**
> - **One requirement surfaced by the survey and filed rather than built:** the runbook records no
>   survey coverage boundary at all, so drift is undetectable for every consumer — prawduct only caught
>   its own because it hand-built a repo-local spike that does not ship. See § "What this section
>   changes about running the scrub."
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

### C. Drops — 2, both owner-approved (one against the recommendation)

| Item | Reason | Proposed |
|---|---|---|
| **COV-3M8Q** | Both of its named routes are now closed. The content-equivalence route was **RULED OUT 2026-07-29** (built, reviewed at 10 blocking with all three reviewers finding the same hole, reverted); the route it then pointed at — record-mechanization Chunk 03, per-mode reviewer payload — **shipped in v3.2.2**. What remains is the bare observation with no live route. **Counter-argument, stated so the drop is not taken cheaply:** the treadmill itself is unfixed (`is_judgeable_path` still classifies by extension, so a docstring-only `.py` edit still demands a full cycle) and the governing goal is ratified. Other items hold that line — `CRT-8N5V`, `CRT-3W6P` | **`dropped` — owner, 2026-07-31.** The counter-argument was put and not taken; recorded here so the drop reads as a decision made against a stated case, not a case nobody made |
| **CRT-8Q6R** | The 4-minute cache-warm interval, sized against an **assumed** 5-minute prompt-cache TTL. The item's own first candidate fix was *"drop it entirely if the harness already handles cache retention — check this first."* **That check can now be made and it comes back against the constant:** sessions run under a documented **1-hour** TTL, which is exactly the case the item calls wasteful ("it burns readouts to defend a cache that was never at risk"). What the item called "a guess dressed as a constant" is now a guess known wrong in the direction that makes the mechanism pure cost. **The requirement is not dropped, the constant is** — "a waiting session must not idle silently" stays live through `CRT-3F7M`, whose cross-link already records that a synchronous coordinator await largely obviates the stopgap and its TTL guessing. **This is not a code change:** `_CACHE_WARM_DIRECTIVE` / `_CACHE_WARM_INTERVAL_MINUTES` and their two pinning tests are untouched | **`dropped` — owner, 2026-07-31** |

### D. Keep — the remaining 80

Everything not named above. No staleness signal and no duplication signal survived screening. Rather
than restate 80 near-identical reasons, the grounds are: each is a recent, independently-verified defect
against live machinery, most carrying explicit dedup rulings from prior sessions.

**Final tally, after the owner's rulings:** 91 = 7 shipped + 2 merged away + 2 dropped + 80 kept. (The
held merge returns `BLD-5R7K` to the keep set; `CRT-8Q6R` left it.)

One keep worth flagging because new evidence has arrived since filing, without changing the
disposition:

- **GOV-7W3D** (6 of 10 `## Direction` norms undispositioned). Its deadline was *"before Chunk 06 runs"*
  and v3.2.0 shipped without Chunk 06, so the trigger has been overtaken rather than met. The plan file
  is retained (Chunks 06/07 unbuilt), so the item is live — but its bound needs restating.

### What this section changes about running the scrub — and the fleet-wide gap behind it

The instrument's verdict **cannot** flip to `CURRENT` by recording dispositions. `backlog_scrub_drift.py`
derives "unsurveyed" as *open items filed since `SNAPSHOT = "964d03b"`*, so on a growing corpus that set
is non-empty forever. Advancing `SNAPSHOT` to the commit this survey was taken at (`a232407`) is what
closes the loop locally — **only after** these dispositions are confirmed, since advancing first would
silently declare an unreviewed corpus surveyed.

**But the local fix is not the fix, and treating it as one would leave every consumer where prawduct
was.** The generalizable defect, filed 2026-07-31:

> A scrub survey is a claim about a corpus **at a moment**, and neither `migration-scrub.md` nor any
> artifact it writes records *which moment*. Step 2 says "surface candidates," Step 3 says "owner
> confirms," and nothing between them establishes what was surveyed or notices that the corpus moved.
> With no recorded coverage boundary there is no definition of "surveyed," so an approved disposition
> table has unknown currency at run time.

prawduct caught its own drift only because someone hand-built `tests/spikes/backlog_scrub_drift.py` and
hand-wrote the ⚠ block at the head of this file. **Neither ships** — `tests/spikes/` is repo-local, so a
consumer following the runbook has no drift check at all. The fix has three legs, and the middle one is
the design call:

1. **Record the boundary explicitly, never derive it.** Deriving it from "the last commit touching this
   artifact" would let an unrelated edit declare the corpus surveyed — and that is not hypothetical: the
   owner-ruling commit for *this very survey* edited this file for reasons unrelated to coverage.
2. **Make the baseline a DATE, not a git ref.** A ref-keyed check **dies at cutover** — it resolves
   through `git show <ref>:.prawduct/backlog.md`, and post-cutover the markdown is frozen while the live
   corpus is Issues, so the check silently stops meaning anything at exactly the moment the migration
   completes. A date evaluates identically on both backends (every open markdown item carries `added:`
   — **every** one of them does, which is the property the baseline needs; issues carry `created_at`) and is immune to the amend/rebase SHA-orphaning
   this repo has already recorded once (BKL-2Q7F, correction 3).
3. **Surface it at Step 3 as a stated choice, not a refusal.** A survey is judgment — "these five are
   all keeps" is a legitimate answer — so a hard gate would block sound runs with no override. Match
   Step 3c's existing archive-scope pattern: state the cost plainly, owner decides, record the choice.

**No new adapter op.** The check is `backlog list --json` plus a date filter, and `list` already routes
to whichever backend is live — so this adds **zero** governed surface, which matters because `GOV-6D4Q`'s
deletion-only pass forbids adding any and is sequenced ahead of Chunks 07/08.

## Survey 3 — full-corpus cleanup pass (**OWNER-CONFIRMED 2026-08-01**)

> ### ✅ OWNER RULING — 2026-08-01
>
> - **§ A, § B and § C APPROVED as proposed** — 1 close, 4 drops, 19 folds into 13 survivors, including
>   all five root-cause uplevels and both contested folds (`VWS-2W6H`, `TST-6H2Q`).
> - **§ B gains a fifth drop: `MET-9K4R`.** Proposed as *held* on the ground that a never-picked idea
>   belongs to `GOV-6D4Q`'s deletion-only pass rather than to a migration scrub; the owner ruled it
>   dropped here instead. Recorded as a decision made against a stated case, not one nobody made.
> - **§ D is OVERRULED — the `CRT-6J4P → CRT-8H3R` merge STANDS as approved 2026-07-18.** The
>   withdrawal argument (that CRT-6J4P's same-lineage cross-bundle chain survives an ancestor guard,
>   so folding it loses a defect the fix does not catch) was put and not taken. Whoever builds
>   CRT-8H3R should read the folded body for the same-lineage case rather than assuming the ancestor
>   guard closes it.
>
> **Ordering — the dispositions split on decision 3's line, not Survey 2's.** The proposal said "apply
> §A–§C to the markdown pre-migration, the same order Survey 2 used." That is **corrected here** and
> the correction is the reason worth recording: Survey 2's pre-import exception was earned by *status
> flips*, where minting an open issue to describe finished work is the waste. It does not extend to
> **folds** — `merge` writes a real `superseded_by` redirect *before* closing the source (AU3/CRASH-2),
> and markdown can only carry that as prose. So:
>
> - **Pre-import, to the markdown source:** § A only (`BKL-3T7X` → `shipped`). Same class as Survey 2 § A.
> - **Post-import, through the adapter:** § B's five drops and § C's nineteen folds, alongside the
>   2026-07-18 set's five merges and thirteen drops. **42 disposition ops in total** — ~1.7s each at
>   VRF-009's measured latency, so the ordering costs nothing and buys real redirects.
>
> The frozen markdown will therefore record these 24 items as open **at cutover**, which is accurate
> history; the live tracker is authoritative from that moment (Step 6).

Requested by the owner at the head of the Chunk 06 session, ahead of the restructure decision:
*"First we should do a cleanup pass to close completed items, merge duplicates (including upleveling
where details are distinct but same root cause), and delete items obsoleted by movement in the code."*

**Survey baseline: the whole open corpus at `5a169b2` (origin/develop) — 195 open items, read in full
through `lib.backlog.legacy.parse_backlog`.** Unlike Survey 2, which closed a coverage *gap*, this pass
re-screens every open item including the ones Surveys 1 and 2 already kept. That is why it finds folds
those surveys did not: they screened for staleness and duplication; this screens for **shared root
cause**, which is a different question and returns different answers about the same corpus.

**Corpus shape, and the honest headline: this backlog is not silted, it is dense.** Zero items were
dropped on staleness grounds — the same result Survey 2 got, for the same reason. The corpus is
overwhelmingly recent, independently-verified defects against live machinery, most carrying explicit
dedup rulings from prior sessions. The reduction available here comes almost entirely from **upleveling
by root cause**, not from disposal.

### A. Close as shipped — 1

| Item | Verification performed | Proposed |
|---|---|---|
| **BKL-3T7X** (issue-title/body standard) | Its own deliverable — `documentation/backlog-service-issue-standard.md` — exists on disk. It was **decomposed 2026-07-17** into four build items; three are archived `shipped` (BKL-2H9W, BKL-4C6P, BKL-8N5K) and the fourth (**BKL-7F3D**, YAML Issue Forms) is open and carries the residual | `shipped` |

### B. Drops — obsoleted by movement in the code, 4 (+1 held for the owner)

Each was checked against the tree today, not read off its own annotation.

| Item | What moved | Confidence |
|---|---|---|
| **STH-6T9W** (untracked non-code files inflate the chunk-diff scope) | kernel-v3 deleted both scope sites and pinned them deleted; the **waiver-wedge is gone** (`files_reviewed` is code-derived). The item's own landing option **(c) WONTFIX** says so: *"a legitimate outcome now that the harm is 'run one extra review' rather than 'waiver or nothing'; the original waiver-training argument no longer applies."* Verified the milder residue survives (`is_judgeable_path('note.txt')` → True) — that is the harm the item itself rates as not worth fixing | **High** — the item names its own drop |
| **CRT-9L2F** (post-release check that an explicit `/critic` mode is honored) | Written 2026-06-10 against a `$ARGUMENTS`-delivery hazard. The mechanism has since been redesigned twice: `SKILL.md` step 1 now says **"Forward, never parse"** into `prawduct-hook infer-critic-mode`, which owns the whole precedence and returns `explicit-args` as a rationale (`critic_mode.py:136`). The verification task names a release six versions stale | **Med-high** |
| **GOV-8N4V** (a set `active_build_plan` reads as "no active build plan") | The heading-form facet was closed by BLD-5J8N's parser broadening. Checked the plan the item names: `build-plan-norm-lifecycle.md` carries `artifact: build-plan` frontmatter and a colon-form `## Status` roster, both of which today's parsers accept. No live repro remains | **Medium** — re-file if it recurs |
| **TST-6H2Q** (xdist cross-file pollution flaking two stop-gate tests) | Not reproduced during its own 2026-07-19 salvage; the full suite ran green today (3141 passed, 7 skipped). Same disposition and same reasoning as **TST-4P8H**, which the 2026-07-18 set already drops for "no active flakes" | **Low-medium** — one green run is weak evidence; both named tests still exist, so a recurrence re-files cheaply |
| **MET-9K4R** (workflow-values schema/validator) | **HELD for the owner, not proposed.** Verified still unvalidated — no code reads or checks `Branching:` / `PR creation:` / `PR merge:` vocabulary. Filed 2026-05-01 at `stage: design` with its own note "low priority — current values are stable," and no instance of the typo-silently-defaults failure has ever been observed. It is a *never-picked idea*, not an obsoleted item, so it belongs to **GOV-6D4Q**'s deletion-only pass rather than to a migration scrub | — |

### C. Merges and uplevels — 19 folds into 13 survivors

The distinction the owner asked for: a **merge** folds a duplicate; an **uplevel** folds several items whose
*details* are distinct but whose *root cause* is one, retitling the survivor to the root so the fix is
aimed at the cause rather than at whichever surface someone happened to be looking at.

**Uplevels (root cause named; instances folded with their bodies preserved):**

| Survivor (retitle to the root) | Folded | The one root cause |
|---|---|---|
| **CRT-9K2P** | CRT-2X7R, CRT-7P5J, CRT-3F7T | **A single-latest-fact derived view stands in for the append-only evidence store.** CRT-9K2P is the census/render path, CRT-2X7R the write path (`verify-resolutions` can only anchor to the cache's one `fact_id`), CRT-7P5J the handoff read path, CRT-3F7T the disposition vocabulary on CRT-9K2P's own surface. One decision — *compose over every review fact in the interval* — answers all four. **Read the objection before ruling:** the corpus says "fixing any one leaves the other two standing." That is true of a *point* fix and is exactly the argument for upleveling rather than against it; CRT-9K2P's own dedup note already names the shared root in those words |
| **BKL-6T3P** | BKL-2D8N, BKL-4H8P, BKL-9T3K | **The adapter's instruction surface does not describe its own contract.** BKL-6T3P bounds the model by "the ops in the usage table" and no usage table exists; BKL-2D8N is that `--help` prints exit-2 instead of the usage; BKL-4H8P is that `retryable: true` states no budget; BKL-9T3K is that block ownership is unstated. **BKL-2D8N's fix literally mints BKL-6T3P's missing referent.** All four are the same surface and the same dogfood |
| **BLD-8R3T** | BLD-9H2M, BLD-5N7C | **The `new` forward-reference exemption is both under- and over-reaching.** BLD-8R3T's own body already requires BLD-9H2M to "land first or alongside," and names BLD-5N7C as "the two instances" of itself. One visit to `_BUILD_PLAN_NEW_QUALIFIER_RE` and the exemption's expiry |
| **VWS-4T9P** | VWS-2F9K, VWS-2W6H | **`build_scope_to_plan_map` answers "which file is a plan" wrong three ways** — invisible (non-recursive glob), mis-classified (no `artifact: build-plan` filter), and unmatchable (`CHUNK_LINE_RE` requires the colon form). VWS-4T9P already says of VWS-2F9K "fix them together — do not fix one and leave the other." **The corpus argues against folding VWS-2W6H** ("cross-linked deliberately, not merged") — the counter is that all three edit the same two glob sites, so they are one visit whoever does them |
| **COV-8R2K** | COV-6T3P | **One judgeability predicate with no per-project file-type opinion.** COV-8R2K wants `.md`/config to stop blocking coverage; COV-6T3P wants `.md` to *start* counting for markdown-centric products. Opposite directions, one knob. Both already name `is_judgeable_path` as the site |

**Ordinary merges (one fix closes both, by the corpus's own words):**

| Survivor | Folded | Why |
|---|---|---|
| **GOV-3K7M** | GOV-2H6X | GOV-3K7M's stated fix — *"when the scope-named plan and the pointer disagree, that is the `unchecked` case, not a silent grade"* — **is** GOV-2H6X's entire ask (counters must not read clean when nothing was checked). Threading the manifest's `scope` into `lint_records_safe` delivers both |
| **STH-4P2R** | STH-3K7M | Verbatim from the corpus: *"one 'resolve the session's git context once at the `cmd_clear` entry and pass it down' change closes both items"* |
| **LRN-6C2X** | LRN-5T2W | Both are whole-file heading-identity checks over the same two files, both break under LRN-9K2P. LRN-5T2W: *"they should almost certainly be built in one pass."* **LRN-9K2P is NOT folded** — it is the sequenced consumer these guardrails must precede, not a duplicate |
| **LRN-8P3W** | LRN-3F8K | Explicit instance/class pair with an explicit instruction: *"Work them together — LRN-3F8K is the one-line reconciliation, this is the guard that stops it recurring"* |
| **CRT-3W6P** | CRT-8N5V | CRT-8N5V has **no residual of its own**: remaining-scope #1 is COV-3M8Q (dropped 2026-07-31), #2 is *"now carried by CRT-3W6P"* in its own words, and #3 is what CRT-3W6P says *"should be designed alongside it."* The survivor is the item that carries the live work; the parent's body is preserved verbatim |
| **CRT-6R3W** | CRT-4X2N | CRT-4X2N is *"the enumeration half of a larger problem; CRT-6R3W carries the rule-vs-instance design question."* One reviewer-protocol change states the generating rule **and** enumerates instances. Direction matters: CRT-6R3W's "must not be deduped into it" forbids folding the *stronger* item into the weaker one, which is not what this does |
| **GOV-7W3D** | GOV-8C3W | **GOV-8C3W's escalation is already shipped.** It asked to "make the enumeration mechanical"; `record_lint`'s `governed-by-gap` check did exactly that in record-mechanization Chunk 02 (measured yield: 22 gaps across 8 plans). Its residual — complete the `security-model` dispositions — is a subset of GOV-7W3D's ask |
| **ONB-7K4D** | BKL-4C9P | Same defect, two files, and ONB-7K4D already states the shared fix: *"BKL-4C9P is the same class one file over, and should be fixed the same way… Whichever of the two lands first should carry the shape to the other."* State the invariant; never correct the count |

**Considered and deliberately NOT merged** (recorded so they are not re-proposed):
`GOV-6X2N`↛`COV-4M2J` (same root, but GOV-6X2N is closable off a language-agnostic trigger and must not
wait on an L-sized requirements pass) · `SCN-8T4R`/`GOV-5N8R`↛`BND-1S4K` (each carries a guardrail leg
beyond the artifact entry; BND-1S4K says so) · `REL-6Q4M`↛`REL-7D4X` (adjacent, but different
mechanisms — runbook prose vs `release_readiness.py`) · `LRN-9K2P`↛`LRN-6C2X` (sequenced consumer,
not duplicate) · `CRT-4V8P`↛`GOV-3K7M` (shares the unbounded-pointer root, but owns mode inference and
review *attribution*, which a record-lint argument does not reach).

### D. One previously-approved disposition the owner should reconsider

**`CRT-6J4P → CRT-8H3R` (approved 2026-07-18) is contradicted by its own target's body.** The approval
reason was *"same mode-inference ancestor-guard fix; bodies cross-reference."* One day later, CRT-6J4P's
2026-07-19 salvage annotation records the opposite, as a correction to the record: *"The branch's ancestor
guard closes only the sibling-BRANCH sub-case, which is CRT-8H3R's territory, not this one… do not treat
the CRT-8H3R fix as closing it."* CRT-6J4P is a **same-lineage** cross-bundle chain (the anchor **is** an
ancestor of HEAD, so an ancestor guard passes it); CRT-8H3R is the sibling-branch case. **Folding them
loses a defect an ancestor guard provably does not catch.** Recommend **withdrawing this merge**; the
other four 2026-07-18 merges are unaffected and re-verified resolvable today.

### E. Net effect

195 open → **153** (−21%): 18 already-approved-and-pending (5 merges + 13 drops, all re-verified
resolvable today by `tests/spikes/backlog_scrub_drift.py`), plus 19 new folds, 1 close, 4 drops. Minus
the CRT-6J4P withdrawal in § D, which returns one item to the keep set.

### F. Keep — the remainder

No staleness signal and no shared-root signal survived screening. The grounds are the same as Survey 2's:
each is a recent, independently-verified defect against live machinery, most carrying an explicit dedup
ruling from a prior session. Two are worth flagging to the migration session specifically rather than
restating 150 reasons: **GOV-7W3D**'s deadline is literally *"before Chunk 06 runs"* (six `## Direction`
norms undispositioned on this very plan), and **BKL-9F6T** is the coverage-boundary defect this survey is
the third hand-run instance of.

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
