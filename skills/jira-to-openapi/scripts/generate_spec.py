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


# ─── DESCRIPTION SECTION PARSER ──────────────────────────────────────────────
# Lines that are placeholder instructions — not real data
_PLACEHOLDER_PATTERNS = [
    re.compile(r"📝"),
    re.compile(r"^examples?:?$", re.IGNORECASE),
    re.compile(r"^please specify", re.IGNORECASE),
    re.compile(r"\(for PATCH endpoints\)", re.IGNORECASE),
    re.compile(r"^e\.?g\.?[\s:]", re.IGNORECASE),
]

def _is_placeholder(line: str) -> bool:
    return any(p.search(line) for p in _PLACEHOLDER_PATTERNS)


def _node_text(node: dict) -> str:
    """Extract plain text from a single ADF node (no recursion into lists)."""
    return "".join(
        n.get("text", "") for n in node.get("content", []) if n.get("type") == "text"
    )


def parse_description_sections(adf_doc: dict | None) -> dict[str, list[str]]:
    """
    Walk an ADF document and group bullet/paragraph lines under their nearest
    heading. Returns {normalised_heading: [non-placeholder lines]}.

    Normalised heading = lower-cased, stripped heading text.
    """
    if not adf_doc:
        return {}

    sections: dict[str, list[str]] = {}
    current_heading: str | None = None
    intro_lines: list[str] = []   # lines before the first heading

    for child in adf_doc.get("content", []):
        t = child.get("type", "")

        if t == "heading":
            current_heading = _node_text(child).strip().lower()
            sections.setdefault(current_heading, [])

        elif t == "paragraph":
            text = _node_text(child).strip()
            if not text or _is_placeholder(text):
                continue
            if current_heading is None:
                intro_lines.append(text)
            else:
                sections[current_heading].append(text)

        elif t in ("bulletList", "orderedList"):
            for item in child.get("content", []):
                # listItem → paragraph(s) → text nodes
                parts: list[str] = []
                for para in item.get("content", []):
                    for n in para.get("content", []):
                        if n.get("type") == "text":
                            parts.append(n["text"])
                line = "".join(parts).strip()
                if not line or _is_placeholder(line):
                    continue
                if current_heading is None:
                    intro_lines.append(line)
                else:
                    sections.setdefault(current_heading, []).append(line)

    # Store intro paragraph under a synthetic key
    if intro_lines:
        sections["_intro"] = intro_lines

    return sections


# Heading aliases → canonical field names used internally
_SECTION_ALIASES: dict[str, str] = {
    # endpoints
    "new endpoints to create":  "endpoints",
    "new endpoint":             "endpoints",
    "endpoint":                 "endpoints",
    "endpoints":                "endpoints",
    # request fields
    "request fields":           "request_fields",
    "request body":             "request_fields",
    "fields":                   "request_fields",
    # validation
    "validation rules":         "validation_rules",
    "validation":               "validation_rules",
    "business rules":           "validation_rules",
    # errors
    "error scenarios":          "error_scenarios",
    "errors":                   "error_scenarios",
    "error cases":              "error_scenarios",
    # acceptance criteria
    "acceptance criteria":      "acceptance_criteria",
    "done criteria":            "acceptance_criteria",
    # context / purpose
    "context":                  "context",
    "description":              "context",
    "background":               "context",
    # required changes
    "required changes":         "required_changes",
    "changes":                  "required_changes",
}

def normalise_sections(raw: dict[str, list[str]]) -> dict[str, list[str]]:
    """Map raw heading keys to canonical names using _SECTION_ALIASES."""
    out: dict[str, list[str]] = {}
    for heading, lines in raw.items():
        canonical = _SECTION_ALIASES.get(heading, heading)
        out.setdefault(canonical, []).extend(lines)
    return out


