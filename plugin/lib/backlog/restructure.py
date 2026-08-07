"""MG6 migration restructure pre-pass — deterministic plan application + preview.

Implements issue-standard §5 ("restructure, preserve, no split", owner decision
2026-07-17): the model *proposes* a restructure plan (new titles / template
bodies / ``kind:`` backfills) during the MG4 scrub, the owner confirms the batch
in aggregate, and THIS module applies the confirmed plan to the parsed
:class:`~lib.backlog.migrate.ImportRecord` set — before the deterministic import
writes anything (no model in the data plane, MIG-5/G1).

**No model, ever (INV-1).** A plan is data: this module validates it
(fail-closed — a typo'd PFX or unknown key must not silently drop a confirmed
rewrite on an irreversible run), applies it (title via
:func:`issuefmt.normalize_title`, body via :func:`issuefmt.render_body` so a
migrated body and a net-new one are byte-identical in layout), stashes the
original verbatim (``original_title`` / ``original_body`` block fields —
recoverable via :func:`encode.parse_text` — plus the MG2 export backup), and
audits the result with :func:`issuefmt.lint`. Body/label findings are advisory;
the four §1 TITLE findings are what `import`'s pre-flight REFUSES on, so a plan
carrying one cannot be imported (`migrate.preflight_titles`).

**Non-atomic items are flagged, never split** — splitting mints new IDs and is
an owner scrub decision (1 PFX = 1 issue, MG1/MIG-2). The flag rides the plan
(``non_atomic``) and surfaces in the preview; application ignores it.

The plan applies **at create**: the importer is skip-if-exists, so an item
already on GitHub is never rewritten by a re-run with a new plan (no surprise
mutations — the restructure is part of the create, not an edit pass).
"""

from __future__ import annotations

import json

from . import encode, issuefmt

# Plan schema (v1). Keys an item entry may carry — anything else is a hard
# validation error: on an irreversible run, an unrecognized key is far more
# likely a typo'd rewrite than a forward-compat extension.
_ENTRY_KEYS: frozenset[str] = frozenset(
    {"title", "kind", "sections", "non_atomic", "note"}
)


def parse_plan(text: str) -> tuple[dict | None, str | None]:
    """Parse + validate a restructure plan JSON document → ``(plan, error)``.

    Shape: ``{"v": 1, "items": {"<PFX>": {title?, kind?, sections?, non_atomic?,
    note?}}}``. Validation is fail-closed (see module docstring); an entry with
    only ``non_atomic``/``note`` (flag-only, no rewrite) is valid.
    """
    try:
        doc = json.loads(text)
    except ValueError as exc:
        return None, f"restructure plan is not valid JSON: {exc}"
    if not isinstance(doc, dict):
        return None, "restructure plan must be a JSON object"
    if doc.get("v") not in (1, "1"):
        # "1" tolerated: the repo's own block convention serializes v as a string,
        # so the string spelling is a natural variant, not an ambiguity.
        return None, "restructure plan must declare \"v\": 1"
    items = doc.get("items")
    if not isinstance(items, dict) or not items:
        return None, "restructure plan must carry a non-empty \"items\" object"
    for pfx, entry in items.items():
        err = _validate_entry(pfx, entry)
        if err:
            return None, err
    return doc, None


def _validate_entry(pfx: str, entry) -> str | None:
    if not isinstance(entry, dict):
        return f"plan item {pfx}: entry must be an object"
    unknown = set(entry) - _ENTRY_KEYS
    if unknown:
        return (
            f"plan item {pfx}: unknown key(s) {sorted(unknown)} "
            f"(allowed: {', '.join(sorted(_ENTRY_KEYS))})"
        )
    title = entry.get("title")
    if title is not None and (
        not isinstance(title, str) or not title.strip() or "\n" in title
    ):
        return f"plan item {pfx}: title must be a non-empty single-line string"
    kind = entry.get("kind")
    if kind is not None and kind not in issuefmt.KINDS:
        return (
            f"plan item {pfx}: kind {kind!r} is not one of "
            f"{', '.join(issuefmt.KINDS)}"
        )
    sections = entry.get("sections")
    if sections is not None:
        if not isinstance(sections, dict) or not sections:
            return f"plan item {pfx}: sections must be a non-empty object"
        for label, body_text in sections.items():
            if not isinstance(label, str) or not isinstance(body_text, str):
                return f"plan item {pfx}: sections must map string → string"
    if "non_atomic" in entry and not isinstance(entry["non_atomic"], bool):
        return f"plan item {pfx}: non_atomic must be a boolean"
    if "note" in entry and not isinstance(entry["note"], str):
        return f"plan item {pfx}: note must be a string"
    return None


