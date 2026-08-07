"""Tests for the import path's two guardrails (#612) — pre-flight title
validation and per-item failure isolation.

The defect both halves answer: the import loop wrote before it validated and
treated a per-item 422 as fatal for the whole run, so discodon's 396-item
migration created 27 issues, took a 422 at item 28, and ended. The failure was
deterministic and position-ordered, so no amount of resuming advanced it.

Two properties are asserted throughout, because they are the ones that actually
bit:

- **Zero writes on refusal.** A pre-flight that refuses *after* writing is not a
  pre-flight. Every refusal test asserts the transport recorded no create.
- **The offender list is a SET.** Asserting "the report mentions item X" passes
  against an empty list. Every list assertion checks non-emptiness AND membership
  AND the count, so a green test cannot mean "nothing was looked at".
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

from lib.backlog import migrate  # noqa: E402
from lib.backlog.transport import TransportError  # noqa: E402
from fakes.fake_github import FakeGitHub  # noqa: E402

OWNER, REPO = "octo", "backlog"

# A title that satisfies all four §1 checks: inside the 15..72 budget, an
# `area: summary` shape, no placeholder token, no em-dash/semicolon join.
CONFORMING = "backlog: import stops at the first rejected row"


@pytest.fixture
def fake():
    return FakeGitHub(user={"login": "agent-a", "id": 1})


def _record(title: str, *, pfx: str | None = None, labels: list[str] | None = None):
    return migrate.ImportRecord(
        pfx=pfx,
        title=title,
        body="Body prose that is long enough to be unremarkable.",
        status="open",
        labels=list(labels or []),
        block={"v": "1"},
    )


def _seed(fake, records):
    """Pre-create every label the import needs, so a create can only fail for the
    reason a test is actually injecting."""
    names: set[str] = set()
    for record in records:
        names.update(record.labels)
        names.add(record.key_label())
    fake.seed_labels(OWNER, REPO, sorted(names))


def _creates(fake) -> list:
    return [c for c in fake.calls if c[0] == "create_issue"]


def _fail_creates(monkeypatch, fake, faults: dict[int, str]) -> dict:
    """Make the n-th (0-based) create raise ``faults[n]``, others succeed. Returns
    a counter dict whose ``n`` is the number of creates ATTEMPTED.

    Two reasons this exists rather than the fake's `fail_at_mutation`. It arms ONE
    code over a contiguous run, so it cannot express alternating failures or a
    rejection followed by a differently-coded cut. And `fake.calls` records only
    creates that SUCCEEDED — the fault check runs before the append — so it cannot
    answer "was the third record ever attempted?", which is exactly the question
    that separates cutting from continuing."""
    real_create = fake.create_issue
    seen = {"n": 0}

    def patched(*args, **kwargs):
        index = seen["n"]
        seen["n"] += 1
        code = faults.get(index)
        if code is not None:
            raise TransportError(code, f"injected {code} on create {index}")
        return real_create(*args, **kwargs)

    monkeypatch.setattr(fake, "create_issue", patched)
    return seen


def _run(fake, records, **kwargs):
    return migrate.import_items(
        fake, owner=OWNER, repo=REPO, records=records, **kwargs
    )


# --- pre-flight: refuse before the first write -------------------------------


def test_preflight_refuses_over_cap_title_with_zero_writes(fake):
    """The reporter's exact failure: one title GitHub would reject. It must never
    reach the API — and nothing before it may be written either."""
    records = [_record(CONFORMING), _record("backlog: " + "x" * 300)]
    _seed(fake, records)

    result = _run(fake, records)

    assert result["status"] == "error"
    assert result["error"]["code"] == "validation"
    assert _creates(fake) == [], "a pre-flight that writes first is not a pre-flight"

    offenders = result["error"]["details"]["nonconforming_titles"]
    assert len(offenders) == 1
    assert offenders[0]["index"] == 1
    assert "title-too-long" in offenders[0]["rules"]


def test_preflight_names_every_offender_not_just_the_first(fake):
    """The whole point of pre-flight over fail-at-first-write: the operator gets
    the full list in one pass, so one scrub run fixes everything."""
    records = [
        _record("backlog: " + "x" * 300),                      # title-too-long
        _record(CONFORMING),                                    # conforming
        _record("fix"),                                         # title-too-short
        _record("backlog: import halts on one row; the run ends"),  # non-atomic
        _record("backlog: fix the thing that broke"),           # placeholder
    ]
    _seed(fake, records)

    result = _run(fake, records)

    offenders = result["error"]["details"]["nonconforming_titles"]
    # Non-empty AND exact AND by-identity: a membership-only assertion would pass
    # against an empty list, which is the "green means nothing was looked at" trap.
    assert offenders, "the offender set must not be empty"
    assert len(offenders) == 4
    assert [o["index"] for o in offenders] == [0, 2, 3, 4]

    by_index = {o["index"]: o["rules"] for o in offenders}
    assert "title-too-long" in by_index[0]
    assert "title-too-short" in by_index[2]
    assert "title-non-atomic" in by_index[3]
    assert "title-placeholder" in by_index[4]
    assert _creates(fake) == []


def test_preflight_refusal_is_not_advertised_as_resumable(fake):
    """`resumable: True` invites a re-run. Re-running an unfixed corpus reproduces
    the refusal exactly, so claiming resumable here would send the operator in a
    loop — the one behaviour the reporter was already stuck in."""
    records = [_record("backlog: " + "x" * 300)]
    _seed(fake, records)

    details = _run(fake, records)["error"]["details"]

    assert details["resumable"] is False
    assert details["created"] == []


def test_conforming_corpus_imports_unchanged(fake):
    """The regression guard. A corpus that conforms must behave exactly as before
    the pre-flight existed."""
    records = [_record(CONFORMING), _record("backlog: a second conforming title")]
    _seed(fake, records)

    result = _run(fake, records)

    assert result["status"] == "ok"
    assert len(result["data"]["created"]) == 2
    assert result["data"]["failed"] == []
    assert len(_creates(fake)) == 2


def test_preflight_titles_is_pure(fake):
    """It is called before the transport is wrapped or paced, so it must not need
    one. Passing no transport at all is the assertion."""
    offenders = migrate.preflight_titles([_record("x"), _record(CONFORMING)])

    assert len(offenders) == 1
    assert offenders[0]["index"] == 0


# --- per-item isolation: one bad row does not end the run --------------------


def test_validation_failure_isolates_and_the_run_continues(fake):
    """The reporter's second failure mode. Item 2 is rejected; items 1 and 3 must
    still land, and the rejection must be reported rather than swallowed."""
    records = [_record(CONFORMING), _record("backlog: the rejected one"), _record("backlog: the third one")]
    # Seeding every label first makes the mutation sequence exactly one create per
    # record, so the fault lands on the create the test names and nowhere else.
    _seed(fake, records)
    fake.fail_at_mutation(2, code="validation")

    result = _run(fake, records)

    assert result["status"] == "ok"
    assert len(result["data"]["created"]) == 2
    failed = result["data"]["failed"]
    assert len(failed) == 1
    assert failed[0]["title"] == "backlog: the rejected one"
    assert any("REJECTED" in w for w in result["warnings"]), (
        "a run that drops items while reporting ok must say so"
    )


@pytest.mark.parametrize("code", ["auth", "not_found", "unavailable"])
def test_non_validation_codes_still_cut_the_run(fake, code, monkeypatch):
    """The line that keeps isolation from becoming a liability: these describe the
    RUN, not the item. Isolating them would spend one futile round-trip per
    remaining record and bury 'your token expired' in a 396-line failure list."""
    records = [_record(CONFORMING), _record("backlog: the second title"), _record("backlog: the third title")]
    _seed(fake, records)
    attempts = _fail_creates(monkeypatch, fake, {1: code})

    result = _run(fake, records)

    assert result["status"] == "error"
    assert result["error"]["code"] == code
    assert result["error"]["details"]["resumable"] is True
    assert result["error"]["details"]["failed"] == [], (
        "a run-fatal code must not be recorded as an item-level rejection"
    )
    # It CUT rather than continuing: the third record was never attempted.
    assert attempts["n"] == 2


def test_exhausted_rate_limit_budget_still_cuts(fake):
    """`rate_limited` is retried in-run and, when the budget is exhausted, takes
    the resumable cut. It must not be reclassified as item-fatal — that would turn
    a pause-and-retry into a silently dropped item."""
    records = [_record(CONFORMING), _record("backlog: the second title")]
    _seed(fake, records)
    fake.set_rate_limited(True)
    backoff = migrate.RateLimitBackoff(max_retries=1, base_seconds=0, sleep=lambda _s: None)

    result = _run(fake, records, backoff=backoff)

    assert result["status"] == "error"
    assert result["error"]["code"] == "rate_limited"
    assert result["error"]["details"]["resumable"] is True
    assert result["error"]["details"]["failed"] == []


def test_consecutive_rejections_trip_the_breaker(fake, monkeypatch):
    """Isolation must be bounded. A systematically bad corpus should stop, not
    spend one API round-trip per item to learn the same thing N times."""
    limit = migrate._CONSECUTIVE_VALIDATION_LIMIT
    records = [_record(f"backlog: item number {n} of the corpus") for n in range(limit + 4)]
    _seed(fake, records)
    attempts = _fail_creates(monkeypatch, fake, {n: "validation" for n in range(len(records))})

    result = _run(fake, records)

    assert result["status"] == "error"
    assert result["error"]["code"] == "validation"
    assert str(limit) in result["error"]["message"], (
        "the operator must learn why the RUN stopped, not why one item did"
    )
    assert len(result["error"]["details"]["failed"]) == limit
    # Stopped AT the limit — the remaining 4 were never attempted, which is the
    # whole yield of the breaker.
    assert attempts["n"] == limit
    assert result["error"]["details"]["resumable"] is True


def test_scattered_rejections_do_not_accumulate_into_a_stop(fake, monkeypatch):
    """The breaker counts CONSECUTIVE rejections. Scattered one-off failures across
    a large corpus are exactly what isolation is for; counting them cumulatively
    would stop a run that is working."""
    limit = migrate._CONSECUTIVE_VALIDATION_LIMIT
    records = [_record(f"backlog: item number {n} of the corpus") for n in range(limit * 3)]
    _seed(fake, records)
    doomed = set(range(0, len(records), 2))  # every other one — never `limit` in a row
    _fail_creates(monkeypatch, fake, {n: "validation" for n in doomed})

    result = _run(fake, records)

    assert result["status"] == "ok", "alternating failures must never trip a consecutive breaker"
    assert len(result["data"]["failed"]) == len(doomed)
    assert len(result["data"]["created"]) == len(records) - len(doomed)


# --- the envelope: `failed` survives every exit ------------------------------


def test_failed_survives_the_transport_error_cut(fake, monkeypatch):
    """Third instance of a named learning class in this function (BKL-3K9N,
    BKL-9V2W were the first two): the error return is built by a DIFFERENT
    constructor than the success return, and silently drops any field the success
    path added. A rejection accrued before the cut is not recoverable on resume —
    the re-run retries the item and may reject it again, but the record of what
    this run dropped is gone."""
    records = [_record(CONFORMING), _record("backlog: the second title"), _record("backlog: the third title")]
    _seed(fake, records)
    _fail_creates(monkeypatch, fake, {0: "validation", 1: "auth"})

    result = _run(fake, records)

    assert result["status"] == "error"
    assert result["error"]["code"] == "auth"
    failed = result["error"]["details"]["failed"]
    assert len(failed) == 1
    assert failed[0]["title"] == CONFORMING


def test_failed_survives_the_unexpected_boundary_cut(fake, monkeypatch):
    """The SECOND error return — `(OSError, json.JSONDecodeError)`. It is a
    separate `return` built by a separate constructor, so proving the field
    survives the TransportError path proves nothing about this one. That is
    precisely how this class recurred twice already."""
    records = [_record(CONFORMING), _record("backlog: the second title")]
    _seed(fake, records)

    real_create = fake.create_issue
    seen = {"n": 0}

    def patched(*args, **kwargs):
        index = seen["n"]
        seen["n"] += 1
        if index == 0:
            raise TransportError("validation", "injected rejection")  # isolated
        raise OSError("socket went away")  # the unexpected boundary, ERR-6

    monkeypatch.setattr(fake, "create_issue", patched)
    assert real_create is not None  # the patch replaces it; nothing should reach it

    result = _run(fake, records)

    assert result["status"] == "error"
    assert result["error"]["code"] == "unavailable"
    failed = result["error"]["details"]["failed"]
    assert len(failed) == 1
    assert failed[0]["title"] == CONFORMING
