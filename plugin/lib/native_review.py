"""The paired native review's record (#1130).

On a development build, ``critic-begin`` pairs every boundary review, and a
sample of inner ``chunk`` and ``verify-resolutions`` reviews, with the host's
native ``/code-review`` over the same interval (the pairing decision, the range
and the manifest block are ``critic_consolidate.native_review_pairing``,
``native_review_range`` and ``native_review_block``). This module is what
happens to the native run after that:

- **At dispatch** :func:`write_dispatch` writes a sidecar beside the text the
  wrapper will write. The manifest cannot carry the run's record: consolidation
  deletes it on success, and the native run may finish after that.
- **When the wrapper finishes** it runs ``native-review record <review id>``:
  :func:`record` reads the sidecar and the text and appends ONE ``native.review``
  ledger event — counts, the range, the clocked duration, the file and line of
  each finding, never the finding text (the text stays in the per-clone,
  gitignored file).
- **When a boundary review consolidates** :func:`next_action_clause` tells the
  builder, in the same ``NEXT-ACTION`` sentence that already travels to them,
  that a second list exists and how to read it — the builder works from both
  (#1130 step 4). It gates nothing. An inner run's list is not put to the
  builder: the boundary pairing puts the same code's native findings to them,
  and a second unrated list beside an inner pass would manufacture rounds.

- **Where it runs** (#1177): the host review checks out what it reads, and
  forked in the session's checkout it detached the session's HEAD. So the
  wrapper is dispatched in a worktree of its own, and runs
  ``native-review prepare`` first: :func:`prepare` refuses in the session's
  checkout and otherwise detaches the wrapper's OWN tree at the reviewed head,
  where the review then reads the reviewed code. :func:`record` returns that
  tree to the commit it started on and reports, through ``head_guard``, a
  session HEAD that left its branch anyway.

The native review returns prose. At ``high`` its findings arrive as a JSON array
(``file``, ``line``, ``summary``, ``failure_scenario``); an empty run prints
``(none)``. :func:`parse_findings` reads those two shapes and says ``None`` —
not countable — for anything else, rather than guessing a number.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .core import atomic_write_text

#: The per-clone, gitignored home of every native text and sidecar, under
#: ``.prawduct/``. A session path (``core.GITIGNORE_ENTRIES``): the wrapper
#: writes here while the Critic's reviewers still run, and consolidation exempts
#: session paths from its changed-tree refusal by path.
DIRNAME = ".native-reviews"

#: How the builder reads a native review's text. Named once, here, because the
#: ``NEXT-ACTION`` clause and the command's own usage line both say it.
SHOW_COMMAND = "prawduct-hook native-review show"

#: A review id this module will turn into a path: the minted shape's alphabet,
#: with no separator or dot that could leave :data:`DIRNAME`.
_SAFE_ID = re.compile(r"rev-[A-Za-z0-9-]+")

_NONE_LINE = re.compile(r"^\s*\(none\)\s*$", re.MULTILINE)


def reviews_dir(prawduct_dir: Path) -> Path:
    return Path(prawduct_dir) / DIRNAME


def is_safe_id(review_id) -> bool:
    return isinstance(review_id, str) and bool(_SAFE_ID.fullmatch(review_id))


def text_path(prawduct_dir: Path, review_id: str) -> Path:
    return reviews_dir(prawduct_dir) / f"{review_id}.md"


def sidecar_path(prawduct_dir: Path, review_id: str) -> Path:
    return reviews_dir(prawduct_dir) / f"{review_id}.json"


def write_dispatch(prawduct_dir: Path, manifest: dict, session_model: "str | None") -> Path:
    """Write the sidecar for a manifest that pairs a native review: everything
    :func:`record` needs once the manifest is gone. The model recorded is the
    one the wrapper runs on — the block's, else the session's it inherits."""
    block = manifest["native_review"]
    sidecar = {
        "review_id": manifest["id"],
        "mode": block.get("mode", "cumulative"),
        "stage": manifest.get("stage"),
        "synthetic_range": bool(block.get("synthetic_range")),
        "level": block["level"],
        "args": block["args"],
        "model": block.get("model") or session_model,
        "dispatched_at": block["dispatched_at"],
        "scope": manifest.get("scope"),
        "base_tree": manifest.get("base_tree"),
        "head_tree": manifest.get("head_tree"),
        "base_commit": manifest.get("base_commit"),
        "head_commit": manifest.get("head_commit"),
        # The session's checkout and the branch it was on at dispatch: where
        # `prepare` must never run, and the branch `head_guard` checks HEAD is
        # still on (#1177).
        "worktree": manifest.get("worktree"),
        "session_branch": manifest.get("branch"),
    }
    path = sidecar_path(prawduct_dir, manifest["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    # The directory ignores itself: a repo whose `.gitignore` has not yet been
    # reconciled to the session-path contract would otherwise show every native
    # review as untracked, for the next `git add -A` to commit.
    ignore = path.parent / ".gitignore"
    if not ignore.is_file():
        atomic_write_text(ignore, "*\n")
    atomic_write_text(path, json.dumps(sidecar, indent=2))
    return path


def _json_arrays(text: str):
    """Every JSON array that parses starting at a ``[`` in ``text``, in order."""
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\[", text):
        try:
            value, _end = decoder.raw_decode(text, match.start())
        except ValueError:
            continue
        if isinstance(value, list):
            yield value


def findings_detail(text: str) -> "list[dict] | None":
    """The findings a native review's text holds, with their words — ``file``,
    ``line``, ``summary``, ``failure_scenario`` — or ``None`` when the text says
    nothing countable. For the comparison's blind sheet, which reads the
    per-clone text; nothing durable stores these words.

    A JSON array of objects wins — the ``high`` recipe's output. With no such
    array, a ``(none)`` line in the review's own body is an empty run. The host
    opens EVERY result with a ``(none)`` line of its own, whatever the review
    found, so a leading one is its header, not the review's answer, and does
    not count. Anything else is not counted: a guessed zero would read as a
    clean review."""
    def _str(value):
        return value if isinstance(value, str) else None

    for candidate in _json_arrays(text):
        if candidate and all(isinstance(item, dict) for item in candidate):
            return [
                {
                    "file": _str(item.get("file")),
                    "line": item["line"] if isinstance(item.get("line"), int)
                    and not isinstance(item.get("line"), bool) else None,
                    "summary": _str(item.get("summary")),
                    "failure_scenario": _str(item.get("failure_scenario")),
                }
                for item in candidate
            ]
    if _NONE_LINE.search(_without_host_header(text)):
        return []
    return None


def _without_host_header(text: str) -> str:
    """``text`` minus the host's result header: a ``Result:`` line, which the
    wrapper is told to drop and may keep, and the ``(none)`` the host prints
    under it or beside it, blank lines between them allowed. The header's answer
    must not depend on its layout. A text that is only the header keeps one
    ``(none)``: there is no review body to hold any other answer."""
    lines = [line.strip() for line in text.strip().splitlines()]
    saw_none = False
    if lines and lines[0].startswith("Result:"):
        saw_none = lines[0][len("Result:"):].strip() == "(none)"
        lines = lines[1:]
    while lines and not lines[0]:
        lines = lines[1:]
    if not saw_none and lines and lines[0] == "(none)":
        saw_none = True
        lines = lines[1:]
    if not any(lines):
        return "(none)" if saw_none else ""
    return "\n".join(lines)


def _read_text(path: Path) -> str:
    """A native text as written by a model: read leniently, because one bad byte
    must not make every retry of ``record`` or ``critic-consolidate`` fail."""
    return path.read_text(encoding="utf-8", errors="replace")


def parse_findings(text: str) -> "list[dict] | None":
    """:func:`findings_detail` without the words — ``{file, line}`` per finding,
    the most the ledger may carry."""
    detail = findings_detail(text)
    if detail is None:
        return None
    return [{"file": f["file"], "line": f["line"]} for f in detail]


def _read_sidecar(prawduct_dir: Path, review_id: str) -> "tuple[dict | None, str]":
    path = sidecar_path(prawduct_dir, review_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"no paired native review was dispatched as {review_id} ({path} is absent)"
    except (OSError, ValueError) as exc:
        return None, f"{path} is unreadable ({exc.__class__.__name__})"
    if not isinstance(data, dict) or data.get("review_id") != review_id:
        return None, f"{path} does not describe {review_id}"
    return data, ""


def _update_sidecar(prawduct_dir: Path, review_id: str, fields: dict) -> "str | None":
    """Merge ``fields`` into the sidecar; ``None`` on success, else why not."""
    sidecar, reason = _read_sidecar(prawduct_dir, review_id)
    if sidecar is None:
        return reason
    sidecar.update(fields)
    try:
        atomic_write_text(sidecar_path(prawduct_dir, review_id), json.dumps(sidecar, indent=2))
    except OSError as exc:
        return f"the sidecar could not be rewritten ({exc.__class__.__name__}: {exc})"
    return None


def _hook_command() -> str:
    """The hook binary that wrote the sidecar, never whatever ``prawduct-hook``
    PATH finds: the sidecar's writer and readers must be one build (a framework
    checkout and its installed plugin differ)."""
    from . import core  # noqa: PLC0415 — lazy, matching the lib's other imports

    return f'python3 "{core.FRAMEWORK_DIR / "bin" / "prawduct-hook"}"'


def prepare_command(review_id: str, project: str) -> str:
    """What the wrapper runs first, from its own worktree (its default
    directory): :func:`prepare`, naming the session's checkout."""
    return f'{_hook_command()} native-review prepare {review_id} "{project}"'


