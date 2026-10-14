"""Tests for the stale-anchor detector and its offered repair (`prawduct-hook reanchor`).

The defect being closed is silent by construction: the anchor writer returns
as soon as it sees the sentinel, so a repo carrying an anchor prawduct shipped two
revisions ago is byte-indistinguishable, to every other code path, from one
carrying the current text. Nothing failed; new onboards got the fix and the whole
already-onboarded fleet did not.

The load-bearing tests here are the **refusals**, not the repair. A repair that
rewrites a governance anchor is editing the product's own instruction files, so the
ways it must decline — an owner-edited anchor, an undecodable file, a dry run —
are what keep it safe to offer at all; the happy path is one string swap. The
byte-preservation test is the sharpest of them: the anchor has no END delimiter,
so a repair that inferred where it stopped could eat the product's instructions,
and only a byte comparison of everything outside the swapped region can say it
did not.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import os

import pytest

# Self-sufficient on sys.path — don't depend on another test module having
# inserted the plugin root first (mirrors tests/test_onboarding_probes.py).
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from lib import anchor_repair as ar  # noqa: E402
from lib.migrate_plugin import STATIC_ANCHOR  # noqa: E402

_HOOK = _PLUGIN_ROOT / "bin" / "prawduct-hook"

_PRODUCT_HEAD = "# CLAUDE.md — Legacy\n\n"
_PRODUCT_TAIL = "\n\n## Legacy-specific\n\nDon't touch this product instruction.\n"


def _write_claude(root: Path, anchor: str | None) -> Path:
    """A product CLAUDE.md with its own prose on both sides of the anchor."""
    root.mkdir(parents=True, exist_ok=True)
    body = "" if anchor is None else anchor
    (root / "CLAUDE.md").write_text(_PRODUCT_HEAD + body + _PRODUCT_TAIL, encoding="utf-8")
    return root


def _write_agents(root: Path, anchor: str | None) -> Path:
    """The current layout: the product's prose and the anchor in AGENTS.md, and a
    CLAUDE.md that is exactly the import."""
    root.mkdir(parents=True, exist_ok=True)
    body = "" if anchor is None else anchor
    (root / "AGENTS.md").write_text(_PRODUCT_HEAD + body + _PRODUCT_TAIL, encoding="utf-8")
    (root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    return root


#: An anchor an owner wrote themselves that says every load-bearing thing.
_HOME_GROWN = (
    "<!-- PRAWDUCT:ANCHOR — ours, kept deliberately short -->\n\n"
    "## Governance\n\n"
    "Prawduct governs this repo. If `/prawduct:*` is missing the plugin is not\n"
    f"installed and nothing here is enforced — run `{ar.NOTICE_PROBE}` first.\n"
    f"Review rigor is {ar.STAGE_PROBE}: the mid-build review is the cheap one."
)


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_HOOK), "reanchor", *args],
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "CLAUDE_PLUGIN_ROOT": str(_PLUGIN_ROOT),
            "CLAUDE_PROJECT_DIR": str(root),
        },
    )


def _release_tags() -> list[str]:
    """Every `vX.Y.Z` tag in this clone, or [] when tags are unreachable."""
    r = subprocess.run(
        ["git", "tag", "-l", "v*"],
        capture_output=True, text=True, cwd=str(_PLUGIN_ROOT.parent),
    )
    return r.stdout.split() if r.returncode == 0 else []


#: Returned for a tag that predates `migrate_plugin.py` itself. Distinct from
#: `None`, and the distinction is the point: "this release had no anchor" is a
#: correct skip, while "this release had one and I could not read it" is the
#: guard going blind. One value for both would have made the second look like the
#: first — which is the vacuous pass this reader exists to avoid.
_NO_MODULE = object()


def _shipped_anchor(tag: str):
    """`STATIC_ANCHOR` as that tag rendered it.

    Returns the rendered text, ``_NO_MODULE`` when the tag predates the module,
    or ``None`` when the module is there but its anchor could not be rendered.

    **Evaluates the module-level assignments; never imports the module.** An
    import would run `from . import core, lifecycle_repair`, which a historical
    tree need not satisfy, and would put an old revision of the code under test
    into the interpreter testing the current one. Only `Assign` statements are
    evaluated, in a namespace holding nothing but builtins and what earlier
    assignments produced — so no historical function body ever runs.

    This replaced a version that hand-rendered the f-string from `ast.Constant`
    parts only. It could resolve `{ANCHOR_MARKER}` and nothing else, so the day
    `STATIC_ANCHOR` began interpolating `{PLUGIN_ID}` — a `next(iter(...))` call
    — it returned None for every tag carrying that code. Green then, because no
    tag did yet; red at the first release cut from that branch, pointing the
    release at this reader rather than at the anchor.
    """
    src = None
    for rel in ("plugin/lib/migrate_plugin.py", "lib/migrate_plugin.py"):
        r = subprocess.run(
            ["git", "show", f"{tag}:{rel}"],
            capture_output=True, text=True, cwd=str(_PLUGIN_ROOT.parent),
        )
        if r.returncode == 0:
            src = r.stdout
            break
    if src is None:
        return _NO_MODULE

    return _render_anchor(src, tag)


def _render_anchor(src: str, origin: str):
    """`STATIC_ANCHOR` rendered from module source, or None if unresolvable."""
    try:
        tree = ast.parse(src)
    except SyntaxError:  # pragma: no cover — source that does not parse
        return None

    namespace: dict = {}
    for node in tree.body:
        # BOTH assignment forms. `INSTALL_REFERENCE` carries a type annotation and
        # is therefore an `AnnAssign`, not an `Assign` — handling only the latter
        # left `PLUGIN_ID` unresolvable and `STATIC_ANCHOR` with it, which is the
        # same "the reader cannot see it" defect one level down from the one this
        # function was rewritten to fix.
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue
            target, value_node = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            if node.value is None or not isinstance(node.target, ast.Name):
                continue
            target, value_node = node.target, node.value
        else:
            continue
        try:
            value = eval(  # noqa: S307 — module-level literals + builtins only
                compile(ast.Expression(value_node), f"<{origin}>", "eval"),
                {"__builtins__": __builtins__},
                namespace,
            )
        except Exception:  # noqa: BLE001 — an assignment we cannot resolve is skipped
            continue
        namespace[target.id] = value

    anchor = namespace.get("STATIC_ANCHOR")
    return anchor.strip() if isinstance(anchor, str) else None


# =============================================================================
# Grading
# =============================================================================
#
# The anchor's home moved from CLAUDE.md to AGENTS.md (#942, #928 D-8), and
# CLAUDE.md became the one line `@AGENTS.md`. The substance tests below grade
# the anchor where it now lives, through `_write_agents`; the layout tests
# grade a shipped anchor still sitting in CLAUDE.md, which every repo onboarded
# before the move carries.


def test_current_anchor_is_ok(tmp_path: Path):
    root = _write_agents(tmp_path / "current", STATIC_ANCHOR.strip())
    assert ar.check(root)["status"] == ar.STATUS_OK


def test_a_shipped_anchor_in_claude_md_is_legacy_layout_and_repairable(tmp_path: Path):
    """Renegotiated from `..._prior_anchor_is_stale_and_repairable`: a shipped
    anchor in CLAUDE.md is now wrong by PLACE before it is wrong by text — a host
    that reads only AGENTS.md never sees it — so it grades `legacy-layout`, which
    is prawduct's to repair, exactly as `stale` was."""
    root = _write_claude(tmp_path / "old", ar.ANCHOR_V2)
    result = ar.check(root)
    assert result["status"] == ar.STATUS_LEGACY_LAYOUT
    assert result["repairable"] is True
    assert result["path"] == ar.CLAUDE_REL


