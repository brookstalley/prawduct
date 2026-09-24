"""Everything the PR reviewer reads, assembled once, deterministically.

The reviewer's activation sequence is 13–18 sequential round-trips that assemble
context the caller and the hooks already hold — the base, the commit log, the
work description, the test verdict, the build plan's ``## Status`` boxes, the
change-log entry, the backlog items the branch cites. Every one of those is a
read this process can do in a single pass.

**Passing facts is not passing reasoning.** The reviewer's independence is that it
has not seen the builder's thinking, and nothing here is the builder's thinking: a
command that reads ``project-state.yaml`` and runs ``git log`` reveals no more
than the reviewer would have read for itself, in the same words, from the same
files. What it removes is the latency, not the separation.

**The diff is deliberately absent.** The reviewer reads the diff itself, once. A
second copy here would be the duplication this command exists to remove, so this
carries the ``--stat`` — the shape of the change, which is what the scope and
narrative goals need before they open anything.

**Failure posture: advice, failing soft, PER SECTION** (``architecture.md``: a
command's failure posture follows what it produces). This emits no verdict, so a
section that cannot be built must not end the run. It must also never render as
*empty*: a silent empty section reads as "checked, nothing found", which
manufactures exactly the false success the section exists to prevent — the
backlog section is the sharp case, because ``review-protocol.md`` marks **R-2**
as the check no other layer in the pipeline owns, so a reviewer told nothing
reports "reconciled" having reconciled nothing. Every degradation therefore
carries its own reason, in the reviewer's own words, where the content would have
been.

**Two hard failures, both exit 1 carrying their own reason rather than a degraded
section.** An unresolvable base: no base means no review interval, which means
there is nothing to review. And an incomplete ``lib/``: ``_lib`` imports six
sibling modules at first use, so without them there is no section to degrade —
``emit`` attributes it rather than letting it surface as a traceback.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

#: Every section this command promises to emit, in the order the reviewer reads
#: them. Named here rather than inferred from whatever got built, so a section
#: that fails to assemble is a NAMED degradation rather than a gap in a list
#: nobody can count.
SECTION_NAMES = (
    "base",
    "commits",
    "diffstat",
    "work",
    "test_evidence",
    "build_plan",
    "change_log",
    "backlog",
    "default_branch",
    "learnings_cap",
)


class Citation(NamedTuple):
    """One cited backlog id and HOW it was cited.

    `claims_closure` is what R-2 is stated over. It is deliberately not "is this
    id closed" — that is the cache's answer — but "did the branch say it closed
    it", which only the citing text knows and which nothing downstream can
    recover once the id is stripped out of its sentence.
    """

    id: str
    claims_closure: bool


#: The verb set of the closing-keyword rule in `skills/pr/review-protocol.md`
#: (`closes`/`fixes`/`resolves` and their inflections), plus the `closed-by:` and
#: `closes:` spellings the change-log uses.
_CLOSING_VERB = (
    r"(?:clos(?:e|es|ed|ing)|fix(?:es|ed|ing)?|resolv(?:e|es|ed|ing)|closed-by)"
)

#: A whole CLAIM REGION: one closing keyword and the run of citations it
#: introduces — `closes: #41 and BKL-9V2W`, `resolves 678`, `closed-by: a/b#7,
#: #8`. Matching the REGION rather than looking backwards from each id is what
#: makes this correct for two cases a lookback cannot reach, and both were live:
#:
#: * The keyword can be part of the id pattern itself (`closes: 678` is matched
#:   by `_ID_PATTERNS[2]`, which BEGINS at `closes`), so text before the match
#:   stops one character short of the word that proves the claim. That rendered
#:   a citation literally reading `closes:` as "mentioned only" — R-2's own
#:   predicate, inverted, on the check no other layer owns.
#: * Only the FIRST id of a run follows the keyword directly; every later one is
#:   preceded by the ids before it, which no fixed lookback can cross.
#:
#: The region is deliberately bounded by what may appear BETWEEN citations —
#: ids, separators, `and` — so ordinary prose after a claim ends the run rather
#: than sweeping the rest of the sentence into it.
_CITATION_RUN = (
    r"(?:[A-Z]{3}-[A-Z0-9]{4}|(?:[\w.-]+/[\w.-]+)?\#?\d+)"
)
_CLAIM_REGION = re.compile(
    r"(?i)\b" + _CLOSING_VERB + r"\b[\s:,\-]*"
    r"(?:" + _CITATION_RUN + r"[\s,]*(?:and\s+)?)+"
)

#: Backlog ids as they are actually written in commits and change-log entries.
#: Both the hand-minted `PFX-1A2B` form and the bare `#123` / `closes: 123`
#: provider form, because `cachequery.resolve` accepts every spelling and the
#: point is to hand the reviewer the resolution rather than the string.
_ID_PATTERNS = (
    re.compile(r"\b([A-Z]{3}-[A-Z0-9]{4})\b"),
    # A fully qualified provider citation, captured WHOLE. `cachequery.resolve`
    # accepts this spelling, and capturing only the trailing number would hand it
    # a different item whenever the citation names another repo.
    re.compile(r"\b([\w.-]+/[\w.-]+#\d+)\b"),
    re.compile(r"(?:closes|closed-by|fixes|resolves)\s*:?\s*#?(\d+)", re.IGNORECASE),
    # Bare `#N`. The lookbehind's job is NOT to exclude prose — it is to stop this
    # pattern re-capturing the number out of a qualified citation the pattern
    # above already took whole, which would resolve one citation twice and under
    # two different identities.
    re.compile(r"(?<![\w/])#(\d+)\b"),
)


class Section(NamedTuple):
    """One payload section: its content, or the named reason there is none.

    Exactly one of ``body`` / ``degraded`` is set. ``degraded`` is a sentence the
    reviewer can act on, not a status word — "backlog reconciliation unavailable
    — cache exit 6; R-1 and R-2 not answered" tells it which of its own goals it
    cannot answer, while "error" tells it nothing and reads like an empty result.
    """

    name: str
    body: str | None = None
    degraded: str | None = None

    @property
    def ok(self) -> bool:
        return self.degraded is None


def _git(project_dir: Path, *args: str) -> tuple[int, str]:
    """``(returncode, stdout)``; ``-1`` when git could not be run at all."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(project_dir), capture_output=True, text=True, timeout=30,
        )
    except Exception:  # prawduct:allow prawduct/broad-except -- a git failure degrades one section, never the run
        return -1, ""
    return proc.returncode, proc.stdout.strip()


