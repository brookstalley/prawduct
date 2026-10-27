# project-state.yaml — Optional Keys

The reference for the optional and opt-in keys of a product's `.prawduct/project-state.yaml`.
The template a repo is scaffolded from carries each key as a one-line comment that points here,
so the full explanation is read when a key is being set rather than by every session that reads
the state file. Read it as `/prawduct:methodology project-state`.

The sections discovery fills (classification, product definition, decisions, open questions)
keep their guidance inline in the template, because that is where it is read.

## active_build_plan (optional, deprecated 2026-10-24)

**Deprecated.** A plan binds to a checkout by declaring `branch:` in its frontmatter
(`methodology/planning.md` "Which plan governs a checkout"); this scalar is served only when no
live plan declares `branch:`, as the legacy route, and the `plan-unbound-legacy` advisory names
each checkout it served. Migrate with `prawduct-hook plan bind <path> --branch <name>`. The window
closes no earlier than two minor releases after the deprecation, and only after that advisory has
been observed firing on no known consumer.

Names the in-progress build plan when it isn't the conventional `artifacts/build-plan.md` —
scope-named plans (`artifacts/build-plan-<scope>.md`) keep release-pending plans distinct under
gitflow. The value is a path relative to `.prawduct/` (a repo-relative `.prawduct/...` spelling is
tolerated). A plan that declares `branch:` is never served by this scalar, on any branch. Unset →
`artifacts/build-plan.md`.

A pointer to a file that doesn't exist means governance sees no active plan by this route — the
session briefing warns when resolution actually took it.

```yaml
active_build_plan: artifacts/build-plan-my-scope.md
```

## base_branch (opt-in, unset by default)

The branch this product's feature work integrates onto — the base every gate diffs against: the PR
gate, the doc-only gate, the cumulative-Critic span, and the reviewer's own range.

**Set it on a gitflow repo.** Unset, base resolution first asks the remote what it integrates onto
(`refs/remotes/origin/HEAD`, which a clone records) and prefers that when it names something
outside the main family; only if that yields nothing does it fall back to guessing `origin/main`,
then `main`, then `HEAD~1`. On a repo whose features cut from `develop`, reaching that guess
anchors every gate to `merge-base(main, HEAD)` — a two-commit branch reviewed as the entire
`develop..main` promotion delta, silently and plausibly.

**This key outranks the remote's answer**, deliberately: a remote default and a product's
integration branch are allowed to differ (a repo whose remote default is `main` while feature work
integrates onto `develop` is exactly the case `origin/HEAD` cannot see), and this is the one an
owner wrote down. `origin/<b>` is preferred over a bare `<b>` for a merge-base that is the same
value in every clone and worktree.

A configured-but-unresolvable value fails CLOSED — the gate refuses rather than quietly diffing the
wrong range — so a typo surfaces instead of shipping. `/prawduct:onboard` and `/prawduct:migrate`
write it when the remote's default is non-main; set it by hand otherwise.

```yaml
base_branch: develop
```

## build_plan_ref_root (opt-in, unset by default)

A second root that this repo's build-plan file refs may be written relative to.
`verify-chunk-refs` tries the repo root first, then this.

Set it when your plans name files the way they read from INSIDE a subdirectory rather than from
the repo root — e.g. a repo that ships a plugin, an extension, or a bundled tool, whose plans say
`lib/gates.py` meaning `plugin/lib/gates.py`. Without the declaration each such ref reports as a
missing deliverable.

DECLARED, never inferred: the verifier will not guess this from your layout, because "there is a
directory that looks like a plugin root" is an ordinary layout rather than a statement of intent,
and guessing would silently resolve a genuinely missing deliverable against an unrelated
directory. Unset (the default) means the repo root is the only root. A value that escapes the
repo, doesn't exist, or isn't a directory is ignored.

```yaml
build_plan_ref_root: plugin
```

## risk_surfaces (opt-in)

