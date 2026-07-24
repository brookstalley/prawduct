# Migration scrub — markdown backlog → GitHub Issues (MG4)

The one-time, owner-confirmed cleanup that runs when a project moves its
`.prawduct/backlog.md` onto GitHub Issues through the backlog service
(`prawduct-hook backlog <op>`). It surfaces stale and duplicate items *before*
they become live issues, so the migrated backlog starts clean instead of
inheriting years of silt.

The session-start **`backlog-service-migration-required`** advisory (GV7) is what
nudges an un-migrated repo here: while `.prawduct/backlog.md` holds a structured
backlog and `backlog_service_repo` is unset, every session flags that migration is
required — so a repo that upgraded past prawduct's own cutover is told to migrate,
never silently degraded to a zeroed backlog count.

This is a **workflow over the deterministic ops** (`provision` / `list` / `status` /
`merge` / `import`), **not a single command** (API §2.5). Run it interactively with
the owner.

## The one invariant: the model decides, it never touches the data plane (MG4/G1)

You (the model) may read items and *propose* dispositions. Every mutating
step — `import`, `merge`, `status` — receives a **concrete set the owner has
confirmed**, never an inference applied on your own authority. Nothing is ever
hard-deleted: a stale item is *closed* (`status … dropped`), a duplicate is
*folded and redirected* (`merge`), and both keep their body verbatim (DM7). No
silent drops — every item is either migrated, closed with a recorded reason, or
explicitly left to the owner. This is asserted structurally by the MIG-5 test:
the import op consumes a record set, not a model call.

## Steps

**0. Select and confirm the target repo — the one binding every later step reads.**
This is the guard that stops a scrub from writing 100–250 real issues into a repo
nobody chose. Nothing below runs until it is done.
   - **Name the target `owner/repo`** with the owner — the GitHub repo whose Issues
     will hold the migrated backlog. **Never infer it from the current directory's
     git remote.** A product may migrate into its own repo, a dedicated backlog
     repo, or an org repo; the current checkout's remote is a guess, and a wrong
     guess is not cleanly reversible — GitHub has no ordinary issue-delete and never
     reuses numbers. If the current directory is not a GitHub repo — or not a git
     repo at all — there is no default to offer: the owner names the target outright.
     (A product staying on the markdown backend has nothing to migrate and should
     not be running this at all.)
   - **Owner confirms** the exact `owner/repo`. Apply nothing until they do.
   - **Record it** where the other scrub decisions live — with the date — so the
     target is auditable later, not remembered only in a transcript. (This repo's
     own run records it in `.prawduct/artifacts/migration-scrub-decisions.md`; a
     product following this runbook uses whatever artifact holds its scrub
     decisions.)
   - **This is NOT the cutover.** Recording the target here does *not* set
     `backlog_service_repo` in `project-state.yaml` — that scalar flip is **Step 6**,
     after the import is verified. Flipping it now would freeze the markdown backlog
     before a single issue exists. Here you *bind* the value; Step 6 *activates* it.
   - **Provision the label taxonomy** against the confirmed target, before any import
     creates labels ad hoc:
     `prawduct-hook backlog provision --repo <target>`
     Idempotent and collision-free — it only ever creates the `<facet>:`-namespaced
     base labels it does not find, and never touches a repo's existing labels. This
     is the scrub's ownership of provisioning; the other two entry paths own it for
     theirs — `/prawduct:onboard` provisions at adoption, `/prawduct:doctor`
     reconciles as a repair.

**Throughout the steps below, `<target>` is that one owner-confirmed repo from
Step 0 — bound once, never re-derived. Every `--repo <target>` is the same value; do
not re-template it per step, and never fall back to the current repo's git remote.**

**1. Back up.** The source `.prawduct/backlog.md` (+ any archive file) is
git-tracked — that is the pre-migration backup. After the first import, run
`prawduct-hook backlog export --repo <target> --to <dir>` for a
full-fidelity restorable dump (body block + native graph).

**2. Surface candidates.** Read the backlog — before import, the source file;
after a first import, `prawduct-hook backlog list --repo <target> --json`.
Propose two candidate sets:
   - **Stale** — items unmoved for a long time, superseded, or obviously
     obsolete. Group with a one-line "why this looks stale."
   - **Duplicate / overlapping** — cluster by area + title/body overlap. For
     each cluster name the **survivor** (the item others fold into) and the
     duplicates. (Lexical `search --like` is a post-cache accelerator, not
     available in the cacheless service — surface duplicates by reading the
     `list` output directly.)

   Present both sets as a **disposition table**: `id | action (keep | drop |
   merge→survivor) | reason`. This table is the model's decision, expressed as
   data.

**3. Owner confirms.** Show the table. The owner accepts, edits (change an
action, correct a survivor), or defers individual rows. **Apply nothing that is
not confirmed.** Deferred rows stay live and untouched — never a silent drop.

