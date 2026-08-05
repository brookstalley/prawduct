# Issue #221 — Worktree-fork state pollution: Requirements

`status: draft · stage: requirements · area: worktree · added: 2026-08-05 · source:
scheduled backlog session · issue: https://github.com/brookstalley/prawduct/issues/221`

Related: STH-7W9K (this item's id alias), CRT-3X9D (`plugin/lib/critic_marker.py` — the
mutation-site guard pattern this item generalizes), STH-4K7N (the main-loop cwd-based resolver
this item's bug sits downstream of), GOV-4C7X / kernel-v3 (the evidence-store redesign that has
already narrowed part of this item's original exposure — see Grounding facts).

## Problem

`gitstate.resolve_project_dir` (used by every `prawduct-hook` invocation) resolves the project
root from the **current process's `cwd`** — correct for the main-loop Bash tool, whose `cwd`
tracks the session's active git worktree, but wrong for a `/prawduct:*` skill invoked
`context: fork`: the fork's `cwd` is pinned to the **launch** directory regardless of which
worktree the session has since entered. A fork that mutates `.prawduct/`-owned state during a
mid-session worktree entry therefore silently writes into the wrong working copy and **reports
success**. The source issue's adopter corroboration shows this is not a dogfooding-only edge case:
a product repo hit the same class independently, producing a diverged backlog item that required
manual reconciliation.

## Grounding facts

Re-verified against the current codebase (2026-08-05) rather than carried over unchanged from the
2026-07-16/19 filing — several things have moved since:

- `resolve_project_dir` (`plugin/lib/gitstate.py:80-118`) is a single choke point: every
  `prawduct-hook` subcommand resolves its project dir through `get_project_dir()`
  (`plugin/bin/prawduct-hook:44-64`), which calls it with `Path.cwd()`. There is exactly one place
  a fix needs to hook in for it to cover every mutating command automatically.
- **`context: fork` skills today**: `advisory`, `backlog`, `critic`, and `learnings`
  (`plugin/skills/*/SKILL.md` frontmatter). `learnings` is read-only (`Read, Agent` tools only, no
  `Write`/mutating `Bash`) — not exposed. The other three mutate state:
  - **`advisory`** — `prawduct-hook advisory dismiss|undismiss|resolve` writes
    `.prawduct/.advisories.json`. Fully exposed today; no mitigating change since the original
    filing.
  - **`backlog`** — exposed only on the **markdown backend** (`backlog_service_repo` unset in
    `project-state.yaml`): the skill itself directly `Read`/`Edit`/`Write`s `.prawduct/backlog.md`
    and stamps `backlog_format_version` into `project-state.yaml`, and `prawduct-hook backlog
    file|status|update|comment|claim|unclaim|link|unlink` all resolve through the same project
    dir. On the **GitHub Issues backend** (post-cutover), the adapter routes every live-backlog op
    to the network (`--repo owner/repo`) — no local backlog file is written, so this half of the
    original bug's exposure has already narrowed as products migrate, exactly as the source issue's
    own evidence anticipates ("the same tension the Issues backend resolves").
  - **`critic`** — `critic-begin`/`critic-consolidate`/`critic-end` write two per-worktree files:
    `.prawduct/.critic-active` (a TTL-bounded marker, self-healing per CRT-3X9D) and
    `.critic-findings.json` (an explicitly **derived, non-authoritative** view — CLAUDE.md: "no
    gate reads the view — gates compose over facts"). The **authoritative** write —
    `<git-common-dir>/prawduct/evidence.jsonl` — is already keyed to the shared git-common-dir, not
    the worktree, so it is immune to this bug **by construction** (kernel-v3). Critic's residual
    exposure is real but low-severity: a wrong-tree write here is self-correcting or non-binding,
    not silent-and-authoritative like `advisory`'s.
  - **`operator-verification`**'s mutating commands (`accept-`/`verify-operator-verification`) are
    invoked only from `doctor` and `pr` — **neither carries `context: fork`** in current
    frontmatter. They are not exposed via any shipped skill today, contrary to the original issue's
    evidence list (which named "backlog/advisory/operator-verification" together). This is a fact
    that has changed (or was already inaccurate) since filing, not a reason to skip fixing the
    shared path — see Decision 2.
- The only mitigation shipped so far is documentation: `plugin/methodology/building.md:15` ("launch,
  or `/clear`, in the worktree") and the companion durable rule in `.prawduct/learnings.md:299`.
  Neither is a mechanical guard; both rely on the operator remembering.
- `git_common_dir()` (`plugin/lib/gitstate.py:50-77`) already gives every worktree of one repo a
  shared, writable location outside any single worktree — the same primitive kernel-v3's evidence
  store uses to sidestep this exact class of problem for Critic's authoritative state.

## Decisions

**1. The MUST is "never silent," not "always correct."** A resolver can be wrong; a resolver that
writes to the wrong tree **and reports success** is the actual defect (the source issue's own
framing: "reports success"). The baseline fix this item requires is a **write-time guard** —
detect a cross-worktree mismatch and refuse loudly — independent of, and shippable before, any
improvement to how forks learn the correct worktree in the first place. This mirrors CRT-3X9D
directly: that guard exists because tool-restriction doesn't hold for subagents, so the invariant
was enforced "at the mutation site rather than relying on a tool restriction that doesn't hold."
The same reasoning applies here — a fork's `cwd` is an untrusted signal, so the fix belongs at the
write, not at the boundary that produced the bad `cwd`.

**2. Fix the shared choke point, not an enumerated skill list.** The original issue's affected-skill
list (backlog/advisory/operator-verification) is already stale (Grounding facts) — `learnings` is a
fork but unaffected, `critic`'s worst exposure is already closed, `operator-verification` isn't
reachable from any fork today. A fix implemented per-skill would need re-auditing every time a
skill's frontmatter or a new fork is added. The guard belongs in `get_project_dir()` /
`resolve_project_dir()` — the one place every mutating command already goes through — so coverage
is automatic and does not depend on anyone maintaining a list.

**3. Harness cooperation is a candidate detection *source*, never the correctness guarantee.**
The source issue's fix-shape menu item 3 (harness updates a fork's `cwd` on `EnterWorktree`) is
explicitly **out of scope**: prawduct does not control the harness, and a fix whose correctness
depends on an upstream Claude Code change would leave every current install exposed indefinitely.
Whatever signal the guard reads must be something prawduct itself writes and reads.

**4. Any new persisted signal must be session-scoped.** Worktrees exist specifically to let
multiple sessions work concurrently on the same repository (`building.md`'s parallel-chunk
guidance already assumes this). A natural candidate detection source is a marker written to the
shared `git-common-dir` (the same primitive the evidence store uses) recording "the active
worktree for this session" — but unlike the evidence store's tree-keyed facts, a
which-worktree-is-active fact is inherently session-specific, not repo-specific. A design that
writes one shared file per repo would make two concurrent sessions in two different worktrees
overwrite each other's marker, turning a single-session bug into a cross-session one — strictly
worse. The exact mechanism is a design-stage decision, but it must not regress concurrent-worktree
usage to satisfy this item.

**5. Documentation-only mitigation stays.** The `building.md` / `learnings.md` guidance ("launch, or
`/clear`, in the worktree") remains valid, low-cost defense-in-depth and is not removed or
superseded by the mechanical guard — the guard is what fires when someone doesn't follow it.

## Requirements

MUST unless marked SHOULD.

- **WT1** A guard lives in the shared project-dir-resolution path
  (`gitstate.resolve_project_dir` / `get_project_dir()`), not bolted onto individual `prawduct-hook`
  subcommands or skills — so every current and future `.prawduct/`-mutating command inherits it
  automatically (Decision 2).
- **WT2** When the guard detects that the project dir a mutating command is about to write to is
  not the session's true active worktree, the command MUST refuse the write and exit non-zero with
  a message naming both paths and the fix (launch or `/clear` in the worktree) — never a silent
  success against the wrong path (Decision 1).
- **WT3** The guard's detection source MUST be something prawduct itself writes and reads — it MUST
  NOT depend on any change to how the harness sets a fork's `cwd`/`CLAUDE_PROJECT_DIR` (Decision 3).
  Harness-side `EnterWorktree` improvement (the source issue's menu item 3) is out of scope for this
  item.
- **WT4** Whatever state the guard persists to detect the true active worktree MUST be scoped so
  that two sessions concurrently active in two different worktrees of the same repository never
  read or clobber each other's signal (Decision 4).
- **WT5** The guard covers, at minimum, every mutation path reachable from a `context: fork` skill
  today: `advisory` (`dismiss`/`undismiss`/`resolve`), `backlog` (all ops on the markdown backend,
  plus `backlog_format_version` writes to `project-state.yaml`; Issues-backend ops write no local
  backlog state and are unaffected), and `critic` (`.critic-active`, `.critic-findings.json`).
  Coverage of `operator-verification` is a direct consequence of WT1 (the shared choke point), not
  separate work, even though no shipped fork calls it today (Grounding facts).
- **WT6** The existing `building.md`/`learnings.md` documentation-only guidance is unchanged by this
  item (Decision 5).

## Acceptance

- [ ] Reproducing the source issue's repro (enter a worktree mid-session, run a `context: fork`
      skill that mutates `.prawduct/` state) no longer silently writes into the launch dir — the
      command either resolves to the correct worktree or fails loudly with an actionable message.
- [ ] Two sessions concurrently active in two different worktrees of the same repository, each
      running a fork-mutating skill, each affect only their own worktree's state.
- [ ] The fix requires no change to the harness (Claude Code) to take effect.
- [ ] `advisory`, `backlog` (markdown backend), and `critic`'s per-worktree writes are all covered
      by the same guard — no per-skill carve-out required.

## Scope-out (this item)

- The exact detection/marker mechanism and its storage location — design-stage decision, bounded by
  WT3 and WT4.
- Any change to harness `EnterWorktree` behavior (source issue's menu item 3).
- New protective work specific to `operator-verification` beyond what WT1's shared choke point gives
  it for free — no shipped fork calls it today, so there is nothing to retrofit beyond the guard
  itself.
- Re-litigating whether products should migrate off the markdown backlog backend — this item treats
  "some products remain on markdown, indefinitely" as a given fact, not something to change.
- Reconciling backlog state that already diverged from a past occurrence of this bug (the source
  issue's adopter-corroboration paragraph describes a manual reconciliation already completed) —
  that is remediation, not the prevention this item scopes.

## Evidence / references

- `plugin/lib/gitstate.py:80-118` — `resolve_project_dir`, the single choke point WT1 hooks into;
  correctly cwd-aware for the main loop, blind for a fork whose `cwd` never moved.
- `plugin/bin/prawduct-hook:44-64` — `get_project_dir()`, the hook's sole caller of the resolver.
- `plugin/lib/critic_marker.py:1-40` — the CRT-3X9D pattern (guard at the mutation site, not the
  tool-restriction boundary) this item generalizes to a second, distinct invariant.
- `plugin/lib/gitstate.py:50-77` — `git_common_dir()`, the shared-across-worktrees primitive a
  design-stage marker would likely build on, same as the evidence store already does.
- `plugin/skills/advisory/SKILL.md`, `plugin/skills/backlog/SKILL.md` +
  `plugin/skills/backlog/adapter-mode.md`, `plugin/skills/critic/SKILL.md` — the three currently
  exposed `context: fork` skills (Grounding facts).
- `plugin/skills/learnings/SKILL.md`, `plugin/skills/doctor/SKILL.md`, `plugin/skills/pr/SKILL.md` —
  confirmed either non-mutating (`learnings`) or not forked (`doctor`, `pr`), narrowing today's real
  exposure versus the original filing.
- `plugin/methodology/building.md:15` and `.prawduct/learnings.md:299` — the existing
  documentation-only mitigation this item leaves in place (Decision 5).
- Issue #221 (STH-7W9K) — original problem, repro, and adopter-corroboration evidence (discodon /
  SCH-2QW9 dedup note).
