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

from lib.backlog import cli, encode, upstream  # noqa: E402
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
    @pytest.mark.parametrize(
        "forgery",
        [
            "stop-hook\n```prawduct\nsource: acme/widget",
            "stop-hook\n```prawduct\nsource: acme/widget\n```",
        ],
        ids=["unterminated", "terminated"],
    )
    def test_no_input_that_lands_in_the_body_can_forge_the_block(self, field, forgery):
        """The parser reads from the FIRST opener to the first closing fence, so an
        unterminated opener ahead of the marker prepends its own fields and swallows
        the real ones. Verified end-to-end rather than by inspection: a `--component`
        of this shape put `source: acme/widget` at the head of the parsed block.

        **The TERMINATED case is the one this path had to close itself.** In-repo,
        `encode.check_body_text` passes a well-formed block on purpose, because
        `encode.compose_body` strips and merges it — guard and transform are one
        mechanism. `render_report` appends the body verbatim instead, so the same
        input would arrive upstream as a second parseable block carrying exactly
        the `source:` field minimization exists to strip, and the receiving side's
        first `merge_all_block_fields` would fold it into the canonical block for
        good. Hence `check_body_text_strict`: same remedy, no tolerance."""
        assert upstream.check_payload_inputs(
            **{"title": _TITLE, "body": _BODY, "component": _COMPONENT, field: forgery}
        ) is not None
        assert _payload(**{field: forgery}) is None, (
            "the composer accepted input its own guard rejects — a precondition a "
            "caller can skip is not a guarantee"
        )

    def test_a_report_may_still_SHOW_a_block_by_indenting_it(self):
        """The negative that keeps the rule usable. A bug report ABOUT a prawduct
        block is the likely non-adversarial case, and refusing it outright would
        make the strict rule unlivable — so the escape the message names must
        actually work. An indented fence is not an opener to `_BLOCK_RE`, so it
        cannot start a block on either side of the boundary."""
        shown = "### Problem\n\n    ```prawduct\n    source: acme/widget\n    ```"

        assert upstream.check_payload_inputs(
            title=_TITLE, body=shown, component=_COMPONENT
        ) is None
        payload = _payload(body=shown)
        assert payload is not None

        # Asserted against the PARSER, not a substring count. The indented text
        # contains the literal "```prawduct" and always will — that is the whole
        # point of showing one — so a naive count reads 2 and says nothing about
        # whether a second block exists. What must hold is that the receiving side
        # sees exactly the three trimmed fields, which is what
        # `merge_all_block_fields` (the call that folds a stray block in) reads.
        merged = encode.merge_all_block_fields(payload["body"])
        assert sorted(merged) == ["found_in", "source-key", "v"], (
            "the indented fence parsed as a second block — `merge_all_block_fields` "
            "is the receiving side's first call and it folds EVERY block, so an "
            f"extra key here is a field crossing the owner boundary: {sorted(merged)}"
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

    def test_the_preview_says_a_non_conforming_TITLE_would_refuse(self, tmp_path, capsys):
        """A budget finding that BLOCKS must not read like the ones that do not.

        The four `title-*` rules are hard refusals on the send arm; the body-budget
        rules never block. Both reach the operator through `lint:` lines, and
        `LintFinding.severity` is hardcoded "warn", so without this the operator
        reviews the bytes, approves the digest, and discovers at send that the
        filing was never possible — a second round on the path §5 calls Fast."""
        long_title = "x" * 90

        code = cli.run(str(tmp_path), [
            "file-upstream", "--title", long_title, "--body", _BODY,
            "--component", _COMPONENT, "--json",
        ])
        envelope = json.loads(capsys.readouterr().out)

        assert code == 0, "the preview itself still renders — it refuses nothing"
        assert any(
            w.startswith("filing would refuse (validation)") and "title" in w
            for w in envelope.get("warnings", [])
        ), (
            "the preview handed over a digest for a payload the send arm can only "
            f"refuse, with no word of it: {envelope.get('warnings')}"
        )

    def test_every_no_transport_refusal_the_send_arm_has_is_predicted(self, tmp_path):
        """The invariant behind `previewable_refusals`, DERIVED rather than listed.

        An earlier cut of this test read the send arm's source and then iterated
        three remembered names — which is the hand-enumeration it exists to
        replace, one level up: a sixth refusal added to `send` matched no name and
        the test stayed green while the preview silently regressed. So the names
        come out of the AST.

        The exclusions are the only hardcoded part, and each carries its reason,
        because an exclusion is a claim about WHY a refusal is unpredictable and
        that claim has to be readable."""
        import ast
        import inspect
        import textwrap

        excluded = {
            # Answered by the CLI on both arms before anything is composed; and
            # composing a payload aimed at the pin in order to lint it would report
            # budget findings about bytes this caller never asked to send.
            "check_target": "the CLI answers it ahead of both arms",
            # A preview has no token to compare, and that absence is what MAKES it
            # a preview rather than a send.
            "check_approval": "a preview has no approval token by definition",
            # Needs the transport this preview path is defined never to touch.
            "check_authenticated": "requires the transport the preview never holds",
            # Predicted, but not through this function: `_file_upstream_preview`
            # calls it directly and returns its `validation` error before anything
            # is composed — there is no payload to attach a "would refuse" note to
            # yet, because these inputs are what a payload would be composed FROM.
            # Surfaced by this derivation, which the hardcoded list it replaced had
            # simply never noticed.
            "check_payload_inputs": "the preview refuses on it directly, pre-compose",
        }

        send_tree = ast.parse(textwrap.dedent(inspect.getsource(upstream.send)))
        called = {
            node.func.id
            for node in ast.walk(send_tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        refusals = {
            name for name in called
            if name.startswith("check_") or name.endswith("_refusal")
        }
        assert refusals, "no refusal-shaped call found in `send` — the derivation broke"

        predicted = inspect.getsource(upstream.previewable_refusals)
        for name in sorted(refusals - set(excluded)):
            assert name in predicted, (
                f"`send` refuses via {name}() and `previewable_refusals` does not "
                "ask it, so an operator can approve a digest for a filing that can "
                "only refuse. Either predict it, or add it to `excluded` above with "
                "the reason it cannot be predicted."
            )

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


# --- the send arm ------------------------------------------------------------


def _product_repo(tmp_path, *, identity="acme/widget", preference=None):
    """A repo whose identity resolves and is not the pinned target."""
    artifacts = tmp_path / ".prawduct" / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".prawduct" / "project-state.yaml").write_text(
        f"backlog_service_repo: {identity}\n", encoding="utf-8"
    )
    if preference is not None:
        artifacts.joinpath("project-preferences.md").write_text(
            f"## Workflow\n\n- **Upstream filing**: {preference}\n", encoding="utf-8"
        )
    return tmp_path


def _send_argv(project_dir, *, approve=None, json_mode=True):
    if approve is None:
        _payload, approve = upstream.render_preview(
            project_dir, title=_TITLE, body=_BODY, component=_COMPONENT
        )
    argv = ["file-upstream", "--title", _TITLE, "--body", _BODY, "--component", _COMPONENT,
            "--approve", approve]
    return argv + ["--json"] if json_mode else argv


class TestTheConsentPreferenceReads:
    """Design §4.1. The row is *authored* in Wave B, so every path this can take
    today lands on the default — which is why the default has to be the safe one."""

    def _write(self, tmp_path, text):
        artifacts = tmp_path / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        artifacts.joinpath("project-preferences.md").write_text(text, encoding="utf-8")

    def test_no_preferences_file_is_the_default_and_not_an_anomaly(self, tmp_path):
        assert upstream.read_filing_preference(tmp_path) == (upstream.PREF_ASK_USER, None)

    def test_a_preferences_file_with_no_row_is_the_default(self, tmp_path):
        self._write(tmp_path, "## Workflow\n\n- **PR creation**: wait_for_user\n")

        assert upstream.read_filing_preference(tmp_path) == (upstream.PREF_ASK_USER, None)

    @pytest.mark.parametrize(
        "value", ["ask-user", "never-file", "always-file"],
    )
    def test_each_defined_state_reads_back(self, tmp_path, value):
        self._write(tmp_path, f"- **Upstream filing**: {value} (default: ask-user — …)\n")

        assert upstream.read_filing_preference(tmp_path) == (value, None)

    @pytest.mark.parametrize(
        "line",
        [
            "- **Upstream filing**: `never-file`\n",
            "- **Upstream filing**:   NEVER-FILE   \n",
            "*  **Upstream filing** :never-file\n",
        ],
        ids=["backticked", "shouty-and-padded", "star-bullet-tight-colon"],
    )
    def test_the_row_is_read_the_way_a_human_writes_it(self, tmp_path, line):
        """A hard mechanical guarantee that a stray backtick turns off is not one.
        Strictness at a hand-edited seam fails in the permissive direction here —
        the value being missed is the one that DISABLES filing."""
        self._write(tmp_path, line)

        assert upstream.read_filing_preference(tmp_path)[0] == upstream.PREF_NEVER_FILE

    def test_a_file_that_cannot_be_read_REFUSES_rather_than_defaulting(self, tmp_path):
        """The stake is `never-file`, which §4.3 calls a hard mechanical guarantee.

        An absent file is ordinary — no product has this row yet — and an
        unparseable VALUE still establishes that the row does not say
        `never-file`. A file that exists and cannot be read establishes nothing,
        so defaulting it to `ask-user` enforced the guarantee by hoping the
        operator read a warning which, on the send arm, rides out on the SUCCESS
        envelope after the irreversible write. `authority fails closed` is the
        recorded posture for a check that cannot read its own input."""
        artifacts = tmp_path / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True)
        artifacts.joinpath("project-preferences.md").write_bytes(b"\xff\xfe not utf-8")
        state, warning = upstream.read_filing_preference(tmp_path)

        assert state == upstream.PREF_UNREADABLE
        assert warning is not None and upstream.PREF_NEVER_FILE in warning, (
            "the warning must still name the standing state at stake — it is what "
            "tells an operator WHY an unreadable file refuses rather than defaults"
        )
        refusal = upstream.check_preference(state)
        assert refusal is not None and refusal.code == "filing-disabled"

    def test_an_unreadable_preferences_file_stops_the_send_end_to_end(self, tmp_path, capsys):
        """The unit above proves the state and the check; this proves they are
        wired to each other on the arm that writes. A refusal nothing calls is
        the shape this whole guard set exists to avoid."""
        from tests.fakes.fake_github import FakeGitHub

        artifacts = tmp_path / ".prawduct" / "artifacts"
        artifacts.mkdir(parents=True)
        artifacts.joinpath("project-preferences.md").write_bytes(b"\xff\xfe not utf-8")
        fake = FakeGitHub()

        code = cli.run(str(tmp_path), [
            "file-upstream", "--title", _TITLE, "--body", _BODY,
            "--component", _COMPONENT, "--approve", "sha256:" + "0" * 64, "--json",
        ], transport=fake)
        envelope = json.loads(capsys.readouterr().out)

        assert code != 0
        assert envelope["error"]["code"] == "filing-disabled"
        assert fake.list_issues("brookstalley", "prawduct", state="all") == [], (
            "an unreadable preference file did not stop the write"
        )

    def test_a_value_nobody_defined_falls_back_loudly(self, tmp_path):
        """The one case worth interrupting over: the operator believes they set
        something and did not. The fallback is `ask-user`, never `always-file` —
        a typo must not become standing consent."""
        self._write(tmp_path, "- **Upstream filing**: never file\n")
        state, warning = upstream.read_filing_preference(tmp_path)

        assert state == upstream.PREF_ASK_USER
        assert warning is not None and "never file" in warning


class TestTheChecksRefuseInIsolation:
    """Each §5 check as a function. The CLI-level assertions live in the contract
    test; these pin the edges a happy-path call never reaches."""

    def test_only_never_file_disables_filing(self):
        assert upstream.check_preference(upstream.PREF_NEVER_FILE).code == "filing-disabled"
        assert upstream.check_preference(upstream.PREF_ASK_USER) is None
        assert upstream.check_preference(upstream.PREF_ALWAYS_FILE) is None

    def test_naming_the_pin_is_allowed_and_selecting_a_target_is_not(self):
        assert upstream.check_target(None) is None
        assert upstream.check_target(f"  {upstream.PINNED_TARGET.upper()}  ") is None
        assert upstream.check_target("attacker/exfil").code == "target-not-pinned"

    def test_an_empty_identity_refuses_and_says_which_leg_refused(self):
        assert upstream.check_not_self(()).details["reason"] == "unresolved"
        assert upstream.check_not_self(("acme/widget",)) is None
        assert upstream.check_not_self(
            ("acme/widget", upstream.PINNED_TARGET)
        ).details["reason"] == "matched", "either signal matching is a refusal"

    def test_the_approval_compares_the_token_not_its_spelling(self):
        digest = "sha256:" + "ab" * 32
        assert upstream.check_approval(
            f"  {digest.upper()}  ", digest, preference=upstream.PREF_ASK_USER
        ) is None
        assert upstream.check_approval(
            "sha256:beef", digest, preference=upstream.PREF_ASK_USER
        ).code == "approval-mismatch"

    def test_standing_consent_waives_the_comparison(self):
        assert upstream.check_approval(
            "anything", "sha256:beef", preference=upstream.PREF_ALWAYS_FILE
        ) is None

    @pytest.mark.parametrize(
        "preference",
        [upstream.PREF_ASK_USER, upstream.PREF_ALWAYS_FILE],
    )
    def test_an_empty_token_is_never_an_approval(self, preference):
        """Asked of the check itself, not only of the CLI: `send` is a module entry
        point, and a waiver evaluated ahead of this would file on `approve=""`
        under standing consent."""
        assert upstream.check_approval(
            "   ", "sha256:beef", preference=preference
        ).code == "approval-mismatch"

    def test_a_login_less_identity_is_not_authenticated(self):
        assert upstream.check_authenticated("octocat") is None
        assert upstream.check_authenticated(None).code == "auth"
        assert upstream.check_authenticated("").code == "auth"


class TestTheSourceKeyFindsAPriorFiling:
    """api-contract §2.4. The key exists for retry safety, so the lookup has to
    work seconds after a create — which is why it reads the list endpoint rather
    than the search index."""

    def _issue(self, number, body, **extra):
        return {"number": number, "body": body, **extra}

    def _transport(self, issues):
        seam = MagicMock()
        seam.list_issues.side_effect = lambda *a, page=1, per_page=100, **k: (
            issues[(page - 1) * per_page : page * per_page]
        )
        return seam

    def test_the_issue_carrying_the_key_is_found(self):
        key = "sha256:" + "cd" * 32
        seam = self._transport([
            self._issue(1, "unrelated"),
            self._issue(2, f"prose\n\n```prawduct\nv: 1\nsource-key: {key}\n```"),
        ])

        found = upstream.find_filed(seam, target=upstream.PINNED_TARGET, key=key)

        assert found["number"] == 2

    def test_a_key_nobody_filed_finds_nothing(self):
        seam = self._transport([self._issue(1, "```prawduct\nsource-key: sha256:other\n```")])

        assert upstream.find_filed(
            seam, target=upstream.PINNED_TARGET, key="sha256:mine"
        ) is None

    def test_a_pull_request_is_never_the_match(self):
        """The REST issues list interleaves PRs, and a PR carrying the marker text
        would otherwise be returned as the issue this report already filed."""
        key = "sha256:" + "ef" * 32
        seam = self._transport([
            self._issue(1, f"```prawduct\nsource-key: {key}\n```", pull_request={"url": "…"}),
        ])

        assert upstream.find_filed(seam, target=upstream.PINNED_TARGET, key=key) is None

    def test_the_scan_is_bounded_and_a_first_filing_does_not_walk_the_tracker(self):
        """The cost this bound exists for falls on the case that matches NOTHING.

        A retry finds its own issue on page one; a first-time filing matches
        nothing and, unbounded, pays for the tracker's entire history — every
        report, forever, growing. Asserted by counting pages fetched rather than
        by reading the constant, so raising the cap without meaning to fails
        here."""
        seam = self._transport([self._issue(n, "unrelated") for n in range(1, 1001)])

        assert upstream.find_filed(
            seam, target=upstream.PINNED_TARGET, key="sha256:matches-nothing"
        ) is None
        assert seam.list_issues.call_count == upstream.DEDUP_SCAN_PAGES, (
            "the miss path fetched a different number of pages than the bound "
            f"allows: {seam.list_issues.call_count}"
        )

    def test_a_match_inside_the_window_is_still_found(self):
        """The negative half — a bound tight enough to break retry safety would
        pass the test above and silently duplicate every retried filing."""
        key = "sha256:" + "ab" * 32
        issues = [self._issue(1, f"```prawduct\nsource-key: {key}\n```")]
        issues += [self._issue(n, "unrelated") for n in range(2, 500)]

        found = upstream.find_filed(self._transport(issues), target=upstream.PINNED_TARGET, key=key)

        assert found is not None and found["number"] == 1


class TestTheSendPathFiles:
    def test_the_filed_body_carries_the_key_the_lookup_matches(self, tmp_path, capsys):
        """The two halves of idempotency have to agree about the key: the marker
        stamped on the way out is the one `find_filed` reads on the way back."""
        fake = FakeGitHub()
        project = _product_repo(tmp_path)

        cli.run(str(project), _send_argv(project), transport=fake)
        envelope = json.loads(capsys.readouterr().out)
        filed = fake.list_issues(*upstream.PINNED_TARGET.split("/"), state="all")[0]

        key = upstream.source_key(
            submitter="acme/widget", title=_EXPECTED_TITLE,
            body=envelope["data"]["payload"]["body"].split("\n\n```prawduct")[0],
        )
        assert upstream.find_filed(
            fake, target=upstream.PINNED_TARGET, key=key
        )["number"] == filed["number"]

    def test_a_lookup_that_cannot_run_files_anyway_and_says_so(self, tmp_path, capsys):
        """XP7 is submit-or-nothing, and a slow flow degrades "submit" into
        "nothing". A dedup read is retry-safety, not one of the five guarantees —
        so it degrades loudly rather than blocking the report. The cost is a
        duplicate a maintainer can close; the alternative costs the signal."""
        class _NoListing(FakeGitHub):
            def list_issues(self, *args, **kwargs):
                raise upstream.tx.TransportError("unavailable", "listing is down")

        fake = _NoListing()
        project = _product_repo(tmp_path)

        assert cli.run(str(project), _send_argv(project), transport=fake) == 0
        envelope = json.loads(capsys.readouterr().out)

        assert envelope["data"]["created"] is True
        assert any("duplicate" in w for w in envelope["warnings"])

    def test_the_human_view_names_the_filed_issue(self, tmp_path, capsys):
        """The `--json` envelope is not the only consumer: a reader who cannot
        tell a send from a preview will file twice."""
        fake = FakeGitHub()
        project = _product_repo(tmp_path)

        cli.run(str(project), _send_argv(project, json_mode=False), transport=fake)
        out = capsys.readouterr().out

        assert "nothing was sent" not in out
        assert f"filed: https://github.com/{upstream.PINNED_TARGET}/issues/1" in out

    def test_the_human_view_distinguishes_a_re_file(self, tmp_path, capsys):
        fake = FakeGitHub()
        project = _product_repo(tmp_path)

        cli.run(str(project), _send_argv(project, json_mode=False), transport=fake)
        capsys.readouterr()
        cli.run(str(project), _send_argv(project, json_mode=False), transport=fake)

        assert "already filed" in capsys.readouterr().out

    def test_an_empty_approval_token_is_not_an_approval(self, tmp_path, capsys):
        """Under `always-file` the token's VALUE is waived, so an empty one is all
        that stands between rendering a payload and filing it."""
        fake = FakeGitHub()
        project = _product_repo(tmp_path, preference="always-file")

        code = cli.run(
            str(project),
            ["file-upstream", "--title", _TITLE, "--body", _BODY, "--approve=", "--json"],
            transport=fake,
        )
        envelope = json.loads(capsys.readouterr().out)

        assert code != 0
        assert envelope["error"]["code"] == "validation"
        assert [c for c in fake.calls if c[0] == "create_issue"] == []
