#!/usr/bin/env python3
"""Measure a governed consumer repo's build economics against prawduct versions.

The derivation behind `documentation/consumer-build-metrics.md`, kept runnable so
its numbers are falsifiable. A count transcribed into prose goes stale silently as
a corpus grows; cite this command rather than the digits.

    tools/measure-consumer-overhead.py ../discodon --prs
    tools/measure-consumer-overhead.py ../discodon --marker
    tools/measure-consumer-overhead.py ../bankmachine --since 2026-09-13T08:55:57-06:00

It buckets a consumer repo's history into windows, one per prawduct MINOR series,
and reports per window: engaged wall clock, lines written by class, Critic and PR
review load, findings and severities, fix-commit composition, and test growth.
The point is the SHAPE ACROSS WINDOWS, not any single figure.

Four sources, three of them independent of each other:

* the consumer's `.prawduct/.governance-ledger.jsonl` — every review fact
* the consumer's git history (`--numstat`), classified by path
* this repo's release tags, which define the window boundaries
* optionally GitHub, for merged-PR cadence (`--prs`; needs `gh` authenticated)

Things to know before citing a number from this script — the full list, with
the ones that have actually burned someone, is `## Hazards` in that document:

* **`duration_seconds` in the ledger is self-reported by the reviewing model**,
  not a measured wall clock: the values are round (74 distinct values across
  discodon's 1,318 review events). This script cross-checks them against
  interval-measured time and prints the ratio per window. Trust the self-reports
  only where that ratio is near 1. Rows dispatched under a plugin carrying the
  per-kind dispatch clock also have a code-read interval, for BOTH review kinds —
  but a consumer's history predates it, so expect the self-reported population to
  dominate any window that reaches back.
* **Interval attribution is biased by commit density.** Time is attributed to the
  event that ENDS each interval, so in a window with few commits, coding time gets
  absorbed into whatever governance event happened to come next. The `ratio`
  column in the VALIDATION table is the tell: where it is far above 1, the
  measured phase split is inflated and the self-reported one is the better series.
* **Two different things are called "measured" here, deliberately kept apart.**
  `critic_hours_measured` is INTERVAL-measured — wall time attributed to the event
  that ends each interval, and biased by commit density (hazard 2 above). The
  `<kind>_clock_*` columns are something stronger: a clock read in code before the
  reviewer was spawned and again when the review ended (`dispatched_at` on the
  ledger envelope; the end is `review_written_at` for a PR review and the append
  otherwise). Read `<kind>_clock_runs` before `<kind>_clock_hours` — a clock
  figure covering 2 of a window's 40 reviews is not that window's cost, and the
  two populations are never pooled, because a median over a mixture of clock
  readings and model recollections measures neither.
* **`prawduct-hook review-stats` pools Critic and PR reviews** under one `reviews`
  count and one duration total. This script keeps them separate. A figure labelled
  "Critic hours" that came from `review-stats` includes PR review hours too: for
  discodon's full ledger, 14.7% of that pooled total is PR review, so the pooled
  number overstates Critic by 17.3%.
* **The review-driven fix classifier is a wide heuristic, not a measurement.**
  Matching the full commit body (as here) versus only its first 600 characters
  moves the per-window product-bug rate by up to 60%. The SHAPE is robust to that
  choice — flat, no trend, in either variant — but treat the level as a band.
* **A repo that does not use conventional-commit prefixes cannot report fix or
  test commit counts.** Those columns print `—`, never `0`, because a zero there
  reads as "no bugs" and means "not measurable this way".
* **Release tags do not tell you what version a consumer actually ran.** Use
  `--marker`; it dates the most recent version transition.
* **Version windows are confounded with what the consumer was building.** These
  are correlations across a handful of windows, not a controlled comparison.
* **Window boundaries are fuzzy by up to one session.** Consumers that pin the
  marketplace to `ref: main` with `autoUpdate` pick up a release at the next
  session start, not at the tag.

Backfilled event kinds are DETECTED and reported, not silently averaged: an event
kind whose timestamps all fall inside a tiny fraction of the span is a one-off
migration, and any rate computed from it is meaningless.

Exit 1 if the consumer repo has no ledger — there is nothing to measure.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugin" / "lib"))

from review_dispatch import event_interval_seconds  # noqa: E402


UTC = dt.timezone.utc

# A gap longer than this ends a session. Chosen to bridge a meal and a meeting
# but not a night; the reported hours are insensitive to it within ~30 minutes.
SESSION_GAP = dt.timedelta(minutes=90)
# Credited before a session's first event, for the work that produced it.
SESSION_LEADIN = dt.timedelta(minutes=20)

# A fix commit whose subject or body reads like it is closing a review finding
# rather than a defect a user could hit. Deliberately generous: the residue
# ("product-bug fixes") is the conservative half, and it is the half that matters.
REVIEW_DRIVEN = re.compile(
    r"critic|blocking|blocker|warning|finding|review|cumulative|rev-\d{4}|round",
    re.IGNORECASE,
)

GENERATED = re.compile(r"(^|/)(package-lock\.json|uv\.lock|poetry\.lock|[^/]*\.snap)$")
TEST_PATH = re.compile(
    r"(^|/)tests?/|(^|/)__tests__/|(^|/)conftest\.py$"
    r"|(^|/)test_[^/]+\.py$|(^|/)[^/]+_test\.py$|\.test\.[jt]sx?$|\.spec\.[jt]sx?$"
)
DOC_PATH = re.compile(r"^(docs|documentation|design_handoff)/|\.md$|\.rst$")
GOVERNANCE_PATH = re.compile(r"^\.prawduct/|^\.claude/|^CLAUDE\.md$")

# Conventional-commit prefixes that produce running code.
CODE_KINDS = {"feat", "fix", "refactor", "perf", "style", "lint", "build", "ci", "revert"}
TEST_KINDS = {"test"}


def git(repo: Path, *args: str) -> str:
    """Run git in `repo` and return stdout. Git's own errors surface on stderr."""
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, errors="replace", check=False,
    ).stdout


