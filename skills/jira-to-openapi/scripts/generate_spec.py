#!/usr/bin/env python3
"""
generate_spec.py
================
Fetches a JIRA story and generates an OpenAPI 3.0 spec with PDF documentation.
Supports both new API creation and existing API updates with change tracking.

Usage:
    python generate_spec.py SCRUM-10
    python generate_spec.py SCRUM-10 --output my-spec.yaml
    python generate_spec.py SCRUM-10 --repo-url https://github.com/user/repo
    python generate_spec.py SCRUM-10 --existing-spec path/to/existing.yaml

Requirements: pip install requests pyyaml reportlab
"""

import os, sys, re, json, argparse
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    sys.exit("Missing dependency: pip install requests")

try:
    import yaml
except ImportError:
    yaml = None

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("⚠️  reportlab not available. PDF generation disabled. Install with: pip install reportlab", file=sys.stderr)

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


def extract_section_from_description(description_adf: dict, section_heading: str) -> str:
    """
    Extract content from a specific section in ADF description.
    Looks for a heading with the given text and returns all content until the next heading.
    """
    if not description_adf or description_adf.get("type") != "doc":
        return ""

    content_nodes = description_adf.get("content", [])
    section_content = []
    in_section = False

    for node in content_nodes:
        node_type = node.get("type", "")

        # Check if this is a heading
        if node_type == "heading":
            heading_text = adf_to_text(node).strip().lower()
            target_heading = section_heading.lower()

            if target_heading in heading_text or heading_text in target_heading:
                in_section = True
                continue
            elif in_section:
                # Hit another heading, stop collecting
                break

        # Collect content if we're in the target section
        if in_section:
            section_content.append(node)

    if not section_content:
        return ""

    # Convert collected nodes to text
    result = []
    for node in section_content:
        text = adf_to_text(node).strip()
        if text:
            result.append(text)

    return "\n".join(result)


def parse_description_sections(description_adf: dict) -> Dict[str, str]:
    """
    Parse the description field to extract sections created by create_api_update_story.py
    Returns a dict with section names as keys.
    """
    sections = {}

    # Extract each section
    sections["Request fields"] = extract_section_from_description(description_adf, "Request fields")
    sections["Validation rules"] = extract_section_from_description(description_adf, "Validation rules")
    sections["Error scenarios"] = extract_section_from_description(description_adf, "Error scenarios")
    sections["Required changes"] = extract_section_from_description(description_adf, "Required changes")
    sections["Acceptance criteria"] = extract_section_from_description(description_adf, "Acceptance criteria")
    sections["New endpoints to create"] = extract_section_from_description(description_adf, "New endpoints to create")

    # Extract purpose from the first paragraph (user story)
    if description_adf and description_adf.get("type") == "doc":
        content_nodes = description_adf.get("content", [])
        for node in content_nodes:
            if node.get("type") == "paragraph":
                sections["Purpose"] = adf_to_text(node).strip()
                break

    return sections


# ─── PARSERS ─────────────────────────────────────────────────────────────────
def parse_request_fields_enhanced(text: str) -> tuple[list[str], dict]:
    """
    Parse request fields from both old and new formats.
    New format: fieldName, type, required/optional
    Old format: name | type | required/optional | validation note
    """
    required, props = [], {}
    
    for line in text.splitlines():
        line = line.strip().lstrip("-•📝 ").strip()
        
        # Skip empty lines, examples, and placeholder text
        if not line or "Example" in line or "[FILL IN]" in line or "Please specify" in line:
            continue
        
        # Try comma-separated format first (new format)
        if "," in line and "|" not in line:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                name = re.sub(r"\s+", "_", parts[0]).strip("_")
                raw_type = parts[1].lower().strip()
                req_flag = parts[2].lower() if len(parts) > 2 else "optional"
                desc = parts[3].strip() if len(parts) > 3 else ""
                
                # Handle enum types: status, enum (TODO/IN_PROGRESS/DONE), required
                if "enum" in raw_type:
                    enum_match = re.search(r"enum\s*\(([^)]+)\)", raw_type, re.IGNORECASE)
                    if enum_match:
                        enum_values = [v.strip() for v in enum_match.group(1).split("/")]
                        oa_type, oa_fmt = "string", None
                        prop: dict = {"type": oa_type, "enum": enum_values}
                    else:
                        oa_type, oa_fmt = "string", None
                        prop = {"type": oa_type}
                else:
                    oa_type, oa_fmt = TYPE_MAP.get(raw_type, ("string", None))
                    prop = {"type": oa_type}
                    if oa_fmt:
                        prop["format"] = oa_fmt
                
                if desc:
                    prop["description"] = desc
                if "required" in req_flag:
                    required.append(name)
                props[name] = prop
                continue
        
        # Try pipe-separated format (old format)
        if "|" in line:
            parts = [p.strip() for p in re.split(r"\|", line)]
            if len(parts) < 2:
                continue
            name     = re.sub(r"\s+", "_", parts[0]).strip("_")
            raw_type = parts[1].lower().strip()
            req_flag = parts[2].lower() if len(parts) > 2 else "optional"
            desc     = parts[3].strip() if len(parts) > 3 else ""
            
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


