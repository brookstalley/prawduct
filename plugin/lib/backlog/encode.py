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

import json
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

#: The one stage that means *buildable*. `stage` is a maturity ladder and only
#: this rung is implementable — the requirements-precede-code guard — so
#: ready-work queries key on this rather than on a bare literal of their own.
#: Written out rather than derived from ``STAGE_VALUES[-1]``: a ladder that later
#: gains a rung beyond `ready` must not silently promote it to buildable. A test
#: asserts the membership this deliberately does not enforce in code.
READY_STAGE: str = "ready"
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
#: Statuses whose GitHub state is `open` — the "pending work" set consumers sum
#: over (the briefing rollup). Derived from the SoT so it can never drift.
OPEN_STATUSES: tuple[str, ...] = tuple(
    status for status, (state, _reason, _label) in _STATUS_ENCODING.items() if state == "open"
)

# Facets carried as `<facet>:value` labels (Data Model §3). `kind/area/effort/
# impact/source` are open soft enums (any value accepted); `stage` has a known
# vocabulary (unknown → warning); `status` is closed (unknown → hard reject).
OPEN_FACETS: tuple[str, ...] = ("kind", "area", "effort", "impact", "source")

#: The one **multi-valued** facet. Every other facet is exactly-one and its
#: writer is a label *swap*; `tag:` accumulates instead.
#:
#: `tags` is folksonomy where `area` is taxonomy: `area` is exactly-one and wired
#: to the title by ``normalize_title(title, area)``, which is what makes a list
#: scannable, so ad-hoc per-team metadata has nowhere to go without this. It is
#: namespaced like every other prawduct label (GV6) — a bare `perf` label would
#: collide with whatever a repo already calls its own.
#:
#: **Binding rule: nothing ever gates on tags.** No check, gate, verdict or
#: refusal may read them. That rule is the entire reason synonym drift
#: (`perf`/`performance`/`speed`) is harmless here rather than corrosive, and it
#: is stated at the constant deliberately: it has to arrive before the first
#: check someone would otherwise be tempted to build on them.
TAG_FACET: str = "tag"

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
    # Multi-valued folksonomy (TAG_FACET). Listing it here widens
    # `is_prawduct_issue` — an issue carrying nothing but a `tag:` label is ours
    # — which is the intended reading: a tag is prawduct metadata, so an item
    # someone tagged and never faceted is still an item, not a plain repo issue.
    "tag:",
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

    def affected(self) -> list[str]:
        """The structured path list — what code this item touches, no prose.

        Block-authoritative and unmirrored. Read **tolerantly**, the same posture
        as every other block field: entries are normalized (see
        :func:`normalize_affected`) and nothing is ever rejected here. The hard
        rejection lives on the write path (:func:`validate_affected`), because a
        body someone hand-edited into prose must still decode to *something* a
        reader can see rather than failing the whole item.
        """
        return normalize_affected(parse_list(self.fields.get("affected")))

    def working_branch(self) -> str | None:
        """The repo-qualified branch someone is working this item on, or ``None``.

        **The block key is ``working_branch``; the domain and CLI spelling is
        ``working-branch``** (``--working-branch``). The block's keys are
        snake_case throughout (``id_aliases``, ``superseded_by``,
        ``original_title``) and block keys are additive-only-forever (Data Model
        §7) — the spelling chosen here is the spelling always, so it matches its
        neighbours rather than the flag. This accessor is the one place the two
        spellings meet.
        """
        value = self.fields.get("working_branch")
        return value.strip() if value and value.strip() else None

    def get(self, key: str) -> str | None:
        return self.fields.get(key)

    def reserialize(self) -> str:
        return _emit_block(self.fields)


