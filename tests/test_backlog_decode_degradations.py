"""#745 — decode degradations that used to return a confident value silently.

Two legs are pinned here (the third, a deleted soft facet, needs an evidence
source the issue does not settle and is deliberately not built):

* **ENC-5(c)** — a scoped, open item with no ``stage:`` label reads as stageless
  with a warning, instead of passing as a legitimately stageless item.
* **Zero blocks** — a scoped item whose ``prawduct:`` block is gone decodes to
  all-defaults *with a warning*, instead of returning fully-populated defaults
  that read as a real answer.

Neither changes a returned value: the loss becomes visible, decode does not start
guessing. Controls pin what must NOT warn, so the warnings stay a signal rather
than noise on every ordinary issue.

All offline: no ``gh``, no network.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent / "plugin"
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from lib.backlog import core, encode  # noqa: E402
from fakes.fake_github import FakeGitHub  # noqa: E402

OWNER, REPO = "octo", "repo"

BLOCK = "```prawduct\nv: 1\n```"


def _issue(*, labels=(), body="Why this matters.\n\n" + BLOCK, state="open", state_reason=None):
    return {
        "number": 7,
        "title": "decode: the item under test",
        "body": body,
        "state": state,
        "state_reason": state_reason,
        "labels": [{"name": name} for name in labels],
    }


def _stage_warnings(warnings):
    return [w for w in warnings if "stage" in w]


def _block_warnings(warnings):
    return [w for w in warnings if "no `prawduct:` block" in w]


class TestMissingStage:
    def test_an_open_item_without_a_stage_label_warns(self):
        item, warnings = encode.decode_item(_issue(labels=["area:backlog"]), canonical_id="o/r#7")
        assert item["stage"] is None, "the returned value must not change"
        assert len(_stage_warnings(warnings)) == 1, warnings
        # It names the ambiguity it cannot resolve rather than claiming a deletion.
        assert "never staged" in _stage_warnings(warnings)[0]
        assert "removed" in _stage_warnings(warnings)[0]

    def test_an_open_item_with_a_stage_does_not_warn(self):
        _item, warnings = encode.decode_item(_issue(labels=["stage:ready"]), canonical_id="o/r#7")
        assert _stage_warnings(warnings) == []

    def test_a_closed_item_without_a_stage_does_not_warn(self):
        """Control: a finished item has no stage to have lost."""
        _item, warnings = encode.decode_item(
            _issue(labels=["area:backlog"], state="closed", state_reason="completed"),
            canonical_id="o/r#7",
        )
        assert _stage_warnings(warnings) == []

    def test_a_plain_repo_issue_does_not_warn(self):
        """Control: no namespaced label and no block means it is not an item, and
        an ordinary GitHub issue is not damaged for lacking a stage."""
        _item, warnings = encode.decode_item(_issue(labels=["bug"], body="just a bug"))
        assert warnings == []

    def test_a_block_only_item_without_a_stage_warns(self):
        """An intake filing (block, no labels) is in scope and has no stage."""
        _item, warnings = encode.decode_item(_issue(labels=[]), canonical_id="o/r#7")
        assert len(_stage_warnings(warnings)) == 1


class TestZeroBlocks:
    def test_a_scoped_item_with_no_block_warns(self):
        item, warnings = encode.decode_item(
            _issue(labels=["stage:ready"], body="Why this matters, but the block is gone."),
            canonical_id="o/r#7",
        )
        assert len(_block_warnings(warnings)) == 1, warnings
        assert item["block_version"] == encode.parse_block(None).version(), (
            "the returned value must not change"
        )

    def test_a_none_body_counts_as_no_block(self):
        _item, warnings = encode.decode_item(_issue(labels=["stage:ready"], body=None))
        assert len(_block_warnings(warnings)) == 1

    def test_an_item_with_a_block_does_not_warn(self):
        _item, warnings = encode.decode_item(_issue(labels=["stage:ready"]), canonical_id="o/r#7")
        assert _block_warnings(warnings) == []

    def test_a_plain_repo_issue_does_not_warn(self):
        _item, warnings = encode.decode_item(_issue(labels=[], body="just a bug"))
        assert warnings == []

    def test_a_pull_request_is_not_an_item_and_does_not_warn(self):
        issue = _issue(labels=["stage:ready"], body="x")
        issue["pull_request"] = {"url": "https://example.test/pr/7"}
        _item, warnings = encode.decode_item(issue)
        assert warnings == []


class TestSurfacesOnTheEnvelope:
    """The decode warning must reach what a caller reads, not stop at `encode`."""

    @pytest.fixture
    def fake(self):
        return FakeGitHub(user={"login": "agent-a", "id": 1})

    def _seed(self, fake, *, labels, body):
        fake.seed_labels(OWNER, REPO, list(labels))
        return fake.create_issue(
            OWNER, REPO, title="decode: the item under test", body=body, labels=list(labels)
        )["number"]

    def test_get_reports_a_destroyed_block(self, fake):
        n = self._seed(fake, labels=["stage:ready"], body="prose only, the block was deleted")
        result = core.get_item(fake, id_raw=f"{OWNER}/{REPO}#{n}")
        assert result["status"] == "ok", result
        assert len(_block_warnings(result["warnings"])) == 1, result["warnings"]

    def test_get_reports_a_removed_stage(self, fake):
        n = self._seed(fake, labels=["area:backlog"], body="Why.\n\n" + BLOCK)
        result = core.get_item(fake, id_raw=f"{OWNER}/{REPO}#{n}")
        assert result["status"] == "ok", result
        assert len(_stage_warnings(result["warnings"])) == 1, result["warnings"]

    def test_get_of_a_healthy_item_carries_neither(self, fake):
        n = self._seed(fake, labels=["stage:ready"], body="Why.\n\n" + BLOCK)
        result = core.get_item(fake, id_raw=f"{OWNER}/{REPO}#{n}")
        assert result["warnings"] == []


class TestFilingIsNotReportedBackToTheFiler:
    def test_filing_a_stageless_item_carries_no_stage_warning(self):
        """The filer chose to omit `--stage`; echoing it back as a loss would put a
        warning on every deliberately stageless filing."""
        fake = FakeGitHub(user={"login": "agent-a", "id": 1})
        result = core.file_item(
            fake, owner=OWNER, repo=REPO, title="core: a conforming title for the lint channel", body="b"
        )
        assert result["status"] == "ok", result
        assert result["warnings"] == []
        # ...while the same item read back later IS reported (the control).
        later = core.get_item(fake, id_raw=result["data"]["id"])
        assert len(_stage_warnings(later["warnings"])) == 1
