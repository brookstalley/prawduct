# Learnings

Concise rules. See `learnings-detail.md` for root cause analysis.

## Testing
- **A vacuous test is worse than no test.** Assert the mutation applied, not that the call returned.
- **Run the canonical full suite before claiming green.** A subset is evidence about a subset.

## Testing!
- **A test docstring claiming "this goes red without X" is a claim to EXECUTE.** The mutation costs nothing; the claim costs the next reader.

## Core
- **The core loop owns the clock.** Nothing downstream may sleep on its behalf.
- **A correction is not done when the code is right.** Grep every prose site describing the rule you changed.

## When a fix touches a claim living in several artifacts, rank the copies by LIFESPAN and fix the longest-lived FIRST (2026-08-02)