def classify(path: str) -> str:
    """Bucket a repo-relative path. Order matters: tests before docs before code.

    Generic on purpose — it keys on layout conventions, not on any one product's
    package name, so the same run works against a consumer this script has never
    seen. A consumer with an unusual layout should be spot-checked with
    `--show-classification` before its `code` numbers are cited.
    """
    if GENERATED.search(path):
        return "generated"
    if TEST_PATH.search(path):
        return "test"
    if GOVERNANCE_PATH.search(path):
        return "governance"
    if DOC_PATH.search(path):
        return "docs"
    return "code"


def minor_windows(framework: Path, since: dt.datetime, until: dt.datetime) -> list[dict]:
    """Window boundaries = the first release tag of each prawduct minor series.

    Patch releases land hours apart, which is finer than a consumer can respond
    to; the minor series is the coarsest grouping that still tracks a change in
    what the framework asks of its consumers.
    """
    tags: list[tuple[tuple[int, int], dt.datetime]] = []
    for tag in git(framework, "tag", "--sort=creatordate").split():
        m = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", tag)
        if not m:
            continue
        iso = git(framework, "log", "-1", "--format=%aI", tag).strip()
        if not iso:
            continue
        tags.append(((int(m[1]), int(m[2])), _parse_instant(iso)))
    if not tags:
        sys.exit(f"no vN.N.N release tags in {framework} — cannot derive windows")

    starts: dict[tuple[int, int], dt.datetime] = {}
    for key, when in tags:
        if key not in starts or when < starts[key]:
            starts[key] = when

    ordered = sorted(starts.items(), key=lambda kv: kv[1])
    windows = []
    for i, (key, when) in enumerate(ordered):
        end = ordered[i + 1][1] if i + 1 < len(ordered) else until
        if end <= since:
            continue
        windows.append({
            "series": f"v{key[0]}.{key[1]}",
            "start": max(when, since),
            "end": min(end, until),
        })
    return [w for w in windows if w["end"] > w["start"]]


def read_commit_bodies(repo: Path, since: dt.datetime) -> dict[str, str]:
    """Full message text per commit hash.

    A separate pass on purpose: a commit body contains newlines, and lines that
    begin with `+` or carry tabs, so interleaving it with `--numstat` output makes
    the numstat parse ambiguous. NUL/SOH delimiters keep this pass unambiguous.
    """
    raw = git(repo, "log", "--no-merges", "--since", since.isoformat(),
              "--format=%H%x00%s%x00%b%x01")
    bodies = {}
    for record in raw.split("\x01"):
        record = record.strip("\n")
        if not record:
            continue
        parts = record.split("\x00")
        if len(parts) >= 3:
            bodies[parts[0]] = parts[1] + "\n" + parts[2]
    return bodies


def read_commits(repo: Path, since: dt.datetime) -> list[dict]:
    """Non-merge commits with per-path add/delete counts, bots excluded."""
    raw = git(repo, "log", "--no-merges", "--since", since.isoformat(),
              "--format=@@@%H|%aI|%an|%s", "--numstat")
    commits: list[dict] = []
    cur: dict | None = None
    for line in raw.splitlines():
        if line.startswith("@@@"):
            sha, iso, author, subject = line[3:].split("|", 3)
            cur = {
                "sha": sha,
                "when": _parse_instant(iso),
                "author": author, "subject": subject, "files": [],
            }
            if author.endswith("[bot]"):
                cur = None
                continue
            commits.append(cur)
        elif line.strip() and cur is not None:
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            add, dele, path = parts
            if "=>" in path:  # a rename; credit the destination
                path = re.sub(r".*\{.*=> (.*)\}", r"\1", path).replace("//", "/")
            cur["files"].append((
                0 if add == "-" else int(add),
                0 if dele == "-" else int(dele),
                path,
            ))
    commits.sort(key=lambda c: c["when"])
    return commits


