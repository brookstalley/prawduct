# Governance tax vs quality — cross-repo study, 2026-10-10

`status: findings · source: owner request 2026-10-09 ("quantify and adjust the governance tax versus quality benefits … I have both kinds of repos") · related: roi-audit-2026-10-02, #951 (found_by / B5), #262, #984, #985, #986`

## Question

The owner has prawduct-governed repos, which feel slow but trustworthy, and ungoverned ones such
as repo F, which feel fast but leave low confidence. Is the quality difference real, and what does
governance cost? The study covers every non-fork, non-archived repo pushed to since 2026-01-01
under two GitHub accounts, the owner's and a collaborator's: 42 repos. **Privacy:** this repo is
public and most of the studied repos are private, so every repo except prawduct is anonymised
here. Repo F is the fast ungoverned repo that prompted the study. The repo list and all raw data
(review findings, samples, keys) are kept outside this repo, because they describe private code.

## Instruments

The tooling and agent prompts are in `.prawduct/research/escape-2026-10/`. The raw outputs are
private (see Re-deriving).

1. **Rework (`escape.py`).** For each landing (a first-parent commit on the integration branch),
   it counts the source lines that a *later, separate* landing rewrote within 30 days. It uses
   `git blame` and ignores commit messages. A fix made inside a PR before merge is not counted:
   that is a catch, not an escape. It passed a synthetic known-answer test. Governance mode per
   landing:
   - **none:** no `project-state.yaml`.
   - **dormant:** onboarded, with no `.prawduct/` activity within ±7 days.
   - **vX.Y:** the latest prawduct release on that date.
2. **Fix share.** 180 rework edges were sampled (60 per mode, at most 12 per repo). Sonnet
   labelled 171 of them fix or evolution (one batch came back partial), and Opus agreed on 23 of
   the 30 it also labelled.
3. **Blind retro-review.** The unit is merged code: a window of a landing's diff, 300–500 lines in
   the pilot and wave 1, 700–900 in wave 2,
   reviewed by Opus with the full tree available. The reviewer saw no governance files, repo
   name, commit messages or dates. A second, independent Opus agent verified every finding, and
   only verified-real defects are counted. Rubric: `research/escape-2026-10/rubric.md`.
4. **Catch class.** Opus labelled each of the 44 fix edges by the cheapest practice that would
   have caught the defect before merge.

## Results

### 1. Defect density in recently merged code (blind retro-review)

Both groups are recent work, 2026-09-01 to 2026-10-10. Ungoverned is repo F's integration
branches plus 6 other repos. Governed is 3.4–3.7 work across 9 repos.

| | items | kLOC | verified defects | per kLOC | items with ≥1 |
|---|---|---|---|---|---|
| ungoverned | 25 | 10.7 | 21 (3 high) | **1.97** | 12 |
| governed 3.4–3.7 | 25 | 10.8 | 17 (3 high) | **1.57** | 9 |

- **Rate ratio 1.25, 95% CI 0.66–2.38, two-sided p ≈ 0.6.** No difference is detectable at this
  sample size. A small benefit or none at all fits the data. A benefit bigger than about 2.4× does
  not.
- **Repo F alone: 6 defects in 6.0 kLOC (1.0/kLOC),** which is lower than the governed average.
  The ungoverned rate is pulled up by three small repos. Without repo F the ratio is 2.06; without prawduct's own repo it is 1.24.
- **Precision:** 38 of the 40 defects the reviewer reported were verified real.
- **The wave 1 subsample showed 3×** (1.85 vs 0.63 per kLOC, n=10 per group). Wave 2 erased it.
  This is a warning about reading small samples.

### 2. Rework and escapes over history (`escape.py`)

Landings up to 2026-09-10, so each has a full 30-day window. Rework lines per kLOC (here "none"
leaves out the single dormant landing, which the fix-share modes below fold into none): none 56,
1.x 191, 2.x 69, 3.0–3.3 60, 3.4–3.5 46. Within each repo, rework falls as prawduct versions
advance (the largest governed repo: 126 → 187 → 88 → 72 → 55). But the "none" and 1.x eras are each repo's youth,
and banding by repo age does not give a clean ordering. Combined with the fix share (none 21%,
1–2.x 23%, 3.x 33%), escapes per kLOC come out at about 0.6 for none, 1.1 for 1–2.x and 0.9 for
3.x, with overlapping CIs. This proxy only counts escapes that someone found and fixed, which
favours ungoverned repos, because governed repos track and fix bugs systematically.

### 3. What would have caught the escapes

Of 41 genuine defects that needed a later fix:
- 19 (46%) could have been caught by **code review**
- 11 needed an **integration test**
- 8 only showed up in **production**
- 3 needed a **unit test**

For governed 3.x the split is 10 code review, 3 integration, 5 production. So the Critic is
missing defects that careful reading could have caught.

### 4. Why non-fix rework happens

All 127 sampled rework edges judged "evolution" were labelled by cause, by Opus, with the
prompt in `wf-cause-classification.js`:

| mode | late requirement | refactor | planned next step | environment surprise | discovery could have prevented it |
|---|---|---|---|---|---|
| none (44) | 45% | 30% | 18% | 7% | 18% |
| 1–2.x (44) | 32% | 34% | 20% | 9% | 9% |
| 3.x (39) | 46% | 21% | 15% | 15% | 18% |

- **Late requirements are the largest single cause in every mode.**
- **Governance does not measurably reduce them.** Late-requirement rework edges per kLOC: none
  1.02, 3.x 0.84. Edges discovery could have prevented: none 0.41, 3.x 0.33. Both gaps are within
  noise.
