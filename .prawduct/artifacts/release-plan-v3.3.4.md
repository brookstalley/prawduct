---
artifact: release-plan
version: 1
release: v3.3.4
last_validated: 2026-08-11
---

# Release plan — v3.3.4

A patch release carrying four independent small fixes, derived from a review of the ten most
recent open issues. Four scopes ship; six issues from that same review are withheld to v3.4.0
with named blockers.

## Release classification

| Scope | Disposition | Blocker |
|---|---|---|
| deprecation-retention-window | ships | |
| release-runbook-tree-identity | ships | |
| jurisdiction-term-normalization | ships | |
| archive-unbuilt-stamp | ships | |
| claude-md-trim | ships | |

**Owner decision 2026-08-11: two cuts, not one.** Requested in-session after the ten-issue review —
the four small fixes have no gate semantics and no new capability between them, and making them
wait on the #640 → #641 dependency chain buys nothing. Six issues stay behind; *Why six issues are
withheld* below is that decision's record, and it is prose rather than table rows for the reason in
the next paragraph.

**Correction, 2026-08-11 — this table classifies scopes, not issues, and `K withheld` is 0.**
The first draft carried ten rows, six of them `withheld`, and read `K withheld = 6` as routing the
release to `promote-a-pruned-release.md`. Both were wrong, and the same confusion produced both.

`check-releasability` classifies **release-pending change-log scopes** — work that is *built on
`develop`* and not yet tagged `release=`. The six withheld items are open **issues**: unbuilt, so
they have no change-log entry, so the gate sees nothing behind their rows and reports them as
`classified scope(s) with nothing release-pending behind them (stale table row?)` and exits 1
(`plugin/lib/release_readiness.py`, the `orphans` branch). The row names also carried `(#NNN)`
suffixes, which cannot match a bare `scope=` token. Ten rows would have blocked the release rather
than described it.

**The promotion path follows from the same fact.** The pruned path exists for content sitting on
`develop` that must *not* reach `main`. Nothing here is in that state — after this batch, `develop`'s
shippable content and the release's content are the same tree — so this is a **standard Phase 2
whole-develop promotion**, not a pruned one. A deferred issue is not withheld content; it is content
that was never written.

*Recorded rather than silently fixed because the mistake is re-makeable: "six things aren't shipping"
is true in English and false in the gate's vocabulary, and the next release plan will be written by
someone who has just made the same decision.*

## Rulings taken 2026-08-11

Both were open questions blocking issues in the withheld set. Both were put to the owner during
this review and answered. They are recorded here so the decision survives the session; **stamping
them into their owning artifacts is work item 0 of this release**, not an optional follow-up.

**Both are stamped — that is the `deprecation-retention-window` scope in the table above.** It ships
as a fifth scope rather than as unrecorded prep: the ruling changes what `api-contract.md` § Direction
permits, and a normative change that reaches consumers through the next release belongs in the
release's own partition, not beside it.

