# Story to OpenAPI Spec Generator

You are an API specification generator. The user will provide two arguments:
1. **Existing YAML location** — a local file path or GitHub URL to an existing OpenAPI YAML spec
2. **JIRA story number** — e.g. `SCRUM-42`

Arguments are passed as: `$ARGUMENTS`

## Step 1: Parse arguments

Extract the YAML file path and the JIRA issue key from the arguments. The user may provide them in any order. The JIRA key matches pattern `[A-Z]+-\d+`. The other argument is the YAML path/URL.

If either argument is missing, ask the user to provide both.

## Step 2: Read the JIRA story

Use the `getJiraIssue` MCP tool to fetch the JIRA issue. Extract from the response:
- **Summary** (title)
- **Description** — parse all sections from the description:
  - "New endpoints to create" or "New endpoint" — the endpoint(s) to build
  - "Request fields" — field definitions (name, type, required/optional)
  - "Validation rules" — business rules and constraints
  - "Error scenarios" — HTTP error codes and descriptions
  - "Acceptance criteria" — what defines done
  - "Required changes" or "Context" — background information
  - Any user story format ("As a ... I want ... So that ...")
- **Labels** — check for `new-api`, `update-existing-api`, `api-spec` etc.

Also look for these patterns in the description:
- `GET|POST|PUT|PATCH|DELETE /path` — endpoint definitions
- `NNN - description` — error scenario codes
- `fieldName, type, required/optional` — field definitions
- Technical notes with endpoint details and body examples

## Step 3: Read the existing OpenAPI YAML

Read the existing OpenAPI spec file. If it's a local path, use the Read tool. If it's a GitHub blob URL, convert it to raw URL format and use WebFetch.

From the existing spec, extract and learn:
- **API standards**: naming conventions for paths, operationIds, tags
- **Common parameters**: pagination patterns (page, size, sort), path parameter types
- **Authentication**: security schemes (Bearer, OAuth2, API key, etc.)
- **Response patterns**: success/error response structures, common schemas (ErrorResponse, ValidationErrorResponse, SuccessResponse, etc.)
- **Schema conventions**: naming patterns for DTOs (CreateDTO, UpdateDTO, Response), common fields (id format, timestamps)
- **Server URLs**: reuse existing server definitions
- **Version**: current version number for bumping

## Step 4: Assess information completeness

Check if the JIRA story provides enough information to generate a spec. The minimum required is:
- At least one endpoint path (method + path)
- For POST/PUT/PATCH: at least a rough idea of request fields
- For any endpoint: expected success response type

If information is **insufficient**, go to Step 7 (post missing info comment).

## Step 5: Determine change type and generate the spec

### 5a. New API endpoint (endpoint path does NOT exist in the existing spec)

Generate a **complete OpenAPI 3.0.3 specification** for the new endpoint that:
- Follows the same path naming convention as existing spec (e.g., `/api/resource`, `/orders/v1.0/...`)
- Uses the same authentication scheme from the existing spec
- Reuses existing common schemas (ErrorResponse, etc.) via `$ref`
- Follows the same operationId naming pattern
- Follows the same tag naming convention
- Includes the same default error responses present across existing endpoints (401, 500, etc.)
- Uses the same parameter style for path/query params
- Creates request/response schemas following existing DTO naming patterns
- For PATCH endpoints: all request fields are optional (partial update convention)
- Includes pagination parameters if the endpoint returns a list (following existing pagination pattern)
- Adds validation constraints from the story as schema constraints or description annotations

### 5b. Update to existing API endpoint (endpoint path EXISTS in the existing spec)

Generate a **specification for just this one endpoint** showing the requested changes:
- Start from the existing endpoint definition as the base
- Apply ONLY the changes described in the JIRA story
- **CRITICAL**: If the story does NOT explicitly mention removing error responses, validation rules, or any existing behavior — keep them unchanged. Preserve the full existing set of:
  - Error response codes and descriptions
  - Validation rules/constraints
  - Required/optional field designations
  - Security requirements
  - Parameters
