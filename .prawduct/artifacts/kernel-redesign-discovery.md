---
artifact: discovery
# scope intentionally empty: discovery for a future program of plans; no plan
# scope is owned here (same opt-out as critic-persistence-redesign.md).
scope:
status: discovery complete 2026-07-12 — all owner questions answered; next: planning
created: 2026-07-12
depends_on: [kernel-inventory-2026-07-12.md, framework-efficiency-review-2026-07-02.md, critic-persistence-redesign.md]
---

# Governance Kernel Redesign (v3) — Discovery

**Owner directive (2026-07-12):** step back from patch-on-patch; rethink the
implementation, in whole or in part, for how Claude Code works today. Key
assumption set by the owner: **prawduct will only ever be run by opus-level or
better models (Opus, Fable, and beyond).** The goals are not in question —
"invaluable in producing great software"; the implementation is.

## 1. Problem (observable, evidenced)

Prawduct's conceptual model works — independent review demonstrably catches
ship-blockers in every active consumer (framework-efficiency-review-2026-07-02
"What works"). The implementation is failing in four structural ways:

1. **Patch accretion in the gate layer.** `lib/gates.py` is 1,531 lines with 24
   inline incident-ID references. Patches now conflict with patches: CRT-5D8Q is
   two gate helpers disagreeing on the metadata boundary (deadlock); CRT-J4PM(2)
   is the framework's own demotion advice (`gates.py:598` → "run final")
   producing a record its own PR gate (`gates.py:1155`) rejects by mode label,
   forcing a fourth identical 3-reviewer run. The July 2 review's proposed
   principle — *third rework of a mechanism is a deletion signal* — is met or
   exceeded by: test-evidence freshness (5 redesigns), the Stop hook (6+
   reworks), critic persistence (v2.1.198 breakage → redesign → roster defect).
2. **A model remains in a protocol-critical write path.** The persistence
   redesign (2026-07-09) made consolidation deterministic but left the
   coordinator's `manifest.json` model-written; `critic-consolidate` fail-closes
   on omissions (`lib/critic_consolidate.py:165`) and leaves the *previous*
   review's findings file in place looking valid. Consumer evidence: CRT-W2NV,
   CRT-J4PM(1) — recurring across v2.3.2/v2.3.3, hand-patched manifests as the
   workaround. **Even fable-class models omit required keys**: the opus-level
   floor does not make prose-driven bookkeeping safe.
