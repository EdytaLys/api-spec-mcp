#!/usr/bin/env python3
"""
publish_spec.py
===============
Checks that a JIRA story has an approved subtask (status=Done + label
api-spec-approved), extracts the OpenAPI YAML embedded in that subtask,
merges it into the existing spec in a GitHub repo, bumps the version, and
opens a Pull Request.

Usage:
    python publish_spec.py SCRUM-42
    python publish_spec.py SCRUM-42 --dry-run
    python publish_spec.py SCRUM-42 --repo owner/repo
    python publish_spec.py SCRUM-42 --spec-path specs/openapi.yaml
    python publish_spec.py SCRUM-42 --base-branch develop

Requirements: pip install requests pyyaml
"""

import os, sys, re, json, argparse, base64, textwrap
from pathlib import Path
from copy import deepcopy

# ─── Dynamic import of generate_spec helpers ─────────────────────────────────
_GEN_SPEC_PATH = (
    Path(__file__).parent.parent.parent   # skills/
    / "jira-to-openapi" / "scripts" / "generate_spec.py"
)

if not _GEN_SPEC_PATH.exists():
    sys.exit(
        f"⛔  Cannot find generate_spec.py at {_GEN_SPEC_PATH}\n"
        "    Make sure both skills live in the same skills/ directory."
    )

import importlib.util as _ilu
_gs_spec = _ilu.spec_from_file_location("generate_spec", _GEN_SPEC_PATH)
_gs = _ilu.module_from_spec(_gs_spec)
_gs_spec.loader.exec_module(_gs)

# Re-export helpers we need
CONFIG             = _gs.CONFIG
fetch_issue        = _gs.fetch_issue
compare_operations = _gs.compare_operations
merge_spec         = _gs.merge_spec

try:
    import yaml
except ImportError:
    yaml = None

try:
    import requests
except ImportError:
    sys.exit("Missing dependency: pip install requests pyyaml")

# ─── Constants ────────────────────────────────────────────────────────────────
APPROVED_LABEL    = "api-spec-approved"
APPROVED_STATUSES = {"done", "closed", "resolved", "complete", "completed"}
DEFAULT_REPO      = "EdytaLys/api-spec-task-manager"
DEFAULT_SPEC_PATH = "specs/swagger.yaml"
DEFAULT_BASE      = "main"

# ─── JIRA helpers ─────────────────────────────────────────────────────────────

def _is_approved(issue: dict) -> bool:
    """Return True if this JIRA issue is status=Done AND labelled api-spec-approved."""
    fields = issue.get("fields", {})
    status = (fields.get("status") or {}).get("name", "").strip().lower()
    labels = [l.strip() for l in (fields.get("labels") or [])]
    return status in APPROVED_STATUSES and APPROVED_LABEL in labels


def find_approved_subtask(parent_key: str) -> dict | None:
    """
    Fetch the parent issue and scan its subtasks + issuelinks for an issue
    that is status=Done and labelled api-spec-approved.

    Returns the full issue dict of the first matching subtask, or None.
    """
    parent = fetch_issue(parent_key)
    fields = parent.get("fields", {})

    candidates: list[dict] = []

    # Direct subtasks
    for sub in fields.get("subtasks", []):
        candidates.append(sub)

    # Issue links (inward + outward)
    for link in fields.get("issuelinks", []):
        for direction in ("inwardIssue", "outwardIssue"):
            linked = link.get(direction)
            if linked:
                candidates.append(linked)

    for candidate in candidates:
        key = candidate.get("key", "")
        # Fetch full issue to get labels + complete status
        try:
            full = fetch_issue(key)
        except SystemExit:
            continue
        if _is_approved(full):
            return full

    return None


# ─── Spec extraction from subtask description ────────────────────────────────

def _adf_texts(node: dict) -> list[str]:
    """Recursively collect all text leaf values from an ADF node."""
    if node.get("type") == "text":
        return [node.get("text", "")]
    return [t for child in node.get("content", []) for t in _adf_texts(child)]


