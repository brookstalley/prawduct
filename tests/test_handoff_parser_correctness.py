"""Build-plan read-path correctness — the parse that feeds the session handoff.

Four independent wrong-output defects were reproduced against this repo's own
live build plan (SCN-4H9T, BLD-7K3Q), all in the path from build-plan Status to
``.session-handoff.md``:

* a completed plan was reported as the next session's active ``**Task**`` —
  ``staleness_scan`` applied a done-predicate and ``_get_active_work`` read the
  *identical* parse without one;
* the current chunk was read as "first ``- [ ]``" against Status checkboxes that
  were a derived view flipping only at release, so it was Chunk 01 forever;
* a frontmatter-style plan (no ``# Build Plan`` H1) produced no description, and
  description is the sole key gating the handoff's whole Work In Progress
  section, so the section silently vanished;
* ``Context:`` was read as one physical line, truncating the multi-paragraph
  block ``building.md`` calls "the cross-session handoff".

Real ``git init`` repos throughout: the defects survived unit-level correctness
for months precisely because nothing exercised the real path.

The second defect was fixed three times. First by deriving progress from git
commits when the checkboxes could not be trusted — two readings of one question,
with a precedence between them. Then by retiring the derived view, so a ticked
box was a statement the builder made. Then (#1051) by taking the box out of the
answer: a chunk is done when a review fact certifies it, and
``plan_status.chunk_states`` is the one walker every consumer reads. What remains
from the git era is a **report**, not a reading — ``built_not_done_notice`` —
naming committed work no review has certified yet.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib import (  # noqa: E402
    briefing, buildplan_refs, critic_mode, evidence, gates, plan_index, plan_status, work_unit,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_env(repo: Path) -> dict[str, str]:
    return {
        "HOME": str(repo.parent / "_home"),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
    }


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=_git_env(repo),
        check=True,
        timeout=10,
    )


def _init_repo(repo: Path, *, branch: str = "main") -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "--quiet", "-b", branch)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _commit(repo: Path, msg: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", msg, "--quiet", "--allow-empty")


def _write_plan(project_dir: Path, content: str) -> Path:
    plan = project_dir / ".prawduct" / "artifacts" / "build-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(content)
    return plan


def _write_state(project_dir: Path, content: str) -> None:
    state = project_dir / ".prawduct" / "project-state.yaml"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(content)


# A plan mid-flight under the single reading: chunks 01-03 ticked by the builder,
# 04 open. `- [x]` is a statement, not a regenerated value.
LIVE_PLAN = """---
artifact: build-plan
scope: session-handoff-continuity
---

## Status

- [x] Chunk 01: The forward channel
- [x] Chunk 02: Parser correctness
- [x] Chunk 03: Proactive close
- [ ] Chunk 04: The Critic summary

Context: Chunks 01-03 shipped.

## Build Chunks

### Chunk 02: Parser correctness
- **Type:** code

### Chunk 04: The Critic summary
- **Type:** code
- **Critic mode:** final