def record_command(review_id: str, project: "str | None" = None) -> str:
    """What the wrapper runs last. Given ``project`` it changes directory into
    the session's checkout first: the wrapper's own tree is disposable, the
    hook's ephemeral-worktree guard refuses a state write from it, and the
    sidecar is not there."""
    command = f"{_hook_command()} native-review record {review_id}"
    return f'cd "{project}" && {command}' if project else command


def _range_head(sidecar: dict) -> "str | None":
    """The head of the range the native review was handed (``<level>
    <base>...<head>``): a real commit, or the unreachable one an inner review's
    working tree was named by."""
    tokens = str(sidecar.get("args") or "").split()
    if len(tokens) < 2 or "..." not in tokens[1]:
        return None
    return tokens[1].split("...", 1)[1] or None


def _toplevel(path: Path) -> "Path | None":
    from . import evidence  # noqa: PLC0415 — lazy, matching the lib's other imports

    rc, out, _err = evidence.run_git(path, "rev-parse", "--show-toplevel")
    return Path(out).resolve() if rc == 0 and out else None


def _review_tree_refusal(tree: Path, session: Path) -> "str | None":
    """Why ``tree`` is not a tree the native review may detach, or ``None``.

    Strict on purpose: a refusal costs one native sample, a wrong tree costs
    someone's checkout. Only a clean tree of the same repository, other than
    the session's, on no real branch (detached, or on the harness's scratch
    branch) is the disposable tree an isolated agent is given."""
    from . import evidence, gitstate  # noqa: PLC0415 — lazy, matching the lib's other imports

    if not Path(tree).is_dir():
        return f"{tree} is not a directory"
    top = _toplevel(tree)
    if top is None:
        return f"{tree} is not a git checkout"
    session_top = _toplevel(session) or Path(session).resolve()
    if top == session_top:
        return (
            f"this is the session's checkout `{session_top}`, which a review must never move: the "
            "native review runs in a worktree of its own (the wrapper is dispatched with "
            '`isolation: "worktree"`)'
        )
    common = gitstate.git_common_dir(top)
    if common is None or common != gitstate.git_common_dir(session_top):
        return f"{top} is not a worktree of the same repository as {session_top}"
    branch = gitstate.current_branch(top)
    if branch is not None and not gitstate.is_scratch_branch(branch):
        return f"{top} holds branch `{branch}`: someone's checkout, not a disposable review tree"
    rc, dirty, err = evidence.run_git(top, "status", "--porcelain", "--untracked-files=no")
    if rc != 0:
        return f"the status of {top} could not be read ({err or rc})"
    if dirty:
        return f"{top} has uncommitted changes to tracked files"
    return None


