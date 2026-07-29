"""SHA-keyed governance evidence store — kernel v3 (GOV-4C7X plan 1, chunk 01).

The append-only store every v3 gate composes over. Design:
``.prawduct/artifacts/kernel-v3-evidence-design.md`` (D1–D3, D9) — fields were
derived from the ten consumer queries enumerated there, not from the mechanism.

**Location (D1).** ``<git-common-dir>/prawduct/evidence.jsonl`` — the one
filesystem location every worktree of a clone already shares. Never committed
(inside ``.git``), no gitignore contract, isolated between unrelated repos by
construction (R9), lazily initialized (an absent file IS the empty store — no
consumer migration, C9 tier 1).

**Envelope (D2).** One JSON object per line::

    {"schema": 1, "kind": "review", "id": "...", "ts": "...",
     "actor": {"session": ..., "worktree": ..., "plugin": ...}, "body": {...}}

``schema`` rides on every record so readers can reject-or-skip explicitly
(C7); ``kind`` namespaces the store (``review``/``resolution`` now;
``test-run``/``pr-review``/``promotion`` reserved for later constituent
plans); ``id`` is fixed at dispatch time so consolidation is idempotent
(CRT-4B7X) and readers dedupe. ``actor`` answers the debugging question
("who wrote this, when, from where, under which plugin") — Q7.

**Keying (D3).** Facts reference *tree SHAs* captured via a temporary index
(``capture_tree``): objects are written to the shared odb, the session's real
index and working tree are never touched (R1 — a reviewer must never mutate
the session under review), and a verbatim commit preserves the tree, so a
pre-commit fact vouches for the commit from any checkout. Verified by the
2026-07-12 D3 spike (plain repo + linked worktree).

**Error posture (D9).** Every path resolves to exactly one of: self-heal (a
torn tail line from a crashed writer — healed by the next append), no-op with
stderr attribution (excluded malformed/unknown records), or loud block left
to the *caller* (no store outside a git repo; schema-ahead records surfaced
in the read result so gates can block with the C7 remedy). No path leaves
state a later reader would mistake for current; exclusion can only make gates
stricter (missing coverage), never looser.

Errors are return values (``{"status": ..., "reason": ...}``) per
project-preferences; exceptions escape only at parse/OS boundaries and are
converted here.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import gitstate

SCHEMA_VERSION = 1
SUPPORTED_SCHEMAS = frozenset({1})
# Kinds this plugin version writes/understands. Unknown kinds under a
# SUPPORTED schema are kept in the facts list (a newer minor may add kinds —
# Q9 forward-compat); gate consumers filter by the kinds they know, so an
# unknown kind can never satisfy a gate, only coexist.
KNOWN_KINDS = frozenset({"review", "resolution"})

STORE_SUBDIR = "prawduct"
STORE_BASENAME = "evidence.jsonl"

_GIT_TIMEOUT = 15


def store_path(project_dir: Path) -> Path | None:
    """The clone-shared store path, or ``None`` outside a git repo (callers
    fail loud with their own attribution — there is no fallback location; a
    per-worktree fallback would silently reintroduce the split this store
    exists to fix)."""
    common = gitstate.git_common_dir(project_dir)
    if common is None:
        return None
    return common / STORE_SUBDIR / STORE_BASENAME


def _plugin_version() -> str | None:
    """The bundled VERSION, nullable — never invented."""
    try:
        text = (Path(__file__).resolve().parent.parent / "VERSION").read_text()
    except OSError:
        return None
    return text.strip() or None


def _session_epoch(project_dir: Path) -> str | None:
    """The session identity available on disk: the ``.session-start`` marker's
    mtime as UTC ISO. Nullable when no session marker exists (headless probes,
    fixtures) — never invented."""
    marker = gitstate.get_prawduct_dir(project_dir) / ".session-start"
    try:
        mtime = marker.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_fact(
    project_dir: Path, kind: str, fact_id: str, body: dict
) -> dict:
    """Append one fact. Returns ``{"status": "appended", "path", "id"}`` or
    ``{"status": "error", "reason"}``. One ``O_APPEND``-mode ``write()`` keeps
    concurrent appends whole (same idiom as the governance ledger). Unknown
    kinds are rejected — fail-closed at the write boundary, mirroring
    ``ledger-append`` (escape hatches in classification create silent
    failures)."""
    if kind not in KNOWN_KINDS:
        allowed = ", ".join(sorted(KNOWN_KINDS))
        return {
            "status": "error",
            "reason": f"unknown fact kind {kind!r} (this plugin writes: {allowed})",
        }
    if not isinstance(fact_id, str) or not fact_id.strip():
        return {"status": "error", "reason": "fact id must be a non-empty string"}
    if not isinstance(body, dict):
        return {"status": "error", "reason": "fact body must be an object"}
    path = store_path(project_dir)
    if path is None:
        return {
            "status": "error",
            "reason": f"no git repository at {project_dir} — the evidence store "
            "lives in the clone's git common dir and has no fallback location",
        }

    envelope = {
        "schema": SCHEMA_VERSION,
        "kind": kind,
        "id": fact_id,
        "ts": _now_iso(),
        "actor": {
            "session": _session_epoch(project_dir),
            "worktree": str(project_dir),
            "plugin": _plugin_version(),
        },
        "body": body,
    }
    line = json.dumps(envelope) + "\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Self-heal a torn tail (D9): a crashed writer can leave a final line
        # without a newline; gluing this record onto it would corrupt BOTH.
        # Lead with a newline in that one case — the torn fragment stays an
        # excluded (attributed) line, this record stays whole.
        if path.is_file() and path.stat().st_size > 0:
            with open(path, "rb") as fh:
                fh.seek(-1, os.SEEK_END)
                if fh.read(1) != b"\n":
                    line = "\n" + line
                    print(
                        f"evidence: healed torn final line in {path.name} "
                        "(crashed writer) — fragment excluded, store consistent",
                        file=sys.stderr,
                    )
        # One os.write() on an O_APPEND fd — a single unbuffered syscall, so
        # concurrent appends interleave whole lines even for D4-sized review
        # facts (the buffered ``open(..., "a")`` idiom only guarantees this
        # below the text-IO buffer size — Critic ch.01 finding).
        fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except OSError as exc:
        return {"status": "error", "reason": f"store unwritable ({exc})"}
    return {"status": "appended", "path": str(path), "id": fact_id}


def read_facts(project_dir: Path) -> dict:
    """Read the store. Returns::

        {"status": "ok"|"empty"|"error", "reason"?: str,
         "facts": [envelope, ...],          # schema-supported, deduped, in order
         "schema_ahead": [{"line", "schema", "kind", "id"}, ...],
         "excluded": int, "duplicates": int}

    ``schema_ahead`` records were written by a NEWER plugin than this reader —
    they are never silently dropped into ``excluded``: gate callers must treat
    their presence as a loud block with the C7 remedy (this reader cannot know
    what they attest). Malformed lines are excluded with one stderr note each;
    duplicate (kind, id) keeps the FIRST occurrence (idempotent-append
    tolerance, CRT-4B7X)."""
    path = store_path(project_dir)
    if path is None:
        return {
            "status": "error",
            "reason": f"no git repository at {project_dir}",
            "facts": [],
            "schema_ahead": [],
            "excluded": 0,
            "duplicates": 0,
        }
    if not path.is_file():
        return {
            "status": "empty",
            "facts": [],
            "schema_ahead": [],
            "excluded": 0,
            "duplicates": 0,
        }
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "status": "error",
            "reason": f"store unreadable ({exc})",
            "facts": [],
            "schema_ahead": [],
            "excluded": 0,
            "duplicates": 0,
        }

    raw_lines = raw_text.splitlines()
    facts: list[dict] = []
    schema_ahead: list[dict] = []
    excluded = 0
    duplicates = 0
    seen: set[tuple[str, str]] = set()
    max_supported = max(SUPPORTED_SCHEMAS)
    # A torn tail is specifically an UNTERMINATED final line (crashed writer
    # mid-append) — that one heals on the next append. A newline-terminated
    # malformed final line is ordinary corruption and will not heal.
    torn_tail_lineno = (
        len(raw_lines) if raw_text and not raw_text.endswith("\n") else None
    )
    for lineno, raw in enumerate(raw_lines, start=1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            excluded += 1
            tail = (
                " (torn tail from a crashed writer — heals on next append)"
                if lineno == torn_tail_lineno
                else ""
            )
            print(
                f"evidence: excluding unparseable line {lineno} of "
                f"{path.name}{tail}",
                file=sys.stderr,
            )
            continue
        if not isinstance(record, dict):
            excluded += 1
            print(
                f"evidence: excluding non-object line {lineno} of {path.name}",
                file=sys.stderr,
            )
            continue
        schema = record.get("schema")
        if not isinstance(schema, int) or isinstance(schema, bool):
            excluded += 1
            print(
                f"evidence: excluding line {lineno} of {path.name} "
                "(missing/invalid schema field)",
                file=sys.stderr,
            )
            continue
        if schema > max_supported:
            schema_ahead.append(
                {
                    "line": lineno,
                    "schema": schema,
                    "kind": record.get("kind"),
                    "id": record.get("id"),
                }
            )
            print(
                f"evidence: line {lineno} of {path.name} carries schema "
                f"{schema} (> {max_supported}, this reader) — written by a "
                "newer prawduct; update the plugin (/reload-plugins or restart)"
                " before trusting gates in this session",
                file=sys.stderr,
            )
            continue
        if schema not in SUPPORTED_SCHEMAS:
            # Below the supported floor (no such version ever shipped) —
            # malformed, not future: exclude with attribution.
            excluded += 1
            print(
                f"evidence: excluding line {lineno} of {path.name} "
                f"(schema {schema} was never a valid store version)",
                file=sys.stderr,
            )
            continue
        kind = record.get("kind")
        fact_id = record.get("id")
        if (
            not isinstance(kind, str)
            or not kind
            or not isinstance(fact_id, str)
            or not fact_id
            or not isinstance(record.get("body"), dict)
        ):
            excluded += 1
            print(
                f"evidence: excluding line {lineno} of {path.name} "
                "(invalid envelope: kind/id/body)",
                file=sys.stderr,
            )
            continue
        key = (kind, fact_id)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        facts.append(record)

    return {
        "status": "ok",
        "facts": facts,
        "schema_ahead": schema_ahead,
        "excluded": excluded,
        "duplicates": duplicates,
    }


def facts_of_kind(read_result: dict, kind: str) -> list[dict]:
    """Filter a ``read_facts`` result to one kind — the consumer-side filter
    that makes unknown future kinds harmless (they can coexist, never satisfy)."""
    return [f for f in read_result.get("facts", []) if f.get("kind") == kind]


def has_fact(project_dir: Path, kind: str, fact_id: str) -> bool:
    """True if a fact with this (kind, id) is already in the store — the
    idempotency probe consolidation uses before appending (CRT-4B7X)."""
    result = read_facts(project_dir)
    return any(f.get("id") == fact_id for f in facts_of_kind(result, kind))


# ---------------------------------------------------------------------------
# Tree capture (D3)
# ---------------------------------------------------------------------------


def run_git(project_dir: Path, *args: str, env: dict | None = None) -> tuple[int, str, str]:
    """One git call; (returncode, stdout, stderr). Never raises — converts
    subprocess failures to a nonzero returncode with the message in stderr.
    Public: the dispatch side of the review data plane (critic_consolidate)
    shares it — per the module-boundary rule, only this module and git
    helpers touch disk/git, so callers borrow the runner rather than
    growing their own (promoted at first external use, chunk 03)."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, "", str(exc)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def capture_tree(project_dir: Path) -> dict:
    """Capture the working tree (tracked changes + untracked, gitignored
    excluded) as a tree object in the shared odb, via a TEMPORARY index.

    Returns ``{"status": "ok", "tree", "head_commit", "head_tree", "clean"}``
    or ``{"status": "error", "reason"}``. The session's real index and working
    tree are never touched (R1) — asserted by tests, verified by the D3 spike.
    ``clean`` is True when the captured tree equals ``HEAD^{tree}`` (a verbatim
    commit of this state will carry the same tree SHA)."""
    tmp_fd, tmp_name = tempfile.mkstemp(prefix="prawduct-idx-")
    os.close(tmp_fd)
    os.unlink(tmp_name)  # git wants to create the index file itself
    env = dict(os.environ)
    env["GIT_INDEX_FILE"] = tmp_name
    try:
        rc, head_commit, _ = run_git(project_dir, "rev-parse", "--verify", "HEAD")
        head_commit = head_commit if rc == 0 else None
        head_tree = None
        if head_commit:
            rc, head_tree_out, _ = run_git(project_dir, "rev-parse", "HEAD^{tree}")
            head_tree = head_tree_out if rc == 0 else None
            # Seed the temp index from HEAD so unchanged paths keep their
            # entries; on an unborn HEAD the empty temp index is correct.
            rc, _, err = run_git(project_dir, "read-tree", "HEAD", env=env)
            if rc != 0:
                return {"status": "error", "reason": f"read-tree failed: {err}"}
        rc, _, err = run_git(project_dir, "add", "-A", env=env)
        if rc != 0:
            return {"status": "error", "reason": f"temp-index add failed: {err}"}
        rc, tree, err = run_git(project_dir, "write-tree", env=env)
        if rc != 0 or not tree:
            return {"status": "error", "reason": f"write-tree failed: {err}"}
        return {
            "status": "ok",
            "tree": tree,
            "head_commit": head_commit,
            "head_tree": head_tree,
            "clean": tree == head_tree,
        }
    finally:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass  # already absent — mkstemp file deleted above, git may not have recreated it