def parse_validation_rules(text: str) -> List[str]:
    """Parse validation rules from plain English descriptions."""
    rules = []
    for line in text.splitlines():
        line = line.strip().lstrip("-•📝 ").strip()
        # Skip empty lines, examples, and placeholder text
        if line and "Example" not in line and "Please specify" not in line:
            rules.append(line)
    return rules

def parse_error_scenarios(text: str) -> dict[str, str]:
    errors = {}
    for line in text.splitlines():
        line = line.strip().lstrip("-•📝 ").strip()
        # Skip examples and placeholder text
        if "Example" in line or "Please specify" in line:
            continue
        m = re.match(r"(\d{3})\s*[—\-–]+\s*(.+)", line)
        if m:
            errors[m.group(1)] = m.group(2).strip()
    return errors


def fetch_existing_spec_from_github(repo_url: str, spec_path: str = "specs/task-manager-openapi.yaml") -> Optional[dict]:
    """Fetch existing OpenAPI spec from GitHub repository."""
    try:
        # Convert GitHub URL to raw content URL
        if "github.com" in repo_url:
            # https://github.com/user/repo -> https://raw.githubusercontent.com/user/repo/main/
            raw_url = repo_url.replace("github.com", "raw.githubusercontent.com")
            if not raw_url.endswith("/"):
                raw_url += "/"
            # Try main branch first, then master
            for branch in ["main", "master"]:
                try:
                    url = f"{raw_url}{branch}/{spec_path}"
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        return yaml.safe_load(response.text) if yaml else json.loads(response.text)
                except:
                    continue
        return None
    except Exception as e:
        print(f"⚠️  Could not fetch existing spec: {e}", file=sys.stderr)
        return None


def load_existing_spec(file_path: str) -> Optional[dict]:
    """Load existing OpenAPI spec from local file."""
    try:
        path = Path(file_path)
        if path.exists():
            with open(path, 'r') as f:
                if path.suffix in ['.yaml', '.yml']:
                    return yaml.safe_load(f) if yaml else None
                else:
                    return json.load(f)
        return None
    except Exception as e:
        print(f"⚠️  Could not load existing spec: {e}", file=sys.stderr)
        return None


