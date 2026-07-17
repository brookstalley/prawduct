# Migration scrub — markdown backlog → GitHub Issues (MG4)

The one-time, owner-confirmed cleanup that runs when a project moves its
`.prawduct/backlog.md` onto GitHub Issues through the backlog service
(`prawduct-hook backlog <op>`). It surfaces stale and duplicate items *before*
they become live issues, so the migrated backlog starts clean instead of
inheriting years of silt.

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

**3. Apply the confirmed plan — deterministically.**
   - **Import** the source into issues (idempotent/resumable, keyed on the
     `id:PFX` alias, so a re-run never duplicates):
     `prawduct-hook backlog import --repo <owner/repo> --from .prawduct/backlog.md [--archive <archive>]`
   - **Fold each duplicate** into its survivor (writes the `superseded-by:`
     redirect *before* closing the source, so a crash leaves a resolvable
     open-but-redirected item, never an orphan — AU3/CRASH-2):
     `prawduct-hook backlog merge <duplicate-id> --into <survivor-id>`
   - **Close each stale item** (closed + preserved, not deleted):
     `prawduct-hook backlog status <id> --to dropped`

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

## What must never happen

- A mutating op run on an item the owner did not confirm.
- An item removed from the source with no corresponding closed issue (a silent
  drop).
- A hard delete — the service never deletes issues (GitHub does not reuse
  numbers; disposal is always close/redirect).
- A model call inside `import`/`merge`/`status` — the decision happens upstream,
  in this workflow, as confirmed data.
