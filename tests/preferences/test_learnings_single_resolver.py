"""Project-preferences enforcement: one resolver knows where learnings live.

Learnings moved out of `.prawduct/learnings.md` and into `.claude/rules/learnings/`,
where the harness loads them. The layout is now something four different jobs have
to agree about — the budget gate sizes what a session pays for, the Critic reads
the area files a diff pulls in, the briefing tells an unmigrated repo it is
unmigrated, and the migrate command rewrites the old file into the new ones. When
a second reader learns the path for itself, they stop agreeing the moment one of
them is updated, and the failure is silent in the worst direction: a file the
harness loaded that the reviewer never opened.

So `plugin/lib/learnings_files.py` is the one module that knows, and this test
pins that by the crudest possible property — **no non-test file under `plugin/`
contains the string `learnings.md`** unless it is on the list below. A string
match rather than an import graph, because the ways to hardcode a path are
unbounded and the ways to write it are one.

**Every entry carries the wave that deletes it, and the list only shrinks.** The
cutover is a three-wave program (`.prawduct/artifacts/learning-system-v2-discovery.md`
§8.1); at the end of it, R1's stated shape is "the migrate command and the
change-log" and nothing else. An entry whose file no longer contains the string
is a *failure*, not a pass: it means a wave landed and the list was not shrunk,
and a stale allowlist is how a guard quietly stops guarding. The falsifying
command, so this is checkable without running pytest:

    git grep -l 'learnings.md' -- plugin
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugin"

NEEDLE = "learnings.md"

#: The waves of the cutover program, plus `none` for the two entries no wave in
#: this program removes. Anything else in an entry's wave slot is a typo, and a
#: typo'd wave is an entry nobody will ever come back for.
WAVES = {"wave-1", "wave-2", "wave-3", "none"}

#: path (repo-relative, posix) -> (wave that removes the entry, why it is here).
#:
#: Derived from `git grep -l 'learnings.md' -- plugin`, classified against
#: discovery R4/R5 (Wave 1), R6 (Wave 2) and R8/R13 (Wave 3). Re-derive it with
#: that command rather than trusting this list's shape; the list only shrinks, so
#: a path the command returns that is not below is a new hardcoding, and a path
#: below that it does not return is an entry a landed wave forgot to remove.
#:
#: Wave 2 emptied every entry that held only a *prose citation* of the old path —
#: docstring rule-citations, the skill instructions naming what init/migrate
#: write, and the subagent-briefing embedding. What is left names the corpus for
#: a reason a reader can check in the file itself.
ALLOWLIST: dict[str, tuple[str, str]] = {
    # --- Wave 2 (`learnings-v2-delete`), R6: whole-feature deletions
    "plugin/lib/record_lint.py": (
        "none",
        "`_base_size`'s migration-commit exception reads the legacy file's size "
        "as `core.md`'s base, so a repo crossing that tree is not graded as "
        "having grown a 0B corpus; it retires with legacy detection, alongside "
        "`learnings_files.LEGACY_REL` and outside this program",
    ),
    "plugin/bin/prawduct-hook": (
        "wave-2",
        "R6 — the removed verbs (`audit-learnings`, `check-learnings-pairing`, "
        "`learnings-obligation`) and the reflection gate's 'also add it to "
        "learnings.md' nudge text",
    ),
    # --- Wave 3 (`learnings-v2-docs`)
    "plugin/methodology/reflection.md": (
        "wave-3",
        "R8 — the write-path guide is rewritten to the new model",
    ),
    "plugin/docs/norms.md": (
        "wave-3",
        "R13 — the norms-are-statute / learnings-are-case-law cross-links",
    ),
    # --- Wave 1, Chunk 02: the one module whose job is reading the old file
    "plugin/lib/learnings_migrate.py": (
        "none",
        "the migrate command names the legacy path because reading it IS its "
        "job (R1 keeps it in the end state); it retires only when the fleet "
        "cutover is complete, which is outside this program",
    ),
    # --- Permanent, and the resolver's own detection constant
    "plugin/CHANGELOG.md": (
        "none",
        "published history — it records what the old layout was and must keep "
        "saying so (R1 keeps it in the end state)",
    ),
    "plugin/lib/learnings_files.py": (
        "none",
        "`LEGACY_REL`, which is how `resolve()` tells the `legacy` and `both` "
        "states apart; it retires with legacy detection once the fleet has "
        "migrated, which is outside this program",
    ),
}


def _non_test_plugin_files() -> list[Path]:
    """Every file the plugin ships that is not a test.

    `plugin/tests/` and any `test_*.py` are excluded because a test that names
    the old path is asserting something about it, which is the opposite of
    hardcoding it.
    """
    out: list[Path] = []
    for path in PLUGIN_ROOT.rglob("*"):
        if not path.is_file():
            continue
        parts = path.relative_to(PLUGIN_ROOT).parts
        if "__pycache__" in parts or parts[0] == "tests":
            continue
        if path.name.startswith("test_"):
            continue
        out.append(path)
    return sorted(out)


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _contains_needle(path: Path) -> bool:
    try:
        return NEEDLE in path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False  # not text; cannot be hardcoding a path


def test_only_the_allowlist_names_the_legacy_corpus() -> None:
    offenders = [
        _rel(p)
        for p in _non_test_plugin_files()
        if _contains_needle(p) and _rel(p) not in ALLOWLIST
    ]
    assert not offenders, (
        "these plugin files name `learnings.md` and are not on the cutover "
        "allowlist — read the layout through `lib/learnings_files.resolve()` "
        "instead, or add the file with the wave that removes it:\n  "
        + "\n  ".join(offenders)
    )


def test_the_allowlist_holds_no_stale_entries() -> None:
    """An entry whose file no longer names the corpus must be deleted.

    This is the half that makes the list shrink. Without it a wave lands, the
    string goes, the entry stays, and the next wave's author reads a list that
    over-states how much of the old layout is left — while the guard silently
    permits a re-introduction at that path.

    A path that does not exist yet is fine: `lib/learnings_migrate.py` is
    allowlisted by Chunk 01 and created by Chunk 02.
    """
    stale = [
        rel
        for rel in ALLOWLIST
        if (REPO_ROOT / rel).is_file() and not _contains_needle(REPO_ROOT / rel)
    ]
    assert not stale, (
        "these allowlist entries no longer name `learnings.md` — delete them, "
        "the list only shrinks:\n  " + "\n  ".join(sorted(stale))
    )


def test_every_entry_names_the_wave_that_removes_it() -> None:
    bad = {
        rel: wave for rel, (wave, _why) in ALLOWLIST.items() if wave not in WAVES
    }
    assert not bad, f"unknown wave label(s) — expected one of {sorted(WAVES)}: {bad}"
    unexplained = [rel for rel, (_w, why) in ALLOWLIST.items() if len(why.strip()) < 20]
    assert not unexplained, (
        "every entry states why the file may still name the corpus — a bare "
        "path is a permission nobody can audit:\n  " + "\n  ".join(unexplained)
    )


def test_the_resolver_is_present_and_is_the_one_that_knows() -> None:
    """The left-hand side is non-empty.

    A scan whose subject silently becomes nothing passes forever while checking
    nothing. Two anchors: the plugin surface is non-trivial, and the module the
    allowlist exists to protect actually holds the constants.
    """
    assert len(_non_test_plugin_files()) > 50
    resolver = PLUGIN_ROOT / "lib" / "learnings_files.py"
    text = resolver.read_text(encoding="utf-8")
    for constant in ("RULES_DIR_REL", "CORE_NAME", "LEGACY_REL", "def resolve("):
        assert constant in text, f"{constant} is gone from the one resolver"
