---
schema: 1
type: chore
scope: version-dev-2
date: 2026-10-27
title: Develop builds stamp 3.8.0-dev.2, above the host-seam beta
---
The host-seam beta (#1086, on `feature/1037-host-seam`) stamps its builds 3.8.0-dev.1 so the facts
it records separate from earlier 3.8.0-dev builds. Develop kept 3.8.0-dev, so a machine moved from
the beta back to develop recorded a version that sorts below the beta's, and the update banner
announced the move as an upgrade with nothing in range to list. Develop now stamps 3.8.0-dev.2 in
`plugin/VERSION`, `plugin/.claude-plugin/plugin.json` and `pyproject.toml`, so every develop build
after the beta sorts above it. When host-seam merges it takes develop's stamp.

## Consumer note
none: a pre-release version stamp on the integration branch; releases set their own version.
