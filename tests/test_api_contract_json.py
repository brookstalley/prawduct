"""Every `prawduct-hook` subcommand that offers `--json` documents its key set (#962).

The api-contract Direction norm says existing `--json` keys are never repurposed; that holds only
against a documented key set. Two subcommands (`stale-plugin-caches`, `cost-of-commit`) shipped
`--json` without one and were caught by a reviewer reading, not by a check.

"Documents a key set" is read as: a paragraph of the contract names the subcommand and follows a
`--json` with the output's keys or shape (a bare mention beside the name does not count). Whether the documented keys match what is emitted is out of scope.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOK = (REPO / "plugin" / "bin" / "prawduct-hook").read_text()
CONTRACT = (REPO / ".prawduct" / "artifacts" / "api-contract.md").read_text()

#: subcommand -> why it is deliberately without a documented key set.
ALLOWLIST: dict[str, str] = {}


def _json_subcommands() -> set[str]:
    """Subcommand names whose usage entry carries `[--json]`, read from the usage constant."""
    start = HOOK.index("_USAGE = (")
    block = HOOK[start : HOOK.index("\n)\n", start)]
    text = "".join(re.findall(r'^\s*"(.*)"\s*$', block, re.M))
    body = text[text.index("{") + 1 :]
    entries, depth, cur = [], 0, ""
    for ch in body:
        depth += ch in "[{" or 0
        depth -= ch in "]}" or 0
        if ch == "|" and depth == 0:
            entries.append(cur)
            cur = ""
        else:
            cur += ch
    entries.append(cur)
    names = set()
    for entry in entries:
        m = re.match(r"([a-z][a-z-]*)\b", entry.strip())
        if m and "--json" in entry:
            names.add(m.group(1))
    return names


_KEY_PHRASE = re.compile(r"--json`?\]?\s*(?:\w+\s+){0,3}(?:keys?|adds|carries|emits|shape|envelope|\(`)|"
                         r"`--json`\s+(?:keys?|adds|carries|emits|shape)|--json\s+→[^\n]*\n?[^\n]*(?:keys?|shape)", re.I)


def _documented(name: str) -> bool:
    """A paragraph of the contract names the subcommand and gives its `--json` output's keys or shape.

    Deliberately the whole file, not one section: key sets live both in the § Machine-readable
    bullet list and in the per-operation prose. The phrase test (a `--json` followed by
    "keys" / "adds" / "carries" / "shape" ...) is what stops a bare mention of `--json` beside the
    name from counting.

    The name must end where the token does: a bare prefix match let `plan`
    count as documented by `plan-backfill`'s paragraph, so a subcommand whose
    name begins another's was covered by nothing.
    """
    named = re.compile(rf"`{re.escape(name)}(?![\w-])")
    for para in re.split(r"\n\s*\n", CONTRACT):
        if named.search(para) and _KEY_PHRASE.search(para):
            return True
    return False


def test_the_subcommand_set_is_read_non_empty():
    names = _json_subcommands()
    assert {"stale-plugin-caches", "cost-of-commit", "check-released"} <= names, names


def test_every_json_subcommand_documents_its_key_set():
    missing = sorted(n for n in _json_subcommands() if n not in ALLOWLIST and not _documented(n))
    assert missing == [], (
        f"--json subcommands with no key set in api-contract.md: {missing}. "
        "Document the keys there, or add the name to ALLOWLIST with a reason."
    )


def test_allowlist_entries_are_real_and_reasoned():
    names = _json_subcommands()
    for name, reason in ALLOWLIST.items():
        assert name in names and reason.strip(), name
