"""Converge a repo off the retired derived-view model (FL2, FL3, GD2).

Three retired things left residue in every already-onboarded repo, and a
template change cannot reach any of them (``init_product`` and
``core.write_template`` skip destinations that already exist — the same reason
:mod:`lib.norm_index_scaffold` exists): a ``views_enabled:`` key, a
``scope_rollups:`` block, a ``release-notes.md`` that was a regenerated view,
and per-plan HTML comments instructing the reader that a plan's ``## Status``
checkboxes are derived and must not be hand-edited.

The last of those is the one that still does damage. The other three are inert
— nothing reads them — but a comment saying *do not hand-flip these boxes* is
read by a human or an agent and obeyed, and the boxes are now the only reading
of chunk progress that the session gates have. A repo that keeps it converges
its data and still behaves the old way.

**Why this is preview-by-default with ``--apply``**, when its sibling
:func:`lib.plan_archive.archive_plan` writes on invocation: the binding rule is
``security-model.md`` § Direction — one informed confirmation at the *operation*
level, naming the blast radius. The scope-vs-danger framing that decides which
shape satisfies it (a command acting on one file the operator named may write; a
repo-wide one that picks its own files previews first) is **descriptive** prose
in ``api-contract.md`` § Operations, not a ratified norm — cited that way round
because attributing a rule to a § Direction that does not contain it is how a
norm acquires authority nobody granted it. This one walks the whole artifacts
tree, so it previews.

**And why the preview is not a second validation pass.** A dry run that
re-validates exactly what the write path validates is where drift hides — it
reports clean while the artifact rots, which is how ``regen-views --check``
exited 0 with writes pending and a real repo lost whole sections of
``release-notes.md``. So the shape here is one computation with two endings:
:func:`plan_repair` returns the concrete edit list, the preview *renders* that
list, and ``--apply`` *executes* the same list. The preview cannot disagree with
the write, because there is nothing for it to disagree with.

**One approval for the whole act.** ``security-model.md`` § Direction requires
an operation-level confirmation naming the blast radius — and forbids a
per-action gate, in those terms: confirmation fatigue is itself a safety
regression. So the preview names every file and every reason once, and
``--apply`` is a single yes. There is deliberately no per-file prompt.

Return convention follows the package: dicts carrying ``status`` (and
``reason`` when refused), never exceptions across the boundary.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import buildplan_refs, core, plan_index


def _read_preserving_newlines(path: Path) -> str:
    """File text with its own line endings intact.

    ``newline=""`` disables universal-newline translation. Without it a CRLF file
    reads as ``\n``-only and every write puts it back that way — so an operation
    that promises to remove two keys instead rewrites every line in a product's
    authored file, and the diff hides the real change inside a whole-file
    reformat. :mod:`lib.norm_index_scaffold` already treats this as load-bearing
    for exactly the same reason; this module did not, and a CRLF fixture turned
    nine CRLF lines into zero.

    ``str.splitlines`` still splits on ``\r\n``, so every predicate here is
    unaffected — the endings simply survive into the text that gets written back.
    """
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()

STATE_REL = ".prawduct/project-state.yaml"
RELEASE_NOTES_REL = ".prawduct/release-notes.md"
ARTIFACTS_REL = ".prawduct/artifacts"

#: The retired opt-in flag. Named once here because three things need it and
#: they must not drift: the repair that removes it, the guard that fails if it
#: comes back (GD2), and the reason text a reader sees.
VIEWS_FLAG = "views_enabled"
#: The retired derived-view block. A mapping, so its removal takes the key line
#: plus everything indented under it.
ROLLUPS_KEY = "scope_rollups"

#: Marker proving ``release-notes.md`` has already been frozen. Matched as a
#: substring anywhere in the file's head rather than as an exact banner, because
#: a repo that froze it by hand wrote its own words and re-freezing it would
#: stack a second banner on the first.
FROZEN_MARKER = "FROZEN ARCHIVE"

#: Prepended to a `release-notes.md` that is still presenting itself as current.
#: It says *what to read instead*, because a reader who arrives here wants the
#: answer, not merely a warning that this is not it.
FROZEN_BANNER = """# Release Notes — FROZEN ARCHIVE

