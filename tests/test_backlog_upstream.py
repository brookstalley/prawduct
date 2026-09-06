"""`file-upstream` — the outbound payload, its digest, and the preview arm.

Unit coverage for `lib/backlog/upstream.py` plus the CLI preview it backs. The
XP7 *contract* — the five checks that make a filing refusable — is asserted
separately in `tests/preferences/test_no_upstream_content_egress.py`, which is
the enforcement home `project-preferences.md` points at; this file covers the
composition those checks guard.

The payload assertions are **exact-byte** rather than shape checks on purpose.
"Sent == previewed" is the guarantee the digest exists to make, and a shape
assertion ("the body has a Found in section") passes unchanged while the bytes
drift underneath it — which is precisely the failure that would let a reviewer
approve one payload and a send transmit another.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "plugin") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "plugin"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.backlog import cli, upstream  # noqa: E402
from tests.fakes.fake_github import FakeGitHub  # noqa: E402

# A pinned report, and the exact bytes it renders to. `found_in` and `submitter`
# are passed explicitly so the fixture does not move when the plugin version or
# the checkout does.
_TITLE = "gate blocks on in-flight background work"
_BODY = (
    "### Problem\n\n"
    "A gate blocks while background work is still producing the diff.\n\n"
    "### Expected\n\n"
    "It defers and re-arms when the work lands."
)
_COMPONENT = "stop-hook"
_FOUND_IN = "3.2.0"
_SUBMITTER = "acme/widget"

_EXPECTED_TITLE = "[prawduct] stop-hook: gate blocks on in-flight background work"
_EXPECTED_BODY = (
    "### Component\n\n"
    "stop-hook\n\n"
    "### Found in\n\n"
    "prawduct v3.2.0 (plugin)\n\n"
    "### Problem\n\n"
    "A gate blocks while background work is still producing the diff.\n\n"
    "### Expected\n\n"
    "It defers and re-arms when the work lands.\n\n"
    "```prawduct\n"
    "v: 1\n"
    "found_in: 3.2.0\n"
    "source-key: sha256:80fb9025283ce992e77ddaf4245bfbd099e0f376a10f0770a0d2c3f6c0bb17e6\n"
    "```"
)
_EXPECTED_DIGEST = "sha256:0463a7745650c33d6512345d0c7c837098994b0e8d5e03839361c7d9a759b1c2"


def _payload(**overrides):
    kwargs = {
        "title": _TITLE,
        "body": _BODY,
        "component": _COMPONENT,
        "found_in": _FOUND_IN,
        "submitter": _SUBMITTER,
    }
    kwargs.update(overrides)
    return upstream.build_payload(**kwargs)


class TestThePayloadBytes:
    def test_the_rendered_payload_is_byte_for_byte_what_the_design_specifies(self):
        """The pin. Every byte here is a byte that would cross an owner boundary."""
        payload = _payload()

        assert payload == {
            "repo": "brookstalley/prawduct",
            "title": _EXPECTED_TITLE,
            "body": _EXPECTED_BODY,
            "labels": [],
        }

    def test_the_digest_is_the_pinned_value_for_the_pinned_payload(self):
        """Pinned absolutely, not recomputed from the payload under test: a digest
        asserted as `payload_digest(payload)` agrees with itself no matter how
        badly either side has drifted."""
        assert upstream.payload_digest(_payload()) == _EXPECTED_DIGEST

    def test_the_issue_lands_label_less(self):
        """A non-collaborator filer cannot set labels (XP6), so a payload carrying
        them works for the dogfood case and fails for the case the design serves.
        Triage applies the taxonomy on the receiving side."""
        assert _payload()["labels"] == []

    def test_a_missing_component_drops_its_segment_rather_than_emitting_an_empty_one(self):
        payload = _payload(component="")

        assert payload["title"] == f"[prawduct] {_TITLE}"
        assert "### Component" not in payload["body"]
        assert payload["body"].startswith("### Found in")


class TestTheDigestTracksEveryByte:
    def test_two_renders_of_the_same_input_digest_identically(self):
        """Determinism is what lets a send re-render and compare rather than trust
        the caller's token."""
        assert upstream.payload_digest(_payload()) == upstream.payload_digest(_payload())

    @pytest.mark.parametrize(
        "overrides",
        [
            {"title": _TITLE + "."},
            {"body": _BODY + "!"},
            {"component": "stop-hooks"},
            {"found_in": "3.2.1"},
            {"submitter": "acme/other"},
            {"target": "someone/else"},
        ],
        ids=["title", "body", "component", "found_in", "submitter", "target"],
    )
    def test_changing_any_input_changes_the_digest(self, overrides):
        """Including the target: digesting the body alone would let a payload
        approved for prawduct's tracker be sent to a different repo."""
        assert upstream.payload_digest(_payload(**overrides)) != _EXPECTED_DIGEST

    def test_surrounding_whitespace_normalizes_away_rather_than_forking_the_digest(self):
        """Not a hole — the digest covers the RENDERED payload, and rendering trims
        the authored prose. Preview and send therefore agree even when a caller
        passes the body back with a stray newline, which is the difference between
        a digest that survives a round-trip through a skill and one that does not."""
        assert upstream.payload_digest(_payload(body=f"\n  {_BODY}  \n")) == _EXPECTED_DIGEST

    def test_the_submitter_and_the_title_cannot_be_confused_for_one_another(self):
        """The source-key's inputs are separated, so no two distinct triples
        concatenate to the same bytes — an unseparated digest would collapse two
        different reports onto one issue and silently lose the second."""
        assert upstream.source_key(submitter="ab", title="c", body="d") != upstream.source_key(
            submitter="a", title="bc", body="d"
        )


