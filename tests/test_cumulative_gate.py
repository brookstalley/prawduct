"""Tests for the cumulative-Critic PR gate — ``prawduct-hook check-cumulative-critic``.

CRT-7M2D: the gate judges a cumulative-Critic record by COMMIT-COVERAGE, not by
mtime-recency. A record satisfies the gate iff it is a clean, schema-valid,
cumulative-mode record whose ``commit_reviewed`` covers HEAD — meaning either
``commit_reviewed == HEAD`` OR the only files changed since are documentation
(``.md``). This kills two prior defects of the mtime-vs-``.session-start`` check:

  * **False-pass:** a record from this session whose ``commit_reviewed`` predated
    real code changes still passed (mtime was fresh). Now it FAILS.
  * **Treadmill:** every inert post-review fix moved HEAD past ``commit_reviewed``,
    forcing a full ``/prawduct:critic cumulative`` re-run. A doc-only delta now
    does NOT — coverage holds.

CRT-4J8W extends the gate with the **chain** acceptance: a ``verify-resolutions``
record carrying an ``extends_cumulative`` anchor X satisfies the gate iff it has
0 BLOCKING findings, its own ``commit_reviewed`` covers HEAD, X resolves, and
every non-``.md``, non-metadata file changed in ``X..HEAD`` is in the record's
``files_reviewed`` — killing the remaining treadmill leg (a full bundle re-review
after every post-cumulative code fix). The chain is a cheaper-path gate, so the
reject cases here are the load-bearing coverage (learnings: a skip-gate needs the
*most* adversarial coverage).

These tests had no predecessor — the gate shipped (v1.4 F2) with zero direct
coverage. Uses real ``git`` repos so ``rev-parse`` / ``diff`` behave as in
production (mock-git would diverge on commit resolution and name-only diffs).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "bin" / "prawduct-hook"
CUMULATIVE_MODE = "cumulative (bundle review, ready for merge)"
CHUNK_MODE = "chunk (lighter pass, not ready for push)"
VERIFY_MODE = "verify-resolutions (delta review, prior findings only)"


# ---------------------------------------------------------------------------
# Helpers (real git, sterile env — mirrors test_critic_mode_inference.py)
# ---------------------------------------------------------------------------


def _git_env(repo: Path) -> dict[str, str]:
    return {
        "HOME": str(repo.parent / "_home"),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=_git_env(repo), check=True, timeout=10,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _commit_file(repo: Path, rel: str, content: str, msg: str) -> str:
    """Write one file, stage ONLY it, commit. Returns the new HEAD sha.

    Targeted ``git add <rel>`` (not ``-A``) so an untracked
    ``.prawduct/.critic-findings.json`` never lands in a commit and pollutes the
    ``commit_reviewed..HEAD`` diff the gate inspects.
    """
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo, "add", rel)
    _git(repo, "commit", "-m", msg, "--quiet")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _write_findings(
    repo: Path,
    *,
    commit_reviewed: str | None,
    mode: str = CUMULATIVE_MODE,
    blocking: bool = False,
    include_commit: bool = True,
    files_reviewed: list[str] | None = None,
    extends_cumulative: str | None = None,
) -> None:
    """Write an UNtracked ``.prawduct/.critic-findings.json`` for the gate.

    ``extends_cumulative`` is the chain anchor SHA (CRT-4J8W); when given it
    is wrapped in the persisted ``{"commit_reviewed": <sha>}`` dict form.
    """
    data: dict = {
        "mode": mode,
        "files_reviewed": files_reviewed if files_reviewed is not None else ["app.py"],
        "findings": (
            [{"goal": "Nothing Is Broken", "severity": "blocking", "summary": "boom"}]
            if blocking else []
        ),
        "summary": "Cumulative review.",
    }
    if include_commit:
        data["commit_reviewed"] = commit_reviewed
    if extends_cumulative is not None:
        data["extends_cumulative"] = {"commit_reviewed": extends_cumulative}
    prawduct = repo / ".prawduct"
    prawduct.mkdir(parents=True, exist_ok=True)
    (prawduct / ".critic-findings.json").write_text(json.dumps(data))


def _run_gate(repo: Path) -> subprocess.CompletedProcess:
    env = dict(_git_env(repo))
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    return subprocess.run(
        ["python3", str(HOOK), "check-cumulative-critic"],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=30,
    )


# ---------------------------------------------------------------------------
# Coverage: the satisfying cases
# ---------------------------------------------------------------------------


def test_covers_head_exactly_passes(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    head = _commit_file(repo, "app.py", "print(1)\n", "init")
    _write_findings(repo, commit_reviewed=head)
    r = _run_gate(repo)
    assert r.returncode == 0, r.stderr
    assert "satisfied" in r.stdout and "covers HEAD" in r.stdout


def test_doc_only_delta_since_review_still_covered(tmp_path):
    # THE treadmill fix: HEAD moved past commit_reviewed but only a .md changed,
    # so the clean cumulative verdict still vouches for the code → no re-run.
    repo = tmp_path / "repo"
    _init_repo(repo)
    reviewed = _commit_file(repo, "app.py", "print(1)\n", "code")
    _commit_file(repo, "README.md", "# docs\n", "docs after review")  # HEAD moves
    _write_findings(repo, commit_reviewed=reviewed)
    r = _run_gate(repo)
    assert r.returncode == 0, f"doc-only delta must stay covered; stderr={r.stderr}"
    assert "satisfied" in r.stdout
    assert "stale" not in (r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# Coverage: the failing cases (honest)
# ---------------------------------------------------------------------------


def test_metadata_only_delta_since_review_still_covered(tmp_path):
    # CRT-5D8Q deadlock regression: a post-cumulative commit touching only
    # .prawduct/ metadata (e.g. repointing active_build_plan) used to read
    # "stale" while the verify-resolutions scope helper (rightly) filtered the
    # same files out — leaving no gate-qualifying path. Coverage now exempts
    # the same boundary the chain gap-check declares (.md + _is_metadata_path).
    repo = tmp_path / "repo"
    _init_repo(repo)
    reviewed = _commit_file(repo, "app.py", "print(1)\n", "code")
    _commit_file(repo, ".prawduct/project-state.yaml", "k: v\n", "repoint plan")
    _write_findings(repo, commit_reviewed=reviewed)
    r = _run_gate(repo)
    assert r.returncode == 0, f"metadata-only delta must stay covered; stderr={r.stderr}"
    assert "satisfied" in r.stdout
    assert "stale" not in (r.stdout + r.stderr)


def test_claude_settings_delta_since_review_still_covered(tmp_path):
    # Exercise the predicate, not one prefix: .claude/settings.json is the
    # second _METADATA_PREFIXES entry.
    repo = tmp_path / "repo"
    _init_repo(repo)
    reviewed = _commit_file(repo, "app.py", "print(1)\n", "code")
    _commit_file(repo, ".claude/settings.json", "{}\n", "install ref churn")
    _write_findings(repo, commit_reviewed=reviewed)
    r = _run_gate(repo)
    assert r.returncode == 0, r.stderr
    assert "satisfied" in r.stdout


def test_metadata_plus_code_delta_since_review_is_stale(tmp_path):
    # The exemption must not over-exempt: metadata riding alongside a code
    # change never launders the code change past the gate (a skip-gate needs
    # a regression test that the non-eligible case still BLOCKS).
    repo = tmp_path / "repo"
    _init_repo(repo)
    reviewed = _commit_file(repo, "app.py", "print(1)\n", "code")
    _commit_file(repo, ".prawduct/project-state.yaml", "k: v\n", "state")
    _commit_file(repo, "core.py", "x = 2\n", "code after review")
    _write_findings(repo, commit_reviewed=reviewed)
    r = _run_gate(repo)
    assert r.returncode == 1
    assert "stale" in r.stderr and "core.py" in r.stderr
    assert "project-state.yaml" not in r.stderr  # exempt files aren't the story


def test_code_delta_since_review_is_stale(tmp_path):
    # THE false-pass fix: a non-doc change since the review means the verdict no
    # longer covers the code being shipped → the gate must FAIL (re-run needed).
    repo = tmp_path / "repo"
    _init_repo(repo)
    reviewed = _commit_file(repo, "app.py", "print(1)\n", "code")
    _commit_file(repo, "core.py", "x = 2\n", "more code after review")  # HEAD moves
    _write_findings(repo, commit_reviewed=reviewed)
    r = _run_gate(repo)
    assert r.returncode == 1
    assert "stale" in r.stderr and "core.py" in r.stderr


def test_blocking_finding_fails(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    head = _commit_file(repo, "app.py", "print(1)\n", "init")
    _write_findings(repo, commit_reviewed=head, blocking=True)
    r = _run_gate(repo)
    assert r.returncode == 1
    assert "blocking" in r.stderr


def test_missing_commit_reviewed_fails(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit_file(repo, "app.py", "print(1)\n", "init")
    _write_findings(repo, commit_reviewed=None, include_commit=False)
    r = _run_gate(repo)
    assert r.returncode == 1
    assert "no-commit-reviewed" in r.stderr


def test_unresolved_commit_reviewed_fails(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit_file(repo, "app.py", "print(1)\n", "init")
    _write_findings(repo, commit_reviewed="0" * 40)  # well-formed but absent sha
    r = _run_gate(repo)
    assert r.returncode == 1
    assert "unresolved-commit" in r.stderr


def test_wrong_mode_fails(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    head = _commit_file(repo, "app.py", "print(1)\n", "init")
    _write_findings(repo, commit_reviewed=head, mode=CHUNK_MODE)
    r = _run_gate(repo)
    assert r.returncode == 1
    assert "wrong-mode" in r.stderr
    # Gate-soundness ch.4 + ch.5: the message teaches the sequencing rule that
    # was previously only learnable by paying a full cumulative re-review —
    # non-.md fixes land first, ONE cumulative, and post-cumulative fixes go
    # through the verify-resolutions chain (CRT-4J8W), not a full re-run.
    assert "verify-resolutions" in r.stderr
    assert "non-.md" in r.stderr


def test_missing_findings_file_fails(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit_file(repo, "app.py", "print(1)\n", "init")
    (repo / ".prawduct").mkdir()  # no .critic-findings.json
    r = _run_gate(repo)
    assert r.returncode == 1
    assert "missing" in r.stderr


# ---------------------------------------------------------------------------
# CRT-4J8W chain: the satisfying cases
# ---------------------------------------------------------------------------


def _chain_repo(tmp_path) -> tuple[Path, str, str]:
    """Repo with the canonical chain shape: cumulative at X, fix committed
    after, returning ``(repo, X, head)``."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    anchor = _commit_file(repo, "app.py", "print(1)\n", "bundle")  # cumulative @ X
    head = _commit_file(repo, "core.py", "x = 2\n", "fix after cumulative")
    return repo, anchor, head


