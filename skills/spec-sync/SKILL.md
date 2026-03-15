---
name: spec-sync
description: >
  Use this skill whenever the user wants to synchronise controller code with
  the OpenAPI specification, or verify that existing code matches the spec.
  Trigger on phrases like: "sync controller with spec", "update controller from spec",
  "verify controller against spec", "does my controller match the API spec",
  "check if endpoint is implemented correctly", "pull latest spec and update code",
  "validate code before push", "is my implementation correct", "update method signatures".
  Also trigger when the user asks to check or update a specific endpoint like
  "update GET /api/tasks in the controller" or "verify before push".
---

# Spec Sync

Synchronises a Spring Boot REST controller with the latest OpenAPI specification.

| Mode | What it does |
|---|---|
| `verify` | Diffs spec against controller and reports mismatches — use before every push |
| `pull` | Updates controller method signatures to match the spec. Keeps method bodies intact; adds TODO stubs for missing endpoints |

## Prerequisites

```bash
# Point to your spec repo — set once, picked up automatically on every run
export SPEC_REPO_URL=https://raw.githubusercontent.com/your-org/your-spec-repo/main/specs/openapi.yaml

# Required only if the spec repo is private
export GITHUB_TOKEN=<token>

# Optional: override the default Java source scan path (default: src/main/java)
export SPEC_SYNC_SRC_DIR=backend/src/main/java

pip install requests pyyaml   # already in /tmp/jira_venv
```

Run from the root of your **Spring Boot project** (not the api-spec-mcp repo).

## How to run

```bash
source /tmp/jira_venv/bin/activate

# Verify all endpoints before pushing
python path/to/skills/spec-sync/scripts/sync_controller.py verify

# Verify a single endpoint
python .../sync_controller.py verify --endpoint GET:/api/tasks

# Preview what pull would change (dry run)
python .../sync_controller.py pull --dry-run

# Apply updates to controller signatures
python .../sync_controller.py pull

# Use a custom spec URL or source directory
python .../sync_controller.py verify \
  --spec-url https://raw.githubusercontent.com/owner/repo/main/specs/openapi.yaml \
  --src-dir src/main/java
```

## Arguments

| Argument | Description |
|---|---|
| `mode` | **Required.** `verify` or `pull` |
| `--spec-url` | OpenAPI spec URL or local path (default: canonical repo spec) |
| `--src-dir` | Java source directory to scan (default: `src/main/java`) |
| `--endpoint` | Filter to one endpoint e.g. `GET:/api/tasks` |
| `--dry-run` | (`pull` only) Show changes without writing files |

## What verify checks

- ❌ Endpoint in spec but missing from controller
- ⚠️ Query parameter missing from controller method
- ⚠️ `@Max` constraint missing (e.g. `size` param capped at 100)
- ⚠️ `@RequestBody` missing when spec has a request body
- ⚠️ Return type doesn't match spec response schema
- ⚠️ Controller method has no spec counterpart (undocumented endpoint)

## What pull updates

- Mapping annotation (`@GetMapping`, `@PostMapping`, etc.) with correct path
- Return type (`ResponseEntity<PageTask>`, `ResponseEntity<TaskResponse>`, etc.)
- Query params with `@RequestParam(defaultValue="...")` and `@Max(...)` constraints
- Path variables with `@PathVariable`
- Request body with `@RequestBody @Valid`
- Adds a TODO stub for endpoints in the spec but missing from the controller
- **Leaves existing method bodies untouched**

## Example output

### verify

```
  Fetching spec: https://raw.githubusercontent.com/...
  Spec has 5 endpoint(s)
  Scanning controllers in src/main/java
  Found 1 controller file(s)
  Found 4 mapped method(s)

❌ DELETE /api/tasks/{id} — missing from controller (expected in TasksController)
⚠️  GET /api/tasks — return type is 'List<TaskResponse>', spec expects 'PageTask'  [TaskController.java:34]
⚠️  GET /api/tasks — param 'size' missing @Max(100) constraint  [TaskController.java:34]
```

### pull

```
→  GET /api/tasks — updating signature  [TaskController.java:34]
✔  POST /api/tasks — already matches spec
+  DELETE /api/tasks/{id} — needs stub:
    @DeleteMapping("/api/tasks/{id}")
    public ResponseEntity<Void> deleteApiTasksId(
            @PathVariable Long id
    ) {
        // TODO: implement DELETE /api/tasks/{id}
        throw new UnsupportedOperationException("Not implemented");
    }
```

## Troubleshooting

| Error | Fix |
|---|---|
| `No @RestController files found` | Check `--src-dir` points to the Java sources root |
| `Could not parse spec` | Check `--spec-url` and `GITHUB_TOKEN` if private |
| `Endpoint not found in spec` | Use exact `METHOD:PATH` format, e.g. `GET:/api/tasks` |
| `ModuleNotFoundError` | `pip install requests pyyaml` |
