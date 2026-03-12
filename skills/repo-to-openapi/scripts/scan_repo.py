#!/usr/bin/env python3
"""
scan_repo.py
============
Scans a GitHub repository (remote) or a local directory and generates an OpenAPI 3.0
spec from all REST endpoints found in source code.
Produces output compatible with the jira-to-openapi skill (same schema style, security
scheme, and x-* extension conventions) for seamless JIRA integration.

Usage — remote GitHub repo:
    python scan_repo.py https://github.com/owner/repo
    python scan_repo.py https://github.com/owner/repo --branch develop
    python scan_repo.py https://github.com/owner/repo --base-url https://api.example.com/v1

Usage — local directory:
    python scan_repo.py /path/to/local/repo
    python scan_repo.py /path/to/local/repo --branch feature/my-branch   # for display only
    python scan_repo.py . --base-url http://localhost:8080

Common options:
    --output my-spec.yaml
    --format json
    --upload-to https://github.com/owner/specs-repo

Requirements: pip install requests pyyaml
"""

import os, sys, re, json, base64, argparse, datetime
from pathlib import Path, PurePosixPath

try:
    import requests
except ImportError:
    sys.exit("Missing dependency: pip install requests")

try:
    import yaml
except ImportError:
    yaml = None

GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# ─── HTTP SESSION ─────────────────────────────────────────────────────────────

def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Accept": "application/vnd.github+json"})
    if GITHUB_TOKEN:
        s.headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return s

SESSION = _session()

# ─── GITHUB HELPERS ───────────────────────────────────────────────────────────

def parse_github_url(url: str) -> tuple[str, str]:
    """Return (owner, repo) from a GitHub URL."""
    url = url.rstrip("/").removesuffix(".git")
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+)", url)
    if not m:
        sys.exit(f"⛔  Cannot parse GitHub URL: {url!r}")
    return m.group(1), m.group(2)

def fetch_tree(owner: str, repo: str, branch: str) -> list[dict]:
    """Return flat list of all file entries in the repo tree."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    r = SESSION.get(url)
    if r.status_code == 404:
        sys.exit(f"⛔  Repo or branch not found: {owner}/{repo}@{branch}")
    r.raise_for_status()
    data = r.json()
    if data.get("truncated"):
        print("⚠  Tree truncated — large repo; some files may be missed.", file=sys.stderr)
    return [f for f in data.get("tree", []) if f["type"] == "blob"]

def fetch_file(owner: str, repo: str, path: str, branch: str) -> str:
    """Return decoded text content of a file."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    r = SESSION.get(url)
    if r.status_code == 404:
        return ""
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list):
        return ""
    content = data.get("content", "")
    encoding = data.get("encoding", "base64")
    if encoding == "base64":
        return base64.b64decode(content).decode("utf-8", errors="replace")
    return content

def default_branch(owner: str, repo: str) -> str:
    r = SESSION.get(f"{GITHUB_API}/repos/{owner}/{repo}")
    r.raise_for_status()
    return r.json().get("default_branch", "main")

def repo_description(owner: str, repo: str) -> str:
    r = SESSION.get(f"{GITHUB_API}/repos/{owner}/{repo}")
    r.raise_for_status()
    return r.json().get("description") or ""

# ─── LOCAL REPO HELPERS ───────────────────────────────────────────────────────

import subprocess

