#!/usr/bin/env python3
"""
jira_story_template_create.py
==============================
Creates a Jira Story pre-populated with all 8 API-First custom fields.

Because the Jira Forms API requires a Premium/Enterprise plan, this script
is the Free-tier alternative: it creates a fully-structured Story issue that
acts as a fill-in template — all custom fields are present and contain
guidance text that the assignee replaces with real values.

Two modes:
  --template   (default) Create one blank template issue with guidance text.
               Copy-paste this issue in Jira to start each new API story.
  --interactive  Prompt for real values on the command line and create a
               ready-to-use API story immediately.

Usage:
  python jira_story_template_create.py               # template mode
  python jira_story_template_create.py --interactive # fill-in mode
  python jira_story_template_create.py --help

Configuration (env vars or the CONFIG block below):
  JIRA_BASE_URL   e.g. https://acme.atlassian.net
  JIRA_EMAIL      admin email
  JIRA_API_TOKEN  Personal Access Token
  JIRA_PROJECT    project key  e.g. SCRUM

Field IDs are read automatically from jira_field_config.json (same directory).
If that file is missing or has placeholder values, the script falls back to
the live Jira field list.
"""

import os, sys, json, textwrap, requests
from pathlib import Path
from requests.auth import HTTPBasicAuth

# ─── CONFIG ───────────────────────────────────────────────────────────────────
CONFIG = {
    "base_url":    os.environ.get("JIRA_BASE_URL",    "https://your-domain.atlassian.net"),
    "email":       os.environ.get("JIRA_EMAIL",       "admin@yourcompany.com"),
    "token":       os.environ.get("JIRA_API_TOKEN",   "YOUR_API_TOKEN_HERE"),
    "project_key": os.environ.get("JIRA_PROJECT",     "PROJ"),
}

# Canonical names — must match what jira_template_setup.py / jira_form_setup.py created
FIELD_NAMES = [
    "API Purpose",
    "API HTTP Method",
    "API Request Fields",
    "API Validation Rules",
    "API Consumers",
    "API Error Scenarios",
    "API Existing Contract",
    "API Change Type",
]

# Guidance text shown in template mode (replaced by real values in interactive mode)
TEMPLATE_HINTS = {
    "API Purpose": (
        "[FILL IN] What does this API do?\n"
        "Who calls it and why?\n"
        "Example: Creates a payment intent and returns a token for client-side confirmation."
    ),
    "API HTTP Method": None,           # select field — handled separately
    "API Request Fields": (
        "[FILL IN] One field per line:\n"
        "  name | type | required/optional | validation rule\n\n"
        "Example:\n"
        "  amount       | integer | required | min 1, max 99999999\n"
        "  currency     | string  | required | ISO 4217 (GBP, EUR, USD)\n"
        "  merchant_ref | string  | required | max 50 chars, alphanumeric\n"
        "  customer_id  | string  | optional | UUID v4"
    ),
    "API Validation Rules": (
        "[FILL IN] List every business rule and constraint:\n\n"
        "Example:\n"
        "  - Amount must be a positive integer (pence).\n"
        "  - Currency must be a valid ISO 4217 code.\n"
        "  - Duplicate merchant_ref within 24 h → 409 Conflict."
    ),
    "API Consumers": (
        "[FILL IN] Which teams or services will call this API?\n\n"
        "Example:\n"
        "  - Checkout Team (Frontend React)\n"
        "  - Mobile Team (iOS / Android)\n"
        "  - Reporting Service (async, via event queue)"
    ),
    "API Error Scenarios": (
        "[FILL IN] HTTP status → reason:\n\n"
        "Example:\n"
        "  400 — invalid amount or currency\n"
        "  404 — resource not found\n"
        "  409 — duplicate merchant_ref\n"
        "  422 — customer_id does not exist\n"
        "  503 — downstream payment provider unavailable"
    ),
    "API Existing Contract": (
        "[FILL IN or leave blank for NEW APIs]\n"
        "Paste the Confluence / GitHub URL of the current OpenAPI spec."
    ),
    "API Change Type": None,           # select field — handled separately
}