def apply(records: list, plan: dict) -> dict:
    """Deterministically apply a validated ``plan`` to import ``records``.

    Returns ``{"ok": True, "records": [...], "entries": [...], "warnings": [...],
    "unaddressable": N}`` — ``records`` is the full list with plan-matched ones
    rebuilt (never mutated in place), ``entries`` the per-item application report
    the preview renders (before/after, kind assignment, ``non_atomic`` flag,
    WARN-only lint audit). A plan PFX matching no record →
    ``{"ok": False, "error": ...}`` before anything is applied: the confirmed
    plan and the source disagree, so the world changed since confirmation.
    """
    by_pfx = {record.pfx: record for record in records if record.pfx}
    unmatched = sorted(set(plan["items"]) - set(by_pfx))
    if unmatched:
        return {
            "ok": False,
            "error": (
                "restructure plan names PFX(s) absent from the source: "
                + ", ".join(unmatched)
                + " — re-confirm the plan against the current source"
            ),
        }

    out: list = []
    entries: list[dict] = []
    warnings: list[str] = []
    for record in records:
        entry = plan["items"].get(record.pfx) if record.pfx else None
        if entry is None:
            out.append(record)
            continue
        rebuilt, report, item_warnings = _apply_one(record, entry)
        out.append(rebuilt)
        entries.append(report)
        warnings.extend(item_warnings)

    unaddressable = sum(1 for record in records if not record.pfx)
    return {
        "ok": True,
        "records": out,
        "entries": entries,
        "warnings": warnings,
        "unaddressable": unaddressable,
    }


def _apply_one(record, entry: dict) -> tuple[object, dict, list[str]]:
    """Apply one plan entry → ``(rebuilt record, report, warnings)``.

    The original title/body are stashed in the block **only when actually
    changed** — an identical rewrite leaves no ``original_*`` residue.
    """
    warnings: list[str] = []
    labels = list(record.labels)
    block = dict(record.block)
    area = encode.facet_value(labels, "area")

    kind = entry.get("kind")
    existing_kind = encode.facet_value(labels, "kind")
    if kind is not None:
        if existing_kind is None:
            labels.append(f"kind:{kind}")
        elif existing_kind != kind:
            labels = [label for label in labels if not label.startswith("kind:")]
            labels.append(f"kind:{kind}")
            warnings.append(
                f"{record.pfx}: kind relabeled {existing_kind!r} → {kind!r} (plan)"
            )
    effective_kind = kind or existing_kind

    title = record.title
    if entry.get("title") is not None:
        proposed = issuefmt.normalize_title(entry["title"].strip(), area)
        if proposed != record.title:
            block["original_title"] = record.title
            title = proposed

    body = record.body
    if entry.get("sections") is not None:
        proposed_body = issuefmt.render_body(effective_kind, entry["sections"])
        if proposed_body != record.body:
            block["original_body"] = encode.format_text(record.body)
            body = proposed_body

    # Rebuilt via type(record) because naming ImportRecord here would import
    # migrate and close a cycle (migrate imports this module). The keyword-only
    # constructor covers every __slots__ field, so a field added to the record
    # without a default breaks this loudly at the call, never silently.
    rebuilt = type(record)(
        pfx=record.pfx,
        title=title,
        body=body,
        status=record.status,
        labels=labels,
        block=block,
    )
    findings = issuefmt.lint(title, body, labels)
    report = {
        "pfx": record.pfx,
        "title_before": record.title,
        "title_after": title,
        "title_changed": title != record.title,
        "body_before": record.body,
        "body_after": body,
        "body_changed": body != record.body,
        "kind": effective_kind,
        "kind_assigned": kind is not None and existing_kind != kind,
        "non_atomic": bool(entry.get("non_atomic")),
        "note": entry.get("note"),
        "lint": [finding.as_dict() for finding in findings],
    }
    return rebuilt, report, warnings



# --- Preview (the owner's aggregate review artifact) -------------------------