def read_ledger(path: Path) -> list[dict]:
    """Parse the governance ledger, skipping unparseable lines loudly."""
    events, corrupt = [], 0
    kind_of = {"review.critic": "critic", "review.pr": "pr", "learning.written": "reflect"}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            corrupt += 1
            continue
        cat = kind_of.get(obj.get("event"))
        if cat is None:
            continue
        review = obj.get("review") or {}
        events.append({
            "when": dt.datetime.fromisoformat(obj["ts"].replace("Z", "+00:00")).astimezone(UTC),
            "cat": cat,
            "mode": (review.get("mode") or "").split(" ")[0],
            # The body of work a review was bought for. Carried because the
            # review round budget bounds a SCOPE rather than a branch, so any
            # question about what that ceiling can reach is asked per scope —
            # and because its absence is meaningful: a scope-less row makes the
            # budget return `unavailable`, which never refuses.
            "scope": obj.get("scope"),
            "duration": obj.get("duration_seconds"),
            # NAMING, because this script already uses "measured" for something
            # else: `critic_hours_measured` below is INTERVAL-measured time,
            # attributed by commit density and biased by it (hazard 2). This is
            # a different and stronger thing — a clock read before the reviewer
            # was spawned and again when its record was appended. Calling both
            # "measured" would collide on a key readers already trust, so this
            # one is "dispatch clock" everywhere it appears.
            "clock_seconds": _dispatch_clock_seconds(obj),
            "severities": collections.Counter(
                f.get("severity", "unlabelled") for f in review.get("findings", [])
            ),
        })
    if corrupt:
        print(f"warning: {corrupt} unparseable ledger line(s) skipped", file=sys.stderr)
    events.sort(key=lambda e: e["when"])
    return events


def _clock_columns(kind: str, total_seconds: float, runs: int) -> dict:
    """The dispatch-clock trio for one window and one review KIND, built
    together so they cannot disagree.

    Keyed by kind rather than hardcoded to ``pr``: both review kinds carry a
    code-read clock now, and a function that can only name one is how the other
    kind's measurement gets accumulated and then silently dropped at render
    time. The prefix is the kind, so a third kind needs no edit here.

    The count is not decoration: 0.3 hours over 2 of a window's 40 reviews is
    not that window's cost, and a figure without its denominator invites exactly
    that reading. With no clocked runs both figures are ``None`` — NOT ZERO,
    which would read as reviews that took no time rather than as a window the
    clock had not reached.
    """
    if not runs:
        return {
            f"{kind}_clock_runs": 0,
            f"{kind}_clock_hours": None,
            f"{kind}_clock_minutes_per_review": None,
        }
    return {
        f"{kind}_clock_runs": runs,
        f"{kind}_clock_hours": round(total_seconds / 3600, 2),
        f"{kind}_clock_minutes_per_review": round(total_seconds / 60 / runs, 1),
    }


def _dispatch_clock_seconds(obj: dict) -> float | None:
    """The interval this event's dispatch mark attests, or ``None``.

    Delegates to the framework's own predicate rather than restating it: the
    plausibility bound, the out-of-order refusal and the not-measured semantics
    are one rule with three readers, and a copy here is a copy that drifts.
    """
    return event_interval_seconds(obj)


def _parse_instant(text: str) -> dt.datetime:
    """Parse an ISO date/instant to UTC. **The one home for this parse.**

    A stated offset is CONVERTED, never overridden: `.replace(tzinfo=UTC)` on an
    already-aware value silently relabels it, which moved a `-06:00` boundary by
    six hours and is most of a short window.

    **`Z` is normalised here because `fromisoformat` only learned it in 3.11.**
    This tool is tested on 3.10, where a `Z`-suffixed stamp raises
    `ValueError: Invalid isoformat string`. Three call sites used to reach
    `fromisoformat` directly and each one was a 3.10 crash the maintainer's 3.11
    machine could not see; they route through here now, which is the point of a
    single home — the version bound is stated once and cannot be forgotten at a
    fourth site.
    """
    parsed = dt.datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def first_ledger_event(product: Path) -> dt.datetime | None:
    """Timestamp of the consumer's earliest governance-ledger event, if any."""
    path = product / ".prawduct" / ".governance-ledger.jsonl"
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ts = json.loads(line)["ts"]
        except (json.JSONDecodeError, KeyError):
            continue
        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(UTC)
    return None


