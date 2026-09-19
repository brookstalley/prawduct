"""The test-report contract doc is implementable by someone who only has it.

`plugin/docs/test-report-contract.md` is the one home for the scope record's
schema, the reader's rules and the conventional paths (`docs/norms.md` — every
fact has one home). Its reader is a *producer author* in an ecosystem prawduct
has never seen: a .NET assembly fixture, a Go `TestMain`, a Jest `globalSetup`.
That reader has the doc and nothing else, so the checks here ask what they can
answer from it alone rather than measuring the file.

What turns these red: an example that drifts from the field table (the two are
pinned against *each other*, so neither can be quietly edited), a required field
losing its `yes`, the permissive and refusing directions collapsing into one, a
Python example that stops parsing, and `building.md` losing the pointer that is
how a builder finds any of it.
"""

from __future__ import annotations

import ast
import json
import re
import textwrap
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parent.parent / "plugin"
CONTRACT_REL = "docs/test-report-contract.md"


@pytest.fixture(scope="module")
def contract() -> str:
    return (PLUGIN / CONTRACT_REL).read_text()


def _fenced_blocks(text: str, lang: str) -> list[str]:
    return re.findall(rf"^```{lang}\n(.*?)^```", text, re.S | re.M)


def _table_rows(text: str, header_first_cell: str) -> list[list[str]]:
    """Rows of the first markdown table whose header starts with that cell.

    Returns each row as its stripped cells, so a check reads the table the way
    a person does rather than pattern-matching prose around it.
    """
    rows: list[list[str]] = []
    in_table = False
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else None
        if cells is None:
            if in_table:
                break
            continue
        if not in_table:
            if cells[0] == header_first_cell:
                in_table = True
            continue
        if set("".join(cells)) <= set("-: "):
            continue  # the header separator
        rows.append(cells)
    return rows


def _schema_fields(contract: str) -> dict[str, str]:
    """`{field: required-column}` from the scope record's field table."""
    rows = _table_rows(contract, "Field")
    assert rows, "the contract has no `| Field |` table"
    return {row[0].strip("`"): row[1].lower() for row in rows}


def test_the_example_record_and_the_field_table_agree(contract):
    """The example is what a producer author copies; the table is what they
    check it against. Pinning them to each other means a field cannot be added
    to one surface alone — which is how a schema doc goes subtly wrong."""
    blocks = _fenced_blocks(contract, "json")
    assert len(blocks) == 1, "expected exactly one JSON example (the scope record)"
    example = json.loads(blocks[0])
    fields = _schema_fields(contract)

    assert set(example) <= set(fields), (
        f"the example carries {sorted(set(example) - set(fields))}, which the "
        "field table does not describe"
    )
    required = {name for name, req in fields.items() if req == "yes"}
    assert required <= set(example), (
        f"the example omits required field(s) {sorted(required - set(example))}"
    )
    assert example["v"] == 1, "the example must carry the version this reader knows"


def test_every_field_names_who_reads_it(contract):
    """A field with no reader is one nobody can implement against, and the
    planning guide's rule for a persisted format is that each one answers a
    consumer query. The table's third column is where that answer lives."""
    rows = _table_rows(contract, "Field")
    for row in rows:
        assert len(row) == 3, f"field row {row!r} is missing its reader column"
        assert len(row[2].split()) >= 5, (
            f"field `{row[0]}` has no stated reader — {row[2]!r}"
        )
    # What this does NOT catch: a plausible-sounding sentence that names no
    # actual consumer. The check is a length proxy, red-verified against a
    # reader cell cut to "Optional."; judging whether a stated reader is real
    # is the Critic's, not a test's.


def test_both_verdict_values_are_specified(contract):
    """`full` and `partial` are the whole vocabulary; a producer that learns
    only one of them cannot write a correct record."""
    fields = _schema_fields(contract)
    scope_row = next(row for row in _table_rows(contract, "Field") if row[0].strip("`") == "scope")
    described = scope_row[2]
    for value in ("full", "partial"):
        assert re.search(rf"`\"?{value}\"?`", described), (
            f"the `scope` row does not document the value {value!r}: {described!r}"
        )
    assert fields["scope"] == "yes"


def test_the_readers_rules_keep_both_directions(contract):
    """The permissive default and the refusal are one table, and a check that
    only asserts the refusal would pass a doc that had quietly dropped the
    'absent changes nothing' guarantee every un-wired repo depends on."""
    rows = _table_rows(contract, "Condition")
    assert rows, "the contract has no `| Condition |` table of the reader's rules"
    verdicts = [row[1] for row in rows]
    proceeds = [v for v in verdicts if "Proceed" in v]
    refusals = [v for v in verdicts if "Refuse" in v]
    assert proceeds and refusals, f"one direction is missing: {verdicts!r}"

    absent = next(row for row in rows if "No record" in row[0])
    assert "Proceed" in absent[1], "an absent record must not refuse"
    partial = next(row for row in rows if '`scope: "partial"`' in row[0])
    assert "Refuse" in partial[1], "a partial record must refuse"


