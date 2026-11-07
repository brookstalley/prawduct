# Issue #1064 — governance: lint test docstrings for review and finding ids, then sweep: Requirements

`status: draft · stage: requirements · area: governance · added: 2026-11-07 · source: critic (PR review of feature/1052-evidence-transport) · issue: https://github.com/brookstalley/prawduct/issues/1064`

Related: #1050, #1052 (the branch where it was found), `plugin/methodology/building.md` ("Comments and durable specs are self-contained"), core.md rule "a rule you must RECALL … is its weakest form".

## Problem

`building.md` says review and finding ids never ship: history's one home is commits and the change-log. Nothing checks it, so the norm holds by recall. The issue estimated ~35 offending docstrings. Measured on this tree, the number is larger and the shape is different:

| Where `\b[RO]-\d+\b` or `rev-\d{8}T` appears in `tests/**/*.py` (excluding `tests/fixtures/`) | Count |
|---|---|
| String literals that are not docstrings (test data: finding ids like `R-1` in dispositions, stats, consolidation inputs) | 579 |
| Docstrings | 109 |
| Comments | 73 |

(Token-based count via `tokenize` + `ast`; 725 raw grep hits in total.) Consequences:

- A naive regex lint over the files is **red on ~580 legitimate fixtures**. The lint must tell prose from data, so it has to be token-aware, not line-grep.
- The prose offenders are ~180, concentrated in a few modules (`test_v5_methodology.py` 38 comments, `test_pr_review_payload.py` 12 docstrings, `test_critic_consolidate.py` 8 docstrings, others). The sweep is bigger than "~35" but still mechanical.
- `tests/test_cutover_prose_coherence.py`, `test_prose_severity_ceiling.py` and `test_record_lint.py` show the repo already has prose-lint tests; the new lint should follow their pattern rather than invent a runner.
- The issue also names the header of `tools/evidence-roundtrip.sh`. On this tree the grep finds no id there; confirm during build whether it was already fixed, and keep `tools/` file headers in scope for the lint regardless.

## Goals

- G1. The "review and finding ids never ship" norm is enforced by a test, not by recall.
- G2. The lint is **red on the current tree and green after the sweep** (red-verified, per core.md "a check never seen to return non-zero proves nothing").
- G3. Legitimate uses of the literal (fixture data that is a finding id by design) never need an allowlist entry per occurrence.
- G4. After the sweep, each touched docstring/comment states the present-tense reason the test exists.

## Non-goals

- Assertion, fixture or behaviour changes: the sweep is prose-only.
- Non-test source (`plugin/`): the norm's other homes (commit messages, change-log) are not touched. Whether `plugin/` source deserves the same lint is a separate decision (Q2).
- Ids other than review and finding ids (issue numbers like `#1052` are a different norm; see Q3).

## Requirements

- R1. **Token-aware classification.** The lint scans `tests/**/*.py` (excluding `tests/fixtures/`) with `tokenize` and `ast`: it flags matches only in **comments and docstrings**, never in ordinary string literals. This is what makes G3 hold without an allowlist for 579 fixtures.
- R2. **Pattern.** `\b[RO]-\d+\b` and `rev-\d{8}T`. The pattern is one constant in the lint module with a test that it matches the shapes the norm names (`R-8`, `O-3`, `rev-20261025T…`) and does not match near-misses (`CR-8`, `PRO-12`, `R-` alone).
- R3. **`tools/` headers.** File-header comment blocks of `tools/*` (Python and shell) are scanned with the same pattern. Shell files are scanned as comment lines only (`#` lines), since there is no tokenizer for them.
- R4. **Allowlist with a reason per entry.** A file/line-independent entry (path + the offending text) with a mandatory reason, for a docstring that needs the literal because it documents the id *format* (for example a test of this lint, or a test of the dispositions id grammar). An entry without a reason fails the lint. Stale entries (no longer matching anything) fail the lint, so the list cannot rot.
- R5. **Failure message names the repair.** Each hit reports path, line, the matched id and one sentence: "carry the present-tense reason this test exists; history lives in commits and the change-log".
- R6. **Red-first.** The lint lands in its own commit and is run against the unswept tree to show it fails with the expected count (~180) before the sweep commit. The red run's count is recorded in the commit message.
- R7. **Sweep is one prose-only commit.** It rewrites each flagged docstring/comment. Verification that it changed no behaviour: the AST of every touched file with docstrings and comments stripped is identical before and after (a one-off script, not shipped), plus the full suite green.
- R8. **Sweep rewrites, does not delete blindly.** Where a docstring is only a review id plus history ("R-8/R-13: the rule is …"), the replacement keeps the rule and drops the id. Where nothing but history remains, the docstring is removed, not left empty.
- R9. **Comment-vs-fixture ambiguity.** A comment that explains *which fixture id plays which role* (e.g. "R-1 is the blocking one") is legitimate data documentation, not history. The lint cannot tell these apart mechanically, so the rule is: a comment inside a test that builds findings may name the fixture ids it uses, via an allowlist entry per file (R4) with the reason "documents fixture ids", not one per line. See Q1.

## Acceptance

- [ ] Lint test exists, follows the existing prose-lint pattern, and fails on the pre-sweep tree with the recorded count.
- [ ] A seeded negative case: a temporary comment containing `R-8` in a scratch test makes the lint fail (proves the instrument can return non-zero).
- [ ] A seeded positive case: the same id inside an ordinary string literal does not fail it.
- [ ] After the sweep: lint green, full suite green, comment/docstring-stripped AST of every touched file unchanged.
- [ ] Allowlist entries each carry a reason; a stale or reason-less entry fails.
- [ ] `building.md` norm sentence points at the lint as its enforcement (one clause), so the norm and the check are described together.

## Open questions for the owner

- **Q1.** Fixture-role comments (R9): allow per-file with a shared reason, or require rewording them to avoid ids (e.g. "the blocking finding")? Allowing is cheaper; rewording makes the lint a pure no-exception check. Recommendation: allow per file, because the ids there are data the reader must be able to cross-reference.
- **Q2.** Extend the same lint to `plugin/**/*.py` comments and docstrings now, or ship tests-only first? The norm is stated for all code. Recommendation: tests and `tools/` now (the measured problem), then measure `plugin/` with the same scanner in report-only mode to size a follow-up.
- **Q3.** Do issue numbers (`#1052`) count as ids that "change under you"? The norm text targets review/finding ids; issue ids are used widely as stable pointers. Recommendation: out of scope here.
- **Q4.** Sizing: the sweep is ~180 sites across ~25 files, not ~35. Keep effort:M with the lint and sweep as two commits, or split the sweep into its own issue so the lint can land first with a temporary allowlist? Recommendation: keep one issue, two commits; a temporary mass allowlist defeats G2.

## Next step

On owner confirmation of Q1 and Q2, write the design: scanner module location, allowlist format, and per-file sweep order (largest offenders first).