Touches `.prawduct/artifacts/build-plan.md`.
"""


def _live_repo(tmp_path: Path, *, commit_chunk: int | None = 4) -> Path:
    """Chunks 01-03 ticked; 04 open and — by default — already COMMITTED.

    That combination is deliberate and makes the fixture discriminating rather
    than merely representative. Every consumer must answer "04", which is what
    the boxes say; the retired git-derived reading would have counted 04 as done
    too and answered "nothing current". So a consumer that quietly reintroduced a
    commit-derived reading fails here instead of agreeing by coincidence.

    It is also a state the built-but-not-done notice reports (04 is committed
    and no review certifies it), so one fixture carries both halves: the answer
    decides, and the discrepancy is reported rather than silently resolved.
    """
    repo = tmp_path / "repo"
    _init_repo(repo, branch="develop")
    _write_state(repo, "base_branch: develop\n")
    _write_plan(repo, LIVE_PLAN)
    _commit(repo, "chore: plan")
    _git(repo, "checkout", "-b", "feature/session-handoff-continuity", "--quiet")
    if commit_chunk is not None:
        _commit(repo, f"feat(continuity): land it (Chunk 0{commit_chunk})")
    return repo


# Defect 4 — one reading of chunk progress, at EVERY consumer
# ---------------------------------------------------------------------------


class TestSingleReadingCurrentChunk:
    """Chunks 01-03 ticked, 04 open and committed. Every consumer must say 04."""

    def test_verify_chunk_refs_grades_the_right_chunk(self, tmp_path: Path):
        """BLD-7K3Q: the gate reported `ok: chunk 01` for a whole branch while
        chunks 02..N went unverified — silently, and green.

        Asserted POSITIVELY. A `"01" not in stdout` check passes on empty
        stdout, which is what a `cannot-verify` exit produces — so it would
        have gone green against the pre-fix code too.
        """
        repo = _live_repo(tmp_path)
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "bin" / "prawduct-hook"), "verify-chunk-refs"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            env={**_git_env(repo), "CLAUDE_PROJECT_DIR": str(repo)},
            timeout=30,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "ok: chunk 04" in proc.stdout, proc.stdout + proc.stderr

    def test_mode_inference_routes_through_the_single_owner(
        self, tmp_path: Path, monkeypatch
    ):
        """`infer_mode` must not re-derive which chunk is current.

        Asserted by DEPENDENCE, not by agreement: two functions returning "04"
        is equally true of an `infer_mode` that derives "04" for itself. So
        redirect the owner and require `infer_mode`'s answer to move with it.
        Chunk 04 declares `**Critic mode:** final`; Chunk 02 declares none, so
        the plan-override appears only when 04 is the resolved chunk.

        Ported to the owner #1051 made it (`plan_status.current_chunks`, read by
        `critic_mode.binding_progress`): the redirect is applied THERE. The
        Status reader it used to redirect is deleted (Chunk 06).
        """
        repo = _live_repo(tmp_path)
        mode, rationale = critic_mode.infer_mode(repo)
        assert (mode, rationale) == ("final", "plan-override: final")

        monkeypatch.setattr(
            critic_mode.plan_status,
            "current_chunks",
            # The stub ignores the plan it is asked about: what is under test is
            # that the ANSWER comes from the owner, not which file it was given.
            lambda *_a, **_k: ["02", "04"],
        )
        assert critic_mode.infer_mode(repo)[1] != "plan-override: final", (
            "infer_mode ignored the resolver — it is re-deriving which chunk is "
            "current for itself"
        )

    def test_briefing_resume_line_names_the_right_chunk(self, tmp_path: Path):
        repo = _live_repo(tmp_path)
        text = briefing.assemble_session_briefing(repo, [])
        assert "Resume: Chunk 04: The Critic summary" in text

    def test_handoff_names_the_right_chunk(self, tmp_path: Path):
        repo = _live_repo(tmp_path)
        briefing.generate_session_handoff(repo)
        handoff = (repo / ".prawduct" / ".session-handoff.md").read_text()
        assert "**Current chunk**: Chunk 04: The Critic summary" in handoff

    def test_handoff_reports_a_completed_plan_as_finished(self, tmp_path: Path):
        """SCN-4H9T end-to-end, renegotiated by #1051 (was
        `test_handoff_omits_work_section_for_a_completed_plan`).

        The defect was a finished plan stamped as the next session's work "in
        progress" while `staleness_scan` called it complete from the same bytes.
        The handoff and the briefing now read `plan_status`, and a finished
        plan's work section says `**Current chunk**: finished` rather than
        naming a chunk — the two readers cannot disagree — instead of vanishing,
        because the plan stays live until it is archived and the next session
        should be told what it is. Asserted on the COMPOSED path
        (`generate_session_handoff`), which is what reaches a reader.
        """
        _init_repo(tmp_path)
        _write_plan(
            tmp_path,
            "# Build Plan — Done (2026-07-26)\n\n## Status\n\n- [x] Chunk 01: A\n",
        )
        (tmp_path / ".prawduct" / ".session-reflected").write_text("did the thing")
        briefing.generate_session_handoff(tmp_path)
        handoff = (tmp_path / ".prawduct" / ".session-handoff.md").read_text()
        assert "## Work In Progress" in handoff
        assert "**Current chunk**: finished\n" in handoff
        assert "**Current chunk**: Chunk" not in handoff
        assert "did the thing" in handoff

    def test_handoff_names_the_open_chunk_of_an_unfinished_plan(self, tmp_path: Path):
        """The control for the test above: the same plan with its box unticked
        names the chunk, so `finished` is the state's answer, not a constant."""
        _init_repo(tmp_path)
        _write_plan(
            tmp_path,
            "# Build Plan — Done (2026-07-26)\n\n## Status\n\n- [ ] Chunk 01: A\n",
        )
        briefing.generate_session_handoff(tmp_path)
        handoff = (tmp_path / ".prawduct" / ".session-handoff.md").read_text()
        assert "**Current chunk**: Chunk 01: A\n" in handoff

    def test_a_done_chunk_after_the_current_one_still_counts_as_done(
        self, tmp_path: Path
    ):
        """Done-ness is per-chunk and non-contiguous. The retired git reading
        reported a bare COUNT, so callers approximated with the roster prefix
        before the current chunk and under-reported a done chunk sitting after
        it. Ported from the box reader to `plan_status`: 01, 02 and 04 done
        (here as unmigrated boxes), 03 the only open chunk."""
        repo = _live_repo(tmp_path)
        plan = _write_plan(
            repo,
            LIVE_PLAN.replace("- [x] Chunk 03", "- [ ] Chunk 03").replace(
                "- [ ] Chunk 04", "- [x] Chunk 04"
            ),
        )
        states = plan_status.chunk_states(plan, None, repo_dir=repo)
        assert {k: s.state for k, s in states.items()} == {
            "02": "done", "04": "done", "01": "done", "03": "open",
        }
        assert plan_status.current_chunks(plan, None, repo_dir=repo, states=states) == ["03"]


# A plan that CLAIMS its branch, so a review fact's anchor can be placed on it
# and certify a chunk; `_live_repo`'s plan binds through the legacy route and
# declares no branch, so nothing could certify it.
CLAIMED_PLAN = """---
artifact: build-plan
scope: notice
branch: feature/notice
---

## Build Chunks

### Chunk 01: The first half

### Chunk 02: The second half
"""


def _claimed_repo(tmp_path: Path, *subjects: str, branch: str = "feature/notice") -> Path:
    repo = tmp_path / "repo"
    _init_repo(repo, branch="develop")
    _write_state(repo, "base_branch: develop\n")
    _write_plan(repo, CLAIMED_PLAN)
    _commit(repo, "chore: plan")
    _git(repo, "checkout", "-b", branch, "--quiet")
    for subject in subjects:
        _commit(repo, subject)
    return repo


def _certify(repo: Path, chunk: str) -> None:
    """Append a clean review fact naming ``chunk``, anchored at HEAD."""
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    appended = evidence.append_fact(repo, "review", f"review-{chunk}", {
        "scope": "notice", "mode": "chunk", "chunk": chunk, "chunks": [chunk],
        "head_commit": head, "dispatch_commit": head, "findings": [],
        "counts": {"blocking": 0, "warning": 0, "note": 0},
    })
    assert appended.get("status") == "appended", appended


