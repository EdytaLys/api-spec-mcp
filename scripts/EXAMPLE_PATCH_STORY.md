# Example: PATCH Endpoint Story

This is an example of how to use the script to create the PATCH /api/tasks/{id} story from your requirements.

## Running the Script

```bash
export JIRA_EMAIL="your-email@example.com"
export JIRA_API_TOKEN="your-api-token"
python create_api_update_story.py
```

## Interactive Input

```
======================================================================
 JIRA API Story Generator
======================================================================

What type of API story do you want to create?
  1. New API endpoint
  2. Update existing API endpoint

Enter choice (1 or 2): 2

UPDATE EXISTING API
----------------------------------------------------------------------
Endpoint to update (e.g., PUT /api/tasks/{id}): PATCH /api/tasks/{id}

Required changes (enter each change, empty line to finish):
  1. Add PATCH /api/tasks/{id} accepting a partial TaskUpdateRequest
  2. Only fields present in the request body are updated (null means 'no change', not 'clear field')
  3. Keep PUT /api/tasks/{id} for full-replacement semantics (no breaking change)
  4. 

Do you need to specify fields for this update? (y/N): y

API FIELDS
----------------------------------------------------------------------
For each field, provide: name, type, and whether it's required
Example: email, string, required
Example: age, integer, optional
(Enter empty line when done)

  Field 1: title, string, optional
  Field 2: description, string, optional
  Field 3: status, enum (TODO/IN_PROGRESS/DONE), optional
  Field 4: dueDate, date, optional
  Field 5: 

VALIDATION RULES
----------------------------------------------------------------------
Describe business validation rules in plain English
Example: Email must be valid format
Example: Age must be between 18 and 100
Example: Title must be unique within the project
(Enter empty line when done)

  Rule 1: Title must be unique within the project if provided
  Rule 2: Status must be one of: TODO, IN_PROGRESS, DONE
  Rule 3: Due date must be in the future if provided
  Rule 4: 

ERROR SCENARIOS
----------------------------------------------------------------------
Describe expected error cases with HTTP status codes
Example: 400 - Invalid email format
Example: 404 - Task not found
Example: 409 - Title already exists
(Enter empty line when done)

  Error 1: 400 - Invalid status value
  Error 2: 400 - Due date is in the past
  Error 3: 404 - Task not found
  Error 4: 409 - Title already exists in project
  Error 5: 

Acceptance criteria (enter each criterion, empty line to finish):
  1. PATCH /api/tasks/{id} with { "status": "DONE" } updates only status, other fields unchanged
  2. PATCH with empty body {} returns 200 with unchanged task
  3. PATCH with title that already exists returns 409 Conflict
  4. updatedAt is refreshed on every successful PATCH
  5. Auto-generated OpenAPI spec lists PATCH separately from PUT with correct schema
  6. 

======================================================================
Creating story in JIRA project SCRUM...
Summary: Update PATCH /api/tasks/{id}
======================================================================

✓ Created: SCRUM-123
  URL: https://playground-best-team.atlassian.net/browse/SCRUM-123

✓ Story created successfully!
```

## Generated JIRA Story

**Summary**: Update PATCH /api/tasks/{id}

**Story Type**: update_existing_api

**Description**:

As a developer, I want to update PATCH /api/tasks/{id} to improve functionality and meet new requirements.

### Existing endpoint
PATCH /api/tasks/{id}

### Required changes
- Add PATCH /api/tasks/{id} accepting a partial TaskUpdateRequest
- Only fields present in the request body are updated (null means 'no change', not 'clear field')
- Keep PUT /api/tasks/{id} for full-replacement semantics (no breaking change)

### Request fields
- title, string, optional
- description, string, optional
- status, enum (TODO/IN_PROGRESS/DONE), optional
- dueDate, date, optional

### Validation rules
- Title must be unique within the project if provided
- Status must be one of: TODO, IN_PROGRESS, DONE
- Due date must be in the future if provided

### Error scenarios
- 400 - Invalid status value
- 400 - Due date is in the past
- 404 - Task not found
- 409 - Title already exists in project

### Acceptance criteria
- PATCH /api/tasks/{id} with { "status": "DONE" } updates only status, other fields unchanged
- PATCH with empty body {} returns 200 with unchanged task
- PATCH with title that already exists returns 409 Conflict
- updatedAt is refreshed on every successful PATCH
- Auto-generated OpenAPI spec lists PATCH separately from PUT with correct schema

**Labels**: update-existing-api, api-spec

**Story Points**: 3

## Next Steps

Once the story is created:
1. The `api-spec` label triggers the jira-to-openapi skill
2. The skill reads the requirements and acceptance criteria
3. An OpenAPI specification is generated/updated
4. The spec is attached to the JIRA story for review
