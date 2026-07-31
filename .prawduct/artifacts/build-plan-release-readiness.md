---
scope: release-readiness
item: REL-8P6M
depends_on:
  - .prawduct/runbooks/cut-and-publish-a-plugin-release.md
governed_by:
  - .prawduct/artifacts/operational-spec.md        # ## Direction — versioning norm, promotion norm
  - .prawduct/artifacts/api-contract.md            # exit-code error model for a new CLI subcommand
  - .prawduct/artifacts/data-model.md              # backlog_service_repo authority over backlog.md
  - .prawduct/artifacts/project-preferences.md     # merge strategy, attribution
requirements_confidence: High
---

# Build plan — release readiness (REL-8P6M, parts a–d and f)

## Requirements Confidence: High

**Problem.** `cut-and-publish-a-plugin-release.md` can publish work that is not fit to ship. Its
only precondition is *"is there anything unreleased?"* (`git diff --stat origin/main origin/develop`
non-empty), never *"is everything on `develop` fit to ship?"*. On v3.1.2 those diverged: following
Phase 2 literally would have published the backlog-service subsystem with all four go-live blockers
open — an unrecallable publish, since consumers re-resolve `main` at next session start.

**Success.** A release cannot proceed while any release-pending scope is unclassified, and the
pruned-promotion shape this repo has now used twice is a first-class documented path rather than
ad-hoc knowledge in an expiring release plan.

**Out of scope.** Part **(e)** — the Phase 1 change-log sweep selection-rule rewrite — is
**deliberately held** (owner decision, 2026-07-29): the change-log ledger proposal
(`change-log-ledger-design.md`) would delete that machinery, so rewriting it now is throwaway work.
That decision was taken 2026-07-31 — **GO on the design, HOLD on the schedule** (`change-log-ledger-design.md`
§11.7) — so the hold survives the trigger and only its bound moved: it now runs until the ledger plan is
scheduled and shipped. This release tags its shipping subset by hand, once. See Chunk 03. `REL-7D4X`
stays open with it.

## Open assumptions

- `[ASSUMPTION: the releasability classification lives in the per-release plan artifact
  (.prawduct/artifacts/release-plan-<version>.md), the artifact type this repo already writes per
  release, rather than a new file type or a backlog marker | MED impact | user can correct — the
  alternative is REL-8P6M's suggested `release-gated:` backlog marker, which spreads the decision
  across N items instead of concentrating it in one reviewable table]`
- `[ASSUMPTION: the gate blocks (exit 1) rather than warning. Publishing is irreversible and the
  failure it prevents is fleet-wide, so fail-closed is the proportionate posture | HIGH | user can
  override to advisory]`
- `[ASSUMPTION: "unreleased scope" means a tagged change-log entry carrying no `release=`, which is
  what `release_readiness.release_pending_scopes` enumerates. NOT `views.collect_release_pending_scopes`, which also includes `status=shipped` scopes so `regen-views` can flip plans regardless of convention — releasability needs the strictly narrower "no `release=` tag" set | LOW]`

## Governing norms — reconciliation

`operational-spec.md` § Direction, versioning norm — *"Versioning is conservative: a small feature is
a patch bump, not a minor-per-feature."* → **inapplicable to this plan**: nothing here changes how a
version number is chosen. Recorded rather than assumed, since the runbook this plan edits quotes the
norm at length and an editor could easily disturb it. **Chunk 02 must leave the norm block at
runbook lines 49–67 byte-identical.**

`api-contract.md` — *recorded decision `api_error_model_approach`: exit codes are the contract, on a
documented scheme.* → **conforms.** Chunk 01 changed the usage-error path from exit 1 to **exit 2**
specifically to stop colliding with the gate's own `not-releasable` code, which is that norm applied,
not vocabulary overlap — so the artifact genuinely governs and its Operations list now names
`check-releasability`. (Corrected: the first pass waived this as incidental overlap while the bundle
was in fact conforming to it.)

`data-model.md` — *once `backlog_service_repo` is set, `backlog.md` is frozen history and no reader
treats it as live.* → **conforms, after a correction.** The first implementation read the markdown
unconditionally; post-cutover that certifies a closed blocker as open. Now gated, failing closed.

`project-preferences.md` — merge-commit strategy and no-attribution-trailers: **conforms**.

---

## Chunk 01 — the releasability gate (part f)

**Type:** `code` · **Critic mode:** inferred (`chunk`)

The highest-value half of REL-8P6M. Phase 1 gains a precondition it has never had.

**Deliverable:** `prawduct-hook check-releasability [--release vX.Y.Z]`.

Behaviour — every release-pending scope must be classified, nothing unclassified:

1. Enumerate release-pending scopes via `release_readiness.release_pending_scopes` — entries
   carrying no `release=` tag. Deliberately a second, narrower definition than
   `views.collect_release_pending_scopes`; the docstring records why.