def extract_fields_from_description(adf_doc: dict | None) -> dict[str, str]:
    """
    Parse the JIRA description ADF and return a dict with the same keys as
    fields_raw (API Purpose, API Request Fields, etc.) so it can be merged.
    """
    raw_sections = parse_description_sections(adf_doc)
    sec = normalise_sections(raw_sections)

    result: dict[str, str] = {}

    # API Purpose — from context section or intro paragraph
    purpose_lines = sec.get("context", []) + sec.get("_intro", [])
    if purpose_lines:
        result["API Purpose"] = "\n".join(purpose_lines)

    # API Request Fields — lines like "title, string, optional"
    rf_lines = sec.get("request_fields", [])
    if rf_lines:
        result["API Request Fields"] = "\n".join(rf_lines)

    # API Validation Rules
    vr_lines = sec.get("validation_rules", [])
    if vr_lines:
        result["API Validation Rules"] = "\n".join(f"- {l.lstrip('- ')}" for l in vr_lines)

    # API Error Scenarios
    es_lines = sec.get("error_scenarios", [])
    if es_lines:
        result["API Error Scenarios"] = "\n".join(es_lines)

    # Acceptance criteria — stored as plain text for description embedding
    ac_lines = sec.get("acceptance_criteria", [])
    if ac_lines:
        result["_acceptance_criteria"] = "\n".join(ac_lines)

    # Required changes — stored for description context
    rc_lines = sec.get("required_changes", [])
    if rc_lines:
        result["_required_changes"] = "\n".join(f"- {l.lstrip('- ')}" for l in rc_lines)

    # Endpoint method from "endpoints" section (e.g. "PATCH /api/tasks/{id}")
    ep_lines = sec.get("endpoints", [])
    for line in ep_lines:
        m = _ENDPOINT_RE.search(line)
        if m:
            result["API HTTP Method"] = m.group(1).upper()
            break   # first endpoint wins; multi-endpoint handled by parse_endpoints_from_text

    return result

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
    acceptance_criteria: str = "",
    required_changes: str = "",
) -> dict:
    """Build a single OpenAPI operation object and populate schemas."""
    res = resource_name(path)

    op_desc = purpose.strip()
    if required_changes.strip() and not op_desc:
        op_desc = required_changes.strip()
    if rules.strip():
        op_desc += "\n\n**Validation rules:**\n" + rules.strip()
    if acceptance_criteria.strip():
        op_desc += "\n\n**Acceptance criteria:**\n" + acceptance_criteria.strip()

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
    override_method: str | None = None,
) -> dict:
    """Build a standalone OpenAPI 3.0 spec from JIRA field values."""
    method   = (override_method or fields.get("API HTTP Method") or "POST").upper()
    path     = override_path or parse_path(summary)
    purpose  = fields.get("API Purpose", "")
    rules    = fields.get("API Validation Rules", "")
    consumers = fields.get("API Consumers", "")
    contract  = fields.get("API Existing Contract", "")
    chg_type  = fields.get("API Change Type", "")
    ac_text   = fields.get("_acceptance_criteria", "")
    rc_text   = fields.get("_required_changes", "")

    req_fields, properties = parse_request_fields(fields.get("API Request Fields", ""))
    error_map = parse_error_scenarios(fields.get("API Error Scenarios", ""))

    # Enrich purpose with required-changes context if purpose is sparse
    if rc_text and not purpose:
        purpose = rc_text

    # NOTE: endpoint detection is done in main() before calling build_spec;
    # build_spec receives override_path so no endpoint regex scanning here.

    schemas: dict = {}
    res = resource_name(path)
    operation = build_operation(
        method, path, summary, purpose, rules,
        req_fields, properties, error_map, schemas,
        acceptance_criteria=ac_text,
        required_changes=rc_text,
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

    if new_op is None:
        return diff  # new spec didn't generate this operation — skip

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


# ─── JIRA COMMENT POSTER ─────────────────────────────────────────────────────
def _adf_para(text: str) -> dict:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}

