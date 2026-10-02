"""Memoization of the composed coverage verdict.

``coverage_algebra.coverage_verdict`` is a pure function, and an expensive one:
its free-edge search keys every tree the store mentions. Keying costs one
``git ls-tree`` per tree the clone has not keyed before; :mod:`tree_key_memo`
keeps the rest. Before that memo, measured on this repo (2,715 facts, 701
distinct trees), a cold verdict cost 17.4 s, and 0.01 s with the keys already
in hand. The store is append-only and shared by every worktree of the clone,
so the cold cost grew monotonically and was paid again by every gate call.
Nine invocations in one consumer session ran 29–120 s each, two of them
hitting the 2-minute Bash ceiling, and the agent resorted to `timeout 200`.

**This is a memo, not a second home for any fact** (``data-model.md``: *derived
views are disposable and never authoritative — no gate reads a view to reach a
verdict*). The distinction is the key: it covers EVERY input the verdict is a
function of — the two endpoint trees and a content hash of the evidence store
(``coverage_fingerprint``: every line but the observational kinds the verdict
never reads, :data:`evidence.OBSERVATIONAL_KINDS`) — so a hit replays a
computation whose inputs are provably unchanged rather than substituting for
one. A miss, an unreadable cache, a corrupt entry,
or an unreadable store all recompute. There is no path on which the cache
decides something the store would not.

**Why a cached verdict can never be a false PASS.** Git objects are immutable
and content-addressed, so they are not in the key — and they do not need to be.
``coverage_verdict`` grants ``covered`` only through review edges (derived from
facts, which ARE in the key) and free edges (tree-key equality). A missing
object or a git failure makes ``key_fn`` return ``None``, which denies a free
edge; it can never manufacture one. So git-side degradation moves the verdict
only toward denial, and a verdict recorded under it can only be replayed as a
denial. The residual, stated: an ``uncovered`` computed while an object was
transiently unreadable is replayed until the store's next append of any kind
outside :data:`evidence.OBSERVATIONAL_KINDS` (so not a test-run or a guard
firing) changes the fingerprint. That is a false negative — the safe direction,
and the one this subsystem's authority contract requires.

The cache lives beside the evidence store, in the per-clone gitignored area
(``two stores, two lifetimes``) — never in committed state.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from . import coverage_algebra, evidence
from .core import atomic_write_text

CACHE_BASENAME = "verdict-cache.json"

#: Bumped whenever the verdict SHAPE changes, so entries written by an older
#: reading of the same inputs cannot be replayed against a newer consumer. The
#: fingerprint covers the inputs; this covers the function.
CACHE_SCHEMA = 2

#: Entries kept, newest first. A gate call touches a handful of keys (the span,
#: plus each diagnosis's), and a branch's keys all die on the next store append,
#: so this only has to outlive one session's polling — not accumulate history.
MAX_ENTRIES = 64


def cache_path(project_dir: Path) -> "Path | None":
    """The cache file beside the evidence store, or ``None`` when the store has
    no home (outside a git repo). No fallback location, for the same reason
    :func:`evidence.store_path` has none."""
    store = evidence.store_path(project_dir)
    return None if store is None else store.parent / CACHE_BASENAME


#: Memoised per process. The docstring above advertises a 0.01 s warm cost, and
#: :func:`_key` runs once per gate call — a `git rev-parse` per lookup would
#: spend the saving this module exists to create.
#: ``None`` until computed. The computed value may legitimately be ``""`` (not
#: a checkout, or git could not answer), which is why the sentinel is ``None``
#: and not falsiness — otherwise the degraded case would re-probe git on every
#: single lookup, which is the cost this memo exists to avoid.
_CODE_IDENTITY: "str | None" = None


def _code_identity() -> str:
    """What identifies the CODE that computed a verdict, beyond its version.

    :func:`_key` folds in the plugin version because the cache outlives the
    plugin and the verdict depends on ``coverage_algebra.is_judgeable_path``.
    That is sufficient for an installed copy, where the version string moves
    whenever the code does. It is **not** sufficient when prawduct runs from a
    git checkout — developing prawduct itself — because the bundled ``VERSION``
    does not change between pushes to ``develop``. Two different develop states
    then produce the same key by construction, and a verdict computed under the
    older one is served as current. That is exactly what ``_key``'s own
    docstring says the key must prevent: it covers "every input the verdict is a
    function of — including the CODE that computed it."

    **Tree, not commit.** ``data-model.md``'s Direction is that facts are keyed
    by git *tree* SHA, and it is load-bearing here rather than stylistic: two
    develop commits that produce an identical plugin tree ARE the same code, and
    commit-keying would miss the cache on every no-op commit — a rebase, a
    merge, an empty commit, or any commit touching only files outside the plugin
    directory. Tree-keying invalidates when the code changes and only then.

    A dirty checkout adds a fingerprint of what is uncommitted, because an
    edited working tree is a third state that neither the version nor the
    committed tree can distinguish.

    Degrades to the empty string when this is not a checkout, or when git cannot
    answer. That is the correct direction and is safe for the same reason the
    module docstring gives for git-side degradation generally: a constant
    component makes the key *coarser*, so entries collide and are replayed — and
    replay can only ever reproduce a verdict the store's own fingerprint already
    vouches for. It cannot manufacture a pass.
    """
    global _CODE_IDENTITY
    if _CODE_IDENTITY is None:
        _CODE_IDENTITY = probe_code_identity(Path(__file__).resolve().parent.parent)
    return _CODE_IDENTITY


def probe_code_identity(plugin_dir: Path) -> str:
    """The uncached probe :func:`_code_identity` memoises.

    Split out so the behaviour can be exercised against real git repositories
    rather than by monkeypatching a module global — the memo would otherwise
    make every test after the first one assert against a cached answer, which
    is the shape that passes while measuring nothing.
    """
    parts: list[str] = []
    try:
        # `HEAD:./` — the tree of THIS directory, not `HEAD^{tree}`, which
        # resolves to the commit's ROOT tree no matter what cwd is. Both halves
        # of this function's contract depend on the difference:
        #
        # - Scoping. With the root tree, a commit touching only `tests/`,
        #   `documentation/` or `.prawduct/` moves the key and invalidates every
        #   cached verdict, which is the churn tree-keying exists to avoid.
        # - Degradation. An installed copy can sit INSIDE an unrelated checkout
        #   (a `~/.claude` tracked in a dotfiles repo). `HEAD^{tree}` succeeds
        #   there and returns that repo's tree, so those users would get a key
        #   churning on every unrelated commit. `HEAD:./` exits 128 for a
        #   directory the repo does not track, so the identity degrades to `""`
        #   and they key exactly as they did before this existed.
        tree = subprocess.run(
            ["git", "rev-parse", "HEAD:./"],
            cwd=plugin_dir, capture_output=True, text=True, timeout=10,
        )
        if tree.returncode == 0 and tree.stdout.strip():
            parts.append(tree.stdout.strip())
            dirty = subprocess.run(
                ["git", "status", "--porcelain", "-z", "--untracked-files=all",
                 "--", str(plugin_dir)],
                cwd=plugin_dir, capture_output=True, text=True, timeout=10,
            )
            if dirty.returncode == 0 and dirty.stdout.strip("\0"):
                parts.append(_dirty_content_digest(plugin_dir, dirty.stdout))
    except (OSError, subprocess.SubprocessError):
        return ""
    return "\0".join(parts)


def _dirty_content_digest(plugin_dir: Path, porcelain_z: str) -> str:
    """A digest of what is uncommitted: each dirty path AND its bytes.

    The status line alone names which files changed, not how, so a second edit
    to a file already modified would keep the identity and replay answers the
    first edit's code computed. Porcelain paths are relative to the repository
    root, so they are resolved against it; a path that cannot be read (deleted,
    a directory) contributes its name and status only, which still moves the
    digest whenever the set of such paths does.
    """
    top = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=plugin_dir, capture_output=True, text=True, timeout=10,
    )
    root = Path(top.stdout.strip()) if top.returncode == 0 else plugin_dir
    digest = hashlib.sha256()
    records = porcelain_z.split("\0")
    i = 0
    while i < len(records):
        record = records[i]
        i += 1
        if len(record) < 4:
            continue
        digest.update(record.encode("utf-8", "surrogateescape") + b"\0")
        # A rename or copy carries its source as the next, unprefixed record.
        if record[0] in "RC" and i < len(records):
            digest.update(records[i].encode("utf-8", "surrogateescape") + b"\0")
            i += 1
        try:
            digest.update((root / record[3:]).read_bytes())
        except OSError:
            pass
        digest.update(b"\0")
    return digest.hexdigest()[:16]


#: The modules whose code decides what a memoised answer MEANS: which paths
#: are judgeable (``coverage_algebra.is_judgeable_path``, reading
#: ``gitstate.METADATA_PREFIXES`` and ``buildplan_refs``' protected paths),
#: how a tree is keyed (``tree_key_memo``), and how keys and facts compose
#: into a verdict (``coverage_algebra``). Their bytes are part of the identity, because an
#: installed copy's only other component is the version string, and the dev
#: track keeps one version across several merges.
_IDENTITY_MODULES = (
    "coverage_algebra.py", "gitstate.py", "buildplan_refs.py", "tree_key_memo.py",
)

_MODULE_DIGEST: "str | None" = None


def module_digest(lib_dir: Path) -> str:
    """Digest of :data:`_IDENTITY_MODULES`' bytes under ``lib_dir``."""
    digest = hashlib.sha256()
    for name in _IDENTITY_MODULES:
        digest.update(name.encode() + b"\0")
        try:
            digest.update((lib_dir / name).read_bytes())
        except OSError:
            digest.update(b"<unreadable>")
        digest.update(b"\0")
    return digest.hexdigest()


