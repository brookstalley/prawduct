"""Upstream filing — the exact bytes that cross the owner boundary.

``file-upstream`` is the one adapter operation that writes into a **foreign,
public** repo: prawduct's own tracker. Every other op targets the product's own
``backlog_service_repo``, where nothing crosses an owner boundary and GitHub
enforces access with the caller's own token. That asymmetry is why this surface
lives in its own module rather than beside the ordinary CRUD in :mod:`core`: the
guarantee here is not "the write succeeded", it is **which bytes leave and where
they go**, and both have to be inspectable *before* anything is sent.

Design: ``documentation/backlog-service-upstream-filing.md`` §2 (the payload) and
§5 (the adapter contract). ``documentation/backlog-service-api-contract.md`` §2.4
owns the ``source-key:`` idempotency contract this stamps.

**Preview by default.** Rendering a payload and its digest is side-effect-free,
touches no network, and is the whole of the first call; sending is a second,
digest-bearing call. A reviewer therefore approves the literal outbound bytes
rather than a summary of them, which is what makes "sent == previewed" a
checkable claim instead of an intention.

**Pure by construction, except twice.** Everything that shapes the payload is a
pure function of its arguments, so the exact-byte pin guarding this surface needs
no filesystem and no transport. The two impure reads are named, narrow and
injectable: the running plugin's version (:func:`plugin_version`) and the running
repo's own identity (:func:`resolve_self_identity`).

**The trimmed block is the minimization.** An in-repo ``prawduct:`` block carries
``provenance: {source: <product>, …}`` — the product's own name. Upstream carries
``v:``, ``found_in:`` and ``source-key:``, and nothing else. The product name is
precisely the field that must not cross (design §3).

Composing only three fields is **not** by itself enough to guarantee only three
arrive, and believing it was is how this shipped wrong once. The block is a fenced
span, and the parser reads from the *first* opener to the first closing fence — so
caller text that reaches the body ahead of the marker and opens an unterminated
```` ```prawduct ```` fence prepends its own fields and swallows the real ones. A
``--component`` of ``stop-hook\n```prawduct\nsource: acme/widget`` put exactly the
product-name field the trim exists to strip at the head of the parsed block. The
guarantee lives in :func:`check_payload_inputs`, which every composition runs — not
in the narrowness of the composer.

**No model, ever.** The recomposition that keeps product content out of the prose
(design §3, L1) is *model judgment in a decision*, and it lives in the
``/prawduct:report-bug`` skill. This module only frames what it is handed: it
sources the two deterministic sections (**Component**, **Found in**), appends the
marker, and audits budgets. It never invents or rewrites prose.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import encode, ids, issuefmt
from ..core import read_str_yaml_key

#: The canonical upstream repo, as a **plugin constant** — never a caller-supplied
#: ``--repo`` (design §5 check 2). Configurability is what would make the pin
#: meaningless: shape-validating an arbitrary ``owner/repo`` is not an owner
#: constraint, and "the target is whatever you passed" is not a guarantee anybody
#: can review. A fork of prawduct changes this line; a caller cannot.
PINNED_TARGET = "brookstalley/prawduct"

#: The title convention's lead-in (design §2). It is the **intake signal** the
#: receiving side keys off, and it is deliberately something a non-collaborator
#: can set — unlike a label, which they cannot (XP6), so the category cannot ride
#: in the label taxonomy and has to ride in the title.
TITLE_PREFIX = "[prawduct]"

#: ``v:`` in the trimmed provenance block — the block schema version, matching the
#: in-repo block's own (Data Model §7).
MARKER_VERSION = 1

#: What ``found_in:`` says when the plugin manifest cannot be read. The design is
#: explicit that this is **sourced, never recalled**: a model-recalled version
#: drifts silently as the plugin updates, and a wrong version on a bug report
#: sends triage to the wrong code. An honest "unknown" costs one triage question;
#: a confident wrong answer costs a wrong bisect.
VERSION_UNKNOWN = "(unknown)"

#: Lint rules a **label-less** filing can never satisfy, so reporting them would
#: train the reader to ignore the findings that matter. §2 files upstream issues
#: with no labels at all — a non-collaborator cannot apply them and consumers are
#: never coupled to prawduct's taxonomy — so "no kind:", "no area:" and the label
#: count are not defects here, they are the design.
_LABELLESS_RULES = frozenset({"no-kind", "no-area", "too-many-labels"})

#: ``owner/repo`` out of a GitHub remote URL — ``https://github.com/o/r.git``,
#: ``git@github.com:o/r.git`` and ``ssh://git@github.com/o/r``. The host is
#: matched rather than assumed: a GitLab or Bitbucket ``origin`` yielding a
#: "GitHub identity" would let the no-self-file check compare a real target
#: against a fabricated one. GitHub Enterprise hosts do not match and resolve as
#: no signal, which is the fail-closed direction.
#:
#: Matched over the WHOLE url with the host in host position — optional scheme,
#: optional userinfo, then `github.com` and nothing else before it. A prefix guard
#: is not enough and the difference is reachable: excluding an alphanumeric prefix
#: stops `notgithub.com/acme/repo`, but leaves `https://evil.example.com/github.com/o/r`
#: matching in *path* position, on a host the caller chooses. A lookalike host
#: resolving to a "GitHub identity" is the one input that could make the
#: no-self-file comparison compare the wrong thing.
_REMOTE_RE = re.compile(
    r"(?:[A-Za-z][A-Za-z0-9+.-]*://)?"      # scheme, or none for the scp-like form
    r"(?:[^/@\s]*@)?"                        # userinfo (`git@`), optional
    r"github\.com[:/](?P<owner>[^/:\s]+)/(?P<repo>[^/\s]+?)(?:\.git)?/?"
)

#: Minimal git-config reading: any section header, the `remote "origin"` one, and
#: a `url =` assignment. Deliberately not a general git-config parser — this reads
#: one value and every unhandled spelling resolves to "no signal", which composes
#: correctly with the other identity signal instead of guessing.
#: Git folds section names and keys to lowercase but preserves a subsection's
#: case, so `[Remote "origin"]` names the same remote and `[remote "Origin"]` does
#: not. Both halves of that rule are honored here: case-insensitive on `remote`
#: and on `url`, exact on `"origin"`. Handling only one half is what leaves a
#: valid config silently yielding no identity signal.
_SECTION_RE = re.compile(r"^\s*\[")
_ORIGIN_SECTION_RE = re.compile(r'^\s*\[\s*(?i:remote)\s+"origin"\s*\]')
_URL_RE = re.compile(r"^\s*url\s*=\s*(.+?)\s*$", re.IGNORECASE)


# --- the two impure reads ----------------------------------------------------


def plugin_version(plugin_root: Path | None = None) -> str:
    """The running plugin's semver from the bundled manifest, or :data:`VERSION_UNKNOWN`.

    Reads the same ``.claude-plugin/plugin.json`` that ``prawduct-hook version``
    reads, at call time, so the two cannot disagree about which plugin is running.
    Every failure mode collapses to the honest sentinel rather than a guess: a
    missing file, an undecodable one, malformed JSON, or a manifest carrying no
    version.
    """
    root = Path(plugin_root) if plugin_root is not None else Path(__file__).resolve().parents[2]
    try:
        raw = (root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, UnicodeDecodeError, ValueError):
        return VERSION_UNKNOWN
    version = data.get("version") if isinstance(data, dict) else None
    return str(version) if version else VERSION_UNKNOWN


def resolve_self_identity(project_dir) -> tuple[str, ...]:
    """Every ``owner/repo`` the **running repo** answers to, in resolution order.

    Two signals, because either alone is fail-open in the state that matters most.
    ``backlog_service_repo`` is unset in every pre-cutover repo, so an identity
    keyed on it alone is inert exactly where the guarantee is needed; the ``origin``
    remote is absent in a bare or template checkout. Resolving both and treating
    *either* match as this repo is what makes the no-self-file comparison live
    without waiting on a migration.

    Returns the identities that resolved, deduplicated, ``backlog_service_repo``
    first — empty when neither resolves, which callers enforcing the invariant
    must read as a refusal rather than a pass.
    """
    directory = Path(project_dir)
    configured = read_str_yaml_key(
        directory / ".prawduct" / "project-state.yaml", "backlog_service_repo"
    )
    resolved: list[str] = []
    for candidate in (configured, _origin_repo(directory)):
        spec = canonical_repo(candidate)
        if spec is None or spec in resolved:
            continue
        resolved.append(spec)
    return tuple(resolved)


def canonical_repo(spec: str | None) -> str | None:
    """``owner/repo`` in one comparable spelling, or ``None`` if it is not one.

    Case-folded, because **GitHub owner and repo names are case-insensitive** and
    the comparisons built on this are not opinions about spelling: two spellings
    of one repo must produce one ``source-key:`` so a retry collapses, and — the
    sharper one — the no-self-file check must refuse ``BrooksTalley/Prawduct`` as
    readily as the lowercase form. A case-sensitive compare there is fail-open,
    and it is fail-open on an input the caller picks.
    """
    parsed = ids.parse_repo(spec) if spec else None
    return f"{parsed[0].lower()}/{parsed[1].lower()}" if parsed else None


def submitter_identity(project_dir) -> str:
    """The ``source-key:`` submitter component: the first resolved identity, or ``""``.

    The key's job is to let *one submitter's* retry collapse onto the issue it
    already filed, so it has to name the filer — but the filer's name is exactly
    what minimization forbids sending, which is why it crosses only as one input
    to a one-way digest (design §2). An unresolved identity keys as the empty
    string rather than refusing: preview is a pure rendering, and a payload that
    could never be sent is caught at *send*, where the no-self-file check fails
    closed on the same empty tuple.
    """
    identities = resolve_self_identity(project_dir)
    return identities[0] if identities else ""


def _origin_repo(directory: Path) -> str | None:
    """``owner/repo`` from this checkout's ``origin`` remote, or ``None``.

    Read out of ``.git/config`` rather than by shelling out to ``git remote
    get-url``, because ``transport.py`` owns the package's only subprocess: the
    egress discipline is what makes "the adapter reaches the network in exactly
    one place" checkable, and it is not worth spending on a value that is sitting
    in a config file. Every failure — no repo, no ``origin``, a non-GitHub URL,
    an unreadable file — resolves to "no signal", which the caller composes with
    the other signal rather than treating as an answer.
    """
    config = _git_config_path(directory)
    if config is None:
        return None
    try:
        lines = config.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    in_origin = False
    for line in lines:
        if _SECTION_RE.match(line):
            in_origin = bool(_ORIGIN_SECTION_RE.match(line))
            continue
        if in_origin:
            match = _URL_RE.match(line)
            if match:
                return parse_remote_url(match.group(1))
    return None


def _git_config_path(directory: Path) -> Path | None:
    """The config file for the checkout containing ``directory``, or ``None``.

    Walks up the way ``git -C`` does, and handles the linked-worktree form: there
    ``.git`` is a *file* pointing at the worktree's own gitdir, whose ``commondir``
    points at the clone's shared directory — and the remotes live in the shared
    one. Resolving only the plain ``.git``-directory case would leave every agent
    worktree with no identity signal at all, which is exactly where a fail-closed
    check turns into a refusal nobody can explain.
    """
    for candidate in (directory, *directory.parents):
        dot_git = candidate / ".git"
        if dot_git.is_dir():
            return dot_git / "config"
        if not dot_git.is_file():
            continue
        try:
            pointer = dot_git.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            return None
        if not pointer.startswith("gitdir:"):
            return None
        gitdir = Path(pointer.split(":", 1)[1].strip())
        if not gitdir.is_absolute():
            gitdir = (candidate / gitdir).resolve()
        commondir = gitdir / "commondir"
        if commondir.is_file():
            try:
                gitdir = (gitdir / commondir.read_text(encoding="utf-8").strip()).resolve()
            except (OSError, UnicodeDecodeError):
                return None
        return gitdir / "config"
    return None


def parse_remote_url(url: str) -> str | None:
    """``owner/repo`` from a GitHub remote URL, or ``None``. Pure.

    Matched against the whole url rather than searched within it — a search finds
    ``github.com/o/r`` wherever it sits, including in the path of a host somebody
    else controls.
    """
    match = _REMOTE_RE.fullmatch((url or "").strip())
    return f"{match.group('owner')}/{match.group('repo')}" if match else None


# --- the payload (design §2) -------------------------------------------------


def render_title(component: str, symptom: str) -> str:
    """``[prawduct] <component>: <symptom>`` — the §2 title convention.

    A component is not required to render a title; omitting it drops the
    ``component:`` segment rather than emitting an empty one, so a report filed
    without a surface still carries the intake prefix that makes it findable.
    """
    component = (component or "").strip().rstrip(":")
    symptom = (symptom or "").strip()
    if component:
        return f"{TITLE_PREFIX} {component}: {symptom}"
    return f"{TITLE_PREFIX} {symptom}"


def render_report(*, component: str, found_in: str, body: str) -> str:
    """The human half of the body: the two sourced sections, then the authored ones.

    **Component** and **Found in** are the only sections this module composes,
    because they are the only two it can *source* — the rest is L1-recomposed
    prose the caller hands over verbatim. Emitting them here rather than asking
    the caller for them is what makes "``found_in`` is read, never recalled" true
    of every filing instead of true of a careful one.
    """
    blocks: list[str] = []
    component = (component or "").strip()
    if component:
        blocks.append(f"### Component\n\n{component}")
    blocks.append(f"### Found in\n\n{version_label(found_in)}")
    body = (body or "").strip()
    if body:
        blocks.append(body)
    return "\n\n".join(blocks)


def version_label(found_in: str) -> str:
    """``prawduct v3.4.0 (plugin)`` — or an unadorned ``(unknown)`` sentinel.

    The ``v`` prefix belongs to a real version only; ``prawduct v(unknown)``
    reads like a version string and invites someone to treat it as one.
    """
    if found_in == VERSION_UNKNOWN:
        return f"prawduct {VERSION_UNKNOWN} (plugin)"
    return f"prawduct v{found_in} (plugin)"


def source_key(*, submitter: str, title: str, body: str) -> str:
    """The api-contract §2.4 idempotency key: ``sha256:<hex>``.

    A digest of *(submitter identity, title + body)*. A re-file with the same key
    returns the existing upstream issue instead of duplicating it, which is what
    makes a retried filing safe. The inputs are NUL-separated so no two different
    triples can concatenate to the same bytes — without the separator,
    ``("ab", "c", …)`` and ``("a", "bc", …)`` collide, and two distinct reports
    that collide are one report silently lost.
    """
    digest = hashlib.sha256()
    for part in (submitter, title, body):
        digest.update((part or "").encode("utf-8"))
        digest.update(b"\x00")
    return f"sha256:{digest.hexdigest()}"


def marker_block(*, found_in: str, key: str) -> str:
    """The trimmed ``prawduct:`` provenance block — three fields, by construction.

    Framed through :func:`encode.serialize_block` so the upstream block and the
    in-repo one cannot drift into two fence formats; what differs is the *fields*,
    which is the whole minimization and is fixed here rather than filtered from a
    larger dict somewhere upstream.
    """
    return encode.serialize_block(
        {"v": str(MARKER_VERSION), "found_in": found_in, "source-key": key}
    )


def check_payload_inputs(*, title: str, body: str, component: str) -> str | None:
    """The first thing wrong with these inputs, or ``None``. Pure.

    Every caller-supplied string that reaches the outbound body is checked here,
    in the module that owns the bytes, rather than at one call site — a guard the
    CLI applied to ``--body`` alone left ``--component`` free to forge the whole
    provenance block, and a second entry point would have inherited the same gap.

    Two rules. **No prawduct fence** in anything that lands in the body: the
    injection route :func:`marker_block`'s framing cannot defend against, closed
    the way ``file`` closes it on its own body — by refusing, never by escaping,
    because a rewrite rule has to be exactly as clever as every future attacker.
    **One line** for the title and the component: both are structural fields of
    the §2 convention rather than prose, an issue title is single-line anyway, and
    forbidding the newline is what stops a value from reaching column 0 of the
    body at all — a strictly narrower thing to check than what it can spell there.
    """
    for label, value in (("--title", title), ("--component", component)):
        if "\n" in (value or "") or "\r" in (value or ""):
            return f"{label} must be a single line"
    for value in (body, component):
        problem = encode.check_body_text(value)
        if problem:
            return problem
    return None


def build_payload(
    *,
    title: str,
    body: str,
    component: str = "",
    found_in: str,
    submitter: str,
    target: str = PINNED_TARGET,
) -> dict | None:
    """The complete outbound payload: ``{repo, title, body, labels}``.

    ``None`` when :func:`check_payload_inputs` rejects the inputs. The composer
    re-runs that check rather than documenting it as a precondition, because a
    precondition a caller can skip is exactly what let ``--component`` through:
    the claim "only three fields can reach the block" has to be enforced where the
    block is built, not asserted next to it.

    ``labels`` is empty and stays empty (§2): the issue lands label-less, and
    prawduct-side triage applies the taxonomy from the intake set. A
    non-collaborator filer cannot set labels at all, so a payload that carried
    them would work for the dogfood case and fail for the case the design exists
    to serve.
    """
    if check_payload_inputs(title=title, body=body, component=component) is not None:
        return None
    rendered_title = render_title(component, title)
    report = render_report(component=component, found_in=found_in, body=body)
    key = source_key(submitter=submitter, title=rendered_title, body=report)
    marker = marker_block(found_in=found_in, key=key)
    return {
        "repo": target,
        "title": rendered_title,
        "body": f"{report}\n\n{marker}",
        "labels": [],
    }


def render_preview(
    project_dir, *, title: str, body: str, component: str = ""
) -> tuple[dict, str] | None:
    """``(payload, digest)`` composed from the running repo, or ``None`` on bad input.

    **The one recipe.** Design §5 check 4 re-renders the payload at send and
    refuses unless the digest equals the caller's ``--approve`` — so preview and
    send must compose from identical ingredients, assembled identically. Leaving
    that assembly at the CLI call site means the send arm re-types it, and any
    divergence at all makes every ``ask-user`` filing refuse with
    ``approval-mismatch``, which reads to the operator as their own mistake rather
    than as two spellings of one recipe. Both arms call this.
    """
    payload = build_payload(
        title=title,
        body=body,
        component=component,
        found_in=plugin_version(),
        submitter=submitter_identity(project_dir),
    )
    if payload is None:
        return None
    return payload, payload_digest(payload)


def canonical_bytes(payload: dict) -> bytes:
    """The exact bytes the digest covers: the whole payload, canonically encoded.

    Sorted keys and no whitespace, so two renderings of the same payload are
    byte-identical and any difference at all — a changed target, a changed label
    list, one character of body — changes the digest. Digesting the body alone
    would let an approved payload be sent to a different repo.
    """
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def payload_digest(payload: dict) -> str:
    """``sha256:<hex>`` over :func:`canonical_bytes` — the approval token's value."""
    return f"sha256:{hashlib.sha256(canonical_bytes(payload)).hexdigest()}"


def lint_payload(title: str, body: str) -> list[issuefmt.LintFinding]:
    """Budget and quality findings for an outbound payload — advisory, never truncating.

    The issue standard's own thresholds, reused rather than restated, so the ~175
    visible-word ceiling this design leans on has one home. Reported instead of
    enforced because silently truncating an outbound bug report is the one failure
    mode nobody can see: the reviewer approves bytes that then get cut. The label
    rules are dropped for the reason :data:`_LABELLESS_RULES` records.
    """
    return [f for f in issuefmt.lint(title, body) if f.rule not in _LABELLESS_RULES]