1. **The harness-only-removal exception requires an inert-retention window.** Unregistering a hook
   is free and immediate; deleting its subcommand waits until no supported install still registers
   it. This ratifies the reading v3.3.3 restored both commands under — that release was the repair,
   and this is the ratification it explicitly said it lacked. Stamp site:
   `api-contract.md` § Direction, the open paragraph at lines 90–97 (which currently ends "Until the
   owner rules, treat the tier permission as live and the atomic-update warrant as withdrawn").
   The tier permission is untouched; what the ruling adds is the retention window that the falsified
   atomic-update warrant used to stand in for. This is what unblocks **#644** from
   `stage: requirements` — the rule its conformance leg checks against is now fully written.

2. **`test_tracking.test_count` is deleted, not checked.** Nothing reads it
   (`plugin/lib/briefing.py:172` says so outright), prawduct's own project-state carries no such
   key, no template scaffolds it, and it disagrees with recorded `.test-evidence.json` counts in
   4 of 4 measured repos. `nonfunctional-requirements.md` § Direction — *a control that fires and
   catches nothing is removed by default* — points the same way, and a check would institutionalize
   maintaining a number nobody reads (discodon's provenance comment for it has reached ~36KB on a
   single YAML line). Stamp site: **#633** itself, which moves from `stage: research` to
   `stage: ready` with the direction fixed.

## What ships

**The two rulings, stamped where they bind** (`deprecation-retention-window`). Recorded above,
written into `api-contract.md` § Direction, `learnings.md` / `learnings-detail.md` and the two
issues. See *Rulings taken 2026-08-11*; this entry exists so the section and the classification
table enumerate the same five things.

**`#646` — the install-sha checks compare trees, not commits.** `main` is built by
`git read-tree --reset -u origin/develop` plus a fresh commit, so a release tag shares `develop`'s
tree but never its commit identity. Both checks in
`.prawduct/runbooks/cut-and-publish-a-plugin-release.md` — the `Done when` sha pair at `:696-700`
and the `merge-base --is-ancestor` case-triage at `:739` — test commit identity, so **neither can
ever pass** on a `directory:` install resolved from `develop`. The triage can only print "cache
holds a NON-release tree", routing a *correct* install into case (2)/(3) and its
"delete the cache directory and restart" remedy. Both become
`git rev-parse <sha>^{tree}` equality, which succeeds exactly when the cache holds the released
content — the thing the checks were written to establish.

**Case (3) was re-triaged, and it is real — measured 2026-08-11.** Its one instance
(`plugins/cache/prawduct/prawduct/3.2.4` at `a0c2468`) had been diagnosed *by* the ancestry test this
scope removes, so it could have been that test's false positive. It is not: `a0c2468^{tree}` is
`165e315f` against `v3.2.4^{tree}` `fa827756` — different trees, so the cache under a release's
version key genuinely held non-release content (`a0c2468` is dated 2026-08-04, on `develop`, after
the cut). The case carries forward with its prose rewritten to cite the tree measurement, not the
ancestry one. The wrong move would have been swapping the test and leaving the prose.

**The same defect is in `promote-a-pruned-release.md` and ships fixed there too.** The issue named
one runbook; the check is duplicated in the pruned-promotion sibling, where the disjoint history is
even more pronounced. Fixing one would have left the next pruned release with the identical false
alarm — in-scope by the *fix, not file* preference, since it is the same defect in the same class of
file.

**`#638` — `_normalize` stops minting non-words.** `plugin/lib/work_model_index.py:67` reduces only
`'s` and `n't`, so every other contraction survives whole (`you'd`, `i'll`, `they've`), and the
bare-plural rule strips the `s` off verbs (`enriches` → `enriche`). Those tokens are what
`jurisdiction_candidates` (`:150`, the module's only surviving entry point) matches on, so the
defect is degraded ranking in the seeding heuristic that suggests which norms govern a piece of
work. `'d`/`'ll`/`'re`/`'ve`/`'m` join the reductions; the plural rule stops firing on verb forms.

The 2026-07-12 #257 ruling declared precision fixes here moot *because the code was slated for
deletion*. The tripwire was deleted on `fix/advisory-false-positives`; `_normalize` was not, because
`jurisdiction_candidates` reads through it. The ruling's premise no longer holds over this function,
so it no longer covers it.

**`#636` — explicit `archive-plan` stamps `unbuilt_at_archive:`.** A plan archived with unticked
chunks is currently indistinguishable in the archive from one that finished clean. The write site is
`plugin/lib/plan_archive.py::archive_plan`, which already stamps frontmatter, and the input already
exists: `plugin/lib/buildplan_refs.py::incompleteness_reason` returns the finished sentence.
Absence of the field means clean, not unknown. Idempotent — re-archiving neither duplicates nor
drifts it. Touches only the explicit route; the automatic `plan-backfill` sweep is out of scope and
already gated by #634.

**One thing the design did not anticipate, found by running it.** `archive-plan` archives whatever
it is pointed at, and `incompleteness_reason` answers *"no readable `## Status` roster"* for a
document that has no roster — which is every **release plan**, by design. A live dry-run against
this repo's own artifacts showed the stamp about to land on `release-plan-v3.3.4.md` itself, and it
would have done so on every release forever. The stamp now asks `plan_index.is_build_plan` first
(failing safe toward *is a plan*: a document declaring no `artifact:` type is still stamped, because
at least one real plan here declares none). This is the norm cited two rulings up, applied to the
change that would have broken it — a control firing where there is nothing to catch.

**`#631` — CLAUDE.md returns under the ~150 lines it teaches.** Currently 191, and always-loaded, so
every line is paid every session. The architecture description and component inventory move to
`documentation/project-structure.md`, which already owns that subject, and CLAUDE.md points at it
instead of restating it. Nothing that moves is deleted. The principles roster and the governance
anchor stay — those are what make the file load-bearing.

## Why a patch

Three of the five ship no plugin surface at all: `deprecation-retention-window` edits artifacts and
learnings, #646 edits two runbooks, #631 edits this repo's own CLAUDE.md — all outside `plugin/`.
Only #638 and #636 reach a consumer, and neither adds an invocable surface, changes a gate's
verdict, or repurposes an existing flag, exit code or `--json` key. Conservative versioning
(`operational-spec.md` § Direction, 2026-07-17) reads that as a patch without argument.

**The ruling is normative and still not minor-tier.** It narrows what the harness-only-removal
exception permits, which binds future work — but it removes no capability, breaks no caller, and
changes no shipped behavior in this release. A rule getting stricter costs a version number only
when something has to change to comply, and nothing does: v3.3.3 already restored both commands
under exactly this reading.

**The honest counter-argument, recorded rather than resolved away.** #636 writes a *new persisted
record field* into archived plan frontmatter, and a new persisted format is ordinarily a minor-tier
signal. It stays a patch because `api-contract.md` § Direction already rules this shape directly:
additive-first evolution, new keys are added, and readers tolerate unknown keys. A reader that
chokes on `unbuilt_at_archive:` was already out of contract. The failure direction is also safe —
absence means clean, so a reader that ignores the field sees exactly what it sees today.

## Why six issues are withheld

Not one of them is judged low-value; each has a specific blocker, and none is "we ran out of time."

- **#640 → #641 is a chain, and its first half is already built.**
  `fix/reviewer-rule-over-instance` exists as a **local-only branch, never pushed** — 5 commits,
  11 files, including `tests/test_control_yield_tokens.py` (131 lines). It carries the *reporting*
  side of #640 (the `rule-unenforced:` convention). Confirmed absent from `develop`:
  `grep -rn rule-unenforced plugin/` returns nothing. Pushing and landing that branch is step 0 of
  v3.4.0, before any new work on the scope. The *resolution* side — a rule-shaped finding is
  resolved by re-running its predicate, not by ticking its enumeration — is what #641 declares
  itself blocked by, and it changes what `verify-resolutions` accepts. That is gate semantics.
- **#630 must precede #641.** The digest sits at 9985 chars against a hard 10,000
  (`tests/test_plugin_methodology_digest.py:37`), and it is the sole carrier of framework-wide
  defaults for thin-anchor and migrated repos. #641's design requires products to **declare their
  entry-point surfaces** — a new framework-wide default those repos must learn. That is precisely
  the trigger #630 names, and doing the relief pass under that deadline is what produces the fake
  rule-merge the issue warns against.
- **#642 and #633 each add a capability.** #642 adds a dispatch-time signal `critic-begin` does not
  emit today; #633 is *entirely* a new `doctor`/`migrate` repair that mutates a consumer's
  `project-state.yaml`, since nothing scaffolds the field and there is no code path to simply stop
  writing.
- **#644 is unblocked but unbuilt.** Ruling 1 above writes the rule; the conformance leg still has
  to be designed against it, and its severity tier is an open question the issue itself flags.

**Ordering for v3.4.0:**

```
step 0:  push + land fix/reviewer-rule-over-instance   (already built, unmerged)
   ↓
#640 resolution half  ──────────────┐
                                    ├──→  #641 entry-point assertion sweep
#630 digest relief pass  ───────────┘
#642, #633, #644  — independent, batch anywhere after step 0
```

Every one of #640, #641, #642 carries the same platform constraint and it is not negotiable:
prawduct governs products in any language, so the mechanism must read **declarations**, never
parsed source. An AST walk is one ecosystem's implementation and solves the class for nobody
writing Swift, Go or TypeScript.

## Verification

Each scope carries its own acceptance criteria from its issue. Release-level:

- The `Done when` sha pair in the release runbook **passes** on this cut's own promotion — the
  first time it has been able to, and the check that proves #646 rather than asserting it.
- `tests/test_plugin_methodology_digest.py` still green (this release adds nothing to the digest;
  #630 is withheld precisely so it is not spent here).
- CLAUDE.md project-specific content at or under ~150 lines, and the always-injected session digest
  still covers everything a product session needs.
- `check-releasability --release v3.3.4` exits 0 reporting **5 shipping, 0 withheld** — and
  `K withheld = 0` routes Phase 2 to `cut-and-publish-a-plugin-release.md`, **not** to
  `promote-a-pruned-release.md`. See the correction under *Release classification*: withheld
  *issues* are not withheld *scopes*, and only the second kind makes a promotion pruned. Run the
  gate before Phase 2 rather than reading the count off this document — it is the gate's answer that
  chooses the branch.
- **The one measurement to take at the cut**, because the case has never been observable before:
  after promotion, start a fresh session and re-run the `Done when` install-sha pair. If it prints
  matching trees, #646 is proven in the field rather than argued. If it does not, run the corrected
  case-triage — a genuine (2)/(3) is now distinguishable from the false alarm the old check produced
  for everyone.
