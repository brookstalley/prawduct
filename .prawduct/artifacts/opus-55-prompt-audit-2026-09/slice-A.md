# Slice A: the always-on surface (session digest, root CLAUDE.md, principles.md, learnings rules, hook- and gate-emitted model text)

## Inventory

Read in full:
- `plugin/methodology/session-digest.md`: 1,462 words (9,499 characters stripped, against a 9,500 working budget and a 10,000 wall; `tests/test_plugin_methodology_digest.py:259-285`)
- `CLAUDE.md`: 1,062 words
- `plugin/docs/principles.md`: 2,866 words
- `.claude/rules/learnings/core.md`: 1,560 words, 38 rules
- `.claude/rules/learnings/authoring.md`: 2,936 words, 74 rules
- `.claude/rules/learnings/hook-surface.md`: 2,662 words, 67 rules
- `.claude/rules/learnings/tests.md`: 2,254 words, 54 rules
- `.claude/rules/learnings/reviews.md`: 1,402 words, 35 rules
- `.claude/rules/learnings/release.md`: 839 words, 22 rules
- `.claude/rules/learnings/gates.md`: 495 words, 12 rules
- `.claude/rules/learnings/backlog.md`: 267 words, 7 rules
- `.claude/rules/learnings/pr.md`: 131 words, 3 rules
- `plugin/hooks/digest.py`: 923 words. It emits the digest file verbatim and adds no model-facing text of its own.
- `plugin/hooks/banner.py`: 2,820 words. Its only directive is the one-line relay at `:413-416`, which is clean.

Read only at the model-facing string sites (these are code files; I read every emitted string, not every line):
- `plugin/bin/prawduct-hook` (59,069 words): `cmd_stop` at `:2472-3700`, which covers every Stop-gate blocker, deferral and advisory string
- `plugin/lib/briefing.py` (12,938 words): `assemble_session_briefing`, `_handoff_pointer`, `ADVISORY_RELAY_TEXT`, `_learnings_lines`, `_learnings_limit_lines`, and the handoff renderer's prose
- `plugin/lib/critic_consolidate.py` (40,752 words): `_CACHE_WARM_DIRECTIVE`, `_FIX_ORDER`, `_BATCH_FIX_DIRECTIVE`, `_COVERAGE_IS_A_SEPARATE_QUESTION`, `span_clause`, `_RIDE_ALONG_ROUTE`, `_IF_YOU_FIX_SOME`, `_RIDES_NEXT_REVIEW_LEAD`, `cost_lead`, `next_action_line`, `RESOLUTION_IS_A_CLAIM_DIRECTIVE`, `VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE` (tail), `FINDING_SCOPE_DIRECTIVE`, the in-flight wait strings `:4995-5035`, and the `consolidate()` print `:5590-5640`
- `plugin/lib/gates.py` (19,233 words): `blocking_remedy_lines` `:2264-2330`, the only prose block it renders for the Stop and PR gates

## Summary

The single highest-impact change is an **add** to the digest. Opus 5.5 ends turns early, and the always-on surface never tells it not to. `session-hygiene.md` step 1 already says "do it, do not end the turn", but the digest compresses that step away (A-1). The add is paid for, with room to spare, by compressing four digest bullets (A-17 to A-20). The second-largest lever is `next_action_line` (A-5). It reaches every builder after every review at about 355 words, and on the consolidate path it follows a 179-word directive that restates the same fix order (A-6, A-7). The learnings corpus is the clearest case of patch accretion in the slice. `core.md` holds nine separate "falsify your claim before writing it" rules. These are mostly self-verification that Opus 5+ does unprompted, and they collapse into two rules. In total `core.md` goes from 38 rules to about 17 (A-8 to A-15), and the area files carry the same clusters again (A-31 to A-38). Two learnings rules restate the digest, and one of them contradicts it (A-2, A-3).

Counts: 42 decisions. By action: 30 rewrite, 7 remove, 2 add, 3 flag. By confidence: 4 high, 35 medium, 3 low (all flags). 12 are `machine_read: yes`, and 9 are `model_dependent: yes`. With every digest decision taken, the digest drops from 9,499 to about 9,100 characters, so `DIGEST_HEADROOM_RESERVE` recovers about 400 characters.

## Decisions

### A-1: Digest: name the early stops to avoid
- location: `plugin/methodology/session-digest.md:118-121`
- evidence: "**Close with the standing block** — unpadded, after every other word, since the bottom is"
- pattern: Opus 5.5 early turn-ending (prompting guide: "naming the specific early stops to avoid helps"); guide keep-list #11 (re-baselining adds text)
- why: Opus 5.5 ends long turns by announcing the next step, offering to carry on, or listing decisions it could make itself. The digest is the only turn-ending guidance every session sees. It carries the standing-block format but not session-hygiene's first step ("Is there work you can do right now…? Then do it — do not end the turn"), so the one rule that counters early stops never reaches the always-on surface.
- confidence: high
- action: add
- replacement: insert as the first paragraph under `## Closing the turn`, above the standing-block rule:
  "**If you can take the next step with what you have, take it.** Don't end a turn to announce the next step, offer to continue, or list decisions you could make yourself; a turn ends when the work is done, when a machine event must land, or when only the user can unblock it."
  This costs about 290 characters. A-17 through A-20 pay for it; see A-17 for the combined section.
- model_dependent: no
- machine_read: no. `TestTheStandingBlockIsTheDigestsLastWord` anchors on the substring "Close with the standing block" and on the tail after it, and text inserted above it passes both tests.

### A-2: authoring.md: the chunk-id rule contradicts the digest
- location: `.claude/rules/learnings/authoring.md:27`
- evidence: "carry the why inline; build plans are deleted after completion"
- pattern: #342 duplicated fact, where the copies disagree (guide keep-list #8 exception); Group 2 volatile specifics
- why: The digest says "completed plans are archived, not deleted", and principles #13 agrees. This rule gives the opposite reason for the same rule. Duplicates that disagree are the one case the keep list says to dedupe.
- confidence: high
- action: remove
- replacement: (delete)
- model_dependent: no
- machine_read: no
- dup_of: `plugin/methodology/session-digest.md:24-28`; `plugin/docs/principles.md:54`

