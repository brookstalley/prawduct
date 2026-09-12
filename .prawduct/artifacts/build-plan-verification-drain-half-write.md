---
artifact: build-plan
version: 2
scope: verification-drain-half-write
branch: fix/verification-drain-half-write
depends_on:
  - artifact: api-contract
governed_by:
  - artifact: api-contract
    dispositions:
      - "exit codes are the contract, on a documented and consistent scheme → conforms, and
        deliberately adds NO exit-code member: the refusal is a state-mutating writer's documented
        `1` (refused — validation failed, nothing written). See § The Exit Code This Plan Does Not Add."
      - "additive-first evolution: flag names, exit-code meanings and `--json` keys are never
        repurposed → conforms; `1` keeps its existing meaning on these commands and the result dicts
        gain keys only"
      - "errors are attributed, never raised as stack traces across the boundary → conforms; the
        refusal is a returned `{\"error\": ...}` rendered by the CLI, not a traceback"
  - artifact: project-preferences
    dispositions:
      - "internal `lib/` functions return dicts with status/reason rather than raising; new code that
        raises within governance internals is a violation → conforms, and this constrained the design:
        the mutators return whether they acted and the entry carries the diagnosis, instead of the
        raise the first draft of this plan called for. The module's two PRE-EXISTING `ValueError`s are
        left alone — see § Known Non-Conformance."
      - "stdlib-only governance runtime, Python 3.10+ → conforms; no new imports"
  - artifact: architecture
    dispositions:
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state and the
        files it must reconcile → conforms, and sharpens the fix: no auto-repair of the queue on any
        path. The queue is an operator-authored record; the tool names the edit and the human makes it."
      - "authority fails closed; advice fails soft → conforms. The gate still counts an unreadable
        entry as `pending` and still blocks; the diagnostic is additive and changes no verdict."
      - "every fact has one home; every other mention is a reference to it → conforms, and it is the
        chunk's central repair: which line is the status line had TWO homes (the reader's walk and
        the writer's), and they disagreed. One walk now owns it. The refusal text likewise has one
        home shared by its three callers."
      - "goals and verification bind; prescribed method is advice → conforms, and exercised once:
        the plan prescribed exit 3 and the code took exit 1, recorded in § The Exit Code This Plan
        Does Not Add rather than conformed to."
      - "an independent reviewer never mutates the session it reviews → inapplicable because this
        plan touches no review machinery."
      - "local-first governance coordination; two admitted network surfaces → inapplicable because
        this plan adds no network call and no dependency."
      - "prawduct is written in Python and must never be specific to Python → inapplicable because
        this plan touches no gate or canary that dispatches per file language; the queue format is
        prawduct's own governance state, not product source."
      - "prawduct guides and reviews; it never implements → inapplicable because the change is to
        prawduct's own runtime, not to a governed product's code."
partition: serial, single chunk — four defects share one write path and one review is cheaper than
  four; splitting them would buy nothing and cost three extra Critic rounds
last_validated: 2026-09-12
---

## Requirements Confidence

**Level:** High

**Why:** The defect is reproduced end-to-end against the live module (not inferred), the root cause is
a single discarded boolean, and the design question the reports raised (widen the parser vs. hold it)
was settled against the framework's own shipped guidance — `plugin/templates/operator-verification.md`
states the bare-token rule twice and prawduct emits the combined shape nowhere.

**Open assumptions / unknowns:** none outstanding. The one design call is recorded below as a
`[DECISION: …]` rather than an assumption, because it was taken deliberately and stated to the owner
with the option to reverse it.

**What would raise confidence:** N/A

## The Decision This Plan Rests On

**[DECISION: the parser stays strict; the silence is the defect, not the strictness.]**

Two downstream products, a day apart, filed the same bug from the same self-invented shape —
`**Chunk:** … · **Raised:** … · **Status:** pending` — and both proposed "teach the parser the
combined-metadata line" as the first acceptable fix.

