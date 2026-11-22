# Issue #1088 — test-evidence: mark a flake touched when its covered code changed: Design

`status: draft · stage: design · area: test-evidence · added: 2026-11-09 · source: builder · issue: https://github.com/brookstalley/prawduct/issues/1088`

Related: #1087 (`flaky_policy`, shipped), #1096 (run ledger; its `env`/`outcomes` fields are the natural home for the per-test map if it lands first), #619 (diff-scoped mutation as an evidence socket), #618 (reference index for blast radius).

## 1. Problem recap

`_judge_flakes` (`plugin/bin/prawduct-hook`) sets `touched = (flake's test file ∈ branch's changed files)`. A flake in an *unchanged* test file that exercises *changed* code reads `touched: false`, outcome `noted`, under every policy. That is the race-hiding case `flaky_policy` exists to catch.

The only coverage signal today is `bin/test-reference-verify`'s symbol grep, which maps changed files to the whole test set, never to single tests. Nothing in `plugin/` carries per-test covered lines, so the issue's premise ("when `coverage_level: executed` evidence carries per-test covered lines") names a format that does not exist yet. **This design must define that format** (smallest possible) and the intersection rule. It must not produce the coverage (scope-out).

## 2. Consumer queries (first, because a persisted format is a lock-in)

- **Q1.** For flake `F` at record time: does any line `F` executed fall on a line the branch added or modified? → `touched` (bool), plus *which file:lines* for the status line.
- **Q2.** Was coverage consulted at all for this flake, and if not, why not? → record says so (acceptance 3).
- **Q3.** For humans/Critic reading `flaky:` lines: why is this "touched by this branch" (own file / covered change / unknown)? One printed reason, not a bare bool.

Nothing else reads the map. It is never a verdict input: like `flaky`, it is printed and carried, not schema-validated, so a malformed map degrades to Q2 "not consulted", never to a stale record.

## 3. Design

### 3.1 Per-test coverage map (the lock-in)

A **sidecar**, `.prawduct/.test-coverage.json`, gitignored like `.test-evidence.json`, written by the product's own coverage tooling (or a thin adapter), not by prawduct:

```json
{
  "v": 1,
  "tree": "<evidence_tree the run was on>",
  "tests": {
    "tests/test_net.py::test_retry": {"src/net.py": "10-24,40", "src/util.py": "3"}
  }
}
```

- Keys are test ids **in the same form as junit ids** (`classname::name`, `_junit_case_id`), so the join to `flaky[].id` is exact string equality. Anything needing translation is the adapter's job. A flake id absent from `tests` is "no per-test evidence for this test" (Q2), never "covers nothing".
- Values are repo-relative path → comma-separated 1-based inclusive line ranges, in **post-change (working tree) numbering**.
- Why a sidecar, not fields in the record: per-test line sets are large; the record is capped and committed to the shared store as a `test-run` fact. The sidecar is local, replaced per run, and bound to `tree` so a stale map is detectable (§3.4).
- If #1096 lands first, the same `tests` map becomes `outcomes[...].covered` on the ledger fact and the sidecar is dropped. Keep §3.2's pure function so only the loader changes.

### 3.2 Branch changed lines

New pure function in `lib/coverage.py`: `changed_line_ranges(project_dir, base) -> dict[path, list[(lo, hi)]]`, from `git diff -U0 <base>` hunk headers (`@@ -a,b +c,d @@`), new-file numbering.

- Added/modified hunk (`d > 0`): range `c .. c+d-1`.
- Pure deletion (`d == 0`): no new-file line exists. Anchor it to the two surrounding lines `c` and `c+1` — a test that executes the code beside a removed branch is exercising the changed region. This errs toward `touched`, matching the existing "unknown ⇒ touched" posture.
- Renames: follow `--find-renames`; a renamed-only file contributes no ranges. Binary files: skipped.
- Uses the same base and the same failure handling as `_coverage_changed_files`; any git failure yields `None` and the existing `diff_why` path.

### 3.3 Judgment

In `_judge_flakes`, after the own-file rule:

```
own = test_file in changed                       # today's rule, unchanged
covered_hit = intersect(map[F.id], changed_lines)  # list of path:range, may be empty
touched = own or bool(covered_hit)
touched_by = "test-file" | "covered-lines" | both
```

Truth table (the acceptance criteria, mechanised):

| own file changed | map has F | intersects | touched | `coverage` note |
|---|---|---|---|---|
| yes | any | any | true | (as today) |
| no | yes | yes | **true** (new) | `covers src/net.py:12-14` |
| no | yes | no | false | `per-test coverage consulted` |
| no | no / map missing / stale | – | false (today's behaviour) | `per-test coverage not consulted: <why>` |
| unknown file/diff | – | – | null (today's) | (as today) |

New entry fields (printed, never a verdict): `touched_by` (`file`|`covered`), `covers` (≤3 `path:range` strings, then a count), `coverage_consulted` (bool) with `coverage_why` when false. `_flake_judgment_tag` renders them; legacy records lack the keys and render as today.

The no-map row deliberately stays `false`, not `null`: absence of an optional signal must not turn every flake in every product into "touched/unknown" (that would be a behaviour change for the 100% of products without per-test coverage; acceptance 3 forbids it).

### 3.4 Staleness and trust

- Map `tree` ≠ the record's `evidence_tree` ⇒ not consulted, `coverage_why: "map is for a different tree"`. Same fail posture as any stale evidence, lenient only in the sense "behaves as today".
- Unparseable / wrong `v` / wrong shape ⇒ not consulted, with the reason. Never raises (return-value convention).
- Size cap on read (e.g. 20 MB) ⇒ not consulted, reason names the cap.

### 3.5 What does not change

Schema of `.test-evidence.json`, `flaky_policy` values, `test-reference-verify`, the symbol-grep level, runner integration, and the `block` handling (`blocked` is driven by `touched`, so a covered-line hit now blocks under `block`, which is the point).

## 4. Build slices

1. `lib/coverage.changed_line_ranges` + unit tests on crafted `-U0` output (add, modify, pure delete, rename, binary, multi-hunk). Red-verify: a pure-delete case must fail against a naive "added lines only" version.
2. Sidecar loader + validator (`lib/gates.py` beside `flaky_entries`): staleness, malformed, oversize, id-miss.
3. `_judge_flakes` intersection + new entry fields; truth-table test, one case per row.
4. `_flake_judgment_tag` rendering + `docs/project-state-keys.md` (`flaky_policy` paragraph) and `docs/test-report-contract.md` (sidecar contract) in the same change.
5. Critic prose (`goals-1-3.md`, `review-protocol.md`) names `touched_by: covered` so the Critic reads it as "branch explains this flake".

## 5. Risks

- **Coarse coverage over-touches.** Line coverage of shared helpers (a logging util every test executes) would mark nearly every flake touched whenever a helper changes. Acceptable for the strict posture, but it may make `block` noisy; mitigation is the printed `covers` so the owner can see why. Open question 2.
- **Id drift.** If an adapter's ids differ from junit ids the join silently misses and degrades to today's behaviour with a "not consulted for this test" note — visible, not silent.
- **Nothing produces the map today**, so until a product adopts an adapter this change is inert. That is intended (scope-out), but means value depends on #619/#618-style tooling. A produced-and-never-consumed risk is the *reverse* here (consumer first); name the first producer before building (open question 3).

## 6. Open questions for the owner

1. **Sidecar vs ledger.** Ship the sidecar now, or wait for #1096's ledger and carry the map there? Recommendation: sidecar now; the loader is the only part that changes.
2. **Over-touch control.** Accept line-level intersection as-is, or ignore covered ranges in files matching a product-declared `coverage_ignore` (shared helpers)? Recommendation: as-is first; add the knob only if `block` proves noisy.
3. **First producer.** Which adapter proves the format — a `coverage.py` contexts (`--cov-context=test`) converter for prawduct's own suite? Recommendation: yes, built as part of slice 2 as a test fixture so the format is exercised end to end.
4. **Pure-deletion anchoring** (§3.2): both neighbouring lines, or only the following line? Recommendation: both.
