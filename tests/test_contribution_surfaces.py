"""Where stats contribution shows itself: the session briefing and the janitor.

Both are silent at the default. The briefing line appears only when the owner
opted in, a collector is pinned and a report is waiting, and each of those
three is pinned by turning it off alone. The janitor's offer is prose an agent
follows, so its load-bearing clauses are pinned in the skill itself: it is
asked as a question, the answer is the person's, and `never` is written too.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import briefing, contribution  # noqa: E402
from test_contribution import NOW, _repo_with_store, _reviews  # noqa: E402


def _repo(tmp_path, row, facts=None):
    repo = _repo_with_store(tmp_path, _reviews(5) if facts is None else facts)
    if row is not None:
        prefs = repo / ".prawduct" / "artifacts"
        prefs.mkdir(parents=True, exist_ok=True)
        (prefs / "project-preferences.md").write_text(f"# Preferences\n\n{row}\n")
    return repo


@pytest.fixture
def pinned(monkeypatch):
    monkeypatch.setattr(contribution, "COLLECTOR_ENDPOINT", "https://collector.example/v1/report")


class TestBriefingLine:
    def test_ask_points_at_the_preview_and_the_persons_yes(self, tmp_path, pinned):
        line = contribution.briefing_line(_repo(tmp_path, "- **Stats contribution**: ask"), NOW)
        assert line.startswith("Stats: 1 anonymous report(s) ready")
        assert "--approve" in line and "only on their yes" in line

    def test_always_instructs_the_send(self, tmp_path, pinned):
        line = contribution.briefing_line(_repo(tmp_path, "- **Stats contribution**: always"), NOW)
        assert line.startswith("Stats: 1 anonymous report(s) ready")
        assert "run `prawduct-hook contribute --send` once, without asking" in line
        assert "--approve" not in line

    @pytest.mark.parametrize(
        "row", [None, "- **Stats contribution**: never", "- **Stats contribution**: (unset — reads as never)"]
    )
    def test_silent_without_an_opt_in(self, tmp_path, pinned, row):
        assert contribution.briefing_line(_repo(tmp_path, row), NOW) is None

    def test_a_misspelled_opt_in_is_named(self, tmp_path, monkeypatch):
        # Even with no collector pinned: the owner believes they opted in.
        monkeypatch.setattr(contribution, "COLLECTOR_ENDPOINT", "")
        line = contribution.briefing_line(_repo(tmp_path, "- **Stats contribution**: alwyas"), NOW)
        assert line.startswith("Stats: contribution is off") and "'alwyas'" in line

    def test_an_opted_in_product_whose_record_broke_is_told(self, tmp_path, pinned):
        repo = _repo(tmp_path, "- **Stats contribution**: always")
        contribution.sent_record_path(repo).write_text("{not json")
        line = contribution.briefing_line(repo, NOW)
        assert line.startswith("Stats: contribution is stuck") and "could not be read" in line

    def test_silent_without_a_pinned_collector(self, tmp_path, monkeypatch):
        monkeypatch.setattr(contribution, "COLLECTOR_ENDPOINT", "")
        assert contribution.briefing_line(_repo(tmp_path, "- **Stats contribution**: always"), NOW) is None

    def test_silent_with_nothing_waiting(self, tmp_path, pinned):
        repo = _repo(tmp_path, "- **Stats contribution**: always", facts=[])
        assert contribution.briefing_line(repo, NOW) is None

    def test_the_default_never_reads_the_store(self, tmp_path, pinned, monkeypatch):
        def refuse(project_dir):
            raise AssertionError("a product at the default paid for a store read")

        monkeypatch.setattr(contribution.evidence, "read_facts", refuse)
        assert contribution.briefing_line(_repo(tmp_path, None), NOW) is None

    def test_the_session_briefing_carries_the_line(self, tmp_path, pinned, monkeypatch):
        repo = _repo(tmp_path, "- **Stats contribution**: always")
        monkeypatch.setattr(contribution, "briefing_line", lambda project_dir: "Stats: sentinel line")
        assert "Stats: sentinel line" in briefing.assemble_session_briefing(repo, [])

    def test_a_failing_line_never_breaks_the_briefing(self, tmp_path, monkeypatch):
        repo = _repo(tmp_path, "- **Stats contribution**: always")

        def boom(project_dir):
            raise RuntimeError("store exploded")

        monkeypatch.setattr(contribution, "briefing_line", boom)
        assert "store exploded" not in briefing.assemble_session_briefing(repo, [])


class TestJanitorOffer:
    @pytest.fixture
    def offer(self):
        text = (_ROOT / "skills" / "janitor" / "SKILL.md").read_text(encoding="utf-8")
        start = text.index("**Stats contribution: an offer, asked once.**")
        return text[start : text.index("\n\n", start)]

    def test_it_is_asked_only_when_the_row_is_absent(self, offer):
        assert "has no `Stats contribution` row" in offer

    def test_it_is_a_question_and_the_answer_is_the_persons(self, offer):
        assert "ask the person, as a question" in offer
        assert "never pick for them" in offer
        assert "leave the row unwritten when no person answers" in offer

    def test_a_no_is_written_so_it_is_asked_once(self, offer):
        assert "`never` included, so the question is not asked again" in offer

    def test_it_never_grants_the_send(self):
        frontmatter = (_ROOT / "skills" / "janitor" / "SKILL.md").read_text(encoding="utf-8").split("---")[1]
        # A Bash grant is a prefix match: granting `contribute` would grant `contribute --send`.
        assert "contribute" not in frontmatter



def test_importing_the_module_does_not_load_the_network_stack():
    """The briefing imports this module for every product at session start, so
    a product at the default must not pay for urllib and TLS there."""
    import subprocess

    probe = (
        "import sys; sys.path.insert(0, %r)\n"
        "from lib import contribution, briefing\n"
        "heavy = [m for m in ('ssl', 'urllib.request', 'http.client') if m in sys.modules]\n"
        "print(','.join(heavy))"
    ) % str(_ROOT)
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == ""
