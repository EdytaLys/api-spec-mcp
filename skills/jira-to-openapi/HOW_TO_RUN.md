# How to Run: JIRA to OpenAPI Spec Generator

## Quick Start

### 1. Install Dependencies

```bash
pip install requests pyyaml reportlab
```

### 2. Set Environment Variables

```bash
export JIRA_BASE_URL="https://playground-best-team.atlassian.net"
export JIRA_EMAIL="your-email@example.com"
export JIRA_API_TOKEN="your-api-token"
```

Get your API token at: https://id.atlassian.com/manage-profile/security/api-tokens

### 3. Run the Script

```bash
# Basic usage - generates YAML and PDF
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-10

# Specify output file
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-10 --output my-api.yaml

# Check for existing spec in GitHub repo
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-10 \
  --repo-url https://github.com/EdytaLys/api-spec-task-manager

# Use local existing spec
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-10 \
  --existing-spec specs/task-manager-openapi.yaml
```

## What the Script Does

1. **Fetches JIRA Story** - Reads the story content including:
   - Request fields (both formats: comma-separated and pipe-separated)
   - Validation rules (plain English)
   - Error scenarios (HTTP codes and messages)
   - Acceptance criteria

2. **Checks for Existing API** - Optionally fetches existing OpenAPI spec from:
   - GitHub repository (via --repo-url)
   - Local file (via --existing-spec)

3. **Generates OpenAPI Spec** - Creates or updates:
   - YAML format (always)
   - JSON format (with --format json)
   - Merges with existing spec if found

4. **Detects Changes** - If existing spec found:
   - Breaking changes (removed endpoints, new required fields)
   - Additive changes (new endpoints, optional fields)
   - Modified endpoints

5. **Generates PDF** - Creates Swagger-style documentation:
   - Highlights breaking changes in red
   - Highlights additive changes in green
   - Shows all endpoints and schemas
   - Includes change summary

## Output Files

For issue `SCRUM-10`, the script generates:
- `SCRUM-10-openapi.yaml` - OpenAPI specification
- `SCRUM-10-api-documentation.pdf` - PDF documentation

## Command Line Options

```
python generate_spec.py <ISSUE_KEY> [OPTIONS]

Required:
  ISSUE_KEY              JIRA issue key (e.g., SCRUM-10)

Optional:
  --output PATH          Output file path (default: <KEY>-openapi.yaml)
  --format FORMAT        Output format: yaml or json (default: yaml)
  --path PATH            Override endpoint path (e.g., /api/tasks)
  --repo-url URL         GitHub repo URL to fetch existing spec
  --existing-spec PATH   Local path to existing spec
  --no-pdf               Skip PDF generation
```

## Examples

### Example 1: New API (No Existing Spec)

```bash
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-15
```

**Output:**
- `SCRUM-15-openapi.yaml` - New OpenAPI spec
- `SCRUM-15-api-documentation.pdf` - PDF documentation

### Example 2: Update Existing API from GitHub

```bash
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-16 \
  --repo-url https://github.com/EdytaLys/api-spec-task-manager
```

**What happens:**
1. Fetches existing spec from GitHub repo
2. Generates new spec based on JIRA story
3. Detects changes (breaking/additive)
4. Merges new endpoint into existing spec
5. Increments version number
6. Generates PDF with change highlights

### Example 3: Update Existing API from Local File

```bash
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-17 \
  --existing-spec ./specs/task-manager-openapi.yaml
```

### Example 4: JSON Output

```bash
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-18 \
  --format json \
  --output api-spec.json
```

## JIRA Story Format

The script supports both old and new story formats:

### New Format (Recommended)

```
### Request fields
- email, string, required
- username, string, required
- age, integer, optional
- status, enum (ACTIVE/INACTIVE), required

### Validation rules
- Email must be valid format and unique
- Username must be 3-20 characters
- Age must be between 18 and 100

### Error scenarios
- 400 - Invalid email format
- 409 - Email already registered
- 404 - User not found
```

### Old Format (Still Supported)