class _Lib(NamedTuple):
    """The plugin lib modules this assembles from, bound by NAME.

    Positional unpacking at six call sites meant adding a module silently
    re-bound every one of them to the wrong thing — and it would still run. A
    test monkeypatching one of them had to hard-code its index too, so the test
    and the implementation were coupled by position rather than by contract.
    """

    briefing: object
    buildplan_refs: object
    change_log: object
    coverage: object
    gates: object
    gitstate: object


def _lib() -> _Lib:
    """The modules, imported lazily and together so a broken install degrades at
    the call rather than at import of this module. ``emit`` is what reports that
    case — the CLI wrapper's own ``ImportError`` handler covers only
    ``from lib import pr_payload`` and this import runs later, inside
    ``assemble``, so without ``emit``'s handler an incomplete ``lib/`` exits as a
    traceback (``api-contract.md`` § Direction: errors are attributed, never
    stack traces)."""
    from . import briefing, buildplan_refs, change_log, coverage, gates, gitstate  # noqa: PLC0415

    return _Lib(briefing, buildplan_refs, change_log, coverage, gates, gitstate)


# --------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------


def _section_commits(project_dir: Path, base: str) -> Section:
    code, out = _git(project_dir, "log", "--oneline", f"{base}..HEAD")
    if code != 0:
        return Section("commits", degraded=(
            f"commit log unavailable — `git log {base}..HEAD` failed; the "
            "narrative goal has no commit sequence to read"
        ))
    if not out:
        # NOT a degradation: an empty range is a real, reviewable answer, and
        # saying so is different from failing to ask.
        return Section("commits", body=f"(no commits in {base}..HEAD)")
    return Section("commits", body=out)


def _commit_bodies(project_dir: Path, base: str) -> str | None:
    """The commit messages in FULL, for the id scan only — never rendered.

    `_section_commits` carries `--oneline`, which is what the narrative goal
    wants to read, and subjects are the WRONG scan set: across 120 commits on
    this repo's own integration branch a backlog `#N` appears on 69 body lines
    against 15 subject lines, so scanning subjects alone renders the ordinary
    citation as "no ids cited" — a false clean on the one check
    `review-protocol.md` gives this reviewer and no other layer.

    A failed read returns ``None``, never ``""``: an empty string is
    indistinguishable from a range whose commits cite nothing, and the backlog
    section would then call the empty set an answer. The caller names ``None``
    to that section as an input it could not scan.
    """
    code, out = _git(project_dir, "log", "--format=%B", f"{base}..HEAD")
    return out if code == 0 else None


def _section_diffstat(project_dir: Path, base: str) -> Section:
    code, out = _git(project_dir, "diff", "--stat", f"{base}...HEAD")
    if code != 0:
        return Section("diffstat", degraded=(
            f"diff stat unavailable — `git diff --stat {base}...HEAD` failed; "
            "read the diff directly before judging scope"
        ))
    return Section("diffstat", body=out or f"(no changes in {base}...HEAD)")


