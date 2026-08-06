"""Project-preferences enforcement: what the CI workflows may and may not restate.

Two facts about this repo live in `pyproject.toml` — the supported Python floor
(`requires-python`) and the test dependency list (the `dev` extra) — and a CI
workflow is the most natural place in the world to accidentally copy both. The
Direction norm is "every fact has one home; every other mention is a reference to
it," and the failure mode it describes is exact: bump the floor in `pyproject.toml`
and the workflow keeps testing the old one, silently, forever.

So the floor is allowed to appear in the matrix — a matrix cannot be computed from
a constraint expression — and this file is what makes it a *checked* copy rather
than a second home. The dependency list is not allowed to appear at all; there the
reference to the extra is available and is what CI must use. (CI's actual line is
`pip install -c constraints.txt ".[dev]"` — the `-c` half is clause 5 of the
upstream intake policy and is guarded next door in
`test_dependency_resolution_pinning.py`. This file cares only that the dependency
list is referenced rather than restated, which is true of either form.)

Also pinned here: the two things about `verify-release.yml` that are decisions
rather than details — it never publishes, and it never waves through an
unverifiable result — because both are invisible in the diff of a future edit that
removes them.
"""

from __future__ import annotations

import re
from pathlib import Path

# Imported plainly, not via `importorskip`. PyYAML is a declared dev dependency,
# so its absence is a broken environment rather than a reason to skip — and a
# guard that skips itself is indistinguishable from one that passes.
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
TESTS_WORKFLOW = WORKFLOWS / "tests.yml"
VERIFY_WORKFLOW = WORKFLOWS / "verify-release.yml"


def _load(path: Path) -> dict:
    """Parse a workflow, normalising YAML 1.1's `on` → `True` key collision.

    PyYAML reads the bare key `on` as the boolean `True`, so `doc["on"]` is a
    `KeyError` on every GitHub workflow ever written. Normalise once here rather
    than letting each test rediscover it.
    """
    doc = yaml.safe_load(path.read_text())
    if True in doc:
        doc["on"] = doc.pop(True)
    return doc


