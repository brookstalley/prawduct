"""The governance ledger records reviews, never their outcomes — and says so (#606).

#606 found a reader taking ``.prawduct/.governance-ledger.jsonl`` for the shared
audit trail: every finding raised, none discharged. Two facts make that reading
wrong, and both are queryable, so they are pinned here rather than left to prose:

* the ledger is a per-worktree, gitignored telemetry file (``core.GITIGNORE_ENTRIES``)
  — it is nobody's shared record, so mirroring outcomes into it would reach no
  one; and
* a finding's outcome is a ``resolution`` or ``disposition`` fact in the evidence
  store, where ``resolution`` travels between clones on ``refs/notes/prawduct``
  and ``disposition`` stays in the clone that wrote it
  (``evidence.TRANSPORTED_KINDS``).

The choice recorded in ``lib/ledger.py``'s docstring is to say so where the
ledger is described, and to name the command that shows an outcome. Each test
below fails when the code moves out from under that sentence.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_ROOT = _REPO / "plugin"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib import core, evidence, evidence_notes, ledger  # noqa: E402

HOOK = _ROOT / "bin" / "prawduct-hook"
LEDGER_REL = f".prawduct/{ledger.LEDGER_BASENAME}"
OUTCOME_COMMAND = "render-dispositions"
_OUTCOME_WORDS = ("resolution", "disposition")


def _outcome_kinds(roles: dict) -> list[str]:
    """Ledger kinds that would record a finding's outcome."""
    return sorted(k for k in roles if any(w in k for w in _OUTCOME_WORDS))


def _docstring_paragraph() -> str:
    """The one docstring paragraph that says where outcomes live."""
    doc = ledger.__doc__ or ""
    hits = [p for p in re.split(r"\n\s*\n", doc) if p.startswith("**Reviews, not their outcomes.**")]
    assert len(hits) == 1, f"expected one outcomes paragraph in lib/ledger.py's docstring, found {len(hits)}"
    return " ".join(hits[0].split())


def _paragraph_naming(text: str, needle: str) -> str:
    """The blank-line-delimited block holding the first ``needle``."""
    for block in re.split(r"\n\s*\n", text):
        if needle in block:
            return " ".join(block.split())
    raise AssertionError(f"{needle!r} not found")


def _line_naming(text: str, needle: str) -> str:
    lines = [line for line in text.splitlines() if needle in line]
    assert lines, f"{needle!r} not found"
    return lines[0]


class TestTheLedgerHoldsNoOutcomeKind:
    def test_no_ledger_kind_records_a_finding_outcome(self):
        """If this fails, outcomes now mirror into the ledger: the docstring's
        outcomes paragraph, and every description below, became false."""
        assert _outcome_kinds(ledger._EVENT_ROLES) == []

    def test_the_check_catches_a_mirrored_outcome_kind(self):
        """Control: the predicate above trips on the kind #606 proposed."""
        roles = {**ledger._EVENT_ROLES, "finding.resolution": "critic", "finding.disposition": "builder"}
        assert _outcome_kinds(roles) == ["finding.disposition", "finding.resolution"]

    def test_the_ledger_is_gitignored_and_never_committed_state(self):
        assert LEDGER_REL in core.GITIGNORE_ENTRIES
        committed = [p.path for p in core.V2_COMMITTED_PATHS]
        assert committed, "the committed-path set was empty — nothing was compared"
        assert not any(LEDGER_REL == p or (p.endswith("/") and LEDGER_REL.startswith(p)) for p in committed)


class TestTheDocstringSaysWhereOutcomesLive:
    def test_it_says_the_ledger_is_per_worktree_and_gitignored(self):
        para = _docstring_paragraph()
        assert "gitignored" in para and "per worktree" in para

    def test_it_names_the_transport_and_the_command(self):
        para = _docstring_paragraph()
        assert evidence_notes.NOTES_REF in para
        assert f"prawduct-hook {OUTCOME_COMMAND}" in para
        assert "evidence sync" in para

    def test_its_transport_claim_matches_the_transported_kinds(self):
        """The paragraph says resolutions travel and dispositions stay. If
        ``TRANSPORTED_KINDS`` changes, so must the sentence."""
        para = _docstring_paragraph()
        assert "resolution" in evidence.TRANSPORTED_KINDS
        assert "disposition" not in evidence.TRANSPORTED_KINDS
        assert "``disposition`` facts stay in the clone that wrote them" in para


class TestTheNamedCommandExists:
    def test_render_dispositions_is_dispatched(self, tmp_path):
        """The command the descriptions name is a real subcommand: a bad flag
        reaches its own usage line (exit 2), where an unknown command does not."""
        env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(tmp_path)}
        subprocess.run(["git", "init", "-q", str(tmp_path / "repo")], check=True, env=env)
        repo = tmp_path / "repo"

        def run(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                [sys.executable, str(HOOK), *args], cwd=repo, env={**env, "CLAUDE_PROJECT_DIR": str(repo)},
                capture_output=True, text=True,
            )

        known = run(OUTCOME_COMMAND, "--no-such-flag")
        assert known.returncode == 2, known.stderr
        assert f"prawduct-hook {OUTCOME_COMMAND} [--review" in known.stderr
        unknown = run(OUTCOME_COMMAND + "-no-such-command")
        assert f"prawduct-hook {OUTCOME_COMMAND} [--review" not in unknown.stderr


#: Every place the ledger is described to a reader, and the smallest span that
#: describes it. Each must say the ledger holds no outcomes by naming the
#: command that shows them.
_DESCRIPTIONS = (
    ("plugin/skills/critic/review-cycle.md", _paragraph_naming, "The ledger (`.prawduct/.governance-ledger.jsonl`, gitignored)"),
    ("plugin/docs/governance-telemetry.md", _paragraph_naming, "`.prawduct/.governance-ledger.jsonl` (gitignored)"),
    ("documentation/project-structure.md", _line_naming, ".governance-ledger.jsonl"),
    (".prawduct/artifacts/data-model.md", _paragraph_naming, "Append-only telemetry of governance events"),
)


class TestEveryDescriptionSaysSo:
    def test_each_description_names_the_outcome_command(self):
        missing = []
        for rel, span_of, anchor in _DESCRIPTIONS:
            span = span_of((_REPO / rel).read_text(encoding="utf-8"), anchor)
            if OUTCOME_COMMAND not in span or "outcome" not in span:
                missing.append(rel)
        assert missing == []
