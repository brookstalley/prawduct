"""The one-time cutover: `.prawduct/learnings.md` → `.claude/rules/learnings/`.

This command deletes a file no product can regenerate, so the suite is built
around two questions rather than around the code's shape.

**Did anything get lost?** :class:`TestByteAccounting` is the answer and the
reason the fixtures are real corpus rather than invented prose: every rule of
the source, after ``strip_links``, must appear *verbatim* in the concatenated
output. It runs over all three fleet shapes, mapped and unmapped, because the
loss modes differ — a topic that goes to an area file, a topic that goes to
core, and a paragraph rule that goes to ``## Unsorted`` are three different
paths through the writer and only one of them was ever the obvious one.

**Could it delete without leaving a destination?** :class:`TestRefusals` covers
the three ways that happens: a dirty legacy file (no committed version to
restore), a gitignored ``.claude/`` (the writes are invisible to git, so the
corpus survives only in one working tree), and the half-migrated ``both`` state
(where only a reader can tell which copy of a rule is current).

The fixtures under ``tests/fixtures/learnings_migrate/`` are derived from
discodon's 160KB corpus — the fleet's largest and hardest, and the source of
every link and metadata shape ``strip_links`` has to know about. ``mixed`` is a
30-rule excerpt carrying both section shapes, all four pointer forms, an
author's own HTML comment (which must survive) and one prawduct metadata comment
(which must not).

One contract is asserted across the module boundary rather than inside it:
:class:`TestTheOutputIsReadableByTheResolver` reads the written area files back
through ``learnings_files``. A migration that produced frontmatter the resolver
parses differently would leave every area file silently unscoped — the harness
loading one set and the Critic reading another, which is the failure the whole
layout exists to avoid.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from lib import learnings_files as lf  # noqa: E402
from lib import learnings_migrate as lm  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "learnings_migrate"
HOOK = _PLUGIN_ROOT / "bin" / "prawduct-hook"

SHAPES = ("topic", "paragraph", "mixed")


# --- helpers ----------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, timeout=30
    )


def repo(tmp_path: Path, shape: str, *, commit: bool = True) -> Path:
    """A fixture corpus in a real git repo — real because every refusal reads git.

    The fixture directory holds the corpus; its ``tree.txt`` names the code tree
    the corpus was written against, materialised here. `propose_map` reads only
    directory names and per-directory file counts, so empty files say everything
    the fixture needs to say — and stub ``.py`` files committed under ``tests/``
    would land inside the suite's own preference scans, which is a second thing
    for a fixture to answer for.

    Committing by default is not tidiness: an uncommitted legacy file is itself
    one of the refusals, so a fixture left dirty would make every other test in
    this file assert the same message.
    """
    root = tmp_path / shape
    shutil.copytree(FIXTURES / shape, root)
    manifest = root / "tree.txt"
    if manifest.is_file():
        for line in manifest.read_text(encoding="utf-8").split("\n"):
            rel = line.strip()
            if not rel or rel.startswith("#"):
                continue
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        manifest.unlink()
    _git(root, "init", "-q", ".")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    if commit:
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "corpus")
    return root


def run_hook(repo_dir: Path, *argv: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(repo_dir)
    return subprocess.run(
        [sys.executable, str(HOOK), "learnings-migrate", *argv],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def legacy_text(root: Path) -> str:
    return (root / lf.LEGACY_REL).read_text(encoding="utf-8")


def concatenated(migration: lm.Plan) -> str:
    return "\n".join(o.content for o in migration.outputs)


def full_map(root: Path) -> dict[str, list[str]]:
    """Every topic the proposer can scope, so the mapped path gets exercised."""
    return lm.propose_map(root, lm.parse_legacy(legacy_text(root)))


# --- parsing ----------------------------------------------------------------


class TestParseLegacy:
    def test_a_section_with_bullets_is_a_topic_and_one_without_is_a_rule(
        self, tmp_path: Path
    ):
        """The single discriminator, on the corpus that motivated it.

        `mixed` holds discodon's own two formats side by side: four bullet
        sections whose headings name a group, and ten headings that ARE the
        rule. Nothing here reads title length — a topic with a 60-character
        name and a rule with a short one must still land on the right side.
        """
        sections = lm.parse_legacy(legacy_text(repo(tmp_path, "mixed")))
        topics = [s for s in sections if s.is_topic]
        rules = [s for s in sections if not s.is_topic]
        assert [s.slug for s in topics] == [
            "pydantic-v2",
            "zmq-multi-process",
            "eval-model-bake-offs",
            "music-streaming",
        ]
        assert len(rules) == 10
        assert all(len(s.rules) == 1 for s in rules)
        assert sum(len(s.rules) for s in sections) == 30

    def test_the_paragraph_shape_parses_with_no_topics_at_all(self, tmp_path: Path):
        sections = lm.parse_legacy(legacy_text(repo(tmp_path, "paragraph")))
        assert sections
        assert not any(s.is_topic for s in sections)

    def test_the_topic_shape_parses_with_no_paragraph_rules_at_all(
        self, tmp_path: Path
    ):
        sections = lm.parse_legacy(legacy_text(repo(tmp_path, "topic")))
        assert sections
        assert all(s.is_topic for s in sections)

    def test_the_preamble_above_the_first_heading_is_dropped(self, tmp_path: Path):
        """It is the old file's title and its pointer at the file being deleted.

        Asserted on the output rather than on the parse, because "dropped" is
        only true if it does not reappear — and the core header the new layout
        ships would otherwise sit above a second, contradictory one.
        """
        root = repo(tmp_path, "mixed")
        assert "Concise rules from 15+ build sessions" in legacy_text(root)
        out = concatenated(lm.plan(root, full_map(root)))
        assert "Concise rules from 15+ build sessions" not in out
        assert out.count("# Learnings — core") == 1

    def test_a_heading_inside_a_fence_does_not_open_a_section(self):
        text = (
            "# Learnings\n\n"
            "## Markdown\n"
            "- **Fenced headings are content.** Like this:\n"
            "```\n"
            "## not a section\n"
            "```\n"
        )
        sections = lm.parse_legacy(text)
        assert [s.title for s in sections] == ["Markdown"]


class TestStripLinks:
    """Every pointer form the fleet actually wrote, and nothing beyond them."""

    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            (
                "- **A rule.** Body text. [detail](learnings-detail.md#a-rule)",
                "- **A rule.** Body text.",
            ),
            (
                "- **A rule.** Body. Detail: [ZMQ Details](learnings-detail.md#zmq).",
                "- **A rule.** Body.",
            ),
            (
                "- **A rule.** Body. (2026-07-30, eval-scope; detail in "
                "learnings-detail.md.)",
                "- **A rule.** Body. (2026-07-30, eval-scope)",
            ),
            (
                "- **A rule.** Body. (detail in learnings-detail.md.)",
                "- **A rule.** Body.",
            ),
            ("- **A rule.** Body. → detail.", "- **A rule.** Body."),
            (
                "- **A rule.** Retired in [history](learnings-history.md#a-rule).",
                "- **A rule.** Retired in.",
            ),
        ],
    )
    def test_each_pointer_form_is_removed(self, source: str, expected: str):
        assert lm.strip_links(source) == expected

    def test_prawduct_metadata_comments_go_and_an_authors_comment_stays(self):
        """The asymmetry is the point.

        `<!-- prawduct-learning: … -->` is bookkeeping the new layout keeps
        nowhere. An author's own comment is rationale someone wrote about their
        corpus, and a migration that swallowed it would be lossy in the one
        direction nobody would notice until the file was already deleted.
        """
        text = (
            "- **A rule.**\n"
            "<!-- prawduct-learning: id=LRN-1 promoted=2026-08-07 -->\n"
            "<!-- Pruned 2026-05-01: superseded by the AST canary.\n"
            "     See tests/unit/test_enum_compliance.py. -->\n"
        )
        out = lm.strip_links(text)
        assert "prawduct-learning" not in out
        assert "Pruned 2026-05-01" in out
        assert "test_enum_compliance.py" in out

    def test_a_rule_naming_no_pointer_is_returned_unchanged(self):
        text = "- **A rule about learnings and detail.** No pointer here."
        assert lm.strip_links(text) == text

    def test_removal_never_joins_two_lines(self):
        """`\\s*` before a pattern would eat the newline and merge two rules
        into one — a loss the byte accounting would see only as a near-miss."""
        text = (
            "- **First.** [detail](learnings-detail.md#first)\n"
            "- **Second.** Still its own rule.\n"
        )
        assert lm.strip_links(text).split("\n")[1].startswith("- **Second.**")


class TestSlug:
    @pytest.mark.parametrize(
        ("title", "expected"),
        [
            ("Eval & Model Bake-offs", "eval-model-bake-offs"),
            ("Postgres / YSQL backend (Yugabyte migration)",
             "postgres-ysql-backend-yugabyte-migration"),
            ("ZMQ & Multi-Process", "zmq-multi-process"),
            ("  Music / Streaming  ", "music-streaming"),
        ],
    )
    def test_titles_slug_to_file_stems(self, title: str, expected: str):
        assert lm.slug(title) == expected


# --- the map ----------------------------------------------------------------


class TestProposeMap:
    def test_a_topic_naming_a_second_level_directory_is_scoped_to_it(
        self, tmp_path: Path
    ):
        """The plan's worked example, on a tree shaped like the repo it came from.

        `discodon/` is the largest top-level directory, so its children are the
        second tier of candidates — which is where a single-package repo keeps
        its domains.
        """
        root = repo(tmp_path, "mixed")
        proposal = lm.propose_map(root, lm.parse_legacy(legacy_text(root)))
        assert proposal["eval-model-bake-offs"] == ["discodon/eval/**"]
        assert proposal["music-streaming"] == ["discodon/music/**"]

    def test_a_topic_matching_nothing_gets_no_entry_and_therefore_goes_to_core(
        self, tmp_path: Path
    ):
        """No entry, never a guessed one: an unscoped rule in core is merely
        unfiltered, while one scoped to the wrong directory is invisible."""
        root = repo(tmp_path, "mixed")
        proposal = lm.propose_map(root, lm.parse_legacy(legacy_text(root)))
        assert "pydantic-v2" not in proposal
        assert "zmq-multi-process" not in proposal

    def test_paragraph_rules_are_never_proposed_a_scope(self, tmp_path: Path):
        root = repo(tmp_path, "paragraph")
        assert lm.propose_map(root, lm.parse_legacy(legacy_text(root))) == {}

    def test_a_layer_named_directory_does_not_win_a_topic(self, tmp_path: Path):
        """`src/` and `lib/` name where code sits, not what it is about."""
        root = tmp_path / "layered"
        (root / "src").mkdir(parents=True)
        (root / "src" / "a.py").write_text("pass\n")
        sections = lm.parse_legacy("# L\n\n## Src Conventions\n- **A rule.**\n")
        assert lm.propose_map(root, sections) == {}


class TestMapFile:
    def test_the_printed_map_parses_back_unedited(self, tmp_path: Path):
        """The sidecar is written by the command and read by the command; a
        format only one half agreed with would fail on the agent's first run."""
        root = repo(tmp_path, "mixed")
        sections = lm.parse_legacy(legacy_text(root))
        proposal = lm.propose_map(root, sections)
        unmatched = [
            s.slug for s in sections if s.is_topic and s.slug not in proposal
        ]
        assert lm.parse_map(lm.format_map(proposal, unmatched)) == proposal

    def test_unmatched_topics_are_shown_commented_out_rather_than_omitted(self):
        text = lm.format_map({"eval": ["discodon/eval/**"]}, ["pydantic-v2"])
        assert "eval: [discodon/eval/**]" in text
        assert "# pydantic-v2: []" in text
        assert lm.parse_map(text) == {"eval": ["discodon/eval/**"]}

    def test_a_line_that_is_not_a_mapping_is_named_rather_than_skipped(self):
        with pytest.raises(ValueError, match="line 2"):
            lm.parse_map("a: [x/**]\nnot a mapping\n")

    def test_quotes_and_whitespace_are_tolerated(self):
        assert lm.parse_map(' eval : [ "a/**" , \'b/**\' ] \n') == {
            "eval": ["a/**", "b/**"]
        }


