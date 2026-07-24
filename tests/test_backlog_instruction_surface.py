"""Guard: the backlog adapter's instruction surfaces never promise a mutation
preview/apply flag the CLI does not implement (BKL-8V3D).

`skills/backlog/adapter-mode.md` once told the model that "mutations follow the
adapter's own ``--apply``/dry-run … contracts (you never invent a mutation
path)" — but ``lib/backlog/`` implements no such flag. The hazard is not
cosmetic: a migration/scrub run then walks a write path *believing a dry-run
guarded it* (BKL-2Q7F's 100–250-real-issues blast radius). The real
preview-before-write is ``restructure-preview`` — a distinct op — never a
per-mutation flag.

This pins the *class*, not the instance: any backlog instruction surface that
names a mutation-safety flag must be backed by the CLI actually parsing it. It is
scoped to the mutation-preview flag family on purpose — a blanket "every ``--flag``
in the docs must be a CLI flag" check false-positives on legitimate roadmap
(``--like``) and markdown-skill flag references, and a probe that misfires trains
its reader to ignore the one real catch (`docs/norms.md`, and the same reasoning
`tests/preferences/test_no_upstream_content_egress.py` gives for scoping).
"""

from __future__ import annotations

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "plugin"
BACKLOG_SURFACES = sorted((PLUGIN / "skills" / "backlog").glob("*.md"))
CLI_SOURCE = (PLUGIN / "lib" / "backlog" / "cli.py").read_text(encoding="utf-8")

# A "preview / apply before a mutation" flag is the exact shape adapter-mode.md
# over-claimed. Extend this tuple if a new mutation-safety flag is coined.
MUTATION_PREVIEW_FLAGS = ("--apply", "--dry-run")


def _cli_parses(flag: str) -> bool:
    """Whether the backlog CLI actually offers ``flag``. The only way the token
    reaches ``cli.py`` is as a real usage/parse entry, so its presence there is
    the authoritative signal — if the flag is genuinely implemented later, the
    docs are free to name it and this guard relaxes automatically."""
    return flag in CLI_SOURCE


def test_backlog_surfaces_name_no_unparsed_mutation_flag():
    offenders: list[str] = []
    for flag in MUTATION_PREVIEW_FLAGS:
        if _cli_parses(flag):
            continue
        for surface in BACKLOG_SURFACES:
            for lineno, line in enumerate(
                surface.read_text(encoding="utf-8").splitlines(), 1
            ):
                if flag in line:
                    rel = surface.relative_to(PLUGIN).as_posix()
                    offenders.append(f"{rel}:{lineno}: {line.strip()[:100]}")
    assert not offenders, (
        "A backlog instruction surface names a mutation preview/apply flag the "
        "backlog CLI does not parse. The adapter has no generic --apply/--dry-run "
        "contract; the only preview-before-write is `restructure-preview`. Either "
        "the CLI must implement the flag or the surface must stop promising it "
        "(BKL-8V3D).\n  - " + "\n  - ".join(offenders)
    )
