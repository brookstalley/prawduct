# Issue #186 — `tests_are_current` fails open with no session marker: Design

`status: draft · stage: design · area: gates · added: 2026-08-11 · source:
scheduled backlog session · issue: https://github.com/brookstalley/prawduct/issues/186`

Builds on `documentation/issues/STH-6D4Q-requirements.md` (the requirements pass for this same
backlog item, filed under its pre-Issues-migration id `STH-6D4Q` — this design keeps that filename
rather than duplicating it, and is filed under the GitHub issue number per the current naming
convention). Resolves the requirements doc's §5 design questions and specifies changes a build chunk
can follow directly: which of the three candidate fix shapes to take, the shared reflection-freshness
concept Success Criterion 2 requires, the regression tests, and the one documentation correction that
survived the 2026-07-27 PR-review partial fix.

## 0. What's already fixed, so this document doesn't re-litigate it

The requirements doc's "Half Three" (the `build-plan-session-boundary-events.md` documentation
defect) is **mostly already corrected**. Re-verified 2026-08-11: the Chunk 01 `[DECISION]` at
`.prawduct/artifacts/archive/build-plan-session-boundary-events.md:265-271` now carries an explicit
"Correction (PR review, 2026-07-27)" admitting the fail-closed claim was false and stating the true
behavior (`gates.py:156` returns `True`, i.e. fail-open). **What was missed:** Success #5, three
sections earlier in the same document (line 176), still reads *"No gate semantics change except in
the fail-closed direction"* — the same false claim, uncorrected. This document's §4 fixes that one
line; everything else in Half Three is done.

## 1. Fix shape: extend the tree-validity clause to the no-marker case (candidate 1)

Chosen over the requirements doc's other two candidates:

- **Candidate 2** (stamp an anchor at the R-15 notice site) was already rejected once, per the
  backlog item's own note, and re-examining it isn't necessary — candidate 1 solves the problem
  without touching anchor-writing lifecycle at all, which is explicitly out of scope (requirements
  doc §4).
