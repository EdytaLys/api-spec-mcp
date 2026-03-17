---
name: story-to-spec
description: >
  Use this skill whenever the user wants to generate or update an OpenAPI specification
  from a JIRA user story. Trigger on any of these phrases or contexts:
  "generate spec from story", "story to spec", "story to openapi", "create spec from JIRA",
  "generate API spec from SCRUM-XX", "turn this story into an openapi spec",
  "create openapi from ticket", "spec from user story", "read JIRA and generate API spec",
  "update spec from story", "new api spec from jira".
  The user must provide two arguments: an existing OpenAPI YAML file path (local or GitHub URL)
  and a JIRA issue key (e.g. SCRUM-42). The skill reads the JIRA story, analyses requirements
  against the existing spec, generates a new or updated OpenAPI 3.0.3 specification, and posts
  the result as a JIRA comment — including breaking change analysis and missing information
  if the story is incomplete.
---

# Story → OpenAPI Spec Generator

This skill reads a JIRA user story and an existing OpenAPI YAML spec, then generates
a new or updated OpenAPI 3.0.3 specification that follows the conventions already
established in the existing spec (authentication, naming, schemas, error patterns).

The result is posted as a **JIRA comment** on the story with:
- The generated OpenAPI YAML
- A breaking-change analysis
- Version bump recommendation
- OR a list of missing information if the story is incomplete

## Prerequisites

The following MCP tools must be available (Atlassian MCP server):
- `getJiraIssue` — to read the JIRA story
- `addCommentToJiraIssue` — to post the result

The existing OpenAPI YAML must be accessible via:
- A local file path, OR
- A GitHub URL (blob or raw)

## How to run

```
/story-to-spec <existing-yaml-path-or-url> <JIRA-ISSUE-KEY>
```

### Examples

```bash
# Local YAML file + JIRA story
/story-to-spec ./specs/task-manager-openapi.yaml SCRUM-42

# GitHub URL + JIRA story
/story-to-spec https://github.com/EdytaLys/api-spec-task-manager/blob/main/specs/task-manager-openapi.yaml SCRUM-15

# Arguments can be in any order
/story-to-spec SCRUM-7 ./SCRUM-15-openapi.yaml
```

## What the skill does

### Step 1 — Parse arguments
Extracts the YAML file path and JIRA issue key from user input. The JIRA key matches
`[A-Z]+-\d+`; everything else is treated as the YAML path/URL.

### Step 2 — Read the JIRA story
Fetches the issue via `getJiraIssue` and parses:
- **Summary** (title line)
- **Description sections**: endpoints, request fields, validation rules, error scenarios,
  acceptance criteria, required changes, context
- **Labels**: `new-api`, `update-existing-api`, `api-spec`, etc.
- **Patterns**: `METHOD /path`, `NNN - description`, `field, type, required/optional`,
  JSON body examples, user-story format ("As a … I want … So that …")

### Step 3 — Read the existing OpenAPI YAML
Loads the spec and learns:
- Path naming conventions, operationId patterns, tag conventions
- Pagination parameters (page/size/sort), path parameter types
- Authentication / security schemes
- Response patterns: success + error response structures
- Schema naming: DTO patterns (`CreateDTO`, `UpdateDTO`, `Response`), common fields
- Server URLs and current version

### Step 4 — Assess completeness
Checks whether the story provides enough detail:
- At least one endpoint (method + path)
- For POST/PUT/PATCH: some idea of request fields
- Expected success response type

If insufficient → posts a comment listing exactly what's missing (Step 7b).

### Step 5 — Generate the specification

#### 5a. New API (path not in existing spec)
Generates a **complete OpenAPI 3.0.3 spec** that:
- Follows the existing spec's naming, auth, parameter, and DTO conventions
- Reuses shared schemas via `$ref` (ErrorResponse, etc.)
- Includes default error responses from existing endpoints (401, 500, …)
- Applies PATCH partial-update convention (all fields optional)
- Adds pagination if the endpoint returns a list

#### 5b. Update existing API (path already in spec)
Generates a spec **for just that endpoint** with requested changes:
- Starts from the existing endpoint definition
- Applies ONLY the changes described in the story
- **Preserves** all existing error responses, validation rules, required/optional
  designations, security, and parameters unless the story *explicitly* removes them

### Step 6 — Breaking-change analysis

| Change type | Classification |
|---|---|
| Remove endpoint / field / response code | Breaking (major bump) |
| Change field type | Breaking |
| Make optional → required | Breaking |
| Change auth scheme | Breaking |
| Add new endpoint | Additive (minor bump) |
| Add optional field / response code / query param | Additive |
| Relax required → optional | Additive |

### Step 7 — Post JIRA comment

#### 7a. Spec generated successfully

Posts a comment containing:
- **Change Summary**: type, endpoint, breaking yes/no, version recommendation
- **Breaking Change Analysis**: per-change classification with explanation
- **Generated OpenAPI Specification**: full YAML in a code block
- **Validation Rules Applied**: how each story rule maps to the spec
- **Next Steps**: review, validate at swagger.io, merge

#### 7b. Insufficient information

Posts a comment listing:
- Each specific missing item with guidance on what to provide
- An example format showing how to structure the story details

## Supported story formats

The skill handles multiple story formats:

### Structured sections (recommended)
```
New endpoint: POST /api/resources

Request fields:
* name, string, required
* description, string, optional

Validation rules:
* name must be unique (409 Conflict)

Error scenarios:
* 400 - Invalid field value
* 404 - Resource not found
```

### Free-text / user-story format
```
As a developer
I want to create an endpoint to retrieve all addresses
So that I can identify which addresses are marked as shipping address

New endpoint: /orders/v1.0/consumers/{consumerId}/carts/{cartId}/addresses
```

### Technical note format
```
A new endpoint has to be exposed
Section: orders-api
Name: PATCH /orders/v1.0/{consumerId}/orders/{orderId}
with body: { "status": "CANCELLED" }
```

## Important rules

1. Always generate valid OpenAPI 3.0.3 YAML
2. Never invent business logic not in the story — list ambiguities as questions
3. Reuse schemas and patterns from the existing spec
4. For updates: when in doubt, preserve existing behavior
5. Use `$ref` for schemas, don't inline large objects
6. Include `x-jira-issue: <KEY>` in the info section
7. Keep operationId values unique and following existing conventions
8. Always include the standard security scheme from the existing spec

## Troubleshooting

| Issue | Fix |
|---|---|
| `getJiraIssue` fails with 401 | Check Atlassian MCP server credentials |
| `getJiraIssue` fails with 404 | Verify the issue key exists |
| Cannot read YAML from GitHub | Check the URL is correct; for private repos ensure GITHUB_TOKEN is set |
| Comment not posted | Check Atlassian MCP server has write permissions |
| Story has no useful sections | Use the structured format shown above |
