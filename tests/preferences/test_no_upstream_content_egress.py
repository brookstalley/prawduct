"""Project-preferences enforcement: the upstream-filing contract (XP7).

Enforces the `security-model.md` § Direction norm: a governed product's content
never leaves that product's own repository and owner without an explicit owner
decision. The hazard is concrete — a **private** consuming repo filing a bug
report into prawduct's **public** tracker would carry that repo's paths, code
excerpts, learnings prose and product detail across a trust boundary, in a
direction no one chose.

**This file used to enforce the guarantee by ABSENCE**, and now enforces it by
contract. The interim rule was a token scan: `file-upstream` must appear on no
shipped surface, and prawduct's own tracker must appear nowhere in the backlog
adapter. That was the right rule while the surface was designed-but-unbuilt
(roadmap wave W3, tracked by BKL-7Q4M), and it was always written to be replaced
by "one asserting the redaction and consent contract" the moment BKL-7Q4M landed.

It landed. `documentation/backlog-service-upstream-filing.md` §5 is the reviewed
design the norm was waiting on, and this file now asserts what §5 makes
mechanically true. The swap is a **strengthening**, which is the only direction
the norm permits: an absence proves nothing about a surface once the surface
exists, while these assertions fail loudly if the built one stops refusing.
Deleting or relaxing them to let an unreviewed filing path through is the one
response that is never correct.

**All five §5 checks are live here.** The adapter refuses to file unless all five
hold: (1) the preference is not `never-file`, (2) the target is pinned, (3) the
running repo is not the target (no self-file), (4) the approval digest matches the
re-rendered bytes, and (5) the session is authenticated. Each is asserted to refuse
**independently** — one class per check, each starting from a repo where the other
four hold — because a suite that only ever exercises them together cannot tell a
live check from one shadowed by its neighbour.

**Every refusal is asserted against the seam, not against the envelope.** "An
error was returned" and "nothing was written" are different claims, and only the
second is the guarantee: the assertions below read the fake's recorded calls, so a
refusal that returned an error *after* creating an issue fails here rather than
passing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugin"
for _entry in (str(PLUGIN_ROOT), str(REPO_ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from lib.backlog import cli, transport as tx, upstream  # noqa: E402
from tests.fakes.fake_github import FakeGitHub  # noqa: E402

#: Prawduct's own public tracker, spelled out. Pinned as a **literal** rather
#: than read from the constant under test: an assertion written relative to the
#: value it polices agrees with that value however wrong the value has become,
#: which is the one failure a target pin cannot afford.
UPSTREAM_TRACKER = "brookstalley/prawduct"


class TestTheTargetIsPinned:
    """§5 check 2. The target is the plugin's declared canonical upstream repo —
    a plugin constant, not a caller-supplied `--repo`. This closes the
    unconstrained-`--repo` hole: shape-validating an arbitrary `owner/repo` says
    the string is well-formed, which is not an owner constraint at all."""

    def test_the_pinned_target_is_prawducts_own_tracker(self):
        assert upstream.PINNED_TARGET == UPSTREAM_TRACKER

    def test_a_payload_targets_the_pin_with_no_repo_given(self):
        payload = upstream.build_payload(
            title="t", body="b", found_in="1.0.0", submitter="acme/widget"
        )

        assert payload["repo"] == UPSTREAM_TRACKER

    def test_a_repo_that_disagrees_with_the_pin_is_refused(self, tmp_path, capsys):
        code = cli.run(
            str(tmp_path),
            ["file-upstream", "--repo", "attacker/exfil", "--title", "a symptom worth reporting",
             "--body", "prose", "--json"],
            transport=MagicMock(),
        )
        envelope = json.loads(capsys.readouterr().out)

        assert code != 0
        assert envelope["status"] == "error"
        assert envelope["error"]["code"] == "target-not-pinned"
        assert envelope["error"]["retryable"] is False

    def test_a_repo_that_agrees_with_the_pin_is_honored_and_changes_nothing(
        self, tmp_path, capsys
    ):
        """Naming the pin is allowed — a caller may be explicit. What it must not
        do is *select* the target, so the rendered payload is identical either
        way."""
        base = ["file-upstream", "--title", "a symptom worth reporting", "--body", "prose",
                "--json"]

        assert cli.run(str(tmp_path), base, transport=MagicMock()) == 0
        without = json.loads(capsys.readouterr().out)
        assert cli.run(
            str(tmp_path), base + ["--repo", UPSTREAM_TRACKER], transport=MagicMock()
        ) == 0
        with_repo = json.loads(capsys.readouterr().out)

        assert without["data"] == with_repo["data"]
        assert without["data"]["payload"]["repo"] == UPSTREAM_TRACKER

    def test_the_digest_covers_the_target(self):
        """A digest over the body alone would let a payload approved for prawduct's
        tracker be sent to a repo the reviewer never saw."""
        approved = upstream.build_payload(
            title="t", body="b", found_in="1.0.0", submitter="acme/widget"
        )
        diverted = upstream.build_payload(
            title="t", body="b", found_in="1.0.0", submitter="acme/widget",
            target="attacker/exfil",
        )

        assert upstream.payload_digest(approved) != upstream.payload_digest(diverted)


class TestNothingFilesWithoutAnApproval:
    """§5's preview-by-default posture. Filing is irreversible — GitHub has no
    issue delete for an ordinary caller and never reuses numbers — so the default
    call renders bytes and stops. A second, digest-bearing call sends."""

    @pytest.mark.parametrize(
        "extra",
        [[], ["--component", "stop-hook"], ["--repo", UPSTREAM_TRACKER]],
        ids=["bare", "with-component", "with-matching-repo"],
    )
    def test_no_unapproved_invocation_reaches_the_transport_seam(self, tmp_path, capsys, extra):
        """Not "performs no write" — performs no CALL. A preview that cannot reach
        the seam cannot send, whatever a later edit does to the handler."""
        seam = MagicMock()

        cli.run(
            str(tmp_path),
            ["file-upstream", "--title", "a symptom worth reporting", "--body", "prose",
             "--json"] + extra,
            transport=seam,
        )
        capsys.readouterr()

        assert seam.mock_calls == []

    def test_no_unapproved_invocation_creates_anything_on_the_target(self, tmp_path, capsys):
        fake = FakeGitHub()

        cli.run(
            str(tmp_path),
            ["file-upstream", "--title", "a symptom worth reporting", "--body", "prose", "--json"],
            transport=fake,
        )
        capsys.readouterr()

        assert fake.list_issues(*UPSTREAM_TRACKER.split("/"), state="all") == []

    def test_the_preview_says_so_in_both_views(self, tmp_path, capsys):
        """A reviewer who thinks the preview already filed will not approve, and
        one who thinks a filed issue was only previewed will file twice."""
        argv = ["file-upstream", "--title", "a symptom worth reporting", "--body", "prose"]

        cli.run(str(tmp_path), argv)
        assert "nothing was sent" in capsys.readouterr().out

        cli.run(str(tmp_path), argv + ["--json"])
        assert json.loads(capsys.readouterr().out)["data"]["sent"] is False


class TestTheOutboundPayloadIsMinimized:
    """§2/§3. The bytes that cross are fixed and inspectable. What the design does
    NOT claim is a redactor — "no proprietary content" is not mechanically
    enforceable at a prose boundary, and the guarantee is L1 authoring plus the
    human's verbatim review. What IS mechanical is the provenance trim, and that
    is what these assert."""

    def test_the_marker_carries_three_fields_and_no_product_name(self):
        """The in-repo block's `provenance: {source: <product>}` is the leak the
        trim exists to prevent."""
        body = upstream.build_payload(
            title="t", body="b", found_in="1.0.0", submitter="acme/widget"
        )["body"]
        marker = body[body.rindex("```prawduct") :]

        assert [line.split(":", 1)[0] for line in marker.splitlines()[1:-1]] == [
            "v", "found_in", "source-key",
        ]
        assert "acme" not in marker, "the submitter crosses only as a one-way digest"

    @pytest.mark.parametrize("flag", ["--body", "--component"])
    def test_no_caller_input_can_forge_the_provenance_block(self, tmp_path, capsys, flag):
        """An unterminated ```prawduct opener anywhere in the body swallows the
        marker appended after it, letting the caller dictate the fields the
        receiving side reads — including the `source:` product name the trim exists
        to strip. Asked of every input that lands in the body, not just the one that
        was guarded first: `--component` was interpolated verbatim, and a guard on
        `--body` alone left the whole block forgeable."""
        argv = ["file-upstream", "--title", "a symptom worth reporting", "--body", "prose",
                "--json"]
        if flag == "--body":
            argv[argv.index("--body") + 1] = "```prawduct\nsource: acme/widget"
        else:
            argv += [flag, "stop-hook\n```prawduct\nsource: acme/widget"]

        code = cli.run(str(tmp_path), argv, transport=MagicMock())
        envelope = json.loads(capsys.readouterr().out)

        assert code != 0
        assert envelope["status"] == "error"

    def test_the_composer_refuses_what_its_own_guard_rejects(self):
        """Enforced where the block is BUILT, not documented as a precondition next
        to it. The precondition form is what let `--component` through: the CLI
        applied the guard to one input and the composer trusted the caller."""
        assert upstream.build_payload(
            title="t", body="```prawduct\nsource: acme/widget", found_in="1.0.0",
            submitter="acme/widget",
        ) is None

    def test_budgets_are_reported_not_silently_applied(self, tmp_path, capsys):
        """Truncating an outbound report after the reviewer approved it is the one
        content failure the verbatim review cannot catch."""
        code = cli.run(
            str(tmp_path),
            ["file-upstream", "--title", "x" * 200, "--body", "prose", "--json"],
            transport=MagicMock(),
        )
        envelope = json.loads(capsys.readouterr().out)

        assert code == 0
        assert "title-too-long" in {f["rule"] for f in envelope["lint"]}
        assert envelope["data"]["payload"]["title"].count("x") == 200


