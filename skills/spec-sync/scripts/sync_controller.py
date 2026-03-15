#!/usr/bin/env python3
"""
sync_controller.py
==================
Sync a Spring Boot (Java) REST controller with an OpenAPI 3.0 specification.

Modes
-----
  verify   Report mismatches between the spec and the controller code.
           Use before every push to catch drift early.

  pull     Update controller method signatures to match the spec.
           Existing method bodies are preserved; new methods get a TODO stub.

Usage
-----
  python sync_controller.py verify
  python sync_controller.py verify --endpoint GET:/api/tasks
  python sync_controller.py pull --dry-run
  python sync_controller.py pull
  python sync_controller.py pull \\
      --spec-url https://raw.githubusercontent.com/owner/repo/main/specs/openapi.yaml \\
      --src-dir src/main/java

Requirements: pip install requests pyyaml
"""

import os, sys, re, json, argparse
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None

try:
    import requests
except ImportError:
    sys.exit("Missing dependency: pip install requests pyyaml")

# ─── Config ───────────────────────────────────────────────────────────────────

_FALLBACK_SPEC_URL = (
    "https://raw.githubusercontent.com/EdytaLys/api-spec-task-manager"
    "/main/specs/task-manager-openapi.yaml"
)
DEFAULT_SPEC_URL = os.environ.get("SPEC_REPO_URL", _FALLBACK_SPEC_URL)
DEFAULT_SRC_DIR  = os.environ.get("SPEC_SYNC_SRC_DIR", "src/main/java")
GITHUB_TOKEN     = os.environ.get("GITHUB_TOKEN", "")

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}

SPRING_MAPPING = {
    "GET":    "GetMapping",
    "POST":   "PostMapping",
    "PUT":    "PutMapping",
    "PATCH":  "PatchMapping",
    "DELETE": "DeleteMapping",
}

_JAVA_SCALARS: dict[tuple, str] = {
    ("integer", ""):        "Integer",
    ("integer", "int32"):   "Integer",
    ("integer", "int64"):   "Long",
    ("string",  ""):        "String",
    ("string",  "date"):    "LocalDate",
    ("string",  "date-time"): "LocalDateTime",
    ("string",  "uuid"):    "UUID",
    ("boolean", ""):        "Boolean",
    ("number",  ""):        "Double",
    ("number",  "float"):   "Float",
    ("number",  "double"):  "Double",
}


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class SpecParam:
    name:     str
    location: str           # query | path | header
    required: bool
    java_type: str
    default:  Optional[str] = None
    maximum:  Optional[int] = None
    example:  Optional[str] = None


@dataclass
class SpecEndpoint:
    method:          str
    path:            str
    summary:         str
    operation_id:    str
    tags:            list
    params:          list       # list[SpecParam]
    has_body:        bool
    body_schema:     Optional[str]      # Java class name for request body
    response_schema: Optional[str]      # Java class name for 200 response


@dataclass
class ControllerMethod:
    http_method:  str
    path:         str
    java_name:    str
    return_type:  str
    param_strs:   list          # raw param annotation strings
    file:         Path
    line_start:   int           # 1-indexed — first annotation line
    line_end:     int           # last line of signature (before {)


# ─── Spec fetching ────────────────────────────────────────────────────────────

def _github_raw(url: str) -> str:
    url = url.replace("https://github.com/", "https://raw.githubusercontent.com/")
    url = url.replace("/blob/", "/")
    return url


def fetch_spec(url_or_path: str) -> dict:
    p = Path(url_or_path)
    if p.exists():
        text = p.read_text(encoding="utf-8")
    else:
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
        r = requests.get(_github_raw(url_or_path), headers=headers, timeout=15)
        r.raise_for_status()
        text = r.text

    parsed = yaml.safe_load(text) if yaml else json.loads(text)
    if not isinstance(parsed, dict) or "paths" not in parsed:
        sys.exit(f"⛔  Could not parse a valid OpenAPI spec from {url_or_path}")
    return parsed


