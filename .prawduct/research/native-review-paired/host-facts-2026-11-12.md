# Native review host facts — measured 2026-11-12 (#1130 Chunk 0)

#1130 rests on two host facts the Claude Code documentation does not state: whether the native
`/code-review` can be started from inside a forked skill or a subagent, and what each level costs.
This records what one live session measured, on Claude Code 2.1.322, Opus 5.5 unless stated.

**Range:** `b738a332...0f305b2f` — PR #1158 (5 files, +212/−92), chosen because the Critic had
already reviewed it: 0 blocking, 0 warning, 1 observation.

**Re-derive the per-fork numbers** (wall clock, tokens, the recipe the fork ran):
`python3 -I .prawduct/research/native-review-paired/fork_costs.py <session-transcripts>/subagents`
— the transcripts stay on the measuring machine; the command, not a copied number, is the record.

## What was established

- **Launch sites.** The `Skill` tool reaches `code-review` from a general-purpose subagent, from a
  `context: fork` skill whose `allowed-tools` lists `Skill`, and from a subagent that such a fork
  dispatched. No route refused. A skill added mid-session is not loaded (`Unknown skill`), so the
  forked-skill route was measured in a fresh headless session with hooks disabled.
- **`code-review` is itself a forked skill**, and the review runs on the **caller's model**: a
  Sonnet subagent's call ran a Sonnet review. A fair comparison therefore pins the caller's model to
  the Critic reviewers' model.
- **Launch mode varies run to run.** Some calls return `Skill "code-review" completed (forked
  execution).` with the result inline; others return `launched (forked execution, running in the
  background)` and deliver the result later as a task notification to the caller. The same level
  did both. A caller must handle both, and must stay alive until the notification lands.
- **Output is text.** The result opens with `Result:\n(none)`, and the review follows as prose;
  at `high` the findings arrive as a JSON array (`file`, `line`, `summary`, `failure_scenario`),
  with no `ReportFindings` call. No severity is assigned.
- **The level asked is not always the level run.** Every fork's prompt opens with its recipe line
  (`<level> effort → …`). Over the session's forks only two recipes appeared, `low` and `high`, and
  both `medium` calls — one run concurrently, one run alone — got the `high` recipe. Record the
  recipe line the fork ran, never the requested level.
- **`low`** reads one filtered diff (test and fixture paths excluded), runs one tool call, and
  returned no findings here in about five seconds. **`high`** runs eight inline angles over the
  diff and reads source, and returned 5-7 findings here in 30-100 seconds; it read the project's
  learnings rules and cited one.
- **Yield on this range.** The `high`-recipe runs raised findings the Critic did not; two were
  checked by hand and are real (filed as #1159): a latent free-step shape slip in
  `coverage_algebra` and a stale `_merge_base_verdict` docstring. Neither is blocking. One range
  is an anecdote, not a rate — the paired run exists to measure the rate.

## Added 2026-11-15 (#1177): the review checks out what it reads

Observed in a product repo's session transcript, Claude Code with Opus 5.5: a `code-review` fork
at `high`, handed `<base>...<head>` by the paired wrapper, ran `git checkout -q <head>` about
fourteen seconds in, in the directory it was forked in — the session's own checkout — and then read
source there. `<head>` was the feature branch's tip, so HEAD went detached at that same commit
with nothing changed on disk. The recipe's Phase 0 assumes the diff is `HEAD`-relative, which is
the likely reason. Re-derive it from the fork's subagent transcript (its `meta.json` names
`code-review`, `spawnDepth` 3): the Bash calls carry the checkout. A caller cannot instruct the
fork, which sees only the skill's recipe and its args, so the wrapper runs in a worktree of its
own.

## Added 2026-11-15: an isolated agent cannot Write into the session's checkout

Observed in this repo's first isolated paired run, on Claude Code with Opus 5.5. The wrapper was
dispatched with `isolation: "worktree"` and told to Write its text to the session checkout's
`.prawduct/.native-reviews/`. The host refused the Write tool call with "This agent is isolated in
the worktree <its tree>. Edit the worktree copy of this file instead of the shared-checkout path."
The same wrapper's Bash calls ran python from its tree, and those did write the session's sidecar.
So the refusal applies to the host's file tools, not to the filesystem. The host also refuses an
isolated agent's Bash commands that it cannot prove stay in the agent's worktree. To re-derive
this, read the wrapper's subagent transcript (its `meta.json` has `spawnedWithWorktree: true`,
and its first prompt line names the review) and find the `tool_use_error` that follows its Write.
The fix: the wrapper writes in its own tree, and `native-review record`, run from the session's
checkout, copies the text across.

The same run left the wrapper's worktree behind, locked. When the agent ended, `record` had failed
before returning the tree, so the tree was still detached at the reviewed head. The Agent tool
says a worktree is auto-cleaned if it is unchanged, and this one was changed. Whether the host
removes a tree that is back on its branch at its creation point, with nothing in `git status`, is
not yet observed.