def _scalars(node: object) -> list[str]:
    """Every string in a parsed workflow — keys and values, recursively.

    These checks look at what the workflow *executes*, never at its raw text.
    A workflow that deliberately omits something explains the omission in a
    comment, and a text scan reads that explanation as the very thing it forbids:
    the sentence "`--allow-unverifiable` is absent on purpose" contains
    `--allow-unverifiable`. Parsing drops comments, so the assertion lands on the
    steps and not on the prose about them.
    """
    found: list[str] = []
    if isinstance(node, str):
        found.append(node)
    elif isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str):
                found.append(key)
            found.extend(_scalars(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_scalars(item))
    return found


def _requires_python_floor() -> str:
    """The lower bound declared by `pyproject.toml`, e.g. `"3.10"`."""
    text = (REPO_ROOT / "pyproject.toml").read_text()
    match = re.search(r'^requires-python\s*=\s*"[><=~^]*\s*([0-9]+\.[0-9]+)', text, re.MULTILINE)
    assert match, "pyproject.toml must declare requires-python with a floor version"
    return match.group(1)


class TestWorkflowsExist:
    def test_both_workflows_are_present(self):
        # Red if a workflow is deleted or renamed without updating this file —
        # which is the point: the rest of these assertions would otherwise pass
        # vacuously against a repo with no CI at all.
        assert TESTS_WORKFLOW.exists(), "the suite must run in CI (.github/workflows/tests.yml)"
        assert VERIFY_WORKFLOW.exists(), (
            "a published release must be verified in CI (.github/workflows/verify-release.yml)"
        )


class TestPythonFloorIsNotASecondHome:
    def test_matrix_covers_the_declared_floor(self):
        # Red if `requires-python` is raised (say to 3.11) and the matrix is not,
        # or vice versa. Either way one of the two is lying about what is supported.
        floor = _requires_python_floor()
        matrix = _load(TESTS_WORKFLOW)["jobs"]["pytest"]["strategy"]["matrix"]["python-version"]
        versions = [str(v) for v in matrix]
        assert floor in versions, (
            f"pyproject.toml declares requires-python >= {floor}, but the CI matrix "
            f"({', '.join(versions)}) never exercises it — the floor would be an "
            "untested claim"
        )

    def test_matrix_does_not_test_below_the_declared_floor(self):
        # Red if the matrix keeps an EOL leg after the floor moves up. Testing
        # below what the project supports is wasted CI and a misleading green.
        floor = tuple(int(part) for part in _requires_python_floor().split("."))
        matrix = _load(TESTS_WORKFLOW)["jobs"]["pytest"]["strategy"]["matrix"]["python-version"]
        below = [
            str(v) for v in matrix if tuple(int(p) for p in str(v).split(".")) < floor
        ]
        assert not below, (
            f"CI tests Python {', '.join(below)}, below the declared floor "
            f"{'.'.join(str(p) for p in floor)}"
        )


class TestNoRestatedConfiguration:
    def test_dependencies_are_installed_through_the_dev_extra(self):
        # Red if someone replaces the extra with an explicit `pip install pytest
        # pytest-xdist ...` list, which is the second home the module docstring
        # exists to prevent.
        scalars = _scalars(_load(TESTS_WORKFLOW))
        assert any('".[dev]"' in s for s in scalars), (
            "CI must install test dependencies via the dev extra, not by listing them"
        )
        for package in ("pytest-xdist", "pytest-timeout", "pyyaml"):
            assert not [s for s in scalars if package in s], (
                f"{package} is named in tests.yml; the dev extra in "
                "pyproject.toml is its one home"
            )

    def test_pytest_flags_are_not_restated_in_the_workflow(self):
        # Red if a future edit inlines `-n auto` / `--timeout` into the run step.
        # Those live in pyproject's addopts; two copies means tuning one of them.
        scalars = _scalars(_load(TESTS_WORKFLOW))
        # `--timeout` needs no trailing space: the job's own `timeout-minutes`
        # key does not contain it, so the bare form still catches `--timeout=30`.
        for flag in ("-n auto", "--dist", "--timeout", "testpaths"):
            offenders = [s for s in scalars if flag in s]
            assert not offenders, (
                f"{flag!r} appears in tests.yml ({offenders}); pytest configuration "
                "belongs in pyproject.toml's [tool.pytest.ini_options]"
            )


class TestSuiteRunsOnEverything:
    def test_no_path_filters_narrow_the_trigger(self):
        # Red if anyone adds `paths:` / `paths-ignore:` to skip doc-only changes.
        # `tests/test_norm_probes.py` reads the live project-state.yaml, so a
        # `.md`-and-`.prawduct/**` change genuinely can turn the suite red — a
        # filter calling those paths untestable would hide exactly that break.
        triggers = _load(TESTS_WORKFLOW)["on"]
        for event, config in triggers.items():
            if not isinstance(config, dict):
                continue
            for key in ("paths", "paths-ignore"):
                assert key not in config, (
                    f"tests.yml filters {event} by {key}; a docs-only change can "
                    "still break this suite"
                )

    def test_runs_on_push_and_pull_request(self):
        triggers = _load(TESTS_WORKFLOW)["on"]
        assert "push" in triggers and "pull_request" in triggers, (
            "the suite must run on both push and pull_request"
        )


class TestVerifyReleaseNeverPublishes:
    def test_the_token_cannot_publish(self):
        """The property, not the spelling.

        `test_no_publish_step` below is a denylist of six literals, and a
        denylist only ever catches what someone thought to list — `gh api
        --method POST /repos/{owner}/{repo}/releases` or a bare `curl` walks
        straight through it. What actually makes publishing impossible is the
        token: the Releases API needs `contents: write`, so pinning the
        workflow to `contents: read` enforces the owner's ruling against every
        spelling at once, including ones that do not exist yet.
        """
        permissions = _load(VERIFY_WORKFLOW).get("permissions")
        assert permissions == {"contents": "read"}, (
            "verify-release.yml must grant exactly `contents: read`; publishing a "
            f"Release needs `contents: write`, and this is what makes the no-publish "
            f"ruling structural rather than a matter of spelling (found: {permissions!r})"
        )
        job = _load(VERIFY_WORKFLOW)["jobs"]["verify"]
        assert "permissions" not in job, (
            "the verify job overrides workflow-level permissions; the read-only "
            "grant above is only binding while nothing widens it"
        )

    def test_no_publish_step(self):
        # Red the moment a `gh release create` (or an upload/publish action)
        # appears. Publishing notifies watchers and is not cleanly retractable;
        # the owner ruling is that CI verifies and a human publishes.
        scalars = _scalars(_load(VERIFY_WORKFLOW))
        for forbidden in (
            "gh release create",
            "gh release edit",
            "gh release upload",
            "softprops/action-gh-release",
            "ncipollo/release-action",
            "actions/create-release",
        ):
            assert not [s for s in scalars if forbidden in s], (
                f"verify-release.yml runs {forbidden!r} — this workflow verifies "
                "a release and never publishes one (owner ruling)"
            )

    def test_unverifiable_is_not_waved_through(self):
        # Red if `--allow-unverifiable` is added to quiet a failing job. Exit 3
        # exists so that "could not check the Releases page" is not green; passing
        # that flag in CI turns the check back into the thing it replaced.
        scalars = _scalars(_load(VERIFY_WORKFLOW))
        assert not [s for s in scalars if "--allow-unverifiable" in s], (
            "verify-release.yml passes --allow-unverifiable; CI must fail when a "
            "check could not run"
        )

    def test_fetches_the_ref_containment_is_checked_against(self):
        # Red if the explicit origin/main fetch is dropped. actions/checkout leaves
        # no origin/main on a tag build, and without it every run reports
        # unverifiable — a permanently red job that says nothing about the release.
        scalars = _scalars(_load(VERIFY_WORKFLOW))
        assert [s for s in scalars if "refs/remotes/origin/main" in s], (
            "verify-release.yml must fetch origin/main; the containment check "
            "cannot answer without it"
        )

    def test_triggers_on_tag_push(self):
        triggers = _load(VERIFY_WORKFLOW)["on"]
        assert "push" in triggers, "verify-release.yml must trigger on tag push"
        assert triggers["push"].get("tags"), (
            "verify-release.yml must be scoped to tag pushes, not every push"
        )
