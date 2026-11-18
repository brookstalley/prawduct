"""Whether a repo whose tests run on testament records its evidence from a testament run.

testament runs a repo's suite on a pool of runners, and a repo that uses it says so
with ``.testament.toml`` at its root, the manifest testament itself reads to run the
suite. Its agent instructions then say to run tests with ``testament run``. The
evidence recorder runs, or ingests, only the declared ``test_command`` /
``test_commands``. When none of those runs testament, the two disagree about what
the suite is: an agent verifies on the pool, cannot hand that run to the recorder
(the JSON envelope is not JUnit, and ``--from-counts`` is refused beside a declared
command), and the recorder runs the whole suite again locally. Every evidence
record costs two full runs, and the second is the one exposed to the local
machine's environment.

Two surfaces answer it: the session-start advisory below, which names the fix to
the owner, and the recorder's ``--from-counts`` refusal (:func:`from_counts_refusal`),
whose text is chosen from the declaration the recorder resolved.

**Which declaration.** The recorder resolves ``test_command`` / ``test_commands``
with its own import-light readers. The recorder hands its resolved declaration to
:func:`from_counts_refusal`, so the refusal reads nothing. The probe runs at
session start, where no recorder runs, and resolves the declaration through
:func:`resolve_declared`, which applies the recorder's rules: a ``test_commands``
block of plain strings wins; a ``test_commands`` the recorder refuses (unparseable,
empty, or beside a ``test_command``) is a declaration nobody can read, and the
probe says it could not look rather than guess. ``tests/test_testament_evidence_probes.py``
drives the real recorder on every such shape to pin the two together.

**A declared command runs testament** when its words contain ``testament`` (the
program, by basename, so a full path or a ``uv run`` prefix counts) with a later
``run``, including inside a quoted ``sh -c`` string, or when it names a script
inside the repo with such a line. It **records** from testament when it also
carries the ``{junit_xml}`` placeholder the recorder fills. A wrapper prawduct
cannot read (a make target, a script outside the repo, a script another script
calls) reads as not running testament, so the advisory says "as far as prawduct
can read" and warns that replacing a wrapper drops what else it runs. It is
dismissable, and its evidence is the declared commands, so a dismissal holds until
they change. One
entry among several that runs testament is enough: a repo may run part of its
suite locally on purpose (prawduct's own does, for tests that need git history).

Registered at the composition root (``lib/probe_families.register_all``).
Read-only: it reads two files, and any wrapper script a declared command names, and runs nothing.
"""

from __future__ import annotations

import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe
from .core import YAML_ABSENT, YAML_DECLARED, read_block_sequence, read_str_yaml_key

FEATURE = "testament-evidence"
PROBE_TYPE = "declared-command-skips-testament"
PROBE_VERSION = 1

#: testament's manifest, at the root of the repo whose suite it runs.
MANIFEST = ".testament.toml"

#: The declared command that records evidence from a testament run.
WIRED_COMMAND = "testament run --junit-xml {junit_xml}"

PLACEHOLDER = "{junit_xml}"

_STATE_REL = (".prawduct", "project-state.yaml")


@dataclass(frozen=True)
class Declared:
    """The suite commands the recorder would run, and the key that declares them.

    ``key`` is ``None`` with no commands when nothing is declared, and the
    recorder's pytest fallback runs.
    """

    key: "str | None"
    commands: "tuple[str, ...]"


def resolve_declared(state_path: Path) -> "Declared | None":
    """The declaration as the recorder resolves it, or ``None`` where it refuses one."""
    try:
        text = Path(state_path).read_text(encoding="utf-8")
    except OSError:
        text = ""
    status, items = read_block_sequence(text, "test_commands")
    single = read_str_yaml_key(Path(state_path), "test_command")
    if status == YAML_ABSENT:
        return Declared("test_command", (single,)) if single else Declared(None, ())
    if status != YAML_DECLARED or not items or single:
        return None
    return Declared("test_commands", tuple(items))


def _words(command: str) -> "list[str]":
    try:
        words = shlex.split(command)
    except ValueError:
        return []
    out: list[str] = []
    for word in words:
        # A quoted shell string (`sh -c '...'`) is one word holding a command.
        out.extend(_words(word) if any(c.isspace() for c in word) else [word])
    return out


#: The largest script :func:`runs_testament` reads. A test wrapper is a few
#: dozen lines; anything far larger is not one, and is not worth reading at
#: session start.
_SCRIPT_READ_LIMIT = 256 * 1024


def _words_run_testament(words: "list[str]") -> bool:
    return any(
        Path(word).name == "testament" and "run" in words[i + 1 :]
        for i, word in enumerate(words)
    )


def _scripts(root: Path, words: "list[str]") -> "list[Path]":
    """The files inside ``root`` that ``words`` name: the wrapper scripts a
    declared command may run. Nothing outside the repo is read."""
    base = Path(root).resolve()
    found: list[Path] = []
    for word in words:
        if word.startswith("-") or "{" in word:
            continue
        candidate = (base / word).resolve()
        if candidate == base or base not in candidate.parents:
            continue
        try:
            if candidate.is_file() and candidate.stat().st_size <= _SCRIPT_READ_LIMIT:
                found.append(candidate)
        except OSError:
            continue
    return found


def runs_testament(command: str, root: "Path | None" = None) -> bool:
    """Whether ``command`` runs ``testament run``: in its own words, or, given
    the repo ``root``, on a line of a script inside the repo that it names.

    One level deep: a script that calls another script is not followed. A
    wrapper prawduct cannot read (a make target, a script outside the repo)
    still reads as not running testament, which is why the advisory hedges.
    """
    words = _words(command)
    if _words_run_testament(words):
        return True
    if root is None:
        return False
    for script in _scripts(root, words):
        try:
            text = script.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and _words_run_testament(_words(stripped)):
                return True
    return False


