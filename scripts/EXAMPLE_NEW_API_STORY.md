# Example: New API Creation Story

This example shows how to create a complete new API story with all field specifications, validation rules, and error scenarios.

## Scenario
Create a new user registration endpoint with comprehensive validation.

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
  Field 3: password, string, required
  Field 4: displayName, string, required
  Field 5: phoneNumber, string, optional
  Field 6: dateOfBirth, date, optional
  Field 7: 

VALIDATION RULES
----------------------------------------------------------------------
Describe business validation rules in plain English
Example: Email must be valid format
Example: Age must be between 18 and 100
Example: Title must be unique within the project
(Enter empty line when done)

  Rule 1: Email must be valid format and unique in the system
  Rule 2: Username must be 3-20 characters, alphanumeric and underscore only
  Rule 3: Password must be at least 8 characters with uppercase, lowercase, and number
  Rule 4: Display name must not be empty and max 100 characters
  Rule 5: Phone number must be valid international format if provided
  Rule 6: User must be at least 13 years old if date of birth is provided
  Rule 7: 

ERROR SCENARIOS
----------------------------------------------------------------------
Describe expected error cases with HTTP status codes
Example: 400 - Invalid email format
Example: 404 - Task not found
Example: 409 - Title already exists
(Enter empty line when done)

  Error 1: 400 - Invalid email format
  Error 2: 400 - Username contains invalid characters
  Error 3: 400 - Password does not meet complexity requirements
  Error 4: 400 - User must be at least 13 years old
  Error 5: 409 - Email already registered
  Error 6: 409 - Username already taken
  Error 7: 422 - Invalid phone number format
  Error 8: 

======================================================================
Creating story in JIRA project SCRUM...
Summary: Create /api/users endpoint
======================================================================

✓ Created: SCRUM-124
  URL: https://playground-best-team.atlassian.net/browse/SCRUM-124

✓ Story created successfully!
```

## Generated JIRA Story

**Summary**: Create /api/users endpoint

**Story Type**: new_api

**Description**:

As a developer, I want /api/users so that register new users in the system

### New endpoints to create
- POST /api/users

### Request fields
- email, string, required
- username, string, required
- password, string, required
- displayName, string, required
- phoneNumber, string, optional
- dateOfBirth, date, optional

### Validation rules
- Email must be valid format and unique in the system
- Username must be 3-20 characters, alphanumeric and underscore only
- Password must be at least 8 characters with uppercase, lowercase, and number
- Display name must not be empty and max 100 characters
- Phone number must be valid international format if provided
- User must be at least 13 years old if date of birth is provided

### Error scenarios
- 400 - Invalid email format
- 400 - Username contains invalid characters
- 400 - Password does not meet complexity requirements
- 400 - User must be at least 13 years old
- 409 - Email already registered
- 409 - Username already taken
- 422 - Invalid phone number format

### Acceptance criteria
- Endpoint accepts valid request and returns appropriate response
- All mandatory fields are validated
- All validation rules are enforced with clear error messages
- All error scenarios return appropriate HTTP status codes and messages
- Auto-generated OpenAPI spec documents the endpoint with correct schemas

**Labels**: new-api, api-spec

**Story Points**: 5

## What Happens Next

1. The `api-spec` label triggers the jira-to-openapi skill
2. The skill reads all the field specifications, validation rules, and error scenarios
3. An OpenAPI specification is generated with:
   - Request schema with all fields and their types
   - Required vs optional field markers
   - Validation constraints (min/max length, patterns, etc.)
   - Error response schemas for each HTTP status code
   - Clear descriptions based on the validation rules
4. The generated spec is attached to the JIRA story
5. Developers can review and implement based on the spec

## Benefits of This Approach

### For Product Owners
- No technical knowledge required
- Plain English descriptions
- Focus on business rules, not implementation
- Quick story creation (2-3 minutes)

### For Developers
- Complete requirements in one place
- Clear field specifications
- Explicit validation rules
- Expected error scenarios documented
- Auto-generated OpenAPI spec as implementation guide

### For QA
- Clear acceptance criteria
- All error scenarios documented
- Easy to create test cases
- Validation rules are explicit
