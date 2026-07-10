# Learnings

Active rules from this project's development. Surfaced via the `/learnings [topic]` skill — topic headers shown in the session briefing for ambient context. Entries use "When X, do Y because Z" format. Each entry's full narrative lives in `learnings-detail.md` under the same heading — keep narrative THERE, not here.

---

## When a governance checkpoint verifies a required side-effect happened, put it OUTSIDE the control flow that produces the side-effect — a check inside the fallible flow can't catch that flow's own skip

A checkpoint that lives *inside* the step it guards cannot fire when that step is skipped entirely. The Critic's `critic-end` carried a HEAD-coverage assertion, but the v2.1.198 background-by-default change made the coordinator fork return before ever reaching `critic-end` — so the review was silently lost and the in-flow assertion never ran. The robust backstop is the one OUTSIDE the flow that can fail: a lingering `.critic-active` marker caught at session end (a state the skippable step would have cleared). When you need to guarantee a side-effect (persist findings, write a record, release a lock), verify it where the mutation *can't be skipped* (session end, a separate hook, a deterministic consolidation), not where the skippable step runs — and prefer making the side-effect a pure function of durable on-disk state (no model/agent in the write path) so no control-flow/harness behavior can bypass it. Corollary: verify post-training-cutoff harness behavior (background-by-default date, SubagentStop existence, plugin agent-type resolution) by investigation + `claude-code-guide` + empirical test, never recall. Relates to Governance Is Structural (#22), Root Cause Discipline (#16), Validate Before Propagating (#15), Honest Confidence (#5), and [[backlog]] CRT-9K7T (the defect), VRF-002 (the deferred live check the plugin-cache-vs-working-tree gap forced).

## When building from a review/audit artifact, verify each cited gap and fix-instruction against HEAD before planning — the artifact's file-state claims aged the moment it was written

The 2026-07-02 efficiency review named "review protocols still let reviewers eyeball staleness" as a residual gap and prescribed "drop six verbs from REQUIREMENT_VERBS" — but the freshness lines had already shipped ten days earlier (PR #104), and the literal verb-drop would have created a new false-positive class (rename/redesign/rework are above the frequency floor; dropping them from the set makes the verb itself the reported orphan). Two cheap checks caught both: `git log -S` on the cited lines, and a 3-line floor-membership probe of the actual predicate. Do both before writing the plan for ANY fix-program item — the parent artifact is the requirement's evidence, not the current file state or a validated design. Validate Before Propagating (#15) applies to review artifacts too.

## When you add an ingest/IO surface to a platform-agnostic framework, expose the minimal data primitive — not one ecosystem's file format — or you silently lock out the toolchains the agnosticism promised

When a framework brands itself language/platform-agnostic, a core ingest surface must not be gated on one ecosystem's interchange format. test-evidence `record` accepted results ONLY as JUnit XML (default pytest, `test_command:` requiring `{junit_xml}`, `--from-junit`) — fine for the many stacks that emit JUnit, but it left embedded/HIL/bespoke toolchains with no paved on-ramp (hand-write the JSON, or fake a JUnit file). The fix is to expose the MINIMAL primitive the gate actually needs — for test results, pass/fail/skip counts (`--from-counts`) — so any toolchain participates without writing an adapter. It surfaced only because the user asked "are we breaking non-Python/embedded users?"; so when adding an ingest path, ask up front which real toolchains CAN'T produce its format. Corollary (same cycle): an upstream bug report's stated root cause is a HYPOTHESIS — the scriob report blamed a `git diff base...HEAD` membership shift the producers don't do (they diff base→worktree, commit-invariant); verify against source before designing, because the real fix was docs + this on-ramp, not the report's suggested content-hash (which a deliberate prior decision had rejected). Relates to Bring Expertise (#7), Honest Confidence (#5), Proportional Effort (#11), Verify-don't-guess, and [[backlog]] COV-4M2J (the Python-only coverage-floor residual).

## When a build plan ships in a different release than it targeted, its frontmatter `scope:` must be the scope-NAME (not a version) — `regen-views` resolves plans by it and a version there silently skips Status flipping at release

When a feature branch authored against version X gets batched into a later release Y, audit the build-plan frontmatter `scope:` field: it MUST equal the change-log `scope=` tag (the scope NAME, e.g. `hook-cli-robustness`), never a version string (`v2.1.7`). At release, `regen-views` enumerates each change-log `scope=` and resolves it to a build-plan FILE via that plan's frontmatter `scope:` (REL-4T8N); a version there means the scope resolves to no plan, the plan's `## Status` checkboxes never flip to `[x]`, and nothing errors loudly — you only notice if you audit. A PR reviewer may dismiss the stale version strings as a cosmetic Coherent-Artifacts nit; don't take that framing — verify against the convention (sibling plans all use the scope-name), because that one frontmatter line is load-bearing for release Status regeneration. Relates to Coherent Artifacts (#13), Validate Before Propagating (#15).

## When serially merging several stale feature branches into develop for one batched release, expect additive bookkeeping conflicts every time — and watch for a duplicate `active_build_plan:` key the auto-merge creates

Merging N stale feature branches into develop in sequence conflicts on the SAME bookkeeping files (`change-log.md`, `backlog.md`, `project-state.yaml`, `CHANGELOG.md`) on every merge, because each branch appended at the same anchor (file top / `## Open` section / pointer-history block). Resolve by UNION — keep both sides' additions; for the change-log, group all release-pending entries above the prior `release=vX` boundary regardless of their own header dates (the release flow enumerates by boundary, not date). The one real trap is `active_build_plan:`: branches that each set the pointer at DIFFERENT file positions produce a duplicate top-level YAML key after merge (different lines don't textually conflict, so git silently keeps both) — malformed YAML that is first-wins under the repo's line parser but LAST-wins under PyYAML (resolves to the wrong plan, silently disabling that scope's gates). Collapse to one canonical key. The per-branch cumulative Critic reliably catches it as the integration crack it exists to find — so run a fresh cumulative on each branch AFTER syncing develop in, never reuse a pre-sync record. Relates to Coherent Artifacts (#13), Independent Review (#14).

## When a session switches branches after SessionStart, pass the Critic mode explicitly — `infer-critic-mode` trusts the stale session-start branch marker

When you change branches mid-session (e.g. start on branch A, then `git checkout -b B` off develop to do unrelated work), do NOT let `/prawduct:critic` infer its mode — pass it explicitly (`cumulative`, then `verify-resolutions`). `infer-critic-mode` reads the branch recorded at SessionStart, so on branch B it can chain `verify-resolutions` to branch A's anchor SHAs; `compute-verify-resolutions-scope` only demotes when an anchor SHA fails to *resolve*, and a sibling-branch SHA still resolves (it's just not an ancestor of HEAD), so the guard passes and the review computes a cross-branch two-way diff full of PHANTOM findings (deletions/changes the sibling branch made, not your work). The Critic can self-flag this, but don't rely on it — anchor your review on the current branch from the start. Relates to Independent Review (#14), Honest Confidence (#5), Validate Before Propagating (#15), and [[backlog]] CRT-8H3R (the `git merge-base --is-ancestor` demote-guard fix).