def parse_block(body: str | None) -> Block:
    """Parse the ``prawduct:`` block out of an issue body (tolerant).

    Zero blocks → an empty ``Block`` (all defaults, no warning). Two+ blocks →
    the **last** wins and each earlier one is flagged (ENC-3). A malformed inner
    line (no ``:`` separator) is skipped with a warning, never an error.

    **This READER and the WRITERS deliberately disagree about a two-block
    body.** Reading keeps the last block (a body someone edited twice means the
    later value); writing — every caller of
    :func:`merge_all_block_fields` — merges every block, because a write that kept only the last would *persist*
    the discard and, since it emits exactly one block, destroy the very
    multi-block warning that was the discard's only signal. Reading is
    non-destructive and writing is not, which is why the same input gets two
    readings on purpose.
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

    fields, malformed = _parse_block_fields(matches[-1], collect_malformed=True)
    block.fields.update(fields)
    block.warnings.extend(f"ignored malformed block line: {m!r}" for m in malformed)
    return block


def _parse_block_fields(
    inner: str, collect_malformed: bool = False
) -> "dict[str, str] | tuple[dict[str, str], list[str]]":
    """Field dict for ONE block's inner text; last occurrence of a key wins.

    Split out of :func:`parse_block` so :func:`merge_all_block_fields` can
    merge *every* block in a body rather than only the last — the reader and
    the writers need the same line grammar and must not drift on what counts
    as a field.
    """
    fields: dict[str, str] = {}
    malformed: list[str] = []
    for raw_line in inner.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue  # blank or comment — not a field
        key, sep, value = line.partition(":")
        key = key.strip()
        if not sep or not key:
            malformed.append(stripped)
            continue
        fields[key] = value.strip()
    return (fields, malformed) if collect_malformed else fields


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
    (Data Model §2) — ``update`` sets ``working_branch``/``affected`` through it,
    ``merge`` sets ``superseded_by``. Creates a
    fresh ``v: 1`` block if the body had none and a value is being set; clearing a
    field on a blockless body is a no-op (never manufactures an empty block).
    """
    # Merges EVERY block, for the same reason :func:`compose_body` does: pairing
    # `parse_block` (last-block-wins) with `strip_block` (removes them all) drops
    # an earlier block's fields, and since the result emits exactly one block the
    # multi-block warning can never fire afterwards to signal it. This is that
    # defect one function over — swept with it rather than left for the body that
    # happens to carry two hand-written blocks.
    fields = merge_all_block_fields(body)
    human = strip_block(body)
    if value is None:
        fields.pop(key, None)
    else:
        fields[key] = value
    if not fields:
        return human
    rendered = serialize_block(fields)
    if human:
        return f"{human}\n\n{rendered}\n"
    return f"{rendered}\n"


#: Block fields that describe WHO FILED an item rather than what it is. A body
#: never gets to assert these: they are stamped by the command from its own
#: invocation context, so :func:`compose_body` drops them from any block found
#: in the caller's text before merging. Every other field is the filer's.
_CALLER_OWNED_FIELDS = frozenset({"automated", "worker"})


def merge_all_block_fields(body: str | None) -> dict[str, str]:
    """Every ``prawduct:`` block in ``body``, merged in document order.

    **The one home for how a WRITER reads a body's blocks**, and it exists
    because this defect has now been found at three separate sites. The trap is
    a pairing that looks correct at each one: :func:`parse_block` keeps the LAST
    block, :func:`strip_block` removes them ALL, and the writer emits exactly
    one — so an earlier block's fields are dropped *and* the "carries N prawduct
    blocks" warning that was the only signal can never fire afterwards. The loss
    is silent and permanent.

    Reading and writing diverge here on purpose (:func:`parse_block` says why),
    so the divergence needs a named home rather than three open-coded copies.
    Later blocks win over earlier ones, matching last-block-wins, so a body that
    was edited twice still means its later value.
    """
    fields: dict[str, str] = {}
    for inner in _BLOCK_RE.findall(body or ""):
        fields.update(_parse_block_fields(inner))
    return fields


