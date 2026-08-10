"""End of life for a build plan: completion frontmatter, then a move into ``archive/``.

**A completed build plan is never deleted.** It is stamped with what became of
it and moved out of the live artifacts directory. Both halves, not either: the
frontmatter makes the document self-describing when someone opens it directly
(a moved file arrives by link, by search, by grep — not always through its
directory), and the move keeps the live directory an answer to "what is in
flight" rather than a pile that has to be read to be sorted.

**Two terminal states, not one.** *Completed* is the easy case. *Superseded* —
work stopped, descoped, or absorbed elsewhere — is the one that matters: a
half-finished dead plan can never satisfy "all boxes ticked", so a lifecycle
with only the first state leaves exactly those plans sitting in live
``artifacts/`` forever, reading as active. That is the confusion this operation
exists to remove, and it is the common case rather than a corner.

**Checkbox state is not a precondition and is not corrected here.** Nothing
reads an archived plan's boxes — the gates that do read them resolve the *live*
plan — so ticking them on the way in would be ceremony with no consumer, and it
would put a writer where the rule is that only a session with the work in
context may say which chunk is done. An archived plan may carry unticked boxes;
that is a fact about how the work ended, and preserving it is the point.

**The release copy is a permitted duplicate, and the reason is narrow.** The
change-log ``release=`` tag stays canonical — it is what the release gate reads.
The copy recorded here is legitimate because a shipped version number is
*immutable*: a copy of it cannot drift. A count or a chunk id can, which is why
those stay out. Two copies of an immutable fact is self-containment; two copies
of a mutable one is the drift that rule exists to prevent.

Return convention follows the package: functions report outcomes as dicts
carrying ``status`` (and ``reason`` when refused) rather than raising, and the
CLI boundary turns those into exit codes.
"""

from __future__ import annotations

from pathlib import Path

from . import plan_index


#: The terminal state of a plan that shipped every chunk.
COMPLETED = "completed"
#: The terminal state of a plan whose work stopped, was descoped, or was
#: absorbed elsewhere. Distinguished from :data:`COMPLETED` because the two need
#: different things said about them: one names the release that carried it, the
#: other names what replaced it or why it stopped.
SUPERSEDED = "superseded"
TERMINAL_STATES = (COMPLETED, SUPERSEDED)

#: Frontmatter keys this operation writes. Named as constants because the reader
#: (:func:`read_completion`) and the writer (:func:`apply_completion_frontmatter`)
#: must agree, and a string literal in both is how they stop agreeing.
LIFECYCLE_KEY = "lifecycle"
ARCHIVED_KEY = "archived"
#: NOT ``release``. A release plan already carries ``release: vX.Y.Z`` meaning
#: *the release this plan governs*, which is a different fact from *the release
#: that carried this work* — and release plans are among the artifacts most
#: likely to be archived, since the gate that reads them searches the archive by
#: design. Claiming the shorter name would have made re-stamping strip a key with
#: a meaning this operation knows nothing about: silent loss, on the operation
#: whose entire purpose is to stop losing plans.
RELEASE_KEY = "released_in"
SUPERSEDED_BY_KEY = "superseded_by"
MAINTAINED_KEY = "maintained"

#: Written in document order, so two plans archived a year apart still read the
#: same way. `lifecycle` leads because it is the question the reader arrived with.
_KEY_ORDER = (LIFECYCLE_KEY, ARCHIVED_KEY, RELEASE_KEY, SUPERSEDED_BY_KEY, MAINTAINED_KEY)

#: The prose half of "no longer maintained". The frontmatter states it as data;
#: this states it to the human who opened the file and will otherwise read a
#: future-tense build plan as a description of present intent. A blockquote so it
#: survives rendering as an interruption rather than as body text.
NOT_MAINTAINED_BANNER = (
    "> **Archived — no longer maintained.** This plan records what was built, "
    "not what will be. Do not edit it to reflect later changes; write those "
    "where they are true."
)