- **Alternative considered and rejected: widen the parser.** `plugin/templates/operator-verification.md`
  states the bare-token rule twice, with the incident that bought it (`verified (2026-07-17, throwaway
  repo foo)` counted as pending; the gate blocked on finished work). Nothing in the plugin emits the
  combined shape. Accepting it would leave the framework documenting one canonical shape and silently
  honouring a second — the same one-rule-two-carriers failure the reports themselves level at the
  half-write.
- **What the reports found that neither named:** the shape is *convergent*, not a typo. Two products
  invented it independently, and this repo's own queue hit it historically (VRF-014's note records six
  sibling entries carrying it, all since repaired — the live queue's 19 entries are clean). It is what
  an agent naturally writes composing a compact entry header. The bare-token rule lives in an HTML
  comment an appending agent may never read, and nothing catches the mistake at write time — the
  operator finds out weeks later from a gate that blocks with no clue why, having been told the drain
  succeeded.
- **Therefore:** hold the parse rule, and spend the work on making the failure loud, precise, and
  early. Refuse rather than half-write; name the offending line and the exact edit; say it at the gate
  too, where today the advice given is provably inapplicable to the entry it is given about.

Recorded as a ruling in `.prawduct/operator-verification.md` and in the shipped template so the next
downstream filer meets the decision beside the rule instead of re-litigating it.

## The Exit Code This Plan Does Not Add

The first draft of this plan specified exit **3** for the refusing mutators, reasoning from
`check-operator-verification`'s exit-3 branch. **That was wrong, and the correction is worth recording
because the reasoning error is the one `learnings.md` L581 names.**

§ Error Model's third-outcome rule is scoped to *a gate whose SUBJECT could not be read*, where `1`
already carries a specific remedy ("there are pending entries, drain or override the first one") that
cannot apply to an unparsed queue. `verify-operator-verification` and `accept-operator-verification`
are not gates — they are **state-mutating writers**, whose row in the scheme table reads `1 = refused,
validation failed, nothing written`. That is exactly and only what happens here. Reusing it is correct;
inventing `3` would add an exit-code meaning the scheme does not need, which is what "documented and
consistent scheme" exists to prevent — and would owe a registry row (L463) for a member that should
not exist.

Consequence: `bin/prawduct-hook` needs **no exit-code change at all**. `run_verify_entry` returning
`{"error": ...}` already routes to exit 1. The whole fix lands in the lib and in what it says.

## Known Non-Conformance (flagged, not fixed here)

`mark_verified` and `mark_accepted` each already raise `ValueError` (verifying an `accepted` entry;
an empty acceptance rationale). Under `project-preferences.md` those raises are non-conforming —
internal `lib/` functions return status/reason dicts. They are **left alone**, deliberately:

- converting them is a behaviour-preserving refactor orthogonal to this defect, and it would churn
  four existing tests that assert the raises;
- neither can reach a CLI boundary on the supported path — `run_verify_entry` pre-checks the accepted
  case and `run_accept_pending` pre-checks the rationale, each returning `{"error": ...}` before the
  mutator is called.

This chunk adds **no new raise**. Filed as **#801** rather than folded in — filed for real, and that
is the point: this plan is archived at the release, so a deferral recorded only here would vanish
exactly when it came due. Noted here too so the next reader of the module meets the decision rather
than re-discovering the inconsistency.

## Status

- [x] Chunk 01: Refuse the half-write; make the queue's write path stop damaging the file
Context: Built and reviewed 2026-09-12, committed a9cf0cec. Grew from upstream reports #798 (root
cause verified by direct call) and #788 (merged into it as the same defect at a different altitude);
defects B, C and D were found while reproducing A and are in neither report.

Two review rounds, and the second was bought by a process error worth naming here: the first review
was dispatched and then the subject files were scrubbed underneath it, so the reviewed code had no
green suite behind it (BLOCKING R-1). `building.md` and `learnings.md` now carry the rule that
prevents it. `rev-20260912T144832Z-5323100f` closed clean — 0 blocking, 0 findings — after nine
fixes; R-10 and R-11 carry recorded `accept` dispositions.

