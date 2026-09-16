---
paths:
  - "tests/**"
---

# Learnings — tests

Rules that fire while writing or changing a test. **Reading a rule is not applying it.** Name the rule and say what it changes about the decision in front of you, or say that it does not apply.

<!-- Migrated from `.prawduct/learnings.md` in the v2 cutover merge (2026-09-15): these
     rules reached `develop` after the branch migrated its corpus, so they had no home in
     `core.md` and `core.md` had no headroom. Scoped here rather than appended there. -->

### A green read off a PIPELINE is the last stage's verdict, not the suite's — `pytest ... | tail` reports `tail`'s exit: 0 whether the run passed or failed. Redirect to a file and read the command's own `$?`. Tell: you called a baseline green from a piped run and never saw a count. It costs a cycle, because every later judgement rests on a baseline that certified nothing.

### A guard's TOLERANCES belong to the path it was written for — when you reuse one on a new path, port what it was PAIRED with or re-derive whether it still holds. What it deliberately lets through is invisible at the call site and reads as safe. Tell: you reused a `check_*` and wrote no transform beside it. Second instance on one seam is a signal about the seam

### To pin a DESIGN CONSTRAINT, mutate to the implementation it FORBIDS, not to something broken — the forbidden alternative usually agrees with the chosen one on every input a fixture can build, so the only discriminator is the degradation path it mis-handles: force that one and assert the verdict holds. Tell: you cannot name an input where the two implementations differ

`check-branch-pushed` (2026-09-12) shipped with a design constraint in its plan: the direction
between a branch and its upstream is decided by **ancestry**, never from the commit counts, which
serve the message only. Three mutations were run against it and all three went red — flipping the
equality, returning 1 where 3 was owed, swapping which ancestry answer was read — and none of them
measured the constraint. `git rev-list --count A..B` and `merge-base --is-ancestor` are computed
from the same graph, so a counts-based classifier returns the identical verdict on every repo a
fixture can build. The forbidden implementation was still available, and the review said so.

Where the two differ is the path a fixture cannot reach: a count that fails to resolve. The probe
degrades it to `"?"`, which a counts comparison reads as non-zero and calls `diverged`. The test
that pins the constraint therefore stubs `_rev_count` to `"?"` and asserts the verdict is still
`unpushed-commits` — one assertion, and the only one of the four that a counts classifier fails.

**The companion error, same session, one commit later.** A fix added *two* independently
falsifiable guards to one code path — an unconditional `rev-parse HEAD` probe (so a 128 from the
ref lookup means "no such branch" rather than "not a repository") and a separate branch for
`_git_text`'s `-1` (git could not be run at all). The mutation deleted **both at once**, one test
went red, and that read as coverage for the pair. The `-1` guard could be deleted with the suite
green, and a Critic found it BLOCKING. This is the sibling rule on mutating each conjunct
independently, arriving through a different door: two guards removed in one mutation is **one**
mutant, and it proves whichever guard the test happened to be about.

### A comment that NAMES a new failure mode owes a test in the same commit — write the sentence and you can write the assertion; unasserted, the comment reads as though the case were handled. Widening what an input may BE changes every branch consuming it: re-read the function, not the line. Tell: a comment describing a case, no test for it

Widening that same reader from `.match` to `.search`, I wrote the sentence "the cost is that a line
merely *discussing* the field parses as declaring it", judged it absorbed by the fail-open posture,
and shipped it. It was absorbed in the branch I was looking at and not in the fallback three lines
below, where first-sight return let prose bury a real declaration and report the loss as a typo —
strictly worse than the bug being fixed, because the original said nothing rather than something
misleading. The review caught it; the comment had already described it.

The general shape is that widening what an input may BE is never confined to the line you edit. Every
branch downstream of it now receives inputs it was written before. Re-read the function, not the
diff — and when a comment in that diff names a case, that sentence is a test specification someone
has already written for you.

### When a guard is about WHERE something may appear, assert the COUNT and scan from the end the PARSER reads — an assertion pointed at the other end finds the genuine structure sitting after the forgery and calls it clean. A marker test slicing `rindex(fence)` passed on a body whose FIRST opener had hijacked the parse. Tell: your guard says "first" and your test slices from the last

### Verify a chunk against the PLAN's deliverable list, not against the files you actually edited — the two diverge silently, because work concentrates in one file and "done" gets judged from what is in front of you rather than from what was owed. Tell: a Tests or Deliverables line naming more than one file, where the editing concentrated in one