- **The classifier judged most late requirements unknowable in advance.** Typical reasons: "learned
  from operating it", "a new consumer arrived later".

### 5. Throughput

Merged source kLOC per active day since 2026-09-01. Repo F's integration-branch landings exclude
everything its `develop` already contains, so nothing is counted twice:
- repo F (ungoverned) 6.7
- the two largest governed repos 6.7 and 6.6
- pooled: ungoverned 4.7, governed 4.4

The slowness the owner feels does not show up in merged output for the large repos. Its cost lies
elsewhere: wall clock per change, owner attention, tokens. None of these were measured here.

## What it means

1. **Low confidence in repo F is not supported by its defect density.** At what blind code reading
   can detect, the fast work is no worse than governed work. The confidence gap is about
   *visibility*: nothing independent looked at it, so nothing vouches for it.
2. **This study cannot show that 3.4–3.7 governance improves defect density.** That is not proof
   that it doesn't. The CI is wide, and the review measures only defects that reading can detect.
3. **One fresh Opus pass over merged, Critic-reviewed code still found verified defects in 9 of 25
   governed items.** Together with result 3, this suggests that multi-round, same-lens review
   saturates. A single independent pass with different framing finds what the rounds missed.
   This is a hypothesis, not a result.
4. **Up-front discovery is not where the requirements value is.** Late requirements drive the most
   rework, as `documentation/purpose.md` predicts ("it is not possible to elicit every important
   requirement before starting"). But about 4 in 5 non-fix rewrites were judged not preventable by asking
   earlier, and governed repos show no measurable reduction. The leverage is in making a late
   requirement **cheap to absorb**: capture it the moment it surfaces, find everything it touches,
   and keep later work bound to it. That is the record and the audit. More discovery up front is
   not it.

## Recommendations

- **Fast repos.** Buy back confidence with one blind, verified Opus review per PR, the same recipe
  as here, at about 2 agent runs per 400 lines. Concentrate it on high-stakes work. Add integration tests for the escape classes that
  reading misses.
- **Prawduct.** Treat the tax as unproven benefit, not as proven waste. Cut the cost the
  2026-10-02 audit already priced: empty verify rounds, the p90 round count, and notes that are
  accepted rather than fixed. Test the hypothesis in "What it means" point 3: swap later review
  rounds for one fresh-framing pass, then re-measure.
- **Prawduct, where to invest** (what models will not subsume):
  - absorbing late requirements: capture, impact walk, binding later work
  - a record of each product's environment and external contracts, plus evidence of the right
    kind (shown against the real dependency) for changes that touch them
  - coherence across sessions and people
  - auditing delivered work against the record
  - running `escape.py` continuously as the signal for retiring or re-pricing mechanisms
- **Do not expand up-front discovery** on the strength of this study. Section 4 gives no evidence
  that it pays.
- **Measure the tax properly next.** Track wall clock per merged change and tokens per change
  (`prawduct-hook stats` C2, ccusage), not kLOC.
- **Re-run `escape.py` after 2026-11-10.** It will then score the actual 30-day escapes of repo F's
  October batch. This is the definitive check on that batch, and costs nothing.

## Limits

- **Sample size:** n=25 per group.
- **Reviewer coverage:** the reviewer reads code. 0 of 8 known escapes were caught in the pilot.
- **Blinding leaks:** `prawduct:allow` pragmas appear in both groups.
- **Assignment is not random:** mode tracks repo, owner, product and age.
- **Repo F's integration branches** come from PR base refs, not from `develop`.
- **Sonnet** was tested and rejected as a reviewer: 2 vs 9 verified defects on the same items, and
  0 found in 20 items.
- **Cost of the study:** 140 agent runs.

## Re-deriving

The tooling is public, in `.prawduct/research/escape-2026-10/`. The data it reads and writes is
private: the repo list, landings, sample specs and keys, and every review and classification
result stay on the owner's machine, because they describe private code. Ask the owner for access.
With the data directory `<data>` and bare clones of its repo list in `<clones>`:

1. `./test_escape.sh`: known-answer test for the rework detector, including `--branch`.
2. `python3 escape.py <clones> <data>/landings.jsonl`: rework per landing, on `develop` or the
   default branch (about 25 minutes). Add `--branch owner/repo=BRANCH` to also trace an unmerged
   integration branch. Use that for repo F's October work once its 30-day window has closed (#987).
3. `python3 branch_landings.py …`: repo F's integration-branch landings as review candidates
   (`<data>/fast_landings.jsonl`). This reproduces the study's file byte for byte; its docstring
   gives the arguments used.
4. Classification inputs:
   - `python3 build_batches.py edges <clones> <data>/landings.jsonl <edges> <data>/fixclass_key.json`
   - after the fix classification, `build_batches.py catch …` and `build_batches.py cause …`
   These reproduce the study's batches byte for byte.
5. Review items: `python3 sample_windows.py <clones> <landings> <spec> <sample>`, then
   `python3 make_items.py <clones> <sample> <items> <key>`.
6. Agent passes, with the Workflow tool:
   - `wf-fix-classification.js` (args `dir`, `batches`)
   - `wf-retro-review-pilot.js` (args `root`, `items`; an item `{item, calibrate: true}` also gets
     an Opus review)
   - `wf-retro-review.js` (args `root`, `items`, `catchFiles`)
   - `wf-cause-classification.js` (args `dir`, `batches`)
   The model runs themselves are not deterministic. Re-running them gives a fresh measurement,
   not the same one.
7. `python3 stats.py <data>`: prints every computed number in this artifact from the recorded
   results. Two figures are not computed:
   - "0 of 8 known escapes caught": a reading of each calibration item's findings against its
     known fix.
   - the agent-run count: from the workflow logs.
