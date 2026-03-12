# API Story Generation Workflow

## Overview Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     PRODUCT OWNER                                │
│                                                                   │
│  Runs: python create_api_update_story.py                        │
│                                                                   │
│  Provides in Plain English:                                      │
│  • Endpoint path                                                 │
│  • HTTP method                                                   │
│  • Purpose                                                       │
│  • Fields (name, type, required/optional)                       │
│  • Validation rules                                              │
│  • Error scenarios                                               │
│  • Acceptance criteria                                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SCRIPT PROCESSING                             │
│                                                                   │
│  1. Collects all information via interactive prompts            │
│  2. Formats into Atlassian Document Format (ADF)                │
│  3. Adds appropriate labels (new-api or update-existing-api)    │
│  4. Assigns story points (5 for new, 3 for update)              │
│  5. Creates JIRA story via REST API                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      JIRA STORY                                  │
│                                                                   │
│  ✓ Summary: Create /api/users endpoint                          │
│  ✓ Labels: new-api, api-spec                                    │
│  ✓ Story Points: 5                                               │
│  ✓ Description:                                                  │
│    - User story                                                  │
│    - Endpoints to create                                         │
│    - Request fields                                              │
│    - Validation rules                                            │
│    - Error scenarios                                             │
│    - Acceptance criteria                                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              JIRA AUTOMATION (api-spec label)                    │
│                                                                   │
│  Triggers: jira-to-openapi skill                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  OPENAPI SPEC GENERATION                         │
│                                                                   │
│  Skill reads story and generates:                                │
│  • Request schema with all fields                                │
│  • Field types and constraints                                   │
│  • Required vs optional markers                                  │
│  • Validation rules as descriptions                              │
│  • Error response schemas                                        │
│  • HTTP status codes                                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  OPENAPI SPEC ATTACHED                           │
│                                                                   │
│  Spec attached to JIRA story                                     │
│  Ready for:                                                      │
│  • Developer implementation                                      │
│  • QA test case creation                                         │
│  • API documentation                                             │
└─────────────────────────────────────────────────────────────────┘
```

## Detailed Flow: New API Creation

```
START
  │
  ├─► Choose story type: [1] New API
  │
  ├─► Enter endpoint: /api/users
  │
  ├─► Enter HTTP method: POST
  │
  ├─► Enter purpose: register new users in the system
  │
  ├─► Enter fields:
  │   ├─ email, string, required
  │   ├─ username, string, required
  │   ├─ password, string, required
  │   └─ [empty line to finish]
  │
  ├─► Enter validation rules:
  │   ├─ Email must be valid format and unique
  │   ├─ Username must be 3-20 characters
  │   ├─ Password must be at least 8 characters
  │   └─ [empty line to finish]
  │
  ├─► Enter error scenarios:
  │   ├─ 400 - Invalid email format
  │   ├─ 409 - Email already registered
  │   ├─ 409 - Username already taken
  │   └─ [empty line to finish]
  │
  ├─► Generate story structure
  │
  ├─► Create JIRA story via API
  │
  └─► Display success message with story URL
END
```

## Detailed Flow: Update Existing API

```
START
  │
  ├─► Choose story type: [2] Update existing API
  │
  ├─► Enter endpoint: PATCH /api/tasks/{id}
  │
  ├─► Enter required changes:
  │   ├─ Add PATCH endpoint for partial updates
  │   ├─ Only provided fields are updated
  │   ├─ Keep PUT for full replacement
  │   └─ [empty line to finish]
  │
  ├─► Specify fields? [y/N]: y
  │
  ├─► Enter fields:
  │   ├─ title, string, optional
  │   ├─ status, enum (TODO/IN_PROGRESS/DONE), optional
  │   ├─ dueDate, date, optional
  │   └─ [empty line to finish]
  │
  ├─► Enter validation rules:
  │   ├─ Title must be unique if provided
  │   ├─ Status must be valid enum value
  │   ├─ Due date must be in future if provided
  │   └─ [empty line to finish]
  │
  ├─► Enter error scenarios:
  │   ├─ 400 - Invalid status value
  │   ├─ 404 - Task not found
  │   ├─ 409 - Title already exists
  │   └─ [empty line to finish]
  │
  ├─► Enter acceptance criteria:
  │   ├─ PATCH with single field updates only that field
  │   ├─ PATCH with empty body returns 200
  │   ├─ updatedAt is refreshed on success
  │   └─ [empty line to finish]
  │
  ├─► Generate story structure
  │
  ├─► Create JIRA story via API
  │
  └─► Display success message with story URL
