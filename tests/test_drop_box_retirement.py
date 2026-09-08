"""The upstream bug drop-box is retired, and no shipped surface still names it.

Reports about prawduct itself used to be written as files into a gitignored
``incoming-bugs/`` directory on a co-located checkout. They are GitHub issues now:
``/prawduct:report-bug`` files through the backlog adapter's ``file-upstream``,
and ``untriaged-upstream-reports`` counts the open prefixed ones nobody has
staged. The channel was retired only once that replacement was counting, which is
the lockstep `documentation/backlog-service-upstream-filing.md` §7 requires.

**Removing a mechanism requires removing its name too, and that is what this file
holds.** The deletions are self-evident — a module that is gone is gone. What is
not self-evident is the prose: a skill, template or guide that still says a report
goes into a directory routes the next model into writing one where nothing reads
it, and every such surface passes its own tests while doing so. A sweep is the
only assertion that quantifies over the surfaces rather than over the ones the
builder happened to remember.

Two rules, and they are deliberately different shapes:

* **Machinery names appear nowhere in the shipped tree.** The env knob, the
  resolver, the pointer, the write-target template, the report scaffold and the
  archive destination exist for one purpose — routing a report to a directory —
  so any survivor is a live write path, wherever it sits.
* **The directory name appears in no instruction surface.** Code may still name it
  in a retirement notice addressed to a person; a skill, template, methodology
  guide or shipped doc may not name it at all, because a model reads those to
  decide what to do and a retired destination read as an available one is exactly
  the failure. ``CLAUDE.md`` is swept with them: it is this repo's own
  always-loaded instruction file.

An operator's local ``incoming-bugs/`` tree is untouched by any of this. It is
gitignored, so anything still in it has no other copy; retiring the channel is not
deleting somebody's archive.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN = REPO_ROOT / "plugin"

#: Every name that exists only to route a report into a directory. Banned from
#: the whole shipped tree, code included — unlike the directory name itself,
#: none of these can appear in a sentence that says the channel is over.
WRITE_PATH_TOKENS = (
    "PRAWDUCT_BUG_INBOX",   # the env knob that selected the directory
    "resolve_inbox",        # the resolver
    ".bug-inbox",           # the gitignored pointer file
    "<inbox>",              # the write-target template a report was rendered into
    "incoming-bug-report",  # the report scaffold
    "incoming-bugs/archive",  # where a triaged report was moved
    "import bug_inbox",     # the deleted module, however it is reached
    "from lib import bug_inbox",
)

#: The directory name. Legal in code that announces the retirement, illegal in
#: anything a model reads as instruction.
DROP_BOX_DIR = "incoming-bugs"

#: Surfaces a model reads to decide what to do.
INSTRUCTION_ROOTS = ("skills", "templates", "methodology", "docs")

#: Text extensions worth reading. Binary and cache files are skipped rather than
#: decoded — a sweep that raises on a `.pyc` is a sweep somebody disables.
TEXT_SUFFIXES = {".py", ".md", ".json", ".yaml", ".yml", ".txt", ".sh", ""}


def _shipped_files() -> list[Path]:
    """Every readable file under ``plugin/`` — the tree a consumer installs."""
    return [
        path
        for path in sorted(PLUGIN.rglob("*"))
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix.lower() in TEXT_SUFFIXES
    ]


def _instruction_files() -> list[Path]:
    """Shipped prose a model reads as instruction, plus this repo's CLAUDE.md."""
    out = [
        path
        for path in _shipped_files()
        if path.relative_to(PLUGIN).parts[0] in INSTRUCTION_ROOTS
    ]
    out.append(REPO_ROOT / "CLAUDE.md")
    return out


def _hits(files: list[Path], token: str) -> list[str]:
    """``file:line`` for every line carrying ``token``."""
    found = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if token in line:
                found.append(f"{path.relative_to(REPO_ROOT)}:{number}: {line.strip()}")
    return found


