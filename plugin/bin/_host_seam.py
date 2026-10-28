"""Load the host seam, ``lib/host.py``, by file path: the one loader that the hook
script, the session banner and the digest share.

The seam is what says where ``lib`` is, so it loads before ``sys.path`` is seeded,
and a broken module elsewhere in ``lib`` cannot stop it loading; it imports nothing
from ``lib``. It is cached in ``sys.modules`` under one name, so every entry point
in a process gets the same instance. There is no fallback when it fails to load: a
plugin tree without its seam is not a plugin, and reading host variables outside
the seam is what the seam exists to prevent.
"""

import importlib.util
import sys
from pathlib import Path

MODULE_NAME = "prawduct_host"


def load():
    """The host seam module, loaded on first call and cached after."""
    module = sys.modules.get(MODULE_NAME)
    if module is None:
        path = Path(__file__).resolve().parent.parent / "lib" / "host.py"
        spec = importlib.util.spec_from_file_location(MODULE_NAME, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[MODULE_NAME] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            # A half-built module must not be what the next caller gets.
            del sys.modules[MODULE_NAME]
            raise
    return module
