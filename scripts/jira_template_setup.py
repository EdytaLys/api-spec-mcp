#!/usr/bin/env python3
"""
jira_template_setup.py
======================
One-time onboarding script for the API-First Specification Workflow.

What it does:
  1. Creates 8 custom fields on your Jira Cloud project
  2. Adds them to the default Create/Edit/View screens
  3. Writes jira_automation_rule.json  — import this in Jira Automation UI
  4. Creates one sample "API Story" issue to verify everything works

Usage:
  pip install requests
  python jira_template_setup.py

Configuration:
  Set the four variables in the CONFIG block below, or export as env vars:
    JIRA_BASE_URL  e.g. https://acme.atlassian.net
    JIRA_EMAIL     your admin email
    JIRA_API_TOKEN Personal Access Token (Jira Cloud → Profile → Security)
    JIRA_PROJECT   project key  e.g. CVX
"""

import os, sys, json, textwrap, requests
from requests.auth import HTTPBasicAuth

# ─── CONFIG ───────────────────────────────────────────────────────────────────
CONFIG = {
    "base_url":    os.environ.get("JIRA_BASE_URL",    "https://your-domain.atlassian.net"),
    "email":       os.environ.get("JIRA_EMAIL",       "admin@yourcompany.com"),
    "token":       os.environ.get("JIRA_API_TOKEN",   "YOUR_API_TOKEN_HERE"),
    "project_key": os.environ.get("JIRA_PROJECT",     "PROJ"),
}

# ─── CUSTOM FIELDS ────────────────────────────────────────────────────────────
# Each field will appear on the Jira Create Issue form.
# type options: "com.atlassian.jira.plugin.system.customfieldtypes:textarea"
#               "com.atlassian.jira.plugin.system.customfieldtypes:textfield"
#               "com.atlassian.jira.plugin.system.customfieldtypes:select"
#               "com.atlassian.jira.plugin.system.customfieldtypes:url"

CUSTOM_FIELDS = [
    {
        "name":        "API Purpose",
        "description": "What does this API do? Who calls it and why?",
        "type":        "com.atlassian.jira.plugin.system.customfieldtypes:textarea",
        "searchKey":   "com.atlassian.jira.plugin.system.customfieldtypes:textsearcher",
    },
    {
        "name":        "API HTTP Method",
        "description": "Primary HTTP method for this endpoint.",
        "type":        "com.atlassian.jira.plugin.system.customfieldtypes:select",
        "searchKey":   "com.atlassian.jira.plugin.system.customfieldtypes:multiselectsearcher",
    },
    {
        "name":        "API Request Fields",
        "description": "List all request fields: name, type, required/optional, validation rule.",
        "type":        "com.atlassian.jira.plugin.system.customfieldtypes:textarea",
        "searchKey":   "com.atlassian.jira.plugin.system.customfieldtypes:textsearcher",
    },
    {
        "name":        "API Validation Rules",
        "description": "Business rules and constraints that the API must enforce.",
        "type":        "com.atlassian.jira.plugin.system.customfieldtypes:textarea",
        "searchKey":   "com.atlassian.jira.plugin.system.customfieldtypes:textsearcher",
    },
    {
        "name":        "API Consumers",
        "description": "Which teams or services will call this API?",
        "type":        "com.atlassian.jira.plugin.system.customfieldtypes:textarea",
        "searchKey":   "com.atlassian.jira.plugin.system.customfieldtypes:textsearcher",
    },
    {
        "name":        "API Error Scenarios",
        "description": "List expected error cases (e.g. 400 invalid input, 404 not found).",
        "type":        "com.atlassian.jira.plugin.system.customfieldtypes:textarea",
        "searchKey":   "com.atlassian.jira.plugin.system.customfieldtypes:textsearcher",
    },
    {
        "name":        "API Existing Contract",
        "description": "URL or Confluence page of the existing OpenAPI spec (leave blank for new APIs).",
        "type":        "com.atlassian.jira.plugin.system.customfieldtypes:url",
        "searchKey":   "com.atlassian.jira.plugin.system.customfieldtypes:urlsearcher",
    },
    {
        "name":        "API Change Type",
        "description": "For updates only — is this change Additive or Breaking?",
        "type":        "com.atlassian.jira.plugin.system.customfieldtypes:select",
        "searchKey":   "com.atlassian.jira.plugin.system.customfieldtypes:multiselectsearcher",
    },
]

