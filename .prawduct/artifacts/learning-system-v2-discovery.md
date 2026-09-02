# Discovery — Learning System v2 (scoped rules, hard budgets, one-way cutover)

**Status:** requirements drafted from the audit and the owner's rulings of 2026-09-01/02; four
design decisions await veto (§7); build plans not yet written.
**Parent:** `learning-system-audit-2026-09-01.md` (§1–§6 the evidence and Option C; §8 the
scoping, location, migration and open-question rulings). This document does not restate the
evidence; it turns the rulings into requirements a build plan can be drawn from.
**Backlog homes:** #744 (the program), #295 (memory convergence), #343 (shipped discipline corpus), #685 (reflection
gate on planless repos), #350 (detail file sink), #347 (reflection.md stale). Eighteen further
learning-machinery defects close by deletion in Wave 2 (§8.3).

---

## 1. The ask

The owner accepted the audit's verdict and Option C, then ruled on the four questions that
shaped it:

- *"Would we be better served by some sense of categorization and filtering to the current
  work?"* — yes, and the harness's `.claude/rules/*.md` with `paths:` is the filter; prawduct
  builds no retrieval (audit §8.1–8.5).
- *"What do you recommend for `.claude/rules` vs `.prawduct`?"* — `.claude/rules/learnings/` is
  the single source of truth; no emitted copies (§8.6).
- *"Doctor is its own problem … should a prawduct update just make the change?"* — hard cutover,
  agent-executed at the first session on the new version, no owner gate, no dual mode (§8.7).
- The §7 answers (§8.8): Stop-hook gate in `record_lint`; bytes-only per-file budget, default
  16KB; framework-owned discipline corpus with push intake; no scheduled consolidation pass;
  episodes not ceded.

And the execution constraint: *"a build plan optimized for execution by multiple opus
subagents."*

## 2. Problem, success, out of scope

**Problem (observable).** Product knowledge reaches context in 23% of sessions and is visibly
applied in a handful; the corpus regrows past every cap within weeks; ≈8,300 lines of code and
tests, 38 backlog items and 20+ reworks maintain a read side with single-digit yield.

**Success (verifiable at release).**

1. On a migrated repo, every session has the core rules in context at launch and the area rules
   in context whenever a matching file is read — with no prawduct code on the read path. Check:
   the files exist under `.claude/rules/learnings/`, nothing in the plugin injects them.
2. Learning-system plugin code is ≈300 lines of lib Python with tests in proportion, down from
   2,107 dedicated lines plus ≈600 mixed and 214 dedicated tests (inventory §8.2).
3. Every fleet repo migrates in its first session on the new version with one commit, no
   owner action, and the old layout is never read by the new version.
4. A rule file over budget blocks the *next addition* at Stop and nothing else.
5. The Critic's cross-check reads core plus the area files whose globs intersect the diff.
6. The ledger records `learning.written` and `learning.fired`, so the next audit reads numbers.

**Out of scope.** The discipline corpus beyond its ten-rule seed (#343 stays open for the
content program); any cession beyond the one digest line in R10; the backlog, change-log and
project-state size advisories (separate); Claude memory's own behaviour; product repos' Claude
memory leakage in the prawduct→product direction (accepted, §8.8 Q6).

## 3. Structural context (feature-level)

Framework work on a product already classified; this recurrence adds nothing to
`classification.structural`. Two characteristics bear on the plan:

- **Exposes a programmatic interface.** Four `prawduct-hook` verbs are removed
  (`audit-learnings`, `check-learnings-pairing`, `learnings-obligation`, and the
  `learnings-entry-shape` finding id) and one added (`learnings-migrate`). One skill
  (`/prawduct:learnings`) is removed. The onboarded-repo contract changes: `.prawduct/learnings*.md`
  leave it, `.claude/rules/learnings/` enters it. These are breaking for consumers and
  `api-contract.md` records them; the versioning decision is §7 D1.
- **Runs unattended (hooks).** The SessionStart and Stop hooks gain one detection each. A
  silent failure here is *an unmigrated repo the new version reads as empty*; R4 makes that loud.

