# Execution Intelligence

Last audited against the live repository: `2026-03-26`

## What this artifact is

The execution-intelligence surface is a snapshot-driven reporting view for operators and leadership. It combines:

- Paperclip project issues, agents, and issue comments
- the current git worktree diff and recent commit history
- repo-relative file paths and hunk ranges for the most important live changes

The v1 route lives at:

- `/webapp/execution-intelligence`

## How to refresh it

From `web-app/`:

```bash
npm run generate:execution-intelligence
```

Or from the repo root:

```bash
python scripts/generate_execution_intelligence_snapshot.py
```

That command writes:

- `web-app/src/data/execution-intelligence-snapshot.json`

The frontend imports that JSON at build time, so the route does not need live Paperclip credentials in the browser.

## Evidence sources

The generator currently reads:

- `GET /api/issues/{PAPERCLIP_TASK_ID}/heartbeat-context`
- `GET /api/companies/{companyId}/dashboard`
- `GET /api/companies/{companyId}/agents`
- `GET /api/companies/{companyId}/issues?projectId={projectId}`
- `GET /api/issues/{issueId}/comments`
- `git status --porcelain=v1 --untracked-files=all`
- `git diff --numstat --`
- `git diff --unified=0 --no-color --`
- `git log -n 12 --date=iso --pretty=...`

## Current reporting limits

- There is no first-class issue-to-commit linkage yet, so issue-to-file attribution still depends on issue comments and git proximity.
- Completion comments are richer for some issues than others. Where comments do not contain path-level evidence, the dashboard marks the summary as inferred from the diff.
- The route shows the live worktree. Until changes are committed, commit references explain recent repo history but not every active modification.
