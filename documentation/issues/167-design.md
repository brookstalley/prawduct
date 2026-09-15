# Issue #167 — Critic: Refuse a Full Re-Round When Zero Blocking Findings Remain: Technical Design

`status: draft · stage: design · area: critic · added: 2026-09-15 · source: scheduled backlog
session · issue: https://github.com/brookstalley/prawduct/issues/167`

Related: #724 (R3/R6, the sibling precondition-and-budget work already shipped in v3.5.0 as
`review_round_budget` — a count-based backstop this item's content-based refusal complements, not
duplicates); #677 (closed — the path-based predicate this item's own comment thread ruled
*cannot* reach the comment/docstring-in-source class, per the `docs-only warn-fix -> #677 only /
comment-or-docstring-in-source -> #167 only` partition recorded on the issue 2026-08-19).

No separate `167-requirements.md` exists, and this document does not author one. The issue's own
five-comment thread (2026-08-05 through 2026-09-02) already did the requirements work a fresh pass
would repeat: it measured the cost on this repo's own ledger, built and then discarded two
candidate mechanisms, red-teamed the survivor against a counter-example, and closed with an owner
triage comment (2026-09-02) that narrows the item to exactly one open question and names every
building block already shipped for it. This document takes that triage comment at its word,
answers its one open question, and turns the result into a placement decision, not a requirements
re-derivation.

## Problem