SELECT_DEFAULT = {
    "API HTTP Method": "POST",
    "API Change Type": "Additive",
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

def _post(path, body):
    r = S.post(f"{BASE}{path}", json=body)
    if r.status_code not in (200, 201):
        print(f"  ⚠  POST {path} → {r.status_code}: {r.text[:300]}")
        return None
    return r.json()


def _post_with_retry(path, body: dict) -> tuple[dict | None, list[str]]:
    """
    POST an issue, automatically dropping any custom fields that the project's
    screen scheme rejects ("not on appropriate screen").  Returns the result
    and a list of field IDs that were skipped.
    """
    skipped: list[str] = []
    fields = dict(body.get("fields", {}))

    for attempt in range(10):          # at most 10 retry passes
        r = S.post(f"{BASE}{path}", json={"fields": fields})
        if r.status_code in (200, 201):
            return r.json(), skipped

        try:
            err = r.json()
        except Exception:
            print(f"  ⚠  POST {path} → {r.status_code}: {r.text[:300]}")
            return None, skipped

        # Extract field IDs that are not on the screen
        field_errors = err.get("errors", {})
        screen_blocked = [
            fid for fid, msg in field_errors.items()
            if "not on the appropriate screen" in msg or "cannot be set" in msg
        ]
        if not screen_blocked:
            print(f"  ⚠  POST {path} → {r.status_code}: {r.text[:300]}")
            return None, skipped

        for fid in screen_blocked:
            print(f"  ⚠  {fid} not on project screen — will be added as a comment instead")
            skipped.append(fid)
            fields.pop(fid, None)

    return None, skipped

# ─── FIELD ID RESOLUTION ──────────────────────────────────────────────────────
def load_field_ids() -> dict[str, str]:
    """
    1. Try jira_field_config.json (written by jira_form_setup.py).
    2. Fall back to live Jira field list.
    Returns {field_name: field_id}.
    """
    config_path = Path(__file__).parent / "jira_field_config.json"
    config_map = {
        "API Purpose":           "apiPurpose",
        "API HTTP Method":       "apiHttpMethod",
        "API Request Fields":    "apiRequestFields",
        "API Validation Rules":  "apiValidationRules",
        "API Consumers":         "apiConsumers",
        "API Error Scenarios":   "apiErrorScenarios",
        "API Existing Contract": "apiExistingContract",
        "API Change Type":       "apiChangeType",
    }

    if config_path.exists():
        with open(config_path) as f:
            cfg = json.load(f)
        custom = cfg.get("customFields", {})
        ids = {}
        for field_name, cfg_key in config_map.items():
            fid = custom.get(cfg_key, "")
            if fid and "XXXXX" not in fid:
                ids[field_name] = fid
        if len(ids) == len(FIELD_NAMES):
            print(f"  ✓ Field IDs loaded from {config_path.name}")
            return ids
        print(f"  ⚠  {config_path.name} has placeholder IDs — falling back to live lookup")

    # Live lookup
    print("  → Looking up custom field IDs from Jira…")
    all_fields = _get("/rest/api/3/field")
    ids = {}
    for f in all_fields:
        if f["name"] in FIELD_NAMES:
            ids[f["name"]] = f["id"]
    missing = [n for n in FIELD_NAMES if n not in ids]
    if missing:
        print(f"  ⚠  Fields not found in Jira: {', '.join(missing)}")
        print("     Run jira_template_setup.py or jira_form_setup.py first.")
    return ids


def get_select_option_id(field_id: str, value: str) -> dict | None:
    """Return the Jira option object {id, value} for a select field value."""
    try:
        contexts = _get(f"/rest/api/3/field/{field_id}/context")
        if not contexts.get("values"):
            return None
        ctx_id = contexts["values"][0]["id"]
        opts = _get(
            f"/rest/api/3/field/{field_id}/context/{ctx_id}/option",
            params={"maxResults": 50}
        )
        for opt in opts.get("values", []):
            if opt["value"] == value:
                return {"id": opt["id"]}
    except Exception:
        pass
    return None


# ─── DESCRIPTION BUILDER ──────────────────────────────────────────────────────
def _adf_paragraph(*text_parts: str) -> dict:
    return {
        "type": "paragraph",
        "content": [{"type": "text", "text": t} for t in text_parts],
    }

def _adf_heading(text: str, level: int = 3) -> dict:
    return {
        "type": "heading",
        "attrs": {"level": level},
        "content": [{"type": "text", "text": text}],
    }

def _adf_bullet(items: list[str]) -> dict:
    return {
        "type": "bulletList",
        "content": [
            {
                "type": "listItem",
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": i}]}],
            }
            for i in items
        ],
    }

def build_description(summary: str, values: dict[str, str]) -> dict:
    """Build ADF description body that embeds the filled-in template values."""
    content = [
        _adf_paragraph(
            "As a developer / product owner, complete the API specification fields on this "
            "issue before the story moves to In Progress. Each custom field drives automatic "
            "OpenAPI spec generation."
        ),
        _adf_heading("API Specification Checklist", level=2),
        _adf_bullet([
            "API Purpose — filled in",
            "API HTTP Method — selected",
            "API Request Fields — filled in",
            "API Validation Rules — filled in",
            "API Consumers — filled in",
            "API Error Scenarios — filled in",
            "API Existing Contract — filled in (or left blank for new APIs)",
            "API Change Type — selected (update stories only)",
        ]),
        _adf_heading("Next steps", level=2),
        _adf_paragraph(
            "1. Review all custom fields on this issue.\n"
            "2. Add label 'api-spec-required' to trigger the spec workflow.\n"
            "3. Transition to Ready for Dev — the automation rule will post a completion comment.\n"
            "4. Once all fields are approved, transition to In Progress."
        ),
    ]
    return {"version": 1, "type": "doc", "content": content}


def _text_to_adf(text: str) -> dict:
    """Convert a plain multi-line string to an ADF doc (one paragraph per line)."""
    paragraphs = []
    for line in text.splitlines():
        paragraphs.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": line or " "}],
        })
    if not paragraphs:
        paragraphs = [{"type": "paragraph", "content": [{"type": "text", "text": " "}]}]
    return {"version": 1, "type": "doc", "content": paragraphs}


