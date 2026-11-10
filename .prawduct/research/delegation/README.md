# Delegation report

Research tooling for backlog item #1134: how did delegated (subagent) work go? Nothing in the
plugin records it, and the host deletes session transcripts after about 30 days, so this reads
the transcripts directly.

## Run it monthly

```
python3 delegation_report.py \
  --source <transcript dir> [--repo <git repo of that dir>] [--suite "<declared suite command>"]... \
  --source <next transcript dir> ... \
  --since YYYY-MM-DD --until YYYY-MM-DD [--base develop] [--json] [--names]
```

A transcript dir is a Claude Code project directory (`~/.claude/projects/<encoded path>`) holding
`<session>.jsonl`. Subagent transcripts are read from `<session>/subagents/` and from inline
sidechain entries. `--repo` and `--suite` attach to the preceding `--source`. Run it before the
oldest transcripts expire and keep each run's counts.

## What it reports

Per repo and overall: dispatches by role, model requested and resolved, isolation, background
versus foreground, fan-out width, delegate wall clock (median, p90), tokens, declared-suite and
governance-command use, follow-up rounds, and (with `--repo`) delegate branches merged, unmerged
and leftover worktrees.

- **Measured**: dispatch count, reviewer role (subagent type), model requested, model resolved,
  isolation, background, fan-out width (dispatches in one assistant message), wall clock (first to
  last timestamp), tokens (input plus output where `usage` exists; otherwise "usage absent"),
  follow-up rounds (SendMessage addressed to the agent id), branch and worktree counts.
- **Heuristic**: research/build (no write tool in the sub-transcript means research), integrate
  (a build whose prompt or description mentions merge or integrat*), declared-suite use (exact
  prefix of a command segment after whitespace normalisation; quoted text such as an echo or grep
  pattern is ignored; with no `--suite`, "not assessed"), governance-command use
  (`prawduct-hook critic-begin|critic-consolidate|disposition|plan retract`, or a Skill call to
  `prawduct:critic` or `prawduct:pr`). A branch counts as merged when the base contains it, which
  includes a delegate branch that never committed.
- **Not reported**: wall clock saved versus serial (not observable), coordinator merge conflicts
  and rework (not mechanised here).

## Privacy

The output is counts and fixed-vocabulary labels only, built from counters: no prompt text, paths,
code or other transcript strings reach it. Repos print as "repo A", "repo B" unless `--names`.
This repository is public: commit only aggregate counts under aliases, never raw run output, and
never a transcript.

## Test

`sh test_delegation_report.sh` runs a known-answer check over the synthetic fixture in
`fixture/transcripts`.