def _adf_heading(text: str, level: int = 3) -> dict:
    return {"type": "heading", "attrs": {"level": level},
            "content": [{"type": "text", "text": text}]}

def _adf_bullet(items: list[str]) -> dict:
    return {"type": "bulletList", "content": [
        {"type": "listItem", "content": [_adf_para(i)]} for i in items
    ]}

def _adf_code(text: str, lang: str = "yaml") -> dict:
    return {"type": "codeBlock", "attrs": {"language": lang},
            "content": [{"type": "text", "text": text}]}


def _extract_operation_yaml(spec_yaml: str, method: str) -> str:
    """Pull the generated operation block out of the rendered YAML string."""
    target = f"{method.lower()}:"
    lines, in_op = [], False
    for line in spec_yaml.splitlines():
        stripped = line.strip()
        if stripped == target:
            in_op = True
        elif in_op and stripped and not line.startswith("    ") and not line.startswith("  "):
            break
        if in_op:
            lines.append(line)
    return "\n".join(lines)


def _plain_english_summary(
    story_summary: str,
    diffs: list[dict],
    detected_endpoints: list[tuple[str, str]],
    fields_raw: dict[str, str],
) -> list[str]:
    """
    Return a list of plain-English sentences describing what changed in the API.
    Each item becomes a separate bullet in the 'What changed' section.
    """
    purpose     = fields_raw.get("API Purpose", "").strip()
    consumers   = fields_raw.get("API Consumers", "").strip()
    change_type = fields_raw.get("API Change Type", "").strip()
    sentences: list[str] = []

    if not diffs:
        # No existing spec to diff against — describe the new endpoint from story fields
        for method, path in detected_endpoints:
            sentences.append(f"A new {method} {path} endpoint is being introduced.")
        if purpose:
            sentences.append(f"Purpose: {purpose}")
        if consumers:
            sentences.append(f"Intended consumers: {consumers}")
        if change_type:
            sentences.append(f"Change type indicated in story: {change_type}")
        if not sentences:
            sentences.append(f"New API design from story: {story_summary}")
        return sentences

    for diff in diffs:
        method = diff["method"]
        path   = diff["path"]
        status = diff["status"]

        if status == "new":
            sentences.append(
                f"A brand-new {method} {path} endpoint is added — no existing consumers are affected."
            )
            if purpose:
                sentences.append(f"Purpose: {purpose}")

        elif status == "unchanged":
            sentences.append(f"{method} {path} has no schema changes.")

        else:
            breaking = diff.get("breaking", [])
            additive = diff.get("additive", [])

            if breaking:
                sentences.append(
                    f"{method} {path} has {len(breaking)} breaking change(s) that will affect existing consumers:"
                )
                for msg in breaking:
                    sentences.append(f"  • {msg}")

            if additive:
                sentences.append(
                    f"{method} {path} has {len(additive)} backward-compatible addition(s):"
                )
                for msg in additive:
                    sentences.append(f"  • {msg}")

            sc = diff.get("summary_change")
            if sc:
                sentences.append(
                    f"The endpoint description changed from \"{sc['before']}\" to \"{sc['after']}\"."
                )

    if consumers:
        sentences.append(f"Known consumers of this API: {consumers}")

    return sentences


