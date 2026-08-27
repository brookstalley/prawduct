# Issue #618 — Coverage: Consume a Reference Index for Blast Radius: Design

`status: draft · stage: design · area: coverage · added: 2026-08-19 · source: scheduled backlog
session · issue: https://github.com/brookstalley/prawduct/issues/618`

Builds on `documentation/issues/618-requirements.md` (CE2-1 through CE2-8, Decisions 1–6). This
document resolves the requirements doc's two design-stage decisions — the Critic-integration seam
(Decision 5) and the storage question (Decision 6) — and specifies file-by-file changes an
implementation chunk can follow directly.

Socket 2 of the four-socket change-evidence contract; siblings #249 (socket 1), #619 (socket 3),
#620 (socket 4, already at requirements/design) have their own requirements/design passes. The
shared contract itself (`.prawduct/artifacts/change-evidence-design.md`) is not restated here.

## Summary of what ships

1. **CE2-2, CE2-3, CE2-4, CE2-5** — `plugin/bin/test-reference-verify` gains a new `--blast-radius`
   mode: same symbol-extraction mechanism, whole-repo search scope instead of the tests tree,
   per-symbol dependent-set output instead of the F4a referenced/unjudged split.
2. **CE2-2** — one new `project-state.yaml` key: `reference_index_producer` (opaque invocation,
   optional — no `*_required` key exists for this socket, per CE2-1).
3. **CE2-4, CE2-5, CE2-8** — a new `lib/gates.py` function, `blast_radius_status()`. No persisted
   verdict (Decision 6 resolved below) — the declared producer, or the floor, is invoked live on
   every call.
4. A new `prawduct-hook blast-radius` command: thin wrapper, dispatch case, `_USAGE` entry,
   `_EPHEMERAL_SAFE_COMMANDS` membership.
5. **CE2-6** — `goals-1-3.md` gains one bullet under "1. Nothing Is Broken," alongside the existing
   Symbol coverage bullet, and `critic/SKILL.md`'s `allowed-tools` frontmatter gains the new
   command.
6. `plugin/templates/project-state.yaml` documentation for the new key.

## Decisions resolved

### Decision 5 — the Critic-integration seam

**A live `prawduct-hook blast-radius` subcommand, invoked from `goals-1-3.md`'s Goal 1 — not a
`manifest.json` field computed at `critic-begin` time.** Three reasons, all from the requirements
doc's own grounding facts:

- **`critic-begin` is a code-authoritative dispatch path, not a place to add per-review work that
  most reviews won't use.** `cmd_critic_begin` (`bin/prawduct-hook:1134-1273`) derives and writes the
  manifest for *every* dispatch — chunk, final, cumulative, verify-resolutions — including the
  `doc-only`/`cleanup` chunk `Type`s that `goals-1-3.md:22-26` already exempts from full Goal 1.
  Computing a blast-radius verdict inside that path taxes every dispatch with a cost only some
  reviews need, where a live command taxes only the reviews that actually run it — exactly the
  "declare it, don't wrap it" / pay-when-asked shape socket 4's live-invocation precedent
  established for the same near-zero-cost reasoning.
- **The live-command shape already exists for exactly this kind of check.** `goals-1-3.md:19`, "Run
  `prawduct-hook test-status` and `prawduct-hook verify-coverage` (Goal 1). Nothing else executes,"
  and the Symbol coverage bullet (`goals-1-3.md:61` in the pre-existing numbering) instructing the
  reviewer to run `verify-coverage` and quote its stderr verbatim — a `blast-radius` command slots
  into the same "run it, read its stdout" pattern with no new machinery.
- **`goals-1-3.md` must carry whichever seam is chosen, on its own terms** (requirements CE2-6,
  Decision 5) — a live command is one line to add there; a manifest field would require also
  documenting the manifest's new field shape in the one file `goals-1-3.md` is allowed to read
  (`goals-1-3.md:3-4` forbids opening `review-cycle.md`/`review-protocol.md`), which is more surface
  for the same outcome.

