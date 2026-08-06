"""Gate as dispatcher: `critic-begin` refuses a review the gate would not require.

`coverage_algebra.is_judgeable_path` already decides which paths need review
coverage, and `coverage_verdict` already grants **free edges** for intervals
holding no judgeable content — but that predicate was consulted only when
*grading* coverage, never when *deciding to spend* a review. A predicate used as
an auditor instead of as a scheduler.

Measured on 2026-08-06: 62 of 492 recorded review facts (12.6%, ~5.2 opus-hours
at the verify-mode median) covered entirely non-judgeable intervals. On
`fix/backlog-import-title-boundary`, rounds 3, 4 and 5 followed docs commits,
were each a free edge, and each returned 0/0/0.

**The predicate, and why both conjuncts are load-bearing.** Refuse iff the
interval holds no judgeable file AND there are no unresolved actionable findings
this review could resolve. Drop the first and reviews of real code are refused.
Drop the second and the gate deadlocks: a `blocked` verdict's only remedy is the
`verify-resolutions` pass that would have been refused. Round 2 of that branch is
the live example — a free-ish delta whose prior review carried five blockers, and
which therefore had to run.

**The safety argument these tests exist to defend.** The dispatcher may refuse
only what the gate would already pass — same predicate, same inputs, moved
upstream of the cost. Nothing unmergeable becomes mergeable. A skip-gate needs
the MOST adversarial coverage: the retired PR trivial fast-path shipped with none
and was withdrawn (`#292`). Every test below is a way the refusal could wrongly
fire, not a way it could work.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"
sys.path.insert(0, str(ROOT))

PARTIALS_REL = ".prawduct/.critic-partials"
MARKER_REL = ".prawduct/.critic-active"

EXIT_NO_REVIEW_NEEDED = 3


# ---------------------------------------------------------------------------
# Harness (mirrors tests/test_critic_consolidate.py so the two read alike)
# ---------------------------------------------------------------------------


def _git_env(repo: Path) -> dict[str, str]:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return {
        "HOME": str(home),
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
    (repo / ".prawduct").mkdir(exist_ok=True)


def _commit_file(repo: Path, rel: str, content: str, msg: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo, "add", rel)
    _git(repo, "commit", "-m", msg, "--quiet")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _run_begin(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(HOOK), "critic-begin", *args],
        cwd=str(repo), capture_output=True, text=True,
        env={**_git_env(repo), "CLAUDE_PLUGIN_ROOT": str(ROOT)}, timeout=30,
    )


def _run_consolidate(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(HOOK), "critic-consolidate"],
        cwd=str(repo), capture_output=True, text=True,
        env={**_git_env(repo), "CLAUDE_PLUGIN_ROOT": str(ROOT)}, timeout=30,
    )


def _review_id(repo: Path) -> str:
    return json.loads((repo / PARTIALS_REL / "manifest.json").read_text())["id"]


def _write_partial(repo: Path, head: str, findings=None) -> None:
    rid = _review_id(repo)
    payload = {
        "role": "reviewer",
        "goals": "1-3",
        "dispatch_id": rid,
        "commit_reviewed": head,
        "model": "opus",
        "duration_seconds": 90,
        "findings": findings or [],
        "summary": "reviewer review complete.",
    }
    (repo / PARTIALS_REL / f"reviewer.{rid}.json").write_text(json.dumps(payload))


def _seed_prior_review(repo: Path, *, findings=None) -> str:
    """Run one real chunk review to completion so a prior FACT exists.

    Goes through the real lifecycle rather than hand-writing a fact: the second
    conjunct reads the prior fact's counts, and a hand-forged fact would let a
    schema change pass here while failing in production.
    """
    # Three files, not one. The prior review's file count sets the unrelated
    # scope-widening threshold (`> 2x prior + 5`); seeding a one-file review
    # makes any realistic later delta trip it, which would fail these tests for
    # a reason that has nothing to do with the refusal.
    for rel in ("src/app.py", "src/two.py", "src/three.py"):
        _commit_file(repo, rel, "x = 1\n", f"seed {rel}")
        (repo / rel).write_text("x = 2\n")  # a dirty judgeable diff to review
    result = _run_begin(repo, "--mode", "chunk")
    assert result.returncode == 0, f"seed dispatch failed: {result.stderr!r}"
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _write_partial(repo, head, findings=findings)
    consolidated = _run_consolidate(repo)
    assert consolidated.returncode == 0, f"seed consolidate failed: {consolidated.stderr!r}"
    # Commit ONLY the source files. `git add -A` would sweep in the
    # `.prawduct/` artifacts consolidate just wrote (`.critic-findings.json`,
    # `.governance-ledger.jsonl`) — non-judgeable, so they never change a
    # verdict, but they pad every later delta with files the test did not put
    # there. That is enough to make a test pass for the wrong reason: with
    # stray non-`.md` paths present, a refusal wrongly keyed on "all files end
    # in .md" still dispatches, and the assertion that the JUDGEABLE `.md` is
    # what forced the dispatch never actually gets exercised. The real repo
    # gitignores these; the fixture matches it.
    _git(repo, "add", "src")
    _git(repo, "commit", "-m", "seed: land the reviewed change", "--quiet")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


#: Content of the sentinel partial :func:`_seed_leftover_partial` plants. Its
#: value is irrelevant; that it is byte-identical afterwards is the assertion.
_SURVIVOR_NAME = "reviewer.rev-19700101T000000Z-leftover.json"
_SURVIVOR_BODY = '{"role": "reviewer", "note": "another review\'s unconsolidated work"}'


def _seed_leftover_partial(repo: Path) -> None:
    """Plant an unconsolidated partial that a refusal must leave ALONE.

    Without this the partial-reset half of :func:`_assert_no_dispatch_state`
    is **vacuous**, and was: `_archive_leftovers` returns before creating
    anything when the partials dir has no children, and every fixture here has
    already had its partials removed by consolidate. So "no leftovers remain"
    held no matter what the refusal did — absence of a thing that was never
    there proves nothing, and all three call sites passed on that.

    Seeding inverts the assertion from an absence to a SURVIVAL: the sweep a
    dispatch performs would move this file into the archive directory, so a
    refusal that fell through to it now fails loudly.

    Safe against the interval under test: the file lands under `.prawduct/`,
    which `is_judgeable_path` classifies non-judgeable, so it cannot turn a
    free interval into a reviewable one for the working-tree modes.
    """
    pdir = repo / PARTIALS_REL
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / _SURVIVOR_NAME).write_text(_SURVIVOR_BODY)


def _assert_no_dispatch_state(repo: Path) -> None:
    """A refusal must disturb nothing a real dispatch would create.

    The refusal returns before the manifest write and before the critic-active
    marker, so a leftover of either would mean it fired too late — and a stray
    marker is worse than a wasted review, because `clear` refuses to run while
    one is live.

    Call :func:`_seed_leftover_partial` first: the partials clause below only
    means something when there is something there to disturb.
    """
    assert not (repo / MARKER_REL).is_file(), "refusal left a critic-active marker"
    assert not (repo / PARTIALS_REL / "manifest.json").is_file(), (
        "refusal wrote a dispatch manifest"
    )
    # The partial-reset half. `begin_review` archives/clears leftover partials
    # as part of dispatching, and that sweep is the single most destructive act
    # against another review — so a refusal reaching it would be worse than the
    # wasted review it was avoiding. Asserted as SURVIVAL of a planted sentinel,
    # never as emptiness: emptiness is the state the fixture is already in.
    survivor = repo / PARTIALS_REL / _SURVIVOR_NAME
    assert survivor.is_file(), (
        "the refusal swept away another review's unconsolidated partial — it "
        "reached the dispatch-time partials reset it must return before "
        f"(seed missing: {survivor})"
    )
    assert survivor.read_text() == _SURVIVOR_BODY, (
        "the refusal rewrote another review's partial"
    )
    leftovers = sorted(p.name for p in (repo / PARTIALS_REL).glob("*.json"))
    assert leftovers == [_SURVIVOR_NAME], (
        f"refusal disturbed the partials dir: {leftovers}"
    )
    archive = repo / ".prawduct" / ".critic-partials-archive"
    assert not archive.exists(), "refusal archived partials it should not have touched"


# ---------------------------------------------------------------------------
# The refusal fires — and only here
# ---------------------------------------------------------------------------


class TestRefusesWhatTheGateWouldPass:
    def test_free_interval_after_a_clean_review_is_refused(self, tmp_path):
        """Rounds 3/4/5 of `fix/backlog-import-title-boundary`, reproduced.

        A docs-only delta after a review that found nothing: nothing to verify
        and nothing to judge.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        _seed_prior_review(repo, findings=[])
        _commit_file(repo, "docs/notes.md", "prose\n", "docs: a note")
        _seed_leftover_partial(repo)

        result = _run_begin(repo, "--mode", "verify-resolutions")

        assert result.returncode == EXIT_NO_REVIEW_NEEDED, (
            f"rc={result.returncode} out={result.stdout!r} err={result.stderr!r}"
        )
        assert "docs/notes.md" in result.stdout, (
            "the refusal must name the free files — an unexplained skip is "
            "indistinguishable from a broken gate"
        )
        _assert_no_dispatch_state(repo)

    @pytest.mark.parametrize("mode", ["chunk", "final", "cumulative"])
    def test_the_rule_is_mode_uniform(self, tmp_path, mode):
        """The refusal is not a verify-resolutions special case.

        `begin_review`'s neighbouring empty-diff refusal exempts
        verify-resolutions, so "which modes does this apply to" is a real
        question here rather than an obvious one — and the answer shipped
        untested. A free interval is free whatever mode is asked for: only
        verify-resolutions can carry outstanding findings, and for every other
        mode `pending_actionable` is 0 by construction.

        `chunk`/`final` diff HEAD against the WORKING tree, so their free
        interval is an uncommitted `.prawduct/` edit; `cumulative` diffs
        `merge-base...HEAD`, so its is a committed one.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        if mode == "cumulative":
            # cumulative's interval is `merge-base(base, HEAD)...HEAD`, so it
            # needs a branch to be measured against. Without one the interval is
            # EMPTY, and the pre-existing empty-diff refusal fires first — which
            # would make this test pass for a reason unrelated to judgeability.
            _git(repo, "checkout", "--quiet", "-b", "feat/x")
            _commit_file(repo, ".prawduct/notes.md", "prose\n", "docs: a note")
        else:
            (repo / ".prawduct" / "notes.md").write_text("prose\n")
        _seed_leftover_partial(repo)

        result = _run_begin(repo, "--mode", mode)

        assert result.returncode == EXIT_NO_REVIEW_NEEDED, (
            f"mode {mode} did not honour the free-interval refusal — "
            f"rc={result.returncode} out={result.stdout!r} err={result.stderr!r}"
        )
        _assert_no_dispatch_state(repo)

    def test_the_refusal_names_the_override(self, tmp_path):
        """A refusal the reader cannot overrule is a dead end, not a decision."""
        repo = tmp_path / "r"
        _init_repo(repo)
        _seed_prior_review(repo, findings=[])
        _commit_file(repo, "docs/notes.md", "prose\n", "docs: a note")

        result = _run_begin(repo, "--mode", "verify-resolutions")

        assert result.returncode == EXIT_NO_REVIEW_NEEDED
        assert "--force" in result.stdout


# ---------------------------------------------------------------------------
# The adversarial set: every way the refusal could wrongly fire
# ---------------------------------------------------------------------------


class TestNeverRefusesJudgeableWork:
    def test_one_judgeable_file_among_many_free_ones_dispatches(self, tmp_path):
        """The fail-closed case. A single `.py` buried in a docs commit is still
        code, and `judgeable_files` is a filter, not a majority vote."""
        repo = tmp_path / "r"
        _init_repo(repo)
        _seed_prior_review(repo, findings=[])
        # Five, not fifty: a wider delta trips the unrelated scope-widening
        # demotion (`> 2x prior + 5`) and would make this test pass for the
        # wrong reason. The claim under test is "a filter, not a majority vote",
        # and 5:1 states it.
        for i in range(5):
            (repo / f"docs/n{i}.md").parent.mkdir(parents=True, exist_ok=True)
            (repo / f"docs/n{i}.md").write_text(f"prose {i}\n")
        (repo / "src/app.py").write_text("x = 3\n")  # the one that matters
        # Named paths, not `-A`: sweeping in the `.prawduct/` artifacts left by
        # the seed's consolidate would widen the delta by files this test did not
        # choose — both re-admitting the scope-widening threshold the file counts
        # above were picked to stay under, and padding the delta with extra
        # non-judgeable paths so the 5:1 ratio the test asserts is no longer the
        # ratio it exercises.
        _git(repo, "add", "docs", "src")
        _git(repo, "commit", "-m", "docs + one code line", "--quiet")

        result = _run_begin(repo, "--mode", "verify-resolutions")

        assert result.returncode == 0, (
            "one judgeable file must force a dispatch — "
            f"rc={result.returncode} out={result.stdout!r}"
        )
        assert (repo / PARTIALS_REL / "manifest.json").is_file()

    @pytest.mark.parametrize("rel", [
        "plugin/skills/critic/review-protocol.md",
        "plugin/methodology/building.md",
        "plugin/templates/build-plan.md",
        "CLAUDE.md",
    ])
    def test_governance_protected_markdown_dispatches(self, tmp_path, rel):
        """The trap: a `.md` that IS judgeable.

        Fork-skill prose is behavioral logic in this framework, so
        `skills/`, `methodology/`, `templates/` and root `CLAUDE.md` are
        judgeable despite the extension. A refusal keyed on "looks like docs"
        rather than on the predicate would wave these straight through.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        _seed_prior_review(repo, findings=[])
        _commit_file(repo, rel, "governance prose\n", f"docs: {rel}")

        result = _run_begin(repo, "--mode", "verify-resolutions")

        assert result.returncode == 0, (
            f"{rel} is judgeable and must be reviewed — rc={result.returncode}"
        )

    def test_free_interval_with_unresolved_findings_dispatches(self, tmp_path):
        """The anti-deadlock case, and the reason the predicate is a conjunction.

        A `blocked` verdict's only remedy is a `verify-resolutions` pass. If a
        free interval could refuse that pass, findings raised over prose would
        become permanently unresolvable — the gate would be wedged with no
        command that clears it. This is round 2 of the merged branch: a delta
        whose prior review carried real findings, which therefore had to run.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        _seed_prior_review(repo, findings=[{
            "name": "A real problem",
            "goal": "Nothing Is Broken",
            "severity": "blocking",
            "detail": "seeded so the prior review is not clean",
            "recommendation": "fix it",
        }])
        _commit_file(repo, "docs/notes.md", "prose\n", "docs: a note")

        result = _run_begin(repo, "--mode", "verify-resolutions")

        assert result.returncode == 0, (
            "a review that could resolve outstanding findings must never be "
            f"refused — rc={result.returncode} out={result.stdout!r}"
        )

    def test_force_dispatches_over_a_free_interval(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        _seed_prior_review(repo, findings=[])
        _commit_file(repo, "docs/notes.md", "prose\n", "docs: a note")

        result = _run_begin(repo, "--mode", "verify-resolutions", "--force")

        assert result.returncode == 0, f"--force ignored: {result.stderr!r}"
        assert (repo / PARTIALS_REL / "manifest.json").is_file()


class TestUncertaintyNeverBuysASkip:
    """The property: an input the check cannot evaluate never produces a refusal.

    Note what these assert and what they do NOT. An earlier version of this class
    called `coverage_algebra` directly — which passes unchanged against code that
    has no refusal at all, so it could never have caught a refusal firing on an
    uncomputable input. These drive `begin_review` through the real CLI, because
    the boundary is where the property either holds or does not.

    The property is **"never refuses"**, not "dispatches". A diff that cannot be
    computed returns an error (exit 1) *before* the refusal is reached — the
    caller is told, and no review is skipped. Both non-refusal outcomes are safe;
    conflating them is what made the original criterion unfalsifiable.
    """

    def test_an_uncomputable_diff_never_refuses(self, tmp_path):
        """A corrupted object store cannot yield a file list, so the interval's
        judgeability is unknown — and unknown must not resolve to "free"."""
        repo = tmp_path / "r"
        _init_repo(repo)
        _seed_prior_review(repo, findings=[])
        _commit_file(repo, "docs/notes.md", "prose\n", "docs: a note")
        _seed_leftover_partial(repo)
        # Break the object store so `tree_diff` cannot answer.
        for pack in (repo / ".git" / "objects").rglob("*"):
            if pack.is_file():
                pack.chmod(0o000)
        try:
            result = _run_begin(repo, "--mode", "verify-resolutions")
        finally:
            for pack in (repo / ".git" / "objects").rglob("*"):
                if pack.is_file():
                    pack.chmod(0o644)

        assert result.returncode != EXIT_NO_REVIEW_NEEDED, (
            "an interval whose diff could not be computed was refused as free — "
            f"uncertainty must never buy a skip. stdout={result.stdout!r}"
        )
        _assert_no_dispatch_state(repo)

    def test_no_evidence_store_never_refuses_judgeable_work(self, tmp_path):
        """With no store there are no facts, so nothing can be outstanding —
        the refusal must then rest entirely on judgeability, and judgeable work
        still dispatches."""
        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / "src/app.py").write_text("x = 2\n")

        result = _run_begin(repo, "--mode", "chunk")  # no prior review anywhere

        assert result.returncode == 0, (
            f"judgeable work with no store must dispatch — rc={result.returncode}"
        )

    def test_unknown_paths_are_treated_as_judgeable(self, tmp_path):
        """The classifier's default, asserted THROUGH the dispatcher: a path
        shape nobody anticipated dispatches rather than skips. Driven at the
        boundary so it fails if the refusal ever grows its own path rules."""
        repo = tmp_path / "r"
        _init_repo(repo)
        _seed_prior_review(repo, findings=[])
        _commit_file(repo, "Makefile", "all:\n\techo hi\n", "add a Makefile")

        result = _run_begin(repo, "--mode", "verify-resolutions")

        assert result.returncode == 0, (
            "an extensionless, unrecognized path must be treated as judgeable — "
            f"rc={result.returncode} out={result.stdout!r}"
        )

class TestTheRefusalIsObservable:
    """A silent skip is indistinguishable from a broken gate.

    The governing norm — *a control names the yield it expects and emits it
    observably* — is why this is a test and not a nicety. The yield argument for
    the whole guard rests on a measurement taken BEFORE it existed; only a
    record of real firings can ever falsify it, or answer the question that
    retires the guard: did it ever refuse a round that turned out to be needed?

    Sink: the clone-shared evidence store, per #596 (which owns pre-dispatch
    guard telemetry as a class) rather than the per-worktree governance ledger
    the build plan first proposed. Reasons live on
    `evidence.append_guard_refusal`; these tests pin the behaviour that ruling
    has to produce.
    """

    @staticmethod
    def _guard_facts(repo: Path) -> list[dict]:
        store = repo / ".git" / "prawduct" / "evidence.jsonl"
        if not store.is_file():
            return []
        facts = []
        for line in store.read_text().splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("kind") == "guard-refusal":
                facts.append(record)
        return facts

    def test_a_refusal_records_exactly_one_fact(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        _seed_prior_review(repo, findings=[])
        _commit_file(repo, "docs/notes.md", "prose\n", "docs: a note")

        result = _run_begin(repo, "--mode", "verify-resolutions")
        assert result.returncode == EXIT_NO_REVIEW_NEEDED

        facts = self._guard_facts(repo)
        assert len(facts) == 1, f"expected one guard-refusal fact, got {facts}"
        body = facts[0]["body"]
        assert body["guard"] == "critic-dispatch-free-interval"
        assert body["mode"] == "verify-resolutions"
        # The free file list is the whole point: "did this guard ever refuse a
        # round that turned out to be needed" is answerable only if the record
        # says what it waved through.
        assert body["free_files"] == ["docs/notes.md"]
        assert body["interval"]["base_tree"] and body["interval"]["head_tree"]

    def test_every_refusal_records_its_own_fact(self, tmp_path):
        """Counting is the yield question. Two refusals that collapse into one
        record would under-report the guard's own saving — and a fixed id is
        the ordinary way that happens (the review store dedupes on
        ``(kind, id)``, keeping the first)."""
        repo = tmp_path / "r"
        _init_repo(repo)
        _seed_prior_review(repo, findings=[])
        _commit_file(repo, "docs/notes.md", "prose\n", "docs: a note")

        for _ in range(2):
            assert _run_begin(
                repo, "--mode", "verify-resolutions"
            ).returncode == EXIT_NO_REVIEW_NEEDED

        facts = self._guard_facts(repo)
        assert len(facts) == 2, f"two refusals collapsed into {len(facts)} record(s)"
        assert facts[0]["id"] != facts[1]["id"]

    def test_a_dispatch_records_no_refusal(self, tmp_path):
        """The other half of a count that means something: a guard that records
        when it did NOT fire makes every yield figure an overstatement."""
        repo = tmp_path / "r"
        _init_repo(repo)
        _seed_prior_review(repo, findings=[])
        _commit_file(repo, "src/app.py", "x = 9\n", "code: a real change")

        assert _run_begin(repo, "--mode", "verify-resolutions").returncode == 0
        assert self._guard_facts(repo) == []

    def test_force_records_no_refusal(self, tmp_path):
        """`--force` dispatches over a free interval, so the guard did not fire
        and must not claim it did."""
        repo = tmp_path / "r"
        _init_repo(repo)
        _seed_prior_review(repo, findings=[])
        _commit_file(repo, "docs/notes.md", "prose\n", "docs: a note")

        assert _run_begin(
            repo, "--mode", "verify-resolutions", "--force"
        ).returncode == 0
        assert self._guard_facts(repo) == []

    def test_an_unrecordable_refusal_is_still_a_refusal(self, tmp_path, monkeypatch):
        """The soft-fail contract, which shipped with no test.

        A refusal is correct whether or not the record lands, so a store failure
        must NOT convert a correct exit 3 into an error — that would hand the
        builder a review round because telemetry broke. It must not be silent
        either: a degraded record that vanishes leaves the yield question
        looking answered at zero (`learnings.md`: "'advice fails soft' is not
        'advice fails silent'").

        Driven in-process rather than through the CLI because the failure has to
        be *injected*: `append_fact` catches `OSError`, and there is no
        filesystem state that reliably produces one at that path on every
        machine (a chmod'd store is still writable as root, and the store's
        parent is created on demand).
        """
        import lib.critic_consolidate as cc
        import lib.evidence as ev

        repo = tmp_path / "r"
        _init_repo(repo)
        _seed_prior_review(repo, findings=[])
        _commit_file(repo, "docs/notes.md", "prose\n", "docs: a note")

        _seed_leftover_partial(repo)
        monkeypatch.setattr(
            ev, "append_guard_refusal",
            lambda *a, **k: {"status": "error", "reason": "store unwritable (injected)"},
        )
        result = cc.begin_review(repo, "verify-resolutions")

        assert result["status"] == "no-review-needed", (
            "a telemetry failure turned a correct refusal into something else — "
            f"the builder would pay a review round for a broken store: {result}"
        )
        assert result["recorded"] is False, (
            "the refusal claims it was recorded when the append failed"
        )
        _assert_no_dispatch_state(repo)

    def test_a_recorded_refusal_says_so(self, tmp_path):
        """The other half of `recorded` — otherwise the False case above is
        consistent with a key that is always False."""
        import lib.critic_consolidate as cc

        repo = tmp_path / "r"
        _init_repo(repo)
        _seed_prior_review(repo, findings=[])
        _commit_file(repo, "docs/notes.md", "prose\n", "docs: a note")

        result = cc.begin_review(repo, "verify-resolutions")

        assert result["status"] == "no-review-needed"
        assert result["recorded"] is True

    def test_a_body_cannot_override_the_guard_name(self, tmp_path):
        """`append_guard_refusal` mints the fact id from the `guard` PARAMETER,
        so a body key of the same name must not win: a record whose grouping key
        disagrees with its own id would split one guard's firings across two
        buckets in the only query that answers the yield question."""
        import lib.evidence as ev

        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "src/app.py", "x = 1\n", "init")

        assert ev.append_guard_refusal(
            repo, "real-guard", {"guard": "impostor", "free_files": []}
        )["status"] == "appended"

        fact = self._guard_facts(repo)[0]
        assert fact["body"]["guard"] == "real-guard"
        assert "real-guard" in fact["id"]

    def test_a_refusal_fact_cannot_cover_anything(self, tmp_path):
        """The safety property. These facts sit in the store every coverage gate
        composes over, so the one thing they must never do is help a gate pass.
        `coverage_algebra` derives edges from `kind == "review"` alone — asserted
        here through the algebra rather than by reading the filter, so it fails
        if the filter is ever loosened."""
        from lib import coverage_algebra

        refusal = {
            "schema": 1,
            "kind": "guard-refusal",
            "id": "guard-x",
            "body": {
                "guard": "critic-dispatch-free-interval",
                # The edge shape, deliberately: if a reader ever walked bodies
                # kind-blind, THIS is the record that would forge a hop.
                "base_tree": "a" * 40,
                "head_tree": "b" * 40,
                "files_changed": [],
                "files_reviewed": [],
            },
        }
        verdict = coverage_algebra.coverage_verdict(
            [refusal], "a" * 40, "b" * 40, lambda *_: ["src/app.py"]
        )
        assert verdict["status"] != "covered", (
            "a guard-refusal fact composed as coverage — the algebra's kind "
            f"filter no longer holds: {verdict}"
        )


class TestTheRefusalAgreesWithTheGate:
    def test_the_refusal_agrees_with_the_gate_predicate(self):
        """The safety invariant: the dispatcher refuses only intervals the
        coverage gate already treats as free. Unit-level on purpose — it pins
        the SHARED predicate, so if `is_judgeable_path` changes, this moves with
        it. It is the companion to the boundary tests above, not a substitute:
        a refusal keyed on its own private notion of "docs" is how a skip-gate
        and its gate drift apart.
        """
        from lib.coverage_algebra import judgeable_files

        free = ["docs/notes.md", ".prawduct/change-log.md", "documentation/x.md"]
        assert judgeable_files(free) == [], (
            "these are the paths the refusal is allowed to skip; if the "
            "predicate no longer agrees, the refusal is over-broad"
        )
        assert judgeable_files(free + ["src/app.py"]) == ["src/app.py"]
