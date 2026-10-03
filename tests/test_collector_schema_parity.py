"""The collector enforces the same allowlist the client builds against.

`plugin/lib/contribution_schema.json` is the one home of the allowlist. The
collector deploys separately, so it carries a copy (`collector/schema.json`),
and the worker embeds the same content. A change to the allowlist that misses
a copy would make the collector refuse reports the client sends, or accept
ones the client never could. This pins the copy to the plugin's file; the
collector's own suite (`collector/test/source.test.mjs`) pins the worker's
embedded object to the copy.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_SCHEMA = ROOT / "plugin" / "lib" / "contribution_schema.json"
COLLECTOR_SCHEMA = ROOT / "collector" / "schema.json"


def test_the_collector_copy_is_byte_identical():
    assert COLLECTOR_SCHEMA.read_bytes() == PLUGIN_SCHEMA.read_bytes()