The paths where a missed defect costs your product the most — auth, payments, migrations, a public
API contract, whatever yours are. Two consumers read the list: `prawduct-hook classify-diff-risk`
(the review `tier`) and the Critic's roster derivation, which gives a diff touching any of them the
deeper three-reviewer review at any size.

Nothing asks for this list, and leaving it unset is a healthy state. Unset, two things escalate:
prawduct's framework-shaped defaults (`skills/`, `lib/gates*`, `bin/*hook*`, plus any contract
paths you list in boundary-patterns.md), which rarely match a product's own tree, and volume — 12
or more judgeable files. There is no file-count fallback below that: prawduct will not review a
small change to your riskiest code more deeply unless you have named that code here.

**A declared list REPLACES those defaults, it does not add to them** — the contract paths from
boundary-patterns.md stop escalating unless you list them here too. So declaring is not free: it
trades the defaults for your list.

Pattern semantics: a trailing `/` is a directory prefix; anything else is an fnmatch glob (a plain
path with no metacharacters is an exact match). Write it as a block list (one `- path` per line);
`[a, b]` flow style is refused and escalates every review until rewritten. An explicit empty list
(`risk_surfaces: []`) replaces the defaults with nothing and turns the tier check off — strictly
less review than leaving the key out.

```yaml
risk_surfaces:
  - src/auth/
  - src/billing/
  - migrations/
  - src/api/contract.py
```

## release_version_files (opt-in)

Which of YOUR files carry the release version, read by `prawduct-hook check-released`. One
consumer, three questions: which paths, how is each read, and which key holds the value.

**Declaring is what lets a mismatch FAIL your release.** Leave it unset and check-released falls
back to guessing prawduct's own layout (`plugin/VERSION`, `plugin/.claude-plugin/plugin.json`,
`pyproject.toml`) — and because that is a guess about a product that never claimed it, the guess
may only report `ok` or `unverifiable`, never `not-released`. That is deliberate: a setuptools-scm
project, or one whose `pyproject.toml` is tooling-only, must not be told its release is broken
against a layout it never chose. Declare your files and prawduct will hold you to them.

**Read from the TAG's tree, not your checkout** — which files carried a release's version is a
fact about that release. So a release cut before you added this key keeps grading through the
fallback, and reorganising your layout later cannot retroactively fail an old release.

`format` names a structural shape, not a language:

- `bare` — the whole file is the version string (no `key`)
- `json` — decoded, then `key` descended
- `toml` — decoded via stdlib `tomllib`, then `key` descended

`key` is a dotted path descended literally, which is what keeps the read dumb: you say
`project.version` and nothing has to decide which table of a manifest wins. A key name containing
a literal dot is not expressible — point at a `bare` or `json` file instead.

`toml` needs Python 3.11+ (`tomllib`); on 3.10 such an entry reports `unverifiable` rather than
failing, since an interpreter's stdlib is not evidence about your release. Block style only. An
empty list is a deliberate "this product ships no version file" and reports that nothing was
checked.

```yaml
release_version_files:
  - path: VERSION
    format: bare
  - path: package.json
    format: json
    key: version
  - path: Cargo.toml
    format: toml
    key: package.version
```

## consumer_digest (opt-in)

Your changelog, so `prawduct-hook cut-change-log` writes each release's notes into it. Every
fragment's `## Consumer note` is required. Without this key, those notes stay in
`.prawduct/change-log-archive/` and reach no consumer.

**What the cut does with it.** At `--apply`, it renders the shipping notes into a new file,
`.prawduct/releases/<version>.md`: a heading, your headline, then the notes. It then inserts that
section into your changelog:
- directly below `marker` if you declare one;
- otherwise above the first `## ` heading that *leads with* a version (`## 1.4.0`, `## v1.4.0`,
  `## [1.4.0] - …`), as `heading` must, so `## [Unreleased]` or `## Contents` stays on top;
- with no such heading at all, at the end.

