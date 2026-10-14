"""Every governance anchor prawduct has shipped and since superseded.

A leaf module — it imports nothing from the plugin — because two sides need it:
the writer (``migrate_plugin``), which swaps a shipped anchor for the current
layout, and the detector (``anchor_repair``), which grades one. Holding the
archive in either of them made the other import back into it.

**Append, never edit.** Each entry is the literal bytes sitting in real repos,
not a description of the current anchor, so "tidying" one makes the repos it
exists to match unmatchable.
"""

from __future__ import annotations

# Every anchor prawduct has shipped that predates the current text, stripped
# exactly as the writer wrote them into ``CLAUDE.md``, oldest first.
#
# **Derive this set from the release tags, never from "the anchor I just
# replaced."** Written the second way, it first shipped covering v2.3.0+ only and
# missing the 31 releases from v2.0.0 to v2.2.3, which differ by a single line
# (`/prawduct:building`, from before the methodology reader was renamed). The
# cohort that gap stranded was the OLDEST repos — and it stranded them while
# reporting that their anchor had been edited locally, blaming an owner for text
# prawduct wrote. ``test_anchor_repair.py`` now reconstructs the shipped set from
# the tags themselves and fails when an entry is missing, so the next revision
# cannot repeat it.

#: v2.0.0 – v2.2.3 (31 releases).
ANCHOR_V1 = """<!-- PRAWDUCT:ANCHOR — static governance pointer managed by the prawduct plugin. Keep it small and version-free: principles, methodology, and the active version live in the plugin and are injected at session start. -->

## Governance (Prawduct)

This repo is governed by **Prawduct**, installed as a Claude Code plugin — not as
committed framework files. The principles, methodology, Critic protocol, and PR
review live in the plugin and are read on demand (run `/prawduct:methodology`);
they are intentionally not copied into this repo.

**Before writing any code, STOP and read the build cycle: `/prawduct:building`.**
Skipping it is the #1 governance failure.

The hardest rules (everything else is in the plugin):

- **Tests are contracts** — fix the code, never weaken a test.
- **No "pre-existing" exception** — fix what you find, or flag why you can't.
- **Never silently drop a requirement** — say so explicitly.
- **Run `/prawduct:critic` after medium+ work** — never write Critic findings
  yourself; the independence is the value.

**Enforcement is structural:** the plugin's Stop hook runs at session end and
**blocks** if code changed against an active build plan with no Critic findings.
The session-start banner shows the active version and what changed — this anchor
stays version-free."""

#: v2.3.0 – v3.4.0 (26 releases). Differs from :data:`ANCHOR_V1` only in the
#: build-cycle line, which gained the `methodology` reader.
#:
#: **This one entry is derived rather than frozen, which bends "append, never
#: edit" and is worth knowing before you edit V1:** a change to V1 silently
#: changes V2 too. Kept because the alternative is 1.3 KB of near-duplicate
#: literal whose only difference is one line — and because the coupling is
#: guarded rather than trusted: `test_the_archive_covers_every_anchor_prawduct_\
#: ever_shipped` reconstructs both from the release tags and fails if either
#: stops matching what shipped.
ANCHOR_V2 = ANCHOR_V1.replace(
    "`/prawduct:building`",
    "`/prawduct:methodology building`",
)

#: v3.5.0 (1 release). The first anchor carrying the plugin-absent notice, and the
#: last one before the Critic line said review rigor is stage-keyed. Frozen as a
#: literal rather than derived from the current anchor: history derived from the
#: present changes every time the present does, which is the inverse of the V2
#: coupling above (older history derived from older history, which never moves).
#: The install command is the id v3.5.0 shipped, spelled out — a later rename of
#: ``PLUGIN_ID`` must not rewrite the bytes this entry exists to match.
ANCHOR_V3 = """<!-- PRAWDUCT:ANCHOR — governance pointer managed by the prawduct plugin; keep it small and version-free. -->

## Governance (Prawduct)

This repo is governed by **Prawduct**, a Claude Code plugin; its methodology and
protocols are read on demand via `/prawduct:methodology`.

**Check first: is the plugin loaded?** If `/prawduct:*` commands are unavailable it
is not, and **governance is OFF** — no Stop gate, no Critic, nothing below enforced.
A clone registers the marketplace but installs nothing. Tell the user to
run `claude plugin install prawduct@prawduct`, then restart — don't proceed as if governed.

**With the plugin loaded — before writing any code, STOP and read the build cycle:
`/prawduct:methodology building`.** Skipping it is the #1 governance failure.

Hardest rules:

- **Tests are contracts** — fix the code, never weaken a test.
- **No "pre-existing" exception** — fix what you find, or flag why you can't.
- **Never silently drop a requirement** — say so explicitly.
- **Run `/prawduct:critic` after medium+ work** — never write findings
  yourself; the independence is the value.

**Enforcement is structural — while the plugin is loaded:** its Stop hook runs at
session end and **blocks** if code changed against an active build plan with no
Critic findings."""



