# Issue #620 — Gates: Detect Breaking Changes to a Published Surface: Design

`status: draft · stage: design · area: gates · added: 2026-08-10 · source: scheduled backlog
session · issue: https://github.com/brookstalley/prawduct/issues/620`

Builds on `documentation/issues/620-requirements.md` (CE4-1 through CE4-8, Decisions 1–6). This
document resolves the requirements doc's three design-stage scope-outs — the minimal verdict-
artifact shape (Decision 4), the evidence-storage choice (Decision 5), and the PR-gate integration
seam (Decision 6) — and specifies file-by-file changes an implementation chunk can follow directly.

Socket 4 of the four-socket change-evidence contract; siblings #249 (socket 1), #618 (socket 2),
#619 (socket 3) have their own requirements/design passes. The shared contract itself
(`.prawduct/artifacts/change-evidence-design.md`) is not restated here.

## Summary of what ships

1. **CE4-1, CE4-2, CE4-3** — two new `project-state.yaml` keys: `api_diff_producer` (opaque
   invocation) and `api_diff_required` (boolean, default `false`).
2. **CE4-4, CE4-5, CE4-8** — a new `lib/gates.py` function, `api_diff_status()`. No persisted
   verdict artifact — the declared producer is invoked live on every call (Decision 5 below).
3. A new `prawduct-hook api-diff-status` command: thin wrapper, dispatch case, `_USAGE` entry,
   `_EPHEMERAL_SAFE_COMMANDS` membership.
4. **CE4-7** — `review-protocol.md`'s Merge Hygiene goal gains one bullet, mirroring the existing
   `test-status` bullet's shape exactly.
5. `plugin/templates/project-state.yaml` documentation for the two new keys.

## Decisions resolved

### Decision 4 — the minimal verdict primitive

A normalized JSON object the declared producer prints to **stdout**:

```json
{"schema": 1, "breaking": [{"symbol": "…", "description": "…"}]}
```

`breaking` is a list of descriptors; an empty list is a clean verdict. `schema` lets the reader
reject a version it does not understand rather than misparse it — the same posture
`evidence.py`'s `SUPPORTED_SCHEMAS` and `data-model.md`'s forward-incompatibility rule already
require (CE4-6). `symbol` and `description` are free-form strings prawduct never inspects or
requires beyond "present, if `breaking` is non-empty" — it renders them, it does not parse them.
This mirrors socket 1's own minimal primitive at the same level of abstraction
(`change-evidence-design.md:109-115`: "a set of *uncovered changed lines* — `file:line`... the four
formats above are conveniences layered on top, never the contract itself"). The two fields are the
whole contract; a per-ecosystem tool's native report (japicmp XML, `cargo public-api diff` text,
`oasdiff` JSON) is translated into this shape by the product's own producer command — never by
prawduct — which is what keeps CE4-5 ("no per-ecosystem parser") true regardless of which tool a
given product runs.

### Decision 5 — no persisted verdict artifact

Requirements' Decision 5 deliberately left open whether a verdict lands in the shared evidence
store (`evidence.jsonl`, a new `kind`) or a dedicated per-product file mirroring
`.test-evidence.json`. Neither is needed. The socket's defining property — "near-zero test-runtime
cost... it reads a built surface, with no tests involved" (issue body; `change-evidence-design.md`
socket 4: "Producer:... near zero" test-runtime cost) — is exactly why `.test-evidence.json` exists
as a *separate write* from `test-status`'s *read*: running the full suite is expensive, so
`test-evidence record` decouples the (expensive, occasional) write from the (cheap, frequent) read.
Socket 4 has no expensive half to decouple from — the producer itself is cheap, by the design doc's
own framing, so `api-diff-status` invokes it live, every time it's asked, and writes nothing to
disk.

This sidesteps `data-model.md`'s unratified "subsume test-run/PR-review evidence into the shared
store" question entirely (CE4-6's requirement is now vacuous by construction — there is no storage
to bump a schema or add a `kind` to). It also means a stale verdict can never exist: the answer
`api-diff-status` gives always reflects the current declared producer run against the current tree,
not a record written at some earlier point that might have drifted. If a future socket (1–3) needs
persistence because its own cost model differs, that is a decision for that socket's own design
pass — this item sets no precedent either way, because the reasoning here is specific to socket 4's
near-zero cost, not a general "sockets don't persist" claim.

