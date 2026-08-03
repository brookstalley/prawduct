"""Authoring lint for the two-audience advisory contract.

Every ``AdvisoryCandidate`` a probe raises reaches two readers who cannot do each
other's job: the owner, who decides, and the runtime, which executes. The schema
gives each its own field (``post-sync-advisory-spec.md`` §3.6), but a schema only
makes the fields *available* — nothing stops the next probe from shipping with a
blank ``owner_action`` and a paragraph of prose in ``recommended_action``, which
is exactly the state this contract was written to end.

Prose has no compiler, so this module is the compiler. It sweeps the construction
sites themselves rather than the rendered output: a probe that never fires in the
test environment still gets its copy checked, and the check is the same one whether
the probe has a live trigger or not.

Four rules, each with its owner:

* **Every site states an owner action** (§7.2 "Both actions, or state why not").
  The rendered fallback line exists so an absent field degrades visibly rather than
  silently — it is a safety net for stored advisories written under the old schema,
  not a licence for new ones.
* **No commands in owner text** (§7.2). If the owner's contribution is "run this",
  the real owner action is *approve* and the command belongs in the agent's field.
* **``recommended_action`` is a command or nothing** (§7.2, narrowed in v0.3). Prose
  here is what produced ``→ Run Review each listed item…``.
* **Every declared ``prerequisite_of`` key names a registered probe.** An edge to an
  unregistered ``<feature>:<type>`` is inert *by design* — it fails soft at render
  time (`architecture.md` § Direction: advice fails soft). That is right for a live
  session and wrong for an author: a typo in an edge would otherwise be silent
  forever. This sweep is where it stops being silent, and it is the cheap home for
  the check because the roster is already imported for the other assertions.

The sweep reads *literal* text only. A value assembled at runtime (``", ".join(...)``)
is skipped by the copy rules rather than guessed at — an unresolvable value that
failed would push authors toward writing checkable-but-worse copy, and one that
silently passed would be a lint claiming coverage it does not have. Skips are
counted and asserted against, so the unreadable set cannot grow unnoticed.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from lib import advisory_store, probe_families

# The probe modules live under plugin/, not the repo root (see tests/conftest.py).
PROBE_DIR = Path(__file__).resolve().parents[1] / "plugin" / "lib"

# Executables a probe may legitimately name in `recommended_action`. An allowlist
# rather than "any lowercase word" so that adding one is a conscious act: the field
# means "the command the runtime executes", and every entry here is a claim that the
# runtime may execute it. `git` is here because the stale-base probe's action really
# is `git push origin <branch>` — a plain shell command, which is why the spec's
# enumeration reads "a slash command, a prawduct-hook invocation, or a plain shell
# command" rather than naming only the first two.
COMMAND_EXECUTABLES = frozenset({"prawduct-hook", "git"})

# Tokens that make owner-facing text a command rather than a decision. `/prawduct:`
# and `prawduct-hook` are banned as substrings (they are unambiguous wherever they
# appear); a bare slash command is matched only token-initially, so a path an owner
# genuinely needs to see — `.prawduct/backlog.md`, `docs/norms.md`, `incoming-bugs/`
# — is not mistaken for one.
_OWNER_BANNED_SUBSTRINGS = ("/prawduct:", "prawduct-hook")
_SLASH_COMMAND_RE = re.compile(r"(?:^|\s)/[a-z][\w:-]*")

# §7.2's third banned form: a bare shell invocation. Without this the rule covered
# slash commands and `prawduct-hook` only, which is two arms of three — and the gap
# was not hypothetical, because `git` is an allowed executable in the agent's field
# and the stale-base advisory's whole subject is a push. "Say go and I will run git
# push origin main" would have shipped green.
#
# Matched as executable-followed-by-a-word, which also catches the incidental noun
# ("your git history"). That over-reach is deliberate and cheap to satisfy: owner
# copy describes an outcome, not a tool, so the fix is always a reword rather than
# a suppression.
_SHELL_INVOCATION_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(name) for name in sorted(COMMAND_EXECUTABLES)) + r")\s+[a-z][\w.-]*"
)

# Placeholder standing in for an f-string's interpolated value. The copy rules ask
# whether the text is a command or prose, and no interpolation changes that answer.
_INTERPOLATION = "{}"


# =============================================================================
# Reading the construction sites
# =============================================================================


class Site:
    """One ``AdvisoryCandidate(...)`` construction, as the lint sees it."""

    def __init__(self, module: str, lineno: int, kwargs: dict):
        self.module = module
        self.lineno = lineno
        self.kwargs = kwargs

    @property
    def label(self) -> str:
        """A handle a failure message can be acted on directly."""
        declared = self.kwargs.get("type")
        named = declared.text if isinstance(declared, _Literal) and declared.text else "?"
        return f"{self.module}:{self.lineno} (type={named})"


class _Literal:
    """A statically-readable string value, or the record that it is not one.

    ``text`` is the resolved string; ``readable`` is False when the expression
    depends on runtime values the sweep declines to guess at.
    """

    def __init__(self, text: str, readable: bool):
        self.text = text
        self.readable = readable


def _read_string(node) -> _Literal:
    """Resolve a string-valued AST expression as far as static reading allows.

    Handles the three forms probe authors actually use: a plain literal, implicit
    concatenation of adjacent literals inside parentheses (which the parser has
    already folded, or which arrives as a ``+`` chain), and f-strings whose
    interpolations become :data:`_INTERPOLATION`. Anything else — a name, a
    ``.join()`` call — is reported unreadable rather than approximated.
    """
    if isinstance(node, ast.Constant):
        return _Literal(node.value, True) if isinstance(node.value, str) else _Literal("", False)
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                parts.append(_INTERPOLATION)
        return _Literal("".join(parts), True)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _read_string(node.left), _read_string(node.right)
        if left.readable and right.readable:
            return _Literal(left.text + right.text, True)
        return _Literal("", False)
    return _Literal("", False)


def _sites_in(path: Path) -> list[Site]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[Site] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "AdvisoryCandidate"):
            continue
        kwargs = {kw.arg: _read_string(kw.value) for kw in node.keywords if kw.arg}
        # `prerequisite_of` is a tuple, not a string — carry the raw node for its
        # own rule rather than forcing it through the string reader.
        for kw in node.keywords:
            if kw.arg == "prerequisite_of":
                kwargs["prerequisite_of"] = kw.value
        found.append(Site(path.name, node.lineno, kwargs))
    return found


def _all_sites() -> list[Site]:
    sites: list[Site] = []
    for path in sorted(PROBE_DIR.glob("*_probes.py")):
        sites.extend(_sites_in(path))
    return sites


@pytest.fixture(scope="module")
def sites() -> list[Site]:
    found = _all_sites()
    assert found, f"no AdvisoryCandidate construction sites found under {PROBE_DIR}"
    return found


def _ids(sites: list[Site]) -> list[str]:
    return [s.label for s in sites]


# =============================================================================
# The census
# =============================================================================


def test_every_registered_probe_module_is_swept(sites):
    """The sweep covers every module the composition root registers.

    Without this, a new probe family added to `probe_families.register_all` but
    named outside the `*_probes.py` glob would be linted by nothing at all — the
    lint would keep passing while its coverage quietly shrank.
    """
    swept = {s.module for s in sites}
    registry = _registry()
    assert registry, "the composition root registered no probes"
    # Ask each registered probe which module it came from rather than comparing
    # counts. A count only detects a roster that outgrew the sweep; this names the
    # module that escaped it, and stays correct if a probe ever yields two
    # candidates (which would make the counts differ for an innocent reason).
    homes = {
        Path(record["fn"].__code__.co_filename).name for record in registry.values()
    }
    missed = sorted(homes - swept)
    assert not missed, (
        f"registered probe(s) live in module(s) the *_probes.py sweep does not reach: "
        f"{missed} — their advisory copy is linted by nothing"
    )


# =============================================================================
# Rule 1 — every site states an owner action
# =============================================================================


def test_every_site_states_an_owner_action(sites):
    missing = [
        s.label
        for s in sites
        if not (s.kwargs.get("owner_action") and s.kwargs["owner_action"].readable
                and s.kwargs["owner_action"].text.strip())
    ]
    assert not missing, (
        "AdvisoryCandidate site(s) with no owner_action — the owner reads a problem "
        "with no route out of it (post-sync-advisory-spec.md §7.2):\n  "
        + "\n  ".join(missing)
    )


# =============================================================================
# Rule 2 — no commands in owner-facing text
# =============================================================================


@pytest.mark.parametrize("site", _all_sites(), ids=_ids(_all_sites()))
def test_owner_action_contains_no_command(site):
    """The owner does not open a terminal. If the owner's contribution is "run
    this", the owner action is *approve* and the command is the agent's field."""
    value = site.kwargs.get("owner_action")
    if value is None or not value.readable:
        pytest.skip("owner_action absent or not statically readable")
    text = value.text
    for banned in _OWNER_BANNED_SUBSTRINGS:
        assert banned not in text, (
            f"{site.label}: owner_action names `{banned}` — owners do not run framework "
            "commands; move it to recommended_action (spec §7.2)"
        )
    found = _SLASH_COMMAND_RE.search(text)
    assert not found, (
        f"{site.label}: owner_action contains the slash command `{found.group().strip()}` "
        "— move it to recommended_action (spec §7.2)"
    )
    shell = _SHELL_INVOCATION_RE.search(text)
    assert not shell, (
        f"{site.label}: owner_action reads as the shell invocation `{shell.group().strip()}` "
        "— the owner does not run commands. Say what saying yes achieves and put the command "
        "in recommended_action (spec §7.2)"
    )


