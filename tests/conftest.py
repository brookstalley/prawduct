"""
Root conftest.py — import path for the relocated plugin, plus test parallelization.

Auto-groups tests by directory so same-directory tests run serially on one
worker (preserving fixture/state isolation) while different directories
run in parallel across workers.
"""

import sys
from pathlib import Path

import pytest

# The plugin lives in plugin/, not at the repo root (v3.1.1, GOV-4H7T): the marketplace copies its
# source directory wholesale with no exclusion mechanism, so anything beside the plugin ships to
# every consumer. `from lib import ...` and `from hooks import ...` therefore resolve against
# plugin/, and this is the one place that is stated.
#
# Individual test modules still compute a repo root and sys.path-insert it; that is now a harmless
# no-op for imports (the repo root holds no `lib/`) and is left alone rather than swept, because
# those inserts are also how each module finds its own fixtures.
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))


def pytest_collection_modifyitems(config, items):
    """Auto-assign xdist_group marks by test directory.

    Tests in the same directory run serially on one worker (deterministic order).
    Different directories run in parallel across workers.

    Example groups: "unit/eval", "unit/web", "integration", "root".
    """
    tests_root = Path(config.rootpath) / "tests"
    for item in items:
        if item.get_closest_marker("xdist_group"):
            continue  # Respect explicit marks
        try:
            rel = item.path.relative_to(tests_root)
            group = "/".join(rel.parts[:-1]) or "root"
        except ValueError:
            group = "root"
        item.add_marker(pytest.mark.xdist_group(group))


def pytest_report_header(config):
    """Print a notice when tests run in parallel via pytest-xdist."""
    worker_count = getattr(config, "workerinput", None)
    if worker_count is not None:
        return []  # Worker process — don't print
    num_workers = getattr(config.option, "numprocesses", None)
    if num_workers and num_workers != 0:
        return [
            "NOTE: Running with pytest-xdist (parallel). Use '-n0' for sequential execution.",
        ]
    return []


#: The v2 (pre-3.3.4, model-written) dispatch-manifest shape: parseable JSON
#: carrying none of the v3 interval fields. Lives HERE because two test modules
#: import it, pinning three distinct behaviours — the CRT-W2NV validation
#: regression and the #676 message readings in `test_critic_consolidate.py`, and
#: the Stop-hook backstop's version-skew cause in `test_stop_abandoned_critic.py`.
#: Hoisting it into ONE of those modules and hand-inlining the copy into the
#: other is how a "one definition" rationale ships with two definitions under it.
V2_MANIFEST = {
    "mode": "final-chunk-review", "mode_chosen_by": "rule-3",
    "roster": ["correctness", "design", "sustainability"],
    "commit_reviewed": "abc", "files_reviewed": ["x.py"],
    "scope": "demo", "model": "opus",
}
