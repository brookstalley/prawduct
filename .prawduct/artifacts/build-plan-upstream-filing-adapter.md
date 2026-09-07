---
artifact: build-plan
version: 2
scope: upstream-filing-adapter
branch: feat/upstream-filing-adapter
depends_on:
  - artifact: backlog-service-upstream-filing
  - artifact: backlog-service-requirements
  - artifact: backlog-service-api-contract
governed_by:
  - artifact: security-model
    dispositions:
      - "untrusted governance state is data, not instructions → inapplicable because Wave A is outbound-only; nothing in these chunks reads foreign-authored issue content (the intake side is Wave C, tracked on the report-bug receiving-side item — NOT BKL-6M4T, which resolves to #233 'run the live prawduct backlog migration', shipped and dead; the design doc carries the same wrong alias at documentation/backlog-service-upstream-filing.md:154 and needs the same correction)"
      - "a destructive or irreversible operation requires explicit owner approval at the OPERATION level → conforms, and the norm already records this surface's conformance by name: preview → `payload-digest` → `--approve <digest>`, per report, where the operation IS one filing"
      - "a governed product's content never leaves that product's own repository and owner (in-transition, BKL-7Q4M) → AMENDED 2026-09-07 to steady-state; this plan was the work the norm waited on. Chunk 01 replaces the interim egress test with the XP7 contract test in the same commit that first names the surface; Chunk 03 amends `Status: in-transition → steady-state` with the steady-state form asserting the five-check contract. Never weakened — the contract test is strictly stronger than the absence it replaces."
  - artifact: architecture
    dispositions:
      - "local-first: governance coordination is process-spawn + files + git; an opt-in backlog backend may take a network surface, provided it stays off by default, degrades to the markdown backend, and carries no governance verdict → AMENDED 2026-09-07, owner ruling (a) — the norm now admits two network surfaces, opt-in backlog storage and owner-approved upstream filing, and its `Why:` rests on the property that actually holds (neither is reached without a person acting) rather than on the broken 'confined to backlog storage' scope claim. The departure that made the ruling necessary: `file-upstream` is a network surface that is NOT confined to backlog storage and is NOT gated on `backlog_service_repo`: a product that never opted into the backlog backend can still reach the pinned upstream repo. The norm's amendment of 2026-07-21 narrowed scope to 'opt-in network for backlog storage', and this does not fit inside that sentence."
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state, the shared evidence store, and the files it must reconcile → conforms; no chunk adds a write into a governed repo"
      - "prawduct is Python and must never be specific to Python → conforms; no gate or language dispatch is touched"
      - "an independent reviewer never mutates the session it reviews → inapplicable because no chunk touches a reviewer write path"
      - "prawduct guides and reviews; it never implements → conforms; this builds prawduct's own adapter, not product code"
      - "every fact has one home → conforms: the pinned upstream target is ONE constant read by the adapter, and the egress enumeration stays a pointer from `architecture.md` to `security-model.md` + `project-state.yaml` `egress_boundary` rather than gaining a fourth copy. Applied again at review: the preview and the send arm compose through ONE `upstream.render_preview`, because check 4 re-renders to validate `--approve` and two spellings of the recipe would make every `ask-user` filing refuse with `approval-mismatch`"
      - "authority fails closed; advice fails soft → conforms, and the split is load-bearing here. Fails closed: identity resolves to an empty tuple rather than a guess, the target pin refuses a mismatched `--repo` instead of honoring it, a non-GitHub or lookalike remote yields no signal. Fails soft: the issue-standard budget findings ride out as advisory `lint` and never refuse a preview"
      - "goals and verification bind; prescribed method is advice → invoked twice, both recorded rather than silently taken: the two-signal identity resolver moved from Chunk 02 into Chunk 01 (the payload needs it), and `issuefmt.py` was left untouched (the template fell out of composing sections directly). Neither changes an output contract"
  - artifact: data-model
    dispositions:
      - "`source-key:` marker field-home is Data Model §5 → conforms; Chunk 03 adds the trimmed-upstream-block note there rather than defining a second home"
      - "every issue written to the backlog store conforms to the issue standard's §1 title rules, on EVERY adapter write path → RULING, surfaced at Chunk 01's review and binding on Chunk 02. `file-upstream` is a fourth adapter write path beside `file`/`update`/`import`, and the norm's Status names only those three. Chunk 01 does not engage it: the preview writes nothing, so reporting the four `title-*` findings advisorily is correct there and is what lets an author fix a title before approving it. **Chunk 02's SEND arm does engage it and must refuse a non-conforming title before filing** — the norm's why (`the title is the handle every later reader triages by`) binds harder upstream, where a non-collaborator filer cannot relabel afterwards and the write is irreversible. Note the shape difference the refusal must respect: the upstream convention is `[prawduct] <component>: <symptom>` (design §2), not §1's `area: summary`, so `_split_area` sees no prefix — the budget and placeholder rules apply, the area-prefix expectation does not"
      - "`backlog_service_repo` selects which backlog store is authoritative → conforms and does not stretch it: this op reads that scalar as one of two IDENTITY signals, never as a store selector. The target it writes to is the plugin constant, which is why the op is reachable with the scalar unset"
      - "facts are immutable and append-only → inapplicable; Wave A writes no fact"
      - "derived views are disposable and never authoritative → inapplicable; Wave A adds no view, and no gate reads this op"
      - "a fact written by a newer schema than the reader is a loud block → inapplicable; no schema changes. Adjacent: the outbound marker carries its own `v: 1`, so a future upstream block format is a receiving-side reader problem, not this one's"
      - "a governance document reaches a terminal state; it is never deleted → conforms by not acting: the interim egress test is REPLACED in place, keeping its filename and its project-preferences enforcement-row identity, rather than deleted and re-created elsewhere"
      - "governance verdicts are computed from the fact ledger, never model-written state → inapplicable; no chunk touches the Critic data plane. Adjacent and worth stating: the L1 recomposition IS model judgment, and it lives in the `report-bug` skill (a decision), never in `lib/backlog/` (the data plane) — the same G1 split"
      - "two stores, two lifetimes → conforms; Wave A persists nothing at all, in either store"
