#!/usr/bin/env python3
"""
jira_form_setup.py
==================
Creates a Jira Issue Form that includes all 8 API-First custom fields.

The script:
  1. Reads existing custom-field IDs (from jira_field_config.json or live lookup)
  2. Creates any missing custom fields (same definitions as jira_template_setup.py)
  3. Creates an Issue Form in the target project via the Jira Forms REST API
  4. Configures every field: required status, descriptions, and display hints
  5. Prints the form ID and direct URL so you can share or embed it immediately

Requirements:
  pip install requests

Configuration (env vars or edit the CONFIG block):
  JIRA_BASE_URL   e.g. https://acme.atlassian.net
  JIRA_EMAIL      admin email
  JIRA_API_TOKEN  Personal Access Token (Profile → Security → API tokens)
  JIRA_PROJECT    project key  e.g. CVX

Notes:
  • The Jira Forms API (/rest/api/3/project/{key}/form) requires a Jira Cloud
    Standard plan or above. Free-tier projects will receive a 403/404.
  • If the Forms API is unavailable the script prints a manual workaround.
  • Running the script twice is safe — it skips fields that already exist and
    offers to update an existing form rather than duplicate it.
"""

import os, sys, json, requests
from requests.auth import HTTPBasicAuth
from pathlib import Path

# ─── CONFIG ───────────────────────────────────────────────────────────────────
CONFIG = {
    "base_url":    os.environ.get("JIRA_BASE_URL",    "https://your-domain.atlassian.net"),
    "email":       os.environ.get("JIRA_EMAIL",       "admin@yourcompany.com"),
    "token":       os.environ.get("JIRA_API_TOKEN",   "YOUR_API_TOKEN_HERE"),
    "project_key": os.environ.get("JIRA_PROJECT",     "PROJ"),
}

FORM_NAME        = "API-First Specification Form"
FORM_DESCRIPTION = (
    "Complete this form when creating a new API story or requesting a change "
    "to an existing contract. All fields marked required must be filled before "
    "the story can move to In Progress."
)

# ─── CUSTOM FIELD DEFINITIONS ─────────────────────────────────────────────────
# Kept in sync with jira_template_setup.py
CUSTOM_FIELDS = [
    {
        "name":        "API Purpose",
        "description": "What does this API do? Who calls it and why?",
        "type":        "com.atlassian.jira.plugin.system.customfieldtypes:textarea",
        "searchKey":   "com.atlassian.jira.plugin.system.customfieldtypes:textsearcher",
        "required":    True,
        "hint":        "Describe the business goal this endpoint fulfils and which consumers will call it.",
    },
    {
        "name":        "API HTTP Method",
        "description": "Primary HTTP method for this endpoint.",
        "type":        "com.atlassian.jira.plugin.system.customfieldtypes:select",
        "searchKey":   "com.atlassian.jira.plugin.system.customfieldtypes:multiselectsearcher",
        "required":    True,
        "hint":        "Choose the primary HTTP verb: GET, POST, PUT, PATCH, or DELETE.",
    },
    {
        "name":        "API Request Fields",
        "description": "List all request fields: name, type, required/optional, validation rule.",
        "type":        "com.atlassian.jira.plugin.system.customfieldtypes:textarea",
        "searchKey":   "com.atlassian.jira.plugin.system.customfieldtypes:textsearcher",
        "required":    True,
        "hint":        "One field per line — name | type | required/optional | validation rule.",
    },
    {
        "name":        "API Validation Rules",
        "description": "Business rules and constraints that the API must enforce.",
        "type":        "com.atlassian.jira.plugin.system.customfieldtypes:textarea",
        "searchKey":   "com.atlassian.jira.plugin.system.customfieldtypes:textsearcher",
        "required":    True,
        "hint":        "List every constraint, uniqueness rule, range check, and invariant.",
    },
    {
        "name":        "API Consumers",
        "description": "Which teams or services will call this API?",
        "type":        "com.atlassian.jira.plugin.system.customfieldtypes:textarea",
        "searchKey":   "com.atlassian.jira.plugin.system.customfieldtypes:textsearcher",
        "required":    True,
        "hint":        "e.g. Checkout Team (Frontend), Mobile Team (iOS / Android).",
    },
    {
        "name":        "API Error Scenarios",
        "description": "List expected error cases (e.g. 400 invalid input, 404 not found).",
        "type":        "com.atlassian.jira.plugin.system.customfieldtypes:textarea",
        "searchKey":   "com.atlassian.jira.plugin.system.customfieldtypes:textsearcher",
        "required":    True,
        "hint":        "HTTP status code — reason.  e.g. 409 — duplicate merchant_ref.",
    },
    {
        "name":        "API Existing Contract",
        "description": "URL or Confluence page of the existing OpenAPI spec (leave blank for new APIs).",
        "type":        "com.atlassian.jira.plugin.system.customfieldtypes:url",
        "searchKey":   "com.atlassian.jira.plugin.system.customfieldtypes:urlsearcher",
        "required":    False,
        "hint":        "Link to the current OpenAPI/Swagger spec in Confluence or GitHub. Leave blank for new APIs.",
    },
    {
        "name":        "API Change Type",
        "description": "For updates only — is this change Additive or Breaking?",
        "type":        "com.atlassian.jira.plugin.system.customfieldtypes:select",
        "searchKey":   "com.atlassian.jira.plugin.system.customfieldtypes:multiselectsearcher",
        "required":    False,
        "hint":        "Additive — new optional fields/endpoints. Breaking — removes or renames existing contract.",
    },
]