def prepare(review_tree: Path, session_dir: Path, review_id: str) -> "tuple[int, str]":
    """Detach the wrapper's own worktree at the reviewed head, or refuse.

    ``(0, message)`` once ``review_tree`` is detached there; ``(1, reason)``
    when it is the session's checkout, or any tree but a disposable one
    (:func:`_review_tree_refusal`), with nothing checked out. A refusal is kept
    in the sidecar (``prepare_refused``), so a run that never happened says
    why. Where the tree started is kept too (``review_tree``), so
    :func:`record` can return it."""
    from . import evidence, gitstate  # noqa: PLC0415 — lazy, matching the lib's other imports

    stop = " Nothing was checked out; do not invoke the review."
    if not is_safe_id(review_id):
        return 1, f"not a review id: {review_id!r}.{stop}"
    prawduct_dir = Path(session_dir) / ".prawduct"
    sidecar, reason = _read_sidecar(prawduct_dir, review_id)
    if sidecar is None:
        return 1, f"{reason}.{stop}"
    refusal = _review_tree_refusal(Path(review_tree), Path(session_dir))
    head = _range_head(sidecar)
    if refusal is None and head is None:
        refusal = f"the sidecar's range {sidecar.get('args')!r} names no head"
    if refusal is not None:
        unkept = _update_sidecar(prawduct_dir, review_id, {"prepare_refused": refusal})
        return 1, f"{refusal}.{stop}" + (f" ({unkept})" if unkept else "")
    tree = _toplevel(Path(review_tree))
    rc, start, err = evidence.run_git(tree, "rev-parse", "HEAD")
    if rc != 0 or not start:
        return 1, f"the HEAD of {tree} could not be read ({err or rc}).{stop}"
    branch = gitstate.current_branch(tree)
    rc, _out, err = evidence.run_git(tree, "checkout", "--quiet", "--detach", head)
    if rc != 0:
        return 1, f"{tree} could not be detached at {head[:12]} ({err or rc}).{stop}"
    unkept = _update_sidecar(
        prawduct_dir, review_id,
        {"review_tree": {"path": str(tree), "branch": branch, "commit": start}, "prepare_refused": None},
    )
    kept = "" if unkept is None else f" Its starting point was not kept ({unkept}), so record cannot return it."
    session_top = _toplevel(Path(session_dir)) or session_dir
    return 0, (
        f"review tree {tree} detached at {head[:12]}, the reviewed head; the session's checkout "
        f"{session_top} was not touched. Invoke the review now.{kept}"
    )


