---
schema: 1
type: governance
scope: critic-good-faith-severity
date: 2026-11-25
title: The Critic rates a finding that needs bad faith or an ignored instruction an observation at most
---
The owner's design stance of 2026-11-26 assumes good faith by humans and competence by models, and
its "what was over-built" ruling (item 4) gives the Critic's review protocol a severity rule to
match. Both severity sections now carry it: `review-protocol.md` § Severity Levels, read by `final`
and `cumulative` reviewers, and `goals-1-3.md` § Severity, read by `chunk` and
`verify-resolutions` reviewers, who never open the protocol. The two copies are one line, pinned
identical.

A finding whose failure needs a person acting in bad faith (hiding work past a gate, rewriting a
version file into a command) or a model ignoring its instructions (invoking a skill unasked), or
whose fix needs a list to close an open set (every spelling a prefix grant reaches), is an
observation at most, whatever its goal rates it. The same sentence states the floor: a crash, a git
error, stale state, untrusted input, or a competent mistake keeps its severity. A competent mistake
is a careful person's misread ambiguous step, forgotten step, or wrong input the code took silently.
Naming untrusted input keeps Goal 1's security rules whole: an attacker across a trust boundary is a
real failure mode, not the bad faith this rule is about.

The rule is reviewer judgment, so it is prose; consolidation assigns no severity from it. Paid in
part by in-place cuts of text another surface owns (see the token-budget entries), the rest declared.

## Consumer note
Critic reviews no longer rate as warnings or blocking findings any failure that needs someone acting
in bad faith, a model ignoring its instructions, or a list to cover an open set; they come back as
observations. Crashes, git errors, stale state, untrusted input and honest mistakes are rated as
before.