# Select options (populated after field creation via separate call)
SELECT_OPTIONS = {
    "API HTTP Method": ["GET", "POST", "PUT", "PATCH", "DELETE"],
    "API Change Type": ["Additive", "Breaking"],
}

# ─── HTTP HELPERS ─────────────────────────────────────────────────────────────
def session():
    s = requests.Session()
    s.auth = HTTPBasicAuth(CONFIG["email"], CONFIG["token"])
    s.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
    return s

S = session()
BASE = CONFIG["base_url"].rstrip("/")

def jira_get(path, **kw):
    r = S.get(f"{BASE}{path}", **kw)
    r.raise_for_status()
    return r.json()

def jira_post(path, body):
    r = S.post(f"{BASE}{path}", json=body)
    if r.status_code not in (200, 201):
        print(f"  ⚠  POST {path} → {r.status_code}: {r.text[:200]}")
        return None
    return r.json()

def jira_put(path, body):
    r = S.put(f"{BASE}{path}", json=body)
    if r.status_code not in (200, 201, 204):
        print(f"  ⚠  PUT {path} → {r.status_code}: {r.text[:200]}")
    return r

# ─── STEP 1: CREATE CUSTOM FIELDS ─────────────────────────────────────────────
def create_custom_fields():
    print("\n── Step 1: Creating custom fields ───────────────────────────────────")

    # Fetch existing fields to avoid duplicates
    existing = {f["name"] for f in jira_get("/rest/api/3/field")}

    created = {}
    for field_def in CUSTOM_FIELDS:
        name = field_def["name"]
        if name in existing:
            print(f"  ✓ Already exists: {name}")
            # Look up its ID
            all_fields = jira_get("/rest/api/3/field")
            match = next((f for f in all_fields if f["name"] == name), None)
            if match:
                created[name] = match["id"]
            continue

        payload = {
            "name":        name,
            "description": field_def["description"],
            "type":        field_def["type"],
            "searcherKey": field_def["searchKey"],
        }
        result = jira_post("/rest/api/3/field", payload)
        if result:
            created[name] = result["id"]
            print(f"  ✓ Created: {name}  (id: {result['id']})")
        else:
            print(f"  ✗ Failed:  {name}")

    return created

# ─── STEP 2: ADD SELECT OPTIONS ───────────────────────────────────────────────
def add_select_options(field_ids):
    print("\n── Step 2: Adding select options ────────────────────────────────────")
    for field_name, options in SELECT_OPTIONS.items():
        fid = field_ids.get(field_name)
        if not fid:
            print(f"  ⚠  Field not found: {field_name}")
            continue

        # Get context ID for the field
        contexts = jira_get(f"/rest/api/3/field/{fid}/context")
        if not contexts.get("values"):
            print(f"  ⚠  No context for: {field_name}")
            continue

        ctx_id = contexts["values"][0]["id"]
        payload = {"options": [{"value": v, "disabled": False} for v in options]}
        r = jira_post(f"/rest/api/3/field/{fid}/context/{ctx_id}/option", payload)
        if r is not None:
            print(f"  ✓ Options set for {field_name}: {', '.join(options)}")

