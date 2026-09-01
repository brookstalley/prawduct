# Learnings — Retired

Entries retired by `audit-learnings --apply`, moved out of `learnings-detail.md` so the active corpus stays the thing a lookup reads. **Nothing is ever deleted from this file.** A reader who remembers a rule and cannot find it in `learnings.md` looks here: each entry carries the reason it was retired and, for a supersession, the heading that replaced it.

## Historical (structurally enforced)

Learnings retired by `audit-learnings --apply`, for one of two reasons, stated on each entry: a declared `sentinel=` test now passes, so the failure mode is structurally enforced; or a broader rule superseded it, in which case the entry names its replacement. Kept here as historical context.

## Pinning the CONSTANT a threshold uses is not testing the threshold — exercise the firing path and prove it by mutation, because a constant-equality assertion survives an inverted comparison while its name convinces the next reader the path is covered

*Retired 2026-08-01 — superseded by **Green is evidence ONLY about what could have made it red — for each test name the change that would turn it red; if you cannot, it measured nothing. The fixture may never reach the subject; a constant-equality assertion survives an inverted comparison while its NAME convinces the reader it is covered. Same for a live probe: say what a FAILING run would have looked like before recording one**. That rule is the active statement; this one is kept for readers who remember it.*

`TREE_COUNT_ADVISORY`'s test was named `test_advisory_fires_at_the_documented_trigger` and asserted exactly one thing: `== 10_000`. The class's only behavioural assertion was the *negative* case (`'NOTE:' not in stdout`, far below the trigger), so flipping `>=` to `>` — or breaking the f-string — shipped green. The recursion is the lesson: this was the test written to close a finding whose thesis was *"a trigger nothing observes"*, and it reproduced that defect one level up. The trap is that a constant feels like the behaviour because the constant is what the plan talks about; asserting it discharges the *documentation* of the threshold and none of the threshold. Mechanics: patch the trigger DOWN to meet a small fixture rather than building a fixture large enough to meet the trigger, and assert at the boundary (fires *at* the count, silent below) so `>=` vs `>` is pinned. Then mutate and watch it fail — four minutes, and it converts "this test looks right" into "this test detects the failure it names," which matters because the old test also looked right. Same discipline caught a narrow `startswith("archive")` masquerading as a four-word resolved-section check: the test only exercised `## Archive`, which both predicates excluded. Discovered 2026-07-29 (coverage-perf verify-resolutions; recurred in release-readiness). Relates to Tests Are Contracts (#1), [[A test that asserts a SUBSTRING of prose stops being a contract]].

## A gate that lives inside a procedure must be tested across the procedure's own state transitions, not at one instant — every fixture encoding a single moment will miss the step where the procedure changes the data the gate reads

*Retired 2026-08-01 — superseded by **A fixture's world is narrower than the requirement it certifies — the COMMON instance narrows the requirement to itself, so check coverage against its stated BREADTH; the framework's OWN state stands in for the propagated contract, so assert what reaches consumer repos; one moment stands in for the procedure's transitions; and the collision case is unwritten when the fan-out key is not unique**. That rule is the active statement; this one is kept for readers who remember it.*

`check-releasability` (release runbook Phase 0) enumerates release-pending scopes as "tagged, no `release=`". Phase 1 step 3 then *stamps* `release=` on the shipping set — so on any second Phase 0 run those scopes have left the pending set, and the orphan check reported every successfully classified scope as a stale table row. The gate would block the release it had just approved, and no test could have caught it because each fixture encoded one point in time. Generalises `building.md`'s multi-hop rule: there the hops are subsequent invocations of a function; here they are *phases of the runbook the gate is embedded in*. So when a gate reads state that a later step of its own procedure mutates, write the fixture for **after** that step too. Corollary found in the same pass: when adding such an exemption, scope it to the disposition that earns it — exempting `withheld` alongside `ships` made a withheld-then-shipped contradiction vanish from `pending`, from the orphan list, and from the summary at once, printing `releasable:`. Discovered 2026-07-29, release-readiness Chunk 01 (Critic warning). Relates to Root Cause Discipline (#16).

## Verify a disposition against the diff before recording it — "fixed" is a claim about the tree, not about intent, and a dispositions record is what the next reader trusts INSTEAD of re-reading the findings

*Retired 2026-08-01 — superseded by **Reads as evidence, is not: an absence-claim citing a path that does not RESOLVE, a missing directory returns the same empty result as the claim being true; a disposition recorded from intent, not the diff, which the next reader trusts INSTEAD of the findings; a commit crediting a backlog item by TITLE while its filed reproduction still reproduces; and a subagent's COUNT or LIST, a lead**. That rule is the active statement; this one is kept for readers who remember it.*

A dispositions change-log entry listed two findings under **FIXED** whose edits were never made; they had been written from what the author intended to do while fixing the others. The verify pass checked each claim against the tree and returned it as BLOCKING — correctly, because the entry's whole function is to let a reader skip re-deriving 30 findings, so one unverifiable claim devalues every acceptance beside it. Two forces produce this: dispositions get written in one sitting *after* the code work, when memory of "I'll fix that too" is indistinguishable from having done it; and the truthful-sounding sentence is cheaper to type than the edit. Fix: write dispositions **from `git diff`**, not from recall, and strike-through-with-annotation rather than silently rewriting when a claim turns out false — the false claim is part of the record. Companion rule from the same review: **record what you declined, not only what you did** — two other fixes landed the code half of a recommendation and dropped the test half, and the entry said "fixed" without noting the drop, which is the same defect one level down. Discovered 2026-07-29, release-readiness Chunk 01 (Critic blocking). Relates to Living Documentation (#3), Honest Confidence (#5).

## Before recording a probe's result as a settled fact, state what a FAILING run would have looked like — if you cannot describe the observation that would have falsified it, the probe measured nothing and the "fact" is an artifact of the measurement Same discipline as a discriminating regression test, applied to live measurement

*Retired 2026-08-01 — superseded by **Green is evidence ONLY about what could have made it red — for each test name the change that would turn it red; if you cannot, it measured nothing. The fixture may never reach the subject; a constant-equality assertion survives an inverted comparison while its NAME convinces the reader it is covered. Same for a live probe: say what a FAILING run would have looked like before recording one**. That rule is the active statement; this one is kept for readers who remember it.*

: SPIKE-S2 timed `pick` at 1/3/5 candidates and read flat latency as proof of a batched fan-out, but the candidate count IS `limit` and `limit` was applied only AFTER the fan-out ran over every eligible issue, so varying it varied nothing; the flatness measured the constant full-scan and the invalid inference was cited as settled across four documents plus the probe's own docstring.

## A completeness claim states the COMMAND that would falsify it and asserts that command now returns nothing — never a count of sites fixed, which is true of any prefix of the real set. Corollaries: run it **whitespace-normalized**, and query the **CONCEPT, not the phrasings you already found wrong** — a regex built from known-bad spellings is another enumeration wearing a query's clothes

*Retired 2026-08-01 — superseded by **A completeness claim asserts the falsifying COMMAND now returns nothing — never a count of sites fixed, which is true of any prefix of the real set. The query is itself a mechanism and can carry the defect it hunts: normalize the text before searching, because line structure is not semantic structure, and query the CONCEPT, not the phrasings you already found wrong**. That rule is the active statement; this one is kept for readers who remember it.*

A line-based pass misses wrapped occurrences, which is why the sweep must be whitespace-normalized.

: "corrected in three places" passed review while six surfaces still carried the claim, two in a file that pass had edited, and the re-run found a seventh (a probe docstring) no enumeration could have reached. Corollaries, each learned by the sweep failing again at the next level: run it **whitespace-normalized** (a line-based pass misses wrapped occurrences), and query the **CONCEPT, not the phrasings you already found to be wrong** — a regex built from the known-bad spellings is another enumeration wearing a query's clothes. Three passes here: named-sites → 7 more; phrase-regex → 4 more (including one asserting the retracted claim in the live tracker, and the probe's own step list)

## An absence-claim must cite a path that RESOLVES, or its verifying command returns empty for the wrong reason — the missing directory produces the same evidence as the claim being true: seven sites asserted "no GraphQL in `lib/backlog/`" after the tree became `plugin/lib/backlog/`, so the grep that "confirmed" it was confirming only its own bad path

*Retired 2026-08-01 — superseded by **Reads as evidence, is not: an absence-claim citing a path that does not RESOLVE, a missing directory returns the same empty result as the claim being true; a disposition recorded from intent, not the diff, which the next reader trusts INSTEAD of the findings; a commit crediting a backlog item by TITLE while its filed reproduction still reproduces; and a subagent's COUNT or LIST, a lead**. That rule is the active statement; this one is kept for readers who remember it.*

## When a commit claims to close a backlog item, verify the claim against the item's FILED CASE before crediting it — a fix aimed at the item's title routinely lands the ADJACENT sub-case, passing every guard while the filed reproduction still reproduces, so merging closes a still-broken item as shipped

*Retired 2026-08-01 — superseded by **Reads as evidence, is not: an absence-claim citing a path that does not RESOLVE, a missing directory returns the same empty result as the claim being true; a disposition recorded from intent, not the diff, which the next reader trusts INSTEAD of the findings; a commit crediting a backlog item by TITLE while its filed reproduction still reproduces; and a subagent's COUNT or LIST, a lead**. That rule is the active statement; this one is kept for readers who remember it.*

`feature/gate-fidelity` commit `af8350f` (preserved at tag `archive/gate-fidelity`) claimed it
addressed "vouching across bundle boundaries (CRT-6J4P)". It did not. CRT-6J4P's filed case is a
*same-lineage* cross-bundle chain: the previously released bundle merged to develop, the new branch
was cut from it, so the anchor's `commit_reviewed` **is** an ancestor of HEAD — `git merge-base
--is-ancestor` returns 0 and rule 1b fires anyway. The branch's ancestor guard closes only the
sibling-BRANCH sub-case, which is CRT-8H3R's territory. Both items live in the same fix family and
cross-reference each other, which is exactly what makes the mis-credit plausible. Diagnostic: before
crediting a fix, re-read the item's filed reproduction and ask whether the guard as written *fires*
on it — a shared area, a shared `refs:` line, and a confident commit message are not evidence.
Mirror of [[When reconciling a backlog item a PR *partly* shipped, read ALL that PR's build-plan
chunks before declaring any leg still open]] — that rule stops a shipped leg being reopened; this one
stops a broken item being closed. Discovered git-state audit (2026-07-19). Relates to Complete
Delivery (#2), Honest Confidence (#5), Validate Before Propagating (#15).

## A test written against a not-yet-implemented flag can pass because the arg guard REJECTED it — assert success before asserting absence

*Retired 2026-08-01 — superseded by **A passing assertion may be satisfied by something other than the property — an unimplemented flag passes because the arg guard REJECTED it (assert success BEFORE absence); a prose SUBSTRING stays green under any longer sentence containing it (when prose changes meaning, grep tests asserting FRAGMENTS, not just failing ones); a proxy passes every test you thought to write — gate on the named event**. That rule is the active statement; this one is kept for readers who remember it.*

Pre-implementation, 11 of 15 new tests failed and 4 passed; two of those passes were free. `--brief-only`
was unrecognized, so the command exited 2 having done nothing — and "no handoff was written" is true
when nothing ran. Absence-of-side-effect is precisely the assertion that cannot distinguish "correctly
skipped" from "never executed." Rule: any test whose assertion is a *negative* (file not created, state
not mutated) asserts `returncode == 0` (or equivalent liveness) first. The detection habit that caught
it: on a test-first run, read **which** tests passed and why, rather than being satisfied that most
failed. Sibling rule for fixtures: to detect "was this rewritten," the fixture must make a rewrite
*observable* — comparing hashes of a file that gets rewritten to identical content proves nothing, so
seed distinct sentinel content. Relates to Tests Are Contracts (#1).

## When a fan-out render keys on a field that isn't unique, test the collision case — and a self-authored adversarial pass inherits the author's blind spots

*Retired 2026-08-01 — superseded by **A fixture's world is narrower than the requirement it certifies — the COMMON instance narrows the requirement to itself, so check coverage against its stated BREADTH; the framework's OWN state stands in for the propagated contract, so assert what reaches consumer repos; one moment stands in for the procedure's transitions; and the collision case is unwritten when the fan-out key is not unique**. That rule is the active statement; this one is kept for readers who remember it.*

When a renderer (or any fan-out) groups/sub-sections by a field, the field's NON-uniqueness is the bug to test for. REL-4T8N-B (release-tooling, 2026-06-04) rendered `release-notes.md` as one `### ` sub-section per change-log ENTRY within a release — correct for distinct scopes (v2.0.5's four), but a single scope split across two change-log entries (v1.4.0's two `scope=v1.4` entries) produced two identical `### v1.4` headings, *worse* than the old collapse. My own new tests covered distinct-scope and no-scope multi-entry but NOT same-scope-multi-entry; the parallel adversarial-verification workflow I launched ALSO missed it — because I wrote its edge-case list, so it inherited my framing. The independent cumulative Critic caught it by reasoning from the actual committed `release-notes.md` artifact (it diffed the real file), not from my fixtures. Fix-shape: (1) when a fan-out keys on a field, add an explicit test for the field-COLLISION case (≥2 inputs sharing the key) — the correct model was "group by the key first" (`_group_release_entries_by_scope` merges same-scope, splits distinct); (2) a self-authored adversary only escapes the author's blind spots to the extent its prompt does — the durable catch is the *independent* reviewer working from real artifacts, not a skeptic whose checklist you wrote. Discovered release-tooling REL-4T8N-B (2026-06-04, develop). Relates to Independent Review (#14), Tests Are Contracts (#1), and Validate Before Propagating (#15).

## A subagent's reported COUNT or LIST is a lead, not ground truth — verify before a blanket edit

*Retired 2026-08-01 — superseded by **Reads as evidence, is not: an absence-claim citing a path that does not RESOLVE, a missing directory returns the same empty result as the claim being true; a disposition recorded from intent, not the diff, which the next reader trusts INSTEAD of the findings; a commit crediting a backlog item by TITLE while its filed reproduction still reproduces; and a subagent's COUNT or LIST, a lead**. That rule is the active statement; this one is kept for readers who remember it.*

When a subagent (Explore/general-purpose) reports an enumeration you're about to act on mechanically — "there are N occurrences of X", "these 4 call sites", "this list of files" — confirm it with a direct `grep -c`/`grep -n` before a `replace_all` or any uniform operation that assumes the count is complete. In v2.0.0 Chunk 5 an explore agent reported "4 lazy lib-import sites"; a direct grep found 5 (it missed `cmd_accept_operator_verification`). A blanket edit trusting "4" would have left the 5th site on the old `tools/`-relative path — a silent miss, not a loud failure. The verification is one cheap grep; the failure mode (an unedited site that looks edited) is expensive and invisible. Fix-shape: for any agent-reported set that drives a sweep, re-derive the set yourself with the precise query right before the sweep. Discovered v2.0.0 Chunk 5. Relates to Validate Before Propagating (#15) and Honest Confidence (#5).

## A plugin skill with unparseable YAML frontmatter loads with ALL metadata silently dropped — validate it in CI

*Retired 2026-08-01 — sentinel `tests/test_plugin_manifest.py::TestAllPluginSkillFrontmatter` passes, so the failure mode this warned about is structurally enforced.*

When shipping plugin skills (`skills/<name>/SKILL.md`), a frontmatter YAML parse error does NOT fail loud — the loader drops EVERY frontmatter field and the skill loads unusable (no `description`, not discoverable/invocable as intended). The unit suite is blind to this: it exercises skill *behavior* via direct subprocess/lib calls, never the loader's frontmatter parse, so the suite stays green while the skill is broken. v2.0.0 Chunk 6 shipped three reader skills (discovery/planning/reflection) whose `description:` value held an unquoted `: ` (colon-space) — YAML reads that as a nested mapping → parse error → empty metadata — and it went unnoticed for a chunk until `claude plugin validate` surfaced it during the Chunk-11 dogfood. Fix-shape: parse every `skills/*/SKILL.md` frontmatter with `yaml.safe_load` in a test AND run `claude plugin validate <path>` as part of plugin-chunk verification; quote any scalar containing `:` / `#` / `|` / leading-special chars. Discovered v2.0.0 Chunk 11. Relates to Validate Before Propagating (#15) and Tests Are Contracts (#1).

## When generalizing or detecting "across all cases", the COMMON / AVAILABLE instance silently narrows the requirement to itself — check coverage against the requirement's stated breadth

*Retired 2026-08-01 — superseded by **A fixture's world is narrower than the requirement it certifies — the COMMON instance narrows the requirement to itself, so check coverage against its stated BREADTH; the framework's OWN state stands in for the propagated contract, so assert what reaches consumer repos; one moment stands in for the procedure's transitions; and the collision case is unwritten when the fan-out key is not unique**. That rule is the active statement; this one is kept for readers who remember it.*

