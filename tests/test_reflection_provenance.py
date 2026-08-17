"""An archived reflection names the version that produced it.

Nothing in the reflection write path used to record a version, so grouping a
corpus by release could only be reconstructed after the fact — and every signal
available for that reconstruction is weak: `.prawduct/.prawduct-version` keeps
only the most recently seen value, `reflections.md` is gitignored so it has no
git history anywhere, and `learnings.md` is tracked in only some repos. The one
strong signal left is whatever ISO dates the prose happens to contain, which is
a minority of entries.

`.session-reflected` has no code write site — the agent appends prose to it
directly — so the stamp goes at its one code-owned write: the archive into
`reflections.md` at the session boundary. Stamping there covers the whole corpus
from a single statement.

The load-bearing constraint is what the stamp must NOT do. That archive carries a
failure contract earned twice over: explicit UTF-8 on every hop (a locale-codec
`UnicodeEncodeError` once tracebacked out of the SessionStart hook and took the
boundary with it), and `reflection_preserved` gating the delete below so a
reflection that could not be archived is KEPT rather than destroyed. A version
stamp must never become a new reason a reflection is lost — hence the degrade-to-
`unknown` cases here, which are the tests this module exists for.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib import change_log  # noqa: E402
from test_plugin_runtime import run_plugin_hook  # noqa: E402

# Load the extensionless hook in-process for the monkeypatched degradation
# cases. The module name is not "__main__", so its CLI dispatch does not run at
# import (same loader shape as test_hook_version.py).
_hook_loader = importlib.machinery.SourceFileLoader(
    "prawduct_hook_reflection_provenance", str(_ROOT / "bin" / "prawduct-hook")
)
_hook_spec = importlib.util.spec_from_loader(
    "prawduct_hook_reflection_provenance", _hook_loader
)
_hook = importlib.util.module_from_spec(_hook_spec)
_hook_loader.exec_module(_hook)

TAG_LINE_RE = re.compile(r"<!--\s*prawduct:\s*(.+?)\s*-->")

REFLECTION_TEXT = "reflection: the chunk went fine"


def _manifest_version() -> str:
    return json.loads(
        (_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )["version"]


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _seed(tmp_path: Path, reflection: str = REFLECTION_TEXT + "\n") -> Path:
    """A repo at a session boundary with a reflection waiting to be archived."""
    prawduct = tmp_path / ".prawduct"
    (prawduct / "artifacts").mkdir(parents=True)
    (prawduct / "project-state.yaml").write_text(
        "backlog_format_version: 2\n", encoding="utf-8"
    )
    (prawduct / "artifacts" / "project-preferences.md").write_text(
        "- **Language**: Python\n", encoding="utf-8"
    )
    (prawduct / ".session-reflected").write_text(reflection, encoding="utf-8")
    (prawduct / ".session-start").write_text("2026-08-01T06:00:00Z", encoding="utf-8")
    return prawduct


def _tags(line: str) -> dict[str, object]:
    """Parse a provenance line with the repo's OWN tag parser.

    Asserting through `lib.change_log` rather than a regex local to this module
    is the point: the header claims to be machine-parseable, and the cheapest
    proof of that claim is that the parser this project already ships reads it.
    """
    m = TAG_LINE_RE.search(line)
    assert m, f"not a prawduct tag line: {line!r}"
    return change_log.parse_tag_line(m.group(1))


# =============================================================================
# The stamp lands
# =============================================================================


class TestArchivedBlockCarriesProvenance:
    def test_boundary_writes_version_and_date_ahead_of_the_block(self, tmp_path):
        prawduct = _seed(tmp_path)
        res = run_plugin_hook("clear", tmp_path, "--session-start")
        assert res.returncode == 0, res.stderr

        archived = (prawduct / "reflections.md").read_text(encoding="utf-8")
        first = archived.splitlines()[0]
        tags = _tags(first)
        assert tags["version"] == _manifest_version()
        assert tags["archived"] == _today()
        assert REFLECTION_TEXT in archived, "the reflection itself must still land"

    def test_header_precedes_the_reflection_text(self, tmp_path):
        """Provenance ahead of the block it describes — a trailing line would
        attach to whichever block a reader scans next."""
        prawduct = _seed(tmp_path)
        assert run_plugin_hook("clear", tmp_path, "--session-start").returncode == 0
        archived = (prawduct / "reflections.md").read_text(encoding="utf-8")
        assert archived.index("<!-- prawduct:") < archived.index(REFLECTION_TEXT)

    def test_header_is_read_by_the_projects_own_tag_parser(self, tmp_path):
        """Machine-parseable, not merely machine-readable. Grouping the corpus by
        release is the whole reason the stamp exists, so the line reuses the tag
        idiom `lib/change_log.py` already parses instead of inventing prose."""
        prawduct = _seed(tmp_path)
        assert run_plugin_hook("clear", tmp_path, "--session-start").returncode == 0
        line = (prawduct / "reflections.md").read_text(encoding="utf-8").splitlines()[0]
        assert set(_tags(line)) == {"version", "archived"}

    def test_no_header_when_there_is_nothing_to_archive(self, tmp_path):
        """A whitespace-only reflection archives nothing, so it must not leave an
        orphan header labelling the NEXT session's block."""
        prawduct = _seed(tmp_path, reflection="   \n\n")
        assert run_plugin_hook("clear", tmp_path, "--session-start").returncode == 0
        log = prawduct / "reflections.md"
        assert not log.is_file() or "<!-- prawduct:" not in log.read_text(
            encoding="utf-8"
        )


