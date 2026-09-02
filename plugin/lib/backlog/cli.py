"""CLI — the ``prawduct-hook backlog <op>`` runner (the surface callers bind to).

A **thin** front over ``core`` (Test Specs §1.1): it parses flags, calls the core
op, serializes the envelope, and maps the error code to a stable exit class. All
the logic lives in ``core``; this layer adds only the CLI surface.

**This is the boundary, and it is an internal one.** Every skill and gate reaches
the backlog through here — nothing outside this package calls ``core`` — so what
is documented below (the op set, the flags, the envelope, the exit classes) is
binding *behaviour*, and a caller at the version it shipped with may rely on all
of it. What is **not** offered is a stability tier for a third party: this CLI is
delivered by the plugin that installs it and carried at the plugin's own version
alongside the skills that call it, so it evolves additive-first with them rather
than under a separate compatibility promise. Prawduct's externally bindable
surface is a short enumeration of read-only subcommands and ``backlog`` is
deliberately not in it — binding to it from outside the plugin is unsupported
rather than merely undocumented.

Output discipline (AG6, API §3/§8):
- ``--json`` → the JSON envelope is the **sole stdout content**; a ``| jq`` never
  chokes. ``warnings[]`` rides inside that envelope (still valid JSON).
- default (human) → a readable summary to stdout, narration/warnings to stderr.

Non-interactive always (INV-2): the runner never prompts and never reads stdin.

Self-describing (AG6): ``<op> --help`` prints that op's usage on **stdout** at
**exit 0**, and a bare ``--help`` prints the whole usage table — the op set an
instruction surface bounds its reader to. Help is a request that succeeded, so
it is never a validation error.

Exit codes are a small fixed set of classes (a build-time coherence check, API
§11) so scripts can branch without parsing the body:
``0 ok · 2 validation · 3 not-found · 4 conflict · 5 auth · 6 unavailable``.
"""

from __future__ import annotations

import json
import sys

from . import context, core, ids, query

# GitHub-mutating ops — refused under an untrusted-triggered Actions run absent an
# explicit triggering-actor authorization check (SEC-5). Reads, ``counts``,
# ``refresh-counts`` and ``sync`` (reads plus a local write) are never withheld —
# read-only reporting under such triggers is fine (Security §1b). ``pick`` is a
# read on every path now that it takes nothing: it revalidates the local store and
# ranks, and mutates nothing on the provider.
_WRITE_OPS: frozenset[str] = frozenset(
    {"file", "status", "update", "comment",
     "link", "unlink", "provision", "reconcile-labels", "import", "merge"}
)

#: Every op :func:`run` dispatches, in dispatch order. It builds the unknown-op
#: message below, so it cannot go stale while that message is correct — and it
#: is what lets a test outside this module enumerate the op surface instead of
#: re-typing it. ``prawduct-hook``'s ephemeral-worktree guard classifies this
#: exact surface into read-only / writes-locally / service-only, and nothing but
#: a partition test keeps the two in step: an op added here and missed in the
#: guard's local-write set is ALLOWED on a service-backed repo (the
#: service-backed early return fires before the per-op set), which is precisely
#: the stranded write that guard exists to refuse. Adding an op therefore has to
#: fail something until it is classified.
_ALL_OPS: tuple[str, ...] = ()  # bound below, once the usage table exists

# code → exit class. A code absent here (should not happen) falls back to 1.
_EXIT_CLASS: dict[str, int] = {
    "validation": 2,
    "ambiguous_id": 2,
    "alias_collision": 2,
    "unsupported": 2,
    "not_found": 3,
    # 4 is `conflict`, and `update`'s optimistic-CAS path is what produces it. A
    # `claim_conflict` value produced it too until the claim op was retired; the
    # CODE keeps its meaning, which is what the additive-first contract protects —
    # retiring one producer of a code is not repurposing the code.
    "conflict": 4,
    "auth": 5,
    "unavailable": 6,
    "rate_limited": 6,
}