If your history spells headings another way (`## Release 1.4.0`), none of them leads with a
version, so the first cut would land at the bottom of the file. Declare a `marker` line above
your newest release to place it instead. Do the same if you file patch releases as `### [1.0.1]`
under a minor's `## ` heading: only `## ` headings count, so the new section would land below
those patches.

No other byte changes: line endings, a BOM, and the trailing newline are kept. The cut never
searches for an open section and never renames one. The release file is also the record that the
release is cut, so a re-run writes nothing twice. Commit it, along with `.prawduct/changes/` and
the archive, and keep every one: release files are permanent history, never pruned.

**The headline** is the release's one-line judgement, kept in `.prawduct/release-headline.md`
before the cut. The cut puts it under the heading and removes the file. With `headline: required`,
the cut refuses `no-headline` without it, and Phase 0 (`check-releasability`) warns first.

**Refusals**, each with nothing written. `check-releasability` warns ahead of the cut about every
one from `digest-missing` to `releases-ignored`:
- `digest-declaration-invalid`: the block below is malformed, or `project-state.yaml` cannot be
  read;
- `digest-missing`, `digest-unreadable`: the changelog is not a file, or not UTF-8;
- `marker-missing`: the declared marker line is not in the changelog;
- `release-in-changelog`: a section already names this release (remove it, or move its first
  paragraph into the headline file);
- `no-headline`;
- `releases-ignored`: git ignores `.prawduct/releases/`;
- `release-already-cut`: a fragment the release file doesn't hold is pending; it belongs to the
  next release.

The dry run prints the exact section, which you can paste into a release PR as the notes preview.

| Field | Values | Default |
|---|---|---|
| `path` | the changelog, repo-relative; must stay in the repo, outside `.git/` and `.prawduct/` | required |
| `heading` | quoted template: `{version}` (`v1.4.0`), `{version_no_prefix}` (`1.4.0`), `{date}` (your local date, `YYYY-MM-DD`); must start `## ` and lead with the version | `"## {version} - {date}"` |
| `headline` | `required` or `none` | `none` |
| `layout` | `paragraphs`, `bullets`, or `by-type` (a `### ` subsection per fragment type) | `bullets` |
| `entry` | quoted per-note template: `{note}` (required), `{scope}`, `{type}`, `{title}`; `{{` `}}` for literal braces | `"- {note}"`, or `` "**`{scope}`**: {note}" `` for `paragraphs` |
| `types` | `by-type` only, one flow mapping on one line: `{feature: Added, fix: Fixed}` | `feature`→Added, `fix`→Fixed, others→Changed |
| `marker` | a literal line; the section is inserted directly below it | none |

Quote `heading` and `entry`: YAML reads an unquoted `#` as the start of a comment.

**With another release tool** (release-please, semantic-release, a script that dates or tags), run
the cut first and the tool after it. The cut writes a finished section and never needs a heading
renamed.

```yaml
# Keep a Changelog
consumer_digest:
  path: CHANGELOG.md
  heading: "## [{version_no_prefix}] - {date}"
  layout: by-type

# prawduct's own
consumer_digest:
  path: plugin/CHANGELOG.md
  heading: "## {version}"
  headline: required
  layout: paragraphs
```

## coverage_required (opt-in, default false)

When true, the Critic requires every changed file the verifier can judge to appear in
`.test-evidence.json`'s `changes_referenced` list (files it can't judge — non-code, symbol-less,
deleted — are declared in `changes_unjudged` and reported, not gated) and scales severity language
to the declared `coverage_level` (`referenced` floor vs. `executed` real). The reference verifier
at `bin/test-reference-verify` emits the floor; products with non-trivial coverage concerns should
plug in a stronger verifier. See `/prawduct:methodology building` "Test Discipline". Default off —
schema is checked but content is not enforced.

## test_command, test_commands, test_rerun_command, test_rerun_commands, flaky_policy, tests_dirs (optional, gate-soundness)

