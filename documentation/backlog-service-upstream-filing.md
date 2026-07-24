# Backlog Service — Upstream Filing (safe cross-owner bug reporting)

`status: v1 — owner-approved & Critic-reviewed 2026-07-23 (0 blocking; the coherence warning folded). The buildable spec for the file-upstream outbound-payload shape and adapter contract, settling BKL-7Q4M (content minimization — the § Direction norm's tracking item) and BKL-9XQ2 (consent / evidence / label taxonomy) against the settled requirements XP4–XP7 (owner decision on the approval gate: byte-pinned + honest limit, upstream-only). Both items now stage: ready. · source: planning session · stage: ready`

**Parent:** `documentation/backlog-service-requirements.md` (Upstream bug reporting — **XP4–XP7**, settled 2026-07-23) and, through it, PRD §8.4/§8.9 (XP1/XP2, MG5). This doc fixes the *how*: the exact bytes that cross the boundary, the recomposition that minimizes them, the consent that authorizes them, and the adapter op that enforces all of it.

**Governed by:** `.prawduct/artifacts/security-model.md` **§ Direction** — *"A governed product's content never leaves that product's own repository and owner … any cross-owner or public-plane filing surface is an owner decision, never an increment"* (`Status: in-transition`, tracking **BKL-7Q4M**). This design is the reviewed design the norm waits on; § *Governance & propagation* below records its disposition. Also governed by `architecture.md` § Direction (the adapter never manages a token — `gh` owns the credential).

**Related design docs this extends (not duplicates):** `backlog-service-api-contract.md` §2.4 (`file-upstream` op — this doc pins its preview/approve contract), `backlog-service-security-model.md` §1a (attended-only foreign filing) / §5 (non-collaborator intake) / §6 (PV3/PV4), `backlog-service-data-model.md` §5 (`source-key:` marker home).

---

## 1. Scope — the one op this governs, and the boundary that defines it

This design governs **exactly one operation: `file-upstream`** — writing an issue into a **foreign, public** repo (for v3.2.0, the fixed target is prawduct's own repo; the drop-box's 1:1 replacement, MG5). It governs **nothing else.**

The organizing principle is the **trust boundary**: *does product content leave its own repository and owner?*

