# Issue #724 — Critic: A Pre-Dispatch Precondition Check for Stale Test Evidence in `verify-resolutions`: Design

`status: draft · stage: design · area: critic · added: 2026-09-06 · source: scheduled backlog
session · issue: https://github.com/brookstalley/prawduct/issues/724`

Builds on `documentation/issues/724-requirements.md` (PDC1 through PDC7, the Decision scoping this
to `verify-resolutions` alone). This document places the check in `begin_review`'s control flow,
pins the new terminal status and CLI exit code, and specifies file-by-file changes an
implementation chunk can follow directly.

Related: `plugin/lib/critic_consolidate.py::begin_review`'s existing "GATE AS DISPATCHER" free-
interval refusal (`:1960-2053`), the mechanism this item extends by analogy on a second axis (test
freshness instead of path judgeability) without touching that refusal's own code.

## Summary of what ships

1. **PDC1, PDC2, PDC3** — one new precondition block in `begin_review`, gated on `mode_token ==
   "verify-resolutions" and not force`, placed immediately after the existing in-flight guard and
   before every other line of derivation (plan resolution, tree capture, prior-fact lookup). It
   calls `gates.tests_are_current(project_dir)` directly — no new staleness logic, no subprocess.
2. **PDC2** — a new terminal status, `"precondition-failed"`, distinct from `"error"`,
   `"no-review-needed"`, and the `scope-widened` error `kind`. `cmd_critic_begin` maps it to a new
   CLI **exit 4** (0/1/2/3 are all already spoken for — see Grounding in the requirements doc's
   Evidence section and Section 2 below).
3. **PDC4** — the refusal prints the freshness verdict's `reason` string verbatim plus one fixed
   remedy line.
4. **PDC5** — `force` (already a `begin_review` parameter) short-circuits the new block exactly as
   it already short-circuits the free-interval refusal.
5. **PDC6** — one new `evidence.append_guard_refusal` call site, `guard="critic-dispatch-stale-
   evidence"`, following the existing free-interval refusal's soft-failure-attribution pattern
   verbatim.
6. `plugin/skills/critic/SKILL.md`'s step-4 exit-code table gains one row (exit 4); no other skill
   file changes — step 5's post-dispatch `test-status` check is untouched (PDC7) and remains the
   live check for `chunk`/`final`/`cumulative`.

## Decision resolved

### Where the check sits, and why here specifically

The requirements doc's Decision already fixed *what* fires and *for which mode*; the one open
question design must resolve is *where in `begin_review`'s existing 350-line body* the check goes,
because "before deriving the prior-review anchor or writing the manifest" (PDC1) admits more than
one candidate position once the function's actual control flow is read.

`begin_review`'s body, in order, is: **(a)** the in-flight guard (`:1687-1694`) — the only
precondition checked today; **(b)** scope resolution via `buildplan_refs` (`:1702-1708`); **(c)**
`evidence.capture_tree` (`:1710-1723`) — the tree-capture PDC2 names; **(d)** the per-mode branch
(`:1763-1943`), where `verify-resolutions` specifically calls `_prior_review_fact` (`:1784`) — the
prior-fact lookup PDC2 names; **(e)** the free-interval GATE AS DISPATCHER refusal (`:1960-2035`);
**(f)** manifest assembly and the critic-active marker set, both downstream of this in code not
reproduced here.

**Placed immediately after (a), before (b).** Three reasons, each independently sufficient:

- **PDC2's own wording is exhaustive.** It names tree capture, prior-fact lookup, manifest write,
  and the critic-active marker as the things a refusal must precede — that is (c) through (f) in
  the ordering above. The only position preceding all four is directly after (a).
- **The check needs nothing (b) through (e) compute.** `tests_are_current` takes only
  `project_dir` — it reads `.prawduct/.test-evidence.json` and the working tree directly
  (`gates.py:199-231`), independent of scope, the captured tree object, or the prior review fact.
  Placing it later would derive state the refusal then discards, exactly the waste the in-flight
  guard's own docstring calls out for its own position ("everything below derives state that a
  refusal would waste").
- **`mode_token` is already known and validated before (a).** The unknown-mode-token guard
  (`:1643-1651`) runs first and returns its own error before the in-flight guard; the new check
  only needs `mode_token` and `force`, both already in scope, so it costs no new parameter and no
  reordering of what precedes it.