def detect_changes(old_spec: dict, new_spec: dict) -> Dict[str, List[str]]:
    """Detect changes between old and new OpenAPI specs."""
    changes = {
        "breaking": [],
        "additive": [],
        "modified": []
    }
    
    old_paths = old_spec.get("paths", {})
    new_paths = new_spec.get("paths", {})
    
    # Check for new endpoints
    for path in new_paths:
        if path not in old_paths:
            for method in new_paths[path]:
                changes["additive"].append(f"New endpoint: {method.upper()} {path}")
        else:
            # Check for new methods on existing paths
            for method in new_paths[path]:
                if method not in old_paths[path]:
                    changes["additive"].append(f"New method: {method.upper()} {path}")
                else:
                    # Check for changes in existing methods
                    old_method = old_paths[path][method]
                    new_method = new_paths[path][method]
                    
                    # Check request body changes
                    old_req = old_method.get("requestBody", {})
                    new_req = new_method.get("requestBody", {})
                    
                    if old_req and not new_req:
                        changes["breaking"].append(f"Removed request body: {method.upper()} {path}")
                    elif new_req and not old_req:
                        changes["additive"].append(f"Added request body: {method.upper()} {path}")
                    
                    # Check response changes
                    old_responses = set(old_method.get("responses", {}).keys())
                    new_responses = set(new_method.get("responses", {}).keys())
                    
                    removed_responses = old_responses - new_responses
                    added_responses = new_responses - old_responses
                    
                    for code in removed_responses:
                        changes["breaking"].append(f"Removed response {code}: {method.upper()} {path}")
                    for code in added_responses:
                        changes["additive"].append(f"Added response {code}: {method.upper()} {path}")
    
    # Check for removed endpoints
    for path in old_paths:
        if path not in new_paths:
            for method in old_paths[path]:
                changes["breaking"].append(f"Removed endpoint: {method.upper()} {path}")
        else:
            # Check for removed methods
            for method in old_paths[path]:
                if method not in new_paths[path]:
                    changes["breaking"].append(f"Removed method: {method.upper()} {path}")
    
    # Check schema changes
    old_schemas = old_spec.get("components", {}).get("schemas", {})
    new_schemas = new_spec.get("components", {}).get("schemas", {})
    
    for schema_name in new_schemas:
        if schema_name not in old_schemas:
            changes["additive"].append(f"New schema: {schema_name}")
        else:
            old_props = old_schemas[schema_name].get("properties", {})
            new_props = new_schemas[schema_name].get("properties", {})
            old_required = set(old_schemas[schema_name].get("required", []))
            new_required = set(new_schemas[schema_name].get("required", []))
            
            # Check for new required fields (breaking)
            newly_required = new_required - old_required
            for field in newly_required:
                changes["breaking"].append(f"Field '{field}' is now required in {schema_name}")
            
            # Check for removed fields (breaking)
            removed_fields = set(old_props.keys()) - set(new_props.keys())
            for field in removed_fields:
                changes["breaking"].append(f"Removed field '{field}' from {schema_name}")
            
            # Check for new optional fields (additive)
            new_fields = set(new_props.keys()) - set(old_props.keys())
            for field in new_fields:
                if field not in new_required:
                    changes["additive"].append(f"New optional field '{field}' in {schema_name}")
    
    return changes

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
               override_path: str | None = None, existing_spec: Optional[dict] = None) -> dict:
    method    = (fields.get("API HTTP Method") or "POST").upper()
    path      = override_path or parse_path(summary)
    res       = resource_name(path)
    purpose   = fields.get("API Purpose", "")
    rules_text = fields.get("API Validation Rules", "")
    consumers = fields.get("API Consumers", "")
    contract  = fields.get("API Existing Contract", "")
    chg_type  = fields.get("API Change Type", "")

    req_fields, properties = parse_request_fields_enhanced(fields.get("API Request Fields", ""))
    validation_rules = parse_validation_rules(rules_text)
    error_map = parse_error_scenarios(fields.get("API Error Scenarios", ""))

    op_desc = purpose.strip()
    if validation_rules:
        op_desc += "\n\n**Validation rules:**\n" + "\n".join(f"- {rule}" for rule in validation_rules)

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

    info_extra: dict = {"x-jira-issue": issue_key, "x-generated-at": datetime.utcnow().isoformat() + "Z"}
    if chg_type:
        info_extra["x-change-type"] = chg_type
    if contract:
        info_extra["x-existing-contract"] = contract
    if consumers:
        info_extra["x-consumers"] = consumers

    # Merge with existing spec if provided
    if existing_spec:
        # Start with existing spec structure
        spec = existing_spec.copy()
        
        # Update info
        spec["info"].update({
            "title": summary,
            "description": purpose or summary,
            "version": increment_version(existing_spec.get("info", {}).get("version", "1.0.0"), chg_type),
            **info_extra
        })
        
        # Merge paths
        if "paths" not in spec:
            spec["paths"] = {}
        if path not in spec["paths"]:
            spec["paths"][path] = {}
        spec["paths"][path][method.lower()] = operation
        
        # Merge schemas
        if "components" not in spec:
            spec["components"] = {}
        if "schemas" not in spec["components"]:
            spec["components"]["schemas"] = {}
        spec["components"]["schemas"].update(schemas)
        
        return spec
    else:
        # Create new spec
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


