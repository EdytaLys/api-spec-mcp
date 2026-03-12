# Complete API-First Workflow

## Overview

This document describes the complete end-to-end workflow for API development using the JIRA story generator and OpenAPI spec generator.

## Workflow Steps

```
1. PO Creates Story (30 sec - 3 min)
   ↓
2. Generate OpenAPI Spec (instant)
   ↓
3. Review & Validate (5 min)
   ↓
4. Implement API (development)
   ↓
5. Deploy & Document (deployment)
```

## Step 1: Create JIRA Story

### Quick Start
```bash
cd git/api-spec-mcp/scripts
python create_api_update_story.py
```

### What You Provide
- Endpoint path (e.g., `/api/users`)
- HTTP method (POST, GET, PUT, PATCH, DELETE)
- Purpose (what the API does)
- Fields (name, type, required/optional)
- Validation rules (plain English)
- Error scenarios (HTTP codes + messages)

### Output
- JIRA story with consistent format
- All sections included (even if empty with examples)
- Labels: `new-api` or `update-existing-api`, `api-spec`

### Time
- Complete story: 2-3 minutes
- Minimal story: 30 seconds (complete later)

## Step 2: Generate OpenAPI Specification

### Quick Start
```bash
cd git/api-spec-mcp/skills/jira-to-openapi
./run.sh SCRUM-XX
```

### With Existing API
```bash
./run.sh SCRUM-XX --repo-url https://github.com/your-org/your-repo
```

### What It Does
1. Fetches JIRA story content
2. Parses fields, validation rules, error scenarios
3. Checks for existing API spec (if --repo-url provided)
4. Detects changes (breaking/additive)
5. Generates OpenAPI 3.0 YAML
6. Creates PDF documentation with change highlights

### Output
- `SCRUM-XX-openapi.yaml` - OpenAPI specification
- `SCRUM-XX-api-documentation.pdf` - PDF documentation

### Time
- Instant (< 5 seconds)

## Step 3: Review & Validate

### Validate YAML
```bash
# Open in Swagger Editor
open https://editor.swagger.io/
# Paste the YAML content
```

### Review PDF
- Check endpoints are correct
- Verify request/response schemas
- Review validation rules
- Check error scenarios
- If updating: Review change summary

### Review Changes (if updating)
- **Breaking changes** (red in PDF):
  - Removed endpoints
  - New required fields
  - Removed responses
- **Additive changes** (green in PDF):
  - New endpoints
  - New optional fields
  - New responses

### Time
- 5-10 minutes

## Step 4: Implement API

### Use Generated Spec
- Implement endpoints as specified
- Follow request/response schemas
- Implement validation rules
- Return correct error codes

### Test Against Spec
```bash
# Use tools like Dredd or Postman
dredd SCRUM-XX-openapi.yaml http://localhost:8080
```

### Time
- Varies by complexity

## Step 5: Deploy & Document

### Commit Spec Files
```bash
git add SCRUM-XX-openapi.yaml SCRUM-XX-api-documentation.pdf
git commit -m "Add API spec for SCRUM-XX"
git push
```

### Update Documentation
- Link JIRA story to spec files
- Share PDF with stakeholders
- Update API documentation site

### Deploy
- Deploy API implementation
- Update version number
- Notify consumers of changes

## Complete Example

### Scenario: Add PATCH Endpoint for Partial Updates

#### Step 1: Create Story (2 minutes)
```bash
python create_api_update_story.py

# Input:
Story type: 2 (Update existing API)
Endpoint: PATCH /api/tasks/{id}

Changes:
1. Add PATCH endpoint for partial updates
2. Only provided fields are updated
3. Keep PUT for full replacement

Fields:
1. title, string, optional
2. status, enum (TODO/IN_PROGRESS/DONE), optional
3. dueDate, date, optional

Validation Rules:
1. Title must be unique if provided
2. Status must be valid enum value
3. Due date must be in future if provided

Error Scenarios:
1. 400 - Invalid status value
2. 404 - Task not found
3. 409 - Title already exists

Acceptance Criteria:
1. PATCH with single field updates only that field
2. PATCH with empty body returns 200
3. updatedAt is refreshed on success
```