def compose_body(human: str | None, block_fields: dict[str, str]) -> str:
    """Compose an issue body from human text + a fresh ``prawduct:`` block's fields.

    The **single** body↔block attachment framing (serialize + the blank-line
    separator) that ``export`` round-trips depend on — every writer that emits a
    fresh block (``file``, ``import``) goes through here, so the separator/newline
    convention lives in exactly one place and the two paths can never silently
    diverge (Data Model §2). An empty human body yields the block alone.

    **A block already in ``human`` is MERGED, not buried.** Filers write their
    own ``prawduct:`` block into the body, and this used to append a second one
    beside it. (The docs steer filers to the flags and ``link`` instead, and
    still do — but "the docs told you not to" is no reason for a silent data
    loss, and the warning it produced reads like housekeeping.) Parsing is last-block-wins, so the filer's fields were then silently
    discarded and the loss surfaced only as a warning that reads cosmetic
    ("issue body carries 2 prawduct blocks; using the last"). Three items filed
    on 2026-08-19 (#690, #691, #692) lost their ``related:`` edges exactly this
    way. Fixed here, at the point of composition, rather than by asking filers
    to omit a block the docs tell them to write.

    **Precedence: the fresh fields win a key collision**, and the filer's other
    fields survive untouched. The caller's fields are the authoritative stamps,
    so a body claiming ``automated: false`` cannot launder a background sweep
    into looking human.

    The attribution stamps are stripped from the embedded block **in both
    directions**, which precedence alone does not cover: an *attended* create
    passes only ``{"v": "1"}``, so with a plain merge a body that self-declared
    ``automated: true`` would face no colliding key and survive — misattributing
    a human's filing to a sweep. These two keys describe *who filed this*, which
    is never something the filed text gets to assert; every other block field is
    the filer's to set.
    """
    # EVERY block in the body is merged, in document order, not just the last.
    # `parse_block` keeps only the last (its own last-block-wins rule) while
    # `strip_block` removes them ALL — so merging via `parse_block` would still
    # drop an earlier block's fields, and now silently: the composed body emits
    # exactly one block, so the downstream "carries N prawduct blocks" warning
    # that was the losses' only signal can never fire again. Merging all of them
    # means nothing is lost, which is better than restoring a warning about a
    # loss. Later blocks win over earlier ones, matching last-block-wins.
    merged = merge_all_block_fields(human)
    for key in _CALLER_OWNED_FIELDS:
        merged.pop(key, None)
    text = strip_block(human)
    merged.update(block_fields)
    rendered = serialize_block(merged)
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


def format_text(text: str) -> str:
    """Render arbitrary (possibly multi-line) text as a single-line block value.

    JSON-string encoding: the block is line-based ``key: value`` (§2), so a
    multi-line value like ``original_body`` must collapse to one line — and the
    escaping also keeps a backtick fence inside the text from ever starting a
    line and closing the block fence. Verbatim-recoverable via
    :func:`parse_text`."""
    return json.dumps(text, ensure_ascii=False)


def parse_text(raw: str | None) -> str | None:
    """Decode a :func:`format_text` block value back to the exact original text.

    ``None``/empty → ``None``. A value that is not a JSON string (hand-edited or
    pre-encoding) is returned as-is — tolerant parse, same posture as the rest of
    the block."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    if text.startswith('"'):
        try:
            decoded = json.loads(text)
        except ValueError:
            return text
        if isinstance(decoded, str):
            return decoded
    return text


def parse_iso(ts: str | None) -> "datetime | None":
    """Parse an ISO-8601 timestamp (tolerant of a trailing ``Z``); assume UTC when
    naive. Returns ``None`` for a missing/unparseable value — a fail-open its
    callers rely on: a date predicate a stamp cannot honestly satisfy declines
    rather than guessing at one side of it."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# --- affected / tags / working-branch ----------------------------------------
#
# The three fields the cache specification adds to the domain model. Two live in
# the `prawduct:` block (`affected`, `working_branch`) and one lives in labels
# (`tag:`), so nothing here is a cache-only field — drop the cache, rebuild from
# the provider, and all three come back.
#
# Read tolerantly, written strictly. The parse/normalize half never rejects, so a
# hand-edited body still decodes; the `validate_*` half is the write path's guard
# and returns a message rather than raising (project preference: envelopes, not
# exceptions).