#: Per-op usage, keyed by the op name — **the usage table**. It is the referent
#: every instruction surface points at when it bounds a caller to "the ops the
#: adapter exposes": `backlog --help` renders the whole table, `backlog <op>
#: --help` renders one entry, both on stdout at exit 0. Composed into `_HELP`
#: below rather than duplicated, so an op cannot be documented in one view and
#: missing from the other, and dict order is display order.
_OP_USAGE: dict[str, str] = {
    "file": (
        "  file     --repo owner/repo --title T --body B "
        "[--stage S] [--kind K] [--area A] [--effort E] [--impact I] [--source SRC]\n"
    ),
    "get": "  get      <id> [--repo owner/repo]   (`show` is an alias)\n",
    "status": (
        "  status   <id> --to submitted|open|in-progress|shipped|dropped [--repo owner/repo]\n"
        "           takes no `--closed-by`: a close records no scope handle\n"
    ),
    "update": (
        "  update   <id> [--title T] [--body B] [--stage S] [--kind K] [--area A] "
        "[--effort E] [--impact I] [--source SRC] [--tags a,b] [--affected p1,p2] "
        "[--working-branch owner/repo@branch] [--if-updated-at TS] [--repo owner/repo]\n"
        "           --tags sets the WHOLE tag set (absent ones are stripped; --tags '' clears)\n"
        "           --affected takes repo-relative paths only, no prose (a directory "
        "covers everything under it)\n"
        "           --working-branch must name a PUSHED branch, repo-qualified\n"
    ),
    "comment": "  comment  <id> --body B [--repo owner/repo]\n",
    "list": (
        "  list     --repo owner/repo [--status S] [--stage S] [--kind K] [--area A] "
        "[--effort E] [--impact I] [--source SRC] [--tag T] [--assignee A|none|*] "
        "[--state open|closed|all] [--sort created|updated] [--direction asc|desc] "
        "[--per-page N] [--page N] [--untriaged]\n"
        "           --untriaged inverts the scope filter: shows only issues with no "
        "prawduct labels or block\n"
    ),
    "pick": (
        "  pick     --repo owner/repo [--limit N] [--include-working]\n"
        "           ready work, ranked; items naming a `working-branch` are excluded "
        "unless --include-working\n"
    ),
    "counts": "  counts   --repo owner/repo\n",
    "refresh-counts": (
        "  refresh-counts   --repo owner/repo   (derive + persist the briefing snapshot)\n"
    ),
    "sync": (
        "  sync     --repo owner/repo [--rebuild]   (populate the local cache; "
        "incremental unless --rebuild)\n"
    ),
    "cache-query": (
        "  cache-query <query> [args] --repo owner/repo   (read the local cache; "
        "never touches the network)\n"
        "           open | unstaged | by-area [--all] | stale [--older-than N] |\n"
        "           search <text> [--area A] | affecting <path>... [--all] |\n"
        "           created-since <ISO> | resolve <id>\n"
        "           exit 6 means the cache could not be read — NOT that nothing matched\n"
    ),
    "link": (
        "  link     <id> --edge blocks|blocked-by|parent|child|related "
        "--to <target-id> [--repo owner/repo]\n"
    ),
    "unlink": (
        "  unlink   <id> --edge blocks|blocked-by|parent|child|related "
        "--to <target-id> [--repo owner/repo]\n"
    ),
    "provision": "  provision --repo owner/repo\n",
    # GV6. The id stays here, out of the operator's way: text emitted into a
    # governed product carries the reason, never a prawduct-internal label.
    "reconcile-labels": (
        "  reconcile-labels --repo owner/repo   "
        "(add missing taxonomy labels; never removes or edits existing ones)\n"
    ),
    "import": (
        "  import   --repo owner/repo --from <backlog.md> [--archive <archive.md>] "
        "[--restructure <plan.json>] [--archive-scope all|open]   "
        # MG6 — see the note on reconcile-labels above.
        "(resumable/idempotent; a --restructure plan is applied as each issue "
        "is created, not as a later edit)\n"
        "           retries a rate-limited record in-run, bounded; every other "
        "failure ends the run resumably\n"
    ),
    "restructure-preview": (
        "  restructure-preview --from <backlog.md> [--archive <archive.md>] "
        "--plan <plan.json> --out <preview.md> [--archive-scope all|open]   "
        "(offline before/after review artifact)\n"
    ),
    "verify-migration": (
        "  verify-migration --repo owner/repo --from <backlog.md> [--archive <archive.md>] "
        "[--archive-scope all|open]   (completeness gate — exit 4 names any source item with "
        "no issue on the target, and any whose id is not a valid PFX so no alias can key it; "
        "run before recording the cutover)\n"
    ),
    "export": (
        "  export   --repo owner/repo --to <dir>   (full-fidelity dump incl. native graph)\n"
    ),
    "merge": (
        "  merge    <source-id> --into <target-id> [--repo owner/repo]   "
        "(fold A→B, redirect-before-close)\n"
    ),
}

#: Ops that share another op's handler and therefore its usage entry. Keeping
#: them out of `_OP_USAGE` keeps the rendered table one row per operation while
#: `--help` still answers for the spelling the caller actually typed.
_OP_ALIASES: dict[str, str] = {"show": "get"}

#: One enumeration, not two. `_ALL_OPS` used to be a hand-kept tuple beside the
#: usage table, and the pins all iterated it — so an op wired into `run` alone was
#: dispatchable, absent from `--help`, and invisible to every check, while this
#: file's own contract promises callers that the published op set is what
#: dispatches. Deriving it from the table that `--help` prints makes the promise
#: structural in one direction; `test_every_dispatched_op_is_in_the_op_set` closes
#: the other, reading the dispatch chain itself.
_ALL_OPS = tuple(_OP_USAGE) + tuple(_OP_ALIASES)

_GLOBAL_HELP = "global: --json  (machine envelope on stdout; default is human)\n"

#: The **caller-side** retry budget. No adapter code enforces it — a single op
#: makes one `gh` call and returns, so a retry only ever exists in the caller —
#: which is exactly why it has to be published rather than assumed: an
#: unbounded caller loop is the opposite of the never-block guarantee. Three
#: attempts cost at most 3 x the 30s `gh` timeout plus the two pauses, so the
#: deadline binds only when calls run long; a healthy op answers in ~2s.
RETRY_MAX_ATTEMPTS = 3
RETRY_DEADLINE_SECONDS = 120

_RETRY_HELP = (
    "retrying: no op retries a failed call for you except `import`, which retries a\n"
    "  rate-limited record in-run. A caller re-attempting a `retryable` error spends\n"
    f"  at most {RETRY_MAX_ATTEMPTS} attempts and {RETRY_DEADLINE_SECONDS}s wall "
    "clock, then gives up and reports.\n"
)

_ISSUE_STANDARD_HELP = (
    "issue standard: `file` emits an `area:`-prefixed title and audits the issue.\n"
    "  The four §1 TITLE checks BLOCK on every write path — `file`, `update` (on a\n"
    "  title it is asked to write) and `import` (whole corpus, before the first\n"
    "  write); body/label `lint` findings stay advisory. Author a scannable\n"
    "  `area: summary` title (15-72) + a sectioned body (bug:\n"
    "  Problem/Repro/Actual/Expected/Evidence; task: Problem/Proposed\n"
    "  change/Acceptance `- [ ]`/Scope-out) and set --kind.\n"
    "  Full contract: documentation/backlog-service-issue-standard.md\n"
)

