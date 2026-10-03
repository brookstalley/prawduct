"""``prawduct-hook contribute``: anonymous stats reports, built for preview.

The owner's two goals for contribution are to collect telemetry that improves
prawduct, and to know nothing about the contributor. The second governs every
choice here, so a report is built to carry nothing that could name a product:

- **No identifier of any kind.** No install id, product name, path, branch,
  scope, sha, finding text or language, and no time finer than the report's
  window.
- **An allowlist, not a filter.** ``contribution_schema.json`` is the one home
  of the keys a report may carry. Every value is an integer, a number on its
  field's step, one of its field's enum values, or one of the schema's volume
  bands, so free text cannot be expressed. :func:`validate` holds a report to
  it before anything can leave.
- **Coarsened against fingerprinting.** Volumes become log bands, rates and
  medians are rounded to their field's step, and the plugin version is
  ``major``/``minor`` plus a ``dev`` flag, so a ``-dev.N`` build never shows its
  ``N``. A metric whose denominator is under the schema's floor is left out
  rather than sent, because a rate over two reviews is a near-identifier and
  not a measurement.

A report covers one **settled window**: one ISO week, for one plugin version,
offered only once the week ended at least :data:`SETTLE_DAYS` ago. The wait
lets findings raised late in the week be dispositioned before their outcomes
are read, because a sent window is never sent again and so never corrects
itself. Dedupe is a record on this clone of the windows already sent, because
the collector cannot dedupe reports that carry no identifier. Only the most
recent :data:`MAX_WEEKS` settled weeks are offered, so a first opt-in previews a
few reports rather than months of history.

A week is a hard edge. A scope whose rounds span a Monday counts as a scope in
each week, and a Stop block whose session started the week before has no
session to divide by. Both read a little low, and neither biases one plugin
version against another.

The numbers come from :func:`stats.aggregate`, the ``stats`` report over the
clone-shared evidence store, so a contributed week uses ``stats``' own
definitions over that week, with dev builds bucketed apart from releases.

The network stack is imported only inside a send, because the session
briefing imports this module for every product, and a product at the default
must not pay for TLS at session start.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import evidence, stats
from .core import PREF_ROW_PRESENT, PREF_ROW_UNREADABLE, atomic_write_text, read_preference_row
from .timewindow import parse_instant

SCHEMA_PATH = Path(__file__).with_name("contribution_schema.json")
#: The sent-window record's own format version, separate from the report's.
SENT_RECORD_SCHEMA = 1
SENT_RECORD_BASENAME = "contributions.json"
#: Held for the whole of a send, so two sessions on one clone cannot both read
#: the record, both claim a window and both send it.
SEND_LOCK_BASENAME = "contributions.lock"
#: A lock older than this was left by a send that died, not one still running:
#: a send is at most MAX_WEEKS requests of SEND_TIMEOUT_SECONDS each.
STALE_LOCK_SECONDS = 600
#: How many of the most recent settled ISO weeks are offered.
MAX_WEEKS = 8
#: How long after a week ends before it is offered.
SETTLE_DAYS = 7
_DEV_SUFFIX = "-dev"
#: Where reports go: prawduct's collector (`collector/`), deployed on the
#: owner's Cloudflare account. A plugin constant and never configuration, so no
#: setting can point a product's reports anywhere else. An empty endpoint
#: refuses every send.
COLLECTOR_ENDPOINT = "https://prawduct-collector.brooks-76d.workers.dev/v1/report"
#: The only identifying header a send carries. urllib's default names the
#: Python version, which is a fingerprint the report itself is built to avoid.
USER_AGENT = "prawduct"
SEND_TIMEOUT_SECONDS = 10
#: Tolerance for "is this number on its step": steps are decimal fractions
#: that binary floats carry inexactly.
_STEP_EPSILON = 1e-6


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# --- validation -----------------------------------------------------------


def _is_number(value) -> bool:
    # bool is an int subclass; True must never pass as 1. An int is finite by
    # construction, and math.isfinite overflows on a huge one rather than
    # answering, so only a float is asked.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return isinstance(value, int) or math.isfinite(value)


def _field_problem(name: str, spec: dict, value, bands: list) -> "str | None":
    kind = spec.get("type")
    if kind == "enum":
        ok = any(type(value) is type(allowed) and value == allowed for allowed in spec["values"])
        return None if ok else f"{name}: {value!r} is not one of {spec['values']}"
    if kind == "band":
        return None if isinstance(value, str) and value in bands else f"{name}: {value!r} is not a band"
    if kind in ("integer", "number"):
        if not _is_number(value):
            return f"{name}: {value!r} is not a number"
        if kind == "integer" and not isinstance(value, int):
            return f"{name}: {value!r} is not an integer"
        if not spec["min"] <= value <= spec["max"]:
            return f"{name}: {value!r} is outside [{spec['min']}, {spec['max']}]"
        step = spec.get("step")
        if step is not None and abs(value / step - round(value / step)) > _STEP_EPSILON:
            return f"{name}: {value!r} is not a multiple of {step}"
        return None
    return f"{name}: the schema gives it an unknown type {kind!r}"


def validate(report, schema: dict) -> list[str]:
    """Every reason ``report`` may not leave this machine; empty means it may."""
    if not isinstance(report, dict):
        return ["a report must be a JSON object"]
    fields = schema["fields"]
    problems = [f"{key}: not in the allowlist" for key in report if key not in fields]
    problems += [
        f"{name}: required and missing"
        for name, spec in fields.items()
        if spec.get("required") and name not in report
    ]
    for name, value in report.items():
        if name in fields:
            problem = _field_problem(name, fields[name], value, schema["bands"])
            if problem:
                problems.append(problem)
    return problems


# --- coarsening -------------------------------------------------------------


def band(count: int, bands: list) -> str:
    """The log-scale band a volume falls in, read from the schema's labels."""
    for label in bands:
        low, _, high = label.rstrip("+").partition("-")
        if label.endswith("+") and count >= int(low):
            return label
        if count >= int(low) and count <= int(high or low):
            return label
    raise ValueError(f"no band holds {count}")


