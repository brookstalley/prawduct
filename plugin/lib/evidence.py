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
     "actor": {"session": ..., "worktree": ..., "plugin": ..., "branch": ...},
     "body": {...}}

``schema`` rides on every record so readers can reject-or-skip explicitly
(C7); ``kind`` namespaces the store (``review``/``resolution``/``disposition``
now; ``test-run``/``pr-review``/``promotion`` reserved for later constituent
plans); ``id`` is fixed at dispatch time so consolidation is idempotent
(CRT-4B7X) and readers dedupe. ``actor`` answers the debugging question
("who wrote this, when, from where, under which plugin") — Q7. Its ``branch``
is OPTIONAL and omitted (never null) when HEAD is detached or unreadable; it
was added by #648 because ``worktree`` alone stopped being able to say whether
a tree was disposable, and no reader can probe a tree that is already deleted.

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

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import gitstate

SCHEMA_VERSION = 1
SUPPORTED_SCHEMAS = frozenset({1})
# Kinds this plugin version writes/understands. Unknown kinds under a
# SUPPORTED schema are kept in the facts list (a newer minor may add kinds —
# Q9 forward-compat); gate consumers filter by the kinds they know, so an
# unknown kind can never satisfy a gate, only coexist.
#
# ``disposition`` records the builder's ACCEPT/FILE answer to a finding that
# was never fixed (``dispositions.py``). It is deliberately a separate kind
# from ``resolution``: only ``resolution`` facts with a resolving disposition
# can unblock a BLOCKING finding, and the coverage algebra filters on kind
# before reading any body — so no disposition can ever weaken a gate.
#
# ``guard-refusal`` records that a PRE-DISPATCH GUARD fired — a control that
# declined to spend something (a reviewer, a build) before spending it. It is
# purely observational: no gate reads it, and it CANNOT be read into one,
# because ``coverage_algebra`` derives graph edges from ``kind == "review"``
# facts alone, so a refusal contributes neither an edge nor a node. It lives
# here rather than in the per-worktree governance ledger because these guards
# fire in worktrees that are then deleted — see :func:`append_guard_refusal`.
KNOWN_KINDS = frozenset({"review", "resolution", "disposition", "guard-refusal"})

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

    actor = {
        "session": _session_epoch(project_dir),
        "worktree": str(project_dir),
        "plugin": _plugin_version(),
    }
    # `actor.branch` (#648) — additive, and OMITTED (never null) on a detached
    # HEAD or a failed probe. Since #648 the worktree path alone cannot say
    # whether a tree was disposable: an `agent-<hex>` path is disposable on the
    # harness's scratch branch and durable on a real named one. The reader
    # cannot probe a tree that is usually deleted by the time it looks, so the
    # answer has to be captured here, at write time, or it is unavailable
    # forever. Omitted-not-null makes "no branch recorded" mean exactly one
    # thing on read — the historical shape and the unreadable-branch shape
    # agree, and `gitstate.ephemeral_kind_of` lands both on the restrictive
    # answer. No schema version moves: absent is a valid, meaningful state.
    branch = gitstate.current_branch(project_dir)
    if branch:
        actor["branch"] = branch
    envelope = {
        "schema": SCHEMA_VERSION,
        "kind": kind,
        "id": fact_id,
        "ts": _now_iso(),
        "actor": actor,
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


def append_guard_refusal(
    project_dir: Path,
    guard: str,
    body: dict,
    *,
    dedupe_key: "str | None" = None,
    known_facts: "list[dict] | None" = None,
) -> dict:
    """Record that a pre-dispatch guard fired. One sink for the whole class.

    A guard that declines to spend something leaves no trace by default: its
    message goes to stderr, the shell exits, and the question "has this guard
    ever fired, and did it ever refuse something that turned out to be needed?"
    has no answer but memory. The nonfunctional norm *a control names the yield
    it expects and emits it observably* makes that answer load-bearing — a
    yield claim nothing can falsify is not a yield claim.

    **Why this store and not the governance ledger** (#596, and the
    gate-as-dispatcher build plan's R-26, whose ``ledger-append`` proposal this
    ruling overrides). Four reasons, in the order they decided it:

    1. *Durability.* The ledger lives at ``.prawduct/.governance-ledger.jsonl``
       — inside the worktree. The guards in this class fire in worktrees that
       are then deleted (``_check_ephemeral_worktree`` is the naming case), and
       a record deleted with its worktree answers nothing. This store is at the
       clone's git common dir, which every worktree shares and none owns.
    2. *A reader already exists.* ``prawduct-hook evidence list --kind
       guard-refusal`` is the yield query. The ledger's reader
       (``telemetry.review-stats``) reports ``review.*`` kinds only, so that
       route needed a new event kind AND a whole new reader; this one needed the
       lister taught to render `guard=` and `free=` off a nested interval — a
       column, not a reader. Counting and grouping worked unchanged; the payload
       did not, and a query that shows only "a refusal happened, at this time"
       cannot answer the retirement question, so the claim would have been false
       without it.
    3. *Envelope fit.* The ledger's envelope is review-cost-shaped
       (``duration_seconds``, ``actor.model``, roster). A refusal has no
       reviewer, no model and no duration; it would be a mostly-null row. This
       store's envelope — ``ts``, ``actor.{session,worktree,plugin}`` — is
       exactly what a firing record wants, and ``actor.worktree`` makes
       :func:`is_ephemeral_fact` classify these retroactively for free.
    4. *One path per event class.* #596 owns pre-dispatch-guard telemetry as a
       class and names this sink; a second path for the same class is the thing
       it forbids.

    **Neither store answers a cross-CLONE question** — this one lives inside
    ``.git`` and is never committed, exactly like the ledger. The axis this
    ruling turns on is cross-*worktree* durability plus an existing reader, not
    cross-clone reach, and a yield question spanning clones still needs an
    exporter nobody has built.

    Safe by construction: ``coverage_algebra`` builds its graph from
    ``kind == "review"`` facts alone, so no refusal can add an edge, a node, or
    a hop to any coverage path.

    ``guard`` names the control (stable across firings — it is the grouping
    key); ``body`` carries whatever that guard needs to answer its own yield
    question later. Returns :func:`append_fact`'s result. Callers must treat a
    failure as **soft**: a guard's refusal is correct whether or not the record
    lands, so a store error must never convert it into an error exit. It must
    not be silent either (``learnings.md``: "'advice fails soft' is not 'advice
    fails silent'") — attribute it on stderr and carry on.

    **``dedupe_key`` is for a guard that fires on a POLLED path**, where the
    default one-record-per-firing shape is wrong twice over. ``critic-begin``
    runs once per dispatch, so a fresh id per firing counts dispatches; a gate
    is re-asked several times a session about an unchanged repo, so the same id
    per *observation* is what counts events. It also has to be that way for a
    reason outside this module: ``verdict_cache`` keys the composed coverage
    verdict on a content hash of this whole store, so a record appended on every
    poll would invalidate every memoized verdict on every poll and put the gate
    back on its cold path. With a key, the id is a digest of ``(guard,
    dedupe_key)`` — no timestamp, no uuid — and the second observation of the
    same event appends nothing at all, leaving the store byte-identical.

    A deduped call returns ``{"status": "duplicate", "id": ...}``, which is a
    SUCCESS: the event is already on the record. Callers checking for a degraded
    write must test for it (``status not in ("appended", "duplicate")``), not
    for ``!= "appended"``.

    ``known_facts`` is the probe's input when the caller has already read the
    store — every gate caller has, and on a large store that read is a
    substantial fraction of the gate's whole budget, so re-reading it here would
    charge the transfer's observability to the latency the memo exists to
    protect. Passing the same read the caller is acting on also keeps one moment
    (the pairing :meth:`verdict_cache.VerdictCache.for_read` makes structural for
    the same reason). Omit it and the probe reads the store itself. Either way
    the failure direction is a redundant line, never a missing one: two
    processes racing the same event can both append, and ``read_facts`` dedupes
    ``(kind, id)`` on the way back out.
    """
    if not isinstance(guard, str) or not guard.strip():
        return {"status": "error", "reason": "guard name must be a non-empty string"}
    if not isinstance(body, dict):
        return {"status": "error", "reason": "fact body must be an object"}
    if dedupe_key is not None:
        if not isinstance(dedupe_key, str) or not dedupe_key.strip():
            return {
                "status": "error",
                "reason": "dedupe key must be a non-empty string",
            }
        digest = hashlib.sha256(
            "\0".join((guard.strip(), dedupe_key)).encode("utf-8", "surrogateescape")
        ).hexdigest()[:16]
        fact_id = f"guard-{guard.strip()}-{digest}"
        already = (
            any(
                f.get("id") == fact_id and f.get("kind") == "guard-refusal"
                for f in known_facts
            )
            if isinstance(known_facts, list)
            else has_fact(project_dir, "guard-refusal", fact_id)
        )
        if already:
            return {"status": "duplicate", "id": fact_id}
        return append_fact(
            project_dir, "guard-refusal", fact_id, {**body, "guard": guard.strip()}
        )
    fact_id = "guard-{}-{}-{}".format(
        guard.strip(),
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        uuid.uuid4().hex[:8],
    )
    # `guard` LAST, not first: the id was minted from the parameter, so a body
    # carrying its own "guard" key must not win — a record whose grouping key
    # disagrees with its own id is worse than a rejected write.
    return append_fact(
        project_dir, "guard-refusal", fact_id, {**body, "guard": guard.strip()}
    )


def read_facts(project_dir: Path) -> dict:
    """Read the store. Returns::

        {"status": "ok"|"empty"|"error", "reason"?: str,
         "facts": [envelope, ...],          # schema-supported, deduped, in order
         "schema_ahead": [{"line", "schema", "kind", "id"}, ...],
         "excluded": int, "duplicates": int,
         "fingerprint": str | None}

    ``fingerprint`` is a SHA-256 of the EXACT bytes these facts were parsed
    from, and ``None`` whenever there were none to parse (no repo, no store,
    unreadable). It exists so a caller memoizing a function OF these facts can
    key on it without hashing the parsed structure — and, more to the point,
    without opening the store a second time: the store is shared by every
    worktree of the clone, so a separate read is a separate moment, and a
    sibling's append between the two silently decouples the key from the facts
    it is supposed to describe. Handing it back from the one read makes that
    impossible rather than unlikely.

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
            "fingerprint": None,
        }
    if not path.is_file():
        return {
            "status": "empty",
            "facts": [],
            "schema_ahead": [],
            "excluded": 0,
            "duplicates": 0,
            "fingerprint": None,
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
            "fingerprint": None,
        }

    fingerprint = hashlib.sha256(raw_text.encode('utf-8')).hexdigest()
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
        "fingerprint": fingerprint,
    }


def facts_of_kind(read_result: dict, kind: str) -> list[dict]:
    """Filter a ``read_facts`` result to one kind — the consumer-side filter
    that makes unknown future kinds harmless (they can coexist, never satisfy)."""
    return [f for f in read_result.get("facts", []) if f.get("kind") == kind]


def findings_index(read_result: dict) -> dict[tuple[str, str], dict]:
    """``(review_id, fid)`` → the finding entry its review fact recorded.

    The one walk over recorded findings, shared by every consumer that joins
    on a finding: the existence check a resolution must pass before it may
    weaken a gate (``critic_consolidate``) needs only the key set, while a
    census needs each finding's severity and title (``dispositions``). Keeping
    the richer structure here stops the two from drifting into separate walks
    that disagree about what "recorded" means.

    Findings without a usable ``fid`` are skipped — nothing can join to them,
    which is exactly why the writer always assigns one.
    """
    index: dict[tuple[str, str], dict] = {}
    for fact in facts_of_kind(read_result, "review"):
        review_id = fact.get("id")
        if not isinstance(review_id, str) or not review_id:
            continue
        body = fact.get("body") or {}
        findings = body.get("findings")
        if not isinstance(findings, list):
            continue
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            fid = finding.get("fid")
            if isinstance(fid, str) and fid.strip():
                index[(review_id, fid)] = finding
    return index


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
    except UnicodeDecodeError as exc:
        # `text=True` decodes strictly, so a command whose output carries file
        # CONTENT (a diff) raises on the first non-UTF-8 byte in any consuming
        # repo — a binary blob, a latin-1 doc. Every caller here already treats
        # a nonzero return as "could not read this", which is the honest answer
        # and the fail-soft one; letting the exception escape instead takes down
        # whichever gate happened to ask. Reported, never silent.
        return 1, "", f"output is not valid UTF-8: {exc}"
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _attribute_bad_tree(value: object) -> None:
    """Name a shape-rejected tree id on stderr — skip WITH attribution, this
    module's posture for malformed input.

    Truncated and repr'd: the value came from a file on disk and is untrusted,
    so it is never pasted raw into a message. Deduped per process, because a
    single corrupt fact is probed once per gate pass per composition path and
    the tenth copy of the same line teaches nothing."""
    key = repr(value)[:80]
    if key in _ATTRIBUTED_BAD_TREES:
        return
    _ATTRIBUTED_BAD_TREES.add(key)
    print(
        f"evidence: ignoring a fact whose tree id is not a git object id ({key}) — "
        "it contributes no review coverage; the store may have been hand-edited",
        file=sys.stderr,
    )


_ATTRIBUTED_BAD_TREES: set[str] = set()


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


def tree_diff(
    project_dir: Path, tree_a: str, tree_b: str, paths: "list[str] | None" = None
) -> "list[str] | None":
    """Paths changed between two tree objects (``git diff --name-only``),
    or ``None`` when the diff cannot be computed (missing object, git
    failure) — never guessed, matching ``coverage_algebra.DiffFn``'s
    contract. This is the diff the gates inject into the algebra and the
    dispatch side uses for its ``files_changed`` snapshot, so the recorded
    set and the composed edge-validity check agree by construction.

    ``paths`` narrows the question to a pathspec: *do these two trees differ on
    THESE files?* Asked of a whole tree the answer costs a full tree walk; asked
    of a handful of paths it costs a pruned one, which is what makes a per-file
    equality check affordable across many candidate trees
    (``coverage.diagnose_base_advance_transfer``). The comparison stays git's
    own, so a mode-only change (``chmod +x``, a file becoming a symlink at the
    same blob) still reports as a difference — the fail-OPEN that a
    ``(path, object id)`` comparison would introduce, and that
    :func:`tree_entries` documents at length, never arises.

    **A path this function reports must be a path it can be asked back about,
    and two separate git conventions break that round trip.** Both matter here
    because the returned list becomes the pathspec of the next call
    (``coverage.diagnose_base_advance_transfer`` asks "do these trees differ on
    the files you just told me changed?"), and both are answered at this
    boundary rather than by each caller.

    - ``-z``, so paths come back RAW. ``--name-only`` alone honours
      ``core.quotepath``, which is on by default, so a non-ASCII filename is
      returned C-quoted — ``"caf\\303\\251.py"``, surrounding quotes included.
      Handed back as a pathspec that string matches nothing on disk, git
      reports no difference over a file it never compared, and a caller reading
      emptiness as agreement gets a fail-OPEN. ``-c core.quotepath=false`` is
      NOT sufficient: a name containing ``"`` or ``\\`` stays quoted regardless
      (pinned in ``tests/test_record_lint.py``), so only ``-z`` closes it. Same
      reasoning, same fix as :func:`tree_entries`.
    - ``:(literal)`` on each pathspec, because pathspecs are wildmatch patterns
      and real filenames carry glob metacharacters (``app/[id]/page.tsx`` is an
      ordinary route convention). Measured rather than assumed (2026-08-13):
      git compares a pathspec literally *as well as* by wildmatch, so a path
      does select its own spelling — but ``x[a].py`` ALSO selects ``xa.py``, so
      an unrelated file can answer a question asked about this one. That
      direction is a spurious *denial* rather than a wrong pass, but it is
      silent, and ``:(literal)`` removes the class instead of leaving
      correctness resting on git's match ORDER.

    (``--`` stops option injection; it does nothing about either of these.)

    A tree id that is not a full-length object id never reaches git argv — it
    is a malformed fact, and a malformed fact yields no answer here for the
    same reason it yields no edge in the algebra. Rejection is **attributed**
    to stderr per this module's error posture: a store holding an unreadable
    tree id is corrupted, and silently answering ``None`` would present that as
    an ordinary "cannot compute"."""
    for value in (tree_a, tree_b):
        if not gitstate.is_object_id(value):
            _attribute_bad_tree(value)
            return None
    pathspec = ["--", *(f":(literal){p}" for p in paths)] if paths else []
    rc, out, _err = run_git(
        project_dir, "diff", "--name-only", "-z", tree_a, tree_b, *pathspec
    )
    if rc != 0:
        return None
    return [path for path in out.split("\0") if path]


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

    Shape-gated like :func:`tree_diff`: a tree id that is not a full-length
    object id is unreadable by definition, so it denies a free edge rather
    than being handed to git, and the rejection is attributed.
    """
    if not gitstate.is_object_id(tree):
        _attribute_bad_tree(tree)
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

# The store is append-only, shared by every worktree of the clone, and never
# pruned. Composition cost is linear in the number of distinct TREES it
# mentions (not facts), so that is the number worth watching — and watching it
# is the whole point: a deferral whose trigger nothing measures fires only if
# someone happens to notice, which is the same silence the gates exist to end.
# Advisory, never a block: `nonfunctional-requirements` makes state-file growth
# something that prompts compaction, not something that stops work.
TREE_COUNT_ADVISORY = 10_000


def distinct_trees(facts: list[dict]) -> set[str]:
    """Every tree id the store's REVIEW facts mention, on either side of an
    edge — the node set coverage composition actually walks.

    The kind filter is the whole contract, not a detail: only review facts
    become edges (``coverage_algebra`` line-one filter), so only their trees
    are nodes. Reading every kind's body for a ``base_tree`` key would let a
    purely observational fact — a ``guard-refusal``, a future ``test-run`` —
    inflate ``evidence status``'s tree count with trees no review covers,
    which reads as coverage that does not exist.
    """
    trees: set[str] = set()
    for fact in facts:
        if fact.get("kind") != "review":
            continue
        body = fact.get("body") or {}
        for key in ("base_tree", "head_tree"):
            value = body.get(key)
            if isinstance(value, str) and value:
                trees.add(value)
    return trees


_CLI_USAGE = "Usage: prawduct-hook evidence {status|list [--kind <k>] [-n <count>]}"


def evidence_cmd(project_dir: Path, argv: list[str]) -> int:
    sub = argv[0] if argv else "status"
    if sub == "status":
        return _cmd_status(project_dir)
    if sub == "list":
        return _cmd_list(project_dir, argv[1:])
    print(_CLI_USAGE, file=sys.stderr)
    return 1


def is_ephemeral_fact(fact: dict) -> bool:
    """Whether one fact was recorded from a disposable worktree.

    The per-fact predicate is the public one so no caller has to hold a
    collection to ask the question — an earlier version marked list rows by
    matching ``id()`` against a prebuilt set, which was correct only while
    ``ephemeral_facts`` returned the very dicts the caller still held, and would
    have failed silently the moment anything normalized or re-parsed a fact on
    the way out.
    """
    actor = fact.get("actor")
    if not isinstance(actor, dict):
        return False  # opaque envelope — never crash a reader on one
    worktree = actor.get("worktree")
    if not isinstance(worktree, str):
        return False
    # `actor.branch` when the writer recorded one (#648). A non-string is
    # treated as absent rather than rejected: same reader convention as the
    # opaque envelope above, and absence lands on the restrictive answer, so a
    # malformed field cannot quietly promote a disposable tree to durable.
    branch = actor.get("branch")
    if not isinstance(branch, str) or not branch:
        branch = None
    return gitstate.ephemeral_kind_of(worktree, branch) is not None


def ephemeral_facts(facts: list[dict]) -> list[dict]:
    """Facts recorded from a disposable worktree, by ``actor`` path + branch.

    Classification is derived on READ, so no schema version moves and every
    fact already in the store still classifies. What #648 changed is that the
    *inputs* now include ``actor.branch``, which only facts written since then
    carry — a branch-less record keeps exactly the reading it always had (see
    :func:`gitstate.ephemeral_kind_of`), and is almost always genuinely
    disposable, since the guard refused the durable case for as long as that
    shape existed. Two carve-outs make that "almost": a write forced with
    ``PRAWDUCT_ALLOW_EPHEMERAL_WRITES=1``, and the harness-invoked commands the
    guard exempts — either could have recorded a branch-less fact from a tree
    that was not disposable. Both are rare and neither is worth a schema move;
    the classification is restrictive, so such a fact reads as covering
    nothing, which understates coverage rather than overstating it.

    These facts are **not** filtered out of anything. Tree-keying already makes
    them cover nothing — a fact recorded against a disposable worktree's tree
    matches no branch the dispatcher will ever have — so the gates compose
    correctly today and suppressing the facts would *change* gate behavior
    rather than describe it (`data-model.md` § Direction: derived views are
    disposable and never authoritative). What is missing is only that such a
    fact reads in `evidence status` exactly like a review that covers the
    branch, so a full-cost review that vouched for nothing looks like coverage.
    """
    return [f for f in facts if is_ephemeral_fact(f)]


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
    trees = distinct_trees(result["facts"])
    print(f"trees referenced: {len(trees)}")
    # Only COVERAGE-BEARING kinds belong in the wasted-cost sentence. A
    # `guard-refusal` recorded from a disposable worktree covers no branch
    # either, but saying "the review cost was spent" of it is exactly backwards
    # — no reviewer ran, which is the entire point of the record.
    ephemeral = [f for f in ephemeral_facts(result["facts"]) if f.get("kind") == "review"]
    if ephemeral:
        print(
            f"from ephemeral worktrees: {len(ephemeral)} (these COVER NO BRANCH — "
            "recorded in a disposable agent/workflow worktree whose trees no "
            "branch will ever carry; the review cost was spent, the coverage was "
            "not gained). Run reviews and test-evidence from the dispatching "
            "session instead."
        )
    if len(trees) >= TREE_COUNT_ADVISORY:
        print(
            f"NOTE: {len(trees)} distinct trees. Coverage composition is linear in this "
            "count, so the store has reached the size where compaction is worth "
            "scheduling. Advisory only — nothing is blocked, and a fact may only be "
            "dropped if no surviving path can traverse it (reachability, not age)."
        )
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
        if not (isinstance(tree, str) and tree):
            # A refusal nests its interval under `body.interval` ON PURPOSE, so
            # no edge-walker can mistake it for a coverage edge — which also
            # means the top-level lookup above finds nothing. Reach for it
            # explicitly rather than leaving the row blank: a listing that shows
            # only "a refusal happened, at this time" cannot answer the question
            # this record exists for ("did it ever refuse a round that turned
            # out to be needed?"), and the claim that this command IS the yield
            # query would be false.
            interval = body.get("interval")
            if isinstance(interval, dict):
                tree = interval.get("head_tree")
        tree_note = f" tree={tree[:12]}" if isinstance(tree, str) and tree else ""
        guard = body.get("guard") if isinstance(body, dict) else None
        guard_note = f" guard={guard}" if isinstance(guard, str) and guard else ""
        free = body.get("free_files") if isinstance(body, dict) else None
        if isinstance(free, list) and free:
            shown = ", ".join(str(p) for p in free[:3])
            more = f" +{len(free) - 3}" if len(free) > 3 else ""
            guard_note += f" free=[{shown}{more}]"
        # Marked inline rather than filtered: the fact is real and stays listed;
        # what it does not do is cover a branch.
        origin = " [ephemeral — covers no branch]" if is_ephemeral_fact(fact) else ""
        print(
            f"{fact.get('ts', '-')}  {fact['kind']:<10} {fact['id']}"
            f"{tree_note}{guard_note}{origin}"
        )
    return 0