#: What an `affected` entry may not contain once normalized. Whitespace is the
#: prose tell — "the sync path and its tests" is a sentence, `plugin/lib/sync.py`
#: is a path — and a comma is the block's own list separator, so an entry
#: carrying one could never round-trip.
_AFFECTED_FORBIDDEN = (" ", "\t", ",")

#: Wrappers a writer naturally reaches for around a path. Stripped rather than
#: rejected: a model emitting `` `plugin/lib/sync.py` `` means the same path, and
#: incidental strictness at a model-output seam is a latent fail-close.
_AFFECTED_WRAPPERS = "`'\"" + "“”‘’"

#: Glob metacharacters. Entries are exact paths or directory prefixes — never
#: patterns — so `plugin/lib/**` is not a broader match, it is a literal that
#: matches nothing forever: a silent NEGATIVE in the one query this field exists
#: to serve, and the mirror of the stale positive the index's delete prevents.
#: Refused at the same seam that refuses prose, with the working form named.
_AFFECTED_GLOB_CHARS = "*?[]"


def normalize_affected(entries: list[str]) -> list[str]:
    """Canonicalize `affected` entries. Never rejects — see the section note.

    Four normalizations, each collapsing a spelling that means the same path:
    surrounding quotes/backticks are stripped, a leading ``./`` or ``/`` is
    removed (entries are repo-relative), and a trailing ``/`` is dropped so
    ``plugin/lib/`` and ``plugin/lib`` are one entry rather than two that match
    identically. Empty entries disappear.
    """
    out: list[str] = []
    for raw in entries:
        value = (raw or "").strip().strip(_AFFECTED_WRAPPERS).strip()
        while value.startswith("./"):
            value = value[2:]
        value = value.lstrip("/").rstrip("/")
        if value and value not in out:
            out.append(value)
    return out


def validate_affected(entries: list[str]) -> tuple[list[str], str | None]:
    """Normalize and check `affected` for the write path.

    Returns ``(normalized, error_message_or_None)``. The one rejection is prose:
    an entry that still carries whitespace or a comma after normalization is not
    a path, and the message says where prose belongs instead. That boundary is
    the field's whole reason for existing — `refs` already mixes artifacts with
    paths and annotations, which is exactly why it can never be matched against a
    changed-file set (Cache Spec §3).
    """
    normalized = normalize_affected(entries)
    bad = [e for e in normalized if any(ch in e for ch in _AFFECTED_FORBIDDEN)]
    if bad:
        return normalized, (
            f"`affected` takes repo-relative paths only, no prose — rejected {bad!r}. "
            "Put the annotation in the item body and leave a bare path here "
            "(e.g. plugin/lib/backlog/sync.py, or plugin/lib/backlog for the directory)."
        )
    globbed = [e for e in normalized if any(ch in e for ch in _AFFECTED_GLOB_CHARS)]
    if globbed:
        return normalized, (
            f"`affected` takes paths, not patterns — rejected {globbed!r}. A directory "
            "entry already covers everything under it, so write `plugin/lib/backlog` "
            "rather than `plugin/lib/backlog/**`."
        )
    return normalized, None


def path_ancestors(path: str) -> list[str]:
    """Every `affected` entry a changed file answers to: itself, then each
    ancestor directory.

    This is what makes the intersection an **equality** match, which is what an
    index can serve. The natural phrasing — does any entry prefix this path —
    runs ``? LIKE path || '%'``, whose variable side is the wrong one for an
    index on ``path``; expanding the changed file into its ancestors inverts it
    into ``path IN (…)``. Changed sets are diffs and paths are shallow, so the
    expansion is small.

    Entries are exact paths or directory prefixes — **not globs.** A glob would
    reintroduce the unindexable direction and buys nothing a directory prefix
    does not already give.
    """
    value = normalize_affected([path])
    if not value:
        return []
    parts = value[0].split("/")
    return ["/".join(parts[: i + 1]) for i in range(len(parts))][::-1]


