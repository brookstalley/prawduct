# Migration scrub — owner decisions (recorded 2026-07-18; decisions 5–6 added 2026-07-20)

Owner checkpoint held at the end of the 2026-07-18 session (BKL-8N5K shipped, Critic clean).
**The live migration itself is HELD** — owner decision, not a blocker. Everything below is
**confirmed** and carries forward to the owner-run migration session (BKL-6M4T), which should
execute against these decisions without re-asking, re-confirming only if the source has drifted.

**Exception — decision 6 is NOT owner-confirmed.** It is builder-proposed and marked sign-off owed.
The "execute without re-asking" rule above covers decisions 1–5 only; 6 must be put to the owner
before it is acted on.

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

## Migration-session runbook pointer

`skills/backlog/migration-scrub.md` (steps 0–4, incl. 2b restructure pre-pass). Sequence:
re-confirm sign-off → author the v1 restructure plan for the keep set → `restructure-preview` →
owner batch approval → `import --restructure` (git history of the source is the pre-import
backup) → `export` backup **after** the import (it dumps the migrated repo — running it before
backs up nothing; ordering corrected 2026-07-18 per the holistic review) → apply the merges/drops
above (all disposition commands take `--repo`) → verify counts + spot-check → activate the
BKL-8P2R cutover (`backlog_service_repo: owner/repo` in project-state.yaml — the repoint code
shipped 2026-07-18) → retire `legacy.py` + `incoming-bugs/` in lockstep with the report-bug MG5
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
