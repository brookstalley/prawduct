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
- **Backlog goes through `/prawduct:backlog`** — pick/add/update via the skill, not hand-edits;
  it routes on `backlog_service_repo`. "Done" = `update status=shipped` (markdown backend: moves
  to `## Archive`, never strikethrough; Issues backend: closes the issue). An early-`stage:`
  item is an undocumented requirement — `pick` routes it to discovery.
- **Feature-branch medium+ work.** Don't create PRs unless asked — then use `/prawduct:pr`.
- **Forward notes go in `.prawduct/.handoff-notes.md`** — yours to write (as is
  `.session-reflected`), at chunk close ("nothing beyond the plan" if true, but write the line, not no file).
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
