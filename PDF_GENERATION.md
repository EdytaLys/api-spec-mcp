# PDF Generation Guide

## Overview

PDF documentation is generated from OpenAPI YAML specifications using a separate Python script.

## Quick Answer

**PDF Location:** The PDF is generated in the `api-spec-mcp/` directory after running the generator.

**Example:** `api-spec-mcp/SCRUM-10-api-documentation.pdf`

## How to Generate PDF

### Option 1: Automated (Recommended)

Use the combined script that generates both YAML and PDF:

```bash
cd git/api-spec-mcp
./generate_spec_with_pdf.sh SCRUM-10
```

**Output:**
- `api-spec-mcp/SCRUM-10-openapi.yaml`
- `api-spec-mcp/SCRUM-10-api-documentation.pdf`

### Option 2: Two-Step Process

**Step 1: Generate YAML**
```bash
cd git/api-spec-mcp/skills/jira-to-openapi
python scripts/generate_spec.py SCRUM-10
```

**Step 2: Generate PDF**
```bash
cd ../../../api-spec-mcp
python generate_api_pdf.py SCRUM-10-openapi.yaml SCRUM-10-api-documentation.pdf
```

## File Locations

```
git/api-spec-mcp/
├── generate_spec_with_pdf.sh    # Combined generator (YAML + PDF)
└── skills/jira-to-openapi/
    └── scripts/
        └── generate_spec.py      # YAML generator

api-spec-mcp/
├── generate_api_pdf.py           # PDF generator
├── SCRUM-10-openapi.yaml         # Generated YAML (example)
└── SCRUM-10-api-documentation.pdf # Generated PDF (example)
```

## Example PDF

An example PDF is already available:
```
api-spec-mcp/SCRUM-10-api-documentation.pdf
```

You can open this to see what the output looks like.

## PDF Contents

The generated PDF includes:

### 1. Title Page
- API name
- Version number
- JIRA issue reference
- Generation timestamp
- Change type (if updating)

### 2. API Information
- Description
- Server URLs (Production, Staging)

### 3. Change Summary (if updating)
- **Breaking changes** (red) - Removed endpoints, new required fields
- **Additive changes** (green) - New endpoints, optional fields
- **Modified** (orange) - Updated endpoints

### 4. Endpoints
For each endpoint:
- HTTP method (color-coded: GET=blue, POST=green, PUT=orange, DELETE=red, PATCH=teal)
- Path
- Summary
- Description with validation rules
- Request body schema
- Response codes and descriptions

### 5. Data Models
For each schema:
- Schema name
- Properties table with:
  - Property name (required fields marked with *)
  - Type (including enums and formats)
  - Description

## Requirements

```bash
pip install reportlab pyyaml
```

Or:
```bash
pip install -r api-spec-mcp/requirements-pdf.txt
```

## Customization

To customize PDF appearance, edit:
```
api-spec-mcp/generate_api_pdf.py
```

You can modify:
- **Colors** - Change method colors, heading colors
- **Fonts** - Change font family and sizes
- **Layout** - Adjust margins, spacing
- **Page size** - Change from A4 to Letter
- **Branding** - Add logos, headers, footers

## Complete Workflow

```bash
# 1. Create JIRA story
cd git/api-spec-mcp/scripts
python create_api_update_story.py
# Creates: SCRUM-20 in JIRA

# 2. Generate YAML + PDF
cd ..
./generate_spec_with_pdf.sh SCRUM-20
# Creates: 
#   - api-spec-mcp/SCRUM-20-openapi.yaml
#   - api-spec-mcp/SCRUM-20-api-documentation.pdf

# 3. Review
open ../api-spec-mcp/SCRUM-20-api-documentation.pdf

# 4. Commit
cd ../api-spec-mcp
git add SCRUM-20-openapi.yaml SCRUM-20-api-documentation.pdf
git commit -m "Add API spec for SCRUM-20"
```

## Troubleshooting

### "ModuleNotFoundError: reportlab"
```bash
pip install reportlab
```

### "FileNotFoundError: SCRUM-XX-openapi.yaml"
Generate the YAML first:
```bash
cd git/api-spec-mcp/skills/jira-to-openapi
python scripts/generate_spec.py SCRUM-XX
```

### PDF is blank or incomplete
Check that the YAML is valid:
```bash
# Validate online
open https://editor.swagger.io/
# Paste YAML content
```

### PDF doesn't show changes
Make sure you provided `--repo-url` or `--existing-spec` when generating the YAML:
```bash
./generate_spec_with_pdf.sh SCRUM-XX --repo-url https://github.com/user/repo
```

## Output Examples

### New API PDF
- Title: "Create /api/users endpoint"
- No change summary
- All endpoints shown as new
- Clean, professional layout

### Updated API PDF
- Title: "Update PATCH /api/tasks/{id}"
- Change summary at top:
  - ✓ Additive: New method PATCH /api/tasks/{id}
  - ✓ Additive: New optional field 'priority'
- Changes highlighted in green
- Version incremented (1.0.0 → 1.1.0)

### Breaking Change PDF
- Title: "Remove GET /api/legacy endpoint"
- Change summary at top:
  - ⚠️ Breaking: Removed endpoint GET /api/legacy
  - ⚠️ Breaking: Field 'oldField' is now required
- Breaking changes highlighted in red
- Version incremented (1.0.0 → 2.0.0)

## Integration

### With CI/CD
```yaml
# .github/workflows/generate-spec.yml
- name: Generate Spec and PDF
  run: |
    export JIRA_BASE_URL=${{ secrets.JIRA_BASE_URL }}
    export JIRA_EMAIL=${{ secrets.JIRA_EMAIL }}
    export JIRA_API_TOKEN=${{ secrets.JIRA_API_TOKEN }}
    ./git/api-spec-mcp/generate_spec_with_pdf.sh ${{ github.event.issue.key }}
    
- name: Upload Artifacts
  uses: actions/upload-artifact@v2
  with:
    name: api-spec
    path: |
      api-spec-mcp/*.yaml
      api-spec-mcp/*.pdf
```

### With Documentation Site
```bash
# Copy PDF to docs folder
cp api-spec-mcp/SCRUM-XX-api-documentation.pdf docs/api/
```

## Summary

**To generate PDF:**
```bash
cd git/api-spec-mcp
./generate_spec_with_pdf.sh SCRUM-XX
```

**PDF will be created at:**
```
api-spec-mcp/SCRUM-XX-api-documentation.pdf
```

**View example:**
```
api-spec-mcp/SCRUM-10-api-documentation.pdf
```

That's it! The PDF is automatically generated and saved in the `api-spec-mcp/` directory.