SELECT_OPTIONS = {
    "API HTTP Method": ["GET", "POST", "PUT", "PATCH", "DELETE"],
    "API Change Type": ["Additive", "Breaking"],
}

# ─── HTTP HELPERS ─────────────────────────────────────────────────────────────
def _session():
    s = requests.Session()
    s.auth = HTTPBasicAuth(CONFIG["email"], CONFIG["token"])
    s.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
    return s

S    = _session()
BASE = CONFIG["base_url"].rstrip("/")

def _get(path, **kw):
    r = S.get(f"{BASE}{path}", **kw)
    r.raise_for_status()
    return r.json()

def _post(path, body, *, ok=(200, 201)):
    r = S.post(f"{BASE}{path}", json=body)
    if r.status_code not in ok:
        print(f"  ⚠  POST {path} → {r.status_code}: {r.text[:300]}")
        return None
    return r.json()

def _put(path, body, *, ok=(200, 201, 204)):
    r = S.put(f"{BASE}{path}", json=body)
    if r.status_code not in ok:
        print(f"  ⚠  PUT {path} → {r.status_code}: {r.text[:300]}")
    return r

# ─── STEP 1: ENSURE CUSTOM FIELDS EXIST ───────────────────────────────────────
def ensure_custom_fields() -> dict[str, str]:
    """Return {field_name: field_id} for all 8 custom fields, creating missing ones."""
    print("\n── Step 1: Ensuring custom fields exist ─────────────────────────────")

    all_fields  = _get("/rest/api/3/field")
    existing_by_name = {f["name"]: f["id"] for f in all_fields}

    field_ids: dict[str, str] = {}

    for defn in CUSTOM_FIELDS:
        name = defn["name"]
        if name in existing_by_name:
            fid = existing_by_name[name]
            field_ids[name] = fid
            print(f"  ✓ Already exists: {name}  ({fid})")
            continue

        payload = {
            "name":        name,
            "description": defn["description"],
            "type":        defn["type"],
            "searcherKey": defn["searchKey"],
        }
        result = _post("/rest/api/3/field", payload)
        if result:
            fid = result["id"]
            field_ids[name] = fid
            print(f"  ✓ Created: {name}  ({fid})")
        else:
            print(f"  ✗ Failed:  {name}")

    return field_ids


# ─── STEP 2: ADD SELECT OPTIONS (idempotent) ──────────────────────────────────
def ensure_select_options(field_ids: dict[str, str]) -> None:
    print("\n── Step 2: Ensuring select-field options ────────────────────────────")
    for field_name, options in SELECT_OPTIONS.items():
        fid = field_ids.get(field_name)
        if not fid:
            print(f"  ⚠  Field not found: {field_name}")
            continue

        contexts = _get(f"/rest/api/3/field/{fid}/context")
        if not contexts.get("values"):
            print(f"  ⚠  No context found for: {field_name}")
            continue

        ctx_id = contexts["values"][0]["id"]

        # Check which options already exist
        existing_opts_resp = _get(
            f"/rest/api/3/field/{fid}/context/{ctx_id}/option",
            params={"maxResults": 50}
        )
        existing_vals = {o["value"] for o in existing_opts_resp.get("values", [])}
        new_opts      = [v for v in options if v not in existing_vals]

        if not new_opts:
            print(f"  ✓ Options already set for {field_name}: {', '.join(options)}")
            continue

        payload = {"options": [{"value": v, "disabled": False} for v in new_opts]}
        r = _post(f"/rest/api/3/field/{fid}/context/{ctx_id}/option", payload)
        if r is not None:
            print(f"  ✓ Added options for {field_name}: {', '.join(new_opts)}")