### A-3: authoring.md: the Status-box rule restates the digest
- location: `.claude/rules/learnings/authoring.md:31`
- evidence: "Review first, tick after: the LAST tick disarms the Stop gates. Prose calling boxes derived is stale"
- pattern: #342 duplicate; Group 1d migration-relative phrasing ("Prose calling boxes derived is stale")
- why: The digest bullet states the same rule and the same mechanism to every session. This copy only adds a clause that describes a retired belief.
- confidence: high
- action: remove
- replacement: (delete)
- model_dependent: no
- machine_read: no
- dup_of: `plugin/methodology/session-digest.md:29-30`

### A-4: core.md rule 13 restates Principle 24
- location: `.claude/rules/learnings/core.md:19`
- evidence: "Before committing a consequential decision under momentum, do the cheapest check that could change it FIRST"
- pattern: #342 duplicate; Group 1c padding (repetition as reinforcement)
- why: Principle 24 and the digest stance bar "retrieval before generation" carry the same rule with the same examples ("read the mechanism before tuning it, search practice, re-read the artifact"). An always-loaded copy adds cost and nothing else.
- confidence: high
- action: remove
- replacement: (delete)
- model_dependent: no
- machine_read: no
- dup_of: `plugin/docs/principles.md:91`, `plugin/methodology/session-digest.md:95-96`

