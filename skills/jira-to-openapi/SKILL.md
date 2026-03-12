---
name: jira-to-openapi
description: >
  Use this skill whenever the user wants to generate an OpenAPI 3.0 specification
  from a JIRA story. Trigger on any of these phrases or contexts:
  "generate spec from JIRA", "create OpenAPI from story", "jira to openapi",
  "generate API spec for SCRUM-XX", "turn this story into a spec",
  "produce OpenAPI YAML from issue", "spec from ticket", "read JIRA story and generate spec".
  Also trigger if the user provides a JIRA issue key (e.g. SCRUM-10, PROJ-42) and asks
  for a spec, documentation, or API definition. Use this skill even if the user just says
  "generate the spec" and a JIRA key is visible in the conversation context.
---

# JIRA → OpenAPI Specification Generator

This skill fetches a JIRA story created with the API-First template (8 custom fields)
and generates a complete, valid OpenAPI 3.0 YAML spec from it.

## Prerequisites

Set these environment variables:
```
JIRA_BASE_URL    e.g. https://acme.atlassian.net
JIRA_EMAIL       admin email
JIRA_API_TOKEN   Personal Access Token
JIRA_PROJECT     project key (e.g. SCRUM)
```

Field IDs are read from `scripts/jira_field_config.json` in the working repo,
or resolved live from the JIRA API if that file is absent.

## How to run

The bundled script handles everything. Run it with:

```bash
python skills/jira-to-openapi/scripts/generate_spec.py <ISSUE_KEY> [--output <path>] [--format json]
```

**Arguments:**
- `<ISSUE_KEY>` — required. E.g. `SCRUM-10`.
- `--output <path>` — defaults to `<ISSUE_KEY>-openapi.yaml` in CWD.
- `--format json` — output JSON instead of YAML.
- `--path /endpoint` — override the endpoint path if auto-detection fails.

**Example:**
```bash
export JIRA_BASE_URL=https://playground-best-team.atlassian.net
export JIRA_EMAIL=aurora.courses.ch@gmail.com
export JIRA_API_TOKEN=<token>
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-10
```

The script prints the full spec to stdout AND saves it to the output file.

## What the script does

1. **Fetches the issue** via `GET /rest/api/3/issue/{issueKey}`
2. **Reads 8 custom fields** (ADF textarea fields have text extracted automatically):
   - `API Purpose` → `info.description`
   - `API HTTP Method` → HTTP verb in the paths section
   - `API Request Fields` → `requestBody` schema properties
   - `API Validation Rules` → appended to the operation description
   - `API Consumers` → `info.x-consumers`
   - `API Error Scenarios` → `responses` (parsed as `STATUS — reason` lines)
   - `API Existing Contract` → `info.x-existing-contract`
   - `API Change Type` → `info.x-change-type`
3. **Parses the endpoint path** from the issue summary (extracts the first `/word/…` segment)
4. **Builds the OpenAPI 3.0 document** and writes YAML or JSON

## Field parsing rules

**API Request Fields** — one field per line:
```
name | type | required/optional | validation note
```
Supported types: `integer`, `string`, `boolean`, `array`, `object`, `uuid`, `date`, `url`

**API Error Scenarios** — one per line:
```
400 — invalid input
404 — resource not found
```
A `200 OK` response is always included automatically.

**Endpoint path** — scanned from the summary for a `/word/…` pattern.
Falls back to `/api/<resource>` derived from the summary words.

## Output structure

```yaml
openapi: "3.0.3"
info:
  title: <issue summary>
  description: <API Purpose>
  version: "1.0.0"
  x-jira-issue: <KEY>
  x-change-type: <Additive|Breaking>
  x-consumers: <API Consumers>
servers:
  - url: https://api.example.com/v1
paths:
  /endpoint:
    post:
      requestBody:
        content:
          application/json:
            schema: { $ref: '#/components/schemas/ResourceRequest' }
      responses:
        '200': { description: Successful response }
        '400': { description: ... }
components:
  schemas:
    ResourceRequest:   { type: object, properties: ... }
    ResourceResponse:  { type: object, properties: ... }
  securitySchemes:
    BearerAuth: { type: http, scheme: bearer }
```

## After generation

1. Open the generated file in [Swagger Editor](https://editor.swagger.io/) to validate
2. Commit alongside a link to the JIRA story
3. If `API Existing Contract` is set, diff against it to find breaking changes

## Troubleshooting

| Error | Fix |
|---|---|
| `401 Unauthorized` | Check `JIRA_EMAIL` / `JIRA_API_TOKEN` |
| `404 Not Found` | Verify the issue key exists |
| `Field IDs not found` | Run `scripts/jira_form_setup.py` first |
| `No path found in summary` | Add `--path /your/endpoint` |
| `ModuleNotFoundError: requests` | `pip install requests pyyaml` |