**Output:** SCRUM-20 created in JIRA

#### Step 2: Generate Spec (5 seconds)
```bash
./run.sh SCRUM-20 \
  --repo-url https://github.com/EdytaLys/api-spec-task-manager
```

**Output:**
- `SCRUM-20-openapi.yaml` - Updated spec with PATCH endpoint
- `SCRUM-20-api-documentation.pdf` - PDF with changes highlighted

#### Step 3: Review (5 minutes)
- Open YAML in Swagger Editor
- Verify PATCH endpoint is correct
- Check PDF shows additive change (green)
- Confirm no breaking changes

#### Step 4: Implement (2 hours)
```java
@PatchMapping("/{id}")
public ResponseEntity<Task> partialUpdate(
    @PathVariable Long id,
    @RequestBody TaskUpdateDTO updates
) {
    // Implementation based on spec
}
```

#### Step 5: Deploy (30 minutes)
```bash
git add SCRUM-20-openapi.yaml SCRUM-20-api-documentation.pdf
git commit -m "Add PATCH endpoint for partial task updates (SCRUM-20)"
git push
# Deploy to production
```

## Time Savings

### Traditional Approach
| Task | Time |
|------|------|
| Write requirements | 15-20 min |
| Clarifications | 10-15 min |
| Write spec manually | 30-45 min |
| Create documentation | 20-30 min |
| **Total** | **75-110 min** |

### With This Workflow
| Task | Time |
|------|------|
| Create JIRA story | 2-3 min |
| Generate spec | 5 sec |
| Review | 5-10 min |
| **Total** | **7-13 min** |

### Savings
**85-90% time reduction** on specification and documentation

## Best Practices

### For Product Owners
1. Provide complete information in JIRA stories
2. Use plain English for validation rules
3. Think through all error scenarios
4. Review generated spec before development starts

### For Developers
1. Always validate generated spec in Swagger Editor
2. Implement exactly as specified
3. Test against the spec
4. Update spec if requirements change

### For Teams
1. Use consistent story format
2. Review specs during refinement
3. Keep specs in version control
4. Link JIRA stories to spec files

## Troubleshooting

### Story Creation Issues
- See `git/api-spec-mcp/scripts/PO_QUICK_REFERENCE.md`
- Check examples in `EXAMPLE_NEW_API_STORY.md`

### Spec Generation Issues
- See `skills/jira-to-openapi/HOW_TO_RUN.md`
- Verify JIRA credentials
- Check story has required sections

### Integration Issues
- Ensure labels are correct (`api-spec`)
- Verify field format matches examples
- Check JIRA story is accessible

## Tools & Resources

### Required Tools
- Python 3.7+
- pip packages: requests, pyyaml, reportlab
- JIRA Cloud account with API access

### Helpful Tools
- [Swagger Editor](https://editor.swagger.io/) - Validate specs
- [Postman](https://www.postman.com/) - Test APIs
- [Dredd](https://dredd.org/) - API testing against specs

### Documentation
- [OpenAPI Specification](https://swagger.io/specification/)
- [JIRA REST API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)
- [ReportLab](https://www.reportlab.com/docs/reportlab-userguide.pdf)

## Support

### Getting Help
1. Check documentation in respective folders
2. Review examples
3. Verify credentials and permissions
4. Test with simple stories first

### Common Issues
- **401 Unauthorized**: Check JIRA credentials
- **404 Not Found**: Verify issue key exists
- **Missing fields**: Ensure story has required sections
- **PDF not generated**: Install reportlab

## Next Steps

1. **Set up credentials** - Configure JIRA access
2. **Create test story** - Try with a simple API
3. **Generate spec** - Run the generator
4. **Review output** - Validate in Swagger Editor
5. **Implement** - Build the API
6. **Deploy** - Ship to production

## Summary

This workflow provides:
- ✅ 85-90% time savings on specs and docs
- ✅ Consistent format across all APIs
- ✅ Automatic change detection
- ✅ Clear documentation for stakeholders
- ✅ Reduced clarification requests
- ✅ Better traceability from requirement to implementation

Start with a simple API and expand from there!