> **This file is history, not a current record. Nothing maintains it.**
>
> It was regenerated from the change log. That regeneration is retired, so the
> change log is now the only record of what shipped in which release — and it
> always was; this was a digest of it.
>
> Everything below is preserved as it stood when this file was frozen. It is
> **not** updated for later releases, so a release missing here has not
> necessarily gone unreleased — look it up in `change-log.md`.

"""

_STATUS_HEADING_RE = re.compile(r"^##\s+Status\s*$")
_NEXT_H2_RE = re.compile(r"^##\s+\S")
_COMMENT_OPEN = "<!--"
_COMMENT_CLOSE = "-->"


# --- project-state.yaml -----------------------------------------------------


def _is_top_level_key(line: str, key: str) -> bool:
    """True for ``key:`` at column 0 — not an indented member of some other key.

    Indentation is the whole test: a nested ``views_enabled:`` under an
    unrelated mapping belongs to that mapping, and removing it would silently
    edit a structure this operation knows nothing about.
    """
    return bool(re.match(rf"^{re.escape(key)}\s*:", line))


def _block_span(lines: list[str], start: int) -> int:
    """Exclusive end index of the block opened at ``start``.

    A top-level key owns every following line that is indented or blank, up to
    the next line at column 0. Trailing blanks are given back to the document so
    removing a block does not also close the gap the author left after it.
    """
    end = start + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() and not line[:1].isspace():
            break
        end += 1
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    return end


def _comment_header_start(lines: list[str], key_index: int) -> int:
    """Index of the first line of the comment header introducing ``key_index``.

    Walks back over blank and ``#`` lines and stops at the first line that is
    real content. That is exactly the ``# ====`` section banner these files use,
    so removing a key removes the section that documents it rather than leaving
    a heading over a hole. It cannot run past a neighbouring key, because a key
    is content and stops the walk.

    **Reaching the top of the file means the comment is the DOCUMENT's, not the
    key's, and it is kept.** With no preceding content line there is nothing to
    distinguish a section banner introducing this key from the file's own header,
    and the two need opposite treatment. Unbounded, this deleted a real state
    file's opening block — *"PROJECT STATE — the source of truth for this
    product"* — because ``views_enabled`` happened to be its first key. Returning
    ``key_index`` there removes the key alone, which is the recoverable error of
    the two: a stale banner is a doc nit, a deleted document header is content
    loss in a file the product hand-authored.
    """
    start = key_index
    while start > 0:
        prev = lines[start - 1].strip()
        if prev and not prev.startswith("#"):
            break
        start -= 1
    if start == 0:
        return key_index
    return start


def state_removals(text: str) -> list[dict]:
    """The line spans a state-file repair would delete, with a reason each.

    Returns ``[{key, start, end, reason}]`` — ``start``/``end`` are 0-based and
    ``end`` is exclusive, covering the key (with its block, for a mapping) and
    the comment header above it.
    """
    lines = text.splitlines()
    found: list[dict] = []
    for index, line in enumerate(lines):
        if _is_top_level_key(line, VIEWS_FLAG):
            found.append(
                {
                    "key": VIEWS_FLAG,
                    "start": _comment_header_start(lines, index),
                    "end": index + 1,
                    "reason": "nothing reads this setting any more — a build plan's "
                    "progress checkboxes are written by hand and mean exactly what "
                    "they say",
                }
            )
        elif _is_top_level_key(line, ROLLUPS_KEY):
            found.append(
                {
                    "key": ROLLUPS_KEY,
                    "start": _comment_header_start(lines, index),
                    "end": _block_span(lines, index),
                    "reason": "this block was regenerated from the change log, which "
                    "is where the same information already lives and stays correct",
                }
            )
    # Descending, so applying one removal cannot shift the next one's indices.
    found.sort(key=lambda item: item["start"], reverse=True)
    return found


def apply_state_removals(text: str, removals: list[dict]) -> str:
    """``text`` with each span in ``removals`` deleted.

    Expects the descending order :func:`state_removals` returns; applying in
    ascending order would invalidate every index after the first deletion.
    """
    lines = text.splitlines(keepends=True)
    for item in removals:
        del lines[item["start"] : item["end"]]
    return "".join(lines)


# --- build-plan Status comments ---------------------------------------------


def _status_section_span(lines: list[str]) -> tuple[int, int] | None:
    """0-based ``(start, end)`` of the ``## Status`` section body, or None."""
    for index, line in enumerate(lines):
        if _STATUS_HEADING_RE.match(line.strip()):
            end = index + 1
            while end < len(lines) and not _NEXT_H2_RE.match(lines[end].strip()):
                end += 1
            return index + 1, end
    return None


