"""Composition root for the production advisory probe families.

The advisory infrastructure (``lib.advisory_store``) is deliberately
feature-agnostic: it owns the registry mechanics (``register_probe`` /
``run_all_probes``) but knows about no specific probe. Something has to know the
full roster and register it before the roster runs, and that "something" is a
composition root — this module.

Two call sites run the roster and so must register it first:

- ``bin/prawduct-hook`` ``cmd_clear`` — the session-start advisory sync.
- ``lib.advisory_cmd.show_advisory`` — the on-demand ``advisory show`` evidence
  reconstruction, which re-runs the probes to recover a compacted entry's full
  citation list.

Before this module, each call site had to know the family list independently, and
the second one didn't — so ``show`` reconstructed against an empty registry and
silently no-op'd for *every* probe family. Homing the list here, imported by both
call sites, is the fix: one roster, no transcription, no call site left behind.

**Lazy imports inside :func:`register_all`.** Each ``*_probes`` module imports
names from ``advisory_store`` at module load. Importing those modules at *this*
module's top level would risk a partially-initialized import cycle
(``advisory_cmd`` imports this module; a probe module importing back through the
chain could see a half-built module). Deferring the imports into the function body
sidesteps it — by the time :func:`register_all` is *called*, every module is fully
importable.
"""

from __future__ import annotations


def register_all() -> None:
    """Register every production probe family into the advisory registry.

    Idempotent: ``register_probe`` overwrites by ``(feature, probe_type)``, so
    calling this twice in a process (session-start sync, then an ``advisory
    show``) simply re-registers the same probes. Registration order does not
    matter — the roster runs them all and each probe is independent.
    """
    from .backlog_probes import register as register_backlog
    from .upstream_probes import register as register_upstream
    from .api_versioning_probes import register as register_api_versioning
    from .gitignore_probes import register as register_gitignore
    from .install_reference_probes import register as register_install_reference
    from .norm_probes import register as register_norm
    from .coverage_probes import register as register_coverage
    from .stale_base_probes import register as register_stale_base
    from .gitattributes_probes import register as register_gitattributes

    register_backlog()  # the backlog feature's probes (incl. legacy-backlog-format)
    register_upstream()  # upstream-bug-reporting receiving-side probe
    register_api_versioning()  # api-design versioning-undecided migration nudge
    register_gitignore()  # session-file .gitignore contract-drift nudge
    register_install_reference()  # committed install-reference (ref/autoUpdate) drift nudge
    register_norm()  # norm-lifecycle time-domain probes (docs/norms.md § Enforcement)
    register_coverage()  # structural-coverage strategy-class artifact probe
    register_stale_base()  # stale remote-base / unpromoted-release-prep nudge (COV-7K4N)
    register_gitattributes()  # change-log merge=union recommendation (top-append conflicts)
