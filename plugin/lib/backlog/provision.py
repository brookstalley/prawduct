"""Provisioning — the namespaced label taxonomy (GV5/GV6 coexistence).

All prawduct labels are ``<facet>:``-namespaced so they never collide with a
repo's existing labels (Data Model §3). Provisioning is **idempotent** (list,
then create only what is missing) and **collision-free** (it only ever *creates*
namespaced labels it does not find — it never modifies an existing label, even
one with the same name; PROV-1).

This module is pure of the envelope layer (no ``core`` import) so ``core`` can
own the envelope without a cycle. ``core`` wraps ``ensure_labels`` into the CLI
``provision`` op; ``file`` calls ``ensure_labels`` for the concrete labels it is
about to apply, so a create never references a non-existent label.

This is the **minimal** provision: create the closed-vocabulary base
set + the labels a ``file`` needs. :func:`reconcile` is the GV6 drift/coexistence
*reconcile* — the idempotent re-run that re-establishes the full taxonomy and
reports the coexistence picture (which foreign labels it left untouched), the
primitive ``/prawduct:onboard`` / ``doctor`` call.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import encode
from .transport import Transport

# One color + description per facet (deterministic; the durable contract is the
# name, not the color — a human may recolor freely).
_FACET_COLORS: dict[str, str] = {
    "stage": "0e8a16",
    "status": "1d76db",
    "kind": "5319e7",
    "area": "fbca04",
    "effort": "c5def5",
    "impact": "d93f0b",
    "source": "bfd4f2",
    "id": "ededed",
    "verified": "0e8a16",
    "superseded-by": "b60205",
    "import-key": "ededed",  # idempotency-only marker for an id-less import (Data Model §5)
    # The multi-valued folksonomy facet (encode.TAG_FACET). Open like
    # kind/area/effort/impact/source, so it is created on demand as values appear
    # and never seeded into `base_labels()` — there is no vocabulary to seed.
    "tag": "d4c5f9",
}
_DEFAULT_COLOR = "ededed"

# Facet prefixes we recognize as ours (guards ensure_labels against provisioning
# a name that is not actually namespaced).
KNOWN_FACETS: tuple[str, ...] = tuple(_FACET_COLORS.keys())


@dataclass
class ProvisionResult:
    created: list[str] = field(default_factory=list)
    existing: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ReconcileResult:
    """The GV6 reconcile picture: what was created/already-present in **our**
    namespace, and the **foreign** (non-prawduct) labels left untouched — the
    coexistence proof (PROV-1: existing non-prawduct labels are never modified)."""

    created: list[str] = field(default_factory=list)
    existing: list[str] = field(default_factory=list)
    foreign_untouched: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def facet_of(name: str) -> str | None:
    """Return the facet prefix of a ``<facet>:value`` label, or ``None``."""
    facet, sep, _ = name.partition(":")
    if sep and facet in KNOWN_FACETS:
        return facet
    return None


def label_spec(name: str) -> tuple[str, str]:
    """Return ``(color, description)`` for a namespaced label."""
    facet = facet_of(name)
    color = _FACET_COLORS.get(facet or "", _DEFAULT_COLOR)
    description = f"prawduct: {facet}" if facet else "prawduct"
    return color, description


def base_labels() -> list[str]:
    """The closed-vocabulary base taxonomy a repo is provisioned with.

    Open facets (``kind``/``area``/``effort``/``impact``/``source``/``tag``) have
    no fixed vocabulary, so their labels are created on demand by ``file`` /
    ``update`` as values appear — not seeded here.
    """
    labels = [f"stage:{value}" for value in encode.STAGE_VALUES]
    labels += [f"status:{value}" for value in encode.STATUS_OPEN_LABELS]
    return labels


def ensure_labels(
    transport: Transport, owner: str, repo: str, names: list[str]
) -> ProvisionResult:
    """Create any of ``names`` that are missing; leave everything else untouched.

    Idempotent and collision-free: lists existing labels first, then creates only
    the missing **namespaced** ones. A non-namespaced name is skipped with a
    warning (we never provision outside our namespace). Raises ``TransportError``
    on a transport failure (caught at the ``core`` boundary).
    """
    result = ProvisionResult()
    existing_names = {label.get("name") for label in transport.list_labels(owner, repo)}
    _create_missing(transport, owner, repo, names, existing_names, result)
    return result


def _create_missing(
    transport: Transport,
    owner: str,
    repo: str,
    names: list[str],
    existing_names: set,
    result,
) -> None:
    """Create any namespaced ``names`` absent from ``existing_names`` (mutated in
    place as labels are created). Collision-free (only ever *creates* labels it
    does not find) and never touches a non-namespaced name. Shared by
    :func:`ensure_labels` and :func:`reconcile` so the create-missing rule lives
    once; ``result`` accumulates ``created``/``existing``/``warnings``."""
    for name in names:
        if name in existing_names:
            result.existing.append(name)
            continue
        if facet_of(name) is None:
            result.warnings.append(f"skipped non-namespaced label {name!r} (not provisioned)")
            continue
        color, description = label_spec(name)
        transport.create_label(owner, repo, name=name, color=color, description=description)
        result.created.append(name)
        existing_names.add(name)


def reconcile(transport: Transport, owner: str, repo: str) -> ReconcileResult:
    """GV6 coexistence reconcile: re-establish the base taxonomy, report the rest.

    Lists the repo's labels **once**, ensures every base label exists (creating
    only the missing **namespaced** ones — same collision-free rule as
    :func:`ensure_labels`), and reports the **foreign** (non-prawduct) labels it
    left completely untouched (PROV-1). Idempotent: a re-run against a fully
    reconciled repo creates nothing. Never deletes or modifies an existing label —
    drift is corrected by *adding* what is missing, never by removing what a human
    or another tool added. Raises ``TransportError`` on a transport failure (caught
    at the ``core`` boundary)."""
    result = ReconcileResult()
    all_labels = [label.get("name") for label in transport.list_labels(owner, repo)]
    existing_names = {name for name in all_labels if name}
    result.foreign_untouched = sorted(
        name for name in existing_names if facet_of(name) is None
    )
    _create_missing(transport, owner, repo, base_labels(), existing_names, result)
    return result
