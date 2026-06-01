# Learnings

Active rules from this project's development. Surfaced via the `/learnings [topic]` skill — topic headers shown in the session briefing for ambient context. Entries use "When X, do Y because Z" format. Full context in `learnings-detail.md`.

---

## Test subprocesses: HOME=tmp_path leaks Python's pyc cache into the test repo

When a test invokes a Python subprocess via `subprocess.run(env={"HOME": str(project_dir), ...}, cwd=str(project_dir))`, Python's xcode-shipped interpreter writes `.pyc` cache files to `$HOME/Library/Caches/com.apple.python/...`. If `$HOME == cwd == git repo root`, `git ls-files --others --exclude-standard` then returns ~50 untracked cache files, inflating diff counts and triggering scope-widening / status-pollution failures in helpers that use it. Fix: set `HOME` to a directory OUTSIDE the test's git repo (e.g., `project_dir.parent / f"{project_dir.name}-home"`). Discovered v1.5.1 Chunk 03 (TestComputeVerifyResolutionsScopeSubcommand). Relates to Structural Awareness (#21).

## "Structurally enforced" requires verifying the harness actually enforces it

When claiming a constraint is "structurally enforced" by a config/sandbox/permission system, verify the enforcement before claiming it in change-logs or memory rules. The v1.5.1 Chunk 02 `!Bash(pytest*)` deny patterns added to skill `allowed-tools` were claimed structural but the Critic ran pytest unimpeded one chunk later — the harness allows `Bash(python3:*)` at project level which overrides skill-level `!`-deny. The prose claim "structurally enforced" survived only until the next chunk's Critic. Negative-path probe (write a test that asserts the constraint blocks the forbidden invocation) before claiming. Discovered v1.5.1 Chunk 04 Critic. Relates to Honest Confidence (#5) and Validate Before Propagating (#15). (v1.8.0 Chunk E added `test_no_allow_pattern_permits_pytest` — the probe this rule asked for — backing the pure-allow-list claim for the Critic.)

## When a deliberate change turns a passing test red, renegotiate the contract in the open

When you intentionally change a documented behavior and an existing test fails because it encoded the OLD behavior, do NOT silently relax or delete the assertion. Rename the test to the new contract, re-document why in the docstring, invert the assertion, and record the rationale (commit/change-log). "Fix the code, not the test" (Principle 1) assumes the test encodes CORRECT behavior — when the test encodes the very thing you're deliberately removing (an every-session nag, or a safety hole asserted as "legitimate"), the test is a contract to renegotiate transparently, not a bright line to respect blindly. Keep any still-valid invariant explicit (changing template-drift to fire-once, also assert the user's place-once file is still never overwritten). Recurred ~20× across v1.8.0 chunks B/C/E. Relates to Tests Are Contracts (#1) and Reasoned Decisions (#4).

## A behavior change isn't done until every artifact that DESCRIBES it is updated

When you change behavior that a synced/templated/documented artifact describes — a briefing format, what files ship to product repos, a CLI's output — grep for every place that describes it, not just the code that implements it. The v1.8.0 cumulative Critic caught two misses in one bundle: the product CLAUDE.md template still described the pre-diet briefing, and the product-layout diagrams still omitted the now-shipped `tools/lib/`. Same blind spot both times: changed the behavior, missed the descriptions. The independent cumulative review is the fresh-eyes pass that catches doc-vs-behavior drift the builder is blind to. Relates to Living Documentation (#3) and Independent Review (#14).

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

When wrapping a multi-chunk bundle, expect the cumulative-Critic pass to surface ≥1 finding the chunk passes missed — mechanisms introduced in chunk N often misbehave only against prose in chunk M. Plan a remediation slot before `/pr create` rather than treating the cumulative pass as a formality. Because the lens differs: chunk-Critic diffs the chunk's own commit; cumulative-Critic diffs `merge-base...HEAD` and catches helper-vs-prose interactions invisible at chunk scope. Wave 1's `_looks_like_file_path` (Chunk 02) false-positived on slash-commands in Chunk 01's prose — only the cumulative pass saw both at once. Relates to Independent Review (#14).

## Auto-enable belongs with visibility, not with enforcement

When deciding whether a new opt-in feature should silently auto-enable on sync, ask whether flipping it ON would cause the next PR to **block** unexpectedly. Visibility surfaces (derived views, additional briefing fields, schema fields the writer fills in) auto-enable safely — at worst the user sees new output. Enforcement surfaces (Critic BLOCKING checks, gates that refuse `/pr create`, hooks that exit non-zero) must be explicitly invoked via `migrate --enable-<feature>` so the workflow commitment is visible before it bites. Chunk 07's F1 derived-views auto-enabled silently on sync ("users should get views for free"). Chunk 10's F4 coverage *deliberately* broke the pattern — a silently-flipped `coverage_required: true` would BLOCK the user's next PR for reasons they didn't agree to. Same shape (one-shot manifest flag, additive YAML edit) but opposite invocation policy. Relates to Visible Costs (#9) and Governance Is Structural (#22).

## Removing a mechanism requires removing its name too

When deprecating or removing a mechanism, grep for the mechanism's **name** in active prose and update terminology in the same change — not in a follow-up cleanup. Because lingering names mislead readers into looking for code that doesn't exist; the resulting confusion is worse than not removing the mechanism at all. The "fingerprint" tree-hash freshness mechanism was removed pre-v1.4, but the word survived in 5 active sites (shebang docs, docstrings, lockstep build-governance prose) until Chunk 10 caught them — a year of reader-confusion gap. Fix-shape: each PR that removes a mechanism includes a `grep -rn` pass for its name(s) across `tools/`, `templates/`, `methodology/`, `agents/` and updates each hit to either describe what replaced it or annotate it as historical. Relates to Living Documentation (#3) and Close the Learning Loop (#18).

## Build-plan fields use `**Title Case:**`, not snake_case

When adding a new build-plan field, format the label as `**Title Case:**` (bold, words-with-spaces, colon) — matching `**Type:**`, `**Critic mode:**`, `**Requirements Confidence:**`, `**Acceptance criteria:**`, `**Done when:**`. Snake_case (`foreign_api:`, `coverage_required:`) is the YAML-key namespace in `project-state.yaml`, a different surface. The methodology's prose form must be string-identical to the template's label except for the `**...**` bolding — so the Critic's substring-match finds real plans. Wave 1's F8 conflated the two namespaces (`foreign_api:` in prose, `**Foreign API:**` in template) and the Critic-check substring never matched a real plan. Relates to Coherent Artifacts (#13).

## Submodule and same-name function in __init__ shadow each other

When a `lib/__init__.py` does `from .foo import foo` (re-exporting a function whose name matches its submodule), attribute access `lib.foo` returns the function while `sys.modules['lib.foo']` still holds the module — `import lib.foo as alias` resolves to one or the other depending on context, and `monkeypatch.setattr(alias, "name", ...)` raises `AttributeError` when it lands on the function. Because Python's `from package.submodule import name` registers both in the parent's namespace; the later import wins for attribute lookup. Fix-shape: use the `_cmd.py` (or other) suffix that every other lib module already uses (`migrate_cmd.py`, `sync_cmd.py`, `init_cmd.py`, `validate_cmd.py`, `views_cmd.py`) — the convention isn't aesthetic, it prevents this collision. Caught in Chunk 13 when test monkeypatches failed; renamed `audit_learnings.py` → `audit_learnings_cmd.py` before commit. Relates to Coherent Artifacts (#13) and Reasoned Decisions (#4).

## Detection of structural characteristics should not rely on mechanistic surface markers

When classifying whether a project has a structural characteristic (uses LLM inference, has human interface, runs unattended, sensitive data, multi-process), use *what the project's correctness depends on* — not surface markers like import statements, hostnames, or filename patterns. Because surface markers miss cases where the same structural feature manifests differently. Prawduct's own Open 1 empirical-detection survey initially classified itself as "not LLM-using" because the framework's executable code has zero LLM SDK imports, zero LLM-API hostnames, and zero message/role/tool-use shapes — but the framework's primary deliverable IS prompts (skill markdown files loaded by an external Claude Code runtime), so its correctness fundamentally depends on LLM behavior. The mechanistic test missed Category B (runtime-instruction) projects entirely until the user surfaced the gap. Fix-shape: every structural-characteristic detector answers "what determines correctness here?" first, then lists surface signals as *evidence* for that structural question — not as the question itself. The distinguishing feature for the LLM case turned out to be "prompts-as-code (Python builds API request bodies) vs prompts-as-content (markdown loaded by an external runtime)" — both correctness-depends-on-LLM, neither captured by SDK enumeration. Discovered 2026-05-28 during prompt-management v0.1 → v0.2. Relates to Structural Awareness (#21), Honest Confidence (#5), and Bring Expertise (#7).

## Shared "answer" state and personal "nag" state belong in separate stores

When designing state about ongoing concerns (advisories, follow-ups, todos), separate two semantically distinct kinds of state: the *answer to the question* (committed, team-shared — e.g., `project-state.yaml`'s `uses_llm_inference: true`) and *have I personally dealt with this nag?* (gitignored, per-clone — e.g., `.advisories.json`'s dismissed list). Because conflating them gets both directions wrong: either everyone's dismissals leak across clones (personal task state shouldn't propagate to teammates) or no resolution propagates (when a teammate's commit answers the structural question, the answer should auto-clear the nag for everyone on next pull, not require each developer to dismiss separately). The post-sync advisory infrastructure (`documentation/post-sync-advisory-spec.md` v0.2) made this explicit: probes declare both a *trigger condition* (reads code state — "should I ask?") and a *resolution condition* (reads `project-state.yaml` — "has the team answered?"); active state lives in the gitignored nag log, settled facts live in the committed answer store. Discovered 2026-05-28 via Q2 in the advisory spec when the naive single-store design would have produced wrong cross-clone behavior. Generalizes beyond advisories — any feature that tracks "did the team agree on X?" + "have I personally followed up?" benefits from this separation. Relates to Coherent Artifacts (#13) and Structural Awareness (#21).

## Framework ownership follows the write strategy, not just registry membership
<!-- prawduct-learning: confirmations=1; created=2026-05-19; sentinel=tests/test_prawduct_sync.py::TestAutoCommitSafety::test_user_authored_place_once_edits_treated_as_wip -->

When defining "the framework owns this file" sets — for auto-commit, hash-based change detection, or "is this user WIP or framework drift" partitioning — the discriminator is *whether the framework overwrites the file on every run*, not "is the file in any registry the framework knows about." Template / block-template / always-update / merge-settings strategies overwrite each sync; place-once strategies create once and never re-touch. The two have opposite ownership semantics after first creation, even though both lists live side-by-side in `core.py`. Because Chunk 11's first-pass `_framework_known_paths` included `PLACE_ONCE_TEMPLATES` and `PLACE_ONCE_COPY` (`.prawduct/change-log.md`, `.prawduct/backlog.md`, `tests/conftest.py`), a user chunk-close append to change-log.md would have been swept into the auto-commit's `chore(sync):` marker — re-creating the exact co-mingling F5a aims to prevent. Fix-shape: when building "framework-managed" sets, derive them from the *strategies that overwrite* (the manifest's `files` dict, sourced from `MANAGED_FILES`), not from "every path the framework has ever placed." Place-once is genuinely place-once — trust the contract. Relates to Reasoned Decisions (#4) and Coherent Artifacts (#13).

## A leftover marker is not an in-progress signal — and a test using the canonical marker leaves the real-world branch untested

When detecting external-tool state from filesystem markers (a `.git/` ref, a lockfile, a PID file), check whether the tool *removes* each marker when the condition ends — a leftover artifact is not an in-progress signal. `_git_op_in_progress` treated `.git/REBASE_HEAD` as a live rebase, but git does **not** clean up `REBASE_HEAD` when a rebase ends (it lingers until the next rebase overwrites it), unlike `MERGE_HEAD`/`CHERRY_PICK_HEAD`/`REVERT_HEAD` which git *does* remove — so the stale ref produced a phantom "rebase in progress" on every downstream session and could block auto-sync. Prefer the tool's own authoritative test: the `rebase-merge`/`rebase-apply` directory check (what `git status` uses) was already present and correct; the ref check was a redundant false-positive source. Two compounding lessons: (1) the existing regression test simulated a rebase with the `rebase-merge` *directory* — it passed via the correct branch and never exercised the buggy `REBASE_HEAD` *file* branch, so the bug only ever fired in the real world; when a detector has multiple input paths, test each one with the messy inputs real systems produce (leftover refs), not just the clean canonical marker. (2) The misdetection was cached into `.prawduct/.sync-pending` and replayed verbatim every session, turning a one-time false positive into sticky noise — a derived/cached blocker that never re-evaluates makes any transient false-positive permanent. Discovered 2026-06-01 from a Hallucinote bug report. Relates to Tests Are Contracts (#1), Root Cause Discipline (#16), and Honest Confidence (#5).
