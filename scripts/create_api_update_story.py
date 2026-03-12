#!/usr/bin/env python3
"""
create_api_update_story.py
==========================
PO-friendly script to create a Jira Story for an API update (new endpoint or
modification to an existing one).

The PO fills in a minimal YAML requirements file (see requirements_example.yaml)
and runs this script.  All 8 API-First custom fields are populated automatically.

Usage:
  python create_api_update_story.py                               # prompts for a YAML file
  python create_api_update_story.py --from-file requirements.yaml # pass file directly
  python create_api_update_story.py --dry-run                     # preview without creating

Environment variables (required unless editing CONFIG below):
  JIRA_BASE_URL   e.g. https://acme.atlassian.net
  JIRA_EMAIL      your Jira login email
  JIRA_API_TOKEN  Personal Access Token
  JIRA_PROJECT    project key (default: SCRUM)
"""

import os, sys, json, argparse, textwrap
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("Missing dependency: pip install pyyaml requests")

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    sys.exit("Missing dependency: pip install pyyaml requests")

# ─── CONFIG ───────────────────────────────────────────────────────────────────
CONFIG = {
    "base_url":    os.environ.get("JIRA_BASE_URL",    "https://your-domain.atlassian.net"),
    "email":       os.environ.get("JIRA_EMAIL",       "admin@yourcompany.com"),
    "token":       os.environ.get("JIRA_API_TOKEN",   "YOUR_API_TOKEN_HERE"),
    "project_key": os.environ.get("JIRA_PROJECT",     "SCRUM"),
}

# Field IDs (read from jira_field_config.json automatically)
FIELD_IDS: dict[str, str] = {}

# ─── HTTP HELPERS ─────────────────────────────────────────────────────────────
def _session():
    s = requests.Session()
    s.auth = HTTPBasicAuth(CONFIG["email"], CONFIG["token"])
    s.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
    return s

S:   requests.Session = None   # initialised in main()
BASE = ""


def _get(path: str, **kw) -> dict:
    r = S.get(f"{BASE}{path}", **kw)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict | None:
    r = S.post(f"{BASE}{path}", json=body)
    if r.status_code not in (200, 201):
        print(f"  ⚠  POST {path} → {r.status_code}: {r.text[:400]}")
        return None
    return r.json()


def _post_with_screen_retry(path: str, body: dict) -> tuple[dict | None, list[str]]:
    """POST an issue, dropping fields not on the project screen. Returns (result, skipped_ids)."""
    skipped: list[str] = []
    fields = dict(body.get("fields", {}))

    for _ in range(10):
        r = S.post(f"{BASE}{path}", json={"fields": fields})
        if r.status_code in (200, 201):
            return r.json(), skipped
        try:
            err = r.json()
        except Exception:
            print(f"  ⚠  {r.status_code}: {r.text[:400]}")
            return None, skipped

        blocked = [
            fid for fid, msg in err.get("errors", {}).items()
            if "not on the appropriate screen" in msg or "cannot be set" in msg
        ]
        if not blocked:
            print(f"  ⚠  {r.status_code}: {r.text[:400]}")
            return None, skipped
        for fid in blocked:
            print(f"  ⚠  {fid} blocked by screen — will post as comment")
            skipped.append(fid)
            fields.pop(fid, None)

    return None, skipped


# ─── FIELD ID RESOLUTION ──────────────────────────────────────────────────────
_CFG_KEY_MAP = {
    "API Purpose":           "apiPurpose",
    "API HTTP Method":       "apiHttpMethod",
    "API Request Fields":    "apiRequestFields",
    "API Validation Rules":  "apiValidationRules",
    "API Consumers":         "apiConsumers",
    "API Error Scenarios":   "apiErrorScenarios",
    "API Existing Contract": "apiExistingContract",
    "API Change Type":       "apiChangeType",
}