# ─── STEP 3: ADD FIELDS TO SCREENS ────────────────────────────────────────────
def add_fields_to_screens(field_ids):
    print("\n── Step 3: Adding fields to Create/Edit/View screens ────────────────")

    screens = jira_get("/rest/api/3/screens", params={"maxResults": 50})
    if not screens.get("values"):
        print("  ⚠  Could not retrieve screens")
        return

    for screen in screens["values"]:
        screen_name = screen["name"].lower()
        if not any(kw in screen_name for kw in ("default", "create", "edit", "view")):
            continue

        sid = screen["id"]
        # Get tabs
        tabs = jira_get(f"/rest/api/3/screens/{sid}/tabs")
        if not tabs:
            continue
        tab_id = tabs[0]["id"]

        # Get existing fields on this tab
        existing = {f["id"] for f in jira_get(f"/rest/api/3/screens/{sid}/tabs/{tab_id}/fields")}

        added = []
        for fname, fid in field_ids.items():
            if fid not in existing:
                result = jira_post(
                    f"/rest/api/3/screens/{sid}/tabs/{tab_id}/fields",
                    {"fieldId": fid}
                )
                if result:
                    added.append(fname)

        if added:
            print(f"  ✓ Screen '{screen['name']}': added {len(added)} field(s)")
        else:
            print(f"  ✓ Screen '{screen['name']}': already up to date")