# --- the send arm ------------------------------------------------------------

#: A report that would file cleanly: the rendered title conforms to the issue
#: standard's §1 rules and no input trips the fence guard. Every class below
#: starts from THIS and breaks exactly one check, so a refusal it observes can
#: only have come from the check it broke.
FILEABLE_TITLE = "gate blocks on in-flight background work"
FILEABLE_BODY = "### Problem\n\nA gate blocks while background work still produces the diff."
FILEABLE_COMPONENT = "stop-hook"


def a_product_repo(tmp_path, *, identity="acme/widget", preference=None):
    """A repo where all five checks hold: a resolvable identity that is not the pin."""
    artifacts = tmp_path / ".prawduct" / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".prawduct" / "project-state.yaml").write_text(
        f"backlog_service_repo: {identity}\n", encoding="utf-8"
    )
    if preference is not None:
        artifacts.joinpath("project-preferences.md").write_text(
            f"## Workflow\n\n- **Upstream filing**: {preference} (default: ask-user)\n",
            encoding="utf-8",
        )
    return tmp_path


def send_argv(project_dir, *, approve=None, extra=()):
    """The send call for the fileable report, approved with its own real digest."""
    if approve is None:
        _payload, approve = upstream.render_preview(
            project_dir, title=FILEABLE_TITLE, body=FILEABLE_BODY,
            component=FILEABLE_COMPONENT,
        )
    return [
        "file-upstream", "--title", FILEABLE_TITLE, "--body", FILEABLE_BODY,
        "--component", FILEABLE_COMPONENT, "--approve", approve, "--json",
    ] + list(extra)


def assert_filed_nothing(fake):
    """Nothing was WRITTEN — the guarantee. An error envelope is not the claim.

    Read off the fake's own recording rather than off the returned envelope,
    because a check that refuses after creating the issue returns an
    indistinguishable error and would pass every envelope-shaped assertion.
    """
    assert [call for call in fake.calls if call[0] == "create_issue"] == []
    assert fake.list_issues(*UPSTREAM_TRACKER.split("/"), state="all") == []


def refuse(tmp_path, capsys, fake, argv):
    """Run a send that must refuse; return its envelope, asserting nothing filed."""
    code = cli.run(str(tmp_path), argv, transport=fake)
    envelope = json.loads(capsys.readouterr().out)
    assert code != 0
    assert envelope["status"] == "error"
    assert envelope["error"]["retryable"] is False
    assert_filed_nothing(fake)
    return envelope