#: The DEVELOP anchor superseded by #833 (2026-09-19) before any release
#: carried it — no release tag ships these bytes, so this entry is deliberately
#: absent from the tag-derived set the module header tells you to build. Keep
#: it: repos onboarded off the develop track between v3.5.0 and that commit
#: hold exactly this text, and they are the only cohort that does.
#:
#: **Why it is not optional, stated as the grade it actually prevents.**
#: Unarchived, `_match_superseded` misses and `_missing_substance` comes back
#: EMPTY — these bytes carry both `SUBSTANCE` probes, including `stage-keyed` —
#: so `check()` falls through to `STATUS_OK`. That cohort would be reported
#: healthy, `repairable: False`, and never offered the repair; no owner is ever
#: told. A silent `ok` is less visible than a refusal, which is why this entry
#: matters more than the V1-V3 ones, not less. (Those predate `stage-keyed`, so
#: an unarchived V1-V3 anchor DOES grade `stale-modified` and surfaces.)
#: Generated from the bytes HEAD rendered, not retyped.
ANCHOR_V4 = '<!-- PRAWDUCT:ANCHOR — governance pointer managed by the prawduct plugin; keep it small and version-free. -->\n\n## Governance (Prawduct)\n\nThis repo is governed by **Prawduct**, a Claude Code plugin; its methodology and\nprotocols are read on demand via `/prawduct:methodology`.\n\n**Check first: is the plugin loaded?** If `/prawduct:*` commands are unavailable it\nis not, and **governance is OFF** — no Stop gate, no Critic, nothing below enforced.\nA clone registers the marketplace but installs nothing. Tell the user to\nrun `claude plugin install prawduct@prawduct`, then restart — don\'t proceed as if governed.\n\n**With the plugin loaded — before writing any code, STOP and read the build cycle:\n`/prawduct:methodology building`.** Skipping it is the #1 governance failure.\n\nHardest rules:\n\n- **Tests are contracts** — fix the code, never weaken a test.\n- **No "pre-existing" exception** — fix what you find, or flag why you can\'t.\n- **Never silently drop a requirement** — say so explicitly.\n- **Run `/prawduct:critic` after medium+ work** — never write findings\n  yourself; the independence is the value. Rigor is stage-keyed: a mid-build\n  review blocks only on what would ship broken, the review at the merge\n  boundary runs everything and is never skipped, and unsure defaults to the\n  cheaper mid-build review.\n\n**Enforcement is structural — while the plugin is loaded:** its Stop hook runs at\nsession end and **blocks** if code changed against an active build plan with no\nCritic findings.\n'


#: v3.6.x – v3.7.x, the last anchor written into ``CLAUDE.md`` rather than
#: ``AGENTS.md``. Generated from the bytes HEAD rendered, not retyped.
ANCHOR_V5 = '<!-- PRAWDUCT:ANCHOR — governance pointer managed by the prawduct plugin; keep it small and version-free. -->\n\n## Governance (Prawduct)\n\nThis repo is governed by **Prawduct**, a Claude Code plugin; its methodology and\nprotocols are read on demand via `/prawduct:methodology`.\n\n**Check first: is the plugin loaded?** If `/prawduct:*` commands are unavailable it\nis not, and **governance is OFF** — no Stop gate, no Critic, nothing below enforced.\nA clone registers the marketplace but installs nothing. Tell the user to\nrun `claude plugin install prawduct@prawduct`, then restart — don\'t proceed as if governed.\n\n**With the plugin loaded — before writing any code, STOP and read the build cycle:\n`/prawduct:methodology building`.** Skipping it is the #1 governance failure.\n\nHardest rules:\n\n- **Tests are contracts** — fix the code, never weaken a test.\n- **No "pre-existing" exception** — fix what you find, or flag why you can\'t.\n  The fix half is bounded to BLOCKING; below it, the flag is the whole answer.\n- **Never silently drop a requirement** — say so explicitly.\n- **Run `/prawduct:critic` after medium+ work** — never write findings\n  yourself; the independence is the value. Rigor is stage-keyed: a mid-build\n  review blocks only on what would ship broken, the review at the merge\n  boundary runs everything and is never skipped, and unsure defaults to the\n  cheaper mid-build review.\n\n**Enforcement is structural — while the plugin is loaded:** its Stop hook runs at\nsession end and **blocks** if code changed against an active build plan with no\nCritic findings.\n'


SUPERSEDED_ANCHORS: tuple[str, ...] = (ANCHOR_V1, ANCHOR_V2, ANCHOR_V3, ANCHOR_V4, ANCHOR_V5)



def shipped_anchor_in(text: str) -> str | None:
    """The superseded anchor present verbatim in ``text``, in the file's own line
    endings — or ``None`` when no shipped anchor is present.

    The archive is stored LF-only because that is how the plugin writes it, but a
    product's instruction file may be CRLF, and on a CRLF repo an LF-only
    comparison finds nothing: the repo would be told its anchor had been edited
    locally, which is a false accusation. So each entry is compared in the file's
    own ending as well.
    """
    for old in SUPERSEDED_ANCHORS:
        if old in text:
            return old
        crlf = old.replace("\n", "\r\n")
        if crlf in text:
            return crlf
    return None
