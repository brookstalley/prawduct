"""Encoding: the ``prawduct:`` block, soft enums, item decode, and status encoding.

Four concerns, all pure (a function-level seam — Test Specs §2.1; no transport):

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
   are never flattened (DM2); ``decode_status`` resolves torn/multi-label states by
   documented fail-open precedence but does not itself mutate.

4. **Status encoding** — the write-side inverse of ``decode_status``:
   ``_STATUS_ENCODING`` (the single source of truth) + ``encode_status`` map each
   status to its ``(state, state_reason, status_label)`` shape (ENC-2), and
   ``reconcile_status_labels`` is the pure label-derivation both the ``set-status``
   transition and the self-heal apply (Data Model §4). Still pure — the mutation
   itself lives in ``core.set_status`` over the transport.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone

# --- Vocabularies ------------------------------------------------------------

STAGE_VALUES: tuple[str, ...] = (
    "idea",
    "research",
    "requirements",
    "design",
    "ready",
)
# The status axis has ONE canonical GitHub encoding per value (Data Model §4) — the
# single source of truth: open sub-states live only in the `status:` label; closed
# states live in `state_reason`; `open`/`shipped`/`dropped` carry no status label. An
# unknown status is a hard reject. STATUS_VALUES / STATUS_OPEN_LABELS derive from it,
# so the vocabulary can never drift from the encoding.
_STATUS_ENCODING: "OrderedDict[str, tuple[str, str | None, str | None]]" = OrderedDict(
    # status        (state,   state_reason,  status: label)
    (
        ("submitted", ("open", None, "status:submitted")),
        ("open", ("open", None, None)),
        ("in-progress", ("open", None, "status:in-progress")),
        ("shipped", ("closed", "completed", None)),
        ("dropped", ("closed", "not_planned", None)),
    )
)
#: The full status vocabulary (closed set), stable order — derived from the SoT.
STATUS_VALUES: tuple[str, ...] = tuple(_STATUS_ENCODING)
#: Open sub-states that live *only* in a `status:` label (Data Model §4).
STATUS_OPEN_LABELS: tuple[str, ...] = tuple(
    status for status, (_state, _reason, label) in _STATUS_ENCODING.items() if label is not None
)

# Facets carried as `<facet>:value` labels (Data Model §3). `kind/area/effort/
# impact/source` are open soft enums (any value accepted); `stage` has a known
# vocabulary (unknown → warning); `status` is closed (unknown → hard reject).
OPEN_FACETS: tuple[str, ...] = ("kind", "area", "effort", "impact", "source")

# The prawduct-namespaced label prefixes (Data Model §3). An issue carrying *any*
# of these — or a `prawduct:` body block — is an in-scope backlog item; one with
# neither is a plain repo issue the adapter ignores as out-of-scope (PROV-2/GV6).
NAMESPACED_LABEL_PREFIXES: tuple[str, ...] = (
    "stage:",
    "status:",
    "kind:",
    "area:",
    "effort:",
    "impact:",
    "source:",
    "id:",
    "verified:",
    "superseded-by:",
    "import-key:",  # idempotency-only marker for an id-less imported item (Data Model §5)
)

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
        return parse_list(self.fields.get("id_aliases"))

    def superseded_by(self) -> str | None:
        """The merge/transfer redirect target (Data Model §1.2 — block-authoritative,
        unmirrored), or ``None``. A ref to a merged-away source resolves *through*
        this to its survivor (``ids.resolve_redirect``); the ``merge`` op writes it
        **before** closing the source so a crash leaves the source open-but-redirected
        (a valid, resolvable state — CRASH-2)."""
        value = self.fields.get("superseded_by")
        return value or None

    def claimed_at(self) -> str | None:
        """The ``claimed_at`` visible-staleness stamp (CC3), or ``None``.

        Block-authoritative and unmirrored (Data Model §1.2): the claim's
        timestamp lives only here, so ``pick``'s TTL reap reads it from the body.
        """
        value = self.fields.get("claimed_at")
        return value or None

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


def strip_block(body: str | None) -> str:
    """Return an issue body with any ``prawduct:`` block removed (human text only).

    Used when a caller replaces the body: the block is body-authoritative and is
    preserved separately, so a block the caller happens to paste into the new text
    is dropped to avoid a duplicate (last-block-wins parse, Data Model §2).
    """
    if not body:
        return ""
    return _BLOCK_RE.sub("", body).rstrip("\n")


def has_block(body: str | None) -> bool:
    """Whether ``body`` carries a ``prawduct:`` block (the native-filed marker)."""
    return bool(body) and _BLOCK_RE.search(body) is not None


def upsert_block_field(body: str | None, key: str, value: str | None) -> str:
    """Return ``body`` with the block's ``key`` set to ``value`` (or removed when
    ``value`` is ``None``), preserving the human text and every other block field.

    The single primitive for editing one block-authoritative field in place
    (Data Model §2): claim stamps ``claimed_at``, unclaim clears it. Creates a
    fresh ``v: 1`` block if the body had none and a value is being set; clearing a
    field on a blockless body is a no-op (never manufactures an empty block).
    """
    block = parse_block(body)
    human = strip_block(body)
    if value is None:
        block.fields.pop(key, None)
    else:
        block.fields[key] = value
    if not block.fields:
        return human
    rendered = serialize_block(block.fields)
    if human:
        return f"{human}\n\n{rendered}\n"
    return f"{rendered}\n"


def compose_body(human: str | None, block_fields: dict[str, str]) -> str:
    """Compose an issue body from human text + a fresh ``prawduct:`` block's fields.

    The **single** body↔block attachment framing (serialize + the blank-line
    separator) that ``export`` round-trips depend on — every writer that emits a
    fresh block (``file``, ``import``) goes through here, so the separator/newline
    convention lives in exactly one place and the two paths can never silently
    diverge (Data Model §2). An empty human body yields the block alone.
    """
    rendered = serialize_block(block_fields)
    text = (human or "").rstrip("\n")
    if text:
        return f"{text}\n\n{rendered}\n"
    return f"{rendered}\n"


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


def parse_list(raw: str | None) -> list[str]:
    """Parse a block list value (``[a, b]`` or bare ``a, b``) into ``[a, b]``."""
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


def format_list(items: list[str]) -> str:
    """Render a list of values as the block's ``[a, b]`` form (inverse of
    :func:`parse_list`)."""
    return "[" + ", ".join(items) + "]"


def parse_iso(ts: str | None) -> "datetime | None":
    """Parse an ISO-8601 timestamp (tolerant of a trailing ``Z``); assume UTC when
    naive. Returns ``None`` for a missing/unparseable value — a fail-open the
    callers rely on (a claim whose stamp cannot be aged is treated as live, never
    wrongly reaped)."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


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


