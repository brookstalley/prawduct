"""Tests for the stale-anchor detector and its offered repair (`prawduct-hook reanchor`).

The defect being closed is silent by construction: ``apply_claude_anchor`` returns
as soon as it sees the sentinel, so a repo carrying an anchor prawduct shipped two
revisions ago is byte-indistinguishable, to every other code path, from one
carrying the current text. Nothing failed; new onboards got the fix and the whole
already-onboarded fleet did not.

The load-bearing tests here are the **refusals**, not the repair. A repair that
rewrites a governance anchor is editing the product's own ``CLAUDE.md``, so the
ways it must decline — an owner-edited anchor, an undecodable file, a dry run —
are what keep it safe to offer at all; the happy path is one string swap. The
byte-preservation test is the sharpest of them: the anchor has no END delimiter,
so a repair that inferred where it stopped could eat the product's instructions,
and only a byte comparison of everything outside the swapped region can say it
did not.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

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

    Parses rather than executes, and resolves the f-string's interpolations from
    the same module's own string constants — which is the whole of what the anchor
    has ever interpolated. A shape this cannot resolve returns None rather than a
    wrong answer; the tag path moved (`lib/` -> `plugin/lib/`) at v2.3.0, so both
    are tried.
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

    try:
        tree = ast.parse(src)
    except SyntaxError:  # pragma: no cover — a tag that does not parse
        return None

    consts: dict[str, str] = {}
    joined: ast.JoinedStr | None = None
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            consts[target.id] = node.value.value
        elif target.id == "STATIC_ANCHOR" and isinstance(node.value, ast.JoinedStr):
            joined = node.value
    if joined is None:
        return None

    parts: list[str] = []
    for piece in joined.values:
        if isinstance(piece, ast.Constant):
            parts.append(piece.value)
        elif isinstance(piece, ast.FormattedValue) and isinstance(piece.value, ast.Name):
            if piece.value.id not in consts:
                return None
            parts.append(consts[piece.value.id])
        else:
            return None
    return "".join(parts).strip()


# =============================================================================
# Grading
# =============================================================================


def test_current_anchor_is_ok(tmp_path: Path):
    root = _write_claude(tmp_path / "current", STATIC_ANCHOR.strip())
    assert ar.check(root)["status"] == ar.STATUS_OK


def test_shipped_prior_anchor_is_stale_and_repairable(tmp_path: Path):
    root = _write_claude(tmp_path / "old", ar.ANCHOR_V2)
    result = ar.check(root)
    assert result["status"] == ar.STATUS_STALE
    assert result["repairable"] is True


def test_owner_edited_anchor_is_reported_not_repaired(tmp_path: Path):
    """The refusal that protects an owner who reworded their own anchor.

    Detection is by substance, so an anchor lacking the notice is not current —
    but replacement is exact-match, so one that matches nothing prawduct shipped
    is not prawduct's to rewrite. Grading these the same would either offer a
    repair that cannot run or refuse one that can.
    """
    edited = ar.ANCHOR_V2.replace(
        "- **Tests are contracts** — fix the code, never weaken a test.",
        "- **Tests are contracts** — and in THIS repo, also run `make lint`.",
    )
    root = _write_claude(tmp_path / "edited", edited)
    result = ar.check(root)
    assert result["status"] == ar.STATUS_STALE_MODIFIED
    assert result["repairable"] is False


def test_owner_written_equivalent_notice_grades_ok(tmp_path: Path):
    """Substance-based detection has to accept a correct anchor it did not write.

    A revision tag would call this stale and offer to overwrite prose that is
    already doing the job — the wrong answer, and the reason the probe asks what
    the anchor SAYS rather than which version it is.
    """
    home_grown = ar.ANCHOR_V2 + (
        "\n\nNote from us: if `/prawduct:*` is missing, run "
        f"`{ar.NOTICE_PROBE}` before doing anything else."
    )
    root = _write_claude(tmp_path / "homegrown", home_grown)
    assert ar.check(root)["status"] == ar.STATUS_OK


def test_no_claude_md_is_absent(tmp_path: Path):
    root = tmp_path / "bare"
    root.mkdir()
    result = ar.check(root)
    assert result["status"] == ar.STATUS_ABSENT
    assert result["repairable"] is True


def test_claude_md_without_the_sentinel_is_absent(tmp_path: Path):
    root = _write_claude(tmp_path / "nosentinel", None)
    assert ar.check(root)["status"] == ar.STATUS_ABSENT


def test_undecodable_claude_md_is_ungraded_not_healthy(tmp_path: Path):
    """A check that could not run must not be indistinguishable from a clean one."""
    root = tmp_path / "binary"
    root.mkdir()
    (root / "CLAUDE.md").write_bytes(b"\xff\xfe\x00\x01 not utf-8 \xc3\x28")
    result = ar.check(root)
    assert result["status"] == ar.STATUS_UNREADABLE
    assert result["repairable"] is False


# =============================================================================
# The repair
# =============================================================================


def test_dry_run_writes_nothing(tmp_path: Path):
    root = _write_claude(tmp_path / "dry", ar.ANCHOR_V2)
    before = (root / "CLAUDE.md").read_bytes()
    result = ar.repair(root, apply=False)
    assert result["applied"] is False
    assert result["replacement"] == STATIC_ANCHOR.strip()
    assert (root / "CLAUDE.md").read_bytes() == before


def test_repair_replaces_only_the_anchor_region(tmp_path: Path):
    """The test the missing END delimiter makes necessary.

    Everything outside the swapped anchor must be byte-identical — the product's
    title, its instructions, and the exact blank lines between them. A repair that
    guessed where the anchor ended would pass a "the notice is present" assertion
    while having eaten the line below it.
    """
    root = _write_claude(tmp_path / "swap", ar.ANCHOR_V2)
    ar.repair(root, apply=True)
    text = (root / "CLAUDE.md").read_text(encoding="utf-8")

    assert text.startswith(_PRODUCT_HEAD)
    assert text.endswith(_PRODUCT_TAIL)
    assert text == _PRODUCT_HEAD + STATIC_ANCHOR.strip() + _PRODUCT_TAIL
    assert ar.ANCHOR_V2 not in text


def test_repair_is_idempotent(tmp_path: Path):
    root = _write_claude(tmp_path / "twice", ar.ANCHOR_V2)
    ar.repair(root, apply=True)
    once = (root / "CLAUDE.md").read_bytes()
    second = ar.repair(root, apply=True)
    assert second["status"] == ar.STATUS_OK
    assert second["applied"] is False
    assert (root / "CLAUDE.md").read_bytes() == once


def test_repair_declines_an_owner_edited_anchor(tmp_path: Path):
    edited = ar.ANCHOR_V2.replace(
        "**Enforcement is structural:**", "**Enforcement (ours, and we mean it):**"
    )
    root = _write_claude(tmp_path / "declined", edited)
    before = (root / "CLAUDE.md").read_bytes()
    result = ar.repair(root, apply=True)
    assert result["applied"] is False
    assert (root / "CLAUDE.md").read_bytes() == before


def test_absent_anchor_is_inserted_through_the_one_inserter(tmp_path: Path):
    """`absent` delegates to `apply_claude_anchor` rather than inserting again.

    Two inserters would be two opinions about where an anchor goes in a document,
    and they would disagree the first time either moved.
    """
    root = _write_claude(tmp_path / "insert", None)
    result = ar.repair(root, apply=True)
    assert result["applied"] is True
    text = (root / "CLAUDE.md").read_text(encoding="utf-8")
    assert ar.NOTICE_PROBE in text
    assert "Don't touch this product instruction." in text


# =============================================================================
# The archive, and the CLI contract
# =============================================================================


@pytest.mark.parametrize("archived", ["ANCHOR_V1", "ANCHOR_V2"])
def test_every_archived_anchor_grades_stale_and_repairs(tmp_path: Path, archived):
    """Each entry in the archive must actually be reachable as `stale`.

    An entry nobody exercises is indistinguishable from an entry that is subtly
    wrong — and being subtly wrong here does not fail, it reports `stale-modified`
    and tells the owner they edited an anchor prawduct wrote. Parametrized over
    the archive so a newly appended entry is covered by existing tests rather than
    by remembering to add one.
    """
    anchor = getattr(ar, archived)
    root = _write_claude(tmp_path / f"archived-{archived}", anchor)
    assert ar.check(root)["status"] == ar.STATUS_STALE

    ar.repair(root, apply=True)
    text = (root / "CLAUDE.md").read_text(encoding="utf-8")
    assert text == _PRODUCT_HEAD + STATIC_ANCHOR.strip() + _PRODUCT_TAIL


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
    for old in ar.SUPERSEDED_ANCHORS:
        assert ar.NOTICE_PROBE not in old, (
            "a superseded anchor carrying the notice would grade `ok` and never "
            "be reachable as `stale`"
        )


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
    root = _write_claude(tmp_path / case, anchor)
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
    root = _write_claude(tmp_path / "badflag", STATIC_ANCHOR.strip())
    assert _run(root, "--nope").returncode == 2