def _comment_spans(lines: list[str]) -> list[tuple[int, int]]:
    """0-based ``(start, end_exclusive)`` for each HTML comment, multi-line included.

    Line-based rather than a regex over the whole document because the caller
    decides by *position* — which section a comment sits in — and a character
    offset cannot answer that without converting back.

    A comment opened inside inline backticks is not a comment. That is not a
    hypothetical nicety: this plan's own Chunk 05 deliverable contains the text
    ``<!-- views_enabled: … -->`` as inline code describing what to strip, and a
    scanner that did not know the difference would delete the sentence
    specifying its own behaviour.

    **An UNTERMINATED comment yields no span at all**, and that asymmetry is
    deliberate. A reader meeting ``<!--`` with no ``-->`` can afford to assume
    the comment runs to the end of the document; a *writer* cannot, because the
    assumption deletes everything after it. On a malformed plan the earlier
    version removed the opening line through end-of-file — checkboxes, chunks and
    all — which is the worst outcome this operation can produce, reached from
    the input a fleet-wide repair is most likely to meet.

    The cost is stated plainly rather than dressed up: a plan whose comment never
    closes **keeps** a note it should have lost, and nothing announces that. It is
    left exactly as found, which is the direction an error here should point.
    """
    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        position = line.find(_COMMENT_OPEN)
        if position == -1 or _is_backticked(line, position):
            index += 1
            continue
        end = index
        while end < len(lines) and _COMMENT_CLOSE not in lines[end]:
            end += 1
        if end >= len(lines):
            break  # unterminated — claim nothing rather than claim the rest
        spans.append((index, end + 1))
        index = end + 1
    return spans


def _is_backticked(line: str, position: int) -> bool:
    """True when ``position`` in ``line`` falls inside inline-code backticks."""
    return line.count("`", 0, position) % 2 == 1


def plan_comment_findings(text: str) -> list[dict]:
    """The ``views_enabled`` comments in ``text`` that this repair removes.

    **The rule is position, not prose.** A comment inside the ``## Status``
    section is an instruction about the checkboxes in that section, and the
    instruction is now false: it tells its reader the boxes are derived and must
    not be hand-edited, when the boxes are the only reading the session gates
    have. A comment anywhere else mentions the retired flag while saying
    something else — a plan header narrating how the work went, a chunk
    deliverable quoting the flag name — and deleting it would be a scanner
    editing sentences it did not understand.

    Sniffing the prose was tried first and rejected. Any word list that catches
    every real marker ("derived view", "do not hand-edit", "checkboxes flip")
    also catches a plan whose *narrative* uses those words, and the one that
    separated the two on this repo's corpus did it on the accident of an
    intervening "never" — a predicate that passes by luck on the sample you
    tuned it against, which is the failure this plan already paid for once.
    Position is structural, and it is the same "explicit and adjacent" rule the
    removal-qualifier check settled on for the same reason.

    A comment mentioning the flag *outside* the Status section is simply not
    returned. An earlier cut collected those into a second "read these once"
    list, which no caller ever consumed — a channel produced and never read is a
    defect rather than an inefficiency, and the list was noise besides: what it
    collected was plans narrating their own history, which is the one thing here
    that needs no action at all.
    """
    lines = text.splitlines()
    status = _status_section_span(lines)
    if status is None:
        return []
    found: list[dict] = []
    for start, end in _comment_spans(lines):
        if not (status[0] <= start < status[1]):
            continue
        body = "\n".join(lines[start:end])
        if VIEWS_FLAG in body:
            found.append({"start": start, "end": end, "text": body})
    return found


