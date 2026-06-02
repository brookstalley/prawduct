# Release Process (v2.0 plugin)

How a Prawduct change goes from a feature branch to something consumers actually receive.
This is for **contributors to the framework**, not product-repo users.

## Branch model — gitflow

- **`develop`** — the integration branch. Feature branches (`feature/…`, `fix/…`) branch off
  `develop` and merge back into `develop`. Nothing here ships to consumers.
- **`main`** — the **release surface**. `main` only ever holds releases. Promoting `develop`
  → `main` is what publishes a new version.

Consumers pin the plugin + marketplace to **`ref: "main"`** (see the install reference in
`documentation/MIGRATION.md`). They never reference `develop`, so in-progress integration work
is invisible to them. Pinning `main` explicitly — rather than the bare repo — also avoids a
footgun: a bare repo silently follows GitHub's *default-branch* setting, which would ship
`develop` if that default ever changed.

## The version is the release trigger — not cosmetic

Claude Code resolves a plugin's version from `plugin.json` `version` first. With
`autoUpdate: true`, the consumer re-resolves `main` at session start, but **`version` is the
update cache key**: if you promote a commit to `main` without bumping `version`, `autoUpdate`
sees the same string and keeps the cached copy — **a release that forgets the version bump does
not ship.** Always bump `version` (and the `VERSION` file it mirrors) as part of the release.

> **One empirical unknown (Chunk 2 spike).** Whether `autoUpdate` on `ref: "main"` re-resolves
> to *main's HEAD* or only to the *latest tag* is undocumented. Both are fine under this model
> (main HEAD == latest release), but Chunk 2 confirms it empirically and records the result here.
> Documented fallback if the version-cache-key gate proves insufficient: pin the marketplace
> entry to `ref: "vX.Y.Z"` per release instead of `ref: "main"`.

## Release checklist (`develop` → `main`)

When `develop` is ready to release as `vX.Y.Z`:

1. **Merge `develop` → `main`.**
2. **Bump the version** in `.claude-plugin/plugin.json` `version` **and** the `VERSION` file
   (they mirror each other). This is the release trigger — without it, nothing ships.
3. **Flip the change-log entries** for the shipped work from `status=merged` to
   `status=shipped`, and add the `release=vX.Y.Z` and `scope=vX.Y.Z` tags to the entry's
   tag line:
   ```
   <!-- prawduct: chunks=01,02,… | release=vX.Y.Z | status=shipped | scope=vX.Y.Z -->
   ```
4. **Regenerate derived views:** `prawduct-hook regen-views`. With `views_enabled`, the build
   plan's `## Status` checkboxes, release notes, and `scope_rollups` are a *derived view* of
   the change-log's `status=shipped` entries — they flip to `[x]` only at this release step.
   Do **not** hand-edit the checkboxes; `regen-views` would revert the edit.
5. **Tag the release:** `git tag vX.Y.Z` (and push the tag).
6. **Confirm the banner.** On the next session against the new `main`, the version-delta banner
   shows `v(old) → vX.Y.Z` plus the crossed releases' change-log highlights, and announces any
   gate newly active in the range.

## Why the checkboxes stay `[ ]` during development

Because the Status checkboxes derive from `status=shipped` change-log entries, a chunk completed
on a feature branch stays `[ ]` until the `develop` → `main` release flips its change-log entry
to `shipped` and `regen-views` runs. During feature-branch development, the build plan's Context
line and git history are the progress record — not the checkboxes.