def load_field_ids() -> dict[str, str]:
    config_path = Path(__file__).parent / "jira_field_config.json"
    if config_path.exists():
        with open(config_path) as f:
            cfg = json.load(f)
        custom = cfg.get("customFields", {})
        ids = {
            name: custom[key]
            for name, key in _CFG_KEY_MAP.items()
            if custom.get(key) and "XXXXX" not in custom.get(key, "")
        }
        if len(ids) == len(_CFG_KEY_MAP):
            return ids
        print(f"  ⚠  {config_path.name} has placeholder IDs — querying Jira live …")

    all_fields = _get("/rest/api/3/field")
    return {f["name"]: f["id"] for f in all_fields if f["name"] in _CFG_KEY_MAP}


def _select_option(field_id: str, value: str) -> dict | None:
    try:
        ctx_resp = _get(f"/rest/api/3/field/{field_id}/context")
        ctxs = ctx_resp.get("values", [])
        if not ctxs:
            return None
        opts = _get(
            f"/rest/api/3/field/{field_id}/context/{ctxs[0]['id']}/option",
            params={"maxResults": 50},
        )
        for opt in opts.get("values", []):
            if opt["value"] == value:
                return {"id": opt["id"]}
    except Exception:
        pass
    return None


# ─── ADF HELPERS ──────────────────────────────────────────────────────────────
def _para(*texts: str) -> dict:
    return {"type": "paragraph",
            "content": [{"type": "text", "text": t} for t in texts]}

def _heading(text: str, level: int = 2) -> dict:
    return {"type": "heading", "attrs": {"level": level},
            "content": [{"type": "text", "text": text}]}

def _bullet(items: list[str]) -> dict:
    return {
        "type": "bulletList",
        "content": [
            {"type": "listItem",
             "content": [_para(item)]}
            for item in items
        ],
    }

def _task_list(items: list[str]) -> dict:
    """ADF task list (checkboxes) for acceptance criteria."""
    return {
        "type": "taskList",
        "attrs": {"localId": "ac-list"},
        "content": [
            {
                "type": "taskItem",
                "attrs": {"localId": f"ac-{i}", "state": "TODO"},
                "content": [{"type": "text", "text": item}],
            }
            for i, item in enumerate(items, 1)
        ],
    }

def _code_block(text: str, language: str = "text") -> dict:
    return {
        "type": "codeBlock",
        "attrs": {"language": language},
        "content": [{"type": "text", "text": text}],
    }

def _text_to_adf(text: str) -> dict:
    """Plain multi-line string → ADF doc (one paragraph per line)."""
    paras = [_para(line or " ") for line in text.splitlines()]
    return {"version": 1, "type": "doc", "content": paras or [_para(" ")]}


# ─── REQUIREMENTS → JIRA FIELDS ───────────────────────────────────────────────
def translate(req: dict) -> tuple[str, dict[str, str], dict]:
    """
    Map the PO requirements YAML to:
      summary   — Jira issue summary
      values    — {field_name: plain_text_value}  (for custom fields)
      ac_items  — list[str] acceptance criteria lines (for description checklist)
    """
    endpoint  = req.get("endpoint", {})
    method    = str(endpoint.get("method", "PATCH")).upper()
    path      = endpoint.get("path", "/api/resource/{id}")
    summary   = req.get("title") or f"{method} {path} — API update"

    # ── API Purpose ─────────────────────────────────────────────────────────
    purpose_lines = [endpoint.get("description", "").strip()]
    keeping = req.get("keeps_endpoints", [])
    if keeping:
        purpose_lines.append(
            "Existing endpoints kept (no breaking change): "
            + ", ".join(keeping)
        )
    api_purpose = "\n".join(l for l in purpose_lines if l)

    # ── API Request Fields ───────────────────────────────────────────────────
    rf_lines = ["name | type | required | validation"]
    for field in req.get("request_fields", []):
        req_flag = "required" if field.get("required") else "optional"
        rf_lines.append(
            f"{field['name']} | {field.get('type','string')} | {req_flag} | {field.get('validation','')}"
        )
    api_request_fields = "\n".join(rf_lines)

    # ── API Validation Rules ─────────────────────────────────────────────────
    rules = req.get("business_rules", [])
    api_validation_rules = "\n".join(f"- {r}" for r in rules) if rules else ""

    # ── API Consumers ────────────────────────────────────────────────────────
    consumers = req.get("consumers", [])
    api_consumers = "\n".join(f"- {c}" for c in consumers) if consumers else ""

    # ── API Error Scenarios ──────────────────────────────────────────────────
    errors = req.get("error_scenarios", [])
    if errors:
        api_error_scenarios = "\n".join(f"- {e}" for e in errors)
    else:
        # Derive standard errors for the method
        api_error_scenarios = _default_errors(method)

    values = {
        "API Purpose":           api_purpose,
        "API HTTP Method":       method,
        "API Request Fields":    api_request_fields,
        "API Validation Rules":  api_validation_rules,
        "API Consumers":         api_consumers,
        "API Error Scenarios":   api_error_scenarios,
        "API Existing Contract": req.get("existing_spec_url", ""),
        "API Change Type":       req.get("change_type", "Additive"),
    }

    ac_items = req.get("acceptance_criteria", [])
    return summary, values, ac_items


