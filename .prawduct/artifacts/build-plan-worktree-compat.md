---
artifact: build-plan
version: 2
scope: worktree-compat
depends_on: []
last_validated: null
---

<!-- Build Plan — Worktree compatibility for governance gates + critic/pr skills
     Backlog: STH-4K7N (related: CRT-8D2W)
     Incoming bug: incoming-bugs/governance-gates-and-critic-pr-skills-dont-compose-with-git-worktrees.md
     This is framework work on an existing repo — the new-product Scaffolding /
     Project Structure sections of the template are N/A (noted, not filled). -->

## Requirements Confidence

**Level:** High

**Why:** The problem, success, and scope are each one sentence. Problem: hooks
resolve `.prawduct/` to the launch dir (`CLAUDE_PROJECT_DIR`) while the agent
side resolves to the session worktree (cwd), so worktree-written gate state is
invisible to the Stop + cumulative-critic gates → false blocks and an off-protocol
workaround. Success: the hooks resolve `.prawduct/` to the session's *actual*
worktree, so the existing (already-relative) critic/pr skills compose in place.
Scope: state-resolution change + tests + methodology guidance; no change to git
operations (already worktree-safe) or to tracked artifacts (branch version is
correct).

**Open assumptions / unknowns:**
- `[ASSUMPTION: a real Stop/SessionStart hook process receives the session worktree as its process cwd (os.getcwd()) — the Claude Code docs say hook cwd tracks the session incl. EnterWorktree, and lib/briefing.py already detects the hook "operating on" a worktree branch | HIGH impact | confirm empirically post-merge via an operator-verification note; if false, the contingency is to consult the hook stdin `cwd` field (requires centralizing the single stdin read in main()) — see Chunk 01 notes]`
- `[ASSUMPTION: per-worktree session/gate state is the desired model (isolation for parallel worktree agents), not shared-across-worktrees state | MED impact | user can override toward a shared --git-common-dir store; deferred as a follow-up, see Out of scope]`

**What would raise confidence:** N/A (High). The one HIGH assumption is confirmed
cheaply by the Chunk 01 simulation test (process-cwd→worktree resolution) plus a
post-merge real-worktree operator check.

## Status

- [ ] Chunk 01: Worktree-aware `.prawduct/` resolution (code + tests)
- [ ] Chunk 02: Worktree workflow guidance (methodology + skill notes)
<!-- views_enabled: checkboxes flip from change-log status=shipped at release;
     mid-branch progress is tracked in this Context line + git commits. -->
Context: Plan authored 2026-06-20 on feature/worktree-compat (off develop).
**BOTH CHUNKS DONE — branch ready for PR (user has not requested it yet).**
Ch.01 (e7b65c6): `resolve_project_dir` in lib/gitstate.py + hook delegation, 10
tests, Critic final passed. Ch.02 (34609e5): building.md worktree callout +
critic/pr skill notes + VRF-001 + change-log entry. Warning fix (3b13720).
Cumulative Critic (cumulative mode) passed 0-blocking; `check-cumulative-critic`
SATISFIED → `/prawduct:pr create` unblocked. Suite 1341 green, evidence @ HEAD.
Follow-up filed: STH-3R8K (observable worktree-redirect signal). Open assumption
(live hook-process cwd == worktree) queued for post-merge check as VRF-001.

## Scaffolding

N/A — existing framework repo. Tests run via the repo's standard `pytest` suite
(`tests/`). No new dependencies.

### Verification Strategy

Beyond the automated suite: a post-merge **operator verification** in a real
worktree session — launch/enter a worktree, run `/prawduct:critic` and
`/prawduct:pr`, and confirm the Stop gate, `.critic-findings.json`, and the
cumulative-critic record all resolve against the worktree's `.prawduct/` (Chunk
02 queues this; it confirms the HIGH assumption against the live harness, which
a unit test cannot reach).

## Project Structure

N/A — existing layout. Resolver lives in `lib/gitstate.py` (the canonical git-probe
module); `bin/prawduct-hook` and the two SessionStart hook scripts call it.

