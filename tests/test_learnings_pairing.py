"""`learnings.md` / `learnings-detail.md` pairing, and the retirement refusal.

Two halves of one defect (#717). `_take_active_narrative` resolved a heading by
exact title and took the FIRST match, so two same-titled blocks meant a
retirement cut one and left its twin in the active section with no index entry
pointing at it — orphaned, in a file whose stated invariant is *never delete an
entry here*. Its docstring warned about a DRIFTED title and guarded that; a
DUPLICATED one was unguarded, and the two fail in opposite directions (drift
matches nothing and is a no-op; duplication matches twice and loses prose).

The check grades duplicates only. #717 also asked for counterpart and order
findings on the stated invariant that the files "mirror each other's headings in
the same order" — measured against the real corpus that invariant does not hold
and never did (270 active index entries vs 179 detail; detail headings are a
truncated prefix, not a copy). Grading it would fire ~117 findings on a corpus
nobody considers broken. The narrowing is deliberate and recorded, and
`test_this_repos_own_corpus_is_clean` is what keeps it honest.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_PLUGIN = str(Path(__file__).resolve().parent.parent / "plugin")
if _PLUGIN not in sys.path:
    sys.path.insert(0, _PLUGIN)

from lib import audit_learnings_cmd as al  # noqa: E402


def _corpus(tmp_path, index: str, detail: str | None = None) -> Path:
    d = tmp_path / ".prawduct"
    d.mkdir(parents=True, exist_ok=True)
    (d / "learnings.md").write_text(index, encoding="utf-8")
    if detail is not None:
        (d / "learnings-detail.md").write_text(detail, encoding="utf-8")
    return tmp_path


# --- the graded dimension ---------------------------------------------------

def test_a_duplicate_in_the_detail_file_is_reported(tmp_path):
    repo = _corpus(
        tmp_path,
        "# Learnings\n\n## Rule one\n\nbody\n",
        "# Detail\n\n## Rule one\n\nfirst\n\n## Rule one\n\nsecond\n",
    )

    result = al.check_learnings_pairing(repo)

    assert result["status"] == "findings"
    assert [f["kind"] for f in result["findings"]] == ["duplicate-heading"]
    assert result["findings"][0]["file"] == "learnings-detail.md"


def test_a_duplicate_in_the_index_is_reported(tmp_path):
    repo = _corpus(
        tmp_path,
        "# Learnings\n\n## Rule one\n\na\n\n## Rule one\n\nb\n",
        "# Detail\n\n## Rule one\n\nbody\n",
    )

    result = al.check_learnings_pairing(repo)

    assert result["findings"][0]["file"] == "learnings.md"


def test_a_clean_pair_produces_no_finding(tmp_path):
    repo = _corpus(
        tmp_path,
        "# Learnings\n\n## Rule one\n\na\n\n## Rule two\n\nb\n",
        "# Detail\n\n## Rule one\n\nx\n\n## Rule two\n\ny\n",
    )

    assert al.check_learnings_pairing(repo)["status"] == "ok"


def test_this_repos_own_corpus_is_clean(tmp_path):
    """The negative that keeps the narrowing honest.

    A check that fires on the corpus prawduct itself maintains would be noise,
    and noise is what trains a reader to skip the one real catch.
    """
    repo = Path(__file__).resolve().parent.parent
    if not (repo / ".prawduct" / "learnings.md").is_file():
        import pytest
        pytest.skip("no learnings corpus in this checkout")

    result = al.check_learnings_pairing(repo)

    assert result["status"] == "ok", result["reason"]


def test_an_archived_duplicate_is_not_a_finding(tmp_path):
    """Only the ACTIVE section pairs. Archived entries are deliberately absent
    from the index, so counting them would report drift for every correctly
    retired entry."""
    detail = (
        "# Detail\n\n## Rule one\n\nactive\n\n"
        f"{al._HISTORICAL_SECTION_HEADER}\n\n## Rule one\n\narchived\n"
    )
    repo = _corpus(tmp_path, "# Learnings\n\n## Rule one\n\na\n", detail)

    assert al.check_learnings_pairing(repo)["status"] == "ok"


# --- the measured, ungraded dimensions --------------------------------------

def test_a_missing_counterpart_is_counted_not_raised(tmp_path):
    """#717 asked for a finding here; the corpus says otherwise."""
    repo = _corpus(
        tmp_path,
        "# Learnings\n\n## Rule one\n\na\n\n## Rule two\n\nb\n",
        "# Detail\n\n## Rule one\n\nx\n",
    )

    result = al.check_learnings_pairing(repo)

    assert result["status"] == "ok"
    assert result["counts"]["index_active"] == 2
    assert result["counts"]["detail_active"] == 1


