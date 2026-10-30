# Prawduct

Prawduct is a [Claude Code](https://docs.anthropic.com/en/docs/claude-code) plugin that makes
Claude work out what to build before it builds it, has an independent agent review the work, and
keeps a record of lessons learned in each repo.

Going from "I need an app that does X" straight to code skips the hard questions: who the users
are, what the edge cases are, what "done" looks like, and what needs testing. Claude Code writes
good code, but left alone it guesses at product intent, drifts from requirements, weakens tests
to get them passing, and piles up technical debt without telling you. Prawduct adds the
discipline, and enforces the parts that matter with hooks instead of instructions.

## Install

You need:

- Claude Code
- git
- Python 3.14 or newer, as `python3.14` or `python3`, on every machine that opens a governed
  repo, even if the repo isn't a Python project. The hooks are Python with no dependencies.
  Without it, governance is off and the session tells you so.

1. Install the plugin once per machine:

   ```bash
   claude plugin marketplace add brookstalley/prawduct
   claude plugin install prawduct@prawduct
   ```

2. Onboard each repo you want governed, new or existing:

   ```bash
   cd ~/my-repo          # new repo? `git init` first
   claude
   > /prawduct:onboard .
   ```

3. Describe what you want:

   ```
   > build a meal-planning app for families with dietary restrictions
   > add OAuth login to the existing API
   ```

Onboarding commits your project's state in `.prawduct/`, a short governance block in
`AGENTS.md`, and an install reference in `.claude/settings.json`. No framework files go in your
repo. Updates come through the marketplace with no repo diff, and the session banner says what
changed.

**Every contributor installs the plugin once.** Claude Code doesn't auto-install a plugin named in
a repo's settings, so a clone on a machine without prawduct runs ungoverned. The `AGENTS.md` block
tells Claude to say so and give the install command.

Other commands you may need:

- `/prawduct:doctor` health-checks an onboarded repo and gives the fix for each problem.
- `/prawduct:repo-disable` turns prawduct off in one repo, for the whole team or just you. To turn
  it back on, set `"prawduct@prawduct": true` under `enabledPlugins` in the settings file it
  wrote, or use Claude Code's `/plugin` menu.
- Repos from before 2.0, which committed framework files, move to the plugin with
  `/prawduct:migrate` ([MIGRATION](documentation/MIGRATION.md)). `/prawduct:onboard` routes you
  there.

## How it works

Each piece of work goes through discovery, planning, building, review, and reflection. How much of
each depends on its size and risk: a family utility gets a few questions and light review; a
platform handling health data gets far more of both.

- **Discovery** asks about users, workflows, edge cases, security, and scope, starting with the
  questions that would change the most. New features get their own discovery.
- **Planning** writes specs in dependency order (product brief, data model, security model, test
  specs, non-functional requirements) and a build plan split into chunks.
- **Building** implements one chunk at a time, writing tests alongside the code.
- **The Critic** reviews each chunk as a separate agent. It sees the code, tests, and specs but
  not the builder's reasoning, and it can't run tests or builds; it reads the test results the
  builder recorded.
- **Reflection** happens after each chunk, fix, or judgment call: what was expected, what
  happened, and why. Lessons worth keeping become one-line rules in `.claude/rules/learnings/`,
  which Claude Code loads on its own.

Telling an LLM to "always do X" works until the context gets large, gets compacted, or the model
decides the task is too small to bother. So hooks enforce the parts that matter:

- At session start, a briefing covers project state, stale artifacts, work in progress, and what
  changed in the plugin.
- At the end of a turn, the Stop hook blocks if code was built against a plan with no Critic
  review, or code changed with no reflection.
- `/prawduct:pr` runs an independent release-readiness review before a PR goes up.
- `/prawduct:janitor` catches the slow drift no single review sees: stale docs and tests, code on
  old patterns, dead branches.

The principles behind all of this are in [`plugin/docs/principles.md`](plugin/docs/principles.md),
and the methodology guides are in [`plugin/methodology/`](plugin/methodology/).

## Q&A

**Doesn't this use a lot of tokens?**

Yes, yes it does. But it uses fewer than going back and reworking an app over and over. Clear
scope, good requirements, test coverage, and consistent architecture take a lot of thought, for a
human or a machine. The only thing more expensive is *not* doing that stuff.

**What languages does it work with?**

Anything Claude Code can write. Prawduct has no language-specific instructions or code. You'll get
better results in the languages Claude is better at, of course.

**How much control do I have over product and tech choices?**

As much or as little as you want. Prawduct infers where you have opinions and where you don't,
and honors any preference you state (a language, a color scheme, a logging provider). Preferences
live in `.prawduct/artifacts/project-preferences.md`, which you can edit directly.

**How do I remove it from a project?**

1. Delete `.prawduct/` and `.claude/rules/learnings/`.
2. In `.claude/settings.json`, remove `extraKnownMarketplaces.prawduct`, the `prawduct@prawduct`
   entry under `enabledPlugins`, and prawduct's SessionStart hook.
3. Remove the `PRAWDUCT:ANCHOR` block from `AGENTS.md`, and the `@AGENTS.md` line from
   `CLAUDE.md` if nothing else needs it. Repos onboarded before the move to `AGENTS.md` have the
   block in `CLAUDE.md` instead.

## Developing prawduct

This repo is governed by its own plugin. Run Claude against the checkout:

```bash
claude --plugin-dir ./plugin --add-dir .
```

Only `plugin/` ships to users; everything else is prawduct's own development state.

- [Project structure](documentation/project-structure.md): both this repo and a governed product repo
- [Running tests](documentation/running-tests.md)
- [Scenario tests](tests/scenarios/README.md): end-to-end evaluations against scripted users
- [Release process](documentation/release-process.md)
- [Changelog](plugin/CHANGELOG.md)

## License

MIT — see [LICENSE](LICENSE).
