# Audit: develop since v3.4.0 (2026-09-10)

Read-only audit of the 23 release-pending scopes on `develop` (`b4d63cb3`) against `main`
(v3.4.0, `9526ec84`). Five independent auditors, one per cluster of related PRs, each grading
claims against code, test strength, plan completeness, and whether the stated problem is solved.
The full test suite on a clean develop checkout was green (0 failed); the evidence store carries the run.

## Verdicts

| Verdict | Scopes |
|---|---|
| COMPLETE (5) | upstream-intake-repoint · silent-governance-failures · test-location-nested-checkout · delegation · norm-lifecycle-stopgaps |
| COMPLETE-WITH-NITS (16) | critic-mode-field-parse · review-loop-termination · verify-resolutions-exit3 · gate-accuracy · upstream-report-bug · upstream-filing-adapter · backlog-burndown-2026-09 · small-batch-2026-09-02 · silent-clear-checks · release-gate-blindness · manifest-state-diagnosis · pr-evidence-reviewed-commit · pr-issues-backend-close · instruction-surface-truth · release-v3.4.0 · adhoc-delegation |
| INCOMPLETE (2) | backlog-metadata · branch-claim-multiplicity |
| DEFECTIVE (0) | — |

Every scope's tests were confirmed to go red against `main`'s modules and green on develop; no
scope has a fabricated or fixture-only test as its primary guard. The work is real. The pattern
across the nits is consistent: each fix closes the instance it named and leaves the same class
open one frame up, and the durable prose (change-log, docstrings, templates) claims slightly
more than the code carries.

## A. Will block or degrade the next release cut

1. **Plan-archive filename collision (review-loop-termination).** `.prawduct/artifacts/archive/build-plan-review-loop-termination.md` already exists from v3.2.0. `plan_archive.py:391-395` refuses on an existing destination; `plan-backfill --apply` exits 1 (`prawduct-hook:6407-6408`). Rename one before the cut.
2. **branch-claim-multiplicity Chunk 04 unticked.** Its live half (run the develop-track dogfooding recipe on one sibling repo, VRF-017) became runnable 2026-08-27 and was never run. `operator_verification_required: false` means no gate will ever raise it. Until then: `plan-backfill` refuses the plan, and the session briefing prints a wrong remedy every session (both "fix the frontmatter" and "create the branch" are wrong here). One dogfooding session closes all three.
3. **`plugin/CHANGELOG.md` open section is not consumer-ready.** Still leads with the seeded placeholder; names 1 of 23 scopes by slug. Substantively it says nothing about `/prawduct:report-bug` now filing GitHub issues on the product's behalf with a consent row (PRs #766/#769, the one change that crosses the owner boundary), nor about adhoc-delegation's new session-start advisory and `backlog add` prompt. This is the v3.4.0 miss recurring.
4. **Reopen-entry tag convention unspecified.** `scope=release-v3.4.0` (from the reopen commit) carries no `release=`; runbook step 22 gives no rule. The gate will nag it as plan-less at every cut and the archiver files it under whichever version ships next. One sentence in the runbook fixes it.
5. **Version number undecided.** Norm says patch by default (`operational-spec.md:21`); a minor is arguable (new egress capability, new gate refusals, sentinel grading change). Must be written into the not-yet-existing `release-plan-v3.4.1.md`.
6. Slug-match false negatives: `check-releasability` will warn "could not find scope=branch-claim-multiplicity" though the notes exist (`CHANGELOG.md:112-140`).

## B. Real defects in shipped behavior

