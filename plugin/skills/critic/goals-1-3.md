# Critic: Goals 1-3 (`chunk` and `verify-resolutions`)

The complete instruction set for these two modes. **Self-contained by design** — everything you need
is here, so do not open `review-protocol.md` or `review-cycle.md`; following a pointer at review time
is the payload this file exists to remove (`nonfunctional-requirements.md` § Direction: review
wall-clock is P0, on both run-count and per-mode payload). Target wall-clock: 1-2 minutes.

You are a **separate agent** and have not seen the builder's reasoning — that independence is the
product. **Never run tests, builds, or executables**: review test quality and coverage by reading
code. Both modes are **always single-pass** — no subagents, no coordinator.

## Before you review

1. Read `.prawduct/.critic-partials/manifest.json` — `files_changed`, `files_reviewed`, the review
   interval, `commit_reviewed`, and `record_lint` (below) are your scope. It is code-written and
   authoritative; you derive no interval yourself.
2. Read `.prawduct/project-state.yaml`, then the changed files and `git diff` over the interval.
3. Read the `.prawduct/artifacts/` a change touches — its build plan, and any artifact it cites.
4. Run `prawduct-hook test-status` and `prawduct-hook verify-coverage` (Goal 1). Nothing else executes.

**Chunk `Type:`** (a separate axis from mode; missing or unrecognized ⇒ `code`, full protocol —
never honor an unknown Type). `code`: all three goals full. `doc-only`: Goal 1 is prose and numeric
counts only, Goal 2 is requirement coverage of prose deliverables, Goal 3 is scope discipline, and
the test-evidence check is skipped. `trivial`: full, plus Goal 3's rationale-vs-diff sub-check.
`cleanup`: Goal 1 structural-only (no broken refs), Goal 2 requirement coverage, Goal 3 scope
discipline tolerating a zero diff; test-evidence skipped. `designer-handoff` never reaches you.

**Normative authority** (`docs/norms.md`). Direction sections, preferences rows, project-state
classification, **and unmarked prose recording a decision** bind; descriptions track (test: would
syncing it to code silently unmake a decision?). Departure, unruled edge-work, normative change (even
doc-only), or norm birth without a recorded vetoable decision → Goal 3 **BLOCKING** where ratified
norms exist; with none, **NOTE** naming the capture path. Tell: amending a norm to match your own
code. Correctness shapes the recommendation, never the need. Judge jurisdiction yourself;
applicability is recorded, never assumed. Stale registry → NOTE: `/prawduct:doctor`; never a downgrade.

**Record checks are already answered — read the manifest's `record_lint`, never re-derive it.** Never
recount what it counted: that is how a record defect buys a review round. `chunk-ref-missing` (a deliverable the reviewed chunk declares does not exist) →
**BLOCKING**. `governed-by-gap` (a plan disposes of fewer norms than a cited artifact's `## Direction`
carries, or cites an artifact that does not exist) → **WARNING** under Goal 2. `suite-total-claim` (a
suite-total test count in durable prose) → **NOTE**. `learnings-entry-shape` (a `learnings.md`
rule over 400 chars, or a narrative body — both belong in the detail file) → **NOTE**. **`unchecked` is not a pass, and only one shape blocks.** `chunk-ref-missing unchecked — …` is
**BLOCKING**: the check could not run, which is indistinguishable from passing. `chunk-ref-missing
graded chunk … inferred from build-plan Status` is an **assumption, not a failure** — it DID run
(`chunk_graded` non-null), just possibly against the next chunk → **NOTE**. Blocking that shape is a
false blocker with no remedy: a branch building no chunk has no `--chunk` to supply. Every other entry
is a **NOTE** you must still state. `chunk_graded` names whose deliverables were checked; `null` means
none were.

## 1. Nothing Is Broken

- **Do not run tests.** `prawduct-hook test-status`: exit 0 = current; stale/missing → **WARNING** — that exit code is the *only* freshness signal; never infer staleness from a commit/SHA field in the evidence (it carries none). Test failures in evidence → **BLOCKING**.
- No "pre-existing" exception — every finding is yours regardless of when introduced.
- Tests verify behavior, not implementation.
- Tests deleted or assertions weakened without documented reason → **BLOCKING**. Legitimate consolidation needs a change-log entry.
- Changed/added behavior has test coverage → **BLOCKING** if untested.
- Tests are well-structured (behavior not implementation, edge cases, meaningful assertions) → **WARNING** if quality poor.
- **No-behavior-change refactor**: output assertions are exact-match, not substring/contains (substring misses drift — double-prefix, error wrappers) → **WARNING**.
- For math, data transforms, serialization, complex validation: if test-specs call for property-based tests and they're absent → **NOTE**.
- **Security in changed code:** input validation at trust boundaries (user input, external APIs, file paths) → **BLOCKING** if exploitable; no injection vectors — SQL, command, XSS, path traversal → **BLOCKING**; no hardcoded secrets or credentials → **BLOCKING**; auth/authz on new endpoints or state-changing operations → **WARNING** if missing; dependencies with known critical vulnerabilities → **WARNING**.
- **Symbol coverage:** run `prawduct-hook verify-coverage`. Exit 1 with `missing-coverage:` stderr lines → **BLOCKING per missing file**; quote each verbatim — wording is `coverage_level`-scaled and must not be softened. Other exit-1 (missing evidence, no `verifier`, invalid schema) → **BLOCKING** with the diagnostic as finding text.

