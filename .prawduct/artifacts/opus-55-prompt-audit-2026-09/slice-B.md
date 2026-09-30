# Slice B: methodology guides (building, planning, discovery, reflection, delegation, session-hygiene) and every artifact template under plugin/templates/

## Inventory

I read every file below in full. Word counts come from `wc -w`.

Methodology guides (each has a token ceiling in `tests/test_v5_methodology.py`: building 5122 at :465, discovery 4603 at :1062, planning 5804 at :1166, reflection 2852 at :1241, session-hygiene 3198 at :1258, delegation 2762 at :1361):

| File | Words |
|---|---|
| plugin/methodology/building.md | 3940 |
| plugin/methodology/planning.md | 4465 |
| plugin/methodology/discovery.md | 3541 |
| plugin/methodology/reflection.md | 2194 |
| plugin/methodology/delegation.md | 2125 |
| plugin/methodology/session-hygiene.md | 2460 |

Templates (no token ceilings; `init_product` copies backlog, change-log, project-preferences, boundary-patterns and project-state verbatim into every new product, and `/prawduct:runbook` copies runbook.md):

| File | Words |
|---|---|
| plugin/templates/api-contract.md | 1614 |
| plugin/templates/architecture.md | 1193 |
| plugin/templates/backlog.md | 635 |
| plugin/templates/boundary-patterns.md | 218 |
| plugin/templates/build-plan.md | 2176 |
| plugin/templates/change-log.md | 230 |
| plugin/templates/data-model.md | 499 |
| plugin/templates/human-interface/accessibility-spec.md | 545 |
| plugin/templates/human-interface/design-direction.md | 558 |
| plugin/templates/human-interface/information-architecture.md | 488 |
| plugin/templates/human-interface/localization-requirements.md | 381 |
| plugin/templates/human-interface/onboarding-spec.md | 598 |
| plugin/templates/human-interface/screen-spec.md | 496 |
| plugin/templates/nonfunctional-requirements.md | 363 |
| plugin/templates/observability-strategy.md | 1378 |
| plugin/templates/operational-spec.md | 385 |
| plugin/templates/operator-verification.md | 998 |
| plugin/templates/product-brief.md | 420 |
| plugin/templates/project-preferences.md | 1321 |
| plugin/templates/runbook.md | 3247 |
| plugin/templates/security-model.md | 466 |
| plugin/templates/test-specifications.md | 1093 |
| plugin/templates/unattended-operation/configuration-spec.md | 424 |
| plugin/templates/unattended-operation/failure-recovery-spec.md | 437 |
| plugin/templates/unattended-operation/monitoring-alerting-spec.md | 446 |
| plugin/templates/unattended-operation/pipeline-architecture.md | 396 |
| plugin/templates/unattended-operation/scheduling-spec.md | 354 |

The human-interface and unattended-operation templates are clean. Their comments are short section prompts that shape the artifact, so I list nothing for them.

## Summary

The highest-impact decisions are these. B-1 stops the builder from reviewing its own changes while the independent Critic runs. B-2 removes a mandated subagent for what is a grep. B-10 to B-15 remove the places that push delegation (tangents offered to a delegate first, independence alone as the "ordinary yes", a third copy of the default) or have the coordinator re-derive a delegate's work. B-9, B-16 and B-35 close three early-stop openings: the "say go" shade, a chunk boundary read as the end of the turn when the next chunk is ready, and a "hard stop" that is really "run the review first". B-6 and B-7 cut incident narratives from the operator-verification template, which is copied into every product. For backlog #341 the binding-method sites are planning.md:57-104 (B-17), the build-plan Deliverables lines (B-18) and planning.md's between-phase self-review (B-19). The Wave 3 scaffolding items are B-21 (domain-concern table), B-23 (root-cause stopping rule), B-25 (3-4 file tie-break) and B-26 (red-baseline protocol), each marked `model_dependent: yes`. I keep the filled example chunk in build-plan.md. It pins a machine-read field format, which is item 7 of the guide's keep list, and it is labeled as an example.

Counts: 41 decisions: 8 high, 32 medium, 1 low. 34 are rewrites, 5 are removals, 1 is an add and 1 is a flag. B-20's rewrite also moves a prawduct-only list into this repo's own rules. The token-ceiling tests to lower after trims are for building, planning, discovery, reflection, delegation and session-hygiene (see Inventory). No template has a ceiling.

## Decisions

### B-1: Builder self-review while the Critic runs
- location: `plugin/methodology/building.md:201`
- evidence: "deep-scrub your own changes while it runs, which often pre-resolves findings"
- pattern: Opus 5 row "Over-verification" and "Self-check instructions are the same trap"; prawduct pattern "self-verification prose aimed at the builder"
- why: An independent reviewer is already checking the same tree. Telling Opus 5 to re-scrub its own diff at the same time is the self-check instruction that the Opus 5 guidance says to delete. The one load-bearing fact is "don't edit the reviewed tree", and it survives in the replacement.
- confidence: high
- action: rewrite
- replacement: "**The Critic takes minutes, not seconds** (per-mode targets: `review-cycle.md`). Don't poll. While it runs, never edit the reviewed files: `critic-begin` snapshots a tree, so an edit under review voids the review and the suite evidence together, and `test-status` still exits 0. Work outside that tree (the plan, the change-log, `.prawduct/`) is safe. If it fails, tell the user and re-invoke — never write `.critic-findings.json` yourself."
- model_dependent: no
- machine_read: no

### B-2: A subagent mandated for consumer search, plus step choreography
- location: `plugin/methodology/building.md:135-141`
- evidence: "**Investigate** with a focused subagent: read the changes, grep for consumers across layers"
- pattern: Opus 5 row "Delegates to subagents more readily" (do not use subagents for "a simple search task"); 1c step-by-step choreography
- why: A consumer grep across layers takes a handful of tool calls. Opus 5 already over-reaches for subagents, and this line mandates one. The four numbered steps are a judgment task scripted as a sequence.
- confidence: high
- action: rewrite
- replacement: (lines 135-139) "When you modify a producer with known consumers, grep for those consumers across layers, update them, add integration tests for the crossing, and record what you checked and found — the Critic verifies the investigation occurred." (line 141, first sentence) "**Both directions.** The above asks *did my change break downstream consumers?*" The rest of line 141 stays as written.
- model_dependent: no
- machine_read: no