def records_testament(command: str, root: "Path | None" = None) -> bool:
    """Whether ``command`` runs testament and writes the report the recorder
    reads. A wrapper script is trusted to pass the ``{junit_xml}`` argument it
    is given on to testament."""
    return runs_testament(command, root) and PLACEHOLDER in command


def uses_testament(root: Path) -> bool:
    """Whether testament's manifest is at ``root``."""
    return (Path(root) / MANIFEST).is_file()


def _fix(key: "str | None") -> str:
    """The declaration that makes a bare record run on testament, in the key's own form."""
    if key == "test_commands":
        return (
            f"replace the `test_commands` entry that runs the same suite as testament "
            f"with `{WIRED_COMMAND}` (keep the other entries)"
        )
    return f"declare `test_command: {WIRED_COMMAND}`"


def from_counts_refusal(root: Path, declared: Declared) -> str:
    """The recorder's refusal of ``--from-counts`` beside ``declared``.

    The route that leads depends on the declaration: how many commands it holds,
    whether one records from testament, and which key declares it. Where several
    commands are declared, evidence takes a report from each, so no text here
    offers one report as the whole suite.
    """
    commands = declared.commands
    several = len(commands) > 1
    head = (
        "error: --from-counts cannot be combined with a declared "
        "test_command/test_commands: a declared command emits JUnit, so the "
        "evidence comes from its report, not from typed counts.\n"
    )
    per_report = (
        f"one `--from-junit <report>` for each of the {len(commands)} declared commands, "
        "in one record" if several else "`--from-junit <report>`"
    )
    generic = (
        "If you already have the report"
        + ("s" if several else "")
        + f" of the whole suite on this tree, ingest with {per_report}. If you have not "
        "run the suite yet, a bare `test-evidence record` runs the declared "
        + ("commands" if several else "command")
        + " and records in one step."
    )
    if not uses_testament(root):
        return head + generic
    lead = f"This repo's tests run on testament ({MANIFEST}). "
    if any(records_testament(c, root) for c in commands):
        return head + lead + (
            "A bare `test-evidence record` runs "
            + (
                f"all {len(commands)} declared commands, the testament one on its runners, "
                if several
                else "the declared command on testament "
            )
            + "and records the result: that is the route after a `testament run`, which "
            "left no report unless asked for one. To ingest instead, ingest "
            + (
                f"{per_report}; a testament report alone covers only its own entry."
                if several
                else "a `testament run --junit-xml <report>` with `--from-junit <report>`."
            )
        )
    if any(runs_testament(c, root) for c in commands):
        return head + lead + (
            f"The declared testament command has no `{PLACEHOLDER}` placeholder, so the "
            f"recorder cannot read its report: add `--junit-xml {PLACEHOLDER}` to it."
        )
    return head + lead + (
        "No declared command runs testament, so a bare `test-evidence record` runs the "
        "declared suite again on this machine. Where testament runs the same suite as "
        "the declared command, `testament run --junit-xml <report>` ingested with "
        + (
            "`--from-junit <report>` stands in for that command; the other declared "
            "commands still owe their own reports in the same record. "
            if several
            else "`--from-junit <report>` records it without the local run. "
        )
        + f"To make a bare record run on testament, {_fix(declared.key)} in "
        ".prawduct/project-state.yaml."
    )


def _note(why: str) -> None:
    print(
        f"NOTE: testament evidence probe skipped: {why} — whether evidence runs the "
        "suite a second time goes unreported this session",
        file=sys.stderr,
    )


def probe_declared_command_skips_testament(state: ProjectState, codebase: Codebase):
    """One advisory when testament is in use and no declared command runs it."""
    root = Path(codebase.root)
    if not uses_testament(root):
        return []
    declared = resolve_declared(root.joinpath(*_STATE_REL))
    if declared is None:
        _note("test_command/test_commands is declared in a shape the recorder refuses")
        return None
    if any(runs_testament(c, root) for c in declared.commands):
        # Wired, or wired without the placeholder, which the recorder's own
        # refusal names on the next record.
        return []
    named = (
        "; ".join(f"`{c}`" for c in declared.commands)
        if declared.commands
        else "none, so the recorder's local pytest fallback runs"
    )
    return [
        AdvisoryCandidate(
            type=PROBE_TYPE,
            evidence=tuple(sorted(f"declared: {c}" for c in declared.commands))
            or ("declared: none",),
            trigger_summary=(
                f"This repo's tests run on testament ({MANIFEST}), but as far as prawduct "
                f"can read, no suite command it records evidence with runs it: {named}. "
                "Unless one of them reaches testament where prawduct cannot see (a make "
                "target, a script outside the repo or called by another script), each "
                "evidence record runs the suite a second time, locally, after the testament "
                f"run that verified it. To record from testament instead, {_fix(declared.key)} "
                "in .prawduct/project-state.yaml; where no runner answers, testament runs "
                "the same suite on this machine."
            ),
            owner_action=(
                "Approve pointing the declared suite command at testament, so test "
                "evidence comes from the testament run rather than a second local run of "
                "the suite. If the declared command is a wrapper, check what else it runs "
                "first (a lint, a build): replacing it drops those from test evidence. "
                "Dismiss this if the local command is deliberate."
            ),
            # Owner-only: the fix is an edit to a committed file, which no single
            # allowlisted command makes.
            recommended_action="",
        )
    ]


def register() -> None:
    """Register the probe. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, PROBE_TYPE, PROBE_VERSION, probe_declared_command_skips_testament)
