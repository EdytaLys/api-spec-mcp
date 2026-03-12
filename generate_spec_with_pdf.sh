#!/bin/bash
# Generate OpenAPI spec and PDF documentation from JIRA story

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "======================================================================"
echo " JIRA to OpenAPI + PDF Generator"
echo "======================================================================"
echo ""

# Check arguments
if [ -z "$1" ]; then
    echo -e "${RED}Error: JIRA issue key required${NC}"
    echo ""
    echo "Usage: ./generate_spec_with_pdf.sh <ISSUE_KEY> [OPTIONS]"
    echo ""
    echo "Examples:"
    echo "  ./generate_spec_with_pdf.sh SCRUM-10"
    echo "  ./generate_spec_with_pdf.sh SCRUM-10 --repo-url https://github.com/user/repo"
    echo ""
    exit 1
fi

ISSUE_KEY=$1
shift  # Remove first argument, keep the rest

# Check environment variables
if [ -z "$JIRA_BASE_URL" ] || [ -z "$JIRA_EMAIL" ] || [ -z "$JIRA_API_TOKEN" ]; then
    echo -e "${RED}Error: Missing environment variables${NC}"
    echo ""
    echo "Please set:"
    echo "  export JIRA_BASE_URL=\"https://your-domain.atlassian.net\""
    echo "  export JIRA_EMAIL=\"your-email@example.com\""
    echo "  export JIRA_API_TOKEN=\"your-api-token\""
    echo ""
    exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check dependencies
echo -e "${YELLOW}Checking dependencies...${NC}"
python3 -c "import requests, yaml, reportlab" 2>/dev/null || {
    echo -e "${RED}Missing dependencies. Installing...${NC}"
    pip install requests pyyaml reportlab
}
echo -e "${GREEN}✓ Dependencies OK${NC}"
echo ""

# Step 1: Generate OpenAPI YAML
echo -e "${BLUE}Step 1: Generating OpenAPI specification...${NC}"
cd "$SCRIPT_DIR/skills/jira-to-openapi"
python3 scripts/generate_spec.py "$ISSUE_KEY" "$@"

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Failed to generate OpenAPI spec${NC}"
    exit 1
fi

echo -e "${GREEN}✓ OpenAPI spec generated${NC}"
echo ""

# Step 2: Generate PDF
echo -e "${BLUE}Step 2: Generating PDF documentation...${NC}"
cd "$SCRIPT_DIR/../api-spec-mcp"

YAML_FILE="${ISSUE_KEY}-openapi.yaml"
PDF_FILE="${ISSUE_KEY}-api-documentation.pdf"

# Check if YAML file exists
if [ ! -f "$YAML_FILE" ]; then
    echo -e "${RED}✗ YAML file not found: $YAML_FILE${NC}"
    exit 1
fi

python3 generate_api_pdf.py "$YAML_FILE" "$PDF_FILE"

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Failed to generate PDF${NC}"
    exit 1
fi

echo -e "${GREEN}✓ PDF documentation generated${NC}"
echo ""

# Summary
echo "======================================================================"
echo -e "${GREEN}✓ Generation Complete!${NC}"
echo "======================================================================"
echo ""
echo "Generated files:"
echo "  📄 YAML: $(pwd)/$YAML_FILE"
echo "  📕 PDF:  $(pwd)/$PDF_FILE"
echo ""
echo "Next steps:"
echo "  1. Review YAML in Swagger Editor: https://editor.swagger.io/"
echo "  2. Open PDF: open $PDF_FILE"
echo "  3. Commit to repository"
echo ""