class TestSeparatorContract:
    def test_second_archive_keeps_the_separator_and_stamps_its_own_block(
        self, tmp_path
    ):
        """Two blocks, one `---` between them, each with its own header. The
        separator is the existing contract; the header must sit inside a block,
        not replace or duplicate the rule."""
        prawduct = _seed(tmp_path)
        (prawduct / "reflections.md").write_text(
            "<!-- prawduct: version=0.0.1 | archived=2026-01-01 -->\n\n"
            "an earlier session's reflection\n",
            encoding="utf-8",
        )

        assert run_plugin_hook("clear", tmp_path, "--session-start").returncode == 0

        archived = (prawduct / "reflections.md").read_text(encoding="utf-8")
        assert archived.count("\n\n---\n\n") == 1, archived
        prior, new = archived.split("\n\n---\n\n")
        assert _tags(prior.splitlines()[0])["version"] == "0.0.1"
        assert _tags(new.splitlines()[0])["version"] == _manifest_version()
        assert "an earlier session's reflection" in prior
        assert REFLECTION_TEXT in new

    def test_first_archive_writes_no_leading_separator(self, tmp_path):
        prawduct = _seed(tmp_path)
        assert run_plugin_hook("clear", tmp_path, "--session-start").returncode == 0
        archived = (prawduct / "reflections.md").read_text(encoding="utf-8")
        assert archived.startswith("<!-- prawduct:"), archived
        assert "---" not in archived


# =============================================================================
# The stamp is never a reason a reflection is lost
# =============================================================================


class TestVersionResolutionDegradesHonestly:
    """Both cases run in-process so the version source can be broken directly.
    Each asserts the SAME two things: the reflection reaches the archive, and it
    is consumed afterwards — i.e. the boundary behaved exactly as it does when
    the version resolves."""

    def test_unresolvable_version_records_unknown(self, tmp_path, monkeypatch):
        """An omitted header would be indistinguishable from a block written
        before stamping existed, so the absence is recorded rather than implied."""
        prawduct = _seed(tmp_path)
        monkeypatch.setattr(_hook, "_plugin_manifest_version", lambda: None)

        _hook._boundary_close_session(tmp_path, prawduct)

        archived = (prawduct / "reflections.md").read_text(encoding="utf-8")
        tags = _tags(archived.splitlines()[0])
        assert tags["version"] == "unknown"
        assert tags["archived"] == _today(), "the date is still knowable — keep it"
        assert REFLECTION_TEXT in archived
        assert not (prawduct / ".session-reflected").is_file()

    def test_raising_version_source_does_not_break_the_boundary(
        self, tmp_path, monkeypatch
    ):
        """A raise here would escape the archive's `(UnicodeError, OSError)`
        handler and traceback the SessionStart hook — the failure shape that
        already cost one whole session boundary. The stamp must not reopen it."""
        prawduct = _seed(tmp_path)

        def _boom():
            raise RuntimeError("manifest exploded")

        monkeypatch.setattr(_hook, "_plugin_manifest_version", _boom)

        _hook._boundary_close_session(tmp_path, prawduct)

        archived = (prawduct / "reflections.md").read_text(encoding="utf-8")
        assert _tags(archived.splitlines()[0])["version"] == "unknown"
        assert REFLECTION_TEXT in archived
        assert not (prawduct / ".session-reflected").is_file()

    def test_header_helper_never_raises(self, monkeypatch):
        """The helper's contract stated directly, independent of the boundary."""
        monkeypatch.setattr(_hook, "_plugin_manifest_version", lambda: 1 / 0)
        assert "unknown" in _hook._reflection_provenance_header()


class TestPreservationOnFailureStillHolds:
    """The pre-existing contract, re-asserted against the stamped write path: an
    archive that fails keeps `.session-reflected` instead of deleting it. The
    stamp sits INSIDE that guard, so this is the test that proves it did not
    step outside."""

    def test_unarchivable_reflection_is_kept_and_announced(self, tmp_path):
        prawduct = _seed(tmp_path)
        # A directory where the archive file is expected -> OSError at open().
        (prawduct / "reflections.md").mkdir()

        res = run_plugin_hook("clear", tmp_path, "--session-start")
        assert res.returncode == 0, res.stderr
        assert (prawduct / ".session-reflected").is_file(), (
            "an un-archivable reflection must be KEPT, not destroyed"
        )
        assert "could not archive .session-reflected" in res.stderr

    def test_unresolvable_version_does_not_trigger_preservation(
        self, tmp_path, monkeypatch
    ):
        """The discriminating half of the pair above: `unknown` is a normal
        archive, not a failure. If a missing version started preserving the file
        the stamp would have become a new way to leave reflections behind."""
        prawduct = _seed(tmp_path)
        monkeypatch.setattr(_hook, "_plugin_manifest_version", lambda: None)

        _hook._boundary_close_session(tmp_path, prawduct)

        assert not (prawduct / ".session-reflected").is_file()
