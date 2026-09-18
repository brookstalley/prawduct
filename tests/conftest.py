"""
Root conftest.py — import path for the relocated plugin, plus test parallelization.

Auto-groups tests by directory so same-directory tests run serially on one
worker (preserving fixture/state isolation) while different directories
run in parallel across workers.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
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


# =============================================================================
# The scope record — this repo's producer for `docs/test-report-contract.md`
# =============================================================================
#
# `pyproject.toml`'s `addopts` makes a JUnit report a side effect of every run,
# so a run made outside `prawduct-hook test-evidence record` can be ingested
# instead of paid for twice. That is only safe if the recorder can tell a
# whole-suite report from a narrowed one, because both now sit at the same path
# and look alike. This writes the record that tells them apart.
#
# The framework does not install this: prawduct states the requirement and reads
# the record, and each product wires its own runner — its ratified norms say it
# guides and reviews and never implements. This repo is a product like any
# other, and this is its implementation. (No `artifacts/…` citation here on
# purpose: this file is also the worked example a consumer copies, and in their
# repo that path resolves to THEIR artifact.)

SCOPE_RECORD_SUFFIX = ".scope.json"

#: The contract's two verdict values, spelled literally rather than imported
#: from `lib.report_scope`: this file is also the worked example a consumer
#: copies into a repo that has no `plugin/` beside it, and the integration test
#: runs a COPY of it in a scratch project for exactly that reason. The two
#: spellings are pinned against each other in `tests/test_test_report_scope.py`,
#: so they cannot drift even though neither imports the other.
FULL = "full"
PARTIAL = "partial"

#: pytest exit statuses that mean the report cannot be a complete account of the
#: selection, whatever the selection was. `1` (tests failed) is deliberately
#: absent: a red suite is a complete run and recording it is the point of
#: record-on-red.
_INCOMPLETE_EXIT_STATUSES = {
    2: "the run was interrupted",
    3: "pytest hit an internal error",
    4: "pytest was invoked incorrectly",
    5: "no tests were collected",
}


def _selection_is_the_default(config) -> bool:
    """True when this invocation selected what a bare run selects.

    Compares RESOLVED paths, not the strings: the declared command says
    `pytest tests/` while `testpaths` says `tests`, and those are the same
    selection spelled two ways. Any node id (`::`) is a narrowing by
    definition and short-circuits.
    """
    args = list(config.args)
    if any("::" in arg for arg in args):
        return False
    invocation_dir = Path(config.invocation_params.dir)
    chosen = {(invocation_dir / arg).resolve() for arg in args}
    testpaths = [str(p) for p in config.getini("testpaths")]
    if testpaths:
        return chosen == {(Path(config.rootpath) / p).resolve() for p in testpaths}
    # No testpaths configured: a bare run collects from where it was invoked.
    return chosen in ({invocation_dir.resolve()}, {Path(config.rootpath).resolve()})


def classify_invocation(config, exitstatus) -> tuple[str, str | None]:
    """`("full", None)` or `("partial", why)` for one pytest invocation.

    Answers ONE question — *was anything narrowed?* — about the invocation,
    never about the result. A run that merely *could* stop early (`-x`) is
    `partial` even when it completed, because classifying the invocation needs
    no arithmetic over the report and arithmetic is where a false refusal
    would come from. `--ff` is absent on purpose: it reorders the selection
    without reducing it.
    """
    option = config.option
    incomplete = _INCOMPLETE_EXIT_STATUSES.get(exitstatus)
    if incomplete:
        return PARTIAL, f"{incomplete} (pytest exit {exitstatus})"
    if getattr(option, "keyword", ""):
        return PARTIAL, f"-k {option.keyword!r} narrowed the selection"
    if getattr(option, "markexpr", ""):
        return PARTIAL, f"-m {option.markexpr!r} narrowed the selection"
    if getattr(option, "deselect", None):
        return PARTIAL, "--deselect removed tests from the selection"
    if getattr(option, "ignore", None) or getattr(option, "ignore_glob", None):
        return PARTIAL, "--ignore removed paths from the selection"
    if getattr(option, "lf", False) or getattr(option, "stepwise", False):
        return PARTIAL, "the run was scoped to a previous run's failures (--lf/--sw)"
    if getattr(option, "collectonly", False):
        return PARTIAL, "--collect-only ran no tests"
    maxfail = getattr(option, "maxfail", 0) or 0
    if maxfail:
        return PARTIAL, f"--maxfail={maxfail} (or -x) can stop the run before the end"
    if not _selection_is_the_default(config):
        return PARTIAL, "the invocation named specific paths rather than the whole suite"
    return FULL, None


def write_scope_record(config, scope: str, why: str | None) -> Path | None:
    """Write the scope record beside this run's JUnit report; return its path.

    Returns None when there is nothing to describe — no `--junit-xml`, or an
    xdist worker process, which shares the controller's options but writes no
    report of its own. Atomic, because a reader that catches the file
    half-written sees malformed JSON, and malformed refuses.
    """
    xmlpath = getattr(config.option, "xmlpath", None)
    if not xmlpath or hasattr(config, "workerinput"):
        return None
    report = Path(xmlpath).resolve()
    record = {
        "v": 1,
        "scope": scope,
        "report": str(report),
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if why:
        record["why"] = why
    target = report.with_name(report.name + SCOPE_RECORD_SUFFIX)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".scope-", suffix=".tmp")
        with os.fdopen(fd, "w") as handle:
            handle.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
        # `mkstemp` creates 0600. The report beside this is world-readable, and
        # the recorder can be a different user from the one who ran the suite (a
        # container, a CI runner) — where it is, an unreadable record REFUSES
        # the ingest, because the reader fails closed on what it cannot read.
        os.chmod(tmp, 0o644)
        os.replace(tmp, target)
    except OSError as exc:
        # A read-only directory or a full disk must not take the suite down
        # with it: this describes the run, it is not part of it. Absence is the
        # permissive case, so failing here costs the guard and never produces a
        # false green — but it is said out loud, because an advisory that fails
        # silently manufactures the confidence it was meant to check.
        print(f"NOTE: could not write the test-report scope record ({exc}) — "
              f"{target} will be absent, and an ingest of this report will be "
              "trusted rather than checked", file=sys.stderr)
        return None
    return target


def pytest_configure(config):
    """Anchor the report to the project root, then claim it as incomplete.

    **The anchoring is not cosmetic.** pytest resolves `--junit-xml` against the
    INVOCATION directory (`os.path.abspath`), not the rootdir, so
    `cd tests && pytest` would write `tests/.prawduct/.test-report.xml` — a path
    the managed `.gitignore` entries do not match (a pattern containing a slash
    is anchored to the repo root) and the session boundary does not clear, which
    is untracked run output one `git add -A` from being committed. Rewriting the
    option here, before the junitxml plugin builds its writer, makes the
    conventional path mean the same thing from any working directory. Only a
    RELATIVE path is touched: an explicit absolute one is the caller's choice.

    **Then the record is claimed as incomplete.** A run that is killed, crashes,
    or is interrupted never reaches `pytest_sessionfinish`, and what it leaves
    behind is a truncated report. Writing `partial` first means the record
    beside such a report says so, rather than the PREVIOUS run's `full` verdict
    sitting there vouching for it.
    """
    xmlpath = getattr(config.option, "xmlpath", None)
    if xmlpath and not os.path.isabs(xmlpath):
        config.option.xmlpath = str(Path(config.rootpath) / xmlpath)
    write_scope_record(config, PARTIAL, "the run did not finish")


def pytest_sessionfinish(session, exitstatus):
    scope, why = classify_invocation(session.config, exitstatus)
    write_scope_record(session.config, scope, why)


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


#: A `.session-reflected` body that SATISFIES the Stop hook's reflection gate.
#:
#: The gate grades shape, not length (`lib/gates.reflection_shape`): the text
#: must name what was expected and what was actual, plus a root cause or its
#: explicit absence. Every fixture that wants the reflection gate quiet writes
#: this string, from ONE definition — the shape is a governance decision that
#: will move again, and forty hand-written variants of it is forty edits and
#: thirty-nine chances to write one that no longer passes.
#:
#: A fixture that wants the gate to FIRE writes its own text and says why, so
#: the two intents are never confused by a reader skimming for this name.
SHAPED_REFLECTION = (
    "Expected the chunk to land with the suite green; actual: it did, "
    "no surprises. No defect.\n"
)


@pytest.fixture(autouse=True, scope="session")
def _unpin_project_dir():
    """Remove `CLAUDE_PROJECT_DIR` from the environment for the whole session.

    **This closes a class that three hand-copied helpers could not.**
    `gitstate.resolve_project_dir` returns that pin whenever cwd is not a git
    work tree, and a pytest `tmp_path` never is — so any test spawning
    `prawduct-hook` with an inherited environment targets whatever the harness
    pinned instead of its fixture. Under a harness that sets the variable (Claude
    Code does), `tests/test_lifecycle_cli.py` and `tests/test_plan_archive.py`
    would run `lifecycle-repair` and `archive-plan` — both WRITERS — against the
    real repository. They pass today only because the variable happens to be
    unset here, which is the worst way for a hazard to be invisible.

    The per-file remedy was a pinned-env helper copied into each file that
    noticed. Three near-identical copies later, two write-command call sites
    were still open, because a convention only protects the files whose author
    knew about it. Deleting the variable once protects every test, including
    ones not yet written — which is the difference between fixing instances and
    closing a class.

    A test that WANTS the pin still sets it explicitly (`env={...}` on the
    subprocess, or `monkeypatch.setenv`); this only removes the ambient
    inheritance that nobody asked for.
    """
    import os

    saved = os.environ.pop("CLAUDE_PROJECT_DIR", None)
    try:
        yield
    finally:
        if saved is not None:
            os.environ["CLAUDE_PROJECT_DIR"] = saved
