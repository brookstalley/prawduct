# Slice D: operational skills (`plugin/skills/**` except `critic/` and `pr/`)

## Inventory

Every file below was read in full, top to bottom. Word counts are from `wc -w`.

| File | Words |
|---|---|
| `plugin/skills/ping/SKILL.md` | 146 |
| `plugin/skills/repo-disable/SKILL.md` | 445 |
| `plugin/skills/advisory/SKILL.md` | 452 |
| `plugin/skills/methodology/SKILL.md` | 790 |
| `plugin/skills/migrate/SKILL.md` | 810 |
| `plugin/skills/backlog/cache-reads.md` | 1,077 |
| `plugin/skills/runbook/SKILL.md` | 1,919 |
| `plugin/skills/onboard/SKILL.md` | 2,507 |
| `plugin/skills/report-bug/SKILL.md` | 2,909 |
| `plugin/skills/backlog/adapter-mode.md` | 4,180 |
| `plugin/skills/janitor/SKILL.md` | 5,180 |
| `plugin/skills/backlog/migration-scrub.md` | 6,582 |
| `plugin/skills/backlog/SKILL.md` | 6,622 |
| `plugin/skills/doctor/SKILL.md` | 7,971 |
| **Total** | **41,590** |

**Budgets.** No file in this slice has a token or size ceiling in `tests/`. `cache-reads.md` is named in `tests/test_reviewer_payload_budget.py`, but only as a read outside the priced sums. Trims here change no ceiling.

**Machine-read check.** Every string literal in `tests/**/*.py` was cross-checked against these files (script: `pins_D.py`, output: `pins_D.txt`, both in this directory). Where a decision touches a string a test asserts, it says so and sets `machine_read: yes`. Every replacement below keeps the pinned phrases unless it says otherwise.

`advisory/SKILL.md` and `report-bug/SKILL.md` are clean apart from shared-duplicate items. The report-bug procedure (recompose, preview, show the exact outbound bytes, send with a digest) and its shell-quoting rationale are a fragile, exact procedure and stay as written.

## Summary

The largest cut is **doctor/SKILL.md**, which is mostly maintainer rationale and incident history inside health checks the model runs on every invocation. Checks #1, #4, #11, #14, #15 and #18 each explain why the check was built, what an earlier version got wrong, and the rule that a check which could not run is "degraded because ungraded". That rule is stated seven times; it should be stated once, and each check can keep its statuses and grading. **migration-scrub.md** keeps every command, gate list and ordering. It sheds its incident archaeology: the `samsung-frame-art-loader` story, a "Corrected 2026-07-24: this previously read…" note, version-pinned release history, a retired drop-box, and spec ids such as MG4, GV7 and API §2.4. It also has one real defect: the `duplicate_alias` fold text sits under the `unencodable_status` bullet and repeats the paragraph that follows it. **backlog/** has three problems. `adapter-mode.md` documents a `queued` envelope that no code emits. The Issues-backend update rules and upstream-filing mechanics are copied between files. And `add` offers delegation first. **janitor/SKILL.md** points the model at "this project's CLAUDE.md" for planning and build-cycle guidance, but in a product repo that file is now a thin anchor with no such guidance. Counts: 61 decisions — rewrite 48, remove 10, move 3, flag 0 — with 22 at high confidence and 39 at medium. Three are `machine_read: yes` (D-2, D-29, D-30) and one is `model_dependent: yes` (D-40).

## Decisions

### D-1: One statement of "degraded because ungraded" in doctor
- location: `plugin/skills/doctor/SKILL.md:42-87`
- evidence: "Same rule for the state file itself being undecodable: **degraded because ungraded** — say the check declined, never that it passed."
- pattern: 1c padding (repetition as reinforcement); #342 duplicated fact within one file
- why: One rule and its full rationale ("a check that could not run is otherwise indistinguishable from one that did and found nothing") are restated at #1, #4, #11, #14, #15, #19 and #20. Current models retain a rule they read once, and the model treats every copy as actionable, reconciling wordings on each trigger of a skill that is already 8k words.
- confidence: high
- action: rewrite
- replacement: Replace the paragraph at line 42 with:

  "Plugin-native — the *subject* of every check is the consumer's OWN `.prawduct/` and `.claude/`, read with Read / Glob. **A check that could not run is degraded because ungraded:** when a command exits "could not run", reports `unknown` or `null`, or the file it grades is undecodable, say the check declined — never that it passed — because a check that could not run otherwise reads exactly like one that found nothing. Each check below names its could-not-run statuses. Check:"

  In each check, cut the restated rationale down to the status plus that label. Worked examples:
  - #4: "`unreadable` — `CLAUDE.md` is not decodable text; the command exits **1**. Degraded because ungraded."
  - #19: "`unknown` (exit **3**) means the check could not run — degraded because ungraded."
  - #20: "`null` is degraded because ungraded."

  Keep the literal phrase `degraded because ungraded` inside Check #1. `tests/test_install_reference_probes.py` asserts it there.
- model_dependent: no
- machine_read: no

### D-2: Health Check #1 — drop the design rationale and the self-cancelling field list
- location: `plugin/skills/doctor/SKILL.md:44-46`
- evidence: "and it exists precisely because reading the value any other way means transcribing it (which drifts) or parsing Python (which breaks on a refactor that changes nothing about the contract)"
- pattern: Group 2, verbose SKILL.md and history narrative; 1a (emphasis runs: "every leaf means every leaf", "never grade against the list in this sentence")
- why: The check lists four fields and then spends two sentences telling the reader not to use them. It also explains why the command exists and why the advisory routes here. None of that changes what the model does. The operative content is: run the command, compare every leaf, and treat a non-zero exit as ungraded.
- confidence: high
- action: rewrite
- replacement: "1. **Install reference** — the consumer's `.claude/settings.json` matches the whole install contract. Run `prawduct-hook print-install-reference` and compare every leaf of the JSON it prints: that output is the contract, so do not grade from memory or from the plugin's source. (Shape only — illustrative, not the set: `enabledPlugins["prawduct@prawduct"]`, and `source` and `autoUpdate` under `extraKnownMarketplaces.prawduct`.) Missing or drifted → the next clone seeds from it and has no marketplace to resolve `claude plugin install prawduct@prawduct` against (Check #4 is where a clone learns the install is still theirs to run). The `install-reference` / `contract-drift` advisory routes here, so grade every field it can report.

      A non-zero exit means the plugin's own install reference could not be read — a broken plugin install, not a repo defect. Report the check **degraded because ungraded**, quote its stderr, and do not fall back to the illustrative fields above."
- model_dependent: no
- machine_read: yes. `tests/test_install_reference_probes.py::test_doctor_asks_the_plugin_for_the_contract_rather_than_parsing_it` asserts `prawduct-hook print-install-reference`, `illustrative, not the set` and `degraded because ungraded` within the Check #1 span, and asserts that `lib/migrate_plugin.py` is absent. The replacement keeps all four.

### D-3: Health Check #15 — keep the grading, drop the history
- location: `plugin/skills/doctor/SKILL.md:71`
- evidence: "Build-plan `## Status` checkboxes used to be a *generated view* in repos where `views_enabled` was on"
- pattern: Group 2 history narrative; 1d migration-relative ("used to be", "outlived it", "measured across the fleet")
- why: About 600 words in one paragraph. Most of it is how each residue came to exist and why the author chose to remove the `test_tracking` block whole. The model needs the residue list, what makes each finding degraded, what to lead with, and why `unscoped` is healthy.
- confidence: high
- action: rewrite
- replacement: "15. **Retired `project-state.yaml` residue** — run `prawduct-hook lifecycle-repair` (dry run) and relay what it reports. The residue is the retired `views_enabled` setting, its `scope_rollups:` block, a derived `release-notes.md`, per-plan "do not hand-edit these checkboxes" notes, and the `build_state.test_tracking` block (removed whole, with any `assertion_count` / `test_files` / `history` beside it). **Report degraded when the dry run lists any edit**, and lead with the two that change behaviour. First, the plan note is obeyed by readers while the session gates read those boxes. Second, a stale `test_tracking` number invites an agent to "correct" it, and each correction is a commit that buys a review round. Name where the real figure lives: the test evidence store (`prawduct-hook test-evidence record`, read back with `test-status`). Also degraded: `retired_flag: present` in `--json` (name the key and its line; it came back by someone copying an older state file); a non-empty `unreadable` list (name each path and say the check was partial, because the walk skipped them and "no edits needed" does not cover them); and an undecodable state file (degraded because ungraded). `unscoped` plans are **healthy**. They are still checked for residue, and `--apply` cannot clear the listing, so relay the count and the paths, say that adding a `scope:` is the owner's call, and move on. The repair is offered, never applied for them: see the Lifecycle Convergence Flow."
- model_dependent: no
- machine_read: no. `tests/test_lifecycle_cli.py` pins the JSON key names `retired_flag`, `plans_to_review` and `unreadable`, not this prose; the replacement keeps the key names.