**3b. Restructure pre-pass (MG6 — issue-standard §5).** For the items being
migrated (typically the open set; archive items may stay verbatim), *propose* a
restructure plan as a JSON file — per item: a ≤72 `area:`-prefixed title,
template body sections, and a `kind:`. **Flag non-atomic items
(`"non_atomic": true`) for owner manual split — never auto-split** (splitting
mints new IDs and is an owner scrub decision; 1 PFX = 1 issue).

Plan shape (v1 — validation is fail-closed; a typo'd PFX or unknown key
refuses the whole run, so match this exactly):

```json
{
  "v": 1,
  "items": {
    "BKL-XXXX": {
      "title": "area: specific summary (<=72 chars)",
      "kind": "bug|feature|task|chore|spike",
      "sections": {"Problem": "…", "Proposed change": "…",
                    "Acceptance": "- [ ] …", "Scope-out": "…"},
      "non_atomic": false,
      "note": "free text shown in the preview"
    }
  }
}
```

Every per-item key is optional (a `non_atomic`/`note`-only entry is a valid
flag-only row). `sections` compose through the shared `issuefmt.render_body`
templates — bug: Problem/Repro/Actual/Expected/Evidence(/Env); everything
else: Problem/Proposed change/Acceptance/Scope-out(/Evidence); extra section
keys are appended, never dropped. The title is normalized against the item's
`area:` label, so a bare summary is also acceptable. Then render the
aggregate review artifact and show it to the owner:
`prawduct-hook backlog restructure-preview --from .prawduct/backlog.md [--archive <archive>] --plan <plan.json> --out <preview.md>`
The owner reviews **in aggregate** (representative sample + the full
before/after artifact) and approves the batch — not per-item. The preview is
generated from the same code path the import consumes, so what is approved is
byte-for-byte what gets written. Originals are preserved verbatim
(`original_title`/`original_body` block fields + the MG2 export backup + git
history of the source file) — a bad rewrite is always recoverable.

**3c. Decide archive scope (MG4b) — an explicit owner choice, never a silent
default.** Ask the owner how much of the historical archive to mint as GitHub
issues, and name the tradeoff:
   - **`open`** — migrate only the live/open set, minting **no** closed issue per
     ancient item. Fewer *total* writes (NF3) and a cleaner live tracker — note the
     ≈80/min + ≈500/hr *rate* ceiling is the Pacer's job, not this lever's (it
     reduces write *volume*, not the rate — BKL-6X5D). **State the cost plainly
     before the owner chooses:** the skipped archive stays in the **git-tracked
     source markdown** (Step 1's pre-migration backup) — *not* in the MG2 export,
     which dumps the migrated repo and therefore never contains what this lever
     excluded. So those items are preserved as **git history, not as live backlog**:
     after cutover the skill treats the source file as frozen history and stops
     reading it, so the skipped set is **outside the tracker entirely** — no adapter
     op, at any flag, can reach it. What is *not* `open`-specific: archived items are
     absent from a default `list` and from add-time dedup under **either** scope (see
     `all` below), so a duplicate of a previously-dropped item can be re-filed with no
     signal either way. The lever decides whether the record is *recoverable through
     the tracker*, not whether dedup sees it. (State it as `list`, not `find`:
     full-text `find` is unavailable for *every* item post-cutover, so it is not what
     this lever costs.)
   - **`all`** — import the full archive as closed issues (every disposed/shipped
     item becomes a closed issue). Complete history *in the tracker* — but
     **reachable, not visible by default**: `list` defaults to `state=open`
     (`lib/backlog/query.py`), and so does the dedup-on-create check `adapter-mode.md`
     documents (`list --area=<area> --json`, no state filter). Seeing the archive takes
     an explicit `--state closed` or `--state all`. So the differential against `open`
     is **reachability, not default visibility**: `all` puts the archive one flag away
     inside the tracker; `open` leaves it outside the tracker entirely, in frozen
     markdown no adapter op reads. Neither scope makes archived items show up in a
     default `list` or block a duplicate at add time. **Its cost, stated
     symmetrically:** an archived item is **two** writes, not one — a create, then a
     status reconcile to closed (the create path has no initial-state field).
     **Both writes are metered** — a `_PacingTransport` decorator charges every
     migration REST call against a 900-points/minute window (5 per write, 1 per
     read), so the close is inside the meter alongside the create. *(Corrected
     2026-07-24: this previously read "Only the create is paced (`Pacer.before_create`
     is the sole paced call), so a large `all` run spends its close writes outside
     the meter" — true when written, made false by the Chunk 04 metering fix, which
     updated the NFR but not this runbook.)* A live `--archive-scope all` run of 295
     items measured **zero** pacing waits: serial `gh` round-trip latency caps the
     burst well under the ceiling, so the budget is a safety belt rather than the
     governor (VRF-009). Size the run on **wall clock** — roughly latency × call
     count, ~18 minutes for 295 items — not on rate-limit risk.

   The model surfaces the tradeoff; the owner decides; the deterministic importer
   applies it via **`--archive-scope {open|all}`** (Step 4) — a data-plane lever,
   never a model inference. Keep the restructure plan (Step 3b) scoped to the set
   you migrate: under `open`, don't author plan entries for archived items you're
   dropping (the importer refuses fail-closed if the plan names an item outside the
   chosen scope — a contradiction, caught, never a silent mis-import). A *quantified*
   recent-shipped window between the poles
   (migrate the last N months, drop older) is the adopter-scale refinement tracked
   by **BKL-6X5D**; today the lever is the binary open/all.

   **Record the choice where the other scrub decisions live**, with its date and the
   cost the owner accepted — the migration is one-time and irreversible in part, so a
   choice remembered only in a transcript is a choice nobody can audit later. (This
   repo's own run records it in `.prawduct/artifacts/migration-scrub-decisions.md`
   alongside the disposition table; a product following this runbook should use
   whatever artifact holds its scrub decisions.)

   **`open` is reversible, but the reversal is not free — say both halves.** A repo
   migrated with `open` can be re-run later under `--archive-scope all` to mint the
   archive it skipped, and the already-migrated items are skipped rather than
   duplicated (the skip authority is the `id:PFX` alias written in the create). So
   `open` *defers* the archive; it does not discard it. **But the skip path still
   reconciles status**, so that backfill re-syncs every already-migrated item to its
   **markdown** status — reopening anything closed on the service since cutover. On a
   repo that has been live for a while, treat the backfill as a migration in its own
   right (re-scrub the source first), never as a free top-up.