| | **In-repo `file`** (a repo → its own Issues) | **`file-upstream`** (→ prawduct's public repo) |
|---|---|---|
| Target | self — the repo's own `backlog_service_repo`, derived, never a free `--repo` | a **foreign public** repo, **pinned** (§5) |
| Content crosses an owner boundary? | **No** — GitHub enforces access with the caller's own token | **Yes, irreversibly** — no issue-delete, numbers never reused |
| Content minimization | none | **XP4** (§3) |
| Per-report consent | none | **XP5** (§4) |
| Preview → digest → approve | none | **XP7** (§5) |
| Attended-only | no — unattended grooming/briefing writes are fine (Security §1a) | **yes** (§4.3) |
| Ceremony | **one call, returns an ID** — like `backlog add` today | the whole flow below |

Everything in this document is the right-hand column. In-repo filing stays zero-ceremony CRUD (AG2/G1); imposing any of this on it would violate the never-block create contract. The § Direction norm is not even *engaged* by in-repo filing — nothing leaves the product's own owner.

---

## 2. What crosses the boundary — the outbound payload (XP4/XP6)

The payload is a **label-less GitHub issue** plus one trimmed provenance marker. Nothing else. The design's honesty rule (XP4): we state exactly what crosses, and we do **not** claim a redactor we cannot back.

**Title** — a structural, human-set convention (a non-collaborator filer cannot apply labels, XP6/Security §5, so category cannot ride in a label):

```
[prawduct] <component>: <one-line symptom>          # ≤72 chars (issue-standard §1)
# e.g.  [prawduct] stop-hook: gate blocks on in-flight background work
```

The `[prawduct]` prefix is the **intake signal** the receiving side keys off (§6) — it is settable by collaborator and non-collaborator alike, so it works for both the third-party filer and the dogfood (owner-as-collaborator) case. `<component>` is a prawduct surface (skill / hook / gate / `prawduct-hook` subcommand / `lib/` / methodology), never a product-side name.

**Body** — fixed sections, ~120 visible words, product-content-free:

| Section | Content | Minimization rule |
|---|---|---|
| **Component** | the prawduct surface at fault | prawduct-side vocabulary only |
| **Found in** | `prawduct vX.Y.Z (plugin)` from `prawduct-hook version` | **sourced, never recalled**; `(unknown)` if the manifest is unreadable — never guessed |
| **Problem** | the symptom, recomposed in prawduct's terms | L1 (§3) — no product identity/paths/ids |
| **Reproduction** | a *synthesized* minimal repro **or** an *abstracted* scenario with placeholders | L1 (§3); a code block trips the §4.2 confirm-synthetic gate |
| **Expected** | the correct prawduct behavior | — |
| **Root cause** | if known, marked verified-vs-inferred (Principle 5) | honest confidence, no internal ids |

**Provenance marker** — one `prawduct:` body block, **trimmed for egress**. The in-repo block's `provenance: {source: <product>, …}` would leak the product name and **must not** be emitted upstream. Upstream carries only:

```prawduct
v: 1
found_in: 3.2.0
source-key: sha256:<digest>          # opaque; = digest(submitter-identity, source-item-ref/title+body)
```

The `source-key:` is the api-contract §2.4 idempotency key (a re-file with the same key **returns the existing issue, never a duplicate**). It is a one-way digest — it does **not** reveal the submitter or the source item; it only lets a retry collapse. The submitter's real GitHub identity is attached natively (public issue author) and unavoidably — that **agency/attribution** exposure is inherent, surfaced at consent (§4), not something minimization can remove.

**Filed label-less; triage applies the taxonomy (XP6).** The issue lands with **no `stage:`/`status:`/`area:` labels** — a non-collaborator cannot set them, and consumers are never coupled to prawduct's taxonomy (GV6 is triage-side). Prawduct-side triage relabels from the intake set (§6). *(Load-bearing platform fact to confirm on a throwaway issue at build, per XP6: current GitHub non-collaborator label behavior — do not ship on recall.)*

---

## 3. L1 — recomposition (soft, model; never the data plane) (XP4)

The composing agent **recomposes the report in prawduct's terms** and never echoes product content. This is model judgment in a *decision*, not in the data plane (G1) — it lives in the rewritten `report-bug` skill (§7), not in `lib/backlog/`. Two modes:

- **synthesize** *(simple code bugs)* — write a **minimal generic reproduction** that stands alone and contains no product content: a few lines that trigger the prawduct defect against a bare fixture. Preferred when the bug reproduces without product specifics.
- **abstract** *(diagnostic bugs — the common case)* — describe the scenario with **generic placeholders** for every product particular: "a governed repo with a feature branch", "a skill file", "a backlog item id", "a merge to the default branch" — never the real branch, path, id, product name, or domain term.

**Never crosses, in either mode:** product/repo name, filesystem paths, internal ids, learnings prose, domain vocabulary, verbatim code excerpts (unless synthesized-generic **and** confirmed at §4.2). **Attribution carries the prawduct version only.**

**Honest limitation (MUST be stated, not implied — XP4):** "no proprietary content" is **not mechanically enforceable at a prose boundary.** L1 is best-effort authoring; the guarantee is L1 + the mandatory human review of L2 (§4). This design ships **no redactor** and claims none. (The credential denylist `scrub_secrets`, `lib/backlog/transport.py`, is a *credential* backstop on transport output — it is not, and is not represented as, a content-minimization filter: product prose and paths have no recognizable shape to match.)

---

## 4. Consent (XP5) — per-report, adapter-bound

### 4.1 The preference (mirrors the PR-merge pattern)

A `project-preferences.md` setting, three states, **default `ask-user`**, honored without exception:

| State | Meaning | Adapter behavior (§5) |
|---|---|---|
| **`ask-user`** *(default)* | ask per report; the ask **is** the XP4-L2 verbatim-payload review | requires `--approve <digest>` |
| **`never-file`** | standing "no" | **hard refuse**, always |
| **`always-file`** | standing pre-consent — "never ask me" | files directly (no per-report digest); **L1 recomposition is then the operative safeguard** |

There is **no install-time opt-in** (owner, 2026-07-23); per-report consent is the whole mechanism. A user moves off the default into a standing state to say "never ask me" — an informed standing choice, not a silent bypass.

### 4.2 The verbatim review (L2), and the code-block gate

Under `ask-user`, the skill shows the **exact** outbound payload (the bytes of §2, nothing summarized) and the human explicitly approves before send. Where a payload contains a **code block**, the skill issues an explicit **"confirm this code is synthetic / non-proprietary"** prompt, so the review is active on the actual leak vector rather than a rubber-stamp. Approval yields the digest passed to the adapter (§5).

### 4.3 The unattended rule, and what the chosen posture does/doesn't guarantee

XP5: *where no human is present, `ask-user` means don't file — never "file anyway."* Foreign filing is **attended-only** (Security §1a: no unattended anonymous/foreign filing).

**`[DECISION: approval gate = byte-pinned + honest limit (owner, 2026-07-23) | the adapter mechanically enforces target-pin, no-self-file, auth, preference-state, and a payload-digest match (sent == previewed); it does NOT mechanically detect "human present" | user chose this over the stronger "attendance gate" option, which would refuse --approve on a detected-unattended session]`**

Consequence, stated honestly: under `ask-user` the mechanical floor is that **nothing files without an `--approve <digest>` token**, and the default is `ask-user` (not `always-file`), so nothing files unprompted. "A human actually reviewed, in an attended session" is enforced by the **skill obligation** (the rewritten `report-bug` must not fabricate approval where no human is present) **plus the honest limitation** that a misbehaving unattended agent under `ask-user` could pass a fabricated `--approve` — the same limitation class XP4 already concedes for content. `never-file` remains a **hard** mechanical guarantee regardless. The stronger attendance gate was considered and declined (above); this is not a gap discovered late but the posture the owner chose, recorded so a reviewer sees the trade.

---

## 5. The adapter contract (XP7) — where the guarantee is testable

`file-upstream` is **preview-by-default**; sending requires a second, digest-bearing call. This is the `--apply`-style posture the "no destructive/irreversible action without explicit consent" norm mandates — and it is the real contract BKL-8V3D found `adapter-mode.md` *claiming* but `lib/backlog/` not implementing. This doc is where it gets implemented for real.

**Call 1 — preview (default, side-effect-free):**
```
prawduct-hook backlog file-upstream --title T --body B [--component C] --json
  → renders the EXACT payload (§2), computes  payload-digest = sha256(canonical send-bytes),
    prints {payload, payload_digest}, sends NOTHING.   exit 0
```

**Call 2 — send (only on an explicit, matching approval):**
```
prawduct-hook backlog file-upstream --approve sha256:<digest> --json
```
The adapter **refuses to file unless ALL hold** (any failure → structured error, files nothing):

1. **Preference** ≠ `never-file`  → else `error: filing-disabled` *(non-retryable)*.
2. **Target pinned** — the target is the plugin's **declared canonical upstream repo** (a plugin constant, resolved like `prawduct-hook version` resolves the version — not a caller-supplied `--repo`). A `--repo` that does not match the pinned target → `error: target-not-pinned`. This closes the unconstrained-`--repo` hole (BKL-2Q7F/BKL-9XQ2): `ids.parse_repo` shape-validation is **not** an owner constraint.
3. **No self-file** — if the pinned target equals the running repo's own identity, refuse → `error: self-file` (prawduct's own bugs route to its own backlog, never upstream to itself). This is the XP7 "never let prawduct's own repo self-file" invariant and the durable replacement for the interim egress test.

   **[AMENDMENT 2026-07-24 (owner-approved) — identity is resolved from TWO signals, and the check fails closed. | Tracked by BKL-4T9C.]** As originally written this check compared the pinned target against the running repo's `backlog_service_repo` alone. That scalar is **unset in every pre-cutover repo** — including prawduct's own until the migration lands — and `lib/backlog/context.py` performs no git-remote resolution, so `backlog_service_repo` was the adapter's *only* self-identity signal. An invariant keyed on a field whose default value disables it is **fail-open**, and it was inert precisely where it matters most. The amended check:

   - resolves the running repo's identity from **both** `backlog_service_repo` **and** the git remote (`origin`), and refuses if **either** matches the pinned target;
   - **fails closed** when neither signal resolves — an unresolvable identity is a refusal, not a pass.

   The norm is amended toward its guarantee, never weakened (§ Direction). Second-order effect, recorded so the sequencing rationale does not outlive its reason: the *only* hard reason this design's build sat behind the real migration was that the migration is what made this check live. With identity resolved independently, that coupling is gone — though note the `[XP6 verify]` step (§9) still needs a live throwaway issue, so the chunk cannot complete entirely offline.