# =============================================================================
# Rule 3 — recommended_action is one command, or nothing
# =============================================================================


@pytest.mark.parametrize("site", _all_sites(), ids=_ids(_all_sites()))
def test_recommended_action_is_a_command_or_empty(site):
    """The field means *what the runtime executes*. Empty is a valid answer — an
    advisory can be owner-only. Prose is not: it renders behind an `agent →` label
    and instructs nobody."""
    value = site.kwargs.get("recommended_action")
    if value is None:
        return  # absent is the same as empty: an owner-only advisory
    if not value.readable:
        pytest.skip("recommended_action not statically readable")
    text = value.text.strip()
    if not text:
        return
    assert "\n" not in text, f"{site.label}: recommended_action spans lines — not a command"
    assert ";" not in text and " — " not in text, (
        f"{site.label}: recommended_action reads as prose (`{text}`) — one command, or "
        "empty and let owner_action carry the decision (spec §7.2)"
    )
    first = text.split()[0]
    assert first.startswith("/") or first in COMMAND_EXECUTABLES, (
        f"{site.label}: recommended_action starts with `{first}`, which is neither a slash "
        f"command nor an allowed executable ({sorted(COMMAND_EXECUTABLES)}). This field is "
        "what the RUNTIME executes; prose belongs in owner_action (spec §7.2)"
    )