def test_the_last_claude_md_anchor_is_legacy_layout_not_edited(tmp_path: Path):
    """The cohort this chunk exists for: every repo onboarded on v3.6–v3.7
    carries `ANCHOR_V5` in CLAUDE.md. Missing from the archive, each would be
    told it had edited text prawduct wrote."""
    root = _write_claude(tmp_path / "v5", ar.ANCHOR_V5)
    assert ar.check(root)["status"] == ar.STATUS_LEGACY_LAYOUT


def test_a_shipped_anchor_in_agents_md_is_stale_and_repairable(tmp_path: Path):
    root = _write_agents(tmp_path / "old-agents", ar.ANCHOR_V2)
    result = ar.check(root)
    assert result["status"] == ar.STATUS_STALE
    assert result["repairable"] is True
    assert result["path"] == ar.AGENTS_REL


def test_the_anchor_that_predates_the_stage_rule_is_stale_and_repairable(tmp_path: Path):
    """An already-onboarded repo carrying the v3.5.0 anchor verbatim is
    prawduct's to repair, not the owner's to reword.

    This is the case the archive-first ordering exists for: that anchor CARRIES
    the install command, so a notice-first check would grade it healthy and the
    stage rule would never reach the fleet that onboarded on v3.5.0. The detail
    names the one sentence it lacks and not the one it has.
    """
    root = _write_agents(tmp_path / "v350", ar.ANCHOR_V3)
    result = ar.check(root)
    assert result["status"] == ar.STATUS_STALE
    assert result["repairable"] is True
    assert "stage-keyed review rule" in result["detail"]
    assert "plugin-absent notice" not in result["detail"]

    ar.repair(root, apply=True)
    assert (root / "AGENTS.md").read_text(encoding="utf-8") == (
        _PRODUCT_HEAD + STATIC_ANCHOR.strip() + _PRODUCT_TAIL
    )


def test_a_hand_edited_anchor_lacking_the_stage_rule_is_stale_modified(tmp_path: Path):
    """An owner-edited v3.5.0 anchor carries the notice, matches no shipped text,
    and says nothing about stages. Graded by the notice alone, it reads `ok` and
    the owner is never told.
    """
    edited = ar.ANCHOR_V3.replace(
        "- **Tests are contracts** — fix the code, never weaken a test.",
        "- **Tests are contracts** — and in THIS repo, also run `make lint`.",
    )
    assert ar.NOTICE_PROBE in edited, "fixture must carry the notice, or it tests the older probe"
    root = _write_agents(tmp_path / "v350-edited", edited)
    result = ar.check(root)
    assert result["status"] == ar.STATUS_STALE_MODIFIED
    assert result["repairable"] is False
    assert "stage-keyed review rule" in result["detail"]
    assert "plugin-absent notice" not in result["detail"]


def test_a_notice_era_stale_anchor_is_told_both_things_it_lacks(tmp_path: Path):
    """The other rendered branch of the derived detail: an anchor from before
    the notice lacks both sentences, and the report says so — the wording is
    computed from the archive entry, never written for one revision."""
    result = ar.check(_write_agents(tmp_path / "v2", ar.ANCHOR_V2))
    assert result["status"] == ar.STATUS_STALE
    assert "plugin-absent notice and the stage-keyed review rule" in result["detail"]


def test_a_fresh_scaffold_writes_the_agents_md_layout(tmp_path: Path):
    """`init-product` writes the current layout, so a new onboard grades `ok`:
    the anchor (stage rule included) in AGENTS.md, and a CLAUDE.md that is
    exactly the import. Pinned here because the repair can never reach this
    population — new onboards are the one cohort with no second line of defence.
    """
    from lib.init_product import init_product

    root = tmp_path / "fresh"
    root.mkdir()
    init_product(root, "demo", apply=True)
    assert ar.STAGE_PROBE in (root / "AGENTS.md").read_text(encoding="utf-8")
    assert (root / "CLAUDE.md").read_text(encoding="utf-8") == "@AGENTS.md\n"
    assert ar.check(root)["status"] == ar.STATUS_OK


def test_a_healthy_grade_and_a_finished_repair_describe_the_same_anchor(tmp_path: Path):
    """Two user-facing sentences, one source: the `ok` detail and the post-repair
    report both say what a current anchor carries — both load-bearing sentences
    by name — so neither can lag the other when the table grows."""
    healthy = ar.check(_write_agents(tmp_path / "healthy", STATIC_ANCHOR.strip()))["detail"]
    repaired = ar.repair(_write_claude(tmp_path / "repaired", ar.ANCHOR_V3), apply=True)["detail"]
    for detail in (healthy, repaired):
        assert ar.NOTICE_PROBE in detail
        assert ar.STAGE_PROBE in detail
    assert repaired.startswith("the governance anchor was moved to AGENTS.md")
    assert healthy.startswith("the anchor tells ")


def test_owner_edited_anchor_is_reported_not_repaired(tmp_path: Path):
    """The refusal that protects an owner who reworded their own anchor, in
    either file. Replacement is exact-match, so an anchor that matches nothing
    prawduct shipped is not prawduct's to rewrite — and in CLAUDE.md it is not
    prawduct's to move either."""
    edited = ar.ANCHOR_V2.replace(
        "- **Tests are contracts** — fix the code, never weaken a test.",
        "- **Tests are contracts** — and in THIS repo, also run `make lint`.",
    )
    for root in (
        _write_agents(tmp_path / "edited-agents", edited),
        _write_claude(tmp_path / "edited-claude", edited),
    ):
        result = ar.check(root)
        assert result["status"] == ar.STATUS_STALE_MODIFIED, root.name
        assert result["repairable"] is False


