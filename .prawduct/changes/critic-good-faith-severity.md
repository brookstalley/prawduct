---
schema: 1
type: governance
scope: critic-good-faith-severity
date: 2026-11-26
title: The Critic rates a finding that needs bad faith or an ignored instruction an observation at most
---
The owner's design stance of 2026-11-26 assumes good faith by humans and competence by models, and
its "what was over-built" ruling (item 4) gives the Critic's review protocol a severity rule to
match. Both severity sections now carry it: `review-protocol.md` § Severity Levels, read by `final`
and `cumulative` reviewers, and `goals-1-3.md` § Severity, read by `chunk` and
`verify-resolutions` reviewers, who never open the protocol. The two copies are one line, pinned
identical.

A finding whose failure needs this repo's own builder, owner or model to act in bad faith later
(bypassing a gate to hide work, invoking a skill unasked) is an observation at most, whatever its
goal rates it. The same sentence states the floor: a defect already in the change, a crash, a git
error, stale state, untrusted input, an actor the product's own requirements defend against, or a
competent mistake keeps its severity. A competent mistake is a careful person's misread ambiguous
step, forgotten step, or wrong input the code took silently. So the cap covers the framework's own
workflow and never a product's threat model or an attacker across a trust boundary, and it judges
the failure, never the fix: closing a class with a longer list stays the remedy rule's to refuse.

The rule is reviewer judgment, so it is prose; consolidation assigns no severity from it. Paid in
part by in-place cuts of text another surface owns (see the token-budget entries), the rest declared.

## Consumer note
Critic reviews no longer rate as warnings or blocking findings a failure that needs the repo's own
builder, owner or model to act in bad faith later; those come back as observations. Defects already
in the change, crashes, git errors, stale state, untrusted input, the product's own threat model and
honest mistakes are rated as before.