def test_chain_record_covering_head_passes(tmp_path):
    # THE run-count fix: cumulative@X + committed fix + verify record at HEAD
    # whose scope covers X..HEAD → gate satisfied, no full re-review.
    repo, anchor, head = _chain_repo(tmp_path)
    _write_findings(
        repo, commit_reviewed=head, mode=VERIFY_MODE,
        files_reviewed=["app.py", "core.py"], extends_cumulative=anchor,
    )
    r = _run_gate(repo)
    assert r.returncode == 0, r.stderr
    assert "satisfied" in r.stdout and "chain" in r.stdout
    assert anchor[:12] in r.stdout


def test_chain_with_doc_only_delta_after_verify_still_passes(tmp_path):
    # The doc-only allowance applies to the chain's HEAD-coverage too:
    # reflections/docs committed after the verify pass don't re-stale it.
    repo, anchor, verify_head = _chain_repo(tmp_path)
    _commit_file(repo, "README.md", "# docs\n", "docs after verify")
    _write_findings(
        repo, commit_reviewed=verify_head, mode=VERIFY_MODE,
        files_reviewed=["app.py", "core.py"], extends_cumulative=anchor,
    )
    r = _run_gate(repo)
    assert r.returncode == 0, r.stderr
    assert "satisfied" in r.stdout


