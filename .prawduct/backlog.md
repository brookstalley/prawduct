# Backlog — prawduct

<!-- Structured backlog (format v2). Managed via the /backlog skill.
     Each item: an ID line + a backticked metadata bar + optional free-form body.
     Sections: ## Open (pickable) · ## Promoted (in an active build plan) · ## Archive (shipped/dropped).
     Items move between sections only via explicit `/backlog update` calls. -->

## Open

- **[CRT-4B7X]** critic-consolidate concurrency — two near-simultaneous SubagentStop firings each write a `review.critic` ledger line (duplicate telemetry)
  `effort: S · impact: S · area: critic · source: critic · added: 2026-07-09 · status: open · stage: ready · related: CRT-9K7T, TEL-2B6K · refs: .prawduct/.governance-ledger.jsonl`

  Two near-simultaneous SubagentStop firings can both pass the completeness check and each write a `review.critic` ledger line — a duplicate telemetry entry. Correctness and gates are unaffected (the findings file is single-slot and check-cumulative reads newest-first); only review-stats double-counts. Fix-shape: a lightweight lock / rename-guard around the consolidate merge so exactly one firing wins. Surfaced by the critic-persistence-redesign cumulative review (NOTE). (critic)

- **[COV-2P7F]** Unify the "`.prawduct/**` is governance-metadata, not code" predicate across ALL PR fast-paths (not just `.md`)
  `effort: M · impact: M · area: coverage · source: user · added: 2026-07-09 · status: open · stage: design · related: CRT-5D8Q, COV-5H3N, COV-8R2K, PR-5K8D · refs: lib/gates.py (_record_covers_head, _compute_verify_resolutions_scope), lib/coverage.py (cmd_check_pr_doc_only), bin/prawduct-hook, incoming-bugs/archive/2026-06-13-governance-metadata-fix-triggers-full-code-pr-gates.md`

  Triaged from incoming bug incoming-bugs/archive/2026-06-13-governance-metadata-fix-triggers-full-code-pr-gates.md (hallucinote, prawduct v2.1.4). "Docs" is defined as `.md`-only across the fast-paths, but governance STATE lives in `.prawduct/*.yaml` too — so editing the governance metadata that DRIVES the gates is treated as editing the product the gates protect. A `.prawduct/`-only maintenance branch (e.g. a one-line active_build_plan pointer fix in project-state.yaml + some `.prawduct/*.md`) fails check-pr-doc-only (not-doc-only on any non-.md file), re-stales the cumulative critic (the "docs changed since review" allowance is .md-only), requires a change-log entry, and forces a full test re-run + a second Critic pass — all disproportionate to a metadata edit.

  This is the UMBRELLA requirement none of our existing scattered items state as one: (1) treat a branch whose entire diff is under `.prawduct/` (state yaml, backlog, change-log, learnings, plans) as governance-only in check-pr-doc-only and the cumulative-critic "changed since" allowance — qualify it for a doc-only / sibling "governance-only" fast-path and don't re-stale a cumulative; (2) don't require a change-log entry for a `.prawduct/`-only branch; guard: keep skills/, methodology/, templates/, root CLAUDE.md classified as code (behavioral logic), exactly as the existing doc-only bound list already does. Related existing items: the metadata-exemption-boundary item (CRT-5D8Q — the two gate helpers _record_covers_head vs _compute_verify_resolutions_scope disagree on the `.prawduct/` boundary), COV-5H3N (gitflow base), and the coverage-floor-on-config item (COV-8R2K); PR-5K8D is the inverse (exclude skills/ from doc-only, i.e. keep governance CONTENT classified as code). This item is the consolidating parent; the boundary item (CRT-5D8Q) is a specific sub-fix. Governance-protected (lib/gates.py, hooks) → full Critic + PR review.

- **[BRF-6K2D]** Session-briefing "delete the plan" nudge isn't merge-aware — fires on develop while the plan's feature branch is unmerged
  `effort: S · impact: M · area: briefing · source: reflection · added: 2026-07-09 · status: open · stage: ready · related: STH-3K7M, STH-3R8K, DOC-5T8N`

  The session-briefing / stale-plan nudge recommends deleting build-plan.md when all its chunks are checked complete. But build-plan.md is gitignored/session-local and persists across branch switches, so the nudge can fire while the session is on `develop` even though the plan's feature branch is still unmerged with no PR open. Following it would orphan live, unshipped work. Reported by discodon (2026-06-11, pre-2.3.0). Fix-shape: make the staleness check branch/merge-aware — before recommending deletion, confirm the plan's feature-branch commits are actually reachable from the integration branch (or its PR merged), e.g. `git merge-base --is-ancestor <plan-branch-tip> <base>`; otherwise say "plan complete but branch not yet merged — keep until merged" rather than "delete". Source: discodon reflection sweep 2026-07-09.

- **[STH-4B7Q]** check-operator-verification gate reportedly throws ModuleNotFoundError (needs repro)
  `effort: S · impact: M · area: stop-hook · source: user · added: 2026-07-09 · status: open · stage: idea · related: STH-2J9F, STH-8M3V`

  hallucinote reported (recorded 2026-07-04, incidents May–June) that the check-operator-verification gate hook throws ModuleNotFoundError across 6+ PRs, and that the failures were never escalated upstream (carved around instead of fixed). Needs-verification: a quick check of bin/prawduct-hook's lazy `from lib import ...` pattern did not confirm the exact failing import path or whether this reproduces on current v2.3.0 (the operator-verification surface was reworked in v2.0.0 Chunk 13, so this may be stale or environment-specific — e.g. a broken/partial install where lib/ is unresolvable). Stage: idea pending a clean repro. Fix-shape (if confirmed): correct the import path / fail loud with an actionable install-repair message rather than an opaque ModuleNotFoundError. Source: hallucinote reflection sweep 2026-07-09. (user)

- **[BKL-7M4Q]** `/prawduct:backlog` mutation is not crash-safe or idempotent — partial file mutation on mid-run crash + duplicate paragraphs emitted
  `effort: M · impact: M · area: backlog · source: critic · added: 2026-07-09 · status: open · stage: ready · related: STH-9T4F, STH-8M3V · refs: skills/backlog/SKILL.md, .prawduct/backlog.md`

  The forked /prawduct:backlog skill mutates backlog.md non-atomically. Two corroborating incidents in hallucinote: (a) the skill died on an API socket error mid-run and left a PARTIAL file mutation — data corruption, not a clean rollback; (b) a Critic (2026-07-07) found a DUPLICATED paragraph the skill had emitted (non-idempotent write). Impact: a mid-run crash or retry can corrupt or duplicate backlog entries — the very tool meant to be the safe mutation path for the backlog is itself unsafe. Fix-shape: make backlog mutations transactional and idempotent — parse the file to a model, transform by item id, assert no duplicate ids / no dropped items, then write atomically (temp file + rename). Governance-protected (skill) → full Critic + PR review. (critic)

- **[PR-7T2K]** PR gates validate local HEAD, not the pushed origin/<branch> that squash-merge uses — post-push commits silently dropped
  `effort: M · impact: M · area: pr · source: user · added: 2026-07-09 · status: open · stage: ready · related: PR-2H8N`

  The PR gates (change-log entry, cumulative-critic, evidence) validate the LOCAL commits, but `gh pr merge --squash` squashes what's on origin/<branch>. A commit made after the last push — very often the change-log entry the gate itself just forced the builder to add — never reaches origin, so the squash-merge silently drops it and the merged result is missing content the gates confirmed present. Reported by hallucinote (~June). Fix-shape: /prawduct:pr (or a PR gate) should assert `git rev-parse origin/<branch>` == local HEAD (branch fully pushed) before allowing merge, and fail loud with "unpushed commits — push before merging" otherwise. Governance-protected → full Critic + PR review.

- **[CRT-5D8Q]** PR-gate coverage vs verify-resolutions scope disagree on the metadata exemption — deadlock when the ledger fallback window has lapsed
  `effort: S · impact: M · area: governance/critic-gate · source: critic · added: 2026-07-02 · status: open · stage: ready · related: CRT-8H3R, CRT-2K9F, CRT-4J8W, STH-6T9W · refs: lib/gates.py (_record_covers_head L972, _compute_verify_resolutions_scope L447)`

  The two gate helpers draw the `.prawduct/` metadata-exemption boundary differently. `_record_covers_head` exempts only `.md` files, so a routine post-cumulative `.prawduct/*.yaml` change (e.g. repointing `active_build_plan`) marks the cumulative record stale. But `_compute_verify_resolutions_scope` exempts ALL `.prawduct/` metadata, so the demanded verify-resolutions pass returns "no-actionable-findings" and the SKILL's literal demotion to `final` yields a non-gate-qualifying record — deadlock when the ledger fallback window has lapsed. Fix-shape: make the two helpers agree on the metadata-exemption boundary. Observed live 2026-07-02 on feature/changelog-fail-loud (Critic hand-anchored a chain record to route around it). Governance-protected (lib/gates.py) → full Critic + PR review. (critic)

