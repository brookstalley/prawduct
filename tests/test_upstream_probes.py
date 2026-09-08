"""Tests for the upstream-bug-reporting receiving-side probe.

The probe counts the **issue intake set** — open items on prawduct's own tracker
whose title carries the ``[prawduct]`` convention and which nobody has staged
(``documentation/backlog-service-upstream-filing.md`` §6). Three properties are
worth more than the count itself and each has a test: it is silent everywhere but
the upstream target, it never carries a filer's words into the briefing, and it
says *unknown* rather than *none* when the local copy cannot be read.

**Every case here reaches the subject.** A cache-backed probe is easy to test into
a false green — this repo has already paid for one, where a probe reported
`unreadable` under CI and the assertion passed having never looked at what it
claimed to check. So each test below builds a real store through the real sync
path and asserts on a decision the probe made *about that store*, and the silent
cases assert why they are silent rather than merely that nothing came back.

All offline: no ``gh``, no network.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from lib.advisory_store import (  # noqa: E402
    Codebase,
    clear_registry,
    compute_id,
    load_project_state,
    make_codebase,
    run_all_probes,
)
from lib import upstream_probes as up  # noqa: E402
from lib.backlog import cache, cachequery, core, sync, transport, upstream  # noqa: E402
from fakes.fake_github import FakeGitHub  # noqa: E402

# The probe is keyed on the pinned target, so the fixtures must BE it — reading
# the constant rather than spelling it keeps the test honest if the target moves.
OWNER, REPO = upstream.PINNED_TARGET.split("/")
NOW = datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _isolated_registry():
    clear_registry()
    yield
    clear_registry()


@pytest.fixture
def fake():
    return FakeGitHub(user={"login": "agent-a", "id": 1})


def _repo(tmp_path, *, identity: str | None = upstream.PINNED_TARGET, origin: str | None = None):
    """A real git work tree whose backlog store is ``identity``.

    ``cache_path`` resolves through ``--git-common-dir``, so the ``git init`` is
    load-bearing rather than scenery. ``origin`` is separate and defaults to
    absent: the two are different facts about a repo, and a fixture that could
    only set them together could not express the case where they disagree.
    """
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    if origin is not None:
        subprocess.run(
            ["git", "remote", "add", "origin", f"https://github.com/{origin}.git"],
            cwd=tmp_path,
            check=True,
        )
    prawduct = tmp_path / ".prawduct"
    prawduct.mkdir(exist_ok=True)
    state = "" if identity is None else f"backlog_service_repo: {identity}\n"
    (prawduct / "project-state.yaml").write_text(state, encoding="utf-8")
    return tmp_path


def _filed_report(
    fake,
    *,
    component: str,
    symptom: str,
    body: str = "what happened",
    owner: str = OWNER,
    repo: str = REPO,
) -> str:
    """One report as ``file-upstream`` actually leaves it, composed by the real op.

    Built through :func:`upstream.build_payload` rather than by hand-spelling a
    title, and that is a coupling rather than a convenience: the intake set exists
    only because the outbound payload carries the title convention and no labels,
    so a fixture that spelled those itself would keep passing after the payload
    stopped producing them. The filing side and the counting side are pinned
    against each other here.
    """
    payload = upstream.build_payload(
        title=symptom,
        body=body,
        component=component,
        found_in="prawduct v3.4.1-dev.2",
        submitter="octo/product",
    )
    assert payload is not None, "the fixture's own inputs must compose a real payload"
    issue = fake.create_issue(
        owner, repo, title=payload["title"], body=payload["body"], labels=payload["labels"]
    )
    return f"{owner}/{repo}#{issue['number']}"


def _own_item(fake, *, title: str, **facets) -> str:
    result = core.file_item(fake, owner=OWNER, repo=REPO, title=title, body="b", facets=facets)
    assert result["status"] == "ok", result
    return result["data"]["id"]


def _rebuild(fake, repo_dir, *, owner: str = OWNER, repo: str = REPO):
    """Sync the fake's issues into the store, under the spelling given.

    ``owner``/``repo`` are overridable because the cache scope is the spec as
    *declared*, not as canonicalized, and a fixture that could only write the one
    spelling could not express a repo whose declaration disagrees in case.
    """
    result = sync.full_rebuild(fake, project_dir=repo_dir, owner=owner, repo=repo, now=NOW)
    assert result["status"] == "ok", result
    return result


def _run(repo_dir):
    """The probe as the runtime calls it — state parsed from the repo's own file.

    Not ``ProjectState({})`` with the identity passed separately: the gate and the
    fixture would then have two sources for one fact, and a test can only catch a
    disagreement between them if they come from the same place the runtime reads.
    """
    return up.probe_untriaged_upstream_reports(
        load_project_state(repo_dir), Codebase(root=repo_dir)
    )


class TestItCountsTheIntakeSet:
    def test_it_fires_once_with_the_number_of_filed_reports(self, fake, tmp_path):
        repo_dir = _repo(tmp_path)
        _filed_report(fake, component="stop-hook", symptom="gate blocks on background work")
        _filed_report(fake, component="critic", symptom="consolidate reads a stale file")
        _rebuild(fake, repo_dir)

        out = _run(repo_dir)

        assert len(out) == 1
        assert out[0].type == "untriaged-upstream-reports"
        assert out[0].trigger_summary.startswith("2 ")
        assert out[0].recommended_action == "/prawduct:backlog"

    def test_a_staged_report_has_been_triaged_and_drops_out(self, fake, tmp_path):
        """The whole point of the set: it empties as a maintainer works it."""
        repo_dir = _repo(tmp_path)
        waiting = _filed_report(fake, component="backlog", symptom="import drops a facet")
        _rebuild(fake, repo_dir)
        assert len(_run(repo_dir)) == 1, "control: it was in the set before staging"

        assert core.update_item(fake, id_raw=waiting, fields={"stage": "ready"})["status"] == "ok"
        _rebuild(fake, repo_dir)

        assert _run(repo_dir) == []

    def test_this_repos_own_unstaged_backlog_is_not_intake(self, fake, tmp_path):
        """Untriaged and *filed from outside* are different sets, and only one is this.

        prawduct's own backlog routinely holds unstaged items; counting them here
        would report the framework's grooming debt as somebody else's bug report.
        """
        repo_dir = _repo(tmp_path)
        _own_item(fake, title="backlog: an item nobody has staged yet", area="backlog")
        _rebuild(fake, repo_dir)

        assert _run(repo_dir) == []

    def test_it_counts_the_prefixed_ones_among_a_mixed_backlog(self, fake, tmp_path):
        repo_dir = _repo(tmp_path)
        _own_item(fake, title="backlog: an item nobody has staged yet", area="backlog")
        _own_item(fake, title="critic: a staged item", area="critic", stage="ready")
        _filed_report(fake, component="doctor", symptom="repair skips a gate")
        _rebuild(fake, repo_dir)

        out = _run(repo_dir)

        assert len(out) == 1
        assert out[0].trigger_summary.startswith("1 ")


class TestItIsSilentAwayFromTheTarget:
    def test_a_product_repo_is_inapplicable_not_merely_empty(self, fake, tmp_path):
        """Inert by identity: a product never receives, so it is never asked.

        Asserted against a store that WOULD fire — same rows, same cache — so the
        silence is attributable to the identity check and not to an empty backlog.
        """
        repo_dir = _repo(tmp_path, identity="octo/product")
        _filed_report(fake, component="stop-hook", symptom="gate blocks on background work")
        _rebuild(fake, repo_dir)

        assert up._is_the_upstream_target(load_project_state(repo_dir)) is False
        assert _run(repo_dir) == []
        assert up._untriaged_report_count(
            load_project_state(repo_dir), Codebase(root=repo_dir)
        ) == 1, (
            "control: the cache the probe declined to read does hold a report"
        )

    def test_a_repo_with_no_backlog_store_is_inapplicable(self, fake, tmp_path):
        repo_dir = _repo(tmp_path, identity=None)
        _filed_report(fake, component="stop-hook", symptom="gate blocks on background work")
        _rebuild(fake, repo_dir)

        assert _run(repo_dir) == []

    def test_an_origin_pointing_at_the_target_is_not_enough(self, fake, tmp_path):
        """A clone of prawduct whose backlog lives elsewhere is not a receiver.

        The filing side's identity resolver admits ``backlog_service_repo`` *or*
        ``origin``, which is right for a refusal and wrong here: this repo would
        pass such a gate, then read a scope nothing syncs and nag every session
        with an *unknown* nobody could clear. The gate and the scope must select
        one store, and this is the case that tells them apart.
        """
        repo_dir = _repo(tmp_path, identity="octo/product", origin=upstream.PINNED_TARGET)
        _filed_report(fake, component="stop-hook", symptom="gate blocks on background work")
        _rebuild(fake, repo_dir)

        assert upstream.PINNED_TARGET in upstream.resolve_self_identity(repo_dir), (
            "control: the broader identity resolver DOES admit this repo"
        )
        assert _run(repo_dir) == []


class TestTheGateAndTheQuerySelectOneStore:
    def test_the_scope_it_queries_is_the_spelling_that_was_declared(
        self, fake, tmp_path, monkeypatch
    ):
        """Compare canonicalized, look up verbatim — the two forms are not swappable.

        GitHub owner and repo names are case-insensitive, so the gate has to fold
        case or a stray capital walks past it. The store does not fold: ``sync``
        keys its cursor and its sync-health row on the spec exactly as declared.

        **Asserted at the seam rather than through a behaviour, because there is no
        behaviour to assert.** ``item`` carries no scope column — the scope selects
        the freshness stamp and the sync-error warning, not the rows — so a
        canonicalized lookup today returns the same count via
        ``oldest_fetched_at``'s fallback and nothing downstream would go red. That
        makes this a contract test on purpose: what it pins is which string is
        handed over, which is the thing a future scope-filtered read would depend
        on and the thing a reader of the code cannot otherwise check.
        """
        spelled = "BrooksTalley/Prawduct"
        assert upstream.canonical_repo(spelled) == upstream.PINNED_TARGET, (
            "control: the gate must still admit this spelling"
        )
        assert spelled != upstream.PINNED_TARGET, "control: and it really does differ"
        repo_dir = _repo(tmp_path, identity=spelled)
        _filed_report(
            fake,
            component="doctor",
            symptom="repair skips a gate",
            owner="BrooksTalley",
            repo="Prawduct",
        )
        _rebuild(fake, repo_dir, owner="BrooksTalley", repo="Prawduct")

        seen = []
        real = cachequery.unstaged_items

        def _spy(project_dir, *, scope, now):
            seen.append(scope)
            return real(project_dir, scope=scope, now=now)

        monkeypatch.setattr(up.cachequery, "unstaged_items", _spy)

        out = _run(repo_dir)

        assert seen == [spelled]
        assert len(out) == 1 and out[0].trigger_summary.startswith("1 ")


class TestUnknownIsNotNone:
    def test_an_unreadable_cache_fires_and_names_the_consequence(self, fake, tmp_path):
        """Advice fails soft, not silent — a broken count must not read as zero."""
        repo_dir = _repo(tmp_path)
        _filed_report(fake, component="pr", symptom="merge falls back to squash")
        _rebuild(fake, repo_dir)
        assert len(_run(repo_dir)) == 1, "control: it fired while the cache was readable"

        store = cache.cache_path(repo_dir)
        assert store is not None and store.exists(), "control: the store the test breaks exists"
        store.unlink()

        out = _run(repo_dir)

        assert len(out) == 1
        assert up._untriaged_report_count(
            load_project_state(repo_dir), Codebase(root=repo_dir)
        ) is None
        assert "unknown" in out[0].trigger_summary
        assert out[0].evidence != ()

    def test_the_two_shapes_carry_different_ids(self, fake, tmp_path):
        """Same type, different id — so dismissing one does not dismiss the other.

        Asserted through ``compute_id`` rather than through the evidence tuples it
        hashes: the id is what a dismissal is keyed on, and two distinguishable
        evidence tuples that collided in the digest would satisfy the weaker claim
        while breaking the one that matters.
        """
        repo_dir = _repo(tmp_path)
        _filed_report(fake, component="pr", symptom="merge falls back to squash")
        _rebuild(fake, repo_dir)
        counted = _run(repo_dir)[0]

        store = cache.cache_path(repo_dir)
        assert store is not None
        store.unlink()
        unknown = _run(repo_dir)[0]

        def _id(candidate):
            return compute_id(up.FEATURE, candidate.type, up.PROBE_VERSION, candidate.evidence)

        assert _id(counted) != _id(unknown)


class TestNothingAFilerWroteReachesTheReader:
    def test_no_text_from_a_filed_issue_appears_in_the_candidate(self, fake, tmp_path):
        """Filed issues are foreign-authored, and advisory text lands in context.

        The marker is distinctive enough that a substring check over every emitted
        field is a real quantifier rather than a spot check.
        """
        marker = "zzqxfilerauthoredmarker"
        repo_dir = _repo(tmp_path)
        _filed_report(
            fake, component=marker, symptom=f"{marker} broke", body=f"body says {marker}"
        )
        _rebuild(fake, repo_dir)

        out = _run(repo_dir)
        assert len(out) == 1, "control: the marked report is what fired this"
        emitted = " ".join(
            [
                out[0].type,
                out[0].trigger_summary,
                out[0].owner_action,
                out[0].recommended_action,
                *out[0].evidence,
                *out[0].alternative_actions,
            ]
        )
        assert marker not in emitted

    def test_evidence_is_count_independent(self, fake, tmp_path):
        """Evidence is hashed into the advisory id, so the id must not churn (D14)."""
        repo_dir = _repo(tmp_path)
        _filed_report(fake, component="doctor", symptom="repair skips a gate")
        _rebuild(fake, repo_dir)
        one = _run(repo_dir)

        _filed_report(fake, component="janitor", symptom="sweep misses a directory")
        _rebuild(fake, repo_dir)
        two = _run(repo_dir)

        assert one[0].evidence == two[0].evidence
        assert one[0].trigger_summary.startswith("1 ")
        assert two[0].trigger_summary.startswith("2 ")


class TestItStaysOffTheNetwork:
    def test_the_probe_reaches_git_but_never_gh(self, tmp_path, fake, monkeypatch):
        """Session start reads the local copy; it must not reach the provider.

        Asserted at the **process egress**, which is where the absence lives: a
        counter on some object the probe never receives cannot move whatever the
        probe does. So the guard sits on ``subprocess.run`` and forbids exactly
        ``gh``, and on ``spawn_detached`` by name. Both narrow deliberately — the
        probe legitimately spawns ``git rev-parse --git-common-dir`` to locate the
        clone-shared store, and a blanket ban would refuse that call and route the
        probe into its degraded branch, where an assertion counting *candidates*
        goes green having never reached the counting path at all.

        Two things make that unfaked: both interceptions are proved to bite before
        either is relied on, and the assertion is on the **counted** summary, which
        only the path under test can produce.
        """
        repo_dir = _repo(tmp_path)
        _filed_report(fake, component="doctor", symptom="repair skips a gate")
        _rebuild(fake, repo_dir)

        real_run = transport.subprocess.run

        def _no_gh(argv, *args, **kwargs):
            if argv and str(argv[0]) == "gh":
                raise AssertionError(f"the probe reached the provider: {argv}")
            return real_run(argv, *args, **kwargs)

        def _no_spawn(*args, **kwargs):
            raise AssertionError(f"the probe spawned a detached call: {args}")

        monkeypatch.setattr(transport.subprocess, "run", _no_gh)
        monkeypatch.setattr(transport, "spawn_detached", _no_spawn)

        with pytest.raises(AssertionError, match="reached the provider"):
            transport.subprocess.run(["gh", "--version"])
        with pytest.raises(AssertionError, match="spawned a detached call"):
            transport.spawn_detached(["gh", "issue", "list"], cwd=repo_dir)

        out = _run(repo_dir)

        assert len(out) == 1
        assert out[0].trigger_summary.startswith("1 "), (
            "the degraded branch must not be what satisfies this case"
        )


def test_register_runs_in_the_roster(fake, tmp_path):
    repo_dir = _repo(tmp_path)
    _filed_report(fake, component="doctor", symptom="repair skips a gate")
    _rebuild(fake, repo_dir)
    up.register()
    up.register()  # idempotent — register_probe overwrites

    cands = run_all_probes(load_project_state(repo_dir), make_codebase(repo_dir))

    fired = [c for c in cands if c.type == "untriaged-upstream-reports"]
    assert len(fired) == 1
    assert fired[0].feature == "report-bug"
    assert fired[0].probe_version == up.PROBE_VERSION
