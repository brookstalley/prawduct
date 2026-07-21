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
        # Native relationships, ref-keyed (owner, repo, number):
        #   blocked_by[n] = the issues that block issue n (pick's blocker fan-out)
        #   sub_issues[n] = the child issues of parent issue n
        self.blocked_by: dict[int, set[tuple[str, str, int]]] = {}
        self.sub_issues: dict[int, set[tuple[str, str, int]]] = {}
        # A minimal native timeline per issue (what export serializes for CC4/audit;
        # a close/reopen/assign event is appended as the mutation happens, so the
        # dump has a real — if shallow — event history to round-trip, MIG-3).
        self.timeline: dict[int, list[dict]] = {}
        # Replication window (QRY-1): number → remaining reads to hide it for,
        # modelling GitHub's observed brief 404-after-create window.
        self.hidden: dict[int, int] = {}


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
        self._fail_code = "unavailable"
        self._fail_details: dict = {"injected": True}
        # Backend-down modelling (Test Specs §3.4 never-block): when set, every
        # call — read or write — raises `unavailable`, as if GitHub were
        # unreachable. Reads have no `fail_at_mutation` hook, so this is the way to
        # exercise read-path degradation and the never-block floor.
        self.unreachable = False
        # Persistent secondary rate limit (BKL-3K9N): when set, every call raises
        # `rate_limited` (carrying `details`, e.g. a `retry_after`), modelling a
        # window that outlasts the reactive backoff's budget.
        self._rate_limited = False
        self._rate_limited_details: dict = {}

    # -- helpers -----------------------------------------------------------

    def _repo(self, owner: str, repo: str) -> _RepoState:
        key = (owner, repo)
        if key not in self.repos:
            self.repos[key] = _RepoState()
        return self.repos[key]

    def set_unreachable(self, flag: bool = True) -> None:
        """Model GitHub being unreachable: every subsequent call raises a
        retryable ``unavailable`` (the backend-down condition for never-block
        tests). Clear with ``set_unreachable(False)``."""
        self.unreachable = flag

    def _maybe_unreachable(self) -> None:
        if self.unreachable:
            raise TransportError("unavailable", "GitHub is unreachable")
        if self._rate_limited:
            raise TransportError(
                "rate_limited",
                "secondary rate limit (fault injection)",
                details=dict(self._rate_limited_details),
            )

    def set_rate_limited(self, flag: bool = True, *, details: dict | None = None) -> None:
        """Model a persistent secondary rate limit: every subsequent call — read or
        write — raises ``rate_limited`` (carrying ``details``, e.g. a ``retry_after``).
        Clear with ``set_rate_limited(False)``. The importer's reactive backoff
        exhausts its budget against this and falls through to a resumable envelope."""
        self._rate_limited = flag
        self._rate_limited_details = details or {}

    def fail_at_mutation(
        self, n: int, *, code: str = "unavailable", details: dict | None = None
    ) -> None:
        """Arm: the n-th (1-based) mutating call after this returns raises ``code``
        (default ``unavailable``) once, then disarms. ``details`` rides the error
        (e.g. ``{"retry_after": 5}`` for a one-shot 429). ``n <= 0`` disarms."""
        self._fail_at = n if n and n > 0 else None
        self._mutation_count = 0
        self._fail_code = code
        self._fail_details = details if details is not None else {"injected": True}

    def _check_fault(self) -> None:
        """Called at the top of every mutating method. Counts only while armed."""
        self._maybe_unreachable()
        if self._fail_at is None:
            return
        self._mutation_count += 1
        if self._mutation_count == self._fail_at:
            self._fail_at = None  # one-shot: the re-run must be allowed to complete
            raise TransportError(
                self._fail_code,
                "injected transport failure (fault injection)",
                details=dict(self._fail_details),
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

    def arm_replication_window(
        self, owner: str, repo: str, number: int, misses: int = 1
    ) -> None:
        """Arm the observed 404-after-create window (QRY-1): issue ``number`` will
        be absent from the next ``misses`` reads (a ``get`` on it 404s; a ``list``
        omits it), then appear. Models GitHub's brief post-create replication lag
        so the adapter's bounded settle-retry can be exercised offline."""
        self._repo(owner, repo).hidden[number] = max(0, misses)

    def _replication_hidden(self, state: _RepoState, number: int) -> bool:
        """Consume one read against the replication window for ``number``.

        Returns True while the issue is still within its hide window (and
        decrements it), False once it has settled (the common, un-armed case)."""
        remaining = state.hidden.get(number, 0)
        if remaining <= 0:
            return False
        remaining -= 1
        if remaining == 0:
            state.hidden.pop(number, None)
        else:
            state.hidden[number] = remaining
        return True

    # -- Transport interface ----------------------------------------------

    def get_authenticated_user(self) -> dict:
        self._maybe_unreachable()
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

    def seed_pull_requests(
        self,
        owner: str,
        repo: str,
        count: int,
        *,
        state: str = "closed",
        labels: list[str] | None = None,
    ) -> list[int]:
        """Seed ``count`` pull requests into the issues list — GitHub's REST
        issues endpoint interleaves PRs (marked by a ``pull_request`` key), and
        the transport returns them raw (BKL-5T3J), so tests must be able to
        model a PR-bearing repo. Numbers come from the same counter as issues
        (real repos share one sequence). ``labels`` lets a test model the
        mislabeled-PR case (a prawduct-namespaced label on a PR)."""
        repo_state = self._repo(owner, repo)
        for name in labels or []:
            repo_state.labels.setdefault(name, {"name": name, "color": "ededed"})
        numbers: list[int] = []
        for _ in range(count):
            number = repo_state.next_number
            repo_state.next_number += 1
            repo_state.issues[number] = {
                "number": number,
                "node_id": f"PR_{owner}_{repo}_{number}",
                "title": f"PR #{number}",
                "body": "",
                "state": state,
                "state_reason": None,
                "labels": [dict(repo_state.labels[n]) for n in (labels or [])],
                "assignee": None,
                "assignees": [],
                "user": {"login": self.user["login"], "id": self.user["id"]},
                "pull_request": {
                    "url": f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
                },
                "html_url": f"https://github.com/{owner}/{repo}/pull/{number}",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
            numbers.append(number)
        return numbers

    def get_issue(self, owner: str, repo: str, number: int) -> dict:
        self._maybe_unreachable()
        self.calls.append(("get_issue", owner, repo, number))
        state = self._repo(owner, repo)
        issue = state.issues.get(number)
        if issue is None or self._replication_hidden(state, number):
            raise TransportError(
                "not_found",
                "the requested GitHub resource was not found",
                details={"operation": f"api repos/{owner}/{repo}/issues/{number}"},
            )
        return dict(issue)

    def list_issues(
        self,
        owner: str,
        repo: str,
        *,
        state: str = "open",
        labels: list[str] | None = None,
        assignee: str | None = None,
        sort: str = "created",
        direction: str = "asc",
        per_page: int = 100,
        page: int = 1,
    ) -> list[dict]:
        self._maybe_unreachable()
        self.calls.append(
            ("list_issues", owner, repo, state, tuple(labels or ()), assignee)
        )
        repo_state = self._repo(owner, repo)
        want_labels = set(labels or ())
        matched: list[dict] = []
        for issue in repo_state.issues.values():
            if state != "all" and (issue.get("state") or "open").lower() != state:
                continue
            names = {label["name"] for label in issue.get("labels", [])}
            if want_labels and not want_labels.issubset(names):
                continue
            if not self._assignee_matches(issue, assignee):
                continue
            if self._replication_hidden(repo_state, issue["number"]):
                continue  # still inside its post-create window
            matched.append(issue)
        key = "updated_at" if sort == "updated" else "created_at"
        matched.sort(
            key=lambda i: (i.get(key) or "", i["number"]),
            reverse=(direction == "desc"),
        )
        start = max(0, (page - 1) * per_page)
        return [dict(issue) for issue in matched[start : start + per_page]]

    @staticmethod
    def _assignee_matches(issue: dict, assignee: str | None) -> bool:
        logins = [a["login"] for a in issue.get("assignees", []) if a]
        if assignee is None:
            return True
        if assignee == "none":
            return not logins
        if assignee == "*":
            return bool(logins)
        return assignee in logins

    def list_labels(self, owner: str, repo: str) -> list[dict]:
        self._maybe_unreachable()
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
        old_state = issue.get("state")
        old_logins = [a["login"] for a in issue.get("assignees", []) if a]
        for key in ("title", "body", "state", "state_reason"):
            if key in fields:
                issue[key] = fields[key]
        # `assignees` is a set-replacing field on the issue PATCH (how claim takes
        # the assignee and its claimed_at stamp in one atomic write).
        if "assignees" in fields:
            logins = fields["assignees"] or []
            issue["assignees"] = [{"login": login, "id": 0} for login in logins]
            issue["assignee"] = issue["assignees"][0] if issue["assignees"] else None
        # GitHub clears `state_reason` when an issue is reopened.
        if fields.get("state") == "open":
            issue["state_reason"] = None
        self._stamp(state, issue)
        self._record_timeline(state, issue, number, old_state, old_logins)
        return dict(issue)

    def _record_timeline(
        self, state: _RepoState, issue: dict, number: int, old_state, old_logins: list
    ) -> None:
        """Append the native timeline events a state/assignee change produces — the
        minimal audit trail ``export`` serializes (MIG-3). Only the transitions the
        dump cares about (close/reopen/assign/unassign) are recorded."""
        events = state.timeline.setdefault(number, [])
        stamp = issue["updated_at"]
        new_state = issue.get("state")
        if new_state != old_state:
            events.append(
                {"event": "closed" if new_state == "closed" else "reopened",
                 "actor": self.user["login"], "created_at": stamp}
            )
        new_logins = [a["login"] for a in issue.get("assignees", []) if a]
        for login in new_logins:
            if login not in old_logins:
                events.append({"event": "assigned", "actor": login, "created_at": stamp})
        for login in old_logins:
            if login not in new_logins:
                events.append({"event": "unassigned", "actor": login, "created_at": stamp})

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

    # -- native relationships (dependencies + sub-issues) ------------------

    def list_blocked_by(self, owner: str, repo: str, number: int) -> list[dict]:
        self._maybe_unreachable()
        self.calls.append(("list_blocked_by", owner, repo, number))
        state = self._repo(owner, repo)
        out: list[dict] = []
        for b_owner, b_repo, b_number in sorted(state.blocked_by.get(number, set())):
            blocker = self._repo(b_owner, b_repo).issues.get(b_number)
            # A cross-repo blocker's state is read live (no cache to be stale).
            b_state = (blocker.get("state") if blocker else "open") or "open"
            out.append(
                {
                    "owner": b_owner,
                    "repo": b_repo,
                    "number": b_number,
                    "state": b_state.lower(),
                    "ref": f"{b_owner}/{b_repo}#{b_number}",
                }
            )
        return out

    def list_sub_issues(self, owner: str, repo: str, number: int) -> list[dict]:
        self._maybe_unreachable()
        self.calls.append(("list_sub_issues", owner, repo, number))
        state = self._repo(owner, repo)
        out: list[dict] = []
        for c_owner, c_repo, c_number in sorted(state.sub_issues.get(number, set())):
            out.append(
                {"owner": c_owner, "repo": c_repo, "number": c_number,
                 "ref": f"{c_owner}/{c_repo}#{c_number}"}
            )
        return out

    def list_timeline(self, owner: str, repo: str, number: int) -> list[dict]:
        self._maybe_unreachable()
        self.calls.append(("list_timeline", owner, repo, number))
        state = self._repo(owner, repo)
        if number not in state.issues:
            raise TransportError(
                "not_found",
                "the requested GitHub resource was not found",
                details={"operation": f"api repos/{owner}/{repo}/issues/{number}/timeline"},
            )
        return [dict(event) for event in state.timeline.get(number, [])]

    def add_blocked_by(
        self, owner: str, repo: str, number: int, *,
        blocker_owner: str, blocker_repo: str, blocker_number: int,
    ) -> None:
        self._check_fault()
        self.calls.append(("add_blocked_by", owner, repo, number, blocker_number))
        state = self._repo(owner, repo)
        self._require(state, owner, repo, number, "dependencies/blocked_by")
        state.blocked_by.setdefault(number, set()).add(
            (blocker_owner, blocker_repo, blocker_number)
        )

    def remove_blocked_by(
        self, owner: str, repo: str, number: int, *,
        blocker_owner: str, blocker_repo: str, blocker_number: int,
    ) -> None:
        self._check_fault()
        self.calls.append(("remove_blocked_by", owner, repo, number, blocker_number))
        state = self._repo(owner, repo)
        self._require(state, owner, repo, number, "dependencies/blocked_by")
        state.blocked_by.get(number, set()).discard(
            (blocker_owner, blocker_repo, blocker_number)
        )

    def add_sub_issue(
        self, owner: str, repo: str, number: int, *,
        child_owner: str, child_repo: str, child_number: int,
    ) -> None:
        self._check_fault()
        self.calls.append(("add_sub_issue", owner, repo, number, child_number))
        state = self._repo(owner, repo)
        self._require(state, owner, repo, number, "sub_issues")
        state.sub_issues.setdefault(number, set()).add(
            (child_owner, child_repo, child_number)
        )

    def remove_sub_issue(
        self, owner: str, repo: str, number: int, *,
        child_owner: str, child_repo: str, child_number: int,
    ) -> None:
        self._check_fault()
        self.calls.append(("remove_sub_issue", owner, repo, number, child_number))
        state = self._repo(owner, repo)
        self._require(state, owner, repo, number, "sub_issue")
        state.sub_issues.get(number, set()).discard(
            (child_owner, child_repo, child_number)
        )

    def _require(
        self, state: _RepoState, owner: str, repo: str, number: int, op: str
    ) -> dict:
        """Fetch issue ``number`` or raise the same ``not_found`` GitHub would."""
        issue = state.issues.get(number)
        if issue is None:
            raise TransportError(
                "not_found",
                "the requested GitHub resource was not found",
                details={"operation": f"api repos/{owner}/{repo}/issues/{number}/{op}"},
            )
        return issue