def _return_review_tree(project_dir: Path, sidecar: dict) -> str:
    """Put the review tree back where :func:`prepare` found it, so the harness
    finds the tree it made and can clean it up. A clause for record's message;
    ``""`` when there is no tree to return (never prepared, or already gone)."""
    from . import evidence  # noqa: PLC0415 — lazy, matching the lib's other imports

    kept = sidecar.get("review_tree")
    if not isinstance(kept, dict) or not isinstance(kept.get("path"), str):
        return ""
    path = Path(kept["path"])
    if not path.is_dir():
        return ""
    top = _toplevel(path)
    if top is None or top == (_toplevel(project_dir) or Path(project_dir).resolve()):
        return ""  # never the session's checkout: prepare refuses that, so this record is stale
    rc, dirty, err = evidence.run_git(top, "status", "--porcelain", "--untracked-files=no")
    if rc != 0 or dirty:
        why = "it has uncommitted changes" if rc == 0 else f"its status could not be read ({err or rc})"
        return f"; its review tree {top} was left where the review put it: {why}"
    branch, commit = kept.get("branch"), kept.get("commit")
    if isinstance(branch, str) and branch:
        rc, _out, err = evidence.run_git(top, "switch", "--quiet", branch)
        where = f"branch `{branch}`"
    elif isinstance(commit, str) and commit:
        rc, _out, err = evidence.run_git(top, "checkout", "--quiet", "--detach", commit)
        where = commit[:12]
    else:
        return f"; its review tree {top} was left: no starting point was kept"
    if rc != 0:
        return f"; its review tree {top} could not be returned to {where} ({err or rc})"
    return f"; its review tree {top} returned to {where}"


def _head_warning(project_dir: Path, sidecar: "dict | None") -> str:
    """`` <loud sentence>`` when the session's HEAD has left the branch this
    review was dispatched on, else ``""``."""
    from . import head_guard  # noqa: PLC0415 — lazy, matching the lib's other imports

    if not isinstance(sidecar, dict):
        return ""
    left = head_guard.left_branch(project_dir, sidecar.get("session_branch"))
    return f" {head_guard.message(left)}" if left else ""


#: How long after dispatch a moved HEAD is put on this review in its
#: ``NEXT-ACTION``. The mover guarded against is the native run, which the
#: wrapper keeps alive at most a background ``sleep 900`` past a review of about
#: a hundred seconds; an hour covers it, and keeps a record re-rendered the next
#: day from blaming this review for a deliberate detach made since.
HEAD_WATCH_SECONDS = 3600


def _seconds_since(stamp) -> "float | None":
    try:
        then = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    return round((datetime.now(timezone.utc) - then).total_seconds(), 1)


