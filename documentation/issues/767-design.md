# Issue #767 — `prawduct-hook test-status`: `current` on a Stale Tree: Design

`status: draft · stage: design · area: test-evidence · added: 2026-09-16 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/767`

No `documentation/issues/767-requirements.md` exists — the owner's 2026-09-10 triage comment
(`#767#issuecomment-5625111162`) already did the requirements-grade work directly on the issue:
confirmed the mechanism by inspection, named the exact clause and line range, corrected the report's
scope twice, and named the fix as "a genuine either/or with a real cost on both sides." This
document takes that triage as its grounding, resolves the either/or, and specifies the change an
implementation chunk can follow directly. It does not re-derive what the triage comment already
established; it cites it.

## What the triage comment already settled — restated, not re-derived

Read in full at the issue; the load-bearing facts:

1. **Confirmed root cause.** `gates.tests_are_current` (`plugin/lib/gates.py:161-231`) returns on
   the session-fresh disjunct (`:210-211`) before `evidence.get("evidence_tree")` is ever read.
   Within one session, `test-status` prints `current` for *any* tree however far HEAD has advanced.
2. **Not a bug against its own spec.** The docstring (`:164-179`) names this disjunct
   deliberately — "the trust the cycle model: write code → run tests → Critic reviews." Session
   freshness is disjunct 1; disjunct 2 (`_test_evidence_tree_valid`, tree-keyed) only ever
   *relaxes* a stale verdict to current, never the reverse.
3. **Narrower blast radius than filed.** `gates.suite_vouches_for_tree` (`:312-363`) is the
   strictly-tree-keyed predicate, "deliberately STRICTER than `tests_are_current`," and it is what
   the PR gate's base-advance transfer and the Stop gate actually consult — not
   `tests_are_current`. So the blocking coverage gates are not exposed to the false-current defect.
4. **What is exposed, and is the real bug: a contract mismatch.** Three governing-artifact call
   sites tell their readers exit 0 means *tree* coverage, which is exactly what disjunct 1 does not
   establish (exact wording and line numbers in Decision 1 below). The implementation delivers
   session recency; every reader was written against tree coverage.
5. **The either/or the triage names, verbatim:**
   - (a) tree-key `test-status` (drop or gate disjunct 1) — correct-by-construction, but forces a
     suite re-run after every commit within a session, reversing the cost #653 was filed to avoid
     and pushing directly against it;
   - (b) keep disjunct 1, make the output disclose which disjunct answered and which tree the
     evidence covers, and correct the three call sites to claim only what exit 0 actually means.

This document resolves that either/or as **(b)**, and specifies it.

## Decision 1 — (b), not (a): keep disjunct 1, make it honest

**(a) is rejected.** Tree-keying `test-status` (or gating disjunct 1 behind a tree check) turns
every post-commit `test-status` call inside a session into a full tree diff *and*, per the
docstring's own accounting, removes the property #653 exists to protect: a session that has
already run the suite once should not re-pay a ~7-minute/~27k-test run for every subsequent commit
that a Critic round or a fix cycle produces, when nothing about the reason `disjunct 1` was chosen
(the "trust the cycle" model) has stopped being true. #653's own filed cost — "one `/clear`
invalidated evidence for four branches, each then paying a ~7.3-minute re-run" — is exactly the
shape (a) would generalize from "session boundary" to "every commit." Rejecting (a) is not new
policy; it is declining to re-litigate a trade the docstring already made and named.

**(b) is adopted**, and it costs nothing on the re-run axis: `_test_evidence_tree_valid`
(`:234-309`) is a git tree-diff plus a path classification, not a test run. It is already computed
on every call where disjunct 1 does *not* fire. This design changes exactly one thing: compute the
same cheap check when disjunct 1 *does* fire too, purely to make the returned reason honest about
which question was actually answered — not to gate on the result. No exit code changes, no new
re-run is forced, and #653's whole point survives untouched.

## Decision 2 — a structural `clause` field, not a parsed string

`tests_are_current` returns `tuple[bool, str]` today. This design adds a third element:
`tuple[bool, str, str]`, the third being `clause`, one of:

- `"session"` — disjunct 1 answered (evidence timestamp ≥ session start); the tree was not
  consulted.