def _default_errors(method: str) -> str:
    lines = [
        "200 — successful response" if method in ("GET", "PATCH") else "201 — created",
        "400 — validation error / bad request",
        "401 — unauthorized",
    ]
    if method in ("GET", "PATCH", "PUT", "DELETE"):
        lines.append("404 — resource not found")
    if method in ("POST", "PATCH", "PUT"):
        lines.append("409 — conflict (e.g. duplicate unique field)")
    lines.append("500 — internal server error")
    return "\n".join(f"- {l}" for l in lines)


# ─── DESCRIPTION BUILDER ──────────────────────────────────────────────────────
def build_description(summary: str, ac_items: list[str], req: dict) -> dict:
    endpoint = req.get("endpoint", {})
    method   = str(endpoint.get("method", "PATCH")).upper()
    path     = endpoint.get("path", "")

    content = [
        _heading("Context", level=2),
        _para(endpoint.get("description", summary)),
    ]

    # Required changes block
    changes = req.get("required_changes", [])
    if changes:
        content += [_heading("Required changes", level=2), _bullet(changes)]

    # Request body example if provided
    body_example = req.get("request_body_example")
    if body_example:
        content += [
            _heading("Request body example", level=2),
            _code_block(body_example, "json"),
        ]

    # Acceptance criteria as a task list
    if ac_items:
        content += [
            _heading("Acceptance criteria", level=2),
            _task_list(ac_items),
        ]

    # OpenAPI spec reminder
    content += [
        _heading("API-First checklist", level=2),
        _bullet([
            "All custom fields on this issue are filled in",
            "Add label 'api-spec-required' to trigger spec workflow",
            "Transition to Ready for Dev to start automation",
            f"Auto-generated spec must list {method} {path} with correct schema",
            "Spec uploaded to specs repo and PR reviewed before merge",
        ]),
    ]

    return {"version": 1, "type": "doc", "content": content}


# ─── ISSUE BUILDER ────────────────────────────────────────────────────────────
def build_issue(
    summary: str,
    values: dict[str, str],
    ac_items: list[str],
    req: dict,
    field_ids: dict[str, str],
) -> dict:
    fields: dict = {
        "project":     {"key": CONFIG["project_key"]},
        "issuetype":   {"name": "Story"},
        "summary":     summary,
        "description": build_description(summary, ac_items, req),
        "labels":      ["api-spec-required"],
    }

    for name, fid in field_ids.items():
        value = values.get(name, "")
        if not value:
            continue
        if name in ("API HTTP Method", "API Change Type"):
            opt = _select_option(fid, value)
            if opt:
                fields[fid] = opt
            else:
                print(f"  ⚠  Option '{value}' not found for {name} — field skipped")
        elif name == "API Existing Contract":
            fields[fid] = value        # plain string (URL)
        else:
            fields[fid] = _text_to_adf(value)   # ADF for textarea fields

    return {"fields": fields}


# ─── DRY RUN PREVIEW ──────────────────────────────────────────────────────────
def print_preview(summary: str, values: dict[str, str], ac_items: list[str]) -> None:
    width = 70
    print("\n" + "═" * width)
    print("  DRY RUN PREVIEW — no issue will be created")
    print("═" * width)
    print(f"\n  SUMMARY : {summary}")
    print(f"  PROJECT : {CONFIG['project_key']}\n")
    print("  ── Custom fields ──────────────────────────────────────────")
    for name, value in values.items():
        if not value:
            continue
        label = f"  {name}:"
        indent = " " * 4
        body = textwrap.indent(value, indent)
        print(f"{label}\n{body}")
    if ac_items:
        print("\n  ── Acceptance criteria (description checklist) ────────────")
        for item in ac_items:
            print(f"    ☐ {item}")
    print("\n" + "═" * width + "\n")


