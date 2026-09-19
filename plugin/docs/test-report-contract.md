# The Test Report Contract — a report from every run, and its scope beside it

Prawduct records a suite run as evidence: `.prawduct/.test-evidence.json` says how many tests
passed, against which tree, and the freshness gates read it to decide whether anything has to run
again. That record is only as honest as what feeds it.

Two properties make it honest, and a product's test setup is where they are implemented. They are
a **requirement** — prawduct states them and reads their output; it installs nothing and edits no
runner config, because prawduct's own ratified norms say it guides and never implements
(`docs/norms.md` for how norms bind; the norm itself lives in prawduct's repo, not in yours).

1. **The machine-readable report is a side effect of every run.** The report path lives in the
   runner's own default-arguments file, not in the command someone types. Nobody can run the suite
   in a way that produces no report, so no run in a session is unrecoverable: whatever happened, it
   can be ingested with `prawduct-hook test-evidence record --from-junit <report>` instead of being
   run again.
2. **The invocation's scope is recorded beside the report.** The runner's pre/post-run hook writes
   a small JSON record saying whether that invocation ran the whole suite or a narrowed part of it.

The second is what makes the first safe. Once a report is always sitting at a known path, a report
from `pytest -k billing` looks exactly like a report from the whole suite, and ingesting it would
record a subset as the suite's evidence — a false green, not a lost ten minutes. The scope record
is how the recorder tells them apart.

## The conventional paths

| What | Path |
|---|---|
| The report | `.prawduct/.test-report.xml` (JUnit XML — the format `--from-junit` already ingests) |
| Its scope record | `.prawduct/.test-report.xml.scope.json` — the report's path plus `.scope.json` |

Both are per-clone run output, never committed; prawduct's managed `.gitignore` section carries
them, so an onboarded repo gets the ignore rules without doing anything. Both are also **deleted at
the session boundary** (`/clear`), with the rest of the session files: a report outliving its
session invites an ingest that stamps the new session's tree onto the old session's run, and the
scope record cannot catch that — it says what the invocation selected, never when it ran. A run is
recoverable inside the session that made it.

The convention is what lets prose and refusals name an exact command. A repo whose runner cannot
write there is not excluded — it passes its own path to `--from-junit`, and the scope record is
looked for beside whatever path that is.

**The path is relative to the project root, and that is the producer's job to guarantee.** Runners
resolve a relative report path against the *invocation directory*, not the project root — pytest
uses `os.path.abspath`, and most runners do the same — so `cd tests && <runner>` writes
`tests/.prawduct/.test-report.xml`. That copy is outside the managed `.gitignore` entries (a
pattern containing a slash is anchored to the repo root) and outside the session boundary's sweep:
untracked run output, one `git add -A` from being committed. The producer closes this by anchoring
a relative path against the project root before the runner resolves it — the worked example below
does it in three lines.

## The scope record

```json
{
  "v": 1,
  "scope": "partial",
  "report": "/abs/path/to/.prawduct/.test-report.xml",
  "why": "-k 'billing' narrowed the selection",
  "at": "2026-09-18T05:12:44Z"
}
```

| Field | Required | Who reads it |
|---|---|---|
| `v` | yes | The reader, to refuse a record written by a schema it does not know rather than guess at it. `1` is the only version. |
| `scope` | yes | The reader's verdict: `"full"` (this invocation ran the runner's whole default selection) or `"partial"` (anything else). |
| `why` | when `partial` | Printed in the refusal, so the operator knows what narrowed the run rather than being told only that something did. |
| `report` | yes | The absolute path of the report this record describes, as the producer resolved it. The reader compares it with the report it was handed, so a record cannot vouch for a file it was not written beside. |
| `at` | no | Printed in the refusal — which run wrote this. |

Unknown keys are ignored, so the record can grow without breaking a reader shipped at `v: 1`.

Write it atomically (temp file in the same directory, then rename) and world-readable: a reader
that catches the file half-written sees malformed JSON, and malformed refuses — and a report
written by one user (a container, a CI runner) has to stay readable by whoever records it.

## What prawduct does with it

`test-evidence record --from-junit <report>` reads `<report>.scope.json` before parsing the
report, and applies these rules in order. Every refusal exits 2 and writes nothing — the previous
evidence record survives untouched, which is the point of refusing rather than recording something
degraded on top of it.

