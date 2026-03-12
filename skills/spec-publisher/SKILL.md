---
name: spec-publisher
description: >
  Use this skill whenever the user wants to publish an approved API specification
  to GitHub. Trigger on any of these phrases or contexts:
  "publish spec", "publish approved spec", "merge spec to main", "open PR for spec",
  "push spec to GitHub", "create PR for SCRUM-XX", "spec is approved publish it",
  "update swagger.yaml", "publish the api spec", "create pull request for spec",
  "the subtask is done publish it".
  Also trigger if the user provides a JIRA issue key (e.g. SCRUM-10, PROJ-42) and
  asks to publish, merge, or create a PR for the spec.
---

# Spec Publisher

This skill checks whether a JIRA story's spec has been approved (subtask in Done
with label `api-spec-approved`), then re-generates the endpoint spec, merges it
into the existing `specs/swagger.yaml` in GitHub, bumps the version, and opens a
Pull Request.

## Prerequisites

Set these environment variables:
```bash
export JIRA_BASE_URL=https://acme.atlassian.net
export JIRA_EMAIL=you@example.com
export JIRA_API_TOKEN=<personal-access-token>
export GITHUB_TOKEN=<github-personal-access-token>   # needs repo scope
```

Python deps: `requests`, `pyyaml` — already installed in `/tmp/jira_venv`.

## How to run

```bash
# Activate the project venv first
source /tmp/jira_venv/bin/activate

# Publish spec for a JIRA story (checks for approved subtask automatically)
python skills/spec-publisher/scripts/publish_spec.py SCRUM-42

# Dry run — show what would change without creating a branch / PR
python skills/spec-publisher/scripts/publish_spec.py SCRUM-42 --dry-run

# Override the GitHub repo target
python skills/spec-publisher/scripts/publish_spec.py SCRUM-42 \
    --repo EdytaLys/api-spec-task-manager

# Override the spec file path inside the repo
python skills/spec-publisher/scripts/publish_spec.py SCRUM-42 \
    --spec-path specs/swagger.yaml

# Override the base branch (default: main)
python skills/spec-publisher/scripts/publish_spec.py SCRUM-42 \
    --base-branch develop
```

## Arguments

| Flag | Description |
|---|---|
| `ISSUE_KEY` | **Required.** JIRA parent story key e.g. `SCRUM-42` |
| `--repo` | GitHub repo in `owner/name` format (default: `EdytaLys/api-spec-task-manager`) |
| `--spec-path` | Path to the spec file inside the repo (default: `specs/swagger.yaml`) |
| `--base-branch` | Branch to merge the PR into (default: `main`) |
| `--dry-run` | Print the merged spec and change report without pushing to GitHub |

## What the script does

1. **Fetches the JIRA parent story** via REST API
2. **Finds an approved subtask** — a child issue (or linked issue) that is:
   - Status in `{Done, Closed, Resolved, Complete, Completed}` (case-insensitive)
   - Has the label `api-spec-approved`
3. **Aborts** with a clear message if no approved subtask is found
4. **Re-generates the endpoint spec** from the parent story using the same logic
   as the `jira-to-openapi` skill
5. **Fetches `specs/swagger.yaml`** from the target GitHub repo (default branch)
6. **Diffs and merges** the new endpoint into the existing spec
7. **Bumps the version**:
   - Breaking changes → major bump (`x.0.0`)
   - Additive changes only → minor bump (`x.y.0`)
   - No changes → patch bump (`x.y.z`)
8. **Creates a feature branch** named `api-spec/{key-lower}-{path-slug}`
9. **Commits** the updated spec file to the feature branch
10. **Opens a Pull Request** with:
    - Title: `[{KEY}] Update API spec — {summary}`
    - Body: change report + Swagger-pasteable endpoint YAML

## Example output

```
✓ Found approved subtask: SCRUM-20 (Done, label: api-spec-approved)
  Re-generating spec from SCRUM-15...
  Fetching existing spec: specs/swagger.yaml @ main
  Diff: PATCH /api/tasks/{id} — NEW endpoint (additive)
  Version bump: 1.0.0 → 1.1.0
  Creating branch: api-spec/scrum-15-api-tasks-id
  Committing: specs/swagger.yaml
✓ Pull Request opened: https://github.com/EdytaLys/api-spec-task-manager/pull/7
```

## Troubleshooting

| Error | Fix |
|---|---|
| `No approved subtask found` | Ensure the subtask status is Done and has label `api-spec-approved` |
| `401 Unauthorized (JIRA)` | Check `JIRA_EMAIL` / `JIRA_API_TOKEN` |
| `401 Unauthorized (GitHub)` | Check `GITHUB_TOKEN` (needs `repo` scope) |
| `404 — spec file not found` | Check `--spec-path` matches the file path in the repo |
| `Branch already exists` | Delete the branch on GitHub or the script will reuse it |
| `ModuleNotFoundError: requests` | `pip install requests pyyaml` |