def test_every_python_snippet_parses(contract):
    """The Python examples are copied, not read. A snippet that does not parse
    fails in the consumer's repo, where nothing of ours is watching.

    EVERY block, not the first: the doc grew a second one (the two lines that
    anchor a relative report path) and a check bounded to one block would have
    stopped looking exactly where the new content is. Fragments are dedented
    before parsing, because an indented insert is a legitimate shape for
    "add this inside that function"."""
    blocks = _fenced_blocks(contract, "python")
    assert blocks, "the contract has no Python producer example at all"
    for i, block in enumerate(blocks):
        try:
            ast.parse(textwrap.dedent(block))
        except SyntaxError as exc:
            raise AssertionError(f"python block {i} in the contract does not parse: {exc}") from exc


def test_the_builders_guide_points_here(contract):
    """`building.md` is the surface a builder actually opens; the contract is
    on-demand. If the pointer goes, the contract is unreachable in practice
    however correct it is."""
    building = (PLUGIN / "methodology" / "building.md").read_text()
    assert CONTRACT_REL in building, (
        "methodology/building.md no longer points at the test-report contract"
    )


# =============================================================================
# The shipped example against the real producer
# =============================================================================


def _doc_classifier_source(contract: str) -> str:
    """The doc's `classify` + `_selection_is_the_default`, as source."""
    for block in _fenced_blocks(contract, "python"):
        if "def classify(" in block and "_selection_is_the_default" in block:
            return block
    raise AssertionError(
        "the contract's worked producer no longer defines both `classify` and "
        "`_selection_is_the_default` in one block — this pin cannot find its subject"
    )


