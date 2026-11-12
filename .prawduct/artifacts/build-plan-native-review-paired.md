---
artifact: build-plan
version: 2
scope: native-review-paired
branch: feature/native-review-paired
base: develop
working-branches: []
partition: "serial — 01 and 02 both write the Critic dispatch seam (critic-begin's manifest and the coordinator/SKILL dispatch step), and 03 reads the record 02 defines"
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms; the native review is invoked without `--fix`, `--comment` or `--post`, and the wrapper writes only the native text file and runs one record command"
      - "authority fails closed; advice fails soft → conforms; the pairing is advice: a native run that fails, hangs or never records changes no gate, and consolidation never waits for it"
      - "local-first → conforms; the native review is a host skill run in-session, and the record is a local file plus a per-clone ledger line"
      - "the plugin writes nothing into a governed repo except its own state → conforms; the text file and the ledger line live under `.prawduct/`, gitignored"
      - "written in Python, never specific to Python → conforms; nothing reads a language"
      - "guides and reviews, never implements → conforms; a second reviewer, no product code"
      - "goals and verification bind, method is advice → conforms; two of #1130's methods are departed from and recorded under Goals (the record's home and the text file's home)"
      - "every fact has one home → conforms; the dev-build test is lifted out of `contribution.py` into one helper both callers use, and the pairing decision is made once, in `critic-begin`"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → conforms; the native review runs concurrently with the Critic's reviewers and nothing waits for it. Measured on 2026-11-12: `high` took 30-100s, under the Critic cumulative's clocked median (`prawduct-hook review-stats`)"
      - "proportionality ratchets both ways; a control names its expected yield and emits it → conforms; the expected yield is the comparison table #1130 step 5 defines, the comparison script (Chunk 03) emits it, and the experiment stops itself at #1130 step 7"
      - "state-file growth is advisory → conforms; one ledger line and one text file per paired review, and the ledger's existing size advisory covers them"
      - "review rigor is stage-keyed → inapplicable because the native review rates nothing and blocks nothing; its findings reach the builder as input, not as a gate"
  - artifact: data-model
    dispositions:
      - "no model in a fact's write path → conforms; the model writes the native text file (as a reviewer writes a partial) and deterministic code derives the ledger line from it, including the count and the clocked duration"
      - "facts immutable and append-only → conforms; the ledger line is appended once per paired review"
      - "derived views never authoritative → conforms; no gate reads the native record"
      - "a newer-schema fact is surfaced, never dropped → conforms, and is why the record is not an evidence-store fact (DECISION under Goals): the store travels between clones, and a released reader would block on a kind it does not know"
      - "two stores, two lifetimes → conforms; the native record is a per-clone measurement, so it lives in the per-clone ledger, never in the shared store of answers"
      - "governance documents reach a terminal state; backlog title rules; backlog_service_repo → inapplicable because no document, issue or backlog read changes"
  - artifact: api-contract
    dispositions:
      - "whole-surface semantic versioning → conforms; the verbs ship at the plugin's version"
      - "exit codes are the contract → conforms; each new verb states its codes in its usage line and the contract"
      - "additive-first evolution → conforms; one manifest block, one ledger event kind, one project-state key and two verbs, all new"
depends_on:
  - plugin/bin/prawduct-hook
  - plugin/lib/critic_consolidate.py
  - plugin/lib/ledger.py
  - plugin/lib/contribution.py
  - plugin/lib/core.py
  - plugin/skills/critic/SKILL.md
  - plugin/skills/critic/coordinator.md
  - plugin/docs/project-state-keys.md
  - .prawduct/research/native-review-paired/host-facts-2026-11-12.md
last_validated: 2026-11-12
---

## Goals

**Response taken:** Proceed, citing it. The owner said "Yes start" on 2026-11-12 to #1130, which
carries the problem, the paired-run design, acceptance and scope-out, and three owner rulings of
2026-11-10 (in `.prawduct/owner-rulings.md`): run both each time on development builds, in every
repo that takes `../prawduct-live` as its plugin, with a per-repo opt-out.

