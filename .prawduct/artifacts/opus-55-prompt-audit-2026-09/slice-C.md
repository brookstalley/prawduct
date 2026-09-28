# Slice C: review machinery prompts (`plugin/skills/critic/*.md`, `plugin/skills/pr/*.md`, `plugin/agents/critic-reviewer.md`, `plugin/agents/pr-reviewer.md`)

## Inventory

I read all nine files in full. Word counts are from `wc -w`.

| File | Words | Who loads it |
|---|---|---|
| `plugin/skills/critic/SKILL.md` | 2,862 | the Critic fork, every mode (the single-pass reviewer, or the coordinator) |
| `plugin/skills/critic/review-cycle.md` | 8,744 | every `final`/`cumulative` single-pass reviewer, and each dispatched reviewer (x3 on a coordinator roster; `tests/test_reviewer_payload_budget.py` `PAYLOAD_ROUTES`); the builder reaches it through pointers in `building.md` |
| `plugin/skills/critic/review-protocol.md` | 3,394 | `final`/`cumulative` single-pass reviewer, the coordinator, and each dispatched reviewer |
| `plugin/skills/critic/goals-1-3.md` | 2,053 | `chunk` / `verify-resolutions` reviewer (the most frequent review) |
| `plugin/skills/critic/framework-checks.md` | 859 | `final`/`cumulative` reviewers |
| `plugin/skills/pr/SKILL.md` | 8,902 | the main (builder) session, on every `/prawduct:pr` invocation. The PR reviewer does **not** load it |
| `plugin/skills/pr/review-protocol.md` | 4,337 | the PR reviewer |
| `plugin/agents/critic-reviewer.md` | 2,220 | the system prompt of each dispatched Critic reviewer |
| `plugin/agents/pr-reviewer.md` | 1,102 | the system prompt of the PR reviewer |

The brief's framing needs one correction. `pr/SKILL.md` is not a per-reviewer cost: the builder pays it once for each `/pr` run. `review-cycle.md` is a per-reviewer cost, and it is the biggest one in this slice. The route sum records a dispatched reviewer's payload at 19,781 tokens, and about 11.4k of that is `review-cycle.md`.

## Summary

The highest-impact decision is **C-8**. `review-cycle.md` is ~8.7k words. About 6.2k of those words are builder and maintainer lifecycle material: dispositions, the census, filing rules, the round budget, which writes are free, the ledger, and the manifest schema. Every `final`/`cumulative` reviewer loads all of it, three times per coordinator review. The repo's own test calls it "the 10k-token maintainer file". Moving the reviewer-facing ~2.5k words into their own routed file saves about 8k tokens per reviewer, or about 24k per coordinator review.

The recall check is mixed. The Critic prompts are clean on the documented pattern. `review-protocol.md` and `goals-1-3.md` both say "RATE it regardless … Never omit or downgrade", and the inner-stage demotion is a reported channel: `observations` reach the builder and the review fact, and nothing is dropped. The PR reviewer prompt is not clean: "file what a maintainer would genuinely want changed", "Only flag if splitting is cheap" and "cheap to act on" are severity/value filters placed ahead of reporting (**C-1**). `critic-reviewer.md`'s "do not invent findings" is a minor recall-negative anchor (**C-22**). The Records Pass drops sub-bar record defects at the boundary with no channel (**C-26**, flag).

The other large wins:
- **C-4**: remove duplicated facts inside a single reviewer context. "Pass the directory" appears three times in the PR reviewer's own payload.
- **C-5**: delete maintainer and caller text that ships in the PR reviewer's payload ("Extending This Skill", a stale relationship table, "You may be skipped").
- **C-6**, **C-13**, **C-14**, **C-16**: cut migration-relative phrasing and decision-record archaeology in `pr/SKILL.md` (about 1,500 words the builder carries on every `/pr`).

Counts: 29 decisions.

| Action | Count |
|---|---|
| remove | 3 |
| rewrite | 19 |
| move | 2 |
| add | 1 |
| flag | 4 |

Of these, 7 are high confidence, 17 medium and 5 low.

Most of this prose is pinned by tests. Every decision marked `machine_read: yes` names the pinning test, so the integrator can edit test and prose together. The budgeted files are `critic/SKILL.md` (<3721), `critic/review-protocol.md` (<4413), `goals-1-3.md` (<2669), `review-cycle.md` (<11368) and `framework-checks.md` (<1150), all in `tests/test_v5_methodology.py`, plus the three route sums in `tests/test_reviewer_payload_budget.py`. Every trim below lowers one of these ceilings.

## Decisions

### C-1: PR reviewer's value filters sit ahead of reporting and depress recall
- location: `plugin/skills/pr/review-protocol.md:7-27`, plus `:96` and `:134`
- evidence: "would genuinely want changed before merge, and say plainly when a finding is worth accepting rather"
- pattern: guide-opus5 "Severity filters still depress measured recall" (report everything with severity, filter downstream); Group 1c strategy coaching
- why: Opus 5+ follows "only file what's worth it" filters literally. Here a reviewer is told to price each finding against the round it costs, to file only what a maintainer "would genuinely want", and (`:96`, `:134`) to flag oversize or simplification only when it is cheap. Disposition already has a downstream filter: the builder's ACCEPT default and `prawduct-hook disposition`. Paragraph 3 (ride along, "Say where it should be written down (the build plan, or the backlog)") is disposition coaching, and it contradicts the Critic-side rule that reviewers never name the backlog as a destination.
- confidence: high
- action: rewrite
- replacement: Replace lines 7-27 with:
  > **Report every release-readiness defect you find, each at its severity. Never drop one because acting on it costs the builder a review round.** Disposition is the builder's call, made downstream with the whole bundle in view. Accepting is a real answer and costs nothing, and some paths move no coverage (`prawduct-hook cost-of-commit <paths>` answers that for a specific batch). When a finding is worth accepting rather than fixing, say so in it. Group observations that share one fix into one finding, so they land in one commit.

  Replace `:96` with:
  > - If oversized: say whether it is practically splittable and what splitting would cost. The work is done, so the builder weighs that.

  Replace `:134` with:
  > **Scope boundary:** flag bundle-level **simplifications** visible only across the full changeset, and say what each would cost to act on. Per-chunk simplification, deduplication, and "you should have used a different pattern" alternatives were the Critic's job during building. Do not re-open them.
- model_dependent: no
- machine_read: yes. `tests/test_pr_reviewer.py:494-544` pins "costs the builder a review round" (the replacement keeps it, and keeps its position above `## Review Goals`), "accepting is a real answer", "some paths move no coverage" and "prawduct-hook cost-of-commit" (all kept). It also pins "ride along with the next chunk or the next build plan", "not always right" and "quietly become a drop", which are deleted, so those three assertions need to come out.