`prawduct-hook test-evidence record` defaults to running `sys.executable -m pytest` from the repo
root and grepping a single `tests/` dir. When the repo's real shape differs (uv/venv-managed
interpreter, no root pytest config, monorepo test trees), declare it — don't wrap it.

**`test_command:`** — the canonical suite invocation (the exact command CI runs), shlex-split and
run from the repo root. Must contain the `{junit_xml}` literal — the hook substitutes its report
path there. Shell operators (&&, |, FOO=1) are not supported; point the command at a script for
compound runs. Caveat: the value is read by a YAML-comment-aware reader, so a `#` that starts a word
outside quotes begins a comment — quote it (`-k "not #slow"`) or wrap the invocation in a script.

```yaml
test_command: uv run pytest --junit-xml={junit_xml} -q
```

**`test_commands:`** — the multi-environment form (backend + web + mobile): one canonical
invocation per environment, each run under the same rules as `test_command:` (shlex-split,
mandatory `{junit_xml}`, an unquoted ` #` begins a comment); counts aggregate across all reports into ONE evidence
record, and any launch failure or unparseable report fails the whole record. Declare it ONLY as
this block-sequence-of-strings shape (flow style `[a, b]` and nested mappings are refused, not
silently ignored). Mutually exclusive with `test_command:`. Ingest path: repeat `--from-junit` once
per report.

```yaml
test_commands:
  - pipenv run pytest --junit-xml={junit_xml} -q
  - npm run test:ci -- --junit --outputFile={junit_xml}
```

**`test_rerun_command:` / `test_rerun_commands:`** — how `test-evidence record --rerun-failed`
retries only a run's failing tests. A declared command is never retried by appending ids to it,
because one that already names a selection (`pytest tests/ -m "…"`) would rerun all of it.
`test_rerun_command:` pairs with `test_command:`. `test_rerun_commands:` pairs by position with
`test_commands:`, one entry per command, and `none` means that command is not retried. A length
mismatch is refused. Each template is shlex-split, needs `{junit_xml}`, and takes
`{pytest_node_ids}` as a separate argument, which becomes one argument per failing test
(`tests/test_x.py::TestY::test_z`). Without a declared command, the fallback pytest path builds
its own rerun. Checked before any suite runs.

```yaml
test_command: uv run pytest tests --junit-xml={junit_xml} -q
test_rerun_command: uv run pytest --junit-xml={junit_xml} -q {pytest_node_ids}
```

**`flaky_policy:`** (`accept` | `warn` | `block`, default `warn`) — what a flake earns when this
branch touched it. A flake is a test that passed only on retry, whether the recorder's
`--rerun-failed` or a runner that reports it (`<flakyFailure>`). Each flake is judged at record
time against the branch's changed files. The test file comes from the report, or from the
classname (pytest's module path, or the class's own file in any language). One whose file or
diff cannot be read counts as touched, and its status line says why. The policy's answer is
decided then and printed with the flake: `accept` notes it; `warn` has the boundary Critic warn;
`block` leaves it failed, so the record stays red. A flake outside the branch's diff is noted
under every policy. An unknown value is refused.

**`tests_dirs:`** — whitespace-separated test trees for the coverage verifier (default: `tests`).
One verifier run unions discovery across all of them.

```yaml
tests_dirs: engine/tests server/tests
```

## suite_coupled_prefixes (opt-in)

The test-evidence freshness check treats a doc or metadata change as unable to change what the
suite says, so evidence recorded before it still reads `current`. That is wrong for files a test
reads as data — a guard that scans `documentation/` prose goes red on a doc edit. Declare those
paths, and a change under one makes recorded evidence stale, as a code change does.

Entries are repo-relative path PREFIXES, not globs, so the trailing slash is yours to write
(`doc/` does not match `documentation/`), and a prefix couples every file under it. Declare it ONLY
as a block sequence of strings; a declaration the reader cannot read whole (flow style, a wrapped
or mis-indented entry, a bare dash) couples EVERY path rather than dropping an entry, so a typo
costs suite runs, never a false `current`. Absent or `[]` couples nothing extra.