# ─── REQUIREMENTS LOADER ──────────────────────────────────────────────────────
def load_requirements(file_path: str) -> dict:
    p = Path(file_path)
    if not p.exists():
        sys.exit(f"⛔  Requirements file not found: {p}")
    with open(p) as f:
        return yaml.safe_load(f)


EXAMPLE_REQUIREMENTS = {
    "title": "PATCH /api/tasks/{id} — Partial update (keep PUT for full-replacement)",
    "endpoint": {
        "method": "PATCH",
        "path": "/api/tasks/{id}",
        "description": (
            "Add a partial-update endpoint for tasks. Only fields present in the "
            "request body are updated. Passing null means 'no change', not 'clear field'. "
            "PUT /api/tasks/{id} is kept for full-replacement with no breaking change."
        ),
    },
    "keeps_endpoints": ["PUT /api/tasks/{id}"],
    "required_changes": [
        "Add PATCH /api/tasks/{id} accepting a partial TaskUpdateRequest",
        "Only fields present in the request body are updated (null = no change, not clear)",
        "Keep PUT /api/tasks/{id} for full-replacement semantics (no breaking change)",
    ],
    "request_fields": [
        {"name": "title",       "type": "string",  "required": False, "validation": "max 255 chars; must be unique — 409 Conflict if duplicate"},
        {"name": "description", "type": "string",  "required": False, "validation": "max 1000 chars"},
        {"name": "status",      "type": "string",  "required": False, "validation": "enum: TODO | IN_PROGRESS | DONE"},
        {"name": "dueDate",     "type": "string",  "required": False, "validation": "ISO 8601 date-time; must be in the future if provided"},
    ],
    "request_body_example": (
        '// Update only status — all other fields unchanged\n'
        '{ "status": "DONE" }\n\n'
        '// Empty body — returns 200 with unchanged task\n'
        '{}'
    ),
    "business_rules": [
        "Only fields present in the request body are updated",
        "null value means 'no change' — it does NOT clear the field",
        "PATCH with an empty body {} returns 200 with the task unchanged",
        "title must remain unique across all tasks (409 Conflict if duplicate)",
        "updatedAt is refreshed on every successful PATCH",
        "Cannot PATCH a task that does not exist (404)",
    ],
    "acceptance_criteria": [
        'PATCH /api/tasks/{id} with { "status": "DONE" } updates only status; other fields unchanged',
        "PATCH with empty body {} returns 200 with unchanged task",
        "PATCH with title that already exists returns 409 Conflict",
        "updatedAt is refreshed on every successful PATCH",
        "Auto-generated OpenAPI spec lists PATCH separately from PUT with correct partial schema",
    ],
    "error_scenarios": [
        "200 — successful partial update, returns updated task",
        "400 — invalid field value (e.g. unknown status)",
        "401 — unauthorized",
        "404 — task not found",
        "409 — title already exists (conflict)",
        "500 — internal server error",
    ],
    "consumers": [
        "Frontend React (Task Management UI)",
        "Mobile clients (iOS / Android)",
    ],
    "existing_spec_url": "",   # paste GitHub/Confluence URL of current OpenAPI spec
    "change_type": "Additive",
}


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main() -> None:
    global S, BASE

    parser = argparse.ArgumentParser(
        description="Create a Jira Story for an API update from a minimal requirements file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--from-file", metavar="YAML",
        help="Path to requirements YAML file (see --generate-example to create one)",
    )
    parser.add_argument(
        "--generate-example", metavar="PATH",
        help="Write an example requirements.yaml to PATH and exit",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview the Jira fields that would be set, without creating the issue",
    )
    args = parser.parse_args()

    # ── Generate example file ────────────────────────────────────────────────
    if args.generate_example:
        out = Path(args.generate_example)
        with open(out, "w") as f:
            yaml.dump(EXAMPLE_REQUIREMENTS, f,
                      default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"✓ Example requirements written to: {out}")
        print(f"  Edit the file, then run:\n  python {Path(__file__).name} --from-file {out}")
        sys.exit(0)

    # ── Load requirements ────────────────────────────────────────────────────
    if args.from_file:
        req = load_requirements(args.from_file)
    else:
        print(
            "\n  No --from-file specified — using built-in PATCH /api/tasks/{id} example.\n"
            f"  To generate a blank template: python {Path(__file__).name} "
            "--generate-example requirements.yaml\n"
        )
        req = EXAMPLE_REQUIREMENTS

    summary, values, ac_items = translate(req)

    # ── Dry run ──────────────────────────────────────────────────────────────
    if args.dry_run:
        print_preview(summary, values, ac_items)
        print("  (dry-run — no issue created)")
        return

    # ── Validate config ──────────────────────────────────────────────────────
    BASE = CONFIG["base_url"].rstrip("/")
    if "your-domain" in BASE or "YOUR_API_TOKEN" in CONFIG["token"]:
        print(
            "\n⛔  JIRA credentials not configured. Set these env vars:\n"
            "    export JIRA_BASE_URL=https://your-team.atlassian.net\n"
            "    export JIRA_EMAIL=you@example.com\n"
            "    export JIRA_API_TOKEN=<token>\n"
            "    export JIRA_PROJECT=SCRUM   # optional, default: SCRUM\n"
        )
        sys.exit(1)

    S = _session()

    # ── Test connection ──────────────────────────────────────────────────────
    try:
        me = _get("/rest/api/3/myself")
        print(f"\n✓ Connected to {BASE} as {me.get('displayName', me.get('emailAddress', '?'))}")
    except requests.HTTPError as e:
        print(f"\n⛔  Connection failed: {e}")
        sys.exit(1)

    # ── Field IDs ────────────────────────────────────────────────────────────
    print("\n── Resolving custom field IDs ───────────────────────────────────────")
    field_ids = load_field_ids()
    for name in _CFG_KEY_MAP:
        status = f"({field_ids[name]})" if name in field_ids else "(NOT FOUND — skipping)"
        print(f"  {'✓' if name in field_ids else '✗'}  {name:30s} {status}")

    # ── Preview ──────────────────────────────────────────────────────────────
    print_preview(summary, values, ac_items)

    answer = input("  Create this Jira story? (Y/n): ").strip().lower()
    if answer == "n":
        print("  Cancelled.")
        sys.exit(0)

    # ── Create issue ─────────────────────────────────────────────────────────
    issue_body   = build_issue(summary, values, ac_items, req, field_ids)
    result, skipped_ids = _post_with_screen_retry("/rest/api/3/issue", issue_body)

    if not result:
        print("\n⛔  Failed to create issue.")
        sys.exit(1)

    issue_key = result["key"]
    issue_url = f"{BASE}/browse/{issue_key}"

    # ── Post screen-blocked fields as a comment ───────────────────────────────
    if skipped_ids:
        id_to_name = {v: k for k, v in field_ids.items()}
        lines = ["*Fields blocked by screen config — set these manually:*\n"]
        for fid in skipped_ids:
            name  = id_to_name.get(fid, fid)
            value = values.get(name, "(see requirements)")
            lines.append(f"*{name}*:\n{value}\n")
        _post(
            f"/rest/api/3/issue/{issue_key}/comment",
            {"body": {"version": 1, "type": "doc", "content": [_para(l) for l in lines]}},
        )
        print(f"  ✓ Skipped field values posted as comment on {issue_key}")

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "═" * 70)
    print(f" ✓ Story created : {issue_key}")
    print(f" URL             : {issue_url}")
    print("═" * 70)
    print(
        "\n Next steps:\n"
        f"  1. Open {issue_url} and verify the custom fields\n"
        "  2. Add label 'api-spec-required' if not already present\n"
        "  3. Transition to 'Ready for Dev' to trigger the spec workflow\n"
        "  4. Run the repo-to-openapi skill to regenerate the implementation spec\n"
        "  5. Compare against the jira-to-openapi spec for contract alignment\n"
    )
    print("═" * 70)


if __name__ == "__main__":
    main()