class TestTheHappyPathFiles:
    """The control. Every refusal class below is only evidence that a check is
    live if the same call, unbroken, actually files — otherwise a send path that
    refuses everything would satisfy all five."""

    def test_an_approved_report_files_exactly_once(self, tmp_path, capsys):
        fake = FakeGitHub()
        project = a_product_repo(tmp_path)

        code = cli.run(str(project), send_argv(project), transport=fake)
        envelope = json.loads(capsys.readouterr().out)

        assert code == 0
        assert envelope["data"]["sent"] is True
        assert envelope["data"]["created"] is True
        assert len([c for c in fake.calls if c[0] == "create_issue"]) == 1
        filed = fake.list_issues(*UPSTREAM_TRACKER.split("/"), state="all")
        assert [issue["number"] for issue in filed] == [envelope["data"]["issue"]["number"]]

    def test_what_lands_upstream_is_byte_for_byte_the_approved_payload(self, tmp_path, capsys):
        """"Sent == previewed" is the whole point of the digest, so it is asserted
        against the issue the target actually holds, not against the envelope the
        sender printed."""
        fake = FakeGitHub()
        project = a_product_repo(tmp_path)
        payload, _digest = upstream.render_preview(
            project, title=FILEABLE_TITLE, body=FILEABLE_BODY, component=FILEABLE_COMPONENT
        )

        cli.run(str(project), send_argv(project), transport=fake)
        capsys.readouterr()

        filed = fake.list_issues(*UPSTREAM_TRACKER.split("/"), state="all")[0]
        assert filed["title"] == payload["title"]
        assert filed["body"] == payload["body"]
        assert filed["labels"] == [], "§2 files label-less; a non-collaborator cannot set labels"

    def test_a_re_file_returns_the_existing_issue_and_creates_nothing(self, tmp_path, capsys):
        """api-contract §2.4: the `source-key:` marker makes a retry safe. The
        second call is the one a crashed-after-create caller makes."""
        fake = FakeGitHub()
        project = a_product_repo(tmp_path)

        cli.run(str(project), send_argv(project), transport=fake)
        first = json.loads(capsys.readouterr().out)
        cli.run(str(project), send_argv(project), transport=fake)
        second = json.loads(capsys.readouterr().out)

        assert second["data"]["created"] is False
        assert second["data"]["sent"] is True
        assert second["data"]["issue"] == first["data"]["issue"]
        assert len([c for c in fake.calls if c[0] == "create_issue"]) == 1


class TestThePreferenceCanHardRefuse:
    """§5 check 1. `never-file` is the one guarantee §4.3 calls mechanical and
    unconditional — no digest, identity or authentication reaches past it."""

    def test_never_file_refuses_a_perfectly_valid_approval(self, tmp_path, capsys):
        fake = FakeGitHub()
        project = a_product_repo(tmp_path, preference="never-file")

        envelope = refuse(project, capsys, fake, send_argv(project))

        assert envelope["error"]["code"] == "filing-disabled"

    def test_the_preview_says_filing_would_refuse(self, tmp_path, capsys):
        """The same wasted round the self-file warning exists to prevent: without
        this the operator reviews the bytes, approves the digest, and only then
        learns filing is off — on the one preference state that can never be
        talked out of refusing."""
        project = a_product_repo(tmp_path, preference="never-file")

        cli.run(
            str(project),
            ["file-upstream", "--title", FILEABLE_TITLE, "--body", FILEABLE_BODY, "--json"],
            transport=MagicMock(),
        )
        envelope = json.loads(capsys.readouterr().out)

        assert any("filing-disabled" in w for w in envelope["warnings"])

    @pytest.mark.parametrize(
        "preference", [None, "ask-user", "wharrgarbl"],
        ids=["absent", "explicit-default", "unrecognised"],
    )
    def test_only_a_real_never_file_disables_filing(self, tmp_path, capsys, preference):
        """The default must be `ask-user` on every path that is not a recognised
        state — an absent row, or a value nobody defined. Reading either as
        `always-file` would turn a typo into standing consent; reading either as
        `never-file` would refuse legitimate reports on a misspelling."""
        fake = FakeGitHub()
        project = a_product_repo(tmp_path, preference=preference)

        assert cli.run(str(project), send_argv(project), transport=fake) == 0
        assert json.loads(capsys.readouterr().out)["data"]["created"] is True