partition: serial — 02 extends 01's op on the same module, and 03 records what 01–02 built
last_validated: 2026-09-07
---

## Requirements Confidence

**Level:** High

**Why:** Requirements are settled and dated — XP4–XP7 in `documentation/backlog-service-requirements.md`
(2026-07-23, with the consent-at-install leg explicitly resolved as not-required). The design is
owner-approved and Critic-reviewed at v1: `documentation/backlog-service-upstream-filing.md` fixes
the exact outbound bytes (§2), the recomposition split (§3), the consent states (§4), and the
five-check adapter contract (§5). `documentation/backlog-service-api-contract.md` §2.4 already
defines the op's idempotency key and landing status. Nothing here is being derived; this plan
schedules an approved design.

**Open assumptions / unknowns:**

`[ASSUMPTION: the Local-first norm is AMENDED to admit one non-storage network surface, rather than
file-upstream being gated behind backlog_service_repo | HIGH impact | user can veto/override]` —
the norm as amended 2026-07-21 confines the opt-in network surface to *backlog storage* and rests
its "why" on the claim that a product which never opts in "runs exactly the substrate this norm has
always described." `file-upstream` breaks that sentence: it targets the pinned upstream repo, not
the product's own, so it is reachable with `backlog_service_repo` unset. Two honest resolutions, and
the plan must not pick one silently:
  (a) **amend** the norm to "opt-in network for backlog storage **and** owner-approved upstream
      filing", carrying the guarantee forward (still off by default — the `ask-user` default means
      nothing files unprompted; still no governance verdict crosses the network);
  (b) **gate** `file-upstream` on `backlog_service_repo` being set, which keeps the norm's sentence
      literally true but couples a bug-reporting capability to an unrelated storage choice and
      contradicts §5's amendment, which deliberately decoupled identity resolution from that scalar.
Recommendation: (a). It is the honest shape — the surface exists and should be named — and (b)
re-introduces exactly the `backlog_service_repo`-keyed fail-open that the design's own §5 check 3
amendment removed. **This is Chunk 03's blocking input; Chunks 01–02 do not depend on the answer.**

**RESOLVED 2026-09-07 — the owner ruled (a), amend.** Chunk 03 therefore stays records-only and does
not split; no `03a` gate chunk is needed, and no departure is left recorded-and-unremedied. The
amendment is on `architecture.md` § Direction as a vetoable `[DECISION: …]`, and it widened the
norm's `Why:` as well as its statement — the prior why rested on "confined to backlog storage",
which is the sentence `file-upstream` breaks, so carrying the guarantee forward meant re-resting it
on the property that actually holds: neither admitted surface is reached without a person acting.

