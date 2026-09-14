# One Home Per Fact — Requirements

`status: draft · stage: requirements · added: 2026-09-14 · source: owner-initiated review of documentation drift in large governed products · related: [#629](https://github.com/brookstalley/prawduct/issues/629) (governance artifact lifecycle), MET-8K4R (constitutional vs. default norms)`

## Summary

Large prawduct-governed products end up writing the same fact in several places: a CLAUDE.md line, a learning, a preferences row, a build plan, a code comment. The copies drift apart, and agents build against whichever copy they found first. Prawduct makes this worse today, because its gates check that things were written and nothing checks that a fact was written once.

This doc proposes two things:

- **One canonical home per kind of information.** The home is decided by what would make the statement false.
- **Handoff before close.** Short-lived documents move their durable content to those homes before they close.

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

- **Every gate rewards writing.**
  - The reflection gate, persistence check, artifact freshness check and coverage stubs all check that something was written.
  - None of them rewards merging a duplicate or deleting stale content.
- **Principle 13 (Coherent Artifacts) depends on diligence.** It asks the builder to check whether other artifacts need updating whenever one changes. That works for five documents. It doesn't work for five hundred, because the number of pairs to check grows much faster than the number of documents.
- **Spec-class artifacts have to track code by hand.** The data model, API contract and architecture docs keep tracking the code manually after the code exists, and the Critic's freshness check grades them on how closely they restate it.
- **Coverage probes push toward more documents** regardless of how big the product is.
- **History stays searchable.** Archived plans, reflections and change-log archives all show up in search results, alongside the documents that are current.

## The rule

**Canonical home:** the place where a change would make the statement false.

| Kind of statement | What makes it false | So its home is |
|---|---|---|
| Behavior | A code change | Code and tests |
| Norm | A new decision | The norm record |
| History | Nothing | An append-only log, which is never read as current truth |
| Plan | The passage of time | A plan document, which must close |

**Tense:**

- Present-tense statements about the system belong only in code, tests, generated docs and coarse maps.
- Future tense belongs in plans and the backlog.
- Past tense belongs in git, the change log and reflections.

Anywhere else a fact appears, it must be a pointer to its home, not a second copy.

## Homes by kind

| Kind | Question it answers | Canonical home | Elsewhere, only as |
|---|---|---|---|
| **Behavior** | What does it do? | Code, pinned by tests | Generated reference; a coarse module-level map |
| **Contract** | What can callers rely on? | Types, schemas and boundary tests, with API docs generated from them | A pointer |
| **Local rationale** | Why is *this* like this? | A comment at the site | Nowhere |
| **Norm** | What must stay true, and why? | A test or lint when it can be checked mechanically, with the why in its docstring; otherwise a `## Direction` entry | A preferences-index row pointing at it |
| **Product intent** | Who is it for, and what's out of scope? | Product brief or requirements | A pointer |
| **Acceptance criteria** | How do we know it works? | The build-plan chunk before the build; the tests after | Nothing, since the chunk is archived |
| **Plan** | What's next, in what order? | Build plan or backlog item | Nothing, since it's archived when done |
| **Status** | Where are we? | Derived from git, the backlog and plan state | Never hand-written twice |
| **History** | What happened? | Commits, change log, reflections | Nothing an agent searches by default |
| **Lesson** | What went wrong last time? | `learnings.md`, temporarily | Moved to a norm, comment or methodology, then deleted |
| **Outside-system fact** | How does vendor X actually behave? | The adapter's docstring, plus a contract test | A pointer from learnings |
| **Procedure** | How do I run operation X? | A runbook that calls scripts for the mechanical steps | A pointer |
| **Agent instructions** | How do I work in this repo? | CLAUDE.md: commands and pointers | Nothing |

## Requirements

**R1 — Published map:** Prawduct must publish the kind-to-home map as methodology. Templates, the Critic and the janitor must use it to decide where content belongs.

**R2 — Authority moves to the code once it exists:** A spec-class artifact (data model, API contract, architecture) is canonical for *what the system is* only until the code it specifies exists.
- After that, it must keep only its `## Direction` norms, the rationale that code can't carry, and a map coarse enough that ordinary changes don't touch it. The alternative is to generate it from code.
- The Critic's freshness check must stop rewarding detailed restatement of code.

**R3 — Hand off before close:** A short-lived document must not close until its durable content has moved to its home. This covers build plans, backlog items, requirements drafts and learnings.
- Decisions move to Direction.
- Local rationale moves to comments at the site.
- Acceptance criteria move to tests.
- Outside-system facts move to the adapter that talks to that system.