def test_chain_metadata_only_delta_after_verify_still_passes(tmp_path):
    # CRT-5D8Q, chain leg: metadata committed after the verify pass doesn't
    # re-stale the chain record's own HEAD-coverage either — both call sites
    # of the coverage rule share the exemption.
    repo, anchor, verify_head = _chain_repo(tmp_path)
    _commit_file(repo, ".prawduct/project-state.yaml", "k: v\n", "state after verify")
    _write_findings(
        repo, commit_reviewed=verify_head, mode=VERIFY_MODE,
        files_reviewed=["app.py", "core.py"], extends_cumulative=anchor,
    )
    r = _run_gate(repo)
    assert r.returncode == 0, r.stderr
    assert "satisfied" in r.stdout


def test_chain_scope_check_ignores_md_and_metadata_paths(tmp_path):
    # X..HEAD also contains a doc and a .prawduct metadata file that the
    # verify scope (rightly) never listed — neither may break the chain,
    # mirroring the gate's doc-only allowance and _is_metadata_path symmetry.
    repo, anchor, _ = _chain_repo(tmp_path)
    _commit_file(repo, "notes.md", "# n\n", "docs inside chain range")
    head = _commit_file(repo, ".prawduct/project-state.yaml", "k: v\n", "state")
    _write_findings(
        repo, commit_reviewed=head, mode=VERIFY_MODE,
        files_reviewed=["app.py", "core.py"], extends_cumulative=anchor,
    )
    r = _run_gate(repo)
    assert r.returncode == 0, r.stderr


