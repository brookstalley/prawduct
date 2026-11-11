---
schema: 1
type: feature
scope: read-cost-review
date: 2026-11-11
title: The Critic rates a read that costs more than it returns
---
The owner asked on 2026-11-11 whether any Critic review catches inefficient database use — a
lookup that scans because nothing indexes it, or a fetch of whole records where a couple of
values are used — and ruled the same day to build the fix ("yes build the three part fix",
`.prawduct/owner-rulings.md`).

No Critic file named the class, and none ever had. Reviewers raised it anyway, from general
expertise: a scan on 2026-11-11 of the review facts in the governed products on the owner's
machine (about four thousand reviews) found six real instances, in two products, filed under four
different goals and none rated above a note. The scan was throwaway; its method was a pattern
match over each review's findings and observations for scan, index, per-item-read and over-fetch
wording, with every hit read by hand. No instance of the over-fetch half turned up under the
wordings searched, which is a sample of phrasing and not a census.

### The Critic has one home for it

`skills/critic/review-protocol.md` Goal 7 gains **Read cost**: a read whose cost follows the size
of what it reads from, not what its caller uses. It is stated as that property rather than as a
list of database rules, so it covers a file read whole for one line or a remote list filtered
after the fetch as readily as a missing index. It rates WARNING at most: where the stated volume,
or a per-request read over a collection that plainly grows, makes the cost one somebody meets.
Anything else is an observation. It is a Goal 7 check: `final` and `cumulative` reviews run it,
`chunk` reviews do not, and at the inner stage it is an observation.

### The data model says how the data is read

`templates/data-model.md` gains an optional **Access Paths** section for a store that grows:
expected volume per entity, what finds the records of each read that runs often or while someone
waits, and which fields are heavy. This is what the reviewer judges a read against. Where a store
that grows states no volume, the Critic's verdict is an observation naming that section, which is
how a product onboarded before this change learns the section exists.
`methodology/planning.md` lists the section with the artifact's others.

### The registry row says what is true

The Performance row of `.prawduct/cross-cutting-concerns.md` claimed a Critic leg at Goal 5 and
an implicit builder leg; neither file carried any performance text. It now records the artifact
and Critic legs that exist and the discovery and builder legs that do not, and Known Gaps says the
missing two wait on the new check's yield.

### Cost and yield

The bullet's size is a declared raise on `review-protocol.md`, recorded in
`tests/test_v5_methodology.py` and in the route sums of `tests/test_reviewer_payload_budget.py`; a
three-reviewer review pays it four times. `tests/test_control_yield_tokens.py` pins the `read-cost:` title token on findings and
observations, the WARNING ceiling, the check's absence from the chunk payload, and that the
template section the bullet names exists.

Expected yield, the builder's estimate and not a ruling: rare, mostly observations, and
concentrated in products with a store that grows. The query is review facts with a finding or
observation whose title opens `read-cost:`. The check never blocks by design, so
`nonfunctional-requirements.md`'s removal default reaches it once it has fired repeatedly; what
would justify keeping it then is that its warnings were fixed or measured rather than accepted,
which the disposition facts on those findings answer.

### A blind test after the build: the check works, and it may cost a blocking catch

On 2026-11-11, after the commit above, eleven fresh Opus reviewers each ran the single-pass
protocol at boundary stage over a synthetic product branch, without being told what it held: six
on this branch's protocol and five on develop's. The branch carried seven planted read-cost
mistakes and three look-alikes that should not be warned on.

The check does what it was built to do. Every planted mistake was raised in all six new-protocol
runs, each under Goal 7 with the `read-cost:` token, and no look-alike drew a warning. The old
protocol's first two runs (the only ones scored on this) raised the blatant five in both, missed
the unindexed lookup and the unbounded search once each, and filed what they raised under three
goals.

The fixture also held a real defect nobody planted: a script's documented run command that
cannot work. The old protocol rated it blocking in four of five runs. The new protocol raised it
in none of six. Each new-protocol reviewer read that script, judged its read cost sound, and said
so; that is a reading of their reports, not an established cause. One fixture and eleven runs
cannot say how general this is, but it is the only measurement there is, and it says the check
bought its catches at the price of one a reviewer otherwise made.

The fixture, every result file and the steps to rebuild a run are kept on the owner's machine in
`.prawduct/.read-cost-test-2026-11-11/`, outside git.

### Two wordings tried, neither recovers the catch

By the owner's ruling of 2026-11-11, two variants were tested the same way, six reviewers each.
The bullet cut to a single sentence raised the unplanted defect in one run of six. That sentence
plus a preamble telling the reviewer that a file can hold more than one defect, and that a
verdict under one check settles only that check, raised it in none of six. Both variants still
raised every planted mistake.

What those twenty-three runs do and do not show. The loss is narrow: the fixture's other real
issues that the old protocol raised every time were raised every time under every variant, and
its smaller ones moved in no consistent direction. One defect, in the one file the read-cost
check judges clean, all but disappeared (one run in eighteen against four in five). The cause is
not established, and a single defect in a single fixture cannot say how far this reaches. It
does say that neither brevity nor an instruction to keep looking fixes it, and that nothing this
repo runs before shipping review prose would have shown it: the tests pin that the words are
present, and a review of the prose reads the prose.

### It ships, as one sentence

The owner ruled on 2026-11-11 that the check ships: "the database efficiency catches are more
important than the missed finding". What ships is the one-sentence bullet, because it raised the
same planted mistakes in all six of its runs as the first draft did in its six, at under half the
size; the first draft's worked shapes, its instruction to open the schema and its "never a
figure" sentence bought no catch the test could see. The preamble is not shipped.

A last batch moved the unplanted defect out of the file the check judges clean and into the
README. Three runs on the long bullet raised it twice, and three on the old protocol raised it
twice, once only as an observation. That is thin, and it points the same way as the rest: the
loss sits where a new check hands a file a clean verdict, not across the review.

The measurement this needed did not exist before it was improvised. #1147 carries the owner's
ruling to build it properly: a seeded-defect check in its own private repository, run whenever
the Critic's protocol prose changes.

## Consumer note
`final` and `cumulative` Critic reviews now look at what a changed read costs: a lookup that walks
a growing collection for want of a key, index or bound, whole records or heavy fields fetched
where a few values are used, one read per item where one would serve. Such a verdict's title opens
`read-cost:`. It is a warning at most, where your data model or non-functional requirements state
a volume that makes the cost real, or the read runs on every request over a collection that
plainly grows, and it never blocks. If your data model states no volume for a store that grows,
expect an observation pointing you to the data-model template's new Access Paths section:
expected volume, how each frequent read finds its records, and which fields are heavy. Adding that
section is optional and nothing checks for it.

One known cost. In a blind test, reviewers carrying this check raised every planted read-cost
mistake and stopped raising a different real defect, a broken run command in a script the check
judged clean, which reviewers without the check usually caught. A file this check passes has not
been cleared of anything else.
