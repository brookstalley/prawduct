"""Command layer for ``prawduct-backlog`` — flags, config, rendering, exit codes.

Owns the CLI surface (api-contract): global flags + the walking-skeleton
subcommands (``add`` / ``get`` / ``list``), the versioned JSON envelope, the
human presentation, and the exit-code scheme. It resolves the target repo (from
``--repo`` or ``.prawduct/project-state.yaml``'s ``backlog.repo``) and the token
(via ``backlog_github.resolve_token``), builds the client, and delegates all
encoding to ``backlog_service`` — this module never speaks HTTP and never encodes
labels or body blocks.

Error discipline: every operational failure is a return-value envelope with a
stable ``error.kind`` and the matching exit code — never a traceback. An
unexpected exception (a bug in us) is the sole traceback path, caught at this
boundary, rendered as an ``internal`` envelope on the data stream with the
traceback on stderr.
"""

from __future__ import annotations

import datetime
import json
import sys
import traceback
from pathlib import Path
from typing import Any

from lib import backlog_github, backlog_service

CONTRACT_VERSION = 1


class UsageError(Exception):
    """A bad-flags / bad-args failure -> ``usage`` envelope, exit 2."""


def run(project_dir: Path, argv: "list[str]") -> int:
    """Entry point invoked by ``bin/prawduct-backlog``; returns an exit code."""
    json_mode = "--json" in argv
    try:
        return _run(project_dir, argv, json_mode)
    except UsageError as err:
        return _emit_error(
            backlog_service.make_error("usage", str(err)), json_mode
        )
    except Exception as err:  # prawduct:allow prawduct/broad-except -- CLI top-level boundary: render an internal-error envelope + traceback, never leak an unhandled traceback onto the data stream (api-contract error model)
        traceback.print_exc(file=sys.stderr)
        return _emit_error(
            backlog_service.make_error("internal", f"internal error: {err}"), json_mode
        )


def _run(project_dir: Path, argv: "list[str]", json_mode: bool) -> int:
    args = _Args(argv, VALUED_FLAGS)
    args.take_flag("--json")  # already inspected

    if args.take_flag("--help") or args.take_flag("-h"):
        _print_help()
        return 0
    if args.take_flag("--version"):
        return _emit_version(project_dir, json_mode)

    repo_override = args.take_value("--repo")
    timeout = args.take_value("--timeout")

    if not args.positionals:
        raise UsageError("no command; expected add|get|list")
    command = args.positionals.pop(0)
    if command not in ("add", "get", "list"):
        raise UsageError(f"unknown command '{command}'; expected add|get|list")

    owner, repo = _resolve_repo(project_dir, repo_override)
    token = backlog_github.resolve_token()
    if not token:
        return _emit_error(
            backlog_service.make_error(
                "auth",
                "no GitHub token; export GH_TOKEN=… or run gh auth login",
            ),
            json_mode,
        )
    client = backlog_github.GitHubClient(
        token, timeout=_parse_timeout(timeout)
    )

    # Each subcommand validates its own leftover args *before* any side-effecting
    # call (a mutating op must never run against an unparsed/bogus flag and then
    # orphan the result behind a usage error).
    if command == "add":
        outcome = _cmd_add(client, owner, repo, args)
    elif command == "get":
        outcome = _cmd_get(client, owner, repo, args)
    else:
        outcome = _cmd_list(client, owner, repo, args)

    return _emit_outcome(command, outcome, json_mode)


# --- Subcommands ------------------------------------------------------------

def _cmd_add(client: Any, owner: str, repo: str, args: "_Args") -> "dict[str, Any]":
    title = args.take_value("--title")
    if not title:
        raise UsageError("add requires --title")
    body = args.take_value("--body")
    stage = args.take_value("--stage")
    labels = args.take_multi("--label")
    args.reject_unconsumed()  # validate before the create — no orphaned mutation
    added = datetime.date.today().isoformat()
    return backlog_service.create_item(
        client, owner, repo, title, body=body, stage=stage, labels=labels, added=added
    )


def _cmd_get(client: Any, owner: str, repo: str, args: "_Args") -> "dict[str, Any]":
    if not args.positionals:
        raise UsageError("get requires an <id>")
    raw_id = args.positionals.pop(0)
    resolved = backlog_service.normalize_id(raw_id, owner, repo)
    if not resolved.get("ok"):
        raise UsageError(resolved.get("message", "ambiguous id"))
    if resolved.get("form") == "alias":
        # Alias (PFX-XXXX) resolution needs a live label lookup; it is minted by
        # the importer, so its resolver lands with the migration slice.
        raise UsageError(
            f"legacy alias '{resolved['alias']}' resolution is not available yet; "
            "use owner/repo#N"
        )
    args.reject_unconsumed()  # validate before the fetch
    return backlog_service.get_item(client, owner, repo, resolved["number"])


