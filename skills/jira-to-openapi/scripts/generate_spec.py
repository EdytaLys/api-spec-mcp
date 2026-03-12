#!/usr/bin/env python3
"""
generate_spec.py
================
Fetches a JIRA story (API-First template) and generates an OpenAPI 3.0 spec.
Supports both the classic pipe-delimited field format and the newer
comma-delimited / free-text story template.

If an existing spec is supplied (via --existing-spec or the
"API Existing Contract" custom field), the script:
  1. Checks whether each new endpoint already exists.
  2. Generates a diff showing what would change.
  3. Flags breaking vs. additive changes in plain English.
  4. Writes a merged, updated spec file.

Usage:
    python generate_spec.py SCRUM-10
    python generate_spec.py SCRUM-10 --output my-spec.yaml
    python generate_spec.py SCRUM-10 --format json
    python generate_spec.py SCRUM-10 --path /api/tasks/{id}
    python generate_spec.py SCRUM-10 \\
        --existing-spec https://github.com/EdytaLys/api-spec-task-manager/blob/main/specs/task-manager-openapi.yaml

Requirements: pip install requests pyyaml
"""

import os, sys, re, json, argparse, textwrap
from copy import deepcopy
from pathlib import Path

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    sys.exit("Missing dependency: pip install requests pyyaml")

try:
    import yaml
except ImportError:
    yaml = None

# ─── CONFIG ───────────────────────────────────────────────────────────────────
CONFIG = {
    "base_url":    os.environ.get("JIRA_BASE_URL", "").rstrip("/"),
    "email":       os.environ.get("JIRA_EMAIL", ""),
    "token":       os.environ.get("JIRA_API_TOKEN", ""),
    "github_token": os.environ.get("GITHUB_TOKEN", ""),
}

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
    "integer": ("integer", None),   "int":      ("integer", None),
    "long":    ("integer", "int64"),"number":   ("number",  None),
    "float":   ("number",  "float"),"double":   ("number",  "double"),
    "string":  ("string",  None),   "text":     ("string",  None),
    "str":     ("string",  None),   "boolean":  ("boolean", None),
    "bool":    ("boolean", None),   "array":    ("array",   None),
    "list":    ("array",   None),   "object":   ("object",  None),
    "dict":    ("object",  None),   "uuid":     ("string",  "uuid"),
    "date":    ("string",  "date"), "datetime": ("string",  "date-time"),
    "url":     ("string",  "uri"),
}

# HTTP methods that carry a request body
BODY_METHODS = {"POST", "PUT", "PATCH"}

# ─── JIRA API ─────────────────────────────────────────────────────────────────
def _jira_session() -> requests.Session:
    s = requests.Session()
    s.auth = HTTPBasicAuth(CONFIG["email"], CONFIG["token"])
    s.headers.update({"Accept": "application/json"})
    return s

def fetch_issue(issue_key: str) -> dict:
    url = f"{CONFIG['base_url']}/rest/api/3/issue/{issue_key}"
    r = _jira_session().get(url)
    if r.status_code == 401:
        sys.exit("⛔  401 Unauthorized — check JIRA_EMAIL and JIRA_API_TOKEN.")
    if r.status_code == 404:
        sys.exit(f"⛔  404 Not Found — issue {issue_key!r} does not exist.")
    r.raise_for_status()
    return r.json()

def fetch_all_fields() -> dict[str, str]:
    r = _jira_session().get(f"{CONFIG['base_url']}/rest/api/3/field")
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
    if t in ("paragraph", "heading", "doc", "listItem", "taskItem"):
        return adf_to_text(children)
    if t in ("bulletList", "orderedList", "taskList"):
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
_ENDPOINT_RE = re.compile(
    r"(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(/[^\s,\n]+)", re.IGNORECASE
)

def parse_endpoints_from_text(text: str) -> list[tuple[str, str]]:
    """
    Extract (METHOD, /path) pairs from free-text blocks such as:
      PATCH /api/tasks/{id}
      * POST /orders
    Returns a list of (method_upper, path) tuples.
    """
    return [(m.group(1).upper(), m.group(2).rstrip(".,")) for m in _ENDPOINT_RE.finditer(text)]


