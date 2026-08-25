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
import json
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


def test_owner_rewritten_anchor_carrying_the_notice_grades_ok(tmp_path: Path):
    """Substance-based detection has to accept a correct anchor it did not write.

    A revision tag would call this stale and offer to overwrite prose already
    doing the job — the wrong answer, and the reason the probe asks what the
    anchor SAYS rather than which version it is.

    The fixture is an anchor the owner **rewrote**, which is what that sentence
    actually describes. An earlier version of this test used a verbatim shipped
    stale anchor with a note appended *elsewhere in the file*, and asserted `ok` —
    encoding the probe-ordering defect as the expected behaviour. That file's
    anchor still told a plugin-less session a Stop gate was watching; a note three
    paragraphs away does not unsay it, and the repair now swaps the shipped block
    and leaves the note alone.
    """
    home_grown = (
        "<!-- PRAWDUCT:ANCHOR — ours, kept deliberately short -->\n\n"
        "## Governance\n\n"
        "Prawduct governs this repo. If `/prawduct:*` is missing the plugin is not\n"
        f"installed and nothing here is enforced — run `{ar.NOTICE_PROBE}` first."
    )
    root = _write_claude(tmp_path / "homegrown", home_grown)
    assert ar.check(root)["status"] == ar.STATUS_OK


def test_a_shipped_stale_anchor_is_stale_even_when_the_file_names_the_command(tmp_path: Path):
    """The probe scans the whole file, so ORDER is what makes it honest.

    A repo can carry the install command far from the anchor — a contributing
    section, a troubleshooting note — while its anchor still carries the
    unconditional enforcement claim. Asked notice-first, that file grades healthy
    and the anchor goes on lying to every plugin-less clone. Asked
    archive-first, the verbatim shipped anchor settles it.
    """
    root = _write_claude(tmp_path / "elsewhere", ar.ANCHOR_V2)
    path = root / "CLAUDE.md"
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
    `apply_claude_anchor`, which strips that block and reformats the prose around
    it. That is a migration, run silently, under a preview promising an
    insertion. It is `/prawduct:migrate`'s act and takes its own approval.
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


def test_a_crlf_repo_is_repaired_without_reformatting_the_file(tmp_path: Path):
    """Line endings are bytes the owner chose, and the repair promises to keep them.

    Read through `read_text`, a CRLF file comes back LF and every line of it is
    rewritten on save — a whole-file diff from an operation that promised to touch
    one region. Matched LF-only, the same file matches no shipped anchor at all
    and is told its anchor was edited locally, which is the false accusation this
    module already made once.
    """
    root = tmp_path / "crlf"
    root.mkdir()
    body = (_PRODUCT_HEAD + ar.ANCHOR_V2 + _PRODUCT_TAIL).replace("\n", "\r\n")
    (root / "CLAUDE.md").write_bytes(body.encode("utf-8"))

    assert ar.check(root)["status"] == ar.STATUS_STALE
    assert ar.repair(root, apply=True)["applied"] is True

    raw = (root / "CLAUDE.md").read_bytes()
    assert b"\r\n" in raw, "the file's own endings must survive the repair"
    assert raw.count(b"\n") == raw.count(b"\r\n"), "no bare LF may be introduced"
    expected = (_PRODUCT_HEAD + STATIC_ANCHOR.strip() + _PRODUCT_TAIL).replace("\n", "\r\n")
    assert raw == expected.encode("utf-8")