def test_owner_rewritten_anchor_carrying_every_load_bearing_sentence_grades_ok(tmp_path: Path):
    """Substance-based detection has to accept a correct anchor it did not write.

    A revision tag would call this stale and offer to overwrite prose already
    doing the job — the wrong answer, and the reason the probe asks what the
    anchor SAYS rather than which version it is.
    """
    root = _write_agents(tmp_path / "homegrown", _HOME_GROWN)
    assert ar.check(root)["status"] == ar.STATUS_OK


def test_a_correct_home_grown_anchor_left_in_claude_md_is_the_owners_to_move(tmp_path: Path):
    """The new contract's sharpest edge, stated in the open: a home-grown anchor
    that says everything right but sits in CLAUDE.md used to grade `ok`. Now a
    host reading only AGENTS.md never sees it, and prawduct did not write it, so
    it is `stale-modified` with the move named — never moved for the owner."""
    root = _write_claude(tmp_path / "homegrown-claude", _HOME_GROWN)
    result = ar.check(root)
    assert result["status"] == ar.STATUS_STALE_MODIFIED
    assert result["repairable"] is False
    assert "move it to AGENTS.md" in result["detail"]


def test_owner_rewrite_carrying_only_the_notice_is_stale_modified_and_says_what_is_missing(
    tmp_path: Path,
):
    """Each load-bearing sentence is asked for separately, and the detail is
    DERIVED from which rows are missing — so an owner is told the one thing to
    add, and is not accused of predating a notice their anchor plainly carries.
    """
    notice_only = (
        "<!-- PRAWDUCT:ANCHOR — ours -->\n\n## Governance\n\n"
        f"If `/prawduct:*` is missing, run `{ar.NOTICE_PROBE}` first."
    )
    root = _write_agents(tmp_path / "notice-only", notice_only)
    result = ar.check(root)
    assert result["status"] == ar.STATUS_STALE_MODIFIED
    assert result["repairable"] is False
    assert "stage-keyed review rule" in result["detail"]
    assert "plugin-absent notice" not in result["detail"]


def test_a_shipped_stale_anchor_is_stale_even_when_the_file_names_the_command(tmp_path: Path):
    """The probe scans the whole file, so ORDER is what makes it honest.

    A repo can carry the install command far from the anchor while its anchor
    still carries the unconditional enforcement claim. Asked notice-first, that
    file grades healthy and the anchor goes on lying to every plugin-less clone.
    Asked archive-first, the verbatim shipped anchor settles it.
    """
    root = _write_agents(tmp_path / "elsewhere", ar.ANCHOR_V2)
    path = root / "AGENTS.md"
    path.write_text(
        path.read_text(encoding="utf-8")
        + f"\n\n## Contributing\n\nNew here? Run `{ar.NOTICE_PROBE}`.\n",
        encoding="utf-8",
    )
    assert ar.check(root)["status"] == ar.STATUS_STALE


def test_a_file_sync_repo_is_declined_and_routed_to_migrate(tmp_path: Path):
    """The silent-migration case, and the reason it is graded rather than repaired.

    A pre-2.0 repo carries the heavy PRAWDUCT:BEGIN/END block and no sentinel, so
    every later check reads it as "no anchor" — and `absent` hands the file to
    the writer, which strips that block and reformats the prose around it. That
    is a migration, run silently, under a preview promising an insertion. It is
    `/prawduct:migrate`'s act and takes its own approval.
    """
    legacy = (
        "<!-- PRAWDUCT:BEGIN -->\n\n## Governance\n\nThe whole heavy block.\n\n"
        "<!-- PRAWDUCT:END -->"
    )
    root = _write_claude(tmp_path / "filesync", legacy)
    before = (root / "CLAUDE.md").read_bytes()

    result = ar.check(root)
    assert result["status"] == ar.STATUS_LEGACY_BLOCK
    assert result["repairable"] is False
    assert "/prawduct:migrate" in result["detail"]

    # And --apply must not perform the migration behind that verdict.
    assert ar.repair(root, apply=True)["applied"] is False
    assert (root / "CLAUDE.md").read_bytes() == before
    assert not (root / "AGENTS.md").exists()


def test_a_crlf_repo_is_repaired_without_reformatting_the_file(tmp_path: Path):
    """Line endings are bytes the owner chose, and the repair promises to keep them.

    Read through `read_text`, a CRLF file comes back LF and every line of it is
    rewritten on save — a whole-file diff from an operation that promised to
    touch one region. Matched LF-only, the same file matches no shipped anchor at
    all and is told its anchor was edited locally.
    """
    root = tmp_path / "crlf"
    root.mkdir()
    body = (_PRODUCT_HEAD + ar.ANCHOR_V5 + _PRODUCT_TAIL).replace("\n", "\r\n")
    (root / "CLAUDE.md").write_bytes(body.encode("utf-8"))

    assert ar.check(root)["status"] == ar.STATUS_LEGACY_LAYOUT
    assert ar.repair(root, apply=True)["applied"] is True

    raw = (root / "CLAUDE.md").read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "no bare LF may be introduced"
    expected = (_PRODUCT_HEAD + "@AGENTS.md\n" + _PRODUCT_TAIL).replace("\n", "\r\n")
    assert raw == expected.encode("utf-8")


@pytest.mark.parametrize("start", ["legacy-layout", "absent"])
def test_an_unwritable_repo_is_reported_not_raised(tmp_path: Path, start):
    """This command is offered BY doctor by name, so a failed write is a report.

    A traceback out of a health check is not a finding, it is a crash.
    Parametrized over both kinds of write, because guarding one was once the
    defect: the swap of a shipped anchor, and the insertion `absent` delegates.
    """
    if os.geteuid() == 0:
        pytest.skip("root writes into a mode-555 dir, so the fixture cannot refuse")
    anchor = ar.ANCHOR_V2 if start == "legacy-layout" else None
    root = _write_claude(tmp_path / f"readonly-{start}", anchor)
    root.chmod(0o555)  # the DIRECTORY: atomic_write_text needs to create a sibling
    try:
        result = ar.repair(root, apply=True)
    finally:
        root.chmod(0o755)
    assert result["applied"] is False
    assert result["status"] == ar.STATUS_UNWRITABLE
    assert "could not write" in result["detail"]


def test_no_instruction_files_is_absent(tmp_path: Path):
    root = tmp_path / "bare"
    root.mkdir()
    result = ar.check(root)
    assert result["status"] == ar.STATUS_ABSENT
    assert result["repairable"] is True