```yaml
suite_coupled_prefixes:
  - documentation/
  - .prawduct/artifacts/data-model.md
```

## learnings_budgets (opt-in override)

Learnings live in `.claude/rules/learnings/`: `core.md` is in every session's context from launch,
and each `<area>.md` arrives when a file its `paths:` globs match is read. So a rule is paid for by
every session that follows it, and the corpus has no natural ceiling — compacted four times, and
regrown past where it started every time.

Every rule is ONE line of at most 250 characters, with no body. `core.md` is capped at 12 KB and
ONLY THE OWNER raises it: a `core.md` entry counts only with an `owner_approved:` date. Each area
file defaults to 16 KB and may be raised here with a reason. A raise counts from the next session,
never the one that writes it, so growth and its excuse cannot land together.

The Stop hook blocks a file over its budget that grew this session, and any line breaking the
one-line format. A corpus not yet compacted is frozen: no file over its budget may grow, and every
added line must already be a one-line rule. Pay by merging or retiring a rule, or by moving a
path-scoped rule to its area file.

```yaml
learnings_budgets:
  core.md: {kb: 16, reason: "the owner's call", owner_approved: 2026-09-24}
  critic.md:
    kb: 20
    reason: "review protocol rules, and reviewers read this file every cycle"
```

Both the flow form and the nested form above are read. `kb` is an integer; `reason` is REQUIRED —
an entry without one is its own finding, because an unreasoned ceiling only ever rises and the
next author inherits a number with no argument behind it. Same `#`-truncation caveat as
`test_command:`, except inside quotes: quote any reason containing a `#`.

## operator_verification_required (opt-in, default false)

When true, `/prawduct:pr create` BLOCKS if `.prawduct/operator-verification.md` has any entry with
`**Status:** pending`. The queue records pre-merge human-verification items for visual /
live-integration changes that automated tests can't fully cover. Drain via
`prawduct-hook verify-operator-verification <VRF-id>` or override per-PR with
`/prawduct:pr create --accept-pending-verification "rationale"`. Default off — opt in by setting
`operator_verification_required: true`.

## review_round_budget (on by default, 6)

The most full review rounds one body of work may buy before `critic-begin` refuses another (exit
4). `verify-resolutions` is never refused and never counted — it is how a BLOCKING finding clears,
so a ceiling that ate it would strand findings with no command that resolves them.

The unit is the build-plan SCOPE, not the branch: a branch may carry two scopes (one would charge
the other), and on a trunk-based repo the merge-base span is zeroed by every push, so a
branch-counted rule could never fire. A dispatch that resolves no scope is not budgeted at all.

The scope's rounds are still bounded — the evidence store is shared by every worktree of the
clone, and holds the rounds other clones ran on this branch once their notes are ingested, so
something has to separate them. On a branch that is its lineage. Where the `base..HEAD`
span holds NO COMMITS, it is the worktree the rounds were recorded from, and on a trunk repo that
is the only reason the ceiling can fire at all.

Two consequences of that predicate, because it is about the SPAN and not about being a trunk repo:

- A branch cut and not yet committed to has an empty span too, so a branch RESUMING a scope that
  already ran rounds in this worktree inherits them. The budget's declared unit is the scope, so
  this is consistent — but it is a behaviour change on branch-based repos, not only trunk ones.