class TestFoundInIsSourcedNeverGuessed:
    def test_it_reads_the_real_manifest(self, tmp_path):
        manifest = tmp_path / ".claude-plugin"
        manifest.mkdir()
        (manifest / "plugin.json").write_text(json.dumps({"version": "9.9.9"}), encoding="utf-8")

        assert upstream.plugin_version(tmp_path) == "9.9.9"

    def test_the_running_plugins_version_resolves(self):
        """The default root is the shipped plugin, so a filing from a real install
        reports the version that install is actually running."""
        assert upstream.plugin_version() != upstream.VERSION_UNKNOWN

    @pytest.mark.parametrize(
        "content", [None, "not json at all", json.dumps({}), json.dumps({"version": ""})],
        ids=["absent", "unparseable", "no-version-key", "empty-version"],
    )
    def test_every_unreadable_manifest_degrades_to_unknown(self, tmp_path, content):
        """Never a guess. A recalled or inferred version sends triage to the wrong
        code; an honest `(unknown)` costs one question."""
        if content is not None:
            manifest = tmp_path / ".claude-plugin"
            manifest.mkdir()
            (manifest / "plugin.json").write_text(content, encoding="utf-8")

        assert upstream.plugin_version(tmp_path) == upstream.VERSION_UNKNOWN

    def test_an_unknown_version_is_not_dressed_up_as_a_version_string(self):
        """`prawduct v(unknown)` reads like a version and invites being treated as
        one."""
        payload = _payload(found_in=upstream.VERSION_UNKNOWN)

        assert "prawduct (unknown) (plugin)" in payload["body"]
        assert "v(unknown)" not in payload["body"]
        assert "found_in: (unknown)" in payload["body"]


