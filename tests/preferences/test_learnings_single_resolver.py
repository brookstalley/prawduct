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
#: Derived on 2026-09-02 from `git grep -l 'learnings.md' -- plugin` after Chunk
#: 01, classified against discovery R4/R5 (Wave 1), R6 (Wave 2) and R8/R13
#: (Wave 3). Seven entries are marked `wave-2` on the strength of §9's
#: **grep-clean sweep** rather than a named R6 deliverable: they are prose
#: citations and skill instructions that name the old path, nobody's chunk lists
#: them, and the sweep is the only mechanism the plan gives for them. They are
#: called out here rather than quietly filed so the sweep's owner knows they are
#: on it.
ALLOWLIST: dict[str, tuple[str, str]] = {
    # --- Wave 1, Chunk 04 (W1-C): detection, directive, cross-check re-pointed
    "plugin/lib/briefing.py": (
        "wave-1",
        "the learnings count line and the size nudge; Chunk 04 replaces both "
        "with the resolver's three states plus the migration directive",
    ),
    "plugin/lib/gates.py": (
        "wave-1",
        "the Critic gate's Learnings Cross-Check text (Chunk 04 points it at "
        "the resolver's file list for the session's changed paths)",
    ),
    "plugin/skills/critic/review-cycle.md": (
        "wave-1",
        "the Final-Mode Cross-Checks scan (Chunk 04); the `learnings-entry-shape` "
        "severity row beside it goes with its check in Wave 2",
    ),
    # --- Wave 2 (`learnings-v2-delete`), R6: whole-feature deletions
    "plugin/lib/audit_learnings_cmd.py": (
        "wave-2",
        "R6 — the lifecycle audit command is deleted whole",
    ),
    "plugin/lib/learnings_obligation.py": (
        "wave-2",
        "R6 — the descent-obligation marker mechanism is deleted whole "
        "(the obligation itself now ships in learnings_files.CORE_HEADER)",
    ),
    "plugin/lib/record_lint.py": (
        "wave-2",
        "R6 — `_check_learnings_shape` and its `learnings-entry-shape` finding "
        "are deleted; Wave 1's budget check replaces them",
    ),
    "plugin/lib/buildplan_refs.py": (
        "wave-2",
        "R6 — the `/prawduct:learnings` slash-command resolution goes with the "
        "skill",
    ),
    "plugin/bin/prawduct-hook": (
        "wave-2",
        "R6 — the removed verbs (`audit-learnings`, `check-learnings-pairing`, "
        "`learnings-obligation`) and the reflection gate's 'also add it to "
        "learnings.md' nudge text",
    ),
    "plugin/skills/learnings/SKILL.md": (
        "wave-2",
        "R6 — the `/prawduct:learnings` skill directory is deleted whole",
    ),
    "plugin/skills/doctor/SKILL.md": (
        "wave-2",
        "R6 — health checks 13/13a and the audit-learnings flow go with their "
        "commands",
    ),
    "plugin/methodology/planning.md": (
        "wave-2",
        "R6 — the § Learnings as Design Constraints instruction site",
    ),
    "plugin/methodology/building.md": (
        "wave-2",
        "R6 — the 'add a rule to learnings.md' instruction site",
    ),
    # --- Wave 2, via §9's grep-clean sweep (no named R6 deliverable)
    "plugin/lib/coverage.py": (
        "wave-2",
        "grep-clean sweep (§9): three docstring citations of the form "
        "``(learnings.md: \"…\")`` naming the file a rule came from",
    ),
    "plugin/lib/telemetry.py": (
        "wave-2",
        "grep-clean sweep (§9): two docstring citations naming the file a rule "
        "came from",
    ),
    "plugin/lib/evidence.py": (
        "wave-2",
        "grep-clean sweep (§9): one docstring citation naming the file a rule "
        "came from",
    ),
    "plugin/lib/critic_consolidate.py": (
        "wave-2",
        "grep-clean sweep (§9): one docstring citation naming the file a rule "
        "came from",
    ),
    "plugin/lib/coverage_algebra.py": (
        "wave-2",
        "grep-clean sweep (§9): the comment listing the `.prawduct/` records "
        "repo-coupled tests also read — a real path list, so it moves with the "
        "corpus",
    ),
    "plugin/skills/janitor/SKILL.md": (
        "wave-2",
        "grep-clean sweep (§9): 'capture learnings in .prawduct/learnings.md'",
    ),
    "plugin/skills/onboard/SKILL.md": (
        "wave-2",
        "grep-clean sweep (§9): the enumerated list of what init-product writes",
    ),
    "plugin/skills/migrate/SKILL.md": (
        "wave-2",
        "grep-clean sweep (§9): the enumerated list of product-owned state the "
        "migration preserves (R11 names this file's `learnings*.md` handling)",
    ),
    # --- Wave 3 (`learnings-v2-docs`)
    "plugin/methodology/reflection.md": (
        "wave-3",
        "R8 — the write-path guide is rewritten to the new model",
    ),
    "plugin/docs/principles.md": (
        "wave-3",
        "R13 — the 'case law that interprets the constitution' pointer is "
        "repointed with the rest of the records",
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
