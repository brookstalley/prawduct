"""Evidence transport — review facts travel between clones as git notes (#1052).

The evidence store (:mod:`evidence`) lives inside ``.git`` and is never pushed,
so every clone but the one that ran a review sees no coverage. This module is
the clone-local half of the transport: :func:`attach` writes a transported fact
onto ``refs/notes/prawduct`` as it is appended, and :func:`ingest` appends the
note records this clone's store does not hold yet. Moving the ref between
clones (fetch, merge, push) is a separate step; nothing here touches a remote.

**The note body is store lines.** Each record is exactly the line
:func:`evidence.envelope_line` writes — one JSON object per line — so a note *is*
store lines on a commit and ingesting one is an append, with nothing to
translate. ``git notes append`` separates records with a blank line; the reader
skips blank lines and surrounding whitespace.

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




def attach(project_dir: Path, envelope: dict, anchor: str) -> dict:
    """Append ``envelope``'s store line to the note on ``anchor``.

    Returns ``{"status": "attached"|"skipped"|"error", "reason"}``. Skipped
    when the kind is not in :data:`evidence.TRANSPORTED_KINDS` or ``anchor`` is
    not a full object id (it reaches git's argv, and an abbreviation means it
    did not come from a fact). One local git call; never a network one.
    """
    kind = envelope.get("kind") if isinstance(envelope, dict) else None
    if kind not in evidence.TRANSPORTED_KINDS:
        return {"status": "skipped", "reason": f"kind {kind!r} stays in this clone's store"}
    if not gitstate.is_object_id(anchor):
        return {"status": "skipped", "reason": f"anchor {anchor!r} is not a commit id"}
    rc, _out, err = evidence.run_git(
        project_dir, "notes", "--ref", NOTES_REF, "append", "-F", "-", anchor,
        input=evidence.envelope_line(envelope),
    )
    if rc != 0:
        return {"status": "error", "reason": f"git notes append on {anchor[:12]} failed ({err or rc})"}
    return {"status": "attached", "reason": None}


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

    With no notes ref the cost is one ``git rev-parse``. Otherwise: one notes
    listing, at most one ``rev-list``, and one ``cat-file --batch`` for every
    note however many there are.

    Only :data:`evidence.TRANSPORTED_KINDS` are taken from a note; a schema-ahead
    record is taken whatever its kind, so the newer writer's block fires here.
    """
    rc, _out, _err = evidence.run_git(project_dir, "rev-parse", "-q", "--verify", NOTES_REF)
    if rc != 0:
        return _result("ok", reason=f"no {NOTES_REF} in this clone — nothing to ingest")

    in_range: "set[str] | None" = None
    if bound:
        from . import coverage  # noqa: PLC0415 — lazy; coverage pulls in the gate stack

        base = coverage.resolve_merge_base_tree(project_dir)
        if base.get("status") != "ok":
            return _result(
                "ok",
                reason=f"no branch range to bound the read ({base.get('reason')}); "
                "`evidence ingest --all` reads every note",
            )
        merge_base = base["merge_base"]
        rc, out, err = evidence.run_git(project_dir, "rev-list", f"{merge_base}..HEAD")
        if rc != 0:
            return _result("error", reason=f"cannot list the branch's commits ({err or rc})")
        in_range = set(out.split()) | {merge_base}

    rc, out, err = evidence.run_git(project_dir, "notes", "--ref", NOTES_REF, "list")
    if rc != 0:
        return _result("error", reason=f"cannot list {NOTES_REF} ({err or rc})")
    blobs: list[str] = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) != 2 or not all(gitstate.is_object_id(p) for p in parts):
            return _result("error", reason=f"unreadable notes listing line {line!r}")
        blob, commit = parts
        if in_range is None or commit in in_range:
            blobs.append(blob)
    if not blobs:
        return _result("ok", reason=None)

    rc, out, err = evidence.run_git(
        project_dir, "cat-file", "--batch", input="\n".join(blobs) + "\n", strip=False
    )
    if rc != 0:
        return _result("error", commits=len(blobs), reason=f"cannot read the notes ({err or rc})")
    bodies = _split_batch(out, blobs)
    if bodies is None:
        return _result("error", commits=len(blobs), reason="the notes batch read was not framed as asked")

    records, skipped = _parse(bodies)
    if known is None:
        known = evidence.read_facts(project_dir)
    if known.get("status") == "error":
        return _result(
            "error", seen=len(records), commits=len(blobs),
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
                "error", appended=appended, seen=len(records), commits=len(blobs),
                reason=f"store append failed after {appended} record(s) ({written.get('reason')})",
            )
        held.add(key)
        appended += 1
    return _result(
        "ok", appended=appended, seen=len(records), commits=len(blobs),
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
