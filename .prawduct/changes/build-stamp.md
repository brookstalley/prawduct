---
schema: 1
type: feature
scope: build-stamp
date: 2026-10-27
title: Facts record the plugin build they ran on, and stats can split a version by build
closes: [brookstalley/prawduct#1086]
---

#1086. Every evidence fact's `actor.plugin` read the same `3.8.0-dev…` for every develop build and
feature-branch head, so a beta comparison blended builds. A per-merge `-dev.N` bump was the
workaround, and it costs a change record, two boundary reviews and a full suite run per bump.

### Chunk 01: `actor.build`

- `evidence.append_fact` stamps an additive `actor.build`: the plugin checkout's commit sha (12 hex
  characters), with `+dirty` when the plugin directory has modified or untracked-unignored files.
  The same omitted-not-null rule as `actor.branch` applies. A marketplace install, a plugin root whose `VERSION`
  is not tracked by the checkout around it, a checkout with no commit, and any git failure record
  no build. No schema version moves.
- It is read once per process, using two git calls (about 35 ms warm, 125 ms cold on the owner's
  machine). The calls drop git's repository-locating environment variables, so a hook run from a
  product's git hook still reads the plugin checkout, not the product.
- `actor.build` travels with the facts through the notes transport to the product's own remote,
  as `actor.branch` does (`api-contract.md`, `evidence sync`). It names a commit of the plugin, not
  of the product, so it tells that remote nothing about the product's own code.
- Its git calls run with `GIT_OPTIONAL_LOCKS=0`, so reading the build never rewrites the index of
  the checkout the plugin runs from, which is often a developer's working tree.

### Chunk 02: `stats --by-build`

- `prawduct-hook stats --by-build` adds `by_build` (`{major.minor: {build: body}}`) next to an
  unchanged `by_version`, and the human report prints one block per build. Each row is computed
  over that build's facts, so rows need not sum to the version's totals. Builds are listed in
  the order the store first saw them. A fact with no build groups as `unstamped`.
- The contribution payload still carries only `major.minor` and the dev flag. Two new tests pin
  that `build` never reaches it.

## Consumer note
Every evidence fact now records which plugin build wrote it when the plugin runs
from a git checkout (a dev or beta build), as `actor.build`. A marketplace install records none.
To compare builds of the same version, run `prawduct-hook stats --by-build`. The build sha now
travels with those facts wherever `evidence sync` pushes them, which is your product's own remote,
as the branch name already does. Contribution reports to prawduct are unchanged: they still carry
only the major.minor version.
