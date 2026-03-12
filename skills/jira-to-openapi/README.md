# JIRA to OpenAPI Skill

Generate OpenAPI 3.0 specifications from JIRA user stories with automatic PDF documentation.

## Features

✅ Reads JIRA stories created with the API story generator
✅ Supports both new API creation and existing API updates
✅ Detects breaking and additive changes
✅ Generates OpenAPI 3.0 YAML specifications
✅ Creates Swagger-style PDF documentation
✅ Highlights changes in PDF (breaking changes in red, additive in green)
✅ Merges with existing specifications from GitHub or local files
✅ Auto-increments version numbers based on change type

## Quick Start

### 1. Install
```bash
pip install requests pyyaml reportlab
```

### 2. Configure
```bash
export JIRA_BASE_URL="https://your-domain.atlassian.net"
export JIRA_EMAIL="your-email@example.com"
export JIRA_API_TOKEN="your-api-token"
```

### 3. Run
```bash
# Easiest way - use the wrapper script
./skills/jira-to-openapi/run.sh SCRUM-10

# Or run Python directly
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-10
```

## Documentation

- **[QUICK_START.md](QUICK_START.md)** - Get started in 3 steps
- **[HOW_TO_RUN.md](HOW_TO_RUN.md)** - Comprehensive guide with all options
- **[SKILL.md](SKILL.md)** - Skill description and technical details

## Usage Examples

### New API
```bash
./run.sh SCRUM-15
```
Creates:
- `SCRUM-15-openapi.yaml` - OpenAPI specification
- `SCRUM-15-api-documentation.pdf` - PDF documentation

### Update Existing API
```bash
./run.sh SCRUM-16 --repo-url https://github.com/user/repo
```
- Fetches existing spec from GitHub
- Detects changes
- Merges new endpoint
- Highlights changes in PDF

### With Local Spec
```bash
./run.sh SCRUM-17 --existing-spec specs/api.yaml
```

## Input Format

The skill reads JIRA stories with these sections:

### Request Fields
```
- email, string, required
- username, string, required
- age, integer, optional
- status, enum (ACTIVE/INACTIVE), required
```

### Validation Rules
```
- Email must be valid format and unique
- Username must be 3-20 characters
- Age must be between 18 and 100
```

### Error Scenarios
```
- 400 - Invalid email format
- 409 - Email already registered
- 404 - User not found
```

## Output

### OpenAPI YAML
```yaml
openapi: 3.0.3
info:
  title: Create /api/users endpoint
  version: 1.0.0
  x-jira-issue: SCRUM-15
paths:
  /api/users:
    post:
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UserRequest'
      responses:
        '200':
          description: Successful response
        '400':
          description: Invalid email format
```

### PDF Documentation
- Title page with API info
- Change summary (if updating)
- All endpoints with color-coded methods
- Request/response details
- Data models with required fields marked

## Command Line Options

```
python generate_spec.py <ISSUE_KEY> [OPTIONS]

Required:
  ISSUE_KEY              JIRA issue key (e.g., SCRUM-10)

Optional:
  --output PATH          Output file path
  --format FORMAT        yaml or json (default: yaml)
  --path PATH            Override endpoint path
  --repo-url URL         GitHub repo URL for existing spec
  --existing-spec PATH   Local path to existing spec
  --no-pdf               Skip PDF generation
```

## Integration

### With Story Generator
```bash
# Step 1: Create story
python git/api-spec-mcp/scripts/create_api_update_story.py

# Step 2: Generate spec
./skills/jira-to-openapi/run.sh SCRUM-XX
```

### With CI/CD
```yaml
# .github/workflows/generate-spec.yml
- name: Generate OpenAPI Spec
  run: |
    export JIRA_BASE_URL=${{ secrets.JIRA_BASE_URL }}
    export JIRA_EMAIL=${{ secrets.JIRA_EMAIL }}
    export JIRA_API_TOKEN=${{ secrets.JIRA_API_TOKEN }}
    ./skills/jira-to-openapi/run.sh ${{ github.event.issue.key }}
```

## Change Detection

The skill automatically detects:

### Breaking Changes (Red in PDF)
- Removed endpoints
- Removed methods
- Removed fields
- New required fields
- Removed responses

### Additive Changes (Green in PDF)
- New endpoints
- New methods
- New optional fields
- New responses

### Version Increment
- Breaking changes → Major version (1.0.0 → 2.0.0)
- Additive changes → Minor version (1.0.0 → 1.1.0)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 401 Unauthorized | Check JIRA credentials |
| 404 Not Found | Verify issue key exists |
| Missing dependency | Run `pip install requests pyyaml reportlab` |
| No PDF generated | Install reportlab or use `--no-pdf` |

## Requirements

- Python 3.7+
- requests
- pyyaml
- reportlab (optional, for PDF generation)

## Files

```
skills/jira-to-openapi/
├── README.md              # This file
├── QUICK_START.md         # Quick start guide
├── HOW_TO_RUN.md          # Detailed documentation
├── SKILL.md               # Skill description
├── run.sh                 # Wrapper script
└── scripts/
    └── generate_spec.py   # Main script
```

## Support

For issues or questions:
1. Check [HOW_TO_RUN.md](HOW_TO_RUN.md) for detailed troubleshooting
2. Verify your JIRA credentials are correct
3. Ensure the JIRA story has the required sections
4. Test with a simple story first

## License

Part of the api-spec-mcp project.
