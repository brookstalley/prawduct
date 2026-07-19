# Learnings

Active rules from this project's development. Surfaced via the `/learnings [topic]` skill — topic headers shown in the session briefing for ambient context. Entries use "When X, do Y because Z" format. Each entry's full narrative lives in `learnings-detail.md` under the same heading — keep narrative THERE, not here.

---

## When committing a consequential decision under momentum, do the cheapest check that could change it FIRST (read the mechanism before tuning it, search current practice before working around a behavior, re-read the artifact you're relying on before contradicting it) — because generation has a short head and a long tail: the plausible unchecked answer costs nothing now and detonates downstream, while retrieval is minutes, full stop

## When a skill/runbook has the model do a read-then-write CLI dance (read X's field, then write with `--if-<field>`), verify the READ actually SURFACES the field the write consumes — a write flag EXISTING in the CLI is not the same as its input being OBTAINABLE from the paired read, and static prose-vs-code review checks only the former; dogfood the handoff live (or write a read-then-feed test), because that gap survives even a clean multi-reviewer review

## When reconciling a backlog item a PR *partly* shipped, read ALL that PR's build-plan chunks before declaring any leg still open — a multi-chunk PR routinely lands the docs/methodology/skill leg in a LATER chunk than the code chunk, so crediting only the code chunk falsely marks the item open and sends the next picker to rebuild shipped work (the shipped-but-not-removed drift BKL-8T3W targets); diagnostic before writing requirements: read the delivering plan's `## Build Chunks`, or `git show --stat <merge>` for the doc paths the "open" leg names

## When compacting or migrating a file that tooling parses, classify every span by its CONSUMER before moving it — machine-read metadata (a parsed comment, a `sentinel=` tag, a status marker) is not "narrative" and must stay where its reader looks, because a content-loss guard that only proves "prose is preserved elsewhere" is blind to metadata it silently relocates or drops

## When a session finds uncommitted work in a worktree it did NOT launch in, treat it as another session's territory and leave it alone — a session works only in its own worktree, because sibling WIP belongs to a possibly-live session and adopting it collides with that work and writes into the clone-shared governance state

## When surfacing a batch of model-proposed candidates for owner confirm-or-correct (norm ratification, backlog reconcile, findings triage), triage by decision-worthiness FIRST — surface the few that carry a real fork individually, bulk-confirm the obvious rest, never a flat dump — because a flat list at scale buries the real decisions and trains the owner to rubber-stamp, defeating the review it exists to be

## When writing a durable artifact (code comment, docstring, long-lived spec), never anchor its meaning to an ephemeral build identifier — carry the *why* inline, because build plans are deleted after completion and every project has many "chunk 03"s

## A red version/release-hygiene test on a feature branch is often a branch-STALENESS symptom, not a doc defect — check distance from the integration branch before patching the changelog

