"""``prawduct-hook learnings-compact``: turn a learnings corpus into one-line
rules under its caps, in one reviewable, revertible commit.

The corpus regrew four times after four sweeps, each time because a control
could be walked around. This command is the sweep that ends in a corpus the
Stop gate then holds: every rule one line of at most
:data:`learnings_files.RULE_LINE_MAX` characters, no bodies, ``core.md``
under :data:`learnings_files.CORE_CAP_KB`.

Mechanical where it can be and model-filled where judgment is needed, on the
``learnings-migrate`` pattern, and it refuses rather than guesses:

1. ``--plan`` writes a **worksheet**: one row per rule unit, with its text, its
   body, its size, how often a review cited it, the area files whose globs
   match a path it names, and related rows (a merge hint, not a verdict). It
   is stored under the git directory, beside ``--local``'s backup, so it is
   never committed.
2. The agent fills one **disposition** per row:
   ``{"action": "rewrite", "text": "- …", "file": "<name>.md"}``,
   ``{"action": "merge-into", "row": "U012"}``,
   ``{"action": "moved-to", "path": "<repo path>", "anchor": "<verbatim text>"}``,
   ``{"action": "banner", "text": "…", "file": "<name>.md"}``, or
   ``{"action": "drop", "reason": "…", "approved": "YYYY-MM-DD"}``.
   A new area file is declared in ``new_areas`` with its ``paths:`` globs.
3. ``--apply`` validates the whole worksheet, then writes every file, deletes
   an area file left with no rules, and records one ``learning.compacted``
   ledger event per rewritten rule so its citation history carries over.

**Drops need the owner.** ``approved`` is a date the owner gave, and an
unapproved drop is refused. The agent keeps that rule as a rewrite for now and
proposes the drop, which is why an apply may leave ``core.md`` over its cap:
then the corpus stays frozen (the Stop gate lets nothing grow) until the owner
approves drops or raises the cap.

**The undo is a commit**, as for the migration: the rules files must be
committed before ``--apply`` overwrites them, unless ``--local`` keeps a
verified private backup instead (the repo that keeps its rules out of git).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import learnings_files, learnings_migrate

SCHEMA = 1

ACTIONS = ("rewrite", "merge-into", "moved-to", "banner", "drop")

#: The shortest anchor a ``moved-to`` row may name. A shorter one matches by
#: accident ("the rule"), and the check exists to prove the text really moved.
MIN_ANCHOR = 20

#: Word-set overlap at which two rows are listed as related, and how many are
#: listed per row. Calibrated on this repo's own corpus (2026-09-24).
RELATED_OVERLAP = 0.2
RELATED_MAX = 3

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_PATHISH = re.compile(r"`([^`\s]+/[^`\s]*|[^`\s]+\.[A-Za-z0-9]{1,5})`")
_WORD = re.compile(r"[a-z0-9]{3,}")


class CompactRefused(RuntimeError):
    """``--apply`` found a reason not to write; nothing was written."""


class CompactInterrupted(RuntimeError):
    """A write failed part-way; ``written`` names what reached disk.

    Nothing is rolled back, as for the migration: the undo is the commit (or
    the ``--local`` backup), and the worksheet is kept so the same decisions
    re-apply once the rules directory is restored.
    """

    def __init__(self, message: str, written: "list[str]") -> None:
        super().__init__(message)
        self.written = written


# ---------------------------------------------------------------------------
# Where the worksheet lives
# ---------------------------------------------------------------------------


def worksheet_path(project_dir: Path) -> "Path | None":
    """``<git-common-dir>/prawduct/learnings-compact/worksheet.json``.

    Beside ``learnings-migrate``'s backup and for the same reason: the common
    dir survives ``git worktree remove``, and nothing there is ever committed.
    """
    backup = learnings_migrate.backup_root(project_dir)
    if backup is None:
        return None
    return backup.parent / "learnings-compact" / "worksheet.json"


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# --plan
# ---------------------------------------------------------------------------


def _cited(prawduct_dir: Path) -> "dict[str, int]":
    """Citations per unit hash, read through earlier compactions."""
    from . import ledger  # noqa: PLC0415 — lazy; the plan is the only reader

    became: dict[str, str] = {}
    fired: dict[str, int] = {}
    for _lineno, event in ledger.iter_events_newest_first(prawduct_dir):
        learning = event.get("learning")
        if not isinstance(learning, dict):
            continue
        if event.get("event") == "learning.compacted":
            old, new = learning.get("from_hash"), learning.get("unit_hash")
            if isinstance(old, str) and isinstance(new, str):
                became[old] = new
        elif event.get("event") == "learning.fired":
            unit = learning.get("unit_hash")
            if isinstance(unit, str):
                fired[unit] = fired.get(unit, 0) + 1
    out: dict[str, int] = {}
    for unit, count in fired.items():
        seen: set[str] = set()
        while unit in became and unit not in seen:
            seen.add(unit)
            unit = became[unit]
        out[unit] = out.get(unit, 0) + count
    return out


def _words(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def build_worksheet(project_dir: Path) -> dict:
    """The worksheet for the corpus as it stands, dispositions empty."""
    project_dir = Path(project_dir)
    layout = learnings_files.resolve(project_dir)
    prawduct_dir = project_dir / ".prawduct"
    cited = _cited(prawduct_dir) if prawduct_dir.is_dir() else {}
    areas = {
        a.path.name: list(a.globs) for a in layout.areas if a.globs
    }
    files: dict[str, dict] = {}
    rows: list[dict] = []
    for path in layout.files:
        rel = path.relative_to(project_dir).as_posix()
        text = path.read_text(encoding="utf-8")
        frontmatter, preamble, blocks = learnings_files.rule_blocks(text)
        files[rel] = {
            "name": path.name,
            "digest": _digest(text),
            "bytes": len(text.encode("utf-8")),
            "frontmatter": frontmatter,
            "preamble": preamble,
        }
        for block in blocks:
            body_paths = _PATHISH.findall(block.unit + "\n" + block.body)
            candidates = sorted(
                name for name, globs in areas.items()
                if body_paths and learnings_files.matches(globs, body_paths)
            )
            rows.append({
                "id": f"U{len(rows) + 1:03d}",
                "file": path.name,
                "line": block.line,
                "text": block.unit,
                "body": block.body,
                "bytes": len((block.raw + "\n" + block.body).encode("utf-8")),
                "cited": cited.get(learnings_files.unit_hash(block.unit), 0),
                "candidate_areas": candidates,
                "disposition": None,
            })
    # A HINT for merge judgment, never a verdict: rules paraphrase each other
    # rather than repeat, so on this repo's corpus the closest real pairs
    # overlap at 0.2-0.35 and a "duplicate" threshold of 0.5 found none of them.
    bags = [_words(r["text"]) for r in rows]
    scored: list[list[tuple[float, str]]] = [[] for _ in rows]
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = bags[i], bags[j]
            if len(a) < 4 or len(b) < 4:
                continue
            overlap = len(a & b) / len(a | b)
            if overlap >= RELATED_OVERLAP:
                scored[i].append((overlap, rows[j]["id"]))
                scored[j].append((overlap, rows[i]["id"]))
    for row, hits in zip(rows, scored):
        row["related"] = [rid for _o, rid in sorted(hits, reverse=True)[:RELATED_MAX]]
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limits": {
            "rule_line_max": learnings_files.RULE_LINE_MAX,
            "core_cap_kb": learnings_files.CORE_CAP_KB,
        },
        "files": files,
        "new_areas": {},
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Validation — everything --apply checks, as a dry run can report it
# ---------------------------------------------------------------------------


@dataclass
class Result:
    """What ``--apply`` would do, or why it may not."""

    refusals: list[str] = field(default_factory=list)
    outputs: dict[str, str] = field(default_factory=dict)
    deletions: list[str] = field(default_factory=list)
    events: list[tuple[str, str, str]] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    over_cap: list[str] = field(default_factory=list)
    undispositioned: list[str] = field(default_factory=list)


def _file_rel(name: str) -> str:
    return f"{learnings_files.RULES_DIR_REL}/{name}"


def validate(project_dir: Path, ws: dict) -> Result:
    """Check every row and build the files ``--apply`` would write."""
    from . import record_lint  # noqa: PLC0415 — lazy; budgets are read once here

    project_dir = Path(project_dir)
    res = Result()
    if ws.get("schema") != SCHEMA:
        res.refusals.append(
            f"worksheet schema {ws.get('schema')!r} is not {SCHEMA}; regenerate it with --plan"
        )
        return res

    # Stale: the corpus changed after --plan, so the rows describe other text.
    for rel, meta in (ws.get("files") or {}).items():
        path = project_dir / rel
        try:
            now = _digest(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            now = None
        if now != meta.get("digest"):
            res.refusals.append(
                f"{rel} changed since --plan, so its rows describe text that is no "
                "longer there. If an earlier --apply was INTERRUPTED, restore the rules "
                f"directory (`git checkout -- {learnings_files.RULES_DIR_REL}` and remove "
                "any file it created, or copy back the --local backup) and re-run --apply; "
                "otherwise regenerate the worksheet with --plan --force"
            )
    layout = learnings_files.resolve(project_dir)
    listed = {p.relative_to(project_dir).as_posix() for p in layout.files}
    for rel in sorted(listed - set(ws.get("files") or {})):
        res.refusals.append(f"{rel} is not in the worksheet (created after --plan); regenerate it")
    if res.refusals:
        return res

    existing = {meta["name"]: meta for meta in ws["files"].values()}
    new_areas = ws.get("new_areas") or {}
    for name, globs in new_areas.items():
        if not name.endswith(".md") or "/" in name or name == learnings_files.CORE_NAME:
            res.refusals.append(f"new area {name!r} must be a plain `<name>.md` other than core.md")
        elif name in existing:
            res.refusals.append(f"new area {name!r} already exists; assign rows to it directly")
        elif not globs or not all(isinstance(g, str) and g.strip() for g in globs):
            res.refusals.append(f"new area {name!r} needs at least one `paths:` glob")
    targets = set(existing) | set(new_areas)

    rows = ws.get("rows") or []
    if not isinstance(rows, list) or not all(
        isinstance(r, dict) and isinstance(r.get("id"), str) and isinstance(r.get("text"), str)
        for r in rows
    ):
        res.refusals.append("every row needs its `id` and `text`; regenerate the worksheet with --plan")
        return res
    by_id = {r["id"]: r for r in rows}
    for r in rows:
        d = r.get("disposition")
        if not isinstance(d, dict) or d.get("action") not in ACTIONS:
            res.undispositioned.append(r["id"])
    if res.undispositioned:
        res.refusals.append(
            f"{len(res.undispositioned)} row(s) have no disposition "
            f"({', '.join(res.undispositioned[:10])}"
            f"{' …' if len(res.undispositioned) > 10 else ''}): every rule needs a decision"
        )

    limit = learnings_files.RULE_LINE_MAX
    placed: dict[str, list[tuple[str, str]]] = {name: [] for name in targets}
    new_hash: dict[str, str] = {}
    pending_drops: list[str] = []
    for r in rows:
        d = r.get("disposition")
        if not isinstance(d, dict) or d.get("action") not in ACTIONS:
            continue
        action = d["action"]
        res.counts[action] = res.counts.get(action, 0) + 1
        rid = r["id"]
        if action in ("rewrite", "banner"):
            text = d.get("text")
            dest = d.get("file")
            if not isinstance(text, str) or "\n" in text or not text.strip():
                res.refusals.append(f"{rid}: `text` must be one non-empty line")
                continue
            if dest not in targets:
                res.refusals.append(
                    f"{rid}: file {dest!r} is neither an existing rules file nor a "
                    "`new_areas` entry"
                )
                continue
            if action == "rewrite":
                if not text.startswith("- "):
                    res.refusals.append(f"{rid}: a rule is written as a `- ` bullet")
                    continue
                line = text.rstrip()
                unit = line[2:].strip()
            else:
                if text.startswith("#") or text.startswith("- "):
                    res.refusals.append(f"{rid}: a banner's text is plain; `## ` is added for it")
                    continue
                line = f"## {text.strip()}"
                unit = text.strip()
            if len(line) > limit:
                res.refusals.append(f"{rid}: {len(line)} characters, over the {limit} limit")
                continue
            placed[dest].append((rid, line))
            new_hash[rid] = learnings_files.unit_hash(unit)
            res.events.append((_file_rel(dest), learnings_files.unit_hash(r["text"]), new_hash[rid]))
        elif action == "drop":
            if not str(d.get("reason") or "").strip():
                res.refusals.append(f"{rid}: a drop names its reason")
            if not _DATE.fullmatch(str(d.get("approved") or "")):
                pending_drops.append(rid)
        elif action == "moved-to":
            rel = str(d.get("path") or "")
            anchor = str(d.get("anchor") or "")
            target = (project_dir / rel).resolve()
            if (
                not rel
                or not target.is_relative_to(project_dir.resolve())
                or target.is_relative_to((project_dir / learnings_files.RULES_DIR_REL).resolve())
            ):
                res.refusals.append(f"{rid}: moved-to path {rel!r} must be a repo file outside the rules directory")
                continue
            if len(anchor) < MIN_ANCHOR:
                res.refusals.append(f"{rid}: moved-to needs an `anchor` of at least {MIN_ANCHOR} characters")
                continue
            try:
                found = anchor in target.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                found = False
            if not found:
                res.refusals.append(f"{rid}: the anchor text is not in {rel}; move the text first")
    if pending_drops:
        res.refusals.append(
            f"{len(pending_drops)} drop(s) have no `approved:` date from the owner "
            f"({', '.join(pending_drops[:10])}{' …' if len(pending_drops) > 10 else ''}). "
            "Show the owner the drop list; until they approve, keep each as a rewrite"
        )
    for r in rows:
        d = r.get("disposition")
        if isinstance(d, dict) and d.get("action") == "merge-into":
            target_row = by_id.get(d.get("row"))
            td = (target_row or {}).get("disposition") or {}
            if target_row is None or td.get("action") != "rewrite" or td.get("file") not in targets:
                res.refusals.append(f"{r['id']}: merge-into must name a row whose action is rewrite")
                continue
            res.events.append((_file_rel(td["file"]), learnings_files.unit_hash(r["text"]), new_hash.get(target_row["id"], "")))
    if res.refusals:
        return res

    # Build the files.
    budgets = record_lint.parse_learnings_budgets(
        record_lint._read_text(project_dir / ".prawduct" / "project-state.yaml") or ""
    )[0]
    for name in sorted(targets):
        lines = [line for _rid, line in placed[name]]
        if name in existing:
            meta = existing[name]
            head = meta["frontmatter"] + (meta["preamble"] or f"# Learnings — {Path(name).stem}")
        else:
            globs = "\n".join(f'  - "{g}"' for g in new_areas[name])
            head = f"---\npaths:\n{globs}\n---\n# Learnings — {Path(name).stem}"
        if not lines and name != learnings_files.CORE_NAME:
            if name in existing:
                res.deletions.append(_file_rel(name))
            continue
        body = ""
        for line in lines:
            body += ("\n" if line.startswith("## ") else "") + line + "\n"
        content = head.rstrip("\n") + "\n\n" + body
        bad = learnings_files.shape_violations(content)
        if bad:
            res.refusals.append(
                f"{name}: the written file would still break the format at line "
                f"{bad[0].line} ({bad[0].kind}) — check its preamble"
            )
            continue
        size = len(content.encode("utf-8"))
        kb = record_lint._effective_kb(name, budgets)
        if size > kb * 1024:
            if name == learnings_files.CORE_NAME:
                res.over_cap.append(f"{name} {size}B over its {kb * 1024}B cap")
            else:
                res.refusals.append(
                    f"{name} would be {size}B, over its {kb * 1024}B budget: move rules to "
                    "another area file, or raise `learnings_budgets` with a reason in a "
                    "commit BEFORE this one (a raise never counts in the session that writes it)"
                )
                continue
        res.outputs[_file_rel(name)] = content
    return res


# ---------------------------------------------------------------------------
# --apply
# ---------------------------------------------------------------------------


def undo_refusals(project_dir: Path, local: bool) -> list[str]:
    """Why ``--apply`` cannot promise an undo. Empty under ``--local``, whose
    undo is the backup :func:`apply` verifies before writing."""
    if local:
        return []
    refusals: list[str] = []
    if learnings_files.rules_dir_is_gitignored(project_dir):
        refusals.append(
            f"{learnings_files.RULES_DIR_REL}/ is gitignored, so no commit can undo "
            "this. Re-run with --local, which keeps a verified private backup."
        )
        return refusals
    proc = learnings_migrate._git(
        project_dir, "status", "--porcelain", "--untracked-files=all", "--",
        learnings_files.RULES_DIR_REL,
    )
    if proc is None or proc.returncode != 0:
        refusals.append(
            "git could not report whether the rules files are committed; the commit "
            "is this command's undo, so an unanswered check is a refusal"
        )
    elif proc.stdout.strip():
        refusals.append(
            "the rules files have uncommitted changes; commit them first, because "
            "the commit is this command's undo:\n    "
            + "\n    ".join(proc.stdout.strip().splitlines())
        )
    return refusals


def apply(project_dir: Path, ws: dict, *, local: bool = False) -> Result:
    """Validate, back up under ``--local``, write, delete, record events."""
    from . import ledger  # noqa: PLC0415 — lazy; only a real apply writes events

    project_dir = Path(project_dir)
    res = validate(project_dir, ws)
    res.refusals.extend(undo_refusals(project_dir, local))
    if res.refusals:
        raise CompactRefused("; ".join(res.refusals))
    if local:
        root = learnings_migrate.backup_root(project_dir)
        if root is None:
            raise CompactRefused("--local: git could not say where the backup goes")
        stamp = datetime.now(timezone.utc).strftime("compact-%Y%m%dT%H%M%SZ")
        rels = sorted(set(ws["files"]) | set(res.outputs))
        learnings_migrate._back_up(
            project_dir, [r for r in rels if (project_dir / r).is_file()], root / stamp
        )
    written: list[str] = []
    try:
        for rel, content in res.outputs.items():
            path = project_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            written.append(rel)
        for rel in res.deletions:
            (project_dir / rel).unlink(missing_ok=True)
            written.append(rel)
    except OSError as exc:
        raise CompactInterrupted(f"{type(exc).__name__}: {exc}", written) from exc
    seen = ledger.learning_events_seen(project_dir / ".prawduct") if (project_dir / ".prawduct").is_dir() else None
    for rel, old, new in res.events:
        if not new or old == new or seen is None:
            continue
        ledger.append_learning_event(
            project_dir, "learning.compacted", file=rel, unit_hash=new,
            from_hash=old, seen=seen,
        )
    return res


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, ws: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(ws, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