def test_a_detail_heading_is_matched_by_prefix_not_equality(tmp_path):
    """The real convention: the detail heading is the index entry's opening
    clause, not a copy of it."""
    repo = _corpus(
        tmp_path,
        "# Learnings\n\n## Rule one — with a long tail — [learnings-detail.md]\n\na\n",
        "# Detail\n\n## Rule one\n\nx\n",
    )

    result = al.check_learnings_pairing(repo)

    assert result["counts"]["detail_without_index_prefix_match"] == 0
    assert result["counts"]["paired_entries_out_of_order"] == 0


# --- degradation ------------------------------------------------------------

def test_an_unsplit_corpus_is_ok_not_a_finding(tmp_path):
    repo = _corpus(tmp_path, "# Learnings\n\n## Rule one\n\na\n")

    assert al.check_learnings_pairing(repo)["status"] == "ok"


def test_a_missing_index_is_not_this_checks_finding(tmp_path):
    """A missing `learnings.md` belongs to doctor Check #5 (core state present),
    and Check #13 in the same file already rules that way for the same absence.

    Two checks reporting one absence differently is how an operator learns to
    trust neither — so `unchecked` is reserved for a file that EXISTS and could
    not be read, which is the case the next test covers.
    """
    (tmp_path / ".prawduct").mkdir()

    result = al.check_learnings_pairing(tmp_path)

    assert result["status"] == "ok"
    assert result["findings"] == []


def test_an_undecodable_file_is_ungraded_not_clean(tmp_path):
    d = tmp_path / ".prawduct"
    d.mkdir()
    (d / "learnings.md").write_bytes(b"\xff\xfe\x00 not utf-8")
    (d / "learnings-detail.md").write_text("# Detail\n")

    result = al.check_learnings_pairing(tmp_path)

    assert result["status"] == "unchecked"


# --- the refusal ------------------------------------------------------------

def test_take_active_narrative_refuses_on_a_duplicate_naming_both_lines():
    lines = "# D\n\n## Rule one\n\nfirst\n\n## Rule one\n\nsecond\n".split("\n")
    before = list(lines)

    body, error = al._take_active_narrative(lines, "Rule one", len(lines))

    assert body == ""
    assert error and "2 active blocks" in error
    assert "3, 7" in error, error
    assert lines == before, "a refusal must not mutate the file"


def test_take_active_narrative_still_cuts_a_single_match():
    lines = "# D\n\n## Rule one\n\nbody text\n".split("\n")

    body, error = al._take_active_narrative(lines, "Rule one", len(lines))

    assert error is None
    assert "body text" in body
    assert "## Rule one" not in "\n".join(lines)


def test_take_active_narrative_is_silent_on_no_match():
    """Absent is not an error — a drifted title is deliberately left alone."""
    lines = "# D\n\n## Other\n\nbody\n".split("\n")

    assert al._take_active_narrative(lines, "Rule one", len(lines)) == ("", None)


def test_a_duplicate_below_the_limit_is_not_counted():
    """`limit` is the historical boundary: an archived twin must not block a
    retirement, or a second retirement of the same title becomes impossible."""
    lines = "# D\n\n## Rule one\n\nactive\n\n## Rule one\n\narchived\n".split("\n")

    body, error = al._take_active_narrative(lines, "Rule one", 5)

    assert error is None
    assert "active" in body


# --- the refusal at the level it actually ships at --------------------------
#
# Every test above this line calls the private `_take_active_narrative`. Three
# defects reached review through that gap and all three lived on the delivery
# path: the refusal was appended to `errors` as a bare string where every other
# member is a {"title","error"} pair (a TypeError traceback across the CLI
# boundary), the per-entry `applied` flag stayed true so a refused run printed
# `retire[retired]` for entries nothing moved, and a refused `--apply` exited 0.
# None of them is reachable from a unit test of the cutter.

from lib.audit_learnings_cmd import run_audit_learnings  # noqa: E402