class TestNoSelfFile:
    """§5 check 3, carrying its 2026-07-24 amendment: identity resolves from BOTH
    `backlog_service_repo` and the `origin` remote, either match refuses, and an
    identity that resolves from neither refuses too."""

    def _origin(self, tmp_path, url):
        git = tmp_path / ".git"
        git.mkdir(exist_ok=True)
        (git / "config").write_text(f'[remote "origin"]\n\turl = {url}\n', encoding="utf-8")

    def test_THIS_repo_refuses_to_self_file(self):
        """The live case, asserted against the real checkout rather than a fixture.

        Every other case here synthesizes an identity under `tmp_path`, which
        tests the comparison but not the thing the acceptance criterion actually
        claims: that running `file-upstream` *in prawduct's own working copy*
        refuses. That is exactly the configuration a maintainer is in when they
        reach for the op, and it is the one no fixture can stand in for — the
        `origin` remote and `backlog_service_repo` are real here, so a resolver
        that silently stopped reading either would still pass every fixture case
        above and fail only in the place nobody tests.

        Deliberately calls the resolver + check rather than the CLI: this must not
        depend on a transport, and the refusal is a pure function of identity."""
        identities = upstream.resolve_self_identity(REPO_ROOT)

        assert identities, (
            "prawduct's own checkout resolved NO identity — the fail-closed leg "
            "would refuse anyway, but for the wrong reason, and this repo is the "
            "one place both signals are genuinely present"
        )
        refusal = upstream.check_not_self(identities)
        assert refusal is not None and refusal.code == "self-file"
        assert refusal.details["reason"] == "matched", (
            "this repo refused as an UNRESOLVED identity rather than as a match — "
            "the live self-file case is not being exercised"
        )
        assert "backlog file" in refusal.message, (
            "XP7's parenthetical is that a self-file ROUTES to its own backlog; "
            "the refusal must name that route, not merely report a wall"
        )

    def test_the_configured_backlog_repo_alone_refuses(self, tmp_path, capsys):
        fake = FakeGitHub()
        project = a_product_repo(tmp_path, identity=UPSTREAM_TRACKER)

        envelope = refuse(project, capsys, fake, send_argv(project))

        assert envelope["error"]["code"] == "self-file"
        assert envelope["error"]["details"]["reason"] == "matched"

    def test_the_git_remote_alone_refuses(self, tmp_path, capsys):
        """The leg that matters most: `backlog_service_repo` is unset in every
        pre-cutover repo, so an identity keyed on it alone is inert exactly where
        the guarantee is needed."""
        fake = FakeGitHub()
        self._origin(tmp_path, f"https://github.com/{UPSTREAM_TRACKER}.git")

        envelope = refuse(tmp_path, capsys, fake, send_argv(tmp_path))

        assert envelope["error"]["code"] == "self-file"
        assert envelope["error"]["details"]["reason"] == "matched"

    def test_an_identity_that_resolves_from_neither_signal_refuses(self, tmp_path, capsys):
        """The fail-closed leg, and the one a naive implementation gets backwards:
        "we could not tell" is a refusal, not a pass."""
        fake = FakeGitHub()

        envelope = refuse(tmp_path, capsys, fake, send_argv(tmp_path))

        assert envelope["error"]["code"] == "self-file"
        assert envelope["error"]["details"]["reason"] == "unresolved"

    def test_the_refusal_routes_rather_than_merely_erroring(self, tmp_path, capsys):
        """XP7 reads "never let prawduct's own repo self-file upstream *(it routes
        to its own backlog)*" — the route is part of the requirement, so it is
        asserted on the message a human reads, not only on the code."""
        fake = FakeGitHub()
        project = a_product_repo(tmp_path, identity=UPSTREAM_TRACKER)

        envelope = refuse(project, capsys, fake, send_argv(project))

        assert "backlog file" in envelope["error"]["message"]

    def test_a_lookalike_spelling_of_the_target_still_refuses(self, tmp_path, capsys):
        """GitHub owner/repo names are case-insensitive, so a case-sensitive
        comparison here is fail-open on an input the caller picks."""
        fake = FakeGitHub()
        project = a_product_repo(tmp_path, identity="BrooksTalley/Prawduct")

        assert refuse(project, capsys, fake, send_argv(project))["error"]["code"] == "self-file"


class TestTheTargetIsPinnedOnTheSendArmToo:
    """§5 check 2 again, on the arm that writes. The class above asserts it on the
    preview, which reaches no seam at all — so on its own it cannot say whether a
    *send* naming another target files there. `send` re-asks rather than trusting
    the CLI's pre-check, because it is a module entry point of its own, and that
    leg is only verified from here."""

    def test_an_approved_send_to_another_target_refuses_and_writes_nothing(
        self, tmp_path, capsys
    ):
        fake = FakeGitHub()
        project = a_product_repo(tmp_path)

        envelope = refuse(
            project, capsys, fake, send_argv(project, extra=["--repo", "attacker/exfil"])
        )

        assert envelope["error"]["code"] == "target-not-pinned"
        assert fake.list_issues("attacker", "exfil", state="all") == []

    def test_the_module_entry_point_refuses_it_without_the_cli(self, tmp_path):
        """Asked of `upstream.send` directly: the CLI's pre-check short-circuits
        every CLI-level call, so a `send` that had dropped its own check-2 leg
        would pass every test routed through `cli.run`."""
        fake = FakeGitHub()
        project = a_product_repo(tmp_path)
        _payload, digest = upstream.render_preview(
            project, title=FILEABLE_TITLE, body=FILEABLE_BODY, component=FILEABLE_COMPONENT
        )

        result = upstream.send(
            project, fake, title=FILEABLE_TITLE, body=FILEABLE_BODY,
            component=FILEABLE_COMPONENT, approve=digest, requested_repo="attacker/exfil",
        )

        assert result["error"]["code"] == "target-not-pinned"
        assert_filed_nothing(fake)


class TestTheProductionEntryPointReachesTheSeam:
    """`prawduct-hook` calls `cli.run(project_dir, argv)` with no transport, so
    every test that injects a fake is blind to whether the op resolves one. A send
    arm that does not dies on `None.get_authenticated_user()` inside the CLI's
    boundary catch and reports the whole op as a retryable `unavailable` — inert,
    and disguised as a transient outage."""

    def test_the_send_arm_builds_a_transport_when_none_is_injected(
        self, tmp_path, capsys, monkeypatch
    ):
        fake = FakeGitHub()
        monkeypatch.setattr(tx, "GhTransport", lambda *a, **k: fake)
        project = a_product_repo(tmp_path)

        assert cli.run(str(project), send_argv(project)) == 0
        assert json.loads(capsys.readouterr().out)["data"]["created"] is True

    def test_the_preview_arm_builds_none(self, tmp_path, capsys, monkeypatch):
        """The other half of the same wiring, and the reason the resolution sits in
        the send branch rather than at the top of the handler where its 17 siblings
        put it: a preview must not construct a seam it could then reach."""
        def _refuse_to_build(*_args, **_kwargs):
            raise AssertionError("the preview arm constructed a transport")

        monkeypatch.setattr(tx, "GhTransport", _refuse_to_build)
        project = a_product_repo(tmp_path)

        code = cli.run(
            str(project),
            ["file-upstream", "--title", FILEABLE_TITLE, "--body", FILEABLE_BODY, "--json"],
        )

        assert code == 0
        assert json.loads(capsys.readouterr().out)["data"]["sent"] is False


