"""Encoding: the ``prawduct:`` body block, soft-enum tolerance, and item decode.

Three concerns, all pure (a function-level seam — Test Specs §2.1; no transport):

1. **The ``prawduct:`` block** (Data Model §2) — a single fenced ``prawduct``
   block at the end of an issue body carrying the non-native, block-authoritative
   fields (so export round-trips losslessly, MG2). Parse is **tolerant**: unknown
   keys are preserved verbatim (forward-compat, additive-only-forever), missing
   keys default, and when a body carries **more than one** block the parser takes
   the **last** and flags the earlier ones (ENC-3, m5).

2. **Soft enums** (Data Model §1.1, DM1) — an undeclared ``stage:``/``kind:``
   value is **flagged, not rejected** (ENC-1). The hard reject is reserved for a
   genuinely ambiguous **status** or a malformed ID (API §3).

3. **Item decode** — read a GitHub issue's state/labels/block into the item
   projection (Data Model §1.1). The two orthogonal axes (``status`` × ``stage``)
   are never flattened (DM2). *The self-healing reconciling write* that strips
   losing labels is the ``set-status`` keystone built next; this module decodes
   with the same precedence but does not itself mutate.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, field

# --- Vocabularies ------------------------------------------------------------

STAGE_VALUES: tuple[str, ...] = (
    "idea",
    "research",
    "requirements",
    "design",
    "ready",
)
# The full status vocabulary (closed set — an unknown status is a hard reject).
STATUS_VALUES: tuple[str, ...] = (
    "submitted",
    "open",
    "in-progress",
    "shipped",
    "dropped",
)
# Open sub-states that live *only* in a `status:` label (Data Model §4).
STATUS_OPEN_LABELS: tuple[str, ...] = ("submitted", "in-progress")

# Facets carried as `<facet>:value` labels (Data Model §3). `kind/area/effort/
# impact/source` are open soft enums (any value accepted); `stage` has a known
# vocabulary (unknown → warning); `status` is closed (unknown → hard reject).
OPEN_FACETS: tuple[str, ...] = ("kind", "area", "effort", "impact", "source")

_BLOCK_RE = re.compile(
    r"^```prawduct[ \t]*\n(?P<body>.*?)^```[ \t]*$",
    re.MULTILINE | re.DOTALL,
)


# --- The prawduct: block -----------------------------------------------------


@dataclass
class Block:
    """A parsed ``prawduct:`` block.

    ``fields`` preserves **every** key (known and unknown) in source order as its
    raw value string, so re-serialization is verbatim and additive-only-forever
    (an unknown key is never dropped or repurposed — ENC-4). Typed accessors
    interpret the specific keys the adapter understands.
    """

    fields: "OrderedDict[str, str]" = field(default_factory=OrderedDict)
    warnings: list[str] = field(default_factory=list)

    def version(self) -> int:
        raw = self.fields.get("v")
        if raw is None:
            return 1
        try:
            return int(raw)
        except ValueError:
            return 1

    def id_aliases(self) -> list[str]:
        return _parse_list(self.fields.get("id_aliases"))

    def get(self, key: str) -> str | None:
        return self.fields.get(key)

    def reserialize(self) -> str:
        return _emit_block(self.fields)


def parse_block(body: str | None) -> Block:
    """Parse the ``prawduct:`` block out of an issue body (tolerant).

    Zero blocks → an empty ``Block`` (all defaults, no warning). Two+ blocks →
    the **last** wins and each earlier one is flagged (ENC-3). A malformed inner
    line (no ``:`` separator) is skipped with a warning, never an error.
    """
    block = Block()
    if not body:
        return block

    matches = _BLOCK_RE.findall(body)
    if not matches:
        return block
    if len(matches) > 1:
        block.warnings.append(
            f"issue body carries {len(matches)} prawduct blocks; using the last "
            "and ignoring the earlier one(s)"
        )

    inner = matches[-1]
    for raw_line in inner.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue  # blank or comment — not a field
        if ":" not in line:
            block.warnings.append(f"ignored malformed block line: {stripped!r}")
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        if not key:
            block.warnings.append(f"ignored malformed block line: {stripped!r}")
            continue
        block.fields[key] = value.strip()  # last occurrence wins
    return block


def serialize_block(fields: dict[str, str]) -> str:
    """Build a fresh ``prawduct:`` block from field→formatted-value strings.

    Always emits ``v: 1`` first (the block schema version, §7). Callers pass
    values already formatted (lists as ``[a, b]``); this only frames the fence.
    """
    ordered: "OrderedDict[str, str]" = OrderedDict()
    ordered["v"] = str(fields.get("v", "1"))
    for key, value in fields.items():
        if key == "v":
            continue
        ordered[key] = value
    return _emit_block(ordered)


def _emit_block(fields: "OrderedDict[str, str]") -> str:
    lines = ["```prawduct"]
    lines.extend(f"{key}: {value}" for key, value in fields.items())
    lines.append("```")
    return "\n".join(lines)


def _parse_list(raw: str | None) -> list[str]:
    if raw is None:
        return []
    text = raw.strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1].strip()
        if not text:
            return []
    return [item.strip() for item in text.split(",") if item.strip()]


# --- Soft enums --------------------------------------------------------------


@dataclass
class EnumCheck:
    """Result of validating a soft/closed enum value.

    ``ok`` is False only for a hard reject (unknown status). An undeclared soft
    value is ``ok`` with a ``warning`` (flagged, not rejected — DM1).
    """

    ok: bool
    warning: str | None = None
    message: str | None = None


def check_enum(facet: str, value: str) -> EnumCheck:
    """Validate an enum value for a facet (ENC-1 / DM1).

    - ``status`` is a **closed** vocabulary — an unknown value is a hard reject.
    - ``stage`` has a **known** vocabulary — an unknown value is **flagged** (a
      warning), never rejected.
    - ``kind``/``area``/``effort``/``impact``/``source`` are **open** — any value
      is accepted with no warning (there is no vocabulary to be unknown against).
    """
    if facet == "status":
        if value not in STATUS_VALUES:
            return EnumCheck(
                ok=False,
                message=f"unknown status {value!r} (expected one of {', '.join(STATUS_VALUES)})",
            )
        return EnumCheck(ok=True)
    if facet == "stage":
        if value not in STAGE_VALUES:
            return EnumCheck(
                ok=True,
                warning=f"unknown stage {value!r} — flagged, not rejected (soft enum)",
            )
        return EnumCheck(ok=True)
    # Open facets: accepted as-is.
    return EnumCheck(ok=True)


# --- Item decode -------------------------------------------------------------


def label_names(issue: dict) -> list[str]:
    """Extract label name strings from an issue's ``labels`` (objects or strings)."""
    out: list[str] = []
    for label in issue.get("labels") or []:
        if isinstance(label, dict):
            name = label.get("name")
        else:
            name = label
        if name:
            out.append(name)
    return out