**Consequence for CE4-4 ("unchecked, never passed")**: since there is no stored record to inspect,
"unchecked" is a live classification `api-diff-status` computes and prints on every invocation
(§ Section 2), not a state some earlier write left behind — distinguishable from "clean" and
"breaking" the same way `verify_coverage`'s `changes_unjudged` is distinguishable from
"missing-coverage" (`gates.py:1228-1234`), just computed fresh rather than read from a file.

### Decision 6 — Merge Hygiene, not `check-releasability`

`review-protocol.md`'s own extension guidance is to prefer strengthening an existing goal over
adding a new one (`review-protocol.md:165-167`). Merge Hygiene already has the exact shape this
needs: an agent-judged bullet that runs one mechanical `prawduct-hook` exit-code check and assigns
severity from it — the `test-status` bullet (`review-protocol.md:69`) is the direct precedent, down
to "don't run \[the expensive thing\] yourself; read the mechanical check's exit code." `check-
releasability` is structurally a different gate — scope classification against a release plan's
withheld/ships table (`release_readiness.py:274-283`) — and has no existing notion of a per-PR diff
check or of WARNING/BLOCKING severity; extending it would mean teaching a release-scope classifier
about producer declarations it has no other reason to model. Socket 4 rides Merge Hygiene's
established pattern instead of inventing a second one.

## Section 1 — `project-state.yaml` keys (CE4-1, CE4-2, CE4-3)

**Where:** `plugin/templates/project-state.yaml`, a new heading placed directly after the existing
"OPERATOR VERIFICATION" block (currently ending ~line 405), matching that block's and the
"COVERAGE EVIDENCE" block's existing comment style and placement convention (both currently precede
this point in the file).

```yaml
# =============================================================================
# CHANGE EVIDENCE — PUBLISHED SURFACE (opt-in, socket 4 of the change-evidence contract)
# =============================================================================
# Activates only when classification.structural.exposes_programmatic_interface
# is recorded present. Declare the command that prints socket 4's normalized
# verdict to stdout — a wrapper around cargo-public-api / japicmp / gocompat /
# oasdiff / api-extractor (whichever fits the ecosystem) emitting
# {"schema": 1, "breaking": [...]}. prawduct never invokes any of those tools
# itself and parses no per-ecosystem report format. See
# `.prawduct/artifacts/change-evidence-design.md` and
# `documentation/issues/620-design.md`.

# api_diff_producer: scripts/api-diff-verdict.sh
#   Opaque, unwrapped shlex-split invocation, run from the repo root — same
#   "declare it, don't wrap it" contract as test_command:, minus the
#   {junit_xml} substitution (there is no report path to inject; the verdict
#   comes back over stdout). Shell operators (&&, |, FOO=1) are not
#   supported — point the command at a script for compound invocations.

# api_diff_required: false
#   Opt-in blocking. Defaults to report-only: a breaking-change verdict is
#   still surfaced at PR review, but does not fail the check until a product
#   with real consumers sets this true.
```

