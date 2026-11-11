#!/usr/bin/env python3
"""Run this repo's pytest suite for CI: on testament's pool when the workflow can use it, on
GitHub's runner when it cannot. Two stages, which the workflow runs as two jobs:

    python tools/ci-suite.py pool     the job that holds the pool's key
    python tools/ci-suite.py tests    the job that runs pytest

They are separate jobs, on separate machines, because the key must not be within reach of a
test. Keeping it out of pytest's environment is not enough: a process can read its parent's
environment (`/proc/<ppid>/environ`), and whatever a test imports runs as the same user. So the
`pool` stage installs nothing from a package index and runs no test, and the `tests` stage is
never given the key. The first tells the second where the suite ran, as one word.

The `pool` stage reads three settings from the environment:

    TESTAMENT_KEY          a client key for the pool (an Actions secret)
    TESTAMENT_COORDINATOR  the pool's wire address, which `testament run` submits to
    TESTAMENT_CONSOLE      the pool's console (https), which serves the pool's CLI build

What each stage does, and which of the two jobs can fail:

    no key                         `pool` passes and says so; `tests` runs the whole suite.
                                   A pull request from a fork is this case: it has no secrets.
    a key, and the pool answers    `pool` takes the pool's result for what `.testament.toml`
                                   selects; `tests` runs what the manifest selects out.
    a key, and the pool cannot     `pool` passes with a warning; `tests` runs the whole suite.
    be reached                     An outage says nothing about the tree.
    a key, and the pool refuses    `pool` fails; `tests` runs the whole suite, so the tree
    it, or a setting is missing    still gets its verdict. CI has stopped using the pool, and
                                   a red job is the only thing that says so to the person who
                                   can fix it.

Anything not known to be an outage is a refusal: the two are told apart by what the pool
reports (`error.retryable`) or the console answers, and an end this file does not recognise
fails the job rather than passing as a fallback nobody reads.

The CLI is the pool's own published build, fetched from its console with the job's key.
Testament's source is private, so a public repository's job cannot install it from source, and
a build taken from the pool is never the wrong version for that pool.

Standard library only: the `pool` stage runs where nothing has been installed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / ".testament.toml"

# Where the console serves the pool's current CLI build to a client key, and the header that
# carries the digest the pool's signed release names for it.
CLI_WHEEL_PATH = "/api/v1/cli/wheel"
WHEEL_SHA256 = "X-Testament-Wheel-SHA256"
# The download's name becomes a path and is handed to pip, which reads a wheel's name.
WHEEL_NAME = re.compile(r"testament-[0-9A-Za-z_.!+]+-py3-none-any\.whl")
DOWNLOAD_SECONDS = 120

# How long the `pool` stage waits on the pool, over both attempts, before leaving the suite to
# the `tests` stage. The pool's own run of this suite takes about a minute; the rest is room to
# queue behind other people's work. It is bounded so that a busy pool costs a fallback rather
# than the job's time limit, which would end it with no verdict at all, and the workflow's
# limit for that job is set from this number.
POOL_WAIT_SECONDS = 600

# The one word the `pool` stage hands the `tests` stage: where the suite ran. The workflow
# carries it as a job output into this variable. Any other value, an empty one included, is
# read as "not on the pool", so a `pool` job that died before answering costs a full run on the
# job and never a suite that ran nowhere.
RAN_ON = "CI_SUITE_RAN_ON"
ON_POOL, ON_JOB = "pool", "job"
# Console answers that mean "not now" rather than "not you": the server is failing, or busy.
CONSOLE_OUTAGES = (408, 429)

# Envelope exit codes that are test results: passed, failed, nothing collected. Everything
# else, 2 included, is not a statement about the tests.
RESULT_CODES = (0, 1, 5)
NOTHING_COLLECTED = 5
# Failing tests named in the summary and annotated; the log holds the rest.
NAMED_FAILURES = 50


class Unavailable(Exception):
    """The pool cannot be used right now, and that says nothing about the job or the tree."""


class Refused(Exception):
    """The pool, or the job's own settings, will not let this job use the pool."""


