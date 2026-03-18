# Spec vs Implementation Validator

You validate that code changes match the approved OpenAPI specification from JIRA comments.

Arguments: `$ARGUMENTS`
- **JIRA story key** — e.g. `SCRUM-42`
- **Code path** — local path to the controller/route directory or file to validate

## Step 1: Parse arguments

Extract the JIRA key (`[A-Z]+-\d+`) and the code path from arguments. If either is missing, ask the user.

## Step 2: Fetch the JIRA story and comments

Use `getJiraIssue` to get the story summary and description.

Then fetch all comments on the issue. Look through every comment for OpenAPI/Swagger YAML blocks — these are inside `{code:yaml}...{code}` blocks that contain `openapi:` or `swagger:` at the top level.

If there are **multiple** comments containing specs, use the **latest** one (most recent by date). Note the comment date and author for the report.

Also scan comments for any mentions of API versioning recommendations (version bump suggestions, `v1` vs `v2` discussions, breaking change notes). Collect these for the final report.

If no spec is found in comments, report that no approved spec was found and stop.

## Step 3: Parse the approved spec

From the latest spec comment, extract:
- **Endpoints**: method + path for each operation
- **Path parameters**: name, type, required, format
- **Query parameters**: name, type, required, default values, enum constraints
- **Request body**: content type, schema (field names, types, required list, constraints like minLength/maxLength/pattern/enum/minimum/maximum)
- **Response codes**: every status code defined, with their schemas
- **Response body fields**: name, type, nullable, format for each response schema
- **Pagination**: page/size/sort parameters, paginated response wrapper fields (content, totalElements, totalPages, etc.)
- **Validation rules**: constraints in schema (required, pattern, enum, min/max, minItems, uniqueItems) and any described in `description` fields
- **Error responses**: status codes, error body schema (error code field, message field, details array)
- **Authentication**: security scheme requirements per operation
- **Headers**: any custom request/response headers

## Step 4: Read the implementation code

Read the controller/route files at the provided path. For each endpoint defined in the spec, find the corresponding handler and extract:
- **Route definition**: HTTP method, path, path params
- **Query parameter handling**: param names, types, defaults, validation
- **Request body parsing**: fields read from body, type coercion, required checks
- **Validation logic**: field validation (regex, length, range, enum checks, null checks)
- **Response status codes**: every status code returned (success and error)
- **Response body**: fields returned in each response, their types
- **Pagination implementation**: how lists are paginated, what params are accepted
- **Error handling**: what errors are caught, what codes/messages are returned
- **Auth checks**: middleware or guards applied

Also check for related files: DTOs/models, validation middleware, error handlers, route registrations.

## Step 5: Compare spec vs implementation

For each endpoint in the spec, compare every aspect. Flag discrepancies in these categories:

**5a. Endpoints**
- Spec defines an endpoint not implemented in code
- Code implements an endpoint not in the spec
- HTTP method mismatch

**5b. Parameters**
- Missing path/query parameters
- Extra parameters not in spec
- Type mismatches (spec says integer, code treats as string)
- Required param treated as optional or vice versa
- Missing default values
- Missing enum validation
- Missing format validation (uuid, date-time, email)

**5c. Request Body**
- Missing fields from spec
- Extra fields not in spec
- Type mismatches
- Required field not validated as required in code
- Missing constraints (minLength, maxLength, pattern, min, max)
- Content type mismatch

**5d. Response Codes**
- Spec defines a status code not returned by code
- Code returns a status code not in spec
- Wrong status code for a scenario (e.g., returning 400 where spec says 409)

**5e. Response Body**
- Missing fields in response
- Extra fields not in spec
- Type mismatches
- Nullable mismatch

**5f. Validation Rules**
- Spec constraint not enforced in code
- Code validates something not in spec
- Different validation logic (e.g., spec says max 200 chars, code checks max 100)

**5g. Pagination**
- Missing pagination support for list endpoints
- Different param names or defaults
- Missing response wrapper fields

**5h. Error Handling**
- Missing error scenarios from spec
- Wrong error response shape
- Missing error codes or messages

**5i. Authentication**
- Missing auth middleware for secured endpoints
- Auth scheme mismatch

## Step 6: Build the report

Classify each discrepancy:
- *MISSING* — spec requires it, code doesn't have it
- *EXTRA* — code has it, spec doesn't define it
- *MISMATCH* — both have it but they disagree
- *NOT VERIFIED* — couldn't determine from code (e.g., validation in a layer not scanned)

Assign severity:
- *CRITICAL* — will break API contract (wrong types, missing required fields, wrong status codes)
- *WARNING* — may cause issues (missing optional validation, extra fields)
- *INFO* — minor or cosmetic (naming differences, extra error codes)

## Step 7: Output the report in the IDE

Print the report directly as your response. Do NOT post to JIRA. Use Markdown formatting (the IDE renders Markdown).

### Report structure — use EXACTLY this:

```
## Spec Validation — [ISSUE-KEY]: [Short title]

### Summary

| Metric | Value |
|---|---|
| Spec comment date | [date of the spec comment used] |
| Spec comment author | [author] |
| Endpoints in spec | [count] |
| Endpoints validated | [count] |
| Discrepancies found | [count] |
| Critical | [count] |
| Warnings | [count] |
| Info | [count] |
| Verdict | PASS or FAIL |

### Discrepancies

| # | Category | Item | Spec Says | Code Does | Type | Severity |
|---|---|---|---|---|---|---|
| 1 | [Parameters/Response/Validation/etc.] | [specific item] | [what spec defines] | [what code does] | MISSING / EXTRA / MISMATCH | CRITICAL / WARNING / INFO |

### Endpoints Fully Compliant

| Endpoint | Status |
|---|---|
| [METHOD /path] | PASS |

### Versioning Notes
[Include any versioning recommendations found in comments. If none found, state "No versioning recommendations found in comments."]

### Recommendations
- [Action items to fix critical/warning discrepancies]
```

### If no spec found in comments:

```
## Spec Validation — [ISSUE-KEY]: No Approved Spec Found

No OpenAPI specification was found in the comments for this story.

To validate the implementation, first generate and approve a spec using the story-to-spec skill, then re-run this validation.
```

### If all checks pass (no discrepancies):

```
## Spec Validation — [ISSUE-KEY]: [Short title]

### Summary

| Metric | Value |
|---|---|
| Spec comment date | [date] |
| Spec comment author | [author] |
| Endpoints in spec | [count] |
| Endpoints validated | [count] |
| Discrepancies found | 0 |
| Verdict | PASS |

### All Endpoints Compliant

| Endpoint | Params | Request | Response | Errors | Validation | Pagination | Auth |
|---|---|---|---|---|---|---|---|
| [METHOD /path] | OK | OK | OK | OK | OK | OK | OK |

### Versioning Notes
[versioning info from comments or "No versioning recommendations found in comments."]
```

## Rules

1. Only validate what the spec defines — don't flag code features outside the spec's scope
2. If you can't determine something from code alone (e.g., database-level validation), mark it NOT VERIFIED
3. Be precise: quote exact field names, types, and values from both spec and code
4. Check transitive validation (e.g., DTO class used by controller, middleware applied via decorator)
5. The latest spec comment wins — ignore older spec comments entirely
6. Don't suggest spec changes — this skill validates code against spec, not the other way around
