# Quick Start Guide

## 3-Step Setup

### Step 1: Install Dependencies
```bash
pip install requests pyyaml reportlab
```

### Step 2: Set Credentials
```bash
export JIRA_BASE_URL="https://playground-best-team.atlassian.net"
export JIRA_EMAIL="your-email@example.com"
export JIRA_API_TOKEN="your-api-token"
```

### Step 3: Run
```bash
# Using the wrapper script (easiest)
./skills/jira-to-openapi/run.sh SCRUM-10

# Or directly with Python
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-10
```

## Common Use Cases

### Generate Spec for New API
```bash
./skills/jira-to-openapi/run.sh SCRUM-15
```
**Output:**
- `SCRUM-15-openapi.yaml`
- `SCRUM-15-api-documentation.pdf`

### Update Existing API (from GitHub)
```bash
./skills/jira-to-openapi/run.sh SCRUM-16 \
  --repo-url https://github.com/EdytaLys/api-spec-task-manager
```
**What it does:**
- Fetches existing spec from GitHub
- Detects changes (breaking/additive)
- Merges new endpoint
- Highlights changes in PDF

### Update Existing API (from local file)
```bash
./skills/jira-to-openapi/run.sh SCRUM-17 \
  --existing-spec specs/task-manager-openapi.yaml
```

## What You Get

### YAML File
Complete OpenAPI 3.0 specification with:
- All endpoints and methods
- Request/response schemas
- Validation rules in descriptions
- Error scenarios
- JIRA issue reference

### PDF File
Swagger-style documentation with:
- Color-coded HTTP methods
- Change summary (if updating)
- Breaking changes highlighted in red
- Additive changes highlighted in green
- All endpoints and data models

## Workflow

```
1. PO creates JIRA story
   ↓
2. Run: ./run.sh SCRUM-XX
   ↓
3. Review generated files
   ↓
4. Validate in Swagger Editor
   ↓
5. Commit to repository
   ↓
6. Implement API
```

## Troubleshooting

### "Missing environment variables"
Set JIRA credentials (see Step 2 above)

### "401 Unauthorized"
Check your JIRA_EMAIL and JIRA_API_TOKEN

### "404 Not Found"
Verify the JIRA issue key exists

### "reportlab not available"
PDF generation will be skipped. Install with:
```bash
pip install reportlab
```

## Need More Help?

- See `HOW_TO_RUN.md` for detailed documentation
- See `SKILL.md` for skill description
- Check examples in the documentation

## Quick Reference

```bash
# Basic usage
./run.sh SCRUM-10

# With GitHub repo
./run.sh SCRUM-10 --repo-url https://github.com/user/repo

# With local spec
./run.sh SCRUM-10 --existing-spec path/to/spec.yaml

# Custom output
./run.sh SCRUM-10 --output my-api.yaml

# JSON format
./run.sh SCRUM-10 --format json

# Skip PDF
./run.sh SCRUM-10 --no-pdf
```

## Example Output

```
======================================================================
 JIRA to OpenAPI Spec Generator
======================================================================

Checking dependencies...
✓ Dependencies OK

Running generator...

Fetching SCRUM-10 from https://playground-best-team.atlassian.net …
  Summary : Add PATCH /api/tasks/{id} for partial task updates
  ✓  API Purpose
  ✓  API HTTP Method
  ✓  API Request Fields
  ✓  API Validation Rules
  ✓  API Error Scenarios

✓ Spec saved: SCRUM-10-openapi.yaml
  Validate : https://editor.swagger.io/

✓ PDF generated: SCRUM-10-api-documentation.pdf

✓ Done!

Next steps:
  1. Review the generated YAML file
  2. Open in Swagger Editor: https://editor.swagger.io/
  3. Review the PDF documentation
  4. Commit to your repository
```
