This repo is governed by **Prawduct** — and it IS the Prawduct framework repo, so the
always-loaded CLAUDE.md already carries the principles roster, the Critic and PR review
mechanics, the Stop-hook enforcement model, commit conventions (no attribution trailers;
merge commits by default — squash only when configured or explicitly asked), and the
rigor-scaling model. This slim reminder carries only what CLAUDE.md does not
restate; product repos receive the full digest (`methodology/session-digest.md`) instead.

**Before writing ANY code against a build plan: STOP and read the build cycle via
`/prawduct:methodology building`.** Proceeding straight to code without it is the #1 governance failure.

## Hardest rules CLAUDE.md does not restate

- **Catch specific exceptions.** Waive a genuinely necessary broad catch with
  `# prawduct:allow prawduct/broad-except -- reason`; never swallow errors silently.
  (`prawduct:allow <scope>/<rule-id> -- reason` is the general pragma — `docs/waivers.md`.)
- **Upstream intake follows the product's recorded policy** — adding, bumping or vendoring
  upstream code, or editing an updater's config, in a manifest or not (this repo's own CI
  actions are the case in point). `docs/upstream-dependency-policy.md`.
- **Backlog goes through `/prawduct:backlog`** — pick/add/update via the skill, not hand-edits;
  it routes on `backlog_service_repo`. "Done" = `update status=shipped` (markdown backend: moves
  to `## Archive`, never strikethrough; Issues backend: closes the issue). An early-`stage:`
  item is an undocumented requirement — `pick` routes it to discovery.
- **Feature-branch medium+ work.** Don't create PRs unless asked — then use `/prawduct:pr`.
- **Forward notes go in `.prawduct/.handoff-notes.md`** — yours to write (as is
  `.session-reflected`), at chunk close ("nothing beyond the plan" if true, but write the line, not no file).
  **Never ask whether to prepare one — prepare it, then signal.**
- **Close with the standing block** — last, after every other word, on any turn that ends a chunk
  or work cycle *or* that you end with work outstanding. A `---` rule, then three
  **separate paragraphs**, labels backticked so they render as coloured tokens:
  `STATE` (done / blocked / waiting; committed or not; suite green or not) ·
  `NEXT` (the ONE next action and whose it is) ·
  `CLEAR` (*Safe to `/clear`.* — or — *Not safe to `/clear` yet: [what has to happen first]*).
  Omitting, burying, padding, and collapsing it onto one line fail identically — people read the
  bottom and nothing else, and three answers run together stop being separately findable. **Outstanding includes work in flight**: a dispatched review, a running PR reviewer
  or any unread background agent takes the second line — a coordinator Critic review hands your
  turn back *before* its three reviewers finish. Full rule: `/prawduct:methodology reflection`.
  **Read it before rewriting it; reconcile, never blind-append**: only `/clear` consumes that file, so a second batch finds the first's notes still there — drop what the work discharged, correct what moved, keep what still bites, and never stack a new section on top.
  `.session-handoff.md` is the machine's, regenerated at every `/clear`.
- **Norms bind; descriptions track** (`/prawduct:methodology norms`) — departures from Direction/preferences
  norms are recorded decisions (amend / ruling / exception), never doc-sync.

## How the agent shows up (stance)

**First duty on any substantive ask: the expert take — risks, the stronger/simpler
alternative, a recommendation — compliance second.** Then: **Verify, don't guess** ·
**Retrieval before generation** (the cheapest check that could change the decision comes
first — read the mechanism before tuning it, search before working around) ·
**Stress-test before agreeing** (name a weakness before endorsing) · Frame decisions as
options + tradeoffs + a recommendation · Plain language, full precision · Research
fast-moving / post-cutoff facts, don't recall them · Verify your own work before "done" ·
Do what was asked — no more · Label your confidence.

## Enforcement & on-demand guides

At session end the **Stop hook** runs the Critic gate + reflection gate (CLAUDE.md "The
Critic" has the mechanics; a block names its gate). Full guides on demand:
`/prawduct:methodology` (overview; pass a topic to open a guide —
`building | discovery | planning | reflection | principles | norms`) · `/prawduct:critic` ·
`/prawduct:pr` · `/prawduct:backlog` · `/prawduct:learnings` · `/prawduct:janitor` ·
`/prawduct:doctor` · `/prawduct:report-bug` (triage `incoming-bugs/` here — the receiving
end; products use it to file prawduct bugs upstream)
