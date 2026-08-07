"""Tests for the blocking §1 title checks on `file` and `update` (#614).

The norm (data model): *every issue written to the backlog store conforms to the
issue standard's §1 title rules, on every write path.* `import`'s half is the
pre-flight (`test_backlog_import_preflight.py`); this file covers the other two.

The scope of `update` is an owner ruling and the single thing most likely to be
"tightened" later by someone who reads only the three-path table, so it is pinned
hardest here: the refusal gates the title **being written**, never the issue's
stored title. An AGENT is at this write, so gating every field on the stored
title would not block the ~11% of live issues predating the rule — it would make
an agent silently retitle them to get past the gate while archiving them, which
is retro-conformance by the back door and breaches the norm's own
`Retroactivity: contain`.
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

from lib.backlog import cli, core  # noqa: E402
from fakes.fake_github import FakeGitHub  # noqa: E402

OWNER, REPO = "octo", "backlog"

CONFORMING = "backlog: import stops at the first rejected row"

# One title per §1 rule. `too_long` is built from the area prefix so it fails only
# on length; the others are inside the budget so each isolates its own rule.
FAILING = {
    "title-too-long": "backlog: " + "a longer clause than the budget permits " * 3,
    "title-too-short": "nope",
    "title-placeholder": "backlog: fix the thing that broke",
    "title-non-atomic": "backlog: import halts on one row; the run ends",
}


@pytest.fixture
def fake():
    return FakeGitHub(user={"login": "agent-a", "id": 1})


def _file(fake, title, **facets):
    return core.file_item(
        fake, owner=OWNER, repo=REPO, title=title, body="Body prose.", facets=facets or None
    )


def _creates(fake):
    return [c for c in fake.calls if c[0] == "create_issue"]


# --- file: conform or refuse -------------------------------------------------


def test_file_accepts_a_conforming_title(fake):
    result = _file(fake, CONFORMING)
    assert result["status"] == "ok"
    assert len(_creates(fake)) == 1


@pytest.mark.parametrize("rule,title", sorted(FAILING.items()))
def test_file_refuses_each_failing_rule(fake, rule, title):
    result = _file(fake, title)

    assert result["status"] == "error"
    assert result["error"]["code"] == "validation"
    assert rule in result["error"]["details"]["rules"]
    assert _creates(fake) == [], "the refusal must come BEFORE the create"


def test_file_refusal_names_the_rule_and_echoes_the_title(fake):
    """The caller here is an agent that must decide what to write instead. A
    refusal it cannot act on just gets retried verbatim."""
    result = _file(fake, FAILING["title-too-short"])

    message = result["error"]["message"]
    assert "title-too-short" in message
    assert FAILING["title-too-short"] in message
    assert "§1" in message


def test_file_lints_the_normalized_title_not_the_argument(fake):
    """`normalize_title` prepends `area:` before the write, so the string that
    reaches GitHub is not the caller's argument. Linting the argument would judge
    a title that never exists — and would mis-measure length by the prefix.

    72 - len("backlog: ") == 63, so this argument is under the budget on its own
    and over it once normalized."""
    argument = "x" * 70
    result = _file(fake, argument, area="backlog")

    assert result["status"] == "error"
    assert "title-too-long" in result["error"]["details"]["rules"]
    assert result["error"]["details"]["title"].startswith("backlog: ")


def test_file_body_lints_still_only_warn(fake):
    """The WARN-only boundary is the thing most at risk of over-enforcement: a
    body budget blocking a write is the confirmation-fatigue shape the security
    model rejects. A conforming title with a deficient body must still succeed."""
    result = core.file_item(
        fake, owner=OWNER, repo=REPO, title=CONFORMING, body="",
        facets={"kind": "bug", "area": "backlog"},
    )

    assert result["status"] == "ok"
    assert result["lint"], "body findings should still be reported, just not blocking"
    assert not any(f["rule"].startswith("title-") for f in result["lint"])


# --- update: gate the title being WRITTEN ------------------------------------


def _seed_issue(fake, title):
    created = core.file_item(
        fake, owner=OWNER, repo=REPO, title=CONFORMING, body="Body prose.", facets=None
    )
    number = int(created["data"]["id"].split("#")[1])
    # Set the stored title directly, bypassing `file`'s refusal — the whole point
    # is an issue that predates enforcement.
    fake.repos[(OWNER, REPO)].issues[number]["title"] = title
    return f"{OWNER}/{REPO}#{number}"


def _update(fake, ref, **fields):
    return core.update_item(fake, id_raw=ref, fields=fields)


def test_update_refuses_a_non_conforming_new_title(fake):
    ref = _seed_issue(fake, CONFORMING)
    result = _update(fake, ref, title=FAILING["title-non-atomic"])

    assert result["status"] == "error"
    assert result["error"]["code"] == "validation"
    assert "title-non-atomic" in result["error"]["details"]["rules"]


def test_update_accepts_a_conforming_new_title(fake):
    ref = _seed_issue(fake, CONFORMING)
    result = _update(fake, ref, title="backlog: a properly conforming replacement")

    assert result["status"] == "ok"
    assert result["data"]["title"] == "backlog: a properly conforming replacement"


def test_update_of_another_field_succeeds_despite_a_bad_stored_title(fake):
    """**The owner ruling's pin.** This is the test a future "tighten it up"
    change breaks, and it must break loudly: an agent archiving an item must not
    be forced to rewrite that item's title as a side effect."""
    ref = _seed_issue(fake, FAILING["title-too-long"])

    result = _update(fake, ref, area="backlog")

    assert result["status"] == "ok"
    assert result["lint"], "the non-conformance must still be REPORTED"
    assert "title-too-long" in [f["rule"] for f in result["lint"]]