_HELP = (
    "usage: prawduct-hook backlog <op> [flags]\n"
    + "".join(_OP_USAGE.values())
    + _GLOBAL_HELP
    + "\n"
    + _RETRY_HELP
    + "\n"
    + _ISSUE_STANDARD_HELP
)


def _op_usage(op: str) -> str | None:
    """That op's usage entry, resolving an alias; ``None`` if it is not an op."""
    return _OP_USAGE.get(_OP_ALIASES.get(op, op))


def _help_text(op: str | None) -> str:
    """The whole usage table, or one op's entry when ``op`` names one."""
    entry = _op_usage(op) if op is not None else None
    if entry is None:
        return _HELP
    return (
        f"usage: prawduct-hook backlog {op} [flags]\n"
        + entry
        + _GLOBAL_HELP
        + "\n"
        + _RETRY_HELP
        + "\n"
        + "the whole op set: prawduct-hook backlog --help\n"
    )


def _emit_help(op: str | None, *, json_mode: bool) -> int:
    """Serve ``--help`` on **stdout** at exit 0.

    Help is a request that succeeded, so it is not a validation error and does
    not go to stderr: a reader discovering the op surface is the intended use,
    and an exit-2 "unknown flag" teaches the opposite. Under ``--json`` the
    usage rides inside the envelope, because the envelope is the sole stdout
    content (ERR-2) for every path that honors the flag.
    """
    text = _help_text(op)
    if json_mode:
        print(json.dumps(core.ok({"usage": text})))
    else:
        print(text)
    return 0


def _unknown_op(op: str, *, json_mode: bool) -> int:
    """The unknown-op envelope, whose message enumerates the whole op set."""
    return _emit(
        core.error(
            "validation",
            f"unknown op {op!r} (expected {'|'.join(_ALL_OPS)})",
        ),
        json_mode=json_mode,
        usage=True,
    )


#: Every flag name that takes a value anywhere in this CLI. Used ONLY to tell a
#: value slot from a flag position when scanning for a global flag — never to
#: validate, which stays each handler's own `_parse_flags(valued=...)` call.
#:
#: The union rather than a per-op map, deliberately: a per-op map is a second
#: enumeration of something the handlers already state, and it would drift the way
#: the op set did. The union is equivalent for every real invocation as long as no
#: name is valued for one op and boolean for another —
#: `test_no_flag_name_is_valued_here_and_boolean_there` is that condition, and
#: `test_the_valued_flag_union_matches_what_the_handlers_parse` reads the handlers
#: by AST so this set cannot fall behind them.
_VALUED_FLAG_NAMES: frozenset[str] = frozenset({
    "affected", "archive", "archive-scope", "area", "assignee", "body",
    "direction", "edge", "effort", "from", "if-updated-at", "impact", "into",
    "kind", "limit", "older-than", "out", "page", "per-page", "plan", "repo",
    "restructure", "sort", "source", "stage", "state", "status", "tag", "tags",
    "title", "to", "working-branch",
})


def _take_global_flag(argv: list[str], flag: str, named: str | None) -> tuple[bool, list[str]]:
    """Whether ``flag`` is present as a FLAG, and ``argv`` with those occurrences gone.

    A token that fills a valued flag's value slot belongs to that flag whatever it
    spells, so ``--body --help`` is a body of ``--help`` and not a help request.
    Membership alone cannot see that, which is how a write that never happened came
    back as a success envelope.
    """
    present = False
    out: list[str] = []
    skip_value = False
    for i, token in enumerate(argv):
        if i == 0 and named is not None:
            out.append(token)          # the op itself
            continue
        if skip_value:
            out.append(token)          # this token is someone's value
            skip_value = False
            continue
        if token == flag:
            present = True
            continue
        if token.startswith("--") and "=" not in token and token[2:] in _VALUED_FLAG_NAMES:
            skip_value = True
        out.append(token)
    return present, out


def resolve_op(argv: list[str]) -> str | None:
    """The op this call names, or ``None``.

    ``argv[0]`` or nothing. Resolving it as "the first token that does not look like
    a flag" reads a VALUED FLAG'S ARGUMENT as the op the moment one is present, and
    ``--repo <owner/repo>`` is in the invocation this adapter's own instruction
    surface teaches — which is how the habitual spelling of a help request came back
    ``unknown op 'owner/repo'``.
    """
    return argv[0] if argv and not argv[0].startswith("-") else None


def is_help_request(argv: list[str]) -> bool:
    """Whether this call asks for usage rather than doing anything.

    Public because more than one caller needs the answer and there must only be one:
    the ephemeral-worktree guard in ``bin/prawduct-hook`` decides whether to refuse a
    call before this module ever sees it, and a guard that re-spells the rule is a
    guard that can disagree with the runner about what the call *is*. A disagreement
    resolves the unsafe way — the guard waves through a write it has classified as a
    read.
    """
    return _take_global_flag(argv, "--help", resolve_op(argv))[0]