# ---------------------------------------------------------------------------
# CRT-4J8W chain: the failing cases (fail-closed — a cheaper-path gate gets
# the most adversarial coverage)
# ---------------------------------------------------------------------------


def test_chain_scope_gap_fails(tmp_path):
    # A non-.md file changed since the extended cumulative but absent from
    # the verify record's scope: the chain cannot vouch for unreviewed code.
    repo, anchor, head = _chain_repo(tmp_path)
    _write_findings(
        repo, commit_reviewed=head, mode=VERIFY_MODE,
        files_reviewed=["app.py"],  # core.py changed in X..HEAD but not reviewed
        extends_cumulative=anchor,
    )
    r = _run_gate(repo)
    assert r.returncode == 1
    assert "chain-scope-gap" in r.stderr and "core.py" in r.stderr


def test_chain_unresolved_anchor_fails(tmp_path):
    repo, _, head = _chain_repo(tmp_path)
    _write_findings(
        repo, commit_reviewed=head, mode=VERIFY_MODE,
        files_reviewed=["app.py", "core.py"], extends_cumulative="0" * 40,
    )
    r = _run_gate(repo)
    assert r.returncode == 1
    assert "chain-unresolved-anchor" in r.stderr


def test_chain_record_with_blocking_finding_fails(tmp_path):
    # The verify pass re-emitted (or newly found) a BLOCKING — the chain
    # never launders an unresolved blocker through the cheap path.
    repo, anchor, head = _chain_repo(tmp_path)
    _write_findings(
        repo, commit_reviewed=head, mode=VERIFY_MODE, blocking=True,
        files_reviewed=["app.py", "core.py"], extends_cumulative=anchor,
    )
    r = _run_gate(repo)
    assert r.returncode == 1
    assert "blocking" in r.stderr


def test_chain_stale_when_code_committed_after_verify_fails(tmp_path):
    # Verify record anchored before the latest code commit (the classic
    # sequencing mistake: reviewing the fix, THEN committing more code).
    repo, anchor, verify_head = _chain_repo(tmp_path)
    _commit_file(repo, "extra.py", "y = 3\n", "code after verify")
    _write_findings(
        repo, commit_reviewed=verify_head, mode=VERIFY_MODE,
        files_reviewed=["app.py", "core.py", "extra.py"],
        extends_cumulative=anchor,
    )
    r = _run_gate(repo)
    assert r.returncode == 1
    assert "chain-stale" in r.stderr
    assert "commit" in r.stderr.lower()  # teaches: commit BEFORE verify


def test_verify_record_without_anchor_fails_with_teaching_message(tmp_path):
    # An anchor-less verify record still cannot certify the bundle — the
    # message now teaches the chain sequence instead of a flat refusal.
    repo, _, head = _chain_repo(tmp_path)
    _write_findings(
        repo, commit_reviewed=head, mode=VERIFY_MODE,
        files_reviewed=["app.py", "core.py"],
    )
    r = _run_gate(repo)
    assert r.returncode == 1
    assert "chain-missing-anchor" in r.stderr
    assert "cumulative" in r.stderr


