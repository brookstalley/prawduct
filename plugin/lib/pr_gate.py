"""The PR gate's code-answered checks: ``check-pr-hygiene`` and ``check-pr-body``.

The `/prawduct:pr` flow opens a PR on composed Critic coverage, and these two
read-only commands answer the few things about a PR that code can answer:

* ``check-pr-hygiene`` — over merge-base…HEAD of the checked-out branch, the
  base taken from the one resolver ``resolve-base`` uses. Each result has a
  name and a severity; a result whose subject could not be read says
  ``unchecked`` with its reason and never reads as clean.
* ``check-pr-body`` — whether a drafted PR description follows the repo's own
  PR template: every heading and every checklist item of the template present
  in the body. With no body it prints what the description must follow.

**Exit codes** (`api-contract.md` § Error Model): 0 when nothing refuses, 1 when
something does, 3 when the command could not answer at all, 2 on a usage error.
A refusal is recorded as a ``guard-refusal`` fact (``evidence.append_guard_refusal``)
so the yield of each control is a query, not a memory; a polled re-check of the
same unchanged subject records the same event, not a second one.

**Failure posture.** The refusing results are authority and fail closed; the
warnings and information are advice and fail soft — but never silent: a check
that raised is reported as ``unchecked`` with the error, in the command's own
output.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REFUSE = "refuse"
WARNING = "warning"
INFO = "information"

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2
EXIT_UNANSWERED = 3

#: The ``guard`` each command's refusals are recorded under — the grouping key
#: of ``prawduct-hook evidence list --kind guard-refusal``.
BODY_GUARD = "pr-body-template"

HYGIENE_GUARD = "pr-hygiene"

#: The waiver a line carries to say its credential shape is deliberate
#: (`docs/waivers.md`): on the line itself or the line above it.
CREDENTIAL_WAIVER = "prawduct/credential-shape"

#: What each result means, in the words the output leads with.
RESULT_MEANINGS = {
    "credential-shape": (
        "lines this branch adds that match the credential denylist, by file, line and "
        f"shape (the text is never printed); a deliberate one carries `prawduct:allow "
        f"{CREDENTIAL_WAIVER} -- <reason>`"
    ),
    "closes-unresolved": "ids in this branch's change-record `closes:` list the backlog does not resolve",
    "closes-still-open": "ids this branch's change record closes that the branch's own backlog still has open",
    "close-owed-at-merge": "ids the PR description must carry a closing line for, so the merge closes them",
    "chunks-open": "the bound build plan's chunks still open",
    "review-tree-changed": (
        "reviews this branch's coverage rests on that were consolidated over a tree "
        "that changed after dispatch, on the builder's word — name each in the PR description"
    ),
}


@dataclass
class Result:
    """One named result. ``items`` are what it found; ``unchecked`` says why
    some or all of its subject could not be read (both may be set: a partial
    answer is reported as partial)."""

    name: str
    severity: str
    items: list[str] = field(default_factory=list)
    unchecked: str | None = None

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "severity": self.severity,
            "items": list(self.items),
            "unchecked": self.unchecked,
        }


@dataclass
class HygieneReport:
    """``error`` set means the command could not answer at all (exit 3)."""

    base: str | None = None
    merge_base: str | None = None
    head: str | None = None
    checked: list[str] = field(default_factory=list)
    results: list[Result] = field(default_factory=list)
    error: str | None = None


def _git(project_dir: Path, *args: str) -> tuple[int, str]:
    from . import gitstate  # noqa: PLC0415 — lazy; the shared read-only runner

    return gitstate._run_git_text(project_dir, *args)


def _attributed(name: str, severity: str, what: str, exc: BaseException) -> Result:
    return Result(name, severity, unchecked=f"{what} raised {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# check-pr-hygiene — credential shapes on the lines this branch adds
# ---------------------------------------------------------------------------


def _credential_shape(project_dir: Path, merge_base: str) -> list[Result]:
    """Refuse an added line matching the plugin's one credential denylist
    (``backlog.transport.credential_shape``), unless it carries the waiver.

    Only lines the branch ADDS in merge-base…HEAD: a credential already on the
    base is not this PR's to answer for. The finding names file, line and the
    shape's class — never the matched text, which would put the secret in the
    PR flow's own output. The waiver follows `docs/waivers.md`'s placement: the
    line itself or the one above it, read from HEAD when that one predates the
    branch.
    """
    from . import record_lint, waivers  # noqa: PLC0415
    from .backlog import transport  # noqa: PLC0415

    added = record_lint._added_lines(project_dir, merge_base, "HEAD", [])
    if added is None:
        return [Result(
            "credential-shape", REFUSE,
            unchecked=f"the diff {merge_base[:8]}..HEAD could not be read",
        )]
    findings: list[str] = []
    for path, lines in sorted(added.items()):
        head_lines: list[str] | None = None
        for number, text in lines:
            shape = transport.credential_shape(text)
            if shape is None or waivers.line_waives(text, CREDENTIAL_WAIVER):
                continue
            if number > 1:
                if head_lines is None:
                    code, content = _git(project_dir, "show", f"HEAD:{path}")
                    head_lines = content.splitlines() if code == 0 else []
                if len(head_lines) >= number - 1 and waivers.line_waives(head_lines[number - 2], CREDENTIAL_WAIVER):
                    continue
            findings.append(f"{path}:{number}: {shape}")
    return [Result("credential-shape", REFUSE, findings)] if findings else []


# ---------------------------------------------------------------------------
# check-pr-hygiene — the closure check
# ---------------------------------------------------------------------------


def _closure(project_dir: Path, base: str, merge_base: str) -> list[Result]:
    """The change record's ``closes:`` ids against the backlog that is live.

    Read through ``change_fragments.branch_change_record`` — the one owner of
    "what change record did this branch add" — so a trunk branch that cut its
    own fragment is read through the archive entry it added instead.
    Routed by ``backlog_service_repo`` (``backlog_probes.post_cutover``): once
    set, the markdown file is frozen history and only the local cache answers.
    """
    from . import change_fragments  # noqa: PLC0415 — lazy, like every reader here

    record = change_fragments.branch_change_record(project_dir, base)
    if record.error is not None:
        return [Result(
            "closes-unresolved", WARNING,
            unchecked=f"the branch's change records could not be read ({record.error})",
        )]
    ids: list[str] = []
    for change in record.changes:
        ids.extend(i for i in change.closes if i not in ids)
    if not record.changes:
        legacy = _legacy_log_touched(project_dir, merge_base)
        if legacy:
            return [Result("closes-unresolved", WARNING, unchecked=legacy)]
    if not ids:
        return []

    from . import advisory_store, backlog_probes  # noqa: PLC0415

    try:
        state = advisory_store.load_project_state(project_dir)
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- unreadable state must not read as reconciled; reported as unchecked
        return [_attributed("closes-unresolved", WARNING, "reading project-state.yaml", exc)]
    if backlog_probes.post_cutover(state):
        return _closure_issues(project_dir, str(state.get("backlog_service_repo")), ids)
    return _closure_markdown(project_dir, ids)


def _legacy_log_touched(project_dir: Path, merge_base: str) -> str | None:
    """A reason when the branch records its change only in the single-file
    log, whose ``closes`` this check does not read; else ``None``."""
    from . import change_log  # noqa: PLC0415

    code, out = _git(project_dir, "diff", "--name-only", f"{merge_base}..HEAD", "--", change_log.CHANGE_LOG_REL_PATH)
    if code == 0 and out.strip():
        return (
            f"this branch records its change in {change_log.CHANGE_LOG_REL_PATH}, whose closures "
            "this check does not read — move it to a change fragment "
            "(`prawduct-hook migrate-change-log`) or reconcile its closes by hand"
        )
    return None


def _closure_issues(project_dir: Path, scope: str, ids: list[str]) -> list[Result]:
    """Issues backend: each id through the local cache (``cachequery.resolve``),
    never the network. An open item is owed at merge — GitHub closes it from
    the PR description's closing line — rather than a contradiction."""
    from datetime import datetime, timezone  # noqa: PLC0415

    from .backlog import cachequery  # noqa: PLC0415

    now = datetime.now(timezone.utc)
    default_owner = scope.split("/", 1)[0] if "/" in scope else None
    unresolved: list[str] = []
    owed: list[str] = []
    failures: list[str] = []
    for item_id in ids:
        try:
            envelope = cachequery.resolve(
                project_dir, scope=scope, id_raw=item_id, now=now, default_owner=default_owner
            )
        except Exception as exc:  # prawduct:allow prawduct/broad-except -- one id's failure must not hide the others; named in the output
            failures.append(f"{item_id} ({type(exc).__name__}: {exc})")
            continue
        # `resolve` REPORTS a failed lookup in its envelope rather than raising,
        # and an error envelope read as a result would fabricate an unresolved id.
        if not isinstance(envelope, dict) or envelope.get("status") != "ok":
            err = (envelope or {}).get("error") if isinstance(envelope, dict) else None
            failures.append(f"{item_id} ({(err or {}).get('message') or (err or {}).get('code') or 'unknown error'})")
            continue
        data = envelope.get("data") or {}
        if not data.get("resolved"):
            reason = data.get("reason")
            unresolved.append(f"{item_id}" + (f" [{reason}]" if reason else ""))
        elif not data.get("dead"):
            title = data.get("title")
            # A title is data, quoted, never an instruction.
            owed.append(f"Closes {item_id}" + (f" — {json.dumps(title)}" if title else ""))
    results = []
    if unresolved or failures:
        results.append(Result(
            "closes-unresolved", WARNING, unresolved,
            unchecked=(
                f"the backlog cache for {scope} could not answer for {'; '.join(failures)} — "
                f"`prawduct-hook backlog sync --repo {scope}`, then re-run"
            ) if failures else None,
        ))
    if owed:
        results.append(Result("close-owed-at-merge", INFO, owed))
    return results


