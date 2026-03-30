# Build Governance — prawduct

This defines **how** to build. The build plan defines **what**. Read both before starting.

## Build Cycle

Each chunk follows this cycle. Do not skip steps.

- [ ] **Clean baseline** — All tests pass. No uncommitted changes. Medium+ work uses a feature branch.
- [ ] **Read the spec** — Chunk entry in build plan + referenced artifacts. Validate targets still exist — plans go stale. Run `/learnings [topic]` for relevant rules.
- [ ] **Write tests alongside code, never after** — Tests are specification made executable. Unit for logic, integration for interactions, e2e for critical flows.
- [ ] **Implement** — Make tests pass. Follow `.prawduct/artifacts/project-preferences.md`. Write idiomatic code for the project's language. Prefer simplicity.
- [ ] **Update artifacts** — Changed API surface, data model, test counts, architecture? Update the artifact now, not later.
- [ ] **Verify** — Full test suite + product verification (launch it, call it, inspect output). Mocks alone are not verification. Record test results to `.prawduct/.test-evidence.json` (see format below).
- [ ] **Critic review** — Run `/critic` now — do not ask the user, do not offer it as an option, do not proceed to the next chunk first. The Critic reads test evidence from step 6; it does not re-run tests. Fix blocking findings before proceeding.
- [ ] **Reflect** — What did the Critic catch? Capture deferred work to `.prawduct/backlog.md`.
- [ ] **Commit and persist state** — Commit all work. Update the build plan Status section in `.prawduct/artifacts/build-plan.md` — mark completed chunks `[x]` and update the `Context:` line with key decisions, what's done, and what's next. This is mandatory — context compaction can happen at any time, and an out-of-date Status section means the next chunk (or session) starts blind.

## Test Evidence

After running the full test suite in the Verify step, write `.prawduct/.test-evidence.json`:

```json
{
  "timestamp": "ISO-8601",
  "git_sha": "HEAD at time of test run",
  "test_command": "the command used",
  "passed": 0,
  "failed": 0,
  "skipped": 0,
  "total": 0,
  "duration_seconds": 0
}
```

The Critic reads this file to confirm tests passed on the current code. If `git_sha` doesn't match HEAD, the evidence is stale.

## Rules

- **Tests are contracts.** Fix the code, never weaken the test. Count never decreases.
- **Complete delivery.** Every requirement implemented or explicitly descoped.
- **Scope discipline.** Build what the plan says. No unrequested features.
- **No "pre-existing" exception.** If you find a problem, fix or flag it.
- **Persist to files.** Context doesn't survive compaction. Plans and decisions go in artifacts.

## Session End

Each chunk already ends with commit + Status update (step 9). Before `/clear`: verify Status is current → backlog deferred work → write reflection. Never signal "done" until these are complete.

## Completing Work

Delete `build-plan.md`. `/pr merge` does this automatically.
