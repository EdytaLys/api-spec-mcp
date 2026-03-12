# Fix: SCRUM-16 YAML Not Found

## The Problem

The error "YAML file not found: SCRUM-16-openapi.yaml" means the first step (generating the YAML) failed.

## Quick Fix

### Option 1: Use SCRUM-10 (Known to Work)

```bash
cd git/api-spec-mcp
./generate_spec_with_pdf.sh SCRUM-10
```

This will work because SCRUM-10 already exists and has been tested.

### Option 2: Check if SCRUM-16 Exists

```bash
# Test with the diagnostic script
cd git/api-spec-mcp
./test_and_fix.sh SCRUM-16
```

This script will:
1. Test your JIRA connection
2. Check if SCRUM-16 exists
3. Generate YAML if it exists
4. Generate PDF
5. Show you exactly where the error is

### Option 3: Create SCRUM-16 First

If SCRUM-16 doesn't exist, create it:

```bash
cd git/api-spec-mcp/scripts
python create_api_update_story.py
```

Follow the prompts to create the story. Note the issue key it creates (might be SCRUM-25 or similar).

Then generate the spec:
```bash
cd ..
./generate_spec_with_pdf.sh SCRUM-25  # Use the actual issue key
```

### Option 4: Generate YAML Manually to See Error

```bash
cd git/api-spec-mcp/skills/jira-to-openapi
python scripts/generate_spec.py SCRUM-16
```

This will show you the actual error message, such as:
- "404 Not Found" - Issue doesn't exist
- "401 Unauthorized" - Wrong credentials
- Other specific errors

## Step-by-Step Debug

### 1. Check Credentials

```bash
echo "JIRA_BASE_URL: $JIRA_BASE_URL"
echo "JIRA_EMAIL: $JIRA_EMAIL"
echo "JIRA_API_TOKEN: ${JIRA_API_TOKEN:0:10}..."
```

If any are empty, set them:
```bash
export JIRA_BASE_URL="https://playground-best-team.atlassian.net"
export JIRA_EMAIL="your-email@example.com"
export JIRA_API_TOKEN="your-api-token"
```

### 2. Test JIRA Connection

```bash
curl -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/myself"
```

Should return your user info. If you get 401, your credentials are wrong.

### 3. Check if SCRUM-16 Exists

```bash
curl -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/issue/SCRUM-16"
```

If you get 404, the issue doesn't exist. Create it first.

### 4. Generate YAML with Verbose Output

```bash
cd git/api-spec-mcp/skills/jira-to-openapi
python scripts/generate_spec.py SCRUM-16 2>&1 | tee output.log
```

Check `output.log` for errors.

### 5. Check Where YAML Was Created

```bash
# Check current directory
ls -la SCRUM-16-openapi.yaml

# Check api-spec-mcp directory
ls -la ../../../api-spec-mcp/SCRUM-16-openapi.yaml

# Search everywhere
find ~/Desktop/Projects/Playground/GitHub -name "SCRUM-16-openapi.yaml"
```

## Most Likely Causes

### 1. SCRUM-16 Doesn't Exist

**Solution:** Use SCRUM-10 or create a new issue

```bash
./test_and_fix.sh SCRUM-10
```

### 2. Wrong Credentials

**Solution:** Verify and reset credentials

```bash
export JIRA_BASE_URL="https://playground-best-team.atlassian.net"
export JIRA_EMAIL="your-email@example.com"
export JIRA_API_TOKEN="your-api-token"
```

### 3. Script Failed Silently

**Solution:** Run manually to see error

```bash
cd git/api-spec-mcp/skills/jira-to-openapi
python scripts/generate_spec.py SCRUM-16
```

## Working Example

To verify everything works:

```bash
cd git/api-spec-mcp
./test_and_fix.sh SCRUM-10
```

This should succeed and show you:
```
✓ JIRA connection successful
✓ Issue SCRUM-10 exists
✓ YAML created
✓ PDF created
```

## Summary

**Immediate fix:**
```bash
cd git/api-spec-mcp
./test_and_fix.sh SCRUM-10
```

**For SCRUM-16 specifically:**
```bash
cd git/api-spec-mcp
./test_and_fix.sh SCRUM-16
```

This will tell you exactly what's wrong and where.

**Create new issue:**
```bash
cd git/api-spec-mcp/scripts
python create_api_update_story.py
# Note the issue key
cd ..
./test_and_fix.sh SCRUM-XX  # Use the actual key
```
