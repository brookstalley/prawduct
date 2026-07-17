"""Backlog service — the GitHub-Issues-backed backlog adapter package.

The service turns the merge-prone ``.prawduct/backlog.md`` markdown file into a
live view over GitHub Issues: deterministic, zero-token CRUD an agent drives
non-interactively, with no per-checkout staleness and no merge conflicts.

Layering (the CLI is the stable public contract; the core library is an internal
seam — see ``documentation/backlog-service-api-contract.md`` §1):

- ``transport``  — the sole egress (drives ``gh`` as a subprocess); the primary
  test seam. No other module shells out or opens a socket.
- ``ids``        — ID normalization to canonical ``owner/repo#number``.
- ``encode``     — the ``prawduct:`` body block parse/serialize + soft-enum
  tolerance + item decode.
- ``core``       — deterministic CRUD (the return-value envelope + op
  implementations); the CLI/MCP fronts are thin over this.
- ``provision``  — the namespaced label taxonomy (idempotent, collision-free).
- ``cli``        — the ``prawduct-hook backlog <op>`` runner (thin front).

``legacy`` is the pre-service markdown-backlog parser, relocated here unchanged.
It is inert during the build (imported only by ``briefing``/``backlog_probes``
and its own tests) and is retired once prawduct reads its live backlog through
the adapter.
"""

from __future__ import annotations
