# Learnings

Active rules from this project's development. Surfaced via the `/learnings [topic]` skill — topic headers shown in the session briefing for ambient context. Entries use "When X, do Y because Z" format. Each entry's full narrative lives in `learnings-detail.md` under the same heading — keep narrative THERE, not here.

---

## When a commit claims to close a backlog item, verify the claim against the item's FILED CASE before crediting it — a fix aimed at the item's title routinely lands the ADJACENT sub-case, passing every guard while the filed reproduction still reproduces, so merging closes a still-broken item as shipped

## Merge instructions written BEFORE the merge — a subagent's advice, or a note you wrote yourself — are verified against the merge's actual hunk shape, never applied literally: whoever reasons from the BRANCH cannot see a convention the DESTINATION adopted after the branch was cut

## When a feature's value rests on an invariant ("presence of X proves Y"), audit the DEGRADATION paths first — that is where the invariant actually lives: a helper that swallows failure into "" or False makes absence ambiguous and can render the signal's exact inverse, so pick each fallback's direction from what the invariant needs, not from what is locally safe

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

## When a docstring makes an absolute robustness claim (never raises / always returns / idempotent), make it literally true and test the claimed-safe path — an absolute claim beside a call that *can* violate it is a coherence gap reviewers reliably flag

## When developing requirements to replace a working system, sweep every consumer's actual usage before finalizing — reported pain is a hypothesis, and the loudest complaint is often not the deepest failure

## When a fail-closed validator guards a model-written field, tolerate the natural encoding variant — reserve the hard fail for genuine ambiguity, because incidental strictness at a model-output seam is a latent fail-close

## When the success path threads advisory/audit data through a result envelope, add it to EVERY error-return path too — in an envelope-heavy codebase the error return is built by a *different* constructor (here `core.from_transport_error` vs `core.ok(data, warnings)`) that has no slot for the field and silently drops it; the damage is permanent, not cosmetic, when the datum is one-shot (a self-heal audit line that won't re-run on resume, so it can never be re-emitted). Second instance of this class in backlog-service import (BKL-3K9N rate-limit path, BKL-9V2W TransportError path — both funnel through one outer `except`). Grep the error/exception returns whenever you enrich a success envelope.

## When designing any flow step that records status or bookkeeping, make it ride IN the PR that does the work — a step that can only run post-merge on the integration branch is structurally broken for protected-branch consumers

## When a governance checkpoint verifies a required side-effect happened, put it OUTSIDE the control flow that produces the side-effect — a check inside the fallible flow can't catch that flow's own skip

## Correcting a false claim is authoring a new claim — verify the replacement and the artifacts it cites, because the fixing mood generates claims faster than the checking reflex fires