def affected_matches(entries: list[str], changed_paths) -> list[str]:
    """The `affected` entries touched by ``changed_paths`` (consumers 1 and 4).

    The set intersection that replaces a reviewer reading item text and
    inferring. Empty means this item claims no overlap with the change — which
    is a different answer from *this item records no paths*, and the caller that
    cares must check ``entries`` itself rather than reading emptiness as either.
    """
    keys: set[str] = set()
    for path in changed_paths:
        keys.update(path_ancestors(path))
    return [entry for entry in normalize_affected(entries) if entry in keys]


#: The longest a `tag:`-prefixed label may be. GitHub caps a label name at 50
#: characters, and a tag that cannot become a label is a tag that cannot be
#: written — better refused at the seam than discovered as a 422.
_MAX_LABEL_NAME = 50


def normalize_tags(values: list[str]) -> list[str]:
    """Canonicalize a tag set: trimmed, de-duplicated, **sorted**.

    Sorted because tags are a set — order carries no meaning — and because the
    provider returns labels in its own order, which would otherwise make the
    cache's stored spelling depend on label creation order and turn
    rebuild-equivalence into a flaky comparison of the same fact.
    """
    seen: list[str] = []
    for raw in values:
        value = (raw or "").strip()
        if value and value not in seen:
            seen.append(value)
    return sorted(seen)


def validate_tags(values: list[str]) -> tuple[list[str], str | None]:
    """Normalize and check a tag set for the write path.

    Returns ``(normalized, error_message_or_None)``. There is deliberately **no
    vocabulary check** — an open folksonomy has nothing to be unknown against,
    and the binding rule that nothing gates on tags is what makes that safe
    (:data:`TAG_FACET`). The only rejections are structural: a comma (the block
    and CLI list separator) and a value too long to become a label.
    """
    normalized = normalize_tags(values)
    for value in normalized:
        if "," in value:
            return normalized, f"a tag may not contain a comma (it separates tags): {value!r}"
        if len(f"{TAG_FACET}:{value}") > _MAX_LABEL_NAME:
            return normalized, (
                f"tag {value!r} is too long — `{TAG_FACET}:<tag>` must fit "
                f"{_MAX_LABEL_NAME} characters"
            )
    return normalized, None


#: Characters git's own `check-ref-format` forbids in a branch name, plus a
#: leading `-` (which a CLI would read as a flag). Enforced here rather than left
#: to the provider because this value is interpolated into a REST path: without
#: it `owner/repo@../../../user` parses clean, resolves a *different* endpoint,
#: and gets stored as a verified working branch — the pushed-ref control failing
#: **open**, which is precisely the invisible claim it exists to prevent.
_REF_FORBIDDEN_CHARS = "~^:?*[\\"


def _is_valid_branch_name(branch: str) -> bool:
    """Whether ``branch`` is a name git would accept (``check-ref-format``).

    Not a security boundary on its own — the call is list-form with no shell, the
    token is the caller's own, and the request is a GET returning one bit. It is
    a *correctness* boundary: a name git could never create cannot be a pushed
    ref, so accepting one can only ever mean the check passed on something else.
    """
    if not branch or branch != branch.strip():
        return False
    if any(ch in branch for ch in _REF_FORBIDDEN_CHARS):
        return False
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in branch):
        return False
    if ".." in branch or "@{" in branch or "//" in branch:
        return False
    if branch.startswith(("/", "-", ".")) or branch.endswith(("/", ".", ".lock")):
        return False
    if branch == "@":
        return False
    # No path component may start with `.` or end with `.lock` — the rule applies
    # per segment, not only to the whole name.
    return all(
        segment and not segment.startswith(".") and not segment.endswith(".lock")
        for segment in branch.split("/")
    )