def test_claude_md_without_the_sentinel_is_absent(tmp_path: Path):
    root = _write_claude(tmp_path / "nosentinel", None)
    assert ar.check(root)["status"] == ar.STATUS_ABSENT


def test_an_anchored_agents_md_that_claude_md_does_not_import_is_import_missing(
    tmp_path: Path,
):
    """AGENTS.md is right and Claude Code still never reads it: a CLAUDE.md
    exists, so Claude does not fall back to AGENTS.md, and nothing imports it."""
    root = _write_agents(tmp_path / "noimport", STATIC_ANCHOR.strip())
    (root / "CLAUDE.md").write_text("# Product notes\n", encoding="utf-8")
    result = ar.check(root)
    assert result["status"] == ar.STATUS_IMPORT_MISSING
    assert result["repairable"] is True

    assert ar.repair(root, apply=True)["applied"] is True
    assert (root / "CLAUDE.md").read_text(encoding="utf-8") == (
        "@AGENTS.md\n\n# Product notes\n"
    )
    assert ar.check(root)["status"] == ar.STATUS_OK


def test_no_claude_md_beside_an_anchored_agents_md_is_import_missing(tmp_path: Path):
    """Recent Claude Code reads AGENTS.md when there is no CLAUDE.md, but the
    first `CLAUDE.local.md` or parent-directory `CLAUDE.md` silently ends that
    (#928 D-8) — so the import is owed even here."""
    root = _write_agents(tmp_path / "noclaude", STATIC_ANCHOR.strip())
    (root / "CLAUDE.md").unlink()
    assert ar.check(root)["status"] == ar.STATUS_IMPORT_MISSING


def test_a_shipped_anchor_left_in_claude_md_beside_agents_md_is_legacy_layout(tmp_path: Path):
    """A half-moved repo: AGENTS.md is current, and CLAUDE.md still carries the
    old copy, so Claude reads two anchors that disagree. The repair swaps the
    old copy for the import and adds no second anchor anywhere."""
    root = _write_agents(tmp_path / "half", STATIC_ANCHOR.strip())
    (root / "CLAUDE.md").write_text("# P\n\n" + ar.ANCHOR_V5, encoding="utf-8")
    assert ar.check(root)["status"] == ar.STATUS_LEGACY_LAYOUT
    ar.repair(root, apply=True)
    assert (root / "CLAUDE.md").read_text(encoding="utf-8") == "# P\n\n@AGENTS.md\n"
    assert (root / "AGENTS.md").read_text(encoding="utf-8").count(ar.ANCHOR_SENTINEL) == 1


@pytest.mark.parametrize("link", ["CLAUDE.md", "AGENTS.md"])
def test_one_file_behind_two_names_keeps_one_anchor_and_no_self_import(tmp_path: Path, link):
    """Both symlink directions are real layouts, and in both the two hosts read
    one file. The anchor belongs in it once, and `@AGENTS.md` written there
    would be the file importing itself — so the repair never writes one, and
    never replaces the symlink with a file."""
    root = tmp_path / f"one-{link}"
    root.mkdir()
    real = "AGENTS.md" if link == "CLAUDE.md" else "CLAUDE.md"
    (root / real).write_text("# Shared\n\n" + ar.ANCHOR_V5, encoding="utf-8")
    os.symlink(real, root / link)

    assert ar.check(root)["status"] == ar.STATUS_STALE
    assert ar.repair(root, apply=True)["applied"] is True
    assert (root / link).is_symlink()
    text = (root / real).read_text(encoding="utf-8")
    assert text == "# Shared\n\n" + STATIC_ANCHOR
    assert "@AGENTS.md" not in text
    assert ar.check(root)["status"] == ar.STATUS_OK


def test_undecodable_claude_md_is_ungraded_not_healthy(tmp_path: Path):
    """A check that could not run must not be indistinguishable from a clean one."""
    root = tmp_path / "binary"
    root.mkdir()
    (root / "CLAUDE.md").write_bytes(b"\xff\xfe\x00\x01 not utf-8 \xc3\x28")
    result = ar.check(root)
    assert result["status"] == ar.STATUS_UNREADABLE
    assert result["repairable"] is False
    assert "not decodable" in result["detail"]


def test_undecodable_agents_md_is_ungraded_not_healthy(tmp_path: Path):
    root = tmp_path / "binary-agents"
    root.mkdir()
    (root / "AGENTS.md").write_bytes(b"\xff\xfe\x00\x01")
    result = ar.check(root)
    assert result["status"] == ar.STATUS_UNREADABLE
    assert result["path"] == ar.AGENTS_REL


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a mode-000 file")
def test_an_unreadable_claude_md_names_its_cause_not_an_encoding(tmp_path: Path):
    """"Not decodable" sends the owner to fix an encoding; a permission problem
    is a different remedy, and doctor relays this detail verbatim."""
    root = tmp_path / "locked"
    root.mkdir()
    target = root / "CLAUDE.md"
    target.write_text("# Product\n", encoding="utf-8")
    target.chmod(0)
    try:
        result = ar.check(root)
    finally:
        target.chmod(0o644)
    assert result["status"] == ar.STATUS_UNREADABLE
    assert "could not be read" in result["detail"]
    assert "UTF-8" not in result["detail"]


# =============================================================================
# The repair
# =============================================================================


def test_dry_run_writes_nothing(tmp_path: Path):
    root = _write_claude(tmp_path / "dry", ar.ANCHOR_V2)
    before = (root / "CLAUDE.md").read_bytes()
    result = ar.repair(root, apply=False)
    assert result["applied"] is False
    assert result["replacement"] == STATIC_ANCHOR.strip()
    assert [w["path"] for w in result["writes"]] == ["AGENTS.md", "CLAUDE.md"]
    assert (root / "CLAUDE.md").read_bytes() == before
    assert not (root / "AGENTS.md").exists()


def test_repair_replaces_only_the_anchor_region(tmp_path: Path):
    """The test the missing END delimiter makes necessary.

    Everything outside the swapped anchor must be byte-identical — the product's
    title, its instructions, and the exact blank lines between them. A repair that
    guessed where the anchor ended would pass a "the import is present" assertion
    while having eaten the line below it.
    """
    root = _write_claude(tmp_path / "swap", ar.ANCHOR_V5)
    ar.repair(root, apply=True)
    text = (root / "CLAUDE.md").read_text(encoding="utf-8")
    assert text == _PRODUCT_HEAD + "@AGENTS.md\n" + _PRODUCT_TAIL
    assert (root / "AGENTS.md").read_text(encoding="utf-8") == STATIC_ANCHOR


