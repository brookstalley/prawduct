---
artifact: build-plan
version: 2
scope: backlog-skill-repoint
depends_on:
  - artifact: backlog-service-api-contract
  - artifact: backlog-service-requirements
  - artifact: data-model
governed_by:
  - artifact: backlog-service-api-contract
    dispositions:
      - "Exit codes are the contract — skills bind to exit codes, not parsed text → conforms (the adapter path branches on the stable exit class 0 ok / 2 validation / 3 not-found / 4 conflict / 5 auth / 6 unavailable, never on human stdout)"
      - "Additive-first evolution — `--json` readers tolerate unknown keys → conforms (the envelope parse reads named fields and ignores unknowns; no key is repurposed)"
  - artifact: observability-strategy
    dispositions:
      - "stdout=agent / stderr=user split, stable prefix vocab (CRITICAL:/WARNING:/NOTE:/PRAWDUCT:/BLOCKED —) → conforms (the skill surfaces adapter warnings[]/errors to the user using the prefix vocab; legibility is Phase-1 operator-verified)"
  - artifact: architecture
    dispositions:
      - "Local-first, stdlib-only; `gh` is the sanctioned external command (list-form, never shell=True) → conforms (the skill shells only `prawduct-hook backlog`, which owns the gh subprocess; the skill adds no network/daemon and no new external dep)"
      - "Authority fails closed; advice fails soft → conforms (the /prawduct:backlog skill is an advice/tool path, not a verdict path; on adapter auth/unavailable failure it surfaces a clear NOTE and never silently falls back to the frozen markdown — stale-as-live is the failure this avoids)"
  - artifact: security-model
    dispositions:
      - "No destructive action without explicit --apply → conforms/inapplicable (the skill delegates every mutation to an adapter op that enforces its own SEC-5 withholding + mutation semantics; the skill introduces no new destructive path)"
  - artifact: data-model
    dispositions:
      - "Governance verdicts from append-only facts / facts immutable / views disposable / schema-ahead loud / two-stores-two-lifetimes → inapplicable because this plan routes the /prawduct:backlog skill's backend, not the Critic evidence store / fact ledger these five norms govern (the backlog adapter has its own analogous schema-versioning + gitignored counts store, untouched here)"
last_validated: 2026-07-19
lifecycle: completed
archived: 2026-08-10
released_in: v3.2.0
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Requirements Confidence

**Level:** High

**Why:** Problem, success, and scope are each one sentence and were confirmed with the owner
this session. The one design fork (`find`/`dedup` have no adapter search op until W2) is resolved
by owner decision — defer to W2 with a clear stub message, `find` may be non-functional against
Issues meanwhile ("won't ship before W2; OK if find is broken for a bit"). No fast-moving external
dependency: the `gh` CLI and the `prawduct-hook backlog` contract (exit classes, `--json` envelope,
non-interactive) are owned and stable, and the adapter surface was read directly (`plugin/lib/backlog/cli.py`).

**Open assumptions / unknowns:**
- [ASSUMPTION: the skill stays PROSE-ONLY — dual-mode routing lives in `SKILL.md` instructions + a
  new `adapter-mode.md` runbook + a `Bash` grant, with no new `lib/` helper | MED impact | user can
  override if a code helper (e.g. a shared repo-resolution shim) is preferred]
- [ASSUMPTION: per-chunk verification is adapter command/envelope-shape confirmation (repo-local
  `python3 plugin/bin/prawduct-hook backlog …`) + frontmatter validity; the end-to-end behavioral proof is
  Phase 1's sibling dogfood, tracked as an operator-verification (VRF) entry that drains at Phase 1 |
  LOW impact | this is inherent to a prose skill — there are no unit tests for skill behavior]

**What would raise confidence:** N/A (High).

## Status