def _facet_value(labels: list[str], facet: str) -> str | None:
    prefix = f"{facet}:"
    for name in labels:
        if name.startswith(prefix):
            return name[len(prefix) :]
    return None


def _facet_values(labels: list[str], facet: str) -> list[str]:
    prefix = f"{facet}:"
    return [name[len(prefix) :] for name in labels if name.startswith(prefix)]


def decode_status(issue: dict, labels: list[str]) -> tuple[str, list[str]]:
    """Decode the ``status`` axis with fail-open precedence (Data Model §4).

    For a closed issue ``state_reason`` is authoritative; for an open issue the
    ``status:`` label decides (``in-progress`` > ``submitted`` > none = open).
    An unknown/torn state decodes to a safe value with a warning — never a reject.
    Returns ``(status, warnings)``.
    """
    warnings: list[str] = []
    state = (issue.get("state") or "open").lower()
    if state == "closed":
        reason = (issue.get("state_reason") or "").lower()
        if reason == "completed":
            status = "shipped"
        elif reason == "not_planned":
            status = "dropped"
        elif reason == "duplicate":
            status = "dropped"  # superseded_by is read from the timeline (Chunk 05+)
        else:
            status = "dropped"  # fail-open: a closed issue is not open work
            if reason:
                warnings.append(
                    f"closed issue has unrecognized state_reason {reason!r}; decoded as dropped"
                )
        if _facet_value(labels, "status"):
            warnings.append(
                "closed issue still carries a status: label (meaningless once closed; "
                "reconciliation strips it)"
            )
        return status, warnings

    # Open issue: status: label precedence.
    present = _facet_values(labels, "status")
    if not present:
        return "open", warnings
    if "in-progress" in present:
        status = "in-progress"
    elif "submitted" in present:
        status = "submitted"
    else:
        # An unknown open status: label — fail open to "open", flag it.
        status = "open"
        warnings.append(
            f"open issue carries unrecognized status label(s) {present!r}; decoded as open"
        )
    if len(present) > 1:
        warnings.append(
            f"open issue carries multiple status labels {present!r}; highest precedence wins"
        )
    return status, warnings


def decode_item(issue: dict, *, canonical_id: str | None = None) -> tuple[dict, list[str]]:
    """Decode a GitHub issue JSON into the item projection (Data Model §1.1).

    The two axes are decoded independently (DM2, ENC-2): ``status`` from
    state/``state_reason``/``status:`` label, ``stage`` from the ``stage:`` label
    only. Soft-enum facets and the ``prawduct:`` block ride along. Returns
    ``(item, warnings)``.
    """
    warnings: list[str] = []
    labels = label_names(issue)

    status, status_warnings = decode_status(issue, labels)
    warnings.extend(status_warnings)

    block = parse_block(issue.get("body"))
    warnings.extend(block.warnings)

    assignees = issue.get("assignees")
    if assignees:
        assignee = (assignees[0] or {}).get("login") if isinstance(assignees[0], dict) else assignees[0]
    elif isinstance(issue.get("assignee"), dict):
        assignee = issue["assignee"].get("login")
    else:
        assignee = None

    item = {
        "id": canonical_id,
        "number": issue.get("number"),
        "node_id": issue.get("node_id"),
        "title": issue.get("title"),
        "body": issue.get("body"),
        "status": status,
        "stage": _facet_value(labels, "stage"),
        "kind": _facet_value(labels, "kind"),
        "area": _facet_value(labels, "area"),
        "effort": _facet_value(labels, "effort"),
        "impact": _facet_value(labels, "impact"),
        "source": _facet_value(labels, "source"),
        "assignee": assignee,
        "url": issue.get("html_url"),
        "labels": labels,
        "id_aliases": block.id_aliases(),
        "block_version": block.version(),
    }
    return item, warnings
