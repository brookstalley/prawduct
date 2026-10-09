---
artifact: build-plan
version: 2
scope: self-citing-clear
branch: fix/977-self-citing-clear
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → conforms: no review round, reviewer or mode is added; a refusal costs one rewritten line"
      - "proportionality ratchets both ways; new controls emit their yield → conforms: `clear-reason` has its own gate id, so its firings are `stop-gate:clear-reason` facts counted by `stats`; its expected yield and retirement condition are recorded in the NFR"
      - "state-file growth is advisory only → inapplicable because no state file is touched"
      - "review rigor is stage-keyed → inapplicable because this changes a Stop gate, not a review"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session → inapplicable because no reviewer is touched"
      - "authority fails closed; advice fails soft → conforms: the gate refuses a message fault, as `clear-verdict` does; it never blocks `/clear` and never reads the handoff note, which stays #560's advisory; an unreadable payload yields no refusal"
      - "the plugin writes nothing into a governed repo but its own state → conforms: the gate writes only the existing stop-block fact"
      - "local-first governance, no third-party governance dependencies → conforms: stdlib regex over the payload field; the measure script reads local transcripts and sends nothing"
      - "prawduct guides and reviews; it never implements → inapplicable because no product code is touched"
      - "never specific to Python → conforms: the check reads the agent's closing prose, whatever the product's language"
      - "goals and verification bind; prescribed method is advice → conforms: the gate checks a claim (that a clear loses nothing), not a method"
      - "every fact has one home → conforms: the vocabulary and both readers live in `standing_block.py`; the prose rule stays once in session-hygiene.md"
partition: serial — one chunk, five files around one function
last_validated: 2026-10-09
---

# Build Plan: A SAFE TO CLEAR that cites the message is refused (#977)

## Goals

**Response taken:** Proceed, citing #977. The owner said "let's fix 977" on 2026-10-09, after
the item's acceptance had framed the choice as widen the gate, fold into #560, or accept
recall-only.

**Product.** A reader who returns to a `SAFE TO CLEAR` turn hours later can clear and lose
nothing. The 2026-10-09 wave-1 trial (`build-plan-requirements-alignment-w1.md` § Trial) had 2 of
7 fresh agents close a findings-only `YOUR TURN` on `SAFE TO CLEAR` with the message itself as
the record. The prose rule (#683, session-hygiene.md) names that tell; recall missed it 2 in 7.

**Architecture.** The verdict check lives in `lib/standing_block.py` with the other readers of the
closing block. `lib/gates.py` exposes it on the Stop payload. The Stop hook reports it under the
`clear-reason` gate (see Decisions made mid-build), held apart from the deferrable blockers like
the `clear-verdict` pair check.

**Constraints.** The prose rule is not reworded (#977 scope-out). No new ledger kind. Mechanical
turns get no new step.

**Inferred decisions (for the boundary):**
- *Inferred:* enforce it in a Stop gate rather than fold into #560 or accept recall-only. Like the
  `clear-verdict` pair, this is a fault in the message the reader acts on, fixed by rewriting one
  paragraph, which is the ground that gate was built on. #560 asks whether a note exists, and it must not block; this asks
  whether the stated reason is a reason. The core rule on mechanising rules recall misses applies.
- *Inferred:* detection is a narrow phrase match on the verdict paragraph only: the message, reply,
  response or turn named as where something *is* or as what *holds* it, or something said to be
  above or below. "Conversation" is deliberately out: "nothing lives only in this conversation" is
  a legitimate reason. A miss costs what today costs, while a false positive costs a rewritten line,
  so the pattern trades recall for precision.

**Decisions made mid-build:**
- The detector was tuned on this machine's transcripts (first pass over two profiles' 1,252
  closes; the committed tool, over every profile, is the current figure: see the revision below).
  The first pattern's hits included sound reasons phrased as denials, and one whose findings were
  saved as issue comments. A denial exemption and `issue` as a durable record removed them.
  Settled by the precision-first inference above.
- session-hygiene.md is not edited. A clause naming the gate cost 8 tokens over that file's pinned
  ceiling, and its sentences stay true without it: line 39 already says the Stop hook reads the
  verdict, and the gate's message points at the guide. Settled by the token-footprint preference
  (simplify before raising) and #977's scope-out on rewording the prose.

- *Revised after the cumulative review:* the check has its own gate id, `clear-reason`
  (`since: 3.7.1`), rather than riding `clear-verdict`. Stop blocks already record one fact per
  gate id, so a shared id would have judged this check on the pair check's numbers (review W3),
  and an unchanged `since` meant the version banner never announced the new refusal (W2). A new
  id adds no format. This reverses the plan's "no new gate id" constraint, whose reason (no
  one-gate ledger kind) did not apply once the stop-gate fact sink existed.
- *Revised after the cumulative review:* a bare "in this turn" means "during this turn", so the
  "in" pattern now needs a verb of being in front of it, and above/below must end the clause
  (review W1: "Nothing changed in this turn", "context is below half" were refused). The corpus
  scan is committed as `tools/measure-self-citing-clear.py`, so the figures re-derive: read
  2026-10-09, 18 of 1,533 closes across every profile, each a genuine instance. After the
  verify pass (R-1), the denial exemption is judged per clause, so any "no/nothing/none" clause
  passes ("No open question is in this message") while a denial in another clause excuses
  nothing ("Nothing is running, and the plan is all in this message" is still refused).

**Level:** High. The verdict paragraph is already isolated by `clear_verdict`; the trial gives two
real phrasings and session-hygiene.md gives a third.

## Status

- [ ] Chunk 01: A Stop gate refuses a self-citing SAFE TO CLEAR

## Build Chunks

### Chunk 01: A Stop gate refuses a self-citing SAFE TO CLEAR

- **Type:** code
- **Depends on:** none
- **Deliverables:**
  - `plugin/lib/standing_block.py`: `self_citation(text)` returns the self-citing phrase from a
    `SAFE TO CLEAR` verdict paragraph, or `None`.
  - `plugin/lib/gates.py`: `turn_cites_itself_as_record(stop_input)` on the payload field, same
    degradation as `turn_contradicts_its_verdict`.
  - `plugin/bin/prawduct-hook`: a `clear-reason` blocker naming the phrase and the remedy (write
    to `.prawduct/.handoff-notes.md`, then give that as the reason).
  - `plugin/hooks/gates.json`: a `clear-reason` row, `since: 3.7.1`.
  - `tools/measure-self-citing-clear.py` + its test: re-derives the tuning figures.
  - `plugin/CHANGELOG.md`: the consumer-facing note for the new refusal.
  - Tests: the three known phrasings refused; legitimate reasons (notes on disk, "nothing lives
    only in this conversation", "findings above are in the notes") pass; `DO NOT CLEAR` and
    no-block turns unaffected; the Stop hook end to end.
  - Records: the NFR exception and the cross-cutting row name the widened check; change-log
    entry. (session-hygiene.md was planned and left unchanged; see Decisions made mid-build.)
- **Acceptance criteria:** #977's two boxes. The red case is already run (2026-10-09: the gate
  returned `None` on "SAFE TO CLEAR — the questions are in this message", control pair fired).
- **Done when:** criteria met, tests pass, committed, cumulative Critic clean, ticked.
