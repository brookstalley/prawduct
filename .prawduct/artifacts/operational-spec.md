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
  `develop` and `main` accumulate divergent histories while their **content stays identical** — a
  promotion is a tree-set (`git read-tree`-style) reset to develop's tree plus a single-parent
  commit, and the content-identical check (`git diff --stat` empty) is the invariant the model
  guarantees.
- The release checklist: merge to `main`, **bump `version` + the `VERSION` file**, flip the release's
  change-log entries to `status=shipped`, regenerate derived views, tag `vX.Y.Z` on `main`, and
  confirm the version banner. Tags are decorative for delivery (the branch-pinned marketplace
  resolves the branch HEAD, not the latest tag) but are kept for human navigation.
- `/prawduct:pr` handles feature→`develop` PRs; it is **not** the release vehicle — the
  develop→main promotion is a separate, deliberate step.
- **Versioning is conservative** (intended practice): small features are patch bumps, so the
  version stays meaningful rather than inflating minor-per-feature. *(Practice reflected in release
  history; a ratification candidate, not yet a written rule.)*

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