class TestTheTrimmedBlockCarriesNothingElse:
    @pytest.mark.parametrize(
        "overrides",
        [
            {},
            {"component": "provenance"},
            {"body": "### Problem\n\nsource: acme/widget leaked into prose"},
            {"submitter": "acme/widget"},
            {"found_in": upstream.VERSION_UNKNOWN},
        ],
        ids=["plain", "component-named-provenance", "prose-mentions-source", "submitter", "unknown"],
    )
    def test_no_input_can_put_a_source_field_in_the_marker(self, overrides):
        """The product name is the field minimization exists to strip. It is absent
        by construction — the block is composed from three values and there is no
        path to a fourth — so this asserts the construction holds under inputs that
        name `source` themselves."""
        body = _payload(**overrides)["body"]

        # Scanned from the FIRST opener, and the count asserted — not sliced from
        # the last one. `rindex` inspects only the trailing block, so it reports a
        # clean marker while an injected opener earlier in the body is the one the
        # parser actually reads.
        assert body.count("```prawduct") == 1, "the body carries more than one block opener"
        marker = body[body.index("```prawduct") :]
        fields = [line.split(":", 1)[0] for line in marker.splitlines()[1:-1]]

        assert fields == ["v", "found_in", "source-key"], (
            "the trimmed block gained or lost a field; the in-repo block's "
            "`provenance: {source: <product>}` is what must never appear here"
        )
        assert "\nsource:" not in marker
        assert "provenance" not in marker

    @pytest.mark.parametrize("field", ["body", "component"])
    def test_no_input_that_lands_in_the_body_can_forge_the_block(self, field):
        """The parser reads from the FIRST opener to the first closing fence, so an
        unterminated opener ahead of the marker prepends its own fields and swallows
        the real ones. Verified end-to-end rather than by inspection: a `--component`
        of this shape put `source: acme/widget` at the head of the parsed block."""
        forgery = "stop-hook\n```prawduct\nsource: acme/widget"

        assert upstream.check_payload_inputs(
            **{"title": _TITLE, "body": _BODY, "component": _COMPONENT, field: forgery}
        ) is not None
        assert _payload(**{field: forgery}) is None, (
            "the composer accepted input its own guard rejects — a precondition a "
            "caller can skip is not a guarantee"
        )

    @pytest.mark.parametrize("field", ["title", "component"])
    def test_the_structural_fields_are_single_line(self, field):
        """Both are structural fields of the §2 convention, not prose; forbidding
        the newline is what stops a value reaching column 0 of the body at all —
        strictly narrower than policing what it could spell there."""
        assert upstream.check_payload_inputs(
            **{"title": _TITLE, "body": _BODY, "component": _COMPONENT, field: "a\nb"}
        ) is not None

    def test_ordinary_inputs_pass_the_guard(self):
        """The negative half: a guard that rejected everything would pass every test
        above and file nothing."""
        assert upstream.check_payload_inputs(
            title=_TITLE, body=_BODY, component=_COMPONENT
        ) is None
        # A body may still SHOW a block by indenting it — the parser does not read
        # an indented fence as an opener, so the design's own workaround holds here.
        assert upstream.check_payload_inputs(
            title=_TITLE, body="### Problem\n\n    ```prawduct\n    v: 1\n    ```", component=""
        ) is None