def _hook():
    import importlib.machinery
    import importlib.util

    loader = importlib.machinery.SourceFileLoader(
        "prawduct_hook_built_not_done_call_site",
        str(Path(__file__).resolve().parent.parent / "plugin" / "bin" / "prawduct-hook"),
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    hook = importlib.util.module_from_spec(spec)
    loader.exec_module(hook)
    return hook


class TestBuiltNotDoneNotice:
    """Committed work no review has certified is REPORTED — never resolved.

    Replaces the unticked-committed-chunk tripwire (#1051): with done-ness read
    from review facts, the discrepancy worth naming is no longer "committed but
    unticked" but "built but not reviewed", and the remedy is a review. It
    reports, never writes and never decides; no gate reads it.
    """

    def test_it_names_a_built_unreviewed_chunk_of_the_bound_plan(self, tmp_path: Path):
        repo = _claimed_repo(tmp_path, "feat(notice): land it (Chunk 01)")
        assert work_unit.resolve(repo).state == "bound"
        notice = plan_status.built_not_done_notice(repo)
        assert notice is not None
        first, *rest = notice.splitlines()
        assert first == (
            f"WARNING: {plan_status.BUILT_NOT_DONE_TOKEN}: 1 chunk of build-plan.md has "
            "work committed on the plan's branch that no review has certified — "
            "built, not done — run the Critic."
        )
        assert rest == ["  - Chunk 01: The first half"]

    def test_two_chunks_are_counted_and_listed_in_plan_order(self, tmp_path: Path):
        repo = _claimed_repo(
            tmp_path,
            "feat(notice): the second (Chunk 02)",
            "feat(notice): the first (Chunk 01)",
        )
        notice = plan_status.built_not_done_notice(repo)
        assert notice is not None
        assert "2 chunks of build-plan.md have work committed" in notice.splitlines()[0]
        assert notice.splitlines()[1:] == [
            "  - Chunk 01: The first half", "  - Chunk 02: The second half",
        ]

    def test_a_chunk_certified_by_a_review_fact_is_not_named(self, tmp_path: Path):
        repo = _claimed_repo(tmp_path, "feat(notice): land it (Chunk 01)")
        assert plan_status.built_not_done_notice(repo) is not None  # the control
        _certify(repo, "01")
        assert plan_status.built_not_done_notice(repo) is None

    def test_an_unbound_checkout_prints_nothing(self, tmp_path: Path):
        """The plan claims `feature/notice`; this checkout is another branch
        with a commit naming Chunk 01, so no plan is borrowed and nothing is
        reported about one."""
        repo = _claimed_repo(
            tmp_path, "feat(notice): land it (Chunk 01)", branch="feature/elsewhere"
        )
        assert work_unit.resolve(repo).state == "unbound"
        assert plan_status.built_not_done_notice(repo) is None

    def test_it_is_silent_when_nothing_is_built(self, tmp_path: Path):
        repo = _claimed_repo(tmp_path)
        assert plan_status.built_not_done_notice(repo) is None

    def test_it_never_writes(self, tmp_path: Path):
        """Reporting-only, asserted rather than asserted-in-prose: the plan and
        the fact store are byte-identical after the notice fires."""
        repo = _claimed_repo(tmp_path, "feat(notice): land it (Chunk 01)")
        plan = repo / ".prawduct" / "artifacts" / "build-plan.md"
        store = evidence.store_path(repo)
        before = (plan.read_bytes(), store.read_bytes() if store.is_file() else None)
        assert plan_status.built_not_done_notice(repo) is not None
        assert (plan.read_bytes(), store.read_bytes() if store.is_file() else None) == before

    def test_it_does_not_change_what_any_consumer_reads(self, tmp_path: Path):
        """The report must not become a reading by the back door: with it
        firing on 04, the current chunk is STILL 04, and the gate stays armed —
        a chunk's last commit lands before its review (`plan_status.gate_arms`)."""
        repo = _live_repo(tmp_path)
        assert plan_status.built_not_done_notice(repo) is not None
        plan = repo / ".prawduct" / "artifacts" / "build-plan.md"
        assert plan_status.current_chunks(plan, None, repo_dir=repo) == ["04"]
        assert plan_status.gate_arms(work_unit.resolve(repo)) is True

    def test_the_session_boundary_emits_it_on_stdout(self, tmp_path: Path, capsys):
        """**The call site, not just the function**: `/clear` is the surface an
        ordinary session passes through, and a refactor that drops the call
        leaves every unit test above green."""
        repo = _claimed_repo(tmp_path, "feat(notice): land it (Chunk 01)")
        hook = _hook()
        capsys.readouterr()
        assert hook.cmd_clear(repo) == 0
        out = capsys.readouterr().out
        assert f"WARNING: {plan_status.BUILT_NOT_DONE_TOKEN}: 1 chunk" in out
        assert "  - Chunk 01: The first half" in out

    def test_the_session_boundary_is_silent_for_a_certified_chunk(self, tmp_path: Path, capsys):
        repo = _claimed_repo(tmp_path, "feat(notice): land it (Chunk 01)")
        _certify(repo, "01")
        hook = _hook()
        capsys.readouterr()
        assert hook.cmd_clear(repo) == 0
        assert plan_status.BUILT_NOT_DONE_TOKEN not in capsys.readouterr().out

    def test_handoff_preview_emits_it_on_stderr(self, tmp_path: Path, capsys):
        repo = _claimed_repo(tmp_path, "feat(notice): land it (Chunk 01)")
        hook = _hook()
        capsys.readouterr()
        assert hook.cmd_handoff(repo, ["preview"]) == 0
        captured = capsys.readouterr()
        assert f"WARNING: {plan_status.BUILT_NOT_DONE_TOKEN}: 1 chunk" in captured.err
        assert plan_status.BUILT_NOT_DONE_TOKEN not in captured.out

    def test_handoff_preview_is_silent_unbound_and_once_certified(self, tmp_path: Path, capsys):
        hook = _hook()
        unbound = _claimed_repo(
            tmp_path / "u", "feat(notice): land it (Chunk 01)", branch="feature/elsewhere"
        )
        capsys.readouterr()
        hook.cmd_handoff(unbound, ["preview"])
        assert plan_status.BUILT_NOT_DONE_TOKEN not in capsys.readouterr().err
        certified = _claimed_repo(tmp_path / "c", "feat(notice): land it (Chunk 01)")
        _certify(certified, "01")
        hook.cmd_handoff(certified, ["preview"])
        assert plan_status.BUILT_NOT_DONE_TOKEN not in capsys.readouterr().err


class TestChunkCommitSubjectForms:
    """Which commit subjects mean *this commit carried chunk N* — now
    `plan_status.built_chunks`' rule, the one home it moved to (#1051).

    The original pattern matched a chunk id ANYWHERE in a subject, so a commit
    saying "…carried to Chunk 04" reported 04 minutes after the first notice
    shipped. A control whose first firing is wrong teaches its readers to
    ignore it.

    All the forms are pinned together because the narrowing is only correct as
    a set: the four that must match, in any case, are the conventions actually
    in use in this repo's history and its products' (#1081), and the ones that
    must not are false positives.
    Dropping any match arm silences a real convention; widening past them
    re-admits prose.
    """

    PLAN = (
        "---\nartifact: build-plan\nscope: forms\n---\n\n"
        "### Chunk 04: the subject under test\n"
    )

    def _built_for(self, tmp_path: Path, *subjects: str, plan: str = PLAN) -> set[str]:
        repo = tmp_path / "repo"
        _init_repo(repo, branch="develop")
        _write_state(repo, "base_branch: develop\n")
        plan_path = _write_plan(repo, plan)
        _commit(repo, "chore: plan")
        _git(repo, "checkout", "-b", "feature/x", "--quiet")
        for subject in subjects:
            _commit(repo, subject)
        return plan_status.built_chunks(plan_path, repo)

    @pytest.mark.parametrize(
        "subject",
        [
            "feat(forms): land it (Chunk 04)",
            "docs(forms): Chunk 04 — the prose half",
            "docs(forms): close Chunk 04 — the verify pass and the reflection",
            "feat(forms): chunk 04 — the lowercase this repo's own log uses",
            "forms chunk 04: the page",
        ],
        ids=["parenthesised", "after-the-colon", "close-idiom", "lowercase", "id-then-colon"],
    )
    def test_a_commit_that_carries_the_chunk_is_built(self, tmp_path: Path, subject):
        assert self._built_for(tmp_path, subject) == {"04"}, (
            f"{subject!r} names chunk 04's work and was not counted"
        )

    @pytest.mark.parametrize(
        "subject",
        [
            "plan(forms): the tripwire's false positive, carried to Chunk 04",
            "docs(forms): the two rules Chunk 04 produced, with narrative in detail",
            "docs(forms): the Context line still said Chunk 04 was next",
        ],
        ids=["carried-to", "produced-by", "said-was-next"],
    )
    def test_a_commit_that_merely_mentions_the_chunk_is_not(self, tmp_path: Path, subject):
        """Every one of these is a real subject from this repo's log, and every
        one made the original pattern report a chunk that had not been done."""
        assert self._built_for(tmp_path, subject) == set(), (
            f"{subject!r} only MENTIONS chunk 04 — counting it is the false "
            "positive that teaches readers to ignore this control"
        )

    def test_alpha_ids_are_never_built_by_subject(self, tmp_path: Path):
        """A KNOWN GAP, pinned rather than left to be discovered: the subject
        forms capture digits and dots only, so `Chunk A` is built only through
        its Deliverables paths, never by a subject naming it."""
        plan = (
            "---\nartifact: build-plan\nscope: forms\n---\n\n"
            "### Chunk A: ay\n\n### Chunk 1.2: dotted\n"
        )
        built = self._built_for(
            tmp_path, "feat(forms): land it (Chunk A)", "feat(forms): land it (Chunk 1.2)",
            plan=plan,
        )
        assert built == {"1.2"}

    def test_a_foreign_plans_chunk_ids_are_not_counted(self, tmp_path: Path):
        """Chunk ids are PER-PLAN (SCN-5B8Q R-2/R-7): once some commit carries
        this plan's scope, a sibling plan's `(Chunk 04)` counts for nothing."""
        built = self._built_for(
            tmp_path,
            "fix(forms): unrelated tidy",
            "feat(other-plan): unrelated work (Chunk 04)",
        )
        assert built == set()

    def test_an_unmatched_plan_scope_keeps_the_unscoped_reading(self, tmp_path: Path):
        """Scope tags are a convention, not a guarantee: when NO commit carries
        the plan's scope, every subject counts rather than none."""
        built = self._built_for(tmp_path, "fix(forms-renamed): the critic summary (Chunk 04)")
        assert built == {"04"}

    def test_the_pattern_matches_nothing_beyond_a_chunk_id_in_any_case(self):
        """Over this repo's own history the pattern must match nothing a
        case-blind ``chunk <id>`` search misses — the risk of a rewrite is "it
        starts matching something else", which no positive test can see.

        Renegotiated in the open (#1081): this pinned the CASE-SENSITIVE
        ``Chunk <id>`` as the ceiling, and that ceiling was the defect. This
        repo's own log carries ``feat(opus-55-w1): chunk 03 — …`` and products
        write ``<scope> chunk 01: …``; both name the chunk and neither was read,
        so a boundary review proposed nothing and certified nothing. Case is
        the one widening; the anchored forms still keep prose out
        (:meth:`test_a_commit_that_merely_mentions_the_chunk_is_not`)."""
        old = re.compile(r"Chunk\s+(\d+)", re.IGNORECASE)
        subjects = subprocess.run(
            ["git", "log", "--format=%s", "-800"],
            cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.splitlines()
        if not subjects:
            pytest.skip("no git history available to compare against")
        gained = [
            s for s in subjects
            if plan_status._CHUNK_COMMIT_RE.search(s) and not old.search(s)
        ]
        assert gained == [], f"the pattern widened rather than narrowed: {gained}"


class TestOneCurrentChunkImplementation:
    """The sweep's structural guarantee: the derivation has ONE home, and no
    consumer re-derives "first unchecked" for itself. CRT-7B4M fixed this at one
    consumer and the defect recurred at two more — the recurrence is the reason
    this pin exists. Since #1051 the home is ``plan_status``."""

    # `_git_aware_progress` was a member until the git-derived progress reading
    # was retired. Of the three names moved out of `critic_mode`, one still lives
    # in `buildplan_refs` (`_commits_ahead_of_base`, which `critic_mode` calls),
    # the subject-form rule moved to `plan_status` (`_CHUNK_COMMIT_RE`, read by
    # `built_chunks`), and `_committed_chunk_ids` is deleted with the notice it
    # fed (#1051). Each still must not regrow in `critic_mode`.
    MOVED_OUT_OF_CRITIC_MODE = (
        "_commits_ahead_of_base",
        "_committed_chunk_ids",
        "_CHUNK_COMMIT_RE",
    )

    #: The population's three exclusions, named so a fourth cannot be added
    #: quietly: the one walker of chunk progress, the module owning the Status
    #: section's bounds and walk, and — inside the hook, bounded to its own
    #: span — the MG2 writer that turns boxes into facts.
    EXCLUDED_MODULES = ("plan_status.py", "plan_index.py")
    EXCLUDED_HOOK_FUNCTION = "_cmd_plan_import_status"

    # A regex escaping a checkbox: `\[`, up to ten box-ish characters, `\]`.
    _BOX = re.compile(r"\\\[((?:[ xX()|?:\[\]]|\\s){1,10}?)\\\]")

    @staticmethod
    def _reads_box_state(interior: str) -> bool:
        """Whether an escaped box tells ticked from unticked.

        A class accepting both states (`[ xX]`, non-capturing) SKIPS a box —
        `buildplan_refs._CHUNK_CHECKBOX` tolerates `### [ ] Chunk 7:` headings
        that way — and is not a reading. A capture, or a box matching one state
        (`x`, ` `, `\\s`), is.
        """
        body = interior
        if body.startswith("(?:") and body.endswith(")"):
            body = body[3:-1]
        if body.startswith("[") and body.endswith("]"):
            cls = body[1:-1]
            if "x" in cls.lower() and (" " in cls or "\\s" in cls) and "(" not in cls:
                return False
        return True

    def _offences(self, path: Path, text: str, skip: "tuple[int, int] | None" = None):
        """``(lineno, what)`` for each Status walk or box-state regex in ``text``."""
        import ast

        tree = ast.parse(text, filename=str(path))
        found = []
        for node in ast.walk(tree):
            line = getattr(node, "lineno", None)
            if line is None or (skip and skip[0] <= line <= skip[1]):
                continue
            names = []
            if isinstance(node, ast.Name):
                names = [node.id]
            elif isinstance(node, ast.Attribute):
                names = [node.attr]
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.asname or a.name for a in node.names] + [a.name for a in node.names]
            for name in names:
                if name.startswith(("iter_status_section_", "_iter_status_section_")):
                    found.append((line, f"walks Status via {name}"))
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for m in self._BOX.finditer(node.value):
                    if self._reads_box_state(m.group(1)):
                        found.append((line, f"box regex {m.group(0)!r}"))
        return found

    def _hook_writer_span(self, text: str) -> "tuple[int, int]":
        import ast

        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.FunctionDef) and node.name == self.EXCLUDED_HOOK_FUNCTION:
                return node.lineno, node.end_lineno
        raise AssertionError(
            f"the hook defines no {self.EXCLUDED_HOOK_FUNCTION} — the exclusion names "
            "a function that is gone; re-point it at the import-status writer"
        )

    def test_the_retired_derivation_is_really_gone(self):
        """The git-derived progress reading must not come back anywhere.

        A module quietly reintroducing it would restore the precedence this
        work removed without any test above going red.
        """
        for module in (buildplan_refs, critic_mode, gates, briefing, plan_status):
            assert "_git_aware_progress" not in vars(module), (
                f"{module.__name__} defines _git_aware_progress — chunk progress "
                "has ONE reading (plan_status), and a second derived reading is "
                "the defect shape this work removed."
            )

    def test_critic_mode_no_longer_defines_the_derivation(self):
        for name in self.MOVED_OUT_OF_CRITIC_MODE:
            assert name not in vars(critic_mode), (
                f"{name} is back in lib/critic_mode.py — the current-chunk path "
                "belongs to lib/plan_status.py so every consumer gets the same "
                "answer (BLD-7K3Q, #1051)."
            )

    def test_each_moved_name_has_one_home(self):
        """Renegotiated by #1051 Chunk 06 (was `test_buildplan_refs_owns_it`)."""
        assert "_commits_ahead_of_base" in vars(buildplan_refs)
        assert "_CHUNK_COMMIT_RE" in vars(plan_status)
        assert "_CHUNK_COMMIT_RE" not in vars(buildplan_refs), (
            "the subject-form rule regrew in buildplan_refs; plan_status.built_chunks owns it"
        )
        for module in (buildplan_refs, plan_status, gates, briefing):
            assert "_committed_chunk_ids" not in vars(module)

    def test_the_box_classifier_tells_a_reading_from_a_skip(self):
        """The control: the scan below is only as good as this classifier, so
        it is shown to flag each state-reading form and to pass the one
        tolerance the tree carries — on the real constant, not a copy."""
        for form in (r"^- \[([ xX])\]", r"- \[x\]", r"- \[ \]", r"\[\s\]", r"\[(x| )\]"):
            hits = [m.group(1) for m in self._BOX.finditer(form)]
            assert hits and self._reads_box_state(hits[0]), form
        tolerance = [m.group(1) for m in self._BOX.finditer(buildplan_refs._CHUNK_CHECKBOX)]
        assert tolerance and not self._reads_box_state(tolerance[0]), tolerance

    def test_no_consumer_walks_the_status_section_itself(self):
        """Only the owners may walk ``## Status`` or read a box (#1051).

        The population is every ``plugin/lib/**/*.py`` and ``plugin/bin/prawduct-hook``.
        Excluded, exactly: ``plan_status.py`` (the one walker of chunk progress),
        ``plan_index.py`` (the section's bounds and its one walk) and, in the
        hook, the span of ``_cmd_plan_import_status`` (the writer turning boxes
        into facts) — nothing else in the hook is exempt. Everywhere else: no
        reference to an ``iter_status_section_*`` walker (a call, an alias or an
        import) and no regex that reads a box's state.

        A bare ``- [ ]`` grep is NOT the guard — backlog acceptance-checkbox
        lint and docstring prose both match it — so the box half is on regexes
        (``_reads_box_state``). Known gap, stated so it is not mistaken for
        coverage: a literal ``startswith("- [x]")`` test, or a box regex built
        by concatenation, passes this scan; the walker half still catches any
        reader that reaches the section through ``plan_index``.
        """
        lib = REPO_ROOT / "lib"
        hook = REPO_ROOT / "bin" / "prawduct-hook"
        excluded = sorted(lib / name for name in self.EXCLUDED_MODULES)
        for path in excluded:
            assert path.is_file(), f"{path} is an exclusion and is gone — re-derive the set"
        scanned = [p for p in sorted(lib.rglob("*.py")) if p not in excluded]
        assert len(scanned) > 30 and lib / "gates.py" in scanned and lib / "briefing.py" in scanned, (
            f"the scan reached {len(scanned)} modules — too few to be the population"
        )

        offenders = []
        for path in scanned:
            for line, what in self._offences(path, path.read_text(encoding="utf-8")):
                offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{line}: {what}")
        hook_text = hook.read_text(encoding="utf-8")
        span = self._hook_writer_span(hook_text)
        assert span[1] - span[0] > 20, span  # the writer, not a stub
        for line, what in self._offences(hook, hook_text, skip=span):
            offenders.append(f"bin/prawduct-hook:{line}: {what}")

        assert not offenders, (
            f"{offenders} walk the build-plan Status section or read a box "
            "directly; ask plan_status (chunk_states / current_chunks / "
            "is_finished) so every consumer gets the one answer."
        )