#: The markdown backend's files, the live one first. The archive file is the
#: Q2 split `/prawduct:backlog` makes when `## Archive` grows past its bound.
_MARKDOWN_BACKLOG = (".prawduct/backlog.md", ".prawduct/backlog-archive.md")


def _closure_markdown(project_dir: Path, ids: list[str]) -> list[Result]:
    """Markdown backend: read the backlog AT HEAD, because the archive move
    rides the branch — a close the branch claims should have moved the item."""
    from .backlog import ids as backlog_ids  # noqa: PLC0415
    from .backlog import legacy  # noqa: PLC0415

    pfx = [i for i in ids if backlog_ids.is_pfx(i)]
    issue_spelled = [i for i in ids if i not in pfx]
    unchecked: list[str] = []
    if issue_spelled:
        unchecked.append(
            f"the markdown backlog cannot say whether {', '.join(issue_spelled)} "
            "(an Issues id) is open"
        )
    pending: set[str] = set()
    known: set[str] = set()
    read_any = False
    for rel in _MARKDOWN_BACKLOG:
        code, text = _git(project_dir, "show", f"HEAD:{rel}")
        if code != 0:
            continue
        read_any = True
        parsed = legacy.parse_backlog(text)
        known.update(i.item_id.upper() for i in parsed.items if i.item_id)
        pending.update(i.item_id.upper() for i in parsed.pending_items() if i.item_id)
    if pfx and not read_any:
        unchecked.append(
            f"no markdown backlog at HEAD ({_MARKDOWN_BACKLOG[0]}), so {', '.join(pfx)} "
            "cannot be reconciled"
        )
        pfx = []
    unresolved = [i for i in pfx if i.upper() not in known]
    still_open = [i for i in pfx if i.upper() in pending]
    results = []
    if unresolved or unchecked:
        results.append(Result(
            "closes-unresolved", WARNING, unresolved,
            unchecked="; ".join(unchecked) if unchecked else None,
        ))
    if still_open:
        results.append(Result("closes-still-open", WARNING, still_open))
    return results


