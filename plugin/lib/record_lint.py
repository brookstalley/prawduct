"""Deterministic record-lint — the checks a reviewer should never re-derive.

On 2026-07-29, 57% of the day's Critic findings targeted hand-authored
governance *records* rather than shipped behavior: a dangling ``file:line``
citation, a backlog id that no longer exists, a ``governed_by:`` block that
disposed of one of an artifact's three norms, a test-count claim corrected three
times. Each correction is a commit, each commit extends HEAD, and that is how a
record defect buys a review round.

None of those need judgment. This module answers them in code, at dispatch
time, and :func:`lint_records` results ride the Critic's dispatch manifest so
the review protocol can tell reviewers the answers are already known.

**Advice, not authority.** Findings here are advisory: they enter the manifest
for the builder to fix or disposition, and they never gate. What they must never
do is *silently pass* — a check that cannot read its inputs reports itself
``unchecked`` with a reason (the same posture the per-language dispatch norm
requires of the compliance canary), because an unrun check and a clean one are
otherwise indistinguishable at the output.

**Cost is proportional to the diff, never the repo.** Consumers are ~20x this
repo's size, so every line-scoped check reads only the lines a change *added*
(``git diff --unified=0``) rather than re-scanning whole files. That is also why
the tripwire below does not drown in history: ``.prawduct/change-log.md`` holds
years of suite-total claims, and linting the added lines of a changed record
sees only the entry just written.

**Yield is observable** (``nonfunctional-requirements.md`` § Direction —
proportionality ratchets both ways; a control born after 2026-07-29 emits its
yield at birth). This control does not print-and-forget: its per-check counts
land in the dispatch manifest, and ``critic_consolidate`` carries them into the
review **fact**, so "how often did record-lint fire, and on what" is a query
over the evidence store rather than an argument. The yield *query* is the
janitor's Norm Health sweep, deliberately not here.

**Records are markdown.** A record is a ``.md`` file — prose is where
hand-authored claims live, and classifying by suffix keeps this language-neutral
(``architecture.md`` § Direction: Python-implemented, never Python-specific).
Archived history is excluded: it is not being asserted any more.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import buildplan_refs, evidence, gitstate
from .core import read_str_yaml_key, resolve_build_plan_path

#: Every check this module can run, in manifest order. Named so a consumer can
#: tell "ran and found nothing" from "never ran" (see ``unchecked`` below).
CHECKS = (
    "chunk-ref-missing",
    "dangling-ref",
    "unknown-backlog-id",
    "governed-by-gap",
    "suite-total-claim",
)

#: History, not live assertion — an archived record is excluded from every check.
_ARCHIVE_MARKERS = ("/archive/", "archive/")

#: Backticked-token extraction, reduction, and path judgment are ALL borrowed
#: from the build-plan ref parser rather than restated, so every carveout it has
#: earned applies here too: no whitespace inside the span (which is what keeps a
#: backticked command — ``python -m pytest tests/ -q`` — and the backlog's
#: ``·``-separated metadata bars from reading as paths), plus globs, URLs, git
#: refs, angle-bracket placeholders, anchors and ``path:line`` suffixes.
#: Measured against the real repo before it was borrowed: a locally-defined
#: "anything between backticks" pattern produced 46 findings on this branch, 44
#: of them prose. One grammar, one home.
_BACKTICKED_RE = buildplan_refs._BUILD_PLAN_PATH_RE
_NEW_QUALIFIER_RE = buildplan_refs._BUILD_PLAN_NEW_QUALIFIER_RE

#: An id-shaped token. The generator's documented format is ``PFX-XXXX`` with a
#: 4-char base36 suffix (``templates/backlog.md``), and requiring the suffix to
#: mix letters and digits is what keeps ``ISO-8601``, ``RFC-7807`` and the
#: template's own ``ABC-1234`` placeholder out of the results. That is stricter
#: than the documented format allows in principle: an all-letter or all-digit
#: suffix is legal and would be missed here. It is the right direction for an
#: advisory check — all 342 ids in this repo's backlog satisfy it, a missed
#: dangling id costs one silent advisory, and a false positive costs noise on
#: every review, which is the ceremony ratchet this whole plan exists to reverse.
_BACKLOG_ID_RE = re.compile(r"(?<![\w-])([A-Z]{2,4})-(?=[A-Z0-9]{4}(?![\w-]))([A-Z0-9]{4})")

#: A suite-total test claim in durable prose — the subtraction's tripwire. The
#: evidence store already records pass/fail per tree (``test-evidence record``),
#: so a number here is a hand-maintained copy of a machine-held fact, and it
#: drifts. Deliberately narrow: 3+ digits, or an explicit "full suite"/"total"
#: framing. A two-digit count is nearly always a scoped or delta count
#: (``+14 tests``, ``28 tests``), which is a different claim and not this one's
#: business. A leading ``+``/``-``/``.``/``/`` blocks the first arm so a delta or
#: a version fragment never reads as a total.
_SUITE_TOTAL_RE = re.compile(
    r"(?<![\w.+/-])\d{3,6}\s*(?:tests?|passing|green|pass(?:ed|es|ing)?)\b"
    r"|(?:full suite|suite total|whole suite|total(?:ling)?)\W{0,16}\d{2,6}",
    re.IGNORECASE,
)

# --- YAML frontmatter `governed_by:` shape (line-based; this codebase carries no
# YAML dependency — `core.read_str_yaml_key` is the same posture). ------------
_FRONTMATTER_FENCE = "---"
_GOVERNED_BY_RE = re.compile(r"^governed_by:\s*$")
_TOP_LEVEL_KEY_RE = re.compile(r"^[A-Za-z_][\w-]*:")
_ARTIFACT_ENTRY_RE = re.compile(r"^(\s*)-\s+artifact:\s*(\S+)\s*$")
_DISPOSITIONS_KEY_RE = re.compile(r"^(\s*)dispositions:\s*$")
_LIST_ITEM_RE = re.compile(r"^(\s*)-\s+\S")

#: A markdown heading, level + text. Local rather than imported: ``norm_probes``
#: owns the same grammar but answers a different question (every logical *line*
#: inside a Direction section, for its ``Why:``/``Status:`` scans) and pulls in
#: the advisory-store, backlog and coverage-probe stack, which is far too heavy
#: for the ``critic-begin`` dispatch path. If the grammar ever changes, both
#: matchers change — they are the same six characters of markdown.
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")

#: A build plan by filename. The `governed_by:` check reads plans only.
_BUILD_PLAN_RE = re.compile(r"(^|/)build-plan[^/]*\.md$")


# ---------------------------------------------------------------------------
# Record classification
# ---------------------------------------------------------------------------


def is_record(path: str) -> bool:
    """True when ``path`` is a governance record this module lints.

    Markdown, and not archived. Suffix-only by design: no content is read to
    decide, and no language is classified.
    """
    if not path.endswith(".md"):
        return False
    return not any(marker in f"/{path}" for marker in _ARCHIVE_MARKERS)


def records_in(paths: "list[str] | None") -> list[str]:
    """The record subset of ``paths`` (order preserved, None-safe)."""
    return [p for p in (paths or []) if is_record(p)]


# ---------------------------------------------------------------------------
# Added-line extraction — the cost boundary
# ---------------------------------------------------------------------------


def _added_lines(
    project_dir: Path, base_tree: str, head_tree: str, path: str
) -> "list[tuple[int, str]] | None":
    """``[(line_num, text), ...]`` for lines ``path`` ADDED between two trees.

    ``None`` when the diff cannot be computed — the caller reports the check
    ``unchecked`` rather than treating an unreadable diff as an empty one.
    ``--unified=0`` means no context lines, so every ``+`` line in the output is
    genuinely added and the hunk header carries its new-file line number.
    """
    rc, out, _err = evidence.run_git(
        project_dir,
        "diff",
        "--unified=0",
        "--no-color",
        "--no-ext-diff",
        base_tree,
        head_tree,
        "--",
        path,
    )
    if rc != 0:
        return None
    added: list[tuple[int, str]] = []
    line_num = 0
    for raw in out.splitlines():
        if raw.startswith("@@"):
            # @@ -a,b +c,d @@ — `c` is the first new-file line of the hunk.
            head = raw.split("@@")[1] if "@@" in raw[2:] else ""
            plus = [tok for tok in head.split() if tok.startswith("+")]
            if not plus:
                continue
            start = plus[0][1:].split(",")[0]
            line_num = int(start) if start.isdigit() else 0
            continue
        if raw.startswith("+++") or raw.startswith("---"):
            continue
        if raw.startswith("+"):
            added.append((line_num, raw[1:]))
            line_num += 1
    return added


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def _finding(check: str, path: str, line: "int | None", detail: str) -> dict:
    return {"check": check, "path": path, "line": line, "detail": detail}


def _forward_refs(added: "list[tuple[int, str]]", whole_file: "str | None") -> set[str]:
    """Paths declared with the ``new `path`` qualifier — a file the record says
    is being created, not one it claims already exists.

    Collected over the whole file for a build plan (a chunk declares ``new`` on
    its Deliverables line and names the same path again in a Done-when step,
    often outside the added set) and over the added lines otherwise. Same
    exemption ``_parse_build_plan_chunk_refs`` applies, for the same reason.
    """
    sources = [text for _, text in added]
    if whole_file is not None:
        sources = whole_file.splitlines()
    return {
        buildplan_refs._ref_path_part(m.group(1))
        for line in sources
        for m in _NEW_QUALIFIER_RE.finditer(line)
    }


def _check_dangling_refs(
    project_dir: Path,
    path: str,
    added: "list[tuple[int, str]]",
    ref_root: "Path | None",
    exempt: "set[str]",
) -> list[dict]:
    """Backticked file / ``file:line`` citations on added lines that resolve
    nowhere. Resolution rules are ``buildplan_refs``' — repo root, the repo's
    declared second ref root, and an intentionally-gitignored managed path all
    count as resolved.

    ``exempt`` holds paths another check already owns: a ``new `path``
    forward declaration, and anything ``chunk-ref-missing`` has reported."""
    findings: list[dict] = []
    seen: set[str] = set()
    for line_num, text in added:
        for match in _BACKTICKED_RE.finditer(text):
            ref = buildplan_refs._ref_path_part(match.group(1).strip())
            if not buildplan_refs._looks_like_file_path(ref):
                continue
            if ref in seen or ref in exempt:
                continue
            if (project_dir / ref).exists():
                seen.add(ref)
                continue
            if ref_root is not None and (ref_root / ref).exists():
                seen.add(ref)
                continue
            if gitstate.git_path_is_ignored(project_dir, ref):
                seen.add(ref)
                continue
            seen.add(ref)
            findings.append(
                _finding("dangling-ref", path, line_num, f"`{ref}` does not exist")
            )
    return findings


def _check_backlog_ids(
    path: str, added: "list[tuple[int, str]]", known_ids: "set[str]"
) -> list[dict]:
    """Backlog ids cited on added lines that the authoritative backlog does not
    contain. Only called when the backlog is readable — routing lives in
    :func:`_backlog_ids`."""
    findings: list[dict] = []
    seen: set[str] = set()
    for line_num, text in added:
        for match in _BACKLOG_ID_RE.finditer(text):
            prefix, suffix = match.group(1), match.group(2)
            if suffix.isalpha() or suffix.isdigit():
                continue  # not this generator's shape — see _BACKLOG_ID_RE
            item_id = f"{prefix}-{suffix}"
            if item_id in known_ids or item_id in seen:
                continue
            seen.add(item_id)
            findings.append(
                _finding(
                    "unknown-backlog-id",
                    path,
                    line_num,
                    f"{item_id} is not in the backlog",
                )
            )
    return findings


def _check_suite_totals(path: str, added: "list[tuple[int, str]]") -> list[dict]:
    """Suite-total test claims on added lines — the subtraction's tripwire.

    The claim is not wrong, it is *unmaintainable*: the number is true the day
    it is written and drifts the next, and nothing consumes it, because the
    evidence store records pass/fail per tree.
    """
    findings: list[dict] = []
    for line_num, text in added:
        match = _SUITE_TOTAL_RE.search(text)
        if match is None:
            continue
        findings.append(
            _finding(
                "suite-total-claim",
                path,
                line_num,
                f"suite-total test claim {match.group(0).strip()!r} — the evidence "
                "store records pass/fail per tree; a prose copy drifts and nothing "
                "reads it",
            )
        )
    return findings


def _read_text(path: Path) -> "str | None":
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def direction_norm_count(text: str) -> "int | None":
    """Number of norm entries in a document's ``## Direction`` section, or
    ``None`` when it has no such section.

    A norm is a top-level list bullet directly inside the section; its
    ``Why:``/``Status:``/amendment lines are indented continuations and are not
    counted. The section opens at a heading whose text is exactly ``Direction``
    and closes at the next heading of equal-or-higher level, so prose that
    merely mentions ``## Direction`` never opens one.
    """
    in_section = False
    section_level = 0
    count: "int | None" = None
    for line in text.splitlines():
        heading = _HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            if heading.group(2).strip() == "Direction":
                in_section, section_level = True, level
                count = 0 if count is None else count
            elif in_section and level <= section_level:
                in_section = False
            continue
        if in_section and re.match(r"^[-*]\s+\S", line):
            count = (count or 0) + 1
    return count


def _parse_governed_by(text: str) -> list[dict]:
    """``[{"artifact", "dispositions", "line"}]`` from a plan's frontmatter.

    Line-based: this codebase carries no YAML dependency, and the block's shape
    is fixed by the build-plan template. A disposition is a list item nested
    under ``dispositions:``; a soft-wrapped continuation does not start with
    ``- `` and so is not miscounted.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_FENCE:
        return []
    entries: list[dict] = []
    in_block = False
    entry_indent = -1
    disp_indent = -1
    for idx, line in enumerate(lines[1:], start=2):
        if line.strip() == _FRONTMATTER_FENCE:
            break
        if not in_block:
            if _GOVERNED_BY_RE.match(line):
                in_block = True
            continue
        if _TOP_LEVEL_KEY_RE.match(line):
            break  # a new top-level key closes the block
        artifact = _ARTIFACT_ENTRY_RE.match(line)
        if artifact:
            entry_indent = len(artifact.group(1))
            disp_indent = -1
            entries.append(
                {"artifact": artifact.group(2), "dispositions": 0, "line": idx}
            )
            continue
        if not entries:
            continue
        key = _DISPOSITIONS_KEY_RE.match(line)
        if key and len(key.group(1)) > entry_indent:
            disp_indent = len(key.group(1))
            continue
        item = _LIST_ITEM_RE.match(line)
        if item and disp_indent >= 0 and len(item.group(1)) > disp_indent:
            entries[-1]["dispositions"] += 1
    return entries