### D-4: Health Check #14 — drop the "previously deferred" archaeology
- location: `plugin/skills/doctor/SKILL.md:69`
- evidence: "It was previously deferred to Check #5, which enumerates `project-state.yaml`, `backlog.md`, `change-log.md` and `artifacts/` and never looks at this file"
- pattern: Group 2 history narrative; 1d
- why: The paragraph narrates when the template stopped shipping the rows, why the fix did not reach existing repos, and which check once mis-graded an absent file. The model needs the statuses and their grades.
- confidence: high
- action: rewrite
- replacement: "14. **Leftover norm-index scaffold rows** — run `prawduct-hook norm-index-scaffold` and relay its status. Two *illustrative* Enforcement rows from older templates have non-empty `Audit home` / `Why` cells, so `norm-health-sweep-overdue` reads them as homed norms and nudges about a sweep the repo does not owe. Report **degraded** on `leftover`, naming the lines, and **healthy** on `ok`. `absent` (no `project-preferences.md`) is **degraded**, because no other check looks at this file; point at `/prawduct:methodology discovery`, which authors it. `unreadable` and `unwritable` (read fine, but the **write** failed and nothing changed) both exit **1** and are degraded because ungraded. Detection is exact-match on the rows prawduct shipped, so an authored or edited row is left alone. **The repair is offered, never applied for them:** the dry run names the file and each line, and the owner runs `prawduct-hook norm-index-scaffold --apply`. The repair is delete-only: it removes those rows and rewrites nothing else, line endings included."
- model_dependent: no
- machine_read: no

### D-5: Health Check #4 — trim the rationale, keep the status table
- location: `plugin/skills/doctor/SKILL.md:49`
- evidence: "Presence of the `PRAWDUCT:ANCHOR` marker is **not** the check: the anchor is the ONLY governance surface a clone on a machine without the plugin ever loads"
- pattern: Group 2 history narrative ("every anchor shipped before this check existed told that reader…, and measured (…)"); 1a caps ("ONLY")
- why: The status list and the repair offer are the contract. The account of what earlier anchors said, and of the measurement that proved it, is archaeology.
- confidence: high
- action: rewrite
- replacement: Replace everything from "Presence of the" through "each routes somewhere different:" with: "The marker's presence is not the check: the anchor is the only governance text a clone without the plugin loads, so what it says matters. Report **healthy** on `ok`, and **degraded** on every other status, each routing differently:" Keep the six status bullets and the repair paragraph, applying D-1 to `unreadable`.
- model_dependent: no
- machine_read: no. `tests/test_plugin_absent_prose.py::test_doctor_grades_the_anchor_by_running_the_command` requires `prawduct-hook reanchor`, every status name in backticks and `--apply` within #4; all are kept.

### D-6: Health Check #8 — cut the "mutating by default on purpose" aside
- location: `plugin/skills/doctor/SKILL.md:61`
- evidence: "(`update-gitignore` is mutating by default on purpose, because it is a repair its other callers want applied;"
- pattern: Group 2 history and design rationale (the parenthetical-aside cluster the brief names)
- why: This is archaeology. The binding instruction ("grade with `--dry-run`, always — never with the bare command") and its reason (a read-only report must not modify the tree) sit two sentences earlier. The aside explains sibling commands' defaults, which changes nothing the model does in this check.
- confidence: high
- action: remove
- replacement: (delete the whole parenthetical, from "(`update-gitignore` is mutating by default" through "forgetting the flag mutates.)")
- model_dependent: no
- machine_read: no. `update-gitignore --dry-run` stays in the check, as `tests/test_doctor_janitor_boundary.py` requires.

### D-7: Lifecycle Convergence — drop "What changed at v3.3.1 (#634)"
- location: `plugin/skills/doctor/SKILL.md:107`
- evidence: "What changed at v3.3.1 (#634): the **mechanical sweep** now declines a plan it cannot evidence as finished"
- pattern: 1d migration-relative plus version pin; Group 2 history narrative ("which archived two unbuilt chunks as shipped in a real product", "The descoped plan this paragraph used to worry about")
- why: The text describes a change against a version the model never saw. The live rules are that `plan-backfill` refuses a plan it cannot evidence as finished, and that a descoped plan goes through `archive-plan` as superseded.
- confidence: high
- action: rewrite
- replacement: "**Two things this flow deliberately does not do.** It never ticks or corrects a checkbox: Health Check #16's plans are reported for a human and left alone, and an archived plan keeps its unticked boxes on purpose. And `plan-backfill` archives a plan only when the plan's own `## Status` evidences completion, because a scope that shipped partially is not a finished plan. A descoped plan is archived **superseded**, which needs a human to name the reason. `prawduct-hook archive-plan <path>` asks no completeness question and is the route for that case."
- model_dependent: no
- machine_read: no

### D-8: Enable-Gate — delete the file-sync fossil
- location: `plugin/skills/doctor/SKILL.md:150`
- evidence: "(There is no `--enable-settings-layout` in the plugin world — "settings layout" was a file-sync"
- pattern: 1d fossil (negates a retired flag); 1c prohibition against a failure the model will not make
- why: Naming a flag that no longer exists can anchor the model toward it. No current surface offers it.
- confidence: high
- action: remove
- replacement: (delete line 150)
- model_dependent: no
- machine_read: no

### D-9: migration-scrub Precondition — keep the two checks, drop the release history and incident
- location: `plugin/skills/backlog/migration-scrub.md:32-58`
- evidence: "backlog service was deliberately withheld from the v3.1.1 and v3.1.2 pruned releases."
- pattern: Group 2 volatile specifics (version pins) and history narrative; 1d ("that was the **v1 file-sync** layout, retired in M4"); incident archaeology ("`samsung-frame-art-loader` was found half-migrated")
- why: The commands (`prawduct-hook backlog`, `prawduct-hook version`, the `--plugin-dir` re-launch) are fragile and stay exact. The pinned versions will rot. The incident story duplicates the reason already given ("the first question is *which build ran it*").
- confidence: high
- action: rewrite
- replacement: "**Precondition. Confirm the running plugin has the backlog service — before anything else.** Every command here is a bare `prawduct-hook backlog …` resolved on `PATH`. Some released builds ship without the `backlog` op, and a build that has the op but predates this runbook's target-binding would run without that safeguard.

     - **Check first, in the repo you are about to migrate:**

           prawduct-hook backlog        # must print the backlog usage, not `unknown op`
           prawduct-hook version        # note it — you will record this

     - **If it prints `unknown op`, or a version older than the one that shipped the service**, stop and re-launch the session against a plugin build that carries it:

           claude <target-repo> --plugin-dir /path/to/prawduct/plugin

       The loaded plugin is the only lever: a plugin-governed repo commits no framework files to fall back to.

     - **Record the plugin version and `--plugin-dir` (if used) alongside the other scrub decisions**, so a migration later found incomplete can be traced to the build that ran it."
- model_dependent: no
- machine_read: no

### D-10: migration-scrub — misplaced and duplicated `duplicate_alias` fold text
- location: `plugin/skills/backlog/migration-scrub.md:447-460`
- evidence: "The number is the only handle that distinguishes the two. **This fold is a migration"
- pattern: #342 duplicated fact; 1c padding (the same content is stated twice, once in the wrong bullet)
- why: Lines 447-451 continue the `duplicate_alias` remedy but sit under the `unencodable_status` bullet, where "the two" and "this fold" have no referent. Lines 453-457 then repeat the `duplicate_alias` bullet's own lines 434-439 ("the merge writes a `superseded_by` redirect … keeping its `id_aliases` entry"). A reader of `unencodable_status` is handed a merge instruction that does not apply to it.
- confidence: high
- action: move
- replacement: Delete lines 447-460 from under `unencodable_status`. Append this to the end of the `duplicate_alias` bullet (after line 439): "This fold is a migration repair, not a confirmed disposition — it reconciles two target issues onto one source item — so run it here, before the gate passes. **Do not hand-edit the loser's body to strip the id**: that breaks the refs the redirect keeps working, and `backlog update --body` cannot do it anyway (it re-appends the original block and reports `ok`)."
- model_dependent: no
- machine_read: no
- dup_of: `plugin/skills/backlog/migration-scrub.md:434-439`