# ─── STEP 4: WRITE AUTOMATION RULE JSON ───────────────────────────────────────
def write_automation_rule(field_ids):
    print("\n── Step 4: Writing Jira Automation rule JSON ────────────────────────")

    # Build dynamic field references for the rule
    # In Jira Automation, custom fields are referenced as cf[NNNNN]
    def cf(name):
        fid = field_ids.get(name, "customfield_XXXXX")
        return fid.replace("customfield_", "cf[") + "]" if fid.startswith("customfield_") else fid

    rule = {
        "_comment": [
            "API-First Specification Workflow — Jira Automation Rule",
            "Import via: Project Settings → Automation → Import Rules",
            "This rule fires when a Story transitions to 'Ready for Dev'",
            "and the label 'api-spec-required' is present.",
            "It adds a comment with the 8-field template and assigns 'api_spec_status'."
        ],
        "cloud": True,
        "rules": [
            {
                "name": "API-First: Trigger spec workflow on Ready for Dev",
                "state": "ENABLED",
                "description": "When a story with label 'api-spec-required' moves to Ready for Dev, "
                               "post the API spec template as a comment and set spec status to Pending.",
                "trigger": {
                    "component": "TRIGGER",
                    "type": "jira.issue.transitioned",
                    "value": {
                        "toStatus": {"name": "Ready for Dev"},
                        "issueTypes": [{"name": "Story"}]
                    }
                },
                "conditions": [
                    {
                        "component": "CONDITION",
                        "type": "jira.issue.condition",
                        "value": {
                            "conditions": [
                                {
                                    "field": "labels",
                                    "operator": "CONTAINS",
                                    "value": "api-spec-required"
                                }
                            ]
                        }
                    }
                ],
                "actions": [
                    {
                        "component": "ACTION",
                        "type": "jira.issue.comment",
                        "value": {
                            "comment": {
                                "version": 1,
                                "type": "doc",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": "🔧 API-First Spec Workflow — Please complete the fields below before development begins.",
                                                "marks": [{"type": "strong"}]
                                            }
                                        ]
                                    },
                                    {
                                        "type": "paragraph",
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": "Fill in the custom fields on this issue:"
                                            }
                                        ]
                                    },
                                    {
                                        "type": "bulletList",
                                        "content": [
                                            {
                                                "type": "listItem",
                                                "content": [{"type": "paragraph", "content": [{"type": "text", "text": "API Purpose — what does this API do?"}]}]
                                            },
                                            {
                                                "type": "listItem",
                                                "content": [{"type": "paragraph", "content": [{"type": "text", "text": "API HTTP Method — GET / POST / PUT / PATCH / DELETE"}]}]
                                            },
                                            {
                                                "type": "listItem",
                                                "content": [{"type": "paragraph", "content": [{"type": "text", "text": "API Request Fields — name, type, required/optional, validation"}]}]
                                            },
                                            {
                                                "type": "listItem",
                                                "content": [{"type": "paragraph", "content": [{"type": "text", "text": "API Validation Rules — business rules and constraints"}]}]
                                            },
                                            {
                                                "type": "listItem",
                                                "content": [{"type": "paragraph", "content": [{"type": "text", "text": "API Consumers — which teams / services will call this?"}]}]
                                            },
                                            {
                                                "type": "listItem",
                                                "content": [{"type": "paragraph", "content": [{"type": "text", "text": "API Error Scenarios — expected error cases (400, 404, 409…)"}]}]
                                            },
                                            {
                                                "type": "listItem",
                                                "content": [{"type": "paragraph", "content": [{"type": "text", "text": "API Existing Contract — Confluence URL (leave blank for new APIs)"}]}]
                                            },
                                            {
                                                "type": "listItem",
                                                "content": [{"type": "paragraph", "content": [{"type": "text", "text": "API Change Type — Additive or Breaking (for updates only)"}]}]
                                            }
                                        ]
                                    },
                                    {
                                        "type": "paragraph",
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": "Once all fields are completed, click Approve Spec Template to trigger automatic OpenAPI spec generation."
                                            }
                                        ]
                                    }
                                ]
                            }
                        }
                    },
                    {
                        "component": "ACTION",
                        "type": "jira.issue.assign",
                        "value": {
                            "assignee": "{{issue.reporter}}"
                        },
                        "_comment": "Reassign to reporter (PO) to fill in the template"
                    },
                    {
                        "component": "ACTION",
                        "type": "jira.issue.label",
                        "value": {
                            "labels": ["api-spec-pending"]
                        },
                        "_comment": "Adds label so MCP webhook knows template needs completion"
                    }
                ]
            },
            {
                "name": "API-First: Block transition if template fields missing",
                "state": "ENABLED",
                "description": "Prevents 'In Progress' transition if API Purpose field is empty on api-spec-required stories.",
                "trigger": {
                    "component": "TRIGGER",
                    "type": "jira.issue.transitioned",
                    "value": {
                        "toStatus": {"name": "In Progress"},
                        "issueTypes": [{"name": "Story"}]
                    }
                },
                "conditions": [
                    {
                        "component": "CONDITION",
                        "type": "jira.issue.condition",
                        "value": {
                            "conditions": [
                                {
                                    "field": "labels",
                                    "operator": "CONTAINS",
                                    "value": "api-spec-required"
                                },
                                {
                                    "field": f"{field_ids.get('API Purpose', 'customfield_API_PURPOSE')}",
                                    "operator": "IS_EMPTY"
                                }
                            ],
                            "operator": "AND"
                        }
                    }
                ],
                "actions": [
                    {
                        "component": "ACTION",
                        "type": "jira.issue.transition",
                        "value": {
                            "transition": {"name": "Ready for Dev"},
                            "_comment": "Roll back to Ready for Dev"
                        }
                    },
                    {
                        "component": "ACTION",
                        "type": "jira.issue.comment",
                        "value": {
                            "comment": {
                                "version": 1,
                                "type": "doc",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": "⛔ Cannot start development — API spec template fields are not yet completed. Please fill in all API-* fields and get spec approved first.",
                                                "marks": [{"type": "strong"}]
                                            }
                                        ]
                                    }
                                ]
                            }
                        }
                    }
                ]
            }
        ]
    }

    out_path = os.path.join(os.path.dirname(__file__), "jira_automation_rule.json")
    with open(out_path, "w") as f:
        json.dump(rule, f, indent=2)
    print(f"  ✓ Written: {out_path}")
    print("  → Import in Jira: Project Settings → Automation → ⋮ → Import Rules")
    return out_path