class TestTheApprovalCoversTheBytes:
    """§5 check 4. The payload is re-rendered and re-digested at send, so an
    approval given for payload A cannot authorize payload B."""

    def test_a_digest_approved_for_another_payload_does_not_authorize_this_one(
        self, tmp_path, capsys
    ):
        fake = FakeGitHub()
        project = a_product_repo(tmp_path)
        _payload, other = upstream.render_preview(
            project, title=FILEABLE_TITLE, body="### Problem\n\nSomething else entirely.",
            component=FILEABLE_COMPONENT,
        )

        envelope = refuse(project, capsys, fake, send_argv(project, approve=other))

        assert envelope["error"]["code"] == "approval-mismatch"

    def test_an_approval_for_a_different_component_does_not_carry_over(self, tmp_path, capsys):
        """The component reaches both the title and the body, so it is inside the
        approved bytes — approving one surface's report never approves another's."""
        fake = FakeGitHub()
        project = a_product_repo(tmp_path)
        _payload, other = upstream.render_preview(
            project, title=FILEABLE_TITLE, body=FILEABLE_BODY, component="pr-gate"
        )

        envelope = refuse(project, capsys, fake, send_argv(project, approve=other))

        assert envelope["error"]["code"] == "approval-mismatch"

    def test_always_file_waives_the_digest_match(self, tmp_path, capsys):
        """Standing pre-consent means the human is not asked per report, so there
        is no previewed digest to hand back."""
        fake = FakeGitHub()
        project = a_product_repo(tmp_path, preference="always-file")

        argv = send_argv(project, approve="sha256:whatever")

        assert cli.run(str(project), argv, transport=fake) == 0
        assert json.loads(capsys.readouterr().out)["data"]["created"] is True

    @pytest.mark.parametrize(
        "repo_kwargs,expected",
        [
            ({"identity": UPSTREAM_TRACKER}, "self-file"),
            ({"identity": "acme/widget"}, "auth"),
        ],
        ids=["check-3", "check-5"],
    )
    def test_always_file_waives_check_4_and_nothing_else(
        self, tmp_path, capsys, repo_kwargs, expected
    ):
        """Standing consent is consent to skip the per-report ASK, not consent to
        skip the contract. A waiver that leaked into its neighbours would make
        `always-file` the state in which none of the five holds."""
        fake = FakeGitHub(user={"id": 0} if expected == "auth" else None)
        project = a_product_repo(tmp_path, preference="always-file", **repo_kwargs)

        envelope = refuse(project, capsys, fake, send_argv(project, approve="sha256:whatever"))

        assert envelope["error"]["code"] == expected

    def test_the_send_token_is_required_even_under_always_file(self, tmp_path, capsys):
        """The token is what separates a send from a preview. Waiving its VALUE is
        the standing consent; waiving its presence would make every preview file."""
        fake = FakeGitHub()
        project = a_product_repo(tmp_path, preference="always-file")

        cli.run(
            str(project),
            ["file-upstream", "--title", FILEABLE_TITLE, "--body", FILEABLE_BODY, "--json"],
            transport=fake,
        )
        envelope = json.loads(capsys.readouterr().out)

        assert envelope["data"]["sent"] is False
        assert_filed_nothing(fake)



class TestAnEmptyPayloadNeverFiles:
    """The failure the skill's own third round named and closed only in prose:
    every composed field arrives via `$(cat <path>)`, and a path the reader did
    not hold reads as nothing. Both flags are present, so the presence check
    passes; the title prefix alone clears the length floor; and under standing
    consent nothing compares bytes. The guard has to be in the module that owns
    the bytes, refusing on BOTH arms, or an empty issue lands where it cannot be
    retitled or deleted."""

    @pytest.mark.parametrize("field", ["--title", "--body"])
    def test_the_preview_refuses_an_empty_field_outright(self, tmp_path, capsys, field):
        project = a_product_repo(tmp_path)
        argv = ["file-upstream", "--title", FILEABLE_TITLE, "--body", FILEABLE_BODY, "--json"]
        argv[argv.index(field) + 1] = "   "

        code = cli.run(str(project), argv, transport=MagicMock())
        envelope = json.loads(capsys.readouterr().out)

        assert code != 0
        assert envelope["status"] == "error"
        assert field in envelope["error"]["message"]

    @pytest.mark.parametrize("field", ["--title", "--body"])
    def test_always_file_does_not_waive_it(self, tmp_path, capsys, field):
        """Standing consent waives the digest comparison — the one check that would
        otherwise have noticed the bytes changed between preview and send. It must
        not waive this, and the transport must see no call at all."""
        fake = FakeGitHub()
        project = a_product_repo(tmp_path, preference="always-file")
        argv = send_argv(project, approve="sha256:whatever")
        argv[argv.index(field) + 1] = ""

        # Run directly rather than through `refuse`, whose own "nothing filed"
        # check reads the fake afterwards: the claim here is that the SEND made no
        # transport call at all, which only an untouched call list can show.
        code = cli.run(str(project), argv, transport=fake)
        envelope = json.loads(capsys.readouterr().out)

        assert code != 0
        assert envelope["status"] == "error"
        assert envelope["error"]["retryable"] is False
        assert field in envelope["error"]["message"]
        assert fake.calls == []


class TestFilingIsAuthenticated:
    """§5 check 5. GitHub issues are inherently authenticated; upstream filing is
    never anonymous, and the token is the session's own — the adapter manages none."""

    def test_an_unresolvable_identity_refuses_before_the_write(self, tmp_path, capsys):
        # A user object with no `login`: `gh` answered, and the answer names
        # nobody. Refusing on it is what keeps "never anonymous" a property of
        # this side of the boundary rather than of GitHub's response to a write.
        fake = FakeGitHub(user={"id": 0})
        project = a_product_repo(tmp_path)

        envelope = refuse(project, capsys, fake, send_argv(project))

        assert envelope["error"]["code"] == "auth"

    def test_an_unreachable_provider_files_nothing(self, tmp_path, capsys):
        fake = FakeGitHub()
        fake.set_unreachable(True)
        project = a_product_repo(tmp_path)

        cli.run(str(project), send_argv(project), transport=fake)
        assert json.loads(capsys.readouterr().out)["status"] == "error"

        fake.set_unreachable(False)  # the fake must be readable to be inspected
        assert_filed_nothing(fake)