2. Read the classification table from `.prawduct/artifacts/release-plan-<version>.md` (new file per
   release; resolved from `--release`, else the version in `plugin/VERSION`).
3. Each release-pending scope must appear exactly once, classified `ships` **or**
   `withheld: <ITEM-ID>` naming an **open** backlog item.
4. Exit 1 naming every unclassified scope, every withheld scope whose blocker is not open (a
   withholding reason that has since shipped is a stale decision, not a valid one), and every
   classified scope that is not release-pending (a table entry with nothing behind it).
5. Exit 0 prints the partition: N scopes, M shipping, K withheld.

**Why a blocker must be *open*:** the withholding decision's justification is the blocker. If it
closed, the reason to withhold evaporated and the decision needs re-taking — silently shipping on a
stale withholding is the same class of error as silently withholding on a stale one.

**Done when:**
1. `tests/test_release_readiness.py` covers: all-classified passes; an unclassified scope blocks and
   is named; a withheld scope with a closed blocker blocks; a table entry with no release-pending
   scope blocks; a missing release-plan file blocks with an actionable message (never passes open);
   empty release-pending set passes.
2. A mutation check on the partition logic — flipping the unclassified test to a subset comparison
   must fail a test (the W-1 lesson: a gate whose firing path is untested ships green).
3. `./plugin/bin/prawduct-hook check-releasability --release v3.2.0` runs and reports **correctly**
   against this repo's real state — which at this commit means **red**, and that is the criterion.
   A green run is impossible before the release: it requires `release-plan-v3.2.0.md` with a
   classification table, which the v3.2.0 release itself authors. The structural reason is worth
   recording, because it also shaped the fallback's behaviour: the runbook bumps `plugin/VERSION` in
   **Phase 1 step 7**, *after* Phase 0 runs, so a `VERSION`-derived version always names the
   *previous* release at gate time. `--release` is therefore authoritative, and the fallback says so
   on stderr rather than silently grading the wrong release.
4. Runbook: new **Phase 0 — Releasability** ahead of Phase 1, with the command, expected output, and
   the "if not" branch.
5. `/prawduct:critic`, findings resolved.

## Chunk 02 — pruned-promotion path (parts a, b, c, d)

**Type:** `doc-only` · **Critic mode:** `final`

Phase 2 as written promotes by making `main` a *copy* of `develop` (`git read-tree --reset -u
origin/develop`, step 15) and asserts content-identity (step 17). Both are true only for a
whole-`develop` promotion. This repo has done a **pruned** promotion twice.

**Deliverable:** a **Phase 2-alternate — pruned promotion**, selected by Phase 0's output, covering:

- **(a) Build the candidate** as `<prev-tag>` plus `git diff <cut-point>..develop` applied with
  `--3way` — not a tree reset.
- **(b) Publish by ref** — `git push origin <sha>:refs/heads/main`, replacing `git checkout main`
  (step 14) and `git push origin main` (step 19). Safer generally, and *necessary* here: `main` is
  checked out in a sibling worktree, where `git checkout main` cannot run at all.
- **(c) Partition check replacing step 17.** Content-identity is meaningless for a pruned release.
  The correct assertion is that every path in `origin/main..origin/develop` is accounted for as
  either shipped or deliberately withheld, nothing unclassified — the same discipline as Chunk 01's
  scope partition, one level down at paths instead of scopes.
- **(d) Suite on the candidate tree + per-file import diff, mandatory before publish.** On the
  v3.1.2 candidate a *clean* `git apply` produced a `NameError` in a shipped path and 11 failing
  tests. "The patch applied without conflict" is not evidence of a correct tree.

**Constraint:** Phase 2 (whole-develop) stays intact and correct — this **adds** a path, it does not
replace one. The reader is routed between them explicitly.

`[DECISION: the alternate lives in its own runbook, .prawduct/runbooks/promote-a-pruned-release.md,
rather than as a Phase 2-alternate section inside the existing file | the runbook budget in
docs/runbook-authoring.md is ≤20 steps per document and says "more than that, split it and give each
part its own entry condition"; the release runbook already stands at 21 (steps 0–20) and the pruned
path needs ~14 more, which would land a 30-step document where a third of the steps never apply to
the reader executing it — the guide names that dilution as its single most strongly evidenced failure
mode. The split also gives each shape an honest `Done when`, which Done-when item 2 requires and
which one shared section cannot provide | user can veto — the alternative is one long document]`