def parse_request_fields(text: str) -> tuple[list[str], dict]:
    """
    Parse request field definitions from JIRA field text.

    Supports both formats:
      Pipe-delimited (classic):  name | type | required | description
      Comma-delimited (new):     name, type, required
      Markdown bullet (new):     * title, string, optional
    """
    required_fields, properties = [], {}
    for line in text.splitlines():
        raw_line = line.strip().lstrip("-•* ").strip()
        if not raw_line or "[FILL IN]" in raw_line or "name |" in raw_line.lower():
            continue

        # Choose separator: pipe takes priority
        if "|" in raw_line:
            parts = [p.strip() for p in raw_line.split("|")]
        elif "," in raw_line:
            parts = [p.strip() for p in raw_line.split(",")]
        else:
            continue

        if len(parts) < 2:
            continue

        name      = re.sub(r"\s+", "_", parts[0]).strip("_")
        raw_type  = parts[1].lower().strip() if len(parts) > 1 else "string"
        req_str   = parts[2].lower()         if len(parts) > 2 else "optional"
        desc      = parts[3].strip()         if len(parts) > 3 else ""

        oa_type, oa_fmt = TYPE_MAP.get(raw_type, ("string", None))
        prop: dict = {"type": oa_type}
        if oa_fmt:
            prop["format"] = oa_fmt
        if desc:
            prop["description"] = desc

        if "required" in req_str:
            required_fields.append(name)
        properties[name] = prop

    return required_fields, properties


def parse_error_scenarios(text: str) -> dict[str, str]:
    """Parse 'NNN — description' or 'NNN - description' lines."""
    errors: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip().lstrip("-•* ").strip()
        m = re.match(r"(\d{3})\s*[—\-–:]+\s*(.+)", line)
        if m:
            errors[m.group(1)] = m.group(2).strip()
    return errors


def parse_path(summary: str) -> str:
    m = re.search(r"(/[a-zA-Z0-9_/{}.-]+)", summary)
    if m:
        return m.group(1).rstrip(".,")
    words = re.findall(r"[a-zA-Z]+", summary.lower())
    skip = {
        "create","update","delete","get","add","post","patch","put","api",
        "endpoint","for","to","and","the","a","an","with","support","enable",
        "allow","implement","template","replace","this","summary","want","so",
        "that","developer","partial","task","user","story","as",
    }
    resource = next((w for w in words if w not in skip and len(w) > 2), "resource")
    return f"/api/{resource}s"


def op_id(method: str, path: str) -> str:
    parts = [method.lower()] + [p for p in path.split("/") if p and not p.startswith("{")]
    return re.sub(r"[^a-zA-Z0-9]", "", parts[0] + "".join(p.title() for p in parts[1:]))


def resource_name(path: str) -> str:
    segs = [s for s in path.split("/") if s and not s.startswith("{")]
    name = segs[-1] if segs else "Resource"
    return name.rstrip("s").title().replace("-", "").replace("_", "")


# ─── GITHUB SPEC FETCHER ─────────────────────────────────────────────────────
def github_blob_to_raw(url: str) -> str:
    """Convert a github.com/…/blob/… URL to raw.githubusercontent.com."""
    # https://github.com/owner/repo/blob/branch/path  →
    # https://raw.githubusercontent.com/owner/repo/branch/path
    url = url.strip()
    m = re.match(
        r"https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)",
        url,
    )
    if m:
        owner, repo, branch, path = m.groups()
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    # Already a raw URL or something else — return as-is
    return url


def fetch_existing_spec(url: str) -> dict | None:
    """
    Fetch an OpenAPI YAML/JSON spec from a URL (GitHub blob or raw).
    Returns the parsed dict, or None on failure.
    """
    if not url:
        return None
    raw_url = github_blob_to_raw(url)
    print(f"  Fetching existing spec: {raw_url}", file=sys.stderr)
    headers = {}
    if CONFIG["github_token"]:
        headers["Authorization"] = f"Bearer {CONFIG['github_token']}"
    try:
        r = requests.get(raw_url, headers=headers, timeout=15)
        r.raise_for_status()
        content = r.text
        if yaml is not None:
            return yaml.safe_load(content)
        return json.loads(content)
    except Exception as e:
        print(f"  ⚠  Could not fetch existing spec: {e}", file=sys.stderr)
        return None


