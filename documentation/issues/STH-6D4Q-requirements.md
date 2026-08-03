# STH-6D4Q — `tests_are_current` fails open with no session marker

`status: draft v1 — 2026-08-02 · backlog: STH-6D4Q · stage: requirements · area: gates · kind: bug
· related: SCN-5B8Q, SCN-4H9T, STH-7W9K, COV-3R9K`

**Parent:** `.prawduct/backlog.md` STH-6D4Q, filed from cumulative Critic review fact
`rev-20260727T164842Z-1b70981d` (branch `feature/session-handoff-continuity`, 2026-07-27). This
document is the requirements pass the backlog item calls for before design — the bug's mechanism,
evidence, and blast radius were already established at filing time; nothing here is new discovery,
it is that material organized into a requirements artifact per Principle 6.

## 1. Problem

`tests_are_current()` (`plugin/lib/gates.py`) is the gate every quality check in the framework
relies on to answer "is the saved test evidence still trustworthy?" It has two independent
freshness paths depending on whether `.prawduct/.session-start` exists:

- **With a session marker** (`gates.py:139-152`): evidence younger than the marker passes
  immediately; older evidence still passes if the *tree-validity clause* (`_test_evidence_tree_valid`,
  `gates.py:160-196`) shows nothing judgeable changed since the recorded run. Either way, something
  is actually checked.
- **Without a session marker** (`gates.py:154-157`): the function returns `True` — evidence with
  passing tests and *any* timestamp is accepted, "no note to verify" — verbatim: *"evidence has
  passing tests (…, no session marker to verify)"*. The tree-validity clause is not reached on this
  path; it lives inside the `if session_start:` block above it (verified against the tree
  2026-08-02, current at `gates.py:139` / `:154`). Arbitrarily old passing evidence, from any tree
  state, satisfies the gate whenever the marker is simply absent.

**This is a genuine fail-open, not a hypothetical.** The marker can be absent for reasons that have
nothing to do with evidence being trustworthy: a session run outside normal `prawduct-hook`
lifecycle management, a marker deleted or never written for any reason, or (per the second half of
this item) an unanchored worktree. What changed in the 2026-07-27 bundle is not the fail-open
itself — it predates that work — but how long a working copy stays in the unmarked state. The old
session-boundary reset used to write `.session-start` incidentally on `resume`, which accidentally
re-anchored an unanchored worktree at the next boundary. `feature/session-handoff-continuity`
deliberately removed that accidental repair (replacing "silent-and-sometimes-destructive" with
"loud-and-never-destructive", per an R-15 notice at the removal site) — the right call on its own
terms, but it means an unanchored worktree can now stay unanchored indefinitely, and every day it
does, the no-marker fail-open is the *only* freshness check any gate consuming
`tests_are_current()` gets.

**A secondary, narrower gap rides on the same missing concept — no freshness check.** Gating the
`.session-reflected` unlink on `reflection_preserved` (`prawduct-hook:647-693`) is a net
improvement over the prior behavior, not a new hole: the flag starts `True`, flips `False` only
once the file is found to exist, and returns `True` the moment archival succeeds — including the
empty-content case. So the file survives a boundary only when archival genuinely failed (a
`UnicodeError`/`OSError`), and that path already prints an attributed `NOTE:` that names the
failure and says it will retry. The residue: both readers of `.session-reflected` —
`prawduct-hook:1471` (the blocking reflection gate) and `briefing.py` (the warning) — check only
presence and `len(content) >= 50`. Neither checks freshness. So in the one session immediately
following a failed archive, the blocking reflection gate can be satisfied by the *previous*
session's leftover text. This is gated behind an announced I/O failure, not a path a normal
boundary reaches, but it is the same missing concept (no-marker/no-anchor freshness) surfacing a
second time, and belongs in the same requirements/design pass rather than a separate item.
(Current line numbers, re-verified 2026-08-02: `prawduct-hook:647-693` for the archival guard,
`prawduct-hook:1509-1515` and `briefing.py:1333-1336` for the two readers.)

**A documentation defect rides alongside, and needs no design work — only correction.** Two
governing-artifact statements assert the opposite of what the code does:
`.prawduct/artifacts/build-plan-session-boundary-events.md` Chunk 01's `[DECISION]` states *"An
absent anchor already has a documented degradation (**freshness gates fail closed**...)"*, and
Success #5 states *"No gate semantics change except in the fail-closed direction."* Both are false
against `gates.py:154-157` today, and the DECISION's stated rationale for `--brief-only` never
writing an anchor rests on that false premise. This is a Living Documentation violation
(Principle 3) in a load-bearing planning artifact, independent of whether/how the code changes.

## 2. Why this matters (impact)

`tests_are_current()` backs the framework's core promise that a session cannot claim "tests pass"
on evidence that doesn't actually cover the current tree (Principle 1 — Tests Are Contracts). The
gate is consumed wherever test-evidence freshness gets checked — build-cycle gates, the stop hook,
Critic pre-review checks — across every product this framework governs, not just this repo. A
fail-open on the no-marker path means the one condition under which the framework has *no* real
signal to fall back on is exactly the condition where it currently asserts the strongest claim
("evidence has passing tests") with the weakest basis (a timestamp and a schema check only).
Because the marker-absent state is now reachable indefinitely rather than self-healing at the next
`resume`, the exposure window grew from "next boundary" to "however long the session stays
unanchored" — which is the concrete way this bundle raised the item's urgency without changing the
underlying defect.

## 3. Success criteria

Design work following this document should converge on a fix where:

1. **No practical path exists for the gate to certify evidence as current on nothing but a
   timestamp and a passing-test count.** Absence of a session marker degrades the check, it does
   not remove it. (Whether the degraded check is the existing tree-validity clause extended to the
   no-marker case, an anchor stamped at a different point in the lifecycle, or another mechanism is
   a design decision — out of scope for this document.)
2. **The freshness gate and the reflection gate share one definition of "fresh".** Whatever concept
   closes Half One should also answer Half Two's residue (can a reader tell current-session content
   from carried-over content?) rather than leaving it as a separate unaddressed gap.
3. **`build-plan-session-boundary-events.md`'s Chunk 01 `[DECISION]` and Success #5 are corrected to
   state what the gates actually do**, and the `--brief-only`-never-writes-an-anchor decision is
   re-derived on a true premise (it may still hold, e.g. on the "don't stamp a resume-time clock"
   rationale alone — that re-derivation is design/build work, not requirements work).
4. **A regression test exists that fails on the current fail-open** — evidence with an old timestamp,
   no session marker, and a working tree that has clearly changed judgeable files since the evidence
   was recorded must NOT pass `tests_are_current()` once the fix lands.
5. **No existing legitimately-passing case regresses.** In particular: a session that genuinely has
   no marker by design (e.g. a context this framework intentionally runs ungoverned in) must not be
   newly broken by closing the fail-open — if such a context exists, the fix's design phase must
   name it explicitly rather than discover it as a regression.

## 4. Scope

**In scope for the design phase this document feeds:**
- The no-marker fail-open in `tests_are_current()` (`gates.py:154-157`).
- The freshness blind spot in the two `.session-reflected` readers (`prawduct-hook:1471`,
  `briefing.py`), to the extent it shares a fix with the above.
- Correcting the two false statements in `build-plan-session-boundary-events.md`.

**Out of scope (explicitly deferred, not silently dropped):**
- Re-litigating the removal of `resume`'s accidental re-anchoring — that trade (documented via the
  R-15 notice) is treated here as settled; this item is about what happens *given* that an
  unanchored worktree can now persist, not about reversing the removal.
- Any change to how `.session-start` markers are created in the first place, beyond what a chosen
  fix requires — a broader audit of anchor-writing lifecycle is a separate concern (see
  `related: STH-7W9K`, which covers markers being written to the wrong directory in worktree/fork
  contexts).
- COV-3R9K-family coverage-floor work — related by the same evidence machinery, not by this defect.

## 5. Design questions to settle next (stage: design)

The backlog item's owner-provided evidence already narrows the design space to three candidate
shapes; none is selected here — that is the design pass's job:

1. **Extend the tree-validity clause to the no-marker case.** Answers "has anything judgeable
   changed" without needing a session clock at all — plausibly the cheapest sound option, since the
   existing clause (`_test_evidence_tree_valid`) already does exactly this comparison for the
   with-marker path.
2. **Stamp an anchor at the R-15 notice site** (the point where a failed reflection-archive is
   announced) — noted in the backlog item as "rejected once already, for good reason"; the design
   phase should record that reasoning explicitly if this option is re-examined and re-rejected, per
   Principle 4 (Reasoned Decisions).
3. **Add a freshness check to the two reflection readers directly** — needs a working definition of
   "fresh" that a legitimately long-running session does not trip (a long session's reflection
   written early should not itself count as stale).

Design must also decide whether the fix is symmetric (one mechanism closes both halves) or requires
two independent changes, and must specify the regression test from Success Criterion 4 concretely
enough to build against.

## 6. Confidence & assumptions

- **Verified, not inferred:** the fail-open at `gates.py:154-157`, the tree-validity clause's
  placement inside the `if session_start:` branch, the `reflection_preserved` control flow in
  `prawduct-hook`, and both readers' presence-and-length-only check — all re-confirmed against the
  current tree while writing this document (2026-08-02), consistent with the backlog item's
  2026-07-27 findings. Line numbers cited here reflect the current tree and may drift by a few lines
  as unrelated work lands; re-verify at design/build time rather than trusting these numbers
  verbatim (Principle 24).
- `[ASSUMPTION: no product currently depends on the no-marker path's permissive behavior as
  intentional design (e.g. a documented ungoverned-context carve-out) | HIGH impact if wrong | the
  design phase must search for such a carve-out before tightening the gate, and the fix owner can
  override this assumption if one is found]`
- **Governance-protected surface.** `gates.py` and `prawduct-hook` are both governance-protected
  (gates + session-boundary machinery) — the eventual build needs full Critic + PR review, matching
  the backlog item's own note.

## 7. Traceability

- Backlog: `.prawduct/backlog.md` → `STH-6D4Q` (full evidence trail, `refs:`, and the critic review
  fact this was filed from).
- Code: `plugin/lib/gates.py` (`tests_are_current`, `_test_evidence_tree_valid`,
  `_read_session_start`), `plugin/bin/prawduct-hook` (reflection archival + reflection gate),
  `plugin/lib/briefing.py` (reflection warning reader).
- Governing artifact requiring correction: `.prawduct/artifacts/build-plan-session-boundary-events.md`
  (Chunk 01 `[DECISION]`, Success #5).
- Related backlog items: `SCN-5B8Q`, `SCN-4H9T` (session-boundary-events work that removed the
  accidental re-anchoring), `STH-7W9K` (marker written to the wrong directory in worktree/fork
  contexts — adjacent but distinct), `COV-3R9K` (the coverage-floor sibling of the same
  test-evidence machinery).