def _quote_if_needed(value: str) -> str:
    """YAML-safe scalar for the values this writer emits.

    Deliberately minimal rather than a YAML serializer: the codebase carries no
    YAML dependency, and every value here is operator-supplied free text on one
    line. Quote when the value could otherwise change the parse.

    **The pairing with :func:`_parse_scalar` is the contract, not the quoting
    rule on its own.** Anything this leaves bare must read back byte-identical,
    so the trigger set covers every character the reader treats as structure:
    an indicator character, ``:``, ``#`` anywhere (the reader strips a comment
    from a bare value), a quote or backslash (which the reader unescapes), and
    surrounding whitespace. An earlier version triggered only on ``": "`` and
    ``" #"``, which let ``absorbed "here"`` through bare — and it read back as
    ``absorbed "here`` because the reader's quote-stripping ate the real one.
    """
    needs = (
        not value
        or value[0] in "-?:,[]{}#&*!|>'\"%@`"
        or ":" in value
        or "#" in value
        or '"' in value
        or "'" in value
        or "\\" in value
        or value != value.strip()
    )
    if not needs:
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _parse_scalar(raw: str) -> str:
    """The value :func:`_quote_if_needed` wrote, recovered exactly.

    Comment-stripping applies to a BARE value only. Doing it first — the shape
    every other reader in this codebase uses, because their values cannot
    contain a ``#`` — would truncate a quoted ``superseded_by`` at the first
    ``#`` inside it, and that field is operator free text.

    An unterminated quote returns what it has rather than raising: a
    hand-corrupted archived plan should read as slightly wrong, not make a
    caller fail.
    """
    raw = raw.strip()
    if raw[:1] == '"':
        out: list[str] = []
        i = 1
        while i < len(raw):
            char = raw[i]
            if char == "\\" and i + 1 < len(raw):
                out.append(raw[i + 1])
                i += 2
                continue
            if char == '"':
                break
            out.append(char)
            i += 1
        return "".join(out)
    if raw[:1] == "'":
        end = raw.find("'", 1)
        return raw[1:end] if end != -1 else raw[1:]
    return raw.split("#", 1)[0].rstrip()


def completion_fields(
    *,
    state: str,
    date: str,
    release: str | None = None,
    superseded_by: str | None = None,
) -> dict[str, str]:
    """The frontmatter keys recording a terminal state, in document order.

    ``release`` is omitted rather than written empty when the product does not
    version — an empty key is a claim that the field was considered and found
    blank, which is not the same as "this product has no releases".
    """
    fields: dict[str, str] = {LIFECYCLE_KEY: state, ARCHIVED_KEY: date}
    if release:
        fields[RELEASE_KEY] = release
    if superseded_by:
        fields[SUPERSEDED_BY_KEY] = superseded_by
    fields[MAINTAINED_KEY] = "false"
    return {key: fields[key] for key in _KEY_ORDER if key in fields}


def apply_completion_frontmatter(
    content: str,
    *,
    state: str,
    date: str,
    release: str | None = None,
    superseded_by: str | None = None,
) -> str:
    """``content`` with completion keys in its frontmatter and the banner below it.

    Idempotent on the keys: re-archiving replaces this operation's own keys in
    place rather than appending a second copy, so a plan corrected from
    *superseded* to *completed* ends with one answer, not two contradicting ones
    in the order a parser happens to read.

    A plan with no frontmatter block gets one, inserted after any leading HTML
    comment header — the position :mod:`plan_index` already skips to when
    looking for a block, so the block this writes is one the readers can find. A
    plan whose frontmatter is unterminated reads as *absent* to those readers, so
    it is treated as absent here too; writing into a block nothing can parse
    would produce a file that claims to be archived and does not say so to any
    consumer.
    """
    fields = completion_fields(
        state=state, date=date, release=release, superseded_by=superseded_by
    )
    new_lines = [f"{key}: {_quote_if_needed(value)}" for key, value in fields.items()]

    lines = content.splitlines()
    span = plan_index.frontmatter_span(content)
    if span is None:
        insert_at = plan_index.frontmatter_body_start(lines)
        block = ["---", *new_lines, "---"]
        lines[insert_at:insert_at] = block
        body_end = insert_at + len(block)
    else:
        open_i, close_i = span
        kept = [line for line in lines[open_i + 1 : close_i] if not _is_own_key(line)]
        lines[open_i + 1 : close_i] = [*kept, *new_lines]
        # The closing fence sits at open_i + 1 + len(kept) + len(new_lines);
        # the banner goes on the line after it.
        body_end = open_i + len(kept) + len(new_lines) + 2

    if NOT_MAINTAINED_BANNER not in content:
        # A blank line on each side, except where the document already supplies
        # one — a blockquote run together with the heading below it stops being
        # a blockquote, and two blank lines are a diff nobody asked for.
        trailer = [] if lines[body_end : body_end + 1] == [""] else [""]
        lines[body_end:body_end] = ["", NOT_MAINTAINED_BANNER, *trailer]

    # A markdown file ends with a newline; one that does not is the anomaly, and
    # normalizing here keeps re-archiving byte-idempotent instead of appending a
    # newline's worth of diff every pass.
    return "\n".join(lines).rstrip("\n") + "\n"


