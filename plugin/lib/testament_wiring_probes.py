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

This module is the one answer to "does this repo's declared suite run testament?".
Two surfaces ask it: the session-start advisory below, which names the one-line
fix to the owner, and the recorder's ``--from-counts`` refusal
(:func:`from_counts_refusal`), which leads with the route that works for a caller
who just ran ``testament run``.

**A declared command runs testament** when its words contain ``testament`` (the
program, by basename, so a full path or a ``uv run`` prefix counts) followed
directly by ``run``. A script wrapping testament reads as not running it; the
advisory is dismissable, and its evidence is the declared commands, so a dismissal
holds until they change. One ``test_commands`` entry that runs testament is enough:
a repo may run part of its suite locally on purpose (prawduct's own does, for tests
that need git history).

**Could not look** (``None``) when ``test_commands`` is declared in a shape the
recorder refuses: that repo's recorder already says so loudly, and guessing here
would resolve or raise an advisory on a declaration nobody can read.

Registered at the composition root (``lib/probe_families.register_all``).
Read-only: it reads two files and runs nothing.
"""

from __future__ import annotations

import shlex
from pathlib import Path

from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe
from .core import YAML_DECLARED, YAML_UNPARSEABLE, read_block_sequence, read_str_yaml_key

FEATURE = "testament-evidence"
PROBE_TYPE = "declared-command-skips-testament"
PROBE_VERSION = 1

#: testament's manifest, at the root of the repo whose suite it runs.
MANIFEST = ".testament.toml"

#: The declaration that records evidence from a testament run.
WIRED_COMMAND = "testament run --junit-xml {junit_xml}"

_STATE_REL = (".prawduct", "project-state.yaml")


def runs_testament(command: str) -> bool:
    """Whether ``command``'s words run ``testament run``."""
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    return any(
        Path(word).name == "testament" and nxt == "run"
        for word, nxt in zip(words, words[1:])
    )


def uses_testament(root: Path) -> bool:
    """Whether testament's manifest is at ``root``."""
    return (Path(root) / MANIFEST).is_file()


def declared_commands(root: Path) -> "list[str] | None":
    """The declared suite commands, ``[]`` for none, ``None`` when unreadable.

    ``test_commands`` wins when declared, as in the recorder; declaring both is
    refused there and reads here as the list.
    """
    state = Path(root).joinpath(*_STATE_REL)
    try:
        text = state.read_text(encoding="utf-8")
    except OSError:
        text = ""
    status, items = read_block_sequence(text, "test_commands")
    if status == YAML_UNPARSEABLE:
        return None
    if status == YAML_DECLARED:
        return list(items)
    single = read_str_yaml_key(state, "test_command")
    return [single] if single else []


def unwired_commands(root: Path) -> "list[str] | None":
    """The declared commands when testament is in use and none of them runs it.

    ``None`` when there is nothing to report: testament is not in use, a declared
    command runs it, or the declaration cannot be read. ``[]`` means testament is in
    use and nothing is declared, so the recorder's local pytest fallback runs.
    """
    if not uses_testament(root):
        return None
    commands = declared_commands(root)
    if commands is None or any(runs_testament(c) for c in commands):
        return None
    return commands


def from_counts_refusal(root: Path) -> str:
    """The recorder's refusal of ``--from-counts`` beside a declared command.

    One function picks which route leads, because the caller's likely state
    differs: in a testament repo they have most likely just run ``testament run``,
    which left no JUnit report unless asked for one.
    """
    head = (
        "error: --from-counts cannot be combined with a declared "
        "test_command/test_commands: a declared command emits JUnit, so the "
        "evidence comes from a report, not from typed counts.\n"
    )
    generic = (
        "If you already have a JUnit report of the whole suite on this tree, "
        "ingest it with `test-evidence record --from-junit <report>` (repeat it "
        "once per report). If you have not run the suite yet, a bare "
        "`test-evidence record` runs the declared command(s) and records in one step."
    )
    if not uses_testament(root):
        return head + generic
    route = (
        f"This repo's tests run on testament ({MANIFEST}). If you ran `testament run`, "
        "run it again as `testament run --junit-xml <report>` (it reuses the "
        "results it can from its cache) and ingest that with "
        "`test-evidence record --from-junit <report>`.\n"
    )
    commands = declared_commands(root)
    if commands is not None and any(runs_testament(c) for c in commands):
        return head + route + (
            "The declared command already runs testament, so a bare "
            "`test-evidence record` runs the suite on testament and records it."
        )
    return head + route + (
        f"The declared command does not run testament, so a bare `test-evidence record` "
        f"runs the whole suite again on this machine. Declaring "
        f"`test_command: {WIRED_COMMAND}` in .prawduct/project-state.yaml makes a bare "
        "record run on testament.\n" + generic
    )


def probe_declared_command_skips_testament(state: ProjectState, codebase: Codebase):
    """One advisory when testament is in use and no declared command runs it."""
    root = Path(codebase.root)
    if not uses_testament(root):
        return []
    commands = declared_commands(root)
    if commands is None:
        return None
    unwired = unwired_commands(root)
    if unwired is None:
        return []
    named = "; ".join(f"`{c}`" for c in unwired) if unwired else "none (the local pytest fallback)"
    return [
        AdvisoryCandidate(
            type=PROBE_TYPE,
            evidence=tuple(sorted(f"declared: {c}" for c in unwired)) or ("declared: none",),
            trigger_summary=(
                f"This repo's tests run on testament ({MANIFEST}), but the suite command "
                f"prawduct records evidence with does not run it: {named}. Each evidence "
                "record therefore runs the whole suite a second time, locally, after the "
                "testament run that verified it. Declaring "
                f"`test_command: {WIRED_COMMAND}` in .prawduct/project-state.yaml records "
                "from testament instead; where no runner answers, testament runs the same "
                "suite on this machine."
            ),
            owner_action=(
                "Approve pointing the declared suite command at testament, so test "
                "evidence comes from the testament run rather than a second local run of "
                "the whole suite. Dismiss this if the local command is deliberate."
            ),
            # Owner-only: the fix is an edit to a committed file, which no single
            # allowlisted command makes.
            recommended_action="",
        )
    ]


def register() -> None:
    """Register the probe. Idempotent (register_probe overwrites)."""
    register_probe(FEATURE, PROBE_TYPE, PROBE_VERSION, probe_declared_command_skips_testament)