@dataclass(frozen=True)
class Settings:
    key: str
    coordinator: str
    console: str


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """The download carries the key in a header, and urllib sends a request's headers on to
    wherever a redirect points. A redirect is therefore an error, never followed."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open(request: urllib.request.Request, timeout: float):
    return urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout)


def read_settings(env: Mapping[str, str]) -> tuple[Settings | None, str | None]:
    """The job's pool settings, or why it has none.

    `(None, None)` is the ordinary case of a job given no key. `(None, problem)` is a job
    given a key it cannot use, which is the repository's configuration being wrong. An empty
    value is an unset one: GitHub renders a secret or variable the job may not read as "".
    """
    key = env.get("TESTAMENT_KEY", "").strip()
    if not key:
        return None, None
    values = {}
    for name in ("TESTAMENT_COORDINATOR", "TESTAMENT_CONSOLE"):
        values[name] = env.get(name, "").strip()
        if not values[name]:
            return None, f"TESTAMENT_KEY is set and {name} is not: set the repository variable {name}"
    console = urllib.parse.urlsplit(values["TESTAMENT_CONSOLE"])
    if console.scheme != "https" or not console.netloc:
        return None, "TESTAMENT_CONSOLE must be an https address: the key is sent to it"
    return Settings(key, values["TESTAMENT_COORDINATOR"], values["TESTAMENT_CONSOLE"]), None


def suite_env(env: Mapping[str, str]) -> dict[str, str]:
    """The environment a process that is not the pool's client runs in: nothing of testament's.

    This keeps the settings out of what an installer or pytest is handed, so a suite run here
    sees what it saw before CI knew of a pool. It is not what keeps the key from a test: a
    child can read its parent's environment. The two stages being separate jobs is.
    """
    return {name: value for name, value in env.items() if not name.startswith("TESTAMENT_")}


def selected_out(manifest: Path) -> str | None:
    """The marker expression for the tests the pool does not run, or None when it runs all.

    The manifest's command selects with `-m <expression>`; what is left for the job is that
    expression negated, so the two runs are the whole suite by construction and the markers
    are named in one file. A command this cannot read is refused rather than read as "nothing
    selected out", which would stop those tests running anywhere without a word.
    """
    command = tomllib.loads(manifest.read_text()).get("command")
    if not isinstance(command, list) or "pytest" not in command:
        raise Refused(f"{manifest.name}: `command` does not run pytest, so what it selects out is unknown")
    # After `pytest`: `python -m pytest` carries a `-m` of its own before it.
    selection = command[command.index("pytest") + 1 :]
    if "-m" not in selection:
        return None
    at = selection.index("-m") + 1
    if at >= len(selection):
        raise Refused(f"{manifest.name}: `command` ends at `-m` with no expression")
    return f"not ({selection[at]})"


def fetch_cli(settings: Settings, dest: Path, opener: Callable = _open) -> Path:
    """Download the pool's CLI build into `dest`, checked against the pool's digest for it."""
    url = settings.console.rstrip("/") + CLI_WHEEL_PATH
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {settings.key}"})
    try:
        with opener(request, timeout=DOWNLOAD_SECONDS) as response:
            body = response.read()
            headers = response.headers
    except urllib.error.HTTPError as e:
        if e.code >= 500 or e.code in CONSOLE_OUTAGES:
            raise Unavailable(f"the pool's console answered {e.code} for its CLI build") from e
        hint = " (the key is unknown to the pool, or revoked)" if e.code in (401, 403) else ""
        raise Refused(f"the pool's console answered {e.code} for its CLI build{hint}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise Unavailable(f"the pool's console could not be reached: {e}") from e
    expected = (headers.get(WHEEL_SHA256) or "").strip().lower()
    if not expected:
        raise Refused("the pool's console named no checksum for its CLI build")
    got = hashlib.sha256(body).hexdigest()
    if got != expected:
        raise Refused(f"the pool's CLI build has sha256 {got}, not the {expected} the pool names")
    named = re.search(r'filename="?([^";]+)"?', headers.get("Content-Disposition") or "")
    name = named.group(1) if named else ""
    if not WHEEL_NAME.fullmatch(name):
        raise Refused(f"the pool's console named its CLI build {name!r}, which is not a testament wheel")
    wheel = dest / name
    wheel.write_bytes(body)
    return wheel


def install_cli(wheel: Path, venv: Path, env: Mapping[str, str], run: Callable = subprocess.run) -> Path:
    """Install the build into an environment of its own and return its `testament`.

    `--no-index`, because the job that holds the key installs the build the pool sent and
    nothing from a package index: a build that came to need one fails here, by name, and
    someone decides whether that job may fetch it.
    """
    steps = (
        [sys.executable, "-m", "venv", str(venv)],
        [str(venv / "bin" / "python"), "-m", "pip", "install", "--quiet", "--no-index", str(wheel)],
    )
    for argv in steps:
        done = run(argv, env=suite_env(env), check=False)  # noqa: S603 — list-form argv, no shell (project preference)
        if done.returncode != 0:
            raise Refused(f"installing the pool's CLI build failed: `{' '.join(argv[1:4])} …` exited {done.returncode}")
    return venv / "bin" / "testament"


def pool_run(
    testament: Path,
    settings: Settings,
    wait: float,
    env: Mapping[str, str],
    work: Path,
    run: Callable = subprocess.run,
) -> tuple[int, dict | None]:
    """One `testament run` of the manifest's default selection, given `wait` seconds: its exit
    code and envelope.

    `--no-fallback`: the client's own fallback would run the suite in this job, which holds
    the key and has none of the suite's dependencies; the fallback is the `tests` stage.
    `--advice never`: its advice is for someone at a desk, about caching and slow tests.
    """
    child = suite_env(env) | {"TESTAMENT_KEY": settings.key, "TESTAMENT_COORDINATOR": settings.coordinator}
    if env.get("TESTAMENT_BRANCH"):
        child["TESTAMENT_BRANCH"] = env["TESTAMENT_BRANCH"]
    argv = [str(testament), "run", "--json=summary", "--no-fallback", "--advice", "never"]
    envelope_path = work / "envelope.json"
    with envelope_path.open("wb") as stdout:
        try:
            done = run(argv, env=child, stdout=stdout, timeout=wait, check=False)  # noqa: S603 — list-form argv, no shell (project preference)
        except subprocess.TimeoutExpired as e:
            raise Unavailable(f"the pool did not finish the run in the {POOL_WAIT_SECONDS // 60} minutes it is given") from e
    try:
        envelope = json.loads(envelope_path.read_text())
    except (OSError, ValueError):
        envelope = None
    return done.returncode, envelope if isinstance(envelope, dict) else None


def run_pytest(args: list[str], env: Mapping[str, str], run: Callable = subprocess.run) -> int:
    """pytest on the job, configured by `pyproject.toml` and by nothing here."""
    argv = [sys.executable, "-m", "pytest", *args]
    return run(argv, env=suite_env(env), cwd=REPO_ROOT, check=False).returncode  # noqa: S603 — list-form argv, no shell (project preference)


def _escape(text: str, *, property_value: bool = False) -> str:
    """GitHub's workflow-command encoding: a message may not end its command or start one."""
    text = text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    if property_value:
        text = text.replace(":", "%3A").replace(",", "%2C")
    return text