def detect_backfills(events: list[dict]) -> dict[str, dict]:
    """Flag event kinds whose timestamps are too clustered to be a real cadence.

    A kind emitted over under 2% of the corpus span is a one-off migration, and
    every per-window rate derived from it is an artifact of the day it ran.
    """
    if not events:
        return {}
    span = (events[-1]["when"] - events[0]["when"]).total_seconds()
    by_kind: dict[str, list[dt.datetime]] = collections.defaultdict(list)
    for e in events:
        by_kind[e["cat"]].append(e["when"])
    flagged = {}
    for cat, times in by_kind.items():
        if len(times) < 2 or span <= 0:
            continue
        own = (max(times) - min(times)).total_seconds()
        if own / span < 0.02:
            flagged[cat] = {
                "events": len(times),
                "spread_minutes": round(own / 60, 1),
                "on": min(times).date().isoformat(),
            }
    return flagged


def attribute(timeline: list[dict], window_of) -> tuple[dict, dict]:
    """Split session wall clock across phases, and count sessions.

    Each interval inside a session is credited to the category of the event that
    ENDS it. See the module docstring: this is density-biased, and the VALIDATION
    table is what tells you whether to believe it for a given window.
    """
    hours: dict[str, dict[str, float]] = collections.defaultdict(
        lambda: collections.defaultdict(float))
    sessions: collections.Counter = collections.Counter()
    prev = None
    for event in timeline:
        series = window_of(event["when"])
        if series is None:
            prev = event
            continue
        starts_session = (
            prev is None
            or event["when"] - prev["when"] > SESSION_GAP
            or window_of(prev["when"]) != series
        )
        if starts_session:
            sessions[series] += 1
            hours[series][event["cat"]] += SESSION_LEADIN.total_seconds() / 3600
        else:
            hours[series][event["cat"]] += (
                event["when"] - prev["when"]).total_seconds() / 3600
        prev = event
    return hours, sessions