### A-5: NEXT-ACTION: cut the builder's close from ~355 words to ~150
- location: `plugin/lib/critic_consolidate.py:942-1000` (arms of `next_action_line`), `:566-573` (`_RIDE_ALONG_ROUTE`), `:607-615` (`_IF_YOU_FIX_SOME`)
- evidence: "finding(s) gate NOTHING: no gate reads them, so nothing in THIS review"
- pattern: Group 1a pressure language (THE REVIEW IS OVER, NOTHING, THIS, ONLY, NOT, NEXT); Group 1c padding and strategy coaching; Group 2 verbose explanation of mechanics
- why: Measured, the warnings arm with cost lead, observations and price is 355 words, and it is the one surface every builder meets after every review. Most of it re-argues the decision ("That is NOT the deferral warned against above…", "you do not have to judge that… asking costs nothing, and a refusal is the answer, not a reason to retry"). Opus 5.5 follows a plain statement of the decision, the command and the cost. The caps make the text read as anxious and push the builder toward over-applying it.
- confidence: medium
- action: rewrite
- replacement: keep the computed pieces (`cost`, `span`, `price`, `carried`) and replace the fixed text as follows.
  - Warnings arm: `lead + f"0 blocking — the review is over. Its {warning} warning(s) and {note} note(s) gate nothing{obs}. Decide each: accept by default with `prawduct-hook disposition {ref} <fid|oid> --accept \"<reason>\"` (no review, no tree move), or fix." + coverage_clause + fix_tail`, where `obs = f", nor do its {observations} observation(s) (answer them by `O-n` id)" if observations else ""`.
  - Blocking arm: `f"{blocking} BLOCKING finding(s) gate this work. Fix them, and decide every warning and note in the same pass (fix, or accept with `prawduct-hook disposition {ref} <fid|oid> --accept \"<reason>\"`, which needs no review): " + _FIX_ORDER + "." + _RIDE_ALONG_ROUTE + price`.
  - `_IF_YOU_FIX_SOME`: `" If you fix some, " + _FIX_ORDER + ". Dispatch exits 3 (`no review needed`) when the fixes touch nothing judgeable, so dispatching is how you find out; judge by the gate after the commit, not output printed before it."`
  - `_RIDE_ALONG_ROUTE`: `" If more judgeable work is coming on this branch, a fix can instead ride the next chunk's commit; record it in the build plan or `.prawduct/.handoff-notes.md` so that chunk meets it."`
  - Apply the same lowercasing (keep `BLOCKING` as the severity token) to `cost_lead` ("AT REVIEW TIME", "COVERS") and `span_clause` ("BRANCH").
- model_dependent: no
- machine_read: yes. The `NEXT-ACTION:` prefix is relayed verbatim by the reviewer protocol files. The text is pinned by `tests/test_critic_consolidate.py` (`TestNextActionLine` :972; asserts "THE REVIEW IS OVER", "gate NOTHING", "NOT DONE"), `tests/test_carried_blocking_findings.py`, `tests/test_cost_of_commit.py`, `tests/test_review_interval_extension.py` and `tests/preferences/test_free_interval_prose.py`, and `tests/test_briefing_functions.py` replays it. Every assertion on the old wording needs updating.

### A-6: `_BATCH_FIX_DIRECTIVE`: shorten it and remove its dangling cross-reference
- location: `plugin/lib/critic_consolidate.py:351-363`
- evidence: "Disposition them ALL in ONE pass — accept or file the rest, and for every"
- pattern: Group 1a (ALL, ONE, ONLY, OUTSIDE); Group 1c padding
- why: `consolidate()` prints this 179-word directive directly above NEXT-ACTION, which states the same fix order again. Its own docstring (`:340-349`) forbids positional cross-references, because on `_already_consolidated_note` nothing follows it. Yet it says "(NEXT-ACTION says which)", which dangles on exactly that path.
- confidence: medium
- action: rewrite
- replacement: `" Decide every finding in one pass: accept or file what you won't fix, and " + _FIX_ORDER + ". Only unresolved BLOCKING findings gate anything; the verify pass is owed only if the fixes touch judgeable files and no later review the plan owes will carry them. " + _FIX_ORDER_AFTER_CUMULATIVE + " Judgeable (moves the tree): code, config, data, tests, and `.md` under `skills/`, `methodology/`, `templates/` or a root `CLAUDE.md` (a comment-only code edit counts). Free at any time: everything under `.prawduct/` (change-log, backlog, project-state, build plans), `.claude/settings.json`, and other `.md` files."`
- model_dependent: no
- machine_read: yes. `TestBatchFixDirective` (`tests/test_critic_consolidate.py:1901`) parses the backticked path tokens, and the replacement keeps all seven. It is also asserted in `tests/test_cost_of_commit.py` and `tests/test_v5_methodology.py`.

### A-7: gates.py restates the fix order in its own words
- location: `plugin/lib/gates.py:2298-2304`
- evidence: "Fix ALL of them in the working tree first — do not commit between fixes."
- pattern: #342 duplicated prose (not a derivation); Group 1a (ALL, ONE, BECAUSE)
- why: `critic_consolidate._FIX_ORDER`'s comment says every directive that tells a builder how to land fixes "composes it, so no carrier can state a different order". `blocking_remedy_lines`, which the Stop and PR gates render, does not compose it. It holds a second, 7-line wording of the same order.
- confidence: medium
- action: rewrite
- replacement: `[f"Fix them: {critic_consolidate._FIX_ORDER} — that commit carries the resolution facts, so this evidence passes with no full re-review (review-cycle.md § Verify-resolutions anchoring and demotion)."]`. Import lazily if `gates` must stay import-light.
- model_dependent: no
- machine_read: yes. Its line strings are asserted wherever the Stop/PR block text is pinned. Grep `blocking_remedy_lines` in `tests/`.
- dup_of: `plugin/lib/critic_consolidate.py:296-299`

### A-8: core.md: merge the claim-falsification cluster into two rules
- location: `.claude/rules/learnings/core.md:8,16,22,23,28,29,32,37,39` (rules 2, 10, 16, 17, 22, 23, 26, 31, 33)
- evidence: "run the one query that would falsify it — coverage claims are the top error class here"
- pattern: Group 1d patch accretion; Opus 5 over-verification ("self-check instructions are the same trap")
- why: Nine rules restate one principle, each with its own incident. Opus 5+ already checks its own claims, and a stack of "verify before you write" instructions produces over-verification. What is not default behavior is the method: a check must be shown able to fail, and a query must target the concept rather than your own wording. The merge keeps that method and drops the repetition.
- confidence: medium
- action: rewrite
- replacement: delete rules 2, 10, 16, 17, 22, 23, 26, 31 and 33, and add two rules.
  - "A check never seen to return non-zero proves nothing — before trusting a zero, a clean sweep or 'X costs nothing', feed the instrument a case it must catch. Tell: the result confirmed what you hoped, first try." (210 chars)
  - "A coverage, completeness or absence claim ('X now handles Y', 'no Y', 'all') holds only when its falsifying query returns nothing — query the concept in more than your own words, over the unsliced set; a count of sites fixed is not that." (237 chars)
- model_dependent: yes
- machine_read: no

### A-9: core.md: merge the class-versus-instance rules
- location: `.claude/rules/learnings/core.md:7,30,35` (rules 1, 24, 29)
- evidence: "A fix lands at the instance a review named; the defect lives in the class"
- pattern: Group 1d patch accretion; Group 1c near-duplicates
- why: Three rules state one idea: find the class, fix it through one owner, then re-check. The re-check clause in rule 29 is builder self-verification.
- confidence: medium
- action: rewrite
- replacement: "A review finding names an instance; the defect is a class. Say in one sentence why it broke — if that sentence covers sites outside your diff, fix the class through one owner. Tell: your second fix of one class in two rounds." (225 chars)
- model_dependent: yes
- machine_read: no

### A-10: core.md: merge the enumerate-by-query rules
- location: `.claude/rules/learnings/core.md:11,17,40` (rules 5, 11, 34)
- evidence: "Surveying a shared thing takes TWO searches: grepping the thing finds copies, not DEPENDENTS"
- pattern: Group 1d patch accretion
- why: All three rules are about how to bound and search a set. One rule carries all three insights.
- confidence: medium
- action: rewrite
- replacement: "Enumerate a set by query, never memory, and bound it by the property that justifies it, not a location: grep the thing's shape for copies and its name and wrappers for dependents. Tell: the boundary is a path, the rationale a verb." (231 chars)
- model_dependent: no
- machine_read: no

### A-11: core.md: merge the "update what describes it" rules
- location: `.claude/rules/learnings/core.md:24,26,36,41,43` (rules 18, 20, 30, 35, 37)
- evidence: "When you change a MECHANISM, cascade-search the CLAIM, not the code"
- pattern: Group 1d patch accretion
- why: Five rules each patch one surface of a single obligation: prose, names, registries, superseded sentences, claims.
- confidence: medium
- action: rewrite
- replacement: "A mechanism change is done when every artifact DESCRIBING it agrees: search for the claim, not the tokens you edited, across prose, tests, templates and registries, and delete superseded sentences and removed names rather than adding beside them." (246 chars)
- model_dependent: no
- machine_read: no

### A-12: core.md: the handoff rules restate the digest and session-hygiene
- location: `.claude/rules/learnings/core.md:25,31,42` (rules 19, 25, 36)
- evidence: "State that exists ONLY in context must be written down before the turn ends"
- pattern: #342 duplicate; Group 1c padding
- why: Rules 19 and 36 restate the digest handoff bullet and session-hygiene's findings-only rule. Rule 25 (file a backlog item now, don't route it to the handoff) is the only non-duplicate content.
- confidence: medium
- action: rewrite
- replacement: delete rules 19 and 36, and replace rule 25 with: "File a backlog item the moment you decide it should exist — routing it to the handoff is not filing it, and a crash or exhausted context loses an unwritten handoff." (164 chars)
- model_dependent: no
- machine_read: no
- dup_of: `plugin/methodology/session-digest.md:47-56`, `plugin/methodology/session-hygiene.md:44`

### A-13: core.md: merge "open what you cite"
- location: `.claude/rules/learnings/core.md:9,38` (rules 3, 32)
- evidence: "When a criterion, plan or rule DESCRIBES an artifact, open the artifact before building to the description"
- pattern: Group 1d patch accretion
- why: Both rules say "read the named thing before acting on a description of it". Rule 32 adds only the gate-specific clause.
- confidence: medium
- action: rewrite
- replacement: "Open what a criterion, plan or stated reason names before building to it or citing it — a description inherits its author's blind spot, and a gate's behaviour lives in the function returning its verdict. Tell: you could comply without opening it." (246 chars)
- model_dependent: no
- machine_read: no

### A-14: core.md: delete two narrow re-check rules and split a double rule
- location: `.claude/rules/learnings/core.md:10,12,14` (rules 4, 6, 8)
- evidence: "Before clearing a reader/caller/path as unaffected, re-read what you just wrote about the mechanism's lifetime"
- pattern: Group 2 recency trap; Opus 5 over-verification
- why: Rule 8 encodes one session's stumble as a standing re-read. Rule 4 ("grep tests for the new symbol") is covered by "Tests are contracts" in the digest and by tests.md. Rule 6 packs two unrelated rules into one line; its "provably equivalent" half is not about the backlog at all.
- confidence: medium
- action: rewrite
- replacement: delete rules 4 and 8. Replace rule 6 with: "Before implementing against a mechanism, search the backlog for its name — an open item may already redefine or retire it."
- model_dependent: yes
- machine_read: no

### A-15: core.md per-rule disposition (index)
- location: `.claude/rules/learnings/core.md:7-44`
- evidence: "Each rule is one line of at most 250 characters. This file is capped, so a new rule is paid for by merging or retiring one."
- pattern: disposition table for the decisions above
- why: The brief asks for a disposition on every rule.
- confidence: medium
- action: rewrite
- replacement (rule number → disposition): 1 merge→A-9 · 2 merge→A-8 · 3 merge→A-13 · 4 delete (A-14) · 5 merge→A-10 · 6 rewrite (A-14) · 7 keep · 8 delete (A-14) · 9 keep · 10 merge→A-8 · 11 merge→A-10 · 12 keep · 13 delete (A-4) · 14 keep · 15 keep · 16 merge→A-8 · 17 merge→A-8 · 18 merge→A-11 · 19 delete (A-12) · 20 merge→A-11 · 21 keep · 22 merge→A-8 · 23 merge→A-8 · 24 merge→A-9 · 25 rewrite (A-12) · 26 merge→A-8 · 27 keep · 28 keep · 29 merge→A-9 · 30 merge→A-11 · 31 merge→A-8 · 32 merge→A-13 · 33 merge→A-8 · 34 merge→A-10 · 35 merge→A-11 · 36 delete (A-12) · 37 merge→A-11 · 38 keep. The result is 9 kept, 2 rewritten and 6 merged rules, 17 in all, down from 38. The capped file's header line stays.
- model_dependent: yes
- machine_read: no. The corpus is linted by `record_lint` for format and budget, not for content.

### A-16: Learnings header: drop the per-rule narration obligation
- location: `.claude/rules/learnings/core.md:3` (canonical source `plugin/lib/learnings_files.py:93-98`; copies at `authoring.md:11`, `hook-surface.md:8`, `tests.md:7`, `reviews.md:8`; carried again by `plugin/lib/briefing.py:1185`)
- evidence: "name the rule and say what it changes about that decision — or say that it does not apply, which is also an answer."
- pattern: Group 1f output-shaping choreography; Opus 5 verbosity and narration
- why: With 38 core rules and dozens more per area file, "say what it changes… or say that it does not apply" instructs the model to narrate rule-by-rule applicability. Opus 5 already over-narrates, so this pushes user-facing text longer without changing the work. Stating it five times, plus the briefing's "cite the one you applied", is repetition as reinforcement.
- confidence: medium
- action: rewrite
- replacement: set `CORE_HEADER` to "**Apply a rule below where it bears on the decision in front of you, and cite it where it changed what you did.**" Delete the obligation sentence from the four area-file headers and keep their scoping sentence ("Rules that fire while…"). Leave the briefing line as is.
- model_dependent: no
- machine_read: yes. `tests/test_learnings_files.py:365-366` asserts "Reading a rule is not applying it" and "does not apply" in `CORE_HEADER`; `:662` excludes the header from rule units; `tests/test_plugin_init.py` also reads it. `CORE_HEADER` ships to every migrated product repo.

### A-17: Digest: compress "Closing the turn"
- location: `plugin/methodology/session-digest.md:120-134`
- evidence: "priceable). A handed-over turn may sit for days: first persist a findings-only turn's or"
- pattern: Group 1d patch accretion (many narrow conditionals); Group 1c jargon ("a reason citing the message itself is the defect said aloud")
- why: The section packs each of session-hygiene's case rulings into one run-on paragraph. Several rulings are unparseable without the source ("the defect said aloud"). Restating the same rules plainly lets the section carry A-1's add at a net cost of +57 characters.
- confidence: medium
- action: rewrite
- replacement (the whole section body, with A-1's paragraph first):
  "**If you can take the next step with what you have, take it.** Don't end a turn to announce the next step, offer to continue, or list decisions you could make yourself; a turn ends when the work is done, when a machine event must land, or when only the user can unblock it.

  **Close with the standing block** — last, unpadded — on any turn that ends a chunk or work cycle or leaves work outstanding. A `---` rule, then three separate paragraphs: `STATE` (what changed; committed?; suite green?) · what produces the next turn: `RUNNING` (a machine event — name it and what you do if it never lands) / `YOUR TURN` (only they can — lead with the ask) / `COMPLETE` (nothing, and no next action to propose) · `SAFE TO CLEAR` or `DO NOT CLEAR` (the label is the verdict, the copy the reason). If they must speak it is `YOUR TURN`, unless a clear would kill running work (then `RUNNING`, ask in the copy); don't predict that they will need to. Work in flight — a dispatched review, an unread background agent — is `RUNNING`, never `COMPLETE`. Only `RUNNING` may say `DO NOT CLEAR`; a live review's copy gives elapsed time, roster and expected finish when priceable. Before handing over, persist conversation-only output (findings, a delegate's report) to `.prawduct/.handoff-notes.md`.
  Full rule: `methodology/session-hygiene.md`."
- model_dependent: no
- machine_read: yes. The labels are parsed from the model's closing message by the Stop hook (`lib/gates.turn_declares_in_flight`, `turn_contradicts_its_verdict`). The label set in this section is pinned by `tests/test_stop_verdict_defer.py:542-545`, and the rule substring and the closing sentence by `tests/test_plugin_methodology_digest.py:707-755`. The replacement keeps all six labels, "Close with the standing block", and the final sentence.

### A-18: Digest: the "STOP" line before code
- location: `plugin/methodology/session-digest.md:15-16`
- evidence: "**Before writing ANY code against a build plan: STOP and read the build cycle via"
- pattern: Group 1a pressure language (bold, "ANY", "STOP", "#1 governance failure")
- why: This is a real trigger with a real reason, but it is shouted. Opus 5.5 follows a plainly stated precondition, and inflated emphasis over-applies, for example to one-line edits that are not against a plan.
- confidence: medium
- action: rewrite
- replacement: "Before writing code against a build plan, read the build cycle (`/prawduct:methodology building`); coding without it is the most common governance failure."
- model_dependent: no
- machine_read: no. `/prawduct:methodology building` is pinned by `tests/test_plugin_methodology_digest.py:290` and is kept; the "ANY code" assertion at `:667` reads `methodology/SKILL.md`, not the digest.

### A-19: Digest: compress the durable-prose bullet
- location: `plugin/methodology/session-digest.md:24-28`
- evidence: "- **Durable prose never rides on a value that changes under it** — one rule, two carriers. Don't"
- pattern: Group 1c padding (internal jargon "one rule, two carriers"; restated parenthetical)
- why: Opus 5 already avoids "where it came from" comments by default. What the model needs from this bullet is the rule and its exemption, not its taxonomy.
- confidence: medium
- action: rewrite
- replacement: "- **Durable prose never rides on a value that changes under it.** A comment, docstring or long-lived spec carries its *why* inline — never a chunk number that renumbers or a count copied from a nearby line. Bookkeeping that records the work is exempt, and a pointer to a plan resolves (completed plans are archived)."
- model_dependent: no
- machine_read: no
- dup_of: `plugin/docs/principles.md:54` (the long form; the digest keeps the trigger)

### A-20: Digest: compress the handoff-notes bullet
- location: `plugin/methodology/session-digest.md:47-56`
- evidence: "`.session-reflected`, its backward-looking twin). Write it at each chunk close, and **never ask"
- pattern: Group 1a (three bold spans in one bullet); Group 1c padding
- why: At 816 characters this is the digest's longest bullet. It restates its reasons twice. Keep the instructions and one reason.
- confidence: medium
- action: rewrite
- replacement: "- **Forward notes go in `.prawduct/.handoff-notes.md`**, yours to write (as is `.session-reflected`) at each chunk close. Prepare it without asking — asking costs a round-trip and a cold-cache replay — then signal; write \"nothing beyond the plan\" rather than no file. Read and reconcile before rewriting — never blind-append: only `/clear` consumes it, so a later batch finds earlier notes live. Drop what the work discharged, correct what moved, keep what still bites. `.prawduct/.session-handoff.md` is regenerated at every `/clear`; don't write there."
- model_dependent: no
- machine_read: yes. `tests/test_v5_methodology.py:2518-2521` requires "never blind-append" (case-insensitive) in the digest, and the replacement keeps it.

### A-21: Digest: the tangent bullet offers delegation first
- location: `plugin/methodology/session-digest.md:67-69`
- evidence: "- **A mid-chunk tangent that is ready to build gets a decision, not a reflex** — delegate it"
- pattern: prawduct "delegation push"; Opus 5 over-delegation ("remove any 'delegate more' guidance")
- why: Opus 5+ reaches for subagents too readily. Listing "delegate it" as the first option on the always-on surface makes it the default. The owner's policy row (`Delegation: off`) stays reachable.
- confidence: medium
- action: rewrite
- replacement: "- **A mid-chunk tangent that is ready to build gets a decision, not a reflex** — do it now, backlog it, or delegate it when a parallel track shortens wall clock without colliding with your files (unless `project-preferences.md` sets `Delegation: off`); say which (`/prawduct:methodology delegation`)."
- owner amendment (F4 ruling, 2026-09-28): the criterion is the owner's — "delegation should be used when it will accelerate wall clock without materially creating conflict" — not size alone. Recount the digest's characters when applying.
- model_dependent: no
- machine_read: no. The three-way-option tests in `tests/test_v5_methodology.py:3417,3647,3788` read `delegation.md` and the backlog skill, not the digest.

### A-22: Stance bar "verify your own work before done" (digest and principles.md)
- location: `plugin/methodology/session-digest.md:97`
- evidence: "recommendation · research fast-moving facts · verify your own work before"
- pattern: Opus 5 "Over-verification: delete your verification scaffolding"; brief keep #2 (keep the output contract)
- why: A standing instruction to verify its own work causes over-verification on Opus 5+. The binding half is the reporting contract: a "done" is shown with evidence, not asserted. Rename the bar to that contract.
- confidence: medium
- action: rewrite
- replacement: in the digest, `show evidence for "done"` (in place of `verify your own work before "done"`). At the bar's home, `plugin/docs/principles.md:119-120`, replace the bullet with: "- **Show evidence for \"done\"** — a completion claim cites what shows it (a test run, output, a real invocation); never assert success."
- model_dependent: yes
- machine_read: no
- dup_of: `plugin/docs/principles.md:119-120`

### A-23: principles.md: a paragraph restating all nine bars in the negative
- location: `plugin/docs/principles.md:126-130`
- evidence: "Each bar names its own failure, and the failure is the check: a claim with no evidence behind it,"
- pattern: Group 1c padding (repetition as reinforcement)
- why: Every bar above this paragraph already names what it forbids ("never paper over", "don't assert success", "if you find none, say so"). The paragraph lists all nine again.
- confidence: medium
- action: remove
- replacement: (delete)
- model_dependent: no
- machine_read: no

### A-24: principles.md: placement notes addressed to authors, not the model
- location: `plugin/docs/principles.md:5` (last sentence), `:103-107`
- evidence: "always-injected session digest carries the lead position — *your first duty on any substantive ask"
- pattern: Group 1c padding; Group 2 "verbose… restates another file"
- why: Twice in this file, prose explains which surface carries the stance and why the bars live here. That is an authoring rationale, and it already sits in `tests/test_plugin_methodology_digest.py`'s `DIGEST_SECTION_PLACEMENT`. The model reading principles gains nothing from it.
- confidence: medium
- action: rewrite
- replacement: delete the last sentence of line 5. Replace lines 103-107 with: "How the constitution above shows up in the working voice, as nine checkable bars. The lead position comes first: on any substantive ask, give the expert take — the risks, the stronger or simpler alternative, a recommendation with its reasoning — before complying."
- model_dependent: no
- machine_read: no

### A-25: CLAUDE.md: the compact instructions preserve what compaction re-injects anyway
- location: `CLAUDE.md:99-110`
- evidence: "- The requirement to read `plugin/methodology/building.md` before writing any code"
- pattern: Group 1d instruction re-insertion (a retention crutch); #342 duplicate
- why: `hooks.json` re-runs `digest.py` on `compact` (matcher `startup|resume|clear|compact|fork`), so the building-first, Critic and reflection rules come back verbatim after every compaction, and CLAUDE.md itself is re-loaded. Asking the summarizer to preserve them, and "the instruction to re-read CLAUDE.md", spends summary space on text that is re-sent anyway.
- confidence: medium
- action: rewrite
- replacement: "## Compact Instructions\n\nWhen compacting, preserve: which product is being built and its current work (size, type, description); unresolved issues, blocked work and pending decisions; and learnings not yet captured. Governance is re-injected on compact by the session digest, so summarize what you learned from methodology files and cite their paths rather than inlining them."
- model_dependent: no
- machine_read: no

### A-26: CLAUDE.md: requirements check 4 duplicates the digest's stance lead
- location: `CLAUDE.md:34-35`
- evidence: "4. **Should it be built as asked?** Lead with the expert take — the risk, the simpler"
- pattern: #342 duplicate. `digest.py:43-48` sets the policy: "When a repo's own always-loaded CLAUDE.md overlaps this digest, the fix is to trim that CLAUDE.md".
- why: The digest gives this repo the same "expert take first" rule on every session.
- confidence: medium
- action: remove
- replacement: delete item 4 and change "check four things" (`:29`) to "check three things".
- model_dependent: no
- machine_read: no
- dup_of: `plugin/methodology/session-digest.md:91-93`

### A-27: Stop gate: reflection blocker coaches cadence at block time
- location: `plugin/bin/prawduct-hook:2706-2710`
- evidence: "Going forward, reflect at WORK BOUNDARIES — right after Critic passes, after a bug"
- pattern: Group 1c strategy coaching; Group 1a caps
- why: The paragraph repeats the cadence advice from CLAUDE.md and `reflection.md` every time the gate blocks. Deleting it changes neither what is legal nor what passes, which is the guide's test for strategy coaching. One line keeps the point.
- confidence: medium
- action: rewrite
- replacement: `"  Reflect at work boundaries (after a Critic pass, a bug fix, an error recovery) and this gate never fires at /clear.\n"` in place of the five-line paragraph.
- model_dependent: no
- machine_read: no. Nothing in `tests/` matches "Going forward" or "creates friction".

### A-28: Stop gate: the escape-hatch paragraph repeats once per blocker
- location: `plugin/bin/prawduct-hook:2717-2723, 2831-2837, 3175-3188, 3376-3386, 3604-3612`
- evidence: "Escape hatch: if this gate cannot be satisfied this session (rare for reflection —"
- pattern: Group 1c padding (the same paragraph five times; two or three at once when several gates block)
- why: Each blocker carries its own 6-9 line copy of the waiver recipe, which differs only in the key. When two gates block together, the model reads the recipe twice and the waiver becomes the loudest thing in the message.
- confidence: medium
- action: rewrite
- replacement: remove the per-blocker hatch and print one footer after the `BLOCKED` list: "Escape hatch: if a gate above genuinely cannot be satisfied this session, waive it with a specific reason — `echo '{\"<key>\": \"reason\"}' > .prawduct/.gates-waived` (keys: reflection, learnings, critic, pr; for an unfinished review run `prawduct-hook critic-discard` first, never `rm`). Empty reasons are rejected; the file clears at the next fresh start or /clear. When it is appropriate: `/prawduct:methodology building` (Gate waivers)." Gates with no waiver (learnings budget) keep their "There is no waiver" line.
- model_dependent: no
- machine_read: yes. `tests/test_reflection_gate.py:434` and `tests/test_learnings_cutover_gate.py:231` slice each block at "\n\n  Escape hatch", and both need rewriting.

### A-29: Reviewer dispatch directives: "Spend this on…" closers
- location: `plugin/lib/critic_consolidate.py:1062-1065, 1235-1237, 1297-1298`
- evidence: "finding you feel surest about: a rule you agree with and do not apply to"
- pattern: Group 1c strategy coaching
- why: Each of three reviewer directives ends with an instruction about where to spend attention. That instruction is the "reading is not applying" line in the reviewer's context. The binding content (name the evidence; leave out what you cannot settle; answer instance or class) stands without it. Opus 5.5 reviews more accurately than prior models, and this nudge targets a failure that may not reproduce on it.
- confidence: medium
- action: remove
- replacement: (delete the final sentence of `RESOLUTION_IS_A_CLAIM_DIRECTIVE`, of `VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE`, and of `FINDING_SCOPE_DIRECTIVE`)
- model_dependent: yes
- machine_read: yes. The constants are pinned by `TestResolutionIsAClaimDirective` (`tests/test_critic_consolidate.py:2114`) and `tests/test_finding_scope_rule.py`; the closers themselves are not asserted.

### A-30: Briefing advisory relay can turn the first reply into a stop
- location: `plugin/lib/briefing.py:646-656`
- evidence: "Relay every advisory above to the user in your first reply"
- pattern: prawduct early-stop invitation; Opus 5.5 ends turns to hand over decisions
- why: A first reply that relays owner decisions and then stops is exactly the "list non-blocking decisions for the user" early stop. The directive never says the user's actual ask proceeds.
- confidence: medium
- action: add
- replacement: append to `ADVISORY_RELAY_TEXT`: " Then carry on with what they asked: an advisory waiting on their decision blocks nothing else."
- model_dependent: no
- machine_read: yes. `tests/test_briefing_functions.py:1467-1470,1500` assert clauses and position; appending keeps both.

### A-31: authoring.md: the claim-verification cluster repeats core.md
- location: `.claude/rules/learnings/authoring.md:13,17,18,19,48,51,52,59,60,66,77,81,83`
- evidence: "A `[DECISION]` block is a CLAIM ABOUT THE CODE nothing checks — re-derive it from the implementation before citing it"
- pattern: Group 1d patch accretion; Opus 5 over-verification; #342 duplicate of core.md
- why: Thirteen rules each patch one kind of record with "re-derive before propagating". The one idea core.md does not already carry (A-8, A-13) is that a record inherits the confidence of its derivation.
- confidence: medium
- action: rewrite
- replacement: delete all thirteen and add: "A claim copied from a record — a [DECISION] block, a plan's VCS state, a quotation, a reflection, an owner-written issue — inherits its derivation, not its author: re-derive it from code, git or the source before propagating it." (228 chars)
- model_dependent: yes
- machine_read: no

### A-32: authoring.md: eight token-budget rules
- location: `.claude/rules/learnings/authoring.md:21,22,37,47,58,75,78,84`
- evidence: "A prose token ceiling breached: pay in place from genuine duplication, or DECLARE a raise with its reason"
- pattern: Group 1d patch accretion; Group 2 recency trap (rule 47's compressibility sample, rule 84's budget-vs-location)
- why: Eight rules govern one act, paying for a size ceiling, and they pull in different directions ("never trim to fit" against "when a trim lands…").
- confidence: medium
- action: rewrite
- replacement: delete the eight and add two rules.
  - "Pay a prose size ceiling in place: cut a class another file owns (dates, tallies, worked examples, duplicated definitions) — never move prose between files or trim the least-defended clause; otherwise declare a raise with its reason."
  - "When a trim lands under a pinned budget, lower its ceiling in the same commit. session-digest.md also has a hard 10,000-character wall (test_plugin_methodology_digest.py) that token budgets do not see."
- model_dependent: no
- machine_read: no

### A-33: tests.md: nine mutation and red-verify rules
- location: `.claude/rules/learnings/tests.md:10,11,15,29,43,47,51,57,58`
- evidence: "A test asserts what would BREAK, not what you just built — red-verify mechanically"
- pattern: Group 1d patch accretion (brief keep #2: mutation-proof binds, so merge, don't drop)
- why: Nine rules restate "see it red against the real defect", each with a different corner case. Rule 14 (restore by inverting your edit, never `git checkout`) is a destructive-operation guard and stays separate.
- confidence: medium
- action: rewrite
- replacement: delete the nine and add two rules.
  - "A test counts once seen red against the defect it pins: reinstate the shipped bug — each conjunct, each defence layer and the call site separately — and watch it fail. Tell: no fixture makes guarded and unguarded code differ."
  - "A mutation sweep where every mutant dies is a claim about the harness: assert each test RAN (return code, not an output substring) and include one mutant you expect to survive."
- model_dependent: no
- machine_read: no

### A-34: tests.md: four assertion-scope rules
- location: `.claude/rules/learnings/tests.md:16,26,28,61`
- evidence: "An assertion against a CONTAINER (whole stdout, row, file) passes on any part"
- pattern: Group 1d patch accretion
- why: All four rules share one fix: bind to the smallest span and add a control.
- confidence: medium
- action: rewrite
- replacement: "Bind an assertion to the smallest span carrying the behaviour and pair it with a control that must differ — substrings, whole stdout and literal spellings pass on any rewording or unrelated match; assert success before absence."
- model_dependent: no
- machine_read: no

### A-35: hook-surface.md: six docstring-claim rules
- location: `.claude/rules/learnings/hook-surface.md:10,16,21,27,37,51`
- evidence: "A docstring stating a guarantee is an ASSERTION, not a verification"
- pattern: Group 1d patch accretion
- why: Six rules cover one idea: a docstring or comment is a claim that must match the code, especially after a reversal or a port.
- confidence: medium
- action: rewrite
- replacement: "A docstring or comment is a claim: before one states reach or a guarantee ('the one reader', 'never raises'), grep the callers or test the path; after a reversal, port or disabled wiring, re-grep your own prose for the old world."
- model_dependent: no
- machine_read: no

### A-36: hook-surface.md: the fail-soft cluster, plus general knowledge
- location: `.claude/rules/learnings/hook-surface.md:15,20,29,31,44,48,62,69,71`
- evidence: "'Advice fails soft' is not 'advice fails silent' — a degraded advisory path must still name its consequence"
- pattern: Group 1d patch accretion; Group 2 "Verbose… things the model already knows"
- why: Six rules (15, 31, 48, 62, 69, 71) each pick a fallback direction for one case. Three others are general engineering the model already knows: amortize a fallback lookup in a loop (20), grep before defining a constant (44), and "governance complexity breeds governance complexity" (29), which restates Principles 25 and 26.
- confidence: medium
- action: rewrite
- replacement: delete rules 15, 20, 29, 31, 44, 48, 62, 69 and 71, and add: "Pick each fallback's direction from the invariant it protects: an unknown bucket blocks, degraded advice names its consequence, and a swallow is fixed in the frame that discards it, not at the symptom."
- model_dependent: yes (for 20, 29 and 44)
- machine_read: no

### A-37: reviews.md: copies of core.md and of NEXT-ACTION
- location: `.claude/rules/learnings/reviews.md:13,20,22,36,43`
- evidence: "After a clean cumulative (0 blocking/0 warning), NOTEs are advisory — don't chase cosmetic ones"
- pattern: #342 duplicates
- why: Rules 20, 36 and 43 restate core's class rule (A-9). Rules 13 and 22 restate what NEXT-ACTION tells the builder at the moment of decision.
- confidence: medium
- action: remove
- replacement: (delete all five)
- model_dependent: no
- machine_read: no
- dup_of: `.claude/rules/learnings/core.md:7,30` (merged in A-9); `plugin/lib/critic_consolidate.py:942-1000`

### A-38: Learnings format: keep one-line + Tell, strip incident specimens
- location: `.claude/rules/learnings/backlog.md:13` (pattern is corpus-wide; other examples at `core.md:8`, `reviews.md:28,42`, `release.md:14`, `authoring.md:78`
- evidence: "nine branches, ~11,000 reviewed lines lost. Tell: you are closing or archiving from a description rather than a diff"
- pattern: Group 2 history narratives; Group 1d recency trap
- why: The format holds up well. A one-line rule plus a Tell is a recognition cue the model cannot derive, which is context rather than cruft. The defect is inside the lines: issue IDs (#644, #767, REL-7D4X, CRT-2J8N), version and date archaeology ("`git_sha` retired as misleading", "since #767"), and specimen parentheticals (`getattr(x, "body", "")`). None of these changes what the rule prescribes. Also drop any Tell that restates the rule instead of naming a state visible at decision time.
- confidence: medium
- action: rewrite
- replacement: approach, applied corpus-wide. Examples:
  - `backlog.md:13` becomes "Archiving an unmerged branch as 'intent captured in the backlog' must verify the IMPLEMENTATION landed, not that an item exists. Tell: you are closing from a description rather than a diff."
  - `reviews.md:42` drops "since #767 it NAMES the changed paths, but".
  - `reviews.md:28` drops "(`git_sha` retired as misleading). What it composes has grown (session timestamp, tree-validity clause, `degraded` flag):".
  - `core.md:8` is already replaced by A-8.
- model_dependent: no
- machine_read: no

### A-39: Digest heading "The hardest rules (these degrade at scale — hold them)"
- location: `plugin/methodology/session-digest.md:18`
- evidence: "## The hardest rules (these degrade at scale — hold them)"
- pattern: Group 1a pressure language
- why: The heading tells the reader to brace. The bullets under it already carry their reasons.
- confidence: medium
- action: rewrite
- replacement: "## Standing rules"
- model_dependent: no
- machine_read: yes. It is a key in `DIGEST_SECTION_PLACEMENT` (`tests/test_plugin_methodology_digest.py:74`), which `test_every_digest_section_carries_a_placement_decision` enforces. Rename the key in the same commit.

### A-40: `_CACHE_WARM_DIRECTIVE`: an elapsed-time progress cadence while reviewers run
- location: `plugin/lib/critic_consolidate.py:280-289`
- evidence: "While waiting, print a one-line progress note (what you are waiting on,"
- pattern: Group 1b/1f fixed interim-update cadence; Opus 5.5 attends to elapsed-time signals in multi-agent setups
- why: A fixed every-4-minutes note about elapsed time, printed next to `_INFLIGHT_GRACE_MINUTES` abandon advice, keeps elapsed time salient. That may push Opus 5.5 toward premature abandonment or busy-waiting. The cache-TTL reason is real, but I cannot tell from here whether the harness wake-on-completion already makes it moot, so this needs a behavioral probe, not an edit.
- confidence: low
- action: flag
- replacement: none
- model_dependent: yes
- machine_read: yes (`tests/test_critic_consolidate.py:1686,1700,1747`; `tests/test_v5_methodology.py`)

### A-41: Digest Critic bullet: the manual `critic-consolidate` step
- location: `plugin/methodology/session-digest.md:38-40`
- evidence: "critic-consolidate` before reading the findings (safe to re-run; never read a stale file)."
- pattern: possible #342 duplicate or unenforced-instruction fossil
- why: `skills/critic/SKILL.md:71` says the `SubagentStop` hook consolidates each reviewer as it finishes, with the session-end backstop behind it. The builder-side manual step may now be redundant on the always-on surface. I have not verified whether the builder can still meet a stale findings file before the last `SubagentStop` fires.
- confidence: low
- action: flag
- replacement: none
- model_dependent: no
- machine_read: no

### A-42: reviews.md loads on skill edits, not on running a review
- location: `.claude/rules/learnings/reviews.md:1-8`
- evidence: "Rules that fire while running or acting on a Critic review."
- pattern: Group 1d unenforced instruction (a delivery mismatch)
- why: `paths:` is `plugin/skills/critic/**` and `plugin/agents/**`, so the harness loads these rules when those files are read. Invoking `/prawduct:critic` or acting on `.critic-findings.json` may never read them, so the rules may not be in context at the moment the header says they fire. Confirm how the harness treats skill invocation before changing anything.
- confidence: low
- action: flag
- replacement: none
- model_dependent: no
- machine_read: yes (`paths:` frontmatter is parsed by the harness and by `lib/learnings_files`)

## Outside my slice
- `plugin/methodology/session-hygiene.md:52` puts a hard stop at "a chunk boundary whose review has not run"; check that it reads as "dispatch the review", not "end the turn", once A-1 lands.