class Report:
    """What the job says: annotations on the run's page, and its summary."""

    def __init__(self, stream: TextIO, summarize: Callable[[str], None]):
        self._stream = stream
        self._summarize = summarize

    def _annotate(self, level: str, message: str, title: str = "") -> None:
        head = f"::{level} title={_escape(title, property_value=True)}::" if title else f"::{level}::"
        print(head + _escape(message), file=self._stream, flush=True)

    def notice(self, message: str) -> None:
        self._annotate("notice", message)

    def warning(self, message: str) -> None:
        self._annotate("warning", message)

    def error(self, message: str, title: str = "") -> None:
        self._annotate("error", message, title)

    def summary(self, line: str) -> None:
        self._summarize(line)


def _why(code: int, envelope: dict | None) -> str:
    error = (envelope or {}).get("error")
    if isinstance(error, dict) and error.get("code"):
        return f"`{error['code']}`" + (f": {error['message']}" if error.get("message") else "")
    if envelope is None:
        return f"`testament run` exited {code} and printed no result"
    return f"`testament run` exited {code}"


def _name_missing(envelope: dict | None, report: Report) -> None:
    missing = ((envelope or {}).get("report") or {}).get("missing") or []
    if missing:
        report.summary(f"Never reported by the pool ({len(missing)}): " + ", ".join(f"`{m}`" for m in missing[:20]))


def _pool_verdict(
    testament: Path, settings: Settings, pool: Callable, report: Report, clock: Callable[[], float]
) -> tuple[int, dict]:
    """The pool's result for the suite, or the reason there is none.

    A retryable end (a lost batch, a pool restarting) is run once more, which is what
    `documentation/running-tests.md` tells a person to do; twice is an outage. Both attempts
    share one allowance, so a run lost late leaves the second only what remains of it.
    """
    deadline = clock() + POOL_WAIT_SECONDS
    code, envelope = 2, None
    for attempt in (1, 2):
        left = deadline - clock()
        if left <= 0:
            break
        code, envelope = pool(testament, settings, left)
        if code in RESULT_CODES and envelope is not None:
            return code, envelope
        _name_missing(envelope, report)
        error = (envelope or {}).get("error")
        if not (code == 2 and isinstance(error, dict) and error.get("retryable") is True):
            raise Refused(_why(code, envelope))
        if attempt == 1:
            report.notice(f"the pool run ended retryable ({_why(code, envelope)}); running it once more")
    raise Unavailable(_why(code, envelope))