def test_repair_keeps_an_existing_agents_md_byte_identical_above_the_block(tmp_path: Path):
    root = _write_claude(tmp_path / "own-agents", ar.ANCHOR_V5)
    mine = "# Codex notes\n\nRun `make check` before committing.\n"
    (root / "AGENTS.md").write_text(mine, encoding="utf-8")
    ar.repair(root, apply=True)
    text = (root / "AGENTS.md").read_text(encoding="utf-8")
    assert text == mine + "\n" + STATIC_ANCHOR


def test_repair_is_idempotent(tmp_path: Path):
    root = _write_claude(tmp_path / "twice", ar.ANCHOR_V2)
    ar.repair(root, apply=True)
    once = {p: (root / p).read_bytes() for p in ("AGENTS.md", "CLAUDE.md")}
    second = ar.repair(root, apply=True)
    assert second["status"] == ar.STATUS_OK
    assert second["applied"] is False
    assert {p: (root / p).read_bytes() for p in once} == once


def test_repair_declines_an_owner_edited_anchor(tmp_path: Path):
    edited = ar.ANCHOR_V2.replace(
        "**Enforcement is structural:**", "**Enforcement (ours, and we mean it):**"
    )
    root = _write_claude(tmp_path / "declined", edited)
    before = (root / "CLAUDE.md").read_bytes()
    result = ar.repair(root, apply=True)
    assert result["applied"] is False
    assert (root / "CLAUDE.md").read_bytes() == before
    assert not (root / "AGENTS.md").exists()


def test_inserting_into_a_crlf_file_does_not_mix_endings(tmp_path: Path):
    """The `absent` path had the CRLF defect the swap was fixed for: the anchor
    and the import are LF-only, so splicing them into a CRLF file handed back a
    mixed-ending document — a whole-file diff dressed as a one-line edit."""
    root = tmp_path / "crlf-insert"
    root.mkdir()
    for name in ("CLAUDE.md", "AGENTS.md"):
        (root / name).write_bytes(
            (_PRODUCT_HEAD + "## Mine\n\nkeep me\n").replace("\n", "\r\n").encode("utf-8")
        )
    assert ar.repair(root, apply=True)["applied"] is True

    for name in ("CLAUDE.md", "AGENTS.md"):
        raw = (root / name).read_bytes()
        assert raw.count(b"\n") == raw.count(b"\r\n"), f"bare LF introduced in {name}"
        assert b"keep me" in raw
    assert ar.NOTICE_PROBE.encode() in (root / "AGENTS.md").read_bytes()
    assert (root / "CLAUDE.md").read_bytes().startswith(b"@AGENTS.md\r\n")


def test_absent_anchor_is_inserted_through_the_one_writer(tmp_path: Path):
    """`absent` delegates to `apply_governance_anchor` rather than writing again.

    Two writers would be two opinions about where an anchor goes in a document,
    and they would disagree the first time either moved.
    """
    root = _write_claude(tmp_path / "insert", None)
    result = ar.repair(root, apply=True)
    assert result["applied"] is True
    assert ar.NOTICE_PROBE in (root / "AGENTS.md").read_text(encoding="utf-8")
    claude = (root / "CLAUDE.md").read_text(encoding="utf-8")
    assert claude.startswith("@AGENTS.md\n\n")
    assert "Don't touch this product instruction." in claude


# =============================================================================
# The archive, and the CLI contract
# =============================================================================


@pytest.mark.parametrize("index", range(len(ar.SUPERSEDED_ANCHORS)))
def test_every_archived_anchor_is_repairable_where_it_can_sit(tmp_path: Path, index):
    """Each entry in the archive must actually be reachable as a repairable grade.

    An entry nobody exercises is indistinguishable from an entry that is subtly
    wrong — and being subtly wrong here does not fail, it reports `stale-modified`
    and tells the owner they edited an anchor prawduct wrote. Parametrized over
    the archive ITSELF so a newly appended entry is covered by existing tests
    rather than by remembering to add one.

    Renegotiated when the anchor moved to AGENTS.md: a shipped anchor in
    CLAUDE.md (where every one of them was written) is `legacy-layout` and
    moves; the same text in AGENTS.md is `stale` and is swapped in place.
    """
    anchor = ar.SUPERSEDED_ANCHORS[index]

    in_claude = _write_claude(tmp_path / f"claude-{index}", anchor)
    assert ar.check(in_claude)["status"] == ar.STATUS_LEGACY_LAYOUT
    ar.repair(in_claude, apply=True)
    tail = "\n" if anchor.endswith("\n") else ""
    assert (in_claude / "CLAUDE.md").read_text(encoding="utf-8") == (
        _PRODUCT_HEAD + "@AGENTS.md" + tail + _PRODUCT_TAIL
    )
    assert (in_claude / "AGENTS.md").read_text(encoding="utf-8") == STATIC_ANCHOR
    assert ar.check(in_claude)["status"] == ar.STATUS_OK

    in_agents = _write_agents(tmp_path / f"agents-{index}", anchor)
    assert ar.check(in_agents)["status"] == ar.STATUS_STALE
    ar.repair(in_agents, apply=True)
    assert (in_agents / "AGENTS.md").read_text(encoding="utf-8") == (
        _PRODUCT_HEAD + STATIC_ANCHOR.rstrip("\n") + tail + _PRODUCT_TAIL
    )
    assert ar.check(in_agents)["status"] == ar.STATUS_OK


def test_the_tag_reader_can_render_the_anchor_this_tree_ships():
    """The reader must handle TODAY's anchor, or the guard fails at the next tag.

    `test_the_archive_covers_every_anchor_prawduct_ever_shipped` walks release
    tags, and no tag yet carries this branch's `STATIC_ANCHOR` — so a reader that
    cannot render it is green right up until the release that ships it, and then
    goes red pointing at the reader rather than at the anchor. That is exactly
    what the first version did: it resolved f-string interpolations from
    module-level `ast.Constant` assignments only, and `PLUGIN_ID` is assigned
    from a `next(iter(...))` call.

    Pinning it against the working tree is what closes the gap between "the guard
    passes" and "the guard can see".
    """
    src = (_PLUGIN_ROOT / "lib" / "migrate_plugin.py").read_text(encoding="utf-8")
    rendered = _render_anchor(src, "HEAD")
    assert rendered == STATIC_ANCHOR.strip(), (
        "the tag reader cannot render the anchor this tree defines, so the archive "
        "guard would go red at the first release cut from here"
    )