The plan's one prescription that the code did NOT follow is § The Exit Code This Plan Does Not Add:
exit 3 was specified and exit 1 shipped. Recorded rather than conformed to, per architecture's
"goals and verification bind; prescribed method is advice".

Outstanding for whoever merges this: `/prawduct:backlog update 798 status=shipped
closed-by=verification-drain-half-write` — deliberately not done here because the branch is unmerged
(accepted finding R-10). The carrier is the **PR body**, which survives to the merge where the close
comes due; an earlier draft named `.prawduct/.handoff-notes.md`, which is gitignored and so cannot
travel with the branch to whoever merges it. Nothing else is open on this plan.

## Verification Strategy

Beyond the suite: re-run the exact reproduction from #798 (two entries differing only in where the
status sits) against the patched module and confirm the drain now writes nothing, exits 1, and names
the line; then run `check-operator-verification` against this repo's real 19-entry queue and confirm
the output is unchanged for a queue that is entirely well-formed — the fix must be silent on healthy
input. Per L555, each new guard is proven able to go red by mutating a real corpus, not only a fixture.

## Build Chunks

### Chunk 01: Refuse the half-write; make the queue's write path stop damaging the file

- **Description:** One write path carries four defects. A is the reported bug; B, C and D were found
  by reproducing A and hit **well-formed** entries too, which is why they are fixed here rather than
  filed — this module's entire posture is that the queue is an operator-authored record it must not
  damage, and B and D damage one on every single drain.

  **Defect A — the half-write and the false success (#798, #788).** `_set_status_line` correctly
  returns `False` when no bare `**Status:**` line matches; `mark_verified` discards it and appends the
  `**Verified:**` footer unconditionally. `mark_accepted` has the identical shape and the identical
  discarded boolean — neither report mentions it, and one fix covers both. Observed: status untouched,
  a `**Verified:**` footer asserting the opposite, exit 0 printing `Marked VRF-102 verified`, and one
  further footer appended per re-run.

  **Defect B — the preamble's blank line is eaten on every round-trip.** `parse_operator_verification`
  joins preamble lines with `"\n"` and then re-adds a single trailing newline, which conflates "the
  last preamble line was blank" with "no trailing newline". A parse→format round trip with **no
  mutation** is not identity: `# Title\n\n## VRF-1` → `# Title\n## VRF-1`. In a real queue the preamble
  is a large HTML comment, so each drain closes the gap between it and the first entry.

  **Defect C — the footer collides with the next heading, and doubles the blank above itself.**
  `mark_verified`/`mark_accepted` append `""` then the footer unconditionally. Draining the first of
  two well-formed entries yields `**Status:** verified\n\n\n**Verified:** …\n## VRF-2` — a doubled
  blank above the footer, and no blank at all before the next heading (#788's effect 2).

  **Defect D — every line ending in the file is rewritten.** `_write_queue` calls `atomic_write_text`
  without `newline=""`, so a CRLF queue is silently re-line-ended to LF on the first drain. That
  helper's own docstring names this case: *"Pass `newline=\"\"` from any repair that edits a file the
  product wrote — an operation promising to touch two keys otherwise hands back a whole-file
  reformat on a CRLF repo."* This call site is exactly that and missed it (confirmed by direct call:
  CRLF in, LF out).

- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/api-contract.md` § Error Model (the scheme table's
  state-mutating-writer row), `.prawduct/artifacts/project-preferences.md` (return-value error handling)
- **Deliverables:**
  - `plugin/lib/operator_verification.py` — classify the status line **once** and let both readers
    share it; refuse in the mutators without raising; round-trip the preamble; one footer-appending
    helper; preserve line endings on write.
  - `tests/test_operator_verification.py` — regression tests, listed below.
  - `plugin/templates/operator-verification.md` — call out the combined-metadata shape by name.
  - `.prawduct/operator-verification.md` — the same call-out plus the ruling.
  - `.prawduct/artifacts/api-contract.md` § Error Model — record the new refusal *class* on the two
    mutators (no new code; the row is about what `1` now covers).
  - `.prawduct/change-log.md` — entry tagged `scope=verification-drain-half-write`.
  - **`plugin/bin/prawduct-hook` — expected to need no change.** Stated as a deliverable-shaped
    expectation so that touching it is a deliberate act rather than drift.

- **Design constraints (these are the fix, not decoration):**
  1. **One walk, two readers.** `status` and the new diagnostic must not each walk `body_lines` with
     their own copy of the rule — that is the defect being fixed, reintroduced one scope up. A single
     private classifier returns `(status, defect)`; both properties read it. Export the answer, not
     the walker (L525): the classifier stays private, the *defect* is what callers see.
  2. **`status` is unchanged on every input.** Gating behaviour is untouched: a defective entry still
     reads `pending` and still blocks. The diagnostic is additive, and only a caller that can act on
     the reason consumes it. Three defect kinds are distinguishable and each earns a different
     sentence: no status line at all, a first non-blank line that is not a status line, and a
     well-shaped line carrying an unrecognised token.
  3. **Refuse before mutating, and without raising.** The mutators consult the classification and
     return whether they acted, *before* appending anything — nothing written, no partial state, no
     new exception in governance internals (see § Known Non-Conformance).
  4. **`accept` is all-or-nothing.** `run_accept_pending` writes once after its loop, so one defective
     entry aborts the whole override with nothing written. That is the correct behaviour and it must be
     tested rather than merely inherited: a bypass that silently fails to cover one entry is precisely
     the "recorded decision about work that was never seen" the module already refuses elsewhere.
  5. **Never rewrite the operator's file to satisfy the tool.** No auto-repair, on any path. The
     refusal names the edit; the human makes it. The existing unreadable-queue messages already say
     this and the new ones match.
  6. **The message must name the edit that actually works.** #798 records that hand-editing the
     combined line *in place* does not help — the parse and the write share the rule. So the message
     says to put `**Status:** <token>` on a line of its own, and quotes the offending line back.
  7. **Messages name no prawduct-internal identifier** (`observability-strategy.md` § Direction), and
     stderr carries the human diagnostics.

- **Tests:**
  - unit — the classifier over all four shapes (valid, no status line, unparsed first line, unknown
    token), asserting `status` is `pending` for all three defective ones (strictness preserved);
  - unit — `mark_verified` and `mark_accepted` each refuse a defective entry **and leave
    `body_lines` unmodified** (the no-partial-write contract, asserted on the object, not the file);
  - unit — parse→format is identity for well-formed content, including the preamble blank line (B);
  - unit — draining the first of two entries leaves exactly one blank line above the footer and one
    before the next heading (C);
  - unit — a CRLF queue keeps CRLF across a drain (D);
  - integration — `run_verify_entry` on a defective entry returns `error`, and the file on disk is
    **byte-identical** to before (the strongest statement of "writes nothing");
  - integration — `run_verify_entry` twice on a defective entry is byte-identical both times
    (idempotence, the third of #788's effects);
  - integration — `run_accept_pending` with one good and one defective pending entry writes nothing
    and leaves the good entry pending (constraint 4);
  - integration — `run_check_operator_verification` names the defective entries and does not offer the
    drain remedy for them;
  - dispatch — `verify-operator-verification` exits 1 on a defective entry with the offending line on
    stderr; a well-formed entry still exits 0 with unchanged output.

- **Acceptance criteria:**
  - The #798 reproduction, run verbatim, refuses: nothing written, exit 1, the offending line quoted.
  - `check-operator-verification` against this repo's real 19-entry queue produces output identical to
    before the change — the fix is silent on healthy input.
  - Full suite passes.

- **Critic mode:** final
- **Type:** bugfix
- **Foreign API:** none
- **Exposed API:** `run_check_operator_verification` and `run_verify_entry` result dicts gain keys;
  no exit-code or flag change. Additive.
- **Visual change:** no

- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status
