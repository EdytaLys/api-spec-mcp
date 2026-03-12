#!/usr/bin/env python3
"""
generate_spec.py
================
Fetches a JIRA story (API-First template) and generates an OpenAPI 3.0 spec.

Usage:
    python generate_spec.py SCRUM-10
    python generate_spec.py SCRUM-10 --output my-spec.yaml
    python generate_spec.py SCRUM-10 --format json
    python generate_spec.py SCRUM-10 --path /payments/initiate

Requirements: pip install requests pyyaml
"""

import os, sys, re, json, argparse
from pathlib import Path

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    sys.exit("Missing dependency: pip install requests")

try:
    import yaml
except ImportError:
    yaml = None  # falls back to JSON output

# ─── CONFIG ───────────────────────────────────────────────────────────────────
CONFIG = {
    "base_url": os.environ.get("JIRA_BASE_URL", "").rstrip("/"),
    "email":    os.environ.get("JIRA_EMAIL", ""),
    "token":    os.environ.get("JIRA_API_TOKEN", ""),
}

# Field config candidates (relative to repo root or script location)
_FIELD_CONFIG_CANDIDATES = [
    Path("scripts/jira_field_config.json"),
    Path(__file__).parent.parent.parent / "scripts/jira_field_config.json",
    Path(__file__).parent / "jira_field_config.json",
]

FIELD_CONFIG_MAP = {
    "API Purpose":           "apiPurpose",
    "API HTTP Method":       "apiHttpMethod",
    "API Request Fields":    "apiRequestFields",
    "API Validation Rules":  "apiValidationRules",
    "API Consumers":         "apiConsumers",
    "API Error Scenarios":   "apiErrorScenarios",
    "API Existing Contract": "apiExistingContract",
    "API Change Type":       "apiChangeType",
}

TYPE_MAP = {
    "integer": ("integer", None),  "int":     ("integer", None),
    "long":    ("integer", "int64"), "number":  ("number",  None),
    "float":   ("number",  "float"), "double":  ("number",  "double"),
    "string":  ("string",  None),  "text":    ("string",  None),
    "boolean": ("boolean", None),  "bool":    ("boolean", None),
    "array":   ("array",   None),  "list":    ("array",   None),
    "object":  ("object",  None),  "dict":    ("object",  None),
    "uuid":    ("string",  "uuid"), "date":    ("string",  "date"),
    "datetime":("string",  "date-time"), "url": ("string", "uri"),
}

# ─── JIRA API ─────────────────────────────────────────────────────────────────
def _session() -> requests.Session:
    s = requests.Session()
    s.auth = HTTPBasicAuth(CONFIG["email"], CONFIG["token"])
    s.headers.update({"Accept": "application/json"})
    return s

def fetch_issue(issue_key: str) -> dict:
    url = f"{CONFIG['base_url']}/rest/api/3/issue/{issue_key}"
    r = _session().get(url)
    if r.status_code == 401:
        sys.exit("⛔  401 Unauthorized — check JIRA_EMAIL and JIRA_API_TOKEN.")
    if r.status_code == 404:
        sys.exit(f"⛔  404 Not Found — issue {issue_key!r} does not exist.")
    r.raise_for_status()
    return r.json()

def fetch_all_fields() -> dict[str, str]:
    r = _session().get(f"{CONFIG['base_url']}/rest/api/3/field")
    r.raise_for_status()
    return {f["name"]: f["id"] for f in r.json()}

# ─── FIELD ID RESOLUTION ─────────────────────────────────────────────────────
def load_field_ids() -> dict[str, str]:
    for candidate in _FIELD_CONFIG_CANDIDATES:
        if candidate.exists():
            with open(candidate) as f:
                cfg = json.load(f)
            custom = cfg.get("customFields", {})
            ids = {
                name: custom[key]
                for name, key in FIELD_CONFIG_MAP.items()
                if key in custom and "XXXXX" not in custom.get(key, "XXXXX")
            }
            if len(ids) >= 6:
                return ids
    # Live fallback
    live = fetch_all_fields()
    return {name: live[name] for name in FIELD_CONFIG_MAP if name in live}

