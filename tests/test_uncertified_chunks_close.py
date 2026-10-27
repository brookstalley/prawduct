"""A whole-plan review that certifies no chunk says so where the builder reads (#1081).

The proposal's notes print to ``critic-begin``'s stderr, inside the forked
critic, and never reach the main agent. So a boundary ``cumulative`` that
proposed nothing certified nothing in silence, and the plan's chunks read open
until the release archived them as unbuilt. The relayed ``NEXT-ACTION:`` line is
the one carrier the fork must pass on verbatim, so the clause rides it, and the
``.critic-findings.json`` copy of that line, from the same computation.

Driven through the CLI, the layer the defect was reported at.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib import critic_consolidate as cc
from test_critic_consolidate import (
    PARTIALS_REL,
    _commit_file,
    _git,
    _init_repo,
    _run_begin,
    _run_consolidate,
    _write_partial,
)

PLAN = (
    "---\nartifact: build-plan\nscope: work\nbranch: feat/work\n---\n\n# Plan\n\n"
    "## Build Chunks\n\n"
    "### Chunk 01: one\n\n- **Deliverables:** the first part\n\n"
    "### Chunk 02: two\n\n- **Deliverables:** the second part\n"
)


def _review(repo: Path, *begin_args: str):
    begin = _run_begin(repo, *begin_args)
    assert begin.returncode == 0, begin.stderr
    manifest = json.loads((repo / PARTIALS_REL / "manifest.json").read_text())
    _write_partial(repo, "reviewer", manifest["commit_reviewed"], findings=[])
    done = _run_consolidate(repo)
    assert done.returncode == 0, done.stderr
    return done


def _close(
    tmp_path: Path, *begin_args: str, first: "tuple[str, ...] | None" = None
) -> "tuple[str, dict]":
    """Both chunks' work committed under subjects that name no chunk, so no
    proposal finds it; reviewed with ``begin_args`` (after a ``first`` review,
    when given). Returns the NEXT-ACTION line and the findings cache."""
    repo = tmp_path / "r"
    _init_repo(repo)
    _commit_file(repo, "src/app.py", "x = 1\n", "init")
    _commit_file(repo, ".prawduct/project-state.yaml", "project_name: t\n", "state")
    _commit_file(repo, ".prawduct/artifacts/build-plan-work.md", PLAN, "plan")
    _git(repo, "checkout", "-b", "feat/work", "--quiet")
    _commit_file(repo, "src/app.py", "x = 2\n", "feat(work): the first part")
    _commit_file(repo, "src/more.py", "y = 1\n", "feat(work): the second part")
    if first:
        _review(repo, *first)
    done = _review(repo, *begin_args)
    line = next(l for l in done.stdout.splitlines() if l.startswith("NEXT-ACTION:"))
    cache = json.loads((repo / ".prawduct" / ".critic-findings.json").read_text())
    return line, cache


# Renegotiated with span-derived chunk state: the review may certify chunks its
# interval builds without naming them, so the clause says it NAMED none, never
# that it certified none.
CLAUSE = "named no chunk"


def test_a_cumulative_that_certifies_nothing_names_the_open_chunks(tmp_path):
    line, cache = _close(tmp_path, "--mode", "cumulative")
    assert CLAUSE in line
    assert "01, 02" in line and "--chunks 01,02" in line
    # The findings file is the other carrier of the same sentence.
    assert CLAUSE in cache["next_action"] and "--chunks 01,02" in cache["next_action"]


def test_a_cumulative_that_certifies_a_chunk_says_nothing(tmp_path):
    """Control: the same history with the chunk declared. Something was
    certified, so the default did not silently drop the plan's work."""
    line, cache = _close(tmp_path, "--mode", "cumulative", "--chunks", "01")
    assert CLAUSE not in line and CLAUSE not in cache["next_action"]


def test_a_cumulative_with_nothing_left_open_says_nothing(tmp_path):
    """The ordinary boundary: chunk reviews already certified every chunk, then
    the cumulative runs without `--chunks` and certifies none, because none is
    open. The clause there would send the builder to pass `--chunks` for work
    already certified."""
    line, cache = _close(
        tmp_path, "--mode", "cumulative",
        first=("--mode", "final", "--chunks", "01,02"),
    )
    assert CLAUSE not in line and CLAUSE not in cache["next_action"]


def test_a_chunk_mode_review_that_names_nothing_says_nothing(tmp_path):
    """A `chunk` review certifies what its own diff touched; naming nothing
    mid-plan is ordinary, and the clause would be noise on every fix round."""
    line, _ = _close(tmp_path, "--mode", "chunk")
    assert CLAUSE not in line


@pytest.mark.parametrize("blocking", [0, 1])
def test_the_clause_rides_every_arm(blocking):
    line = cc.next_action_line("rev-x", blocking, 0, 0, uncertified=("cumulative", ["03"]))
    assert line.endswith(cc.uncertified_clause("cumulative", ["03"]))
    assert cc.next_action_line("rev-x", blocking, 0, 0).find(CLAUSE) == -1