# ---------------------------------------------------------------------------
# check-pr-hygiene — open chunks and review attestations
# ---------------------------------------------------------------------------


def _chunks_open(project_dir: Path) -> list[Result]:
    """The bound plan's open chunks, from ``plan_status``'s finished answer.

    Unbound is the ordinary state of a chore branch and says nothing. A broken
    binding is not ordinary: whether a plan claims this branch is unknown.
    """
    from . import evidence, plan_status, work_unit  # noqa: PLC0415

    binding = work_unit.resolve(project_dir)
    if binding.state == "unbound":
        return []
    if binding.plan_path is None:
        return [Result(
            "chunks-open", INFO,
            unchecked=f"this branch's plan binding is {binding.state} ({binding.reason or 'no reason given'})",
        )]
    rel = work_unit.repo_rel(binding.plan_path, project_dir)
    facts = evidence.read_facts(project_dir)
    states = plan_status.chunk_states(binding.plan_path, facts, repo_dir=project_dir)
    if plan_status.is_finished(binding.plan_path, facts, repo_dir=project_dir, states=states):
        return []
    current = plan_status.current_chunks(binding.plan_path, facts, repo_dir=project_dir, states=states)
    synthetic = [s.reason or key for key, s in states.items() if s.synthetic and s.state == "open"]
    return [Result(
        "chunks-open", INFO,
        [f"{rel}: Chunk {chunk}" for chunk in current],
        unchecked=(f"{rel} has entries that could not be read: {'; '.join(synthetic)}" if synthetic else None),
    )]


