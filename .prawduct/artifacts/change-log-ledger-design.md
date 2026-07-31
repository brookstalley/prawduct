---
artifact: design proposal
scope: change-log-ledger
status: spiked 2026-07-31 — design validated, GO conditional on scheduling (§11); not built
depends_on:
  - .prawduct/artifacts/kernel-v3-evidence-design.md   # the precedent this reuses
governed_by:
  - .prawduct/artifacts/data-model.md                   # persisted-format norms — binds hardest
  - .prawduct/artifacts/project-preferences.md          # derived-view conventions, merge strategy
  - .prawduct/artifacts/nonfunctional-requirements.md   # state-file growth posture
requirements_confidence: High   # raised from Medium 2026-07-31 by the §11 spike
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
| Entries carrying machine tags | ~~**77** (~40%) — the other 117 are invisible to every view~~ **FALSIFIED 2026-07-31** — recounted at this table's own named tree `7db9eca`: **173 tagged (89%), 21 untagged**. See §11. |
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
date: 2026-07-29
title: Coverage's free-edge equivalence — 5m12s to 7.95s, same verdict
type: perf
scope: coverage-perf
chunks: ["01"]
---
The cumulative coverage gate was quadratic: 5,597 `git diff` subprocesses, 316 s of a 318 s
verdict. Free edges are an equivalence relation, so keying each tree once replaces diffing
every pair. 5 m 12 s → 7.95 s, same verdict.
```

`date` and `title` are **required, not decorative** — the spike proved the id slug is lossy
(backticks stripped, punctuation collapsed, truncated), so a renderer cannot reconstruct the `##`
heading from the id alone. An earlier draft of this section omitted both; §11 records the correction.

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
2. **Convert the tagged entries mechanically** — **193 at HEAD, not 77** (§11); the tag line is already `key=value`. Deterministic
   script, output diffed against `parse_change_log`'s current output as the equivalence oracle (the
   same "keep the old implementation as reference and test both" discipline that carried the
   coverage-perf rewrite).
3. **The 21 untagged entries stay in the archive** (not 117 — §11). They pre-date tagging, no view can see them
   today, and inventing metadata for them would be fabricating history.
4. **Reconstruct release records** for shipped versions from git tags plus each release's tree —
   per L:21, from *code*, never from prose.
5. **Normalize first, then cut over.** Byte-identity with *today's* file is **provably unreachable**
   (117/214 — §11), because the corpus carries two tag-key orders and two blank-line layouts. So the
   cutover is two commits, not one: a mechanical **normalization** commit touching 127 tagged entries
   (97 key-order, 30 blank-layout, disjoint), which is reviewable as pure formatting because
   `parse_change_log` output is unchanged by construction; then cut over with both paths live and
   `regen-views --check` asserting byte-identity against the *normalized* file. Delete the parser only
   after a full release cycle runs on the new path.

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

## 9. Requirements Confidence: **High** *(raised from Medium, 2026-07-31)*

The problem is measured and the consumer queries are read from source rather than assumed. What was
unconfirmed was scope and sequencing, not the diagnosis.

**Both of the named raisers have now been executed** (§11): the round-trip spike ran — not on five
entries but on all 214 — and the backlog-service overlap was reviewed. The format is validated; the
residual uncertainty is *scheduling*, which is a decision rather than an unknown.

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

---

## 11. Spike findings (2026-07-31) — GO, conditional on scheduling

§9 named two raisers: a five-entry round-trip and a decision on the backlog-service overlap. Both
were executed. The round-trip ran on **all 214 entries** rather than five, because the converter is
the same code either way and a five-entry sample cannot distinguish "the format works" from "the
five I picked were easy."

### 11.1 The oracle, and what it returned

Two oracles, deliberately. Parsed-structure identity is what every consumer query (Q1–Q7) reads;
byte identity is what §7 step 5 proposes to assert at cutover. A format can pass the second and fail
the first, and only the first proves the rendered view is drop-in.

| Oracle | Result |
|---|---|
| `parse_change_log` structure identical (title + tags) | **214 / 214** |
| Byte-identical, preserving each entry's own tag-key order | **214 / 214** |
| Byte-identical under one canonical tag-key order | **117 / 214** |

**The format survives the full historical corpus losslessly.** No entry defeated it — including
tables, fenced code, sub-headings, backticked titles, em-dashes, an untagged pre-tagging entry, and
one entry (L3267) carrying a non-prawduct HTML comment flush against its tag line.