```python
    active, age_s = critic_marker.review_active(prawduct_dir)
    roster_state, _missing = pending_state(prawduct_dir)
    if active or roster_state == "complete":
        return {
            "status": "error",
            "kind": "review-in-flight",
            "reason": active_dispatch_refusal(prawduct_dir, age_s, active),
        }

    # STALE-EVIDENCE PRECONDITION (PDC1-PDC6, issue #724) — verify-resolutions only.
    # `tests_are_current` is the same verdict `prawduct-hook test-status` exposes
    # (gates.py:161-231); no second notion of "stale" is written here. Scoped to
    # this one mode because its own promotion rule (goals-1-3.md step 1: findings
    # here are BLOCKING only) is what turns a routine staleness signal into a
    # full-cost round — chunk/final/cumulative code review has value independent
    # of suite freshness and are structurally unaffected (PDC7).
    if mode_token == "verify-resolutions" and not force:
        from . import gates  # noqa: PLC0415 — lazy; mirrors the coverage_algebra import below

        current, why_not = gates.tests_are_current(project_dir)
        if not current:
            recorded = evidence.append_guard_refusal(
                project_dir,
                "critic-dispatch-stale-evidence",
                {
                    "mode": mode_token,
                    "reason": why_not,
                    "branch": gitstate.current_branch(project_dir),
                },
            )
            if recorded.get("status") != "appended":
                print(
                    "critic-begin: the refusal is correct but was NOT recorded "
                    f"({recorded.get('reason', 'unknown')}) — this firing is missing "
                    "from `prawduct-hook evidence list --kind guard-refusal`, so read "
                    "that query as a lower bound.",
                    file=sys.stderr,
                )
            return {
                "status": "precondition-failed",
                "reason": why_not,
            }

    # Which plan this review is OF. ...
```

`why_not` is printed **verbatim** (PDC4) — never wrapped in a re-derived sentence — so the reason a
builder reads here can never drift from the reason `test-status` alone would have printed for the
same tree. No `free_files`/`excluded_wip`/`anchor` triple: those exist on the free-interval refusal
because that refusal is *about* which files an interval excludes, a question this refusal does not
ask — the remedy is identical regardless of which files are stale (run the suite, record it).

**`force` short-circuits by construction, not by a separate check (PDC5).** The condition is `not
force` in the same `if`, mirroring `not force` in the free-interval refusal's own guard
(`:1983-1987`) — one boolean, no second code path to keep in sync with the first.

**Why `evidence.append_guard_refusal` and not a new sink.** `append_guard_refusal`'s own docstring
states its four reasons apply to "the whole class" of pre-dispatch guards (durability across
worktrees, an existing reader, envelope fit, one path per event class —
`evidence.py:274-315`) — none of those reasons are specific to the free-interval guard; they hold
for any pre-dispatch refusal `critic-begin` can make. A second sink here would be exactly the "one
path per event class" violation the docstring names as reason 4.

## Section 1 — `begin_review`'s new terminal status (PDC2)

**Where:** `plugin/lib/critic_consolidate.py`, `begin_review`'s docstring (`:1603-1621`) gains one
line documenting the new return shape, immediately after the existing `"no-review-needed"` sentence:

```
    Returns {"status": "ok", "id", "roster", "path", "notes": [...],
    "cleared_leftovers": bool, "manifest": {...}} or {"status": "error",
    "reason", "kind"?} where kind == "scope-widened" tells the CLI to
    exit 2 ... or {"status": "no-review-needed", "reason", "free_files"}
    when the interval holds no judgeable file ... or {"status":
    "precondition-failed", "reason"} when mode_token == "verify-resolutions"
    and saved test evidence is not current — the CLI exits 4. Distinct from
    "no-review-needed": that means nothing to review; this means something
    to review that the evidence can't presently validate, and a reader of
    the reason string must be able to tell the two apart (issue #724).
    force=True bypasses this precondition exactly as it bypasses the
    free-interval refusal.
```

No other field is added to the returned dict — `"reason"` alone (PDC4's verbatim-reason
requirement) is the whole payload; there is no `free_files`/`anchor`/`excluded_wip` triple because
nothing about *which files* is at stake here (see Decision above).

## Section 2 — `bin/prawduct-hook`: exit 4 (PDC2)

**Where:** `cmd_critic_begin`, directly after the existing `if result["status"] == "no-review-
needed":` block (`:1723-1777`) and before `if result["status"] != "ok":` (`:1778`):

