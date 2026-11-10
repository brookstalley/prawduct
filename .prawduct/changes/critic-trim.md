---
schema: 1
type: feature
scope: critic-trim
date: 2026-11-10
title: The Critic stops relaying machine checks and null cross-check notes
closes: [brookstalley/prawduct#1128]
---
Over the 60 days measured in #1128, the Critic's mandated cross-checks were 23% of all findings
and produced one blocking finding, and 87% of the notes that were answered were accepted unfixed.
The owner ruled on 2026-11-10 to delete the model-relayed checks and notes-as-findings.

### Notes become observations at every stage (Chunk 01)

`critic-consolidate` refuses a finding rated `note` from any dispatch, with a message naming
`observations`, and accepts an `observations` array from a boundary (`cumulative`) dispatch as it
already did from an inner one. BLOCKING and WARNING ratings are unchanged, and a `blocking`
observation is still refused. Every protocol table that rated something NOTE now rates it an
observation. The NEXT-ACTION line, `review-cycle.md` and the protocol files stop asking the builder
to answer observations; `prawduct-hook disposition` still accepts an `O-n` id. Facts already
written keep their `note` findings, and `stats`, `review-stats`, `render-dispositions` and the
findings view still read and count them.

### The reviewer stops relaying and cross-checking (Chunk 02)

The Backlog Reconciliation (with its C-B1 to C-B4 hygiene checks), the Learnings Cross-Check and
the `priors:` acknowledgement leave the protocol, the coordinator roster and the reviewer agent,
along with the `backlog cache-query` and `learnings-files` grants that existed only for them.
`prior_dispositions` stays as reviewer input: a reviewer still does not re-raise an accepted
finding. The mandated NOTE listing the plan's mid-build decisions is removed and nothing replaces
it, because no reader of a plan's Goals section exists to print the list from.

Record-lint results used to reach a gate only through a reviewer restating them as findings;
the manifest's `record_lint` rode into the fact as data no gate reads. `critic-consolidate` now
records every result and `unchecked` entry in the review itself, at the severity
`record_lint.SEVERITY` assigns for the review's stage (`record_lint_partial`), so a blocking
record result blocks with no reviewer in the path. At the inner stage only `chunk-ref-missing`
stays a finding; a `verify-resolutions` pass carries only the findings. Results of one check at
one place become one entry listing every detail. A result identical to one already accepted or
filed (a WARNING), or already `waived` by a resolution (a BLOCKING one — the only answer the gate
takes for a blocker), is carried as an observation naming that answer instead of being raised
again. At the boundary an observation its reviewer rated `warning` is promoted into the findings.

### Every description agrees (Chunk 03)

`building.md`, `docs/norms.md`, `docs/governance-telemetry.md`, `skills/backlog/cache-reads.md`,
the PR protocol's statements about what the Critic owns, the end-of-cycle Stop nudge (which no
longer names a Learnings Cross-Check read list), the norm index and the cross-cutting registry
now describe the trimmed Critic. Backlog filing keeps Critic Goal 3 as its mechanism; nothing
replaces the backlog walk.

## Consumer note
Critic reviews get shorter. A reviewer no longer files backlog-reconciliation, learnings
cross-check or "priors" notes, or a note listing the plan's mid-build decisions, and nothing is
rated NOTE: what used to be a note arrives as an observation, which gates nothing and needs no
disposition, so the closing line no longer asks you to answer observations. Record-lint results
(a missing declared deliverable, a learnings file over budget, a `governed_by:` gap) now appear
in the review as findings or observations recorded by consolidation itself, at the severity the
lint assigns; a review whose plan has no gradable chunk section records a blocking finding for
the deliverable check that could not run. A record-lint warning you accepted or filed is not
raised again until the result changes. Reviews recorded before this change keep their notes.