def _git(root: Path, *args: str) -> str:
    """Run a git command in root and return stdout, or '' on error."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout if result.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""

def _is_git_repo(root: Path) -> bool:
    return bool(_git(root, "rev-parse", "--git-dir").strip())

def local_git_branch(root: Path) -> str:
    """Return the currently checked-out branch name, or ''."""
    return _git(root, "rev-parse", "--abbrev-ref", "HEAD").strip()

def local_git_tree(root: Path, branch: str) -> list[str]:
    """List all file paths in a git branch (no checkout needed)."""
    out = _git(root, "ls-tree", "-r", "--name-only", branch)
    return [line for line in out.splitlines() if line]

def local_git_fetcher(root: Path, branch: str):
    """Return a fetcher that reads file content from a specific git branch."""
    def _fetch(rel_path: str) -> str:
        return _git(root, "show", f"{branch}:{rel_path}")
    return _fetch

def local_tree(root: Path) -> list[str]:
    """Return relative POSIX paths of all files under root, skipping common noise dirs."""
    _skip = {".git", "node_modules", "__pycache__", ".gradle", "target", "build",
             "dist", "out", ".idea", ".vscode", ".mvn"}
    paths: list[str] = []
    for p in root.rglob("*"):
        if p.is_file() and not any(part in _skip for part in p.parts):
            paths.append(p.relative_to(root).as_posix())
    return paths

def local_fetcher(root: Path):
    """Return a fetcher that reads files from the working tree on disk."""
    def _fetch(rel_path: str) -> str:
        full = root / rel_path
        try:
            return full.read_text(encoding="utf-8", errors="replace")
        except (OSError, IsADirectoryError):
            return ""
    return _fetch

def local_readme_base_url(root: Path, fetcher=None) -> str:
    """Try to extract a production URL from README."""
    for name in ("README.md", "readme.md", "README.rst"):
        text = fetcher(name) if fetcher else ""
        if not text:
            p = root / name
            if p.exists():
                text = p.read_text(errors="replace")
        if text:
            m = re.search(r'https?://[^\s)\"\']+run\.app', text)
            if m:
                return m.group(0).rstrip("/")
    return ""

# ─── FRAMEWORK DETECTION ──────────────────────────────────────────────────────

def detect_framework(file_paths: list[str], fetcher) -> str:
    """Return one of: springboot | fastapi | flask | express | django | unknown."""
    names = {p.split("/")[-1] for p in file_paths}
    # pom.xml can be in a subdirectory (e.g. backend/pom.xml)
    pom_paths = [p for p in file_paths if p.split("/")[-1] == "pom.xml"]
    for pom_path in pom_paths:
        pom = fetcher(pom_path)
        if "spring-boot" in pom:
            return "springboot"
    gradle_paths = [p for p in file_paths if p.split("/")[-1] in ("build.gradle", "build.gradle.kts")]
    for g in gradle_paths:
        if "spring-boot" in fetcher(g):
            return "springboot"
    req_paths = [p for p in file_paths if p.split("/")[-1] == "requirements.txt"]
    for rp in req_paths:
        req = fetcher(rp).lower()
        if "fastapi" in req:
            return "fastapi"
        if "flask" in req:
            return "flask"
        if "django" in req:
            return "django"
    pkg_paths = [p for p in file_paths if p.split("/")[-1] == "package.json"
                 and "node_modules" not in p]
    for pp in pkg_paths:
        try:
            data = json.loads(fetcher(pp))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "@nestjs/core" in deps or "nestjs" in str(deps):
                return "nestjs"
            if "express" in deps:
                return "express"
            if "fastify" in deps:
                return "fastify"
        except Exception:
            pass
    return "unknown"

# ─── TYPE MAPPING ─────────────────────────────────────────────────────────────

# Maps Java / TypeScript / Python types → (OA type, OA format)
TYPE_MAP: dict[str, tuple[str, str | None]] = {
    # Java primitives
    "string": ("string", None), "String": ("string", None),
    "int": ("integer", "int32"), "Integer": ("integer", "int32"),
    "long": ("integer", "int64"), "Long": ("integer", "int64"),
    "double": ("number", "double"), "Double": ("number", "double"),
    "float": ("number", "float"), "Float": ("number", "float"),
    "boolean": ("boolean", None), "Boolean": ("boolean", None),
    "Instant": ("string", "date-time"),
    "LocalDate": ("string", "date"),
    "LocalDateTime": ("string", "date-time"),
    "ZonedDateTime": ("string", "date-time"),
    "OffsetDateTime": ("string", "date-time"),
    "UUID": ("string", "uuid"),
    "BigDecimal": ("number", None),
    "BigInteger": ("integer", None),
    # TypeScript / JS
    "number": ("number", None),
    "Date": ("string", "date-time"),
    # Python
    "int": ("integer", None),
    "float": ("number", None),
    "str": ("string", None),
    "bool": ("boolean", None),
    "datetime": ("string", "date-time"),
    "date": ("string", "date"),
    "uuid": ("string", "uuid"),
    # Generic
    "object": ("object", None),
    "array": ("array", None),
}

def java_type_to_oa(java_type: str) -> dict:
    """Convert a Java type string to an OpenAPI schema snippet."""
    java_type = java_type.strip()
    # List<X> or Collection<X>
    m = re.match(r"(?:List|Set|Collection|Iterable)<(.+)>", java_type)
    if m:
        inner = java_type_to_oa(m.group(1))
        return {"type": "array", "items": inner}
    # Optional<X>
    m = re.match(r"Optional<(.+)>", java_type)
    if m:
        return java_type_to_oa(m.group(1))
    # Map<K,V>
    if java_type.startswith("Map<"):
        return {"type": "object", "additionalProperties": True}
    t, fmt = TYPE_MAP.get(java_type, ("string", None))
    result: dict = {"type": t}
    if fmt:
        result["format"] = fmt
    return result

# ─── PARSERS: SPRING BOOT ─────────────────────────────────────────────────────

_MAPPING_RE = re.compile(
    r'@(?P<verb>Get|Post|Put|Delete|Patch|Request)Mapping\s*'
    r'(?:\(\s*(?:value\s*=\s*)?'
    r'(?:"(?P<path1>[^"]*)"|\{[^}]*"(?P<path1b>[^"]+)"[^}]*\})'
    r'(?:.*?method\s*=\s*RequestMethod\.(?P<method>[A-Z]+))?'
    r'[^)]*\))?',
    re.DOTALL,
)

_FIELD_RE = re.compile(
    r'(?:private|public|protected)\s+'
    r'(?P<type>[\w<>,\s]+?)\s+'
    r'(?P<name>\w+)\s*;'
)

_ANNOTATION_FIELD_RE = re.compile(
    r'@(?:NotNull|NotBlank|NotEmpty|Size|Min|Max|Valid)\b.*?\n'
    r'\s*(?:private|public|protected)\s+'
    r'(?P<type>[\w<>,\s]+?)\s+'
    r'(?P<name>\w+)\s*;',
    re.DOTALL,
)

_NOT_NULL_RE = re.compile(
    r'@(?:NotNull|NotBlank|NotEmpty)\b.*?(?:private|public|protected)\s+[\w<>,\s]+?\s+(\w+)\s*;',
    re.DOTALL,
)

def _extract_dto_fields(content: str, class_name: str) -> tuple[list[str], dict]:
    """Extract fields from a DTO class body; returns (required_list, properties_dict)."""
    # Find class body
    m = re.search(rf'class\s+{re.escape(class_name)}\s*(?:extends[^{{]*)?\{{', content)
    if not m:
        return [], {}
    start = m.end()
    depth, end = 1, start
    while end < len(content) and depth > 0:
        if content[end] == "{":
            depth += 1
        elif content[end] == "}":
            depth -= 1
        end += 1
    body = content[start:end]

    required = []
    props: dict = {}

    # Fields with annotations
    for fm in _FIELD_RE.finditer(body):
        java_type = fm.group("type").strip()
        name = fm.group("name")
        if name in ("serialVersionUID",):
            continue
        props[name] = java_type_to_oa(java_type)

    # Required annotations
    for m2 in _NOT_NULL_RE.finditer(body):
        fname = m2.group(1)
        if fname in props:
            required.append(fname)

    return required, props

def parse_springboot(files: list[str], fetcher) -> tuple[list[dict], dict]:
    """
    Returns:
        endpoints: list of endpoint dicts
        schemas:   dict of schema name → schema object
    """
    endpoints: list[dict] = []
    schemas: dict = {}
    dto_cache: dict[str, tuple[list, dict]] = {}  # class_name → (required, props)

    # Collect all Java source files
    java_files = [f for f in files if f.endswith(".java")]

    # Cache all file contents keyed by simple class name
    class_content: dict[str, str] = {}
    for path in java_files:
        content = fetcher(path)
        cls_m = re.search(r'(?:class|interface|enum)\s+(\w+)', content)
        if cls_m:
            class_content[cls_m.group(1)] = content

    def get_dto_schema(class_name: str) -> dict:
        if class_name not in dto_cache:
            content = class_content.get(class_name, "")
            dto_cache[class_name] = _extract_dto_fields(content, class_name)
        required, props = dto_cache[class_name]
        if props:
            schema: dict = {"type": "object", "properties": props}
            if required:
                schema["required"] = required
            schemas[class_name] = schema
        return {"$ref": f"#/components/schemas/{class_name}"}

    # Find controllers
    for path, content in class_content.items():
        if not re.search(r'@(?:Rest)?Controller\b', content):
            continue

        # Class-level base path
        base_m = re.search(
            r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?'
            r'"([^"]+)"',
            content
        )
        base_path = base_m.group(1) if base_m else ""
        base_path = base_path.rstrip("/")

        # Find each mapped method
        method_re = re.compile(
            r'@(?P<verb>Get|Post|Put|Delete|Patch)Mapping\s*'
            r'(?:\(\s*(?:value\s*=\s*)?'
            r'"(?P<path>[^"]*)"[^)]*\))?'
            r'(?:(?!@(?:Get|Post|Put|Delete|Patch|Request)Mapping).)*?'
            r'(?:public|protected)\s+'
            r'(?P<return_type>[\w<>?,\s]+?)\s+'
            r'(?P<method_name>\w+)\s*\((?P<params>[^)]*)\)',
            re.DOTALL,
        )

        for mm in method_re.finditer(content):
            verb = mm.group("verb").upper()
            sub_path = (mm.group("path") or "").strip("/")
            full_path = base_path + ("/" + sub_path if sub_path else "")
            if not full_path:
                full_path = "/"
            # Normalise path params: {id} → {id}  (already OK in Java)
            method_name = mm.group("method_name")
            params_str = mm.group("params")
            return_type = mm.group("return_type").strip()

            # Parse parameters
            path_params: list[dict] = []
            query_params: list[dict] = []
            request_body_ref: dict | None = None

            for param in re.split(r",\s*(?=@|(?:final\s+)?[A-Z])", params_str):
                param = param.strip()
                if not param:
                    continue
                if "@PathVariable" in param:
                    ptype_m = re.search(r'@PathVariable[^)]*\)\s+([\w<>]+)\s+(\w+)', param)
                    if not ptype_m:
                        ptype_m = re.search(r'(?:final\s+)?([\w<>]+)\s+(\w+)\s*$', param)
                    if ptype_m:
                        path_params.append({
                            "name": ptype_m.group(2),
                            "in": "path",
                            "required": True,
                            "schema": java_type_to_oa(ptype_m.group(1)),
                        })
                elif "@RequestParam" in param:
                    rp_m = re.search(
                        r'@RequestParam\s*(?:\([^)]*\))?\s+(?:final\s+)?([\w<>]+)\s+(\w+)', param
                    )
                    if rp_m:
                        required_flag = 'required = false' not in param
                        qp: dict = {
                            "name": rp_m.group(2),
                            "in": "query",
                            "required": required_flag,
                            "schema": java_type_to_oa(rp_m.group(1)),
                        }
                        query_params.append(qp)
                elif "@RequestBody" in param:
                    rb_m = re.search(r'(?:final\s+)?([\w<>]+)\s+(\w+)\s*$', param)
                    if rb_m:
                        dto_name = rb_m.group(1)
                        get_dto_schema(dto_name)
                        request_body_ref = {"$ref": f"#/components/schemas/{dto_name}"}

            # Response schema: unwrap ResponseEntity<SuccessResponse<X>> → X
            resp_schema = _unwrap_return_type(return_type, class_content, schemas, get_dto_schema)

            ep: dict = {
                "verb": verb,
                "path": full_path,
                "operation_id": method_name,
                "path_params": path_params,
                "query_params": query_params,
                "request_body_ref": request_body_ref,
                "response_schema": resp_schema,
                "tags": [_path_to_tag(full_path)],
            }
            endpoints.append(ep)

    # Always ensure wrapper schemas present
    _ensure_wrapper_schemas(schemas)
    return endpoints, schemas

def _unwrap_return_type(
    return_type: str,
    class_content: dict[str, str],
    schemas: dict,
    get_dto_schema,
) -> dict:
    """Extract the inner data type from ResponseEntity<SuccessResponse<X>>."""
    # Strip ResponseEntity<...>
    inner = return_type.strip()
    m = re.match(r'ResponseEntity<(.+)>$', inner)
    if m:
        inner = m.group(1).strip()
    # Strip SuccessResponse<...> or ApiResponse<...>
    m = re.match(r'(?:Success|Api)Response<(.+)>$', inner)
    if m:
        inner = m.group(1).strip()
    # List<X> → array
    m = re.match(r'(?:List|Set|Collection)<(.+)>$', inner)
    if m:
        item_schema = _resolve_type(m.group(1).strip(), class_content, schemas, get_dto_schema)
        return {"type": "array", "items": item_schema}
    return _resolve_type(inner, class_content, schemas, get_dto_schema)

def _resolve_type(
    type_name: str,
    class_content: dict[str, str],
    schemas: dict,
    get_dto_schema,
) -> dict:
    if type_name in ("void", "Void", "?"):
        return {}
    if type_name in TYPE_MAP:
        t, fmt = TYPE_MAP[type_name]
        s: dict = {"type": t}
        if fmt:
            s["format"] = fmt
        return s
    if type_name in class_content:
        return get_dto_schema(type_name)
    return {}

def _ensure_wrapper_schemas(schemas: dict) -> None:
    """Add SuccessResponse and ErrorResponse schemas if not already present."""
    if "SuccessResponse" not in schemas:
        schemas["SuccessResponse"] = {
            "type": "object",
            "properties": {
                "data":      {"description": "Response payload"},
                "timestamp": {"type": "string", "format": "date-time"},
            },
        }
    if "ErrorResponse" not in schemas:
        schemas["ErrorResponse"] = {
            "type": "object",
            "properties": {
                "message":   {"type": "string"},
                "timestamp": {"type": "string", "format": "date-time"},
            },
        }
    if "ValidationErrorResponse" not in schemas:
        schemas["ValidationErrorResponse"] = {
            "type": "object",
            "properties": {
                "errors":    {"type": "object", "additionalProperties": {"type": "string"}},
                "timestamp": {"type": "string", "format": "date-time"},
            },
        }

# ─── PARSERS: FASTAPI ─────────────────────────────────────────────────────────

def parse_fastapi(files: list[str], fetcher) -> tuple[list[dict], dict]:
    endpoints: list[dict] = []
    schemas: dict = {}
    py_files = [f for f in files if f.endswith(".py")]
    for path in py_files:
        content = fetcher(path)
        for m in re.finditer(
            r'@(?:app|router)\.(?P<verb>get|post|put|delete|patch)\s*\(\s*"(?P<path>[^"]+)"',
            content,
        ):
            verb = m.group("verb").upper()
            ep_path = m.group("path")
            func_m = re.search(r'\ndef\s+(\w+)\s*\(([^)]*)\)', content[m.end():m.end()+500])
            op_id = func_m.group(1) if func_m else re.sub(r"[^a-z0-9]", "_", ep_path.lower())
            endpoints.append({
                "verb": verb,
                "path": ep_path,
                "operation_id": op_id,
                "path_params": [
                    {"name": p, "in": "path", "required": True, "schema": {"type": "string"}}
                    for p in re.findall(r'\{(\w+)\}', ep_path)
                ],
                "query_params": [],
                "request_body_ref": None,
                "response_schema": {},
                "tags": [_path_to_tag(ep_path)],
            })
    return endpoints, schemas

# ─── PARSERS: EXPRESS / NODE ──────────────────────────────────────────────────

def parse_express(files: list[str], fetcher) -> tuple[list[dict], dict]:
    endpoints: list[dict] = []
    schemas: dict = {}
    js_files = [f for f in files if f.endswith((".js", ".ts")) and "test" not in f.lower()]
    for path in js_files:
        content = fetcher(path)
        for m in re.finditer(
            r'(?:app|router)\.(?P<verb>get|post|put|delete|patch)\s*\(\s*[\'"](?P<path>[^\'"]+)[\'"]',
            content,
        ):
            verb = m.group("verb").upper()
            ep_path = m.group("path")
            # Convert Express :param → {param}
            ep_path = re.sub(r":(\w+)", r"{\1}", ep_path)
            endpoints.append({
                "verb": verb,
                "path": ep_path,
                "operation_id": f"{verb.lower()}{_path_to_tag(ep_path).title()}",
                "path_params": [
                    {"name": p, "in": "path", "required": True, "schema": {"type": "string"}}
                    for p in re.findall(r'\{(\w+)\}', ep_path)
                ],
                "query_params": [],
                "request_body_ref": None,
                "response_schema": {},
                "tags": [_path_to_tag(ep_path)],
            })
    return endpoints, schemas

# ─── PARSERS: FLASK ───────────────────────────────────────────────────────────

def parse_flask(files: list[str], fetcher) -> tuple[list[dict], dict]:
    endpoints: list[dict] = []
    schemas: dict = {}
    for path in [f for f in files if f.endswith(".py")]:
        content = fetcher(path)
        for m in re.finditer(
            r'@(?:app|bp)\.route\s*\(\s*[\'"](?P<path>[^\'"]+)[\'"]'
            r'(?:[^)]*methods\s*=\s*\[(?P<methods>[^\]]+)\])?',
            content,
        ):
            ep_path = m.group("path")
            methods_raw = m.group("methods") or "'GET'"
            # Convert Flask <type:name> → {name}
            ep_path = re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", ep_path)
            for verb in re.findall(r"'(\w+)'", methods_raw):
                endpoints.append({
                    "verb": verb.upper(),
                    "path": ep_path,
                    "operation_id": f"{verb.lower()}_{re.sub(r'[^a-z0-9]', '_', ep_path.lower()).strip('_')}",
                    "path_params": [
                        {"name": p, "in": "path", "required": True, "schema": {"type": "string"}}
                        for p in re.findall(r'\{(\w+)\}', ep_path)
                    ],
                    "query_params": [],
                    "request_body_ref": None,
                    "response_schema": {},
                    "tags": [_path_to_tag(ep_path)],
                })
    return endpoints, schemas

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _path_to_tag(path: str) -> str:
    """Derive a tag name from an endpoint path, e.g. /api/tasks/{id} → Tasks."""
    segs = [s for s in path.split("/") if s and not s.startswith("{")]
    name = segs[-1] if segs else "Resource"
    return name.rstrip("s").title().replace("-", "").replace("_", "") + "s"

def _op_id(verb: str, path: str, declared: str | None = None) -> str:
    if declared:
        return declared
    parts = [verb.lower()] + [p for p in path.split("/") if p and not p.startswith("{")]
    return re.sub(r"[^a-zA-Z0-9]", "", parts[0] + "".join(p.title() for p in parts[1:]))

# ─── STANDARD RESPONSES ───────────────────────────────────────────────────────

def _standard_responses(verb: str, response_schema: dict) -> dict:
    """
    Build the responses dict for an operation.
    200/201 success + 400/401/500 always included (matches jira-to-openapi convention).
    """
    success_code = "201" if verb == "POST" else "200"
    responses: dict = {
        success_code: {
            "description": "Created" if verb == "POST" else "Successful response",
            "content": {"application/json": {
                "schema": response_schema or {"$ref": "#/components/schemas/SuccessResponse"},
            }} if response_schema else {},
        }
    }
    # Omit content key if empty
    if not responses[success_code].get("content"):
        del responses[success_code]["content"]

    if verb in ("PUT", "PATCH", "POST"):
        responses["400"] = {"description": "Bad request — validation error"}
        responses["409"] = {"description": "Conflict — resource already exists"}
    responses.setdefault("400", {"description": "Bad request"})
    responses["401"] = {"description": "Unauthorized"}
    if verb in ("GET", "PUT", "PATCH", "DELETE"):
        responses["404"] = {"description": "Resource not found"}
    responses["500"] = {"description": "Internal server error"}
    return responses

# ─── SPEC BUILDER ─────────────────────────────────────────────────────────────

def build_spec(
    repo_url: str,
    owner: str,
    repo_name: str,
    description: str,
    endpoints: list[dict],
    schemas: dict,
    base_url: str,
) -> dict:
    """Assemble the OpenAPI 3.0.3 document."""
    paths: dict = {}
    tags_seen: set[str] = set()

    for ep in endpoints:
        path = ep["path"]
        verb = ep["verb"].lower()
        paths.setdefault(path, {})

        parameters: list[dict] = ep.get("path_params", []) + ep.get("query_params", [])

        # Standard Authorization header (consistent with jira-to-openapi BearerAuth)
        operation: dict = {
            "operationId": _op_id(ep["verb"], path, ep.get("operation_id")),
            "tags":        ep.get("tags", [_path_to_tag(path)]),
            "summary":     f"{ep['verb']} {path}",
            "responses":   _standard_responses(ep["verb"], ep.get("response_schema") or {}),
        }
        if parameters:
            operation["parameters"] = parameters

        rb_ref = ep.get("request_body_ref")
        if rb_ref:
            operation["requestBody"] = {
                "required": True,
                "content": {"application/json": {"schema": rb_ref}},
            }

        for tag in ep.get("tags", []):
            tags_seen.add(tag)

        paths[path][verb] = operation

    scanned_at = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "openapi": "3.0.3",
        "info": {
            "title":          f"{repo_name.replace('-', ' ').replace('_', ' ').title()} API",
            "description":    description or f"API specification generated from {repo_url}",
            "version":        "1.0.0",
            "x-source-repo":  repo_url,
            "x-scanned-at":   scanned_at,
        },
        "servers": [
            {"url": base_url,                    "description": "Production"},
            {"url": "http://localhost:8080",      "description": "Local development"},
        ],
        "paths":  paths,
        "components": {
            "schemas": schemas,
            "securitySchemes": {
                "BearerAuth": {
                    "type":         "http",
                    "scheme":       "bearer",
                    "bearerFormat": "JWT",
                },
            },
        },
        "security": [{"BearerAuth": []}],
        "tags": [{"name": t, "description": f"Operations on {t} resources"} for t in sorted(tags_seen)],
    }

# ─── UPLOAD TO REPO ──────────────────────────────────────────────────────────

def upload_spec(
    content: str,
    target_repo_url: str,
    file_path_in_repo: str,
    commit_message: str,
    branch: str,
) -> None:
    """Create or update a file in a GitHub repo via the Contents API."""
    if not GITHUB_TOKEN:
        print("⚠  GITHUB_TOKEN is not set — cannot upload to target repo.", file=sys.stderr)
        print("   Set GITHUB_TOKEN with write access to the target repo and retry.", file=sys.stderr)
        return

    t_owner, t_repo = parse_github_url(target_repo_url)
    url = f"{GITHUB_API}/repos/{t_owner}/{t_repo}/contents/{file_path_in_repo}"

    # Check if file already exists (need its SHA to update)
    existing_sha: str | None = None
    r = SESSION.get(f"{url}?ref={branch}")
    if r.status_code == 200:
        existing_sha = r.json().get("sha")
    elif r.status_code not in (404,):
        r.raise_for_status()

    body: dict = {
        "message": commit_message,
        "content": base64.b64encode(content.encode()).decode(),
        "branch":  branch,
    }
    if existing_sha:
        body["sha"] = existing_sha

    r = SESSION.put(url, json=body)
    if r.status_code in (200, 201):
        action = "Updated" if existing_sha else "Created"
        html_url = r.json().get("content", {}).get("html_url", "")
        print(f"✓ {action} {file_path_in_repo} in {t_owner}/{t_repo}@{branch}", file=sys.stderr)
        if html_url:
            print(f"  {html_url}", file=sys.stderr)
    else:
        print(f"⛔  Upload failed ({r.status_code}): {r.text}", file=sys.stderr)


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate an OpenAPI 3.0 spec by scanning a GitHub repository or a local directory. "
            "Pass either a GitHub URL (https://github.com/owner/repo) or a local path (/path/to/repo or .)."
        )
    )
    parser.add_argument(
        "source",
        help=(
            "GitHub repo URL (https://github.com/owner/repo) "
            "OR local directory path (/path/to/repo or .)"
        ),
    )
    parser.add_argument("--branch", "-b", default="",
                        help="Remote: branch to scan (default: repo default branch). "
                             "Local: displayed in spec metadata only.")
    parser.add_argument("--base-url", default="",
                        help="Override the production server base URL in the spec")
    parser.add_argument("--output", "-o",
                        help="Local output file path (default: <repo-name>-openapi.yaml)")
    parser.add_argument("--format", "-f", choices=["yaml", "json"], default="yaml")
    # Upload options
    parser.add_argument("--upload-to",      metavar="REPO_URL",
                        help="GitHub repo URL to upload the generated spec into "
                             "(e.g. https://github.com/owner/specs-repo)")
    parser.add_argument("--upload-path",    metavar="PATH",
                        help="Path inside the target repo (default: specs/<filename>)")
    parser.add_argument("--upload-branch",  metavar="BRANCH", default="main",
                        help="Branch in the target repo to commit to (default: main)")
    parser.add_argument("--upload-message", metavar="MSG",
                        help="Commit message for the upload (default: auto-generated)")
    args = parser.parse_args()

    source = args.source

    # ── Determine if source is a local path or a remote GitHub URL ──────────
    is_local = not source.startswith("http") and not source.startswith("git@")
    if is_local:
        local_root = Path(source).expanduser().resolve()
        if not local_root.is_dir():
            sys.exit(f"⛔  Local path does not exist or is not a directory: {local_root}")

        repo_name    = local_root.name
        source_label = str(local_root)
        is_git       = _is_git_repo(local_root)

        # Resolve branch: explicit flag > current checkout > "local" (non-git)
        current_branch = local_git_branch(local_root) if is_git else ""
        branch         = args.branch or current_branch or "local"

        print(f"Scanning local path: {local_root} …", file=sys.stderr)
        print(f"  Branch            : {branch}", file=sys.stderr)

        if is_git and args.branch and args.branch != current_branch:
            # Read files from the specified branch via git without checking it out
            git_files = local_git_tree(local_root, branch)
            if not git_files:
                sys.exit(
                    f"⛔  Branch {branch!r} not found in local repo, "
                    f"or no files returned. Available branches:\n"
                    + (_git(local_root, "branch", "--list") or "  (run git branch to check)")
                )
            print(f"  Reading from git branch (no checkout)", file=sys.stderr)
            file_paths = git_files
            fetcher    = local_git_fetcher(local_root, branch)
        elif is_git:
            # Use git ls-tree for the current branch (avoids noise dirs via .gitignore)
            git_files = local_git_tree(local_root, branch)
            if git_files:
                file_paths = git_files
                fetcher    = local_git_fetcher(local_root, branch)
            else:
                # Fall back to filesystem walk for untracked/new repos
                file_paths = local_tree(local_root)
                fetcher    = local_fetcher(local_root)
        else:
            # Not a git repo — walk the filesystem
            file_paths = local_tree(local_root)
            fetcher    = local_fetcher(local_root)

        # Description from first non-heading line of README
        description = ""
        readme_text = fetcher("README.md") or fetcher("readme.md")
        for line in readme_text.splitlines():
            if line.strip() and not line.startswith("#"):
                description = line.strip()
                break

        base_url = args.base_url or local_readme_base_url(local_root, fetcher) or "http://localhost:8080"

    else:
        owner, repo_name = parse_github_url(source)
        branch      = args.branch or default_branch(owner, repo_name)
        description = repo_description(owner, repo_name)
        source_label = source

        print(f"Scanning {owner}/{repo_name}@{branch} …", file=sys.stderr)

        tree = fetch_tree(owner, repo_name, branch)
        file_paths = [f["path"] for f in tree]

        def fetcher(path: str) -> str:
            return fetch_file(owner, repo_name, path, branch)

        base_url = args.base_url
        if not base_url:
            readme = fetcher("README.md") or fetcher("readme.md")
            m = re.search(r'https?://[^\s)\"\']+run\.app', readme)
            base_url = m.group(0).rstrip("/") if m else "https://api.example.com/v1"

    # ── Framework detection and parsing ─────────────────────────────────────
    framework = detect_framework(file_paths, fetcher)
    print(f"  Framework detected: {framework}", file=sys.stderr)

    if framework == "springboot":
        endpoints, schemas = parse_springboot(file_paths, fetcher)
    elif framework == "fastapi":
        endpoints, schemas = parse_fastapi(file_paths, fetcher)
    elif framework == "flask":
        endpoints, schemas = parse_flask(file_paths, fetcher)
    elif framework in ("express", "fastify", "nestjs"):
        endpoints, schemas = parse_express(file_paths, fetcher)
    else:
        print("  ⚠  Framework not recognised — attempting generic scan.", file=sys.stderr)
        endpoints, schemas = [], {}
        for fn in [
            lambda: parse_springboot(file_paths, fetcher),
            lambda: parse_fastapi(file_paths, fetcher),
            lambda: parse_express(file_paths, fetcher),
            lambda: parse_flask(file_paths, fetcher),
        ]:
            eps, schs = fn()
            if eps:
                endpoints, schemas = eps, schs
                break

    print(f"  Endpoints found : {len(endpoints)}", file=sys.stderr)
    for ep in endpoints:
        print(f"    {ep['verb']:6s} {ep['path']}", file=sys.stderr)

    # ── Build and serialise spec ─────────────────────────────────────────────
    spec = build_spec(source_label, repo_name, repo_name, description, endpoints, schemas, base_url)

    ext          = "json" if args.format == "json" else "yaml"
    out_path_str = args.output or f"{repo_name}-openapi.{ext}"

    if args.format == "json" or yaml is None:
        content = json.dumps(spec, indent=2)
    else:
        content = yaml.dump(spec, default_flow_style=False, sort_keys=False, allow_unicode=True)

    with open(out_path_str, "w", encoding="utf-8") as fh:
        fh.write(content)

    print(f"\n✓ Spec saved: {out_path_str}", file=sys.stderr)
    print(f"  Validate : https://editor.swagger.io/\n", file=sys.stderr)

    # ── Optional upload ──────────────────────────────────────────────────────
    if args.upload_to:
        upload_spec(
            content=content,
            target_repo_url=args.upload_to,
            file_path_in_repo=args.upload_path or f"specs/{out_path_str.split('/')[-1]}",
            commit_message=args.upload_message
                or f"chore: add OpenAPI spec scanned from {source_label}",
            branch=args.upload_branch or "main",
        )

    print(content)


if __name__ == "__main__":
    main()
