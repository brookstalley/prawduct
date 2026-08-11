---
artifact: build-plan
version: 2
scope: v3.3.4-batch
governed_by:
  - artifact: api-contract.md   # § Direction — additive-first evolution + the harness-only-removal ruling
    dispositions:
      - "RULED (Chunk 00). The exception `[[harness-only-removal-is-not-a-major]]` carried an open
         owner question — whether it requires an inert-retention window. The owner ruled 2026-08-11
         that it does. Recorded as a further dated paragraph on the existing Rulings line plus a
         learnings entry, not as an edit to the Statement or Why: the tier permission is untouched,
         and what the ruling adds is the retention window the falsified atomic-update warrant used
         to stand in for."
      - "CONFORMS (Chunk 03). `unbuilt_at_archive:` is a new persisted frontmatter key on archived
         plans — additive-first evolution, new keys added, readers tolerate unknown keys. Absence
         means clean, so a reader that ignores it sees exactly what it sees today."
  - artifact: operational-spec.md   # § Direction — conservative versioning
    dispositions:
      - "CONFORMS. Patch tier. No new invocable surface, no gate verdict change, no repurposed flag,
         exit code or `--json` key. #636's new persisted field is the one arguable signal and it is
         ruled by api-contract's additive-first clause rather than by silence — argued in
         `release-plan-v3.3.4.md` § Why a patch."
  - artifact: nonfunctional-requirements.md   # § Direction — a control that fires and catches nothing is removed by default
    dispositions:
      - "CITED (Chunk 00, ruling 2). The direction that settles #633 toward deletion rather than a
         `test-count-lag` check. No departure — the ruling applies the norm."
lifecycle: completed
archived: 2026-08-11
released_in: v3.3.4
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

# Build Plan — v3.3.4 batch

**Scope:** `v3.3.4-batch` (five change-log scopes ship under it — see Chunk table)
**Type:** bugfix + task batch
**Size:** medium (nine files across five independent scopes)
**Critic mode:** cumulative-final
**Target release:** v3.3.4
**Branch:** `fix/v3.3.4-batch`
**Baseline:** green at the branch point; evidence tree-valid via `prawduct-hook test-status` (the
count lives in `.prawduct/.test-evidence.json`, not restated here)

## Requirements Confidence