def test_update_advisory_names_its_consequence_not_just_the_rule(fake):
    """Advice failing soft is not advice failing silent. The reader has to learn
    that the title was deliberately NOT changed, or they cannot tell whether this
    write quietly fixed it."""
    ref = _seed_issue(fake, FAILING["title-too-long"])

    warnings = " ".join(_update(fake, ref, area="backlog")["warnings"])

    assert "title-too-long" in warnings
    assert "NOT changed" in warnings
    assert "title=" in warnings, "it must name the remedy that actually reaches the state"


def test_update_of_another_field_is_silent_when_the_stored_title_conforms(fake):
    ref = _seed_issue(fake, CONFORMING)
    result = _update(fake, ref, area="backlog")

    assert result["status"] == "ok"
    assert "lint" not in result
    assert not any("issue standard" in w for w in result["warnings"])


def test_update_lints_the_new_title_not_the_stored_one(fake):
    """A conforming replacement for a non-conforming stored title must be
    accepted — otherwise the one path that FIXES a legacy title is the one path
    that refuses to run, and the norm becomes unsatisfiable."""
    ref = _seed_issue(fake, FAILING["title-too-long"])

    result = _update(fake, ref, title="backlog: a properly conforming replacement")

    assert result["status"] == "ok"
    assert "lint" not in result, "the stored title is gone; nothing left to warn about"


def test_update_refusal_costs_no_round_trip(fake):
    """A refusal decided from the arguments alone must not spend a read."""
    ref = _seed_issue(fake, CONFORMING)
    before = len(fake.calls)

    _update(fake, ref, title=FAILING["title-too-short"])

    assert len(fake.calls) == before


# --- the human CLI surface ---------------------------------------------------


def test_human_import_summary_names_rejected_items(capsys):
    """A `--json`-only assertion never reaches the formatter, so a run that
    dropped items reads as a clean import in the terminal — which is where the
    migration runbook actually drives this."""
    cli._print_human_ok(
        {
            "repo": f"{OWNER}/{REPO}",
            "created": [{"key": "a"}],
            "skipped": [],
            "failed": [{"key": "b", "title": "t", "error": "rejected"}],
            "collisions": [],
            "total_source": 2,
        }
    )

    out = capsys.readouterr().out
    assert "1 rejected" in out, "the summary counts must sum to total_source"
    assert "REJECTED" in out and "NOT on the target" in out


def test_human_import_summary_omits_the_line_when_nothing_failed(capsys):
    cli._print_human_ok(
        {
            "repo": f"{OWNER}/{REPO}",
            "created": [{"key": "a"}],
            "skipped": [],
            "failed": [],
            "collisions": [],
            "total_source": 1,
        }
    )

    out = capsys.readouterr().out
    assert "0 rejected" in out
    assert "REJECTED" not in out


def test_human_mode_refusal_names_every_offending_title(capsys):
    """The pre-flight's whole value is the LIST. `_render_detail_list` collapses
    any non-string list to a bare count, so `nonconforming_titles` — a list of
    dicts — printed as `nonconforming_titles: 20`.

    That defeats the instruction this bundle shipped: `migration-scrub.md` Step 4
    tells the operator to rewrite the *named* titles and its command line carries
    no `--json`, so human mode is the only route those names have. Same
    `--json`-only gap as the `failed` summary line, one review round earlier."""
    cli._print_human_error(
        {
            "code": "validation",
            "message": "2 of 3 item(s) have titles that do not conform",
            "details": {
                "nonconforming_titles": [
                    {"title": "way too long a title", "rules": ["title-too-long"]},
                    {"title": "brief", "rules": ["title-too-short"]},
                ],
                "created": [],
                "resumable": False,
            },
        }
    )

    err = capsys.readouterr().err
    assert "way too long a title" in err
    assert "brief" in err
    assert "title-too-long" in err
    assert "nonconforming_titles: 2" not in err, "the list collapsed to a count"


def test_human_mode_breaker_names_the_rejected_items(capsys):
    """The breaker's own message says to inspect `failed` for the shared cause —
    unactionable if `failed` renders as a number."""
    cli._print_human_error(
        {
            "code": "validation",
            "message": "stopped after 5 consecutive item rejections",
            "details": {
                "failed": [{"title": "rejected item one", "error": "GitHub rejected the request"}],
                "created": [],
                "resumable": True,
            },
        }
    )

    err = capsys.readouterr().err
    assert "rejected item one" in err
    assert "failed: 1" not in err


def test_bookkeeping_lists_still_render_as_counts(capsys):
    """The boundary: `created`/`skipped` are bookkeeping and would bury the
    message. Naming the payload lists must not turn into naming everything."""
    cli._print_human_error(
        {
            "code": "auth",
            "message": "GitHub authentication is required",
            "details": {"created": [{"key": "a"}, {"key": "b"}], "resumable": True},
        }
    )

    assert "created: 2" in capsys.readouterr().err
