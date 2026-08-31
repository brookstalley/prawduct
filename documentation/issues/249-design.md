# Issue #249 — Coverage: The Coverage Floor Is Python-Only: Design

`status: draft · stage: design · area: coverage · added: 2026-08-31 · source: scheduled backlog
session · issue: https://github.com/brookstalley/prawduct/issues/249`

Builds on `documentation/issues/249-requirements.md` (CE1-1 through CE1-10, Decisions 1–8). This
document resolves the requirements doc's two design-stage deferrals — the exact verdict
serialization (Decision 2's "left open to design" clause) and whether executed-level line data
extends the existing F4a schema or lives in a separate shape (Decision 4) — and specifies
file-by-file changes an implementation chunk can follow directly. It also settles, for socket 1,
the cross-socket declaration-surface question `change-evidence-design.md`'s Open Questions left
open, and retires that same artifact's "which real toolchains cannot emit any of the four formats"
open question outright (both resolved in the two Decisions immediately below).

Socket 1 of the four-socket change-evidence contract — the last of the four to reach design.
Siblings #618 (socket 2), #619 (socket 3), #620 (socket 4) already have requirements and design
merged. The shared contract itself (`.prawduct/artifacts/change-evidence-design.md`) is not
restated here.

## Summary of what ships

1. **CE1-1, CE1-8** — one new `project-state.yaml` key: `coverage_producer` (opaque invocation,
   optional — no new boolean; `coverage_required` is reused per requirements Decision 5).
2. **CE1-2, CE1-3** — `bin/test-reference-verify` gains a new `--executed-command <cmd>` flag and a
   new `_build_executed_evidence_fields()` function. When invoked with the flag, it runs the
   declared producer instead of its own symbol-grep and writes `coverage_level: "executed"`. Its
   existing symbol-grep path (the floor) is untouched — same file, same entry point, a second
   branch.
3. **CE1-4** — one new *optional*, additive F4a field: `uncovered_lines` (a list of `file:line`
   strings). `changes_referenced`/`changes_unjudged`/`coverage_level` are populated exactly as
   `verify_coverage` already reads them — **CE1-3's "no new gate logic" promise is kept literally:
   `lib/gates.py` needs zero code changes.**
4. `bin/prawduct-hook`'s existing `test-evidence record` overlay call (the one call site that
   already invokes `test-reference-verify --merge-into`) reads the new key and passes
   `--executed-command` through when declared. No new `prawduct-hook` subcommand.
5. **CE1-9** — the Case-B caveat added at three doc sites: `test-reference-verify`'s module
   docstring, `verify_coverage`'s docstring, and the new `project-state.yaml` key's comment block.
6. `plugin/templates/project-state.yaml` documentation for the new key.

## Decisions resolved

### Decision — declaration surface (settles `change-evidence-design.md` Open Question #1, for
socket 1; the cross-socket question in general)

Requirements' Scope-out left this "not decided for socket 1 in isolation... no sibling design has
settled it yet." It is now settled by precedent, not by waiting further: #618, #619, and #620 each
independently declared their **own** dedicated key(s) — `reference_index_producer`,
`mutation_producer`/`mutation_required`, `api_diff_producer`/`api_diff_required` — none of them
introduced or reused a shared cross-socket key. Three-for-three is the pattern, not a coincidence
to relitigate: each socket's producer contract is shaped differently (a `{base}` placeholder for
socket 3, none for socket 4, none needed for socket 1 either), so a shared key would need to be the
union of four incompatible shapes or force an artificial common envelope onto producers that don't
need one. Socket 1 follows the same pattern: **one new key, `coverage_producer`, scoped to this
socket alone.** This design closes `change-evidence-design.md` Open Question #1 for good — a future
reader hitting that line in the artifact should treat it as answered by the accumulated precedent
of all four sockets' designs, not still open.

