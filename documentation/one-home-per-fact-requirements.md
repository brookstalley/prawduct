# One Home Per Fact — Requirements

`status: draft · stage: requirements · added: 2026-09-14 · source: owner-initiated review of documentation drift in large governed products · related: [#629](https://github.com/brookstalley/prawduct/issues/629) (governance artifact lifecycle), MET-8K4R (constitutional vs. default norms)`

## Summary

Large prawduct-governed products end up writing the same fact in several places: a CLAUDE.md line, a learning, a preferences row, a build plan, a code comment. The copies drift apart, and agents build against whichever copy they found first. Prawduct makes this worse today, because its gates check that things were written and nothing checks that a fact was written once.

This doc proposes three things:

- **One canonical home per kind of information.** The home is decided by what would make the statement false.
- **Home before writing.** An agent names a statement's home before it writes the statement, and writes it there or nowhere.
- **Handoff before close.** Short-lived documents move their durable content to those homes before they close.

It also sets the constraints for moving existing repos onto the rule.

## Problem

### What the drift looks like

These examples come from discodon, measured 2026-09-14. They're a snapshot: re-derive the numbers before citing them anywhere.

- **Plans that shipped still read as future work.**
  - `build-plan-prompt-externalization.md` says PLANNED with no boxes ticked, but the work shipped in `5e823d1e4`.
  - `build-plan-event-loop-unblock.md` says in progress, but `services/em/` has no sync `to_db(` calls left.
- **Durable design lives only in a plan.** The yugabyte backend plan holds the table-per-container schema and the row-level security (RLS) isolation design. `architecture.md` never mentions RLS.
- **Restated facts go stale one copy at a time.**
  - Ruff's line length is written in six places, one of which is `pyproject.toml`.
  - Cosmos was removed, but `project-state.yaml`, a comment in `research_tool.py` and a live learning still describe it.
- **Content lands in the wrong file.**
  - The top of `learnings.md` holds a norm ruling.
  - Several learnings restate code that sits right next to them.
  - `project-state.yaml` carries a dated log that grew back ten days after someone deleted it.
  - About half of `learnings.md` is repeated word for word in `learnings-detail.md`.

Prawduct's own repo shows the same pattern:

- **Old designs stay live.** The `work-model-*` docs are mostly marked HISTORICAL but still sit in `documentation/`.
- **Backlog items do other documents' jobs.** They carry rulings, design risks and `path:line` references.
- **History sits at the top of a requirements doc.** One requirements doc opens with its own version history.

This matters most for agents. An agent that greps for a module name and finds a shipped plan describing the old design will build the old design, confidently.

### Why prawduct makes it worse

- **Checks reward writing, and nothing rewards consolidating.**
  - The reflection gate blocks session end until a reflection is captured.
  - The Critic's drift check (`skills/critic/review-protocol.md` § Everything Is Coherent) grades a description that no longer matches the code as a WARNING. The cheapest fix is to update the copy, which keeps the copy alive.
  - The janitor's Artifact Fitness theme does look for redundant documentation, but only a human can start the janitor.
- **Principle 13 (Coherent Artifacts) depends on diligence.** It asks the builder to check whether other artifacts need updating whenever one changes. That works for five documents. It doesn't work for five hundred, because the number of pairs to check grows much faster than the number of documents.
- **Spec-class artifacts have to track code by hand.** The data model, API contract and architecture docs keep tracking the code manually after the code exists. "Artifact freshness" is a named review emphasis for feature work in `methodology/building.md`, and it reads as "keep the restatement current."
- **Templates model large artifacts.** A coverage probe accepts a one-line stub, but a new artifact starts from its template, and the build-plan template is mostly explanatory comments.
- **History stays searchable.** Archived plans, reflections and change-log archives all show up in search results, alongside the documents that are current.

## The rule

**Canonical home:** the place where a change would make the statement false.

| Kind of statement | What makes it false | So its home is |
|---|---|---|
| Behavior | A code change | Code and tests |
| Norm or decision | A new decision | The norm or decision record |
| History | Nothing | An append-only log, which is never read as current truth |
| Plan | The passage of time | A plan document, which must close |

**Tense:**

- Present-tense statements about the system belong only in code, tests, generated docs and coarse maps.
- Future tense belongs in plans and the backlog.
- Past tense belongs in git, the change log and reflections.

