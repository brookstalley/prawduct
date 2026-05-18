# Change Log — {{PRODUCT_NAME}}

<!-- Append new entries at the top. Each entry is a ## section.
     This file is separate from project-state.yaml to reduce merge conflicts
     when multiple branches add entries simultaneously.

     # Tagged entries (optional, opt-in via `views_enabled: true` in project-state.yaml)

     When views are enabled, add a tag-line directly under each ## header to
     mark which build-plan chunks the entry shipped. `product-hook regen-views`
     uses these tags to regenerate the build-plan `## Status` block — flipping
     `[ ]` ↔ `[x]` from `status=shipped` tags. Untagged entries are ignored.

     Format:

         ## YYYY-MM-DD: title (vN.M.P)

         <!-- prawduct: chunks=00,01,02 | release=v1.3.18 | status=shipped | scope=v1.4 -->

         **Why:** ...

     Recognized keys:
       chunks   - comma-separated chunk IDs (zero-padded, must match
                  build-plan.md ## Status headers exactly: `Chunk 00:`)
       release  - version string (used by release-notes view, future)
       status   - shipped | in-progress | deferred
       scope    - rollup identifier (e.g., v1.4)

     With `views_enabled: true`, the Status checkboxes in build-plan.md are a
     derived view. Don't hand-edit them — add/update a tagged entry here and
     run `python3 tools/product-hook regen-views`. -->
