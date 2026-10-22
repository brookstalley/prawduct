---
schema: 1
type: chore
scope: backlog-burndown
date: 2026-10-21
title: A backlog burndown fixes 57 small, ready items and closes 5 stale ones
closes: [brookstalley/prawduct#159, brookstalley/prawduct#187, brookstalley/prawduct#192, brookstalley/prawduct#236, brookstalley/prawduct#285, brookstalley/prawduct#301, brookstalley/prawduct#303, brookstalley/prawduct#304, brookstalley/prawduct#305, brookstalley/prawduct#320, brookstalley/prawduct#322, brookstalley/prawduct#324, brookstalley/prawduct#556, brookstalley/prawduct#560, brookstalley/prawduct#561, brookstalley/prawduct#575, brookstalley/prawduct#577, brookstalley/prawduct#578, brookstalley/prawduct#613, brookstalley/prawduct#624, brookstalley/prawduct#657, brookstalley/prawduct#695, brookstalley/prawduct#706, brookstalley/prawduct#707, brookstalley/prawduct#718, brookstalley/prawduct#719, brookstalley/prawduct#731, brookstalley/prawduct#741, brookstalley/prawduct#749, brookstalley/prawduct#750, brookstalley/prawduct#754, brookstalley/prawduct#763, brookstalley/prawduct#778, brookstalley/prawduct#780, brookstalley/prawduct#781, brookstalley/prawduct#785, brookstalley/prawduct#786, brookstalley/prawduct#796, brookstalley/prawduct#822, brookstalley/prawduct#823, brookstalley/prawduct#836, brookstalley/prawduct#846, brookstalley/prawduct#860, brookstalley/prawduct#870, brookstalley/prawduct#911, brookstalley/prawduct#917, brookstalley/prawduct#929, brookstalley/prawduct#953, brookstalley/prawduct#962, brookstalley/prawduct#968, brookstalley/prawduct#997, brookstalley/prawduct#999, brookstalley/prawduct#1002, brookstalley/prawduct#1008, brookstalley/prawduct#1013, brookstalley/prawduct#1014, brookstalley/prawduct#1033]
---
A ROI-ordered burndown of the ready backlog, done 2026-10-21. Triage agents checked all 160 open
items against develop. Implementation agents built the small ones in isolated worktrees, ran only
their own test files, and were integrated here, where the full suite ran once.

Closed directly as no longer applicable: #1012 (the fragment record shipped), #783 (no `release=`
tag left to give a convention), and #609, #610 and #611 (their premises live only on the
three-month-stale `feature/upstream-dependency-policy` branch).

Integration surfaced one methodology gap, fixed here: a worktree delegate's branch is cut from
the repo's default branch, not the coordinator's, so all ten first-wave delegates started on the
v3.7.1 release. `delegation.md` now says a gitflow delegate resets onto the integration branch
first.