### Decision 6 — no persisted verdict artifact

Requirements' Decision 6 deliberately left open whether a verdict lands in the shared evidence store
or a dedicated file, deferred "identically to socket 4's Decision 5." Resolved the same way, for the
same reason: socket 2 shares socket 4's defining property — "zero test-runtime cost... it reads a
static index" (`change-evidence-design.md:140-141`) — so there is no expensive half to decouple a
write from a read for. `blast-radius` invokes the declared producer or the floor live, every time
it's asked, and writes nothing to disk. This sidesteps `evidence.py`'s still-unratified `KNOWN_KINDS`
extension question (CE2-7) the same way issue #620's design did, for the identical reason: there is
no storage to add a `kind` to.

**Consequence for CE2-5 ("unchecked, never coalesced with empty")**: since nothing is stored,
"unchecked" is a live classification `blast-radius` computes and prints on every invocation, exactly
mirroring `api-diff-status`'s "unchecked" handling (issue #620 design, §2) — not a state some earlier
write left behind.

## Section 1 — `project-state.yaml` key (CE2-2)

**Where:** `plugin/templates/project-state.yaml`, a new heading placed directly after the existing
"COVERAGE EVIDENCE" block (currently ending at line 338, `coverage_required: false`) — adjacent to
the socket this one is most often declared alongside, matching the existing "CHANGE EVIDENCE —
PUBLISHED SURFACE" block's (issue #620 design, §1) comment style and placement convention.

```yaml
# =============================================================================
# CHANGE EVIDENCE — BLAST RADIUS (report-only, socket 2 of the change-evidence contract)
# =============================================================================
# Unlike the other three sockets, this one has no *_required key — it is
# always report-only (a large dependent set is orientation, never a defect
# claim). Declare the command that prints socket 2's normalized dependent-set
# verdict to stdout — a wrapper around a SCIP index query (indexers exist for
# most languages) emitting {"schema": 1, "symbols": [...]}. Leave unset to
# fall back to bin/test-reference-verify's --blast-radius mode: the existing
# Python-only symbol-grep floor, pointed at the whole repo instead of the
# tests tree — a stopgap, not a portable answer. See
# `.prawduct/artifacts/change-evidence-design.md` and
# `documentation/issues/618-design.md`.

# reference_index_producer: scripts/blast-radius-verdict.sh
#   Opaque, unwrapped shlex-split invocation, run from the repo root — same
#   "declare it, don't wrap it" contract as test_command:/api_diff_producer:.
#   Shell operators (&&, |, FOO=1) are not supported — point the command at a
#   script for compound invocations.
```

**Compatibility:** the key is optional and additive; a `project-state.yaml` predating this change
reads as "not declared" (`read_str_yaml_key` returns `None`) and the command falls back to the floor
— no migration, matching `api_diff_producer`'s existing posture (issue #620 design, §1).

## Section 2 — `bin/test-reference-verify`: `--blast-radius` mode (CE2-2, CE2-3, CE2-5)

**Where:** `plugin/bin/test-reference-verify`, a new `--blast-radius` flag on the existing
`argparse` parser (near `--tests-dir`, `main:296-326`), branching `_build_evidence_fields`'s call
site rather than adding a parallel script — this keeps the symbol-extraction mechanism
(`_PY_SYMBOL_RE`, `_extract_symbols`) in the one file `architecture.md`'s Retroactivity list already
names as its home, instead of opening a second one (the requirements doc's Decision 2: reuse, don't
duplicate; the design doc's own open question about *not* creating "two homes for one fact,"
`change-evidence-design.md:308-310`).

