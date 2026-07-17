"""The transport-seam fake — an in-process GitHub for the L1 deterministic suite.

Implements the subset of GitHub the adapter uses (Test Specs §6), swapped in at
the transport boundary (Test Specs §2.1) so L1 runs offline, with no ``gh`` and
no network. It is **stateful** — it remembers the labels/state a prior call set,
which is what lets crash-recovery and idempotent-re-run tests (built in the
state-machine chunk) observe convergence. It raises the same
``transport.TransportError`` the real transport does, so core's error handling is
exercised identically on both paths.

Behavioral choices flagged as ``verify-api``/S1-pending (Test Specs §2.1: a
fake's *behavior* is confirmed by the L4/L5 spikes, not by the shape-diff):
- ``create_issue`` requires every applied label to **already exist** (a
  validation error otherwise). This is the conservative model — the adapter
  provisions the labels it needs before creating, so it is correct whether or not
  real GitHub auto-creates missing labels.

Fault-injection (fail the n-th mutating call) is added with the crash-safety
tests in the state-machine chunk; this Chunk-01 fake is stateful but has no
fault injection yet.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.backlog.transport import Transport, TransportError  # noqa: E402

_DEFAULT_USER = {"login": "octocat", "id": 1, "node_id": "U_octocat"}


class _RepoState:
    def __init__(self) -> None:
        self.issues: dict[int, dict] = {}
        self.labels: dict[str, dict] = {}
        self.next_number: int = 1


class FakeGitHub(Transport):
    def __init__(self, user: dict | None = None) -> None:
        self.user = dict(user) if user else dict(_DEFAULT_USER)
        self.repos: dict[tuple[str, str], _RepoState] = {}
        # Observability for tests.
        self.calls: list[tuple] = []
        self.user_resolutions = 0
        self._user_cache: dict | None = None

    # -- helpers -----------------------------------------------------------

    def _repo(self, owner: str, repo: str) -> _RepoState:
        key = (owner, repo)
        if key not in self.repos:
            self.repos[key] = _RepoState()
        return self.repos[key]

    def seed_labels(self, owner: str, repo: str, names: list[str]) -> None:
        """Pre-create labels (for tests that bypass provisioning)."""
        state = self._repo(owner, repo)
        for name in names:
            state.labels.setdefault(name, {"name": name, "color": "ededed", "description": ""})

    # -- Transport interface ----------------------------------------------

    def get_authenticated_user(self) -> dict:
        self.calls.append(("get_authenticated_user",))
        if self._user_cache is None:
            self.user_resolutions += 1
            self._user_cache = dict(self.user)
        return self._user_cache

    def create_issue(
        self, owner: str, repo: str, *, title: str, body: str, labels: list[str]
    ) -> dict:
        self.calls.append(("create_issue", owner, repo, title, tuple(labels)))
        state = self._repo(owner, repo)
        missing = [name for name in labels if name not in state.labels]
        if missing:
            # Conservative model of GitHub's 422 (see module docstring).
            raise TransportError(
                "validation",
                "cannot create issue with labels that do not exist",
                details={"missing_labels": missing},
            )
        number = state.next_number
        state.next_number += 1
        issue = {
            "number": number,
            "node_id": f"I_{owner}_{repo}_{number}",
            "title": title,
            "body": body,
            "state": "open",
            "state_reason": None,
            "labels": [dict(state.labels[name]) for name in labels],
            "assignee": None,
            "assignees": [],
            "user": {"login": self.user["login"], "id": self.user["id"]},
            "html_url": f"https://github.com/{owner}/{repo}/issues/{number}",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        state.issues[number] = issue
        return dict(issue)

    def get_issue(self, owner: str, repo: str, number: int) -> dict:
        self.calls.append(("get_issue", owner, repo, number))
        state = self._repo(owner, repo)
        issue = state.issues.get(number)
        if issue is None:
            raise TransportError(
                "not_found",
                "the requested GitHub resource was not found",
                details={"operation": f"api repos/{owner}/{repo}/issues/{number}"},
            )
        return dict(issue)

    def list_labels(self, owner: str, repo: str) -> list[dict]:
        self.calls.append(("list_labels", owner, repo))
        state = self._repo(owner, repo)
        return [dict(label) for label in state.labels.values()]

    def create_label(
        self, owner: str, repo: str, *, name: str, color: str, description: str
    ) -> dict:
        self.calls.append(("create_label", owner, repo, name))
        state = self._repo(owner, repo)
        if name in state.labels:
            # GitHub returns 422 "already_exists" — provision lists-then-creates
            # so it never reaches here; guard anyway.
            raise TransportError(
                "validation",
                "label already exists",
                details={"name": name},
            )
        label = {"name": name, "color": color, "description": description}
        state.labels[name] = label
        return dict(label)