def to_step(value: float, spec: dict):
    """``value`` rounded half-up to the field's step and clamped to its range.

    A whole step is reported as an integer, so ``3.0`` and ``3`` cannot become
    two spellings of one value.
    """
    step = spec["step"]
    stepped = math.floor(value / step + 0.5) * step
    stepped = min(max(stepped, spec["min"]), spec["max"])
    decimals = max(0, -math.floor(math.log10(step))) + 1
    stepped = round(stepped, decimals)
    return int(stepped) if float(stepped).is_integer() else stepped


# --- windows ----------------------------------------------------------------


def contribution_bucket(fact: dict) -> str:
    """``3.7`` or ``3.7-dev``: the version bucket, split by whether a dev build
    wrote the fact. A report names the dev flag, never the build number."""
    actor = fact.get("actor")
    plugin = actor.get("plugin") if isinstance(actor, dict) else None
    bucket = stats.version_bucket(plugin)
    if bucket != "unknown" and isinstance(plugin, str) and _DEV_SUFFIX in plugin:
        return bucket + _DEV_SUFFIX
    return bucket


def window_id(iso_year: int, iso_week: int, bucket: str) -> str:
    return f"{iso_year}-W{iso_week:02d}:{bucket}"


def settled_weeks(facts: list[dict], now: datetime) -> list[tuple[int, int]]:
    """ISO weeks that ended at least :data:`SETTLE_DAYS` ago and hold at least
    one fact, newest :data:`MAX_WEEKS` only, oldest first."""
    settled = (now - timedelta(days=SETTLE_DAYS)).date()
    this_monday = settled - timedelta(days=settled.weekday())
    earliest = this_monday - timedelta(weeks=MAX_WEEKS)
    weeks = set()
    for fact in facts:
        instant = parse_instant(fact.get("ts"))
        if instant is None:
            continue
        day = instant.astimezone(timezone.utc).date()
        if earliest <= day < this_monday:
            iso = day.isocalendar()
            weeks.add((iso[0], iso[1]))
    return sorted(weeks)