**The instance (2026-08-25, plugin-absent-governance-anchor Chunk 01).** The chunk's Tests line named
two files: `tests/test_plugin_migrate.py` and `tests/test_plugin_init.py`. Three tests went into the
first, none into the second, and the chunk was declared to have met its acceptance criteria with a
full green suite behind it. The Critic found it.

**Why green said nothing.** `init_product` imports `apply_claude_anchor`, so the scaffold path was
in fact rendering the new anchor correctly — nothing was broken, and no test could have gone red.
What was missing was a test that *would* go red if that path ever stopped rendering it. Green is
evidence about what could have made it red, and no assertion reached this path at all.

**Why this particular omission bit harder than most.** The unpinned path was the scaffold one, and
the same plan's next chunk was a repair that converges *already-onboarded* repos. New onboards are
precisely the population that repair can never reach, so the untested path was the one with no
second line of defence behind it.

**Root cause, and it is not carelessness about testing.** Verification ran against *what had been
edited* rather than against *what the plan said was owed*. The plan is the checklist, and it was not
re-read at the step that exists to check it — the "acceptance criteria met" step. The tell is
mechanical and available before the work starts: a Tests or Deliverables line naming more than one
file, where the editing will naturally concentrate in one of them.

### A CLASS finding closed at the site where it was NOTICED is not closed — fix every site it names AND check a test fails for each, because fixing both while pinning one lets the other be deleted green. Tell: your fix cites a finding saying "two owners" / "every row" / "both writers", and touches or tests one

**Two instances in one verify round (2026-08-25, plugin-absent-governance-anchor).** Both findings
said, in their own text, that they covered more than one site. Both were fixed at one.

* **R-12 (blocking)** named two owners: `anchor_repair.repair`'s swap branch, and
  `migrate_plugin.apply_claude_anchor`'s writes *"that the `absent` branch delegates to"*. The fix
  wrapped the swap. `repair()`'s `absent` branch calls `apply_claude_anchor` outside that `try`, and
  `core.atomic_write_text`'s contract is explicitly that OSErrors propagate to the caller — so an
  unwritable `CLAUDE.md` still raised `PermissionError` out of a doctor session. Worse than a random
  miss: `absent` is the status Health Check #4 *advertises* ("the repair inserts one"), so the branch
  left unguarded was the advertised one.
* **R-4 (warning)** asked that *every* `--json` row be checked. Only the row it named was fixed, and
  the sibling row went on claiming a JSON consumer that parses nothing.

**Why the tests did not catch either.** The new test for R-12 used a `stale` fixture, because that
was the branch being fixed — so it exercised the guarded path and asserted the guard worked. A test
written from the fix inherits the fix's blind spot; parametrizing it over both writing branches is
what closes that, and it is the same shape as "tests written from the same mental model inherit its
blind spot".

**A fourth instance, and a sharper sub-shape: the CODE was fixed at both sites and only one was
PINNED.** `repair`'s success report was corrected on both write branches, but both new assertions
started from a `stale` fixture — so deleting the `absent` branch's two success lines shipped green,
reinstating the defect on the one status Health Check #4 advertises as repairable. The test file had
*already learned this shape one round earlier*: `test_an_unwritable_claude_md_is_reported_not_raised`
is parametrized over these same two branches for exactly this reason, and the next test written
against those same branches was not.

So the rule has two halves, and the second is the one that keeps recurring: **fix every site the
finding names, then check that a test fails for each of them.** A fix verified only where it was
noticed is a fix that can be deleted anywhere else.

**Root cause.** Reading a finding for *what to change* rather than for *what it says is in scope*.
The severity and the recommendation get read; the sentence enumerating the owners is skimmed,
because by then the fix already feels identified. The cheap counter is mechanical: before committing
a fix, re-read the finding's own text and list the sites it names — the words are right there
("two owners", "every row", "both writers", "re-sweep all three").

**A second, smaller lesson from the same round.** The verify review's `NEXT-ACTION` line said "0
blocking, 0 findings — THE REVIEW IS OVER" while its own body said R-12 survived. The body was
right, and it took three lines of running the code to confirm. A summary line is not evidence about
the analysis above it; when they disagree, the specific and checkable half wins.