7. **`file-upstream` files an empty title/body/symptom with no warning, under every consent state.** `cli.py:585-588` checks flag presence, `check_payload_inputs` (`upstream.py:366-398`) bans only newlines/fences, `lint_title("[prawduct] critic: ")` clears the length floor. Under `always-file`, or the same wrong `$(cat …)` path pasted in both calls, an empty public issue lands irreversibly. The report-bug entry names this as uncaught and closes it in prose only. Fix: one whitespace-only refusal in `check_payload_inputs`.
8. **Review budget is silently inert on trunk-based repos, and the docs claim the opposite.** `critic_consolidate.py:1672-1685` intersects scope facts with `count_branch_rounds`, which needs commits in `merge_base..HEAD` (`coverage.py:709-723`); after every push to trunk that set is empty. Docstring, change-log, and `templates/project-state.yaml:439-442` all give the trunk-based case as the reason for the design. Untested.
9. **Opt-in gate flags fail open on an unreadable `project-state.yaml`.** `operator_verification.py:281-283` (`OSError → False`), `core.py:625-630` (`read_bool_yaml_key`, also used for `coverage_required`), `prawduct-hook:4288-4290`. Reproduced: `chmod 000` state file with `operator_verification_required: true` → `check-operator-verification` exits 0 silently. `_load_queue` (`:301-303`) tracebacks on an unreadable/undecodable queue. Same class silent-clear-checks closed, one frame above the frame it fixed, in the same file.
10. Other still-silent checks found by sweep: `buildplan_refs.py:733-736` (unreadable plan reads as finished, and this feeds `resolve_branch_claim`); `prawduct-hook:2905-2961` (Stop hook PR-evidence gate wrapped in `except Exception: pass`); `gitstate.py:517-518, 853-854` (corrupted `.session-git-baseline` = no session changes, commented as deliberate); `gates.py:1170` (incomplete-chunk check returns `False` on any exception); `risk.py:139-142`.
11. **critic-mode-field-parse residual reopens the gate-off case.** The `\.\s+` arm of `_FIELD_DECLARATION_PREFIX_RE` fires after `e.g.`/`i.e.`; reproduced: a Description containing `(e.g. **Type:** designer-handoff)` on a chunk declaring no Type is graded `designer-handoff`, which skips review. Undisclosed in the entry and in `planning.md:201`.
12. **backlog-metadata is INCOMPLETE.** `plugin/templates/backlog.md:51` still reads `closed-by: <chunk-id | scope/branch | tag>` and `init_product.py:58` scaffolds it into every new product. The entry's "all four surfaces" missed the one consumers read first. No test pins any of the wording.
13. **gate-accuracy's `suite_coupled_prefixes` is undiscoverable outside this repo** (absent from `templates/project-state.yaml`, doctor, onboard, docs), so the product-declared design ships inert in every product. Also `core.py:509-514` silently drops malformed block lines, contradicting `read_block_sequence`'s own rule two functions up.
14. Sixth carrier of the cumulative-then-commit promise: `building.md:209` and `pr/SKILL.md:95` still say "land every judgeable fix before the one cumulative run, then commit", but `cumulative` anchors committed HEAD, so an uncommitted fix is excluded, not reviewed.

## C. Record and test integrity

15. **Critic-mode corpus test has two assertions that cannot fail** (`tests/test_critic_mode_inference.py:2536-2569`, `lost` and `noisy`) — the identical inertness commit 28d1bc85 fixed in its Type twin. Rewrite to ask the reader's return value.
16. **Change-log claims a positive control that does not exist** for the cross-call shell-variable pin (`change-log.md:454-456` vs `tests/preferences/test_no_upstream_content_egress.py:1074-1103`).
17. **adhoc-delegation's carried debt was promised to "the next commit touching `norm_probes.py`"; four such commits passed** (2026-09-01) without paying it. `norm_probes.py:1291-1294` and `tests/test_norm_probes.py:955-957` still assert a falsehood; HC#14 route printed twice.
18. **#164's body was not amended after the ruff retirement was reverted.** Criterion still reads "ruff is configured"; no blocked-by #742. `pick` will hand the same retirement to the next agent. Nothing pins ruff in the dev extra.
19. **The hook's own usage banner under-describes two commands the skills rely on**: `ledger-append` lacks `--findings` (`prawduct-hook:6672` vs `ledger.py:147`); `critic-begin` lacks `--chosen-by/--tier/--scope/--chunk` (`:6650` vs `:1679-1682`). Same class instruction-surface-truth closed; the banner was outside its sweep.
20. Entry-accuracy nits: instruction-surface-truth's retry figures at `adapter-mode.md:88-89` are chosen, not "traceable to the transport"; its #178 count is wrong; #729's declared `SCOPE-OUT: reflection.md (G4)` neither discharged nor filed; `onboard/SKILL.md:68` says "two of three answers exit 0" (develop: 0/1/3); `pr/SKILL.md:180` numeric step pointer and `:165` unnamed source list, both accepted-not-fixed through three later PRs; `documentation/project-structure.md:36` pre-rewrite description of `delegation.md`; `documentation/backlog-service-requirements.md:52`; `.prawduct/artifacts/project-preferences.md:99` "no linter configured"; prawduct's own preferences carry no delegation rows; `release_readiness.py:804-823` skips the suite verdict on a Phase 0 re-run with nothing pending (by design, undocumented in the runbook's re-entry paragraph); the stopgap expiry advisory will print 4 rows for 5 entries.

## Upgrade path for a v3.4.0 product

No per-version migration infrastructure exists; nothing runs on the version crossing. Three
behavior changes need product action, documented only in the CHANGELOG section:
`sentinel_command:` must be declared or every `sentinel=` learning reports `ungraded`;
`resolve-base` now prefers `origin/HEAD` when `base_branch:` is unset; `merge=union` is
recommended by advisory, never written. Adequate provided the CHANGELOG is what consumers
read, which makes finding 3 the real upgrade-documentation gap.