# ─── STEP 3: LOOK UP ISSUE TYPE ID ────────────────────────────────────────────
def get_story_issue_type_id() -> str | None:
    """Return the issue type ID for 'Story' in the configured project."""
    try:
        data = _get(f"/rest/api/3/project/{CONFIG['project_key']}")
        for it in data.get("issueTypes", []):
            if it["name"].lower() == "story":
                return it["id"]
    except Exception:
        pass
    return None


# ─── STEP 4: BUILD FORM PAYLOAD ────────────────────────────────────────────────
def _build_form_payload(field_ids: dict[str, str], issue_type_id: str | None) -> dict:
    """
    Compose the request body for POST /rest/api/3/project/{key}/form.

    The Jira Forms API accepts a 'layout' array that lists fields in order.
    Each item references a field by its Jira field ID plus UI metadata.
    """
    layout = []

    # Standard built-in fields that every form should include first
    standard_fields = [
        {
            "type":     "field",
            "fieldId":  "summary",
            "required": True,
            "label":    "Summary",
            "description": "Short title for the API story.",
        },
        {
            "type":     "field",
            "fieldId":  "issuetype",
            "required": True,
            "label":    "Issue Type",
        },
        {
            "type":     "field",
            "fieldId":  "assignee",
            "required": False,
            "label":    "Assignee",
        },
        {
            "type":     "field",
            "fieldId":  "labels",
            "required": False,
            "label":    "Labels",
            "description": "Add 'api-spec-required' to trigger the spec workflow.",
        },
        {
            "type":     "field",
            "fieldId":  "description",
            "required": False,
            "label":    "Description",
            "description": "Background context. The custom fields below capture the formal spec.",
        },
    ]
    layout.extend(standard_fields)

    # Section header — custom fields
    layout.append({
        "type":  "section",
        "label": "API Specification",
        "description": (
            "Fill in every required field before the story moves to In Progress. "
            "These values drive automatic OpenAPI spec generation."
        ),
    })

    # One layout entry per custom field
    for defn in CUSTOM_FIELDS:
        name = defn["name"]
        fid  = field_ids.get(name)
        if not fid:
            continue
        layout.append({
            "type":        "field",
            "fieldId":     fid,
            "required":    defn["required"],
            "label":       name,
            "description": defn["hint"],
        })

    payload: dict = {
        "name":        FORM_NAME,
        "description": FORM_DESCRIPTION,
        "layout":      layout,
    }
    if issue_type_id:
        payload["issueTypeId"] = issue_type_id

    return payload


# ─── STEP 5: CREATE / UPDATE THE FORM ─────────────────────────────────────────
def create_or_update_form(field_ids: dict[str, str]) -> dict | None:
    print("\n── Step 3: Creating the Issue Form ──────────────────────────────────")

    issue_type_id = get_story_issue_type_id()
    if issue_type_id:
        print(f"  ✓ Story issue type ID: {issue_type_id}")
    else:
        print("  ⚠  Could not determine Story issue type ID — form will not be scoped to Stories")

    form_path = f"/rest/api/3/project/{CONFIG['project_key']}/form"

    # Check for an existing form with the same name
    try:
        existing_forms = _get(form_path)
        forms_list = existing_forms if isinstance(existing_forms, list) else existing_forms.get("values", [])
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code in (403, 404):
            _print_forms_unavailable()
            return None
        raise

    duplicate = next((f for f in forms_list if f.get("name") == FORM_NAME), None)

    payload = _build_form_payload(field_ids, issue_type_id)

    if duplicate:
        form_id = duplicate["id"]
        answer  = input(
            f"\n  A form named '{FORM_NAME}' already exists (id: {form_id}).\n"
            "  Update it with current field configuration? (y/N): "
        ).strip().lower()
        if answer == "y":
            r = _put(f"{form_path}/{form_id}", payload)
            if r.status_code in (200, 201, 204):
                print(f"  ✓ Form updated: {form_id}")
                return {"id": form_id, **payload}
            return None
        else:
            print("  → Skipped. Existing form left unchanged.")
            return duplicate

    # Create new form
    result = _post(form_path, payload)
    if result:
        form_id = result.get("id", "?")
        print(f"  ✓ Form created: {FORM_NAME}  (id: {form_id})")
        return result

    return None