def _review_tree_changed(project_dir: Path) -> list[Result]:
    """Reviews on the composed coverage path consolidated over a changed tree.

    ``critic-consolidate --tree-changed-by-builder`` is the builder's word that
    files changed during a review were theirs. The PR description is where the
    PR's human reader — the independent reader at this boundary — sees it.
    Scoped to the reviews the coverage gate actually credits, because facts
    carry no branch.
    """
    from . import critic_consolidate, evidence, gates  # noqa: PLC0415

    try:
        answer = gates.branch_coverage_verdict(project_dir)
        read = evidence.read_facts(project_dir)
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- an evidence read must not end the run; reported as unchecked
        return [_attributed("review-tree-changed", INFO, "reading the review facts", exc)]
    path = (answer.get("verdict") or {}).get("path") or []
    on_path = {step.get("id") for step in path if step.get("kind") == "review"}
    # A base-advance transfer credits the reviews of the span it transferred from.
    if answer.get("status") == "transferred":
        on_path |= set((answer.get("transfer") or {}).get("prior_review_ids") or [])
    if not on_path:
        return []
    items = []
    for fact in evidence.facts_of_kind(read, "review"):
        changed = (fact.get("body") or {}).get(critic_consolidate.TREE_CHANGED_KEY)
        if fact.get("id") in on_path and changed:
            items.append(f"{fact['id']}: {critic_consolidate.describe_tree_change(changed)}")
    return [Result("review-tree-changed", INFO, items)] if items else []


# ---------------------------------------------------------------------------
# check-pr-hygiene — assembly and the command
# ---------------------------------------------------------------------------