# ─── Type helpers ─────────────────────────────────────────────────────────────

def _scalar(t: str, fmt: str) -> str:
    return _JAVA_SCALARS.get((t, fmt)) or _JAVA_SCALARS.get((t, "")) or "Object"


def schema_to_java(spec: dict, schema: dict) -> str:
    """Convert an OpenAPI schema dict to a bare Java type string."""
    if not schema:
        return "Void"
    if "$ref" in schema:
        return schema["$ref"].split("/")[-1]
    t   = schema.get("type", "")
    fmt = schema.get("format", "")
    if t == "array":
        item = schema_to_java(spec, schema.get("items", {}))
        return f"List<{item}>"
    return _scalar(t, fmt)


def param_java_type(schema: dict) -> str:
    t   = schema.get("type", "string")
    fmt = schema.get("format", "")
    return _scalar(t, fmt)


# ─── Spec parsing ─────────────────────────────────────────────────────────────

def parse_spec(spec: dict, endpoint_filter: Optional[str] = None) -> list:
    endpoints = []
    for path, path_item in spec.get("paths", {}).items():
        for http_method, operation in path_item.items():
            if http_method.upper() not in HTTP_METHODS:
                continue
            if not isinstance(operation, dict):
                continue
            method = http_method.upper()
            if endpoint_filter and endpoint_filter != f"{method}:{path}":
                continue

            # Parameters
            params: list[SpecParam] = []
            for p in operation.get("parameters", []):
                schema = p.get("schema", {})
                params.append(SpecParam(
                    name=p["name"],
                    location=p.get("in", "query"),
                    required=p.get("required", False),
                    java_type=param_java_type(schema),
                    default=schema.get("default"),
                    maximum=schema.get("maximum"),
                    example=p.get("example"),
                ))

            # Path params inferred from URL template (if not already listed)
            for var in re.findall(r"\{(\w+)\}", path):
                if not any(p.name == var for p in params):
                    params.append(SpecParam(name=var, location="path",
                                            required=True, java_type="Long"))

            # Request body
            has_body    = "requestBody" in operation
            body_schema = None
            if has_body:
                content     = operation["requestBody"].get("content", {})
                json_schema = content.get("application/json", {}).get("schema", {})
                body_schema = (json_schema.get("$ref", "").split("/")[-1]
                               or "Object")

            # Success response (200 / 201)
            response_schema = None
            for code in ("200", "201"):
                resp = operation.get("responses", {}).get(code, {})
                json_schema = resp.get("content", {}).get("application/json", {}).get("schema", {})
                if json_schema:
                    response_schema = schema_to_java(spec, json_schema)
                    break

            endpoints.append(SpecEndpoint(
                method=method,
                path=path,
                summary=operation.get("summary", ""),
                operation_id=operation.get("operationId", ""),
                tags=operation.get("tags", []),
                params=params,
                has_body=has_body,
                body_schema=body_schema,
                response_schema=response_schema,
            ))
    return endpoints


# ─── Controller parsing ───────────────────────────────────────────────────────

_RETURN_TYPE_RE = re.compile(
    r'(?:public|protected)\s+([\w<>\[\],\s?]+?)\s+\w+\s*\(')
_METHOD_NAME_RE = re.compile(
    r'(?:public|protected)\s+[\w<>\[\],\s?]+?\s+(\w+)\s*\(')