### When a fix NARROWS a detector, the verification set must contain the TRUE POSITIVES it exists to catch, not only the false alarms you narrowed it to stop — suppressing a real detection and removing a false one read identically at the call site: zero findings. Tell: every shape you tested is one you were told was legal

### When every test INJECTS a dependency, green says nothing about how production OBTAINS it — drive a new consumer of an existing seam once with nothing injected, asserting the seam gets BUILT, because injection makes the acquisition path untested by construction. Tell: you threaded a dependency parameter through a new arm without asking who supplies it outside the tests

**From:** upstream-filing-adapter Chunk 02 (2026-09-06), Critic finding R-1, BLOCKING.

`plugin/lib/backlog/cli.py`'s `_run_file_upstream` began life as the preview arm, whose defining
property — stated in its docstring and asserted by the contract test — was that it takes **no**
`transport`, so it cannot reach the network. Chunk 02 extended it into a send arm that needs one and
threaded the parameter down from `run`. Every one of the seventeen sibling handlers calls
`_resolve_transport(transport)` on its first line; this one did not, because the question "who
supplies this in production?" never came up: `run`'s signature has `transport=None`, and every test
in the suite passes a `FakeGitHub` or a `MagicMock`.

Production enters at `plugin/bin/prawduct-hook` via `backlog_cli.run(project_dir, argv)` with no
transport kwarg. So `None` travelled into `upstream.send`, which called
`transport.get_authenticated_user()` and raised `AttributeError`. `run`'s CLI-boundary broad-except
turned that into `core.error("unavailable", …)` at exit 6 — a code whose contract says *retryable*.
The chunk's entire deliverable was non-functional for every real caller, and the failure presented
as a transient GitHub outage that a caller would retry three times before giving up.

Nothing was sent (checks 1–4 pass before the transport is touched), so this was non-function rather
than a safety hole. But the suite was green over it, and would have stayed green through the PR
gate: dependency injection at every call site makes the *acquisition* path untested by construction.