**Product:** decide, from data, which Critic goals to cede to the host's native review. Today
there is no local measurement of the native review at all (#1130 Problem).

**Architecture:** the Critic stays exactly as it is. The native review is a second, concurrent
instrument the Critic's own dispatch starts, and it never blocks, delays or rates anything.

**Constraints:**
- The host facts the design rests on were measured, not read: `.prawduct/research/native-review-paired/host-facts-2026-11-12.md`.
- The native review runs on the caller's model, so the wrapper runs on the Critic reviewers' model
  — the manifest's `reviewer_model`, else the session model (the #1136 cap).
- The level asked is not always the level run (`medium` ran the `high` recipe), so the record
  keeps the requested level and the comparison reads the recipe each fork ran from its transcript.
- Launch mode varies (inline or background), so the wrapper's instructions cover both.

**Tradeoffs accepted:** each paired review costs a wrapper subagent plus the native fork. At `high`
on Opus the fork measured 67-99s, about 80-88k cache-write, 1.0-1.4M cache-read and 13-19k output
tokens, and the wrapper roughly 33k cache-write and 0.5M cache-read (`fork_costs.py`). The
experiment ends itself at #1130 step 7; worth revisiting earlier if a month's cost surprises.

**Decisions made in planning:**
- [DECISION: record each native run as a per-clone ledger event `review.native`, not an
  evidence-store fact | #1130 says "fact"; evidence facts travel between clones through
  `/prawduct:pr`, and the data model's newer-schema rule makes a released reader block on a kind it
  does not know, while the ledger is per-clone, gitignored, tolerant of unknown kinds in its
  readers, and already read by `review-stats` per role × model × mode | owner can veto]
- [DECISION: keep the native text at `.prawduct/.native-reviews/<critic review id>.md`, gitignored,
  not beside the partials | #1130 says "beside the review's partials", but `critic-begin` archives
  the partials at the next review, and the monthly comparison needs every text | owner can veto]
- Inferred: the level is `high`. `low` skips test files and reads only the diff; `medium` ran the
  `high` recipe in 2.1.322. Put to the owner with this plan.
- Inferred: the opt-out key is `native_review_pairing: false` in `project-state.yaml`, default on
  for development builds, ignored on released builds.
- Inferred: the dispatch rides the Critic coordinator, not the builder's main session — the
  pairing then fires on code's decision (`critic-begin`), not on the builder remembering.

**Level:** High for Chunks 01-02: every host fact they use was measured. Medium for Chunk 03's
overlap matcher: whether file-and-line proximity agrees with a reader's judgement of "the same
finding" is unknown until it meets real data; the cheapest step that raises it is running the
matcher over the first ten paired reviews and reading its pairings.

## Verification Strategy

Chunk 01 is verified by a dispatch in a scratch repo running this checkout as its plugin
(`claude --plugin-dir`): a development build with a cumulative review produces the manifest block
and the wrapper's run, and a released `VERSION` or the opt-out produces neither. Chunk 02 by one
real paired review end to end: the text file exists, the ledger line has counts and no text, and
the consolidate summary names the native file. Chunk 03 by its known-answer test and a run over the
paired reviews recorded so far.

## Build Chunks

### Chunk 01: A development build's cumulative review dispatches the native review beside the Critic

- **Description:**
  - One helper answers "is this a development build" from the plugin `VERSION` (the `-dev` suffix);
    `contribution.py`'s test moves to it, so the two cannot drift.
  - `critic-begin` decides pairing once: mode `cumulative`, a development build, and
    `native_review_pairing` not `false`. When it pairs, the manifest gains a `native` block: the
    range (`<base commit>...<head commit>`, the same interval the reviewers get), the level, the
    model, the text path, and the dispatch time. Otherwise there is no block.
  - The level and its flags are a code constant, and a test pins that no `--fix`, `--comment`,
    `--post`, `max` or `ultra` can appear in what the manifest hands the wrapper.
  - `coordinator.md` and `SKILL.md` step 7 dispatch one general-purpose wrapper in the same
    message as the reviewers, for both cumulative roster shapes, with a fixed prompt: invoke
    `code-review` with the manifest's arguments, wait for a background completion if there is one,
    write the review's text to the manifest's path, run the record command (Chunk 02), and nothing
    else. Without the block, nothing new happens.
  - The new key is documented in `plugin/docs/project-state-keys.md`.
- **Depends on:** none
- **Deliverables:** `plugin/lib/core.py` (or the module that owns the version), `plugin/lib/contribution.py`,
  the `critic-begin` path in `plugin/bin/prawduct-hook`, `plugin/skills/critic/SKILL.md`,
  `plugin/skills/critic/coordinator.md`, `plugin/docs/project-state-keys.md`, and tests.
- **Tests:** red first — a released `VERSION` writes no `native` block; the opt-out writes none;
  `chunk`, `final` and `verify-resolutions` write none; a development cumulative writes one whose
  arguments carry an explicit level and none of the forbidden flags or levels.
- **Acceptance criteria:** #1130's "released build and opt-out change nothing, red first" and "never
  a fix flag or the cloud level"; the reviewer payload budget tests stay green or their raise is
  recorded.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 02: The native run is recorded, and the builder sees both reviews' findings

- **Description:**
  - `prawduct-hook native-review record` reads the manifest's `native` block and the text file,
    and appends one ledger event `review.native`: the Critic review id, base and head trees, the
    requested level, the model, findings counted by code from the text (a JSON array's length; no
    array and a `(none)` result count zero; anything else records the count as unknown), and the
    duration from dispatch to record. No finding text enters the ledger or any tracked file.
  - `prawduct-hook native-review show [<review id>]` prints the text, newest by default.
  - `critic-consolidate`'s summary names the native file and its count when the record exists, and
    says it is still running when it does not — the builder reads both before fixing (#1130 step 4).
  - `.prawduct/.native-reviews/` is gitignored where the plugin reconciles `.gitignore`.
- **Depends on:** 01
- **Deliverables:** `plugin/lib/ledger.py` (the event kind and role), `plugin/bin/prawduct-hook`
  (both verbs, usage lines, read-only classification for `show`), `plugin/lib/critic_consolidate.py`
  (the summary line), the `.gitignore` reconciler, `.prawduct/artifacts/api-contract.md` and
  `.prawduct/artifacts/data-model.md` entries, and tests.
- **Tests:** red first — a record from a text with a three-item JSON array logs count 3 and no
  text; `(none)` logs 0; unparseable logs unknown; a record without a `native` block refuses with
  its reason; the consolidate summary names a recorded file and a pending one.
- **Acceptance criteria:** #1130's "one Critic fact and one native record for the same base and
  head trees" (as a ledger event, per the DECISION) and "no native finding text in a tracked file
  or a fact".
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 03: The comparison, and the boundary review

- **Description:**
  - `.prawduct/research/native-review-paired/compare.py` joins each `review.native` event to its
    Critic review fact, matches findings by file and nearby line, and reports per Critic goal:
    shared, Critic-only and native-only findings; per instrument: wall clock and, via
    `fork_costs.py`, tokens; and progress toward #1130's stop condition. It writes a blind
    verification sheet — each unique finding with its source removed — for the verifier #1130 step 5
    names, and the README says how to run it monthly.
  - Change fragment `.prawduct/changes/native-review-paired.md`; the boundary cumulative review.
- **Type:** cumulative-final
- **Depends on:** 01, 02
- **Tests:** #1130's known-answer test: three Critic findings and three native findings with one
  overlap yield one shared, two and two unique.
- **Done when:**
  1. Known-answer test green, and the script run over the paired reviews recorded so far
  2. Suite green on the head, recorded
  3. Cumulative review with no unresolved blocking finding
