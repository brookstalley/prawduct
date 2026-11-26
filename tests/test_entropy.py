"""`lib/entropy.py` is the one owner of the randomness in prawduct's record ids, and the suite
replaces it with a seeded sequence.

A consumer's ids must stay unique across clones and worktrees writing one store, so production
draws real entropy. The suite cannot let a test read randomness and still have testament reuse
its result, and nearly every hook test mints an evidence fact, so conftest seeds the owner.
These tests pin both halves, that the seed reaches each way the code runs (in-process, the
in-process hook runner, and a scrubbed child), and that a randomness read cannot be added beside
the owner without saying why.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN = REPO_ROOT / "plugin"
sys.path.insert(0, str(PLUGIN))

from lib import determinism_lint, entropy, evidence  # noqa: E402
from conftest import (  # noqa: E402
    ENTROPY_SEED_ENV, TEST_ENTROPY_SEED, plugin_python_sources, scrubbed_env,
)
from _hook_inproc import run_hook  # noqa: E402

_HEX8 = re.compile(r"[0-9a-f]{8}")


@pytest.fixture
def no_urandom(monkeypatch):
    """Any read of OS entropy fails the test that asked for this."""
    def refuse(_n):
        raise AssertionError("os.urandom was read")

    monkeypatch.setattr(os, "urandom", refuse)


class TestTheProductionDefault:
    @pytest.mark.uncacheable("its subject is real entropy: unseeded, a token reads os.urandom")
    def test_unseeded_a_token_is_real_entropy_and_two_differ(self, monkeypatch):
        monkeypatch.delenv(entropy.SEED_ENV, raising=False)
        real = os.urandom
        drawn: list[int] = []

        def counting(n):
            drawn.append(n)
            return real(n)

        monkeypatch.setattr(os, "urandom", counting)
        first, second = entropy.token_hex(8), entropy.token_hex(8)
        assert drawn == [4, 4], "each token reads four bytes of OS entropy"
        assert _HEX8.fullmatch(first) and _HEX8.fullmatch(second)
        assert first != second

    @pytest.mark.parametrize("value", ["", "   ", "has space", "semi;colon", "x" * 65, "ünï"])
    def test_a_value_outside_the_seed_form_is_not_obeyed(self, monkeypatch, value):
        """The variable exists only for the suite, which always sets a well-formed seed;
        anything else is someone else's value, and ids keep real entropy."""
        monkeypatch.setenv(entropy.SEED_ENV, value)
        assert entropy.seed() is None

    def test_the_name_says_it_is_for_tests_only(self):
        assert entropy.SEED_ENV == "PRAWDUCT_TEST_ONLY_ENTROPY_SEED"

    def test_only_the_owner_reads_the_variable(self):
        """One owner: no other plugin file can seed, or read, randomness of its own."""
        readers = sorted(
            str(path.relative_to(REPO_ROOT))
            for path in PLUGIN.rglob("*")
            if path.is_file() and path.suffix in (".py", "")
            and entropy.SEED_ENV in path.read_text(encoding="utf-8", errors="replace")
        )
        assert readers == ["plugin/lib/entropy.py"]

    @pytest.mark.parametrize("chars", [0, 65])
    def test_a_token_length_outside_one_to_64_is_refused(self, chars):
        with pytest.raises(ValueError):
            entropy.token_hex(chars)


class TestTheSeededSequence:
    def test_a_seeded_token_reads_no_entropy_and_two_differ(self, monkeypatch, no_urandom):
        monkeypatch.setenv(entropy.SEED_ENV, "a-seed")
        tokens = [entropy.token_hex(8) for _ in range(50)]
        assert all(_HEX8.fullmatch(t) for t in tokens)
        assert len(set(tokens)) == 50

    def test_the_length_is_what_was_asked(self, monkeypatch):
        monkeypatch.setenv(entropy.SEED_ENV, "a-seed")
        assert [len(entropy.token_hex(n)) for n in (1, 7, 8, 64)] == [1, 7, 8, 64]

    def test_the_seed_and_the_pid_both_pick_the_sequence(self, monkeypatch):
        """Same seed, pid and draw count: the same token. Change any one and it moves. The pid is
        what keeps two processes' tokens apart, so it has to be in what is hashed."""
        def draw_at(seed: str, pid: int, count: int) -> str:
            monkeypatch.setenv(entropy.SEED_ENV, seed)
            monkeypatch.setattr(os, "getpid", lambda: pid)
            monkeypatch.setattr(entropy, "_drawn", count - 1)
            return entropy.token_hex(8)

        base = draw_at("a-seed", 1000, 5)
        assert draw_at("a-seed", 1000, 5) == base
        assert draw_at("b-seed", 1000, 5) != base
        assert draw_at("a-seed", 1001, 5) != base
        assert draw_at("a-seed", 1000, 6) != base

    @pytest.mark.uncacheable("its subject is two separate python3 processes sharing one seed")
    def test_two_processes_with_one_seed_draw_distinct_tokens(self, tmp_path):
        """Two hook children in one test mint ids at the same frozen second, so their tokens are
        all that keeps the ids apart, as two children's uuid4 tokens did."""
        script = (
            "import sys; sys.path.insert(0, sys.argv[1]);"
            " from lib import entropy; print(entropy.token_hex(8))"
        )
        env = scrubbed_env(tmp_path / "_home")
        assert env[entropy.SEED_ENV] == TEST_ENTROPY_SEED, "precondition: the children are seeded"
        tokens = [
            subprocess.run(
                [sys.executable, "-c", script, str(PLUGIN)],
                capture_output=True, text=True, check=True, env=env, timeout=60,
            ).stdout.strip()
            for _ in range(2)
        ]
        assert all(_HEX8.fullmatch(t) for t in tokens), tokens
        assert tokens[0] != tokens[1]