```
### API Request Fields
name | type | required/optional | validation note
email | string | required | must be unique
age | integer | optional | 18-100

### API Validation Rules
Email must be valid format
Age must be between 18 and 100

### API Error Scenarios
400 — invalid input
409 — duplicate email
```

## Troubleshooting

### Error: 401 Unauthorized
```
⛔  401 Unauthorized — check JIRA_EMAIL and JIRA_API_TOKEN
```
**Fix:** Verify your credentials are correct

### Error: 404 Not Found
```
⛔  404 Not Found — issue SCRUM-XX does not exist
```
**Fix:** Check the issue key exists in your JIRA project

### Error: Missing dependency
```
Missing dependency: pip install requests
```
**Fix:** Install required packages:
```bash
pip install requests pyyaml reportlab
```

### Warning: reportlab not available
```
⚠️  reportlab not available. PDF generation disabled.
```
**Fix:** Install reportlab:
```bash
pip install reportlab
```
PDF generation will be skipped, but YAML will still be generated.

### Error: No custom field IDs found
```
⛔  No custom field IDs found. Run scripts/jira_form_setup.py first
```
**Fix:** The script will try to fetch field IDs from JIRA API automatically. If this fails, run the setup script first.

## Integration with Workflow

### Step 1: PO Creates Story
```bash
python git/api-spec-mcp/scripts/create_api_update_story.py
```

### Step 2: Generate Spec from Story
```bash
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-XX \
  --repo-url https://github.com/your-org/your-repo
```

### Step 3: Review Generated Files
- Open `SCRUM-XX-openapi.yaml` in [Swagger Editor](https://editor.swagger.io/)
- Review `SCRUM-XX-api-documentation.pdf` for documentation
- Check change summary for breaking changes

### Step 4: Commit to Repository
```bash
git add SCRUM-XX-openapi.yaml SCRUM-XX-api-documentation.pdf
git commit -m "Add API spec for SCRUM-XX"
git push
```

## Advanced Usage

### Custom Endpoint Path
If the script can't detect the endpoint path from the summary:
```bash
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-19 \
  --path /api/v2/users/{id}/notifications
```

### Skip PDF Generation
If you only need the YAML:
```bash
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-20 --no-pdf
```

### Validate Generated Spec
```bash
# Using Swagger CLI
swagger-cli validate SCRUM-XX-openapi.yaml

# Using online validator
open https://editor.swagger.io/
# Then paste the YAML content
```

## Output Structure

### YAML File Structure
```yaml
openapi: 3.0.3
info:
  title: Create /api/users endpoint
  description: Register new users in the system
  version: 1.0.0
  x-jira-issue: SCRUM-XX
  x-generated-at: 2026-03-12T14:30:00Z
  x-change-type: Additive
servers:
  - url: https://api.example.com/v1
paths:
  /api/users:
    post:
      summary: Create /api/users endpoint
      description: |
        Register new users in the system
        
        **Validation rules:**
        - Email must be valid format and unique
        - Username must be 3-20 characters
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UserRequest'
      responses:
        '200':
          description: Successful response
        '400':
          description: Invalid email format
        '409':
          description: Email already registered
components:
  schemas:
    UserRequest:
      type: object
      required:
        - email
        - username
      properties:
        email:
          type: string
        username:
          type: string
        age:
          type: integer
```

### PDF Structure
1. **Title Page** - API name, version, JIRA issue
2. **Change Summary** (if updating) - Breaking/additive changes
3. **Servers** - Production and staging URLs
4. **Endpoints** - All API endpoints with:
   - HTTP method (color-coded)
   - Path
   - Description
   - Request body
   - Responses
5. **Data Models** - All schemas with properties

## Tips

1. **Always check for existing specs** when updating APIs
2. **Review breaking changes** carefully before deploying
3. **Validate the generated spec** in Swagger Editor
4. **Commit both YAML and PDF** to your repository
5. **Link the JIRA issue** to the generated spec files

## Next Steps

After generating the spec:
1. Review in Swagger Editor
2. Share PDF with stakeholders
3. Implement the API based on the spec
4. Update tests to match the spec
5. Deploy and update documentation