class TestTheShippedExampleMatchesTheRealProducer:
    """A consumer copies the DOC, not `tests/conftest.py`.

    The example was hand-written from the real producer and nothing compared the
    two, so every correction made to `conftest.py` during this branch's own
    review left the copy consumers take still wrong. That is the class, and it
    is what these tests close — not the one bug that exposed it.

    The bug it exposed is worth naming because it is invisible by reading: the
    example compared `list(config.args)` against absolute `testpaths`, and
    pytest sets `config.args` to the RELATIVE results of its own glob expansion
    (`_pytest/config/__init__.py::_decide_args`). So a bare `pytest` compared
    `["tests"]` with `["/abs/root/tests"]`, classified every whole-suite run
    `partial`, and made `--from-junit` refuse for every consumer who copied it —
    the cheapest escape being to delete the record, which is the one lever this
    same doc forbids.

    What turns these red, verified by mutation rather than claimed: reverting
    `classify`'s call to the string comparison that shipped (2 of 11 red).

    What they do NOT discriminate, stated so the docstring does not imply
    coverage it lacks: resolving only one side of the comparison survives,
    because both sides here are absolute and already normalised — that is
    unreachability, not a gap, and `.resolve()` earns its place on the RELATIVE
    side, which these fixtures do exercise. A comment reword also survives,
    which is the control proving the pin is not matching incidental text.
    """

    def _classifiers(self, contract: str):
        """The doc's `classify` and this repo's, both ready to call.

        Entered at `classify`, NOT at the selection predicate. A first cut
        called `_selection_is_the_default` directly and both real mutants
        survived: reverting `classify`'s CALL to a string comparison never
        enters the predicate, so the test could not see the defect it was
        written for. Pin the call, not the arithmetic.
        """
        import tests.conftest as real

        ns: dict = {}
        exec(  # noqa: S102 — executing the doc's own snippet is the point
            "import json, os, sys, tempfile\nfrom pathlib import Path\n"
            + _doc_classifier_source(contract),
            ns,
        )
        return ns["classify"], real.classify_invocation

    #: The SAME matrix `TestTheClassifier` runs over the real producer, not a
    #: hand-picked subset. A first cut picked four selection cases by hand and
    #: was blind to `--ignore-glob`: neither `_Option` carried the attribute, so
    #: both classifiers fell through `getattr(..., None)` and AGREED — a test
    #: that passes because neither side was asked. Driving the real matrix is
    #: what makes "the two agree" mean something, and it is what the finding
    #: asked for.
    NARROWING_OPTIONS = [
        ({"keyword": "billing"}, "-k"),
        ({"markexpr": "smoke"}, "-m"),
        ({"deselect": ["tests/test_a.py::test_b"]}, "--deselect"),
        ({"ignore": ["tests/slow"]}, "--ignore"),
        ({"ignore_glob": ["tests/slow*"]}, "--ignore"),
        ({"lf": True}, "--lf"),
        ({"stepwise": True}, "--lf"),
        ({"collectonly": True}, "--collect-only"),
        ({"maxfail": 1}, "--maxfail"),
    ]

    def _config(self, *, args=("tests",), testpaths=("tests",), **opts):
        class _Option:
            def __init__(self):
                self.keyword = ""
                self.markexpr = ""
                self.deselect = None
                self.ignore = None
                self.ignore_glob = None
                self.lf = False
                self.stepwise = False
                self.failedfirst = False
                self.collectonly = False
                self.maxfail = 0
                for k, v in opts.items():
                    setattr(self, k, v)

        class _Params:
            dir = "/repo"

        class _Config:
            def __init__(self):
                self.args = list(args)
                self.rootpath = Path("/repo")
                self.invocation_params = _Params()
                self.option = _Option()

            def getini(self, name):
                assert name == "testpaths"
                return list(testpaths)

        return _Config

    def _agree(self, contract, make_config, exitstatus=0):
        doc_classify, real_classify = self._classifiers(contract)
        doc = doc_classify(make_config(), exitstatus)[0]
        real = real_classify(make_config(), exitstatus)[0]
        return doc, real

    @pytest.mark.parametrize("opts,_token", NARROWING_OPTIONS)
    def test_every_narrowing_option_is_partial_in_both(self, contract, opts, _token):
        """`--ignore-glob` is the case that shipped wrong and that the first
        version of this test could not see. A consumer copying the doc and
        running `pytest --ignore-glob=...` recorded `full` for a narrowed run —
        a FALSE GREEN, the inverse of the bug that prompted the review."""
        doc, real = self._agree(contract, self._config(**opts))
        assert doc == real == "partial", (
            f"options {opts!r}: doc says {doc!r}, real says {real!r} — both must "
            "read a narrowed invocation as partial"
        )

    @pytest.mark.parametrize("args,expected", [
        (("tests",), "full"),
        (("tests/",), "full"),
        (("tests/test_a.py",), "partial"),
        (("tests/test_a.py::test_b",), "partial"),
        (("tests", "extra"), "partial"),
        ((), "partial"),
    ])
    def test_selection_cases_agree_and_are_right(self, contract, args, expected):
        doc, real = self._agree(contract, self._config(args=args))
        assert doc == real, f"args={args!r}: doc {doc!r} vs real {real!r}"
        # Pinned against the REQUIREMENT too — "make A agree with B" is also
        # satisfied by teaching A the defects of B.
        assert doc == expected, f"args={args!r}: both say {doc!r}, expected {expected!r}"

    @pytest.mark.parametrize("exitstatus", [2, 3, 4, 5])
    def test_an_incomplete_exit_status_is_partial_in_both(self, contract, exitstatus):
        doc, real = self._agree(contract, self._config(), exitstatus=exitstatus)
        assert doc == real == "partial"

    def test_failed_first_alone_is_not_narrowing_in_either(self, contract):
        """`--ff` reorders without reducing. Pinned because the obvious
        grouping ("the last-failed family") would wrongly refuse it."""
        doc, real = self._agree(contract, self._config(failedfirst=True))
        assert doc == real == "full"

    def test_the_example_guards_its_write_for_every_hook(self, contract):
        """R-1's second member, and the one a fix closed at one site.

        The guard belongs INSIDE `_write`, where one guard covers every hook
        that writes — `pytest_configure` AND `pytest_sessionfinish`. Guarding
        one call site leaves the other able to raise out of a hook, which this
        same document forbids, and it must SAY so on stderr: the doc's own
        "What a producer owes" requires it, because an advisory that fails
        silently manufactures the confidence it exists to check.
        """
        writer = [b for b in _fenced_blocks(contract, "python") if "def _write(" in b]
        assert writer, "the contract no longer ships a worked `_write`"
        body = writer[0]
        assert "except OSError" in body, (
            "the example's `_write` can raise out of a pytest hook — a producer "
            "that cannot write its record must not take the suite down with it"
        )
        assert "file=sys.stderr" in body, (
            "the example's write failure does not reach stderr, which this "
            "document's own 'What a producer owes' section forbids. Asserted as "
            "`file=sys.stderr` rather than the word 'stderr': the block's own "
            "comment says 'Say so on stderr', so a bare substring passes while "
            "the code prints to stdout — verified by mutation."
        )

    def test_the_doc_resolves_rather_than_comparing_strings(self, contract):
        """The property, not one spelling of it.

        A string comparison is the defect; asserting the absence of one exact
        line would pass for every other way of writing the same mistake.
        """
        src = _doc_classifier_source(contract)
        assert ".resolve()" in src, (
            "the contract's selection test no longer resolves its paths — pytest "
            "hands back relative args, so an unresolved comparison calls every "
            "whole-suite run `partial`"
        )
