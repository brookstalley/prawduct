"""Tests for lib/backlog/core.py link / unlink (Chunk 03, L1).

DM3 typed edges — ``blocks``/``blocked-by`` (native dependencies, so blockers are
queryable by ``pick``), ``parent``/``child`` (native sub-issues), and ``related``
(no native GitHub edge → a block-authoritative ``related:`` list). Idempotent
set/clear; self-links and unknown edges are rejected.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from lib.backlog import cli, core, encode, ids  # noqa: E402
from fakes.fake_github import FakeGitHub  # noqa: E402

OWNER, REPO = "octo", "repo"


@pytest.fixture
def fake():
    return FakeGitHub(user={"login": "agent-a", "id": 1})


def _file(fake, *, title="t", owner=OWNER, repo=REPO):
    result = core.file_item(fake, owner=owner, repo=repo, title=title, body="b")
    assert result["status"] == "ok", result
    return result["data"]["id"]


def _num(id_raw):
    return int(id_raw.split("#")[1])


class TestLinkByPfxAlias:
    """BKL-4W7H: either endpoint may be a hand-minted PFX alias, resolved via its
    id:PFX label against --repo — the same read-resolution ``get`` uses."""

    def _seed_alias(self, fake, pfx):
        label = ids.alias_label(pfx)
        fake.seed_labels(OWNER, REPO, [label])
        return fake.create_issue(OWNER, REPO, title="t", body="b", labels=[label])["number"]

    def test_pfx_endpoint_resolves_to_its_issue(self, fake):
        src = self._seed_alias(fake, "BKL-SRC1")
        tgt = _file(fake, title="blocker")
        result = core.link(
            fake, id_raw="BKL-SRC1", edge="blocked-by", target_raw=tgt,
            default_repo=(OWNER, REPO),
        )
        assert result["status"] == "ok", result
        assert result["data"]["item"] == f"{OWNER}/{REPO}#{src}"
        assert [x["ref"] for x in fake.list_blocked_by(OWNER, REPO, src)] == [tgt]

    def test_pfx_endpoint_without_a_repo_is_validation(self, fake):
        self._seed_alias(fake, "BKL-SRC1")
        tgt = _file(fake, title="blocker")
        result = core.link(fake, id_raw="BKL-SRC1", edge="related", target_raw=tgt)
        assert result["status"] == "error"
        assert result["error"]["code"] == "validation"


class TestBlockedBy:
    def test_link_blocked_by_registers_native_dependency(self, fake):
        a = _file(fake, title="a")
        b = _file(fake, title="blocker")
        result = core.link(fake, id_raw=a, edge="blocked-by", target_raw=b)
        assert result["status"] == "ok"
        assert result["data"] == {"item": a, "edge": "blocked-by", "target": b, "linked": True}
        blockers = fake.list_blocked_by(OWNER, REPO, _num(a))
        assert [x["ref"] for x in blockers] == [b]

    def test_blocks_is_the_inverse_of_blocked_by(self, fake):
        a = _file(fake, title="a")
        b = _file(fake, title="b")
        # "a blocks b" ⇔ "b is blocked-by a"
        core.link(fake, id_raw=a, edge="blocks", target_raw=b)
        assert [x["ref"] for x in fake.list_blocked_by(OWNER, REPO, _num(b))] == [a]
        assert fake.list_blocked_by(OWNER, REPO, _num(a)) == []

    def test_unlink_removes_dependency_idempotently(self, fake):
        a = _file(fake, title="a")
        b = _file(fake, title="b")
        core.link(fake, id_raw=a, edge="blocked-by", target_raw=b)
        core.unlink(fake, id_raw=a, edge="blocked-by", target_raw=b)
        assert fake.list_blocked_by(OWNER, REPO, _num(a)) == []
        # unlinking again is a no-op (idempotent), not an error
        again = core.unlink(fake, id_raw=a, edge="blocked-by", target_raw=b)
        assert again["status"] == "ok"

    def test_link_is_idempotent(self, fake):
        a = _file(fake, title="a")
        b = _file(fake, title="b")
        core.link(fake, id_raw=a, edge="blocked-by", target_raw=b)
        core.link(fake, id_raw=a, edge="blocked-by", target_raw=b)
        assert len(fake.list_blocked_by(OWNER, REPO, _num(a))) == 1


class TestSubIssues:
    def test_parent_makes_this_a_sub_issue_of_target(self, fake):
        child = _file(fake, title="child")
        parent = _file(fake, title="parent")
        core.link(fake, id_raw=child, edge="parent", target_raw=parent)
        # target is the parent → child registered under parent
        assert (OWNER, REPO, _num(child)) in fake._repo(OWNER, REPO).sub_issues[_num(parent)]

    def test_child_registers_target_under_this(self, fake):
        parent = _file(fake, title="parent")
        child = _file(fake, title="child")
        core.link(fake, id_raw=parent, edge="child", target_raw=child)
        assert (OWNER, REPO, _num(child)) in fake._repo(OWNER, REPO).sub_issues[_num(parent)]

    def test_unlink_child_removes_sub_issue(self, fake):
        parent = _file(fake, title="parent")
        child = _file(fake, title="child")
        core.link(fake, id_raw=parent, edge="child", target_raw=child)
        core.unlink(fake, id_raw=parent, edge="child", target_raw=child)
        assert fake._repo(OWNER, REPO).sub_issues[_num(parent)] == set()


class TestRelated:
    def test_related_stored_in_block_list(self, fake):
        a = _file(fake, title="a")
        b = _file(fake, title="b")
        core.link(fake, id_raw=a, edge="related", target_raw=b)
        issue = fake.get_issue(OWNER, REPO, _num(a))
        block = encode.parse_block(issue["body"])
        assert encode.parse_list(block.get("related")) == [b]

    def test_related_unlink_removes_from_list(self, fake):
        a = _file(fake, title="a")
        b = _file(fake, title="b")
        c = _file(fake, title="c")
        core.link(fake, id_raw=a, edge="related", target_raw=b)
        core.link(fake, id_raw=a, edge="related", target_raw=c)
        core.unlink(fake, id_raw=a, edge="related", target_raw=b)
        issue = fake.get_issue(OWNER, REPO, _num(a))
        block = encode.parse_block(issue["body"])
        assert encode.parse_list(block.get("related")) == [c]

    def test_related_preserves_the_prawduct_block(self, fake):
        a = _file(fake, title="a")
        b = _file(fake, title="b")
        core.link(fake, id_raw=a, edge="related", target_raw=b)
        issue = fake.get_issue(OWNER, REPO, _num(a))
        # The block still parses and keeps v:1 (the related list rode alongside it).
        block = encode.parse_block(issue["body"])
        assert block.version() == 1


class TestLinkValidation:
    def test_self_link_rejected(self, fake):
        a = _file(fake, title="a")
        result = core.link(fake, id_raw=a, edge="related", target_raw=a)
        assert result["status"] == "error" and result["error"]["code"] == "validation"

    def test_unknown_edge_rejected(self, fake):
        a = _file(fake, title="a")
        b = _file(fake, title="b")
        result = core.link(fake, id_raw=a, edge="sideways", target_raw=b)
        assert result["status"] == "error" and result["error"]["code"] == "validation"

    def test_bad_target_id_rejected(self, fake):
        a = _file(fake, title="a")
        result = core.link(fake, id_raw=a, edge="related", target_raw="not-an-id")
        assert result["status"] == "error" and result["error"]["code"] == "validation"


class TestLinkCli:
    def test_link_and_unlink_through_cli(self, fake, capsys):
        import json

        a = _file(fake, title="a")
        b = _file(fake, title="b")
        code = cli.run(None, ["link", a, "--edge", "blocked-by", "--to", b, "--json"], transport=fake)
        env = json.loads(capsys.readouterr().out)
        assert code == 0 and env["data"]["linked"] is True

        code = cli.run(None, ["unlink", a, "--edge", "blocked-by", "--to", b, "--json"], transport=fake)
        env = json.loads(capsys.readouterr().out)
        assert code == 0 and env["data"]["linked"] is False

    def test_link_missing_edge_is_validation_error(self, fake, capsys):
        import json

        a = _file(fake, title="a")
        b = _file(fake, title="b")
        code = cli.run(None, ["link", a, "--to", b, "--json"], transport=fake)
        env = json.loads(capsys.readouterr().out)
        assert code == 2 and env["error"]["code"] == "validation"