Rigor: stakes are high on one path (the Critic cross-check is where rules fire today; re-pointing
it wrong silences the only working channel) and low elsewhere (deletions of unread code).
Knowledge confidence is high; the one volatility item — harness rules semantics — was verified
against current docs on 2026-09-02 (audit §8.3, §8.6) and is recorded in §6 as assumptions
where the docs are silent.

## 4. Requirements

Each carries its source and what proves it. Numbering is stable; a build plan cites `R<n>`.

**R1 — Layout and resolver.** Rules live in `.claude/rules/learnings/`: `core.md` (no `paths:`
frontmatter; always loaded) plus zero or more `<area>.md`, each opening with YAML frontmatter
whose `paths:` lists root-relative globs. One resolver in `plugin/lib/` returns the ordered file
list, the core file, and for a given set of changed paths the area files whose globs intersect
them; every plugin reader goes through it. Nothing else in the plugin names `learnings.md`.
*Proof:* a preference test that no non-test plugin file contains `learnings.md` outside the
migrate command and the change-log; resolver unit tests including glob∩diff.

**R2 — Budget gate.** `record_lint` gains one check: for each file the resolver returns, when its
size exceeds its budget **and** it grew since the session baseline, emit a BLOCKING finding
whose text carries the payment rule (pay from duplication, or raise the budget with a reason).
Default budget 16KB; per-file override `learnings_budgets:` in `project-state.yaml` mapping file
name → `{kb, reason}`, reason required. No count cap. The `oversized_file_threshold_kb` nudge
stops covering learnings files. *Proof:* lint tests for over-and-grew (blocks), over-and-shrank
(passes), under (passes), override with and without reason.

**R3 — Migration command.** `prawduct-hook learnings-migrate [--apply] [--map <file>]`:
mechanical and lossless. Dry run prints the plan; `--apply` performs it. Behaviour: each
`## <Topic>` section with bullet rules becomes `<slug>.md`; sections and unsectioned
paragraph-heading rules with no glob mapping go to `core.md` under `## Unsorted` (paragraph rules)
or their own heading (sections); `[detail](…)`/`→ detail.` links are stripped; `<!-- prawduct-learning: … -->`
metadata comments and the descent-obligation block are dropped; `learnings-detail.md` and
`learnings-history.md` are deleted. The topic→glob map is proposed by the command from the
repo's top-level directories and the section titles, written to a sidecar the agent edits and
passes back with `--map`. Refuses when any learnings file has uncommitted changes. Idempotent:
a second run on a migrated repo reports nothing to do. *Proof:* fixture repos in the three fleet
formats (topic-bulleted, paragraph-heading, mixed); a byte-accounting test that every non-link,
non-metadata byte of the source appears in the output.

