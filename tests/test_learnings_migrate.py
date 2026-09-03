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

SHAPES = ("topic", "paragraph", "mixed", "collision", "flat")


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


def migrated_text(root: Path, mapping: dict[str, list[str]] | None = None) -> str:
    """Apply the migration, then read every rules file back **off disk**.

    Asserting against `Plan.outputs` only proves the writer agrees with itself.
    Two outputs can name one path — and then the tree holds one of them while
    the plan still reports both, which is a loss no in-memory check can see.
    The filesystem is the thing the harness will load, so it is the thing the
    accounting is done against.
    """
    lm.apply(root, lm.plan(root, mapping))
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((root / lf.RULES_DIR_REL).rglob("*.md"))
    )


def sections_of(root: Path) -> list[lm.Section]:
    """The corpus's sections, dropping the parser's second return value."""
    return lm.parse_legacy(legacy_text(root))[0]


def full_map(root: Path) -> dict[str, list[str]]:
    """Every topic the proposer can scope, so the mapped path gets exercised."""
    return lm.propose_map(root, sections_of(root))


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
        sections = sections_of(repo(tmp_path, "mixed"))
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
        sections = sections_of(repo(tmp_path, "paragraph"))
        assert sections
        assert not any(s.is_topic for s in sections)

    def test_the_topic_shape_parses_with_no_paragraph_rules_at_all(
        self, tmp_path: Path
    ):
        sections = sections_of(repo(tmp_path, "topic"))
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
        out = migrated_text(root, full_map(root))
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
        sections, _dropped = lm.parse_legacy(text)
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
        proposal = lm.propose_map(root, sections_of(root))
        assert proposal["eval-model-bake-offs"] == ["discodon/eval/**"]
        assert proposal["music-streaming"] == ["discodon/music/**"]

    def test_a_topic_matching_nothing_gets_no_entry_and_therefore_goes_to_core(
        self, tmp_path: Path
    ):
        """No entry, never a guessed one: an unscoped rule in core is merely
        unfiltered, while one scoped to the wrong directory is invisible."""
        root = repo(tmp_path, "mixed")
        proposal = lm.propose_map(root, sections_of(root))
        assert "pydantic-v2" not in proposal
        assert "zmq-multi-process" not in proposal

    def test_paragraph_rules_are_never_proposed_a_scope(self, tmp_path: Path):
        root = repo(tmp_path, "paragraph")
        assert lm.propose_map(root, sections_of(root)) == {}

    def test_a_layer_named_directory_does_not_win_a_topic(self, tmp_path: Path):
        """`src/` and `lib/` name where code sits, not what it is about."""
        root = tmp_path / "layered"
        (root / "src").mkdir(parents=True)
        (root / "src" / "a.py").write_text("pass\n")
        sections, _ = lm.parse_legacy("# L\n\n## Src Conventions\n- **A rule.**\n")
        assert lm.propose_map(root, sections) == {}