def test_the_archive_covers_every_anchor_prawduct_ever_shipped():
    """Derive the shipped set from the release tags — never from memory.

    This is the guard for the way the archive was first written: from "the anchor
    I just replaced" rather than from what shipped, which covered v2.3.0+ and
    missed the 31 releases before it. `test_the_current_anchor_is_never_listed_as_\
    superseded` guards the opposite direction and structurally cannot see an
    omission, because an entry that is absent is absent from both sides.

    Renders each tag's `STATIC_ANCHOR` by parsing, never by executing: the module
    imports siblings that a historical tree may not satisfy, and importing old
    revisions of the code under test to test the current one is its own trap.
    """
    tags = _release_tags()
    if not tags:
        pytest.skip("no release tags reachable (shallow clone or fresh fork)")

    known = {a.strip() for a in ar.SUPERSEDED_ANCHORS} | {STATIC_ANCHOR.strip()}
    missing: dict[str, str] = {}
    unresolved: list[str] = []
    for tag in tags:
        shipped = _shipped_anchor(tag)
        if shipped is _NO_MODULE:
            continue  # predates migrate_plugin.py; there was no anchor to ship
        if shipped is None:
            unresolved.append(tag)
        elif shipped not in known:
            missing.setdefault(shipped, tag)

    # A tag whose anchor could not be rendered is skipped by the loop, and a loop
    # that skipped every tag would pass having checked nothing. Assert the reader
    # still works before trusting what it did not find: `_shipped_anchor` resolves
    # only the f-string shape the anchor has always had, so a future anchor that
    # interpolates something else would silently empty this guard rather than
    # fail it. Every tag carrying the module must resolve.
    assert not unresolved, (
        f"could not render STATIC_ANCHOR for {unresolved} — the guard skips what it "
        "cannot read, so this is the guard going blind, not the tags being fine. "
        "Teach `_shipped_anchor` the new shape before trusting a green run here"
    )

    assert not missing, (
        "these anchors shipped in a release and are in neither SUPERSEDED_ANCHORS "
        "nor the current STATIC_ANCHOR, so every repo onboarded on them is graded "
        f"`stale-modified` and refused a repair: {sorted(missing.values())}"
    )


def test_the_current_anchor_is_never_listed_as_superseded(tmp_path: Path):
    """`SUPERSEDED_ANCHORS` is history; the current anchor is not history.

    Listing it would make a healthy repo eligible for a swap of the anchor for
    itself — harmless today, and exactly the entry someone would add by reflex
    when the next revision lands instead of appending beside it.
    """
    assert STATIC_ANCHOR.strip() not in ar.SUPERSEDED_ANCHORS
    # No second assertion that an archived anchor must LACK the notice. It was
    # true only while `check` asked the notice probe first, and this bundle
    # reversed that ordering — the archive is now consulted before the probe, so a
    # superseded anchor carrying the notice is still reachable as `stale`. Left in
    # place it would have closed the archive structurally: every anchor from here
    # on carries the notice, so the day one of them is superseded, the sibling
    # tag guard demands the append and this assertion forbids it.


class TestCommand:
    """The chunk names `plugin/bin/prawduct-hook` as a deliverable, so the command
    is driven rather than only its lib.

    Ported from `test_norm_index_scaffold.py::TestCommand`, which is the precedent
    this module cites — and whose own docstring records that testing the lib alone
    left the formatter, `--json` and both exit-code mappings executing in no test
    at all. Citing that precedent while not copying its test file is the active
    learnings rule "When you cite a precedent, COPY ITS TEST FILE FIRST", and this
    module re-instanced it: `_run` drove the binary four times and read only
    `returncode`.

    **The confirmation block is the load-bearing part.** `security-model.md`
    § Direction requires one informed approval naming the blast radius before a
    repair rewrites a file the framework did not author. That approval IS this
    stdout. Untested, it could be dropped or truncated and ship green.
    """

    def test_the_human_dry_run_prints_every_write_in_full(self, tmp_path: Path):
        """Renegotiated when the repair began writing two files: the preview
        names each file, what happens to it, and its exact text."""
        root = _write_claude(tmp_path / "cmd-preview", ar.ANCHOR_V2)
        result = _run(root)
        assert result.returncode == 0
        assert "dry-run" in result.stdout
        assert "Would create: AGENTS.md" in result.stdout
        assert "Would replace the shipped anchor in place: CLAUDE.md" in result.stdout
        assert "    | @AGENTS.md" in result.stdout
        # The entire anchor, not a summary of it — an approval given for text the
        # owner has not seen is not informed.
        for line in STATIC_ANCHOR.strip().split("\n"):
            assert f"| {line}" in result.stdout, f"preview omits: {line!r}"

    def test_the_absent_preview_says_add_not_replace(self, tmp_path: Path):
        root = _write_claude(tmp_path / "cmd-insert", None)
        result = _run(root)
        assert "Would add at the top: CLAUDE.md" in result.stdout
        assert "Would create: AGENTS.md" in result.stdout
        assert "replace" not in result.stdout

    def test_a_declined_status_prints_no_offer(self, tmp_path: Path):
        """`legacy-block` must not print a preview it will refuse to apply."""
        legacy = "<!-- PRAWDUCT:BEGIN -->\n\nheavy\n\n<!-- PRAWDUCT:END -->"
        root = _write_claude(tmp_path / "cmd-legacy", legacy)
        result = _run(root)
        assert result.returncode == 0
        assert ar.STATUS_LEGACY_BLOCK in result.stdout
        assert "/prawduct:migrate" in result.stdout
        assert "Would " not in result.stdout, "an offer that cannot be honoured is worse than none"

    @pytest.mark.parametrize(
        ("start", "anchor", "was"),
        [
            ("legacy-layout", ar.ANCHOR_V2, ar.STATUS_LEGACY_LAYOUT),
            ("absent", None, ar.STATUS_ABSENT),
        ],
    )
    def test_apply_reports_the_write_not_the_defect_it_fixed(
        self, tmp_path: Path, start, anchor, was
    ):
        """The success report, which `--apply` got wrong for a whole review round.

        `repair` starts from `check`'s dict, so a successful write kept returning
        the graded defect — only `applied` distinguished success from refusal, and
        the CLI's confirmation block is gated on `not applied`, so it printed the
        defect and stopped.

        **Parametrized over both write branches, because pinning one was the
        follow-up defect.** `repair` writes in two places — the swap and the
        `absent` delegation — and a first cut asserted only the swap, so deleting
        the `absent` branch's two success lines shipped green. That branch is the
        one Health Check #4 advertises as repairable, so a doctor session that
        inserted a missing anchor would have read the defect back and graded the
        repo degraded immediately after fixing it. `test_an_unwritable_claude_md_\
        is_reported_not_raised` is parametrized for this same reason, one round
        earlier, on these same two branches.
        """
        root = _write_claude(tmp_path / f"cmd-apply-{start}", anchor)
        assert ar.check(root)["status"] == was, "fixture must actually start from the defect"

        result = _run(root, "--apply")
        assert result.returncode == 0
        assert was not in result.stdout, (
            "a repair that worked must not report the condition it repaired"
        )
        assert f"reanchor (apply): {ar.STATUS_OK}" in result.stdout

    def test_json_publishes_the_documented_key_set(self, tmp_path: Path):
        """`api-contract.md` publishes these keys; nothing executed this branch."""
        root = _write_claude(tmp_path / "cmd-json", ar.ANCHOR_V2)
        result = _run(root, "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert set(data) >= {
            "status", "path", "repairable", "detail", "applied", "replacement", "writes",
        }
        assert data["status"] == ar.STATUS_LEGACY_LAYOUT
        assert data["applied"] is False
        assert data["replacement"] == STATIC_ANCHOR.strip()
        assert [w["path"] for w in data["writes"]] == ["AGENTS.md", "CLAUDE.md"]

    def test_json_after_apply_reports_ok(self, tmp_path: Path):
        root = _write_claude(tmp_path / "cmd-json-apply", ar.ANCHOR_V2)
        data = json.loads(_run(root, "--apply", "--json").stdout)
        assert data["status"] == ar.STATUS_OK and data["applied"] is True