4. **Approval matches the bytes** *(when preference = `ask-user`)* — re-render the payload, recompute the digest, refuse unless it equals `--approve`'s value → `error: approval-mismatch`. Guarantees **sent == previewed** (closes approved-A-sent-B). Waived under `always-file` (standing consent; L1 is then the safeguard, §4.1).
5. **Authenticated** — resolve the session `gh` identity (never anonymous — GitHub issues are inherently authenticated; never a managed token, `architecture.md` § Direction) → else `error: auth`.

On success: file the label-less issue (§2), stamp the trimmed `prawduct:` block + `source-key:` marker (idempotent re-file returns the existing issue, api-contract §2.4).

**Submit-or-nothing (XP7).** Declining files **nothing** — there is **no local backlog capture** of an upstream bug (a captured-but-unsubmitted upstream bug helps no one and clutters the product). The only no-op fallback is *pointing the user at the tracker URL* to file by hand — a pointer, not a capture (§7).

**Fast (XP7).** draft → one recomposition → one approve → filed. A slow flow degrades submit-or-nothing into "nothing" and loses the signal.

**What the adapter does NOT guarantee (the honest boundary):** it pins **where** the issue goes and **which bytes** go, and it hard-blocks `never-file`; it does **not** verify a human read the content (that is §3 L1 + §4.2 review) and does **not** mechanically detect attendance (§4.3). The XP7 contract test asserts the five checks above — target-pinned, no-self-file, authenticated, refuses-without-approval, digest-match — and **replaces** `tests/preferences/test_no_upstream_content_egress.py` (never weakened to let an unreviewed surface through — § Direction).