def _section_work(project_dir: Path, prawduct_dir: Path, scope: str | None) -> Section:
    """What this branch claims to be doing — the scope goal's other operand.

    Two sources, and the second is not a fallback for a broken first: `scope` is
    derived from the branch against the plans that declare it, while
    `work_in_progress:` is a hand-maintained block many repos simply do not keep.
    An absent block is therefore an ANSWER about this repo, not a failure to read
    one, and rendering it as a degradation would teach the reviewer to distrust a
    healthy repo. Only having neither is a degradation, because then the scope
    goal has nothing at all to compare the diff against.
    """
    lib = _lib()
    # `gitstate.current_branch`, NOT `briefing._get_current_branch` — the latter
    # returns the STRING "main" on a git failure or a detached HEAD, which is a
    # display default for the briefing and a fabrication here (its own docstring
    # says so and points at this alternative, PDT-WT9K). This module's contract
    # is that an absent answer is always named; a fabricated branch would also
    # key `_parse_wip` off it, handing the reviewer ANOTHER branch's work
    # description as this PR's stated scope — the operand Goal 1 grades the diff
    # against.
    branch = lib.gitstate.current_branch(project_dir)
    # And when the branch is unreadable, do not ASK for the work block:
    # `_parse_wip(dir, None)` auto-detects the branch through the same
    # `_get_current_branch` fabrication, so handing it `None` routes straight
    # back into the value this call exists to avoid.
    wip = lib.briefing._parse_wip(prawduct_dir, branch) if branch else {}

    fields = []
    if branch:
        fields.append(f"branch: {branch}")
    else:
        fields.append(
            "branch: could not be read (detached HEAD, or git failed) — no work "
            "description was resolved, because resolving one requires the branch"
        )
    if scope:
        fields.append(f"scope: {scope} (derived from the branch against declared plan scopes)")
    if wip.get("description"):
        fields.append(f"description: {wip['description']}")
        for key in ("size", "type", "current_chunk", "governance_level"):
            if wip.get(key):
                fields.append(f"{key}: {wip[key]}")
    elif scope:
        fields.append(
            "project-state.yaml carries no `work_in_progress:` block for this "
            "branch — the scope above is the stated scope; size/type are not "
            "declared, so do not infer them"
        )

    if not scope and not wip.get("description"):
        # Two different causes, and saying the wrong one is its own defect: a
        # branch that could not be READ has not "matched no declared scope" —
        # nothing was matched against anything.
        cause = (
            "project-state.yaml carries no `work_in_progress:` description and "
            "the branch name matches no declared plan scope"
            if branch else
            "the branch could not be read (detached HEAD, or git failed), so "
            "neither the declared plan scopes nor the branch-scoped "
            "`work_in_progress:` block could be consulted"
        )
        return Section("work", degraded=(
            f"no stated scope for this branch — {cause}. The scope goal has "
            "nothing to compare the diff against; judge it from the commits and "
            "the build plan instead"
        ))
    return Section("work", body="\n".join(fields))


def _section_test_evidence(project_dir: Path) -> Section:
    lib = _lib()
    try:
        is_current, reason, clause = lib.gates.tests_are_current(project_dir)
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- an evidence read must not end the run
        return Section("test_evidence", degraded=(
            f"test evidence unreadable ({exc.__class__.__name__}) — treat the "
            "changeset as having NO fresh evidence, which is the warning "
            "condition, not the clear one"
        ))
    # The CLAUSE rides the payload, not just the verdict. Both disjuncts exit 0
    # and they are different evidence: `tree` means the recorded run met this
    # exact tree, `session` means a run from earlier this session that never
    # did. `review-protocol.md` tells the reviewer to read which one a bundle
    # rests on, and a payload that reports only "current" makes that
    # unanswerable from the section it was told to read.
    verdict = (
        lib.gates.CURRENT_TREE_LABEL if clause == "tree"
        else lib.gates.CURRENT_SESSION_LABEL if is_current
        else "stale"
    )
    return Section("test_evidence", body=(
        f"test-status: {verdict} (exit {0 if is_current else 1})\nreason: {reason}"
    ))


