"""Post-sync advisory probe for an oversized clone-shared evidence store (#953).

``<git-common-dir>/prawduct/evidence.jsonl`` is append-only and never pruned, and
``evidence.read_facts`` parses all of it on every gate call. Parse cost tracks
bytes — a review fact averages ~9 KB and a session-start fact ~280 bytes — so the
threshold is in bytes, and the probe reads one ``stat``: no line count, and never
``read_facts``, so measuring the store never pays the cost it reports.

The growth is in kinds a gate composes (``review``, ``resolution``,
``disposition``), which no command drops today and no age rule can drop safely.
So this is an advisory, never a limit, and its ask is a report upstream: the
lifecycle of gate-composed facts is to be designed against a real store.

Evidence is the fixed store name, never its size: evidence is hashed into the
advisory id, and a size in it would mint a new id on every append and silently
un-dismiss a decision the owner had already made — the ``oversized_state_probes``
rule.

Registered at the composition root (``lib/probe_families.register_all``), not at
import time — the same pattern as the sibling probe modules.
"""

from __future__ import annotations

import os
from pathlib import Path

from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe
from .core import log, read_str_yaml_key

FEATURE = "governance"
PROBE_TYPE = "oversized-evidence-store"
PROBE_VERSION = 1

#: Default size, in MB (10**6 bytes), above which the store earns the advisory.
#: At the rate measured on prawduct's own store (127 ms for 14.2 MB, roughly
#: linear in bytes) 50 MB is about 450 ms per ``read_facts``.
EVIDENCE_STORE_MB = 50

#: ``project-state.yaml`` key overriding :data:`EVIDENCE_STORE_MB` for this repo.
EVIDENCE_STORE_THRESHOLD_KEY = "evidence_store_threshold_mb"

#: Milliseconds per MB that one ``read_facts`` took on the measured store.
_MS_PER_MB = 9


def evidence_store_threshold(prawduct_dir: Path) -> int:
    """Bytes above which the evidence store earns the advisory, for this repo.

    Fail-soft like :func:`lib.core.oversized_file_threshold`: an absent key or a
    value that is not a positive integer falls back to the default, because a
    typo in a tuning knob must not silence a nudge or make it fire everywhere.
    """
    raw = read_str_yaml_key(prawduct_dir / "project-state.yaml", EVIDENCE_STORE_THRESHOLD_KEY)
    megabytes = EVIDENCE_STORE_MB
    if raw is not None:
        try:
            configured = int(raw)
        except ValueError:
            configured = 0
        if configured > 0:
            megabytes = configured
    return megabytes * 1_000_000


def probe_oversized_evidence_store(state: ProjectState, codebase: Codebase):
    """One advisory when the clone-shared evidence store is over the threshold.

    Silent outside git and when the store is absent: there is no store to be
    oversized. A store that exists but cannot be stat'ed is different — the probe
    could not look, so it prints a NOTE and returns ``None``, which holds an open
    advisory open rather than resolving it over a size nobody measured (#917).
    It never blocks.
    """
    from . import evidence  # noqa: PLC0415 — lazy; keeps probe registration light

    root = Path(codebase.root)
    path = evidence.store_path(root)
    if path is None:
        return []
    try:
        size = os.stat(path).st_size
    except FileNotFoundError:
        return []
    except OSError as exc:
        log(
            f"NOTE: the evidence store could not be measured ({exc}) — this session did "
            "not check whether it is over the size threshold."
        )
        return None  # could not look — not "nothing to report" (#917)
    threshold = evidence_store_threshold(root / ".prawduct")
    if size <= threshold:
        return []
    megabytes = size / 1_000_000
    return [
        AdvisoryCandidate(
            type=PROBE_TYPE,
            # Fixed: see the module docstring. A size here would un-dismiss on append.
            evidence=("evidence.jsonl",),
            trigger_summary=(
                f"the clone-shared evidence store is {megabytes:.1f} MB, over this repo's "
                f"{threshold // 1_000_000} MB nudge threshold — every gate parses all of it, "
                f"about {round(megabytes * _MS_PER_MB)} ms per read at the measured rate; the "
                "growth is review, resolution and disposition facts, which no command drops today"
            ),
            owner_action=(
                "Decide whether the gate slowdown is worth reporting upstream to prawduct, so "
                "the lifecycle of gate-composed facts gets designed against a real store like "
                "this one; nothing here is safe to delete by hand. If the ceiling is wrong for "
                "this repo, raise `evidence_store_threshold_mb` in project-state.yaml, or "
                "dismiss this to record that the size is accepted."
            ),
            recommended_action="prawduct-hook evidence status",
            priority="info",
        )
    ]


def register() -> None:
    """Register the oversized-evidence-store probe. Idempotent."""
    register_probe(FEATURE, PROBE_TYPE, PROBE_VERSION, probe_oversized_evidence_store)