class TestTheSec5WithholdReachesTheSendArm:
    """The SEC-5 withhold (Security §1b) refuses every GitHub-mutating op under an
    untrusted-triggered Actions run, and `file-upstream` is in that set — including
    its preview arm, which mutates nothing but which nobody could act on there.

    **Why this reads the seam rather than the op table.** What holds the op in
    `cli._WRITE_OPS` is a partition test whose failure text is about the *counts
    cache*: drop `file-upstream` from the set and the "fix" that suite suggests is
    deleting a cache-map row, which re-opens the send arm under a pwn-request
    trigger with the whole suite green. This class fails instead, and says why.

    Note what the withhold is NOT: it is not a human-present check. It fires on an
    untrusted trigger with no authorized actor, and reaches neither
    `PRAWDUCT_UNATTENDED=1` nor a trusted Actions event — see the send arm's honest
    limit in the upstream-filing design §4.3.
    """

    @pytest.fixture(autouse=True)
    def _untrusted_actions(self, monkeypatch):
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request_target")
        monkeypatch.delenv("PRAWDUCT_ACTOR_AUTHORIZED", raising=False)

    def test_the_send_arm_files_nothing_under_an_untrusted_trigger(self, tmp_path, capsys):
        """A fully valid send — all five §5 checks hold, digest genuinely rendered
        — still files nothing, because the withhold refuses before dispatch."""
        fake = FakeGitHub()
        project = a_product_repo(tmp_path)

        code = cli.run(str(project), send_argv(project), transport=fake)

        assert code == 5  # auth exit class
        assert_filed_nothing(fake)

    def test_an_authorized_actor_clears_it(self, tmp_path, capsys, monkeypatch):
        """The withhold is the untrusted-trigger check, not a blanket Actions ban:
        the explicit triggering-actor authorization clears it and the same call
        files. Without this the test above would also pass if the op simply never
        worked in Actions."""
        monkeypatch.setenv("PRAWDUCT_ACTOR_AUTHORIZED", "1")
        fake = FakeGitHub()
        project = a_product_repo(tmp_path)

        assert cli.run(str(project), send_argv(project), transport=fake) == 0
        assert json.loads(capsys.readouterr().out)["data"]["created"] is True


class TestTheOutboundTitleConforms:
    """`data-model.md` § Direction binds the issue standard's §1 title rules on
    every adapter write path, and `file-upstream` is the fourth. It binds harder
    here: the write is irreversible and a non-collaborator filer cannot retitle
    afterwards. The PREVIEW stays advisory — an advisory finding is exactly what
    lets an author fix a title before approving it."""

    def _over_budget(self, project_dir, capsys, transport, *, approve):
        title = "a symptom that runs on and on past every reasonable budget the standard sets"
        argv = ["file-upstream", "--title", title, "--body", FILEABLE_BODY, "--json"]
        if approve:
            _payload, digest = upstream.render_preview(
                project_dir, title=title, body=FILEABLE_BODY, component=""
            )
            argv += ["--approve", digest]
        cli.run(str(project_dir), argv, transport=transport)
        return json.loads(capsys.readouterr().out)

    def test_the_send_arm_refuses_a_non_conforming_title(self, tmp_path, capsys):
        fake = FakeGitHub()
        project = a_product_repo(tmp_path)

        envelope = self._over_budget(project, capsys, fake, approve=True)

        assert envelope["status"] == "error"
        assert envelope["error"]["code"] == "validation"
        assert "title-too-long" in {
            f["rule"] for f in envelope["error"]["details"]["findings"]
        }
        assert_filed_nothing(fake)

    def test_the_preview_arm_reports_the_same_title_and_refuses_nothing(self, tmp_path, capsys):
        project = a_product_repo(tmp_path)

        envelope = self._over_budget(project, capsys, MagicMock(), approve=False)

        assert envelope["status"] == "ok"
        assert "title-too-long" in {f["rule"] for f in envelope["lint"]}


class TestEveryRefusalCarriesTheSameAdvisories:
    """A field that rides the success envelope and vanishes from the failure one
    is this repo's recurring envelope defect, and a refused filing is precisely
    when the author is about to edit the report — so the budget findings are worth
    more on the refusal than on the success."""

    @pytest.mark.parametrize(
        "preference,approve,expected",
        [
            ("never-file", None, "filing-disabled"),
            ("ask-user", "sha256:nope", "approval-mismatch"),
        ],
        ids=["filing-disabled", "approval-mismatch"],
        # `target-not-pinned` is deliberately absent: it refuses before any payload
        # is composed, so there is nothing to lint and the remedy is the `--repo`
        # flag rather than the report. See the note at its call site in `cli.py`.
    )
    def test_a_refusal_reports_the_budget_findings_the_success_would_have(
        self, tmp_path, capsys, preference, approve, expected
    ):
        fake = FakeGitHub()
        project = a_product_repo(tmp_path, preference=preference)
        body = "### Problem\n\n" + " ".join(["word"] * 400)
        argv = ["file-upstream", "--title", FILEABLE_TITLE, "--body", body,
                "--component", FILEABLE_COMPONENT, "--json"]
        _payload, digest = upstream.render_preview(
            project, title=FILEABLE_TITLE, body=body, component=FILEABLE_COMPONENT
        )
        argv += ["--approve", approve or digest]

        cli.run(str(project), argv, transport=fake)
        envelope = json.loads(capsys.readouterr().out)

        assert envelope["error"]["code"] == expected
        assert "body-too-long" in {f["rule"] for f in envelope["lint"]}
        assert_filed_nothing(fake)