# ─── ISSUE BUILDER ────────────────────────────────────────────────────────────
def build_issue_fields(
    summary: str,
    field_ids: dict[str, str],
    values: dict[str, str],
) -> dict:
    fields: dict = {
        "project":   {"key": CONFIG["project_key"]},
        "issuetype": {"name": "Story"},
        "summary":   summary,
        "description": build_description(summary, values),
        "labels": ["api-spec-required"],
    }

    for name, fid in field_ids.items():
        value = values.get(name)
        if not value:
            continue

        # Select fields need an option object
        if name in ("API HTTP Method", "API Change Type"):
            opt = get_select_option_id(fid, value)
            if opt:
                fields[fid] = opt
            else:
                print(f"  ⚠  Option '{value}' not found for {name} — skipping")
        # Textarea fields: try ADF first; plain string is a fallback
        elif name not in ("API Existing Contract",):
            fields[fid] = _text_to_adf(value)
        else:
            fields[fid] = value

    return {"fields": fields}


# ─── INTERACTIVE PROMPTS ───────────────────────────────────────────────────────
def _prompt(label: str, hint: str, default: str = "") -> str:
    print(f"\n  {label}")
    if hint:
        for line in hint.splitlines():
            print(f"    {line}")
    if default:
        print(f"    [Enter to use default: {default!r}]")
    val = input("  → ").strip()
    return val or default

