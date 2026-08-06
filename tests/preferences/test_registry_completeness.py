"""Every primitive the code enumerates has a row in the artifact that owns it.

**Why this exists.** The framework keeps several *registries* — documents that
declare themselves the authoritative list of some primitive — and the code keeps
the matching enumerated set. Nothing checked that the two move together, so the
recurring defect was: add the primitive, ship it, and let the registry go stale.

Measured on `feat/gate-as-dispatcher` (2026-08-06), one branch, one chunk. Four
registries went stale in the same work, and the Critic found each one by hand:

| primitive added        | registry that lagged                    |
|------------------------|-----------------------------------------|
| `critic-begin` exit 3  | `api-contract.md` § Error Model         |
| `guard-refusal` kind   | `data-model.md` § Entities              |
| the dispatch refusal   | `cross-cutting-concerns.md` row         |
| `chunk-ref-missing`    | `docs/waivers.md` vocabulary            |

Three of those cost a full review round, because the class is cheap to fix and
expensive to *notice*: a reviewer has to know the registry exists, remember it is
authoritative, and check it. That is precisely the work `record_lint` was built
to take off reviewers — "record-class findings were 57% of one day's review
output, and none of them needed judgment." This test extends that argument to the
class `record_lint` did not cover.

**It mechanizes the first two rows of that table, not all four**, and the
difference is what a set-difference can express rather than what matters most:

- *Exit codes vs `api-contract.md`* — there is no enumerated set in code to
  difference against. Exit codes are `return` statements scattered across command
  functions, so extracting "the sentinels this subcommand can return" means
  reading control flow, not a literal. A check built on a regex over `return N`
  would be noise, and a noisy registry check is one nobody acts on.
- *`cross-cutting-concerns.md` rows* — the registry's members are *concerns*, a
  human judgement about what recurs across the pipeline. Nothing in code
  enumerates them, so there is no left-hand side.

Both remain reviewer work (Framework Check 10 already asks for the concerns
sweep). Stated here so the next reader does not take a green suite as proof the
whole class is covered — which is the same over-claim this file exists to catch
one level down.

**Set-difference, not diff inspection.** The check is "is the registry complete
*now*", not "did this commit update it" — so it holds no matter which commit
introduced the gap, cannot be satisfied by a stale baseline, and fires at suite
time rather than at review time. Wrong-direction failures are impossible: a row
with no code is allowed (a registry may document a rule before anything uses it,
and reserved kinds are declared deliberately); code with no row is the defect.

Each extractor asserts its own subject is NON-EMPTY. A set-difference test whose
left side silently becomes `set()` passes forever while checking nothing — the
exact shape this repo has a durable learnings rule about.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGIN = REPO_ROOT / "plugin"

sys.path.insert(0, str(PLUGIN))
from lib import evidence, waivers  # noqa: E402

#: Source files that may name a framework primitive.
_CODE_FILES = sorted(PLUGIN.glob("lib/**/*.py")) + [PLUGIN / "bin" / "prawduct-hook"]

#: A rule ref passed to the waiver API as a string literal —
#: `waives(lines, i, "prawduct/chunk-ref-missing")`. Deliberately NOT a bare
#: `prawduct/<word>` scan: `.prawduct/artifacts`, `.prawduct/backlog` and a dozen
#: other STATE PATHS match that shape, and a checker whose subject is polluted
#: with 31 false members is one nobody can act on.
_RULE_LITERAL_RE = re.compile(r'"(prawduct/[a-z][a-z0-9-]*)"')

#: A row in `docs/waivers.md`'s vocabulary table: `| `rule-id` | ... |`
_WAIVER_ROW_RE = re.compile(r"^\|\s*`([a-z][a-z0-9-]*)`\s*\|")


def _declared_waiver_rules() -> set[str]:
    """Every `prawduct/*` rule the code actually uses — as a pragma it writes,
    or as a rule ref it checks against."""
    used: set[str] = set()
    for path in _CODE_FILES:
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            # Pragmas the framework's own source carries.
            used.update(
                w.ref for w in waivers.parse_waivers(line) if w.scope == "prawduct"
            )
        # Rule refs the framework CHECKS — the half that invents new ids.
        used.update(_RULE_LITERAL_RE.findall(text))
    return used


def _registered_waiver_rules() -> set[str]:
    doc = (PLUGIN / "docs" / "waivers.md").read_text(encoding="utf-8")
    body = doc.split("## The `prawduct/*` vocabulary", 1)
    assert len(body) == 2, "waivers.md lost its `prawduct/*` vocabulary heading"
    # Stop at the next section so `project/*` rows never satisfy a `prawduct/*` id.
    table = body[1].split("\n## ", 1)[0]
    return {
        f"prawduct/{m.group(1)}"
        for line in table.splitlines()
        if (m := _WAIVER_ROW_RE.match(line))
    }


def test_every_waiver_rule_the_code_uses_is_registered():
    """`docs/waivers.md` says its table IS the registry — "add a row when a new
    framework rule becomes waivable, that is the only change needed" — and defines
    `<rule-id>` as "a *reference* into a registry, not a literal the tooling
    hard-codes". A hard-coded id with no row breaks that contract twice: the row
    is how a plan author DISCOVERS the escape exists, and it is where the rule
    states the legitimacy test the Critic checks each waiver against.
    """
    used = _declared_waiver_rules()
    assert used, (
        "extracted no waiver rules from plugin source — the extractor broke, and "
        "a set-difference against an empty set passes while checking nothing"
    )
    assert "prawduct/broad-except" in used, (
        "the most-used rule in the tree is missing from the extraction — the "
        "scan is not reaching the pragmas it claims to read"
    )

    missing = sorted(used - _registered_waiver_rules())

    assert not missing, (
        f"waiver rule(s) used in code with no row in docs/waivers.md: {missing}. "
        f"The table is the registry; add a row naming what the rule waives, the "
        f"principle it maps to, and the legitimacy test a reviewer applies. "
        f"Without it the next author cannot discover the escape, and the Critic "
        f"has nothing to validate a pragma against."
    )


def test_every_evidence_fact_kind_is_documented():
    """`data-model.md` owns the evidence store's schema and carries a per-kind
    body spec plus a droppability rule. A kind that ships without one leaves the
    store's own contract describing a set it no longer has — and droppability is
    load-bearing: it decides what compaction may remove.
    """
    kinds = set(evidence.KNOWN_KINDS)
    assert kinds, "KNOWN_KINDS is empty — the extractor's subject vanished"

    doc = (REPO_ROOT / ".prawduct" / "artifacts" / "data-model.md").read_text(
        encoding="utf-8"
    )
    # The body-spec bullets, e.g. `- **Guard-refusal fact `body`** — ...`. The
    # kinds TABLE alone is not enough: a kind can be listed there and still have
    # no body spec, which is the half a reader needs.
    documented = {
        m.group(1).lower()
        for m in re.finditer(r"\*\*([A-Za-z][\w-]*) fact `body`\*\*", doc)
    }
    assert documented, "no per-kind body specs found in data-model.md"

    missing = sorted(k for k in kinds if k.lower() not in documented)

    assert not missing, (
        f"evidence fact kind(s) in KNOWN_KINDS with no body spec in "
        f"data-model.md: {missing}. Add the kind to § Entities' `kind` row and a "
        f"body paragraph stating its payload and its droppability rule."
    )
