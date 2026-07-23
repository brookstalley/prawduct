"""Runtime context — unattended detection + the Actions pwn-request guard.

Two security behaviors that depend on *where the adapter is running*, resolved
from the environment (mechanized, not asserted — N1) so they are pure and
unit-testable without spawning anything:

- **Unattended (Security §1a, SEC-6).** A background worker / detached briefing
  refresh runs with **no human present**. It never prompts (the transport already
  disables `gh` prompts — INV-2), fails clean on auth, and **marks its mutations
  `automated: true`** + a worker id so a bulk sweep is not misattributed to the
  human (CC4). "Unattended" is an *explicit* signal, never guessed from "no TTY"
  (the CLI is always non-interactive, so no-TTY cannot distinguish an agent at the
  keyboard from a cron job): ``PRAWDUCT_UNATTENDED`` set by the caller, or a
  GitHub Actions run.

- **Actions untrusted trigger (Security §1b, SEC-5).** Under an untrusted-
  triggerable workflow event the *triggerer* can be an anonymous outsider while
  the *actor* is the write-scoped App bot — the classic "pwn request". The App
  bot's scope is the privilege ceiling, **not** the triggerer's, so the
  unattended-write capability is **withheld** from such runs unless the workflow
  has done an explicit triggering-actor authorization check (surfaced back as
  ``PRAWDUCT_ACTOR_AUTHORIZED``). Read-only reporting stays allowed.

The front (``cli.py``) resolves context from the environment and passes the
booleans into ``core`` — ``core`` stays env-free and pure.
"""

from __future__ import annotations

import os

# Workflow events an external, untrusted party can trigger while the job runs
# with the repo's write-scoped token (Security §1b). A fork ``pull_request`` is
# also untrusted; it is caught by the fork check below (base repo != head repo).
_UNTRUSTED_EVENTS: frozenset[str] = frozenset(
    {"pull_request_target", "issue_comment", "issues", "discussion", "discussion_comment"}
)

WITHHOLD_MESSAGE = (
    "write withheld: an untrusted-triggered GitHub Actions run may not perform "
    "backlog writes without an explicit triggering-actor authorization check "
    "(pwn-request defense, Security §1b)"
)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _env(env: dict | None) -> dict:
    return env if env is not None else os.environ


def is_actions(env: dict | None = None) -> bool:
    """Whether we are inside a GitHub Actions run (`GITHUB_ACTIONS=true`)."""
    return _truthy(_env(env).get("GITHUB_ACTIONS"))


def is_unattended(env: dict | None = None) -> bool:
    """Whether this run has no human present (explicit signal or Actions).

    Explicit ``PRAWDUCT_UNATTENDED`` (set by a scheduled job or the detached
    refresh) or any Actions run. Never inferred from "no TTY" — see the module
    docstring."""
    e = _env(env)
    return _truthy(e.get("PRAWDUCT_UNATTENDED")) or is_actions(e)


def worker_marker(env: dict | None = None) -> str:
    """A stable identifier for the unattended actor, stamped alongside
    ``automated: true`` (CC4). Prefers an explicit ``PRAWDUCT_WORKER``; falls back
    to the Actions workflow name, then a generic label."""
    e = _env(env)
    return e.get("PRAWDUCT_WORKER") or e.get("GITHUB_WORKFLOW") or "prawduct-hook"


def is_untrusted_trigger(env: dict | None = None) -> bool:
    """Whether the current Actions event is untrusted-triggerable (Security §1b).

    True for the named untrusted events, and for a fork ``pull_request`` (head repo
    differs from the base repo — an outside contributor's branch). Outside Actions
    this is always False (the guard only bites in a workflow)."""
    e = _env(env)
    if not is_actions(e):
        return False
    event = (e.get("GITHUB_EVENT_NAME") or "").strip()
    if event in _UNTRUSTED_EVENTS:
        # The write-token-bearing untrusted events (`pull_request_target`,
        # `issue_comment`, `issues`, `discussion*`) — the real pwn-request surface.
        # Covered **unconditionally**, from native Actions env, no wiring needed.
        return True
    if event == "pull_request":
        # A fork `pull_request` is untrusted too, but a fork run is granted a
        # **read-only** token by GitHub — so this is *defense-in-depth*, not the
        # load-bearing control (that is the event set above). `GITHUB_PR_HEAD_REPO`
        # is **not** a native Actions variable: the workflow must surface it as
        # `PRAWDUCT_PR_HEAD_REPO` (e.g. `${{ github.event.pull_request.head.repo.full_name }}`),
        # the same workflow-surfaced-signal family as `PRAWDUCT_ACTOR_AUTHORIZED`.
        # Absent that wiring this branch is inert — safe by construction (the token
        # is read-only), but the wiring is required to make the flag *itself* fire.
        head = (e.get("GITHUB_HEAD_REF") or "").strip()
        base_repo = (e.get("GITHUB_REPOSITORY") or "").strip()
        fork_repo = (e.get("PRAWDUCT_PR_HEAD_REPO") or "").strip()
        return bool(head) and bool(fork_repo) and fork_repo != base_repo
    return False


def actor_authorized(env: dict | None = None) -> bool:
    """Whether the workflow asserted the triggering actor is authorized.

    The explicit triggering-actor authorization check Security §1b requires lives
    in the *workflow* (e.g. "is the triggerer a repo collaborator?"); its result is
    surfaced to the adapter as ``PRAWDUCT_ACTOR_AUTHORIZED``. Absent it, an
    untrusted-triggered write is withheld — a structural default-deny, not a
    documented "please don't"."""
    return _truthy(_env(env).get("PRAWDUCT_ACTOR_AUTHORIZED"))


def writes_withheld(env: dict | None = None) -> bool:
    """Whether backlog **writes** must be refused in this context (SEC-5).

    Withheld exactly when an untrusted-triggered Actions run has **not** cleared
    the triggering-actor authorization check. Reads are never withheld — read-only
    reporting under such triggers is fine (Security §1b)."""
    e = _env(env)
    return is_untrusted_trigger(e) and not actor_authorized(e)