def build_comment_body(
    issue_key: str,
    summary: str,
    diffs: list[dict],
    merged_spec: dict,
    endpoint_only_yaml: str,
    detected_endpoints: list[tuple[str, str]],
    fields_raw: dict[str, str],
) -> dict:
    """Build an ADF comment body with the change report and the full endpoint-only spec."""
    all_breaking = [m for d in diffs for m in d["breaking"]]
    all_additive = [m for d in diffs for m in d["additive"]]
    new_version   = merged_spec.get("info", {}).get("version", "?")

    # ── Header ────────────────────────────────────────────────────────────────
    content: list[dict] = [
        _adf_heading("🤖 Auto-generated OpenAPI Change Report", level=2),
    ]

    # ── Plain-English summary ──────────────────────────────────────────────────
    plain = _plain_english_summary(summary, diffs, detected_endpoints, fields_raw)
    if plain:
        content.append(_adf_heading("What changed", level=3))
        content.append(_adf_bullet(plain))

    # ── Per-endpoint verdict ───────────────────────────────────────────────────
    for diff in diffs:
        method = diff["method"]
        path   = diff["path"]
        status = diff["status"]

        content.append(_adf_heading(f"{method} {path}", level=3))

        if status == "new":
            verdict_items = [
                "✅ NEW endpoint — additive change, no breaking impact",
                "No existing callers will be affected",
            ]
        elif status == "unchanged":
            verdict_items = ["✔  No changes detected for this endpoint."]
        else:
            verdict_items = []
            for msg in diff["breaking"]:
                verdict_items.append(f"⚠️  BREAKING: {msg}")
            for msg in diff["additive"]:
                verdict_items.append(f"➕ {msg}")
            if diff.get("summary_change"):
                verdict_items.append(
                    f"📝 Summary: '{diff['summary_change']['before']}' → '{diff['summary_change']['after']}'"
                )

        content.append(_adf_bullet(verdict_items))

    # ── Full endpoint-only spec (Swagger-pasteable) ────────────────────────────
    if endpoint_only_yaml:
        content.append(_adf_heading("Generated OpenAPI spec (paste into editor.swagger.io)", level=3))
        content.append(_adf_code(endpoint_only_yaml, "yaml"))

    # ── Overall verdict ────────────────────────────────────────────────────────
    content.append(_adf_heading("Overall verdict", level=3))
    if all_breaking:
        verdict_bullets = [
            f"⚠️  BREAKING CHANGES — major version bump recommended",
            f"Version: {new_version}",
            "Coordinate with all API consumers before releasing",
        ]
        for msg in all_breaking:
            verdict_bullets.append(f"✗ {msg}")
    elif all_additive:
        verdict_bullets = [
            f"✅ All changes are ADDITIVE — backward compatible",
            f"Version bumped to {new_version} (minor bump sufficient)",
        ]
    else:
        verdict_bullets = [f"✔  No meaningful changes. Version: {new_version}"]
    content.append(_adf_bullet(verdict_bullets))

    # ── Request fields detected ────────────────────────────────────────────────
    rf = fields_raw.get("API Request Fields", "")
    if rf:
        _, props = parse_request_fields(rf)
        if props:
            content.append(_adf_heading("Request schema detected", level=3))
            schema_lines = ["type: object", "properties:"]
            for fname, fdef in props.items():
                fmt = f", format: {fdef['format']}" if "format" in fdef else ""
                schema_lines.append(f"  {fname}: {{ type: {fdef['type']}{fmt} }}")
            content.append(_adf_code("\n".join(schema_lines), "yaml"))

    # ── Next steps ────────────────────────────────────────────────────────────
    content.append(_adf_heading("Next steps", level=3))
    content.append(_adf_bullet([
        "Review and validate at https://editor.swagger.io/",
        "Raise a PR to update specs/task-manager-openapi.yaml in api-spec-task-manager repo",
        "Existing spec: https://github.com/EdytaLys/api-spec-task-manager/blob/main/specs/task-manager-openapi.yaml",
    ]))
    content.append(_adf_para(f"Generated by jira-to-openapi skill • generate_spec.py {issue_key}"))

    return {"version": 1, "type": "doc", "content": content}


