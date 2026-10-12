"""``prawduct-hook aggregate-stats`` — governance stats pooled across products, per plugin version.

``stats`` answers "did version N cost more or protect more than N-1?" for one
product. This answers it across products, from two inputs that share one
shape:

- **Local products the operator names.** Each one's clone-shared evidence
  store is turned into the weekly reports :func:`contribution.weekly_reports`
  builds, so a local week is byte for byte what that product would contribute
  for it. Nothing is discovered: a product is read only because its path was
  named.
- **Contributed reports**, from the collector's published daily bundles, read
  from local files or fetched from the collector on request (``--collector``,
  the only path that opens a socket). Every line is re-validated against
  the allowlist, because the reader does not trust the publisher, and a line
  that fails is counted rather than read. Identical lines are distinct
  contributions, so none is merged.

Each report is one product-week for one plugin version, and that is the unit
every number here is over. Reports carry no identity, so a poisoned line
cannot be found; the view uses medians and trimmed means, so no single report
decides a number. Versions are never pooled.

When contributed data is included, a local window the clone has already sent
is left out, so it is not counted twice.

Informational only: no gate reads it, and it writes nothing.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from . import contribution, evidence

REPORT_SCHEMA_VERSION = 1

#: The share of reports the trimmed mean drops from EACH end, rounded down, so
#: under ten reports it is the plain mean.
TRIM_FRACTION = 0.1

#: The allowlist's volume fields, reported as a count of reports per band.
VOLUME_FIELDS = ("sessions", "scopes", "reviews")

#: The most one fetched response may hold. A day's bundle holds at most a
#: flush's claim of small reports, far under this; a larger reply is not a
#: bundle and is refused before it is parsed.
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
FETCH_TIMEOUT_SECONDS = 10
#: A bundle day as the collector names it. The day is interpolated into a URL
#: path, so anything else is refused rather than requested.
_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

_USAGE = (
    "usage: aggregate-stats [<product-dir>...] [--from-file <list>] "
    "[--bundles <file-or-dir>]... [--collector] [--json]"
)


class UsageError(Exception):
    """A bad argument, or an input the operator named that cannot be read."""


class FetchError(Exception):
    """The collector's bundles could not be fetched in full."""


# --- local products -----------------------------------------------------------


def read_local(paths: list[str], now: datetime, schema: dict, exclude_sent: bool) -> dict:
    """Every named product's weekly reports.

    Returns ``{"reports": [...], "sources": [...], "skipped": [...]}``. A
    product that cannot be read is skipped with its reason and the rest still
    report, because one stale checkout should not cost the whole view. Two
    paths into one clone share a store, so the second is skipped as
    ``same-store`` rather than counted twice."""
    reports: list[dict] = []
    sources: list[dict] = []
    skipped: list[dict] = []
    stores: dict[Path, str] = {}
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if not path.is_dir():
            skipped.append({"path": str(path), "reason": "invalid-path"})
            continue
        store = evidence.store_path(path)
        if store is None:
            skipped.append({"path": str(path), "reason": "not-a-git-repo"})
            continue
        store = store.resolve()
        if store in stores:
            skipped.append({"path": str(path), "reason": "same-store", "as": stores[store]})
            continue
        stores[store] = str(path)
        read = evidence.read_facts(path)
        if read["status"] == "empty":
            skipped.append({"path": str(path), "reason": "no-store"})
            continue
        if read["status"] == "error":
            skipped.append({"path": str(path), "reason": "unreadable-store", "detail": read["reason"]})
            continue
        sent: set = set()
        if exclude_sent:
            sent, why = contribution.read_sent(path)
            if sent is None:
                skipped.append({"path": str(path), "reason": "unreadable-sent-record", "detail": why})
                continue
        weekly = contribution.weekly_reports(read["facts"], now, schema, max_weeks=None)
        kept = [item["report"] for item in weekly if item["window"] not in sent]
        reports.extend(kept)
        sources.append({
            "path": str(path),
            "reports": len(kept),
            "already_contributed": len(weekly) - len(kept),
            # Facts a newer plugin wrote are not counted, and the view says how many.
            "schema_ahead": len(read.get("schema_ahead") or []),
        })
    return {"reports": reports, "sources": sources, "skipped": skipped}