class TestNoSurfaceStillDescribesTheAbsence:
    """The norm's other half: the surfaces agree the capability exists.

    Enforcing the contract in code while a governing artifact still says the
    capability is unbuilt is the failure this class exists to catch, and it is
    quiet — nothing breaks, a model reading the artifact simply routes around a
    surface that is right there. It happened once already inside this very work:
    `skills/backlog/SKILL.md` went on saying an adapter-side pin existed "only in
    the design" for two chunks after the pin shipped.

    **Records are exempt, and the distinction is the point.** A dated audit, a
    completed plan, a change-log entry and an archived artifact all describe a
    world that was true when written; correcting them would falsify the record.
    What must track reality is prose a reader consults to learn what the system
    does *now*.
    """

    #: Prose a reader consults for current behaviour. Deliberately not a glob over
    #: the repo: the exemptions below would then be doing the real work, and an
    #: exemption list grows until it means nothing.
    LIVE_SURFACES = (
        "documentation/backlog-service-prd.md",
        "documentation/backlog-service-api-contract.md",
        "documentation/backlog-service-data-model.md",
        "documentation/backlog-service-security-model.md",
        "documentation/backlog-service-upstream-filing.md",
        "documentation/backlog-service-requirements.md",
        ".prawduct/artifacts/security-model.md",
        ".prawduct/artifacts/architecture.md",
        ".prawduct/artifacts/data-model.md",
        ".prawduct/artifacts/project-preferences.md",
        # The two instruction surfaces, and the reason they are named explicitly:
        # SKILL.md is the case in the docstring above — it went on saying the pin
        # existed "only in the design" for two chunks after the pin shipped — and
        # a list that omitted the file it was written about would have passed
        # green while that exact sentence was re-introduced. adapter-mode.md is
        # its sibling: it is the referent SKILL.md points a reader at for the op's
        # contract, so a stale claim there reaches the same reader one hop later.
        "plugin/skills/backlog/SKILL.md",
        "plugin/skills/backlog/adapter-mode.md",
        # The op's only caller. It is on this list for the same reason
        # adapter-mode.md is, one step more directly: it is the surface a model
        # reads when it has an actual prawduct bug in hand, so a sentence here
        # saying the channel is unbuilt routes the report nowhere.
        "plugin/skills/report-bug/SKILL.md",
    )

    #: Phrasings that assert the surface does not exist yet. Matched only on lines
    #: that also name the op, so ordinary uses of "deferred" and "W3" — both of
    #: which describe things that ARE still deferred — do not fire.
    ABSENCE_CLAIMS = (
        "unbuilt",
        "not built",
        "still designed",
        "designed but unbuilt",
        "deferred to w3",
        "stays w3",
        "is w3",
        "only in the design",
        "only in the `file-upstream` design",
        "filesystem-local",
        "zero occurrences",
        "when it lands",
    )

    def test_no_live_surface_says_the_capability_is_unbuilt(self):
        offenders = []
        for rel in self.LIVE_SURFACES:
            path = REPO_ROOT / rel
            assert path.exists(), f"{rel} moved — this guard is only as good as its list"
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                low = line.lower()
                if "file-upstream" not in low and "file upstream" not in low:
                    continue
                # A line that dates itself is a record, not a claim about now.
                if _reads_as_a_record(low):
                    continue
                hit = next((c for c in self.ABSENCE_CLAIMS if c in low), None)
                if hit:
                    offenders.append(f"{rel}:{lineno}: [{hit}] {line.strip()[:140]}")
        assert not offenders, (
            "A live governing surface still describes `file-upstream` as unbuilt or "
            "deferred. The op ships: the five checks are enforced in "
            "lib/backlog/upstream.py and asserted above. Update the surface, or — if "
            "the line is a dated record of what was true then — say so on the line, "
            "which is what makes it a record rather than a stale claim.\n  - "
            + "\n  - ".join(offenders)
        )


#: Markers that make a line self-dating. A record says WHEN it was true; a stale
#: claim just states it. Requiring the year on the line keeps the exemption
#: narrow — "historically" alone would exempt anything that felt like prose.
_RECORD_MARKERS = ("at birth", "birth-time", "amended", "prior form", "the prior")


def _reads_as_a_record(low: str) -> bool:
    import re

    return bool(re.search(r"20\d\d-\d\d-\d\d", low)) and any(
        m in low for m in _RECORD_MARKERS
    )


def test_the_documented_dedup_bound_cites_the_symbol_that_sets_it():
    """The claim and the constant must not drift apart again.

    The commit that BOUNDED the dedup scan left three prose sites still promising
    absolute retry-collapse, because prose that merely describes old behaviour
    shares no token with the code that changed — there was nothing to grep. This
    pins the fix's shape: api-contract §2.4 is the claim's home and names the
    symbol, so renaming or deleting the constant fails here rather than silently
    stranding the sentence.
    """
    contract = (REPO_ROOT / "documentation" / "backlog-service-api-contract.md").read_text(
        encoding="utf-8"
    )

    assert isinstance(upstream.DEDUP_SCAN_PAGES, int) and upstream.DEDUP_SCAN_PAGES > 0
    assert "DEDUP_SCAN_PAGES" in contract, (
        "api-contract §2.4 states the retry-collapse guarantee but no longer cites "
        "the symbol that bounds it, so the next change to the window leaves the "
        "sentence behind — which is exactly how this drifted the first time"
    )