class TestMapFile:
    def test_the_printed_map_parses_back_unedited(self, tmp_path: Path):
        """The sidecar is written by the command and read by the command; a
        format only one half agreed with would fail on the agent's first run."""
        root = repo(tmp_path, "mixed")
        sections = sections_of(root)
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
        sections = sections_of(root)
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
        sections = sections_of(root)
        output = migrated_text(root, full_map(root))
        missing = [
            rule for section in sections for rule in section.rules if rule not in output
        ]
        assert not missing, f"{len(missing)} rule(s) lost, first: {missing[:1]}"

    @pytest.mark.parametrize("shape", SHAPES)
    def test_the_accounting_holds_with_no_map_at_all(self, tmp_path: Path, shape: str):
        """The unmapped path writes core alone — a different branch of the
        writer, and the one a repo that skips `--propose-map` takes."""
        root = repo(tmp_path, shape)
        sections = sections_of(root)
        output = migrated_text(root)
        assert all(
            rule in output for section in sections for rule in section.rules
        )

    def test_the_check_is_not_vacuous(self, tmp_path: Path):
        """A parse that found no rules would make every assertion above pass."""
        root = repo(tmp_path, "mixed")
        sections = sections_of(root)
        rule_bytes = sum(len(r.encode("utf-8")) for s in sections for r in s.rules)
        assert sum(len(s.rules) for s in sections) == 30
        assert rule_bytes > 5000

    def test_a_rule_the_writer_dropped_would_be_caught(self, tmp_path: Path):
        """The detector, detected. Asserting on real output only proves the
        writer agrees with itself unless a known-lossy output fails."""
        root = repo(tmp_path, "mixed")
        sections = sections_of(root)
        lossy = migrated_text(root, full_map(root)).replace(
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


class TestSlugCollisions:
    """Two sections wanting one file, which is a silent overwrite by default.

    `plan()` used to emit one `OutputFile` per mapped topic keyed on
    `slug(title)` and `apply()` wrote them in list order, so `## Testing` and
    `## Testing!` — one directory match, one map entry, two sections — both
    addressed `testing.md` and the second replaced the first. The sharpest
    instance was a topic titled "Core": its file IS `core.md`, so it took out
    the header, every unmapped topic and the whole `## Unsorted` block.

    Outputs are now keyed by destination path and sections landing on one path
    merge, which is the lossless answer and makes the reserved-name case fall
    out of the same rule rather than needing its own.
    """

    MAP = {"testing": ["src/testing/**"], "core": ["src/core/**"]}

    def test_two_topics_that_slug_alike_produce_one_file_not_two_writes(
        self, tmp_path: Path
    ):
        root = repo(tmp_path, "collision")
        migration = lm.plan(root, self.MAP)
        rels = [o.rel for o in migration.outputs]
        assert len(rels) == len(set(rels)), f"duplicate destination: {rels}"
        assert rels.count(f"{lf.RULES_DIR_REL}/testing.md") == 1

    def test_both_headings_and_all_their_rules_survive_the_merge(
        self, tmp_path: Path
    ):
        root = repo(tmp_path, "collision")
        lm.apply(root, lm.plan(root, self.MAP))
        area = (root / lf.RULES_DIR_REL / "testing.md").read_text(encoding="utf-8")
        assert "# Testing\n" in area
        assert "# Testing!\n" in area
        assert "A vacuous test is worse than no test." in area
        assert "this goes red without X" in area

    def test_a_topic_slugging_to_core_does_not_replace_core(self, tmp_path: Path):
        """The header, the unsorted block and the topic's own rules coexist."""
        root = repo(tmp_path, "collision")
        lm.apply(root, lm.plan(root, self.MAP))
        core = (root / lf.RULES_DIR_REL / lf.CORE_NAME).read_text(encoding="utf-8")
        assert core.startswith(lf.CORE_HEADER.rstrip("\n"))
        assert "The core loop owns the clock." in core
        assert f"## {lm.UNSORTED_HEADING}" in core

    def test_every_merge_is_named_in_the_plan(self, tmp_path: Path):
        """A fold the operator did not ask for is one they must be able to see —
        the `core` merge especially, because it silently drops the scoping the
        agent wrote into the map."""
        root = repo(tmp_path, "collision")
        merges = lm.plan(root, self.MAP).merges
        assert any("both slug to 'testing'" in m for m in merges)
        assert any("always-loaded file" in m and "'Core'" in m for m in merges)

    def test_the_merges_reach_the_operator_on_the_apply_path(self, tmp_path: Path):
        root = repo(tmp_path, "collision")
        map_file = tmp_path / "map.txt"
        map_file.write_text(
            "testing: [src/testing/**]\ncore: [src/core/**]\n", encoding="utf-8"
        )
        proc = run_hook(root, "--apply", "--map", str(map_file))
        assert proc.returncode == 0, proc.stderr
        assert "merged:" in proc.stdout

    def test_the_rule_count_still_matches_the_corpus_after_merging(
        self, tmp_path: Path
    ):
        """The dry run's headline number must describe the tree, not the plan:
        an overwrite used to leave it over-stating what landed."""
        root = repo(tmp_path, "collision")
        sections = sections_of(root)
        migration = lm.plan(root, self.MAP)
        assert migration.rules == sum(len(s.rules) for s in sections)


class TestUnknownMapKeys:
    """A typo'd slug scopes nothing and says nothing — the mirror of the
    unparseable-line refusal `parse_map` already carries.

    Left silent, the prescribed `--propose-map` -> edit -> `--apply --map` flow
    ends with the agent believing its scoping took while the rules went to the
    always-loaded file, which is the inverse of what the budget gate is for.
    """

    def test_a_key_matching_no_section_refuses_and_names_the_key(
        self, tmp_path: Path
    ):
        root = repo(tmp_path, "mixed")
        refusals = lm.plan(root, {"evel-model-bake-offs": ["discodon/eval/**"]}).refusals
        assert refusals
        assert any("'evel-model-bake-offs'" in r for r in refusals)

    def test_a_key_naming_a_paragraph_rule_refuses_too(self, tmp_path: Path):
        """Only topics can be scoped; a paragraph rule's slug in the map is the
        same mistake wearing a real string."""
        root = repo(tmp_path, "mixed")
        rule = next(s for s in sections_of(root) if not s.is_topic)
        refusals = lm.plan(root, {rule.slug: ["web/**"]}).refusals
        assert any("matching no section" in r for r in refusals)

    def test_the_command_refuses_and_writes_nothing(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        bad = tmp_path / "bad.txt"
        bad.write_text("no-such-topic: [web/**]\n", encoding="utf-8")
        proc = run_hook(root, "--apply", "--map", str(bad))
        assert proc.returncode == 1
        assert "no-such-topic" in proc.stderr
        assert not (root / lf.RULES_DIR_REL).exists()
        assert (root / lf.LEGACY_REL).is_file()

    def test_a_correct_map_is_not_refused(self, tmp_path: Path):
        """The guard's failure mode is over-refusal, which would break the flow
        it exists to protect."""
        root = repo(tmp_path, "mixed")
        assert not lm.plan(root, full_map(root)).refusals

    def test_the_unmapped_topics_are_named_on_the_apply_path(self, tmp_path: Path):
        """Not only the dry run: an apply that reported just what it wrote let
        the scoping decision go unexamined at the one moment it becomes real."""
        root = repo(tmp_path, "mixed")
        map_file = tmp_path / "map.txt"
        map_file.write_text(run_hook(root, "--propose-map").stdout, encoding="utf-8")
        proc = run_hook(root, "--apply", "--map", str(map_file))
        assert proc.returncode == 0, proc.stderr
        assert "no glob mapping" in proc.stdout
        assert "pydantic-v2" in proc.stdout


class TestAnInterruptedApply:
    """A transient write error must not cost a hand-merge of a 160KB corpus.

    `apply` writes every file before deleting anything, so a failure part-way
    leaves the rules tree half-written and the legacy file intact — which
    `resolve()` reports as `both`, the one state the command refused outright.
    Recovery is decided from the tree rather than from the exception, so an
    interrupt no `except` could have seen recovers the same way.
    """

    def _half_apply(self, root: Path, mapping: dict[str, list[str]]) -> lm.Plan:
        """Write only the first output — exactly what an OSError on the second
        would have left behind."""
        migration = lm.plan(root, mapping)
        first = migration.outputs[0]
        path = root / first.rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(first.content, encoding="utf-8")
        return migration

    def test_the_half_written_tree_is_recognised_and_finished(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        mapping = full_map(root)
        self._half_apply(root, mapping)
        assert lf.resolve(root).state == lf.STATE_BOTH

        resumed = lm.plan(root, mapping)

        assert resumed.resumed
        assert not resumed.refusals
        lm.apply(root, resumed)
        assert lf.resolve(root).state == lf.STATE_NEW
        assert not (root / lf.LEGACY_REL).exists()

    def test_resuming_loses_nothing(self, tmp_path: Path):
        """The recovery path is a full migration, not a patch-up: the byte
        accounting has to hold across it too."""
        root = repo(tmp_path, "mixed")
        mapping = full_map(root)
        sections = sections_of(root)
        self._half_apply(root, mapping)
        lm.apply(root, lm.plan(root, mapping))
        tree = "\n".join(
            p.read_text(encoding="utf-8")
            for p in sorted((root / lf.RULES_DIR_REL).rglob("*.md"))
        )
        assert all(r in tree for s in sections for r in s.rules)

    def test_a_both_holding_anything_else_still_refuses(self, tmp_path: Path):
        """One extra file nobody planned, and it is a two-corpus repo again —
        the distinction has to be strict or the fold directive stops meaning
        anything."""
        root = repo(tmp_path, "mixed")
        mapping = full_map(root)
        self._half_apply(root, mapping)
        (root / lf.RULES_DIR_REL / "hand-written.md").write_text(
            "# Someone's own rules\n", encoding="utf-8"
        )
        migration = lm.plan(root, mapping)
        assert not migration.resumed
        assert migration.refusals and "by hand" in migration.refusals[0]

    def test_a_planned_file_with_different_content_still_refuses(
        self, tmp_path: Path
    ):
        root = repo(tmp_path, "mixed")
        mapping = full_map(root)
        self._half_apply(root, mapping)
        core = root / lf.RULES_DIR_REL / lf.CORE_NAME
        core.write_text(core.read_text(encoding="utf-8") + "\n- **Edited.**\n")
        assert not lm.plan(root, mapping).resumed

    def test_the_failure_names_the_files_that_reached_disk(self, tmp_path: Path):
        """`failed — <exc>` left the operator with no way to know what state the
        repo was in. The written set IS the answer."""
        root = repo(tmp_path, "mixed")
        migration = lm.plan(root, full_map(root))
        # A directory where the second output's file must go: the write raises,
        # the first output has already landed.
        blocked = root / migration.outputs[1].rel
        blocked.mkdir(parents=True)

        with pytest.raises(lm.MigrateInterrupted) as caught:
            lm.apply(root, migration)

        assert caught.value.written == [migration.outputs[0].rel]
        assert (root / lf.LEGACY_REL).is_file(), "nothing was deleted"

    def test_the_command_reports_the_written_set_and_how_to_recover(
        self, tmp_path: Path
    ):
        root = repo(tmp_path, "mixed")
        map_file = tmp_path / "map.txt"
        map_file.write_text(run_hook(root, "--propose-map").stdout, encoding="utf-8")
        migration = lm.plan(root, lm.parse_map(map_file.read_text(encoding="utf-8")))
        (root / migration.outputs[1].rel).mkdir(parents=True)

        proc = run_hook(root, "--apply", "--map", str(map_file))

        assert proc.returncode == 1
        assert "INTERRUPTED" in proc.stderr
        assert migration.outputs[0].rel in proc.stderr
        assert "Re-run" in proc.stderr

    def test_the_resume_is_announced_rather_than_silent(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        map_file = tmp_path / "map.txt"
        map_file.write_text(run_hook(root, "--propose-map").stdout, encoding="utf-8")
        self._half_apply(root, lm.parse_map(map_file.read_text(encoding="utf-8")))

        proc = run_hook(root, "--map", str(map_file))

        assert proc.returncode == 0, proc.stderr
        assert "resuming an interrupted --apply" in proc.stdout



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
        assert refusals
        assert any("never committed" in r for r in refusals)
        assert any("cannot give it back" in r for r in refusals)

    def test_a_gitignored_legacy_corpus_refuses(self, tmp_path: Path):
        """R-2's case, and the one `git status` cannot see.

        Porcelain omits ignored paths entirely, so a repo that ignores
        `.prawduct/` reads *clean* — and `--apply` would then unlink a corpus
        git has never held a byte of. Deciding from tracking is what closes it,
        and the reason has to say `ignored`, because "commit it first" is
        useless advice about a file an ignore rule keeps out of the index.
        """
        root = repo(tmp_path, "mixed", commit=False)
        (root / ".gitignore").write_text(".prawduct/\n")
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "everything but the corpus")

        assert _git(root, "status", "--porcelain").stdout.strip() == ""
        refusals = lm.plan(root).refusals
        assert refusals
        assert any("ignored by git" in r for r in refusals)
        assert any(lf.LEGACY_REL in r for r in refusals)

    def test_the_ignored_corpus_is_still_there_after_a_refused_apply(
        self, tmp_path: Path
    ):
        """The assertion that matters is on the file, not the exit code."""
        root = repo(tmp_path, "mixed", commit=False)
        (root / ".gitignore").write_text(".prawduct/\n")
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "everything but the corpus")
        before = (root / lf.LEGACY_REL).read_bytes()

        proc = run_hook(root, "--apply")

        assert proc.returncode == 1
        assert (root / lf.LEGACY_REL).read_bytes() == before

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

    def test_a_divergent_both_refuses_and_points_at_the_hand_fold(
        self, tmp_path: Path
    ):
        """Two corpora, and only a reader can tell which copy of a rule is the
        current one — so this is not a transform, it is a decision.

        `scaffold_core` writes the bare header, which is not what this plan
        would write, so the state is genuinely divergent rather than an
        interrupted run of it.
        """
        root = repo(tmp_path, "mixed")
        lf.scaffold_core(root)
        migration = lm.plan(root)
        assert migration.state == lf.STATE_BOTH
        assert migration.refusals and "by hand" in migration.refusals[0]
        assert not migration.resumed

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


class TestTheFlatShape:
    """A corpus with no `## ` headings at all — and the shape that made this
    command destructive.

    `# Learnings` then a plain bullet list is what prawduct's own starter file
    writes and what the oldest fleet corpora look like. Parsing sections only on
    `## ` made every one of those lines preamble, so the corpus parsed to zero
    rules, the plan was a header-only `core.md` with all three legacy files in
    `deletions`, and no guard fired: `--apply` would write an empty corpus and
    unlink the real one.
    """

    MINIMAL = "# Learnings\n\n- a standing rule\n"

    def test_the_minimal_headingless_corpus_yields_its_rule(self):
        sections, dropped = lm.parse_legacy(self.MINIMAL)
        assert [r for s in sections for r in s.rules] == ["a standing rule"]
        assert dropped == ["Learnings"]

    def test_that_corpus_migrates_rather_than_being_deleted(self, tmp_path: Path):
        """End to end on the exact fixture that exposed this."""
        root = tmp_path / "starter"
        (root / ".prawduct").mkdir(parents=True)
        (root / lf.LEGACY_REL).write_text(self.MINIMAL, encoding="utf-8")

        migration = lm.plan(root)
        assert not migration.refusals, migration.refusals
        assert migration.rules == 1
        lm.apply(root, migration)

        core = (root / lf.RULES_DIR_REL / lf.CORE_NAME).read_text(encoding="utf-8")
        assert "a standing rule" in core

    def test_a_flat_bullet_stays_a_bullet(self, tmp_path: Path):
        """Promoting it to a heading would silently edit someone's corpus, and
        would read as a topic title in a file where every heading means topic."""
        root = repo(tmp_path, "flat")
        lm.apply(root, lm.plan(root))
        core = (root / lf.RULES_DIR_REL / lf.CORE_NAME).read_text(encoding="utf-8")
        assert "- **A vacuous test is worse than no test.**" in core
        assert "### A stated cause is a hypothesis" in core

    def test_prose_under_a_flat_rule_travels_with_it(self, tmp_path: Path):
        root = repo(tmp_path, "flat")
        core = lm.plan(root).outputs[0].content
        assert "a second guess wearing a commit message" in core

    def test_only_the_title_and_its_paragraph_are_dropped(self, tmp_path: Path):
        root = repo(tmp_path, "flat")
        dropped = lm.plan(root).dropped
        assert "Learnings" in dropped
        assert any("Accumulated project wisdom" in d for d in dropped)
        assert not any(lm._RULE_SHAPED.match(d) for d in dropped)

    def test_the_dropped_preamble_is_named_to_the_operator(self, tmp_path: Path):
        """"What did it throw away" is the one question that cannot be answered
        after the deletion, so it is answered before it."""
        root = repo(tmp_path, "flat")
        proc = run_hook(root)
        assert proc.returncode == 0, proc.stderr
        assert "dropped 2 preamble line(s)" in proc.stdout
        assert "Accumulated project wisdom" in proc.stdout


class TestTheAccountingRunsInsideThePlan:
    """The losslessness contract, moved from the suite into the command.

    The suite asserts every rule survives — on fixtures. The corpus this
    command deletes is never a fixture, so the same contract runs in `plan()`
    and a shortfall is a refusal rather than a test failure nobody was there to
    see. Three checks, and each is exercised against a case the other two
    cannot see.
    """

    def test_a_writer_that_loses_a_rule_refuses(self, tmp_path: Path, monkeypatch):
        """Check (1): a rule parsed but not emitted. Simulated by an output
        builder that forgets a section — the class of bug a parser check is
        blind to."""
        root = repo(tmp_path, "mixed")
        real = lm._build_outputs

        def lossy(sections, mapping):
            outputs, unmapped, merges = real(sections[:-1], mapping)
            return outputs, unmapped, merges

        monkeypatch.setattr(lm, "_build_outputs", lossy)
        refusals = lm.plan(root).refusals
        assert any("do not appear in the planned output" in r for r in refusals)

    def test_a_parser_gap_refuses(self, tmp_path: Path, monkeypatch):
        """Check (2): a rule-shaped line carried into no output. A rule that was
        never parsed is not in `sections` for check (1) to miss."""
        root = repo(tmp_path, "mixed")
        real = lm.parse_legacy
        monkeypatch.setattr(
            lm, "parse_legacy",
            lambda text: (real(text)[0], ["- **A rule this parser did not know.**"]),
        )
        refusals = lm.plan(root).refusals
        assert any("look like rules were carried into no output" in r for r in refusals)

    def test_a_corpus_that_parses_to_nothing_refuses(self, tmp_path: Path):
        """Check (3): the catastrophic shape, in its own terms. Prose only —
        no bullets, no headings — so neither subtler check would fire."""
        root = tmp_path / "prose"
        (root / ".prawduct").mkdir(parents=True)
        (root / lf.LEGACY_REL).write_text(
            "Some notes we never got round to formatting.\n\nMore of them.\n",
            encoding="utf-8",
        )
        refusals = lm.plan(root).refusals
        assert any("parsed to zero rules" in r for r in refusals)

    def test_the_refusal_stops_the_deletion_end_to_end(self, tmp_path: Path):
        """The assertion that matters is on the corpus, not the exit code."""
        root = tmp_path / "prose"
        (root / ".prawduct").mkdir(parents=True)
        legacy = root / lf.LEGACY_REL
        legacy.write_text("Some notes.\n", encoding="utf-8")
        before = legacy.read_bytes()

        proc = run_hook(root, "--apply")

        assert proc.returncode == 1
        assert legacy.read_bytes() == before
        assert not (root / lf.RULES_DIR_REL).exists()

    @pytest.mark.parametrize("shape", SHAPES)
    def test_no_real_fixture_trips_the_accounting(self, tmp_path: Path, shape: str):
        """The guard's failure mode is over-refusal, which would stop every
        migration the command exists for."""
        root = repo(tmp_path, shape)
        assert not lm.plan(root, full_map(root)).refusals


class TestGitCannotAnswer:
    """"Could not ask" must not read as "nothing dirty".

    `dirty_legacy_files` returned `[]` on an OSError, a timeout, a held
    `index.lock` or a nonzero status, so one of the guards over an irreversible
    delete silently stopped applying on exactly the repos where something was
    already wrong.
    """

    def test_an_unanswerable_status_is_a_third_outcome(self, tmp_path: Path, monkeypatch):
        root = repo(tmp_path, "mixed")
        real = lm._git

        def refuse_status(project_dir, *args):
            if args[:1] == ("status",):
                return None
            return real(project_dir, *args)

        monkeypatch.setattr(lm, "_git", refuse_status)
        assert lm.dirty_legacy_files(root) is None

    def test_it_becomes_a_refusal_naming_git(self, tmp_path: Path, monkeypatch):
        root = repo(tmp_path, "mixed")
        real = lm._git

        def refuse_status(project_dir, *args):
            if args[:1] == ("status",):
                return None
            return real(project_dir, *args)

        monkeypatch.setattr(lm, "_git", refuse_status)
        refusals = lm.plan(root).refusals
        assert any("git could not report" in r for r in refusals)

    def test_a_nonzero_status_is_unanswerable_not_clean(
        self, tmp_path: Path, monkeypatch
    ):
        root = repo(tmp_path, "mixed")
        real = lm._git

        def failing_status(project_dir, *args):
            proc = real(project_dir, *args)
            if args[:1] == ("status",) and proc is not None:
                proc.returncode = 128
            return proc

        monkeypatch.setattr(lm, "_git", failing_status)
        assert lm.dirty_legacy_files(root) is None

    def test_no_repo_still_fails_open(self, tmp_path: Path):
        """The intended fail-open, kept distinct: with no repo there is no
        history for the deletion to be measured against and nothing to promise.
        """
        root = tmp_path / "nogit"
        shutil.copytree(FIXTURES / "topic", root)
        assert not lm.plan(root).refusals


class TestExitCodes:
    """`artifacts/api-contract.md` § Error Model, which the sibling repairs
    (`norm-index-scaffold`, `lifecycle-repair`) follow verbatim: 0 written or
    no-op, 1 refused, 2 usage error.

    This command returned 2 for both refusals and usage errors, so a caller —
    including the agent the briefing directive sends here — could not tell "fix
    your dirty tree" from "you typed the flag wrong".
    """

    def test_a_refusal_is_1(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        (root / lf.LEGACY_REL).write_text("# Learnings\n\n## T\n- **New.**\n")
        assert run_hook(root, "--apply").returncode == 1

    def test_a_usage_error_is_2(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        assert run_hook(root, "--zzz-unrecognised-token").returncode == 2
        assert run_hook(root, "--map").returncode == 2
        assert run_hook(root, "--propose-map", "--apply").returncode == 2

    def test_a_successful_run_and_a_no_op_are_both_0(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        assert run_hook(root, "--apply").returncode == 0
        assert run_hook(root).returncode == 0

    def test_the_two_are_distinguishable_which_is_the_whole_point(
        self, tmp_path: Path
    ):
        root = repo(tmp_path, "mixed")
        (root / lf.LEGACY_REL).write_text("# Learnings\n\n## T\n- **New.**\n")
        refused = run_hook(root, "--apply").returncode
        mistyped = run_hook(root, "--aply").returncode
        assert refused != mistyped



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

    def test_apply_json_reports_the_outcome_and_the_dropped_lines(self, tmp_path: Path):
        """The envelope is printed AFTER the apply, from its outcome, and carries
        `dropped` — the one question a --json caller could not otherwise ask."""
        root = repo(tmp_path, "mixed")
        map_file = tmp_path / "map.txt"
        map_file.write_text(run_hook(root, "--propose-map").stdout, encoding="utf-8")
        planned = lm.plan(root, lm.parse_map(map_file.read_text(encoding="utf-8")))

        proc = run_hook(root, "--apply", "--map", str(map_file), "--json")
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)  # exactly one JSON document on stdout
        assert payload["applied"] is True
        assert payload["dropped"] == list(planned.dropped)
        assert (root / lf.RULES_DIR_REL / lf.CORE_NAME).is_file()

    def test_an_interrupted_apply_with_json_never_claims_applied(self, tmp_path: Path):
        """An envelope emitted before the apply ran said `"applied": true` over
        a half-written tree. Now nothing on stdout says so."""
        root = repo(tmp_path, "mixed")
        map_file = tmp_path / "map.txt"
        map_file.write_text(run_hook(root, "--propose-map").stdout, encoding="utf-8")
        migration = lm.plan(root, lm.parse_map(map_file.read_text(encoding="utf-8")))
        (root / migration.outputs[1].rel).mkdir(parents=True)
        proc = run_hook(root, "--apply", "--map", str(map_file), "--json")
        assert proc.returncode == 1
        assert "INTERRUPTED" in proc.stderr
        assert '"applied": true' not in proc.stdout

    def test_the_dry_run_json_carries_dropped_and_applied_false(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        map_file = tmp_path / "map.txt"
        map_file.write_text(run_hook(root, "--propose-map").stdout, encoding="utf-8")
        proc = run_hook(root, "--map", str(map_file), "--json")
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        assert payload["applied"] is False
        assert "dropped" in payload
        assert not (root / lf.RULES_DIR_REL).exists()

    def test_a_refusal_exits_1_and_names_the_reason_on_stderr(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        (root / lf.LEGACY_REL).write_text("# Learnings\n\n## T\n- **New.**\n")
        proc = run_hook(root, "--apply")
        assert proc.returncode == 1
        assert "REFUSED" in proc.stderr
        assert (root / lf.LEGACY_REL).is_file()

    def test_a_gitignored_destination_refuses_the_apply(self, tmp_path: Path):
        root = repo(tmp_path, "mixed", commit=False)
        (root / ".gitignore").write_text(".claude/\n")
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "corpus")

        proc = run_hook(root, "--apply")

        assert proc.returncode == 1
        assert "gitignored" in proc.stderr
        assert (root / lf.LEGACY_REL).is_file()
        assert not (root / lf.RULES_DIR_REL).exists()

    def test_propose_map_and_apply_together_are_a_usage_error(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        proc = run_hook(root, "--propose-map", "--apply")
        assert proc.returncode == 2
        assert "Nothing ran" in proc.stderr
        assert (root / lf.LEGACY_REL).is_file()

    def test_map_without_a_value_is_a_usage_error(self, tmp_path: Path):
        root = repo(tmp_path, "mixed")
        proc = run_hook(root, "--map")
        assert proc.returncode == 2
        assert "--map needs a value" in proc.stderr

    def test_an_unreadable_map_file_is_a_usage_error_named_by_path(
        self, tmp_path: Path
    ):
        root = repo(tmp_path, "mixed")
        proc = run_hook(root, "--map", str(tmp_path / "absent.txt"))
        assert proc.returncode == 2
        assert "cannot read --map" in proc.stderr

    def test_a_malformed_map_file_is_a_usage_error_named_by_line(
        self, tmp_path: Path
    ):
        """A file the operator wrote and mistyped is bad input, not a refusal —
        exit 2, the same as an unknown flag."""
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


class TestBareBracketPointer:
    """`— [learnings-detail.md]` with no link target is a pointer too (prawduct's
    own corpus carried 67 of them); after migration it would name a deleted file."""

    def test_bare_bracket_pointer_is_stripped(self):
        src = "## When X do Y because Z — [learnings-detail.md]\n"
        assert lm.strip_links(src) == "## When X do Y because Z\n"

    def test_a_real_link_elsewhere_survives(self):
        src = "## When X do Y — see [the norm](docs/norms.md#x) — [learnings-detail.md]\n"
        assert lm.strip_links(src) == "## When X do Y — see [the norm](docs/norms.md#x)\n"
