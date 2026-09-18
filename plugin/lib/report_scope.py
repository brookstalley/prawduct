"""The scope record beside a test report — the reader half of the contract.

Specification: ``docs/test-report-contract.md``. A product configures its test
runner so the machine-readable report is a side effect of *every* run, and its
pre/post-run hook writes a small JSON record beside that report saying whether
the invocation ran the whole suite or a narrowed part of it. This module is
what reads that record; nothing here knows what a test runner is, what language
the product is written in, or how the record got written — the path is derived
by string suffix and the content is plain JSON (``artifacts/architecture.md``
§ Direction: no gate may assume the governed product shares the runtime's
language).

**Why a reader exists at all.** ``test-evidence record --from-junit`` trusts the
caller's assertion that the report covers the declared suite. That was a
reasonable posture while producing a report took a deliberate ``--junit-xml``;
once the report is a side effect of every run, a report from ``pytest -k
billing`` sits at the same path and looks identical, and ingesting it would
record a subset as the suite's evidence. This is the guard that tells them
apart — and the case it exists for is a false GREEN, not a wasted run.

**Error posture.** Authority fails closed (``artifacts/architecture.md``
§ Direction): this feeds an evidence record the freshness gates read, so
malformed, schema-ahead, mismatched or narrowed all refuse. The one permissive
case is *absence*, and it is permissive because a missing record cannot be
distinguished from a repo that has never wired a producer — which is every repo
today. Refusals are return values, never exceptions (project-preferences).
"""

from __future__ import annotations

import json
from pathlib import Path

#: The only schema version this reader understands. A record carrying anything
#: else refuses rather than being read optimistically — the same posture the
#: fact store takes on a schema-ahead record (``artifacts/data-model.md``
#: § Direction), applied to a different artifact.
SCHEMA_VERSION = 1

#: Appended to the report's path to get its record's path. A suffix rather than
#: a sibling-with-a-fixed-name so that several reports in one directory (a
#: multi-environment product's ``test_commands``) each carry their own.
RECORD_SUFFIX = ".scope.json"

FULL = "full"
PARTIAL = "partial"


def record_path(report_path: str | Path) -> Path:
    """The scope record's path for ``report_path``."""
    report = Path(report_path)
    return report.with_name(report.name + RECORD_SUFFIX)


def read_scope_record(report_path: str | Path) -> tuple[bool, str | None]:
    """Whether ``report_path`` may be ingested as suite evidence.

    Returns ``(True, None)`` to proceed, or ``(False, reason)`` where *reason*
    is one sentence naming what is wrong — the caller owns the remedy text, so
    that it is stated once at the surface the operator is actually holding.

    The rules, in the order ``docs/test-report-contract.md`` states them:
    no record proceeds; unreadable, non-object, unknown ``v``, missing or
    invalid ``scope``, and a ``report`` naming some other file each refuse; a
    ``partial`` record refuses and quotes its own ``why``/``at``; ``full``
    proceeds.
    """
    path = record_path(report_path)
    try:
        raw = path.read_text()
    except FileNotFoundError:
        # The permissive case, and the only one. See the module docstring.
        return True, None
    except OSError as exc:
        return False, f"the scope record {path} could not be read ({exc})"

    try:
        record = json.loads(raw)
    except json.JSONDecodeError as exc:
        return False, f"the scope record {path} is not valid JSON ({exc})"
    if not isinstance(record, dict):
        return False, f"the scope record {path} is not a JSON object"

    version = record.get("v")
    if version != SCHEMA_VERSION:
        return False, (
            f"the scope record {path} declares schema version {version!r}, and "
            f"this reader understands only {SCHEMA_VERSION} — it was written by "
            "a different version of the contract, so what it asserts about the "
            "run is unknown"
        )

    scope = record.get("scope")
    if scope not in (FULL, PARTIAL):
        return False, (
            f"the scope record {path} carries scope={scope!r}, which is neither "
            f"{FULL!r} nor {PARTIAL!r}"
        )

    # Identity before verdict: a record that describes a different file cannot
    # be trusted in either direction, so a copied or moved report loses its
    # record's authority rather than inheriting it.
    claimed = record.get("report")
    if not isinstance(claimed, str) or not claimed.strip():
        return False, (
            f"the scope record {path} does not name the report it describes "
            "(the required `report` field)"
        )
    if Path(claimed).resolve() != Path(report_path).resolve():
        return False, (
            f"the scope record {path} describes {claimed}, not the report it "
            "sits beside — it is a record of some other run"
        )

    if scope == PARTIAL:
        why = record.get("why")
        at = record.get("at")
        detail = str(why).strip() if isinstance(why, str) and why.strip() else "no reason recorded"
        when = f" (recorded {at})" if isinstance(at, str) and at.strip() else ""
        return False, (
            f"the run that produced this report did not cover the whole suite: "
            f"{detail}{when}"
        )

    return True, None