def merged_prs(repo: Path, since: dt.datetime) -> list[dict]:
    """Merged PRs via `gh`. Returns [] (with a note) if gh is unavailable."""
    slug = ""
    for line in git(repo, "remote", "-v").splitlines():
        m = re.search(r"github\.com[:/]([^/\s]+/[^/\s.]+)", line)
        if m:
            slug = m.group(1)
            break
    if not slug:
        print("note: no github remote found; skipping PR cadence", file=sys.stderr)
        return []
    out = []
    for page in range(1, 25):
        proc = subprocess.run(
            ["gh", "api", "-X", "GET", f"repos/{slug}/pulls"
             f"?state=closed&sort=created&direction=desc&per_page=100&page={page}"],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0:
            print(f"note: gh failed ({proc.stderr.strip()[:120]}); "
                  "PR cadence omitted", file=sys.stderr)
            return out
        try:
            batch = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return out
        if not batch:
            break
        for pr in batch:
            if pr.get("merged_at"):
                out.append({"created": pr["created_at"], "merged": pr["merged_at"]})
        if batch[-1]["created_at"][:10] < since.date().isoformat():
            break
    return out


def build_report(product: Path, framework: Path, since: dt.datetime,
                 want_prs: bool, until_override: dt.datetime | None = None) -> dict:
    ledger_path = product / ".prawduct" / ".governance-ledger.jsonl"
    if not ledger_path.is_file():
        sys.exit(f"no governance ledger at {ledger_path} — nothing to measure")

    ledger = read_ledger(ledger_path)
    commits = read_commits(product, since)
    if not commits:
        sys.exit(f"no commits in {product} since {since.date()}")
    bodies = read_commit_bodies(product, since)

    # Tables D and E are derived from conventional-commit prefixes. A repo that
    # does not use them yields 0 fix commits and 0 test commits, which reads as
    # "no bugs, no tests" when it means "not measurable this way". Measure the
    # convention before trusting anything derived from it.
    typed = sum(1 for c in commits if re.match(r"[a-z]+(\(.*?\))?(!)?:", c["subject"]))
    conventional_share = typed / len(commits)
    commit_kinds_usable = conventional_share >= 0.5

    # An explicit --until clips the last window; events past it then fall outside
    # every window and drop out of every count, which is what isolates a
    # sub-window the release tags cannot delimit.
    until = until_override or max(
        commits[-1]["when"], ledger[-1]["when"] if ledger else commits[-1]["when"])
    windows = minor_windows(framework, since, until)
    if not windows:
        sys.exit(f"no prawduct release window overlaps {since.date()}..{until.date()}")
    bounds = [(w["series"], w["start"], w["end"]) for w in windows]

    def window_of(when: dt.datetime) -> str | None:
        for series, start, end in bounds:
            if start <= when < end:
                return series
        return None

    # --- timeline: commits (typed) merged with ledger events ----------------
    timeline: list[dict] = []
    for c in commits:
        m = re.match(r"([a-z]+)(\(.*?\))?(!)?:", c["subject"])
        kind = m.group(1) if m else "(none)"
        cat = "test" if kind in TEST_KINDS else "code" if kind in CODE_KINDS else "records"
        timeline.append({"when": c["when"], "cat": cat})
    timeline.extend(ledger)
    timeline.sort(key=lambda e: e["when"])

    hours, sessions = attribute(timeline, window_of)

    # --- per-window counts ---------------------------------------------------
    lines: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    kinds: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    fixes: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for c in commits:
        series = window_of(c["when"])
        if series is None:
            continue
        m = re.match(r"([a-z]+)(\(.*?\))?(!)?:", c["subject"])
        kind = m.group(1) if m else "(none)"
        kinds[series][kind] += 1
        if kind == "fix":
            fixes[series]["total"] += 1
            # Subject AND body: "fix(audio): the play control was below the fold"
            # names its trigger only in the body, and the body is where a review
            # round is cited. Matching the subject alone undercounts by ~4x.
            if REVIEW_DRIVEN.search(bodies.get(c["sha"], c["subject"])):
                fixes[series]["review_driven"] += 1
        for add, dele, path in c["files"]:
            bucket = classify(path)
            lines[series][f"{bucket}+"] += add
            lines[series][f"{bucket}-"] += dele

    reviews: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    selfreported: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    # The dispatch-clock population, kept APART from the self-reported one
    # rather than preferred over it: pooling the two is the hazard the clock was
    # added to retire, and a window part-measured part-estimated must say so.
    clock: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    clock_runs: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for e in ledger:
        series = window_of(e["when"])
        if series is None or e["cat"] == "reflect":
            continue
        reviews[series][f"{e['cat']}:runs"] += 1
        if e["mode"]:
            reviews[series][f"{e['cat']}:mode:{e['mode']}"] += 1
        for sev, n in e["severities"].items():
            reviews[series][f"{e['cat']}:{sev}"] += n
        selfreported[series][e["cat"]] += e["duration"] or 0
        if e["clock_seconds"] is not None:
            clock[series][e["cat"]] += e["clock_seconds"]
            clock_runs[series][e["cat"]] += 1

    pr_rows: dict[str, list[float]] = collections.defaultdict(list)
    if want_prs:
        for pr in merged_prs(product, since):
            merged = dt.datetime.fromisoformat(pr["merged"].replace("Z", "+00:00"))
            created = dt.datetime.fromisoformat(pr["created"].replace("Z", "+00:00"))
            series = window_of(merged)
            if series:
                pr_rows[series].append((merged - created).total_seconds() / 3600)

    rows = []
    for w in windows:
        s = w["series"]
        days = (w["end"] - w["start"]).total_seconds() / 86400
        measured = dict(hours[s])
        engaged = sum(measured.values())
        ln = lines[s]
        written = sum(ln[f"{k}+"] for k in ("code", "test", "governance", "docs"))
        crit_self = selfreported[s]["critic"] / 3600
        pr_self = selfreported[s]["pr"] / 3600
        n_crit = reviews[s]["critic:runs"]
        crit_findings = sum(reviews[s][f"critic:{k}"] for k in ("blocking", "warning", "note"))
        opens = sorted(pr_rows[s])
        rows.append({
            "series": s,
            "start": w["start"].date().isoformat(),
            "end": w["end"].date().isoformat(),
            "days": round(days, 1),
            "sessions": sessions[s],
            "engaged_hours": round(engaged, 1),
            "hours_per_day": round(engaged / days, 2) if days else 0,
            "lines": {k: ln[k] for k in sorted(ln)},
            "lines_written": written,
            "lines_per_hour": round(written / engaged) if engaged else 0,
            "code_share_pct": round(100 * ln["code+"] / written, 1) if written else 0,
            "commit_kinds": dict(kinds[s]),
            "critic_runs": n_crit,
            "critic_hours_self_reported": round(crit_self, 1),
            "critic_hours_measured": round(measured.get("critic", 0), 1),
            "critic_ratio_measured_over_self": (
                round(measured.get("critic", 0) / crit_self, 2) if crit_self else None),
            "critic_share_pct": round(100 * crit_self / engaged, 1) if engaged else 0,
            "critic_minutes_per_run": round(crit_self * 60 / n_crit, 1) if n_crit else 0,
            # The Critic's dispatch-clock population, reported BESIDE its
            # self-report for the same reason the PR one is: these are two
            # populations and a median over the mixture measures neither.
            # Accumulated since the clock reached `review.critic`; a window
            # older than that reads 0 runs, which is "not measured", not "free".
            **_clock_columns("critic", clock[s]["critic"], clock_runs[s]["critic"]),
            "critic_findings_per_run": round(crit_findings / n_crit, 2) if n_crit else 0,
            "critic_blocking": reviews[s]["critic:blocking"],
            "critic_blocking_per_run": (
                round(reviews[s]["critic:blocking"] / n_crit, 2) if n_crit else 0),
            "critic_blocking_per_1k_code": (
                round(reviews[s]["critic:blocking"] / (ln["code+"] / 1000), 2)
                if ln["code+"] else 0),
            "critic_modes": {k.split(":", 2)[2]: v for k, v in reviews[s].items()
                             if k.startswith("critic:mode:")},
            "pr_runs": reviews[s]["pr:runs"],
            "pr_hours_self_reported": round(pr_self, 1),
            "pr_minutes_per_review": (
                round(pr_self * 60 / reviews[s]["pr:runs"], 1) if reviews[s]["pr:runs"] else 0),
            # The dispatch-clock population for PR reviews, reported BESIDE the
            # self-reported one. `pr_clock_runs` is what makes the pair readable:
            # a clock figure over 2 of 40 reviews is not a window's cost, and
            # without the count nothing says which it is. Zero runs means the
            # clock had not reached this window, never that reviews were free.
            **_clock_columns("pr", clock[s]["pr"], clock_runs[s]["pr"]),
            "pr_blocking": reviews[s]["pr:blocking"],
            "pr_findings": sum(reviews[s][f"pr:{k}"] for k in ("blocking", "warning", "note")),
            # None, not 0, when --prs was not passed: a zero that means "not
            # measured" reads identically to a zero that means "none merged".
            "merged_prs": len(opens) if want_prs else None,
            "pr_median_open_hours": round(opens[len(opens) // 2], 3) if opens else None,
            "fix_commits": fixes[s]["total"],
            "fix_review_driven": fixes[s]["review_driven"],
            "product_bug_fixes": fixes[s]["total"] - fixes[s]["review_driven"],
            "product_bug_fixes_per_1k_code": (
                round((fixes[s]["total"] - fixes[s]["review_driven"]) / (ln["code+"] / 1000), 2)
                if ln["code+"] else 0),
            "test_to_code_ratio": (
                round(ln["test+"] / ln["code+"], 2) if ln["code+"] else 0),
        })

    # Trim LEADING windows with no activity — those predate the consumer being
    # governed, and printing them invites "zero work under v2.2" when the truth
    # is "not onboarded yet". Interior zero windows are kept: a quiet window in
    # the middle of an active range is a real observation.
    while rows and not (rows[0]["engaged_hours"] or rows[0]["critic_runs"]
                        or rows[0]["lines_written"]):
        rows.pop(0)

    return {
        "product": product.resolve().name,
        "framework": framework.resolve().name,
        "generated_at": dt.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "since": since.isoformat(timespec="minutes"),
        "until": until.isoformat(timespec="minutes"),
        "prs_fetched": want_prs,
        "conventional_commit_share": round(conventional_share, 3),
        "commit_kind_metrics_usable": commit_kinds_usable,
        "backfilled_event_kinds": detect_backfills(ledger),
        "windows": rows,
    }


def render(report: dict) -> None:
    rows = report["windows"]
    print(f"# {report['product']} vs {report['framework']} versions\n"
          f"# window {report['since']} -> {report['until']}"
          f"  (generated {report['generated_at']})\n")

    for kind, info in report["backfilled_event_kinds"].items():
        print(f"!! BACKFILL DETECTED: all {info['events']} '{kind}' events span "
              f"{info['spread_minutes']} min on {info['on']}. Any per-window rate "
              f"from this kind is an artifact — do not cite it.\n")

    print("A. EFFORT AND OUTPUT")
    print(f"{'series':7}{'days':>6}{'sess':>6}{'hours':>8}{'h/day':>7}"
          f"{'code+':>9}{'test+':>9}{'gov+':>9}{'lines/h':>9}{'code%':>7}")
    print("-" * 77)
    for r in rows:
        ln = r["lines"]
        print(f"{r['series']:7}{r['days']:6.1f}{r['sessions']:6}{r['engaged_hours']:8.1f}"
              f"{r['hours_per_day']:7.2f}{ln.get('code+', 0):9}{ln.get('test+', 0):9}"
              f"{ln.get('governance+', 0):9}{r['lines_per_hour']:9}{r['code_share_pct']:7.1f}")

    # "self-report" describes the `hours` column only; the clock columns live in
    # VALIDATION, which the header points at.
    print("\nB. CRITIC (hours are the ledger's self-report — clocked time in VALIDATION)")
    print(f"{'series':7}{'runs':>7}{'hours':>8}{'min/run':>9}{'%engaged':>10}"
          f"{'runs/day':>10}{'find/run':>10}{'blk/run':>9}{'blocking':>10}")
    print("-" * 80)
    for r in rows:
        print(f"{r['series']:7}{r['critic_runs']:7}{r['critic_hours_self_reported']:8.1f}"
              f"{r['critic_minutes_per_run']:9.1f}{r['critic_share_pct']:10.1f}"
              f"{r['critic_runs'] / r['days']:10.2f}"
              f"{r['critic_findings_per_run']:10.2f}{r['critic_blocking_per_run']:9.2f}"
              f"{r['critic_blocking']:10}")

    print("\nC. PR LAYER (self-rep hours are the ledger's self-report; clk columns are "
          "the dispatch clock)")
    if not report["prs_fetched"]:
        print("(merged/open columns not measured — re-run with --prs)")
    # The rule is DERIVED from the header, never a second hand-counted copy of
    # the same width: this pair drifted the moment two columns were added, and a
    # number that must be recounted whenever the line above changes is a defect
    # waiting for the next edit rather than a one-off typo.
    header = (f"{'series':7}{'merged':>8}{'reviews':>9}{'self-rep h':>12}{'min/review':>12}"
                                          f"{'clk runs':>10}{'clk min/rev':>13}"
              f"{'findings':>10}{'blocking':>10}{'median open h':>15}")
    print(header)
    print("-" * len(header))
    for r in rows:
        opened = "—" if r["pr_median_open_hours"] is None else f"{r['pr_median_open_hours']:.3f}"
        merged = "—" if r["merged_prs"] is None else str(r["merged_prs"])
        # The clock trio was `--json`-only while this tool's own docstring told
        # readers to "read pr_clock_runs before pr_clock_hours" — advice about a
        # column the default output never printed. The run COUNT leads, because a
        # clock figure over 2 of a window's 40 reviews is not that window's cost,
        # and an em dash (never 0.0) says the clock had not reached this window.
        clk = "—" if r["pr_clock_minutes_per_review"] is None else f"{r['pr_clock_minutes_per_review']:.1f}"
        print(f"{r['series']:7}{merged:>8}{r['pr_runs']:9}"
              f"{r['pr_hours_self_reported']:12.1f}{r['pr_minutes_per_review']:12.1f}"
              f"{r['pr_clock_runs']:10}{clk:>13}"
              f"{r['pr_findings']:10}{r['pr_blocking']:10}{opened:>15}")

    print("\nD. DEFECT SIGNAL")
    if not report["commit_kind_metrics_usable"]:
        print(f"(fix/test commit columns NOT MEASURABLE here — only "
              f"{report['conventional_commit_share']:.0%} of subjects carry a "
              f"conventional-commit prefix. The line counts above are path-derived "
              f"and unaffected; blocking/1k code is ledger-derived and unaffected.)")
    print(f"{'series':7}{'fix cmts':>10}{'review-drv':>12}{'prod-bug':>10}"
          f"{'prod/1k code':>14}{'blocking/1k code':>18}")
    print("-" * 71)
    for r in rows:
        na = not report["commit_kind_metrics_usable"]
        cell = (lambda v, w, f="d": f"{'—':>{w}}" if na else f"{v:>{w}{f}}")
        print(f"{r['series']:7}{cell(r['fix_commits'], 10)}"
              f"{cell(r['fix_review_driven'], 12)}{cell(r['product_bug_fixes'], 10)}"
              f"{cell(r['product_bug_fixes_per_1k_code'], 14, '.2f')}"
              f"{r['critic_blocking_per_1k_code']:18.2f}")

    print("\nE. TESTING")
    print(f"{'series':7}{'test cmts':>11}{'test+ lines':>13}{'test:code':>11}")
    print("-" * 42)
    for r in rows:
        tc = ("—" if not report["commit_kind_metrics_usable"]
              else str(r["commit_kinds"].get("test", 0)))
        print(f"{r['series']:7}{tc:>11}"
              f"{r['lines'].get('test+', 0):13}{r['test_to_code_ratio']:11.2f}")

    print("\nVALIDATION — measured-interval Critic hours over the ledger's self-report.")
    print("Near 1.0: commits are dense enough that interval attribution is sound, and")
    print("the self-report is corroborated. Far above 1.0: the window's measured phase")
    print("split is absorbing coding time into review; cite the self-report instead.")
    print(f"\n{'series':7}{'measured h':>12}{'self-rep h':>12}{'ratio':>8}{'verdict':>26}"
          f"{'clocked':>10}{'clock h':>10}")
    print("-" * 85)
    for r in rows:
        ratio = r["critic_ratio_measured_over_self"]
        if ratio is None:
            verdict = "no self-report"
        elif ratio <= 1.5:
            verdict = "corroborated"
        elif ratio <= 2.5:
            verdict = "weak — prefer self-report"
        else:
            verdict = "density-inflated"
        shown = "n/a" if ratio is None else f"{ratio:.2f}"
        # The last two columns are the CODE-READ clock, not the interval
        # estimate the first two are -- the file's own "two different things
        # called measured" hazard. `clocked` is the denominator: without it a
        # clock figure over 2 of 40 reviews reads as the window's cost.
        runs = r["critic_clock_runs"]
        clock_h = "n/a" if r["critic_clock_hours"] is None else f"{r['critic_clock_hours']:.2f}"
        print(f"{r['series']:7}{r['critic_hours_measured']:12.1f}"
              f"{r['critic_hours_self_reported']:12.1f}{shown:>8}{verdict:>26}"
              f"{runs:>10}{clock_h:>10}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure a consumer repo's build economics across prawduct versions.")
    parser.add_argument("product", type=Path,
                        help="path to the governed consumer repo")
    parser.add_argument("--framework", type=Path, default=Path(__file__).resolve().parent.parent,
                        help="path to the prawduct repo whose tags define the windows")
    parser.add_argument("--since", default=None,
                        help="ISO date to start from (default: the consumer's plugin-migration "
                             "commit, else its first prawduct ledger event)")
    parser.add_argument("--until", default=None,
                        help="ISO instant to stop at (default: now). With --since, isolates an "
                             "arbitrary sub-window — which is how you measure a version the tags "
                             "cannot delimit, such as an unreleased dev build. See --marker.")
    parser.add_argument("--marker", action="store_true",
                        help="print the consumer's last-seen plugin version and the instant it "
                             "changed, then exit. The banner rewrites the marker only when the "
                             "version DIFFERS, so its mtime dates that transition.")
    parser.add_argument("--prs", action="store_true",
                        help="also fetch merged-PR cadence via gh (slower, needs auth)")
    parser.add_argument("--json", action="store_true", help="emit the full report as JSON")
    parser.add_argument("--show-classification", action="store_true",
                        help="print how each changed path was bucketed, then exit")
    args = parser.parse_args()

    product = args.product.resolve()
    if not (product / ".git").exists():
        sys.exit(f"{product} is not a git repo")

    if args.marker:
        marker = product / ".prawduct" / ".prawduct-version"
        if not marker.is_file():
            print(f"{product.name}: no version marker (never ran the plugin banner here)")
            return 0
        changed = dt.datetime.fromtimestamp(marker.stat().st_mtime).astimezone()
        print(f"{product.name}: last-seen plugin version "
              f"{marker.read_text(encoding='utf-8').strip()}, "
              f"which it first saw at {changed.isoformat(timespec='seconds')}")
        print("  (mtime dates the TRANSITION, not the last session: the banner returns "
              "early without writing when the version is unchanged.)")
        return 0

    if args.since:
        since = _parse_instant(args.since)
    else:
        # The plugin migration is the natural floor: before it the consumer ran
        # file-synced framework files and the ledger does not exist.
        iso = git(product, "log", "--diff-filter=M", "--format=%aI", "-1",
                  "--grep=migrate to plugin distribution", "--", ".claude/settings.json").strip()
        if iso:
            since = _parse_instant(iso)
        else:
            # No migration commit (repo onboarded straight onto the plugin, or
            # the commit was worded differently). The first ledger event is the
            # honest floor — earlier windows are not "zero activity", they are
            # "not governed yet", and emitting them invites the first reading.
            since = first_ledger_event(product) or dt.datetime(2026, 1, 1, tzinfo=UTC)

    if args.show_classification:
        seen: dict[str, str] = {}
        for c in read_commits(product, since):
            for _a, _d, path in c["files"]:
                seen.setdefault(path, classify(path))
        for bucket in ("code", "test", "governance", "docs", "generated"):
            paths = sorted(p for p, b in seen.items() if b == bucket)
            print(f"\n{bucket} ({len(paths)} paths)")
            for p in paths[:15]:
                print(f"  {p}")
            if len(paths) > 15:
                print(f"  ... and {len(paths) - 15} more")
        return 0

    until = _parse_instant(args.until) if args.until else None
    report = build_report(product, args.framework.resolve(), since, args.prs, until)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        render(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