def test_chain_record_with_malformed_anchor_fails_schema(tmp_path):
    # extends_cumulative must be {"commit_reviewed": <non-empty str>} —
    # writer drift fails schema validation, never half-evaluates the chain.
    repo, anchor, head = _chain_repo(tmp_path)
    _write_findings(
        repo, commit_reviewed=head, mode=VERIFY_MODE,
        files_reviewed=["app.py", "core.py"], extends_cumulative=anchor,
    )
    findings_path = repo / ".prawduct" / ".critic-findings.json"
    data = json.loads(findings_path.read_text())
    data["extends_cumulative"] = {"commit_reviewed": ""}
    findings_path.write_text(json.dumps(data))
    r = _run_gate(repo)
    assert r.returncode == 1
    assert "invalid" in r.stderr


# ---------------------------------------------------------------------------
# CRT-4J8W scope helper: chain-anchor emission + demotion relaxation
# ---------------------------------------------------------------------------


def _scope(repo: Path) -> tuple[list[str], str]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from lib.gates import _compute_verify_resolutions_scope

    return _compute_verify_resolutions_scope(repo / ".prawduct", repo)


def test_scope_reason_carries_anchor_for_cumulative_prior(tmp_path):
    # Prior is a cumulative with a fix committed after: the ok-reason must
    # name the anchor so the Critic embeds extends_cumulative.
    repo, anchor, _ = _chain_repo(tmp_path)
    _write_findings(
        repo, commit_reviewed=anchor, mode=CUMULATIVE_MODE,
        files_reviewed=["app.py"],
    )
    scope, reason = _scope(repo)
    assert reason.startswith("ok:"), reason
    assert f"extends-cumulative={anchor}" in reason
    assert "core.py" in scope and "app.py" in scope


def test_scope_clean_cumulative_prior_with_delta_no_longer_demotes(tmp_path):
    # Pre-CRT-4J8W this returned no-actionable-findings; a chain-extendable
    # prior with a reviewable delta is now a valid verify baseline.
    repo, anchor, _ = _chain_repo(tmp_path)
    _write_findings(
        repo, commit_reviewed=anchor, mode=CUMULATIVE_MODE,
        files_reviewed=["app.py"],  # clean record (no findings) by default
    )
    scope, reason = _scope(repo)
    assert scope, reason


def test_scope_anchor_propagates_through_chain_prior(tmp_path):
    # Prior is itself a chain record: the ORIGINAL cumulative anchor is
    # carried forward, not the intermediate verify commit.
    repo, anchor, verify_head = _chain_repo(tmp_path)
    _commit_file(repo, "extra.py", "y = 3\n", "second fix")
    _write_findings(
        repo, commit_reviewed=verify_head, mode=VERIFY_MODE,
        files_reviewed=["app.py", "core.py"], extends_cumulative=anchor,
    )
    scope, reason = _scope(repo)
    assert reason.startswith("ok:"), reason
    assert f"extends-cumulative={anchor}" in reason
    assert "extra.py" in scope


def test_scope_clean_cumulative_prior_with_no_delta_still_demotes(tmp_path):
    # Nothing to verify AND nothing to extend over — original demotion holds.
    repo = tmp_path / "repo"
    _init_repo(repo)
    head = _commit_file(repo, "app.py", "print(1)\n", "init")
    _write_findings(
        repo, commit_reviewed=head, mode=CUMULATIVE_MODE, files_reviewed=["app.py"],
    )
    scope, reason = _scope(repo)
    assert scope == []
    assert "no-actionable-findings" in reason


def test_scope_clean_non_chain_prior_still_demotes(tmp_path):
    # A clean chunk/final prior is NOT chain-extendable — demotion unchanged.
    repo, _, head = _chain_repo(tmp_path)
    _write_findings(
        repo, commit_reviewed=head, mode=CHUNK_MODE, files_reviewed=["app.py"],
    )
    scope, reason = _scope(repo)
    assert scope == []
    assert "no-actionable-findings" in reason


def test_scope_no_anchor_in_reason_for_non_chain_prior(tmp_path):
    # Actionable chunk-mode prior computes a scope but must NOT advertise a
    # chain anchor — the Critic would otherwise embed a bogus one.
    repo, _, head = _chain_repo(tmp_path)
    _write_findings(
        repo, commit_reviewed=head, mode=CHUNK_MODE, blocking=True,
        files_reviewed=["app.py", "core.py"],
    )
    repo_file = repo / "app.py"
    repo_file.write_text("print(2)\n")  # uncommitted fix in scope
    scope, reason = _scope(repo)
    assert reason.startswith("ok:"), reason
    assert "extends-cumulative=" not in reason