def _describe(envelope: dict, report: Report) -> None:
    """The pool run in the summary: its counts and each failing test. No runner is named: the
    summary is as public as the repository, and a runner's name is somebody's machine."""
    result = envelope.get("report") or {}
    counts = result.get("counts")
    tally = ", ".join(f"{n} {outcome}" for outcome, n in counts.items()) if isinstance(counts, dict) and counts else ""
    report.summary(f"Ran on the pool: {tally or 'no counts reported'}")
    _name_missing(envelope, report)
    failing = [i for i in result.get("items") or [] if isinstance(i, dict) and i.get("outcome") in ("failed", "error")]
    for item in failing[:NAMED_FAILURES]:
        text = str(item.get("message") or "").strip().splitlines() or [""]
        # pytest's own assertion line ("E   …") says more than the file:line that follows it.
        said = [line[1:].strip() for line in text if line.startswith("E ")]
        last = (said[0] if said else text[-1])[:300]
        report.summary(f"- `{item.get('id')}` {item.get('outcome')}: {last}")
        report.error(last, title=str(item.get("id")))
    if len(failing) > NAMED_FAILURES:
        report.summary(f"…and {len(failing) - NAMED_FAILURES} more")


def pool_stage(
    env: Mapping[str, str],
    *,
    install: Callable[[Settings], Path],
    pool: Callable[[Path, Settings, float], tuple[int, dict | None]],
    report: Report,
    manifest: Path = MANIFEST,
    clock: Callable[[], float] = time.monotonic,
) -> tuple[int, str]:
    """The job that holds the key: its exit code, and where the suite ran.

    It never runs a test. When the answer is `ON_JOB` the `tests` stage runs the whole suite,
    whatever this job's own result.
    """
    report.summary("### pytest suite: the pool")
    settings, problem = read_settings(env)
    if settings is None and problem is None:
        why = "the workflow has no TESTAMENT_KEY (a pull request from a fork is given no secrets)"
        report.notice(f"the suite is not sent to the pool: {why}")
        report.summary(f"Not sent to the pool: {why}. The test job runs the whole suite.")
        return 0, ON_JOB
    try:
        if settings is None:
            raise Refused(problem or "the job's pool settings are unusable")
        # Before the pool is asked: a manifest whose selection cannot be read would leave the
        # `tests` stage unable to say which tests the pool did not run.
        selected_out(manifest)
        code, envelope = _pool_verdict(install(settings), settings, pool, report, clock)
    except Unavailable as e:
        report.warning(f"the pool could not be used, so the test job runs the whole suite: {e}")
        report.summary(f"Not run on the pool: {e}. The test job runs the whole suite.")
        return 0, ON_JOB
    except Refused as e:
        report.error(
            f"this workflow cannot use the pool: {e}. The test job still runs the whole suite, for the "
            "tree's verdict, and this job fails until the pool takes it again."
        )
        report.summary(f"Refused by the pool, or misconfigured: {e}. The test job runs the whole suite.")
        return 1, ON_JOB
    _describe(envelope, report)
    return code, ON_POOL


def tests_stage(
    ran_on: str, *, pytest: Callable[[list[str]], int], report: Report, manifest: Path = MANIFEST
) -> int:
    """The job that runs pytest: the whole suite, or what the pool left out. Its exit code."""
    report.summary("### pytest suite: this job")
    if ran_on != ON_POOL:
        report.summary("The pool did not run the suite, so the whole suite ran here.")
        return pytest([])
    try:
        rest = selected_out(manifest)
    except Refused as e:
        report.error(f"{e}. The whole suite runs here, and this job fails until the manifest can be read.")
        return pytest([]) or 1
    if rest is None:
        report.summary("The pool ran the whole suite; the manifest selects nothing out for this job.")
        return 0
    code = pytest(["-m", rest])
    if code == NOTHING_COLLECTED:
        report.summary(f"No test matches what the manifest selects out (`{rest}`); nothing ran here.")
        return 0
    report.summary(f"The pool ran the suite; the tests the manifest selects out (`{rest}`) ran here: exit {code}.")
    return code


def _append(path: str | None, line: str) -> None:
    """A line for one of the files GitHub reads back from a step, or stdout where there is none."""
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    else:
        print(line, flush=True)


def main(argv: list[str]) -> int:
    env = dict(os.environ)
    report = Report(sys.stdout, lambda line: _append(env.get("GITHUB_STEP_SUMMARY"), line))
    stage = argv[1] if len(argv) == 2 else ""
    if stage == "pool":
        work = Path(tempfile.mkdtemp(prefix="ci-suite-"))
        code, ran_on = pool_stage(
            env,
            install=lambda settings: install_cli(fetch_cli(settings, work), work / "venv", env),
            pool=lambda testament, settings, wait: pool_run(testament, settings, wait, env, work),
            report=report,
        )
        _append(env.get("GITHUB_OUTPUT"), f"suite={ran_on}")
        return code
    if stage == "tests":
        return tests_stage(env.get(RAN_ON, ""), pytest=lambda args: run_pytest(args, env), report=report)
    print("usage: ci-suite.py pool | tests", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
