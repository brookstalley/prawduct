---
artifact: operational-spec
version: 1
depends_on:
  - artifact: nonfunctional-requirements
  - artifact: security-model
last_validated: null
---

# Operational Specification

<!-- "Operations" for a Claude Code plugin: how it's distributed, installed, updated, rolled back,
     backed up, and recovered. There is no server — deployment is a version promotion. Written
     toward the operational model we want. -->

## Direction

<!-- Ratified norms (2026-07-17). The Release Flow section below holds the descriptive detail; these
     are their binding form. See docs/norms.md. -->

- **Versioning is conservative: a small feature is a patch bump, not a minor-per-feature.**
  Why: keeps the version number meaningful rather than inflating it — the plugin semver is the one handle a consumer reads and the auto-update cache key, so it should track real significance. A departure (a minor bump for a small change, or the reverse) is a recorded decision, not a reflex.
  Status: steady-state. Judgment norm — no mechanical size test; audited by the janitor.
- **Gitflow: `develop` is the integration branch (features branch off it and merge back); `main` is the release surface and only ever holds releases; the `develop`→`main` promotion is a separate, deliberate single-parent step, never a `/prawduct:pr`. `main`'s tree is a *deliberately chosen and fully classified* snapshot of `develop` — every unreleased scope is either shipped or withheld behind a named open blocker, nothing unaccounted. Content-identity with `develop` is the expected outcome of a **whole-develop** promotion, not the invariant.**
  Why: unchanged, and this amendment serves it more faithfully than the wording it replaces. The purpose is that the branch-pinned marketplace resolves a *clean* release while feature granularity stays on `develop` — "conflating the two would either **ship integration WIP** or lose the release boundary." Content-identity was the mechanism chosen to secure that, but when `develop` holds unready work it *forces* shipping exactly the WIP the norm exists to prevent. The binding property is therefore the **partition** (every path shipped or withheld, verified at Phase 0 for scopes and Phase 2 for paths), with content-identity as its special case when nothing is withheld.
  Status: steady-state. **Amended 2026-07-29 by owner ruling** — `[DECISION: narrow the promotion mechanism from "content-identical tree-set" to "fully classified snapshot, content-identical when nothing is withheld" | the original mechanism contradicted its own rationale, forcing WIP to ship whenever develop held unready work; prawduct had already departed from it twice (v3.1.1, v3.1.2) with no recorded decision, so the norm was describing a practice that had ceased | user can veto or narrow]`. Prompted by the v3.1.2 near-miss, where following the promotion literally would have published a subsystem with all four of its go-live blockers open. Enforcement is `check-releasability` at Phase 0 (scopes) plus the path partition at step 10 of `runbooks/promote-a-pruned-release.md` — both landed, so the rationale stands on the mechanisms rather than on the item that prompted them. **Owner confirmed the ruling explicitly on 2026-07-29 at PR time**, out-of-diff, when the Critic (R-7) observed that the amendment's provenance was attested only inside the change that made it — an amendment self-certifying its own authority is the shape of laundering even when the substance is sound, so the confirmation is recorded here rather than inferred from the edit.

## Deployment

Prawduct is a **Claude Code plugin**, and it *is* its own single-plugin, git-backed marketplace.
"Deployment" is a **version promotion**, not a server rollout.

- **Install once per machine, onboard per repo.** The user installs the plugin at the user level
  (`claude plugin marketplace add …` + `plugin install`); each repo they want governed is onboarded
  with `/prawduct:onboard`, which commits only a small **install reference** to the repo's
  `.claude/settings.json` (marketplace + enabled plugin) plus a thin CLAUDE.md anchor. **No framework
  files are committed to the repo.**
- **Updates arrive through the marketplace with zero repo diff.** With auto-update, Claude Code
  re-resolves the latest release at session start — no sync step, no framework files to reconcile.
- **The version bump is the release mechanism.** The plugin's `version` (in the manifest, mirrored
  in the `VERSION` file) is the auto-update **cache key**: with the marketplace pinned to the
  release branch, the consumer re-resolves that branch each session, but if `version` is unchanged
  the cached copy is kept. **A release that forgets the version bump does not ship.** This is the
  single most important operational fact about deploying prawduct.

### Release Flow (gitflow)

- **`develop` is the integration branch** (features branch off it and merge back); **`main` is the
  release surface** and only ever holds releases.
