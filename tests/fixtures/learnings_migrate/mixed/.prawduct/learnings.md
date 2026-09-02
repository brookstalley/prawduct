# Learnings

Concise rules from 15+ build sessions. See `learnings-detail.md` for root cause analysis and demoted rules.

## Pydantic v2
- **No `@dataclass` at boundaries.** Anything crossing API/IPC/storage must be Pydantic. Grep periodically.
- **Whitespace-significant fields use plain `BaseModel`.** `DiscodonBaseModel` sets `str_strip_whitespace=True` — wrong for prompts/rendered content.
- **Every `*_simple` serializer round-trips through its source model.** When a presenter has both `_info` (display) and `_simple` (clone/eval), `_simple` is consumed by `Model(**data)`; missing required fields fail at construction. Pin every new `_simple` with a round-trip test. Three repeats in 2026-04 (Goal/NarrativeWisdom/TodoItem `created_turn`).
<!-- Pruned 2026-05-01: "raw strings for str,Enum fields" rule. Structurally enforced
     by tests/unit/test_enum_compliance.py — the AST canary scans production code for
     two budget functions (record_turn_cost, record_cost) on two param names (source,
     category). The original learning was phrased generically; if the canary's scope
     is extended to additional enum-typed parameters, the rule is fully retired. -->

## ZMQ & Multi-Process
- Never call blocking ZMQ ops in `__del__` — deadlocks during GC.
- Force `async_mode=False` for sync callers in async context.
- PUB sockets need 0.5s settle delay after `connect()`.
- **`os.register_at_fork(after_in_child=...)` callbacks must do MINIMAL work — no SDK init, no lock-using imports, no new threads.** The callback runs synchronously inside the fork syscall with parent locks inherited in held state. Calling into a complex SDK that uses locks (e.g. [detail](learnings-detail.md#osregister-at-forkafter-in-child-callbacks-must-do-minimal-w)

- **When you enumerate "the other sites" after fixing one, record the *shape of the search* beside the list — an absence-claim is only as strong as its search, and a bare list fails by stopping the next person looking.** Detail: [ZMQ & Multi-Process Details](learnings-detail.md#zmq--multi-process-details).


## Eval & Model Bake-offs
- **A probe that returns the expected answer for the WRONG reason is indistinguishable from confirmation — make it show the mechanism working, not just the absence you predicted.** #2346 recorded "standalone `web_search` credits are never counted" and cited a run showing no external spend. The spend was absent because the eval slot never STARTED the tool, so no Tavily call happened at all; the accounting gap was real in source and unreachable in practice. Four rounds carried that evidence. The tell was available the whole time: nobody had asked the probe to prove the search SUCCEEDED, only that the number was zero. When a probe confirms a predicted absence, demand one positive observation of the path actually running before believing the diagnosis. (eval prod-readiness round Part B, 2026-08-19; `DEFECT-B1`.)
- **An acceptance criterion states the property the output must HAVE, never the conclusion you expect it to REACH.** Chunk 03 of the metric-scope plan required "the fanout verdict reverses or is withdrawn". [detail](learnings-detail.md#an-acceptance-criterion-states-the-property-the-output-must)
- **When reading LLM-judge output in an eval, verify the verdict against the actual transcript before trusting it — judges hallucinate.** One judge labeled a correct, tool-grounded answer a "fabrication" while simultaneously scoring its own grounding=5, contradicting itself. Treat all outcome/judge scores as untrusted until judge calibration lands; a ranking must not rest on them. (research-model bake-off, 2026-07-25; bug `EVL-H8NR`.)
- **When a metric is a coin-flip (high-variance), treat n=1 as noise — a single-cell "win" routinely reverses at k=2.** Confirm any difference at k≥2-3 before believing it. [detail](learnings-detail.md#when-a-metric-is-a-coin-flip-high-variance-treat-n1-as-noise)
- **A "measurement is broken" fix must check whether the SUBJECT is broken too.** When a capture/serialisation seam is implicated, trace it in BOTH directions — what reads it, and what is BUILT from it. (2026-07-30, eval-judge-persona-context; detail in learnings-detail.md.)
- **When recovering "all fields of class X", take membership from where the code GROUPS X, not from a flat list**, and state the count out loud so it is falsifiable. (2026-07-30; detail in learnings-detail.md.)
- **A fallback is camouflage for the thing it falls back from** — `x or "(none)"` makes a defect look like handled absence, which is the no-fallbacks rule from the other direction. (2026-07-30; detail in learnings-detail.md.)
- **A figure that LEADS a report needs a test more than the one beside it.** The production-replicating *mean* became the run index's headline cost and shipped with no assertion anywhere, while the subset-style key check in the generator test stayed green through its removal. (2026-08-11.) [detail](learnings-detail.md#a-figure-that-leads-a-report-needs-a-test-more-than-the-one)

## Music / Streaming
- yt-dlp downloads to local temp files — direct URL streaming unreliable.
- Reset transient state on disconnect events (e.g., listener count).
- Subprocess: redirect stderr to log file, not PIPE (deadlock) or DEVNULL (lost output).
- Last-one-wins event deduplication for budget-friendly perception.

## The chart palette never refuses to draw (`EVAL_REPORTS.md` § *The palette never refuses to draw*) — slots 1-4 validated, 5-8 a derived tier, past 8 it recycles; series count is a property of the DATA. What makes the weaker separation honest: **a direct label on every mark from five series up**. Prefer an axis anyway — a sorted bar has no ceiling. → detail.

## Never hand-convert design tokens into a renderer's palette — `npm run tokens` emits the resolved hexes and is the same conversion the server-side renderer reads, so a hand-conversion is a second source of truth with nothing gating the drift. → detail.

## When you add a field that TELLS a reader what the code did, derive it from the same predicate the code branched on, never from an observable that merely correlates — a correlate is right on the fixtures you happen to have and wrong on the case the field exists for, and the pin must use the shape where the correlation breaks (2026-08-02, eval `cohort_scope`)

## A correction is not done when the code is right — grep every prose site describing the rule you changed, the CONSUMER's copy included, because a prompt still teaching the old contract makes the system misbehave with correct code (2026-08-02, eval `cohort_scope`)

## Grep the CONCEPT, not the sentence you just fixed — a rule's copies are paraphrases, so searching the wording you edited finds duplicates and never synonyms; sweep an alternation of phrasings across every file type, then classify each hit live-vs-record, and never write "swept" in a change-log — say what was fixed and what was left (2026-08-07, host-stage ruling)
<!-- prawduct-learning: id=LRN-8842 promoted=2026-08-07 source=host-stage-ruling -->

## Read what a count's own docstring claims, and name every branch that increments it, before multiplying it by money — and fix at the counting site (2026-08-02, eval chunk 12)

## When a fix touches a claim living in several artifacts, rank the copies by LIFESPAN and fix the longest-lived FIRST — the ephemeral copies are already in front of you and the durable one you must go find, so fixing them in the order they come to hand leaves the survivor asserting the wrong thing (2026-08-02, eval chunk 12P)

## A correct action with a fabricated mechanism is worse than no comment, and no test can see it — when you write "because <mechanism>", open the mechanism, because right placement keeps every gate green while the comment teaches the next reader a false model (2026-08-02, eval chunk 12P)

## Before trusting a decomposition, establish that its inputs are the population you think they are — a partition over the wrong population is a precise number about nothing (2026-08-02, eval chunk 13)

## A discriminator built from loop coordinates is only as unique as the loop — when you need "this execution", mint a nonce, because `(run_id, test_case_id)` looked like a cell id and every k × model sibling carried it (2026-08-02, eval chunk 13)
