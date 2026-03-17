# PR Reviewer Subagent — Requirements

## Origin
User request from 2026-03-17 session. Persisted here so context survives /clear.

## Goal
Every PR created in a project that uses prawduct methodology is approved and merged with no further changes. Zero comments, zero change requests.

## What It Does
When prawduct, Claude Code, or the user creates a PR, this subagent should immediately review the PR like a very seasoned and expert SWE + architect + product manager would.

## Review Criteria (from user)
- Code style
- Proportionality (right amount of effort for the task)
- Explanations of why this method and not another
- Granularity (PR size and scope)

## Design Tension (flagged by user)
Granularity is tricky: the PR reviewer runs *after the fact*. Insisting a large PR be broken up causes churn — the work is already done. The user acknowledged "I may not have it right" on this point and wants careful design thinking about where in the workflow this agent operates and what it optimizes for.

## Key Design Question
The goal (PRs approved with no changes) means the reviewer should either:
1. Run *before* PR creation to catch issues early (proactive), or
2. Run *at PR creation* but focus on what can be fixed without churn (pragmatic), or
3. Some hybrid — flag structural issues early, polish at PR time

## Status
Awaiting discovery and design. Next session should read this file and proceed with planning.
