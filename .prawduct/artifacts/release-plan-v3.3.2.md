---
artifact: release-plan
version: 1
release: v3.3.2
last_validated: 2026-08-11
---

# Release plan — v3.3.2

A patch cut same-day on v3.3.1, carrying one scope. Nothing withheld.

## Release classification

| Scope | Disposition | Blocker |
|---|---|---|
| advisory-false-positives | ships | |

## What ships

Two advisory surfaces that reported things that were not true, plus the norm amendment the first
one's repair turned out to require.

1. **A blockquoted `> **Why:**` Direction entry is now detected.** A product was told for a week,
   across several syncs, that "no `## Direction` section is ratified in any artifact" while five
   ratified sections sat in its artifacts directory. Every field matcher anchored at `^\s*`, and
   `>` is not whitespace. Verified end-to-end rather than at the helper: the probe no longer fires
   against that repo, and all seven sibling repos carrying Direction sections are unchanged.
2. **The work-model term tripwire is deleted**, executing the owner's 2026-07-12 ruling on #257 —
   its resolution was deletion, not a further precision fix. Precondition verified live rather than
   trusted: CRT-5M9J (#293) ships the `scope-trace:` question in both review protocols, so
   requirements-precede-code enforcement moved rather than lapsed. `prawduct-hook jurisdiction` is
   deliberately kept.
3. **`architecture.md` § Direction's *every fact has one home* gains a granularity clause** (#643,
   owner amendment 2026-08-11) — a fact is the whole predicate, not a token inside it. Added
   because the norm was **followed** on this branch (one home, an imported symbol) and still
   produced two answers.

## Why a patch and not a minor

**Removing two hook subcommands.** `build-index` and `user-prompt-submit` are gone from
`hooks.json`, and every installed repo loses a `UserPromptSubmit` registration at its next session
start. This adds no capability, breaks no gate — the tripwire was advisory and gated nothing — and
its replacement was already live before the deletion. Owner-ratified as a patch, 2026-08-11.

**The deprecation norm was departed from, and it is recorded rather than quietly satisfied.**
`api-contract.md` § Direction defers subcommand removal to a major, "never silent." The owner's
scoped exception (`[[harness-only-removal-is-not-a-major]]`) holds that the clause governs the
externally-callable surface: these two had exactly one caller, `hooks.json`, shipped in the same
plugin at the same version and updated in the same commit, so no caller could observe a gap.
Deprecate-then-remove still governs anything a human or a skill can call, and `stamp-merged` /
`regen-views` stay inert-and-deferred as the contrast that keeps the exception narrow.

**The norm amendment does forbid something previously permitted** — sharing a constant while
leaving its input unshared satisfied the norm as written and does not now. That is stated on the
norm rather than smoothed over, and it does not change the tier: the amendment is small, its only
known violating site is already fixed, and the Enforcement row is Critic-judgment-only (GOV-2R8K
records why), so no consumer's gates change behaviour on upgrade. What changes is what a reviewer
asks.

## The honest counter-argument, recorded rather than resolved away

A consumer who had come to rely on the pre-turn nudge loses a signal with no deprecation window.
Two things bound the cost, and neither is "nobody used it": its precision was the reason for
deleting it — it reported ordinary contractions and mis-stemmed non-words as undocumented domain
vocabulary — and the enforcement it carried now runs at review time, where the question can
actually be answered against the work.

## Verification

- `check-releasability --release v3.3.2` → releasable, 1 shipping, 0 withheld
- Suite green; the count lives in `.prawduct/.test-evidence.json`
- Review: cumulative + three verify rounds closing at 0 findings, then four PR review passes on
  the amendment, each of which found a real error in the *justification prose* and none in the
  normative clause
- The reported defect confirmed fixed against the reporting repo, not only in tests