# --- contributed reports ------------------------------------------------------


def parse_bundle(text: str, schema: dict) -> dict:
    """``{"reports", "lines", "refused", "schema_ahead"}`` from one bundle's text.

    A line that does not parse, or fails the allowlist, is refused and counted.
    A line naming a newer allowlist ``schema`` than this plugin's is counted
    apart, as ``schema_ahead``: it is a newer version's report this reader
    cannot check, not junk, and the view says so. Nothing from either is
    echoed, because bundle content is untrusted input. Duplicate lines are
    kept: two contributors can send identical reports."""
    out = {"reports": [], "lines": 0, "refused": 0, "schema_ahead": 0}
    for line in text.splitlines():
        if not line.strip():
            continue
        out["lines"] += 1
        try:
            report = json.loads(line)
        except (ValueError, RecursionError):
            # RecursionError: a deeply nested line exhausts the parser's stack.
            out["refused"] += 1
            continue
        if _schema_ahead(report, schema):
            out["schema_ahead"] += 1
            continue
        if contribution.validate(report, schema):
            out["refused"] += 1
            continue
        out["reports"].append(report)
    return out


def _schema_ahead(report, schema: dict) -> bool:
    version = report.get("schema") if isinstance(report, dict) else None
    return (
        isinstance(version, int) and not isinstance(version, bool)
        and version > schema["schema"]
    )


def read_bundle_paths(paths: list[str]) -> list[str]:
    """Each named bundle's text: a file is one bundle, and a directory is every
    ``*.jsonl`` in it, in name order. A path that does not exist, or a file
    that cannot be read, raises :class:`UsageError`: the operator named it, so
    a view without it would look complete and not be."""
    texts = []
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            files = sorted(path.glob("*.jsonl"))
        elif path.is_file():
            files = [path]
        else:
            raise UsageError(f"--bundles {raw}: no such file or directory")
        for file in files:
            try:
                texts.append(file.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError) as exc:
                raise UsageError(f"--bundles {file}: cannot be read ({exc})") from exc
    return texts


def collector_origin() -> str:
    """The pinned collector's origin. The read side derives it from the write
    side's constant, so it can never be pointed somewhere the upload is not."""
    parts = urlsplit(contribution.COLLECTOR_ENDPOINT)
    return f"{parts.scheme}://{parts.netloc}"