- [x] Chunk 01: Dual-mode dispatch scaffold + read ops (summary/list/get)
- [x] Chunk 02: Write ops + deferred find/dedup + cutover-aware edge messaging
Context: **Phase 0 COMPLETE, PR-ready.** Chunks 01-02 built + verified (suite green 2396; write-op
flags + the `promoted→in-progress` status bridge confirmed against `encode.py`). Cumulative Critic
(3 reviewers, coordinator): 0 blocking / 0 warning / 7 note — the two actionable notes (summary menu
advertised moot ops; grooming stamp on failed calls) resolved on `adapter-mode.md`, `verify-resolutions`
clean (R-2/R-3 fixed). Branch `feature/backlog-skill-repoint`, **merging to develop** (owner chose to
merge before the sibling dogfood). BKL-3W6K is **archived shipped** (`closed-by: backlog-skill-repoint`
— Phase-0 skill-repoint code is delivered); its end-to-end verification is tracked separately as
**VRF-007** (pending the sibling-session confirm; drives no gate — `operator_verification_required:
false`). **Phase 1 adapter pre-verification PASSED** (2026-07-19, dogfood on `prawduct-backlog-smoke`:
reads/writes/`promoted`→`in-progress` bridge/exit-3/exit-4 all live) — caught + fixed one doc bug
(`get` doesn't expose `updated_at`). Remaining: the owner's sibling-*session* confirm via
`--plugin-dir` (drains VRF-007), then `/prawduct:pr`. Next after that: Phase 2 (prawduct self-cutover).

## Scaffolding

No new project, dependencies, or code substrate — the `prawduct-hook backlog` adapter, its `gh`
transport, the `backlog_service_repo` config knob (`project-state.yaml`), and the cutover-aware
briefing already exist. This plan edits prose (`skills/backlog/`) plus one frontmatter line.

### Build & Test Configuration

Skills are prose the model executes — there are no unit tests for skill *behavior*. Two mechanical
checks still apply: the plugin-manifest frontmatter validator (`tests/test_plugin_manifest.py` +
kin — a skill with unparseable YAML frontmatter loads with metadata silently dropped, so the
`allowed-tools` edit must keep valid YAML), and `python3 -m pytest -q` staying green (the edit
touches no `lib/`, so this is a regression guard, not new coverage).

### Verification Strategy

Per chunk: (1) confirm the frontmatter still validates (plugin-manifest test); (2) run the adapter
commands the chunk's prose depends on **repo-local** (`python3 plugin/bin/prawduct-hook backlog <op> --repo
<throwaway> --json`, never the on-PATH cached plugin) and confirm the envelope shape + exit class
match what the prose instructs. End-to-end behavioral proof (the human-output legibility a
`--json`-only check can't speak to) is **Phase 1's sibling dogfood** — drive the full loop against a
real cutover sibling repo via `--plugin-dir=../prawduct`. Chunk 02 declares `Visual change: yes` and
appends the VRF entry.

## Project Structure

```
skills/backlog/
├── SKILL.md          # frontmatter (+ Bash) + a top-level "Backend routing" gate; per-op markdown sections stay byte-unchanged (routing centralized in one gate, not per-op branches — cleaner/DRY)
├── adapter-mode.md   # NEW — the adapter-path runbook: repo resolution, command map, envelope/exit handling, deferred find/dedup
└── migration-scrub.md # unchanged (the existing one-shot migration runbook)
```

### Module Boundaries

`SKILL.md` decides the mode (read `backlog_service_repo`; unset → today's markdown behavior,
untouched; set → follow `adapter-mode.md`). `adapter-mode.md` owns the adapter protocol and never
duplicates the markdown behavior. The skill binds to the adapter's **exit codes and `--json`
envelope**, never to its human stdout (api-contract norm).

## Build Chunks

### Chunk 01: Dual-mode dispatch scaffold + read ops (summary/list/get)

- **Description:** Land the dual-mode dispatch pattern end-to-end on the read ops — the thin
  vertical slice that proves the path before writes widen it. `SKILL.md` frontmatter gains `Bash`
  (scoped to `prawduct-hook backlog *`); a new top-level **"Backend routing"** section resolves
  `backlog_service_repo` from `project-state.yaml` and branches (unset → the existing markdown
  sections, byte-unchanged; set → `adapter-mode.md`). New `adapter-mode.md` carries the protocol:
  resolve the repo, run `python3 plugin/bin/prawduct-hook backlog <op> --repo <r> --json` (repo-local when
  developing; `prawduct-hook` in a consumer), parse the envelope, branch on the exit class, and
  **surface `warnings[]` from BOTH the ok AND the error envelope** (the error return is a different
  constructor that drops enrichment — the recurring backlog-service envelope bug). On exit `5`
  (auth) / `6` (unavailable): a clear NOTE to the user, never a silent fall-back to the frozen
  markdown. Wire only the READ ops this chunk: summary→`counts`, list→`list`, get→`get`.
- **Depends on:** none
- **Artifacts consumed:** `backlog-service-api-contract.md` (exit classes, `--json` envelope),
  `data-model.md` (item fields the read ops render)
- **Deliverables:** `skills/backlog/SKILL.md` (frontmatter + Backend-routing section + read-op
  branches), new `skills/backlog/adapter-mode.md`
- **Tests:** none (prose). Guards: `tests/test_plugin_manifest.py` (frontmatter valid), `pytest -q` green.
- **Acceptance criteria:** with `backlog_service_repo` set, summary/list/get route to the adapter and
  render its `--json` envelope (exit-class-branched, warnings surfaced); with it unset, the markdown
  read behavior is byte-unchanged; frontmatter validates.
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met; frontmatter validates; `pytest -q` green
  2. Verified: `python3 plugin/bin/prawduct-hook backlog counts/list/get --repo <throwaway> --json` shapes
     match `adapter-mode.md`'s instructions (incl. an error-envelope case for exit-class handling)
  3. `/prawduct:critic` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

### Chunk 02: Write ops + deferred find/dedup + cutover-aware edge messaging

- **Description:** Widen to the write ops under the same envelope/exit discipline: add→`file`,
  update→`status` (when `status=`) / `update` (other fields), pick→`pick` (`--claim` on claim
  intent), claim/unclaim→`claim`/`unclaim`, link/unlink→`link`/`unlink`. Handle the SEC-5
  write-withheld case (exit `5`) with a clear message. **Deferred (owner-decided):** under cutover,
  `find` and `dedup`'s auto-candidate-scan return a NOTE — "full-text search arrives in W2; use
  `list --area=…`/`--status=…` filters or the GitHub UI meanwhile" — no degraded search code (`merge`
  still works when both ids are known). **Cutover-aware edge messaging:** `migrate`/`import`(legacy)/
  the Q2 archive-split are markdown-file operations and are moot post-cutover → a clear "not
  applicable on the Issues backend" NOTE. The `backlog_last_groomed_at` grooming stamp still writes
  regardless of backend. Order the per-op human formatting most-specific-first (a shared-key result
  type must not shadow another — and the human path is unexercised by `--json` checks, so it is
  Phase-1 verified).
- **Depends on:** Chunk 01
- **Artifacts consumed:** `backlog-service-api-contract.md` (write-op contracts, SEC-5),
  `security-model.md` (mutation/`--apply` semantics)
- **Deliverables:** `skills/backlog/SKILL.md` (write-op branches + per-op cutover messaging),
  `skills/backlog/adapter-mode.md` (write ops, deferred find/dedup, edge messaging)
- **Tests:** none (prose). Guards as Chunk 01.
- **Acceptance criteria:** the full add→list→update→pick→claim→link→get→status loop works against a
  real test repo via the skill; `find`/`dedup` give the deferred NOTE; markdown-only ops give the
  cutover NOTE; markdown-path behavior still byte-unchanged when `backlog_service_repo` is unset.
- **Type:** doc-only
- **Critic mode:** cumulative
  <!-- Last chunk, ships as one PR: the cumulative review over merge-base…HEAD IS the /prawduct:pr
       gate. doc-only keeps test-evidence out of scope (prose skill) while still reviewing prose
       coverage across the whole branch. -->
- **Visual change:** yes — the human output of every op now derives from the adapter; legibility and
  correctness need a real look. Appends the Phase-1 sibling-dogfood VRF entry to
  `.prawduct/operator-verification.md`.
- **Done when:**
  1. Acceptance criteria met; frontmatter validates; `pytest -q` green
  2. Verified: the CRUD+pick+claim+link loop driven repo-local against a throwaway repo; deferred
     and edge NOTEs observed
  3. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  4. VRF entry appended; chunk marked `[x]` in Status

## Early Feedback Milestone

**Milestone chunk:** 01 (with `backlog_service_repo` set on a throwaway repo, the read ops already
show live Issues data through the skill).

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic review passes. Chunk 02's `cumulative`
review makes the branch PR-ready — `/prawduct:pr create` is gated on it and runs when asked.

- After Chunk 01: confirm the dual-mode dispatch pattern (routing + envelope/exit handling + fail-loud)
  is right before wiring the write ops onto it.
- After Chunk 02 (cumulative): whole-branch review; confirm the markdown path is genuinely
  byte-unchanged and the deferred/edge NOTEs read clearly. Then Phase 1 (sibling dogfood) drains the VRF.