def _checks(base: str, merge_base: str):
    """``(group name, severity if it raises, the check)`` in output order. The
    group is what the one-line clean answer says was checked; the severity is
    the check's own, so a refusing check that raised fails closed."""
    return (
        ("credential-shape", REFUSE, lambda d: _credential_shape(d, merge_base)),
        ("closes", WARNING, lambda d: _closure(d, base, merge_base)),
        ("chunks-open", INFO, _chunks_open),
        ("review-tree-changed", INFO, _review_tree_changed),
    )


def hygiene(project_dir: Path) -> HygieneReport:
    """Every hygiene result over merge-base…HEAD. Never raises."""
    from . import coverage  # noqa: PLC0415

    base, why = coverage._resolve_base_branch(project_dir)
    if not base:
        return HygieneReport(error=f"could not resolve a base branch: {why}")
    code, merge_base = _git(project_dir, "merge-base", base, "HEAD")
    merge_base = merge_base.strip()
    if code != 0 or not merge_base:
        return HygieneReport(base=base, error=f"no merge-base between {base} and HEAD")
    _, head = _git(project_dir, "rev-parse", "HEAD")
    report = HygieneReport(base=base, merge_base=merge_base, head=head.strip())
    for group, severity, check in _checks(base, merge_base):
        report.checked.append(group)
        try:
            report.results.extend(check(project_dir))
        except Exception as exc:  # prawduct:allow prawduct/broad-except -- one check's failure must not hide the others; reported as unchecked
            report.results.append(_attributed(group, severity, f"the {group} check", exc))
    return report


def hygiene_exit(report: HygieneReport) -> int:
    """1 when a refusing result found something; 3 when a refusing result
    could not be read (authority fails closed) or nothing could be answered;
    else 0. Warnings and information never change the exit."""
    if report.error is not None:
        return EXIT_UNANSWERED
    if any(r.severity == REFUSE and r.items for r in report.results):
        return EXIT_REFUSED
    if any(r.severity == REFUSE and r.unchecked for r in report.results):
        return EXIT_UNANSWERED
    return EXIT_OK


def render_hygiene(report: HygieneReport) -> str:
    span = f"{report.base} (merge-base {(report.merge_base or '')[:8]})..HEAD"
    shown = [r for r in report.results if r.items or r.unchecked]
    if not shown:
        return f"check-pr-hygiene: nothing to report over {span} (checked: {', '.join(report.checked)})"
    lines = [f"check-pr-hygiene over {span}:"]
    for r in shown:
        if r.items:
            lines.append(f"{r.name} ({r.severity}): {RESULT_MEANINGS.get(r.name, '')}".rstrip(": "))
            lines.extend(f"  - {item}" for item in r.items)
        if r.unchecked:
            lines.append(f"{r.name}: unchecked — {r.unchecked}")
    return "\n".join(lines)


def hygiene_cmd(project_dir: Path, argv: list[str]) -> int:
    """``check-pr-hygiene [--json]``."""
    for arg in argv:
        if arg != "--json":
            print(f"check-pr-hygiene: unknown argument {arg!r} (recognized flags: --json)", file=sys.stderr)
            return EXIT_USAGE
    as_json = "--json" in argv
    report = hygiene(project_dir)
    exit_code = hygiene_exit(report)
    if exit_code == EXIT_REFUSED:
        refusing = [r for r in report.results if r.severity == REFUSE and r.items]
        findings = [item for r in refusing for item in r.items]
        _record_refusal(
            project_dir, HYGIENE_GUARD, refusing[0].name,
            {
                "head": report.head,
                "merge_base": report.merge_base,
                "results": {r.name: list(r.items) for r in refusing},
            },
            {"findings": len(findings)},
            "\0".join([report.head or "", *findings]),
        )
    if as_json:
        print(json.dumps({
            "base": report.base,
            "merge_base": report.merge_base,
            "head": report.head,
            "checked": report.checked,
            "results": [r.to_json() for r in report.results if r.items or r.unchecked],
            "error": report.error,
            "exit": exit_code,
        }, indent=2))
    elif report.error is None:
        print(render_hygiene(report))
    if report.error is not None:
        print(f"check-pr-hygiene: could not answer — {report.error}", file=sys.stderr)
    return exit_code