# ---------------------------------------------------------------------------
# Defect 5a — a frontmatter-style plan with no H1
# ---------------------------------------------------------------------------


class TestDescriptionFallback:
    """Ported from `buildplan_refs._parse_build_plan_status` (deleted, #1051) to
    `briefing._plan_work`, the reader the handoff and the briefing now share."""

    def test_frontmatter_scope_names_a_plan_with_no_h1(self, tmp_path: Path):
        _init_repo(tmp_path)
        plan = _write_plan(
            tmp_path,
            "---\nartifact: build-plan\nscope: session-handoff-continuity\n---\n\n"
            "## Status\n\n- [ ] Chunk 01: A\n",
        )
        status = briefing._plan_work(tmp_path, plan)
        assert status["description"] == "session-handoff-continuity"

    def test_filename_is_the_last_resort(self, tmp_path: Path):
        # A work tree: the plan is read through the work-unit binding, and
        # outside one no branch binds and no plan is read (#1050).
        _init_repo(tmp_path)
        plan_dir = tmp_path / ".prawduct" / "artifacts"
        plan_dir.mkdir(parents=True)
        plan = plan_dir / "build-plan-widgets.md"
        plan.write_text("## Status\n\n- [ ] Chunk 01: A\n")
        status = briefing._plan_work(tmp_path, plan)
        assert status["description"] == "widgets"

    def test_h1_still_wins_when_present(self, tmp_path: Path):
        # A work tree: the plan is read through the work-unit binding, and
        # outside one no branch binds and no plan is read (#1050).
        _init_repo(tmp_path)
        plan = _write_plan(
            tmp_path,
            "---\nscope: ignored-when-h1-present\n---\n\n"
            "# Build Plan — Real Title (2026-07-26)\n\n## Status\n\n- [ ] Chunk 01: A\n",
        )
        assert briefing._plan_work(tmp_path, plan)["description"] == "Real Title"

    def test_handoff_work_section_survives_a_missing_h1(self, tmp_path: Path):
        """The section vanished entirely on a live four-chunk plan, because
        `description` is the only key gating it."""
        _init_repo(tmp_path)
        _write_plan(
            tmp_path,
            "---\nscope: session-handoff-continuity\n---\n\n"
            "## Status\n\n- [ ] Chunk 02: Parser correctness\n",
        )
        briefing.generate_session_handoff(tmp_path)
        handoff = (tmp_path / ".prawduct" / ".session-handoff.md").read_text()
        assert "## Work In Progress" in handoff
        assert "**Task**: session-handoff-continuity" in handoff
        assert "**Current chunk**: Chunk 02: Parser correctness" in handoff


