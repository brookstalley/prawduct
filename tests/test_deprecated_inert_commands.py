"""The **announcing** inert tier: deprecated, callable, and loud on stderr.

`regen-views` and `stamp-merged` lost their bodies when derived views were retired
— `regen-views` had no views left to regenerate, and `stamp-merged`'s only output
(`status=`) had no reader left. `bug-inbox` joined them when the upstream bug
drop-box retired: it resolved a local directory for `/prawduct:report-bug` to
write a report into, and reports are GitHub issues now, so there is no directory
left to resolve. None was DELETED, because `api-contract.md`'s deprecation norm
requires a retired subcommand to stay callable, announce itself on stderr, and
defer removal to a major: prawduct's own release runbook called `regen-views`, and
a non-zero exit in a copied operator script would break a pipeline mid-release.

**Announcing is the half of the tier that has a reader.** `build-index` and
`user-prompt-submit` are inert too and say *nothing* on either stream, because
their caller is a stale `hooks.json` registration rather than a person — pinned in
`tests/test_retired_hook_subcommands.py`. Membership here means a human or a
script calls the command and can act on being told to stop.

**That inert-but-callable shape is a promise to those scripts, and this file is
the only thing holding it.** The ~20 tests that covered these commands lived in
`tests/test_views.py` and died correctly with the machinery they exercised; the
surviving contract needs its own pin. Without one, a later edit that drops the
subcommand, restores a non-zero exit, or removes the notice breaks a copied
release script silently and the suite stays green.

The contract, per command:

* exit 0, always — including for flags that no longer mean anything;
* a `WARNING:` notice on **stderr** (stdout stays clean for pipelines);
* the notice says what to do instead, in plain language;
* nothing on disk changes.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = REPO_ROOT / "bin" / "prawduct-hook"

# Both commands, and the argument forms an old script might still pass. `--check`
# is here because it was `regen-views`' own previously-deprecated flag: a script
# pinned before that deprecation passes it, and must not now hit a usage error.
#
# `bug-inbox` appears bare only: it never accepted a flag, so no pinned script
# passes one, and it stays in the hook's `_NO_ARGUMENT_COMMANDS` refusal set
# where a mistyped argument is still worth reporting as a usage error.
INERT_INVOCATIONS = [
    ("regen-views",),
    ("regen-views", "--check"),
    ("regen-views", "--a-flag-that-never-existed"),
    ("stamp-merged",),
    ("bug-inbox",),
]

#: Derived, not transcribed — a command added above is covered below too.
ANNOUNCING_TIER = tuple(dict.fromkeys(argv[0] for argv in INERT_INVOCATIONS))


def _repo(tmp_path: Path) -> Path:
    """A minimal governed repo with a change log and a half-done build plan —
    the state in which `regen-views` and `stamp-merged` used to WRITE, so a
    command that still wrote something would have something to write. It is the
    fixture for the whole tier: `bug-inbox` never wrote here, and a repo that
    would notice a write is a strictly stronger place to prove it does not."""
    repo = tmp_path / "repo"
    (repo / ".prawduct" / "artifacts").mkdir(parents=True)
    (repo / ".prawduct" / "project-state.yaml").write_text(
        "base_branch: main\nactive_build_plan: artifacts/build-plan-demo.md\n"
    )
    (repo / ".prawduct" / "change-log.md").write_text(
        "# Change Log\n\n## 2026-08-08: a thing\n"
        "<!-- prawduct: chunks=01 | scope=demo -->\n\nBody.\n"
    )
    (repo / ".prawduct" / "artifacts" / "build-plan-demo.md").write_text(
        "---\nartifact: build-plan\nscope: demo\n---\n\n"
        "## Status\n\n- [ ] Chunk 01: first\n- [ ] Chunk 02: second\n"
    )
    return repo


def _run(repo: Path, argv: tuple[str, ...]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK), *argv],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "CLAUDE_PROJECT_DIR": str(repo)},
        timeout=30,
    )


def _tree(repo: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(repo)): p.read_bytes()
        for p in sorted(repo.rglob("*"))
        if p.is_file()
    }


@pytest.mark.parametrize("argv", INERT_INVOCATIONS, ids=lambda a: " ".join(a))
class TestInertContract:
    def test_exits_zero(self, tmp_path: Path, argv: tuple[str, ...]):
        """Exit 0 including for an unknown flag.

        A usage error here would be the pipeline break the deprecation exists to
        avoid: a command that does nothing cannot be misused, so there is no
        input worth refusing.
        """
        proc = _run(_repo(tmp_path), argv)
        assert proc.returncode == 0, proc.stdout + proc.stderr

    def test_announces_itself_on_stderr_not_stdout(
        self, tmp_path: Path, argv: tuple[str, ...]
    ):
        """`api-contract.md`: deprecation is signalled, not silent — and the
        channel split matters, because stdout is what a pipeline consumes."""
        proc = _run(_repo(tmp_path), argv)
        assert "WARNING:" in proc.stderr, proc.stderr
        assert argv[0] in proc.stderr, proc.stderr
        assert "WARNING:" not in proc.stdout, proc.stdout

    def test_the_notice_says_what_to_do_instead(
        self, tmp_path: Path, argv: tuple[str, ...]
    ):
        """A deprecation notice that only says "stop" strands its reader. Every
        notice must name the replacement — and none may name a prawduct-internal
        identifier (the observability norm), which is why the assertion is on
        plain words rather than a requirement or chunk id."""
        proc = _run(_repo(tmp_path), argv)
        assert "drop the call" in proc.stderr, proc.stderr
        for internal in ("DV7", "DECISION-", "Chunk 0", "#629"):
            assert internal not in proc.stderr, (
                f"the notice names the internal identifier {internal!r}: {proc.stderr!r}"
            )

    def test_writes_nothing(self, tmp_path: Path, argv: tuple[str, ...]):
        """The load-bearing half of "inert".

        Asserted over the WHOLE tree byte-for-byte rather than on the files these
        commands used to touch: a regression that wrote to some other path would
        pass a check that only re-read the build plan. The fixture is deliberately
        the state in which they used to write — an unflipped Status and a tagged,
        release-pending change-log entry — so "nothing changed" is evidence rather
        than a fixture with nothing to change.
        """
        repo = _repo(tmp_path)
        before = _tree(repo)
        _run(repo, argv)
        assert _tree(repo) == before


def test_the_fixture_would_notice_a_write(tmp_path: Path):
    """Positive control for `test_writes_nothing`.

    Every assertion there is an equality between two snapshots, and equality is
    also what a `_tree` that silently stopped reading files would report. So
    perturb the same fixture through the same comparison and require it to be
    SEEN — otherwise a broken snapshot helper makes every case above vacuous.
    """
    repo = _repo(tmp_path)
    before = _tree(repo)
    (repo / ".prawduct" / "artifacts" / "build-plan-demo.md").write_text(
        "---\nartifact: build-plan\nscope: demo\n---\n\n"
        "## Status\n\n- [x] Chunk 01: first\n- [ ] Chunk 02: second\n"
    )
    assert _tree(repo) != before


def test_every_announcing_command_is_still_dispatched(tmp_path: Path):
    """The deprecation's whole point: no name may become unrecognized.

    An unknown command exits non-zero with a usage error, which is precisely the
    break a copied release script would hit — and it is a different failure from
    the notice tests above, which would also pass if the dispatcher fell through
    to a generic handler that happened to print a warning.
    """
    repo = _repo(tmp_path)
    for name in ANNOUNCING_TIER:
        proc = _run(repo, (name,))
        assert proc.returncode == 0
        assert "unknown command" not in (proc.stdout + proc.stderr).lower()


def test_the_usage_text_advertises_every_announcing_command(tmp_path: Path):
    """A reader running `prawduct-hook` bare must be told these exist and do
    nothing. Without it the only way to learn a command is retired is to call it,
    which is the discovery path a copied script never takes."""
    usage = _run(tmp_path, ()).stderr
    for name in ANNOUNCING_TIER:
        assert f"{name} [deprecated, inert]" in usage, (
            f"`{name}` is inert but the usage text does not say so:\n{usage}"
        )


def test_no_announcing_command_reports_a_condition_it_can_no_longer_have(
    tmp_path: Path,
):
    """`bug-inbox` is why this exists, and it generalises.

    It used to exit **1** to mean *no inbox is configured* — a real condition a
    caller could branch on. Nothing can be configured now, so a surviving 1 would
    report a state rather than a retirement, and a script branching on it would
    take the not-configured arm forever. Exit 0 is asserted above for a repo
    carrying prawduct state; assert it too for a bare directory, which is the
    shape that used to produce the 1.
    """
    for name in ANNOUNCING_TIER:
        proc = _run(tmp_path, (name,))
        assert proc.returncode == 0, f"{name}: {proc.stdout + proc.stderr}"
        assert proc.stdout == "", f"{name} wrote to stdout: {proc.stdout!r}"
