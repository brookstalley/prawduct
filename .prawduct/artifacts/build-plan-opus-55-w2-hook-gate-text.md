---
artifact: build-plan
version: 1
scope: opus-55-w2-hook-gate-text
branch: feature/opus-55-w2-hook-gate-text
partition: serial — one chunk, and the one test file big enough to split on (`tests/test_briefing_functions.py`) carries both A-5's NEXT-ACTION replay and A-30's relay pins, so two delegates would fight over it; a delegate for the small hook/briefing half would cost as much in brief and integration as it saves
depends_on:
  - artifact: opus-55-prompt-audit-2026-09
governed_by:
  - artifact: architecture
    dispositions:
      - "every fact has one home → conforms, and it is A-7's point: `gates.blocking_remedy_lines` composes `critic_consolidate._FIX_ORDER` instead of holding a second wording of the fix order"
      - "authority fails closed; advice fails soft → conforms: only text changes; no verdict, exit code or gate predicate moves. The Stop gate's waiver footer is rendered from the blockers already raised, so it cannot waive what did not block"
      - "an independent reviewer never mutates the session it reviews → inapplicable, because only the text of three dispatch directives changes"
      - "goals and verification bind; prescribed method is advice → conforms: the ruled decisions bind; where a slice's replacement text would drop content a builder or reviewer needs (A-7's 'commit the verified tree verbatim', A-28's gate-specific waiver conditions), the content is kept in plain words and the departure is recorded in the chunk"
      - "the plugin writes nothing into a governed repo except… → inapplicable, because nothing new is written"
      - "local-first governance coordination; written in Python, never specific to Python; guides and never implements → inapplicable, because no mechanism changes"
  - artifact: observability-strategy
    dispositions:
      - "stable severity-prefix vocabulary → conforms: `NEXT-ACTION:`, `PRAWDUCT:`, `BLOCKED —` and the gate attributions are kept; only the prose after them changes, and `BLOCKING` stays as the severity token"
      - "text emitted into a governed product names no prawduct-internal identifier → conforms: the rewrites add no ids; the waiver footer names only waiver keys, which are the file's own interface"
      - "the governance ledger has a single writer → inapplicable"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall clock is P0 → conforms: one chunk, one boundary review; A-29 (F6) is measured by `review-stats` rounds-per-PR before and after W3, per the ruling"
      - "proportionality ratchets both ways → conforms: this wave deletes text and adds no control"
      - "review rigor is stage-keyed → inapplicable, because no severity rule changes; A-29 removes only the closing 'spend this on…' sentence of each directive"
  - artifact: program-purpose-and-cession
    dispositions:
      - "prose-test taxonomy: a doc test pins budgets, refs, interface tokens and render consistency, never a sentence → conforms: a test pinning a sentence this wave rewrites is retired as a descoped requirement or re-pointed at the interface token or one-home composition it protects"
      - "model plan (Fable coherence before the cycle lands) → conforms: owed once, before W6 lands"
---

# Build Plan: Opus 5.5 prompt audit — W2, hook and gate text

## Problem

The text the hooks and gates print into the model's context is the one surface every builder meets
at the moment it acts. It is also the most shouted and the most repeated:

- After every review, NEXT-ACTION runs to about 355 words of capitals and re-argued rules (A-5).
  The batch-fix directive above it states the same fix order again, and it carries a cross-reference
  that dangles on one of its two emission paths (A-6).
- `gates.blocking_remedy_lines` holds its own wording of the fix order instead of composing
  `_FIX_ORDER`, which is the fix order's one home (A-7).
- The Stop gate coaches reflection cadence each time it blocks (A-27). It also prints a waiver
  recipe per blocker, so two blocking gates print it twice (A-28).
- Three reviewer dispatch directives end with a "spend this on…" nudge (A-29, F6).
- The briefing's advisory relay never says the user's own request goes ahead, so the first reply
  can stop at the relay (A-30).