- **[COV-4M2J]** Coverage floor is Python-only — `bin/test-reference-verify` symbol-grep can't reference non-Python (JS/TS/Go/…) changed files; bring-your-own-verifier via `--merge-into` is the only escape
  `effort: L · impact: M · area: coverage · source: builder · added: 2026-06-26 · status: open · stage: requirements · related: COV-3R9K, COV-8R2K, TST-2H9P · refs: bin/test-reference-verify (symbol-grep floor), lib/coverage.py (changed-files derivation), bin/prawduct-hook (verify-coverage, test-evidence record F4a overlay), skills/critic/review-cycle.md (Goal 1 F4b)`

  Split from COV-3R9K during the test-evidence-single-run work (build-plan-test-evidence-single-run.md, Chunk 03 — the user's "add `--from-counts`, backlog the floor" choice). COV-3R9K closed the RUN-half of the test-evidence double-run; this is the residual coverage-FLOOR gap.

  The F4a coverage floor — `bin/test-reference-verify`'s symbol-grep that populates `changes_referenced` — only understands Python symbols. On a polyglot or non-Python repo (vitest JS/TS, Go, Rust, embedded), changed source files yield an empty/honest `changes_referenced` half (no false regression today because `coverage_required` defaults OFF), but there is NO working coverage floor for those languages — the framework's "the tests actually referenced the changed code" guarantee is Python-only. Current escape: bring-your-own-verifier — a product writes its own reference output and feeds it via `bin/test-reference-verify --merge-into` (the same seam TST-2H9P exposed for monorepo tests-dir). The residual is a language-agnostic / pluggable coverage floor so non-Python products get the guarantee without hand-rolling a verifier.

  Needs a requirements/design pass (stage: requirements). Open question is the plug-point: a declared per-language verifier command (project-state knob) vs a built-in multi-language symbol grep vs ingesting native coverage-tool output (lcov / cobertura). Adjacent to COV-8R2K (make the floor file-type/language-aware for non-executable files) — both are "make the floor smarter about what it's inspecting." effort/impact are preliminary (sized at the split; confirm during design). Governance-protected (bin/, lib/) → full Critic + PR review. (builder)

- **[CRT-4Q7K]** Coded auto-detect variant of the `**Exposed API:**` Critic trigger — fire the versioning/error-model Goal-2 check on API-exposing chunks even when the author didn't declare it
  `effort: M · impact: M · area: critic/governance · source: user · added: 2026-06-24 · status: open · stage: idea · related: SEC-4Q7H, GOV-9K2T · refs: .prawduct/cross-cutting-concerns.md (Known Gaps), templates/api-contract.md, skills/critic/review-cycle.md (Goal 2)`

  Deferred follow-up from the api-design feature (cross-cutting-concerns.md Known Gaps). Today the API versioning / error-model Goal-2 Critic check fires only when a chunk author declares `**Exposed API:** <name>` in the build plan — an opt-in trigger mirroring the existing Foreign-API convention. A stronger guarantee would AUTO-DETECT API-exposing chunks from boundary-patterns globs / code (the surfaces a chunk actually touches) so an undeclared chunk still gets the versioning/error-model check, closing the "author forgot to declare it" hole. ENHANCEMENT, not a gap in shipped coverage — the opt-in path works; this hardens it against omission. Idea-stage: needs a design pass on the detection signal (boundary-patterns globs vs diff inspection) and its false-positive posture before it's buildable. Governance-protected (skills/critic) → full Critic + PR review. (user)

- **[TPL-8H3M]** Standalone error-model artifact/template — extract the error-envelope decision from api-contract.md if error-model design grows
  `effort: M · impact: M · area: templates/artifacts · source: user · added: 2026-06-24 · status: open · stage: idea · related: CRT-4Q7K · refs: .prawduct/cross-cutting-concerns.md (Known Gaps), templates/api-contract.md, .prawduct/project-state.yaml (design_decisions.api_error_model_approach)`

  Deferred follow-up from the api-design feature (cross-cutting-concerns.md Known Gaps). Today the error-model decision lives INSIDE templates/api-contract.md plus the `design_decisions.api_error_model_approach` project-state block. A DEDICATED error-model template/artifact may be wanted if error-envelope design grows in importance (richer error taxonomies, machine-readable problem-details, per-surface error contracts). ENHANCEMENT, not a gap in shipped coverage — the embedded form covers today's needs; extract only when the design surface earns its own artifact. Idea-stage: the trigger is "does error-model design grow?" — re-derive the requirement (what the standalone artifact must capture beyond the embedded block) before any template work. (user)

- **[DOC-5T8N]** Self-document the build-plan Status "derived view" behavior in templates/build-plan.md to prevent hand-editing confusion
  `effort: S · impact: S · area: templates/docs · source: user · added: 2026-06-24 · status: open · stage: idea · related: VWS-4D8J, CRT-3D9K, CRT-4Q7K, TPL-8H3M · refs: templates/build-plan.md, lib/views.py (extract_status_section, regenerate_status_section), .prawduct/change-log.md`

  Sibling to the named-but-dropped / derived-view learnings from api-design. Problem: when project-state has `views_enabled: true`, a build-plan `## Status` block is a DERIVED view of change-log `status=shipped|merged` tags (regen-views flips checkboxes at merge/release), so `[ ]` on a feature branch is correct, not a forgotten update — but nothing in the plan doc itself says so, and a session that "fixes" the checkboxes by hand has its edits silently overwritten by regen-views (happened during the api-design build: hand-flipped chunks 01/02 to `[x]`, regen-views reset them).

  Fix-shape: add a short explanatory HTML comment to templates/build-plan.md explaining that when `views_enabled` the Status is derived (don't hand-edit; flip via change-log status tags + regen-views; checkboxes track merge/release, dev-progress lives in the Context line). Make it conditional-aware — a repo WITHOUT `views_enabled` hand-maintains the checkboxes.

  Placement nuance (verified against lib/views.py): put the comment ABOVE the `## Status` heading (or in the template's top comment block), NOT inside the Status section body — `extract_status_section` (lib/views.py) spans from the `## Status` line to the next `## ` H2 and `regenerate_status_section` rewrites that block, so a comment placed inside it would be clobbered.

  Idea-stage: a small DX self-documentation fix, but confirm the exact comment text and placement against the current views.py extraction bounds before writing. (user)

- **[SEC-4Q7H]** Audit auth/authz as a holistic cross-cutting concern — confirm coherent pipeline coverage across ALL surfaces, not fragmented per-surface
  `effort: M · impact: M · area: governance/security · source: user · added: 2026-06-24 · status: open · stage: research · refs: .prawduct/cross-cutting-concerns.md (Security + Data-privacy rows), build-plan-api-design.md, skills/critic/review-cycle.md (Goal 1 auth completeness), templates/ (security-model artifact)`

  Surfaced during the api-design cross-cutting work (build-plan-api-design.md), where API auth was deliberately NOT duplicated into the API-design concern because auth belongs to the Security pipeline (Security + Data-privacy rows in cross-cutting-concerns.md; Critic Goal-1 auth completeness; security-model artifact). This audit verifies that placement is sound: trace auth/authz across the FULL pipeline (discovery structural detection → security-model artifact → builder guidance → Critic checks) and confirm it is treated coherently across ALL surfaces (API, human-interface, multi-party, unattended) rather than ad-hoc per surface.

  Look specifically for: object-level authorization / BOLA (OWASP API Top 10 #1) coverage; session vs token models; multi-party trust-boundary enforcement; and whether the security-model template prompts auth decisions strongly enough.

  Outcome: either confirm coverage is sound or identify the gaps (likely a follow-on to the api-design work). Research-stage — this is an audit/investigation, not yet a buildable task; route to discovery to advance the stage. (user)

- **[COV-5H3N]** resolve-base ignores origin/HEAD and defaults to main on gitflow repos — silent wrong-base inflates review scope and misroutes PR bookkeeping + build-plan lifecycle
  `effort: M · impact: M · area: coverage · source: user · added: 2026-06-22 · status: open · stage: design · related: PR-2H8N, REL-7P3X, MIG-6B0R · refs: lib/coverage.py (_resolve_base_branch, _DEFAULT_BASE_CANDIDATES), lib/migrate_plugin.py, skills/onboard, incoming-bugs/archive/resolve-base-ignores-origin-head-defaults-to-main-on-gitflow-repos.md · reviewed: 2026-07-10`

  When base_branch: is unset in project-state.yaml, _resolve_base_branch falls back to the hardcoded candidate list (origin/main, main, HEAD~1) and returns the first that resolves — even when the repo's declared default branch (origin/HEAD) is develop. The wrong base flows into the cumulative-Critic base, PR-reviewer base, coverage diff, classify-diff-risk, and the stamp-merged guard, so a 2-commit feature off develop is reviewed/gated as the entire develop..main promotion range, and stamp-merged refuses on develop ("integration base is main"), and Merge-Flow step 8 can take the build-plan-DELETE branch for a release-pending merge. Reported v2.1.4 from Discodon; every gitflow consumer hits it on its first PR unless they know the base_branch knob. THIS repo masks it (base_branch: develop is set). Fix-shape (either alone closes most of the gap; both is best): (1) make the default branch-aware — consult `git symbolic-ref --short refs/remotes/origin/HEAD` before the hardcoded list, prefer it when it resolves and isn't main-family (trunk repos with origin/HEAD=main unaffected); optionally warn instead of silently picking main when both a main-family branch and a non-main origin/HEAD exist. (2) set base_branch: at onboarding/migration time when origin/HEAD is non-main, so freshly-migrated gitflow repos start correct. Governance-protected (lib/) → full Critic + PR review.

  **Note 2026-07-10 (single-pr-bookkeeping):** the stamp-merged branch-guard consequence above
  is retired — no flow calls stamp-merged anymore (it is deprecated-but-callable only; hard
  removal tracked as REL-4Q9V). But the item is now MORE load-bearing, not less:
  `/prawduct:pr` create-flow Step 1d branches trunk-vs-gitflow on resolve-base, so a wrong
  default base silently misroutes the PR's change-log bookkeeping (statusless-until-release vs
  shipped-in-PR), on top of the review-scope inflation.

- **[COV-8R2K]** verify-coverage records BLOCKING missing-coverage for non-executable files — prose .md docs AND non-code config (YAML) — forcing waivers or token reference-tests on otherwise-clean chunks
  `effort: M · impact: M · area: coverage · source: user · added: 2026-06-22 · status: open · stage: design · related: TST-4K2P · refs: bin/prawduct-hook (verify-coverage), lib/coverage.py, skills/critic/review-cycle.md (Goal 1 rule F4b), incoming-bugs/archive/verify-coverage-records-blocking-missing-coverage-for-prose-docs.md, incoming-bugs/archive/check-pr-trivial-passes-feature-clusters-that-only-touch-existing-files.md`

  The symbol-grep coverage floor is applied to non-executable files the same as code. Two corroborating reports: (a) a chunk whose deliverables legitimately include a prose .md always produces an unsoftenable BLOCKING missing-coverage (Goal 1 F4b: "a missing-coverage line is recorded BLOCKING per file, never softened"), even though prose can't be executed; (b) a branch editing a YAML/config file with no test symbols (e.g. .prawduct/project-state.yaml) is flagged missing-coverage and verify-coverage exits 1 on an otherwise-clean branch (the "config-file-accounting gap" products already note in their own learnings). A doc-ONLY-chunk skip already exists; this is the MIXED-chunk and non-code-config version. Fix-shape: make the floor file-type/language-aware — exempt (or downgrade to NOTE) files under a docs-path policy (configurable allowlist, e.g. **/README.md, docs/**, *.md) and non-code config, or scope the floor to runner-executable languages only. Governance-protected → full Critic + PR review.

- **[STH-6T9W]** Stop critic-review gate counts untracked operator-authored non-code files as chunk-diff scope — no Critic mode can satisfy it, forcing a waiver on a clean, fully-reviewed tree
  `effort: M · impact: M · area: stop-hook · source: user · added: 2026-06-22 · status: open · stage: design · related: STH-3W7F, STH-7K2A · refs: lib/gates.py (critic-review gate, verify-resolutions scope check; validate_critic_findings files_reviewed), incoming-bugs/archive/stop-gate-counts-untracked-operator-notes-as-chunk-diff.md`

  An untracked operator-dropped non-code file (e.g. a note placed in incoming-bugs/) is counted into the chunk-diff scope, growing it beyond what the verify-resolutions findings cover; the suggested remedy (re-run /critic chunk) can't produce a schema-valid empty-scope record (validate_critic_findings requires non-empty files_reviewed), so a waiver becomes the only exit — on a session whose code was already fully reviewed and merged. Trains waiver-reaching: when the framework's cleanest sessions end in waivers, waivers stop signaling anything. Distinct root cause from STH-3W7F (background work) and STH-7K2A (loop-counter). Fix-shape: exclude untracked non-code files outside source/test/governance roots from the chunk-diff scope; and/or allow a schema-valid scope:empty findings record. Governance-protected → full Critic + PR review.

- **[BLD-5J8N]** verify-chunk-refs can't parse the "## Chunk NN — Title" header style — false "chunk not found" exits habituate reviewers to dismiss a real-BLOCKING-shaped signal
  `effort: S · impact: M · area: critic · source: user · added: 2026-06-22 · status: open · stage: ready · related: BLD-4K7P, BLD-7P3K · refs: bin/prawduct-hook (cmd_verify_chunk_refs), templates/build-plan.md, incoming-bugs/archive/verify-chunk-refs-cant-parse-house-chunk-header-style.md`

  The chunk-header regex only matches the template's "### Chunk 01: [Name]" form; plans using "## Chunk 01 — title" (h2, em-dash) exit 1 "chunk not found" even though the chunk exists, so reviewers learn to hand-wave the exit — and a real missing-deliverable BLOCKING can then hide behind the dismissed exit (false-negative habituation). Distinct from the verify-chunk-refs ref-TOKEN-extraction family (BLD-2R9X glob, BLD-8F2Q path::symbol, BLD-4K7P <>/URL tokens, BLD-5V8F symbol/backlog-ref) — this is the chunk-HEADER detection regex (which chunks exist at all). Fix-shape: loosen header regex to ^#{2,3}\s+Chunk\s+(\w+)\s*[:—–-]; and/or distinguish "cannot parse" from "ref missing" in the exit contract. Same cmd_verify_chunk_refs surface as BLD-4K7P — could ride in one pass. Governance-protected → full Critic + PR review.

- **[WMK-4Q9T]** Work-model term tripwire flags ordinary English words and file-path fragments as ungoverned terms — desensitizes the one tripwire meant to catch real undocumented requirements
  `effort: S · impact: M · area: work-model · source: user · added: 2026-06-22 · status: open · stage: design · related: WMK-7D3R, WMK-1P4Q, GOV-7T2M, GOV-4C7X · refs: UserPromptSubmit hook (work-model term extraction), lib/work_model_index.py, incoming-bugs/archive/work-model-term-tripwire-flags-ordinary-prose-words.md · reviewed: 2026-07-12`

  The prompt-term extractor treats common adjectives/adverbs/verbs and singularized file-path fragments (e.g. "incoming-bug" from incoming-bugs/) as candidate domain terms, firing the "terms not found in any governing artifact" tripwire on most natural-language prompts. Noise PERSISTS as of 2026-06-22 — it fired on THIS very session's prompt ("urgent, wrap-up, awaiting, model-id, fold, single-owner, ceiling, cross-linked…"). Pure noise today, but desensitizes tripwire #1 (requirements-precede-code). WMK-7D3R is the staleness/rebuild sibling and explicitly says probe PRECISION was "separate, covered by the review-fixes plan Chunk 2" — verify whether that precision pass shipped before sizing; the 2026-06-11 Scriob repros + this session's recurrence show the noise is live regardless (so file NEW; if review-fixes Chunk 2 shipped a partial fix, this is the incomplete-fix follow-up). Fix-shape: stoplist/POS-filter to nouns; don't tokenize path-like strings; scope firing to build-intent prompts or recurring terms.

  **Narrowed 2026-07-02 (partial supersession by GOV-7T2M, shipped closed-by=gate-noise):** two
  of the noise classes are now fixed — maintenance verbs (refactor/rename/redesign/rework/
  remove/replace) split into MAINTENANCE_VERBS so review/cleanup prompts are no longer
  requirement-shaped at the single-orphan threshold, and the `docs/`/`methodology/` corpus globs
  are recursive so doc-subdir vocabulary no longer reads as orphaned. (Review-fixes Chunk 2's
  precision pass — the common-English frequency floor, lib/common_words.py — had also shipped;
  the 2026-06-22 recurrence was on top of it.) **Remaining scope:** path-like tokenization —
  `_WORD` (`[A-Za-z][A-Za-z'-]*`, lib/work_model_index.py:71) still extracts hyphenated
  path/compound fragments ("incoming-bug" from incoming-bugs/, "wrap-up", "model-id",
  "cross-linked") as orphan candidates — plus the optional POS/noun-filter and
  build-intent-scoping legs if the tokenizer fix alone doesn't quiet it. Effort re-sized M→S
  to match the narrowed scope.

  **Owner decision 2026-07-12 (kernel-redesign discovery) — resolution is DELETION, not a
  precision fix.** The work-model term tripwire will be deleted outright (the prompt-term
  extractor plus the work-model index machinery behind it), superseding the remaining fix-shape
  legs above (path-tokenization fix, POS/noun-filter, build-intent scoping — all moot).
  Requirements-precede-code enforcement moves to a review-time scope-check question instead
  (cf. CRT-5M9J). Subsumed by the governance kernel redesign program GOV-4C7X, which carries
  the deletion; this item stays open until the deletion actually ships, then archive it
  `closed-by:` the shipping kernel-redesign plan scope.

- **[CRT-6W2N]** Governance gates + Critic/PR skills have no supported git-worktree workflow — the learned "run Critic/PR from the primary session" workaround breaks across working copies, forcing every worktree work cycle off-protocol
  `effort: L · impact: M · area: worktree · source: user · added: 2026-06-22 · status: open · stage: requirements · related: STH-4K7N, CRT-8D2W, CRT-2K9F, REL-7P3X · refs: lib/gates.py, bin/prawduct-hook (infer-critic-mode, check-cumulative-critic, test-evidence), skills/critic, skills/pr, Stop hook, incoming-bugs/archive/governance-gates-and-critic-pr-skills-dont-compose-with-git-worktrees.md · reviewed: 2026-06-22`

  Host repos increasingly MANDATE worktrees for WIP (stable primary checkout served live as a --plugin-dir MCP source), but prawduct has no documented worktree story, so sessions abandon the formal machinery (review via an independent Agent, PR/merge via raw gh), silently skipping the cumulative-Critic record the framework otherwise requires. IMPORTANT reconciliation (verified 2026-06-22 in this framework repo): state-file resolution is NOT actually ambiguous — get_project_dir() deterministically uses the session's CLAUDE_PROJECT_DIR, so a session run ENTIRELY inside one worktree reads/writes that worktree's .prawduct/ consistently and the gates ARE satisfiable in place (empirically confirmed: check-cumulative-critic resolved the worktree's own .critic-findings.json; gitignored runtime files isolate per-worktree). The real gap is therefore (a) NO documented supported worktree workflow, so host repos invented the "run Critic/PR from the PRIMARY session against worktree WIP" rule — and THAT genuinely breaks because the primary's .prawduct/ is a different working copy than the worktree's; and (b) the harness EnterWorktree defaults new worktrees off origin/<default-branch>=main (wrong on gitflow — belongs upstream with the harness, noted not-a-prawduct-bug). Fix-shape (remediation menu): (1) document/own a supported worktree workflow in the methodology — drive the full cycle (code→critic→pr→reflection) from inside the worktree (this WORKS today); (2) worktree-capable critic/pr skills that detect the worktree and review merge-base(base)..HEAD writing the normal record; (3) at minimum, methodology guidance so repos stop reinventing the workaround as private memory. Distinct from CRT-8D2W (inverse: run the Critic in ITS OWN worktree for session-isolation) and CRT-2K9F (worktrees SIDESTEP the single-slot clobber). Adjacent to the gitflow base-resolution item (base resolution vs gate/skill composition). Governance-protected → full Critic + PR review.

  Dedup/reconcile 2026-06-22 (vs STH-4K7N, shipped v2.1.8 / scope=worktree-compat): the
  CODE-RESOLUTION leg this item leans on ("a session run entirely inside one worktree reads/writes
  that worktree's .prawduct/ consistently") is now HARDENED, not merely assumed — STH-4K7N shipped
  `lib.gitstate.resolve_project_dir` so `get_project_dir` follows the session into its worktree
  (`git rev-parse --show-toplevel` of cwd, preferred over the `CLAUDE_PROJECT_DIR` pin only when cwd
  is a same-repo worktree, failing open on git error). That closes the narrow `.prawduct/`-resolution
  defect (STH-4K7N's "Full fix approved"). It does NOT close THIS item: CRT-6W2N's remaining,
  genuinely-open want is the DOCUMENTATION/METHODOLOGY leg — a documented, supported worktree
  workflow (fix-shape 1 & 3) plus optional worktree-capable critic/pr skills (fix-shape 2) — so host
  repos stop reinventing the "run from the primary session" workaround as private memory. Kept OPEN
  at stage:requirements, scoped now to that doc/methodology + skill leg; `related: STH-4K7N` records
  the shipped code dependency it builds on. NOT archived (not a true duplicate — STH-4K7N was the
  code fix, this is the workflow/docs).

- **[CRT-2K9F]** PR-gate ledger fallback should select the newest record that covers HEAD — interleaved Critic→PR cycles silently invalidate the earlier branch
  `effort: S · impact: M · area: critic · source: user · added: 2026-06-22 · status: open · stage: design · related: CRT-8W3F, CRT-4J8W, CRT-7M2D · refs: lib/gates.py (compute_pr_gate, _pr_gate_record_qualifies, _evaluate_pr_gate_record, _ledger_fallback_record), .prawduct/.critic-findings.json · reviewed: 2026-06-22`

  Observed live 2026-06-22 while shipping the review-streamlining track (PRs #101/#102/#103). The cumulative-Critic PR gate (lib/gates.py compute_pr_gate) reads the single-slot .prawduct/.critic-findings.json. When two branches' Critic→PR cycles interleave (run branch X's Critic, then branch Y's Critic, then go to PR branch X), Y's Critic has overwritten the single slot with a record that IS the right KIND (a clean cumulative) but covers Y's HEAD, not X's. compute_pr_gate only falls back to the governance ledger when the slot record is the WRONG KIND (_pr_gate_record_qualifies false); a right-kind-but-wrong-HEAD record goes straight to _evaluate_pr_gate_record, fails the coverage check, and exits 1 — it never consults the ledger, where X's own still-valid qualifying record was appended. This session it forced a needless re-run of budget's Critic after B's Critic clobbered budget's slot.

  Fix-shape: when the slot record fails (wrong kind OR fails HEAD-coverage/chain-scope), fall back to the ledger AND make _ledger_fallback_record select the newest qualifying record whose commit_reviewed COVERS THE CURRENT HEAD (CRT-7M2D coverage semantics), not merely the newest session-fresh qualifying record. The CRT-8W3F session-freshness bound stays.

  Workaround today: finish one branch's full Critic→PR cycle before starting the next branch's Critic.

  Assurance: must not loosen the gate — a record that covers HEAD and is clean is exactly as strong as the slot record would have been; this only stops a sibling branch's clean record from masking this branch's. Governance-protected file (lib/gates.py + skills/) → full Critic + PR review.

  Related: CRT-8W3F (ledger-fallback freshness bound, shipped), CRT-4J8W (verify-resolutions chain record, shipped), CRT-7M2D (covers-HEAD semantics). (user)

  Worktree corollary (verified 2026-06-22): the clobber is strictly a within-ONE-working-tree problem. Each git worktree has its own gitignored .prawduct/.critic-findings.json (and .session-start, .governance-ledger.jsonl), so running each branch's Critic->PR cycle in a separate worktree sidesteps the clobber entirely — no shared single slot to overwrite. That makes worktrees an available workaround and lowers this item's urgency; the in-tree fix below still matters for users who switch branches within one tree.

- **[BKL-8T3W]** Backlog-accuracy structural enforcement — surface cross-session "shipped-but-not-removed" Open items (and stale-by-age) so a ready item isn't rebuilt
  `effort: M · impact: M · area: governance/backlog-tooling · source: user · added: 2026-06-21 · status: open · stage: requirements · related: BLD-4K7P · refs: incoming-bugs/archive/backlog-accuracy-stale-check-hook-plus-closed-but-not-removed-critic-goal.md, skills/critic/review-cycle.md, skills/pr/review-protocol.md, lib/backlog_probes.py`

  ENHANCEMENT (not a defect), needs a design pass before build — file at stage=requirements. Recurring
  drift: a `stage: ready` Open item (or its headline sub-claim) is shipped by OTHER, already-merged
  work and never reconciled, so the next picker rebuilds shipped work or does archaeology. Evidence: 3
  ready items in one Hallucinote session were 60–100% already shipped. Upstream report from
  Hallucinote/puzzles.

  Three CONSTRAINTS for whoever builds this (the review already mapped the overlap — scope to the
  DELTA, don't rebuild):
  1. Most of the proposal already exists — EXTEND, don't duplicate: the Critic's Backlog
     Reconciliation (skills/critic/review-cycle.md:137, final+cumulative) already does the SEMANTIC
     "this session's changes resolve an open item → NOTE archive"; the PR reviewer's R-2
     (skills/pr/review-protocol.md:58, WARNING) already flags a diff referencing closes:/closed-by: PFX
     while the item is still open; lib/backlog_probes.py's backlog-overdue-grooming advisory + the
     /prawduct:backlog summary already do age/stale. The proposed (b) Critic "closed-but-not-removed"
     goal is NOT the inverse of (a) — it largely duplicates review-cycle.md:137.
  2. The genuine UNCOVERED gap is CROSS-SESSION drift: an item resolved by work that merged on a PRIOR
     branch/session — the per-session Critic reconciliation structurally can't catch it. A
     periodic/briefing-level scan of all Open items vs recently-merged work (the report's part (a)(2))
     is the real value. Keep it ADVISORY (briefing/NOTE), never blocking.
  3. The proposed keyword/headline-grep matching is the WEAK part — high false-positive risk, the exact
     BLD-4K7P over-matching family. Prefer high-precision signals (an item's named files/functions from
     its refs/body), NOT headline keywords. The existing SEMANTIC reviewer check is more precise than
     grep for this. Consider a cheaper high-ROI partial first: a `pick`-time "this ready item may
     already be shipped — grep the code/changelog first" nudge, which catches the drift at the moment it
     costs money.

  related: BLD-4K7P (keyword-grep over-match lesson), backlog-overdue-grooming probe. (user — upstream
  report from Hallucinote/puzzles)

- **[REL-3M7K]** Release-prep must add the root CHANGELOG.md headline and gate on a green suite before tagging
  `effort: S · impact: M · area: governance/release · source: builder · added: 2026-06-21 · status: open · stage: ready · related: REL-9F2T · refs: CHANGELOG.md, hooks/banner.py (parse_changelog), skills/pr/SKILL.md, .prawduct/release-notes.md`

  Root cause found 2026-06-21 during the hook-cli-robustness baseline check: v2.1.6 was tagged +
  version-bumped (81b28fe) but its consumer-facing root CHANGELOG.md headline was never added — the
  prep commit updated .prawduct/release-notes.md and .prawduct/change-log.md but missed root
  CHANGELOG.md. That left develop RED on
  tests/test_plugin_version_banner.py::test_changelog_has_current_version_entry (PLUGIN_VERSION 2.1.6
  absent from CHANGELOG.md) since the release, i.e. v2.1.6 shipped on a red suite.

  Two gaps: (a) release-prep updates the .prawduct views but not root CHANGELOG.md, so the
  consumer-facing headline is hand-step-only and was forgotten; (b) the release tagged without a
  green full suite, or CI does not gate tagging. Symptom already repaired (headline added in
  024bf53, sourced from release-notes.md v2.1.6 block).

  Fix-shape: wire the CHANGELOG.md headline into the /prawduct:pr release-promotion / release-prep
  flow (or generate it from the release= change-log tag like release-notes.md is), and make
  release-prep refuse to bump/tag on a non-green suite. (builder)

- **[STH-3K7M]** Capture `git branch --show-current` once on the SessionStart (clear) hot path
  `effort: S · impact: S · area: stop-hook · source: builder · added: 2026-06-21 · status: open · stage: ready · related: STH-6Q9D · refs: lib/briefing.py (_get_current_branch and its callers)`

  `_get_current_branch` (lib/briefing.py) is invoked redundantly on the SessionStart (clear) hot
  path — measured 4× during STH-6Q9D. The redundancy spans three separate briefing functions:
  `staleness_scan` (~L160), `assemble_session_briefing` (~L455), and `_parse_wip` (~L246
  auto-detect). So "capture once" is a cross-function thread (compute in `cmd_clear` or the briefing
  entry and pass the branch down), unlike STH-6Q9D's three local targets — which is why it was left
  out of that chunk. Same fan-out theme as STH-6Q9D (shipped hot-path-git-batching). (builder)

- **[STH-3R8K]** Surface a one-line signal when `get_project_dir` redirects `.prawduct/` resolution to a worktree toplevel
  `effort: S · impact: S · area: stop-hook · source: critic · added: 2026-06-20 · status: open · stage: ready · related: STH-4K7N · refs: bin/prawduct-hook, hooks/digest.py, hooks/banner.py`

  Surface a one-line signal when `get_project_dir` redirects `.prawduct/` resolution away from
  `CLAUDE_PROJECT_DIR` to a worktree toplevel. Today the worktree redirect (STH-4K7N) is silent: the
  load-bearing assumption that a hook process runs with the worktree as its cwd fails safe (toward
  more gating) but invisibly. A brief stderr/briefing note on the Stop path ("operating on worktree
  <path> for branch <b>") when toplevel != `CLAUDE_PROJECT_DIR` would make the redirect observable
  and aid debugging if the assumption is ever false. (critic)

- **[CRT-7Q2T]** Critic's no-test-execution rule is not structurally enforced for coordinator-dispatched subagents
  `effort: M · impact: M · area: governance/critic · source: reflection · added: 2026-06-10 · status: open · stage: design · related: CRT-3X9D, CRT-8D2W, CRT-9V4T · refs: skills/critic/SKILL.md (Structural Constraints), bin/prawduct-hook (critic-begin/critic-end) · reviewed: 2026-06-10`

  During the 2026-06-10 gate-soundness cumulative review, a coordinator-pattern subagent ran the
  affected test files directly (217 passed, reported in the review summary) despite the SKILL prose
  instruction and the pure-allow tool list — which doesn't bind Agent-dispatched subagents. Same gap
  class as CRT-3X9D, whose critic-begin marker guards only `prawduct-hook clear`. The review
  conclusion was unaffected, but the boundary exists so reviews can't mutate or depend on session
  state. Fix-shape: extend the critic-active marker enforcement (or subagent tool restriction) to
  test/build execution, or have the coordinator pass an enforced `allowed-tools` to Agent
  dispatches. Priority P2. (reflection)

- **[TEL-7A4X]** Cross-project review-telemetry aggregation — aggregate and review review-cost/value stats across all Prawduct-governed products
  `effort: M · impact: L · area: governance/telemetry · source: user · added: 2026-06-10 · status: open · stage: requirements · refs: build-plan-review-proportionality.md · reviewed: 2026-06-10`

  Builds on the per-project foundation in `build-plan-review-proportionality.md` (chunk 02 ledger
  `.prawduct/.critic-reviews.jsonl` with schema_version/model fields; chunk 03 `prawduct-hook
  review-stats --json` stable machine shape with top-level schema_version/project/generated_at —
  that JSON contract is the integration point). Fix-shape sketch (requirements still open): an
  aggregator that scans known product directories (the same discovery the "reviewing product
  feedback" CLAUDE.md route uses for learnings.md), collects each repo's `review-stats --json`, and
  renders a cross-project view: review wall-clock and actionable-finding rate by mode/model/project,
  so proportionality tuning (e.g. which products' chunk reviews yield nothing, where escalation
  pays) is evidence-driven framework-wide. Open requirements: where the aggregate view lives (skill
  vs doc vs janitor section), product opt-in/privacy posture (ledgers are gitignored local state),
  and whether product plugin versions skew comparability. **Blocked until review-proportionality
  chunks 02–03 ship.** User request 2026-06-10 ("grab a backlog to enable telemetry aggregation and
  review across projects"). (user)

  Groom 2026-06-10: UNBLOCKED — review-proportionality chunks 02 and 03 both shipped in v2.1.0
  (change-log `release=v2.1.0 | status=shipped`), so the `review-stats --json` integration point
  exists. Next step is the open requirements (where the view lives, opt-in posture, version skew),
  not code.

- **[TEL-2B6K]** Governance ledger phase 2 — record gate-block + probe-fire events and finding dispositions
  `effort: M · impact: M · area: governance/telemetry · source: builder · added: 2026-06-10 · status: open · stage: design · related: TEL-7A4X · refs: lib/ledger.py, lib/telemetry.py, lib/gates.py · reviewed: 2026-06-10`

  The v2.1.0 ledger records review.critic/review.pr only; proportionality tuning cannot answer "how
  often did each gate block?", "which probes fire and where?", or "were findings acted on or
  ignored?" (actionable-rate is currently severity-presence, not disposition). Phase 2: (a)
  `gate.blocked` / `probe.fired` event kinds (the schema already reserves unknown-kind
  forward-compat; consumers skip unknowns); (b) a lightweight finding-disposition record at
  resolution time feeding an honest actionable-rate. Design questions: where dispositions get
  captured (verify-resolutions already walks findings — a natural hook), and volume control for
  gate events. Feeds TEL-7A4X cross-project aggregation. (builder)

- **[CRT-5Q8W]** Skill prose clarity micro-fixes from the 2026-06-09 review (critic protocol wording, designer-handoff note, backlog pick defaults, framework-checks example)
  `effort: S · impact: S · area: critic · source: builder · added: 2026-06-09 · status: open · stage: ready · closes: PR-3J6W · related: PR-3J6W, CRT-6F2N, MET-3Q8V · refs: skills/critic/review-protocol.md, skills/critic/review-cycle.md, skills/critic/framework-checks.md, skills/critic/SKILL.md, skills/backlog/SKILL.md, skills/pr/SKILL.md · reviewed: 2026-07-03`

  Batch of small wording fixes from the skills review agent, none changing behavior: (1) critic
  review-protocol.md 'Decide checks from signals below' is vague — state that the resolved MODE
  determines which goals apply, with a pointer to review-cycle.md. (2) ~~critic SKILL.md Getting
  Started: add a one-line note that Type: designer-handoff chunks exit early without a findings
  file, so an agent that skips the protocol read still knows the special case.~~ **Resolved** by
  review-fixes ch.3's CRT-6F2N fix (2026-06-10, feature/review-fixes). (3) review-cycle.md
  learnings cross-check: note that if a later learning revokes/softens the original, the latest
  learning wins (currently assumes learnings are infallible). (4) framework-checks.md Check 7: add
  a concrete avoid/prefer example for 'strengthening the dynamic generation system'. (5) backlog
  SKILL pick: document the combined effect of missing effort/impact defaults (2/2 = 1.0 score)
  explicitly; drop the stale Q6 label. (builder)

  2026-06-10: sub-item (2) resolved by review-fixes ch.3's CRT-6F2N fix; sub-items (1), (3), (4),
  (5) remain open.

  2026-06-10 (merged from PR-3J6W residual): the audit verified PR-3J6W sub-items 1-3 are resolved
  (release-promotion guard now sits pre-routing via REL-8K3M; Step 2 names its re-check loop; Step
  1b made imperative in #89). The surviving piece joins this batch as sub-item (6): decide
  PR-review evidence-file retention — archive to .prawduct/.pr-reviews-archive/ vs document why
  deletion is intended. Full original body preserved on the archived PR-3J6W.

  2026-07-03 post-prose-diet check (branch feature/prose-diet; chunks 02-03 rewrote
  review-protocol/review-cycle/framework-checks): the diet compressed and merged the
  surrounding text but ABSORBED NONE of the open sub-items — all of (1), (3), (4), (5), (6)
  still apply, at slightly shifted locations. (1) "Decide checks from signals below" survives
  verbatim as activation step 6 (review-protocol.md:12); the Modes block above it does map
  mode→goals with a review-cycle.md pointer, so the residual fix narrows to making step 6
  reference that mapping. (3) the Learnings Cross-Check (now in review-cycle.md, "Learnings
  Cross-Check") still assumes learnings are infallible — no latest-learning-wins note. (4)
  framework-checks.md Check 7: the diet merged the Test/Plan-level-generality bullets into one
  but added no concrete avoid/prefer example for "strengthening the dynamic generation system".
  (5) backlog SKILL pick: the diet only repointed the discovery/planning routes to
  /prawduct:methodology; the score line documents missing→2 ("unknown-middle") but not the
  combined 2/2 = 1.0 effect, and the stale "(Q6)" label remains. (6) untouched.

- **[MET-5C2H]** Holistic context/token-budget audit — manage what fills the context window, don't dodge ceilings
  `effort: M · impact: L · area: methodology · source: user · added: 2026-06-08 · status: open · stage: research`

  The per-file token-budget tests (`building.md` <4850, critic `review-protocol.md` <3120) are proxies for
  context-window cost, but they (a) don't measure the *whole* always-loaded surface (session digest +
  product CLAUDE.md anchor + whatever methodology gets read on demand per work cycle), and (b) invite a
  "we hit a ceiling, put the tokens in a file with headroom" reflex that optimizes the wrong thing —
  content lands in a less-natural home to dodge a budget instead of asking whether the budget should rise.
  Surfaced during backlog-rework Chunk 05 (placing C-B checks in `review-cycle.md`): there the file *was*
  the natural home, but the heuristic itself is a smell. **Research-stage** — investigate before designing:
  enumerate every always-on / per-cycle context surface and its size; estimate per-token ROI (is every
  existing token earning its place?); decide whether budgets should be holistic (a total always-on ceiling)
  rather than per-file; and only raise a per-file budget when every existing token is high-ROI. Output: a
  recommendation + (likely) a revised budget model. Then it can advance to `design`/`ready`. (user)

  — 2026-06-22: the critic-protocol-budget bump (review-protocol.md ceiling 3120→3350; change-log + PR #103) is a data point for this audit — a per-file ceiling raised AFTER a lean-audit (file at 3116/3120, every token load-bearing, relocating the one movable block would fragment the instructions), i.e. the reasoned posture this item asks for, not a ceiling-dodge. Does not close this (the broad holistic budget audit remains open).

- **[ADR-7X2M]** Adversarial review agent (4th review-agent role) — RFC: systematic edge-case / attack-surface generation
  `effort: L · impact: M · area: methodology · source: user · added: 2026-06-06 · status: open · stage: requirements · related: CRT-9V4T, PRR-4M9T, JAN-4F7M · reviewed: 2026-06-10`

  RFC for a FOURTH independent review agent alongside Critic / PR-reviewer / Janitor, with the
  opposite goal — make the code *break*, not work: systematic edge-case / attack-surface generation.
  **Opt-in per project (default disabled).** Defense-in-depth via THREE independent attack-surface
  identification points: (1) **Planning** — build-plan chunks declare an `attack_surfaces:` field (an
  empty list is a valid declaration; the field itself is required); (2) **Builder** — verifies the
  actual surfaces touched at chunk-end and prompts the user for an opt-in adversarial pass when the
  diff matches the surface taxonomy; (3) **Critic Goal 8** — independent diff inspection backstop
  (WARNING on an undeclared touched surface, or a declared-but-undispositioned surface). Plus a
  pre-release `/adversarial --sweep-since-last-release` sweep.

  **NOTE — needs rework, not a merge:** the original RFC targeted the pre-2.0 `agents/` +
  `templates/critic-review.md` layout (both since removed). A real implementation must be reworked
  onto the current plugin `skills/` architecture; treat as **new feature work**, not a merge. Full
  original design is preserved verbatim at git tag `rfc/adversarial-review` (commit `967b861`).
  Author: Jason-Vaughan. Type: feature/methodology, size: medium-large. (user)


- **[PR-2H8N]** Key the `/pr` release-promotion guard off `resolve-base` instead of hardcoded branch names
  `effort: S · impact: S · area: pr · source: critic · added: 2026-06-06 · status: open · stage: ready · related: REL-8K3M · reviewed: 2026-06-10`

  REL-8K3M's release-promotion guard in `skills/pr/SKILL.md` hardcodes `develop`/`main`/`master` to
  recognize a release/integration context. The skill's own merge-flow (step 7) already distinguishes
  trunk-vs-gitflow generically via `prawduct-hook resolve-base`. A repo with a custom `base_branch`
  name (or an unusual release-surface name) would slip past the guard. Kept a NOTE during REL-8K3M
  because the guard is judgment-admitting prose an LLM can generalize, the doc reference is already
  present, and REL-8K3M targets prawduct's own gitflow case. Fix-shape: have the guard compare the
  current branch to `resolve-base`'s output (the integration base) and to the release surface, rather
  than a fixed name list. Filed from the REL-8K3M cumulative Critic NOTE on 2026-06-06. (critic)

- **[WMK-1P4Q]** Work-model parent-map injection (B2) + optional `vocabulary:` frontmatter convention
  `effort: M · impact: M · area: hooks · source: critic · added: 2026-06-06 · status: open · stage: idea · related: WMK-7D3R · refs: docs/work-model-spec.md, docs/work-model-enforcement.md · reviewed: 2026-06-10`

  Deferred from the work-model build (confidence-gated). A SessionStart hook would inject a compact,
  capped "parent map" (governing docs + 1-line scope) as ambient awareness, complementing the shipped
  *active* UserPromptSubmit nudge. Deferred because its value over the active nudge is medium-confidence
  and it adds ambient per-session tokens (review NOTE-7) — earn with usage evidence (false-positive /
  miss data from the live nudge). Also document the optional `vocabulary:`/`governs:` frontmatter
  convention in artifact templates (the lib already supports it; auto-extract is the default). See
  `docs/work-model-spec.md` Part C and `docs/work-model-enforcement.md`.

- **[LRN-3F8K]** Reconcile the dangling sentinel on the "Framework ownership follows the write strategy" learning
  `effort: S · impact: S · area: learnings · source: critic · added: 2026-06-04 · status: open · stage: design · refs: .prawduct/learnings.md · reviewed: 2026-06-10`

  `audit-learnings` reports an error: the learning "Framework ownership follows the write strategy,
  not just registry membership" carries `sentinel=tests/test_prawduct_sync.py::TestAutoCommitSafety::test_user_authored_place_once_edits_treated_as_wip`,
  but `tests/test_prawduct_sync.py` was deleted with the file-sync engine in M4 (v2.0.3) — so the
  sentinel is dangling and the audit flags it as a failing sentinel (which blocks the learning's
  retirement). Pre-existing (M4-era); surfaced by the rigor-and-stance cumulative Critic as outside
  that bundle, flagged rather than fixed inline (Scope Discipline). Fix-shape: decide whether the
  write-strategy-ownership contract still has a live equivalent test (repoint the sentinel to it), or
  the learning has outlived its mechanism (drop the sentinel annotation / retire the learning) — a
  one-line annotation fix once decided. Filed from the v2.0.7 release audit. (critic)

- **[STN-6K3D]** (Optional) Ship a non-forced `output-styles/` style power users can voluntarily select
  `effort: S · impact: S · area: agent-stance · source: builder · added: 2026-06-04 · status: open · stage: ready · reviewed: 2026-06-10`

  rigor-and-stance Chunk 02 placed the agent stance in the always-on session digest because a
  `force-for-plugin` output style HARD-OVERRIDES (clobbers) a consumer's own output style and does not
  compose — disqualifying for unconditional, composable governance (verified against the Claude Code
  output-styles docs, 2026-06-04). A *non-forced* output style is a separate, safe nice-to-have: ship
  `output-styles/<name>.md` (no `force-for-plugin`) so power users can OPT IN to the prawduct voice via
  `/config` without clobbering their own style. Low priority — the digest already delivers the stance
  unconditionally; this is pure ergonomics. Filed from the rigor-and-stance cumulative Critic
  (Complete Delivery — the plan deferred this). (builder)

- **[STH-4D2X]** Decide whether the trivial/doc-only file-set gate should also protect a consumer's own `.claude/skills/`
  `effort: M · impact: M · area: stop-hook · source: builder · added: 2026-06-03 · status: open · stage: requirements · related: STH-1W5N · reviewed: 2026-06-10`

  The waiver-pragma branch (W2-C1) fixed `_classify_trivial_change` to bound `skills/` (the framework
  repo's own skill definitions) instead of the deleted `agents/`. Open question it surfaced: in a
  CONSUMER repo, a product's own skills live at `.claude/skills/` (not top-level `skills/`), and
  `_is_metadata_path` no longer excuses them (M4 made `.claude/skills/` count as gated code). Should
  editing `.claude/skills/foo/SKILL.md` in a `Type: trivial`/doc-only chunk trip the catastrophic-
  blast-radius bound? A product skill is important but arguably not "governs all future work"
  catastrophic the way the framework's own `skills/`/`methodology/`/`templates/` are. Changing it
  affects every consumer, so it needs a deliberate decision + test, not a silent add. Filed from the
  2.0-rock-solid pass, 2026-06-03. (builder)

- **[CRT-9V4T]** Verify (or harden) interactive enforcement of the Critic fork-skill's `allowed-tools` cap
  `effort: M · impact: M · area: critic · source: builder · added: 2026-06-01 · status: open · stage: research · related: CRT-7Q2T · reviewed: 2026-06-10`

  Surfaced during v2.0.0 Chunk 4 empirical verification. The Critic's structural "no pytest / read-only git" guarantee rests on a `context: fork` skill with a pure-allow `allowed-tools` list (pytest unmatchable). `test_critic_skill_metadata.py` pins the *list shape* (no allow pattern matches pytest), and CLAUDE.md calls the constraint "structural, not behavioral." But a Chunk-4 probe found that under headless `claude -p`, a fork-skill with `allowed-tools: Read, Bash(git status *)` still ran a NON-allow-listed `echo` (marker printed) — i.e. headless `-p` did not enforce the allow-list as a hard cap. This does NOT prove a hole: the real Critic runs **interactively** (forked from a `/critic` invocation), where the cap is designed to apply, and the probe couldn't exercise that path. But it means the interactive enforcement is **assumed, not hermetically verified**, and the "structural" claim is only as strong as that assumption. Pre-existing — affects today's file-sync Critic identically; Chunk 4 introduced no regression (frontmatter byte-identical). Relates to memory `feedback_critic_no_test_execution` and learning CRT-2M5P. Fix-shapes: (a) an interactive-mode verification (manual or scripted) that confirms a forked `/critic` is actually denied a non-allow-listed Bash command — establishes whether the cap is structural or merely prompt-suppression; (b) if (a) shows it's not a hard cap, add a belt-and-suspenders **PreToolUse guard hook** in the plugin `hooks/hooks.json` that blocks pytest/`git checkout`/tree-mutation specifically when the calling agent is the critic (needs the hook to be able to scope to the subagent — itself unverified); (c) at minimum, soften the "structural, not behavioral" wording in CLAUDE.md to match what's actually verified. Open question: does Claude Code treat skill `allowed-tools` as a hard deny-cap in interactive mode, or as a no-prompt allow-list with a separate ask-fallback for unlisted tools? Resolve (a) before relying further on the claim. Filed from Chunk 4 verification on 2026-06-01. (builder)

- **[STH-7K2A]** Stop-hook structural loop-detection counter (defense-in-depth on top of v1.5.2's discoverability fix)
  `effort: M · impact: M · area: stop-hook · source: reflection · added: 2026-05-23 · status: open · stage: design · closes: v1.5.2 discoverability half · related: STH-3W7F · reviewed: 2026-06-10`

  v1.5.2 (2026-05-23) shipped the discoverability piece: all four blocker stderr messages now name `.gates-waived`, the JSON shape, and `build-governance.md` so agents stuck in unsatisfiable gate states can declare a waiver. The structural piece is still open. Pathology: even with the escape hatch named in the blocker text, an agent can in principle ignore it and continue re-firing the same gate. Defense-in-depth fix-shape: track stop-hook fire count per session in a new `.prawduct/.stop-fire-count` file recording `{count, blocker_signature, ts}`. On the Nth (e.g., 3rd) consecutive fire with the same signature and no progress (no new Critic findings, no new waiver, no diff change since last fire), either (a) escalate the blocker text to name the loop explicitly and force-surface the waiver mechanism above the existing prose, or (b) auto-downgrade to advisory (stderr-only) on the assumption that the agent has seen the gate and made an informed call. (a) is conservative; (b) is firmer about not burning tokens. Auto-clear on session start. Open design questions: per-blocker counter or session-wide? what counts as "progress" (any diff change or only changes that materially address the gate)? should the counter persist if the blocker signature changes mid-session? Filed from v1.5.2 release (2026-05-23) as the deferred structural half of the original infinite-loop bug; the original "discoverability" half is shipped and the backlog entry closes against v1.5.2's change-log entry. (reflection)

- **[MIG-6B0R]** Recommend gitflow as the default git strategy + strip prawduct artifacts on deploy-to-main
  `effort: L · impact: M · area: migration · source: builder · added: 2026-05-19 · status: open · stage: requirements · reviewed: 2026-06-10`

  Two coupled proposals:
  1. **Recommend gitflow** (`develop` for ongoing work, `main` as the deployed/released branch, feature/release/hotfix branches off `develop`) as the prawduct-recommended workflow. Captured in `project-preferences.md` (or a new `methodology/git-strategy.md`) with rationale: prawduct's session-artifacts churn pattern fits gitflow's "develop is mutable, main is immutable releases" split much better than trunk-based flow, where every session-edit lands on the deployable branch.
  2. **In gitflow repos, strip prawduct artifacts from `main` when promoting `develop` → `main`** (or when pushing directly to `main`). Filter scope:
     - **Strip:** `.prawduct/` contents — `backlog.md`, `build-plan.md`, `artifacts/`, `learnings.md`, `learnings-detail.md`, `change-log.md`, `.session-*`, `.critic-findings.json`, `.test-evidence.json`, etc. (governance bookkeeping, not deployment payload).
     - **Strip:** prawduct-owned hooks/skills — `bin/prawduct-hook`, `.claude/skills/{critic,pr,janitor,learnings,prawduct-doctor}/SKILL.md`, framework-managed `.claude/settings.json` hook entries.
     - **Keep:** `docs/` and `documentation/` (real product documentation, not governance artifacts).
     - **Keep:** project-owned skills/hooks (anything in `.claude/skills/` that's NOT in the prawduct-managed set — user-authored skills stay).
  Fix-shape: probably a `prawduct-doctor deploy-to-main` (or `prawduct-deploy`) subcommand that performs a filtered merge/squash — strips the listed paths from a temp index, commits the cleaned tree to `main`, leaves `develop` intact. Alternative: a git pre-receive hook recipe in `methodology/git-strategy.md` that products copy into their own remote. Need to decide which paths are framework-canonical (centralizable in `core.py`'s MANAGED_FILES + a new `DEPLOY_STRIP_PATHS` set) vs. project-configurable. Open question: does the filter run on every push to main, or only on explicit `prawduct-doctor deploy` invocations? Filed from user request on 2026-05-19. (builder)

  Groom 2026-06-10: premise partially obsoleted — the strip-list names file-sync-era files
  (bin/prawduct-hook, framework-managed skills in product repos) that plugin-governed products no
  longer commit. The residual want (keep governance bookkeeping like .prawduct/ state off a
  deployed main) may still be real; re-derive the requirement against the plugin-era reality
  before any design. Stays stage: requirements.

- **[BLD-5V8F]** F3: extend `verify-chunk-refs` beyond file paths
  `effort: M · impact: M · area: build-plan · source: critic · added: 2026-05-18 · status: open · stage: requirements · related: BLD-2R9X, BLD-8F2Q · reviewed: 2026-06-10`

  v1.4 Chunk 02 (F3) shipped file-path verification only; the original plan also called for symbol (function/class names) and backlog-ID verification. Deferred during build because (a) symbols in prose are often approximate (`parse_func` vs implementation's `_parse_func`) so strict grep produces false positives requiring fuzzy match; (b) this project's backlog has no formal IDs (bullet titles, not e.g. `BL-123`), so the check would be inert here and need per-project ID convention. Add when a project surfaces a concrete need: define matching rules (substring grep across configured source roots for symbols; project-preferences `backlog_id_pattern` regex for backlog refs) and extend `_parse_build_plan_chunk_refs` to return `symbols` and `backlog_refs` lists alongside `file_paths`. Note: this project now HAS formal backlog IDs (`[PFX-XXXX]`) post-migration, so the backlog-ID half is newly actionable. Filed from /critic NOTE on 2026-05-18. (critic)

- **[MET-9K4R]** Workflow-values schema/validator
  `effort: S · impact: S · area: methodology · source: critic · added: 2026-05-01 · status: open · stage: design · reviewed: 2026-06-10`

  Workflow preferences (`Branching: direct`, `PR creation: wait_for_user`, `PR merge: wait_for_user`) are read by `building.md` and `/pr` but have no allowed-vocabulary or shape check. A typo or unknown value would silently default. Candidate: small Critic checklist line ("Workflow values must be one of X / Y / Z") OR a tiny config-presence test. Low priority — current values are stable. (critic, 2026-05-01)

- **[MET-3P7B]** Lift "assign a mechanism per preference" pattern into methodology
  `effort: M · impact: M · area: methodology · source: critic · added: 2026-05-01 · status: open · stage: research · reviewed: 2026-06-10`

  The Enforcement section added to `project-preferences.md` (and the template, 2026-05-01) encodes a methodology insight: every preference must be assigned to Linter / Test / Critic when it's captured, with a false-confidence guardrail that escalates weak tests to Critic. Currently lives only in the artifact + template. Candidate: weave into `methodology/discovery.md` (when capturing preferences) and `methodology/planning.md` (when designing test specs). Validate the pattern against 2-3 more preferences first before promoting. (critic)

- **[CRT-6T1V]** Critic check: test helpers duplicating production logic
  `effort: M · impact: M · area: critic · source: reflection · added: 2026-04-16 · status: open · stage: design · reviewed: 2026-06-10`

  Cross-product reflection audit (Apr 16) surfaced a recurring drift hazard in discodon: test files re-implement production calculations (LogQL builders, SDK result parsing) rather than importing the shared helper, so tests keep passing while production drifts. Evidence: discodon/reflections.md §2026-04-14 "Pattern worth keeping". Candidate: extend Goal 1 or Goal 7 in skills/critic/review-protocol.md — when a test performs a calculation/parsing operation that exists in production, flag as WARNING unless the test is deliberately testing the helper itself. Needs design work on detection heuristic (string-matching is noisy; AST match is heavier). (reflection)

- **[CRT-1B6Q]** Critic check: stateful objects in shared_kwargs need lifecycle cleanup
  `effort: M · impact: M · area: critic · source: reflection · added: 2026-04-15 · status: open · stage: design · reviewed: 2026-06-10`

  Discodon's multi-tool coordinator pattern passes stateful objects (PendingVoiceSlot, prior voice_getter closures) via `shared_kwargs` to multiple tools. Critic caught lifecycle bugs (missed_intro false-positives when idle) only after complex state interactions emerged. Evidence: discodon/reflections.md §2026-04-15 V0.5-5. Candidate: extend Goal 6 (The System Can Be Understood) — when an object with enter/exit/close methods is shared across tools, verify owner tool's stop() drains/closes it. Generalizes beyond discodon's specific pattern to any DI/coordinator framework. (reflection)

- **[CRT-5N3F]** Critic false positives from fork-context limits
  `effort: L · impact: M · area: critic · source: reflection · added: 2026-04-16 · status: open · stage: research · reviewed: 2026-06-10`

  Discodon archive (Feb–Apr 2026) has 4 confirmed cases where Critic misread code: Mar 24 shutdown event closure, Mar 25 eval doc merge (3 of 4 prior findings false), Mar 28 ARIA A1/A2 missed an existing `model_config = ConfigDict(str_strip_whitespace=False)` override, plus branch-switching confusion. Root cause: `context: fork` can't see overrides spanning files / inheritance / closures. Investigate whether Critic's research phase needs a wider read budget for inheritance chains, or whether prompt engineering can compensate. (reflection)

- **[CRT-8D2W]** Critic-in-worktree as structural fix for session-file conflicts
  `effort: L · impact: M · area: critic · source: reflection · added: 2026-03-25 · status: open · stage: requirements · reviewed: 2026-06-10 · related: CRT-3X9D`

  v1.3.3 gitignored build-plan.md and v1.3.4 added `_untrack_session_files()`, but the user explicitly suggested running Critic in a separate worktree to avoid touching session files in the active tree at all. Mar 25 discodon avatar_description session captured this when branch-switching during Critic review caused merge conflicts on `.session-handoff.md` and backlog. Worth designing as a follow-up to the gitignore approach. (reflection)

  **Premise partially obsoleted — reassessed 2026-06-10:** the original motivation rested in part on
  the build plan being a *gitignored* session file; gate-soundness ch.3 (feature/gate-soundness) made build
  plans **tracked**, so that half of the conflict surface is gone. The residual rationale is
  narrower: the remaining gitignored session files (`.session-handoff.md`, `.critic-findings.json`,
  `.session-reflected`, …) plus the broader isolation argument — an independent reviewer should not
  be able to mutate the session tree at all (the same invariant CRT-3X9D enforces at the mutation
  site via the critic-begin/critic-end guard). Before any design work, re-derive the requirement
  against the current tracked-build-plan + critic-session-guard reality; the worktree approach may
  now be redundant defense-in-depth rather than a structural fix. (critic, gate-soundness cumulative
  review note)

- **[TST-4P8H]** Flaky tests under parallel execution (xdist)
  `effort: M · impact: M · area: tests · source: builder · added: 2026-04-16 · status: open · stage: research · reviewed: 2026-06-10`

  Re-validated 2026-06-03: 5 of the 6 originally-named tests were removed with the file-sync engine (M4) — only `TestStopPrReviewGate::test_stop_clean_without_pr` survives. The narrow open question is whether that surviving subprocess-heavy test (and peers) still flake under `-n10`. The depth_cap test creates 111 git subprocess commits in a loop — when 9 other xdist workers are simultaneously doing similar subprocess-heavy work, the system runs out of fork resources / hits IO contention and the test times out. Passes 100% of the time when run in isolation or with reduced parallelism. Root cause likely race conditions in the subprocess-based hook tests sharing process-level state or temp dir contention. (builder)

  Groom 2026-06-10 (audit refresh): no active flakes; conftest now auto-groups by directory under
  xdist and the heavy git suites (test_governance_ledger, test_cumulative_gate) use sterile-HOME
  isolation. New evidence in the same family: test_audit_learnings hit a pytest-timeout worker
  crash under full-suite xdist (2026-06-10, worked around by pointing at a tmp repo). Item narrowed
  to: give the residual heavy tests explicit timeouts or a dedicated xdist group; close when the
  suite runs clean at -n10 repeatedly.

- **[STH-7B5N]** Session lock file for concurrent session detection
  `effort: M · impact: M · area: stop-hook · source: builder · added: 2026-04-16 · status: open · stage: ready · reviewed: 2026-06-10`

  Advisory lock file in product-hook clear/stop to warn when another Claude session is active on the same project. Agreed on non-blocking approach with staleness timeout (~4 hours). (builder)

- **[BLD-7W2J]** Single-slot `active_build_plan` vs parallel in-flight plans
  `effort: M · impact: M · area: governance/planning · source: critic · added: 2026-06-10 · status: open · stage: idea · related: REL-4T8N · refs: lib/core.py (resolve_build_plan_path), methodology/planning.md`

  Two concurrent feature branches (feature/review-fixes → `build-plan-review-fixes.md`,
  feature/gate-soundness → `build-plan-gate-soundness.md`) each set the one `active_build_plan`
  pointer in `project-state.yaml`, guaranteeing a same-line merge conflict on develop — after which
  one plan is invisible to pointer-resolved governance (stop hook, `infer-critic-mode`,
  `verify-chunk-refs`) until repointed. planning.md's new "Plan lifecycle on gitflow" paragraph
  covers only the *serial* release-pending case; gate-soundness ch.3 (tracked plans) + scope-named
  files make parallel plans more likely. Design work needed: model multi-plan state (e.g. a plan
  list, or per-branch resolution) or document the parallel-branch convention. Related: REL-4T8N
  solved the *release-side* multi-plan problem (regen-views enumerates change-log scopes instead of
  the pointer) but the in-flight pointer remains single-slot. Filed from fable test-reviewer NOTE on
  the gate-soundness bundle, 2026-06-10. (critic)

- **[MET-7R4J]** Methodology/CLAUDE.md redundancy and prompt-quality pass — hard rules stated 4-6x across always-loaded surfaces
  `effort: S · impact: M · area: methodology · source: builder · added: 2026-06-09 · status: open · stage: ready · related: MET-5C2H, MET-3Q8V · refs: CLAUDE.md, docs/principles.md, methodology/building.md, methodology/planning.md, methodology/session-digest.md · reviewed: 2026-07-03`

  From the 2026-06-09 framework review (methodology-as-prompts agent). For Opus/Fable-class models, restating a rule with varied phrasing creates interference, not reinforcement. (1) Consolidate to one canonical statement + cross-refs: Tests Are Contracts appears 6x (CLAUDE.md, principles.md, agent-stance.md, building.md 2x, session-digest.md); the mid-build-requirement rule has 8+ phrasings; the Critic mandate appears 6x with escalating emphasis. (2) Remove emphasis escalation: CLAUDE.md 'STOP. Read this before writing ANY code' caps — prompt-rot pattern that also misstates Critic timing (Critic runs after code). (3) Compress planning.md Foreign API Verification (~40 lines to ~15: rule + when-to-apply + one worked example; move match mechanics to the Critic protocol). (4) Add one sentence to building.md Before You Build: re-review the plan's Open assumptions as code reveals new facts (assumptions are recorded at plan time but never checkpointed mid-build). Note: digest-vs-CLAUDE.md duplication is handled separately by the review-fixes plan Chunk 4 (slim framework-repo digest); this item is the within-file redundancy pass. Token-budget guardrail tests on methodology files will need adjusting downward, not up. (builder)

  2026-07-03 superseded-check (prose-diet cumulative Critic reconciliation, branch
  feature/prose-diet — MET-3Q8V's own note said prose-diet "largely supersedes" this item).
  What prose-diet DELIVERED: sub-item (1) largely — `methodology/agent-stance.md` deleted
  (one whole duplicate surface gone), building.md's Tests-Are-Contracts restatements removed
  (now 0 in-file; canonical lives in principles.md + CLAUDE.md list + digest), and the
  mid-build-requirement phrasings compressed by the D1-D6 reconcile; sub-item (3) fully —
  planning.md Foreign API Verification is now ~17 lines (rule + when-to-apply + pointer to the
  filled template example). RESIDUE still open, now the whole of this item: sub-item (2) —
  CLAUDE.md's "**STOP. Read this before writing ANY code**" emphasis-escalation caps survive
  verbatim (line ~94), still misstating Critic timing; sub-item (4) — building.md still has no
  mid-build open-assumptions re-review sentence (assumptions recorded at plan time, never
  checkpointed). Effort trimmed M→S to match the residue.

- **[JNT-9R2K]** Janitor SKILL: move the investigation-theme taxonomy to a companion reference file; close the Step 2.5 to Step 7 backlog loop
  `effort: S · impact: S · area: janitor · source: builder · added: 2026-06-09 · status: open · stage: ready · refs: skills/janitor/SKILL.md · reviewed: 2026-06-10`

  From the 2026-06-09 framework review (skills agent). (1) The nine investigation themes (~100 lines, ~50% of the skill) read once per janitor run — move theme details to a bundled companion file (the pattern the Critic already uses with review-protocol.md etc.) and keep SKILL.md as dispatcher + process. (2) Clarify that Step 2.5 Backlog Health emits read-only NOTE findings and Step 7 Reconcile is where those findings drive /prawduct:backlog update calls — the linkage is currently implicit. (3) Reframe the 'fresh eyes' line toward pattern-detection + infer-and-confirm, and say what to do when the user cannot confirm a preference divergence (file a backlog item rather than resolving unilaterally). (builder)

- **[WMK-7D3R]** Work-model index never rebuilds on artifact deletion — retired vocabulary lingers
  `effort: S · impact: S · area: work-model · source: builder · added: 2026-06-09 · status: open · stage: design · related: WMK-1P4Q, GOV-7T2M · refs: bin/prawduct-hook, lib/work_model_index.py · reviewed: 2026-07-02`

  From the 2026-06-09 framework review. The staleness check (bin/prawduct-hook, build-index path) compares
  remaining artifact mtimes to the index mtime, so deleting an artifact never triggers a rebuild and its
  vocabulary lingers between sessions. Mostly masked by build-index force=True at SessionStart — decide
  whether to fix (include the artifact file-set in the staleness fingerprint) or document the SessionStart
  rebuild as the intended guarantee. Note: probe precision (false positives on common English) is separate,
  covered by the review-fixes plan Chunk 2. (builder)

  **Re-checked 2026-07-02** at GOV-7T2M ship (gate-noise): still open, content unchanged in kind —
  gate-noise widened the corpus (`docs/`/`methodology/` now recursive in
  `_work_model_corpus_paths`) but did not touch the mtime-only staleness check, so the
  deletion-doesn't-rebuild gap now spans a strictly larger file-set (marginally more relevant,
  same fix-shape: file-set in the staleness fingerprint, or document SessionStart force-rebuild
  as the guarantee). The probe-precision thread this item pointed sideways at continued in
  GOV-7T2M/WMK-4Q9T.

- **[CRT-6J4P]** infer-critic-mode rule-1b chains across work-cycle/bundle boundaries — prior bundle's cumulative vouches for a new plan's first chunk
  `effort: S · impact: S · area: governance/critic · source: reflection · added: 2026-06-10 · status: open · stage: design · related: CRT-8W3F, CRT-4J8W, CRT-7B4M, CRT-2N7V · refs: lib/critic_mode.py, skills/critic/SKILL.md`

  Observed 2026-06-10: on a brand-new branch/plan (feature/do-next, first chunk), inference picked
  verify-resolutions extending the PREVIOUS released bundle's cumulative (3c4b627,
  changelog-lifecycle v2.1.1) instead of chunk mode. Commit-coverage keeps the record sound, but
  cross-bundle chaining is surprising; consider bounding rule-1b to the current branch/merge-base or
  active plan scope. (reflection)

- **[CRT-8H3R]** infer-critic-mode / compute-verify-resolutions-scope picks an unsound verify-resolutions chain when the session switched branches
  `effort: S · impact: M · area: critic/gates · source: critic · added: 2026-06-21 · status: open · stage: ready · related: CRT-6J4P · refs: infer-critic-mode, compute-verify-resolutions-scope (bin/prawduct-hook + lib/) · reviewed: 2026-07-03`

  If SessionStart recorded branch A but the work is on a divergent branch B, mode-inference can chain
  verify-resolutions to A's anchor SHAs; compute-verify-resolutions-scope only demotes when an anchor
  SHA does NOT resolve, so a SHA that still resolves on the sibling branch (not an ancestor of HEAD)
  passes the guard and yields a cross-branch two-way diff full of phantom findings (surfaced live this
  session on feature/hot-path-git-batching, anchors f208ad2/f92a4be from sibling
  feature/hook-cli-robustness). Fix shape: add an is-ancestor check on commit_reviewed (git merge-base
  --is-ancestor <anchor> HEAD) — if the anchor isn't an ancestor of HEAD, demote to cumulative/final
  instead of computing a divergent delta. Surfaced + self-flagged by the Critic during STH-6Q9D.
  (critic)

  Second live occurrence + soundness escalation (2026-07-03, prose-diet chunk-01 Critic WARNING): a
  stale single-slot `.critic-findings.json` left by sibling branch feature/gate-exemption-boundary
  latched verify-resolutions onto a cross-branch delta while reviewing feature/prose-diet. Both
  `commit_reviewed` and `extends_cumulative` SHAs must be required to be ANCESTORS OF HEAD (mere
  object-resolution is insufficient) — and the stakes are worse than phantom findings: if the reviewer
  records the chain anchor, `check-cumulative-critic` could spuriously accept a Goals-1-3 review as
  cumulative coverage for an unrelated branch's PR. Fail closed: non-ancestor anchor → demote to
  chunk/final. (critic, chunk-01 prose-diet review)

- **[CRT-9L2F]** Post-release live verification: explicit /prawduct:critic mode argument honored end-to-end (follow-up to CRT-2N7V, gate-hardening ch.03)
  `effort: S · impact: M · area: governance/critic · source: builder · added: 2026-06-10 · status: open · stage: ready · related: CRT-2N7V, CRT-3M8Q · refs: skills/critic/SKILL.md, lib/critic_mode.py`

  After the gate-hardening bundle ships in a release (so the installed plugin carries the rewritten
  SKILL.md step 1), invoke the Critic via the Skill tool with an explicit mode that DIFFERS from
  what inference would pick, and confirm .critic-findings.json records mode_chosen_by:
  "explicit-args". Context: the bundle's own cumulative (2026-06-10) was invoked with explicit args
  and still recorded rule-2 inference — third observation; undetermined whether the edited skill
  even ran (framework-repo skill source ambiguity: marketplace v2.1.2 clone vs working tree).
  Known facts: $ARGUMENTS substitution is broken for Skill-tool→fork (anthropics/claude-code#34164,
  closed not-planned); args demonstrably reach OTHER fork skills (backlog, learnings — same
  session); the helper layer (prawduct-hook infer-critic-mode <token>) is unit-proven. If
  launch-message delivery doesn't reach the Critic fork, escalate to a file-based mode request
  (invoker writes the requested mode to a .prawduct dotfile; helper reads + deletes it). (builder)

- **[REL-5K8M]** Heavier-mechanism option for reviewer-model churn — single-source tier→model registry + drift check
  `effort: M · impact: M · area: governance/release · source: builder · added: 2026-06-12 · status: open · stage: idea · refs: .prawduct/artifacts/build-plan-reviewer-model-fallback.md, documentation/research/open-6-model-tier-registry.md`

  Deferred from reviewer-model-fallback (2026-06-12). The v2.1.5 fix handled model withdrawal (Fable
  temporarily pulled) with prose-only ordered fallback chains — the user chose the lightest mechanism.
  If model churn recurs or the prose-driven resolution proves error-prone, consider the heavier
  mechanism that was considered and declined for proportionality: a single source-of-truth tier→model
  registry (one place to edit on a lineup change) plus a `/prawduct:doctor` or `/prawduct:janitor`
  drift check that flags when a named alias in the registry is past a known retirement date.

  Honest constraint recorded in `build-plan-reviewer-model-fallback.md`: a Python hook cannot see the
  harness's live valid-model set, so any check is refresh-cadence/advisory-based, not an automated
  availability probe. Related: `documentation/research/open-6-model-tier-registry.md` is a separate
  surface (the Critic classifying a *product's* models), not this reviewer-dispatch registry. Type:
  enhancement, low priority. (builder)

- **[TEL-6P2D]** review-stats windowing + zero-yield pruning-candidate flag + a documented pruning protocol (no auto-cut)
  `effort: S · impact: M · area: telemetry · source: user · added: 2026-06-22 · status: open · stage: design · related: TEL-4M9X, CRT-9R4K, CRT-5T8N · refs: lib/telemetry.py, methodology/building.md`

  Problem: We want to retire/lighten review legs that demonstrably catch nothing, WITHOUT guessing.
  Today review-stats has no window and no "this leg looks unproductive" signal, and there is no written
  protocol for how a cut is justified/approved. The 2026-06-22 data (post-A1) is too thin per bucket
  (1–8 reviews) to act on, so the immediate need is to accumulate clean data and stand up the decision
  machinery.

  Approach:
  - Add `review-stats --since=<window>` (time-based e.g. 30d AND/OR last-N reviews) so trailing-window
    yield is readable, not just all-time.
  - Flag any (role × mode [× code-path]) leg with ≥N reviews and 0 actionable (B/W) findings over the
    window as a HUMAN-REVIEWED pruning candidate — surfaced in the report, NEVER auto-applied.
  - Write the pruning protocol into methodology: a review leg may be lightened/retired only when (a) ≥N
    reviews in window, (b) 0 actionable yield, (c) a human signs off, AND (d) it ships with a regression
    test proving a non-eligible case still gets the full review (the trivial-fast-path lesson: a
    skip-gate needs the MOST adversarial coverage).
  - Name the PR reviewer (pr-scoped) as the standing WATCH-TARGET: as of 2026-06-22 it is the lowest
    yield-per-run (9 reviews, ~1 actionable, ~46 min wall-clock total), BUT its low yield is confounded
    — its job includes confirming the Critic was right + release-readiness, where an empty result is
    partly success. Do NOT cut it on current data; instrument and watch.

  Assurance: preserved by construction — every cut is gated behind data + human sign-off + a regression
  test; the flag is advisory only.

  Open design decisions: threshold N (proposal ≥10 reviews/0 actionable before flagging); window
  semantics (time vs count — recommend both, default time); whether to break the flag down by
  code-path/scope (a leg may be productive on governance diffs, dead on docs). Depends on A1 (clean
  model dimension). Feeds C (the data that would justify deferring per-chunk reviews on short plans).
  (user)

- **[CRT-9R4K]** Extend cumulative-final to short plans — defer per-chunk Critic reviews into one end-of-plan cumulative
  `effort: M · impact: M · area: building · source: user · added: 2026-06-22 · status: open · stage: requirements · related: TEL-6P2D · refs: methodology/building.md, skills/critic/review-protocol.md, lib/critic_mode.py`

  Opportunity: For a multi-chunk feature every chunk gets its own opus fork Critic review, then the
  cumulative re-reviews all of them (the deliberate local-vs-integration redundancy). For SHORT plans
  this is the biggest avoidable wall-clock: N per-chunk runs a single end-of-plan cumulative would
  cover. The 2026-06-22 chunk-mode yield is low (~1 actionable across 7 reviews) — MILD supporting
  evidence only; early-detection value is not captured by finding-count, so this is a judgment call,
  not a data verdict.

  Tradeoff (USER owns it — Principle 23): deferring per-chunk reviews trades EARLY detection for a
  bigger blast radius — a flaw introduced in chunk 1 surfaces only at end-of-plan, costing more rework
  to unwind. Eligibility bounds that risk.

  Requirements to pin FIRST (C0 — why this is stage:requirements, not ready):
  - Decide the acceptable-tradeoff bounds: under what plan shape is deferring early detection
    acceptable? Proposal: chunk-count ≤ 3 AND risk tier = standard AND NEVER escalate-tier
    (governance/contract-path scope always gets per-chunk review). User to confirm/adjust.
  - Confirm composition with the existing cumulative-final Type (today: commit last chunk, run
    cumulative once = chunk review + PR record). C generalizes that to cover ALL chunks of a short
    eligible plan, not just the last.

  Design (C1, after requirements): eligibility predicate in lib/critic_mode.py + the build cycle in
  methodology/building.md (eligible short plan marks intermediate chunks "review deferred to
  end-of-plan cumulative"); resolve how a deferred plan interacts with the stop-hook Critic gate and
  session boundaries (a plan spanning sessions cannot defer past a session end without a gate record).

  Guardrail (C2 — MANDATORY, load-bearing): ship with a regression test proving a NON-eligible plan
  (4+ chunks OR escalate-tier) STILL gets per-chunk reviews. The retired PR trivial-fast-path failed
  precisely because it shipped with zero adversarial coverage — a skip-gate needs the MOST adversarial
  coverage.

  Assurance: preserved only if the eligibility predicate + C2 regression test hold and the bounded
  early-detection loss is explicitly accepted by the user. Gated behind A's accumulated data OR an
  explicit user accept-the-tradeoff decision. (user)

- **[BLD-3M7K]** `verify-chunk-refs` over-matches git-ref tokens (origin/-prefixed and branch-like slash tokens) in build-plan prose, producing false missing-ref positives
  `effort: S · impact: S · area: critic · source: critic · added: 2026-06-21 · status: open · stage: idea · related: BLD-4K7P, BLD-2R9X, BLD-8F2Q · refs: lib/buildplan_refs.py (_looks_like_file_path)`

  Follow-up to BLD-4K7P. Surfaced 2026-06-21 by the hook-cli-robustness cumulative Critic: the
  plan's own prose backticked `origin/develop` and `origin/` while describing the REL-7P3X fix;
  `_looks_like_file_path` treats any backticked slash-token without `<>`/`://`/glob as a file path,
  so git refs flag as missing. Same false-positive family the BLD-4K7P fix (placeholders, URLs,
  gitignored) does NOT cover, and PR #99's cumulative saw it too. Workaround in place: de-backtick
  git refs in plan prose (the gate correctly checks file paths; a git ref isn't one). Open question:
  a general fix is hard — branch-like tokens (feature/x) are indistinguishable from real paths
  (feature/x), so an origin/-prefix-only heuristic risks false-negatives on real missing paths.
  Decide whether the narrow origin/ exclusion is worth it or the convention (don't backtick git
  refs) suffices. (critic)

<!-- Fix program from the framework efficiency review (owner-accepted 2026-07-02).
     Parent requirement doc: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md
     READ IT IN FULL before planning any item below — it carries the evidence these one-liners cannot.
     Waves: 1 = P0 (kill recurring taxes), 2 = P1 (outcome gaps), 3 = P2 (weaker-model scaffolding).
     Each wave item ships as its own small 1-2 chunk plan on its own branch — NOT one monolithic plan. -->

- **[CRT-5M9J]** Wave 2: scope check in review — mandated question: does this capability trace to a documented requirement, and is it reachable/consumed end-to-end?
  `effort: S · impact: M · area: critic/pr-protocols · source: user · added: 2026-07-02 · status: open · stage: ready · related: ADR-7X2M · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 2, Underspecified #2), skills/critic/review-protocol.md, skills/pr/review-protocol.md`

  P1. The metallm blind spot, documented 4x: every reviewer checks work AS SCOPED, never whether
  the requirement should EXIST or was ever built (scriob shipped 697 commits with an unversioned
  API on an unchallenged one-word deferral). Fix costs a paragraph: one mandated question in the
  cumulative and PR protocols pressure-testing scope and end-to-end reachability. (user)

- **[STH-8R3Q]** Wave 2: outcome-checking Critic Stop gate — findings file must show zero unresolved blocking findings, not merely valid schema
  `effort: S · impact: M · area: stop-hook/gates · source: user · added: 2026-07-02 · status: open · stage: ready · related: STH-4F7C · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 2, Overbuilt #5), lib/gates.py:300-311 (critic_findings_satisfy_session_gate)`

  P1. The Critic Stop gate accepts any schema-valid fresh findings file EVEN WITH unresolved
  blocking findings — it enforces a proxy (file exists, schema valid), not the outcome (blockers
  resolved). Make `critic_findings_satisfy_session_gate` check disposition of blocking findings.
  Gate edit governs the editing session — small blast radius, own branch. (user)

- **[ENV-2W7K]** Wave 2: environments plan — worktree story, gitflow base detection, non-Python coverage floor goes silent, document --from-counts as the paved non-pytest path
  `effort: L · impact: L · area: environments · source: user · added: 2026-07-02 · status: open · stage: design · related: CRT-6W2N, STH-4K7N, CRT-8D2W, COV-5H3N, COV-4M2J, TST-2H9P · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 2, Underspecified #1)`

  P1. The framework assumes repo-root Python, single checkout, main-based — violated by engine/
  subdirs (scriob), .NET/Swift (cordyceps/trenchant), worktrees (incoming bug 2026-06-20:
  "following one prawduct rule forces you off-protocol on another"), devcontainers (discodon),
  gitflow (silent wrong-base on every first PR). Scope: a supported worktree story; gitflow base
  detection that doesn't require knowing `base_branch:` exists; non-Python coverage floor goes
  SILENT (not noisy) for languages it can't see; document `--from-counts` as the paved non-pytest
  path. Owner's rule: the worktree piece needs a short design note FIRST, confirmed with the
  owner, before building. Umbrella over CRT-6W2N/STH-4K7N/COV-5H3N — dedup/`closes:` when
  planned. (user)

- **[CRT-3F6W]** Wave 2: reviewer-dedup deletion — keep both reviewers; PR reviewer becomes a fresh full-scope release review; delete the record-audit protocol, extends_cumulative chain, and don't-re-scan scoping prose
  `effort: M · impact: M · area: critic/pr-protocols · source: user · added: 2026-07-02 · status: open · stage: ready · related: CRT-5T8N, CRT-6J4P, CRT-8H3R, CRT-9R4K · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 2, Overbuilt #4), skills/pr/review-protocol.md:19-27`

  P1. Independence is load-bearing — two reviewers stay (PR reviewer independently caught bugs
  the Critic missed at least twice). What goes is the ~2k words of OVERLAP machinery that exists
  only to deduplicate two overlapping scopes: the "Critic Record — Evidence, Not Truth" audit
  protocol, the extends_cumulative chain, verify-resolutions scope math, and the "don't re-scan"
  scoping prose. The PR review becomes a simple fresh full-scope release review. Prefer deletion
  over patching. Supersedes CRT-5T8N's single-owner question — candidate `closes:` at dedup. (user)

- **[LRN-7M4D]** Wave 2: memory convergence — learnings + learnings-detail durable, .session-reflected ephemeral, retire per-repo reflections.md accumulation (design note first)
  `effort: M · impact: M · area: memory/learnings · source: user · added: 2026-07-02 · status: open · stage: design · related: MET-6W3J · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 2, Underspecified #5)`

  P1. The memory triple-track: reflections.md is write-heavy/read-never (discodon: 7,645 lines,
  nothing retrieves from it); metallm's reflection loop froze while learnings thrived. Converge:
  learnings + learnings-detail as the durable pair; .session-reflected ephemeral (distilled or
  discarded at session end); retire per-repo reflections.md accumulation. Owner flagged this
  convergence directly. Changes the onboarded-repo contract, so it needs a migrate path — write
  the short design note FIRST and confirm with the owner before building. (user)

- **[MET-8J5R]** Wave 2: plan-shape guidance in planning.md — one plan per scope tag; split heterogeneous work; a plan that won't ship in ~3 sessions is a program; planner pushes back on monolithic requests
  `effort: S · impact: M · area: methodology/planning · source: user · added: 2026-07-02 · status: open · stage: ready · related: BLD-7W2J · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (finding 6a, Wave 2), methodology/planning.md, methodology/building.md`

  P1 (finding 6a). building.md's size ladder reads as an instruction to build ONE big chunked
  plan; long-lived-plan frictions sat in learnings for weeks without flowing back into
  planning.md (a Close the Learning Loop failure). Add mechanical heuristics: one plan per scope
  tag; split when change types differ; a plan that won't ship within ~3 sessions is a program →
  backlog items + per-wave plans; the planner must push back on monolithic-plan requests. This
  fix program's own wave structure is the worked example. (user)

- **[DOC-3V7T]** Wave 2: persistence contract for review/research artifacts — first-class home (.prawduct/artifacts/ + naming convention), backlog items link their parent artifact, pick surfaces it
  `effort: S · impact: M · area: artifacts/convention · source: user · added: 2026-07-02 · status: open · stage: ready · related: MET-8J5R · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (finding 6b, Wave 2)`

  P1 (finding 6b). Rich review/research output has no first-class home — cross-session surfaces
  (build-plan Context line, backlog one-liners, .session-handoff.md) are all thin; the efficiency
  review itself had to hand-roll the workaround (write an artifact, link every item to it).
  Deliverable is likely just a convention + template + one line in planning.md: artifacts live in
  .prawduct/artifacts/ with a naming convention; backlog items `refs:` their parent artifact;
  `pick` surfaces the linked artifact. Avoid building machinery. (user)

- **[STN-4W7R]** Wave 2: advisor-first stance made structural — digest stance-block tone rewrite (rides with MET-3Q8V) + advisory obligations attached to existing checkpoints
  `effort: M · impact: M · area: agent-stance · source: user · added: 2026-07-02 · status: open · stage: ready · related: MET-3Q8V, MET-8J5R · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Advisor-first stance, Wave 2), methodology/session-digest.md, methodology/planning.md, methodology/discovery.md, CLAUDE.md (Before Building) · reviewed: 2026-07-03`

  P1. Owner directive 2026-07-02: lean into prawduct's role as advisor/expert rather than merely
  an implementor of whatever the user asks for. Two parts: (a) TONE — when Plan C (MET-3Q8V
  prose-diet) rewrites the digest, reframe the stance block from a trait list into a lead
  position: the agent's first duty on any substantive ask is the expert take (risks,
  stronger/simpler alternative, recommendation), compliance second. (b) STRUCTURE — attach
  advisory obligations to checkpoints models already hit, because tone exhortations decay on
  weaker models: plan creation (plan-shape pushback, MET-8J5R), backlog pick ("is this still
  worth doing?"), discovery start (what the user hasn't thought of — already present), and the
  Before-Building check gains an explicit "should this be built as asked?" line. Advisorship
  that lives only in adjectives will not survive under context pressure; advisorship attached to
  gates will. Parent: framework-efficiency-review-2026-07-02.md "Advisor-first stance" section. (user)

  2026-07-03 (prose-diet cumulative Critic reconciliation, branch feature/prose-diet): part (a)
  DELIVERED on that branch — chunk 03 rewrote the digest stance block in
  `methodology/session-digest.md` (~239 words) from trait list to expert-take-leads framing,
  keeping the checkable bars; slim digest synced. Also this branch deleted
  `methodology/agent-stance.md` (folded by MET-3Q8V), so the stance's sole operational surface
  is now `methodology/session-digest.md` — refs repointed accordingly. Part (b) (advisory
  obligations attached to existing checkpoints: plan creation, backlog pick, discovery start,
  Before-Building line) remains open and is now the whole of this item.

- **[MET-2X6F]** Wave 3: weaker-model scaffolding — filled example chunk, domain-concern checklist seeded by structural characteristics, root-cause stopping rule, 3-4-file size tiebreak, red-baseline protocol
  `effort: M · impact: M · area: methodology/templates · source: user · added: 2026-07-02 · status: open · stage: ready · related: MET-3Q8V, BLD-8N4W · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 3, Underspecified #4), templates/build-plan.md, methodology/discovery.md:100, methodology/building.md · reviewed: 2026-07-03`

  P2. Judgment offloads with no weaker-model scaffolding: "detect domain concerns dynamically, no
  hardcoded lists"; no root-cause stopping rule; the 3-4-file size-classification dead zone; no
  red-baseline protocol; zero filled examples in the build-plan template. Note: the filled
  example chunk may already land in Wave 1 Plan C (MET-3Q8V) — check before duplicating work. (user)

  2026-07-03 (prose-diet cumulative Critic reconciliation): the "filled example chunk"
  deliverable LANDED in prose-diet chunk 01 — `templates/build-plan.md` is now a fully-filled
  Pantry example (1,197 words), so Wave 3 must NOT redo it. The rest of the item still stands:
  domain-concern checklist seeded by structural characteristics, root-cause stopping rule,
  3-4-file size tiebreak, and red-baseline protocol remain undelivered (4 of 5 deliverables
  open). Item stays open at effort M — the template piece was the smallest of the five.

- **[BLD-8N4W]** Wave 3: subagent-output verification rule in building.md — a subagent's "Done" on a removal is a claim to verify
  `effort: S · impact: M · area: methodology/building · source: user · added: 2026-07-02 · status: open · stage: ready · related: MET-2X6F · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 3, Underspecified #4), methodology/building.md`

  P2. Actual weak-model failures cluster in SUBAGENT quality: premature "Done", over-broad
  allowlists, 5-15% inventory undercounts (discodon learnings — already a learning there; this
  closes the loop into methodology). Add the verification rule to building.md. (user)

- **[STH-5D8J]** Wave 3: trivial gate — add a waiver key + product-relative blast radius, or retire it
  `effort: S · impact: S · area: stop-hook · source: user · added: 2026-07-02 · status: open · stage: design · related: STH-4D2X · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 3, Overbuilt #5)`

  P2. The trivial gate hard-codes prawduct's own dir names as blast radius in product repos and
  has no waiver key (KNOWN_WAIVER_KEYS lacks "trivial"). Decision needed (patch vs retire): its
  sibling trivial fast-path already proved fileset-as-detector unsound (built 2026-05-22, fully
  retired 2026-06-08) — the third-rework-is-a-deletion-signal lens (MET-9W2P) applies. (user)

- **[MET-9W2P]** Wave 3: principle amendment proposal — the third rework of a mechanism is a deletion signal, not a patch signal
  `effort: S · impact: M · area: principles · source: user · added: 2026-07-02 · status: open · stage: idea · related: STH-5D8J · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Structural diagnosis, Wave 3), docs/principles.md`

  P2. Supported 3x in the evidence: freshness fingerprint, trivial fast-path, stop hook (reworked
  6+ times, never stabilized). Pattern: gate misfires → suppression layer added → suppression
  layer accretes its own bugs and learnings. Draft the amendment (Principle 19 — Evolving
  Principles is the vehicle) and confirm wording with the owner. (user)

- **[REL-4Q9V]** Vocabulary shrink for the change-log lifecycle — hard-remove `status=merged` and the deprecated stamp-merged machinery; one scope identifier (future major)
  `effort: M · impact: M · area: governance/change-log · source: builder · added: 2026-07-02 · status: open · stage: design · related: VWS-6R4T, REL-9F2T · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 1 Plan B "consider shrinking"), .prawduct/artifacts/build-plan-changelog-fail-loud.md (descope assumption + rationale) · reviewed: 2026-07-10`

  Deletion-over-patching candidate. Descoped from the changelog-fail-loud plan (VWS-6R4T) per
  that plan's HIGH-impact assumption. Blocked on the owner confirming the shrink is wanted once
  fail-loud validation ships — validation removes the P0 urgency. Cascade surfaces:
  `docs/release-process.md`, `stamp_merged` in `lib/views.py`, several learnings. (planning)

  **Delivery note 2026-07-10 (feature/single-pr-bookkeeping) — lifecycle half shipped; item
  stays open, narrowed to the hard-removal half.** Statusless-until-release is now the
  documented + code-supported lifecycle: `collect_release_pending_scopes` enumerates statusless
  tagged scopes; the `/prawduct:pr` merge-flow stamp step is removed (merge-flow step 6 no
  longer exists — cascade list above updated accordingly); create-flow Step 1d establishes "the
  PR carries its own bookkeeping"; `docs/release-process.md` + the template are rewritten.
  Remaining scope (deferred to a future major): drop `merged` from `VALID_STATUS_VALUES`,
  delete `stamp_merged`/`cmd_stamp_merged` (currently deprecated-but-callable with a stderr
  notice), and the "one scope identifier" vocabulary consolidation.

- **[CRT-6Q2N]** critic-consolidate's ledger anchor lacks an idempotency guard — retry in the ledger-append→remove_partials crash window lands a duplicate `review.critic` line
  `effort: S · impact: S · area: governance/critic · source: critic · added: 2026-07-13 · status: open · stage: ready · related: CRT-4B7X · refs: .prawduct/artifacts/build-plan-kernel-evidence-store.md, .prawduct/.governance-ledger.jsonl`

  The review-fact and resolution-fact appends are id-idempotent, but the ledger anchor is not: a
  retry after the crash window between ledger-append and remove_partials (or a re-materialized
  same-id manifest) lands a duplicate `review.critic` ledger line for the same review id. Benign
  today — check-cumulative-critic reads the newest qualifying event and the store fact stays
  single — but worth a guard keyed on the dispatch id. Surfaced by the Critic (NOTE),
  kernel-evidence-store chunk 03, 2026-07-13. Sibling of CRT-4B7X (same duplicate-ledger-line
  symptom via concurrent SubagentStop firings); a dispatch-id-keyed guard likely fixes both —
  merge candidates at next triage. (critic)

## Promoted

- **[GOV-4C7X]** Governance kernel redesign (v3) — SHA-keyed evidence store + coverage-algebra gates + deterministic Critic data plane
  `effort: L · impact: L · area: governance/kernel · source: user · added: 2026-07-12 · status: promoted · stage: design · related: CRT-5D8Q, GOV-7T2M, WMK-4Q9T, MIG-6B0R, CRT-9K7T · refs: .prawduct/artifacts/kernel-redesign-discovery.md, .prawduct/artifacts/kernel-inventory-2026-07-12.md, .prawduct/artifacts/build-plan-kernel-evidence-store.md, .prawduct/artifacts/kernel-v3-evidence-design.md · reviewed: 2026-07-12`

  PROGRAM-level item (true effort is XL — a program of small shippable plans; recorded `L`, the
  metadata-bar scale ceiling). Owner-approved re-architecture per the discovery artifact (owner
  decisions 2026-07-12). Concerns: evidence model (C1), deterministic data plane (C2), fail-loud
  invariant (C3), gate posture recalibration (C4), per-repo SHA-keyed store (C5),
  upstream-feedback pull path (C6), schema versioning (C7), branch-role-aware gates including
  the MIG-6B0R strip-on-promotion (C8). Subsumes the Wave 2 MECHANISM items of
  framework-efficiency-review-2026-07-02 (CRT-5M9J scope-check question, STH-8R3Q
  outcome-checking Stop gate, ENV-2W7K environments plan, CRT-3F6W reviewer-dedup deletion —
  reconcile/close those against this program as its constituent plans ship; they stay open until
  then). Also carries WMK-4Q9T's owner-decided tripwire deletion (extractor + index machinery
  removed; requirements-precede-code becomes a review-time scope-check question). External
  drivers: discodon upstream reports CRT-8F3K (local counterpart CRT-9K7T, shipped
  critic-persistence-redesign), CRT-W2NV, CRT-J4PM. Delivery posture: breaking release + doctor
  migration; opus-level model floor assumed. (user)

  **Promoted 2026-07-12** — first constituent plan authored:
  `artifacts/build-plan-kernel-evidence-store.md` (C1 evidence store + C2 review data plane,
  6 chunks, `feature/kernel-v3-evidence-store`); design note
  `artifacts/kernel-v3-evidence-design.md`. This program item stays the umbrella; later plans
  (test evidence, PR facts, C8 promotion gate, C6 feedback pull, §4.3 deletions) will be carved
  as their predecessors ship.

## Archive

- **[CRT-9K7T]** Forked `/prawduct:critic` coordinator never writes `.critic-findings.json` and leaves a stale `.critic-active` marker
  `effort: M · impact: M · area: critic · source: critic · added: 2026-07-09 · status: shipped · stage: ready · closed-by: critic-persistence-redesign · reviewed: 2026-07-09 · related: CRT-7Q2T, CRT-2K9F, STH-6T9W, CRT-6F2N · refs: skills/critic/SKILL.md, .prawduct/.critic-findings.json, .prawduct/.critic-active`

  In forked/coordinator mode (final + verify-resolutions, 3-subagent pattern), the reviewer subagents complete and return full reviews via task-notifications, but the coordinator never writes the consolidated `.prawduct/.critic-findings.json` (it stays frozen at a prior review's timestamp), and `.critic-active` is left present with a now-dead pid (must `rm -f` before the next run). Impact: stop-hook / cumulative-critic gates read a stale/foreign record, so they cannot confirm a review ran for the current changeset even though it did and all findings were resolved; the builder cannot sanctioned-ly write the file themselves, forcing a manual gate waiver every time. Observed 4x in one session on prawduct plugin v2.3.0 (discodon, filed there as CRT-8F3K, area prawduct-upstream). A related variant seen in cordyceps (2026-07-02): the forked coordinator returns BEFORE its background reviewers finish, so a network drop + re-invoke spawns a duplicate reviewer fleet (wasted cost) and aggregation only completes via a manual "aggregation-only" re-invoke. Fix-shape: make the coordinator reliably write the consolidated findings file and clear `.critic-active` on completion; consider an idempotent/resume-aggregation coordinator that reattaches to in-flight reviewers instead of re-spawning. Governance-protected → full Critic + PR review. Cross-repo (2 consumers), post-2.3.0. (critic)

- **[MET-3Q8V]** Wave 1 Plan C: prose-diet — single-source the mode/type matrix, strip the build-plan template to a filled example, fold agent-stance + delegator skills, reconcile the 5 contradictions
  `effort: L · impact: L · area: methodology/prose · source: user · added: 2026-07-02 · status: shipped · stage: ready · closed-by: prose-diet · reviewed: 2026-07-04 · related: MET-7R4J, MET-5C2H, CRT-5Q8W · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 1 Plan C, Overbuilt #3), .prawduct/artifacts/build-plan-prose-diet.md, methodology/planning.md:97-137, templates/build-plan.md:222-281, methodology/building.md:284`

  P0. Target: halve the ~31k-token governance cycle load. Moves: single-source the mode×type
  matrix (methodology only; template gets a pointer); strip build-plan template (2,774 words,
  zero filled examples) to a FILLED example + brief comments; fold agent-stance.md into the
  digest; fold the 4 one-line delegator skills (building/discovery/planning/reflection) into
  /prawduct:methodology; delete implementation narration (hook internals, bug IDs,
  withdrawn-model chains, the parser-bug narrative at build-plan.md:22-29) from files weaker
  models parse; de-Fable-ese compressed sentences; reconcile the 5 documented cross-doc
  contradictions (listed in the artifact). Largely supersedes MET-7R4J. (user)

  Promoted 2026-07-02: build plan authored at .prawduct/artifacts/build-plan-prose-diet.md
  (branch feature/prose-diet, 3 chunks). The plan pre-delivers STN-4W7R part (a) (advisor-first
  digest stance rewrite, chunk 03) and MET-2X6F's filled-example-chunk (chunk 01) — those items
  get updated at close-out, not now. MET-7R4J supersession check is a chunk 03 close-out step.

- **[VWS-6R4T]** Wave 1 Plan B: changelog-fail-loud — regen-views validates every change-log tag against the plan roster and errors loudly; tolerant chunk-ID matching
  `effort: M · impact: L · area: change-log/views · source: user · added: 2026-07-02 · status: shipped · stage: ready · closed-by: changelog-fail-loud · related: REL-9F2T, REL-2N8K, REL-6C3W, VWS-4D8J, VWS-7N3K, BLD-5J8N, REL-4Q9V · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 1 Plan B, Overbuilt #2), .prawduct/artifacts/build-plan-changelog-fail-loud.md · reviewed: 2026-07-02`

  P0. The literal-string tag DSL fails partially and SILENTLY (~12 of 71 learnings, duplicate
  incoming bugs, broke for trenchant's entire lifespan). Fix: validate every tag (`scope=`,
  `chunks=`, `status=`) against the plan roster at write/check time — no silent partial flips;
  tolerant chunk-ID matching (zero-padding, separator variants). Consider shrinking the
  vocabulary: one scope identifier; statusless-until-release as the only lifecycle. Overlaps the
  REL-9F2T silent-drop family and VWS-4D8J/VWS-7N3K — dedup pass should fold or `closes:` those
  once this is planned. Prefer deletion over patching. (user)

  — 2026-07-02: claimed by @brooks; build plan authored at
  `.prawduct/artifacts/build-plan-changelog-fail-loud.md` (branch `feature/changelog-fail-loud`).
  The "consider shrinking the vocabulary" clause is DESCOPED from that plan per the plan's
  HIGH-impact assumption (owner asked 2026-07-02, AFK, recommendation applied) — the shrink now
  lives as its own item, [REL-4Q9V].

  **Shipped 2026-07-02** on `feature/changelog-fail-loud` (chunk 01 built and Critic-cleared,
  aaaf39a): fail-loud roster validation + tolerant chunk-ID matching + `regen-views --check`
  shipped. The vocabulary-shrink clause lives on as [REL-4Q9V].

- **[GOV-7T2M]** Wave 1 Plan A: gate-noise — freshness = `test-status` exit code only (both review protocols) + work-model tripwire verb/corpus fix
  `effort: S · impact: L · area: gates · source: user · added: 2026-07-02 · status: shipped · stage: ready · closed-by: gate-noise · related: WMK-4Q9T, WMK-7D3R · refs: .prawduct/artifacts/framework-efficiency-review-2026-07-02.md (Wave 1 Plan A), .prawduct/artifacts/build-plan-gate-noise.md, skills/critic/review-protocol.md, skills/pr/review-protocol.md, lib/work_model_index.py:120-126, bin/prawduct-hook:2661-2675 · reviewed: 2026-07-02`

  P0. (1) One line in BOTH review protocols: test-evidence freshness is the `test-status` exit
  code; reviewers must never infer staleness from anything else (session-timestamp is the settled
  freshness answer — this closes the residual "reviewer eyeballs staleness" gap). (2) Tripwire:
  drop refactor/rename/redesign/rework/remove/replace from REQUIREMENT_VERBS and include doc
  subdirectories in the corpus glob (fired on the owner's own review prompt twice). Largely
  supersedes WMK-4Q9T — candidate for a `closes:` merge at dedup. High-confidence; proceed to
  planning without re-running discovery. (user)

  **Promoted 2026-07-02:** build plan active at `.prawduct/artifacts/build-plan-gate-noise.md`
  on `feature/gate-noise`. Deliverable (1) (protocol freshness lines) verified already shipped
  in PR #104 — the plan descopes it; remaining scope is the tripwire verb split + recursive
  doc corpus.

  **Shipped 2026-07-02** on `feature/gate-noise` (chunk 01, cumulative Critic clean):
  MAINTENANCE_VERBS split out of REQUIREMENT_VERBS (still orphan-exempt via _DIRECTIVE_VERBS)
  + `docs/`/`methodology/` corpus globs made recursive. Deliverable (1) was descoped — already
  shipped in PR #104 (2026-06-22, TST-4K2P: skills/critic/review-protocol.md:41,
  skills/pr/review-protocol.md:56). Dedup resolution: WMK-4Q9T is NOT closed by this — the
  supersession is partial (requirement-shape misfire + doc-subdir recall fixed here; the
  path-fragment tokenization leg remains) — WMK-4Q9T stays open, narrowed to the residual.

- **[COV-3R9K]** test-evidence double-run after a no-op commit — RUN-half closed (retired "record-after-commit" habit + `--from-counts`/`--no-rerun`); the original F4a-scope-shift diagnosis was a MISDIAGNOSIS
  `effort: M · impact: M · area: coverage · source: user · added: 2026-06-26 · status: shipped · stage: requirements · closed-by: test-evidence-single-run · related: TST-4K2P, TST-7M3K, COV-8R2K, COV-4M2J · refs: methodology/building.md, bin/prawduct-hook, .prawduct/artifacts/build-plan-test-evidence-single-run.md · reviewed: 2026-06-26`

  **RESOLVED — reframed 2026-06-26 with the VERIFIED diagnosis (closed-by=test-evidence-single-run; ships in this branch's PR, merged-pending like the rest of the bundle).** A multi-agent investigation (consumer map of every `.test-evidence.json`/`changes_referenced` reader, empirical `git diff` traces in throwaway repos, TST-4K2P/TST-7M3K history, three adversarial verifiers) corrected the original triage: the RUN-half is closed by docs + two new on-ramps, the coverage-FLOOR language gap is split out (COV-4M2J), and the originally-blamed F4a scope-shift was a MISDIAGNOSIS.

  **Verified diagnosis (replaces the original F4a framing in the upstream report below):**
  - The double-RUN is NOT gate-forced. Freshness is session-scoped (`lib/gates.py:tests_are_current`: `timestamp >= .session-start` AND `failed==0`, with NO `git_sha`/HEAD/tree-hash since TST-4K2P), and `changes_referenced` is produced by `git diff --name-only <base>` (base→working-tree, content-based), commit-invariant on a real base branch.
  - The reported `git diff base...HEAD` membership-shift was a MISDIAGNOSIS: the changed-file producers use two-arg `git diff <base>` (base→working-tree), not three-dot `base...HEAD`, so a no-op commit does not shift the set on a real base. (The only genuine no-op-commit shift is the HEAD~1 *fallback* base on repos with no `main`/`base_branch:` — advisory, addressed in resolution item 3.)
  - Root cause: a retired "record AFTER the final commit / evidence SHA must equal HEAD" habit (declared obsolete at learnings.md:270-272), not a code defect.

  **RESOLUTION — shipped in build-plan-test-evidence-single-run (scope=test-evidence-single-run):**
  1. `methodology/building.md` now prescribes record-ONCE-at-Verify and states that a commit (even a no-op) does not stale session-scoped evidence — kills the habit at its documentation source; propagates to every consumer via the plugin.
  2. The stale "Stopgap … record test-evidence as the LAST step, after committing" wording in the TST-4K2P content-hash item is marked SUPERSEDED (survives only as a quoted-obsolete reference).
  3. Suggested fix #2 (`--no-rerun`/`--restamp`) shipped as the sanctioned cheap COVERAGE-half refresh — reuse prior counts, re-stamp the timestamp, re-overlay F4a against the current tree, no suite run (covers the real surviving F4a shifts: a rename or a force-added gitignored path on a fixed base). Plus a HEAD~1-fallback-base stderr advisory naming the `base_branch:` knob.
  4. The agnosticism gap surfaced during design (the recorder was JUnit-coupled) is closed by a NEW `--from-counts passed=N failed=M skipped=K` on-ramp so non-JUnit / embedded / bespoke toolchains record evidence without faking a JUnit report.

  (Suggested fix #3 `--from-junit` was already shipped in TST-7M3K / v2.1.8 — the prior triage noted this.)

  **NOT done — deliberately rejected (pre-v1.4 + TST-4K2P):** content-/tree-hash freshness (suggested fix #1) and any `git_sha`/HEAD/commit-position field. Both were removed pre-v1.4 for chronic false positives and TST-4K2P explicitly rejected re-adding them; freshness stays session-scoped (timestamp).

  **Split out → COV-4M2J:** the Python-only coverage FLOOR (`bin/test-reference-verify` symbol-grep is Python-only; bring-your-own-verifier via `--merge-into` is the current escape for other languages) is the remaining residual.

  --- Original upstream report (scriob, prawduct 2.2.1, gitflow, per-component venvs: engine+server pytest, frontend vitest; source: incoming-bugs/test-evidence-redundant-rerun-after-noop-commit.md, archived) ---

  SYMPTOM: To satisfy the documented discipline that test-evidence must "vouch for HEAD," the operator records evidence, commits the chunk (which packages the exact same tree just tested), then must record evidence AGAIN — a second full multi-component suite run (~3-4 min) with byte-identical inputs and identical outputs. `record` always re-runs the suite; there is no "tree didn't change, just restamp" path. One chunk paid ~7 min of test time, half pure duplicate. Severity: medium (waste + trains operator to distrust a green test-status).

  COMPONENTS: `prawduct-hook test-evidence record` + `lib/coverage.py` (changed_files / reference-verify) + the methodology learning "Record test-evidence AFTER the chunk's final commit — the evidence SHA must equal HEAD". `.prawduct/.test-evidence.json` stores timestamp + changes_referenced + counts but NO git_sha at top level — nothing in the file even names the commit it's supposed to match.

  ROOT CAUSE (reporter: inferred, partially traced): `lib/coverage.py` derives the changed-file set from `git diff <base>...HEAD` (base = origin/main / main / HEAD~1) unioned with untracked files; this feeds `changes_referenced`, which `bin/test-reference-verify` later checks. The diff membership shifts the moment you commit (a modified file moves from "working-tree vs HEAD" into "in HEAD vs base"), so pre-commit evidence references a differently-scoped set than the post-commit gate recomputes — hence the re-record rule. The only refresh mechanism is a full re-run; no content-/tree-hash short-circuit, no restamp.

  SUGGESTED FIXES (any one removes the duplicate run): (1) Validate evidence by source/tree-content hash, not commit position — stamp the recording with the tree hash, have the gate compare that so a no-op commit needs no re-record (most principled; also lets methodology drop the "record AFTER final commit" rule entirely). (2) Add a restamp path: `test-evidence record --restamp`/`--no-rerun` that updates only HEAD/metadata association iff the tracked+test-file content hash matches the last recording. (3) Expose `--from-junit` in the multi-component recorder so an already-completed pytest/vitest run can be ingested instead of re-run. (4) Short-circuit `record` when the tree hash equals the last recording's. (user — upstream report from scriob)

- **[STH-3W7F]** Stop gate blocks session end while a tracked background workflow/task is still producing the diff
  `effort: M · impact: M · area: stop-hook · source: user · added: 2026-06-04 · status: shipped · stage: ready · closed-by: stop-gate-defer · related: STH-7K2A · reviewed: 2026-06-25`

  Filed by a Hallucinote session (`incoming-bugs/stop-gate-blocks-on-in-flight-background-work.md`) and
  **confirmed firsthand** in the roi-batch-2 session: the `critic-review` + `reflection` Stop gates fire
  on "tracked files changed, no Critic/reflection yet" with NO awareness of in-flight background work.
  While a background `Workflow`/`Task` is still generating the diff, ending the turn (the natural thing
  while awaiting an async run) trips the block, and every subsequent yield re-fires it until the job
  completes (roi-batch-2 absorbed ~15 block-loops over the ~12-min HOOK lane). The two available
  outcomes both misfit: SPIN (absorb a block every turn) or WAIVE — but `.gates-waived` means "cannot be
  satisfied THIS session" (`docs/waivers.md`), which is FALSE here (the gate WILL be satisfied minutes
  later), so waiving overloads the semantics and pollutes the archive with a "can't satisfy" reason for
  work that was satisfied. Distinct from [STH-7K2A] (a same-signature loop COUNTER that escalates/
  downgrades after N fires): this is about *deferral when a live tracked job exists*, not loop-counting —
  though a unified design could cover both. Remediation options (from the report): (1) background-aware
  deferral — before blocking, the Stop hook checks for a live tracked background job (workflow run dir /
  task registry) and DEFERS, re-running the gate on the next Stop after completion; (2) a first-class
  `.gates-deferred` state (reason + expected-completion) distinct from a waiver, so the archive records
  "deferred pending async run"; (3) minimal — sanction an in-flight-work waiver reason-prefix in
  `docs/waivers.md` to stop the semantic overload. Open design problem: the Stop hook is a subprocess and
  has no guaranteed handle on "is a Workflow still running" — the detection signal (a live workflow run
  dir under the session dir?) is harness-version-dependent and needs verification before (1) is viable;
  (3) is the cheap, safe floor. Filed 2026-06-04. (user)

  **DESIGN + safe floor shipped (evidence-deferral, 2026-06-04 — chunk 02).** Investigation
  corrected the framing: the report's option (3) "sanction an in-flight WAIVER" is actually WRONG —
  waiving the Critic gate while background work is in flight would SKIP the Critic the completed
  work still needs (the waiver persists the session, auto-clears next). So the agent is NOT forced
  to choose between two bad options: SPIN is the *correct* behavior (wait, then run the Critic when
  the job lands); the only real defect is the NOISE of repeated harmless blocks during a legitimate
  wait. Shipped floor: `methodology/building.md` Gate-waivers now states "in-flight background work
  is NOT a waiver case — wait, don't waive," so the semantic-overload temptation is removed.
  Detection finding (rules out option 1 for now): the Stop hook (`prawduct-hook stop`) does NOT read
  stdin, so it has no `transcript_path`/`session_id`; even if it did, inspecting
  `subagents/workflows/*/journal.jsonl` can't distinguish a LIVE run from a CRASHED one (`started >
  result` matches both; the journal persists after completion) — harness-version-dependent, unsafe
  to build. Recommended REAL fix (option 2, refined): a SELF-DECLARED `.prawduct/.gates-deferred`
  file (the AGENT knows it launched background work; the hook can't detect it) that the Stop hook
  honors to defer the gate EXACTLY ONCE, then auto-rearms (clears itself on the deferred fire) — so
  it quiets the wait WITHOUT ever permanently skipping the Critic (the next Stop re-checks normally;
  the harness's pending-background-work keeps the session alive across the deferred fire). Distinct
  archive semantics from a waiver ("deferred pending async run," not "unsatisfiable"). This needs a
  Stop-hook code change + a guard test that a deferred gate re-arms; deferred from the doc-floor
  chunk on proportionality. Could unify with [STH-7K2A] (both quiet a re-firing gate). (builder)

  Groom 2026-06-10: design is done and the floor shipped — the remaining work is just the
  `.gates-deferred` one-shot deferral (Stop-hook code + re-arm guard test). Effort dropped L → M;
  stage advanced to ready.

  RESOLUTION (2026-06-25, closed-by=stop-gate-defer): the remaining `.gates-deferred` one-shot
  deferral — the code fix left pending after the 2026-06-04 floor+design (chunk 02) — shipped, so the
  item is fully delivered and archived. The earlier `partial:` metadata note ("floor+design shipped
  via #60 (code fix pending)") is superseded by this completion; the floor+design history above is
  preserved verbatim.

- **[VWS-7N3K]** regen-views aborts the entire regen (release-notes + scope_rollups never written) when no build plan resolves; YAML-null pointer reads as the string "null"
  `effort: M · impact: H · area: views · source: report-bug · added: 2026-06-24 · status: shipped · stage: ready · closed-by: regen-views-null-plan · related: STH-5P2W, REL-4T8N, BLD-4Q9X · refs: lib/core.py (read_str_yaml_key, resolve_build_plan_path), lib/views.py (_plan_status_results, plan_regen), bin/prawduct-hook (inline _read_str_yaml_key / _resolve_build_plan_path mirrors + regen-views handler), incoming-bugs/archive/regen-views-aborts-whole-regen-when-no-build-plan-resolves.md, incoming-bugs/archive/regen-views-aborts-when-active-build-plan-is-yaml-null.md · reviewed: 2026-06-24`

  On a clean release boundary — change-log carries `status=shipped | release=vX` entries but no build plan resolves and `active_build_plan` is `null`/unset — `prawduct-hook regen-views` raises `FileNotFoundError: build-plan not found at .prawduct/null` and exits 2 BEFORE regenerating `release-notes.md` or the `scope_rollups` block. Those two views depend on NO build plan, yet a missing/absent plan aborts the whole command, blocking `docs/release-process.md` step 3 on a clean release; the consumer-facing release-notes silently goes stale. Two independent, complementary layers:

  (1) NULL LITERAL NOT NORMALIZED (originating). The column-0 pointer reader `read_str_yaml_key` (lib/core.py ~145-166) maps only EMPTY to None (`return value or None`); the truthy string `"null"` survives, so `resolve_build_plan_path` (lib/core.py ~221-226) returns `.prawduct/null` (a path that never exists). The codebase already handles this elsewhere — `_parse_build_plan_frontmatter_scope` (lib/views.py ~353) does `if not value or value.lower() in ("null","~")` — the pointer reader just doesn't mirror it. The inline `_read_str_yaml_key`/`_resolve_build_plan_path` mirror in bin/prawduct-hook has the same gap, which is why the SessionStart briefing emits the spurious `active_build_plan points at a MISSING file: 'null' resolved to .prawduct/null` warning (the STH-5P2W loud guard mis-firing on an explicit YAML-null opt-out).

  (2) ZERO-PLAN RESOLUTION ABORTS THE WHOLE REGEN. `_plan_status_results` (lib/views.py ~876-922) builds plan_paths from (a) scope-tagged release-pending plans and (b) the active_build_plan pointer plan; when BOTH are empty it enters the back-compat single-plan branch and `raise FileNotFoundError(...)`. `plan_regen` (lib/views.py ~994) calls it FIRST, before the release-notes (~997) and scope-rollups steps, so the exception takes down views that have nothing to do with build plans; bin/prawduct-hook's regen-views handler catches FileNotFoundError and exits 2 (~1559-1567). This back-compat contract predates REL-4T8N's multi-scope model, under which "no plans to update" is a legitimate clean-release state, not an error. NOTE: fixing only layer 1 is insufficient — a normalized None pointer falls back to DEFAULT_BUILD_PLAN_REL (artifacts/build-plan.md), also absent in these repos, so _plan_status_results still raises. BOTH layers need addressing.

  FIX-SHAPE (two complementary changes; either alone is a real improvement):
  - Normalize the YAML null literal at the pointer reader: treat `null`/`~` as None in read_str_yaml_key (or at minimum in resolve_build_plan_path + the bin/prawduct-hook inline mirror, kept in parity), the same way _parse_build_plan_frontmatter_scope already does. Makes `active_build_plan: null` behave like absent/empty, silences the spurious briefing warning, makes "no active plan" expressible in canonical YAML. WATCH the parity test pinning read_str_yaml_key semantics — this is a value-normalization change, not a parse change.
  - Make the status view degrade gracefully: when plan_paths is empty, _plan_status_results returns an empty/noop result (or plan_regen isolates the status step) so plan-independent release-notes + scope_rollups still regenerate. The hard FileNotFoundError back-compat contract should fire only when a plan is genuinely EXPECTED (an explicitly-pinned but missing active_build_plan), not when the project opted out of an active plan / has no resolvable plan — gate it on views_enabled + an explicitly-pinned-but-missing pointer, not on the absence of any plan.

  EVIDENCE: Reported twice from the Hallucinote repo (gitflow on develop, views_enabled, build plans without `scope:` frontmatter, no default artifacts/build-plan.md): first at prawduct v2.1.8 during the v1.6.0 release (severity medium, worked around by temporarily pointing active_build_plan at an already-shipped plan, running regen-views, then restoring null); again at v2.2.0 cutting v1.6.1 (severity escalated to high, worked around by invoking lib.views.build_release_notes_view + build_scope_view directly and writing their byte-identical outputs, skipping only the status step). Root cause traced and verified against source both times. ALSO LIVE IN THE FRAMEWORK REPO ITSELF — this session's SessionStart briefing fired the exact `'null' resolved to .prawduct/null` warning. Both incoming reports archived under incoming-bugs/archive/. Deduped from two upstream report-bug filings of the same two-layer defect (recurred across the v1.6.0 and v1.6.1 releases). (report-bug)

  RESOLUTION (2026-06-24, closed-by=regen-views-null-plan, branch fix/regen-views-null-plan-resolution): both layers landed. (1) `read_str_yaml_key` + the bin/prawduct-hook inline mirror normalize the YAML `null`/`~` literal to None. (2) `_plan_status_results` returns a no-op instead of raising when no plan resolves and the pointer is unset/null, while still raising for an explicitly-pinned-but-missing pointer. 14 new/updated tests; full suite 1449 passed, 1 skipped; dogfooded on this repo (regen-views now exits 0 with active_build_plan: null).

- **[GOV-9K2T]** Review the doctor vs janitor scope boundary — clarify the responsibility split and eliminate apparent overlap
  `effort: M · impact: M · area: governance/tooling · source: user · added: 2026-06-24 · status: shipped · stage: research · closed-by: doctor-janitor · refs: skills/doctor/SKILL.md, skills/janitor/SKILL.md, .prawduct/cross-cutting-concerns.md · reviewed: 2026-06-24`

  Surfaced during the api-design cross-cutting work, where the new API-versioning concern landed in BOTH a `/prawduct:doctor` check (#9) and a `/prawduct:janitor` theme — exposing that the line between the two skills is fuzzy. Both are framed as "health check": doctor = "health-check, repair, and maintain an already-onboarded Prawduct repo"; janitor = "periodic codebase maintenance — systematic health check across VCS hygiene, code quality, docs, tests, deps, controllability."

  Hypothesis to confirm or redraw: doctor = prawduct GOVERNANCE/install health (is this repo correctly set up and governed — install reference, distribution, anchor, core state, discovery captured, gitignore contract); janitor = the product's OWN codebase craft health (is the code/docs/tests well-maintained).

  Audit for: (1) duplicated/overlapping checks across the two skills; (2) a clear rule for which skill a new concern belongs to (or legitimately both, and why); (3) whether the API check should stay in both or consolidate. Research-stage — investigation/audit, not yet a buildable task; route to discovery to advance the stage. (user)

<!-- Bundle: test-evidence cluster — shipped in v2.1.8 (scope=test-evidence, #104).
     Shared surface: `prawduct-hook test-evidence record` (bin/prawduct-hook).
     TST-4K2P is the spine (content-based freshness identity); TST-7M3K folds in
     double-execution (--from-junit); TST-2H9P folds in configurable --tests-dir.
     Governance-protected (bin/, lib/, skills/) → full Critic + PR review. -->

- **[TST-4K2P]** Make test-evidence freshness content-based, not commit-SHA-based — a pre-commit record must not read as stale
  `effort: M · impact: L · area: test-evidence · source: user · added: 2026-06-22 · status: shipped · stage: design · related: TST-6V2N, TST-7M3K, TST-2H9P · refs: bin/prawduct-hook, lib/gates.py, skills/pr/review-protocol.md, skills/critic/review-cycle.md · closed-by: test-evidence · reviewed: 2026-06-22`

  **URGENT** (user: "a huge pain for all users", "a constant annoyance" — flagged 2026-06-22). High impact: affects every product using the prawduct PR/review flow.

  **Bundle spine** (picked 2026-06-22 with TST-7M3K + TST-2H9P → one design + build plan): the content-hash *scope decision* this item must make ("which files are test-relevant inputs") is the same question TST-2H9P answers for --tests-dir, and the runner-ownership choice in TST-7M3K decides *when* the hash is computed. Design all three in one pass.

  Problem: `prawduct-hook test-evidence record` stamps `git_sha` = HEAD at record time, but it tests the WORKING TREE (HEAD + uncommitted edits). So the natural flow "edit → run suite → record → commit" stamps the PRE-commit SHA; after committing, the stamp lags HEAD. Consumers that read the stamp then judge the evidence stale even though its CONTENT tested exactly what's shipping — the PR reviewer flagged this as a WARNING on PR #101 ("evidence ran against a tree without the fix"; false — the tree had the fix, uncommitted), and it recurs on every branch unless you remember to record AFTER committing (hit twice in the 2026-06-22 session: A1 and the critic-protocol-budget bump). The mismatch is structural, not user error.

  Proposed direction (user): judge freshness by CONTENT, independent of commit status — stamp a hash of the test-relevant file contents instead of (or alongside) `git_sha`. Then "edit → record → commit" stays current (the commit doesn't change content), and an amend/rebase/cherry-pick doesn't falsely invalidate.

  KEY design decision (why stage:design, not ready): the hash MUST be scoped to test-relevant inputs (source + tests + test config), NOT the whole tree — a naive whole-tree content hash would invalidate evidence on every `.md` edit and destroy the CRT-7M2D docs-only allowance (a doc tweak after a clean review currently rides free, and SHOULD). Options for the scope: all tracked non-`.md` non-metadata files; a declared `tests_dirs:`/source glob; or language-native coverage inputs. Decide the scope, then content-hash that set.

  Consumers to reconcile (all currently key off git_sha / commit-coverage): `test-status` (the reader), the PR-reviewer Merge-Hygiene freshness check (`skills/pr/review-protocol.md`), the Critic Goal-1 test-status check, and the cumulative-gate's HEAD-covering + CRT-7M2D docs-only-since logic in `lib/gates.py` (git_sha-based — reconcile content-freshness with the gate's commit-coverage requirement; they answer different questions).

  ~~Stopgap until shipped: record test-evidence as the LAST step, after committing, on a clean tree.~~ **SUPERSEDED (TST-4K2P, v2.1.8 + test-evidence-single-run, v2.2.3):** `git_sha` was retired and freshness is session-scoped timestamp-only, so a commit (even a no-op) does not stale evidence — record ONCE at Verify, never re-record after committing (see methodology/building.md and learnings.md:270-272). Surfaced by TEL-4M9X (A1) and critic-protocol-budget; part of the review-streamlining track.

  Cross-product corroboration + digest-mechanism suggestion (from upstream report test-evidence-git-sha-pins-parent-commit-when-tree-is-dirty.md, Scriob/halcyon, v-2026-06): a SECOND product independently hit this — record stamps git_sha=HEAD-at-record-time but tests the working tree, so in the natural 'run suite (dirty) → commit' order the stamp carries the PARENT sha (~50s wasted re-run, surfaced as a procedurally-correct-but-substantively-false Critic freshness WARNING). Concrete digest mechanism the report proposes for the content-hash: `git stash create`-style working-tree tree hash, OR a hash of (`git diff HEAD` + HEAD sha) — either makes the natural test→commit order first-class without a post-commit re-run. Corroborates the two 2026-06-22 Hallucinote hits this item already records.

- **[TST-7M3K]** test-evidence record re-runs the full suite the builder just ran — every stamp point pays for the suite twice
  `effort: M · impact: M · area: test-evidence · source: user · added: 2026-06-22 · status: shipped · stage: design · related: TST-4K2P, TST-6V2N, TST-2H9P · refs: bin/prawduct-hook (test-evidence record), methodology/building.md (Verify), incoming-bugs/archive/test-evidence-record-reruns-the-suite-the-builder-just-ran.md · closed-by: test-evidence · reviewed: 2026-06-22`

  **Bundled with TST-4K2P (spine) + TST-2H9P** (picked 2026-06-22 → one design + build plan): this is the runner-ownership leg — whether `record` runs the suite itself, accepts `--from-junit`, or `--reuse-last` determines *when* TST-4K2P's content hash is computed and which run produced the evidence.

  The build cycle says "run the suite, then record," but `test-evidence record` executes the entire suite itself rather than accepting the builder's run, so every stamp point triggers two back-to-back full-suite runs (~5 min/feature in Hallucinote). Pure wall-clock waste that scales with suite size × stamp frequency; a gate that costs double its necessary price trains the corner-cutting it exists to prevent. Distinct from TST-6V2N (created the record WRITER) and TST-4K2P (freshness IDENTITY, sha-vs-content) — this is record's double EXECUTION. Fix-shape (reporter ranks option 2): (1) record --from-junit <file> parses a runner-native junitxml the builder already produced; (2) record becomes the canonical runner (builder doesn't run separately); (3) --reuse-last. Pairs naturally with TST-4K2P's content-hash design — could be designed in one pass. Governance-protected → full Critic + PR review.

- **[TST-2H9P]** test-evidence record (F4a overlay) defaults --tests-dir to repo-root tests/ — breaks engine-subdir / monorepo layouts, writing empty changes_referenced/tests_executed halves
  `effort: S · impact: S · area: test-evidence · source: user · added: 2026-06-22 · status: shipped · stage: design · related: TST-4K2P, TST-7M3K, TST-6V2N · refs: bin/prawduct-hook (test-evidence record, bin/test-reference-verify --merge-into --tests-dir), incoming-bugs/archive/check-pr-trivial-passes-feature-clusters-that-only-touch-existing-files.md · closed-by: test-evidence · reviewed: 2026-06-22`

  **Bundled with TST-4K2P (spine) + TST-7M3K** (picked 2026-06-22 → one design + build plan): the configurable --tests-dir / source-scope this item needs is the SAME "which files are test-relevant inputs" decision TST-4K2P's content-hash scope must make — design the layout knob once and both consume it.

  Secondary finding harvested from the check-pr-trivial report (Scriob, polyglot monorepo with the engine in engine/). The test-evidence record F4a overlay step (bin/test-reference-verify --merge-into) defaults --tests-dir to repo-root tests/; with tests in engine/tests it writes an EMPTY changes_referenced/tests_executed half → false verify-coverage missing-coverage and a cumulative-Critic BLOCKING. This is the next layer after TST-6V2N ("reader without a writer" — the writer now exists but assumes repo-root tests). Worked around in-repo with a wrapper passing --tests-dir engine/tests, but the hook itself can't be told the tests dir. Fix-shape: make tests-dir configurable (a project-state.yaml knob, e.g. tests_dir:) and/or auto-detect from the layout; thread it through record's overlay. Governance-protected → full Critic + PR review.

- **[STH-5R2Q]** Flag-only `prawduct-hook` subcommands silently ignore unknown positional arguments
  `effort: S · impact: M · area: governance/cli · source: builder · added: 2026-06-10 · status: shipped · stage: ready · refs: bin/prawduct-hook · related: STH-9V4K · closed-by: hook-cli-robustness · reviewed: 2026-06-22`

  `prawduct-hook audit-learnings` (and any flag-only subcommand) silently ignores unknown positional
  arguments; this hid a test bug where `tmp_path` was passed positionally and the real repo was audited
  instead (found 2026-06-10 during review-proportionality ch.04). Tighten flag-only subcommand arg
  parsing to reject unknowns, matching ledger-append/review-stats/classify-diff-risk fail-closed arg
  handling. (builder)

  Shipped 2026-06-22 in v2.1.8, scope=hook-cli-robustness (#105).

- **[TST-3E8V]** `cmd_test_evidence` catches only FileNotFoundError for a declared test_command — widen to OSError
  `effort: S · impact: S · area: tests/runtime · source: critic · added: 2026-06-10 · status: shipped · stage: ready · refs: bin/prawduct-hook (cmd_test_evidence), tests/test_plugin_runtime.py (TestTestEvidenceKnobs) · closed-by: hook-cli-robustness · reviewed: 2026-06-22`

  `cmd_test_evidence` wraps the declared `test_command` launch in `except FileNotFoundError` only,
  so a *missing* executable gets the clean exit-2 path but a *non-executable* target raises
  PermissionError and tracebacks instead. Fix-shape: widen the except to `OSError`
  (FileNotFoundError and PermissionError are both subclasses) so any OS-level launch failure takes
  the same clean exit-2 path; add a non-executable-target case alongside the existing
  `TestTestEvidenceKnobs` coverage. Filed from the cumulative Critic NOTE on the gate-soundness
  bundle, 2026-06-10. (critic)

  Shipped 2026-06-22 in v2.1.8, scope=hook-cli-robustness (#105).

- **[REL-7P3X]** stamp-merged branch guard rejects origin/-prefixed base_branch configs
  `effort: S · impact: S · area: governance/release · source: critic · added: 2026-06-10 · status: shipped · stage: ready · refs: bin/prawduct-hook · related: PR-2H8N · closed-by: hook-cli-robustness · reviewed: 2026-06-22`

  cmd_stamp_merged (bin/prawduct-hook) compares the raw `base_branch` value from project-state.yaml
  to `git rev-parse --abbrev-ref HEAD` output; works for bare `develop` (this repo) but
  project-state.yaml's own comment calls `origin/develop` "preferred", and an origin/-prefixed value
  would make stamp-merged refuse permanently while resolve-base normalizes fine. Fix-shape: strip a
  leading `origin/` from the configured value before comparing (the guard compares local branch names
  by design — deliberate divergence from `_resolve_base_branch` is on record in the 2026-06-10
  chunk-02 Critic findings). Source: PR #90 reviewer NOTE (fable, escalate tier), same family as
  PR-2H8N. (critic)

  Shipped 2026-06-22 in v2.1.8, scope=hook-cli-robustness (#105).

- **[STH-9T4F]** Convert the two remaining non-atomic .prawduct state writes to core.atomic_write_text
  `effort: S · impact: S · area: stop-hook · source: builder · added: 2026-06-10 · status: shipped · stage: ready · related: STH-8M3V · refs: lib/critic_marker.py, lib/operator_verification.py, lib/core.py · closed-by: hook-cli-robustness · reviewed: 2026-06-22`

  Convert the two remaining non-atomic .prawduct state writes to core.atomic_write_text:
  lib/critic_marker.py:75 (critic-active marker payload) and lib/operator_verification.py:251
  (operator-verification queue rewrite). Found during STH-8M3V (gate-hardening ch.02), which
  converted the four audited sites and added the shared helper; these two were out of that item's
  groomed scope. Same rationale: readers fail open, torn writes misfire governance silently.
  (builder)

  Shipped 2026-06-22 in v2.1.8, scope=hook-cli-robustness (#105).

- **[BLD-4K7P]** `verify-chunk-refs` over-matches inline-code/prose tokens in build-plan chunk sections, producing false "missing-ref" positives
  `effort: S · impact: S · area: critic · source: critic · added: 2026-06-20 · status: shipped · stage: ready · related: BLD-2R9X, BLD-8F2Q, BLD-5V8F · refs: bin/prawduct-hook (cmd_verify_chunk_refs / _parse_build_plan_chunk_refs) · closed-by: hook-cli-robustness · reviewed: 2026-06-22`

  The Goal-2 ref-drift check (`cmd_verify_chunk_refs` / `_parse_build_plan_chunk_refs`) extracts
  backticked paths from a chunk's section and asserts they exist on disk. It misparses tokens that
  are NOT deliverables: env-var names (`PRAWDUCT_BUG_INBOX`), write-target templates with angle
  brackets (`<inbox>/<kebab-slug>.md`), URLs (`https://...`), and intentionally-gitignored paths
  (`.prawduct/.bug-inbox`). Surfaced during the upstream-bug-reporting cumulative review (HEAD
  befbcb8) — 4 false missing-ref lines, all adjudicated NOT blocking by the Critic. Fix-shape:
  tighten the extractor to skip non-path-shaped tokens (contains `<>` or `://`, or matches a
  known-gitignored managed entry), so the `new`-prefix convention is only needed for genuinely
  created files. Also a candidate learning: a ref-existence heuristic over backticked spans must
  exclude placeholder/templated/gitignored tokens or it cries wolf on legitimate plans. Same
  parser family as the shipped BLD-2R9X (glob metacharacters) and BLD-8F2Q (`path::symbol`); this
  covers token classes those two fixes don't reach. (critic)

  Shipped 2026-06-22 in v2.1.8, scope=hook-cli-robustness (#105).

- **[STH-6Q9D]** Batch git subprocess fan-out on SessionStart/Stop hot paths
  `effort: M · impact: M · area: stop-hook · source: builder · added: 2026-06-09 · status: shipped · stage: ready · refs: bin/prawduct-hook, lib/gitstate.py · closed-by: hot-path-git-batching · reviewed: 2026-06-22`

  From the 2026-06-09 framework review. cmd_clear runs ~20+ serial subprocesses (~940ms here; 5-10s
  risk on monorepos): _untrack_session_files issues 1 + up to 14 git ls-files --error-unmatch calls
  every session start (replace with one batched 'git ls-files -- <paths>'); 'git status --porcelain'
  is re-run 4-5x per clear and >=3x per stop (capture once per invocation and pass down);
  _has_product_code (lib/gitstate.py) walks the full tree via rglob including node_modules/.git
  before filtering (use pruned os.walk or git ls-files). (builder)

  Groom 2026-06-10: partial fix landed in v2.1.0 (#89 removed the no-change-session `gh pr list`).
  Remaining hot-path cost per the audit: _untrack_session_files (up to 15 git ls-files + 15 git rm
  --cached per SessionStart, bin/prawduct-hook ~L291-339 — batch into one ls-files + one rm),
  repeated `git status --porcelain` per clear/stop (capture once, pass down), and _has_product_code
  rglob walking node_modules before filtering (lib/gitstate.py ~L219-227). Still stage: ready.

  Shipped 2026-06-22 in v2.1.8, scope=hot-path-git-batching (#106).

- **[STH-4K7N]** Governance gates + critic/pr skills don't compose with git worktrees — hooks resolve `.prawduct/` to the launch dir, agent side to the session worktree
  `effort: M · impact: M · area: stop-hook · source: user · added: 2026-06-20 · status: shipped · stage: ready · related: CRT-8D2W · refs: bin/prawduct-hook, hooks/digest.py, hooks/banner.py, incoming-bugs/governance-gates-and-critic-pr-skills-dont-compose-with-git-worktrees.md · closed-by: worktree-compat · reviewed: 2026-06-22`

  Hooks resolve `.prawduct/` to the launch dir (`CLAUDE_PROJECT_DIR`) while the agent side resolves
  to the session worktree (cwd), so worktree-written reflection/critic/cumulative records are
  invisible to the Stop + cumulative-critic gates (false blocks), forcing every worktree work cycle
  off-protocol. Full fix approved: worktree-aware `get_project_dir()` resolution (stdin cwd →
  `os.getcwd()` → `CLAUDE_PROJECT_DIR` via `git rev-parse --show-toplevel`) in `bin/prawduct-hook` +
  `hooks/digest.py` + `hooks/banner.py`, empirical hook-cwd confirmation + regression tests, and
  methodology guidance to run critic/pr from the worktree. (user)

  Shipped 2026-06-22 in v2.1.8, scope=worktree-compat (#107). `lib.gitstate.resolve_project_dir`
  makes the project dir follow the session into its worktree (`git rev-parse --show-toplevel` of cwd,
  preferred over the `CLAUDE_PROJECT_DIR` pin only when cwd is a worktree of the same repo, failing
  open on any git error); `get_project_dir` delegates to it across `bin/prawduct-hook` +
  `hooks/digest.py` + `hooks/banner.py`. The broader "no documented supported worktree workflow"
  remediation (the methodology/documentation leg) remains open under CRT-6W2N, which was reframed
  2026-06-22 to the docs/methodology gap once the code-resolution leg was confirmed sound.

- **[CRT-5T8N]** Single-owner the Learnings Cross-Check & Backlog Reconciliation shared by the cumulative-Critic and the PR reviewer
  `effort: S · impact: S · area: critic · source: user · added: 2026-06-22 · status: shipped · stage: ready · related: TEL-6P2D · refs: skills/critic/review-protocol.md, skills/pr/review-protocol.md · closed-by: single-owner-shared-checks · reviewed: 2026-06-22`

  Problem: After the consume-and-audit redesign (PR reviewer audits the Critic record instead of
  re-deriving code soundness), two checklist items are still performed by BOTH the cumulative/final
  Critic and the PR reviewer: (1) Learnings Cross-Check (both scan learnings.md) and (2) Backlog
  Reconciliation (Critic does it; PR reviewer does a data-consistency variant). This duplicates prompt
  scope across two agents. It saves prompt tokens/focus, NOT wall-clock (no review run is removed) — a
  tidy, not a needle-mover; scope accordingly.

  Approach:
  - B0 (validate FIRST — Principle 15): diff the two protocols' checklists and confirm the overlap is
    TRUE duplication, not complementary work. Specifically check whether the PR reviewer's
    release-coherence/data-consistency check (change-log ↔ version ↔ backlog) catches something the
    Critic's reconciliation does not. Do NOT dedup complementary checks. If complementary, close B as
    "no-op, confirmed complementary."
  - B1: assign single ownership for the genuinely-duplicated parts — Critic owns the Learnings
    Cross-Check and the substantive Backlog Reconciliation; the PR reviewer cites the Critic's result /
    does only the thin release-coherence delta. Edit skills/critic/review-protocol.md and
    skills/pr/review-protocol.md to state the single owner explicitly.

  Assurance: must NOT drop any check — only relocate it to exactly one owner.
  Acceptance: each of the two checks has exactly one named owner across the two protocols; nothing
  silently dropped; the PR reviewer protocol explicitly references the Critic's result for the
  relocated checks. Governance-protected files (skills/) → full Critic + PR review. (user)

  Shipped 2026-06-22 on branch feature/single-owner-shared-checks: scoped the PR reviewer's
  Learnings Cross-Check + Backlog R-1 to the consumed Critic record; R-2 stays unconditional;
  review-cycle.md names final/cumulative as owner; 2 guard tests; cumulative Critic clean, PR
  reviewer clean. Archived on-branch per the ship-in-PR contract so it rides in the closing PR.
  closed-by is the branch/feature scope name (a pre-commit handle, not a SHA).

- **[TEL-4M9X]** Normalize model-id strings in the governance ledger so review-stats can analyze the model dimension
  `effort: S · impact: M · area: telemetry · source: user · added: 2026-06-22 · status: shipped · stage: ready · related: TEL-6P2D · refs: lib/telemetry.py, .prawduct/.governance-ledger.jsonl, .prawduct/artifacts/reviewer-model-ab-2026-06-10.md · closed-by: telemetry-model-id-normalization · reviewed: 2026-06-22`

  Problem: `review-stats` aggregates by `role × model × mode`, but the SAME model is recorded under
  several id strings — `opus`, `claude-opus-4-8`, and `claude-opus-4-8[1m]` are all the same model,
  while `fable`/`sonnet` are genuinely different. This fragments the model dimension into noise. The
  2026-06-22 review-stats run split critic-opus reviews across three buckets (1 + 6 + others), making
  per-model yield unreadable — which defeats the exact A/B question the telemetry was built to answer
  (see reviewer-model-ab artifact).

  Approach:
  - Canonicalize the model-id at the aggregation key in lib/telemetry.py (read-time fold) AND at
    write-time where the review.* ledger event is created, so new events are clean and the existing 41
    immutable events still aggregate correctly without rewriting the append-only ledger.
  - Collapse opus aliases (`opus`, `claude-opus-4-8`, `claude-opus-4-8[1m]`) → one canonical `opus`
    family label; keep `fable`, `sonnet`, `haiku` distinct; unknown id → passthrough.
  - Put the mapping in ONE shared helper so future model ids are a one-line add.

  Assurance impact: pure measurement/observability fix — changes no gate behavior and adds no review
  runs. Zero assurance risk.

  Acceptance:
  - review-stats shows opus variants collapsed to one bucket per (role, mode); fable stays separate.
  - The historical 41 events aggregate correctly with NO rewrite of the ledger file.
  - Unit test covers the canonicalization map (opus aliases→opus; fable→fable; unknown→passthrough).

  Open decision: normalize the aggregation key only vs. add a persisted `model_family` field —
  recommend aggregation-key normalization + shared helper (lighter; preserves the raw string). This is
  the FIRST deliverable of the evidence-driven-pruning track and must land before any per-model or
  per-leg pruning can be data-justified. Being started immediately (will be promoted on a feature
  branch off develop). (user)

  Shipped 2026-06-22 on branch feature/telemetry-model-id-normalization (lib/telemetry.py
  `_canonical_model` fold + 4 tests + docs/governance-telemetry.md + change-log entry; full suite 1355
  passed). Archived on the branch per the ship-in-PR contract so it rides in the closing PR.

- **[BKL-9K4T]** Reconcile the `closed-by:` contract with non-chunk/bare-commit work — define a stable on-branch handle and warn on the amend-dangle footgun
  `effort: S · impact: S · area: backlog · source: user · added: 2026-06-21 · status: shipped · stage: ready · related: REL-7P3X, PR-2H8N · refs: incoming-bugs/archive/backlog-closed-by-cannot-reference-its-own-commit.md, skills/backlog/SKILL.md, templates/backlog.md · closed-by: backlog-closed-by-handle · reviewed: 2026-06-21`

  Upstream report (puzzles repo via Hallucinote, prawduct v2.1.5;
  `incoming-bugs/archive/backlog-closed-by-cannot-reference-its-own-commit.md`). The `closed-by:` field is
  contracted as `<chunk-id|tag>` — an identifier that exists **before** the commit (backlog SKILL.md
  item-shape contract, the `update … closed-by=<change-log tag or chunk id>` step, and the
  `templates/backlog.md` legend line, reported as SKILL :30/:61 + template :45 in v2.1.5). That holds
  for chunked/released work, but prawduct also legitimately ships **non-chunk** items (refactors,
  chores, debt paydown) whose only stable "what shipped this" handle is the commit SHA — and a bare
  SHA is a footgun: a `git commit --amend` that folds `backlog.md` into the ship commit rewrites the
  SHA (dangling ref), and a commit cannot contain its own final SHA (chicken-and-egg), so recording
  `closed-by` correctly forces an extra "fix closed-by ref" commit.

  Fix-shape (reconcile the contract with the v2.1.6 on-branch ship rule, reported at :14): define the
  on-branch `closed-by` handle as the **branch/scope name** (or a change-log `date-slug` heading,
  which also exists before the commit) — never a bare SHA and never a PR# (assigned post-push, also
  unstable for an in-commit handle). Update the three contract sites (SKILL item-shape line, the
  `update … closed-by` step, the template legend) consistently, and have the `update <ID>
  closed-by=<bare-sha>` path **warn** about the amend-dangle and recommend the stable handle instead.
  Dedup note: distinct from REL-7P3X / PR-2H8N (release/PR-merge guard mechanics) — this is the
  `closed-by` provenance contract, not the merge flow. (user — upstream report)

- **[STH-2K8R]** `lib/critic_mode` could consume `lib/buildplan_refs` directly instead of mirroring its build-plan helpers
  `effort: S · impact: S · area: refactor · source: builder · added: 2026-06-07 · status: shipped · stage: ready · closes: CRT-3D9K · related: STH-9V4K, BLD-6Q1N · closed-by: PR #93 / v2.1.4 (bf0c889) · reviewed: 2026-06-10`

  `lib/critic_mode.py` carries independent re-implementations of `_current_chunk_id_from_status`,
  the chunk-`Type:` parser, and `_is_metadata_path` (and references `_parse_build_plan_status`),
  whose stated rationale is "no dependency on `bin/prawduct-hook` — re-implemented to stay importable
  from the slash-command shim" (critic_mode.py docstring ~L46). STH-9V4K ch.2–3 moved those helpers
  into `lib/gitstate` + `lib/buildplan_refs`, which `critic_mode` *already* imports siblings from
  (`from .core import resolve_build_plan_path`). So the mirror's reason-to-exist is now gone:
  `critic_mode` could `from .buildplan_refs import _current_chunk_id_from_status` (etc.) and
  `from .gitstate import _is_metadata_path`, deleting the duplicate bodies + their manual-sync
  docstrings. Defer until the decomposition (ch.4–7) lands so the lib surface is stable. NOT a
  behavior-preserving move (it changes critic_mode's structure + collapses a parity relationship),
  so it needs its own tests + Critic pass — kept out of ch.3 for scope discipline. Filed from the
  ch.3 buildplan_refs extraction on 2026-06-07. (builder)

  Critic note (review-fixes Chunk 1, 2026-06-09): lib/critic_mode.py contains a third porcelain
  parser that near-duplicates the new shared gitstate.parse_porcelain_line (quoted paths, renames);
  fold it onto the shared helper when consolidating this item's lib/critic_mode mirrors.

  Groom 2026-06-10: UNBLOCKED — the defer-until condition ("until the decomposition (ch.4–7) lands")
  is satisfied: STH-9V4K shipped in v2.0.14 (archived). The lib surface is stable; this is now
  directly actionable.

  — merged from CRT-3D9K (2026-06-10) — this item's consolidation closes CRT-3D9K by construction
  (CRT-3D9K's own text says so); CRT-3D9K's full original body is preserved on its archived entry.
  Audit 2026-06-10 confirmed critic_mode still carries its own _current_chunk_id_from_status
  (~L640), _count_build_plan_chunks (~L744, duplicate of lib/gates.py ~L633 — the BLD-6Q1N pair),
  and an inline porcelain parse in _get_uncommitted_code_files (~L462-474) that does NOT use
  gitstate.parse_porcelain_line despite importing gitstate. One consolidation pass closes STH-2K8R +
  CRT-3D9K + the porcelain remnant; do BLD-6Q1N in the same pass.

  Promoted 2026-06-10 into `artifacts/build-plan-critic-mode-consolidation.md` (branch
  `feature/critic-mode-consolidation`) — one consolidation chunk covering STH-2K8R + BLD-6Q1N.

  Shipped 2026-06-10 in v2.1.4 (PR #93, commit bf0c889, squash-merged to develop). Carries
  `closes: CRT-3D9K` (already archived) — CRT-3D9K's closure rides this anchor: the consolidation
  that closed it by construction shipped in PR #93 / v2.1.4.

- **[BLD-6Q1N]** Extract `_iter_status_section_items` shared parser for build-plan Status
  `effort: S · impact: S · area: build-plan · source: critic · added: 2026-05-08 · status: shipped · stage: ready · refs: lib/gates.py, lib/critic_mode.py, lib/buildplan_refs.py · related: STH-2K8R · closed-by: PR #93 / v2.1.4 (bf0c889) · reviewed: 2026-06-10`

  `_count_build_plan_chunks` (bin/prawduct-hook lines ~2073-2113, added v1.3.13) duplicates the Status-section parsing skeleton of `_parse_build_plan_status` (lines ~1021-1099): same `## Status` detection, same HTML-comment skip, same exit on next `## ` heading. Two callers is borderline; if a third caller appears (e.g., a future stop-hook check that needs chunk metadata), extract to `_iter_status_section_items(prawduct_dir) -> Iterator[StatusItem]` and refactor both call sites. Filed from /critic NOTE on 2026-05-08. (critic)

  Groom 2026-06-10 — refs refreshed post hook-decomposition (STH-9V4K, v2.0.14) and the premise is
  now STRONGER: `_count_build_plan_chunks` exists as near-duplicate copies in BOTH `lib/gates.py`
  (~L633) and `lib/critic_mode.py` (~L744), alongside `_parse_build_plan_status` in
  `lib/buildplan_refs.py` (~L31). The third-caller threshold the item set is effectively met;
  natural home for the shared iterator is lib/buildplan_refs. Overlaps the STH-2K8R consolidation —
  consider doing both in one pass.

  Promoted 2026-06-10 into `artifacts/build-plan-critic-mode-consolidation.md` (branch
  `feature/critic-mode-consolidation`) — one consolidation chunk covering STH-2K8R + BLD-6Q1N.

  Shipped 2026-06-10 in v2.1.4 (PR #93, commit bf0c889, squash-merged to develop) — one
  consolidation chunk with STH-2K8R.

- **[STH-4F7C]** Extract the duplicated Critic-freshness gate (cmd_stop vs briefing) to lib/gates.py — copies have already diverged
  `effort: S · impact: M · area: stop-hook · source: builder · added: 2026-06-09 · status: shipped · stage: ready · related: STH-9V4K, STH-6B4R, STH-2K8R · refs: bin/prawduct-hook, lib/briefing.py, lib/gates.py · closed-by: feature/gate-hardening ch.01 (04f571a) · reviewed: 2026-06-10`

  From the 2026-06-09 framework review. The mtime-vs-session-start freshness check is duplicated
  nearly verbatim (including the same STH-6B4R comment block) in cmd_stop (bin/prawduct-hook) and
  briefing._check_previous_session_gates (lib/briefing.py). Unlike the hook's intentional inline
  mirrors, this pair has no parity test and has already diverged: cmd_stop gained the
  verify-resolutions scope check; the briefing copy did not. The briefing copy lives in lib/
  already, so the import-light hot-path rationale does not apply — extract to lib/gates.py and add
  a parity/regression test. (builder)

  Groom 2026-06-10 (audit): divergence re-confirmed and sharpened — cmd_stop runs the
  verify-resolutions scope check (bin/prawduct-hook ~L787-812) but
  lib/briefing._check_previous_session_gates (~L906-934) does not, so the session-start advisory
  can report a stale verify-resolutions record as satisfying. Still stage: ready.

  Shipped 2026-06-10 on feature/gate-hardening (chunk 01, commit 04f571a): shared session
  Critic-freshness gate extracted, advisory gains the scope check. Gate-hardening bundle, delivered
  and Critic-approved this session.

- **[STH-8M3V]** Atomic writes for .prawduct state files + guard unguarded hot-path I/O in cmd_clear
  `effort: S · impact: M · area: stop-hook · source: builder · added: 2026-06-09 · status: shipped · stage: ready · related: STH-6Q9D, ADV-9K2T, STH-9T4F · refs: bin/prawduct-hook, lib/advisory_store.py, lib/gitstate.py, lib/briefing.py · closed-by: feature/gate-hardening ch.02 (cd644be) · reviewed: 2026-06-10`

  From the 2026-06-09 framework review. Only .test-evidence.json gets tmp + os.replace;
  .advisories.json (lib/advisory_store.py), .work-model-index.json, .session-start,
  .session-git-baseline, and .session-handoff.md are plain write_text — two concurrent sessions on
  the same repo (worktrees) can tear them. Readers fail open, so blast radius is a misfired gate,
  not a crash — still worth one shared atomic_write_text helper. Same pass: three unguarded I/O
  sites in cmd_clear (session-file unlink loop, .session-start write, baseline write) can traceback
  the SessionStart hook on an OSError, unlike the meticulously best-effort code around them;
  gitstate's _get_session_changed_files also lacks the (UnicodeDecodeError, OSError) guard its
  siblings have. (builder)

  Groom 2026-06-10 (audit): the unatomic set confirmed — .session-start + .session-git-baseline
  (bin/prawduct-hook ~L468, 563), .session-handoff.md (lib/briefing.py ~L868), .advisories.json
  (lib/advisory_store.py ~L333), and .gates-waived. One shared atomic_write_text helper covers all.
  Still stage: ready.

  Shipped 2026-06-10 on feature/gate-hardening (chunk 02, commit cd644be): atomic .prawduct state
  writes via shared helper + cmd_clear OSError resilience. Two out-of-scope sites spun off as
  STH-9T4F. Gate-hardening bundle, delivered and Critic-approved this session.

- **[CRT-2N7V]** /prawduct:critic explicit mode argument not honored — mode_chosen_by records inference rationale instead of explicit-args
  `effort: S · impact: M · area: governance/critic · source: builder · added: 2026-06-10 · status: shipped · stage: ready · related: CRT-3M8Q, CRT-7B4M, CRT-6J4P, CRT-9L2F · refs: skills/critic/SKILL.md · closed-by: feature/gate-hardening ch.03 (b5f0c2c) · reviewed: 2026-06-10`

  Observed 2026-06-10 on feature/do-next chunk 01: invoked the skill with args "chunk" but the
  forked Critic ran rule-1b verify-resolutions and recorded mode_chosen_by as the verbatim inference
  string, not "explicit-args" as skills/critic/SKILL.md documents. The $ARGUMENTS override path
  appears not to reach or not to be honored by the forked skill. Review validity was unaffected
  (superset scope) but the documented override contract is broken; investigate whether Skill-tool
  args reach $ARGUMENTS in forked execution. Possible regression/recurrence of CRT-3M8Q (shipped
  v2.0-era, closed-by #58), which fixed the same Skill-tool-args-don't-thread-to-$ARGUMENTS gap —
  verify whether that fix covers explicit args or only the plan-field override. (builder)

  Shipped 2026-06-10 on feature/gate-hardening (chunk 03, commit b5f0c2c): explicit mode arg now
  forwarded to infer-critic-mode; the skill never self-parses $ARGUMENTS. Post-release end-to-end
  verification tracked as CRT-9L2F. Gate-hardening bundle, delivered and Critic-approved this
  session.

- **[CRT-8W3F]** PR-gate ledger fallback accepts an arbitrarily old cumulative — no freshness/session check
  `effort: S · impact: M · area: governance/gates · source: critic · added: 2026-06-10 · status: shipped · stage: ready · related: CRT-4J8W, CRT-7M2D · refs: lib/gates.py (_ledger_fallback_record ~L1094-1121) · closed-by: feature/do-next ch.01 (59258bd) · reviewed: 2026-06-10`

  When the latest `.critic-findings.json` is wrong-mode (e.g. a chunk review overwrote the
  cumulative), check_cumulative_critic falls back to the NEWEST qualifying `review.critic` ledger
  event with no timestamp or session-freshness check — only commit-coverage. A days-old cumulative
  from prior work can satisfy the PR gate if only `.md` changed since, where the findings-file path
  would have demanded freshness. Fix-shape: require the ledger record's `ts >=` session start
  (mirroring the findings-file freshness model) or a bounded age, fail closed. Found by the
  2026-06-10 governance audit of the new v2.1.0 chain-gate code. Priority: do-next (gate soundness,
  S effort). (critic)

  Shipped 2026-06-10 on feature/do-next (scope=do-next, chunk 01, commit 59258bd); cumulative
  Critic passed with 0 blocking. Ledger fallback now requires envelope `ts >= .session-start`,
  failing closed on a missing marker or ts-less events.

- **[STH-5P2W]** Loud guard when a set active_build_plan pointer resolves to no file
  `effort: S · impact: M · area: stop-hook · source: critic · added: 2026-06-09 · status: shipped · stage: ready · related: REL-4T8N · refs: lib/core.py, bin/prawduct-hook, templates/project-state.yaml · closed-by: feature/do-next ch.02 (a5305c0) · reviewed: 2026-06-10`

  From review-fixes Chunk 1 Critic (2026-06-09). The active_build_plan pointer is
  .prawduct/-relative; a repo-relative value (the natural way to write it) mis-resolves and the
  resolvers (lib/core.py resolve_build_plan_path + the hook's inline mirror) silently fall back to
  the default plan path — disabling the Critic gate, plan-aware mode inference, and
  verify-chunk-refs with no signal. Happened live: the review-fixes planning commit shipped the
  mis-resolving form and the gates were blind for one work cycle until the Critic caught it.
  Fix-shape: when the pointer is SET but resolves to a nonexistent file, warn loudly in the session
  briefing (and/or accept repo-relative forms by stripping a leading .prawduct/) + test.
  Escape-hatches-create-silent-failures shape. (critic)

  Groom 2026-06-10 (audit): scope widened — besides the loud briefing warning + accepting
  repo-relative pointers, also document the `active_build_plan` field in
  templates/project-state.yaml: it is currently undocumented in the template a new product copies,
  and the audit found no schema guidance anywhere a product would look. Do-next priority.

  Shipped 2026-06-10 on feature/do-next (scope=do-next, chunk 02, commit a5305c0); cumulative
  Critic passed with 0 blocking. Repo-relative pointer now accepted (leading-prefix strip in both
  parity-pinned resolvers), loud briefing guard added for a set-but-missing pointer, and
  active_build_plan documented in templates/project-state.yaml.

- **[MET-6W3J]** learnings.md compaction: restore When-X-do-Y-because-Z brevity, move narrative to learnings-detail.md, add a size nudge
  `effort: M · impact: M · area: methodology · source: builder · added: 2026-06-09 · status: shipped · stage: ready · related: MET-5C2H, MET-7R4J · refs: .prawduct/learnings.md, .prawduct/learnings-detail.md · closed-by: feature/do-next ch.03 (b5439e1) · reviewed: 2026-06-10`

  From the 2026-06-09 framework review. learnings.md is ~28k tokens for 23 entries — individual
  entries run 300-600 words, drifting from the file's own stated format (rule in learnings.md, full
  context in learnings-detail.md). Every /prawduct:learnings lookup and Critic learnings cross-check
  pays this. Fix-shape: (1) compact each entry to the When/do/because rule plus a pointer into
  learnings-detail.md (move the narrative there — never delete it); (2) add a mechanical size check
  per this repo's own 'growing files need structural nudges to prune' learning (e.g. session-start
  warn when learnings.md exceeds a threshold, like the existing project-state.yaml 40KB warning).
  (builder)

  Groom 2026-06-10 (audit): learnings.md is now ~80KB on disk and growing; every
  /prawduct:learnings lookup and Critic learnings cross-check pays it. Do-next priority among the
  context-economy items.

  Shipped 2026-06-10 on feature/do-next (scope=do-next, chunk 03, commit b5439e1); cumulative
  Critic passed with 0 blocking. learnings.md 79.5KB → 32.3KB: 48 of 58 entries compacted,
  narratives moved verbatim to learnings-detail.md, navigation by same-heading convention; briefing
  size nudge added at 40KB. Drive-by fix: the briefing "Learnings (N rules)" line counted only
  bullets and reported 0 on entry-format files — now counts `##` entries.

- **[REL-9F2T]** Change-log lifecycle hardening — close the silent-drop family (statusless entries, missing entries, multi-tag entries, orphaned scopes)
  `effort: M · impact: L · area: governance/change-log · source: reflection · added: 2026-06-10 · status: shipped · stage: ready · closes: REL-2N8K, REL-6C3W, VWS-4D8J · related: VWS-3K7P, REL-4T8N, CRT-7B4M · refs: lib/views.py, skills/pr/SKILL.md, docs/release-process.md, .prawduct/artifacts/build-plan-changelog-lifecycle.md · closed-by: v2.1.1 · reviewed: 2026-06-10`

  The change-log state machine (statusless → merged → shipped) is broken at three transitions, all
  silent, all observed live: (a) the /prawduct:pr merge flow is documented to stamp `status=merged`
  but never does, so most entries reach release-prep statusless, and docs/release-process.md step 3
  literally says flip "`status=merged`" → statusless entries silently dropped (v2.0.14: 8 of 10)
  [REL-2N8K]; (b) a code-changing branch can merge with NO entry at all and nothing flags it
  (CRT-7B4M/#82, reconstructed at the v2.0.16 release) [REL-6C3W]; (c) lib/views.py
  parse_change_log stops at the FIRST `prawduct:` tag line per entry section, silently dropping
  later ones (v2.1.0 live: the reviewer-model-tiering chunks=02 tag nearly shipped unflipped)
  [VWS-4D8J]; (d) NEW from the 2026-06-10 audit: diagnose_scope_plan_coverage validates the
  scope=→plan mapping only for `status=merged` entries, so a statusless entry with a bad `scope=`
  is undetected until release. Fix as one scope: stamp `status=merged` in the /prawduct:pr merge
  step + reword release-process step 3 to "every unreleased entry, statusless OR merged"; add a
  release-prep/merge probe for code-changing diffs with no new entry; warn (or union) on multiple
  tag lines per entry; extend scope validation to statusless entries. Priority: do-next — this is
  the top release-integrity hole. Merged 2026-06-10 from REL-2N8K + REL-6C3W + VWS-4D8J; the three
  original bodies are preserved verbatim on the archived items. (reflection)

  Promoted 2026-06-10 — build plan authored at
  .prawduct/artifacts/build-plan-changelog-lifecycle.md (3 chunks: multi-tag-line union+warning,
  stamp-merged + statusless scope validation, missing-entry probe at PR create); branch
  feature/changelog-lifecycle.

  — Shipped 2026-06-10 as v2.1.1: all three chunks shipped (PR #90 squash-merged to develop as
  c7015e9). Closes the silent-drop family REL-2N8K, REL-6C3W, VWS-4D8J per the `closes:` field —
  all three already archived (dropped, merged into this item) at the 2026-06-10 groom.

- **[REL-2N8K]** Release-prep silently drops statusless change-log entries — step 3 only flips `status=merged`
  `effort: S · impact: M · area: methodology · source: builder · added: 2026-06-08 · status: dropped · stage: design · related: REL-4T8N, REL-6C3W, VWS-4D8J, REL-9F2T · reviewed: 2026-06-10`

  `docs/release-process.md` step 3 instructs the release author to flip entries "from `status=merged`
  to `status=shipped`." But the documented two-state lifecycle (set `status=merged` at the
  feature→develop merge) is manual and the `/prawduct:pr` merge flow never applies it, so most entries
  arrive at release-prep **statusless**. A literal reading of step 3 flips only the `status=merged`
  entries and silently omits every statusless one — and since `regen-views` acts only on
  `status ∈ {shipped, merged}`, those scopes' build-plan `## Status` checkboxes never flip and they
  vanish from `release-notes.md` + `scope_rollups`, with no warning. At v2.0.14, 8 of 10 unreleased
  entries were statusless (hook-decomp ch.1–7 + critic-session-guard); the release was correct only
  because the author enumerated ALL entries above the prior `release=` boundary by hand. Two fix
  options: (a) reword step 3 to "flip every unreleased entry — statusless OR `status=merged` — to
  `status=shipped`," and/or (b) make the `/prawduct:pr` feature→develop merge reliably stamp
  `status=merged` on the merged entry so the lifecycle the learnings describe actually holds. Either
  closes the silent-omission hole. (builder, from the v2.0.14 release)

  — Dropped 2026-06-10 (groom): merged into [REL-9F2T] "Change-log lifecycle hardening," which
  carries this as silent-drop transition (a). Body preserved here verbatim.

- **[REL-6C3W]** Flag a code-changing branch that merges with no change-log entry
  `effort: M · impact: M · area: release/change-log · source: reflection · added: 2026-06-08 · status: dropped · stage: design · related: REL-2N8K, REL-9F2T · refs: docs/release-process.md · reviewed: 2026-06-10`

  A non-doc-only feature branch can merge to develop with NO `.prawduct/change-log.md` entry at all,
  and nothing flags it — CRT-7B4M (#82) did exactly this, and it only surfaced at the v2.0.16
  release-prep, where the entry had to be reconstructed from the build plan to ship release-notes /
  flip the plan's Status / clear the pointer. This is a worse sibling of REL-2N8K (statusless entries
  silently dropped at release): there the entry exists but lacks a status; here there's no entry.
  Candidate fix: a PR/merge gate (parallel to check-pr-doc-only/trivial) or a release-prep probe that
  flags when `merge-base...HEAD` is not doc-only/trivial yet adds no new change-log entry. Filed from
  the v2.0.16 release (2026-06-08). (reflection)

  — Dropped 2026-06-10 (groom): merged into [REL-9F2T] "Change-log lifecycle hardening," which
  carries this as silent-drop transition (b). Body preserved here verbatim.

- **[VWS-4D8J]** regen-views silently honors only the FIRST `<!-- prawduct: ... -->` tag line when an entry section carries several
  `effort: S · impact: M · area: governance/views · source: reflection · added: 2026-06-10 · status: dropped · stage: ready · related: REL-2N8K, VWS-3K7P, REL-9F2T · refs: lib/views.py, .prawduct/change-log.md · reviewed: 2026-06-10`

  Observed live at the v2.1.0 release (2026-06-10): the reviewer-model-tiering change-log entry had
  two `<!-- prawduct: ... -->` tag lines under one `##` header (chunks=01 and chunks=02);
  regen-views flipped only chunk 01 and the only signal was the per-scope rollup count printing
  "1 chunk(s)". Same silent-drop family as REL-2N8K (statusless entries) and the shipped VWS-3K7P
  (status-value typos). Fix-shape: lib/views.py warns on stderr when an entry section contains more
  than one prawduct: tag comment (suggesting a merged chunks= list), or unions the chunk lists.
  (reflection)

  — Dropped 2026-06-10 (groom): merged into [REL-9F2T] "Change-log lifecycle hardening," which
  carries this as silent-drop transition (c). Body preserved here verbatim.

- **[CRT-3D9K]** `bin/prawduct-hook` stop-gate chunk resolution has the same views-branch blindness CRT-7B4M fixed in inference
  `effort: S · impact: S · area: critic · source: critic · added: 2026-06-08 · status: dropped · stage: requirements · related: CRT-7B4M, STH-2K8R · reviewed: 2026-06-10`

  CRT-7B4M fixed `lib/critic_mode.py` so Critic-mode inference derives the current chunk from git
  on a `views_enabled` feature branch (where the build-plan Status checkboxes are a derived view
  that never flips until release). But `bin/prawduct-hook`'s stop-gate still resolves the current
  chunk via the non-git-aware `_current_chunk_id_from_status` mirror (for chunk-`Type:` detection —
  e.g. the trivial-rationale gate), so on a feature branch it reads Chunk 01's `Type:`, not the
  chunk actually in progress. This was an explicit, user-vetoable scope boundary in the
  critic-mode-branch-fix build plan (ASSUMPTION 2); it fails safe (worst case: the gate checks the
  wrong chunk's Type, defaulting toward stricter review), so it's filed rather than fixed in that
  PR. Fix-shape: give the hook's chunk resolver the same git-aware path (or — per STH-2K8R —
  consolidate the mirrored helpers into `lib/` and have both the hook and inference consume one
  implementation, which would close this by construction). Surfaced by the CRT-7B4M cumulative
  Critic (2026-06-08). (critic)

  — Dropped 2026-06-10 (groom): merged into [STH-2K8R], whose consolidation closes this by
  construction (this item's own fix-shape says so). Body preserved here verbatim.

- **[PR-3J6W]** PR skill control-flow clarity: pre-flight guard placement, named retry entry points, Step 1b addressee, evidence retention
  `effort: S · impact: M · area: pr · source: builder · added: 2026-06-09 · status: dropped · stage: ready · related: PR-5K8D, PR-2H8N, CRT-5Q8W · refs: skills/pr/SKILL.md, skills/pr/review-protocol.md · reviewed: 2026-06-10`

  From the 2026-06-09 framework review (skills agent). (1) The release-promotion guard sits
  mid-prose after the Context Detection heading but must fire before routing — extract it as an
  explicit Pre-flight section before the routing table. (2) The three sequential STOPs (steps 2,
  2b, 3) never name their retry entry point; an agent may re-run Step 1 after fixing a Step 3
  block — add 'fix, re-run THIS gate, continue' to each. (3) Step 1b's doc-only fast-path
  instruction reads as if addressed to the Critic; rephrase as imperative to the skill executor.
  (4) Decide evidence-file retention: 'delete the evidence file with the branch' loses the audit
  trail if a PR is reverted — archive to .prawduct/.pr-reviews-archive/ or document why deletion
  is intended. Note: the doc-only fileset bug itself (skills/ treated as docs) is PR-5K8D,
  promoted into the review-fixes plan Chunk 3 — this item is the prose/control-flow cleanup only.
  (builder)

  — Dropped 2026-06-10 (groom): sub-items 1-3 verified resolved by the audit (release-promotion
  guard pre-routing via REL-8K3M; Step 2 names its re-check loop; Step 1b made imperative in #89).
  The residual sub-item 4 (evidence-file retention) merged into [CRT-5Q8W] as its sub-item (6).
  Body preserved here verbatim.

- **[CRT-1F7N]** Re-enable cumulative inference mid-build by recording per-HEAD cumulative records
  `effort: M · impact: S · area: critic · source: builder · added: 2026-05-22 · status: dropped · stage: research · reviewed: 2026-06-10`

  Chunk 03's rule 2 (cumulative) added a clean-tree guard so it doesn't over-fire mid-chunk-N. Side effect: even after the user commits chunk N, rule 2 still doesn't fire because the helper has no record that cumulative was already run for THIS HEAD — but in practice cumulative IS expensive and the user typically only wants it pre-PR. The current behavior matches the proportionality intent, but loses some signal: if the user committed and is about to PR, inference doesn't surface "you should run cumulative" — it returns `chunk` (or `final` if last chunk). Fix-shape: when the working tree is clean AND ≥2 commits ahead, return `cumulative` even though it'd take 4-10 min — the cleanness is the signal the user has stopped editing and is about to merge. Risk: false-positives on chunk boundaries where the user clean-committed but isn't about to PR. Validate against a few real chunk boundaries before changing. Filed from Chunk 03 work on 2026-05-22. (builder)

  — Dropped 2026-06-10 (groom): superseded — the /pr Step 2 gate now tells the user exactly when a
  cumulative is needed, and CRT-4J8W's chain removed the treadmill cost the mid-build inference
  nudge was meant to manage.

- **[CRT-2H8K]** `.critic-findings.json` cumulative-state file
  `effort: M · impact: S · area: critic · source: builder · added: 2026-05-05 · status: dropped · stage: idea · reviewed: 2026-06-10`

  Would let `final` reviews focus on emergent cross-chunk concerns by remembering what each `chunk` review already covered. Useful but not necessary for proportionality MVP (v1.3.13). Revisit if `final` reviews still feel slow after live use. Filed during proportional-Critic build plan as out-of-scope. (builder)

  — Dropped 2026-06-10 (groom): superseded by the v2.1.0 governance ledger, which records what each
  review covered; revisit only if final reviews still feel slow in practice.

- **[CRT-SHADOW]** (Optional) Recreate an A/B "shadow Critic" as a plugin variant
  `effort: M · impact: S · area: critic · source: builder · added: 2026-06-02 · status: dropped · stage: idea · reviewed: 2026-06-10`

  Chunk 13 retired the `critic-test` shadow skill (owner decision 2026-06-02). It was a framework-only experimental twin of `/critic` that wrote to `.critic-test-findings.json` (non-gating) for A/B-testing review-strategy changes. It was deliberately never ported to the plugin (Chunk 3), it read the now-deleted `agents/` tree, and its comparison baseline — the production Critic — now lives in the plugin. If A/B review-strategy testing is wanted again, recreate it as a **plugin** skill (`skills/critic-test/`) that forks against the plugin's bundled `skills/critic/review-protocol.md`, rather than maintaining divergent copies of the protocol. Low priority — only build if a concrete review-strategy experiment needs it. (builder)

  — Dropped 2026-06-10 (groom): superseded — the reviewer-model A/B
  (reviewer-model-ab-2026-06-10.md) was run without a shadow skill, and the ledger now provides the
  evidence base a shadow Critic was meant to supply.

<!-- v1.7.0 deferred scope — the backlog feature shipped its lean core (the /backlog skill + the single
     legacy-backlog-format probe). The items below are real requirements scope (backlog-system-requirements.md,
     post-sync-advisory-spec.md §8.2) held back on proportionality grounds: low-risk internal markdown tool,
     no current consumer. Add each when a real product needs it. Filed from the v1.7.0 release chunk (2026-05-29).
     (Comment moved to Archive with BKL-4N6X at the 2026-06-10 groom — its sibling items were already archived.) -->

- **[BKL-4N6X]** `/backlog dismiss-advisory` per-feature alias
  `effort: S · impact: S · area: backlog · source: builder · added: 2026-05-29 · status: dropped · stage: ready · reviewed: 2026-06-10`

  Requirements §8.2. A convenience alias that forwards to the existing unified `/prawduct-advisory dismiss`. The unified command already works, so this is pure ergonomics — deferred until the alias's discoverability is worth the extra surface. (builder)

  — Dropped 2026-06-10 (groom): pure ergonomics alias with no demand since filing; the requirement
  stays recorded in backlog-system-requirements.md §8.2 — re-file if a product asks.

- **[SYN-6J0R]** WIP tracking goes stale when branches merge piecemeal
  `effort: M · impact: M · area: sync · source: reflection · added: 2026-03-23 · status: dropped · stage: design · reviewed: 2026-06-10`

  Mar 23 discodon doc audit found 3 WIP branches were already merged into develop via other PRs but project-state.yaml still listed them in-progress. No mechanism reflects branch completion back to project-state.yaml when PRs merge. Consider git-based detection (branch existence on remote) or a post-merge sync step. (reflection)

  — Dropped 2026-06-10 (groom): premise stale — project-state.yaml no longer carries a WIP-branch
  list (work is tracked via active_build_plan + change-log scopes); the discodon-era mechanism it
  referenced is gone.

- **[DOC-9J4B]** F8: add Foreign-API example to hallucinote product repo
  `effort: S · impact: S · area: docs · source: critic · added: 2026-05-18 · status: dropped · stage: ready · reviewed: 2026-06-10`

  v1.4 Chunk 04 (F8) acceptance criterion called for "at least one product-repo example added (hallucinote's Ableton Live MCP work is the obvious reference)." The Ableton-MCP example was shipped as a worked illustration inside the framework (planning.md "Foreign API Verification" section + templates/build-plan.md inline example), satisfying the spirit but not the literal product-repo touch. Defer the hallucinote-side update — `**Foreign API:** ableton-live-mcp` on the relevant build-plan chunk + `verify-api` step in Done-when — to the next hallucinote session. Filed from /critic NOTE on 2026-05-18. (critic)

  — Dropped 2026-06-10 (groom): the remaining work is entirely in the hallucinote repo — re-file in
  hallucinote's backlog at the next hallucinote session.

- **[STH-9V4K]** `bin/prawduct-hook` decomposition
  `effort: L · impact: M · area: stop-hook · source: janitor · added: 2026-04-16 · status: shipped · closed-by: hook-decomp ch.1–7 (v2.0.14) · reviewed: 2026-06-10 · related: STH-2K8R`

  Split the hook monolith into logical modules. **Implementation complete (2026-06-07):** all 7 chunks built + Critic-clean, one module per PR in dependency order — ch.1 lazy `lib/__init__` (enabling), ch.2 `lib/gitstate` (#74), ch.3 `lib/buildplan_refs` (#75), ch.4 `lib/compliance` (#76), ch.5 `lib/coverage` (#77), ch.6 `lib/gates` (#78), ch.7 `lib/briefing` (the SessionStart surface — final). The hook went from **4,942 → 1,911 lines (−61%)** and is now a thin dispatcher (bootstrap + parity-pinned inline mirrors + lazy `lib` accessors + `cmd_*` wrappers + `cmd_clear`/`cmd_stop`/`main`). An AST call-graph drove the leaf-first order; the briefing↔gates↔coverage↔buildplan_refs cycle was broken by reassigning `_parse_build_plan_status` to buildplan_refs. **Remaining: the develop→main release** that flips the build-plan checkboxes `[x]` (`status=shipped` change-log tags + regen-views) — close this item then. Enabled follow-up still open: STH-2K8R (critic_mode mirror consolidation). (janitor)

  — Shipped 2026-06-08 in v2.0.14: all 7 hook-decomp change-log entries carry `release=v2.0.14 |
  status=shipped`, so the develop→main release this item was held open for has happened. Plan was
  `build-plan-hook-decomposition.md`. Archived at the 2026-06-10 groom; follow-up STH-2K8R remains
  open (now unblocked).

- **[CRT-3X9D]** Critic's no-execution constraint doesn't prevent session-mutating `prawduct-hook clear`
  `effort: S · impact: M · area: critic · source: builder · added: 2026-06-07 · status: shipped · closed-by: critic-session-guard ch.1 (v2.0.14) · reviewed: 2026-06-10 · related: STH-9V4K, CRT-7Q2T`

  The Critic skill is documented (CLAUDE.md, review-protocol) to run with restricted `allowed-tools` so
  it "cannot run test suites, builds, or executables" — review is code-analysis only. During the
  STH-9V4K ch.7 `cumulative` review the Critic nonetheless ran `prawduct-hook clear` (as a "read-only
  smoke") AND `pytest` once against the real project dir. `clear` is NOT read-only: it archived +
  deleted the builder's `.session-reflected`, rewrote `.session-start` (making fresh test evidence read
  "stale"), and recaptured the git baseline — clobbering live session governance state mid-review. The
  builder had to restore the reflection and re-record evidence. Root cause: the tool restriction must
  not actually be enforced for `prawduct-hook <subcmd>` (and pytest) the way the docs imply, OR the
  Critic agent has Bash latitude it shouldn't. Fix options: tighten the Critic's `allowed-tools` so it
  genuinely cannot invoke `prawduct-hook`/`pytest`, or make the Critic's smoke run against a temp copy /
  with a guard env var that disables session-file mutation. Either way, an independent reviewer must
  never be able to mutate the session it's reviewing. (builder)

  — Shipped 2026-06-08 in v2.0.14 (`scope=critic-session-guard`, built on branch
  fix/critic-session-guard-CRT-3X9D, plan build-plan-critic-session-guard.md): the invariant is
  enforced at the mutation site — `prawduct-hook critic-begin`/`critic-end` markers make the
  session-mutating `clear` refuse to run while a review is active (now documented in CLAUDE.md).
  Residual gap — coordinator-dispatched subagents' Bash latitude is not bound by the marker — is
  tracked separately as CRT-7Q2T. Archived at the 2026-06-10 groom.

- **[BLD-2R9X]** `verify-chunk-refs` over-matches glob paths (`*.md`) written as prose in a build plan
  `effort: S · impact: S · area: build-plan · source: critic · added: 2026-06-05 · status: shipped · closed-by: #73 (v2.0.14) · reviewed: 2026-06-10 · related: BLD-8F2Q, BLD-5V8F`

  **Resolved on branch.** `_looks_like_file_path` (`bin/prawduct-hook`, the single semantic gate the
  chunk-ref parser consults) now returns False for any backticked token carrying a shell-glob
  metacharacter (`*`, `?`, `[`) — a literal source path never contains one, so a glob written in prose
  (e.g. a Tests bullet's `docs/requirements/*.md`) is skipped instead of reported `missing-ref`. Same
  parser family as the shipped BLD-8F2Q (`path::symbol`); symbol/backlog-ref verification stays
  deferred (BLD-5V8F). 4 regression tests in
  `tests/test_build_plan_resolution.py::TestVerifyChunkRefsGlobPaths` (each glob char + the per-token
  case where a real path on the same line is still captured). Statusless change-log entry on-branch;
  flips to `merged` at develop-merge, `shipped` at release, then this item archives.

  — Shipped 2026-06-08 in v2.0.14 (change-log "verify-chunk-refs skips glob patterns written as
  prose", merged via #73, `release=v2.0.14 | status=shipped`). Archived at the 2026-06-10 groom.

- **[REL-8K3M]** `/pr` cumulative-Critic gate false-positives (benign exit-1) on a develop→main RELEASE promotion
  `effort: S · impact: S · area: release · source: reflection · added: 2026-06-06 · status: shipped · closed-by: v2.0.14 · reviewed: 2026-06-10 · related: CRT-7M2D, PR-2H8N`

  **Resolved on branch (fix-shape a+b, no gate-logic change).** `skills/pr/SKILL.md` gained a
  release-promotion guard (on `develop`/`main` → redirect to `docs/release-process.md`, don't run the
  feature-PR gates); `docs/release-process.md` gained a "`/prawduct:pr` is not the release vehicle"
  section explaining the benign `check-cumulative-critic` exit-1 is neither a gate to re-satisfy (the
  CRT-7M2D treadmill) nor a waiver case. Fix-shape (c) — broadening the CRT-7M2D allowance to version/
  derived-view files — was rejected (weakens a correct global gate to patch a context-misuse). 2 guard
  tests in `tests/test_pr_reviewer.py::TestPrReviewSkillContent`. Change-log entry is statusless
  on-branch (avoids the regen-views typo-guard); gains `status=merged` at feature→develop merge and
  `status=shipped` at the develop→main release, then this item archives.

  Original report: the `/prawduct:pr` Step 2 gate is feature→develop shaped and exit-1'd during the
  v2.0.13 release because release-prep touches non-`.md` version files (version strings +
  `regen-views`-regenerated `scope_rollups`) outside CRT-7M2D's docs-only allowance. (reflection)

  — Shipped 2026-06-08 in v2.0.14 (change-log "/prawduct:pr redirects a release promotion to the
  release process (REL-8K3M)", `release=v2.0.14 | status=shipped`). Follow-up PR-2H8N (key the guard
  off `resolve-base` instead of hardcoded branch names) remains open. Archived at the 2026-06-10
  groom.

- **[CRT-4J8W]** P0 — review-phase wall clock: accept a cumulative + verify-resolutions CHAIN at the PR gate
  `effort: M · impact: L · area: governance/gates · source: user · added: 2026-06-10 · status: shipped · closed-by: gate-soundness ch.05 (commits 9618c2b + 78fadaf) · reviewed: 2026-06-10 · stage: ready · related: CRT-7M2D · refs: lib/gates.py (check_cumulative_critic), skills/critic/SKILL.md, skills/critic/review-protocol.md, tests/test_cumulative_gate.py`

  User escalation 2026-06-10: review phase ran 30+ min wall clock for ~5 min of work. Two cost
  drivers: unit cost per review (fixed same day — reviewers default to model opus, ~4x faster per
  the reviewer-model-ab-2026-06-10.md experiment) and the **re-review treadmill**: every non-.md fix
  after a cumulative review re-stales `check-cumulative-critic` and costs a FULL bundle re-review
  even when only 2 files changed. Structural fix (the option deferred in gate-soundness ch.4 as
  "build if it recurs" — it recurred the same session):
  1. When `/prawduct:critic verify-resolutions` runs while the existing `.critic-findings.json` is a
     clean cumulative record, embed an `extends_cumulative: {commit_reviewed: <X>}` anchor in the
     new record.
  2. `check_cumulative_critic` accepts EITHER a HEAD-covering cumulative record (today's rule) OR a
     chain: `mode=verify-resolutions`, 0 blocking, `commit_reviewed==HEAD`, `extends_cumulative`
     present, AND files changed in `X..HEAD` ⊆ the record's `files_reviewed` (fail closed on any
     gap, same as today).

  Soundness argument: cumulative@X vouches for the bundle; a clean delta review whose scope covers
  `X..HEAD` extends that vouching to HEAD — same shape as the existing doc-only allowance, with
  scope verification. Surfaces: `lib/gates.py` (`check_cumulative_critic` + findings schema optional
  field), `skills/critic/SKILL.md` + `review-protocol.md` (record the anchor),
  `tests/test_cumulative_gate.py` (chain accept/reject cases incl. scope-gap fail-closed),
  `methodology/building.md` + `skills/pr/SKILL.md` sequencing prose (update: the fix-after-cumulative
  path becomes a cheap delta review, not a full re-run). Priority P0. Related: CRT-7M2D (the
  coverage-not-mtime gate this extends — archived/shipped). (user)

  — Shipped 2026-06-10 — Built as gate-soundness chunk 05 (commits 9618c2b + 78fadaf). Dogfooded on
  its own PR bundle: the chain record satisfied `check-cumulative-critic` live.
- **[CRT-6F2N]** `critic-begin` runs before the designer-handoff skip, so a designer-handoff chunk leaves the marker set
  `effort: S · impact: S · area: critic · source: critic · added: 2026-06-08 · status: shipped · closed-by: review-fixes-ch3 · reviewed: 2026-06-09 · related: CRT-3X9D`

  Critic SKILL.md step 1 runs `prawduct-hook critic-begin` right after mode resolution, but a
  `Type: designer-handoff` chunk exits clean *before* step 8 (`critic-end`), so the
  `.prawduct/.critic-active` marker is left set on that path. Benign — the marker self-corrects
  three ways (30-min TTL, session-start sweep, explicit override) — and rare, but ideally
  `critic-begin` should run only after the designer-handoff skip is ruled out (move the
  `critic-begin` call below the skip, or pair the skip with a `critic-end`). Surfaced as a NOTE in
  the CRT-3X9D cumulative review. (critic, 2026-06-08)

- **[PR-5K8D]** check-pr-doc-only should exclude skills/ (and methodology/templates) — align with `_classify_trivial_change`'s bounds
  `effort: S · impact: M · area: pr/governance · source: reflection · added: 2026-06-08 · status: shipped · closed-by: review-fixes-ch3 · reviewed: 2026-06-09 · related: PR-9T4M · refs: skills/pr/SKILL.md, lib/buildplan_refs.py, lib/coverage.py`

  The two PR fast-path classifiers disagreed on skill files. On the backlog-legend-refresh PR (#83),
  `check-pr-doc-only` returned exit 0 (all 4 files `.md` → "gates may be skipped"), which per the
  `/pr` Step 1b instruction would skip the independent PR reviewer entirely — but `check-pr-trivial`
  correctly returned "not-trivial: skill-file-edited: skills/backlog/SKILL.md. Full review required."
  A fork-skill's SKILL.md IS behavior/logic (per the existing learning "when a feature's logic lives
  in a context:fork skill, lib/ holds DATA not LOGIC"), so an extension-only doc-only classification
  under-reads a behavioral skill change and can skip review.

  Re-anchored 2026-06-08 (branch fix/retire-pr-trivial-fast-path): `check-pr-trivial` /
  `_pr_diff_is_trivial` were DELETED when the PR-boundary trivial fast-path was retired (see
  PR-9T4M). The original fix-shape pointed at `check-pr-trivial` as the model to copy; that
  classifier is gone. The canonical exclusion bounds still live in `lib/buildplan_refs.py`
  (`_classify_trivial_change` / `_TRIVIAL_PROTECTED_PATHS` — `{skills/, methodology/, templates/,
  CLAUDE.md}`), now consumed only by the chunk-level `_is_trivial_fileset_eligible` gate
  (`lib/gates.py`). This item is now MORE relevant, not less: with the trivial fast-path retired,
  `check-pr-doc-only` (`lib/coverage.py`, hook `cmd_check_pr_doc_only`) is the ONLY remaining
  PR-boundary gate-skip path, and it still under-reads behavioral `skills/*.md` changes. Candidate
  fix (re-anchored): align `check-pr-doc-only`'s fileset bounds with `_classify_trivial_change` —
  exclude `skills/`, `methodology/`, `templates/`, and `CLAUDE.md` from the doc-only fast-path so a
  behavioral-prose change still gets the reviewer; consume the shared `_TRIVIAL_PROTECTED_PATHS`
  rather than re-listing the bounds. refs: skills/pr/SKILL.md (Step 1b/1c), lib/coverage.py
  (check_pr_doc_only), lib/buildplan_refs.py (_classify_trivial_change). Filed from the v2.0.16
  release (2026-06-08). (reflection)

- **[PR-9T4M]** Trivial PR fast-path treats `bin/` + `lib/` (core runtime) as fileset-eligible — a core-runtime change can skip cumulative-Critic + reviewer
  `effort: S · impact: M · area: pr · source: builder · added: 2026-06-06 · status: shipped · closed-by: retire-pr-trivial-fast-path · reviewed: 2026-06-08 · related: STH-1W5N, BLD-2R9X`

  `_TRIVIAL_PROTECTED_PATHS` (`bin/prawduct-hook`) bounds the `Type: trivial` / `check-pr-trivial`
  fast-path to `{skills/, methodology/, templates/, CLAUDE.md}` — the governance *content* surfaces.
  It does NOT include `bin/` or `lib/`, which hold the framework's executable runtime — including
  `bin/prawduct-hook` itself (the ~4,369-line hook that *implements every gate*) and the `lib/`
  modules. Consequence (observed firsthand merging BLD-2R9X, a `bin/prawduct-hook` bugfix):
  `check-pr-trivial` returned exit 0 (`all fileset-eligible`), so the `/prawduct:pr` fast-path would
  have skipped BOTH the cumulative-Critic gate AND the independent reviewer for a change to the core
  gate-runtime. I declined the fast-path manually and ran the full review, but the next contributor
  may not. A bug in `bin/prawduct-hook`/`lib/` can break gating itself, so it is arguably *more*
  catastrophic-blast-radius than a `templates/` edit, not less. Fix-shape: add `("bin/", False,
  "runtime-edited")` and `("lib/", False, "runtime-edited")` to `_TRIVIAL_PROTECTED_PATHS` (single
  source of truth — both the stop-hook `_is_trivial_fileset_eligible` and the PR-boundary
  `_pr_diff_is_trivial` consume it), with tests in `tests/test_trivial_fileset_gate.py`. Open
  question: is a doc/comment-only edit to a `bin/`/`lib/` file (no logic change) worth exempting, or
  keep the bound coarse (any `bin/`/`lib/` touch → full review)? Coarse is safer and simpler. Filed
  from the BLD-2R9X merge on 2026-06-06. (builder)

  — Resolved 2026-06-08 (branch fix/retire-pr-trivial-fast-path) — Closed by retiring the entire
  PR-boundary trivial fast-path (`check-pr-trivial` / `_pr_diff_is_trivial` removed) rather than the
  narrower proposed fix (adding `bin/`/`lib/` to `_TRIVIAL_PROTECTED_PATHS`). With the whole
  PR-boundary fast-path gone, there is no longer any path where fileset-eligibility skips BOTH review
  gates — retiring the unsound predicate supersedes the narrower patch. Note: the chunk-level
  `Type: trivial` fileset bounds still omit `bin/`/`lib/`, but `Type: trivial` does NOT skip the
  Critic gate at the chunk level, so no gate-skip risk remains there.

- **[CRT-7B4M]** infer-critic-mode pins to Chunk 01 on a feature branch with views_enabled (derived checkboxes never flip)
  `effort: S · impact: S · area: critic · source: builder · added: 2026-06-08 · status: shipped · closed-by: critic-mode-branch-fix · reviewed: 2026-06-08 · stage: requirements`

  On a feature branch with views_enabled, build-plan ## Status checkboxes are a derived view that only flips at release, so they stay [ ] for every chunk during branch development. prawduct-hook infer-critic-mode reads the first unchecked [ ] as the current chunk → always resolves to Chunk 01, so a multi-chunk plan's later chunks all inherit Chunk 01's declared Critic mode (final, in backlog-rework) regardless of the chunk's own declared mode. Observed across all 10 backlog-rework chunks: passing an explicit /prawduct:critic <mode> arg was the workaround. Not harmful (final is the safe direction) but it makes per-chunk Critic-mode declarations inert on a branch and the mode_chosen_by rationale misleading. Research-stage: investigate whether inference should consult git-committed-chunk-count or the plan's own chunk ordering rather than the derived checkboxes. Surfaced during backlog-rework (2026-06-08).

- **[BKL-2F7K]** Ship the three remaining §8.2 backlog probes (`external-backlog-detected`, `legacy-section-schema`, `backlog-overdue-grooming`)
  `effort: L · impact: M · area: backlog · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 06) · reviewed: 2026-06-08`

  v1.7.0 shipped only `legacy-backlog-format` (the first production probe). The other three §8.2 probes are deferred — no product today has an external backlog file, an old-section-schema backlog, or a stale-grooming signal worth nagging. Build when one does. Each registers against the v1.6.0 advisory infrastructure via `register_probe("backlog", …)` in a new `lib/` probe module via `lib/advisory_store.register_probe` (the file-sync `tools/lib/backlog_probes.py` was deleted in M4) and resolves off a `project-state.yaml` fact: `external-backlog-detected` → `backlog_external_imports` (set by `/backlog import`); `legacy-section-schema` → reuse `backlog_format_version: 2` (migration folds the old `## Active`/`## Queue` headings); `backlog-overdue-grooming` → `backlog_last_groomed_at` + the 90-day window (spec §8.2). Tune the >5-item / >20-item / 90-day thresholds against a real product's backlog before shipping. (builder)

- **[BKL-3R8P]** `/backlog dedup` — surface and merge near-duplicate items
  `effort: M · impact: M · area: backlog · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 04) · reviewed: 2026-06-08`

  Requirements §4.3. A subcommand that finds candidate duplicate items (title/area/keyword overlap) and proposes merges, preserving both bodies. Not on the path to the §1 user-facing test ("pick a high-value item in 30 min"), so deferred from lean core. The `add` subcommand already does inline dedup-on-create; this is the after-the-fact sweep. (builder)

- **[BKL-5H9M]** `/backlog import <path>` — convert an external TODO/BACKLOG file into structured items
  `effort: M · impact: M · area: backlog · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 08) · reviewed: 2026-06-08`

  Requirements §4.3/§8.4. Resolves the `external-backlog-detected` probe ([BKL-2F7K]) by writing `backlog_external_imports` to `project-state.yaml`. Heuristically converts each bullet/list item in the named file into a `[PFX-XXXX]` entry (`source: user`, `status: open`, area inferred), always confirming before writing. Deferred with its probe — this repo has no external file to import. Build alongside [BKL-2F7K]'s `external-backlog-detected`. (builder)

- **[BKL-1V8J]** prawduct-doctor setup-time external-backlog report
  `effort: S · impact: S · area: backlog · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 08) · reviewed: 2026-06-08`

  Requirements/advisory-spec §8.3. At setup/health-check time, `prawduct-doctor` reports any external backlog files (`TODO.md`, `BACKLOG.md`) found in repo root + `.github/`. Redundant with the `external-backlog-detected` probe ([BKL-2F7K]); deferred with it — build both together or decide one supersedes the other. (builder)

- **[BKL-6L3Q]** Build-plan hygiene-step guidance in `templates/build-plan.md` + `methodology/building.md`
  `effort: S · impact: M · area: backlog · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 09) · reviewed: 2026-06-08`

  Requirements §5.3, decision D9. Document the backlog-hygiene step (at chunk close, review open items in the chunk's area and update status explicitly — the framework never infers status from plans/change-logs, per D4) in the build-plan template's Done-when prose and in `methodology/building.md`. Cheap, but no probe or check depends on it in lean core, so filed rather than shipped. The v1.7.0 plan already dogfoods the step informally (chunk close-out includes "backlog hygiene"); this makes it a documented standard. (builder)

- **[CRT-3K9P]** The four backlog Critic checks C-B1–C-B4
  `effort: M · impact: S · area: critic · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 05) · reviewed: 2026-06-08`

  Requirements §7. Four soft NOTE-level Critic checks for backlog hygiene (e.g. C-B3: a chunk touches an area with open backlog items but its Done-when has no backlog-hygiene step). Decision D1 made them NOTE-level; deferred because adding governance friction to *every* product's Critic run before there's evidence of need is the least proportional piece of the feature (success criterion S6 watches for fatigue). Build when backlog-hygiene drift actually shows up in reviews. (builder)

- **[JNT-7T1W]** Janitor Step 2.5 — Backlog Triage (incl. Q2 archive-split)
  `effort: M · impact: M · area: janitor · source: builder · added: 2026-05-29 · status: shipped · closed-by: backlog-rework (Chunk 07) · reviewed: 2026-06-08`

  Requirements §6. Add a backlog-triage step to the janitor: flag stale `status: open` items (`reviewed`/`added` >90d), surface neglected `## Promoted` items whose owning chunk shipped, and — the Q2 decision — when `## Archive` exceeds ~200 entries, propose splitting it to `backlog-archive.md` (with `/backlog find` spanning both files). Deferred from lean core; build when a product's backlog is large enough that grooming friction is real. (builder)

- **[CRT-7M2D]** Cumulative-Critic gate judges commit-coverage, not mtime-recency
  `effort: M · impact: M · area: critic · source: builder · added: 2026-06-04 · status: shipped · closed-by: #65 (v2.0.9) · related: STH-6B4R`

  `check-cumulative-critic` now passes iff the cumulative record covers HEAD (`commit_reviewed == HEAD`,
  or only `.md` changed since), instead of judging mtime vs `.session-start` — closing the false-pass
  (a stale record passing over real code changes) AND the post-review re-run treadmill (inert doc fixes
  no longer force a full cumulative re-run). New `tests/test_cumulative_gate.py` (8 real-git tests; the
  gate previously had none); doc wording swept "fresh" → "HEAD-covering". Dogfooded on its own PR #65
  (doc-only post-review fixes stayed covered, no re-run). Shipped v2.0.9. (builder)

- **[REL-4T8N]** Release tooling: handle MULTIPLE release-pending plans (regen-views per scope) instead of a single `active_build_plan` pointer
  `effort: M · impact: M · area: release · source: builder · added: 2026-06-04 · status: shipped · closed-by: #62 (v2.0.6)`

  The release model assumed ~one release-pending plan between `develop→main` releases: `regen-views`
  resolved THE plan via the single `active_build_plan` pointer. Batched sub-releases stack up (v2.0.5
  shipped four scopes), so the release had to point the pointer at each plan in turn and `regen-views`
  per scope — 4× tedious, easy to miss one. It also surfaced a SECOND symptom: the derived
  `release-notes.md` rendered only one entry per `release=` tag, mis-aggregating all scopes of a
  release under one heading with a union'd chunk list.

  **Resolved #62 (v2.0.6):** Chunk 01 (REL-4T8N-A) — `regen-views` now enumerates every change-log
  `scope=` (status ∈ {shipped, merged}), resolves each to its build-plan file via frontmatter `scope:`
  (`build_scope_to_plan_map`), and regenerates every release-pending plan in one pass (per-plan scope
  re-detection → no cross-scope leakage; single-plan back-compat preserved; also fixed a latent
  can't-run exit-2 state). Chunk 02 (REL-4T8N-B) — `release-notes.md` renders each distinct scope as
  its own `### ` sub-section (group-by-scope; same-scope collapses; single sub-release stays flat). The
  open "scope→file" question was answered by the existing frontmatter parser. (builder)

- **[BLD-8F2Q]** `verify-chunk-refs` misreads `path::symbol` backtick tokens as missing file paths
  `effort: S · impact: S · area: build-plan · source: critic · added: 2026-06-04 · status: shipped · closed-by: #62 (v2.0.6)`

  The chunk-ref parser (`bin/prawduct-hook` `cmd_verify_chunk_refs` / `_parse_build_plan_chunk_refs`)
  captured a whole backtick token like `lib/views.py::is_views_enabled`, saw the `/`, and treated the
  entire `module.py::symbol` string as a (missing) file path → false-positive exit 1 even though the
  file exists. **Resolved #62 (v2.0.6):** the parser splits on `::` and existence-checks only the
  pre-`::` path (stored as the ref); symbol verification stays deferred (BLD-5V8F). The `new ` forward-
  ref exclusion still composes; 6 net-new tests. (critic)

- **[PR-7Q3M]** Condition PR-skill merge-flow step 7 (build-plan deletion) on whether the develop-merge is itself the release
  `effort: M · impact: M · area: pr · source: user · added: 2026-06-02 · status: shipped · closed-by: #62 (v2.0.6) · related: BLD-3X9M`

  Under the v2.0 gitflow batched-release model, release-bound work merges feature→develop ahead of the
  develop→main release, where the release runs `regen-views` ON the build plan. Deleting the plan +
  clearing `active_build_plan` at develop-merge time left the release nothing to regenerate; step 7 also
  hardcoded `artifacts/build-plan.md`. **Resolved #62 (v2.0.6):** step 7 branches on `prawduct-hook
  resolve-base` — base = release surface (`main` family) → delete the plan (resolved via the pointer,
  not a hardcoded path) + clear the pointer; base = `develop` (release-pending) → RETAIN both until the
  release. Dogfooded on this very PR's merge (base=develop → retained). (user)

- **[TST-9K4W]** Structural tests scan `.claude/worktrees/` — leftover/in-flight workflow worktrees fail the suite
  `effort: S · impact: S · area: tests · source: builder · added: 2026-06-04 · status: shipped · closed-by: #62 (v2.0.6)`

  `test_test_location::test_all_test_files_live_under_tests_directory` and
  `test_plugin_methodology_digest::test_source_is_one_canonical_copy` globbed the whole repo tree, so a
  worktree-isolated workflow's leftover `.claude/worktrees/wf_*/` checkout (duplicate test/methodology
  copies) failed both. **Resolved #62 (v2.0.6):** both collectors prune the `.claude/` path component
  (and take a `root` param for testability); regression tests via synthetic worktree trees + a real-tree
  simulation. Layer-2 `norecursedirs` was deliberately skipped (collection is already scoped by
  `testpaths=["tests"]`). (builder)

- **[BLD-7P3K]** Guard test: assert the active build plan's chunk headings parse (fail loud on heading-format drift)
  `effort: S · impact: M · area: build-plan · source: critic · added: 2026-06-04 · status: shipped · closed-by: #61 (v2.0.5) — shipped test-only; runtime-check-for-any-product variant not pursued · related: VWS-3K7P`

  Recommended by `learnings.md` ("Build-plan chunk headings must use `### Chunk N:` colon form") AND
  twice by the roi-batch-2 cumulative Critic after the build plan itself shipped with `#### Chunk NN:`
  (four-hash, under a `### Lane` grouping level) — which silently defeated the `### Chunk ` parsers
  (`verify-chunk-refs`, `_parse_build_plan_chunk_type`, `lib/critic_mode.py` plan-override) for the
  WHOLE plan. The degradation is silent: chunk-type fail-closes to `code`, refs stop verifying, and
  nothing errors. Fix-shape: a test (or a `regen-views`/stop-hook check) that resolves the active
  build plan via `resolve_build_plan_path` and asserts its `## Status` chunk IDs each map to a
  parseable `### Chunk <id>:` heading — so a depth/format mismatch fails LOUDLY instead of degrading.
  Open question: test-only (pins the framework's own plan) vs. a runtime check that fires for any
  product's active plan. Filed from roi-batch-2 Critic NOTE on 2026-06-04. (critic)

- **[SYN-9C4T]** Extract shared `read_bool_yaml_key(state_path, key)` from `lib/views.py::is_views_enabled` and `bin/prawduct-hook::_read_bool_yaml_key`
  `effort: S · impact: S · area: sync · source: critic · added: 2026-05-19 · status: shipped · closed-by: #61 (v2.0.5) · reviewed: 2026-06-03`

  Both perform the same column-0 boolean scan against `project-state.yaml`, intentionally duplicated to keep the hook flat (one inline ~10-line helper vs. a new lib import). Move to `lib/core.py::read_bool_yaml_key(path, key) -> bool` and call from both sites. **Now more actionable (re-verified 2026-06-03):** the file-sync `product-hook` named in the original NOTE was deleted in M4; the duplicate survives in the plugin runtime as `bin/prawduct-hook::_read_bool_yaml_key` (line ~3331, comment says "kept parallel to is_views_enabled in lib/views.py") against `lib/views.py::is_views_enabled` (line ~651). The third caller the original NOTE said would tip this to extraction is already here — `_read_bool_yaml_key` now also reads `coverage_required` (bin/prawduct-hook ~3464). Filed from /critic chunk NOTE on 2026-05-19 (Chunk 09); paths refreshed post-M4. (critic)

- **[TST-5W1J]** Cache test-file contents in `bin/test-reference-verify` to drop O(N*T) re-reads
  `effort: S · impact: S · area: tests · source: critic · added: 2026-05-19 · status: shipped · closed-by: #61 (v2.0.5) · reviewed: 2026-05-29`

  `_has_reference` re-opens every test file once per changed file. Sub-second on framework scale (~20 test files × small chunk diffs) but a stronger verifier or larger product would feel it. Fix-shape: discover_tests reads all test contents into a dict once, then `_has_reference` runs substring across the cached text. Filed from /critic chunk NOTE on 2026-05-19 (Chunk 08). (critic)

- **[PRR-4M9T]** Trim PR-reviewer goals to remove Critic overlap
  `effort: S · impact: S · area: pr-reviewer · source: builder · added: 2026-05-05 · status: shipped · closed-by: #61 (v2.0.5) · reviewed: 2026-05-29`

  PR reviewer Goals 1, 2, 4, 5, 6 in `skills/pr/review-protocol.md` overlap with Critic. Now that the layering is explicit (Critic-chunk = local; Critic-final = synthesis; PR reviewer = release readiness), PR reviewer goals could be trimmed to release-specific concerns (narrative, scope, merge hygiene, simplification). Filed during proportional-Critic build plan as out-of-scope. (builder)

- **[CRT-4W8M]** Critic check: byte-exact assertions for "no behavior change" refactors
  `effort: S · impact: M · area: critic · source: reflection · added: 2026-04-16 · status: shipped · closed-by: #61 (v2.0.5) · reviewed: 2026-05-29`

  When a refactor's explicit bar is "no behavior change," substring-level test assertions are insufficient. Discodon graph_ops refactor (Apr 16) had two silent text drifts (double-prefix, error message wrapper) that substring assertions missed and Critic caught only by reading the code. Evidence: discodon/reflections.md §2026-04-16 graph_ops. Candidate: add to skills/critic/review-protocol.md for Refactor work type — "If the chunk claims no behavior change, are output assertions exact-match (not substring/contains)? If not, flag WARNING." (reflection)

- **[MET-7H2D]** Testing guidance: multi-hop edge-case tests
  `effort: S · impact: M · area: methodology · source: reflection · added: 2026-04-08 · status: shipped · closed-by: #61 (v2.0.5) · reviewed: 2026-05-29`

  When a data structure or state machine's correctness depends on what happens on the NEXT invocation (accumulator, coordinator, cursor, stateful retry), tests that only check post-state miss multi-hop bugs. Discodon has repeatedly shipped bugs caught only by the next cycle (Apr 8 accumulator, Apr 15 V0.5-7a timestamp collision under prune). Evidence: discodon/reflections.md §2026-04-08 "What I'd do differently". Candidate: add a bullet to methodology/building.md §Test Discipline — "When tested behavior depends on subsequent invocations (next cycle, next call, next prune), exercise at least one additional step beyond the immediate post-state." Broadly applicable; no detection heuristic needed. (reflection)

- **[TST-6V2N]** test-evidence freshness gate reads `.test-evidence.json` but the plugin ships no command to WRITE it
  `effort: M · impact: M · area: tests · source: user · added: 2026-06-04 · status: shipped · closed-by: #60 (72c4081, develop) · related: TST-5W1J · reviewed: 2026-06-04`

  Filed by a Hallucinote session (`incoming-bugs/test-evidence-gate-reads-a-file-the-plugin-doesnt-write.md`)
  and **confirmed firsthand** in roi-batch-2: the plugin has a READER (`cmd_test_status` freshness check +
  the cumulative-Critic staleness flag + `cmd_validate_evidence` schema check) but NO command that RUNS the
  suite and PRODUCES `.test-evidence.json` (timestamp + `git_sha` + passed/failed/skipped/duration + the
  F4a fields). `bin/test-reference-verify` writes only the F4a half (`changes_referenced`/`coverage_level`)
  via `--merge-into`; nothing writes the pytest half. Under the retired file-sync model `product-hook`
  wrote it; post-plugin-migration it's a reader without a writer. roi-batch-2 had to hand-author the
  passed/failed/git_sha/timestamp JSON and manually merge F4a — exactly the friction the prior roi-batch
  handoff flagged ("no automated test-evidence writer is wired up"). Hallucinote improvises with a local
  `tools/stamp_evidence_sha.py` shim; every product repo reinvents this. Worse, the gate's `git_sha` check
  is satisfiable by a post-commit stamp over STALE counts — nothing ties the recorded counts to a real run.
  Fix-shape: add a `prawduct-hook test-evidence record [-- <pytest args>]` subcommand that runs (or wraps)
  the suite, captures real `passed/failed/skipped/duration`, stamps `git_sha = HEAD` + ISO timestamp, calls
  `test-reference-verify --merge-into` for the F4a half, and writes atomically — so the freshness gate
  judges output the plugin itself produced + ties counts to an actual run. Watch the pytest-count parse
  (no native JSON without a plugin; parse the summary line or use exit-code + `--json-report`). Until then,
  ship the sha-stamp+schema as a documented helper so repos don't each reinvent it. Filed 2026-06-04. (user)

- **[VWS-3K7P]** Validate change-log `status=` values + reconcile views.py docstring
  `effort: M · impact: M · area: views · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  lib/views.py parse_tag_line accepts ANY status= string; only `status=shipped` flips checkboxes, so a typo (e.g. `status=shippd`) silently never flips and emits no warning — a real release-process footgun. Also the views.py module docstring (~line 19) lists status values as `shipped|in-progress|deferred` but the actual convention (docs/release-process.md, learnings.md, roi-batch entry) uses `merged` for the release-pending intermediate; in-progress/deferred are not emitted today. Fix-shape: add a pure `validate_status_values(entries) -> list[str]` helper in views.py recognizing {shipped, merged} (warn on others) and have bin/prawduct-hook cmd_regen_views print the warnings; sync the docstring to {shipped, merged}; never change the flip rule (only shipped flips). + tests. The DOC half (defining the enum in release-process.md) already shipped in a28ccaa; this is the code half. (janitor)

- **[STH-2J9F]** regen-views returns exit 0 on ImportError (silent degradation)
  `effort: S · impact: M · area: stop-hook · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  bin/prawduct-hook cmd_regen_views (~line 3673-3683) catches `from lib import views` ImportError, prints a NOTE, and returns 0 — but it is a state-mutating command, and other mutating commands (accept-operator-verification, verify-operator-verification) return 1 on ImportError per the honest-failure pattern. A user on a broken install sees exit 0 and assumes views regenerated. Fix-shape: return 1 for ImportError, keep 0 for the disabled-by-config path. + test. (janitor)

- **[STH-6B4R]** Gate freshness timestamp comparison is lexicographic / tie-ambiguous
  `effort: M · impact: M · area: stop-hook · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  The stop-hook Critic gate (bin/prawduct-hook ~2579-2594) and check-cumulative-critic (~3616-3627) compare ISO-8601 string mtimes (`.session-start` vs findings mtime). Same-second ties are ambiguous and the precision contract is undocumented/untested. Fix-shape: format both sides to identical %Y-%m-%dT%H:%M:%SZ precision and TEST the tie case (findings_mtime == session_start must be rejected as not-fresh), or switch to numeric epoch seconds. Document the tie-breaking rule. (janitor)

- **[TST-7Q3D]** Stop-gate regression coverage gaps (verify-resolutions, trivial-fileset, waiver unknown-key)
  `effort: M · impact: M · area: tests · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  TestPluginStopGate is missing three regression cases: (a) verify-resolutions mode out-of-scope file blocking — findings with files_reviewed=[a.py], diff modifies [a.py,b.py] -> assert exit 2 out-of-scope (bin/prawduct-hook ~2198); (b) Type: trivial chunk modifying files outside the allowed bounds -> assert exit 2 fileset reason (~2536-2564); (c) gate-waiver unknown key -> assert stderr diagnostic WITHOUT blocking (~2438-2447). All test-only, no runtime change. (janitor)

- **[TST-4H8M]** Unit coverage for migrate `_collapse_blank_runs` edge cases
  `effort: S · impact: S · area: tests · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  lib/migrate_plugin.py _collapse_blank_runs (~264-273, added by MIG-8C3V) has no dedicated unit tests for 3/4/5/7+ consecutive newlines, only-newlines, empty string, or while-loop convergence (e.g. `a\n\n\nb\n\n\nc` -> `a\n\nb\n\nc`). Currently only covered indirectly via the end-to-end migrate test. Add a TestCollapseBlankRuns class. (janitor)

- **[VWS-8M2Q]** Harden lib/views.py tag/frontmatter parsers (quote-in-chunk-id, unclosed HTML comment)
  `effort: S · impact: S · area: views · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  Two low-impact parser corners in lib/views.py: (a) chunk IDs from parse_tag_line are quoted verbatim into scope_rollups YAML (~368-384) without escaping — a chunk id containing a quote (malformed tag) produces unparseable YAML; CHUNK_LINE_RE guards the build-plan file but not tag-line input. (b) _parse_build_plan_frontmatter_scope (~165-170) silently treats an UNCLOSED HTML comment block as missing frontmatter (returns (False,None)) rather than flagging it; the v1.5.1 R5 'explicit malformed-frontmatter test' was never added. Fix-shape: validate/escape chunk IDs (or yaml.safe_dump); raise or explicitly document unclosed-comment leniency + add the malformed-frontmatter test. (janitor)

- **[ADV-9K2T]** advisory_store read/write failures degrade silently (no corruption surfacing)
  `effort: M · impact: M · area: advisory · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  lib/advisory_store.py best-effort read/write falls back to safe defaults on any failure, so a corrupted `.advisories.json` is silently reset with no signal — the user never learns their advisory state was lost. Fix-shape: on a parse/read failure, drop a `.advisories.json.corrupt` sentinel (or log) so corruption is surfaced on next session start for user-initiated recovery, instead of silently swallowed. (janitor)

- **[STH-1W5N]** Centralize the trivial-change protected-path bounds into a documented constant
  `effort: S · impact: S · area: stop-hook · source: janitor · added: 2026-06-04 · status: shipped · closed-by: #59 (a91d156, develop) · related: STH-4D2X · reviewed: 2026-06-04`

  The Type: trivial / doc-only fileset bounds (skills/, methodology/, templates/, CLAUDE.md, test deletions, new files) are enforced inline in bin/prawduct-hook (~3120-3180) with no central spec. Extract to a documented module-level `_TRIVIAL_PROTECTED_PATHS` frozenset (lib/core.py or bin/prawduct-hook) with a rationale per path, referenced from all call sites. Relates to STH-4D2X (the `.claude/skills/` bound question). (janitor)

- **[TST-1D5W]** Tighten `_validate_evidence_schema` against bool-as-int
  `effort: S · impact: S · area: tests · source: critic · added: 2026-05-05 · status: shipped · closed-by: #59 (a91d156, develop) · reviewed: 2026-06-04`

  Python's `bool` is a subclass of `int`, so `{"passed": True}` slips through `isinstance(v, int)` in the test-evidence validator. No real test runner emits booleans for these fields, so impact is theoretical, but the loophole is real. If addressed: add `or isinstance(v, bool)` exclusion to the type check (with a comment), and add a `TestValidateEvidenceSchema::test_bool_rejected_for_int_field` case. Filed from /critic NOTE on 2026-05-05. (critic)

- **[CRT-3M8Q]** `/critic` ignores the build plan's per-chunk `Critic mode:` override — Skill-tool args don't thread to `$ARGUMENTS`, so a plan-mandated `final` silently runs as inferred `chunk`
  `effort: M · impact: M · area: critic · source: reflection · added: 2026-06-01 · status: shipped · closed-by: #58 (befd69b, develop) · related: CRT-1F7N · reviewed: 2026-06-04`

  The `/critic` skill ignores the build plan's per-chunk `**Critic mode:**` field, and Skill-tool args don't thread to its `$ARGUMENTS`, so a plan-mandated `final` override silently runs as inferred `chunk` mode. Discovered in v2.0.0 Chunk 9 (a destructive cutover whose plan overrode the mode to `final`): the independent Critic ran clean goals 1-3 twice but goals 4-7 were never run by the agent (`mode_chosen_by: rule-4`, not `explicit-args`). The methodology already says the per-chunk `Critic mode:` should be a "successive override," but the skill doesn't read it and the Skill-tool args never reach the forked skill, so the override is inert. Fix-shape: (a) have the `/critic` skill read the active build plan's per-chunk `**Critic mode:**` field as an override (matching the methodology's "successive override" intent), and/or (b) fix Skill-tool args reaching the forked skill's `$ARGUMENTS`. Type: process/governance. Priority: medium. Filed from v2.0.0 Chunk 9 reflection on 2026-06-01. (reflection)

- **[BLD-4Q9X]** `scope: null` in build-plan frontmatter does not suppress change-log inference
  `effort: M · impact: M · area: build-plan · source: critic · added: 2026-05-23 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  Surfaced by v1.5.1 Chunk 05 cumulative Critic. The template ships `scope: null` as the documented opt-out form, and `_parse_build_plan_frontmatter_scope` correctly returns `None` for null literals. But `_detect_active_scope` then treats "key present with null" identically to "key absent" — it falls through to change-log inference, picking up the most-recent `scope=` tag. Result: a product with a tagged release in change-log.md (e.g. `scope=v1.5`) plus a fresh `scope: null` build-plan with new chunks 01/02/03 will see `regen-views` flip those chunks to `[x]` because v1.5's tagged entries claim chunks 01/02/03. Author's explicit-null intent ("don't filter") is overridden silently. Fix-shape: distinguish "key absent" from "key present with null/empty" in `_parse_build_plan_frontmatter_scope` (return a sentinel or change to `tuple[bool, str | None]`); have `_detect_active_scope` skip inference when key was explicitly null. Doesn't bite the framework's own v1.5.1 plan (sets `scope: v1.5.1` explicitly). Filed from /critic cumulative WARNING on 2026-05-23 (v1.5.1 Chunk 05). (critic)

- **[TST-2R7H]** Add fixture coverage for `cumulative-final`/`cleanup` Type fall-through to default gate
  `effort: S · impact: M · area: tests · source: critic · added: 2026-05-18 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  Code analysis confirms only `designer-handoff` skips the Critic gate; the other Type values (`code`, `doc-only`, `cleanup`, `cumulative-final`) all fall through to the default gate path. But no dedicated test fixture pins this — `TestDesignerHandoffSkipsCriticGate` only covers the explicit skip branch. A refactor that accidentally broadens the skip list (e.g. `if chunk_type in {"designer-handoff", "doc-only"}`) would silently regress. Fix-shape: add a parametrized `TestNonHandoffTypesFallThroughToGate` covering the four fall-through Types. Filed from /critic cumulative NOTE on 2026-05-18. (critic)

- **[MIG-8C3V]** migrate's CLAUDE.md transform leaves a double blank line at the top of the migrated file
  `effort: S · impact: S · area: migration · source: user · added: 2026-06-02 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  When `apply_claude_anchor` strips the framework generator comments via `_drop_generator_comments` (`lib/migrate_plugin.py`), it removes the comment lines but leaves the blank line that preceded them adjacent to the blank line that followed, producing two consecutive blank lines between the H1 title and the first product section. Cosmetic only (markdown collapses it on render), zero semantic impact, but it's a wart in a diff meant to be pristine. Found during the v2.0.0 1.x→2.x migration acceptance test against ../discodon (2026-06-02). Fix: collapse 3+ consecutive newlines to 2 in the assembled CLAUDE.md, or drop blank lines left adjacent to removed generator comments. Low priority / trivial. (user)

- **[MET-4K8Z]** 8-surface cascade pattern — anticipate token-budget pressure in chunk plans
  `effort: S · impact: M · area: methodology · source: reflection · added: 2026-05-18 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  Chunk 05's source-of-truth guardrail threading touched 8 surfaces (product-claude / Critic SKILL / 2 critic-review / 2 pr-review / methodology / build-plan template). Same pattern Requirements Precede Code (v1.3.15) hit. When a chunk introduces a project-wide structural concept, the plan should enumerate the surface count up front so token-budget bumps (and the aggressive trim that precedes them) are anticipated, not discovered. Worth promoting to methodology after one more datapoint; until then, captured as observation. Filed from Chunk 05 reflection, 2026-05-18. (reflection)

- **[MET-1T5W]** Document the `new \`path\`` forward-ref convention in methodology prose
  `effort: S · impact: S · area: methodology · source: critic · added: 2026-05-18 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  `verify-chunk-refs` (F3) supports `new \`path/to/file\`` syntax to mark forward-references for not-yet-created files; this is implemented, tested, and documented inside `templates/build-plan.md`'s inline HTML comment, but not in `methodology/planning.md` prose. Authors who write plans without copying the template won't know the keyword exists and will get spurious BLOCKING ref-drift findings for chunks creating new files. Fix-shape: add a one-paragraph "Forward-references" note to planning.md near the build-plan-structure section. Filed from /critic cumulative NOTE on 2026-05-18. (critic)

- **[MET-8N2C]** Tighten F8 worked-example numbering language for consistency
  `effort: S · impact: S · area: methodology · source: critic · added: 2026-05-18 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  `methodology/planning.md:118` describes the `verify-api` step as "the first item in its Done-when", while the worked example a few lines down uses "step 0" (`0. verify-api: ...`). Both true, but the terminology is inconsistent. Fix-shape: change line 118 to "prepended as step 0 in its Done-when (so existing step numbering is preserved across chunks with and without a foreign API)". One-line tweak. Filed from /critic cumulative NOTE on 2026-05-18. (critic)

- **[MET-2D9K]** `methodology/planning.md` parallel section for the `Visual change:` build-plan field
  `effort: S · impact: S · area: methodology · source: critic · added: 2026-05-18 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  F8 added a "Foreign API Verification" section to planning.md when introducing `**Foreign API:**`. F10 (Chunk 14) added `**Visual change:**` to the build-plan template with inline-comment guidance but no parallel planning.md section. The build-plan template's HTML comment is sufficient discoverability for v1.4.0; consider a v1.5 enhancement (~50 tokens) to align with the F8 precedent and pre-empt the asymmetry NOTE the Critic emitted. Filed from /critic Chunk 14 final review NOTE. (critic)

- **[DOC-2W9P]** Repoint stale `tools/lib/` example paths in `documentation/` design specs to plugin-native
  `effort: S · impact: S · area: docs · source: builder · added: 2026-06-03 · status: shipped · closed-by: #58 (befd69b, develop) · reviewed: 2026-06-04`

  `documentation/post-sync-advisory-spec.md` (≈ lines 197/218/276/296/434/435) and
  `documentation/governance-tax-followups.md` §3 still illustrate the advisory/probe layout with
  retired file-sync paths (`tools/lib/probes/…`, `tools/product-hook`, `prawduct-setup.py`, `run_sync`).
  The spec is still the authoritative reference for `lib/advisory_store.py`, so the illustrative paths
  should point at `lib/advisory_store.py` / `hooks/hooks.json` / `bin/prawduct-hook`. Internal design
  archive, not user-facing — deferred from the 2.0-rock-solid pass Wave 2. (builder)

- **[ADV-3K7Q]** Namespace skill names in plugin advisory output (briefing recommended_action + dismiss hint)
  `effort: S · impact: S · area: advisory · source: critic · added: 2026-06-03 · status: shipped · closed-by: #53 (12e03b3, v2.0.3) · reviewed: 2026-06-03`

  Surfaced when the advisory-probe-at-SessionStart fix made post-sync advisories visible in plugin repos for the first time. The briefing rendered un-namespaced skill forms (`/backlog migrate`, `/prawduct-advisory dismiss`) where a plugin repo resolves `/prawduct:backlog` / `/prawduct:advisory`. info-priority/cosmetic; not a broken gate.

  **Shipped (#53 — `fix(plugin): namespace all agent-facing command forms in the plugin runtime`, commit `12e03b3`, in develop/v2.0.3):** the runtime gate-message + advisory-output sweep landed. `bin/prawduct-hook` now renders `/prawduct:advisory` (0 bare `/prawduct-advisory` remain) and `/prawduct:critic`/`/prawduct:pr` in every agent-facing gate; `lib/operator_verification.py`'s `/pr create` stragglers namespaced. Pinned by `TestPluginRuntimeNamespacing` (assert-absent source-scan) + strengthened stop-gate/divergence tests. The byte-parity-lock half (`backlog_probes` → `DIVERGED_MODULES`) is moot: `lib/backlog_probes.py` and its frozen `tools/lib/` twin were both deleted in M4 (v2.0.3, Chunk 3) along with the `legacy_backlog_format_probe`, so source #1 no longer exists. The stale standalone branch `origin/fix/advisory-namespace-backlog` (single commit, same title/SHA-content as #53) was superseded by the merged PR and can be deleted. (Triage 2026-06-03 — the "do not archive until merged" hold is satisfied: the work is in HEAD.)

- **[CRT-2M5P]** Critic skill `Bash(git *)` allowed-tools is too broad — permits state-mutating git verbs (checkout/stash/reset/branch)
  `effort: S · impact: M · area: critic · source: critic · added: 2026-05-23 · status: shipped · closed-by: reduce-governance-tax Chunk E · reviewed: 2026-05-29`

  Observed v1.5.1 Chunk 05 verify-resolutions: the Critic ran `git checkout d2b8af4` (mid-review!), corrupted the working tree to a detached HEAD state, and recovered via stash+pop. All my modified files survived but only because the Critic chose to restore them. The skill `allowed-tools` entry `Bash(git *)` permits every git subcommand including ones that mutate the working tree. Read-only verbs are sufficient for Critic's review purpose. Fix-shape: replace `Bash(git *)` with an explicit allow-list of read-only verbs — `Bash(git diff *)`, `Bash(git log *)`, `Bash(git status *)`, `Bash(git show *)`, `Bash(git ls-files *)`, `Bash(git rev-parse *)`, `Bash(git merge-base *)`, `Bash(git branch --show-current)`, `Bash(git for-each-ref *)`. Or, more concise, add a deny-list (subject to the same v1.5.1 Chunk 02 caveat that skill-frontmatter denies may not enforce). Filed from /critic verify-resolutions NOTE on 2026-05-23 (v1.5.1 Chunk 05). (critic)

  **Resolved (reduce-governance-tax Chunk E):** The Critic's `allowed-tools` now grants explicit read-only git verbs (diff/log/status/show/ls-files/rev-parse/merge-base/branch --show-current/for-each-ref) instead of the broad `Bash(git *)`, so a review can no longer run `git checkout`/`reset`/`stash` and corrupt the tree. Applied to `.claude/skills/critic/SKILL.md`, `templates/skill-critic.md`, and the `critic-test` shadow skill; pinned by `test_critic_skill_metadata.py::test_git_is_read_only`.

- **[CRT-8H3D]** v1.5.1 Chunk 02's `!Bash(pytest*)` deny patterns in skill `allowed-tools` do NOT structurally block pytest invocation
  `effort: M · impact: M · area: critic · source: critic · added: 2026-05-23 · status: shipped · closed-by: reduce-governance-tax Chunk E · reviewed: 2026-05-29`

  Confirmed by v1.5.1 Chunk 04 Critic WARNING: the Critic agent ran `python3 -m pytest` despite the four deny patterns in `.claude/skills/critic/SKILL.md` `allowed-tools`. The patterns appear to be documentation-only; Claude Code's skill `allowed-tools` field is allow-list semantics and the `!`-prefixed deny syntax is not honored there (or is overridden by project-level `settings.local.json` `permissions.allow: ["Bash(python3:*)"]`). Fix-shape options: (1) move deny patterns to `.claude/settings.json` `permissions.deny` (project-wide block — but would also block the *builder* from running pytest, which is wrong); (2) scope deny via a wrapper command or use a tool-namespace filter the harness actually enforces; (3) accept that the constraint is prose-and-allow-list only (the allow-list IS restrictive — `Bash(python3 tools/product-hook ...)` exact-strings shouldn't match pytest in pure-allow mode), and soften the v1.5.1 change-log / memory rule claim of "structurally enforced". Add a deliberate negative-path probe test before claiming structural enforcement. Filed from /critic chunk WARNING on 2026-05-23 (v1.5.1 Chunk 04). (critic)

  **Resolved (reduce-governance-tax Chunk E):** Structural enforcement is the PURE-ALLOW list (the `!Bash(...pytest*)` entries are documented as non-functional). Added the negative-path probe the item asked for: `test_critic_skill_metadata.py::test_no_allow_pattern_permits_pytest` asserts no allow pattern can match a pytest invocation. The skill comment already softens the 'structurally enforced' claim to name the allow-list as the real mechanism.

- **[SYN-2K9N]** Template drift advisory dismiss/acknowledge mechanism
  `effort: M · impact: M · area: sync · source: critic · added: 2026-04-16 · status: shipped · closed-by: reduce-governance-tax Chunk B · reviewed: 2026-05-30`

  **Resolved** by the template-drift fire-once fix (Chunk B of the governance-tax reduction): a drift advisory now surfaces exactly once per template change, then sync refreshes the stored template hash so it self-resolves — directly fixing the "nags every session" pathology. This is a cleaner fix than the proposed `dismissed_advisories` list / `/janitor dismiss` flow: place-once files are user-owned ("surface the change once, then it's yours"), so auto-resolving after one surfacing matches the semantics without new dismiss machinery. The user's place-once file is never overwritten. (critic)

- **[BLD-9R3K]** `infer-critic-mode` does not detect a build plan living in `.prawduct/artifacts/`
  `effort: M · impact: M · area: build-plan · source: critic · added: 2026-05-29 · status: shipped · closed-by: v1.6.0 Chunk 06 · reviewed: 2026-05-29`

  During v1.6.0 Chunk 02 the helper returned `rule-4 final: no active build plan ... fail-safe to thoroughness` even though `.prawduct/artifacts/v1.6.0-advisory-infrastructure-plan.md` is the active plan. **Resolved** by Chunk 06's `active_build_plan:` pointer (project-state.yaml) + the shared `core.resolve_build_plan_path` resolver, mirrored inline in product-hook and used by `infer-critic-mode`, `regen-views`, the stop-hook gates, `verify-chunk-refs`, and `check-pr-trivial`. The chosen shape is the explicit pointer (not the `*plan*.md` glob the original fix-shape proposed — a glob is ambiguous when multiple scope-named plans accumulate, which this repo demonstrates). Validated against both the framework repo (pointer → scope-named plan) and the back-compat default (no pointer → `build-plan.md`). Filed from /critic NOTE on 2026-05-29 (v1.6.0 Chunk 02); closed 2026-05-29 (v1.6.0 Chunk 06). (critic)

- **[JAN-4F7M]** Rewrite `skills/janitor/SKILL.md` "Template Currency" theme for plugin distribution
  `effort: M · impact: M · area: janitor · source: builder · added: 2026-06-03 · status: resolved · reviewed: 2026-06-04`

  The janitor skill's **Template Currency** investigation theme (and its Step 1 framework-health
  pre-check + Step 7 hash-update guidance) still teaches the file-sync maintenance workflow:
  comparing the consumer's place-once artifacts against `framework_source/templates/*` via
  `.prawduct/sync-manifest.json` `place_once_templates` stored hashes. Under plugin distribution a
  consumer carries no sync-manifest (init never creates it; `/prawduct:migrate` removes it) and has
  no `framework_source` checkout, so the whole theme is inert for migrated/plugin-native repos.
  Surfaced during M4 Chunk 4: `test_v5_templates.py::TestJanitorSkillTemplateCurrency` (which pinned
  this content via the now-deleted `templates/skill-janitor.md`) was DELETED rather than retargeted,
  precisely to avoid pinning stale guidance. Resolve: rework the theme for plugin-era maintenance —
  what does "is this product's tooling current with the plugin?" mean when governance ships from the
  plugin and updates via `autoUpdate`? — and add fresh `skills/janitor/SKILL.md` structural coverage
  to replace the deleted mirror test. Candidate to fold into M4 Chunk 5 (docs/residue) if cheap, else
  a standalone janitor-skill pass. Filed from M4 Chunk 4 on 2026-06-03. (builder)

  **Resolved (v2.0.3 pre-promotion, 2026-06-04):** reworked the Template Currency theme for plugin
  distribution — it now compares the product's artifacts against the read-only plugin templates at
  `${CLAUDE_PLUGIN_ROOT}/templates/` (no `sync-manifest.json`, no `framework_source`, no place-once
  hash store). The Step 1 framework-health pre-check now confirms the plugin runtime is reachable
  (`${CLAUDE_PLUGIN_ROOT}/templates/` readable) instead of asserting a sync-manifest exists; Step 7
  records resolved drift in `.prawduct/change-log.md` rather than recomputing template hashes.
  Structural coverage restored via `test_plugin_runtime.py::TestJanitorSkillPluginEra` (asserts no
  `sync-manifest`/`framework_source`/`place_once` residue + the plugin-root target). The same pass
  also cleaned the file-sync-era `_METADATA_PREFIXES` entries (`.claude/skills/`, `tools/product-hook`)
  from both mirrors (`bin/prawduct-hook` + `lib/critic_mode.py`) — a product's own `.claude/skills/`
  skill now counts as gated code, not excused metadata (`TestMetadataPathClassification`). Surfaced by
  the develop→main release-readiness review; folded into v2.0.3 rather than deferred. 652 passing. (builder)

- **[DOC-7H2K]** Port `/prawduct:doctor`'s remaining file-sync-coupled flows to the plugin model (Chunk 13)
  `effort: L · impact: M · area: doctor · source: builder · added: 2026-06-02 · status: resolved · reviewed: 2026-06-02`

  Surfaced during v2.0.0 Chunk 11 (dogfood + self-containment audit). The plugin's `skills/doctor/SKILL.md` is a thin wrapper over `python3 <framework>/tools/prawduct-setup.py` for nearly every flow: Onboard (`setup`), Health Check (`validate`), Migrate feature opt-ins (`migrate --enable-coverage|--enable-settings-layout|--enable-operator-verification`), and Audit Learnings (`audit-learnings`). In a migrated consumer there is no framework checkout, so all of these break — only the **Verify** flow was ported this chunk (new `prawduct-hook verify-operator-verification`, which operates purely on the consumer's `.prawduct/`). The rest were deliberately NOT ported because (a) `setup`/`validate` ARE the file-sync engine, which design §5 / Chunk 5 deliberately excludes from the plugin runtime — bundling them would re-introduce exactly what the architecture removes; and (b) the plugin onboarding model is "install the plugin + `/prawduct:migrate`", not a `setup` script. Resolve as part of Chunk 13 (remove file-sync + its name): rework the doctor skill to the plugin model — Onboard → install + `/prawduct:migrate`; Health Check → a plugin-native `prawduct-hook` validate/health read of the consumer's own `.prawduct/` (no framework path); coverage / operator-verification opt-ins → plugin-native `project-state.yaml` flag flips (need no sync); decide whether `--enable-settings-layout` (pure file-sync settings normalization) and `audit-learnings` survive in the plugin world. Also: `lib/operator_verification.py::run_verify_entry`'s "no queue" error hint still names the legacy `prawduct-setup migrate --enable-operator-verification` path — repoint once the plugin-native enable exists. And the legacy `agents/` tree ships inside the plugin and the loader picks it up as frontmatter-less agents (`claude plugin validate` warnings) — Chunk 13's grep-sweep across `agents/` should drop it. Filed from Chunk 11 dogfood on 2026-06-02. (builder)

  **Resolved (Chunk 13, 2026-06-02):** all four flows reworked off file-sync — Onboard → install + `/prawduct:migrate`; Health-Check → plugin-native Read/Glob of the consumer's own `.prawduct/`; opt-ins (F4/F10) → `project-state.yaml` flag flips (F5 settings-layout dropped as file-sync-only); Audit-Learnings → new plugin-native `prawduct-hook audit-learnings` (port of `lib/audit_learnings_cmd.py`). Operator-verification hint repointed off `prawduct-setup migrate`. The legacy `agents/` tree dropped (clears the 6 `claude plugin validate` frontmatter warnings). `/prawduct:doctor` `allowed-tools` tightened (broad `Bash(python3 *)` removed). Confirmed by the Chunk-13 Critic (NOTE 2). (builder)

- **[MIG-M4-REMOVE]** Permanently delete the file-sync engine + payload + shims (post-2.0.0 milestone M4)
  `effort: L · impact: M · area: distribution · source: builder · added: 2026-06-02 · status: shipped · closed-by: M4 (v2.0.3) · reviewed: 2026-06-03`

  The terminal step of the file-sync→plugin transition, deliberately deferred out of 2.0.0. Chunk 13 removes file-sync only from THIS repo's active path; the engine stays a **live service** for un-migrated external repos, because `tools/product-hook` + `tools/lib/*` are `MANAGED_FILES` synced into products and a product's own `try_sync()` calls back to this framework's `tools/prawduct-setup.py sync` every session (fail-soft: missing script ⇒ no crash, the sibling keeps governing on its last-synced version). **Blocked on:** marketplace live (Chunk 2) AND every local sibling migrated to the plugin (`/prawduct:migrate`). Inventory is the owner's — manual, "only this one machine"; no consumer census / deprecation advisory is being added (owner decision 2026-06-02, keep 1.x frozen). When unblocked: delete `templates/`, the 7 `.claude/skills/*` sync sources, `tools/product-hook`, `tools/lib/*` (sync modules), `tools/prawduct-setup.py`, and the `prawduct-{init,sync,migrate}.py` shims; finish the deep name-sweep across the (now-removed) `templates/`+`tools/` — *you can only remove a mechanism's name from a path once the mechanism has left it.* After M4, a stale un-migrated sibling fails-soft (silent no-update), an acceptable terminal contract because it was warned during M3. See build-plan Chunk 13 "Permanent-removal path (M1–M4)". **Cleanup rider (Chunk 13 Critic NOTE 1, 2026-06-02):** the plugin `lib/audit_learnings_cmd.py` is byte-parity-locked to `tools/lib/audit_learnings_cmd.py`, so its `run_audit_learnings` docstring still names the legacy `prawduct-setup audit-learnings` path (correct for the file-sync copy, stale for the plugin). When `tools/lib/` is deleted here, the parity lock dissolves — repoint that docstring to `prawduct-hook audit-learnings`. (builder)

  **Resolved (M4, v2.0.3, 2026-06-03):** the owner directive (2026-06-03, "we DO NOT need backwards compatibility … remove ANY cruft that exists only for back compat to pre-2.0") lifted the consumer-census block — the inventory is "only this one machine," all local siblings migrated. M4 (5 chunks on `feat/retire-filesync-engine-m4`) executed the full removal: Chunk 2 deleted `tools/` (product-hook, prawduct-setup.py, the 3 shims, `tools/lib/`), Chunk 4 deleted the file-sync templates (`product-claude`/`critic-review`/`pr-review`/`build-governance`/`product-settings.json`/`conftest.py` + the 7 `skill-*.md` sources) and slimmed `lib/core.py`, Chunk 5 removed the committed `.prawduct/` protocol-doc residue + swept the deep name-sweep across kept code/docs/templates. The `run_audit_learnings` docstring rider was discharged (repointed to `prawduct-hook audit-learnings`, Chunk 5). Deferred fragment: `[JAN-4F7M]` (the janitor skill's file-sync Template Currency theme). (builder)

- **[BLD-3X9M]** Resolve `status=shipped` semantic — per-chunk merge vs. tagged release
  `effort: S · impact: M · area: build-plan · source: builder · added: 2026-05-18 · status: resolved · reviewed: 2026-06-02`

  Chunk 05 dogfooding raised an open question: does `status=shipped` on a change-log tag line mean "merged to mainline" (per-chunk timing — Status flips `[x]` when the chunk commits) or "in a tagged release" (wave timing — Status flips when a release entry covers it)? Current state: Chunk 05 left `[ ]` pending Wave 2 release entry. The Critic check (mismatch → WARNING) is symmetric, so either interpretation is internally consistent once chosen. Decide before Wave 2 release; document the chosen semantic in `templates/change-log.md` schema doc. Filed from Chunk 05 work, 2026-05-18. (builder)

  **Resolved (v2.0.0 Chunk 14, 2026-06-02):** decided as **tagged-release / wave timing** — `status=shipped` means "in a tagged release" and flips Status `[x]` only at the `develop → main` release; `status=merged` is the develop-phase intermediate that does NOT flip checkboxes. Documented in `docs/release-process.md` (release checklist + "Why the checkboxes stay `[ ]` during development") and the v2.0.0 build-plan "Checkbox model" note. (Schema-doc home moved from `templates/change-log.md` to `docs/release-process.md` under the plugin model.)

- **[DOC-4B2W]** Namespace bare command forms in plugin-bundled teaching prose (`skills/critic/*.md`, `methodology/*.md`)
  `effort: M · impact: M · area: docs/governance · source: builder · added: 2026-06-03 · status: shipped · closed-by: M4 Chunk 1 (v2.0.3) · reviewed: 2026-06-03`

  **Resolved (M4 Chunk 1, v2.0.3, 2026-06-03):** swept the 6 plugin-only prose files (`methodology/{building,planning,reflection}.md`, `skills/critic/{review-cycle,review-protocol}.md`, `skills/pr/review-protocol.md`) → `/prawduct:*`; pinned by `TestPluginDocsNamespacing` (assert-absent source-scan over the skill vocabulary). Decision (point 3): conceptual short-names ARE namespaced in the teaching prose, since a plugin repo resolves `/prawduct:*`. File-path carve-outs (`.prawduct/critic-review.md`) and the built-in `/clear` preserved; the file-sync `tools/` copies that carried duplicated prose were deleted outright in Chunk 2 rather than kept on bare forms. (builder)

  The runtime gate-message sweep (#53) namespaced `bin/prawduct-hook` + `lib/` agent-facing OUTPUT, but the plugin-bundled PROSE an agent reads via `/prawduct:*` still carries ~34+ bare command forms — `skills/critic/review-cycle.md`, `skills/critic/review-protocol.md`, and `methodology/{building,planning,reflection}.md` say "run /critic", "/pr create", "/critic cumulative" etc. where a plugin repo resolves `/prawduct:critic`, `/prawduct:pr`. Same leak class as #53, larger + lower-severity surface (teaching prose, not gates; agents can often infer the mapping, and the SessionStart briefing already lists namespaced forms). This is the "entire leak class as a build plan" follow-up.

  Scope notes for the build plan: (1) sweep the whole FORM-FAMILY per the new learning — bare `/cmd`, hyphenated `/prawduct-advisory`, legacy `prawduct-setup` — one grep per spelling; (2) preserve carve-outs: file paths (`.prawduct/critic-review.md`, `agents/critic/SKILL.md`), the Claude Code built-in `/clear`, and prose like "critic/pr skills"; (3) DECISION REQUIRED — whether to namespace conceptual short-names in teaching guides at all, or keep `/critic` as the canonical short name with a one-time namespacing note (judgment call, raise with owner); (4) the frozen `tools/` copies of any duplicated prose stay bare; (5) pin with an assert-absent source-scan like `TestPluginRuntimeNamespacing`, extended to the docs surface. (builder)

- **[SYN-3D8K]** Align `enable_v1_4_views` detector/mutator on inline-comment forms
  `effort: S · impact: S · area: sync · source: critic · added: 2026-05-19 · status: dropped · reviewed: 2026-05-29`

  Same pattern Chunk 10 fixed in `enable_v1_4_coverage`: `is_views_enabled`-style detection strips inline comments via `split('#', 1)`, but `enable_v1_4_views`'s flip uses exact `line.strip() == "views_enabled: false"`. A user line like `views_enabled: false  # opt-out` is detected as present-and-off but never flipped → silent no-op (manifest flag still set, file unchanged). Edge case (templates emit bare values), but the asymmetry will keep biting until both helpers use the same shape-aware match. Apply the Chunk-10 fix-shape: iterate lines, skip indented, compare comment-stripped value, re-attach inline comment on rewrite. Filed from /critic chunk NOTE on 2026-05-19 (Chunk 10) — the views variant was left alone in-chunk to keep diff scope tight. (critic)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — the enable_v1_4_views mutator/flip lived in the deleted sync engine; only the is_views_enabled reader survives and it isn't the buggy path.

- **[BLD-0G6V]** Backfill Done-when blocks on Chunks 05-14 of v1.4 build plan
  `effort: S · impact: S · area: build-plan · source: critic · added: 2026-05-18 · status: dropped · reviewed: 2026-05-29`

  Chunks 00-04 each carry a Done-when block; Chunks 05-14 do not. Not a chunk-close blocker (chunk-mode Critic still fires on declared `**Critic mode:**`), but worth backfilling for consistency before Chunk 06 starts. Filed from /critic chunk NOTE on 2026-05-18 (Chunk 05). (critic)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — backfilling Done-when on the long-shipped v1.4 plan has no consumer.

- **[BLD-7A2E]** Capture pre-commit-regen scope-shift in Wave 2 retrospective / change-log
  `effort: S · impact: S · area: build-plan · source: critic · added: 2026-05-18 · status: dropped · reviewed: 2026-05-29`

  F1 plan line 234 promises "pre-commit regen of build-plan Status from work-log"; Chunk 05 shipped on-demand `regen-views` plus methodology docs that tell users to invoke manually (Chunk 06 plan note confirms this is deliberate as "ad-hoc regen between commits"). The deliverable line was flagged "high level — to be expanded before chunk starts" so this is not silent, but the Wave-2 release entry / retrospective should record the explicit decision: pre-commit hook (deferred to Chunk 07's migration tooling or Wave-3) vs. on-demand `regen-views` (shipped now). Filed from /critic chunk NOTE on 2026-05-18 (Chunk 05). (critic)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — the v1.4 Wave-2 retrospective window is closed; the decision shipped.

- **[DOC-6P3Q]** v1.4 release-readiness: document the new `/pr create` gate before tagging
  `effort: S · impact: M · area: docs · source: critic · added: 2026-05-18 · status: dropped · reviewed: 2026-05-29`

  F2 ships hard enforcement: `check-cumulative-critic` blocks `/pr create` without a fresh cumulative-mode findings file. Product owners who sync v1.4 without reading the change-log will hit the gate cold and read it as a regression. Before tagging v1.4 (after all waves merge): add a change-log entry naming the new gate, a `prawduct-doctor` migration prompt if relevant, and a Compatibility-Strategy line in the release notes (the cumulative gate is new structural enforcement, not a behavior tweak). Filed from /critic cumulative NOTE on 2026-05-18. (critic)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — the 'before tagging v1.4' window is closed; the /pr cumulative gate shipped and is live.

- **[SYN-7L0D]** Remove dead `if rel_path in ("CLAUDE.md",)` lines in sync_cmd.py `template`-strategy branch
  `effort: S · impact: S · area: sync · source: critic · added: 2026-05-08 · status: dropped · reviewed: 2026-05-29`

  Two pre-existing branches (`force=True` overwrite + `current_hash != stored_hash` skip) emit a "re-read CLAUDE.md" note guarded by `if rel_path in ("CLAUDE.md",)`. CLAUDE.md uses `block_template`, not `template`, so it can never reach these branches. Dead since the strategy split. Remove or document. Filed from /critic chunk on 2026-05-08 — flagged after the same dead pattern was caught in the new stale-clean branch (already removed there). Two-line cleanup; defer until next sync_cmd.py touch. (critic)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — the dead CLAUDE.md branch lived in the deleted sync_cmd.py.

- **[SYN-3F6P]** Sync: skip-summary line counts + `--diff` preview flag
  `effort: M · impact: M · area: sync · source: reflection · added: 2026-05-08 · status: dropped · reviewed: 2026-05-29`

  When sync skips a file as "local edits," it gives no signal about the size or shape of the divergence — the user must `--force` blind or manually diff. Add to the skip note: `+N lines / -M lines vs current template`. Add a `--diff` flag that prints the unified diff(s) of would-be skips (or all would-be changes) without writing anything. For `block_template`, also note that content outside markers won't change. Lets users decide whether to force without a separate investigation. (reflection)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — pure file-sync `sync` UX (--diff/--force/skip-summary); the sync engine is gone.

- **[TST-8B3X]** Audit public-function coverage exemptions in `tests/preferences/test_public_function_coverage.py`
  `effort: M · impact: S · area: tests · source: builder · added: 2026-05-05 · status: dropped · reviewed: 2026-05-29`

  Four functions in `tools/lib/` are exercised transitively but never directly referenced as a function call (under the tightened detection that requires `Attribute.attr` or `Name` in `Call.func`): `core.py::log`, `core.py::load_json`, `migrate_cmd.py::strip_test_tracking`, `migrate_cmd.py::generate_sync_manifest`. For each, decide: (a) add a direct unit test class, or (b) rename to `_<name>` (private-by-convention) and remove from the exemption list. Rationale captured inline in `EXEMPT_FROM_DIRECT_COVERAGE`. (builder)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — two of the four named functions were in the deleted tools/lib/migrate_cmd.py and the exemption list referenced the old tree (a fresh public-function-coverage audit against lib/ can be re-filed if wanted).

- **[SYN-5G2J]** Extract `_git_run` helper for fw-dir git lookups
  `effort: S · impact: S · area: sync · source: critic · added: 2026-05-01 · status: dropped · reviewed: 2026-05-29`

  `_get_framework_head_commit`, `_get_template_last_change` (sync_cmd.py), and the inline `git log -1` inside `_compute_framework_freshness` (product-hook) share the same try/except + subprocess.run + timeout=10 + broad-except + None-on-failure pattern. Three is the minimum-viable case for extraction. If a fourth fw-dir git lookup gets added, factor into `tools/lib/core.py` as `_git_run(fw_dir, args, timeout=10) -> str | None`. Currently small and well-commented; not urgent. (critic, 2026-05-01)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — the three _git_run call sites were framework-dir freshness probes in the deleted sync_cmd.py/product-hook.

- **[SYN-3T7B]** run_sync() decomposition
  `effort: M · impact: M · area: sync · source: janitor · added: 2026-04-16 · status: dropped · reviewed: 2026-05-29`

  Extract per-strategy logic (template, block_template, always_update, merge_settings) from 337-line function in sync_cmd.py. (janitor)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** references file-sync machinery deleted in M4 — run_sync() was the deleted sync_cmd.py dispatcher; no 2.0 analog.

- **[TST-1M6V]** Pre-existing timeout flakes in test_product_hook.py
  `effort: M · impact: S · area: tests · source: builder · added: 2026-04-16 · status: dropped · reviewed: 2026-05-29`

  `TestStopCriticGate::test_no_build_plan_anywhere_skips_critic` and `TestCanaryDepNoRationale::test_no_manifest_file_no_flag` intermittently hit the 15s timeout. May need investigation into why the product-hook subprocess hangs in certain test configurations. (builder)

  **Dropped (2.0 rock-solid pass, 2026-06-03):** both named tests were removed with the file-sync engine in M4 — `TestStopCriticGate::test_no_build_plan_anywhere_skips_critic` and `TestCanaryDepNoRationale::test_no_manifest_file_no_flag` (manifest = file-sync) no longer exist.


