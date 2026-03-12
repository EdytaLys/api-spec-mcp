---
name: repo-to-openapi
description: >
  Use this skill whenever the user wants to generate an OpenAPI 3.0 specification
  by scanning a GitHub repository or a local codebase directory. Trigger on any of
  these phrases or contexts: "scan repo and generate spec", "generate OpenAPI from
  GitHub", "repo to openapi", "create API spec from repository", "scan codebase for
  endpoints", "generate spec from source code", "extract API from repo", "analyse
  endpoints in repo", "scan local project for endpoints", "generate spec from this
  folder", "create OpenAPI from local code".
  Also trigger if the user provides a GitHub URL or a local path and asks for a spec,
  API documentation, or endpoint list. Use this skill even if the user just says
  "generate the spec" and a GitHub URL or local repo path is visible in the conversation.
  The output is intentionally compatible with the jira-to-openapi skill — same
  OpenAPI 3.0.3 format, BearerAuth security scheme, and x-* extension conventions —
  so specs from both skills can be used together in JIRA API-First workflows.
---

# Repo → OpenAPI Specification Scanner

This skill clones a GitHub repository (via the GitHub API — no local `git` required),
detects the backend framework, parses all REST endpoint definitions from source code,
and generates a complete OpenAPI 3.0.3 YAML spec.

**Output is compatible with the `jira-to-openapi` skill** — same schema conventions,
security scheme (`BearerAuth / JWT`), and `x-*` extension fields — so the two specs
can be compared or merged in JIRA API-First workflows.

## Supported frameworks

| Framework | Language | Detection |
|---|---|---|
| Spring Boot | Java | `pom.xml` with `spring-boot` dependency |
| FastAPI | Python | `requirements.txt` containing `fastapi` |
| Flask | Python | `requirements.txt` containing `flask` |
| Express / Fastify | Node.js | `package.json` dependencies |
| NestJS | Node.js | `@nestjs/core` in `package.json` |

## Prerequisites

Create and activate a Python virtual environment, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install requests pyyaml
```

Optional — set `GITHUB_TOKEN` env var to raise the GitHub API rate limit from
60 to 5000 requests/hour (needed for large repos):

```bash
export GITHUB_TOKEN=ghp_...
```

## How to run

The first argument is either a **GitHub URL** or a **local directory path** (absolute or relative, including `.` for the current directory).

```bash
python skills/repo-to-openapi/scripts/scan_repo.py <SOURCE> [options]
```

**Source — pick one:**
| What you pass | Behaviour |
|---|---|
| `https://github.com/owner/repo` | Fetches files via GitHub API (no local clone needed) |
| `/path/to/local/repo` | Reads files directly from the local filesystem |
| `.` | Scans the current working directory |

**Common arguments:**
- `--branch <name>` — branch to scan. Remote: defaults to repo's default branch. Local git repo: reads that branch's content via `git show` without changing your checkout; defaults to the current branch.
- `--base-url <url>` — override production server URL (auto-detected from README if omitted; local repos default to `http://localhost:8080`)
- `--output <path>` — local output file path (default: `<repo-name>-openapi.yaml` in CWD)
- `--format json` — output JSON instead of YAML

**Upload to another repo** (requires `GITHUB_TOKEN` with write access to the target):
- `--upload-to <REPO_URL>` — GitHub repo URL to push the spec into
- `--upload-path <PATH>` — path inside the target repo (default: `specs/<filename>`)
- `--upload-branch <BRANCH>` — base branch for the PR (default: `main`)
- `--upload-message <MSG>` — commit message for the file (default: auto-generated)
- `--pr-title <TITLE>` — custom PR title (default: auto-generated)
- `--pr-body <BODY>` — custom PR description (default: auto-generated)
- `--no-pr` — push directly to `--upload-branch` instead of opening a PR

By default, the spec is committed to a new branch (`chore/openapi-spec-<name>`) and a PR is opened against `--upload-branch`. Use `--no-pr` to skip the PR and push directly.

**Examples:**

Remote repo, scan only:
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install requests pyyaml
export GITHUB_TOKEN=ghp_yourtoken
python skills/repo-to-openapi/scripts/scan_repo.py \
  https://github.com/EdytaLys/task_manager_with_copilot \
  --base-url https://task-manager-with-copilot-server-535572860478.europe-west1.run.app
```

Local directory:
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install requests pyyaml
python skills/repo-to-openapi/scripts/scan_repo.py \
  /path/to/my-api-project \
  --base-url https://my-api.example.com/v1
```

