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

**Precondition. Confirm the running plugin actually HAS the backlog service — before anything else.**
Every command in this runbook is written as a bare `prawduct-hook backlog …`, which resolves on
`PATH`. **On a released plugin that resolves to a binary with no `backlog` op at all**, because the
backlog service was deliberately withheld from the v3.1.1 and v3.1.2 pruned releases. The failure is
loud (`unknown op`), but the *diagnosis* is not obvious mid-migration, and the same skew is silent in
the more dangerous direction: a build that has the op but predates this runbook's safety rails will
run happily and skip the target-binding this runbook exists to enforce.

   - **Check first, in the repo you are about to migrate:**

         prawduct-hook backlog        # must print the backlog usage, not `unknown op`
         prawduct-hook version        # note it — you will record this

   - **If it prints `unknown op`, or a version older than the one that shipped the service**, stop and
     re-launch the session against a plugin build that carries it:

         claude <target-repo> --plugin-dir /path/to/prawduct/plugin

     There is no `.prawduct/tools/prawduct-hook` to fall back to — that was the **v1 file-sync**
     layout, retired in M4. A plugin-governed repo commits the install reference and no framework
     files, so the *only* lever is which plugin the session loaded.

   - **Record the plugin version and `--plugin-dir` (if used) alongside the other scrub decisions.**
     Not bookkeeping: when a migration is later found to be incomplete, the first question is *which
     build ran it*, and a repo that cannot answer that cannot be diagnosed. This is not hypothetical —
     `samsung-frame-art-loader` was found half-migrated (7 of 9 items never reached GitHub, with the
     cutover already recorded) and nothing in the repo records which build performed it.

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

**1b. Fix any id that is not a valid PFX — before the import, not after.**
The accepted shape is deliberately lenient (`ids._PFX_RE` — a letter-led segment
followed by one or more `-`-joined alphanumeric segments: `BKL-7M4Q`,
`ARR-FROMBUILD`, `ADR-12`, `A-1`, `MIG-M4-REMOVE`, `AUD-TIMBRE-CALIB` all pass).
Multi-segment ids are ordinary, not exotic — about a fifth of real backlogs carry
one — so they are absorbed rather than rejected.

What still fails, and is what this step hunts:

- **No marker at all** — a bullet with no `[...]`. The most common residual case.
- **No hyphen** — `[TODO]`, `[BKL]`.
- **Not letter-led** — `[2026-07-28]`, `[-1234]`. Deliberate: it keeps a bracketed
  date from being adopted as an id.
- **Anything but letters, digits and single interior hyphens** — `[FOO_BAR]`,
  `[FOO.BAR]`, `[a b-1]`, `[FOO-]`, `[FOO--BAR]`.

Such an item cannot carry an `id:PFX` alias, so nothing can key it back to the
source. It still imports — under an idempotency-only `import-key:<digest>` marker,
so it neither duplicates nor strands — but it has no permanent identity, every
`related:` reference to it dangles once the markdown is frozen, and step 6's gate
blocks the cutover on it.

**This is cheap now and expensive later**: the digest is over title+body, and
giving the item a real PFX changes both the key and the title, so renaming it
*after* an import and re-importing mints a **second** issue rather than adopting
the first. Rename here, and update every `related:` that names the old id.

Find the marked ones — the inverse of the same shape the parser applies. Rewrite
each hit's marker to a freshly minted PFX for its area:

```sh
grep -nE '^- \*\*\[[^]]+\]\*\*' .prawduct/backlog.md \
  | grep -vE '\[[A-Za-z][A-Za-z0-9]*(-[A-Za-z0-9]+)+\]'
```

**That grep is a first pass, not the whole step** — it only inspects bullets whose
marker is **bold** (`- **[…]**`), so a markerless bullet and a valid-but-unbolded
one (`- [A-1] one` parses fine) both escape it. This second pass takes every
column-0 bullet and flags any that does not *begin* with a well-formed marker,
bolded or not — so it catches the markerless class the first grep cannot see:

```sh
grep -nE '^- ' .prawduct/backlog.md \
  | grep -vE '^[0-9]+:- (\*\*)?\[[A-Za-z][A-Za-z0-9]*(-[A-Za-z0-9]+)+\](\*\*)?'
```

