# Issue #249 — Coverage: The Coverage Floor Is Python-Only: Requirements

`status: draft · stage: requirements · area: coverage · added: 2026-08-23 · revised: 2026-08-31 ·
source: scheduled backlog session · issue: https://github.com/brookstalley/prawduct/issues/249`

Related: siblings #618 (socket 2 — blast radius, requirements+design merged), #619 (socket 3 —
diff-scoped mutation, requirements+design merged), #620 (socket 4 — API diff, requirements+design
merged); GOV-2R8K, the single home of the shared four-socket contract
(`.prawduct/artifacts/change-evidence-design.md`), which this document must not restate. Also
related: #556 (a residual gap in the language-agnostic green-is-evidence trigger this item's
producer partially closes as a side effect — see Grounding facts and Decision 7).

## Problem

The framework's only shipped answer to "is this change exercised at all?" is
`plugin/bin/test-reference-verify`'s symbol-grep, which understands only Python `def`/`class`
syntax. On a polyglot or non-Python repo the framework's "the tests actually referenced the
changed code" guarantee does not exist — and because this mechanism feeds `verify_coverage`, a
BLOCKING Goal 1 Critic check, `architecture.md` names it "the most serious instance found" of the
Python-specificity norm's violation. Socket 1 is the instrument for exactly this gap: the
product's own coverage tooling plus an existing diff-coverage normalizer, whose verdict prawduct
consumes rather than re-derives. The design rationale, the four-socket contract shape, and the
default report-only posture all live in `change-evidence-design.md` and are not re-derived here;
this document grounds socket 1's five acceptance criteria against the current codebase and
resolves the decisions that document deliberately left open where they are scoped to this socket
alone.

## Grounding facts

Re-verified against `origin/develop` at commit `7583fb29` (2026-08-31), correcting an earlier pass
(commit `f1d78cc5`, 2026-08-23) whose line citations had drifted and whose GOV-6X2N reference no
longer matches the tree — both corrected below and flagged inline where they matter:

- **The shipped floor's complete output shape is five fields, and `coverage_level` is a hardcoded
  literal, never computed.** `_build_evidence_fields` (`plugin/bin/test-reference-verify:271-276`)
  returns exactly `verifier`, `coverage_level` (always the string `"referenced"`), `tests_executed`,
  `changes_referenced`, `changes_unjudged` — there is no sixth field, and no code path in this file
  ever assigns `"executed"`. `VERIFIER_NAME` (`:58`) is `"test-reference-verify (floor:
  symbol-grep)"`. Unchanged since the 2026-08-23 pass (`test-reference-verify` carries zero diff
  against it in the current tree).
- **The Python-specificity gate is a single, complete predicate.** `_is_python_file`
  (`plugin/bin/test-reference-verify:142-145`) is `path.suffix == ".py" or _looks_like_python(path)`
  (the latter checking for a Python shebang on extensionless scripts, `:126-140`); symbol extraction
  is `_PY_SYMBOL_RE` (`:64-67`), matching only `def`/`async def`/`class` lines. Any file failing
  `_is_python_file` is routed straight to `changes_unjudged` at the call site (`:239`) — never
  silently passed, which is the mechanism's one already-correct property this item must not
  regress.
- **The `referenced` vs `executed` distinction the design doc invokes is real, ratified plumbing —
  but only one side of it has ever been populated.** `_EVIDENCE_COVERAGE_LEVELS =
  frozenset({"referenced", "executed"})` (`plugin/lib/gates.py:70`, unchanged) is a validated enum;
  `verify_coverage`'s own docstring names the gap directly: *"The reasoning does not survive a
  `coverage_level: executed` verifier, whose evidence is execution: no in-plugin writer emits that
  level today, and the day one does is the day this needs to ask"* (`gates.py:1785-1787` — the
  2026-08-23 pass cited `:1774-1776`; an unrelated verify-resolutions docstring edit earlier in the
  file shifted every line below it by +11, corrected throughout this revision). A repo-wide search
  confirms `"executed"` is never assigned as a `coverage_level` value anywhere in shipped code — it
  exists only as the enum member, as prose telling product-authored verifiers what they *should*
  emit, and as one dead conditional branch in `verify_coverage`'s severity wording
  (`gates.py:1868-1869`: `if coverage_level == "executed": suffix = "has no executing test."`).
  Socket 1 is precisely "the day one does."
