# Issue #619 — Tests: Diff-Scoped Mutation as an Opt-In Evidence Socket: Requirements

`status: draft · stage: requirements · area: tests · added: 2026-08-15 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/619`

Related: siblings #249 (socket 1 — diff coverage), #618 (socket 2 — blast radius), #620 (socket 4
— API diff); GOV-2R8K, the single home of the shared four-socket contract
(`.prawduct/artifacts/change-evidence-design.md`), which this document must not restate.

## Problem

No instrument in the framework answers "would a test have *failed* if this behaviour changed?"
Diff coverage (socket 1) proves a changed line executed; it does not prove any assertion
constrained it. Socket 3 is the only one of the four sockets that closes that gap — the
literature's *checked coverage* / Case B distinction — and it is deliberately the most expensive
one, so its adoption story has to be different from its siblings' from the outset.

## Grounding facts

Re-verified against the current tree (2026-08-15):

- **The design doc already fully specifies socket 3's contract** — producer (PIT incremental,
  Stryker `--since`, mutmut `--incremental`/`--since`), verdict (surviving mutants in changed
  code), posture (opt-in, off by default, "the only socket expected to stay rare"), and consumer
  ("the Critic's test-adequacy goal") (`change-evidence-design.md:144-154`). This document grounds
  those five acceptance criteria against the codebase and resolves the decisions the design doc
  left open where they are scoped to this socket alone — it does not re-derive the contract.
- **No implementation exists today.** A repo-wide search for `mutation`/`mutmut`/`PIT`/`Stryker`
  in a testing-tool sense turns up nothing outside `change-evidence-design.md` itself — this is
  genuinely greenfield work, consistent with the design doc's own "target design, not current
  reality" header.
- **The closest existing precedent for "product declares an opaque producer invocation, prawduct
  validates no tool name" is `test_command`/`test_commands`, not a hypothetical.**
  `test_command:` (`plugin/templates/project-state.yaml:339` region; the declaration block
  precedes it) is explicitly "declare it — don't wrap it," and `coverage_required: false`
  (`plugin/templates/project-state.yaml:339`) / `operator_verification_required: false`
  (`:385`) are both opt-in-by-default booleans read via `core.read_bool_yaml_key`
  (`plugin/lib/gates.py:53,1697`) — the exact "fails soft to False" contract
  (`plugin/lib/core.py:243,252`) socket 3's opt-in flag needs, and the same shape sibling sockets
  2 and 4 already reuse in their own requirements passes.
- **The "unchecked, never passed" precedent socket 3 must mirror already ships in
  `verify_coverage`.** `changes_unjudged` files are reported informationally and never counted as
  a failure (`plugin/lib/gates.py:1668-1768`, specifically the `skipped`/`missing` split at
  `:1753-1762`) — the concrete precedent for "a missing producer reports unchecked, never passed"
  that the Python-specificity norm's fail-open clause requires of every socket.
