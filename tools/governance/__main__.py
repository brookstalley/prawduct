"""CLI entry point for the governance module.

Usage: python3 -m governance <command> [--root DIR]

Commands:
  gate             — PreToolUse gate (Edit/Write/Read). Exit 0=allow, 2=block.
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
import sys
from typing import NoReturn

from . import __version__
from .context import resolve
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
        try:
            ctx = resolve(framework_root=root)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
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
        ctx = resolve(framework_root=root)
    except ValueError:
        sys.exit(0)  # no framework = no activation check

    output = check(ctx)
    if output:
        print(output)
    sys.exit(0)


def _run_compact_reinject(root: str | None) -> NoReturn:
    from .reinject import build_reinject

    try:
        ctx = resolve(framework_root=root)
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

    decision = validate(hook_input, ctx, state)
    if decision.allowed:
        sys.exit(0)
    else:
        print("", file=sys.stderr)
        print(
            f"BLOCKED: Governance debt. Read {ctx.framework_root}/skills/orchestrator/protocols.md and resolve:",
            file=sys.stderr,
        )
        print("; ".join(decision.debts), file=sys.stderr)
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
