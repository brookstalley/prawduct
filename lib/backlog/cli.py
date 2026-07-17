"""CLI — the ``prawduct-hook backlog <op>`` runner (the stable public contract).

A **thin** front over ``core`` (Test Specs §1.1): it parses flags, calls the core
op, serializes the envelope, and maps the error code to a stable exit class. All
the logic lives in ``core``; this layer adds only the CLI surface.

Output discipline (AG6, API §3/§8):
- ``--json`` → the JSON envelope is the **sole stdout content**; a ``| jq`` never
  chokes. ``warnings[]`` rides inside that envelope (still valid JSON).
- default (human) → a readable summary to stdout, narration/warnings to stderr.

Non-interactive always (INV-2): the runner never prompts and never reads stdin.

Exit codes are a small fixed set of classes (a build-time coherence check, API
§11) so scripts can branch without parsing the body:
``0 ok · 2 validation · 3 not-found · 4 conflict · 5 auth · 6 unavailable``.
"""

from __future__ import annotations

import json
import sys

from . import core, ids

# code → exit class. A code absent here (should not happen) falls back to 1.
_EXIT_CLASS: dict[str, int] = {
    "validation": 2,
    "ambiguous_id": 2,
    "alias_collision": 2,
    "unsupported": 2,
    "not_found": 3,
    "conflict": 4,
    "claim_conflict": 4,
    "auth": 5,
    "unavailable": 6,
    "rate_limited": 6,
}

_HELP = (
    "usage: prawduct-hook backlog <op> [flags]\n"
    "  file     --repo owner/repo --title T --body B "
    "[--stage S] [--kind K] [--area A] [--effort E] [--impact I] [--source SRC]\n"
    "  get      <id> [--repo owner/repo]\n"
    "  status   <id> --to submitted|open|in-progress|shipped|dropped [--repo owner/repo]\n"
    "  update   <id> [--title T] [--body B] [--stage S] [--kind K] [--area A] "
    "[--effort E] [--impact I] [--source SRC] [--if-updated-at TS] [--repo owner/repo]\n"
    "  comment  <id> --body B [--repo owner/repo]\n"
    "  provision --repo owner/repo\n"
    "global: --json  (machine envelope on stdout; default is human)\n"
)


def run(project_dir, argv: list[str], *, transport=None) -> int:
    """Dispatch ``backlog <op> ...``; emit the envelope, return an exit code.

    ``argv`` is the tokens after ``backlog`` (``sys.argv[2:]``). ``transport`` is
    injected by tests (the L1 fake); in production it defaults to the real
    ``gh``-backed transport built lazily so no import cost lands on other paths.
    """
    json_mode = "--json" in argv
    argv = [tok for tok in argv if tok != "--json"]

    if not argv:
        return _emit(core.error("validation", "no operation given"), json_mode=json_mode, usage=True)

    op = argv[0]
    rest = argv[1:]

    try:
        if op == "file":
            result = _run_file(rest, transport)
        elif op in ("get", "show"):
            result = _run_get(rest, transport)
        elif op == "status":
            result = _run_status(rest, transport)
        elif op == "update":
            result = _run_update(rest, transport)
        elif op == "comment":
            result = _run_comment(rest, transport)
        elif op == "provision":
            result = _run_provision(rest, transport)
        else:
            return _emit(
                core.error(
                    "validation",
                    f"unknown op {op!r} "
                    "(expected file|get|status|update|comment|provision)",
                ),
                json_mode=json_mode,
                usage=True,
            )
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- CLI boundary: an unforeseen exception must become a clean, token-free envelope, never a raw traceback on stdout (SEC-1)
        from .transport import scrub_secrets

        # Surface (scrubbed) on stderr so it is never swallowed; keep stdout a
        # generic envelope so no unexpected detail — token or otherwise — leaks.
        print(
            f"backlog: unexpected failure in {op!r}: "
            f"{scrub_secrets(type(exc).__name__ + ': ' + str(exc))}",
            file=sys.stderr,
        )
        result = core.error("unavailable", "an unexpected error occurred")

    return _emit(result, json_mode=json_mode)


# --- op handlers -------------------------------------------------------------


def _run_file(rest: list[str], transport):
    flags, positionals, err = _parse_flags(
        rest,
        valued={"repo", "title", "body", "stage", "kind", "area", "effort", "impact", "source"},
    )
    if err:
        return core.error("validation", err)
    repo_spec = flags.get("repo")
    parsed = ids.parse_repo(repo_spec) if repo_spec else None
    if parsed is None:
        return core.error("validation", "file requires --repo owner/repo")
    if "body" not in flags:
        # Only title+body are required to file (API §3); an empty --body is fine,
        # but an omitted one is not (title-only capture is not the contract).
        return core.error("validation", "file requires --body (may be empty: --body '')")
    owner, repo = parsed
    facets = {
        key: flags[key]
        for key in ("stage", "kind", "area", "effort", "impact", "source")
        if key in flags
    }
    transport = _resolve_transport(transport)
    return core.file_item(
        transport,
        owner=owner,
        repo=repo,
        title=flags.get("title", ""),
        body=flags.get("body", ""),
        facets=facets,
    )


def _run_get(rest: list[str], transport):
    flags, positionals, err = _parse_flags(rest, valued={"repo"})
    if err:
        return core.error("validation", err)
    if not positionals:
        return core.error("validation", "get requires an <id>")
    id_raw = positionals[0]
    default_owner = None
    if flags.get("repo"):
        parsed = ids.parse_repo(flags["repo"])
        if parsed is None:
            return core.error("validation", "--repo must be owner/repo")
        default_owner = parsed[0]
    transport = _resolve_transport(transport)
    return core.get_item(transport, id_raw=id_raw, default_owner=default_owner)


