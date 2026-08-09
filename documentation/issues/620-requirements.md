# Issue #620 — Gates: Detect Breaking Changes to a Published Surface: Requirements

`status: draft · stage: requirements · area: gates · added: 2026-08-09 · source: scheduled backlog
session · issue: https://github.com/brookstalley/prawduct/issues/620`

Related: siblings #249 (socket 1 — diff coverage), #618 (socket 2 — blast radius), #619 (socket 3 —
diff-scoped mutation); GOV-2R8K, the single home of the shared four-socket contract
(`.prawduct/artifacts/change-evidence-design.md`), which this document must not restate.

## Problem

Nothing in the framework today detects a breaking change to a governed product's published
surface. A one-line change to an output format fifty callers depend on can ship while diff coverage
(the framework's only shipped signal) reports green, because coverage answers "was this line
executed," never "did I break a contract." Socket 4 is the instrument for exactly that motivating
case — a per-ecosystem API-diff producer the product declares, whose verdict prawduct consumes at
build time with zero test-runtime cost. The design rationale, the four-socket contract shape, and
the default posture (report-only, product opts into blocking) all live in
`change-evidence-design.md` and are not re-derived here; this document grounds socket 4's five
acceptance criteria against the current codebase and resolves the decisions that document
deliberately left open where they are scoped to this socket alone.

## Grounding facts

Re-verified against the current tree (2026-08-09):

- **The trigger already exists and is already recognized.** `classification.structural.
  exposes_programmatic_interface` is one of six structural characteristics
  (`plugin/templates/project-state.yaml:28-32`), and prawduct's own instance already sets it
  (`.prawduct/project-state.yaml:112-116`, `consumers: both`). It is a **presence** flag, not a
  boolean: `plugin/lib/coverage_probes.py`'s `_structural_recorded_at()` (lines 162-228) recognizes
  it as present via either a truthy scalar not in `_ABSENT_VALUES` (`{"null","~","none","false",
  "no","off","0"}`, line 137) or a nested attribute block (`_opens_nested_block`, lines 151-159) —
  exactly the `consumers:` shape prawduct's own record uses. It already triggers the
  `api-contract.md` strategy artifact (`TRIGGERED_ARTIFACTS`, `coverage_probes.py:104`) and an
  `api_versioning_approach` doctor nudge (`plugin/skills/doctor/SKILL.md:52`). This is the trigger
  the design doc says to reuse (`change-evidence-design.md:260-263`), and the recognition logic to
  reuse it against already exists and is tested (`tests/test_coverage_probes.py:226-330,386-536,
  627-653`) — nothing new needs building to detect "does this product have a published surface."
- **`api-contract.md` already names the surface concretely, per product.** Its template
  (`plugin/templates/api-contract.md`) requires an `## Overview & Surface Type` naming the kind of
  interface and where its canonical contract lives (OpenAPI/SDL/.proto, typed public signatures,
  documented CLI flags), and a `## Surface Inventory & Stability Tiers` section listing public vs.
  internal operations. Prawduct's own filled instance concretizes this for its own CLI
  (`.prawduct/artifacts/api-contract.md:18-39,63-106,296-330`) — this is the artifact a socket-4
  producer declaration would sit alongside, since it is already where "what is the published
  surface" gets answered per product.
- **The closest existing full precedent for "product declares a producer → prawduct consumes a
  verdict → opt-in blocking" is `test_command`/`test_commands` + `coverage_required`, not a
  hypothetical.** `test_command:` (`plugin/templates/project-state.yaml:359-388`) is a declared,
  unwrapped invocation prawduct shells out to — explicitly "declare it — don't wrap it" — with no
  parsing of framework-specific output beyond a documented `{junit_xml}` substitution point.
  `coverage_required: false` (`plugin/templates/project-state.yaml:357`, `.prawduct/project-state.
  yaml:569`) is the opt-in-blocking half, read by `verify_coverage` (`plugin/lib/gates.py:1215-1246`):
  skips (exit 0, "skipped: … false (default)") when unset, and — critically for acceptance criterion
  4 — already implements the exact "unchecked, never passed" distinction socket 4 needs:
  `changes_unjudged` files are reported informationally on stdout and never counted as a failure
  (`gates.py:1228-1234`), which is precisely the gate-soundness lesson ("an unsatisfiable gate is
  worse than no gate") a missing-producer state must inherit. `operator_verification_required: false`
  is a second, independent instance of the same report-only/opt-in-blocking shape.
- **The evidence store's `kind` enum is fail-closed and does not yet include anything socket 4 could
  write to.** `plugin/lib/evidence.py`'s `KNOWN_KINDS` is `frozenset({"review", "resolution",
  "disposition", "guard-refusal"})` (line 78); `append_fact` rejects any other kind outright (lines
  131-136). `test-run`, `pr-review`, and `promotion` are named as **reserved, not implemented**
  (module docstring line 20; `.prawduct/artifacts/data-model.md:24-28,57`) — and `data-model.md`'s
  own Direction section says extending the store to subsume test-run/PR-review evidence is "design
  direction, not yet a ratified norm." Socket 4's own kind (an API-diff verdict) is not even among
  the three reserved names. `change-evidence-design.md`'s Open Questions (lines 311-316) already
  flags this as unsettled across all four sockets, "before the first socket persists anything."
- **The PR-review layer is where the design doc says socket 4 composes in, and there are two
  distinct existing seams, not one.** `plugin/skills/pr/review-protocol.md`'s `### 3. Merge Hygiene`
  goal already reads a report/gate-style signal the same shape socket 4 would need — test-evidence
  freshness via `prawduct-hook test-status`'s exit code, described as "the *only* freshness signal"
  (review-protocol.md:69) — and the skill's own extension guidance (lines 165-167) says to prefer
  strengthening an existing goal over adding a new one. Separately, `prawduct-hook
  check-releasability` (`plugin/bin/prawduct-hook:3718`, `plugin/lib/release_readiness.py:274`) is a
  mechanical, non-agent PR/release gate of the kind a blocking-opt-in check might belong to instead.
  Neither is named by the design doc, which only says "the PR-review gate" — both are live
  candidates.
