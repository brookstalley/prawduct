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

**Composition is pure; only the send arm is not.** Everything that shapes the
payload is a pure function of its arguments, so the exact-byte pin guarding this
surface needs no filesystem and no transport. Three narrow reads sit outside that:
the running plugin's version (:func:`plugin_version`), the running repo's own
identity (:func:`resolve_self_identity`), and the consent preference
(:func:`read_filing_preference`). Each is its own function with its own fallback,
because they fail in different directions and a shared "read the repo" helper
would give them one.

**The seam is reached from exactly one function.** :func:`send` is where the five
§5 checks are composed and the only place this module calls the transport; the
five checks themselves (:func:`check_preference` and its siblings) are pure
predicates over already-resolved inputs, which is what lets each be falsified on
its own rather than only in company.

**The trimmed block is the minimization.** An in-repo ``prawduct:`` block carries
``provenance: {source: <product>, …}`` — the product's own name. Upstream carries
``v:``, ``found_in:`` and ``source-key:``, and nothing else. The product name is
precisely the field that must not cross (design §2, which fixes the outbound field list).

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
from typing import NamedTuple

from . import core, encode, ids, issuefmt, transport as tx
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

    Two rules. **No prawduct fence at all** in anything that lands in the body —
    terminated or not, which is STRICTER than ``file``'s rule on its own body and
    deliberately so. ``file`` tolerates a well-formed block because
    ``encode.compose_body`` strips and merges it; guard and transform are one
    mechanism. :func:`render_report` appends the body verbatim and
    :func:`build_payload` then adds the real block, so a terminated fence would
    cross the owner boundary as a SECOND parseable block and the receiving side's
    first ``merge_all_block_fields`` would fold its fields into the canonical one
    permanently. Closed by refusing, never by escaping, because a rewrite rule has
    to be exactly as clever as every future attacker; a report that needs to SHOW
    a block indents it, exactly as in-repo.
    **One line** for the title and the component: both are structural fields of
    the §2 convention rather than prose, an issue title is single-line anyway, and
    forbidding the newline is what stops a value from reaching column 0 of the
    body at all — a strictly narrower thing to check than what it can spell there.
    **Something in the title and the body.** The skill composes both through
    ``$(cat <path>)``, and a path the reader did not actually hold reads as nothing
    — the flag is present, so a presence check passes, and the ``[prawduct]``
    prefix alone clears the title floor. Under ``always-file`` nothing later
    compares bytes, so the empty payload would file as an issue that cannot be
    retitled or deleted. Refused here, where every composition runs, rather than
    in the skill prose that first noticed it. The component may be empty: it is
    optional by signature, and an absent component is a legitimate report.
    """
    for label, value in (("--title", title), ("--body", body)):
        if not (value or "").strip():
            return (
                f"{label} is empty — a `$(cat …)` over a path that was never written "
                "reads as nothing, and an empty issue cannot be retitled or deleted upstream"
            )
    for label, value in (("--title", title), ("--component", component)):
        if "\n" in (value or "") or "\r" in (value or ""):
            return f"{label} must be a single line"
    for value in (body, component):
        problem = encode.check_body_text_strict(value)
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


# --- the consent preference (design §4.1) ------------------------------------

#: The three consent states, design §4.1. ``ask-user`` is the default, and the
#: default is where a product lands whenever the row is absent, empty or spelled
#: wrong — three cases a hand-edited seam produces routinely. It therefore has to
#: mean "ask" and never "always", which is the one direction in which guessing
#: files something nobody approved. ``templates/project-preferences.md`` ships
#: the row reading ``ask-user`` for the same reason: what an onboarded product
#: has authored and what it would fall back to agree, so an operator who deletes
#: the row changes nothing.
PREF_ASK_USER = "ask-user"
PREF_NEVER_FILE = "never-file"
PREF_ALWAYS_FILE = "always-file"
FILING_PREFERENCE_STATES = (PREF_ASK_USER, PREF_NEVER_FILE, PREF_ALWAYS_FILE)

#: Not an authored value — the state of a preferences file that EXISTS and cannot
#: be read. Deliberately outside :data:`FILING_PREFERENCE_STATES`, which is the set
#: of things an operator can write in the row.
#:
#: It refuses rather than defaulting, and the asymmetry with the absent-file and
#: unrecognised-value branches is the whole point: those two know the row does not
#: say ``never-file``, and this one knows nothing at all. §4.3 calls ``never-file``
#: a hard mechanical guarantee, and "authority fails closed" (architecture §
#: Direction) is the posture for a check that cannot read its own input — the
#: alternative enforces the guarantee by hoping the operator reads a warning that,
#: on the send arm, rides out on the SUCCESS envelope after an irreversible
#: cross-owner write.
PREF_UNREADABLE = "unreadable"

#: The ``project-preferences.md`` row this reads, as the row spells itself.
FILING_PREFERENCE_LABEL = "Upstream filing"

#: The bullet form every Workflow preference in ``templates/project-preferences.md``
#: uses — ``- **Name**: value (default: … )`` — matched over the whole file. The
#: trailing parenthetical is guidance for the human, so the value is everything
#: ahead of the first ``(``.
_PREFERENCE_RE = re.compile(
    rf"^[ \t]*[-*][ \t]*\*\*[ \t]*{re.escape(FILING_PREFERENCE_LABEL)}[ \t]*\*\*[ \t]*:"
    r"(?P<value>.*)$",
    re.IGNORECASE | re.MULTILINE,
)


def read_filing_preference(project_dir) -> tuple[str, str | None]:
    """``(state, warning)`` — the §4.1 consent state, plus any reason it is not the row's.

    Defaults to :data:`PREF_ASK_USER` where the row is knowably not ``never-file``:
    no preferences file, no row, or a value nobody defined. That default is the
    strictest state a caller can land in by accident — it still requires an
    ``--approve`` whose digest matches the re-rendered bytes — whereas defaulting
    toward ``always-file`` would turn a typo into standing consent. A *recognised*
    ``never-file`` is stricter still, but reaching it by mistake would refuse an
    author's legitimate report on a misspelling, so it is honored only when it is
    what the row actually says.

    **A file that exists and cannot be READ is the one branch that does not
    default** — it returns :data:`PREF_UNREADABLE`, which :func:`check_preference`
    refuses. It is a different question from the other three: they establish that
    the row does not say ``never-file``, and this one establishes nothing. Since
    §4.3 makes ``never-file`` a hard mechanical guarantee, a permissions or
    encoding failure that downgraded it to ``ask-user`` would let a matching digest
    file the very report the standing "no" forbade, with the warning as the only
    thing standing in the way — and on the send arm that warning rides out on the
    SUCCESS envelope, after the irreversible write.

    The warning is non-empty whenever the operator could believe they have set
    something and have not: a row that does not parse, and a file that cannot be
    read. An **absent** file is the genuinely ordinary case and stays silent: it
    resolves to the same state the shipped row names, so a repo predating the row
    — or an operator who deleted it — has nothing to be told.
    """
    path = Path(project_dir) / ".prawduct" / "artifacts" / "project-preferences.md"
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return PREF_ASK_USER, None
    except (OSError, UnicodeDecodeError) as exc:
        return PREF_UNREADABLE, (
            f"project-preferences.md exists but could not be read ({exc}), so "
            f"`{FILING_PREFERENCE_LABEL}` could not be consulted — filing is "
            f"refused rather than assumed, because a row reading {PREF_NEVER_FILE} "
            "and a row nobody can read are indistinguishable from here"
        )
    match = _PREFERENCE_RE.search(text)
    if match is None:
        return PREF_ASK_USER, None
    raw = match.group("value").split("(", 1)[0].strip().strip("`").lower()
    if raw in FILING_PREFERENCE_STATES:
        return raw, None
    return PREF_ASK_USER, (
        f"`{FILING_PREFERENCE_LABEL}` in project-preferences.md reads {raw or '(empty)'!r}, "
        f"which is not one of {'/'.join(FILING_PREFERENCE_STATES)} — treating it as "
        f"{PREF_ASK_USER}, so an approval digest is still required"
    )


# --- the five checks (design §5) ---------------------------------------------


class Refusal(NamedTuple):
    """One failed §5 check: the code a caller branches on, and the prose it reads.

    A named type rather than a raw envelope because the checks are composed —
    every refusal picks up the same advisory payload on its way out (:func:`send`),
    and building the envelope inside each check is how that enrichment goes
    missing from one of five error paths without anybody noticing.
    """

    code: str
    message: str
    details: dict


def check_preference(state: str) -> Refusal | None:
    """§5 check 1 — ``never-file`` is a hard, unconditional refusal.

    The only one of the five that holds regardless of what else is true: §4.3
    calls it "a hard mechanical guarantee", so it is evaluated first and no
    later check, digest or authentication can reach past it.

    :data:`PREF_UNREADABLE` refuses under the same code and for the same reason
    one rung back: a guarantee that can only be honored by reading a file is not
    mechanical if an unreadable file means "proceed". The messages differ because
    the remedies do — one is a standing decision, the other is a broken file.
    """
    if state == PREF_UNREADABLE:
        return Refusal(
            "filing-disabled",
            "project-preferences.md could not be read, so the "
            f"`{FILING_PREFERENCE_LABEL}` preference could not be checked — filing "
            f"is refused rather than assumed, because a standing {PREF_NEVER_FILE} "
            "and an unreadable file look identical from here. Fix the file (or "
            "remove it — an ABSENT file is the ordinary case and does not refuse)",
            {"preference": state},
        )
    if state != PREF_NEVER_FILE:
        return None
    return Refusal(
        "filing-disabled",
        f"`{FILING_PREFERENCE_LABEL}` is {PREF_NEVER_FILE} in project-preferences.md — "
        "upstream filing is disabled here and nothing was sent; file it by hand at "
        f"https://github.com/{PINNED_TARGET}/issues, or change the preference if that "
        "standing no was not meant",
        {"preference": state},
    )


def check_target(requested: str | None) -> Refusal | None:
    """§5 check 2 — a ``--repo`` that disagrees with the pin is refused, not honored.

    Naming the pin is allowed, since a caller may reasonably be explicit; what a
    caller may not do is *select* the target. Shape-validating an arbitrary
    ``owner/repo`` is not an owner constraint, which is the hole this closes.
    """
    if requested is None or canonical_repo(requested) == PINNED_TARGET:
        return None
    return Refusal(
        "target-not-pinned",
        f"--repo {requested.strip()!r} is not the pinned upstream target "
        f"({PINNED_TARGET}); file-upstream files there or nowhere",
        {"pinned": PINNED_TARGET, "requested": requested.strip()},
    )


def check_not_self(identities: tuple[str, ...]) -> Refusal | None:
    """§5 check 3 — prawduct never files upstream to itself, and an unknown identity refuses.

    Two legs under one code, because the code names *which check refused* and a
    caller that wants the distinction reads ``details["reason"]``. The messages
    differ because the remedies do: a real self-file is **routed** — XP7's
    parenthetical is "it routes to its own backlog", so the refusal names
    ``backlog file`` rather than merely reporting a wall — while an unresolved
    identity is a configuration gap and the remedy is to give the repo an
    identity to compare.

    The invariant behind the routing: this op's whole ceremony — recomposition,
    verbatim review, digest approval, the visible-word ceiling — exists because
    content crosses an *owner* boundary. prawduct→prawduct crosses none, so
    minimizing its own bug reports would lose fidelity to protect prawduct from
    prawduct.

    **Empty is a refusal, not a pass.** ``resolve_self_identity`` returns an empty
    tuple when neither signal resolves, and reading that as "not the target" is
    the fail-open this check's 2026-07-24 amendment exists to close: identity keyed
    on ``backlog_service_repo`` alone is inert in every pre-cutover repo, which is
    exactly the state in which nobody has checked anything.
    """
    if not identities:
        return Refusal(
            "self-file",
            "this repo's own identity could not be resolved from either "
            "`backlog_service_repo` or an `origin` remote, so filing cannot prove it "
            f"is not {PINNED_TARGET} filing to itself — set one of the two and retry",
            {"reason": "unresolved", "pinned": PINNED_TARGET, "identities": []},
        )
    if PINNED_TARGET not in identities:
        return None
    return Refusal(
        "self-file",
        f"this repo IS the pinned upstream target ({PINNED_TARGET}), and prawduct's own "
        "bugs route to its own backlog rather than upstream to itself — file it with "
        "`prawduct-hook backlog file` instead",
        {"reason": "matched", "pinned": PINNED_TARGET, "identities": list(identities)},
    )


def check_approval(approve: str, digest: str, *, preference: str) -> Refusal | None:
    """§5 check 4 — the approval token must be the digest of the bytes about to go.

    This is what makes "sent == previewed" a property of the bytes rather than of
    the caller's intentions: the payload is re-rendered here and re-digested, so an
    approval given for payload A cannot authorize payload B.

    **Waived under ``always-file``, and only the value is waived.** Standing
    consent means the human is not asked per report, so there is no previewed
    digest for them to hand back — but the token is still *required*, because it
    is the only thing separating a send from a preview and a caller that renders a
    payload must not discover it filed one. So the empty token is refused FIRST,
    ahead of the waiver: this function is reachable from anywhere :func:`send` is,
    and a waiver that ran first would make ``approve=""`` file under standing
    consent. The CLI additionally rejects an empty ``--approve`` as a malformed
    flag, which is a better message for that caller and not a second rule.
    """
    if not approve.strip():
        return Refusal(
            "approval-mismatch",
            "an empty approval token is not an approval — pass the digest the preview "
            "printed; under standing consent its value is not compared, but the token "
            "is still what separates rendering a payload from filing one",
            {"approved": "", "payload_digest": digest},
        )
    if preference == PREF_ALWAYS_FILE:
        return None
    if approve.strip().lower() == digest.strip().lower():
        return None
    return Refusal(
        "approval-mismatch",
        "the approval token does not match the payload about to be sent — re-run the "
        "preview, review the bytes it prints, and approve that digest; an approval "
        "given for other bytes never authorizes these",
        {"approved": approve.strip(), "payload_digest": digest},
    )


def check_authenticated(actor: str | None) -> Refusal | None:
    """§5 check 5 — a resolved ``gh`` login, never an anonymous filing.

    GitHub issues are inherently authenticated, so an unresolvable login means the
    send would fail anyway — but it fails *after* the request, and the refusal
    here is what keeps the failure on this side of the boundary. The token is the
    session's own; the adapter never manages one (architecture § Direction).
    """
    if actor:
        return None
    return Refusal(
        "auth",
        "no authenticated GitHub identity — `gh auth login` first; upstream filing is "
        "never anonymous",
        {},
    )


#: How far back the ``source-key:`` dedup scan looks, in pages.
#:
#: Sized to the window the key exists for — a retry seconds after a create, whose
#: own issue is the newest one — not to the tracker. Unbounded, the scan's cost
#: falls entirely on the FIRST-time filing, which matches nothing and therefore
#: pays for the whole history every time; bounding it trades the ability to detect
#: a duplicate nobody is creating for a cost that stops growing with the tracker.
DEDUP_SCAN_PAGES = 3


# --- the send path (design §5, call 2) ---------------------------------------


def find_filed(transport, *, target: str, key: str) -> dict | None:
    """The issue already carrying this ``source-key:``, or ``None``. The §2.4 key at work.

    Scanned off the REST list endpoint rather than the search API, and the reason
    is the use case: the key exists for *retry safety* (api-contract A3/N2), so
    the lookup that matters most runs seconds after a create — and GitHub's search
    index is not read-your-writes, which makes it blind exactly then. The list
    endpoint is strongly consistent in practice, so a retry finds the issue its
    predecessor filed. Newest-first, because a retry's own issue is the newest one.

    **Bounded to :data:`DEDUP_SCAN_PAGES`, and the bound is the correction to an
    earlier reading of "the common case reads one page".** That was true of the
    RETRY and the retry is the rare case: a first-time filing matches nothing, so
    an unbounded walk exhausts the entire tracker — every closed issue, PRs
    interleaved — before it writes, once per report and growing monotonically
    forever. The window this scan serves is measured in seconds by design §5, so
    a few pages covers it and the pages beyond it were only ever buying the
    ability to find a duplicate nobody is about to create.

    So **"no duplicate" here means "no duplicate in the recent window"**, and that
    is the honest reading of the return value. It is safe to bound precisely
    because a miss is already non-fatal: :func:`_already_filed` catches a
    transport failure and files anyway with a loud warning, since the cost of
    proceeding blind is a duplicate a maintainer can close. None of the five
    checks runs through this path — they are the guarantees, this is advice.

    Pull requests interleave the REST issues list and are skipped; a body with no
    ``prawduct:`` block parses to an empty one and matches nothing.
    """
    owner, repo = target.split("/", 1)

    def fetch(page: int, per_page: int) -> list:
        return transport.list_issues(
            owner, repo, state="all", sort="created", direction="desc",
            per_page=per_page, page=page,
        )

    # `on_cap="stop"` because reaching the window's edge IS this scan's answer,
    # not a failed read. With the default, every first-time filing — which matches
    # nothing by definition — would trip the cap and raise, and `_already_filed`
    # would report a transport failure that did not happen.
    for issue in tx.paginate(
        fetch, max_pages=DEDUP_SCAN_PAGES, on_cap="stop", what=f"{target} issues"
    ):
        if not isinstance(issue, dict) or "pull_request" in issue:
            continue
        if encode.parse_block(issue.get("body")).get("source-key") == key:
            return issue
    return None


def send(
    project_dir,
    transport,
    *,
    title: str,
    body: str,
    component: str = "",
    approve: str,
    requested_repo: str | None = None,
) -> dict:
    """File upstream, or refuse — the whole of design §5's second call.

    Returns a result envelope. **Nothing is sent unless all five checks hold**,
    and each refuses with a distinct code so a caller can tell which one fired
    without reading prose. None of the five is retryable — an identical refused
    filing refuses identically — which is what separates them from the transport
    errors that can also come back here and carry their own retryability.

    The payload is composed FIRST, through the same :func:`render_preview` the
    preview arm calls, for two reasons that both bite. Check 4 has to compare
    against bytes re-rendered here rather than bytes the caller kept, or the
    approval covers a claim instead of a payload — and composing before the
    checks is what lets every refusal carry the same advisory ``lint`` findings
    the success envelope carries, so an author fixing a refusal sees the budget
    problems in the same round instead of the next one.

    **Title conformance is enforced here and merely reported by the preview.**
    ``data-model.md`` § Direction binds the issue standard's §1 title rules on
    every adapter write path, and this is the fourth. It binds harder upstream
    than in-repo: a non-collaborator filer cannot relabel or retitle afterwards,
    and the write does not come back. The preview stays advisory because nothing
    is written there — an advisory finding is precisely what lets an author fix a
    title *before* approving it.
    """
    input_err = check_payload_inputs(title=title, body=body, component=component)
    if input_err:
        return core.error("validation", input_err)

    # Composed unconditionally, ahead of every check: `check_payload_inputs` above
    # is what makes this total, so the pair is never `None` here.
    payload, digest = render_preview(project_dir, title=title, body=body, component=component)
    findings = lint_payload(payload["title"], payload["body"])
    preference, pref_warning = read_filing_preference(project_dir)
    warnings = [pref_warning] if pref_warning else []

    def refuse(refusal: Refusal) -> dict:
        return attach_advisories(
            core.error(refusal.code, refusal.message, retryable=False, details=refusal.details),
            warnings=warnings,
            findings=findings,
        )

    for refusal in (
        check_preference(preference),
        check_target(requested_repo),
        check_not_self(resolve_self_identity(project_dir)),
        check_approval(approve, digest, preference=preference),
    ):
        if refusal is not None:
            return refuse(refusal)

    try:
        actor = (transport.get_authenticated_user() or {}).get("login")
    except tx.TransportError as exc:
        return attach_advisories(
            core.from_transport_error(exc), warnings=warnings, findings=findings
        )
    refusal = check_authenticated(actor)
    if refusal is not None:
        return refuse(refusal)

    title_refusal = _title_refusal(payload["title"])
    if title_refusal is not None:
        return attach_advisories(title_refusal, warnings=warnings, findings=findings)

    key = encode.parse_block(payload["body"]).get("source-key") or ""
    existing, dedup_warning = _already_filed(transport, payload["repo"], key)
    if dedup_warning:
        warnings.append(dedup_warning)
    if existing is not None:
        return attach_advisories(
            core.ok(_sent(payload, digest, existing, created=False), warnings),
            findings=findings,
        )

    owner, repo = payload["repo"].split("/", 1)
    try:
        issue = transport.create_issue(
            owner, repo, title=payload["title"], body=payload["body"], labels=payload["labels"]
        )
    except tx.TransportError as exc:
        return attach_advisories(
            core.from_transport_error(exc), warnings=warnings, findings=findings
        )
    return attach_advisories(
        core.ok(_sent(payload, digest, issue, created=True), warnings), findings=findings
    )


def _already_filed(transport, target: str, key: str) -> tuple[dict | None, str | None]:
    """``(existing_issue, warning)`` — the §2.4 dedup read, degraded rather than fatal.

    A lookup that cannot run does **not** block the filing. XP7 is submit-or-nothing
    and explicitly names a slow flow as the failure that turns "submit" into
    "nothing", while the cost of proceeding blind is a duplicate issue a maintainer
    can close. So a transport failure here files anyway and says so loudly enough
    that the operator knows to look — the honest trade, not a silent one. The
    guarantees that *do* fail closed are the five checks above, and none of them
    runs through this function.
    """
    if not key:
        return None, None
    try:
        return find_filed(transport, target=target, key=key), None
    except tx.TransportError as exc:
        return None, (
            f"could not check {target} for an existing filing of this report "
            f"({exc.message}); filed without the idempotency check, so look for a "
            "duplicate if this was a retry"
        )


def _sent(payload: dict, digest: str, issue: dict, *, created: bool) -> dict:
    """The success payload for a send. ``created`` is what a re-file changes.

    ``sent`` answers "does this report exist upstream now?" and is true either
    way — the preview's ``sent: False`` is the state this distinguishes itself
    from. ``created`` answers "did this call write it?", which is the only thing
    an idempotent re-file changes and the only thing a caller counting filings
    should read.
    """
    return {
        "payload": payload,
        "payload_digest": digest,
        "sent": True,
        "created": created,
        "issue": {
            "number": issue.get("number"),
            "url": issue.get("html_url"),
            "state": issue.get("state"),
        },
    }


def previewable_refusals(project_dir, *, rendered_title: str, preference: str) -> list[tuple]:
    """Every reason the send arm would refuse that a PREVIEW can already know.

    One list, consumed by the preview arm, because the alternative is a preview
    that hand-enumerates the refusals it can predict: a refusal added to the send
    arm is then missing from the preview **by default**. The title refusal is the
    case that shape gets wrong — without this list it reaches the operator only
    as an ordinary ``lint:`` line, indistinguishable from the body-budget
    findings that never block, and ``issuefmt.LintFinding.severity`` is hardcoded
    ``"warn"`` with its own docstring saying not to read it as advisory.

    Why that costs more than a confusing line: the operator reviews bytes,
    approves a digest, and only then learns the send cannot succeed — a second
    recomposition-and-approval round on the path design §5 calls *Fast*, and slow
    is exactly what turns XP7's submit-or-nothing into nothing.

    **Excluded on purpose:** ``check_target`` (the CLI answers it on both arms
    before anything is composed, and composing a payload aimed at the pin to lint
    it would report budget findings about bytes this caller never asked to send),
    ``check_approval`` (a preview has no token to compare and its absence is what
    MAKES it a preview), ``check_authenticated`` (it needs the transport this
    function is defined never to touch), and ``check_payload_inputs`` (the preview
    arm refuses on it directly, before there is a payload to hang a "would refuse"
    note on — these inputs are what a payload is composed FROM).

    That list is mirrored by the ``excluded`` set in
    ``test_every_no_transport_refusal_the_send_arm_has_is_predicted``, which
    derives the refusals from ``send``'s AST; the test is authoritative and this
    prose is the readable copy, so a divergence between them is this docstring's
    bug.

    Returns ``(code, message)`` pairs so a caller renders them; the send arm keeps
    returning its own structured errors, whose ``details`` differ per refusal.
    """
    refusals: list[tuple] = []
    for refusal in (
        check_preference(preference),
        check_not_self(resolve_self_identity(project_dir)),
    ):
        if refusal is not None:
            refusals.append((refusal.code, refusal.message))
    title_refusal = _title_refusal(rendered_title)
    if title_refusal is not None:
        err = title_refusal["error"]
        refusals.append((err["code"], err["message"]))
    return refusals


def _title_refusal(title: str) -> dict | None:
    """A ``validation`` error when the rendered title fails a §1 rule, else ``None``.

    The **rendered** title, not the caller's ``--title``: the issue that lands
    upstream carries the ``[prawduct] <component>:`` convention, so that is the
    string the standard binds and its budget is what the prefix spends against.
    Deliberately not shared with ``core._title_refusal`` — that one's message
    tells an agent to rewrite and refile into the product's own repo, and the
    remedy here is to re-preview and re-approve, which is a different sentence
    about a different, irreversible write.

    The area-prefix expectation does not apply and is not consulted: §2's
    convention is ``[prawduct] <component>: <symptom>``, not §1's ``area:
    summary``, and ``_split_area`` reads the multi-word lead-in as no prefix at
    all — so the budget, placeholder and atomicity rules are what remain.
    """
    findings = issuefmt.lint_title(title)
    if not findings:
        return None
    detail = "; ".join(f"{f.rule}: {f.message}" for f in findings)
    return core.error(
        "validation",
        f"the outbound title does not conform to the issue standard ({detail}); "
        f"upstream filing is irreversible and a non-collaborator cannot retitle "
        f"afterwards, so fix it and re-preview: {title!r}",
        details={"title": title, "findings": [f.as_dict() for f in findings]},
    )


def attach_advisories(result: dict, *, findings: list, warnings: list | None = None) -> dict:
    """Attach the advisory payload to a result — success **and** every refusal.

    ``core.error`` is a different constructor from ``core.ok`` with no slot for
    either field, which is how a datum that rides the success path silently
    vanishes from the failure path. Here the loss would be concrete: a refused
    filing is exactly the moment an author is about to edit the report, so the
    budget findings are worth more on that envelope than on the one where the
    filing already worked.
    """
    if warnings:
        result["warnings"] = list(result.get("warnings") or []) + list(warnings)
    if findings:
        result["lint"] = [finding.as_dict() for finding in findings]
    return result