### Decision — the "which toolchains cannot emit LCOV/Cobertura/Clover/JaCoCo" open question is
moot (retires `change-evidence-design.md`'s last open question)

That question predates the issue's own 2026-08-07 Correction (requirements Grounding facts) and
asked it because the pre-Correction plan had prawduct **parsing** one of those four report formats
directly — so a toolchain unable to produce any of them would have had no path in. Under the
corrected, already-ratified contract, prawduct parses **no** report format; it consumes an
already-normalized verdict the product's own producer command prints (requirements Decision 1,
CE1-1, CE1-8). This design's producer envelope (below) needs nothing more than "the changed lines
that are not covered, and the changed files the producer could judge at all" — a shape any coverage
signal can be squeezed into by a five-line wrapper script, regardless of whether the underlying
tool speaks LCOV, Cobertura, a proprietary JSON, or nothing exportable at all (a wrapper can read a
tool's terminal output and regex it, same as any CI script already does). No product is excluded by
format. This design therefore treats the artifact's open question as **retired**, not merely
deferred again. The proposed edit (Files touched, below) strikes the line and replaces it with a
one-sentence pointer here: *"Retired — #249's design supplies a producer envelope no report format
is required to pass through; see `documentation/issues/249-design.md` § Decision."*

### Decision 2 (requirements) — the minimal verdict primitive, serialized

The declared `coverage_producer` command prints one JSON object to **stdout**:

```json
{"schema": 1, "tracked": ["src/a.py", "src/b.py"], "uncovered": ["src/a.py:42", "src/a.py:57"]}
```

- `tracked` — every changed file the producer's underlying coverage report could judge at all
  (instrumented, or otherwise assessable for the diff). This is the field the pre-Correction plan
  never needed and the corrected contract does: without it, "zero uncovered lines for this file"
  is ambiguous between "fully covered" and "not a source file the coverage tool tracks" (a
  `README.md` in the diff, say) — the same ambiguity the floor resolves today via
  `_is_python_file`, generalized to whatever universe the product's own tool defines instead of a
  hardcoded suffix check.
- `uncovered` — `file:line` pairs (requirements CE1-2, verbatim from the design artifact's own
  stated primitive) for every tracked, changed line the report shows as not executed. Line is a
  1-based integer following the `:`; `file` must appear in `tracked`.
- `schema` — rejects a version this reader does not understand rather than misparsing it, the same
  posture `api_diff_producer`'s envelope uses (#620 design, Decision 4) and `data-model.md`'s
  forward-incompatibility rule requires (CE1-4).

`changes_referenced` = changed files present in `tracked` with no `uncovered` entry.
`changes_unjudged` = changed files absent from `tracked` (mirrors the floor's existing "outside the
verifier's judgment" classification, generalized). `missing` (the actual gate population) is
derived by `verify_coverage` exactly as today — changed, not referenced, not unjudged — because
`changes_referenced`/`changes_unjudged` already encode the right answer; **no branch inside
`verify_coverage` needs to know executed-level verdicts exist at all.**

### Decision 4 (requirements) — schema extension, not a separate shape

One new **optional** field, `uncovered_lines: list[str]` (`file:line`, verbatim from the producer's
`uncovered`, filtered to changed files as a defensive measure — see §2), added to the merged
`.test-evidence.json` record when `coverage_level: "executed"`. It is not added to
`_EVIDENCE_REQUIRED_FIELDS` or `_EVIDENCE_COVERAGE_FIELDS` (`gates.py:56-69`) — `_validate_evidence_schema`
only rejects a **missing** required field or a **wrong-typed present** one (`gates.py:349-389`); an
extra key it was never told to expect is neither, so a record without `uncovered_lines` (every
floor-level record ever written, and this socket's own error/fallback paths) continues to validate
unchanged. This is what "additive-only field evolution" (Decision 4's own constraint) means
concretely, and it is why `lib/gates.py` needs no code change (CE1-3): the field exists for a
reader that wants it (a future `verify_coverage` enhancement citing exact lines in its BLOCKING
message — noted as an Open item below, not required by this chunk) without the existing reader
needing to know it exists. A parallel storage shape (a second file, or a new `evidence.py`
`kind`) was rejected: it would need its own freshness/staleness story `test_status`/`verify_coverage`
already solve for the one file that exists, for no benefit this field doesn't already provide.

## Section 1 — `project-state.yaml` key (CE1-1, CE1-8)

**Where:** `plugin/templates/project-state.yaml`, inside the existing "TEST EXECUTION" block,
directly after the `tests_dirs:` comment (currently ending at line 372) and before the new
`sentinel_command:` block that now follows it — same section family (coverage/test declaration
surfaces), matching the "COVERAGE EVIDENCE" heading's own placement convention one block up.

```yaml
# coverage_producer: scripts/coverage-diff-verdict.sh
#   Opaque, unwrapped shlex-split invocation, run from the repo root — same
#   "declare it, don't wrap it" contract as test_command:/api_diff_producer:/
#   mutation_producer:. Prints one JSON object to stdout:
#     {"schema": 1, "tracked": [...changed files the coverage report could
#      judge...], "uncovered": ["file:line", ...changed, tracked, not
#      executed...]}
#   prawduct validates no report format and ships no LCOV/Cobertura/Clover/
#   JaCoCo parser — the product's own coverage tool plus an existing
#   diff-coverage normalizer (or a hand-rolled wrapper) does that and prints
#   this envelope. Declaring this activates coverage_level: "executed"
#   evidence, read by the SAME coverage_required lever above — no separate
#   opt-in. Unset: prawduct-hook test-evidence record falls back to the
#   Python-only symbol-grep floor, unchanged. An "executed" verdict proves a
#   changed line ran during a test; it does not prove any assertion
#   constrained its behaviour (see change-evidence-design.md § Blind spots).
#   See `.prawduct/artifacts/change-evidence-design.md` and
#   `documentation/issues/249-design.md`.
```

**Compatibility:** additive and optional; a `project-state.yaml` predating this change reads as
"not declared" (`read_str_yaml_key` returns `None`) and the existing floor path runs exactly as it
does today — no migration, matching `api_diff_producer`/`reference_index_producer`/
`mutation_producer`'s existing posture.

## Section 2 — `bin/test-reference-verify`: `--executed-command` (CE1-2, CE1-3, CE1-4)

**New argparse option**, alongside the existing `--merge-into` definition (`test-reference-verify:321-325`):

```python
parser.add_argument(
    "--executed-command",
    default=None,
    help=(
        "Opaque, shlex-split command emitting the executed-level verdict "
        '{"schema": 1, "tracked": [...], "uncovered": ["file:line", ...]} on '
        "stdout. When given, replaces the Python-only symbol-grep floor for "
        "this run: coverage_level is written as executed (issue #249 design)."
    ),
)
```

**Dispatch** (`main()`, replacing the unconditional `fields = _build_evidence_fields(repo, base,
tests_dirs)` call at `test-reference-verify:352-356`):

```python
try:
    if args.executed_command:
        fields = _build_executed_evidence_fields(repo, base, args.executed_command)
    else:
        fields = _build_evidence_fields(repo, base, tests_dirs)
except RuntimeError as exc:
    print(f"error: {exc}", file=sys.stderr)
    return 2
```

The existing `except RuntimeError` branch is reused verbatim — a producer failure surfaces exactly
like a git failure does today (exit 2, one stderr line), no new error-handling shape.

**New function**, placed beside `_build_evidence_fields` (mirrors `api_diff_status`'s
`_run_api_diff_producer` helper, #620 design §2, at the same level of abstraction — subprocess +
JSON contract, timeout-guarded):

```python
_EXECUTED_PRODUCER_TIMEOUT_SECONDS = 60
_EXECUTED_VERIFIER_NAME = "test-reference-verify (executed: declared producer)"


def _build_executed_evidence_fields(cwd: Path, base: str, command: str) -> dict:
    """Compute F4a fields from a declared executed-level producer's verdict.

    Fixed name in ``verifier`` rather than embedding ``command`` verbatim —
    the field is meant for a human scanning evidence, not for reproducing the
    invocation (that lives in project-state.yaml, one place, not duplicated
    into every record it produces).

    Raises RuntimeError on any producer failure — timeout, non-zero exit,
    invalid JSON, wrong schema, or a malformed tracked/uncovered shape —
    which ``main()`` reports and turns into exit 2, identically to a git
    failure. There is no silent-degrade path: an executed-level producer that
    cannot be trusted must not write coverage_level: executed evidence for a
    verdict it did not actually compute.
    """
    changed = set(_changed_files(cwd, base))
    try:
        argv = shlex.split(command)
        result = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True,
            timeout=_EXECUTED_PRODUCER_TIMEOUT_SECONDS, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"coverage_producer failed to run: {exc}") from exc
    if result.returncode != 0:
        raise RuntimeError(
            f"coverage_producer exited {result.returncode}: "
            f"{result.stderr.strip() or '(no stderr)'}"
        )
    try:
        verdict = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"coverage_producer emitted invalid JSON: {exc}") from exc
    if not isinstance(verdict, dict) or verdict.get("schema") != 1:
        raise RuntimeError("coverage_producer verdict missing schema: 1")
    tracked = verdict.get("tracked")
    uncovered = verdict.get("uncovered")
    if not isinstance(tracked, list) or not isinstance(uncovered, list):
        raise RuntimeError("coverage_producer verdict missing tracked/uncovered lists")

    tracked_set = {str(t) for t in tracked}
    uncovered_files = set()
    uncovered_lines: list[str] = []
    for entry in uncovered:
        text = str(entry)
        file_part, _, _line_part = text.rpartition(":")
        if not file_part:
            continue  # malformed entry, defensively dropped rather than raised on
        uncovered_files.add(file_part)
        if file_part in changed:
            uncovered_lines.append(text)

    referenced = sorted(f for f in changed if f in tracked_set and f not in uncovered_files)
    unjudged = sorted(f for f in changed if f not in tracked_set)

    return {
        "verifier": _EXECUTED_VERIFIER_NAME,
        "coverage_level": "executed",
        "tests_executed": [],
        "changes_referenced": referenced,
        "changes_unjudged": unjudged,
        "uncovered_lines": sorted(uncovered_lines),
    }
```

`tests_executed: []` — the field means "test files discovered under the tests directory," a
floor-specific concept (which test file textually mentions a symbol) with no executed-level
analogue; an empty list is honest rather than a fabricated re-derivation. Nothing downstream reads
it as a count of anything (`verify_coverage` never inspects `tests_executed`; it exists in the F4a
schema for the pytest-half record `cmd_test_evidence` writes before the overlay, per
`_EVIDENCE_REQUIRED_FIELDS`).

**Module-level imports:** `shlex` is new (`subprocess`/`json` already imported at
`test-reference-verify:52-55`).

## Section 3 — `bin/prawduct-hook`: read the new key, pass the flag (CE1-1)

**Where:** `cmd_test_evidence`'s existing overlay block (`prawduct-hook:3898-3922`) — the single
call site that already invokes `test-reference-verify --merge-into`. Add one read and one
conditional argument, touching no other line in the block:

```python
verifier = Path(_plugin_root()) / "bin" / "test-reference-verify"
if verifier.is_file():
    coverage_producer = read_str_yaml_key(
        prawduct_dir / "project-state.yaml", "coverage_producer"
    )
    merge_cmd = [
        sys.executable,
        str(verifier),
        "--merge-into",
        str(evidence_path),
        "--repo",
        str(project_dir),
    ]
    for tests_dir in tests_dirs:
        merge_cmd += ["--tests-dir", tests_dir]
    if base:
        merge_cmd += ["--base", base]
    if coverage_producer:
        merge_cmd += ["--executed-command", coverage_producer]
    mp = subprocess.run(merge_cmd, check=False, capture_output=True, text=True)
    ...  # unchanged below
```

`--tests-dir` is still passed even when `--executed-command` is given — harmless (the executed path
never reads `tests_dirs`), and keeps the two call shapes from diverging for no reason. `prawduct_dir`
is already in scope at this point in `cmd_test_evidence` — it is assigned near the top of the
function (`prawduct-hook:3384`) and used again just above this block, at the atomic-write step
(`prawduct_dir.mkdir(...)`, `:3879`) — so reading `coverage_producer` needs no new variable, only
the one extra `read_str_yaml_key` call shown above.

No new `prawduct-hook` subcommand, no dispatch-table change, no `_USAGE` edit: this rides the
existing `test-evidence record` entry point exactly as the floor already does, which is what keeps
`verify_coverage` (the actual gate) and the Critic's Symbol-coverage bullet (`goals-1-3.md:71`)
untouched — they read `.test-evidence.json`, not the producer.

## Section 4 — Case-B caveat at the sites that state the guarantee (CE1-9)

Three edits, each one sentence, at the concrete places socket 1's guarantee is stated in running
code/docs (the design artifact's own "Blind spots" section already carries the canonical statement
this mirrors, `change-evidence-design.md:173-179`):

1. **`test-reference-verify`'s module docstring** (`:2-24`) — the existing floor-level sentence
   ("A referenced symbol does NOT prove a test exercises the code — only that some test mentions
   it") gets an executed-level sibling directly after the `--executed-command` description added in
   §2's usage text: *"An executed verdict proves a changed line ran during some test; it does not
   prove any assertion constrained that line's behaviour (Case B — see
   `change-evidence-design.md` § Blind spots)."*
2. **`verify_coverage`'s docstring** (`gates.py:1754-1788`) — already discusses the
   `referenced`/`executed` distinction generally (the "day one does" paragraph); append: *"Neither
   level proves an assertion constrained the covered line's behaviour — `executed` proves execution,
   not verification."*
3. **The new `project-state.yaml` key's comment block** (§1 above) already carries the caveat inline
   — it is the first place a product author reads before declaring the key, which is where CE1-9's
   "wherever the guarantee is described" is most load-bearing (an author who never reads a docstring
   still reads the key they are about to set).

No edit to `plugin/skills/critic/goals-1-3.md:71` — its Symbol-coverage bullet already instructs
"wording is `coverage_level`-scaled and must not be softened," which routes the Critic to whatever
`verify_coverage` actually prints; adding the caveat there too would be a fourth restatement of the
same sentence with nothing new to say.

## Files touched

| File | Change |
|---|---|
| `plugin/templates/project-state.yaml` | New `coverage_producer:` comment block in the existing TEST EXECUTION section (CE1-1, CE1-8) |
| `plugin/bin/test-reference-verify` | New `--executed-command` flag; new `_build_executed_evidence_fields()`, `_EXECUTED_PRODUCER_TIMEOUT_SECONDS`, `_EXECUTED_VERIFIER_NAME`; `main()` branches on the flag; module docstring gains the Case-B sentence; `import shlex` |
| `plugin/bin/prawduct-hook` | `cmd_test_evidence`'s overlay block reads `coverage_producer` and conditionally passes `--executed-command` |
| `plugin/lib/gates.py` | **No change** (CE1-3 — `verify_coverage` already reads `changes_referenced`/`changes_unjudged`/`coverage_level` correctly; docstring gains the Case-B sentence, Section 4 item 2) |
| `.prawduct/artifacts/change-evidence-design.md` | Open Questions: strike "which real toolchains cannot emit any of the four formats" as retired (Decision above); mark Open Question #1 answered by the four sockets' accumulated precedent |
| `tests/test_reference_verify_executed.py` (new) | See test plan below |

## Test plan (`tests/test_reference_verify_executed.py`)

Following `tests/test_verify_coverage_gate.py`'s and #620's `tests/test_api_diff_gate.py`'s
established style — real git repos, real subprocess invocation of `bin/test-reference-verify`, no
mocking of git or the filesystem. Producer commands are small fixture scripts printing fixed JSON
to stdout.

1. **No `--executed-command`** — unchanged floor behavior, symbol-grep runs exactly as today
   (regression guard: this flag must not perturb the existing default path).
2. **Executed, clean** — producer prints `{"schema": 1, "tracked": ["a.py"], "uncovered": []}` for
   a diff that only changes `a.py` → `coverage_level: "executed"`, `changes_referenced: ["a.py"]`,
   `uncovered_lines: []`.
3. **Executed, some lines uncovered** — producer prints one `uncovered` entry for the changed file
   → that file is absent from `changes_referenced`, present in `uncovered_lines`; `verify_coverage`
   run against the resulting record reports `missing-coverage` for it with `coverage_level:
   executed` severity wording ("has no executing test"), unmodified from today's behavior —
   confirms CE1-3's "no gate change" claim end-to-end, not just by code inspection.
4. **Untracked changed file** — a changed file absent from `tracked` → lands in
   `changes_unjudged`, not `changes_referenced` and not counted as `missing` — the ambiguity
   Decision 2's `tracked` field exists to resolve.
5. **Producer exits non-zero** — `--merge-into` run returns exit 2, one `error:` stderr line naming
   the producer's own stderr; the pre-existing evidence file (if any) is left untouched (`_merge_into`
   is never reached because the exception fires before it, per §2's dispatch).
6. **Producer emits invalid JSON / wrong schema / missing `tracked` or `uncovered`** — each is its
   own case, all raising the same `RuntimeError` shape, all exit 2.
7. **Producer times out** — a fixture script sleeping past
   `_EXECUTED_PRODUCER_TIMEOUT_SECONDS` (test overrides the constant to keep the suite fast) →
   exit 2, same as case 5.
8. **`uncovered` entry naming a file outside `changed`** — defensively dropped from
   `uncovered_lines` (only changed files are recorded there) but still contributes to
   `uncovered_files` for the referenced/unjudged split — a producer over-reporting relative to the
   requested diff must not corrupt the record it writes, but also must not silently mark a stale
   entry as covered.
9. **`prawduct-hook test-evidence record` end-to-end** — `coverage_producer:` declared in
   `project-state.yaml`, a real repo, real commit → the written `.test-evidence.json` carries
   `coverage_level: "executed"` and `uncovered_lines`; `coverage_producer` absent → unchanged
   `coverage_level: "referenced"` record, confirming Decision 6's fallback (demoted, not retired).

## Open items for the build chunk (not resolved here)

- Whether `verify_coverage`'s BLOCKING message should be enriched to cite exact `uncovered_lines`
  per file when present, rather than only naming the file (as today). `uncovered_lines` is written
  specifically to make this possible later without a schema change — but CE1-3 promises zero gate
  logic change for this item, so it is explicitly deferred, not silently assumed.
  Recommendation: a follow-up item, not this chunk.
- Exact wording of the fixture producer scripts in the test plan (cosmetic).
- Whether `_EXECUTED_PRODUCER_TIMEOUT_SECONDS` should be product-configurable — no knob proposed,
  mirroring #620's identical call on `_API_DIFF_PRODUCER_TIMEOUT_SECONDS` (design §"Open items");
  revisit only if real-world use proves 60s too tight for a large diff's coverage tool.

## Acceptance (carried from requirements, now with an implementation path)

- [ ] A non-Python product with `coverage_producer:` declared gets a `coverage_level: "executed"`
      diff-coverage verdict without hand-rolling a verifier — pinned by test-plan cases 2–3, 9.
- [ ] Prawduct ships no coverage-report parser — `_build_executed_evidence_fields` parses only the
      two-field `{schema, tracked, uncovered}` envelope, never a tool-native report format
      (confirmed moot for LCOV/Cobertura/Clover/JaCoCo specifically by the Decision above).
- [ ] A missing producer reports *unchecked*, never *passed* — unchanged: no `coverage_producer`
      means the existing floor runs exactly as today, whose `changes_unjudged` behavior is
      untouched (case 1); a *declared* producer that fails is a loud `error:`, exit 2, never a
      silent pass (cases 5–7).
- [ ] The socket defaults to report-only; a blocking threshold is a product opt-in via the existing
      `coverage_required` key, with no new key introduced for blocking (`verify_coverage` itself is
      unmodified — CE1-3).
- [ ] The Case-B limit (covered ≠ verified) is stated wherever the guarantee is stated — three doc
      sites, Section 4.

## Evidence / references

- `documentation/issues/249-requirements.md` — CE1-1–10, Decisions 1–8, grounding facts.
- `.prawduct/artifacts/change-evidence-design.md:104-125,171-179,303-318` — socket 1's design-doc
  entry, the Blind spots / Case-B statement this design's Section 4 mirrors, and the two Open
  Questions this design settles/retires.
- `plugin/bin/test-reference-verify:210-277,291-376` — `_build_evidence_fields` (the floor,
  unmodified), `main()`'s dispatch (the exact insertion point for the new branch), `_merge_into`
  (reused as-is — the new function returns the same shape it already merges).
- `plugin/lib/gates.py:56-69,349-389,1754-1881` — `_EVIDENCE_REQUIRED_FIELDS`/
  `_EVIDENCE_COVERAGE_FIELDS`, `_validate_evidence_schema` (confirms `uncovered_lines` needs no
  entry), `verify_coverage` (confirms it needs no code change).
- `plugin/bin/prawduct-hook:3898-3922` — the exact overlay call site Section 3 extends.
- `documentation/issues/620-design.md` §"Decision 4", §"Section 2" — the sibling precedent for a
  producer-envelope `schema` field, a subprocess-with-timeout helper shape, and the exact
  declaration-surface pattern (own key per socket) this design's opening Decision generalizes from.
- `documentation/issues/618-design.md:20-21,86-88` — the sibling precedent for a producer key with
  no paired `*_required` key (this item's own shape, since `coverage_required` predates the
  four-socket design and is reused rather than duplicated).
- `documentation/issues/619-design.md:17-18,174-179` — the sibling precedent for a mandatory
  placeholder in a producer command (`{base}`); socket 1's producer needs none, noted for
  completeness since design must show it considered the question, not merely omit it.