Writing general guidance, a transport-/protocol-neutral template, or a "detect X everywhere" scan, the most common instance (HTTP for APIs, Python for a code scan) and the most *available* primitive (a `*.py`-only `has_imports`, a Read/Glob-only skill) try to colonize the general framing — you ship something that silently covers only the common case. Before calling it general: state the requirement's stated breadth explicitly and check each instance (library/SDK, on-device, CLI — not just network/HTTP; JS/Go/Java manifests — not just Python imports), and confirm the primitive or tool-grant you build on can actually *see* that breadth (a Read/Glob skill can't grep source; a `*.py`-only scanner can't read `package.json`). Extend the primitive (or attribute the unreachable signal to the surface that can reach it) rather than narrow the requirement to fit the tool. Caught three times in one feature: the api-contract template framed HTTP-only, doctor #9's prose implied a grep its tool-grant lacked, and the advisory probe's base primitive saw only Python. Relates to Complete Delivery (#2), Honest Confidence (#5 — don't let prose imply a reach the tool grant lacks), Bring Expertise (#7), and [[detection of structural characteristics should not rely on mechanistic surface markers]].

## A test asserting the framework repo's OWN state instead of the propagated contract gives false coverage — assert the contract that reaches consumer repos

*Retired 2026-08-01 — superseded by **A fixture's world is narrower than the requirement it certifies — the COMMON instance narrows the requirement to itself, so check coverage against its stated BREADTH; the framework's OWN state stands in for the propagated contract, so assert what reaches consumer repos; one moment stands in for the procedure's transitions; and the collision case is unwritten when the fan-out key is not unique**. That rule is the active statement; this one is kept for readers who remember it.*

The plugin's defaults reach onboarded products only through **canonical carriers**, never through this framework repo's own files: gitignore defaults via `lib/core.py::GITIGNORE_ENTRIES` (written into a product `.gitignore` by `update_gitignore` on onboard/doctor) and its import-light inline mirror `bin/prawduct-hook::_SESSION_GITIGNORED_PATHS` (the `_untrack_session_files` set); format legends via `templates/`; default-behavior changes via `methodology/session-digest.md`. Dogfooding this repo creates a blind spot: state the framework repo *also* generates (because the plugin is active here too) can be made quiet by a hand-edit to *this* repo's tracked files, which does nothing for products. The work-model vocabulary index (PR #71) is the canonical instance. Two hooks generate `.prawduct/.work-model-index.json` on every session in *every* `.prawduct/`-bearing repo (SessionStart `build-index`, UserPromptSubmit `user-prompt-submit`). PR #71 correctly intended it ephemeral/gitignored and added the ignore line to this framework repo's own `.gitignore` (line 25) — but never to `GITIGNORE_ENTRIES` or `_SESSION_GITIGNORED_PATHS`. Result: `update_gitignore` never wrote an ignore rule for it into any product, so every onboarded repo regenerated the file each session and carried it as permanent untracked noise (the reported symptom). The damning part is the *test*: `tests/test_work_model_hooks.py::test_index_is_gitignored` existed and **passed continuously** — because it asserted `(ROOT / ".gitignore")`, i.e. *this repo's* file, the one surface that has no bearing on products. A green guard test on the wrong surface is worse than no test: it reads as "covered." Discovered 2026-06-25 from a user report that the file was noisy in both this repo (where it's actually fine) and consuming repos (where it wasn't). Fix: add `.prawduct/.work-model-index.json` to both contract lists (`TestSessionGitignoreMirror` pins them in sync); existing products self-heal — `update_gitignore` adds the line next session, and `_untrack_session_files` `git rm --cached`s it if a repo already committed it. The regression net was rebuilt to assert the *contract*: `test_index_is_in_gitignore_contract` (the entry is in `GITIGNORE_ENTRIES`) and `test_update_gitignore_writes_index_line` (end-to-end — a freshly reconciled product `.gitignore` contains the line). Fix-shape, general: when a feature ships any propagated default (an ignore line, a format field, a digest behavior), write the regression test against the canonical carrier AND an end-to-end propagation into a fresh `tmp_path` product — never against the framework repo's own dogfood copy; if the only assertion touches a file under this repo's root, ask "would this still hold in a *product* repo?" and if not, the test is false coverage. Same root shape as [[A format's schema legend lives in `templates/` (scaffold-only) — adding an optional field reaches already-onboarded repos only via a migrate/triage *refresh* step, not the template]] — anything living only in the framework repo does not reach onboarded repos. Relates to Tests Are Contracts (#1 — a contract test must test the contract, not the producer's private copy), Validate Before Propagating (#15), Complete Delivery (#2), and Clean Deployment (#10 — dev-time dogfood state masking a product-facing defect).

## A test that asserts a SUBSTRING of prose stops being a contract the moment someone writes a longer sentence containing it — when prose changes meaning, grep the tests that assert fragments of it, not just the ones that fail

*Retired 2026-08-01 — superseded by **A passing assertion may be satisfied by something other than the property — an unimplemented flag passes because the arg guard REJECTED it (assert success BEFORE absence); a prose SUBSTRING stays green under any longer sentence containing it (when prose changes meaning, grep tests asserting FRAGMENTS, not just failing ones); a proxy passes every test you thought to write — gate on the named event**. That rule is the active statement; this one is kept for readers who remember it.*

`test_pr_reviewer.py` asserted `"always run" in content` under a docstring reading "R-2 stays unconditional." Chunk 02 rewrote that prose to "always run **on this backend**" — the opposite claim — and the assertion sailed through a green 2453-test suite. A failing test renegotiates its contract in the open ([[When a deliberate change turns a passing test red, renegotiate the contract in the open]]); a test that keeps passing while its stated contract inverts is strictly worse, because nothing signals. So: when an edit changes what a prose surface *means*, `grep` the test corpus for fragments of the old sentence and re-read every hit against its docstring; and prefer assertions that pin the *discriminating* clause (`"always run on this backend"`), not a prefix any successor sentence will contain. Corollary: a chunk planned `doc-only` is mis-typed the moment its prose contradicts a test — re-type it rather than leave the substring passing. Discovered skills-cutover-awareness Chunk 02 (2026-07-20). Relates to Tests Are Contracts (#1) and Honest Confidence (#5).

## A rationale you reached for to defend a decision you'd already made is the one to verify BEFORE writing it into a durable spec — the reach itself is the tell

*Retired 2026-08-01 — superseded by **Anything in a durable artifact that one command could check is a CLAIM — an identifier, a count, a `file:line`, or a facet value, not just a rationale — so run its falsifying query first. The rationale you REACHED FOR to defend a decision already made is the one to verify, and a CORRECTION is itself a completeness claim: quoting the parent rule demonstrably does not prevent this**. That rule is the active statement; this one is kept for readers who remember it.*

Justifying "the janitor gets no post-cutover backlog context," I wrote into `skills/janitor/SKILL.md` that its `allowed-tools` grants no `Bash(prawduct-hook *)`, so "the janitor surveys, it does not query services." The frontmatter fact was true and the inference was unsound: Step 1 of the same file already instructs `prawduct-hook review-stats`, and every sibling skill instructing a hook call carries the matching grant — janitor is the sole exception, i.e. an oversight. The decision was actually made on other grounds (the owner's W1 read-through-cache ruling); the grant story was recruited afterward to make it look principled, and it laundered a bug into a recorded architectural position where a later builder could cite it. So: when you notice yourself supplying a *second* reason for a decision already settled, treat that reason as unverified — read the mechanism it rests on (Principle 24), and if it turns out to be a defect, file the defect and rest the prose on the premise that actually decided it. This is the requirement-invention tripwire (#6) in inverted form: not a requirement invented forward into code, but a rationale invented backward into a spec. Discovered skills-cutover-awareness Chunk 03 (2026-07-20, Critic warning). Relates to [[A decision reversed mid-chunk leaves stale rationale in prose you just wrote]] and Reasoned Decisions (#4).

## A falsifying query is itself a mechanism and can carry the defect it hunts — when proving a claim is ABSENT from a tree, normalize the text before searching, because line structure is not semantic structure

*Retired 2026-08-01 — superseded by **A completeness claim asserts the falsifying COMMAND now returns nothing — never a count of sites fixed, which is true of any prefix of the real set. The query is itself a mechanism and can carry the defect it hunts: normalize the text before searching, because line structure is not semantic structure, and query the CONCEPT, not the phrasings you already found wrong**. That rule is the active statement; this one is kept for readers who remember it.*

Fixing a "prose asserts a property the code lacks" finding (the REST-point meter charges per transport *method*, not per HTTP request, so its total is a floor), I corrected the sites the review named, ran `grep -rn "every.*REST call" plugin/`, got one hit — my own corrective comment quoting the phrase — and recorded the sweep as complete in a change-log entry. Four sites survived, because the claim **wraps across line breaks** (`charges every\n       migration REST call`) and a line-based grep structurally cannot match it. One of the survivors was `skills/backlog/migration-scrub.md`, which ships to every consumer and is the operator's runbook for an irreversible ~900-issue migration. The reviewer's own grep missed a fifth site for the same reason. Replacing it with a whitespace-normalized sweep (`" ".join(text.split())`, then regex) found every one. The general form: **a negative result is only as strong as the query's ability to represent the claim**, and the default text tools represent *lines*, while prose claims are sentences that wrap, hyphenate, and get reflowed by formatters. So: to prove absence, flatten first; and treat "my grep found nothing" as evidence about the grep until you have shown the query matches a known-positive. Sharpest form of the tell — I wrote a comment warning that a mechanism overclaims what it measures, and in the same commit used a verification method that overclaimed what it checked. Discovered 2026-07-28 (v3.2.0 develop-integration, verify-resolutions warning). Relates to [[A fix lands at the instance a review named; the defect lives in the class]], [[When a guarantee names a specific event, gate on THAT event]], Honest Confidence (#5), Validate Before Propagating (#15).

## When a guarantee names a specific event, gate on THAT event — a signal that usually co-occurs with it passes every test you think to write, because you wrote them believing the proxy

*Retired 2026-08-01 — superseded by **A passing assertion may be satisfied by something other than the property — an unimplemented flag passes because the arg guard REJECTED it (assert success BEFORE absence); a prose SUBSTRING stays green under any longer sentence containing it (when prose changes meaning, grep tests asserting FRAGMENTS, not just failing ones); a proxy passes every test you thought to write — gate on the named event**. That rule is the active statement; this one is kept for readers who remember it.*

Session-handoff Chunk 01 introduced `.handoff-notes.md`, a model-authored note consumed into the generated handoff and then deleted. The stated guarantee — written into the docstring, the call-site comment, `architecture.md` and the change-log — was "a note is deleted only once its text is durably in the handoff." The code gated the delete on `handoff_written`, which is true whenever *any* section produced content, while the notes reader collapsed absent / empty / **unreadable** into one empty string. So an undecodable note was deleted with its text carried nowhere — unrecoverable, through the documented happy path — and the chunk's own test walked that exact path while asserting nothing about the notes file. All three Critic reviewers found it independently, which is the tell: convergence from unrelated lenses means it was never subtle, the author was reading their own comment instead of the code. So: when you write "only after X," find the expression that *is* X and gate on it; if X isn't representable, that absence is the finding — make it representable (here, the reader returning a state rather than a string whose emptiness meant three different things). Corollary: an invariant asserted in N prose locations is N places that will keep asserting it after the code stops honoring it, so the prose count is a risk multiplier, not evidence. Discovered session-handoff-continuity Chunk 01 (2026-07-26, Critic warning ×3). Relates to [[A test that asserts a SUBSTRING of prose stops being a contract the moment someone writes a longer sentence containing it]], Tests Are Contracts (#1), Independent Review (#14).

## When you write a CORRECTION it is itself a completeness claim — run the query that would falsify it across the whole class BEFORE asserting the fix, because a correction that repaired only the site a review named is false about its own subject, and quoting the parent rule demonstrably does not prevent this

*Retired 2026-08-01 — superseded by **Anything in a durable artifact that one command could check is a CLAIM — an identifier, a count, a `file:line`, or a facet value, not just a rationale — so run its falsifying query first. The rationale you REACHED FOR to defend a decision already made is the one to verify, and a CORRECTION is itself a completeness claim: quoting the parent rule demonstrably does not prevent this**. That rule is the active statement; this one is kept for readers who remember it.*

Confirmed 2026-07-31 (fleet-migration-triage), four instances in one session, each one occurring
*after* the parent rule had been quoted. **(1)** Struck the `legacy.py` retirement leg in `BKL-6M4T`
and wrote a change-log entry presenting the fix as complete; the same instruction was still live in
four other surfaces, including `migration-scrub.md` — a runbook an agent **executes**. So the repo
contradicted itself across five surfaces with the correction applied to one, and the executed one
still said to retire it. **(2)** Told that a warning box transcribed a figure the box itself
forbids, deleted the one figure the review named and left three more in the same block. **(3)** Then
wrote *"No figures are quoted here on purpose"* directly above the survivors — the correction was now
false about itself, strictly worse than the defect it replaced, because a reader trusts the bolded
claim and skips the instrument. **(4)** Carried in from the same day's earlier session: the
`learnings-entry-shape` guard, repaired three times, each repair addressing the instance the review
named.

**Why a third rule rather than a louder restatement of the two parents.** Both parents already exist
here — [[A fix lands at the instance a review named; the defect lives in the class]] and
[[A completeness claim states the COMMAND that would falsify it and asserts that command now returns nothing]].
They were quoted in a session reflection and in a commit message on the day of the violations, and
the violations followed each quotation within minutes. Restating them is therefore proven not to be
the fix. What was missing is the **composition**, and specifically its trigger: the parents fire on
"closing a finding" and "claiming completeness," neither of which felt like what I was doing. Writing
a correction did not present itself as either — it felt like *repair*, which is why nothing engaged.

Operative form: the moment you write text asserting that other text was wrong, you have made a claim
about the whole class of that wrongness. Before committing it, grep for the correction's own subject —
the file name, the instruction, the figure, the claim — and confirm the query returns only the sites
you fixed plus the legitimate contexts. For prose corrections this costs one grep. All four instances
above would have been caught by it. Relates to Root Cause Discipline (#16) and Honest Confidence (#5)
— the false-about-itself case is the sharp one, because it converts a partial fix into an active
misdirection.

---

## Enumerate the sites answering a question by GREP, never by memory — and the grep is itself a site

A fix that threads a resolved value through the two call sites you remembered leaves the third
reading the old source, and the comment you write above it ("both fields") is accurate for exactly
one commit — the same shape as the bug being fixed, one field over.

**Four instances, all on the branch that wrote this rule down.** The first two were value-threading.
The third and fourth were the *query* carrying the defect it hunted:

- A find-and-replace over quoted tree-id literals in `test_coverage_algebra.py` fixed sixteen of
  seventeen fixtures. The seventeenth built its ids as `f"t{i}"` — a literal sweep is a **prefix**
  of the real set wherever the code also *constructs* the string.
- A sweep for prawduct-internal ids in emitted text scoped itself to literals passed **as
  arguments** to `print`/`error`/`log_diag`/`TransportError`, and reported clean. Emitted text is
  not a syntactic category: it missed a string returned and printed by its caller
  (`_worktree_redirect_note` → `cmd_stop`), one appended to a list printed at session end (the
  designer-handoff waiver note), and one assembled into a document written for a human (the
  restructure-preview title). Two independent reviewers found the first; only widening to *every
  non-docstring literal, read by eye* found the other two.

So the rule has a second half. A completeness claim rests on a falsifying command, and the command
is a mechanism that can be wrong in the same way the code is: too narrow, matching the shape you
already have in mind. Widen it until it would catch a case you have not thought of, and treat a
clean result from a query you wrote yourself as the weakest evidence available.
See [[a completeness claim asserts the falsifying command]].

---

## A filed item's stated MECHANISM is a hypothesis, not a finding

#532 was titled *"stage-less items vanish from counts"* and its Repro said so. That is not what
happened. Stage-less items **were** counted and landed in the `(none)` stage bucket — which the
item itself reported seeing at 64. What vanished was anything failing `is_prawduct_issue`: no
namespaced label **and** no `prawduct:` block, which is how a human-filed or product-filed issue
arrives.

**The item's own evidence contained the disproof.** It recorded `total` moving 374 → 383 after
labelling nine issues, and a stage-bucket bug cannot change a total. Nobody read it that way,
including the reporter, because the correlation was clean: labels went on, the count went up.

The catch came from measurement, not from re-reading. `gh issue list --state open` said 159 and
`counts` said 158 — a **one**-item gap where the item predicted nine. That forced "which one?", and
the answer (#533, filed by a human, no block) was the mechanism. The plan had already inherited the
wrong number into a `[DECISION:]` block predicting 158 → 167, and would have shipped it into the
change-log as measured fact.

Pairs with [[when you correct an inherited number recount the SET]] — same failure, one rung
earlier: that rule is about re-measuring inside an inherited frame; this one is about the frame
arriving in the item text and reading like a finding because it sits under a "Problem" heading.


## A token budget is raised only when the framework is provably better FOR THE RAISE and upleveling has no headroom left

Two Critic controls had to land in files with 2 and 12 words of headroom. Word-shaving looked
hopeless, and the estimator is `len(text.split()) * 1.3`, so reflowing buys literally nothing.

What worked was cutting whole classes of content rather than tightening sentences:

- **Definitions another file owns.** `goals-1-3.md` told the reviewer to read `record_lint`'s output
  and *never re-derive it*, then spent forty words re-deriving what each lint id means — including a
  400-char threshold no reviewer applies, because code computes it. `review-protocol.md` did the same
  with the four Framework-Specific Checks, immediately after pointing at `framework-checks.md` for
  the definitions. Both cuts are safe *because* the file already ordered the reader elsewhere.
- **Machine output quoted verbatim.** A WARNING's exact wording, reproduced in prose, when the
  reviewer composes the message anyway.
- **History.** "Reviewer-model tiering was removed" — what a mechanism *used* to do, carried in an
  instruction payload where it can only cost. Note the near-miss: "an undeclared repo is never
  reviewed less than before" *looks* like the same class and is not — it is a **live invariant**,
  still asserted in `review-cycle.md`. Cutting it was right for a different reason (the fact has one
  home and the payload already points at it), and filing a live invariant under "history" is how a
  true statement gets deleted next time on a false premise. Check which one you have before cutting.
- **Rationale aimed at a maintainer, inside a payload aimed at a reviewer.** The most self-defeating
  instance: a citation explaining *why this file is short*, in the file whose purpose is minimum
  reviewer payload.

Both files ended up smaller than they started while each gained a check.

**Two guards caught real damage, and both were worth more than the tokens saved.** Deleting Goal 4's
`**Norms**` bullet as a "pure restatement" broke `test_project_preferences_blocking`, which contracts
on a single line carrying both `project-preferences` and `blocking` — that bullet is the only line
satisfying it. The budget comment recorded a previous editor doing exactly this and reverting; I did
it anyway, which is why the note now names the trap instead of narrating the incident. Separately,
compressing "the chunk *inferred from* build-plan Status" to "the chunk from build-plan Status"
broke a guard pinning that the assumption shape names both its causes — a compressed reading there
had previously produced a recurring false BLOCKING no `--chunk` could clear.

The general form: **prose that reads as redundant may be the only witness to a contract.** Uplevel
aggressively, then run the suite — the guards, not the reading, decide what was redundant.

## Exactness is owed to a number something RELIES ON for a decision, not one something merely READS

Instance, 2026-08-02: restoring one word to a budgeted file moved its token reading by 1, which then
had to be updated in `LAST_MEASURED_TOKENS`, a change-log paragraph, and a build-plan Status
paragraph. Three edits, one word, and no decision anywhere depended on the digit — the *ceiling*
assertion is what decides. The prose figures were removed and the table left owning the reading.
`LAST_MEASURED_TOKENS` itself is the open question: it is an exact-equality pin that drives no
branch, so every edit to a budgeted file pays a mandatory update whose only function is to force the
author to notice. That may be worth it, but it is exact-number churn by construction and should be
decided deliberately rather than inherited.

## A rule you must RECALL at the right moment is its weakest form

Three failures in one work cycle, all of the same shape: the rule was **in context** and the instance
went unrecognised.

1. Deleted a bullet a budget comment explicitly warns against deleting — while reading that comment.
2. Missed the second site on three of four review warnings, against a *second-site sweep* rule this
   same branch wrote two chunks earlier.
3. Wrote a retire rule counting PR reviews from a store PR findings never reach — about a hundred
   lines below my own paragraph explaining that this ledger is per-worktree and gitignored, which I
   had just applied correctly to a different item.

The tempting conclusion is "read more carefully." The evidence says otherwise: **every catch came
from something that runs.** The suite caught both bad cuts. `render-dispositions` caught a
disposition claiming a fix I had not yet made. Two independent reviewers caught a schema assumption.
Nothing was caught by remembering a rule at the moment it applied — including rules authored minutes
earlier, because familiarity reads as compliance.

So the operational form is not vigilance but conversion: when a rule governs a class of claim that a
query could settle, spend the effort building the query rather than restating the rule. This is
exactly what the stable-token mechanism does for control yield — it turns "did this check ever fire?"
from a memory into a grep — and why the structured `check:` field is the better version still.

Corollary for review economics: this is an argument for *mechanising*, not for more review rounds.
Two of the three failures were caught by a reviewer, which is expensive; the first was caught by a
test, which is free and repeats forever.

## The RHETORICAL ROLE of a sentence can select its content over a fact you already hold

`pr/SKILL.md`, one paragraph, written in a single pass:

> The durable record of a review is the *fact*, and facts live in the shared evidence store …
> **Known cost, accepted:** PR findings are therefore not queryable from the shared store …

Both sentences are mine, two apart. The first is false for PR reviews (`evidence.KNOWN_KINDS` is
`{review, resolution, disposition}`, all written by `critic-consolidate`; a PR review lands in a
gitignored per-worktree ledger). The second states that correctly. I had been corrected on exactly
this by a review round the same day.

This is not forgetting, and no recall-based guard would have caught it — I *held* the fact, and
demonstrated so in the same paragraph. What happened is that the two sentences had different jobs.
The justification slot wanted a reason that made the decision sound principled, and "the durable
record lives in the shared store" is a better-sounding reason than "it lives in a gitignored
per-worktree ledger event." The caveat slot wanted a limitation, and there the true fact fit.

The operational form: when writing a rationale, identify the **load-bearing clause** — the one the
decision rests on — and check that one against the mechanism, separately from reading the paragraph
for sense. Reading for sense will pass it, because it reads well; that is the property that selected
it. Pairs with [[A rule you must RECALL at the right moment is its weakest form]]: that rule covers
rules you fail to apply, this one covers facts you apply *away from* where they are needed.

## A disposition claiming "fixed" must restate the finding's own predicate

**Where it came from.** `fix/drift-burndown` Chunk 01 (#193), 2026-08-02. The chunk review's R-3
said: *the `plugin/` root fallback means the check cannot see the root-`bin/` → `plugin/bin/`
relocation its own docstring cites as the reason it exists.* The fallback resolves a bare
`bin/prawduct-hook` against `plugin/bin/prawduct-hook`, so the motivating defect was invisible.

**What I did.** Scoped the fallback by FILE — allowed only for files under `plugin/` and for build
plans under `.prawduct/artifacts/` (which carry a declared `build_plan_ref_root: plugin`). That
immediately surfaced **seven real defects**: every `tests/scenarios/*.md` told a reader to run
`python3 bin/prawduct-hook init-product …` from the repo root, where no such file has existed since
the relocation. I fixed them, dispositioned R-3 as "fixed beyond the ask", and wrote in the
change-log: *"the reviewer asked for a hedge on the claim; the claim turned out to be fixable
instead."*

**Why it was wrong.** The motivating defect lived in five **skills'** prose and `allowed-tools:`
grants. Skills live at `plugin/skills/*/SKILL.md` — **inside the scope I retained**. Two of the
three covered forms, on the exact files, of the exact class, still resolved. The finding was
untouched. The verify pass caught it by checking the tree rather than the fix notes.

**The mechanism of the error.** I verified *the fix I made* instead of *the finding as stated*. My
question was "did offenders appear, and are they real?" — which returns yes for a neighbouring
surface. R-3's question was "can the check see this specific relocation, in these specific files?"
Seven genuine fixes made the false claim feel earned; had the scoping found nothing I would have
looked harder.

**Aggravating context.** This shipped inside a batch whose subject is *records asserting what the
code does not support*, in the chunk building the detector for that class. The failure mode does not
care that you are writing about it.

**The closing fix, and why it is better than the hedge R-3 asked for.** Scope by FORM as well as
file. The fallback is justified by *naming* a file — plugin docs refer to siblings the way the
plugin ships them (`skills/critic/review-cycle.md`, `methodology/building.md`, dozens more) — and is
justified for nothing when *running* one, because a reader executes from a working directory, which
in this repo means `plugin/bin/prawduct-hook` (all fifteen in-tree invocations say so). Denied to
`command` and `allowed-tools`. That bought four more live fixes in build plans and is pinned by
`test_the_plugin_fallback_is_denied_to_invocation_forms`, red-verified by restoring the wider form.

**The rule.** A "fixed" disposition restates the finding's predicate and demonstrates it false,
ideally as an assertion. Tell: the fix note argues from what the change caught rather than from what
the finding said.

## Scope an exemption by the property that justifies it, not by the container

**Same chunk, the structural half of the above.** The `plugin/` fallback's rationale is a verb —
*naming* a file — but the boundary I wrote was a path prefix: `containing.startswith("plugin/")`.
Those coincide for most files and diverge exactly where the defect lives, because a skill both names
sibling files (legitimate) and invokes executables (not). Container-scoping looked complete: it had
a stated rationale, a declared config backing half of it (`build_plan_ref_root`), and it produced
real catches.

**The generalisation trap.** Going from "plugin docs name paths as the plugin ships them" to "files
under `plugin/` get the fallback" is one step, feels like the same sentence, and silently widens the
exemption from a *form* to a *location*. The correct boundary needed both: entitled file **and**
non-invocation form.

**Tell.** The exemption's boundary is expressed as a path prefix while its rationale is expressed as
a verb. When those two shapes disagree, the prefix is the approximation.

## Citing a named procedure is a claim that you ran it

**v3.2.3 release prep, Critic W-2.** Classifying `drift-burndown` into the release, I wrote that it
was classified "by the runbook's step-2 **code test**" and ran
`git merge-base --is-ancestor 6f443a2 v3.2.2`. Step 2's test is content-based —
`git show <prev-tag>:<path>` — stated in a call-out box I had read earlier in the same session.

**Why the substitution is not harmless.** The two tests agree under whole-develop promotion and
diverge exactly under the pruned cherry-pick path the same release plan contemplates: a cherry-picked
commit is not an ancestor while its content *is* in the previous release's tree, so ancestry reports
"unreleased" for work that shipped. The conclusion was right; the warrant was not. In a document that
reads as precedent that is the more durable defect — the next reader re-derives conclusions and copies
warrants.

**The mechanism.** Two independent recalls ran and neither was checked. I reached for the test I *use*
for "did this land" (ancestry) and attached the authority I *remembered* having read (step 2). Each
recall supplied the other's confidence. Retrieval-over-generation names the fix, and the file had been
open twenty minutes earlier; the step whose name I borrowed was the one thing I did not re-open.

**Repair shape matters.** The cheap fix — hedge the citation to say what actually ran — leaves the
classification resting on the substitute. The content test was run instead, and both files the scope
creates are absent from `v3.2.2` (`learnings-obligation` appears 0 times there against 5 on `develop`).

**Tell.** A sentence names a numbered step, a runbook, or a spec section as the warrant for a check
you performed from memory. If you cannot quote the step, you are citing your recollection of it.

## An edit that changes a count falsifies more sentences than the one you noticed

**Same commit, Critic W-4.** Adding an eleventh row to the release classification table falsified two
sentences. I caught the consumer CHANGELOG stating as a "known limitation" the exact thing
`drift-burndown` Chunk 03 fixes — a genuine catch, and a release that ships a limitation and its fix in
the same notes is a real defect. Three sections above, in the same file and the same commit, "the ten
rows still partition the corpus" went untouched.

**The structural cause.** Finding one falsified sentence *feels like completing a search* rather than
starting one. The catch arrives with the satisfaction of thoroughness and generates no pressure to
enumerate; the instance found is simply the one being read at the time. This is the same commit
correcting one instance of a defect and committing another instance of it — the shape this repo has
now recorded repeatedly under different headings.

**The cheap mechanism, not applied.** When an edit changes a count or a set, grep the document for the
old value before committing. Better: state the relation rather than the number ("the table's rows still
partition the corpus"), since the claim never needed the count and the count is the part that goes
stale. The corrected sentence now carries an explicit *do not re-introduce a literal count here*.

**Adjacent instance worth carrying.** `check-releasability` could not have caught the CHANGELOG defect
at all — it grades **classification**, not **description**. A green gate remains evidence only about
what that gate measures.

## A green suite is evidence about the ONE environment that ran it

Added 2026-08-04, when this repo gained its first CI (`release-integrity` Chunk 05). The full suite
had been run three times locally first — on 3.12, 3.10 and 3.14 — precisely so the first push would
be a confirmation. It was red on both legs anyway, and none of the three causes was reachable from a
maintainer's macOS checkout:

1. **A guard reading `git ls-files` answers differently across `git commit`.**
   `tests/test_plugin_packaging.py` asserts every tracked top-level directory either ships or is
   explicitly excluded. `.github/` became *tracked* at commit time — after the last local run — so
   the guard could not see the thing it exists to guard until CI did. *"I ran the suite" and "I ran
   the suite against what I am about to commit" are different claims.*
2. **A test that searches git history by content reads a shallow clone as "never shipped".**
   `actions/checkout` defaults to `fetch-depth: 1`; `tests/test_norm_index_scaffold.py` runs
   `git log --all -S <row>` and got empty output, which it reported as a wrong scaffold row — an
   accusation against the code for a truncated checkout. Its author *had* anticipated unavailable
   history, but only via `returncode != 0`, and a shallow clone returns 0. The anticipated failure
   mode and the real one differed by one exit code. Fixed with `fetch-depth: 0` **and** an explicit
   `git rev-parse --is-shallow-repository` check, because the workflow line alone leaves the next
   shallow runner lying.
3. **Non-ASCII source through `python -c` dies under `LC_ALL=C` on Linux.** macOS always decodes
   argv as UTF-8; Linux uses the locale's codec, so an em-dash arrives as surrogates and the
   interpreter exits before reaching the assertion. Pass source as a **file** — source files are
   UTF-8 by language definition regardless of locale — so only ASCII crosses the command line.

**The generalisation.** All three are the same failure as the defect that scope existed to fix:
nothing verified what a *different* consumer receives. A single execution environment makes every
assumption it satisfies invisible.

## A guardrail whose anchors come from your MENTAL MODEL of a file is a second copy of the claim, not a check on it

A cross-file check written *specifically* to police the claim "these five classes are already
BLOCKING-rated in `goals-1-3.md`" stayed green while two of the five were rated WARNING there and a
third was not rated at all. Its anchors had been picked from the same mental list the false claim
came from, so the test asserted the belief rather than the file.

The repair was to split it: one guard for the classes the protocol genuinely rates (the citation
half), one for the classes the directive *escalates*, with the protocol's LOWER rating pinned so
stale escalation wording fails rather than passing quietly.

**It recurred one method over.** The sibling guard was fixed to judge per clause after a
five-verdict line let a downgrade pass; the same fix batch left its neighbour matching on the whole
line, where the vulnerable-dependency clause supplied a `**WARNING**` that made an `auth/authz`
promotion invisible. Verified by reverting the fix and re-running: the pre-fix assertion passes with
the promotion applied. A slack-carrying drift detector is indistinguishable from the drift it
watches for, and fixing one instance does not fix its siblings.

## Making a capability conditional on the RUNTIME retroactively conditions every existing test whose fixture touches it

Chunk 02 of `release-verification-false-reds` (2026-08-04). `_version_from`'s hand-rolled
TOML branch was replaced by delegation to stdlib `tomllib`, which is 3.11+ — chosen over a
section-aware hand-rolled reader because `architecture.md`'s LNG-5W8R forbids a gate
acquiring a language-specific parser, and its own interim rule says new gate code delegates
first. Below 3.11 a declared `toml` version file reports `unverifiable`, never `failed`.

The cost was priced as "one of three files unread on 3.10." The actual cost included the
test suite. `tests.yml` runs a deliberate `["3.10", "3.14"]` matrix, and **five** tests went
red on the floor leg:

* the new test for the fallback's absent-vs-present-but-unreadable split, built on
  `pyproject.toml` — it was that fix's *only* test, so on 3.10 the repair went from covered
  to red;
* four **pre-existing** happy-path tests (`test_agreeing_tree_is_ok`,
  `test_reads_the_tag_tree_not_the_working_tree`, `test_complete_release_exits_zero`,
  `test_accepts_bare_version`) whose only connection to TOML was the shared `_make_repo`
  fixture, which writes a `pyproject.toml` to mirror prawduct's real layout. None of them
  mentions TOML. None was edited by the change.

The `verify-resolutions` reviewer found the first and reported it as *the* problem — correct
about the instance, and the instance framing is the trap. What found the other four was
mechanical: substitute the loader lookup with one that returns `None` and run the whole
file. That is a 30-second check and it is the only thing that enumerates the set.

Two repairs, and the split matters. The new test was **rebuilt on a `json` file**, because
its subject (the reason a skipped file was skipped) has nothing to do with TOML — a test
should not inherit a dependency its subject does not have. The four pre-existing ones
genuinely assert an outcome that is only true on 3.11+, so they declare it with `skipif`,
paired with `test_the_floor_leg_degrades_instead_of_failing`, which asserts what 3.10 *does*
see: unverifiable, never failed, two readable files still verified. Guarding without that
companion would have left the floor leg with no coverage of the shape it actually runs,
which is the failure mode the guard was supposed to prevent.

Related: "A green suite is evidence about the ONE environment that ran it" — this is its
active form. There, the second environment finds the dependency. Here *you* introduced the
dependency, so you can enumerate it before CI does, and the enumeration is not optional
because the affected set is invisible in the diff.


## A test asserts what would BREAK, not what you just built — red-verify mechanically (break the subject, watch that specific test go red, restore), because the vacuous shapes all look correct while proving nothing

Three vacuous-pass shapes, all observed on `fix/ephemeral-agent-worktrees` (2026-08-05, #594):
an **exit code** asserted on a command that also exits non-zero for its own reasons (missing
args, no active review) — it passed with the guard entirely removed; an **equality** that also
held under the regression (`distinct_trees(mixed) == distinct_trees(plain)` where the fixture
hardcoded one tree for every fact, so it passed whether or not ephemeral facts reached the
coverage algebra — the single thing it existed to detect); and a **fixture built from ambient
env**, which passed whenever the shell happened to export the override the test meant to exclude.

Two were caught by the Critic, one by a red-verify pass. Each was written by someone who knew
the rule, which is why the remedy is mechanical rather than attentional: revert the subject,
run the specific test, confirm it goes red, restore. It caught something every time it was run
here and cost about a minute each time.

## Apparent duplication across governing docs may be the RECEIPT for a token budget already paid — check for a pinning test before cutting it, never fund a budget by moving prose between files, and raise the ceiling rather than spend redundancy twice

`plugin/methodology/building.md` carries a hard ceiling asserted in
`tests/test_v5_methodology.py`. Adding the two delegation hazards (+146 tokens) against 3 tokens
of headroom needed funding. The standing block looked like free redundancy — stated in
`session-digest.md`, `session-digest-slim.md`, `reflection.md` and `building.md`, with
`building.md` already pointing at `reflection.md` as the canonical rule. Cutting it turned two
tests red, and `test_standing_block_is_on_every_surface_that_claims_it`'s docstring said why:
*"building.md's token budget was FUNDED by relocating this rule's rationale"* — the redundancy
had been harvested once already, and the pin exists so a later trim cannot spend it twice.

Owner rule (2026-08-05): never fund a budget by moving prose to another file — total context
footprint is the only number that matters, so relocation satisfies the assertion and achieves
nothing. Order: simplify genuine duplication, then raise the ceiling and record what bought the
increase **at the assertion**, where the next person to hit it will be reading.

## A fixture's world is narrower than the requirement it certifies

The common instance narrows the requirement to itself. The framework's OWN state stands in for the
propagated contract, so assert what reaches consumer repos. One moment stands in for the procedure's
transitions. The collision case is unwritten when the fan-out key is not unique.

**2026-08-06 instance — the guard redefined the criterion, silently.** Acceptance criterion 4 of
`build-plan-critic-review-identity` read "the partial-path shape appears in exactly one place in the
codebase; no instruction surface spells it", and its guard test — written in the same breath — scanned
`plugin/skills`, `plugin/agents`, `plugin/methodology`. Six live sites outside that scan still spelled
the superseded name, including two artifacts the plan's own `governed_by:` block cites and a *pending*
`operator-verification.md` entry that would have made an operator record a false failure. The criterion
read as verified. The repair was to narrow the criterion to what the guard enforces and state what it
cannot — not to widen the guard, because the superseded name legitimately appears wherever prose
CONTRASTS it with the new one.

## When a trim is justified by the surrounding prose's OWN instruction

The dangerous cut is not the one you cannot justify — it is the one the file appears to endorse.

**First instance.** A record-lint explanation read as redundant under its own "raise it, don't restate
it" rule, and was the only witness to a two-shape contract.

**2026-08-06 instance — placement is not duplication.** `goals-1-3.md` had 6 tokens of headroom under
its budget, whose comment carries the standing rule "THE NEXT ADDITION TRIMS OR RELOCATES, IT DOES NOT
BUMP". That licensed compressing the closing "**Either way** your last line is consolidate's
`NEXT-ACTION:` … the clean pass is where it matters most" to a single word, on the reasoning that it
restated a rule 30 lines above. It did restate it — and
`test_goals_1_3_relay_survives_the_clean_pass_shorthand` exists precisely because the sentence sits
where a reader shortcuts the rule, and pins the phrase for that reason. The test caught it. The
question that separates a copy from a placement: *does this sentence sit where the rule gets skipped?*
The same instinct then reached for `review-protocol.md`'s reviewer-model prose — an emergency patch
with its own test — and stopped; that refusal is now recorded in the budget comment itself.

## When you add a validator because a value became DANGEROUS

**2026-08-06 instance.** A Critic review id became a filename component, so
`critic_consolidate._path_component_safe` was added and applied to both paths the change created.
`_archive_leftovers` — already in the same file — kept deriving an archive directory name from the
same id, read raw off disk, unchecked: `rev-../../escape` walked up out of the archive, `/tmp/x`
replaced the base outright, and because an archive failure degrades to DELETE it failed silently in
both directions. It reads the manifest raw deliberately (it must work when the manifest is unreadable),
so `validate_manifest`'s gate never covers it. Found by the review OF the commit that added the gate.
The generalisation is about attention, not about paths: reviewing your own change shows you the new
call sites, and the vulnerable one is the line that did not move.


## When a check's subject is a SET (files scanned, paths matched, items collected), assert the set is non-empty and contains what the check names — otherwise green means "nothing was looked at", and the check passes forever

**Pattern**: three independent instances in one session (2026-08-06), which is why this is a rule
and not an anecdote.

1. **`test_subprocess_safety.py` scanned `plugin/tests`** — a directory that has never existed on any
   branch. The repo's largest Python tree had never been checked for `shell=True`. The suite stayed
   green for the check's entire life, because a missing root yields no files rather than an error.
   Green meant *no files*, not *no violations*.
2. **A mutation-escape in `test_critic_dispatch_refusal.py`.** The test asserting that a
   governance-protected `.md` still dispatches passed under a mutation that keyed the refusal on
   `.md` instead of the predicate — because the fixture's `git add -A` had swept `.prawduct/`
   artifacts into the delta, so a stray non-`.md` path forced the dispatch. The judgeable `.md` the
   test named was never what made it pass.
3. **`_assert_no_dispatch_state`'s partial-reset clause** (caught by the Critic, not by me).
   It asserted the partials dir held no leftovers — but the sweep it guards returns early when there
   are no children, and every fixture had already had its partials removed. True at all three call
   sites regardless of behaviour.

**Root cause**: a predicate over a collection has two failure modes, and tests routinely cover only
one. "No violations in the set" and "the set is empty" are indistinguishable from the outside, and
the empty-set case is the one that fails silently *and* permanently — it never goes red, so nothing
ever prompts a look.

**Reusable rule**: any check that iterates — a scan root, a glob, a filtered list, a mutation-verified
assertion — carries a companion assertion that the iteration reached its subject. Concretely:
assert the roots exist (`test_scan_roots_all_exist`), assert a known member is present
(`test_scan_reaches_the_repo_test_tree`), and for absence-assertions **seed the thing that must
survive** rather than checking that nothing is there. Mutation testing is the cheap detector: mutate
the predicate and confirm the test that names it goes red — if a *different* test dies instead, the
named test is passing for the wrong reason. Instance 2 was found exactly that way.

**Ties to**: the free-edge/judgeable work in `gate-as-dispatcher-requirements.md` (instances 2-3) and
`.prawduct/change-log.md`'s 2026-08-06 entry (instance 1).


## A measurement with no POSITIVE CONTROL cannot support a claim — before believing "X costs nothing", confirm the instrument MOVES when it should, because a dead instrument reads zero for the treatment and the control alike, and zero is the answer you were hoping for. Tell: the confirming result arrived first try and the null case was never run

Chunk 02 needed to know whether a conditional request against GitHub's issues list is free. Polling
the `rate_limit` endpoint before and after three 304s showed `used` unchanged, which is exactly the
hoped-for answer, and it went into `cache-spec.md` §6 and two docstrings as "measured".

The positive control was run only because the number looked too clean: five *unconditional* 200s
also moved it by zero, and so did a 452-item rebuild. That is impossible, so the instrument was
dead — `rate_limit` was not reflecting these calls at all. Each response's own `X-RateLimit-Used`
header gave 134 → 135 → 136 across three 200s and a flat 136 across three 304s. Same conclusion,
but the first version of the evidence supported nothing.

The general shape: a null result is only informative if the measurement can produce a non-null one.
When the claim is "X costs nothing" / "Y never fires" / "Z is not called", the control is not
optional politeness, it is the whole experiment.

**Ties to**: `documentation/backlog-service-cache-spec.md` §6, which now records the *method* and
the dead instrument alongside the result.


## For every value you plan to PERSIST from a provider, verify the exact request that will later REPLAY it, not just the one that produced it — a verify-api step scoped to the plan's own mechanism confirms that mechanism and misses the one the plan got wrong

Chunk 02's build plan scheduled a `verify-api` step as step 0, specifically so the fakes could not
be built from recall. It asked four questions — what `since` filters on, whether it interacts with
`state`, whether closed items return, and the etag/304 behaviour — and all four came back clean.

The finding that mattered was not among them. The plan said sync would write `item.etag`; sync reads
the *list* endpoint. Asking "which endpoint will replay this stored value?" showed a list etag
returns 200 against `GET /issues/{n}` where that item's own returns 304, and the list body carries
no per-item validator at all. Chunk 05's revalidation would have missed on every read, spent a full
request each time, and looked like it was working.

The step was scoped to the plan's stated mechanism, so it could only ever confirm that mechanism.
The question that broke it came from the *persistence* direction: every value crossing from a
provider into a store is later replayed into some request, and that request is the one to verify.

**Ties to**: the DECISION block in Chunk 02 of `build-plan-backlog-cache.md`, and the two-validator
split now recorded in `backlog-service-data-model.md` §6.


## A test written RELATIVE to the constant it polices can never detect that constant being wrong — pin the absolute value when the value is a historical fact (a version a real store was stamped with, a format that shipped), because `CONST - 1` moves with CONST and passes at every setting of it. Tell: the mutation you expected to go red stayed green

`cursor.fetched_at` was added to the v2 cache schema without bumping past v2. A store written by the
earlier v2 code matches on version, is never discarded, and then fails every `_write_cursor` on the
missing column — `unavailable` on every sync, permanently, because the self-heal is gated behind the
version check that just approved the store. It happened on this machine and read as an empty result,
not as an error.

The fix was a bump to 3. The first test written for it seeded the store with
`PRAGMA user_version = cache.SCHEMA_VERSION - 1` — which looks careful, and is inert: mutate
SCHEMA_VERSION back to 2 and the fixture obediently writes 1, still behind, still discarded, still
green. The test could not fail for the reason it existed.

The seed had to be the literal `2`, because 2 is a fact about a format that existed, not a
expression over the current constant. Rewritten that way the mutation fails with the real
production error (`table cursor has no column named fetched_at`).

Generalises past versions: any fixture derived from the code under test inherits that code's bug.
Thresholds, limits, schema numbers, retry counts — if the test computes its input from the constant,
it is asserting internal consistency, which the defect also satisfies.

**Ties to**: `tests/test_backlog_cache.py::TestSchemaMismatch::test_the_v2_shaped_store_that_actually_shipped_is_discarded`,
whose docstring carries the do-not-relativise warning at the seed itself.

## A build plan can name a CODE IDENTIFIER it never opened

Two of one chunk's stated deliverables were wrong on mechanism, and both read as bookkeeping until
the named symbol was opened.

"Name all three fields in `_UPDATE_FACETS`" — `_UPDATE_FACETS` is the label *swap* loop: add the new
value, strip every other label sharing the prefix. Correct for `area` (exactly-one, wired to the
title); wrong twice over here. It would have written `affected:` labels for a field the spec puts in
the body block, and made setting a second tag silently remove the first, since `tags` is the one
deliberately multi-valued facet.

"The three cache columns and the `affected` index" — unimplementable as written. The intersection
runs *entry-contains-changed-file* (`plugin/lib` matches `plugin/lib/sync.py`), so the natural SQL is
`WHERE ? LIKE affected || '%'`, whose variable is on the side no index can help. It had to become a
normalised table (`item_affected(item_id, path)`) matched by equality after expanding each changed
file into its ancestor directories.

Why this is narrower than "plans go stale": a plan written at design altitude is usually right about
*intent* and is checked against reality when its prose is read. A named code identifier skips that
check — the sentence looks like an instruction rather than a claim, so it is followed instead of
verified. Both errors here were caught by the same move (open the symbol before editing it), and
neither would have been caught by re-reading the plan.

**Ties to**: `plugin/lib/backlog/core.py` (`_UPDATE_MULTI_FACETS` / `_UPDATE_BLOCK_FIELDS`, the
SEC-2 allowlist's third and fourth categories); `plugin/lib/backlog/cache.py` (`item_affected` and
the comment stating the query direction).

## A VALIDATOR that only refuses the malformed can still let a control fail OPEN

`working-branch`'s one job is to make a claim visible to other agents, so the write path verifies the
branch is actually pushed — `GET /repos/{owner}/{repo}/branches/{branch}`. The parser guarding that
value checked whitespace, the `owner/repo@branch` shape, and leading/trailing slashes. All
well-formedness questions.

`owner/repo@../../../user` passes every one of them, and is then interpolated into the REST path. The
request resolves a *different* endpoint, succeeds, and the value is stored as a **verified** working
branch pointing at a branch nobody can find — the exact invisible claim the check exists to prevent.

What it is not: injection (the call is list-form with no shell), or a privilege crossing (same
token, GET, one bit returned). Which is why it reads as low-severity on a first pass and is not. The
harm is that a control **reports success about something other than the thing it was asked about**,
and a control that can do that is worse than no control, because its output is trusted.

The same seam produced the mirror image on the other new field. `validate_affected` refused prose and
accepted globs, which the docs say are unsupported: `plugin/lib/**` is written happily and then
matches nothing forever — a silent *negative* where the branch case was a silent *positive*.

The fix in both cases was to add rejections of a second kind. Branch names are now held to git's own
`check-ref-format` rules (a name git could never create cannot be a pushed ref, so accepting one can
only mean the check passed against something else); `affected` refuses glob metacharacters at the
same seam that refuses prose, with the directory-prefix form named in the message.

**Ties to**: `plugin/lib/backlog/encode.py` (`_is_valid_branch_name`, `parse_working_branch`,
`validate_affected`); `tests/test_backlog_encode.py::TestWorkingBranch` (17 refused spellings, 5
accepted — including `docs.github.com`, since a dot is legal in a repo name).

## Changing HOW data ARRIVES silently re-scopes every aggregate over it

**Origin:** W1 backlog cache, Chunk 04 (2026-08-07), carried in as a finding from Chunk 03's review.

`cachequery._freshness` answered the cache's visible age with `MIN(item.fetched_at)`, and its
docstring argued the case well: *an age is a promise about the whole payload, and the honest promise
is the worst row in it.* That was exactly right while the cache was rebuild-only — every sync
rewrote every row, so the oldest row stamp *was* the age of the payload.

Chunk 02 made sync incremental. It changed no line of `_freshness`, and it did not need to: from
that commit on, only the fetched window gets restamped, so `MIN(item.fetched_at)` became the fetch
time of the **least-recently-edited** item. It grows without bound precisely while syncs keep
succeeding. A store synced ten seconds ago could honestly report an age of weeks, and a consumer
reading that age would treat the cache as abandoned at the moment it was most current. The 304 path
was worse still: it returned before touching the store at all, so the cheapest and most common
successful sync left no trace whatsoever.

**Why no test could have caught it.** Every test still passed. The value was still a well-formed
timestamp, still monotonic, still derived from real data by correct code. Nothing was broken in any
sense a suite can assert — the *inputs* changed meaning, and the aggregate over them inherited the
new meaning silently. The rebuild-era fixtures in particular could never have shown it, because in a
rebuild every row shares one stamp and the two readings coincide.

**What caught it** was a reviewer asking what the number *means* now, rather than whether it is
computed correctly. That is the transferable move: after a change to how data arrives — full scan to
incremental, batch to streaming, snapshot to event log, single-writer to many — walk every aggregate,
watermark, MIN/MAX, count and age over that data and ask what each one now denotes. The ones that
broke will not announce themselves, because computing correctly is exactly what they still do.

**The fix, and why it is two facts rather than one.** Row provenance (`item.fetched_at`: when this
machine last read *this row*) and coverage (`cursor.coverage_confirmed_at`: when a sync last
established that the store is level with the provider) are different questions, and the age wants the
second. Every successful sync advances it, **including a 304** — which establishes something
positive, that the provider has nothing newer, not merely that nothing was written. Row provenance
stays as the reader's fallback for a store that holds rows but carries no cursor row.

**Related:** the sibling failure is [[a-behaviour-change-falsifies-surfaces-a-chunk-never-edits]] —
there the stale thing is a docstring that now lies; here it is a *value* that now lies, which is
harder, because prose can be read and disagreed with while a plausible number cannot.


## A retirement is one act PER SUBSTRATE the thing lives on

The `claim` retirement's case was entirely about the Issues adapter: a release-current op, its
replacement (`working-branch`) shipping in the same release, and three coupled mechanisms — an
assignee take, a `claimed_at` stamp, a staleness TTL — collapsing into one field. Executed, it also
stripped the **markdown** backend's `accepted-by:`, which has none of those three mechanisms and
cannot supply what replaces them: `working-branch` must name a *pushed* ref and a repo, which a
local-only repo or a shared-trunk team has not got. `accepted-by:` cost those products nothing.

The same session made the identical mistake a second time, one file over. `probe_revisit_due` was
retired on the argument that exception clocks *"had already migrated to prose on the norm"* — true of
this repo's single live exception and of no other product. For every markdown-backend product the
probe was live and working; `docs/norms.md` § Exceptions expire states the two-path split
normatively, and the janitor's Norm Health sweep declines dated clocks **because** this probe fires
them. Removing it took a working control from a whole class of products and left four active surfaces
promising a mechanism that no longer existed.

Two instances in one changeset is what makes it a rule rather than a slip. The tell is cheap and was
available both times: **the argument names a substrate and the diff does not.** Where a rationale is
stated in terms of one op, one release, one provider or one backend, the edit has to be bounded by
that substrate — otherwise the next question is which other substrate it just governed by accident.
Found by the Critic (`rev-20260807T202943Z-a483337f`, R-4/R-10/R-16/R-23), from two independent
goals; the fix was to scope the retirement to the adapter, and the requirements' CC3 now records the
supersession rather than quietly changing meaning.

## A rule enforced only as a SIDE EFFECT of some other failure is unenforced for changes whose failure mode differs

`cache.py`'s `SCHEMA_VERSION` comment is emphatic and has a real incident behind it: a `cursor` column
was once added under an unchanged version, and because the version check is the same mechanism that
would have rebuilt the store, it approved the store and every sync failed permanently with no
self-heal. So the rule reads *bump on any column change, including one made before release*.

Chunk 05 dropped the `relationship` table and bumped to v6 — then mutation testing left
`SCHEMA_VERSION` at 5 and the whole suite stayed green. An old v5 store simply carries an extra table
nobody reads, so nothing breaks. Looking at why the earlier incident *was* caught: a query broke
loudly against the stale store. That is not the rule being enforced; that is a different failure
happening to be noisy. A **removal** is quiet by construction, so the rule had no guard for half the
changes it governs, and the bump was silently optional whenever the failure mode was silence.

Fixed by pinning `SCHEMA_VERSION` to a fingerprint of `_SCHEMA_STATEMENTS` in a test, mutated both
ways (bump missed → red; schema edited under an unchanged version → red). The generalizable move:
when a rule cites a past incident, ask what *actually* caught that incident before assuming the rule
is enforced.

## Sweeping for the IDENTIFIER is not sweeping for the CLAIM

Three instances on one branch (`feat/backlog-cache`, 2026-08-07), each caught by review rather than
by the sweep that was supposed to catch it:

1. **Chunk 05 — the `claim` retirement.** Done-when named `data-model.md` and `api-contract.md`; both
   were reconciled carefully, and `-test-specifications.md`, `-nfr.md` and `-requirements.md` were
   left specifying a mechanism that no longer existed. A Done-when list is a floor, not a scope.
2. **Chunk 06 — janitor checks 6 and 7.** Retired on "meaningless once Issues is system of record",
   an argument true of one backend, applied to both. (This one also has its own rule — *a retirement
   is one act per substrate* — and recurring anyway is the point: recognizing a pattern in a review
   finding is not the same as recognizing it in a task list.)
3. **Chunk 06 verify — `adapter-mode.md`.** One section routed `find`/`dedup` through the new cache
   while two others in the *same file* said they were unavailable: the action menu printed on every
   invocation ("present `find`/`dedup` as **not available on this backend yet**") and the `add` flow
   ("**Dedup-on-create is degraded** … say full dedup is not available"). The preceding fix commit
   had addressed the tool-grant half of the very finding that named this file, and never re-read it.

**Why grep does not catch this.** The falsifying prose contains none of the identifiers. "Not
available on this backend yet", "is degraded", "meaningless once X", "remains dormant" — no `find`,
no `dedup`, no `cache-query`. Searching for the dormancy-notice text I had written came back clean,
because **I was searching a string I wrote, not a claim I had falsified** — which is the tell, and
the clause the rule heading had to shed to fit its budget.

**The check that would have worked** is a question, not a pattern: *what did this change make true or
false, and who asserts the opposite in words?* For a restoration the query is "what still says this
is unavailable"; for a retirement, "what still says this works". Both are read-and-judge over the
files that describe the capability, and neither is a `grep` for a symbol.

A fifth instance closed the loop on the *fix* rather than the defect. The tripwire written for #3
**enumerated two files**; `migration-scrub.md` carried the same claim ("full-text `find` is
unavailable for *every* item post-cutover") and was edited by Chunk 06's own commit. Enumeration was
what missed #4 as well. The tripwire now **globs every `.md` under `skills/`**, so a surface added
later is covered the day it lands — scoped to `skills/` because that is agent-executed prose, where a
build plan or change-log is a record of what was once true and may say so. It was validated against
all three historical blobs (3 hits, 1 hit, 1 hit) and the fixed tree (0).

Related: *a retirement is one act per substrate the thing lives on* (the scoping half of the same
family) and *a rule about second homes does not stop at the homes someone remembered to enumerate*.


## A change-log `scope=` tag borrowed from the neighbouring entry

Tagged `scope=backlog-cache` on a branch whose plan scope is `backlog-cache-write-path`, caught by the Chunk 02 cumulative reviewer. Under `views_enabled`, `views.collect_shipped_chunks` filters entries by exact `scope=` equality, so at release these chunks would have flipped `build-plan-backlog-cache.md`'s boxes — already covered by its own entries — while `build-plan-backlog-cache-write-path.md`'s chunks collected nothing and regenerated to `[ ]`. The integrity check does not catch it: `diagnose_scope_plan_coverage` complains only when a `chunks=` id matches no line in the mapped plan's roster, and `backlog-cache` genuinely has chunks 01 and 02.

**This is the same failure class as `807cd75` on the parent branch** — the `release=unreleased` placeholder that made a finished branch invisible to its release — recurring three weeks later inside the change-log entry describing the fix for it. Cause both times: the tag was copied from the surrounding entries rather than derived from the artifact it points at. A neighbouring entry is the most available model and the least reliable one, because it was written for a different scope.

**Related:** [[observable-beats-stored]] shares the shape — a field whose value must be remembered rather than derived is a field that will eventually be wrong.


## Hand-tick a build plan's `## Status` box the moment its chunk's review passes

**This entry is the inversion of the rule that stood here until 2026-08-08, and the history is the
useful part** — a rule this file once stated as a prohibition is now stated as an obligation, so
anything still repeating the old form is running on a mechanism that no longer exists.

**What the old rule was, and why it was right at the time.** The boxes were a derived view:
`views.build_status_view` counted `status=shipped` change-log entries and regenerated the `## Status`
block at release. Hand-ticking therefore survived right up to the moment anyone would consult it,
then silently disappeared. It was caught by the PR reviewer on `fix/backlog-cache-write-path`
(`8551e26`), where three boxes were `[x]` against a deliberately statusless entry on a `develop`
base, and the sibling plan that kept `[ ]` and recorded completion in prose was the documented
convention.

**What the convention cost, and why it lost.** With the boxes correctly `[ ]`, the session briefing
announced `Resume: Chunk 01` for that plan *after all three chunks had shipped and merged* (PR #628),
and the handoff notes repeated it as fact. That is the shape of the whole defect: completion had two
readings, neither was authoritative, and the framework's own answer was to tell every reader not to
trust the one printed in the artifact. A governance file whose most-read field is documented as
untrustworthy is not a file with a caveat, it is a file with a bug — and the bug was the tool that
overwrote it, not the people ticking boxes.

**The rule now.** Tick `[x]` by hand when a chunk's "Done when" steps are all satisfied, and in that
order — the Critic review comes before the tick, because ticking the LAST box disarms the Stop hook's
Critic and reflection gates. Nothing derives the boxes, nothing reverts them, and everything reads
them: the briefing's `Resume:` line, the handoff, review-mode inference, chunk-ref grading, and both
Stop gates. The opposite error is now the live one — a chunk built, committed, and left unticked —
and its only backstop is `buildplan_refs.unticked_committed_chunk_notice`, an advisory that fires
solely on a `Chunk <n>` commit subject with a numeric id. A repo without that commit habit gets
silence from it, indistinguishable from every box being right.

**Tell that the old rule is still running somewhere:** any prose telling a reader the boxes are
untrustworthy, that they "only flip at release", or to consult git history or the Context line
instead of the checkboxes.

**Related:** [[the-derived-views-retirement]] — the sorting rule this inversion produced;
[[a-change-log-scope-tag-borrowed-from-the-neighbouring-entry]] — same branch, same
release-bookkeeping surface, both found by review rather than by a check.


## When a requirement is about a COST, assert the operation that costs

Requirement BP9 said a growing archive must not be walked twice per session. I implemented
`sorted(root.rglob("*.md"))` followed by `if <archived>: continue`, wrote "pruned at directory level,
not filtered per file" into three docstrings, and wrote a test asserting **no archived file was
opened** — which the defective shape satisfies perfectly. `Path.rglob` has no pruning hook: it
descends the whole subtree and hands you every path. Reading is a *proxy* for traversing; the cost
BP9 bounds is the traversal. The fix was `os.walk` with in-place `dirnames[:]` assignment, and a test
that spies on `os.scandir` — the call that performs the work the requirement is about.

**Why my own mutation testing did not catch it, which is the transferable half.** I ran a three-way
mutation battery, including moving the filter from before the read to after it. Both arms still used
`rglob`. **A mutation battery only explores the neighbourhood of the implementation you wrote** — it
cannot see a defect invariant across every mutation you think to make. Mutation testing validates
tests against *nearby* wrong code, not against the family of wrong code you are already inside.

**Related:** [[a-stage-whose-worth-is-speed-needs-a-test-that-fails-when-it-stops-being-fast]] — this
is the sharper form of it: not merely *a* test, but a test whose observable is the cost itself.

---

## A pattern narrowed to kill a false positive is validated against the case that PROVOKED it

**Context.** The unticked-committed-chunk tripwire (DV7) shipped with `_CHUNK_COMMIT_RE =
Chunk\s+(\d+)`, which matched a chunk id anywhere in a commit subject. Minutes later it fired on
`plan(...): carry R-9's tail to Chunk 03` — a commit that merely *mentions* a later chunk. The build
plan recorded a fix: `\(Chunk\s+(\d+)\)|:\s*Chunk\s+(\d+)\b`, described as "a narrowing verified
against this branch's real subjects."

**What the full corpus said.** Over the repo's last 800 commit subjects the proposed narrowing
disagreed with the old pattern on 22 subjects — all in the direction of matching less, as intended.
But grouping by conventional-commit scope showed it removed *all* chunk coverage from two entire
plans: `drift-burndown` (chunks 1–4) and `critic-burndown` (chunks 1, 3). Those plans named their
chunks only in a third idiom the sample never contained — `docs(scope): close Chunk 01 — the census`.
A control that is silent for a whole plan is indistinguishable from one that found nothing, which is
the failure mode this control's own docstring names.

**Why the sample was the defect.** The branch that provoked the false positive contains, by
construction, the conventions that branch happens to use. It cannot contain a convention used by a
plan written six months earlier. The check that changed the decision was one `git log --format=%s
-800 | python3 -` comparing old-vs-new match sets grouped by scope, and it took under a minute.

**What shipped.** Three anchored arms — parenthesised, immediately after the conventional-commit
colon, and the `clos(e|es|ed) Chunk NN` idiom — pinned positively for all three forms, negatively
for three real prose mentions from the log, and by a property test asserting the pattern *strictly
narrows*: over the real history it matches nothing the old pattern missed. That property is the one
no positive test can replace, because the risk in a rewrite is not "it stops matching" but "it starts
matching something else."

**The general shape.** Narrowing a matcher is a two-sided change and it is nearly always evaluated on
one side. Ask both: what does it stop matching that it should, and what does it stop matching that it
shouldn't? The second question needs a corpus, not a case.

---

## A new key in a shared namespace needs a collision check against real DATA before it needs a test

**Context.** Build-plan archival records "the release that carried this work" in the archived plan's
frontmatter. The obvious key was `release:`. The writer also has to be idempotent — re-archiving must
replace its own keys rather than append a second contradicting copy — so it strips every key it
considers its own before rewriting them.

**The collision.** `.prawduct/artifacts/release-plan-v3.2.7.md` already carries `release: v3.2.7`,
meaning *the release this plan governs* — a different fact from *the release that carried this plan*.
And release plans are among the artifacts most likely to be archived, because the gate that reads
them (`check-releasability._find_release_plan`) searches the archive by design, specifically so
archiving a shipped release plan does not make the gate fail closed. So the one artifact type whose
archival was explicitly designed for was the one whose data the writer would silently delete.

**Why every test passed.** The unit tests were written against the writer's own semantics: stamp,
read back, assert the keys. A test suite validates the contract you thought you had. It has no
opinion about what else in the repo already means something by the name you chose.

**The check that found it.** A loop over `.prawduct/artifacts/*.md` printing any top-level
frontmatter key matching the set the writer claims. One hit, and it was the decisive one. Renaming to
`released_in` removed the ambiguity permanently and reads better besides; a regression test now pins
that a release plan's own `release:` survives both a first and a second stamp.

**The general shape.** Any writer that owns a subset of a shared namespace — frontmatter keys, config
keys, tag fields, env-var prefixes, label names — is defining what it will overwrite. Enumerate the
existing occupants from real data before choosing the name, not from memory and not from the schema
you are about to write.

---

## An assert-absent guard passes when the instruction is simply DROPPED

**Context.** Retiring "delete the build plan" across five instruction surfaces, the coverage shipped
as a property-matched sweep asserting that no shipped surface instructs deleting a plan — matched on
the instruction rather than on the sentences that were removed, and verified red against rewordings
that never shipped.

**What it could not see.** An edit that removes the *archive* instruction from `pr/SKILL.md`'s trunk
branch leaves the sweep green, because nothing then instructs deletion either. Silence satisfies a
negative guard by construction. This is the same never-armed failure the same branch had just closed
for the DV7 tripwire — a control nothing reaches reads as a control that found nothing — reproduced
one file over, by the author who had written the argument.

**What was added.** A positive pin per surface, scoped to the *branch* rather than the file: the
trunk path must name `archive-plan`; the gitflow path must say RETAIN and must NOT name
`archive-plan`, because gitflow decides *when* a plan is archived, never *whether*, and that
distinction is the entire rule. A whole-file grep passes when the instruction is present but sitting
in the wrong branch, which is the likeliest way this actually breaks. The locator asserts it found
exactly one matching line, so a rename makes the pin go red rather than silently match nothing.

**A second trap in the same guard.** The sweep's first exemption clause skipped any match whose
±90-character window contained "archive" — which, after the change, is every line on those surfaces.
It would have excused a genuine deletion instruction written beside an archival one. Replacing it
with a negator scoped to the 24 characters immediately before the verb is tight and testable, and
the motivating case is now a fixture: *"Archive the plan at the release; on trunk, delete the plan
file now."* must still be caught. **A negative test's exemption clause is where its teeth go.**

## Prove a new regression test DISCRIMINATES by running it against a stash of the pre-fix source

Written after the R-11 fix in the governance-artifact-lifecycle scrub (2026-08-10). The defect:
`archive_plan`'s write and `unlink` shared one `except OSError`, so a failed unlink left the
stamped copy in `archive/` AND the original live while reporting `refused`.

The first test written for it **passed against the unfixed code.** Its fixture created
`artifacts/` and the plan but not `artifacts/archive/`, then made `artifacts/` read-only to
provoke the unlink failure. With the archive directory absent, `destination.parent.mkdir()` failed
first — so the WRITE path errored, the function returned `refused`, no copy existed, and every
assertion held. Green, while exercising nothing the finding was about.

It surfaced only because a second, narrower test in the same class asserted on the failure
*message* and could not pass on the write path. Pre-creating `archive/` is the whole fixture: a
write into `artifacts/archive/` needs permission on `archive/`, an unlink of the plan needs it on
`artifacts/`, and that asymmetry is what isolates the two operations.

The cheap general check is one command: `git stash push <source file>`, run the new test, expect
red, `git stash pop`. It costs seconds and answers the only question a green error-path test
raises. This is the same family as the earlier "a report added at your call site is empty by
construction" rule — both are cases where the *absence* of a signal is indistinguishable from
health, and both are settled by making the thing fail on purpose once.

## Release prep vs the cut, and the version tier a draft had already decided (2026-08-10)

**Context.** Assessing `develop` for a release to `main`, then doing Phase 0 prep. Two rules came
out of one session, and they compound: the second is *what* the prep got wrong, the first is *how
far* the prep was allowed to go.

**The tier.** A `## v3.2.8` CHANGELOG section had been drafted on the branch that finished
`governance-artifact-lifecycle`, carrying a careful RELEASE-PREP comment listing what the release
still owed — re-derive the pending scope set, widen the headline, restore the anchored heading,
bump the version. The list was correct and I worked it. Writing the release plan's "Version
decision" section sent me to `operational-spec.md`'s descriptive version tiers, where the observed
minor tier is *"a substantial new capability or a subsystem going live"* — and the named instance
is **v3.2.0, the backlog service shipping dormant**. This release is where that subsystem wakes
up: Chunk 06 restores the Critic's reconciliation walk and hygiene checks, the PR reviewer's R-1
and R-2, and the janitor's Backlog Health block, and retires the dormancy advisory. The draft's
number predated two of the three scopes it would ship.

The comment could not have flagged this. Its author saw the risk in front of them — a headline
describing one scope while three were pending — and the tier question is only askable once you
know what the other two scopes *are*. Nothing joins the two facts: `check-releasability` grades
whether the partition is complete and is silent on whether the number matches what the partition
contains, while printing that number in its own output.

**The trigger.** I had offered the owner three prep items and scoped out the merge to `main`. When
they said "don't actually release yet" my first reading was that nothing changed. Wrong: **two of
the three were the trigger.** Bumping `version` is the auto-update cache key — the single fact the
release process calls "the most important operational fact about deploying prawduct" — and
stripping the ` — DRAFT` suffix is precisely what makes the section publishable, since the suffix
exists to stop the draft reading as shipped. Had I done both and stopped, the repo would sit one
promotion from shipping with every in-repo signal claiming it already had.

**Resolution.** Wrote the classification artifact (it grades readiness; it causes nothing),
renumbered and widened the prose, and left the version strings at 3.2.7 with the DRAFT suffix
intact — recorded under "What this plan does NOT authorise" in the release plan itself, so a green
gate cannot be misread as an armed release. The asymmetry is the general point: a *record* of
readiness is free to write and free to discard, while the acts that arm a release are neither.

## Six guards that pinned the repo's release phase, and the two defects hiding in the repair (2026-08-10)

**Context.** Six `TestAgainstTheReal*` guards went red the moment the v3.3.0 release prep ran, on a
branch where nothing shipped to consumers had changed. The concise rule for the *cause* — a test
asserting against its own repo's live state pins that repo's current phase — was filed by the
session that hit it. These two rules come from the session that repaired it, and both are about the
repair rather than the original defect.

**What the repair was.** Not weaker assertions: the guards had been hardened by an earlier round
precisely to stop vacuous passes, so relaxing the non-emptiness checks was the one move that could
not be right. The fix was corpus selection. An archived plan is still a real plan with real
frontmatter and the archive only ever grows (76 against 0 live mid-release), so the resolver tests
and the change-log join read live + archived — strictly larger and more discriminating than what
they replaced. Two tests genuinely needed a *live* plan to perturb; they now promote a real archived
one into a `tmp_path` copy instead of borrowing whichever plan the branch happens to be building.
The two whose subject really is work in flight say which emptiness they reject: the plan pointer
skips with a named reason when `active_build_plan` is null, and the release partition accepts an
empty pending side only when some entry is stamped with the version `plugin/VERSION` claims.

**The first defect: a skip that should have been a failure.** The helper picked its victim plan as
"in the archived map but not in the live one." That reads as obviously correct and is a trap — it
asks the resolver under test to select the fixture for testing the resolver. Mutating
`prune_archive=True` to `False`, which is exactly the defect
`test_archiving_a_real_plan_removes_it_from_the_live_map` exists to catch, made that set difference
empty; the helper skipped with "nothing to perturb" and pytest printed `s`. A skip is
indistinguishable from a pass in a summary line, so a broken resolver would have shipped green
through the very test written to stop it. The fix walks the archive directory — a filesystem fact,
independent of what is being graded — and makes the precondition an `assert` naming the defect
("the live walk is not pruning archive/") rather than a `skip`.

**The second defect: a rewritten assertion that could no longer fail.** Replacing the hardcoded
branch scope with a read of the `active_build_plan` pointer removed the per-branch edit and the
death-on-archival — and silently removed the test's ability to catch a *wrong* scope value. The map
is keyed from the same frontmatter the test re-reads, so mutating `scope:` to `WRONG-SCOPE` left
both sides agreeing and the test green. The old hardcoded literal had been the independent source of
truth; nothing replaces it. Two probes showed what *does* still bite — a stale pointer, and a second
plan declaring the same scope and sorting earlier, which steals the key and sends review dispatch at
the wrong file silently. The limit is now written into the docstring under "what turns this red"
instead of being implied away by prose about cross-checking.

**How both were found.** Nine mutations against an `rsync` copy of the real tree: shrink the
archive, duplicate a scope, stale the pointer, walk the archive first, disable pruning, mistag the
release version, key the map by filename, return the wrong plan for a scope. Seven bit immediately;
two came back green and those two were the findings. Neither was visible by reading the diff — both
tests looked careful, and one of them *was* careful about everything except whether it could fail.
A filename↔scope cross-check was considered as a replacement source of truth and rejected on
measurement: 74 of 77 plans follow `build-plan-<scope>.md`, but three genuinely do not, so asserting
it would have been inventing a norm mid-build rather than enforcing one.

**Verification that the phase problem is actually gone.** Green in both phases — the post-prep tree
(0 live plans, 0 pending entries) and a worktree at pre-prep `50d99594` (3 live, 9 pending) — with
no skips in either, plus a simulated re-run of runbook steps 3 and 11 against this cycle's own
change-log entry and plan. One run can only ever prove the phase you are standing in.


## RULING (harness-only-removal-is-not-a-major), 2026-08-11

`api-contract.md` § Direction: "deprecation is signalled (stderr notice, kept working, removal
deferred to a major), never silent." v3.3.2 removed `build-index` and `user-prompt-submit` in a
patch, silently, as part of deleting the work-model tripwire.

The clause's why protects CALLERS across versions. These two had exactly one caller — `hooks.json`,
shipped inside the same plugin at the same version and updated in the same commit — so no caller
could observe a gap. The same artifact already classes them "called by the harness, not by humans"
(§ Operations) and already records, as a dated decision, that there is no supported external
consumer of the subcommand surface (§ Versioning). Honouring the letter would have spent a major
version number on a change that breaks nothing for anyone, and would have set the precedent that
harness-internal cleanup is a major.

Recorded as a `Rulings:` line on the entry rather than as an edit to its Statement or Why — editing
a norm to permit your own change is the amend tell. `stamp-merged` and `regen-views` stay
inert-and-deferred, which is the contrast that keeps the exception narrow rather than a loophole.

### Premise falsified the same day — 2026-08-11 (v3.3.3)

The paragraph above contains one false sentence: *"so no caller could observe a gap."* Every
product repo did. Within hours of v3.3.2 publishing, `../samsung-frame-art-loader` and its siblings
were printing `SessionStart:clear hook error` with the CLI usage string at every session start, and
the same failure once per prompt through `UserPromptSubmit`.

**Where the reasoning went wrong.** "Shipped inside the same plugin at the same version and updated
in the same commit" is a fact about the *repository*, and it was read as a fact about *installs*.
It is not one. Claude Code caches the plugin per version under
`plugins/cache/prawduct/prawduct/<version>/` and records a pin **per project** in
`installed_plugins.json`; those pins move lazily and independently of each other. At the moment of
the report, four sibling repos sat at 3.3.0 or 3.3.1 with a user-scope 3.3.2 install beside them.
The harness then resolves which binary runs — so a `hooks.json` registration is not a caller that
updates in lockstep with the binary. It is the caller that *most reliably does not*, because it is
invoked by the harness rather than by anything that ships with it.

Co-shipping is real, but it only proves atomicity **within one cache directory**, and the decision
lands across directories. That is the transferable error: a compatibility argument that names a
version or a commit, rather than naming who invokes the caller and when that invoker updates.

**What this does and does not overturn.** The tier question the owner actually ruled on — that
harness-only removal need not spend a major — is untouched; nothing here argues a major was owed.
What is withdrawn is the *warrant*, the claim that no gap is observable. The consequence follows
from the norm's own why (protecting callers across versions) rather than from the tier: unregistering
a hook is free and takes effect at the next session start, but **deleting its subcommand is not
free until no supported install still registers it**. v3.3.3 restores both as inert on that reading.

Left open for the owner rather than settled here, because scope is normative content and an
amendment carries it: whether the exception should state that inert-retention window explicitly.
Recorded the same shape as `[[install-reference-is-published]]` — a premise falsified without the
decision necessarily becoming wrong. **Ruled 2026-08-11 (v3.3.4):
`[[deprecation-requires-an-inert-retention-window]]`, below.**

## RULING (deprecation-requires-an-inert-retention-window), 2026-08-11

Owner decision, put directly during the v3.3.4 release review and answered: **the harness-only
removal exception requires an inert-retention window.** Unregistering a hook is free and immediate;
deleting its subcommand waits until no supported install still registers it.

This is the question `[[harness-only-removal-is-not-a-major]]` left open one paragraph above, and it
is settled at the norm rather than in a release plan because scope is normative content. Homed as a
further dated paragraph on the existing `Rulings:` line in `api-contract.md` § Direction — the
Statement and Why are untouched, which is the split `docs/norms.md` draws between amending a norm
and recording case law at its edge.

**Why the window, and not simply "don't remove".** The two halves of a retirement are separable and
their costs are wildly unequal. Dropping the `hooks.json` registration costs one line and takes
effect at the consumer's next resolve; dropping the dispatch branch breaks every pin that has not
yet caught up. A rule that treated them alike would either forbid the free half or permit the
expensive one. The window is what lets the cheap half proceed at any tier while the expensive half
waits for the thing that actually makes it safe.

**And it is the replacement for the falsified warrant, not an addition to it.** What made v3.3.2's
deletion look safe was the belief that the caller updates atomically with the binary. That belief
was false. The retention window delivers, mechanically, the safety that belief was assuming — which
is why the tier permission survives unchanged while the warrant stays withdrawn.

**Where the window closes.** When no version a consumer could still be pinned to registers the
command. Under a `directory:` marketplace that bound is set by how lazily pins update, so the honest
floor is *at least one release after the registration is dropped*, and longer wherever evidence says
a pin is older. The cost of holding it is a `return 0` and a docstring; the cost of getting it wrong
is every product repo erroring at session start and once per prompt, which is what v3.3.2 measured.

**What it unblocks.** #644's conformance leg was at `stage: requirements` on exactly this ground —
its own Scope-out said the rule it checks against was not fully written until this was ruled. It is
written now.


## RULING (inert-retention-cannot-be-extended-across-norms), 2026-08-26

Owner decision, stated directly when the question was put during `fix/silent-governance-failures`:
**"NEVER python specific, never requiring a specific implementation of testing or anything else. We
provide absolute business requirements, consuming repos decide the best way to implement for their
project."**

The occasion: `audit-learnings`' sentinel runner hardcoded `sys.executable -m pytest`, an
uninventoried instance of `architecture.md`'s **"never be specific to Python"** norm. Products now
declare `sentinel_command:`. The question was what to do with the pytest fallback — and
`api-contract.md`'s additive-first clause, read alone, says withdrawing working behaviour defers to
a major, with `[[deprecation-requires-an-inert-retention-window]]` prescribing an inert window
meanwhile.

**Why the window does not reach this case.** That ruling's whole warrant is that retention is
cheap — its own words, "an inert subcommand is a `return 0` and a docstring". The cost it prices is
the cost of *keeping a stub alive*. Here the thing to keep alive is a Python-specific default, so
retention is not cheap at all: every day of the window is a day the architecture norm is still
violated, in the exact code the fix exists to correct. The two norms cannot both be satisfied by
waiting, and the one whose premise changed is the retention window's.

**Why it was safe to withdraw immediately.** The deprecation clause's Why is protecting *callers*
from breakage, and this withdrawal fails CLOSED: an ungraded sentinel withholds a retirement and
destroys nothing. Contrast the case that produced the window — a deleted subcommand that broke every
governed session at startup. Same clause, opposite blast radius.

**Scope, kept narrow.** Immediate withdrawal is in-bounds only where BOTH hold: the retained
behaviour would itself perpetuate a ratified norm violation, AND its removal fails closed. A default
that is merely unfashionable, or whose removal fails open, still takes the window. The departure was
signalled rather than silent, per the clause's own requirement — an ungraded sentinel prints a
`notice:` to stderr naming the knob.

**Category-level: an inert-retention window is a courtesy the deprecating norm extends, not one it
can extend on another norm's behalf.** When two norms collide, the question is not which is senior
but which one's stated *warrant* has stopped holding.

## (one-home-is-the-predicate-not-the-token) Sharing a matcher shares syntax, not the definition — 2026-08-11

`record_lint._norm_field_re` imports `norm_probes._FIELD_MARKER_RE` *specifically* so that one
definition of a norm entry cannot drift; its docstring said the two "cannot drift apart on an edit."
Adding blockquote tolerance to `_direction_lines` alone left the regex byte-identical and made them
answer differently on identical input: `record_lint` walks raw text and never goes through
`_direction_lines`, so a `> **Why:**` registry became N entries to the probes and 0 to the
`governed_by` lint, whose `if not norms: continue` then silently skipped exactly the products the
fix was written for.

Two things make this worth keeping. First, the direction: the fix INTRODUCED the divergence — before
it, both readers agreed on zero. Second, the reasoning error. The sibling module was opened
deliberately, the shared import was seen, and the conclusion drawn was "one home, so widening
propagates." What was shared was the pattern, not the input it is matched against. So the tell is not
"did I check the consumers" — that check was made — but "does the shared thing include the INPUT."

Found by two independent reviewers in the same cumulative round, neither by the author, against a
commit message that asserted the opposite.

## A negative reproduction against a fail-open mechanism — 2026-08-11 (v3.3.3)

The cumulative Critic found that the restored inert commands were still refused inside an ephemeral
worktree. I tried to reproduce it by writing the pre-fix binary to a scratchpad path and running it
there. It exited 0, and for a moment I had "the finding does not reproduce" in hand.

It reproduced perfectly. From a scratchpad path `_gitstate()` raises ImportError, and
`_check_ephemeral_worktree` **fails open by design** in that case — a bootstrap-resilience contract
it documents explicitly. So the fixture never reached the code under test. With `CLAUDE_PLUGIN_ROOT`
pointed at the checkout, both commands exited 1 with `BLOCKED: refusing …`.

The general shape is worse than a fixture mistake. A mechanism that degrades safely is *built* to
answer "fine" when its inputs are broken, so breaking the fixture and breaking the subject produce
the same output — and the fail-open path is invisible unless you already know it exists. A negative
result is therefore never self-certifying: it says either "the finding is wrong" or "my setup did
not reach it", and nothing in the output distinguishes them.

The cheap discriminator is to run, in the same fixture, a case that MUST trip the mechanism. Here
that was any command absent from `_EPHEMERAL_SAFE_COMMANDS` (`test-evidence` did it) — it printed
`BLOCKED`, proving the guard was live, after which the exit-0 result meant something. That check
costs one command and would have prevented telling a reviewer they were wrong.

Prompted by the test-evidence recorder's own question — whether the fixture actually reaches the
subject — which is doing real work at exactly the moment it fires.

## Editing a norm's statement in the same commit as the code it blesses — 2026-08-11 (v3.3.3)

`api-contract.md` § Deprecation & Compatibility said "Deprecation is signalled, not silent … print a
deprecation notice to stderr on use." The two commands this branch restored deliberately print
nothing, for a good reason (their caller is a registration with no reader, and hook stdout is
injected into the model's context). I softened the clause to "…where a signal has a reader."

That is the amend-to-match-own-code tell, and the aggravating detail is that I was *primed*: forty
lines earlier in the same artifact, in the same sitting, I had explicitly declined to settle the
adjacent retention-window question **because scope is normative content an amendment must carry**.
The cumulative Critic did not catch it; the PR reviewer did.

Why the guard failed while alert. The retention question *arrived as a question*, so it was met with
the norm-lifecycle machinery. The silence question arrived as an implementation detail I had already
decided — and a decision that feels settled does not present as a norm change at all. Vigilance
aimed at "am I about to amend a norm?" does not fire, because subjectively I was only writing down
what the code already did.

So the usable tell is structural rather than introspective: **a norm's statement edited in the same
commit as the code that statement would bless.** That is checkable without knowing the author's
state of mind. `cost-of-commit` reporting the doc paths as "free" made it frictionless in the
direction of the mistake — cheap edits get less scrutiny, and this one was cheap and wrong.

The repair: restore the clause verbatim, record the two silent commands beneath it as a dated
departure pending owner ratification, naming why, what the owner is being asked, and the remedy if
the answer is no (warn on stderr — never stdout).


## Re-measure against the question, not the last test's conclusion — 2026-08-11 (v3.3.4, #646)

The release runbook's case-(3) triage carried one "live instance": a plugin cache under version key
`3.2.4` at commit `a0c2468`, diagnosed as holding non-release content.

Three tests, three verdicts, and only the last one asked the right question.

1. **`git merge-base --is-ancestor a0c2468 v3.2.4`** → not an ancestor → "non-release tree." This is
   the test #646 removed: `main` is built by `read-tree` plus a fresh commit, so it returns false for
   *every* install. The instance was born from an instrument that cannot return true.
2. **`a0c2468^{tree}` vs `v3.2.4^{tree}`** → `165e315f` vs `fa827756`, different → "still real,
   confirmed under the corrected test." This is where the fix stopped, and it is the interesting
   failure: the release plan had explicitly instructed *do not carry the case forward on evidence
   produced by the broken test*, and that instruction was obeyed — with a second wrong instrument.
3. **`a0c2468:plugin` vs `v3.2.4:plugin`** → both `ba3e8581` → **phantom.** The cache held the
   v3.2.4 plugin byte-for-byte. Only `.prawduct/` had moved on, which it does every session.

**The unit was the whole question and nobody asked what the check was a fact *about*.**
`marketplace.json` declares `source: ./plugin`; the cache holds that subtree and nothing else. A
whole-repo tree comparison grades content the consumer never receives, so it over-fires on ordinary
governance commits. Step 3 arrived only because a reviewer asked "what is actually installed?" —
which is the question step 2 should have started from.

The transferable shape: a correction inherits the framing of the thing it corrects. "Is this test
right?" keeps you inside the old test's terms. "What is this check a fact about, and what unit
carries that fact?" is what leaves them.

## Copying a fix into a sibling procedure is a new change — 2026-08-11 (v3.3.4, #646)

`#646` named one runbook. The same install-sha check lived in `promote-a-pruned-release.md`, so the
fix was copied there in the same pass, under the *fix-not-file* preference. That looked like
diligence and was a defect.

The whole-develop runbook's problem was commit identity: `main` shares `develop`'s tree but not its
commit, so a tree comparison is the repair. The pruned runbook's `main` is **deliberately unlike**
`develop`'s — its own next bullet requires `git diff --stat origin/main origin/develop` to be
non-empty — and the marketplace resolves from the primary worktree, which that procedure never
checks `main` out in. So a *correct* install differs from the release there by construction, in
exactly the withheld work. The copied check reintroduced next door the false-remedy loop the fix had
just removed: mismatch → sibling's triage → case (2)/(3) → delete the cache of a healthy install.

The right answer was not a better comparison but *no* comparison: the pruned runbook now states the
check has no equivalent on its path, explains why, and offers the one that does apply — is my cache
current with my own checkout, which is a fact about the machine and not about the release.

**Tell:** you fixed one file, grepped for the same lines, and found them. That grep found *text*.
Whether it found the same *defect* depends on invariants the grep cannot see.

## A feature's own subject is a blind spot in its tests — 2026-08-11 (v3.3.4, #636)

`archive-plan` learned to stamp `unbuilt_at_archive:` from a plan's `## Status` roster. Eight unit
tests, all green: unticked chunks stamp, complete plans don't, an unparseable roster stamps rather
than filing clean, the write is idempotent.

Every one of those fixtures is a **build plan**, because that is what the feature is about. But
`archive-plan` archives whatever it is pointed at, and release plans, discovery notes and design
docs have no `## Status` roster **by design**. `incompleteness_reason` correctly refuses-not-passes
for an unreadable roster — and applied to a document that never had one, that refusal became "no
readable `## Status` roster" stamped onto every release plan at every cut, forever.

Found in about ten seconds by running `archive-plan --dry-run` against this repo's own artifacts
directory and reading the output. No test could have found it: writing one requires already having
had the thought that the subject was wider than the feature.

**The bound is a test-design fact, not a diligence fact.** A test suite explores the space its
author already conceived. Running the real command against real inputs samples a space someone else
populated — which is the only cheap way to discover that your subject widened without you noticing.

## A rule that LOWERS a severity outranks every rule that raises one — 2026-08-13 (tactical-efficiency ch.04)

A prose severity ceiling ("comment and doc wording is NOTE unless load-bearing") was written with
only an upward exit: the conditions under which a finding could climb back out of the cap. Two
bullets above it in the same file, an **actively misleading README instruction is BLOCKING**.

A reviewer who correctly identified a wrong command in a README would have read the ceiling,
found no exit that fit, and landed on WARNING — which gates nothing. The wrong command ships,
and every control involved reports success.

**The exits that LIFT a ceiling are not the same as the severities it must never touch.** Writing
only the exits leaves the ceiling outranking every promotion rule in the file, silently, because
nothing in the ceiling's own text says otherwise. The fix is a floor clause in the same sentence:
the ceiling never lowers a severity another rule assigns explicitly.

Caught by the chunk's own second verify pass, on the rule the chunk existed to add.

## Scrub the WHOLE diff before dispatching a review — 2026-08-13 (tactical-efficiency ch.04)

A provenance ban — review ids and finding ids never ship in comments — shipped with a violation
**inside the test that pins that ban**. The scrub before dispatch had covered the four protocol
surfaces the chunk was "about" and skipped the file the chunk had just added.

The reflex it caught is the general one: under review pressure the instinct is to record *why the
reviewer was right*, in the artifact, where it reads as documentation and decays into archaeology
the moment the plan is renumbered or archived.

Third defect of this shape on one branch, and the countermeasure was the same each time: when you
install a rule, grep for every place that states the old one — including the places the chunk
itself created.

**Fourth occurrence, at the PR boundary, after this rule was already filed.** The release-readiness
reviewer found three more anchors in three test files. The rule above had named the countermeasure
— *grep* — and the scrub that missed them was another careful re-read. A ban stated as a literal
string (`chunk 0`, a review id's shape) is decidable by `git diff | grep`; re-reading is how you
check a rule that has no literal form, and spending it on one that does is the whole failure. The
reviewer's list is also a sample, not a census: applying its three-line remedy with a grep surfaced
a fourth anchor in a file it had already cited, which its own enumeration had passed over.

## "Fail closed" means the channel's blocking value — 2026-08-13 (tactical-efficiency ch.06)

A new plan-resolution refusal was written to fail closed: rather than guess between two build plans
claiming one branch, raise. The CLI wrapper caught it and returned **1** for every command, with a
docstring stating "a refused gate is a blocked gate, which is the intended posture."

`stop` is a harness hook. `api-contract.md` § Error Model — a recorded decision — gives its row
exactly two outcomes: **0 allow/clean, 2 block**. Exit 1 is in neither column, so on the one state
the feature invents, the session ended **clean** with the reflection gate, the composed-coverage
Critic gate and the PR gate never having run. The wrapper written to fail closed was the thing that
failed open, and the docstring asserting the posture was the reason nobody looked.

**The generalizable error is checking the contract for the surface you are writing rather than the
surface the refusal can REACH.** A refusal raised deep in a resolver surfaces at every command that
resolves — CLI, hook, library caller — and those speak different protocols. Non-zero is a
convention; blocking is a specific value in a specific table.

Two follow-ons, both found while fixing it:

1. **Guarding call sites is whack-a-mole when the raise is deep.** Three sites in `cmd_stop` resolve
   a plan independently, and guarding each one only moved which line raised. The fix is one probe at
   the entry point, before any gate runs — which is also what the rendered message claims ("every
   gate resolves a plan, so none of them ran").
2. **The probe must precede any early `return 0`.** A background-work deferral returned 0 further
   down; deferring a refusal would have ended the session clean by a second route, and no amount of
   background work resolves two plans claiming one branch.

---

## A recommendation an advisory prints ships to every consumer's repo, so test its EFFECT, not just that it fires

A probe is easy to test into a false sense of completeness. Fires on the bad state, inert on the
good state, stable id, wired into the roster — six or eight green tests, and not one of them touches
the question the advisory actually raises with the user: *does doing this do what you say it does?*

The change-log union-merge advisory tells an operator to add a line to `.gitattributes` in a repo
prawduct does not own. The claim behind it — "union-merge is safe for an append-only entry log" —
came from an analysis document and read as obviously true. It is true, and checking took four
minutes: two branches each prepending a tagged entry, merged with the attribute and without it. The
control conflicts; the attributed merge succeeds with both entries present and each
`<!-- prawduct: … -->` line still under its own header, because the union driver concatenates whole
hunks and never crosses them.

The check paid for itself twice over. It converted an assertion into a test with a control, and it
surfaced the honest caveat that belonged in the shipped text: union **never** conflicts, so a
genuine two-sided edit to the same line survives as both versions rather than as a conflict to
resolve. That is fine for this file — the release gate's tag validator errors on one key set two
ways — but a reader deciding whether to take the advice deserves to know it, and nobody would have
written it without having watched the driver work.

The general shape: when a mechanism's output is *advice*, the advice is the deliverable, and a test
that only exercises the mechanism has tested the packaging. The recommendation needs a fixture where
it is followed and one where it is not.

---

## A `try/except` around a producer that RETURNS its degraded states guards nothing

The prior-dispositions block is built inside `try: ... except (OSError, ValueError, TypeError)`, and
the comment above that guard states the requirement perfectly: *an empty block and an unbuilt one
are different facts about the world, and a reviewer told "nothing was dispositioned here" when the
join failed would be told something false.*

The single producer of its input is `evidence.read_facts`, which never raises for either degraded
case. It **returns** `{"status": "error", ...}` for an unreadable store, and it filters
newer-plugin records into `schema_ahead` while returning `status: "ok"`. So the guard covered a
path that does not occur and missed both that do — and the manifest carried an empty block, which
the reviewer protocol reads as "nothing was dispositioned." Worst in exactly the case the control
exists for: the answers were there and simply unreadable, so every accepted finding was available
to be re-raised.

What makes this hard to see is that everything *looks* right. The requirement is stated. A guard
exists. Tests pass, because the tests build well-formed stores. And the same module already had the
correct posture twice over — `record_disposition` and the census reader both test `status ==
"error"` and `schema_ahead` explicitly and refuse loudly. The new sibling in the same file did
neither, and nothing in the file's shape objected.

The check is one question, asked before writing the guard: **what does this callee do on its bad
paths?** If it returns them, an `except` is decoration; answer the returned states where the read
already is. A tell that costs nothing to look for: your `except` clause names exception types the
producer's own docstring never mentions raising.

## A rule discovered on one branch of a dispatch table governs its siblings silently

`SKILL.md`'s `critic-begin` exit table has five rows. The exit-3 row carries a carefully
reasoned qualifier: `chunk`/`final`'s interval is HEAD-tree → working-tree, which is
narrower than the coverage gate's span, so when a gate reports `uncovered` the right
re-dispatch is `cumulative`. Someone worked that out, wrote it against the exit where they
hit it, and stopped. Exit 2 — the scope-widened demotion — shares the premise exactly and
said "re-dispatch as `final`" flat.

The cost: a `verify-resolutions` refused for a 95-file widening demoted to a `final` whose
interval held two untracked strays, which were then recorded as a chunk's review. Every
component reported success; the defect lived only in the relation between two rows of one
table.

The general shape is that a table makes each row look self-contained, so a fix reads as
complete when it lands in the row that produced the bug. It is not complete: the premise
that justified it is a property of the mechanism, not of the row. Cheapest check — after
writing a rule into one branch, state the premise in one sentence and grep the other
branches for it.

## A fallback must be checked against the SIZE of the interval it replaces

The refusal here is sound: a delta far larger than the prior reviewed surface should not get
a partial re-review. What made it harmful was the remedy. "Run a full review" sounds like a
widening — more goals, more scrutiny — and `final` genuinely is the seven-goal mode. But
mode names carry goal counts, not spans, and `final`'s span is the uncommitted diff. A
delta that widened *because commits landed* demoted to the one mode structurally blind to
commits.

Two things follow. First, when a mechanism refuses an interval and offers a replacement,
the replacement's span must be compared against the refused one — a fallback that shrinks
the span is not a fallback, it is a silent narrowing that reports success. Second, the
decision belongs in code where the spans are known. `begin_review` had already computed
whether committed content moved since the prior review; it simply was not saying, leaving a
reader to infer from prose what the callee could state as fact.

The fix also had to avoid reproducing itself: recommending `cumulative` unconditionally
fails on the base branch and with no resolvable merge-base, where `cumulative`'s interval is
empty or unavailable and it would refuse at dispatch — recommending a mode that cannot run
being precisely the original defect in a new shape.

## A correct decision defended by an unread mechanism is still a defect

Three times on one branch, each caught by a reviewer and none by me:

1. `cumulative` sold as "a superset of what widened" — false. A base-branch merge moves the
   merge-base forward, so `merge-base…HEAD` *excludes* the merged-in files that inflated the delta.
2. The empty-span guard's message said "HEAD is at the merge-base" while the code compared *trees*.
   A commit-then-revert branch sits far ahead of the merge-base with an identical tree.
3. The plan-less discriminator justified itself with "`check-change-log-entry` refuses a branch
   without an entry tagged with its scope." It refuses a branch without an *added* entry; the tag is
   never inspected there.

The pattern is exact and worth naming because it is invisible from the inside: in all three the
*decision* was right and survived review untouched. What was wrong was the sentence explaining why —
each a confident claim about a mechanism I had not opened, written in the flow of explaining a
choice I had already made correctly on other grounds.

That is more dangerous than a wrong decision, not less. A wrong decision fails and gets fixed. A
false reason attached to a right decision is load-bearing prose that the next maintainer checks
their change against — and it reads as verified precisely because the thing it justifies works.
Overclaiming is also asymmetric under review: reviewers check whether the code does what the change
says, and a rationale sentence is the part least likely to be executed by anything.

The cheap check is the same one Principle 24 names, applied one level in from where it usually
fires: before writing "X forces this", open X. Not to verify the decision — to verify the sentence.
Ten seconds of reading beats a round, and beats a durable false claim that no round ever revisits.

## A refusal predicate is not a severity predicate

`buildplan_refs.chunk_section_gap` answers one question — why a chunk section cannot be
trusted — by folding three conditions into one string: *not located and the plan reads
cleanly*, *not located and the plan has unreadable headings*, and *located but the plan has
unreadable headings*. Its own docstring says "the first two must not share a sentence."

Fixing a silent mode demotion, I needed "this plan cannot be trusted, escalate the review"
and reached for that function, because its name matched my sentence. Eleven tests went red:
the first of its three conditions — a chunk with no detail section in a plan that parses
perfectly — is completely ordinary (a Status roster whose later chunks are not written up
yet), and escalating on it would have reviewed every not-yet-detailed chunk at `final`.

The composite is correct for the readers that must REFUSE, which is what it was built for:
all three conditions mean "do not answer from this section." It is wrong for a caller
deciding how *severely* to react, because severity is not uniform across the reasons. The
fix was to call the narrower `unparsed_chunk_heading_reason` for the escalation and leave
the composite for the refusal, then pin both directions — the escalating case and the
ordinary one — as separate tests, and falsify the escalation to confirm the test fails
without it.

Discovered fleet-feedback-661 (2026-08-17, Critic blocking, second round). Relates to
Honest Confidence (#5) and [[Reads as evidence, is not]].

## The three consolidation entries (fleet-feedback-661 follow-on, 2026-08-17)

Seventeen rules across three families were folded into three. Each said a true thing; each
said it at the altitude of the incident that produced it, so the general statement sat buried
among its own paraphrases and **none of them fired** during the session that produced three
instances of the very defect they describe. The corpus had the disease it was describing:
seventeen instances, no construction.

The retired text is preserved verbatim below — a rule is retired, never deleted, and the
wording each incident produced is often sharper about its own case than the general form can
afford to be.

### Family A — retired into `A fix lands at the instance a review named; the defect lives in the class`

All seven say: the change you made reaches past the site you made it at. They differ only in the relation that carries it — siblings in a table, readers of a moved path, existing uses of a newly-dangerous value, surfaces of a leak, guards behind prose, and the only-consumers of a thing being retired. The survivor states the relation generally (the premise of the defect) and keeps the one insight none of the seven stated outright: **the other members are outside your diff**, which is the mechanical reason they stay invisible.

- **Relocating a source file: sweep every READER of the old path, not just the data-key references** — Relocating a source file: sweep every READER of the old path, not just the data-key references

- **A "renders-but-doesn't-resolve" leak is a SURFACE, not a line** — A "renders-but-doesn't-resolve" leak is a SURFACE, not a line — sweep the whole renderer and assert the bad form is ABSENT

- **An untested governance bound rots silently across a migration** — An untested governance bound rots silently across a migration — sweep the guards (with tests), not just the prose

- **When you add a validator because a value became DANGEROUS, sweep every existing use of that value, not the uses you are writing** — When you add a validator because a value became DANGEROUS, sweep every existing use of that value, not the uses you are writing — the vulnerable line is already in the file and therefore not in your diff. Tell: the helper is new and you never grepped the value's other readers — [learnings-detail.md]

- **A retirement ruling also retires whatever existed only to serve the retired thing, and those consequences never announce themselves** — A retirement ruling also retires whatever existed only to serve the retired thing, and those consequences never announce themselves — after deciding to remove a mechanism, sweep for what it was the ONLY reader of. Retiring the claim machinery silently killed the `assignee` column's only consumer, so a schema specified by a reviewed artifact would have shipped a dead field; found only by walking all fifteen consumer queries against the column list before writing the DDL. Tell: you have just accepted a removal and are moving straight to the thing that replaces it

- **Read a review's findings for the CLASS, not the list** — Read a review's findings for the CLASS, not the list — when four findings share a shape, fixing four instances leaves the fifth to be found by the next round. Tell: several findings could be described by one sentence

- **A rule discovered on one branch of a dispatch table governs its siblings silently** — A rule discovered on one branch of a dispatch table governs its siblings silently — when you write a fix into one exit code, one mode, or one error row, ask which other rows share its premise, because the branch you did not visit keeps the old behavior while the file reads as if the rule is stated. Tell: your fix is a table row, and you edited exactly one — [learnings-detail.md]

## A clean sweep usually indicts your QUERY, not the tree — grep returns sites phrased in your words, so survivors are the ones that paraphrase, assert the opposite in prose, or say nothing (silence satisfies an assert-absent guard). Name the state the change makes true or false, search two vocabularies sharing no word, pin positively. Tell: every hit used your words

### Family B — retired into `A clean sweep usually indicts your QUERY, not the tree`

These six are NOT family A restated — they are the second half of the problem, and folding them into A would have destroyed real content. A says the class exists; B says **your search for it under-reports**, and names four distinct ways: one spelling of a form-family, a phrasing rather than a concept, an identifier rather than the claim, and an assert-absent guard that silence satisfies by construction.

- **An "assert the bad form is ABSENT" sweep is only as good as the pattern that defines the bad form** — An "assert the bad form is ABSENT" sweep is only as good as the pattern that defines the bad form — enumerate the whole FORM-FAMILY, not one spelling

- **A falsifying grep queries a PHRASING** — A falsifying grep queries a PHRASING; only a reader queries a concept — the same stale state written in words your query does not contain is invisible, so the sites that survive a sweep are exactly the ones that paraphrase. Name the STATE being asserted, then search two or three vocabularies that share no word with each other. Tell: every hit came back in the words you typed

- **An edit that changes a COUNT or a SET falsifies every sentence stating the old one** — An edit that changes a COUNT or a SET falsifies every sentence stating the old one — and noticing one of them feels like completing a search rather than starting one, because the catch arrives with the satisfaction of thoroughness. The instance you found is the one you happened to be reading, not the first of an enumerated set. Grep the document for the old value before committing; prefer a relational statement ("the table's rows") over a literal count, which is the part that goes stale

- **Enumerating the surfaces a chunk EDITS is a different question from enumerating the surfaces its behaviour change FALSIFIES** — Enumerating the surfaces a chunk EDITS is a different question from enumerating the surfaces its behaviour change FALSIFIES — only the second finds the docstring that now lies. A plan that lists the first and calls it a surface sweep misses the file the chunk never opens, which is exactly where a maintainer reads the old rule before changing a threshold

- **Sweeping for the IDENTIFIER is not sweeping for the CLAIM** — Sweeping for the IDENTIFIER is not sweeping for the CLAIM — when a change makes a capability appear or disappear, grep finds the sites naming the symbol and misses the prose asserting the opposite. Ask what the change made true or false, then find who says the opposite in words. Tell: your post-change grep came back clean

- **An assert-absent guard passes when the instruction is simply DROPPED** — An assert-absent guard passes when the instruction is simply DROPPED — silence satisfies it by construction — so any retired-behaviour sweep needs a positive pin on each surface that must now carry the replacement, scoped to the BRANCH rather than the file, because which branch carries it is usually the whole rule. Tell: your only coverage of a governance surface is a negative grep

## Bound a class by the PROPERTY that justifies it, never by the container it sits in — a path prefix, a line range, or a fixture built from the feature's own subject each look complete while bounding the wrong set, so the claim reads as verified at the fixture's scope rather than the requirement's BREADTH. Tell: your boundary is a location, your rationale is a verb

### Family C — retired into `Bound a class by the PROPERTY that justifies it`

The third distinct rule: how the class gets bounded in the first place. A path prefix, a line range and a fixture drawn from the feature's own subject are all containers standing in for a property, and each looks complete from inside itself. `methodology/planning.md`'s 'Line-number scoping' trap is the same rule stated for build plans.

- **A fixture's world is narrower than the requirement it certifies** — A fixture's world is narrower than the requirement it certifies — check coverage against the requirement's stated BREADTH, not against the common instance, because a guard silently redefines the claim to its own scope and the claim then reads as verified — [learnings-detail.md]

- **Scope an exemption by the PROPERTY that justifies it, not by the container it lives in** — Scope an exemption by the PROPERTY that justifies it, not by the container it lives in — an exemption justified by *naming* a file belongs to naming forms, not to every file under that directory, and the container is one cheap generalisation away from correct while looking complete. Tell: the boundary is a path prefix while the rationale is a verb

- **Unit tests built from a feature's OWN subject cannot catch a WIDENED subject** — Unit tests built from a feature's OWN subject cannot catch a WIDENED subject — every fixture is an instance of the thing the feature is about, so the input that breaks it is the one you had no reason to construct. Run the real command against the real repo before believing green. Tell: your feature reads whatever it is pointed at — [learnings-detail.md]

## When a durable prose surface holds both released and UNRELEASED sections, "it is history, leave it" is a per-SECTION test, not a per-file one

Found by the PR reviewer on #689 (`governance-surface-dedup`), 2026-08-19.

The branch replaced the turn-closing block's disposition labels, retiring `BLOCKED`. Chunk 04's
commit rationale said: *"plugin/CHANGELOG.md keeps NEXT/BLOCKED — it is history."* True of v3.3.4
and every section below it. Not true of the `v3.3.5-dev` section, which is unreleased and whose
own text says "Rolling release notes accumulate here" — that paragraph was a **pending claim**
about what v3.3.5 would ship, and v3.3.5 was about to ship the opposite.

Left standing it would have been consumer-visible in the worst possible place: the version-delta
banner, the surface built to tell consumers what changed, announcing a vocabulary the shipped
session digest contradicts. Consumers on v3.3.4 hold `NEXT`/`CLEAR` and jump straight to
`RUNNING`/`YOUR TURN`/`COMPLETE`; the intermediate set never ships to anyone, so the honest note
describes the net delta and never mentions it.

**Why the reasoning failed.** "It is history" is a property of a *section*, and it was applied to
a *file*. Changelogs are precisely the artifact where that distinction is load-bearing — they are
append-at-top, so every one of them is part frozen and part pending, with the boundary at the
version header. Any file-level rule about them is wrong for one half.

Same shape as this branch's Chunk 03 blocking finding, where coverage was verified at section
level for a deletion that needed clause-level checking: **rigor tracked the artifact's genre
instead of the blast radius, and the defect landed where confidence was highest.**

Cheap tell at review time: the fix cost nothing — `prawduct-hook cost-of-commit
plugin/CHANGELOG.md` reported `free`, so no review coverage moved and no round was bought. A
"leave it alone" rationale for a free edit is worth one more look; the reason to skip it was never
cost.

## An UNEXPECTED PASS is a signal, not a result

Three instances in one session on `fix/clear-cadence`, and the difference between the good and bad
outcomes was entirely whether I opened anything.

**Investigated (correct).** A restamp guard was expected to break 13 existing tests and broke none.
The reason was principled rather than lucky: those tests seed via `--from-counts`, which records no
`evidence_tree` by design, so they exercise the *uncheckable* branch of the new guard. Knowing that
was the difference between shipping a guard and shipping a guard I could describe.

**Banked (wrong).** A mode-inference guard's own new test went green. Its fixture writes the build
plan but never commits it, so the tree is dirty, the clean-tree redirect it was written to prove is
skipped, and the test graded a different branch. The fix was inert — it did nothing at the moment it
targeted — and reached a Critic review before anyone noticed.

**Banked twice more, in the same test, after adding this rule.** A fault-injection test claimed an
unparseable marker was "undatable"; `_marker_age_seconds` falls back to mtime, so it is dated. v2
claimed `chmod 000` made the read raise; that function catches `OSError` and falls back to `stat()`,
which succeeds on a mode-000 file. Both passed, and reverting the code they guarded left both green.
The fault was unreachable through that call path at all — which is itself the finding, and worth
more than the test: the defensive reorder it guarded is defence in depth against something this
caller cannot produce.

**Why it recurs.** Green is overwhelmingly confirmation, so the prior is strong and one plausible
sentence discharges it. The cheap check is not "is my explanation plausible" but "which branch did
it take" — print it, or mutate the code and watch the test go red. A mutation that leaves the test
green is the same signal arriving a second time.

## One home stops DIVERGENCE, not staleness — when you add a caller to shared copy, re-read the shared sentence AS THAT SURFACE'S READER, because a clause true of every existing caller can be flatly false at the new one and composition hands it over unexamined. Tell: you satisfied "route it through the one home" and never read the composed output

**The case.** `critic_consolidate.pending_roster_reading()` is the single home for what a pending
Critic roster MEANS, deliberately shared so a refusal and a session-boundary notice cannot tell
different stories about what is on disk. Its `incomplete` reading carried the reassurance "a
`/clear` retains the marker; it does not release it" — true of both surfaces that existed when it
was written, both of which retain. A third surface was then added that *sweeps*: the boundary
notice reporting an expired marker with an incomplete roster. Composing through the one home was
the right call and the plan required it, and it delivered a notice that told the reader *waiting is
safe* three lines above *the marker is gone and no gate will raise this again*.

**Why it recurs.** The one-home rule is enforced by checking that callers don't restate the fact,
and that check passes perfectly here — the defect is in the fact, not the plumbing. Nothing about
routing a new caller through shared copy prompts you to re-examine the copy, because the discipline
you are exercising is *not writing anything new*. The staleness arrives precisely when the shared
sentence describes behaviour that the new caller is the exception to, which is the normal reason a
new caller is being added at all.

**The cheap check.** Run the composed output and read it as its reader — not diff it, not verify
the call site. The contradiction was invisible in the code (two correct functions, one correct
call) and unmissable in eight lines of terminal text. Where the shared text asserts a behaviour,
prefer a clause that names its condition over a flat statement: a conditional survives a new caller,
an absolute has to be found and rewritten by someone who has no reason to look.

## When you add a rule to the site that motivated it, ENUMERATE the siblings that perform the same ACT before calling it done — a criterion can be false at a surface your chunk never opened, and listing a reader is not asking whether the change reaches it. Tell: your fix names one call site and your acceptance criterion names a class ("cannot X without Y")

**The case.** A chunk taught `critic_marker.boundary_sweep` to keep a Critic marker whose reviewers
had all reported, so a session boundary could no longer discard a review the Stop hook was about to
consolidate. Its acceptance criterion was a class statement: *a review that outruns the TTL cannot
lose its marker without a signal*. But `review_active` unlinked an expired marker as a side effect
of ANSWERING, and a bare `prawduct-hook clear` — the exact invocation the guard was written for,
after a reviewer subagent ran it and clobbered the session under review — asked that question and
destroyed the review the boundary had just been taught to protect. Two independent reviewers found
it from opposite goals.

**Why the enumeration was there and still did not fire.** The same chunk added a mechanical
inventory of every reader of the marker, precisely because reasoning about this subsystem had gone
wrong twice before. The inventory NAMED the bare-clear site — and mapped it to a test covering only
the live-marker case. Enumerating the readers answers "who touches this"; it does not answer "does
my new rule reach them". The second question has to be asked per row, out loud, at the moment the
rule is written.

**The cheap check.** Take the acceptance criterion's verb — *release*, *delete*, *notify* — and grep
for every site that performs it, not for the symbol you just changed. Then ask of each: with my
change in place, what does this one do? A predicate that mutates while answering is the sneakiest
member of such a class, because its callers read as questions and act as acts — which is also the
fix worth reaching for first: make the rule a construction both surfaces call, not a branch each
implements.

## Re-invoking the thing you just edited verifies nothing in the same session

2026-08-21, delegation Chunk 01. The chunk's acceptance criterion was "`/prawduct:methodology
delegation` opens the guide" — invocation, not assertion, exactly as the plan's Verification
Strategy demanded. I ran it. The harness served the skill body **cached from an earlier invocation
in the same session** (its own header said "the skill instructions were previously loaded"), so the
render was missing the two routing bullets I had written minutes before.

I caught it only because the omission was visible: two bullets I had just authored were absent. Had
the chunk touched only the frontmatter `description`, the stale render would have looked entirely
correct and I would have reported the criterion met on evidence that **could not have shown a
failure** — the class of green the learnings already call out under the unexpected-pass and
negative-reproduction rules, arriving through a new door.

Generalizes past skills: any surface the harness loads once per session — skill bodies, hook
payloads, the SessionStart digest — is unverifiable by re-invocation within that session. Verify
against disk (read the file, resolve the path it prints), or in a fresh session.

## Funding a budget by deleting what another surface says is only valid for readers who receive it

Same chunk. The standing way to pay for growth in `methodology/building.md` is to cut what the
always-injected `session-digest.md` already states in full — the −86 entry of 2026-08-19 is the
precedent, and the audit here used the same class for −53.

The trap surfaced on the fourth candidate cut. `building.md`'s "review first, tick after" ordering
is stated verbatim in the digest, so by the class rule it was removable. It is not: a **subagent
does not receive the SessionStart digest**, and `building.md` is the file every delegate is
instructed to read. For that reader the digest covers nothing, and every "dedup" against it is a
plain deletion.

The three cuts that shipped were re-checked against this and survive it — a delegate does not write
handoff notes, and the retained tells and acting rules stayed. But the class as previously stated is
unsound, and it will be reached for again: it is the cheapest funding move in the repo, and this
feature exists to produce *more* delegates. Enumerate who opens the file before crediting the cut.

## Adding the right rule is not the same act as deleting the wrong one

2026-08-21, delegation Chunk 01, second pass. The whole feature exists because delegation runs at
0.34% of 31,220 tool calls, and the proximate cause is a permissive line in
`methodology/building.md`: *"also when chunks are independent and parallelizable…"* — a permission
where the design calls for a default.

I wrote the default into the new on-demand guide, added a pointer to that guide **into the same
paragraph as the permissive line**, and left the permissive line alone. `building.md` is mandatory
reading before code; the guide is opt-in, and my pointer described it as "the questions worth
asking" — the exact framing the new default was ruled an exception to. A coordinator reading the
mandatory file and stopping got the *unchanged* 0.34%-era instruction. The Critic caught it (R-1).

The mechanics of the miss are worth keeping. This was not a surface I failed to open — I edited
that paragraph in the same commit. The diff showed me touching it, my attention was on the sentence
I was adding, and the sentence directly above it read as background. **Editing a paragraph is not
reviewing it.** When a change exists because some existing statement was wrong, the change is not
done until you have named that statement and removed or replaced it; writing the correct rule
somewhere else leaves two rules standing, and readers obey the one they reach first.

## A mutation sweep where EVERY mutant dies on the first pass is a claim about the HARNESS

**What happened (2026-08-21, delegation Chunk 04).** I wrote an ad-hoc mutation harness to check
whether twelve new prose-guarding tests were load-bearing: for each of eighteen defects, patch the
file, run the named test, expect red, restore. It reported eighteen reds. Every one was a lie.

The runner invoked `pytest ... -p no:xdist`, and this repo's `addopts` carries `-n --dist loadfile`.
Disabling the xdist plugin makes those arguments unrecognised, so every subprocess exited on a
usage error before collecting a single test. My red-check was `" failed" in stdout or "error" in
stdout.lower()` — and `ERROR: usage:` contains "error". The harness graded eighteen tests on
whether they could fail, using a runner that never started, and every answer was the same answer.

**Why it survived a read.** Nothing about the code looked wrong; the bug was in the *interaction*
between a flag I added for tidiness and a config file I did not open. The only signal was the
result itself — eighteen for eighteen, first try, on tests I had written minutes earlier. A
perfect score on a first pass is not a strong result, it is an implausible one.

**What the fix found.** Switching the check to `returncode != 0` plus an explicit guard for
"no tests ran" / "unrecognized arguments" turned 17 of 18 red and left one genuinely green — a
placement assertion that sliced its section at a `---` rule several headings below the section it
meant to bound, so a row relocated into a heading of its own was still "inside Workflow". That
assertion had been passing on exactly the prose it existed to reject, and only the eighteenth
mutant could see it.

**The general shape.** This is the same defect class as a test that cannot fail on its subject,
moved one level up: the instrument that measures load-bearingness was itself not load-bearing. So
the instrument needs the same treatment as the tests it grades — a case it must report as a
survivor, and a positive assertion that the measurement ran at all. `[learnings-detail.md]`
neighbours (L52, L448, L462, L506) all cover "a mutant that should die but lives"; this is the
inverse tell, and it is the one that looks like success.

## When editing `session-digest.md`, count CHARACTERS as well as tokens

The digest carries two independent budgets, enforced in two test modules that never reference each
other. `tests/test_v5_methodology.py` holds `LAST_MEASURED_INJECTED_TOKENS` and
`INJECTED_FOOTPRINT_CEILINGS` — a *policy* ratchet, with a documented procedure for declaring a
raise when a trim falls short. `tests/test_plugin_methodology_digest.py` holds
`ADDITIONAL_CONTEXT_INLINE_LIMIT = 10_000`, which is not policy at all: above it Claude Code stops
inlining the SessionStart context and spills it to a file, so no declaration, ruling or comment can
buy a character past it.

**How it bit.** The ad-hoc-delegation work did a careful token accounting — a class-based trim
measured in word deltas, a per-edit cost table, a declared raise with its counter-case recorded at
the assertion. Every assertion in the token module was green. The digest was 12 characters over the
inline limit, because 216 free characters at the branch point had never been part of anyone's
arithmetic. The token budget had been ratcheted to near-zero headroom over many commits, which made
it feel like *the* constraint; the character budget was the one actually about to bind.

**The general shape.** A surface with two budgets in two enforcement sites has a blind spot at
whichever site you are reasoning from, and the more elaborate the accounting at one site, the more
confident the blind spot feels. The fix was a reference at the accounting site rather than a third
mechanism: the token table now opens by naming the character wall and saying which one wins when
they disagree. Watch for the same shape wherever a thorough "budget" comment exists — its
thoroughness is evidence about one budget only.

## When designing any flow step that records status or bookkeeping, make it ride IN the PR that does the work

Ride-in-the-PR is a property of **being a commit**, not of the bookkeeping. The rule was written when
every archive was a file edit, and it was stated unconditionally: "an abandoned PR abandons the
archive too, so state can't drift." That is true of a commit and false of a remote side effect.

On a GitHub Issues backlog backend, `status --to shipped` closes the issue over the API the moment it
runs. Run on an unmerged branch — which is what "in the PR" tells you to do — it lands immediately
and survives an abandoned PR, leaving an item wrongly closed. Same drift the rule exists to prevent,
in the opposite direction, and worse: nothing sweeps for items closed too early
(brookstalley/prawduct#697; #687 and #688 are instances).

The equivalent for a remote side effect is to run it **at the merge, in the same breath** — after the
merge succeeds, before the local artifacts that record the debt are deleted. That is
`/prawduct:pr`'s Merge Flow *"Close the backlog items this PR resolves"* step. It is not the
post-merge commit the rule forbids: no commit is involved and the integration branch is never
touched.

Two consequences worth carrying. A `Closes #N` in a PR body does not substitute — GitHub fires
closing keywords only for merges into the repository's *default* branch, so on a gitflow base it is
inert. And this arrangement has no detector: `documentation/backlog-service-requirements.md` **GV3**
replaces ship-atomicity with traceability plus a reconciliation sweep, and the sweep is prescribed
but unbuilt, so the step running is the whole guarantee.


## When operator prose restates a PREDICATE, diff against the canonical statement

**Where it bit.** `fix/verify-resolutions-exit3-excluded-wip` (#722), 2026-08-26, caught as a
BLOCKING finding by the cumulative's R-1 — not by the suite, and not by the prose test the same
change added.

**The predicate.** `critic_consolidate.begin_review` decides where a `verify-resolutions` pass
anchors with `committed_differs = capture["head_tree"] != base_tree and not anchor_is_ahead`. Two
prose surfaces — `gates.py`'s `uncovered` remedy and `skills/pr/SKILL.md` Step 2 — needed to tell
an operator what that means for their next commit. Both shipped it as *"whether anything was
committed between the review it verified and the pass itself."*

**Why that is wrong, and why it looks right.** The expression is a TREE comparison. A commit-set
reading agrees with it in three of four cases and disagrees in the one that is the happy path: the
commit that vouches for a reviewed dirty tree materializes that tree *verbatim*, so the commit set
is non-empty while the trees are identical, and the anchor does not move. The commit-set phrasing
therefore tells a builder on the golden path that they owe another `verify-resolutions` — which is
the wasted round #722 exists to remove, reintroduced by #722's own fix, in the same commit.

**The failure was not misreading the code.** The code was read, understood, and cited in the same
session's comments. What went wrong is one layer up: the *operator-facing sentence* was composed
from a mental summary of the expression rather than checked against anything. And there was
something to check against — `review-cycle.md` § Verify-resolutions anchoring and demotion already
carried the correct statement, in prose, including the vouching-commit exclusion by name. It was
not opened. Principle 24 (Retrieval Over Generation) failing at the cheapest possible check.

**Why the duplication made it worse.** The rule had five prose carriers (`gates.py` ×2,
`pr/SKILL.md`, `critic/SKILL.md`, `building.md`). Editing two of them in one pass from one mental
model is how a single bad paraphrase became two shipped defects rather than one. Filed as #723:
the fix is a construction with one authoring home, not a longer list of pinned phrasings.

**What now stops it.** `tests/preferences/test_free_interval_prose.py` pins both halves — that each
stating surface phrases the test as committed *content*, and that each cites `review-cycle.md`
rather than restating the derivation. The pin is a floor, not the fix: it catches this sentence
regressing, not the next predicate paraphrased the same way.

**The tell, restated.** You can state the rule but cannot point at the sentence you got it from.
If the only source you can name is "the code", you are generating, not retrieving — go find whether
a canonical prose statement exists first, and diff against that.

## Prose about what a new guard BUYS must state its predicate, not its purpose

**What happened (2026-08-28, `fix/release-gate-blindness`).** The gate had just been taught to
refuse a release-pending change-log entry carrying no `scope=`. Writing the runbook paragraph
explaining what the operator gains, I concluded: *"nothing can hide from a `scope=`-keyed grep."*

**Why it was false, and the falsifier sat in the file I had just edited.**
`test_an_untagged_entry_is_still_invisible` pins that an entry with **no tag line at all** is
deliberately outside the gate's set — the gate claims no authority over entries predating the tag
convention. So the paragraph told the operator they could skip the untagged walk, which is the one
walk the new refusal does not cover. A document teaching a procedure shipped a new instance of the
blindness the code change was fixing.

**The mechanism.** "Scopeless entries can no longer hide" (motivation, true) and "nothing can hide"
(extension, false) are one word apart in English and a whole set apart in code. Prose about a guard
drifts toward its *purpose*, because purpose is what the author has in mind; the predicate is what
the reader will act on.

**Why the exclusion tests are the right instrument.** They are written precisely to pin what the
guard does NOT cover, so each states a boundary in one assertion — cheaper to read than the
implementation, and they fail loudly if the boundary later moves. Read them before writing the
sentence, not after a review returns it.

**Sharpest tell.** The claim turns on a term defined in BOTH the code and the operator prose with
different extensions — here, "release-pending". The sentence reaches for the document's definition
while its warrant is a function's.

## Naming a prior fix as "the same family" IS the class finding

**What happened.** Building the release-gate digest-coverage check, my pre-review scrub found that
the new `plugin/CHANGELOG.md` path would be printed at product repos, where it cannot exist. I
recorded it accurately, including the sentence *"same family as the no-version hint fixed in
R-13/R-30 (naming prawduct's own layout at a product user)."* My proposed remedy was to **reword the
message** — split the absent case from the unreadable case and drop the errno.

The independent review took the same fact and classified it as the **second member of a class**,
which changes the remedy in kind: one predicate deciding whether prawduct's own layout is this
repo's subject, **suppressing the whole arm rather than rephrasing it**, consumed by the first
member too, with the search bound stated as *every literal `plugin/` path this module prints*.

**Why the smaller conclusion was available and wrong.** A recurrence is not a coincidence between
two messages; it is evidence about the *first* fix — that it was scoped to an instance when the
defect was structural. R-13/R-30 had guarded one hint with an inline `.exists()`. That guard was
correct and insufficient, and nothing about it stopped the next `plugin/…` string from being
written, because there was no shared question to answer. Rewording the second message would have
left the third member equally free.

**Root cause.** A self-scrub asks *"what did I get wrong in what I just wrote?"* — and it works;
this one found the defect before any reviewer did. *"Has this been fixed here before?"* is a
different query over a different corpus (findings history, not the diff), and nothing in the scrub
pass runs it. The scrub found the instance because it was looking at the instance.

**The tell, sharpened.** You wrote a prior finding id into your own note as precedent, and the fix
you are proposing touches strictly fewer sites than that precedent did. Precedent that narrows your
remedy is precedent you have inverted: it should widen it. When you can name the earlier fix, the
next move is to re-run its stated reason as a search over the current tree — the review did exactly
that here (`grep -n "plugin/"`) and it returned three members, not one.

**Cheap and general.** Re-running a cited finding's own reason as a search costs one grep. It is the
same shape as the Retrieval-Over-Generation cheap-check gate: the cheapest verification that could
change the decision, done before committing to the decision.

## An exemption filter exempts environments, not just conditions

Found while merging PR #734 (`release-gate-blindness`), 2026-09-01.

The local suite was red on
`tests/test_norm_probes.py::TestSilentAgainstThisRepo::test_no_norm_lifecycle_advisory_fires_here_today`
— four `Status: in-transition` norms had crossed the 30-day stall window, so the probe emitted
`stalled-transition`. I told the user CI would "almost certainly" go red too. All four jobs passed.

The counts are what make it legible. Local: 5553 passed, 1 failed, 17 skipped. CI (3.14): 5554
passed, 0 failed, 17 skipped. **Same 5571 total** — so the test did not skip in CI, it *passed*.

The mechanism is one line of the test:

```python
fired = sorted(
    c.type
    for c in run_all_probes(state, codebase)
    if c.feature == "norm-lifecycle" and c.type != "backlog-cache-unreadable"
)
```

The `backlog-cache-unreadable` exclusion is well-reasoned, and the test says so in a comment: that
candidate is "true about this machine and nothing about the norms — asserting on it here would make
a clean clone's first test run red for a correct reason."

That reasoning is right about a clean clone and silently wrong about CI. Resolving "has this
tracking item been unchanged >30d" requires the backlog cache. The cache is gitignored. So in CI the
probe cannot reach the tracking items at all, emits `backlog-cache-unreadable`, and the filter drops
it — leaving `fired == []` and a green assertion that never evaluated a single norm.

**The generalisation.** An exemption filter is written thinking about a *condition* ("the cache is
missing on a fresh clone"). It actually quantifies over *environments*: every environment where the
subject is unreachable is now permanently exempt. When the unreachable resource is gitignored, that
set is exactly "every CI run" — which is to say, the only environment anybody watches
automatically. The test inverts: it is honest on the developer machine that can see the subject, and
vacuous on the machine whose green light gates merges.

**The fix shape** is not to remove the exclusion — it would make clean clones red for a correct
reason, which is why it exists. It is to add a reachability assertion beside it: assert the probe
*did* evaluate the tracking items (non-empty candidate set, or an explicit
`assert 'backlog-cache-unreadable' not in types` guarded by a cache-present precondition), so
"unreachable" fails loudly as an infrastructure gap rather than passing as a clean bill of health.

**Two adjacent entries this is NOT.** The `TestAgainstTheReal*` phase entry is about *time* — a
release ends the phase a self-referential test pinned. The set-emptiness entry is about a check whose
subject is a set that can legitimately be empty. This one is about *portability*: the same test, the
same commit, two environments, opposite verdicts, and the one that is wrong is the one that is
automated.

**My own error underneath it** was predicting one environment's result from another's rather than
asking the cheap question — could the assertion even reach its subject over there? Retrieval over
generation applies to predictions about tooling, not only to design decisions.

## A documented clearing arm is not evidence it is implemented

**Context.** `#732`, recording stopgaps for four stalled norm transitions. The advisory's own
remedy text and `probe_stalled_transition`'s docstring both say a recorded stopgap clears it.

**What was true.** Nothing in `plugin/lib/norm_probes.py` detects a stopgap. `_cited_stall_age`
resolves the tracking item's `updated_at` post-cutover (`_item_floor_date` off `reviewed:`/`added:`
before it), and the only other lever is `Status:` leaving `in-transition`. The word `stopgap`
occurs in the module exclusively in comments and in the two strings shown to a reader.

**Why it is more than a doc bug.** The failure is directional. Doing the documented thing —
writing the stopgap into the norm entry — leaves the advisory firing, and the operator is then one
step from the lever that does work: touch the item. That is precisely the "silent departure" the
Authority Rule forbids, reached by following the instructions. A prose contract that names an
unimplemented arm does not merely fail to help; it routes compliant people to the forbidden move.

**What actually cleared it here.** `docs/norms.md` puts an exception's clock on a backlog item, so
recording it meant commenting on #342/#341/#164 — which moved `updated_at`, the *touched* arm. The
right outcome by the wrong mechanism. Filed as `#737`; the preferred remedy is teaching the probe
to honour a `Stopgap:` field while its expiry is in the future, which also gives the expiry the
mechanical firing path it currently lacks.

**Generalises to.** Any gate, probe or linter whose docstring enumerates exemptions. Before
building the fix the docs describe, grep for the mechanism. If it is absent, that is the finding.

## A deduped summary undercounts the sites, and going quiet hides the miss

**Context.** `#732`. The advisory named four stalled transitions: `architecture.md`→GOV-2R8K,
`architecture.md`→GOV-4T9P, `architecture.md`→LNG-5W8R, `nonfunctional-requirements.md`→LNG-5W8R.

**The trap.** `_scan_direction_citations` accumulates into `found[(path.name, cited)]` — a dict
keyed by artifact and tracking id. `architecture.md` carries **two** in-transition entries citing
LNG-5W8R (the Python-agnosticism norm at the per-suffix-dispatch rule, and the
guides-never-implements corollary at the linter-duplication rule). They collapse to one row.

**Why the miss would have survived.** Editing the four printed rows clears the advisory completely,
because the key that was already satisfied stays satisfied. The fifth entry would have gone on
governing new work with no recorded exception, and no signal would ever have pointed at it. A
report going quiet is evidence about the report's key, not about the sites.

**What to do.** Read the scan, not the summary — here, iterate `_direction_lines` and filter on
`_IN_TRANSITION_RE` directly, which returns five. Where a report aggregates, its row count and your
edit count are different quantities and should be reconciled explicitly.
