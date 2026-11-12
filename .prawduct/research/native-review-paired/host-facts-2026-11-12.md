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
