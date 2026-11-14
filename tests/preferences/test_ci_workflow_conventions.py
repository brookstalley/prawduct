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
reference (`pip install ".[dev]"`) is available and is what CI must use.

Also pinned here: the two things about `verify-release.yml` that are decisions
rather than details — it never publishes, and it never waves through an
unverifiable result — because both are invisible in the diff of a future edit that
removes them.

And what must hold of `tests.yml` now that it holds a key to testament's pool, a key that
runs code on the pool's machines: no workflow hands that key to a fork's code, the job
that holds it installs nothing from a package index and runs no test, and the job that
runs the tests references no secret. The pool runs the suite in an image of its own, so
that image's Python is a third copy of the floor and is checked here like the matrix's.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

# Imported plainly, not via `importorskip`. PyYAML is a declared dev dependency,
# so its absence is a broken environment rather than a reason to skip — and a
# guard that skips itself is indistinguishable from one that passes.
import sys

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
TESTS_WORKFLOW = WORKFLOWS / "tests.yml"
VERIFY_WORKFLOW = WORKFLOWS / "verify-release.yml"
POOL_IMAGE = REPO_ROOT / "docker" / "testament.Dockerfile"
POOL_KEY = "${{ secrets.TESTAMENT_KEY }}"
POOL_STAGE = "python tools/ci-suite.py pool"
TESTS_STAGE = "python tools/ci-suite.py tests"