def _denominators(v: dict) -> dict:
    measured = v["review_seconds"]["measured"]
    # ``stats`` owns which outcomes count as answered; the floor reads its count.
    answered = {
        f"answered_{severity}": v["findings"][severity]["answered"]
        for severity in ("blocking", "warning", "note")
    }
    return {
        "sessions": v["sessions"],
        "scopes": v["scopes"],
        "reviews": v["reviews"]["total"],
        "measured_reviews": measured["reviews"],
        "measured_scopes": measured["per_scope"]["n"],
        "verify_rounds": v["verify_rounds"]["total"],
        "test_runs": v["test_runs"]["total"],
        **answered,
    }


def _share(part, whole):
    return part / whole if whole else None


def _minutes(seconds):
    return None if seconds is None else seconds / 60


def _metrics(v: dict) -> dict:
    """Each schema metric's raw value from one ``stats`` version bucket. A
    value of ``None`` has no answer in this window and is left out."""
    reviews = v["reviews"]["total"]
    measured = v["review_seconds"]["measured"]
    findings = v["findings"]
    return {
        "rounds_per_scope_median": v["rounds_per_scope"]["median"],
        "rounds_per_scope_p90": v["rounds_per_scope"]["p90"],
        "review_minutes_median": _minutes(measured["median"]),
        "review_minutes_per_scope_median": _minutes(measured["per_scope"]["median"]),
        "estimated_only_review_share": _share(v["review_seconds"]["estimated"]["reviews"], reviews),
        "empty_verify_round_share": _share(v["verify_rounds"]["empty"], v["verify_rounds"]["total"]),
        "rereview_same_interval_share": _share(v["rereviews"]["same_interval"], reviews),
        "rereview_same_head_share": _share(v["rereviews"]["same_head_tree"], reviews),
        "stops_blocked_per_session": v["stop_blocks"]["stops_blocked_per_session"],
        "guard_refusals_per_session": v["guard_refusals"]["per_session"],
        "transfer_grants_per_session": v["transfer_grants"]["per_session"],
        "blocking_per_review": _share(findings["blocking"]["raised"], reviews),
        "warning_per_review": _share(findings["warning"]["raised"], reviews),
        "note_per_review": _share(findings["note"]["raised"], reviews),
        "blocking_acted_on_rate": findings["blocking"]["acted_on_rate"],
        "warning_acted_on_rate": findings["warning"]["acted_on_rate"],
        "note_acted_on_rate": findings["note"]["acted_on_rate"],
        "blocking_fixed_per_scope": v["blocking_fixed_per_scope"],
        "warning_fixed_per_scope": v["warnings_fixed_per_scope"],
        "red_test_run_share": _share(v["test_runs"]["red"], v["test_runs"]["total"]),
    }


def build_report(iso_year: int, iso_week: int, bucket: str, v: dict, schema: dict) -> dict:
    """One report from one ``stats`` version bucket. Floors and steps come from
    the schema, so the allowlist is the only place either is written."""
    version, dev, _ = bucket.partition(_DEV_SUFFIX)
    major, minor = (int(part) for part in version.split("."))
    fields, floor = schema["fields"], schema["floor"]
    denominators = _denominators(v)
    report = {
        "schema": schema["schema"],
        "iso_year": iso_year,
        "iso_week": iso_week,
        "plugin_major": major,
        "plugin_minor": minor,
        "dev": bool(dev),
        "sessions": band(denominators["sessions"], schema["bands"]),
        "scopes": band(denominators["scopes"], schema["bands"]),
        "reviews": band(denominators["reviews"], schema["bands"]),
    }
    for name, value in _metrics(v).items():
        spec = fields[name]
        if value is None or denominators[spec["floor_on"]] < floor:
            continue
        report[name] = to_step(value, spec)
    return report