def run(project_dir, argv: list[str], *, transport=None) -> int:
    """Dispatch ``backlog <op> ...``; emit the envelope, return an exit code.

    ``argv`` is the tokens after ``backlog`` (``sys.argv[2:]``). ``transport`` is
    injected by tests (the L1 fake); in production it defaults to the real
    ``gh``-backed transport built lazily so no import cost lands on other paths.
    """
    named = resolve_op(argv)

    # `--json` and `--help` are global, but "global" is about which flag it is, not
    # about where the token sits: a token occupying a VALUE slot belongs to the flag
    # that claimed it, whatever it spells. Scanning by membership instead let
    # `comment <id> --body --help` print usage and report ok for a write that never
    # happened. `_VALUED_FLAG_NAMES` is what distinguishes a value slot from a flag,
    # and it is pinned against what each handler actually parses.
    json_mode, argv = _take_global_flag(argv, "--json", named)
    wants_help, argv = _take_global_flag(argv, "--help", named)

    # Help is answered before anything can turn it into an error: no op is
    # dispatched, no flag is parsed, and a write op under a withheld-writes trigger
    # still gets its usage (printing help is not writing). An unrecognized op still
    # gets the unknown-op envelope, so a typo is never dressed up as success.
    if wants_help:
        if named is None or _op_usage(named) is not None:
            return _emit_help(named, json_mode=json_mode)
        return _unknown_op(named, json_mode=json_mode)

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
            result = _run_file(rest, transport, project_dir)
        elif op in ("get", "show"):
            result = _run_get(rest, transport)
        elif op == "status":
            result = _run_status(rest, transport, project_dir)
        elif op == "update":
            result = _run_update(rest, transport, project_dir)
        elif op == "comment":
            result = _run_comment(rest, transport)
        elif op == "list":
            result = _run_list(rest, transport)
        elif op == "pick":
            result = _run_pick(rest, transport, project_dir)
        elif op == "counts":
            result = _run_counts(rest, transport)
        elif op == "verify-migration":
            result = _run_verify_migration(rest, transport)
        elif op == "refresh-counts":
            result = _run_refresh_counts(rest, transport, project_dir)
        elif op == "sync":
            result = _run_sync(rest, transport, project_dir)
        elif op == "cache-query":
            result = _run_cache_query(rest, project_dir)
        elif op == "reconcile-labels":
            result = _run_reconcile_labels(rest, transport)
        elif op in ("link", "unlink"):
            result = _run_link(op, rest, transport, project_dir)
        elif op == "provision":
            result = _run_provision(rest, transport)
        elif op == "import":
            result = _run_import(rest, transport, project_dir)
        elif op == "restructure-preview":
            result = _run_restructure_preview(rest)
        elif op == "export":
            result = _run_export(rest, transport)
        elif op == "merge":
            result = _run_merge(rest, transport, project_dir)
        else:
            return _unknown_op(op, json_mode=json_mode)
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


