# Issue #619 — Tests: Diff-Scoped Mutation as an Opt-In Evidence Socket: Design

`status: draft · stage: design · area: tests · added: 2026-08-27 · source: scheduled backlog
session · issue: https://github.com/brookstalley/prawduct/issues/619`

Builds on `documentation/issues/619-requirements.md` (MUT-1 through MUT-9, Decisions 1–6). This
document resolves the requirements doc's two design-stage deferrals — the PR-review consumer
(Decision 5, MUT-8) and the storage question (Decision 6, MUT-9) — and specifies file-by-file
changes an implementation chunk can follow directly.

Socket 3 of the four-socket change-evidence contract; siblings #249 (socket 1), #618 (socket 2),
#620 (socket 4) have their own requirements/design passes. The shared contract itself
(`.prawduct/artifacts/change-evidence-design.md`) is not restated here.

## Summary of what ships

1. **MUT-1, MUT-2, MUT-3, MUT-4** — two new `project-state.yaml` keys: `mutation_producer`
   (opaque invocation, mandatory `{base}` placeholder) and `mutation_required` (boolean, default
   `false`, independently read — never inherited from any other socket's opt-in).
2. **MUT-4, MUT-9** — a new writer, `prawduct-hook mutation-evidence record`, which runs the
   declared producer once and persists its verdict to `.prawduct/.mutation-evidence.json` — a
   dedicated file mirroring `.test-evidence.json`'s shape and freshness model, not a new
   `evidence.py` `kind` (Decision 6 below).
3. **MUT-5, MUT-9** — a new cheap reader, `lib/gates.py`'s `mutation_status()`, exposed as
   `prawduct-hook mutation-status`: reads the persisted record, never re-runs the producer.
4. **MUT-8** — `review-protocol.md`'s Goal 1 ("Nothing Is Broken") gains one bullet, **`final`/
   `cumulative` mode only** — deliberately not `goals-1-3.md` (Decision 5 below explains why this
   differs from sibling socket 2's placement).
5. `plugin/templates/project-state.yaml` documentation for the two new keys.

## Decisions resolved

### Decision 5 — the consumer is `review-protocol.md` Goal 1, `final`/`cumulative` only, never `goals-1-3.md`

**Grafts onto the existing "Nothing Is Broken" goal, at the review cadence that matches the
socket's own cost model — not the per-chunk cadence its siblings use.**

The requirements doc's grounding facts already establish that socket 3 has no existing consumer
seam (unlike socket 4's two live candidates) and that this is a materially different starting
point from siblings 2 and 4. Two constraints, both already ratified, decide the placement:

- **Both Critic files forbid the fork from executing the mutation run itself.**
  `goals-1-3.md:6-7`, "Never run tests, builds, or executables... Run `prawduct-hook test-status`
  and `prawduct-hook verify-coverage` (Goal 1). Nothing else executes," and
  `review-protocol.md`'s own Goal 1, "**Do not run tests.**" This rules out a live producer
  invocation as the consumer path (unlike sockets 2 and 4, which invoke their live, zero-cost
  producer directly from a `prawduct-hook` command the Critic is allowed to run) — Decision 6
  below is what makes a *read* possible at all: `mutation-status` only ever reads a file another
  actor already wrote.
- **Even a cheap read is wrong at chunk cadence, because a mutation run is not.** A
  freshness check compares the persisted record's tree against the tree under review. At
  `goals-1-3.md`'s per-chunk cadence (target wall-clock 1-2 minutes, one dispatch per chunk), the
  record would read *stale* on almost every chunk — mutation testing is explicitly "high"
  test-runtime cost (`change-evidence-design.md:34`, the one socket "expected to stay rare"),
  so no builder re-runs it every chunk. Two ways that plays out, both bad: the builder re-runs
  the expensive producer every chunk to keep the record fresh — the exact review-wall-clock P0
  violation Decision 3 (no cascading opt-in) was written to prevent, just self-inflicted instead
  of inherited from a sibling — or the record stays stale and every chunk review prints an
  `unchecked` line nobody can act on, which is noise, not evidence (the review-wall-clock NFR's
  "a control whose findings are printed and forgotten... can never be retired on evidence").
  Reading it once per PR bundle, at `final`/`cumulative`, matches the cadence the socket's own
  cost was designed around: `change-evidence-design.md:150-151`'s "diff-scoping and result reuse
  have moved this from an overnight batch job to something runnable in the loop" describes a
  bundle-scale loop, not a chunk-scale one.

This is a genuine placement difference from sibling socket 2 (issue #618), which lives in
`goals-1-3.md` because its producer is zero-cost and can be invoked live at every chunk with no
cadence mismatch. Socket 3's cost model is the opposite of socket 2's, so its placement is too —
consistent with `change-evidence-design.md`'s per-socket cost table, not a departure from it.

**The bullet's severity mirrors `test-status`'s existing shape exactly** (`review-protocol.md`
Goal 1, the direct precedent both sibling designs already cite): a mechanical exit-code check,
severity assigned from it, no re-derivation of what the check computed.

> - **Test adequacy (mutation):** when `mutation_required: true`, run `prawduct-hook
>   mutation-status`. Exit 0 with a `clean:` line = no surviving mutants in changed code. Exit 0
>   with `unchecked: ...` = `mutation_required` is set but no current record exists — **WARNING**
>   ("mutation evidence does not cover the changeset — run `prawduct-hook mutation-evidence
>   record`"). Exit 1 = surviving mutants in changed code, or the opted-in product's record is
>   missing/stale — **BLOCKING**, quoting the `survivors:` lines verbatim (wording is
>   `mutation_required`-scaled and must not be softened, mirroring symbol coverage's own
>   verbatim-quote rule). When `mutation_required` is unset or false, this bullet does not run —
>   don't invoke a check whose product never opted in.

Placed directly after the existing `test-status` bullet in Goal 1 — same goal, same "read a
mechanical exit code, don't re-derive it" shape, and the same place a reviewer already looks for
"is the test evidence trustworthy."

### Decision 6 — a dedicated `.mutation-evidence.json`, not a new evidence-store `kind`

Requirements' Decision 6 deliberately left open where the verdict is persisted, "not assumed to be
`evidence.jsonl`." Resolved by the same reasoning siblings #618 and #620 used to resolve their own
storage questions — but reaching the opposite conclusion, because socket 3's cost model is the
opposite of theirs:

- **Sockets 2 and 4 persist nothing because their producers are cheap enough to invoke live on
  every read** (`.prawduct/artifacts/change-evidence-design.md:140-141,163` — "zero test-runtime
  cost," "near zero"). Socket 3 has no such property — it is the design doc's own named example of
  a **high**-cost instrument (`:34`). There *is* an expensive half to decouple write-time from
  read-time for, which is exactly the shape `.test-evidence.json` already solves for the
  suite-run/status-read split (`test-evidence record` writes, `test-status` reads — `gates.py:136-
  260`, `bin/prawduct-hook:3109-3200`).
- **`.test-evidence.json` is not itself a kernel-v3 evidence-store record.** It is its own
  dedicated file, read by `_load_test_evidence`/`tests_are_current` with a purpose-built freshness
  model (session-fresh OR tree-valid, `gates.py:154-260`), entirely outside `evidence.py`'s
  `KNOWN_KINDS`. That precedent already answers `data-model.md`'s open "does the append-only store
  subsume test-run evidence" question for the *closest existing analog* to a mutation-run record:
  it doesn't, today, for test evidence itself. Mutation evidence is close enough in shape (a
  per-product, occasionally-expensive-to-produce, freshness-checked verdict file) that following
  the same working pattern is the lower-risk choice — it ships without waiting on
  `data-model.md`'s still-unratified subsumption question, the same way `.test-evidence.json`
  already does.
- **The freshness primitives generalize without new code.** `_test_evidence_tree_valid`
  (`gates.py:213-260`) already accepts a `target_tree` parameter distinct from the working tree
  ("not always the working tree... `suite_vouches_for_tree` passes the tree its calling gate
  composes to"), built on `evidence.capture_tree`/`evidence.tree_diff`/
  `coverage_algebra.judgeable_files` — none of which are test-specific. `.mutation-evidence.json`
  reuses this exact machinery rather than duplicating a second tree-validity checker (the "two
  homes for one fact" retirement risk `change-evidence-design.md:308-310` warns against, applied
  here to *mechanism* rather than *data*).

**Record shape**, mirroring `.test-evidence.json`'s field set where the concepts match:

```json
{
  "schema": 1,
  "timestamp": "2026-08-27T00:00:00Z",
  "producer": "scripts/mutation-verdict.sh",
  "base": "origin/main",
  "evidence_tree": "<git tree object written by evidence.capture_tree>",
  "survivors": [
    {"file": "src/pricing.py", "line": 42, "description": "arithmetic mutant survived"}
  ]
}
```

`survivors` is the socket-3 analog of socket 4's `breaking` list (`620-design.md` §Decision 4) —
free-form `description`, prawduct renders it, never parses it. `schema` lets `mutation-status`
reject a version it does not understand rather than misparse it, the same forward-incompatibility
posture every sibling socket's verdict envelope already carries. No `failed`/`degraded` fields:
those are `.test-evidence.json`-specific (they answer "did the suite run cleanly," not "did any
mutant survive") and MUT-9 does not require they be shared.

**Freshness = tree-valid only, no session-fresh clause.** `.test-evidence.json`'s session-fresh
clause exists because a pytest run is cheap enough to expect fresh within the current session; a
mutation run is not (Decision 5), so requiring session-freshness would make the record read stale
on every session restart regardless of the tree — a false-stale class the tree-validity clause was
designed to avoid reintroducing (`gates.py:213-217`'s own rationale for why the removed
content-hash mechanism was retired). `mutation-status` uses the tree-validity comparison alone,
against the tree the current review is scoped to (working tree for `final`, `merge-base...HEAD`
for `cumulative` — the same tree each mode already diffs for its own Goal 1 checks).

## Section 1 — `project-state.yaml` keys (MUT-1, MUT-2, MUT-3, MUT-4)

**Where:** `plugin/templates/project-state.yaml`, a new heading placed directly after the "CHANGE
EVIDENCE — PUBLISHED SURFACE" block issue #620's design adds — grouping the four sockets'
declaration blocks together, matching that block's comment style and placement convention.

```yaml
# =============================================================================
# CHANGE EVIDENCE — MUTATION (opt-in, socket 3 of the change-evidence contract)
# =============================================================================
# The only socket expected to stay rare: diff-scoped mutation testing is
# high test-runtime cost, so it is never invoked live at review time. Declare
# the command that runs your mutation tool scoped to the diff and prints
# socket 3's normalized verdict to stdout — a wrapper around PIT incremental,
# Stryker --since, or mutmut --incremental/--since (whichever fits the
# ecosystem) emitting {"schema": 1, "survivors": [...]}. Run it yourself with
# `prawduct-hook mutation-evidence record` before requesting a final/
# cumulative Critic review; nothing in the framework runs it automatically.
# See `.prawduct/artifacts/change-evidence-design.md` and
# `documentation/issues/619-design.md`.

# mutation_producer: scripts/mutation-verdict.sh --since={base}
#   Opaque, unwrapped shlex-split invocation, run from the repo root — same
#   "declare it, don't wrap it" contract as test_command:/api_diff_producer:.
#   MUST contain a {base} literal — the hook substitutes the resolved diff
#   base (same resolver `resolve-base` uses) so the command can scope itself
#   to changed code, mirroring test_command:'s mandatory {junit_xml}
#   placeholder. Shell operators (&&, |, FOO=1) are not supported — point
#   the command at a script for compound invocations.

# mutation_required: false
#   Opt-in blocking. Defaults to report-only-via-WARNING: a stale/missing
#   record is surfaced but never fails the check until set true. Setting
#   this true is what makes surviving mutants, and a missing/stale record,
#   BLOCKING at final/cumulative review — read independently of every other
#   socket's opt-in (MUT-3): adopting coverage_required, reference_index_
#   producer, or api_diff_required never enables this socket as a side
#   effect.
```

**Compatibility:** both keys are optional and additive; a `project-state.yaml` predating this
change reads as "not declared" (`read_str_yaml_key` returns `None`) and "false"
(`read_bool_yaml_key`'s existing fail-soft-to-`False` default) — no migration, exactly
`coverage_required`'s and `api_diff_required`'s existing posture.

## Section 2 — `lib/gates.py`: the writer/reader split (MUT-4, MUT-5, MUT-9)

**`mutation_evidence_record(project_dir)`** — the writer, invoked only by `prawduct-hook
mutation-evidence record`, never by the Critic:

- Reads `mutation_producer`; missing → prints `no mutation_producer declared — nothing to record`
  and exits 1 (a record command with nothing to record is a usage error, distinct from
  `mutation-status`'s soft `unchecked`, which the reviewer must never treat as blocking on its
  own — MUT-5's "never silently coalesced with clean" applies to the *reader*, not to a writer
  asked to do nothing).
- Resolves the diff base the same way `resolve-base`/`_coverage_resolve_base` already do, and
  substitutes it into `mutation_producer`'s mandatory `{base}` token (rejects the command at
  record time if the token is absent, mirroring `test_command`'s `{junit_xml}` validation at
  `bin/prawduct-hook:3459-3464`).
- Runs the substituted command: `shlex.split`, `subprocess.run(..., timeout=...)` — a generous
  named-constant timeout distinct from the near-zero-cost sockets' 60s
  (`_MUTATION_PRODUCER_TIMEOUT_SECONDS`, left to the build chunk to size — this is explicitly the
  one socket where a long run is expected, not a symptom of a hung producer), `json.loads` the
  stdout, reject a `schema` other than `1` or a missing/non-list `survivors` key exactly as
  `_run_api_diff_producer` does for `breaking` (`620-design.md` §2).
- On success, captures the tree via `evidence.capture_tree(project_dir)` and writes
  `.prawduct/.mutation-evidence.json` atomically (mirroring `test-evidence record`'s atomic write)
  with the shape in Decision 6.
- On producer error (non-zero exit, timeout, malformed JSON), writes **nothing** — an old,
  still-tree-valid record must not be clobbered by a failed attempt to refresh it — and exits 1
  with the error on stderr.

**`mutation_status(project_dir)`** — the reader, the only one of the two the Critic ever invokes:

```python
def mutation_status(project_dir: Path) -> int:
    """Socket 3 (MUT, issue #619) — surviving-mutant verdict for the product's
    persisted mutation-evidence record. Never invokes the producer: reads
    ``.mutation-evidence.json``, written by ``mutation-evidence record``
    (issue #619 design, Decision 6 — the expensive half is decoupled from
    this cheap read the same way ``test-evidence record``/``test-status``
    decouple the suite run from its freshness check).

    Exit codes:
      0 — mutation_required unset/false (not applicable), OR true with a
          clean record (no survivors, tree-valid).
      1 — mutation_required: true AND (no record, a stale record, OR a
          non-empty survivors list). Mirrors verify_coverage's
          missing-evidence-file case: an unusable verdict source is a hard
          failure only when the product opted into blocking.

    stdout carries exactly one status line (`not-applicable: ...` /
    `unchecked: ...` / `clean: ...` / `survivors: N mutant(s)...`), quotable
    directly in a Goal 1 finding — same convention verify_coverage's stderr
    lines and api_diff_status's stdout line use.
    """
    prawduct_dir = gitstate.get_prawduct_dir(project_dir)
    state_path = prawduct_dir / "project-state.yaml"

    required = read_bool_yaml_key(state_path, "mutation_required")
    if not required:
        print("not-applicable: mutation_required is false")
        return 0

    record, why_not = _load_mutation_evidence(prawduct_dir)
    if record is None:
        print(f"unchecked: {why_not}")
        return 1

    valid, reason = _test_evidence_tree_valid(
        project_dir, record["evidence_tree"]
    )  # tree-only comparison — see Decision 6, no session-fresh clause
    if not valid:
        print(f"unchecked: mutation record is stale ({reason})")
        return 1

    survivors = record["survivors"]
    if not survivors:
        print(f"clean: no surviving mutants ({record['producer']})")
        return 0

    for s in survivors:
        print(f"  - {s.get('file', '?')}:{s.get('line', '?')}: {s.get('description', '')}",
              file=sys.stderr)
    print(f"survivors: {len(survivors)} mutant(s) — mutation_required: true", file=sys.stderr)
    return 1
```

`_load_mutation_evidence(prawduct_dir)` mirrors `_load_test_evidence`'s shape (on-disk /
parseable / object / schema-valid prologue) but reads `.mutation-evidence.json` and has no
`failed`/`degraded` handling — those fields don't exist in this record.

## Section 3 — `bin/prawduct-hook` wiring

```python
def cmd_mutation_evidence(project_dir: Path, argv: list[str]) -> int:
    """Run the declared mutation_producer and WRITE
    ``.prawduct/.mutation-evidence.json`` (issue #619). Thin wrapper — body
    lives in ``lib.gates.mutation_evidence_record``. A state-mutating writer:
    an unimportable lib fails CLOSED (exit 1), matching test-evidence
    record's posture — never report a false success for a record that was
    not written."""
    ...

def cmd_mutation_status(project_dir: Path) -> int:
    """Report the persisted mutation-evidence verdict. Thin wrapper — body
    lives in ``lib.gates.mutation_status`` (issue #619)."""
    return _gates().mutation_status(project_dir)
```

**Dispatch**, alongside the existing `test-evidence`/`test-status` cases:

```python
elif command == "mutation-evidence":
    return cmd_mutation_evidence(project_dir, args)
elif command == "mutation-status":
    return cmd_mutation_status(project_dir)
```

**`_USAGE`**: extend near the existing `test-status|validate-evidence|` segment —

```
"test-status|validate-evidence|mutation-status|"
"mutation-evidence record [--degraded \"<reason>\"]|"
```

**`_EPHEMERAL_SAFE_COMMANDS`**: add `"mutation-status"` only (alphabetical placement, near
`"test-status"`) — read-only by construction, matching `test-status`'s existing membership.
`mutation-evidence` (the `record` subcommand) is **not** added — it writes to `.prawduct/` and
runs an arbitrary declared producer, the same reason `test-evidence` itself is absent from this
set.

## Section 4 — `review-protocol.md` Goal 1 (MUT-8)

**Where:** `plugin/skills/critic/review-protocol.md`, Goal 1 "Nothing Is Broken," a new bullet
directly after the existing `test-status`-driven bullet — see the exact bullet text in Decision 5
above. `goals-1-3.md` (`chunk`/`verify-resolutions` modes) is deliberately **not** touched — the
cadence mismatch in Decision 5 is the reason, not an oversight.

**`critic/SKILL.md` `allowed-tools`**: add `Bash(prawduct-hook mutation-status)` and
`Bash(python3 plugin/bin/prawduct-hook mutation-status)` to the frontmatter allow-list, mirroring
the existing `test-status` pair's bare-command shape. `mutation-evidence record` is **not** added
— the Critic never runs it; it is the builder's own act, run before requesting review, the same
way the builder runs `test-evidence record` before requesting any review.

## Files touched

| File | Change |
|---|---|
| `plugin/templates/project-state.yaml` | New "CHANGE EVIDENCE — MUTATION" block: `mutation_producer`, `mutation_required` (MUT-1, MUT-2, MUT-4) |
| `plugin/lib/gates.py` | New `mutation_evidence_record()`, `mutation_status()`, `_load_mutation_evidence()`, `_run_mutation_producer()`, `_MUTATION_PRODUCER_TIMEOUT_SECONDS` (MUT-4, MUT-5, MUT-9) |
| `plugin/bin/prawduct-hook` | New `cmd_mutation_evidence`, `cmd_mutation_status`; two dispatch cases; `_USAGE` entries; `mutation-status` added to `_EPHEMERAL_SAFE_COMMANDS` |
| `plugin/skills/critic/review-protocol.md` | One new bullet under Goal 1 "Nothing Is Broken" (MUT-8) |
| `plugin/skills/critic/SKILL.md` | `allowed-tools` gains the `mutation-status` Bash pair |
| `tests/test_mutation_evidence_gate.py` (new) | See test plan below |

## Test plan

Following `tests/test_verify_coverage_gate.py`'s and siblings' own test-plan style — real git
repos, real hook subprocess, fixture producer scripts printing fixed JSON — no mocking of git or
the filesystem.

1. **`mutation_required: false`** — `mutation-status` with the flag unset → `not-applicable: ...`,
   exit 0, regardless of whether a record exists.
2. **`mutation_required: true`, no record** — `unchecked: no .mutation-evidence.json on disk`,
   exit **1**.
3. **`mutation_required: true`, stale record** — a record whose `evidence_tree` no longer matches
   the working tree (a judgeable file changed since) → `unchecked: mutation record is stale
   (...)`, exit 1.
4. **`mutation_required: true`, current record, clean** — `clean: no surviving mutants (...)`,
   exit 0.
5. **`mutation_required: true`, current record, survivors present** — `survivors: N mutant(s)...`
   on stdout, per-survivor lines on stderr, exit **1**.
6. **`mutation-evidence record`, no `mutation_producer` declared** — `no mutation_producer
   declared — nothing to record`, exit 1, no file written.
7. **`mutation-evidence record`, `{base}` missing from the declared command** — rejected at record
   time, exit 1 (mirrors `test_command`'s `{junit_xml}` validation), no file written.
8. **`mutation-evidence record`, producer succeeds** — fixture script prints
   `{"schema": 1, "survivors": []}` → `.mutation-evidence.json` written with the current tree,
   exit 0.
9. **`mutation-evidence record`, producer errors** — fixture script exits non-zero → error on
   stderr, exit 1, **existing record (if any) untouched** — pinned by writing a valid record
   first, then failing a second `record` call and re-reading the first record unchanged.
10. **Schema mismatch on read** — a hand-written `.mutation-evidence.json` with `"schema": 2` →
    treated as `unchecked`, never silently parsed as schema 1 (mirrors CE4-6's forward-
    incompatibility posture, applied to this file).

## Open items for the build chunk (not resolved here)

- Sizing `_MUTATION_PRODUCER_TIMEOUT_SECONDS` — the design deliberately does not pin a number
  (Section 2), since "high cost" is the socket's defining property and a fixed short timeout
  would misclassify a legitimately slow run as a producer error.
- Whether a doctor/session-advisory nudge should remind a `mutation_required: true` product to run
  `mutation-evidence record` before requesting `final`/`cumulative` review — the design doc's
  general adoption advisory (`change-evidence-design.md` § Adoption) already covers *declaring*
  the producer; a separate *staleness* nudge is new territory this item does not resolve.
- Exact wording of the fixture producer scripts (cosmetic).

## Acceptance (carried from requirements, now with an implementation path)

- [ ] Surviving mutants in changed code are the reported verdict, diff-scoped via the mandatory
      `{base}` substitution, never a whole-repo mutation run — pinned by `mutation-evidence
      record`'s `{base}`-rejection case (test 7) and the producer's own diff-scoping (outside
      prawduct's control by design — MUT-4).
- [ ] Off by default; a product opts in via `mutation_required: true`, read independently of every
      other socket's opt-in — pinned by test 1 and Decision 5's per-key independence.
- [ ] A missing producer, or a missing/stale record, reports a distinct *unchecked* state — never
      silently coalesced with a clean verdict — pinned by tests 2, 3, 6, 10.
- [ ] Prawduct runs no mutation engine and implements no mutation operators — `mutation_producer`
      is an opaque, unwrapped invocation prawduct never inspects beyond its JSON envelope.
- [ ] A PR-review consumer is named and justified: `review-protocol.md` Goal 1, `final`/
      `cumulative` only (Decision 5) — pinned by Section 4 and the new bullet's placement.
- [ ] Whatever storage the verdict lands in respects additive-only field evolution and loud
      handling of a schema-ahead record — pinned by test 10; `.mutation-evidence.json` is a
      dedicated file, not a new `evidence.py` `kind` (Decision 6).

## Evidence / references

- `documentation/issues/619-requirements.md` — MUT-1 through MUT-9, Decisions 1–6, grounding
  facts this design resolves against.
- `.prawduct/artifacts/change-evidence-design.md:34,144-154,308-310` — socket 3's design-doc
  entry (high cost, opt-in, "the only socket expected to stay rare"), and the "two homes for one
  fact" retirement question Decision 6 avoids widening.
- `plugin/lib/gates.py:113-260` (`_load_test_evidence`, `tests_are_current`,
  `_test_evidence_tree_valid`) — the write/read decoupling and tree-validity primitives Decision 6
  reuses rather than duplicates.
- `plugin/bin/prawduct-hook:3109-3200` (`cmd_test_evidence`), `:3459-3464` (the `{junit_xml}`
  mandatory-placeholder validation) — the writer-command pattern and substitution-token precedent
  Section 2/3 mirror for `{base}`.
- `plugin/skills/critic/goals-1-3.md:6-7,19` — "Never run tests, builds, or executables... Nothing
  else executes," the constraint Decision 5 grounds the placement choice against.
- `plugin/skills/critic/review-protocol.md` Goal 1 (`test-status` bullet, "**Do not run tests.**")
  — the exact bullet shape Section 4's new bullet mirrors, and the second "don't execute it
  yourself" constraint Decision 5 cites.
- `documentation/issues/620-design.md` §Decision 4-5, `documentation/issues/618-design.md`
  §Decision 5-6 — the sibling sockets' verdict-envelope and storage reasoning this design follows
  where the cost model matches (envelope shape) and departs from where it doesn't (storage,
  consumer cadence).
- `plugin/lib/evidence.py:83,131-140` — `KNOWN_KINDS`, the fail-closed store Decision 6
  deliberately does not extend.
- `.prawduct/artifacts/data-model.md:26-28,57,107` — the reserved-but-unratified
  `test-run`/`pr-review`/`promotion` kinds; Decision 6 sidesteps this open question the same way
  `.test-evidence.json` already does.
- `.prawduct/artifacts/nonfunctional-requirements.md:18,22` — the review-wall-clock P0 constraint
  Decision 5's cadence argument is built on.