# ---------------------------------------------------------------------------
# Defect 5b — the Context block
# ---------------------------------------------------------------------------


MULTI_PARAGRAPH_PLAN = """# Build Plan — Context (2026-07-26)

## Status

- [ ] Chunk 01: A

Context: **Chunk 01 complete** — the forward channel shipped and the
generator stopped destroying what it found.

Plan written on a feature branch off develop. Parents: SCN-4H9T.

The last paragraph, which used to be lost.

## Problem, Success, Scope

Prose that is NOT context.
"""


class TestContextBlock:
    """`plan_index.status_context` — the block's one reader since #1051 moved it
    out of `briefing` (and `_parse_build_plan_status` before it)."""

    def test_multi_paragraph_context_survives_whole(self):
        context = plan_index.status_context(MULTI_PARAGRAPH_PLAN)
        assert context.startswith("**Chunk 01 complete**")
        assert "generator stopped destroying" in context
        assert "Parents: SCN-4H9T." in context
        assert "The last paragraph, which used to be lost." in context

    def test_context_stops_at_the_next_heading(self):
        context = plan_index.status_context(MULTI_PARAGRAPH_PLAN)
        assert "Prose that is NOT context" not in context

    def test_context_stops_at_a_later_chunk_item(self, tmp_path: Path):
        """Context is conventionally last, but a plan that interleaves must not
        swallow its own checklist into the handoff."""
        _init_repo(tmp_path)
        plan = _write_plan(
            tmp_path,
            "# Build Plan — Interleaved (2026-07-26)\n\n## Status\n\n"
            "- [ ] Chunk 01: A\n\nContext: mid-plan note.\n\n- [ ] Chunk 02: B\n",
        )
        status = briefing._plan_work(tmp_path, plan)
        assert status["context"] == "mid-plan note."
        assert status["current_chunk"] == "Chunk 01: A"

    def test_a_second_context_line_is_kept_as_block_text(self):
        """Block semantics dissolve the first-wins/last-wins question: the first
        `Context:` opens the block and a later one is text inside it, so neither
        wins and nothing is dropped."""
        context = plan_index.status_context(
            "# Build Plan — Two (2026-07-26)\n\n## Status\n\n- [ ] Chunk 01: A\n\n"
            "Context: first note.\n\nContext: second note.\n"
        )
        assert "first note." in context
        assert "second note." in context

    def test_handoff_carries_the_whole_block(self, tmp_path: Path):
        _init_repo(tmp_path)
        _write_plan(tmp_path, MULTI_PARAGRAPH_PLAN)
        briefing.generate_session_handoff(tmp_path)
        handoff = (tmp_path / ".prawduct" / ".session-handoff.md").read_text()
        assert "The last paragraph, which used to be lost." in handoff

    def test_briefing_flattens_and_caps_the_block(self, tmp_path: Path):
        """The briefing has a token budget; the handoff is where it lands whole.
        A multi-line block must not blow up the one-line `Context:` field."""
        _init_repo(tmp_path)
        _write_plan(tmp_path, MULTI_PARAGRAPH_PLAN)
        text = briefing.assemble_session_briefing(tmp_path, [])
        context_lines = [ln for ln in text.splitlines() if ln.startswith("Context: ")]
        assert len(context_lines) == 1
        assert len(context_lines[0]) <= len("Context: ") + 200