| Condition | Result |
|---|---|
| No record beside the report | **Proceed**, exactly as before the contract existed. A repo that has not wired a producer is unaffected. |
| Unreadable, not JSON, or not a JSON object | **Refuse** — ambiguous state on a path that feeds a gate verdict fails closed. |
| `v` missing, or a version this reader does not know | **Refuse**, naming the version it found. |
| `scope` missing or neither `full` nor `partial` | **Refuse**. |
| `report` naming a different file than the one handed in | **Refuse** — the record is about some other run. |
| `report` missing | **Refuse** — the record is about nothing; it was never written correctly. |
| `scope: "partial"` | **Refuse**, quoting `why` and `at`. |
| `scope: "full"` | **Proceed.** |

A refusal names the two honest ways forward — run the declared command through the recorder
(`prawduct-hook test-evidence record`), or ingest a report from a run that was not narrowed.
Deleting or editing the scope record is not one of them: it buys a silent false green, which is
the thing this contract exists to prevent.

The record is consulted on **ingest, and on the undeclared-run fallback**. Where the repo declares
a `test_command` / `test_commands`, that declaration *is* the definition of the suite on the run
path and is not second-guessed by this — a repo whose canonical command is deliberately narrow is
taken at its word. Where it declares none, the recorder runs its own pytest fallback and *does*
consult the record, because there is no declaration standing behind that invocation: the fallback
is the reader's own guess at the suite, so the scope it actually selected is the only evidence of
what it covered. Pinned by `TestTheUndeclaredRunPath`.

## Producing one

**Advice, not contract.** What binds is the two properties above and the record this reads;
*how* you produce it is yours (prawduct's own norms put goals and verification in the binding half
and prescribed method in the advisory one). Every ecosystem has the two surfaces this needs: a file
holding the runner's default arguments, and a pre/post-run hook. The pairing below is a starting
point.

| Ecosystem | Default-arguments file | Pre/post-run hook | What narrows a run there |
|---|---|---|---|
| pytest | `addopts` in `pyproject.toml` / `pytest.ini` | `conftest.py`'s `pytest_configure` + `pytest_sessionfinish` | `-k`, `-m`, node ids, `--deselect`, `--lf`, `-x` |
| .NET (`dotnet test`) | a `.runsettings` naming a JUnit logger | an assembly-level init/cleanup fixture | `--filter` |
| Go | the `go test` target in the task runner, piped through a JUnit converter | `TestMain` | `-run`, a package subset |
| Jest / Vitest | `reporters` in the config file | `globalSetup` / `globalTeardown` | `-t`, a path pattern, `--onlyChanged` |
| CTest | the test target's `--output-junit` in the build config | a fixture test that runs first and last | `-R`, `-L` |

A worked pytest producer, which is what this repo itself runs:

```python
# conftest.py
import json, os, tempfile
from datetime import datetime, timezone
from pathlib import Path

def _write(config, scope, why):
    xml = getattr(config.option, "xmlpath", None)
    if not xml or hasattr(config, "workerinput"):
        return  # no report to describe, or an xdist worker rather than the controller
    report = Path(xml).resolve()
    record = {"v": 1, "scope": scope, "report": str(report),
              "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if why:
        record["why"] = why
    target = report.with_name(report.name + ".scope.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent))
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(record, indent=2) + "\n")
    os.chmod(tmp, 0o644)   # mkstemp is 0600; the recorder may run as another user
    os.replace(tmp, target)

def pytest_configure(config):
    # Written FIRST, so a run that is killed or crashes leaves a record saying so
    # rather than the previous run's verdict sitting beside a truncated report.
    # Never raise out of a hook: a producer that cannot write its record must not
    # take the suite down with it (see "What a producer owes" above).
    try:
        _write(config, "partial", "the run did not finish")
    except OSError:
        pass

def pytest_sessionfinish(session, exitstatus):
    _write(session.config, *classify(session.config, exitstatus))

def classify(config, exitstatus):
    """Was anything narrowed? A question about the INVOCATION, never the result."""
    o = config.option
    if exitstatus in (2, 3, 4, 5):      # interrupted, internal error, bad usage, nothing collected
        return "partial", f"pytest exited {exitstatus}, so the report may be truncated"
    if getattr(o, "keyword", ""):
        return "partial", f"-k {o.keyword!r} narrowed the selection"
    if getattr(o, "markexpr", ""):
        return "partial", f"-m {o.markexpr!r} narrowed the selection"
    if getattr(o, "deselect", None) or getattr(o, "ignore", None):
        return "partial", "--deselect/--ignore removed tests from the selection"
    if getattr(o, "lf", False) or getattr(o, "stepwise", False):
        return "partial", "the run was scoped to a previous run's failures"
    if getattr(o, "collectonly", False):
        return "partial", "--collect-only ran no tests"
    if getattr(o, "maxfail", 0):
        return "partial", "--maxfail/-x can stop the run before the end"
    if not _selection_is_the_default(config):
        return "partial", "the invocation named specific paths rather than the whole suite"
    return "full", None

def _selection_is_the_default(config):
    """True when this invocation selected what a bare run selects.

    Compare RESOLVED paths, never the strings. pytest sets `config.args` to the
    RELATIVE results of its own glob expansion, while `testpaths` is declared
    relative to rootdir — so a bare `pytest` gives `["tests"]` on one side and
    `["/abs/root/tests"]` on the other, and a string comparison calls every
    whole-suite run `partial`. Set-compare, because order is not selection.
    """
    args = list(config.args)
    if any("::" in arg for arg in args):
        return False          # a node id is a narrowing by definition
    invocation_dir = Path(config.invocation_params.dir)
    chosen = {(invocation_dir / arg).resolve() for arg in args}
    testpaths = [str(x) for x in config.getini("testpaths")]
    if testpaths:
        return chosen == {(Path(config.rootpath) / p).resolve() for p in testpaths}
    # No testpaths configured: a bare run collects from where it was invoked.
    return chosen in ({invocation_dir.resolve()}, {Path(config.rootpath).resolve()})
```