```python
def _build_blast_radius_fields(cwd: Path, base: str) -> dict:
    """Blast-radius mode (issue #618): same symbol extraction as the F4a
    floor, but searches the WHOLE repo for callers instead of a tests tree,
    and reports a dependent set per symbol instead of a referenced/unjudged
    split.

    Python-only, exactly as honestly limited as the F4a floor it reuses —
    this is the floor issue #618's design explicitly calls a stopgap, not a
    fix (documentation/issues/618-design.md, Decision on the floor).
    """
    changed = _changed_files(cwd, base)
    # Search root is the whole repo, not a tests_dirs argument — "all
    # callers instead of the tests tree" (change-evidence-design.md:132-133).
    repo_files = [
        p for p in cwd.rglob("*.py")
        if ".git" not in p.parts
    ]
    repo_texts = _read_test_texts(repo_files)  # name kept; reads ANY .py file here

    symbols_out: list[dict] = []
    unjudged: list[str] = []
    diff_set = set(changed)
    for f in changed:
        fp = cwd / f
        if not fp.is_file() or not _is_python_file(fp):
            unjudged.append(f)
            continue
        symbols = _extract_symbols(fp)
        if not symbols:
            unjudged.append(f)
            continue
        for sym in sorted(symbols):
            dependents = sorted(
                str(p.relative_to(cwd)) for p, text in zip(repo_files, repo_texts)
                if p.relative_to(cwd) != Path(f) and sym in text
            )
            symbols_out.append({
                "symbol": sym,
                "file": f,
                "dependents": dependents,
                "diff_touched_dependents": sorted(d for d in dependents if d in diff_set),
            })

    return {"schema": 1, "symbols": symbols_out, "unjudged": sorted(unjudged)}
```

**CLI wiring** — `main()` gains `--blast-radius` (store_true, mutually exclusive with `--output`/
`--merge-into`'s F4a-specific framing since blast-radius always prints to stdout, matching the
producer contract Section 3 below expects):

```
parser.add_argument(
    "--blast-radius",
    action="store_true",
    help="Emit socket-2 dependent-set JSON instead of F4a evidence fields (issue #618).",
)
```

When `--blast-radius` is set, `main()` calls `_build_blast_radius_fields` instead of
`_build_evidence_fields` and always prints the JSON to stdout (the `--output`/`--merge-into` paths
are F4a-specific and stay unreached in this mode — `--blast-radius` combined with either is a usage
error, checked the same way `--output`/`--merge-into` already reject each other,
`test-reference-verify:328-330`).

## Section 3 — `lib/gates.py`: `blast_radius_status()` (CE2-4, CE2-5, CE2-8)

**Where:** `plugin/lib/gates.py`, placed near `verify_coverage` and (once built) `api_diff_status` —
all three read a project-state-declared producer and compose into the same PR/Critic surface.

```python
def blast_radius_status(project_dir: Path) -> int:
    """Socket 2 (CE2, issue #618) — dependent-set verdict for the product's
    declared reference-index producer, or the repo-wide symbol-grep floor.

    No persisted artifact: invoked live on every call, mirroring socket 4's
    api_diff_status (issue #620 design, Decision 5) — the same "zero
    test-runtime cost, nothing to decouple write from read for" reasoning.

    Always exits 0 — this socket has no blocking variant (CE2-1, CE2-5).
    stdout carries one status line plus, when non-empty, one line per
    changed symbol with a non-empty dependent set — orientation for a
    reviewer, never a pass/fail claim (change-evidence-design.md:136-137).
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    state_path = prawduct_dir / "project-state.yaml"

    producer = read_str_yaml_key(state_path, "reference_index_producer")
    if producer is not None:
        verdict, error = _run_blast_radius_producer(producer, project_dir)
        source = producer
    else:
        base, base_reason = coverage._coverage_resolve_base(project_dir)
        if base is None:
            print(f"unchecked: cannot resolve diff base — {base_reason}")
            return 0
        floor_cmd = [
            sys.executable,
            str(Path(_plugin_root()) / "bin" / "test-reference-verify"),
            "--blast-radius", "--repo", str(project_dir), "--base", base,
        ]
        verdict, error = _run_blast_radius_subprocess(floor_cmd, project_dir)
        source = "floor: test-reference-verify --blast-radius (Python-only)"

    if error is not None:
        print(f"unchecked: {source} — {error}")
        return 0

    symbols = verdict["symbols"]
    unjudged = verdict.get("unjudged", [])
    if unjudged:
        print(f"unchecked: {len(unjudged)} changed file(s) outside {source}'s judgment: "
              f"{', '.join(unjudged[:5])}" + (" …" if len(unjudged) > 5 else ""))
    with_dependents = [s for s in symbols if s["dependents"]]
    if not with_dependents:
        print(f"clean: no dependents found for {len(symbols)} changed symbol(s) ({source})")
        return 0

    for s in with_dependents:
        touched = len(s["diff_touched_dependents"])
        total = len(s["dependents"])
        print(f"  - {s['symbol']} ({s['file']}): {total} dependent(s), "
              f"{touched} also touched by this diff", file=sys.stderr)
    print(f"blast-radius: {len(with_dependents)} symbol(s) with dependents ({source})")
    return 0
```