def _run_file(rest: list[str], transport, project_dir):
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
    return _with_mirror(
        project_dir,
        lambda absorb: core.file_item(
            transport,
            owner=owner,
            repo=repo,
            title=flags.get("title", ""),
            body=flags.get("body", ""),
            facets=facets,
            automated=automated,
            worker=context.worker_marker() if automated else None,
            absorb=absorb,
        ),
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


def _run_status(rest: list[str], transport, project_dir):
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
    return _with_mirror(
        project_dir,
        lambda absorb: core.set_status(
            transport,
            id_raw=positionals[0],
            target=target,
            default_owner=default_owner,
            default_repo=default_repo,
            absorb=absorb,
        ),
    )


def _run_update(rest: list[str], transport, project_dir):
    flags, positionals, err = _parse_flags(
        rest,
        valued={
            "repo", "title", "body", "stage", "kind", "area",
            "effort", "impact", "source", "if-updated-at",
            "tags", "affected", "working-branch",
        },
    )
    if err:
        return core.error("validation", err)
    if not positionals:
        return core.error("validation", "update requires an <id>")
    # `--tags` is plural because it sets the whole set rather than adding one —
    # the `--tag` on `list` filters by a single tag, which is a different verb on
    # purpose and is named for it.
    fields = {
        key: flags[key]
        for key in (
            "title", "body", "stage", "kind", "area", "effort", "impact", "source",
            "tags", "affected", "working-branch",
        )
        if key in flags
    }
    default_owner, default_repo, err = _repo_defaults(flags)
    if err:
        return core.error("validation", err)
    transport = _resolve_transport(transport)
    return _with_mirror(
        project_dir,
        lambda absorb: core.update_item(
            transport,
            id_raw=positionals[0],
            fields=fields,
            expected_updated_at=flags.get("if-updated-at"),
            default_owner=default_owner,
            default_repo=default_repo,
            absorb=absorb,
        ),
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
            "tag",
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
            "assignee", "state", "tag",
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


def _run_pick(rest: list[str], transport, project_dir):
    flags, _positionals, err = _parse_flags(
        rest, valued={"repo", "limit"}, boolean={"include-working"}
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
    transport = _resolve_transport(transport)
    from pathlib import Path  # noqa: PLC0415 — only the store-backed ops need a path

    return query.pick(
        transport,
        project_dir=Path(project_dir),
        owner=owner,
        repo=repo,
        limit=limit,
        include_working="include-working" in flags,
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


def _run_sync(rest: list[str], transport, project_dir):
    """Populate the backlog cache — the writer's entry point.

    Incremental by default: it fetches only what the provider reports changed
    since the stored watermark, and takes a rate-free 304 when nothing has.
    ``--rebuild`` forces the full scan, which is the answer to a corrupt store or
    a schema bump; the incremental path already falls back to it on its own when
    no watermark exists.

    This op is what three ``unavailable`` messages in ``cache.py`` and
    ``cachequery.py`` already tell the operator to run — a cache with no writer
    reachable from the CLI is a cache that only ever reports being empty."""
    flags, _positionals, err = _parse_flags(rest, valued={"repo"}, boolean={"rebuild"})
    if err:
        return core.error("validation", err)
    parsed = ids.parse_repo(flags.get("repo", ""))
    if parsed is None:
        return core.error("validation", "sync requires --repo owner/repo")
    owner, repo = parsed
    transport = _resolve_transport(transport)
    from pathlib import Path  # noqa: PLC0415 — only this op needs a path

    from . import sync as sync_mod  # noqa: PLC0415 — only this op drives the store

    run = sync_mod.full_rebuild if flags.get("rebuild") else sync_mod.incremental_sync
    return run(transport, project_dir=Path(project_dir), owner=owner, repo=repo)


#: The default staleness horizon for `cache-query stale`, in days — carried over
#: from the janitor's Backlog Health check, which has said ">90d" since it was
#: written against the markdown backend.
#:
#: An earlier version of this comment claimed the number "moves here rather than
#: being retyped in the skill, so the prose and the query cannot disagree" — which
#: was false as written: `skills/janitor/SKILL.md` and `skills/backlog/cache-reads.md`
#: both name a default, and this constant cannot stop them. The two now say "the
#: query's default" instead of a figure, so there is one number; the claim is
#: dropped rather than restated, because a comment asserting a property its own
#: tree contradicts is worse than no comment.
_STALE_DEFAULT_DAYS = 90

#: Each ``cache-query`` sub-query, mapped to the ``cachequery`` function that
#: answers it and the flags it accepts. ``ready`` is deliberately absent: its only
#: consumer is ``pick``, which is already an op here, so exposing it would give one
#: query two operator-facing doors.
#:
#: The queries are named for what a reader asks, not for the Python function —
#: `stale`, not `stale_items` — because the operator typing this has no register
#: to resolve module names against.
_CACHE_QUERIES: tuple[str, ...] = (
    "open", "created-since", "by-area", "affecting", "search",
    "stale", "unstaged", "resolve",
)


#: Per-query argument contracts, so the dispatcher can refuse what a query does
#: not take instead of dropping it. Kept as data beside `_CACHE_QUERIES` rather
#: than as per-branch guards: a query added to the tuple without an entry here
#: raises a `KeyError` at dispatch and fails its test, where a missing guard would
#: simply have gone quiet — which is the failure mode being fixed.
#:
#: Arity is the count of positionals, or `None` for "one or more".
_CACHE_QUERY_ARITY: dict[str, int | None] = {
    "open": 0, "unstaged": 0, "by-area": 0, "stale": 0,
    "created-since": 1, "resolve": 1,
    "search": None, "affecting": None,
}

#: Valued/boolean flags each query accepts, beyond the universal `--repo`.
_CACHE_QUERY_FLAGS: dict[str, frozenset[str]] = {
    "open": frozenset(),
    "unstaged": frozenset(),
    "by-area": frozenset({"all"}),
    "affecting": frozenset({"all"}),
    "stale": frozenset({"older-than"}),
    "search": frozenset({"area"}),
    "created-since": frozenset(),
    "resolve": frozenset(),
}


def _run_cache_query(rest: list[str], project_dir):
    """Read the local backlog cache — the **agent-facing** door onto ``cachequery``.

    Every consumer bound before this one was in-process Python (the norm probes,
    ``pick``), so the query surface needed no CLI. The consumers this serves are
    agents — the Critic's backlog-reconciliation walk, the PR reviewer's
    resolved-items and closes/status checks, the janitor's Backlog Health block —
    and an agent reaches a Python module only by running something.

    **This op reads and does nothing else**: no provider call, no store write, no
    session state touched. That is what makes it grantable to the ``critic-reviewer``
    agent type, whose narrow tool list is the Critic's no-execution enforcement — a
    reviewer holding this can ask the backlog a question and still cannot run a
    test, reach the network, or mutate the session it is reviewing.

    ``unavailable`` surfaces as exit 6, which is the whole contract for these
    consumers: a reader that cannot reach the store must be able to say so rather
    than report an empty set, and an exit code says it without the caller parsing
    prose.
    """
    flags, positionals, err = _parse_flags(
        rest,
        valued={"repo", "area", "older-than"},
        boolean={"all"},
    )
    if err:
        return core.error("validation", err)
    if not positionals:
        return core.error(
            "validation",
            f"cache-query requires a query ({'|'.join(_CACHE_QUERIES)})",
        )
    name, args = positionals[0], positionals[1:]
    if name not in _CACHE_QUERIES:
        return core.error(
            "validation",
            f"unknown query {name!r} (expected {'|'.join(_CACHE_QUERIES)})",
        )
    parsed = ids.parse_repo(flags.get("repo", ""))
    if parsed is None:
        return core.error("validation", "cache-query requires --repo owner/repo")
    scope = f"{parsed[0]}/{parsed[1]}"

    from datetime import datetime, timezone  # noqa: PLC0415 — only this op needs a clock
    from pathlib import Path  # noqa: PLC0415 — only this op needs a path

    from . import cachequery  # noqa: PLC0415 — lazy; no other op reads the store

    # **Everything a query does not take is refused, never ignored.** The rule was
    # applied to `--all` alone at first and left the rest silent, which put two
    # opposite policies in one dispatcher: `cache-query stale 60` returned the
    # 90-day set as `status: ok` — the caller meant `--older-than 60` — and extra
    # positionals were dropped without a word. A wrong answer that looks right is
    # the failure this whole surface exists to prevent, so the strict half wins.
    accepted = _CACHE_QUERY_FLAGS[name]
    for flag in sorted(set(flags) - accepted - {"repo"}):
        return core.error("validation", f"--{flag} does not apply to {name!r}")
    expected = _CACHE_QUERY_ARITY[name]
    if expected is not None and len(args) != expected:
        return core.error(
            "validation",
            f"{name} takes exactly {expected} argument(s), got {len(args)}",
        )
    if expected is None and not args:
        return core.error("validation", f"{name} requires at least one argument")

    common = {"project_dir": Path(project_dir), "scope": scope,
              "now": datetime.now(timezone.utc)}
    open_only = not flags.get("all")

    if name == "open":
        return cachequery.open_items(**common)
    if name == "unstaged":
        return cachequery.unstaged_items(**common)
    if name == "by-area":
        return cachequery.by_area(**common, open_only=open_only)
    if name == "stale":
        days, int_err = _int_flag(flags, "older-than", _STALE_DEFAULT_DAYS)
        if int_err:
            return core.error("validation", int_err)
        return cachequery.stale_items(**common, older_than_days=days)
    if name == "affecting":
        return cachequery.items_affecting(**common, changed_paths=args, open_only=open_only)
    if name == "created-since":
        return cachequery.items_created_since(**common, since=args[0])
    if name == "search":
        return cachequery.search(**common, text=" ".join(args), area=flags.get("area"))
    # `resolve` — the only remaining member, and the exhaustiveness is guaranteed
    # by the membership check above rather than by a fallback that could go stale.
    return cachequery.resolve(**common, id_raw=args[0], default_owner=parsed[0])


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


def _run_link(op: str, rest: list[str], transport, project_dir):
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
    return _with_mirror(
        project_dir,
        lambda absorb: fn(
            transport,
            id_raw=positionals[0],
            edge=edge,
            target_raw=target,
            default_owner=default_owner,
            default_repo=default_repo,
            absorb=absorb,
        ),
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
    result = migrate.import_backlog(
        transport,
        owner=owner,
        repo=repo,
        content=content,
        archive_content=archive_content,
        plan=plan,
        archive_scope=archive_scope,
        checkpoint=checkpoint,
    )
    return _refresh_after_import(result, transport, Path(project_dir), owner=owner, repo=repo)


def _refresh_after_import(result: dict, transport, project_dir, *, owner: str, repo: str) -> dict:
    """Bring the cache level after an import, by sync rather than by mirror.

    A bulk create holds no single authoritative issue to hand to the mirror — the
    importer creates through the transport directly, hundreds of times — so the
    per-write path does not apply and re-fetching each issue to feed it would
    spend a request per item to save one. An incremental sync costs one pass and
    is the mechanism already built for "the provider moved a lot": every created
    issue has an `updated_at` past the watermark, so the window catches them all.

    **Skipped, with a reason, when no store exists.** The import is by far the most
    likely command to run *before* a first sync — it is how a repo becomes a
    backlog at all — and building a store here would be a mirror creating one,
    which §6.1 forbids for the same reason it forbids it per write.

    A sync failure never fails the import. The issues are on the provider; the
    local cache is a mirror of them, and the next sync converges it."""
    if result.get("status") != "ok":
        return result

    from . import cache  # noqa: PLC0415 — lazy; only this tail touches the store

    path = cache.cache_path(project_dir)
    if path is None or not path.exists():
        # A diagnostic rather than a warning: an absent store is reported at every
        # read with the command that fixes it (§6.1), so a per-import warning would
        # restate it — but a maintainer asking "why is the cache empty after the
        # import?" deserves the answer where they are looking.
        core.log_diag("no backlog cache to refresh after the import; run `backlog sync` to build one")
        return result

    from . import sync  # noqa: PLC0415 — lazy

    # The import's own transport, not a fresh one: building a second would drop
    # the injected fake under test and open a second `gh` session in production.
    warmed = sync.incremental_sync(
        transport, project_dir=project_dir, owner=owner, repo=repo
    )
    if warmed.get("status") != "ok":
        message = (warmed.get("error") or {}).get("message") or "unknown reason"
        result["warnings"] = list(result.get("warnings") or []) + [
            f"the import succeeded, but the local backlog cache was not refreshed ({message}); "
            "run `prawduct-hook backlog sync` before relying on cached reads"
        ]
    return result


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
    # Ask the import's own gate about the records this preview is approving. The
    # preview is the owner's AGGREGATE pre-approval artifact for an irreversible
    # run, so a preview that reads clean and is then hard-refused by the import
    # has failed at its one job. It reports rather than refuses — a read-only
    # preview must still render, and the refusal is what the operator needs to
    # SEE. Note the preview document already lists per-entry lint findings, but
    # WARN-only body lints sit right beside these; what it could not say before is
    # which of them BLOCK.
    preflight_offenders = migrate.preflight_titles(applied["records"])

    source_label = flags["from"] + (f" + {flags['archive']}" if "archive" in flags else "")
    preview = restructure.render_preview(
        applied, source_label=source_label, collisions=collisions,
        blocking=preflight_offenders,
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
        "preflight_blocking": len(preflight_offenders),
        "nonconforming_titles": preflight_offenders,
        "collisions": len(collisions),
        "archive_skipped": archive_skipped,
        "total_source": len(records),  # records entering the import (post archive-scope filter)
    }
    warnings = applied["warnings"]
    if preflight_offenders:
        # First in the list: approving a plan the import will refuse wastes the
        # one review the owner gives an irreversible run.
        warnings = [
            f"{len(preflight_offenders)} of {len(records)} item(s) have titles that FAIL the "
            "issue standard §1 — an import of this plan would refuse before writing anything. "
            "Fix these titles in the restructure plan and re-preview; the per-item rules are in "
            "`nonconforming_titles` (and --json carries the full list)"
        ] + warnings
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


def _run_merge(rest: list[str], transport, project_dir):
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
    return _with_mirror(
        project_dir,
        lambda absorb: migrate.merge(
            transport,
            source_raw=positionals[0],
            target_raw=target,
            default_owner=default_owner,
            default_repo=default_repo,
            absorb=absorb,
        ),
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

    Fixed by op name. It once had a flag-sensitive arm — ``pick --claim`` was the
    one read that could mutate — and it went with the claim op; the signature
    keeps ``rest`` because the withhold decision is the kind that grows an arm
    again the moment an op takes a mutating flag, and re-threading the argument at
    that point is how the check gets skipped instead."""
    return op in _WRITE_OPS


def _with_mirror(project_dir, call):
    """Run a write with the local mirror bound, folding a mirror failure into the
    result's warnings rather than into its status.

    **The write has already landed on the provider by the time the mirror runs**,
    so a mirror failure can never become the command's failure — that would tell a
    caller to retry a mutation that is already done. It rides out as a warning on
    an otherwise-successful envelope.

    Two outcomes are deliberately silent. A store that does not exist is not a
    degraded mirror, it is a repo not using one, and every read already reports
    that condition with the command that fixes it; restating it on each write
    would be noise on a path where nothing is wrong and nothing is lost, since
    the next sync picks the item up by watermark anyway. An item outside the
    store's scope is likewise a correct write this cache was never meant to hold.
    Both are tagged ``details["mirror"] = "absent"`` at the source, so this reads a
    marker rather than matching on message text.
    """
    from pathlib import Path  # noqa: PLC0415 — only the store-backed ops need a path

    warnings: list[str] = []

    def absorb(issue, owner, repo):
        from . import sync  # noqa: PLC0415 — lazy; no store import on other paths

        try:
            outcome = sync.absorb_issue(
                Path(project_dir), owner=owner, repo=repo, issue=issue
            )
        # A supervisor boundary. The provider mutation has already landed by the
        # time this runs, so ANY escape would report a completed write as failed
        # and send the caller to retry it into a duplicate. The mirror is local
        # bookkeeping and the command's success does not depend on it. Nothing is
        # silenced — the failure becomes a warning on the envelope below, and the
        # type reaches the diagnostic log.
        #
        # The functions this calls are each written not to raise, and one of them
        # stopped being true once: `absorb_rows` ran its first query outside its
        # own guard, so an unreadable store escaped the whole chain. Distributing
        # a never-raises guarantee across a call chain means every future edit to
        # any link has to preserve it; catching at the seam makes it structural.
        #
        # prawduct:allow prawduct/broad-except -- supervisor boundary; see above
        except Exception as exc:
            warnings.append(
                "the write succeeded, but the local backlog cache was not updated "
                f"({type(exc).__name__}); cached reads stay stale until the next "
                "`prawduct-hook backlog sync`"
            )
            core.log_diag(f"the backlog cache mirror raised: {type(exc).__name__}: {exc}")
            return
        if outcome.get("status") == "ok":
            return
        failure = outcome.get("error") or {}
        if (failure.get("details") or {}).get("mirror") == sync.MIRROR_ABSENT:
            return
        warnings.append(
            "the write succeeded, but the local backlog cache was not updated "
            f"({failure.get('message') or 'unknown reason'}); "
            "cached reads stay stale until the next `prawduct-hook backlog sync`"
        )

    result = call(absorb)
    if warnings:
        # Attached regardless of the result's status. Today no call site can
        # mirror and then fail — every one invokes the mirror immediately before
        # its `ok(...)` — but conditioning advisory data on the success path is
        # the exact recurring defect this repo records for result envelopes
        # (BKL-3K9N, BKL-9V2W), and `_emit` already prints `warnings` on the error
        # branch. One clause removes the trap for the first op that mirrors before
        # a later failure.
        result["warnings"] = list(result.get("warnings") or []) + warnings
    return result


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



def _print_cache_query(data: dict) -> None:
    """Human-mode rendering for `cache-query`, freshness line included.

    **The age is printed on every shape, not only the ones with rows.** It is the
    invariant the whole store is built to carry, and `cache-reads.md` tells readers
    to name a conspicuously old store beside their finding — which they cannot do
    if the default output drops it. An empty result with a visible age is a
    different fact from an empty result of unknown vintage.
    """
    if "groups" in data:  # by-area
        for group in data.get("groups", []):
            print(f"{group.get('area')}  ({group.get('count')} item(s))")
            for item in group.get("items", []):
                _print_item_line(item)
        print(f"  {len(data.get('groups', []))} area(s)")
    elif "resolved" in data:  # resolve — a miss is an ANSWER, so it prints as one
        if not data.get("resolved"):
            # `reason` distinguishes "no such item" (None) from "that is not an id"
            # (a message). Dropping it sends a reader to the wrong repair.
            why = data.get("reason") or "no item in the cache claims that id"
            print(f"{data.get('requested')}: unresolved — {why}")
        else:
            _print_item_line(data)
            bits = [f"status={data.get('status')}", f"dead={data.get('dead')}"]
            if data.get("via"):
                bits.append(f"via={data['via']}")
            if data.get("redirected_from"):
                bits.append(f"redirected-from={data['redirected_from']}")
            print("  " + "  ".join(bits))
    else:  # every row-returning query
        items = data.get("items", [])
        for item in items:
            _print_item_line(item)
        print(f"  {len(items)} item(s)")
    print(f"  cache: {data.get('scope')}, confirmed {data.get('synced_at')} "
          f"({_humanize_seconds(data.get('age_seconds'))})")


def _humanize_seconds(age) -> str:
    """A compact age for the freshness line. Mirrors `briefing._humanize_age`'s
    vocabulary so one store does not read as two different ages depending on which
    surface reported it."""
    if not isinstance(age, (int, float)) or age < 0:
        return "age unknown"
    if age < 60:
        return "just now"
    if age < 3600:
        return f"{int(age // 60)}m old"
    if age < 86400:
        return f"{int(age // 3600)}h old"
    return f"{int(age // 86400)}d old"

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
    if not value:
        return str(len(value))
    if not all(isinstance(item, str) for item in value):
        return str(len(value))
    if len(value) <= _DETAIL_LIST_CAP:
        return ", ".join(value)
    head = ", ".join(value[:_DETAIL_LIST_CAP])
    return f"{head}, … (+{len(value) - _DETAIL_LIST_CAP} more)"


#: Detail keys whose entries are the **payload**, not bookkeeping — the same test
#: `_render_detail_list` applies to string lists, for lists of dicts. Each remedy
#: names the items ("rewrite the named titles", "inspect `failed` for the shared
#: cause"), so a bare count is unactionable, and the runbook drives these paths
#: without ``--json`` so the named form has no other route to the operator.
#: Anything absent here stays counted: `created`/`skipped`/`collisions` are
#: bookkeeping and would bury the message.
_NAMED_DETAIL_ENTRIES = {
    "nonconforming_titles": lambda e: f"{e.get('title')!r} — {', '.join(e.get('rules') or [])}",
    "failed": lambda e: f"{e.get('title')!r} — {e.get('error')}",
}


def _render_named_entries(value: list, project) -> str:
    """Render a payload dict-list as named lines, capped like the string form.

    An empty list renders as ``0``, not as a bare newline: a resumable cut
    carrying ``failed: []`` otherwise printed the key followed by a blank
    indented line, which reads as truncated output rather than as "none"."""
    if not value:
        return "0"
    shown = [project(item) if isinstance(item, dict) else str(item) for item in value]
    if len(shown) <= _DETAIL_LIST_CAP:
        return "\n      " + "\n      ".join(shown)
    head = "\n      " + "\n      ".join(shown[:_DETAIL_LIST_CAP])
    return f"{head}\n      … (+{len(shown) - _DETAIL_LIST_CAP} more)"


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
        # Standard lint findings — emitted by `file` (body/label) and by `update`
        # (a stored title left unconformed). Advisory by construction: a finding
        # that BLOCKS never reaches here, because it returned a validation error
        # instead. So these never affect the exit code, and stay distinct from
        # operational warnings.
        for finding in result.get("lint", []):
            print(f"lint: {finding.get('message')}", file=sys.stderr)
    else:
        _print_human_error(result.get("error", {}))
        # A resumable error envelope (e.g. import) carries the audit warnings accrued
        # before the cut; surface them like the ok path so they reach the operator.
        for warning in result.get("warnings", []):
            print(f"warning: {warning}", file=sys.stderr)
        if usage:
            print(_HELP, file=sys.stderr)
    return exit_code


def _print_human_error(err: dict) -> None:
    """Render an error envelope to stderr.

    Extracted from :func:`_emit` so it can be tested directly. It could not be
    before, and the consequence was exactly the defect this docstring now guards:
    `nonconforming_titles` printed as a bare count for two review rounds because
    every test of the refusal read the `--json` envelope instead.

    A cut mid-import already KNOWS how far it got — the envelope carries
    `created`/`skipped`/`failed`/`collisions`/`resumable`/`pacing` — and human
    mode once dropped all of it, so the operator of an irreversible ~900-issue
    migration learned only that it broke. The scrub runbook drives this path
    without ``--json``, so this is the surface that matters.
    """
    print(f"error [{err.get('code')}]: {err.get('message')}", file=sys.stderr)
    for key, value in (err.get("details") or {}).items():
        if key == "pacing" and isinstance(value, dict):
            shown = _pacing_line(value)
        elif isinstance(value, list) and key in _NAMED_DETAIL_ENTRIES:
            shown = _render_named_entries(value, _NAMED_DETAIL_ENTRIES[key])
        elif isinstance(value, list):
            shown = _render_detail_list(value)
        else:
            shown = value
        print(f"  {key}: {shown}", file=sys.stderr)


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
    elif "synced_at" in data and "age_seconds" in data:
        # A `cache-query` result. Matched on the pair of freshness keys
        # every `cachequery` payload carries and no other op produces — the shapes
        # underneath overlap several branches below (`items`, `id`), so keying on
        # those would route a cache read into a formatter built for a live one.
        # (Two branches sit above this one; neither can collide — an `edge`+`target`
        # link result and a `preview` result share no key with a cache payload.)
        #
        # This branch exists because `boundary-patterns.md` records "Result
        # Envelopes" as a contract surface with TWO consumers — the `--json`
        # passthrough and these formatters — and its recurring defect is that a
        # `--json`-only test never runs the second. It did so again here: before
        # this branch, `unstaged` printed every item and then `0 item(s)` (the
        # `items` branch reads a `count` key no cache payload carries), a `resolve`
        # miss printed a blank line and `status=None`, and `by-area` fell through
        # to a raw JSON dump.
        _print_cache_query(data)
    elif "total_source" in data:
        # An import result (checked before `items`: an export result also carries an
        # `items` key, so the migration results are matched first on their own keys).
        # `failed` rides in the count line, not only in a warning: without it the
        # summary triple silently stops summing to `total_source`, so a run that
        # dropped items reads as a clean import. Named in the same breath as the
        # others because it is the only one of them that means "this item is not on
        # the target at all".
        failed = data.get("failed") or []
        line = (
            f"{data.get('repo')}: imported {len(data.get('created', []))} created, "
            f"{len(data.get('skipped', []))} skipped, "
            f"{len(failed)} rejected, "
            f"{len(data.get('collisions', []))} collision(s) of "
            f"{data.get('total_source')} source item(s)"
        )
        if "restructured" in data:
            line += f" ({data['restructured']} restructured by plan)"
        print(line)
        if failed:
            print(
                f"  WARNING: {len(failed)} item(s) were REJECTED and are NOT on the "
                "target — re-run the import to retry them, then verify-migration:"
                + _render_named_entries(failed, _NAMED_DETAIL_ENTRIES["failed"])
            )
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
        if data.get("working_branch"):
            # The someone-is-on-it signal, and visibility is its ONLY job — a populated
            # `working-branch` that the default human view omits fails at exactly
            # the thing the field exists for. `tags` and `affected` are not here
            # for the same reason `area`/`effort`/`impact` are not: they are read
            # by filters and by the changed-file intersection, not off this line.
            bits.append(f"working-branch={data['working_branch']}")
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
