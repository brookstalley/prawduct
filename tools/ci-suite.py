#!/usr/bin/env python3
"""Run this repo's pytest suite for a CI job: on testament's pool when the job can use it, on
the job itself when it cannot.

    python tools/ci-suite.py

It reads three settings from the environment and takes no arguments:

    TESTAMENT_KEY          a client key for the pool (an Actions secret)
    TESTAMENT_COORDINATOR  the pool's wire address, which `testament run` submits to
    TESTAMENT_CONSOLE      the pool's console (https), which serves the pool's CLI build

Where the suite runs, and what the job's result is:

    no key                         the whole suite on the job; the suite's result. A pull
                                   request from a fork is this case: it is given no secrets.
    a key, and the pool answers    the pool runs what `.testament.toml` selects and the job
                                   runs what it selects out; the job fails if either does.
    a key, and the pool cannot     the whole suite on the job, with a warning; the suite's
    be reached                     result. An outage says nothing about the tree.
    a key, and the pool refuses    the whole suite on the job, and the job fails whatever the
    it, or a setting is missing    suite says: CI has stopped using the pool, and a red job is
                                   the only thing that says so to the person who can fix it.

Anything not known to be an outage is a refusal: the two are told apart by what the pool
reports (`error.retryable`), and an end this file does not recognise fails the job rather than
passing as a fallback nobody reads.

The CLI is the pool's own published build, fetched from its console with the job's key.
Testament's source is private, so a public repository's job cannot install it from source, and
a build taken from the pool is never the wrong version for that pool.

Standard library only: this runs before, and apart from, the suite's own environment.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
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

# How long the job waits on the pool before running the suite itself. The pool's own run of
# this suite takes about a minute; the rest is room to queue behind other people's work. It is
# bounded so that a busy pool costs the job a fallback rather than its whole time limit, which
# would end it with no verdict at all.
POOL_WAIT_SECONDS = 600

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

    The key must never reach a test process or an installer. The other settings go too, so
    the suite on the job sees what it saw before the job knew of a pool.
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
        if e.code >= 500:
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

    Its own environment, because testament installed beside the suite adds its pytest plugin
    to the suite. `--no-index`, because the job installs the build the pool sent and nothing
    else: a build that came to need a package from an index fails here, by name, and someone
    decides whether CI may fetch it.
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
    testament: Path, settings: Settings, env: Mapping[str, str], work: Path, run: Callable = subprocess.run
) -> tuple[int, dict | None]:
    """One `testament run` of the manifest's default selection: its exit code and envelope.

    `--no-fallback`: the client's own fallback would run the manifest's command on the job,
    which needs the pool image's tooling and not this job's; the fallback is this file's.
    `--advice never`: its advice is for someone at a desk, about caching and slow tests.
    """
    child = suite_env(env) | {"TESTAMENT_KEY": settings.key, "TESTAMENT_COORDINATOR": settings.coordinator}
    if env.get("TESTAMENT_BRANCH"):
        child["TESTAMENT_BRANCH"] = env["TESTAMENT_BRANCH"]
    argv = [str(testament), "run", "--json=summary", "--no-fallback", "--advice", "never"]
    envelope_path = work / "envelope.json"
    with envelope_path.open("wb") as stdout:
        try:
            done = run(argv, env=child, stdout=stdout, timeout=POOL_WAIT_SECONDS, check=False)  # noqa: S603 — list-form argv, no shell (project preference)
        except subprocess.TimeoutExpired as e:
            raise Unavailable(f"the pool did not finish the run in {POOL_WAIT_SECONDS // 60} minutes") from e
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


def _pool_verdict(testament: Path, settings: Settings, pool: Callable, report: Report) -> tuple[int, dict]:
    """The pool's result for the suite, or the reason there is none.

    A retryable end (a lost batch, a pool restarting) is run once more, which is what
    `documentation/running-tests.md` tells a person to do; twice is an outage.
    """
    code, envelope = 2, None
    for attempt in (1, 2):
        code, envelope = pool(testament, settings)
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


def run(
    env: Mapping[str, str],
    *,
    install: Callable[[Settings], Path],
    pool: Callable[[Path, Settings], tuple[int, dict | None]],
    pytest: Callable[[list[str]], int],
    report: Report,
    manifest: Path = MANIFEST,
) -> int:
    """Decide where the suite runs, run it, and return the job's exit code."""
    report.summary("### pytest suite")

    def on_job(why: str) -> int:
        report.summary(f"Ran on this job, not the pool: {why}")
        return pytest([])

    settings, problem = read_settings(env)
    if settings is None and problem is None:
        why = "the job has no TESTAMENT_KEY (a pull request from a fork is given no secrets)"
        report.notice(f"the suite runs on this job: {why}")
        return on_job(why)
    try:
        if settings is None:
            raise Refused(problem or "the job's pool settings are unusable")
        rest = selected_out(manifest)
        code, envelope = _pool_verdict(install(settings), settings, pool, report)
    except Unavailable as e:
        report.warning(f"the pool could not be used, so the suite runs on this job: {e}")
        return on_job(str(e))
    except Refused as e:
        report.error(
            f"this job cannot use the pool: {e}. The suite still runs on this job for the tree's verdict, "
            "and the job fails either way until the pool takes it again."
        )
        return on_job(str(e)) or 1
    _describe(envelope, report)
    rest_code = 0
    if rest is not None:
        rest_code = pytest(["-m", rest])
        if rest_code == NOTHING_COLLECTED:
            rest_code = 0
            report.summary(f"No test matches what the manifest selects out (`{rest}`); nothing ran on this job.")
        else:
            report.summary(f"The tests the manifest selects out (`{rest}`) ran on this job: exit {rest_code}.")
    return code or rest_code


def main() -> int:
    env = dict(os.environ)
    work = Path(tempfile.mkdtemp(prefix="ci-suite-"))
    summary_path = env.get("GITHUB_STEP_SUMMARY")

    def summarize(line: str) -> None:
        if summary_path:
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        else:
            print(line, flush=True)

    return run(
        env,
        install=lambda settings: install_cli(fetch_cli(settings, work), work / "venv", env),
        pool=lambda testament, settings: pool_run(testament, settings, env, work),
        pytest=lambda args: run_pytest(args, env),
        report=Report(sys.stdout, summarize),
    )


if __name__ == "__main__":
    sys.exit(main())
