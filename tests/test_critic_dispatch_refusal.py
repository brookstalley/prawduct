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


def _load_hook():
    """`prawduct-hook` as a module, for the rendering assertions.

    The script has a shebang and no `.py` extension; SourceFileLoader is how the
    rest of the suite reaches its internals. The module name is not "__main__",
    so importing does not dispatch. Needed here because the failure these tests
    inject cannot cross a subprocess boundary.
    """
    import importlib.machinery
    import importlib.util

    loader = importlib.machinery.SourceFileLoader("prawduct_hook_refusal", str(HOOK))
    spec = importlib.util.spec_from_loader("prawduct_hook_refusal", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


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
    marker is worse than a wasted review, because a bare `clear` refuses to run
    while one is live.

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

    def test_an_unrecordable_refusal_is_still_a_refusal(self, tmp_path, monkeypatch, capsys):
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
        # Soft is not SILENT. A degraded record that vanishes leaves the yield
        # question looking answered at zero, so the failure must reach a human
        # channel with the injected reason attached — not merely be flagged in a
        # return value no operator sees.
        err = capsys.readouterr().err
        assert "NOT recorded" in err, f"the failed append was silent: {err!r}"
        assert "store unwritable (injected)" in err, (
            f"the attribution dropped the underlying reason: {err!r}"
        )
        assert "lower bound" in err, (
            "the message does not tell the reader how to read the query it "
            f"just under-counted: {err!r}"
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


class TestDeliverableCheckGapReachesDispatch:
    """#642 — the gap helper's answer must actually reach the operator.

    `deliverable_check_gaps` is unit-tested in `test_buildplan_walkers.py`; this
    asserts the wiring, which is the half that was missing. A correct helper
    nobody calls leaves the check exactly as silently disabled as before, and
    the whole complaint in #642 is about *where* the signal appears: at dispatch,
    where the remedy is three lines of frontmatter — not at release, via
    `check-releasability`, long after the blind reviews have run.
    """

    def _plan(self, repo: Path, body: str) -> None:
        plans = repo / ".prawduct" / "artifacts"
        plans.mkdir(parents=True, exist_ok=True)
        (plans / "build-plan-thing.md").write_text(body)

    def test_unparseable_plan_notes_reach_stderr_at_dispatch(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        # No frontmatter `scope:`, and chunks as list items — both #642 routes.
        self._plan(
            repo,
            "## Status\n\n- [ ] Chunk 01: Do it\n\n## Chunks\n\n- Chunk 01: Do it\n",
        )
        _commit_file(repo, "plugin/lib/thing.py", "x = 1\n", "feat: a thing")
        # `chunk` diffs HEAD against the WORKING tree, so a fully-committed
        # fixture is an empty diff and never reaches dispatch.
        (repo / "plugin" / "lib" / "thing.py").write_text("x = 1\ny = 2\n")

        res = _run_begin(repo, "--mode", "chunk")

        assert "no frontmatter `scope:`" in res.stderr, (
            f"the scope gap never reached the operator: {res.stderr!r}"
        )
        assert "no parseable chunk heading" in res.stderr, (
            f"the heading gap never reached the operator: {res.stderr!r}"
        )
        assert "PRAWDUCT NOTE:" in res.stderr, "must ride the existing note channel"

    def test_the_signal_is_advisory_and_blocks_nothing(self, tmp_path):
        """Advice fails soft. The review is still worth running — what is not
        worth having is one that grades nothing while reporting cleanly — so
        this must not become a refusal, or #642's fix would cost more than the
        defect."""
        repo = tmp_path / "r"
        _init_repo(repo)
        self._plan(repo, "## Chunks\n\n- Chunk 01: Do it\n")
        _commit_file(repo, "plugin/lib/thing.py", "x = 1\n", "feat: a thing")
        (repo / "plugin" / "lib" / "thing.py").write_text("x = 1\ny = 2\n")

        res = _run_begin(repo, "--mode", "chunk")
        assert res.returncode == 0, (
            f"an advisory gap refused the dispatch: rc={res.returncode} {res.stderr!r}"
        )

    def test_a_conforming_plan_dispatches_silently(self, tmp_path):
        """No-false-positive: a template-shaped plan must produce neither note."""
        repo = tmp_path / "r"
        _init_repo(repo)
        self._plan(
            repo,
            "---\nartifact: build-plan\nscope: thing\n---\n\n"
            "## Status\n\n- [ ] Chunk 01: Do it\n\n"
            "## Build Chunks\n\n### Chunk 01: Do it\n\n- **Deliverables:** none\n",
        )
        _commit_file(repo, "plugin/lib/thing.py", "x = 1\n", "feat: a thing")
        (repo / "plugin" / "lib" / "thing.py").write_text("x = 1\ny = 2\n")

        res = _run_begin(repo, "--mode", "chunk")
        assert res.returncode == 0, f"fixture never dispatched: {res.stdout} {res.stderr}"
        assert "no frontmatter `scope:`" not in res.stderr
        assert "no parseable chunk heading" not in res.stderr


# ---------------------------------------------------------------------------
# A refusal names the tree it graded and the work that tree excludes
# ---------------------------------------------------------------------------


class TestARefusalNamesWhatItExcluded:
    """The refusal is correct; what it *reported* was not.

    `verify-resolutions` anchors at committed HEAD once a commit lands that the
    prior review never saw — the PR gate's target. Judgeable files still sitting
    uncommitted are outside that interval by construction, and refusing over it
    is right: reviewing the interval would not have covered them either. But
    "no judgeable file in a..b" is a statement about the *interval*, and the
    operator reads it as a statement about the *repo*. The observed cost is two
    dispatches for one review — commit, discover the delta exists after all,
    dispatch again.

    So the contract these tests pin is not "refuse less". It is: a refusal says
    which tree it graded, names the judgeable work that tree does not contain,
    and does not end on an instruction that would change nothing.
    """

    @staticmethod
    def _repro(repo: Path) -> None:
        """The issue's repro: a committed fix, plus uncommitted judgeable work."""
        _seed_prior_review(repo, findings=[])
        # Committed since the prior review, and non-judgeable — so the interval
        # this dispatch picks is free, which is what makes it refuse.
        _commit_file(repo, "docs/notes.md", "prose\n", "docs: a note")
        # Uncommitted and judgeable — invisible to that interval.
        (repo / "tests").mkdir(exist_ok=True)
        (repo / "tests" / "test_wip.py").write_text("def test_wip():\n    assert True\n")

    def test_the_refusal_names_the_excluded_judgeable_file(self, tmp_path):
        repo = tmp_path / "r"
        _init_repo(repo)
        self._repro(repo)

        result = _run_begin(repo, "--mode", "verify-resolutions")

        assert result.returncode == EXIT_NO_REVIEW_NEEDED, (
            f"rc={result.returncode} out={result.stdout!r} err={result.stderr!r}"
        )
        assert "tests/test_wip.py" in result.stdout, (
            "the refusal never named the judgeable uncommitted file it excluded — "
            f"the operator cannot tell a free interval from a missed one: {result.stdout!r}"
        )
        assert "committed HEAD" in result.stdout, (
            f"the refusal never said which tree it graded: {result.stdout!r}"
        )

    def test_the_refusal_does_not_claim_there_is_nothing_to_do(self, tmp_path):
        """The sentence that turned a partial answer into a wrong one."""
        repo = tmp_path / "r"
        _init_repo(repo)
        self._repro(repo)

        result = _run_begin(repo, "--mode", "verify-resolutions")

        assert "Nothing to do" not in result.stdout, (
            "work sits outside the graded interval, so 'nothing to do' is false — "
            f"{result.stdout!r}"
        )

    def test_the_correction_is_the_last_word(self, tmp_path):
        """A reader of a multi-line block acts on the final imperative.

        Above the exclusion notice that imperative is `--force`, which reviews
        the very interval that already excluded these files. Ordering is the
        behaviour here, not decoration.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        self._repro(repo)

        out = _run_begin(repo, "--mode", "verify-resolutions").stdout
        # rindex, not index: the route is mentioned twice, and the notice has to
        # clear the LAST of them to be what the reader acts on.
        assert out.index("tests/test_wip.py") > out.rindex("--force"), (
            f"the exclusion notice was buried above the --force route: {out!r}"
        )

    def test_a_clean_tree_still_reports_nothing_to_do(self, tmp_path):
        """No-false-positive: the ordinary free interval is unchanged."""
        repo = tmp_path / "r"
        _init_repo(repo)
        _seed_prior_review(repo, findings=[])
        _commit_file(repo, "docs/notes.md", "prose\n", "docs: a note")

        result = _run_begin(repo, "--mode", "verify-resolutions")

        assert result.returncode == EXIT_NO_REVIEW_NEEDED
        assert "Nothing to do" in result.stdout, (
            f"a genuinely free refusal lost its verdict: {result.stdout!r}"
        )
        assert "NOT REVIEWED" not in result.stdout, (
            f"a clean tree was reported as excluding work: {result.stdout!r}"
        )

    def test_non_judgeable_wip_is_not_reported_as_excluded(self, tmp_path):
        """Same predicate as the gate. A dirty tree holding only files the
        coverage gate waves through excludes nothing reviewable, and saying
        otherwise would send the operator to commit a scratch file."""
        repo = tmp_path / "r"
        _init_repo(repo)
        _seed_prior_review(repo, findings=[])
        _commit_file(repo, "docs/notes.md", "prose\n", "docs: a note")
        (repo / "docs" / "scratch.md").write_text("draft\n")

        import lib.critic_consolidate as cc

        # In-process for the reach-proof: the fixture has to actually enter the
        # dirty-tree branch, or the CLI assertion below passes forever on a tree
        # that came out clean. `excluded_wip == []` is that witness — `None`
        # would mean the diff failed, and a clean tree never reaches the branch.
        lib_result = cc.begin_review(repo, "verify-resolutions")
        assert lib_result["status"] == "no-review-needed", lib_result
        assert lib_result["excluded_wip"] == [], (
            f"the dirty-tree branch was never reached: {lib_result['excluded_wip']!r}"
        )

        result = _run_begin(repo, "--mode", "verify-resolutions")

        assert result.returncode == EXIT_NO_REVIEW_NEEDED
        assert "NOT REVIEWED" not in result.stdout, (
            f"non-judgeable WIP was reported as excluded work: {result.stdout!r}"
        )

    def test_the_guard_fact_records_what_was_excluded(self, tmp_path):
        """`free_files` alone cannot answer the guard's yield question once an
        anchor can exclude work: a refusal over a free interval that left
        judgeable files outside it is a different event from one over a clean
        tree, and only the record can tell them apart afterwards."""
        repo = tmp_path / "r"
        _init_repo(repo)
        self._repro(repo)

        assert _run_begin(
            repo, "--mode", "verify-resolutions"
        ).returncode == EXIT_NO_REVIEW_NEEDED

        facts = TestTheRefusalIsObservable._guard_facts(repo)
        assert len(facts) == 1, f"expected one guard-refusal fact, got {facts}"
        body = facts[0]["body"]
        assert body["excluded_wip"] == ["tests/test_wip.py"], (
            f"the record cannot distinguish this refusal from a clean one: {body}"
        )

    def test_the_refusal_forwards_the_notes_it_does_not_deliver_itself(self, tmp_path):
        """This path returned before `notes` reached ANY channel, so a note about
        something else entirely — here, a build plan the deliverable check cannot
        grade — was written and silently discarded.

        The dirty-tree note is the one exception, and for the opposite reason:
        the refusal block on stdout already names those files, so forwarding it
        too would print one fact twice in a single invocation.
        """
        repo = tmp_path / "r"
        _init_repo(repo)
        plans = repo / ".prawduct" / "artifacts"
        plans.mkdir(parents=True, exist_ok=True)
        (plans / "build-plan-thing.md").write_text("## Chunks\n\n- Chunk 01: Do it\n")
        self._repro(repo)

        result = _run_begin(repo, "--mode", "verify-resolutions")

        assert result.returncode == EXIT_NO_REVIEW_NEEDED
        assert "PRAWDUCT NOTE:" in result.stderr, (
            f"the dispatch's own notes were dropped on the refusal path: {result.stderr!r}"
        )

    def test_the_exclusion_is_delivered_exactly_once(self, tmp_path):
        """"Printed LAST, deliberately" is a claim about what the reader meets
        at the end of the block. It is only true if the same fact does not turn
        up again on the other stream a line later."""
        repo = tmp_path / "r"
        _init_repo(repo)
        self._repro(repo)

        result = _run_begin(repo, "--mode", "verify-resolutions")

        both = result.stdout + result.stderr
        assert both.count("tests/test_wip.py") == 1, (
            f"the excluded file was named {both.count('tests/test_wip.py')} times "
            f"in one invocation:\nSTDOUT {result.stdout!r}\nSTDERR {result.stderr!r}"
        )

    def test_a_dirty_cumulative_names_its_exclusions_too(self, tmp_path):
        """`cumulative` has always anchored committed HEAD and always noted a
        dirty tree without naming anything. Same fact, same carrier."""
        import lib.critic_consolidate as cc

        repo = tmp_path / "r"
        _init_repo(repo)
        _commit_file(repo, "README.md", "start\n", "chore: init")
        _git(repo, "checkout", "--quiet", "-b", "feature/x")
        _commit_file(repo, "src/app.py", "x = 1\n", "feat: a thing")
        (repo / "src" / "wip.py").write_text("y = 2\n")  # judgeable, uncommitted

        result = cc.begin_review(repo, "cumulative")

        assert result["status"] == "ok", result
        assert any("src/wip.py" in n for n in result["notes"]), (
            f"the cumulative dirty-tree note named nothing: {result['notes']}"
        )


# ---------------------------------------------------------------------------
# A check that could not run is not a clean bill
# ---------------------------------------------------------------------------


class TestAnUncomputableWipDiffIsNotAnAllClear:
    """`evidence.tree_diff` returns ``None`` when the diff cannot be computed —
    a missing object, a git failure — and never guesses. Collapsing that into
    ``[]`` makes the one report written to catch work falling outside an
    interval answer "nothing fell outside" on the strength of a check that never
    ran, which is the fail-open direction in the fail-closed half of the system.

    Driven in-process because the failure has to be *injected*: no filesystem
    state reliably makes git fail on that diff on every machine.
    """

    @staticmethod
    def _fail_the_wip_diff(monkeypatch, repo: Path):
        """Break exactly the head_tree→working_tree diff, nothing else.

        Breaking `tree_diff` wholesale would take the interval down with it and
        the dispatch would fail earlier, for a different reason — the test would
        then pass without ever reaching the branch it names.
        """
        import lib.evidence as ev

        cap = ev.capture_tree(repo)
        real = ev.tree_diff

        def fake(project_dir, tree_a, tree_b, paths=None):
            if tree_a == cap["head_tree"] and tree_b == cap["tree"]:
                return None
            return real(project_dir, tree_a, tree_b, paths)

        monkeypatch.setattr(ev, "tree_diff", fake)

    def test_the_refusal_reports_unknown_rather_than_empty(self, tmp_path, monkeypatch):
        import lib.critic_consolidate as cc

        repo = tmp_path / "r"
        _init_repo(repo)
        TestARefusalNamesWhatItExcluded._repro(repo)
        self._fail_the_wip_diff(monkeypatch, repo)

        result = cc.begin_review(repo, "verify-resolutions")

        assert result["status"] == "no-review-needed", result
        assert result["excluded_wip"] is None, (
            "a diff that could not be computed was reported as 'nothing "
            f"excluded': {result['excluded_wip']!r}"
        )

    def test_the_guard_fact_records_unknown_as_null(self, tmp_path, monkeypatch):
        """`[]` and `null` are different answers to the retirement question, and
        the record is the only place it can be asked later."""
        import lib.critic_consolidate as cc

        repo = tmp_path / "r"
        _init_repo(repo)
        TestARefusalNamesWhatItExcluded._repro(repo)
        self._fail_the_wip_diff(monkeypatch, repo)

        assert cc.begin_review(repo, "verify-resolutions")["status"] == "no-review-needed"

        body = TestTheRefusalIsObservable._guard_facts(repo)[0]["body"]
        assert body["excluded_wip"] is None, (
            f"the record cannot tell 'nothing excluded' from 'could not tell': {body}"
        )

    def test_the_cli_withholds_the_all_clear(self, tmp_path, monkeypatch, capsys):
        """The rendering half. "Nothing to do" is an all-clear, and only a check
        that ran may issue one."""
        hook = _load_hook()
        repo = tmp_path / "r"
        _init_repo(repo)
        TestARefusalNamesWhatItExcluded._repro(repo)
        self._fail_the_wip_diff(monkeypatch, repo)
        # `cmd_critic_begin` refuses when cwd resolves to a different tree than
        # the review (PDT-WT9K), so the shell has to be inside the fixture.
        monkeypatch.chdir(repo)

        rc = hook.cmd_critic_begin(repo, ["--mode", "verify-resolutions"])
        out = capsys.readouterr().out

        assert rc == EXIT_NO_REVIEW_NEEDED, out
        assert "Nothing to do" not in out, (
            f"an unverifiable tree was reported as an all-clear: {out!r}"
        )
        assert "UNVERIFIED" in out, f"the unknown answer never printed: {out!r}"
        # Last word, same reason as the NOT REVIEWED block.
        assert out.index("UNVERIFIED") > out.rindex("--force"), (
            f"the caveat was buried above the --force route: {out!r}"
        )


class TestAnErrorReturnKeepsItsNotes:
    """The refusal path was not the only return that computed notes and then
    left past them. `scope-widened` is the one error return that reaches its
    `return` with `notes` populated — and it fires exactly when the tree has
    grown enough that what the dispatch noticed about it is worth having.
    """

    @staticmethod
    def _widen(repo: Path) -> None:
        """A delta wide enough to trip `_scope_widened` (> 2x prior + 5), plus a
        dirty tree so the committed anchor has something to note."""
        _seed_prior_review(repo, findings=[])  # 3 files reviewed
        for i in range(14):
            _commit_file(repo, f"src/gen{i}.py", "x = 1\n", f"feat: gen{i}")
        (repo / "src" / "dirty.py").write_text("y = 2\n")

    def test_the_scope_widened_error_carries_the_notes(self, tmp_path):
        import lib.critic_consolidate as cc

        repo = tmp_path / "r"
        _init_repo(repo)
        self._widen(repo)

        result = cc.begin_review(repo, "verify-resolutions")

        assert result.get("kind") == "scope-widened", result
        assert any("src/dirty.py" in n for n in result.get("notes") or []), (
            "the dispatch noticed judgeable uncommitted work and then returned "
            f"past it: {result.get('notes')}"
        )

    def test_the_cli_prints_notes_before_the_reason(self, tmp_path):
        """Notes first, reason last: the reason is what the reader acts on, and
        a reader of a multi-line block acts on the final line."""
        repo = tmp_path / "r"
        _init_repo(repo)
        self._widen(repo)

        result = _run_begin(repo, "--mode", "verify-resolutions")

        assert result.returncode == 2, (
            f"rc={result.returncode} out={result.stdout!r} err={result.stderr!r}"
        )
        assert "PRAWDUCT NOTE:" in result.stderr, (
            f"the error path dropped the dispatch's notes: {result.stderr!r}"
        )
        assert result.stderr.index("PRAWDUCT NOTE:") < result.stderr.index(
            "critic-begin: scope-widened"
        ), f"the reason was buried above the notes: {result.stderr!r}"


class TestDispatchAnchorsToTheWorktree:
    """`critic-begin` measures the tree it was run in, not the primary checkout.

    This is the property the reviewer's `git -C <dir> rev-parse HEAD` check
    compares against (#147), so it is pinned rather than assumed: if dispatch
    ever recorded the primary checkout's HEAD, the reviewer would abort on every
    worktree review and the check would read as the defect.

    A linked worktree is the sharpest available case - one repository, two
    working trees, two branches, two HEADs, one shared object store - and it is
    how this framework's own parallel work is done.
    """

    def _worktree_repo(self, tmp_path: Path) -> tuple[Path, Path, str, str]:
        repo = tmp_path / "repo"
        _init_repo(repo)
        primary_head = _commit_file(repo, "src/a.py", "def a():\n    return 1\n", "feat: a")
        wt = tmp_path / "wt"
        _git(repo, "worktree", "add", "-b", "feature", str(wt))
        (wt / ".prawduct").mkdir(exist_ok=True)
        wt_head = _commit_file(wt, "src/b.py", "def b():\n    return 2\n", "feat: b")
        return repo, wt, primary_head, wt_head

    def test_the_two_trees_really_do_disagree(self):
        """The control. Without this, every assertion below could pass on a
        setup where both paths lead to the same commit anyway."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            repo, wt, primary_head, wt_head = self._worktree_repo(Path(td))
            assert primary_head != wt_head
            assert _git(repo, "rev-parse", "HEAD").stdout.strip() == primary_head
            assert _git(wt, "rev-parse", "HEAD").stdout.strip() == wt_head

    def test_manifest_records_the_worktree_not_the_primary_checkout(self, tmp_path):
        repo, wt, primary_head, wt_head = self._worktree_repo(tmp_path)
        (wt / "src" / "c.py").write_text("def c():\n    return 3\n")

        result = _run_begin(wt, "--mode", "chunk", "--chosen-by", "test", "--tier", "standard")
        assert result.returncode == 0, result.stderr

        assert (wt / PARTIALS_REL / "manifest.json").is_file()
        assert not (repo / PARTIALS_REL / "manifest.json").exists(), (
            "dispatch wrote its manifest into the primary checkout - the review "
            "state and the reviewed tree must be the same tree"
        )
        manifest = json.loads((wt / PARTIALS_REL / "manifest.json").read_text())
        assert manifest["commit_reviewed"] == wt_head
        assert manifest["commit_reviewed"] != primary_head
        assert manifest["branch"] == "feature"

    def test_manifest_carries_an_absolute_worktree_path_for_the_dispatch_prompt(self, tmp_path):
        """The coordinator substitutes `[dir]` from this field, so it has to be
        absolute at the source rather than absolute by the coordinator's care."""
        repo, wt, _primary_head, _wt_head = self._worktree_repo(tmp_path)
        (wt / "src" / "c.py").write_text("def c():\n    return 3\n")
        assert _run_begin(wt, "--mode", "chunk", "--chosen-by", "test", "--tier", "standard").returncode == 0

        manifest = json.loads((wt / PARTIALS_REL / "manifest.json").read_text())
        recorded = manifest.get("worktree")
        assert recorded, "the manifest must name the tree it measured"
        assert Path(recorded).is_absolute()
        assert Path(recorded).resolve() == wt.resolve()
