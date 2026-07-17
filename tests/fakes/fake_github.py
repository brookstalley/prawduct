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

Fault-injection: ``fail_at_mutation(n)`` arms the fake so the n-th subsequent
**mutating** call (create/update/label/comment — never a read) raises
``unavailable`` exactly once, then disarms. That lets a test cut a compound
transition at each intermediate point and assert the decoder still reads a valid
state and a re-run converges (Test Specs §3.2 crash-safety) — no real
process-kill needed, because the canonical write-orders make each cut
deterministic.
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
        self.comments: dict[int, list[dict]] = {}
        self.next_comment_id: int = 1
        # A monotonic tick so every mutation stamps a distinct `updated_at`
        # (what the optimistic-CAS `update` compares against — CC2).
        self.clock: int = 0


class FakeGitHub(Transport):
    def __init__(self, user: dict | None = None) -> None:
        self.user = dict(user) if user else dict(_DEFAULT_USER)
        self.repos: dict[tuple[str, str], _RepoState] = {}
        # Observability for tests.
        self.calls: list[tuple] = []
        self.user_resolutions = 0
        self._user_cache: dict | None = None
        # Fault injection (armed via fail_at_mutation).
        self._fail_at: int | None = None
        self._mutation_count = 0

    # -- helpers -----------------------------------------------------------

    def _repo(self, owner: str, repo: str) -> _RepoState:
        key = (owner, repo)
        if key not in self.repos:
            self.repos[key] = _RepoState()
        return self.repos[key]

    def fail_at_mutation(self, n: int) -> None:
        """Arm: the n-th (1-based) mutating call after this returns raises
        ``unavailable`` once, then disarms. ``n <= 0`` disarms immediately."""
        self._fail_at = n if n and n > 0 else None
        self._mutation_count = 0

    def _check_fault(self) -> None:
        """Called at the top of every mutating method. Counts only while armed."""
        if self._fail_at is None:
            return
        self._mutation_count += 1
        if self._mutation_count == self._fail_at:
            self._fail_at = None  # one-shot: the re-run must be allowed to complete
            raise TransportError(
                "unavailable",
                "injected transport failure (fault injection)",
                details={"injected": True},
            )

    def _stamp(self, state: _RepoState, issue: dict) -> None:
        """Bump `updated_at` to a fresh distinct value (drives CAS detection)."""
        state.clock += 1
        issue["updated_at"] = f"2026-01-01T00:00:00.{state.clock:06d}Z"

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
        self._check_fault()
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
        self._check_fault()
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

    # -- mutations (the state-machine write path) --------------------------

    def update_issue(
        self, owner: str, repo: str, number: int, *, fields: dict
    ) -> dict:
        self._check_fault()
        self.calls.append(("update_issue", owner, repo, number, tuple(sorted(fields))))
        state = self._repo(owner, repo)
        issue = state.issues.get(number)
        if issue is None:
            raise TransportError(
                "not_found",
                "the requested GitHub resource was not found",
                details={"operation": f"api repos/{owner}/{repo}/issues/{number}"},
            )
        for key in ("title", "body", "state", "state_reason"):
            if key in fields:
                issue[key] = fields[key]
        # GitHub clears `state_reason` when an issue is reopened.
        if fields.get("state") == "open":
            issue["state_reason"] = None
        self._stamp(state, issue)
        return dict(issue)

    def add_labels(
        self, owner: str, repo: str, number: int, labels: list[str]
    ) -> list[dict]:
        self._check_fault()
        self.calls.append(("add_labels", owner, repo, number, tuple(labels)))
        state = self._repo(owner, repo)
        issue = state.issues.get(number)
        if issue is None:
            raise TransportError(
                "not_found",
                "the requested GitHub resource was not found",
                details={"operation": f"api repos/{owner}/{repo}/issues/{number}/labels"},
            )
        missing = [name for name in labels if name not in state.labels]
        if missing:
            # Conservative model of GitHub's 422 (same as create_issue) — the
            # adapter provisions before it adds, so it never reaches here.
            raise TransportError(
                "validation",
                "cannot add labels that do not exist",
                details={"missing_labels": missing},
            )
        present = {label["name"] for label in issue["labels"]}
        changed = False
        for name in labels:
            if name not in present:
                issue["labels"].append(dict(state.labels[name]))
                present.add(name)
                changed = True
        if changed:
            self._stamp(state, issue)
        return [dict(label) for label in issue["labels"]]

    def remove_label(self, owner: str, repo: str, number: int, name: str) -> None:
        # A label already absent is the desired end state — GitHub 404s and the
        # real transport swallows it, so the fake mirrors that (idempotent), while
        # still counting the attempt as a mutating call for fault injection.
        self._check_fault()
        self.calls.append(("remove_label", owner, repo, number, name))
        state = self._repo(owner, repo)
        issue = state.issues.get(number)
        if issue is None:
            raise TransportError(
                "not_found",
                "the requested GitHub resource was not found",
                details={"operation": f"api repos/{owner}/{repo}/issues/{number}/labels/{name}"},
            )
        before = len(issue["labels"])
        issue["labels"] = [label for label in issue["labels"] if label["name"] != name]
        if len(issue["labels"]) != before:
            self._stamp(state, issue)

    def create_comment(
        self, owner: str, repo: str, number: int, *, body: str
    ) -> dict:
        self._check_fault()
        self.calls.append(("create_comment", owner, repo, number))
        state = self._repo(owner, repo)
        issue = state.issues.get(number)
        if issue is None:
            raise TransportError(
                "not_found",
                "the requested GitHub resource was not found",
                details={"operation": f"api repos/{owner}/{repo}/issues/{number}/comments"},
            )
        cid = state.next_comment_id
        state.next_comment_id += 1
        comment = {
            "id": cid,
            "body": body,
            "user": {"login": self.user["login"], "id": self.user["id"]},
            "html_url": f"https://github.com/{owner}/{repo}/issues/{number}#issuecomment-{cid}",
            "created_at": "2026-01-01T00:00:00Z",
        }
        state.comments.setdefault(number, []).append(comment)
        return dict(comment)
