# How to Generate PDF Documentation

## Current Setup

The PDF generation is currently available as a **separate script** that you run after generating the OpenAPI YAML.

## Location

The PDF generator is located at:
```
api-spec-mcp/generate_api_pdf.py
```

## Quick Usage

### Step 1: Generate OpenAPI YAML
```bash
cd git/api-spec-mcp/skills/jira-to-openapi
python scripts/generate_spec.py SCRUM-10
```

**Output:** `SCRUM-10-openapi.yaml`

### Step 2: Generate PDF
```bash
cd ../../../api-spec-mcp
python generate_api_pdf.py SCRUM-10-openapi.yaml SCRUM-10-api-documentation.pdf
```

**Output:** `SCRUM-10-api-documentation.pdf`

## One-Line Command

```bash
# Generate both YAML and PDF
cd git/api-spec-mcp/skills/jira-to-openapi && \
python scripts/generate_spec.py SCRUM-10 && \
cd ../../../api-spec-mcp && \
python generate_api_pdf.py SCRUM-10-openapi.yaml SCRUM-10-api-documentation.pdf
```

## Automated Script

Create a wrapper script to do both:

```bash
#!/bin/bash
# generate_spec_with_pdf.sh

ISSUE_KEY=$1

if [ -z "$ISSUE_KEY" ]; then
    echo "Usage: ./generate_spec_with_pdf.sh SCRUM-XX"
    exit 1
fi

echo "Generating OpenAPI spec for $ISSUE_KEY..."
cd git/api-spec-mcp/skills/jira-to-openapi
python scripts/generate_spec.py $ISSUE_KEY

echo "Generating PDF documentation..."
cd ../../../api-spec-mcp
python generate_api_pdf.py ${ISSUE_KEY}-openapi.yaml ${ISSUE_KEY}-api-documentation.pdf

echo "✓ Done!"
echo "  YAML: ${ISSUE_KEY}-openapi.yaml"
echo "  PDF:  ${ISSUE_KEY}-api-documentation.pdf"
```

Save as `generate_spec_with_pdf.sh` and run:
```bash
chmod +x generate_spec_with_pdf.sh
./generate_spec_with_pdf.sh SCRUM-10
```

## Example Output

After running both scripts, you'll have:
- `SCRUM-10-openapi.yaml` - OpenAPI specification
- `SCRUM-10-api-documentation.pdf` - PDF documentation

## PDF Features

The generated PDF includes:
- ✅ Title page with API info
- ✅ Version and JIRA issue reference
- ✅ Server URLs
- ✅ All endpoints with color-coded HTTP methods
- ✅ Request/response details
- ✅ Data models with required fields marked
- ✅ Professional Swagger-style formatting

## Requirements

```bash
pip install reportlab pyyaml
```

Or use the requirements file:
```bash
pip install -r api-spec-mcp/requirements-pdf.txt
```

## Existing Example

There's already an example PDF in the repository:
```
api-spec-mcp/SCRUM-10-api-documentation.pdf
```

You can open this to see what the output looks like.

## Customization

To customize the PDF appearance, edit:
```
api-spec-mcp/generate_api_pdf.py
```

You can modify:
- Colors
- Fonts
- Layout
- Page size
- Headers/footers

## Integration with Workflow

### Complete Workflow
```bash
# 1. Create JIRA story
cd git/api-spec-mcp/scripts
python create_api_update_story.py

# 2. Generate OpenAPI spec
cd ../skills/jira-to-openapi
python scripts/generate_spec.py SCRUM-XX

# 3. Generate PDF
cd ../../../api-spec-mcp
python generate_api_pdf.py SCRUM-XX-openapi.yaml SCRUM-XX-api-documentation.pdf

# 4. Review
open SCRUM-XX-api-documentation.pdf
```

## Future Enhancement

The PDF generation will be integrated directly into `generate_spec.py` so you only need to run one command. For now, use the two-step process above.

## Troubleshooting

### "ModuleNotFoundError: reportlab"
```bash
pip install reportlab
```

### "FileNotFoundError: SCRUM-XX-openapi.yaml"
Make sure you run the spec generator first:
```bash
python skills/jira-to-openapi/scripts/generate_spec.py SCRUM-XX
```

### PDF looks wrong
Check that the YAML file is valid:
```bash
# Validate in Swagger Editor
open https://editor.swagger.io/
# Paste the YAML content
```

## Summary

**Current Process:**
1. Generate YAML: `python generate_spec.py SCRUM-XX`
2. Generate PDF: `python generate_api_pdf.py SCRUM-XX-openapi.yaml SCRUM-XX-api-documentation.pdf`

**Files:**
- YAML generator: `git/api-spec-mcp/skills/jira-to-openapi/scripts/generate_spec.py`
- PDF generator: `api-spec-mcp/generate_api_pdf.py`
- Example PDF: `api-spec-mcp/SCRUM-10-api-documentation.pdf`