def _module_digest() -> str:
    """:func:`module_digest` of this plugin's own modules, once per process."""
    global _MODULE_DIGEST
    if _MODULE_DIGEST is None:
        _MODULE_DIGEST = module_digest(Path(__file__).resolve().parent)
    return _MODULE_DIGEST


def code_identity() -> str:
    """What identifies the code behind any memoised coverage answer: the
    plugin version, the checkout's plugin tree and uncommitted content
    (:func:`_code_identity`), and the bytes of the modules that define
    judgeability and keying (:func:`_module_digest`). The one composition both
    per-clone memos key on (this module's verdicts and
    :mod:`tree_key_memo`'s tree keys), so an input added here reaches both."""
    return hashlib.sha256(
        "\0".join((
            evidence._plugin_version() or "unversioned",
            _code_identity(),
            _module_digest(),
        )).encode()
    ).hexdigest()


def read_memo_entries(path: Path, schema: int) -> dict:
    """A per-clone memo file's ``entries``, or ``{}`` for anything unreadable,
    malformed, or written under a different schema. Never raises: a memo that
    cannot be read is a miss, and a miss is only ever slower. Shared by both
    memos beside the evidence store."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    if not isinstance(data, dict) or data.get("schema") != schema:
        return {}
    entries = data.get("entries")
    return entries if isinstance(entries, dict) else {}


def write_memo_entries(path: Path, schema: int, entries: dict, max_entries: int) -> bool:
    """Write ``entries`` (oldest first), keeping the newest ``max_entries``.
    ``False`` on an ``OSError``: best-effort by contract, since a memo that
    fails to save costs a recomputation and never a verdict."""
    if len(entries) > max_entries:
        entries = dict(list(entries.items())[-max_entries:])
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            path, json.dumps({"schema": schema, "entries": entries}, separators=(",", ":"))
        )
    except OSError:
        return False
    return True


def _key(base_tree: str, target_tree: str, fingerprint: str) -> str:
    """The memo key covers every input the verdict is a function of — including
    the CODE that computed it.

    The plugin version is in here because the cache outlives the plugin: it
    persists in `.git/prawduct/` across upgrades, and the verdict depends on
    `coverage_algebra.is_judgeable_path`, which decides which files need review
    at all. Widen that predicate in a release and every entry written by the
    older one becomes a `covered` the new rules would not grant. `CACHE_SCHEMA`
    was the intended guard and is a hand bump that nothing enforces — a
    maintainer changing judgeability has no reason to look at a cache module.
    The version is derived, so it cannot be forgotten, and the bytes of the
    judgeability modules ride with it (:func:`code_identity`) for the installs
    where one version string spans several code states.
    """
    return hashlib.sha256(
        "\0".join((
            str(CACHE_SCHEMA),
            # The version alone is constant across develop pushes on a git
            # checkout and across same-version installs, so it cannot identify
            # the code. See `code_identity`.
            code_identity(),
            base_tree,
            target_tree,
            fingerprint,
        )).encode()
    ).hexdigest()


def _read(path: Path) -> dict:
    """The cache file's entries, or ``{}`` for anything unreadable, malformed,
    or written under a different schema. Never raises: a cache that cannot be
    read is a cache miss, and a cache miss is only ever slower."""
    return read_memo_entries(path, CACHE_SCHEMA)


class VerdictCache:
    """One gate invocation's view of the memo. Built once, consulted by every
    call site that needs a composed verdict — the span itself and each
    diagnosis — so they share both the disk cache and the in-process one.

    Construct with :meth:`for_read`; a cache whose fingerprint could not be
    computed is *inert* (every call recomputes), so callers need no special
    case for "no store" or "unreadable store".
    """

    def __init__(self, path: "Path | None", fingerprint: "str | None"):
        self._path = path
        self._fingerprint = fingerprint
        self._enabled = path is not None and fingerprint is not None
        self._disk: "dict | None" = None
        self._memory: dict[str, dict] = {}
        self._dirty = False
        self.hits = 0
        self.misses = 0

    @classmethod
    def for_read(cls, project_dir: Path, read: dict) -> "VerdictCache":
        """Build the memo from the ``read_facts`` result whose facts it will be
        asked about.

        The fingerprint comes from that read rather than from a second look at
        the store, and that is a correctness property, not a saved syscall: the
        store is shared by every worktree of the clone, so two reads are two
        moments, and a sibling's ``critic-consolidate`` landing between them
        yields a key that does not describe the facts it was computed for.
        Taking both from one read makes the pairing structural — there is no
        window to lose.
        """
        return cls(cache_path(project_dir), read.get("coverage_fingerprint"))

    @property
    def enabled(self) -> bool:
        return self._enabled

    def verdict(
        self,
        facts: list[dict],
        base_tree: str,
        target_tree: str,
        diff_fn,
        key_fn,
    ) -> dict:
        """:func:`coverage_algebra.coverage_verdict`, memoized.

        **``facts`` must be the parse of the store this cache was fingerprinted
        from.** It is deliberately not in the key — hashing a 2,700-element
        structure per lookup would cost what the memo saves — so the fingerprint
        stands in for it, and that substitution is only sound while the two
        describe the same bytes. :meth:`for_read` is what makes that hold:
        both come out of one ``read_facts``. A caller that filtered the list, or
        paired a cache with a different read, would be asking a different
        question under an unchanged key.

        Returns a fresh copy every time, so a caller that annotates the verdict
        (``check_cumulative_critic`` adds ``base``/``target``/``base_source``)
        cannot mutate what the next caller — or the next gate call — reads back.
        """
        if not self._enabled or not base_tree or not target_tree:
            return coverage_algebra.coverage_verdict(
                facts, base_tree, target_tree, diff_fn, key_fn
            )
        key = _key(base_tree, target_tree, self._fingerprint)
        if key in self._memory:
            self.hits += 1
            return json.loads(json.dumps(self._memory[key]))
        if self._disk is None:
            self._disk = _read(self._path)
        cached = self._disk.get(key)
        if isinstance(cached, dict) and isinstance(cached.get("status"), str):
            self.hits += 1
            self._memory[key] = cached
            return json.loads(json.dumps(cached))
        self.misses += 1
        verdict = coverage_algebra.coverage_verdict(
            facts, base_tree, target_tree, diff_fn, key_fn
        )
        self._memory[key] = verdict
        self._dirty = True
        return json.loads(json.dumps(verdict))

    def flush(self) -> bool:
        """Persist newly computed verdicts. ``True`` when something was written.

        Best-effort by contract: a cache that fails to save costs the next call
        a recomputation and nothing else, so an ``OSError`` here must not turn a
        correct verdict into a gate failure. Re-reads the file first, so a
        sibling worktree's concurrent entries survive this write — last-writer
        semantics lose entries, and a lost entry is only ever slower.
        """
        if not self._enabled or not self._dirty:
            return False
        merged = _read(self._path)
        merged.update(self._memory)
        # Newest-last insertion order is what `dict` preserves, so the writer's
        # trim from the front drops the oldest.
        if not write_memo_entries(self._path, CACHE_SCHEMA, merged, MAX_ENTRIES):
            return False
        self._dirty = False
        return True
