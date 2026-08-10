---
artifact: build-plan
version: 1
scope: critic-disposition
governed_by:
  - artifact: architecture
    dispositions:
      - "Authority fails closed; advice fails soft → conforms. Nothing here changes what any gate blocks on: the PR and Stop gates still require coverage plus zero unresolved BLOCKING. What changed is what a builder does with findings *after* the gate is satisfied, which is advice-side by construction."
last_validated: 2026-07-29
lifecycle: completed
archived: 2026-08-10
released_in: v3.2.0
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

# Build Plan — findings are dispositioned, not filed

Authored **after** the work, deliberately. The change was owner-driven mid-session and shipped in
two commits before a plan existed; this records it so the change-log scope is plan-backed and a
later reader can find the reasoning. Writing a speculative plan for work already done would be
theatre — writing the record is not.

## Requirements Confidence

**Level:** High.

- **Problem:** `review-cycle.md` told the builder to FILE every non-blocking finding and
  `review-protocol.md` told the reviewer to "recommend backlog" on every NOTE. Measured on this
  repo: open items **50 → 180 in 26 days**, 67 Critic-sourced, **53 never touched since filing**,
  58% of all Critic items ever filed still open, and `verify-chunk-refs` alone carrying **six** —
  each a facet found by a later review of the same unfixed gate.
- **Success:** every finding leaves a review as FIX, ACCEPT, or (narrowly, with a named trigger)
  FILE; no surface in the framework recommends filing as the default.
- **Out of scope:** retro-triage of the ~20–25 existing items the audit identified as
  should-have-been-ACCEPTs. That is a separate owner decision, not part of this change.

**Parent requirement:** Principle 2 — *implemented or explicitly descoped*. ACCEPT is the explicit
descope, which the resolution flow previously had no way to express: it offered fix-or-file only.
The framework already stated the rule in `methodology/reflection.md` ("Earn the backlog entry —
don't let it inflate"); this change stops the Critic path from overriding it.

## Status

- [ ] Chunk 01: three dispositions, builder side — `review-cycle.md`, `methodology/building.md`
- [ ] Chunk 02: reviewer side and the pervasiveness sweep — `review-protocol.md`, `runbook/SKILL.md`

---

### Chunk 01: three dispositions, builder side

**Type:** doc-only · **Critic mode:** chunk

FIX / ACCEPT / FILE replace "file the rest," with ACCEPT the default and FILE required to name its
trigger. The loop-termination guarantee the old rule existed for is untouched — the review still
ends at zero BLOCKING; only the disposal route changed. Added the count smell test, the
"pre-existing / already filed are not dispositions" clause, and explicit coverage of all three
severities (NOTE was the majority of findings in the review that prompted this).

`methodology/building.md` carries the one-line form and was trimmed to stay inside its 4660-token
ceiling — **5 tokens spare**, so any future edit there needs a trim first.

### Chunk 02: reviewer side and the pervasiveness sweep

**Type:** doc-only · **Critic mode:** chunk

`review-protocol.md` said "Recommend backlog" twice, including in the definition of NOTE. Both
removed — **deletions only**, because that file is diet-locked with ~1 token of headroom and a rule
is not worth weakening a budget test for. The positive prohibition lives in `review-cycle.md`.

The Critic never *files* — its `allowed-tools` carries no backlog access at all. It was
*recommending*, which is the same pump one step upstream and harder to see because it reads as
helpfulness.

Swept by concept across the whole plugin surface, not by phrase. Also corrected:
`skills/runbook/SKILL.md`, which told authors to file a discovered operational gap. Left alone as
legitimate, each for a stated reason: `report-bug` (bugs filed into another product's repo),
`docs/norms.md` (a temporary norm exception must carry a tracking item with a `revisit:` clock — a
FILE that names its trigger, the narrow case working as designed), `janitor`/`doctor` (findings
become a build plan), `pr/review-protocol.md` (reconciliation *closes* items).

**Verification:** suite 2783 passed / 7 skipped at the time of the change; `grep` for the concept
returns no remaining filing-as-default instruction. Applied immediately to the review that prompted
it — five findings headed for the backlog became **three FIX, one ACCEPT, one FILE with a trigger.**