# ─── SPEC BUILDER ─────────────────────────────────────────────────────────────
def build_operation(
    method: str,
    path: str,
    summary: str,
    purpose: str,
    rules: str,
    req_fields: list[str],
    properties: dict,
    error_map: dict[str, str],
    schemas: dict,
) -> dict:
    """Build a single OpenAPI operation object and populate schemas."""
    res = resource_name(path)

    op_desc = purpose.strip()
    if rules.strip():
        op_desc += "\n\n**Validation rules:**\n" + rules.strip()

    # Determine success status code
    success_code = "201" if method == "POST" else "200"
    success_desc = "Resource created" if method == "POST" else "Successful response"

    responses: dict = {
        success_code: {
            "description": success_desc,
            "content": {"application/json": {
                "schema": {"$ref": f"#/components/schemas/{res}Response"}
            }},
        }
    }
    for code, desc in sorted(error_map.items()):
        responses[code] = {"description": desc}
    for code, desc in [
        ("400", "Bad request — validation error"),
        ("401", "Unauthorized"),
        ("500", "Internal server error"),
    ]:
        if code not in responses:
            responses[code] = {"description": desc}

    operation: dict = {
        "summary":     summary,
        "description": op_desc or summary,
        "operationId": op_id(method, path),
        "tags":        [res],
        "responses":   responses,
    }

    if method in BODY_METHODS and properties:
        req_schema_name = f"{res}{method.title()}Request"
        req_schema: dict = {"type": "object", "properties": deepcopy(properties)}
        # PATCH requests never have required fields by convention (partial update)
        if req_fields and method != "PATCH":
            req_schema["required"] = req_fields
        schemas[req_schema_name] = req_schema
        operation["requestBody"] = {
            "required": True,
            "content": {"application/json": {
                "schema": {"$ref": f"#/components/schemas/{req_schema_name}"}
            }},
        }

    # Ensure a Response schema exists
    if f"{res}Response" not in schemas:
        resp_props = {
            "id": {"type": "string", "format": "uuid", "description": "Unique resource identifier"},
        }
        resp_props.update(properties)
        schemas[f"{res}Response"] = {"type": "object", "properties": resp_props}

    return operation


def build_spec(
    issue_key: str,
    fields: dict[str, str],
    summary: str,
    override_path: str | None = None,
) -> dict:
    """Build a standalone OpenAPI 3.0 spec from JIRA field values."""
    method   = (fields.get("API HTTP Method") or "POST").upper()
    path     = override_path or parse_path(summary)
    purpose  = fields.get("API Purpose", "")
    rules    = fields.get("API Validation Rules", "")
    consumers = fields.get("API Consumers", "")
    contract  = fields.get("API Existing Contract", "")
    chg_type  = fields.get("API Change Type", "")

    req_fields, properties = parse_request_fields(fields.get("API Request Fields", ""))
    error_map = parse_error_scenarios(fields.get("API Error Scenarios", ""))

    # Check "New endpoints to create" section in purpose / raw description
    endpoints_text = "\n".join([
        fields.get("API Purpose", ""),
        fields.get("API Request Fields", ""),
        summary,
    ])
    detected = parse_endpoints_from_text(endpoints_text)
    if detected:
        method, path = detected[0]   # use first detected endpoint

    schemas: dict = {}
    res = resource_name(path)
    operation = build_operation(
        method, path, summary, purpose, rules,
        req_fields, properties, error_map, schemas,
    )

    info_extra: dict = {"x-jira-issue": issue_key}
    if chg_type:  info_extra["x-change-type"] = chg_type
    if contract:  info_extra["x-existing-contract"] = contract
    if consumers: info_extra["x-consumers"] = consumers

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
        "paths": {path: {method.lower(): operation}},
        "components": {
            "schemas": schemas,
            "securitySchemes": {
                "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
            },
        },
        "security": [{"BearerAuth": []}],
        "tags": [{"name": res, "description": f"Operations on {res} resources"}],
    }