def _get(url: str) -> "bytes | None":
    """GET one collector path: its body, or ``None`` on a 404. Anything else
    that is not a 200 raises :class:`FetchError`. Proxies come from the
    environment, as for the upload, and a redirect is refused rather than
    followed, because the origin is pinned."""
    import http.client  # noqa: PLC0415 — lazy: only --collector pays for the network stack
    import urllib.error  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    request = urllib.request.Request(url, headers={"User-Agent": contribution.USER_AGENT})
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise FetchError(f"{url}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(f"{url}: {exc.reason}") from exc
    except (OSError, http.client.HTTPException) as exc:
        raise FetchError(f"{url}: {exc or type(exc).__name__}") from exc
    if len(body) > MAX_RESPONSE_BYTES:
        raise FetchError(f"{url}: the response is larger than {MAX_RESPONSE_BYTES} bytes")
    return body


def fetch_collector(origin: str) -> list[str]:
    """Every published bundle's text, in the index's order. A missing index
    means nothing is published yet, which is no bundles. Any other failure
    raises :class:`FetchError`, because a view missing some bundles would look
    complete."""
    index = _get(f"{origin}/bundles/index.json")
    if index is None:
        return []
    try:
        days = json.loads(index)["days"]
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        raise FetchError(f"{origin}/bundles/index.json is not a bundle index") from exc
    if not isinstance(days, list) or not all(isinstance(d, str) and _DAY.fullmatch(d) for d in days):
        raise FetchError(f"{origin}/bundles/index.json lists something that is not a day")
    texts = []
    for day in days:
        url = f"{origin}/bundles/{day}.jsonl"
        body = _get(url)
        if body is None:
            raise FetchError(f"{url}: listed in the index but not published")
        try:
            texts.append(body.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise FetchError(f"{url}: not UTF-8") from exc
    return texts


# --- aggregation --------------------------------------------------------------


def version_key(report: dict) -> str:
    """``3.7``, or ``3.7-dev`` for a dev build: the report's own version, the
    same bucket the client sent it under."""
    key = f"{report['plugin_major']}.{report['plugin_minor']}"
    return key + "-dev" if report["dev"] else key


def _version_order(key: str) -> tuple:
    version, _, dev = key.partition("-")
    major, minor = version.split(".")
    return int(major), int(minor), bool(dev)


def _week(report: dict) -> str:
    return f"{report['iso_year']}-W{report['iso_week']:02d}"


def robust(values: list) -> dict:
    """``n``, ``median`` and ``trimmed_mean`` of one metric's values."""
    ordered = sorted(values)
    n = len(ordered)
    k = int(n * TRIM_FRACTION)
    return {
        "n": n,
        "median": round(statistics.median(ordered), 4),
        "trimmed_mean": round(statistics.fmean(ordered[k:n - k]), 4),
    }


def aggregate(local: list[dict], contributed: list[dict], schema: dict) -> dict:
    """``{version: {...}}`` over both inputs, versions in ascending order.

    A metric a report omitted, because its denominator was under the floor, is
    absent from that report and is not a zero, so ``n`` differs by metric."""
    metric_names = [
        name for name, spec in schema["fields"].items() if spec.get("type") == "number"
    ]
    grouped: dict[str, dict] = {}
    for origin, reports in (("local", local), ("contributed", contributed)):
        for report in reports:
            group = grouped.setdefault(version_key(report), {"local": [], "contributed": []})
            group[origin].append(report)
    by_version = {}
    for key in sorted(grouped, key=_version_order):
        group = grouped[key]
        reports = group["local"] + group["contributed"]
        weeks = sorted(reports, key=lambda r: (r["iso_year"], r["iso_week"]))
        volume = {}
        for field in VOLUME_FIELDS:
            counts = {label: 0 for label in schema["bands"]}
            for report in reports:
                if field in report:
                    counts[report[field]] += 1
            volume[field] = {label: n for label, n in counts.items() if n}
        metrics = {}
        for name in metric_names:
            values = [report[name] for report in reports if name in report]
            if values:
                metrics[name] = robust(values)
        by_version[key] = {
            "reports": {"local": len(group["local"]), "contributed": len(group["contributed"])},
            "weeks": {"first": _week(weeks[0]), "last": _week(weeks[-1])},
            "volume": volume,
            "metrics": metrics,
        }
    return by_version


# --- rendering ----------------------------------------------------------------


def _number(value: float) -> str:
    return f"{value:g}"


def render_human(report: dict) -> str:
    sources = report["sources"]
    lines = []
    for source in sources["local"]:
        extra = (
            f", {source['already_contributed']} already contributed and left out"
            if source["already_contributed"] else ""
        )
        ahead = (
            f", {source['schema_ahead']} fact(s) from a newer plugin not counted"
            if source["schema_ahead"] else ""
        )
        lines.append(f"local: {source['path']} — {source['reports']} report(s){extra}{ahead}")
    for skip in sources["local_skipped"]:
        detail = f" ({skip['detail']})" if skip.get("detail") else ""
        same = f" as {skip['as']}" if skip.get("as") else ""
        lines.append(f"skipped: {skip['path']} — {skip['reason']}{same}{detail}")
    contributed = sources["contributed"]
    if contributed is not None:
        ahead = (
            f", {contributed['schema_ahead']} written under a newer allowlist "
            "and not counted (run a newer prawduct to include them)"
            if contributed["schema_ahead"] else ""
        )
        lines.append(
            f"contributed: {contributed['lines']} line(s) in {contributed['bundles']} bundle(s), "
            f"{contributed['refused']} refused by the allowlist{ahead}"
        )
    if not report["by_version"]:
        lines.append("no settled weeks to report")
        return "\n".join(lines)
    lines.append(
        "each report is one product-week for one plugin version; "
        "every number below is over reports, never across versions"
    )
    for version, v in report["by_version"].items():
        counts = v["reports"]
        lines.append(
            f"{version} — {counts['local'] + counts['contributed']} report(s): "
            f"{counts['local']} local, {counts['contributed']} contributed; "
            f"{v['weeks']['first']} to {v['weeks']['last']}"
        )
        for field, bands in v["volume"].items():
            if bands:
                lines.append(f"  {field}: " + ", ".join(f"{b} ×{n}" for b, n in bands.items()))
        for name, m in v["metrics"].items():
            lines.append(
                f"  {name}: median {_number(m['median'])}, "
                f"trimmed mean {_number(m['trimmed_mean'])} (n={m['n']})"
            )
    return "\n".join(lines)


# --- the command --------------------------------------------------------------


def _read_path_list(raw: str) -> list[str]:
    """One path per line; blank lines and ``#`` lines are skipped."""
    try:
        text = Path(raw).expanduser().read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise UsageError(f"--from-file {raw}: cannot be read ({exc})") from exc
    return [
        line.strip() for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _parse_args(argv: list[str]) -> dict:
    args = {"products": [], "bundles": [], "collector": False, "json": False}
    rest = list(argv)
    while rest:
        arg = rest.pop(0)
        if arg == "--json":
            args["json"] = True
        elif arg == "--collector":
            args["collector"] = True
        elif arg in ("--from-file", "--bundles"):
            if not rest:
                raise UsageError(f"{arg} needs a value")
            value = rest.pop(0)
            if arg == "--from-file":
                args["products"].extend(_read_path_list(value))
            else:
                args["bundles"].append(value)
        elif arg.startswith("-"):
            raise UsageError(f"unknown argument {arg!r}")
        else:
            args["products"].append(arg)
    if not args["products"] and not args["bundles"] and not args["collector"]:
        raise UsageError("name at least one product or bundle source")
    return args


def aggregate_stats_cmd(argv: list[str], now: "datetime | None" = None) -> int:
    """Body of ``prawduct-hook aggregate-stats``. Exit 0 with a report (no
    reports at all is an answer); exit 1 on a bad argument or a named input
    that cannot be read, or a ``--collector`` fetch that fails."""
    now = now or datetime.now(timezone.utc)
    try:
        args = _parse_args(argv)
        texts = read_bundle_paths(args["bundles"])
    except UsageError as exc:
        print(f"aggregate-stats: {exc} ({_USAGE})", file=sys.stderr)
        return 1
    if args["collector"]:
        try:
            texts += fetch_collector(collector_origin())
        except FetchError as exc:
            print(f"aggregate-stats: the collector's bundles could not be fetched: {exc}", file=sys.stderr)
            return 1
    schema = contribution.load_schema()
    with_contributed = bool(args["bundles"]) or args["collector"]
    local = read_local(args["products"], now, schema, exclude_sent=with_contributed)
    contributed_reports: list[dict] = []
    contributed = None
    if with_contributed:
        contributed = {"bundles": len(texts), "lines": 0, "refused": 0, "schema_ahead": 0}
        for text in texts:
            parsed = parse_bundle(text, schema)
            contributed_reports.extend(parsed["reports"])
            for key in ("lines", "refused", "schema_ahead"):
                contributed[key] += parsed[key]
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {
            "local": local["sources"],
            "local_skipped": local["skipped"],
            "contributed": contributed,
        },
        "by_version": aggregate(local["reports"], contributed_reports, schema),
    }
    if args["json"]:
        print(json.dumps(report, indent=2))
    else:
        print(render_human(report))
    return 0
