"""The work-model index cache's gitignore contract, which OUTLIVES its producer.

The tripwire that generated `.prawduct/.work-model-index.json` was deleted in
v3.3.2 (owner ruling 2026-07-12, #257), and nothing writes the file any more.
**The ignore entries deliberately stay**, and these tests are why they cannot be
tidied away later as dead config:

every repo that ran a pre-3.3.2 session still has that file on disk. Dropping the
entries would resurface all of them as permanent untracked noise in every
governed repo — which is the exact defect the entries were added to fix (see the
v3.2.x CHANGELOG). An ignore line for a path nothing writes costs nothing; the
removal costs every consumer.

The rest of this file — the build-index/user-prompt-submit runtime contract,
index staleness and corruption recovery, corpus widening — went with the
tripwire. `prawduct-hook jurisdiction` is the surviving consumer of
`lib/work_model_index`, and it reads the corpus directly rather than this cache,
which is what made the deletion separable.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
REPO_ROOT = Path(__file__).resolve().parent.parent

HOOK = ROOT / "bin" / "prawduct-hook"
INDEX_RELPATH = ".prawduct/.work-model-index.json"


def _run(command: str, project_dir: Path, stdin: str = "") -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir), "CLAUDE_PLUGIN_ROOT": str(ROOT)}
    return subprocess.run(
        [sys.executable, str(HOOK), command],
        input=stdin, capture_output=True, text=True, env=env,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / ".prawduct" / "artifacts").mkdir(parents=True)
    return tmp_path


def test_index_is_gitignored():
    gitignore = (REPO_ROOT / ".gitignore").read_text()
    assert INDEX_RELPATH in gitignore


def test_index_is_in_gitignore_contract():
    """The entry must be in the canonical contract list that propagates to
    product repos — not just this framework repo's hand-edited ``.gitignore``.

    Originally a regression test for the ship that generated the index in every
    governed repo without ever writing an ignore line for it. It now guards the
    opposite direction: the producer is gone, and the entry must survive it so
    leftover caches stay invisible. ``TestSessionGitignoreMirror`` pins the
    hook's ``_SESSION_GITIGNORED_PATHS`` in sync, so asserting the core contract
    covers both lists.
    """
    sys.path.insert(0, str(ROOT))
    from lib.core import GITIGNORE_ENTRIES  # noqa: PLC0415

    assert INDEX_RELPATH in GITIGNORE_ENTRIES


def test_update_gitignore_writes_index_line(repo: Path):
    """End-to-end: a reconciled product ``.gitignore`` still ignores the index,
    so a repo carrying a pre-3.3.2 cache stays quiet instead of accruing noise.
    """
    sys.path.insert(0, str(ROOT))
    from lib.core import update_gitignore  # noqa: PLC0415

    update_gitignore(repo)
    assert INDEX_RELPATH in (repo / ".gitignore").read_text()


# --- corpus assembly (coverage the deleted build-index tests used to carry) --


def test_jurisdiction_corpus_covers_claude_md_docs_subdirs_and_methodology(repo: Path):
    """`_work_model_corpus_paths` is the surviving half of the tripwire's hook
    wiring — `jurisdiction` assembles its corpus through it.

    Its recursive doc-SUBDIRECTORY widening (gate-noise) was only ever exercised
    through `build-index`'s tests, which went out with the tripwire. Left
    uncovered, a regression would silently narrow `jurisdiction`'s corpus rather
    than fail anything — the quiet direction.

    Driven through the CLI rather than the private helper: the contract worth
    pinning is that a governing file in each corpus root can be FOUND, and a
    test that reached into `_work_model_corpus_paths` would keep passing if the
    subcommand stopped calling it.
    """
    (repo / ".prawduct" / "artifacts" / "spec.md").write_text(
        "# Spec\nThe **quaternion** subsystem.\n", encoding="utf-8")
    (repo / "CLAUDE.md").write_text("# Repo\nThe **holography** rules.\n", encoding="utf-8")
    (repo / "docs" / "nested").mkdir(parents=True)
    (repo / "docs" / "nested" / "deep.md").write_text(
        "# Deep\nThe **magnetosphere** notes.\n", encoding="utf-8")
    (repo / "methodology").mkdir()
    (repo / "methodology" / "m.md").write_text(
        "# M\nThe **bathysphere** guide.\n", encoding="utf-8")

    out = _run("jurisdiction", repo, stdin="quaternion holography magnetosphere bathysphere").stdout
    for expected in (
        ".prawduct/artifacts/spec.md",
        "CLAUDE.md",
        "docs/nested/deep.md",   # the widening that matters: a doc SUBDIRECTORY
        "methodology/m.md",
    ):
        assert expected in out, f"{expected} missing from the jurisdiction corpus:\n{out}"