# ---------------------------------------------------------------------------
# BRF-6K2D — the delete-the-plan nudge is merge-aware
# ---------------------------------------------------------------------------


COMPLETE_PLAN = "# Build Plan — Done (2026-07-26)\n\n## Status\n\n- [x] Chunk 01: A\n"


class TestEndOfLifeNudgeIsMergeAware:
    """The nudge's *timing* logic is unchanged; what it recommends is not.

    It used to say "delete the plan". A completed plan is now archived, never
    deleted, so these assert the new instruction — and, positively, that the old
    one is gone from the surface that told an operator to do it every session.
    """

    def test_unmerged_feature_branch_says_keep_it_live(self, tmp_path: Path):
        """The plan survives a branch switch, so the nudge once told the user to
        retire a plan whose work had not shipped — which would orphan it. Under
        archival the harm is smaller (an archived plan is still findable) but the
        recommendation is the same: not yet."""
        repo = tmp_path / "repo"
        _init_repo(repo, branch="develop")
        _write_state(repo, "base_branch: develop\n")
        _commit(repo, "chore: init")
        _git(repo, "checkout", "-b", "feature/x", "--quiet")
        _write_plan(repo, COMPLETE_PLAN)
        _commit(repo, "feat: land it (Chunk 01)")
        findings = "\n".join(briefing.staleness_scan(repo))
        assert "keep the plan live until it merges" in findings
        assert "archive the plan" not in findings

    def test_merged_branch_still_gets_the_end_of_life_nudge(self, tmp_path: Path):
        """Merge-awareness may only ADD a keep-recommendation on positive
        evidence — a plan that really is finished and merged must still reach its
        end of life, or the nudge silently stops working."""
        repo = tmp_path / "repo"
        _init_repo(repo, branch="develop")
        _write_state(repo, "base_branch: develop\n")
        _write_plan(repo, COMPLETE_PLAN)
        _commit(repo, "feat: land it (Chunk 01)")
        findings = "\n".join(briefing.staleness_scan(repo))
        assert "archive the plan" in findings
        assert "keep the plan" not in findings

    def test_it_names_the_command_rather_than_leaving_the_operator_to_guess(
        self, tmp_path: Path
    ):
        """The old nudge described an action any operator could perform with
        `rm`. This one names an operation that has to be run, so the nudge that
        does not carry it is a nudge that gets answered with a deletion."""
        repo = tmp_path / "repo"
        _init_repo(repo, branch="develop")
        _write_state(repo, "base_branch: develop\n")
        _write_plan(repo, COMPLETE_PLAN)
        _commit(repo, "feat: land it (Chunk 01)")
        findings = "\n".join(briefing.staleness_scan(repo))
        assert "archive-plan" in findings

    def test_no_nudge_anywhere_still_says_to_delete_a_plan(self, tmp_path: Path):
        """Asserted over BOTH branches of the stale-plan scan, because the
        deletion instruction lived in two of them and fixing one leaves the
        behaviour in force in the other."""
        for state in (
            "base_branch: develop\n",
            "base_branch: develop\n"
            "work_in_progress:\n  feature/elsewhere:\n    description: unshipped\n",
        ):
            repo = tmp_path / f"repo{abs(hash(state)) % 1000}"
            _init_repo(repo, branch="develop")
            _write_state(repo, state)
            _write_plan(repo, COMPLETE_PLAN)
            _commit(repo, "feat: land it (Chunk 01)")
            findings = "\n".join(briefing.staleness_scan(repo)).lower()
            assert "delete the plan" not in findings
            assert "deleting now" not in findings

    def test_foreign_branch_wip_says_keep_it_live(self, tmp_path: Path):
        """The reported repro: a plan surviving a switch onto the base branch,
        with project-state.yaml still recording work on the feature branch."""
        repo = tmp_path / "repo"
        _init_repo(repo, branch="develop")
        _write_state(
            repo,
            "base_branch: develop\n"
            "work_in_progress:\n  feature/elsewhere:\n    description: unshipped work\n",
        )
        _write_plan(repo, COMPLETE_PLAN)
        _commit(repo, "feat: land it (Chunk 01)")
        findings = "\n".join(briefing.staleness_scan(repo))
        assert "keep the plan live until it merges" in findings

    def test_non_git_directory_fails_toward_the_ordinary_nudge(self, tmp_path: Path):
        _write_plan(tmp_path, COMPLETE_PLAN)
        assert briefing._plan_work_possibly_unmerged(
            tmp_path, tmp_path / ".prawduct"
        ) == (False, "")


