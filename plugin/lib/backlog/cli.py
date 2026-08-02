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

from . import context, core, ids, query

# GitHub-mutating ops — refused under an untrusted-triggered Actions run absent an
# explicit triggering-actor authorization check (SEC-5). Reads, ``counts``, and
# ``refresh-counts`` (a read + a local snapshot write) are never withheld —
# read-only reporting under such triggers is fine (Security §1b). ``pick`` is a
# write only with ``--claim`` (handled in ``_is_write``).
_WRITE_OPS: frozenset[str] = frozenset(
    {"file", "status", "update", "comment", "claim", "unclaim",
     "link", "unlink", "provision", "reconcile-labels", "import", "merge"}
)

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
    "  list     --repo owner/repo [--status S] [--stage S] [--kind K] [--area A] "
    "[--effort E] [--impact I] [--source SRC] [--assignee A|none|*] "
    "[--state open|closed|all] [--sort created|updated] [--direction asc|desc] "
    "[--per-page N] [--page N] [--untriaged]\n"
    "           --untriaged inverts the scope filter: shows only issues with no "
    "prawduct labels or block\n"
    "  pick     --repo owner/repo [--limit N] [--claim] [--claim-ttl SECONDS]\n"
    "  counts   --repo owner/repo\n"
    "  refresh-counts   --repo owner/repo   (derive + persist the briefing snapshot)\n"
    "  claim    <id> [--repo owner/repo] [--claim-ttl SECONDS]\n"
    "  unclaim  <id> [--repo owner/repo]\n"
    "  link     <id> --edge blocks|blocked-by|parent|child|related --to <target-id> [--repo owner/repo]\n"
    "  unlink   <id> --edge blocks|blocked-by|parent|child|related --to <target-id> [--repo owner/repo]\n"
    "  provision --repo owner/repo\n"
    # GV6. The id stays here, out of the operator's way: text emitted into a
    # governed product carries the reason, never a prawduct-internal label.
    "  reconcile-labels --repo owner/repo   "
    "(add missing taxonomy labels; never removes or edits existing ones)\n"
    "  import   --repo owner/repo --from <backlog.md> [--archive <archive.md>] "
    "[--restructure <plan.json>] [--archive-scope all|open]   "
    # MG6 — see the note on reconcile-labels above.
    "(resumable/idempotent; a --restructure plan is applied as each issue "
    "is created, not as a later edit)\n"
    "  restructure-preview --from <backlog.md> [--archive <archive.md>] "
    "--plan <plan.json> --out <preview.md> [--archive-scope all|open]   "
    "(offline before/after review artifact)\n"
    "  verify-migration --repo owner/repo --from <backlog.md> [--archive <archive.md>] "
    "[--archive-scope all|open]   (completeness gate — exit 4 names any source item with "
    "no issue on the target, and any whose id is not a valid PFX so no alias can key it; "
    "run before recording the cutover)\n"
    "  export   --repo owner/repo --to <dir>   (full-fidelity dump incl. native graph)\n"
    "  merge    <source-id> --into <target-id> [--repo owner/repo]   (fold A→B, redirect-before-close)\n"
    "global: --json  (machine envelope on stdout; default is human)\n"
    "\n"
    "issue standard: `file` emits an `area:`-prefixed title and audits the issue\n"
    "  (WARN-only `lint` findings, never blocks). Author a scannable `area: summary`\n"
    "  title (<=72) + a sectioned body (bug: Problem/Repro/Actual/Expected/Evidence;\n"
    "  task: Problem/Proposed change/Acceptance `- [ ]`/Scope-out) and set --kind.\n"
    "  Full contract: documentation/backlog-service-issue-standard.md\n"
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

    # SEC-5 — withhold writes under an untrusted-triggered Actions run (pwn-request
    # defense). Checked before dispatch so no mutating path can run at all.
    if _is_write(op, rest) and context.writes_withheld():
        return _emit(
            core.error("auth", context.WITHHOLD_MESSAGE, retryable=False),
            json_mode=json_mode,
        )

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
        elif op == "list":
            result = _run_list(rest, transport)
        elif op == "pick":
            result = _run_pick(rest, transport)
        elif op == "counts":
            result = _run_counts(rest, transport)
        elif op == "verify-migration":
            result = _run_verify_migration(rest, transport)
        elif op == "refresh-counts":
            result = _run_refresh_counts(rest, transport, project_dir)
        elif op == "reconcile-labels":
            result = _run_reconcile_labels(rest, transport)
        elif op == "claim":
            result = _run_claim(rest, transport)
        elif op == "unclaim":
            result = _run_unclaim(rest, transport)
        elif op in ("link", "unlink"):
            result = _run_link(op, rest, transport)
        elif op == "provision":
            result = _run_provision(rest, transport)
        elif op == "import":
            result = _run_import(rest, transport, project_dir)
        elif op == "restructure-preview":
            result = _run_restructure_preview(rest)
        elif op == "export":
            result = _run_export(rest, transport)
        elif op == "merge":
            result = _run_merge(rest, transport)
        else:
            return _emit(
                core.error(
                    "validation",
                    f"unknown op {op!r} (expected file|get|status|update|comment|"
                    "list|pick|counts|refresh-counts|claim|unclaim|link|unlink|"
                    "provision|reconcile-labels|import|verify-migration|"
                    "restructure-preview|export|merge)",
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
    # Unattended context (SEC-6): a background/Actions run stamps its creates
    # `automated: true` + a worker marker so a sweep is not misattributed.
    automated = context.is_unattended()
    return core.file_item(
        transport,
        owner=owner,
        repo=repo,
        title=flags.get("title", ""),
        body=flags.get("body", ""),
        facets=facets,
        automated=automated,
        worker=context.worker_marker() if automated else None,
    )


def _run_get(rest: list[str], transport):
    flags, positionals, err = _parse_flags(rest, valued={"repo"})
    if err:
        return core.error("validation", err)
    if not positionals:
        return core.error("validation", "get requires an <id>")
    id_raw = positionals[0]
    default_owner = None
    default_repo = None
    if flags.get("repo"):
        parsed = ids.parse_repo(flags["repo"])
        if parsed is None:
            return core.error("validation", "--repo must be owner/repo")
        default_owner = parsed[0]
        default_repo = parsed  # (owner, repo) — the repo a bare PFX resolves against
    transport = _resolve_transport(transport)
    return core.get_item(
        transport, id_raw=id_raw, default_owner=default_owner, default_repo=default_repo
    )


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
    default_owner, default_repo, err = _repo_defaults(flags)
    if err:
        return core.error("validation", err)
    transport = _resolve_transport(transport)
    return core.set_status(
        transport,
        id_raw=positionals[0],
        target=target,
        default_owner=default_owner,
        default_repo=default_repo,
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
    default_owner, default_repo, err = _repo_defaults(flags)
    if err:
        return core.error("validation", err)
    transport = _resolve_transport(transport)
    return core.update_item(
        transport,
        id_raw=positionals[0],
        fields=fields,
        expected_updated_at=flags.get("if-updated-at"),
        default_owner=default_owner,
        default_repo=default_repo,
    )


def _run_comment(rest: list[str], transport):
    flags, positionals, err = _parse_flags(rest, valued={"repo", "body"})
    if err:
        return core.error("validation", err)
    if not positionals:
        return core.error("validation", "comment requires an <id>")
    if "body" not in flags:
        return core.error("validation", "comment requires --body")
    default_owner, default_repo, err = _repo_defaults(flags)
    if err:
        return core.error("validation", err)
    transport = _resolve_transport(transport)
    return core.comment_item(
        transport,
        id_raw=positionals[0],
        body=flags["body"],
        default_owner=default_owner,
        default_repo=default_repo,
    )


def _run_list(rest: list[str], transport):
    flags, _positionals, err = _parse_flags(
        rest,
        valued={
            "repo", "status", "stage", "kind", "area", "effort", "impact",
            "source", "assignee", "state", "sort", "direction", "per-page", "page",
        },
        boolean={"untriaged"},
    )
    if err:
        return core.error("validation", err)
    parsed = ids.parse_repo(flags.get("repo", ""))
    if parsed is None:
        return core.error("validation", "list requires --repo owner/repo")
    owner, repo = parsed
    filters = {
        key: flags[key]
        for key in (
            "status", "stage", "kind", "area", "effort", "impact", "source",
            "assignee", "state",
        )
        if key in flags
    }
    if "untriaged" in flags:
        filters["untriaged"] = True
        # --untriaged always scans every page (the set is small and its members
        # are the NEWEST issues, so one ascending page is where they are not).
        # Refuse an explicit page request rather than ignoring it: returning the
        # whole set to someone who asked for page 2 is a confident wrong answer,
        # and only this layer can tell a passed value from a default.
        if "per-page" in flags or "page" in flags:
            return core.error(
                "validation",
                "--untriaged scans every page, so --per-page/--page do not apply "
                "— re-run without them to get the whole untriaged set",
            )
    per_page, err = _int_flag(flags, "per-page", 100)
    if err:
        return core.error("validation", err)
    page, err = _int_flag(flags, "page", 1)
    if err:
        return core.error("validation", err)
    transport = _resolve_transport(transport)
    return query.list_items(
        transport,
        owner=owner,
        repo=repo,
        filters=filters,
        sort=flags.get("sort", "created"),
        direction=flags.get("direction", "asc"),
        per_page=per_page,
        page=page,
    )


def _run_pick(rest: list[str], transport):
    flags, _positionals, err = _parse_flags(
        rest, valued={"repo", "limit", "claim-ttl"}, boolean={"claim"}
    )
    if err:
        return core.error("validation", err)
    parsed = ids.parse_repo(flags.get("repo", ""))
    if parsed is None:
        return core.error("validation", "pick requires --repo owner/repo")
    owner, repo = parsed
    limit, err = _int_flag(flags, "limit", 1)
    if err:
        return core.error("validation", err)
    ttl, err = _int_flag(flags, "claim-ttl", core.DEFAULT_CLAIM_TTL_SECONDS)
    if err:
        return core.error("validation", err)
    transport = _resolve_transport(transport)
    return query.pick(
        transport,
        owner=owner,
        repo=repo,
        limit=limit,
        claim="claim" in flags,
        claim_ttl_seconds=ttl,
        default_owner=owner,
    )


def _run_counts(rest: list[str], transport):
    flags, _positionals, err = _parse_flags(rest, valued={"repo"})
    if err:
        return core.error("validation", err)
    parsed = ids.parse_repo(flags.get("repo", ""))
    if parsed is None:
        return core.error("validation", "counts requires --repo owner/repo")
    owner, repo = parsed
    transport = _resolve_transport(transport)
    return query.counts(transport, owner=owner, repo=repo)


def _run_verify_migration(rest: list[str], transport):
    from . import migrate  # noqa: PLC0415 — lazy: migration ops only

    flags, _positionals, err = _parse_flags(
        rest, valued={"repo", "from", "archive", "archive-scope"}
    )
    if err:
        return core.error("validation", err)
    parsed = ids.parse_repo(flags.get("repo", ""))
    if parsed is None:
        return core.error("validation", "verify-migration requires --repo owner/repo")
    if "from" not in flags:
        return core.error("validation", "verify-migration requires --from <backlog.md path>")
    archive_scope, err = _archive_scope_flag(flags)
    if err:
        return core.error("validation", err)
    owner, repo = parsed
    content, err = _read_source(flags["from"], "--from")
    if err:
        return core.error("validation", err)
    archive_content = None
    if "archive" in flags:
        archive_content, err = _read_source(flags["archive"], "--archive")
        if err:
            return core.error("validation", err)
    transport = _resolve_transport(transport)
    return migrate.verify_migration(
        transport,
        owner=owner,
        repo=repo,
        content=content,
        archive_content=archive_content,
        archive_scope=archive_scope,
    )


def _run_refresh_counts(rest: list[str], transport, project_dir):
    flags, _positionals, err = _parse_flags(rest, valued={"repo"})
    if err:
        return core.error("validation", err)
    parsed = ids.parse_repo(flags.get("repo", ""))
    if parsed is None:
        return core.error("validation", "refresh-counts requires --repo owner/repo")
    owner, repo = parsed
    transport = _resolve_transport(transport)
    from pathlib import Path  # noqa: PLC0415 — only this op needs a path

    return query.refresh_counts(
        transport, project_dir=Path(project_dir), owner=owner, repo=repo
    )


def _run_reconcile_labels(rest: list[str], transport):
    flags, _positionals, err = _parse_flags(rest, valued={"repo"})
    if err:
        return core.error("validation", err)
    parsed = ids.parse_repo(flags.get("repo", ""))
    if parsed is None:
        return core.error("validation", "reconcile-labels requires --repo owner/repo")
    owner, repo = parsed
    transport = _resolve_transport(transport)
    return core.reconcile_labels(transport, owner=owner, repo=repo)


def _run_claim(rest: list[str], transport):
    flags, positionals, err = _parse_flags(rest, valued={"repo", "claim-ttl"})
    if err:
        return core.error("validation", err)
    if not positionals:
        return core.error("validation", "claim requires an <id>")
    default_owner, default_repo, err = _repo_defaults(flags)
    if err:
        return core.error("validation", err)
    ttl, err = _int_flag(flags, "claim-ttl", core.DEFAULT_CLAIM_TTL_SECONDS)
    if err:
        return core.error("validation", err)
    transport = _resolve_transport(transport)
    return core.claim(
        transport,
        id_raw=positionals[0],
        default_owner=default_owner,
        default_repo=default_repo,
        claim_ttl_seconds=ttl,
    )


def _run_unclaim(rest: list[str], transport):
    flags, positionals, err = _parse_flags(rest, valued={"repo"})
    if err:
        return core.error("validation", err)
    if not positionals:
        return core.error("validation", "unclaim requires an <id>")
    default_owner, default_repo, err = _repo_defaults(flags)
    if err:
        return core.error("validation", err)
    transport = _resolve_transport(transport)
    return core.unclaim(
        transport,
        id_raw=positionals[0],
        default_owner=default_owner,
        default_repo=default_repo,
    )


def _run_link(op: str, rest: list[str], transport):
    flags, positionals, err = _parse_flags(rest, valued={"repo", "edge", "to"})
    if err:
        return core.error("validation", err)
    if not positionals:
        return core.error("validation", f"{op} requires an <id>")
    edge = flags.get("edge")
    if not edge:
        return core.error(
            "validation",
            f"{op} requires --edge (blocks|blocked-by|parent|child|related)",
        )
    target = flags.get("to")
    if not target:
        return core.error("validation", f"{op} requires --to <target-id>")
    default_owner, default_repo, err = _repo_defaults(flags)
    if err:
        return core.error("validation", err)
    transport = _resolve_transport(transport)
    fn = core.link if op == "link" else core.unlink
    return fn(
        transport,
        id_raw=positionals[0],
        edge=edge,
        target_raw=target,
        default_owner=default_owner,
        default_repo=default_repo,
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


def _run_import(rest: list[str], transport, project_dir):
    from pathlib import Path  # noqa: PLC0415 — only migration ops need a path

    from . import migrate  # noqa: PLC0415 — lazy: no migration import cost on other paths

    from . import restructure  # noqa: PLC0415 — lazy, migration ops only

    flags, _positionals, err = _parse_flags(
        rest, valued={"repo", "from", "archive", "restructure", "archive-scope"}
    )
    if err:
        return core.error("validation", err)
    parsed = ids.parse_repo(flags.get("repo", ""))
    if parsed is None:
        return core.error("validation", "import requires --repo owner/repo")
    if "from" not in flags:
        return core.error("validation", "import requires --from <backlog.md path>")
    archive_scope, err = _archive_scope_flag(flags)
    if err:
        return core.error("validation", err)
    owner, repo = parsed
    content, err = _read_source(flags["from"], "--from")
    if err:
        return core.error("validation", err)
    archive_content = None
    if "archive" in flags:
        archive_content, err = _read_source(flags["archive"], "--archive")
        if err:
            return core.error("validation", err)
    plan = None
    plan_text = None
    if "restructure" in flags:
        plan_text, err = _read_source(flags["restructure"], "--restructure")
        if err:
            return core.error("validation", err)
        plan, err = restructure.parse_plan(plan_text)
        if err:
            return core.error("validation", err)
    transport = _resolve_transport(transport)
    checkpoint = migrate.Checkpoint(
        migrate.checkpoint_path(Path(project_dir)),
        f"{owner}/{repo}",
        migrate.run_key(content, archive_content, plan_text),
    )
    return migrate.import_backlog(
        transport,
        owner=owner,
        repo=repo,
        content=content,
        archive_content=archive_content,
        plan=plan,
        archive_scope=archive_scope,
        checkpoint=checkpoint,
    )


def _run_restructure_preview(rest: list[str]):
    """The MG6 owner-review artifact — offline (no transport, nothing written to
    GitHub): parse the source(s) exactly as `import` would, apply the plan, and
    write the deterministic before/after preview the owner approves in aggregate."""
    from pathlib import Path  # noqa: PLC0415 — only migration ops need a path

    from . import migrate, restructure  # noqa: PLC0415 — lazy

    flags, _positionals, err = _parse_flags(
        rest, valued={"from", "archive", "plan", "out", "archive-scope"}
    )
    if err:
        return core.error("validation", err)
    for required in ("from", "plan", "out"):
        if required not in flags:
            return core.error(
                "validation", f"restructure-preview requires --{required}"
            )
    archive_scope, err = _archive_scope_flag(flags)
    if err:
        return core.error("validation", err)
    content, err = _read_source(flags["from"], "--from")
    if err:
        return core.error("validation", err)
    archive_content = None
    if "archive" in flags:
        archive_content, err = _read_source(flags["archive"], "--archive")
        if err:
            return core.error("validation", err)
    plan_text, err = _read_source(flags["plan"], "--plan")
    if err:
        return core.error("validation", err)
    plan, err = restructure.parse_plan(plan_text)
    if err:
        return core.error("validation", err)
    records, collisions = migrate.collect_records(content, archive_content)
    records, archive_skipped = migrate.apply_archive_scope(records, archive_scope)
    applied = restructure.apply(records, plan)
    if not applied["ok"]:
        return core.error("validation", applied["error"])
    source_label = flags["from"] + (f" + {flags['archive']}" if "archive" in flags else "")
    preview = restructure.render_preview(
        applied, source_label=source_label, collisions=collisions
    )
    out_path = Path(flags["out"])
    try:
        out_path.write_text(preview, encoding="utf-8")
    except OSError as exc:
        # "unavailable", matching export's local-write failure class — an
        # environment failure, not bad input.
        return core.error(
            "unavailable", f"could not write --out {flags['out']}: {type(exc).__name__}"
        )
    entries = applied["entries"]
    data = {
        "preview": str(out_path),
        "plan_entries": len(entries),
        "titles_rewritten": sum(1 for e in entries if e["title_changed"]),
        "bodies_restructured": sum(1 for e in entries if e["body_changed"]),
        "kinds_assigned": sum(1 for e in entries if e["kind_assigned"]),
        "non_atomic_flagged": sum(1 for e in entries if e["non_atomic"]),
        "lint_findings": sum(len(e["lint"]) for e in entries),
        "collisions": len(collisions),
        "archive_skipped": archive_skipped,
        "total_source": len(records),  # records entering the import (post archive-scope filter)
    }
    warnings = applied["warnings"]
    if archive_skipped:
        # Surface the dropped count in human mode too (not JSON-only) so an owner
        # previewing "exactly what imports" sees what --archive-scope excluded — the
        # excluded items stay in the git-tracked source markdown, never lost, but
        # they do not enter the migrated tracker (see migrate.apply_archive_scope).
        warnings = [
            f"--archive-scope open: {archive_skipped} closed/archived item(s) excluded from "
            "this preview (they remain in the git-tracked source markdown; this preview "
            "matches what an import run with the SAME --archive-scope would write — note "
            "both commands default to all, so a bare import would not match this)"
        ] + warnings
    return core.ok(data, warnings)


def _run_export(rest: list[str], transport):
    from pathlib import Path  # noqa: PLC0415 — only migration ops need a path

    from . import migrate  # noqa: PLC0415 — lazy

    flags, _positionals, err = _parse_flags(rest, valued={"repo", "to"})
    if err:
        return core.error("validation", err)
    parsed = ids.parse_repo(flags.get("repo", ""))
    if parsed is None:
        return core.error("validation", "export requires --repo owner/repo")
    if "to" not in flags:
        return core.error("validation", "export requires --to <dir>")
    owner, repo = parsed
    transport = _resolve_transport(transport)
    return migrate.export_backlog(transport, owner=owner, repo=repo, dest=Path(flags["to"]))


def _run_merge(rest: list[str], transport):
    from . import migrate  # noqa: PLC0415 — lazy

    flags, positionals, err = _parse_flags(rest, valued={"repo", "into"})
    if err:
        return core.error("validation", err)
    if not positionals:
        return core.error("validation", "merge requires a <source-id>")
    target = flags.get("into")
    if not target:
        return core.error("validation", "merge requires --into <target-id>")
    default_owner, default_repo, err = _repo_defaults(flags)
    if err:
        return core.error("validation", err)
    transport = _resolve_transport(transport)
    return migrate.merge(
        transport,
        source_raw=positionals[0],
        target_raw=target,
        default_owner=default_owner,
        default_repo=default_repo,
    )


def _read_source(path_str: str, flag: str) -> tuple[str | None, str | None]:
    """Read a migration input file; returns ``(content, error)``. A read failure is
    a ``validation`` error (the caller passed a bad path) — never a raised exception."""
    from pathlib import Path  # noqa: PLC0415

    try:
        return Path(path_str).read_text(), None
    except OSError as exc:
        return None, f"cannot read {flag} {path_str!r}: {type(exc).__name__}"


# --- plumbing ----------------------------------------------------------------


def _is_write(op: str, rest: list[str]) -> bool:
    """Whether ``op`` performs a GitHub mutation (subject to the SEC-5 withhold).
    ``pick`` mutates only with ``--claim``; everything else is fixed by op name."""
    if op in _WRITE_OPS:
        return True
    return op == "pick" and "--claim" in rest


def _resolve_transport(transport):
    if transport is not None:
        return transport
    from .transport import GhTransport  # lazy — no gh import cost on other paths

    return GhTransport()


def _repo_defaults(
    flags: dict,
) -> tuple[str | None, tuple[str, str] | None, str | None]:
    """Resolve the ``--repo`` defaults a single-id op needs: the same-owner default
    (for short ``repo#N`` ids) **and** the ``(owner, repo)`` a bare hand-minted
    ``PFX`` alias resolves against (MG1 — a migrated item's original id stays a valid
    ref forever, across every id-taking command).

    Returns ``(default_owner, default_repo, error)``; a present-but-malformed
    ``--repo`` is an error string, an absent one is ``(None, None, None)``.
    """
    repo = flags.get("repo")
    if not repo:
        return None, None, None
    parsed = ids.parse_repo(repo)
    if parsed is None:
        return None, None, "--repo must be owner/repo"
    return parsed[0], parsed, None


def _parse_flags(tokens: list[str], *, valued: set[str], boolean: set[str] | None = None):
    """Parse ``--key value`` / ``--key=value`` / ``--flag`` tokens and positionals.

    Returns ``(flags, positionals, error_message)``. ``valued`` names flags that
    take a value; ``boolean`` names presence-only flags (stored as ``"true"``). An
    unknown flag, a missing value, or a value given to a boolean flag is an error.
    """
    boolean = boolean or set()
    flags: dict[str, str] = {}
    positionals: list[str] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--"):
            key, sep, value = token[2:].partition("=")
            if key in boolean:
                if sep:
                    return {}, [], f"--{key} takes no value"
                flags[key] = "true"
            elif key in valued:
                if sep:
                    flags[key] = value
                elif i + 1 < len(tokens):
                    flags[key] = tokens[i + 1]
                    i += 1
                else:
                    return {}, [], f"--{key} requires a value"
            else:
                return {}, [], f"unknown flag: {token}"
        else:
            positionals.append(token)
        i += 1
    return flags, positionals, None


def _int_flag(flags: dict, key: str, default: int) -> tuple[int, str | None]:
    """Parse an integer flag; returns ``(value, error_or_None)``."""
    if key not in flags:
        return default, None
    try:
        return int(flags[key]), None
    except (TypeError, ValueError):
        return default, f"--{key} must be an integer, got {flags[key]!r}"


def _archive_scope_flag(flags: dict) -> tuple[str, str | None]:
    """Resolve + validate the shared ``--archive-scope`` selector (MG4b), the one
    lever `import` and `restructure-preview` both accept. Returns ``(scope,
    error_or_None)``; defaults to ``all``. Single source of the valid set and the
    error message so the two callers cannot drift."""
    from . import migrate  # noqa: PLC0415 — lazy, migration ops only

    scope = flags.get("archive-scope", "all")
    if scope not in migrate.ARCHIVE_SCOPES:
        return scope, f"--archive-scope must be one of {'|'.join(migrate.ARCHIVE_SCOPES)}"
    return scope, None


_DETAIL_LIST_CAP = 20


def _render_detail_list(value: list) -> str:
    """Render one error-detail list for human mode.

    Two shapes arrive here and they need opposite treatment.

    A list of **entry dicts** — an interrupted import's `created`/`skipped` —
    is bookkeeping whose only useful summary is how many; printing them buries
    the error message under hundreds of lines just as the operator is deciding
    whether to resume. `status_unreconciled` renders as a count here for the
    same reason, and is the one dict-list that is *not* merely bookkeeping — so
    it is not left to this count alone: each deferral also emits a per-item
    warning naming the issue, printed on this path directly below the details.

    A list of **plain strings is the payload itself.** The completeness gate's
    `missing`, `unaliasable`, `collisions`, `status_mismatch` and
    `duplicate_alias` name the items that stranded the run, and the documented
    remedy for each is unactionable without them —
    "give each a real prefix in the source before importing" cannot be followed
    against the number 3. Counting those turns a verdict into a figure nobody
    can act on, and the runbook drives this path without ``--json``, so the
    named form has no other route to the operator.

    Long lists are capped so one bad run still cannot bury the message.
    """
    if not value or not all(isinstance(item, str) for item in value):
        return str(len(value))
    if len(value) <= _DETAIL_LIST_CAP:
        return ", ".join(value)
    head = ", ".join(value[:_DETAIL_LIST_CAP])
    return f"{head}, … (+{len(value) - _DETAIL_LIST_CAP} more)"


def _pacing_line(pacing: dict) -> str:
    """The pacing footer, shared by the success path and the resumable-cut path.

    ``≥`` is not decoration. The meter charges per transport METHOD call, not per
    HTTP request, so a paged read (up to 100 requests) is charged once and
    per-item label reads are undercounted (BKL-3H7W). The number is a **floor**.
    Printing it bare puts a figure that reads exact in front of the one person
    sizing an irreversible run — drop the ``≥`` only when BKL-3H7W makes it true.

    Shared rather than duplicated because the cut path needs this MORE than the
    success path, not less: a run that stopped is exactly where the budget
    question gets asked, and a second construction is where the ``≥`` goes
    missing.
    """
    throttled = (
        pacing.get("rest_point_waits", 0)
        + pacing.get("content_creation_waits", 0)
        + pacing.get("rate_limit_pauses", 0)
    )
    summary = f"≥{pacing.get('rest_points_charged', 0)} REST points"
    if throttled:
        waited = (
            pacing.get("rest_point_wait_seconds", 0.0)
            + pacing.get("content_creation_wait_seconds", 0.0)
            + pacing.get("rate_limit_paused_seconds", 0.0)
        )
        summary += (
            f"; THROTTLED {throttled}× for {waited:.0f}s total "
            f"({pacing.get('rest_point_waits', 0)} rest-point, "
            f"{pacing.get('content_creation_waits', 0)} content-cap, "
            f"{pacing.get('rate_limit_pauses', 0)} rate-limit)"
        )
    else:
        summary += "; no throttling (budgets never bound)"
    return summary


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
        # Standard lint findings (WARN-only, `file`): advisory, never affect the
        # exit code, and kept distinct from operational warnings.
        for finding in result.get("lint", []):
            print(f"lint: {finding.get('message')}", file=sys.stderr)
    else:
        err = result.get("error", {})
        print(f"error [{err.get('code')}]: {err.get('message')}", file=sys.stderr)
        # A cut mid-import already KNOWS how far it got — the envelope carries
        # `created`/`skipped`/`collisions`/`resumable`/`pacing` — and human mode
        # dropped all of it, so the operator of an irreversible ~900-issue
        # migration learned only that it broke. The scrub runbook drives this
        # path without `--json`, so this is the surface that matters.
        for key, value in (err.get("details") or {}).items():
            if key == "pacing" and isinstance(value, dict):
                shown = _pacing_line(value)
            elif isinstance(value, list):
                shown = _render_detail_list(value)
            else:
                shown = value
            print(f"  {key}: {shown}", file=sys.stderr)
        # A resumable error envelope (e.g. import) carries the audit warnings accrued
        # before the cut; surface them like the ok path so they reach the operator.
        for warning in result.get("warnings", []):
            print(f"warning: {warning}", file=sys.stderr)
        if usage:
            print(_HELP, file=sys.stderr)
    return exit_code


def _print_human_ok(data) -> None:
    if not isinstance(data, dict):
        print(json.dumps(data))
        return
    if "edge" in data and "target" in data:
        # A link/unlink result.
        verb = "linked" if data.get("linked") else "unlinked"
        print(f"{verb} {data.get('item')} --{data.get('edge')}--> {data.get('target')}")
    elif "preview" in data:
        # A restructure-preview result (checked before `total_source`, which it
        # also carries — an unmatched new result type must not shadow into the
        # import line).
        print(
            f"wrote restructure preview to {data.get('preview')}: "
            f"{data.get('plan_entries')} plan entr(ies) over "
            f"{data.get('total_source')} source item(s) — "
            f"{data.get('titles_rewritten')} title(s), "
            f"{data.get('bodies_restructured')} bod(ies), "
            f"{data.get('kinds_assigned')} kind(s); "
            f"{data.get('non_atomic_flagged')} flagged non-atomic, "
            f"{data.get('lint_findings')} lint finding(s), "
            f"{data.get('collisions')} collision(s)"
        )
    elif "total_source" in data:
        # An import result (checked before `items`: an export result also carries an
        # `items` key, so the migration results are matched first on their own keys).
        line = (
            f"{data.get('repo')}: imported {len(data.get('created', []))} created, "
            f"{len(data.get('skipped', []))} skipped, "
            f"{len(data.get('collisions', []))} collision(s) of "
            f"{data.get('total_source')} source item(s)"
        )
        if "restructured" in data:
            line += f" ({data['restructured']} restructured by plan)"
        print(line)
        # An item can be created and still not migrated: a failed status reconcile
        # defers so the run continues, leaving the issue on the target at the wrong
        # status. That is invisible in the counts above — a deferred item is in
        # `created` — so it gets its own line rather than only a stderr warning, for
        # the same reason as the pacing footer below: this path runs without --json.
        unreconciled = data.get("status_unreconciled") or []
        if unreconciled:
            print(
                f"  WARNING: {len(unreconciled)} item(s) imported but NOT reconciled "
                "to their target status — re-run the import, then verify-migration"
            )
        # The pacing footer is the operator's after-the-fact answer to "was this run
        # throttled, and where did the budget stand?" — printed in HUMAN mode because
        # that is how `migration-scrub.md` actually invokes import (no --json), so a
        # JSON-only summary would reach every consumer except the one person running
        # the irreversible migration (BKL-8K2N).
        pacing = data.get("pacing")
        if pacing:
            print(f"  pacing: {_pacing_line(pacing)}")
    elif "dir" in data and "count" in data:
        # An export result (its `items` is a list of id strings, not item dicts).
        print(f"{data.get('repo')}: exported {data.get('count')} item(s) to {data.get('dir')}")
    elif "merged" in data:
        # A merge result.
        print(f"merged {data.get('source')} --superseded-by--> {data.get('target')}")
    elif "candidates" in data:
        # A pick result — ranked ready-work.
        candidates = data.get("candidates", [])
        if not candidates:
            print("no ready work")
        for cand in candidates:
            _print_item_line(cand)
            if cand.get("why"):
                print(f"    {cand['why']}")
        print(f"  {data.get('count', len(candidates))} candidate(s)")
    elif "items" in data:
        # A list result.
        for item in data.get("items", []):
            _print_item_line(item)
        print(f"  {data.get('count', 0)} item(s)")
    elif "by_status" in data:
        # A counts / refresh-counts result.
        print(f"{data.get('repo')}: {data.get('total')} item(s)")
        print("  status: " + ", ".join(f"{k}={v}" for k, v in data.get("by_status", {}).items()))
        print("  stage:  " + ", ".join(f"{k}={v}" for k, v in data.get("by_stage", {}).items()))
        # Surfaced by exception, and only when there are any: an untriaged item
        # is one nobody has looked at, so it has to be louder than a triaged
        # one, and it must come with the command that shows it — a bare number
        # nobody can act on is how these accumulate.
        if data.get("untriaged"):
            print(
                f"  untriaged: {data['untriaged']} issue(s) carry no prawduct "
                "labels or block — filed by hand or by another product, and "
                "nothing has triaged them yet"
            )
            # The full binary name, not a bare `backlog …`: an operator copies
            # this line, and `backlog` alone is not a command.
            print(
                f"    see them: prawduct-hook backlog list --repo {data.get('repo')} --untriaged"
            )
        if "persisted" in data:  # refresh-counts adds the snapshot outcome
            if data.get("persisted"):
                print(f"  snapshot written ({data.get('fetched_at')})")
            else:
                print("  snapshot NOT persisted (see warnings)")
    elif "item" in data and "url" in data:
        # A comment result (distinct from an item — no status/stage axes).
        print(f"commented on {data.get('item')} by {data.get('actor')}")
        if data.get("url"):
            print(f"  {data['url']}")
    elif "id" in data:
        _print_item_line(data)
        bits = [f"status={data.get('status')}"]
        if data.get("stage"):
            bits.append(f"stage={data['stage']}")
        if data.get("assignee"):
            bits.append(f"assignee={data['assignee']}")
        print("  " + "  ".join(bits))
        if data.get("superseded_by"):
            # A merged-away item: the human reader needs the breadcrumb to the
            # survivor, not just "closed as dropped" (BKL-5R2K).
            line = f"  superseded_by → {data['superseded_by']}"
            if data.get("resolves_to"):
                line += f"  (survivor: {data['resolves_to']})"
            print(line)
        # The comment thread (only `get` attaches it — the DM5 drill-down).
        # A failed fetch leaves it empty with the payload count intact; the
        # warning on stderr says why, so nothing extra is rendered here.
        comments = data.get("comments") or []
        if comments:
            print(f"  {len(comments)} comment(s):")
            for comment in comments:
                stamp = " · ".join(
                    bit for bit in (comment.get("author"), comment.get("created_at")) if bit
                )
                print(f"  — {stamp}" if stamp else "  —")
                for line in (comment.get("body") or "").splitlines():
                    print(f"    {line}")
    elif "created" in data:
        # provision / reconcile-labels.
        line = (
            f"{data.get('repo')}: {len(data.get('created', []))} label(s) created, "
            f"{len(data.get('existing', []))} already present"
        )
        if "foreign_untouched" in data:  # reconcile-labels reports coexistence
            line += f", {len(data.get('foreign_untouched', []))} foreign untouched"
        print(line)
    else:
        print(json.dumps(data))


def _print_item_line(item: dict) -> None:
    """One-line item summary: ``<id>  <title>`` (used by get/list/pick)."""
    line = item.get("id") or ""
    if item.get("title"):
        line = f"{line}  {item['title']}"
    print(line)


def _exit_code(result: dict) -> int:
    if result.get("status") == "ok":
        return 0
    code = result.get("error", {}).get("code", "")
    return _EXIT_CLASS.get(code, 1)
