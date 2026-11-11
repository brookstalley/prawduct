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

`skills/critic/review-protocol.md` Goal 7 gains **Read cost**: a read costs what its caller uses,
not the size of what it reads from. It is stated as that property rather than as a list of
database rules, so it covers a file read whole for one line or a remote list filtered after the
fetch as readily as a missing index. It rates WARNING at most: where the stated volume makes the
cost one somebody meets, or where no volume is stated and the read runs per request, item or tick
over a collection that plainly grows with use. Anything else is an observation. The reviewer runs nothing, so it names
the shape and the measurement that would settle it, never a figure. It is a Goal 7 check: `final`
and `cumulative` reviews run it, `chunk` reviews do not, and at the inner stage it is an
observation.

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

So the branch is held unmerged, by the rule set before the replicates ran (the owner's ruling of
the same day asked for them before merging). What it waits on is a version of the check that
keeps the old protocol's catch rate on that defect, tested the same way, or a decision to drop
the check. The fixture, the eleven result files and the steps to rebuild a run are kept on the
owner's machine in `.prawduct/.read-cost-test-2026-11-11/`, outside git.

## Consumer note
`final` and `cumulative` Critic reviews now look at what a changed read costs: a lookup that walks
a growing collection for want of a key, index or bound, whole records or heavy fields fetched
where a few values are used, and one read per item where one would serve. Such a verdict's title
opens `read-cost:`. It is a warning at most — where your data model or non-functional
requirements state a volume that makes the cost real, or where they state none and the read runs on
every request, item or tick over a collection that plainly grows — and it never blocks. If your data model
says nothing about volume for a store that grows, expect an observation pointing you to the
data-model template's new Access Paths section — expected volume, how each frequent read finds its
records, and which fields are heavy. Adding that section is optional and nothing checks for it.
