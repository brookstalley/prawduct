---
artifact: design
scope: purpose-and-cession
status: ratified by owner 2026-08-12 — Cycle 1 complete 2026-08-13; Cycles 2–4 open
created: 2026-08-13
depends_on: [framework-efficiency-review-2026-07-02.md, build-plan-purpose-and-cession.md]
---

# The Purpose-and-Cession Program — parent requirement document

**Status:** Ratified by owner (Brooks) 2026-08-12 across a multi-session philosophy
thread. **Cycle 1 shipped 2026-08-13.** This file is the parent requirement document for
Cycles 2–4 — the durable home for a program that was, until this file existed, carried
only in an ephemeral session handoff. A future session picking up any cycle should read
this in full before planning; the backlog one-liners cannot carry the rationale.

**The frame is `documentation/purpose.md`.** This file does not restate it. Purpose owns
*why* prawduct exists and what shape its evolution must take; this file owns *the four
cycles that act on it*. The binding principles — notably #25 Third Rework Is a Deletion
Signal and #26 Graceful Cession — live in `plugin/docs/principles.md`.

## Why this program exists

The 2026-07-02 efficiency review's diagnosis was correct and owner-accepted, and the
governed surface grew 3.4x anyway. The program's thesis is that the missing thing is not
more analysis but a **deletion decision**, plus a durable way to keep re-pricing what
prawduct should own as runtimes absorb what it currently hedges against.

The three-hedge taxonomy (owner correction, 2026-08-12) is the classifier the whole
program runs on — each pile depreciates on a different schedule:

| Hedge | Depreciates via | Observed churn |
|---|---|---|
| **Runtime judgment** | model releases | high — this is where enforcement Python grew |
| **Joint myopia** (task-focused dyad never states the context) | slowly, via elicitation | low — methodology prose stable since the prose-diet |
| **Statelessness** | harness features | medium |

## The four cycles

### Cycle 1 — the framework records its own purpose ✅ COMPLETE 2026-08-13

Shipped on `docs/purpose-and-cession`: `documentation/purpose.md` (the framework's
first-ever purpose doc — verified none ever existed in git history), principles #25 and
#26 under a new `## Evolution` section, the roster contract 24→26, CLAUDE.md held at 148
lines, the session-digest roster line paid in-file, and the model-floor norm in
`project-preferences.md`. Plan and review history: `build-plan-purpose-and-cession.md`.

Cycle 1 deliberately precedes Cycle 2 so the deletion pass's *why* is on disk first.

### Cycle 2 — #181 (GOV-6D4Q), the deletion-only pass

