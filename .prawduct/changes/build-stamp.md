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
- `actor.build` travels with the facts through the notes transport to the product's own remote.
  It identifies no more than `actor.branch` already does; `api-contract.md` says so.

### Chunk 02: `stats --by-build`

- `prawduct-hook stats --by-build` adds `by_build` (`{major.minor: {build: body}}`) next to an
  unchanged `by_version`, and the human report prints one block per build. Builds are listed in
  the order the store first saw them. A fact with no build groups as `unstamped`.
- The contribution payload still carries only `major.minor` and the dev flag. Two new tests pin
  that `build` never reaches it.

### Chunk 03: change record

This fragment.

## Consumer note
Review, resolution and guard facts now record which plugin build wrote them when the plugin runs
from a git checkout (a dev or beta build), as `actor.build`. A marketplace install records none.
To compare builds of the same version, run `prawduct-hook stats --by-build`. Nothing you send
upstream changes: contribution reports still carry only the major.minor version.