- **Candidate 3** (freshness check on the reflection readers alone) doesn't address the primary
  fail-open (`tests_are_current`'s no-marker branch) — it only closes Half Two. It's adopted below
  in §2, but as a *supplement* to candidate 1, not a replacement.

**Why candidate 1 is sound:** `_test_evidence_tree_valid` (`gates.py:160-196`) is already a pure,
session-marker-independent function — it takes `project_dir` and a `recorded_tree` SHA and answers
"has anything judgeable changed since that tree" using `evidence.capture_tree` / `evidence.tree_diff`
/ `coverage_algebra.judgeable_files`. Nothing in its body reads `.session-start`. It is only ever
*called* from inside the `if session_start:` branch (`gates.py:143-151`) — that's a call-site
restriction, not a functional one. Calling it from the no-marker branch too requires no new
primitive, only a new call site.

**Current code** (`gates.py:154-157`):

```python
    # No session-start marker — fall back to recency check.
    # Evidence exists with passing tests and a timestamp, but we can't verify
    # it's from this session. Accept it with a note.
    return True, f"evidence has passing tests ({evidence_ts}, no session marker to verify)"
```

**Replacement:**

```python
    # No session-start marker — degrade rather than skip the check entirely
    # (STH-6D4Q). A marker-absent context gets exactly the fallback the
    # marker-present-but-stale path already has: the tree-validity clause. It
    # can only relax, never manufacture a false stale (same guarantee the
    # with-marker path relies on), so this cannot newly reject evidence that
    # genuinely reflects the current tree.
    recorded_tree = evidence.get("evidence_tree")
    if isinstance(recorded_tree, str) and recorded_tree:
        tree_valid, tree_reason = _test_evidence_tree_valid(project_dir, recorded_tree)
        if tree_valid:
            return True, f"no session marker; tree-valid — {tree_reason}"
        return False, (
            f"no session marker and working tree diverged since the recorded "
            f"run: {tree_reason}"
        )
    return False, (
        f"no session marker and no evidence_tree to validate against "
        f"({evidence_ts}) — rerun tests inside a governed session or with a "
        "verifier that captures evidence_tree"
    )
```

**What this changes in practice:**

1. Evidence carrying `evidence_tree` (the normal `record` on-ramp — `evidence.capture_tree` runs on
   every record except `--from-counts`, per `_EVIDENCE_OPTIONAL_FIELDS`'s docstring at
   `gates.py:71-77`) now passes the no-marker path only when the tree is provably unchanged —
   exactly the same bar the with-marker path already applies to *stale* evidence. No new concept.
2. Evidence without `evidence_tree` (pre-clause records, or the `--from-counts` on-ramp — confirmed
   at `tests/test_plugin_runtime.py:2066`, `"evidence_tree" not in ev` for `--from-counts`) can no
   longer pass on a bare timestamp when there's no marker. This is the fail-open closing: previously
   this was the *only* case the no-marker branch had to handle, and it always passed.

**Success Criterion 1 met:** no path remains where the gate certifies evidence current on nothing but
a timestamp and a passing-test count — the no-marker branch now requires either a session marker
(existing with-marker logic) or a validated tree (this change); absence of both fails closed.

**Regression check against Success Criterion 5 (a documented ungoverned-context carve-out).**
Searched for one before writing this section: no test in `tests/test_plugin_runtime.py` exercises
`test-status` with no session marker present at all — every `test-status`/`tests_are_current`-adjacent
test (`test_record_makes_test_status_current`, `TestFromCountsIngest`, the tree-validity suite around
line 1977) calls `_make_session_start` first. No governing doc (`architecture.md`,
`building.md`, the `--from-counts` docstring) names an intentional no-marker-but-still-current
context. **The no-marker path today has zero test coverage of its permissive branch** — consistent
with the backlog item's characterization of it as an unexercised fail-open, not a deliberately relied
on capability. `[ASSUMPTION: confirmed by search, not just inferred | if a product-specific
ungoverned context surfaces later that legitimately wants the old permissive behavior, it should
capture `evidence_tree` via a real `record` call rather than reopening this gate]`.

## 2. Reflection freshness: one shared concept (Success Criterion 2)

**The gap, re-verified against the current tree (2026-08-11, line numbers drifted from the
requirements doc's 2026-08-02 citations as expected):**

- Blocking gate: `plugin/bin/prawduct-hook:1751-1759` — `reflection_sufficient = len(content) >= 50`.
- Advisory warning: `plugin/lib/briefing.py:1644-1650` — `len(reflected_file.read_text().strip()) < 50`.

Both check presence + length only. Neither can distinguish this session's reflection from one
`cmd_clear` preserved because archival failed (`prawduct-hook:703-742`, `reflection_preserved`).

**The shared concept, mirroring `tests_are_current`'s own definition of fresh** (content newer than
the session boundary) **but applied via mtime, because `.session-reflected` carries no embedded
timestamp the way `.test-evidence.json` does:**

Trace the write order in `cmd_clear` (`prawduct-hook:703-767`): the reflection preserve-or-archive
decision runs first (703-742); the `doomed` deletion loop that removes the *old* `.session-start` runs
next (748-758); the *new* `.session-start` is written last, at line 767. So whenever
`reflection_preserved` is `False` (archival failed) and `.session-reflected` survives the boundary
untouched, its mtime is strictly older than the new `.session-start`'s — the new marker is always
written after the old reflection file was last modified in that scenario, by construction of the
function's own ordering. A reflection genuinely written *during* the current session (the documented
"reflect as you go" pattern, `building.md`) is appended to *after* `.session-start` already exists, so
its mtime is naturally newer. The same comparison — file content strictly newer than the current
session's start — answers both halves.

**New shared helper, `gates.py`** (beside `_read_session_start`, same module per the file's own
"Holds the gate decision helpers" charter):

```python
def reflection_is_current(prawduct_dir: Path) -> tuple[bool, str]:
    """Whether `.session-reflected` reflects the current session, not a
    reflection `cmd_clear` preserved (`reflection_preserved` at
    `prawduct-hook:703-742`) because archival failed on a prior boundary.

    Mirrors `tests_are_current`'s own freshness concept (content newer than
    the session marker) via mtime, since this file carries no embedded
    timestamp. No marker present means no boundary to compare against —
    unlike `tests_are_current`, that case is left permissive: reflection is
    advisory (or gated per build-plan presence, never the sole freshness-of-
    truth check `tests_are_current` is), so there is no equivalent fail-open
    risk to close here.
    """
    reflected = prawduct_dir / ".session-reflected"
    try:
        content = reflected.read_text(encoding="utf-8").strip()
    except OSError:
        return False, "no .session-reflected"
    if len(content) < 50:
        return False, "reflection shorter than 50 chars"
    try:
        session_start_mtime = (prawduct_dir / ".session-start").stat().st_mtime
    except OSError:
        return True, "sufficient length; no session marker to compare against"
    if reflected.stat().st_mtime < session_start_mtime:
        return False, "reflection predates the current session (carried over from a failed archive)"
    return True, "sufficient length and written during the current session"
```