> **Norm amended — Chunk 02 is unblocked.** `operational-spec.md` § Direction's gitflow promotion
> norm bound promotion to a *content-identical tree-set*, which parts (a)/(b)/(c) replace. Raised as
> a blocking precondition (Critic `rev-20260729T170856Z-8a025aec`) rather than edited quietly, and
> **amended 2026-07-29 by owner ruling** with the decision recorded in the norm itself.
>
> The amendment engages the norm's own *why* rather than overriding it: the stated purpose is that a
> release must not **ship integration WIP**, and content-identity *forces* precisely that whenever
> `develop` holds unready work — the mechanism contradicted its own rationale, and prawduct had
> already departed from it twice (v3.1.1, v3.1.2) with nothing recorded. The binding property is now
> the **partition** — every path shipped or withheld, nothing unaccounted — with content-identity as
> its special case when nothing is withheld. Chunk 02's part (c) is that norm's enforcement, which is
> the inverse of laundering: the code conforms to the amended norm, and the norm is stricter about
> what it actually cares about.

**Done when:**
1. Both promotion shapes documented, with an explicit selection step naming which to use.
2. The `## Done when` section is split per shape — today's content-identity assertion is **false**
   for a pruned release and must not be the universal completion test.
3. Runbook lines 49–67 (the ratified versioning norm block) byte-identical — `git diff` confirms.
4. `.prawduct/artifacts/release-plan-v3.1.2-pruned.md` referenced as the worked example, not
   duplicated (an expiring artifact is not a durable surface — that is REL-8P6M's own reasoning).
5. `last_verified:` stays `null` — this plan does not exercise the runbook end-to-end.
   ~~v3.2.0's actual run is what verifies it.~~ **Corrected 2026-07-29 (PR reviewer, W-2): naming a
   version as the verifier was the wrong shape.** The owner's standing intent is to ship v3.2.0
   *non-pruned*; on that plan its run takes Phase 2's whole-develop path and never opens
   `promote-a-pruned-release.md`, so the trigger would never fire. Note the confidence boundary: that
   is a **plan, not a structural fact** — it rests on an owner decision recorded only in session
   handoff notes (untracked), and if v3.2.0 ends up withholding any scope it *is* a pruned release and
   the original trigger fires after all. Either way the defect is the same: a *version* is the wrong
   kind of trigger for a *promotion shape*. Nothing else tracked the gap either — REL-8P6M archives
   `shipped`, and `last_verified` turns out to have **no code reader at all** (its only consumer is a
   model-side review question in `skills/runbook/SKILL.md`), so it is an unread field rather than a
   missing advisory. The trigger is now stated as a shape — **the next pruned release, whenever one
   occurs** — tracked as `REL-3K9P`. What *was* exercised: the command set was rehearsed by rebuilding
   the real v3.1.2 candidate, reproducing its three conflicts and catching a missing `import sys`, so
   the unverified remainder is the *publish* half, not the procedure.
6. **`documentation/release-process.md` carries the amended promotion norm.** Chunk 01 corrected its
   two universal content-identity assertions, but that file is a *second active procedure* and this
   chunk adds a whole promotion shape to it — it is in scope here, not incidentally. A norm amendment
   whose cascade stops at one of two procedures has not landed (Principle 13).
7. `/prawduct:critic`, findings resolved.

## Chunk 03 — the (e) stopgap and the W-1 note

**Type:** `doc-only` · **Critic mode:** inferred

Part (e) is held, so the sweep keeps its positional selection rule — but the *reader* must not be
misled by it twice more.

**Deliverable:**
1. Extend Phase 1 step **2**'s existing REL-7D4X warning with the **scope** dimension (W-1, found by
   the PR reviewer on `feature/v3.2.0-c02-adapter-safety`): the re-derivation instruction
   `re-grep scope=v3.2.0-golive` sees one scope, while a release bundle routinely spans several. On
   v3.2.0 exactly this misses **16 statusless entries across five other scopes** (measured on this
   branch @ `1a353d1`: 23 release-pending across six scopes, of which `v3.2.0-golive` is 7).
   *(Corrections made while building: the warning is attached to step **2**, not step 3, since that
   is where the derivation rule lives; and the figure was wrong twice — filed as 8, "corrected" to 9
   by recounting only the four scopes the finding already named, which is the same scope-narrowing
   the finding is about. The runbook now carries the derivation command instead of a fixed number.)*
2. State that the consumer-facing note list must be derived from **all** shipping scopes — the
   `protected_path_violation` widening is fleet-visible and would have been omitted.
3. A pointer to `change-log-ledger-design.md` recording *why* (e) is held, so the next reader does
   not "fix" the sweep in ignorance of the pending decision.

**Done when:**
1. The warning names the scope dimension and the four scopes, with the count, and points the reader
   at Phase 0's already-computed list rather than at a fresh grep.
2. `REL-8P6M` updated via `/prawduct:backlog` — parts a/b/c/d/f closed, **(e) explicitly retained**
   with its trigger, so archiving the item does not silently drop it.
3. `/prawduct:critic`, findings resolved.

---

## Status

<!-- Derived view — regen-views owns this section. Do not hand-edit. -->

- [x] Chunk 01: releasability gate (f)
- [x] Chunk 02: pruned-promotion path (a, b, c, d)
- [x] Chunk 03: (e) stopgap and W-1 note