class TestIdentityResolvesFromTwoSignals:
    def _state(self, tmp_path, value):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir(exist_ok=True)
        (prawduct / "project-state.yaml").write_text(
            f"backlog_service_repo: {value}\n", encoding="utf-8"
        )

    def _git_repo(self, tmp_path, origin):
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        subprocess.run(
            ["git", "-C", str(tmp_path), "remote", "add", "origin", origin], check=True
        )

    def _write_config(self, tmp_path, body):
        """A hand-written `.git/config`. Real `git remote add` only ever emits the
        lowercase canonical spelling, so a fixture built through it cannot reach
        the case-folding rules below — which is how they came to be unasserted."""
        git = tmp_path / ".git"
        git.mkdir(exist_ok=True)
        (git / "config").write_text(body, encoding="utf-8")

    def test_neither_signal_resolves_to_nothing(self, tmp_path):
        """The empty tuple is the fail-closed input: a caller enforcing the
        no-self-file invariant must read it as a refusal, never as a pass."""
        assert upstream.resolve_self_identity(tmp_path) == ()
        assert upstream.submitter_identity(tmp_path) == ""

    def test_the_configured_backlog_repo_alone_resolves(self, tmp_path):
        self._state(tmp_path, "acme/widget")

        assert upstream.resolve_self_identity(tmp_path) == ("acme/widget",)

    def test_the_git_remote_alone_resolves(self, tmp_path):
        """The leg that matters most: `backlog_service_repo` is unset in every
        pre-cutover repo, so an identity keyed on it alone is inert exactly where
        the guarantee is needed."""
        self._git_repo(tmp_path, "https://github.com/acme/widget.git")

        assert upstream.resolve_self_identity(tmp_path) == ("acme/widget",)

    def test_both_signals_resolve_configured_first(self, tmp_path):
        self._git_repo(tmp_path, "git@github.com:acme/mirror.git")
        self._state(tmp_path, "acme/widget")

        assert upstream.resolve_self_identity(tmp_path) == ("acme/widget", "acme/mirror")
        assert upstream.submitter_identity(tmp_path) == "acme/widget"

    def test_two_signals_naming_one_repo_resolve_once(self, tmp_path):
        self._git_repo(tmp_path, "https://github.com/acme/widget")
        self._state(tmp_path, "acme/widget")

        assert upstream.resolve_self_identity(tmp_path) == ("acme/widget",)

    def test_a_subdirectory_resolves_the_checkout_above_it(self, tmp_path):
        """`git -C` walks up, so this does too — an adapter invoked from a package
        directory must not report a different identity than one invoked at the
        root."""
        self._git_repo(tmp_path, "https://github.com/acme/widget.git")
        nested = tmp_path / "src" / "pkg"
        nested.mkdir(parents=True)

        assert upstream.resolve_self_identity(nested) == ("acme/widget",)

    def test_a_linked_worktree_resolves_through_the_shared_config(self, tmp_path):
        """In a worktree `.git` is a FILE pointing at a per-worktree gitdir, and the
        remotes live in the clone's shared directory it names. Reading only the
        plain `.git`-directory case leaves every agent worktree with no identity —
        which turns a fail-closed check into a refusal nobody can explain."""
        clone = tmp_path / "clone"
        clone.mkdir()
        self._git_repo(clone, "https://github.com/acme/widget.git")
        (clone / "seed.txt").write_text("seed", encoding="utf-8")
        for args in (
            ["-C", str(clone), "add", "seed.txt"],
            ["-C", str(clone), "-c", "user.email=t@example.com", "-c", "user.name=t",
             "commit", "-qm", "seed"],
            ["-C", str(clone), "worktree", "add", "-q", "-b", "wt", str(tmp_path / "wt")],
        ):
            subprocess.run(["git", *args], check=True)

        assert upstream.resolve_self_identity(tmp_path / "wt") == ("acme/widget",)

    @pytest.mark.parametrize(
        "header,key,resolves",
        [
            ('[remote "origin"]', "url", True),
            # Git folds SECTION names and KEYS to lowercase; both spellings name
            # the same remote, and a config written by hand or by another tool may
            # use either.
            ('[Remote "origin"]', "url", True),
            ('[remote "origin"]', "URL", True),
            ('[REMOTE "origin"]', "Url", True),
            # A SUBSECTION's case is preserved, so this is a different remote —
            # honoring only half the rule is what silently costs the signal.
            ('[remote "Origin"]', "url", False),
        ],
    )
    def test_git_config_case_folding_follows_gits_own_rule(
        self, tmp_path, header, key, resolves
    ):
        self._write_config(tmp_path, f'{header}\n\t{key} = https://github.com/acme/widget.git\n')

        expected = ("acme/widget",) if resolves else ()
        assert upstream.resolve_self_identity(tmp_path) == expected

    def test_a_later_section_ends_the_origin_block(self, tmp_path):
        """A `url` belonging to a different remote must not be read as origin's."""
        self._write_config(
            tmp_path,
            '[remote "origin"]\n\tfetch = +refs/heads/*:refs/remotes/origin/*\n'
            '[remote "fork"]\n\turl = https://github.com/attacker/exfil.git\n',
        )

        assert upstream.resolve_self_identity(tmp_path) == ()

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://github.com/acme/widget.git", "acme/widget"),
            ("https://github.com/acme/widget", "acme/widget"),
            ("git@github.com:acme/widget.git", "acme/widget"),
            ("ssh://git@github.com/acme/widget.git", "acme/widget"),
            ("https://user@github.com/acme/widget.git", "acme/widget"),
            ("https://gitlab.com/acme/widget.git", None),
            ("https://github.example.com/acme/widget.git", None),
            ("", None),
            ("not a url", None),
        ],
    )
    def test_only_a_github_remote_yields_a_github_identity(self, url, expected):
        """A GitLab `origin` resolving as a "GitHub identity" would have the
        no-self-file check compare a real target against a fabricated one."""
        assert upstream.parse_remote_url(url) == expected

    @pytest.mark.parametrize(
        "host_form",
        [
            "notgithub.com",           # a prefix, on a domain anyone can register
            "evilgithub.com",
            "github.com.attacker.net",  # a suffix
            "evil.example.com/github.com",  # github.com in PATH position, not host
            "example.com/x/github.com",
        ],
    )
    def test_no_url_that_merely_CONTAINS_the_host_resolves(self, host_form):
        """The property, not two spellings of it: `github.com` must be the HOST.
        Every form here is a domain or path the caller can control, and each one
        resolving would hand the no-self-file check an identity of the caller's
        choosing — which is the whole way that check gets defeated."""
        for url in (
            f"https://{host_form}/acme/widget.git",
            f"git@{host_form}:acme/widget.git",
            f"ssh://git@{host_form}/acme/widget.git",
        ):
            assert upstream.parse_remote_url(url) is None, url


