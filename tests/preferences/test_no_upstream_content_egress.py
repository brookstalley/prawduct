"""Project-preferences enforcement: no upstream content egress.

Enforces the `security-model.md` § Direction norm: a governed product's content
never leaves that product's own repository and owner without an explicit owner
decision. The hazard is concrete — a **private** consuming repo filing a backlog
item or bug report into prawduct's **public** tracker would carry that repo's
paths, code excerpts, learnings prose and product detail across a trust boundary,
in a direction no one chose.

Today the guarantee holds by *absence*: the cross-owner/public identity plane
(`file-upstream`, XP1/XP2 in `documentation/backlog-service-security-model.md`)
is designed but deliberately unbuilt — it is roadmap wave W3 — and
`/prawduct:report-bug`'s upstream channel is filesystem-only, writing into a
local `incoming-bugs/` drop-box in a reachable local checkout and refusing any
remote write when none is reachable.

The norm is `in-transition`, tracked by **BKL-7Q4M** — the named 3.2.0 release
blocker. The end state is not prohibition: a private repo filing upstream is a
capability prawduct wants, and BKL-7Q4M is the work that makes it safe (content
minimization, redaction, owner preview-and-consent for the outbound payload).
This test enforces the norm's *interim rule* — no foreign-owner surface ships
until that work is settled and reviewed.

So these assertions are expected to fail when BKL-7Q4M is built. That failure is
the handoff point: replace this test with one asserting the redaction and consent
contract, and amend the norm to its steady-state form. Deleting or relaxing it to
let an unreviewed surface through is the one response that is never correct.

Detection: token scan for the unbuilt operation, plus a check that prawduct's own
tracker never appears inside the backlog adapter, whose sole egress is
`lib/backlog/transport.py`. The tracker legitimately appears elsewhere as a
human-facing URL and as marketplace-install metadata; neither reaches the Issues
API, so this test is scoped to the adapter rather than the whole plugin.
"""

from __future__ import annotations

from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent / "plugin"
ADAPTER = PLUGIN_ROOT / "lib" / "backlog"

# The upstream/cross-owner filing operation. Deferred to roadmap wave W3.
UPSTREAM_OP_TOKENS = ("file-upstream", "file_upstream")

# Prawduct's own public tracker — the destination that must never be written to
# on a governed product's behalf.
UPSTREAM_TRACKER = "brookstalley/prawduct"


def _adapter_sources() -> list[Path]:
    return sorted(p for p in ADAPTER.rglob("*.py") if "__pycache__" not in p.parts)


def _dispatch_surfaces() -> list[Path]:
    """Executable surfaces only. Prose that *describes* the deferred operation is
    harmless; a dispatch entry that *offers* it is not. Scoping to code keeps this
    from firing on documentation — a probe that misfires trains its reader to
    ignore the one real catch (`docs/norms.md`, Deliberate Non-Design)."""
    files = [
        p
        for root in ("lib", "hooks")
        for p in (PLUGIN_ROOT / root).rglob("*.py")
        if "__pycache__" not in p.parts
    ]
    files.extend(p for p in (PLUGIN_ROOT / "bin").iterdir() if p.is_file())
    return sorted(files)


class TestNoUpstreamContentEgress:
    def test_no_cross_owner_filing_operation_exists(self):
        """`file-upstream` is the W3 public/foreign-identity plane. While it is
        unbuilt, no shipped surface may name it as a live operation — a usage
        string or dispatch entry advertising it is the tell that the plane
        landed without the owner decision the norm requires."""
        offenders: list[str] = []
        for path in _dispatch_surfaces():
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue  # binary or unreadable — carries no dispatch entry
            for token in UPSTREAM_OP_TOKENS:
                if token in content:
                    rel = path.relative_to(PLUGIN_ROOT).as_posix()
                    offenders.append(f"{rel}: names {token!r}")
        assert not offenders, (
            "A cross-owner upstream filing surface appears in the shipped plugin. "
            "This is the W3 public/foreign-identity plane: building it moves a "
            "private product's content into a public tracker, which "
            "`.prawduct/artifacts/security-model.md` § Direction makes an owner "
            "decision, not an increment. Record the decision and amend the norm "
            "before this ships.\n  - " + "\n  - ".join(offenders)
        )

    def test_backlog_adapter_never_targets_the_prawduct_tracker(self):
        """The adapter reaches exactly one repo: the one the product configured
        in `backlog_service_repo`. Prawduct's own tracker reaching the adapter —
        whose sole egress is `transport.py` — would mean a governed product can
        write into prawduct's public Issues."""
        offenders: list[str] = []
        for path in _adapter_sources():
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if UPSTREAM_TRACKER in line:
                    rel = path.relative_to(PLUGIN_ROOT).as_posix()
                    offenders.append(f"{rel}:{lineno}: {line.strip()[:100]}")
        assert not offenders, (
            f"The backlog adapter names {UPSTREAM_TRACKER!r}. The adapter must "
            "only ever reach the product's own `backlog_service_repo`; prawduct's "
            "tracker belongs in human-facing prose and marketplace metadata, "
            "never on a write path.\n  - " + "\n  - ".join(offenders)
        )
