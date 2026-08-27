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

**Honest limits (Principle 5).** These are prose guards over a curated
vocabulary, not a proof. Three things they do not do. They cannot catch a
paraphrase that never writes the keyword ("the merge will close the issue") --
the same scoping rationale `tests/test_backlog_instruction_surface.py` states for
its own vocabulary. `_paragraphs` splits on blank lines, so a whole markdown
bullet list is one "paragraph": on list-shaped surfaces the locality these guards
claim is looser than it reads, and a qualification several bullets away still
counts. And the closing-keyword check asserts that two words are *present*, not
that the claim around them is *right* -- it prevents omission, not divergence, so
a future correction to GitHub's semantics has to be applied at each site.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "plugin"
PROTOCOL = PLUGIN / "skills" / "pr" / "review-protocol.md"
PR_SKILL = PLUGIN / "skills" / "pr" / "SKILL.md"
BACKLOG_SKILL = PLUGIN / "skills" / "backlog" / "SKILL.md"

# Append-only history. A release note that writes `Closes #12` is recording what
# happened, not instructing anyone, and editing it to satisfy a prose guard would
# mean rewriting history to please a test.
_RECORD_FILENAMES = {"CHANGELOG.md", "change-log.md", "learnings.md", "learnings-detail.md"}


def instruction_surfaces() -> list[Path]:
    """Every live instruction surface in the repo, bounded by the property that
    justifies the guard — "prose that tells an agent what to do" — rather than by
    the directory it happens to sit in. `documentation/` carries runbooks and
    requirements that instruct exactly as `plugin/` does; excluding it would have
    left the class open at the container boundary, which is the failure this
    repo's own learnings name."""
    out = []
    for root in (PLUGIN, REPO / "documentation"):
        if not root.is_dir():
            continue
        for path in root.rglob("*.md"):
            if path.name in _RECORD_FILENAMES:
                continue
            if "archive" in path.parts:
                continue
            out.append(path)
    return sorted(out)

# The keyword family GitHub actually honours, spelled as prose writes them.
CLOSING_KEYWORDS = re.compile(
    # GitHub honours the keyword only immediately before an issue reference, so
    # require one -- a bare "closes the loop" is not a closing keyword. This
    # narrows the match; it does not make it exact. "suggested fix #2" still
    # matches, because the shape is genuinely ambiguous in prose. That residual is
    # accepted rather than chased: the surface set excludes append-only records,
    # and every live hit today carries the qualification. Narrowing further would
    # start missing the instruction prose this exists to catch, and a guard that
    # misfires trains its reader to ignore the one real catch.
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(?:\d+|N)\b",
    re.IGNORECASE,
)


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
        """Create Step 4 validates the field; the Update Flow consumes it. Two
        sites, asserted separately — a bare occurrence count does not do this
        job, because Create Step 4 alone contributes three and the Update Flow
        half could be deleted whole with the count still passing."""
        skill = PR_SKILL.read_text()
        assert "git merge-base --is-ancestor <commit_reviewed> HEAD" in skill, (
            "Create Step 4 no longer validates `commit_reviewed` against HEAD. That check "
            "is what catches a rebase or amend moving the tree out from under a review."
        )
        assert "git diff --name-only <commit_reviewed>..HEAD" in skill, (
            "The Update Flow no longer prices its delta from `commit_reviewed` — the "
            "consumer the field exists for. Without it the field is written and never read."
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
    @pytest.mark.parametrize("path", instruction_surfaces(), ids=lambda p: p.name)
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
                f"{path.relative_to(REPO)} names a GitHub closing keyword without saying "
                "it fires only for merges into the repository's DEFAULT branch. On a "
                "gitflow base the keyword is inert and the item silently stays open.\n\n"
                f"Paragraph:\n{para[:400]}"
            )