Anywhere else a fact appears, it must be a pointer to its home, not a second copy.

**A statement that fits two kinds gets split.** "Tenants are isolated with row-level security, because a shared schema was cheaper than a database per tenant" is a decision (RLS over the alternatives, and why) and a norm (isolation must stay on). The decision goes in the decision record, the norm goes in Direction with its why pointing at the decision, and the policies themselves are behavior in code.

## Homes by kind

| Kind | Question it answers | Canonical home | Elsewhere, only as |
|---|---|---|---|
| **Behavior** | What does it do? | Code, pinned by tests | Generated reference; a component-level map (R2) |
| **Contract** | What can callers rely on? | Types, schemas and boundary tests. API docs are generated from them where the tooling allows; otherwise the types and schemas are the reference | A pointer |
| **Local rationale** | Why is *this* like this? | A comment at the site | Nowhere |
| **Design decision** | Why is the system shaped this way across modules? | `technical_decisions` or `design_decisions` in `project-state.yaml`: the decision, its rationale, the alternatives | A pointer from the spec artifact's map; the why of any Direction entry the decision produces |
| **Norm** | What must stay true, and why? | A test or lint when it checks the whole rule, with the why in its docstring. Otherwise a `## Direction` entry, naming any test that checks part of the rule as its mechanism | A preferences-index row pointing at it |
| **Configured value** | What is it set to? | The config file that sets it | A pointer naming the file and key |
| **Product intent** | Who is it for, and what's out of scope? | Product brief or requirements | A pointer |
| **Acceptance criteria** | How do we know it works? | The build-plan chunk before the build; the tests after | Nothing, since the chunk is archived |
| **Plan** | What's next, in what order? | Build plan or backlog item | Nothing, since it's archived when done |
| **Open question** | What haven't we decided? | The document that needs the answer; `open_questions` in `project-state.yaml` when no document owns it yet | Nothing, since it closes by becoming a decision |
| **Status** | Where are we? | A plan's checkboxes, written by the session that did the work. Everything else is derived from them, git and the backlog | Never hand-written a second time |
| **History** | What happened? | Commits, change log, reflections | Nothing an agent searches by default |
| **Research** | What are the options outside the system? | A research doc, which becomes history once the decision is recorded | A citation from the decision's rationale |
| **Lesson** | What went wrong last time? | `learnings.md`, temporarily. Its `learnings-detail.md` narrative extends the entry and never repeats it | Moved to a permanent home, then retired to `learnings-history.md` |
| **Outside-system fact** | How does vendor X actually behave? | The adapter's docstring, plus a contract test | A pointer from learnings |
| **Procedure** | How do I run operation X? | A runbook that calls scripts for the mechanical steps | A pointer |
| **Agent instructions** | How do I work in this repo? | CLAUDE.md: commands and pointers | Nothing |

## Requirements

**R1 — Published map:** Prawduct must publish the kind-to-home map as methodology. Templates, the Critic and the janitor must use it to decide where content belongs.

**R2 — Authority moves to the code once it exists:** A spec-class artifact (data model, API contract, architecture) is canonical for *what the system is* only until the code it specifies exists.
- After that, it must keep only its `## Direction` norms, pointers to the design decisions behind it, and a component-level map. Nothing in the map names a function, field or flag. The alternative is to generate it from code.
- When the Critic's drift check finds a description that no longer matches the code, the fix it asks for must be to cut the description down to the map or generate it, not to update the copy.
- The "artifact freshness" emphasis in `methodology/building.md` must say the same.

**R3 — Hand off before close:** A short-lived document must not close until its durable content has moved to its home. This covers build plans, backlog items, requirements drafts and learnings.
- Decisions move to the decision record, and the norms they produce move to Direction.
- Local rationale moves to comments at the site.
- Acceptance criteria move to tests.
- Outside-system facts move to the adapter that talks to that system.

The closed document must record where each item went. Closing with nothing to move is fine and should cost one line.

**R4 — Learnings are temporary:** A learning must move to a permanent home and then be retired. Permanent homes are a test or lint, a Direction entry, a code comment or methodology.
- Retirement moves the entry to `learnings-history.md`, the route `audit-learnings` uses. Nothing is deleted, and R7 keeps the history file out of default search.
- Learnings that go a long time without moving must be flagged. The age is a design decision.
- A learning phrased as an always or never rule must be proposed as a test.
- A `learnings-detail.md` narrative must extend its `learnings.md` entry, not repeat it. The pairing check must grade the body text, not just the headings.

