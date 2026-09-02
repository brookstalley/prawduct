"""The deprecated-inert commands: callable, announced, and doing nothing.

Five commands lost their bodies without losing their names. `regen-views` had no
views left to regenerate and `stamp-merged`'s only output (`status=`) had no
reader left, when derived views were retired. `audit-learnings`,
`learnings-obligation` and `check-learnings-pairing` graded a lifecycle that no
longer exists: rules moved to `.claude/rules/learnings/`, where the harness loads
them by path match, so there is no `learnings.md` to audit, no descent obligation
to insert, and no summary/detail pair to grade.

None was DELETED, because `api-contract.md`'s deprecation norm requires a retired
subcommand a human or a skill can call to stay callable, announce itself on
stderr, and defer removal to a major: prawduct's own release runbook called
`regen-views`, and a copied `/prawduct:doctor` flow on an older per-project plugin
pin still calls the three learnings verbs. A non-zero exit in either is a pipeline
break where a notice would have been enough.

**That inert-but-callable shape is a promise to those callers, and this file is
the only thing holding it.** The tests that covered these commands died correctly
with the machinery they exercised — ~20 in `tests/test_views.py`, and over 200
across the three learnings-lifecycle files; the surviving contract needs its own
pin. Without one, a later edit that drops the subcommand, restores a non-zero
exit, or removes the notice breaks a copied script silently and the suite stays
green.

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

# Every command, and the argument forms an old script might still pass. `--check`
# is here because it was `regen-views`' own previously-deprecated flag: a script
# pinned before that deprecation passes it, and must not now hit a usage error.
# The learnings verbs carry the flags they used to honour for the same reason,
# `--apply` most of all: it selected the WRITING path, so a caller that passes it
# is the one that most needs "inert" to mean inert. `--json` was a machine
# contract, and a caller still piping it must get an empty stdout rather than a
# corrupted payload — `test_announces_itself_on_stderr_not_stdout` covers that.
INERT_INVOCATIONS = [
    ("regen-views",),
    ("regen-views", "--check"),
    ("regen-views", "--a-flag-that-never-existed"),
    ("stamp-merged",),
    ("audit-learnings",),
    ("audit-learnings", "--json"),
    ("audit-learnings", "--apply", "--json"),
    ("audit-learnings", "--a-flag-that-never-existed"),
    ("learnings-obligation",),
    ("learnings-obligation", "--apply"),
    ("learnings-obligation", "--a-flag-that-never-existed"),
    ("check-learnings-pairing",),
    ("check-learnings-pairing", "--json"),
    ("check-learnings-pairing", "--a-flag-that-never-existed"),
]


def _repo(tmp_path: Path) -> Path:
    """A governed repo holding, for EVERY command here, the state in which it
    used to write — so "nothing changed" is evidence rather than a fixture with
    nothing to change.

    For `regen-views` and `stamp-merged`: an unflipped build-plan `## Status` and
    a tagged, release-pending change-log entry.

    For the three learnings verbs, a legacy corpus in the shape each one acted
    on. `audit-learnings --apply` retired an entry whose `superseded-by=` pointer
    resolved — the route chosen here because it needed no test runner, so the
    fixture cannot be inert for the accidental reason that this repo declared no
    way to run one. `learnings-obligation --apply` inserted the
    `prawduct:descent-obligation` marker above the first rule, so the file
    deliberately lacks one. `check-learnings-pairing` never wrote, but it graded
    this pair and reported findings on it: the detail file carries the duplicate
    active heading that made it exit 1, so a stub that fell through to the old
    body would be visible in the exit code as well as the tree.
    """
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
    (repo / ".prawduct" / "learnings.md").write_text(
        "# Learnings\n\n"
        "## A narrow rule about widgets\n"
        "<!-- prawduct-learning: confirmations=2; created=2026-02-22;"
        " superseded-by=A broad rule -->\n\n"
        "Body of the narrow rule.\n\n"
        "## A broad rule about every component\n\n"
        "Body of the broad rule.\n"
    )
    (repo / ".prawduct" / "learnings-detail.md").write_text(
        "# Learnings Detail\n\n"
        "## A broad rule about every component\n\nOne copy.\n\n"
        "## A broad rule about every component\n\nThe duplicate.\n\n"
        "## Historical (structurally enforced)\n"
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


INERT_COMMANDS = (
    "regen-views",
    "stamp-merged",
    "audit-learnings",
    "learnings-obligation",
    "check-learnings-pairing",
)


def test_every_command_is_still_dispatched(tmp_path: Path):
    """The deprecation's whole point: no name may become unrecognized.

    An unknown command exits non-zero with a usage error, which is precisely the
    break a copied release script would hit — and it is a different failure from
    the notice tests above, which would also pass if the dispatcher fell through
    to a generic handler that happened to print a warning.
    """
    repo = _repo(tmp_path)
    for name in INERT_COMMANDS:
        proc = _run(repo, (name,))
        assert proc.returncode == 0
        assert "unknown command" not in (proc.stdout + proc.stderr).lower()


def test_the_usage_text_still_lists_every_inert_command(tmp_path: Path):
    """A deprecated verb is still a verb.

    Dropping it from the usage string is how a caller reading `--help` concludes
    the command is gone and rewrites a working script around its absence — the
    same outcome as deleting it, arrived at through the documentation. Asserted
    against the usage text the hook prints for an unknown command, which is the
    text that reader actually meets.
    """
    proc = _run(_repo(tmp_path), ("a-command-that-never-existed",))
    usage = proc.stdout + proc.stderr
    for name in INERT_COMMANDS:
        assert name in usage, f"`{name}` is missing from the usage text: {usage!r}"


LEARNINGS_VERBS = ("audit-learnings", "learnings-obligation", "check-learnings-pairing")


def test_the_learnings_notices_name_where_rules_live_now(tmp_path: Path):
    """"Drop the call" is only half an answer for these three.

    Their caller is an operator or a copied doctor flow that wanted to know
    something about this repo's rules, and the honest reply is that the question
    moved rather than vanished. Without the path, the notice tells them a
    capability is gone and leaves them looking for a replacement command that
    does not exist.
    """
    repo = _repo(tmp_path)
    for name in LEARNINGS_VERBS:
        proc = _run(repo, (name,))
        assert ".claude/rules/learnings/" in proc.stderr, (name, proc.stderr)


def test_the_learnings_verbs_no_longer_grade_the_legacy_corpus(tmp_path: Path):
    """Exit 0 HERE means the body is gone, not that a surviving body found nothing.

    The fixture is a legacy corpus each old body had something to say about, and
    what it said was measured against the pre-deprecation source rather than
    assumed. **The two signals are not the same per command, which is why both
    assertions are here:** `check-learnings-pairing` exited **1** on the duplicate
    active heading, so the exit code carries it; `audit-learnings` (one promotion
    and one resolvable retirement candidate) and `learnings-obligation` (`missing`)
    both exited **0** on their dry runs and printed their report to **stdout**, so
    for those two the exit code proves nothing and the empty-stdout assertion is
    the whole discriminator.

    `test_writes_nothing` covers the mutating half over the same fixture: against
    the pre-deprecation source, `audit-learnings --apply --json` rewrote
    `learnings.md`, `learnings-detail.md` and `learnings-history.md`, and
    `learnings-obligation --apply` rewrote `learnings.md`.
    """
    repo = _repo(tmp_path)
    for name in LEARNINGS_VERBS:
        proc = _run(repo, (name,))
        assert proc.returncode == 0, (name, proc.stdout, proc.stderr)
        assert proc.stdout == "", (name, proc.stdout)