def _check_governed_by(prawduct_dir: Path, plan_rel: str, text: str) -> list[dict]:
    """A plan's ``governed_by:`` block against each cited artifact's actual
    ``## Direction`` norm count — the GOV-8C3W mechanical enumeration.

    Fires only on **under**-disposition. Disposing of more entries than the
    artifact has norms is legitimate (a plan may split a norm's limbs); leaving
    a norm unaddressed is the defect, and "inapplicable, because —" is a
    perfectly good disposition, so there is never a reason to be short.
    """
    findings: list[dict] = []
    for entry in _parse_governed_by(text):
        artifact = entry["artifact"]
        artifact_text = _read_text(prawduct_dir / "artifacts" / f"{artifact}.md")
        if artifact_text is None:
            continue  # a citation to a nonexistent artifact is dangling-ref's job
        norms = direction_norm_count(artifact_text)
        if not norms:
            continue  # no ratified norms to dispose of
        if entry["dispositions"] < norms:
            findings.append(
                _finding(
                    "governed-by-gap",
                    plan_rel,
                    entry["line"],
                    f"{artifact} carries {norms} `## Direction` norm(s) but this "
                    f"plan disposes of {entry['dispositions']} — each norm needs a "
                    "recorded disposition, and \"inapplicable, because —\" is one",
                )
            )
    return findings