### C-2: Fixed progress-note cadence for the builder, inside the reviewer payload
- location: `plugin/skills/critic/review-cycle.md:108`
- evidence: "emit a one-line progress note at least every 4 minutes rather than going quiet"
- pattern: Group 1f output-shaping choreography (fixed interim-update cadence); Group 1d update cadence
- why: A fixed cadence is the pattern the guide says to remove whole. Opus 5.5 paces and narrates by itself, and its between-tool text arrives in thinking blocks. The paragraph is also builder-facing, so every `final`/`cumulative` reviewer carries it for nothing (see C-8).
- confidence: high
- action: rewrite
- replacement: Replace the last sentence ("If the prep runs out before the review does, emit a one-line progress note at least every 4 minutes rather than going quiet.") with:
  > If the prep runs out before the review lands, tell the user what you are waiting on.
- model_dependent: no
- machine_read: no

### C-3: Dead output format that no reader of this file uses
- location: `plugin/skills/critic/review-cycle.md:515-535`
- evidence: "[Total findings by severity. Whether the chunk passes review.]"
- pattern: Group 1c example over-indexing (stale format block); prawduct Size
- why: This is the chunk-mode report format, but chunk mode reads only `goals-1-3.md`. That file says "do not open … `review-cycle.md`" and carries its own report instructions at `:155-158`. The `final`/`cumulative` readers of this file have their own format in `review-protocol.md:157-180`. So a reader of this block is shown a second, conflicting report shape (it has no `Scope:` line) that belongs to no mode it runs.
- confidence: high
- action: remove
- replacement: (delete the whole `## Per-Chunk Output Format` section)
- model_dependent: no
- machine_read: no. No test names the heading. The `review-cycle.md` ceiling at `tests/test_v5_methodology.py:875` should drop.