**The two branches do not cost the same, and only one of them fits Chunk 03** (surfaced at Chunk
01's review). Chunk 03 is records-only — six artifacts, no module. That is the whole of what (a)
needs: an amendment recording that the norm admits one non-storage network surface. **(b) is a code
change** — gating the op on `backlog_service_repo` is a refusal arm in `upstream.py` plus its
`filing-disabled`-shaped error, its tests, and a re-reading of §5 check 3's amendment, which
deliberately decoupled identity from that scalar. No chunk owns it. So a (b) ruling does not
reshuffle Chunk 03, it **adds a chunk** — and shipping Wave A on a (b) ruling without that chunk
leaves the departure recorded and unremedied, which is the one outcome neither branch intends. If
the owner rules (b), Chunk 03 splits: 03a the gate, 03b the records.

`[ASSUMPTION: the pinned upstream target is a single hard constant, not configurable | MED impact |
user can correct]` — design §5 check 2 says "the plugin's declared canonical upstream repo (a plugin
constant … not a caller-supplied `--repo`)". Read literally that forbids configurability, which is
what makes the check meaningful. Recorded because a future fork of prawduct would need to change it.

**What would raise confidence:** the owner's ruling on the Local-first departure (one sentence).

## Status

- [x] Chunk 01: The pinned target, the preview payload, and the contract test that replaces the interim guard
- [x] Chunk 02: The send path refuses on all five checks, and identity fails closed
- [x] Chunk 03: The norm reaches steady-state, and every artifact that described the absence describes the contract

**Context:** Wave A of the BKL-7Q4M program (three waves; B = the `Upstream filing:` preference and
the `report-bug` rewrite plus the live XP6 verification, C = the MG5 drop-box retirement and the
`untriaged-upstream-reports` repoint). The owner ruled 2026-09-06 that the release cuts **after all
three waves**, so this plan does not close the release on its own. It was split out because the
three waves have different `Type:` values and would review badly as one unit.

**Chunk 01 complete, 2026-09-06.** The preview op, the pinned target, the two-signal identity
resolver, and the XP7 contract test in place of the interim egress guard. Suite green with the
interim test gone. Two things a later chunk must not re-derive: the identity resolver already exists
(`upstream.resolve_self_identity`), and preview and send compose through one
`upstream.render_preview` — check 4 re-renders to validate `--approve`, so a second recipe makes
every `ask-user` filing refuse with `approval-mismatch`.

The chunk's cumulative review also **added a requirement to Chunk 02** (the title refusal — see its
spec and the data-model disposition) and **changed what a (b) ruling costs** on the Local-first
question (it adds a chunk rather than reshaping this one). Neither is optional and neither is in the
design; both were surfaced by review rather than by the design doc, which is why they are recorded
here rather than left to be rediscovered.

**Chunk 03 complete, 2026-09-07 — Wave A is done.** The egress norm is `steady-state`, the
Local-first norm admits a second network surface on the owner's (a) ruling, the title norm binds four
write paths, and every coherence edit the design's §8 named is applied.

Two reviews ran. The first was dispatched over a dirty tree and therefore covered Chunks 01–02, not
this one — `cumulative` takes a commit range, so uncommitted work is invisible to it. That is now a
`learnings.md` rule, and this chunk was committed before its own review. Both rounds returned 0
blocking; fourteen findings were fixed across them, of which the sharpest were a `--body` fence that
crossed the owner boundary intact (a guard reused without the transform it was paired with), an
unreadable preferences file demoting `never-file`, and — twice — a guard of mine that could not see
the case it was written for. **What Wave B should take from that pattern:** every one of those was a
claim about a PATH that was true of the codebase generally, so check what a guard covers, not that
it exists.

**Carried to Wave B, not dropped.** `skills/backlog/adapter-mode.md` states that `report-bug` has
not been rewritten onto `file-upstream` and that nothing calls the op — true at Wave A's close and
false the moment Wave B lands. The absence guard will not catch it (it keys on lines naming the op,
and that sentence does not), and widening it to phrase-only matching across every governing document
is how a guard starts crying wolf. So Wave B must correct that passage as part of its own work; this
paragraph and `.prawduct/.handoff-notes.md` are the only things that will say so.

**Owed at the merge, and this is its durable home.** `#329` (BKL-4T9C) is satisfied in full by this
plan's Chunk 02 — `upstream.resolve_self_identity` + `check_not_self` is its Expected — but it stays
OPEN until the PR merges, because on the Issues backend `status --to shipped` closes the remote issue
the instant it runs, leaving it wrongly closed if this branch is reworked or dropped (the failure
`#697` files, citing `#687` and `#688`). At merge, both calls are needed — `status` records no ship
handle by itself:

```
prawduct-hook backlog status 329 --to shipped
prawduct-hook backlog update 329 --closed-by upstream-filing-adapter
```