def extract_spec_from_subtask(subtask: dict) -> dict | None:
    """
    Find the OpenAPI YAML code block embedded in the subtask description
    (written by generate_spec.py under the 'Generated OpenAPI spec' heading).

    Walks the ADF document, finds the first codeBlock node whose language
    is 'yaml' (or whose content parses as a valid OpenAPI dict), and returns
    the parsed spec dict.

    Returns None if no valid spec is found.
    """
    desc_adf = subtask.get("fields", {}).get("description")
    if not desc_adf:
        return None

    def _find_code_blocks(node: dict) -> list[str]:
        """Return text content of every codeBlock node in the ADF tree."""
        results = []
        if node.get("type") == "codeBlock":
            results.append("".join(_adf_texts(node)))
        for child in node.get("content", []):
            results.extend(_find_code_blocks(child))
        return results

    for block_text in _find_code_blocks(desc_adf):
        block_text = block_text.strip()
        if not block_text:
            continue
        # Try YAML first, then JSON
        parsed = None
        if yaml is not None:
            try:
                parsed = yaml.safe_load(block_text)
            except Exception:
                pass
        if not isinstance(parsed, dict):
            try:
                parsed = json.loads(block_text)
            except Exception:
                pass
        # Validate it looks like an OpenAPI doc
        if isinstance(parsed, dict) and "openapi" in parsed and "paths" in parsed:
            return parsed

    return None


# ─── Version bumping ──────────────────────────────────────────────────────────

def bump_version(current: str, has_breaking: bool, has_additive: bool) -> str:
    """
    Bump a semver string.
    Breaking  → major bump (x.0.0)
    Additive  → minor bump (x.y.0)
    None      → patch bump (x.y.z+1)
    """
    parts = [int(p) for p in re.split(r"[.\-]", current)[:3]] + [0, 0, 0]
    major, minor, patch = parts[0], parts[1], parts[2]
    if has_breaking:
        return f"{major + 1}.0.0"
    if has_additive:
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


# ─── GitHub API helpers ───────────────────────────────────────────────────────

def _gh_session() -> requests.Session:
    s = requests.Session()
    token = CONFIG.get("github_token") or os.environ.get("GITHUB_TOKEN", "")
    if not token:
        sys.exit("⛔  GITHUB_TOKEN is not set. Export it and re-run.")
    s.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    return s


def gh_get_ref_sha(repo: str, ref: str = "main") -> str:
    """Return the commit SHA of the tip of `ref` in `repo`."""
    url = f"https://api.github.com/repos/{repo}/git/ref/heads/{ref}"
    r = _gh_session().get(url)
    if r.status_code == 404:
        sys.exit(f"⛔  GitHub ref 'heads/{ref}' not found in {repo}.")
    r.raise_for_status()
    return r.json()["object"]["sha"]


def gh_get_file(repo: str, path: str, ref: str = "main") -> tuple[str, str]:
    """
    Fetch a file from `repo` at `ref`.
    Returns (decoded_content_str, blob_sha).
    """
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={ref}"
    r = _gh_session().get(url)
    if r.status_code == 404:
        sys.exit(f"⛔  File '{path}' not found in {repo} on branch '{ref}'.")
    r.raise_for_status()
    data = r.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    return content, data["sha"]


def gh_create_branch(repo: str, branch: str, from_sha: str) -> None:
    """Create a new branch in `repo` pointing at `from_sha`."""
    url = f"https://api.github.com/repos/{repo}/git/refs"
    payload = {"ref": f"refs/heads/{branch}", "sha": from_sha}
    r = _gh_session().post(url, json=payload)
    if r.status_code == 422:
        # Branch already exists — that's OK, we'll push to it
        print(f"  ⚠  Branch '{branch}' already exists — will update it.", file=sys.stderr)
        return
    r.raise_for_status()


