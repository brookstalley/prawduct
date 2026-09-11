"""Backlog service — the GitHub-Issues-backed backlog adapter package.

The service turns the merge-prone ``.prawduct/backlog.md`` markdown file into a
live view over GitHub Issues: deterministic, zero-token CRUD an agent drives
non-interactively, with no per-checkout staleness and no merge conflicts.

Layering (the CLI is the entry point every caller binds to — an internal surface
carried at the plugin version, not a published one; the core library is a seam no
module outside this package touches — see
``documentation/backlog-service-api-contract.md`` §1):

- ``transport``  — the sole egress (drives ``gh`` as a subprocess); the primary
  test seam. No other module shells out or opens a socket.
- ``ids``        — ID normalization to canonical ``owner/repo#number``.
- ``encode``     — the ``prawduct:`` body block parse/serialize + soft-enum
  tolerance + item decode + prawduct-issue detection (PROV-2).
- ``issuefmt``   — the deterministic issue-structure standard: title
  normalization, the §2 body composer, and the linter — whose four §1 TITLE
  checks BLOCK every write path, while body/label findings stay WARN-only.
- ``core``       — deterministic CRUD (the return-value envelope + op
  implementations); the CLI/MCP fronts are thin over this.
- ``query``      — the read side (``list``/``pick``/``counts``): structured
  filters and stage-aware ready-work, online off the REST list endpoint.
- ``provision``  — the namespaced label taxonomy (idempotent, collision-free).
- ``snapshot``   — the ``briefing_counts`` degenerate cache (atomic write,
  visible-age read, network-independent).
- ``context``    — unattended/Actions context detection (pure, env-resolved);
  backs the SEC-5/SEC-6 guards.
- ``migrate``    — the importer (idempotent/resumable), ``merge``, ``export``,
  and the write-``Pacer``.
- ``restructure`` — the MG6 migration pre-pass: fail-closed plan validation,
  apply through ``issuefmt``, verbatim ``original_*`` preservation.
- ``cli``        — the ``prawduct-hook backlog <op>`` runner (thin front).

``legacy`` is the pre-service markdown-backlog parser, relocated here unchanged.
It is inert during the build (imported only by ``briefing``/``backlog_probes``/
``norm_probes`` and its own tests) and is retired once prawduct reads its live
backlog through the adapter.
"""

from __future__ import annotations