def increment_version(version: str, change_type: str) -> str:
    """Increment version based on change type."""
    try:
        parts = version.split(".")
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
        
        if change_type and "breaking" in change_type.lower():
            return f"{major + 1}.0.0"
        else:
            return f"{major}.{minor + 1}.0"
    except:
        return version

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Generate OpenAPI spec from a JIRA story.")
    parser.add_argument("issue_key")
    parser.add_argument("--output", "-o")
    parser.add_argument("--format", "-f", choices=["yaml", "json"], default="yaml")
    parser.add_argument("--path", help="Override endpoint path")
    parser.add_argument("--repo-url", help="GitHub repo URL to fetch existing spec")
    parser.add_argument("--existing-spec", help="Local path to existing spec")
    args = parser.parse_args()

    key = args.issue_key.upper()

    if not CONFIG["base_url"] or not CONFIG["email"] or not CONFIG["token"]:
        sys.exit(
            "⛔  Set JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN env vars."
        )

    print(f"Fetching {key} from {CONFIG['base_url']} …", file=sys.stderr)

    issue   = fetch_issue(key)
    summary = issue["fields"].get("summary", key)
    raw     = issue["fields"]

    print(f"  Summary : {summary}", file=sys.stderr)

    # Try to parse from description first (new format from create_api_update_story.py)
    description_adf = raw.get("description")
    fields_raw: dict[str, str] = {}

    if description_adf and isinstance(description_adf, dict):
        print(f"  Parsing description sections...", file=sys.stderr)
        sections = parse_description_sections(description_adf)

        # Map sections to expected field names
        fields_raw = {
            "API Purpose": sections.get("Purpose", ""),
            "API Request Fields": sections.get("Request fields", ""),
            "API Validation Rules": sections.get("Validation rules", ""),
            "API Error Scenarios": sections.get("Error scenarios", ""),
            "API HTTP Method": "",
            "API Consumers": "",
            "API Existing Contract": "",
            "API Change Type": "",
        }

        # Try to extract HTTP method from "New endpoints to create" section
        endpoints_section = sections.get("New endpoints to create", "")
        if endpoints_section:
            for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
                if method in endpoints_section.upper():
                    fields_raw["API HTTP Method"] = method
                    break

        # If still no method, try to extract from summary
        if not fields_raw["API HTTP Method"]:
            for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
                if method in summary.upper():
                    fields_raw["API HTTP Method"] = method
                    break

        print(f"  ✓  Parsed from description", file=sys.stderr)
        print(f"  ✓  Request fields: {'Yes' if fields_raw['API Request Fields'] else 'No'}", file=sys.stderr)
        print(f"  ✓  Validation rules: {'Yes' if fields_raw['API Validation Rules'] else 'No'}", file=sys.stderr)
        print(f"  ✓  Error scenarios: {'Yes' if fields_raw['API Error Scenarios'] else 'No'}", file=sys.stderr)
        print(f"  ✓  HTTP Method: {fields_raw['API HTTP Method'] or 'Not found (will default to POST)'}", file=sys.stderr)
    else:
        # Fall back to custom fields (old format)
        print(f"  Trying custom fields...", file=sys.stderr)
        field_ids = load_field_ids()
        if not field_ids:
            print(f"  ⚠️  No custom fields found, using description only", file=sys.stderr)
        else:
            for name, fid in field_ids.items():
                fields_raw[name] = extract_value(raw.get(fid))
                status = "✓" if fields_raw[name] else "○ (empty)"
                print(f"  {status}  {name}", file=sys.stderr)

    # Load existing spec if requested
    existing_spec = None
    if args.repo_url:
        print(f"\n  Fetching existing spec from {args.repo_url}...", file=sys.stderr)
        existing_spec = fetch_existing_spec_from_github(args.repo_url)
        if existing_spec:
            print(f"  ✓  Found existing spec", file=sys.stderr)
        else:
            print(f"  ⚠️  No existing spec found, creating new", file=sys.stderr)
    elif args.existing_spec:
        print(f"\n  Loading existing spec from {args.existing_spec}...", file=sys.stderr)
        existing_spec = load_existing_spec(args.existing_spec)
        if existing_spec:
            print(f"  ✓  Loaded existing spec", file=sys.stderr)
        else:
            print(f"  ⚠️  Could not load spec, creating new", file=sys.stderr)

    spec = build_spec(key, fields_raw, summary, override_path=args.path, existing_spec=existing_spec)

    # Detect changes if we have an existing spec
    changes = None
    if existing_spec:
        print(f"\n  Detecting changes...", file=sys.stderr)
        changes = detect_changes(existing_spec, spec)
        if changes["breaking"]:
            print(f"  ⚠️  {len(changes['breaking'])} breaking change(s)", file=sys.stderr)
        if changes["additive"]:
            print(f"  ✓  {len(changes['additive'])} additive change(s)", file=sys.stderr)

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