**The remedy is two tests, not one.** Drive the new arm through `cli.run` with no transport and
assert the seam is constructed (monkeypatch the module's `GhTransport`); and drive the arm that must
NOT build one and assert construction never happens. The second is what forces the resolution to sit
inside the send branch rather than at the top of the handler where the siblings put it — at the top
it would build a `GhTransport` on the preview path, dissolving the scope guarantee that is the
preview arm's whole point. Both mutations were verified: moving the call to the handler top fails the
preview test, removing it fails the send test.

Related: [[a-fixtures-world-is-narrower-than-the-requirement-it-certifies]].

### Defence in depth costs a test PER LAYER, not per rule — an outer pre-check short-circuits every call routed through it, so the inner copy of the same check is a mutation survivor that reads as covered; each layer needs a test entering at its own door. Tell: you skipped mutation-checking a rule because an earlier chunk verified it — on a different arm

### A fix that replaces a visible placeholder with something that READS as working code can be worse than the gap it closed — an agent skill's shell state does not survive between tool calls, so a variable assigned in one block is empty in the next and every downstream guard sees well-formed-but-empty input. `<scratch>` demanded substitution; `"$SCRATCH"` looked correct and would have filed an empty issue into a repo with no delete. Pin the dangerous half, not the instructive prose, and give the pin a positive control. Tell: your fix makes an instruction look executable that previously looked like a blank to fill

### A test that pins the ARITHMETIC does not pin the CALL — when a guard's value comes from a narrowing call at its call site, the test must enter at that site with an input the narrowed and un-narrowed forms answer DIFFERENTLY, or the call can be deleted with the suite green. A comment claimed a widening bound was "pinned by" a class that only exercised the predicates on hand-built lists, and the one dispatch-level test used paths BOTH predicates excluded, so removing the narrowing failed open — a partial re-review where a full one was owed — with nothing red. Tell: you are writing "pinned by <TestClass>" about a call site, and that class never invokes the function containing it

### An explanation is falsified by a case where its stated cause is ABSENT and the behaviour survives — when a comment says "X still matches because Y", the test set must contain an X without Y, or your own suite is green under both the true mechanism and your wrong one. I narrowed a prose guard and wrote that ``the `Closes #N` keyword`` escaped the exclusion "because the character before `Closes` is a backtick rather than a space". False: the exclusion sat only on the participle alternation, so `the Closes #N` — no backticks — had always matched. Every positive case I wrote carried backticks or lacked a determiner, so all of them passed identically under the real rule and the invented one, and green meant nothing. A reviewer found it in one probe. The behaviour was right both times; only the stated reason was wrong, and the stated reason is what the next author edits against. Tell: your comment attributes survival to a feature of the input, and no test varies that feature alone

`origin/develop` was red: a requirements document wrote "adjacent to the closed #422" and the
closing-keyword guard read the participle as an instruction to GitHub. Repairing the classifier
rather than reflowing the prose was correct, and the first cut worked — every case I probed
returned the right answer.

The comment explaining it did not. It said the backticked ``the `Closes #N` keyword`` survived the
new determiner exclusion because the character immediately before `Closes` is a backtick rather
than a space. The lookbehinds were `(?<!\bthe )(?<!\ba )(?<!\ban )` attached ONLY to the
`closed|fixed|resolved` alternation, so `Closes` was never eligible for exclusion at all — with or
without backticks. `the Closes #N` matched, and always would have.

**Why the suite could not catch it.** My must-match list held `Closes #123`, `Fixes #7`,
``a `Closes #N` line``, ``the `Closes #N` keyword``. Every entry either had no determiner in front
(so the exclusion was irrelevant) or had one with a backtick between (so both explanations predicted
a match). The discriminating case — a determiner, no backtick, non-participle form — was the one
case my false model told me was already covered. A wrong explanation does not merely fail to be
tested; it actively suppresses the test that would falsify it, because the test looks redundant
from inside the wrong model.

The same commit carried a second instance in milder form: the rule was stated as "a determiner
before a past-participle form" while the code implemented three articles plus one literal space, so
`this closed #422`, `every closed #422` and — in a repo that hard-wraps at ~100 columns — a
line-broken `the\nclosed #422` all still matched. The triggering sentence had tripped the guard only
because both words happened to land on one line, which means the narrow version would have returned
as the same red under a different wrap.

**The repair that holds.** Lookbehinds gave way to a named predicate (`names_closing_keyword`) whose
determiner set and whitespace handling are readable and extensible, and the must-match list gained
`the Closes #N keyword` (no backticks) and `was closed #422` — the two cases that discriminate
between the real rule and the plausible wrong ones. Related: the docstring-as-assertion rule and
"a correct decision defended by an unread mechanism is still a defect" — this is their test-design
consequence, and the sharpest tell is that behaviour was correct throughout, so nothing but the
prose was ever wrong.

### Proving a new guard can go red is half the question — ask whether each ASSERTION discriminates the two outcomes it names, because a substring check over a formatted message, or a fixture that never reaches the new branch, passes identically either way. Mutation grades lines you added, not paths you never enter. Tell: every test on the new path shares one fixture

### When test evidence is stale, run the suite THROUGH `prawduct-hook test-evidence record` rather than running it bare and recording the counts after — because a repo that declares a `test_command:` emitting JUnit refuses both `--from-counts` (it wants the machine-readable report, not your transcription) and `--no-rerun`, so a bare `pytest` run buys nothing and the suite runs twice. Two five-minute runs at a PR boundary, for the same green. Tell: you just read `stale:` from `test-status` and your next thought is the pytest command you already know

**2026-09-12, PR #807 (`branch-pushed-gate`).** `/prawduct:pr` Step 1 says to check
`prawduct-hook test-status` first and only run the suite if it reports `stale`. It reported stale, and
the obvious next move — `python3 -m pytest tests/ -q` — was the wrong one. Five minutes later the
suite was green and the evidence was still stale, because recording it is a separate step with its
own constraints:

- `test-evidence record --from-counts passed=N failed=M skipped=K` is **refused** on any repo that
  declares `test_command:`/`test_commands:`. The declared command emits JUnit, so the recorder wants
  the report; hand-transcribed counts are exactly the unbacked evidence it exists to prevent.
- `--from-counts` and `--no-rerun` are also mutually exclusive with each other, so there is no
  combination that launders a bare run into evidence.

The supported paths are `test-evidence record` with no flags (it runs the declared command itself,
substituting `{junit_xml}`), or running the declared command by hand *with* `--junit-xml` and
ingesting the report with `--from-junit`. Either way the JUnit report is the artifact; a green
transcript is not.

The cost was one wasted five-minute suite run at a PR boundary. The generalisable shape: when a
governance step names a hook that produces an artifact, the hook is the entry point, not a
formality wrapped around a command you would have run anyway. Reaching for the familiar raw command
first means the hook has to either re-run it or reject what you brought back.