def _check_chunk_refs(
    project_dir: Path, prawduct_dir: Path
) -> "tuple[list[dict], str | None, set[str]]":
    """The current chunk's declared deliverables, existence-checked.

    Delegates wholly to ``buildplan_refs`` — the same parse and the same
    resolution ``verify-chunk-refs`` performs, computed here so it rides the
    manifest instead of being an instruction a reviewer executes. A plan or
    chunk section that cannot be located is the ``cannot-verify:`` case and
    returns an ``unchecked`` reason, never an empty pass.

    Unlike the line-scoped checks this reads the *current chunk* regardless of
    whether the plan changed: a chunk's deliverables must exist by the time its
    review runs, whether or not the plan file moved in the same diff.

    The third return value is the set of missing paths, so the line-scoped
    ``dangling-ref`` check can stay quiet about them. Adding a chunk section
    otherwise reports one absent file twice — once as a deliverable and once as
    a citation — and a control that double-counts is the one nobody trusts.
    """
    chunk_id = buildplan_refs._current_chunk_id_from_status(project_dir)
    if chunk_id is None:
        return [], None, set()  # no current chunk — nothing declared to check
    refs = buildplan_refs._parse_build_plan_chunk_refs(prawduct_dir, chunk_id)
    if refs["error"]:
        return [], (
            f"chunk-ref-missing unchecked — {refs['error']}; the chunk's "
            "deliverable check did not run"
        ), set()
    missing = buildplan_refs._verify_chunk_refs(project_dir, refs)
    findings = [
        _finding(
            "chunk-ref-missing",
            f"chunk {chunk_id}",
            entry.get("line_num"),
            f"declared deliverable `{entry['ref']}` {entry['reason']}",
        )
        for entry in missing
    ]
    return findings, None, {entry["ref"] for entry in missing}


