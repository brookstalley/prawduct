---
artifact: build-plan
version: 2
scope: learnings-v2-delete
branch: feature/learning-system-v2
backlog: brookstalley/prawduct#744
depends_on:
  - artifact: learning-system-v2-discovery
  - artifact: learning-system-audit-2026-09-01
  - artifact: build-plan-learnings-v2-core
governed_by:
  - artifact: api-contract
    dispositions:
      - "whole-surface semantic versioning; no per-subcommand version; persisted data independently schema-versioned → conforms: no verb gains a version; the ledger's per-line `schema_version` stays 1 because two ADDITIVE event kinds change no existing line's meaning"
      - "exit codes are the contract; stable severity prefixes; errors attributed, never stack traces → conforms: the three deprecated verbs exit 0 with a `WARNING:` on stderr (the `regen-views` shape, pinned in `tests/test_deprecated_inert_commands.py`); `ledger-append --event learning.*` is refused with exit 1 and a reason"
      - "additive-first evolution; deprecation is signalled — stderr notice, kept working, removal deferred to a major — never silent → [DECISION: conform. `audit-learnings`, `learnings-obligation` and `check-learnings-pairing` become deprecated-inert stubs and stay dispatchable; their modules, tests and every instruction site are deleted. Discovery R6 said 'deletions, whole' and R13 'the removed verbs', but the norm's deprecate-then-remove path governs everything a human or a skill can call, D1 chose a minor, and the inert shape costs three ~15-line stubs and three rows in one existing test | engages the norm's why: a copied runbook, or a doctor skill on an older per-project pin, gets a notice naming the replacement instead of usage text and exit 1 | user can veto: delete outright with a recorded exception]"
  - artifact: data-model
    dispositions:
      - "verdicts on the Critic data plane computed from the fact ledger, no model in a fact's write path → inapplicable because the reflection gate is not on the Critic data plane (the norm scopes itself to it) and the learning events are telemetry no gate reads"
      - "facts immutable and append-only → inapplicable because this plan writes ledger EVENTS, not evidence-store facts; the ledger is append-only by construction (one `O_APPEND` write per line)"
      - "derived views never authoritative → conforms: nothing reads the governance ledger to reach a verdict, before or after this plan"
      - "a governance document reaches a terminal state, never deleted → conforms: no governance document is deleted. The `reflections.md` ARCHIVE STEP is removed (owner-ruled 2026-09-02, discovery §5) — the plugin stops writing a gitignored, per-clone file that nothing read; the copies on disk are untouched"
      - "every backlog write conforms to the title rules → inapplicable because this plan writes no backlog items (Chunk 05 posts comments)"
      - "a fact written by a newer schema is a loud block → inapplicable because no fact is written; the ledger's own contract is that consumers skip unknown kinds, and `review-stats` already counts them"
      - "two stores, two lifetimes: committed answers vs gitignored nags and caches → conforms: the ledger stays gitignored telemetry; `.session-reflected` stays per-session state"
      - "backlog_service_repo selects the authoritative backlog store → inapplicable because no reader of the backlog changes"
  - artifact: observability-strategy
    dispositions:
      - "stable severity-prefix vocabulary with the stdout/stderr channel split → conforms: the reflection blocker keeps its `REFLECTION:` blocker on the existing channel; the stubs print `WARNING:` to stderr and nothing to stdout; a learning event that could not be appended is a `NOTE:` on stderr, never silence"
      - "the governance ledger has a single writer (the `ledger-append` helper); agents never hand-author it → conforms: both learning events go through `lib.ledger`'s one append function, called in-process from `cmd_stop` and `critic-consolidate` exactly as `critic-consolidate` already calls it for `review.critic`; the CLI refuses `learning.*`, so no agent can emit one by hand"
      - "no prawduct-internal identifier in text emitted into a governed product → conforms: the blocker names the two lines it wants and the waiver key, never R7 or an issue number; the stubs name the replacement path, never an id"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms: `learning.fired` is appended by `critic-consolidate`, the coordinator's deterministic writeback, never by a reviewer subagent"
      - "authority fails closed; advice fails soft → conforms: the reflection gate's span helper falls back to the porcelain span when the base-tree marker is missing (its jurisdiction shrinks to today's, it does not open) and an unreadable reflection blocks as today; the event emission is advice and degrades to a named NOTE"
      - "local-first, no network, no daemon, no third-party runtime dependency → conforms: git reads and file writes only"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state and the files it must reconcile → conforms, and one write fewer: `reflections.md` is no longer written"
      - "written in Python, never specific to Python → conforms, and less specific than before: the deleted sentinel runner was the plugin's one pytest-shaped assumption"
      - "prawduct guides and reviews; it never implements → inapplicable because nothing here writes product code"
      - "goals and verification bind; prescribed method is advice → conforms: every chunk's Acceptance criteria and Tests are the binding half; Deliverables name sites by the pattern they share"
      - "every fact has one home → conforms: the gate predicate lives in one helper and `session-digest.md` describes it; the event kinds are registered once in `docs/governance-telemetry.md`; the single-resolver allowlist shrinks as each remaining home of `learnings.md` is deleted"
  - artifact: security-model
    dispositions:
      - "untrusted governance state — learnings included — is data, not instructions → conforms: the shape check tests two phrases and interprets nothing; `learning.fired` matches a heading's opening words inside finding text and records a HASH, never the text"
      - "a destructive or irreversible operation requires owner approval at the operation level → conforms: every deletion is of the plugin's own code on a feature branch, reviewed and merged by the coordinator; no product file is deleted or rewritten"
      - "a governed product's content never leaves its repository → conforms: the ledger is gitignored and local"