- **`verify_coverage`'s gating logic is fully report-only/blocking-switchable today, and the switch
  is already the right one for this socket.** `coverage_required` (read via `read_bool_yaml_key`)
  gates the entire check: false (the default) → `"skipped: coverage_required is false (default in
  v1.4)"`, return 0, no enforcement at all (`gates.py:1792-1794`). When true, changed files split
  three ways: `skipped` (unjudged or deleted, reported only — the list built at `:1844-1847`,
  printed at `:1852-1857`), `missing` (changed, not referenced, not skipped — the actual gate
  population, `:1848-1851`), and everything else passes (`:1858-1863`). Severity wording is already
  `coverage_level`-scaled (`:1865-1874`). The full function runs `gates.py:1754-1881`. This is the
  same file `changes_unjudged` mechanics used across sockets 2–4's "unchecked, never passed"
  precedent, native to socket 1's own gate.
- **No per-language or diff-coverage-tool declaration key exists anywhere in `project-state.yaml`,
  template or live.** An exhaustive case-insensitive search for `diff-cover`, `diff-test-coverage`,
  `lcov`, `cobertura`, `clover`, `jacoco` returns zero matches in either
  `plugin/templates/project-state.yaml` or `.prawduct/project-state.yaml`. The only existing
  declaration surface in the COVERAGE EVIDENCE / TEST EXECUTION blocks
  (`plugin/templates/project-state.yaml:329-375` — shifted from the 2026-08-23 pass's `326-372` by
  an unrelated `active_build_plan` comment edit earlier in the file; a further `sentinel_command:`
  block for the unrelated `audit-learnings` sentinel-grading feature was also added just past this
  range since that pass, and names no coverage tool) is `coverage_required`, `test_command`/
  `test_commands`, and `tests_dirs` — none of which name a coverage tool or report format. Socket
  1's producer declaration is greenfield, exactly like its siblings'.
- **No LCOV/Cobertura/Clover/JaCoCo parser exists anywhere in the repo, confirming the issue's own
  2026-08-07 Correction has not regressed.** The only files mentioning any of these formats are
  `change-evidence-design.md` itself; `test-reference-verify`'s only parsing is its own Python
  regex and plain-text substring matching — it ingests no external coverage-report format. This is
  the concrete evidence behind the issue's own acceptance criterion "prawduct ships no
  coverage-report parser."