**4. Apply the confirmed plan — deterministically.**
   - **Import** the source into issues (idempotent/resumable, keyed on the
     `id:PFX` alias, so a re-run never duplicates), applying the confirmed
     restructure plan at create:
     `prawduct-hook backlog import --repo <target> --from .prawduct/backlog.md [--archive <archive>] [--archive-scope {all|open}] [--restructure <plan.json>]`
     (`--archive-scope` defaults to `all`; pass `open` for the open-only choice from Step 3c —
     the closed/archived items it skips stay in the git-tracked source markdown — never lost, but
     outside the migrated tracker and so outside post-cutover `list` and dedup; see Step 3c)
   - **Fold each duplicate** into its survivor (writes the `superseded_by`
     redirect *before* closing the source, so a crash leaves a resolvable
     open-but-redirected item, never an orphan — AU3/CRASH-2):
     `prawduct-hook backlog merge <duplicate-id> --into <survivor-id> --repo <target>`
     (`--repo` is required for bare `PFX-XXXX` ids — alias resolution needs the
     target repo)
   - **Close each stale item** (closed + preserved, not deleted):
     `prawduct-hook backlog status <id> --to dropped --repo <target>`

   Ordering: import-then-dispose is always safe and idempotent. For a **large**
   backlog where the content-creation budget (≈80/min, ≈500/hr) is the scarce
   path, it is tempting to import obvious stale items already-closed to avoid
   create-then-close churn — **but the importer cannot do that today**: the create
   path carries no initial-state field (Step 3c), so every closed item is a create
   plus a status reconcile regardless of ordering. Treat the churn as a fixed cost
   of `all` and size the run for it; revisit only if the create path gains an
   initial state.

**5. Verify.** `prawduct-hook backlog counts --repo <target>` for the
rollup; spot-check a handful of migrated bodies and IDs; confirm every
hand-minted `PFX` resolves as an `id:PFX` alias and every disposed item is
*closed*, not missing. Total issue count = every source item — a dropped or
merged item is still present, just closed.

**6. Cut over.** Record the switch that makes the migrated repo the live
backlog — a top-level scalar in `.prawduct/project-state.yaml`, set to the same
`<target>` bound in Step 0:

```yaml
backlog_service_repo: <target>
```

This single key (API §2.4) repoints the session briefing to the GV2 snapshot
(`snapshot.read`, file-only, visible age + detached refresh warm — never a
synchronous network call) and retires every markdown-premise advisory probe
(the backlog trio `legacy-backlog-format` / `legacy-section-schema` /
`backlog-overdue-grooming` AND the norm trio `revisit-due` / `dead-why` /
`stalled-transition` — the frozen file must not generate nudges). Retirement is
not silence: one probe starts firing at the same switch —
`backlog-checks-dormant`, an `info` advisory naming every backlog check that has
no Issues-backend path yet, so the operator running this scrub learns what goes
dark rather than discovering it as an unexplained absence (full retirement
table: post-sync-advisory-spec §8.2). **Do not set
it before the import has been verified** (Step 5) — once set, the briefing
stops counting the markdown file. From here the markdown backlog is frozen
history; `legacy.py` + `incoming-bugs/` retirement follows in lockstep with
their replacements (build plan Chunk 06).

## What must never happen

- A mutating op run on an item the owner did not confirm.
- An item removed from the source with no corresponding closed issue (a silent
  drop).
- A hard delete — the service never deletes issues (GitHub does not reuse
  numbers; disposal is always close/redirect).
- A model call inside `import`/`merge`/`status` — the decision happens upstream,
  in this workflow, as confirmed data.