def _tree_moved(project_dir: Path, sidecar: dict) -> "bool | None":
    """Whether a file in the reviewed interval, outside ``.prawduct/``, differs
    in the working tree now from the tree the review read — the native review
    reads source and docs from the tree it runs in, and a builder may fix one
    before it lands. A run :func:`prepare` placed read its own tree at the
    reviewed head, so for it the answer is ``False``. ``.prawduct/`` holds the records about the work, which
    consolidation and the builder write during any review. ``None`` when it
    cannot be told: unknown, never "no"."""
    from . import evidence  # noqa: PLC0415 — lazy, matching the lib's other imports

    if isinstance(sidecar.get("review_tree"), dict):
        return False  # read in its own tree at the reviewed head: nothing could move under it
    base, head = sidecar.get("base_tree"), sidecar.get("head_tree")
    if not (isinstance(base, str) and base and isinstance(head, str) and head):
        return None
    capture = evidence.capture_tree(project_dir)
    if capture.get("status") != "ok":
        return None
    rc_a, reviewed, _ = evidence.run_git(project_dir, "diff", "--name-only", base, head)
    rc_b, moved, _ = evidence.run_git(project_dir, "diff", "--name-only", head, capture["tree"])
    if rc_a != 0 or rc_b != 0:
        return None
    both = (set(reviewed.split("\n")) & set(moved.split("\n"))) - {""}
    return any(not path.startswith(".prawduct/") for path in both)


#: Where a native run's reviewed trees are pinned. A dirty working tree's tree
#: is written through a temporary index, so nothing else references it, and
#: `git gc` prunes an unreferenced object after gc.pruneExpire (two weeks by
#: default) — before the experiment's blind verification reads the code there.
#: Clone-local: prawduct's evidence sync pushes only its notes ref, though a
#: mirror push would publish these too. Released when the experiment stops (the
#: research README says how). Whether a run is pinned is read from the refs,
#: never stored, so a later pin is never contradicted by a stale record.
PIN_PREFIX = "refs/prawduct/native-trees"


def pin_trees(project_dir: Path, review_id: str, base: "str | None", head: "str | None") -> bool:
    """Point ``<PIN_PREFIX>/<review_id>/{base,head}`` at the reviewed trees.
    True only when both are pinned. Never raises: a pin that fails costs the
    verification later, never the record now. A review id that is not a safe
    ref component pins nothing."""
    from . import evidence  # noqa: PLC0415 — lazy, matching the lib's other imports

    if not is_safe_id(review_id):
        return False
    pinned = True
    for name, tree in (("base", base), ("head", head)):
        if not tree:
            pinned = False
            continue
        rc, _out, _err = evidence.run_git(project_dir, "update-ref", f"{PIN_PREFIX}/{review_id}/{name}", tree)
        pinned = pinned and rc == 0
    return pinned


def record(project_dir: Path, prawduct_dir: Path, review_id: str) -> "tuple[int, str]":
    """Append the native run's ``native.review`` ledger event. ``(0, message)``
    on an append or when it is already recorded; ``(1, reason)`` when there is
    nothing to record. Idempotent per review id."""
    from . import ledger  # noqa: PLC0415 — lazy, matching the lib's other imports

    if not is_safe_id(review_id):
        return 1, f"not a review id: {review_id!r}"
    sidecar, reason = _read_sidecar(prawduct_dir, review_id)
    if sidecar is None:
        return 1, reason
    path = text_path(prawduct_dir, review_id)
    try:
        text = _read_text(path)
    except FileNotFoundError:
        return 1, f"the native review's text has not been written to {path}"
    except OSError as exc:
        return 1, f"{path} is unreadable ({exc.__class__.__name__})"
    if not text.strip():
        return 1, f"{path} is empty — write the review's text there first"
    pinned = pin_trees(project_dir, review_id, sidecar.get("base_tree"), sidecar.get("head_tree"))
    unpinned = "" if pinned else (
        f"; its reviewed trees could not be pinned under {PIN_PREFIX}/{review_id}/, so git gc may "
        "prune them before verification (run it again, or `compare.py --pin`)"
    )
    after = _return_review_tree(project_dir, sidecar) + _head_warning(project_dir, sidecar)
    if ledger.native_review_event_exists(prawduct_dir, review_id):
        return 0, f"native review {review_id} is already recorded; nothing appended{unpinned}{after}"
    findings = parse_findings(text)
    # A sidecar written before inner reviews paired carries no mode or stage;
    # every run dispatched then was a boundary `cumulative`.
    payload = {
        "critic_review_id": review_id,
        "mode": sidecar.get("mode") or "cumulative",
        "stage": sidecar.get("stage") or "boundary",
        "synthetic_range": bool(sidecar.get("synthetic_range")),
        "tree_moved": _tree_moved(project_dir, sidecar),
        "level": sidecar.get("level"),
        "args": sidecar.get("args"),
        "base_tree": sidecar.get("base_tree"),
        "head_tree": sidecar.get("head_tree"),
        "base_commit": sidecar.get("base_commit"),
        "head_commit": sidecar.get("head_commit"),
        "findings": findings or [],
        "findings_parsed": findings is not None,
    }
    ledger.append_native_review_event(
        project_dir, prawduct_dir, payload,
        model=sidecar.get("model"), scope=sidecar.get("scope"),
        dispatched_at=sidecar.get("dispatched_at"),
        duration_seconds=_seconds_since(sidecar.get("dispatched_at")),
    )
    counted = f"{len(findings)} finding(s)" if findings is not None else "findings not countable from the text"
    return 0, f"native review {review_id} recorded: {counted}{unpinned}{after}"