def gh_update_file(
    repo: str,
    path: str,
    content: str,
    message: str,
    blob_sha: str,
    branch: str,
) -> None:
    """Commit an updated file to `branch` in `repo`."""
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    payload = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "sha":     blob_sha,
        "branch":  branch,
    }
    r = _gh_session().put(url, json=payload)
    r.raise_for_status()


def gh_create_pr(
    repo: str,
    branch: str,
    title: str,
    body: str,
    base: str = "main",
) -> str:
    """Open a pull request. Returns the HTML URL of the new PR."""
    url = f"https://api.github.com/repos/{repo}/pulls"
    payload = {
        "title": title,
        "head":  branch,
        "base":  base,
        "body":  body,
    }
    r = _gh_session().post(url, json=payload)
    if r.status_code == 422:
        data = r.json()
        # PR may already exist
        errors = data.get("errors", [])
        for err in errors:
            if "already exists" in str(err.get("message", "")):
                print("  ⚠  A PR for this branch already exists.", file=sys.stderr)
                # Try to find and return its URL
                list_url = f"https://api.github.com/repos/{repo}/pulls?head={repo.split('/')[0]}:{branch}&state=open"
                lr = _gh_session().get(list_url)
                if lr.ok and lr.json():
                    return lr.json()[0]["html_url"]
        sys.exit(f"⛔  Failed to create PR: {r.text}")
    r.raise_for_status()
    return r.json()["html_url"]


# ─── Rendering ────────────────────────────────────────────────────────────────

def _render(spec: dict, fmt: str = "yaml") -> str:
    if fmt == "json" or yaml is None:
        return json.dumps(spec, indent=2)
    return yaml.dump(spec, default_flow_style=False, sort_keys=False, allow_unicode=True)


# ─── Change report (plain text) ───────────────────────────────────────────────

def _build_change_report(key: str, summary: str, diffs: list[dict], new_version: str) -> str:
    W = 72
    lines = [
        "=" * W,
        f"  OpenAPI Change Report — {key}",
        f"  {summary}",
        "=" * W,
        "",
    ]

    for d in diffs:
        method = d["method"]
        path   = d["path"]
        status = d["status"]

        lines.append(f"  ┌─ {method} {path}")
        if status == "new":
            lines.append("  │  ✅ NEW endpoint — this is an additive change.")
            lines.append("  │     No existing callers will be affected.")
        elif status == "unchanged":
            lines.append("  │  ✔  UNCHANGED — no diff detected.")
        else:
            for msg in d.get("breaking", []):
                lines.append(f"  │  ⚠️  BREAKING: {msg}")
            for msg in d.get("additive", []):
                lines.append(f"  │  ✅ ADDITIVE: {msg}")
        lines.append("  └" + "─" * (W - 4))
        lines.append("")

    # Overall verdict
    has_breaking = any(d.get("breaking") for d in diffs)
    has_additive = any(d.get("additive") or d["status"] == "new" for d in diffs)
    lines += [
        "-" * W,
        "  OVERALL VERDICT",
        "-" * W,
    ]
    if has_breaking:
        lines.append("  ⚠️  Breaking changes detected. Major version bump applied.")
    elif has_additive:
        lines.append("  ✅ All changes are ADDITIVE (backward compatible).")
        lines.append("     Minor version bump applied.")
    else:
        lines.append("  ✔  No functional changes. Patch version bump applied.")
    lines.append(f"  Version → {new_version}")

    return "\n".join(lines)


# ─── PR body builder ──────────────────────────────────────────────────────────