def pending_reports(facts: list[dict], now: datetime, sent: set, schema: dict) -> list[dict]:
    """``[{"window": id, "report": {...}}]`` for every settled, unsent window
    that holds a review or a recorded session, oldest first."""
    pending = []
    for iso_year, iso_week in settled_weeks(facts, now):
        monday = date.fromisocalendar(iso_year, iso_week, 1)
        by_bucket = stats.aggregate(
            facts,
            since=monday.isoformat(),
            until=(monday + timedelta(days=6)).isoformat(),
            bucket=contribution_bucket,
        )
        for bucket, v in by_bucket.items():
            if bucket == "unknown" or not (v["reviews"]["total"] or v["sessions"]):
                continue
            wid = window_id(iso_year, iso_week, bucket)
            if wid not in sent:
                pending.append({"window": wid, "report": build_report(iso_year, iso_week, bucket, v, schema)})
    return pending


# --- the bytes ----------------------------------------------------------------


def canonical_bytes(report: dict) -> bytes:
    """The exact bytes one report is sent as: sorted keys, no whitespace."""
    return json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")


def reports_digest(reports: list[dict]) -> str:
    """``sha256:<hex>`` over every report's bytes, in order. Approving it
    approves exactly these reports and no others."""
    digest = hashlib.sha256()
    for report in reports:
        digest.update(canonical_bytes(report))
        digest.update(b"\n")
    return f"sha256:{digest.hexdigest()}"


# --- the sent-window record -------------------------------------------------


def sent_record_path(project_dir: Path) -> "Path | None":
    store = evidence.store_path(project_dir)
    return None if store is None else store.with_name(SENT_RECORD_BASENAME)


def read_sent(project_dir: Path) -> "tuple[set | None, str | None]":
    """``(windows, None)``, or ``(None, reason)`` when the record exists and
    cannot be read. An unreadable record refuses rather than reading as empty,
    because empty would offer every window again."""
    path = sent_record_path(project_dir)
    if path is None:
        return None, "not inside a git repository"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return set(), None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"the sent-window record {path} could not be read ({exc})"
    sent = data.get("sent") if isinstance(data, dict) else None
    if not isinstance(sent, list) or data.get("schema") != SENT_RECORD_SCHEMA:
        return None, f"the sent-window record {path} is not a schema-{SENT_RECORD_SCHEMA} record"
    return {w for w in sent if isinstance(w, str)}, None


def _write_sent(project_dir: Path, windows: set) -> None:
    """Replace the sent-window record. OSError propagates: a send that cannot
    record its window must not happen."""
    path = sent_record_path(project_dir)
    if path is None:
        raise OSError("not inside a git repository")
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"schema": SENT_RECORD_SCHEMA, "sent": sorted(windows)}
    atomic_write_text(path, json.dumps(record, indent=1) + "\n")


# --- consent ------------------------------------------------------------------

#: The three consent states. ``never`` is the default, and it is where a
#: product lands whenever the row is absent, empty, misspelled or unreadable:
#: the owner's condition is that contribution is off by default and a product
#: opts in affirmatively, so only a row its owner wrote as ``ask`` or
#: ``always`` can open the socket. (The upstream-filing row defaults the other
#: way, to ``ask-user``, because a bug report is the person's own act; a stats
#: upload is not.)
PREF_NEVER = "never"
PREF_ASK = "ask"
PREF_ALWAYS = "always"
PREFERENCE_STATES = (PREF_NEVER, PREF_ASK, PREF_ALWAYS)
PREFERENCE_LABEL = "Stats contribution"


def read_preference(project_dir: Path) -> "tuple[str, str | None]":
    """``(state, warning)``: the product's consent, and why it is not the row's
    when the two differ. Every failure reads as :data:`PREF_NEVER`.

    Silent for the ordinary cases: no file, no row, or a row left unset (the
    shipped template's ``(unset — …)``, whose value is empty). The warning is
    set whenever the owner could believe they opted in and have not: a value
    that is not a state, or a file that cannot be read."""
    row = read_preference_row(project_dir, PREFERENCE_LABEL)
    if row.state == PREF_ROW_UNREADABLE:
        return PREF_NEVER, (
            f"project-preferences.md could not be read ({row.error}), so `{PREFERENCE_LABEL}` "
            f"reads as {PREF_NEVER}"
        )
    if row.state != PREF_ROW_PRESENT or not row.value:
        return PREF_NEVER, None
    if row.value in PREFERENCE_STATES:
        return row.value, None
    return PREF_NEVER, (
        f"`{PREFERENCE_LABEL}` in project-preferences.md reads {row.value!r}, which is not one "
        f"of {'/'.join(PREFERENCE_STATES)}, so it reads as {PREF_NEVER} and nothing is sent"
    )