# ─── ADF → PLAIN TEXT ────────────────────────────────────────────────────────
def adf_to_text(node) -> str:
    if node is None:
        return ""
    if isinstance(node, list):
        return "\n".join(adf_to_text(n) for n in node)
    if isinstance(node, str):
        return node
    t = node.get("type", "")
    if t == "text":
        return node.get("text", "")
    children = node.get("content", [])
    if t in ("paragraph", "heading", "doc", "listItem"):
        return adf_to_text(children)
    if t in ("bulletList", "orderedList"):
        return "\n".join("- " + adf_to_text(i).strip() for i in children)
    return adf_to_text(children) if children else node.get("text", "")

def extract_value(raw) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, dict):
        if raw.get("type") == "doc":
            return adf_to_text(raw)
        return raw.get("value", str(raw))
    return str(raw)

# ─── PARSERS ─────────────────────────────────────────────────────────────────
def parse_request_fields(text: str) -> tuple[list[str], dict]:
    required, props = [], {}
    for line in text.splitlines():
        line = line.strip().lstrip("-• ").strip()
        if not line or "[FILL IN]" in line:
            continue
        parts = [p.strip() for p in re.split(r"\|", line)]
        if len(parts) < 2:
            continue
        name     = re.sub(r"\s+", "_", parts[0]).strip("_")
        raw_type = parts[1].lower().strip() if len(parts) > 1 else "string"
        req_flag = parts[2].lower()          if len(parts) > 2 else "optional"
        desc     = parts[3].strip()          if len(parts) > 3 else ""
        oa_type, oa_fmt = TYPE_MAP.get(raw_type, ("string", None))
        prop: dict = {"type": oa_type}
        if oa_fmt:
            prop["format"] = oa_fmt
        if desc:
            prop["description"] = desc
        if "required" in req_flag:
            required.append(name)
        props[name] = prop
    return required, props

def parse_error_scenarios(text: str) -> dict[str, str]:
    errors = {}
    for line in text.splitlines():
        line = line.strip().lstrip("-• ").strip()
        m = re.match(r"(\d{3})\s*[—\-–]+\s*(.+)", line)
        if m:
            errors[m.group(1)] = m.group(2).strip()
    return errors

def parse_path(summary: str) -> str:
    m = re.search(r"(/[a-zA-Z0-9_/{}.-]+)", summary)
    if m:
        return m.group(1).rstrip(".,")
    words = re.findall(r"[a-zA-Z]+", summary.lower())
    skip = {"create","update","delete","get","add","post","patch","put","api",
            "endpoint","for","to","and","the","a","an","with","support","enable",
            "allow","implement","template","replace","this","summary"}
    resource = next((w for w in words if w not in skip and len(w) > 2), "resource")
    return f"/api/{resource}s"

def op_id(method: str, path: str) -> str:
    parts = [method.lower()] + [p for p in path.split("/") if p and not p.startswith("{")]
    return re.sub(r"[^a-zA-Z0-9]", "", parts[0] + "".join(p.title() for p in parts[1:]))

def resource_name(path: str) -> str:
    segs = [s for s in path.split("/") if s and not s.startswith("{")]
    name = segs[-1] if segs else "Resource"
    return name.rstrip("s").title().replace("-", "").replace("_", "")