class TestIssuesBackendCloseIsDeferred:
    """The remedy this bugfix installs, pinned. Without these, deleting the
    deferral from either surface leaves the whole suite green — a bugfix whose
    behavioural fix has no regression test, in a repo whose idiom is to pin
    exactly such prose norms.

    Class-scoped where it can be: the timing rule has ONE owner, and what the
    other surfaces must not do is restate it. That is checkable — a surface that
    tells the reader to archive "now, on this branch" unconditionally is asserting
    the timing itself."""

    def test_backlog_skill_owns_the_timing_and_splits_it_by_backend(self):
        """`skills/backlog/SKILL.md` is the single home. It must name both
        backends where it states when the call runs — the unconditional version
        was false for every Issues-backend product (#697)."""
        text = BACKLOG_SKILL.read_text()
        para = next(
            (p for p in _paragraphs(text) if "When to mark shipped" in p), None
        )
        assert para, "`skills/backlog/SKILL.md` lost its 'When to mark shipped' rule"
        block = text[text.index(para):text.index(para) + 3000]
        assert "Markdown backend" in block and "Issues backend" in block, (
            "The 'When to mark shipped' rule no longer splits by backend. Archiving is "
            "atomic with the merge only when it IS a commit: a markdown archive is a file "
            "edit and rides the branch, an Issues close is an API call that does not."
        )
        assert "backlog_service_repo" in block, (
            "The rule must name the scalar that selects the backend, or the reader "
            "cannot tell which half applies to them."
        )

    def test_pr_skill_defers_the_close_to_the_merge_and_names_the_step(self):
        skill = PR_SKILL.read_text()
        assert "Close the backlog items this PR resolves" in skill, (
            "The Merge Flow lost its named close step — the sole discharge point for the "
            "deferral Step 1d makes."
        )
        step_1d = skill[skill.index("Step 1d"):skill.index("### Step 2")]
        assert "Close the backlog items this PR resolves" in step_1d, (
            "Step 1d defers the Issues-backend close but no longer names where it lands. "
            "A deferral with no named target is a drop."
        )

    def test_the_close_step_precedes_the_deletions_that_destroy_its_record(self):
        """Ordering is the property, so assert the order — not the numbers. Steps
        5-7 delete the branch and the evidence file; a close numbered after them
        has had its own audit trail deleted first."""
        skill = PR_SKILL.read_text()
        merge_flow = skill[skill.index("## Merge Flow"):]
        close_at = merge_flow.index("Close the backlog items this PR resolves")
        delete_at = merge_flow.index("Delete remote branch")
        evidence_at = merge_flow.index("Clean up evidence file")
        assert close_at < delete_at < evidence_at, (
            "The close must come before the branch and evidence deletions. Those destroy "
            "the local artifacts that record the close was owed, and this step is its own "
            "only detector until the GV3 reconciliation sweep exists."
        )

    def test_no_surface_restates_the_timing_as_unconditionally_on_the_branch(self):
        """The class: any live instruction surface that tells the reader WHEN to
        archive a backlog item is restating the timing the backlog skill owns —
        and every such restatement found so far took the on-branch form, which is
        false on the Issues backend. The owner's own rule paragraph is exempt: it
        states the branch case as one half of an explicit split, which is the
        correct form. The exemption is scoped to that paragraph and not to the
        owner FILE — the file-wide version hid a live member sitting three
        sections below the rule.

        Matched as a family of phrasings rather than the one sentence that broke,
        because pinning that sentence would pass the moment someone reworded it.
        The residual limit is real and stated in the module docstring: a
        paraphrase outside the family still escapes. What this buys is that the
        obvious rewordings do not."""
        # Each names a TIME for the call. "on the branch that closes it" is the
        # owner's own phrasing and appears in its routing sentences, so it is
        # matched too -- only the rule paragraph itself is exempt.
        TIMING_CLAIMS = re.compile(
            r"archive it now"
            r"|now, on this branch"
            r"|on this branch,? so it ships"
            r"|so it ships in this PR"
            r"|archiv\w+ (?:an? )?item \*?on the branch",
            re.IGNORECASE,
        )
        offenders = []
        for path in instruction_surfaces():
            for para in _paragraphs(path.read_text()):
                # The owner's OWN rule is the one place a timing may be stated,
                # and it states both halves. Two narrowings, each from a real
                # miss: exempting the whole owner FILE hid a live member three
                # sections below the rule, and keying the exemption on the
                # section NAME re-exempted it the moment it routed to the owner
                # by that name. The key is the rule's own opening clause, which
                # only the rule itself carries.
                if path == BACKLOG_SKILL and "the timing rule lives here" in para:
                    continue
                if "status=shipped" not in para:
                    continue
                hit = TIMING_CLAIMS.search(para)
                if hit:
                    offenders.append(
                        f"{path.relative_to(REPO)}: ...{hit.group(0)}... in {para[:160]}"
                    )
        assert not offenders, (
            "These surfaces state WHEN a backlog item is archived, which the backlog "
            "skill's 'When to mark shipped' rule owns — and state it in the on-branch "
            "form that is false on the Issues backend, where an API close on an unmerged "
            "branch survives an abandoned PR. Route to the owner instead of "
            "restating:\n" + "\n".join(offenders)
        )

    def test_the_ledger_cross_check_on_commit_reviewed_is_present(self):
        """The remedy for a `commit_reviewed` advanced after the fact. The
        is-ancestor check cannot see that failure — every commit on the branch
        passes it — so the second witness is the `review.pr` ledger event, whose
        payload is the evidence record verbatim. Unpinned, this is the same shape
        the deferral guard above was added for: a remedy with nothing holding it."""
        skill = PR_SKILL.read_text()
        assert "review.pr" in skill and ".review.commit_reviewed" in skill, (
            "The Update Flow no longer cross-checks `commit_reviewed` against the "
            "ledger's independent copy. Without it the field is self-certifying, and "
            "the prohibition on advancing it has nothing behind it."
        )