- **No implementation of any of this exists today.** A repo-wide check confirms no file besides
  `change-evidence-design.md` mentions `cargo-public-api`, `japicmp`, `oasdiff`, or "socket 4" —
  this is genuinely greenfield work, consistent with the design doc's own "Status: target design,
  not current reality" header.
- **The norms this socket must satisfy are ratified, not aspirational.** `architecture.md:66`
  (local-first, no third-party runtime dependencies for the governance runtime), `:74` (never
  Python-specific; a language with no populated rules is *unchecked*, never silently passed), `:79`
  (prawduct guides and reviews, never implements — "a bare-except check belongs to ruff or clippy,
  not to a prawduct gate") together are the textual source for "prawduct implements no API differ
  and maintains no per-ecosystem matrix" (the issue's own acceptance criterion 5).
- **Discovery does not yet ask the question this socket depends on.** None of discovery.md's three
  developer-preference touchpoints (`discovery.md:113,117,222`) ask, conditional on a detected
  ecosystem, which API-diff checker is standard — confirming the design doc's claim
  (`change-evidence-design.md:254-256`) and `architecture.md:80`'s named gap, tracked separately by
  LNG-5W8R. This item does not fix that gap; it only needs the *declaration surface* the fix would
  eventually populate to exist.

## Decisions

Scoped to socket 4 alone — none of these reopen the shared four-socket contract, which stays owned
by `change-evidence-design.md`.

**1. The trigger is `exposes_programmatic_interface`, recognized exactly as `coverage_probes.py`
already recognizes it — no second detector.** The design doc says reuse the trigger; the grounding
facts show the recognition logic (presence via truthy scalar or nested block, honoring
`_ABSENT_VALUES`) already exists and is tested. Socket 4's activation check is a read of the same
flag through the same semantics, not a new probe.

**2. Producer declaration is an opaque, unwrapped invocation or result-artifact path — prawduct
validates no per-ecosystem tool name and maintains no enum of supported tools.** This mirrors
`test_command`'s "declare it — don't wrap it" contract exactly, and is required by the acceptance
criterion that prawduct implement no differ and maintain no per-ecosystem matrix. The specific tools
the design doc names (`cargo-public-api`, `japicmp`, `oasdiff`, …) are illustrative research, not a
validated allowlist — a product can name any command or point at any artifact path.

**3. Blocking is a new boolean project-state.yaml key, defaulting to `false` (report-only), read the
same way `coverage_required`/`operator_verification_required` are read today.** The exact key name
is left to design (candidates: `api_diff_required`, `change_evidence.socket4_required` — naming
depends on Decision 4 in the shared design doc about a single vs. four-key declaration surface,
which this item does not resolve).

**4. The minimal verdict primitive is NOT decided here — it is design-stage, deliberately, mirroring
how the design doc treated socket 1's primitive as a decision to make "before building, not after."**
Whatever shape it takes, it must be a normalized, tool-agnostic artifact (e.g., a list of
breaking-change descriptors) that the product's own declared producer emits — prawduct's own code
must never parse a tool-specific diff report format directly. Requiring this now, without picking
the shape, keeps the acceptance criterion ("no per-ecosystem matrix") satisfiable regardless of which
shape design picks.

**5. Where the verdict is persisted is explicitly deferred, not assumed to be `evidence.jsonl`.**
Landing there requires deliberately adding a new kind to `KNOWN_KINDS` — a real option, since the
existing fail-closed design (`append_fact` rejects unregistered kinds) makes that safe by
construction — but a dedicated per-product file, closer to `.test-evidence.json`'s shape, is equally
viable and sidesteps `data-model.md`'s still-unratified "subsume test-run/PR-review evidence" question
entirely. This item states the constraint (additive-only new fields; a schema-ahead record blocks
loudly, never silently misreads; a record predating a new field degrades to absent, not a crash —
the same forward/backward-compatibility rules `data-model.md` and `evidence.py`'s
`SUPPORTED_SCHEMAS` already enforce) without picking the store.

**6. The PR-gate integration seam is left open between the two live candidates found in Grounding
facts — extending `review-protocol.md`'s Merge Hygiene goal, or a mechanical check alongside
`check-releasability`.** `review-protocol.md`'s own guidance says prefer strengthening an existing
goal; `check-releasability` is the more mechanical, gate-like home a blocking-by-default posture (if
a product opts in) might actually need, since a PR-reviewer agent finding is advisory-shaped by
default (WARNING) unless promoted to BLOCKING. Design must pick one and state why, not both by
default.

## Requirements

MUST unless marked SHOULD.

- **CE4-1** Socket 4 activates for a product only when `classification.structural.
  exposes_programmatic_interface` is present in `project-state.yaml`, recognized via the existing
  `coverage_probes.py` presence semantics (Decision 1) — not a new structural flag or a second
  detection path.
- **CE4-2** The product declares its API-diff producer as an opaque invocation or result-artifact
  path; prawduct validates no ecosystem-specific tool name and ships no per-language enum or
  allowlist of "supported" tools (Decision 2).
- **CE4-3** A new project-state.yaml boolean key gates blocking vs. report-only for this socket,
  defaulting to `false`, read with the same helper (`read_bool_yaml_key`) `coverage_required` and
  `operator_verification_required` already use (Decision 3).
- **CE4-4** A product with `exposes_programmatic_interface` set but no producer declared reports a
  distinct *unchecked* state — never silently coalesced with a clean/passing verdict — mirroring
  `gates.py`'s `changes_unjudged` vs. missing-coverage split (`gates.py:1228-1234`) as the concrete
  precedent for "unchecked, never passed."
- **CE4-5** The verdict prawduct consumes is a normalized, tool-agnostic artifact the product's
  declared producer emits; prawduct's own code contains no per-ecosystem report parser (Decision 4).
  The exact shape of that artifact is explicitly out of this document's scope (design-stage).
- **CE4-6** Whatever storage this socket's verdict lands in respects additive-only field evolution
  and loud (never silent) handling of a schema-ahead or malformed record, consistent with
  `data-model.md`'s existing forward-incompatibility rules; if it lands in the shared evidence store,
  a new `kind` is added deliberately to `evidence.py`'s `KNOWN_KINDS` rather than assumed (Decision
  5).