3. **Governance state is keyed to the wrong identity.** Evidence lives in
   per-worktree, gitignored, single-slot files judged by session recency; the
   facts they record are about *commits and trees*. Consequences, all observed:
   host-critic/container-test split (discodon learnings 2026-06-27), reviews
   that can't cross worktrees (incoming bug 2026-06-20), `.critic-findings.json`
   holding an unrelated branch's record (CRT-J4PM), stale-evidence warnings on
   nearly every review for 2.5 months (the #1 friction in EVERY consumer —
   efficiency review, Overbuilt #1).
4. **Gate posture trains gate-dodging.** Consumers have normalized hand-editing
   manifests, `rm -f .critic-active`, hand-anchored chain records, waivers. 82
   broad-except allow-pragmas mean gate bugs fail OPEN while docs claim
   fail-closed. Silent failure is the recurring harm-multiplier: the roster
   bug's damage was not the rejection but the stale file masquerading as
   current.

Meta-problem: the feedback loop is push-only. Containerized consumers file
`area: prawduct-upstream` backlog items that nothing harvests; the same defect
family recurred across three plugin versions (2026-07-09 → 07-13) without the
framework repo noticing.

Scale of the implementation vs. what it enforces (efficiency review): ~15,500
LOC of enforcement Python for 4 Stop-hook blockers + 1 advisory; ~88% of this
repo's backlog is governance self-maintenance; ~30% of consumer learnings are
about surviving prawduct.

## 2. What success looks like (verifiable)

1. **Zero silent failures.** Every kernel failure mode either self-heals or
   blocks loudly with attribution. Verify: no state file can be left stale-but-
   plausible by any error path (enumerate error paths in design; test each).
2. **A review is never re-run to relabel or re-persist.** Semantically
   sufficient coverage at HEAD satisfies the PR gate regardless of the label of
   the run that produced it. Verify: the CRT-J4PM and CRT-5D8Q reproduction
   scenarios pass without a re-run.
3. **Evidence composes across worktrees and sequential sessions of the same
   repo.** A review or test run recorded at commit X is usable by any checkout
   of that repo that has X. Verify: worktree + two-checkout scenarios.
4. **No model writes protocol state.** Models produce judgment (findings text,
   review verdicts); code produces every manifest, record, marker, and ledger
   line. Verify: audit of write paths; grep-able invariant.
5. **Kernel shrinks.** Target (directional, not a quota): gate/bookkeeping LOC
   and governance-prose tokens both materially down (efficiency review target:
   halve the ~31k-token cycle load; this program should beat that since prose
   for sub-opus scaffolding is deleted).
6. **Consumer-visible friction drops.** The measurable proxy: stale-evidence
   warnings and full-bundle re-reviews per consumer-week trend to ~zero;
   `area: prawduct-upstream` items get harvested within one framework session.

## 3. Structural characteristics (per methodology/discovery.md)

- **Runs unattended: YES** — hooks fire in headless/container sessions with no
  human watching. Design against silent failure is the central requirement.
- **Exposes programmatic interface: YES** — the hook CLI (allowlisted by skill
  `allowed-tools`), state-file schemas, and the ledger schema are contracts
  consumed across plugin/product version skew. Versioning decision required
  (§6 Q4) — CRT-J4PM explicitly suspected version skew.
- **Multi-process/distributed: YES** — coordinator + parallel reviewers +
  concurrently-firing hooks (CRT-4B7X double-consolidate race) + multiple
  checkouts/worktrees/containers of one product. Concurrency and identity
  (what is keyed by what) are first-class design concerns, not edge cases.
- **Multiple party types: YES (trust boundaries)** — builder agent, independent
  reviewer agents, human operator. Reviewer independence (never mutating the
  session under review; builder never authoring findings) is load-bearing and
  must survive the redesign structurally, not by prose.
- Human interface: only via terminal text (gate messages must stay actionable,
  attributed, copy-pasteable — a praised strength). Sensitive data: no.

**Risk: medium-high.** ~20 governed repos; the framework governs its own
rebuild (self-hosting risk → small blast-radius plans, per the July 2 program
structure decision).

## 4. Requirements

### 4.1 Preserve (from kernel-inventory-2026-07-12.md — the full matrix)

- **R1 Independence, structurally enforced**: reviewers in separate contexts
  with restricted tools; builder never authors findings; reviewer never mutates
  the session under review. (The `clear`-refusal guard's *purpose* stays even
  if its mechanism changes.)
- **R2 Two independent reviewers** (Critic + PR reviewer) — each has caught
  bugs the other missed; keep both, delete their *overlap machinery*.
- **R3 The Stop-hook floor**: session cannot end with code changed against an
  active plan and no review evidence; reflection floor; in-message,
  copy-pasteable escape hatches; background-work deferral (STH-3W7F);
  gate attribution (`gates.json` banner/prefix mechanism).
- **R4 The no-arbitrary-code pattern**: a stable, allowlistable
  `prawduct-hook <subcmd>` surface so skills scope to
  `Bash(prawduct-hook …*)`, never `Bash(python3 -c *)`.
- **R5 Append-only governance ledger** written only by code; review telemetry
  (`review-stats`) on top.
- **R6 Product-owned committed state** (project-state.yaml, backlog, learnings,
  change-log, artifacts) untouched in shape by this program except where a
  design note says otherwise (memory convergence is Wave-2 scoped, see §5).
- **R7 Proportionality knobs**: risk-classified review rigor, doc-only
  carveouts, trivial-with-rationale, opt-in coverage/operator-verification.
- **R8 Onboard/migrate/doctor lifecycle** including one-commit reversible
  migration for existing consumers.
- **R9 Isolation between unrelated repos** (same-repo guard) — sharing is only
  ever within one product's checkouts.
- **R10 Do-not-reintroduce list** (inventory §6): content-hash freshness,
  git_sha evidence pinning, trivial fast-path, stamp-merged, file-sync.

### 4.2 Change (the kernel redesign proper)

- **C1 Evidence model**: replace label-matched single-slot records with
  SHA-keyed facts and a coverage algebra. A review fact = (base, head, files,
  findings, blocking-count, reviewer-roster, tier). The PR gate's question
  becomes *"does composed coverage span merge-base..HEAD at HEAD with zero
  unresolved blocking findings?"* — chains, doc-only allowances, and
  "demotion" special cases dissolve into interval composition. Ledger-style
  append-only store is the source of truth; any single-slot file is a derived
  cache. Test evidence: same treatment, keyed to tree state the run actually
  saw, with non-Python producers first-class (`--from-counts`/JUnit paths).
- **C2 Deterministic data plane**: every manifest, marker, record, and ledger
  write is code (`prawduct-hook` subcommands invoked at dispatch/completion
  events), driven by harness lifecycle hooks (SubagentStop et al.). Models
  hand judgment to the data plane as content, never as file-format authorship.
  Harness-volatility resilience rule (from critic-persistence-redesign):
  never depend on background/foreground defaults or fork-resume semantics.
- **C3 Fail-loud invariant**: a kernel error path may self-heal, no-op with a
  stderr explanation, or block — it may never leave state that a later reader
  will mistake for current. Broad-except pragma count becomes a tracked
  metric with a shrink target.
- **C4 Gate posture recalibration**: classify every gate as outcome (hard) or
  process (advisory) per the inventory matrix. Outcome gates: review coverage,
  test evidence, change-log-on-ship, operator verification. Process signals
  (reflection cadence, tripwires, synthesis nudges): advisory by design, and
  the work-model tripwire is a deletion candidate (§4.3).
- **C5 Identity & sharing**: evidence store lives per-repo (not per-worktree)
  so same-product checkouts compose; exact location/portability is Open
  Question Q2 (it decides whether the container/host split is actually fixed
  or only the worktree half).
- **C6 Feedback pull path**: a framework-side harvest (doctor subcommand or
  session-start advisory in THIS repo) that sweeps configured product paths
  for pending `area: prawduct-upstream` items — closing the loop that let one
  defect family span three releases.
- **C8 Branch-role-aware gate semantics** (owner, 2026-07-12): the testing
  burden sits intentionally at *entry to develop*, not at main promotion.
  Feature→develop PRs are evidence-gated (C1 coverage at HEAD, same clone
  reviews and opens the PR — owner confirmed this is always true). The
  develop→main promotion gate is a *policy* check — verify every commit in
  the promotion range arrived via a gated develop PR (ledger/PR bookkeeping),
  never a demand for fresh local evidence — so promotion works from any
  clone with no evidence transport. Pairs with **MIG-6B0R** (open since
  2026-05-19): strip prawduct artifacts from the promoted tree
  (filtered-merge deploy path) — main stays clean of governance bookkeeping;
  this program's release-path plan is MIG-6B0R's natural home.
- **C9 Zero-touch upgrade path** (owner, 2026-07-12): marketplace
  auto-updates mean a consumer repo can wake up on a new plugin version with
  no human aware of it — relying on someone to run `/prawduct:doctor` is not
  a plan (evidence: discodon-brooks2's api-versioning advisory, active and
  unactioned since 2026-07-11 — passive nudges fail). Three-tier requirement:
  (1) *Minimize migration surface by design* — the evidence store is
  gitignored and lazily initialized (an empty store needs no migration);
  hold the committed product-state contract stable across v3, or upgradable
  lazily on read, so most repos need no migration commit at all.
  (2) *Auto-run + agent-route* — the first SessionStart on a new version
  (`.prawduct-version` delta, the existing banner detection point)
  automatically performs any cutover touching only gitignored state, and if
  a tracked-file change is required, injects a directive briefing the AGENT
  acts on (run the migration, one-line human confirm) — never a banner the
  human must notice.
  (3) *Version interlock backstop* (with C7) — every hard gate checks the
  state-format version first and blocks loudly with the exact remedy command
  on mismatch; a new-version kernel never silently misreads old-format
  state. Covers headless/container sessions where no one can consent.
  Also in scope: in-session skew (an auto-update landing mid-session swaps
  hook binaries under a live session) — C7 records must make this detectable.
- **C7 Version-skew defense**: kernel records carry a schema version; readers
  reject-or-migrate explicitly instead of failing obscurely (CRT-J4PM
  suspected coordinator/hook skew).

### 4.3 Delete (opus-floor dividend + third-rework signals)

- Wave 3 "weaker-model scaffolding" program: cancelled as a category (owner's
  opus-floor assumption). Filled-example/checklist work survives only where it
  helps opus-class models too.
- Work-model term tripwire (WMK-4Q9T): the lexical approach fires on ordinary
  prose including the owner's own prompts, twice during its own review. With
  an opus-floor, requirements-precede-code is better carried by the
  methodology + review question ("does this capability trace to a documented
  requirement?" — the Wave 2 scope-check) than by token matching. Delete the
  extractor; keep tripwire #1 as a review obligation.
- The two-reviewer overlap machinery (efficiency review Overbuilt #4):
  extends_cumulative chain bookkeeping, record-audit protocol, "don't
  re-scan" prose — all subsumed by C1's coverage algebra.
- `stamp-merged`, `.sync-pending`, `.critic-test-findings.json` gitignore
  entry, and any other inventory-flagged vestige.
- Prose written to compensate for sub-opus parsing (per efficiency review
  Overbuilt #3, beyond what prose-diet already shipped).

## 5. Relationship to the accepted 2026-07-02 fix program

The July 2 review stays the parent diagnosis; its Wave 1 items shipped or are
shipping. This program **supersedes Wave 2's mechanism-level items** where C1
subsumes them (reviewer-dedup deletion, environments/worktree story,
gate-noise residuals) — subject to Q1. Wave 2's advisor-first stance and
plan-shape guidance items are prose/methodology work, orthogonal to the
kernel, and continue as planned. Memory convergence (reflections.md
retirement) remains a separate design-note-first item; the kernel program
must not silently absorb it (it changes the onboarded-repo contract — R8).

The July 2 guardrail binds this program doubly: *the fix program itself must
not get overbuilt; prefer deletion over patching; prefer convention over
machinery.*

## 6. Platform facts the design may rely on (verified 2026-07-12, live docs)

- Hook events incl. SessionStart/End, UserPromptSubmit, PreToolUse (can
  block), Stop, **SubagentStop with agent-type matcher + structured
  `agent_result`** (no transcript path), Pre/PostCompact, TaskCompleted,
  WorktreeCreate/Remove. Hooks can be scoped in skill/agent frontmatter
  (v2.1.197+).
- Plugins ship custom agent types with restricted tools (`agents/`), skills
  with `context: fork`, `allowed-tools`, `model`/`effort` overrides.
- **Schema-forced structured output exists only via the Workflow tool or the
  Agent SDK** — plugin subagents return freeform text. The partials +
  deterministic-merge pattern therefore remains the right shape for an
  always-on gate (Workflow stays rejected for the kernel: opt-in gated —
  reconfirmed from the persistence redesign).
- Headless (`claude -p`) runs hooks; PermissionRequest hooks don't fire there;
  SubagentStop-in-headless is **unverified — must be empirically tested during
  design** (the Stop-hook backstop already covers the miss case).
- `CLAUDE_PROJECT_DIR` is provided to hooks; no sanctioned per-plugin state
  dir exists — state location stays a prawduct decision (Q2).
- Volatility rule stands: v2.1.198 background-by-default broke the previous
  coordinator inline-resume design. Design only against documented lifecycle
  events + on-disk state.

## 7. Assumptions (vetoable)

- [ASSUMPTION: Opus-level floor means *prose* can assume strong judgment, but
  all bookkeeping stays deterministic — the roster evidence shows fable-class
  models omit keys under context pressure | HIGH impact | owner can override]
- [ASSUMPTION: No back-compat for *evidence records* — v3 starts consumers
  with an empty evidence store; in-flight branches re-review once. Committed
  product state (backlog/learnings/change-log/project-state) migrates
  losslessly | MED impact | owner can override]
- [ASSUMPTION: The Critic's three-role roster and reviewer-model tiering
  survive as configuration, not redesign surface | LOW impact | defer]
- [ASSUMPTION: The kernel stays Python + stdlib, distributed as today's plugin
  (no new runtime deps) | LOW impact | defer]

## 8. Open questions (owner) — asked 2026-07-12

- **Q1 Program shape** — **ANSWERED 2026-07-12: subsume.** The v3 kernel
  program absorbs the remaining Wave 2 mechanism items (reviewer-dedup
  deletion, environments/worktree story, gate-noise residuals), keeping the
  small-shippable-plan structure. Advisor-first tone and plan-shape prose
  items continue separately.
- **Q2 Evidence portability** — **ANSWERED 2026-07-12: local per-repo store,
  no pushable channel.** Owner confirmed review-and-PR are same-clone for all
  develop-entry PRs; develop→main promotion is deliberately policy-weight,
  not evidence-weight → C8. Git-notes portability is not needed (revisit only
  if a topology emerges where develop-entry review and PR-open are different
  clones). Findings-in-remote comfort was conditional on main staying clean —
  moot under local-only, but MIG-6B0R (strip on promotion) is pulled into
  scope via C8 regardless.
- **Q3 Migration posture** — **ANSWERED 2026-07-12: breaking release +
  doctor migration**, amended same day by owner: the migration must not
  depend on a human knowing to run anything (marketplace auto-updates are
  invisible). One breaking plugin release; evidence stores start empty
  (in-flight branches re-review once); committed product state carries over
  losslessly; no dual-semantics shims — and the upgrade UX is governed by
  **C9** (minimize migration surface → auto-run safe parts at SessionStart →
  agent-routed directive for any tracked-file change → version-interlocked
  gates as backstop). `/prawduct:doctor` remains the manual/repair entry
  point, not the primary path.
- **Q4 Interface versioning** — adopted per recommendation as a vetoable
  assumption (not separately owner-answered): kernel records carry a schema
  version with explicit reject-or-migrate (C7). Consistent with Q3's
  breaking-release posture; flag at design review if unwanted.
- **Opus-floor deletions (§4.3)** — **CONFIRMED 2026-07-12: delete both.**
  Wave 3 weaker-model scaffolding cancelled as a category; the work-model
  term tripwire (extractor + index machinery) is deleted, with
  requirements-precede-code carried by the review-time scope-check question.
  Supersedes WMK-4Q9T's fix-the-precision framing (deletion, not repair).

## 9. Out of scope for this program

- Methodology *content* rewrites beyond deleting sub-opus scaffolding prose
  (advisor-first tone work continues under the July 2 program).
- Memory convergence / reflections.md retirement (separate design note; R6).
- Backlog storage re-architecture (markdown-as-database strain is real —
   §1 — but it's a consumer-state contract change; file as its own
  discovery if the kernel program's fail-loud work doesn't relieve it).
- Any new suppression machinery (waiver DSLs, stopword lists) — banned by the
  July 2 guardrail.

## 10. Next step

Owner answers Q1-Q4 → planning (`methodology/planning.md`): decompose into
small independently-shippable plans (per July 2 program structure), starting
with C1 evidence model + C2 data plane (they unblock the most open defects:
CRT-8F3K, CRT-W2NV, CRT-J4PM, CRT-5D8Q, CRT-4B7X, plus the stale-evidence
tax).