def find_controller_files(src_dir: Path) -> list[Path]:
    results = []
    for f in src_dir.rglob("*.java"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        if "@RestController" in text or "@Controller" in text:
            results.append(f)
    return results


def parse_controller(file: Path) -> list:
    lines = file.read_text(encoding="utf-8", errors="ignore").splitlines()

    # Class-level @RequestMapping base path
    class_base = ""
    for line in lines:
        m = re.search(r'@RequestMapping\s*\(\s*"([^"]+)"\s*\)', line)
        if m:
            class_base = m.group(1).rstrip("/")
            break

    methods: list[ControllerMethod] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        http_method    = None
        endpoint_path  = None

        # @GetMapping("/path") or bare @GetMapping (path on class-level @RequestMapping)
        for http, ann in SPRING_MAPPING.items():
            if f"@{ann}" in line:
                m = re.search(r'"([^"]*)"', line)
                # bare annotation: @GetMapping or @GetMapping() → path = ""
                endpoint_path = m.group(1) if m else ""
                http_method   = http
                break

        # @RequestMapping(method=RequestMethod.GET, value="/path") style
        if not http_method:
            m = re.search(
                r'@RequestMapping\s*\([^)]*(?:value|path)\s*=\s*"([^"]+)"[^)]*'
                r'method\s*=\s*RequestMethod\.(\w+)',
                line, re.IGNORECASE,
            )
            if m:
                endpoint_path = m.group(1)
                http_method   = m.group(2).upper()

        if http_method and endpoint_path is not None:
            if endpoint_path == "":
                full_path = class_base or "/"
            elif endpoint_path.startswith("/"):
                # Check if class_base is already included
                full_path = (class_base + endpoint_path
                             if not endpoint_path.startswith(class_base)
                             else endpoint_path)
            else:
                full_path = (class_base + "/" + endpoint_path).rstrip("/")
            if not full_path.startswith("/"):
                full_path = "/" + full_path

            ann_line = i

            # Scan forward to find the complete method signature (up to "{")
            j = i + 1
            open_paren = 0
            found_open = False
            sig_end    = i
            while j < min(i + 25, len(lines)):
                l = lines[j]
                open_paren += l.count("(") - l.count(")")
                if "(" in l:
                    found_open = True
                if found_open and open_paren <= 0:
                    sig_end = j
                    break
                j += 1

            sig_text = " ".join(lines[ann_line:sig_end + 1])

            rt_m = _RETURN_TYPE_RE.search(sig_text)
            return_type = rt_m.group(1).strip() if rt_m else "?"

            mn_m = _METHOD_NAME_RE.search(sig_text)
            java_name = mn_m.group(1) if mn_m else "?"

            param_strs = re.findall(r"@\w+(?:\([^)]*\))?\s+[\w<>]+\s+\w+", sig_text)

            methods.append(ControllerMethod(
                http_method=http_method,
                path=full_path,
                java_name=java_name,
                return_type=return_type,
                param_strs=param_strs,
                file=file,
                line_start=ann_line + 1,    # 1-indexed
                line_end=sig_end + 1,
            ))
        i += 1

    return methods


# ─── Signature generation ─────────────────────────────────────────────────────

def _param_ann(p: SpecParam) -> str:
    """Build a single Java parameter declaration from a SpecParam."""
    if p.location == "path":
        return f"@PathVariable {p.java_type} {p.name}"

    parts = []
    if p.default is not None:
        parts.append(f'defaultValue = "{p.default}"')
    elif not p.required:
        parts.append("required = false")
    ann        = f"@RequestParam({', '.join(parts)})" if parts else "@RequestParam"
    constraint = f"@Max({p.maximum}) " if p.maximum else ""
    return f"{ann} {constraint}{p.java_type} {p.name}"


def generate_signature(ep: SpecEndpoint, indent: str = "    ") -> str:
    """Return the Java method annotation + signature string (no body)."""
    spring_ann = SPRING_MAPPING.get(ep.method, "RequestMapping")
    annotation = f'{indent}@{spring_ann}("{ep.path}")'

    ret_type = (f"ResponseEntity<{ep.response_schema}>"
                if ep.response_schema else "ResponseEntity<Void>")

    if ep.operation_id:
        method_name = ep.operation_id[0].lower() + ep.operation_id[1:]
    else:
        slug = re.sub(r"[{}]", "", ep.path).replace("/", "_").strip("_")
        slug = re.sub(r"_+", "_", slug)
        method_name = ep.method.lower() + "".join(w.title() for w in slug.split("_"))

    param_parts = [_param_ann(p) for p in ep.params]
    if ep.has_body and ep.body_schema:
        param_parts.append(f"@RequestBody @Valid {ep.body_schema} request")

    inner_indent = f"{indent}        "
    if not param_parts:
        sig = f"{indent}public {ret_type} {method_name}()"
    elif len(param_parts) == 1:
        sig = f"{indent}public {ret_type} {method_name}({param_parts[0]})"
    else:
        joined = f",\n{inner_indent}".join(param_parts)
        sig = f"{indent}public {ret_type} {method_name}(\n{inner_indent}{joined}\n{indent})"

    return f"{annotation}\n{sig}"


def generate_stub(ep: SpecEndpoint, indent: str = "    ") -> str:
    """Return a complete TODO stub method for a missing endpoint."""
    sig = generate_signature(ep, indent)
    return (
        f"{sig} {{\n"
        f"{indent}    // TODO: implement {ep.method} {ep.path}\n"
        f"{indent}    throw new UnsupportedOperationException(\"Not implemented\");\n"
        f"{indent}}}"
    )


# ─── Path normalisation (for comparison) ─────────────────────────────────────

def _norm(path: str) -> str:
    """Collapse {param} names so /tasks/{id} == /tasks/{taskId}."""
    return re.sub(r"\{[^}]+\}", "{p}", path.lower().rstrip("/"))


# ─── Verify ───────────────────────────────────────────────────────────────────

def verify(spec_eps: list, ctrl_methods: list) -> list[str]:
    issues: list[str] = []
    ctrl_idx = {(_norm(m.path), m.http_method): m for m in ctrl_methods}

    for ep in spec_eps:
        ctrl = ctrl_idx.get((_norm(ep.path), ep.method))
        loc  = f"  [{ctrl.file.name}:{ctrl.line_start}]" if ctrl else ""

        if ctrl is None:
            tag_hint = f" (expected in {ep.tags[0]}Controller)" if ep.tags else ""
            issues.append(f"❌ {ep.method} {ep.path} — missing from controller{tag_hint}")
            continue

        prefix = f"⚠️  {ep.method} {ep.path}"

        # Query params
        for p in ep.params:
            if p.location != "query":
                continue
            if not any(p.name in s for s in ctrl.param_strs):
                issues.append(f"{prefix} — query param '{p.name}' not found{loc}")
                continue
            if p.maximum and not any(f"@Max" in s and p.name in s for s in ctrl.param_strs):
                issues.append(
                    f"{prefix} — param '{p.name}' missing @Max({p.maximum}) constraint{loc}"
                )

        # Request body
        if ep.has_body and not any("RequestBody" in s for s in ctrl.param_strs):
            issues.append(f"{prefix} — spec has requestBody but controller has no @RequestBody{loc}")

        # Return type
        if ep.response_schema and ep.response_schema not in ctrl.return_type:
            issues.append(
                f"{prefix} — return type is '{ctrl.return_type}', "
                f"spec expects '{ep.response_schema}'{loc}"
            )

    # Undocumented endpoints in controller
    spec_keys = {(_norm(ep.path), ep.method) for ep in spec_eps}
    for m in ctrl_methods:
        if (_norm(m.path), m.http_method) not in spec_keys:
            issues.append(
                f"⚠️  {m.http_method} {m.path} — controller endpoint not in spec"
                f"  [{m.file.name}:{m.line_start}]"
            )

    return issues


# ─── Pull ─────────────────────────────────────────────────────────────────────

def pull(
    spec_eps: list,
    ctrl_methods: list,
    dry_run: bool = False,
) -> list[str]:
    changes: list[str] = []
    ctrl_idx = {(_norm(m.path), m.http_method): m for m in ctrl_methods}

    # Group patches by file
    file_patches: dict[Path, list[tuple[int, int, str]]] = {}

    for ep in spec_eps:
        ctrl    = ctrl_idx.get((_norm(ep.path), ep.method))
        new_sig = generate_signature(ep)

        if ctrl is None:
            changes.append(
                f"+ {ep.method} {ep.path} — not in controller; add this stub:\n\n"
                + generate_stub(ep) + "\n"
            )
            continue

        file  = ctrl.file
        lines = file.read_text(encoding="utf-8", errors="ignore").splitlines()
        # Current signature = annotation line + everything up to (but not including) {
        current_sig = "\n".join(lines[ctrl.line_start - 1: ctrl.line_end])

        if new_sig.strip() == current_sig.strip():
            changes.append(f"✔  {ep.method} {ep.path} — already matches spec")
            continue

        changes.append(
            f"→  {ep.method} {ep.path} — updating signature"
            f"  [{file.name}:{ctrl.line_start}]"
        )
        if not dry_run:
            file_patches.setdefault(file, []).append(
                (ctrl.line_start - 1, ctrl.line_end, new_sig)
            )

    # Apply patches in reverse line order to preserve offsets
    for file, patches in file_patches.items():
        lines = file.read_text(encoding="utf-8", errors="ignore").splitlines()
        for start, end, replacement in sorted(patches, key=lambda x: -x[0]):
            lines[start:end] = replacement.splitlines()
        file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return changes


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync a Spring Boot controller with the OpenAPI spec.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("mode", choices=["verify", "pull"],
                        help="'verify' reports mismatches; 'pull' applies signature updates")
    parser.add_argument("--spec-url", default=DEFAULT_SPEC_URL,
                        help="OpenAPI spec URL or local path (default: canonical repo spec)")
    parser.add_argument("--src-dir", default=DEFAULT_SRC_DIR,
                        help="Java source directory (default: src/main/java)")
    parser.add_argument("--endpoint", metavar="METHOD:PATH",
                        help="Filter to one endpoint, e.g. GET:/api/tasks")
    parser.add_argument("--dry-run", action="store_true",
                        help="(pull) Show changes without writing files")
    args = parser.parse_args()

    src_dir = Path(args.src_dir)
    if not src_dir.is_dir():
        sys.exit(f"⛔  Source directory not found: {src_dir}\n"
                 "    Run from your Spring Boot project root or pass --src-dir.")

    # Fetch spec
    print(f"  Fetching spec: {args.spec_url}", file=sys.stderr)
    spec = fetch_spec(args.spec_url)
    spec_eps = parse_spec(spec, endpoint_filter=args.endpoint)
    if not spec_eps:
        sys.exit(f"⛔  No endpoints found" +
                 (f" matching '{args.endpoint}'" if args.endpoint else "") + ".")
    print(f"  Spec has {len(spec_eps)} endpoint(s)", file=sys.stderr)

    # Find controllers
    print(f"  Scanning controllers in {src_dir}", file=sys.stderr)
    ctrl_files = find_controller_files(src_dir)
    if not ctrl_files:
        sys.exit(f"⛔  No @RestController files found in {src_dir}")
    print(f"  Found {len(ctrl_files)} controller file(s)", file=sys.stderr)

    ctrl_methods: list[ControllerMethod] = []
    for f in ctrl_files:
        ctrl_methods.extend(parse_controller(f))
    print(f"  Found {len(ctrl_methods)} mapped method(s)", file=sys.stderr)

    W = 72
    print("\n" + "─" * W, file=sys.stderr)

    if args.mode == "verify":
        print("  VERIFY — spec vs controller", file=sys.stderr)
        print("─" * W + "\n", file=sys.stderr)
        issues = verify(spec_eps, ctrl_methods)
        if not issues:
            print("✅ Controller matches the spec — no issues found.")
        else:
            for issue in issues:
                print(issue)
            sys.exit(1)

    else:  # pull
        label = "(dry run) " if args.dry_run else ""
        print(f"  PULL {label}— updating controller signatures", file=sys.stderr)
        print("─" * W + "\n", file=sys.stderr)
        changes = pull(spec_eps, ctrl_methods, dry_run=args.dry_run)
        for c in changes:
            print(c)
        if args.dry_run:
            print("\n⚠️  Dry run — no files were modified.", file=sys.stderr)


if __name__ == "__main__":
    main()