## Build Chunks

### Chunk 01: Worktree-aware `.prawduct/` resolution

- **Description:** Make state resolution follow the session into its git worktree
  instead of pinning to the launch dir. Add a canonical resolver to
  `lib/gitstate.py` that returns the session's git toplevel — `git rev-parse
  --show-toplevel` from the process cwd — and prefer it over `CLAUDE_PROJECT_DIR`
  **only when cwd is a worktree of the SAME repo** (shared `--git-common-dir`),
  falling back to today's behavior (`CLAUDE_PROJECT_DIR` → cwd) otherwise. Route
  `bin/prawduct-hook`'s `get_project_dir()` through it so hooks and the agent-side
  (already-relative) skill writes land in the SAME `.prawduct/`. This single
  resolution point is threaded into every gate (Stop, cumulative-critic,
  critic-mode inference, session markers via `cmd_clear`, and all agent-invoked
  commands), so it is the architectural keystone.

  **Scope refinement (from build):** the two SessionStart scripts
  `hooks/digest.py` (slim/full digest selection) and `hooks/banner.py`
  (version-notice marker) are descoped from the code change — neither touches
  gate state, both run only at SessionStart (cwd == launch dir there), and
  `banner.py` *deliberately* refuses a cwd fallback ("marker write must never
  land in an unexpected repo"). Making them worktree-aware would add lib coupling
  to intentionally self-contained scripts for no gate-correctness gain (Scope
  Discipline). They stay `CLAUDE_PROJECT_DIR`-pinned.
- **Depends on:** none
- **Artifacts consumed:** this plan; the incoming bug report.
- **Deliverables:**
  - `lib/gitstate.py` — new `resolve_project_dir(env_project_dir, cwd)` (pure,
    testable: takes the candidate dir from `CLAUDE_PROJECT_DIR` and the cwd, runs
    `git rev-parse --show-toplevel`, returns the worktree toplevel or the fallback).
  - `bin/prawduct-hook` — `get_project_dir()` delegates to the resolver (keeps the
    `CLAUDE_PROJECT_DIR`/cwd fallback as the floor).
  - new `tests/test_project_dir_resolution.py` — test module for the resolver +
    the bin delegation (see Tests).
- **Tests:**
  - Resolver returns the **worktree** toplevel when process cwd is inside a real
    worktree (create a `git worktree add`, chdir, assert resolution == worktree
    root, not the primary). This is the empirical confirmation of the HIGH
    assumption at the mechanism level.
  - Resolver returns the **repo root** when cwd is a subdirectory of the primary
    checkout (toplevel walk-up).
  - **No-regression:** in an ordinary single-checkout repo, resolution ==
    `CLAUDE_PROJECT_DIR` (the change is a no-op there).
  - Fallback: cwd not a git repo → returns `CLAUDE_PROJECT_DIR` (or cwd if unset),
    matching today.
  - **Same-repo guard:** cwd is an *unrelated* git repo (different
    `--git-common-dir`) → honors the `CLAUDE_PROJECT_DIR` pin, not cwd's toplevel.
  - `bin/prawduct-hook get_project_dir()` goes through the resolver (delegation +
    self-check: from this very checkout it returns this checkout's root — the
    "don't saw the branch you stand on" check for a session-governing runtime).
- **Acceptance criteria:** `pytest` green (full suite — the change touches the
  single resolution point threaded everywhere, so the existing gate/briefing tests
  exercise it); new resolver tests pass; no behavior change for a non-worktree repo.
- **Critic mode:** final
  <!-- Override forward from inferred `chunk`: this first chunk lands the
       load-bearing resolution keystone whose coherence every gate depends on;
       Goals 4-7 + cross-checks pay off before Chunk 02's docs reference it. -->
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic final` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status
  <!-- Contingency (only if a live-harness check later shows process cwd does NOT
       track the worktree): add stdin `cwd`-field consultation by centralizing the
       single stdin.read() in main() and threading the parsed input to both
       get_project_dir() and cmd_user_prompt_submit (which reads stdin today at
       ~L2230). Kept out of the default path to avoid the stdin-consumption
       refactor unless the simpler os.getcwd() resolution proves insufficient. -->

