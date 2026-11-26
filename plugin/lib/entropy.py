"""The one owner of the randomness that mints prawduct's record ids.

An evidence fact's id (``session-start-<stamp>-<token>``, a stop block's, a
test run's, a guard refusal's, a chunk import's or retraction's) and a Critic
review's id end in a short random token drawn through :func:`token_hex`. The
token is what keeps two ids minted in the same second distinct, in one process
and across every clone and worktree that writes the same store, so in a
consumer's repository it is real entropy (``os.urandom``), as ``uuid4`` was.
Every direct randomness read left in the plugin is listed with its reason in
``tests/test_entropy.py``.

:data:`SEED_ENV` replaces it for the test suite, the way ``lib.clock``'s
``FROZEN_ENV`` replaces the wall clock: unmistakably a test fixture by name, an
environment variable so it reaches a hook child unasked, and a value outside
its form (:data:`_SEED_FORM`) is ignored rather than trusted. Seeded, a token
is the SHA-256 of the seed, this process's pid and a per-process draw count:
no entropy is read, so a test runner that refuses to reuse a result which read
randomness (testament) can reuse it, and the two promises an id needs still
hold. Two draws in one process differ because the count moves, and two
processes' draws differ because their pids do, as two children's ``uuid4``
tokens did. The count is never reset for the life of the process: a test that
runs the hook in-process twice gets distinct tokens, as two children did.

Stdlib only, no relative imports: ``bin/prawduct-hook`` imports it from its own
plugin tree.
"""

from __future__ import annotations

import hashlib
import os
import re

#: The environment variable that replaces real entropy with a seeded sequence. Test-only by name.
SEED_ENV = "PRAWDUCT_TEST_ONLY_ENTROPY_SEED"

#: What a seed the suite sets looks like. Anything else is someone else's value and is not obeyed.
_SEED_FORM = re.compile(r"[A-Za-z0-9._-]{1,64}")

#: Draws made from the seeded sequence in this process. Only a seeded draw moves it.
_drawn = 0


def seed() -> "str | None":
    """The seed :data:`SEED_ENV` holds, or ``None`` when ids draw real entropy."""
    value = os.environ.get(SEED_ENV, "").strip()
    return value if _SEED_FORM.fullmatch(value) else None


def token_hex(chars: int = 8) -> str:
    """``chars`` lowercase hex characters (1 to 64) for the random part of an id.

    Real entropy unless :data:`SEED_ENV` is set; then the next token of the
    seeded sequence, which reads none."""
    if not 1 <= chars <= 64:
        raise ValueError(f"a token is 1 to 64 hex characters, not {chars}")
    seeded = seed()
    if seeded is None:
        return os.urandom((chars + 1) // 2).hex()[:chars]
    global _drawn
    _drawn += 1
    material = f"{seeded}\0{os.getpid()}\0{_drawn}".encode("utf-8", "surrogateescape")
    return hashlib.sha256(material).hexdigest()[:chars]