def _runner():
    """`tools/ci-suite.py`, imported by path (its name is not a module name), so the figures and
    names the workflow must agree with are read from their one home."""
    import importlib.util  # noqa: PLC0415 — only these two tests need it

    spec = importlib.util.spec_from_file_location("ci_suite_conventions", REPO_ROOT / "tools" / "ci-suite.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # a dataclass resolves its module through sys.modules
    spec.loader.exec_module(module)
    return module


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
    """The lower bound declared by `pyproject.toml`, e.g. `"3.14"`."""
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

    def test_the_enforced_floor_is_the_declared_floor(self):
        # Red if `requires-python` moves and the floor the hooks enforce does not.
        # A stale FLOOR passes CI silently: the suite runs on the new floor, so
        # nothing below it is ever exercised.
        path = REPO_ROOT / "plugin" / "bin" / "_python_floor.py"
        spec = importlib.util.spec_from_file_location("python_floor_pin", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.floor_text() == _requires_python_floor()

    def test_release_verification_runs_the_declared_floor(self):
        steps = _load(VERIFY_WORKFLOW)["jobs"]["verify"]["steps"]
        versions = [
            str(s["with"]["python-version"]) for s in steps
            if str(s.get("uses", "")).startswith("actions/setup-python") and "with" in s
        ]
        assert versions == [_requires_python_floor()], versions

    def test_the_doctor_check_names_the_declared_floor(self):
        doctor = (REPO_ROOT / "plugin" / "skills" / "doctor" / "SKILL.md").read_text()
        check = next(line for line in doctor.splitlines() if line.startswith("26. "))
        assert f"{_requires_python_floor()} or newer" in check

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


class TestThePoolImageRunsTheDeclaredFloor:
    def test_the_image_python_is_the_declared_floor(self):
        # Red if `requires-python` moves and the image does not, or the reverse. A run
        # the pool takes executes in this image and not on the matrix's interpreter, so
        # on that path the image is what exercises the floor: a matrix that still names
        # it would be covering a run that no longer happens there.
        bases = re.findall(r"^FROM\s+python:([0-9]+\.[0-9]+)", POOL_IMAGE.read_text(), re.MULTILINE)
        assert bases == [_requires_python_floor()], (
            f"docker/testament.Dockerfile builds on Python {bases}, and pyproject.toml "
            f"declares requires-python >= {_requires_python_floor()}"
        )


class TestThePoolKeyIsHeldByAJobThatRunsNoTest:
    """`TESTAMENT_KEY` submits code to the pool, where it runs on the owner's machines.

    GitHub gives a pull request from a fork no secrets, and that is the whole reason a
    stranger's code cannot reach the pool. Inside a run, the key is kept from the tests
    and from everything they import by being in a different job: a step's environment is
    readable by its child processes' children (`/proc/<ppid>/environ`), so a step, or a
    stripped environment, is not a boundary. Each test here is one way of undoing that.
    """

    def test_no_workflow_runs_on_pull_request_target(self):
        # Red if any workflow adds the trigger. `pull_request_target` runs with the base
        # repository's secrets, and a job that then checks out the pull request's head
        # has handed a fork's code the key.
        workflows = sorted(WORKFLOWS.glob("*.y*ml"))
        assert TESTS_WORKFLOW in workflows, "the scan must reach the workflow that holds the key"
        for path in workflows:
            triggers = _load(path)["on"]
            names = [triggers] if isinstance(triggers, str) else list(triggers)
            assert "pull_request_target" not in names, (
                f"{path.name} triggers on pull_request_target, which gives a fork's "
                "pull request this repository's secrets"
            )

    def test_the_key_is_named_once_by_the_pool_jobs_own_step(self):
        # Red if the key moves to a job's or the workflow's `env`, if a second step or
        # job names it, or if the step that holds it runs anything but the pool stage.
        doc = _load(TESTS_WORKFLOW)
        holders = [
            (name, step) for name, job in doc["jobs"].items() for step in job.get("steps", [])
            if POOL_KEY in (step.get("env") or {}).values()
        ]
        assert [(name, step.get("run")) for name, step in holders] == [("pool", POOL_STAGE)]
        mentions = [s for s in _scalars(doc) if "secrets" in s]
        assert mentions == [POOL_KEY], (
            "tests.yml reads `secrets` somewhere other than the pool step's own env "
            f"(every mention: {mentions})"
        )

    def test_no_workflow_reads_a_secret_except_that_step(self):
        # The same property over the whole directory: a new workflow that reads the key,
        # or passes every secret on with `secrets: inherit`, is a second holder.
        found = {
            path.name: [s for s in _scalars(_load(path)) if "secrets" in s]
            for path in sorted(WORKFLOWS.glob("*.y*ml"))
        }
        assert {name: hits for name, hits in found.items() if hits} == {"tests.yml": [POOL_KEY]}

    def test_the_job_that_holds_the_key_installs_nothing_and_runs_no_test(self):
        # Red if the pool job gains a step: a `pip install`, a `pytest`, a third-party
        # action. Whatever runs in that job runs within reach of the key, so the job is
        # held to exactly what it needs: GitHub's own checkout and Python, and the stage.
        steps = _load(TESTS_WORKFLOW)["jobs"]["pool"]["steps"]
        assert [step["run"] for step in steps if "run" in step] == [POOL_STAGE]
        actions = [str(step["uses"]).split("@")[0] for step in steps if "uses" in step]
        assert actions == ["actions/checkout", "actions/setup-python"], actions
        assert len(steps) == 3, "a step that neither runs nor uses is not one this test can read"

    def test_the_job_that_runs_the_tests_is_given_no_secret_and_only_the_pool_jobs_word(self):
        # The test job's one input from the pool job is where the suite ran. Anything
        # else passed across (a second output, the job's whole context) is a channel the
        # key could be put on by a later edit.
        doc = _load(TESTS_WORKFLOW)
        assert doc["jobs"]["pool"].get("outputs") == {"suite": "${{ steps.pool.outputs.suite }}"}
        job = doc["jobs"]["pytest"]
        stage = [step for step in job["steps"] if step.get("run") == TESTS_STAGE]
        assert len(stage) == 1, "the pytest job must run the tests stage, once"
        assert stage[0].get("env") == {_runner().RAN_ON: "${{ needs.pool.outputs.suite }}"}
        crossing = [s for s in _scalars(job) if "needs." in s]
        assert crossing == ["${{ needs.pool.outputs.suite }}"], crossing

    def test_the_pool_jobs_time_limit_outlasts_what_the_runner_may_wait(self):
        # Red if the allowance is raised and only its pin is updated. A job killed at its
        # limit writes no `suite=` output, so the test job falls back to the whole suite with
        # nothing saying why. The margin is for checkout, setup and the install itself.
        runner = _runner()
        limit = _load(TESTS_WORKFLOW)["jobs"]["pool"]["timeout-minutes"] * 60
        margin = 120
        assert limit >= runner.POOL_WAIT_SECONDS + runner.DOWNLOAD_SECONDS + margin, (
            limit, runner.POOL_WAIT_SECONDS, runner.DOWNLOAD_SECONDS)

    def test_the_test_job_runs_whatever_the_pool_jobs_result(self):
        # Red if the `if` is dropped. A job that `needs` a failed job is skipped by
        # default, so a failing pool run would skip the tests the pool leaves out, and a
        # refused key would leave the tree with no verdict at all: a red run that says
        # nothing about the code.
        job = _load(TESTS_WORKFLOW)["jobs"]["pytest"]
        assert job.get("needs") == "pool"
        assert job.get("if") == "${{ !cancelled() }}", job.get("if")

    def test_the_jobs_token_is_read_only(self):
        # The pool job runs a CLI it downloaded. What that process can do to this
        # repository is bounded by the token, as `verify-release.yml`'s no-publish rule is.
        doc = _load(TESTS_WORKFLOW)
        assert doc.get("permissions") == {"contents": "read"}, doc.get("permissions")
        widened = [name for name, job in doc["jobs"].items() if "permissions" in job]
        assert not widened, f"jobs override the workflow's read-only grant: {widened}"

    def test_no_step_runs_pytest_but_through_the_runner(self):
        # Red if a step runs `pytest` itself. The runner owns where the suite runs; a
        # second invocation is a second answer to that, and the place a pytest flag would
        # next be written.
        runs = [
            str(step.get("run", "")) for job in _load(TESTS_WORKFLOW)["jobs"].values()
            for step in job.get("steps", [])
        ]
        assert TESTS_STAGE in runs
        assert not [r for r in runs if "pytest" in r], runs

    def test_the_pool_addresses_are_variables_not_text(self):
        # The addresses are the pool operator's to change; a tracked file is not where
        # they are kept.
        env = next(
            step["env"] for step in _load(TESTS_WORKFLOW)["jobs"]["pool"]["steps"]
            if step.get("run") == POOL_STAGE
        )
        assert env["TESTAMENT_COORDINATOR"] == "${{ vars.TESTAMENT_COORDINATOR }}"
        assert env["TESTAMENT_CONSOLE"] == "${{ vars.TESTAMENT_CONSOLE }}"


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
