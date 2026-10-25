"""Evidence transport between clones — moving ``refs/notes/prawduct`` (#1052).

:mod:`evidence_notes` writes transported facts onto the notes ref and reads them
back, inside one clone. This module moves the ref to and from the product's own
remote, and sets a clone up so ordinary git carries it:

- :func:`sync` — fetch the remote's notes into a tracking ref
  (``refs/notes/<remote>/prawduct``), merge them into the local ref by
  ``cat_sort_uniq``, attach any of this branch's stored facts whose note is
  missing, ingest the records the store lacks, push the local ref, and move
  the tracking ref to what was pushed.
- :func:`configure` — add the notes refspec (a pattern, :func:`refspec`) to
  ``remote.<remote>.fetch`` and ``refs/notes/prawduct`` to
  ``notes.rewriteRef``, so a plain ``git fetch`` carries the notes and an
  amend or rebase carries them to the rewritten commit; an exact notes
  refspec an earlier version wrote is replaced. Preview by default;
  ``apply=True`` writes the clone's own ``.git/config``.

**Why a tracking ref.** Fetching straight into the local ref would need a
forced update and would drop notes written here and not yet pushed. The
tracking ref takes the remote's state as it is; the merge combines; the push
is then a fast-forward. **Why ``cat_sort_uniq``.** Records are deduplicated by
``(kind, id)`` on ingest either way, so any line-union merge is correct; this
one never conflicts and also drops the blank separator lines
``git notes append`` inserts.

**Network.** :func:`sync`'s fetch and push are the only calls here that reach
a remote, and they reach the product's own — the one a bare ``git push``
would (``gitstate.push_remote``). Nothing runs unless a person or the agent
runs the command; the PR skill's push step is where it is meant to run. Every
git call goes through :func:`evidence.run_git` (its network legs take the
network timeout floor), with ``GIT_TERMINAL_PROMPT=0`` so a credential prompt
fails instead of waiting out the budget, and ``LC_ALL=C`` so the messages a
person is shown read the same everywhere. A remote with no notes yet — the
normal state before a first push — is not an error: the fetch refspec is a
pattern, which matches nothing there. git's own message is echoed only after
the credential denylist (``backlog.transport.scrub_secrets``) has run over it.

**Failure.** The first failing step stops the run and is named in ``step``;
nothing is retried. A notes merge left unfinished by an earlier run or by
hand is the person's to finish or abort — it is reported, not touched.

Errors are return values, never raises (``project-preferences``).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from . import evidence, evidence_notes, gitstate

NOTES_REF = evidence_notes.NOTES_REF
REWRITE_KEY = "notes.rewriteRef"

_SYNC_USAGE = "Usage: prawduct-hook evidence sync [--no-push] [--json]"
_CONFIGURE_USAGE = "Usage: prawduct-hook evidence configure [--apply] [--json]"

tracking_ref = evidence_notes.tracking_ref


def refspec(remote: str) -> str:
    """The fetch refspec that carries the remote's notes into the tracking ref:
    ``+refs/notes/prawduct*:refs/notes/<remote>/prawduct*``.

    A pattern, not the exact ``+refs/notes/prawduct:…``. git resolves a
    configured exact refspec as a ref that must exist, so while the remote has
    no notes — every fresh onboard, until some clone first pushes — a plain
    ``git fetch`` or ``git pull`` dies with ``couldn't find remote ref``; a
    pattern that matches nothing is not an error (probed on git 2.54). The
    pattern also carries any ``refs/notes/prawduct<suffix>`` to
    ``refs/notes/<remote>/prawduct<suffix>``, which
    :func:`evidence_notes.is_notes_ref` does not count as the transport."""
    return f"+{NOTES_REF}*:{tracking_ref(remote)}*"


def _legacy_refspec(remote: str) -> str:
    """The exact refspec an earlier ``configure`` wrote; :func:`configure`
    replaces it, because left beside the pattern it still breaks a plain
    fetch while the remote has no notes."""
    return f"+{NOTES_REF}:{tracking_ref(remote)}"


def _git(project_dir: Path, *args: str) -> "tuple[int, str]":
    """``(returncode, detail)`` for one git call; ``detail`` is git's stderr
    (else stdout), scrubbed of credential shapes, because a remote's URL or its
    server-side hooks can put a token in it and the detail reaches stdout and
    the ``--json`` payload."""
    from .backlog.transport import scrub_secrets  # noqa: PLC0415 — the one credential denylist

    env = {**os.environ, "LC_ALL": "C", "GIT_TERMINAL_PROMPT": "0"}
    rc, out, err = evidence.run_git(project_dir, *args, env=env)
    return rc, scrub_secrets((err or out).strip())


def _ere_literal(value: str) -> str:
    """A POSIX extended regex matching exactly ``value`` — the value pattern
    ``git config --unset-all`` takes. Escaped by hand rather than with
    ``--fixed-value``, which git gained only in 2.30."""
    return "^" + "".join("\\" + ch if ch in ".[]()*+?{}|^$\\" else ch for ch in value) + "$"


def _remote(project_dir: Path) -> "tuple[str | None, str | None]":
    """``(remote, None)`` — the remote a bare ``git push`` reaches — or
    ``(None, reason)`` when the clone has none (or it cannot be read)."""
    rc, out, err = evidence.run_git(project_dir, "remote")
    if rc != 0:
        return None, f"cannot list the clone's remotes ({err or rc})"
    remotes = [line.strip() for line in out.splitlines() if line.strip()]
    if not remotes:
        return None, "no remote configured — notes have nowhere to travel"
    remote = gitstate.push_remote(project_dir)
    if remote not in remotes or remote.startswith("-"):
        return None, f"the push remote {remote!r} is not one of this clone's remotes"
    return remote, None


def _has_ref(project_dir: Path, ref: str) -> bool:
    rc, _out, _err = evidence.run_git(project_dir, "rev-parse", "-q", "--verify", ref)
    return rc == 0


def _unfinished_merge(project_dir: Path) -> "tuple[str | None, str | None]":
    """Whether a notes merge was left in progress. git does not refuse a new
    merge over one, so the check is ours.

    ``(path, None)`` when the merge-state path ``NOTES_MERGE_REF`` or
    ``NOTES_MERGE_WORKTREE`` exists — that path; ``(None, None)`` when neither
    does; ``(None, reason)`` when git could not say where they live, which
    tells nothing about a merge either way."""
    rc, out, err = evidence.run_git(
        project_dir, "rev-parse", "--git-path", "NOTES_MERGE_REF",
        "--git-path", "NOTES_MERGE_WORKTREE",
    )
    if rc != 0:
        return None, f"{err or rc}"
    for line in out.splitlines():
        path = Path(line) if Path(line).is_absolute() else Path(project_dir) / line
        if path.exists():
            return line, None
    return None, None


def sync(project_dir: Path, *, push: bool = True) -> dict:
    """Fetch, merge, reconcile, ingest and (unless ``push=False``) push the
    notes ref against the clone's push remote.

    Returns ``{"status": "ok"|"error", "step": "fetch"|"merge"|"reconcile"|
    "ingest"|"push"|None, "pushed": bool, "ingested": int, "reconciled": int,
    "reason"}``. ``step`` names the step that failed (``None`` on success);
    ``ingested`` counts records appended to the store, ``reconciled`` facts
    attached to a note they were missing from. No remote is ``ok`` with the
    reason and nothing done.
    """
    result = {"status": "ok", "step": None, "pushed": False, "ingested": 0,
              "reconciled": 0, "reason": None}

    def failed(step: str, reason: str) -> dict:
        return {**result, "status": "error", "step": step, "reason": reason}

    remote, why = _remote(project_dir)
    if remote is None:
        return {**result, "reason": why}
    tracking = tracking_ref(remote)
    notes: list[str] = []

    # The pattern refspec: a remote with no notes yet fetches nothing, rc 0.
    rc, detail = _git(project_dir, "fetch", "--quiet", remote, refspec(remote))
    if rc != 0:
        return failed("fetch", f"git fetch {remote} failed: {detail or rc}")

    stuck, unknown = _unfinished_merge(project_dir)
    if unknown is not None:
        return failed(
            "merge",
            "cannot tell whether a notes merge is in progress — git could not answer "
            f"`rev-parse --git-path NOTES_MERGE_REF` ({unknown}); nothing was merged",
        )
    if stuck is not None:
        return failed(
            "merge",
            f"a notes merge is unfinished — {stuck} exists — finish it with "
            f"`git notes --ref {NOTES_REF} merge --commit`, or discard it with "
            f"`git notes --ref {NOTES_REF} merge --abort`, then sync again",
        )
    if not _has_ref(project_dir, tracking):
        notes.append(f"{remote} has no notes yet")
    else:
        rc, detail = _git(
            project_dir, "notes", "--ref", NOTES_REF, "merge", "-q", "-s", "cat_sort_uniq", tracking
        )
        if rc != 0:
            return failed("merge", f"git notes merge of {tracking} failed: {detail or rc}")

    known = evidence.read_facts(project_dir)
    reconciled = evidence_notes.reconcile(project_dir, known=known)
    if reconciled["status"] == "error":
        return failed("reconcile", reconciled["reason"])
    result["reconciled"] = reconciled["attached"]
    if reconciled["status"] == "unbounded":
        notes.append(f"nothing reconciled: {reconciled['reason']}")

    ingested = evidence_notes.ingest(project_dir, known=known)
    if ingested["status"] != "ok":
        return failed("ingest", ingested["reason"])
    result["ingested"] = ingested["appended"]
    if ingested["reason"]:
        notes.append(ingested["reason"])

    if push:
        if not _has_ref(project_dir, NOTES_REF):
            notes.append("no notes in this clone to push")
        else:
            rc, detail = _git(project_dir, "push", "--quiet", remote, NOTES_REF)
            if rc != 0:
                return failed(
                    "push",
                    f"git push {remote} {NOTES_REF} was refused — the local ref is "
                    f"unchanged: {detail or rc}",
                )
            result["pushed"] = True
            # The remote now holds the local ref. git moves the tracking ref
            # itself only where `configure` set the fetch refspec; set it here
            # too, so `evidence status`'s unpushed count (local against
            # tracking) reads 0 in an unconfigured clone as well. Local only.
            rc, detail = _git(project_dir, "update-ref", tracking, NOTES_REF)
            if rc != 0:
                notes.append(f"pushed, but {tracking} was not moved to match ({detail or rc})")
    result["reason"] = "; ".join(notes) or None
    return result


def configure(project_dir: Path, *, apply: bool) -> dict:
    """Add the notes refspec to ``remote.<remote>.fetch`` and
    ``refs/notes/prawduct`` to ``notes.rewriteRef`` where either is absent, and
    replace the exact notes refspec an earlier ``configure`` wrote.

    Returns ``{"status": "ok"|"error", "changes": [{"key", "value",
    "replaces"}, ...], "applied": bool, "reason"}``. ``changes`` lists what is
    (or was) missing or replaced — ``replaces`` is the line removed, else
    ``None``; ``applied`` is true only when ``apply`` wrote at least one of
    them. Both keys are multi-valued: a value the clone holds that is not the
    legacy notes refspec — another rewrite ref, the branch refspec — is never
    touched, and the pattern is added once. No remote is ``ok`` with the
    reason and nothing to do.
    """
    remote, why = _remote(project_dir)
    if remote is None:
        return {"status": "ok", "changes": [], "applied": False, "reason": why}
    wanted = [
        (f"remote.{remote}.fetch", refspec(remote), _legacy_refspec(remote)),
        (REWRITE_KEY, NOTES_REF, None),
    ]
    changes = []
    for key, value, legacy in wanted:
        rc, out, err = evidence.run_git(project_dir, "config", "--get-all", key)
        if rc not in (0, 1):  # 1 is git's "key not set"
            return {"status": "error", "changes": [], "applied": False,
                    "reason": f"cannot read {key} ({err or rc})"}
        held = out.splitlines()
        replaces = legacy if legacy is not None and legacy in held else None
        if value not in held or replaces is not None:
            changes.append({"key": key, "value": value, "replaces": replaces,
                            "add": value not in held})
    if not changes:
        return {"status": "ok", "changes": [], "applied": False,
                "reason": "already configured"}
    public = [{k: c[k] for k in ("key", "value", "replaces")} for c in changes]
    if not apply:
        return {"status": "ok", "changes": public, "applied": False, "reason": None}
    wrote = False
    for change in changes:
        steps = []
        if change["replaces"] is not None:
            steps.append(("--unset-all", change["key"], _ere_literal(change["replaces"])))
        if change["add"]:
            steps.append(("--add", change["key"], change["value"]))
        for step in steps:
            rc, detail = _git(project_dir, "config", *step)
            if rc != 0:
                return {"status": "error", "changes": public, "applied": wrote,
                        "reason": f"git config {step[0]} {change['key']} failed: {detail or rc}"}
            wrote = True
    return {"status": "ok", "changes": public, "applied": True, "reason": None}


# ---------------------------------------------------------------------------
# Hook-facing commands: 0 ok, 1 a reported failure, 2 usage
# ---------------------------------------------------------------------------


def _flags(args: "list[str]", allowed: "tuple[str, ...]", usage: str, name: str) -> "set[str] | None":
    unknown = [a for a in args if a not in allowed]
    if unknown:
        print(f"evidence {name}: unexpected argument {unknown[0]!r}\n{usage}", file=sys.stderr)
        return None
    return set(args)


def cmd_evidence_sync(project_dir: Path, args: "list[str]") -> int:
    """``prawduct-hook evidence sync [--no-push] [--json]``."""
    flags = _flags(args, ("--no-push", "--json"), _SYNC_USAGE, "sync")
    if flags is None:
        return 2
    result = sync(project_dir, push="--no-push" not in flags)
    if "--json" in flags:
        print(json.dumps(result, sort_keys=True))
    elif result["status"] != "ok":
        print(f"evidence sync: failed at {result['step']} — {result['reason']}", file=sys.stderr)
    else:
        sent = "pushed" if result["pushed"] else "not pushed"
        print(
            f"evidence sync: reconciled {result['reconciled']}, ingested "
            f"{result['ingested']}, notes {sent}"
        )
        if result["reason"]:
            print(f"  {result['reason']}")
    return 0 if result["status"] == "ok" else 1


def cmd_evidence_configure(project_dir: Path, args: "list[str]") -> int:
    """``prawduct-hook evidence configure [--apply] [--json]`` — preview unless
    ``--apply``."""
    flags = _flags(args, ("--apply", "--json"), _CONFIGURE_USAGE, "configure")
    if flags is None:
        return 2
    apply = "--apply" in flags
    result = configure(project_dir, apply=apply)
    if "--json" in flags:
        print(json.dumps(result, sort_keys=True))
    elif result["status"] != "ok":
        print(f"evidence configure: {result['reason']}", file=sys.stderr)
    elif not result["changes"]:
        print(f"evidence configure: nothing to change — {result['reason']}")
    else:
        done = result["applied"]
        for change in result["changes"]:
            if change.get("replaces"):
                verb = "replaced" if done else "would replace"
                print(f"evidence configure: {verb} {change['key']} {change['replaces']} "
                      f"with {change['value']}")
            else:
                verb = "added" if done else "would add"
                print(f"evidence configure: {verb} {change['key']} {change['value']}")
        if not apply:
            print("  re-run with --apply to write them to this clone's .git/config")
    return 0 if result["status"] == "ok" else 1