**R5 — Pointers, not copies:** Governance docs must refer to other content by a stable name: a module or symbol, a test name, an item ID or an artifact section.
- Line numbers are acceptable only in history, pinned to a commit.
- Values that already live in a config file (versions, line lengths, ports) must be written as pointers to that file.
- References must be mechanically resolvable, and broken ones must be reported.

**R6 — Status is derived:** A plan's checkboxes are the only hand-written work status. Only the session with the work in context writes them, and no tool rewrites them, as #629 requires.
- Every other statement of status (a plan's status line, "in progress" in `project-state.yaml`, a backlog item saying a thing shipped) must be derived from the checkboxes, git and the backlog, or removed.
- When a status line disagrees with its checkboxes, the disagreement is reported for a person. Nothing rewrites the boxes to match.

**R7 — History stays out of the way:** Archived plans, reflections, `learnings-history.md` and change-log archives must stay available but must not appear in an agent's default search results.
- Default search means how agents actually search: the Grep and Glob tools, subagents, and plain `grep` and `find` run through Bash.
- Durable docs must not carry version-history headers or narrate how they got to their current form. The comment rule in `methodology/building.md` § The Build Cycle extends to every durable doc, prawduct's own included.

**R8 — Removal counts as work:** Merging a duplicate or deleting stale content must be a finding with the same weight as missing content.
- The Critic must carry this, because it reviews every change. The janitor's Artifact Fitness theme must give its redundant-documentation check the same weight, but it can't be the only place, because a human has to start it.
- When the same normative statement shows up in more than one of CLAUDE.md, learnings, preferences, Direction and comments, it must be flagged along with a proposed single home.

**R9 — Artifacts sized to the product:**
- A coverage nudge must stay satisfiable with a one-line `(not relevant — reason)` stub.
- Templates must model the size and shape of artifact we actually want. The build-plan template is mostly explanatory comments today.

**R10 — Prawduct follows its own map:** Prawduct's repo is the first consumer.
- Principle 13 (Coherent Artifacts) must replace "check whether others need updating" with "don't create a second copy; when you find one, merge it into its home." It must keep its rule against meaning that rides on an identifier that moves.
- Principle 13's "carry the *why* inline" must say where the line is: carry the reason for *this* code or *this* passage inline, and point at a fact that has a home somewhere else.
- Principle 3 (Living Documentation) must favor generating or removing descriptive docs over keeping them in sync by hand.

**R11 — Home before writing:** Before a builder adds a statement to any governance doc, it must name the statement's kind and home. If the home is code, a test or a config file, the statement goes there or nowhere.
- `methodology/building.md` § The Build Cycle must state this next to the comment rule, because that's where a builder is when it's about to write.
- A check that something was written, the reflection gate included, must accept a record of where the content went, or one line saying there was nothing new.

## Dependencies

- **R1 comes first.** Every other requirement points at the map.
- **R10 comes second.** Prawduct's principles and methodology are what agents read, so they have to follow the map before any product is asked to.
- **R11 comes before the detectors (R5, R7, R8).** Otherwise cleanup races new copies.
- **R2, R4 and R6 change mechanisms that pull the other way today**: the drift check's fix, the learnings pairing check, and status lines. The detectors would flag what those mechanisms keep producing, so these change before the detectors ship.
- **Migrating existing repos comes after prawduct's own repo is clean.**

## Success

- An agent that searches for a module name finds current material. Archived plans, retired learnings and old designs don't come back from a default search.
- No live plan reads as in progress for work that shipped, and no plan's status line disagrees with its checkboxes.
- A normative statement has one home. Every other mention is a pointer, and every pointer resolves.
- Every learning is either on its way to a permanent home or flagged. No `learnings-detail.md` narrative repeats its index entry.
- The Critic gives an agent that deletes a duplicate the same credit as one that fills a gap.
- Measured on prawduct and discodon before and after migration, using the measures in *What the drift looks like*: shipped plans still live, restated config values, normative statements with more than one home, and learnings repeated between files. Each goes down, and a check keeps it down.

## Migrating existing repos

Every repo that has this problem is already onboarded, so a rule that only reaches newly onboarded repos misses all of them. Each product's cleanup gets its own plan, but these constraints bind the design:

**M1 — Ratchet, don't flood:** New violations are flagged when they're written. Existing ones are inventoried once per repo and worked down in batches the owner sizes. A repo's first session after the upgrade must not surface one advisory per violation.

**M2 — In-flight plans are grandfathered:** R3's handoff blocks archiving only for plans created after the rule ships. Older plans get a warning.

**M3 — The owner approves each spec cut:** Cutting an existing architecture, data-model or API-contract doc down to its map (R2) deletes content. Each cut is proposed as its own diff and the owner takes or rejects it. This differs from the single confirmation `security-model.md` § Direction asks for on file operations, because each cut is a judgment about what the content was worth, not a move version control can undo without reading it.

**M4 — Legacy learnings content has a disposition:** A `learnings-detail.md` narrative that repeats its index entry is cut to what it adds. A legacy historical section in `learnings-detail.md` moves to `learnings-history.md` by the existing `audit-learnings --apply` route.

**M5 — Delivered through doctor and advisories:** The upgrade reaches an existing repo as a post-sync advisory pointing at a `/prawduct:doctor` flow. For file moves and mechanical edits, the flow shows the complete dry run and takes one confirmation, the way the Lifecycle Convergence Flow does.

**M6 — Prawduct first, then discodon:** Prawduct migrates first, under R10. Discodon follows, measured before and after against *Success*.

## Candidate mechanisms

These are inputs to the design phase, not decisions. Where a check already exists, extend it rather than adding a second one.

- **`archive-plan` requires a `promoted:` list.** The final Critic review flags an archived plan that still holds Direction-like content.
- **Reference resolution, extending the `chunk-ref-missing` check** from build-plan chunks to all governance docs. It resolves paths, symbols, markdown anchors, quoted marker strings and item IDs, and sends an advisory for anything broken.
- **A status-line check beside Health Check #16.** It compares each plan's status line with its checkboxes, flags plans marked shipped that are still in the live directory, and reports only, as #16 does.
- **One-home checks in the Critic's drift check and the janitor's Artifact Fitness theme.** They look for:
  - near-duplicate normative sentences across files;
  - present-tense system descriptions inside plans, learnings and backlog items;
  - history narration in durable docs.
- **A learnings age flag in `audit-learnings`' stale candidates**, plus a flag on learnings phrased as always or never rules, since those are usually tests waiting to be written.
- **A body-text grade in the learnings pairing check** for narratives that repeat their index entry.
- **Generated descriptive sections** for data models and API contracts, wherever the product's tooling can produce them.
- **An ignore file for archive directories**, pending open question 1.

## Out of scope

- **Deleting archived plans.** #629 ruled "archive, never delete." R7 keeps archives and only takes them out of default search.
- **New file classes, norm IDs or schemas.** `docs/norms.md` rules those out, and none are needed here.
- **Each product's cleanup.** This doc sets the target and the migration constraints. Each product's cleanup is its own plan.
- **User-facing product docs.** READMEs and user guides only need to follow the tense rule.

## Open questions

1. **Do agents' searches skip files listed in `.ignore` or `.rgignore`?** ripgrep does: in a local test with ripgrep 15.2, a directory listed in `.ignore` dropped out of its results. Plain `grep -r` doesn't read the file. Claude Code's Grep and Glob tools are untested. *Recommendation:* test Grep, Glob and a subagent's Bash search before designing R7. If agents regularly fall back to `grep` or `find`, an ignore file hides archives from some searches and not others, and archives may need to live outside the working tree or only in git history.
2. **Where does an outside-system fact live when several modules call that system directly?** *Recommendation:* the lowest module they share. If there isn't one, create the adapter.
3. **Should the handoff in R3 block archiving or only warn?** *Recommendation:* block on the explicit `archive-plan` route and warn in the automatic sweep. That matches how the two routes already split on incomplete plans.
4. **Should constitutional rules follow R5 too?** MET-8K4R proposes that a constitutional rule is written once in the plugin and cited everywhere else. *Recommendation:* yes. Treat the plugin as the home for constitutional rules, under the same pointer rules as everything else.