- `"tree"` — disjunct 2 answered, whether relaxing a stale timestamp (marker present) or as the
  sole clause (no marker, STH-6D4Q's path).
- `"none"` — neither disjunct passed; `is_current` is `False`.

**Why a field and not a reason-string convention.** The only two callers
(`gates.test_status:1295`, `release_readiness._suite_verdict:705`) already destructure a
fixed-width 2-tuple; both are two-line changes. A field is machine-checkable by the regression test
in Decision 4 without a regex against prose that a later wording pass could quietly break. The
alternative — prefixing `reason` with a fixed marker — was considered and rejected: it would make
`reason` do two jobs (human-readable explanation and a parseable tag), and `_suite_verdict` (below)
would need to parse a string it currently only forwards as-is.

**`release_readiness._suite_verdict`** (`plugin/lib/release_readiness.py:677-705`) wraps
`gates.tests_are_current` and returns only `(bool, str)` to its one caller (`:874`, printed
verbatim as `f"suite: green — {suite_reason}."` or the `unproven-suite:` refusal). It needs no
behavior change, only its own return to drop the new third element before returning — its
docstring (`:690-697`) already argues session-freshness is the *correct* bound for this call site
("Phase 0 runs before Phase 1 rewrites four files ... no check at this point can vouch for the tree
the tag will carry"), so `clause` is not needed by its caller and is not threaded further. Decision
3 below does not touch it; it is not one of the three mismatched call sites, and re-verified here
as correctly scoped already.

## Decision 3 — what the CLI prints, and what the three call sites say

### `gates.test_status` (`:1283-1300`)

```python
def test_status(project_dir: Path) -> int:
    """Print whether saved test evidence is fresh enough to trust.

    Used by builders, the Critic, and the PR reviewer to decide whether to
    re-run the test suite.

    stdout: one line — `current (session-fresh, tree not verified): <reason>`,
    `current (tree-valid): <reason>`, or `stale: <reason>`. The parenthetical
    names which of tests_are_current's two disjuncts answered — see #767.

    Exit codes:
      0  - tests are current; safe to skip re-running
      1  - tests are stale or no evidence
    """
    is_current, reason, clause = tests_are_current(project_dir)
    if is_current:
        label = "current (tree-valid)" if clause == "tree" else \
            "current (session-fresh, tree not verified)"
        print(f"{label}: {reason}")
    else:
        print(f"stale: {reason}")
    return 0 if is_current else 1
```

Exit codes are unchanged — this is disclosure, not a new gate. `reason`'s own text is untouched
(`"evidence from this session (...)"`, `"tree-valid despite predating session: ..."`, etc.); the
label is additive context in front of it. Every existing test that asserts on a substring of
`reason` (`"degraded"`, `"no session marker"`, per `tests/test_plugin_runtime.py:2404,2712`)
still matches, since none pins the old bare `current: ` prefix (verified by search: no test in
`tests/test_plugin_runtime.py` asserts that exact prefix as of this pass).

### The three call sites, corrected

**`plugin/skills/pr/SKILL.md:53`** — currently: *"if it exits 0 (`current`), the saved
`.prawduct/.test-evidence.json` already covers the current tree (HEAD + uncommitted edits) and
re-running is wasteful."* That is disjunct 2's claim stated as if it always held. Corrected to:

> Then the suite: run `prawduct-hook test-status` first — exit 0 means either the evidence is
> tree-valid or it is session-fresh (read the printed label: `tree-valid` or `session-fresh, tree
> not verified`). Both are sufficient to skip re-running: a session-fresh run from earlier this
> session covers work done since, by the framework's own trust-the-cycle model (write code → run
> tests → Critic reviews) — it is not a weaker guarantee here, just a different one than tree
> identity. Only run the suite if `test-status` reports `stale` or evidence is missing.

This keeps the operational instruction identical (skip the re-run on exit 0) — the fix is honesty
about *why* it's safe to skip, not a new requirement to run the suite more often. That is the same
shape #653 already relies on and this design declined to disturb.

**`plugin/skills/critic/SKILL.md:65`** — currently: *"run `prawduct-hook test-status` to validate
evidence covers the current tree (exit 1 = stale → WARNING in your review)."* Corrected to:

> Then read `.prawduct/.test-evidence.json` for test results and run `prawduct-hook test-status`
> (exit 1 = stale, or evidence missing → **WARNING** in your review). Exit 0 means the evidence is
> either tree-valid or session-fresh — the printed label says which; no further action needed
> either way, since you are about to read the diff yourself regardless.

The "no further action needed" clause is deliberate: the Critic reviewer reads the changed files
directly as its own step 6, so a session-fresh verdict is not a blind spot for *this* reader the
way it would be for an automated gate — the reviewer's own read of the diff is the tree check. No
new WARNING tier is added for `session-fresh` alone; inventing one would manufacture a finding for
every session-fresh call, which is the false-positive shape Recommendation R5 of #724 named and
this repository already ruled against paying for.

**`plugin/skills/pr/review-protocol.md:69`** — currently: *"validate freshness via
`prawduct-hook test-status` (exit 0 = current, 1 = stale) — that exit code is the *only* freshness
signal."* Corrected to:

> validate freshness via `prawduct-hook test-status` (exit 0 = current, 1 = stale) — that exit code
> is the *only* freshness signal this gate needs; read the printed label if you want to know
> whether it rests on tree identity or session recency, but either satisfies this WARNING.

**`plugin/skills/critic/goals-1-3.md:62`** — same claim family, same fix, one clause: *"exit 0 =
current; stale/missing → **WARNING**"* stays as-is (accurate), no wording change needed — flagged
here only to confirm it does **not** claim tree coverage and needs no correction, so the
grounding pass covers all four `test-status`-consuming skill files rather than leaving one
unchecked.

## Decision 4 — regression coverage

New tests in `tests/test_plugin_runtime.py`, alongside the existing test-status coverage
(`TestDegradedEvidence` at `:2339`, the tree-validity cases around `:2551-2658`):

1. `test_status_labels_session_fresh_evidence_as_tree_unverified` — record evidence, write a
   session-start marker dated before it, advance the tree with a judgeable change, run
   `test-status`: exit 0 (unchanged from today's behavior) and stdout contains
   `"session-fresh, tree not verified"`. This is the report's original repro, now asserting the
   disclosure rather than the (unchanged) exit code.
2. `test_status_labels_tree_valid_evidence_distinctly` — record evidence, advance the tree with
   only non-judgeable changes: exit 0, stdout contains `"tree-valid"` and not
   `"tree not verified"`.
3. `test_status_stale_reason_unaffected_by_the_label_change` — the existing degraded-evidence and
   no-marker cases (`:2404`, `:2712`) re-asserted verbatim to confirm the `stale:` branch and its
   `reason` text are untouched.
4. `test_tests_are_current_clause_field` — direct unit test on `gates.tests_are_current`, one case
   per disjunct (`"session"`, `"tree"`, `"none"`), asserting the third tuple element rather than
   parsing `reason`.
5. `test_suite_verdict_unaffected_by_clause` — `release_readiness._suite_verdict` (`:677-705`)
   returns the same 2-tuple to its caller after being updated to drop the new `clause` element;
   assert its existing green/unproven-suite print strings (`:879`, `:882`) are byte-identical to
   before this change. No existing test in `tests/test_release_readiness.py` exercises
   `_suite_verdict` directly as of this grounding pass (verified: no `_suite_verdict` hit in that
   file) — this is new coverage, not an update to an existing case.

## Files touched

| File | Change |
|---|---|
| `plugin/lib/gates.py` | `tests_are_current` returns `tuple[bool, str, str]` (adds `clause`); `test_status` prints the disjunct-labeled line (Decisions 2–3) |
| `plugin/lib/release_readiness.py` | `_suite_verdict` (`:677-705`) drops the new `clause` element before returning; no behavior change to its own 2-tuple contract |
| `plugin/skills/pr/SKILL.md` | Correct line 53's claim (Decision 3) |
| `plugin/skills/critic/SKILL.md` | Correct line 65's claim (Decision 3) |
| `plugin/skills/pr/review-protocol.md` | Correct line 69's claim (Decision 3) |
| `tests/test_plugin_runtime.py` | Five new/updated cases (Decision 4) |

## Scope-out (explicit, not silent)

- **Recommendation (a)** (tree-keying disjunct 1) — rejected in Decision 1, not deferred; #653
  remains the place a per-tree cache is designed, and this item does not block or gate it.
- **A new Critic WARNING tier for session-fresh-only evidence** — rejected in Decision 3's
  critic/SKILL.md correction; the reviewer's own diff read is the tree check for that call site.
- **`#653`'s per-tree evidence cache** — unrelated mechanism (multiple stored records keyed by
  tree); this item's `clause` field composes with whatever #653 ships without needing to
  anticipate its schema, since `clause` describes *which disjunct of the single current record*
  answered, not which record was consulted.
- **Re-observing #768's failure mode** — unrelated issue, mentioned nowhere in this item's
  grounding; not addressed here.

Next step per the framework's methodology is a build plan against this design.