def _build_pr_body(
    key: str,
    summary: str,
    approved_subtask_key: str,
    diffs: list[dict],
    new_version: str,
    endpoint_yaml: str,
) -> str:
    has_breaking = any(d.get("breaking") for d in diffs)
    has_additive = any(d.get("additive") or d["status"] == "new" for d in diffs)

    verdict = (
        "⚠️ **Breaking changes** — major version bump"
        if has_breaking else
        "✅ **Additive changes** — minor version bump"
        if has_additive else
        "✔ No functional changes — patch version bump"
    )

    changes_md = []
    for d in diffs:
        method, path, status = d["method"], d["path"], d["status"]
        if status == "new":
            changes_md.append(f"- `{method} {path}` — ✅ new endpoint")
        elif status == "unchanged":
            changes_md.append(f"- `{method} {path}` — ✔ unchanged")
        else:
            for msg in d.get("breaking", []):
                changes_md.append(f"- `{method} {path}` — ⚠️ {msg}")
            for msg in d.get("additive", []):
                changes_md.append(f"- `{method} {path}` — ✅ {msg}")

    body_parts = [
        f"## [{key}] {summary}",
        "",
        f"**Approved subtask:** {approved_subtask_key}  ",
        f"**New version:** `{new_version}`  ",
        f"**Verdict:** {verdict}",
        "",
        "## Changes",
        "",
        "\n".join(changes_md) if changes_md else "_No changes detected._",
        "",
        "## Endpoint spec (paste into [editor.swagger.io](https://editor.swagger.io/))",
        "",
        "```yaml",
        endpoint_yaml.rstrip(),
        "```",
        "",
        "---",
        "_Generated by the spec-publisher Claude skill._",
    ]
    return "\n".join(body_parts)


# ─── Branch name helper ───────────────────────────────────────────────────────