# ---------------------------------------------------------------------------
# check-pr-body — where GitHub looks for a PR template
# ---------------------------------------------------------------------------

#: GitHub's PR template name, compared case-insensitively, as a file (one
#: template) or as a directory (several, one chosen by the `template` query
#: parameter). Rules read from GitHub's documentation on 2026-11-11.
TEMPLATE_NAME = "pull_request_template"
#: The contribution guide GitHub links from a new PR, at the same locations.
CONTRIBUTING_NAME = "contributing"


def template_locations(root: Path) -> list[Path]:
    """The ONE home of where GitHub looks: the repository root, ``docs/`` and
    ``.github/``. Every other function here asks this one."""
    return [root, root / "docs", root / ".github"]


def _named(entry: Path, name: str) -> bool:
    """``name``, any case, with no extension or exactly one (``.md``, ``.txt``):
    ``pull_request_template.md.bak`` is a backup, not a template."""
    lowered = entry.name.lower()
    return lowered == name or (Path(lowered).stem == name and Path(lowered).suffix != "")


def _entries(directory: Path) -> list[Path]:
    try:
        return sorted(directory.iterdir(), key=lambda p: p.name)
    except OSError:
        return []


def find_templates(root: Path) -> list[Path]:
    """Every PR template candidate, in location order: a single template file
    in a location, or each file of a ``PULL_REQUEST_TEMPLATE/`` directory there.
    GitHub states no precedence among them, so more than one is reported, not
    resolved by a guess."""
    found: list[Path] = []
    for location in template_locations(root):
        for entry in _entries(location) if location.is_dir() else []:
            if entry.is_file() and _named(entry, TEMPLATE_NAME):
                found.append(entry)
            elif entry.is_dir() and entry.name.lower() == TEMPLATE_NAME:
                found.extend(p for p in _entries(entry) if p.is_file() and not p.name.startswith("."))
    return found


def find_contributing(root: Path) -> list[Path]:
    """A ``CONTRIBUTING`` file at the locations GitHub reads one from."""
    return [
        entry
        for location in template_locations(root) if location.is_dir()
        for entry in _entries(location)
        if entry.is_file() and _named(entry, CONTRIBUTING_NAME)
    ]


def _searched(root: Path) -> str:
    places = ", ".join(
        (loc.relative_to(root).as_posix() + "/") if loc != root else "the repository root"
        for loc in template_locations(root)
    )
    return (
        f"{TEMPLATE_NAME} (any case, with or without an extension such as .md or .txt) "
        f"or a PULL_REQUEST_TEMPLATE/ directory, in {places}"
    )


# ---------------------------------------------------------------------------
# check-pr-body — what a template requires, and whether a body has it
# ---------------------------------------------------------------------------

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
#: An ATX heading: up to three spaces, 1-6 `#`, then a space or end of line.
_HEADING_RE = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
#: Its optional closing sequence: whitespace then `#`s at the end.
_CLOSING_RE = re.compile(r"(?:^|[ \t]+)#+[ \t]*$")
#: A task-list item: a bullet, a `[ ]`/`[x]` box, then its text.
_CHECKLIST_RE = re.compile(r"^[ \t]*[-*+][ \t]+\[[ xX]\][ \t]+(.+?)[ \t]*$")


@dataclass(frozen=True)
class Requirement:
    """One template line a body must carry. ``key`` is what is compared."""

    kind: str  # "heading" | "checklist item"
    key: str
    shown: str


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def _visible_lines(text: str) -> list[str]:
    """The lines GitHub renders as markdown structure: HTML comments removed
    (in a template they are instructions to the author, and in a body they
    render as nothing), and fenced code blocks dropped. A comment keeps its
    newlines so line boundaries around it hold."""
    text = _COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    lines: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        opened = _FENCE_RE.match(line)
        if fence is not None:
            if opened and opened.group(1)[0] == fence[0] and len(opened.group(1)) >= len(fence):
                fence = None
            continue
        if opened:
            fence = opened.group(1)
            continue
        lines.append(line)
    return lines