# ---------------------------------------------------------------------------
# A non-UTF-8 plan degrades, at each reader that has to survive one
# ---------------------------------------------------------------------------


class TestNonUtf8PlanDegrades:
    """The behavioral half of `tests/preferences/test_build_plan_decoding.py`.

    That pin is grep-level — it asserts each read names UTF-8 and each guard
    spells `UnicodeDecodeError`. It cannot assert the designed degradation
    actually *runs*, so a refactor that keeps the token and breaks the return
    would pass it. Shape and behavior are different claims; the gap between
    them is where this class lived for three review rounds.
    """

    UNDECODABLE = (
        b"# Build Plan \xff\xfe Bad Bytes (2026-07-27)\n\n"
        b"## Status\n\n- [ ] Chunk 01: A\n\n"
        b"### Chunk 01: A\n- **Type:** code\n"
    )

    def _write_undecodable_plan(self, project_dir: Path) -> Path:
        plan = project_dir / ".prawduct" / "artifacts" / "build-plan.md"
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_bytes(self.UNDECODABLE)
        return plan

    def test_chunk_refs_returns_its_error_instead_of_raising(self, tmp_path: Path):
        """The reachable symptom: `verify-chunk-refs <chunk_id>` bypasses the
        degrading resolver and calls this directly, so a raise here becomes a
        traceback where the CLI documents a `cannot-verify:` exit.

        The id is POSITIONAL. `--chunk <id>` is `verify-records`' spelling, and
        passing it here recorded the literal string `--chunk` as the chunk id —
        which still reached this error, because an undecodable plan fails at the
        read before any id is used. So the assertion below passed while the
        invocation it documented did not exist.
        """
        # The plan is passed: `verify-chunk-refs` resolves the binding first
        # and hands the bound plan in (an undecodable plan at the conventional
        # path makes the binding broken, which the CLI test below covers). The
        # subject here is the reader's own degradation on the bytes.
        plan = self._write_undecodable_plan(tmp_path)
        refs = buildplan_refs._parse_build_plan_chunk_refs(tmp_path / ".prawduct", "01", plan)
        assert "unreadable build-plan" in refs["error"]

    def test_verify_chunk_refs_cli_reports_rather_than_tracebacks(self, tmp_path: Path):
        """End-to-end, because the boundary's recorded error model says no
        internal stack trace may cross it."""
        _init_repo(tmp_path)
        self._write_undecodable_plan(tmp_path)
        proc = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "bin" / "prawduct-hook"),
                "verify-chunk-refs",
                "01",
            ],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            env={**_git_env(tmp_path), "CLAUDE_PROJECT_DIR": str(tmp_path)},
            timeout=30,
        )
        assert proc.returncode == 1, proc.stdout + proc.stderr
        assert "cannot-verify" in proc.stderr, proc.stdout + proc.stderr
        assert "Traceback" not in proc.stderr, proc.stderr

    def test_duplicate_scope_diagnosis_survives_an_unreadable_plan(
        self, tmp_path: Path
    ):
        """`duplicate_scope_errors` is the twin of `build_scope_to_plan_map` and
        was the last reader still on the narrow guard — called bare with no
        global handler, so one bad file tracebacked out of its caller. Its
        duplicate-scope branch had no coverage at all, which is how a rename into
        it could have gone unnoticed.

        The check outlived the derived-view regenerator that used to host it: it
        guards frontmatter `scope:`, a field that survives, so it was rehomed to
        `plan_index` and is now reached through the release gate rather than
        dying with its old caller."""
        artifacts = tmp_path / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True)
        self._write_undecodable_plan(tmp_path)
        for name in ("build-plan-a.md", "build-plan-b.md"):
            (artifacts / name).write_text(
                "---\nscope: dup\n---\n\n## Status\n\n- [ ] Chunk 01: A\n",
                encoding="utf-8",
            )
        errors = plan_index.duplicate_scope_errors(artifacts)
        assert any(
            "duplicate scope=" in message and "build-plan-b.md" in message
            for _scope, message in errors
        ), errors