### 11.2 Three corrections to the design

1. **`title` and `date` are required fields.** §5's example frontmatter carried neither. The id slug
   is lossy — it strips backticks, collapses punctuation, and truncates — so a renderer cannot
   rebuild the `##` heading from the id. §5 corrected.

2. **§1's tag census was wrong, and nothing derives it.** Recounted at the table's own named tree
   `7db9eca`: **173 tagged / 21 untagged**, not 77 / 117. `77` matches no query over that tree —
   not any-tag (173), any single key (114–141), all-four-core-keys (71), immediate-adjacency (0), or
   a raw grep (253). It appears to be a hand-authored number, and it propagated into migration steps
   2 and 3, oversizing the archive set by 96 entries and undersizing the conversion set by the same.
   *This artifact is itself an instance of the disease the parent plan exists to cure* — a governance
   record carrying an unreproducible count that later work planned against.

3. **§7 step 5's acceptance test was unreachable as written.** It asserted the rendered file be
   byte-identical to *today's*. It cannot be: the corpus carries two tag-key orders (97 entries lead
   with `chunks=`) and two blank-line layouts (30 entries put the body flush against the tag line).
   Byte-identity is reachable only *after* normalization. Step 5 rewritten as two commits.

### 11.3 The normalization commit, sized

| | count |
|---|---|
| Entries | 214 (193 tagged, 21 untagged) |
| Already fully canonical — untouched | 66 |
| Non-canonical key order | 97 |
| Non-canonical blank layout | 30 |
| **Total touched by normalization** | **127** (the two sets are disjoint) |

Blank lines *before* the tag line are universally 1, so that axis needs no normalization. The commit
is reviewable as pure formatting: `parse_change_log` output is unchanged by construction, which is a
machine-checkable property rather than a promise.

### 11.4 Release records reconstruct cleanly

Rebuilding release records from the existing `release=` / `status=` tags yields **57 releases**, and
the partition property §5 wants as a schema invariant **already holds in the data**: zero entries
carry a release without a status or vice versa, and zero are release-pending at HEAD. Reconstruction
(§7 step 4) is therefore mechanical, and the invariant is being adopted rather than imposed.

### 11.5 Two hazards are latent, not live

`validate_tag_line_multiplicity` guards a case with **zero current instances** — no entry in the
corpus has more than one tag line. The guard is cheap insurance against a defect that has not
recurred, which slightly weakens §1's "three validators become impossible by construction" as a
*present* cost while leaving the argument intact.

### 11.6 §6 backlog-service overlap — reviewed

The overlap is **scheduling, not machinery**. Prawduct's own `backlog_service_repo` is unset (markdown
backend); the service shipped dormant in v3.2.0; the two migrations share no code and touch different
files. But **BKL-6J2X is still `open, stage: ready`** — the deliberate *hold* on the
`backlog-service-migration-required` advisory, held precisely because it "routes the whole fleet into
an unproven migration path." §8 concedes the change-log ledger needs exactly that: a
`/prawduct:migrate` path, a major bump, and a fleet migration.

**Running two unproven fleet-migration paths concurrently is the risk BKL-6J2X exists to prevent.**

### 11.7 Decision: GO on the design, HOLD on the schedule

The design is sound, the format is validated against the whole corpus, and the migration is mechanical
and reviewable. Nothing found here argues for the §10 alternatives — in particular, "fix the sweep
properly" remains the fallback but gains no new support.

Scheduling gate, in preference order: **either** BKL-6J2X's hold is lifted and the backlog migration
is proven on the fleet first, **or** an explicit owner decision to run this one first and hold the
backlog. Not both at once. Until one of those lands, this stays `spiked`, not `scheduled`.

**Follow-on plan scope, when scheduled** (five chunks, roughly the shape the evidence supports):
converter + fact schema with `schema: 1`; the 127-entry normalization commit; renderer +
`regen-views` repoint; Q9 gate re-pointed at `.prawduct/changes/` per §5; migrate path + fleet
rollout. The ~30 `test_views.py` tests targeting `parse_change_log` are the contract (§8) and are
rewritten in the renderer chunk, not deleted.

**Spike artifacts** are throwaway by design and were not committed: a corpus survey, a five-entry
round-trip, and the whole-corpus oracle. Every number above is reproducible from the change log at
this tree by re-deriving them; recount, do not cite.
