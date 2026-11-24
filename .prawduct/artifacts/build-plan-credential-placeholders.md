---
artifact: build-plan
version: 2
scope: credential-placeholders
branch: fix/credential-placeholders
base: develop
working-branches: []
last_validated: 2026-11-24
depends_on:
  - artifact: api-contract
  - artifact: architecture
governed_by:
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; CLI subcommands carry no per-subcommand version → conforms: one new sentinel exit on an existing subcommand, patch-level"
      - "exit codes are the contract; stable severity prefixes; errors attributed → conforms: `critic-begin` 9 is a new documented sentinel; the refusal prints file, line and shape class, never the matched text"
      - "additive-first evolution → conforms: exit 9 is unclaimed; no existing exit, flag or --json key changes meaning"
  - artifact: architecture
    dispositions:
      - "authority fails closed; advice fails soft → conforms: the PR gate still fails closed; the earlier refusal at `critic-begin` dispatches when the diff cannot be read, with a note, since the PR gate will still check"
      - "every fact has one home → conforms: the credential shapes and the placeholder rule stay in `backlog.transport`; `critic-begin` calls the PR gate's own check rather than a copy"
      - "never specific to Python → conforms: the placeholder rule reads URL text, any language or file"
      - "an independent reviewer never mutates the session it reviews → inapplicable because the refusal fires in `critic-begin`, before any reviewer exists, and writes only its guard-refusal fact"
      - "local-first: process-spawn, atomic files, the git object database → conforms: git and the local evidence store only"
      - "the plugin writes nothing into a governed repo but its own state → conforms: the only write is the guard-refusal fact in the shared evidence store"
      - "prawduct guides and reviews; it never implements → inapplicable because this is framework code"
      - "goals and verification bind; prescribed method is advice → conforms: the chunk routes are forecasts; the Constraints bind"
partition: serial — Chunk 02's refusal calls the check Chunk 01 narrows, and both are small
---

## Goals

**Response taken:** Proceed. The owner said "Yes to all of your recommendations" on 2026-11-24, and the recommendation was: placeholder exemptions, plus running the check before the boundary review instead of only at PR creation.

**Product:** The credential check in `check-pr-hygiene` refuses any `scheme://user:pass@` URL a branch adds. In consumer sessions since 2026-11-21 it refused only placeholders (`user:password@host`, test DSNs) in four sessions, and it fires only when the PR is created, after the cumulative review. In one consumer the waiver comment landed in a code file, which cost a full suite run and a verify-resolutions round (round 19 on the branch). Two fixes: stop flagging what is visibly not a secret, and meet the check before the boundary review, where a waiver costs nothing extra.

**Architecture:** The placeholder rule lives with the shapes in `backlog/transport.py` and applies only to the `url-embedded password` shape, as a full match on the password segment. `scrub_secrets` is unchanged: redacting a placeholder from output is harmless. `critic-begin --mode cumulative` runs the PR gate's own credential check over the same span (merge-base…HEAD, committed lines) and refuses with exit 9 when it would refuse.

**Constraints:** A random-looking string must still be reported, so every exemption is a full match against a short, closed list. The earlier refusal must never refuse what the PR gate would pass, so it adds no refusal of its own: it moves one that was going to happen.

**Tradeoffs accepted:**
- *Inferred, then confirmed by the owner on 2026-11-24 (`.prawduct/owner-rulings.md`):* the exemption set. It comes from a survey of every governed repo on this machine (2026-11-24, tracked files): of 204 url-embedded password matches, the rule exempts 176, all placeholders, and keeps 28 random-looking test strings, including this repo's own fixtures, which the check must still flag. Exempt: a password of three characters or fewer; one equal to its user; a placeholder word (`password`, `secret`, `token`, …); a template or variable whose content is a single-case name (`${VAR}`, `$VAR`, `{name}`, `{{name}}`, `<password>`, `%(name)s`); a mask. **The residual risk:** a real secret of one of those forms passes, which means three characters or fewer, the same as the user, a placeholder word, or a single-case name in a wrapper (`$kx9fpq2mz`). A mixed-case secret in a wrapper, or one carrying an unencoded `@`, is still reported.
- Only `cumulative` refuses, not `chunk` or `final`: `cumulative` is the review the PR gate composes, and an inner review refusing would add a cost to every chunk.
- When the diff cannot be read, `critic-begin` dispatches with a `NOTE:`. The PR gate still fails closed on the same condition.

**Decisions made mid-build:**
- Chunk 01: `token` joined the placeholder words, so the documented `x-access-token:TOKEN@` form needs no waiver. The url shape's regex has one home, `transport._URL_CREDENTIAL`, read by both the shape table and the placeholder test.
- Cumulative review (rev-20261124T154824Z-24a7cbfa): the template shapes bounded only the wrapper, so `$Kx9fPq2mZ`, `{Kx9fPq2mZ}` and `<Xk9mQ2vLr7>` passed (R-1), and an unencoded `@` in the password let the piece before it be judged (native review). A wrapper's content must now be a single-case name, wrappers must balance, and an authority holding a second `@` is never exempt. `--force` past a cumulative's other refusals now prints the credential lines it skipped.

## Build Chunks

### Chunk 01: Placeholder passwords are not credentials

- **Description:** `credential_shape` stops reporting a url-embedded password that is visibly a placeholder.
- **Depends on:** none
- **Deliverables:** the placeholder rule in `plugin/lib/backlog/transport.py`, applied by `credential_shape` to the url-embedded password shape only; `plugin/docs/waivers.md` says what is exempt without a waiver
- **Tests:** unit — each placeholder family exempt; random-looking passwords, a secret containing a placeholder word, and a URL with both a placeholder and a real credential still reported; `scrub_secrets` still redacts placeholders. Integration — `check-pr-hygiene` passes a branch that adds only placeholder DSNs and refuses one that adds a real-looking credential.
- **Acceptance criteria:** the corpus survey's placeholder classes are exempt, `s3cr3tpass` is still reported
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed

### Chunk 02: The boundary review meets the credential check first

- **Description:** `critic-begin --mode cumulative` refuses with exit 9 when `check-pr-hygiene`'s credential check would refuse, naming each line, so the waiver or the removal lands before the boundary review instead of after it.
- **Depends on:** Chunk 01
- **Deliverables:** one public entry point in `plugin/lib/pr_gate.py` returning the credential findings over merge-base…HEAD; the refusal in `critic_consolidate.begin_review` for `cumulative` (not under `--force`), with one `guard-refusal` fact; exit 9 and its message in `plugin/bin/prawduct-hook`; the exit-9 row in `plugin/skills/critic/SKILL.md`; the sentinel in `.prawduct/artifacts/api-contract.md` § Error Model
- **Tests:** unit — cumulative refuses on an unwaived credential line and names it; a waived line, a placeholder-only branch, and `chunk`/`final`/`verify-resolutions` modes dispatch; `--force` dispatches; an unreadable diff dispatches with a note. CLI — exit 9 and its stdout.
- **Acceptance criteria:** a branch that `check-pr-hygiene` would refuse for credentials cannot start a cumulative review without `--force`; every branch it would pass starts as before
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved

## Governance Checkpoints

**Commit & PR cadence:** a short plan: commit per chunk, one `cumulative` at the end covers both chunks. No PR unless the owner asks.
