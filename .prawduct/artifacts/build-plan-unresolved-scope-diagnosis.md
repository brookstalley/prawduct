---
artifact: build-plan
version: 2
scope: unresolved-scope-diagnosis
branch: fix/unresolved-scope-diagnosis
depends_on:
  - artifact: architecture
governed_by:
  - artifact: architecture
    dispositions:
      - "authority fails closed; advice fails soft → conforms: the diagnosis is advice. It rides `critic-begin`'s `notes` (stderr `PRAWDUCT NOTE:`), changes no exit code and refuses no dispatch; a diagnosis that cannot be derived is silence, never an error"
      - "every fact has one home → conforms: the cause is computed by one function in `buildplan_refs` beside the resolver it explains, from the same readers the resolver uses (`plan_index.branch_claiming_plans`, the scope map, `core.resolve_build_plan_path`)"
      - "goals and verification bind; prescribed method is advice → engaged: the owner-facing proposal listed five causes including 'a name match rejected because every box is ticked'; Chunk 2 removes that rejection, so the diagnosis does not carry a case for it"
  - artifact: nonfunctional-requirements
    dispositions:
      - "a control names its yield and emits it observably → conforms: the diagnosis is recorded in the dispatch manifest as `scope_unresolved_cause`, so how often each cause fires can be counted from the archived manifests later"
      - "review wall-clock is P0 → conforms: no gate, no new round; one extra artifacts walk only on the unresolved path"
  - artifact: api-contract
    dispositions:
      - "additive-first evolution → conforms: one new manifest key and one new stderr note; no flag, exit code or existing key changes meaning"
partition: serial — two small chunks over the same two modules, one agent
last_validated: 2026-09-22
---

# Build plan — say why a review's scope did not resolve, and stop rejecting finished plans by name

## Requirements Confidence

**Level:** High

**Why:** the causes were measured on 2026-09-22 across seven repos' shared evidence stores:
131 of 382 Critic review facts since 2026-09-13 recorded `scope_chosen_by: not-resolved`
(discodon 84/128, faidh 7/10, swordfishing 5/6, hallucinote 3/3, bankmachine 16/73, puzzles
5/71, prawduct 11/91). Re-derive per repo from its checkout:

```sh
grep '"kind": *"review"' "$(git rev-parse --git-common-dir)/prawduct/evidence.jsonl" \
  | python3 -c 'import json,sys; fs=[json.loads(l) for l in sys.stdin]; fs=[f for f in fs if f["ts"]>="2026-09-13"]; print(sum(f["body"].get("scope_chosen_by")=="not-resolved" for f in fs), "of", len(fs))'
```

Repos whose plans put `branch:` in frontmatter (bankmachine, puzzles, prawduct) resolved about
90% of the time; the others about 35%. The faidh cases were reproduced by running the plugin's
resolver against faidh's commits in a scratch clone.

The four causes found:

1. **`branch:` written in the plan body, not frontmatter.** `plan_index.branch_claiming_plans`
   reads frontmatter only, so it returns nothing. faidh's `build-plan-claims-residual-scan.md`
   (written on 3.6.1) and many discodon plans have this shape, spelled `branch: X`,
   `**Branch:** \`X\`` or `**Branch**: \`X\``.
2. **Name-match rejected once every box is ticked.** `infer_scope_from_branch` accepts a
   branch-name match only for a plan with unticked chunks. The methodology ticks each chunk after
   its review, so by the end-of-plan cumulative the match is gone (faidh `c3f77d8a` resolved with
   1 of 2 ticked; `fe128ff7` with 2 of 2 did not). The rejection's warrant — "those boxes flip at
   release" — stopped being true when the boxes stopped being derived; archiving is now what
   retires a plan, and the scope map already prunes `archive/`.
3. **The active plan claims a different branch.** discodon's
   `build-plan-eval-campaigns-then-extract.md` declares `branch: develop` while the work is on
   `feat/eval-classifier-campaign`.
4. **Reviews run on the integration branch.** No plan should claim it; missing is correct.

Plus: a plan claiming the branch but declaring no `scope:` resolves nothing (faidh `2dbabaed`).

**Why nobody noticed:** the only signal is the `(scope (none), not-resolved)` parenthetical on the
record-lint line, and — for full rounds only — a budget note saying the budget could not be
derived. Neither says why, or what to change.

`[DECISION: no note on the integration branch | a note that says "this is expected" fires on every
review there with no yield (nonfunctional-requirements: a control that never yields is removed by
default) | vetoable]`

`[DECISION: Chunk 2 drops the ticked-box rejection outright rather than replacing it with another
liveness test | archiving already ends a plan's claim everywhere else (branch claims, the scope
map); a second, weaker retirement signal is what produced the miss. The residual — a new branch
named exactly like a finished, not-yet-archived plan's scope is attributed to it — is the same
residual the docstring already states for unfinished plans, and `--scope` remains the remedy.
Measured 2026-09-22: 8 such plans across the seven repos | vetoable]`

**Out of scope:** no gate; no change to `core.resolve_branch_claim` (its tie-break among several
claimants still uses unticked chunks); no auto-repair of plans; the template's `branch:` guidance.

## Chunk 1: critic-begin explains an unresolved scope

**Delivers:** `buildplan_refs.unresolved_scope_cause(project_dir, prawduct_dir)` returning
`(code, sentence)` or `None`. Checked in this order:

- on the integration branch, or detached HEAD → `None`;
- `claim-no-scope` — a live plan claims this branch in frontmatter but declares no `scope:`;
- `body-branch` — a live build plan names this branch on a `branch:` line below its frontmatter;
- `pointer-claims-other` — the active plan claims a different branch;
- `no-claim` — otherwise: no plan claims the branch and no scope matches its name.

Each sentence names the plan and the edit that fixes it. `critic-begin` appends it to `notes` when
`scope_chosen_by == "not-resolved"` and records the code as `scope_unresolved_cause` in the
manifest (`null` otherwise). The body-line scan lives in `plan_index` beside
`branch_claiming_plans`.

**Done when:**
- Each code has a test on a real `critic-begin` dispatch asserting the note and the manifest key;
  explicit `--scope` and a resolved scope produce neither; the integration branch produces neither.
- The body-line matcher is tested on each spelling found in discodon, and on a frontmatter
  `branch:` (not a body mention).
- Targeted tests green.

## Chunk 2: a finished, unarchived plan still matches its branch name

**Delivers:** `infer_scope_from_branch` drops the `_has_unfinished_chunk` condition on the
name-match route; its docstring states archiving as the retirement signal and the residual.
`_has_unfinished_chunk`'s own docstring stops listing `infer_scope_from_branch` as a consumer.
`test_a_branch_named_after_a_finished_plan_does_not_match` is renegotiated in the open: a finished
live plan matches; the same plan under `archive/` does not.

**Done when:** targeted tests green; one `/prawduct:critic` covering both chunks.

## Status

- [ ] Chunk 1: critic-begin explains an unresolved scope
- [ ] Chunk 2: a finished, unarchived plan still matches its branch name
