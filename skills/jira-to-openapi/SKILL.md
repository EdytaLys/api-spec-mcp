---
name: jira-to-openapi
description: >
  Use this skill whenever the user wants to generate an OpenAPI 3.0 specification
  from a JIRA story. Trigger on any of these phrases or contexts:
  "generate spec from JIRA", "create OpenAPI from story", "jira to openapi",
  "generate API spec for SCRUM-XX", "turn this story into a spec",
  "produce OpenAPI YAML from issue", "spec from ticket", "read JIRA story and generate spec",
  "check if endpoint already exists in spec", "what changed", "are there breaking changes".
  Also trigger if the user provides a JIRA issue key (e.g. SCRUM-10, PROJ-42) and asks
  for a spec, documentation, API definition, or a diff against an existing spec.
  Use this skill even if the user just says "generate the spec" and a JIRA key is
  visible in the conversation context.
---

# JIRA → OpenAPI Specification Generator

This skill fetches a JIRA story created with the API-First template and generates a
complete, valid OpenAPI 3.0 YAML spec from it.

If an existing spec URL is provided (GitHub or local), the script also:
- Checks whether the new endpoint already exists in the spec
- Computes a detailed diff (added/removed/changed fields and responses)
- Flags **breaking vs. additive** changes
- Outputs a plain-English change report
- Produces a **merged** spec with the new endpoint integrated and the version bumped automatically
- Produces a **standalone endpoint-only spec** ready to paste into Swagger Editor
- Optionally **creates a JIRA subtask** containing the change report and the Swagger-ready YAML

## Prerequisites

Set these environment variables:
```bash
export JIRA_BASE_URL=https://acme.atlassian.net
export JIRA_EMAIL=you@example.com
export JIRA_API_TOKEN=<personal-access-token>
export JIRA_PROJECT=SCRUM             # optional, default SCRUM
export GITHUB_TOKEN=<token>           # optional, for private spec repos
```

Field IDs are read from `scripts/jira_field_config.json` in the working repo,
or resolved live from the JIRA API if that file is absent.

## How to run

```bash
# Activate the project venv first (only needed once per session)
source /tmp/jira_venv/bin/activate   # or: python3 -m venv .venv && source .venv/bin/activate
pip install requests pyyaml

# Basic: generate spec from a JIRA story
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-42

# With output file name
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-42 --output specs/patch-tasks.yaml

# With JSON output
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-42 --format json

# Override path if auto-detection fails
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-42 --path /api/tasks/{id}

# Compare against existing spec and produce a change report
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-42 \
    --existing-spec https://github.com/EdytaLys/api-spec-task-manager/blob/main/specs/task-manager-openapi.yaml

# Print change report only, without writing the spec file
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-42 \
    --existing-spec <url> --report-only

# Create a JIRA subtask with the change report and the Swagger-ready spec
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-42 \
    --existing-spec <url> --create-subtask

# Create subtask under a different project
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-42 \
    --existing-spec <url> --create-subtask --project PROJ
```

## Arguments

| Flag | Description |
|---|---|
| `ISSUE_KEY` | **Required.** JIRA issue key e.g. `SCRUM-42` |
| `--output`, `-o` | Output file path (default: `<KEY>-openapi.yaml`) |
| `--format` | `yaml` (default) or `json` |
| `--path` | Override auto-detected endpoint path |
| `--existing-spec` | GitHub blob URL, raw URL, or local path to the current spec |
| `--report-only` | Print change report without writing the spec file |
| `--create-subtask` | Create a JIRA subtask with the change report and Swagger-ready YAML |
| `--project` | JIRA project key for the subtask (default: `SCRUM`) |

## Output files

Every run produces **two spec files** plus a change report:

| File | Contents |
|---|---|
| `<KEY>-endpoint-only.yaml` | ✅ **Swagger-pasteable** — single endpoint, complete OpenAPI 3.0.3 doc |
| `<KEY>-openapi.yaml` | Full merged spec (all endpoints from existing spec + new one) |
| `<KEY>-openapi.change-report.txt` | Plain-English change report |

The endpoint-only YAML is also printed to **stdout** for easy copy-paste, and is embedded
verbatim in the JIRA subtask (if `--create-subtask` is used).

## Supported story template formats

### New template (comma-delimited, free-text)
```
New endpoints to create
* PATCH /api/tasks/{id}

Request fields
* title, string, optional
* description, string, optional
* status, string, optional
* dueDate, date, optional

Validation rules
* null value means 'no change', not 'clear field'
* title must be unique (409 Conflict if duplicate)

Error scenarios
* 400 - Invalid field value
* 404 - Task not found
* 409 - Title already exists
```

