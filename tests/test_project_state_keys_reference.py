"""The optional project-state keys are documented once, in the plugin, and reachable.

The state template used to carry each optional key's full explanation as
comments, which every new repo copied and every session then read. That prose
now lives in ``docs/project-state-keys.md``; the template keeps a one-line hint
per key and points at the ``/prawduct:methodology project-state`` topic. These
tests hold the three pieces together: a key the reference documents is still
hinted in the template, the template names the route, and the route resolves.

The methodology skill also states the root for the bare plugin-relative paths
its guides use. Without it, an agent in a product repo rooted
``methodology/planning.md`` at a full prawduct checkout and landed one level
above ``plugin/``.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"
REFERENCE = ROOT / "docs" / "project-state-keys.md"
TEMPLATE = ROOT / "templates" / "project-state.yaml"
SKILL = ROOT / "skills" / "methodology" / "SKILL.md"
TOPIC = "project-state"


def _documented_keys() -> list[str]:
    """Every key the reference documents, read from its own headings and bullets."""
    text = REFERENCE.read_text(encoding="utf-8")
    keys: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            keys += re.findall(r"\b([a-z]+(?:_[a-z]+)+)\b", line)
        elif line.startswith("- **`"):
            keys += re.findall(r"^- \*\*`([a-z_]+)`\*\*", line)
    return keys


def test_the_reference_documents_a_real_set_of_keys():
    keys = _documented_keys()
    # Non-empty and holding what it names: a parse that found nothing would
    # make the next test vacuously green.
    for expected in ("base_branch", "risk_surfaces", "review_round_budget", "backlog_backend"):
        assert expected in keys, keys


def test_every_documented_key_is_still_hinted_in_the_template():
    template = TEMPLATE.read_text(encoding="utf-8")
    missing = [
        key for key in _documented_keys()
        if not re.search(rf"^#?\s*{key}:", template, re.MULTILINE)
    ]
    assert not missing, f"documented but absent from the template: {missing}"


def test_the_template_names_the_route_to_the_reference():
    assert f"/prawduct:methodology {TOPIC}" in TEMPLATE.read_text(encoding="utf-8")


def test_the_skill_routes_the_topic_to_the_reference():
    text = SKILL.read_text(encoding="utf-8")
    front, body = text.split("---", 2)[1], text.split("---", 2)[2]
    description = next(ln for ln in front.splitlines() if ln.startswith("description:"))
    hint = next(ln for ln in front.splitlines() if ln.startswith("argument-hint:"))
    route = next(ln for ln in body.splitlines() if ln.startswith(f"- `{TOPIC}` →"))
    assert TOPIC in description
    assert TOPIC in hint
    assert "${CLAUDE_SKILL_DIR}/../../docs/project-state-keys.md" in route
    assert REFERENCE.is_file()


def test_the_skill_states_the_root_of_bare_guide_paths():
    body = SKILL.read_text(encoding="utf-8").split("---", 2)[2]
    line = next(ln for ln in body.splitlines() if ln.startswith("**Paths the guides write bare**"))
    assert "${CLAUDE_SKILL_DIR}/../.." in line
    for prefix in ("methodology/", "templates/", "docs/"):
        assert prefix in line


def test_every_key_an_advisory_tells_owners_to_set_is_documented():
    """A key an advisory's text tells the owner to set in project-state.yaml is a
    consumer surface: undocumented, it is internal by the api-contract's rule, so
    a rename owes it no deprecation and the owner's override is silently dropped
    (Critic R-12 on the backlog-burndown branch)."""
    named = set()
    for path in sorted((ROOT / "lib").rglob("*.py")):
        named |= set(re.findall(
            r"`([a-z]+(?:_[a-z]+)+)`\s+in\s+`?project-state\.yaml",
            path.read_text(encoding="utf-8"),
        ))
    # Non-empty: a regex that matched nothing would make the check vacuous.
    assert {"oversized_file_threshold_kb", "evidence_store_threshold_mb"} <= named, named
    missing = sorted(named - set(_documented_keys()))
    assert not missing, f"advisories tell owners to set undocumented keys: {missing}"