- **The evidence store's `kind` enum is fail-closed and has no slot for a coverage-specific fact,
  same open state as every sibling.** `KNOWN_KINDS = frozenset({"review", "resolution",
  "disposition", "guard-refusal"})` (`plugin/lib/evidence.py:84`, unchanged); `append_fact` rejects
  any other kind outright (`:191-196`, unchanged — the 17 lines `evidence.py` gained since the
  2026-08-23 pass are inside `_cmd_list`, well after this range, and do not touch it). `test-run` is
  named reserved-but-unimplemented (`.prawduct/artifacts/data-model.md:26-27,57` — unchanged —
  *"extending the store to subsume [test-run/PR-review evidence] is design direction, not yet a
  ratified norm"*), and is not itself a coverage-specific kind. This is the identical open question
  #618/#619/#620 already flag for their own sockets, not new to socket 1.
- **A separate, already-partially-addressed governance consumer of the same root cause exists and
  is out of this item's scope — correcting the 2026-08-23 pass's tracking reference.** That pass
  named the residual gap "GOV-6X2N," an informal id that resolves to no filed issue (a repo-wide
  search finds it nowhere). The code itself has since been corrected on exactly this point: the
  comment above `_GREEN_IS_EVIDENCE_DIRECTIVE` (`plugin/bin/prawduct-hook:3001-3013`) now states
  plainly that its own *predecessor* comment "previously said it was 'tracked separately' while
  naming no item, which is how it stayed open long enough to be worth this warning: a tracking
  reference that points at no id is not a tracking reference" — and names the real, filed successor
  directly: **#556** (`brookstalley/prawduct#556`, cited at `:3007`), *"governance: green-is-evidence
  is blind to unreferenced code"* — a Python file whose symbols no test mentions lands in neither
  `changes_referenced` nor `changes_unjudged`, so `_GREEN_IS_EVIDENCE_DIRECTIVE` (`:3016-3029`,
  which fires off `_evidence_changed_judged_code`, `:3031+`, reading the same `changes_referenced`
  field) stays silent on it. #556 is itself `related: COV-4M2J` — this issue. The predecessor
  limitation ("empty in every non-Python product") is separately closed (#348, unchanged). Once a
  real executed-level producer exists for a language, #556's gap narrows for that language as a side
  effect (an executed-level record still cannot see a wholly untested symbol, but the languages
  where the directive can fire at all grows) — worth recording so design does not have to
  rediscover it, but fixing `prawduct-hook`'s directive logic is not this item's work.
- **`test-reference-verify` is explicitly named, by the ratified architecture norm itself, as the
  socket this item must eventually retire toward — not delete outright.** `architecture.md:78`'s
  Retroactivity paragraph (content unchanged since the 2026-08-23 pass; the file's only diff since
  is a later addition to the same paragraph, about an unrelated site): *"Confirmed violating:
  `plugin/bin/test-reference-verify` (`_PY_SYMBOL_RE`, `_is_python_file` — and it feeds
  `verify-coverage`, a BLOCKING Goal 1 check that therefore passes silently on Swift/Rust/C#, the
  most serious instance found)."* The design doc's own Open Questions name the retirement path as
  unresolved: *"leaving it in place alongside a working socket would be two homes for one fact"*
  (`change-evidence-design.md:308-310`, unchanged) — this item does not resolve that question, only
  avoids worsening it.
- **The current Critic protocol's citation points are unchanged since the 2026-08-23 pass** (a diff
  check against the current tree confirms zero changes to `plugin/skills/critic/goals-1-3.md`).
  Self-containment is `:3-4`, the "Before you review" checklist runs `:19-21` and ends with *"Run
  `prawduct-hook test-status` and `prawduct-hook verify-coverage` (Goal 1). Nothing else executes"*
  at `:21`, and the Symbol-coverage bullet reviewers actually follow is at `:71`, reading in full:
  *"**Symbol coverage:** run `prawduct-hook verify-coverage`. Exit 1 with `missing-coverage:` stderr
  lines → BLOCKING per missing file; quote each verbatim — wording is `coverage_level`-scaled and
  must not be softened."* Socket 1's design pass can cite these directly.
- **The precedent for "requirements numbers every decision, including the ones punted to design"
  is established across all three sibling docs, and the declaration-surface-count question is
  explicitly left for whichever socket's design lands first.** #620's own Scope-out states: *"cross-
  socket, not decided for socket 4 in isolation; whichever socket's design lands first should
  settle it, or it is settled directly on the design doc."* Socket 1 follows the identical shape
  below rather than attempting to resolve that cross-socket question here — and, per the Acceptance
  section below, this item's own design pass is now free to settle it, since no sibling design has.

## Decisions

Scoped to socket 1 alone — none of these reopen the shared four-socket contract, which stays owned
by `change-evidence-design.md`.

**1. A declared producer is an opaque invocation or result-artifact path that itself already emits
a normalized diff-coverage verdict — prawduct validates no coverage-report format and ships no
LCOV/Cobertura/Clover/JaCoCo parser.** This is the design doc's own corrected contract (the
2026-08-07 Correction the issue's Evidence section records) and mirrors `test_command`'s "declare
it — don't wrap it" precedent every sibling reuses. The product runs its native coverage tool plus
an existing diff-coverage normalizer (`diff-cover`, `diff-test-coverage`, or any other); prawduct
never touches the underlying report format's bytes.

**2. The minimal verdict primitive is fixed by the design doc, not deferred: uncovered changed
lines as `file:line` pairs.** Unlike socket 4 (whose primitive was explicitly left to design),
socket 1's shape is already stated as the required contract, "not an afterthought"
(`change-evidence-design.md`'s Socket 1 section) — this document requires it directly. Exact
serialization (whether pairs are encoded as strings, tuples, or ranges) is left open to design.

**3. A producer satisfying Decisions 1–2 populates `coverage_level: "executed"`, activating
plumbing that already exists and is already dormant — no new enum value, and no change to
`_EVIDENCE_COVERAGE_LEVELS` or `verify_coverage`'s existing severity-wording branch is needed.**
`gates.py`'s own docstring names this exact moment ("the day one does is the day this needs to
ask") as the trigger for re-examining the function's assumptions — this item is that trigger, and
design must re-read that docstring's caveat before extending the function.

**4. Whether the executed-level line data extends the existing F4a schema (`changes_referenced`/
`changes_unjudged`, file-granularity) with new field(s), or is carried as a separate shape
`verify_coverage` (or a successor) reads alongside it, is explicitly deferred to design.** The two
shapes answer different-grained questions — "was this file referenced at all" vs. "which lines in
it executed" — and design must pick one rather than assume the file-level fields can silently
absorb line-level data. Whichever is chosen must respect additive-only field evolution and loud
(never silent) handling of a schema-ahead or malformed record, per `data-model.md`'s existing
forward-incompatibility rules — the same constraint every sibling states for its own storage
question.

**5. `coverage_required` remains the single activation/blocking lever for socket 1 — no new
project-state.yaml boolean key is introduced.** Unlike sockets 2–4, which each need a brand-new
opt-in key, socket 1's lever already exists: `verify_coverage` already reads `coverage_required`
as exactly the report-only/blocking switch this socket needs. Reusing it, rather than adding a
second key that would mean the same thing, is what "declare it, don't wrap it" implies once a
lever already exists.

**6. `test-reference-verify` is demoted to socket 1's fallback producer, unchanged in its own
behavior, when no executed-level producer is declared — it is not retired by this item.** This is
what preserves the Python-specificity norm's fail-open guarantee for every product that has not
yet adopted a stronger producer, and is the design doc's own explicit adoption path (*"`test-
reference-verify` is demoted, not deleted... it becomes socket 1's fallback producer when no
better one is declared"*). `test-reference-verify`'s actual retirement is the design doc's own
open question (`change-evidence-design.md:308-310`) and is not resolved here.

**7. The #556 governance consumer of `changes_referenced` is not this item's work, but this item's
producer narrows its blind spot for adopting languages as a side effect.** #556 is separately filed
(correcting the earlier pass's untracked "GOV-6X2N" reference — see Grounding facts), its
predecessor limitation is already closed (#348), and its residual gap (a symbol declared but never
referenced by any test, in neither evidence list) narrows for any language that adopts an
executed-level producer under this item — but fixing `prawduct-hook`'s directive logic itself is
out of scope here.

**8. Documentation must state the Case-B limit wherever socket 1's guarantee is described, exactly
as the design doc requires.** An `executed` verdict proves the changed line ran during a test; it
proves nothing about whether any assertion constrained that line's behavior. This item does not
close that gap (socket 3 does) — it must not be described as if it does.

## Requirements

MUST unless marked SHOULD.

- **CE1-1** A product declares its socket 1 producer as an opaque invocation or result-artifact
  path; prawduct validates no coverage-report format name and ships no per-format parser or
  allowlist (Decision 1).
- **CE1-2** The verdict is uncovered changed lines as `file:line` pairs, matching the design doc's
  stated primitive verbatim (Decision 2); exact serialization is out of this document's scope
  (design-stage).
- **CE1-3** A producer satisfying CE1-1/CE1-2 populates `coverage_level: "executed"` in the merged
  evidence record — the enum value and `verify_coverage`'s severity branch for it already exist and
  require no new gate logic (Decision 3).
- **CE1-4** Whether executed-level line data extends the existing `changes_referenced`/
  `changes_unjudged` schema or is carried in a separate shape is a design-stage decision, not
  resolved here (Decision 4); whichever is chosen respects additive-only field evolution and loud
  (never silent) handling of a schema-ahead record.
- **CE1-5** `coverage_required` remains the sole activation/blocking lever for this socket; no new
  project-state.yaml boolean key is introduced for it (Decision 5).
- **CE1-6** `test-reference-verify` continues to serve as socket 1's fallback producer, emitting
  `coverage_level: "referenced"` unchanged, whenever no executed-level producer is declared —
  demoted, not retired, by this item (Decision 6).
- **CE1-7** A changed file with neither a declared executed-level producer's verdict nor an
  applicable `test-reference-verify` floor result continues to report `changes_unjudged`, never
  coalesced with a passing verdict — the existing, already-correct behavior
  (`gates.py:1844-1851`) this item must not regress.
- **CE1-8** Prawduct's own code contains no LCOV/Cobertura/Clover/JaCoCo parser and no diff-coverage
  engine of its own, confirmed absent today and required to stay that way; the verdict is consumed
  from the product's own coverage tool plus an existing diff-coverage normalizer, never re-derived
  (Decision 1).
- **CE1-9** Documentation states, wherever socket 1's guarantee is described, that an `executed`
  verdict proves the changed line ran during tests and never that any assertion constrained its
  behavior (Case B) (Decision 8).
- **CE1-10** Fixing #556's directive-silence gap is out of scope for this item, though its residual
  narrows as a side effect once a language adopts an executed-level producer (Decision 7).

## Acceptance

Restated from the issue body, grounded against the current tree:

- [ ] A non-Python product gets a diff-coverage verdict without hand-rolling a verifier.
- [ ] Prawduct ships no coverage-report parser — the verdict is consumed, never re-derived.
- [ ] A missing producer reports *unchecked*, never *passed* — inherited automatically once
      `test-reference-verify` is the fallback (Decision 6) and its existing `changes_unjudged`
      handling is preserved (CE1-7).
- [ ] The socket defaults to report-only; a blocking threshold is a product opt-in via the existing
      `coverage_required` key, with no new key introduced (CE1-5).
- [ ] The Case-B limit (covered ≠ verified) is stated wherever the guarantee is stated (CE1-9).

## Scope-out (this item)

- The shared four-socket contract, its rationale, blind spots, and adoption/rollout mechanics —
  `change-evidence-design.md`'s territory, per the issue's own scope-out.
- Sockets 2–4 (#618, #619, #620) — sibling items with their own requirements passes, already
  merged.
- Whether all four sockets share one `project-state.yaml` declaration surface or four
  (`change-evidence-design.md` Open Question #1) — cross-socket, not decided for socket 1 in
  isolation; no sibling design has settled it yet, so socket 1's own design pass may settle it or
  defer it again.
- The exact declaration key name for the producer invocation, the verdict's exact serialization
  format, whether the F4a schema is extended in place or replaced by a parallel shape (Decision 4),
  and any persistence choice beyond `.test-evidence.json` — all design-stage deliverables.
- Retiring `test-reference-verify` or otherwise resolving its Python-specificity violation in
  general — tracked by the Python-specificity migration (LNG-5W8R) and the design doc's own
  retirement open question (`change-evidence-design.md:308-310`); this item only adds a
  stronger fallback-first producer alongside it.
- Fixing #556 (`_GREEN_IS_EVIDENCE_DIRECTIVE`'s silence on unjudged changesets) — separately filed
  and tracked (Decision 7).
- Selecting or wiring a specific diff-coverage normalizer for any particular ecosystem — a
  product's own declaration, per the socket contract.
- Which real toolchains cannot produce any of LCOV/Cobertura/Clover/JaCoCo — the design doc's own
  explicit Open Question, carried forward, not resolved here.

## Evidence / references

- `.prawduct/artifacts/change-evidence-design.md` — the shared four-socket design; §"Socket 1 —
  Exercised? (diff coverage)", the defect table, Open Questions.
- `plugin/bin/test-reference-verify:58,64-67,126-145,239,271-277` — `VERIFIER_NAME`,
  `_PY_SYMBOL_RE`, `_looks_like_python`/`_is_python_file`, the `changes_unjudged` routing, and
  `_build_evidence_fields`'s complete five-field output shape.
- `plugin/lib/gates.py:70,1754-1881,1785-1787,1792-1794,1844-1863,1865-1874` —
  `_EVIDENCE_COVERAGE_LEVELS`, `verify_coverage`'s full gating logic, its own docstring naming the
  dormant `executed` case, the `coverage_required` report-only switch, and the
  `skipped`/`missing`/severity-wording split. (Re-verified 2026-08-31; the 2026-08-23 pass's
  citations for this function were `1743-1870`/`1774-1776`/`1781-1783`/`1833-1863`/`1857-1858` — an
  unrelated verify-resolutions docstring edit earlier in the file shifted everything from
  `verify_coverage` onward by +11 lines, corrected here.)
- `plugin/templates/project-state.yaml:329-375` — the COVERAGE EVIDENCE / TEST EXECUTION blocks:
  `coverage_required`, `test_command`/`test_commands`, `tests_dirs` — confirming no existing
  per-format declaration key. (Shifted from `326-372` by an unrelated `active_build_plan` comment
  edit earlier in the file; re-verified 2026-08-31.)
- `plugin/lib/evidence.py:84,191-196` — `KNOWN_KINDS` and `append_fact`'s fail-closed rejection of
  unregistered kinds. Unaffected by the 17-line addition this file gained since 2026-08-23 (inside
  `_cmd_list`, well after this range).
- `.prawduct/artifacts/data-model.md:26-27,57` — the reserved-but-unratified `test-run`/`pr-review`/
  `promotion` kinds, the open question `change-evidence-design.md` inherits and this item does not
  resolve.
- `plugin/bin/prawduct-hook:3001-3013,3016-3029,3031` — the comment above
  `_GREEN_IS_EVIDENCE_DIRECTIVE` explicitly correcting its own predecessor's untracked reference and
  naming `brookstalley/prawduct#556` as the filed successor (re-verified 2026-08-31; the 2026-08-23
  pass cited `2780-2803` and the informal, unfiled "GOV-6X2N" — both corrected here), the directive
  constant itself, and `_evidence_changed_judged_code`.
- `.prawduct/artifacts/architecture.md:78` — the Retroactivity paragraph naming
  `test-reference-verify` a confirmed Python-specificity violation, "the most serious instance
  found." (Content unchanged at this line since 2026-08-23; the paragraph gained an unrelated
  addition about a different site.)
- `plugin/skills/critic/goals-1-3.md:3-4,19-21,71` — the self-contained protocol, the "Before you
  review" checklist ending in "nothing else executes," and the Symbol-coverage bullet. Confirmed
  unchanged since the 2026-08-23 pass (zero diff against this file).
- `brookstalley/prawduct#556` — "governance: green-is-evidence is blind to unreferenced code,"
  `related: COV-4M2J` (this issue); the correctly-filed successor to the earlier pass's untracked
  "GOV-6X2N" reference.
- `documentation/issues/618-requirements.md`, `619-requirements.md`, `620-requirements.md` — the
  sibling socket requirements passes this document follows in structure and mirrors for shared
  open questions (declaration-surface count, evidence storage).