def _section_build_plan(reviewed) -> Section:
    """``reviewed`` is the caller's already-resolved :class:`ReviewedPlan`.

    Resolved once by the caller and handed down, rather than re-resolved here:
    ``resolve_branch_plan`` exists precisely because the longhand two-call form
    scanned ``artifacts/`` twice per resolution, and asking it again here would
    reinstate the second scan inside the command whose whole purpose is latency.
    """
    if reviewed.path is None:
        return Section("build_plan", degraded=(
            f"no build plan resolved for this branch ({reviewed.gap or 'no reason given'}) "
            "— the Status-box checks have no subject; say so rather than reading "
            "them as all-ticked"
        ))
    try:
        content = reviewed.path.read_text(encoding="utf-8")
    except OSError as exc:
        return Section("build_plan", degraded=(
            f"build plan at {reviewed.rel} could not be read ({exc.__class__.__name__}) "
            "— the Status-box checks have no subject"
        ))
    boxes = [
        ln for ln in content.splitlines()
        if ln.strip().startswith(("- [ ]", "- [x]", "- [X]"))
    ]
    lines = [f"path: {reviewed.rel}"]
    if reviewed.gap:
        # A resolution that is an ASSUMPTION is reported as one. The plan may
        # still be the right subject; what must not happen is the reviewer
        # grading it as though the answer were grounded.
        lines.append(f"resolution caveat: {reviewed.gap}")
    if boxes:
        lines.append("## Status boxes (hand-authored; nothing derives them):")
        lines.extend(f"  {b.strip()}" for b in boxes)
    else:
        lines.append("## Status: no checkbox items found in the plan")
    return Section("build_plan", body="\n".join(lines))


def _added_lines(project_dir: Path, base: str, path: Path) -> set[str] | None:
    """The lines this branch adds to ``path`` against ``base``, or ``None`` when
    the diff cannot be read — never an empty set, which is an answer."""
    code, out = _git(project_dir, "diff", "--unified=0", f"{base}...HEAD", "--", str(path))
    if code != 0:
        return None
    return {
        ln[1:] for ln in out.splitlines()
        if ln.startswith("+") and not ln.startswith("+++")
    }


def _section_change_log(
    project_dir: Path, prawduct_dir: Path, scope: str | None, base: str
) -> Section:
    lib = _lib()
    path = prawduct_dir / "change-log.md"
    if not path.is_file():
        return Section("change_log", degraded=(
            f"no change log at {path.name} — the version/changelog coherence "
            "check has nothing to compare the diff against"
        ))
    try:
        raw = path.read_text(encoding="utf-8")
        entries = lib.change_log.parse_change_log(raw)
    except (OSError, ValueError) as exc:
        return Section("change_log", degraded=(
            f"change log unparseable ({exc.__class__.__name__}) — the "
            "version/changelog coherence check is not answered"
        ))
    all_lines = raw.splitlines()
    paired_by = None
    if scope is None:
        # No build plan claims this branch — the ordinary state of a docs or
        # fix branch — so there is no scope to pair by. The entry is still
        # knowable: it is the one this branch ADDS. Without this the section
        # degraded, the backlog scan received no entry text, and every id the
        # entry cited was reported as "no backlog ids cited".
        added = _added_lines(project_dir, base, path)
        if added is None:
            return Section("change_log", degraded=(
                "no scope resolved for this branch, and the change log's diff "
                f"against {base} could not be read, so the entry cannot be paired "
                "to it — check coherence by reading the log's newest entries "
                "directly"
            ))
        # Matched by heading TEXT, not line number: the diff numbers HEAD's
        # file, and this reads the working tree, which may differ.
        matched = [e for e in entries if all_lines[e.line_number - 1] in added]
        if not matched:
            return Section("change_log", body=(
                "no build plan claims this branch, and it adds no change-log "
                "entry — this bundle currently ships with nothing describing it, "
                "which is itself the finding"
            ))
        paired_by = (
            "paired by diff: no build plan claims this branch, so the entry "
            f"carried is the one it adds against {base}"
        )
    else:
        matched = [e for e in entries if e.tags.get("scope") == scope]
    if not matched:
        # An ANSWER, not a degradation: the log was read and parsed, and the
        # result is that nothing describes this bundle — which is the finding,
        # not a failure to look. Rendering it `degraded` counts it into
        # `render_human`'s "N of M sections degraded — each says which of your
        # checks it leaves unanswered", which is false of this one, and hands
        # `--json` consumers `ok: false` for a healthy read. The degraded channel
        # stays for unreadable/unparseable, which genuinely leave R-2 unanswered.
        return Section("change_log", body=(
            f"no change-log entry tagged `scope={scope}` — this bundle currently "
            "ships with nothing describing it, which is itself the finding"
        ))
    # The BODY, not just the head. Two consumers need it and both were being
    # served a heading: the reviewer is told to read this entry against the
    # diffstat (the entry IS the release note, so a deliverable its prose omits
    # ships invisibly), and `cited_backlog_citations` scans this section's text — an
    # id written in the entry's prose rather than its title is the ordinary
    # case, and without the body it renders as "no ids cited", which is a false
    # clean on the one check nothing else in the pipeline owns.
    starts = sorted(e.line_number for e in entries)
    lines = [paired_by] if paired_by else []
    for entry in matched:
        after = [s for s in starts if s > entry.line_number]
        end = (after[0] - 1) if after else len(all_lines)
        body = "\n".join(all_lines[entry.line_number:end]).strip()
        lines.append(f"line {entry.line_number}: {entry.title}")
        lines.append(f"  tags: {json.dumps(entry.tags, sort_keys=True, default=str)}")
        if entry.tag_conflicts:
            lines.append(f"  tag conflicts: {', '.join(entry.tag_conflicts)}")
        if entry.unconsumed_tag_lines:
            lines.append(
                f"  {entry.unconsumed_tag_lines} tag line(s) past the entry head — "
                "parsed by nothing"
            )
        lines.append("  body:")
        lines.extend(f"    {ln}" for ln in (body.splitlines() or ["(empty)"]))
    return Section("change_log", body="\n".join(lines))