The handle is the branch scope, not a SHA and not a chunk id — a chunk id names no plan. **A
`Closes #329` in the PR body will not stand in:** GitHub fires closing keywords only into the
*default* branch, and this PR bases on `develop`. Recorded here rather than only in
`.prawduct/.handoff-notes.md`, which is gitignored and consumed by the next `/clear`.

**Chunk 02 complete, 2026-09-06.** The send arm, all five checks refusing independently and filing
nothing, the title refusal on the fourth adapter write path, `source-key:` idempotency, and the
advisory carry-through onto every refusal. `#329` (BKL-4T9C) is closed by it. Suite green.

Its review caught the defect the whole test suite was structurally blind to: **the send arm never
resolved a transport**, because every test injected a fake and production enters `cli.run` with
none. Resolution now sits inside the send branch — not at the handler top, where it would build a
seam on the preview path and dissolve the guarantee that arm exists for — and both halves are pinned
by tests that pass no transport at all. Check 2 was likewise the one of five with no send-arm test,
its inner leg surviving mutation behind the CLI's pre-check. Two rules went to `learnings.md`.

Chunk 03 inherits three things from this chunk, all recorded in its own section: the `data-model.md`
§ Direction "all three write paths" count (now four), the still-standing `SKILL.md` claim that the
adapter-side pin exists "only in the design", and `IMPLEMENTED_ADAPTER_GUARDS`, which still excludes
`target-pin`.

**Two findings from the planning pass that fix the chunk order, and must not be re-litigated
into a later chunk:**

**Chunk 01 must replace the interim egress test in the SAME commit that first names the surface.**
`tests/preferences/test_no_upstream_content_egress.py` asserts (a) the token `file-upstream` /
`file_upstream` appears nowhere under `plugin/lib`, `plugin/hooks`, `plugin/bin`, and (b) the
literal `brookstalley/prawduct` appears nowhere under `plugin/lib/backlog/`. Design §5 check 2
requires the pinned target to be a plugin constant *in the adapter*, so the keystone violates both
the moment it lands. The design's "the interim test stays live until the contract test lands" is
therefore a same-commit constraint, not a chunk-ordering preference. Splitting them leaves the suite
red for the whole wave, and a red suite is what the release gate reads.

**Prawduct cannot exercise its own happy path against a LIVE target** — §5 check 3 refuses when the
pinned target equals the running repo's identity, and the pinned target IS `brookstalley/prawduct`.
This constrains less than it first appears, and the limit is worth stating precisely so a later
chunk does not try to design around it. The offline suite runs entirely against
`tests/fakes/fake_github.py`, which implements the transport seam, so **Wave A exercises the send
path in full**; Chunk 02 asserts the refusals against this repo's real identity (prawduct is the
natural fixture for check 3, since the refusal is live here) and the happy path against the fake.

What genuinely needs a live repo is only the `[XP6 verify]` item, and it is **Wave B's blocker, not
a self-file consequence**: confirming that a non-collaborator cannot set labels requires a
*non-collaborator identity*, and the owner is a collaborator on `brookstalley/prawduct`. Relaxing
check 3 would buy nothing here. Wave B needs a second GitHub identity, or a repo where the filing
account is not a collaborator — flagged now because it has a lead time that a build session does not.

## Scaffolding

Existing repo — no initialization. Branch `feat/upstream-filing-adapter` off `develop`. Suite:
`python3 -m pytest tests/ -q`; record evidence via `prawduct-hook test-evidence record`. The offline
suite runs against `tests/fakes/fake_github.py`, which implements the transport seam — extend it for
the upstream target rather than adding a second fake.

Several governance prose files carry token-budget guardrail tests: when a protocol edit trips one,
simplify or deduplicate within the file first, raise the ceiling second, and never relocate text
between files to dodge a budget.

### Verification Strategy

Beyond unit tests: Chunk 01's payload rendering is verified by asserting the **exact bytes** of a
rendered payload against a pinned fixture, not by asserting fields exist — "sent == previewed" is
the guarantee, so a shape assertion would pass while the bytes drifted. Chunk 02 is verified against
this repo's own real identity (the self-file refusal is live here, which makes prawduct the natural
fixture for check 3) and against a fixture repo whose identity resolves from the git remote alone,
with `backlog_service_repo` unset — the fail-open case the design's §5 amendment exists to close.
Chunk 03 is verified by the norm probes: `stalled-transition` must fall silent for the security-model
citation, and `tests/test_norm_probes.py::TestSilentAgainstThisRepo` must pass without a stopgap.

## Build Chunks

### Chunk 01: The pinned target, the preview payload, and the contract test that replaces the interim guard