@pytest.mark.parametrize("start", ["stale", "absent"])
def test_an_unwritable_claude_md_is_reported_not_raised(tmp_path: Path, start):
    """This command is offered BY doctor by name, so a failed write is a report.

    A traceback out of a health check is not a finding, it is a crash — and the
    two precedents this module copies both own their write failure explicitly.

    **Parametrized over BOTH writing branches, because guarding one was the
    defect.** `repair` writes in two places: the swap, and the `absent` branch
    that delegates to `apply_claude_anchor`. The first fix wrapped the swap only,
    and `absent` is the status Health Check #4 advertises as "the repair inserts
    one" — so the branch left raising was the advertised one, and a `stale`-only
    fixture could not see it.
    """
    anchor = ar.ANCHOR_V2 if start == "stale" else None
    root = _write_claude(tmp_path / f"readonly-{start}", anchor)
    root.chmod(0o555)  # the DIRECTORY: atomic_write_text needs to create a sibling
    try:
        result = ar.repair(root, apply=True)
    finally:
        root.chmod(0o755)
    assert result["applied"] is False
    assert result["status"] == ar.STATUS_UNWRITABLE
    assert "could not write" in result["detail"]


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


def test_inserting_into_a_crlf_file_does_not_mix_endings(tmp_path: Path):
    """The `absent` path had the CRLF defect the `stale` path was fixed for.

    Reading with `newline=""` keeps a CRLF document intact, but the anchor
    constant is LF-only — so the insert branch spliced LF lines into a CRLF file
    and handed back a mixed-ending document. A whole-file diff dressed as a
    one-block edit, and the same class the swap branch had already closed.
    """
    root = tmp_path / "crlf-insert"
    root.mkdir()
    (root / "CLAUDE.md").write_bytes(
        (_PRODUCT_HEAD + "## Mine\n\nkeep me\n").replace("\n", "\r\n").encode("utf-8")
    )
    assert ar.repair(root, apply=True)["applied"] is True

    raw = (root / "CLAUDE.md").read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "no bare LF may be introduced"
    assert ar.NOTICE_PROBE.encode() in raw
    assert b"keep me" in raw


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

    def test_the_human_dry_run_prints_the_whole_replacement(self, tmp_path: Path):
        root = _write_claude(tmp_path / "cmd-preview", ar.ANCHOR_V2)
        result = _run(root)
        assert result.returncode == 0
        assert "dry-run" in result.stdout
        assert "Would rewrite" in result.stdout
        # The entire anchor, not a summary of it — an approval given for text the
        # owner has not seen is not informed.
        for line in STATIC_ANCHOR.strip().split("\n"):
            assert f"| {line}" in result.stdout, f"preview omits: {line!r}"

    def test_the_absent_preview_says_insert_not_rewrite(self, tmp_path: Path):
        root = _write_claude(tmp_path / "cmd-insert", None)
        result = _run(root)
        assert "Would insert into" in result.stdout
        assert "Would rewrite" not in result.stdout

    def test_a_declined_status_prints_no_offer(self, tmp_path: Path):
        """`legacy-block` must not print a preview it will refuse to apply."""
        legacy = "<!-- PRAWDUCT:BEGIN -->\n\nheavy\n\n<!-- PRAWDUCT:END -->"
        root = _write_claude(tmp_path / "cmd-legacy", legacy)
        result = _run(root)
        assert result.returncode == 0
        assert ar.STATUS_LEGACY_BLOCK in result.stdout
        assert "/prawduct:migrate" in result.stdout
        assert "Would " not in result.stdout, "an offer that cannot be honoured is worse than none"

    def test_apply_reports_the_write_not_the_defect_it_fixed(self, tmp_path: Path):
        """The success report, which `--apply` got wrong for a whole review round.

        `repair` starts from `check`'s dict, so a successful write kept returning
        `stale` and the prose describing the lying anchor. Only `applied`
        distinguished success from refusal — and the CLI's confirmation block is
        gated on `not applied`, so it printed the defect and stopped.
        """
        root = _write_claude(tmp_path / "cmd-apply", ar.ANCHOR_V2)
        result = _run(root, "--apply")
        assert result.returncode == 0
        assert ar.STATUS_STALE not in result.stdout, (
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
            "status", "path", "repairable", "detail", "applied", "replacement",
        }
        assert data["status"] == ar.STATUS_STALE
        assert data["applied"] is False
        assert data["replacement"] == STATIC_ANCHOR.strip()

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