When a feature branch fails a release-hygiene test (e.g. `test_changelog_has_current_version_entry`: `VERSION`/`plugin.json` say vN but `CHANGELOG.md`'s top entry is vN-1), check the branch's distance from its integration branch BEFORE editing the changelog. A branch cut long ago and never reconciled can sit many releases — a whole major version — behind (here: cut at v2.0.1, **45 commits / one major behind `develop` @ 3.0.4**); its `VERSION` was bumped by an ancestor `release-prep(vN)` commit, but the matching CHANGELOG headline landed on the integration branch, not this one. Patching the changelog on the stale base FABRICATES divergent history (the entry already exists downstream) and keeps the work under an obsolete governance model (a Critic finding here was recorded under the pre-v3.0.0 single-slot data plane). Root-cause fix: merge the integration branch in — `VERSION`/`CHANGELOG`/`plugin.json` reconcile by auto-merge and the current review data plane comes with it. Diagnostic before ANY changelog edit: `git rev-list --count HEAD..<integration>` + `git merge-base <integration> HEAD` — many releases behind ⇒ reconcile, don't patch. A Critic can correctly flag the red suite yet read the symptom ("add the vN headline"); the reviewer sees the tree, not the branch topology, so this diagnosis is the builder's. Full narrative in `learnings-detail.md`. Discovered backlog-service Chunk 01 close-out (2026-07-17). Relates to Root Cause Discipline (#16), Coherent Artifacts (#13), and the sibling stale-base gate diagnostic below.

## When `check-cumulative-critic` reports `uncovered` on a branch whose code you know was reviewed, suspect a stale base before running a fresh review — the gate anchors to `origin/<base>` by design, so unpushed integration commits drag already-shipped work into the required span

## When developing requirements to replace a working system, sweep every consumer's actual usage before finalizing — reported pain is a hypothesis, and the loudest complaint is often not the deepest failure

## When a fail-closed validator guards a model-written field, tolerate the natural encoding variant — reserve the hard fail for genuine ambiguity, because incidental strictness at a model-output seam is a latent fail-close

## When the success path threads advisory/audit data through a result envelope, add it to EVERY error-return path too — in an envelope-heavy codebase the error return is built by a *different* constructor (here `core.from_transport_error` vs `core.ok(data, warnings)`) that has no slot for the field and silently drops it; the damage is permanent, not cosmetic, when the datum is one-shot (a self-heal audit line that won't re-run on resume, so it can never be re-emitted). Second instance of this class in backlog-service import (BKL-3K9N rate-limit path, BKL-9V2W TransportError path — both funnel through one outer `except`). Grep the error/exception returns whenever you enrich a success envelope.

## When designing any flow step that records status or bookkeeping, make it ride IN the PR that does the work — a step that can only run post-merge on the integration branch is structurally broken for protected-branch consumers

## When a governance checkpoint verifies a required side-effect happened, put it OUTSIDE the control flow that produces the side-effect — a check inside the fallible flow can't catch that flow's own skip

## When building from a review/audit artifact, verify each cited gap and fix-instruction against HEAD before planning — the artifact's file-state claims aged the moment it was written

## When a backlog item's `refs:` names several surfaces, treat them as candidates and let the mechanism pick the surface — implement only where the condition can actually manifest (and grep for existing coverage first), because mechanically touching every listed ref adds dead or duplicative surfaces the item never needed. STH-3R8K listed SessionStart `digest.py`/`banner.py` alongside the Stop hook, but SessionStart runs in the launch dir *before* any mid-cycle worktree move, so it provably cannot observe the redirect — the Stop path was the only load-bearing surface, and a SessionStart line would have duplicated BRF-6K2D. Descope the dead surfaces explicitly in the item note (Principle 2 — a deliberate scope call, not a silent drop). Relates to Scope Discipline (#12) and [[When building from a review/audit artifact, verify each cited gap and fix-instruction against HEAD before planning]].

## When you add an ingest/IO surface to a platform-agnostic framework, expose the minimal data primitive — not one ecosystem's file format — or you silently lock out the toolchains the agnosticism promised

When a framework brands itself language/platform-agnostic, a core ingest surface must not be gated on one ecosystem's interchange format. test-evidence `record` accepted results ONLY as JUnit XML (default pytest, `test_command:` requiring `{junit_xml}`, `--from-junit`) — fine for the many stacks that emit JUnit, but it left embedded/HIL/bespoke toolchains with no paved on-ramp (hand-write the JSON, or fake a JUnit file). The fix is to expose the MINIMAL primitive the gate actually needs — for test results, pass/fail/skip counts (`--from-counts`) — so any toolchain participates without writing an adapter. It surfaced only because the user asked "are we breaking non-Python/embedded users?"; so when adding an ingest path, ask up front which real toolchains CAN'T produce its format. Corollary (same cycle): an upstream bug report's stated root cause is a HYPOTHESIS — the scriob report blamed a `git diff base...HEAD` membership shift the producers don't do (they diff base→worktree, commit-invariant); verify against source before designing, because the real fix was docs + this on-ramp, not the report's suggested content-hash (which a deliberate prior decision had rejected). Relates to Bring Expertise (#7), Honest Confidence (#5), Proportional Effort (#11), Verify-don't-guess, and [[backlog]] COV-4M2J (the Python-only coverage-floor residual).

## When you add a fallback lookup INSIDE a per-item loop, amortize it AND make it a no-op on the common path — a naive fallback that fires on every miss is O(N²) at scale, and the fresh case is all-misses

A spec that says "make X a fallback authority in `_find_by_key`" reads as "scan on every label-miss" — but the importer calls it once per record, and on a FRESH import every record misses the label (nothing exists yet), so a per-miss full-issue scan is O(N²), invisible in the unit suite and only biting at ~200-item migration scale (the same full-scan cost BKL-2K8V already flagged). The fix (BKL-4W7H `_AliasIndex`): build the fallback index ONCE, lazily on the first miss, and cache it for the run — a clean import/resume where every label is intact never scans at all; a drifted re-import pays exactly one scan. Pin the zero-cost property with a test that asserts NO unfiltered `list_issues` on a clean re-run — a silent perf regression here won't show in the unit suite. Corollary (same cycle): when a fix must satisfy two named gaps (here read-resolution AND import-idempotency), look for the ONE mechanism that closes both — restoring the `id:PFX` label on the fallback hit self-heals the skip-authority AND makes the alias resolve again, because the label was both keys. Relates to Proportional Effort (#11), Tests Are Contracts (#1), and [[backlog]] BKL-2K8V (the ~12s full-scan pick floor).

## When a test injects a fixed clock, EVERY actor in the scenario must share that clock domain — one real-clock participant (a CLI front, an un-injected default) turns fixed-timestamp + TTL into a scheduled deterministic failure at stamp+TTL wall time

A claim-conflict test stamped the holder's claim via `core.claim(now=NOW)` (fixed 2026-07-17T12:00Z) but drove the challenger through `cli.run`, which reads the real clock. The 24h claim TTL made the test green until 2026-07-18T12:00Z and deterministically red after — the challenger's "conflict" became a LEGAL TTL-reap of an expired claim. The product was correct; the test mixed clock domains, and the failure surfaced as an apparent regression in an unrelated PR-prep run. Rule: pick ONE domain per scenario — inject `now` into every participant, or drive every participant through the real clock (here: both claims via the CLI). Sweep test: grep each test file mixing `now=<fixed>` with a front that defaults to wall time. Discovered PR-prep after the develop merge (2026-07-18); the sibling query/governance suites were single-domain and clean. Relates to Tests Are Contracts (#1 — the fix preserved the contract, changed only the clock plumbing), Root Cause Discipline (#16 — "passed yesterday, fails today, no code change" points at time, not the merge), and [[When validating a CLI's JSON output, feed the tool the raw bytes (direct pipe or file) — never `echo "$captured" | jq` under zsh, whose `echo` interprets `\n` and turns valid JSON into a false "malformed output" finding]] (both: the harness between test and product lied, not the product).

## When a build plan ships in a different release than it targeted, its frontmatter `scope:` must be the scope-NAME (not a version) — `regen-views` resolves plans by it and a version there silently skips Status flipping at release

## When serially merging several stale feature branches into develop for one batched release, expect additive bookkeeping conflicts every time — and watch for a duplicate `active_build_plan:` key the auto-merge creates

## When a session switches branches after SessionStart, pass the Critic mode explicitly — `infer-critic-mode` trusts the stale session-start branch marker

## When prose picks which model a reviewer/subagent runs on, express it as an ordered fallback chain resolved at dispatch — never a pinned alias

## When you disable a mechanism at its wiring point but keep its implementation, reconcile the retained code's self-descriptions in the same change — or its prose reads as false

## When verifying a framework-repo `lib/`/`bin/` change by running the hook, invoke the repo-local `python3 bin/prawduct-hook` — the bare `prawduct-hook` on PATH is the installed plugin cache, not your working tree

## After a clean cumulative (0 blocking/0 warning), NOTEs are advisory — don't chase cosmetic ones; fixing them reopens the coverage gate on judgeable governance files and forces a no-value review pass

## A new build plan with `scope: null` and low chunk numbers inherits another scope's shipped checkbox flips — set `scope:` from the start

## New change-log entries on a feature branch are statusless — `status=in-progress` is deprecated and trips the regen-views typo-guard

## A change-log `chunks=` tag must match the build plan's chunk-heading numbering *exactly* (zero-padding included) or `regen-views` flips only the matching chunks

## When a feature's logic lives in a `context:fork` skill (no Bash), `lib/` holds the DATA, not the LOGIC — logic helpers nothing imports are dead code

## At release, flip *statusless* unreleased change-log entries to `status=shipped` too — not just `status=merged`

## "I'm just codifying their guidance" is not an exemption from the research trigger — and volatility is a separate axis from knowledge-confidence

## The "canonical" mechanism for a capability can be disqualified by a plugin's composability + always-on constraints — verify the constraint before adopting the recommendation

## When a fan-out render keys on a field that isn't unique, test the collision case — and a self-authored adversarial pass inherits the author's blind spots

## When fanning out a batch build to parallel worktree-isolated workflow agents, partition by disjoint file ownership (integrator owns shared files) and force-clean leftover worktrees before the integration suite

## When a fresh-eyes review's advice about a CONVENTION conflicts with a durable learning + the process doc, the documented convention wins — re-verify before acting

## A reviewer's NOTE/severity is a prior, not a verdict — re-scope any "harmless" change that touches a governance-gate input

## A new framework-wide DEFAULT must land in the session digest — place-once preferences and the thin anchor don't reach migrated repos

## Single-repo plugin+marketplace: the marketplace entry's plugin `source` must be `"./"`, not `{source:github,ref}`

## Release-bound work merged feature→develop under gitflow: KEEP the build plan — it's a live release artifact, not spent

## A `--plugin-dir` read-block is a dev-flag artifact, not a self-containment bug — pair it with `--add-dir`

## Test subprocesses: HOME=tmp_path leaks Python's pyc cache into the test repo

## "Structurally enforced" requires verifying the harness actually enforces it

## Tool-restricted reviewer agents must be context:fork SKILLS, not named plugin subagents

## When a deliberate change turns a passing test red, renegotiate the contract in the open

## A behavior change isn't done until every artifact that DESCRIBES it is updated

## A decision reversed mid-chunk leaves stale rationale in prose you just wrote

## Editing a runtime that governs the current session: check your own signals first

## Pre-dispatch bootstrap code must fail open on a `lib/` ImportError

## Session-end signals must come AFTER handoff

## Artifacts drift silently during sustained building

## Structural gates must match natural workflow

## Growing files need structural nudges to prune

## Reactive systems can't detect missing things

## Governance complexity breeds governance complexity

## Principles need runtime enforcement, not just change-time checks

## Denormalized state drifts without mechanical validation

## Coherence cascades require checking summaries, not just primary locations
<!-- prawduct-learning: confirmations=2; created=2026-01-30 -->

## Escape hatches in classification create silent failures

## Cumulative-Critic finds first-use regressions chunk-Critic can't

## Auto-enable belongs with visibility, not with enforcement

## Removing a mechanism requires removing its name too

## Build-plan fields use `**Title Case:**`, not snake_case

## Build-plan chunk parsers accept `### Chunk N:` AND `## Chunk N (ID) — Name` (BLD-5J8N) — but `regen-views`/`chunks=` still key on the colon Status form

## Submodule and same-name function in __init__ shadow each other

## Detection of structural characteristics should not rely on mechanistic surface markers

## Shared "answer" state and personal "nag" state belong in separate stores

## Framework ownership follows the write strategy, not just registry membership
<!-- prawduct-learning: confirmations=1; created=2026-05-19; sentinel=tests/test_prawduct_sync.py::TestAutoCommitSafety::test_user_authored_place_once_edits_treated_as_wip -->

## A leftover marker is not an in-progress signal — and a test using the canonical marker leaves the real-world branch untested

## A near-verbatim file PORT carries the source's prose — adapt the docs, not just the logic

## A subagent's reported COUNT or LIST is a lead, not ground truth — verify before a blanket edit

## Verify the platform's copy/packaging boundary before duplicating a shared bundled file — a prior "duplicate into each consumer" choice may be an unverified-constraint workaround

## A plugin skill with unparseable YAML frontmatter loads with ALL metadata silently dropped — validate it in CI
<!-- prawduct-learning: confirmations=1; created=2026-06-02; sentinel=tests/test_plugin_manifest.py::TestAllPluginSkillFrontmatter -->

## Dogfooding the generator on its own output masks output-relative bugs the real consumer would hit

## Relocating a source file: sweep every READER of the old path, not just the data-key references

When moving a source file, sweep EVERY reader of the old path — grep it for `read_text` / `open` / fixture writes, not just the path string used as a data key; content-assertions and fixtures that touch the old path surface only on the full-suite run. **The sweep re-triggers at every MERGE, not just at move time:** merging an integration branch into a feature branch that renamed/packaged a module can import NEW readers of the old path that didn't exist when the move was done (here: `lib/norm_probes.py` arrived from develop importing the pre-move `from .backlog import …` API after Chunk 01 moved the parser to `.backlog.legacy`; the full-suite collection error caught it). After such a merge, grep the merged-in tree for the old import/path before trusting green. Relates to Validate Before Propagating (#15) and Living Documentation (#3).

## A review's "inert / harmless" verdict on a latent bug is conditional on the current call graph

## Excising a subsystem silently kills the incidental work it happened to host — re-home the orphaned call, and test the positive

## A "renders-but-doesn't-resolve" leak is a SURFACE, not a line — sweep the whole renderer and assert the bad form is ABSENT

## An "assert the bad form is ABSENT" sweep is only as good as the pattern that defines the bad form — enumerate the whole FORM-FAMILY, not one spelling

## An untested governance bound rots silently across a migration — sweep the guards (with tests), not just the prose

## In a leaf-first decomposition, dependency-scan a chunk's COMMAND bodies against later-chunk symbols before moving — and never move a parity-pinned mirror just because a deliverable lists it

## A format's schema legend lives in `templates/` (scaffold-only) — adding an optional field reaches already-onboarded repos only via a migrate/triage *refresh* step, not the template

## A structural bound that ENFORCES a declaration is not a DETECTOR of the declared property — reusing it at a new boundary silently drops its justification

## A rebuild scoped to a subsystem's "remaining / deferred" parts silently omits an already-shipped part that was deleted in between — re-port against the spec roster, not the open-work list

## A persisted schema's requirements are its consumers' future queries — lock-in is reversal cost, not LOC, so "small format" never exempts it from decision research

## Test-evidence freshness is `test-status` (session timestamp) ONLY — `git_sha` was retired as misleading (TST-4K2P)

## A cross-cutting concern can be UNCOVERED even when discovery names it once — audit the coverage matrix for "named-but-dropped", not just "absent"

## When generalizing or detecting "across all cases", the COMMON / AVAILABLE instance silently narrows the requirement to itself — check coverage against the requirement's stated breadth

## Before "fixing" an apparent forgotten-manual-update, check whether the artifact is a GENERATED / DERIVED view — the real fix is upstream

## A test asserting the framework repo's OWN state instead of the propagated contract gives false coverage — assert the contract that reaches consumer repos

## When a plan sets a quantitative reduction/size floor over a corpus you cannot shrink by dropping content, derive the floor from a per-file compressibility sample — not a global intuition

## Never chain a test-evidence `record` after a suite run in the same command, and never read a piped suite's exit code — read the run's own summary first, because a false-green record pollutes the gate exactly like a false-red

## Re-attempting a mechanism rejected for a false-positive class: make it ADDITIVE and relax-only, and separate the framing from the primitive

A mechanism carrying scar tissue can be viable on a second attempt if you change its FRAMING, not just its implementation — and the check before re-proposing is *what exactly was rejected: the direction or the primitive?* Test-evidence tree-anchoring had been rejected twice (content-hash "fingerprint" v1.3.8, `git_sha` v2.1.8), both as *expiry signals that make evidence go stale*, and both failed as false-STALES (HEAD-SHA baked in; churny metadata hashed between Verify and Critic). The winning reframe was a **disjunction that only ever moves the verdict in the safe direction**: `current iff session-fresh OR judgeable-tree-matches`. Because it can only turn stale→current, never current→stale, it is *structurally* incapable of the false-stale class that killed both predecessors — a property you get from the SHAPE, not from getting details right (which the two prior patches each wrongly believed they had). Separately, distinguish FRAMING from PRIMITIVE: what stayed banned was content-*hashing* (`coverage_algebra`: "paths classify, contents don't"); classifying *paths* via a git tree-diff + `is_judgeable_path` is a different, already-trusted primitive that sits entirely outside the rejection. So: when a diagnosis proposes something with a standing rejection, separate the rejected *direction* (expiry/replace) from the rejected *primitive* (content-hash) — an additive, relax-only, path-classifying clause may be untouched by either. Gate it on a validation matrix that proves the safe-direction-only property BEFORE the schema lands: reasoning the §9 matrix pre-build caught that capturing a tree for `--from-counts` would have flipped a standing restamp contract (stale→current) — the gate doing exactly its job for a lineage where "we believed we'd solved it" had failed twice. Detail in [[learnings-detail]]. Relates to Root Cause Discipline (#16 — fix the failure class, not the instance), Reasoned Decisions (#4), Honest Confidence (#5), Validate Before Propagating (#15), and [[Test-evidence freshness is test-status (session timestamp) ONLY]].

## When validating a CLI's JSON output, feed the tool the raw bytes (direct pipe or file) — never `echo "$captured" | jq` under zsh, whose `echo` interprets `\n` and turns valid JSON into a false "malformed output" finding

Verifying a `--json` CLI, the natural move — capture stdout into a shell var, then `echo "$out" | jq .` — is a trap in **zsh** (this repo's shell): zsh's `echo` builtin interprets backslash escapes by default, so it re-expands the JSON's escaped `\n` into raw newlines, and jq then correctly rejects the corrupted bytes ("control characters from U+0000 through U+001F must be escaped"). The CLI output was never wrong — `json.dumps` escaped the newlines properly; the corruption is 100% consumer-side. This nearly became a false BLOCKING finding against a correct serializer during VRF-004 (backlog-service Chunk 01 live smoke). Two safe consumption patterns: pipe the command *directly* (`prawduct-hook … --json | jq .`) or redirect to a file and validate that (`… --json >/tmp/x.json; jq -e . /tmp/x.json`); to prove validity beyond doubt use `python3 -c 'import json,sys; json.load(open(sys.argv[1]))'` — a real parser on the real bytes, immune to the shell. Corollary for the producer side: do NOT "harden" correct JSON against a shell's `echo` — it distorts right behavior and can't fix a consumer that re-interprets escapes. Same epistemics as the "read the run's own summary, don't trust the pipe" test-evidence rule above: the shell between you and the tool can lie about the tool's output. Discovered VRF-004 zsh-echo false positive (2026-07-17). Relates to Honest Confidence (#5 — nearly reported a guess as a defect), Root Cause Discipline (#16 — the shell, not the code, was the fault), Validate Before Propagating (#15), and [[Never chain a test-evidence `record` after a suite run in the same command]].
## A proactive nudge narrowed to pass a "zero-fire against this repo" acceptance criterion suppresses the exact signal on the reference repo — check the repo is genuinely OUT of the target state before muting

## For a coverage / forcing-function opt-out, make the resolution a first-class recorded artifact (even a one-line stub), not a suppression flag

When a forcing function (a coverage nudge, a required-artifact check, any "you must have X" gate) needs an opt-out for products where X genuinely doesn't apply, resist a suppression scalar / exclusion list — make the resolution the artifact EXISTING, where a deliberate `(not relevant — <reason>)` stub is valid content. A suppression flag is inert (nobody reads it), invisible (buried in state), and rubber-stampable (decline-all defeats the purpose); a first-class artifact — even a one-line stub — is self-documenting, lives where a reader looks for the decision, participates in the rest of the pipeline (the Critic can read it, a norm can attach to it, risk calibration can challenge it), and makes the opt-out a conscious recorded act rather than a silent toggle. Split the labor to keep the check simple: the forcing function owns EXISTENCE (a decision was recorded); the Critic / risk calibration own decision QUALITY (is "(not relevant)" honest for THIS product — e.g. a high-risk repo stubbing out its security model, or a repo that recorded `exposes_programmatic_interface` stubbing out its api-contract, is a contradiction they catch). This also keeps proportionality honest for tiny products: a 30-second stub is cheaper and more legible than maintaining an exclusion list, and a gentle recurring nudge stays un-annoying precisely because resolution is that cheap — so "surface repeatedly" beats "one-shot dismiss + suppression state." Emerged when the owner rejected a `coverage_declined_*` project-state scalar for the structural-coverage probe in favor of `(not relevant)` stub artifacts. Relates to Living Documentation (#3 — the decision documents itself where reality is described), Proportional Effort (#11), Governance Is Structural (#22), Honest Confidence (#5 — a recorded decline is visible and correctable; a silent flag is neither), and [[reactive systems can't detect missing things]] (the forcing function exists because absence is invisible — its resolution must not itself be invisible).

## When a later chunk extends an earlier chunk's module with a derived/richer version of a constant that module already defines by hand, grep for the name first — you otherwise create a SHADOWED DUPLICATE that silently works until the two drift, and the fix is to make the richer structure the source of truth the older constant derives from

Chunked builds keep extending earlier chunks' modules, and the trap is adding a parallel definition of something already there while focused on the new feature. Building the backlog-service status *encoder* (Chunk 02) I added `_STATUS_ENCODING` (a map: status → (state, state_reason, label)) plus `STATUS_VALUES = tuple(_STATUS_ENCODING)` — not noticing Chunk 01 had already defined a hand-written `STATUS_VALUES` literal at the top of the same module. Two module-level definitions of the same name: the later one wins, and because the values were identical it *worked*, so no test failed — a dead literal + a silent drift hazard (add a status to one, not the other, and they disagree). Both Critic reviewers (correctness + design) flagged it independently. The clean resolution is NOT "delete the duplicate" but "pick the SoT and derive": promote the richer structure (`_STATUS_ENCODING`) to the single definition and derive every vocabulary constant from it (`STATUS_VALUES = tuple(...)`, `STATUS_OPEN_LABELS = tuple(s for s,(…,label) in …items() if label)`), so drift is now *impossible*, not merely absent. Discipline: before defining a module-level constant/enum/table in a module you're extending, `grep` the module for the name and for the concept; if the concept already has a hand-maintained form and you're adding a structured one, make the structured one authoritative. This is [[When developing requirements to replace a working system, sweep every consumer's actual usage before finalizing]] pointed inward — sweep every *definition*, not just every reader — and a Reasoned-Decisions/SoT instance (identical duplicated state is denormalization that drifts without mechanical validation). Discovered backlog-service Chunk 02 (2026-07-17, both Critic reviewers). Relates to Reasoned Decisions (#4), Coherent Artifacts (#13), Validate Before Propagating (#15), and [[Before "fixing" an apparent forgotten-manual-update, check whether the artifact is a GENERATED / DERIVED view]] (same derive-don't-duplicate spine).

## Idempotent-re-run crash-safety is only sound when SOME actor is guaranteed to re-run the same transition — when recovery depends on the crashed party specifically (the one who won't return), make the write ATOMIC, not merely re-run-convergent

Two compound-write ops in the same subsystem can both be "crash-safe via idempotent re-run" and yet one be broken, because the property hides an assumption: *who* re-runs. The backlog-service `set-status` (Chunk 02) is genuinely crash-safe — its add-before-remove label reconciliation converges on *any* subsequent writer's re-run (the next status change by anyone self-heals a torn state). I pattern-matched that onto `claim` (Chunk 03): take the assignee first, stamp `claimed_at` second, "a re-run by the same actor converges." But claim's recovery depended on the **crashed actor** returning — and the exact failure the feature exists for (M11: a *died* fleet agent's claim must free so `pick` can't starve) is precisely when that actor never returns. Worse, my own fail-open ("assignee set + no `claimed_at` stamp → treat as a live claim, never reap") made the torn intermediate state *permanently* stuck: assigned-but-unstampable, invisible to `pick` until a manual `unclaim`. The Critic caught it; every one of my own tests passed because the two-write torn state is invisible without fault-injection at the seam. Fix: collapse the take into ONE atomic `update_issue` PATCH (assignees + body together — GitHub's issue PATCH accepts both), so no torn state can exist; drop the now-redundant `set_assignees` seam; add a fault-injected crash test (inject at the take → item stays free → re-run converges). Test for the pattern: for any compound write claiming crash-safety-by-re-run, ask "if the process that crashed never comes back, does another actor's ordinary operation still converge this?" — if recovery is actor-specific, atomicity (one request, or a redirect-before-close ordering that reads valid at every cut) is required, not idempotent re-run. Discovered backlog-service Chunk 03 (2026-07-17, Critic warning). Relates to Root Cause Discipline (#16), Honest Confidence (#5 — green tests don't prove a seam's crash path), Independent Review (#14 — a "does it work?" self-review can't see the torn state), and [[When a later chunk extends an earlier chunk's module with a derived/richer version of a constant that module already defines by hand, grep for the name first]] (both are "the earlier chunk's pattern doesn't transfer unexamined to the later one").

## A human-mode output formatter that dispatches on "which key is present" silently shadows a new result type sharing a key with an earlier branch — order the checks most-specific-first, and TEST the human path because `--json`-only tests never exercise the formatter

The backlog-service CLI's `_print_human_ok` is an `if/elif` chain keyed on the presence of a distinctive field (`"candidates"`→pick, `"items"`→list, `"by_status"`→counts, …). Chunk 05's `export` result carries `{repo, dir, count, items}` — and its `items` is a list of id *strings*, but the earlier `elif "items" in data` branch (the `list` result) assumed a list of item *dicts* and called `.get("id")` on each → `AttributeError` the moment `export` ran in human mode. Every test passed because they all asserted on `--json` output, which bypasses the formatter entirely. Two coupled lessons: (1) a dispatch keyed on key-presence is order-sensitive and additively fragile — a new result type must be matched on its *own* unique key placed before any earlier branch whose key it happens to share (same failure family as the shadowed-duplicate constant, but for output shapes); (2) `--json`-only tests are not coverage of the human path — driving the actual front at Verify (Principle 15) caught it where the whole L1 suite could not. Fix: reorder the migration branches ahead of the generic `items`/`candidates` ones, plus a human-mode regression test that runs each new op without `--json`. Discovered backlog-service Chunk 05 (2026-07-17, at Verify). Relates to [[When a later chunk extends an earlier chunk's module with a derived/richer version of a constant that module already defines by hand, grep for the name first]] and Honest Confidence (#5 — green tests over the wrong surface aren't verification).

## An "unverified / validated-when-run" honesty caveat covers only genuinely-unknowable facts (live behaviour, external state) — NEVER facts checkable now (a key path, a signature, a flag); verify the knowable, disclaim only the unknowable

A dev-only spike script (can't run offline) carried a "these assertions are validated when run live" caveat — but one check read the export's native graph from top-level `dependencies`/`sub_issues` keys when `_export_record` nests them under `relationships`, an always-falsy false-negative the Critic caught. The caveat is legitimate for the live-GitHub timing/behaviour the script probes; it is *not* a license to skip reading a source file whose shape is knowable now. When you write a confidence disclaimer, scope it to the genuinely-uncertain and still verify everything statically checkable. Discovered backlog-service Chunk 06 offline deliverables (2026-07-17, Critic chunk-mode). Sharpens Honest Confidence (#5) and Validate Before Propagating (#15).
## A repo-coupled (non-hermetic) test turns every "non-judgeable" doc/state change into a silent test-breaker — the doc-only and test-status classifiers assume non-code files can't change test outcomes

## A `/prawduct:*` skill fork writes `.prawduct/` state to the LAUNCH dir, not a worktree the session ENTERED mid-session — launch/`/clear` inside the worktree, or relocate the fork's output and restore the polluted checkout

When you enter a git worktree mid-session (harness `EnterWorktree`), main-loop `prawduct-hook` calls resolve to the worktree (Bash cwd = worktree; STH-4K7N's cwd-based `resolve_project_dir`), but a skill invoked as a FORK does NOT — its `CLAUDE_PROJECT_DIR`/cwd stays pinned to the launch dir, so `/prawduct:backlog add` (and any state-mutating skill) silently writes into the PRIMARY checkout and reports success. If that checkout is another active worktree's WIP, this cross-pollutes a different branch's diff/Critic/PR. Confirmed 2026-07-16 (VWS-2W6H landed in feature/norm-lifecycle, not the backlog-service worktree — had to relocate it and `git checkout` the primary's backlog.md) and independently in discodon (SCH-2QW9/ENT-T8QN: an item filed into a worktree's backlog, reverted + hand-merged so "main solely owns the backlog"). So: prefer to LAUNCH (or `/clear`) the session INSIDE the worktree so every fork inherits the worktree project dir; if you must file from a mid-entered worktree, verify WHERE the fork wrote and relocate + restore. Deeper cause — `.prawduct/backlog.md` is a per-working-copy flat file, so worktrees diverge by construction (a motivation for a server-side backlog store). Full detail + fix-shape in [[backlog]] STH-7W9K. Relates to Structural Awareness (#21), Root Cause Discipline (#16), and [[backlog]] CRT-6W2N / STH-4K7N.