### Chunk 02: Worktree workflow guidance (methodology + skill notes)

- **Description:** Document the now-supported worktree workflow so repos stop
  reinventing the private "review in primary, merge with raw `gh`" workaround. Add
  a short worktree subsection to `methodology/building.md` (work cycles compose in
  a worktree; run `/prawduct:critic` and `/prawduct:pr` *from the worktree*; the
  Stop gate, findings, and cumulative record resolve against the worktree's
  `.prawduct/`). Note the one edge — a session that starts in primary and
  `EnterWorktree`s mid-cycle leaves the SessionStart lifecycle markers
  (`.session-start`, `.session-git-baseline`) in primary; readers fail safe (toward
  more gating), and the clean pattern is to launch/`/clear` in the worktree. Add a
  one-line pointer in the `critic` and `pr` skill docs that they operate on the
  current worktree. Queue the post-merge operator-verification check.
- **Depends on:** Chunk 01
- **Artifacts consumed:** Chunk 01 deliverables; `methodology/building.md`;
  `skills/critic/SKILL.md`; `skills/pr/SKILL.md`.
- **Deliverables:**
  - `methodology/building.md` — new "Working in a git worktree" subsection.
  - `skills/critic/SKILL.md`, `skills/pr/SKILL.md` — a one-line worktree note each
    (they already use relative `.prawduct/` paths; this makes the support explicit).
  - `.prawduct/operator-verification.md` — queued entry for the live-worktree check.
- **Tests:** none new (prose). The methodology/skill token-budget guardrail tests
  in `tests/` must stay green — keep additions terse (trim adjacent prose if a
  budget is pressured, per the planning "enumerate the surfaces" guidance).
- **Acceptance criteria:** `pytest` green (incl. doc token-budget guards); the
  worktree workflow is documented in `building.md`; both skills carry the note.
- **Type:** cumulative-final
  <!-- Last chunk; single PR. Its own review IS the one `/prawduct:critic
       cumulative` against merge-base...HEAD (covers Chunk 01's code + this
       chunk's docs) — the /prawduct:pr create gate. Commit first, then run once. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed and chunk marked `[x]` in Status
  3. `/prawduct:critic cumulative` run against `merge-base...HEAD` and blocking
     findings resolved — the gate for `/prawduct:pr create`.

## Out of scope (follow-ups)

- **Shared cross-worktree state via `--git-common-dir`** (e.g. one audit ledger /
  advisory store across all worktrees, or lifecycle markers in the shared `.git`).
  The per-worktree model is intentional (isolation for parallel worktree agents);
  a shared store is a separate design with its own tradeoffs. Capture to backlog
  if the mid-session-enter edge proves painful in practice.
- **CRT-8D2W** (Critic-in-worktree for reviewer *isolation*) — distinct motivation
  (an independent reviewer shouldn't mutate the session tree); already partially
  obsoleted by tracked build plans + the critic-session guard. Not addressed here.
- The upstream `EnterWorktree` default-base issue (origin/HEAD=main on gitflow) is
  a harness bug, not prawduct's — already noted in the bug report and adjacent to
  the filed `resolve-base-ignores-origin-head` item.

## Early Feedback Milestone

**Milestone chunk:** Chunk 01 (the resolver is independently verifiable; the
worktree-resolution behavior can be exercised the moment it lands).

## Governance Checkpoints

**Commit & PR cadence:** Commit per chunk. Chunk 01 gets a `final` review (keystone);
Chunk 02 is `cumulative-final` — commit it, then one `/prawduct:critic cumulative`
over `merge-base...HEAD` is both its review and the `/prawduct:pr create` gate.

- After Chunk 01: `final` review — validate the resolution keystone before docs build on it.
- After Chunk 02: `cumulative` review — the PR-creation gate over the whole branch.