END
```

## Data Flow

```
Plain English Input
        │
        ▼
┌───────────────────┐
│  Field Parser     │  → Extracts: name, type, required/optional
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  Rule Parser      │  → Extracts: business validation rules
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  Error Parser     │  → Extracts: HTTP code, error message
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  ADF Generator    │  → Converts to Atlassian Document Format
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  JIRA API Client  │  → Creates story via REST API
└───────────────────┘
        │
        ▼
    JIRA Story
```

## Integration Points

```
┌─────────────────────────────────────────────────────────────────┐
│                        JIRA PROJECT                              │
│                                                                   │
│  Stories with label: api-spec                                    │
│  ├─ new-api (new endpoints)                                      │
│  └─ update-existing-api (modifications)                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AUTOMATION RULES                              │
│                                                                   │
│  Trigger: Label = "api-spec"                                     │
│  Action: Call jira-to-openapi skill                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  JIRA-TO-OPENAPI SKILL                           │
│                                                                   │
│  Reads:                                                          │
│  • Request fields section                                        │
│  • Validation rules section                                      │
│  • Error scenarios section                                       │
│  • Acceptance criteria                                           │
│                                                                   │
│  Generates:                                                      │
│  • OpenAPI 3.0 specification                                     │
│  • Complete schemas                                              │
│  • Validation constraints                                        │
│  • Error responses                                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OPENAPI SPECIFICATION                         │
│                                                                   │
│  Used by:                                                        │
│  • Developers (implementation guide)                             │
│  • QA (test case creation)                                       │
│  • Documentation (API docs)                                      │
│  • Frontend (API client generation)                              │
└─────────────────────────────────────────────────────────────────┘
```

## Time Comparison

### Traditional Approach
```
PO writes requirements (text)         → 10 min
Developer asks clarifications         → 5 min
PO provides more details              → 5 min
Developer creates JIRA story          → 10 min
Developer writes OpenAPI spec         → 30 min
QA reviews and asks questions         → 10 min
                                      ─────────
Total:                                  70 min
```

### With Script Approach
```
PO runs script                        → 3 min
Script creates JIRA story             → instant
Automation generates OpenAPI spec     → instant
Team reviews complete story           → 5 min
                                      ─────────
Total:                                  8 min

Time saved: 62 minutes (89% reduction)
```

## Error Handling Flow

```
Script Start
     │
     ├─► Check credentials
     │   ├─ Missing? → Display error + exit
     │   └─ Valid? → Continue
     │
     ├─► Collect user input
     │   ├─ Invalid choice? → Re-prompt
     │   └─ Valid? → Continue
     │
     ├─► Generate story structure
     │   └─ Always succeeds (internal)
     │
     ├─► Call JIRA API
     │   ├─ HTTP error? → Display error + exit
     │   ├─ Network error? → Display error + exit
     │   └─ Success? → Continue
     │
     └─► Display success message
         └─ Show story URL
```

## Success Indicators

```
✓ Story created in < 3 minutes
✓ All required information captured
✓ Consistent format across all stories
✓ Automatic label assignment
✓ Proper story point allocation
✓ Ready for automation trigger
✓ Complete OpenAPI spec generated
✓ Reduced clarification requests
✓ Faster development cycle
```