```python
    if result["status"] == "precondition-failed":
        # Exit 4, not 1: this is not a generic dispatch failure — it is a
        # SPECIFIC, mechanically-checkable precondition ("saved test evidence
        # does not cover this tree") that the coverage/PR gate would already
        # flag, moved ahead of spending a reviewer (issue #724). Not exit 3
        # either: "no review needed" means the interval is empty; this means
        # the interval is real but the evidence that would validate a fix to
        # it cannot presently be trusted. Conflating the two would make a
        # future reader of this exit code unable to tell "nothing to do" from
        # "something to do that I can't currently validate."
        print(
            f"PRAWDUCT: verify-resolutions refused — test evidence is not current "
            f"({result['reason']}).\n"
            "  Run the declared suite, record it (`prawduct-hook test-evidence "
            "record` or your product's own recording step), then re-invoke "
            "`/prawduct:critic verify-resolutions`.\n"
            "  To review anyway: `/prawduct:critic verify-resolutions --force`."
        )
        return 4
```

**`cmd_critic_begin`'s own docstring** (`:1649-1659`) gains one clause after the existing exit-3
sentence:

```
    ...no gate reads); **exit 4 = precondition failed** — verify-resolutions
    was dispatched against test evidence that is not current, so the check
    refused before any manifest was written or marker was set (`--force`
    dispatches anyway; the refusal appends one inert `guard-refusal` fact,
    which no gate reads); exit 1 = any other dispatch failure (reason on
    stderr).
```

**`plugin/skills/critic/SKILL.md`, step 4's exit-code table** (`:53-59`) gains one row, placed
after exit 3 and before the `verify-resolutions`-specific exit-1 row (grouping the two
`verify-resolutions`-only rows together):

```
   | **4** on `verify-resolutions` | test evidence is not current | run the declared suite, record it, then re-invoke `/prawduct:critic verify-resolutions` (or pass `--force` if the user asked for the review anyway) |
