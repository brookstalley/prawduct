---
paths:
  - "plugin/skills/pr/**"
  - "plugin/lib/pr_payload.py"
  - "plugin/agents/pr-reviewer.md"
---
# Learnings — pr

- A flow step recording status/bookkeeping must ride IN the PR doing the work — post-merge steps break protected-branch consumers. Non-commit bookkeeping (API status) runs AT the merge, before the debt records are deleted
- GitHub says CONFLICTING but a local trial merge is CLEAN: suspect a .gitattributes merge driver (change-log.md is merge=union) the server ignores — push the union resolution as a real sync commit. Tell: `git merge-tree --write-tree` exits 0, PR red
- After the last commit, re-check the remote ref IS HEAD before creating or merging a PR — the gate reads local HEAD, CI grades the pushed tip, the merge succeeds; only `git branch -d` notices, post-merge. Tell: you pushed once and committed after