def cited_backlog_citations(
    commit_text: str, change_log_text: str
) -> list[Citation]:
    """Every backlog id the branch's commits or change-log entry cite, deduped
    and in first-seen order, each with HOW it was cited.

    **Both arguments must carry the full text, not a rendering of it.** The
    sentence above is the contract three records state (`review-protocol.md`,
    the Chunk 01 deliverable, and the backlog section's own "no ids cited"
    answer), and it is false the moment a caller passes a summary: subjects
    without bodies, or an entry's head without its prose. Callers pass
    `_commit_bodies` and the change-log section's body, both of which carry the
    whole text.

    Exported because it is the ANSWER the backlog section needs, and because the
    reviewer's R-2 check is stated over exactly this set: a change-log entry or
    commit that claims a closure. A caller that re-derived the set privately
    would give a third answer to a question that has one.
    **Each citation carries whether a CLOSING KEYWORD introduced it**, because
    R-2's predicate is not "an id appears" but "a commit or entry *claims a
    closure* the backlog does not show". Scanning commit bodies (which is where
    the citations are) means most cited ids are discussed rather than claimed —
    this bundle's own bodies mention several as context — and an id list with the
    form stripped renders every one of them as `STILL OPEN`, inviting a reviewer
    to file a closure-that-never-happened against work nobody claimed to close.
    The alternative is the reviewer re-reading `git log` to find out, which is
    the round-trip this command exists to remove.
    """
    seen: dict[str, Citation] = {}
    text = f"{commit_text}\n{change_log_text}"
    claim_spans = [m.span() for m in _CLAIM_REGION.finditer(text)]
    for pattern in _ID_PATTERNS:
        for match in pattern.finditer(text):
            token = match.group(1)
            # Does this id fall INSIDE a claim region? Asked of the id's own
            # span rather than of the text before it, because the keyword can be
            # inside the id match and because later ids in a run are preceded by
            # their siblings, not by the verb.
            claimed = any(
                start <= match.start() and match.end() <= end
                for start, end in claim_spans
            )
            if token not in seen:
                seen[token] = Citation(token, claimed)
            elif claimed and not seen[token].claims_closure:
                # One id can be cited twice — discussed here, claimed there. The
                # CLAIM is what R-2 asks about, so any claim wins over a mention.
                seen[token] = Citation(token, True)
    return list(seen.values())