def _consent_line(state: str) -> str:
    if state == PREF_NEVER:
        return (
            f"consent: `{PREFERENCE_LABEL}` is {PREF_NEVER}, so nothing can be sent. A product opts "
            f"in only by its owner writing `{PREF_ASK}` or `{PREF_ALWAYS}` in that row of "
            ".prawduct/artifacts/project-preferences.md"
        )
    if state == PREF_ASK:
        return (
            f"consent: `{PREFERENCE_LABEL}` is {PREF_ASK}. Sending needs "
            "`contribute --send --approve <digest>`, with the digest below"
        )
    return f"consent: `{PREFERENCE_LABEL}` is {PREF_ALWAYS}. `contribute --send` sends without a digest"


# --- the transport ------------------------------------------------------------


class NeverArrived(Exception):
    """The collector provably did not store the report: the request never
    reached it, or it answered with a refusal or "retry later"."""


class MaybeArrived(Exception):
    """The report may or may not have been stored."""


#: Replies that prove the report was not stored: 400 is the collector's
#: allowlist refusal, 503 is its storage unavailable, and 429 can only come
#: from Cloudflare's edge (the worker never sends it), before the worker runs.
_NOT_STORED_STATUSES = (400, 429, 503)


def _post(url: str, body: bytes) -> None:
    """POST one report, or raise :class:`NeverArrived` / :class:`MaybeArrived`.

    Proxies come from the environment (``HTTPS_PROXY``), as urllib reads them.
    A redirect is refused rather than followed, because the endpoint is pinned
    and following one would send the report somewhere nobody approved. A
    failed proxy tunnel or TLS handshake happens before any byte of the report
    is written, so it never arrived; so did a reply the collector documents as
    not stored, whose refusal rule is passed on, because the collector keeps no
    logs and its reply is the only diagnostic there is."""
    import http.client  # noqa: PLC0415 — lazy: the briefing imports this module
    import socket  # noqa: PLC0415
    import ssl  # noqa: PLC0415
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=SEND_TIMEOUT_SECONDS):
            return
    except urllib.error.HTTPError as exc:
        if exc.code in _NOT_STORED_STATUSES:
            try:
                rule = json.loads(exc.read() or b"{}").get("refused")
            except (ValueError, AttributeError, OSError):
                rule = None
            detail = f"refused: {rule}" if rule else f"HTTP {exc.code}"
            raise NeverArrived(f"the collector did not store it ({detail})") from exc
        raise MaybeArrived(f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, (ConnectionRefusedError, socket.gaierror, ssl.SSLError)):
            raise NeverArrived(str(reason)) from exc
        if isinstance(reason, OSError) and str(reason).startswith("Tunnel connection failed"):
            raise NeverArrived(str(reason)) from exc
        raise MaybeArrived(str(reason)) from exc
    except (OSError, http.client.HTTPException) as exc:
        raise MaybeArrived(str(exc) or type(exc).__name__) from exc


def _refuse(message: str) -> int:
    print(f"BLOCKED: contribute: {message}", file=sys.stderr)
    return 2