It over-flags slightly by design — the parser finds a marker anywhere in the title
and skips fenced code blocks, while this is anchored and literal. Over-flagging is
the safe direction for a step whose output a human reads. **`verify-migration`
(step 6) is the authority**; these two greps only make the fixes cheap while they
are still renames.

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
     transport *method* call against a 900-points/minute window (5 per write, 1 per
     read), so the close is inside the meter alongside the create. The charge is per
     method, not per HTTP request — a paged read issues several requests and is
     charged once — so the reported point total is a **floor**, not an exact REST
     count, and the run summary prints `≥N` (BKL-3H7W). *(Corrected
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

     **Read the line after the summary before moving on.** A status reconcile that
     fails for a non-rate-limit reason does not stop the run — the item is created
     and left at the wrong status — so the counts can read as a clean import while
     work remains. When that happens the import prints
     `WARNING: N item(s) imported but NOT reconciled to their target status`.
     **Re-run the import** (it reconciles the status axis on already-migrated items,
     so this converges) until the line is gone. Step 6's `status_mismatch` is the
     backstop if you miss it, not a substitute for reading it here.
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

**6. Cut over.** **Gate first — this is the one step that must not be taken on
trust.** Setting the key below is what makes the markdown stop being read, so
any item that did not make it across becomes invisible *at the moment you record
the cutover*. Run:

    prawduct-hook backlog verify-migration --repo <target> \
      --from .prawduct/backlog.md [--archive <archive>] [--archive-scope all|open]

**Exit 0 — `missing`, `unaliasable`, `collisions`, `status_mismatch` and
`duplicate_alias` all empty — is the precondition for the rest of this step.** Do
**not** record the key while any is non-empty. Exit 4 names the items, and the
five lists have different remedies — **re-running the import is the right answer
for only two of them**:

- **`missing`** — source items with no issue on the target. Re-run the import
  (idempotent, alias-keyed, so already-migrated items skip rather than
  duplicate) and verify again.
- **`unaliasable`** — items whose id is not a valid PFX (step 1b), so no alias
  can key them. **Do not just re-run the import**: their idempotency key is a
  digest of title+body, so renaming one to a real PFX changes the key and mints
  a *second* issue rather than adopting the existing one. **The only fix is in
  the source markdown**: rename, re-import, close the duplicate. Nothing done to
  the target issue can clear this list — the gate derives `unaliasable` from
  parsing the source alone and never inspects the target for it, so hand-adding
  an `id:PFX` label to the created issue leaves the exit-4 unchanged.
- **`collisions`** — two source items claim the same PFX. The import drops the
  second rather than merging two items onto one alias, so it was never created
  and re-running will not create it. Give each a distinct PFX in the source,
  then re-import.
- **`status_mismatch`** — the item is on the target and correctly keyed, but at
  the **wrong status**: its issue exists, so it is not `missing`, yet a status
  reconcile never landed. The import defers a failed reconcile so a long run can
  continue (it reports them in `status_unreconciled`), and under
  `--archive-scope all` a rate-limited close stretch can leave every archived
  item sitting open. Same remedy as `missing` — re-run the import, which
  reconciles the status axis on already-migrated items too — and verify again.
- **`duplicate_alias`** — **two issues on the target** record the same id in their
  body block and their statuses disagree, so nothing can decide which is
  authoritative. It looks like `status_mismatch` and behaves like `collisions`:
  **do not re-run the import.** A re-run writes to neither issue — the one carrying
  the `id:PFX` label already matches, and the block-only one is never looked up —
  so it burns a full pass and returns the identical exit 4. Find the pair by
  searching the target for the id, fold one into the other
  (`merge <duplicate-id> --into <survivor-id>`), then verify again.

`source_items` counts **every** parsed item in scope, not just the aliasable
ones — so `source_items` exceeding `aliased` with an empty `missing` is exactly
the `unaliasable`/`collisions` case, not an arithmetic error. The converse does
**not** mean you are clear: `status_mismatch` counts items that ARE keyed, so
`source_items` equalling `aliased` and still exiting 4 is the expected reading
for that list, not a contradiction. Read the four lists, not the arithmetic.

**Pass the same `--archive-scope` you imported with.** The gate derives its
source set through the importer's own record assembly, so `open` verifies against
what `open` actually creates — the closed items it skips stay in the git-tracked
source markdown and are correctly not counted as stranded. Passing a different
scope than you imported with compares against the wrong set.

*Why this is a command and not the eyeball check step 5 already asks for.* Step 5
has always said "Total issue count = every source item," and it was not enough:
`samsung-frame-art-loader` recorded its cutover with **7 of 9 items never
imported**, and nothing noticed until the repo was read months later. A raw issue
count would not have caught it either — issues filed natively after a cutover
carry a `prawduct` block but no `id:PFX` alias, so that repo's counts looked
plausible (17 issues) while 7 source items were stranded. The gate compares the
**source set against alias coverage**, which is the only comparison that holds —
and then, because coverage alone still cannot see an item that arrived at the
wrong status, compares each covered item's **decoded status** against the
source's target.

Then record the switch that makes the migrated repo the live backlog — a
top-level scalar in `.prawduct/project-state.yaml`, set to the same `<target>`
bound in Step 0:

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
history for *this* repo.

**`legacy.py` is NOT retired at this cutover — not this repo's, not any repo's.**
It is the shared plugin's markdown read path, and `GV7`/`MG3` retire it only when
the **whole portfolio** has migrated: retiring it at one project's cutover is the
silent degradation GV7 exists to prevent, and it would also disable the *next*
repo's migration, since `lib/backlog/migrate.py` reads the source through
`legacy.parse_backlog`.
Portfolio-wide retirement is not this runbook's business.

`incoming-bugs/` is different: it retires **in lockstep with its MG5 replacement**,
never before it (BKL-0QR1) — and that leg is **gated by BKL-9XQ2**, so it does not
run here either. Everything else in this runbook is unaffected by that gate.

## What must never happen

- A mutating op run on an item the owner did not confirm.
- An item removed from the source with no corresponding closed issue (a silent
  drop).
- A hard delete — the service never deletes issues (GitHub does not reuse
  numbers; disposal is always close/redirect).
- A model call inside `import`/`merge`/`status` — the decision happens upstream,
  in this workflow, as confirmed data.