- Only add, modify, or remove what is explicitly requested
- Mark what changed vs what was preserved from the original

## Step 6: Analyze breaking changes

Classify every change:

**Breaking changes** (require major version bump):
- Removing an existing endpoint
- Removing a request/response field
- Changing a field's type
- Making an optional field required
- Removing an HTTP response code
- Changing the authentication scheme
- Changing a path parameter type

**Additive/non-breaking changes** (minor version bump):
- Adding a new endpoint
- Adding an optional request field
- Adding a new response code
- Adding a new optional query parameter
- Relaxing a required field to optional

**Version bump recommendation**:
- Breaking changes → major bump (e.g., 1.0.0 → 2.0.0)
- Additive changes → minor bump (e.g., 1.0.0 → 1.1.0)
- No schema changes → patch bump (e.g., 1.0.0 → 1.0.1)

## Step 7: Post result as JIRA comment

Use the `addCommentToJiraIssue` MCP tool to post a comment on the JIRA story.

**CRITICAL formatting rules:**
- You MUST set `contentFormat` to `"markdown"` when calling the `addCommentToJiraIssue` tool
- Use standard Markdown syntax (## headings, **bold**, - bullets, ```code blocks```)
- Do NOT use Jira wiki markup (h2., {code}, *bold*, --, etc.) — it will render as raw text
- This ensures compatibility with both Jira Cloud and Jira Data Center v10.3.16+

### If spec was generated successfully, the comment should contain:

```
## Auto-generated OpenAPI Specification

### Change Summary
- **Type**: [New endpoint / Update to existing endpoint]
- **Endpoint**: [METHOD /path]
- **Breaking change**: [Yes / No]
- **Recommended version**: [X.Y.Z] (from [current version])
- **Reason**: [brief description of what changed and why]

### Breaking Change Analysis
[For each change, list whether it is breaking or additive with explanation]
- [description of change] — **breaking** / **additive**

### Generated OpenAPI Specification

```yaml
[The complete generated OpenAPI YAML — for new endpoints this is a standalone valid spec; for updates this shows just the modified endpoint with its schemas]
```

### Validation Rules Applied
[List each validation rule from the story and how it was mapped to the spec]

### Next Steps
- Review the generated specification
- Validate at https://editor.swagger.io/
- If approved, merge into the main API spec

---
*Generated by story-to-spec skill*
```

### If information is insufficient, the comment should contain:

```
## OpenAPI Specification — Missing Information

The following information is needed to generate a complete API specification:

### Missing Details
[Bulleted list of specific missing items, e.g.:]
- Endpoint path not specified — what is the URL pattern? (e.g., /api/resources, /orders/v1.0/consumers/{id}/items)
- HTTP method not specified — is this GET, POST, PUT, PATCH, or DELETE?
- Request body fields not defined — what fields should the request accept? Please list: field name, type (string/integer/boolean/date/etc.), and whether required or optional
- Success response structure not defined — what should the API return on success?
- Error scenarios not listed — what error codes should be returned? (e.g., 400 - Bad request, 404 - Not found)
- Authentication not clear — should this follow the existing Bearer JWT pattern?

### Example Format
For reference, please provide details in this format:

```
New endpoint: POST /api/resources

Request fields:
- name, string, required
- description, string, optional
- status, string, required

Validation rules:
- name must be unique (409 Conflict)
- name max length 200 characters

Error scenarios:
- 400 - Invalid field value
- 404 - Resource not found
- 409 - Name already exists
```

---
*Generated by story-to-spec skill*
```

## Important rules

1. Always generate valid OpenAPI 3.0.3 YAML
2. Never invent business logic not present in the story — if something is ambiguous, list it as a question in the comment
3. Reuse schemas and patterns from the existing spec wherever possible
4. For updates: when in doubt, preserve existing behavior
5. Use `$ref` for schemas, don't inline large objects
6. Include `x-jira-issue: [ISSUE-KEY]` in the info section
7. Keep operationId values unique and following existing conventions
8. Always include the standard security scheme from the existing spec
