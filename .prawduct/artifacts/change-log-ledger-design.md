---
artifact: design proposal
scope: change-log-ledger
status: proposed — not scheduled, not built
depends_on:
  - .prawduct/artifacts/kernel-v3-evidence-design.md   # the precedent this reuses
governed_by:
  - .prawduct/artifacts/data-model.md                   # persisted-format norms — binds hardest
  - .prawduct/artifacts/project-preferences.md          # derived-view conventions, merge strategy
  - .prawduct/artifacts/nonfunctional-requirements.md   # state-file growth posture
requirements_confidence: Medium
---

# Change-log restructure: facts in a ledger, prose in the change log

**One sentence:** `change-log.md` stores typed relational state as hand-written prose, so every
consumer re-derives that state with regexes and every writer must memorise rules the format cannot
enforce — move the typed fields into a committed, append-only fact store and let the change log
become the rendered view it was always meant to be.

**Status: a proposal, not a plan.** Nothing here is scheduled. It exists because the owner asked for
the shape before committing to REL-8P6M part (e), which rewrites machinery this design deletes.

---

## 1. The problem, measured

Measured on `feature/v3.2.0-c02-adapter-safety` @ `7db9eca`, 2026-07-29:

| Signal | Value |
|---|---|
| `change-log.md` size | 657 KB · 6,872 lines · **194 entries** |
| Entries carrying machine tags | **77** (~40%) — the other 117 are invisible to every view |
| Machine-derived checkboxes under `regen-views` | **224** across `artifacts/` (191 `[x]`, 33 `[ ]`) |
| Learnings that exist to encode change-log format rules | **14** |
| Open backlog items in contact with change-log mechanics | ~41 of 179 (keyword upper bound; the named families below are exact) |
| Largest open-backlog area | `governance`, 31 items |

**The named defect families, all one root cause:**

- `REL-7D4X` — the release sweep is **positional** (counts entries above a boundary), so entries
  merged below it are dropped.
- `REL-8P6M` (e) — the same sweep tags the **wrong subset**: under a pruned release it marks withheld
  work as shipped.
- **W-1**, filed by the PR reviewer on this very branch — the sweep is **scope-narrowed**: its
  re-derivation instruction is `re-grep scope=v3.2.0-golive`, which cannot see the statusless entries
  under the other scopes on the same branch. *(Figure corrected twice, 2026-07-29. Filed as 8; a
  first "correction" to 9 recounted only the four scopes the finding already named, which verified
  the number while inheriting the frame — the same scope-narrowing the finding is about. Measured on
  `feature/rel-8p6m-releasability-gate` @ `1a353d1`, above the `release=v3.1.2` boundary: **23
  release-pending entries across six scopes**, of which `v3.2.0-golive` is 7, so the miss is **16
  across five scopes**. Every figure here is a measurement of one tree; recount, do not cite.)*
- `VWS-4T9P` / `VWS-2W6H` / `VWS-2F9K` — `regen-views` plan discovery globs non-recursively,
  mis-classifies design artifacts as build plans, and still keys on one of two accepted chunk-heading
  forms.
- `DOC-5T8N` — people keep hand-editing derived Status blocks because nothing tells them not to.

Three of those are the *same defect in the same sweep*, found three separate times. That is the
signature of a structural cause, not three mistakes.

**The tell.** `regen-views` exists to overwrite what humans and agents write. A tool whose job is to
undo hand edits is proof that derived state is being stored in a hand-edited medium.

**The tax is also paid in rules people must memorise.** From `learnings.md`, every one a workaround
for a missing schema:

- a `chunks=` tag must match the plan's chunk numbering **exactly, zero-padding included**, or
  `regen-views` silently flips only the matching subset (L:276)
- a plan's `scope:` must be the scope-*name*, never a version, or plans don't resolve (L:129)
- new entries on a feature branch are **statusless**; `status=in-progress` is deprecated and trips a
  typo-guard (L:274)
- at release, flip *statusless* entries too, not just `status=merged` (L:280)
- never determine what a previous release shipped from change-log prose (L:21)
- `.prawduct/` markdown is where merge conflicts happen — four in one integration, **all**
  append-collisions in these files, zero in code (L:496)

And in the parser itself, three validators whose only job is catching malformed hand-written tags:
`validate_status_values` (typo guard), `validate_tag_line_multiplicity` (an entry grew two tag
lines), `validate_tag_conflicts` (the same key written twice with different values, resolved
first-wins). **All three become impossible by construction under a typed store** — you cannot write
one key twice into a dict.