def _is_own_key(line: str) -> bool:
    """True for a top-level frontmatter line this writer owns.

    Indented lines are excluded: a nested ``release:`` under some other key
    belongs to that key, and stripping it would silently edit a structure this
    operation knows nothing about.
    """
    if line[:1] in (" ", "\t"):
        return False
    return any(line.startswith(f"{key}:") for key in _KEY_ORDER)


def read_completion(content: str) -> dict[str, str] | None:
    """The completion keys recorded in ``content``, or ``None`` if it records none.

    The round-trip partner of :func:`apply_completion_frontmatter`, and the
    predicate a reader uses to answer "is this current?" without inferring it
    from the file's location — a plan can be read from a link or a grep hit, and
    "it was under ``archive/``" is not information the reader has then.

    **Its production consumer is :func:`archive_plan`'s re-archive refusal.** That
    is worth naming because the function shipped without one: every other
    archive-awareness decision in the tree is path-based, so for one chunk this
    was a producer whose only caller was its own test — the produced-and-never-
    consumed shape this codebase treats as a defect rather than an inefficiency.
    The consumer that closed it is the one place the *content* of the stamp
    matters rather than its location: a plan already recording ``superseded``
    must not be silently re-stamped ``completed`` by a sweep.
    """
    fm = plan_index.frontmatter_lines(content)
    if fm is None:
        return None
    found: dict[str, str] = {}
    for line in fm:
        if line[:1] in (" ", "\t"):
            continue
        for key in _KEY_ORDER:
            prefix = f"{key}:"
            if line.startswith(prefix):
                found[key] = _parse_scalar(line[len(prefix) :])
                break
    if LIFECYCLE_KEY not in found:
        return None
    return found


def archive_destination(plan_path: Path, artifacts_dir: Path) -> Path:
    """Where ``plan_path`` lands: an ``archive/`` beside it, not one central pile.

    Beside it, because plan layout is the repo's choice and this operation must
    not flatten it: a repo nesting ``plans/<id>/build-plan.md`` would otherwise
    have every one of its plans collapse onto the single name
    ``artifacts/archive/build-plan.md`` and collide on the first archival. The
    scanners find an ``archive`` component at any depth, so a sibling archive is
    as discoverable as a top-level one.
    """
    parent = plan_path.parent
    if parent != artifacts_dir and parent.is_relative_to(artifacts_dir):
        return parent / plan_index.ARCHIVE_DIR_NAME / plan_path.name
    return artifacts_dir / plan_index.ARCHIVE_DIR_NAME / plan_path.name