- **Description:** The thin vertical slice: a `file-upstream` op that renders the exact outbound
  payload and computes its digest, sends nothing, and is guarded by the contract test that replaces
  the interim egress guard **in this same commit** (see Context). Three pieces. **(1) The pinned
  target** — one constant naming the canonical upstream repo, read by the adapter; not a
  caller-supplied `--repo`, and a `--repo` that does not match it is an error in Chunk 02.
  **(2) The preview path** — `file-upstream --title T --body B [--component C] --json` renders the
  §2 payload (title convention `[prawduct] <component>: <symptom>`, the six fixed body sections, and
  the **trimmed** `prawduct:` block carrying only `v:`, `found_in:`, `source-key:`), computes
  `payload_digest = sha256(canonical send-bytes)`, prints `{payload, payload_digest}`, exits 0,
  sends nothing. `found_in:` is sourced from `prawduct-hook version`, never recalled, and is
  `(unknown)` when the manifest is unreadable. The in-repo `provenance:` block's `source:` field
  **must not** be emitted — that is the product-name leak the trimming exists to prevent.
  **(3) The contract test** — replaces `tests/preferences/test_no_upstream_content_egress.py` with
  the XP7 five-check test. Chunk 01 lands the two checks it can already assert (target-pinned;
  refuses-without-approval, since no send path exists yet) and the payload-byte pin; Chunk 02 fills
  in the remaining three. Reuse `issuefmt`'s `TITLE_MAX` / `BODY_MAX_WORDS` budgets rather than
  restating them.
- **Depends on:** none
- **Artifacts consumed:** `documentation/backlog-service-upstream-filing.md` §2, §5 checks 1–2;
  `documentation/backlog-service-api-contract.md` §2.4 (the `source-key:` idempotency contract —
  already decided, do not re-derive); `documentation/backlog-service-requirements.md` XP4, XP7
- **Deliverables:** `plugin/lib/backlog/cli.py` (`file-upstream` op + `_OP_USAGE` entry — both
  views, since the help table is composed once), new `plugin/lib/backlog/upstream.py` (the pinned
  target, payload rendering, digest, **and the two-signal identity resolver** — see the amendment
  below), `plugin/lib/backlog/issuefmt.py` (the upstream title/body
  template, if it does not fall out of `render_body`), `tests/preferences/test_no_upstream_content_egress.py`
  (**replaced in place** — the file keeps its enforcement-row identity in `project-preferences.md`
  and is rewritten to assert the contract, so row 86's pointer stays live),
  `tests/test_ephemeral_worktree.py` (adding an op fails the guard's partition test until the op is
  classified — that refusal is the guard working, not a surprise). Delete nothing else:
  the drop-box stays whole until Wave C.

  **Amendment, recorded at build:** the two-signal identity resolver moved from Chunk 02 into this
  chunk, because the payload cannot be rendered without it. The api-contract §2.4 `source-key:` is a
  digest of *(submitter identity, title+body)*, and the submitter is the filing repo — so the
  resolver is an input to the preview, not only to check 3. Chunk 02 consumes
  `upstream.resolve_self_identity` rather than writing a second one; a later chunk building its own
  copy is the shadowed-duplicate failure, not a fresh implementation. `issuefmt.py` was **not**
  touched: the title/body template fell out of composing sections directly, as the deliverable's own
  conditional anticipated.
- **Tests:** exact-byte pin of a rendered payload against a fixture; digest is stable across two
  renders of the same input and changes when any byte changes; `found_in:` reads the real version
  and degrades to `(unknown)` on an unreadable manifest rather than guessing; the trimmed block
  carries no `source:` field for any input; a preview call performs no transport call at all
  (assert against the fake, not by inspection); title/body over budget are reported through
  `issuefmt.lint`, not silently truncated.
- **Acceptance criteria:** `file-upstream` previews and returns a digest; nothing sends; the
  replacement contract test passes and its two live checks fail when deliberately broken (mutation-
  check both, since a contract test that cannot fail is the vacuous-pass class this repo has paid
  for); suite green with the interim test gone and the contract test in its place.
- **Critic mode:** final
  <!-- Keystone: it lands the norm's enforcement swap. Coherence matters before Chunk 02 builds on it. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added (`scope=upstream-filing-adapter`, no `release=`)
  3. `/prawduct:critic` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

### Chunk 02: The send path refuses on all five checks, and identity fails closed

- **Description:** `file-upstream --approve sha256:<digest> --json` sends, and refuses unless all
  five §5 checks hold — each a distinct structured error, files nothing on any failure:
  (1) preference ≠ `never-file` → `filing-disabled`; (2) target pinned → `target-not-pinned`;
  (3) no self-file → `self-file`; (4) approval matches the re-rendered bytes → `approval-mismatch`;
  (5) authenticated via the session `gh` identity → `auth`. **Check 3's refusal ROUTES rather than
  merely erroring:** XP7 reads "never let prawduct's own repo self-file upstream *(it routes to its
  own backlog)*" — the routing is part of the requirement, and design §5 reduced it to a bare error.
  The refusal names the in-repo `file` path as the correct route. The invariant itself stands: the
  op's ceremony (recomposition, verbatim review, digest approval, the ~175-word body ceiling) exists
  because content crosses an *owner* boundary, and prawduct→prawduct crosses none — routing its own
  bugs through the minimized path would lose fidelity to protect prawduct from prawduct.
  **Check 3 carries the design's
  2026-07-24 amendment and is the subtle one:** identity resolves from **both** `backlog_service_repo`
  **and** the git remote (`origin`), refuses if **either** matches the pinned target, and **fails
  closed when neither resolves**. Keying it on `backlog_service_repo` alone is fail-open in every
  pre-cutover repo — the state the check most needs to hold. Check 4 re-renders the payload and
  recomputes the digest rather than trusting the caller's, which is what makes "sent == previewed"
  true; it is waived under `always-file` (standing consent). The preference is read here but is
  *authored* in Wave B — until then the default `ask-user` is the only reachable state, and the
  reader must treat an absent preference as `ask-user`, never as `always-file`.
  **Carry the advisory/audit fields onto the error returns too**, not only the success envelope:
  error returns use a different constructor from `core.ok`, and this repo has twice shipped a field
  that existed on the success path and silently vanished on the failure path.