partition: >-
  Four delegates on opus in isolated worktrees, partitioned by file tree — A (Chunk 01) the
  three lifecycle verbs, the entry-shape check, doctor; B (Chunk 02) the lookup skill, the
  reflections archive, the subagent-briefing embedding, every instruction site and the docstring
  sweep; C (Chunk 03) the reflection gate; D (Chunk 04) the ledger events. Chunk 05 serial
  (coordinator: merge, grep-clean re-derivation, full suite, records, the one review). Shared
  files are shared by NAMED REGION, the rule Wave 1 used for `bin/prawduct-hook`: prawduct-hook
  (A: the three `cmd_` bodies and the two `_EPHEMERAL_*` sets; B: the `cmd_clear` archive block,
  the provenance header and the session-file registry line; C: `cmd_stop` Gate 1; D: `cmd_stop`
  directly after the budget block, nothing else), `skills/critic/review-cycle.md` (A: the
  `learnings-entry-shape` severity row; B: the cumulative-prep line naming the skill; D: one
  sentence in the Learnings Cross-Check), `tests/preferences/test_learnings_single_resolver.py`
  (each deletes only the allowlist entries for files it emptied) and `LAST_MEASURED_TOKENS` (each
  re-measures the files it edited; the coordinator re-measures every pinned file at merge).
  Precedent read: Wave 1 on this branch (three delegates, same rule, one merged `final`); the
  owner asked for multi-subagent execution in the discovery, so no approval round.
last_validated: 2026-09-02
---

## Requirements Confidence

**Level:** Medium

**Why:** R6 is High — every deletion target was opened before the chunk was drawn, and three of
the discovery's listed sites turned out to be already gone or never there (the obligation block in
`init_product.py` / `onboarding_probes.py` went in Wave 1 Chunk 01; `gitignore_probes.py` and
`migrate_plugin.py` name no `reflections` entry; Chunk 02 lists what actually remains). R7 and R9
are Medium because each rests on a choice the discovery left to the plan and #685's own triage
named as the blocking question — the session-work predicate, and what counts as a rule citation.
Both are recorded below as vetoable decisions rather than silently picked.

**Open assumptions / unknowns:**

[ASSUMPTION: a merge-only or pull-only session with the new predicate pays a two-line reflection
("expected: sync develop; actual: same; no defect") — the span is base tree → working tree with
no authorship test | LOW impact — the cost is two lines once, and the shape check makes them two
lines | user can override with an authorship exclusion, which is not cheap]