**Compatibility:** both keys are optional and additive; a `project-state.yaml` predating this
change reads as "not declared" (`read_str_yaml_key` returns `None`) and "false"
(`read_bool_yaml_key`'s existing fail-soft-to-`False` default) respectively — no migration, exactly
`coverage_required`'s existing posture.

## Section 2 — `lib/gates.py`: `api_diff_status()`

**Where:** `plugin/lib/gates.py`, placed near `verify_coverage` (same module — both are
project-state-boolean-gated checks composed into the same PR/Critic surface, reading via
`read_bool_yaml_key`/`read_str_yaml_key` from `.core`).

```python
def api_diff_status(project_dir: Path) -> int:
    """Socket 4 (CE4, issue #620) — breaking-change verdict for the product's
    declared published-surface producer.

    No persisted artifact: the declared ``api_diff_producer`` command is
    invoked live on every call. The socket's whole premise is that this is
    cheap ("near-zero test-runtime cost... reads a built surface") — unlike
    test evidence there is no expensive half to decouple write-time from
    read-time for (issue #620 design, Decision 5).

    Exit codes:
      0 — not applicable (``exposes_programmatic_interface`` unset), unchecked
          (no producer declared, or the producer errored/emitted an invalid
          verdict while ``api_diff_required`` is false), clean (empty
          ``breaking`` list), or breaking-but-report-only.
      1 — ``api_diff_required: true`` AND (a non-empty ``breaking`` verdict,
          OR the producer could not be run / emitted an invalid verdict).
          Mirrors ``verify_coverage``'s missing-evidence-file case: an
          unusable verdict source is a hard failure only when the product
          opted into blocking; report-only mode never blocks on it (CE4-4 —
          unchecked is never silently coalesced with a *pass*, but it is
          also never itself a failure unless the product asked for teeth).

    stdout carries exactly one status line (``not-applicable: ...`` /
    ``unchecked: ...`` / ``clean: ...`` / ``breaking: N change(s)...``),
    quotable directly in a Merge Hygiene finding — same convention
    ``verify_coverage`` uses for its stderr lines.
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    state_path = prawduct_dir / "project-state.yaml"

    from . import coverage_probes  # noqa: PLC0415 — lazy, mirrors release_readiness's `views` import

    if not coverage_probes._structural_recorded_at(state_path, "exposes_programmatic_interface"):
        print("not-applicable: exposes_programmatic_interface is unset")
        return 0

    producer = read_str_yaml_key(state_path, "api_diff_producer")
    if producer is None:
        print("unchecked: no api_diff_producer declared")
        return 0

    blocking = read_bool_yaml_key(state_path, "api_diff_required")

    verdict, error = _run_api_diff_producer(producer, project_dir)
    if error is not None:
        if blocking:
            print(f"error: api_diff_producer failed: {error}", file=sys.stderr)
            return 1
        print(f"unchecked: producer error ({error}) — report-only, not blocking")
        return 0

    breaking = verdict["breaking"]
    if not breaking:
        print(f"clean: no breaking changes (`{producer}`)")
        return 0

    for item in breaking:
        print(f"  - {item.get('symbol', '(unnamed)')}: {item.get('description', '')}",
              file=sys.stderr)
    if blocking:
        print(f"breaking: {len(breaking)} change(s) — api_diff_required: true", file=sys.stderr)
        return 1
    print(f"breaking: {len(breaking)} change(s) — report-only (api_diff_required: false)")
    return 0
```

`_run_api_diff_producer(producer, project_dir)` — a small helper returning `(verdict_dict, None)`
or `(None, error_string)`:

- `shlex.split(producer)` (same list-form, no-shell-operators posture as `test_command:`'s
  execution path in `bin/prawduct-hook`).
- `subprocess.run(argv, cwd=project_dir, capture_output=True, text=True, timeout=60)` — a fixed
  timeout because "near-zero cost" is the socket's own stated property; a producer that hangs is
  itself a producer error, not a slow-but-valid run. A named constant
  (`_API_DIFF_PRODUCER_TIMEOUT_SECONDS = 60`), not a hardcoded literal, so a future chunk can tune
  it without hunting for the number.
- Non-zero exit, `OSError` (command not found), or `subprocess.TimeoutExpired` → `error` describes
  which.
- `json.loads(result.stdout)` — a `JSONDecodeError`, a non-dict, a `schema` key other than `1`, or a
  missing/non-list `breaking` key are all `error` (schema-ahead or malformed both loud-block per
  CE4-6's forward-compatibility posture, applied here to a live read instead of a stored file — the
  same rule, different medium).

**Note on `coverage_probes._structural_recorded_at`**: private-by-convention, imported directly
across modules — the exact pattern `ledger.py` already uses for `evidence.py`'s `_plugin_version()`
(issue #262 design, §1: "reuse `evidence.py`'s existing `_plugin_version()`... `from .evidence import
_plugin_version`"). No second detector is written (CE4-1); the existing recognition logic is reused
as-is, including its `_ABSENT_VALUES` semantics.

## Section 3 — `bin/prawduct-hook` wiring

**Thin wrapper**, mirroring `cmd_verify_coverage` exactly:

```python
def cmd_api_diff_status(project_dir: Path) -> int:
    """Socket 4 breaking-change gate. Thin wrapper — body lives in
    ``lib.gates.api_diff_status`` (issue #620)."""
    return _gates().api_diff_status(project_dir)
```

**Dispatch** (`main()`, alongside the existing `elif command == "verify-coverage":`):

```python
elif command == "api-diff-status":
    return cmd_api_diff_status(project_dir)
```

**`_USAGE`**: extend the existing `verify-coverage` segment —

```
"verify-records [--base <t>] [--head <t>] [--chunk <id>] [--scope <s>] [--json]|verify-coverage|"
"api-diff-status|"
```

**`_EPHEMERAL_SAFE_COMMANDS`**: add `"api-diff-status"` to the frozenset (alphabetical placement,
before `"bug-inbox"`) — read-only by construction: it never writes to `.prawduct/` or the tree, only
invokes the declared producer and prints its verdict. Per the module's own comment above that set
("verified command by command by READING each implementation for a write path, never inferred from
the name"), this is a deliberate per-command check, not a batch add.

## Section 4 — `review-protocol.md`: Merge Hygiene

**Where:** `plugin/skills/pr/review-protocol.md`, `### 3. Merge Hygiene`, as a new bullet directly
after the existing test-evidence-freshness bullet (currently `review-protocol.md:69`) — same
section, same severity family, same "don't run the expensive thing yourself, read the mechanical
check's exit code" shape:

> - **A declared published-surface producer's verdict is current.** When
>   `classification.structural.exposes_programmatic_interface` is set, run `prawduct-hook
>   api-diff-status`. Don't invoke the product's underlying diff tool yourself — the mechanical
>   check already ran it. If it prints `breaking: N change(s)...` → **WARNING** by default
>   ("published surface has N breaking change(s), report-only"), or **BLOCKING** when the product
>   declared `api_diff_required: true` (exit code 1 IS that signal — quote the stdout/stderr lines
>   directly, same as the test-evidence bullet quotes `test-status`). If it prints `unchecked: ...`
>   → **WARNING** ("published surface has no declared `api_diff_producer`") — never silently read as
>   clean. `not-applicable` and `clean` need no finding.

**`pr/SKILL.md` `allowed-tools`**: add `Bash(prawduct-hook api-diff-status)` (and the
`python3 plugin/bin/prawduct-hook api-diff-status` mirror, matching every other paired entry already
in that frontmatter line) alongside the existing `Bash(prawduct-hook test-status)` entry.

## Files touched

| File | Change |
|---|---|
| `plugin/templates/project-state.yaml` | New "CHANGE EVIDENCE — PUBLISHED SURFACE" block: `api_diff_producer`, `api_diff_required` (CE4-1–3) |
| `plugin/lib/gates.py` | New `api_diff_status()`, `_run_api_diff_producer()`, `_API_DIFF_PRODUCER_TIMEOUT_SECONDS` (CE4-4, CE4-5, CE4-8) |
| `plugin/bin/prawduct-hook` | New `cmd_api_diff_status`; dispatch case; `_USAGE` entry; `_EPHEMERAL_SAFE_COMMANDS` membership |
| `plugin/skills/pr/review-protocol.md` | One new Merge Hygiene bullet (CE4-7) |
| `plugin/skills/pr/SKILL.md` | `allowed-tools` gains the `api-diff-status` Bash pair |
| `tests/test_api_diff_gate.py` (new) | See test plan below |

## Test plan (`tests/test_api_diff_gate.py`)

Following `tests/test_verify_coverage_gate.py`'s existing style — real git repos, real hook
subprocess, no mocking of git or the filesystem (the module docstring's own stated rationale
applies equally here: "the gate's job is git + filesystem inspection, and mocking either would test
nothing useful"). Producer commands are small fixture scripts (`python3 -c "..."` or a tiny shell
script under the fixture repo) printing fixed JSON to stdout — no real API-diff tool involved.

1. **Not activated** — no `exposes_programmatic_interface` recorded → stdout
   `not-applicable: exposes_programmatic_interface is unset`, exit 0.
2. **Activated, no producer declared** — `exposes_programmatic_interface: {consumers: external}`
   present, `api_diff_producer` absent → stdout `unchecked: no api_diff_producer declared`, exit 0.
3. **Clean verdict** — producer prints `{"schema": 1, "breaking": []}` → stdout
   `clean: no breaking changes (...)`, exit 0.
4. **Breaking, report-only (default)** — producer prints a `breaking` list, `api_diff_required`
   absent → stdout `breaking: N change(s) — report-only (api_diff_required: false)`, each item on
   stderr, exit 0.
5. **Breaking, blocking** — same producer, `api_diff_required: true` → stderr carries the same
   per-item lines plus `breaking: N change(s) — api_diff_required: true`, exit **1**.
6. **Producer errors, report-only** — a producer script that exits non-zero (or emits invalid JSON)
   with blocking unset → stdout `unchecked: producer error (...)`, exit 0 — never silently "clean".
7. **Producer errors, blocking** — same producer script, `api_diff_required: true` → stderr
   `error: api_diff_producer failed: ...`, exit **1**.
8. **Producer times out** — a fixture script that sleeps past
   `_API_DIFF_PRODUCER_TIMEOUT_SECONDS` (test overrides the constant, does not actually wait 60s) →
   treated identically to case 6/7's error path depending on `api_diff_required`.
9. **Schema mismatch** — producer prints `{"schema": 2, "breaking": []}` → treated as a producer
   error (loud, not silently parsed as schema 1), exercising both the report-only and blocking
   branches once each.

## Open items for the build chunk (not resolved here)

- Exact wording of the fixture producer scripts (cosmetic — any script printing the two verdict
  shapes suffices).
- Whether `_run_api_diff_producer`'s timeout should be product-configurable — no knob proposed; the
  socket's own "near-zero cost" framing makes 60s generous rather than tight, and a product needing
  longer is arguably not satisfying the socket's own cost premise. Revisit only if real-world use
  proves this wrong.

## Acceptance (carried from requirements, now with an implementation path)

- [ ] A product with `exposes_programmatic_interface` set and a declared producer receives a
      breaking-change verdict at PR-review time (`api_diff_status`, invoked from Merge Hygiene),
      with zero prawduct-authored per-ecosystem diffing logic — pinned by
      `tests/test_api_diff_gate.py` cases 3–5.
- [ ] A product with the flag set but no producer declared is reported *unchecked*, distinctly from
      a clean pass — pinned by case 2, never silently green.
- [ ] The check defaults report-only; `api_diff_required: true` makes it block — pinned by cases 4
      vs. 5.
- [ ] The motivating case (a breaking output-format change with socket 1 green) is caught here, at
      PR-review time, with no tests run — `api_diff_status` never invokes a test suite; the
      producer it runs is the product's own diff tool, not prawduct's.
- [ ] No new per-ecosystem parser, tool wrapper, or symbol table ships in prawduct — `gates.py`
      parses only the two-field `{schema, breaking}` envelope, never a tool-native report format.

## Evidence / references

- `documentation/issues/620-requirements.md` — CE4-1–8, Decisions 1–6, grounding facts.
- `.prawduct/artifacts/change-evidence-design.md:156-169` — socket 4's design-doc entry (producer
  list, posture, consumer).
- `plugin/lib/coverage_probes.py:104,137,151-230` — `_structural_recorded_at`, `_ABSENT_VALUES`,
  the reused trigger-recognition logic (CE4-1).
- `plugin/lib/core.py:180-239` — `read_str_yaml_key`, `read_bool_yaml_key`, reused for
  `api_diff_producer`/`api_diff_required`.
- `plugin/lib/gates.py:1215-1246` — `verify_coverage`, the report-only/opt-in-blocking precedent
  CE4-3/CE4-4 mirror, including the `changes_unjudged`-vs-failure split.
- `plugin/lib/evidence.py:58-59,78,131-136` — `SUPPORTED_SCHEMAS`/`KNOWN_KINDS` fail-closed
  posture, the model for the verdict envelope's own `schema` field (Decision 4) even though the
  verdict itself is never persisted there (Decision 5).
- `.prawduct/artifacts/data-model.md:24-28,57` — the unratified evidence-store subsumption question
  Decision 5 sidesteps.
- `plugin/skills/pr/review-protocol.md:69,165-167` — the `test-status` Merge Hygiene bullet
  (precedent for shape) and the "prefer strengthening an existing goal" extension guidance.
- `plugin/lib/release_readiness.py:274-283` — `check_releasability`, the rejected alternative
  integration seam, and why its shape doesn't fit (Decision 6).
- `plugin/bin/prawduct-hook` (`cmd_test_status`, `cmd_verify_coverage`, dispatch, `_USAGE`,
  `_EPHEMERAL_SAFE_COMMANDS`) — the exact wiring pattern §3 follows.
- `tests/test_verify_coverage_gate.py:1-19` — the real-subprocess test style §"Test plan" follows,
  and its stated rationale for not mocking git/filesystem.