### Fixed
- #159: migration-scrub records a survey baseline date and re-derives the unsurveyed set at Step 3
- #187: the session-boundary prose pin also catches "auto-cleared" and "at session start"; red on both motivating sentences
- #192: norms.md: correctness never waits on an opt-in command; only SessionStart/UserPromptSubmit/Stop/SubagentStop are always-run; coverage-status layer-2 remedy reworded
- #236: security model documents the Actions env wiring the SEC-5 fork-PR guard reads
- #285: janitor theme taxonomy moved to skills/janitor/themes.md; Step 2.5 findings are read-only NOTEs Step 7 acts on
- #301: retired the Type: trivial stop-hook gate (file-set + rationale checks) per owner ruling; trivial stays a Critic declaration; missing rationale is a Critic WARNING
- #303: removed inert stamp-merged and regen-views and the parser's chunks= special-casing, per owner ruling
- #304: the session Critic gate fires on session work already committed (reads gates.session_work_span, the reflection gate's span), not porcelain; briefing reads the same span
- #305: briefing names newer-plugin review evidence and errored verdicts instead of "not recorded"; plan-end synthesis reads this worktree+branch's latest review
- #320: backlog_archive_scope stamped at cutover; info advisory backlog-archive-deferred while the archive is deferred
- #322: update --stage warns when body prose still describes the old stage
- #324: boundary-patterns.md names the four session-file registry sites and the parity test guarding each
- #556: evidence gains a changes_unreferenced bucket; "green is evidence" fires on new code no test mentions
- #560: Stop gives a non-blocking HANDOFF NOTE advisory when judgeable code changed under an active plan and .handoff-notes.md is empty/missing (user channel at exit 0, model only when another gate blocks)
- #561: product-code detection classifies by exclusion; an unlisted language no longer reads as an empty repo
- #575: tests cover the remaining sentinel branches in release_verification
- #577: a lint test catches invalid ordered-list markers in plugin and artifact markdown; fixed five live sites
- #578: a gh timeout in release verification names the 15s ceiling and says it is transient
- #613: import re-run retitles a matched PFX issue in place to the corrected parse
- #624: refresh-counts is allowed from an ephemeral worktree (its snapshot lives in the shared git dir); refusal reason no longer false
- #657: the Status-roster predicate moved into plan_index; core no longer reaches into buildplan_refs
- #695: building.md Test Discipline teaches "green is evidence only about what could have made it red" before tests are written
- #706: Critic Goal 2 warns when a declared Exposed API surface is missing from the contract artifact; planning.md states the author rule
- #707: the grants test sweeps every bundled instruction file beside a SKILL.md against its governing grant (pr/review-protocol.md against the pr-reviewer agent); exemptions carry reasons
- #718: api-contract.md classifies project-state keys as a supported-not-stable consumer surface
- #719: onboarding asks for release_version_files or records why not; concerns registry row for product-declared toolchain invocation
- #731: gates.BLAST_RADIUS_CHECK joins the blocking NEXT-ACTION close: check the fix's blast radius before the fix commit
- #741: deleted the unconsumed #644 conformance functions and their tests
- #749: cache.STORE_SIDECARS; cache tests tolerate -wal/-shm sidecars (not red-verifiable without sqlite 3.51.0)
- #750: conftest warns loudly when pytest runs outside the repo .venv (silent in CI or with PRAWDUCT_ALLOW_ANY_PYTHON)
- #754: a ref read from an issue body resolves only when fully qualified (ids.normalize_stored_ref, no default repo); get now agrees with cache-query resolve
- #763: upstream source-key hashes the rendered title+body only; submitter identity removed, so the key no longer confirms a guessed submitter repo
- #778: a field marker after e.g./i.e./cf./viz. no longer binds as a declaration
- #780: suite_coupled_prefixes hinted in the template and documented; an unreadable declaration couples every path instead of dropping a root
- #781: the lost/noisy Critic-mode corpus checks call the real classifier, so they can fail; coverage-algebra corpus labels are asserted
- #785: the norm-health advisory states its Health Check route once; false "unrendered" comment fixed
- #786: usage banner lists the flags skills instruct; a test derives each flag set from the parsers
- #796: the norm-index scaffold reader reports the read failure's real cause
- #822: one _deliver_stop_advisories runs at every cmd_stop exit: stderr under ADVISORIES at exit 2, systemMessage only at exit 0 (no false additionalContext)
- #823: deleted risk.has_product_risk_declaration and its orphaned helper
- #836: get/list/update return updated_at/created_at so the CAS guard (--if-updated-at) has its token
- #846: five surfaces stop promising a test report lasts the session; contract says a subset run overwrites a whole-suite report
- #860: chmod(0o000) fixtures carry a non_root marker that skips under root; a guard test enforces the marker
- #870: release-process.md: a dev-track version bump rides the work PR, never a PR of its own
- #911: short-plan deferral credits a review to a chunk only when a dispatch supplied that chunk id; Status-derived fallback removed
- #917: a probe that cannot look (returns None or raises) holds its type's open advisories instead of resolving them
- #929: an empty-valued key in a prawduct block opens a YAML list instead of warning per line
- #953: oversized-evidence-store advisory (stat-only, 50 MB default, evidence_store_threshold_mb); evidence status shows size per kind
- #962: test checks every --json subcommand documents its key set in api-contract.md; documented aggregate-stats and change-record
- #968: block-list and nested state readers (lib + hook mirror + coverage probe) strip comments quote-aware; a quoted # survives
- #997: pytest uses --timeout-method signal and --max-worker-restart 0, so a hung test fails instead of stalling the run at 99%; config pin test
- #999: one shared note tells a chunk that ships as its own PR to declare Critic mode: cumulative (rationale, Stop warning, planning.md, template)
- #1002: base-advance transfer "unavailable" names the unreadable tree objects and how to supply them
- #1008: test-evidence record warns, naming untracked non-ignored judgeable files a review cannot cover
- #1013: comment/update/status/link/unlink refuse foreign-target when the resolved target (and the fetched issue's actual repo) is not this repo's own tracker; fails closed
- #1014: import preflights facet label length (50) before the first write and refuses the set, naming offenders
- #1033: a withheld release row can name an Issues blocker (#N / owner/repo#N), checked open/closed through the local backlog cache; unverifiable is never releasable

### Partly done
- #95 (stays open): review-cycle.md documents programmatic invocation (docs half); code half (critic-begin --out-of-band etc.) left open
- #787 (stays open): six nits fixed; left: preferences delegation rows (owner policy), reflection.md G4 scope-out, stopgap advisory key collapse
- #856 (stays open): tests pin that build-plan key spellings cannot switch off the Critic/reflection gates at stop; the state-key-is-only-plan-source case is left for the owner
- #806 (stays open): items 1-2 (git-failed reason, push_remote tie-break pin); item 3 (route gitstate subprocess calls through _git_text) left

## Consumer note
- The `Type: trivial` Stop gate is retired. `trivial` remains a chunk type the Critic reviews: a
  rationale the diff contradicts blocks, and a missing one is a warning.
- `stamp-merged` and `regen-views` are removed. Both had been inert no-ops and were never
  registered in a shipped `hooks.json`, so nothing that ran them did anything. That is why this
  removal ships outside a major release.
- Backlog writes by id (`comment`, `update`, `status`, `link`/`unlink`) refuse a target that is not
  this repo's own tracker (`foreign-target`), as `file` already did.
- New advisories: a missing handoff note under an active plan (at Stop), an oversized evidence
  store, and a deferred backlog archive. A Stop that blocks now also prints the non-blocking
  advisories.
- The session Critic gate now sees work the session already committed, not only uncommitted work.
- A release plan's `withheld` row may name an Issues blocker (`#N` or `owner/repo#N`).
- A short plan's Stop gate credits a review to a chunk only when the review was dispatched for
  that chunk, so a Stop can now ask for a chunk review it used to waive.
- A short `repo#N` stored in an issue body (such as `superseded_by`) no longer resolves; stored refs
  must be fully qualified (`owner/repo#N`).
- `import` refuses the whole set before writing when any facet label is over 50 characters, and
  names each offender.
- Product-code detection works by exclusion, so repos in languages that were not listed before
  (C#, PHP, TSX and others) now get the product-code nudges.