- **Also required, surfaced at Chunk 01's review and not in the design:** the send arm **refuses a
  non-conforming title** (the four blocking `issuefmt.lint_title` rules) before filing. `data-model.md`
  § Direction binds title conformance on every adapter write path and names only `file`/`update`/
  `import`, because this is the fourth. The preview stays advisory — nothing is written there, and an
  advisory finding is what lets an author fix a title before approving it. See the plan's data-model
  disposition for the shape difference the refusal must respect.
- **Closes:** `#329` (BKL-4T9C) — its Expected is the two-signal, fail-closed identity check. Chunk 01
  shipped the resolver half; this chunk ships the check that consumes it, which is what closes the
  fail-open the item describes.

  **Amendments and decisions, recorded at build.** Four, none of which the design settles:
  1. **`--approve` is the send trigger in every preference state, and `always-file` waives only its
     value.** §4.1 says standing consent "files directly (no per-report digest)" and §5 waives check
     4 there, which leaves open whether a bare call sends under `always-file`. It does not: the
     token is the only thing separating rendering a payload from filing one, so its *presence* is
     required always (an empty token is refused) and only the digest comparison is waived. The other
     reading makes every preview under standing consent an irreversible foreign write.
  2. **The `source-key:` lookup scans the REST list endpoint, newest-first, not the search API.**
     §2.4 pins the key and specifies no lookup. Search is not read-your-writes, so it is blind in
     exactly the seconds after a create — the retry window the key exists for.
  3. **A dedup lookup that cannot run files anyway, with a loud warning.** XP7 is submit-or-nothing
     and names a slow flow as what turns "submit" into "nothing"; the cost of proceeding blind is a
     duplicate a maintainer can close. The five checks are the guarantees and none runs through this
     path — "authority fails closed, advice fails soft", and retry-safety is advice.
  4. **An absent or unrecognised `Upstream filing` value reads as `ask-user`.** Never `always-file`
     (a typo would become standing consent) and never `never-file` (a misspelling would refuse a
     legitimate report); an unrecognised value additionally warns, because that is the case where
     the operator believes they set something and did not.

  `transport.py` and `tests/fakes/fake_github.py` were listed as deliverables and needed **no
  change** — `create_issue`/`list_issues` are already the seam and the fake is keyed per repo, so
  the pinned target is just another repo to it. `plugin/skills/backlog/adapter-mode.md` gained the
  send arm, which the deliverable list did not name: the CLI usage table is the referent that
  surface points at, and it changed here.

  **Still Chunk 03's, confirmed as stale but deliberately not touched here:** `skills/backlog/SKILL.md`
  (line ~219) still says an adapter-side pin "exists only in the `file-upstream` design", and
  `tests/test_backlog_instruction_surface.py`'s `IMPLEMENTED_ADAPTER_GUARDS` still excludes
  `target-pin` with a comment awaiting it. Both are the "describes the capability as unbuilt" class
  Chunk 03's grep assertion owns, and both went stale at Chunk 01 rather than here.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `documentation/backlog-service-upstream-filing.md` §5 (all five checks
  and the check-3 amendment); `documentation/backlog-service-requirements.md` XP5, XP7