def _backlog_ids(prawduct_dir: Path) -> "tuple[set[str] | None, str | None]":
    """``(ids, unchecked_reason)`` for the authoritative backlog.

    Routes on ``backlog_service_repo`` (``data-model.md`` § Direction). On the
    Issues backend ``.prawduct/backlog.md`` is frozen history — every item
    archived at cutover still parses as present, so an existence check against
    it would pass and dangle with equal confidence. Stating the gap is
    recoverable; a confident wrong answer is not.
    """
    service = read_str_yaml_key(prawduct_dir / "project-state.yaml", "backlog_service_repo")
    if service:
        return None, (
            f"backlog ids unchecked — this repo's live backlog is GitHub Issues "
            f"({service}) and .prawduct/backlog.md is frozen history, which would "
            "resolve every id with equal confidence"
        )
    text = _read_text(prawduct_dir / "backlog.md")
    if text is None:
        return None, "backlog ids unchecked — .prawduct/backlog.md is missing or unreadable"
    ids: set[str] = set()
    for match in _BACKLOG_ID_RE.finditer(text):
        ids.add(f"{match.group(1)}-{match.group(2)}")
    if not ids:
        return None, "backlog ids unchecked — .prawduct/backlog.md contains no item ids"
    return ids, None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def lint_records(
    project_dir: Path,
    prawduct_dir: Path,
    paths: "list[str] | None",
    base_tree: str,
    head_tree: str,
) -> dict:
    """Run every check over the record subset of ``paths``.

    Returns ``{"records": [...], "findings": [...], "unchecked": [...],
    "counts": {check: n}}``. ``findings`` is advisory — it never gates.
    ``unchecked`` names each check that could not run and why, so an unrun
    check is never mistaken for a clean one.
    """
    records = records_in(paths)
    findings: list[dict] = []
    unchecked: list[str] = []

    # Chunk deliverables are checked whether or not a RECORD changed — a
    # code-only diff still has a current chunk whose declared outputs must
    # exist by review time.
    chunk_findings, chunk_gap, chunk_missing = _check_chunk_refs(project_dir, prawduct_dir)
    findings.extend(chunk_findings)
    if chunk_gap:
        unchecked.append(chunk_gap)

    if not records:
        return {
            "records": [],
            "findings": findings,
            "unchecked": unchecked,
            "counts": _count(findings),
        }

    ref_root = buildplan_refs._ref_root(project_dir)
    known_ids, backlog_gap = _backlog_ids(prawduct_dir)
    if backlog_gap:
        unchecked.append(backlog_gap)

    undiffable: list[str] = []
    for rel in records:
        added = _added_lines(project_dir, base_tree, head_tree, rel)
        if added is None:
            undiffable.append(rel)
            continue
        whole = _read_text(project_dir / rel) if _BUILD_PLAN_RE.search(rel) else None
        findings.extend(
            _check_dangling_refs(
                project_dir,
                rel,
                added,
                ref_root,
                _forward_refs(added, whole) | chunk_missing,
            )
        )
        findings.extend(_check_suite_totals(rel, added))
        if known_ids is not None:
            findings.extend(_check_backlog_ids(rel, added, known_ids))
    if undiffable:
        unchecked.append(
            "line-scoped checks unchecked on "
            f"{', '.join(sorted(undiffable))} — git could not diff "
            f"{base_tree[:12]}..{head_tree[:12]} for those paths"
        )

    for rel in _plans_to_check(prawduct_dir, records):
        text = _read_text(project_dir / rel)
        if text is None:
            unchecked.append(f"governed-by-gap unchecked on {rel} — unreadable")
            continue
        findings.extend(_check_governed_by(prawduct_dir, rel, text))

    return {
        "records": records,
        "findings": findings,
        "unchecked": unchecked,
        "counts": _count(findings),
    }