def create_subtask_in_jira(
    parent_key: str,
    diffs: list[dict],
    description_body: dict,
    project_key: str = "SCRUM",
) -> str | None:
    """
    Create a Subtask under parent_key containing the OpenAPI change report.
    Returns the new subtask URL on success, or None on failure.
    """
    all_breaking = [m for d in diffs for m in d["breaking"]]
    endpoints    = ", ".join(f"{d['method']} {d['path']}" for d in diffs)

    if not diffs:
        summary = f"OpenAPI spec review: {parent_key} — generated spec"
    elif all_breaking:
        summary = f"OpenAPI spec review: {endpoints} — breaking changes detected"
    elif any(d["additive"] for d in diffs):
        summary = f"OpenAPI spec review: {endpoints} — additive changes, update spec"
    else:
        summary = f"OpenAPI spec review: {endpoints} — no schema changes"

    body = {
        "fields": {
            "project":     {"key": project_key},
            "parent":      {"key": parent_key},
            "issuetype":   {"name": "Subtask"},
            "summary":     summary,
            "description": description_body,
            "labels":      ["api-spec-generated"],
        }
    }

    r = _jira_session().post(f"{CONFIG['base_url']}/rest/api/3/issue", json=body)
    if r.status_code in (200, 201):
        data = r.json()
        subtask_key = data.get("key", "?")
        return f"{CONFIG['base_url']}/browse/{subtask_key}"

    # Subtask issue type may not exist on the project — try "Task" as fallback
    if r.status_code == 400 and "issuetype" in r.text.lower():
        body["fields"]["issuetype"] = {"name": "Task"}
        body["fields"].pop("parent", None)   # tasks don't always require parent
        r2 = _jira_session().post(f"{CONFIG['base_url']}/rest/api/3/issue", json=body)
        if r2.status_code in (200, 201):
            data = r2.json()
            task_key = data.get("key", "?")
            # Link back to parent via issue link
            _jira_session().post(
                f"{CONFIG['base_url']}/rest/api/3/issueLink",
                json={
                    "type":         {"name": "is subtask of"},
                    "inwardIssue":  {"key": task_key},
                    "outwardIssue": {"key": parent_key},
                },
            )
            return f"{CONFIG['base_url']}/browse/{task_key}"

    print(f"  ⚠  Failed to create subtask: {r.status_code} {r.text[:400]}", file=sys.stderr)
    return None


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
    parser.add_argument("--create-subtask", action="store_true", default=True,
        help="Create a Subtask under the JIRA issue with the change report and generated spec (default: on).")
    parser.add_argument("--no-subtask", dest="create_subtask", action="store_false",
        help="Skip subtask creation.")
    parser.add_argument("--project", default="SCRUM",
        help="JIRA project key used when creating the subtask (default: SCRUM).")
    args = parser.parse_args()

    key = args.issue_key.upper()

    if not CONFIG["base_url"] or not CONFIG["email"] or not CONFIG["token"]:
        sys.exit("⛔  Set JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN env vars.")

    print(f"\nFetching {key} from {CONFIG['base_url']} …", file=sys.stderr)

    issue   = fetch_issue(key)
    summary = issue["fields"].get("summary", key)
    raw     = issue["fields"]
    print(f"  Summary : {summary}", file=sys.stderr)

    # Extract all fields from the description sections
    desc_adf = raw.get("description")
    desc_fields = extract_fields_from_description(desc_adf)

    fields_raw: dict[str, str] = {}
    for key_name, value in desc_fields.items():
        if value:
            fields_raw[key_name] = value
            if not key_name.startswith("_"):
                print(f"  ✓  {key_name}", file=sys.stderr)

    # 3. Detect NEW endpoints only — restrict search to safe sources so that
    #    references to existing endpoints ("Keep PUT …", "existing GET …") in
    #    Context / Required-changes sections are never picked up.
    #
    #    Priority (highest → lowest):
    #      a) "New endpoints to create" / "Endpoints" description section
    #      b) Story summary line
    #      c) API HTTP Method custom field + parsed path
    raw_sections = parse_description_sections(desc_adf)
    norm_sections = normalise_sections(raw_sections)

    # (a) Explicit "endpoints" section
    ep_section_lines = norm_sections.get("endpoints", [])
    detected_endpoints = parse_endpoints_from_text("\n".join(ep_section_lines))

    # (b) Summary line (covers "Add PATCH /api/tasks/{id} …" pattern)
    if not detected_endpoints:
        detected_endpoints = parse_endpoints_from_text(summary)

    # (c) Custom field fallback
    if not detected_endpoints:
        method = (fields_raw.get("API HTTP Method") or "POST").upper()
        path   = args.path or parse_path(summary)
        detected_endpoints = [(method, path)]

    if args.path:
        detected_endpoints[0] = (detected_endpoints[0][0], args.path)

    print(f"\n  Endpoints in this story:", file=sys.stderr)
    for m, p in detected_endpoints:
        print(f"    {m} {p}", file=sys.stderr)

    # Build the new spec — pass both the detected method and path
    new_spec = build_spec(
        key, fields_raw, summary,
        override_path=detected_endpoints[0][1],
        override_method=detected_endpoints[0][0],
    )

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
                acceptance_criteria=fields_raw.get("_acceptance_criteria", ""),
                required_changes=fields_raw.get("_required_changes", ""),
            )
            new_spec["paths"].setdefault(path, {})[method.lower()] = op

    # ── Existing spec comparison ──────────────────────────────────────────────
    _DEFAULT_EXISTING_SPEC = (
        "https://raw.githubusercontent.com/EdytaLys/api-spec-task-manager"
        "/main/specs/task-manager-openapi.yaml"
    )
    existing_spec_url = (
        args.existing_spec
        or fields_raw.get("API Existing Contract", "")
        or _DEFAULT_EXISTING_SPEC
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

    def _render(spec: dict) -> str:
        if args.format == "json" or yaml is None:
            return json.dumps(spec, indent=2)
        return yaml.dump(spec, default_flow_style=False, sort_keys=False, allow_unicode=True)

    content          = _render(merged_spec)
    endpoint_content = _render(new_spec)

    # ── Change report ─────────────────────────────────────────────────────────
    if diffs:
        report = generate_report(diffs, key, summary)
        print("\n" + report, file=sys.stderr)
        report_path = out_path.with_suffix(".change-report.txt")
        report_path.write_text(report, encoding="utf-8")
        print(f"  Change report : {report_path}", file=sys.stderr)

    if not args.report_only:
        # Always write the endpoint-only spec (pasteable directly into Swagger Editor)
        ep_only_path = out_path.with_name(f"{key}-endpoint-only.{ext}")
        ep_only_path.write_text(endpoint_content, encoding="utf-8")
        print(f"\n✓ Endpoint-only spec: {ep_only_path}  ← paste this into https://editor.swagger.io/", file=sys.stderr)

        # Write the full merged spec (all endpoints from existing spec + new one)
        out_path.write_text(content, encoding="utf-8")
        print(f"✓ Full merged spec  : {out_path}", file=sys.stderr)
        print(f"  Version           : {merged_spec.get('info', {}).get('version', '?')}", file=sys.stderr)

        # Print the endpoint-only YAML to stdout so it's easy to copy
        print("\n" + "─" * 72, file=sys.stderr)
        print("  ENDPOINT-ONLY SPEC (copy-paste into https://editor.swagger.io/)", file=sys.stderr)
        print("─" * 72 + "\n", file=sys.stderr)
        print(endpoint_content)

    # ── Create subtask in JIRA ────────────────────────────────────────────────
    if args.create_subtask:
        print(f"\n  Creating subtask under {key} …", file=sys.stderr)
        description_body = build_comment_body(
            key, summary, diffs, merged_spec,
            endpoint_content, detected_endpoints, fields_raw,
        )
        subtask_url = create_subtask_in_jira(
            key, diffs, description_body,
            project_key=args.project,
        )
        if subtask_url:
            print(f"  ✓ Subtask created: {subtask_url}", file=sys.stderr)
        else:
            print("  ⚠  Subtask creation failed.", file=sys.stderr)


if __name__ == "__main__":
    main()