Fixing a false safety claim across ten sites, the same changeset introduced two fresh ones: an `all`-scope bullet promising the archive "stays reachable from `find`/`list`" (post-cutover `find` is W2-deferred for *every* item — established by the PR merged an hour earlier, precisely because it was adjacent), and "re-run with `--archive-scope all` to backfill, no duplicates" (true about duplicates, silent that the skip path reconciles status, so a backfill reopens anything closed on the service since cutover). Then the *correction* of one of those overclaims swung into a different wrong claim — asserting a backlog note "records the same gap" when it concluded the opposite — taking three commits to land accurate. **Two rules.** (1) A replacement sentence gets the same falsification query the original needed; being in the middle of a correction is the *highest*-risk moment for this class, not a safe one. (2) When successive edits to one passage alternate direction (overclaim → overcorrect → …), stop editing and go read the sources — the oscillation is the tell that you are reasoning from the passage instead of from what it describes, and a reviewer calling a further pass "churn, not improvement" is usually right. Discovered 2026-07-20 on `fix/archive-scope-preservation-claim` (cumulative + 5 verify-resolutions rounds, 15→0). Relates to [[Before writing any sentence of the shape "X now covers/catches/handles Y" or "there is no Y", run the one query that would falsify it]] and Validate Before Propagating (#15).

## Before writing any sentence of the shape "X now covers/catches/handles Y" or "there is no Y", run the one query that would falsify it — a coverage claim is the highest-frequency error class here and is almost always checkable in under a minute, so treat the SENTENCE as the trigger, not your confidence in it

The claim-shape is the tripwire, not the topic: "this test now catches the class", "every reader is repointed", "there is nothing local to run this against", "the inventory is exhaustive". Six instances across 2026-07-19/20 — twice stating a repo/state didn't exist that did (one loop over sibling `project-state.yaml` files falsified it), twice describing a regex/test as covering a class it demonstrably could not (`[^.]` excluding the dots in `.prawduct/backlog.md`; an `op == "x"` derivation blind to `op in ("a","b")`), once repeating a docstring's rationale that the requirements had already corrected two days earlier, and once writing "fixing one and not the other would be the patch-the-flagged-line failure" while leaving the sibling copy in the same file. Being careful demonstrably does not work at this frequency; the check does. Fix-shape: (a) for a set/coverage claim, re-derive the set with the precise query right before writing it; (b) for an absence claim ("no X exists"), run the enumeration rather than reasoning from what you happened to see; (c) for a rationale read off a comment or docstring, verify the requirement it cites still says that — the nearest source is not the authoritative one; (d) for "I am avoiding anti-pattern P", actually run P's detector, because naming P is not running it.

**Instance 8 (2026-07-20) sharpens this into something mechanically detectable — the check can be *performed* and still be worthless.** Correcting a false claim across the repo, I ran the grep, counted the hits, and told the user "seven surfaces." The pipeline ended in `| head -20`, so real hits had been truncated away; a wider re-run found more and I said "nine." The enumerated truth was **ten claim sites across seven files** — so the first number was wrong, and so was the correction, which is the part worth keeping: *this entry originally asserted "It was nine," and a Critic pass caught the durable learning about miscounting carrying a wrong count.* A number read off a truncated search is not a count — it is a check-shaped artifact that reads as diligence in the transcript, and is therefore *more* convincing than an unchecked guess would have been. The tell is now syntactic rather than introspective: **if the pipeline that establishes completeness contains `head`, `tail`, `-m`, or any other cap, its output must not be stated as a total.** Re-run it uncapped, with the pattern widened to the claim's actual shape, before writing the number. Corollary from the same session, pointing the other way: before mass-correcting a sentence, check the *siblings* that share its wording — four "recoverable via the MG2 export backup" claims about `restructure` were **true** (the block carries `original_title`/`original_body`, so the post-import export does hold them) while the identically-worded `--archive-scope` ones were false, so a sweep-and-replace would have converted four correct statements into wrong ones. Relates to Honest Confidence (#5), Validate Before Propagating (#15), Retrieval Over Generation (#24), and [[When building from a review/audit artifact, verify each cited gap and fix-instruction against HEAD before planning]].

**Sharpening (2026-07-20, `fix/archive-scope-preservation-claim`, across a run of verify-resolutions
rounds — count deliberately omitted; corollary (c) says why):
the error lives in the QUANTIFIER, and that makes it detectable before writing.** Across one branch
the same shape recurred with the narrow fact correctly verified every time and the written claim
scoped wider than the check: "there is **no** follow-up commit on **any** of them" (true for two of
three files — the third had one), "the other ten, **every** one of them migration work" (one was
not — `stale-remote-base-diagnostics`; the sentence survives verbatim in the hotfix plan and is
now *true*, because the set it quantifies over was re-derived, which is the point: quantified
sentences go stale when the set moves under them, not when the words change), "six `--repo`
placeholders in six **steps**" (six commands across four steps), "**also**
catches a second minting site" (only one copied in the same literal shape; an f-string passes).
Each was written inside the correction of the previous one. So the operative rule is not "check
harder" — it is **verify at the quantifier**: when a sentence contains *no / every / all / only /
none / also*, the check must enumerate the quantified set, and a per-file claim needs a per-file
loop, not a combined query that returns one answer. Three corollaries. (a) A number derived
positionally is not derived from the field: counting change-log entries *above* a release boundary
structurally cannot see an unreleased entry below it, and one was there — REL-2N8K reproducing
inside the plan citing REL-2N8K. (b) **An untouched sentence inside an edited paragraph reads as
freshly vouched-for.** Editing a paragraph re-publishes all of it; re-verify the sentences you did
not change, because a reviewer — and a later reader — cannot tell which ones you actually looked at.
(c) **Some quantified sets contain the sentence that counts them, and those counts cannot be
written truthfully.** This entry first opened "five verify-resolutions rounds," then "twelve —
eleven reachable, one orphaned," and a re-enumeration minutes later returned thirteen reachable
plus the orphan, because the review answering the sentence had itself consolidated in between and a
widened predicate swept in a round the first query's `head_commit` filter had missed. Neither
number was carelessly derived; both were stale on arrival. The tell is self-reference: **when the
act of writing the claim changes the set the claim quantifies over, no enumeration converges** —
say "a run of" and describe the shape, or pin the set to a closed predicate ("the rounds preceding
this one") that writing cannot move. Counting harder is the wrong response; the set is the problem.

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

## When verifying a framework-repo `lib/`/`bin/` change by running the hook, invoke the repo-local `python3 plugin/bin/prawduct-hook` — the bare `prawduct-hook` on PATH is the installed plugin cache, not your working tree

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

## Single-repo plugin+marketplace: the marketplace entry's plugin `source` must be a RELATIVE PATH, not `{source:github,ref}` — and that path is a curated subdirectory, not the repo root

A `{source:github,…}` object makes Claude Code re-clone over SSH to fetch the plugin, which fails with "Permission denied (publickey)" on any machine without SSH keys, even for a public repo. A relative path reuses the marketplace's own HTTPS checkout. **Corrected 2026-07-21:** this entry previously read `must be "./"` with no body, so the heading was the whole rule — and a reader applying it would revert the v3.1.1 packaging fix. `"./"` distributes the entire repository, putting prawduct's own backlog, learnings and internal docs into every consumer's plugin cache (GOV-4H7T). The path is `"./plugin"`, a curated root holding only what consumers run. Both halves matter and neither implies the other: relative-not-github is about the clone transport, subdirectory-not-root is about the distributed surface. Pinned by `tests/test_plugin_packaging.py`.

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

When moving a source file, sweep EVERY reader of the old path — grep it for `read_text` / `open` / fixture writes, not just the path string used as a data key; content-assertions and fixtures that touch the old path surface only on the full-suite run. **The sweep re-triggers at every MERGE, not just at move time:** merging an integration branch into a feature branch that renamed/packaged a module can import NEW readers of the old path that didn't exist when the move was done (here: `lib/norm_probes.py` arrived from develop importing the pre-move `from .backlog import …` API after Chunk 01 moved the parser to `.backlog.legacy`; the full-suite collection error caught it). After such a merge, grep the merged-in tree for the old import/path before trusting green.

**Readers are not only code — and the non-code readers are the ones the suite cannot see (recurrence 3, 2026-07-21, escalated).** The `plugin/` relocation merge left `bin/prawduct-hook` in five skills' *instruction prose* and, worse, in their `allowed-tools:` **permission grants** — so the documented command could not run and the grant did not cover the one that would. A green full suite proved nothing, because no test executes a skill's front-matter. Same merge, same class, third occurrence. The sweep surfaces, in the order they fail silently: `allowed-tools:` grants → skill/methodology prose → durable planning artifacts (`.prawduct/artifacts/**` — release plans and build plans a future session reads as current instruction, which is DOC-2R7M) → docstrings (lowest stakes; often correct to leave). The packaging boundary test verifies file *location* and is blind to path *references*; closing that asymmetry is the structural enforcement this recurrence earns (BLD-6P8T). Relates to Validate Before Propagating (#15) and Living Documentation (#3).

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

## When salvaging work from a branch you are about to delete, diff the ID SETS of its state files — a commit-by-commit triage silently drops novel items that ride inside otherwise-obsolete commits

Retiring a stale worktree branch, the natural triage is per commit: read each one, judge it superseded or novel, salvage the novel. That method has a blind spot — a commit's *overall* disposition says nothing about every hunk inside it, and `.prawduct/` state files accumulate independent items that ride along with unrelated code. Confirmed 2026-07-19: commit-by-commit triage of the removed `backlog-service-plan` branch concluded exactly one backlog item needed salvaging; the Critic then caught that the learnings rule I had just ported ended with a dangling `[[backlog]] STH-7W9K` pointer, and STH-7W9K turned out to be committed *inside* a 100%-obsolete backlog-service walking-skeleton commit. Extracting every `[XXX-NNNN]` id from both copies and running `comm -23` found three more (STH-7W9K, VWS-2W6H, BLD-6T4R) in seconds. So: for any structured state file with stable ids (backlog, operator-verification, change-log scopes), compare the SETS mechanically and let the diff — not your reading of the commit log — decide what is missing; then re-verify each candidate against current code before filing, since a stranded item's body may describe behavior that has since drifted (VWS-2W6H's loud error had partly become a silent wrong-pick). Generalizes [[When a later chunk extends an earlier chunk's module with a derived/richer version of a constant that module already defines by hand, grep for the name first]] from definitions to *records*, and relates to Complete Delivery (#2 — never silently drop a requirement, including one someone else wrote), Validate Before Propagating (#15), and [[A `/prawduct:*` skill fork writes `.prawduct/` state to the LAUNCH dir]] (the pollution that stranded these items in the first place).

## A test that asserts a SUBSTRING of prose stops being a contract the moment someone writes a longer sentence containing it — when prose changes meaning, grep the tests that assert fragments of it, not just the ones that fail

`test_pr_reviewer.py` asserted `"always run" in content` under a docstring reading "R-2 stays unconditional." Chunk 02 rewrote that prose to "always run **on this backend**" — the opposite claim — and the assertion sailed through a green 2453-test suite. A failing test renegotiates its contract in the open ([[When a deliberate change turns a passing test red, renegotiate the contract in the open]]); a test that keeps passing while its stated contract inverts is strictly worse, because nothing signals. So: when an edit changes what a prose surface *means*, `grep` the test corpus for fragments of the old sentence and re-read every hit against its docstring; and prefer assertions that pin the *discriminating* clause (`"always run on this backend"`), not a prefix any successor sentence will contain. Corollary: a chunk planned `doc-only` is mis-typed the moment its prose contradicts a test — re-type it rather than leave the substring passing. Discovered skills-cutover-awareness Chunk 02 (2026-07-20). Relates to Tests Are Contracts (#1) and Honest Confidence (#5).

## A rationale you reached for to defend a decision you'd already made is the one to verify BEFORE writing it into a durable spec — the reach itself is the tell

Justifying "the janitor gets no post-cutover backlog context," I wrote into `skills/janitor/SKILL.md` that its `allowed-tools` grants no `Bash(prawduct-hook *)`, so "the janitor surveys, it does not query services." The frontmatter fact was true and the inference was unsound: Step 1 of the same file already instructs `prawduct-hook review-stats`, and every sibling skill instructing a hook call carries the matching grant — janitor is the sole exception, i.e. an oversight. The decision was actually made on other grounds (the owner's W1 read-through-cache ruling); the grant story was recruited afterward to make it look principled, and it laundered a bug into a recorded architectural position where a later builder could cite it. So: when you notice yourself supplying a *second* reason for a decision already settled, treat that reason as unverified — read the mechanism it rests on (Principle 24), and if it turns out to be a defect, file the defect and rest the prose on the premise that actually decided it. This is the requirement-invention tripwire (#6) in inverted form: not a requirement invented forward into code, but a rationale invented backward into a spec. Discovered skills-cutover-awareness Chunk 03 (2026-07-20, Critic warning). Relates to [[A decision reversed mid-chunk leaves stale rationale in prose you just wrote]] and Reasoned Decisions (#4).

## A status surface that reports the ABSENCE of expected output must say whether absence is the normal in-flight state — a bare zero invites the reader to invent a death story and take recovery action against healthy work

Confirmed 2026-07-20 ("critic reviewers died with fork", cross-repo): background critic reviewers
run 5-15 min after the dispatching fork returns; a parent session consolidating at ~2.5 min got
`0/3 partials present`, inferred "the fork ended and took them with it" (transcript-verified false
— all three were alive and completed), and re-dispatched a duplicate roster, doubling review cost.
Same binary had run the identical shape clean the day before — the trap is probabilistic model
inference over ambiguous silence, so the fix belongs at the decision point: the message now renders
dispatch age plus a wait/abandon verdict (8b6eef6, CRT-3F7M fix (b)). Generalizes to any
empty-state report an agent acts on (empty queue, no results yet, 0 workers reporting): pair the
count with the timing fact that discriminates in-flight from dead, and name the sanctioned recovery
path so the reader doesn't improvise one. Relates to Honest Confidence (#5), and note the failure
phrase itself ("died with fork") began as one model's hallucinated diagnosis and propagated as
observed fact — including into CRT-3F7M's title.

## When auditing guidance material, have a fresh agent USE it before you recommend changing it — analytic review predicts defects that do not survive contact with practice, and the trial is what tells you which findings are real

Auditing the runbook guide/skill/template (2026-07-20), I argued from the text that the template should be inverted — minimal default, optional sections in a library — because a form-shaped template pulls authors into filling it in and "deletion is the weaker operation." Two subagents then authored real runbooks from the *unmodified* material and both deleted correctly and for the right reasons (blast radius, duration, authorization, maintenance, prerequisites, phases, irreversible block — each against its include-test), with one reporting the guide "stopped me from writing a bloated runbook, which is what I would otherwise have produced." The recommendation was refuted by the artifact it was about. The trials also produced findings no amount of reading would have: that ~150 of 1,277 lines carried all the binding instruction, that the worked example outperformed everything after it, and that a documented procedure contradicted itself in a way only a deriving reader would hit. So: for any material whose purpose is to *make an agent produce something*, the audit is a usage trial, and reading is only how you form hypotheses to test. Run the trial before writing recommendations, not after — otherwise the write-up is sunk cost arguing against the evidence. Corollary, learned the same session: an audit's deliverable is ranked findings, not a work program; ~7 verified small defects became a 5-chunk plan with 12 new rules before the owner cut it back to the defects. Relates to Proportional Effort (#11 — which the methodology states for artifacts and rigor but not for the size of a response to a finding), Retrieval Over Generation (#24), and Honest Confidence (#5).

## When a guarantee names a specific event, gate on THAT event — a signal that usually co-occurs with it passes every test you think to write, because you wrote them believing the proxy

Session-handoff Chunk 01 introduced `.handoff-notes.md`, a model-authored note consumed into the generated handoff and then deleted. The stated guarantee — written into the docstring, the call-site comment, `architecture.md` and the change-log — was "a note is deleted only once its text is durably in the handoff." The code gated the delete on `handoff_written`, which is true whenever *any* section produced content, while the notes reader collapsed absent / empty / **unreadable** into one empty string. So an undecodable note was deleted with its text carried nowhere — unrecoverable, through the documented happy path — and the chunk's own test walked that exact path while asserting nothing about the notes file. All three Critic reviewers found it independently, which is the tell: convergence from unrelated lenses means it was never subtle, the author was reading their own comment instead of the code. So: when you write "only after X," find the expression that *is* X and gate on it; if X isn't representable, that absence is the finding — make it representable (here, the reader returning a state rather than a string whose emptiness meant three different things). Corollary: an invariant asserted in N prose locations is N places that will keep asserting it after the code stops honoring it, so the prose count is a risk multiplier, not evidence. Discovered session-handoff-continuity Chunk 01 (2026-07-26, Critic warning ×3). Relates to [[A test that asserts a SUBSTRING of prose stops being a contract the moment someone writes a longer sentence containing it]], Tests Are Contracts (#1), Independent Review (#14).

## "Advice fails soft" is not "advice fails silent" — a degraded advisory path must still name its consequence, or it manufactures the false success it was meant to prevent

Same chunk, second instance of the same class. `architecture.md`'s ratified norm reads "advice fails soft… a probe that errors is swallowed with attribution, not raised" — and its own words are *degrades to a note*. I read the norm as license to swallow, and left handoff generation as the one failure path in `cmd_clear` that printed nothing, while every sibling (session-start write, each session-file unlink) named what the user loses. Consequence: an agent that wrote a forward note, watched `/clear` exit 0, and reported "safe to `/clear`" was wrong, and nothing told anyone — which is precisely the silent-success defect the chunk existed to repair, reproduced inside the repair. So: when a norm says a path may not *block*, that constrains the exit code, not the diagnostic. Ask separately "who is harmed by this failure, and how would they learn?" — if the answer is "nobody tells them," the soft failure is incomplete regardless of the norm. Discovered session-handoff-continuity Chunk 01 (2026-07-26, Critic warning). Relates to Honest Confidence (#5) and Living Documentation (#3).

## A fix lands at the instance a review named; the defect lives in the class — so before closing a finding, name the class and route it through one owner, because every local fix looks complete from inside itself

Three instances in one bundle, which is why this is a rule and not an anecdote. (1) CRT-7B4M shipped the git-derived "which chunk is current" for `infer-critic-mode` alone; the identical defect then surfaced at `verify-chunk-refs` (BLD-7K3Q) and at the session handoff (SCN-4H9T) — three consumers, one root cause, fixed once locally and twice more later. (2) The Chunk 01 Critic's central catch produced the rule "make the state representable," and it was applied to `_read_handoff_notes` — while its sibling `_read_unmarked_handoff`, *three lines below*, kept returning a string whose emptiness meant absent / machine-generated / **unreadable**, and the Chunk 02 Critic found it as BLOCKING. The learning had been written the day before, from that very function's neighbour. (3) Chunk 02's own sweep moved three git helpers into one module and pinned them out of the old one — while the *composition* they served ("try git, else checkboxes") stayed written in two places, so a third progress signal would have diverged the consumers again with the pin still green. So: a finding names a location; ask what class it belongs to and sweep the class. Prefer sweeping **by construction** — one owner every consumer must go through — over sweeping by enumeration, because enumeration is a list that the next consumer is not on. Corollary with teeth: a consolidation pin that asserts where a SYMBOL lives does not assert where a DECISION is made; pin the decision. Discovered session-handoff-continuity Chunk 02 (2026-07-27, Critic blocking + warning). Relates to [[When a guarantee names a specific event, gate on THAT event]], Root Cause Discipline (#16) and Close the Learning Loop (#18).

## A CLI on `$PATH` is a different checkout from the worktree you are editing — an interactive command's exit code is not verification evidence for a change to that command

The Chunk 02 Critic coordinator traced a lead that did not reproduce: it ran `prawduct-hook verify-chunk-refs` and got the pre-fix answer, because bare `prawduct-hook` resolved to the *installed plugin* (`~/source/prawduct`, on `main`) while the fix lived in the feature worktree. It corrected itself in the review, and the hazard generalizes past that one command: in any repo whose own tool is installed globally — a plugin, a CLI, an editable package — the shell reaches for the installed copy while you are reading the edited one, and the two agree just often enough to be trusted. The tell is a live check that disagrees with a passing test suite, and the instinct to believe the CLI. So: invoke the artifact under test by explicit path (`python3 plugin/bin/tool`, `./bin/tool`) whenever the change IS the tool, and say which copy ran when citing the output as evidence. This also bites the dogfooding case in the other direction — this repo's own `/clear` hook ran the installed `main` build all session, so Chunk 01's shipped forward-channel code was not the code that processed the notes file. Discovered session-handoff-continuity Chunk 02 (2026-07-27, Critic note). Relates to Honest Confidence (#5) and Validate Before Propagating (#15).