### Classic template (pipe-delimited)
```
name | type | required/optional | validation note
```

Both formats are parsed automatically — no configuration required.

## What the script does

1. **Fetches the JIRA issue** via the REST API
2. **Reads 8 custom fields**, extracting plain text from ADF format automatically:
   - `API Purpose` → `info.description`
   - `API HTTP Method` → HTTP verb
   - `API Request Fields` → `requestBody` schema (pipe or comma format)
   - `API Validation Rules` → appended to operation description
   - `API Consumers` → `info.x-consumers`
   - `API Error Scenarios` → `responses` (parsed as `NNN — reason` lines)
   - `API Existing Contract` → existing spec URL (used if `--existing-spec` not passed)
   - `API Change Type` → `info.x-change-type`
3. **Falls back to description sections** when custom fields are empty (free-text template)
4. **Auto-detects new endpoints** — only from the "New endpoints to create" section and summary line (never from context or required-changes to avoid false positives)
5. **Fetches the existing spec** if a URL is provided (converts GitHub blob → raw URL)
6. **Diffs each endpoint** against the existing spec:
   - New endpoint → additive ✅
   - Removed/type-changed request fields → breaking ⚠️
   - New required fields → breaking ⚠️
   - New optional fields → additive ✅
   - New/removed HTTP response codes → flagged accordingly
7. **Merges** the new endpoints into the existing spec and bumps the version:
   - Breaking changes → major bump (`2.0.0`)
   - Additive changes → minor bump (`1.1.0`)
8. **Writes** three files: endpoint-only YAML, full merged YAML, and change report
9. **Creates a JIRA subtask** (if `--create-subtask`) with:
   - Per-endpoint verdict (new / modified / unchanged)
   - Full Swagger-pasteable YAML in a code block
   - Overall verdict and version bump recommendation
   - Next steps

## Example change report output

```
========================================================================
  OpenAPI Change Report — SCRUM-42
  PATCH /api/tasks/{id} — Partial update
========================================================================

  ┌─ PATCH /api/tasks/{id}
  │  ✅ NEW endpoint — this is an additive change.
  │     No existing callers will be affected.
  └────────────────────────────────────────────────────────────

------------------------------------------------------------------------
  OVERALL VERDICT
------------------------------------------------------------------------
  ✅ All changes are ADDITIVE (backward compatible).
     A minor version bump (x.y.0) is sufficient.

------------------------------------------------------------------------
  WHAT CHANGED (summary)
------------------------------------------------------------------------
  • PATCH /api/tasks/{id} — new endpoint added
```

## Output file structure

### Endpoint-only spec (`<KEY>-endpoint-only.yaml`) — paste into Swagger Editor

```yaml
openapi: "3.0.3"
info:
  title: <issue summary>
  description: <API Purpose>
  version: "1.0.0"
  x-jira-issue: SCRUM-42
servers:
  - url: https://api.example.com/v1
paths:
  /api/tasks/{id}:
    patch:
      summary: ...
      requestBody:
        content:
          application/json:
            schema: { $ref: '#/components/schemas/TaskPatchRequest' }
      responses:
        '200': { description: Successful response }
        '400': { description: Bad request }
        '404': { description: Task not found }
        '409': { description: Title already exists }
components:
  schemas:
    TaskPatchRequest:
      type: object
      properties:
        title:       { type: string }
        description: { type: string }
        status:      { type: string }
        dueDate:     { type: string, format: date }
    TaskResponse:
      type: object
      properties:
        id:          { type: string, format: uuid }
        ...
  securitySchemes:
    BearerAuth: { type: http, scheme: bearer, bearerFormat: JWT }
security:
  - BearerAuth: []
```

> **Note:** `PATCH` request schemas never include `required` fields by convention
> (partial update means all fields are optional).

## Troubleshooting

| Error | Fix |
|---|---|
| `401 Unauthorized` | Check `JIRA_EMAIL` / `JIRA_API_TOKEN` |
| `404 Not Found` | Verify the issue key exists |
| `Field IDs not found` | Run `scripts/jira_form_setup.py` first |
| `No path found in summary` | Add `--path /your/endpoint` |
| `ModuleNotFoundError: requests` | `pip install requests pyyaml` |
| `Could not fetch existing spec` | Check `GITHUB_TOKEN` or use a public URL |
| `Subtask creation failed` | Free-tier JIRA may not support Subtask type; script falls back to Task + issue link |