def requirements(text: str) -> list[Requirement]:
    """Every heading and checklist item ``text`` carries, deduplicated, in order."""
    found: list[Requirement] = []
    seen: set[tuple[str, str]] = set()
    for line in _visible_lines(text):
        heading = _HEADING_RE.match(line)
        if heading:
            title = _CLOSING_RE.sub("", heading.group(2) or "").strip()
            if not title:
                continue
            req = Requirement("heading", _norm(title), f"{heading.group(1)} {title}")
        else:
            item = _CHECKLIST_RE.match(line)
            if not item:
                continue
            req = Requirement("checklist item", _norm(item.group(1)), f"- [ ] {' '.join(item.group(1).split())}")
        if (req.kind, req.key) not in seen:
            seen.add((req.kind, req.key))
            found.append(req)
    return found


def missing_from(template_text: str, body_text: str) -> tuple[list[Requirement], list[Requirement]]:
    """``(required, missing)``: the template's headings and checklist items,
    and those the body does not carry. A heading compares on its text (level
    and closing hashes aside), an item on its text (checkbox state aside),
    both with whitespace and case normalised."""
    required = requirements(template_text)
    present = {(r.kind, r.key) for r in requirements(body_text)}
    return required, [r for r in required if (r.kind, r.key) not in present]


# ---------------------------------------------------------------------------
# check-pr-body — the command
# ---------------------------------------------------------------------------


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _record_refusal(project_dir: Path, guard: str, reason: str, body: dict, observed: dict, dedupe: str) -> None:
    """Record a refusal; soft on failure, never silent (the sink's contract)."""
    from . import evidence  # noqa: PLC0415

    try:
        recorded = evidence.append_guard_refusal(
            project_dir, guard, body, reason=reason, observed=observed,
            dedupe_key=hashlib.sha256(dedupe.encode("utf-8", "surrogateescape")).hexdigest(),
        )
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- a refusal is correct whether or not its record lands; attributed below
        recorded = {"status": "error", "reason": f"{type(exc).__name__}: {exc}"}
    if recorded.get("status") not in ("appended", "duplicate"):
        print(
            f"NOTE: this refusal was not recorded ({recorded.get('reason', 'unknown')}) — "
            f"`prawduct-hook evidence list --kind guard-refusal` undercounts `{guard}`.",
            file=sys.stderr,
        )


def _parse_body_args(argv: list[str]) -> tuple[str | None, str | None, bool] | str:
    """``(body, template, as_json)`` or a usage error message."""
    body = template = None
    as_json = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--json":
            as_json = True
        elif arg == "--template":
            if i + 1 >= len(argv) or argv[i + 1].startswith("-"):
                return "--template needs a path"
            template = argv[i + 1]
            i += 1
        elif arg.startswith("-"):
            return f"unknown argument {arg!r} (recognized flags: --template <path>, --json)"
        elif body is None:
            body = arg
        else:
            return f"unexpected extra argument {arg!r} — one body file at a time"
        i += 1
    return body, template, as_json


