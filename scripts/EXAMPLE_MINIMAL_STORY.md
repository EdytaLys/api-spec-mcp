# Example: Minimal Story with Placeholder Guidance

This example shows what happens when a PO creates a story with minimal information. The script automatically includes all sections with helpful examples and guidance.

## Scenario
PO wants to create a new API but doesn't have all the details yet. They provide only the basic information and skip the detailed fields.

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
Endpoint path (e.g., /api/tasks): /api/notifications
HTTP method (GET/POST/PUT/PATCH/DELETE) [POST]: POST
Purpose (what does this API do?): send notifications to users

API FIELDS
----------------------------------------------------------------------
For each field, provide: name, type, and whether it's required
Example: email, string, required
Example: age, integer, optional
(Enter empty line when done)

  Field 1: 

VALIDATION RULES
----------------------------------------------------------------------
Describe business validation rules in plain English
Example: Email must be valid format
Example: Age must be between 18 and 100
Example: Title must be unique within the project
(Enter empty line when done)

  Rule 1: 

ERROR SCENARIOS
----------------------------------------------------------------------
Describe expected error cases with HTTP status codes
Example: 400 - Invalid email format
Example: 404 - Task not found
Example: 409 - Title already exists
(Enter empty line when done)

  Error 1: 

======================================================================
Creating story in JIRA project SCRUM...
Summary: Create /api/notifications endpoint
======================================================================

✓ Created: SCRUM-125
  URL: https://playground-best-team.atlassian.net/browse/SCRUM-125

✓ Story created successfully!
```

## Generated JIRA Story

**Summary**: Create /api/notifications endpoint

**Story Type**: new_api

**Description**:

As a developer, I want /api/notifications so that send notifications to users

### New endpoints to create
- POST /api/notifications

### Request fields
📝 *Please specify request fields in the format: fieldName, type, required/optional*

**Examples:**
- email, string, required
- age, integer, optional
- status, enum (ACTIVE/INACTIVE), required
- price, number, required

### Validation rules
📝 *Please specify business validation rules in plain English*

**Examples:**
- Email must be valid format and unique in the system
- Age must be between 18 and 100
- Title must be unique within the project
- Password must be at least 8 characters with uppercase, lowercase, and number

### Error scenarios
📝 *Please specify expected error cases with HTTP status codes*

**Examples:**
- 400 - Invalid email format
- 404 - Resource not found
- 409 - Email already registered
- 422 - Validation failed

### Acceptance criteria
- Endpoint accepts valid request and returns appropriate response
- All mandatory fields are validated
- All validation rules are enforced with clear error messages
- All error scenarios return appropriate HTTP status codes and messages
- Auto-generated OpenAPI spec documents the endpoint with correct schemas

**Labels**: new-api, api-spec

**Story Points**: 5

## Benefits of This Approach

### 1. Story Can Be Created Immediately
- PO doesn't need to wait until all details are known
- Story can be created during initial planning
- Details can be added later by editing the JIRA story

### 2. Clear Guidance for What's Needed
- Each section shows exactly what format is expected
- Examples demonstrate the level of detail required
- PO knows what information to gather

### 3. Consistent Structure
- All stories have the same sections
- Developers know where to look for information
- Easy to identify incomplete stories

### 4. Facilitates Refinement
- Team can see what's missing during refinement
- Examples help guide the discussion
- Easy to update the story with new information

## When to Use This Approach

### Good Use Cases
✅ Initial story creation during backlog grooming
✅ Placeholder for future work
✅ High-level planning before details are known
✅ Quick capture of an idea

### When to Add Details
⚠️ Before moving to "Ready for Dev"
⚠️ During story refinement sessions
⚠️ Before sprint planning
⚠️ When technical details become available

## How to Complete the Story

### Step 1: Edit the JIRA Story
Open the story in JIRA and click Edit

### Step 2: Replace Placeholder Text
For each section with 📝 guidance:
1. Remove the placeholder text
2. Add actual field specifications
3. Add validation rules
4. Add error scenarios

### Step 3: Example Completion

**Before:**
```
### Request fields
📝 Please specify request fields in the format: fieldName, type, required/optional

Examples:
- email, string, required
- age, integer, optional
```

**After:**
```
### Request fields
- userId, string, required
- message, string, required
- notificationType, enum (EMAIL/SMS/PUSH), required
- priority, enum (LOW/NORMAL/HIGH), optional
- scheduledAt, datetime, optional
```

### Step 4: Trigger Spec Generation
Once all details are added:
1. Ensure the `api-spec` label is present
2. Move to "Ready for Dev" status
3. Automation will trigger OpenAPI spec generation

## Comparison: Minimal vs Complete Story

### Minimal Story (Created Quickly)
```
Time to create: 30 seconds
Information provided: Endpoint, method, purpose
Sections with examples: Fields, Validation, Errors
Ready for development: No
Ready for refinement: Yes
```

### Complete Story (Fully Detailed)
```
Time to create: 3 minutes
Information provided: All details
Sections with examples: None (all filled)
Ready for development: Yes
Ready for refinement: Yes
```

## Best Practice Workflow

```
1. Initial Creation (30 sec)
   ↓
   Create minimal story with basic info
   ↓
2. Backlog Grooming (5 min)
   ↓
   Team discusses and identifies missing details
   ↓
3. Story Refinement (10 min)
   ↓
   PO updates story with complete information
   ↓
4. Ready for Dev
   ↓
   Story has all details, spec auto-generated
   ↓
5. Development
```

## Tips for POs

### Do Create Minimal Stories When:
- You have a high-level idea but not all details
- You want to capture something quickly
- You're doing initial backlog planning
- You need a placeholder for future work

### Do Complete Stories Before:
- Moving to "Ready for Dev"
- Sprint planning
- Assigning to developers
- Expecting spec generation

### Don't:
- Leave stories incomplete indefinitely
- Move incomplete stories to development
- Expect developers to fill in the details
- Skip refinement sessions

## Example Update Flow

### Week 1: Initial Creation
```
Story created with minimal info
Status: Backlog
Has: Endpoint, method, purpose
Missing: Fields, validation, errors
```

### Week 2: Refinement
```
Team discusses requirements
PO gathers information
Status: Still in Backlog
```

### Week 3: Completion
```
PO updates story with all details
Removes placeholder text
Adds actual fields, validation, errors
Status: Ready for Dev
```

### Week 4: Development
```
Automation generates OpenAPI spec
Developer implements based on spec
Status: In Progress
```

## Summary

The script now supports both workflows:
1. **Quick creation** - Minimal info with helpful examples
2. **Complete creation** - All details provided upfront

Both approaches create valid JIRA stories with consistent structure. The choice depends on when information is available and team workflow preferences.
