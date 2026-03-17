#!/usr/bin/env python3
"""
Validates an OpenAPI 3.0 YAML file for structural correctness.
Prints errors/warnings to stdout. Exit code 0 = valid, 1 = errors found.

Usage: python3 validate_openapi.py <openapi.yaml>

Checks performed (no external dependencies required):
  - Valid YAML syntax
  - Required top-level fields: openapi, info, paths
  - openapi version starts with "3."
  - info has title and version
  - All $ref values point to defined components
  - Path parameters declared in path string are present in parameters list
  - HTTP status codes are strings, not integers
  - Each operation has at least one response
  - No duplicate operationIds
"""

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("WARNING: PyYAML not installed. Running minimal checks only.")
    print("Install with: pip install pyyaml")
    content = Path(sys.argv[1]).read_text()
    if "openapi:" not in content:
        print("ERROR: Missing 'openapi:' field")
        sys.exit(1)
    if "paths:" not in content:
        print("ERROR: Missing 'paths:' field")
        sys.exit(1)
    print("OK (minimal checks only - install pyyaml for full validation)")
    sys.exit(0)


def validate(path: str):
    errors = []
    warnings = []

    try:
        with open(path) as f:
            spec = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return [f"YAML parse error: {e}"], []

    if not isinstance(spec, dict):
        return ["Root document is not a YAML mapping"], []

    # Required top-level fields
    for field in ["openapi", "info", "paths"]:
        if field not in spec:
            errors.append(f"Missing required top-level field: '{field}'")

    if "openapi" in spec:
        ver = str(spec["openapi"])
        if not ver.startswith("3."):
            errors.append(f"openapi version should start with '3.', got '{ver}'")

    if "info" in spec and isinstance(spec["info"], dict):
        for field in ["title", "version"]:
            if field not in spec["info"]:
                errors.append(f"info.{field} is required")

    # Collect defined $ref targets
    defined_schemas = set()
    for section, items in (spec.get("components") or {}).items():
        if isinstance(items, dict):
            for name in items:
                defined_schemas.add(f"#/components/{section}/{name}")

    # Walk paths
    paths = spec.get("paths") or {}
    operation_ids = []
    METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}

    def collect_refs(obj, refs):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "$ref" and isinstance(v, str):
                    refs.add(v)
                else:
                    collect_refs(v, refs)
        elif isinstance(obj, list):
            for item in obj:
                collect_refs(item, refs)

    all_refs: set[str] = set()

    for path_str, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        path_params_in_url = set(re.findall(r"\{(\w+)\}", path_str))

        for method, operation in path_item.items():
            if method not in METHODS:
                continue
            if not isinstance(operation, dict):
                continue

            loc = f"{method.upper()} {path_str}"

            if "responses" not in operation:
                errors.append(f"{loc}: missing 'responses'")

            for code in (operation.get("responses") or {}):
                if isinstance(code, int):
                    errors.append(f"{loc}: status code {code} must be a string e.g. \"{code}\"")

            op_id = operation.get("operationId")
            if op_id:
                if op_id in operation_ids:
                    errors.append(f"Duplicate operationId: '{op_id}'")
                else:
                    operation_ids.append(op_id)

            params_declared = set()
            for p in (operation.get("parameters") or []) + (path_item.get("parameters") or []):
                if isinstance(p, dict) and p.get("in") == "path":
                    params_declared.add(p.get("name", ""))

            for pname in path_params_in_url:
                if pname not in params_declared:
                    warnings.append(f"{loc}: path param '{{{pname}}}' not declared in parameters")

            collect_refs(operation, all_refs)

    # Check $refs
    for ref in sorted(all_refs):
        if ref.startswith("#/") and ref not in defined_schemas:
            errors.append(f"$ref '{ref}' not found in components")

    return errors, warnings


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 validate_openapi.py <openapi.yaml>", file=sys.stderr)
        sys.exit(1)

    result = validate(sys.argv[1])
    if isinstance(result, tuple):
        errors, warnings = result
    else:
        errors, warnings = result, []

    for w in warnings:
        print(f"WARNING: {w}")
    for e in errors:
        print(f"ERROR: {e}")

    if errors:
        print(f"\n{len(errors)} error(s) found. Fix before publishing.")
        sys.exit(1)
    else:
        print(f"Valid ✓" + (f" ({len(warnings)} warning(s))" if warnings else ""))
        sys.exit(0)