## 2. Root cause

`change-log.md` does five jobs. Only the first wants to be prose:

1. **Human narrative** — what changed and why. *(genuinely prose)*
2. **Release-notes source** — grouped by `release=`.
3. **Release state machine** — statusless → `shipped`, swept at promotion.
4. **Build-plan status derivation** — `chunks=` ticks checkboxes in plan files.
5. **Gate input** — `check-change-log-entry` at the PR boundary; `regen-views --check` fails closed.

Jobs 2–5 are typed relational data. Stored as prose, they have no schema, no uniqueness constraint,
and no transaction — so selection degrades to positional greps, which is exactly REL-7D4X,
REL-8P6M(e), and W-1.

## 3. This repo already solved this, one subsystem over

`CLAUDE.md` describes the kernel-v3 Critic data plane in these words:

> the reviewer(s) … write partials; `prawduct-hook critic-consolidate` merges them …, appends the
> review fact to the shared evidence store …, and regenerates `.critic-findings.json` as a derived
> view (**no model in the write path; no gate reads the view — gates compose over facts**).

The change log is the last subsystem doing the inverse: **gates parse prose, and a tool exists to
overwrite hand edits.** This proposal is not new architecture — it applies the pattern the project
already trusts to the one place that never received it.

**Prior art beyond this repo:** one-file-per-change with a render step is the settled industry
pattern — `towncrier` newsfragments (CPython, Twisted), `changesets` (npm ecosystem), Keep a
Changelog's "unreleased" convention. All three exist because a single hand-edited CHANGELOG is a
merge-conflict magnet and an unreliable database. We would be adopting a known-good shape, not
inventing one.

## 4. Requirements: the queries the data must answer

`methodology/planning.md` is explicit that *a persisted format is always a lock-in decision* and that
its consumers' queries are its requirements, **elicited from the consumers, not inferred from the
mechanism**. So this section is derived by reading every call site, not by designing fields first.

The load-bearing consumer is `plugin/lib/views.py` — one parser (`parse_change_log`) behind eight
internal queries. `plugin/lib/coverage.py` adds a ninth of a different kind. (Six other modules
mention the change log only in comments or copy it as a template; they are not consumers.)

| # | Query | Asked by | Today's mechanism |
|---|---|---|---|
| Q1 | Which scope is currently active? | `_detect_active_scope` | scan entries, infer |
| Q2 | Which chunks of plan P are shipped? | `build_status_view` | `chunks=` ∧ `status=shipped` |
| Q3 | Does every unreleased scope have a build-plan file? | `diagnose_scope_plan_coverage` | glob + match |
| Q4 | Do the chunks named in tags exist in the plan? | `validate_chunk_roster` | regex both sides |
| Q5 | What belongs to scope S? | `build_scope_view` | filter by `scope=` |
| Q6 | What shipped in release R? | `build_release_notes_view` | group by `release=` |
| Q7 | What is plan P's overall status? | `_plan_status_results` | aggregate Q2 |
| Q8 | Mark this set as shipped *(write path)* | `stamp_merged` | **positional prose rewrite** ← the defect site |
| Q9 | Did this branch add an entry? | `coverage.check_change_log_entry` | git-diff shape, not semantics |

Q1–Q7 are ordinary selections over `(scope, chunks, release, status, type, date)`. Q8 is the only
writer, and every one of REL-7D4X, REL-8P6M(e), and W-1 lives in it. Q9 is diff-shaped and survives
any format unchanged.

**Nothing in this list needs prose.** That is the finding: the entire machine surface is six typed
fields.

## 5. Proposed design

**One fact per change.** `.prawduct/changes/<YYYY-MM-DD>-<slug>.md` — YAML frontmatter carries the
typed fields, the body carries the narrative:

```markdown
---
id: 2026-07-29-coverage-free-edge-equivalence
type: perf
scope: coverage-perf
chunks: ["01"]
---
The cumulative coverage gate was quadratic: 5,597 `git diff` subprocesses, 316 s of a 318 s
verdict. Free edges are an equivalence relation, so keying each tree once replaces diffing
every pair. 5 m 12 s → 7.95 s, same verdict.
```

Note what is **absent**: no `status`, no `release`. Those are not properties of a change — they are
properties of *a release's relationship to* a change, and storing them per-entry is why the sweep
exists at all.