- **Deliverables:** `plugin/lib/backlog/upstream.py` (the five checks and the send path; the
  two-signal identity resolution landed in Chunk 01 as `resolve_self_identity` — consume it, do not
  write a second one), `plugin/lib/backlog/cli.py` (`--approve` handling; `_EXIT_CLASS` gains the
  four remaining refusal codes beside Chunk 01's `target-not-pinned`), `plugin/lib/backlog/transport.py`
  (the upstream write, reusing the existing `gh` seam — the adapter never manages a token),
  `tests/preferences/test_no_upstream_content_egress.py` (fill in checks 3–5), `tests/fakes/fake_github.py`
  (the upstream target seam)
- **Tests:** each of the five checks refuses independently and files nothing (assert the fake
  recorded no write, not merely that an error returned); check 3 refuses when identity comes from
  `backlog_service_repo` alone, when it comes from the git remote alone, and **refuses when neither
  resolves** — the fail-closed leg, which is the one a naive implementation gets backwards; the
  `self-file` refusal names the in-repo `file` route (XP7's parenthetical), asserted on the message
  rather than only on the error code; a digest
  approved for payload A does not authorize payload B; `always-file` waives check 4 but no other;
  `never-file` refuses regardless of a valid digest; every error return carries the same envelope
  fields as the success return.
- **Acceptance criteria:** all five checks enforced and independently falsifiable; the happy path
  files exactly once against the fake and is idempotent on the `source-key:` (a re-file returns the
  existing issue, per api-contract §2.4); running in *this* repo produces `self-file` (the live case,
  per Context); suite green.
- **Critic mode:** chunk
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added (`scope=upstream-filing-adapter`, no `release=`)
  3. `/prawduct:critic` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

### Chunk 03: The norm reaches steady-state, and every artifact that described the absence describes the contract

- **Description:** The records half. **(1) The security-model norm** amends
  `Status: in-transition → steady-state`, with the steady-state form asserting the XP7 contract
  (target-pinned, authenticated, refuses-without-owner-approval, no self-file) rather than the
  interim absence — amended toward the guarantee, never weakened, and the `Mechanism:` line
  repointed to the contract test. This is what clears the stalled transition the release gate reads.
  **(2) The Local-first ruling** from Open assumptions is recorded in `architecture.md` § Direction
  as a `[DECISION: … | … | user can veto/override]` — an amendment if the owner takes (a), a bounded
  exception if (b). **Blocking input: do not write this chunk before the owner has ruled.**
  **(3) Coherence edits**, all of which the design's §8 names, so none is discretionary: api-contract
  §2.4 gains the preview/`--approve`/digest contract and the five-check refusal set, and its error
  vocabulary gains `filing-disabled`, `target-not-pinned`, `self-file`, `approval-mismatch`;
  **`data-model.md` § Direction's title-conformance norm says "all three write paths" in both its
  `Status:` and its `Mechanism:` and there are now four** (surfaced at Chunk 02's review; not a
  departure — the code conforms harder than the norm asks, and the binding ruling is already in this
  plan's `governed_by:` — but the norm's own text still describes the pre-`file-upstream` world, and
  this list named only §5's `source-key:` note, so it fell through);
  security-model §1a/§5 gains the attended-only reconciliation; data-model §5's `source-key:` gains
  the trimmed-upstream-block note; and `project-state.yaml`'s `egress_boundary` description is
  corrected — the *count* stays three (the op rides `transport.py`, already site 1), but site 1 is
  no longer only "the opt-in backlog backend" and saying so is the point.
- **Depends on:** Chunk 02, and the owner's ruling on the Local-first departure
- **Artifacts consumed:** `documentation/backlog-service-upstream-filing.md` §8
- **Deliverables:** `.prawduct/artifacts/security-model.md` (§ Direction norm to steady-state),
  `documentation/backlog-service-security-model.md` (§1a/§5 — see the decision below; the artifact has
  no numbered sections, so this half of the original entry resolved to the design doc),
  `.prawduct/artifacts/architecture.md` (§ Direction Local-first decision),
  `documentation/backlog-service-api-contract.md` (§2.4 + error vocabulary),
  `documentation/backlog-service-data-model.md` (§5), `.prawduct/project-state.yaml`
  (`egress_boundary` description), `.prawduct/artifacts/project-preferences.md` (row 86's mechanism
  description, which currently names the interim rule)
- **Tests:** `tests/test_norm_probes.py::TestSilentAgainstThisRepo` passes with **no stopgap
  recorded** — the transition is finished, not bounded; the norm entry parses (single-word field
  labels, `Status:` on its own line — the soft-wrap defect this repo has already paid for twice);
  no artifact still describes `file-upstream` as unbuilt or deferred to W3 (grep-asserted, since
  that claim now appears in several files)
- **Acceptance criteria:** `stalled-transition` no longer fires for the security-model citation;
  the full suite is green **without** a stopgap; no surface still says the capability is unbuilt.
- **Critic mode:** cumulative
  <!-- Last chunk of the wave; the wave ships as one PR. Type: cumulative-final. -->
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added (`scope=upstream-filing-adapter`, no `release=`)
  3. `/prawduct:critic cumulative` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

  **Decisions taken at build, both departing from this section as written.** Neither is optional and
  both are recorded here rather than left for a later reader to rediscover as a discrepancy.

  1. **`IMPLEMENTED_ADAPTER_GUARDS` does not gain `target-pin`**, though Chunk 02's context listed it
     as inherited work and the test's own comment invited it. The mechanism **narrowed rather than
     arrived**: `upstream.py` compares repo identity, but only on the `file-upstream` path, and the
     ops that test guards — `import` / `file` / `update` — reach none of it. Backing the name would
     let a migration surface cite a safety net that does not cover it, which is precisely the defect
     that file exists to close, one op over. The stale *reasons* were corrected instead (the comment
     asserted no repo-identity comparison existed anywhere in `lib/backlog/`, which is now false),
     and the chunk-number reference in the comment was replaced with the standing why.
  2. **The `security-model.md` §1a/§5 deliverable resolves to
     `documentation/backlog-service-security-model.md`, not `.prawduct/artifacts/security-model.md`.**
     The artifact has no §1a and no numbered sections at all; the design doc has both, and the
     design's §8 — the source this deliverable list was drawn from — means that one. The artifact's
     § Direction norm was still edited, as its own separate deliverable.

  **Also corrected, beyond the deliverable list:** `documentation/backlog-service-prd.md`'s XP1 bullet
  said the fixed-target subset "ships **with the migration**", which was both stale and a scheduling
  claim about a wave it no longer belongs to; api-contract §2.4's `file-upstream` row said auth
  "resolves by **target owner**", which is the W3 foreign-identity plane and contradicts the built
  check 5 (the session's own `gh` login). Both are the "describes the capability as unbuilt" class
  this chunk's grep assertion owns.

  **The wave's cumulative review ran against Chunks 01–02, not this chunk, and the ordering rule is
  now recorded.** Dispatched with this chunk uncommitted, `cumulative` takes a COMMIT RANGE
  (merge-base → HEAD), so all three reviewers read `git show <HEAD>:<path>` and this chunk was
  invisible to them. `chunk` mode takes the opposite interval (HEAD-tree → working tree) and must NOT
  be committed first — the mode determines the order, which is the rule that went to `learnings.md`.
  This chunk is therefore committed BEFORE its own cumulative runs.

  **Six fixes came out of that review anyway, four in Chunk 02's code, all folded into this chunk's
  commit rather than deferred** (0 blocking; each was real and the wave ships as one PR): the
  terminated-`prawduct`-fence egress hole (`encode.check_body_text_strict` — the in-repo guard's
  tolerance is only safe where `compose_body` runs beside it, and `render_report` inherited the guard
  without the transform); the unbounded `source-key:` dedup walk (bounded to a window, which required
  `transport.paginate` to gain an opt-in `on_cap="stop"` because its cap RAISES by contract and a bare
  cap would have made every first-time filing report a transport failure that did not happen); the
  preview's inability to predict the title refusal (`upstream.previewable_refusals`, one named set
  consumed by the preview and pinned against the send arm's own source); `adapter-mode.md`'s
  exhaustive-reading refusal list; the `source-key:` oracle overclaim (corrected in the design,
  mechanism filed as **#763** at `stage: design` — a keyed digest needs a per-submitter secret the
  adapter deliberately does not manage); and Chunk 02's untested live-repo self-file criterion.

  **The grep assertion is a test, not a grep** —
  `TestNoSurfaceStillDescribesTheAbsence` in the egress contract test. Records are exempt by
  construction (a line must carry both a date and a record marker) rather than by a file list, which
  would grow until it meant nothing; `functional-audit-v3.2.0.md` and `operator-verification.md` are
  dated acceptance records and were deliberately left describing the world they measured.
