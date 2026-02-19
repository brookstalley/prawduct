"""Governance module — consolidated hook logic for prawduct.

All governance enforcement (activation gating, PFR, chunk review, edit tracking,
stop validation, commit gating, prompt checks, compaction recovery) lives here.
Called via `tools/governance-hook <command>` which delegates to
`python3 -m governance <command>`.
"""

__version__ = "1.0"