# ─── SPEC COMPARISON & DIFF ──────────────────────────────────────────────────
def _schema_props(spec: dict, ref: str) -> dict:
    """Resolve a $ref like '#/components/schemas/Foo' and return its properties."""
    if not ref.startswith("#/components/schemas/"):
        return {}
    name = ref.removeprefix("#/components/schemas/")
    return (
        spec.get("components", {})
        .get("schemas", {})
        .get(name, {})
        .get("properties", {})
    )


def _schema_required(spec: dict, ref: str) -> list[str]:
    if not ref.startswith("#/components/schemas/"):
        return []
    name = ref.removeprefix("#/components/schemas/")
    return (
        spec.get("components", {})
        .get("schemas", {})
        .get(name, {})
        .get("required", [])
    )


def compare_operations(
    existing_spec: dict,
    new_spec: dict,
    method: str,
    path: str,
) -> dict:
    """
    Compare a single operation (method + path) between existing and new spec.
    Returns a structured diff dict.
    """
    m = method.lower()
    existing_op = existing_spec.get("paths", {}).get(path, {}).get(m)
    new_op      = new_spec.get("paths", {}).get(path, {}).get(m)

    diff: dict = {
        "path":           path,
        "method":         method.upper(),
        "status":         "unchanged",  # new | added | modified | unchanged
        "breaking":       [],           # list of breaking-change descriptions
        "additive":       [],           # list of additive change descriptions
        "request_body":   {},
        "responses":      {},
        "summary_change": None,
    }

    if existing_op is None and new_op is None:
        return diff  # nothing to compare

    if existing_op is None:
        diff["status"] = "new"
        diff["additive"].append(
            f"{method.upper()} {path} is a brand-new endpoint — no breaking change."
        )
        return diff

    # ── Existing operation is present — do a detailed diff ───────────────────
    diff["status"] = "modified"

    # Summary
    if existing_op.get("summary") != new_op.get("summary"):
        diff["summary_change"] = {
            "before": existing_op.get("summary"),
            "after":  new_op.get("summary"),
        }

    # ── Request body diff ─────────────────────────────────────────────────────
    ex_rb = existing_op.get("requestBody", {})
    nw_rb = new_op.get("requestBody", {})

    if ex_rb and not nw_rb:
        diff["breaking"].append(
            "Request body removed entirely — callers that send a body will be affected."
        )
    elif not ex_rb and nw_rb:
        diff["additive"].append("Request body added (was not present before).")
    elif ex_rb and nw_rb:
        ex_ref = (ex_rb.get("content", {}).get("application/json", {})
                  .get("schema", {}).get("$ref", ""))
        nw_ref = (nw_rb.get("content", {}).get("application/json", {})
                  .get("schema", {}).get("$ref", ""))

        ex_props = _schema_props(existing_spec, ex_ref)
        nw_props = _schema_props(new_spec, nw_ref)
        ex_req   = set(_schema_required(existing_spec, ex_ref))
        nw_req   = set(_schema_required(new_spec, nw_ref))

        removed = set(ex_props) - set(nw_props)
        added   = set(nw_props) - set(ex_props)
        common  = set(ex_props) & set(nw_props)

        for f in removed:
            diff["breaking"].append(
                f"Request field '{f}' was removed — existing callers that send this field will break."
            )
        for f in added:
            if f in nw_req:
                diff["breaking"].append(
                    f"New required request field '{f}' added — existing callers that omit it will break."
                )
            else:
                diff["additive"].append(f"New optional request field '{f}' added.")

        for f in common:
            ex_t = ex_props[f].get("type", "")
            nw_t = nw_props[f].get("type", "")
            if ex_t != nw_t:
                diff["breaking"].append(
                    f"Request field '{f}' changed type from '{ex_t}' to '{nw_t}'."
                )

        newly_required = nw_req - ex_req
        newly_optional = ex_req - nw_req
        for f in newly_required:
            if f not in added:  # already reported above
                diff["breaking"].append(
                    f"Existing optional field '{f}' is now required — existing callers may break."
                )
        for f in newly_optional:
            diff["additive"].append(f"Field '{f}' relaxed from required to optional.")

        diff["request_body"] = {
            "removed_fields":  sorted(removed),
            "added_fields":    sorted(added),
            "changed_types":   [
                f for f in common
                if ex_props[f].get("type") != nw_props[f].get("type")
            ],
        }

    # ── Response diff ─────────────────────────────────────────────────────────
    ex_codes = set(existing_op.get("responses", {}).keys())
    nw_codes = set(new_op.get("responses", {}).keys())
    removed_codes = ex_codes - nw_codes
    added_codes   = nw_codes - ex_codes

    for code in removed_codes:
        desc = existing_op["responses"][code].get("description", "")
        diff["breaking"].append(
            f"HTTP {code} response ('{desc}') removed — clients handling it will be affected."
        )
    for code in added_codes:
        desc = new_op["responses"][code].get("description", "")
        diff["additive"].append(f"New HTTP {code} response added: '{desc}'.")

    diff["responses"] = {
        "removed_codes": sorted(removed_codes),
        "added_codes":   sorted(added_codes),
    }

    if not diff["breaking"] and not diff["additive"]:
        diff["status"] = "unchanged"

    return diff


