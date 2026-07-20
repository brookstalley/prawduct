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

This is a **workflow over the deterministic ops** (`list` / `status` / `merge` /
`import`), **not a single command** (API §2.5). Run it interactively with the
owner.

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

**0. Back up.** The source `.prawduct/backlog.md` (+ any archive file) is
git-tracked — that is the pre-migration backup. After the first import, run
`prawduct-hook backlog export --repo <owner/repo> --to <dir>` for a
full-fidelity restorable dump (body block + native graph).

**1. Surface candidates.** Read the backlog — before import, the source file;
after a first import, `prawduct-hook backlog list --repo <owner/repo> --json`.
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

**2. Owner confirms.** Show the table. The owner accepts, edits (change an
action, correct a survivor), or defers individual rows. **Apply nothing that is
not confirmed.** Deferred rows stay live and untouched — never a silent drop.

**2b. Restructure pre-pass (MG6 — issue-standard §5).** For the items being
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

**2c. Decide archive scope (MG4b) — an explicit owner choice, never a silent
default.** Ask the owner how much of the historical archive to mint as GitHub
issues, and name the tradeoff:
   - **`open`** — migrate only the live/open set, minting **no** closed issue per
     ancient item. Fewer *total* writes (NF3) and a cleaner live tracker — note the
     ≈80/min + ≈500/hr *rate* ceiling is the Pacer's job, not this lever's (it
     reduces write *volume*, not the rate — BKL-6X5D). **State the cost plainly
     before the owner chooses:** the skipped archive stays in the **git-tracked
     source markdown** (step 0's pre-migration backup) — *not* in the MG2 export,
     which dumps the migrated repo and therefore never contains what this lever
     excluded. So those items are preserved as **git history, not as searchable
     backlog**: after cutover the skill treats the source file as frozen history
     and stops reading it, putting the skipped set outside `find`/`list`.
   - **`all`** — import the full archive as closed issues (every disposed/shipped
     item becomes a closed issue). Complete history *in the tracker*, and the whole
     archive stays reachable from `find`/`list` after cutover. **Its cost, stated
     symmetrically:** an archived item is **two** writes, not one — a create, then a
     status reconcile to closed (the create path has no initial-state field). Only
     the create is paced (`Pacer.before_create` is the sole paced call), so a large
     `all` run is a half-metered create-then-close stretch — the gap **BKL-6X5D part
     (b)** exists to close.

   The model surfaces the tradeoff; the owner decides; the deterministic importer
   applies it via **`--archive-scope {open|all}`** (step 3) — a data-plane lever,
   never a model inference. Keep the restructure plan (step 2b) scoped to the set
   you migrate: under `open`, don't author plan entries for archived items you're
   dropping (the importer refuses fail-closed if the plan names an item outside the
   chosen scope — a contradiction, caught, never a silent mis-import). A *quantified*
   recent-shipped window between the poles
   (migrate the last N months, drop older) is the adopter-scale refinement tracked
   by **BKL-6X5D**; today the lever is the binary open/all. prawduct's own dogfood
   is owner-decided as **`all`** — decision A1, taken 2026-07-20 and recorded in
   `.prawduct/artifacts/migration-scrub-decisions.md`, which also carries its
   consequence (part (b) becomes a release blocker for v3.2.0).

**3. Apply the confirmed plan — deterministically.**
   - **Import** the source into issues (idempotent/resumable, keyed on the
     `id:PFX` alias, so a re-run never duplicates), applying the confirmed
     restructure plan at create:
     `prawduct-hook backlog import --repo <owner/repo> --from .prawduct/backlog.md [--archive <archive>] [--archive-scope {all|open}] [--restructure <plan.json>]`
     (`--archive-scope` defaults to `all`; pass `open` for the open-only choice from step 2c —
     the closed/archived items it skips stay in the git-tracked source markdown — never lost, but
     outside the migrated tracker and so outside `find`/`list` after cutover; see step 2c)
   - **Fold each duplicate** into its survivor (writes the `superseded_by`
     redirect *before* closing the source, so a crash leaves a resolvable
     open-but-redirected item, never an orphan — AU3/CRASH-2):
     `prawduct-hook backlog merge <duplicate-id> --into <survivor-id> --repo <owner/repo>`
     (`--repo` is required for bare `PFX-XXXX` ids — alias resolution needs the
     target repo)
   - **Close each stale item** (closed + preserved, not deleted):
     `prawduct-hook backlog status <id> --to dropped --repo <owner/repo>`

   Ordering: import-then-dispose is always safe and idempotent. For a **large**
   backlog where the content-creation budget (≈80/min, ≈500/hr) is the scarce
   path, obvious stale items may instead be imported already-closed to avoid
   create-then-close churn — confirm the exact recipe against the live dry-run
   before committing to it, since the burst size decides whether it is worth the
   extra bookkeeping.

**4. Verify.** `prawduct-hook backlog counts --repo <owner/repo>` for the
rollup; spot-check a handful of migrated bodies and IDs; confirm every
hand-minted `PFX` resolves as an `id:PFX` alias and every disposed item is
*closed*, not missing. Total issue count = every source item — a dropped or
merged item is still present, just closed.

**5. Cut over.** Record the switch that makes the migrated repo the live
backlog — a top-level scalar in `.prawduct/project-state.yaml`:

```yaml
backlog_service_repo: <owner/repo>
```

This single key (API §2.4) repoints the session briefing to the GV2 snapshot
(`snapshot.read`, file-only, visible age + detached refresh warm — never a
synchronous network call) and retires every markdown-premise advisory probe
(the backlog trio `legacy-backlog-format` / `legacy-section-schema` /
`backlog-overdue-grooming` AND the norm trio `revisit-due` / `dead-why` /
`stalled-transition` — the frozen file must not generate nudges). **Do not set
it before the import has been verified** (step 4) — once set, the briefing
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