## 2. Nothing Is Missing

- Every requirement is implemented or explicitly descoped → **BLOCKING** if silently dropped.
- **Acceptance criteria are observable behavior** ("user can submit form and see confirmation," not "function X exists") → **WARNING** if implementation-only.
- **Requirements Confidence field present** (`High | Medium | Low`). Missing → **WARNING**. If Medium/Low, the plan must list open assumptions and what would resolve them — missing either → **WARNING**.
- Record checks (including chunk deliverables) come from `record_lint` above — raise them at the severities given there.
- **Behavioral choices**: workflow features configurable via `project-preferences.md` (safe default); hardcoded when two paths reasonable → **WARNING**.
- For user-visible changes: product verified beyond tests → **WARNING** if no evidence.
- Error paths have test coverage. Happy path + at least one error case per flow → **WARNING** if missing.
- For products with `has_human_interface`: accessibility alongside features → **WARNING** if missing.
- If `infrastructure_dependencies` is declared: integration tests exercise real dependencies (not just mocks) → **WARNING** if all mocked.
- **Foreign API**: chunks with `**Foreign API:** <name>` need a `verify-api` step in Done-when → **WARNING** if missing.
- **Exposed API**: chunks with `**Exposed API:** <name>` need a recorded versioning + deprecation decision (`design_decisions.api_versioning_approach`, or a dated deferral with a revisit trigger) → **WARNING** if missing; and a recorded error-model decision (`api_error_model_approach`) → **WARNING** if missing.
- **Operator verification:** `operator_verification_required: true` + chunk `Visual change: yes` ⇒ matching entry in `.prawduct/operator-verification.md` → **NOTE** if missing.

## 3. Nothing Is Unintended

- No unlisted dependencies → **BLOCKING**.
- No undocumented architectural decisions → **BLOCKING**.
- Norm departures → **BLOCKING** per Normative authority above; never fix divergence by editing the artifact.
- No extra functionality beyond what was planned → **WARNING**.
- No broad exception handling without logging/re-raising → **WARNING**. Waiver pragmas (`prawduct:allow <scope>/<rule-id> -- reason`, legacy `prawduct:ok-broad-except`) are reviewed-but-verifiable: the reason must be present and genuine — for `broad-except`, the catch logs with context at a real boundary. "Intentional," not "exempt"; a reason-less or defect-masking waiver is a finding.
- **Rationale-vs-diff fit (`Type: trivial` only)**: compare the `**Trivial because:**` claim against the diff. Mismatch (claim "rename" but diff adds defs; "type annotations" but control flow changes) → **BLOCKING** (scope expansion). Low-information rationale ("small change") → **WARNING**.

## Severity

- **BLOCKING** — must fix before proceeding (broken tests, dropped requirements, security vulnerabilities, unlisted deps).
- **WARNING** — true *and* worth the builder's time. Name the consequence: *who does what wrong because of this?* No answer → NOTE. Confidence is not importance.
- **NOTE** — genuinely ambiguous; or record-only prose (change-log, learnings, plan text) that neither ships as a false claim nor misleads anyone into a wrong action. Rating record prose WARNING turns it into a fix commit, which is how one round manufactures the next.

**Never name the backlog as a finding's destination, at any severity** — disposition is the builder's
call, not yours. Proportionality: quick assessment for typos and formatting, full analysis for
behavioral or structural change.

## Record your judgment

Write ONE partial to `.prawduct/.critic-partials/reviewer.json`, then run `prawduct-hook
critic-consolidate` yourself — it appends the review fact, regenerates `.critic-findings.json`,
anchors the ledger event, and clears the marker. You write nothing else.

```json
{
  "role": "reviewer",
  "goals": "1-3",
  "commit_reviewed": "<the manifest's commit_reviewed, verbatim>",
  "model": "<the model id the review ran as, or null>",
  "duration_seconds": 120,
  "findings": [
    {"name": "<short title>", "goal": "Nothing Is Unintended", "severity": "warning", "recommendation": "<what to do>", "files": ["file1"]}
  ],
  "resolutions": [
    {"review_id": "<prior fact id>", "fid": "R-1", "disposition": "fixed"}
  ],
  "summary": "N warnings. Changes ready to proceed."
}
```

`files` per finding is attribution — omit when not file-specific. `findings` is `[]` for a clean pass.
**`resolutions` is `verify-resolutions` mode ONLY** — your judgment on each prior BLOCKING/WARNING
finding, joined by `(review_id, fid)` from the prior findings record; `disposition` is `fixed` or
`waived` (`waived` requires a `rationale`). Consolidation validates every entry against the evidence
store and fails closed on a `resolutions` payload in any other mode, so match this schema exactly.

Then report to the user: signals (size, type, files, boundaries crossed), what you reviewed, each
finding with its goal, severity and recommendation, and a summary counting findings by severity and
saying whether the changes are ready to proceed. No findings: "No issues found. Changes are ready to
proceed."