def archive_plan(
    plan_path: Path,
    artifacts_dir: Path,
    *,
    state: str,
    date: str,
    release: str | None = None,
    superseded_by: str | None = None,
) -> dict[str, object]:
    """Stamp ``plan_path`` with its terminal state and move it into the archive.

    Returns ``{"status": "archived", "source": …, "destination": …, "fields": …}``
    on success, or ``{"status": "refused", "reason": …}``. It **refuses** rather
    than half-completing, because the two halves are one change: a plan stamped
    but not moved still reads as live to every directory scan, and a plan moved
    but not stamped answers "is this current?" only to a reader who noticed the
    path. Writing the stamped copy at the destination and unlinking the source
    last means an interruption leaves the live plan intact rather than gone.

    ``date`` is a parameter with no default and no clock read here: the caller
    owns the calendar, which is what lets this be tested without freezing time
    and what lets a backfill stamp a plan with the date it actually finished
    rather than the date someone got around to filing it.
    """
    if state not in TERMINAL_STATES:
        return {
            "status": "refused",
            "reason": f"unknown terminal state {state!r} (expected one of "
            f"{', '.join(TERMINAL_STATES)})",
        }
    if state == SUPERSEDED and not superseded_by:
        return {
            "status": "refused",
            "reason": "a superseded plan must name what replaced it or why it "
            "stopped — an unexplained dead plan is the thing archiving is "
            "supposed to stop producing",
        }
    if not plan_path.is_file():
        return {"status": "refused", "reason": f"no such plan: {plan_path}"}
    # This moves a file and then UNLINKS the original, so "is it a plan?" has to
    # be asked before the move, not assumed from the caller's good intentions.
    # The path is not always a keystroke: the PR flow has an *agent* supply it,
    # and `archive-plan README.md` would otherwise stamp, move and unlink at
    # exit 0. Containment is the cheap half of the test and the half that cannot
    # be wrong — a file outside the artifacts tree is not this operation's to move.
    # `resolve()` on BOTH sides before comparing, because `is_relative_to` is a
    # comparison of path PARTS and never collapses `..`. The first cut of this
    # guard compared them lexically, so
    # `archive-plan .prawduct/artifacts/../../README.md` satisfied it, took the
    # matching lexical branch in `archive_destination`, wrote the stamped copy
    # outside the tree and unlinked the original — at exit 0. A containment check
    # that a single `..` walks through is not a containment check.
    try:
        resolved_plan = plan_path.resolve()
        resolved_artifacts = artifacts_dir.resolve()
    except OSError as exc:  # unresolvable symlink chain: refuse, never guess
        return {"status": "refused", "reason": f"cannot resolve {plan_path}: {exc}"}
    if not resolved_plan.is_relative_to(resolved_artifacts):
        return {
            "status": "refused",
            "reason": f"{plan_path} is not under {artifacts_dir} — archiving moves "
            "and then deletes the original, so it only ever acts inside the "
            "artifacts directory",
        }
    # A plan already carrying a terminal state is refused rather than re-stamped:
    # re-archiving in place is how a `superseded` record silently becomes
    # `completed`, and the frontmatter is the whole content of the record.
    try:
        existing = read_completion(plan_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        existing = None
    if existing:
        return {
            "status": "refused",
            "reason": f"{plan_path} already records lifecycle "
            f"{existing.get(LIFECYCLE_KEY)!r} (archived {existing.get(ARCHIVED_KEY)}) "
            "— it has an end of life already; move it by hand if that record is wrong",
        }

    destination = archive_destination(plan_path, artifacts_dir)
    if destination.exists():
        return {
            "status": "refused",
            "reason": f"{destination} already exists — archiving would overwrite an "
            "earlier plan of the same name; rename one of them first",
        }

    try:
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {"status": "refused", "reason": f"cannot read {plan_path}: {exc}"}

    stamped = apply_completion_frontmatter(
        content, state=state, date=date, release=release, superseded_by=superseded_by
    )
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(stamped, encoding="utf-8")
        plan_path.unlink()
    except OSError as exc:
        return {"status": "refused", "reason": f"cannot archive {plan_path}: {exc}"}

    return {
        "status": "archived",
        "source": plan_path,
        "destination": destination,
        "fields": completion_fields(
            state=state, date=date, release=release, superseded_by=superseded_by
        ),
    }