class TestTheSuiteSeedsIt:
    def test_conftest_names_the_owners_variable_and_sets_it(self):
        """conftest spells the name rather than importing the module (so it does not widen every
        test's import closure): the two spellings must agree, or the seed reaches nothing."""
        assert ENTROPY_SEED_ENV == entropy.SEED_ENV
        assert os.environ[entropy.SEED_ENV] == TEST_ENTROPY_SEED
        assert entropy.seed() == TEST_ENTROPY_SEED

    def test_a_scrubbed_child_is_seeded(self, tmp_path):
        assert scrubbed_env(tmp_path / "_home")[entropy.SEED_ENV] == TEST_ENTROPY_SEED

    def test_in_process_evidence_ids_read_no_entropy(self, tmp_path, no_urandom):
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        results = [evidence.append_session_start(repo) for _ in range(2)]
        assert [r["status"] for r in results] == ["appended", "appended"], results
        ids = [f["id"] for f in evidence.facts_of_kind(evidence.read_facts(repo), "session-start")]
        assert len(ids) == 2 and ids[0] != ids[1], ids

    def test_two_in_process_hook_calls_mint_distinct_ids(self, tmp_path, no_urandom):
        """The in-process runner leaves the draw count alone (`_hook_inproc.PROCESS_CONSTANTS`),
        so two session starts in one test are two facts, as they were from two children."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        (repo / ".prawduct").mkdir()
        env = {"CLAUDE_PROJECT_DIR": str(repo), "CLAUDE_PLUGIN_ROOT": str(PLUGIN)}
        for _ in range(2):
            proc = run_hook("clear", "--session-start", cwd=repo, env=env)
            assert proc.returncode == 0, proc.stderr
        ids = [f["id"] for f in evidence.facts_of_kind(evidence.read_facts(repo), "session-start")]
        assert len(ids) == 2 and ids[0] != ids[1], ids


# Each plugin file that still reads randomness directly, how many times, and why it does not draw
# through `lib.entropy`. A new read is either routed through the owner or added here with its
# reason, so "is this real entropy in the suite" is a decision someone made, not a default.
LEFT_ON_REAL_ENTROPY: dict[str, tuple[int, str]] = {}

#: The randomness APIs, from the product's own determinism lint, so the two lists cannot drift.
_ENTROPY_CALLS = frozenset(
    name for name in determinism_lint.AMBIENT_CALLS
    if name.split(".")[0] in ("uuid", "os", "random", "secrets")
) | {"random.Random"}


def _entropy_reads(source: str) -> int:
    """References to a randomness API in ``source``, called or passed uncalled (a
    ``default_factory=uuid.uuid4``), through any import spelling, at any depth. A seeded
    ``random.Random`` counts too: testament counts any draw from one, seeded or not."""
    tree = ast.parse(source)
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Name, ast.Attribute)):
            continue
        dotted = ast.unparse(node)
        head, _, rest = dotted.partition(".")
        resolved = aliases.get(head, head) + (f".{rest}" if rest else "")
        count += resolved in _ENTROPY_CALLS
    return count


def test_the_scan_sees_each_spelling():
    """The scan's own control: each import spelling it must catch, a seeded Random among them,
    and a randomness API passed uncalled; a name that only looks like one is not counted."""
    source = (
        "import uuid\nimport os as _os\nfrom secrets import token_hex\nimport random\n"
        "def f():\n    import uuid as u\n    return u.uuid4(), uuid.uuid4().hex[:8]\n"
        "a = _os.urandom(4)\nb = token_hex(4)\nc = random.Random()\nd = random.Random(7)\n"
        "e = random.choice([1])\n"
        "g = dataclasses.field(default_factory=uuid.uuid4)\n"
        "h = entropy.token_hex(4)\n"
    )
    assert _entropy_reads(source) == 8


def test_every_direct_randomness_read_is_accounted_for():
    found: dict[str, int] = {}
    for path in plugin_python_sources():
        rel = str(path.relative_to(REPO_ROOT))
        if rel == "plugin/lib/entropy.py":
            continue
        count = _entropy_reads(path.read_text(encoding="utf-8", errors="replace"))
        if count:
            found[rel] = count
    # The scan reads what it claims to: the owner's own real-entropy draw is the shape it hunts,
    # and the hook (extensionless) is in the set it walks.
    assert _entropy_reads((PLUGIN / "lib" / "entropy.py").read_text()) == 1
    assert PLUGIN / "bin" / "prawduct-hook" in plugin_python_sources()
    assert found == {path: count for path, (count, _why) in LEFT_ON_REAL_ENTROPY.items()}
