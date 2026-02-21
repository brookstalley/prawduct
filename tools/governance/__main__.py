"""CLI entry point for the governance module.

Usage: python3 -m governance <command> [--root DIR]

Commands:
  gate             — PreToolUse gate (Edit/Write/Read/Task/Glob/Grep). Exit 0=allow, 2=block.
  track            — PostToolUse tracker (Edit/Write). Exit 0 always.
  failure          — PostToolUseFailure PFR reminder (Edit/Write). Exit 0 always.
  stop             — Stop hook validation. Exit 0=allow, 2=block.
  commit           — Commit gate (Bash with git commit). Exit 0=allow, 2=block.
  prompt           — UserPromptSubmit activation check. Exit 0 always.
  compact-reinject — SessionStart compact reinject. Exit 0 always.

Hook JSON is read from stdin for gate/track/failure/stop/commit.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import NoReturn

from . import __version__
from .context import resolve, update_product_context, enumerate_active_products
from .state import SessionState


def _parse_root(args: list[str]) -> str | None:
    if "--root" in args:
        idx = args.index("--root")
        if idx + 1 < len(args):
            return args[idx + 1]
    return None


def _read_hook_json() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return {}


def main() -> NoReturn:
    args = sys.argv[1:]

    if "--version" in args:
        print(__version__)
        sys.exit(0)

    if not args:
        print(
            "Usage: python3 -m governance <gate|track|failure|stop|commit|prompt|compact-reinject> [--root DIR]",
            file=sys.stderr,
        )
        sys.exit(1)

    command = args[0]
    root = _parse_root(args)

    # Lightweight advisory commands (no session state needed)
    if command == "failure":
        hook_input = _read_hook_json()
        _run_failure(hook_input)
    elif command == "prompt":
        sys.stdin.read()  # consume stdin per hook protocol
        _run_prompt(root)
    elif command == "compact-reinject":
        _run_compact_reinject(root)
    else:
        # Standard hook commands: read JSON from stdin, load state
        hook_input = _read_hook_json()

        # Stop/commit do NOT follow the active-products registry via resolve().
        # Stop enumerates all registered products itself (multi-product debt check).
        # Commit operates per-commit at session level only.
        # Gate/track follow the registry (and also call update_product_context)
        # because they operate per-file — they need the correct product context
        # for classification and state tracking.
        session_level = command in ("stop", "commit")
        try:
            ctx = resolve(framework_root=root, follow_pointer=not session_level)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)

        # For gate/track: resolve product from the file being operated on
        # and update ctx so all downstream code uses the correct paths.
        # Read operations resolve context but don't register products —
        # reading a file is passive and shouldn't cause the stop hook
        # to validate that repo's governance debt.
        if command in ("gate", "track"):
            file_path = hook_input.get("tool_input", {}).get("file_path", "")
            tool_name = hook_input.get("tool_name", "")
            register = command == "track" or tool_name not in ("Read",)
            ctx = update_product_context(file_path, ctx, register=register)

        state = SessionState.load(ctx.session_file)

        if command == "gate":
            _run_gate(hook_input, ctx, state)
        elif command == "track":
            _run_track(hook_input, ctx, state)
        elif command == "stop":
            _run_stop(hook_input, ctx, state)
        elif command == "commit":
            _run_commit(hook_input, ctx, state)
        else:
            print(f"Unknown command: {command}", file=sys.stderr)
            sys.exit(1)


def _run_failure(hook_input: dict) -> NoReturn:
    from .failure import check

    output = check(hook_input)
    if output:
        print(output)
    sys.exit(0)


def _run_prompt(root: str | None) -> NoReturn:
    from .prompt import check

    try:
        ctx = resolve(framework_root=root, follow_pointer=False)
    except ValueError:
        sys.exit(0)  # no framework = no activation check

    output = check(ctx)
    if output:
        print(output)
    sys.exit(0)


def _run_compact_reinject(root: str | None) -> NoReturn:
    from .reinject import build_reinject

    try:
        ctx = resolve(framework_root=root, follow_pointer=False)
    except ValueError as e:
        # Minimal fallback if context resolution fails
        print("CONTEXT RESTORED AFTER COMPACTION.")
        if root:
            print(f"Read {root}/skills/orchestrator/SKILL.md from disk before taking action.")
        sys.exit(0)

    print(build_reinject(ctx))
    sys.exit(0)


def _run_gate(hook_input: dict, ctx, state: SessionState) -> NoReturn:
    from .gate import check

    decision = check(hook_input, ctx, state)
    # Gate checks are read-only — they never mutate session state.
    # Trace events go to .session-trace.jsonl via tr.event(), not
    # through state.save(). Saving here would rewrite the file on
    # every gate check, causing race conditions when the agent tries
    # to Read then Edit .session-governance.json (the gate's save
    # changes the file's mtime between those operations).
    if decision.allowed:
        sys.exit(0)
    else:
        print(decision.reason, file=sys.stderr)
        sys.exit(2)


def _run_track(hook_input: dict, ctx, state: SessionState) -> NoReturn:
    from .tracker import track

    track(hook_input, ctx, state)
    state.save()
    sys.exit(0)


def _run_stop(hook_input: dict, ctx, state: SessionState) -> NoReturn:
    from .stop import validate
    from .context import Context

    all_debts: list[str] = []

    # 1. Check session-level debt (framework repo's own governance)
    decision = validate(hook_input, ctx, state)
    all_debts.extend(decision.debts)

    # 2. Enumerate registered products and check each one's debt.
    # Only check products registered during THIS session — stale registrations
    # from prior conversations should not block session exit.
    session_prawduct_dir = ctx.prawduct_dir
    session_real = os.path.realpath(session_prawduct_dir)
    session_start_ts = 0.0
    if state.session_started:
        try:
            session_start_ts = datetime.fromisoformat(
                state.session_started.replace("Z", "+00:00")
            ).timestamp()
        except (ValueError, TypeError):
            pass
    for product_dir in enumerate_active_products(
        session_prawduct_dir, min_timestamp=session_start_ts
    ):
        product_real = os.path.realpath(product_dir)
        if product_real == session_real:
            continue  # Already checked above

        try:
            product_ctx = Context(
                framework_root=ctx.framework_root,
                prawduct_dir=product_dir,
                repo_root=os.path.dirname(product_dir),
            )
            product_state = SessionState.load(product_ctx.session_file)
            product_decision = validate(hook_input, product_ctx, product_state)
            product_name = os.path.basename(os.path.dirname(product_dir))
            for debt in product_decision.debts:
                all_debts.append(f"[{product_name}] {debt}")
        except Exception:
            continue  # Never block on product enumeration failure

    if not all_debts:
        sys.exit(0)
    else:
        print("", file=sys.stderr)
        print(
            f"BLOCKED: Governance debt. Read {ctx.framework_root}/skills/orchestrator/protocols/governance.md and resolve:",
            file=sys.stderr,
        )
        print("; ".join(all_debts), file=sys.stderr)
        print("", file=sys.stderr)
        sys.exit(2)


def _run_commit(hook_input: dict, ctx, state: SessionState) -> NoReturn:
    from .commit import check_and_archive

    decision = check_and_archive(hook_input, ctx, state)
    if decision.allowed:
        sys.exit(0)
    else:
        print(decision.reason, file=sys.stderr)
        sys.exit(2)


main()
