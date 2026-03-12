# API Story Generation Scripts

This directory contains scripts for creating JIRA user stories for API development with minimal Product Owner input.

## Quick Start

1. **Set up credentials** (one-time):
   ```bash
   export JIRA_EMAIL="your-email@example.com"
   export JIRA_API_TOKEN="your-api-token"
   ```

2. **Run the script**:
   ```bash
   python create_api_update_story.py
   ```

3. **Follow the prompts** to create your story

## Files

### Main Script
- **`create_api_update_story.py`** - Interactive script for creating API stories

### Documentation
- **`QUICK_START.md`** - Fastest way to get started
- **`PO_QUICK_REFERENCE.md`** - Quick reference guide for Product Owners (START HERE!)
- **`README.md`** - Overview and setup (this file)
- **`API_UPDATE_STORY_GUIDE.md`** - Comprehensive guide with examples
- **`EXAMPLE_NEW_API_STORY.md`** - Complete example of creating a new API
- **`EXAMPLE_PATCH_STORY.md`** - Complete example of updating an existing API
- **`EXAMPLE_MINIMAL_STORY.md`** - Example of creating a minimal story with placeholders
- **`WORKFLOW_DIAGRAM.md`** - Visual workflow diagrams
- **`IMPLEMENTATION_SUMMARY.md`** - Technical details

## Features

### For Product Owners
- ✅ No technical knowledge required
- ✅ Plain English input
- ✅ Interactive prompts guide you through
- ✅ Takes 2-3 minutes per story
- ✅ Can create minimal stories with examples for later completion
- ✅ All sections always included with helpful guidance

### Story Types Supported
1. **New API Creation** - Create brand new endpoints
2. **Existing API Updates** - Modify existing endpoints

### Flexibility
- **Complete stories** - Provide all details upfront (2-3 minutes)
- **Minimal stories** - Provide basic info, get examples for later (30 seconds)
- **All sections included** - Even empty sections show helpful examples

### What You Can Specify
- **Fields**: name, type, required/optional
- **Validation Rules**: business rules in plain English
- **Error Scenarios**: HTTP codes and error messages
- **Acceptance Criteria**: specific requirements

## Example Usage

### New API
```bash
$ python create_api_update_story.py

What type of API story do you want to create?
  1. New API endpoint
  2. Update existing API endpoint

Enter choice (1 or 2): 1

Endpoint path: /api/users
HTTP method [POST]: POST
Purpose: register new users in the system

# Then specify fields, validation rules, and error scenarios
```

### Update API
```bash
$ python create_api_update_story.py

What type of API story do you want to create?
  1. New API endpoint
  2. Update existing API endpoint

Enter choice (1 or 2): 2

Endpoint to update: PATCH /api/tasks/{id}

# Then specify changes, fields, validation rules, and acceptance criteria
```

## Integration

Stories created by this script:
1. Are automatically labeled with `api-spec`
2. Trigger the `jira-to-openapi` skill
3. Generate OpenAPI specifications automatically
4. Maintain traceability from requirement to spec

## Getting Help

- **First time?** Read `PO_QUICK_REFERENCE.md`
- **Need examples?** See `EXAMPLE_NEW_API_STORY.md` or `EXAMPLE_PATCH_STORY.md`
- **Detailed guide?** Read `API_UPDATE_STORY_GUIDE.md`

## Configuration

Edit these constants in `create_api_update_story.py`:
```python
JIRA_BASE_URL = "https://your-domain.atlassian.net"
PROJECT_KEY = "YOUR_PROJECT"
```

## Requirements

- Python 3.6+
- JIRA Cloud account with API access
- Valid JIRA API token