- **CE4-7** The verdict composes into the PR/release boundary as a release-level decision, not a
  per-chunk Critic concern, through one of the two candidate seams named in Decision 6 — the choice
  and its rationale are a design-stage deliverable, not resolved here.
- **CE4-8** Once built, the motivating case — a changed output format socket 1 (diff coverage)
  reports green on — is demonstrably caught by this mechanism at build time, with no test suite
  invoked.

## Acceptance

- [ ] A product with `exposes_programmatic_interface` set and a declared producer receives a
      breaking-change verdict at build time, using existing trigger-recognition logic
      (`coverage_probes.py`), with zero prawduct-authored per-ecosystem diffing logic.
- [ ] A product with the flag set but no producer declared is reported *unchecked*, distinctly from
      a clean pass — never silently green.
- [ ] The check defaults report-only; flipping one declared key (mirroring `coverage_required`)
      makes it block.
- [ ] The motivating case (a breaking output-format change with socket 1 green) is caught here, at
      build time, with no tests run.
- [ ] No new per-ecosystem parser, tool wrapper, or symbol table ships in prawduct as part of this
      item.

## Scope-out (this item)

- The shared four-socket contract, its rationale, blind spots, and adoption/rollout mechanics
  (yield-gated advisory, onboarding reconciliation) — `change-evidence-design.md`'s territory, per
  the issue's own scope-out.