### D-11: migration-scrub `all` scope — drop the correction note and pacer internals
- location: `plugin/skills/backlog/migration-scrub.md:264-279`
- evidence: "2026-07-24: this previously read "Only the create is paced (`Pacer.before_create`"
- pattern: Group 2 history narrative ("an earlier draft said", in its purest form); Group 2 volatile specifics (`_PacingTransport`, 900 points/minute, BKL-3H7W, VRF-009, "Chunk 04")
- why: An inline erratum that quotes the superseded sentence re-teaches the wrong rule, and the decorator mechanics are code facts the model neither needs nor can check. What the owner must hear is two writes per archived item, both paced, and sizing on wall clock.
- confidence: high
- action: rewrite
- replacement: "**Its cost, stated symmetrically:** an archived item is **two** writes — a create, then a status reconcile to closed (the create path has no initial-state field) — and both are paced. The run summary prints its point total as a floor (`≥N`). Pacing rarely has to wait in practice, so size the run on **wall clock**: roughly round-trip latency × call count, about 18 minutes for 295 items."
- model_dependent: no
- machine_read: no

### D-12: migration-scrub Step 6 — what the cutover key does, in operator terms
- location: `plugin/skills/backlog/migration-scrub.md:501-516`
- evidence: "This single key (API §2.4) repoints the session briefing to the GV2 snapshot"
- pattern: Group 2 history narrative and volatile specifics (spec ids, `snapshot.read`, probe roster, "Two former members of that list now switch backends", "it no longer needs an advisory to say so"); 1d
- why: The model running a cutover needs one fact: this key makes tooling stop reading the markdown, so it must not be set before the gate passes. The advisory-retirement roster is framework internals, and it goes stale whenever a probe changes.
- confidence: high
- action: rewrite
- replacement: "Setting this key makes every prawduct surface read the backlog from the service instead of the markdown file, and stops the markdown-premise advisories. **Do not set it until the gate at the head of this step passes.** Once it is set nothing counts the markdown file, which from here on is frozen history for this repo."
- model_dependent: no
- machine_read: no. The pinned advisory names (`legacy-backlog-format`, `legacy-section-schema`, `backlog-overdue-grooming`) are matched as test string literals, but no test asserts them against this file; `backlog-overdue-grooming` also stays in `adapter-mode.md` and `SKILL.md`.

### D-13: migration-scrub — replace the `samsung-frame-art-loader` story with its rule
- location: `plugin/skills/backlog/migration-scrub.md:481-491`
- evidence: "`samsung-frame-art-loader` recorded its cutover with **7 of 9 items never"
- pattern: Group 2 history narrative; recency trap (one product's incident told as the justification)
- why: The rule's authority is the mechanism (a count cannot see a stranded item), not the incident. The same product is also named in the Precondition (D-9).
- confidence: high
- action: rewrite
- replacement: "*Why a command rather than step 5's count.* A raw issue count cannot see stranded items: issues filed natively after a cutover carry a `prawduct` block but no `id:PFX` alias, so totals can look plausible while source items are missing. The gate compares the source set against alias coverage, then compares each covered item's decoded status against the source."
- model_dependent: no
- machine_read: no

### D-14: migration-scrub — delete the `legacy.py` and drop-box paragraphs
- location: `plugin/skills/backlog/migration-scrub.md:551-564`
- evidence: "**The local upstream-bug drop-box this runbook once had to sequence against is"
- pattern: Group 2 history narrative ("retired 2026-09-08", "BKL-0QR1"); 1c prohibition against a failure the model will not make
- why: A product operator running this runbook cannot retire the plugin's `legacy.py`. That paragraph is a note to framework maintainers. The drop-box paragraph describes a mechanism that no longer exists, and says so.
- confidence: high
- action: remove
- replacement: (delete lines 551-564)
- model_dependent: no
- machine_read: no. `tests/test_drop_box_retirement.py` bans drop-box write tokens from shipped surfaces; deleting the paragraph only helps it.

### D-15: adapter-mode — delete the `queued` envelope for an unbuilt layer
- location: `plugin/skills/backlog/adapter-mode.md:43, 52-56`
- evidence: "`provisional_id` and that it reconciles on reconnect. **In the current state there is no queue: an"
- pattern: 1d fossil (describes an output shape no code path emits); 1c prohibition-by-description
- why: `grep -rn queued plugin/lib/backlog/` returns nothing, so the envelope cannot occur. Documenting it teaches the model to parse a phantom shape. The bullet itself ends by saying to handle the real case (exit 6), which the error discipline section already does.
- confidence: high
- action: remove
- replacement: Delete the third bullet (lines 52-56), and change line 43 to "The stdout envelope is one of two shapes:".
- model_dependent: no
- machine_read: no

### D-16: adapter-mode `update` status bullet — drop issue numbers and "used to prescribe"
- location: `plugin/skills/backlog/adapter-mode.md:229-238`
- evidence: "a `--closed-by` flag writing a queryable block field (#550/#564) — the comment workaround this"
- pattern: Group 2 history narrative; 1d ("the comment workaround this paragraph used to prescribe is retired", "`status` itself still takes none")
- why: The bullet explains GitHub's timeline and a retired workaround before it reaches the rule: pair the close with `update --closed-by`.
- confidence: high
- action: rewrite
- replacement: "- **status** (`status=X`) → `status <id> --to <mapped>` (bridge table above). Idempotent (re-run = no-op). `status` takes no scope, and a close records `closed_by` only on close-on-merge, so pass a `closed-by=<scope>` argument through as `update <id> --closed-by <scope>` in the same breath, or the ship handle is lost. Never hand-write it into a `prawduct:` block: that block is adapter-owned."
- model_dependent: no
- machine_read: no. `tests/test_backlog_instruction_surface.py::test_no_surface_claims_a_close_records_the_closed_by_scope` returns early while `update --closed-by` exists; its regex would match "records `closed_by`", exactly as the current text does.

### D-17: backlog SKILL — drop the #697 story from the timing rule
- location: `plugin/skills/backlog/SKILL.md:41, 44`
- evidence: "which is why it was once stated unconditionally and was false for half the products running it (#697)."
- pattern: Group 2 history narrative; 1d
- why: The rule (on the markdown backend, archive on the branch; on the Issues backend, close at the merge) stands on its stated reason, the commit atomicity. The issue numbers and "was once stated" are archaeology. Line 44 has a second copy: "(#697 records #687 and #688 as instances)".
- confidence: high
- action: rewrite
- replacement: Line 41: end the sentence at "…because the atomicity the convention promises is a property of **being a commit**, not a property of the archive." Line 44: delete "(#697 records #687 and #688 as instances)".
- model_dependent: no
- machine_read: no. `tests/test_pr_evidence_contract.py` keys on "the timing rule lives here" in this paragraph, which is kept.

### D-18: janitor Steps 5–6 — stale pointers to "this project's CLAUDE.md"
- location: `plugin/skills/janitor/SKILL.md:298, 310, 315`
- evidence: "Review the chunking and planning guidance in this project's CLAUDE.md."
- pattern: Group 2 volatile specifics (a factual claim that has rotted)
- why: A plugin-governed product's `CLAUDE.md` is the thin static anchor (`migrate_plugin.STATIC_ANCHOR`), which carries no chunking guidance. Planning and the build cycle live in `/prawduct:methodology planning` and `building`. "Write a build plan to `.prawduct/artifacts/build-plan.md` (or update the existing one)" also conflicts with planning.md's "One plan per scope tag". "Invoke the Critic as a separate agent" re-describes how the Critic skill dispatches.
- confidence: high
- action: rewrite
- replacement: Line 298: "After the user approves the scope, write a build plan under `.prawduct/artifacts/` following `/prawduct:methodology planning`." Line 310: "Read `/prawduct:methodology building` before writing any code, and follow its build cycle for each chunk:" Line 315: "- Run `/prawduct:critic` after each chunk (medium+ changes)". Keep line 314, which is pinned by `tests/test_suite_at_boundary.py`.
- model_dependent: no
- machine_read: no

### D-19: janitor Backlog Health — drop "blocked on #529" and "an earlier pass"
- location: `plugin/skills/janitor/SKILL.md:231, 238`
- evidence: "That argument names one backend, and an earlier pass in this work let it reach the other"
- pattern: Group 2 history narrative ("an earlier pass in this work", issue numbers); 1d ("still dormant")
- why: Line 238 is a design defence addressed to the next editor. The model needs only to know that checks 6 and 7 run on the markdown backend, which line 233 already says. Line 231's "blocked on #529" is a tracking note.
- confidence: high
- action: rewrite
- replacement: Delete line 238 (the whole "*Why scoped rather than retired.*" paragraph). Line 231: "5. **Neglected hygiene** — on the markdown backend, survey `## Promoted` items whose owning chunk appears shipped and ask "should this be `status=shipped`?" (never inferred — D4). The Issues backend has no `promoted` state to query, so say in the block that this check does not apply there."
- model_dependent: no
- machine_read: no

### D-20: migrate — remove the "Chunk 8" references
- location: `plugin/skills/migrate/SKILL.md:14-16, 92-94`
- evidence: "The plugin governs this repo the moment it is installed (Chunk 8: plugin governs, legacy"
- pattern: Group 2 history narrative (build-chunk ids in an instruction)
- why: A chunk id from a deleted build plan names nothing to the reader. The sentence reads correctly without it.
- confidence: high
- action: rewrite
- replacement: Line 14: "The plugin governs this repo the moment it is installed; this cutover removes the now-redundant committed framework files so the repo commits zero framework code and stops folding framework drift into its own diffs." Line 94: end at "…while `distribution: plugin` is recorded and/or the plugin is enabled)."
- model_dependent: no
- machine_read: no. The "Chunk 8" string in `tests/test_plugin_migrate.py:899` is a code comment.

### D-21: ping — drop the chunk and version provenance
- location: `plugin/skills/ping/SKILL.md:8-10`
- evidence: "`/prawduct:ping` namespace (Chunk 1, v2.0.0 plugin distribution). It performs no"
- pattern: Group 2 history narrative
- why: The provenance has no behavioural content.
- confidence: high
- action: rewrite
- replacement: "This skill proves that plugin skills resolve under the `/prawduct:ping` namespace. It performs no file access and changes no state."
- model_dependent: no
- machine_read: no

### D-22: repo-disable — drop "As of v2.0.11"
- location: `plugin/skills/repo-disable/SKILL.md:14-16`
- evidence: "(As of v2.0.11 the SessionStart hooks are already silent in a repo with no"
- pattern: 1d migration-relative plus version pin
- why: The fact (hooks are silent without `.prawduct/`; this skill also removes the commands and banner) is useful; the version date is not.
- confidence: high
- action: rewrite
- replacement: "(SessionStart hooks are silent in a repo with no `.prawduct/`. This skill goes further: it removes the `/prawduct:*` commands and the version banner too, by disabling the plugin outright for this repo.)"
- model_dependent: no
- machine_read: no

### D-23: cache-reads — move maintainer grant guidance out of a runtime prompt
- location: `plugin/skills/backlog/cache-reads.md:32-42`
- evidence: "every reader that runs under a **restricted tool list** is granted both explicitly — the Critic skill,"
- pattern: Group 2 verbose SKILL.md (text addressed to the framework editor); 1a bold emphasis ("The standing rule is what this paragraph is for")
- why: This file is read at runtime by the Critic reviewer, the PR reviewer and the janitor. None of them edits tool grants. The rule "whenever a reader is narrowed, the grant goes in the same edit" is already enforced by `tests/test_skill_command_grants.py` and `tests/test_pr_reviewer_agent.py::test_the_backlog_cache_read_survives_the_narrowing`. It costs tokens on every review for no runtime effect.
- confidence: medium
- action: move
- replacement: Keep only: "**Developing prawduct itself** (the plugin is in the tree, uncommitted): `python3 plugin/bin/prawduct-hook backlog cache-query …` — identical contract." Move the grant rule (lines 34-42) into the docstring of `tests/test_skill_command_grants.py`.
- model_dependent: no
- machine_read: no

### D-24: adapter-mode `file-upstream` — keep the routing, drop the copied mechanics
- location: `plugin/skills/backlog/adapter-mode.md:283-304`
- evidence: "**Preview-by-default, send on a second call.** With no `--approve` it renders the exact outbound"
- pattern: #342 duplicated fact; Group 2 time-sensitive content ("duplicated info across SKILL.md and reference files")
- why: The section opens with "**Do not call it from here.**" and then documents the preview/approve protocol and the refusal guarantee, all of which `/prawduct:report-bug` owns and states in full. A model told not to use an op does not need its protocol, and the copy can drift from the owner.
- confidence: medium
- action: rewrite
- replacement: "### file-upstream\nDo not call it from here. It is the data plane for `/prawduct:report-bug`, its only caller, which carries the recomposition and the verbatim human review that make the payload safe to send. Route a prawduct bug there. A product's own work is filed with `add`: this op writes into a foreign public repo, irreversibly."
- model_dependent: no
- machine_read: no. `tests/preferences/test_no_upstream_content_egress.py` lists `adapter-mode.md` only for absence-claims ("unbuilt", "not built"); `` `/prawduct:report-bug` `` stays.
- dup_of: `plugin/skills/report-bug/SKILL.md:148-266`

### D-25: backlog SKILL `update` — replace the Issues-backend block-field paragraph with a pointer
- location: `plugin/skills/backlog/SKILL.md:114`
- evidence: "It is no longer *silent*: the warning fires when the paste asks for something the write did not land"
- pattern: #342 duplicated fact; 1d migration-relative ("no longer *silent*")
- why: The writable-field list, the `--body` block-discard behaviour and the warning comparison are stated authoritatively in `adapter-mode.md` § update, which the routing section already sends every Issues-backend operation to. The two copies are worded differently.
- confidence: medium
- action: rewrite
- replacement: "**On the Issues backend these are adapter flags, not `field=value` args.** `adapter-mode.md` § update lists the writable block fields and what a `--body` edit does to the block."
- model_dependent: no
- machine_read: no
- dup_of: `plugin/skills/backlog/adapter-mode.md:264-273`

### D-26: backlog `add` — stop leading with delegation
- location: `plugin/skills/backlog/SKILL.md:97`; `plugin/skills/backlog/adapter-mode.md:201`
- evidence: "the instinct to file is one of three options, and it gets said out loud: **delegate it, do it now, or backlog it** — filing is the third answer, not the default."
- pattern: prawduct delegation push (the offer is listed first, and filing is framed as disfavoured); guide Opus 5 row "Delegates to subagents more readily"
- why: Opus 5-class models reach for subagents freely, and an offer that lists delegation first and demotes filing tilts an already-biased choice. The three options, the cost disclosure and the ready-to-build bound all stay.
- confidence: medium
- action: rewrite
- replacement: SKILL.md line 97: "…the instinct to file is one of three options, and it gets said out loud: **do it now, backlog it, or delegate it**. Offer the delegate with its cost attached (…unchanged…)". adapter-mode.md line 201: "say the three options out loud — *do it now, backlog it, or delegate it* — with the delegate's cost attached."
- model_dependent: no
- machine_read: no. `tests/test_v5_methodology.py::TestAdHocDelegationBacklogPrompt` checks that each option is present and that the offer sits between "dedup first" and the append; order is not asserted.

### D-27: backlog SKILL `scrub` — two sentences instead of grant and code archaeology
- location: `plugin/skills/backlog/SKILL.md:229-231`
- evidence: "**There is no adapter-side target guard on these ops, and you must not assume one.**"
- pattern: Group 2 verbose SKILL.md (maintainer guidance: "Do not 'fix' the prompt by re-widening the grant"; code facts: "`ids.parse_repo` is *shape-only* … at every one of its call sites", "`lib/backlog/upstream.py` compares repo identity")
- why: The operative facts are that the scrub ops prompt on purpose and that nothing checks `--repo`, so the Step 0 confirmation is the guard. `migration-scrub.md` Step 0 already carries that guard. The rest is an argument addressed to a reviewer.
- confidence: medium
- action: rewrite
- replacement: "The scrub's high-consequence ops (`import`, `merge`, `provision`, `reconcile-labels`) are outside this skill's grant on purpose, so each prompts at the moment it would write. Nothing in the adapter checks `--repo`: `import --repo <any-valid-slug>` writes to that repo. The runbook's Step 0 owner-confirmed target is the only guard."
- model_dependent: no
- machine_read: no. `tests/test_backlog_instruction_surface.py::test_surfaces_claim_no_unbacked_adapter_guard` forbids naming a "target pin"; the replacement names none.

### D-28: backlog `pick` — a qualitative ranking, not an arithmetic rubric
- location: `plugin/skills/backlog/SKILL.md:133-134`
- evidence: "**An item missing *both* fields scores `2/2 = 1.0`** — the same as a genuine `M`-impact/`M`-effort item"
- pattern: 1b inline point systems and arithmetic the model must compute; 1c padding (a paragraph explaining a flaw in the author's own formula)
- why: The model computes `impact/effort` with a letter-to-number map, and a second paragraph then explains how the default misranks unassessed items. The judgment the author actually wants is "rank by value per effort and treat missing fields as unassessed". The Issues backend already ranks in the adapter.
- confidence: medium
- action: rewrite
- replacement: "3. **Score** each candidate by impact relative to effort, nudged up for recency and down for legacy items with no metadata bar. Treat an item missing `effort:`/`impact:` as *unassessed* rather than medium: say so, and prefer filling the fields over trusting its rank."
- model_dependent: no
- machine_read: no

### D-29: backlog SKILL — move the "considered and rejected" design note out
- location: `plugin/skills/backlog/SKILL.md:34-37`
- evidence: "A blanket "never read the file directly" was considered and rejected: it would retire the janitor's"
- pattern: Group 2 history narrative (a rejected alternative, addressed to the next editor)
- why: The model executing `/prawduct:backlog` is not choosing between read policies. The three bullets above are the rule, and the paragraph's last sentence is about how *other* files are written.
- confidence: medium
- action: move
- replacement: Delete lines 34-37 from the skill, and put the rationale in the docstring of `tests/test_cutover_prose_coherence.py::test_owner_states_the_rule_and_records_the_rejected_alternative`.
- model_dependent: no
- machine_read: yes. That test asserts `"blanket" in flat and "rejected" in flat` against this file, so drop those two asserts along with the move.

### D-30: Health Check #18 — keep every pinned clause, cut the maintainer rationale
- location: `plugin/skills/doctor/SKILL.md:79`
- evidence: "`Delegation approval` is not in the trigger set: it is a *setting* shipping a default, so it is never unset"
- pattern: Group 2 verbose SKILL.md; 1c padding ("`Inner-loop verification` is in the set for the opposite reason…", "`docs/norms.md` names the cost from this repo's own orphan-term hook")
- why: A single ~650-word paragraph. About half of it justifies the trigger set's membership to a future editor. The model needs the three rows, the per-row branches, the evidence search and "never grade".
- confidence: medium
- action: rewrite
- replacement: "18. **Delegation policy unrecorded (a recommendation, not a conformance check)** — read `project-preferences.md`'s `Delegation`, `Delegate verification` and `Inner-loop verification` rows, and branch per row rather than on the set. `Delegation approval` is not in the trigger set: it ships filled with a default, so reading it would make every freshly scaffolded repo look recorded — what excludes a row is shipping filled, not being a third. **`Delegation: off` ends the check**: say nothing and propose nothing further. A filled row is reported as recorded and left alone; a blank one beside it is still a candidate. When all three are filled the check ends. A durable `Delegation approval` yes is `methodology/planning.md`'s offer, not doctor's. **For each unset row — or absent row, since this file is scaffolded once and never regenerated** — look for what this repo already encodes about running part of its suite: test markers or groups in the test config, a named script, a build-tool target, a CI job that runs a subset. The same findings answer `Inner-loop verification` (what to run while iterating and at each chunk's Verify), worded as the narrowest thing that proves a change. **Propose only what you actually found, quoting the repo's own names and naming the file each came from.** If you found nothing, say so and propose nothing, because a proposal that fires everywhere carries no information. **Never degrade the repo on this, and never grade it at all**: an absent policy is not a defect. The promotion is offered, never applied: see the Delegation Policy Flow."
- model_dependent: no
- machine_read: yes. `tests/test_v5_methodology.py::TestDelegationPolicyAndPromotion` asserts, within this check: `a recommendation, not a conformance check`; the three row names in backticks before `branch per row rather than on the set`; `not in the trigger set`; `what excludes a row is shipping filled, not being a third`; `off\` ends the check`; `a blank one beside it is still a candidate`; `found nothing` / `propose nothing`; `the repo's own names`; `naming the file each came from`; `never degrade the repo on this`; and no `tier` token. The replacement keeps all of them.

### D-31: Health Check #11 — compress the layer staging
- location: `plugin/skills/doctor/SKILL.md:64`
- evidence: "note that the scan reads source by suffix, so a repo in an unlisted language reads as unstarted (`#561`)"
- pattern: Group 2 verbose SKILL.md; 1c padding (nested parentheticals restating what `coverage-status` prints); history (`#561`)
- why: The command already names the primary fix. The model needs the layer meanings, the `false`/`null` distinction and the read-and-guide boundary.
- confidence: medium
- action: rewrite
- replacement: "11. **Strategy-class artifact coverage** — run `prawduct-hook coverage-status` and relay the chain it reports; it reads the same expectation table as the `strategy-artifact-missing` / discovery-not-captured advisories. The layers stage the fixes. **Layer 0**: structural characteristics are not recorded → `/prawduct:methodology discovery`. **Layer 1**: expected strategy-class artifacts are missing → author each via `/prawduct:methodology planning`, or stub them with `prawduct-hook coverage-scaffold --apply`. **Layer 2**: the artifacts exist but the norms are unratified → the Norm Ratification Flow. Layers 0 and 1 are mutually exclusive; layer 2 can be active beside layer 1, and the command names the highest-priority active layer as the primary fix. Report **degraded** when any layer is active and **healthy** when none is, with one exception: when `discovery_expected` is false (`--json`; the human line says so), say "the coverage chain has not engaged yet" rather than calling the repo healthy. `discovery_expected: null` (or `structural_recorded: null`) means the staging check could not run: degraded because ungraded. The scan reads source by suffix, so a repo in an unlisted language reads as unstarted. A `(not relevant — <reason>)` stub counts as coverage, and whether a stubbed decision is sound is the Critic's call. Offer `coverage-scaffold` (dry run first; `--apply` writes neutral stubs and never overwrites); the owner runs `--apply` and fills each stub."
- model_dependent: no
- machine_read: no

### D-32: doctor — three small maintainer asides
- location: `plugin/skills/doctor/SKILL.md:42, 67, 131`
- evidence: "(Checks 13 and 13a were retired with the learnings corpus they graded; the numbering keeps its gap"
- pattern: Group 2 history narrative
- why: Line 67 explains a numbering gap to the next editor. Line 131's "the same reach gap that put Health Check #14 in this file" is cross-check archaeology. Line 42's "One check reads a value **out of the plugin** (#1's contract)…" restates #1 (and is superseded by D-1's rewrite of that paragraph).
- confidence: medium
- action: remove
- replacement: Delete line 67. At line 131, end the paragraph at "…this flow is the only path by which it gets them. Add the rows under `## Workflow` if they are missing." Line 42 is handled by D-1.
- model_dependent: no
- machine_read: no

### D-33: doctor "Important Notes" — delete; every line restates the top of the file
- location: `plugin/skills/doctor/SKILL.md:163-168`
- evidence: "Every flow decides from the consumer's OWN `.prawduct/` and `.claude/` — no framework checkout, no sync."
- pattern: 1c padding (repetition as reinforcement); 1d ("no sync")
- why: Line 165 restates line 11, 166 restates line 42, and 167 restates the Enable-Gate flow. Line 168 ("Hooks and governance activate in the target's own Claude Code session") concerns onboarding a different directory, which doctor refuses at line 23.
- confidence: medium
- action: remove
- replacement: (delete the `## Important Notes` section, lines 163-168)
- model_dependent: no
- machine_read: no. `/prawduct:onboard` still appears at lines 11, 23 and 29, as `tests/test_plugin_init.py::test_doctor_skill_does_not_onboard` requires.

### D-34: Label-provisioning ownership map, stated in three skills
- location: `plugin/skills/doctor/SKILL.md:65`; `plugin/skills/onboard/SKILL.md:42`; `plugin/skills/backlog/migration-scrub.md:86-89`
- evidence: "this is doctor's ownership of provisioning (GV6) — onboard provisions at adoption, scrub at migration"
- pattern: #342 duplicated fact; Group 2 (spec id GV6)
- why: Each skill needs only its own step. The map of who provisions when is framework design, repeated three times, and it does not change what any one skill does.
- confidence: medium
- action: rewrite
- replacement: onboard line 42: "For Issues, onboard provisions the labels — two steps, in order:". doctor line 65: delete "this is doctor's ownership of provisioning (GV6) — onboard provisions at adoption, scrub at migration, doctor *reconciles* on repair." migration-scrub lines 87-89: delete "This is the scrub's ownership of provisioning; the other two entry paths own it for theirs — `/prawduct:onboard` provisions at adoption, `/prawduct:doctor` reconciles as a repair."
- model_dependent: no
- machine_read: no. `tests/test_backlog_governance.py` matches "GV6" as its own string; it does not assert against doctor.
- dup_of: `plugin/skills/onboard/SKILL.md:42`, `plugin/skills/backlog/migration-scrub.md:86-89`

### D-35: migration-scrub — strip the spec and backlog ids throughout
- location: `plugin/skills/backlog/migration-scrub.md:1, 9, 16, 19, 25-28, 183, 233, 237-238, 287-289, 625`
- evidence: "explicitly left to the owner. This is asserted structurally by the MIG-5 test:"
- pattern: Group 2 history narrative and volatile specifics (internal requirement ids: MG4, GV7, API §2.5, MG4/G1, DM7, MIG-5, MG6, MG4b, NF3, BKL-6X5D, AU3/CRASH-2)
- why: The ids point into a requirements register the operator cannot see, and they rot as the register renumbers. Keep `issue-standard §1/§5`, which names a doc the reader can open.
- confidence: medium
- action: rewrite
- replacement: Drop each parenthetical id. Worked examples:
  - Line 1: "# Migration scrub — markdown backlog → GitHub Issues".
  - Line 19: "## The one invariant: the model decides, it never touches the data plane".
  - Delete the sentence "This is asserted structurally by the MIG-5 test: the import op consumes a record set, not a model call."
  - Delete lines 287-289: "A *quantified* recent-shipped window … today the lever is the binary open/all."
- model_dependent: no
- machine_read: no

### D-36: migration-scrub 3c `open` / `all` — state the owner-facing cost once
- location: `plugin/skills/backlog/migration-scrub.md:236-263`
- evidence: "the tracker*, not whether dedup sees it. (State it as `list`, not `find`: an item"
- pattern: Group 2 verbose SKILL.md; 1c padding (the reachability-versus-visibility point is argued twice, plus an author-to-self aside about word choice)
- why: This is a judgment presentation to the owner, not a fragile command. The two bullets restate the same distinction at length, with code-path citations (`lib/backlog/query.py`).
- confidence: medium
- action: rewrite
- replacement: "   - **`open`** — migrate only the live/open set and mint no closed issue per archived item: fewer total writes and a cleaner tracker. (The rate ceiling is the importer's pacer's job, not this lever's.) **State the cost before the owner chooses:** the skipped archive stays only in the git-tracked source markdown, not in the export (which dumps the migrated repo), so after cutover no adapter op — not `list`, not the cache-served `find` — can reach it.\n   - **`all`** — import the full archive as closed issues: complete history inside the tracker, one `--state closed|all` flag away. Under either scope, archived items are absent from a default `list` and from add-time dedup; the lever decides whether the record is reachable through the tracker, not whether dedup sees it. [D-11's cost sentence follows.]"
- model_dependent: no
- machine_read: no

### D-37: migration-scrub 6b / 6c — the rule without the incident narrative
- location: `plugin/skills/backlog/migration-scrub.md:566-597`
- evidence: "earlier partial run — that item keeps whatever title and body it already had. On a real"
- pattern: Group 2 history narrative ("On a real 415-item migration that was 25 issues", "nothing drew the consequence, and nothing repaired it", "the real find was a `DEVELOPMENT.md`", "on that migration it did not mention…")
- why: Each step's instruction is sound. The stories that justify it are one migration's particulars.
- confidence: medium
- action: rewrite
- replacement: 6b opening: "**6b. Repair the items the import ADOPTED.** A `--restructure` plan applies only at create, so an item the importer adopted by its `id:PFX` alias from an earlier partial run keeps its old title and body." 6b lint bullet: "**Then lint the whole target, not just the adopted set.** `verify-migration` checks source → target coverage, and nothing checks the target against the issue standard, so an issue aliased before this run is seen by no other step. List every aliased issue, check its title against §1 (`≤72`, `area:`-prefixed, atomic), and fix failures with `update --title`." 6c: "Fix **wrong instructions**, not only stale links — for example, a contributor guide telling people to file into the now-frozen file." and "**Name the anchor doc explicitly: `CLAUDE.md`** (or this repo's equivalent), the file every agent session and new contributor reads, and say in it where the backlog now lives."
- model_dependent: no
- machine_read: no

### D-38: migration-scrub — migration-relative phrasing in two gate remedies
- location: `plugin/skills/backlog/migration-scrub.md:331-334, 445-446`
- evidence: "A per-item rejection **no longer ends the run**: an item GitHub refuses is"
- pattern: 1d migration-relative ("no longer", "can never again", "now carried across")
- why: Relative phrasing implies an earlier behaviour the model never saw. The current behaviour is the instruction.
- confidence: medium
- action: rewrite
- replacement: Lines 331-333: "A per-item rejection does not end the run: an item GitHub refuses is recorded and the import continues past it. Those items are **not on the target at all**, …" (drop "so one malformed row can never again end a 396-row migration"). Lines 445-446: "`promoted` lands as the service's `in-progress` sub-state."
- model_dependent: no
- machine_read: no

### D-39: migration-scrub — delete the Step 4 sizing note
- location: `plugin/skills/backlog/migration-scrub.md:366-372`
- evidence: "**Sizing note for `--archive-scope all`.** For a **large** backlog where the"
- pattern: 1c padding (restates Step 3c's "two writes, create then reconcile"); Group 2 (a roadmap aside: "revisit only if the create path gains an initial state")
- why: It tells the operator not to attempt something the importer cannot do, then repeats the cost Step 3c already states.
- confidence: medium
- action: remove
- replacement: (delete lines 366-372)
- model_dependent: no
- machine_read: no
- dup_of: `plugin/skills/backlog/migration-scrub.md:264-265`

### D-40: migration-scrub Step 5 — drop the eyeball self-check the gate supersedes
- location: `plugin/skills/backlog/migration-scrub.md:374-385`
- evidence: "rollup; spot-check a handful of migrated bodies and IDs; confirm every"
- pattern: prawduct self-verification prose aimed at the builder; Opus 5 row "Over-verification"
- why: The step itself says "the gate that actually decides completeness is `verify-migration` in step 6, not this arithmetic". The spot-checks and alias confirmation duplicate what the gate checks mechanically (the gate stays, per keep item 2).
- confidence: medium
- action: rewrite
- replacement: "**5. Rollup.** Run `prawduct-hook backlog counts --repo <target>` for the rollup. Completeness is decided by `verify-migration` in step 6, not by this count: `total` includes any pre-existing non-prawduct issues (`untriaged`), and nothing has been disposed yet."
- model_dependent: yes
- machine_read: no

### D-41: adapter-mode `working-branch` — drop the retired-`claim` prohibition
- location: `plugin/skills/backlog/adapter-mode.md:260-263`
- evidence: "**This is how an item is taken. There is no `claim` op** — it is retired, along with `unclaim`,"
- pattern: 1d migration-relative; 1c prohibition that can anchor toward the failure it names
- why: Naming the retired `claim`, `unclaim`, TTL and assignee stamp tells the model about four things that no longer exist. The positive statement carries the rule.
- confidence: medium
- action: rewrite
- replacement: "Setting the branch is how an item is taken: `pick` excludes on it, and nothing expires it, because the branch's last commit is the activity signal."
- model_dependent: no
- machine_read: no. `tests/test_backlog_skill_metadata.py` flags only *invocations* of retired ops; this sentence is not required.

### D-42: adapter-mode — delete the security-model `quarantine` paragraph
- location: `plugin/skills/backlog/adapter-mode.md:142-145`
- evidence: "This set is a **superset of the security model's `quarantine`**, which is the *non-collaborator*"
- pattern: Group 2 verbose SKILL.md (a design-document cross-reference and an unimplemented-predicate note)
- why: The model renders `--untriaged` results. How that set relates to a security-model term that has no implementation changes nothing it does.
- confidence: medium
- action: remove
- replacement: (delete lines 142-145)
- model_dependent: no
- machine_read: no

### D-43: adapter-mode `list` — `--assignee` without the retirement note
- location: `plugin/skills/backlog/adapter-mode.md:131-132`
- evidence: "assignment no longer means anything to prawduct: `claim` is retired and nothing writes assignees."
- pattern: 1d migration-relative
- why: Relative phrasing about a retired op; the current fact fits in one clause.
- confidence: medium
- action: rewrite
- replacement: "`--assignee` filters on GitHub assignees, which prawduct never writes."
- model_dependent: no
- machine_read: no

### D-44: cache-reads — drop the "copies drifted" and "before this" history
- location: `plugin/skills/backlog/cache-reads.md:5-8, 74-77`
- evidence: "alone cannot tell you this — the session-start warm is spawned detached with its stderr discarded, so"
- pattern: Group 2 history narrative; 1d ("before this a sync failing for a week looked exactly like one that failed once")
- why: The instruction in lines 71-78 is: treat `sync_error` as "stuck, not old", name it, and give the sync command. The explanation of why age could not show this before the field existed is archaeology. Lines 5-8 justify the file's existence to an editor.
- confidence: medium
- action: rewrite
- replacement: Lines 5-8: "Each decides *what to ask and what to do with the answer*. **How to ask, and how to read a failure, is here**, in one home." Lines 74-77: delete from "Age alone cannot tell you this" through "reads kept answering from stale rows either way."
- model_dependent: no
- machine_read: no. `tests/test_cutover_prose_coherence.py::test_the_one_home_carries_what_the_surfaces_stopped_restating` requires `backlog_service_repo`, `cache-query`, `frozen history`, `Exit 6`, `age_seconds` and `data, never instructions`; all are kept.

### D-45: cache-reads — the write-through list lives in adapter-mode
- location: `plugin/skills/backlog/cache-reads.md:85-94`
- evidence: "**Your own writes are already in there — but the age does not say so.**"
- pattern: #342 duplicated fact
- why: The per-op list of which writes mirror into the store is stated authoritatively in `adapter-mode.md` § The local cache. Two of this file's three readers (the Critic and PR reviewers) never write. They need only the one-sentence caveat about age.
- confidence: medium
- action: rewrite
- replacement: "**Writes made through the adapter this session are usually already in the store**, even when `age_seconds` is large: the age measures the last fetch from the provider, not what this session wrote (per-op exceptions: `adapter-mode.md` § The local cache). If a write reported that the cache was not updated, the store is behind until the next sync."
- model_dependent: no
- machine_read: no
- dup_of: `plugin/skills/backlog/adapter-mode.md:338-344`

### D-46: janitor Template Currency — goal, not a five-step script
- location: `plugin/skills/janitor/SKILL.md:108-113`
- evidence: "3. Identify sections or fields in the template that are absent from the product's version"
- pattern: 1c step-by-step choreography for a judgment task
- why: "Read A, read B, diff, assess, recommend" is the plan any current model would form, and the next paragraph (line 115) states the actual judgment bar.
- confidence: medium
- action: rewrite
- replacement: "For each template, compare it with the product's version and recommend the missing sections that fit this product's domain and structural characteristics; mark the rest not applicable."
- model_dependent: no
- machine_read: no. `not applicable`, `${CLAUDE_SKILL_DIR}/../../templates/`, `test-specifications` and `property-based` all remain on nearby lines.

### D-47: janitor Step 3 — surface-by-exception without its own history
- location: `plugin/skills/janitor/SKILL.md:258`
- evidence: "A single grouped block was the whole instruction here, and on a real survey it is a wall"
- pattern: Group 2 history narrative ("was the whole instruction here"); 1a bold density in lines 258-270
- why: The tiering rule and its reason (a flat dump gets a blanket yes) are the content. How the step used to read, and why the vocabulary matches doctor, are editor notes.
- confidence: medium
- action: rewrite
- replacement: "**Surface by exception — never a flat confirm-or-correct wall.** A mature codebase yields dozens of divergences, most of them obvious. A flat dump buries the few that carry a decision, and a blanket yes to an unread list is the same as not asking. This is the same two-tier taxonomy as `/prawduct:doctor`'s Norm Ratification Flow." Keep lines 260-270, including the bulk-confirm line that carries "count".
- model_dependent: no
- machine_read: no. `tests/test_doctor_janitor_boundary.py` requires `Surface by exception`, both tier names, a bulk-confirm line that carries "count", and either no "confirm-or-correct block" or "never a flat"; all hold.

### D-48: janitor "Important" — keep only what is not said above
- location: `plugin/skills/janitor/SKILL.md:329-336`
- evidence: "- The survey is the most valuable phase. Resist the urge to fix things as you find them."
- pattern: 1c padding (repetition as reinforcement)
- why: Line 332 restates line 219, line 333 restates line 53, and line 336 restates Steps 5-7. Keep list 10 allows one deliberate recap of the *few key* constraints; this list re-says six.
- confidence: medium
- action: rewrite
- replacement: "## Important\n\n- This is maintenance, not feature work. Do not add new functionality or refactor for taste.\n- When removing code (dead code, backcompat shims, migrations), verify the paths are truly unreachable before deleting.\n- If a finding requires significant redesign, flag it for a dedicated work cycle. The janitor cleans; it doesn't renovate."
- model_dependent: no
- machine_read: no

### D-49: janitor — migration-relative notes about templates
- location: `plugin/skills/janitor/SKILL.md:204, 324`
- evidence: "The plugin ships templates read-only; there is no per-product sync manifest."
- pattern: 1d migration-relative (negates a retired file-sync artifact)
- why: Saying there is no sync manifest or hash store only matters to a reader who remembers file-sync.
- confidence: medium
- action: rewrite
- replacement: Line 204: "**Framework health pre-check.** If `${CLAUDE_SKILL_DIR}/../../templates/` is unreadable, the janitor is running outside the plugin runtime; advise checking the plugin install (`/prawduct:doctor`) before relying on Template Currency." Line 324: "…record in `.prawduct/change-log.md` which artifacts were brought up to the current plugin templates; updating the product artifact is itself the resolution."
- model_dependent: no
- machine_read: no. `tests/test_plugin_runtime.py` forbids `sync-manifest` in this file, so this edit removes a near-miss rather than adding one.

### D-50: backlog SKILL `accepted-by:` — one sentence on the Issues equivalent
- location: `plugin/skills/backlog/SKILL.md:77`
- evidence: "The two are deliberately not unified: `working-branch` requires a **pushed** ref and a named repo"
- pattern: Group 2 verbose SKILL.md (a design defence for not unifying the fields)
- why: The model needs the equivalence and the migration consequence, not the argument for keeping two fields.
- confidence: medium
- action: rewrite
- replacement: "  On the Issues backend the equivalent is `working-branch: owner/repo@branch` (`adapter-mode.md`). The import maps neither field to the other, so a migrating product's open claims are not carried and should be re-recorded as working branches."
- model_dependent: no
- machine_read: no

### D-51: backlog SKILL — `closed-by` handle rule stated in three places
- location: `plugin/skills/backlog/SKILL.md:74`
- evidence: "a handle that exists *before* the commit recording it, never a bare commit SHA and never a bare chunk id, which names no plan"
- pattern: #342 duplicated fact
- why: The "scope name, not SHA, not chunk id" rule is stated at line 41, again in the metadata-bar legend at line 74, and in full under `update` at line 112. Line 112 is the one `tests/test_backlog_instruction_surface.py` treats as the router, and line 41 already points to it.
- confidence: medium
- action: rewrite
- replacement: At line 74, replace the `closed-by:` parenthetical with "`closed-by:` (what shipped this item — the handle rule is under `update`)".
- model_dependent: no
- machine_read: no
- dup_of: `plugin/skills/backlog/SKILL.md:112`, `plugin/skills/backlog/SKILL.md:41`

### D-52: backlog SKILL archive split — stop describing the janitor
- location: `plugin/skills/backlog/SKILL.md:60`
- evidence: "the janitor's Backlog Health step only *surfaces* when a split is due, and it still does — on this backend."
- pattern: #342 (restates `janitor/SKILL.md:233-236`); 1d ("it still does")
- why: The skill needs the split rule and its scope, not the janitor's behaviour on each backend.
- confidence: medium
- action: rewrite
- replacement: "**Archive split (Q2) — markdown backend only.** When `## Archive` grows past ~200 entries, move the oldest archived items into a sibling `backlog-archive.md` (same item format); `find` searches both, and git preserves history. This is a `/prawduct:backlog` operation. Post-cutover there is nothing to split, because closed issues *are* the archive."
- model_dependent: no
- machine_read: no. `tests/test_cutover_prose_coherence.py` requires `Archive split (Q2) — markdown backend only` and `closed issues *are* the archive`; both are kept.
- dup_of: `plugin/skills/janitor/SKILL.md:233-236`

### D-53: backlog SKILL — issue ids and advisory internals in `migrate` / `decline-migration`
- location: `plugin/skills/backlog/SKILL.md:164, 181`
- evidence: "Permanently record that this product is staying on the **markdown** backlog (#197/TM1) — a product"
- pattern: Group 2 history narrative (issue and requirement ids); Group 2 verbose (line 164's advisory mechanics, "so a repo that adopts a new prawduct version … is prompted")
- why: The ids carry no behaviour. Line 164's second half explains to the model the nudge that brought the user here.
- confidence: medium
- action: rewrite
- replacement: Line 181: drop "(#197/TM1)". Line 164: end at "…Run it when a repo carries unstructured legacy items (the `pick`/list views and the `legacy-backlog-format` advisory flag these)."
- model_dependent: no
- machine_read: no. `tests/test_path_reference_resolution.py` checks that a `lib/backlog_probes.py` reference *resolves* if present; it does not require one.

### D-54: onboard — "MANDATORY" in a behavioural heading
- location: `plugin/skills/onboard/SKILL.md:25, 64`
- evidence: "### Prove the plugin will actually load there — MANDATORY"
- pattern: 1a pressure language
- why: The section already carries its reason ("This session is the only one that can ask"), and step 5 already sends the model there. Caps in the body read as anxiety, not information.
- confidence: medium
- action: rewrite
- replacement: Line 64: "### Prove the plugin will actually load there". Line 25: "5. **Check that the plugin will load there** (below)."
- model_dependent: no
- machine_read: no

### D-55: onboard — file-sync negations
- location: `plugin/skills/onboard/SKILL.md:15, 19`
- evidence: "Onboarding under the plugin model is plugin-native — there is no file-sync setup script."
- pattern: 1d migration-relative
- why: Negating a retired mechanism implies a phantom alternative. Route B still names the file-sync layout where it is actually relevant.
- confidence: medium
- action: rewrite
- replacement: Line 15: "Pick the shape by inspecting the target:". Line 19: delete "— and **none** of the file-sync machinery (no `tools/`, no committed skills, no sync-manifest)".
- model_dependent: no
- machine_read: no

### D-56: onboard — the exit-3 paragraph repeats its table row
- location: `plugin/skills/onboard/SKILL.md:85-88`
- evidence: "**Exit 3 is not a failure of onboarding** — it is the same *unverified* sentinel `check-released`"
- pattern: 1c padding (repetition as reinforcement)
- why: The `unknown` row directly above says the same thing: it was not established, never say it passed, and confirm by opening the target.
- confidence: medium
- action: remove
- replacement: (delete lines 85-88)
- model_dependent: no
- machine_read: no

### D-57: onboard — the transcribed install-reference JSON
- location: `plugin/skills/onboard/SKILL.md:53-59`
- evidence: "The committed install *reference* (project scope) in `.claude/settings.json` is the only prawduct content the repo commits, and it never drifts"
- pattern: #342 duplicated fact; Group 2 volatile specifics (a hardcoded copy of `migrate_plugin.INSTALL_REFERENCE`)
- why: Onboarding never writes this JSON by hand (`init-product` does). The copy agrees with the constant today, but doctor Check #1 exists because transcriptions of this contract drift, and "it never drifts" is the claim a copy undermines.
- confidence: medium
- action: rewrite
- replacement: "- The committed install *reference* (project scope) in `.claude/settings.json` is the only prawduct content the repo commits. `init-product` writes it for new repos, and `/prawduct:migrate` for existing file-sync ones; `/prawduct:doctor` Check #1 grades it against `prawduct-hook print-install-reference`." Keep the "On first trusted open…" paragraph unchanged.
- model_dependent: no
- machine_read: no. `tests/test_plugin_absent_prose.py` requires `claude plugin install prawduct@prawduct` in this file, which stays in the following paragraph.
- dup_of: `plugin/lib/migrate_plugin.py:36-44`

### D-58: methodology — caps and "#1" emphasis on the building route
- location: `plugin/skills/methodology/SKILL.md:11, 28`
- evidence: "**STOP: read this before writing ANY code against a build plan** (skipping it is the #1 governance failure)"
- pattern: 1a pressure language (caps plus bold plus ranking claim, in a skill body; the frontmatter description already carries the routing urgency, per keep item 6)
- why: This is text for a model that has already chosen to read the guide. At that point the booster only raises the register.
- confidence: medium
- action: rewrite
- replacement: Line 11: "- `building` → `${CLAUDE_SKILL_DIR}/../../methodology/building.md` — read before writing any code against a build plan. Then match rigor to risk and run `/prawduct:critic` after medium+ work, as the plan's "Done when" steps direct." Line 28: "- `/prawduct:methodology building` — before writing any code against a plan".
- model_dependent: no
- machine_read: no. `tests/test_plugin_methodology_digest.py::test_index_carries_stop_before_code_line` accepts "before writing any code" in either case; the topic-list line keeps its "- `" prefix and "→".

### D-59: methodology — the delegation route restates delegation.md
- location: `plugin/skills/methodology/SKILL.md:16`
- evidence: "When to delegate and when to stay serial; what a delegate verifies (what proves its own change, and nothing beyond it)"
- pattern: Group 2 verbose (a routing line summarising a guide's contents); #342
- why: Every other topic line gives the when-to-read plus one line. This one gives a table of contents of `delegation.md`, which the reader is about to open anyway.
- confidence: medium
- action: rewrite
- replacement: "- `delegation` → `${CLAUDE_SKILL_DIR}/../../methodology/delegation.md` — before splitting work across subagents, and when a tangent arrives mid-chunk."
- model_dependent: no
- machine_read: no. The pinned `nothing beyond it` and `integration debt` are asserted against `methodology/delegation.md`, not this skill.
- dup_of: `plugin/methodology/delegation.md`

### D-60: runbook — the subtraction pass is stated twice
- location: `plugin/skills/runbook/SKILL.md:54-56`
- evidence: "**Do a subtraction pass before you finish** — one read whose only purpose is deletion."
- pattern: 1c padding (repetition as reinforcement)
- why: Step 5 of `new` (lines 166-167) gives the same deletion pass, at the point in the workflow where it runs. The anti-length guidance itself stays; it matches the Opus 5 "longer written deliverables" shift.
- confidence: medium
- action: remove
- replacement: (delete lines 54-56)
- model_dependent: no
- machine_read: no
- dup_of: `plugin/skills/runbook/SKILL.md:166-167`

### D-61: repo-disable — "REQUIRED" in a step heading
- location: `plugin/skills/repo-disable/SKILL.md:53`
- evidence: "### 4. Tell the user what happens next — REQUIRED"
- pattern: 1a pressure language
- why: The step's content (it takes effect after reload; there is no re-enable command, so here is the manual edit) is load-bearing and self-evidently necessary. The caps add nothing.
- confidence: medium
- action: rewrite
- replacement: "### 4. Tell the user what happens next"
- model_dependent: no
- machine_read: no

## Outside my slice

- `tests/test_cutover_prose_coherence.py`, `tests/test_v5_methodology.py` (`TestDelegationPolicyAndPromotion`) and `tests/test_install_reference_probes.py` pin maintainer rationale phrases inside runtime skill prose, which is why D-2, D-29 and D-30 must keep sentences whose only reader is an editor.
