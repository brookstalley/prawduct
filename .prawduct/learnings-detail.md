# Learnings

Accumulated wisdom from this project's development. Read this at session start — it directly informs how you work. Entries are ordered by relevance; most important patterns first.

No size constraint on this file — it's the deep reference, consulted via `/learnings` or directly when debugging in a known area. Prune entries that have been incorporated into principles, methodology, or structural enforcement.

---

## When `check-cumulative-critic` reports `uncovered` on a branch whose code you know was reviewed, suspect a stale base before running a fresh review — the gate anchors to `origin/<base>` by design, so unpushed integration commits drag already-shipped work into the required span

**Pattern**: v3.0.3 release (2026-07-14). Wrapping a +0.0.1 release, `check-cumulative-critic`
reported `uncovered: no composed review evidence spans 136bca56..b9b4356 at HEAD` for a feature
(`tree-validated-test-evidence`) whose change-log said it had a clean final Critic + a
verify-resolutions pass. Investigation, not re-review, was the right first move.

**Root cause — a two-layer staleness.** (1) `resolve-base` returned `origin/develop`, which sat at
**v3.0.1** while local `develop` was at **v3.0.2** — three unpushed commits, including a
`release-prep(v3.0.2)` that had never been promoted to `main` (a "phantom release": version files
and `develop` moved, but the `develop→main` promotion + push never happened, across sessions).
(2) `check-cumulative-critic` composes review facts from `merge-base(base, HEAD)`'s TREE forward;
with the base stale, the required span became the whole **v3.0.2 + v3.0.3** range. The evidence
store DID contain a clean fact for every piece (`test-evidence-ingest-test-command` base_tree
`136bca56`→`9136970e`; `tree-validated-test-evidence` `998c5d31`→`cb5aa9ca`→`669e94d5`, all
blocking=0), but no single chain composed from the stale `origin/develop` tree to HEAD because the
reviewed *working* trees never exactly equalled the committed trees (docs/release-prep tails).

**The fix was reconciling the base, not re-reviewing.** `git push origin develop` (a required
release step regardless) advanced `origin/develop` to the local tree; re-running the gate then
reported `satisfied: ... 2 review fact(s) + 1 free edge(s), 0 unresolved blocking` — the chain now
began at `develop`'s actual tree (`998c5d31`, exactly the feature's review base) and the single
free edge was the docs-only tail the CRT-7M2D allowance excuses. Zero fresh review needed.

**Diagnostic order** (bank this to avoid the 4–10 min wrong remedy the stderr suggests):
1. `prawduct-hook resolve-base` — is it `origin/<b>`?
2. Is local `<b>` ahead of `origin/<b>` AND an ancestor of HEAD? (feature cut from unpushed base)
3. If yes → `git push origin <b>` and re-check the gate BEFORE `/prawduct:critic cumulative`.
4. If unsure, read the evidence store (`<git-common-dir>/prawduct/evidence.jsonl`): the review
   chain's earliest `base_tree` should equal `merge-base(resolve-base, HEAD)`'s tree; if it equals
   the LOCAL integration tree instead, the base is stale.