`_run_blast_radius_producer(producer, project_dir)` and `_run_blast_radius_subprocess(argv,
project_dir)` share one inner implementation — `shlex.split` for the declared-producer form only,
`subprocess.run(argv, cwd=project_dir, capture_output=True, text=True, timeout=60)`, `json.loads` the
stdout, and reject a `schema` other than `1` or a missing/non-list `symbols` key — the same shape and
the same named-constant timeout (`_BLAST_RADIUS_PRODUCER_TIMEOUT_SECONDS = 60`) as socket 4's
`_run_api_diff_producer` (issue #620 design, §2), duplicated in spirit but not in code — the two
producers' verdict envelopes differ (`breaking` vs. `symbols`), so the parsing bodies are not
byte-identical, but the subprocess/timeout/error-classification skeleton is.

## Section 4 — `bin/prawduct-hook` wiring

**Thin wrapper**, mirroring `cmd_verify_coverage`/`cmd_api_diff_status`:

```python
def cmd_blast_radius(project_dir: Path) -> int:
    """Socket 2 blast-radius report. Thin wrapper — body lives in
    ``lib.gates.blast_radius_status`` (issue #618)."""
    return _gates().blast_radius_status(project_dir)
```

**Dispatch** (`main()`, alongside `elif command == "verify-coverage":`):

```python
elif command == "blast-radius":
    return cmd_blast_radius(project_dir)
```

**`_USAGE`**: extend the existing segment —

```
"verify-coverage|blast-radius|"
```

**`_EPHEMERAL_SAFE_COMMANDS`**: add `"blast-radius"` (alphabetical placement, after `"bug-inbox"`) —
read-only by construction, matching `"verify-coverage"`'s existing membership: it never writes to
`.prawduct/` or the tree, only invokes the declared producer or the floor and prints its verdict.

## Section 5 — `goals-1-3.md` and `critic/SKILL.md`

**Where:** `plugin/skills/critic/goals-1-3.md`, "## 1. Nothing Is Broken," a new bullet directly
after the existing Symbol coverage bullet — same section, since blast radius is read alongside
`verify-coverage` in the same "run these two, nothing else executes" step (`goals-1-3.md:19`):

> - **Blast radius:** run `prawduct-hook blast-radius`. It always exits 0 — this is orientation, not
>   a pass/fail signal. For each symbol it lists with dependents, use the dependent count and
>   `diff_touched_dependents` split as evidence when judging *other* bullets in this protocol (e.g.
>   whether a changed/added behavior's test coverage extends to callers the diff does not itself
>   touch) — it does not, on its own, produce a finding. A `unchecked: ...` line names files or
>   symbols outside its judgment; state that briefly, no severity — never read as "no dependents."

This deliberately does not mint a new BLOCKING/WARNING trigger keyed off dependent count alone,
consistent with the design doc's own posture ("report-only, always... a large dependent set is
information, not a defect," `change-evidence-design.md:136-137`) and its blind-spot note that a
reference index "cannot rank which dependents care about the property you changed"
(`change-evidence-design.md:186-187`) — a reviewer, not the tool, decides whether an unaccounted-for
dependent is actually a problem, the same judgment call Goal 5's existing (narrower, coordinator-only)
downstream-consumer-impact bullet already asks a human to make.

**`critic/SKILL.md` `allowed-tools`**: add `Bash(prawduct-hook blast-radius)` and
`Bash(python3 plugin/bin/prawduct-hook blast-radius)` to the frontmatter allow-list, alongside the
existing `Bash(prawduct-hook test-status)` / `Bash(python3 plugin/bin/prawduct-hook test-status)`
pair — matching that entry's shape (`blast-radius` takes no arguments, so no trailing `*`, mirroring
`test-status`'s own bare-command entries rather than `critic-begin *`'s parameterized ones).

