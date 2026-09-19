"""The scope record beside a test report — the reader half of the contract.

Specification: ``docs/test-report-contract.md``. A product configures its test
runner so the machine-readable report is a side effect of *every* run, and its
pre/post-run hook writes a small JSON record beside that report saying whether
the invocation ran the whole suite or a narrowed part of it. This module is
what reads that record; nothing here knows what a test runner is, what language
the product is written in, or how the record got written — the path is derived
by string suffix and the content is plain JSON (prawduct's architecture norms:
no gate may assume the governed product shares the runtime's language).

**Why a reader exists at all.** ``test-evidence record --from-junit`` trusts the
caller's assertion that the report covers the declared suite. That was a
reasonable posture while producing a report took a deliberate ``--junit-xml``;
once the report is a side effect of every run, a report from ``pytest -k
billing`` sits at the same path and looks identical, and ingesting it would
record a subset as the suite's evidence. This is the guard that tells them
apart — and the case it exists for is a false GREEN, not a wasted run.

**Error posture.** Authority fails closed: this feeds an evidence record the
freshness gates read, so malformed, schema-ahead, mismatched or narrowed all
refuse. The one permissive case is *absence*, and it is permissive because a
missing record cannot be distinguished from a repo that has never wired a
producer — which is every repo today. Refusals are return values, never
exceptions (project-preferences), including for a record whose ``report`` field
cannot be turned into a path at all.

**The cause is returned, not just the refusal.** Six conditions refuse here and
they do not share a remedy: a narrowed run needs a different one from a record
describing some other file. A reader that folded them into one sentence would
force its caller to print advice that is wrong for five of the six.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

#: The only schema version this reader understands. A record carrying anything
#: else refuses rather than being read optimistically — the same posture the
#: fact store takes on a schema-ahead record, applied to a different artifact.
SCHEMA_VERSION = 1

#: Appended to the report's path to get its record's path. A suffix rather than
#: a sibling-with-a-fixed-name so that several reports in one directory (a
#: multi-environment product's ``test_commands``) each carry their own.
RECORD_SUFFIX = ".scope.json"

FULL = "full"
PARTIAL = "partial"

#: Why an ingest was refused. The caller maps these to remedies, so they name
#: what is wrong with the RECORD rather than what the operator should do.
CAUSE_UNREADABLE = "unreadable"      # the file is there and cannot be read
CAUSE_MALFORMED = "malformed"        # unusable content: bad JSON, not an
                                     # object, or a required field missing
CAUSE_SCHEMA = "schema"              # a version this reader does not know
CAUSE_SCOPE = "scope"                # missing or unrecognised `scope`
CAUSE_MISMATCH = "mismatch"          # a record about some other report
CAUSE_NARROWED = "narrowed"          # a genuine `scope: partial`


class ScopeVerdict(NamedTuple):
    """``ok`` alone decides whether to ingest; ``reason`` is one sentence
    stating what is wrong, and ``cause`` is which of the six it is."""

    ok: bool
    reason: str | None = None
    cause: str | None = None


def record_path(report_path: str | Path) -> Path:
    """The scope record's path for ``report_path``."""
    report = Path(report_path)
    return report.with_name(report.name + RECORD_SUFFIX)


def read_scope_record(report_path: str | Path) -> ScopeVerdict:
    """Whether ``report_path`` may be ingested as suite evidence.

    Applies the rules in the order ``docs/test-report-contract.md`` states
    them: no record proceeds; unreadable, non-object, unknown ``v``, missing or
    invalid ``scope``, and a ``report`` naming some other file each refuse; a
    ``partial`` record refuses and quotes its own ``why``/``at``; ``full``
    proceeds.
    """
    path = record_path(report_path)
    try:
        raw = path.read_text()
    except FileNotFoundError:
        # The permissive case, and the only one. See the module docstring.
        return ScopeVerdict(True)
    except OSError as exc:
        return ScopeVerdict(
            False, f"the scope record {path} could not be read ({exc})", CAUSE_UNREADABLE
        )

    try:
        record = json.loads(raw)
    except json.JSONDecodeError as exc:
        return ScopeVerdict(
            False, f"the scope record {path} is not valid JSON ({exc})", CAUSE_MALFORMED
        )
    if not isinstance(record, dict):
        return ScopeVerdict(
            False, f"the scope record {path} is not a JSON object", CAUSE_MALFORMED
        )

    version = record.get("v")
    if version != SCHEMA_VERSION:
        return ScopeVerdict(
            False,
            f"the scope record {path} declares schema version {version!r}, and "
            f"this reader understands only {SCHEMA_VERSION} — it was written by "
            "a different version of the contract, so what it asserts about the "
            "run is unknown",
            CAUSE_SCHEMA,
        )

    scope = record.get("scope")
    if scope not in (FULL, PARTIAL):
        return ScopeVerdict(
            False,
            f"the scope record {path} carries scope={scope!r}, which is neither "
            f"{FULL!r} nor {PARTIAL!r}",
            CAUSE_SCOPE,
        )

    # Identity before verdict: a record that describes a different file cannot
    # be trusted in either direction, so a copied or moved report loses its
    # record's authority rather than inheriting it.
    claimed = record.get("report")
    if not isinstance(claimed, str) or not claimed.strip():
        # MALFORMED rather than MISMATCH: a record naming no report is not
        # about some other run, it is about nothing, and the two get different
        # remedies — "fetch the report without its record" is nonsense advice
        # for a record that was never written correctly.
        return ScopeVerdict(
            False,
            f"the scope record {path} does not name the report it describes "
            "(the required `report` field)",
            CAUSE_MALFORMED,
        )
    try:
        claims_this_report = Path(claimed).resolve() == Path(report_path).resolve()
    except (OSError, ValueError) as exc:
        # `Path("\x00").resolve()` raises ValueError, and a path the OS refuses
        # to resolve raises OSError. Both are malformed CONTENT reaching a
        # function whose contract is that errors come back as values — so the
        # cause is MALFORMED, not MISMATCH. The distinction is the remedy: a
        # mismatch tells the reader this record belongs to another run and the
        # report can be fetched without it, which is nonsense advice for a
        # record that was never written correctly. The no-`report`-field branch
        # above already classifies its sibling case this way.
        return ScopeVerdict(
            False,
            f"the scope record {path} names a report path that cannot be "
            f"resolved ({exc})",
            CAUSE_MALFORMED,
        )
    if not claims_this_report:
        return ScopeVerdict(
            False,
            f"the scope record {path} describes {claimed}, not the report it "
            "sits beside — it is a record of some other run",
            CAUSE_MISMATCH,
        )

    if scope == PARTIAL:
        why = record.get("why")
        at = record.get("at")
        detail = str(why).strip() if isinstance(why, str) and why.strip() else "no reason recorded"
        when = f" (recorded {at})" if isinstance(at, str) and at.strip() else ""
        return ScopeVerdict(
            False,
            f"the run that produced this report did not cover the whole suite: "
            f"{detail}{when}",
            CAUSE_NARROWED,
        )

    return ScopeVerdict(True)