**High for all five chunks.** Each is a defect with a named write site, a named input, and an issue
carrying its own acceptance criteria. Two of the five (#646, #638) were reproduced against real data
before any code was written; #636's input (`incompleteness_reason`) already returns the finished
sentence; #631 is a line-count target with an existing destination file.

The parent requirement for the batch is `.prawduct/artifacts/release-plan-v3.3.4.md`, which
classifies all five as shipping and records the two rulings Chunk 00 stamps.

## Correction to the release plan, taken before building

**The release plan's classification table over-populates and mis-shapes the pruned/whole-develop
decision.** `check-releasability` classifies **release-pending change-log scopes** — work already
built on `develop` and not yet tagged `release=` (`plugin/lib/release_readiness.py`
`parse_classification` + the `orphans` branch at `:496`). It does *not* classify open issues.

Two consequences, both measured rather than inferred:

1. **The six withheld rows are orphans to the gate.** None of #640, #630, #641, #642, #633, #644 is
   built on `develop`, so none has a change-log entry, so each becomes
   `classified scope(s) with nothing release-pending behind them (stale table row?)` and the gate
   exits 1. Verified against `check-releasability`'s current verdict:
   `no release-pending scopes — nothing to classify`.
2. **`K withheld` will be 0, not 6 — so the *standard* Phase 2 applies, not
   `promote-a-pruned-release.md`.** The pruned path exists for content that is on `develop` and must
   *not* reach `main`. Nothing here is in that state: after this batch, `develop`'s shippable content
   and the release's content are the same tree. The plan's "K withheld = 6" reads the withheld
   *issues* as withheld *scopes*; they are different populations.

   The one thing to re-confirm at Phase 0 rather than assume: that no *other* release-pending scope
   is sitting on `develop` from earlier work. The gate answers that, and it currently says none.

The scope cells also carry `(#NNN)` suffixes, which will not match the bare change-log `scope=`
token. Chunk 05 rewrites the table to the five shipping scopes with bare names; the prose section
*Why six issues are withheld* keeps every word of the deferral reasoning, which is where that
reasoning belongs — it is a statement about the roadmap, not about this release's partition.

## Chunks

| # | Chunk | Scope (change-log) | Issue |
|---|---|---|---|
| 00 | The two rulings, stamped where they bind | `deprecation-retention-window` | ruling 1 (#644), ruling 2 (#633) |
| 01 | The install-sha checks compare trees | `release-runbook-tree-identity` | #646 |
| 02 | `_normalize` stops minting non-words | `jurisdiction-term-normalization` | #638 |
| 03 | `archive-plan` stamps `unbuilt_at_archive:` | `archive-unbuilt-stamp` | #636 |
| 04 | CLAUDE.md back under the length it teaches | `claude-md-trim` | #631 |
| 05 | Release-plan correction + classification table | — | — |

**`check-releasability` prints five `has no build-plan file` WARNINGs against this batch, and they
are expected.** That probe resolves a change-log scope to a plan declaring the same `scope:`, which
assumes one scope per plan. This plan declares `scope: v3.3.4-batch` and describes five. The
warnings are advisory and change no exit code; the claim they make — *"work is shipping with no plan
describing it"* — is false here, and this paragraph is the record of that. Accepted rather than
worked around: renaming the plan could satisfy at most one of the five, and splitting one batch into
five plans to quiet an advisory would be the tail wagging the dog.

---

### Chunk 00: The two rulings, stamped where they bind

**Why first.** Both rulings were taken by the owner in the session that wrote the release plan, and
both currently live *only* in that plan. A ruling recorded in a release plan and nowhere else is
post-hoc paperwork the next reader never meets: the reader who next retires a hook-registered
subcommand opens `api-contract.md`, and the reader who next picks up #633 opens the issue.

**Deliverables**

- `.prawduct/artifacts/api-contract.md` § Direction — the `[[harness-only-removal-is-not-a-major]]`
  Rulings paragraph. Replace the closing sentence *"Until the owner rules, treat the tier permission
  as live and the atomic-update warrant as withdrawn"* with the ruling: the exception **requires an
  inert-retention window**. Unregistering a hook is free and immediate; deleting its subcommand
  waits until no supported install still registers it. The Statement and Why are untouched — this is
  scope added to a recorded exception, homed as case law beside the rule.
- `.prawduct/learnings.md` + `.prawduct/learnings-detail.md` — the ruling's durable home
  (`docs/norms.md`: rulings live in `learnings.md`, cross-linked from the norm). The existing entry
  is annotated, not rewritten.
- **#644** moves `stage: requirements` → `stage: ready`. Its own Scope-out names this ruling as the
  thing keeping it at `requirements`; that sentence is now satisfied and is updated to say so.
- **#633** moves `stage: research` → `stage: ready`, with the direction fixed to **delete the
  field**, and the rationale recorded on the issue: nothing reads it
  (`plugin/lib/briefing.py:172`), prawduct's own project-state carries no such key, no template
  scaffolds it, it disagrees with recorded evidence in 4 of 4 measured repos, and
  `nonfunctional-requirements.md` § Direction removes a control that catches nothing by default.

**Out of scope.** Building either #644's conformance leg or #633's `doctor`/`migrate` repair. Both
are withheld to v3.4.0; this chunk writes the rules they will be built against, nothing more.

**Done when**
- [x] The api-contract paragraph ends with a ruling, not an open question
- [x] `learnings.md` carries the ruling and links it from the existing entry
- [x] Both issues carry their new stage and the reasoning that moved them
- [x] Suite green

---

### Chunk 01: The install-sha checks compare trees, not commits (#646)

**The defect.** `main` is built by `git read-tree --reset -u origin/develop` plus a fresh commit, so
a release tag shares `develop`'s tree and never its commit identity. Two checks in
`.prawduct/runbooks/cut-and-publish-a-plugin-release.md` test commit identity:

- the `Done when` sha pair (`:696-700`) — two `echo`s that must print the same 40-char sha
- the `If this doesn't work` case-triage (`:739`) — `git merge-base --is-ancestor <installed> vX.Y.Z`

Neither can pass on a `directory:` install resolved from `develop`. The triage can only ever print
`cache holds a NON-release tree`, routing a **correct** install into case (2)/(3) and its
"delete the cache directory and restart" remedy.

**Deliverables**

- Both checks become `git rev-parse <sha>^{tree}` equality, which succeeds exactly when the cache
  holds the released content.
- The prose around them is rewritten to match: the `Done when` bullet currently says "these two print
  the same 40-character sha" and its blockquote reasons about sha identity; case (1)/(2)/(3) triage
  prose reasons about ancestry.

**The case-(3) re-measurement, done before writing** (the plan required it, and it changes nothing —
recording the result so the next reader does not redo it):

> ~~**Case (3) is real, not a phantom.** The instance survives the correct test: the cache under
> version key `3.2.4` held a tree that is not `v3.2.4`'s (`a0c2468^{tree}` `165e315f` vs
> `v3.2.4^{tree}` `fa827756`).~~
>
> **SUPERSEDED — struck, not deleted, because the error is the point.** Whole trees were still the
> wrong unit. See *the case-(3) verdict inverted* below. This paragraph is what the plan asserted
> between the first re-measurement and the Critic's R-12, and leaving it visible is what stops the
> next reader from re-deriving it.

**Two things the Critic added after the first cut, recorded because they changed the design:**

- **The unit is `git rev-parse <sha>:plugin`, not `^{tree}`.** `marketplace.json` declares
  `source: ./plugin`, so a whole-tree comparison over-fires on any post-release commit touching only
  `.prawduct/` — nearly every session.
- **The pruned runbook needed the opposite of this fix.** Copying the tree comparison there was
  itself a defect: a pruned release's `main` is deliberately unlike `develop`, so a *correct* install
  differs by construction and the comparison routes the operator into the delete-the-cache remedy.
  That runbook now states the check has no pruned equivalent — the check was **removed** there, not
  converted — and gives the one that does apply.

**And the case-(3) verdict inverted under the corrected unit.** `a0c2468:plugin` equals
`v3.2.4:plugin` (`ba3e8581`), so the instance was a false positive of *both* prior tests. The case is
marked never-observed rather than deleted.

**Out of scope.** The `UNVERIFIED` remedy banner (deleting the cache directory and re-resolving) is
still unexecuted and stays marked. This chunk fixes the detections, not the remedy's verification.

**Done when**
- [x] The whole-develop runbook's two checks compare `:plugin` subtrees; no `merge-base --is-ancestor`
      against a tag remains anywhere
- [x] The pruned runbook states the check has no equivalent on its path and offers the one that does
- [x] Case (3) prose cites the **subtree** measurement and marks the case never-observed
- [x] The `Done when` bullet's blockquote still says a mismatch grades *your machine*, not the release
- [x] Suite green

---

### Chunk 02: `_normalize` stops minting non-words (#638)

**The defect.** `plugin/lib/work_model_index.py:67` reduces only `'s` and `n't`, so every other
contraction survives whole (`you'd`, `i'll`, `they've`), and the bare-plural rule strips the `s` off
verbs (`enriches` → `enriche`). Those tokens are what `jurisdiction_candidates` (`:150`, the module's
only surviving entry point) matches on, so the defect is degraded ranking in the seeding heuristic
that suggests which norms govern a piece of work.

**Deliverables**

- `'d` / `'ll` / `'re` / `'ve` / `'m` join `'s` and `n't` as reductions to the base word.
- The bare-plural rule stops firing on verb forms — `enriches` must not become `enriche`.
- Tests that fail against the current code, in the module's existing test file.

**The ruling that does not cover this.** The 2026-07-12 #257 ruling declared precision fixes here
moot *because the code was slated for deletion*. The tripwire was deleted on
`fix/advisory-false-positives`; `_normalize` was not, because `jurisdiction_candidates` reads through
it. The ruling's premise no longer holds over this function, so it no longer covers it — recorded
here because the module docstring still describes the post-ruling footing and a reader could
reasonably read this chunk as a departure.

**Out of scope.** A real stemmer. The docstring's own constraint holds: an aggressive one collapses
distinct terms (`series` → `seri`). This stays a light, predictable reduction.

**Done when**
- [x] `you'd` / `i'll` / `they've` / `we're` / `i'm` reduce to their base word
- [x] `enriches` survives as a real word; `series`-class terms are not collapsed
- [x] Tests pin both directions and fail against the pre-change function
- [x] Suite green

---

### Chunk 03: `archive-plan` stamps `unbuilt_at_archive:` (#636)

**The defect.** A plan archived with unticked chunks is currently indistinguishable in the archive
from one that finished clean.

**Deliverables**

- `plugin/lib/plan_archive.py` — `completion_fields` / `apply_completion_frontmatter` /
  `archive_plan` learn one new key, `unbuilt_at_archive`, sourced from
  `plugin/lib/buildplan_refs.py::incompleteness_reason` over the plan's own content.
- The key joins `_KEY_ORDER` (so `_is_own_key` strips it on re-archive and the write stays
  idempotent) and `read_completion` reads it back.
- The CLI wrapper passes the plan content through; no new flag. `--dry-run` previews the stamp —
  a preview omitting a field the write makes is the mirror of the overstatement that branch was
  already fixed for.
- **A type gate, added after running it:** the stamp asks `plan_index.is_build_plan` first. Without
  it the "no readable roster" sentence lands on every *release plan* at every cut — a document with
  no roster by design. Fails safe toward *is a plan* (no declared `artifact:` type is still stamped).
  `is_build_plan` is the new public spelling of `plan_index._declares_non_build_plan_artifact`.

**The contract.** Absence means **clean**, not unknown. That is what makes this additive rather than
a format break: a reader that ignores the field sees exactly what it sees today.

**The one care point.** `incompleteness_reason` has three states, and the middle one is not the
interesting one. *No readable Status roster* returns a refusal sentence rather than `None` — an
unparseable plan is not evidence of completion. That sentence must be stamped too: filing an
unreadable plan as clean is the exact silent-completion failure the function was written to prevent.

**Out of scope.** The automatic `plan-backfill` sweep — already gated by #634. This touches only the
explicit route. How incompleteness is *detected* is unchanged.

**Done when**
- [x] Explicit `archive-plan` of a plan with unticked chunks writes `unbuilt_at_archive:` naming the
      chunk(s) that stopped it
- [x] A complete plan archives with no such field
- [x] A plan with no readable Status roster is stamped, not silently filed clean
- [x] Re-archiving neither duplicates nor drifts the field
- [x] Suite green

---

### Chunk 04: CLAUDE.md back under the length it teaches (#631)

**The defect.** 191 lines, always-loaded, against the ~150 the methodology teaches
(`plugin/methodology/building.md:83`) — every line is paid every session, and some of it restates
`documentation/project-structure.md` rather than pointing at it.

**Deliverables**

- The architecture description and component inventory move to
  `documentation/project-structure.md`, which already owns that subject. CLAUDE.md points at it.
- **That file's framework half had to be repaired first** (Critic R-9). Delegating made it
  load-bearing, and its tree still showed `bin/`, `lib/`, `skills/`, `methodology/`, `templates/`,
  `hooks/` and `VERSION` at the repo root — all under `plugin/` since the cutover — plus a
  `docs/principles.md` that does not exist and a claim that `tools/` was retired while a tracked
  file lives there. A pointer is only as good as its target; handing a session wrong paths for the
  most-read files in the repo is worse than the duplication it replaced.
- Nothing that moves is deleted.
- The principles roster and the governance anchor stay — those are what make the file load-bearing.

**Out of scope.** The session digest's own budget (#630, withheld), and the principles roster.

**Done when**
- [x] Project-specific content at or under ~150 lines
- [x] Every moved paragraph lands in a file that already owns that subject
- [x] The always-injected session digest still covers everything a product session needs
- [x] `tests/test_plugin_methodology_digest.py` green (unchanged — this batch adds nothing to the digest)
- [x] Suite green

---

### Chunk 05: Release-plan correction + classification table

**Deliverables**

- `release-plan-v3.3.4.md` § Release classification — five rows, bare change-log scope names, all
  `ships`. The six withheld issues leave the table and stay in the prose, where the deferral
  reasoning already lives and belongs.
- The *Verification* section's `K withheld = 6` line is corrected to what the gate will actually
  report, with the reason (the two populations are different) stated once so the next release plan
  does not repeat it.
- The classification-table population rule is recorded where a plan author meets it — the release
  runbook's Phase 0, not only here.

**Done when**
- [x] `check-releasability --release v3.3.4` exits 0, reporting 5 shipping / 0 withheld
- [x] The withheld-issue reasoning survives verbatim in prose
- [x] Suite green

## Status

- [x] Chunk 00: The two rulings, stamped where they bind
- [x] Chunk 01: The install-sha checks compare trees, not commits
- [x] Chunk 02: `_normalize` stops minting non-words
- [x] Chunk 03: `archive-plan` stamps `unbuilt_at_archive:`
- [x] Chunk 04: CLAUDE.md back under the length it teaches
- [x] Chunk 05: Release-plan correction + classification table

## Context

Branch `fix/v3.3.4-batch` off `develop`. Five independent scopes; no
chunk depends on another's output, so ordering is by risk (governance first, docs last) rather than
by dependency. The release itself — version bump, `release=` tagging, promotion — follows
`cut-and-publish-a-plugin-release.md` **standard Phase 2** after this plan closes, per the
correction recorded above.
