---
schema: 1
type: fix
scope: credential-placeholders
date: 2026-11-24
title: The credential check passes placeholder passwords, and a cumulative review meets the check before it runs
closes: []
---
`check-pr-hygiene` refused every `scheme://user:pass@` URL a branch added, including the placeholders
that docs and test DSNs are full of (`user:password@host`, `app:${PG_PASS}@db`). And it refused only at
PR creation, after the cumulative review, so the waiver moved HEAD and bought another review round, plus a
suite run when the waiver landed in a code file.

A url-embedded password is no longer reported when it is visibly a placeholder: the same as its user,
three characters or fewer, a placeholder word (`password`, `secret`, `token`, …), a template field or
variable whose content is a single-case name (`${VAR}`, `{name}`, `<password>`, `%(name)s`), or a mask
(`****`). Each is a full match, so a real-looking secret, one that merely contains such a word, a
mixed-case secret in a wrapper (`$Kx9fPq2mZ`) and a password holding an unencoded `@` are still
reported. Output scrubbing is unchanged.

`critic-begin --mode cumulative` now runs the same check over the same span first, and refuses with
exit 9 when the PR would be refused, naming each line. Other modes, and every branch the PR gate passes,
dispatch as before; `--force` dispatches anyway.

## Consumer note
Placeholder DSNs in docs and tests no longer need a `prawduct/credential-shape` waiver. If a branch adds
a line the PR's credential check would refuse, `/prawduct:critic cumulative` now stops before the review
with exit 9 and the lines to answer: waive a fixture or documented example, or rotate and remove a real
credential, commit, and run the review again.
