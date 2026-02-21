# Observation Contribution Flow (Product Repos Only)

When a product repo has uncontributed observations, the Orchestrator facilitates submission. This flow is triggered during session resumption (when `UNCONTRIBUTED_OBSERVATIONS > 0`) or on user request.

**Steps:**

1. **Check.** Run `tools/contribute-observations.sh --check <product-dir>` to get the count and file list.
2. **Present.** Read the observation files and present a summary in conversation — observation types, severities, and key descriptions.
3. **Privacy notice.** Tell the user: "These will be posted as a public GitHub issue on the framework repo. Please review for any information you don't want shared publicly."
4. **User review.** If the user wants to edit observations before contributing, make the edits via Claude (modify the YAML files directly). If the user wants to skip some files, note which ones to exclude.
5. **Submit.** Run `tools/contribute-observations.sh --submit <product-dir> [approved-files...]` with only the user-approved files. If `gh` is not available (exit 2), show the user the install instructions from stderr and offer `--format` as a fallback.
6. **Report.** Show the issue URL to the user.
7. **Partial submission.** If the user skipped some files, those remain uncontributed and will be surfaced again next session. No pressure.

**Self-hosted note:** The framework repo's own observations are acted on directly — they never go through this flow. `--check` returns `self_hosted: true` and count 0.