def _cmd_list(client: Any, owner: str, repo: str, args: "_Args") -> "dict[str, Any]":
    state = args.take_value("--state") or "open"
    if state not in ("open", "closed", "all"):
        raise UsageError(f"--state must be open|closed|all, got '{state}'")
    labels = args.take_multi("--label")
    assignee = args.take_value("--assignee")
    limit_raw = args.take_value("--limit")
    limit = None
    if limit_raw is not None:
        if not limit_raw.isdigit() or int(limit_raw) <= 0:
            raise UsageError(f"--limit must be a positive integer, got '{limit_raw}'")
        limit = int(limit_raw)
    full = args.take_flag("--full")
    args.reject_unconsumed()  # validate before the query
    # The changed-since query surface (--since consumption with the same-second
    # rewind + dedupe) lands in the query slice; this list still emits the cursor
    # (max updated_at) that surface consumes.
    return backlog_service.list_items(
        client, owner, repo, state=state, labels=labels, assignee=assignee,
        limit=limit, full=full,
    )


# --- Config / token helpers -------------------------------------------------

def _resolve_repo(project_dir: Path, override: "str | None") -> "tuple[str, str]":
    spec = override or _read_backlog_repo(project_dir / ".prawduct" / "project-state.yaml")
    if not spec:
        raise UsageError(
            "no repo configured; pass --repo owner/name or set backlog.repo in "
            "project-state.yaml"
        )
    if spec.count("/") != 1 or not all(spec.split("/")):
        raise UsageError(f"--repo must be owner/name, got '{spec}'")
    owner, name = spec.split("/")
    return owner, name


def _read_backlog_repo(state_path: Path) -> "str | None":
    """Read ``backlog.repo`` (nested under a column-0 ``backlog:`` block).

    A minimal no-PyYAML nested-scalar read matching the project's stdlib-only
    stance; the full ``backlog:`` backend-selection semantics land with the
    governance-integration slice.
    """
    try:
        content = state_path.read_text(encoding="utf-8")
    except OSError:
        return None
    in_block = False
    for raw in content.splitlines():
        stripped = raw.split("#", 1)[0].rstrip()
        if not stripped:
            continue
        if raw[:1] not in (" ", "\t"):
            in_block = stripped.startswith("backlog:")
            continue
        if in_block and stripped.lstrip().startswith("repo:"):
            value = stripped.split(":", 1)[1].strip().strip("\"'")
            return value or None
    return None


def _parse_timeout(value: "str | None") -> float:
    if value is None:
        return backlog_github.DEFAULT_TIMEOUT
    try:
        parsed = float(value)
    except ValueError as err:
        raise UsageError(f"--timeout must be a number, got '{value}'") from err
    if parsed <= 0:
        raise UsageError("--timeout must be positive")
    return parsed


# --- Rendering --------------------------------------------------------------

def _emit_outcome(command: str, outcome: "dict[str, Any]", json_mode: bool) -> int:
    if not outcome.get("ok"):
        return _emit_error(outcome["error"], json_mode, warnings=outcome.get("warnings", []))
    warnings = outcome.get("warnings", [])
    if command == "list":
        data = outcome["data"]
    else:
        data = outcome["item"]
    if json_mode:
        _print_json({"v": CONTRACT_VERSION, "ok": True, "data": data, "warnings": warnings})
    else:
        _print_human(command, data)
        for warning in warnings:
            print(f"! {warning}", file=sys.stderr)
    return 0


def _emit_error(error: "dict[str, Any]", json_mode: bool, warnings: "list[str] | None" = None) -> int:
    if json_mode:
        _print_json(
            {"v": CONTRACT_VERSION, "ok": False, "error": error, "warnings": warnings or []}
        )
    else:
        retry = ""
        if error.get("retry_after") is not None:
            retry = f" (retry after {error['retry_after']}s)"
        print(f"error [{error['kind']}]: {error['message']}{retry}", file=sys.stderr)
    return backlog_service.exit_code_for(error["kind"])


def _print_human(command: str, data: "dict[str, Any]") -> None:
    if command == "list":
        for item in data["items"]:
            print(_item_line(item))
        print(f"{data['count']} item(s)", file=sys.stderr)
        if data.get("cursor"):
            print(f"cursor: {data['cursor']}", file=sys.stderr)
        return
    print(_item_line(data))
    if data.get("body"):
        for line in str(data["body"]).splitlines():
            print(f"    {line}")