- Sockets 1–3 (#249, #618, #619) — sibling items with their own requirements passes.
- Whether all four sockets share one `project-state.yaml` declaration surface or four
  (`change-evidence-design.md` Open Question #1) — cross-socket, not decided for socket 4 in
  isolation; whichever socket's design lands first should settle it, or it is settled directly on the
  design doc.
- The minimal verdict-artifact shape (Decision 4), the evidence-storage choice (Decision 5), and the
  exact PR-gate integration seam (Decision 6) — all explicitly deferred to the design pass.
- Populating discovery with a per-ecosystem "which API-diff checker is standard" question
  (LNG-5W8R's gap, named in Grounding facts) — a separate, already-tracked item; this socket only
  needs the declaration surface that question would eventually populate to exist.
- Wiring prawduct's own `api-contract.md` (its CLI surface) up as a live socket-4 producer — a
  natural dogfooding candidate once built, not a requirement of building the capability itself.

## Evidence / references

- `.prawduct/artifacts/change-evidence-design.md` — the shared four-socket design; §"Socket 4 —
  Contract broken? (API diff)" (lines 156-169), adoption §"New products" (260-266), Open Questions
  (303-318).
- `plugin/templates/project-state.yaml:28-32,357,359-388` — the `exposes_programmatic_interface`
  template declaration, `coverage_required`, and `test_command`/`test_commands`, the closest existing
  producer-declaration precedent.
- `.prawduct/project-state.yaml:112-116,569,580` — prawduct's own recorded flag, `coverage_required`,
  and `operator_verification_required`.
- `plugin/lib/coverage_probes.py:104,137,151-159,162-228` — the existing recognition logic for
  `exposes_programmatic_interface` presence (`_structural_recorded_at`, `_ABSENT_VALUES`,
  `_opens_nested_block`), and its trigger table.
- `plugin/lib/gates.py:1215-1246` — `verify_coverage`, the concrete report-only/opt-in-blocking
  precedent, including the `changes_unjudged`-vs-failure split CE4-4 mirrors.
- `plugin/lib/evidence.py:13-23,58-59,78,131-136` — the evidence store envelope, `SCHEMA_VERSION`/
  `SUPPORTED_SCHEMAS`, `KNOWN_KINDS`, and its fail-closed rejection of unregistered kinds.
- `.prawduct/artifacts/data-model.md:24-28,57` — the reserved-but-unratified `test-run`/`pr-review`/
  `promotion` kinds, the open question `change-evidence-design.md` inherits.
- `plugin/skills/pr/review-protocol.md:5,45-93,154-167` — the PR reviewer's goals, severity levels,
  the existing `test-status` exit-code precedent (line 69), and the "prefer strengthening an existing
  goal" extension guidance.
- `plugin/bin/prawduct-hook:3718`, `plugin/lib/release_readiness.py:274` — `check-releasability`, the
  alternative mechanical-gate integration candidate.
- `.prawduct/artifacts/architecture.md:66,74,79-80` — the Direction norms grounding "prawduct
  implements no differ, maintains no matrix."
- `.prawduct/artifacts/api-contract.md:18-39,63-106,296-330` — prawduct's own filled instance,
  showing how a product's published surface is already named concretely per product.
- `plugin/methodology/discovery.md:113,117,222` — confirms the discovery gap the design doc cites (a
  separate, already-tracked item, not this one's scope).