**R4 — Detection and directive.** SessionStart: when `.prawduct/learnings.md` exists and
`.claude/rules/learnings/` does not, the briefing's learnings line reads `UNMIGRATED — not
loaded` and carries an `agent →` directive to run the migration and commit before other work.
When both exist, the directive is to fold the old file into the rules files and delete it.
Neither is an advisory: no id, no dismiss. Stop: while the old layout is present and code changed
this session, the reflection gate's sibling blocks with a named reason. *Proof:* briefing and
stop tests for the three states (old only, both, new only).

**R5 — Critic and PR cross-check.** `skills/critic/review-protocol.md`, `review-cycle.md`,
`goals-1-3.md`, `agents/critic-reviewer.md`, `skills/pr/review-protocol.md` and `lib/gates.py`
read the resolver's answer (core + glob∩diff) instead of `learnings.md`. One goal is added to the
cross-check: *rules added or changed this cycle — duplicate of an existing rule, wrong area file,
or discipline/framework content that belongs upstream?* The `learnings-entry-shape` NOTE severity
mapping is removed with its check. *Proof:* the skill-structure preference tests updated; a
review-cycle test that the goal text is present once.

**R6 — Deletions, whole.** Code, tests, docs and records together (`purpose.md`): 
`audit_learnings_cmd.py` (1,751) and `tests/test_audit_learnings.py` (131 `test_` functions);
`learnings_obligation.py` (356), `tests/test_learnings_obligation.py` (34), the obligation block
in `init_product.py` and `onboarding_probes.py`; `check-learnings-pairing` and
`tests/test_learnings_pairing.py` (37); `record_lint._check_learnings_shape` and
`TestLearningsEntryShape` (10); the `/prawduct:learnings` skill directory and its instruction sites
(planning.md §Learnings as Design Constraints, building.md, pr/SKILL.md, review-cycle.md, doctor
checks 13a/audit flow, session-digest.md, `buildplan_refs.py` slash-command resolution,
`test_path_reference_resolution.py`); the `reflections.md` archive step in `cmd_clear`, its
provenance header, `tests/test_reflection_provenance.py` (12) and the `reflections.md` entries in
`core.py`'s session-file registry, `gitignore_probes.py`, `migrate_plugin.py`; the learnings
embedding in `.subagent-briefing.md`; the `sentinel_command` / `sentinel_ungraded_exit_codes`
keys in `templates/project-state.yaml`; the `run_audit_learnings` lazy-import entry;
`_EPHEMERAL_*_COMMANDS` entries; `tests/spikes/learning_families.py`. *Proof:* the lazy-import
registry test, ephemeral command-list tests and hook-argument-shape tests updated; grep-clean
for every removed verb.

**R7 — Reflection gate fires on the common case.** The Stop gate's reflection check applies
when code changed this session regardless of an active build plan (#685), and grades shape —
an "expected vs actual" and a "root cause" or "no defect" line — not a 50-character floor.
Waiver key unchanged. *Proof:* stop tests for planless-clean-repo-with-code-change (blocks),
shape-present (passes), length-only (blocks).

**R8 — Write path instruction.** `methodology/reflection.md` is rewritten to the new model:
episode → `.session-reflected`; rule → the right file (core if cross-cutting, area if
path-bound, upstream via `/prawduct:report-bug` if framework friction, and *not written* if it is
portable discipline — say why in the reflection instead); the budget and the payment rule; the
descent obligation in two sentences at the top of `core.md`'s scaffold. The routing question is
an instruction and a Critic goal (R5), **not a write-time probe** — `docs/norms.md` § Deliberate
Non-Design forbids prose-parsing probes and the audit's own evidence is that the Critic is where
rules fire. `building.md:107` "reflect now" stays. *Proof:* `test_v5_methodology.py` prose
assertions updated; a token-budget entry for reflection.md (#688).

**R9 — Ledger events.** `learning.written` (record_lint sees a rules file grow at Stop) and
`learning.fired` (a Critic finding cites a rule by heading, detected at `critic-consolidate`).
Fields: repo, file, rule heading hash, session id. *Proof:* ledger schema test; one emission test
each.

**R10 — Digest line.** One sentence in `session-digest.md`: the harness's auto-memory should not
hold project state or product rules; `.prawduct/` and `.claude/rules/learnings/` are
authoritative. Within the digest's token budget (#503 cascade). *Proof:* the digest budget test.

**R11 — Onboard and scaffold.** `init-product` writes `.claude/rules/learnings/core.md` with the
two-sentence obligation header and no rules; `onboarding_probes` expect it; `.gitignore` handling
stops mentioning `reflections.md`; `migrate_plugin.py` stops preserving `learnings*.md`. *Proof:*
`test_plugin_init.py`, `test_onboarding_probes.py`, `test_gitignore_management.py` updated.

**R12 — Discipline seed.** The ten cross-repo duplicates (audit §3.5) become, each, one of: a
Critic goal sentence, a code directive at the action, or a methodology sentence — chosen per rule
and recorded in a table in `docs/principles.md` or a new `docs/discipline.md`. Nothing is shipped
as an always-loaded corpus. *Proof:* the table exists with ten rows and each row's target
surface contains its sentence.

**R13 — Records and release.** `api-contract.md` records the removed verbs, the added verb and
the contract change; `documentation/project-structure.md` shows the new tree for both repos;
`CLAUDE.md` Reference section repointed; `plugin/CHANGELOG.md`; one change-log entry per plan
with `scope=` tags; version bump per D1; this repo migrated by its own command as the last
chunk of Wave 1 (dogfood before release).

**R14 — Fleet migration** is not a framework deliverable: it happens in each repo's first
session on the new version (R4). The 19 repos and the orphan `wt-*` worktrees need no action.

## 5. Decisions recorded

`[DECISION: rules live in .claude/rules/learnings/, not .prawduct/, and no copy is emitted |
one carrier per fact; the harness owns loading; every remaining prawduct job works on any path
(audit §8.6) | user can veto]` — engages the "durable prose never rides on a value that changes
under it" rule and the file-sync retirement (M4).

`[DECISION: one-way cutover, no dual read or write path, agent-executed at first session |
the backlog cutover's dual mode is three months old and still open; the relayout is lossless
and revertible, so the property that justified an owner gate there is absent (§8.7) | user can
veto]` — engages `discovery.md` "Surface Behavioral Choices": backwards compatibility is elicited,
not assumed, and here it was elicited and declined.

`[DECISION: the write-time routing is an instruction plus a Critic goal, never a probe |
docs/norms.md § Deliberate Non-Design; the Critic is the channel with measured firing | user can
override]`

`[DECISION: budget is bytes per file, 16KB default, override-with-reason; no count cap |
audit §8.8 Q2 | user can override]`

`[DECISION: `reflections.md` archive and provenance are deleted, not ceded to Claude memory |
§8.8 Q6 | user can veto]`

## 6. Assumptions (vetoable)

`[ASSUMPTION: rules files do not reach subagents; the Critic keeps reading them explicitly |
LOW impact — explicit read is what it does today | user can defer]` (docs silent)

`[ASSUMPTION: `paths:` globs are matched relative to the repo root | MED impact — every area
file depends on it | user can correct]` (every doc example implies it; not stated)

`[ASSUMPTION: an Edit in this harness is preceded by a Read, so Read-triggered loading is
sufficient | MED impact | user can correct]` (harness behaviour observed, not documented)

`[ASSUMPTION: a briefing `agent →` directive is acted on in the same session | MED impact —
otherwise the Stop floor in R4 carries it | user can defer]` (evidence: advisory relay
compliance in transcripts)

`[ASSUMPTION: the framework repo's own core.md will exceed 16KB at migration and that is
accepted — it blocks the next addition, not the release | LOW impact | user can override]`

## 7. Open for veto before the first build plan

- **D1 — Version.** The contract break (four verbs and a skill removed, repo layout changed)
  argues for **3.5.0**; `feedback_conservative_versioning` argues patch. Recommendation: minor —
  a consumer's repo is rewritten on first session, which is the definition of a change they must
  be able to see in the version.
- **D2 — Standing block relocation.** `reflection.md` is ~60% standing-block spec (STATE /
  RUNNING / SAFE TO CLEAR). The rewrite (R8) is the natural moment to move it to its own guide
  (`methodology/session-hygiene.md`) with the digest pointer updated. Recommendation: yes, in
  Wave 3, as its own chunk — it is a doc move, and leaving it makes the learning guide unreadable.
- **D3 — Directory name.** `.claude/rules/learnings/` (recommended: names the origin, keeps a
  user's own rules files unambiguous) vs a flat `.claude/rules/` with a name prefix.
- **D4 — Budget scope.** Gate every file under `.claude/rules/` (what loads is what costs) vs
  only `learnings/`. Recommendation: only `learnings/` in this release; widening is a one-line
  change once the gate has a track record, and a user's own style file blocking their session on
  day one is the wrong first impression.

## 8. Program shape

### 8.1 Three plans, one release

`planning.md`: a plan that will not ship in about three sessions is a program. This is one
release in three waves, each its own plan and scope tag, all on one branch
(`feature/learning-system-v2`, from `develop`).

| Wave | Scope tag | Delivers | Ships alone? |
|---|---|---|---|
| 1 | `learnings-v2-core` | R1 resolver + layout · R2 gate · R3 migrate · R4 detection · R5 cross-check · R11 scaffold · this repo migrated | No — the lookup skill and nudge would still point at the old file |
| 2 | `learnings-v2-delete` | R6 deletions · R7 reflection gate · R9 ledger | No — docs still describe the old system |
| 3 | `learnings-v2-docs` | R8 reflection.md · R10 digest · R12 seed · R13 records, D2 move, version, release | Yes — the release |

### 8.2 Partition for parallel delegates

Precedent read, not asserted: `build-plan-instruction-surface-truth.md` delegated four ways at
the owner's request, partitioned by file tree because delegates shared one working tree;
`project-preferences.md` carries no Delegation row. The owner has asked for multi-subagent
execution, which is a standing negative on the approval question; disclosure follows.

**Wave 1 — keystone then fan-out.** Chunk 01 (resolver + layout + scaffold, R1/R11) is the
thin slice everything reads, built serially and reviewed `final`. Then three delegates in
isolated worktrees, each owning disjoint files:

| Delegate | Owns | Must not touch |
|---|---|---|
| W1-A migrate | `lib/learnings_migrate.py` (new), `cmd_learnings_migrate`, `tests/test_learnings_migrate.py`, fixtures | `record_lint.py`, `briefing.py`, skills |
| W1-B gate | `record_lint.py` budget check, `tests/test_record_lint.py`, `templates/project-state.yaml` budgets key | `bin/prawduct-hook` beyond the lint dispatch, briefing |
| W1-C detection + cross-check | `briefing.py` learnings line + directive, `cmd_stop` floor, `gates.py`, the five Critic/PR prose files, their tests | `record_lint.py`, the migrate module |

`prawduct-hook` is shared: each delegate's edit is confined to one named `cmd_` function or
dispatch line, and the coordinator merges. Chunk 05, serial: migrate this repo with W1-A's
command, commit, `cumulative` review.

**Wave 2 — the widest fan-out, all deletions by module.** Six delegates, each owning one
deletion set from R6 and its tests, no shared files except `prawduct-hook` (one `cmd_` each) and
`__init__.py`'s registry (one line each, merged by the coordinator): audit-learnings; obligation +
init/onboard; lookup skill + instruction sites; reflections archive + registry + gitignore;
ledger events (R9, additive); reflection gate (R7). The coordinator owns the grep-clean sweep
and the full suite.

**Wave 3 — serial.** Docs are one voice; three of the five chunks edit `reflection.md` or the
digest, and the release chunk is the coordinator's by definition.

**Verification ceiling for every delegate:** its own test files plus `tests/preferences/`. The
full suite, `verify-records`, the Critic and all bookkeeping are the coordinator's.

### 8.3 Backlog closed by Wave 2

By deletion, no other action: #154, #237, #269, #338, #339, #345, #346, #350, #369, #449, #571,
#573, #661, #717, #351 (obligation marker), #347 (by R8), #685 (by R7), #439 (single-owner
cross-check — R5 makes the cumulative Critic the one owner). #295 closes with the release;
#343 stays open as the content program with R12 as its first entry.

## 9. Risks and the plan's answer

- **The cross-check goes dark** if R5 lands before R1's resolver is trustworthy → Chunk 01 is
  reviewed `final` before fan-out, and W1-C's tests assert the resolver is the only path.
- **A Stop floor annoys unrelated sessions** on an unmigrated repo → it fires only with code
  changed, and the migration is one command; measured cost is one turn, once per repo.
- **Branch modify/delete conflicts** on feature branches carrying the old file → loud, one-time;
  R4's both-present directive is the repair.
- **Token-budget guardrail tests** on the digest and CLAUDE.md (#503) → R10 and R13 name them
  and budget the trim in the chunk.
- **The framework repo's 3 metadata-carrying rules** (`sentinel=`, `superseded-by=`) lose their
  metadata in R3 → git history keeps it; nothing will read it after R6.
- **A delegate's "done" on a deletion** is the `Done taken on faith` anti-pattern → the
  coordinator re-derives every removal with the grep-clean sweep before the wave's review.

## 10. Next steps

1. Owner vetoes or accepts §7 D1–D4 and §6.
2. `feature/learning-system-v2` from `develop`; this artifact and the audit committed on it.
3. Backlog: one epic linking the three scope tags; #295/#343/#685/#350/#347 updated with
   `refs:` to this document and `stage=design`.
4. `build-plan-learnings-v2-core.md` (Wave 1) written per §8.2, `partition:` recorded, delegate
   briefs written into each worktree at dispatch; Waves 2 and 3 drawn when their wave starts.