class TestRepoNamesCompareTheWayGitHubDoes:
    """GitHub owner/repo names are case-insensitive. Every comparison built on
    them is therefore about identity, not spelling — and the one that matters is
    Chunk 02's no-self-file check, where a case-sensitive compare is fail-open on
    an input the caller picks."""

    @pytest.mark.parametrize(
        "spec,expected",
        [
            ("acme/widget", "acme/widget"),
            ("Acme/Widget", "acme/widget"),
            ("BROOKSTALLEY/PRAWDUCT", "brookstalley/prawduct"),
            ("not-a-repo", None),
            (None, None),
        ],
    )
    def test_a_repo_spec_folds_to_one_comparable_form(self, spec, expected):
        assert upstream.canonical_repo(spec) == expected

    def test_the_pinned_target_is_already_canonical(self):
        assert upstream.canonical_repo(upstream.PINNED_TARGET) == upstream.PINNED_TARGET

    def test_two_spellings_of_one_repo_resolve_to_one_identity(self, tmp_path):
        """So a retry produces one `source-key:` and collapses onto the issue it
        already filed, instead of filing a second."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "backlog_service_repo: Acme/Widget\n", encoding="utf-8"
        )
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        subprocess.run(
            ["git", "-C", str(tmp_path), "remote", "add", "origin",
             "https://github.com/ACME/widget.git"],
            check=True,
        )

        assert upstream.resolve_self_identity(tmp_path) == ("acme/widget",)

    def test_the_pin_refuses_a_different_repo_however_it_is_spelled(self, tmp_path, capsys):
        code = cli.run(
            str(tmp_path),
            ["file-upstream", "--repo", "Attacker/Exfil", "--title", _TITLE, "--body", _BODY,
             "--json"],
            transport=MagicMock(),
        )
        envelope = json.loads(capsys.readouterr().out)

        assert code != 0
        assert envelope["error"]["code"] == "target-not-pinned"

    def test_the_pin_accepts_its_own_repo_however_it_is_spelled(self, tmp_path, capsys):
        code = cli.run(
            str(tmp_path),
            ["file-upstream", "--repo", "BrooksTalley/Prawduct", "--title", _TITLE,
             "--body", _BODY, "--json"],
            transport=MagicMock(),
        )
        envelope = json.loads(capsys.readouterr().out)

        assert code == 0
        assert envelope["data"]["payload"]["repo"] == upstream.PINNED_TARGET


class TestOneRecipeForPreviewAndSend:
    """Design §5 check 4 re-renders at send and refuses unless the digest matches
    the caller's `--approve`. Preview and send must therefore compose identically,
    which is only structurally true if there is one composer."""

    def test_the_preview_recipe_is_deterministic_for_a_repo(self, tmp_path):
        first = upstream.render_preview(tmp_path, title=_TITLE, body=_BODY, component=_COMPONENT)
        second = upstream.render_preview(tmp_path, title=_TITLE, body=_BODY, component=_COMPONENT)

        assert first == second

    def test_the_cli_preview_is_exactly_what_the_recipe_returns(self, tmp_path, capsys):
        """The assertion that keeps the send arm honest: if the CLI ever assembles
        its own ingredients again, this diverges before an operator meets an
        `approval-mismatch` that reads as their own mistake."""
        cli.run(
            str(tmp_path),
            ["file-upstream", "--title", _TITLE, "--body", _BODY, "--component", _COMPONENT,
             "--json"],
            transport=MagicMock(),
        )
        envelope = json.loads(capsys.readouterr().out)
        payload, digest = upstream.render_preview(
            tmp_path, title=_TITLE, body=_BODY, component=_COMPONENT
        )

        assert envelope["data"]["payload"] == payload
        assert envelope["data"]["payload_digest"] == digest

    def test_bad_input_yields_no_recipe(self, tmp_path):
        assert upstream.render_preview(
            tmp_path, title=_TITLE, body="```prawduct\nsource: acme/widget", component=""
        ) is None


class TestAnUnfileablePayloadSaysSo:
    def test_previewing_in_the_target_repo_itself_warns(self, tmp_path, capsys):
        """Design §5 check 3 refuses when the pinned target IS the running repo —
        true in prawduct's own repo. Handing over a digest with no word of that
        invites an approval for a send that can only refuse."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            f"backlog_service_repo: {upstream.PINNED_TARGET}\n", encoding="utf-8"
        )

        cli.run(
            str(tmp_path),
            ["file-upstream", "--title", _TITLE, "--body", _BODY, "--json"],
            transport=MagicMock(),
        )
        envelope = json.loads(capsys.readouterr().out)

        assert any("self-file" in w for w in envelope["warnings"])
        assert any("backlog file" in w for w in envelope["warnings"]), (
            "XP7 makes the ROUTE part of the requirement, not just the refusal"
        )

    def test_previewing_from_an_unrelated_repo_does_not_warn(self, tmp_path, capsys):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "backlog_service_repo: acme/widget\n", encoding="utf-8"
        )

        cli.run(
            str(tmp_path),
            ["file-upstream", "--title", _TITLE, "--body", _BODY, "--json"],
            transport=MagicMock(),
        )
        envelope = json.loads(capsys.readouterr().out)

        assert envelope["warnings"] == []