_DUPLICATED = (
    "# Detail\n\n## Old rule\n\nfirst copy\n\n## Old rule\n\nsecond copy\n"
)
_INDEX = (
    "# Learnings\n\n## Old rule\n"
    "<!-- prawduct-learning: superseded-by=New rule -->\n\n## New rule\n"
)


def _retiring_corpus(tmp_path, detail):
    d = tmp_path / ".prawduct"
    d.mkdir(parents=True, exist_ok=True)
    (d / "learnings.md").write_text(_INDEX, encoding="utf-8")
    (d / "learnings-detail.md").write_text(detail, encoding="utf-8")
    return tmp_path


def test_apply_refuses_on_a_duplicated_detail_heading(tmp_path):
    repo = _retiring_corpus(tmp_path, _DUPLICATED)

    result = run_audit_learnings(str(repo), apply=True)

    assert result["applied"] is False
    assert result["errors"], "the refusal must be reported"


def test_the_refusal_is_attributed_not_a_bare_string(tmp_path):
    """The renderer reads `e['title']` and `e['error']`; a bare string is a
    TypeError traceback across the CLI boundary, which api-contract forbids."""
    repo = _retiring_corpus(tmp_path, _DUPLICATED)

    error = run_audit_learnings(str(repo), apply=True)["errors"][0]

    assert set(error) >= {"title", "error"}
    assert isinstance(error["title"], str)
    assert "2 active blocks" in error["error"]


def test_a_refused_apply_writes_neither_file(tmp_path):
    """Composition happens before I/O precisely so a refusal can be total."""
    repo = _retiring_corpus(tmp_path, _DUPLICATED)
    index_before = (repo / ".prawduct" / "learnings.md").read_text()
    detail_before = (repo / ".prawduct" / "learnings-detail.md").read_text()

    run_audit_learnings(str(repo), apply=True)

    assert (repo / ".prawduct" / "learnings.md").read_text() == index_before
    assert (repo / ".prawduct" / "learnings-detail.md").read_text() == detail_before


def test_no_per_entry_record_claims_it_was_applied_after_a_refusal(tmp_path):
    """The renderer branches on the per-entry flag, not the top-level one, so
    leaving it true prints `retire[retired]` for an entry still in place."""
    repo = _retiring_corpus(tmp_path, _DUPLICATED)

    result = run_audit_learnings(str(repo), apply=True)

    assert result["retirements"], "the fixture must produce a candidate"
    assert not any(r["applied"] for r in result["retirements"])


def test_a_clean_corpus_still_applies_and_reports_applied(tmp_path):
    """The negative. A refusal that fires on a healthy retirement would break
    every retirement, which is worse than the orphaning it prevents."""
    repo = _retiring_corpus(
        tmp_path, "# Detail\n\n## Old rule\n\nthe only copy\n"
    )

    result = run_audit_learnings(str(repo), apply=True)

    assert result["applied"] is True
    assert all(r["applied"] for r in result["retirements"])
    assert "the only copy" in (repo / ".prawduct" / "learnings-detail.md").read_text()


_HOOK = Path(__file__).resolve().parent.parent / "plugin" / "bin" / "prawduct-hook"


def _run_hook(repo: Path, *args: str):
    """Invoke the hook against `repo` with a PINNED environment.

    Inheriting `os.environ` is the bug this helper exists to prevent, and it is
    not hypothetical: `gitstate.resolve_project_dir` returns the
    `CLAUDE_PROJECT_DIR` pin whenever cwd is not a git work tree, and a pytest
    `tmp_path` never is. So an inherited env sends `--apply` at the REAL repo —
    which for these fixtures means rewriting its `learnings.md` and
    `learnings-detail.md` the moment that corpus grows one supersession pointer.
    The identical incident is recorded at
    `tests/test_audit_learnings.py::TestAuditLearningsCLI` (a worker killed on
    2026-06-10 by a 13s audit of the real corpus); its guard is this one.
    """
    return subprocess.run(
        [sys.executable, str(_HOOK), *args],
        capture_output=True, text=True,
        env={"CLAUDE_PROJECT_DIR": str(repo), "PATH": "/usr/bin:/bin"},
    )


