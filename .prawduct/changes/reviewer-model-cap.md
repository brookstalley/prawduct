---
schema: 1
type: feature
scope: reviewer-model-cap
date: 2026-11-11
title: Reviewers and forked skills never run above Opus-class by accident
closes: [brookstalley/prawduct#1136]
---
The owner ruled on 2026-11-10: "Yes cap at opus. In fact we need to be very careful to not
accidentally spam fable subagents anywhere, given the cost." This amends the norm "Reviewers run
on the session model — no intelligent model switching": its statement stands, and the amendment
sits in its entry in `project-preferences.md` and in `nonfunctional-requirements.md` § Direction.
A session at or below Opus-class dispatches exactly as before.

### Dispatched reviewers are capped at Opus-class (Chunk 01)

`lib/model_tier.py` owns one answer: the model a reviewer runs on, given the model the dispatcher
runs as. A session whose model names Haiku, Sonnet or Opus gets no override and its reviewer
inherits the session's model; any other session — a stronger tier, an id the code does not
recognise, or no id at all — gets the Opus-class alias. `review-stats` folds model ids with the
same function, so the grouping and the cap cannot disagree about a model.

`critic-begin --session-model <id>` writes the answer into the manifest as `reviewer_model` and
prints it as a `reviewer model:` line; `pr-review-dispatch --begin --session-model <id>` prints
the same line, before it attempts the dispatch mark, so a mark that cannot be written keeps the
cap. Without the flag the cap applies and a note says it was assumed. `--tier` never moves it.
The Critic skill, `coordinator.md` and the PR skill pass the answer as the Agent call's `model`,
or pass none, and name no model themselves. Both reviewer agents keep `model: inherit`.

### A capped single-pass review is handed to one dispatched reviewer (Chunk 02)

A forked skill's model is fixed in front matter, so the forked Critic cannot cap itself. When the
manifest sets `reviewer_model`, the fork reviews nothing: it skips the evidence and the diff,
dispatches each roster role through `coordinator.md` on that model — one `critic-reviewer` in role
`reviewer` for a single-pass `chunk`, `verify-resolutions`, `final` or `cumulative` — and stops.
The reviewer writes its marker and its partial, `resolutions` included on a `verify-resolutions`
dispatch, and the `SubagentStop` hook consolidates it as it does a three-reviewer roster.

The directives `critic-begin` prints for a reviewer are rendered by one function,
`critic_consolidate.dispatch_directives`, in their pinned order; the manifest carries the same list
as `dispatch_directives` when a reviewer model is set, and the handed-off reviewer reads it there.
`critic-consolidate`'s wait message tells a handed-off review's reader that it runs in the
background and consolidates on `SubagentStop`. The reviewer contract learns the `reviewer` role,
and the protocol files tell only the fork to consolidate.

### Forked utility skills name Sonnet, and review-stats counts reviews above the ceiling (Chunk 03)

`/prawduct:backlog` and `/prawduct:advisory` declare `model: sonnet` (owner ruling of
2026-11-11, "Sonnet for both"). `review-stats` reports `above_reviewer_ceiling` — how many reviews
in its window were recorded on a model above the ceiling, judged by the dispatch's own function,
and how many recorded no model (not counted as above) — in `--json` (schema 10) and in the human
report.

Every place the plugin starts a subagent or a forked skill, found by query (`plugin/agents/*.md`;
skill front matter declaring `context: fork`; plugin prose naming the Agent tool, `subagent_type`,
a dispatch, a spawn or a subagent):

| Start | Where | Runs on | Why |
|---|---|---|---|
| `critic-reviewer` agent | `agents/critic-reviewer.md`, dispatched by `skills/critic/coordinator.md` | `model: inherit`, overridden by the manifest's `reviewer_model`: the session's model at or below Opus-class, Opus-class above | The ceiling is conditional, which only the dispatch call can express |
| `pr-reviewer` agent | `agents/pr-reviewer.md`, dispatched by `skills/pr/SKILL.md` Step 3 | `model: inherit`, overridden by `pr-review-dispatch`'s answer, as above | As above |
| `/prawduct:critic` (forked) | `skills/critic/SKILL.md` | The session's model — no `model:` | A fixed model would raise a lower-tier session's reviews and fail where it is not offered; above the ceiling the fork only routes and hands the review off |
| `/prawduct:backlog` (forked) | `skills/backlog/SKILL.md` | `model: sonnet` | Owner ruling of 2026-11-11 |
| `/prawduct:advisory` (forked) | `skills/advisory/SKILL.md` | `model: sonnet` | Owner ruling of 2026-11-11 |
| Build, research and integration delegates | `methodology/building.md` "Delegating Work to Subagents" and "Decision Research", `methodology/planning.md`, `methodology/session-digest.md` | The model the dispatcher names | `methodology/delegation.md` "Always name the model at dispatch" governs them |

No start was found that names no model and is not covered by `methodology/delegation.md`.

## Consumer note
On a session running a model stronger than Opus-class, Critic and PR reviews now run on
Opus-class instead of on the session's model, and `/prawduct:backlog` and `/prawduct:advisory`
run on Sonnet-class on every session. On a capped session every single-pass review, whatever its
mode, is handed by the Critic to one background reviewer, so `/prawduct:critic` returns before the
review lands: run `prawduct-hook critic-consolidate` before reading the findings, as after a
three-reviewer review. Sessions on Opus-class or below review exactly as before. `prawduct-hook review-stats`
gains a count of reviews that ran above the ceiling.