[ASSUMPTION: a rule unit for the ledger is a `##`/`###` heading OR a top-level `- ` bullet in a
rules file — the fleet holds both shapes (Wave 1's migrate parses the flat-bullet corpus) | MED
impact — the written/fired join keys on the unit's hash | user can correct]

[ASSUMPTION: a Critic finding "cites a rule by heading" when its summary or description contains
the rule's normalized opening eight words (the whole unit when shorter) | MED impact —
under-detection is silent: the count reads low, never wrong | user can override with a schema
field on findings, which is a persisted-format change this plan does not make]

[ASSUMPTION: the session id on both events is the evidence store's session identity
(`evidence._session_epoch`, the `.session-start` marker's mtime) — the Stop payload's
`session_id` is absent at `critic-consolidate`, and one session must have one id on both events
| LOW impact | user can override]

**What would raise confidence:** the owner's yes or no on the two `[DECISION]` blocks in Chunks
01 and 03. Both are one word; both are cheaper to reverse before the delegates dispatch.

## Status

- [x] Chunk 01: Retire the lifecycle verbs, the entry-shape check and doctor's learnings checks
- [x] Chunk 02: Delete the lookup skill, the reflections archive, the briefing embedding and every instruction site
- [x] Chunk 03: The reflection gate fires on the session's work and grades shape
- [x] Chunk 04: Two ledger events — `learning.written` and `learning.fired`
- [x] Chunk 05: Integrate, re-derive every removal, record
Context: Plan drawn 2026-09-02 from the tree at 18767064 (Wave 1 complete). A–D built and merged
2026-09-02 (4ea91ff7 + coordinator fixes). Chunk 03's false-fire analysis, measured by its tests:
FIRES on a committed judgeable change with no plan (the target), an uncommitted one, a new untracked
judgeable file, 200 shapeless characters, and a merge/pull that brought judgeable files (two lines,
once — pinned by a real `git merge --no-ff` in `test_reflection_gate.py`); SILENT on no change,
doc-only or metadata-only spans, a waived gate, a shaped reflection, and a repo without the
base-tree marker (today's behaviour). Residual false-fire class: judgeable files entering the tree
without this session authoring them (merge, pull, rebase, switch). Fixture blast radius was 10
modules, not 18 (the rest read the file without going through the gate); the shape text lives in
`tests/conftest.py::SHAPED_REFLECTION`. Chunk 04 live check (2026-09-03, this worktree, repo-local
hook): one heading appended to core.md, two Stops — the ledger gained 2 `learning.written` lines on
the first Stop (the appended heading, and the unit R-15 re-worded this session: an EDITED rule hashes
as a new unit, so a rewording reads as a write — hash identity, recorded not fixed) and 0 on the
second; the review's resolution round produced 3 `learning.fired` lines. Review
rev-20260902T232816Z-f97fa40b: 2 blocking + 9 warning + 7 note, all fixed or accepted; one
verify-resolutions round found the untested raise arm of R-1's fix; the second (rev-20260903T002619Z-7276f933) was clean. Wave 2 complete 2026-09-03; the plan stays live until the release ships.

## Scaffolding

### Project Initialization

None — existing plugin. No new modules; one new test file per chunk where named.

### Dependencies

None added. `hashlib` and `re` from the standard library.

### Build & Test Configuration

`uv run pytest -q` runs the suite (`-n 5 --dist loadfile`). A fresh worktree needs
`uv sync --extra dev` first, or `uv run pytest` falls through to the pyenv shim and two
backlog-cache WAL tests fail on the wrong sqlite (Wave 1 reflection). Box load over 12 doubles
the suite; nested-pytest tests were widened to 90s. A delegate's ceiling is named per chunk; the
coordinator runs the full suite at merge and records it with `prawduct-hook test-evidence record`.

### Scaffold Verification

Not applicable — nothing is scaffolded.

### Verification Strategy

Beyond tests, three live checks in this worktree. After Chunk 01 merges: `python3
plugin/bin/prawduct-hook audit-learnings --json` prints one `WARNING:` on stderr, nothing on
stdout, exit 0. After Chunk 03 merges: `/clear`, commit a one-line code change with no plan
active, end the turn — the reflection blocker fires, names the two lines it wants, and a two-line
reflection satisfies it. After Chunk 04 merges: append one `### ` heading to `core.md`, end the
turn twice — `.prawduct/.governance-ledger.jsonl` gains exactly one `learning.written` line; then
read the ledger after Chunk 05's own Critic review — reviewers who quoted a rule produced
`learning.fired` lines, which is the loop measuring itself for free.

## Project Structure

```
plugin/lib/audit_learnings_cmd.py          # DELETED (01)
plugin/lib/learnings_obligation.py         # DELETED (01)
plugin/lib/record_lint.py                  # − _check_learnings_shape, − learnings-entry-shape (01)
plugin/skills/learnings/                   # DELETED (02)
plugin/lib/briefing.py                     # − the Active Learnings section of .subagent-briefing.md (02)
plugin/lib/gates.py                        # + session_work_span, + reflection_shape (03)
plugin/lib/ledger.py                       # + learning.* kinds, one shared append, CLI refusal (04)
plugin/lib/learnings_files.py              # + rule_units, + unit_hash (04)
plugin/lib/critic_consolidate.py           # + learning.fired after the review.critic anchor (04)
plugin/bin/prawduct-hook                   # 01: three inert stubs · 02: cmd_clear archive gone · 03: Gate 1 · 04: learning.written
plugin/docs/governance-telemetry.md        # + the two kinds (04)
plugin/hooks/gates.json                    # reflection row's summary (03)
tests/test_deprecated_inert_commands.py    # + three verbs (01)
tests/test_reflection_gate.py              # NEW (03)
tests/test_learning_events.py              # NEW (04)
tests/test_audit_learnings.py, test_learnings_obligation.py, test_learnings_pairing.py,
tests/test_reflection_provenance.py, tests/spikes/learning_families.py   # DELETED (01, 02)
```

### Module Boundaries

Every reader of the rules files still goes through `learnings_files.resolve()`; the two new
helpers there (`rule_units`, `unit_hash`) are the ONE definition of "a rule" and its hash, used by
`cmd_stop` and `critic_consolidate` alike. `lib.ledger` is the one writer of the ledger; the
learning emitters call its append, never `open()`. `gates.session_work_span` is the one answer to
"what did this session change"; in this wave only Gate 1 reads it (Chunk 03's decision).

## Build Chunks

### Chunk 01: Retire the lifecycle verbs, the entry-shape check and doctor's learnings checks

- **Description:** The three lifecycle verbs lose their bodies and become deprecated-inert
  stubs; their modules, their tests, the record-lint shape check, the sentinel keys and every
  doctor instruction that runs them are deleted. Delegate A.
- **Depends on:** none
- **Artifacts consumed:** discovery R6 (the audit / obligation / pairing / shape / sentinel /
  registry items); `api-contract.md` § Direction (the deprecation norm) and § Operations (the
  `regen-views (deprecated, inert)` listing); `tests/test_deprecated_inert_commands.py` (the
  precedent whose contract the stubs inherit — copy its cases first).
- **Deliverables:**
  - `[DECISION: audit-learnings, learnings-obligation and check-learnings-pairing stay
    dispatchable as deprecated-inert stubs (exit 0 always, unknown flags accepted, one WARNING: on
    stderr naming that the lifecycle audit is gone and rules live in .claude/rules/learnings/,
    nothing on stdout, nothing written) rather than being deleted from the dispatcher | the
    api-contract deprecation norm governs every verb a human or a skill can call, and D1 chose a
    minor; the shape is the regen-views precedent | user can veto: delete outright and record an
    exception]`
  - `plugin/bin/prawduct-hook`: the three `cmd_` bodies replaced by stubs modelled on
    `cmd_regen_views`; the usage strings keep the verbs (a deprecated verb is still a verb); the
    lazy `run_audit_learnings` path is gone. `_EPHEMERAL_APPLY_GATED_COMMANDS` drops all three and
    `_EPHEMERAL_SAFE_COMMANDS` gains them — that set is an allowlist of READS and an unlisted
    command is REFUSED inside an ephemeral worktree, which would break the stub's exit-0 promise;
    a stub writes nothing, so it belongs with the reads. Verify by reading the two sets' comments
    before moving anything.
  - deleted `plugin/lib/audit_learnings_cmd.py`, deleted `plugin/lib/learnings_obligation.py`,
    deleted `tests/test_audit_learnings.py`, deleted `tests/test_learnings_obligation.py`,
    deleted `tests/test_learnings_pairing.py`, deleted `tests/spikes/learning_families.py`.
  - `plugin/lib/__init__.py`: the `run_audit_learnings` lazy-import entry.
  - `plugin/lib/record_lint.py`: `_check_learnings_shape`, the `learnings-entry-shape` id in the
    check roster, and the unchecked-line that names it; `tests/test_record_lint.py`
    `TestLearningsEntryShape` and every other assertion naming the id.
  - `plugin/templates/project-state.yaml`: the `sentinel_command` / `sentinel_ungraded_exit_codes`
    comment block; `plugin/lib/coverage_algebra.py`'s comment citing `test_audit_learnings`;
    `plugin/lib/norm_index_scaffold.py`'s docstring "shape mirrors `lib.learnings_obligation`"
    rewritten to say the shape in its own words (a citation of a deleted module is a dangling
    pointer).
  - `plugin/skills/doctor/SKILL.md`: the three verbs leave `allowed-tools`; the routing-table row
    about the descent obligation, Health Checks 13 and 13a, the whole "Audit-Learnings Flow"
    section and the "Important Notes" sentence about it are deleted; the `description:` line stops
    saying "audit learnings". Renumber nothing — a gap in the check numbers is a smaller change
    than a renumbering every cross-reference would have to follow.
  - `plugin/skills/critic/review-cycle.md`: the `learnings-entry-shape` severity row;
    `plugin/skills/critic/goals-1-3.md`: the `learnings-entry-shape → NOTE` clause. Ratchet both
    files' `LAST_MEASURED_TOKENS` entries DOWN in the same commit.
  - `documentation/project-structure.md`: the `test_audit_learnings.py` line.
  - Tests updated by pattern — every test file that names one of the three verbs, the lazy-import
    entry, the shape id or the ephemeral sets: `tests/test_hook_argument_shape.py`,
    `test_ephemeral_worktree.py`, `test_lib_lazy_imports.py`, `test_operator_verification.py`,
    `test_plugin_runtime.py`, `test_backlog_instruction_surface.py`, `test_atomic_state_writes.py`,
    `test_norm_index_scaffold.py`, `tests/preferences/test_critic_skill_structure.py`. Find them by
    grep, not from this list.
  - `tests/preferences/test_learnings_single_resolver.py`: delete the allowlist entries for
    `audit_learnings_cmd.py`, `learnings_obligation.py`, `record_lint.py` and `plugin/skills/doctor/SKILL.md`
    once each no longer names `learnings.md`. Leave `bin/prawduct-hook`'s entry (Chunk 05 settles
    it — the migrate command's docstring still names the legacy path).
- **Tests:** `tests/test_deprecated_inert_commands.py` extended with the three verbs on the
  precedent's four-point contract (exit 0 with and without flags; `WARNING:` on stderr; stdout
  empty; nothing on disk changes); the record-lint roster test asserts the id is gone;
  `test_the_allowlist_holds_no_stale_entries` green.
- **Acceptance criteria:** `uv run pytest -q tests/test_deprecated_inert_commands.py
  tests/test_record_lint.py tests/test_hook_argument_shape.py tests/test_ephemeral_worktree.py
  tests/test_lib_lazy_imports.py tests/test_plugin_runtime.py tests/test_operator_verification.py
  tests/test_backlog_instruction_surface.py tests/test_atomic_state_writes.py
  tests/test_norm_index_scaffold.py tests/preferences tests/test_v5_methodology.py` passes;
  `grep -rn "audit_learnings\|learnings_obligation\|learnings_pairing\|learnings-entry-shape\|_check_learnings_shape\|sentinel_command\|sentinel_ungraded" plugin tests documentation/project-structure.md`
  returns only the three stubs, their test, and `plugin/CHANGELOG.md` history.
- **Critic mode:** final (reviewed in Chunk 05's merged review — no separate round)
- **Done when:**
  1. Acceptance criteria met and tests pass on the delegate branch
  2. Merged by the coordinator; reviewed in Chunk 05's `final`; blocking findings resolved
  3. Chunk marked `[x]` in Status by the coordinator after that review

### Chunk 02: Delete the lookup skill, the reflections archive, the briefing embedding and every instruction site

- **Description:** Everything that still tells an agent to look rules up, archive reflections, or
  read a learnings file by its old name goes — code and prose, plugin and repo root. Delegate B.
- **Depends on:** none
- **Artifacts consumed:** discovery R6 (skill + instruction sites; `reflections.md` archive,
  provenance, registry; the briefing embedding), §5 (archive deleted, not ceded); the Wave 1
  handoff's sweep list (README.md's three-tier narrative, CLAUDE.md's fleet-scan line,
  `documentation/`); the single-resolver allowlist's `wave-2` entries, which name every docstring
  site the sweep owes.
- **Deliverables:**
  - deleted `plugin/skills/learnings/` (whole), deleted `tests/test_reflection_provenance.py`.
  - `plugin/lib/buildplan_refs.py`: `/prawduct:learnings` leaves the slash-command resolution
    set; `tests/test_path_reference_resolution.py` follows.
  - Instruction sites, each rewritten to the harness-loaded model or deleted: `methodology/planning.md`
    § "Learnings as Design Constraints" becomes two sentences (rules are loaded by the harness —
    `core.md` every session, an area file on a matching read — so before planning, open the area
    files whose `paths:` cover the files the work will touch); `methodology/building.md` where it
    names the skill; `methodology/session-digest.md`'s skill list; `skills/methodology/SKILL.md`;
    `skills/pr/SKILL.md`'s prep line; `skills/critic/review-cycle.md`'s cumulative-prep line (that
    line ONLY — Chunks 01 and 04 own other regions of the file); `methodology/reflection.md` ONLY
    where a sentence names the skill or the `reflections.md` archive — Wave 3's R8 rewrites the
    file, so do not restructure it; `README.md` § "Closed learning loop" (the three-tier paragraph
    becomes one about `.claude/rules/learnings/`); `CLAUDE.md`'s fleet-scan cell (scan for
    `.claude/rules/learnings/`); `documentation/project-structure.md` (the skill directory line,
    and `reflections.md` if listed).
  - The reflections archive: in `plugin/bin/prawduct-hook`, `cmd_clear`'s "preserve previous
    session's reflection" block, `_reflection_provenance_header` and the comment block above it,
    and the `reflections.md` line in the session-file registry; `plugin/lib/core.py`'s registry
    line. `.session-reflected` stays in the doomed list unconditionally (nothing gates its removal
    any more). **Keep the handoff's "Previous Session Reflection" section** (`briefing.py`): it
    reads the file before the boundary deletes it — verify the order and pin it.
  - The briefing embedding: `plugin/lib/briefing.py`'s "Active Learnings" section of
    `.subagent-briefing.md`, and the tests that assert it.
  - The docstring sweep — every citation of the form ``(learnings.md: "…")`` in `lib/coverage.py`,
    `lib/telemetry.py`, `lib/evidence.py`, `lib/critic_consolidate.py`, `lib/gates.py`, plus the
    record list in `lib/coverage_algebra.py`, `skills/janitor/SKILL.md`, `skills/onboard/SKILL.md`,
    `skills/migrate/SKILL.md`: the RULE citation stays (by its heading words), the FILE name
    becomes "the learnings rules" or `core.md`. The single-resolver allowlist entries for every
    file this chunk empties are deleted in the same commit; the test names any you missed.
  - Ratchet `LAST_MEASURED_TOKENS` for every pinned file edited (planning, building, reflection,
    review-cycle, session-digest's two totals, CLAUDE.md) in the same commit; the digest's
    character ceiling (`tests/test_plugin_methodology_digest.py`) is in the ceiling below.
  - Report: the backlog item #661 ("stamp the running version at write time") is about the
    provenance header this chunk deletes — say so in the return; the coordinator closes it.
- **Tests:** `tests/test_hook_session_file_registry.py` and `tests/test_session_boundary_events.py`
  updated (no `reflections.md` write at `/clear`; `.session-reflected` removed at `/clear`; the
  handoff still carries the previous reflection — pin the ORDER, that is the property);
  `tests/test_briefing_extraction.py` / `test_briefing_functions.py` assert the section is absent
  and the rest of the briefing survives; `test_path_reference_resolution.py` no longer resolves the
  skill; `test_only_the_allowlist_names_the_legacy_corpus` and its stale-entry twin green.
- **Acceptance criteria:** `uv run pytest -q tests/test_hook_session_file_registry.py
  tests/test_session_boundary_events.py tests/test_briefing_extraction.py
  tests/test_briefing_functions.py tests/test_path_reference_resolution.py tests/test_handoff_affordance.py
  tests/preferences tests/test_v5_methodology.py tests/test_plugin_methodology_digest.py` passes;
  `grep -rn "prawduct:learnings\|reflections\.md\|reflection_provenance\|Active Learnings" plugin tests README.md CLAUDE.md documentation`
  returns only `plugin/CHANGELOG.md` history, `documentation/issues/` history, and test ASSERTION
  strings that guard the absence (a guard must name what it forbids).
- **Critic mode:** final (reviewed in Chunk 05's merged review)
- **Done when:**
  1. Acceptance criteria met and tests pass on the delegate branch
  2. Merged by the coordinator; reviewed in Chunk 05's `final`; blocking findings resolved
  3. Chunk marked `[x]` in Status by the coordinator after that review

### Chunk 03: The reflection gate fires on the session's work and grades shape

- **Description:** Gate 1 stops asking "is a build plan active" and "is porcelain dirty", and
  asks "did this session change judgeable code" of the session's tree span; it stops counting
  characters and asks for two lines. Delegate C.
- **Depends on:** none
- **Artifacts consumed:** discovery R7; backlog #685 (the problem and its acceptance: a
  reasoned false-fire rate, a trivial session still ends silently) and #304's comment (the
  primitives — `.session-base-tree` at `gates._read_session_base_tree`, the companion `doc_only`
  trap); `tests/test_learnings_cutover_gate.py` (Wave 1's Stop-gate test precedent — copy its
  fixture shape); `tests/test_critic_gate_fallthrough.py` (which pins that `has_build_plan` decides
  whether the gates run — that pin changes meaning here and is renegotiated in the open, not
  deleted).
- **Deliverables:**
  - `[DECISION: "code changed this session" is the tree span from the .session-base-tree marker to
    the working tree, computed by one helper in lib/gates.py; when the marker is missing the helper
    returns the porcelain span (today's behaviour) and says which it used. In this wave ONLY Gate 1
    reads it; the Critic composition gate keeps its porcelain guard and its own doc_only, with a
    comment naming the helper as the guard #304 flips | #685's triage asked exactly this
    question; a reflection false-fire costs two lines, a Critic-gate false-fire costs a review round
    the P0 wall-clock rule prices, and the merge-only case for the Critic gate has not been
    reasoned about — #304 stays open holding that flip | user can veto: flip both gates now]`
  - `plugin/lib/gates.py`: `session_work_span(project_dir, status_output=None) -> dict` with keys
    `changed` (non-metadata paths), `judgeable` (bool, via `coverage_algebra.judgeable_files`) and
    `source` (`"base-tree"` | `"porcelain"`). **Cost bound:** this runs on EVERY Stop, which is
    every turn — no temp-index capture here. Tracked changes come from one `git diff --name-only
    <base-tree>` against the working tree; untracked, non-ignored files come from the porcelain
    snapshot `cmd_stop` already holds. `reflection_shape(text) -> tuple[bool, list[str]]`: ok when
    the text contains both `expected` and `actual` (case-insensitive, anywhere) AND one of
    `root cause` / `root-cause` / `no defect`; the list names what is missing, in the words the
    blocker prints.
  - `plugin/bin/prawduct-hook` `cmd_stop` Gate 1: `reflection_would_block = span.judgeable and
    not shape_ok` — no `has_build_plan` conjunct, no length floor, `doc_only` for THIS gate derived
    from the span. The planless advisory branch is gone (it is the blocking branch now). The blocker
    text names the two lines it wants and drops "archived to reflections.md"; the waiver hatch and
    the rule-destination sentence stay. The message must not mention a character count.
  - **False-fire analysis (the #685 acceptance), written into the chunk's Context line with the
    numbers from the tests:** fires on — a committed judgeable change with no plan (the target); a
    merge or pull that brought judgeable files (two lines, once). Silent on — no change; doc-only
    or metadata-only spans; a waived gate; harness-tracked background work in flight (the STH-3W7F
    deferral is unchanged); a repo with no base-tree marker behaves exactly as today.
  - `plugin/hooks/gates.json`: the `reflection` row's `summary` says what the gate now asks;
    `since` is unchanged (the gate is not new — the banner announces new gates, and this one has
    existed since 1.0.0; the widening is a CHANGELOG paragraph in Chunk 05).
  - Prose that DESCRIBES the old predicate, found by grep for the claim not the code:
    `methodology/session-digest.md` § Enforcement ("they BLOCK when code changed against an active
    build plan with no review or reflection captured" — now: no reflection when judgeable code
    changed this session; no review when that change was against an active plan);
    `methodology/building.md` "Gate waivers" and any sentence stating the plan conjunct or the
    floor; `methodology/reflection.md` where it states the floor; `CLAUDE.md`'s "(a reflection
    exists)" parenthesis. Ratchet `LAST_MEASURED_TOKENS`, the digest totals and the digest
    character ceiling in the same commit.
  - **Fixture blast radius, priced here so it is not discovered at build time:** 18 test files
    write `.session-reflected` at 42 sites, most as a fifty-plus-character sentence with no shape.
    Every fixture that must satisfy the gate gains the two phrases. Fixture DATA changes; no
    assertion weakens. One helper string in `tests/conftest.py` (or the gate test module) is the
    single source of the satisfying text, so the next shape change is one edit.
- **Tests:** new `tests/test_reflection_gate.py`, mirroring the cutover-gate file's fixture shape:
  planless repo, committed judgeable change, no reflection → blocks and names both lines;
  shape present → passes; 200 characters without shape → blocks; doc-only committed change →
  silent; metadata-only → silent; no marker + dirty porcelain → blocks (today's behaviour);
  no marker + clean porcelain + committed change → silent (today's behaviour, the fallback is
  pinned); waiver honoured; the Critic gate's guard unchanged by a committed planless change
  (the decision's other half, pinned). Red-verify the shape check by deleting one conjunct.
- **Acceptance criteria:** `uv run pytest -q tests/test_reflection_gate.py
  tests/test_learnings_cutover_gate.py tests/test_session_critic_gate.py
  tests/test_critic_gate_fallthrough.py tests/test_stop_gate_error_posture.py
  tests/test_stop_abandoned_critic.py tests/test_critic_session_guard.py
  tests/test_handoff_affordance.py tests/preferences tests/test_v5_methodology.py
  tests/test_plugin_methodology_digest.py` passes, plus every file the 18-file grep names; the
  live check in Verification Strategy passes after merge.
- **Critic mode:** final (reviewed in Chunk 05's merged review)
- **Done when:**
  1. Acceptance criteria met and tests pass on the delegate branch
  2. Merged by the coordinator; reviewed in Chunk 05's `final`; blocking findings resolved
  3. Chunk marked `[x]` in Status by the coordinator after that review

### Chunk 04: Two ledger events — `learning.written` and `learning.fired`

- **Description:** The loop measures itself: a rule written this session and a rule a Critic
  finding cited each append one line to the governance ledger. Delegate D.
- **Depends on:** none (reads Wave 1's `learnings_files.resolve`)
- **Artifacts consumed:** discovery R9; audit §5 Principle 6 ("measure the loop or do not claim
  it") and its telemetry row; `docs/governance-telemetry.md` (the registry this chunk owes rows
  to); `lib/ledger.py` (the writer and its `review_event_exists` idempotence shape);
  `critic_consolidate.consolidate`'s `review.critic` anchor (where `learning.fired` lands).
- **Persisted format — the questions the data must answer, elicited before fields:** (1) how
  many rules were written per session, per scope, per repo, over a window; (2) which rules fire —
  are cited by a finding — how often, and in which review; (3) which rules never fire, by joining
  the corpus's units against `fired` on the unit hash; (4) all of the above across a fleet, keyed
  by the envelope's `project`. Nothing here reads the events yet; the format is a lock-in decision
  and these four are its requirements.
- **Deliverables:**
  - `plugin/lib/learnings_files.py`: `rule_units(text) -> list[str]` — the `##`/`###` headings
    below the file's title (never the title, never the scaffold's obligation header) and the
    top-level `- ` bullets; `unit_hash(text) -> str` — lowercase, whitespace collapsed, trailing
    punctuation stripped, sha256, first 16 hex. The ONE definition both emitters use.
  - `plugin/lib/ledger.py`: `_EVENT_ROLES` gains `learning.written: builder` and
    `learning.fired: critic`; the envelope-and-append body of `ledger_append` is extracted into one
    private function every kind uses; `ledger_append` (the CLI) REFUSES `learning.*` with exit 1
    and a reason (emitted by the Stop hook and critic-consolidate, never by hand);
    `append_learning_event(project_dir, kind, *, file, unit_hash, review_id=None) -> bool` builds
    the payload `{"learning": {"file", "unit_hash", "session", "review_id"}}` under the standard
    envelope, and is idempotent by `(kind, session, file, unit_hash, review_id)` through a
    `learning_event_exists` probe in the `review_event_exists` shape. `session` is
    `evidence._session_epoch(project_dir)` (nullable, never invented). `schema_version` stays 1.
  - `plugin/bin/prawduct-hook` `cmd_stop`, directly after the budget block and nowhere else: when
    the base-tree marker resolves, for each file the resolver returns, the units at the base
    revision (`git show <base>:<rel>`; a file absent at base has every unit new) against the units
    now — one `learning.written` per new hash. Best-effort: a failure is one `NOTE:` on stderr
    saying the event was not recorded. When the marker is missing, the existing "unchecked — no
    .session-base-tree marker" line ALSO says `learning.written` was not recorded — one message
    derived from one state, not a second message for the same state. The Stop hook runs every
    turn, so the idempotence key is what keeps this at one line per rule.
  - `plugin/lib/critic_consolidate.py`: after the `review.critic` anchor, for each finding in the
    consolidated record and each unit in EVERY file the resolver returns (a finding may cite a
    rule from any loaded file), when the normalized `summary + recommendation` (the two prose
    fields a cache record carries — the plan first said `description`, which no finding has)
    contains the unit's
    normalized opening eight words (the whole unit when shorter): one `learning.fired` carrying the
    review id. Failure is a NOTE; consolidation's exit code is unaffected.
  - `plugin/skills/critic/review-cycle.md` § Learnings Cross-Check, one sentence (this region
    only): when a finding rests on a rule, quote the rule's opening words in the finding so the
    citation is countable. Ratchet `LAST_MEASURED_TOKENS` in the same commit — Chunk 01's row
    deletion funds it; the coordinator settles the net at merge.
  - `plugin/docs/governance-telemetry.md`: the two kinds, their payload, roles, the idempotence
    key, the session identity, and that `review-stats` counts them under `skipped.unknown_kinds`
    by v1's contract (a JSON key is never repurposed; the label is documented, not renamed).
- **Tests:** `tests/test_learnings_files.py` — `rule_units` on a heading corpus, a bullet corpus,
  and a mixed one; the title and obligation header excluded; `unit_hash` stable across case and
  whitespace and different across two real headings; **one test reads the real
  `.claude/rules/learnings/core.md`** and asserts every unit hashes uniquely (a collision check
  against real data, not a fixture). `tests/test_governance_ledger.py` — the CLI refuses
  `learning.*`; `append_learning_event` envelope, role, payload, nullable session; a second call
  with the same key appends nothing. new `tests/test_learning_events.py` — Stop emits one line per
  new unit, none for unchanged files, none on a second Stop, none and a NOTE when the marker is
  missing, none when the append raises (and the gate's exit code is unchanged); consolidate emits
  `fired` for a finding quoting a unit's opening and nothing for a finding that does not, and does
  not double-emit on re-consolidation. Red-verify the idempotence probe by breaking its key.
- **Acceptance criteria:** `uv run pytest -q tests/test_learnings_files.py
  tests/test_governance_ledger.py tests/test_learning_events.py tests/test_review_stats.py
  tests/test_critic_consolidate.py tests/test_learnings_cutover_gate.py tests/preferences
  tests/test_v5_methodology.py` passes (name the consolidate test module by grep if it differs);
  the live check in Verification Strategy passes after merge.
- **Critic mode:** final (reviewed in Chunk 05's merged review)
- **Done when:**
  1. Acceptance criteria met and tests pass on the delegate branch
  2. Merged by the coordinator; reviewed in Chunk 05's `final`; blocking findings resolved
  3. Chunk marked `[x]` in Status by the coordinator after that review

### Chunk 05: Integrate, re-derive every removal, record

- **Description:** The coordinator merges the four branches, re-derives every deletion by grep
  (a delegate's "done" on a removal is the `Done taken on faith` anti-pattern), runs the suite
  from a synced venv, writes the records, and runs the wave's one review.
- **Depends on:** Chunks 01–04
- **Artifacts consumed:** discovery R6 proof ("grep-clean for every removed verb"), R13 (the
  records Wave 3 owns — this chunk writes only what the same-commit rule demands);
  `api-contract.md` § Operations; the change-log's `scope=` tag idiom.
- **Deliverables:**
  - Merges `--no-ff` in the order A, B, C, D; conflicts in `bin/prawduct-hook`, `review-cycle.md`,
    the allowlist and `LAST_MEASURED_TOKENS` resolved by hunk, then every pinned file re-measured
    (the test message carries the number).
  - The grep-clean re-derivation, as ONE command the change-log entry cites:
    `grep -rnE "audit_learnings|learnings_obligation|learnings_pairing|learnings-entry-shape|_check_learnings_shape|prawduct:learnings|reflections\.md|reflection_provenance|sentinel_command|sentinel_ungraded|Active Learnings|learning_families" plugin tests README.md CLAUDE.md documentation .prawduct/cross-cutting-concerns.md .prawduct/artifacts .claude/rules/learnings`
    — expected survivors: the three stubs and their test, test assertion strings that guard an
    absence, `plugin/CHANGELOG.md`, and `documentation/issues/` history. Anything else is a
    delegate's miss and is fixed here.
  - `tests/preferences/test_learnings_single_resolver.py`: the surviving allowlist is
    `learnings_migrate.py` (none), `bin/prawduct-hook` (re-classified `none` — the migrate
    command's docstring names the legacy path because reading it is its job), `reflection.md` and
    `norms.md` (wave-3). Every `wave-2` entry is gone or the test says which.
  - `.prawduct/artifacts/api-contract.md` § Operations: the three verbs listed as
    `(deprecated, inert)` beside `regen-views`; the narrative contract change is Wave 3's R13.
  - `plugin/CHANGELOG.md`, the unreleased section: one paragraph per change a consumer sees — the
    three verbs deprecated; `/prawduct:learnings` removed (rules are harness-loaded);
    `reflections.md` no longer written; the reflection gate fires on any session that changed
    judgeable code and asks for two lines; two ledger events. The section's rename is the release.
  - `.prawduct/change-log.md`: one entry, `type=feat | scope=learnings-v2-delete`, whose body
    covers all five chunks (the body IS the release note — a chunk the prose omits ships invisibly).
  - Full suite from `uv sync --extra dev`, recorded with `prawduct-hook test-evidence record`.
  - Backlog comments via `/prawduct:backlog` (no status flips — status moves at Wave 3's release):
    #685 resolved by Chunk 03 with the false-fire analysis; #304 pointed at `session_work_span`;
    #661 moot by Chunk 02's deletion; #744 Wave 2 complete.
  - `/prawduct:critic final` over the merged tree (Wave 1's 02–04 precedent); every blocking AND
    warning finding fixed (this repo's rule); `verify-resolutions`; then the five boxes ticked.
  - `.prawduct/.handoff-notes.md` rewritten for Wave 3 (reconciled with what is there, never
    blind-appended).
- **Tests:** the full suite; the grep above returning only the expected survivors is the
  acceptance test for R6 and is recorded in the change-log entry with its survivor list.
- **Acceptance criteria:** full suite green from a synced venv; `prawduct-hook test-status` exit 0;
  the grep's survivors are exactly the expected set; `prawduct-hook verify-records` clean;
  the three live checks in Verification Strategy done in this worktree.
- **Critic mode:** final
- **Done when:**
  1. Acceptance criteria met and the suite recorded
  2. `/prawduct:critic final` run; blocking and warning findings resolved; `verify-resolutions` clean
  3. Committed; Chunks 01–05 marked `[x]` in Status; handoff notes written

## Early Feedback Milestone

**Milestone chunk:** 03
**What the user can do:** end a turn in this worktree after committing a one-line code change
with no plan active, watch the reflection gate fire and name the two lines it wants, write them,
and watch it pass — the gate firing on the common case is the whole of #685.

## Governance Checkpoints

**Commit & PR cadence:** delegates commit on their branches; the coordinator merges each with
`--no-ff`, runs the full suite once, and records the evidence. One review for the wave (Chunk 05's
`final`); the program's `cumulative` is Wave 3's PR gate, as Wave 1's plan already says. No PR
until Wave 3 closes the release.

- After the merge, before the review: the grep-clean re-derivation. Every removal is re-derived by
  the coordinator, not read from a report.
- After the review: reflect, and decide the candidate rule Wave 1's reflection deferred to this
  wave ("a destructive command carries its own losslessness check; a test proving it is not a
  substitute") with a second corpus in view — promote it to `core.md` and pay the budget gate, or
  say why not.
- Before Chunk 05 ticks: `prawduct-hook check-releasability` reads the new `scope=` tag against
  this plan's frontmatter — the tag is `learnings-v2-delete`, never the neighbouring entry's.