**One record per release.** `.prawduct/releases/v3.2.0.yaml` names the set it shipped:

```yaml
version: v3.2.0
date: 2026-07-30
promoted_from: develop@<sha>
shipped:  [2026-07-29-coverage-free-edge-equivalence, ...]
withheld: [{id: 2026-07-22-backlog-service-adapter, reason: "BKL-6J2X open", blocker: BKL-6J2X}]
```

A change is unreleased iff no release record names it. **Q8 stops being a sweep**: releasing is
writing one file that names a set. The positional scan (REL-7D4X), the wrong-subset tagging
(REL-8P6M e), and the scope-narrowed re-grep (W-1) have nowhere left to live.

`shipped` + `withheld` also makes REL-8P6M's **partition check** (c) a schema property rather than a
procedure: every unreleased change must appear in exactly one list, and a release record that omits
one fails validation. That is item (f)'s releasability gate — *"is everything fit to ship?"* — turned
into a file that cannot be written incompletely.

**Everything else becomes a rendered view**, regenerated and never hand-edited: `change-log.md`,
build-plan `## Status` blocks, `release-notes.md`.

**Q9 must be re-pointed at the facts.** Today `check-change-log-entry` reads `change-log.md` — which
this design demotes to a derived view. Leaving it there would put a *gate* on a *view*, which
`data-model.md` forbids outright (§5a, norm 3). The gate instead asserts that the branch adds a file
under `.prawduct/changes/`. This is a **design correction the norm reconciliation surfaced**, not a
detail: had it shipped unnoticed it would have reproduced the exact inversion this proposal exists to
remove. It also converges with the open item `COV-2P7F`, which already wants that gate routed
through `judgeable_files`.

**Schema version is a required field.** Each fact carries `schema: 1`. A reader encountering a
higher version **blocks loudly** rather than skipping the record — `data-model.md` norm 4, and the
behaviour `evidence.jsonl` already implements (`SCHEMA-AHEAD records: … Gates must not be trusted in
this session`). Designing it in now costs one field; retrofitting it costs a migration.

**Why one file per change, not one JSONL:** it eliminates the append-collision class outright
(L:496 — four conflicts in one integration, *all* append-collisions in these files). Two branches
adding changes touch two different files. This is why towncrier and changesets both chose it.

## 5a. Governing norms — reconciliation

`methodology/planning.md`: *a departure from a norm is never silent — you conform, or you record the
decision.* One disposition per binding norm.

**`data-model.md` § Direction**

| Norm | Disposition |
|---|---|
| 1. Governance verdicts computed from the append-only fact ledger, never from mutable model-written state; no model in a fact's write path | **conforms** — and this is the proposal's whole thesis. Today's change-log is *entirely* model-written mutable state that gates read. |
| 2. Facts are immutable and append-only; a state change is a new fact, never an edit in place | **conforms** — a change fact is written once. "Released" is expressed by a *new* release record naming it, never by editing the change. This is precisely what deletes the `stamp_merged` sweep. |
| 3. Derived views are disposable and never authoritative — **no gate reads a view** | **conforms, after a correction.** The draft violated this: Q9 would have gated on the rendered `change-log.md`. Re-pointed at `.prawduct/changes/` (§5). |
| 4. A fact from a newer schema is a loud block, never silently dropped | **conforms** — `schema: 1` on every fact, block-on-higher (§5). |
| 5. Two stores, two lifetimes: shared committed *answers* vs per-clone gitignored *nags and caches* | **conforms** — `changes/` and `releases/` are committed answers. The rendered change log is a view; committing it is a convenience for GitHub browsing, and no gate may read it (norm 3). |
| 6. `backlog_service_repo` selects the authoritative backlog store; `backlog.md` is then frozen history | **inapplicable** — this design does not touch the backlog. Recorded rather than assumed, because §6 flags the overlap as a scheduling prerequisite. |

**`nonfunctional-requirements.md` § Direction**