def _prompt_select(label: str, options: list[str], default: str) -> str:
    print(f"\n  {label}")
    for i, opt in enumerate(options, 1):
        marker = " (default)" if opt == default else ""
        print(f"    {i}. {opt}{marker}")
    choice = input(f"  → [1-{len(options)}, Enter for default]: ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(options):
        return options[int(choice) - 1]
    return default

def gather_interactive_values() -> tuple[str, dict[str, str]]:
    print("\n  Fill in the API specification fields.\n  Press Enter to accept the default.\n")

    summary = _prompt(
        "Story summary (required):",
        hint="e.g.  POST /payments/initiate — Create payment intent",
    )
    if not summary:
        print("  ⛔  Summary is required.")
        sys.exit(1)

    values: dict[str, str] = {}

    values["API Purpose"] = _prompt(
        "API Purpose (required):",
        hint="What does this API do? Who calls it and why?",
    )
    values["API HTTP Method"] = _prompt_select(
        "API HTTP Method (required):",
        options=["GET", "POST", "PUT", "PATCH", "DELETE"],
        default="POST",
    )
    values["API Request Fields"] = _prompt(
        "API Request Fields (required):",
        hint="name | type | required/optional | validation rule  (one per line)",
    )
    values["API Validation Rules"] = _prompt(
        "API Validation Rules (required):",
        hint="Business rules and constraints the API must enforce.",
    )
    values["API Consumers"] = _prompt(
        "API Consumers (required):",
        hint="Which teams or services will call this API?",
    )
    values["API Error Scenarios"] = _prompt(
        "API Error Scenarios (required):",
        hint="HTTP status — reason  (e.g. 400 — invalid input)",
    )
    values["API Existing Contract"] = _prompt(
        "API Existing Contract (optional — leave blank for new APIs):",
        hint="Confluence or GitHub URL of the current OpenAPI spec.",
        default="",
    )
    values["API Change Type"] = _prompt_select(
        "API Change Type (optional — for updates only):",
        options=["Additive", "Breaking"],
        default="Additive",
    )

    return summary, values


def gather_template_values() -> tuple[str, dict[str, str]]:
    """Return placeholder guidance text for all fields."""
    summary = "[API-FIRST TEMPLATE] Replace this summary — e.g. POST /resource — Short description"
    values = {
        name: (TEMPLATE_HINTS[name] if TEMPLATE_HINTS[name] else SELECT_DEFAULT.get(name, ""))
        for name in FIELD_NAMES
    }
    return summary, values


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main() -> None:
    interactive = "--interactive" in sys.argv
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)

    print("=" * 65)
    mode_label = "Interactive" if interactive else "Template"
    print(f" Jira Story Template Creator — {mode_label} Mode")
    print(f" Project: {CONFIG['project_key']}  |  {BASE}")
    print("=" * 65)

    # Validate config
    if "your-domain" in BASE or "YOUR_API_TOKEN" in CONFIG["token"]:
        print(
            "\n⛔  CONFIG not set. Export the required env vars:\n"
            "     export JIRA_BASE_URL=https://acme.atlassian.net\n"
            "     export JIRA_EMAIL=admin@acme.com\n"
            "     export JIRA_API_TOKEN=<token>\n"
            "     export JIRA_PROJECT=SCRUM\n"
        )
        sys.exit(1)

    # Test connection
    try:
        me = _get("/rest/api/3/myself")
        print(f"\n✓ Connected as: {me.get('displayName', me.get('emailAddress', '?'))}")
    except requests.HTTPError as e:
        print(f"\n⛔  Connection failed: {e}")
        sys.exit(1)

    # Resolve field IDs
    print("\n── Resolving custom field IDs ───────────────────────────────────────")
    field_ids = load_field_ids()
    if not field_ids:
        print("⛔  No custom field IDs found — run jira_form_setup.py first.")
        sys.exit(1)

    for name in FIELD_NAMES:
        status = f"({field_ids[name]})" if name in field_ids else "(NOT FOUND — will be skipped)"
        print(f"  {'✓' if name in field_ids else '✗'}  {name:30s} {status}")

    # Gather values
    if interactive:
        summary, values = gather_interactive_values()
    else:
        summary, values = gather_template_values()
        print(
            "\n  ℹ  Template mode: creating a guide issue with placeholder text.\n"
            "     Clone this issue in Jira for each new API story, then fill in the fields.\n"
            "     Use --interactive to create a ready-to-use story right now.\n"
        )

    # Confirm before creating
    print(f"\n── Creating story ───────────────────────────────────────────────────")
    print(f"  Summary : {summary}")
    print(f"  Project : {CONFIG['project_key']}")
    print(f"  Fields  : {len(field_ids)} custom fields will be populated")

    answer = input("\n  Proceed? (Y/n): ").strip().lower()
    if answer == "n":
        print("  Cancelled.")
        sys.exit(0)

    issue_body = build_issue_fields(summary, field_ids, values)
    result, skipped_ids = _post_with_retry("/rest/api/3/issue", issue_body)

    if not result:
        print("\n⛔  Failed to create issue.")
        sys.exit(1)

    # Post skipped fields as a comment so the data is not lost
    if skipped_ids:
        id_to_name = {v: k for k, v in field_ids.items()}
        comment_lines = ["*Fields not supported on this project's screen — set these manually:*\n"]
        for fid in skipped_ids:
            name  = id_to_name.get(fid, fid)
            value = values.get(name, "(see template guidance)")
            comment_lines.append(f"*{name}*: {value}\n")
        comment_body = {
            "body": {
                "version": 1,
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": line}],
                    }
                    for line in comment_lines
                ],
            }
        }
        issue_key_tmp = result.get("key", "")
        _post(f"/rest/api/3/issue/{issue_key_tmp}/comment", comment_body)
        print(f"  ✓ Skipped field values posted as a comment on {issue_key_tmp}")

    issue_key = result.get("key", "?")
    issue_url = f"{BASE}/browse/{issue_key}"

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print(f" ✓ Story created: {issue_key}")
    print(f" URL : {issue_url}")
    print("=" * 65)

    if not interactive:
        print(
            "\n How to use this template:\n"
            f"  1. Open {issue_url}\n"
            "  2. Click ··· → Clone  for each new API story\n"
            "  3. Replace every [FILL IN] placeholder with real values\n"
            "  4. Transition to 'Ready for Dev' to trigger the spec workflow\n"
        )
    else:
        print(
            "\n Next steps:\n"
            f"  1. Open {issue_url} and review the custom fields\n"
            "  2. Transition to 'Ready for Dev' to trigger the spec workflow\n"
            "  3. The automation rule will post a completion checklist comment\n"
        )

    print("=" * 65)


if __name__ == "__main__":
    main()