### C-4: The PR reviewer's payload restates its own contract two or three times
- location: `plugin/agents/pr-reviewer.md:29-34`, `:46-51`, `:60-64`; `plugin/skills/pr/review-protocol.md:33-37`, `:123`
- evidence: "**pass the directory.** You have no `cd`, and"
- pattern: prawduct duplicated facts (#342); Group 1c padding ("duplicated rules make the model spend effort reconciling wordings")
- why: The PR reviewer loads both files. "Pass the project dir to `pr-review-payload`, because you have no `cd` and it resolves the launch directory; then compare `base`'s project dir and HEAD with your prompt; branch names cannot catch this" is stated three times, in near-identical wording. The rule for resolving ids the payload could not see is stated twice (agent `:60-64`, protocol `:123`). These are copies within one context, not working redundancy across readers.
- confidence: high
- action: rewrite
- replacement: Keep the protocol's statements (`review-protocol.md:33-37` and `:123`) as the home.
  - In `pr-reviewer.md`, replace the third bullet of "The project directory is not necessarily your cwd" (`:29-34`) with:
    > - Run `prawduct-hook pr-review-payload <project dir>` as `review-protocol.md` step 1 says. If either the project dir or the HEAD it reports disagrees with your prompt, say so in your summary rather than picking one.
  - Replace the tools bullet at `:46-51` with:
    > - `prawduct-hook pr-review-payload <project dir>`: your first read (protocol step 1).
  - Replace `:60-64` with:
    > - `prawduct-hook backlog cache-query`: for ids inside a diff hunk, which the payload does not scan (protocol R-1).
- model_dependent: no
- machine_read: yes. `tests/test_pr_reviewer_agent.py:361` pins "If either disagrees" in the agent body. The first replacement keeps it.
- dup_of: `plugin/skills/pr/review-protocol.md:33-37`, `:123`

### C-5: Maintainer-facing and caller-facing text ships in the PR reviewer's payload
- location: `plugin/skills/pr/review-protocol.md:67`, `:205`, `:211`, `:213-222`, `:224-226`; `plugin/skills/pr/SKILL.md:188`, `:190`
- evidence: "Prefer strengthening existing goals over adding new ones. The 4 goals cover release readiness comprehensively"
- pattern: Group 2 verbose SKILL.md; Group 1c padding (scope boundary restated); Group 1d fossils (the table's "Separate agent (Task tool)")
- why: "Extending This Skill" addresses whoever maintains the skill. The Critic moved its own copy out of `review-protocol.md` for exactly this reason (`review-cycle.md:567`). `:67` ("You may be skipped …") describes a caller-side decision the reviewer cannot observe. `:211`'s rules about what the *caller* may edit bind the caller, not the reviewer. The "Relationship to the Critic" table is the fifth statement of the scope boundary (after `:5`, `:205`, `:220` and `:226`), and it carries stale cells ("Task tool", "BLOCKING (stop hook)" for chunk/final).
- confidence: high
- action: remove
- replacement:
  - Delete `:67` (the "You may be skipped" paragraph) and the `## Relationship to the Critic` and `## Extending This Skill` sections.
  - At `:205`, cut the clause after "release-readiness scope", leaving:
    > `mode`: always `"pr"` (release-readiness scope).
  - At `:211`, keep:
    > **Never rewrite `commit_reviewed`**: it records the tree you read.

    and delete the rest of the paragraph (the caller-binding sentences belong to `pr/SKILL.md`, which already states them at Step 4 and the Update Flow).
  - In `pr/SKILL.md`, reduce `:188` to:
    > **Say which of the two it is**: running beside you, or already passed.

    and delete `:190` ("The reviewer's own instructions reinforce this …").
- model_dependent: no
- machine_read: yes. `tests/test_pr_reviewer.py:901-904` pins the scope phrases at `:5` (kept). `:914` names the Relationship table and "Extending This Skill" only in a comment, and `test_v5_methodology.py:4787` and `:5558` mention "Extending This Skill" only in comments. `tests/test_pr_reviewer.py:1048` pins "running beside you, or has already passed" in the Step 3 dispatch prompt, which is untouched.

### C-6: Migration-relative phrasing in `pr/SKILL.md`, one instance inside the reviewer's dispatch prompt
- location: `plugin/skills/pr/SKILL.md:74`, `:88`, `:165`, `:186`, `:217`, `:251`
- evidence: "Prawduct no longer selects a reviewer model from the diff's risk tier"
- pattern: Group 1d migration-relative phrasing; Group 2 history narratives
- why: Each sentence is a diff against a prior version that the reader never saw. It implies alternatives that do not exist, and it costs tokens on every `/pr`. `:186` sits inside the verbatim prompt sent to the reviewer ("everything else your activation section used to assemble by hand").
- confidence: high
- action: rewrite
- replacement: Worked edits:
  - (a) `:165`: delete the sentence "Prawduct no longer selects a reviewer model from the diff's risk tier; the reviewer inherits whatever model the session is on, and intelligent model switching has been removed." Keep "Record which model actually ran."
  - (b) `:74`: delete from "The two gates at this boundary once classified with different rules" to the end of the blockquote.
  - (c) `:88`: delete the whole paragraph beginning "**What the two bullets above give you is the action; the rule they follow is owned by**". Replace it with:
    > The rule and its reason live in `/prawduct:backlog`'s "When to mark shipped".
  - (d) `:186`, in the dispatch prompt: "Start with `prawduct-hook pr-review-payload`, which carries the base and everything else your activation section used to assemble by hand." becomes:
    > Start with `prawduct-hook pr-review-payload <project dir>`.
  - (e) `:217`: delete "(content equivalence was built as an exception and reverted — `coverage_algebra.is_judgeable_path`)".
  - (f) `:251`: delete the parenthetical "(Archiving early is not the deletion it used to be — …)".
  - (g) `:86`: delete "(#550/#564)".
- model_dependent: no
- machine_read: yes, for (d) only: `tests/test_pr_reviewer_agent.py:410-411` pins "(absolute)" and "never your cwd" in Step 3, and the edit keeps both. The rest are unpinned.

### C-7: Incident archaeology inside `review-cycle.md` instructions
- location: `plugin/skills/critic/review-cycle.md:14`, `:141`, `:171-173`, `:184-187`, `:202-210`, `:227-229`, `:260-276`, `:296-297`, `:302-308`, `:471-474`
- evidence: "in a file this mode's reviewer is forbidden to open). An earlier draft claimed all five"
- pattern: prawduct incident archaeology; Group 2 history narratives and recency trap; Group 1d migration-relative
- why: A rule's authority is the behaviour it prescribes. Issue numbers, dates, "an earlier draft said", "the old rule said" and tallies of past incidents make the reader navigate history, and the reviewer payload currently carries all of it (C-8). I kept every sentence that states *why* the rule holds, and I left alone the measured figures tests deliberately pin as reasons: "23%" and "13.5"/"18.4".
- confidence: high
- action: rewrite
- replacement: Worked edits (apply the same approach to any sibling found by grepping `#[0-9]\{3\}`, `20[0-9][0-9]-`, `earlier draft`, `used to` and `now do`):
  - (a) `:141`: delete "(The workaround case was rated **WARNING** here until the narrowing below; … the finding is unresolved.)"
  - (b) `:171-173`: "(Owner-requested rule, 2026-07-29; bounded to blocking severity 2026-09-19 at the owner's direction, #833. Below BLOCKING …)" becomes:
    > Below BLOCKING, the same deep context argues for a recorded ACCEPT, which costs no round, rather than a fix that buys one.
  - (c) `:202-210`: replace the paragraph with:
    > The directive names the shapes a fix delta gets wrong (a weakened or deleted test, a dropped requirement, changed behavior with no test, exploitable security in changed code including missing auth/authz and known-vulnerable dependencies, and fix-by-fudging) and rates each BLOCKING, including the two `goals-1-3.md` prints lower.
  - (d) `:227-229`: "ACCEPT, FILE, and the FIX that bought *no* round now do too:" becomes:
    > ACCEPT, FILE, and a FIX that bought no round record theirs with:
  - (e) `:260-276`: replace "**Why this stopped being prose.**" and "**Why the default moved.**" with:
    > Hand-written censuses drift, and correcting one is a commit that buys a review round, so counting is the machine's job and deciding is yours. FILE is the narrowest disposition because a backlog that receives every non-blocking finding stops being a work queue.
  - (f) `:296-297`: delete "The severity contract (`review-protocol.md`) no longer says "recommend backlog" anywhere, and reviewers must not reintroduce it in prose."
  - (g) `:302-308`: delete "Observed live: **four rounds and ~40 minutes of review on a ~40-line code change** — every finding correct, none blocking, and the last round required by no gate at all."
  - (h) `:471-474`: delete ", and habituation to that silence is what BLD-5J8N cost".
  - (i) `:14`: delete "(#292)".
  - (j) `:184-187`: delete from "The rule is delivered where the reviewer meets it" to "carries the worked instances."
- model_dependent: no
- machine_read: yes, partly. `tests/test_v5_methodology.py:5824-5828` pins "no natural fixed point", "13.5" and "18.4" (`:345`, untouched). `:6424` pins "23%" in the Records Pass (untouched). `VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE` and `fix-by-fudging` are named by tests, and (c) and (j) keep "fix-by-fudging". `test_the_builder_facing_severity_rule_points_at_the_pass` needs "Records Pass** below" in the builder half, which is kept (`:343`).

### C-8: Split `review-cycle.md`: every `final`/`cumulative` reviewer loads ~6k words of builder and maintainer lifecycle
- location: `plugin/skills/critic/review-cycle.md:1-60`, `:91-358`, `:537-568` (builder/maintainer material) against `:76-89` and `:359-513` (reviewer material); routed by `plugin/skills/critic/SKILL.md:24`
- evidence: "**Once a pass returns zero BLOCKING, the review is over.** That is the exit condition, not a judgment"
- pattern: prawduct Size and pattern #342; Group 2 "Verbose SKILL.md … a tax paid on every trigger"; brief's "how much protocol the coordinator and builder are asked to carry"
- why: `tests/test_reviewer_payload_budget.py` prices this file into both `single-pass-full` and `dispatched-reviewer`, and a coordinator roster pays it three times. `tests/test_v5_methodology.py:6162` already describes it as "the 10k-token maintainer file" that a reviewer should not need.

  | Part of the file | Words | Who uses it |
  |---|---|---|
  | Type selector (`:76-89`) | ~330 | reviewers |
  | Final-Mode Cross-Checks through Governing-Artifact Reconciliation (`:359-513`) | ~2,180 | reviewers |
  | Mode selection, the evidence model, verify anchoring, the per-chunk cycle, dispositions/FILE/census, free writes, round budget, manifest/ledger schema, "Extending This Skill" | ~6,200 | the builder, the operator or a maintainer; no reviewer acts on these |

  The Stage section is not needed by reviewers either: `review-protocol.md:32` and `critic-reviewer.md:35-40` carry it by design. This is a move for audience, not for budget. The builder-side pointers (`building.md`, `planning.md`, `gates.py` strings, `runbook/SKILL.md`) all name builder sections, and those stay put.
- confidence: medium
- action: move
- replacement: Create `plugin/skills/critic/cross-checks.md` holding `review-cycle.md:76-89` (Per-Chunk Type Protocol Selector) and `:359-513` (Final-Mode Cross-Checks, Learnings Cross-Check, Backlog Reconciliation, Records Pass, Record-Lint, Governing-Artifact Reconciliation). Also move the reviewer-addressed paragraph at `:296-300` ("Reviewers: never name the backlog as a finding's destination …") there, trimmed per C-7(f).

  Then change the routing and pointers:
  - `SKILL.md:24` routes `${CLAUDE_SKILL_DIR}/cross-checks.md` for `final`/`cumulative` in place of `review-cycle.md`.
  - `review-protocol.md:22, 30, 67, 119, 125` and `critic-reviewer.md:64, 128` repoint their bare-name citations to `cross-checks.md`.
  - `pr/review-protocol.md:138` and `skills/backlog/cache-reads.md:4` repoint as well.
  - `review-cycle.md` keeps a one-line pointer where each moved section was.
  - `planning.md:187` and `templates/build-plan.md:183` repoint the Type table.

  Net: `dispatched-reviewer` drops by about 8k tokens per reviewer (about 24k per coordinator review), and `single-pass-full` by about 8k.
- model_dependent: no
- machine_read: yes. The tests to move with it:
  - `tests/test_reviewer_payload_budget.py` `PAYLOAD_ROUTES` and the route sums
  - `tests/test_v5_methodology.py:6362-6436` (Records Pass ownership, "three additional passes", "23%"; these re-point to `cross-checks.md`) and the per-file ceilings at `:875` and `:5741`, plus a new ceiling for `cross-checks.md`
  - `tests/test_control_yield_tokens.py:269-284` (the single-pass rule-unenforced pointer moves with the Learnings Cross-Check)
  - `tests/preferences/test_critic_skill_structure.py:459` (the record-lint table)

  `tests/test_finding_scope_rule.py` parses the Per-Mode Behavior table, which stays in `review-cycle.md`.

### C-9: `critic-reviewer.md` restates `review-protocol.md` inside the same dispatched context
- location: `plugin/agents/critic-reviewer.md:35-40`, `:115-121`, `:126-132`
- evidence: "Three passes own oracle findings and are not narrowed"
- pattern: prawduct duplicated facts (#342); Group 1c padding
- why: A dispatched reviewer loads both this agent definition and `review-protocol.md` (the coordinator template says "read [critic path] for goal definitions", and step 3 sends it there). The Stage rule (`review-protocol.md:32`), the "finding's subject is never another finding" rule (`:126`), and the subject/oracle carve-out (`:30`) are therefore each read twice, in different wordings, with meta-commentary such as "This is here because it binds every reviewer and because YOU are the only one …". The pinning test's premise, that "a dispatched coordinator reviewer reads its agent definition" instead of the protocol, is only half true: it reads both.
- confidence: medium
- action: rewrite
- replacement:
  - `:35-40`, from "**`Stage` decides what is a finding**" to "consolidation refuses the array." becomes:
    > **`Stage` decides what is a finding** (`review-protocol.md` "Stage"): at `inner`, what you rate outside the inner BLOCKING set goes in your partial's `observations` array.
  - Step 5 (`:115-121`) becomes:
    > 5. **A finding's subject is never another finding.** One that restates your own finding, names its consequence, or cross-checks it against learnings folds into it (`review-protocol.md`, Severity Levels).
  - Step 6's bold block (`:126-132`) becomes:
    > The manifest's `files_reviewed` is your subject set and `files_oracle` is what the code is judged against; `review-protocol.md` "Subject and oracle" says which passes may rate an oracle file. *"The code violates this spec"* has the code as its subject, at full severity.
- model_dependent: no
- machine_read: yes. `tests/test_v5_methodology.py:6252-6256` pins "Stage: <inner|boundary>", "`Stage` decides what is a finding" and `"observations"` (all kept). `:6286-6296` pins `files_reviewed`/`files_oracle` (kept). `:6352` pins "violates this spec" (kept). `tests/preferences/test_critic_skill_structure.py:340-380` pins "subject is never another finding", "consequence", "learnings" and "your own" (all kept).
- dup_of: `plugin/skills/critic/review-protocol.md:30`, `:32`, `:126`

### C-10: Tool-boundary provenance and maintainer rationale in both reviewer agent definitions
- location: `plugin/agents/critic-reviewer.md:12-23`; `plugin/agents/pr-reviewer.md:38-43`, `:53-57`
- evidence: "(measured against Claude Code 2.1.277). Whether the `Bash(...)` patterns narrow"
- pattern: Group 2 history narratives and volatile specifics (a pinned harness version, backlog id CRT-3X9D); Group 1c padding
- why: The reviewer needs three things: what its tools are for, that it cannot run tests or builds, and which files it may write. How the harness enforces `tools:`, which Claude Code version was measured, and why a prefix grant would expose a sibling op are facts for whoever edits the frontmatter. The tests already hold them (`test_critic_reviewer_agent.py:147`, `test_pr_reviewer_agent.py:117`).
- confidence: medium
- action: rewrite
- replacement:
  - In `critic-reviewer.md`, replace `:12-23` (from "Your restricted tools are the no-execution boundary" through "Review through code analysis only; the builder ran the tests before requesting review.") with:
    > Your tools are read-only: you can read files, search code, inspect git read-only, and run four read-only `prawduct-hook` probes. Those are `backlog cache-query` and `learnings-files --for-diff` (for the `sustainability` role's reconciliation and Learnings Cross-Check), and `test-status` and `verify-coverage` (Goal 1, which read recorded evidence rather than produce it). Nothing here can run a test, a build, or the product's own code, or mutate the session you are reviewing. Review through code analysis only; the builder ran the tests before requesting review.
  - In `pr-reviewer.md`, replace `:38-43` with:
    > **You cannot run tests, builds, or any of the product's own code, and you cannot mutate the session you are reviewing.** Stay inside the commands listed below.
  - Replace `:55-57` with:
    > - Never run `pr-review-dispatch`: it is a writer, and your grant names only `pr-review-payload`.
- model_dependent: no
- machine_read: yes. `tests/test_pr_reviewer_agent.py:318` pins "not path-scoped" (at `:67`, untouched). `tests/test_critic_reviewer_agent.py:236-240` pins "critic-findings.json", "critic-consolidate", "critic-end" and "do NOT" (all at `:142-144`, untouched). Neither pins the provenance text.

### C-11: `pr-reviewer.md` repeats the protocol's learnings rationale, with archaeology
- location: `plugin/agents/pr-reviewer.md:76-87`
- evidence: "matches a file you Read, arrives as a system message after that Read (measured 2026-09-22,"
- pattern: prawduct duplicated facts (#342); incident archaeology (date, #888)
- why: The same reader loads `review-protocol.md:138-140`, which carries the same argument (Critic owns the scan, "1 finding in 122 reviews", recognising a pattern is still a WARNING). The agent copy adds a date and an issue number. The protocol's copy is test-pinned, so it is the home.
- confidence: medium
- action: rewrite
- replacement: Replace `:76-87` with:
  > One kind of rules file still reaches you: a **path-scoped** one, whose `paths:` frontmatter matches a file you Read, arrives as a system message after that Read. Treat it as you would the learnings you were not given: it is not a checklist to scan the diff against (`review-protocol.md`, Learnings Cross-Check).
- model_dependent: no
- machine_read: yes. `tests/test_pr_reviewer_agent.py:169-171` pins "its always-loaded `.claude/rules/` project rules" (at `:72`, kept), "One kind of rules file still reaches you: a **path-scoped** one" and "it is not a checklist to scan the diff against" (both kept).
- dup_of: `plugin/skills/pr/review-protocol.md:138-140`

### C-12: Measurement archaeology in the PR reviewer's goals
- location: `plugin/skills/pr/review-protocol.md:80-89`, `:120`, `:126`, `:149-156`
- evidence: "Measured over **this framework repo's own 279 findings** — a repo whose product *is* governance, so"
- pattern: Group 2 history narratives; Group 1c padding (a self-caveating statistic whose only instruction is "don't deprioritise"); Group 1d fossil (the retired-field story)
- why: `:80-89` spends about 150 words on a finding mix from another repo, then tells the reviewer to ignore it. The only live instruction is the last sentence. `:126` repeats "0.7% … in this framework repo's corpus". `:120`'s TST-4K2P story explains a retired field (see also C-21). `:149-156` cites an NFR clause and a removed check (`dangling-ref`) as provenance.
- confidence: medium
- action: rewrite
- replacement:
  - Replace `:80-89` with:
    > Rarity in one repo is not rarity in yours: a secret, debug code or a stray file is a release blocker at any frequency, so the classic merge-hygiene bullets stay.
  - At `:126`, delete "0.7% of findings *in this framework repo's corpus*, a share a product diff has no reason to share, and kept because rarity is not deadness and one of these is a release blocker:", so the bullet opens "**Classic merge hygiene**: debug code and …".
  - At `:149-151`, delete "This is the cheapest thing you can do about run-count (`nonfunctional-requirements.md` § Direction: review cost is unit-cost × run-count, and *both* are levers): a class re-filed per instance buys a round every branch, forever." Replace it with:
    > A class re-filed per instance buys a round on every branch.
  - At `:154-155`, delete "(a written rule, and no check since `dangling-ref` was measured and removed)".
- model_dependent: no
- machine_read: no. "0.7%" and "279" appear only in a docstring (`tests/test_pr_reviewer.py:440-449`), not in an assertion.

### C-13: Step 2's concurrency rule is buried in justification
- location: `plugin/skills/pr/SKILL.md:98-128`
- evidence: "composed here is not Step 3's, so the agent runs against a different contract than the one this"
- pattern: Group 2 verbose SKILL.md; Group 1c padding; prawduct Size
- why: The instruction is: dispatch the PR reviewer in the same message as the cumulative, using Step 3's preparation, and do not dispatch again. It is surrounded by about 350 words defending why it is safe ("Two things go wrong if you improvise", "stated rather than implied", "The trade this parallelism accepts"). The builder carries all of it on every `/pr`. The reasons can be kept in one sentence each.
- confidence: medium
- action: rewrite
- replacement: Replace `:98-128` with:
  > **The gate check itself is seconds and comes first; it says whether a cumulative review is owed. When it sends you to `/prawduct:critic cumulative`, dispatch the PR reviewer in the SAME message**, doing Step 3's preparation here in its order: compute the evidence path, create `.prawduct/.pr-reviews/`, run `prawduct-hook pr-review-dispatch --begin`, then spawn the agent with Step 3's verbatim prompt. An improvised prompt runs a contract nobody tested, and a skipped mark loses the measured duration. Having dispatched here, do NOT dispatch again at Step 3. Step 2b may STOP between the two steps with the reviewer already in flight.
  >
  > There is no data dependency in either direction. The PR reviewer is scoped off code soundness because the Critic owns that layer, whether or not it has reported, and both read the same tree. Running them together makes the boundary cost the longer of the two rather than their sum (`nonfunctional-requirements.md` § Performance). The one cost: a cumulative that returns `blocking` moves the tree when you fix it, and Step 4's delta check then sends you back to Step 3. Keep that check even when the ancestor test passes, because it is the only thing that sees this case. When the gate is already satisfied there is nothing to run beside, and Step 3 dispatches as usual.
  >
  > **Reconcile at Step 4**: this gate satisfied, and the evidence file's `commit_reviewed` still an ancestor of HEAD.
- model_dependent: no
- machine_read: yes. `tests/test_pr_reviewer.py:693`, `:965`, `:1016`, `:1020` and `:1025` pin "Step 4's delta check", "do NOT dispatch again at", "dispatch the PR reviewer in the SAME message", "pr-review-dispatch --begin" and "There is no data dependency in either direction". All are kept.

### C-14: Step 2's sequencing paragraph re-derives the verify anchoring rule
- location: `plugin/skills/pr/SKILL.md:132`
- evidence: "Do not predict which case you are in: dispatch is seconds and its own answer is authoritative"
- pattern: prawduct duplicated facts (#342); Group 1c padding ("the round this sentence exists to save")
- why: This single paragraph (~450 words) restates the verify-resolutions anchoring derivation, which it then cites as living in `review-cycle.md` § Verify-resolutions anchoring. It also restates the batch-fix order that `building.md:107` and the consolidate-printed `_BATCH_FIX_DIRECTIVE` already carry. The builder needs the action sequence and the one decision point (read the block).
- confidence: medium
- action: rewrite
- replacement: Replace `:132` with:
  > **Sequencing (run the full review ONCE):** land every **judgeable** fix before the one cumulative run, then commit verbatim so the reviewed tree is HEAD's tree. Judgeable fixes are code, evidence, pointers, configs, and governance-protected prose (`skills/`, `methodology/`, `templates/`, root `CLAUDE.md`). For any fix after the cumulative, its own findings included, fix in the working tree, run `/prawduct:critic verify-resolutions`, and read its block rather than predicting its case:
  > - If it graded your working tree, commit it whole and HEAD stays covered.
  > - The pass anchors on committed HEAD instead when you have committed content the prior review never saw. Committing the reviewed tree verbatim does not move it. In that case it refuses (exit 3) and names your uncommitted judgeable files as NOT REVIEWED: commit them, then run the pass over the delta that appears.
  > - An exit 3 that names nothing means no review was needed (a fix confined to `.prawduct/` or non-governance prose costs nothing). Do not re-run it in another mode.
  >
  > Re-run a full cumulative only when the verify pass itself refuses (widened delta, lost anchor), or after a rebase or amend, which rewrites the tree. Derivation: `review-cycle.md` § Verify-resolutions anchoring and demotion.
- model_dependent: no
- machine_read: yes. `tests/preferences/test_free_interval_prose.py:47-50` and `:139-150` require "exit 3" and "content the prior review never saw" in this file. Both are kept.
- dup_of: `plugin/skills/critic/review-cycle.md:116`, `:320-326`; `plugin/methodology/building.md:107`

### C-15: The release-promotion guard carries its own history
- location: `plugin/skills/pr/SKILL.md:40`
- evidence: "**Why derived and not a list.** `develop`/`main`/`master` was the whole test"
- pattern: Group 2 history narratives; Group 1d migration-relative
- why: The first ~120 words narrate the list-based guard this one replaced, and the `resolve-base` internals (`#254`). The live content is: the residual gap (record `base_branch:`); STOP and hand back to the release process; exit 1 from `check-cumulative-critic` is expected here, and is not a waiver case.
- confidence: medium
- action: rewrite
- replacement: Replace `:40` with:
  > One residual gap: a repo whose `origin/HEAD` is `main` but which integrates on `develop` cannot be inferred. If you are plainly on an integration base and the guard did not fire, record `base_branch:` in `project-state.yaml` and say so. A release is the project's own **manual** process (its release runbook plus a version bump); each feature's cumulative review and release-readiness review already ran on its feature PR. **STOP and hand back to the user's own release process; do not run the Create/Update gates.** A `check-cumulative-critic` exit 1 here is expected and benign (release prep touches non-`.md` version files), so it is **not** a gate to satisfy and **not** a `.gates-waived` case.
- model_dependent: no
- machine_read: yes. `tests/test_pr_reviewer.py:745-765` pins, in this file, "Release-promotion guard" (at `:33`), "release process" (kept in the replacement) and "release/integration context" (at `:38`, untouched). The "benign", ".gates-waived" and "not the release vehicle" pins at `:813-820` read `documentation/release-process.md`, not this file.

### C-16: Decision records and maintainer defences inside builder steps
- location: `plugin/skills/pr/SKILL.md:63-69`, `:167`, `:228`, `:233`, `:235-245`, `:266`
- evidence: "**Why a named agent rather than a generic one.** The agent definition is what holds two things"
- pattern: Group 2 history narratives and verbose SKILL.md; prawduct incident archaeology (2026-09-22 #888, owner 2026-08-02, #712)
- why: These paragraphs defend a design choice against a future editor. Examples: "dropping it as duplication reintroduces exactly the failure", "this is the recorded decision (owner, 2026-08-02)", "Deliberately not restated here: three copies of a procedure is how two of them go stale". Others record facts the builder does not act on (what `omitClaudeMd` excludes, `evidence.KNOWN_KINDS`). The builder executing `/pr` needs the action.
- confidence: medium
- action: rewrite
- replacement:
  - (a) Delete `:167` entirely. The agent definition is the home for what it excludes (see C-11), and Step 3 already says the reviewer runs as a named agent.
  - (b) Replace the `:63-69` blockquote with:
    > A `Type: trivial` chunk does not waive the cumulative-Critic or PR-reviewer gates here: fileset bounds are necessary, not sufficient, for triviality, so code PRs always take the full review below.
  - (c) At `:228`, delete from "**It is deliberately OUTSIDE the step whose skip causes the defect:**" to "reintroduces exactly the failure." Keep the "**Neither check subsumes the other …**" sentence.
  - (d) Replace `:233` with:
    > **This step is its own only detector:** if you merge through the GitHub UI or the session ends at the merge, nothing notices that the close never fired. Run it before ending the session.
  - (e) Replace `:235-245` with:
    > 8. Delete the evidence file (gitignored and local, so no commit is involved). The durable record of the review is the `review.pr` ledger event appended at Create Step 4.
  - (f) At `:266`, delete "Deliberately not restated here: three copies of a procedure is how two of them go stale."
- model_dependent: no
- machine_read: yes. `tests/test_pr_reviewer_agent.py:174-175` and `:438` pin "its always-loaded `.claude/rules/` files", "does not stop a **path-scoped** rules file" and "omitClaudeMd" inside Step 3 (all in `:167`). (a) requires moving those assertions to `agents/pr-reviewer.md`, which carries the same facts. `tests/test_pr_reviewer.py` pins "Neither check subsumes the other" (kept).

### C-17: Caps and repeated "never create without the reviewer" framing
- location: `plugin/skills/pr/SKILL.md:11`, `:153`, `:206`, `:272`
- evidence: "**CRITICAL: The independent PR review is the core value of this skill."
- pattern: Group 1a pressure language (CRITICAL plus caps, and the same constraint restated four times)
- why: The owner's constraint (never skip the reviewer; see the user memory) stays. Stated once in capitals and three more times in the same file, it reads as anxious register on a model that follows a plainly stated instruction. Step 4's mechanical check is what enforces it.
- confidence: medium
- action: rewrite
- replacement: `:11` becomes:
  > The independent PR review is this skill's core value. Never create a PR without running the reviewer and checking its evidence file; Step 4 refuses otherwise, and the stop hook blocks session end on a PR with no evidence.

  Leave `:153` ("**STOP. Do NOT proceed to step 4 until …**"), which is the pinned step-local instruction. Delete `:272` ("**Never run `gh pr create` without a valid evidence file on disk**"), which repeats Step 4's "If any check fails, STOP. Do not create the PR."
- model_dependent: yes (owner feedback records a past skip)
- machine_read: yes. `tests/test_pr_reviewer.py:625-627` pins "MANDATORY", "Do NOT proceed" and "evidence file" in the file (kept at `:152-153`).

### C-18: Bold does the job of caps across `pr/SKILL.md`
- location: `plugin/skills/pr/SKILL.md:51-272` (166 bold spans in 272 lines)
- evidence: "**Nothing downstream catches that.** The coverage gate re-runs green because it reads local HEAD"
- pattern: prawduct "Emphasis in bold rather than caps"; Group 1a
- why: When most sentences in a paragraph are bold (`:130`, `:132`, `:211`, `:228`), the bold stops marking the one instruction that matters. The guide treats that as the same register problem as a page of capitals.
- confidence: medium
- action: rewrite
- replacement: Rewrite approach: in each paragraph keep bold on at most one element, the command to run or the stop condition, and plain-text the rest. Worked examples:
  - `:211`: "**Nothing downstream catches that.**" becomes "Nothing downstream catches that." The bold stays on `prawduct-hook check-branch-pushed`'s sentence.
  - `:130`: keep "**Run `prawduct-hook check-cumulative-critic`.**" and unbold "**STOP**" to "stop".
  - `:228`: keep the step's lead "**Verify the PR's head is the commit you mean to merge**" and unbold the rest.

  Leave severity labels and field names as they are.
- model_dependent: no
- machine_read: yes. Several pins include `**` (for example `test_pr_reviewer_agent.py:433` "**Wait for the agent to complete.**"). Keep any bold span a test quotes.

### C-19: The Critic fork reads mechanism prose it never acts on
- location: `plugin/skills/critic/SKILL.md:10-17`, `:37`, `:45`, `:47`, `:50`, `:73`
- evidence: "a defined agent type's tools DO constrain it, unlike a skill's `allowed-tools`"
- pattern: Group 2 verbose SKILL.md; Group 1c padding (restating the precedence a helper owns); incident archaeology (#292, #167, "30 of 30")
- why: The fork's job is to resolve the mode, dispatch, then review or coordinate. The HTML comment (`:10-17`) and `:37` explain how the harness enforces tool lists. `:45` spells out the full mode precedence right after saying "Do NOT interpret the arguments yourself: the helper owns the full precedence". `:50` justifies the file split with a measurement. `:73` documents `critic-discard`/`critic-restore`, which the fork is told it never runs. All of this is paid on every Critic invocation, including every chunk review.
- confidence: medium
- action: rewrite
- replacement:
  - (a) Delete the `<!-- Role: … -->` comment (`:10-17`). `:35` already states the no-execution rule.
  - (b) Delete `:37`.
  - (c) `:45` becomes:
    > **Forward, never parse.** Run `prawduct-hook infer-critic-mode <args…>`, forwarding the collected arguments verbatim (no argument when none were delivered; never forward the literal placeholder). Do NOT interpret the arguments yourself: the helper owns the precedence (explicit token, then the plan's `Critic mode:`, then inference) and prints one line, `<mode>|<rationale>`. Use the returned mode and record the rationale verbatim as `mode_chosen_by`.
  - (d) `:47`: delete "(#292)" and "(#167)".
  - (e) `:50`: delete "Loading the seven-goal protocol to run three is the payload this split removes — measured, `chunk` missed its 1-2 min target in 30 of 30 recorded runs."
  - (f) `:73` becomes:
    > You never write `.prawduct/.critic-findings.json` or a ledger line; `critic-consolidate` is the only writer of both. If you must abandon a review after dispatch, run `prawduct-hook critic-end` to clear the marker (it does not touch partials). A complete roster left by a failed consolidation is the main session's decision (`critic-discard` / `critic-restore` are not in your tools): report the refusal's stderr and stop.
- model_dependent: no
- machine_read: yes. `tests/test_critic_skill_metadata.py:165-176` pins "infer-critic-mode <args" and "Do NOT interpret the arguments yourself" (kept) and "34164" (at `:44`, untouched). `tests/preferences/test_free_interval_prose.py` requires "Exit 3" and "--force" (untouched). `tests/test_skill_command_grants.py:272-273` expects critic-discard/restore to be absent from the grants, not from the prose.

### C-20: The Coordinator Pattern ships to the three reviewers it dispatches
- location: `plugin/skills/critic/review-protocol.md:139-155`; `plugin/skills/critic/SKILL.md:71`
- evidence: "Persistence is **decoupled from the review**: reviewers write partials, `critic-consolidate` merges them against the code-written manifest"
- pattern: prawduct duplicated facts (#342); Size (text read by an audience that never acts on it)
- why: The coordinator instructions (dispatch three agents in one message, the prompt template, "Stop — do not resume") are for the fork, which also reads `SKILL.md:71`, where the same rule is restated. Each dispatched `critic-reviewer` also loads `review-protocol.md` and so reads instructions for dispatching itself.
- confidence: medium
- action: move
- replacement: Move `review-protocol.md:139-155` (the `### Coordinator Pattern` subsection) into `SKILL.md` step 7's coordinator bullet, replacing that bullet's restatement. In `review-protocol.md`, leave:
  > **Roster `correctness`/`design`/`sustainability`**: the coordinator dispatches you. Your contract is your agent definition.
- model_dependent: no
- machine_read: yes. `tests/test_critic_reviewer_agent.py:243-261` and `:370-379` split `REVIEW_PROTOCOL` on "### Coordinator Pattern" … "## Output Format" and pin "do not resume", "Project (absolute)", "`worktree`" and "git -C [dir] rev-parse HEAD" there. `tests/test_v5_methodology.py:6259` pins "Signals: <SIGNALS>" and "`signals` verbatim" in `review-protocol.md`. All would re-point to `SKILL.md`. The `single-pass-full` route is unchanged (it loads both files); `dispatched-reviewer` drops about 500 tokens per reviewer.

### C-21: A prohibition against reading a field that does not exist
- location: `plugin/skills/critic/review-protocol.md:51`, `plugin/skills/critic/goals-1-3.md:71`, `plugin/skills/pr/review-protocol.md:120`
- evidence: "never infer staleness from a commit/SHA field in the evidence (it carries none)"
- pattern: Group 1c prohibition lists ("a prohibition against a failure the model wasn't going to make can anchor it toward that failure"); Group 1d fossil
- why: The evidence record has no SHA field (the text says so), so the prohibition guards a retired field. It mentions that field in all three reviewer payloads, and `pr/review-protocol.md:120` adds the TST-4K2P story. The positive rule ("that exit code is the *only* freshness signal") already carries the constraint.
- confidence: medium
- action: rewrite
- replacement:
  - In both Critic files, delete "; never infer staleness from a commit/SHA field in the evidence (it carries none)", leaving "that exit code is the *only* freshness signal."
  - In `pr/review-protocol.md:120`, delete "Never infer "stale" from a commit/SHA field in the evidence: the record carries none (TST-4K2P retired `git_sha` precisely because a record-before-commit run made it lag HEAD and read as a false stale)."
- model_dependent: yes
- machine_read: no (no test pins these phrases). Budgeted: `review-protocol.md` <4413, `goals-1-3.md` <2669.

### C-22: "Do not invent findings" anchors toward under-reporting
- location: `plugin/agents/critic-reviewer.md:133-135`
- evidence: "do not invent findings to fill space. When a finding rests"
- pattern: guide-opus5 "Severity filters still depress measured recall"; Group 1c prohibition against a failure the model does not make (Opus 5.5: "fewer false alarms")
- why: Opus 5.5 does not pad reviews. A prohibition on padding, paired with "a clean pass is normal and correct", pushes a literal-following reviewer toward silence on borderline items. That is the recall direction the Opus 5 guidance warns about. "Zero findings is a valid result" is the fact worth keeping.
- confidence: medium
- action: rewrite
- replacement: "Assess your goals and gather findings, each with a severity … A clean pass has zero findings — that is normal and correct; do not invent findings to fill space." becomes:
  > Assess your goals and report every finding with its severity: `blocking`, `warning`, or `note` (definitions in `review-protocol.md`). A clean pass has zero findings.
- model_dependent: yes
- machine_read: no

### C-23: Depth-by-work-size heuristics coach review strategy
- location: `plugin/skills/critic/review-protocol.md:24-28`
- evidence: "**Work size**: Trivial (1-2 files) → quick coherence check. Small (bug fix) → root cause + regression."
- pattern: Group 1c strategy coaching; Opus 5.5 is a stronger code reviewer
- why: "Trivial → quick coherence check … Large → deep architectural review" and "Bugfix → root cause + regression test" are the author's heuristics for how to review. Removing them does not change what is legal or how success is measured: the goals and severities do that. `:111` ("Applies proportionally …") already states the one real quality bar.
- confidence: medium
- action: remove
- replacement: (delete the `## Signals That Guide Your Review` heading and its **Work size** and **Work type** lines; keep the **Subject and oracle** and **Stage** paragraphs, which currently sit under that heading, under a heading such as `## Scope and stage`)
- model_dependent: yes
- machine_read: yes. `tests/test_v5_methodology.py:4647-4653` (`test_signals_and_work_scaling`) pins the heading and the words Trivial, Small, Medium, Large, Feature and Bugfix. Delete that test with the text.

### C-24: Dangling standard ids in the Instruction Clarity check
- location: `plugin/skills/critic/framework-checks.md:37`, `:41`
- evidence: "Check for S1 violations (multi-level conditionals in prose), S2 violations"
- pattern: Group 2 volatile specifics (ids of a structural-standards list that no longer exists anywhere in `plugin/` or `documentation/`)
- why: A reviewer asked to find "S1/S2/S6 violations" goes looking for a definition that does not exist. The parentheticals already say what each id means.
- confidence: medium
- action: rewrite
- replacement: `:37` becomes:
  > Check for multi-level conditionals in prose, subjective thresholds without concrete definitions, and unresolved contradictions.

  `:41` becomes:
  > One of those three structural defects → **warning**
- model_dependent: no
- machine_read: no. The `framework-checks.md` ceiling is at `tests/test_v5_methodology.py:5759`.

### C-25: Budget line for the builder while it waits on both boundary reviews
- location: `plugin/skills/pr/SKILL.md:192-195`
- evidence: "- If the file does not exist, the review did not complete — do NOT proceed"
- pattern: Opus 5.5 guide: "pays close attention to elapsed-time signals in multi-agent setups"; Group 1d/1f (say *when* user-facing text is wanted instead of a cadence)
- why: The builder waiting on the cumulative Critic and the PR reviewer has no stated expectation of how long that takes. The only wait guidance is C-2's cadence, which lives in a file the builder is not in. A budget stated in the coordinator (not in either reviewer) helps it pace. Recall risk: none on the reviewers, because the line never reaches them. The risk is the builder treating a slow reviewer as dead. Per `.claude/rules/learnings/reviews.md`, liveness is answered by the agent's own completion signal, never by reading files it is mid-writing. The caller asked for this as `add` at low confidence, so it carries replacement text.
- confidence: low
- action: add
- replacement: After "**Wait for the agent to complete.** Then:", insert:
  > Both boundary reviews usually land within about 10 minutes. If one has not reported after about 20, tell the user what you are waiting on. Judge liveness by the agent's own completion signal, never by reading files it may be mid-writing, and never re-dispatch while it is running.
- model_dependent: yes
- machine_read: yes. `tests/test_pr_reviewer_agent.py:433-434` pins the two surrounding lines; the insertion keeps both.

### C-26: The Records Pass drops sub-bar record defects with no channel at the boundary
- location: `plugin/skills/critic/review-cycle.md:432-435`
- evidence: "Everything else — an imprecise count, a narration one revision short, a phrasing that could be truer —"
- pattern: guide-opus5 "Severity filters still depress measured recall"
- why: This is the one place in the Critic prompts where a rated defect is dropped rather than demoted. At `inner` stage a sub-bar item could ride `observations`, but at `boundary` (sustainability at `cumulative`) consolidation refuses that array, so "is **not a finding**" means unreported. The filter is deliberate and measured (it cuts rounds on record-only findings). The documented alternative (report with severity, filter downstream) would need a consolidation change so `observations` are accepted at the boundary too. That is outside prompt text, so this is flagged only.
- confidence: low
- action: flag
- replacement: (none)
- model_dependent: yes
- machine_read: no

### C-27: Wall-clock targets inside reviewer payloads
- location: `plugin/skills/critic/goals-1-3.md:3`, `plugin/skills/critic/review-protocol.md:19-20`
- evidence: "do not open `review-protocol.md` or `review-cycle.md`. Target wall-clock: 1-2 minutes."
- pattern: Opus 5.5 guide (elapsed-time signals; "may verify slightly less under time pressure")
- why: "Target wall-clock: 1-2 minutes" (chunk, the most frequent review) and "Target 4-10 min" (final) are owner telemetry targets, but they reach the reviewer as a time budget. On Opus 5.5 a tight budget can trade away verification, and so recall. Whether these lines measurably depress findings needs an A/B on `review-stats` yield. If they do, they belong in `review-cycle.md`'s table (maintainer-facing) only.
- confidence: low
- action: flag
- replacement: (none)
- model_dependent: yes
- machine_read: no

### C-28: The "resolutions" prohibition explains a field that is absent from the schema
- location: `plugin/agents/critic-reviewer.md:183-186`
- evidence: "different review entirely — you exist only for a coordinator roster, and `resolutions` belongs"
- pattern: Group 1c prohibition list (it names a key that is absent from the reviewer's schema, which can anchor toward it)
- why: The partial schema shown to this reviewer has no `resolutions` key. Four lines explaining `resolutions[].review_id` may create the failure they forbid. The prose may encode an observed failure, though, and I cannot confirm from here that it no longer reproduces.
- confidence: low
- action: flag
- replacement: (none)
- model_dependent: yes
- machine_read: no

### C-29: Update Flow legacy-evidence branches
- location: `plugin/skills/pr/SKILL.md:216`
- evidence: "If the field is absent (evidence written by an older reviewer), the delta is **substantive by default**"
- pattern: Group 1d fossils (back-compat conditionals for records written before a field existed)
- why: Evidence files are per-branch and deleted at merge, and the ledger's absent-field case covers "an event appended before the field existed". Both may now be unreachable in practice. If so, the two conditionals are dead weight in the builder's longest step. I could not verify reachability from the prompt surface alone.
- confidence: low
- action: flag
- replacement: (none)
- model_dependent: no
- machine_read: no

## Outside my slice
- `plugin/lib/critic_consolidate.py` `VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE` / `_BATCH_FIX_DIRECTIVE` and `plugin/lib/gates.py:2304,2921` print review-cycle section names to the model; C-8 should leave those section names in `review-cycle.md`.
- `plugin/methodology/building.md:107` and `:201` carry the builder-side summary that `review-cycle.md`'s builder half expands; see C-14's `dup_of`.