The closed document must record where each item went. Closing with nothing to move is fine and should cost one line.

**R4 — Learnings are temporary:** A learning must either move to a permanent home or be deleted. Permanent homes are a test or lint, a Direction entry, a code comment or methodology.
- Learnings that go a long time without moving must be flagged.
- A learning that could be checked mechanically must be proposed as a test.
- `learnings-detail.md` must not repeat `learnings.md`.

**R5 — Pointers, not copies:** Governance docs must refer to other content by a stable name: a module or symbol, a test name, an item ID or an artifact section.
- Line numbers are acceptable only in history, pinned to a commit.
- Values that already live in a config file (versions, line lengths, ports) must be written as pointers to that file.
- References must be mechanically resolvable, and broken ones must be reported.

**R6 — Status is derived:** Work status (what's in progress, what shipped, which branch is active) must be derived from git, the backlog and plan state, not hand-written in more than one place. A plan's status line and its checkboxes must never disagree.

**R7 — History stays out of the way:** Archived plans, reflections and change-log archives must stay available but must not appear in an agent's default search results. Durable docs must not carry version-history headers or narrate how they got to their current form. The comment rule in `methodology/building.md` § The Build Cycle extends to every durable doc, prawduct's own included.

**R8 — Removal counts as work:** The janitor and the Critic must treat merging a duplicate or deleting stale content as findings with the same weight as missing content. When the same normative statement shows up in more than one of CLAUDE.md, learnings, preferences, Direction and comments, it must be flagged along with a proposed single home.

**R9 — Artifacts sized to the product:** A coverage nudge must be satisfiable with a one-line `(not relevant — reason)` stub. Templates must model the size and shape of artifact we actually want. The build-plan template is mostly explanatory comments today.

**R10 — Prawduct follows its own map:** Prawduct's repo is the first consumer.
- Principle 13 (Coherent Artifacts) must change from "check whether others need updating" to "don't create a second copy; when you find one, merge it into its home."
- Principle 3 (Living Documentation) must favor generating or removing descriptive docs over keeping them in sync by hand.

## Candidate mechanisms

These are inputs to the design phase, not decisions.

- **`archive-plan` requires a `promoted:` list.** The final Critic review flags an archived plan that still holds Direction-like content.
- **A `check-refs` hook command.** It resolves paths, symbols, markdown anchors, quoted marker strings and item IDs across governance docs, and sends an advisory for anything broken.
- **A plan-status probe.** It compares each plan's status line with its checkbox counts, and flags plans marked shipped that are still in the live directory.
- **A janitor "one home" theme.** It looks for:
  - near-duplicate normative sentences across files;
  - present-tense system descriptions inside plans, learnings and backlog items;
  - history narration in durable docs.
- **A learnings age advisory**, plus a flag on learnings phrased as always/never rules, since those are usually tests waiting to be written.
- **Generated descriptive sections** for data models and API contracts, wherever the product's tooling can produce them.
- **An ignore file for archive directories**, pending open question 1.

## Out of scope

- **Deleting archived plans.** #629 ruled "archive, never delete." R7 keeps archives and only takes them out of default search.
- **New file classes, norm IDs or schemas.** `docs/norms.md` rules those out, and none are needed here.
- **Cleaning up existing products.** This doc defines the target. Migrating discodon and the rest of the fleet gets its own plan once the map settles.
- **User-facing product docs.** READMEs and user guides only need to follow the tense rule.

## Open questions

1. **Does Claude Code's search skip files listed in `.ignore` or `.rgignore`?** That covers Grep and subagent searches. If it does, R7 is a small per-repo ignore file. If not, archives may need to live outside the working tree, or only in git history. *Recommendation:* verify this first, because it decides how R7 is built.
2. **How coarse is "coarse enough" for the map R2 leaves behind?** *Recommendation:* component level. Nothing in the map should name a function, field or flag.
3. **Where does an outside-system fact live when several modules call that system directly?** *Recommendation:* the lowest module they share. If there isn't one, create the adapter.
4. **Should the handoff in R3 block archiving or only warn?** *Recommendation:* block on the explicit `archive-plan` route and warn in the automatic sweep. That matches how the two routes already split on incomplete plans.
5. **Should constitutional rules follow R5 too?** MET-8K4R proposes that a constitutional rule is written once in the plugin and cited everywhere else. *Recommendation:* yes. Treat the plugin as the home for constitutional rules, under the same pointer rules as everything else.