## Files touched

| File | Change |
|---|---|
| `plugin/templates/project-state.yaml` | New "CHANGE EVIDENCE — BLAST RADIUS" block: `reference_index_producer` (CE2-2) |
| `plugin/bin/test-reference-verify` | New `--blast-radius` flag, `_build_blast_radius_fields()` (CE2-2, CE2-3, CE2-4, CE2-5) |
| `plugin/lib/gates.py` | New `blast_radius_status()`, `_run_blast_radius_producer()`, `_run_blast_radius_subprocess()`, `_BLAST_RADIUS_PRODUCER_TIMEOUT_SECONDS` (CE2-4, CE2-5, CE2-8) |
| `plugin/bin/prawduct-hook` | New `cmd_blast_radius`; dispatch case; `_USAGE` entry; `_EPHEMERAL_SAFE_COMMANDS` membership |
| `plugin/skills/critic/goals-1-3.md` | One new bullet under "1. Nothing Is Broken" (CE2-6) |
| `plugin/skills/critic/SKILL.md` | `allowed-tools` gains the `blast-radius` Bash pair |
| `tests/test_blast_radius_gate.py` (new) | See test plan below |
| `tests/test_reference_verifier.py` | Extended with `--blast-radius` mode cases |

## Test plan

Following `tests/test_verify_coverage_gate.py`'s and issue #620's own test-plan style — real git
repos, real hook subprocess, fixture producer scripts printing fixed JSON — no mocking of git or the
filesystem.

`tests/test_reference_verifier.py` additions:

1. `--blast-radius` on a repo with one changed symbol called from two other files → both listed as
   dependents, `diff_touched_dependents` empty when neither is in the diff.
2. A dependent that is *also* in the diff → appears in `diff_touched_dependents`.
3. A changed file with no `def`/`class` symbols → listed in `unjudged`, not silently dropped.
4. A non-Python changed file → listed in `unjudged`.

`tests/test_blast_radius_gate.py`:

1. **No producer, floor finds dependents** — `blast-radius` with no `reference_index_producer`
   declared, a fixture repo with a real cross-file call → stdout `blast-radius: 1 symbol(s)...`,
   dependent lines on stderr, exit **0**.
2. **No producer, floor finds none** — stdout `clean: no dependents found for N changed symbol(s)
   (floor: ...)`, exit 0.
3. **Declared producer, clean** — fixture script prints `{"schema": 1, "symbols": []}` → stdout
   `clean: ...`, exit 0.
4. **Declared producer, dependents found** — fixture script prints a `symbols` list with a non-empty
   `dependents` → stdout `blast-radius: N symbol(s)...`, exit 0 (never 1 — no blocking variant,
   CE2-1).