@pytest.mark.parametrize(
    ("case", "anchor", "args", "expected"),
    [
        ("current-dry", STATIC_ANCHOR.strip(), (), 0),      # graded ok
        ("stale-dry", ar.ANCHOR_V2, (), 0),                # a finding is not a failure
        ("stale-apply", ar.ANCHOR_V2, ("--apply",), 0),    # wrote
        ("current-apply", STATIC_ANCHOR.strip(), ("--apply",), 0),  # idempotent no-op
    ],
)
def test_exit_codes_for_graded_runs(tmp_path: Path, case, anchor, args, expected):
    write = _write_agents if case.startswith("current") else _write_claude
    root = write(tmp_path / case, anchor)
    assert _run(root, *args).returncode == expected


def test_unreadable_exits_one_on_a_dry_run(tmp_path: Path):
    """Could-not-run is 1 even though a dry run is otherwise advisory."""
    root = tmp_path / "binexit"
    root.mkdir()
    (root / "CLAUDE.md").write_bytes(b"\xff\xfe\x00\x01")
    assert _run(root).returncode == 1


def test_apply_exits_one_when_it_refuses(tmp_path: Path):
    """`--apply` is a writer: refusing to write is a failed write, not a report."""
    edited = ar.ANCHOR_V2.replace("Skipping it is the #1 governance failure.", "Skip freely.")
    root = _write_claude(tmp_path / "refuse", edited)
    assert _run(root, "--apply").returncode == 1


def test_unknown_flag_is_two(tmp_path: Path):
    root = _write_agents(tmp_path / "badflag", STATIC_ANCHOR.strip())
    assert _run(root, "--nope").returncode == 2


# =============================================================================
# The layout writer (`migrate_plugin.apply_governance_anchor`)
# =============================================================================

from lib import migrate_plugin as mp  # noqa: E402

#: Every starting layout the writer meets in a real repo, as {file: text}.
_LAYOUTS = {
    "empty": {},
    "claude-product-only": {"CLAUDE.md": "# P\n\nmine\n"},
    "agents-product-only": {"AGENTS.md": "# Codex\n\nmine\n"},
    "both-product": {"CLAUDE.md": "# P\n", "AGENTS.md": "# Codex\n"},
    "shipped-anchor-in-claude": {"CLAUDE.md": "# P\n\n" + ar.ANCHOR_V5},
    "pre-2.0-block": {"CLAUDE.md": "# P\n\n<!-- PRAWDUCT:BEGIN -->\nheavy\n<!-- PRAWDUCT:END -->\n"},
    "current-layout": {"AGENTS.md": STATIC_ANCHOR, "CLAUDE.md": "@AGENTS.md\n"},
    # Someone copied CLAUDE.md to AGENTS.md before onboarding: both carry the
    # shipped anchor. The preview once disagreed with the writer on exactly this.
    "claude-copied-to-agents": {"AGENTS.md": "# P\n\n" + ar.ANCHOR_V5, "CLAUDE.md": "# P\n\n" + ar.ANCHOR_V5},
}


@pytest.mark.parametrize("layout", sorted(_LAYOUTS))
def test_the_dry_run_plan_names_exactly_what_apply_changes(tmp_path: Path, layout):
    """The preview is what the operator's single confirmation is given against,
    so a file it omits is an unannounced edit and a file it adds is a false one.
    Asserted against the writer itself, over every starting layout."""
    root = tmp_path / layout
    root.mkdir()
    for name, text in _LAYOUTS[layout].items():
        (root / name).write_text(text, encoding="utf-8")
    plan = mp.plan_governance_anchor(root)
    assert mp.governance_anchor_pending(root) == plan.paths
    executed = mp.apply_governance_anchor(root)
    assert executed == plan, "the writer must execute the plan the preview printed"
    for write in plan.writes:
        assert (root / write.path).read_text(encoding="utf-8") == write.content, write.path
    assert mp.apply_governance_anchor(root).writes == (), "a second run must change nothing"
    assert mp.governance_anchor_pending(root) == []


def test_a_symlink_pointing_elsewhere_is_never_written_through(tmp_path: Path):
    """An AGENTS.md linked to a file outside the pair is the owner's arrangement:
    writing through it would edit a file this repo may not own, and replacing it
    would break the link."""
    root = tmp_path / "foreign"
    root.mkdir()
    shared = tmp_path / "shared-rules.md"
    shared.write_text("# Org-wide rules\n", encoding="utf-8")
    os.symlink(shared, root / "AGENTS.md")

    mp.apply_governance_anchor(root)
    assert (root / "AGENTS.md").is_symlink()
    assert shared.read_text(encoding="utf-8") == "# Org-wide rules\n"
    result = ar.check(root)
    assert result["status"] == ar.STATUS_ABSENT
    assert result["repairable"] is False, "an offer the writer will not honour is worse than none"