def merge_spec(existing: dict, new_paths: dict, new_components: dict) -> dict:
    """
    Merge new paths + components into the existing spec.
    Existing paths that are not in new_paths are preserved unchanged.
    """
    merged = deepcopy(existing)
    for path, methods in new_paths.items():
        if path not in merged.setdefault("paths", {}):
            merged["paths"][path] = {}
        for method, operation in methods.items():
            merged["paths"][path][method] = operation

    for schema_name, schema in new_components.get("schemas", {}).items():
        merged.setdefault("components", {}).setdefault("schemas", {})[schema_name] = schema

    # Ensure tags list includes new tags
    existing_tag_names = {t["name"] for t in merged.get("tags", [])}
    for tag in new_components.get("tags", []):
        if tag["name"] not in existing_tag_names:
            merged.setdefault("tags", []).append(tag)

    return merged


# ─── PLAIN-ENGLISH REPORT ────────────────────────────────────────────────────
def generate_report(diffs: list[dict], issue_key: str, summary: str) -> str:
    lines: list[str] = [
        "=" * 72,
        f"  OpenAPI Change Report — {issue_key}",
        f"  {summary}",
        "=" * 72,
        "",
    ]

    for diff in diffs:
        method = diff["method"]
        path   = diff["path"]
        status = diff["status"]

        lines.append(f"  ┌─ {method} {path}")

        if status == "new":
            lines.append("  │  ✅ NEW endpoint — this is an additive change.")
            lines.append("  │     No existing callers will be affected.")

        elif status == "unchanged":
            lines.append("  │  ✔  No changes detected for this endpoint.")

        elif status == "modified":
            has_breaking = bool(diff["breaking"])

            if has_breaking:
                lines.append("  │  ⚠️  BREAKING CHANGES DETECTED:")
                for msg in diff["breaking"]:
                    lines.append(f"  │     ✗ {msg}")
            else:
                lines.append("  │  ✅ Additive changes only — backward compatible.")

            if diff["additive"]:
                lines.append("  │")
                lines.append("  │  ➕ Additive changes:")
                for msg in diff["additive"]:
                    lines.append(f"  │     + {msg}")

            if diff.get("summary_change"):
                before = diff["summary_change"]["before"]
                after  = diff["summary_change"]["after"]
                lines.append(f"  │  📝 Summary changed: '{before}' → '{after}'")

        lines.append("  └" + "─" * 60)
        lines.append("")

    # Overall verdict
    all_breaking = [m for d in diffs for m in d["breaking"]]
    all_additive = [m for d in diffs for m in d["additive"]]

    lines.append("─" * 72)
    lines.append("  OVERALL VERDICT")
    lines.append("─" * 72)

    if not diffs:
        lines.append("  No endpoints were compared.")
    elif all_breaking:
        lines.append("  ⚠️  This change contains BREAKING CHANGES.")
        lines.append("     A major version bump (x.0.0) is recommended.")
        lines.append("     Coordinate with all API consumers before releasing.")
    elif all_additive:
        lines.append("  ✅ All changes are ADDITIVE (backward compatible).")
        lines.append("     A minor version bump (x.y.0) is sufficient.")
    else:
        lines.append("  ✔  No meaningful changes detected.")

    lines.append("")
    lines.append("─" * 72)
    lines.append("  WHAT CHANGED (summary)")
    lines.append("─" * 72)
    for diff in diffs:
        if diff["status"] == "new":
            lines.append(f"  • {diff['method']} {diff['path']} — new endpoint added")
        elif diff["status"] == "modified":
            rb = diff.get("request_body", {})
            added   = rb.get("added_fields", [])
            removed = rb.get("removed_fields", [])
            changed = rb.get("changed_types", [])
            resp    = diff.get("responses", {})
            parts   = []
            if added:   parts.append(f"added fields: {', '.join(added)}")
            if removed: parts.append(f"removed fields: {', '.join(removed)}")
            if changed: parts.append(f"type changes: {', '.join(changed)}")
            if resp.get("added_codes"):
                parts.append(f"new responses: {', '.join(resp['added_codes'])}")
            if resp.get("removed_codes"):
                parts.append(f"removed responses: {', '.join(resp['removed_codes'])}")
            detail = "; ".join(parts) if parts else "no schema changes"
            lines.append(f"  • {diff['method']} {diff['path']} — {detail}")
        elif diff["status"] == "unchanged":
            lines.append(f"  • {diff['method']} {diff['path']} — no change")

    lines.append("")
    return "\n".join(lines)


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate OpenAPI spec from a JIRA story and optionally diff against an existing spec.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("issue_key",
        help="JIRA issue key, e.g. SCRUM-42")
    parser.add_argument("--output", "-o",
        help="Output file path (default: <issue_key>-openapi.yaml)")
    parser.add_argument("--format", "-f", choices=["yaml", "json"], default="yaml")
    parser.add_argument("--path",
        help="Override endpoint path extracted from the story")
    parser.add_argument("--existing-spec",
        metavar="URL_OR_PATH",
        help=(
            "URL (GitHub blob or raw) or local file path of the existing OpenAPI spec "
            "to compare against. Overrides the 'API Existing Contract' custom field."
        ),
    )
    parser.add_argument("--report-only", action="store_true",
        help="Print the change report only; do not write the spec file.")
    args = parser.parse_args()

    key = args.issue_key.upper()

    if not CONFIG["base_url"] or not CONFIG["email"] or not CONFIG["token"]:
        sys.exit("⛔  Set JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN env vars.")

    print(f"\nFetching {key} from {CONFIG['base_url']} …", file=sys.stderr)
    field_ids = load_field_ids()
    if not field_ids:
        sys.exit("⛔  No custom field IDs found. Run scripts/jira_form_setup.py first.")

    issue   = fetch_issue(key)
    summary = issue["fields"].get("summary", key)
    raw     = issue["fields"]
    print(f"  Summary : {summary}", file=sys.stderr)

    # Extract raw field values
    fields_raw: dict[str, str] = {}
    for name, fid in field_ids.items():
        fields_raw[name] = extract_value(raw.get(fid))
        status = "✓" if fields_raw[name] else "○ (empty)"
        print(f"  {status}  {name}", file=sys.stderr)

    # Detect endpoints from story — scan purpose + request fields + summary
    full_text = "\n".join([
        summary,
        fields_raw.get("API Purpose", ""),
        fields_raw.get("API Request Fields", ""),
    ])
    detected_endpoints = parse_endpoints_from_text(full_text)
    if not detected_endpoints:
        # Fall back to HTTP method field + path flag/parse
        method = (fields_raw.get("API HTTP Method") or "POST").upper()
        path   = args.path or parse_path(summary)
        detected_endpoints = [(method, path)]

    if args.path:
        # Override path for first detected endpoint
        detected_endpoints[0] = (detected_endpoints[0][0], args.path)

    print(f"\n  Endpoints in this story:", file=sys.stderr)
    for m, p in detected_endpoints:
        print(f"    {m} {p}", file=sys.stderr)

    # Build the new spec
    new_spec = build_spec(key, fields_raw, summary, override_path=detected_endpoints[0][1])

    # If multiple endpoints detected, add them all
    if len(detected_endpoints) > 1:
        req_fields, properties = parse_request_fields(fields_raw.get("API Request Fields", ""))
        error_map = parse_error_scenarios(fields_raw.get("API Error Scenarios", ""))
        schemas = new_spec["components"]["schemas"]
        for method, path in detected_endpoints[1:]:
            op = build_operation(
                method, path, summary,
                fields_raw.get("API Purpose", ""),
                fields_raw.get("API Validation Rules", ""),
                req_fields, properties, error_map, schemas,
            )
            new_spec["paths"].setdefault(path, {})[method.lower()] = op

    # ── Existing spec comparison ──────────────────────────────────────────────
    existing_spec_url = (
        args.existing_spec
        or fields_raw.get("API Existing Contract", "")
    )
    existing_spec = fetch_existing_spec(existing_spec_url) if existing_spec_url else None

    diffs: list[dict] = []
    merged_spec: dict = new_spec

    if existing_spec:
        print("\n  Comparing against existing spec …", file=sys.stderr)
        for method, path in detected_endpoints:
            diff = compare_operations(existing_spec, new_spec, method, path)
            diffs.append(diff)
            status_label = {
                "new":       "NEW ✅",
                "modified":  "MODIFIED ⚠️" if diff["breaking"] else "MODIFIED ✅",
                "unchanged": "UNCHANGED",
            }.get(diff["status"], diff["status"])
            print(f"    {method} {path} → {status_label}", file=sys.stderr)

        # Merge new endpoints into the existing spec
        merged_spec = merge_spec(
            existing_spec,
            new_spec.get("paths", {}),
            {
                "schemas": new_spec.get("components", {}).get("schemas", {}),
                "tags":    new_spec.get("tags", []),
            },
        )
        # Bump patch version
        ver = merged_spec.get("info", {}).get("version", "1.0.0").split(".")
        has_breaking = any(d["breaking"] for d in diffs)
        has_additive = any(d["additive"] for d in diffs)
        if has_breaking:
            ver[0] = str(int(ver[0]) + 1); ver[1] = "0"; ver[2] = "0"
        elif has_additive:
            ver[1] = str(int(ver[1]) + 1); ver[2] = "0"
        merged_spec["info"]["version"] = ".".join(ver)
        merged_spec["info"]["x-jira-issue"] = key

    # ── Render output ─────────────────────────────────────────────────────────
    ext      = "json" if args.format == "json" else "yaml"
    out_path = Path(args.output) if args.output else Path(f"{key}-openapi.{ext}")

    if args.format == "json" or yaml is None:
        content = json.dumps(merged_spec, indent=2)
    else:
        content = yaml.dump(
            merged_spec,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

    # ── Change report ─────────────────────────────────────────────────────────
    if diffs:
        report = generate_report(diffs, key, summary)
        print("\n" + report, file=sys.stderr)
        report_path = out_path.with_suffix(".change-report.txt")
        report_path.write_text(report, encoding="utf-8")
        print(f"  Change report : {report_path}", file=sys.stderr)

    if not args.report_only:
        out_path.write_text(content, encoding="utf-8")
        print(f"\n✓ Spec saved    : {out_path}", file=sys.stderr)
        print(f"  Version       : {merged_spec.get('info', {}).get('version', '?')}", file=sys.stderr)
        print(f"  Validate at   : https://editor.swagger.io/\n", file=sys.stderr)
        print(content)


if __name__ == "__main__":
    main()