class TestTheDropBoxReplacementIsLive:
    """Design §7's lockstep, from the replacement's side.

    The drop-box is retired **only together with** a live replacement, never
    before it — so the thing that must be mechanically true before anyone
    retires `incoming-bugs/` is that `/prawduct:report-bug` reaches the adapter
    and no longer writes a file. Asserted here rather than left to the retirement
    itself, where "is the replacement live?" would be answered by the same person
    doing the retiring, from memory.

    **What is pinned here is mechanical; the rest is not.** Everything else this skill owes — that the
    report carries no product content, that a human actually read the bytes,
    that a blocked filing captures nothing locally — is judgment about prose, and
    a grep for it would pass on any text containing the right words. Those are
    the Critic's (Goal 4), deliberately: a green test that cannot catch a real
    violation is worse than no test.
    """

    SKILL = REPO_ROOT / "plugin/skills/report-bug/SKILL.md"

    def test_the_skill_drives_both_arms_of_the_op(self):
        """A skill describing the preview and not the send is a half-rewrite —
        and it fails in the quiet direction, composing a payload nobody files."""
        text = self.SKILL.read_text(encoding="utf-8")

        for token in ("file-upstream", "--approve"):
            assert token in text, (
                f"`/prawduct:report-bug` no longer names `{token}` — it is the only caller of "
                "the upstream filing op, and a report that never reaches the send arm is a "
                "report nobody receives"
            )

    #: How to make each non-previewable refusal produce its code, so the CODES in
    #: the assertion below come out of the adapter rather than out of memory. The
    #: names are derived from `send`; only the inputs are written here, and a
    #: refusal `send` gains that is missing from this map fails loudly rather than
    #: being skipped — an unknown name is unbacked by default, which is the same
    #: rule `IMPLEMENTED_ADAPTER_GUARDS` follows one file over.
    #:
    #: `check_payload_inputs` is deliberately absent: it rejects malformed FLAGS
    #: before a payload exists, and the skill has nothing to branch on there — the
    #: CLI's message names the flag.
    REFUSAL_PROBES = {
        "check_target": lambda: upstream.check_target("someone/else"),
        "check_approval": lambda: upstream.check_approval(
            "sha256:not-the-digest", "sha256:the-digest", preference=upstream.PREF_ASK_USER
        ),
        "check_authenticated": lambda: upstream.check_authenticated(None),
    }

    def test_the_skill_names_every_refusal_the_preview_cannot_predict(self):
        """The skill keeps a copy of the codes, and this is what keeps it honest.

        It is a justified copy — a model needs the codes to branch on an outcome
        — but a copy with nothing pinning it goes stale silently: a seventh
        refusal added to `send` would leave the skill's list incomplete, and the
        first reader to learn that is an operator staring at a code the
        instructions do not mention, on the one surface where the write is
        foreign and irreversible.

        Only the NON-predictable ones are required. The rest reach the operator
        as `filing would refuse (…)` on the preview, which the skill does tell
        the model to read and act on.
        """
        import ast
        import inspect
        import textwrap

        def called_in(fn):
            # CALLS, not mentions. `previewable_refusals`' docstring names every
            # refusal it deliberately excludes, so a substring search over its
            # source reports the whole set as predicted and this derivation
            # silently finds nothing to check.
            return {
                node.func.id
                for node in ast.walk(
                    ast.parse(textwrap.dedent(inspect.getsource(fn)))
                )
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            }

        refusals = {n for n in called_in(upstream.send) if n.startswith("check_")}
        assert refusals, "no refusal-shaped call found in `send` — the derivation broke"

        predicted = called_in(upstream.previewable_refusals)
        unpredictable = sorted(
            n for n in refusals
            if n not in predicted and n != "check_payload_inputs"
        )
        assert unpredictable, "every refusal is predictable — this derivation broke"

        text = self.SKILL.read_text(encoding="utf-8")
        for name in unpredictable:
            probe = self.REFUSAL_PROBES.get(name)
            assert probe is not None, (
                f"`send` refuses via {name}() and REFUSAL_PROBES does not know how to make "
                "it fire, so its code cannot be checked against the skill. Add a probe (or "
                "say why the skill need not name it) — an unknown refusal is unbacked here "
                "by default, on purpose"
            )
            code = probe().code
            assert f"`{code}`" in text, (
                f"`{code}` is a refusal the preview cannot predict, so the operator meets it "
                "for the first time at send — and `/prawduct:report-bug` does not name it. "
                "Give the skill a line saying what that code means and what to do about it"
            )

    def test_no_command_block_passes_a_composed_field_as_a_shell_literal(self):
        """Every composed field the skill shows must be read from a file.

        Inside double quotes bash still runs `` `…` `` and expands `$…`, and this
        skill instructs these fields be written in prawduct's own backticked
        vocabulary — so `` `prawduct-hook version` `` executes and a symptom
        naming `$CLAUDE_SKILL_DIR` expands to nothing. The result is composed,
        digested, approved and filed with the defect's own name deleted from it,
        into a repo where a non-collaborator cannot retitle it. Under standing
        consent the digest comparison is waived, so the mangling is not even
        caught by an `approval-mismatch`.

        **`--body` is in the class for a reason worth stating**, because the
        obvious argument excludes it: the digest does not protect it. Both calls
        expand identically, so a mangled body previews and sends as the same
        bytes, the digests agree, and the check passes on content nobody wrote.
        The trailing space in each match is load-bearing — it is what separates a
        flag being *passed* from one being *named* in prose.

        Asserted over EVERY line rather than the one that was wrong: the skill
        shows the command twice, the first fix landed on one block, and the round
        that found it had to come back for the other. Command-substitution output
        is not re-expanded, which is why `$(cat …)` is the shape required.
        """
        offenders = [
            f"{n}: {line.strip()}"
            for n, line in enumerate(self.SKILL.read_text(encoding="utf-8").splitlines(), 1)
            if any(f"--{f} " in line for f in ("title", "component", "body"))
            and "$(cat" not in line
        ]

        assert not offenders, (
            "a command block passes a composed field as a shell literal — bash "
            "expands backticks and `$` inside double quotes, and this skill tells the model "
            "to write these fields in backticked prawduct vocabulary:\n  - "
            + "\n  - ".join(offenders)
        )

    def test_no_command_block_reads_a_field_through_a_cross_call_shell_variable(self):
        """The scratch path must be one the reader holds, not one a variable carries.

        A round fixing the undefined `<scratch>` placeholder replaced it with
        `SCRATCH="$(mktemp -d)"`, which reads as working code and is not: the
        Bash tool does not persist env vars between calls, and preview and send
        are necessarily separate ones. By the send `$SCRATCH` is empty and every
        `$(cat …)` reads nothing. `check_payload_inputs` now refuses an empty
        title or body on both arms (`TestAnEmptyPayloadNeverFiles`), so the
        variable form costs a wasted round rather than an empty issue — this pin
        is what makes the round not happen.

        The sibling above pins that the fields arrive via `$(cat …)`; it is
        satisfied by a `$(cat …)` reading a path that does not exist. This pins
        the other half. Asserted over every line for the same reason: the skill
        shows the command twice and a one-block fix has already been shipped once.
        """
        offenders = [
            f"{n}: {line.strip()}"
            for n, line in enumerate(self.SKILL.read_text(encoding="utf-8").splitlines(), 1)
            if any(f"--{f} " in line for f in ("title", "component", "body"))
            and "$(cat" in line
            and "$" in line.split("$(cat", 1)[1]
        ]

        assert not offenders, (
            "a command block reads a composed field through a shell variable. Variables do "
            "not survive between tool calls, so the send reads an empty path and files an "
            "empty issue irreversibly. Name a path the reader pasted:\n  - "
            + "\n  - ".join(offenders)
        )

    def test_the_skill_names_no_drop_box_at_all(self):
        """Was "the write, not the mention" while the drop-box still held
        untriaged reports and the receiving-side section had to say so. The
        channel is retired, so there is no mention left to carve out and the ban
        is total: a directory nothing writes and nothing counts, named in the one
        skill a model reads to decide where a report goes, is an instruction to
        put one somewhere it will not be found."""
        text = self.SKILL.read_text(encoding="utf-8")

        for token in ("bug-inbox", "<inbox>/", "incoming-bugs"):
            assert token not in text, (
                f"`/prawduct:report-bug` still names `{token}`. Upstream reports are "
                "filed as GitHub issues; the local drop-box is retired, and naming it "
                "here routes a report into a directory with no channel behind it"
            )