Exit status `1` — a red suite — is `full`: that run is complete, and recording a failing suite is
the point of recording on red. `--ff` is absent for the same kind of reason: it reorders the
selection without reducing it.

To anchor a relative path (the paragraph above), add this as the first two lines of
`pytest_configure`, which runs before the report writer is built:

```python
    xmlpath = getattr(config.option, "xmlpath", None)
    if xmlpath and not os.path.isabs(xmlpath):
        config.option.xmlpath = str(Path(config.rootpath) / xmlpath)
```

## What a producer owes beyond writing the record

The record is only worth reading while it is still being written, and **absence is permissive** —
so a producer that quietly stops (a runner upgrade renaming the option, a config edit dropping the
report path, a refactor of the hook) does not fail loudly. It degrades straight into the trusting
path, and the next ingest of a narrowed run records a subset as suite evidence with nothing
anywhere having noticed. Two obligations follow, and they are cheap:

- **Pin the configuration entry itself.** One assertion that the runner's default-arguments file
  still carries the report path. Nothing else in a suite fails when that line is deleted — the
  tests stay green, and the only symptom arrives months later as a run somebody has to repeat.
- **Drive the real runner once.** A test that runs the runner against a scratch project and
  asserts the record reads `full` for a plain run and `partial` for a narrowed one. Unit tests over
  a fake config assert what you believe the runner passes; this asserts what it does, and it is the
  only check that the hook is wired at all.

**A record that cannot be written is not an error to raise.** The producer describes the run; it is
not part of it. A failed write (read-only directory, full disk) must leave the run alone and say so
on stderr — absence is the permissive case, so the cost is the guard, never a false green, and an
advisory that fails *silently* manufactures the confidence it exists to check.

## What this does not do

- **Absence stays permissive.** A missing record means "this repo has no producer", not "this
  report is fine" — but the two are indistinguishable to the reader, so absence cannot refuse
  without breaking every repo that has not wired one. It follows that deleting the record gets
  past the guard. The contract raises the cost of laundering a subset from *typing nothing* to
  *deleting a file you were just told not to delete*; it does not make it impossible.
- **A run that *could* stop early is `partial` even if it did not.** `-x` on a green whole-suite
  run produces a complete report and is still recorded as narrowed, because the producer classifies
  the invocation rather than measuring the result. Drop the flag to record the run.
- **It says nothing about *when* the run happened.** Ingesting any old report stamps today's tree
  onto that run, which is the standing posture of `--from-junit` and not something this changes; the
  boundary deletion above is what keeps it from becoming routine. `at` is in the record for an
  operator to check, and the reader does not compare it.
- **A report carried away from where it was produced, WITH its record, is refused.** The record
  names the report it describes by absolute path, so a report and record downloaded from CI and
  ingested on a developer's machine do not match and the ingest refuses. That is deliberate — a
  present-but-mismatched record is not the un-wired population that absence is, so it is surfaced
  rather than ignored — but it is a real cost: ingest the report where it was produced, or download
  the report alone, which lands in the permissive absent case.
- **It says nothing about the report's contents.** A hand-edited report is out of scope; this
  answers what the invocation selected, not whether the XML is truthful.