**Sequence:** enumerate mechanisms → classify each by hedge pile (the table above;
`documentation/purpose.md` is the frame) → yield lookup against evidence the repo already
holds (evidence store, git, learnings) → produce the disposition list **as ledger rows**
(see Cycle 3 — the list *is* the ledger's first draft, never a separate project) →
owner's **one** batch-veto sitting → execute deletions as governed, Critic-reviewed
chunks → disposition the 12 still-open Wave 2/3 items and the 4 false-premise change-log
deferrals → archive #181 itself.

**Constraints — the constraint IS the design:**
- **No new backlog items.** No new mechanism. No replacements. No numeric target.
- **Burden of proof sits on the mechanism:** delete unless yield is shown.
- Anything not deletable is **left** — no notes-for-later.
- **Do not re-audit.** #181 explicitly rejects a conventional audit; the diagnosis is
  `framework-efficiency-review-2026-07-02.md` plus this program's analysis. "We should
  audit this properly first" is the failure mode the item exists to refuse.

**Precondition** (v3.2.0 Chunk 06 backlog migration) was met 2026-08-01.

**Framing basis:** the requirement was framed as a burden-of-proof inversion rather than
a cleanup with a size target — grounded in the prose-diet's mispriced-floor precedent and
#563's no-yield evidence.

### Cycle 3 — the responsibility ledger lands

`documentation/responsibility-ledger.md`. One row =
**success-condition × fractional owner × the assumption that assigns it × the reassignment signal.**

- Splits are **ordinal** and drift gradually — continuous evolution, not step functions.
- Header carries `last re-priced against <runtime> <date>`; the re-pricing protocol is a
  prose section in the same file.
- **~One page. An index over evidence, never a store.** Rows are subject to the same
  delete-unless-yield default as everything else.
- The **one permitted post-pass mechanism**: a `banner.py` runtime-change advisory against
  the ledger stamp.
- Worked example (agreed in spirit): `/code-review` broke the "no native reviewer"
  assumption → the Critic **cedes** bug-hunting and keeps artifact-conformance scope
  (requirements coverage, plan conformance, descoping honesty).

Codifying "always change" as a standing rule was **considered and rejected**; the ledger's
assumption-carrying rows, re-evaluated on external events, are what replaced it.

### Cycle 4 — telemetry, sibling-first

1. **Zero-code analysis first**: a periodic agent run over sibling repos' existing evidence
   stores (critic finding → surviving-change rate). No new instrumentation to start.
2. Then a **directional-by-construction** schema: counts against a fixed vocabulary
   (owner's histogram — N findings → critical / useful / real-but-unimportant / wrong).
   **No free text, paths, or code** for external consumers; trusted siblings get the rich
   version. The schema must be *physically incapable* of carrying proprietary information.
3. **3tears** (the eval system being extracted from `../discodon`) is the outcome-eval
   bench; prawduct grows no harness of its own. Circularity is accepted.
4. Builder-rates-critic bias is real: read **trends, not absolutes**. Scalar self-ratings
   are worthless under sycophancy — prefer named, auditable incidents over scores.

**File the backlog item only when this cycle is reached** (owner decision — deliberately
not filed now).

### Parallel track

`project-state.yaml` compaction — janitor-grade; the session briefing nudges it.

## Standing decisions to honor

- **Model plan.** The norm itself lives in `project-preferences.md` (§ Model floor and
  coherence pass) — not restated here. Per-cycle mapping: **Cycle 2** = Sonnet enumeration
  fan-out + **Fable** disposition sitting + Sonnet execution + Fable pre-merge coherence;
  **Cycle 3** = Sonnet build, Fable coherence; **Cycle 4** = Sonnet fan-out, Fable
  synthesis; **compaction** = Sonnet.

- **Prose-test taxonomy** (governs the pass's test dispositions). A doc test may pin
  budgets, resolvable refs, interface tokens, and single-sourced render consistency —
  **never a sentence**: a meaning-preserving rewording must not break it, and the
  preferred fix is single-sourcing per the `cache-reads.md` routing pattern. Prose-pinning
  tests **die with their mechanisms**, as descoped requirements, not as contracts being
  violated. LLM-judge unit tests were rejected. A small outcome-eval harness (release
  cadence, models the reader) is a separate post-pass decision, and each eval must
  **retire** tests, not add them.

  Basis: 31 test files pin methodology prose. Combined with Tests-Are-Contracts that is a
  complexity ratchet — simplifying prose reads as "weakening a test." Reading those tests
  before judging them changed the answer: they are drift-compilers for duplicated
  contracts, not dumb greps, so the disease is the duplication and the remedy is
  single-sourcing plus interface-token pins.

- **Seed rows for the disposition list:**
  1. **The change-log** — owner: *"has been a bane."* Essay entries duplicating git, the
     plan, and reflections; `lib/change_log.py`; the scope-pairing release gate; #181's
     false-authority deferrals were change-log prose.
  2. **The archive-plan advisory** — false-positives on release-pending plans. Cycle 1's
     one blocking Critic finding came from following that advisory against
     `pr/SKILL.md`'s RETAIN rule.

- **Open learnings-rule candidate** (earned in Cycle 1; deliberately deferred to the
  pass's learnings disposition rather than growing the 254-rule file):
  > *A session-start advisory that tells you to mutate governance state is advice about a
  > record — read the record before acting; advisories fail soft, records bind.*

## What will bite you

- `build-plan-purpose-and-cession.md` archives at the **develop→main release**, not at
  merge (the RETAIN rule — Cycle 1's blocking finding was exactly that mistake).
- `documentation/purpose.md` is the ONE home for the framework's purpose; principles stay
  in `plugin/docs/principles.md`. Restate neither anywhere, including here.
- The 6–24-month subsumption framing was **deliberately generalized** in purpose.md to
  "months or years" — the owner's user-needs framing is the spine, not a timeline.