def apply_comment_removals(text: str, removals: list[dict]) -> str:
    """``text`` with each comment span deleted, plus a blank line it orphaned.

    Removing a comment that stood alone between two blank lines otherwise leaves
    a double blank — a diff nobody asked for in a file the operator is about to
    read.
    """
    lines = text.splitlines(keepends=True)
    for item in sorted(removals, key=lambda r: r["start"], reverse=True):
        start, end = item["start"], item["end"]
        if end < len(lines) and not lines[end].strip() and start > 0 and not lines[start - 1].strip():
            end += 1
        del lines[start:end]
    return "".join(lines)


# --- FL3: live plans a human must look at once ------------------------------


def stale_status_reports(artifacts_dir: Path) -> list[dict]:
    """Live plans whose Status was a derived view and has unticked chunks.

    **Report only — this never writes, and the prohibition is the point.** A
    derived Status block is stale on an in-flight chunk, only a session with the
    work in context can say which chunk is actually done, and the session gates
    read that state. So a model must not write it (``data-model.md``: no model
    in a fact's write path). Naming the plan is the most this may do.

    Narrowed to *live* plans: an archived plan's boxes are read by nothing, so
    reporting them would be noise that never goes quiet.

    **Expected yield, stated so it can be judged rather than defended:** it
    names the plans a human must look at once, per repo, during this transition
    — and it prints the plan and the specific chunks, so a reader can settle
    each without re-deriving anything and the check can be retired when it stops
    firing.
    """
    reports: list[dict] = []
    for plan_path, _scope in plan_index.iter_scoped_plan_candidates(artifacts_dir):
        try:
            content = plan_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not plan_comment_findings(content):
            continue  # never carried a derived-Status instruction
        # The finished answer from the module that owns Status parsing — this
        # must not walk the section itself, because walking Status and testing
        # checkboxes IS re-deriving currency, and that derivation has one home.
        unticked = buildplan_refs.unticked_chunk_items(content)
        if unticked:
            reports.append({"path": plan_path, "chunks": unticked})
    return reports


# --- GD2: the flag must not come back ---------------------------------------


def views_flag_present(project_dir: str | Path) -> dict:
    """Whether ``project-state.yaml`` declares the retired flag (GD2).

    **Expected yield:** a repo that reintroduces the flag by copying an older
    state file — which is how a retired setting comes back, not by anyone
    deciding to reinstate it. It names the repo and the key.

    ``unreadable`` is its own answer rather than folding into ``ok``: a check
    that could not run must never report as one that ran and found nothing.
    """
    path = Path(project_dir) / STATE_REL
    if not path.is_file():
        return {"status": "absent", "path": str(path), "line": None}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {"status": "unreadable", "path": str(path), "line": None}
    for index, line in enumerate(text.splitlines(), start=1):
        if _is_top_level_key(line, VIEWS_FLAG):
            return {"status": "present", "path": str(path), "line": index}
    return {"status": "ok", "path": str(path), "line": None}


# --- the repair itself ------------------------------------------------------


