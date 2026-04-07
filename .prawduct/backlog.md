# Backlog — prawduct

<!-- Work discovered during sessions but out of current scope.
     Add items at the top. Each is a bullet with source marker:
     (builder), (critic), (reflection), or (migrated).
     Review with /janitor or when planning new work. -->

- **Fingerprint parser doesn't handle paths with newlines/special chars** — `compute_test_fingerprint()` in `tools/product-hook` parses `git status --porcelain` (non-`-z`) using `line.split()` and `.strip('"')`. Robust for typical paths, but files with embedded newlines, NULs, or unusual quoting break the loop. Switch to `--porcelain -z` and a binary-safe parser. (critic)
- **product-hook decomposition** — Split 1,757-line monolith into logical modules (_gates.py, _briefing.py, _yaml_parser.py). Currently working and well-tested, but 5 distinct concerns in one file hinders readability. (janitor)
- **run_sync() decomposition** — Extract per-strategy logic (template, block_template, always_update, merge_settings) from 337-line function in sync_cmd.py. (janitor)
- **Flaky tests under parallel execution (xdist)** — Several tests fail intermittently with `-n10` but pass sequentially: `TestClear::test_appends_multiple_reflections`, `TestClear::test_skips_empty_reflection`, `TestStopPrReviewGate::test_stop_clean_without_pr`, `TestNewProject::test_warning_disappears_after_filling`, `TestTrySyncFrameworkDiscovery::test_manifest_framework_source`. Root cause likely race conditions in the subprocess-based hook tests sharing process-level state or temp dir contention. (builder)
- **Pre-existing timeout flakes in test_product_hook.py** — `TestStopCriticGate::test_no_build_plan_anywhere_skips_critic` and `TestCanaryDepNoRationale::test_no_manifest_file_no_flag` intermittently hit the 15s timeout. May need investigation into why the product-hook subprocess hangs in certain test configurations. (builder)
- **Session lock file for concurrent session detection** — Advisory lock file in product-hook clear/stop to warn when another Claude session is active on the same project. Agreed on non-blocking approach with staleness timeout (~4 hours). (builder)

