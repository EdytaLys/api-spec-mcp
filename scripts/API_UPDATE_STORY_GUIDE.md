# API Story Generation Guide

## Overview
This script creates JIRA user stories for API requests with minimal Product Owner input. It supports both:
- **New API endpoint creation**
- **Existing API endpoint updates**

The script uses an interactive prompt to gather requirements and automatically generates properly formatted JIRA stories.

## Quick Start

### 1. Set up credentials
```bash
export JIRA_EMAIL="your-email@example.com"
export JIRA_API_TOKEN="your-api-token"
```

Get your API token at: https://id.atlassian.com/manage-profile/security/api-tokens

### 2. Run the script
```bash
python create_api_update_story.py
```

### 3. Follow the prompts
The script will ask you:
1. Story type (new API or update existing)
2. Endpoint details
3. Required changes (for updates)
4. Acceptance criteria (for updates)

## Example Usage

### Creating a New API Story
```
What type of API story do you want to create?
  1. New API endpoint
  2. Update existing API endpoint

Enter choice (1 or 2): 1

NEW API ENDPOINT
----------------------------------------------------------------------
Endpoint path (e.g., /api/tasks): /api/users
HTTP method (GET/POST/PUT/PATCH/DELETE) [POST]: POST
Purpose (what does this API do?): register new users in the system

API FIELDS
----------------------------------------------------------------------
For each field, provide: name, type, and whether it's required
Example: email, string, required
Example: age, integer, optional
(Enter empty line when done)

  Field 1: email, string, required
  Field 2: username, string, required
  Field 3: displayName, string, required
  Field 4: phoneNumber, string, optional
  Field 5: 

VALIDATION RULES
----------------------------------------------------------------------
Describe business validation rules in plain English
Example: Email must be valid format
Example: Age must be between 18 and 100
Example: Title must be unique within the project
(Enter empty line when done)

  Rule 1: Email must be valid format and unique in the system
  Rule 2: Username must be 3-20 characters, alphanumeric only
  Rule 3: Display name must not be empty
  Rule 4: Phone number must be valid international format if provided
  Rule 5: 

ERROR SCENARIOS
----------------------------------------------------------------------
Describe expected error cases with HTTP status codes
Example: 400 - Invalid email format
Example: 404 - Task not found
Example: 409 - Title already exists
(Enter empty line when done)

  Error 1: 400 - Invalid email format
  Error 2: 400 - Username contains invalid characters
  Error 3: 409 - Email already registered
  Error 4: 409 - Username already taken
  Error 5: 
```

### Creating an Update Story
```
What type of API story do you want to create?
  1. New API endpoint
  2. Update existing API endpoint

Enter choice (1 or 2): 2

UPDATE EXISTING API
----------------------------------------------------------------------
Endpoint to update (e.g., PUT /api/tasks/{id}): PATCH /api/tasks/{id}

Required changes (enter each change, empty line to finish):
  1. Add PATCH /api/tasks/{id} accepting a partial TaskUpdateRequest
  2. Only fields present in the request body are updated
  3. Keep PUT /api/tasks/{id} for full-replacement semantics
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
  Rule 4: At least one field must be present in the request
  Rule 5: 

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
  1. PATCH /api/tasks/{id} with { "status": "DONE" } updates only status
  2. PATCH with empty body {} returns 200 with unchanged task
  3. PATCH with duplicate title returns 409 Conflict
  4. updatedAt is refreshed on every successful PATCH
  5. Auto-generated OpenAPI spec lists PATCH separately from PUT
  6. 
```

## Generated Story Structure

### For New APIs
- **User Story**: "As a developer, I want [endpoint] so that [purpose]"
- **New endpoints to create**: List of endpoints with HTTP methods
- **Request fields**: Field name, type, and whether required/optional
- **Validation rules**: Business validation rules in plain English
- **Error scenarios**: Expected error cases with HTTP status codes and messages
- **Acceptance criteria**: Auto-generated based on provided information

### For Existing API Updates
- **User Story**: "As a developer, I want to update [endpoint] to improve functionality"
- **Existing endpoint**: Current endpoint being modified
- **Required changes**: List of changes provided by PO
- **Request fields** (optional): Updated or new fields
- **Validation rules**: Business validation rules in plain English
- **Error scenarios**: Expected error cases with HTTP status codes and messages
- **Acceptance criteria**: Specific criteria provided by PO

## What the PO Needs to Provide

### Required Information
1. **Endpoint path** - e.g., /api/users, /api/tasks/{id}
2. **HTTP method** - GET, POST, PUT, PATCH, DELETE
3. **Purpose** - What the API does in plain English

### Field Specification (Plain English)
For each field, provide:
- **Field name** - e.g., email, username, age
- **Field type** - e.g., string, integer, boolean, date, enum
- **Required or optional** - Is this field mandatory?

Example format:
```
email, string, required
age, integer, optional
status, enum (ACTIVE/INACTIVE), required
```

### Validation Rules (Plain English)
Describe business rules without technical jargon:
- "Email must be valid format and unique"
- "Age must be between 18 and 100"
- "Title must be unique within the project"
- "Password must be at least 8 characters"
- "Due date must be in the future"

### Error Scenarios (Plain English)
Specify HTTP status code and error message:
- "400 - Invalid email format"
- "404 - User not found"
- "409 - Email already registered"
- "422 - Age is below minimum requirement"

## Integration with Skills

This template is designed to work with the `jira-to-openapi` skill, which:
1. Reads the story from JIRA
2. Extracts the requirements and acceptance criteria
3. Generates/updates the OpenAPI specification
4. Attaches the spec to the JIRA story

## Labels

The script automatically adds these labels:
- **New API**: `new-api`, `api-spec`
- **Update API**: `update-existing-api`, `api-spec`

The `api-spec` label triggers automation for OpenAPI spec generation.

## Story Points

Default story points:
- **New API**: 5 points
- **Update API**: 3 points

## Configuration

Edit these constants in the script to match your JIRA setup:
- `JIRA_BASE_URL` - Your Atlassian domain
- `PROJECT_KEY` - Your JIRA project key (e.g., "SCRUM")

## Benefits

### Minimal PO Input
- Simple interactive prompts
- No need to understand JIRA API or ADF format
- Focus on requirements, not formatting

### Consistent Structure
- All stories follow the same template
- Easy for developers to understand
- Compatible with automation workflows

### Integration Ready
- Works with `jira-to-openapi` skill
- Triggers automatic spec generation
- Maintains traceability from requirement to spec
