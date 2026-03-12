# Get Started in 5 Minutes

## Prerequisites

- Python 3.7+
- JIRA Cloud account
- 5 minutes of your time

## Step 1: Install (1 minute)

```bash
pip install requests pyyaml reportlab
```

## Step 2: Configure (1 minute)

```bash
export JIRA_BASE_URL="https://your-domain.atlassian.net"
export JIRA_EMAIL="your-email@example.com"
export JIRA_API_TOKEN="your-api-token"
```

Get your API token: https://id.atlassian.com/manage-profile/security/api-tokens

## Step 3: Create Story (2 minutes)

```bash
cd git/api-spec-mcp/scripts
python create_api_update_story.py
```

Follow the prompts:
- Choose story type (new or update)
- Enter endpoint, method, purpose
- Add fields, validation rules, error scenarios

**Result:** JIRA story created (e.g., SCRUM-20)

## Step 4: Generate Spec (1 minute)

```bash
# Generate both YAML and PDF
cd ../..
./generate_spec_with_pdf.sh SCRUM-20
```

**Result:**
- `SCRUM-20-openapi.yaml` - OpenAPI specification
- `SCRUM-20-api-documentation.pdf` - PDF documentation

**Alternative (YAML only):**
```bash
cd skills/jira-to-openapi
./run.sh SCRUM-20
```

Then generate PDF separately:
```bash
cd ../../api-spec-mcp
python generate_api_pdf.py SCRUM-20-openapi.yaml SCRUM-20-api-documentation.pdf
```

## Step 5: Review

Open the YAML in Swagger Editor:
https://editor.swagger.io/

Review the PDF documentation.

## Done! 🎉

You now have:
- ✅ Complete JIRA story
- ✅ OpenAPI 3.0 specification
- ✅ PDF documentation
- ✅ Ready for implementation

## What's Next?

### Learn More
- **Complete workflow**: See `COMPLETE_WORKFLOW.md`
- **Story creation**: See `git/api-spec-mcp/scripts/QUICK_START.md`
- **Spec generation**: See `skills/jira-to-openapi/QUICK_START.md`

### Try Advanced Features
```bash
# Update existing API
./run.sh SCRUM-21 --repo-url https://github.com/your-org/your-repo

# Use local spec
./run.sh SCRUM-22 --existing-spec specs/api.yaml

# JSON output
./run.sh SCRUM-23 --format json
```

### Integrate with CI/CD
Add to your GitHub Actions, GitLab CI, or Jenkins pipeline.

## Quick Reference

### Create Story
```bash
cd git/api-spec-mcp/scripts
python create_api_update_story.py
```

### Generate Spec
```bash
cd ../../skills/jira-to-openapi
./run.sh <ISSUE_KEY>
```

### With Options
```bash
./run.sh SCRUM-XX --repo-url https://github.com/user/repo
./run.sh SCRUM-XX --existing-spec path/to/spec.yaml
./run.sh SCRUM-XX --format json
```

## Troubleshooting

### "Missing environment variables"
Set JIRA credentials (see Step 2)

### "401 Unauthorized"
Check your JIRA_EMAIL and JIRA_API_TOKEN

### "Missing dependency"
Run: `pip install requests pyyaml reportlab`

## Need Help?

- **Quick start**: `QUICK_START.md` files in each folder
- **Detailed guide**: `HOW_TO_RUN.md` in jira-to-openapi folder
- **Complete workflow**: `COMPLETE_WORKFLOW.md`
- **Examples**: Check `EXAMPLE_*.md` files

## Time Savings

- Traditional approach: 75-110 minutes
- With this workflow: 7-13 minutes
- **Savings: 85-90%**

## Support

For issues:
1. Check documentation
2. Verify credentials
3. Test with simple story
4. Review examples

---

**Ready to start?** Run Step 1 above! 🚀
