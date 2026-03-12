#!/bin/bash
# Simple wrapper script to run the JIRA to OpenAPI generator

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================================================"
echo " JIRA to OpenAPI Spec Generator"
echo "======================================================================"
echo ""

# Check if issue key provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: JIRA issue key required${NC}"
    echo ""
    echo "Usage: ./run.sh <ISSUE_KEY> [OPTIONS]"
    echo ""
    echo "Examples:"
    echo "  ./run.sh SCRUM-10"
    echo "  ./run.sh SCRUM-10 --repo-url https://github.com/user/repo"
    echo "  ./run.sh SCRUM-10 --existing-spec specs/api.yaml"
    echo ""
    exit 1
fi

# Check environment variables
if [ -z "$JIRA_BASE_URL" ] || [ -z "$JIRA_EMAIL" ] || [ -z "$JIRA_API_TOKEN" ]; then
    echo -e "${RED}Error: Missing environment variables${NC}"
    echo ""
    echo "Please set:"
    echo "  export JIRA_BASE_URL=\"https://your-domain.atlassian.net\""
    echo "  export JIRA_EMAIL=\"your-email@example.com\""
    echo "  export JIRA_API_TOKEN=\"your-api-token\""
    echo ""
    echo "Get your API token at:"
    echo "  https://id.atlassian.com/manage-profile/security/api-tokens"
    echo ""
    exit 1
fi

# Check Python dependencies
echo -e "${YELLOW}Checking dependencies...${NC}"
python3 -c "import requests, yaml" 2>/dev/null || {
    echo -e "${RED}Missing dependencies. Installing...${NC}"
    pip install requests pyyaml reportlab
}

python3 -c "import reportlab" 2>/dev/null || {
    echo -e "${YELLOW}Warning: reportlab not installed. PDF generation will be skipped.${NC}"
    echo "Install with: pip install reportlab"
    echo ""
}

echo -e "${GREEN}✓ Dependencies OK${NC}"
echo ""

# Run the script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo -e "${YELLOW}Running generator...${NC}"
echo ""

python3 "$SCRIPT_DIR/scripts/generate_spec.py" "$@"

echo ""
echo -e "${GREEN}✓ Done!${NC}"
echo ""
echo "Next steps:"
echo "  1. Review the generated YAML file"
echo "  2. Open in Swagger Editor: https://editor.swagger.io/"
echo "  3. Review the PDF documentation"
echo "  4. Commit to your repository"
echo ""