def tree_diff(project_dir: Path, tree_a: str, tree_b: str) -> "list[str] | None":
    """Paths changed between two tree objects (``git diff --name-only``),
    or ``None`` when the diff cannot be computed (missing object, git
    failure) — never guessed, matching ``coverage_algebra.DiffFn``'s
    contract. This is the diff the gates inject into the algebra and the
    dispatch side uses for its ``files_changed`` snapshot, so the recorded
    set and the composed edge-validity check agree by construction."""
    if not (isinstance(tree_a, str) and tree_a and isinstance(tree_b, str) and tree_b):
        return None
    rc, out, _err = run_git(project_dir, "diff", "--name-only", tree_a, tree_b)
    if rc != 0:
        return None
    return [line for line in out.splitlines() if line.strip()]


def tree_entries(project_dir: Path, tree: str) -> "list[tuple[str, str, str]] | None":
    """``(mode, object_id, path)`` for every entry in ``tree``, or ``None``
    when the tree cannot be read (missing object, git failure) — never
    guessed, the same direction as :func:`tree_diff`.

    **Mode is part of the identity, not decoration.** ``git diff`` reports a
    path whose mode changed even when its blob is byte-identical (``chmod
    +x``, a file becoming a symlink at 120000, a gitlink at 160000). A caller
    comparing trees by ``(object_id, path)`` alone would call those trees
    equal where git calls them different — and for a caller deciding whether
    a change needs review, that difference is a fail-OPEN. Carrying the mode
    keeps this function's notion of "same content" no looser than git's.

    Lets a caller decide whether two trees agree on some *subset* of their
    content without asking git to diff the pair: equal content over a subset
    is equality of a per-tree value, so n trees cost n calls rather than n².

    ``-z`` because git quotes paths containing spaces or non-ASCII bytes in
    its default output, and a quoted path classifies differently from the
    real one — the same trap ``gitstate.parse_porcelain_line`` exists to
    absorb, met here before it can bite.
    """
    if not (isinstance(tree, str) and tree):
        return None
    rc, out, _err = run_git(project_dir, "ls-tree", "-r", "-z", "--full-tree", tree)
    if rc != 0:
        return None
    entries: list[tuple[str, str, str]] = []
    for record in out.split("\0"):
        if not record:
            continue
        meta, _tab, path = record.partition("\t")
        if not path:
            continue
        fields = meta.split()
        if len(fields) < 3:
            continue
        mode, _type, object_id = fields[0], fields[1], fields[2]
        entries.append((mode, object_id, path))
    return entries