def _run_status(rest: list[str], transport):
    flags, positionals, err = _parse_flags(rest, valued={"repo", "to"})
    if err:
        return core.error("validation", err)
    if not positionals:
        return core.error("validation", "status requires an <id>")
    target = flags.get("to")
    if not target:
        return core.error(
            "validation",
            "status requires --to <target> (submitted|open|in-progress|shipped|dropped)",
        )
    default_owner, err = _default_owner(flags)
    if err:
        return core.error("validation", err)
    transport = _resolve_transport(transport)
    return core.set_status(
        transport, id_raw=positionals[0], target=target, default_owner=default_owner
    )


def _run_update(rest: list[str], transport):
    flags, positionals, err = _parse_flags(
        rest,
        valued={
            "repo", "title", "body", "stage", "kind", "area",
            "effort", "impact", "source", "if-updated-at",
        },
    )
    if err:
        return core.error("validation", err)
    if not positionals:
        return core.error("validation", "update requires an <id>")
    fields = {
        key: flags[key]
        for key in ("title", "body", "stage", "kind", "area", "effort", "impact", "source")
        if key in flags
    }
    default_owner, err = _default_owner(flags)
    if err:
        return core.error("validation", err)
    transport = _resolve_transport(transport)
    return core.update_item(
        transport,
        id_raw=positionals[0],
        fields=fields,
        expected_updated_at=flags.get("if-updated-at"),
        default_owner=default_owner,
    )


def _run_comment(rest: list[str], transport):
    flags, positionals, err = _parse_flags(rest, valued={"repo", "body"})
    if err:
        return core.error("validation", err)
    if not positionals:
        return core.error("validation", "comment requires an <id>")
    if "body" not in flags:
        return core.error("validation", "comment requires --body")
    default_owner, err = _default_owner(flags)
    if err:
        return core.error("validation", err)
    transport = _resolve_transport(transport)
    return core.comment_item(
        transport, id_raw=positionals[0], body=flags["body"], default_owner=default_owner
    )


def _run_provision(rest: list[str], transport):
    flags, positionals, err = _parse_flags(rest, valued={"repo"})
    if err:
        return core.error("validation", err)
    parsed = ids.parse_repo(flags.get("repo", ""))
    if parsed is None:
        return core.error("validation", "provision requires --repo owner/repo")
    owner, repo = parsed
    transport = _resolve_transport(transport)
    return core.provision_labels(transport, owner=owner, repo=repo)


# --- plumbing ----------------------------------------------------------------


def _resolve_transport(transport):
    if transport is not None:
        return transport
    from .transport import GhTransport  # lazy — no gh import cost on other paths

    return GhTransport()


def _default_owner(flags: dict) -> tuple[str | None, str | None]:
    """Resolve the same-owner default from ``--repo`` (for short IDs like ``repo#N``).

    Returns ``(owner_or_None, error_or_None)``; a present-but-malformed ``--repo``
    is an error string, an absent one is ``(None, None)``.
    """
    repo = flags.get("repo")
    if not repo:
        return None, None
    parsed = ids.parse_repo(repo)
    if parsed is None:
        return None, "--repo must be owner/repo"
    return parsed[0], None


def _parse_flags(tokens: list[str], *, valued: set[str]):
    """Parse ``--key value`` / ``--key=value`` flags and positionals.

    Returns ``(flags, positionals, error_message)``. ``valued`` names the flags
    that take a value; an unknown flag or a missing value is an error string.
    """
    flags: dict[str, str] = {}
    positionals: list[str] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--"):
            key, sep, value = token[2:].partition("=")
            if key not in valued:
                return {}, [], f"unknown flag: {token}"
            if sep:
                flags[key] = value
            elif i + 1 < len(tokens):
                flags[key] = tokens[i + 1]
                i += 1
            else:
                return {}, [], f"--{key} requires a value"
        else:
            positionals.append(token)
        i += 1
    return flags, positionals, None


def _emit(result: dict, *, json_mode: bool, usage: bool = False) -> int:
    """Print the result in the chosen mode and return the exit code."""
    exit_code = _exit_code(result)
    if json_mode:
        # The envelope is the sole stdout content (ERR-2). Nothing else on stdout.
        print(json.dumps(result))
        return exit_code

    # Human mode: payload/summary to stdout, narration + warnings to stderr.
    if result.get("status") == "ok":
        _print_human_ok(result.get("data"))
        for warning in result.get("warnings", []):
            print(f"warning: {warning}", file=sys.stderr)
    else:
        err = result.get("error", {})
        print(f"error [{err.get('code')}]: {err.get('message')}", file=sys.stderr)
        if usage:
            print(_HELP, file=sys.stderr)
    return exit_code


def _print_human_ok(data) -> None:
    if isinstance(data, dict) and "item" in data and "url" in data:
        # A comment result (distinct from an item — no status/stage axes).
        print(f"commented on {data.get('item')} by {data.get('actor')}")
        if data.get("url"):
            print(f"  {data['url']}")
    elif isinstance(data, dict) and "id" in data:
        line = data.get("id") or ""
        if data.get("title"):
            line = f"{line}  {data['title']}"
        print(line)
        bits = [f"status={data.get('status')}"]
        if data.get("stage"):
            bits.append(f"stage={data['stage']}")
        print("  " + "  ".join(bits))
    elif isinstance(data, dict) and "created" in data:
        print(
            f"{data.get('repo')}: {len(data.get('created', []))} label(s) created, "
            f"{len(data.get('existing', []))} already present"
        )
    else:
        print(json.dumps(data))


def _exit_code(result: dict) -> int:
    if result.get("status") == "ok":
        return 0
    code = result.get("error", {}).get("code", "")
    return _EXIT_CLASS.get(code, 1)