**Call-site changes:**

- `prawduct-hook:1751-1759` — replace the inline `len(content) >= 50` block with
  `reflection_sufficient, _reason = _gates().reflection_is_current(prawduct_dir)`.
- `briefing.py:1644-1650` — replace the inline `len(...) < 50` check with
  `if not gates.reflection_is_current(prawduct_dir)[0]: warnings.append("reflection not captured")`.

Both readers already import their respective gate module (`_gates()` lazy accessor in the hook,
direct `gates` import in `briefing.py` per its existing `gates._read_gates_waived` call at line
1638), so no new dependency.

**Why not require an embedded timestamp instead.** Rewriting `.session-reflected` to a structured
format (JSON with a `written_at` field, matching `.test-evidence.json`'s shape) was considered and
rejected for this pass: it would require migrating every reader/writer of a currently-freeform
append-only text file (`building.md`'s documented "reflect as you go" workflow appends raw prose),
for a freshness signal the mtime comparison already provides exactly. Scoped out (§5) as a possible
future normalization, not needed to close this gap.

## 3. What does NOT change

- `_read_session_start` (`gates.py:199-207`) — unchanged; still the single source of the marker
  content string used by the with-marker branch.
- The with-marker branches of both `tests_are_current` (lines 139-152) and the reflection readers —
  unchanged; this item only touches the no-marker/carried-over-file degenerate cases.
- `cmd_clear`'s `reflection_preserved` control flow (`prawduct-hook:703-742`) — unchanged; it's
  already correct per the requirements doc's own re-verification (§1's "net improvement, not a new
  hole" finding stands).
- Anchor-writing lifecycle (when `.session-start` gets created) — explicitly out of scope per the
  requirements doc §4; nothing here changes when or whether a marker is written, only what happens
  when one is absent.

## 4. Documentation correction

`.prawduct/artifacts/archive/build-plan-session-boundary-events.md:176`, Success #5, currently reads:

> 5. No gate semantics change except in the fail-closed direction; full suite green; `/clear` is never
>    blocked or slowed by any of this.

Correct to match the correction already made three sections later at lines 268-271 (the false
"freshness gates fail closed" claim was retracted there but this earlier restatement of the same
claim was missed):

> 5. **Correction (documented alongside the Chunk 01 DECISION correction, PR review 2026-07-27):**
>    this originally also asserted "no gate semantics change except in the fail-closed direction."
>    That repeats the same false premise corrected at the Chunk 01 `[DECISION]` above —
>    `tests_are_current`'s no-marker path fails OPEN, not closed (`gates.py:154-157` before
>    STH-6D4Q; see `documentation/issues/186-design.md` for the fix). No gate semantics changed as
>    part of *this* plan's own work — the false claim was about pre-existing behavior this plan
>    didn't touch, not about a regression it introduced. `/clear` was, and remains, never blocked or
>    slowed by any of this.

This is a documentation-only edit to an archived planning artifact — no code or test implication,
included in the same build chunk as §1/§2 only because it's cheap and was named by the requirements
doc as in-scope, not because it's coupled to the code change.

## 5. Files touched

| File | Change |
| --- | --- |
| `plugin/lib/gates.py` | rewrite `tests_are_current`'s no-marker branch (§1); add `reflection_is_current` (§2) |
| `plugin/bin/prawduct-hook` | reflection blocking-gate check (~line 1751) calls `_gates().reflection_is_current` instead of inlining the length check |
| `plugin/lib/briefing.py` | reflection advisory warning (~line 1644) calls `gates.reflection_is_current` instead of inlining the length check |
| `.prawduct/artifacts/archive/build-plan-session-boundary-events.md` | correct Success #5 (§4) |
| `tests/test_plugin_runtime.py` | new coverage — see §6 |

## 6. Testing strategy → Acceptance mapping

- **No-marker + `evidence_tree` present + tree unchanged → current.** New test: seed evidence via a
  real `record` (captures `evidence_tree`), delete `.session-start`, assert `test-status` returns 0.
  Direct analog of the existing `test_restart_no_change_is_current` (line 1979) but without a marker.
- **No-marker + `evidence_tree` present + judgeable change → stale.** Same seed, edit a judgeable
  file (e.g. `src/app.py`, matching the pattern at line 2014), delete `.session-start`, assert
  `test-status` returns 1. This is the requirements doc's Success Criterion 4 repro, adapted to the
  no-marker case it's actually about.
- **No-marker + no `evidence_tree` (`--from-counts`) → stale, closing the literal reported bug.**
  Record via `--from-counts` (no marker set at all, unlike the existing
  `test_makes_test_status_current` at line 1674 which sets one first), assert `test-status` returns 1
  with a reason naming the missing `evidence_tree`. This is the exact fail-open the issue reports:
  today this combination returns 0.
- **With-marker paths unaffected.** No changes needed to the with-marker tests already passing
  (lines 1315-1319, 1674-1679, 1977-2069 range) — run them unmodified as the regression backstop that
  §1's change doesn't touch that branch.
- **`reflection_is_current` unit tests** (new, alongside existing gate tests): no file → not current;
  short content → not current; long content + no marker → current (permissive, per §2's design);
  long content + mtime older than marker → not current (the carried-over-from-failed-archive case);
  long content + mtime newer than marker → current.
- **Integration: the blocking reflection gate rejects carried-over text.** Simulate the
  `reflection_preserved=False` scenario end-to-end (write `.session-reflected`, then a *newer*
  `.session-start`, mimicking the write-order established in §2), assert `cmd_stop`'s reflection
  gate still blocks — this is Success Criterion 2's acceptance test, distinct from the unit-level
  check above.
- **Success Criterion 3** (the doc correction) is verified by the corrected text existing at the
  cited line, not by a runtime test — same treatment `221-design.md` gives its own doc-only
  scope items.

## 7. Scope-out (unchanged from requirements, no additions)

Carries forward `STH-6D4Q-requirements.md` §4's scope-out list verbatim: re-litigating the removal of
`resume`'s accidental re-anchoring, any change to when `.session-start` markers are created (beyond
this fix's read-only use of the marker's presence/mtime), and COV-3R9K-family coverage-floor work.
Nothing in this design pass surfaced a need to widen that list.

## 8. Evidence / references

- `documentation/issues/STH-6D4Q-requirements.md` — the requirements pass this design builds on
  (Problem, Success Criteria 1-5, §5's three candidate fix shapes).
- `plugin/lib/gates.py:81-157` (`tests_are_current`), `:160-196` (`_test_evidence_tree_valid`,
  reused unchanged), `:199-207` (`_read_session_start`), `:71-77` (`evidence_tree`'s docstring,
  confirming it's omitted rather than null on the on-ramps that don't capture it) — all re-verified
  against the current tree 2026-08-11.
- `plugin/bin/prawduct-hook:703-767` (`cmd_clear`'s reflection preserve/delete + marker rewrite,
  establishing the write-order §2 relies on), `:1751-1759` (the blocking reflection-gate reader).
- `plugin/lib/briefing.py:1640-1650` (the advisory reflection-gate reader), `:1431-1441` (a third,
  non-gating reader — the handoff-content assembly step, which surfaces reflection text for human
  reading rather than gating on it; left unchanged, out of scope, since a stale-but-present
  reflection being shown in a handoff is not a false "you did this" governance claim the way passing
  a blocking gate is).
- `.prawduct/artifacts/archive/build-plan-session-boundary-events.md:176` (Success #5, uncorrected),
  `:265-271` (the Chunk 01 `[DECISION]`'s existing correction, the model §4's correction follows).
- `tests/test_plugin_runtime.py:206-208` (`_make_session_start` helper), `:1315-1319`,
  `:1674-1679`, `:1977-2069` (existing with-marker test coverage this design leaves unmodified),
  `:2048-2069` (`--from-counts` captures no `evidence_tree`, the precondition §1's third branch
  exercises).