def _count(findings: list[dict]) -> dict:
    """Per-check tallies with every check present, so a zero is visibly a zero
    rather than a missing key a consumer has to interpret."""
    counts = {check: 0 for check in CHECKS}
    for finding in findings:
        counts[finding["check"]] = counts.get(finding["check"], 0) + 1
    return counts


def _plans_to_check(prawduct_dir: Path, records: list[str]) -> list[str]:
    """Which build plans get the ``governed_by:`` enumeration this run.

    Every changed plan, plus — when a *governing artifact* changed — the active
    plan, because adding a norm to an artifact silently shortens the
    disposition block of a plan that did not itself change. That is the GOV-8C3W
    class rather than its instance, and it costs one extra file read.
    """
    plans = [rel for rel in records if _BUILD_PLAN_RE.search(rel)]
    governing_changed = any(
        rel.startswith(".prawduct/artifacts/") and not _BUILD_PLAN_RE.search(rel)
        for rel in records
    )
    if governing_changed:
        active = resolve_build_plan_path(prawduct_dir)
        try:
            rel_active = str(active.relative_to(prawduct_dir.parent))
        except ValueError:
            rel_active = ""
        if rel_active and active.is_file() and rel_active not in plans:
            plans.append(rel_active)
    return plans


def format_findings(result: dict) -> list[str]:
    """Human-readable lines for the CLI and the manifest's reader. One line per
    finding, then one per unchecked reason — an unrun check is reported, never
    silently absent."""
    out: list[str] = []
    for finding in result.get("findings") or []:
        where = finding["path"]
        if finding.get("line"):
            where = f"{where}:{finding['line']}"
        out.append(f"{finding['check']}: {where}: {finding['detail']}")
    for reason in result.get("unchecked") or []:
        out.append(f"unchecked: {reason}")
    return out