5. **Producer errors** — fixture script exits non-zero → stdout `unchecked: ... — <error>`, exit
   **0** (never blocks — contrast socket 4's blocking-when-opted-in path, which does not exist here).
6. **Schema mismatch** — fixture prints `{"schema": 2, "symbols": []}` → treated as `unchecked`,
   loud in the sense of naming the mismatch, never silently parsed as schema 1.
7. **Diff base unresolvable (no producer)** — floor path with no `origin/main`/`main`/`HEAD~1` → `
   unchecked: cannot resolve diff base — ...`, exit 0.

## Open items for the build chunk (not resolved here)

- Whether `_build_blast_radius_fields`'s whole-repo `rglob("*.py")` scan should exclude
  `.prawduct/`, `node_modules/`, or other non-source trees beyond `.git` — the floor's honest
  Python-only scope means it already skips non-`.py` trees; a build chunk should confirm no
  degenerate-large-repo timeout risk exists before shipping, and add an exclusion list if it does.
- Exact wording of the fixture producer scripts (cosmetic).

## Acceptance (carried from requirements, now with an implementation path)

- [ ] For each changed symbol the dependent set is reported, marking which of them the diff also
      touches — pinned by `tests/test_reference_verifier.py` cases 1-2 and
      `tests/test_blast_radius_gate.py` cases 1, 4.
- [ ] Report-only, always — `blast_radius_status` never returns non-zero — pinned by all
      `test_blast_radius_gate.py` cases.
- [ ] Zero test-runtime cost: no producer runs during the product's test suite; `blast-radius` is
      invoked only from the Critic's Goal 1 step, never from `test-evidence record`.
- [ ] A missing or inapplicable producer reports *unchecked* distinctly from a clean (empty)
      verdict — pinned by cases 3, 5, 6, 7 and `test_reference_verifier.py` cases 3-4.
- [ ] No per-language symbol table or SCIP/LSIF consumer ships in prawduct — `gates.py` parses only
      the two-field `{schema, symbols}` envelope; the floor reuses `test-reference-verify`'s
      existing Python-only extraction rather than adding a second mechanism.

## Evidence / references

- `documentation/issues/618-requirements.md` — CE2-1–8, Decisions 1–6, grounding facts.
- `.prawduct/artifacts/change-evidence-design.md:127-142,308-310` — socket 2's design-doc entry and
  the "two homes for one fact" retirement question this design avoids widening.
- `plugin/bin/test-reference-verify:60-66,100-123,148-207,239-246,296-330` — the existing
  symbol-extraction and changed-file-derivation mechanism reused by `--blast-radius`, and the
  `--output`/`--merge-into` mutual-exclusion precedent the new flag follows.
- `plugin/lib/gates.py` (`verify_coverage`, `_coverage_resolve_base`) — the report-only-by-default
  precedent and the diff-base resolver `blast_radius_status` reuses for its floor path.
- `documentation/issues/620-design.md` §2-4 — `api_diff_status`'s live-invocation, no-persistence,
  subprocess/timeout/error-classification pattern this design mirrors for socket 2.
- `plugin/bin/prawduct-hook:1134-1273` (`cmd_critic_begin`), `:3085-3115` (the existing
  `test-reference-verify` subprocess invocation from `test-evidence record`) — grounding Decision 5's
  rejection of a manifest-computed seam.
- `plugin/skills/critic/goals-1-3.md:3-4,19` — the self-contained protocol's "read nothing else"
  constraint and the existing "run these two hook commands" step the new bullet extends.
- `plugin/skills/critic/SKILL.md` frontmatter `allowed-tools` — the exact list Section 5 extends.
- `plugin/bin/prawduct-hook:5633-5671,5975-5985` — `_EPHEMERAL_SAFE_COMMANDS` and the dispatch
  `elif` chain, the exact wiring pattern §4 follows.
- `tests/test_verify_coverage_gate.py`, `tests/test_reference_verifier.py` — the real-subprocess test
  style the Test plan follows.