def _print_forms_unavailable() -> None:
    print(
        "\n  ⛔  The Jira Forms API returned 403 or 404.\n"
        "  This usually means:\n"
        "    a) Your Jira Cloud plan does not include Issue Forms (Free tier), OR\n"
        "    b) Issue Forms are disabled for this project.\n"
        "\n"
        "  Manual workaround — add these fields to the Create screen instead:\n"
        "    1. Project Settings → Screens → find the 'Default Screen'\n"
        "    2. Click 'Configure' and add each custom field created in Step 1.\n"
        "\n"
        "  Or enable Forms:\n"
        "    Project Settings → Features → toggle 'Forms' ON (Premium/Enterprise plans).\n"
    )


# ─── STEP 6: SAVE FIELD IDS TO jira_field_config.json ────────────────────────
def update_field_config(field_ids: dict[str, str]) -> None:
    config_path = Path(__file__).parent / "jira_field_config.json"
    if not config_path.exists():
        return

    with open(config_path) as f:
        cfg = json.load(f)

    mapping = {
        "API Purpose":           "apiPurpose",
        "API HTTP Method":       "apiHttpMethod",
        "API Request Fields":    "apiRequestFields",
        "API Validation Rules":  "apiValidationRules",
        "API Consumers":         "apiConsumers",
        "API Error Scenarios":   "apiErrorScenarios",
        "API Existing Contract": "apiExistingContract",
        "API Change Type":       "apiChangeType",
    }
    for field_name, cfg_key in mapping.items():
        if field_name in field_ids:
            cfg.setdefault("customFields", {})[cfg_key] = field_ids[field_name]

    cfg["jira"]["baseUrl"]    = CONFIG["base_url"]
    cfg["jira"]["projectKey"] = CONFIG["project_key"]

    with open(config_path, "w") as f:
        json.dump(cfg, f, indent=2)

    print(f"\n  ✓ Updated: {config_path}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 65)
    print(" Jira Issue Form Setup — API-First Specification")
    print(f" Project: {CONFIG['project_key']}  |  {BASE}")
    print("=" * 65)

    # Validate config
    if "your-domain" in BASE or "YOUR_API_TOKEN" in CONFIG["token"]:
        print(
            "\n⛔  CONFIG not set.\n"
            "   Edit the CONFIG block at the top of this script, or export:\n"
            "     export JIRA_BASE_URL=https://acme.atlassian.net\n"
            "     export JIRA_EMAIL=admin@acme.com\n"
            "     export JIRA_API_TOKEN=<your-token>\n"
            "     export JIRA_PROJECT=PROJ\n"
        )
        sys.exit(1)

    # Test connection
    try:
        me = _get("/rest/api/3/myself")
        print(f"\n✓ Connected as: {me.get('displayName', me.get('emailAddress', '?'))}")
    except requests.HTTPError as e:
        print(f"\n⛔  Connection failed: {e}")
        sys.exit(1)

    # Run pipeline
    field_ids = ensure_custom_fields()
    if not field_ids:
        print("\n⛔  No custom fields available — aborting.")
        sys.exit(1)

    ensure_select_options(field_ids)
    form = create_or_update_form(field_ids)
    update_field_config(field_ids)

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print(" Summary")
    print("=" * 65)
    print("\n Custom field IDs:")
    for name, fid in field_ids.items():
        req = next((d["required"] for d in CUSTOM_FIELDS if d["name"] == name), False)
        flag = " [required]" if req else ""
        print(f"   {fid:30s}  {name}{flag}")

    if form:
        form_id = form.get("id", "?")
        print(f"\n Form ID   : {form_id}")
        print(f" Form URL  : {BASE}/jira/software/projects/{CONFIG['project_key']}/form/{form_id}")

    print("\n Next steps:")
    print("   1. Open the Form URL above and review the field order/labels")
    print("   2. Share the form link with stakeholders for direct issue creation")
    print("   3. Update mcp-server/config/jira.json with the field IDs above")
    print("   4. Import jira_automation_rule.json to enforce spec completeness")
    print("=" * 65)


if __name__ == "__main__":
    main()