def _branch_name(key: str, path: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")
    return f"api-spec/{key.lower()}-{slug}"


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish an approved JIRA story spec to GitHub as a PR."
    )
    parser.add_argument("issue_key", metavar="ISSUE_KEY",
                        help="JIRA parent story key, e.g. SCRUM-42")
    parser.add_argument("--repo", default=DEFAULT_REPO,
                        help=f"GitHub repo owner/name (default: {DEFAULT_REPO})")
    parser.add_argument("--spec-path", default=DEFAULT_SPEC_PATH,
                        help=f"Path to spec file in repo (default: {DEFAULT_SPEC_PATH})")
    parser.add_argument("--base-branch", default=DEFAULT_BASE,
                        help=f"Base branch for the PR (default: {DEFAULT_BASE})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print merged spec and report without pushing to GitHub")
    args = parser.parse_args()

    key = args.issue_key.upper()

    # ── 1. Find approved subtask ───────────────────────────────────────────────
    print(f"  Looking for approved subtask on {key}…", file=sys.stderr)
    approved = find_approved_subtask(key)
    if not approved:
        sys.exit(
            f"⛔  No approved subtask found for {key}.\n"
            f"    A subtask must have status in {APPROVED_STATUSES} "
            f"and label '{APPROVED_LABEL}'."
        )
    approved_key = approved["key"]
    print(f"✓ Found approved subtask: {approved_key}", file=sys.stderr)

    # ── 2. Extract OpenAPI spec from approved subtask ─────────────────────────
    print(f"  Extracting spec from subtask {approved_key}…", file=sys.stderr)
    new_spec = extract_spec_from_subtask(approved)

    if new_spec is None:
        sys.exit(
            f"⛔  Could not find an OpenAPI YAML code block in {approved_key}.\n"
            "    Make sure the subtask was generated by the jira-to-openapi skill\n"
            "    (it should contain a 'Generated OpenAPI spec' section)."
        )

    print(f"✓ Spec extracted from {approved_key}", file=sys.stderr)

    # Derive summary from parent story for PR title / commit message
    parent_issue = fetch_issue(key)
    summary = parent_issue.get("fields", {}).get("summary", key)

    # Collect endpoints from the extracted spec paths (source of truth)
    endpoints = [
        (method.upper(), path)
        for path, methods in new_spec.get("paths", {}).items()
        for method in methods
        if method.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
    ]
    if not endpoints:
        sys.exit(f"⛔  Extracted spec from {approved_key} has no paths.")

    # ── 3. Fetch existing spec from GitHub ────────────────────────────────────
    print(f"  Fetching existing spec: {args.spec_path} @ {args.base_branch}", file=sys.stderr)
    raw_content, blob_sha = gh_get_file(args.repo, args.spec_path, args.base_branch)

    if yaml is not None:
        existing_spec = yaml.safe_load(raw_content)
    else:
        existing_spec = json.loads(raw_content)

    if not isinstance(existing_spec, dict):
        sys.exit(f"⛔  Could not parse {args.spec_path} as a YAML/JSON dict.")

    # ── 4. Diff ───────────────────────────────────────────────────────────────
    diffs = []
    for ep_method, ep_path in endpoints:
        diff = compare_operations(existing_spec, new_spec, ep_method, ep_path)
        diffs.append(diff)
        status = diff["status"]
        breaking_count = len(diff.get("breaking", []))
        additive_count = len(diff.get("additive", []))
        print(
            f"  Diff: {ep_method} {ep_path} — {status}"
            + (f"  ({breaking_count} breaking, {additive_count} additive)" if status == "modified" else ""),
            file=sys.stderr,
        )

    # ── 5. Merge + bump version ───────────────────────────────────────────────
    merged_spec = merge_spec(
        existing_spec,
        new_spec.get("paths", {}),
        new_spec.get("components", {}),
    )

    has_breaking = any(d.get("breaking") for d in diffs)
    has_additive = any(d.get("additive") or d["status"] == "new" for d in diffs)

    current_version = existing_spec.get("info", {}).get("version", "1.0.0")
    new_version = bump_version(current_version, has_breaking, has_additive)
    merged_spec.setdefault("info", {})["version"] = new_version
    print(f"  Version bump: {current_version} → {new_version}", file=sys.stderr)

    # ── 6. Render ─────────────────────────────────────────────────────────────
    merged_yaml    = _render(merged_spec, "yaml")
    endpoint_yaml  = _render(new_spec,    "yaml")
    change_report  = _build_change_report(key, summary, diffs, new_version)

    print("\n" + change_report, file=sys.stderr)

    if args.dry_run:
        print("\n" + "─" * 72, file=sys.stderr)
        print("  DRY RUN — merged spec (would be committed to GitHub)", file=sys.stderr)
        print("─" * 72 + "\n", file=sys.stderr)
        print(merged_yaml)
        print("\n⚠️  Dry run — no branch or PR was created.", file=sys.stderr)
        return

    # ── 7. Create branch + commit ─────────────────────────────────────────────
    _, path = endpoints[0]
    branch = _branch_name(key, path)
    print(f"  Creating branch: {branch}", file=sys.stderr)
    base_sha = gh_get_ref_sha(args.repo, args.base_branch)
    gh_create_branch(args.repo, branch, base_sha)

    commit_msg = (
        f"[{key}] Update API spec — {summary}\n\n"
        f"Version: {current_version} → {new_version}\n"
        f"Approved subtask: {approved_key}\n"
        f"Change type: {'breaking' if has_breaking else 'additive' if has_additive else 'patch'}"
    )
    print(f"  Committing: {args.spec_path}", file=sys.stderr)
    gh_update_file(args.repo, args.spec_path, merged_yaml, commit_msg, blob_sha, branch)

    # ── 8. Open Pull Request ──────────────────────────────────────────────────
    pr_title = f"[{key}] Update API spec — {summary}"
    pr_body  = _build_pr_body(key, summary, approved_key, diffs, new_version, endpoint_yaml)
    pr_url   = gh_create_pr(args.repo, branch, pr_title, pr_body, args.base_branch)

    print(f"\n✓ Pull Request opened: {pr_url}", file=sys.stderr)
    print(pr_url)


if __name__ == "__main__":
    main()