# --- the plan ---------------------------------------------------------------


class TestPlan:
    @pytest.mark.parametrize("shape", SHAPES)
    def test_core_is_always_written_and_always_first(self, tmp_path: Path, shape: str):
        """Core carries the descent obligation, so a corpus that mapped every
        topic to an area file must still get one."""
        root = repo(tmp_path, shape)
        migration = lm.plan(root, full_map(root))
        core_rel = f"{lf.RULES_DIR_REL}/{lf.CORE_NAME}"
        assert migration.outputs[0].rel == core_rel
        assert migration.outputs[0].content.startswith(lf.CORE_HEADER.rstrip("\n"))

    def test_a_mapped_topic_becomes_its_own_area_file(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        migration = lm.plan(root, full_map(root))
        rels = [o.rel for o in migration.outputs]
        assert f"{lf.RULES_DIR_REL}/eval-model-bake-offs.md" in rels
        assert f"{lf.RULES_DIR_REL}/music-streaming.md" in rels

    def test_an_unmapped_topic_keeps_its_heading_in_core(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        migration = lm.plan(root, full_map(root))
        assert "## Pydantic v2" in migration.outputs[0].content
        assert "## ZMQ & Multi-Process" in migration.outputs[0].content
        assert set(migration.unmapped) == {"pydantic-v2", "zmq-multi-process"}

    def test_paragraph_rules_land_under_one_unsorted_heading(self, tmp_path: Path):
        """One heading, so the next author can see at a glance what has not been
        filed — ten `## Unsorted` sections would file nothing."""
        root = repo(tmp_path, "mixed")
        core = lm.plan(root, full_map(root)).outputs[0].content
        assert core.count(f"## {lm.UNSORTED_HEADING}") == 1
        assert core.count("\n### ") == 10

    def test_a_paragraph_rules_body_travels_with_it(self, tmp_path: Path):
        root = repo(tmp_path, "paragraph")
        core = lm.plan(root).outputs[0].content
        assert "the docstring is the contract" in core

    @pytest.mark.parametrize("shape", SHAPES)
    def test_the_rule_counts_of_the_outputs_sum_to_the_sources(
        self, tmp_path: Path, shape: str
    ):
        """The dry run's headline number, checked against the parse rather than
        against itself — a writer that dropped a section would still report a
        self-consistent total."""
        root = repo(tmp_path, shape)
        sections = lm.parse_legacy(legacy_text(root))
        migration = lm.plan(root, full_map(root))
        assert migration.rules == sum(len(s.rules) for s in sections)

    def test_every_legacy_file_present_is_scheduled_for_deletion(
        self, tmp_path: Path
    ):
        root = repo(tmp_path, "mixed")
        assert lm.plan(root).deletions == list(lm.LEGACY_FILES)

    def test_a_legacy_file_that_is_absent_is_not_scheduled(self, tmp_path: Path):
        root = repo(tmp_path, "topic")
        assert lm.plan(root).deletions == [lf.LEGACY_REL]


class TestByteAccounting:
    """The losslessness contract, and the reason this command is trustworthy.

    Both sides are compared after the same `strip_links`, so what the cleaner
    removes is removed on purpose and *everything else must survive byte for
    byte*. Rule text rather than rule line, because a paragraph rule is written
    `## ` in the source and `### ` under `## Unsorted` in the output: the
    heading level is allowed to change, the rule is not.
    """

    @pytest.mark.parametrize("shape", SHAPES)
    def test_every_rule_of_the_source_survives_verbatim(
        self, tmp_path: Path, shape: str
    ):
        root = repo(tmp_path, shape)
        sections = lm.parse_legacy(legacy_text(root))
        output = concatenated(lm.plan(root, full_map(root)))
        missing = [
            rule for section in sections for rule in section.rules if rule not in output
        ]
        assert not missing, f"{len(missing)} rule(s) lost, first: {missing[:1]}"

    @pytest.mark.parametrize("shape", SHAPES)
    def test_the_accounting_holds_with_no_map_at_all(self, tmp_path: Path, shape: str):
        """The unmapped path writes core alone — a different branch of the
        writer, and the one a repo that skips `--propose-map` takes."""
        root = repo(tmp_path, shape)
        sections = lm.parse_legacy(legacy_text(root))
        output = concatenated(lm.plan(root))
        assert all(
            rule in output for section in sections for rule in section.rules
        )

    def test_the_check_is_not_vacuous(self, tmp_path: Path):
        """A parse that found no rules would make every assertion above pass."""
        root = repo(tmp_path, "mixed")
        sections = lm.parse_legacy(legacy_text(root))
        rule_bytes = sum(len(r.encode("utf-8")) for s in sections for r in s.rules)
        assert sum(len(s.rules) for s in sections) == 30
        assert rule_bytes > 5000

    def test_a_rule_the_writer_dropped_would_be_caught(self, tmp_path: Path):
        """The detector, detected. Asserting on real output only proves the
        writer agrees with itself unless a known-lossy output fails."""
        root = repo(tmp_path, "mixed")
        sections = lm.parse_legacy(legacy_text(root))
        lossy = concatenated(lm.plan(root, full_map(root))).replace(
            sections[0].rules[0], ""
        )
        assert any(
            rule not in lossy for section in sections for rule in section.rules
        )


class TestTheOutputIsReadableByTheResolver:
    """The cross-module contract: what this writes, Chunk 01's resolver reads.

    A migration whose frontmatter the resolver parsed differently would leave
    every area file unscoped — the harness loading one set of rules and the
    Critic's cross-check reading another, silently, with nothing red.
    """

    def test_an_area_files_globs_come_back_out_of_the_resolver(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        lm.apply(root, lm.plan(root, full_map(root)))
        layout = lf.resolve(root)
        assert layout.state == lf.STATE_NEW
        areas = {a.path.name: a.globs for a in layout.areas}
        assert areas["eval-model-bake-offs.md"] == ["discodon/eval/**"]

    def test_core_is_unscoped_so_the_harness_always_loads_it(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        lm.apply(root, lm.plan(root, full_map(root)))
        layout = lf.resolve(root)
        assert layout.core is not None
        assert lf.parse_frontmatter(layout.core.read_text(encoding="utf-8"))[0] == []

    def test_a_diff_in_the_scoped_directory_pulls_the_area_file_in(
        self, tmp_path: Path
    ):
        root = repo(tmp_path, "mixed")
        lm.apply(root, lm.plan(root, full_map(root)))
        layout = lf.resolve(root)
        names = [p.name for p in lf.files_for_paths(layout, ["discodon/eval/report.py"])]
        assert names == [lf.CORE_NAME, "eval-model-bake-offs.md"]
        elsewhere = [p.name for p in lf.files_for_paths(layout, ["web/src/App.tsx"])]
        assert elsewhere == [lf.CORE_NAME]


# --- refusals ---------------------------------------------------------------


class TestRefusals:
    def test_an_uncommitted_legacy_file_refuses(self, tmp_path: Path):
        """Git is this migration's undo, and a modified file's committed version
        is not the one about to be deleted."""
        root = repo(tmp_path, "mixed")
        (root / lf.LEGACY_REL).write_text("# Learnings\n\n## T\n- **New.**\n")
        refusals = lm.plan(root).refusals
        assert refusals and "uncommitted changes" in refusals[0]

    def test_an_untracked_legacy_file_refuses_too(self, tmp_path: Path):
        """The irreversible case: nothing to restore from, because it was never
        committed. Refusing costs one commit."""
        root = repo(tmp_path, "mixed", commit=False)
        refusals = lm.plan(root).refusals
        assert refusals and "uncommitted changes" in refusals[0]

    def test_a_gitignored_destination_refuses_and_says_what_to_unignore(
        self, tmp_path: Path
    ):
        """A product gitignoring `.claude/` is ordinary. Under that ignore
        `--apply` deletes tracked files and writes files git never sees: the
        session looks migrated and the clone comes back empty."""
        root = repo(tmp_path, "mixed", commit=False)
        (root / ".gitignore").write_text(".claude/\n")
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "corpus")
        refusals = lm.plan(root).refusals
        assert refusals
        assert "gitignored" in refusals[0]
        assert ".claude/rules/" in refusals[0]

    def test_the_both_state_refuses_and_points_at_the_hand_fold(
        self, tmp_path: Path
    ):
        """Two corpora, and only a reader can tell which copy of a rule is the
        current one — so this is not a transform, it is a decision."""
        root = repo(tmp_path, "mixed")
        lf.scaffold_core(root)
        migration = lm.plan(root)
        assert migration.state == lf.STATE_BOTH
        assert migration.refusals and "by hand" in migration.refusals[0]
        assert not migration.outputs

    def test_a_migrated_repo_reports_nothing_to_do(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        lm.apply(root, lm.plan(root, full_map(root)))
        migration = lm.plan(root)
        assert migration.nothing_to_do
        assert not migration.refusals
        assert not migration.outputs

    def test_a_repo_with_no_corpus_at_all_reports_nothing_to_do(
        self, tmp_path: Path
    ):
        root = tmp_path / "empty"
        root.mkdir()
        assert lm.plan(root).nothing_to_do

    def test_apply_refuses_a_plan_carrying_refusals(self, tmp_path: Path):
        """The guard lives in `apply` as well as in the command: a caller that
        skipped the dry run must not be able to skip the reason with it."""
        root = repo(tmp_path, "mixed")
        (root / lf.LEGACY_REL).write_text("# Learnings\n\n## T\n- **New.**\n")
        migration = lm.plan(root)
        with pytest.raises(lm.MigrateRefused):
            lm.apply(root, migration)
        assert (root / lf.LEGACY_REL).is_file()

    def test_a_non_git_directory_is_migrated_rather_than_refused(
        self, tmp_path: Path
    ):
        """Neither guard has anything to protect outside a repo: no uncommitted
        changes exist and no ignore rule applies. Refusing there would block a
        real, if unusual, product for a risk it does not carry."""
        root = tmp_path / "nogit"
        shutil.copytree(FIXTURES / "topic", root)
        migration = lm.plan(root)
        assert not migration.refusals
        assert migration.outputs


class TestApply:
    def test_it_writes_the_plan_and_deletes_the_corpus(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        migration = lm.plan(root, full_map(root))
        lm.apply(root, migration)
        for output in migration.outputs:
            assert (root / output.rel).read_text(encoding="utf-8") == output.content
        for rel in lm.LEGACY_FILES:
            assert not (root / rel).exists()

    def test_the_second_run_changes_nothing(self, tmp_path: Path):
        """Idempotence as the operator experiences it: re-running after a
        migration must not append, duplicate, or re-delete."""
        root = repo(tmp_path, "mixed")
        lm.apply(root, lm.plan(root, full_map(root)))
        before = {
            p: p.read_bytes() for p in (root / lf.RULES_DIR_REL).rglob("*.md")
        }
        second = lm.plan(root)
        assert second.nothing_to_do
        assert {p: p.read_bytes() for p in (root / lf.RULES_DIR_REL).rglob("*.md")} == (
            before
        )


# --- the command ------------------------------------------------------------


class TestTheCommand:
    def test_propose_map_prints_the_sidecar_format(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        proc = run_hook(root, "--propose-map")
        assert proc.returncode == 0, proc.stderr
        assert "eval-model-bake-offs: [discodon/eval/**]" in proc.stdout
        assert "# pydantic-v2: []" in proc.stdout

    def test_propose_map_writes_nothing(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        run_hook(root, "--propose-map")
        assert not (root / lf.RULES_DIR_REL).exists()
        assert (root / lf.LEGACY_REL).is_file()

    def test_the_dry_run_reports_each_file_with_its_bytes_and_rules(
        self, tmp_path: Path
    ):
        """The plan's own acceptance criterion: an operator reads the output
        sizes by eye before authorising the only irreversible step."""
        root = repo(tmp_path, "mixed")
        map_file = tmp_path / "map.txt"
        map_file.write_text(run_hook(root, "--propose-map").stdout, encoding="utf-8")

        proc = run_hook(root, "--map", str(map_file))

        assert proc.returncode == 0, proc.stderr
        assert "dry run" in proc.stdout
        for name in ("core.md", "eval-model-bake-offs.md", "music-streaming.md"):
            line = next(ln for ln in proc.stdout.splitlines() if name in ln)
            assert "bytes" in line and "rules" in line
        assert "30 rules" in proc.stdout
        assert not (root / lf.RULES_DIR_REL).exists()

    def test_apply_migrates_and_a_second_run_is_a_no_op(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        map_file = tmp_path / "map.txt"
        map_file.write_text(run_hook(root, "--propose-map").stdout, encoding="utf-8")

        applied = run_hook(root, "--apply", "--map", str(map_file))
        assert applied.returncode == 0, applied.stderr
        assert (root / lf.RULES_DIR_REL / lf.CORE_NAME).is_file()
        assert not (root / lf.LEGACY_REL).exists()

        again = run_hook(root)
        assert again.returncode == 0
        assert "nothing to do" in again.stdout

    def test_a_refusal_exits_2_and_names_the_reason_on_stderr(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        (root / lf.LEGACY_REL).write_text("# Learnings\n\n## T\n- **New.**\n")
        proc = run_hook(root, "--apply")
        assert proc.returncode == 2
        assert "REFUSED" in proc.stderr
        assert (root / lf.LEGACY_REL).is_file()

    def test_a_gitignored_destination_refuses_the_apply(self, tmp_path: Path):
        root = repo(tmp_path, "mixed", commit=False)
        (root / ".gitignore").write_text(".claude/\n")
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "corpus")

        proc = run_hook(root, "--apply")

        assert proc.returncode == 2
        assert "gitignored" in proc.stderr
        assert (root / lf.LEGACY_REL).is_file()
        assert not (root / lf.RULES_DIR_REL).exists()

    def test_propose_map_and_apply_together_are_a_usage_error(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        proc = run_hook(root, "--propose-map", "--apply")
        assert proc.returncode == 2
        assert "Nothing ran" in proc.stderr
        assert (root / lf.LEGACY_REL).is_file()

    def test_map_without_a_value_is_refused(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        proc = run_hook(root, "--map")
        assert proc.returncode == 2
        assert "--map needs a value" in proc.stderr

    def test_an_unreadable_map_file_is_refused_by_name(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        proc = run_hook(root, "--map", str(tmp_path / "absent.txt"))
        assert proc.returncode == 2
        assert "cannot read --map" in proc.stderr

    def test_a_malformed_map_file_is_refused_by_line(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        bad = tmp_path / "bad.txt"
        bad.write_text("eval: [a/**]\nthis is not a mapping\n", encoding="utf-8")
        proc = run_hook(root, "--map", str(bad))
        assert proc.returncode == 2
        assert "line 2" in proc.stderr

    def test_an_unknown_flag_is_refused_and_named(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        proc = run_hook(root, "--zzz-unrecognised-token")
        assert proc.returncode == 2
        assert "--zzz-unrecognised-token" in proc.stderr
        assert (root / lf.LEGACY_REL).is_file()

    def test_json_carries_the_plan_a_caller_would_otherwise_parse_by_eye(
        self, tmp_path: Path
    ):
        root = repo(tmp_path, "mixed")
        proc = run_hook(root, "--json")
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        assert payload["state"] == lf.STATE_LEGACY
        assert payload["applied"] is False
        assert payload["total_rules"] == 30
        assert payload["outputs"][0]["path"].endswith(lf.CORE_NAME)
        assert set(payload["deletions"]) == set(lm.LEGACY_FILES)