- Nothing resets the worktree count. On a branch, cutting a new one resets it; on trunk there is
  no cut, so REUSING a scope name for a second body of work inherits the first one's rounds and
  can refuse its very first dispatch (auto-accepting the OLD work's outstanding findings with it).
  Give each body of work its own scope name, or raise the budget.

At exhaustion the outstanding NON-blocking findings are auto-accepted with the budget as their
recorded reason and a census is rendered. BLOCKING is never swept: the budget can end a review
loop, never open a gate.

ON by default, at 6 — an off-by-default terminating rule is a mechanism that works and that nobody
knows exists. Six because it sits above every measured chain that ever produced a late BLOCKING
finding, while still catching the 20-to-34-round chains whose count is indefensible on any
reading.

Set to `null` to disable it entirely; raise it if this repo genuinely reviews more. A budget that
gets `--force`d past every time is a budget set wrong.

## oversized_file_threshold_kb, evidence_store_threshold_mb (opt-in overrides)

Size thresholds for two advisories, as positive integers. `oversized_file_threshold_kb` (default
40, where KB is 1000 bytes) is the size above which a governance file earns the oversized-file
nudge. `evidence_store_threshold_mb` (default 50) is the size above which the clone-shared
evidence store earns the oversized-evidence-store advisory; at 50 MB one read of the store takes
about half a second. Both fail soft: an absent key, or a value that is not a positive integer,
uses the default, so a typo cannot silence a nudge or make it fire everywhere. Raise one when the
advisory names it and the size is expected for this repo.

## api_versioning_decided (advisory resolution fact)

The committed "answer store" fact the `api-versioning` sync probe consults. When the product
exposes a programmatic interface (detected from the code — web framework, OpenAPI/proto), the
probe raises a dismissable, auto-resolving session advisory until a versioning decision is
recorded — here, or under design_decisions.api_versioning_approach; either one resolves it. This
is the short form: the decision summary (e.g. "uri-path-v1", "header", "none-internal-only",
"deferred:<revisit-trigger>"). Unset/absent = undecided. Recording "none-internal-only" resolves
it; this is NOT a mandate to version.

## Backlog keys (structured backlog resolution conditions)

The shared "answer store" (committed) that backlog sync probes consult to know whether a migration
nudge is still needed. The per-clone nag log lives in `.prawduct/.advisories.json`; these committed
facts auto-resolve a teammate's advisory on next sync.

- **`backlog_format_version`** — set to 2 once `/prawduct:backlog migrate` has converted items to
  the [PFX-XXXX] structured format. Unset (or absent) means legacy/unmigrated; the
  `legacy-backlog-format` probe may nudge.
- **`backlog_prefixes`** — OPTIONAL declared prefix vocabulary for /prawduct:backlog validation
  (e.g. [STH, CRT, SYN]). Emergent by default; declare only if you want validation.
- **`backlog_backend`** — set to `markdown` to declare that this product is staying on the
  markdown backlog PERMANENTLY: no GitHub remote, another forge, air-gapped, or an owner who does
  not want an Issues tracker. It resolves `backlog-service-migration-required` and NOTHING else —
  the format, schema and grooming nudges keep running, because a product staying on the file needs
  its hygiene more, not less. Absent means undecided, which is the default and keeps the migration
  nudge. `markdown` is the only defined value. Set it with
  `/prawduct:backlog decline-migration <reason>`, which records the reason as a comment directly
  above the field; unset it by deleting the line. An actual cutover (the backlog-service repo
  scalar, written by `scrub`) wins outright if both are set — having migrated beats declaring you
  never will.

- **`backlog_archive_scope`** — set to `open` by hand at cutover (beside `backlog_service_repo`)
  when the import ran with `--archive-scope open`, so the closed/archived items stayed off the
  tracker. Post-cutover `list` and add-time dedup cannot see them; the `backlog-archive-deferred`
  advisory (info) states that. Set it to `all` after a backfill, or delete it, to resolve.
  Absent means `all` or undecided; there is no other defined value.

Also read by the backlog probes:

- **`backlog_external_imports`** — list of external backlog files already audited via
  `/prawduct:backlog import` (resolves external-detected).
- **`backlog_last_groomed_at`** — ISO-8601 of the last /prawduct:backlog list|pick (resolves
  overdue-grooming).

```yaml
backlog_format_version:
backlog_backend:
backlog_prefixes: []
backlog_external_imports: []
backlog_last_groomed_at:
```