**Systematic follow-through**: filed COV-7K4N (a stale-base hint on the uncovered path so the gate
diagnoses this itself + an unpromoted-release-prep session-start advisory for the root cause;
deferred spike on preferring the nearer of local/remote base). Frequency is low — needs gitflow
(`base_branch: develop`) AND a feature built on an unpushed local-`develop` advance; trunk repos
(base = `main`) essentially never hit it since `main` never sits locally-ahead. The gap that
warrants the fix is the *misleading remedy* when it does fire, not the frequency. Relates to Root
Cause Discipline (#16), Validate Before Propagating (#15), Honest Confidence (#5), and COV-5H3N
(the distinct wrong-default-to-`main` facet), PR-7T2K (the mirror-image feature-branch push-state
case).

## When you add an ingest/IO surface to a platform-agnostic framework, expose the minimal data primitive — not one ecosystem's file format — or you silently lock out the toolchains the agnosticism promised

**Pattern**: test-evidence-single-run (2026-06-26, v2.2.3). An upstream report (COV-3R9K, scriob)
said consumers run the suite twice per chunk. A multi-agent investigation found the double-run was
NOT gate-forced (freshness is session-scoped; `changes_referenced` is base→working-tree
content-based, commit-invariant) — it came from a retired "record after the final commit" habit.
While scoping the fix, the user asked: "prawduct is supposed to be language/platform agnostic — are
we breaking embedded/non-Python users?" Auditing the recorder showed it was JUnit-XML-coupled: the
default runner is pytest, the `test_command:` knob REQUIRES a `{junit_xml}` placeholder, and
`--from-junit` ingests JUnit. JUnit is a broad de-facto standard (pytest/vitest/ctest/nextest/
gotestsum all emit it), so `test_command:` already made the recorder runner-agnostic FOR
JUnit-emitters — but a bespoke HIL rig or custom harness that can't emit JUnit had only two off-road
options: hand-write `.test-evidence.json` (the gap TST-6V2N closed) or write a JUnit adapter.

**Fix**: `--from-counts passed=N failed=M skipped=K [duration=S]` — the minimum viable test result
is pass/fail/skip counts; forcing those through JUnit XML WAS the coupling. The on-ramp records
counts directly (no run), so any toolchain participates. The Python-only COVERAGE floor (symbol-grep
in `bin/test-reference-verify`) is a separate, larger gap, split to COV-4M2J.

**Two lessons**: (1) When you add an ingest path to an agnostic framework, ask which real toolchains
CANNOT produce its format BEFORE shipping — agnostic-for-X is not agnostic. (2) A bug report's stated
root cause is a hypothesis: the report blamed a three-dot `git diff base...HEAD` shift, but the
producers use two-arg `git diff <base>` (base→worktree, commit-invariant); verifying against source
(not recalling, not trusting the report) redirected the whole fix from the report's suggested
content-hash (a deliberately-rejected mechanism, pre-v1.4 + TST-4K2P) to documentation + the on-ramp.
Relates to Bring Expertise (#7), Honest Confidence (#5), Verify-don't-guess, Proportional Effort
(#11).

## When a build plan ships in a different release than it targeted, its frontmatter `scope:` must be the scope-NAME (not a version) — `regen-views` resolves plans by it and a version there silently skips Status flipping at release

**Pattern**: v2.1.8 batch release (2026-06-22). The `hook-cli-robustness` branch was built
targeting v2.1.7, then batched into the v2.1.8 release alongside three other branches. Its
build-plan frontmatter read `scope: v2.1.7` (and five prose references said v2.1.7). The PR
reviewer flagged the version references as a single **cosmetic** Coherent-Artifacts WARNING
("authoring-time snapshot, may be waived"). Checking the convention — every sibling plan's
frontmatter `scope:` is the scope NAME (`test-evidence`, `gate-hardening`, …), matching its
change-log `scope=` tag — revealed that line 11 was not cosmetic: it is the field
`regen-views` uses (REL-4T8N) to resolve a change-log `scope=hook-cli-robustness` tag to its
build-plan file. With `scope: v2.1.7`, the release would have enumerated `scope=hook-cli-robustness`,
found no plan with that frontmatter, and left the plan's `## Status` checkboxes `[ ]` — a silent
miss, since regen-views skips (doesn't error on) an unresolved scope.

**The rule**: when a plan ships in a different release than it was authored for, audit the
frontmatter `scope:` and any version references. The `scope:` must equal the change-log `scope=`
tag (the scope name), never a version. Don't accept a reviewer's "cosmetic version string" framing
for the frontmatter line — verify it against the sibling-plan convention, because release-time
`## Status` regeneration is load-bearing on it. The prose version references ARE cosmetic; the
frontmatter `scope:` is not. Relates to Coherent Artifacts (#13), Validate Before Propagating (#15),
Independent Review (#14 — the reviewer surfaced it but mis-severitied it; the audit caught the real impact).

## When serially merging several stale feature branches into develop for one batched release, expect additive bookkeeping conflicts every time — and watch for a duplicate `active_build_plan:` key the auto-merge creates

**Pattern**: v2.1.8 batch release (2026-06-22). Four completed-but-stale feature branches
(12–21 commits behind develop) were merged into develop in sequence for one release. Observations:

- **Bookkeeping conflicts are additive and predictable.** Every single merge conflicted on
  `.prawduct/change-log.md`, `.prawduct/backlog.md`, `.prawduct/project-state.yaml`, and
  `CHANGELOG.md` — because each branch had appended a change-log entry at the file top, backlog
  items at the `## Open` head, a pointer-history comment, and (for branches carrying the
  `024bf53` v2.1.6-headline cherry-pick) a `## v2.1.7`-vs-empty CHANGELOG gap. The resolution is
  always a UNION: keep both sides' additions. For the change-log, place all release-pending
  entries above the prior `release=vX` boundary regardless of their header dates (worktree-compat
  was dated 2026-06-20 but still belongs above the 2026-06-21 v2.1.7 boundary entry) — the release
  checklist enumerates by boundary, not date.

- **The `active_build_plan:` duplicate-key trap.** worktree-compat set its pointer near the TOP of
  project-state.yaml (just under `base_branch:`) while develop carried the pointer in the canonical
  mid-file slot (set to hot-path by the previous merge). Two column-0 `active_build_plan:` keys on
  different lines do NOT textually conflict, so git auto-merged BOTH → a duplicate top-level YAML
  key. It is runtime-correct under the repo's first-wins line parser (`lib.core.read_str_yaml_key`)
  but a PyYAML reader would last-wins to the WRONG plan, silently disabling that scope's gates. The
  cumulative Critic caught it as a Goal-4 coherence WARNING. Fix: collapse to one canonical key.

- **Critic records don't survive re-sync.** Each branch's prior-session cumulative Critic findings
  were gone (single-slot `.critic-findings.json`, gitignored), and re-syncing develop changed HEAD
  anyway — so a fresh `cumulative` per branch after the sync was unavoidable (verify-resolutions
  only extends a record that already covers the merge-base..pre-fix range). A forked Critic that
  dies mid-run (connection-closed) leaves `.critic-active` set with no findings written; clear it
  with `prawduct-hook critic-end` before re-invoking.

**The rule**: batch-merging stale branches → resolve bookkeeping by union (release-boundary order
for the change-log), explicitly check for a duplicated `active_build_plan:` key, and run a fresh
cumulative Critic on each branch AFTER syncing develop in. Relates to Coherent Artifacts (#13),
Independent Review (#14), Validate Before Propagating (#15).

## When a session switches branches after SessionStart, pass the Critic mode explicitly — `infer-critic-mode` trusts the stale session-start branch marker

**Pattern**: hot-path-git-batching / STH-6Q9D (2026-06-21). The session started on
`feature/hook-cli-robustness` (a merge-ready branch the user deferred), then the
work moved to a fresh `feature/hot-path-git-batching` off develop. At chunk close I
ran `/prawduct:critic` with no args. It inferred `verify-resolutions` and chained to
the *prior* session's anchors `f208ad2`/`f92a4be` — which live on the SIBLING
hook-cli-robustness branch and are not ancestors of HEAD. The mode-inference read the
branch captured at SessionStart, not the current one.

**Why the guard missed it**: `compute-verify-resolutions-scope` demotes a chain only
when the anchor `commit_reviewed` SHA does not *resolve*. A sibling-branch SHA still
resolves in the shared object store — it's simply not an ancestor of HEAD — so the
demote-guard passed it and the review computed an `anchor..HEAD` two-way diff that
spanned the divergence point. That surfaced the sibling branch's `git_path_is_ignored`
deletion and a `BLD-4K7P` carveout removal as if THIS work removed shipped behavior;
both were absent at the develop merge-base and untouched by the real commit. The Critic
self-flagged the phantoms and recommended `cumulative` on this branch, which I then ran
(clean: 0/0/4), followed by a chain-extending `verify-resolutions` (0/0/0).

**The rule**: after any mid-session branch switch, the session-start git markers
(branch, baseline) are stale for governance inference — pass the Critic mode
explicitly and anchor on the current branch. The deeper fix is filed as CRT-8H3R: add
a `git merge-base --is-ancestor <anchor> HEAD` check to the demote-guard so a
non-ancestor anchor demotes to `cumulative`/`final` instead of computing a divergent
delta. Note this is distinct from CRT-6J4P (anchor is a valid ancestor, just from a
prior bundle — surprise, not unsoundness); CRT-8H3R is the actual soundness bug.

---

## When verifying a framework-repo `lib/`/`bin/` change by running the hook, invoke the repo-local `python3 bin/prawduct-hook` — the bare `prawduct-hook` on PATH is the installed plugin cache, not your working tree

Surfaced 2026-06-22 during TEL-4M9X (review-stats model-id normalization). After landing the `_canonical_model` fold in `lib/telemetry.py` and confirming the unit tests passed, I ran `prawduct-hook review-stats` against the real ledger to watch the opus buckets collapse — and they didn't: the output still showed `opus` / `claude-opus-4-8` / `claude-opus-4-8[1m]` as three separate buckets, exactly as before the fix. Momentary "did the change not take?" The root cause: `command -v prawduct-hook` resolved to `~/.claude/plugins/cache/prawduct/prawduct/2.1.7/bin/prawduct-hook` — the installed plugin, pinned to the released v2.1.7 and importing *that release's* `lib/telemetry.py`, which has no `_canonical_model`. Re-running `python3 bin/prawduct-hook review-stats` from the repo root (which imports the working-tree `lib/`) showed the correct collapse — the 14-review cumulative bucket, with `fable` kept distinct. The unit tests never caught a problem because `tests/test_review_stats.py` invokes the hook via `ROOT / "bin" / "prawduct-hook"` — i.e. the repo-local copy — so the suite always exercised the new code. Fix-shape: when behaviorally verifying a framework `lib/`/`bin/` change, invoke the repo-local `python3 bin/prawduct-hook <cmd>`; treat the bare on-PATH command as *released* behavior that lags your edits until the plugin is re-released and re-cached. The diagnostic contradiction to watch for — green tests but unchanged PATH-command output — is itself the signal you're hitting the cached plugin, not your working tree. Relates to Honest Confidence (#5 — don't report a fix as broken on stale evidence), Validate Before Propagating (#15), and Reasoned Decisions (#4).

---

## When prose picks which model a reviewer/subagent runs on, express it as an ordered fallback chain resolved at dispatch — never a pinned alias

**Pattern**: reviewer-model-fallback (2026-06-12). Reviewer dispatch pinned `model: fable` (escalate) / `model: opus` (standard) as literals in three skill-prose surfaces. Fable was temporarily withdrawn; the pin would break escalate-tier review — or worse, silently run it on the *session* model, because Claude Code resolves a blocked/unavailable subagent `model:` override to the inherited/default model rather than erroring (verified via `claude-code-guide`, code.claude.com/docs — not recall).

**Fix**: ordered tier chains + a withdrawn-model resolution rule across all three surfaces (`escalate` fable→opus, `standard` opus→sonnet): "use the first the harness lists as valid; fall back on a withdrawn/unrecognized model or dispatch error; record what ran." Per-call and frontmatter `model:` take a single value (no fallback syntax), so resolution is prose-driven by the runtime dispatching agent — the only actor that can see the live valid-model set (a Python hook can't, so an automated availability probe isn't feasible; the heavier registry+drift-check option is deferred as REL-5K8M).

**Two reusable sub-lessons**: (1) a token-budget guardrail at its ceiling forces trim-vs-bump on any necessary addition — remove genuine redundancy (cross-file duplicate comments, self-restating clauses), don't bump the budget or drop a check; the guardrail correctly makes new content pay for itself. (2) Verifying harness/model behavior beats recalling it: the silent-substitution-to-session-model detail (which I would not have recalled correctly) is exactly what turned the rule from "pass fable and hope" into "pick a confirmed-valid model, then fall back explicitly."

## A clean cumulative (0 blocking/0 warning) makes post-review note-fixes asymmetric — `.md` fixes ride free, any `.py` change forces a fresh full review

**Pattern**: upstream-bug-reporting (2026-06-20). A cumulative Critic over the bundle came back 0 blocking / 0 warning / 5 notes. Some notes were `.py` (a misleading docstring, a speculative dead-code guard), some `.md` (slim-digest framing); fixing them meant a follow-up commit. Because the follow-up touched `lib/upstream_probes.py` (non-`.md`), the prior cumulative no longer vouched for HEAD, so the PR gate (`check-cumulative-critic`) needed a fresh HEAD-covering record — a full re-review. Had the fixes been `.md`-only, the CRT-7M2D docs-only allowance would have kept the original cumulative HEAD-covering and cost nothing.

**Why the re-review is full, not light**: the cheap post-fix path (`verify-resolutions`, Goals 1-3 over the delta) *demotes to `final`* precisely when prior findings hold no BLOCKING/WARNING — there's nothing to "verify resolved," so it falls back to a full pass. So an all-NOTE cumulative gives no cheap re-review path for a `.py` touch.

**Reusable rule**: self-scrub hard BEFORE the first cumulative (the methodology's "deep-scrub while the Critic runs" only helps if there's a gap to use; a synchronous skill return leaves none — so scrub before invoking). When notes land: fix `.md` notes in place (free), and weigh each `.py` cosmetic note against one opus re-run — fixing a false docstring + dropping dead code was worth it here, but a pure tense-nit was not (left as a defensible description). Route low-value `.py` notes to a backlog item rather than re-reviewing. Ties directly to the Review-wall-clock-is-P0 priority.

## Artifacts drift silently during sustained building

**Pattern**: Discodon built 40+ chunks over multiple sessions. Artifacts written during planning (test-specifications, architecture, data-model) were never updated. Test-specifications says "1056 tests" when the actual count is 1318+. Coverage matrix is missing 15+ test files. Architecture may not reflect scheduling, tool framework, or prompt architecture features.

**Root cause**: Build cycle step 8 said "Update state" (meaning project-state.yaml) but didn't mention updating artifacts. The Critic's Coherence check verified code→artifact direction (does code implement the spec?) but not artifact→code direction (does the spec still describe the code?). No structural prompt to update artifacts as the code evolved.

**Resolution**: (1) Updated build cycle step 8 to explicitly include artifact updates. (2) Added bidirectional artifact freshness check to Critic's Coherence check. (3) This is Principle 3 (Living Documentation) applied to specifications — the same principle that prevents documentation fiction also applies to specs that become planning fiction.

**Principle**: Relates to Living Documentation (#3), Coherent Artifacts (#13).

## Structural gates must match natural workflow

**Pattern**: The stop hook checked for `artifacts/build-plan.md` to trigger the Critic gate. The methodology said to put the build plan there. But the natural workflow for discodon put the build plan in `project-state.yaml` (alongside status tracking). Result: the Critic structural gate never fired for 40+ build sessions. The Critic was invoked purely through behavioral compliance (Claude following CLAUDE.md instructions).

**Root cause**: When there are two reasonable places for something and the gate only checks one, the gate becomes optional. This is especially ironic given the v2 learning that "judgment alone won't interrupt momentum" — the gate existed to catch judgment failures but was watching the wrong door.

**Resolution**: Updated the hook to check both `artifacts/build-plan.md` and `project-state.yaml` for build plan content. Updated methodology to acknowledge both locations.

**Principle**: Relates to Governance Is Structural (#22) — structural gates must match how people actually work.

## Growing files need structural nudges to prune

**Pattern**: Discodon's learnings.md grew to 42KB (430 lines, ~12,000 tokens) despite guidance saying "keep under ~3,000 tokens." Each session added detailed technical learnings. No session pruned. The guidance to prune was present but never triggered behavior change — exactly the pattern from "filed-away observations don't change behavior."

**Resolution**: Originally a clear-hook size warning at 8KB (2026-Q1). Superseded when learnings moved to the `/learnings` skill (`context: fork`, filters to ~500 tokens) — the skill makes large knowledge files cheap to consult, so the size threshold no longer earns its complexity. The surviving mechanical-check pattern is the `project-state.yaml > 40KB` warning, which serves the same role for a file that is still loaded directly. The nudge returned 2026-06-10 (MET-6W3J) at the 40KB project-state threshold — at ~80KB the per-lookup cost of the fork-skill read became the problem the threshold now guards.

**Principle**: Relates to Close the Learning Loop (#18). The general rule (size targets need mechanical checks) still holds; the specific case got obsolesced by a better load mechanism.

---

## Init leaves CLAUDE.md unmerged when onboarding existing repos (RESOLVED)

**Pattern**: `prawduct-init.py`'s `write_template` skips existing files to avoid overwriting user edits. When onboarding an existing repo that already has a CLAUDE.md, init created all other Prawduct files but left CLAUDE.md untouched — no framework block markers, no Prawduct content.

**Resolution**: Added three-way CLAUDE.md handling in `run_init()`: new file → write template; existing without markers → prepend framework template, preserving user content below END marker; existing with markers → skip (sync handles). The merge action is reported in output. Manifest hash is correctly computed from the merged result.

**Principle**: Relates to Complete Delivery (#2) and Honest Confidence (#5).

## Mock scripts break with embedded newlines in f-strings

**Pattern**: The test mock git script is built via an f-string with `textwrap.dedent`. When `git_output` contains literal newlines (e.g., `" M file.py\n"`), the newline breaks `textwrap.dedent` — the injected line has no leading whitespace, so dedent finds no common prefix and leaves the shebang indented, making the script non-functional.

**Lesson**: When building mock scripts via f-string interpolation, avoid injecting values that contain newlines into the template. Test the mock's boundaries, not just the logic it simulates. Single-line mock outputs test the same comparison logic without fighting the test harness.

**Principle**: Relates to Tests Are Contracts (#1) — tests should be robust to incidental complexity.

## Shared modules via importlib work well for hyphenated Python scripts

**Pattern**: The sync/init/migrate scripts need to share helpers (`compute_hash`, `render_template`, `merge_settings`, `create_manifest`) but have hyphenated filenames that prevent normal Python imports. Using `importlib.util.spec_from_file_location` for cross-script imports works cleanly — already used in test files, now used in production code too.

**Lesson**: When multiple scripts need shared logic, extract it to one canonical module and import via importlib rather than duplicating. This prevented three copies of `merge_settings` from drifting apart. The pattern is: one module owns the function, others import it.

**Principle**: Relates to Coherent Artifacts (#13) — one source of truth for shared logic.

## Judgment alone won't interrupt momentum

**Pattern**: The v2 experiment replaced structural Critic gates with principles saying "invoke the Critic after each chunk." In the first real product build (Hum, chunk 1), Claude didn't read `methodology/building.md`, never invoked the Critic, and self-declared the chunk complete with 15 findings that any independent review would have caught. Discovery and planning methodology guides were read correctly — building was skipped because "start coding" doesn't naturally trigger "read the process guide first."

**Lesson**: There's an asymmetry between behaviors Claude will self-regulate and behaviors it won't. Claude follows principles about *how* to do work (test quality, scope discipline, spec fidelity). It does *not* self-impose process interruptions that halt momentum (invoke a reviewer, pause to read methodology). The first category can be governed by principles. The second needs structural gates. The minimum structural enforcement is: force independent review before declaring work complete.

**Principle**: Relates to Governance Is Structural (#22) and Independent Review (#14).

## Products must be self-contained for parallel agent work

**Pattern**: The v1 system required `framework-path` pointing to a local clone, runtime hook resolution, and shared session state files (`.session-governance.json`, `.active-products/`). This made it impossible for multiple agents to work on different products simultaneously — shared mutable state created race conditions and clobbering.

**Lesson**: Product repos must carry everything they need: their own CLAUDE.md with principles, their own hooks, their own Critic instructions. No runtime dependency on a framework clone. No shared state between agents. The framework is a *generator* that produces self-contained product repos, not a *runtime* that products depend on. This is also the distribution story — if products are self-contained, they work anywhere Claude Code runs.

**Principle**: Relates to Clean Deployment (#10) and structural independence.

## Reactive systems can't detect missing things

**Pattern**: The learning pipeline (observations, Critic, reviews) validates quality of what exists but cannot identify what should exist and doesn't. Critical gaps (missing cross-cutting concerns, missing artifact categories) went undetected across 13+ evaluations and 6+ sessions until an external audit surfaced them.

**Lesson**: Correctness validation ("does this work?") and completeness auditing ("is this everything?") are fundamentally different capabilities. You need both. Periodically step back and ask "what should exist here that doesn't?" — not just "is what exists correct?"

**Principle**: Relates to Automatic Reflection (#17) — reflection must include completeness, not just correctness.

## Governance complexity breeds governance complexity

**Pattern**: Each failure spawned a separate fix. After 11 independent additions, hooks alone were 1,079 lines — exceeding the skill files they protected. Triple-redundant debt detection, uniform 11-step processes regardless of impact. Root cause: reactive additions without coverage auditing.

**Lesson**: Before adding any new enforcement mechanism, ask: "Is this failure already covered by something that exists? Am I adding defense-in-depth where defense-in-one suffices?" Impact-scaled processes (lightweight for small changes, heavy for structural ones) reduce the temptation to make everything heavyweight.

**Principle**: Relates to Proportional Effort (#11) — governance itself must be proportional.

## Independent review catches what self-review misses

**Pattern**: Moving the Critic from in-context (same LLM reviews its own work) to a separate agent improved review quality measurably. The independent agent caught 2 surviving reference errors that in-context review missed, on its very first invocation.

**Lesson**: Independence is a feature for review functions. The reviewer should NOT see the builder's conversation context — that's what creates blind spots. Invoke the Critic as a separate agent via the Task tool. This likely applies to any review function.

**Principle**: Relates to Independent Review (#14).

## Principles need runtime enforcement, not just change-time checks

**Pattern**: "Generality Over Enumeration" was checked when modifying framework files but not when evaluating incoming user guidance. Result: the framework accepted a 285-line technology-specific design that violated the principle, because the principle wasn't applied at runtime.

**Lesson**: Principles apply to decisions as they happen, not just during retrospective review. When receiving guidance or making decisions, actively check: does this violate a principle? Especially watch for: technology specificity, structural assumptions, scope creep, and instance-specific solutions where general ones exist.

**Principle**: Relates to Governance Is Structural (#22) — governance applies continuously, not at checkpoints.

## Filed-away observations don't change behavior

**Pattern**: The YAML observation system captured detailed findings with severity, RCA categories, and status tracking. But observations accumulated without systematically influencing future decisions. The learning loop was write-only — observations were filed but nothing read them before making new decisions.

**Lesson**: Learnings must live where they're read, not where they're filed. This file exists because YAML archives don't change behavior. Keep learnings here, in natural language, where they're loaded at session start and directly influence decisions. When a learning has been incorporated into a principle or methodology update, it can be condensed here.

**Principle**: Relates to Close the Learning Loop (#18).

## Phase-based implementation enables independent testing and rollback

**Pattern**: Large changes (17+ files) that follow phased plans (infrastructure → validation → consumption → documentation) succeed more reliably than monolithic changes. Each phase preserves system functionality and enables confidence to build incrementally.

**Lesson**: For significant changes, plan phases so each one is independently testable and the system remains functional at every boundary. The opposite pattern — monolithic changes with deferred integration — creates fragility and makes rollback difficult.

**Principle**: Relates to Validate Before Propagating (#15).

## Denormalized state drifts without mechanical validation

**Pattern**: Parallel artifact generation by 5 agents produced 12 inconsistencies in denormalized inverse-dependency fields. Each agent independently estimated the field without cross-agent validation.

**Lesson**: Either compute derived data on demand from the source of truth, or mechanically validate it after writes. Never trust denormalized caches maintained by independent actors. This applies to any computed or derived field in any artifact.

**Principle**: Relates to Coherent Artifacts (#13).

## Coherence cascades require checking summaries, not just primary locations

**Pattern**: When adding `prior_art` to discovery, the primary section and template were updated correctly. But two summary lines elsewhere ("What Discovery Produces" in discovery.md and the condensed discovery paragraph in product-claude.md) listed what classification contains without mentioning prior art. Similarly, only one of four test scenarios received the new rubric criterion. The Critic caught all three gaps.

**Lesson**: When adding a concept to a system, search for every place that *summarizes* or *enumerates* what the system contains. Summaries are a form of denormalized state — they drift when the source of truth changes. After making a primary change, grep for summary phrases ("produces", "contains", "includes") that might need updating. Also check *scope declarations* — section comments that say "only for X" may contradict a universally-applicable new field. And check test scenarios — if sibling concepts have rubric criteria, the new concept needs one too.

**Reinforcement (2026-02-22)**: Fell into this exact pattern again when adding `error_handling_approach` under a "UI only" section comment and omitting test scenario rubric coverage. The learning was already captured; reading it wasn't enough to prevent the miss. The scope-declaration variant (section comments) and the test-scenario variant are now explicitly called out above.

**Principle**: Relates to Coherent Artifacts (#13) and Living Documentation (#3).

## Escape hatches in classification create silent failures

**Pattern**: Gate classified files as framework/product/ungoverned with ungoverned defaulting to auto-allow. An entire product was built without governance because unregistered repos fell into the "ungoverned" escape hatch.

**Lesson**: When classifying inputs, the "unknown" category should default to "suspicious/blocked", not "allowed." Fail-closed is almost always safer than fail-open. This applies broadly: any classification with an "other" bucket that auto-allows is a potential escape hatch.

**Principle**: Relates to Governance Is Structural (#22).

---

<!-- Narratives moved from learnings.md 2026-06-10 (MET-6W3J compaction) -->

## A new build plan with `scope: null` and low chunk numbers inherits another scope's shipped checkbox flips — set `scope:` from the start

When creating a build plan, set the frontmatter `scope:` to a unique slug immediately (matching the change-log entry's `scope=` tag) — do NOT leave it `scope: null`. With `views_enabled: true`, `regen-views` derives each plan's `## Status` checkboxes from `status=shipped` change-log entries; `collect_shipped_chunks` filters by the plan's detected scope, but a `scope: null` plan falls into "legacy unfiltered" mode where EVERY shipped entry contributes its chunk IDs. So a brand-new single-chunk plan whose chunk is "Chunk 1" gets flipped to `[x]` by an unrelated shipped entry like `chunks=1,2,3 | status=shipped | scope=work-model` — a spurious "shipped" on work that's only on a feature branch. (Discovered building CRT-3X9D: my `scope: null` plan's Chunk 1 flipped from the work-model v2.0.13 entry.) The build-plan template's `scope:` comment warns about this, but the warning lives in a template comment that from-scratch plan authors don't see, so it keeps recurring. Fix-shape: every build plan declares a unique `scope:` slug up front; verify with `regen-views --check` after adding the change-log entry (a statusless branch entry must leave the chunk `[ ]`). Discovered CRT-3X9D (2026-06-07, branch). Relates to Coherent Artifacts (#13), [[new change-log entries on a feature branch are statusless]] (the sibling regen-views trap), and Validate Before Propagating (#15).

## New change-log entries on a feature branch are statusless — `status=in-progress` is deprecated and trips the regen-views typo-guard

When adding a `.prawduct/change-log.md` entry for work on a feature branch (before it reaches develop), leave the `status=` tag OFF entirely — do NOT use `status=in-progress`. `lib/views.py` recognizes only `{shipped, merged}` (`VALID_STATUS_VALUES`), and `warn_unrecognized_status_tags` flags any *present-but-unrecognized* `status=` as "Likely a typo" on every `regen-views` run; `in-progress` is a deprecated legacy value (`docs/release-process.md` "Change-log `status=` values" documents the current model). The documented lifecycle (updated by single-pr-bookkeeping, 2026-07-10): the entry stays **statusless** through the feature→develop merge — a statusless tagged entry IS the release-pending state, and the old post-merge `status=merged` stamp step was retired because it required a commit on the integration branch, forcing protected-branch consumers into bookkeeping-only PRs (`merged` in older logs is an accepted legacy synonym, treated as statusless). Flip to `status=shipped` + `release=vX.Y.Z` at the develop→main release (gitflow), or write `status=shipped` (+ `release=` when the product versions) in the closing PR when its base is the release surface (trunk). A statusless entry triggers no warning (the guard only fires when `status=` is *present*) and flips no checkbox (that needs `status=shipped` + `chunks=`), which is exactly correct for branch-state and release-pending work. The work-model entry (v2.0.13, the immediately prior session) used `status=in-progress` on its branch and it slipped through only because `regen-views` wasn't run during that window — REL-8K3M's cumulative Critic caught the same value as a WARNING. Fix-shape: branch entries carry only `type=`/`scope=`; statuses change only inside a PR (release-prep or a trunk closing PR), never as a post-merge commit. Discovered REL-8K3M (2026-06-06, develop). Relates to Coherent Artifacts (#13), Escape hatches create silent failures (#22), Honest Confidence (#5), and Living Documentation (#3).

## A change-log `chunks=` tag must match the build plan's chunk-heading numbering *exactly* (zero-padding included) or `regen-views` flips only the matching chunks

When tagging a multi-chunk change-log entry, the `chunks=` list must use the **same numbering format** as the plan's `## Status` headings — if the plan reads `Chunk 01 … Chunk 10`, the tag must be `chunks=01,02,…,10`, not `chunks=1,2,…,10`. `lib/views.py`'s `regenerate_status_section` matches chunk IDs as **literal strings** (`CHUNK_LINE_RE` captures `01` from `Chunk 01:`), so `chunks=1` does not match `Chunk 01` — and the failure is *partial and silent*: at v2.0.15 release-prep, `chunks=1,2,…,10` against `Chunk 01..10` headings flipped **only chunk 10** (the one token that happened to match), leaving 01–09 stuck `[ ]` with no error. The tell is `regen-views`' own output — `"1 chunk(s) flipped — shipped [10]"` when you expected 10. The work-model release (v2.0.13) dodged this by using single-digit `Chunk 1/2/3` headings to match `chunks=1,2,3` (noted inline in its prep commit), but a plan written with zero-padded headings needs zero-padded tags. Fix-shape: after `regen-views` at release, read its flipped-count and confirm it equals the chunk count; if fewer flipped, the `chunks=` numbering doesn't match the headings — align the tag to the headings (don't renumber the plan). Discovered v2.0.15 backlog-rework release (2026-06-08, release). Relates to Coherent Artifacts (#13), Validate Before Propagating (#15), and [[At release, flip statusless unreleased change-log entries]].

## When a feature's logic lives in a `context:fork` skill (no Bash), `lib/` holds the DATA, not the LOGIC — logic helpers nothing imports are dead code

A `context:fork` skill (e.g. `/prawduct:backlog`, `allowed-tools: Read, Edit, Write, Grep, Glob` — no Bash) is LLM-interpreted prose: it cannot import or call a `lib/` module. So its filtering/routing/dedup/ranking *logic* is the agent reasoning over the file it reads — there is no Python call site. The runtime (`bin/prawduct-hook` and the hooks it runs) is the only consumer of `lib/`. Consequence: when planning such a feature, `lib/` should carry the **data layer** (a parser + pure query accessors — like `lib/backlog.py` mirroring `lib/views.py`) that the *runtime* needs (briefing counts, probes), and the **logic** belongs in the skill prose. A planned `lib/` "logic helper" the skill would supposedly use (`is_implementable`, a dedup-candidate scorer, an archive-split function) is **dead code** — nothing imports it — and the Critic flags it (Goal 7) or it sits untested-by-a-real-consumer. The backlog-rework plan listed four such helpers; each was correctly descoped, but the descope must be **recorded** (Principle 2) — the Critic flagged the first one left silent (ch.03). Fix-shape: when a plan assigns logic to a fork-skill feature, put data in `lib/` (+ tests) and logic in the SKILL.md; if a plan line says "add `lib/` helper X for the skill," ask "does any *Python* path call X?" — if no, it's skill prose, descope the helper and record it. Discovered backlog-rework v0.3 (2026-06-08, branch). Relates to The Design Is Sound (#7 — no dead code), Complete Delivery (#2 — record descopes), Scope Discipline (#12), and [[fine-grained tool restriction needs a fork-skill, not a named subagent]].

## At release, flip *statusless* unreleased change-log entries to `status=shipped` too — not just `status=merged`

`docs/release-process.md` step 3 says to flip entries "from `status=merged` to `status=shipped`," but in practice most unreleased entries reach release-prep **statusless**, not `status=merged`. The documented two-state lifecycle (add `status=merged` at the feature→develop merge — see [[new change-log entries on a feature branch are statusless]]) is manual, and the `/prawduct:pr` merge flow does NOT apply it, so a branch entry stays statusless from branch through develop into release-prep. A release author who follows step 3 literally flips only the `status=merged` entries and **silently drops every statusless one** — and because `regen-views` acts only on entries with `status ∈ {shipped, merged}`, a dropped statusless entry's build-plan `## Status` checkboxes never flip, and it never appears in `release-notes.md` or `scope_rollups`. The omission is invisible (no warning — a statusless entry trips no typo-guard), so the release ships looking complete while quietly missing scopes. At v2.0.14 (batched: hook-decomp ch.1–7 + critic-session-guard) **8 of 10** unreleased entries were statusless; only the two bugfixes carried `status=merged`. Fix-shape: at release-prep, enumerate ALL change-log entries above the prior `release=vX` boundary and flip each (statusless OR `status=merged`) to `status=shipped` + `release=vX.Y.Z`; then run `regen-views` and confirm with `regen-views --check` that every shipped scope's plan flipped to `[x]` and appears in `scope_rollups`. Deeper fix is filed ([[backlog]] REL-2N8K): either make the feature→develop merge reliably set `status=merged`, or reword release-process.md step 3 to say "statusless or `status=merged`." Discovered v2.0.14 release (2026-06-08, release). Relates to Complete Delivery (#2), Living Documentation (#3), [[new change-log entries on a feature branch are statusless]], and Validate Before Propagating (#15).

## "I'm just codifying their guidance" is not an exemption from the research trigger — and volatility is a separate axis from knowledge-confidence

When you're about to design or place something and tell yourself "I'm only writing down what the user already specified, so no research needed," check whether the *design or placement* (not the content) lives in a fast-moving domain — that's a separate, easily-missed trigger. In rigor-and-stance (2026-06-04) I judged "no web research — internal codification of owner guidance," but the work was *designing agent methodology and choosing a Claude Code placement*, both in a space that ships changes weekly, well past my training cutoff. The owner caught it; two research passes then materially improved the design AND corrected the requirements model we were building. Root cause: I conflated owner-specified *content* (the stances — genuinely no research) with the *design/placement* (volatile — needed it). The durable distinction, now encoded in `methodology/discovery.md` "Calibrate Rigor": rigor has TWO independent research axes — **knowledge-confidence** ("do I know enough to design this well?" → reason/decompose) and **volatility/recency** ("does correctness depend on timely / post-cutoff / fast-moving data?" → web research). My miss was a pure volatility miss *with* high knowledge-confidence — direct proof the axes are distinct, which is why the model splits them. Fix-shape: before declaring "no research needed," run the self-check "does this depend on the current state of the world, or a field moving faster than my training cycle?" against the DESIGN and its INPUTS, not just the stated requirements — "I'm just codifying" is the phrase that suppresses exactly this check. Discovered rigor-and-stance (2026-06-04, develop). Relates to Honest Confidence (#5), Bring Expertise (#7), Validate Before Propagating (#15).

## The "canonical" mechanism for a capability can be disqualified by a plugin's composability + always-on constraints — verify the constraint before adopting the recommendation

When research or docs name a "first-class / canonical" mechanism for a capability, verify it against the consumer's *structural* constraints before adopting it — a governance plugin needs its behavior always-on AND non-clobbering of a consumer's own config, and that can disqualify the otherwise-correct canonical choice. In rigor-and-stance (2026-06-04) the research recommended Claude Code **Output Styles** as the first-class home for agent personality/stance (true in general — system-prompt-level, prompt-cached, discoverable via `/config`). A verification pass confirmed `force-for-plugin: true` HARD-OVERRIDES (clobbers) a consumer's own selected output style and does not compose — disqualifying for a plugin whose governance must be unconditional AND must not trample a consumer's setup. The always-on SessionStart digest is both unconditional and composable (additive context, orthogonal to the user's chosen style), so the stance stayed there — the original instinct, now correct for a *verified* reason instead of inertia. Sibling of "verify the platform's copy/packaging boundary before duplicating": a generic best-practice loses to a verified structural constraint; confirm the constraint (single active slot? clobbers? composes?) before taking the rec. Platform fact for future Claude Code work: an output style's `force-for-plugin` overrides the user's `outputStyle` (one active style at a time, no merge). Discovered rigor-and-stance (2026-06-04, develop). Relates to Validate Before Propagating (#15), Reasoned Decisions (#4), Visible Costs (#9).

## When a fan-out render keys on a field that isn't unique, test the collision case — and a self-authored adversarial pass inherits the author's blind spots

When a renderer (or any fan-out) groups/sub-sections by a field, the field's NON-uniqueness is the bug to test for. REL-4T8N-B (release-tooling, 2026-06-04) rendered `release-notes.md` as one `### ` sub-section per change-log ENTRY within a release — correct for distinct scopes (v2.0.5's four), but a single scope split across two change-log entries (v1.4.0's two `scope=v1.4` entries) produced two identical `### v1.4` headings, *worse* than the old collapse. My own new tests covered distinct-scope and no-scope multi-entry but NOT same-scope-multi-entry; the parallel adversarial-verification workflow I launched ALSO missed it — because I wrote its edge-case list, so it inherited my framing. The independent cumulative Critic caught it by reasoning from the actual committed `release-notes.md` artifact (it diffed the real file), not from my fixtures. Fix-shape: (1) when a fan-out keys on a field, add an explicit test for the field-COLLISION case (≥2 inputs sharing the key) — the correct model was "group by the key first" (`_group_release_entries_by_scope` merges same-scope, splits distinct); (2) a self-authored adversary only escapes the author's blind spots to the extent its prompt does — the durable catch is the *independent* reviewer working from real artifacts, not a skeptic whose checklist you wrote. Discovered release-tooling REL-4T8N-B (2026-06-04, develop). Relates to Independent Review (#14), Tests Are Contracts (#1), and Validate Before Propagating (#15).

## When fanning out a batch build to parallel worktree-isolated workflow agents, partition by disjoint file ownership (integrator owns shared files) and force-clean leftover worktrees before the integration suite

A workflow that builds N backlog items in parallel via `isolation: worktree` subagents integrates cleanly IFF the work is partitioned so each agent OWNS a disjoint file-set and any file that MULTIPLE chunks would touch is reserved for the integrator. In cleanup-batch (6 chunks, 2026-06-04) the one shared file was `tests/test_v5_methodology.py` (token-budget assertions for both `methodology/building.md` and the critic `review-protocol.md`); keeping it OFF the two doc agents — they only *reported* budget overruns in their structured result, the integrator did the bump — meant all six `git diff --cached` patches applied to the main tree with zero conflicts (`git apply --check` clean on all 6). Two operational gotchas: (1) worktree-isolated agents' worktrees do NOT auto-remove when they have changes, and this repo's structural tests (`test_test_location`, `test_plugin_methodology_digest`) scan the whole tree — so leftover `.claude/worktrees/wf_*/` copies fail the suite with "not one canonical copy" / "test files outside tests/". `git worktree unlock && remove -f && prune` them BEFORE the integration full-suite run (filed a backlog item to make those tests ignore `.claude/worktrees/`). (2) Governance stays in the main session: agents BUILD and self-verify only their targeted test module (`-n0`); the integrator runs the FULL suite, reconciles shared-file budgets, records test-evidence, and runs the cumulative Critic. The Critic's only findings were integration-bookkeeping (stale evidence, a chunk-ref-parser false positive), never code — confirming the agents-build / main-session-governs split holds at fan-out. Discovered cleanup-batch (2026-06-04, develop). Relates to Independent Review (#14), Scope Discipline (#12), and Proportional Effort (#11).

## When a fresh-eyes review's advice about a CONVENTION conflicts with a durable learning + the process doc, the documented convention wins — re-verify before acting

When a forked Critic / PR reviewer makes a claim about *how this project does bookkeeping* (release timing, status semantics, "X is consistent with the flow"), treat it as a reading of the CURRENT tree, not as institutional authority — the reviewer has not read `learnings.md` or `docs/release-process.md` and only sees the artifacts in front of it. In the roi-batch session the cumulative Critic noted "no change-log entry yet is consistent with this project's release flow (added at release time)" — empirically true of the recent *plan-IS-the-release* cases (every prior entry was `status=shipped`, added in the `chore(release)` commit), so it over-generalized. I over-weighted it (plus the runbook's own `status=shipped` error) and first DEFERRED the change-log entirely + CLEARED `active_build_plan` — the opposite of the documented convention. The source of truth (`docs/release-process.md` + `learnings.md` "KEEP the build plan" + the build plan's own `scope=` comment) prescribes Model A for a batched sub-release merged ahead of its `develop→main` release: add a `status=merged` change-log entry (tagged `scope=`, `chunks=`), KEEP `active_build_plan` until the release, then the release flips `merged→shipped` + runs `regen-views` + clears the pointer. Fix-shape: when a review's convention-claim or a pre-`/clear` runbook's bookkeeping step diverges from a durable learning, RE-READ the learning + process doc and follow them; a reviewer's tree-level observation does not override documented institutional memory. Discovered roi-batch (2026-06-03, develop). Relates to Validate Before Propagating (#15), Independent Review (#14), and Close the Learning Loop (#18).

## A reviewer's NOTE/severity is a prior, not a verdict — re-scope any "harmless" change that touches a governance-gate input

When an independent review rates a change low-severity ("harmless dead allowlist entries"), treat the label as a starting prior, not a conclusion — especially when the change touches an *input to a governance gate*. The develop→main v2.0.3 release review NOTE-rated removing `.claude/skills/` and `tools/product-hook` from `_METADATA_PREFIXES` (the allowlist `_is_metadata_path` consults to decide whether a changed file trips the Critic/reflection gates). Tracing the call sites showed it was not purely dead: `tools/product-hook` removal is inert in a plugin repo (the file never exists), but removing `.claude/skills/` is a real behavior change — a product's *own* skill under `.claude/skills/` had been classified as excused framework metadata and silently skipped the gates, so the removal closes a governance hole. A behavior change to a gate input is a contract change and gets a test (`TestMetadataPathClassification` pins both the classifier and the end-to-end inference flip from rule-4 to "no build plan medium+"). Fix-shape: for any edit to a gate's input set (allowlists, prefix tables, fileset bounds), enumerate the predicate's consumers (`grep` its call sites), decide whether behavior actually changes, and add/adjust a test when it does — don't let a low-severity label substitute for tracing the blast radius. Discovered v2.0.3 develop→main promotion (folding `[JAN-4F7M]`). Relates to Tests Are Contracts (#1), Root Cause Discipline (#16), Independent Review (#14), and Honest Confidence (#5).

## A new framework-wide DEFAULT must land in the session digest — place-once preferences and the thin anchor don't reach migrated repos

When changing a framework-level *default behavior* that every product (any vintage) should pick up, the carrier must be `methodology/session-digest.md` — the only surface injected into every product session unconditionally (`hooks/digest.py`, all SessionStart matchers). The intuitive homes don't propagate to existing repos: `templates/project-preferences.md` is **place-once** (created once at init, never regenerated when the template changes — see "Framework ownership follows the write strategy"), and a migrated repo's `CLAUDE.md` is only the thin static anchor (`migrate_plugin.STATIC_ANCHOR`, deliberately minimal/version-free), so neither carries a default added after the repo was set up. Concretely (v2.0.0, "default to no commit attribution trailers"): the rule went in the digest (reaches all vintages) + the project-preferences template (documents the opt-in for *new* products) — and was deliberately NOT added to the every-session `product-claude.md` PRAWDUCT block, which is token-budget-bound (`test_token_budget`, 3050) and was already at ceiling; duplicating it there would have bought nothing the digest doesn't already deliver, at a permanent per-session token cost. Fix-shape: for a new default, ask "which surface does an *already-onboarded* repo actually re-read?" → the digest, not its frozen place-once files. Relates to Coherent Artifacts (#13), Visible Costs (#9), and Proportional Effort (#11).

## Single-repo plugin+marketplace: the marketplace entry's plugin `source` must be `"./"`, not `{source:github,ref}`

When a plugin and its `.claude-plugin/marketplace.json` live in the SAME repo (prawduct's topology), the marketplace entry's plugin `source` must be the relative `"./"`, NOT a `{ "source": "github", "repo": …, "ref": … }` object. The github-source form makes Claude Code **re-clone the repo over SSH** (`git@github.com:…`) to fetch the plugin — which fails with "Permission denied (publickey)" on any machine without SSH keys (most HTTPS/`gh`-auth users), **even for a public repo**. The `"./"` form reuses the marketplace's own HTTPS checkout (one clone, no SSH) and inherits the marketplace's pinned `ref`. Don't confuse the two source surfaces: the *consumer's* `extraKnownMarketplaces` source IS `{source:github,repo,ref:main}` (that's the marketplace clone — HTTPS, fine); the *plugin* source inside `marketplace.json` is `"./"`. Empirically proven in the v2.0.0 Chunk-2 spike (throwaway public repo) and confirmed on prawduct's real marketplace install (`claude plugin install prawduct@prawduct` → v2.0.0, no SSH). Related operational gotchas from the same release: `claude plugin marketplace remove <name>` **cascades** — it disables dependent plugins and wipes their `enabledPlugins`/`extraKnownMarketplaces` from settings (don't use it as "cleanup" if you want the plugin to stay enabled); and `git merge -F -` does **not** read stdin like `git commit` (use `-m` or a real file). Full spike results in `docs/release-process.md`. Relates to Validate Before Propagating (#15) and Visible Costs (#9).

## Release-bound work merged feature→develop under gitflow: KEEP the build plan — it's a live release artifact, not spent

When you merge a feature branch whose work ships at a *later* `develop→main` release (gitflow batched-release, not the old develop-merge=release model), do NOT delete the build plan at merge time. The PR skill's merge-flow **step 7** ("delete `artifacts/build-plan.md` after merge; git preserves history") assumes the older model where the develop-merge *is* the release. Under gitflow the build plan stays a *live release artifact* in the window between the develop-merge and the develop→main release: release-checklist **step 4** runs `regen-views` *on the build plan* to flip its `## Status` checkboxes `[ ]`→`[x]` from the change-log's `status=shipped` entries (`docs/release-process.md`). Delete it at merge and the release step has nothing to regenerate — and the `active_build_plan` pointer in `project-state.yaml` must likewise survive until the release. Retention loses nothing: the release-pending state is already fully captured in the change-log's `status=merged` entry plus its "Deferred" note, and git preserves the plan regardless. So the deletion is both premature and lossy. Fix-shape: the skill's step 7 should be *conditioned on whether the merge is itself the release* (develop-merge that ships now → delete; develop-merge ahead of a batched develop→main release → retain). Discovered v2.0.0 PR #49 merge to develop (release deferred to develop→main per `docs/release-process.md`). Relates to Coherent Artifacts (#13), Living Documentation (#3), and Proportional Effort (#11).

## A `--plugin-dir` read-block is a dev-flag artifact, not a self-containment bug — pair it with `--add-dir`

When testing a Claude Code plugin's self-containment via `--plugin-dir <path-outside-the-project>`, a skill reading its OWN bundled file (`${CLAUDE_SKILL_DIR}/../../methodology/X.md`) is blocked by the session's working-dir read sandbox — which looks exactly like a self-containment defect ("the skill can't read its methodology"). It isn't: the path resolves correctly into the plugin, but the plugin tree sits outside the project dir, so tool reads there are sandboxed. Pass `--add-dir <plugin-path>` alongside `--plugin-dir` and the read succeeds; a real *marketplace* install grants plugin-tree reads automatically (the plugin is discovered from a config root already in scope), so `--add-dir` is a dev-flag-only need. Do NOT "fix" the skill's paths in response to a `--plugin-dir`-only failure. Verified v2.0.0 Chunk 12 (claude-code-guide + empirical A/B: `/prawduct:building` returned the plugin's H1 from a hallucinote-2 cwd with no `methodology/`, but only once `--add-dir` was added). Relates to Honest Confidence (#5) and Validate Before Propagating (#15).

## Test subprocesses: HOME=tmp_path leaks Python's pyc cache into the test repo

When a test invokes a Python subprocess via `subprocess.run(env={"HOME": str(project_dir), ...}, cwd=str(project_dir))`, Python's xcode-shipped interpreter writes `.pyc` cache files to `$HOME/Library/Caches/com.apple.python/...`. If `$HOME == cwd == git repo root`, `git ls-files --others --exclude-standard` then returns ~50 untracked cache files, inflating diff counts and triggering scope-widening / status-pollution failures in helpers that use it. Fix: set `HOME` to a directory OUTSIDE the test's git repo (e.g., `project_dir.parent / f"{project_dir.name}-home"`). Discovered v1.5.1 Chunk 03 (TestComputeVerifyResolutionsScopeSubcommand). Relates to Structural Awareness (#21).

## "Structurally enforced" requires verifying the harness actually enforces it

When claiming a constraint is "structurally enforced" by a config/sandbox/permission system, verify the enforcement before claiming it in change-logs or memory rules. The v1.5.1 Chunk 02 `!Bash(pytest*)` deny patterns added to skill `allowed-tools` were claimed structural but the Critic ran pytest unimpeded one chunk later — the harness allows `Bash(python3:*)` at project level which overrides skill-level `!`-deny. The prose claim "structurally enforced" survived only until the next chunk's Critic. Negative-path probe (write a test that asserts the constraint blocks the forbidden invocation) before claiming. Discovered v1.5.1 Chunk 04 Critic. Relates to Honest Confidence (#5) and Validate Before Propagating (#15). (v1.8.0 Chunk E added `test_no_allow_pattern_permits_pytest` — the probe this rule asked for — backing the pure-allow-list claim for the Critic.)

## Tool-restricted reviewer agents must be context:fork SKILLS, not named plugin subagents

When an agent needs a fine-grained tool restriction (the Critic: read-only git verbs, no pytest, no tree mutation), implement it as a `context: fork` skill with a pure-allow `allowed-tools` list — NOT as a named plugin subagent (`agents/<name>.md`). A named plugin subagent's `tools`/`disallowedTools` frontmatter is bare-tool-names-only (no `Bash(git diff:*)` granularity), so listing `Bash` grants unrestricted Bash; and a skill's `allowed-tools` does NOT bind a named subagent it delegates to. Only the fork-skill layer can express AND enforce the fine-grained allow-list. Verified v2.0.0 Chunk 4 (claude-code-guide + `--plugin-dir` probes); this is why the recorded "Option A — proper plugin subagents" decision was reversed mid-build once the unverified granularity assumption resolved. Relates to Reasoned Decisions (#4) and the safety constraint CRT-2M5P. Caveat: whether the fork-skill cap is enforced interactively (vs. headless, where a probe showed it is NOT) is still open — backlog CRT-9V4T.

## When a deliberate change turns a passing test red, renegotiate the contract in the open

When you intentionally change a documented behavior and an existing test fails because it encoded the OLD behavior, do NOT silently relax or delete the assertion. Rename the test to the new contract, re-document why in the docstring, invert the assertion, and record the rationale (commit/change-log). "Fix the code, not the test" (Principle 1) assumes the test encodes CORRECT behavior — when the test encodes the very thing you're deliberately removing (an every-session nag, or a safety hole asserted as "legitimate"), the test is a contract to renegotiate transparently, not a bright line to respect blindly. Keep any still-valid invariant explicit (changing template-drift to fire-once, also assert the user's place-once file is still never overwritten). Recurred ~20× across v1.8.0 chunks B/C/E. Relates to Tests Are Contracts (#1) and Reasoned Decisions (#4).

## A behavior change isn't done until every artifact that DESCRIBES it is updated

When you change behavior that a synced/templated/documented artifact describes — a briefing format, what files ship to product repos, a CLI's output — grep for every place that describes it, not just the code that implements it. The v1.8.0 cumulative Critic caught two misses in one bundle: the product CLAUDE.md template still described the pre-diet briefing, and the product-layout diagrams still omitted the now-shipped `tools/lib/`. Same blind spot both times: changed the behavior, missed the descriptions. The independent cumulative review is the fresh-eyes pass that catches doc-vs-behavior drift the builder is blind to. Relates to Living Documentation (#3) and Independent Review (#14).

## A decision reversed mid-chunk leaves stale rationale in prose you just wrote

When you reverse a design decision partway through a chunk, the code follows the new decision (it's what you're actively editing) but comments and docstrings you authored *under the old decision* keep asserting it — and they feel trustworthy precisely because you wrote them minutes ago. Before handing to the Critic, re-grep your OWN new comments/docstrings for the abandoned rationale. v2.0.0 Chunk 7: the banner docstring claimed the version marker was gitignored "via `GITIGNORE_ENTRIES` in `lib/core.py`" — written while leaning toward adding it there; the decision then flipped to gitignore-in-this-repo-only + defer-to-Chunk-9, the code followed, the docstring lied until the Critic flagged it. Distinct from "update every artifact that describes a behavior change" (#3): the trigger here is a *reversal within one work cycle*, and the stale prose is your own fresh code-adjacent text. Relates to Living Documentation (#3) and Reasoned Decisions (#4).

## Editing a runtime that governs the current session: check your own signals first

When you modify a runtime that ALSO governs the session you're editing in (a self-hosted framework — prawduct's hooks govern prawduct's own development), verify the change doesn't alter the CURRENT session's governance before trusting it. v2.0.0 Chunk 8 added "legacy hook stands down when it detects the plugin" to `tools/product-hook` — which is THIS repo's own active SessionStart/Stop hook. A wrong detection signal (or a stray `enabledPlugins` / `distribution: plugin` already in this repo) would have silently disabled the very Stop gate enforcing the session, with no test failure to warn you. The check is one command: run the new detection against the repo root and confirm it returns the expected value (here: plugin-active = False) before relying on the edit. "Am I standing on the branch I'm sawing?" Distinct from test coverage — this is about the live session, not the test matrix. Every remaining v2.0 migration chunk (9–13) edits this same self-hosted runtime, so the check recurs. Relates to Structural Awareness (#21) and Validate Before Propagating (#15).

## Cumulative-Critic finds first-use regressions chunk-Critic can't

When wrapping a multi-chunk bundle, expect the cumulative-Critic pass to surface ≥1 finding the chunk passes missed — mechanisms introduced in chunk N often misbehave only against prose in chunk M. Plan a remediation slot before `/pr create` rather than treating the cumulative pass as a formality. Because the lens differs: chunk-Critic diffs the chunk's own commit; cumulative-Critic diffs `merge-base...HEAD` and catches helper-vs-prose interactions invisible at chunk scope. Wave 1's `_looks_like_file_path` (Chunk 02) false-positived on slash-commands in Chunk 01's prose — only the cumulative pass saw both at once. Relates to Independent Review (#14).

## Auto-enable belongs with visibility, not with enforcement

When deciding whether a new opt-in feature should silently auto-enable on sync, ask whether flipping it ON would cause the next PR to **block** unexpectedly. Visibility surfaces (derived views, additional briefing fields, schema fields the writer fills in) auto-enable safely — at worst the user sees new output. Enforcement surfaces (Critic BLOCKING checks, gates that refuse `/pr create`, hooks that exit non-zero) must be explicitly invoked via `migrate --enable-<feature>` so the workflow commitment is visible before it bites. Chunk 07's F1 derived-views auto-enabled silently on sync ("users should get views for free"). Chunk 10's F4 coverage *deliberately* broke the pattern — a silently-flipped `coverage_required: true` would BLOCK the user's next PR for reasons they didn't agree to. Same shape (one-shot manifest flag, additive YAML edit) but opposite invocation policy. **Nuance (v2.0.0 §5a — owner override):** this rule is *superseded* when the owner explicitly models governance **as CI** — a plugin update MAY ship a gate that blocks immediately, with no opt-in / adopt step, *provided the block is attributed*: the version-delta banner announces the new gate on the bump that introduces it, and the blocking message names the version + gate so a surprise block is always traceable to the update ("no different than shipping a CI change that blocks someone's push"). Visibility is preserved as **attribution, not opt-in**; the deciding question becomes whether a block is *explainable*, not whether it was *pre-adopted*. Relates to Visible Costs (#9) and Governance Is Structural (#22).

## Removing a mechanism requires removing its name too

When deprecating or removing a mechanism, grep for the mechanism's **name** in active prose and update terminology in the same change — not in a follow-up cleanup. Because lingering names mislead readers into looking for code that doesn't exist; the resulting confusion is worse than not removing the mechanism at all. The "fingerprint" tree-hash freshness mechanism was removed pre-v1.4, but the word survived in 5 active sites (shebang docs, docstrings, lockstep build-governance prose) until Chunk 10 caught them — a year of reader-confusion gap. Fix-shape: each PR that removes a mechanism includes a `grep -rn` pass for its name(s) across `tools/`, `templates/`, `methodology/`, `agents/` and updates each hit to either describe what replaced it or annotate it as historical. **Caveat (v2.0.0 Chunk 13): you can only remove the name from a path once the mechanism has actually LEFT that path.** A mechanism kept deliberately alive for un-migrated consumers — a frozen "live service," not dead code — correctly keeps its name on the paths it still occupies. Before deleting a "deprecated" mechanism, verify nothing reaches back to it at runtime (here: file-sync's `tools/`+`templates/` are `MANAGED_FILES` and an un-migrated product's `try_sync()` calls back to this framework's `prawduct-setup.py` every session — a live service). Sweep the name from the *active* path now; gate the still-live path's sweep behind the mechanism's actual removal (Chunk 13 swept the plugin/active path + dropped `agents/`; the `templates/`+`tools/` sweep is deferred to milestone M4, when the engine is finally deleted). Relates to Living Documentation (#3), Close the Learning Loop (#18), and Unnecessary Backwards Compatibility (a live consumer is the opposite case — removal there is a breaking change to be sequenced behind migration).

## Build-plan fields use `**Title Case:**`, not snake_case

When adding a new build-plan field, format the label as `**Title Case:**` (bold, words-with-spaces, colon) — matching `**Type:**`, `**Critic mode:**`, `**Requirements Confidence:**`, `**Acceptance criteria:**`, `**Done when:**`. Snake_case (`foreign_api:`, `coverage_required:`) is the YAML-key namespace in `project-state.yaml`, a different surface. The methodology's prose form must be string-identical to the template's label except for the `**...**` bolding — so the Critic's substring-match finds real plans. Wave 1's F8 conflated the two namespaces (`foreign_api:` in prose, `**Foreign API:**` in template) and the Critic-check substring never matched a real plan. Relates to Coherent Artifacts (#13).

## Build-plan chunk headings must use `### Chunk N:` colon form — em-dash fails the parsers silently

When writing or editing a build plan, chunk headings AND `## Status` lines must use the colon form (`### Chunk N: Name` / `- [ ] Chunk N: Name`). The chunk-id parsers — `verify-chunk-refs`, `regen-views`'s `CHUNK_LINE_RE`, and `infer-critic-mode`'s chunk-type lookup — all isolate the id via `rest.split(":",1)[0]`, so an em-dash separator (`### Chunk N — Name`) makes the *whole string* the "id", which matches no heading and silently disables Goal-2 ref verification and per-chunk scoping across the ENTIRE plan (chunk-type fail-closes to `code`, so the session still gates — but the ref-verifier and derived views quietly stop working). The v2.0.0 plan shipped with em-dashes; the failure was dismissed as out-of-scope one Critic review before becoming a blocker the next — a deferred finding is not a retired finding. Fix-shape: keep the colon form (leading zeros are tolerated, so `1` and `01` both parse); consider a guard test asserting the active build plan's chunk headings parse, so a format mismatch fails loudly instead of degrading silently. Sibling of "Build-plan fields use `**Title Case:**`" above — build-plan text is a contract with the parsers, and format mismatches fail silent. Discovered v2.0.0 Chunk 1 Critic. Relates to Coherent Artifacts (#13), Escape hatches create silent failures (#22), and Honest Confidence (#5).

## Submodule and same-name function in __init__ shadow each other

When a `lib/__init__.py` does `from .foo import foo` (re-exporting a function whose name matches its submodule), attribute access `lib.foo` returns the function while `sys.modules['lib.foo']` still holds the module — `import lib.foo as alias` resolves to one or the other depending on context, and `monkeypatch.setattr(alias, "name", ...)` raises `AttributeError` when it lands on the function. Because Python's `from package.submodule import name` registers both in the parent's namespace; the later import wins for attribute lookup. Fix-shape: use the `_cmd.py` (or other) suffix that every other lib module already uses (`migrate_cmd.py`, `sync_cmd.py`, `init_cmd.py`, `validate_cmd.py`, `views_cmd.py`) — the convention isn't aesthetic, it prevents this collision. Caught in Chunk 13 when test monkeypatches failed; renamed `audit_learnings.py` → `audit_learnings_cmd.py` before commit. Relates to Coherent Artifacts (#13) and Reasoned Decisions (#4).

## Detection of structural characteristics should not rely on mechanistic surface markers

When classifying whether a project has a structural characteristic (uses LLM inference, has human interface, runs unattended, sensitive data, multi-process), use *what the project's correctness depends on* — not surface markers like import statements, hostnames, or filename patterns. Because surface markers miss cases where the same structural feature manifests differently. Prawduct's own Open 1 empirical-detection survey initially classified itself as "not LLM-using" because the framework's executable code has zero LLM SDK imports, zero LLM-API hostnames, and zero message/role/tool-use shapes — but the framework's primary deliverable IS prompts (skill markdown files loaded by an external Claude Code runtime), so its correctness fundamentally depends on LLM behavior. The mechanistic test missed Category B (runtime-instruction) projects entirely until the user surfaced the gap. Fix-shape: every structural-characteristic detector answers "what determines correctness here?" first, then lists surface signals as *evidence* for that structural question — not as the question itself. The distinguishing feature for the LLM case turned out to be "prompts-as-code (Python builds API request bodies) vs prompts-as-content (markdown loaded by an external runtime)" — both correctness-depends-on-LLM, neither captured by SDK enumeration. Discovered 2026-05-28 during prompt-management v0.1 → v0.2. Relates to Structural Awareness (#21), Honest Confidence (#5), and Bring Expertise (#7).

## Shared "answer" state and personal "nag" state belong in separate stores

When designing state about ongoing concerns (advisories, follow-ups, todos), separate two semantically distinct kinds of state: the *answer to the question* (committed, team-shared — e.g., `project-state.yaml`'s `uses_llm_inference: true`) and *have I personally dealt with this nag?* (gitignored, per-clone — e.g., `.advisories.json`'s dismissed list). Because conflating them gets both directions wrong: either everyone's dismissals leak across clones (personal task state shouldn't propagate to teammates) or no resolution propagates (when a teammate's commit answers the structural question, the answer should auto-clear the nag for everyone on next pull, not require each developer to dismiss separately). The post-sync advisory infrastructure (`documentation/post-sync-advisory-spec.md` v0.2) made this explicit: probes declare both a *trigger condition* (reads code state — "should I ask?") and a *resolution condition* (reads `project-state.yaml` — "has the team answered?"); active state lives in the gitignored nag log, settled facts live in the committed answer store. Discovered 2026-05-28 via Q2 in the advisory spec when the naive single-store design would have produced wrong cross-clone behavior. Generalizes beyond advisories — any feature that tracks "did the team agree on X?" + "have I personally followed up?" benefits from this separation. Relates to Coherent Artifacts (#13) and Structural Awareness (#21).

## Framework ownership follows the write strategy, not just registry membership

When defining "the framework owns this file" sets — for auto-commit, hash-based change detection, or "is this user WIP or framework drift" partitioning — the discriminator is *whether the framework overwrites the file on every run*, not "is the file in any registry the framework knows about." Template / block-template / always-update / merge-settings strategies overwrite each sync; place-once strategies create once and never re-touch. The two have opposite ownership semantics after first creation, even though both lists live side-by-side in `core.py`. Because Chunk 11's first-pass `_framework_known_paths` included `PLACE_ONCE_TEMPLATES` and `PLACE_ONCE_COPY` (`.prawduct/change-log.md`, `.prawduct/backlog.md`, `tests/conftest.py`), a user chunk-close append to change-log.md would have been swept into the auto-commit's `chore(sync):` marker — re-creating the exact co-mingling F5a aims to prevent. Fix-shape: when building "framework-managed" sets, derive them from the *strategies that overwrite* (the manifest's `files` dict, sourced from `MANAGED_FILES`), not from "every path the framework has ever placed." Place-once is genuinely place-once — trust the contract. Relates to Reasoned Decisions (#4) and Coherent Artifacts (#13).

## A leftover marker is not an in-progress signal — and a test using the canonical marker leaves the real-world branch untested

When detecting external-tool state from filesystem markers (a `.git/` ref, a lockfile, a PID file), check whether the tool *removes* each marker when the condition ends — a leftover artifact is not an in-progress signal. `_git_op_in_progress` treated `.git/REBASE_HEAD` as a live rebase, but git does **not** clean up `REBASE_HEAD` when a rebase ends (it lingers until the next rebase overwrites it), unlike `MERGE_HEAD`/`CHERRY_PICK_HEAD`/`REVERT_HEAD` which git *does* remove — so the stale ref produced a phantom "rebase in progress" on every downstream session and could block auto-sync. Prefer the tool's own authoritative test: the `rebase-merge`/`rebase-apply` directory check (what `git status` uses) was already present and correct; the ref check was a redundant false-positive source. Two compounding lessons: (1) the existing regression test simulated a rebase with the `rebase-merge` *directory* — it passed via the correct branch and never exercised the buggy `REBASE_HEAD` *file* branch, so the bug only ever fired in the real world; when a detector has multiple input paths, test each one with the messy inputs real systems produce (leftover refs), not just the clean canonical marker. (2) The misdetection was cached into `.prawduct/.sync-pending` and replayed verbatim every session, turning a one-time false positive into sticky noise — a derived/cached blocker that never re-evaluates makes any transient false-positive permanent. Discovered 2026-06-01 from a Hallucinote bug report. Relates to Tests Are Contracts (#1), Root Cause Discipline (#16), and Honest Confidence (#5).

## A near-verbatim file PORT carries the source's prose — adapt the docs, not just the logic

When you create a new file by copying an existing one and surgically adapting it (the design-blessed "duplicate during coexistence" pattern — e.g. `tools/product-hook` → plugin `bin/prawduct-hook` in v2.0.0 Chunk 5), the copy inherits every docstring, comment, and user-facing message from the source — and those describe the SOURCE's world, not the new one. After adapting the logic, do an explicit doc-sweep: grep the copy for terms that were true only of the source (here: "trigger sync", "needs tools/lib", "run a framework sync", `python3 tools/product-hook` tool forms) and repoint them to the new context. The Chunk 5 Critic's one WARNING was exactly this — the logic was correct and tests passed, but the inherited prose lied (it claimed the plugin syncs and that lib might be absent, when the plugin never syncs and always bundles lib). EXCEPTION: leave verbatim any string that is a cross-file CONTRACT (the `final|fallback-no-tools-lib` token the critic skill prose matches on) — renaming it silently breaks the consumer. Fix-shape: treat a copy-port as logic-adapt PASS + doc-sweep PASS, two passes, before declaring done. Discovered v2.0.0 Chunk 5. Relates to Living Documentation (#3), Coherent Artifacts (#13), and The System Can Be Understood (#6, accurate diagnostics).

## A subagent's reported COUNT or LIST is a lead, not ground truth — verify before a blanket edit

When a subagent (Explore/general-purpose) reports an enumeration you're about to act on mechanically — "there are N occurrences of X", "these 4 call sites", "this list of files" — confirm it with a direct `grep -c`/`grep -n` before a `replace_all` or any uniform operation that assumes the count is complete. In v2.0.0 Chunk 5 an explore agent reported "4 lazy lib-import sites"; a direct grep found 5 (it missed `cmd_accept_operator_verification`). A blanket edit trusting "4" would have left the 5th site on the old `tools/`-relative path — a silent miss, not a loud failure. The verification is one cheap grep; the failure mode (an unedited site that looks edited) is expensive and invisible. Fix-shape: for any agent-reported set that drives a sweep, re-derive the set yourself with the precise query right before the sweep. Discovered v2.0.0 Chunk 5. Relates to Validate Before Propagating (#15) and Honest Confidence (#5).

## Verify the platform's copy/packaging boundary before duplicating a shared bundled file — a prior "duplicate into each consumer" choice may be an unverified-constraint workaround

Before deciding whether to DUPLICATE a shared file into each consumer dir vs. REFERENCE one canonical copy, verify the platform's file-resolution/packaging boundary — and don't cargo-cult an earlier duplication decision made when that boundary was unverified. In v2.0.0 Chunk 4 the Critic/PR protocols were COPIED into each skill's own dir (`skills/critic/review-protocol.md`) and referenced via `${CLAUDE_SKILL_DIR}/…` — the safe move *then*, because Claude Code's plugin-install copy semantics were unverified. Chunk 6 needed the same call for `methodology/`. Rather than inherit the duplication, I verified (claude-code-guide → plugins-reference "path traversal limitations"): a marketplace install copies the WHOLE plugin tree — the boundary is the PLUGIN ROOT, and only traversal *outside* it fails. So `methodology/` stays ONE canonical source at plugin root, read by hooks via `${CLAUDE_PLUGIN_ROOT}/…` and by skills via in-plugin `${CLAUDE_SKILL_DIR}/../../methodology/…` (a traversal that stays inside the root) — no copies, no parity test, no drift surface. Note the two valid in-plugin read paths: `${CLAUDE_PLUGIN_ROOT}` substitutes in HOOK commands and bash-injection/subprocess env but NOT in skill PROSE; skill prose gets `${CLAUDE_SKILL_DIR}`, so a skill reaches a plugin-root file via `${CLAUDE_SKILL_DIR}/../../`. Fix-shape: when a duplicate-vs-reference decision recurs, re-verify the constraint that motivated the earlier choice — single source of truth beats a parity-tested copy whenever the platform actually guarantees the canonical file ships. Discovered v2.0.0 Chunk 6. Relates to Validate Before Propagating (#15), Reasoned Decisions (#4), and the DRY/no-unnecessary-duplication design goal (Critic Goal 7).

## A plugin skill with unparseable YAML frontmatter loads with ALL metadata silently dropped — validate it in CI

When shipping plugin skills (`skills/<name>/SKILL.md`), a frontmatter YAML parse error does NOT fail loud — the loader drops EVERY frontmatter field and the skill loads unusable (no `description`, not discoverable/invocable as intended). The unit suite is blind to this: it exercises skill *behavior* via direct subprocess/lib calls, never the loader's frontmatter parse, so the suite stays green while the skill is broken. v2.0.0 Chunk 6 shipped three reader skills (discovery/planning/reflection) whose `description:` value held an unquoted `: ` (colon-space) — YAML reads that as a nested mapping → parse error → empty metadata — and it went unnoticed for a chunk until `claude plugin validate` surfaced it during the Chunk-11 dogfood. Fix-shape: parse every `skills/*/SKILL.md` frontmatter with `yaml.safe_load` in a test AND run `claude plugin validate <path>` as part of plugin-chunk verification; quote any scalar containing `:` / `#` / `|` / leading-special chars. Discovered v2.0.0 Chunk 11. Relates to Validate Before Propagating (#15) and Tests Are Contracts (#1).

## Dogfooding the generator on its own output masks output-relative bugs the real consumer would hit

When a generator/framework repo runs its OWN output (here: the framework governed by its own plugin via `--plugin-dir .`), paths relative to the generator's tree resolve fine — because the generator's checkout HAS them — so the dogfood passes while the same artifact breaks in a real consumer that lacks those paths. v2.0.0 Chunk 11: the plugin's critic skill read `docs/principles.md` repo-relative and hardcoded "This is the Prawduct framework itself, not a product repo"; both are correct in the framework checkout and wrong/broken in any product repo, and a `--plugin-dir .` run here would never expose either. Therefore "self-contained / no external files needed" must be proven by (a) a STATIC audit of the artifact for tree-relative reads, and (b) a run against a tree that genuinely lacks the generator's source (a real consumer, or a stripped copy) — never by the generator dogfooding itself. Discovered v2.0.0 Chunk 11 (the real-consumer proof is Chunk 12 — hallucinote). Relates to Validate Before Propagating (#15) and Honest Confidence (#5).

## Relocating a source file: sweep every READER of the old path, not just the data-key references

When you move a source file (`git mv A → B`) and repoint the engine that reads it, the migration is not done until **every reader of the old path** is swept — including test content-assertions that `read_text()` the old path and fixtures that write/read it, not only the structural/manifest references that name the path as a data key. v2.0.0 Chunk 14 relocated 6 file-sync skill sources `.claude/skills/<n>/SKILL.md → templates/skill-<n>.md`; validating the hardcoded template-*value* assertions and existence checks all passed, but **5 failures + 8 errors** surfaced on the first full-suite run from tests that read the framework skill *content* by path (and a fake-framework fixture that *wrote* the old source path). Grep the old path for `read_text` / `open` / fixture writes, not just for the path string used as a dict key. The content was byte-identical at the new home, so every repoint was a one-line path swap — but they had to be found. Relates to Validate Before Propagating (#15) and Living Documentation (#3).

## A review's "inert / harmless" verdict on a latent bug is conditional on the current call graph

When review judges a latent defect "inert" or "harmless" *because nothing currently exercises the broken path*, treat that as "inert **for now**", not "safe to leave forever" — the next feature that touches the dormant path makes it live. v2.0.0 Chunk 14: the relocation Critic correctly flagged the plugin `lib/core.py`'s byte-parity `FRAMEWORK_DIR = parent.parent.parent` mis-resolving one level too high (it sits at `lib/`, not `tools/lib/`) as inert — and it WAS, until the very next chunk's scaffolder became the first plugin code to render `templates/` at runtime via `core.TEMPLATES_DIR`, which crashed (`…/source/templates/...` not found). So: when you write code that touches a path a prior review called inert, re-check the verdict's premise before relying on it. Fix here: resolve `templates/`/`VERSION` from the plugin root (`__file__.parent.parent`), the established `bin/`/`hooks/` pattern — not via `core`'s parity-locked constant. Relates to Honest Confidence (#5) and Root Cause Discipline (#16).

## Excising a subsystem silently kills the incidental work it happened to host — re-home the orphaned call, and test the positive

When you remove a mechanism, audit not just what *calls* it (the name-sweep above) but what *it* called that was not actually part of its purpose — incidental work co-located inside the removed code path dies with it, and no test catches it because the tests assert the subsystem is GONE, not that its side effects survived. v2.0.0 Chunk 5 excised file-sync `sync` from the plugin runtime; the post-sync advisory **probe** step lived inside the sync tail (`tools/lib/sync_cmd.py` → `run_sync_advisories`) but was purely local — it reads the consumer's own `.prawduct/` (backlog.md, project-state.yaml), no network/checkout — i.e. not sync at all, just co-located. Excising sync silently took it: `cmd_clear` hardcoded `sync_advisories = []`, so the probe roster never ran in ANY plugin repo, `.advisories.json` never refreshed, and the `legacy-backlog-format` nudge → `/prawduct:backlog migrate` could never fire (surfaced ~4 months later, as a user's confusion that the plugin cutover didn't migrate their backlog). The port thoroughly verified the NEGATIVE ("no sync": `test_sync_cluster_excised`, `test_clear_does_not_sync_even_with_manifest`) but never asserted the POSITIVE that sync's non-sync side effects were re-homed. Fix-shape: when removing subsystem X, list everything X *did* and split it into "X's actual job" vs "work X merely hosted"; re-home the latter to a surviving call site (here: `cmd_clear` now calls `run_sync_advisories` directly, before the briefing reads the store) and add a regression test asserting the re-homed behavior STILL happens. Directly relevant to the pending Chunk-13 file-sync removal ([MIG-M4-REMOVE]), which excises more of the same engine. Discovered 2026-06-03 (advisory-probe fix). Relates to Root Cause Discipline (#16), Validate Before Propagating (#15), and Complete Delivery (#2 — a capability dropped without a decision is a silently-dropped requirement).

## A "renders-but-doesn't-resolve" leak is a SURFACE, not a line — sweep the whole renderer and assert the bad form is ABSENT

When user-facing output names something that won't resolve in the current context — a bare `/backlog` skill in a plugin repo that namespaces it `/prawduct:backlog`, a stale command form, a renamed token — fix every command-bearing line in the SAME renderer in one pass, not just the one you noticed, and add a test that asserts the WRONG form is ABSENT, not merely that the right form is present. A presence-only assertion (`assert "/prawduct:backlog" in out`) passes happily while a sibling line still emits the bare `/backlog`. In the ADV-3K7Q fix the Critic caught the same leak class in two successive rounds — first the advisory dismiss hint left bare after the migrate action was fixed, then `/backlog to triage` left bare after both advisory lines were fixed — because each patch targeted the flagged line, not `assemble_session_briefing` as a surface. Root cause upstream: v2.0.0 Chunk 13's namespace divergence was driven module-by-module (it diverged `operator_verification`) instead of by enumerating every command-bearing OUTPUT, so `backlog_probes` and three briefing status lines were silently missed and only surfaced when v2.0.2 re-enabled the advisory. Fix-shape: when you touch one occurrence of a context-dependent leak, immediately `grep` the enclosing renderer (and its frozen twin) for the whole leak class, fix all live-context occurrences together, leave the frozen-context twin (the file-sync `tools/` copy) untouched, and pin it with assert-present + assert-absent. Extends the copy-port doc-sweep rule (a copied renderer inherits the source's command vocabulary) and the deprecation name-sweep rule. Discovered 2026-06-03 (ADV-3K7Q). Relates to Coherent Artifacts (#13), Validate Before Propagating (#15), and Complete Delivery (#2).

## An "assert the bad form is ABSENT" sweep is only as good as the pattern that defines the bad form — enumerate the whole FORM-FAMILY, not one spelling

The renderer-surface rule above says grep "the whole leak class." The trap: a frozen-vs-namespaced vocabulary has MULTIPLE spellings of the SAME leak, and a grep that encodes one spelling silently passes over the siblings. Completing ADV-3K7Q's gate-message sweep, I grepped `/(critic|pr|backlog|learnings|...)\b` and cleared every BARE slash-command form from `bin/prawduct-hook` — but that pattern can't match the **hyphenated frozen skill name** `/prawduct-advisory` (the v1 file-sync skill; the plugin form is `/prawduct:advisory`), so a `cmd_advisory` docstring kept emitting it. The Critic caught it — the exact leak class I thought I'd swept, in a spelling my pattern didn't cover. Widening to `/prawduct-[a-z]+` then surfaced a THIRD spelling, the legacy CLI tool `prawduct-setup` (correctly left as a factual historical reference, not a command-resolution leak). Fix-shape: before declaring a namespace/rename sweep done, list every SPELLING the frozen vocabulary uses for the thing — bare `/cmd`, hyphenated `/prawduct-cmd`, legacy CLI `prawduct-setup` — and run one grep per spelling (or a union pattern), because each spelling is a distinct regex the others won't match; then bake the full spelling-set into the absent-assertion's `FORBIDDEN` list, not just the spelling you happened to fix. Discovered 2026-06-03 (gate-message sweep). Extends the renderer-surface rule above; relates to Validate Before Propagating (#15) and Complete Delivery (#2).

## An untested governance bound rots silently across a migration — sweep the guards (with tests), not just the prose

The name-sweep rule above ("Removing a mechanism requires removing its name too") covers prose; its sharper corollary is about *guards*. When a migration removes or relocates a mechanism, the code that **enforces a bound by naming the old shape** rots silently if no test pins it. Two instances surfaced together in the 2.0-rock-solid pass (2026-06-03), both rooted in M4's `agents/`→`skills/` plugin cutover: (1) the trivial/doc-only file-set gate (`_classify_trivial_change`) still bounded `agents/` (deleted) and was **missing `skills/`** — so a `Type: trivial` chunk could edit `skills/critic/SKILL.md` (the Critic's own protocol) without tripping the catastrophic-blast-radius guard; the literal survived precisely because the bound had **zero test coverage**. (2) M4 deleted `tests/test_coverage_gaps.py`, which carried the only `_SESSION_GITIGNORED_PATHS`↔`GITIGNORE_ENTRIES` parity test, while leaving comments that still cited it as live — so the two mirrored lists could drift undetected. Fix-shape: when a migration removes/relocates a mechanism, enumerate the **guards** that referenced the old shape (path bounds, allowlists, parity tests, prefix tables) and (a) repoint them to the new shape, (b) add the regression test if it was missing, or (c) **restore** a deleted guard rather than deleting its now-dangling references — deleting a reference to a guard that *should* exist hides the gap instead of closing it. A guard with no test is the thing most likely to carry a stale literal through a cutover. Discovered 2026-06-03 (waiver-pragma / 2.0-rock-solid pass; gate fixed test-first, 12 new tests; parity test restored). Relates to Tests Are Contracts (#1), Root Cause Discipline (#16), and "Removing a mechanism requires removing its name too" (the prose sibling of this rule).

## In a leaf-first decomposition, dependency-scan a chunk's COMMAND bodies against later-chunk symbols before moving — and never move a parity-pinned mirror just because a deliverable lists it

A leaf-first module extraction (move module N only after the modules it depends on) is safe for *leaf helpers* but has two traps when a chunk also moves *command bodies* or *named functions* — both surfaced in STH-9V4K ch.5 (`lib/coverage.py`), and the build plan was wrong on both. (1) **A command body can reach UP the DAG even when its helpers move down it.** The plan assigned `cmd_verify_coverage` + `cmd_check_cumulative_critic` to the `coverage` chunk, but an AST scan of their bodies (run BEFORE editing) showed they call `_validate_evidence_schema` / `validate_critic_findings` / `_CRITIC_MODE_CUMULATIVE` — all symbols assigned to the LATER `gates` chunk. With the DAG `coverage ← gates`, moving them into coverage would be a `coverage → gates → bin` back-import. Fix: defer those two commands to the `gates` chunk (where `gates → coverage` is legal); their shared helpers still move down. (2) **A function carrying an explicit mirror/parity contract stays put regardless of the deliverable.** The plan listed `_read_bool_yaml_key` to move + "repoint test_views.py", but its def was annotated `# intentional inline mirror (import-light hot path); pinned by TestBoolKeyCallSiteParity` and a test class pins it to `lib.core.read_bool_yaml_key` — the same class as `_read_str_yaml_key`, which the plan's Out-of-scope keeps in the hook. The plan's Out-of-scope merely forgot this sibling mirror. Moving it would break the parity test and regress the import-light invariant. Fix-shape, now part of the move ritual for every remaining chunk (6, 7): before moving a chunk's symbols, (a) AST-scan each moved *body* for references to symbols slated for any LATER chunk — if found, defer that body to the chunk that owns those symbols; and (b) grep each moved def's surrounding comment + the test suite for `mirror` / `*Parity*` / `import-light` — if pinned, it stays in the hook even if the deliverable lists it. Both checks are cheap and both caught a real plan defect here. Discovered 2026-06-07 (STH-9V4K ch.5). Relates to Validate Before Propagating (#15), Requirements Precede Code (#6 — the plan is the parent; correct it, don't silently follow or silently deviate), and Reasoned Decisions (#4).

## A format's schema legend lives in `templates/` (scaffold-only) — adding an optional field reaches already-onboarded repos only via a migrate/triage *refresh* step, not the template

When you add an optional field to a structured-file format (here the backlog: `stage:`/`refs:`/`accepted-by:` in v2.0.15), there are **two** propagation surfaces that drift independently, and it's easy to wire only the first: (1) the **per-item** backfill — the triage/`migrate` step that writes the new field onto existing items; and (2) the file's **schema legend** — the `<!-- … -->` header comment that documents what each field means. The legend is authored **once at scaffold time** from `templates/backlog.md` and is never re-applied to an already-onboarded repo, so a product that adopts the new field ends up with backfilled items behind a legend that never documents them — a reader hits `stage: ready` on an item with no key explaining it. `../scriob` hit exactly this (2026-06-08): their grooming pass backfilled `stage:` but the legend still didn't mention `accepted-by`, and they had to hand-patch it. Root cause is the same shape as [[a new build plan with scope null inherits another scope's shipped checkbox flips]]'s tail ("the warning lives in a template comment that from-scratch authors don't see, so it keeps recurring") — **anything that lives only in `templates/` is scaffold-only and does not reach onboarded repos**; the universal carriers are `migrate`/triage (for backlog.md) and `methodology/session-digest.md` (for default-behavior changes). Fix-shape: when adding an optional format field, wire BOTH surfaces — the per-item backfill AND a legend-refresh step in `migrate` that reconciles the header to the canonical field set (additive/non-destructive: fill missing canonical-field docs, never remove a repo's local extension like a `kind:` facet). Self-check when shipping a format addition: "a repo onboarded *before* this field existed runs `migrate` — does its legend end up documenting the field?" If no, the legend-refresh step is missing. Fixed in `skills/backlog/SKILL.md` migrate step 4c + `documentation/backlog-system-requirements.md` §8.4. Discovered via scriob (2026-06-08, develop). Relates to Living Documentation (#3), Coherent Artifacts (#13), Complete Delivery (#2), and [[a new build plan with scope null inherits another scope's shipped checkbox flips]].

## A structural bound that ENFORCES a declaration is not a DETECTOR of the declared property — reusing it at a new boundary silently drops its justification

When you reuse a structural predicate at a second boundary, re-derive *why it's valid there* — don't assume the justification travels with the code. A bound can be a **necessary** condition that *enforces* an explicit declaration ("you declared this chunk `Type: trivial`; therefore its files must stay within these paths") without being a **sufficient** condition that *detects* the declared property ("these files are within the paths, therefore the work is trivial"). The `Type: trivial` fileset bounds (`_classify_trivial_change` / `_TRIVIAL_PROTECTED_PATHS`) were designed as the *enforcement* of a per-chunk declaration — the stop hook checks them **only when `chunk_type == "trivial"`**. The PR-boundary `check-pr-trivial` / `_pr_diff_is_trivial` reused the *same bounds* with no link to any declaration, so it became a *detector*: a multi-chunk **feature** that only modified existing files cleared the fileset and was reported `trivial`, skipping BOTH the cumulative-Critic gate and the independent PR reviewer (the two core review gates). The skill text even admitted the sufficient condition was elsewhere — *"trivial is a semantic claim, validated per-chunk by Critic Goal 3"* — but nothing checked that claim at the bundle boundary, so a necessary condition silently stood in for a sufficient one. Compounding it: the fast-path shipped with **zero** test coverage at the PR boundary — a **skip-gate (a gate whose job is to waive other gates) needs the *most* adversarial coverage, not the least**, because its failure mode is invisible (work sails through). Discovered 2026-06-08 (incoming-bug from scriob); user chose to retire the PR-boundary fast-path entirely rather than gate it on the declaration (the doc-only fast-path — all-`.md` = no code — stays, because *that* predicate is genuinely sufficient at its boundary). Fix-shape: when a predicate moves to a new boundary, write down the sufficient condition for the *decision being made there* (here: "skip review") and confirm the predicate actually establishes it — if it only establishes a necessary precondition, either gate on the real (declared/semantic) signal or don't make the decision automatically; and give every skip-gate a regression test that asserts a non-eligible case still BLOCKS. Relates to Reasoned Decisions (#4), Validate Before Propagating (#15), Governance Is Structural (#22), Tests Are Contracts (#1), and [[an untested governance bound rots silently across a migration]].

## A rebuild scoped to a subsystem's "remaining / deferred" parts silently omits an already-shipped part that was deleted in between — re-port against the spec roster, not the open-work list

When you rebuild a subsystem in a new home, enumerate what it is *supposed* to contain from the **specification**, not from the **open-work backlog** — because a backlog framed as "the *remaining* N" silently assumes the already-shipped part still exists, and if a migration deleted that part in between, the rebuild reproduces only the remainder and the primary member vanishes with no error. The post-sync advisory backlog roster is spec'd (`backlog-system-requirements.md` §8.2) as **four** probes; `legacy-backlog-format` (the `/prawduct:backlog migrate` nudge — trigger: `backlog.md` has >5 items, none carrying a `[PFX-XXXX]` id; resolution: `backlog_format_version: 2`) was the **single production probe** shipped in v1.7.0, and `[BKL-2F7K]` tracked only "ship the three *remaining* §8.2 probes." M4 (v2.0.3) then deleted the file-sync `tools/lib/backlog_probes.py` **with the engine** — taking the primary probe. The v0.3 backlog rework built a new plugin-native `lib/backlog_probes.py` scoped to `[BKL-2F7K]` (the three deferred probes) and assumed the primary one already existed — so `register()` registered three and never re-ported `legacy-backlog-format`. The roster ran (the grooming probe fired in real briefings, which is exactly why the absence *looked* fine — the channel was alive, just missing one member), but the migrate nudge could never fire. This is the **second chapter** of [[excising a subsystem silently kills the incidental work it happened to host]]: chapter one re-homed the advisory *infrastructure* (so the roster runs); this chapter is the *member* that the infra was always about, still missing because the rebuild's scope inherited a "ship the rest" framing that predated the deletion. Surfaced 2026-06-08 as a user's report that updating the plugin didn't nudge their backlog to migrate. Fix-shape: when rebuilding/porting a subsystem, list its members from the spec/requirements roster and diff that against what the new module actually registers (here: a `register()` that names every spec'd probe; an end-to-end test that drives the *registered* roster, not just each probe in isolation, so an unregistered member fails a test); and when a deletion lands between a feature's spec and its build, re-confirm the baseline the feature's scope assumes still exists. Relates to Complete Delivery (#2 — a member dropped without a decision is a silently-dropped requirement), Root Cause Discipline (#16), Validate Before Propagating (#15), and [[removing a mechanism requires removing its name too]] (its inverse: this is *rebuilding* requires rebuilding the whole roster).

## A persisted schema's requirements are its consumers' future queries — lock-in is reversal cost, not LOC, so "small format" never exempts it from decision research

The decision-research trigger list already names **lock-in** as a research trigger, but lock-in gets mis-sized when judged by implementation effort: a 10-line JSONL writer with the wrong shape is HIGH lock-in (every line written in the old shape is a migration liability), while a 500-line refactor behind a stable interface may be none. The 2026-06-10 review-proportionality plan hit this exactly: the governance ledger was first designed mechanism-first ("append review records to a file") and marked **High confidence** — but the cheapest discovery question for any data product, *"what questions must this data answer over time?"*, was never asked. The user's unprompted analytics requirements (model efficiency per ROLE, findings density per code path, wall-clock per phase per feature, cross-project aggregation) restructured the schema from review-shaped to an event-envelope shape — a structural choice that retrofitting after lines exist would cost a migration. A second trap rode along: user **endorsement of an analysis/diagnosis is not a requirements confirmation for the artifacts that implement it** — "this is fantastic, build all five" confirmed the cost diagnosis, not the data product's spec. Fix-shape (and the methodology tripwire shipped with review-proportionality ch.01): a chunk introducing any persisted format/schema/ledger must enumerate, in the plan, the questions the data must answer — elicited from its future consumers (usually the user), not inferred from the mechanism — before designing fields; and judge every lock-in trigger by reversal cost, never by LOC. Cheap accommodations that make this survivable when a question is missed anyway: per-line `schema_version`, envelope/payload split, consumers skip unknown kinds/fields, a structural single-writer (validate at append) instead of prose-instructed serialization. Caught at plan stage by the user, before any code — which is the plan-review layer working, but the elicitation should have happened at authoring. Relates to Requirements Precede Code (#6), Reasoned Decisions (#4), Bring Expertise (#7 — the builder should have asked), and Honest Confidence (#5 — "High" meant mechanism-confidence, not requirements-confidence).

## A test asserting the framework repo's OWN state instead of the propagated contract gives false coverage — assert the contract that reaches consumer repos

The plugin's defaults reach onboarded products only through **canonical carriers**, never through this framework repo's own files: gitignore defaults via `lib/core.py::GITIGNORE_ENTRIES` (written into a product `.gitignore` by `update_gitignore` on onboard/doctor) and its import-light inline mirror `bin/prawduct-hook::_SESSION_GITIGNORED_PATHS` (the `_untrack_session_files` set); format legends via `templates/`; default-behavior changes via `methodology/session-digest.md`. Dogfooding this repo creates a blind spot: state the framework repo *also* generates (because the plugin is active here too) can be made quiet by a hand-edit to *this* repo's tracked files, which does nothing for products. The work-model vocabulary index (PR #71) is the canonical instance. Two hooks generate `.prawduct/.work-model-index.json` on every session in *every* `.prawduct/`-bearing repo (SessionStart `build-index`, UserPromptSubmit `user-prompt-submit`). PR #71 correctly intended it ephemeral/gitignored and added the ignore line to this framework repo's own `.gitignore` (line 25) — but never to `GITIGNORE_ENTRIES` or `_SESSION_GITIGNORED_PATHS`. Result: `update_gitignore` never wrote an ignore rule for it into any product, so every onboarded repo regenerated the file each session and carried it as permanent untracked noise (the reported symptom). The damning part is the *test*: `tests/test_work_model_hooks.py::test_index_is_gitignored` existed and **passed continuously** — because it asserted `(ROOT / ".gitignore")`, i.e. *this repo's* file, the one surface that has no bearing on products. A green guard test on the wrong surface is worse than no test: it reads as "covered." Discovered 2026-06-25 from a user report that the file was noisy in both this repo (where it's actually fine) and consuming repos (where it wasn't). Fix: add `.prawduct/.work-model-index.json` to both contract lists (`TestSessionGitignoreMirror` pins them in sync); existing products self-heal — `update_gitignore` adds the line next session, and `_untrack_session_files` `git rm --cached`s it if a repo already committed it. The regression net was rebuilt to assert the *contract*: `test_index_is_in_gitignore_contract` (the entry is in `GITIGNORE_ENTRIES`) and `test_update_gitignore_writes_index_line` (end-to-end — a freshly reconciled product `.gitignore` contains the line). Fix-shape, general: when a feature ships any propagated default (an ignore line, a format field, a digest behavior), write the regression test against the canonical carrier AND an end-to-end propagation into a fresh `tmp_path` product — never against the framework repo's own dogfood copy; if the only assertion touches a file under this repo's root, ask "would this still hold in a *product* repo?" and if not, the test is false coverage. Same root shape as [[A format's schema legend lives in `templates/` (scaffold-only) — adding an optional field reaches already-onboarded repos only via a migrate/triage *refresh* step, not the template]] — anything living only in the framework repo does not reach onboarded repos. Relates to Tests Are Contracts (#1 — a contract test must test the contract, not the producer's private copy), Validate Before Propagating (#15), Complete Delivery (#2), and Clean Deployment (#10 — dev-time dogfood state masking a product-facing defect).

## When building from a review/audit artifact, verify each cited gap and fix-instruction against HEAD before planning — the artifact's file-state claims aged the moment it was written

Full context (2026-07-02, gate-noise / GOV-7T2M, Wave 1 Plan A of the efficiency-review fix
program): The parent artifact `framework-efficiency-review-2026-07-02.md` carried two claims
that were wrong by build time. (1) "residual gap: review protocols still let reviewers eyeball
staleness" — but PR #104 (2026-06-22, TST-4K2P cluster) had added "that exit code is the *only*
freshness signal" to both `skills/critic/review-protocol.md:41` and `skills/pr/review-protocol.md:56`
ten days before the review was written; the audit agents missed it. Found via
`git log -S 'freshness signal'` on the cited files before planning. Descoping it avoided adding
a duplicate line to a protocol sitting at its 3350-token ceiling. (2) The literal instruction
"drop refactor/rename/redesign/rework/remove/replace from REQUIREMENT_VERBS" ignored the set's
second role: `find_orphan_terms` exempts these verbs from being reported as orphans, and a
3-line probe showed rename/redesign/rework are NOT absorbed by the `_in_floor` frequency floor —
a bare drop would make "rename the FooBar module" report *rename* itself as the orphan (a brand-new
false-positive class in a fix whose whole purpose was killing false positives). The fix became a
two-set split (REQUIREMENT_VERBS for requirement-shape, MAINTENANCE_VERBS added to the orphan
exemption union). Why it matters going forward: ~13 more backlog items point at this same parent
artifact (waves 1-3); every one of them should re-verify its cited file:line evidence and
empirically probe the predicate it changes before planning. The artifact remains the requirement's
*evidence and rationale*; it is not a statement of current file state nor a validated design.

## When a plan sets a quantitative reduction/size floor over a corpus you cannot shrink by dropping content, derive the floor from a per-file compressibility sample — not a global intuition

Context: the prose-diet feature (MET-3Q8V) targeted the ~37k est-token governance cycle-load
set. The build plan's Success clause set a floor of ≥45% reduction, targeting 50%, alongside a
hard no-drop constraint (no rule, gate semantics, or checkable bar may be lost — Complete
Delivery outranks the number). The 45–50% figure came from a global intuition that priced
*triplication* — the mode×type matrix and stance prose repeated across three surfaces — as the
bulk of the mass.

What actually happened across three chunks: structural single-sourcing + editorial compression +
folding five instruction surfaces landed the corpus at 36,991 → 25,789 est tokens, **−30.3%**,
measured with the test suite's `words × 1.3` estimator. The cumulative Critic flagged this as
BLOCKING against the ≥45% floor. Root-cause, chaining the whys: (1) single-sourcing the
triplicated matrices recovered only ~3–4k est tokens, not the assumed bulk — the repetition was a
small fraction of total mass; (2) the corpus's true composition is rule-dense — single-statement
rules, irreducible behavior tables, and deliberate weaker-model anchors that the no-drop
constraint forbids compressing further; (3) ~2.6k est tokens of in-set two-reviewer chain
machinery had already been carved out to a separate backlog item (review Overbuilt #4) by the plan
itself; (4) the same review program had earlier certified `review-protocol.md` already lean —
evidence the 50% prior had ignored.

Resolution: the owner chose to amend the Success floor to the honest achieved −30.3% rather than
direct a further compression pass (whose realistic yield was ~3–5 more points, approaching rule
loss). This confirmed the provisional lesson recorded at chunk close: a reduction floor set above
honest reach, over a corpus with a no-drop constraint, is not a stretch goal — it is a latent
Complete-Delivery violation that detonates at close-out, when the only ways to "hit the number"
are to drop a load-bearing rule or to miss your own acceptance criterion. The number is a
*measurement of rule density*, not a measure of remaining waste.

The cheap prevention: before writing a quantitative reduction floor under a no-drop constraint,
take a per-file compressibility sample — pick 2–3 representative files, estimate honest achievable
compression on each (what's redundant vs. what's irreducible rule text), and derive the corpus
floor from that bottom-up estimate. Record the floor as a vetoable assumption with its derivation,
not as an aspiration handed down from a global "should be halvable" feel. Relates to Complete
Delivery (#2 — the number must never outrank preservation), Reasoned Decisions (#4 — a floor needs
a derivation), Honest Confidence (#5 — distinguish a measured estimate from an intuition), and
Proportional Effort (#11 — a sampling step is cheap insurance against a close-out trade-off).

## When a governance checkpoint verifies a required side-effect happened, put it OUTSIDE the control flow that produces the side-effect

**Context (critic-persistence-redesign, 2026-07-09/10).** Claude Code v2.1.198 flipped Agent
subagents to background-by-default. The Critic's final/cumulative coordinator was a `context: fork`
skill that dispatched 3 reviewers and *resumed inline* to persist (write findings → ledger anchor →
critic-end). Under background-by-default the fork returns before the resume, so the writeback never
ran: reviews were silently lost, surfacing only later as a check-cumulative-critic deadlock (CRT-9K7T).

**The trap.** A prior hardening (gate-friction-batch Chunk 03) added a HEAD-coverage assertion
INSIDE critic-end. But the failure mode is "critic-end never reached" — so the assertion, living
inside the flow that fails, could never fire on that flow's own failure. Verifying persistence at
the skippable step is worthless when the step is skipped.

**The fix (Option A).** Decouple model judgment from deterministic persistence:
1. The floor is OUTSIDE the flow — a lingering `.critic-active` marker caught at session end
   (a state critic-end would have cleared). This is Chunk 01, built first, on purpose.
2. Persistence is a pure function of durable on-disk state — reviewers write partials; a
   deterministic, idempotent, fail-closed `critic-consolidate` merges them (NO model in the write
   path), so no fork/background/resume behavior can bypass it.
3. Event-driven fast path (SubagentStop → consolidate) for latency, but the session-end backstop
   is the enforcing floor — a two-tier design that degrades gracefully if the fast path misfires.

**Process notes worth keeping.**
- Verified the post-cutoff harness facts (background-by-default date, SubagentStop existence,
  plugin `agents/` auto-discovery, agent-type/matcher semantics) via `claude-code-guide` + empirical
  reasoning, NOT recall — the whole fix hinged on facts recall would have gotten wrong.
- Honest limitation (Principle 5): the harness firing the SubagentStop hook and resolving the
  plugin `critic-reviewer` agent type can't be exercised until the plugin ships this branch (the
  session runs the plugin from cache, not the working tree). Captured as operator-verification
  VRF-002; the command bodies + consolidation core are exhaustively unit-tested meanwhile. When the
  thing under test is the installed governance machinery itself, "self-validating" needs the fix to
  be *live* first — flag the gap, don't fake the validation.
- Token-budget friction: adding a subsystem's prose to a lean instruction file (review-protocol.md,
  3350-token ceiling) meant RELOCATING record detail to review-cycle.md, not expanding — the
  prose-diet lever, and the budget test earned its keep by forcing it.

## When developing requirements to replace a working system, sweep every consumer's actual usage before finalizing — reported pain is a hypothesis, and the loudest complaint is often not the deepest failure

Full narrative (2026-07-13, backlog-service requirements discovery). The owner asked for
requirements to move the backlog out of git, framing the pain as slow LLM-mediated CRUD, merge
conflicts, and git-coupled edits. All three were real and independently corroborated (BKL-7M4Q
crash corruption; discodon's 454 backlog.md commits with 47 merges / 38 conflict-mentioning
commits; the incoming-bugs drop-box). But a read-only sweep of all 16 local checkouts of the 8
backlog-bearing projects (scriob, scriob2, discodon + 5 copies, hallucinote ×2, cordyceps,
trenchant, puzzles, metallm, prawduct) produced a different ranking:

1. Stale item state / trust collapse — hallucinote hit two `stage: ready` items 60–80% done in
   one session; a scriob scrub found four completed items sitting in Open; an upstream report
   counted three ready items 60–100% shipped; discodon's EVL-D8K2 described a destructive live
   code path as "permanently dead" (dangerously inverted); discodon ran a 48-agent
   assessor+adversarial-verifier workflow over 39 items because item text could no longer be
   trusted. Consumers now re-verify premises in code before building — universally.
2. Stale views across checkouts — the wt-discodon-backlog worktree showed 66 closed items as
   Open and was missing 65 newer ones; discodon-brooks2 held SOL-K3PN found nowhere else.
   Cross-copy divergence was ~98% staleness, ~2% genuine fork.
3. Only then: merge conflicts, unsafe mutation, git coupling — the originally-reported pains.

Consequence: the requirements doc gained a Truth & freshness group (TF1 single live view, TF2
first-class verification stamps, TF3 mass grooming as supported workload) that no tracker
provides out of the box and that the original sketch never implied. Also observed and folded in:
per-project soft vocabularies (scriob's `kind:` on 158 items, `owner:`, `reverted-by:`, stage
values `discovery`/`built`), zero-ceremony tier (metallm: 5 items, no metadata), high-cardinality
ad-hoc ID prefixes (27–58/project), and bulk-read grooming workloads that must be served from a
local cache, not a rate-limited API.

Method notes that made it work: requirements were drafted from the problem BEFORE reading the
vendor research (two parallel web-research agents ran meanwhile), so GitHub/Linear capabilities
informed a separate adopt/build/buy section rather than anchoring the requirements themselves;
and the sweep was one read-only background agent — cheap insurance against designing to the
complaint instead of the disease.

---

## Re-attempting a mechanism rejected for a false-positive class: make it ADDITIVE and relax-only (tree-validated test-evidence freshness, 2026-07-14)

Context: the deferred kernel-v3 §4 item ("test evidence on the store") had three live frictions —
restart false-stale, doc/metadata-edit re-run, chronic per-session re-run — all rooted in
`tests_are_current` keying freshness on `timestamp >= .session-start` (WHEN the run happened)
rather than WHAT tree it ran against. The obvious fix ("stamp a tree hash, compare it") was the
*exact* direction rejected twice before: the content-hash fingerprint (HEAD SHA + sha256 of dirty
files, v1.3.4→v1.3.8) and `git_sha` (v2.1.8, TST-4K2P) — both rejected for chronic false-STALES,
a standing and explicit rejection (COV-3R9K, kernel-v3 R10, `coverage_algebra.py:66`).

What made the third attempt land where two failed:
- **Additive, relax-only shape.** Not "replace the timestamp with a tree check" but "current iff
  session-fresh OR tree-valid." A disjunction that only moves evidence stale→fresh cannot, by
  construction, produce a false stale — the failure mode of both predecessors. The immunity is a
  property of the shape, not of implementation care.
- **Path-classification, not content-hashing.** The clause diffs two git tree objects
  (`capture_tree` / `tree_diff`) and filters with `is_judgeable_path` — it never hashes file
  bytes, so it honors the standing "paths classify, contents don't" rule. Metadata churn (the
  record's own `.prawduct/.test-evidence.json` write, doc edits) filters out; the verbatim-commit
  case survives because the *judgeable-scoped* tree is preserved even though the raw tree SHA
  shifts when `record` writes the evidence file — the stronger, real invariant.
- **`evidence_tree` is a gate-consumed object, not an eyeball field.** `git_sha` failed partly
  because review agents *read* it and inferred staleness from a lagging SHA. `evidence_tree` is
  only ever consumed by the gate's tree-diff — no human/agent reads it as a position signal.

Build-time refinements the design predicted imperfectly: dropped the proposed `head_tree` field
(no consumer — the clause needs only `tree_diff(evidence_tree, current_tree)`), and excluded
`--from-counts` from capture (hand-typed counts carry no machine tie to the working tree; this
also preserved the standing `test_restamp_flips_stale_record_to_current` contract). Validation
matrix: 11 cases (5 relax-only current, 5 judgeable-change stale, 1 `--from-counts`-stays-stale)
plus 2 monkeypatch fail-toward-stale unit tests; full suite 1727 passed. The env-drift tradeoff
(the incidental per-session re-run that catches dep/flake drift with no file footprint) was
explicitly accepted by the owner as an expensive, undesigned safety net.
