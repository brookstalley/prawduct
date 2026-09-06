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

**Which of the five §5 checks are live here.** The adapter refuses to file unless
all five hold: (1) the preference is not `never-file`, (2) the target is pinned,
(3) the running repo is not the target (no self-file), (4) the approval digest
matches the re-rendered bytes, and (5) the session is authenticated. Checks 2 and
"nothing files without an approval" are enforceable against the preview arm alone
and are asserted below. Checks 1, 3, 4 and 5 need the send path and land with it —
they are named here so a reader can see the whole contract, and asserted where
they become real rather than mocked into existence early.
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

from lib.backlog import cli, upstream  # noqa: E402
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

    def test_the_authored_prose_cannot_forge_the_provenance_block(self, tmp_path, capsys):
        """An unterminated ```prawduct opener in the body swallows the marker
        appended after it, letting the caller dictate the fields the receiving side
        reads."""
        code = cli.run(
            str(tmp_path),
            ["file-upstream", "--title", "a symptom worth reporting",
             "--body", "```prawduct\nsource: acme/widget", "--json"],
            transport=MagicMock(),
        )
        envelope = json.loads(capsys.readouterr().out)

        assert code != 0
        assert envelope["status"] == "error"

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