- Releases land on `main` as **squash / single-parent** commits (not back-merged into `develop`), so
  `develop` and `main` accumulate divergent histories. **Two promotion shapes exist, and the
  descriptive claim that content is always identical was false for both of the last two releases:**
  - *Whole-develop* — the tree-set (`git read-tree`-style) reset to develop's tree plus a
    single-parent commit. Here `git diff --stat origin/main origin/develop` is empty afterwards, and
    that check is a valid completion test.
  - *Pruned* — used for **v3.1.1 and v3.1.2**, where only a classified subset shipped. `main`'s tree
    is deliberately **not** develop's, the content-identical check can never pass, and the completion
    test is the **partition**: every path in `origin/main..origin/develop` accounted for as shipped or
    deliberately withheld. The durable procedure is `runbooks/promote-a-pruned-release.md`, selected
    at Phase 2 by Phase 0's withheld count; `release-plan-v3.1.2-pruned.md` is the worked example.
- The release checklist: merge to `main`, **bump `version` + the `VERSION` file**, flip the release's
  change-log entries to `status=shipped`, regenerate derived views, tag `vX.Y.Z` on `main`, and
  confirm the version banner. Tags are decorative for delivery (the branch-pinned marketplace
  resolves the branch HEAD, not the latest tag) but are kept for human navigation.
- `/prawduct:pr` handles feature→`develop` PRs; it is **not** the release vehicle — the
  develop→main promotion is a separate, deliberate step.
- **Versioning is conservative:** small features are patch bumps, so the version stays meaningful
  rather than inflating minor-per-feature. **Ratified 2026-07-17 — see `## Direction` above, which
  is the binding form; this line is descriptive and tracks it.** *(Corrected 2026-07-21: this line
  had continued to read "a ratification candidate, not yet a written rule" for four days after the
  norm was ratified forty lines above it. That contradiction is not cosmetic — it is what licensed
  v3.1.1's release plan to infer a version convention from sampled `CHANGELOG.md` entries and
  record a compliant patch bump as a "departure," and what let the shipped release runbook assert
  that no written version policy exists. A stale description of a ratified norm is a norm that does
  not bind.)*
- **Major and minor tiers are practice, not ratified.** Observed: a break in gate semantics or
  persisted state formats has been a major bump; a substantial new capability or a subsystem going
  live has been a minor (v3.1.0 — structural coverage + norm lifecycle; v3.2.0 — planned for the
  backlog-service go-live). This is read off release history, **not** a written rule, and is
  deliberately left unratified — only the conservative-bump norm above binds. Do not present these
  two tiers as ratified.

## Backup & Recovery

Backup is **git**, by design — the recovery model falls straight out of the committed/gitignored
boundary:

- **Committed, therefore backed up with the repo:** `project-state.yaml`, `backlog.md`,
  `learnings.md` / `learnings-detail.md`, `artifacts/`, `change-log.md`, and the build plan. Losing a
  working copy loses nothing — clone again.
- **Gitignored and local, therefore ephemeral:** the evidence store, governance ledger, advisory
  nag log, findings cache, session markers, and test evidence. These are **regenerable or
  re-derivable** — a lost evidence store means past review facts are gone, but the next review
  re-establishes coverage; a lost advisory log just re-triggers the relevant nudges. Nothing here
  needs a backup regime.
- **Recovery = reclone + regenerate.** There is no database to restore, no point-in-time recovery to
  design. The one thing worth stating: the evidence store lives inside `.git` (the common dir), so a
  `.git` that survives carries review history across worktrees; a fresh clone starts its evidence
  store empty and rebuilds coverage from the next review forward.

## Monitoring

There is nothing running to monitor in the server sense; "monitoring" is the on-demand and
session-start health surface (detailed in `observability-strategy.md`):

- **`/prawduct:doctor`** — on-demand health check (healthy / degraded, with the specific reason) and
  repair.
- **The SessionStart briefing + advisories** — per-session surfacing of repo state, stale artifacts,
  size warnings, and outstanding nudges.
- **`review-stats`** — pulled telemetry over the governance ledger for the review wall-clock/cost
  budget.

## Failure Recovery

Proportionate to a local tool — mostly "the fail-soft design already handled it," with a few
explicit repair paths:

- **A probe/briefing error** degrades to a note and the session continues — no action needed beyond
  reading the note.
- **A broken or partial install** → `/prawduct:doctor` diagnoses and repairs (reconciles the install
  reference, gitignore contract, anchor, and core state).
- **A bad release** → roll back by pinning/reverting the plugin version; because `version` is the
  cache key, the consumer re-resolves the older release on next session start.
- **Uninstall / disable** is clean and reversible: `repo-disable` for one repo (via
  `.claude/settings.json`), or the documented full uninstall (remove `.prawduct/`, the marketplace +
  enabled-plugin entries, and the CLAUDE.md anchor block). The one destructive operation — migrating
  a legacy file-sync repo onto the plugin — lands as a **single revertible commit**.
- **A stuck in-flight review** self-heals: the active-review marker carries a TTL, and the
  session-end backstop consolidates or blocks with a named remedy rather than leaving the session
  wedged.