def send_pending(project_dir: Path, pending: list[dict], approve: "str | None") -> int:
    """Send every pending report, one request each, after the consent checks:
    the preference first, then the digest, then a pinned endpoint. A refusal
    happens before the transport and records nothing.

    Delivery is at most once. A window is recorded before its request, and the
    record is withdrawn only when the request provably never arrived, because
    the collector cannot recognise a duplicate of a report that carries no
    identifier."""
    state, warning = read_preference(project_dir)
    if warning:
        print(f"NOTE: contribute: {warning}", file=sys.stderr)
    if state == PREF_NEVER:
        return _refuse(_consent_line(state))
    if not pending:
        print("contribute: no settled window is waiting to be sent")
        return 0
    digest = reports_digest([item["report"] for item in pending])
    if state == PREF_ASK and approve is None:
        return _refuse(
            f"`{PREFERENCE_LABEL}` is {PREF_ASK}, so a send needs --approve with the digest "
            "`contribute` previews"
        )
    if approve is not None and approve != digest:
        return _refuse(
            "--approve does not match the reports pending now, so they are not the bytes that "
            "were approved. Preview again with `contribute`"
        )
    if not COLLECTOR_ENDPOINT:
        # The collector is #950; the operator-facing text names no internal id.
        return _refuse("prawduct's collector is not deployed yet, so there is nowhere to send to")

    lock = _acquire_send_lock(project_dir)
    if isinstance(lock, str):
        print(f"contribute: {lock}", file=sys.stderr)
        return 1
    try:
        return _send_locked(project_dir, pending)
    finally:
        lock.unlink(missing_ok=True)


def _acquire_send_lock(project_dir: Path) -> "Path | str":
    """The lock path, or why it could not be taken. Exclusive creation is the
    whole mechanism: of two sessions racing, exactly one creates the file."""
    record = sent_record_path(project_dir)
    if record is None:
        return "not inside a git repository"
    lock = record.with_name(SEND_LOCK_BASENAME)
    lock.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return lock
        except FileExistsError:
            try:
                age = datetime.now(timezone.utc).timestamp() - lock.stat().st_mtime
            except FileNotFoundError:
                continue  # released between the two calls; try again
            if age < STALE_LOCK_SECONDS:
                return "another session on this clone is sending; nothing was sent"
            lock.unlink(missing_ok=True)  # left by a send that died
        except OSError as exc:
            return f"could not take the send lock ({exc}), so nothing was sent"
    return "could not take the send lock, so nothing was sent"


def _send_locked(project_dir: Path, pending: list[dict]) -> int:
    """The send loop, under the lock. The record is re-read here, inside the
    lock, so a window another session sent since the preview is skipped."""
    sent, reason = read_sent(project_dir)
    if sent is None:
        print(f"contribute: {reason}", file=sys.stderr)
        return 1
    failures = 0
    for item in pending:
        window = item["window"]
        if window in sent:
            continue
        try:
            _write_sent(project_dir, sent | {window})
        except OSError as exc:
            print(f"contribute: could not record {window} as sent ({exc}), so it was not sent", file=sys.stderr)
            return 1
        sent = sent | {window}
        try:
            _post(COLLECTOR_ENDPOINT, canonical_bytes(item["report"]))
        except NeverArrived as exc:
            failures += 1
            sent = sent - {window}
            try:
                _write_sent(project_dir, sent)
                retry = "it stays pending"
            except OSError:
                retry = "it is recorded as sent anyway, because the record could not be rewritten"
            print(f"WARNING: contribute: {window} was not stored ({exc}); {retry}", file=sys.stderr)
        except MaybeArrived as exc:
            failures += 1
            print(
                f"WARNING: contribute: {window} may or may not have arrived ({exc}). It stays recorded "
                "as sent, because a duplicate cannot be told apart from a second contributor",
                file=sys.stderr,
            )
        else:
            print(f"contribute: sent {window}")
    return 1 if failures else 0


# --- the briefing -------------------------------------------------------------