# ─── STEP 5: CREATE SAMPLE ISSUE ──────────────────────────────────────────────
def create_sample_issue(field_ids):
    print("\n── Step 5: Creating sample API story ────────────────────────────────")

    def field(name):
        return field_ids.get(name)

    issue_body = {
        "fields": {
            "project":   {"key": CONFIG["project_key"]},
            "issuetype": {"name": "Story"},
            "summary":   "[API-FIRST SAMPLE] POST /payments/initiate — Create payment intent",
            "description": {
                "version": 1,
                "type": "doc",
                "content": [
                    {"type": "paragraph", "content": [
                        {"type": "text", "text": "Sample story created by jira_template_setup.py to verify custom fields."}
                    ]}
                ]
            },
            "labels": ["api-spec-required"],
        }
    }

    # Add custom fields if we have their IDs
    cf = issue_body["fields"]
    if field("API Purpose"):
        cf[field("API Purpose")] = "Create a new payment intent and return a payment token for client-side confirmation."
    if field("API Request Fields"):
        cf[field("API Request Fields")] = (
            "amount        | integer  | required | min: 1, max: 99999999 (pence)\n"
            "currency      | string   | required | ISO 4217 code (GBP, EUR, USD)\n"
            "merchant_ref  | string   | required | max 50 chars, alphanumeric\n"
            "customer_id   | string   | optional | UUID v4"
        )
    if field("API Validation Rules"):
        cf[field("API Validation Rules")] = (
            "Amount must be positive integer.\n"
            "Currency must be ISO 4217 3-letter code.\n"
            "Duplicate merchant_ref within 24h returns 409 Conflict."
        )
    if field("API Consumers"):
        cf[field("API Consumers")] = "Checkout Team (Frontend)\nMobile Team (iOS / Android)"
    if field("API Error Scenarios"):
        cf[field("API Error Scenarios")] = (
            "400 — invalid amount or currency\n"
            "409 — duplicate merchant_ref\n"
            "422 — customer_id not found\n"
            "503 — payment provider unavailable"
        )

    result = jira_post("/rest/api/3/issue", issue_body)
    if result:
        issue_key = result.get("key", "?")
        print(f"  ✓ Created sample issue: {issue_key}")
        print(f"  → {BASE}/browse/{issue_key}")
    else:
        print("  ✗ Failed to create sample issue")

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print(" Jira API-First Template Setup")
    print(f" Project: {CONFIG['project_key']}  |  {BASE}")
    print("=" * 65)

    # Validate config
    if "your-domain" in BASE or "YOUR_API_TOKEN" in CONFIG["token"]:
        print("\n⛔  CONFIG not set. Edit the CONFIG block at the top of this script")
        print("   or export JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT.\n")
        sys.exit(1)

    # Test connection
    try:
        me = jira_get("/rest/api/3/myself")
        print(f"\n✓ Connected as: {me.get('displayName', me.get('emailAddress', '?'))}")
    except requests.HTTPError as e:
        print(f"\n⛔  Connection failed: {e}")
        sys.exit(1)

    # Run steps
    field_ids = create_custom_fields()
    if field_ids:
        add_select_options(field_ids)
        add_fields_to_screens(field_ids)

    write_automation_rule(field_ids)

    # Ask before creating sample issue
    answer = input("\nCreate a sample API story to verify the setup? (y/N): ").strip().lower()
    if answer == "y":
        create_sample_issue(field_ids)

    # Summary
    print("\n" + "=" * 65)
    print(" Setup complete. Field IDs created:")
    for name, fid in field_ids.items():
        print(f"   {fid:30s}  {name}")
    print("\n Next steps:")
    print("   1. Import jira_automation_rule.json in Jira Automation")
    print("   2. Add 'api-spec-required' label to API stories")
    print("   3. Configure MCP server with these field IDs")
    print("=" * 65)

if __name__ == "__main__":
    main()