def body_cmd(project_dir: Path, argv: list[str]) -> int:
    """``check-pr-body [<body file>] [--template <path>] [--json]``.

    ``--template`` is read relative to the repository root, as the candidates
    are named. The body file is read as given (relative to the caller's cwd).
    """
    parsed = _parse_body_args(argv)
    if isinstance(parsed, str):
        print(f"check-pr-body: {parsed}", file=sys.stderr)
        return EXIT_USAGE
    body_arg, template_arg, as_json = parsed
    root = project_dir
    candidates = find_templates(root)
    contributing = find_contributing(root)
    out = {
        "templates": [_rel(p, root) for p in candidates],
        "contributing": [_rel(p, root) for p in contributing],
        "searched": _searched(root),
        "template": None,
        "body": body_arg,
        "required": [],
        "missing": [],
        "verdict": None,
    }

    def _finish(code: int, human: list[str], *, err: str | None = None) -> int:
        out["exit"] = code
        if err is not None:
            print(f"check-pr-body: {err}", file=sys.stderr)
        if as_json:
            print(json.dumps(out, indent=2))
        elif human:
            print("\n".join(human))
        return code

    chosen: Path | None = None
    if template_arg is not None:
        chosen = Path(template_arg) if Path(template_arg).is_absolute() else root / template_arg
    elif len(candidates) == 1:
        chosen = candidates[0]
    template_text = None
    if chosen is not None:
        try:
            template_text = chosen.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            out["verdict"] = "unreadable"
            return _finish(EXIT_UNANSWERED, [], err=f"cannot read the template {template_arg or _rel(chosen, root)}: {exc}")
        out["template"] = _rel(chosen, root)
        out["required"] = [r.shown for r in requirements(template_text)]

    guide = [f"contribution guide: {_rel(p, root)} (read its section on pull requests)" for p in contributing]

    if body_arg is None:
        out["verdict"] = "listed"
        if chosen is not None:
            human = [f"PR template: {out['template']}"]
            if out["required"]:
                human.append("the description must carry each of these (text compared; level and checkbox state aside):")
                human.extend(f"  {line}" for line in out["required"])
            else:
                human.append("the template has no headings or checklist items to carry")
        elif candidates:
            human = ["PR templates (GitHub states no precedence; choose one with --template <path>):"]
            human.extend(f"  {p}" for p in out["templates"])
        else:
            out["verdict"] = "no-template"
            human = [f"no PR template — looked for {out['searched']}"]
        return _finish(EXIT_OK, human + guide)

    try:
        body_text = Path(body_arg).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        out["verdict"] = "unreadable"
        return _finish(EXIT_UNANSWERED, [], err=f"cannot read the body {body_arg}: {exc}")

    if chosen is None and candidates:
        out["verdict"] = "ambiguous"
        _record_refusal(
            project_dir, BODY_GUARD, "ambiguous-template",
            {"candidates": out["templates"]},
            {"candidates": len(candidates)},
            "\0".join(["ambiguous", *out["templates"], body_text]),
        )
        human = ["check-pr-body: more than one PR template and none chosen — re-run with --template <path>:"]
        human.extend(f"  {p}" for p in out["templates"])
        return _finish(EXIT_REFUSED, human)
    if chosen is None:
        out["verdict"] = "no-template"
        return _finish(EXIT_OK, [f"check-pr-body: no PR template, nothing to follow — looked for {out['searched']}"])

    required, missing = missing_from(template_text or "", body_text)
    out["missing"] = [{"kind": r.kind, "line": r.shown} for r in missing]
    if missing:
        out["verdict"] = "missing"
        _record_refusal(
            project_dir, BODY_GUARD, "missing-template-lines",
            {"template": out["template"], "missing": [r.shown for r in missing]},
            {
                "missing_headings": sum(r.kind == "heading" for r in missing),
                "missing_items": sum(r.kind == "checklist item" for r in missing),
            },
            "\0".join(["missing", out["template"], template_text or "", body_text]),
        )
        human = [f"check-pr-body: {body_arg} does not follow {out['template']} — missing:"]
        human.extend(f"  {r.shown}" for r in missing)
        return _finish(EXIT_REFUSED, human)
    out["verdict"] = "follows"
    headings = sum(r.kind == "heading" for r in required)
    return _finish(EXIT_OK, [
        f"check-pr-body: {body_arg} follows {out['template']} "
        f"({headings} heading(s), {len(required) - headings} checklist item(s))"
    ])