## When prose picks which model a reviewer/subagent runs on, express it as an ordered fallback chain resolved at dispatch — never a pinned alias

When governance prose selects a model for a reviewer or subagent, write an ordered tier chain with a resolution rule ("use the first the harness lists as valid; fall back on a withdrawn/unrecognized model or dispatch error"), not a single pinned `model: X` — model lineups churn (Fable was pulled mid-cycle), and a pin either breaks when X is withdrawn or silently resolves to the *session* model (wrong tier), because Claude Code falls a blocked/unavailable subagent `model:` override back to the inherited/default model rather than erroring. Per-call and frontmatter `model:` take a single value (no built-in fallback syntax), so the chain is resolved by the runtime dispatching agent — the only actor that can see the live valid-model set (a Python hook can't). Verify harness/model behavior via `claude-code-guide`, don't recall it. Relates to Reasoned Decisions (#4), Honest Confidence (#5), Living Documentation (#3), and [[backlog]] REL-5K8M (deferred heavier mechanism).

## When verifying a framework-repo `lib/`/`bin/` change by running the hook, invoke the repo-local `python3 bin/prawduct-hook` — the bare `prawduct-hook` on PATH is the installed plugin cache, not your working tree

When you change `lib/` or `bin/` in the prawduct framework repo and confirm the behavior by running the hook, invoke the **repo-local** `python3 bin/prawduct-hook <cmd>` — NOT the bare `prawduct-hook` on PATH, which resolves to the installed plugin cache (`~/.claude/plugins/cache/prawduct/<version>/bin/prawduct-hook`, pinned to the *released* version and importing its *released* `lib/`). The PATH command shows STALE behavior, so a correct fix looks like it didn't take and you can misreport it as broken. The tell is a contradiction: the test suite passes (it runs `bin/prawduct-hook` from the repo root) while the bare command's output is unchanged — trust the repo-local invocation, and `command -v prawduct-hook` confirms which one you're hitting. Relates to Honest Confidence (#5 — don't report a fix as broken on stale evidence), Validate Before Propagating (#15), and Reasoned Decisions (#4).

## A clean cumulative (0 blocking/0 warning) makes post-review note-fixes asymmetric — `.md` fixes ride free, any `.py` change forces a fresh full review

When a cumulative Critic returns all-NOTEs (0 blocking / 0 warning), fix the `.md`-only notes in place — they ride FREE because the CRT-7M2D docs-only allowance keeps the existing cumulative HEAD-covering — but treat any `.py` note-fix as costing a full re-review, because verify-resolutions *demotes to final* exactly when no blocking/warning remains to verify. So self-scrub hard BEFORE the first cumulative, fix `.md` notes in place, and weigh each `.py` cosmetic note against one opus re-run — route low-value ones to a backlog item instead of re-reviewing. Relates to Review wall-clock is P0, Independent Review (#14), Proportional Effort (#11), and Scope Discipline (#12).

## A new build plan with `scope: null` and low chunk numbers inherits another scope's shipped checkbox flips — set `scope:` from the start

When creating a build plan, set the frontmatter `scope:` to a unique slug (matching the change-log entry's `scope=` tag) from the start — a `scope: null` plan is "legacy unfiltered" to regen-views, so EVERY `status=shipped` entry's chunk IDs flip its `## Status` checkboxes. Verify with `regen-views --check`. Relates to Coherent Artifacts (#13), [[new change-log entries on a feature branch are statusless]], and Validate Before Propagating (#15).

## New change-log entries on a feature branch are statusless — `status=in-progress` is deprecated and trips the regen-views typo-guard

When adding a change-log entry for work still on a feature branch, leave `status=` OFF entirely (carry only `type=`/`scope=`) — `status=in-progress` is deprecated and trips the regen-views typo-guard (valid: `{shipped, merged}`). Lifecycle: `status=merged` at the feature→develop merge; `status=shipped` + `release=vX.Y.Z` at the develop→main release. Relates to Coherent Artifacts (#13), Escape hatches create silent failures (#22), Honest Confidence (#5), and Living Documentation (#3).

## A change-log `chunks=` tag must match the build plan's chunk-heading numbering *exactly* (zero-padding included) or `regen-views` flips only the matching chunks

When tagging a multi-chunk change-log entry, `chunks=` must use the SAME numbering format as the plan's `## Status` headings, zero-padding included — `regen-views` matches chunk IDs as literal strings (`chunks=1` ≠ `Chunk 01`) and the failure is partial and silent. Confirm regen-views' flipped-count equals the chunk count; if fewer, align the tag to the headings (don't renumber the plan). Relates to Coherent Artifacts (#13), Validate Before Propagating (#15), and [[At release, flip statusless unreleased change-log entries]].

## When a feature's logic lives in a `context:fork` skill (no Bash), `lib/` holds the DATA, not the LOGIC — logic helpers nothing imports are dead code

When planning a feature whose logic lives in a `context:fork` skill (no Bash), put the DATA layer (parser + pure query accessors) in `lib/` for the runtime and the LOGIC in the skill prose — a fork skill cannot import `lib/`, so a `lib/` "logic helper" no Python path calls is dead code; descope it and RECORD the descope. Relates to The Design Is Sound (#7 — no dead code), Complete Delivery (#2 — record descopes), Scope Discipline (#12), and [[fine-grained tool restriction needs a fork-skill, not a named subagent]].

## At release, flip *statusless* unreleased change-log entries to `status=shipped` too — not just `status=merged`

At release-prep, enumerate ALL change-log entries above the prior `release=vX` boundary and flip each — statusless OR `status=merged` — to `status=shipped` + `release=vX.Y.Z`; a literal "merged→shipped" reading silently drops statusless entries (most of them) from checkboxes, release-notes, and scope_rollups, with no warning. Confirm via `regen-views --check`; deeper fix filed ([[backlog]] REL-2N8K). Relates to Complete Delivery (#2), Living Documentation (#3), [[new change-log entries on a feature branch are statusless]], and Validate Before Propagating (#15).

## "I'm just codifying their guidance" is not an exemption from the research trigger — and volatility is a separate axis from knowledge-confidence

Before declaring "no research needed," check volatility against the DESIGN and its INPUTS, not just the stated requirements — "I'm just codifying their guidance" conflates owner-specified content with the volatile design/placement choices around it. Rigor has TWO independent research axes — knowledge-confidence and volatility/recency (`methodology/discovery.md` "Calibrate Rigor") — and a volatility miss can coexist with high confidence. Relates to Honest Confidence (#5), Bring Expertise (#7), Validate Before Propagating (#15).

## The "canonical" mechanism for a capability can be disqualified by a plugin's composability + always-on constraints — verify the constraint before adopting the recommendation

When research names a "first-class / canonical" mechanism for a capability, verify it against the consumer's structural constraints (single active slot? clobbers? composes?) before adopting — a governance plugin needs always-on AND non-clobbering behavior, which disqualified Output Styles (`force-for-plugin: true` hard-overrides the user's own style) in favor of the composable SessionStart digest. Relates to Validate Before Propagating (#15), Reasoned Decisions (#4), Visible Costs (#9).

## When a fan-out render keys on a field that isn't unique, test the collision case — and a self-authored adversarial pass inherits the author's blind spots

When a renderer or fan-out groups by a field, add an explicit test for the field-COLLISION case (≥2 inputs sharing the key; usually "group by the key first" is the model). A self-authored adversarial pass inherits your blind spots — the durable catch is an independent reviewer working from real artifacts. Relates to Independent Review (#14), Tests Are Contracts (#1), and Validate Before Propagating (#15).

## When fanning out a batch build to parallel worktree-isolated workflow agents, partition by disjoint file ownership (integrator owns shared files) and force-clean leftover worktrees before the integration suite

When fanning out a batch build to parallel worktree-isolated agents, partition so each agent OWNS a disjoint file-set, reserving shared files for the integrator (agents only REPORT needed changes there); governance stays in the main session (full suite, evidence, cumulative Critic). Force-clean leftover `.claude/worktrees/wf_*/` before the integration suite — dirty worktrees don't auto-remove and trip structural tests. Relates to Independent Review (#14), Scope Discipline (#12), and Proportional Effort (#11).

## When a fresh-eyes review's advice about a CONVENTION conflicts with a durable learning + the process doc, the documented convention wins — re-verify before acting

When a forked Critic / PR reviewer makes a claim about how this project does bookkeeping, treat it as a reading of the CURRENT tree, not institutional authority — it hasn't read `learnings.md` or `docs/release-process.md` and can over-generalize. When its claim diverges from a durable learning + the process doc, RE-READ those and follow them. Relates to Validate Before Propagating (#15), Independent Review (#14), and Close the Learning Loop (#18).

## A reviewer's NOTE/severity is a prior, not a verdict — re-scope any "harmless" change that touches a governance-gate input

When a review rates a change low-severity ("harmless"), treat the label as a prior, not a verdict — for any edit to a governance-gate's input set (allowlists, prefix tables, fileset bounds), grep the predicate's call sites, decide whether behavior actually changes, and add a test when it does. Relates to Tests Are Contracts (#1), Root Cause Discipline (#16), Independent Review (#14), and Honest Confidence (#5).

## A new framework-wide DEFAULT must land in the session digest — place-once preferences and the thin anchor don't reach migrated repos

When changing a framework-level default every product (any vintage) should pick up, the carrier must be `methodology/session-digest.md` — the only surface injected into every product session unconditionally; `templates/project-preferences.md` is place-once (never regenerated) and a migrated repo's CLAUDE.md is only the thin anchor. Ask "which surface does an *already-onboarded* repo actually re-read?" Relates to Coherent Artifacts (#13), Visible Costs (#9), and Proportional Effort (#11).

## Single-repo plugin+marketplace: the marketplace entry's plugin `source` must be `"./"`, not `{source:github,ref}`

When a plugin and its `.claude-plugin/marketplace.json` live in the SAME repo, the plugin `source` must be the relative `"./"` — the `{source:github,repo,ref}` form re-clones over SSH and fails without SSH keys even for a public repo; `"./"` reuses the marketplace's own HTTPS checkout. (The consumer's `extraKnownMarketplaces` github source is a different, valid surface.) Relates to Validate Before Propagating (#15) and Visible Costs (#9).

## Release-bound work merged feature→develop under gitflow: KEEP the build plan — it's a live release artifact, not spent

When a feature branch merges to develop but ships at a LATER develop→main release (gitflow batched-release), KEEP the build plan and the `active_build_plan` pointer until the release — the release step runs `regen-views` on the plan to flip its `## Status` checkboxes; delete at merge only when the develop-merge is itself the release. Relates to Coherent Artifacts (#13), Living Documentation (#3), and Proportional Effort (#11).

## A `--plugin-dir` read-block is a dev-flag artifact, not a self-containment bug — pair it with `--add-dir`

When a `--plugin-dir <path-outside-the-project>` test shows a skill unable to read its OWN bundled file, that's the working-dir read sandbox, not a self-containment bug — pair it with `--add-dir <plugin-path>` (a marketplace install grants plugin-tree reads automatically); do NOT "fix" the skill's paths. Relates to Honest Confidence (#5) and Validate Before Propagating (#15).

## Test subprocesses: HOME=tmp_path leaks Python's pyc cache into the test repo

When a test's Python subprocess runs with `HOME` inside the test's git repo, the interpreter writes pyc caches under `$HOME/Library/Caches/com.apple.python/`, polluting `git ls-files --others` and triggering scope/status false failures — set `HOME` to a directory OUTSIDE the repo. Relates to Structural Awareness (#21).

## "Structurally enforced" requires verifying the harness actually enforces it

When claiming a constraint is "structurally enforced" by a config/sandbox/permission system, verify with a negative-path probe (a test asserting the forbidden invocation is actually blocked) before claiming it — a broader allow pattern (project-level `Bash(python3:*)`) can override a skill-level `!`-deny. Relates to Honest Confidence (#5) and Validate Before Propagating (#15).

## Tool-restricted reviewer agents must be context:fork SKILLS, not named plugin subagents

When an agent needs fine-grained tool restriction, implement it as a `context: fork` skill with a pure-allow `allowed-tools` list — NOT a named plugin subagent, whose frontmatter is bare-tool-names-only (listing `Bash` grants unrestricted Bash) and which a delegating skill's `allowed-tools` does not bind. Relates to Reasoned Decisions (#4) and safety constraint CRT-2M5P; headless-vs-interactive enforcement of the fork-skill cap is still open (backlog CRT-9V4T).

## When a deliberate change turns a passing test red, renegotiate the contract in the open

When you deliberately change documented behavior and an existing test fails because it encoded the OLD behavior, don't silently relax or delete the assertion — rename the test to the new contract, invert the assertion, record the rationale, and keep any still-valid invariant asserted. "Fix the code, not the test" assumes the test encodes CORRECT behavior; a test encoding the thing you're removing is a contract to renegotiate transparently. Relates to Tests Are Contracts (#1) and Reasoned Decisions (#4).

## A behavior change isn't done until every artifact that DESCRIBES it is updated

When you change behavior that a synced/templated/documented artifact describes, grep for every place that DESCRIBES it, not just the code implementing it — the independent cumulative review is the fresh-eyes pass that catches doc-vs-behavior drift the builder is blind to. Relates to Living Documentation (#3) and Independent Review (#14).

## A decision reversed mid-chunk leaves stale rationale in prose you just wrote

When you reverse a design decision partway through a chunk, re-grep your OWN new comments/docstrings for the abandoned rationale before handing to the Critic — code follows the new decision, but prose written under the old one keeps asserting it, and it feels trustworthy precisely because it's fresh. Relates to Living Documentation (#3) and Reasoned Decisions (#4).

## Editing a runtime that governs the current session: check your own signals first

When you modify a runtime that ALSO governs the session you're editing in, run the new detection against the repo root and confirm the expected value BEFORE relying on the edit — a wrong signal can silently disable the very gate enforcing the current session, with no test failure to warn you ("am I standing on the branch I'm sawing?"). Relates to Structural Awareness (#21) and Validate Before Propagating (#15).

## Pre-dispatch bootstrap code must fail open on a `lib/` ImportError

`get_project_dir()` and any other helper that runs in `main()` BEFORE command dispatch must not hard-depend on the lazily-imported plugin `lib/`: wrap the lib call and fall back to the env/cwd behavior on `ImportError`. Adding a `lib` call there once broke the `regen-views` "could not import" contract — the eager import crashed with a traceback before the command's own graceful handler could fire. The hook's lib-free top level + lazy per-command imports are the architecture; bootstrap code that pre-empts a command's import-error handling defeats it. Relates to Honest Confidence (#5) and the broad-except/fail-open conventions.

## Session-end signals must come AFTER handoff

When signaling session completion ("Ready for next session", "Session is complete"), do the handoff FIRST — commit, update build plan Status, write reflection, capture backlog. Because users interpret completion signals as "handoff is done" and act on them immediately.

## Artifacts drift silently during sustained building

When building multiple chunks, update artifacts (test specs, architecture, data model) as code changes what they describe — not at the end. Because the Critic checks bidirectional freshness, and stale specs become planning fiction. Relates to Living Documentation (#3).

## Structural gates must match natural workflow

When adding structural enforcement (hooks, gates), check BOTH reasonable locations for the thing being enforced. Because the Critic gate only checked `artifacts/build-plan.md` but the natural location was `project-state.yaml`, so the gate never fired for 40+ sessions. Relates to Governance Is Structural (#22).

## Growing files need structural nudges to prune

When a file has a size target, add a mechanical check (not just guidance). Because guidance alone never triggers pruning — the session-start hook warns when `project-state.yaml` exceeds 40KB, prompting compaction before context bloat compounds. Relates to Close the Learning Loop (#18).

## Reactive systems can't detect missing things

When validating work, also ask "what should exist here that doesn't?" — not just "is what exists correct?" Because the learning pipeline, Critic, and reviews all validate quality of existing work but cannot identify missing cross-cutting concerns or artifact categories. Relates to Automatic Reflection (#17).

## Governance complexity breeds governance complexity

When adding enforcement, first ask "is this failure already covered by something that exists?" Because after 11 independent additions, hooks alone exceeded the skill files they protected. Impact-scaled processes (lightweight for small, heavy for structural) reduce the temptation to make everything heavyweight. Relates to Proportional Effort (#11).

## Principles need runtime enforcement, not just change-time checks

When receiving guidance or making decisions, actively check against principles — not just during retrospective review. Because the framework accepted a 285-line technology-specific design that violated "Generality Over Enumeration" since the principle wasn't applied at decision time. Relates to Governance Is Structural (#22).

## Denormalized state drifts without mechanical validation

When data appears in multiple places, compute derived values on demand or mechanically validate after writes. Because 5 parallel agents produced 12 inconsistencies in denormalized inverse-dependency fields. Relates to Coherent Artifacts (#13).

## Coherence cascades require checking summaries, not just primary locations
<!-- prawduct-learning: confirmations=2; created=2026-01-30 -->

When adding a concept to a system, grep for every place that *summarizes* or *enumerates* what the system contains. Because summaries are denormalized state — they drift when the source changes. Also check scope declarations (section comments saying "only for X") and test scenarios (sibling concepts need rubric criteria too). Reinforced 2026-02-22 with identical miss. Relates to Coherent Artifacts (#13).

## Escape hatches in classification create silent failures

When classifying inputs with an "unknown" or "other" bucket, default to blocked, not allowed. Because an entire product was built without governance when unregistered repos fell into the "ungoverned" auto-allow escape hatch. Relates to Governance Is Structural (#22).

## Cumulative-Critic finds first-use regressions chunk-Critic can't

When wrapping a multi-chunk bundle, expect the cumulative-Critic pass to surface ≥1 finding the chunk passes missed — it diffs `merge-base...HEAD` and catches helper-vs-prose interactions invisible at chunk scope — so plan a remediation slot before `/pr create` rather than treating it as a formality. Relates to Independent Review (#14).

## Auto-enable belongs with visibility, not with enforcement

When deciding whether a new opt-in feature should silently auto-enable, ask whether flipping it ON would BLOCK the next PR: visibility surfaces auto-enable safely; enforcement surfaces must be explicitly invoked so the workflow commitment is visible before it bites. Owner override (v2.0.0 §5a): with governance modeled AS CI, an update MAY ship an immediately-blocking gate if the block is ATTRIBUTED (banner + message name the version and gate) — visibility as attribution, not opt-in. Relates to Visible Costs (#9) and Governance Is Structural (#22).

## Removing a mechanism requires removing its name too

When removing a mechanism, grep for its NAME in active prose in the SAME change and update each hit — lingering names send readers hunting for code that doesn't exist. Caveat: only remove the name from a path the mechanism has actually LEFT — a mechanism kept alive for un-migrated consumers is a live service; verify nothing reaches back at runtime before deleting. Relates to Living Documentation (#3), Close the Learning Loop (#18), and Unnecessary Backwards Compatibility.

## Build-plan fields use `**Title Case:**`, not snake_case

When adding a build-plan field, format the label `**Title Case:**` (matching `**Type:**`, `**Done when:**`) — snake_case is the `project-state.yaml` YAML-key namespace, a different surface — and keep the methodology's prose form string-identical to the template's label (minus bolding) so the Critic's substring-match finds real plans. Relates to Coherent Artifacts (#13).

## Build-plan chunk headings must use `### Chunk N:` colon form — em-dash fails the parsers silently

Build-plan chunk headings and `## Status` lines must use the colon form (`### Chunk N: Name` / `- [ ] Chunk N: Name`) — the chunk-id parsers split on `:`, so an em-dash separator silently disables ref verification and per-chunk scoping for the WHOLE plan (chunk-type fail-closes to `code`). Leading zeros are tolerated; add a guard test that the active plan's headings parse — build-plan text is a contract with the parsers. Relates to Coherent Artifacts (#13), Escape hatches create silent failures (#22), and Honest Confidence (#5).

## Submodule and same-name function in __init__ shadow each other

When a `lib/__init__.py` re-exports a function whose name matches its submodule (`from .foo import foo`), attribute access returns the function while `sys.modules` holds the module — `import lib.foo as alias` resolves to either depending on context and monkeypatching breaks. Use the `_cmd.py` suffix convention; it exists to prevent this collision. Relates to Coherent Artifacts (#13) and Reasoned Decisions (#4).

## Detection of structural characteristics should not rely on mechanistic surface markers

When classifying whether a project has a structural characteristic (LLM inference, human interface, unattended, sensitive data, multi-process), answer "what does correctness depend on?" first and use surface markers (imports, hostnames, filenames) only as evidence — mechanistic markers miss variant manifestations of the same structural feature. Relates to Structural Awareness (#21), Honest Confidence (#5), and Bring Expertise (#7).

## Shared "answer" state and personal "nag" state belong in separate stores

When designing state about ongoing concerns (advisories, follow-ups, todos), keep the committed team-shared ANSWER (e.g. `project-state.yaml`) separate from the gitignored per-clone "have I dealt with this nag?" state (e.g. `.advisories.json`) — conflating them either leaks personal dismissals across clones or stops a teammate's committed answer from auto-clearing everyone's nag. Relates to Coherent Artifacts (#13) and Structural Awareness (#21).

## Framework ownership follows the write strategy, not just registry membership
<!-- prawduct-learning: confirmations=1; created=2026-05-19; sentinel=tests/test_prawduct_sync.py::TestAutoCommitSafety::test_user_authored_place_once_edits_treated_as_wip -->

When defining "the framework owns this file" sets, the discriminator is whether the framework OVERWRITES the file on every run, not registry membership — overwrite-each-sync and place-once strategies have opposite ownership semantics after first creation, so derive the sets from the strategies that overwrite (the manifest's `files` dict), never from every path the framework ever placed. Relates to Reasoned Decisions (#4) and Coherent Artifacts (#13).

## A leftover marker is not an in-progress signal — and a test using the canonical marker leaves the real-world branch untested

When detecting external-tool state from filesystem markers, check whether the tool REMOVES each marker when the condition ends (git leaves `REBASE_HEAD` behind) — prefer the tool's own authoritative test (the `rebase-merge`/`rebase-apply` dir check). Also: test EACH detector input path with messy real-world leftovers, not just the canonical marker; never cache a derived blocker without re-evaluation — a transient false positive becomes permanent. Relates to Tests Are Contracts (#1), Root Cause Discipline (#16), and Honest Confidence (#5).

## A near-verbatim file PORT carries the source's prose — adapt the docs, not just the logic

When creating a file by copying and adapting an existing one, treat the port as TWO passes — logic-adapt, then a doc-sweep grepping the copy for docstrings/comments/messages true only of the SOURCE's world. EXCEPTION: leave verbatim any string that is a cross-file CONTRACT a consumer matches on — renaming it silently breaks the consumer. Relates to Living Documentation (#3), Coherent Artifacts (#13), and The System Can Be Understood (#6, accurate diagnostics).

## A subagent's reported COUNT or LIST is a lead, not ground truth — verify before a blanket edit

When a subagent reports an enumeration you'll act on mechanically ("N occurrences", "these call sites"), re-derive the set with a direct `grep -c`/`grep -n` right before any `replace_all` or uniform sweep — an undercount leaves a site on the old form as a silent miss. Relates to Validate Before Propagating (#15) and Honest Confidence (#5).

## Verify the platform's copy/packaging boundary before duplicating a shared bundled file — a prior "duplicate into each consumer" choice may be an unverified-constraint workaround

Before duplicating a shared file into each consumer dir vs. referencing one canonical copy, verify the platform's packaging boundary — and don't cargo-cult an earlier duplication made when it was unverified: a marketplace install copies the WHOLE plugin tree, so one canonical source at plugin root beats a parity-tested copy. Relates to Validate Before Propagating (#15), Reasoned Decisions (#4), and the DRY design goal (Critic Goal 7).

## A plugin skill with unparseable YAML frontmatter loads with ALL metadata silently dropped — validate it in CI
<!-- prawduct-learning: confirmations=1; created=2026-06-02; sentinel=tests/test_plugin_manifest.py::TestAllPluginSkillFrontmatter -->

A frontmatter YAML parse error in a plugin skill does NOT fail loud — the loader drops EVERY field and the skill loads unusable while the unit suite (which never exercises the loader) stays green. Parse every `skills/*/SKILL.md` frontmatter with `yaml.safe_load` in a test AND run `claude plugin validate`; quote scalars containing `:` / `#` / `|`. Relates to Validate Before Propagating (#15) and Tests Are Contracts (#1).

## Dogfooding the generator on its own output masks output-relative bugs the real consumer would hit

A generator running its OWN output (e.g. `--plugin-dir .`) can't prove self-containment — tree-relative paths resolve because the generator's checkout has them. Prove "no external files needed" by a STATIC audit for tree-relative reads plus a run against a tree that genuinely lacks the generator's source. Relates to Validate Before Propagating (#15) and Honest Confidence (#5).

## Relocating a source file: sweep every READER of the old path, not just the data-key references

When moving a source file, sweep EVERY reader of the old path — grep it for `read_text` / `open` / fixture writes, not just the path string used as a data key; content-assertions and fixtures that touch the old path surface only on the full-suite run. Relates to Validate Before Propagating (#15) and Living Documentation (#3).

## A review's "inert / harmless" verdict on a latent bug is conditional on the current call graph

A review's "inert / harmless" verdict on a latent defect is conditional on the current call graph — the next feature touching the dormant path makes it live, so when new code touches a path a prior review called inert, re-check the verdict's premise first. Relates to Honest Confidence (#5) and Root Cause Discipline (#16).

## Excising a subsystem silently kills the incidental work it happened to host — re-home the orphaned call, and test the positive

When removing subsystem X, list everything X DID and split "X's actual job" from "work X merely hosted" — co-located incidental work dies silently, and tests asserting X is GONE never catch it. Re-home orphaned work to a surviving call site and add a regression test that the re-homed behavior STILL happens (test the POSITIVE). Relates to Root Cause Discipline (#16), Validate Before Propagating (#15), and Complete Delivery (#2).

## A "renders-but-doesn't-resolve" leak is a SURFACE, not a line — sweep the whole renderer and assert the bad form is ABSENT

When output names something that won't resolve in the current context (a bare `/backlog` in a plugin repo), fix every command-bearing line in the SAME renderer in one pass — grep the whole renderer (leaving its frozen-context twin untouched) — and pin with BOTH assert-present and assert-absent tests — a presence-only assertion passes while a sibling line still leaks. Relates to Coherent Artifacts (#13), Validate Before Propagating (#15), and Complete Delivery (#2).

## An "assert the bad form is ABSENT" sweep is only as good as the pattern that defines the bad form — enumerate the whole FORM-FAMILY, not one spelling

Before declaring a namespace/rename sweep done, enumerate every SPELLING the frozen vocabulary uses (bare `/cmd`, hyphenated `/prawduct-cmd`, legacy CLI `prawduct-setup`) and grep each — every spelling is a distinct regex the others won't match — then bake the full spelling-set into the absent-assertion's FORBIDDEN list. Extends the renderer-surface rule above. Relates to Validate Before Propagating (#15) and Complete Delivery (#2).

## An untested governance bound rots silently across a migration — sweep the guards (with tests), not just the prose

When a migration removes or relocates a mechanism, enumerate the GUARDS that referenced the old shape (path bounds, allowlists, parity tests, prefix tables) and repoint them, add the missing regression test, or RESTORE a deleted guard rather than deleting its dangling references — a guard with no test is the likeliest carrier of a stale literal through a cutover. Relates to Tests Are Contracts (#1), Root Cause Discipline (#16), and "Removing a mechanism requires removing its name too".

## In a leaf-first decomposition, dependency-scan a chunk's COMMAND bodies against later-chunk symbols before moving — and never move a parity-pinned mirror just because a deliverable lists it

In a leaf-first module extraction, before moving a chunk's symbols: (a) AST-scan each moved COMMAND body for references to symbols slated for LATER chunks — a command body can reach UP the DAG even when its helpers move down it — and defer that body to the owning chunk; (b) grep each moved def's comments + the test suite for `mirror` / `*Parity*` / `import-light` — a parity-pinned mirror stays put even if the deliverable lists it. Relates to Validate Before Propagating (#15), Requirements Precede Code (#6 — the plan is the parent; correct it openly), and Reasoned Decisions (#4).

## A format's schema legend lives in `templates/` (scaffold-only) — adding an optional field reaches already-onboarded repos only via a migrate/triage *refresh* step, not the template

When adding an optional field to a structured-file format, wire BOTH propagation surfaces: the per-item backfill (triage/`migrate`) AND a `migrate` legend-refresh reconciling the file's schema-legend header to the canonical field set (additive-only); anything living only in `templates/` is scaffold-only and never reaches onboarded repos. Relates to Living Documentation (#3), Coherent Artifacts (#13), Complete Delivery (#2), and [[a new build plan with scope null inherits another scope's shipped checkbox flips]].

## A structural bound that ENFORCES a declaration is not a DETECTOR of the declared property — reusing it at a new boundary silently drops its justification

When reusing a structural predicate at a second boundary, re-derive why it's valid THERE — a NECESSARY condition that enforces a declaration is not a SUFFICIENT detector of the declared property, and reused without the declaration it silently waives gates; confirm the predicate establishes the new decision's sufficient condition, and give every skip-gate a regression test that a non-eligible case still BLOCKS. Relates to Reasoned Decisions (#4), Validate Before Propagating (#15), Governance Is Structural (#22), Tests Are Contracts (#1), and [[an untested governance bound rots silently across a migration]].

## A rebuild scoped to a subsystem's "remaining / deferred" parts silently omits an already-shipped part that was deleted in between — re-port against the spec roster, not the open-work list

When rebuilding/porting a subsystem, enumerate its members from the SPEC roster and diff against what the new module actually registers — a "remaining N" open-work framing assumes the already-shipped part still exists, and a deletion in between makes the rebuild silently omit it — re-confirm the assumed baseline and add an end-to-end test driving the REGISTERED roster. Second chapter of [[excising a subsystem silently kills the incidental work it happened to host]]. Relates to Complete Delivery (#2), Root Cause Discipline (#16), Validate Before Propagating (#15), and [[removing a mechanism requires removing its name too]].

## A persisted schema's requirements are its consumers' future queries — lock-in is reversal cost, not LOC, so "small format" never exempts it from decision research

A chunk introducing any persisted format/schema/ledger must enumerate, in the plan, the questions the data must answer over time — elicited from its future consumers, not inferred from the mechanism — before designing fields; judge lock-in by REVERSAL cost, never LOC; user endorsement of a diagnosis is not requirements confirmation for the artifacts implementing it. Relates to Requirements Precede Code (#6), Reasoned Decisions (#4), Bring Expertise (#7), and Honest Confidence (#5 — mechanism-confidence is not requirements-confidence).

## Test-evidence freshness is `test-status` (session timestamp) ONLY — `git_sha` was retired as misleading (TST-4K2P)

The freshness gate (`prawduct-hook test-status`) decides current-vs-stale by `timestamp >= .session-start`, never by a commit field. The record no longer carries a `git_sha`: TST-4K2P removed it because it was **dead-read** by every runtime consumer yet review agents *eyeballed* it and flagged a false "stale / ran against a tree without the fix" whenever a record-before-commit run made the stamp lag HEAD. Consequences: (1) record timing no longer matters for freshness — the old "record AFTER commit, on a clean tree" stopgap is **obsolete**; record whenever in the cycle. (2) When reviewing, judge freshness ONLY by the `test-status` exit code — never infer staleness from a commit/SHA field (there is none). (3) Content-hash freshness is deliberately **not** reintroduced — that mechanism was removed pre-v1.4 for chronic false positives; the build cycle (write → test → Critic) is the trust boundary. Relates to Honest Confidence (#5 — don't let a misleading field read as a real gap), Validate Before Propagating (#15), and [[when verifying a framework-repo change by running the hook use the repo-local bin/prawduct-hook]].

## A cross-cutting concern can be UNCOVERED even when discovery names it once — audit the coverage matrix for "named-but-dropped", not just "absent"

A concern discovery mentions in passing but no downstream stage operationalizes (no artifact template, no builder guidance, no Critic check, no matrix row) is *uncovered*, not covered — a failure distinct from "absent," and one the coverage matrix itself misses because it lists concerns without auditing whether each is carried *through* all four columns. When checking pipeline coverage, walk each named concern across Discovery → Artifact → Builder → Critic and treat a name-without-operationalization as a gap; the cost is real (../scriob ran ~697/700 commits with its API unversioned on an unchallenged one-word "versioning deferred" note, then paid a coordinated breaking-change retrofit). The framework had no opinion to pressure-test the deferral with, because the concern was named but never built. Relates to [[reactive systems can't detect missing things]] (the Critic reviews diffs, so a never-built concern is invisible to it), Complete Delivery (#2), Governance Is Structural (#22), and Validate Before Propagating (#15).

## When generalizing or detecting "across all cases", the COMMON / AVAILABLE instance silently narrows the requirement to itself — check coverage against the requirement's stated breadth

Writing general guidance, a transport-/protocol-neutral template, or a "detect X everywhere" scan, the most common instance (HTTP for APIs, Python for a code scan) and the most *available* primitive (a `*.py`-only `has_imports`, a Read/Glob-only skill) try to colonize the general framing — you ship something that silently covers only the common case. Before calling it general: state the requirement's stated breadth explicitly and check each instance (library/SDK, on-device, CLI — not just network/HTTP; JS/Go/Java manifests — not just Python imports), and confirm the primitive or tool-grant you build on can actually *see* that breadth (a Read/Glob skill can't grep source; a `*.py`-only scanner can't read `package.json`). Extend the primitive (or attribute the unreachable signal to the surface that can reach it) rather than narrow the requirement to fit the tool. Caught three times in one feature: the api-contract template framed HTTP-only, doctor #9's prose implied a grep its tool-grant lacked, and the advisory probe's base primitive saw only Python. Relates to Complete Delivery (#2), Honest Confidence (#5 — don't let prose imply a reach the tool grant lacks), Bring Expertise (#7), and [[detection of structural characteristics should not rely on mechanistic surface markers]].

## Before "fixing" an apparent forgotten-manual-update, check whether the artifact is a GENERATED / DERIVED view — the real fix is upstream

When something looks like a stale or forgotten manual edit (an unflipped checkbox, an out-of-date count, a summary that lags), first ask whether that artifact is *derived* from a canonical source rather than hand-maintained — a correct-looking manual edit to a generated view is churn the generator silently overwrites, and the diagnosis ("someone forgot to update it") is wrong. In this repo `views_enabled: true` makes a build-plan `## Status` block a derived view of `change-log.md` `status=shipped|merged` tags: checkboxes flip at merge/release via `regen-views`, so `[ ]` on a feature branch is the CORRECT derived state, not a gap — I hand-flipped Chunks 01/02 to `[x]`, wrote a reflection calling it a "coherence gap," and `regen-views` overwrote it back to unshipped. The methodology already says "don't hand-edit Status when views_enabled" — the trap was acting on the *symptom* before checking the *generation model*. Verify what writes an artifact before you write it; fix the source (the tags), then regenerate. Relates to Validate Before Propagating (#15), Living Documentation (#3 — docs describe reality, but derived docs describe it *through* their source), Root Cause Discipline (#16), and [[denormalized state drifts without mechanical validation]].

## A test asserting the framework repo's OWN state instead of the propagated contract gives false coverage — assert the contract that reaches consumer repos

When a feature emits ephemeral/derived state that must be gitignored (or any default that must reach onboarded products), the load-bearing surface is the **canonical contract that propagates** (`lib/core.py::GITIGNORE_ENTRIES` + its `bin/prawduct-hook` mirror, `templates/`, `methodology/session-digest.md`), NOT this framework repo's own files. Dogfooding hides the gap: the work-model index (PR #71) added its ignore line only to this repo's hand-edited `.gitignore` and to no contract list, so `update_gitignore` never wrote it into product `.gitignore` files and every onboarded repo carried the runtime-generated file as permanent untracked noise. The guard test `test_index_is_gitignored` *passed the whole time* because it asserted this repo's `.gitignore` — the one surface that didn't matter. When a feature ships a propagated default, the regression test must assert the contract list AND the end-to-end propagation (`update_gitignore` writes the line into a fresh product `.gitignore`), never just the framework repo's dogfood state — a test scoped to the producer's own copy is false coverage for everything downstream. Same root shape as [[A format's schema legend lives in `templates/` (scaffold-only) — adding an optional field reaches already-onboarded repos only via a migrate/triage *refresh* step, not the template]]: anything living only in the framework repo does not reach onboarded repos; propagation goes through the canonical carriers. Relates to Tests Are Contracts (#1), Validate Before Propagating (#15), Complete Delivery (#2), and Clean Deployment (#10 — dev-time dogfood state masking a product-facing defect).

## When a plan sets a quantitative reduction/size floor over a corpus you cannot shrink by dropping content, derive the floor from a per-file compressibility sample — not a global intuition

A "halve it" intuition prices the redundancy you can *see* (triplicated matrices, boilerplate) but not the corpus's irreducible mass — single-statement rules, behavior tables, weaker-model anchors that a no-drop constraint forbids you to touch. prose-diet set ≥45% / target-50% from a triplication intuition; honest single-sourcing over a rule-dense, no-drop corpus reached only −30.3% (single-sourcing recovered ~3–4k est tokens, not the assumed bulk; ~2.6k was carved out as out-of-scope; the review program had already certified one protocol lean), forcing an owner floor-amendment at close-out. A floor set above honest reach converts Complete Delivery (#2) into a forced trade-off precisely when you can least afford it — you either drop a load-bearing rule to hit the number or miss your own acceptance bar. Before committing a reduction floor under a no-drop constraint, sample 2–3 representative files, estimate each one's honest compressibility, and derive the floor from that — record it as a vetoable assumption, not an aspiration. Detail in [[learnings-detail]] under the same heading. Relates to Complete Delivery (#2), Reasoned Decisions (#4), Honest Confidence (#5), Proportional Effort (#11).
