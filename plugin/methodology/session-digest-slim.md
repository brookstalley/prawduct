This repo is governed by **Prawduct**, and it IS the Prawduct framework repo. The always-loaded
CLAUDE.md already carries the principles roster, the Critic and PR review mechanics, the
Stop-hook enforcement model, the commit conventions, and the rigor-scaling model. This slim
reminder carries only what CLAUDE.md does not restate. Product repos get the full digest
(`methodology/session-digest.md`) instead.

**Read the build cycle via `/prawduct:methodology building` before writing code against a build
plan.** Skipping it is the most common governance failure.

## Hardest rules CLAUDE.md does not restate

- **There is no "pre-existing" exception.** A problem you find — failing test, broad catch,
  stale artifact — is yours: fix it, or flag why it can't be fixed now.
- **Durable artifacts are self-contained.** A comment, docstring, or long-lived spec never
  anchors its meaning to an ephemeral build id (chunk, build-plan, work-cycle name) — carry the
  *why* inline. Exception: bookkeeping that records the work (change-log `chunks=`, `closed-by:`).
- **Catch specific exceptions.** Waive a genuinely necessary broad catch with
  `# prawduct:allow prawduct/broad-except -- reason`; never swallow errors silently.
  (`prawduct:allow <scope>/<rule-id> -- reason` is the general pragma — `docs/waivers.md`.)
- **Backlog goes through `/prawduct:backlog`** — pick/add/update via the skill, not hand-edits;
  it routes on `backlog_service_repo`. "Done" = `update status=shipped` (markdown backend: moves
  to `## Archive`, never strikethrough; Issues backend: closes the issue). An early-`stage:`
  item is an undocumented requirement — `pick` routes it to discovery.
- **Feature-branch medium+ work.** Don't create PRs unless asked — then use `/prawduct:pr`.
- **Norms bind; descriptions track** (`/prawduct:methodology norms`) — departures from Direction/preferences
  norms are recorded decisions (amend / ruling / exception), never doc-sync.

## How the agent shows up (stance)

**First duty on any substantive ask: the expert take — risks, the stronger or simpler
alternative, a recommendation — compliance second.** Then the checkable bars:

- **Verify, don't guess** — and when you report something works, show what showed it.
- **Retrieval before generation** — the cheapest check that could change the decision comes
  first: read the mechanism before tuning it, search before working around. Fast-moving and
  post-cutoff facts get looked up, never recalled.
- **Stress-test before agreeing** — name a weakness before endorsing.
- **Frame decisions** — options with tradeoffs, plus a recommendation.
- **Do what was asked — no more.** Documents too: cover the substance and stop.
- **Delegation has a floor** — a subagent must buy something, never work you can finish in a
  handful of tool calls. The Critic is exempt: independence, not thoroughness.
- **Plain language, full precision** · **Label your confidence.**

## Enforcement & on-demand guides

At session end the **Stop hook** runs the Critic gate + reflection gate (CLAUDE.md "The
Critic" has the mechanics; a block names its gate). Full guides on demand:
`/prawduct:methodology` (overview; pass a topic to open a guide —
`building | discovery | planning | reflection | principles | norms`) · `/prawduct:critic` ·
`/prawduct:pr` · `/prawduct:backlog` · `/prawduct:learnings` · `/prawduct:janitor` ·
`/prawduct:doctor` · `/prawduct:report-bug` (triage `incoming-bugs/` here — the receiving
end; products use it to file prawduct bugs upstream)
