---
schema: 1
type: feature
scope: control-check-field
date: 2026-11-18
title: a Critic control's firings now persist a structured check field, so their yield is countable
closes: [brookstalley/prawduct#548]
---
A control's yield was recoverable only from the free-text title token the reviewer writes
(`scope-trace:`, `rule-unenforced:` …), and a capitalised, colon-less or filename-led title missed
a naive query. The new `plugin/lib/control_checks.py` holds the closed registry `KNOWN_CHECKS`:
`cross-component-contract`, `scope-trace`, `rule-unenforced`, plus `read-cost`, which shipped after
the issue was filed. Its `derive_check` reads a title's token case-insensitively, with or without
the colon, and after an optional leading file reference. Consolidation stamps the result as `check`
on each review fact finding and observation. `.critic-findings.json` copies it, and so does the
`review.critic` ledger row. Reviewers write nothing new. A title with no token gets no key. The
field is additive, so `evidence.SCHEMA_VERSION` does not move.

The token is read at the title's lead only, not anywhere in it. On 2026-11-18 this clone's
evidence store held 8 titles, among 172 that carry a token, which name a control while reporting a
defect about it ("The scope-trace: retire rule's numerator is already polluted"). Counting those is
what pollutes a retirement numerator; `tests/test_control_checks.py` pins five of them as fixtures.

`tests/test_control_yield_tokens.py` now fails if any shipped prose instructs a yield token that is missing from the registry, or if the registry names one that no
prose instructs. `tools/pr-review-yield.py` reports counts by check and severity. It derives the
check on read for rows recorded before the field existed. With `--event review.critic` it reads the
Critic's rows instead; re-run it for the current counts.

The issue's PR-path step (stamping `check` in `ledger-append --event review.pr`) has no writer left
to change. That kind was retired with the PR reviewer (#1129) and is refused at the CLI.

## Consumer note
none: review records gain an optional `check` key, and readers that ignore unknown keys are unaffected