@pytest.mark.parametrize("link", ["outside", "dangling"])
@pytest.mark.parametrize("via", ["repair", "migrate-writer"])
def test_a_shipped_claude_anchor_is_never_deleted_when_agents_md_cannot_take_it(
    tmp_path: Path, link, via
):
    """The CLAUDE.md side of the layout only REMOVES text, so it may act only
    when the anchor has somewhere to go. An AGENTS.md linked outside the pair,
    or dangling, is never written through — so swapping CLAUDE.md's anchor for
    the import there would delete the anchor and put it nowhere, while the
    report said "moved". Every surface that can drive the swap is asked."""
    root = _write_claude(tmp_path / f"{link}-{via}", ar.ANCHOR_V5)
    target = tmp_path / f"shared-{link}-{via}.md"
    if link == "outside":
        target.write_text("# Org-wide rules\n", encoding="utf-8")
    os.symlink(target, root / "AGENTS.md")
    before = (root / "CLAUDE.md").read_bytes()

    graded = ar.check(root)
    assert graded["status"] == ar.STATUS_LEGACY_LAYOUT
    assert graded["repairable"] is False, "an offer the writer will not honour is worse than none"
    assert mp.governance_anchor_pending(root) == [], "the preview must not announce a loss"

    if via == "repair":
        assert ar.repair(root, apply=True)["applied"] is False
    else:
        executed = mp.apply_governance_anchor(root)
        assert executed.writes == ()
        assert executed.unplaced and "symlink" in executed.unplaced
    assert (root / "CLAUDE.md").read_bytes() == before, "the anchor must survive"
    assert (root / "AGENTS.md").is_symlink()


def test_an_outside_link_that_already_carries_the_anchor_takes_the_import(tmp_path: Path):
    """The control for the guard above: when the linked file already holds the
    anchor, the anchor has a home, and CLAUDE.md's old copy can give way."""
    root = _write_claude(tmp_path / "linked-anchored", ar.ANCHOR_V5)
    target = tmp_path / "shared-anchored.md"
    target.write_text(STATIC_ANCHOR, encoding="utf-8")
    os.symlink(target, root / "AGENTS.md")
    assert mp.apply_governance_anchor(root).paths == ["CLAUDE.md"]
    assert "@AGENTS.md" in (root / "CLAUDE.md").read_text(encoding="utf-8")
    assert target.read_text(encoding="utf-8") == STATIC_ANCHOR


def test_the_stale_preview_names_the_import_the_apply_will_add(tmp_path: Path):
    """A stale anchor in AGENTS.md is swapped in place, and the layout writer
    that runs after it adds CLAUDE.md's import. Both are edits, and the preview
    is what the owner's single confirmation covers, so both are listed."""
    root = tmp_path / "stale-noimport"
    root.mkdir()
    (root / "AGENTS.md").write_text("# A\n\n" + ar.ANCHOR_V5, encoding="utf-8")
    (root / "CLAUDE.md").write_text("# Mine\n", encoding="utf-8")
    result = ar.repair(root, apply=False)
    assert result["status"] == ar.STATUS_STALE
    assert [w["path"] for w in result["writes"]] == ["AGENTS.md", "CLAUDE.md"]
    ar.repair(root, apply=True)
    assert (root / "CLAUDE.md").read_text(encoding="utf-8") == "@AGENTS.md\n\n# Mine\n"



def test_a_claude_md_linked_outside_is_never_reported_repaired(tmp_path: Path):
    """With CLAUDE.md a symlink out of the repo, prawduct cannot add the import
    there, so the repair is not offered — and a repair that could not reach the
    healthy layout is never reported as `ok`."""
    root = tmp_path / "claude-linked"
    root.mkdir()
    target = tmp_path / "shared-claude.md"
    target.write_text("# Shared\n\n" + ar.ANCHOR_V5, encoding="utf-8")
    os.symlink(target, root / "CLAUDE.md")

    graded = ar.check(root)
    assert graded["status"] == ar.STATUS_LEGACY_LAYOUT
    assert graded["repairable"] is False
    assert "symlink" in graded["detail"]
    result = ar.repair(root, apply=True)
    assert result["applied"] is False
    assert result["status"] != ar.STATUS_OK
    assert target.read_text(encoding="utf-8") == "# Shared\n\n" + ar.ANCHOR_V5


@pytest.mark.parametrize("kind", ["directory", "not-utf8"])
def test_an_unreadable_agents_md_stops_the_writer_without_a_crash(tmp_path: Path, kind):
    """The writer reads a product's AGENTS.md before deciding anything; one it
    cannot read is reported as the reason the anchor was not placed, never as a
    traceback out of onboarding or migration."""
    root = tmp_path / f"unreadable-{kind}"
    root.mkdir()
    (root / "CLAUDE.md").write_text("# P\n\n" + ar.ANCHOR_V5, encoding="utf-8")
    if kind == "directory":
        (root / "AGENTS.md").mkdir()
    else:
        (root / "AGENTS.md").write_bytes(b"\xff\xfe not utf-8")
    before = (root / "CLAUDE.md").read_bytes()
    plan = mp.apply_governance_anchor(root)
    assert plan.writes == () and plan.unplaced and "AGENTS.md" in plan.unplaced
    assert (root / "CLAUDE.md").read_bytes() == before


def test_init_says_so_when_the_anchor_cannot_be_placed(tmp_path: Path):
    """Onboarding writes the rest of the scaffold but does not stay silent about
    an anchor it could not place (AGENTS.md linked outside the repo)."""
    from lib.init_product import init_product

    root = tmp_path / "init-linked"
    root.mkdir()
    shared = tmp_path / "org.md"
    shared.write_text("# Org\n", encoding="utf-8")
    os.symlink(shared, root / "AGENTS.md")
    result = init_product(root, "demo", apply=True)
    assert any("anchor not placed" in w for w in result["warnings"]), result["warnings"]
    assert shared.read_text(encoding="utf-8") == "# Org\n"


def test_an_ordinary_init_has_no_anchor_warning(tmp_path: Path):
    from lib.init_product import init_product

    root = tmp_path / "init-plain"
    root.mkdir()
    result = init_product(root, "demo", apply=True)
    assert not any("anchor not placed" in w for w in result["warnings"])


def test_a_write_that_does_not_finish_the_layout_is_reported_as_what_remains(
    tmp_path: Path, monkeypatch
):
    """`repair` re-grades after writing and reports that grade, never a blanket
    `ok`. Pinned by making the writer achieve nothing: the report must still say
    the layout is unfinished."""
    root = _write_claude(tmp_path / "noop-writer", ar.ANCHOR_V5)
    monkeypatch.setattr(ar, "apply_governance_anchor", lambda _pd: None)
    result = ar.repair(root, apply=True)
    assert result["applied"] is True
    assert result["status"] == ar.STATUS_LEGACY_LAYOUT