# =============================================================================
# Rule 4 — every prerequisite edge names a registered probe
# =============================================================================


@pytest.fixture(autouse=True)
def _restore_probe_registry():
    """Leave the global probe registry exactly as found.

    :func:`_registry` registers the *production* roster into module-level state that
    every other advisory test shares. Without this, a test running later in the same
    worker inherits 18 live probes it never asked for — and those are not inert: they
    shell out to git and walk the tree they are pointed at. A sibling that registers
    one synthetic probe and asserts on what fires would see the whole roster instead.
    """
    saved = dict(advisory_store._REGISTRY)
    try:
        yield
    finally:
        advisory_store._REGISTRY.clear()
        advisory_store._REGISTRY.update(saved)


def _registry() -> dict:
    """The live probe roster, registered through the production composition root."""
    probe_families.register_all()
    return dict(advisory_store._REGISTRY)


def _declared_edge_keys(site: Site) -> list[str]:
    """The ``<feature>:<type>`` keys a site declares, read from the source tuple."""
    node = site.kwargs.get("prerequisite_of")
    if not isinstance(node, (ast.Tuple, ast.List)):
        return []
    keys: list[str] = []
    for entry in node.elts:
        if not isinstance(entry, (ast.Tuple, ast.List)) or not entry.elts:
            continue
        key = _read_string(entry.elts[0])
        if key.readable and key.text:
            keys.append(key.text)
    return keys