def _item_line(item: "dict[str, Any]") -> str:
    stage = f"[stage:{item['stage']}] " if item.get("stage") else ""
    facets = item.get("facets") or {}
    facet_str = ""
    if facets:
        facet_str = "  (" + ", ".join(f"{k}:{v}" for k, v in facets.items()) + ")"
    return f"{item['id']}  {stage}[{item['status']}] {item.get('title', '')}{facet_str}"


def _emit_version(project_dir: Path, json_mode: bool) -> int:
    version = _plugin_version()
    data = {"cli": "prawduct-backlog", "contract_v": CONTRACT_VERSION, "plugin_version": version}
    if json_mode:
        _print_json({"v": CONTRACT_VERSION, "ok": True, "data": data, "warnings": []})
    else:
        print(f"prawduct-backlog (prawduct {version}, contract v{CONTRACT_VERSION})")
    return 0


def _plugin_version() -> str:
    for parent in Path(__file__).resolve().parents:
        manifest = parent / ".claude-plugin" / "plugin.json"
        if manifest.exists():
            try:
                return str(json.loads(manifest.read_text(encoding="utf-8")).get("version", "unknown"))
            except (OSError, ValueError):
                return "unknown"
    return "unknown"


def _print_json(envelope: "dict[str, Any]") -> None:
    print(json.dumps(envelope, ensure_ascii=False))


def _print_help() -> None:
    print(_USAGE)


_USAGE = """\
prawduct-backlog — GitHub Issues backlog service (walking-skeleton slice)

Usage:
  prawduct-backlog add --title T [--body B] [--stage S] [--label pb:…]…
  prawduct-backlog get <id>
  prawduct-backlog list [--state open|closed|all] [--label L]… [--assignee A]
                        [--limit N] [--full]

Global flags:
  --json            emit the versioned JSON envelope on stdout (else human text)
  --repo owner/name overrides backlog.repo from project-state.yaml
  --timeout S       socket timeout in seconds (default 10)
  --version         print version info
  --help            this help

IDs: owner/repo#N (canonical) · repo#N · repo/N · repo-N. Bare numbers are rejected.
Exit codes: 0 ok · 1 operational · 2 usage · 3 retryable (network/rate/5xx).\
"""


# --- Tiny argv helper -------------------------------------------------------

# Flags that consume a following value token. Everything else prefixed with '-'
# is a boolean flag (takes no value). Knowing this set up front is what lets
# positional extraction be correct regardless of flag order — a boolean flag
# placed before the command (``--json get <id>``) must not swallow the command.
VALUED_FLAGS = frozenset(
    {
        "--repo", "--timeout", "--title", "--body", "--stage", "--label",
        "--state", "--assignee", "--since", "--limit",
    }
)


class _Args:
    """A small consume-as-you-go flag parser.

    Hand-rolled (not argparse) so usage errors render as the CLI's own ``usage``
    envelope with exit 2, rather than argparse's stderr format and exit path.
    ``valued_flags`` names the flags that take a value; the rest are booleans.
    """

    def __init__(self, argv: "list[str]", valued_flags: "frozenset[str]") -> None:
        self.valued = valued_flags
        self.tokens: list[str] = []
        self.positionals: list[str] = []
        self._extract_positionals(list(argv))

    def _extract_positionals(self, argv: "list[str]") -> None:
        i = 0
        while i < len(argv):
            token = argv[i]
            if token.startswith("-"):
                self.tokens.append(token)
                base = token.split("=", 1)[0]
                if "=" not in token and base in self.valued and i + 1 < len(argv):
                    self.tokens.append(argv[i + 1])
                    i += 1
            else:
                self.positionals.append(token)
            i += 1

    def take_flag(self, name: str) -> bool:
        if name in self.tokens:
            self.tokens = [t for t in self.tokens if t != name]
            return True
        return False

    def take_value(self, name: str) -> "str | None":
        for i, token in enumerate(self.tokens):
            if token == name:
                if i + 1 >= len(self.tokens):
                    raise UsageError(f"{name} requires a value")
                value = self.tokens[i + 1]
                del self.tokens[i : i + 2]
                return value
            if token.startswith(name + "="):
                value = token.split("=", 1)[1]
                del self.tokens[i]
                return value
        return None

    def take_multi(self, name: str) -> "list[str]":
        values: list[str] = []
        while True:
            value = self.take_value(name)
            if value is None:
                break
            values.append(value)
        return values

    def reject_unconsumed(self) -> None:
        if self.positionals:
            raise UsageError(f"unexpected argument(s): {' '.join(self.positionals)}")
        if self.tokens:
            raise UsageError(f"unknown flag(s): {' '.join(self.tokens)}")