class TestTheSweepActuallyReads:
    """Every assertion below is an emptiness check, and a corpus that came back
    empty satisfies all of them. These make that impossible to miss.

    Not a formality: the two sweeps differ only in which files they read, so a
    glob that silently stopped matching would turn the whole module green while
    the surfaces it exists to police went unread.
    """

    def test_the_shipped_corpus_is_substantial(self):
        assert len(_shipped_files()) > 50, "the shipped sweep found almost nothing to read"

    def test_the_instruction_corpus_covers_every_root(self):
        roots = {
            path.relative_to(PLUGIN).parts[0]
            for path in _instruction_files()
            if path.is_relative_to(PLUGIN)
        }
        assert roots == set(INSTRUCTION_ROOTS), (
            f"the instruction sweep reads {sorted(roots)}, not {sorted(INSTRUCTION_ROOTS)} "
            "— a root that matches nothing is a root nobody is checking"
        )

    def test_claude_md_is_in_the_instruction_corpus_and_readable(self):
        claude = REPO_ROOT / "CLAUDE.md"
        assert claude in _instruction_files()
        assert claude.read_text(encoding="utf-8").strip(), "CLAUDE.md read as empty"

    def test_a_token_that_is_present_is_found(self):
        """The positive control for `_hits` itself. `prawduct` appears in every
        corner of both corpora, so a matcher that reports nothing is broken
        rather than reassuring."""
        assert _hits(_shipped_files(), "prawduct")
        assert _hits(_instruction_files(), "prawduct")


@pytest.mark.parametrize("token", WRITE_PATH_TOKENS)
def test_no_shipped_file_names_drop_box_write_machinery(token: str):
    """Each of these names one step of *putting a report into a directory*.

    A survivor is not a stale mention: it is a knob somebody can set, a pointer
    somebody can write, or a template somebody can render, for a channel with
    nothing behind it. Reports are filed as GitHub issues.
    """
    hits = _hits(_shipped_files(), token)
    assert not hits, (
        f"`{token}` is drop-box write machinery and the drop-box is retired:\n  "
        + "\n  ".join(hits)
    )


def test_no_instruction_surface_names_the_drop_box():
    """The prose half, and the one a green suite would otherwise hide.

    A skill, template, methodology guide, shipped doc or `CLAUDE.md` line naming
    the directory tells the next model a report can go there. Nothing writes it
    and nothing counts it, so a report that lands there is lost. Code is exempt —
    `prawduct-hook bug-inbox` names it to say the channel is over, which is a
    sentence addressed to a person, not a destination offered to a model.
    """
    hits = _hits(_instruction_files(), DROP_BOX_DIR)
    assert not hits, (
        f"an instruction surface still names `{DROP_BOX_DIR}/`, which is a retired "
        "destination — upstream reports are filed as GitHub issues:\n  "
        + "\n  ".join(hits)
    )


class TestTheDeletedArtifactsAreGone:
    """The resolver and the report scaffold, named rather than left implicit.

    They are what the write path was made of: a module that picked the directory
    and a template that shaped the file dropped into it. The `bug-inbox`
    subcommand that called the resolver is deliberately NOT deleted — it is
    human-callable, so the deprecation norm keeps it dispatchable and inert until
    a major, pinned in `tests/test_deprecated_inert_commands.py`.
    """

    def test_the_resolver_module_is_deleted(self):
        assert not (PLUGIN / "lib" / "bug_inbox.py").exists()

    def test_the_report_scaffold_is_deleted(self):
        assert not (PLUGIN / "templates" / "incoming-bug-report.md").exists()

    def test_the_subcommand_is_still_dispatchable(self):
        """The contrast that keeps the two deletions above from reading as a
        blanket removal, and the thing a later cleanup would get wrong."""
        assert 'command == "bug-inbox"' in (PLUGIN / "bin" / "prawduct-hook").read_text(
            encoding="utf-8"
        )