Grounded directly from the issue: nothing today refuses a Critic dispatch that exists only because
a *previous* review's own findings — or a previous review's own report prose — prompted the commit
under review. `verify-resolutions` mode selection is correct (rule 1 already ships, see Grounding
facts), but once that mode is selected, `critic-begin` dispatches every time regardless of whether
the delta being verified could possibly contain anything new. Measured repeatedly, cross-repo: 27
rounds/4.5h (#724's branch), 10 rounds (a released-version consumer), six rounds twice in this
repo, 85 minutes across two wasted rounds (a third sighting, 2026-08-18).

## Grounding facts

Re-verified against the current tree (`develop`, 2026-09-15):

- **Rule 1 (mode selection) already ships and is not this item's gap.**
  `plugin/lib/critic_mode.py:269-276`, `_rule_verify_resolutions_fires` routes to
  `verify-resolutions` whenever prior findings are actionable and the current diff is a non-empty
  subset of the prior review's `files_reviewed` — "round 2+ on the same chunk is verify-resolutions
  only" is already structural. What remains is rule 2: *given* `verify-resolutions` was correctly
  selected, some of those dispatches should still be refused.
- **The discriminator issue #167 said it lacked now exists, but answers a different question than
  this item needs.** `coverage.diagnose_fix_churn` (`plugin/lib/coverage.py:250-447`) is wired at
  `gates.py:1846` inside the **cumulative gate's** `uncovered` remedy — it fires *after* a round
  would already run, prints a NOTE naming `disposition` as the cheaper route, and never refuses a
  dispatch. It is also a **general lineage search**: it re-derives "the nearest review fact on this
  lineage" from the full facts list (`coverage.py:341-390`) rather than reading the specific fact a
  `verify-resolutions` dispatch is anchored to — appropriate for its own caller (the gate has no
  dispatch to anchor to), wrong precision for this one (`begin_review` already knows its anchor by
  explicit pointer — next fact).
- **`begin_review`'s `verify-resolutions` branch already resolves its own anchor fact, by pointer,
  more precisely than `diagnose_fix_churn`'s search does.** `critic_consolidate.py:2024-2035`:
  `_prior_review_fact` (`:1540-1553`) reads `.critic-findings.json`'s `fact_id` pointer (D7) and
  returns exactly the fact this pass exists to verify — `prior` / `prior_body` are already local
  variables in scope at the point `base_tree`/`base_commit` are assigned. No lineage re-search is
  needed to place this item's check; reusing `diagnose_fix_churn` wholesale would silently swap a
  precise, already-computed anchor for a re-derived approximate one, for no benefit.
- **The anchor's own severity mix is the fact the owner's escalation trail converged on, and it is
  already computed and threaded, just not consumed.** `diagnose_fix_churn`'s return carries
  `warning`/`note` counts pulled from the anchor's `body.counts` (`coverage.py:439-446`) — dead
  weight in its current caller (the gate's NOTE message quotes them but nothing branches on them).
  Comment `5200245939` (2026-08-06) is the ruling this field exists to let a caller honor: *"the
  refusal must be conditioned on the COVERAGE state, not the findings count"* — concretely, a
  `verify-resolutions` pass anchored on a **full round** (`chunk`/`cumulative`/`final`) must never
  be refused by count alone, because it is the pass that establishes coverage over whatever the
  builder committed next, *whether or not that full round found a blocking finding* (mitigation 5,
  "two rounds is the floor"). The worked example in that comment is exact: round 2
  (`89f2d4a3`, anchored on the **cumulative** round `6aaa7cf8` which had 1 blocking + 7 warning + 6
  note) is not refusable — the prior anchor carries actionable content, full stop, regardless of
  what round 2 itself later finds. Round 3 (`410ef5c4`, anchored on round 2 — a
  **`verify-resolutions`** fact that itself recorded **zero findings of any severity**) is the round
  the same comment calls out as genuinely wasteful — but see the next fact for why this exact case
  still falls outside the mechanism this document specifies.
- **A `verify-resolutions` fact's own mode string is already recorded and already read elsewhere by
  the same name.** `critic_consolidate.py:2465` writes `"mode": verbose` into every manifest (and
  from there into the review fact evidence.py persists); `coverage.py:726` and
  `dispositions.py:660` both already read `body.get("mode")` off a review fact for unrelated
  purposes. `_VERBOSE_VERIFY_RESOLUTIONS` (`critic_consolidate.py:96`) is the exact string
  `MODE_TOKEN_TO_VERBOSE["verify-resolutions"]` produces, already a module-level constant. Testing
  "was the anchor itself a `verify-resolutions` fact" needs no new field and no new constant.
- **`coverage_algebra.unresolved_blocking` and `resolution_index` are the two primitives
  `diagnose_fix_churn` itself is built from** (`coverage_algebra.py:305-339`), already imported
  lazily inside `coverage.py` and already the store's own notion of "does this fact still owe a
  fix" — reused here rather than re-derived, same as `diagnose_fix_churn` does internally.
- **The exit-code space is 0-4, all taken, all documented in one table.**
  `plugin/skills/critic/SKILL.md:53` (`| Exit | Meaning | Do |`) and
  `critic_consolidate.py:1846-1852`/`bin/prawduct-hook` confirm 0=dispatched, 1=dispatch failed
  (two sub-cases), 2=scope-widened, 3=no-review-needed, 4=budget-exhausted. Exit 5 is unclaimed.
  `_refuse_over_budget` (`critic_consolidate.py:1743-1822`) is the shape a new pre-dispatch refusal
  follows: build a `reason`, call `evidence.append_guard_refusal` under its own `guard=` name, print
  a soft warning if the record does not land (never turn a correct refusal into an error over a
  logging failure), return a status dict the CLI maps to its own exit code.
- **`--force` is already the uniform escape hatch for every guard in this cluster** (free-interval,
  round-budget), parsed once in `cmd_critic_begin` (`bin/prawduct-hook:1676-1681`) and threaded to
  `begin_review(force=True)`. This item's "override that was designed rather than discovered"
  acceptance criterion is this exact flag, reused rather than invented.

## Decisions

**D1. The check lives in `begin_review`'s `verify-resolutions` branch, keyed on the already-resolved
`prior` fact — not on a fresh call to `diagnose_fix_churn`.** Grounded above: `prior`/`prior_body`
is the precise, pointer-resolved anchor this dispatch already trusts; re-deriving a second, coarser
anchor via lineage search would let the two answers disagree with nothing to reconcile them.

**D2. The refusal fires only when the anchor fact is ITSELF a `verify-resolutions` fact.** This is
the single new discriminator this document adds, and it is what resolves the owner's one open
question (`5508777274`) without reopening it. Consequences, stated as the acceptance criteria read:

- The **first** `verify-resolutions` pass after any full round (`chunk`/`cumulative`/`final`) is
  **never** refused by this mechanism, regardless of that round's severity mix — mitigation 5's
  floor holds unconditionally, because `prior_body["mode"]` can never equal
  `_VERBOSE_VERIFY_RESOLUTIONS` there. This is what "coverage state, not findings count" means made
  concrete: the pass that establishes coverage over the fix commit always runs.
- A **second** `verify-resolutions` pass — one anchored on a `verify-resolutions` fact — is a
  candidate for refusal, subject to D3. This is exactly the W2/W3 cascade shape (#724) and the
  round-3-after-round-2 shape (`5200245939`'s worked example, `89f2d4a3 -> 410ef5c4`): the pass that
  would be reviewing prose or churn a *verify* pass's own report produced, not a full round's.

**D3. Within that scope, refuse only when the anchor left zero unresolved blocking AND the new
delta's judgeable files are a non-empty subset of files the anchor's OWN findings (any severity)
named.** Both conjuncts, for the reasons `diagnose_fix_churn` already establishes and this item
inherits rather than re-argues:

- Zero unresolved blocking (`coverage_algebra.unresolved_blocking`) — a round that still owes a real
  fix is never refused; "the discriminator is what moved the tree, never a round counter" survives
  intact, because an anchor with an unresolved blocking finding is out of scope before file identity
  is even checked.
- The delta subset of `named` — the anchor found *something* (a warning, a note, anything with a
  `files` list), and everything that changed since sits inside exactly those files. This is
  `diagnose_fix_churn`'s own subset test (`coverage.py:431-436`), file-granularity by design
  (COV-3M8Q's ruling against AST/content normalization applies here unchanged), reused rather than
  reimplemented, minus the lineage re-search D1 already replaces with the precise anchor.
- **`named` empty is not a match, by construction** — a `verify-resolutions` anchor that itself
  recorded literally zero findings of any severity (the `410ef5c4` round in the worked example)
  cannot satisfy the subset test, and this document does not extend the check to cover it. See
  Scope-out: that specific shape needs the anchor's own **observations** (prose it printed but never
  recorded as a finding) to be checkable, which no store field carries today
  (`5200245939`: "round 2's observations are unrecoverable from either store"). Building an
  observation-recording mechanism to close that gap is a different item; this one ships the class
  the store can already answer.

**D4. New terminal status `"self-inflicted-refusal"`, CLI exit 5.** Not exit 3 (`no-review-needed`):
that status means the interval holds no judgeable file at all, and this refusal's interval is
judgeable and non-empty — collapsing the two would make exit 3's own contract ("no judgeable file")
false on this path, and the skill's existing "exit 3 is a success, do not re-dispatch" instruction
would then also cover a case where files plainly changed, which is confusing for a different reason
than exit 3 is confusing today. Not exit 4 (`budget-exhausted`): that status is a count-based,
scope-wide backstop or­thogonal to this item (v3.5.0, `review_round_budget`) and its own refusal path
sweeps and auto-accepts outstanding findings across the whole scope — wrong action here, where the
anchor already has zero unresolved blocking and nothing needs sweeping. A fifth, distinct status
keeps the three refusal reasons ("nothing to review", "loop over budget", "this exact pass is
self-inflicted") separately queryable and separately retireable, per the same "a control names the
yield it expects and emits it observably" norm the other two guards ship under
(`critic_consolidate.py:2304-2310`, `:1761-1767`).

**D5. Placement: after the free-interval check, before the round-budget check.** Free-interval
(exit 3) answers "is there anything to review at all" and must run first, so an empty verify-on-a-
verify reads as "nothing to review" (exit 3) rather than "self-inflicted" (exit 5) — the more
specific status is wasted on an interval that was already going to be refused for a simpler reason.
Round-budget (exit 4) only ever applies to `FULL_ROUND_MODES` (`critic_consolidate.py:119`, which
excludes `verify-resolutions` by construction), so relative order against it is inert; placed
before it anyway, matching the existing comment's own ordering rationale ("the loop is over" and
"there was nothing to review" are different answers) extended to a third answer, "this delta was
already reviewed."

## Mechanism

Inside `begin_review`, in the `verify-resolutions` branch, after `files_changed` is computed
(`critic_consolidate.py:2261`) and the free-interval refusal (`:2299-2377`) has already had its
chance to fire:

```python
if mode_token == "verify-resolutions" and not force:
    if prior_body.get("mode") == _VERBOSE_VERIFY_RESOLUTIONS:
        from . import coverage_algebra  # noqa: PLC0415 — lazy, matches this module's other lib imports

        store = evidence.read_facts(project_dir)
        if store.get("status") != "error":
            resolved_idx = coverage_algebra.resolution_index(store.get("facts") or [])
            if not coverage_algebra.unresolved_blocking(prior, resolved_idx):
                named: set[str] = set()
                for finding in prior_body.get("findings") or []:
                    for path in finding.get("files") or []:
                        if isinstance(path, str) and path:
                            named.add(path)
                judgeable = coverage_algebra.judgeable_files(files_changed)
                if judgeable and named and set(judgeable) <= named:
                    return _refuse_self_inflicted(
                        project_dir, prior, judgeable, named,
                        mode_token, scope, chunk, dispatch_commit, notes,
                    )
```

`_refuse_self_inflicted` (new, modeled on `_refuse_over_budget`'s shape at
`critic_consolidate.py:1743-1822`, without the sweep — nothing here is outstanding to sweep):

- Builds `reason`: `f"verify-resolutions anchored on {prior['id']}, itself a clean verify-"
  f"resolutions pass (0 unresolved blocking) — the changed file(s) {sorted(judgeable)} are all "
  f"among the {len(named)} file(s) that pass's own findings already named. This looks like the "
  f"round the fixing itself generated, not new work."`
- Calls `evidence.append_guard_refusal(project_dir, "critic-dispatch-self-inflicted-verify", {...})`
  with `anchor_fact_id`, `delta_files`, `named_files`, `mode`, `scope`, `chunk`, `branch`,
  `dispatch_commit` — same shape as the two existing guard-refusal bodies, so
  `prawduct-hook evidence list --kind guard-refusal` answers all three with one query, per the
  norm D4 cites.
- Prints the soft-failure stderr line if the record does not land (`critic_consolidate.py:2342-2349`
  pattern), so a firing that vanishes is never silently read as a firing that never happened.
- Returns `{"status": "self-inflicted-refusal", "reason", "anchor_fact_id", "delta_files",
  "named_files", "notes", "recorded"}`.

`cmd_critic_begin` (`bin/prawduct-hook`) gains one new branch, mirroring the existing
`if result["status"] == "budget-exhausted": ... return 4` block (`:1722-1766`): print the reason and
the two file lists, print the remedy (`disposition --accept` against the anchor's still-open
warning/note findings, per NEXT-ACTION's existing free-disposition route — no round needed to close
them), print the `--force` override line, and `return 5`.

## SKILL.md / exit-code table update

One new row in the table at `plugin/skills/critic/SKILL.md:53-59`, inserted after exit 4 (severity
order, most-terminal first):

```
| **5** | **self-inflicted** — this verify pass would re-review a prior verify pass's own clean
  result | **you are DONE for this delta — report stdout's reason and stop.** Any still-open
  warning/note from the named anchor: `disposition --accept` (free, no round). `--force` only if the
  user asks. |
```

And one line added beside the existing exit-3 "Exit 3 is a success, not a failure" paragraph
(`SKILL.md:65` region), stating the exit-5 analogue: exit 5 is also a success, not a failure — the
delta was already covered by the reasoning that produced it; re-dispatching without `--force` is the
instinct this exit exists to end, same as exit 3's.

## Test plan

1. `verify-resolutions` anchored on a `cumulative` fact with 1 blocking, 3 warning → dispatches
   (unresolved blocking present; D2 never reached).
2. `verify-resolutions` anchored on a `cumulative` fact with 0 blocking, 2 warning, delta confined to
   the warning's named files → dispatches (D2: anchor mode is not `verify-resolutions`). The
   mitigation-5 regression test.
3. `verify-resolutions` anchored on a `verify-resolutions` fact with 0 blocking, 1 warning naming
   file `a.py`, delta = `a.py` only → **refused, exit 5**. The `410ef5c4`-shape case with one
   non-empty finding, i.e. the class this item actually closes.
4. Same as 3, but the anchor's `findings` list is empty (0 warning, 0 note too) → **dispatches**
   (D3: `named` is empty, subset test fails by construction). Documents the deliberate scope
   boundary from D3/Scope-out — pins that this document does NOT claim to catch the true
   zero-finding double-verify.
5. Same as 3, but delta also touches `b.py`, outside `named` → dispatches (genuine-outside-change
   acceptance criterion).
6. Same as 3, but delta is a docstring-only edit inside `a.py` (not a full rewrite) →
   **refused, exit 5**. Pins acceptance criterion 3 (comment/docstring-in-source, the class #677
   cannot reach) at file granularity, matching COV-3M8Q.
7. Same as 3, but `--force` passed → dispatches; the guard-refusal fact is NOT appended (no refusal
   fired) — mirrors the existing free-interval/`force` contract, not the budget one (budget still
   records the firing even under `--force`, per its own comment; this refusal, like free-interval,
   simply does not evaluate under `force`).
8. `evidence.read_facts` returns `status: error` mid-check → falls through to normal dispatch, no
   refusal, no crash (mirrors free-interval's degraded-store posture: never let a store read failure
   manufacture a refusal that would need `--force` to escape something that was never actually
   checked).
9. `cmd_critic_begin` prints the exit-5 message shape and returns 5; the exit-4 branch is untouched
   (regression pin — the two must not be reachable from the same manifest state).

## Files touched

| File | Change |
|---|---|
| `plugin/lib/critic_consolidate.py` | New check in `begin_review`'s `verify-resolutions` branch (D1-D3); new `_refuse_self_inflicted` helper (D4/Mechanism) |
| `plugin/bin/prawduct-hook` | New `status == "self-inflicted-refusal"` branch in `cmd_critic_begin`, `return 5` |
| `plugin/skills/critic/SKILL.md` | New exit-5 table row; exit-5 "success, not failure" paragraph |
| Critic dispatch tests (wherever `begin_review`'s existing free-interval/budget cases live) | Cases 1-9 above |

## Scope-out (this item)

- The true zero-finding-anchor double-verify (`410ef5c4`-on-`89f2d4a3` where the FIRST verify also
  recorded nothing) — D3 explicitly does not extend to it; it needs observations to become
  checkable facts first, which is a separate, currently-unfiled gap (`5200245939`'s closing note).
- Any change to `diagnose_fix_churn` or its `gates.py` caller — this document reuses its primitives
  (`coverage_algebra.unresolved_blocking`/`resolution_index`/`judgeable_files`) and its subset-test
  shape, but does not call the function itself (D1) and makes no change to the cumulative gate's
  `uncovered` remedy.
- `chunk`/`cumulative`/`final` dispatch — untouched; rule 1 (`infer_mode`) already keeps a genuine
  round-2-on-the-same-chunk out of those modes, so this item's refusal has nothing to do there.
- Auto-accepting the anchor's open warning/note findings on refusal — unlike budget-exhausted, this
  refusal's anchor already has zero unresolved blocking and nothing structurally requires sweeping;
  the builder is pointed at the existing free `disposition --accept` route instead (Mechanism).
- Any UI/wording change to the NEXT-ACTION carrier itself (`critic_consolidate.py` `next_action`
  logic) — untouched; this item only adds a dispatch-time refusal upstream of it.

## Evidence / references

- Issue #167's own comment thread, `5195369660` / `5200245939` / `5337260701` / `5337307096` /
  `5508777274` — the measurement, the discriminator's design constraint, the #677 partition ruling,
  and the triage comment naming the single open question this document answers.
- `plugin/lib/critic_mode.py:269-276` — `_rule_verify_resolutions_fires`, rule 1, already shipped.
- `plugin/lib/coverage.py:250-447` — `diagnose_fix_churn`, the discriminator this item's check is
  modeled on and reuses primitives from, without calling directly (D1).
- `plugin/lib/coverage_algebra.py:305-339` — `resolution_index`, `unresolved_blocking`, the two
  primitives this item's check calls directly.
- `plugin/lib/critic_consolidate.py:1540-1553` (`_prior_review_fact`), `:1825-2035` (`begin_review`'s
  signature and `verify-resolutions` branch), `:2261-2377` (free-interval refusal, the placement
  anchor), `:2379-2411` (round-budget refusal, the sibling this item's placement follows), `:96`
  (`_VERBOSE_VERIFY_RESOLUTIONS`), `:119` (`FULL_ROUND_MODES`), `:1743-1822`
  (`_refuse_over_budget`, the shape `_refuse_self_inflicted` follows).
- `plugin/bin/prawduct-hook:1634-1766` — `cmd_critic_begin`, its `--force` parsing, and the existing
  exit-code branches this item adds a fifth sibling to.
- `plugin/skills/critic/SKILL.md:53-65` — the exit-code table and the exit-3 "success, not failure"
  framing this item's exit-5 paragraph mirrors.
- `plugin/CHANGELOG.md` v3.5.0 — `review_round_budget`, the shipped count-based sibling control this
  item is explicitly not duplicating (Related, above).
- COV-3M8Q (cited throughout the issue thread) — the standing ruling against AST/content
  normalization that keeps this item's subset test at file granularity (D3).