def _section_backlog(
    project_dir: Path,
    backlog_scope: str | None,
    citations: list[Citation],
    unscanned: Sequence[str] = (),
) -> Section:
    """Resolve every cited id. **This is R-2's only data source anywhere in the
    pipeline**, so its degradation must be loud: `review-protocol.md` assigns
    that check to this reviewer and to no other layer, and an unnamed failure
    here renders as "reconciled" having reconciled nothing.

    **`backlog_scope` is the BACKLOG repo (`owner/repo`), never the build-plan
    scope.** Both are called "scope" one call frame apart and every other section
    here takes the plan one, which is how the plan scope reached
    `cachequery.resolve` and made every id report as needing a repo. The names
    differ now because the types cannot tell them apart.

    **`unscanned` names the id-scan inputs that could not be read.** "No ids
    cited" is an answer only over inputs that were actually scanned; over an
    unread one it is the false clean this section exists to remove, so it
    degrades, and a non-empty set says what it did not see.
    """
    ids = [c.id for c in citations]
    if not citations and unscanned:
        return Section("backlog", degraded=(
            f"no backlog ids found, but {' and '.join(unscanned)} could not be "
            "scanned, so ids cited there are unknown — R-2 is NOT answered; read "
            "them by hand for closure claims"
        ))
    if not citations:
        return Section("backlog", body=(
            "no backlog ids cited in the commits or the change-log entry — "
            "R-2 has nothing to check (this is an answer, not a failure)"
        ))
    if backlog_scope is None:
        return Section("backlog", degraded=(
            "backlog reconciliation unavailable — this repo sets no "
            "`backlog_service_repo:`, so there is no cache scope to resolve the "
            f"cited ids against; R-1 and R-2 are NOT answered for {', '.join(ids)}"
        ))
    try:
        from datetime import datetime, timezone  # noqa: PLC0415

        from .backlog import cachequery  # noqa: PLC0415
    except ImportError as exc:
        return Section("backlog", degraded=(
            f"backlog reconciliation unavailable — {exc.__class__.__name__} "
            f"importing the cache reader; R-1 and R-2 are NOT answered for "
            f"{', '.join(ids)}"
        ))

    now = datetime.now(timezone.utc)
    lines, failures = [], []
    for citation in citations:
        item_id = citation.id
        try:
            envelope = cachequery.resolve(
                project_dir,
                scope=backlog_scope,
                id_raw=item_id,
                now=now,
                default_owner=backlog_scope.split("/", 1)[0],
            )
        except Exception as exc:  # prawduct:allow prawduct/broad-except -- one id's failure must not hide the others
            failures.append(f"{item_id}: {exc.__class__.__name__}")
            continue
        # `resolve` speaks the transport ENVELOPE — `{status, data, warnings}` —
        # and REPORTS a failed lookup rather than raising it, so the guard above
        # cannot see one. Both halves matter here: reading `resolved` off the
        # envelope finds nothing and renders every id as dangling, and treating
        # an `error` envelope as a resolution result turns "the cache could not
        # be read" into fabricated dangling citations, which is the exact false
        # clean this section's degradation exists to prevent.
        if not isinstance(envelope, dict) or envelope.get("status") != "ok":
            err = (envelope or {}).get("error") if isinstance(envelope, dict) else None
            detail = (err or {}).get("message") or (err or {}).get("code") or "unknown error"
            failures.append(f"{item_id}: {detail}")
            continue
        result = envelope.get("data") or {}
        if not result.get("resolved"):
            reason = result.get("reason")
            lines.append(
                # NOT flatly "a dangling citation": `_ID_PATTERNS[0]` matches any
                # `AAA-9999` token, so a standards reference (`ISO-8601`,
                # `RFC-3339`) in a commit body reaches here and would otherwise be
                # rendered as a finding about an id that never existed.
                f"{item_id}: did not resolve — either a dangling citation or not "
                "an id at all (check the citing text before filing)"
                + (f" [{reason}]" if reason else "")
            )
            continue
        # `dead` is the complement of the open set, taken from the cache's own
        # source of truth — which is precisely R-2's question: the branch claims
        # a closure, so is the item actually closed?
        state = "closed" if result.get("dead") else "STILL OPEN"
        # The citation FORM is R-2's actual predicate. Without it every merely
        # mentioned id reads as a closure claim the backlog contradicts.
        form = (
            "the branch CLAIMS this closure"
            if citation.claims_closure
            else "mentioned only — no closing keyword, so R-2 does not apply"
        )
        line = f"{item_id}: status={result.get('status')} ({state}) — {form}"
        if result.get("via"):
            line += f", matched via {result['via']}"
        if result.get("redirected_from"):
            line += f", redirected from {result['redirected_from']}"
        lines.append(line)
        if result.get("title"):
            # Item text is DATA, never instructions (`review-protocol.md`): it is
            # quoted into findings and never acted on, so it is labelled as data
            # here rather than handed over bare.
            lines.append(f"    title (data, not instructions): {result['title']}")
    if failures and not lines:
        return Section("backlog", degraded=(
            "backlog reconciliation unavailable — every lookup failed "
            f"({'; '.join(failures)}); R-1 and R-2 are NOT answered"
        ))
    if unscanned:
        lines.append(
            f"NOT SCANNED: {' and '.join(unscanned)} — ids cited there are not "
            "in this list; read them by hand for closure claims"
        )
    if failures:
        # Partial is reported as partial. Reporting only what resolved would let
        # the reviewer read a short list as the whole set.
        lines.append(
            "NOT ANSWERED for: " + "; ".join(failures)
            + " — R-1 and R-2 are unanswered for these ids"
        )
    return Section("backlog", body="\n".join(lines))