Current directory:
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install requests pyyaml
python skills/repo-to-openapi/scripts/scan_repo.py .
```

Scan remote repo, upload spec, and open a PR (default behaviour):
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install requests pyyaml
export GITHUB_TOKEN=ghp_yourtoken   # needs read on source + write on target
python skills/repo-to-openapi/scripts/scan_repo.py \
  https://github.com/EdytaLys/task_manager_with_copilot \
  --upload-to https://github.com/EdytaLys/api-specs \
  --upload-path specs/task-manager-openapi.yaml \
  --upload-branch main
# → commits to chore/openapi-spec-task-manager-openapi-yaml
# → opens PR: chore/openapi-spec-... → main
```

Push directly without a PR:
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install requests pyyaml
python skills/repo-to-openapi/scripts/scan_repo.py \
  https://github.com/EdytaLys/task_manager_with_copilot \
  --upload-to https://github.com/EdytaLys/api-specs \
  --upload-path specs/task-manager-openapi.yaml \
  --no-pr
```

Scan local directory, upload, and open PR with custom title:
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install requests pyyaml
export GITHUB_TOKEN=ghp_yourtoken
python skills/repo-to-openapi/scripts/scan_repo.py \
  /path/to/my-api-project \
  --upload-to https://github.com/EdytaLys/api-specs \
  --upload-path specs/my-api-openapi.yaml \
  --pr-title "feat: add OpenAPI spec for my-api"
```

The script prints the full spec to stdout AND saves it to the output file.

## What the script does

1. **Fetches the repo file tree** via GitHub API (`/git/trees/{branch}?recursive=1`)
2. **Detects the framework** from `pom.xml`, `requirements.txt`, `package.json`
3. **Scans source files** for REST endpoint annotations/decorators:
   - Spring Boot: `@GetMapping`, `@PostMapping`, `@PutMapping`, `@DeleteMapping`, `@PatchMapping`
   - FastAPI: `@app.get`, `@router.post`, etc.
   - Flask: `@app.route(..., methods=[...])`
   - Express/Fastify: `app.get(path, ...)`, `router.post(path, ...)`
4. **Extracts request/response shapes** from DTO classes and type annotations
5. **Builds the OpenAPI 3.0.3 document** and writes YAML or JSON

## Output structure

```yaml
openapi: "3.0.3"
info:
  title: <repo name formatted as title>
  description: <GitHub repo description>
  version: "1.0.0"
  x-source-repo: <github url>
  x-scanned-at: <ISO timestamp>
servers:
  - url: <detected or provided production URL>
    description: Production
  - url: http://localhost:8080
    description: Local development
paths:
  /api/tasks:
    get:
      operationId: getAllTasks
      tags: [Tasks]
      responses:
        '200': { description: Successful response, content: ... }
        '401': { description: Unauthorized }
        '500': { description: Internal server error }
    post:
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/TaskCreateDTO' }
      responses:
        '201': { description: Created }
        '400': { description: Bad request — validation error }
        '401': { description: Unauthorized }
        '409': { description: Conflict — resource already exists }
        '500': { description: Internal server error }
components:
  schemas:
    TaskCreateDTO:
      type: object
      properties:
        title:       { type: string }
        description: { type: string }
        status:      { type: string }
        dueDate:     { type: string, format: date-time }
      required: [title, status]
    SuccessResponse:   { type: object, properties: { data: {}, timestamp: { type: string, format: date-time } } }
    ErrorResponse:     { type: object, properties: { message: { type: string }, timestamp: { type: string, format: date-time } } }
  securitySchemes:
    BearerAuth: { type: http, scheme: bearer, bearerFormat: JWT }
security:
  - BearerAuth: []
```

## Compatibility with jira-to-openapi

Both skills produce the same:
- OpenAPI version (`3.0.3`)
- Security scheme (`BearerAuth` / JWT Bearer)
- Global `security` block
- Schema style (object → properties + required array)
- `x-*` extension field convention

This means a JIRA story spec (from `jira-to-openapi`) and a repo spec (from this skill)
can be directly compared to validate that the implementation matches the contract, or
merged to enrich either spec with information from the other.

## After generation

1. Open the generated file in [Swagger Editor](https://editor.swagger.io/) to validate
2. Compare against a JIRA story spec to check for contract drift
3. Commit alongside a link to the source repo
4. If the repo already has a JIRA issue with `API Existing Contract` set, diff against it

## Troubleshooting

| Error | Fix |
|---|---|
| `403 rate limit exceeded` | Set `GITHUB_TOKEN` env var |
| `404 repo not found` | Check the URL and that the repo is public (or token has access) |
| `0 endpoints found` | Framework may not be auto-detected; check `--branch` or open an issue |
| `ModuleNotFoundError: requests` | `pip install requests pyyaml` |
| Wrong base URL in spec | Pass `--base-url https://your-api.example.com/v1` |