### B-3: Dead "Tier / Owner: Artifact Generator (C3)" headers in the artifact templates
- location: `plugin/templates/build-plan.md:1`
- evidence: "Build Plan Template — Tier 1 (Source of Truth)"
- pattern: Group 2 "Volatile specifics" and history narratives; 1d fossil
- why: No code, skill or doc in the plugin defines "Artifact Generator (C3)" or an artifact "Tier 1 (Source of Truth)". Each is a leftover component name that gets copied into every product artifact. In runbook.md, "Tier: 2 (Operational)" also collides with the runbook proportionality tier set by the frontmatter `tier:` (docs/runbook-authoring.md "Tier 1 — Note").
- confidence: high
- action: remove
- replacement: Delete the `Tier: …` and `Owner: Artifact Generator…` lines. Sites: product-brief.md:2-3, data-model.md:2-3, security-model.md:2-3, nonfunctional-requirements.md:2-3, operational-spec.md:2-3, test-specifications.md:2-3, architecture.md:2-3, api-contract.md:2-3 and runbook.md:2-3 (runbook's `Owner:` repeats the frontmatter `owner:`). In build-plan.md:1, change "`<!-- Build Plan Template — Tier 1 (Source of Truth)`" to "`<!-- Build Plan Template`".
- model_dependent: no
- machine_read: no (the plan-frontmatter parser only skips a leading comment; `tests/test_plan_index.py:82` uses its own fixture string, not the template)

### B-4: Unnamespaced command names and dangling references in shipped templates
- location: `plugin/templates/backlog.md:3-14`
- evidence: "Structured backlog (Prawduct v1.7+). Managed with the `/backlog` skill:"
- pattern: Group 2 "Volatile specifics" (stale command names and a dead doc reference); 1d version fossil
- why: The skills are `/prawduct:backlog`, `/prawduct:pr` and `/prawduct:critic`. The bare forms name commands that do not exist, and the hook test that forbids them (`tests/test_plugin_runtime.py:639`) does not scan templates. `backlog-system-requirements.md D4/§5` lives only in prawduct's own `documentation/`, so every product receives a dangling reference. "(Prawduct v1.7+)" is a version fossil.
- confidence: high
- action: rewrite
- replacement: backlog.md lines 3-14 become "`<!-- Structured backlog. Manage it with /prawduct:backlog — pick, add, find <q>, list, update ID, migrate. Items move between the three sections below via /prawduct:backlog update ID status=...; status is never inferred from build plans or change logs — an agent or human sets it explicitly.`". Also change backlog.md:69 to "Run `/prawduct:backlog migrate` to add structure…". Change project-preferences.md:68 "`/critic` review" to "`/prawduct:critic` review". Change operator-verification.md:18 and :20 "`/pr create`" to "`/prawduct:pr create`".
- model_dependent: no
- machine_read: no (only the item shape and `Legacy items` are pinned: `tests/test_v5_templates.py:143-151`)

### B-5: The backlog legend disagrees with the skill on `closed-by:` and omits `revisit:`
- location: `plugin/templates/backlog.md:51-53`
- evidence: "closed-by: <chunk-id | scope/branch | tag>  what shipped this item"
- pattern: guide keep list 8, exception clause (duplicates that disagree); Group 3 under-description (a field missing from the contract)
- why: `skills/backlog/SKILL.md:74` says closed-by is "never a bare chunk id, which names no plan", and the template lists `<chunk-id>` first. The skill's canonical field set includes `revisit:`, which the template never mentions, so a freshly onboarded repo starts with a legend that its own migrate step 4c has to repair.
- confidence: high
- action: rewrite
- replacement: "`closed-by: <scope/branch | release tag>  what shipped this item (item → release), set on status=shipped; a handle that exists before the commit — never a bare chunk id (names no plan), a bare commit SHA (dangles on --amend) or an unassigned PR#`". Then add after the `refs:` entry: "`revisit: YYYY-MM-DD | <event>  expiry on a norm exception or stopgap; a past date raises an advisory while the item is open`".
- model_dependent: no
- machine_read: no (the legend is model-read by migrate step 4c; no parser reads the comment)
- dup_of: plugin/skills/backlog/SKILL.md:74

### B-6: Incident narrative and ruling date in the operator-verification status rule
- location: `plugin/templates/operator-verification.md:32-55`
- evidence: "AND THAT IS SETTLED, NOT AN OPEN BUG. Ruled 2026-09-12, after the shape above"
- pattern: Group 2 "History narratives" and "The recency trap"; 1a caps
- why: The rule is that the status sits on its own line. Around it are two bug filings, a ruling date and a paragraph defending the decision. All of it is copied into every product's queue. A one-sentence statement of the ruling does the same job for the reader who would file it again.
- confidence: high
- action: rewrite
- replacement: "`     It also sits on a line of its own: the entry's first non-blank body line, holding nothing but **Status:** <word>. A compact header that runs the status in with other metadata —` / `         **Chunk:** <chunk> - **Raised:** <date> - **Status:** pending` / `     — is the shape an agent naturally writes, and it is not read as a status: the entry keeps counting as pending until the line is split. The strict shape is deliberate; the parser will not accept a second one.`"
- model_dependent: no
- machine_read: yes (the shipped template must still parse as an OK queue, which `tests/test_operator_verification.py:713` pins; keep "bare token and nothing else", pinned at :907)

### B-7: Incident story in the split-the-deferral rule
- location: `plugin/templates/operator-verification.md:60-91`
- evidence: "here deferred three integration facts together on the grounds that"
- pattern: Group 2 "History narratives"
- why: The rule (split the static half from the delivery half, and give each fact its own reason) is sound. The "seventeen days" story and "the rule this queue cost the most to learn" are archaeology, and they ship into every product.
- confidence: high
- action: rewrite
- replacement: "`     SPLIT THE DEFERRAL BEFORE YOU WRITE THE ENTRY. Every claim you are about to defer splits in two:` / `       1. CAN THIS BE TRUE IN PRINCIPLE? — static, decidable today from the code and the documented rules (can a matcher match this agent type; is this exit code mapped).` / `       2. DOES THE HARNESS ACTUALLY DO IT? — delivery: does the event fire, does the session render it, does the real API behave as the fake does.` / `     ONLY THE SECOND HALF BELONGS IN THIS QUEUE. The first half is a test you can write now. Give each fact its own reason; a fact whose reason is really "I have not checked" is work, not a queue item.` / `     A deferral needs an owner and a trigger: name whose harness answers it and when you will ask. If the answer is "nobody's, ever", the honest status is accepted with that stated.`"
- model_dependent: no
- machine_read: yes (`tests/test_operator_verification.py:879-888` pins "SPLIT THE DEFERRAL", "ONLY THE SECOND HALF BELONGS IN THIS QUEUE" and "Drain before you flip", all of which stay)

### B-8: Issue and feature ids inside instructions
- location: `plugin/methodology/planning.md:172`
- evidence: "and the last chunk's `cumulative` is every chunk's review (#292)"
- pattern: Group 2 "History narratives: … incident IDs, PR numbers"
- why: The rule carries its own authority. "(#292)" here and "(F10)" at building.md:111 are archaeology the reader cannot act on.
- confidence: high
- action: remove
- replacement: planning.md:172 drops " (#292)". building.md:111 changes "**Operator verification (F10).**" to "**Operator verification.**".
- model_dependent: no
- machine_read: no (`tests/test_short_plan_deferral.py:386` pins "unless the plan is short" and "at most 3 chunks", which are unchanged)

### B-9: The "just go" shade of `YOUR TURN` licenses the early stop
- location: `plugin/methodology/session-hygiene.md:29`
- evidence: "because its three shades cost them very different amounts: *just go*"
- pattern: Opus 5.5 early-stop behavior ("announces the next step instead of taking it, offers to carry on"); prawduct pattern "early-stop invitations"
- why: Offering "say go" as a legitimate way to end a turn is the stop that Opus 5.5 makes too readily. Step 1 at :57 already forbids it when you can proceed, but this line teaches it as a normal shade. The replacement names the stops that are wanted, which the 5.5 guide says works.
- confidence: medium
- action: rewrite
- replacement: "…the **copy leads with the ask, imperative, cheapest form first**, because its shades cost them very different amounts: *approve* ("say go to open the PR" — only for a step that needs their word: a PR, a merge, anything outward-facing or irreversible), *decide* ("pick A or B"), *unblock* ("I need push access to the release remote"). A turn whose only ask would be "shall I continue?" is not `YOUR TURN`: continue. Obstruction is one of those shades…" (the rest unchanged)
- model_dependent: no
- machine_read: no

### B-10: The coordinator re-derives a delegate's sweep
- location: `plugin/methodology/building.md:161`
- evidence: "on a removal or a sweep is a claim — verify it by re-deriving it."
- pattern: Opus 5 delegation block ("Never redo the subagent's work and do not re-derive its findings"); Over-verification
- why: The failure behind it is real (sweeps fail looking finished). The fix belongs in the delegate's return contract, where it costs one pasted command output. Doing it in the coordinator's loop re-derives the delegate's work.
- confidence: medium
- action: rewrite
- replacement: "**A delegate's "Done" on a removal or a sweep arrives with its evidence.** These fail silently and in the direction of looking finished: a symbol left behind, an allowlist wider than the brief, an inventory short. Ask for the falsifying output in the brief (the grep for the removed symbol returning nothing, the recount against the source you named, the files it touched) and read it when the report lands; don't repeat the sweep."
- model_dependent: yes
- machine_read: no
- dup_of: plugin/methodology/delegation.md:43

### B-11: The same re-derivation, as an anti-pattern tell
- location: `plugin/methodology/delegation.md:43`
- evidence: "you accepted a delegate's completion report on a removal or a sweep without re-deriving it"
- pattern: Opus 5 delegation block (do not re-derive); #342 duplicate of building.md:161
- why: Same reason as B-10. The tell changes from "you didn't redo it" to "it came back without evidence".
- confidence: medium
- action: rewrite
- replacement: "- **The Done taken on faith.** *Tell:* you accepted a delegate's completion report on a removal or a sweep that carried no evidence — no grep output for the removed symbol, no recount against the source you named. These fail in the direction of looking finished, so the report reads identically either way."
- model_dependent: yes
- machine_read: no (`tests/test_v5_methodology.py:3207` needs at least 7 bullets, each with a `*Tell:*`; both hold)

### B-12: The brief's return clause should ask for that evidence
- location: `plugin/methodology/delegation.md:56-57`
- evidence: "**Who integrates** — you. Say so, so the delegate doesn't try."
- pattern: guide keep list 11 (re-baselining adds text) paired with B-10 and B-11
- why: B-10 and B-11 move verification into the brief, so the brief checklist needs the clause, or nothing asks for it.
- confidence: medium
- action: add
- replacement: Line 56 becomes "- **What to return**, and in what form — for a removal or a sweep, the output of the command that shows it complete."
- model_dependent: yes
- machine_read: no

### B-13: "Delegation is offered first" for tangents
- location: `plugin/methodology/delegation.md:67`
- evidence: "Delegation is offered first — and that default is a *policy* setting rather than a technical one."
- pattern: Opus 5 row "Delegates to subagents more readily" (remove "delegate more" guidance); 1a "Default to [tool]"
- why: This makes delegation the first proposal for every tangent, and Opus 5+ over-reaches for subagents without help. The file's own sorting question ("would you integrate this today?") does the real work. The owner's measured 0.34% delegation rate (`tests/test_v5_methodology.py:3222`) concerned plan-time partition, not tangents. Verify on the current model before taking this.
- confidence: medium
- action: rewrite
- replacement: "**The decision is three-way, made once, out loud: do it now, delegate it, or backlog it.** `project-preferences.md`'s `Delegation` row sets this project's policy, and `off` means delegation is never proposed. The question that sorts the three: *would you integrate this today if it came back green?* If not, backlog it; if it would take a handful of tool calls, do it now; delegate when running it beside your own work shortens wall clock and it touches nothing yours does."
- owner amendment (F4 ruling, 2026-09-28): the delegate criterion is wall-clock gain without material conflict, per the owner's note, not size alone.
- model_dependent: yes
- machine_read: no

### B-14: building.md restates the delegation default and re-asks it of tangents
- location: `plugin/methodology/building.md:153`
- evidence: "and asked again of a tangent or anything you were about to backlog"
- pattern: Opus 5 row "Delegates to subagents more readily"; #342 duplicate (the default is stated at delegation.md:9 and planning.md:112 as well)
- why: A third copy of the default, plus an instruction to raise delegation for every backlog candidate, is a delegation push. delegation.md owns the judgment, and this section says so.
- confidence: medium
- action: rewrite
- replacement: "**When the user asks you to work in a subagent, do it** (Principle 23). Otherwise whether to delegate is `/prawduct:methodology delegation`'s judgment, recorded as the plan's `partition:` and re-checked at each chunk close — read it before fanning out; this section is the mechanics."
- model_dependent: yes
- machine_read: yes (`tests/test_v5_methodology.py:4043-4048` pins "chunk close" and "`partition:`" in this preamble; both are kept)
- dup_of: plugin/methodology/delegation.md:9

### B-15: "Independent chunks" alone is the ordinary yes
- location: `plugin/methodology/delegation.md:9`
- evidence: "A plan whose chunks are independent is the ordinary yes."
- pattern: Opus 5 delegation block (subagents for "large tasks that are genuinely independent", not work "you could finish yourself in a handful of tool calls")
- why: Independence is necessary but not sufficient. The Opus 5 guidance adds size. Without it, three small independent chunks count as a yes.
- confidence: medium
- action: rewrite
- replacement: "Independent chunks are the ordinary yes when delegating them shortens wall clock, which needs each to be large enough to repay a delegate's re-exploration; a chunk you could finish in a handful of tool calls does not."
- owner amendment (F4 ruling, 2026-09-28): size is kept as the proxy for wall-clock gain, which is the owner's criterion.
- model_dependent: yes
- machine_read: no (`tests/test_v5_methodology.py:3236-3243` pins "wall clock", "fight each other" and "stay serial", all unchanged)

### B-16: A chunk boundary reads as the end of the turn
- location: `plugin/methodology/building.md:123`
- evidence: "**Then close the turn with the standing block — last, after every other word.**"
- pattern: Opus 5.5 early stop (name the stops you want); prawduct pattern "early-stop invitations"
- why: The paragraph opens "at a chunk boundary … complete in order" and then says "close the turn". Read literally, that ends every turn at every chunk boundary, even when the user asked for the whole plan. Naming when a boundary does end the turn is the 5.5 guide's recommended fix.
- confidence: medium
- action: rewrite
- replacement: "**A chunk boundary ends the turn only when the plan is done, the next chunk needs the user, or the work cycle has reached what one review can cover** (§ above); otherwise carry on to the next chunk after steps 1-7. **When the turn does end, close it with the standing block — last, after every other word.** Say `SAFE TO CLEAR` only when steps 1-7 above are done **and nothing is outstanding, in flight included** — that binding is what this file owes the block. A decision awaiting the user is not outstanding once step 7 records it. Its shape, trigger and failure modes are `methodology/session-hygiene.md`, and the session digest injects them into every session."
- model_dependent: no
- machine_read: yes (`tests/test_v5_methodology.py:2489-2503` pins "standing block", "steps 1-7", "in flight included" and "methodology/session-hygiene.md", and forbids the `STATE`/`RUNNING`/`YOUR TURN`/`COMPLETE` labels; the replacement complies)

### B-17: Chunk shape asserted as binding (#341) in planning.md
- location: `plugin/methodology/planning.md:57-104`
- evidence: "The build plan decomposes artifacts into buildable chunks — coherent units of work with clear deliverables and acceptance criteria."
- pattern: #341 binding method; 1c "Strategy coaching next to task rules"; 1c over-specification
- why: Acceptance criteria are the contract. The chunk *shape* is advice the model can depart from with reason, and the same goes for "Good chunks are:", "The first chunk is special" and the checkpoint quota (1-2 / 3-5). The only hard limit here is "one Critic pass", and review mechanics drive it.
- confidence: medium
- action: rewrite
- replacement: Line 57: "The build plan decomposes artifacts into buildable chunks, each with acceptance criteria that define done. What a chunk will touch is a forecast, not a contract." Lines 94-100: "**Chunks usually work best** as vertical slices (working, testable functionality across layers), in dependency order, each verifiable without later chunks and small enough for one Critic pass — the last is the firm limit. A thin first slice through the whole architecture proves the layers connect before you widen it." Line 104: "**Governance checkpoints** are points where you review the whole trajectory, not just the current chunk — typically after the first chunk proves the architecture, and before completion; add more as risk warrants."
- model_dependent: no
- machine_read: no

### B-18: Deliverables phrased as a file contract in the template (#341)
- location: `plugin/templates/build-plan.md:196`
- evidence: "- **Deliverables:** new `pantry/main.py`, new `pantry/store.py`, new `templates/list.html`, seeded dev database"
- pattern: #341 binding method; 1c example over-indexing (the filled example teaches file lists as the deliverable)
- why: Every backticked path in a chunk section is existence-checked, and `chunk-ref-missing` is BLOCKING (`skills/critic/review-cycle.md:447`). A file list as the deliverable therefore binds the builder to a layout the planner guessed. Chunk 03 (:226) also creates `pantry/lookup.py` without the `new` prefix that planning.md:208 requires.
- confidence: medium
- action: rewrite
- replacement: :196 "- **Deliverables:** the list page renders seeded items from SQLite end to end (routes and a store module in the app package, one Jinja page)". :209 "- **Deliverables:** add and check-off routes, the open → checked → archived transitions in the store, and the add form grouped by section". :226 "- **Deliverables:** barcode lookup against OpenFoodFacts with an offline manual fallback (new `pantry/lookup.py` client, a lookup route and UI field)". Add to the Build Chunks comment (:176-189): "`Deliverables:` states what the chunk delivers. Backtick a path only when that file existing is itself the requirement — every backticked path here is existence-checked, BLOCKING when missing."
- model_dependent: no
- machine_read: yes (backticked paths in chunk list items feed the ref-drift check in `lib/buildplan_refs.py`; the `new` prefix is parsed)

### B-19: Artifact phases with a self-review between each
- location: `plugin/methodology/planning.md:36-43`
- evidence: "Between phases, review what you've produced through the review perspectives (Product, Design, Architecture, Skeptic, Testing)."
- pattern: Opus 5 row "Over-verification"; #341 binding method (Phase A-D choreography)
- why: A dependency order needs one sentence. The five-perspective self-review at each of four phase boundaries is verification scaffolding for the builder, and the independent Critic already does the review.
- confidence: medium
- action: rewrite
- replacement: "Generate in dependency order — the cost of fixing a spec error scales with how many downstream artifacts have incorporated it: the Product Brief first (everything references it), the Data Model and Non-Functional Requirements next, the Build Plan last (it depends on all of them)."
- model_dependent: yes
- machine_read: no

### B-20: Prawduct-internal surfaces listed in a product-facing guide
- location: `plugin/methodology/planning.md:108`
- evidence: "product CLAUDE.md, the Critic and PR protocols, methodology guides, the template, their guarding tests"
- pattern: 1d patch accretion and 2 recency trap (a framework-repo lesson written into every product's planning guide)
- why: Product repos have no Critic protocols, methodology guides or token-budget tests. The general half ("list the surfaces a project-wide concept cascades to") is useful everywhere. The named list is prawduct's own.
- confidence: medium
- action: rewrite
- replacement: "**Enumerate the surfaces when a chunk introduces a project-wide concept.** A new convention, config key or shared type cascades across files; list them up front in the chunk description, so the count shows the chunk's true size (split it if it is too large for one Critic pass)." The prawduct-specific list (Critic and PR protocols, methodology guides, the template, budget-guardrail tests) moves to this repo's `.claude/rules/learnings/` area file for `plugin/`.
- model_dependent: no
- machine_read: no

### B-21: Wave 3 domain-concern table in discovery
- location: `plugin/methodology/discovery.md:121-132`
- evidence: "Running them is the floor — the part a hardcoded list was standing in for"
- pattern: backlog #299 Wave 3 scaffolding; 1c "Example over-indexing" and prohibition-style floors; #342 duplicate of the characteristic "Implications" at :11-21
- why: Line 119 says "don't rely on hardcoded question lists — your domain knowledge is the source", and the table then supplies one as a mandatory floor. Its rows restate the Implications already given for each characteristic at :11-21. Opus 5.5 raises these questions natively. The table is a weaker-model aid.
- confidence: medium
- action: rewrite
- replacement: Delete :121-132 and append to :119: "Each characteristic's *Implications* above is where the sweep starts, not where it ends — a marketplace, a data pipeline and a healthcare app each have critical questions no general list names, and finding those is the expertise the user came for (Principle 7)."
- model_dependent: yes
- machine_read: no (`tests/test_v5_methodology.py:5967-5968` pins "property-based" and "test-specifications" at :119, which is unchanged)
- dup_of: plugin/methodology/discovery.md:11-21

### B-22: Numeric question and search quotas
- location: `plugin/methodology/discovery.md:29-35`
- evidence: "(family utility, personal tool, 1-3 users): 5-8 questions, 1-2 rounds. Infer aggressively."
- pattern: 1f numeric output ceilings; 1c strategy coaching
- why: The file itself calls these "not a quota … always governed by the pacing judgment", which is an escape hatch attached to a number. The same applies to "Low: 1-2 quick searches. Medium: 2-3 … High: 3-5" at :142. Opus 5.5 calibrates depth from the stated risk. The numbers anchor it.
- confidence: medium
- action: rewrite
- replacement: :29 "After detecting structural characteristics, assess risk; risk drives how much discovery you do, always under the pacing judgment in "Read the room on pacing" below:". :31 "**Low risk** (family utility, personal tool, 1-3 users): a round or two. Infer aggressively. Move fast." :33 "**Medium risk** (team tool, small marketplace, modest user base): confirm key assumptions; cover structural implications." :35 "**High risk** (financial data, health records, large user base, regulatory): deep exploration over several rounds. Surface regulatory concerns. Challenge assumptions explicitly." :142 "**Scale search depth to risk** — at high risk, include standards and cautionary tales."
- model_dependent: yes
- machine_read: no

### B-23: Wave 3 root-cause stopping rule
- location: `plugin/methodology/reflection.md:37-39`
- evidence: "**The stopping rule, stated so it survives being applied in a hurry.**"
- pattern: backlog #299 Wave 3 scaffolding; 1c padding; 1a (rules restated for emphasis, "Two of three is not a stop")
- why: The criterion is worth keeping. The meta-framing and the restatement for emphasis are scaffolding: "stated so it survives being applied in a hurry", "Two of three is not a stop", "Three whys is typical, and the chain is short by default because most chains are". One sentence carries it for Opus 5.5.
- confidence: medium
- action: rewrite
- replacement: "**Where to stop.** At the shallowest cause you can change here that would have prevented this instance *and* instances that don't look like this one. A cause you can only report becomes a learning or a backlog item, and the fix goes to the deepest cause you can change. A terminal that restates the failure — "the model made a mistake", "we were in a hurry", "nobody reviewed it" — is not a cause."
- model_dependent: yes
- machine_read: no

### B-24: Post-Fix Reflection restates Step 3 and widens scope
- location: `plugin/methodology/reflection.md:95-103`
- evidence: "4. **Meta-check**: could the same root cause manifest elsewhere? Fix those too."
- pattern: Opus 5 row "Task scope expansion"; #342 duplicate of Steps 3-4 (:31-48)
- why: Items 2, 3 and 5 restate Step 3 and Step 4. "Fix those too" invites fixes beyond the change's scope, which is the scope expansion that Opus 5 needs no push toward. Two points are unique and stay: classify first, and treat a reported cause as a hypothesis.
- confidence: medium
- action: rewrite
- replacement: "## Post-Fix Reflection\n\nWhen fixing a bug or recovering from an error, root-cause it (Step 3) before implementing. First classify it — product bug, or framework/methodology issue (those get deeper analysis) — and treat a reported cause as a hypothesis until you reproduce it against live data; the report's own evidence often carries the disproof. Where the same cause shows up elsewhere inside this change's scope, fix those instances too; file the rest. Capture it as Step 4 says."
- model_dependent: no
- machine_read: no
- dup_of: plugin/methodology/reflection.md:31-39

### B-25: Wave 3 "3-4 files is the dead zone" tie-break
- location: `plugin/methodology/building.md:37`
- evidence: "**3-4 files is the dead zone: medium if the change crosses a contract surface"
- pattern: backlog #299 Wave 3 scaffolding; 1a bold on a whole sentence
- why: The real classifier is the risk property (contract surface, new dependency, state outliving the process), not the file count. Stating it first removes the need for a count-based tie-break. The whole-sentence bold is emphasis doing the work of caps.
- confidence: medium
- action: rewrite
- replacement: "Classification heuristic: file count is a proxy for risk. 1-2 files = trivial/small; 5+ files = medium; new directory structure or API surface = large. Whatever the count, a change that crosses a contract surface, adds a dependency, or touches state outliving the process is at least medium."
- model_dependent: yes
- machine_read: no

### B-26: Wave 3 red-baseline protocol, which conflicts with "no pre-existing exception"
- location: `plugin/methodology/building.md:68-72`
- evidence: "*A red baseline is diagnosed before it is fixed*: re-run the failure on a clean checkout of the base commit."
- pattern: backlog #299 Wave 3 scaffolding (prescribed method); guide keep list 8, exception clause (two statements that disagree)
- why: The method (clean checkout of the base) is one way to answer "did my work cause this?", and Opus 5.5 can choose its own. As written, line 68 says "not yours; record it", while line 72 says "There is no "pre-existing" exception". A reader gets two rules. The replacement keeps both commitments and says how they fit.
- confidence: medium
- action: rewrite
- replacement: :68 "- *A red baseline*: establish whether your work caused it before fixing it. If it predates your work, record it (`test-evidence record --degraded`) and name it in the handoff rather than folding a fix into your diff; if your work caused it, fix it first." :72 "There is no "pre-existing" exception: every session starts clean. Recording a predated failure is its disposition, not an exemption. The obligation to FIX is bounded to BLOCKING — below it, a recorded accept discharges it in full."
- model_dependent: yes
- machine_read: yes (`tests/test_v5_methodology.py:2738` pins the sentence 'There is no "pre-existing" exception: every session starts clean.', which is kept verbatim; also :2724-2735 pin "`test-status` current is the baseline" and "one run of the declared suite", which are untouched)

### B-27: Bold used as emphasis across building.md
- location: `plugin/methodology/building.md:7-233`
- evidence: "record the declared suite **once**, at the boundary run — **not** after committing"
- pattern: 1a pressure language (bold standing in for caps); prawduct pattern "emphasis in bold rather than caps"
- why: The file has 128 bold spans in about 3,900 words. When most sentences carry bold, the markers stop carrying information, and the prompt reads as anxious. Keep bold only on run-in paragraph labels and on defined terms in the Size, Type and major-decision lists. Drop it everywhere else. That takes the count to roughly 60.
- confidence: medium
- action: rewrite
- replacement: Approach, not one hunk. Examples: :96 "record the declared suite once, at the boundary run — not after committing"; :92 "Suite totals are the common case: the evidence store holds pass/fail per tree, so say "suite green" and cite `test-status`; never copy a total into a record or add a field for one."; :201 "but read the reviewed files, never edit them" (or take B-1's text). Leave :107's "Disposition them ALL in ONE pass …" as is: it mirrors the runtime `_BATCH_FIX_DIRECTIVE` and carries its reason.
- model_dependent: no
- machine_read: yes (:107 is pinned by `tests/test_v5_methodology.py:2145` and `tests/test_critic_consolidate.py:1939`; excluded above)

### B-28: Bold used as emphasis across planning.md
- location: `plugin/methodology/planning.md:5-238`
- evidence: "**Several plans may declare one branch, and that is ordinary**"
- pattern: 1a pressure language (bold)
- why: Same as B-27, with 107 bold spans in about 4,500 words. Examples of mid-sentence emphasis that can go: :63 "**This is the one place the precedence is written; every other surface points here.**"; :67 "**On gitflow**", "**cleared**"; :114 "**Record the decision either way**"; :194 "**The only Type that bypasses Critic enforcement entirely — use deliberately.**"
- confidence: medium
- action: rewrite
- replacement: Same approach as B-27. Keep bold on run-in labels and on field names or defined terms; drop it inside sentences. Do not touch lines that open with a field marker (:204 explains why a line-leading `**Type:**` declares a type).
- model_dependent: no
- machine_read: yes (field markers such as `**Type:**` and `**Foreign API:**` are parsed; leave every `**Field:**` form alone)

### B-29: The Direction comment is copied into seven templates
- location: `plugin/templates/data-model.md:20-29`
- evidence: "a bare `## Direction` heading reads as ratified norms to the advisory probes"
- pattern: #342 duplicated facts; guide 1c padding ("Don't restate the rules here" while restating them)
- why: The same 105-word comment appears in data-model, security-model, nonfunctional-requirements, operational-spec, architecture, api-contract and observability-strategy, and ends up in every product artifact. Only two facts in it are needed at the point of authoring: where the anatomy lives, and the bare-heading hazard.
- confidence: medium
- action: rewrite
- replacement: In all seven: "`<!-- OPTIONAL norm home. To record a norm, add a ## Direction heading with entries (a bold **Statement.**, then Why:, Status:, optional Retroactivity: / Rulings:) — anatomy and rules: /prawduct:methodology norms. Add the heading only with a real entry: the advisory probes read a bare ## Direction heading as ratified norms. With no norms, leave this comment; "none to ratify" is recorded through /prawduct:doctor, not here. -->`"
- model_dependent: no
- machine_read: no (no test pins the comment text; `lib/norm_probes.py` reads real headings, and the comment keeps `## Direction` inside a comment)
- dup_of: plugin/templates/security-model.md:22-31

### B-30: build-plan.md frontmatter and Status comments carry design rationale
- location: `plugin/templates/build-plan.md:15-85`
- evidence: "# END OF LIFE — written by `prawduct-hook archive-plan`, not by hand. A plan is"
- pattern: Group 2 "Verbose SKILL.md" (rationale restating planning.md, which the comment itself names as the one home); 1d migration-relative ("the scalar keeps working exactly as before")
- why: Each product plan starts with about 700 words of comment. They argue why `released_in:` is a permitted copy, how the precedence works, and when the advisory stays silent. The model needs the fields and one rule for each. The reasoning lives in planning.md.
- confidence: medium
- action: rewrite
- replacement: :15-30 "`# branch: the branch this plan governs — uncomment with your real branch (a placeholder names a branch no repo has). While it is checked out, governance resolves this plan ahead of active_build_plan; several plans may declare one branch (precedence: methodology/planning.md "Which plan is active is branch state").`". :55-85 "`# End of life — written by prawduct-hook archive-plan, never by hand; a plan is archived, not deleted:` / `#   lifecycle: completed | superseded · archived: YYYY-MM-DD · released_in: vX.Y.Z (not release:, which a release plan uses for the release it governs)` / `#   superseded_by: <what replaced it>   (superseded only)` / `#   unbuilt_at_archive: <unticked chunks>   (absent means clean)` / `#   maintained: false`". :112-129 (Status comment) "`Ticking the LAST box disarms the Stop hook's Critic gate, so review before you tick. A built-but-unticked chunk is caught by an advisory only if commit subjects name a numeric chunk id as (Chunk 02), right after the colon, or "close Chunk 02"; other positions read as a mention.`" Keep :104-111 as written.
- model_dependent: no
- machine_read: yes (keys `branch:`, `partition:`, `lifecycle:` and so on are parsed, and the comments are not; `tests/test_v5_methodology.py` pins "never merged or released" in the Status comment, which is kept)

### B-31: Migration-relative phrasing in planning.md
- location: `plugin/methodology/planning.md:61`
- evidence: "a plan declaring no `branch:` resolves by the scalar exactly as before."
- pattern: 1d "Migration-relative phrasing"
- why: "Exactly as before" describes a diff against a version of the guide the reader never saw.
- confidence: medium
- action: rewrite
- replacement: "Opt in per plan — a plan declaring no `branch:` resolves by the scalar."
- model_dependent: no
- machine_read: no

### B-32: Retired change-log keys described in the shipped template
- location: `plugin/templates/change-log.md:30-35`
- evidence: "Nothing else is read. `chunks=` and `status=` were retired along with the"
- pattern: 1d "Migration-relative phrasing"
- why: A new product's change log has never had these keys. Naming them as retired implies alternatives that don't exist for this reader.
- confidence: medium
- action: rewrite
- replacement: "`     Nothing else is read; any other key is inert. Which chunks an entry shipped belongs in the entry BODY, where release notes and readers find it — a deliverable omitted from the body ships invisibly. -->`"
- model_dependent: no
- machine_read: no (the `scope=` / `release=` documentation above is unchanged)

### B-33: Incident stories inside delegation considerations
- location: `plugin/methodology/delegation.md:34`
- evidence: "One governed repo paid to learn it — a 403 from a video host failed a gate"
- pattern: Group 2 "History narratives"
- why: The considerations are sound. The stories at :34 ("seven minutes later") and :42 ("measured in one governed repo, three whole-suite runs…") are archaeology. The mechanism clause in :42 is context and stays.
- confidence: medium
- action: rewrite
- replacement: :34 "A failure in a test that depends on an uncontrolled third party (a video host returning 403) says nothing about the delegate's change. Prawduct names the consideration; you decide what it means for your suite." :42 "- **The unattributable green.** *Tell:* you accepted a pass count without knowing what was collected, from a box running several agents. A test worker that dies under contention is typically not re-queued and does not fail the run, so the same tree can report different totals, all exiting 0. A green you cannot attribute to a known set of tests is not evidence — record it as one: `test-evidence record --degraded "<what did not report>"`, which the gates read as stale rather than as a pass."
- model_dependent: no
- machine_read: no

### B-34: The review-deadline paragraph restates a code constant and contradicts itself
- location: `plugin/methodology/session-hygiene.md:41`
- evidence: "so apply the constant's: below **5** recorded rounds for that row"
- pattern: #342 duplicated fact (prose copy of `MIN_PRICED_SAMPLE`); 1c padding
- why: The paragraph ends "Never write a constant here instead" after writing the constant 5. That copy drifts when `MIN_PRICED_SAMPLE` changes. The paragraph also runs to about 330 words to say: live review → `DO NOT CLEAR` → give elapsed, roster and expected-if-priceable.
- confidence: medium
- action: rewrite
- replacement: "**A live Critic review moves this verdict, not merely the copy.** `RUNNING` alongside `SAFE TO CLEAR` is emittable, and for work a clear leaves alone it is correct. A dispatched review is not that work: whether forked reviewers survive a clear is unverified, and a roster a clear leaves incomplete is recovered only by re-dispatching the whole round. So a live review is `DO NOT CLEAR`, and the copy owes a **deadline** — the person stepping away is asking *by when must I check back*. Give the elapsed time (from `.critic-active`'s `started_at`), the roster (the per-role started markers), and the expected total from `prawduct-hook review-stats` (the `critic` row for this mode in its `by role x model x mode` block; `by_role_model_mode` under `--json`) — but only when that row has at least `lib/telemetry.py`'s `MIN_PRICED_SAMPLE` recorded rounds, because `review-stats` applies no floor and the ledger is empty in every fresh clone. Below it, give elapsed and roster and say the expectation is unavailable. Never quote a fixed duration."
- model_dependent: no
- machine_read: yes (`tests/test_v5_methodology.py:2388-2405` pins "live review is `DO NOT CLEAR`", "deadline", "elapsed" and "roster"; :2415 pins "for work a clear leaves alone it is correct"; all are kept)

### B-35: session-hygiene's hard stop reads as "end the turn"
- location: `plugin/methodology/session-hygiene.md:57`
- evidence: "There you stop even with work in hand."
- pattern: Opus 5.5 early stop; prawduct pattern "early-stop invitations"
- why: At an unreviewed chunk boundary, the Stop hook's Critic gate would refuse a turn end anyway. The intent is "don't build further before the review", not "hand the turn back". As written, it gives Opus 5.5 a named reason to stop.
- confidence: medium
- action: rewrite
- replacement: "…a context replay into a cold cache. The one exception is a chunk boundary whose review has not run: run that review before starting more work."
- model_dependent: no
- machine_read: no

### B-36: A standalone self-verification step for artifacts
- location: `plugin/methodology/building.md:113`
- evidence: "**Verify artifacts are current.** Confirm artifacts reflect the code — the Critic checks bidirectional freshness."
- pattern: Opus 5 row "Over-verification" (delete separate verification steps); #342 duplicate of :86 "Update artifacts as you go"
- why: :86 already binds the behavior while building, and the sentence itself says the independent Critic checks freshness. A separate "confirm" step is re-check scaffolding.
- confidence: medium
- action: remove
- replacement: (delete)
- model_dependent: yes
- machine_read: no
- dup_of: plugin/methodology/building.md:86

### B-37: Caps-lock register in the runbook template
- location: `plugin/templates/runbook.md:30-107`
- evidence: "START SHORT. THIS TEMPLATE IS A MENU, NOT A FORM TO COMPLETE."
- pattern: 1a pressure language (caps density)
- why: The authoring comments put roughly 30 rules in caps: "EVERY OTHER SECTION IS A DECISION", "DELETE THE SECTION ENTIRELY", "NEVER HEDGE", "A STEP DOES NOT HAVE TO BE A COMMAND", "HELPFULNESS AT THE WRONG MOMENT", "BOTH READERS, ONE PAGE", and more. When all of them are loud, none stands out, and the model over-applies them. The rules are good. The register is the problem.
- confidence: medium
- action: rewrite
- replacement: Change caps to sentence case throughout the comments (:30-107, :143, :187-252, :263-295, :316, :355). Keep caps only on the `⚠️ IRREVERSIBLE` block heading at :361, which the runbook reader sees. Examples: "Start short: this template is a menu, not a form to complete."; "- Never hedge. "You may want to", "usually", "if appropriate" — each one is a missing branch…"; "Delete all of these comments in the finished runbook."
- model_dependent: no
- machine_read: no (no test reads runbook.md text; `tests/test_plugin_packaging.py:55` only checks that it ships)

### B-38: Evidence anecdotes in the runbook template
- location: `plugin/templates/runbook.md:424-428`
- evidence: "no runbook than to a good one: when surgical checklists were adopted"
- pattern: Group 2 "History narratives"; #342 duplicate (the evidence lives in docs/runbook-authoring.md, which the template's header names as the home for evidence)
- why: The template points to runbook-authoring.md for the "why" in every section. The hospital study at :424-428 and the military/S1000D citation at :172-173 duplicate that doc's evidence inside the blank.
- confidence: medium
- action: remove
- replacement: :424-428 becomes "`<!-- Re-verify after any change to the system this touches; a runbook that is never rehearsed is closer to no runbook than to a good one. -->`". Delete :171-173's second sentence ("This block is mandatory in military and S1000D…").
- model_dependent: no
- machine_read: no
- dup_of: plugin/docs/runbook-authoring.md:1196

### B-39: The API-versioning "dated deferral" rule is stated in four places
- location: `plugin/methodology/planning.md:29`
- evidence: "not silent defaults — a deferral must be dated with a revisit trigger."
- pattern: #342 duplicated facts
- why: The same rule (versioning, deprecation and error model are recorded decisions; a deferral is dated with a revisit trigger) is stated at planning.md:29, planning.md:218, discovery.md:15 and api-contract.md:22-27. The home should be planning.md § "Exposed API" (:218), where the decision is made. Keep the api-contract template copy, since that is where it is filled in.
- confidence: medium
- action: rewrite
- replacement: planning.md:29 becomes "- *Programmatic interface* (any surface others call — network service, library/SDK, on-device/platform, or CLI): API contract (template: `templates/api-contract.md`), whose versioning and error-model decisions are recorded as "Exposed API" below describes." discovery.md:15's sentence "Implications: an API contract … a deferral must be dated with a revisit trigger." becomes "Implications: an API contract with recorded versioning, deprecation and error-model decisions (`methodology/planning.md` "Exposed API")." Keep discovery.md:15's OWASP sentence.
- model_dependent: no
- machine_read: no
- dup_of: plugin/methodology/planning.md:218

### B-40: Product-feedback scanning in a guide every product reads
- location: `plugin/methodology/reflection.md:93`
- evidence: "**Product feedback review**: periodically scan product repos' `.claude/rules/learnings/` for methodology feedback"
- pattern: Group 2 recency trap / wrong audience; #342 duplicate
- why: A product session cannot scan other products' repos. Only prawduct's own sessions can, and prawduct's root CLAUDE.md "Review product feedback" row already routes this. In a product repo the sentence is an instruction it cannot carry out.
- confidence: medium
- action: remove
- replacement: "This produces change-log entries and may trigger methodology updates." (delete the rest of the paragraph)
- model_dependent: no
- machine_read: no
- dup_of: CLAUDE.md:23

### B-41: The three clarity questions appear in two guides
- location: `plugin/methodology/discovery.md:47-53`
- evidence: "**Feature-level discovery** is shorter. For each non-trivial new feature, answer three questions in one sentence each:"
- pattern: #342 duplicated facts
- why: This repeats building.md:41-47 ("Before You Build: Confidence Check"), and prawduct's root CLAUDE.md:31-33 repeats it again. building.md's copy fires on every non-trivial cycle and carries the three close-the-gap options, so it should be the home.
- confidence: low
- action: flag
- model_dependent: no
- machine_read: no
- dup_of: plugin/methodology/building.md:41-47

## Outside my slice

- plugin/skills/runbook/SKILL.md:143-148 repeats runbook.md:74-83's "whole sections will not apply" list almost word for word; one of the two should become a pointer.
- `_BATCH_FIX_DIRECTIVE` (lib/critic_consolidate.py) carries the same ALL/ONE caps as building.md:107, so the two need to change together if either does.