def show(prawduct_dir: Path, review_id: "str | None" = None) -> "tuple[int, str]":
    """``(0, text)`` for one native review's text — the newest when no id is
    given — or ``(1, reason)``."""
    if review_id is None:
        texts = sorted(reviews_dir(prawduct_dir).glob("rev-*.md"), key=lambda p: p.stat().st_mtime)
        if not texts:
            return 1, f"no native review text in {reviews_dir(prawduct_dir)}"
        path = texts[-1]
    elif not is_safe_id(review_id):
        return 1, f"not a review id: {review_id!r}"
    else:
        path = text_path(prawduct_dir, review_id)
    try:
        return 0, f"native review {path.stem} ({path}):\n\n{_read_text(path)}"
    except FileNotFoundError:
        return 1, f"no native review text at {path} — it may still be running"
    except OSError as exc:
        return 1, f"{path} is unreadable ({exc.__class__.__name__})"


def next_action_clause(prawduct_dir: Path, review_id: "str | None") -> str:
    """The sentence the Critic's ``NEXT-ACTION`` gains when its review was
    paired, or ``""``. Paired means a sidecar exists for the review — the record
    ``critic-begin`` wrote — so every path that renders the findings record from
    the fact says it, not only the consolidation that had the manifest in hand.

    Worded to stay true as the cache ages, in four states: a count once the text
    has landed and parses (it is written once); "landed, not countable" when it
    landed and holds no countable answer; "text unreadable" when it exists and
    cannot be read; and otherwise that it may still be running — never "still
    running", which the next session's briefing would repeat after it finished.
    It never says the native review gates anything, and says nothing of an
    inner run's list (the module docstring says why).

    Either stage leads with ``head_guard``'s sentence when the session's HEAD
    has left the branch the review was dispatched on, within
    :data:`HEAD_WATCH_SECONDS` of the dispatch (#1177): a moved HEAD is not a
    finding, and it is what the builder must act on before their next commit."""
    if not is_safe_id(review_id) or not sidecar_path(prawduct_dir, review_id).is_file():
        return ""
    # Only a sidecar that SAYS inner silences the list: one that exists and
    # cannot be read still means a native list was dispatched, and the builder
    # is owed the pointer to it.
    sidecar, _reason = _read_sidecar(prawduct_dir, review_id)
    elapsed = _seconds_since((sidecar or {}).get("dispatched_at"))
    watched = elapsed is not None and elapsed <= HEAD_WATCH_SECONDS
    warning = _head_warning(Path(prawduct_dir).parent, sidecar) if watched else ""
    if sidecar is not None and (sidecar.get("stage") or "boundary") != "boundary":
        return warning
    command = f"`{SHOW_COMMAND} {review_id}`"
    unreadable = False
    try:
        text = _read_text(text_path(prawduct_dir, review_id))
    except FileNotFoundError:
        text = ""
    except OSError:
        text, unreadable = "", True
    findings = parse_findings(text) if text.strip() else None
    if unreadable:
        counted = " (text unreadable)"
    elif findings is not None:
        counted = f" ({len(findings)} finding(s))"
    elif text.strip():
        counted = " (landed, not countable)"
    elif sidecar is not None and sidecar.get("prepare_refused"):
        # `prepare` refused its tree, so no review ran and none will land:
        # "may still be running" would be false for good (#1177).
        return warning + (
            " A paired native review of this range (#1130) did not run: its worktree check "
            f"refused ({sidecar['prepare_refused']}). It gates nothing."
        )
    else:
        counted = " (it may still be running)"
    return warning + (
        f" A paired native review of this range (#1130) ran beside it{counted}: read its list "
        f"with {command} and work from both lists before fixing. It gates nothing."
    )
