#!/bin/bash
# Quick test and fix script

set -e

ISSUE_KEY=${1:-SCRUM-10}

echo "======================================================================"
echo " Testing JIRA Connection and Generating Spec"
echo "======================================================================"
echo ""

# Check environment variables
if [ -z "$JIRA_BASE_URL" ] || [ -z "$JIRA_EMAIL" ] || [ -z "$JIRA_API_TOKEN" ]; then
    echo "❌ Missing environment variables"
    echo ""
    echo "Please set:"
    echo "  export JIRA_BASE_URL=\"https://your-domain.atlassian.net\""
    echo "  export JIRA_EMAIL=\"your-email@example.com\""
    echo "  export JIRA_API_TOKEN=\"your-api-token\""
    echo ""
    exit 1
fi

echo "✓ Environment variables set"
echo "  JIRA_BASE_URL: $JIRA_BASE_URL"
echo "  JIRA_EMAIL: $JIRA_EMAIL"
echo ""

# Test JIRA connection
echo "Testing JIRA connection..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/myself")

if [ "$HTTP_CODE" = "200" ]; then
    echo "✓ JIRA connection successful"
else
    echo "❌ JIRA connection failed (HTTP $HTTP_CODE)"
    echo "   Check your credentials"
    exit 1
fi
echo ""

# Check if issue exists
echo "Checking if $ISSUE_KEY exists..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/issue/$ISSUE_KEY")

if [ "$HTTP_CODE" = "200" ]; then
    echo "✓ Issue $ISSUE_KEY exists"
else
    echo "❌ Issue $ISSUE_KEY not found (HTTP $HTTP_CODE)"
    echo ""
    echo "Available options:"
    echo "  1. Use SCRUM-10 (known to exist): ./test_and_fix.sh SCRUM-10"
    echo "  2. Create a new issue: cd scripts && python create_api_update_story.py"
    echo ""
    exit 1
fi
echo ""

# Generate YAML
echo "Generating OpenAPI YAML..."
cd skills/jira-to-openapi
python3 scripts/generate_spec.py "$ISSUE_KEY"

if [ $? -ne 0 ]; then
    echo "❌ Failed to generate YAML"
    exit 1
fi
echo ""

# Check if YAML was created
YAML_FILE="../../../api-spec-mcp/${ISSUE_KEY}-openapi.yaml"
if [ -f "$YAML_FILE" ]; then
    echo "✓ YAML created: $YAML_FILE"
else
    echo "❌ YAML file not found: $YAML_FILE"
    echo "   The file might have been created in a different location"
    echo "   Searching..."
    find ../../.. -name "${ISSUE_KEY}-openapi.yaml" 2>/dev/null || echo "   Not found"
    exit 1
fi
echo ""

# Generate PDF
echo "Generating PDF..."
cd ../../../api-spec-mcp
python3 generate_api_pdf.py "${ISSUE_KEY}-openapi.yaml" "${ISSUE_KEY}-api-documentation.pdf"

if [ $? -ne 0 ]; then
    echo "❌ Failed to generate PDF"
    exit 1
fi
echo ""

# Summary
echo "======================================================================"
echo "✓ Success!"
echo "======================================================================"
echo ""
echo "Generated files:"
echo "  📄 YAML: $(pwd)/${ISSUE_KEY}-openapi.yaml"
echo "  📕 PDF:  $(pwd)/${ISSUE_KEY}-api-documentation.pdf"
echo ""
echo "Next steps:"
echo "  1. Review YAML: open ${ISSUE_KEY}-openapi.yaml"
echo "  2. Review PDF:  open ${ISSUE_KEY}-api-documentation.pdf"
echo "  3. Validate:    https://editor.swagger.io/"
echo ""