# ---------------------------------------------------------------------------
# CLI (``prawduct-hook evidence <status|list>``) — the stable allowlistable
# surface (R4); skills scope to ``Bash(prawduct-hook evidence*)``.
# ---------------------------------------------------------------------------

_CLI_USAGE = "Usage: prawduct-hook evidence {status|list [--kind <k>] [-n <count>]}"


def evidence_cmd(project_dir: Path, argv: list[str]) -> int:
    sub = argv[0] if argv else "status"
    if sub == "status":
        return _cmd_status(project_dir)
    if sub == "list":
        return _cmd_list(project_dir, argv[1:])
    print(_CLI_USAGE, file=sys.stderr)
    return 1


def _cmd_status(project_dir: Path) -> int:
    path = store_path(project_dir)
    if path is None:
        print(
            f"evidence: no git repository at {project_dir} — no store here",
            file=sys.stderr,
        )
        return 1
    result = read_facts(project_dir)
    if result["status"] == "error":
        print(f"evidence: {result['reason']}", file=sys.stderr)
        return 1
    print(f"store: {path}")
    if result["status"] == "empty":
        print("empty store (created lazily on the first recorded fact)")
        return 0
    by_kind: dict[str, int] = {}
    for fact in result["facts"]:
        by_kind[fact["kind"]] = by_kind.get(fact["kind"], 0) + 1
    counts = ", ".join(f"{k}={n}" for k, n in sorted(by_kind.items())) or "none"
    print(f"facts: {counts}")
    if result["duplicates"]:
        print(f"duplicate appends tolerated: {result['duplicates']}")
    if result["excluded"]:
        print(f"excluded malformed lines: {result['excluded']} (see stderr)")
    if result["schema_ahead"]:
        print(
            f"SCHEMA-AHEAD records: {len(result['schema_ahead'])} — written by "
            "a newer prawduct than this reader. Gates must not be trusted in "
            "this session until the plugin is updated (/reload-plugins or "
            "restart Claude Code)."
        )
        return 2
    return 0