```

No change to step 4's prose paragraph above the table, to the demotion-property paragraph
(`:61`), or to step 5 (`:64`) — step 5's `test-status` check remains exactly as it is today and
now simply never fires stale on a dispatched `verify-resolutions` review, because dispatch already
refused one (PDC7: no existing current-evidence behavior changes).

## Section 3 — nothing else moves

Explicitly, to keep this item's diff minimal and match PDC7:

- `gates.tests_are_current` and `_load_test_evidence` are **called, not modified** — no new
  staleness clause, no new field on `.test-evidence.json`.
- The existing free-interval GATE AS DISPATCHER block (`:1960-2035`) is untouched; the new check
  is a sibling precondition earlier in the same function, not a change to that one.
- `chunk`, `final`, `cumulative` dispatch paths gain no new code — the `if mode_token ==
  "verify-resolutions"` guard means every other mode's control flow is byte-identical to today.
- `goals-1-3.md`'s promotion rule (staleness is BLOCKING in `verify-resolutions`) is not touched or
  removed — it still governs the (now rarer) case where evidence goes stale *between* a successful
  dispatch and consolidation, e.g. a builder edits files mid-review. This item removes the common
  case (stale at dispatch time), not the rule that covers the residual one.

## Files touched

| File | Change |
|---|---|
| `plugin/lib/critic_consolidate.py` | New precondition block in `begin_review`, gated on `mode_token == "verify-resolutions" and not force`; docstring gains the `precondition-failed` return shape (PDC1–PDC6) |
| `plugin/bin/prawduct-hook` | `cmd_critic_begin` gains one new `elif`-shaped block mapping `precondition-failed` → exit 4; docstring gains the exit-4 clause (PDC2) |
| `plugin/skills/critic/SKILL.md` | Step 4's exit-code table gains one row for exit 4 |
| `tests/test_critic_dispatch_stale_evidence.py` (new) | See test plan below |

## Test plan (`tests/test_critic_dispatch_stale_evidence.py`)

Following the existing dispatch-guard test style (`tests/` fixtures for `critic-begin`'s free-
interval refusal) — real git repos, real hook subprocess, a fixture `.test-evidence.json` written
directly rather than produced by an actual suite run.

1. **No test evidence at all, `verify-resolutions` dispatch** — `critic-begin --mode
   verify-resolutions` with no `.prawduct/.test-evidence.json` on disk → exit **4**, stdout names
   the freshness verdict's own reason, no `manifest.json` written, no critic-active marker set.
2. **Stale evidence (tree-invalid, no session marker)** — a saved record whose `evidence_tree`
   does not match the working tree and no session-start marker present → exit 4, same guarantees
   as case 1.
3. **Failing saved run** — a saved record with `failed > 0` → exit 4 (mirrors W1 from the issue
   body exactly).
4. **Self-reported degraded run** — a saved record with `degraded: true` → exit 4.
5. **Current evidence (tree-valid)** — a saved record whose `evidence_tree` matches the working
   tree → dispatch proceeds normally (exit 0 or whatever the existing per-mode logic already
   produces for that fixture), unchanged from today's behavior.
6. **`--force` bypasses a stale-evidence refusal** — case 1's fixture, `critic-begin --mode
   verify-resolutions --force` → dispatch proceeds (manifest written, marker set), mirroring the
   existing free-interval guard's own `--force` test.
7. **`chunk`, `final`, `cumulative` are unaffected by stale evidence** — each of the three modes,
   dispatched against case 1's fixture (no test evidence at all) → dispatch proceeds exactly as it
   does today; this item adds no new refusal path for any mode but `verify-resolutions` (pins
   PDC7 and the Decision's mode scoping).
8. **Guard-refusal fact recorded** — after case 1, `prawduct-hook evidence list --kind
   guard-refusal` includes one fact with `guard: critic-dispatch-stale-evidence` and a `reason`
   field matching the printed message (PDC6).
9. **Precondition takes priority over the in-flight guard's absence but not its presence** — a
   live critic-active marker plus stale evidence still refuses with the **in-flight** reason
   (`review-in-flight`), not `precondition-failed` — pins the new check's placement strictly after
   the in-flight guard, never before it.

## Open items for the build chunk (not resolved here)

- Exact wording of the fixture `.test-evidence.json` records for each staleness case (cosmetic —
  the four ways `_load_test_evidence`/`tests_are_current` already classify evidence as not current
  are the four the test plan exercises, no fifth is introduced).
- Whether `prawduct-hook evidence list`'s existing renderer needs any new column for
  `critic-dispatch-stale-evidence` beyond what it already renders for
  `critic-dispatch-free-interval` — the body shape here (`mode`, `reason`, `branch`) is a strict
  subset of the free-interval guard's own body, so no renderer change is expected, but confirming
  that is a one-line check the build chunk can make against the existing lister.

## Acceptance (carried from requirements, now with an implementation path)

- [ ] A `verify-resolutions` dispatch against stale test evidence (no evidence, a failing saved
      run, a self-reported degraded run, or a tree/timestamp mismatch neither freshness clause
      relaxes) refuses before any manifest is written or marker is set, citing the freshness
      verdict's own reason — pinned by test-plan cases 1–4, exit code 4.
- [ ] The same dispatch with `--force` proceeds as it does today — pinned by case 6.
- [ ] `chunk`, `final`, and `cumulative` dispatches are behaviorally unchanged by this item on both
      current and stale evidence — pinned by case 7.
- [ ] The refusal is recorded as a `guard-refusal` evidence fact distinct in `kind`
      (`critic-dispatch-stale-evidence`) from the existing judgeable-path refusal
      (`critic-dispatch-free-interval`) — pinned by case 8.

## Evidence / references

- `documentation/issues/724-requirements.md` — PDC1 through PDC7, the Decision, and the Grounding
  facts this design resolves against (in particular `gates.py:161-231`, `critic_consolidate.py`
  `:1594-1694,1960-2053`, and `goals-1-3.md`'s BLOCKING-only promotion rule).
- `plugin/lib/critic_consolidate.py:1643-1694` (`begin_review`'s mode-token guard and in-flight
  guard — the only preconditions today, and the exact point this item's check follows),
  `:1960-2053` (the existing free-interval refusal this item's mechanism and evidence-recording
  pattern mirror).
- `plugin/lib/gates.py:161-231` (`tests_are_current`), `:130-158` (`_load_test_evidence`) — the
  verdict this item calls, unmodified.
- `plugin/lib/evidence.py:266-315` (`append_guard_refusal`'s docstring, "one sink for the whole
  class" and its four reasons) — why this item reuses the sink rather than adding a second one.
- `plugin/bin/prawduct-hook:1635-1788` (`cmd_critic_begin`, its docstring, and the existing
  exit-code branches this item adds exit 4 alongside).
- `plugin/skills/critic/SKILL.md:51-64` (step 4's dispatch paragraph and exit-code table, step 5's
  post-dispatch `test-status` check — untouched by this item per PDC7).
- `plugin/skills/critic/goals-1-3.md` step 1 — the BLOCKING-only promotion rule for
  `verify-resolutions` findings, the reason W1 cost a full round and the reason this item scopes
  to that mode alone.
- Issue #724 body, §W1 — the lived-experience report this item's acceptance criteria trace back to.