- **The evidence store's `kind` enum is fail-closed and has no slot for a mutation verdict.**
  `evidence.py`'s `KNOWN_KINDS` is `frozenset({"review", "resolution", "disposition",
  "guard-refusal"})` (`plugin/lib/evidence.py:83`); `append_fact` rejects any other kind outright
  (`:136-140`). `test-run`, `pr-review`, and `promotion` are named as **reserved, not
  implemented** (`data-model.md:26-28,57,107`), and `data-model.md`'s own Direction section
  states extending the store to subsume test-run-shaped evidence is "design direction, not yet a
  ratified norm." A mutation verdict is not even among the three reserved names — this is the
  same open question siblings #618 and #620 already flag, not a new one.
- **The named consumer does not exist yet.** The design doc says socket 3's consumer is "the
  Critic's test-adequacy goal" (`change-evidence-design.md:152`), but no goal by that name, or by
  any mutation/test-adequacy framing, exists in `plugin/skills/pr/review-protocol.md` today — its
  three goals are Architectural Fit, (an omitted second), and Merge Hygiene
  (`review-protocol.md:60-72`), none of which mention mutation or surviving-mutant verdicts. Unlike
  socket 4, which has two live candidate seams to choose between (Grounding facts, #620's
  requirements pass), socket 3 has **zero** — its consumer is itself unbuilt. This is a materially
  different starting point from siblings 2 and 4, both of which compose into an existing seam.
- **Diff-scoping already has a working in-repo pattern to point to, even though it belongs to a
  different socket.** `bin/test-reference-verify`'s `_resolve_base`/`_changed_files`
  (`plugin/bin/test-reference-verify:81-123`) resolve a diff base (`origin/main` → `main` →
  `HEAD~1`, or an explicit `--base`) and compute the changed-file set the same way any diff-scoped
  producer (including a mutation tool run with `--since`) would need to. This is the floor
  socket 1 already retires toward per the design doc's Open Questions
  (`change-evidence-design.md:308-310`) — cited here only as the shape of "diff-scoped," not
  reused as socket 3's implementation.
- **The ratified norms constrain what prawduct itself may build.** `architecture.md:74`
  (never Python-specific — a language with no populated rules is *unchecked*, never silently
  passed), `:79` (prawduct guides and reviews, never implements — "a bare-except check belongs to
  ruff or clippy, not to a prawduct gate"), together with the local-first / no third-party
  runtime dependencies Direction, are the textual source for "prawduct implements no mutation
  engine and maintains no per-language mutation-operator set" — the corresponding requirement
  every sibling socket also carries for its own instrument.
- **The review-wall-clock P0 norm is the reason this socket's opt-in posture cannot be casual.**
  `nonfunctional-requirements.md:18` names review wall-clock cost as `unit-cost × run-count`, and
  `:22` requires any added control to "name the yield it expects **and emit that yield
  observably** … a control whose findings are printed and forgotten … can never be retired on
  evidence." Socket 3 is the design doc's own example of a *high* test-runtime-cost instrument
  (`change-evidence-design.md:33-35`) — the one socket where an accidental default-on, or a
  default-on inherited from adopting a sibling socket, would directly violate this P0 constraint.

## Decisions

Scoped to socket 3 alone — none of these reopen the shared four-socket contract, which stays
owned by `change-evidence-design.md`.

**1. Producer declaration is an opaque, unwrapped invocation — prawduct validates no
per-ecosystem tool name and maintains no enum of supported mutation tools.** This mirrors
`test_command`'s "declare it — don't wrap it" contract exactly (Grounding facts), and is required
by the norm that prawduct implement no per-language mutation-operator set. The tools the design
doc names (PIT, Stryker, mutmut) are illustrative research, not a validated allowlist.

**2. Opt-in is a new, independent boolean project-state.yaml key, defaulting to `false`, read
via `read_bool_yaml_key` exactly as `coverage_required` and `operator_verification_required` are
read today.** The exact key name is left to design (candidates: `mutation_testing_required`,
`change_evidence.socket3_required`) — naming depends on the same cross-socket "one declaration
surface vs. four" open question `change-evidence-design.md:305` already flags, which this item
does not resolve in isolation.

**3. Opt-in is per-socket and never inherited from any other socket's adoption.** A product that
declares producers for sockets 1, 2, or 4 acquires none of socket 3's cost as a side effect —
each socket's opt-in flag is independent, read independently, with no cascading default. This is
the concrete guard against the review-wall-clock P0 violation named in Grounding facts: the one
socket expected to stay rare must not become accidentally common because a product enabled a
cheap sibling.

**4. A missing producer, with the opt-in flag set, reports a distinct *unchecked* state — never
silently coalesced with "no surviving mutants."** This mirrors `verify_coverage`'s
`changes_unjudged`-vs-missing-coverage split (Grounding facts) as the concrete, already-shipped
precedent for "unchecked, never passed," applied to socket 3's own verdict shape.

**5. The consumer does not exist and building it is out of this item's scope, but the requirement
that one exist before this socket ships is not deferrable.** The design doc states "a channel
produced and never consumed is a defect" for every socket (`change-evidence-design.md:119`,
stated for socket 1 and implied as a standing rule). Because socket 3's named consumer — "the
Critic's test-adequacy goal" — has zero existing seam (Grounding facts, unlike socket 4's two
live candidates), the design pass must either define a new PR-review goal or graft onto an
existing one (`review-protocol.md`'s own extension guidance, cited by sibling #620, prefers
strengthening an existing goal over adding a new one) before any implementation lands.

**6. Where the verdict is persisted is explicitly deferred, not assumed to be `evidence.jsonl`.**
Same constraint siblings #618 and #620 already state for their own sockets: additive-only field
evolution, loud (never silent) handling of a schema-ahead or malformed record
(`data-model.md`'s forward-incompatibility rules), and — if it lands in the shared evidence
store — a new `kind` added deliberately to `KNOWN_KINDS` rather than assumed. This item does not
pick the store.

## Requirements

MUST unless marked SHOULD.

- **MUT-1** The verdict is surviving mutants in changed code only — diff-scoped to the same
  changed-symbol/changed-file boundary every other socket uses, never a whole-repo mutation run
  (Decision 1; Scope-out).
- **MUT-2** The socket is off by default; a product opts in via one explicit boolean, read the
  same way `coverage_required` is read today (Decision 2).
- **MUT-3** Opting into any other socket (1, 2, or 4) never enables socket 3 as a side effect —
  each socket's opt-in is independently declared and independently read (Decision 3).
- **MUT-4** The product declares its mutation producer as an opaque invocation; prawduct
  validates no ecosystem-specific tool name and ships no per-language enum or allowlist of
  "supported" mutation tools (Decision 1).
- **MUT-5** A product with the opt-in flag set but no producer declared reports a distinct
  *unchecked* state — never silently coalesced with a clean ("no surviving mutants") verdict
  (Decision 4).
- **MUT-6** Prawduct implements no mutation engine and authors no mutation operators of its own —
  the verdict is consumed from the product's declared tool, never re-derived.
- **MUT-7** Documentation states, wherever socket 1's coverage guarantee is described, that
  socket 1 does not close the covered ≠ verified (Case B) gap and that socket 3 is the only
  instrument here that does — mirroring the design doc's own "must never be described as if it
  closes Case B" instruction for socket 1 (`change-evidence-design.md:177-179`).
- **MUT-8** A defined PR-review consumer exists for the verdict before this socket ships in any
  form — either a new goal or an extension of an existing one in `review-protocol.md` — chosen and
  justified at design time, not left unresolved past this item (Decision 5).
- **MUT-9** Whatever storage the verdict lands in respects additive-only field evolution and loud
  (never silent) handling of a schema-ahead or malformed record; if it lands in the shared
  evidence store, a new `kind` is added deliberately to `evidence.py`'s `KNOWN_KINDS` rather than
  assumed (Decision 6).

## Acceptance

- [ ] Surviving mutants in changed code are the reported verdict, diff-scoped, never a whole-repo
      result.
- [ ] Off by default; a product opts in explicitly and never acquires the cost by adopting
      another socket.
- [ ] A missing producer (with opt-in set) reports *unchecked*, never *passed*.
- [ ] Prawduct runs no mutation engine and implements no mutation operators.
- [ ] Documentation states this is the only socket that closes the covered ≠ verified gap,
      wherever socket 1's guarantee is stated.
- [ ] A PR-review consumer for the verdict is named and justified before the socket ships.

## Scope-out (this item)

- The shared four-socket contract, its rationale, blind spots, and adoption/rollout mechanics —
  `change-evidence-design.md`'s territory, per the issue's own scope-out.
- Sockets 1, 2, and 4 (#249, #618, #620) — sibling items with their own requirements passes.
- Whole-repo mutation runs.
- The exact producer-command support matrix (PIT vs. Stryker vs. mutmut specifics, `--since`/
  `--incremental` flag handling) — a design-stage concern once the declaration surface (Decision
  1–2) is fixed.
- The evidence-storage choice (Decision 6) and the exact PR-review consumer seam (Decision 5,
  MUT-8's "which goal") — both explicitly deferred to the design pass, which must resolve them
  before implementation, not leave them open indefinitely.
- Whether all four sockets share one `project-state.yaml` declaration surface or four
  (`change-evidence-design.md` Open Question #1) — cross-socket, not decided for socket 3 in
  isolation.

## Evidence / references

- `.prawduct/artifacts/change-evidence-design.md:33-35,119,144-154,173-179,305,308-310` — the
  socket-cost comparison table, the "produced and never consumed is a defect" rule, Socket 3's
  design section, the Case B blind spot, and the open declaration-surface / retirement-path
  questions.
- `plugin/templates/project-state.yaml:339,385` — `coverage_required` and
  `operator_verification_required`, the opt-in-boolean precedent Decision 2 reuses.
- `plugin/lib/core.py:243,252-272` — `read_bool_yaml_key`, the fail-soft-to-`False` helper
  MUT-2 reuses.
- `plugin/lib/gates.py:53,1668-1768,1697` — `verify_coverage`, its `changes_unjudged`-vs-missing
  split (the concrete "unchecked, never passed" precedent MUT-5 mirrors), and its
  `read_bool_yaml_key` call site.
- `plugin/lib/evidence.py:83,131-140` — `KNOWN_KINDS`, its fail-closed rejection of unregistered
  kinds.
- `.prawduct/artifacts/data-model.md:26-28,57,107` — the reserved-but-unratified
  `test-run`/`pr-review`/`promotion` kinds, the open question Decision 6 inherits from siblings
  #618 and #620.
- `plugin/skills/pr/review-protocol.md:60-72` — the PR reviewer's current goal set (Architectural
  Fit, Merge Hygiene, …), confirming no test-adequacy or mutation-verdict goal exists today.
- `plugin/bin/test-reference-verify:81-123` — `_resolve_base`/`_changed_files`, the shape of
  "diff-scoped" cited for context, not reused as socket 3's implementation.
- `.prawduct/artifacts/architecture.md:74,79` — the Direction norms grounding "prawduct
  implements no mutation engine, maintains no per-language operator set."
- `.prawduct/artifacts/nonfunctional-requirements.md:18,22` — the review-wall-clock P0 constraint
  and the yield-must-be-observable norm, the source of Decision 3's no-cascading-default rule.
- Issue #619 — problem statement, proposed change, and acceptance criteria this document grounds.
- Issue #249 (socket 1) — confirms via its own body that no mutation/PIT/Stryker/mutmut
  implementation exists anywhere in the tree as of this pass.