The evidence and replacement text are in `opus-55-prompt-audit-2026-09/slice-A.md`. The owner
ruled on 2026-09-28 (the artifact's § Rulings).

## Success

- NEXT-ACTION's arms, `_IF_YOU_FIX_SOME`, `_RIDE_ALONG_ROUTE`, `cost_lead` and `span_clause` carry
  A-5's wording, with `BLOCKING` kept as the severity token. The warnings-arm close is roughly half
  its old length.
- `_BATCH_FIX_DIRECTIVE` carries A-6's wording and no positional cross-reference. The parsed
  free-write list (`TestBatchFixDirective`) still matches `is_judgeable_path`.
- `blocking_remedy_lines`' standard remedy contains `_FIX_ORDER` verbatim, and the superseded
  branches are unchanged.
- The reflection blocker carries A-27's one line. The Stop gate prints one escape-hatch footer after
  the `BLOCKED` list. The footer names only the keys of the gates that blocked, as one JSON object,
  so two waivers no longer overwrite each other. The learnings-budget "no waiver" line is kept.
- The three dispatch directives lose their closers, and the docstrings that argued for the closers
  are corrected.
- `ADVISORY_RELAY_TEXT` ends with A-30's sentence.
- The suite passes. Every sentence pin a rewrite breaks is retired or re-pointed, per the prose-test
  taxonomy.
- One probe on the session model: a fresh agent is shown the old and the new NEXT-ACTION for the
  same 0-blocking/3-warning review, and asked what it does next. These surfaces reach only the main
  agent, except the three dispatch directives, which a reviewer reads; that part gets the Sonnet 5.5
  probe under F1. The control is the old text. The failure it targets is reflexive fixing of
  warnings that gate nothing.

## Out of scope

- W3 to W6.
- The flags A-40 (a progress cadence while reviewers run) and A-41 (the digest's manual
  `critic-consolidate` step).
- `Escape hatch` text outside the Stop gate (`lib/operator_verification.py`, `lib/ledger.py`).
  Those belong to other gates, which A-28 did not audit.
- Any change to what a gate decides. Only the text changes.

## Requirements Confidence: High

Every change has replacement text, and the owner has ruled on it.

- [ASSUMPTION: A-5's "apply the same lowercasing" covers every arm of `next_action_line`, including the observations-only, empty and carried-blocker arms, and `_RIDES_NEXT_REVIEW_LEAD`. The carried arm keeps its `NOT DONE.` lead as a status token. The decision's evidence cites the function as a whole | LOW impact | owner can narrow it to the arms A-5 quotes]
- [DECISION: A-7's replacement says "that commit carries the resolution facts". The verify pass records those facts; the commit doesn't carry them. So the remedy says the pass records them, and it keeps "commit the tree it verified verbatim", which A-7's text dropped | the text must stay true, and "verbatim" is the half of the golden path the test names | owner can veto]
- [DECISION: A-28's single footer keeps two gate-specific conditions as one line inside their own blocker. The Critic blocker gets "a `Type: designer-handoff` chunk skips this gate automatically", which is a route rather than a waiver. The PR blocker gets "waive only when the merge will not happen this session". The pending-review blockers keep critic-discard's restore note in the footer, which prints only when one of them blocked | these are conditions on a waiver, not repeats of the recipe | owner can veto]

- [DECISION: A-6's replacement puts the costly clause before the free one. The directive keeps free-then-costly, because `TestBatchFixDirective` classifies each path token by its first occurrence, and in A-6's order "`.md`" is met first inside the costly clause. The ruled content (one pass, no positional pointer, no caps) is applied | a reordering would force a weaker parser for no reader gain | owner can veto]
- [DECISION: A-5's `_IF_YOU_FIX_SOME` drops "a refusal is the answer, not a reason to retry in another mode". The rewrite keeps it as "exit 3 is the answer, not a cue to retry in another mode". Retrying after exit 3 is a failure mode the text prevents, and the replacement doesn't restate it anywhere else | owner can veto]
- [DECISION: A-29 removes `VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE`'s closer. The record-gap sentence left last becomes imperative ("Rate a record gap BLOCKING, and say so, when…"), because `test_it_descends_rather_than_only_stating_a_rule` requires the directive to end on an instruction. That requirement is not what A-29 retires. The content is unchanged | owner can veto]

## Found while applying

- Each per-blocker waiver recipe was an `echo … >` line. When two gates blocked together, running
  both recipes left only the second key in the file. The footer writes every key as one object, and
  a test runs the printed recipe and expects the block to clear.
- `KNOWN_WAIVER_KEYS` was a second list of the waiver keys, kept by hand. It is now derived from
  the footer's gate-to-key map, so adding a waivable gate is one entry.
- `documentation/issues/855-design.md` (open, unbuilt) told its future gate to add its own
  escape-hatch paragraph and a key to the old set. It now points at the map and the footer.
- The banner's "tell the user what changed" relay was checked against A-30 and left alone. It
  reports and waits on no decision, so it doesn't invite the early stop A-30 targets.

## Status

- [ ] Chunk 01: hook and gate text (A-5, A-6, A-7, A-27, A-28, A-29, A-30)

## Chunk 01: hook and gate text

**Type:** code
**Decisions:** A-5, A-6, A-7, A-27, A-28, A-29 (F6), A-30.
**Files:** `plugin/lib/critic_consolidate.py`, `plugin/lib/gates.py`, `plugin/lib/briefing.py`,
`plugin/bin/prawduct-hook`. Tests found by grepping each file's path and each rewritten phrase in
`tests/`: `test_critic_consolidate.py`, `test_carried_blocking_findings.py`,
`test_cost_of_commit.py`, `test_review_interval_extension.py`,
`preferences/test_free_interval_prose.py`, `test_briefing_functions.py`, `test_v5_methodology.py`,
`test_finding_scope_rule.py`, `test_cumulative_gate.py`, `test_session_critic_gate.py`,
`test_reflection_gate.py`, `test_learnings_cutover_gate.py`, plus any other test the suite shows.
**Also check:** every other site that emits a message for the same state. That means
`building.md`'s "NEXT-ACTION says when" and `review-cycle.md`'s "exits 3". Search by the state, not
by the words. A sentence another wave owns is fixed now only if this wave made it false.
**Done when:** each Success bullet holds, the suite passes, and the probe has run. Critic: this is
the plan's only chunk, so its review is the branch's `cumulative`.