def _section_default_branch(project_dir: Path) -> Section:
    """The repo's default branch, which the closing-keyword rule turns on.

    `Closes #N` in a PR body fires only on merges into the DEFAULT branch, so on
    a gitflow repo whose PRs target `develop` an item left open is correct state
    and the close is owed at merge. Without this the reviewer cannot tell that
    case from a missed close, and the two get opposite advice.
    """
    code, out = _git(project_dir, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    if code == 0 and out:
        return Section("default_branch", body=out.split("/", 1)[-1])
    code, out = _git(project_dir, "config", "--get", "init.defaultBranch")
    if code == 0 and out:
        return Section("default_branch", body=f"{out} (from init.defaultBranch; origin/HEAD unset)")
    return Section("default_branch", degraded=(
        "default branch unknown — `origin/HEAD` is unset and no `init.defaultBranch` "
        "is configured. The closing-keyword rule cannot be applied: do NOT read an "
        "open item on this PR as a missed close"
    ))


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------


def _section_learnings_cap(project_dir: Path, prawduct_dir: Path, base: str) -> Section:
    """Whether this branch changes ``core.md``'s cap, and on whose word.

    ``owner_approved:`` is text an agent can write, so its visibility at the
    PR boundary is the only check on a raise the owner never gave. A reviewer
    who is told nothing here would have to open ``project-state.yaml`` itself.
    """
    from . import learnings_files, record_lint  # noqa: PLC0415 — lazy; only this section needs them

    # The MERGE-BASE, not the base branch's tip: a cap changed on the base after
    # this branch forked is not this branch's change, and would read as one.
    code, fork = _git(project_dir, "merge-base", base, "HEAD")
    if code != 0 or not fork:
        return Section("learnings_cap", degraded=(
            f"core.md's cap could not be compared — no merge-base with {base}; read "
            "`learnings_budgets.core.md` in project-state.yaml at both ends yourself"
        ))
    try:
        before = record_lint.budgets_at(project_dir, prawduct_dir, fork).get(learnings_files.CORE_NAME) or {}
        after = record_lint.budgets_at(project_dir, prawduct_dir, "HEAD").get(learnings_files.CORE_NAME) or {}
    except (OSError, ValueError) as exc:
        return Section("learnings_cap", degraded=(
            f"core.md's cap could not be compared ({type(exc).__name__}) — read "
            "`learnings_budgets.core.md` in project-state.yaml at both ends yourself"
        ))
    def _cap(entry: dict) -> tuple:
        return (entry.get("kb"), entry.get("owner_approved"))

    if _cap(before) == _cap(after):
        return Section("learnings_cap", body="this branch does not change core.md's cap")
    return Section("learnings_cap", body=(
        f"core.md's cap CHANGES on this branch: {before or 'the default'} -> {after or 'the default'}. "
        "`owner_approved:` is text an agent can write: this raise needs the owner's "
        "approval quoted in the PR description, or it is a WARNING."
    ))


def assemble(project_dir: Path) -> tuple[list[Section], str | None]:
    """Build every section. Returns ``(sections, hard_failure_reason)``.

    A hard failure means no base could be resolved, and that is the one condition
    that is not a degraded section: without a base there is no review interval, so
    there is nothing for any other section to be about.
    """
    lib = _lib()
    prawduct_dir = lib.gitstate.get_prawduct_dir(project_dir)

    base, base_reason = lib.coverage._resolve_base_branch(project_dir)
    if not base:
        return [], f"could not resolve a base branch: {base_reason}"

    commits = _section_commits(project_dir, base)
    # ONE resolution, ONE scan of `artifacts/`: the composite already carries the
    # scope it inferred, so asking separately would scan the directory twice and
    # let the two answers drift.
    reviewed = lib.buildplan_refs.resolve_branch_plan(project_dir, prawduct_dir)
    scope = reviewed.scope

    sections = [
        # The tree this ANSWERED about, so a reviewer can tell it apart from the
        # tree it was asked about. The base branch cannot do that job — both the
        # primary checkout and a worktree of the same repo resolve `develop` — so
        # the discriminating facts are the absolute directory and its HEAD, which
        # the reviewer already holds from its prompt and its `git -C` reads.
        Section("base", body=(
            f"{base}\nresolved by: {base_reason}\n"
            f"project dir: {project_dir}\n"
            f"HEAD: {_git(project_dir, 'rev-parse', 'HEAD')[1] or '(unreadable)'}\n"
            "If either disagrees with what your prompt carries, you are reading a "
            "different tree than the caller thinks — say so rather than picking one."
        )),
        commits,
        _section_diffstat(project_dir, base),
        _section_work(project_dir, prawduct_dir, scope),
        _section_test_evidence(project_dir),
        _section_build_plan(reviewed),
    ]
    change_log_section = _section_change_log(project_dir, prawduct_dir, scope, base)
    bodies = _commit_bodies(project_dir, base)
    unscanned = [
        name for name, text in (
            ("the commit messages", bodies),
            ("the change-log entry", change_log_section.body),
        ) if text is None
    ]
    sections.append(change_log_section)
    sections.append(
        _section_backlog(
            project_dir,
            # `backlog_service_repo:`, the same key `briefing._backlog_pending_line`
            # and `norm_probes._live_scope` read — NOT `scope` above, which is the
            # build plan's.
            lib.briefing.read_str_yaml_key(
                prawduct_dir / "project-state.yaml", "backlog_service_repo"
            ),
            # `_commit_bodies`, NOT `commits.body` — that section is `--oneline`,
            # and a citation in a commit's body is the ordinary case here.
            cited_backlog_citations(bodies or "", change_log_section.body or ""),
            unscanned,
        )
    )
    sections.append(_section_default_branch(project_dir))
    sections.append(_section_learnings_cap(project_dir, prawduct_dir, base))

    # The roster is the promise, so reconcile against it rather than trusting the
    # list just built. A builder that raised, or a section quietly dropped in a
    # refactor, would otherwise leave a GAP — and a gap is the one rendering this
    # command must never produce, because a missing section reads exactly like a
    # section that found nothing. Named here, it degrades like any other.
    produced = {s.name for s in sections}
    for name in SECTION_NAMES:
        if name not in produced:
            sections.append(Section(name, degraded=(
                "this section was not assembled at all — treat every check it "
                "carries as UNANSWERED, not as passed"
            )))
    return _in_roster_order(sections), None


def _in_roster_order(sections: list[Section]) -> list[Section]:
    """Sections in the order the reviewer reads them, roster first.

    Anything the roster does not name keeps its place at the end rather than
    being dropped — an unexpected section is a thing to show, not to hide.
    """
    by_name = {s.name: s for s in sections}
    ordered = [by_name[n] for n in SECTION_NAMES if n in by_name]
    ordered += [s for s in sections if s.name not in set(SECTION_NAMES)]
    return ordered


def render_human(sections: list[Section]) -> str:
    out = ["# PR review payload", ""]
    degraded = [s for s in sections if not s.ok]
    if degraded:
        out.append(
            f"**{len(degraded)} of {len(sections)} sections degraded** — each says which "
            "of your checks it leaves unanswered. An unanswered check is not a passed one."
        )
        out.append("")
    for section in sections:
        out.append(f"## {section.name}")
        out.append(section.body if section.ok else f"DEGRADED — {section.degraded}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def emit(project_dir: Path, argv: list[str]) -> int:
    """Body of ``prawduct-hook pr-review-payload [--json] [<project dir>]``.

    **The positional exists because the caller that needs it cannot use a
    `cd`.** This command's own premise, stated in `agents/pr-reviewer.md` and
    repeated in `review-protocol.md`, is that a review subagent does not inherit
    the caller's working directory and must anchor every read on the absolute
    project dir its prompt carries — which is why every git call there is
    `git -C <dir>`. That reviewer's tool allow-list grants this op by exact name
    and grants no `cd`, so without an argument the one reader the command was
    built for can only ask about whatever tree the process started in.
    `get_project_dir()` resolves `CLAUDE_PROJECT_DIR` — the LAUNCH dir — first,
    so in a mid-session worktree move the payload would describe the primary
    checkout while the reviewer's `-C` diff describes the worktree, and every
    section (the `## Status` boxes, the `scope=` entry, the cited ids, the test
    verdict) would be graded against a bundle nobody asked about, reading clean.
    """
    as_json = False
    target: Path | None = None
    for arg in argv:
        if arg == "--json":
            as_json = True
        elif not arg.startswith("-") and target is None:
            target = Path(arg).expanduser()
        else:
            print(
                f"pr-review-payload: unknown argument {arg!r} "
                "(usage: pr-review-payload [--json] [<project dir>])",
                file=sys.stderr,
            )
            return 1

    if target is not None:
        # A hard failure, not a degradation, and deliberately so: every section
        # would otherwise answer about the WRONG tree, which is the silent pass
        # the argument exists to prevent. Naming the directory is the caller
        # asserting which tree it means, so failing to find it is unambiguous.
        if not (target / ".git").exists() and not (target / ".prawduct").is_dir():
            print(
                f"pr-review-payload: {target} is not a project directory "
                "(no `.git` and no `.prawduct/`) — pass the absolute path your "
                "prompt carries, or omit the argument to use the current one",
                file=sys.stderr,
            )
            return 1
        project_dir = target.resolve()

    try:
        sections, hard_failure = assemble(project_dir)
    except ImportError as exc:
        # `_lib()` imports six sibling modules at first use, inside `assemble`
        # and outside the wrapper's handler. An incomplete `lib/` is the one
        # failure this module cannot degrade per section, because no section
        # can be built without them.
        print(
            f"pr-review-payload: the plugin lib/ is incomplete ({exc}) — "
            "reinstall or update the prawduct plugin",
            file=sys.stderr,
        )
        return 1
    if hard_failure:
        print(f"pr-review-payload: {hard_failure}", file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps({
            "schema_version": 1,
            "sections": [
                {"name": s.name, "ok": s.ok, "body": s.body, "degraded": s.degraded}
                for s in sections
            ],
        }, indent=2))
        return 0

    print(render_human(sections), end="")
    return 0