def is_prawduct_issue(issue: dict) -> bool:
    """Whether a GitHub issue is an in-scope prawduct backlog item (PROV-2/GV6).

    An item is ours if it carries any prawduct-namespaced label *or* a
    ``prawduct:`` body block (a natively-filed item with no facets still carries
    the block). A plain repo issue with neither is out-of-scope — ``list``/decode
    ignore it (not malformed, just not ours). The SEC-7 anonymous-quarantine case
    (an unlabeled non-collaborator filing surfaced to triage rather than ignored)
    is a separate governance path and is **not** decided here.
    """
    labels = label_names(issue)
    if any(name.startswith(prefix) for name in labels for prefix in NAMESPACED_LABEL_PREFIXES):
        return True
    return has_block(issue.get("body"))


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
            status = "dropped"  # superseded_by is read from the timeline (not yet implemented)
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


# --- status encoding (the write-side inverse of decode_status) ---------------
# (The `_STATUS_ENCODING` source of truth + STATUS_VALUES/STATUS_OPEN_LABELS are
# defined at the top under Vocabularies; these are the functions over it.)


def encode_status(status: str) -> tuple[str, str | None, str | None]:
    """Map a ``status`` value to its GitHub encoding ``(state, state_reason,
    status_label)`` — the write-side inverse of :func:`decode_status` (ENC-2).

    ``state`` is ``"open"``/``"closed"``; ``state_reason`` is set only for closed
    states; ``status_label`` is set only for the open sub-states ``submitted`` /
    ``in-progress`` (``open``/``shipped``/``dropped`` carry none — Data Model §4).
    Raises ``KeyError`` for an unknown status (callers validate first).
    """
    return _STATUS_ENCODING[status]


def canonical_status_label(status: str) -> str | None:
    """The single ``status:`` label a given status should carry, or ``None``."""
    return _STATUS_ENCODING[status][2]


def status_labels_present(labels: list[str]) -> list[str]:
    """The ``status:`` labels currently on an issue, full names, source order."""
    return [f"status:{value}" for value in _facet_values(labels, "status")]


def reconcile_status_labels(
    present_status_labels: list[str], keep: str | None
) -> tuple[list[str], list[str]]:
    """Re-derive the canonical ``status:`` label set (Data Model §4): given the
    labels present and the ONE that should remain (``keep``, or ``None`` for a closed
    issue / plain ``open``), return ``(to_add, to_remove)`` — the canonical label to
    add if missing, and every other present ``status:`` label to strip.

    The single reconciliation primitive shared by both writers: a **set-status**
    transition passes ``keep = canonical_status_label(target)`` (may need the add);
    a **self-heal** of a torn/multi-label state passes ``keep =
    canonical_status_label(decoded_current)`` (``to_add`` is empty — the decoded
    label is already present — and only losers are stripped).
    """
    to_add = [keep] if (keep and keep not in present_status_labels) else []
    to_remove = [name for name in present_status_labels if name != keep]
    return to_add, to_remove


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
        "claimed_at": block.claimed_at(),
        "automated": block.get("automated") == "true",
        "url": issue.get("html_url"),
        "labels": labels,
        "id_aliases": block.id_aliases(),
        "superseded_by": block.superseded_by(),
        "block_version": block.version(),
    }
    return item, warnings