def parse_working_branch(value: str | None) -> tuple[str, str, str] | None:
    """Split ``owner/repo@branch`` into ``(owner, repo, branch)``, or ``None``.

    **Repo-qualified because ``backlog_service_repo`` can differ from the code
    repo** (Cache Spec §3) — an unqualified branch name names nothing on the
    machine that has to go and look at it. ``@`` is the separator because
    ``owner/repo`` cannot contain one, so splitting on the *first* ``@`` is
    unambiguous even for a branch called ``feat/a@b`` or ``feat/a/b``.

    The branch is held to git's ref rules (:func:`_is_valid_branch_name`) and the
    repo to a single ``owner/repo`` pair, because both segments are interpolated
    into a provider URL path downstream.
    """
    if not value:
        return None
    text = value.strip()
    left, sep, branch = text.partition("@")
    if not sep:
        return None
    owner, slash, repo = left.partition("/")
    branch = branch.strip()
    if not (owner and slash and repo and branch):
        return None
    if "/" in repo or any(ch.isspace() for ch in text):
        return None
    # A dot is legal in a repo name (`docs.github.com`, `foo.js`), so only the
    # traversal sequence and the path-metacharacters are refused — the same
    # failing-open concern as the branch, one path segment up.
    if any(ch in owner or ch in repo for ch in _REF_FORBIDDEN_CHARS):
        return None
    if ".." in owner or ".." in repo:
        return None
    if not _is_valid_branch_name(branch):
        return None
    return owner, repo, branch


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


def is_pull_request(issue: dict) -> bool:
    """Whether a raw issues-list entry is a pull request (the ``pull_request``
    key GitHub stamps on interleaved PRs). The one greppable home for the
    predicate — decode filtering and the label-keyed lookups all route here
    (BKL-5T3J)."""
    return "pull_request" in issue


def is_prawduct_issue(issue: dict) -> bool:
    """Whether a GitHub issue is an in-scope prawduct backlog item (PROV-2/GV6).

    An item is ours if it carries any prawduct-namespaced label *or* a
    ``prawduct:`` body block (a natively-filed item with no facets still carries
    the block). A plain repo issue with neither is out-of-scope — ``list``/decode
    ignore it (not malformed, just not ours). The SEC-7 anonymous-quarantine case
    (an unlabeled non-collaborator filing surfaced to triage rather than ignored)
    is a separate governance path and is **not** decided here.

    A **pull request** is never an item, even when someone has stuck a
    prawduct-namespaced label on it — the REST issues list interleaves PRs
    (returned raw by the transport so pagination terminators stay honest,
    BKL-5T3J), and this predicate is where they leave the pipeline.
    """
    if is_pull_request(issue):
        return False
    labels = label_names(issue)
    if any(name.startswith(prefix) for name in labels for prefix in NAMESPACED_LABEL_PREFIXES):
        return True
    return has_block(issue.get("body"))


def facet_value(labels: list[str], facet: str) -> str | None:
    """The value of the first ``<facet>:value`` label, or ``None``. The single
    facet-label scan (shared by decode, the linter, and the restructure
    pre-pass — one implementation, not per-module copies)."""
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
        if facet_value(labels, "status"):
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
        "stage": facet_value(labels, "stage"),
        "kind": facet_value(labels, "kind"),
        "area": facet_value(labels, "area"),
        "effort": facet_value(labels, "effort"),
        "impact": facet_value(labels, "impact"),
        "source": facet_value(labels, "source"),
        "assignee": assignee,
        # The three fields Cache Spec §3 adds. `tags` is label-authoritative and
        # multi-valued; `affected` and `working_branch` are block-authoritative.
        # All three decode tolerantly — the write path is where they are refused.
        "tags": normalize_tags(_facet_values(labels, TAG_FACET)),
        "affected": block.affected(),
        "working_branch": block.working_branch(),
        "automated": block.get("automated") == "true",
        "url": issue.get("html_url"),
        "labels": labels,
        "id_aliases": block.id_aliases(),
        "superseded_by": block.superseded_by(),
        "block_version": block.version(),
    }
    return item, warnings