def plan_repair(project_dir: str | Path) -> dict:
    """The concrete edit list this repair would perform. Computes, never writes.

    This is the single computation both endings share — :func:`apply_repair`
    executes exactly what a preview rendered, so the two cannot disagree.

    ``edits`` is ``[{path, kind, reason, detail}]``. An empty list means the repo
    is already converged, which is what makes the repair a no-op on a second run
    rather than merely harmless on one — **provided ``unreadable`` is also
    empty.** Files that could not be read are collected there rather than skipped
    silently, because "no edits" and "no edits I could compute" are different
    answers and only one of them means converged.
    """
    root = Path(project_dir)
    edits: list[dict] = []
    unreadable: list[dict] = []

    state_path = root / STATE_REL
    if state_path.is_file():
        try:
            state_text = _read_preserving_newlines(state_path)
        except (OSError, UnicodeDecodeError):
            return {
                "status": "refused",
                "reason": f"{state_path} is not readable as text — nothing was changed",
                "edits": [],
            }
        for removal in state_removals(state_text):
            edits.append(
                {
                    "path": state_path,
                    "kind": "state-key",
                    "reason": removal["reason"],
                    "detail": f"{removal['key']} (lines "
                    f"{removal['start'] + 1}-{removal['end']})",
                    "removal": removal,
                }
            )

    notes_path = root / RELEASE_NOTES_REL
    if notes_path.is_file():
        try:
            notes_text = _read_preserving_newlines(notes_path)
        except (OSError, UnicodeDecodeError) as exc:
            notes_text = FROZEN_MARKER  # no edit is computed for a file we cannot read
            unreadable.append({"path": str(notes_path), "reason": str(exc)})
        if FROZEN_MARKER not in notes_text:
            edits.append(
                {
                    "path": notes_path,
                    "kind": "freeze-notes",
                    "reason": "this file was rebuilt from the change log and is no "
                    "longer rebuilt by anything, so it is labelled as the history it "
                    "is instead of reading as a current record",
                    "detail": "add the archive notice at the top; nothing below it changes",
                }
            )

    artifacts_dir = root / ARTIFACTS_REL
    # Asked separately, because the plan scan swallows an undecodable file by
    # design (one bad file must not blind the map). That is right for a map and
    # wrong for a repair: such a plan never reaches the loop below, so without
    # this the command reported a clean sweep over a file nothing had read.
    unreadable.extend(plan_index.unreadable_candidates(artifacts_dir))
    for plan_path, _scope in plan_index.iter_scoped_plan_candidates(artifacts_dir):
        try:
            content = _read_preserving_newlines(plan_path)
        except (OSError, UnicodeDecodeError) as exc:
            # NOT a silent skip. A plan this cannot read may hold the one piece of
            # residue that still changes behaviour, and "nothing to change" would
            # report it as converged — a check that could not run is otherwise
            # indistinguishable from one that ran and found nothing.
            unreadable.append({"path": str(plan_path), "reason": str(exc)})
            continue
        removals = plan_comment_findings(content)
        if removals:
            edits.append(
                {
                    "path": plan_path,
                    "kind": "plan-comment",
                    "reason": "this note tells the reader the progress checkboxes are "
                    "generated and must not be edited by hand; both halves are now "
                    "wrong, and a reader who believes it will leave finished work "
                    "unmarked",
                    "detail": f"{len(removals)} note(s) in the Status section",
                    "removals": removals,
                }
            )
    return {"status": "ok", "edits": edits, "unreadable": unreadable}


def apply_repair(project_dir: str | Path, plan: dict) -> dict:
    """Execute ``plan``'s edits. Returns ``{status, applied, failed}``.

    Per-file failures are collected rather than raised: one unwritable artifact
    must not abandon the repo half-converged with no report of which half.
    """
    if plan.get("status") != "ok":
        return {"status": "refused", "reason": plan.get("reason", ""), "applied": [], "failed": []}

    by_path: dict[Path, list[dict]] = {}
    for edit in plan["edits"]:
        by_path.setdefault(edit["path"], []).append(edit)

    applied: list[str] = []
    failed: list[dict] = []
    for path, edits in by_path.items():
        try:
            text = _read_preserving_newlines(path)
        except (OSError, UnicodeDecodeError) as exc:
            failed.append({"path": str(path), "reason": str(exc)})
            continue
        for edit in edits:
            if edit["kind"] == "state-key":
                text = apply_state_removals(text, [edit["removal"]])
            elif edit["kind"] == "freeze-notes":
                # Match the file's own endings. The banner is authored with
                # `\n`, and prepending it verbatim to a CRLF document produces a
                # file with two conventions in it — which is a worse outcome than
                # either one, and invisible in a rendered diff.
                banner = FROZEN_BANNER
                if "\r\n" in text:
                    banner = banner.replace("\n", "\r\n")
                text = banner + text
            elif edit["kind"] == "plan-comment":
                text = apply_comment_removals(text, edit["removals"])
        try:
            core.atomic_write_text(path, text, encoding="utf-8", newline="")
        except OSError as exc:
            failed.append({"path": str(path), "reason": str(exc)})
            continue
        applied.append(str(path))
    return {
        "status": "applied" if not failed else "partial",
        "applied": applied,
        "failed": failed,
    }