# ─── SPEC BUILDER ─────────────────────────────────────────────────────────────
def build_spec(issue_key: str, fields: dict[str, str], summary: str,
               override_path: str | None = None) -> dict:
    method    = (fields.get("API HTTP Method") or "POST").upper()
    path      = override_path or parse_path(summary)
    res       = resource_name(path)
    purpose   = fields.get("API Purpose", "")
    rules     = fields.get("API Validation Rules", "")
    consumers = fields.get("API Consumers", "")
    contract  = fields.get("API Existing Contract", "")
    chg_type  = fields.get("API Change Type", "")

    req_fields, properties = parse_request_fields(fields.get("API Request Fields", ""))
    error_map = parse_error_scenarios(fields.get("API Error Scenarios", ""))

    op_desc = purpose.strip()
    if rules.strip():
        op_desc += "\n\n**Validation rules:**\n" + rules.strip()

    # Responses
    responses: dict = {
        "200": {
            "description": "Successful response",
            "content": {"application/json": {
                "schema": {"$ref": f"#/components/schemas/{res}Response"}
            }}
        }
    }
    for code, desc in sorted(error_map.items()):
        responses[code] = {"description": desc}
    for code, desc in [("400", "Bad request"), ("401", "Unauthorized"), ("500", "Internal server error")]:
        if code not in responses:
            responses[code] = {"description": desc}

    operation: dict = {
        "summary":     summary,
        "description": op_desc or summary,
        "operationId": op_id(method, path),
        "tags":        [res],
        "responses":   responses,
    }

    schemas: dict = {}
    if method in ("POST", "PUT", "PATCH") and properties:
        req_schema: dict = {"type": "object", "properties": properties}
        if req_fields:
            req_schema["required"] = req_fields
        schemas[f"{res}Request"] = req_schema
        operation["requestBody"] = {
            "required": True,
            "content": {"application/json": {
                "schema": {"$ref": f"#/components/schemas/{res}Request"}
            }}
        }

    resp_props = {"id": {"type": "string", "format": "uuid",
                         "description": "Unique resource identifier"}}
    resp_props.update(properties)
    schemas[f"{res}Response"] = {"type": "object", "properties": resp_props}

    info_extra: dict = {"x-jira-issue": issue_key}
    if chg_type:
        info_extra["x-change-type"] = chg_type
    if contract:
        info_extra["x-existing-contract"] = contract
    if consumers:
        info_extra["x-consumers"] = consumers

    return {
        "openapi": "3.0.3",
        "info": {
            "title":       summary,
            "description": purpose or summary,
            "version":     "1.0.0",
            **info_extra,
        },
        "servers": [
            {"url": "https://api.example.com/v1",         "description": "Production"},
            {"url": "https://staging-api.example.com/v1", "description": "Staging"},
        ],
        "paths":      {path: {method.lower(): operation}},
        "components": {
            "schemas": schemas,
            "securitySchemes": {
                "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
            }
        },
        "security": [{"BearerAuth": []}],
        "tags": [{"name": res, "description": f"Operations on {res} resources"}],
    }

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Generate OpenAPI spec from a JIRA story.")
    parser.add_argument("issue_key")
    parser.add_argument("--output", "-o")
    parser.add_argument("--format", "-f", choices=["yaml", "json"], default="yaml")
    parser.add_argument("--path", help="Override endpoint path")
    args = parser.parse_args()

    key = args.issue_key.upper()

    if not CONFIG["base_url"] or not CONFIG["email"] or not CONFIG["token"]:
        sys.exit(
            "⛔  Set JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN env vars."
        )

    print(f"Fetching {key} from {CONFIG['base_url']} …", file=sys.stderr)

    field_ids = load_field_ids()
    if not field_ids:
        sys.exit("⛔  No custom field IDs found. Run scripts/jira_form_setup.py first.")

    issue   = fetch_issue(key)
    summary = issue["fields"].get("summary", key)
    raw     = issue["fields"]

    print(f"  Summary : {summary}", file=sys.stderr)

    fields_raw: dict[str, str] = {}
    for name, fid in field_ids.items():
        fields_raw[name] = extract_value(raw.get(fid))
        status = "✓" if fields_raw[name] else "○ (empty)"
        print(f"  {status}  {name}", file=sys.stderr)

    spec = build_spec(key, fields_raw, summary, override_path=args.path)

    ext      = "json" if args.format == "json" else "yaml"
    out_path = Path(args.output) if args.output else Path(f"{key}-openapi.{ext}")

    if args.format == "json" or yaml is None:
        content = json.dumps(spec, indent=2)
    else:
        content = yaml.dump(spec, default_flow_style=False, sort_keys=False, allow_unicode=True)

    out_path.write_text(content, encoding="utf-8")
    print(f"\n✓ Spec saved: {out_path}", file=sys.stderr)
    print(f"  Validate : https://editor.swagger.io/\n", file=sys.stderr)
    print(content)


if __name__ == "__main__":
    main()
