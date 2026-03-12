# Troubleshooting Guide

## Error: "YAML file not found: SCRUM-XX-openapi.yaml"

This error means the OpenAPI YAML file wasn't generated in the first step.

### Common Causes

1. **JIRA issue doesn't exist**
2. **JIRA credentials are incorrect**
3. **Issue doesn't have required fields**
4. **Script failed silently**

### How to Fix

#### Step 1: Check if JIRA issue exists

```bash
# Set credentials
export JIRA_BASE_URL="https://playground-best-team.atlassian.net"
export JIRA_EMAIL="your-email@example.com"
export JIRA_API_TOKEN="your-api-token"

# Test connection
curl -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/issue/SCRUM-16" | jq .
```

If you get 404, the issue doesn't exist. Create it first:
```bash
cd git/api-spec-mcp/scripts
python create_api_update_story.py
```

#### Step 2: Generate YAML manually to see errors

```bash
cd git/api-spec-mcp/skills/jira-to-openapi
python scripts/generate_spec.py SCRUM-16
```

This will show you the actual error message.

#### Step 3: Check the output

Look for these error messages:

**"401 Unauthorized"**
```
⛔  401 Unauthorized — check JIRA_EMAIL and JIRA_API_TOKEN
```
**Fix:** Verify your credentials are correct

**"404 Not Found"**
```
⛔  404 Not Found — issue SCRUM-16 does not exist
```
**Fix:** Create the issue first or use a different issue key

**"No custom field IDs found"**
```
⛔  No custom field IDs found
```
**Fix:** The script will try to fetch field IDs automatically. If this fails, the issue might not have the required fields.

#### Step 4: Verify YAML was created

```bash
ls -la ../../../api-spec-mcp/SCRUM-16-openapi.yaml
```

If the file exists, you can now generate the PDF:
```bash
cd ../../../api-spec-mcp
python generate_api_pdf.py SCRUM-16-openapi.yaml SCRUM-16-api-documentation.pdf
```

### Complete Debug Process

```bash
# 1. Check environment variables
echo "JIRA_BASE_URL: $JIRA_BASE_URL"
echo "JIRA_EMAIL: $JIRA_EMAIL"
echo "JIRA_API_TOKEN: ${JIRA_API_TOKEN:0:10}..." # Show first 10 chars

# 2. Test JIRA connection
curl -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/myself" | jq .displayName

# 3. Check if issue exists
curl -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/issue/SCRUM-16" | jq .key

# 4. Generate YAML with verbose output
cd git/api-spec-mcp/skills/jira-to-openapi
python scripts/generate_spec.py SCRUM-16 2>&1 | tee generation.log

# 5. Check if YAML was created
ls -la ../../../api-spec-mcp/SCRUM-16-openapi.yaml

# 6. If YAML exists, generate PDF
cd ../../../api-spec-mcp
python generate_api_pdf.py SCRUM-16-openapi.yaml SCRUM-16-api-documentation.pdf
```

### Working Example

Use the existing SCRUM-10 issue to test:

```bash
cd git/api-spec-mcp
./generate_spec_with_pdf.sh SCRUM-10
```

This should work because SCRUM-10 already exists.

### Create a Test Issue

If you want to test with a new issue:

```bash
# 1. Create story
cd git/api-spec-mcp/scripts
python create_api_update_story.py

# Follow prompts - this will create a new issue (e.g., SCRUM-25)

# 2. Generate spec + PDF
cd ..
./generate_spec_with_pdf.sh SCRUM-25
```

## Other Common Issues

### "Missing dependency: pip install requests"

**Fix:**
```bash
pip install requests pyyaml reportlab
```

### "ModuleNotFoundError: reportlab"

**Fix:**
```bash
pip install reportlab
```

PDF generation will be skipped if reportlab is not installed, but YAML will still be generated.

### "Permission denied: ./generate_spec_with_pdf.sh"

**Fix:**
```bash
chmod +x git/api-spec-mcp/generate_spec_with_pdf.sh
```

### YAML is generated but PDF fails

**Check YAML is valid:**
```bash
# Install yq (YAML processor)
brew install yq  # macOS
# or
pip install yq

# Validate YAML
yq . api-spec-mcp/SCRUM-16-openapi.yaml
```

**Generate PDF manually:**
```bash
cd api-spec-mcp
python generate_api_pdf.py SCRUM-16-openapi.yaml SCRUM-16-api-documentation.pdf
```

### Script runs but no output

**Check where you are:**
```bash
pwd
# Should be: /path/to/GitHub/git/api-spec-mcp
```

**Check output directory:**
```bash
ls -la ../api-spec-mcp/*.yaml
ls -la ../api-spec-mcp/*.pdf
```

The YAML and PDF are created in `api-spec-mcp/` (parent directory), not `git/api-spec-mcp/`.

## Quick Fixes

### Fix 1: Use existing issue
```bash
cd git/api-spec-mcp
./generate_spec_with_pdf.sh SCRUM-10
```

### Fix 2: Create new issue first
```bash
cd git/api-spec-mcp/scripts
python create_api_update_story.py
# Note the issue key (e.g., SCRUM-25)

cd ..
./generate_spec_with_pdf.sh SCRUM-25
```

### Fix 3: Generate YAML separately
```bash
# Generate YAML
cd git/api-spec-mcp/skills/jira-to-openapi
python scripts/generate_spec.py SCRUM-16

# Check if it was created
ls -la ../../../api-spec-mcp/SCRUM-16-openapi.yaml

# Generate PDF
cd ../../../api-spec-mcp
python generate_api_pdf.py SCRUM-16-openapi.yaml SCRUM-16-api-documentation.pdf
```

## Still Having Issues?

### Check the logs

The script outputs detailed information. Look for:
- ✓ marks indicate success
- ✗ marks indicate failure
- Error messages explain what went wrong

### Verify prerequisites

```bash
# Python version (need 3.7+)
python3 --version

# Dependencies
python3 -c "import requests, yaml, reportlab; print('All dependencies OK')"

# JIRA credentials
env | grep JIRA
```

### Test with minimal example

Create a simple test:

```bash
# Create test script
cat > test_jira.py << 'EOF'
import os
import requests
from requests.auth import HTTPBasicAuth

base_url = os.environ.get("JIRA_BASE_URL")
email = os.environ.get("JIRA_EMAIL")
token = os.environ.get("JIRA_API_TOKEN")

print(f"Testing connection to {base_url}")
r = requests.get(
    f"{base_url}/rest/api/3/myself",
    auth=HTTPBasicAuth(email, token)
)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    print(f"Connected as: {r.json()['displayName']}")
else:
    print(f"Error: {r.text}")
EOF

python3 test_jira.py
```

## Summary

**Most common issue:** JIRA issue doesn't exist or credentials are wrong.

**Quick fix:**
1. Verify credentials are set
2. Check issue exists in JIRA
3. Run YAML generation manually to see errors
4. Generate PDF separately if needed

**Working example:**
```bash
cd git/api-spec-mcp
./generate_spec_with_pdf.sh SCRUM-10
```
