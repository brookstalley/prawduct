---
artifact: build-plan
version: 2
scope: self-citing-clear
branch: fix/977-self-citing-clear
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "new controls emit their yield → conforms by widening the recorded bounded exception: the `clear-verdict` gate's exception names its expected yield and clock; this check rides the same gate id, so it joins that exception, and the exception text widens to name it, rather than adding a gate"
      - "review wall-clock is P0 → conforms: no review round, reviewer or mode is added; the refusal costs one rewritten paragraph"
      - "state-file growth is advisory only → inapplicable: no state file is touched"
  - artifact: architecture
    dispositions:
      - "authority fails closed; advice fails soft → conforms: the gate refuses a message fault (a clear verdict whose reason points at what a clear deletes), as the existing pair check does; it never blocks `/clear` and never reads the handoff note, which stays #560's advisory"
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
existing `clear-verdict` gate, held apart from the deferrable blockers like the pair check.

**Constraints.** The prose rule is not reworded (#977 scope-out). No new gate id or ledger kind
(the NFR exception's reasoning). Mechanical turns get no new step.

**Inferred decisions (for the boundary):**
- *Inferred:* widen the gate rather than fold into #560 or accept recall-only. Both checks are faults
  in the message the reader acts on, fixed by rewriting one paragraph, which is the ground the
  existing exception gives. #560 asks whether a note exists, and it must not block; this asks
  whether the stated reason is a reason. The core rule on mechanising rules recall misses applies.
- *Inferred:* detection is a narrow phrase match on the verdict paragraph only: the message, reply,
  response or turn named as where something *is* or as what *holds* it, or something said to be
  above or below. "Conversation" is deliberately out: "nothing lives only in this conversation" is
  a legitimate reason. A miss costs what today costs, while a false positive costs a rewritten line,
  so the pattern trades recall for precision.

**Decisions made mid-build:**
- The detector was tuned on this machine's transcripts. Of 1,252 `SAFE TO CLEAR` closes, the
  first pattern matched 18; 3 were sound reasons (two negated, "nothing ... lives only in this
  message"; one whose findings were saved as issue comments). A negation exemption and `issue` as
  a durable record took it to 15, each a genuine instance. Settled by the precision-first inference
  above.
- session-hygiene.md is not edited. A clause naming the gate cost 8 tokens over that file's pinned
  ceiling, and its sentences stay true without it: line 39 already says the Stop hook reads the
  verdict, and the gate's message points at the guide. Settled by the token-footprint preference
  (simplify before raising) and #977's scope-out on rewording the prose.

**Level:** High. The verdict paragraph is already isolated by `clear_verdict`; the trial gives two
real phrasings and session-hygiene.md gives a third.

## Status

- [ ] Chunk 01: The clear-verdict gate refuses a self-citing SAFE TO CLEAR

## Build Chunks

### Chunk 01: The clear-verdict gate refuses a self-citing SAFE TO CLEAR

- **Type:** code
- **Depends on:** none
- **Deliverables:**
  - `plugin/lib/standing_block.py`: `self_citation(text)` returns the self-citing phrase from a
    `SAFE TO CLEAR` verdict paragraph, or `None`.
  - `plugin/lib/gates.py`: `turn_cites_itself_as_record(stop_input)` on the payload field, same
    degradation as `turn_contradicts_its_verdict`.
  - `plugin/bin/prawduct-hook`: a `clear-verdict` blocker naming the phrase and the remedy (write
    to `.prawduct/.handoff-notes.md`, then give that as the reason).
  - `plugin/hooks/gates.json`: the `clear-verdict` summary covers both checks.
  - Tests: the three known phrasings refused; legitimate reasons (notes on disk, "nothing lives
    only in this conversation", "findings above are in the notes") pass; `DO NOT CLEAR` and
    no-block turns unaffected; the Stop hook end to end.
  - Records: the NFR exception and the cross-cutting row name the widened check; change-log
    entry. (session-hygiene.md was planned and left unchanged; see Decisions made mid-build.)
- **Acceptance criteria:** #977's two boxes. The red case is already run (2026-10-09: the gate
  returned `None` on "SAFE TO CLEAR — the questions are in this message", control pair fired).
- **Done when:** criteria met, tests pass, committed, cumulative Critic clean, ticked.
