"""Evidence transport — review facts travel between clones as git notes (#1052).

The evidence store (:mod:`evidence`) is a file inside ``.git``, which no push
carries; its transported facts reach other clones on ``refs/notes/prawduct``.
This module is the clone-local half of that transport: :func:`attach` writes a
transported fact onto the ref as it is appended (a no-op when the note already
holds it), :func:`reconcile` attaches every fact of this branch whose note is
missing — the repair for an attach that failed or never ran — and
:func:`ingest` appends the note records this clone's store does not hold yet.
Moving the ref between clones (fetch, merge, push) is :mod:`evidence_sync`'s;
nothing here touches a remote.

**The note body is store lines.** Each record is the line
:func:`evidence.envelope_line` writes — one JSON object per line — so a note *is*
store lines on a commit and ingesting one is an append, with nothing to
translate. One reduction is made on the way out (:func:`sent_envelope`): the
note is pushed to the product's remote, where anyone who can fetch the repo
reads it, so ``actor.worktree`` travels as its last path component and
``actor.session`` not at all — the writing clone's store keeps both, and
nothing a verdict or dedupe reads lives in ``actor``. ``git notes append``
separates records with a blank line; the reader skips blank lines and
surrounding whitespace.

**The commit is a locator, the tree is the fact.** A note hangs on the fact's
anchor: a review's ``head_commit``, or its ``dispatch_commit`` when it reviewed
a dirty tree (``head_commit`` null); a resolution rides on the anchor of the
review that verified it; a ``chunk-imported`` fact on the HEAD it was written
at. Verdicts still compose by the tree ids inside each fact, so a squash or
rebase that makes the anchor unreachable loses no verdict — it only takes the
note out of a later bounded ingest.

Errors are return values, never raises (``project-preferences``): a failed
attach leaves the fact in the store and says so; an unreadable note ingests
nothing and says so.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from . import evidence, gitstate

NOTES_REF = "refs/notes/prawduct"

_USAGE = "Usage: prawduct-hook evidence ingest [--all] [--json]"


def attach(project_dir: Path, envelope: object, anchor: "str | None") -> dict:
    """Append ``envelope``'s store line to the note on ``anchor``, unless that
    note already holds it.

    Returns ``{"status": "attached"|"present"|"skipped"|"error", "reason"}``.
    ``present`` when a line of the anchor's note carries the same
    ``(kind, id)`` — so a retry, or a repair run over facts already sent, adds
    nothing. Skipped when the kind is not in :data:`evidence.TRANSPORTED_KINDS`
    or ``anchor`` is not a full object id (``None`` included: a fact with no
    anchor has nowhere to travel; and an abbreviation means the value did not
    come from a fact, while it would reach git's argv). Two local git calls,
    the read and the append; never a network one.
    """
    kind = envelope.get("kind") if isinstance(envelope, dict) else None
    if kind not in evidence.TRANSPORTED_KINDS:
        return {"status": "skipped", "reason": f"kind {kind!r} stays in this clone's store"}
    if not gitstate.is_object_id(anchor):
        return {"status": "skipped", "reason": f"anchor {anchor!r} is not a commit id"}
    # A failed read (no note on the anchor, no ref yet) reads as an empty note:
    # the append below then either writes or reports the real failure.
    rc, out, _err = evidence.run_git(project_dir, "notes", "--ref", NOTES_REF, "show", anchor)
    if rc == 0 and (kind, envelope.get("id")) in _keys_in(out):
        return {"status": "present", "reason": None}
    failed = _append(project_dir, anchor, [envelope])
    if failed is not None:
        return {"status": "error", "reason": failed}
    return {"status": "attached", "reason": None}


def sent_envelope(envelope: dict) -> dict:
    """``envelope`` as a note carries it: identical except the actor's locator
    fields. ``actor.worktree`` is cut to its last path component — the
    reviewing machine's absolute path (``/Users/<name>/…``) is no one else's
    business, while the directory name still tells a reader which tree it was —
    and ``actor.session`` is dropped. ``(kind, id)``, ``ts`` and ``body`` are
    untouched, so dedupe and every verdict read the same fact.

    A reader comparing ``actor.worktree`` against a live path (the round
    counter in ``critic_consolidate``, the latest-review lookup in ``gates``)
    compares an absolute path, which a bare name never equals, so an ingested
    fact never reads as recorded in this worktree. A non-dict ``actor`` or a
    non-string ``worktree`` is left as it is."""
    actor = envelope.get("actor")
    if not isinstance(actor, dict):
        return envelope
    reduced = {k: v for k, v in actor.items() if k != "session"}
    worktree = actor.get("worktree")
    if isinstance(worktree, str):
        reduced["worktree"] = Path(worktree).name
    return {**envelope, "actor": reduced}


def _append(project_dir: Path, anchor: str, envelopes: "list[dict]") -> "str | None":
    """Append the envelopes' lines, as :func:`sent_envelope` reduces them, to
    ``anchor``'s note in one git call; ``None`` on success, else the reason.
    The one writer of note lines — :func:`attach` and :func:`reconcile` both
    come through here."""
    rc, _out, err = evidence.run_git(
        project_dir, "notes", "--ref", NOTES_REF, "append", "-F", "-", anchor,
        input="".join(evidence.envelope_line(sent_envelope(e)) for e in envelopes),
    )
    if rc != 0:
        return f"git notes append on {anchor[:12]} failed ({err or rc})"
    return None


def _keys_in(body: str) -> "set[tuple[str, str]]":
    """The ``(kind, id)`` of every parseable record in one note body."""
    keys: set[tuple[str, str]] = set()
    for raw in body.splitlines():
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and isinstance(record.get("kind"), str) \
                and isinstance(record.get("id"), str):
            keys.add((record["kind"], record["id"]))
    return keys


def tracking_ref(remote: str) -> str:
    """Where a remote's notes are fetched to: ``refs/notes/<remote>/prawduct``.
    A plain ``git fetch`` with the refspec ``evidence configure`` sets fills it;
    :func:`ingest` reads it beside the local ref, so fetched facts reach the
    store without a merge (the merge is what ``evidence sync`` does before it
    pushes)."""
    return f"refs/notes/{remote}/prawduct"


def is_notes_ref(name: str) -> bool:
    """Whether ``name`` is one of the refs that hold the transport: the local
    ``refs/notes/prawduct``, or a remote's tracking ref as
    :func:`tracking_ref` builds it (``refs/notes/<remote>/prawduct``, the
    remote's name possibly holding a slash). The one roster every reader uses
    — ingest, the unsent-facts check and the presence read — so they cannot
    disagree about which refs are "the notes". A sibling such as
    ``refs/notes/<remote>/prawduct-other``, which the pattern refspec also
    fetches, is not one."""
    if name == NOTES_REF:
        return True
    prefix, suffix = "refs/notes/", "/prawduct"
    return (name.startswith(prefix) and name.endswith(suffix)
            and len(name) > len(prefix) + len(suffix))


def _notes_refs(project_dir: Path) -> "list[str] | None":
    """The notes refs this clone holds (:func:`is_notes_ref`), in one
    ``for-each-ref``. Empty when the clone has none; ``None`` when git could
    not answer."""
    rc, out, _err = evidence.run_git(
        project_dir, "for-each-ref", "--format=%(refname)", "refs/notes/"
    )
    if rc != 0:
        return None
    return [name for name in out.split() if is_notes_ref(name)]


def notes_refs_on_disk(common_dir: Path) -> "list[str] | None":
    """The notes refs this clone holds (:func:`is_notes_ref`), read from the
    files under the clone's git common dir — no subprocess, so a surface that
    runs on every status read pays nothing for a clone that has never written
    or fetched a note.

    Loose ref files under ``refs/notes/``, then ``packed-refs``; sorted, each
    once. ``None`` when the clone keeps its refs in a ``reftable``, whose
    binary format this does not read, or a file cannot be read; the caller
    asks git instead (:func:`_notes_refs`)."""
    if (common_dir / "reftable").is_dir():
        return None
    found: set[str] = set()
    notes_dir = common_dir / "refs" / "notes"
    try:
        for path in notes_dir.rglob("prawduct"):
            if path.is_file():
                name = path.relative_to(common_dir).as_posix()
                if is_notes_ref(name):
                    found.add(name)
    except OSError:
        return None
    try:
        packed = (common_dir / "packed-refs").read_text(encoding="utf-8")
    except FileNotFoundError:
        packed = ""
    except (OSError, UnicodeDecodeError):
        return None
    for line in packed.splitlines():
        if line.startswith(("#", "^")):
            continue
        name = line.split(" ", 1)[-1]
        if is_notes_ref(name):
            found.add(name)
    return sorted(found)


def ref_present(common_dir: Path) -> "bool | None":
    """Whether the clone holds any notes ref — the local one or a fetched
    tracking ref — by :func:`notes_refs_on_disk`; ``None`` when that cannot
    tell."""
    refs = notes_refs_on_disk(common_dir)
    return None if refs is None else bool(refs)


def unpushed(project_dir: Path, refs: "list[str]") -> "int | None":
    """How many commits of the local ``refs/notes/prawduct`` the push
    remote's tracking ref does not hold — notes attached here and not yet
    pushed, the leg a failed or skipped push leaves that no note count shows.

    ``refs`` is the clone's notes roster, already in hand. ``None`` (and no
    subprocess) when either ref is absent: with no local ref there is nothing
    to push, and with no tracking ref nothing has been fetched or pushed to
    compare against. Otherwise one ``git remote`` (the push remote's name)
    and one ``git rev-list --count``; ``None`` when git cannot answer."""
    if NOTES_REF not in refs or not any(r != NOTES_REF for r in refs):
        return None
    tracking = tracking_ref(gitstate.push_remote(project_dir))
    if tracking not in refs:
        return None
    rc, out, _err = evidence.run_git(project_dir, "rev-list", "--count", f"{tracking}..{NOTES_REF}")
    if rc != 0 or not out.strip().isdigit():
        return None
    return int(out.strip())


def _branch_commits(project_dir: Path) -> dict:
    """The bound every bounded read and repair shares: the commits in
    ``merge_base..HEAD`` plus the merge base itself, which is where a fresh
    branch's first dirty-tree review anchors.

    ``{"status": "ok", "commits": set}``; ``{"status": "unbounded", "reason"}``
    when no merge base resolves; ``{"status": "error", "reason"}`` when the
    commits cannot be listed."""
    from . import coverage  # noqa: PLC0415 — lazy; coverage pulls in the gate stack

    base = coverage.resolve_merge_base_tree(project_dir)
    if base.get("status") != "ok":
        return {"status": "unbounded", "reason": base.get("reason")}
    merge_base = base["merge_base"]
    rc, out, err = evidence.run_git(project_dir, "rev-list", f"{merge_base}..HEAD")
    if rc != 0:
        return {"status": "error", "reason": f"cannot list the branch's commits ({err or rc})"}
    return {"status": "ok", "commits": set(out.split()) | {merge_base}}


def _read_notes(project_dir: Path, in_range: "set[str] | None",
                refs: "tuple[str, ...]" = (NOTES_REF,)) -> dict:
    """Every note on a commit in ``in_range`` (every note when ``None``) under
    each of ``refs``, read with one listing per ref and one ``cat-file --batch``
    for all of them. The same note blob reached through two refs is read once.

    ``{"status": "ok", "notes": [(commit, body), ...]}`` or
    ``{"status": "error", "reason", "commits"}`` (``commits``: how many notes
    the failed read was for)."""
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for ref in refs:
        rc, out, err = evidence.run_git(project_dir, "notes", "--ref", ref, "list")
        if rc != 0:
            return {"status": "error", "commits": 0, "reason": f"cannot list {ref} ({err or rc})"}
        for line in out.splitlines():
            parts = line.split()
            if len(parts) != 2 or not all(gitstate.is_object_id(p) for p in parts):
                return {"status": "error", "commits": 0,
                        "reason": f"unreadable notes listing line {line!r}"}
            blob, commit = parts
            if (in_range is None or commit in in_range) and (blob, commit) not in seen:
                seen.add((blob, commit))
                pairs.append((blob, commit))
    if not pairs:
        return {"status": "ok", "notes": []}
    blobs = [blob for blob, _commit in pairs]
    rc, out, err = evidence.run_git(
        project_dir, "cat-file", "--batch", input="\n".join(blobs) + "\n", strip=False
    )
    if rc != 0:
        return {"status": "error", "commits": len(blobs), "reason": f"cannot read the notes ({err or rc})"}
    bodies = _split_batch(out, blobs)
    if bodies is None:
        return {"status": "error", "commits": len(blobs),
                "reason": "the notes batch read was not framed as asked"}
    return {"status": "ok", "notes": [(commit, body) for (_b, commit), body in zip(pairs, bodies)]}


def unattached(project_dir: Path, *, known=None, refs: "list[str] | None" = None) -> dict:
    """This branch's transported facts whose note does not hold them.

    The check that sits outside the flow that writes notes: built from the
    store, which holds every fact whatever happened to its attach, and compared
    against the notes as they stand — under every ref :func:`ingest` reads (the
    local ref and each fetched tracking ref), so a fact that arrived on a
    fetched note is not reported as unsent. ``refs`` is that roster when the
    caller already has it; omitted, one ``for-each-ref`` reads it. Returns
    ``{"status": "ok", "missing": [{"anchor", "envelope"}, ...], "reason": None}``,
    ``{"status": "unbounded", "missing": [], "reason"}`` when no merge base
    resolves, or ``{"status": "error", "missing": [], "reason"}``.

    A fact is this branch's when its anchor is in the bound :func:`ingest`
    reads. The anchor is the writer's: a review's :func:`evidence.review_anchor`;
    a resolution's ``verified_by`` review's anchor (a resolution whose review
    is not in the store has none). A ``chunk-imported`` fact does not record
    the HEAD it was attached on, so it counts as this branch's when its
    ``actor.branch`` is the checked-out branch, as missing only when no note in
    the bound holds it, and is re-attached on HEAD — a descendant of the commit
    it was written at, so the same branch carries it.

    ``known`` is a :func:`evidence.read_facts` result; omitted, the store is
    read once. Schema-ahead records are not re-sent: this reader cannot vouch
    for their anchor.
    """
    if known is None:
        known = evidence.read_facts(project_dir)
    if known.get("status") == "error":
        return {"status": "error", "missing": [],
                "reason": f"the store cannot be read ({known.get('reason')})"}
    facts = [f for f in known.get("facts", []) if f.get("kind") in evidence.TRANSPORTED_KINDS]
    if not facts:
        return {"status": "ok", "missing": [], "reason": None}

    bound = _branch_commits(project_dir)
    if bound["status"] != "ok":
        return {"status": bound["status"], "missing": [],
                "reason": f"no branch range to bound the check ({bound['reason']})"}
    commits = bound["commits"]

    anchors = {
        f["id"]: evidence.review_anchor(f.get("body"))
        for f in facts if f["kind"] == "review"
    }
    head = branch = None
    candidates: list[tuple[str | None, dict]] = []  # (anchor or None for "any note", fact)
    for fact in facts:
        body = fact.get("body") if isinstance(fact.get("body"), dict) else {}
        if fact["kind"] == "review":
            anchor = anchors.get(fact["id"])
        elif fact["kind"] == "resolution":
            anchor = anchors.get(body.get("verified_by"))
        else:
            if head is None:
                rc, out, err = evidence.run_git(
                    project_dir, "rev-parse", "HEAD", "--abbrev-ref", "HEAD"
                )
                lines = out.splitlines() if rc == 0 else []
                if len(lines) != 2:
                    return {"status": "error", "missing": [],
                            "reason": f"cannot read HEAD ({err or rc})"}
                head, branch = lines
            actor = fact.get("actor") if isinstance(fact.get("actor"), dict) else {}
            if actor.get("branch") == branch:
                candidates.append((None, fact))
            continue
        if anchor in commits:
            candidates.append((anchor, fact))
    if not candidates:
        return {"status": "ok", "missing": [], "reason": None}

    if refs is None:
        refs = _notes_refs(project_dir)
        if refs is None:
            return {"status": "error", "missing": [], "reason": "git could not list refs/notes/"}
    held: dict[str, set[tuple[str, str]]] = {}
    if refs:
        read = _read_notes(project_dir, commits, tuple(refs))
        if read["status"] != "ok":
            return {"status": "error", "missing": [], "reason": read["reason"]}
        for commit, body in read["notes"]:
            held.setdefault(commit, set()).update(_keys_in(body))
    anywhere = set().union(*held.values()) if held else set()

    missing = []
    for anchor, fact in candidates:
        key = (fact["kind"], fact["id"])
        if anchor is None:
            if key not in anywhere:
                missing.append({"anchor": head, "envelope": fact})
        elif key not in held.get(anchor, set()):
            missing.append({"anchor": anchor, "envelope": fact})
    return {"status": "ok", "missing": missing, "reason": None}


def reconcile(project_dir: Path, *, known=None) -> dict:
    """Attach every fact :func:`unattached` finds, one append per anchor.

    Returns ``{"status": "ok"|"unbounded"|"error", "attached": int,
    "missing": int, "reason"}``: ``missing`` is what was found, ``attached``
    what was written before any failure. Local only; :mod:`evidence_sync` runs
    it before a push so a fact whose note was never written still travels.
    """
    found = unattached(project_dir, known=known)
    missing = found["missing"]
    if found["status"] != "ok":
        return {"status": found["status"], "attached": 0, "missing": 0, "reason": found["reason"]}
    by_anchor: dict[str, list[dict]] = {}
    for item in missing:
        by_anchor.setdefault(item["anchor"], []).append(item["envelope"])
    attached = 0
    for anchor, envelopes in by_anchor.items():
        failed = _append(project_dir, anchor, envelopes)
        if failed is not None:
            return {"status": "error", "attached": attached, "missing": len(missing),
                    "reason": f"{failed}; {attached} of {len(missing)} attached before it"}
        attached += len(envelopes)
    return {"status": "ok", "attached": attached, "missing": len(missing), "reason": None}


def ingest(project_dir: Path, *, bound: bool = True, known=None) -> dict:
    """Append every note record this clone's store does not hold yet.

    Returns ``{"status": "ok"|"error", "appended", "seen", "commits", "reason"}``:
    ``seen`` counts well-formed records read, ``commits`` the annotated commits
    whose notes were read, and ``reason`` says what was skipped and why (``None``
    when nothing was).

    ``bound`` (the session-start default) reads only notes on the branch's own
    commits — ``merge_base..HEAD`` plus the merge base itself, which is where a
    fresh branch's first dirty-tree review anchors — so the archive is never
    walked. When no merge base resolves it is ``ok`` with nothing appended and
    the reason; ``bound=False`` reads every note. ``known`` is a
    :func:`evidence.read_facts` result to dedupe against; omitted, the store is
    read once, and only if there is a note to read.

    Reads the local ``refs/notes/prawduct`` and every fetched tracking ref
    (``refs/notes/<remote>/prawduct``), so a configured refspec plus a plain
    ``git fetch`` is enough for another clone's facts to arrive. With no notes
    ref the cost is one ``git for-each-ref``. Otherwise: one listing per ref, at
    most one ``rev-list``, and one ``cat-file --batch`` for every note however
    many there are.

    Only :data:`evidence.TRANSPORTED_KINDS` are taken from a note; a schema-ahead
    record is taken whatever its kind, so the newer writer's block fires here.
    """
    refs = _notes_refs(project_dir)
    if refs is None:
        return _result("error", reason="git could not list refs/notes/")
    if not refs:
        return _result("ok", reason=f"no {NOTES_REF} (or a fetched tracking ref) in this clone — nothing to ingest")

    in_range: "set[str] | None" = None
    if bound:
        branch = _branch_commits(project_dir)
        if branch["status"] == "unbounded":
            return _result(
                "ok",
                reason=f"no branch range to bound the read ({branch['reason']}); "
                "`evidence ingest --all` reads every note",
            )
        if branch["status"] != "ok":
            return _result("error", reason=branch["reason"])
        in_range = branch["commits"]

    read = _read_notes(project_dir, in_range, tuple(refs))
    if read["status"] != "ok":
        return _result("error", commits=read["commits"], reason=read["reason"])
    if not read["notes"]:
        return _result("ok", reason=None)
    bodies = [body for _commit, body in read["notes"]]
    annotated = len(bodies)

    records, skipped = _parse(bodies)
    if known is None:
        known = evidence.read_facts(project_dir)
    if known.get("status") == "error":
        return _result(
            "error", seen=len(records), commits=annotated,
            reason=f"the store cannot be read to dedupe against ({known.get('reason')})",
        )
    held = {(f.get("kind"), f.get("id")) for f in known.get("facts", [])}
    held |= {(s.get("kind"), s.get("id")) for s in known.get("schema_ahead", [])}

    appended = 0
    for record in records:
        key = (record["kind"], record["id"])
        if key in held:
            continue
        written = evidence.append_envelope(project_dir, record)
        if written.get("status") != "appended":
            return _result(
                "error", appended=appended, seen=len(records), commits=annotated,
                reason=f"store append failed after {appended} record(s) ({written.get('reason')})",
            )
        held.add(key)
        appended += 1
    return _result(
        "ok", appended=appended, seen=len(records), commits=annotated,
        reason="; ".join(skipped) or None,
    )


def _result(status: str, *, appended: int = 0, seen: int = 0, commits: int = 0,
            reason: "str | None") -> dict:
    return {"status": status, "appended": appended, "seen": seen, "commits": commits,
            "reason": reason}


def _split_batch(out: str, blobs: "list[str]") -> "list[str] | None":
    """Each blob's content from one ``git cat-file --batch`` reply, in the order
    asked; ``None`` when the reply is not framed as asked.

    Framed by the header line git writes before each object
    (``<id> blob <size>``) rather than by ``<size>``: the reply arrives as
    decoded text with newlines normalised, so a byte count no longer measures
    it, while the next header is known in advance — the next id asked for. A
    ``missing`` reply yields an empty body (that note was gone by the read)."""
    lines = out.split("\n")
    bodies: list[str] = []
    i = 0
    for n, blob in enumerate(blobs):
        if i >= len(lines):
            return None
        header = lines[i]
        i += 1
        if header == f"{blob} missing":
            bodies.append("")
            continue
        if re.fullmatch(rf"{re.escape(blob)} blob \d+", header) is None:
            return None
        nxt = blobs[n + 1] if n + 1 < len(blobs) else None
        start = i
        while i < len(lines) and not (
            nxt is not None and (lines[i] == f"{nxt} missing" or lines[i].startswith(f"{nxt} blob "))
        ):
            i += 1
        bodies.append("\n".join(lines[start:i]))
    return bodies


def _parse(bodies: "list[str]") -> "tuple[list[dict], list[str]]":
    """Records to consider from the note bodies, and a phrase per skipped class."""
    records: list[dict] = []
    malformed = 0
    local = 0
    newest = max(evidence.SUPPORTED_SCHEMAS)
    for body in bodies:
        for raw in body.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if not _is_envelope(record):
                malformed += 1
                continue
            schema = record["schema"]
            if schema <= newest:
                if schema not in evidence.SUPPORTED_SCHEMAS:
                    malformed += 1
                    continue
                if record["kind"] not in evidence.TRANSPORTED_KINDS:
                    local += 1
                    continue
            records.append(record)
    skipped = []
    if malformed:
        skipped.append(f"{malformed} malformed note line(s) skipped")
    if local:
        skipped.append(f"{local} record(s) of a kind not transported skipped")
    return records, skipped


def _is_envelope(record: object) -> bool:
    if not isinstance(record, dict):
        return False
    schema = record.get("schema")
    return (
        isinstance(schema, int) and not isinstance(schema, bool)
        and isinstance(record.get("kind"), str) and bool(record["kind"].strip())
        and isinstance(record.get("id"), str) and bool(record["id"].strip())
        and isinstance(record.get("body"), dict)
    )


def ingest_cmd(project_dir: Path, argv: "list[str]", *, usage: str = _USAGE) -> int:
    """``prawduct-hook evidence ingest [--all] [--json]``: 0 when the ingest
    ran (appending nothing included), 1 on an error or a bad argument."""
    unknown = [a for a in argv if a not in ("--all", "--json")]
    if unknown:
        print(f"evidence ingest: unexpected argument {unknown[0]!r}\n{usage}", file=sys.stderr)
        return 1
    result = ingest(project_dir, bound="--all" not in argv)
    if "--json" in argv:
        print(json.dumps(result, sort_keys=True))
    else:
        scope = "every note" if "--all" in argv else "this branch's commits"
        print(
            f"evidence ingest: appended {result['appended']} of {result['seen']} record(s) "
            f"from notes on {result['commits']} commit(s) ({scope})"
        )
        if result["reason"]:
            failed = result["status"] != "ok"
            print(f"  {result['reason']}", file=sys.stderr if failed else sys.stdout)
    return 0 if result["status"] == "ok" else 1
