"""The one-time relayout: `.prawduct/learnings.md` → `.claude/rules/learnings/`.

Every onboarded repo runs this once. It is a **mechanical, lossless transform**,
and each of those three words is doing work:

*Mechanical* — nothing here reads a rule for meaning. Sections are split on
``## ``, bullets are counted, titles are slugged, and the text is copied. A
transform that summarised, reworded or de-duplicated would be a transform whose
output nobody can check against its input, and the corpus it rewrites is the one
artifact a product cannot regenerate.

*Lossless* — the byte-accounting test is the contract: every rule of the source,
after :func:`strip_links`, appears **verbatim** somewhere in the concatenated
output. Only two classes of text are deliberately dropped, and both are pointers
rather than content: links into ``learnings-detail.md`` / ``learnings-history.md``
(the same command deletes those files, so the pointers are about to dangle) and
prawduct's own ``<!-- prawduct-learning: … -->`` metadata comments. Preamble
above the first ``## `` goes too — it is the old file's header, and the new
``core.md`` ships its own (:data:`learnings_files.CORE_HEADER`). An author's
other HTML comments survive: they are rationale someone wrote, not machinery.

*One-time* — so the failure that matters is not a bad layout, it is a **deletion
without a destination**. ``--apply`` writes three tracked files and deletes
three; the operator's control point is the commit that follows. Five refusals
protect that commit, all of them exit 2 with a named reason:

* a legacy file git cannot give back — **ignored** or never committed.
  ``git status`` does not list ignored paths at all, so this is decided from
  *tracking*, where an ignored file and an untracked one are the same answer;
* the legacy files have uncommitted changes — git is the undo, and a dirty file
  has no committed version to come back to;
* the destination is **gitignored** — ``--apply`` would delete tracked files and
  write untracked ones, which is data loss dressed as a migration (a product
  gitignoring ``.claude/`` is common, so this is the likely case, not the exotic
  one);
* a **map key naming no section** — a mistyped slug scopes nothing, and the
  topic it meant to scope lands in the always-loaded file instead, which is the
  inverse of what scoping is for;
* the repo is in the ``both`` state and its rules files are **not** this plan's
  output — two corpora is a fold only a reader can do.

A migrated repo reports "nothing to do" and exits 0, so a second run is safe.
A ``both`` whose rules files ARE byte-identical to this plan is not a second
corpus but an interrupted run of this one, and finishes instead of refusing.

Two sections can want the same file. Outputs are therefore keyed by
**destination path**, and sections landing on one path merge into it under
their own headings, globs unioned — including the reserved ``core.md``, which a
topic titled "Core" would otherwise overwrite wholesale. Every merge is named
in the plan, because a fold the operator did not ask for is a fold they must
be able to see.

Format coverage. The fleet writes learnings three ways and this reads all of
them by one discriminator: **a ``## `` section holding top-level ``- `` bullets
is a topic; one holding none is itself a single rule.** That is not a guess
about title length — it is the structural difference between "a heading that
names a group" and "a heading that *is* the rule", which is what the two later
fleet formats (H2 + body, and the paragraph-heading form the 2026-07-31 ruling
spread) both produce. Topics with a glob mapping become scoped area files;
topics without become their own headings in ``core.md``; single-rule sections
land in ``core.md`` under ``## Unsorted``, where the next author can see at a
glance what has not been filed yet.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import learnings_files

#: The two companion files the cutover deletes with the corpus. Their names are
#: written here rather than imported because nothing else in the plugin has any
#: business knowing they exist — after this command runs, they do not.
DETAIL_REL = ".prawduct/learnings-detail.md"
HISTORY_REL = ".prawduct/learnings-history.md"

#: Everything ``--apply`` removes, in report order.
LEGACY_FILES = (learnings_files.LEGACY_REL, DETAIL_REL, HISTORY_REL)

#: The heading the unfiled single-rule sections land under in ``core.md``.
UNSORTED_HEADING = "Unsorted"

#: Section kinds. ``topic`` groups bullet rules under a name; ``rule`` IS one
#: rule, written as its own heading.
KIND_TOPIC = "topic"
KIND_RULE = "rule"

#: Directories that are never a scope. Hidden ones are excluded separately; this
#: list is the non-hidden noise that would otherwise win "largest top-level
#: directory" on a repo with vendored dependencies checked in.
_SKIP_DIRS = frozenset({
    "node_modules",
    "__pycache__",
    "venv",
    "env",
    "dist",
    "build",
    "target",
    "vendor",
    "site-packages",
})

#: Title tokens too short or too generic to scope anything. ``lib`` and ``src``
#: are here because they name a *layer*, not a domain: a "Lib" section matching
#: ``src/lib/**`` would scope a rule by where code happens to sit.
_STOP_TOKENS = frozenset({"and", "the", "a", "of", "in", "for", "lib", "src"})


class MigrateRefused(RuntimeError):
    """:func:`apply` was called on a plan carrying refusals."""


class MigrateInterrupted(RuntimeError):
    """:func:`apply` failed part-way. ``written`` is what reached disk.

    Carried rather than merely logged because the operator's next question is
    always "what state am I in now", and because the answer is short: re-run the
    same command — it recognises its own half-written tree and finishes.
    """

    def __init__(self, message: str, written: list[str]) -> None:
        super().__init__(message)
        self.written = list(written)


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

_DEAD_FILES = r"learnings-(?:detail|history)\.md"

#: ``<!-- prawduct-learning: … -->``, possibly spanning lines. Prawduct's own
#: bookkeeping about a rule, which the new layout keeps nowhere.
_METADATA_COMMENT = re.compile(
    r"[ \t]*<!--\s*prawduct-learning:.*?-->[ \t]*\n?", re.DOTALL | re.IGNORECASE
)

#: ``Detail: [ZMQ & Multi-Process Details](learnings-detail.md#…).`` — a whole
#: sentence whose only content is the pointer, terminating period included.
#: Matched before the bare link form so the period goes with it; leaving it
#: behind strands a ``.`` against the previous sentence's own full stop.
_DEAD_SENTENCE = re.compile(
    r"[ \t]*Detail:[ \t]*\[[^\]\n]*\]\([ \t]*" + _DEAD_FILES + r"[^)\n]*\)\.?",
    re.IGNORECASE,
)

#: ``[detail](learnings-detail.md#…)`` sitting inside a sentence that continues
#: without it. The trailing period is NOT eaten here — it belongs to the
#: surrounding sentence.
# A bare bracketed pointer with no link target — `… — [learnings-detail.md]` — the
# form one fleet member (prawduct itself, 67 headings) used instead of a markdown link.
_DEAD_BRACKET = re.compile(r"[ \t]*(?:—|-)?[ \t]*\[learnings-detail\.md\]")
_DEAD_LINK = re.compile(
    r"[ \t]*\[[^\]\n]*\]\([ \t]*" + _DEAD_FILES + r"[^)\n]*\)",
    re.IGNORECASE,
)

#: ``; detail in learnings-detail.md.`` inside a parenthetical that also carries
#: a date or a scope name — the clause goes, the provenance stays.
_DEAD_CLAUSE = re.compile(
    r"[;,][ \t]*detail in " + _DEAD_FILES + r"\.?", re.IGNORECASE
)

#: A parenthetical that was *only* the pointer.
_DEAD_PARENTHETICAL = re.compile(
    r"[ \t]*\([ \t]*detail in " + _DEAD_FILES + r"\.?[ \t]*\)", re.IGNORECASE
)

#: The terse form the later corpus used.
_DEAD_ARROW = re.compile(r"[ \t]*→[ \t]*detail\.?")


def strip_links(text: str) -> str:
    """Remove pointers into the files this migration deletes, and nothing else.

    Applied to titles and bodies alike, and applied to the *source* side of the
    byte-accounting check too — which is what makes the accounting meaningful:
    both sides are compared after the same cleaning, so anything this function
    removes is removed on purpose and everything else must survive byte for
    byte.

    The parenthetical forms are handled in two passes because the corpus writes
    both ``(detail in learnings-detail.md.)`` — the whole parenthetical is the
    pointer — and ``(2026-07-30, eval-judge-persona-context; detail in
    learnings-detail.md.)``, where dropping the parentheses would take a date
    and a scope name with it.
    """
    text = _METADATA_COMMENT.sub("", text)
    text = _DEAD_PARENTHETICAL.sub("", text)
    text = _DEAD_CLAUSE.sub("", text)
    text = _DEAD_SENTENCE.sub("", text)
    text = _DEAD_LINK.sub("", text)
    text = _DEAD_BRACKET.sub("", text)
    text = _DEAD_ARROW.sub("", text)
    # Cleaning leaves the punctuation that led into the pointer stranded a space
    # from its sentence. Per-line so a removal can never join two lines.
    return "\n".join(
        re.sub(r"[ \t]+([.,;)])", r"\1", line).rstrip() for line in text.split("\n")
    )


def slug(title: str) -> str:
    """A file-name stem from a section title: lowercase, ``-``-joined tokens.

    ``"Eval & Model Bake-offs"`` → ``"eval-model-bake-offs"``. The slug is the
    map file's key as well as the area file's name, so an agent editing the
    proposed map is editing something it can see on disk afterwards.
    """
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Section:
    """One ``## `` section of the legacy corpus, already cleaned.

    ``rules`` is the rule **text** rather than the rule *line*: a topic's
    bullets without their ``- ``, or — for a single-rule section — the title
    itself. That is the unit the byte accounting checks for verbatim survival,
    and it is prefix-independent on purpose, because a single-rule section is
    written ``## `` in the source and ``### `` under ``## Unsorted`` in the
    output. The heading level changes; the rule may not.
    """

    title: str
    body: str
    kind: str
    rules: list[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return slug(self.title)

    @property
    def is_topic(self) -> bool:
        return self.kind == KIND_TOPIC


def parse_legacy(text: str) -> list[Section]:
    """Split the corpus into sections, cleaned and classified.

    Everything before the first ``## `` is preamble and is dropped: it is the
    old file's title and its pointer at ``learnings-detail.md``, both of which
    the new layout replaces. Headings inside fenced code blocks are not
    headings — a rule quoting markdown would otherwise split itself in half.
    """
    titles: list[str] = []
    bodies: list[list[str]] = []
    current: list[str] | None = None
    fenced = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith("## "):
            titles.append(line[3:].strip())
            current = []
            bodies.append(current)
            continue
        if current is not None:
            current.append(line)

    sections: list[Section] = []
    for title, body_lines in zip(titles, bodies):
        clean_title = strip_links(title).strip()
        body = _trim_blank_edges(strip_links("\n".join(body_lines)))
        bullets = [
            line[2:].strip() for line in body.split("\n") if line.startswith("- ")
        ]
        if bullets:
            sections.append(
                Section(title=clean_title, body=body, kind=KIND_TOPIC, rules=bullets)
            )
        else:
            sections.append(
                Section(
                    title=clean_title,
                    body=body,
                    kind=KIND_RULE,
                    rules=[clean_title] if clean_title else [],
                )
            )
    return sections


def _trim_blank_edges(text: str) -> str:
    lines = text.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The topic → glob map
# ---------------------------------------------------------------------------


def _candidate_dirs(project_dir: Path) -> list[tuple[str, str]]:
    """``(directory name, root-relative glob)`` for every plausible scope.

    Two tiers, because a repo's domains sit at one of two depths: the top-level
    directories, and — for the repo's largest top-level directory, which for a
    single-package repo is the package — that directory's own children.
    "Largest" is by file count rather than by any language's packaging marker,
    so this works on a TypeScript monorepo and a Python package alike.
    """
    tops = sorted(
        p
        for p in _safe_iterdir(project_dir)
        if p.is_dir() and not p.name.startswith(".") and p.name not in _SKIP_DIRS
    )
    out = [(p.name, f"{p.name}/**") for p in tops]
    if not tops:
        return out
    largest = max(tops, key=lambda p: (_file_count(p), p.name))
    for child in sorted(_safe_iterdir(largest)):
        if not child.is_dir() or child.name.startswith(".") or child.name in _SKIP_DIRS:
            continue
        out.append((child.name, f"{largest.name}/{child.name}/**"))
    return out


def _safe_iterdir(path: Path) -> list[Path]:
    try:
        return list(path.iterdir())
    except OSError:
        return []


def _file_count(path: Path) -> int:
    try:
        return sum(1 for p in path.rglob("*") if p.is_file())
    except OSError:
        return 0


def _token_matches(token: str, name: str) -> bool:
    """Case-folded equality, tolerating one repo's plural against another's singular.

    ``eval`` must reach ``evals/`` and ``music`` must reach ``music/``; nothing
    fuzzier, because a partial match would scope a rule to a directory that
    merely shares a prefix, and a rule loaded on the wrong reads is worse than a
    rule the agent files by hand.
    """
    name = re.sub(r"[^a-z0-9]+", "", name.lower())
    if not token or not name:
        return False
    return token == name or token + "s" == name or token == name + "s"


def propose_map(
    project_dir: str | Path, sections: list[Section]
) -> dict[str, list[str]]:
    """Slug → globs, for the topic sections whose title names a directory.

    A proposal, not a decision: the command prints it to a sidecar the agent
    edits and hands back with ``--map``. Sections with no match get **no entry**
    — they go to ``core.md``, which is the safe direction, because an
    unrecognised topic filed into core is merely unscoped while one scoped to a
    guessed directory is invisible on every read outside it.
    """
    candidates = _candidate_dirs(Path(project_dir))
    proposal: dict[str, list[str]] = {}
    for section in sections:
        if not section.is_topic:
            continue
        tokens = [
            t for t in section.slug.split("-") if len(t) > 2 and t not in _STOP_TOKENS
        ]
        globs: list[str] = []
        for name, glob in candidates:
            if any(_token_matches(token, name) for token in tokens) and glob not in globs:
                globs.append(glob)
        if globs:
            proposal[section.slug] = globs
    return proposal


def format_map(proposal: dict[str, list[str]], unmatched: list[str]) -> str:
    """The sidecar text: one ``slug: [glob, …]`` line per topic.

    Unmatched topics are emitted **commented out** rather than omitted. Omitting
    them would hide the decision the agent is there to make — the sidecar's job
    is to show every topic and let a reader scope the ones the matcher could not.
    """
    lines = [f"{name}: [{', '.join(globs)}]" for name, globs in sorted(proposal.items())]
    if unmatched:
        lines.append("")
        lines.append("# No directory matched these topics; they go to core.md as they")
        lines.append("# are. Uncomment and fill in globs to scope one to an area file.")
        lines.extend(f"# {name}: []" for name in sorted(unmatched))
    return "\n".join(lines) + "\n"


def parse_map(text: str) -> dict[str, list[str]]:
    """Read a ``slug: [glob, …]`` sidecar back.

    Blank lines and ``#`` comments are skipped, so the file the command printed
    round-trips unedited. A line that is not ``slug: [...]`` raises
    :class:`ValueError` naming it — a typo'd glob that silently scoped nothing
    would send a whole topic to core with no signal at all.
    """
    mapping: dict[str, list[str]] = {}
    for number, raw in enumerate(text.split("\n"), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"line {number}: expected `slug: [glob, …]`, got {raw!r}")
        name, _, value = line.partition(":")
        name = name.strip()
        value = value.strip()
        if not name:
            raise ValueError(f"line {number}: empty slug in {raw!r}")
        if value.startswith("[") and value.endswith("]"):
            items = [g.strip().strip("\"'") for g in value[1:-1].split(",")]
        else:
            items = [value.strip().strip("\"'")]
        globs = [g for g in items if g]
        if globs:
            mapping[name] = globs
    return mapping


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OutputFile:
    """One file ``--apply`` would write."""

    rel: str
    content: str
    rules: int

    @property
    def size(self) -> int:
        return len(self.content.encode("utf-8"))


@dataclass(frozen=True)
class Plan:
    """What the migration would do, and why it may not.

    ``refusals`` non-empty means ``--apply`` must not run; ``nothing_to_do``
    means it need not. Both are reported rather than raised so a dry run can
    print the reason in the same shape as the plan it could not make.

    ``merges``, ``unmapped`` and ``resumed`` exist because the operator's whole
    control over this command is reading its report before authorising it: a
    transform that quietly folded two topics together, quietly ignored a
    scoping decision, or quietly resumed someone else's half-finished run would
    be a report you cannot audit against the tree it produces.
    """

    state: str
    outputs: list[OutputFile] = field(default_factory=list)
    deletions: list[str] = field(default_factory=list)
    refusals: list[str] = field(default_factory=list)
    nothing_to_do: str | None = None
    sections: list[Section] = field(default_factory=list)
    unmapped: list[str] = field(default_factory=list)
    merges: list[str] = field(default_factory=list)
    resumed: bool = False

    @property
    def rules(self) -> int:
        return sum(o.rules for o in self.outputs)

    @property
    def size(self) -> int:
        return sum(o.size for o in self.outputs)


# ---------------------------------------------------------------------------
# What git can and cannot restore
# ---------------------------------------------------------------------------


def _git(project_dir: Path | str, *args: str) -> subprocess.CompletedProcess | None:
    """Run git in the project, or ``None`` when git cannot answer.

    ``None`` is "unknown", never "clean": callers treat it as *no evidence of a
    problem* only where the absence of a repo genuinely removes the risk.
    """
    try:
        proc = subprocess.run(  # noqa: S603 — list-form argv, no shell (project preference)
            ["git", *args],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc


def _is_git_repo(project_dir: str | Path) -> bool:
    proc = _git(project_dir, "rev-parse", "--git-dir")
    return proc is not None and proc.returncode == 0


def dirty_legacy_files(project_dir: str | Path) -> list[str]:
    """Porcelain status lines for **tracked** legacy files with local changes.

    Untracked entries are filtered out here rather than reported twice: a file
    git does not track is :func:`unrecoverable_legacy_files`' subject, and it
    needs a different sentence — "commit your edit" is useless advice about a
    file that has never been committed at all.
    """
    proc = _git(project_dir, "status", "--porcelain", "--", *LEGACY_FILES)
    if proc is None or proc.returncode != 0:
        return []
    return [
        line
        for line in proc.stdout.split("\n")
        if line.strip() and not line.startswith("??")
    ]


def unrecoverable_legacy_files(project_dir: str | Path) -> list[tuple[str, str]]:
    """``(path, why)`` for each legacy file git could not give back.

    Two ways a corpus about to be deleted has no committed version behind it,
    and they are not the same fix:

    * **ignored** — ``.gitignore`` covers it (``.prawduct/`` is a plausible
      thing for a product to ignore). ``git status --porcelain`` does not list
      ignored paths at all, so a status-based check reads such a repo as clean
      and ``--apply`` unlinks a file git has never seen. Deciding from
      *tracking* is what closes that: an ignored file and an untracked one are
      both simply "not in the index".
    * **never committed** — added to the tree but not to git.

    Nothing is reported outside a git repo: with no repo there is no history
    for the deletion to be measured against, and refusing there would block a
    real, if unusual, product for a risk it does not carry.
    """
    root = Path(project_dir)
    if not _is_git_repo(root):
        return []
    out: list[tuple[str, str]] = []
    for rel in LEGACY_FILES:
        if not (root / rel).is_file():
            continue
        tracked = _git(root, "ls-files", "--error-unmatch", "--", rel)
        if tracked is not None and tracked.returncode == 0:
            continue
        ignored = _git(root, "check-ignore", "-q", "--no-index", "--", rel)
        why = (
            "ignored by git"
            if ignored is not None and ignored.returncode == 0
            else "never committed"
        )
        out.append((rel, why))
    return out


# ---------------------------------------------------------------------------
# Building the output files
# ---------------------------------------------------------------------------


@dataclass
class _Destination:
    """One output path and every section that lands on it.

    Sections are grouped by **destination**, not by slug, which is what makes
    the collision cases fall out of one rule instead of three. Two topics whose
    titles slug alike address one file — ``propose_map`` can only give them one
    map entry anyway — and merging them keeps both headings and every byte,
    where writing them in list order silently kept whichever came last.
    """

    rel: str
    sections: list[Section] = field(default_factory=list)
    globs: list[str] = field(default_factory=list)


def _area_content(destination: _Destination) -> str:
    paths = "\n".join(f'  - "{g}"' for g in destination.globs)
    body = "\n\n".join(
        f"# {s.title}\n\n{s.body}".rstrip() for s in destination.sections
    )
    return f"---\npaths:\n{paths}\n---\n\n{body}\n"


def _core_content(topics: list[Section], rules: list[Section]) -> str:
    parts = [learnings_files.CORE_HEADER.rstrip("\n")]
    for section in topics:
        parts.append(f"## {section.title}\n\n{section.body}".rstrip())
    if rules:
        unsorted = [f"## {UNSORTED_HEADING}"]
        for section in rules:
            block = f"### {section.title}"
            if section.body:
                block += f"\n\n{section.body}"
            unsorted.append(block)
        parts.append("\n\n".join(unsorted))
    return "\n\n".join(parts) + "\n"


def _build_outputs(
    sections: list[Section], mapping: dict[str, list[str]]
) -> tuple[list[OutputFile], list[str], list[str]]:
    """``(outputs, unmapped slugs, merge notes)`` — core first, areas by path."""
    core_rel = f"{learnings_files.RULES_DIR_REL}/{learnings_files.CORE_NAME}"
    destinations: dict[str, _Destination] = {}
    core_topics: list[Section] = []
    core_rules: list[Section] = []
    unmapped: list[str] = []
    merges: list[str] = []

    for section in sections:
        if not section.is_topic:
            core_rules.append(section)
            continue
        globs = mapping.get(section.slug)
        if not globs:
            core_topics.append(section)
            if section.slug not in unmapped:
                unmapped.append(section.slug)
            continue
        rel = f"{learnings_files.RULES_DIR_REL}/{section.slug}.md"
        if rel == core_rel:
            # The reserved name. Merging is still the lossless answer — every
            # byte lands in core.md under its own heading — but the `paths:`
            # the agent wrote cannot survive it, because core.md is *defined*
            # as the file with no paths. Said out loud rather than absorbed:
            # the difference is a rule loaded on every session start instead of
            # on a matching read, which is the budget gate's whole subject.
            core_topics.append(section)
            merges.append(
                f"{section.title!r} slugs to {learnings_files.CORE_NAME!r}, the "
                "always-loaded file — merged into it, so the globs mapped to "
                f"{section.slug!r} do not scope it"
            )
            continue
        existing = destinations.get(rel)
        if existing is None:
            destinations[rel] = _Destination(rel, [section], list(globs))
            continue
        merges.append(
            f"{section.title!r} and {existing.sections[0].title!r} both slug to "
            f"{section.slug!r} — merged into one file, each under its own heading"
        )
        existing.sections.append(section)
        for glob in globs:
            if glob not in existing.globs:
                existing.globs.append(glob)

    outputs = [
        OutputFile(
            rel=core_rel,
            content=_core_content(core_topics, core_rules),
            rules=sum(len(s.rules) for s in core_topics + core_rules),
        )
    ]
    for rel in sorted(destinations):
        destination = destinations[rel]
        outputs.append(
            OutputFile(
                rel=rel,
                content=_area_content(destination),
                rules=sum(len(s.rules) for s in destination.sections),
            )
        )
    return outputs, unmapped, merges


def _resume_state(root: Path, outputs: list[OutputFile]) -> bool:
    """Is this ``both`` the wreckage of an interrupted apply of THIS plan?

    True only when every rules file already on disk is byte-identical to what
    this plan would write — which no genuine two-corpus repo can be, and which
    a half-finished run of this exact plan always is. That distinction is what
    lets a transient write error be re-run away instead of sending an operator
    to hand-merge a 160KB corpus.
    """
    rules_dir = root / learnings_files.RULES_DIR_REL
    planned = {o.rel: o.content.encode("utf-8") for o in outputs}
    existing = {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(rules_dir.rglob("*.md"))
        if p.is_file()
    }
    if not existing:
        return False
    return all(planned.get(rel) == data for rel, data in existing.items())


def plan(
    project_dir: str | Path, mapping: dict[str, list[str]] | None = None
) -> Plan:
    """What the migration would write and delete, or why it will not.

    Reads the legacy corpus itself rather than taking parsed sections, so the
    dry run and ``--apply`` cannot diverge on which bytes they were looking at.
    """
    root = Path(project_dir)
    layout = learnings_files.resolve(root)

    if layout.state not in (learnings_files.STATE_LEGACY, learnings_files.STATE_BOTH):
        return Plan(
            state=layout.state,
            nothing_to_do=(
                f"no {learnings_files.LEGACY_REL} to migrate; "
                f"this repo is in the '{layout.state}' state."
            ),
        )

    legacy = root / learnings_files.LEGACY_REL
    try:
        text = legacy.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return Plan(
            state=layout.state,
            refusals=[f"cannot read {learnings_files.LEGACY_REL}: {exc}"],
        )

    sections = parse_legacy(text)
    mapping = mapping or {}
    outputs, unmapped, merges = _build_outputs(sections, mapping)
    deletions = [rel for rel in LEGACY_FILES if (root / rel).is_file()]

    refusals: list[str] = []
    resumed = False

    if layout.state == learnings_files.STATE_BOTH:
        resumed = _resume_state(root, outputs)
        if not resumed:
            refusals.append(
                "both layouts are present: "
                f"{learnings_files.LEGACY_REL} and "
                f"{learnings_files.RULES_DIR_REL}/ both hold rules, and the rules "
                "files are NOT what this plan would write — so this is a repo with "
                "two corpora, not an interrupted --apply. Fold the old file into "
                "the rules files by hand and delete it; only a reader can tell "
                "which copy of a rule is the current one."
            )

    unknown = sorted(
        key for key in mapping if key not in {s.slug for s in sections if s.is_topic}
    )
    if unknown:
        refusals.append(
            "map key(s) matching no section in the corpus: "
            + ", ".join(repr(k) for k in unknown)
            + ". A mistyped slug would silently send its topic to core.md, where "
            "it loads on every session start instead of on a matching read. Run "
            "--propose-map again for the current slugs."
        )

    for rel, why in unrecoverable_legacy_files(root):
        refusals.append(
            f"{rel} is {why}, so git cannot give it back once --apply deletes "
            "it. Commit it first (unignore it if an ignore rule covers it) — "
            "the commit is this migration's undo."
        )
    dirty = dirty_legacy_files(root)
    if dirty:
        refusals.append(
            "uncommitted changes to the files this migration deletes — commit "
            "or stash them first, because the commit is the undo:\n    "
            + "\n    ".join(dirty)
        )
    if learnings_files.rules_dir_is_gitignored(root):
        refusals.append(
            f"the destination is gitignored: a new file under "
            f"{learnings_files.RULES_DIR_REL}/ matches an ignore rule, so --apply "
            "would delete tracked files and write files git never sees. "
            "Unignore .claude/rules/ first."
        )

    return Plan(
        state=layout.state,
        outputs=outputs,
        deletions=deletions,
        refusals=refusals,
        sections=sections,
        unmapped=unmapped,
        merges=merges,
        resumed=resumed,
    )


def apply(project_dir: str | Path, migration: Plan) -> list[str]:
    """Write the plan's files and delete the legacy ones. Returns what changed.

    Writes before deletes, and refuses outright on a plan carrying refusals —
    the check belongs here as well as in the command, because this is the
    function that can lose a corpus and a caller that skipped the dry run must
    not be able to skip the guard with it.

    A write that fails part-way raises :class:`MigrateInterrupted` carrying the
    files that reached disk. Nothing is rolled back on purpose: the half-written
    tree is what lets the *next* run recognise its own wreckage and finish the
    job (:func:`_resume_state`), where a rollback would leave the operator with
    an error message and no evidence. An interrupt that no ``except`` can see
    lands in the same recoverable state, because recovery is decided from the
    tree rather than from the exception.
    """
    if migration.refusals:
        raise MigrateRefused("; ".join(migration.refusals))
    root = Path(project_dir)
    changed: list[str] = []
    for output in migration.outputs:
        path = root / output.rel
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(output.content, encoding="utf-8")
        except OSError as exc:
            raise MigrateInterrupted(f"writing {output.rel}: {exc}", changed) from exc
        changed.append(output.rel)
    for rel in migration.deletions:
        try:
            (root / rel).unlink(missing_ok=True)
        except OSError as exc:
            raise MigrateInterrupted(f"deleting {rel}: {exc}", changed) from exc
        changed.append(rel)
    return changed