def _cmd_list(project_dir: Path, argv: list[str]) -> int:
    kind_filter: str | None = None
    limit = 20
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--kind" and i + 1 < len(argv):
            kind_filter = argv[i + 1]
            i += 2
        elif arg == "-n" and i + 1 < len(argv):
            try:
                limit = max(1, int(argv[i + 1]))
            except ValueError:
                print(_CLI_USAGE, file=sys.stderr)
                return 1
            i += 2
        else:
            print(_CLI_USAGE, file=sys.stderr)
            return 1
    result = read_facts(project_dir)
    if result["status"] == "error":
        print(f"evidence: {result['reason']}", file=sys.stderr)
        return 1
    facts = result["facts"]
    if kind_filter is not None:
        facts = [f for f in facts if f.get("kind") == kind_filter]
    if not facts:
        print("no matching facts")
        return 0
    for fact in list(reversed(facts))[:limit]:
        body = fact.get("body", {})
        tree = body.get("head_tree") or body.get("at_tree")
        # Opaque bodies stay opaque: a non-string value here is a valid
        # envelope whose body this lister doesn't understand — never crash.
        tree_note = f" tree={tree[:12]}" if isinstance(tree, str) and tree else ""
        print(f"{fact.get('ts', '-')}  {fact['kind']:<10} {fact['id']}{tree_note}")
    return 0
