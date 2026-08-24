"""Guards for the two carriers of the PR-review evidence contract, and for the
class of claim that a GitHub closing keyword closes a backlog item.

Both defects these guards close were found the same way: by a PR that merged
cleanly and left something undone.

**The evidence contract has two carriers.** `skills/pr/review-protocol.md`
tells the reviewer what to write; `skills/pr/SKILL.md` tells the caller what to
read. They agree on `commit_reviewed` — the SHA the reviewer actually read —
and if either drops or renames it, the Update Flow's substantive-delta test
silently loses its input. Before the field existed, that test said to diff from
"the reviewed commit" with nothing recording which commit that was, so the
caller reconstructed it from `timestamp` and `commits_reviewed`. That inference
is correct exactly until a commit lands *during* the review, which is the case
it needed to catch: PR #709's evidence was written at 12:05 claiming 16 commits
while its 17th landed at 12:02, inside the reviewer's own 420-second window.

**The closing-keyword claim is a class, not an instance.** A PR-review agent
dispositioned a backlog item as closed-by-the-merge because the PR body opened
with `Closes #676`. GitHub fires closing keywords only for PRs merged into the
repository's *default* branch; that PR based on `develop` against a `main`
default, so the merge closed nothing and the item stayed open through an
independent review that had explicitly signed off on its closure. The guard
below is therefore written against the keyword family rather than that one
sentence: any plugin surface that names a closing keyword must also name the
condition under which it fires.

**Honest limit (Principle 5).** These are prose guards over a curated
vocabulary, not a proof. They catch a renamed/dropped field and an unqualified
closing-keyword claim; they cannot catch a paraphrase that never writes the
keyword ("the merge will close the issue"). That is the same scoping rationale
`tests/test_backlog_instruction_surface.py` states for its own vocabulary.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1] / "plugin"
PROTOCOL = PLUGIN / "skills" / "pr" / "review-protocol.md"
PR_SKILL = PLUGIN / "skills" / "pr" / "SKILL.md"

# The keyword family GitHub actually honours, spelled as prose writes them.
CLOSING_KEYWORDS = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#", re.IGNORECASE)


def _fenced_json_blocks(text: str) -> list[dict]:
    """Every ```json fence in a document, parsed. A malformed example is a
    defect in its own right — the reviewer copies these verbatim."""
    blocks = []
    for raw in re.findall(r"```json\n(.*?)```", text, re.DOTALL):
        blocks.append(json.loads(raw))
    return blocks


def _paragraphs(text: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


class TestEvidenceSchemaCarriers:
    def test_protocol_example_documents_commit_reviewed_as_a_sha(self):
        """The reviewer's template must carry the field, with a value shaped
        like what the instruction asks for (`git rev-parse HEAD`). A truncated
        or placeholder value teaches the reviewer to write a short SHA, which
        `git merge-base --is-ancestor` accepts but a later string comparison
        against a full SHA does not."""
        blocks = _fenced_json_blocks(PROTOCOL.read_text())
        evidence = [b for b in blocks if isinstance(b, dict) and "findings" in b]
        assert evidence, "review-protocol.md has no evidence-shaped ```json example"
        for block in evidence:
            assert "commit_reviewed" in block, (
                "The evidence example dropped `commit_reviewed`. The Update Flow's "
                "substantive-delta test reads it; without it the caller is back to "
                "inferring the reviewed commit from a timestamp."
            )
            assert re.fullmatch(r"[0-9a-f]{40}", block["commit_reviewed"]), (
                f"`commit_reviewed` example is {block['commit_reviewed']!r}; it must be a "
                "full 40-hex SHA so the reviewer copies the right shape."
            )

    def test_caller_reads_the_field_at_both_points_it_matters(self):
        """Create Step 4 validates the field; the Update Flow consumes it. Both
        carriers, one name."""
        skill = PR_SKILL.read_text()
        assert skill.count("commit_reviewed") >= 2, (
            "`SKILL.md` names `commit_reviewed` fewer than twice — it is needed both "
            "where the evidence is validated (Create Step 4) and where the delta is "
            "priced (Update Flow step 2)."
        )

    def test_reviewed_commit_is_never_inferred_from_the_upstream_ref(self):
        """`@{u}..HEAD` was the old stand-in for "since the review". It answers a
        different question — since the last *push* — and the two diverge exactly
        when a commit lands mid-review and is pushed before the caller looks."""
        skill = PR_SKILL.read_text()
        assert "@{u}..HEAD" not in skill, (
            "`SKILL.md` is back to deriving the reviewed commit from the upstream ref. "
            "The reviewed commit is `commit_reviewed`; the upstream ref tracks pushes, "
            "not reviews."
        )

    def test_protocol_forbids_advancing_the_field_after_the_fact(self):
        """`pr_number` is backfilled after PR creation, and the neighbouring
        instruction must not read as licence to backfill the SHA too — that
        would launder unreviewed commits into the reviewed set."""
        protocol = PROTOCOL.read_text()
        assert re.search(r"[Nn]ever rewrite `commit_reviewed`", protocol), (
            "review-protocol.md no longer forbids rewriting `commit_reviewed`. It sits "
            "next to the `pr_number` backfill instruction, which is what makes the "
            "prohibition load-bearing."
        )


class TestClosingKeywordClaims:
    @pytest.mark.parametrize("path", sorted(PLUGIN.rglob("*.md")), ids=lambda p: p.name)
    def test_closing_keyword_is_never_named_without_its_condition(self, path: Path):
        """Wherever a plugin surface names `Closes #N` and friends, the same
        paragraph must name the default-branch condition. Paragraph scope, not
        file scope: a qualification three sections away is not read by someone
        following the sentence in front of them."""
        for para in _paragraphs(path.read_text()):
            if not CLOSING_KEYWORDS.search(para):
                continue
            qualified = "default" in para.lower() and "branch" in para.lower()
            assert qualified, (
                f"{path.relative_to(PLUGIN)} names a GitHub closing keyword without saying "
                "it fires only for merges into the repository's DEFAULT branch. On a "
                "gitflow base the keyword is inert and the item silently stays open.\n\n"
                f"Paragraph:\n{para[:400]}"
            )
