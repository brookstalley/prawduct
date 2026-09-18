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


def test_the_worked_producer_parses(contract):
    """The Python example is copied, not read. A snippet that does not parse
    fails in the consumer's repo, where nothing of ours is watching."""
    blocks = _fenced_blocks(contract, "python")
    assert len(blocks) == 1, "expected exactly one Python producer example"
    ast.parse(blocks[0])


def test_the_builders_guide_points_here(contract):
    """`building.md` is the surface a builder actually opens; the contract is
    on-demand. If the pointer goes, the contract is unreachable in practice
    however correct it is."""
    building = (PLUGIN / "methodology" / "building.md").read_text()
    assert CONTRACT_REL in building, (
        "methodology/building.md no longer points at the test-report contract"
    )