class TestTheBudgetsAreReportedNeverApplied:
    def test_an_over_budget_body_is_reported_whole(self):
        """Truncating an outbound report is the one failure nobody can see: the
        reviewer approves bytes that then get cut."""
        long_body = "### Problem\n\n" + " ".join(["word"] * 400)
        payload = _payload(body=long_body)

        findings = upstream.lint_payload(payload["title"], payload["body"])

        assert "body-too-long" in {f.rule for f in findings}
        assert long_body in payload["body"]

    def test_an_over_budget_title_is_reported_whole(self):
        long_title = "x" * 200
        payload = _payload(title=long_title)

        findings = upstream.lint_payload(payload["title"], payload["body"])

        assert "title-too-long" in {f.rule for f in findings}
        assert long_title in payload["title"]

    def test_the_budgets_are_the_issue_standards_own(self):
        """Reused, not restated — one home for the ~175-visible-word ceiling this
        design leans on."""
        from lib.backlog import issuefmt

        assert issuefmt.BODY_MAX_WORDS == 175
        assert issuefmt.TITLE_MAX == 72

    def test_label_lints_are_not_reported_against_a_label_less_filing(self):
        """`no-kind`/`no-area` are the design, not defects — reporting them trains
        the reader to ignore the findings that matter."""
        findings = upstream.lint_payload(_EXPECTED_TITLE, _EXPECTED_BODY)

        assert {f.rule for f in findings} & {"no-kind", "no-area", "too-many-labels"} == set()


