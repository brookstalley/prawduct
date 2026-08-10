"""`regen-views` and `stamp-merged`: deprecated, callable, and inert.

Both commands lost their bodies when derived views were retired — `regen-views`
had no views left to regenerate, and `stamp-merged`'s only output (`status=`) had
no reader left. Neither was DELETED, because `api-contract.md`'s deprecation norm
requires a retired subcommand to stay callable, announce itself on stderr, and
defer removal to a major: prawduct's own release runbook called `regen-views`, and
a non-zero exit in a copied operator script would break a pipeline mid-release.

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
INERT_INVOCATIONS = [
    ("regen-views",),
    ("regen-views", "--check"),
    ("regen-views", "--a-flag-that-never-existed"),
    ("stamp-merged",),
]


def _repo(tmp_path: Path) -> Path:
    """A minimal governed repo with a change log and a half-done build plan —
    the state in which both commands used to WRITE, so a command that still
    wrote something would have something to write."""
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
        """A deprecation notice that only says "stop" strands its reader. Both
        notices must name the replacement — and neither may name a
        prawduct-internal identifier (the observability norm), which is why the
        assertion is on plain words rather than a requirement or chunk id."""
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
    SEEN — otherwise a broken snapshot helper makes all four cases vacuous.
    """
    repo = _repo(tmp_path)
    before = _tree(repo)
    (repo / ".prawduct" / "artifacts" / "build-plan-demo.md").write_text(
        "---\nartifact: build-plan\nscope: demo\n---\n\n"
        "## Status\n\n- [x] Chunk 01: first\n- [ ] Chunk 02: second\n"
    )
    assert _tree(repo) != before


def test_both_commands_are_still_dispatched(tmp_path: Path):
    """The deprecation's whole point: neither name may become unrecognized.

    An unknown command exits non-zero with a usage error, which is precisely the
    break a copied release script would hit — and it is a different failure from
    the notice tests above, which would also pass if the dispatcher fell through
    to a generic handler that happened to print a warning.
    """
    repo = _repo(tmp_path)
    for name in ("regen-views", "stamp-merged"):
        proc = _run(repo, (name,))
        assert proc.returncode == 0
        assert "unknown command" not in (proc.stdout + proc.stderr).lower()