def test_the_cli_exits_nonzero_on_a_refused_apply(tmp_path):
    """A writer that refused and wrote nothing exits 1 (api-contract). Exit 0
    tells the caller the retirement happened."""
    repo = _retiring_corpus(tmp_path, _DUPLICATED)

    for extra in ([], ["--json"]):
        proc = _run_hook(repo, "audit-learnings", "--apply", *extra)
        assert proc.returncode == 1, (extra, proc.returncode, proc.stdout[-400:])
        assert "Traceback" not in proc.stderr, proc.stderr[-400:]


def test_the_cli_exits_zero_on_a_clean_apply(tmp_path):
    repo = _retiring_corpus(tmp_path, "# Detail\n\n## Old rule\n\nonly\n")

    proc = _run_hook(repo, "audit-learnings", "--apply")

    assert proc.returncode == 0, proc.stdout[-400:]


def test_the_cli_tests_target_the_fixture_and_not_the_real_repo(tmp_path):
    """The guard on the guard.

    If `_run_hook` ever inherits the environment again, this fails loudly rather
    than silently auditing — and possibly rewriting — the repo the suite runs
    in. Asserted by observing that the fixture is what changed.
    """
    repo = _retiring_corpus(tmp_path, "# Detail\n\n## Old rule\n\nonly\n")
    real_index = Path(__file__).resolve().parent.parent / ".prawduct" / "learnings.md"
    real_before = real_index.read_text(encoding="utf-8") if real_index.is_file() else None

    _run_hook(repo, "audit-learnings", "--apply")

    assert "superseded by" in (repo / ".prawduct" / "learnings-detail.md").read_text()
    if real_before is not None:
        assert real_index.read_text(encoding="utf-8") == real_before


def test_the_ordering_metric_counts_descents_among_paired_entries(tmp_path):
    """`paired_entries_out_of_order` is published output — doctor #13a names it
    and `check-learnings-pairing` is in the stable `check-*` tier — so its
    semantics need pinning: unpaired detail titles are dropped BEFORE adjacent
    positions are compared, so an unpaired entry between two ordered ones does
    not manufacture a descent."""
    repo = _corpus(
        tmp_path,
        "# Learnings\n\n## Alpha\n\na\n\n## Beta\n\nb\n\n## Gamma\n\nc\n",
        "# Detail\n\n## Gamma\n\nc\n\n## Alpha\n\na\n",
    )

    counts = al.check_learnings_pairing(repo)["counts"]

    assert counts["paired_entries_out_of_order"] == 1


def test_an_unpaired_entry_does_not_manufacture_a_descent(tmp_path):
    repo = _corpus(
        tmp_path,
        "# Learnings\n\n## Alpha\n\na\n\n## Beta\n\nb\n",
        "# Detail\n\n## Alpha\n\na\n\n## Orphan\n\no\n\n## Beta\n\nb\n",
    )

    counts = al.check_learnings_pairing(repo)["counts"]

    assert counts["detail_without_index_prefix_match"] == 1
    assert counts["paired_entries_out_of_order"] == 0


def test_the_refusal_names_the_entry_that_refused_not_the_first_candidate(tmp_path):
    """A bulk `--apply` retires many entries and returns on the FIRST duplicate.

    With one candidate the two are the same entry, so every single-candidate
    fixture above passes whether the attribution is right or wrong. This one
    puts the duplicate on the SECOND candidate, which is the only shape that can
    tell them apart — and `errors[].title` is the field doctor is told to relay,
    so a mismatch prints one line naming two different entries.
    """
    index = (
        "# Learnings\n\n"
        "## First rule\n<!-- prawduct-learning: superseded-by=Survivor -->\n\n"
        "## Second rule\n<!-- prawduct-learning: superseded-by=Survivor -->\n\n"
        "## Survivor\n"
    )
    detail = (
        "# Detail\n\n## First rule\n\nonly copy\n\n"
        "## Second rule\n\nfirst copy\n\n## Second rule\n\nsecond copy\n"
    )
    d = tmp_path / ".prawduct"
    d.mkdir(parents=True)
    (d / "learnings.md").write_text(index, encoding="utf-8")
    (d / "learnings-detail.md").write_text(detail, encoding="utf-8")

    errors = run_audit_learnings(str(tmp_path), apply=True)["errors"]

    assert errors, "the duplicate on the second candidate must refuse"
    assert errors[0]["title"] == "Second rule", errors[0]
    assert "Second rule" in errors[0]["error"]
    assert "First rule" not in errors[0]["title"]