| Norm | Disposition |
|---|---|
| State-file growth is an **advisory** that prompts compaction — never a hard block | **conforms** — the `changes/` directory gets the advisory treatment (§8's per-year subdirectory note), matching `TREE_COUNT_ADVISORY`'s posture. |
| Review wall-clock is P0; run-count is the lever | **conforms, favourably** — fewer format defects means fewer fix→re-review rounds. Three of this branch's review rounds trace to sweep defects. |

**`project-preferences.md`** has no `## Direction` section; its binding content is the norm rows,
none of which this design departs from (merge-commit strategy and no-attribution-trailers are
unaffected).

## 6. What this closes, and what it does not

**Closed outright** (the mechanism is gone, not fixed): `REL-7D4X`, `REL-8P6M`(e), **W-1**,
`DOC-5T8N`, and the three parser validators. `VWS-4T9P` / `VWS-2W6H` / `VWS-2F9K` narrow to plain
directory reads. Format-memorisation learnings L:274, L:276, L:280, L:129, L:349 become schema
validation. L:21 ("never reconstruct what a release shipped from prose") becomes a file lookup.

**Explicitly not solved.** The backlog (`backlog.md`, 898 KB) has the same disease and is **out of
scope here** — it has its own in-flight migration to GitHub Issues. Reviewing that overlap is a
prerequisite to scheduling this, not part of it. This proposal also does not reduce the *number* of
governance surfaces; it makes one of them typed.

## 7. Migration

1. **Preserve history verbatim.** `change-log.md` → `change-log-archive.md`, untouched, forever. The
   194 existing entries are the record; nothing is rewritten in place.
2. **Convert the 77 tagged entries mechanically** — the tag line is already `key=value`. Deterministic
   script, output diffed against `parse_change_log`'s current output as the equivalence oracle (the
   same "keep the old implementation as reference and test both" discipline that carried the
   coverage-perf rewrite).
3. **The 117 untagged entries stay in the archive.** They pre-date tagging, no view can see them
   today, and inventing metadata for them would be fabricating history.
4. **Reconstruct release records** for shipped versions from git tags plus each release's tree —
   per L:21, from *code*, never from prose.
5. **Cut over** with both paths live and `regen-views --check` asserting the rendered `change-log.md`
   is byte-identical to today's. Delete the parser only after a full release cycle runs on the new path.

## 8. Costs and risks — the honest objections

- **This is a plugin-wide breaking change for consumer products.** Every onboarded repo carries a
  `change-log.md`. This needs a `/prawduct:migrate` path, a major version bump, and a fleet migration
  — and the fleet is exactly what BKL-6J2X shows we get wrong (an advisory firing in every
  un-migrated repo). **This is the single largest cost and the main argument against.**
- **~30 tests in `test_views.py` target `parse_change_log` directly.** They are the contract and must
  be rewritten deliberately, not deleted.
- **Rendering must be deterministic** or `regen-views --check` becomes a false-positive generator.
- **194 files in one directory** is a legibility change; `changes/` will want per-year subdirectories
  before long.
- **Not during a release.** Doing this while v3.2.0 is in flight would repeat the v3.1.2 mistake of
  restructuring under release pressure.

## 9. Requirements Confidence: **Medium**

The problem is measured and the consumer queries are read from source rather than assumed. What is
unconfirmed is scope and sequencing, not the diagnosis.

**What would raise it to High:** a decision on the backlog-service overlap (§6), and a 30-minute
spike converting five real entries end-to-end to confirm the frontmatter shape survives contact with
messy historical data.

**Open assumptions:**

- `[ASSUMPTION: the rendered change-log.md stays committed, not gitignored, so GitHub browsing and
  non-prawduct readers keep working | MED impact | user can override → gitignore it and treat the
  facts as the only source]`
- `[ASSUMPTION: release notes keep grouping by release, which the release record preserves | LOW |
  user can correct]`
- `[ASSUMPTION: this follows v3.2.0 rather than blocking it | HIGH | user can override, but see §8]`
- `[ASSUMPTION: build-plan Status blocks stay as rendered checkboxes rather than being dropped —
  §1 counts 224 of them, and whether they earn their machinery is a separate question | MED |
  user can correct]`

## 10. Alternatives considered

- **Fix the sweep properly (REL-8P6M e as written).** Correct and self-contained, and it is the
  fourth fix to the same mechanism. Rejected as the primary path for that reason, though it remains
  the right move if this proposal is declined.
- **Keep prose, add a schema validator.** Cheaper, and strictly better than today — but it makes
  malformed tags *detectable* rather than *impossible*, and leaves Q8's positional write path intact.
- **Move state into `project-state.yaml`.** Already 32 KB and merge-hostile; concentrates the
  collision class rather than removing it.
- **Do nothing.** Defensible if the change log is near end-of-life. Worth noting `GOV-6D4Q` records a
  2026-07-02 simplification diagnosis whose fix programme was never run — "file it and move on" has
  a track record here.