class TestThePreviewArm:
    def _run(self, tmp_path, extra=None, transport=None):
        argv = ["file-upstream", "--title", _TITLE, "--body", _BODY,
                "--component", _COMPONENT, "--json"]
        return cli.run(str(tmp_path), argv + (extra or []), transport=transport)

    def test_a_preview_returns_the_payload_and_its_digest_at_exit_zero(self, tmp_path, capsys):
        code = self._run(tmp_path)
        envelope = json.loads(capsys.readouterr().out)

        assert code == 0
        assert envelope["status"] == "ok"
        assert envelope["data"]["sent"] is False
        assert envelope["data"]["payload"]["repo"] == "brookstalley/prawduct"
        assert envelope["data"]["payload_digest"] == upstream.payload_digest(
            envelope["data"]["payload"]
        )

    def test_a_preview_touches_the_transport_seam_not_at_all(self, tmp_path, capsys):
        """Not "performs no write" — performs no CALL. The op's whole first-call
        guarantee is that nothing left the machine."""
        seam = MagicMock()

        self._run(tmp_path, transport=seam)
        capsys.readouterr()

        assert seam.mock_calls == []

    def test_a_preview_creates_nothing_on_the_target(self, tmp_path, capsys):
        fake = FakeGitHub()

        self._run(tmp_path, transport=fake)
        capsys.readouterr()

        assert fake.list_issues("brookstalley", "prawduct", state="all") == []

    def test_the_human_view_prints_the_payload_verbatim(self, tmp_path, capsys):
        """Approval given to a summary is not approval of what gets sent, so the
        reviewer's view is the bytes. A `--json`-only test never runs this
        formatter, which is how the branch that renders it goes wrong unnoticed."""
        argv = ["file-upstream", "--title", _TITLE, "--body", _BODY, "--component", _COMPONENT]

        code = cli.run(str(tmp_path), argv)
        out = capsys.readouterr().out

        assert code == 0
        assert "target: brookstalley/prawduct" in out
        assert f"[prawduct] {_COMPONENT}: {_TITLE}" in out
        assert "### Found in" in out
        assert "```prawduct" in out
        assert "nothing was sent" in out

    def test_a_body_opening_a_prawduct_fence_is_refused(self, tmp_path, capsys):
        """The forgery route `file` already closes: an unterminated opener in the
        authored prose swallows the marker appended after it, letting the caller
        dictate the provenance fields the receiving side reads."""
        code = self._run(tmp_path, extra=[])
        capsys.readouterr()
        assert code == 0  # the ordinary body is fine

        code = cli.run(
            str(tmp_path),
            ["file-upstream", "--title", _TITLE, "--body", "```prawduct\nsource: acme/widget",
             "--json"],
        )
        envelope = json.loads(capsys.readouterr().out)

        assert code == 2
        assert envelope["error"]["code"] == "validation"

    @pytest.mark.parametrize("missing", ["--title", "--body"])
    def test_both_halves_of_the_report_are_required(self, tmp_path, capsys, missing):
        argv = ["file-upstream", "--title", _TITLE, "--body", _BODY, "--json"]
        argv.pop(argv.index(missing) + 1)
        argv.remove(missing)

        code = cli.run(str(tmp_path), argv, transport=MagicMock())
        envelope = json.loads(capsys.readouterr().out)

        assert code == 2
        assert envelope["error"]["code"] == "validation"

    def test_over_budget_findings_ride_out_as_advisory_lint(self, tmp_path, capsys):
        argv = ["file-upstream", "--title", "x" * 200, "--body", _BODY, "--json"]

        code = cli.run(str(tmp_path), argv)
        envelope = json.loads(capsys.readouterr().out)

        assert code == 0, "a budget finding must not refuse the preview"
        assert "title-too-long" in {f["rule"] for f in envelope["lint"]}