def test_every_prerequisite_edge_names_a_registered_probe(sites):
    """An edge to an unregistered key is inert at render time and silent forever.

    Fail-soft is right for a live session — a mis-declared edge must not cost the
    session its advisory block — but it means the *author* gets no signal at all.
    This is the signal.
    """
    known = set(_registry())
    assert known, "the composition root registered no probes"
    dangling = [
        (site.label, key)
        for site in sites
        for key in _declared_edge_keys(site)
        if key not in known
    ]
    assert not dangling, (
        "prerequisite_of edge(s) naming no registered probe — inert at render time, "
        "so nothing else would ever report this:\n  "
        + "\n  ".join(f"{label} → {key}" for label, key in dangling)
    )


def test_prerequisite_edges_are_declared_on_the_earlier_advisory(sites):
    """Each edge carries a `because` explaining why THIS advisory comes first.

    The field is `prerequisite_of` — declared on the earlier work, naming the later.
    A blank reason turns the rendered `after →` line into a bare re-statement of the
    ordering, which is the "here is a fact, no route out" shape being fixed."""
    thin = []
    for site in sites:
        node = site.kwargs.get("prerequisite_of")
        if not isinstance(node, (ast.Tuple, ast.List)):
            continue
        for entry in node.elts:
            if not isinstance(entry, (ast.Tuple, ast.List)) or len(entry.elts) != 2:
                thin.append((site.label, "edge is not a (key, because) pair"))
                continue
            because = _read_string(entry.elts[1])
            if not because.readable or not because.text.strip():
                thin.append((site.label, "edge carries no `because` text"))
    assert not thin, "\n  ".join(f"{label}: {why}" for label, why in thin)


# =============================================================================
# The named copy guarantee (security-model.md § Direction)
# =============================================================================


def _site_named(sites: list[Site], probe_type: str) -> Site:
    for site in sites:
        declared = site.kwargs.get("type")
        if isinstance(declared, _Literal) and declared.text == probe_type:
            return site
    raise AssertionError(f"no AdvisoryCandidate site declares type={probe_type!r}")


def test_backlog_migration_owner_action_states_cost_and_volume(sites):
    """The one advisory that routes to an irreversible bulk write says so.

    `security-model.md` § Direction requires explicit owner approval at the
    *operation* level for a destructive or irreversible operation. This advisory
    authorises the creation of real GitHub issues — which GitHub does not let you
    ordinarily delete, and whose numbers it never reuses. Approval given without
    the volume and the irreversibility in the sentence the owner actually reads is
    uninformed approval, and a copy edit could quietly drop either word.
    """
    site = _site_named(sites, "backlog-service-migration-required")
    owner = site.kwargs["owner_action"]
    assert owner.readable and owner.text.strip(), "owner_action is not readable"
    text = owner.text.lower()
    assert "cannot be undone" in text or "irreversible" in text, (
        "the backlog-migration owner action must state that the write cannot be "
        f"undone — reads: {owner.text!r}"
    )
    assert _INTERPOLATION in owner.text, (
        "the backlog-migration owner action must state the VOLUME from live data "
        "(the pending count), not a static adjective — a number the owner can weigh "
        f"is the difference between an informed yes and a reflexive one; reads: {owner.text!r}"
    )
    assert "issue" in text, (
        f"the owner action must name what is written (GitHub issues) — reads: {owner.text!r}"
    )


# =============================================================================
# Coverage honesty — the unreadable set must not grow unnoticed
# =============================================================================


def test_no_construction_site_hides_its_copy_from_the_lint(sites):
    """Every site's two action fields are statically readable.

    The rules above skip what they cannot read, which is the honest behaviour for a
    single site and a silent hole if it spreads: a probe could evade the whole lint
    by assembling its copy through a helper. Today nothing does, and this test is
    what makes that a property rather than a coincidence.
    """
    unreadable = [
        f"{site.label}: {field}"
        for site in sites
        for field in ("owner_action", "recommended_action")
        if field in site.kwargs and not site.kwargs[field].readable
    ]
    assert not unreadable, (
        "action field(s) the lint cannot read, so the copy rules silently skip them. "
        "Keep advisory copy as literal text at the construction site:\n  "
        + "\n  ".join(unreadable)
    )