---

## 6. Receiving side (referenced, not designed here)

The intake/triage half is MG5's receiving end + Security §5, tracked separately (report-bug receiving side / BKL-6M4T); this doc only guarantees the outbound payload carries the signal it needs:

- **Intake query** = open issues whose title carries the `[prawduct]` convention and no triage label — works for both non-collaborator filings (Security §5's non-collaborator-authored-unlabeled set) and the collaborator dogfood case.
- The `untriaged-upstream-reports` advisory (today: counts `incoming-bugs/*.md`) is repointed to **count that intake set** instead of drop-box files (MG5). *Exact query pinned on the receiving-side item, at build.*

---

## 7. What this replaces — `report-bug` rewrite & MG5 lockstep (sequencing)

The build (not this design pass) executes, in lockstep — the drop-box is retired **only together with** its live replacement (MG5, never before):

1. **`report-bug` skill** — step 3 "write to `incoming-bugs/<slug>.md`" becomes "L1-recompose → `file-upstream` preview → (ask-user) show payload + confirm-synthetic → approve → send". The `Found in:` version step is unchanged (already sourced, not recalled). The **inert-fallback (step 4) changes**: submit-or-nothing removes the *local-capture* of an upstream bug; the "point at `github.com/brookstalley/prawduct/issues`" pointer stays as the no-reachable-path fallback.
2. **Preference** — add `Upstream filing: ask-user | always-file | never-file` (default `ask-user`) to `project-preferences.md`, mirroring `PR merge strategy`.
3. **Egress test → contract test** — `test_no_upstream_content_egress.py` is **replaced** by the XP7 five-check contract test (§5); the interim test stays live until that lands.
4. **Drop-box + probe retirement** — retire `bug-inbox` resolver, `.bug-inbox` pointer, `incoming-bugs/`, and repoint the `untriaged-upstream-reports` probe to the §6 intake count.
5. **§ Direction norm** — amend `Status: in-transition → steady-state` once §5's contract test replaces the interim one (§8).

---

## 8. Governance & propagation

- **§ Direction disposition:** `in-transition → (on build) steady-state`. This design *is* the reviewed design the norm waits on; it does not itself ship a surface, so the interim rule and its test stay live until §5/§7 land. The norm is **amended, never weakened** — the steady-state form asserts the XP7 contract (target-pinned, authenticated, refuses-without-approval, no-self-file).
- **Coherence edits this design implies** (do at build, so nothing silently drifts — Principle 13): api-contract §2.4 gains the preview/`--approve`/digest contract and the five-check refusal set; security-model §1a/§5 gains the attended-only + intake reconciliation; data-model §5's `source-key:` gains the trimmed-upstream-block note; the api-contract error vocabulary gains `filing-disabled`, `target-not-pinned`, `self-file`, `approval-mismatch`.
- **Blocked-by / adjacent:** BKL-2Q7F (target-repo binding — §5 check 2 is its durable form), BKL-8V3D (the `--apply`/dry-run contract — §5 is where it becomes real), BKL-5N9W (wildcard grant narrowing — defense-in-depth beside §5), BKL-6J2X (hold the migration advisory — unrelated but same release).

## 9. Open items handed to build

- **[XP6 — verify]** current GitHub non-collaborator label behavior, on a throwaway issue — load-bearing, do not ship on recall.
- **[§6 — receiving side]** exact intake query + advisory repoint — pinned on the receiving-side item, not here.
- **[W3 — out of scope]** the general XP1 surface (arbitrary cross-owner targets, private repos, foreign-identity auth) stays W3. This design ships only the fixed-target public-repo subset. Do not pull W3 forward.