def briefing_line(project_dir: Path, now: "datetime | None" = None) -> "str | None":
    """The session briefing's line about stats contribution, or ``None``.

    Silent at the default, and without a store read, so a product that never
    opted in pays nothing. A row that is present but not a state is named,
    because its owner may believe they opted in. An opted-in product whose
    contribution has stopped (an unreadable store or sent record) is told so,
    because under ``always`` this line is the only thing that prompts a send.
    Under ``ask`` the line asks for the person's yes on the exact bytes; under
    ``always`` it tells the agent to send, because the owner already chose."""
    state, warning = read_preference(project_dir)
    if warning:
        return f"Stats: contribution is off — {warning}. The row is the owner's to fix"
    if state == PREF_NEVER or not COLLECTOR_ENDPOINT:
        return None
    read = evidence.read_facts(project_dir)
    sent, reason = read_sent(project_dir)
    if read["status"] == "error" or sent is None:
        stuck = read.get("reason") if read["status"] == "error" else reason
        return f"Stats: contribution is stuck — {stuck}. Nothing is sent until that is fixed"
    pending = pending_reports(read["facts"], now or datetime.now(timezone.utc), sent, load_schema())
    if not pending:
        return None
    if state == PREF_ASK:
        return (
            f"Stats: {len(pending)} anonymous report(s) ready to contribute — show the person "
            "`prawduct-hook contribute`'s exact bytes, and send with `--send --approve <digest>` only "
            "on their yes"
        )
    return (
        f"Stats: {len(pending)} anonymous report(s) ready — run `prawduct-hook contribute --send` "
        "once, without asking: the owner chose `always`"
    )


# --- the command --------------------------------------------------------------


def contribute_cmd(project_dir: Path, argv: list[str], now: "datetime | None" = None) -> int:
    """Body of ``prawduct-hook contribute``.

    Bare, it previews every pending report's exact bytes and their digest, and
    opens no socket. ``--send`` sends them under the product's consent
    (:func:`send_pending`).

    Exit 0 with a preview or a completed send (nothing pending included); 1 on
    bad arguments, an unreadable store or sent-window record, or a send that
    failed; 2 on a refusal: no consent, no matching digest, no collector, or a
    built report failing the allowlist, which is a defect here and is never
    sent."""
    usage = "usage: contribute [--json] | contribute --send [--approve sha256:<digest>]"
    as_json = send = False
    approve = None
    rest = list(argv)
    while rest:
        arg = rest.pop(0)
        if arg == "--json":
            as_json = True
        elif arg == "--send":
            send = True
        elif arg == "--approve" and rest:
            approve = rest.pop(0)
        else:
            print(f"contribute: unknown argument {arg!r} ({usage})", file=sys.stderr)
            return 1
    if approve is not None and not send:
        print(f"contribute: --approve only means something with --send ({usage})", file=sys.stderr)
        return 1
    if send and as_json:
        print(f"contribute: --json is a preview format ({usage})", file=sys.stderr)
        return 1
    read = evidence.read_facts(project_dir)
    if read["status"] == "error":
        print(f"contribute: {read['reason']}", file=sys.stderr)
        return 1
    ahead = len(read.get("schema_ahead") or [])
    if send and ahead:
        # A sent window is never sent again, so a report missing facts this
        # plugin cannot read would stay short for good.
        return _refuse(
            f"{ahead} fact(s) in the store were written by a newer plugin and cannot be read here, "
            "so these reports would undercount for good. Send with the newer plugin"
        )
    sent, reason = read_sent(project_dir)
    if sent is None:
        print(f"contribute: {reason}", file=sys.stderr)
        return 1
    schema = load_schema()
    pending = pending_reports(read["facts"], now or datetime.now(timezone.utc), sent, schema)
    for item in pending:
        problems = validate(item["report"], schema)
        if problems:
            return _refuse(
                f"the report for {item['window']} fails the allowlist, so nothing is offered: "
                + "; ".join(problems)
            )
    if send:
        return send_pending(project_dir, pending, approve)

    state, warning = read_preference(project_dir)
    reports = [item["report"] for item in pending]
    digest = reports_digest(reports) if reports else None
    if as_json:
        print(json.dumps({"schema_version": 1, "pending": pending, "digest": digest}, indent=2))
        return 0
    if warning:
        print(f"NOTE: contribute: {warning}", file=sys.stderr)
    if not pending:
        print("contribute: no settled window is waiting to be sent")
        print(_consent_line(state))
        return 0
    lines = [
        f"contribute: {len(pending)} report(s) would be sent, one request each, "
        "exactly as below (this preview sends nothing)",
    ]
    for item in pending:
        lines += ["", f"window {item['window']}", canonical_bytes(item["report"]).decode("utf-8")]
    lines += ["", f"digest {digest}", _consent_line(state)]
    print("\n".join(lines))
    return 0
