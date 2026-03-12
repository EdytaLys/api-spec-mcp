# API-First Specification Workflow

Complete system for creating JIRA stories and generating OpenAPI specifications with PDF documentation.

## Quick Start

```bash
# 1. Install
pip install requests pyyaml reportlab

# 2. Configure
export JIRA_BASE_URL="https://your-domain.atlassian.net"
export JIRA_EMAIL="your-email@example.com"
export JIRA_API_TOKEN="your-api-token"

# 3. Create story
cd scripts
python create_api_update_story.py

# 4. Generate spec + PDF
cd ..
./generate_spec_with_pdf.sh SCRUM-XX
```

## Documentation

### Getting Started
- **[GET_STARTED.md](GET_STARTED.md)** - 5-minute quick start
- **[COMPLETE_WORKFLOW.md](COMPLETE_WORKFLOW.md)** - End-to-end workflow
- **[PDF_GENERATION.md](PDF_GENERATION.md)** - How to generate PDFs

### Story Creation
- **[scripts/QUICK_START.md](scripts/QUICK_START.md)** - Quick reference
- **[scripts/PO_QUICK_REFERENCE.md](scripts/PO_QUICK_REFERENCE.md)** - PO guide
- **[scripts/README.md](scripts/README.md)** - Detailed documentation

### Spec Generation
- **[skills/jira-to-openapi/QUICK_START.md](skills/jira-to-openapi/QUICK_START.md)** - 3-step setup
- **[skills/jira-to-openapi/HOW_TO_RUN.md](skills/jira-to-openapi/HOW_TO_RUN.md)** - Complete guide
- **[skills/jira-to-openapi/GENERATE_PDF.md](skills/jira-to-openapi/GENERATE_PDF.md)** - PDF generation

## Features

### Story Creation
✅ Interactive CLI for creating JIRA stories
✅ Supports new APIs and updates
✅ Plain English input (no technical knowledge required)
✅ Collects fields, validation rules, error scenarios
✅ Creates stories in 30 seconds to 3 minutes
✅ Consistent format with helpful examples

### Spec Generation
✅ Generates OpenAPI 3.0 specifications
✅ Creates Swagger-style PDF documentation
✅ Detects breaking and additive changes
✅ Merges with existing specs from GitHub or local files
✅ Auto-increments version numbers
✅ Highlights changes in PDF (red=breaking, green=additive)

## File Structure

```
git/api-spec-mcp/
├── README.md                      # This file
├── GET_STARTED.md                 # Quick start guide
├── COMPLETE_WORKFLOW.md           # End-to-end workflow
├── PDF_GENERATION.md              # PDF generation guide
├── generate_spec_with_pdf.sh      # Combined generator script
├── scripts/                       # Story creation scripts
│   ├── create_api_update_story.py # Main story generator
│   ├── QUICK_START.md
│   ├── PO_QUICK_REFERENCE.md
│   └── README.md
└── skills/jira-to-openapi/        # Spec generation
    ├── QUICK_START.md
    ├── HOW_TO_RUN.md
    ├── GENERATE_PDF.md
    ├── README.md
    ├── run.sh                     # YAML generator wrapper
    └── scripts/
        └── generate_spec.py       # Main spec generator

api-spec-mcp/                      # Output directory
├── generate_api_pdf.py            # PDF generator
├── SCRUM-XX-openapi.yaml          # Generated specs
└── SCRUM-XX-api-documentation.pdf # Generated PDFs
```

## Usage Examples

### Create New API Story
```bash
cd scripts
python create_api_update_story.py
# Choose: 1 (New API)
# Enter: /api/users, POST, register new users
# Add fields, validation rules, error scenarios
```

### Generate Spec + PDF
```bash
cd ..
./generate_spec_with_pdf.sh SCRUM-15
```

**Output:**
- `api-spec-mcp/SCRUM-15-openapi.yaml`
- `api-spec-mcp/SCRUM-15-api-documentation.pdf`

### Update Existing API
```bash
./generate_spec_with_pdf.sh SCRUM-16 \
  --repo-url https://github.com/EdytaLys/api-spec-task-manager
```

**What it does:**
- Fetches existing spec from GitHub
- Detects changes (breaking/additive)
- Merges new endpoint
- Increments version
- Highlights changes in PDF

## Time Savings

| Task | Traditional | With This System | Savings |
|------|-------------|------------------|---------|
| Story creation | 15-20 min | 2-3 min | 85% |
| Spec writing | 30-45 min | Instant | 100% |
| Documentation | 20-30 min | Instant | 100% |
| **Total** | **65-95 min** | **2-3 min** | **97%** |

## Requirements

- Python 3.7+
- JIRA Cloud account with API access
- Dependencies: `requests`, `pyyaml`, `reportlab`

## Installation

```bash
# Install dependencies
pip install requests pyyaml reportlab

# Or use requirements file
pip install -r api-spec-mcp/requirements-pdf.txt

# Set credentials
export JIRA_BASE_URL="https://your-domain.atlassian.net"
export JIRA_EMAIL="your-email@example.com"
export JIRA_API_TOKEN="your-api-token"
```

Get API token: https://id.atlassian.com/manage-profile/security/api-tokens

## Examples

### Example 1: New User Registration API
```bash
# Create story
python scripts/create_api_update_story.py
# Input: /api/users, POST, register new users
# Fields: email, username, password (all required)
# Validation: Email unique, username 3-20 chars, password 8+ chars
# Errors: 400 invalid, 409 duplicate

# Generate spec
./generate_spec_with_pdf.sh SCRUM-20
```

### Example 2: Add PATCH Endpoint
```bash
# Create story
python scripts/create_api_update_story.py
# Input: PATCH /api/tasks/{id}, partial updates
# Fields: title, status, dueDate (all optional)
# Validation: Title unique if provided, status valid enum
# Errors: 400 invalid, 404 not found, 409 conflict

# Generate spec with existing API
./generate_spec_with_pdf.sh SCRUM-21 \
  --repo-url https://github.com/EdytaLys/api-spec-task-manager
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Missing dependencies | `pip install requests pyyaml reportlab` |
| 401 Unauthorized | Check JIRA credentials |
| 404 Not Found | Verify issue key exists |
| No PDF generated | Check reportlab is installed |
| YAML validation fails | Review story format |

## Support

- Check documentation in respective folders
- Review example files
- Verify credentials and permissions
- Test with simple stories first

## Next Steps

1. Read [GET_STARTED.md](GET_STARTED.md) for quick start
2. Create your first story
3. Generate the spec and PDF
4. Review in Swagger Editor
5. Implement your API

## License

Part of the api-spec-mcp project.
