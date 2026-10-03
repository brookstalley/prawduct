"""Regenerate the collector's Python-parity fixtures from the real client.

Run from the repository root:  python3 collector/test/fixtures/generate.py

- python-step-values.json: every value contribution.to_step can emit for one
  field of each distinct (step, min, max), as json.dumps writes it.
- python-verdicts.json: raw request bodies, each with Python's verdict
  (json.loads, then contribution.validate) and, when it passes, the bytes the
  client would have sent for it: canonical_bytes after to_step, which is the
  form the collector stores.

Writes only the two JSON files beside this script.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "plugin"))
from lib import contribution as c  # noqa: E402

SCHEMA = c.load_schema()
FIELDS = SCHEMA["fields"]


def step_values():
    seen, out = set(), {}
    for name, spec in FIELDS.items():
        if spec["type"] != "number":
            continue
        key = (spec["step"], spec["min"], spec["max"])
        if key in seen:
            continue
        seen.add(key)
        n = round((spec["max"] - spec["min"]) / spec["step"])
        out[name] = [json.dumps(c.to_step(spec["min"] + k * spec["step"], spec)) for k in range(n + 1)]
    return out


BASE = '{"schema":1,"iso_year":2026,"iso_week":39,"plugin_major":3,"plugin_minor":7,"dev":false,"sessions":"10-49","scopes":"1-9","reviews":"10-49"'


def with_field(raw):
    return BASE + "," + raw + "}"


BODIES = [
    BASE + "}",
    BASE.replace('"iso_week":39', '"iso_week":39.0') + "}",
    BASE.replace('"iso_week":39', '"iso_week":3.9e1') + "}",
    BASE.replace('"iso_week":39', '"iso_week":-0') + "}",
    BASE.replace('"iso_week":39', '"iso_week":53') + "}",
    BASE.replace('"iso_week":39', '"iso_week":54') + "}",
    BASE.replace('"iso_week":39', '"iso_week":true') + "}",
    BASE.replace('"dev":false', '"dev":0') + "}",
    BASE.replace('"dev":false', '"dev":1') + "}",
    BASE.replace('"dev":false', '"dev":true') + "}",
    BASE.replace('"sessions":"10-49"', '"sessions":"1\\u002d9"') + "}",
    BASE.replace('"sessions":"10-49"', '"sessions":"1-9 "') + "}",
    BASE.replace('"iso_week":39', '"iso_week":12,"iso_week":39') + "}",
    BASE.replace('"iso_week":39', '"iso_week":39,"iso_week":"x"') + "}",
    BASE.replace('"schema":1,', "") + "}",
    with_field('"surprise":1'),
    with_field('"blocking_per_review":0.30000000000000004'),
    with_field('"blocking_per_review":0.3'),
    with_field('"blocking_per_review":3.0'),
    with_field('"blocking_per_review":3'),
    with_field('"blocking_per_review":30e-1'),
    with_field('"blocking_per_review":1e-8'),
    with_field('"blocking_per_review":1e-6'),
    with_field('"blocking_per_review":0.35'),
    with_field('"blocking_per_review":100.0'),
    with_field('"blocking_per_review":100.1'),
    with_field('"blocking_per_review":-0.0'),
    with_field('"blocking_per_review":null'),
    with_field('"red_test_run_share":0.35'),
    with_field('"red_test_run_share":0.35000000001'),
    with_field('"red_test_run_share":0.3500001'),
    with_field('"red_test_run_share":0.375'),
    with_field('"red_test_run_share":1'),
    with_field('"red_test_run_share":1.0000000001'),
    with_field('"rounds_per_scope_p90":2.25'),
    with_field('"rounds_per_scope_p90":2.5'),
    with_field('"review_minutes_per_scope_median":6000'),
    with_field('"review_minutes_per_scope_median":5999.5'),
    with_field('"review_minutes_per_scope_median":1e400'),
    "[]",
    '"a report"',
    "null",
]


def verdict(body):
    try:
        report = json.loads(body)
    except ValueError:
        return {"body": body, "accepted": False}
    problems = c.validate(report, SCHEMA)
    if problems:
        return {"body": body, "accepted": False}
    client = {
        k: (c.to_step(v, FIELDS[k]) if FIELDS[k]["type"] == "number" else v) for k, v in report.items()
    }
    assert c.validate(client, SCHEMA) == []
    return {"body": body, "accepted": True, "stored": c.canonical_bytes(client).decode("ascii")}


def write(name, about, payload):
    doc = {"about": about, **payload}
    (HERE / name).write_text(json.dumps(doc, indent=0) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write(
        "python-step-values.json",
        "Every value contribution.to_step can emit for one field of each distinct (step, min, max), "
        "as Python json.dumps writes it. Regenerate: python3 collector/test/fixtures/generate.py",
        {"values": step_values()},
    )
    write(
        "python-verdicts.json",
        "Raw bodies with Python's verdict (json.loads, then contribution.validate) and, when accepted, "
        "the client-form canonical bytes. Regenerate: python3 collector/test/fixtures/generate.py",
        {"cases": [verdict(b) for b in BODIES]},
    )