def render_preview(
    result: dict,
    *,
    source_label: str,
    collisions: list[dict] | None = None,
) -> str:
    """Render the **full before/after diff artifact** the owner approves in
    aggregate (issue-standard §5.4 — batch review, not per-item HITL).

    Deterministic: generated from the same :func:`apply` result the import will
    consume, so what the owner reviews is byte-for-byte what gets written.
    """
    entries = result["entries"]
    # The BLOCKING subset, computed from the records the import will actually
    # consume. The CLI envelope already reports this, but the owner approves from
    # THIS document — a preview that shows only a WARN-only total lets a plan the
    # import will hard-refuse read as clean at the one moment it is reviewed.
    blocking = [
        (r.title, [f.rule for f in issuefmt.lint_title(r.title or "")])
        for r in result["records"]
        if issuefmt.lint_title(r.title or "")
    ]
    titles = sum(1 for e in entries if e["title_changed"])
    bodies = sum(1 for e in entries if e["body_changed"])
    kinds = sum(1 for e in entries if e["kind_assigned"])
    flagged = [e for e in entries if e["non_atomic"]]
    lint_total = sum(len(e["lint"]) for e in entries)

    lines: list[str] = [
        # This document is written for the owner to review, so the pre-pass's
        # internal id (MG6) stays in this comment rather than in its title.
        "# Restructure preview — before/after, for owner review before import",
        "",
        f"Source: {source_label}",
        "",
        f"- plan entries applied: **{len(entries)}**",
        f"- titles rewritten: **{titles}** · bodies restructured: **{bodies}**"
        f" · kind: assigned/changed: **{kinds}**",
        f"- flagged non-atomic (owner manual split — NOT auto-split): "
        f"**{len(flagged)}**",
        f"- lint findings (body/label, WARN-only) on the restructured set: **{lint_total}**",
        f"- **titles that FAIL issue-standard §1 (the import will refuse): "
        f"{len(blocking)}**",
    ]
    if blocking:
        lines.append("")
        lines.append(
            "> ⚠️ **This plan cannot be imported as-is.** The import validates every "
            "title against §1 before its first write and refuses the whole corpus, "
            "writing nothing. Fix these in the plan and re-preview:"
        )
        for title, rules in blocking[:20]:
            lines.append(f">   - `{title}` — {', '.join(rules)}")
        if len(blocking) > 20:
            lines.append(f">   - … (+{len(blocking) - 20} more)")
    if result["unaddressable"]:
        lines.append(
            f"- items without a PFX (not addressable by a plan, imported "
            f"verbatim): **{result['unaddressable']}**"
        )
    if collisions:
        lines.append(
            f"- ⚠ duplicate-PFX collisions (dropped from import, must be "
            f"resolved first): **{len(collisions)}**"
        )
        for collision in collisions:
            lines.append(f"  - `{collision}`")
    if result["warnings"]:
        lines.append("")
        lines.append("## Warnings")
        lines.append("")
        lines.extend(f"- {warning}" for warning in result["warnings"])
    if flagged:
        lines.append("")
        lines.append("## Flagged non-atomic — owner decision required")
        lines.append("")
        for e in flagged:
            note = f" — {e['note']}" if e["note"] else ""
            lines.append(f"- **{e['pfx']}**{note}")

    lines.append("")
    lines.append("## Before / after")
    for e in entries:
        lines.append("")
        lines.append(f"### {e['pfx']}")
        lines.append("")
        marker = " (unchanged)" if not e["title_changed"] else ""
        lines.append(f"- title before: `{e['title_before']}`")
        lines.append(f"- title after{marker}: `{e['title_after']}`")
        if e["kind"]:
            assigned = " (assigned by plan)" if e["kind_assigned"] else ""
            lines.append(f"- kind: `{e['kind']}`{assigned}")
        if e["non_atomic"]:
            lines.append("- ⚠ **flagged non-atomic** — split is an owner scrub decision")
        for finding in e["lint"]:
            lines.append(f"- lint: `{finding['rule']}` — {finding['message']}")
        if e["body_changed"]:
            lines.append("")
            lines.append("<details><summary>body before</summary>")
            lines.append("")
            lines.append(e["body_before"] or "*(empty)*")
            lines.append("")
            lines.append("</details>")
            lines.append("")
            lines.append("**body after:**")
            lines.append("")
            lines.append(e["body_after"])
    lines.append("")
    return "\n".join(lines)
