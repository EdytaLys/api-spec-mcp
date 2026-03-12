#!/usr/bin/env python3
"""
Script to create JIRA user stories for API requests with minimal PO input.
Supports both NEW API creation and EXISTING API updates.

Usage:
    export JIRA_EMAIL="your-email@example.com"
    export JIRA_API_TOKEN="your-api-token"
    python create_api_update_story.py

Get your API token at: https://id.atlassian.com/manage-profile/security/api-tokens
"""

import os
import sys
import json
import base64
import urllib.request
import urllib.error

JIRA_BASE_URL = "https://playground-best-team.atlassian.net"
PROJECT_KEY = "SCRUM"


def get_new_api_template(endpoint, purpose, http_method="POST", fields=None, validation_rules=None, error_scenarios=None):
    """Template for creating a new API endpoint"""
    fields = fields or []
    validation_rules = validation_rules or []
    error_scenarios = error_scenarios or []
    
    content = [
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": f"As a developer, I want {endpoint} so that {purpose}"}]
        },
        {
            "type": "heading",
            "attrs": {"level": 3},
            "content": [{"type": "text", "text": "New endpoints to create"}]
        },
        {
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": f"{http_method} {endpoint}"}]}]},
            ]
        },
    ]
    
    # Always add fields section with examples if empty
    content.append({
        "type": "heading",
        "attrs": {"level": 3},
        "content": [{"type": "text", "text": "Request fields"}]
    })
    
    if fields:
        content.append({
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": field}]}]}
                for field in fields
            ]
        })
    else:
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": "📝 Please specify request fields in the format: fieldName, type, required/optional", "marks": [{"type": "em"}]}]
        })
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": "Examples:", "marks": [{"type": "strong"}]}]
        })
        content.append({
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "email, string, required"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "age, integer, optional"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "status, enum (ACTIVE/INACTIVE), required"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "price, number, required"}]}]},
            ]
        })
    
    # Always add validation rules section with examples if empty
    content.append({
        "type": "heading",
        "attrs": {"level": 3},
        "content": [{"type": "text", "text": "Validation rules"}]
    })
    
    if validation_rules:
        content.append({
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": rule}]}]}
                for rule in validation_rules
            ]
        })
    else:
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": "📝 Please specify business validation rules in plain English", "marks": [{"type": "em"}]}]
        })
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": "Examples:", "marks": [{"type": "strong"}]}]
        })
        content.append({
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Email must be valid format and unique in the system"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Age must be between 18 and 100"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Title must be unique within the project"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Password must be at least 8 characters with uppercase, lowercase, and number"}]}]},
            ]
        })
    
    # Always add error scenarios section with examples if empty
    content.append({
        "type": "heading",
        "attrs": {"level": 3},
        "content": [{"type": "text", "text": "Error scenarios"}]
    })
    
    if error_scenarios:
        content.append({
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": error}]}]}
                for error in error_scenarios
            ]
        })
    else:
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": "📝 Please specify expected error cases with HTTP status codes", "marks": [{"type": "em"}]}]
        })
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": "Examples:", "marks": [{"type": "strong"}]}]
        })
        content.append({
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "400 - Invalid email format"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "404 - Resource not found"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "409 - Email already registered"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "422 - Validation failed"}]}]},
            ]
        })
    
    # Add acceptance criteria
    content.append({
        "type": "heading",
        "attrs": {"level": 3},
        "content": [{"type": "text", "text": "Acceptance criteria"}]
    })
    
    acceptance_criteria = [
        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Endpoint accepts valid request and returns appropriate response"}]}]},
        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "All mandatory fields are validated"}]}]},
        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "All validation rules are enforced with clear error messages"}]}]},
        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "All error scenarios return appropriate HTTP status codes and messages"}]}]},
        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Auto-generated OpenAPI spec documents the endpoint with correct schemas"}]}]},
    ]
    
    content.append({
        "type": "bulletList",
        "content": acceptance_criteria
    })
    
    return {
        "summary": f"Create {endpoint} endpoint",
        "story_type": "new_api",
        "description": {
            "version": 1,
            "type": "doc",
            "content": content
        },
        "labels": ["new-api", "api-spec"],
        "story_points": 5,
    }


def get_update_api_template(endpoint, changes, acceptance_criteria, fields=None, validation_rules=None, error_scenarios=None):
    """Template for updating an existing API endpoint"""
    fields = fields or []
    validation_rules = validation_rules or []
    error_scenarios = error_scenarios or []
    
    content = [
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": f"As a developer, I want to update {endpoint} to improve functionality and meet new requirements."}]
        },
        {
            "type": "heading",
            "attrs": {"level": 3},
            "content": [{"type": "text", "text": "Existing endpoint"}]
        },
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": endpoint}]
        },
        {
            "type": "heading",
            "attrs": {"level": 3},
            "content": [{"type": "text", "text": "Required changes"}]
        },
        {
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": change}]}]}
                for change in changes
            ]
        },
    ]
    
    # Always add fields section with examples if empty
    content.append({
        "type": "heading",
        "attrs": {"level": 3},
        "content": [{"type": "text", "text": "Request fields"}]
    })
    
    if fields:
        content.append({
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": field}]}]}
                for field in fields
            ]
        })
    else:
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": "📝 Please specify updated or new request fields in the format: fieldName, type, required/optional", "marks": [{"type": "em"}]}]
        })
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": "Examples:", "marks": [{"type": "strong"}]}]
        })
        content.append({
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "title, string, optional (for PATCH endpoints)"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "status, enum (TODO/IN_PROGRESS/DONE), optional"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "priority, enum (LOW/MEDIUM/HIGH), required"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "dueDate, date, optional"}]}]},
            ]
        })
    
    # Always add validation rules section with examples if empty
    content.append({
        "type": "heading",
        "attrs": {"level": 3},
        "content": [{"type": "text", "text": "Validation rules"}]
    })
    
    if validation_rules:
        content.append({
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": rule}]}]}
                for rule in validation_rules
            ]
        })
    else:
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": "📝 Please specify business validation rules in plain English", "marks": [{"type": "em"}]}]
        })
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": "Examples:", "marks": [{"type": "strong"}]}]
        })
        content.append({
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Title must be unique within the project if provided"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Status must be one of the valid enum values"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Due date must be in the future if provided"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "At least one field must be present in PATCH request"}]}]},
            ]
        })
    
    # Always add error scenarios section with examples if empty
    content.append({
        "type": "heading",
        "attrs": {"level": 3},
        "content": [{"type": "text", "text": "Error scenarios"}]
    })
    
    if error_scenarios:
        content.append({
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": error}]}]}
                for error in error_scenarios
            ]
        })
    else:
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": "📝 Please specify expected error cases with HTTP status codes", "marks": [{"type": "em"}]}]
        })
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": "Examples:", "marks": [{"type": "strong"}]}]
        })
        content.append({
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "400 - Invalid field value"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "404 - Resource not found"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "409 - Conflict with existing data"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "422 - Validation failed"}]}]},
            ]
        })
    
    # Add acceptance criteria
    content.append({
        "type": "heading",
        "attrs": {"level": 3},
        "content": [{"type": "text", "text": "Acceptance criteria"}]
    })
    content.append({
        "type": "bulletList",
        "content": [
            {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": criterion}]}]}
            for criterion in acceptance_criteria
        ]
    })
    
    return {
        "summary": f"Update {endpoint}",
        "story_type": "update_existing_api",
        "description": {
            "version": 1,
            "type": "doc",
            "content": content
        },
        "labels": ["update-existing-api", "api-spec"],
        "story_points": 3,
    }


def build_auth_header(email: str, api_token: str) -> str:
    credentials = f"{email}:{api_token}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def create_issue(auth_header: str, story: dict) -> dict:
    url = f"{JIRA_BASE_URL}/rest/api/3/issue"

    payload = {
        "fields": {
            "project": {"key": PROJECT_KEY},
            "summary": story["summary"],
            "description": story["description"],
            "issuetype": {"name": "Story"},
            "labels": story.get("labels", []),
        }
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())


def collect_fields():
    """Collect field information from PO"""
    print("\nAPI FIELDS")
    print("-" * 70)
    print("For each field, provide: name, type, and whether it's required")
    print("Example: email, string, required")
    print("Example: age, integer, optional")
    print("(Enter empty line when done)")
    print()
    
    fields = []
    i = 1
    while True:
        field_input = input(f"  Field {i}: ").strip()
        if not field_input:
            break
        fields.append(field_input)
        i += 1
    
    return fields


def collect_validation_rules():
    """Collect validation rules from PO"""
    print("\nVALIDATION RULES")
    print("-" * 70)
    print("Describe business validation rules in plain English")
    print("Example: Email must be valid format")
    print("Example: Age must be between 18 and 100")
    print("Example: Title must be unique within the project")
    print("(Enter empty line when done)")
    print()
    
    rules = []
    i = 1
    while True:
        rule = input(f"  Rule {i}: ").strip()
        if not rule:
            break
        rules.append(rule)
        i += 1
    
    return rules


def collect_error_scenarios():
    """Collect error scenarios and messages from PO"""
    print("\nERROR SCENARIOS")
    print("-" * 70)
    print("Describe expected error cases with HTTP status codes")
    print("Example: 400 - Invalid email format")
    print("Example: 404 - Task not found")
    print("Example: 409 - Title already exists")
    print("(Enter empty line when done)")
    print()
    
    errors = []
    i = 1
    while True:
        error = input(f"  Error {i}: ").strip()
        if not error:
            break
        errors.append(error)
        i += 1
    
    return errors


def get_user_input():
    """Interactive prompt to gather story details"""
    print("=" * 70)
    print(" JIRA API Story Generator")
    print("=" * 70)
    print()
    
    # Story type
    print("What type of API story do you want to create?")
    print("  1. New API endpoint")
    print("  2. Update existing API endpoint")
    print()
    
    while True:
        choice = input("Enter choice (1 or 2): ").strip()
        if choice in ["1", "2"]:
            break
        print("Invalid choice. Please enter 1 or 2.")
    
    story_type = "new" if choice == "1" else "update"
    print()
    
    if story_type == "new":
        # New API
        print("NEW API ENDPOINT")
        print("-" * 70)
        endpoint = input("Endpoint path (e.g., /api/tasks): ").strip()
        http_method = input("HTTP method (GET/POST/PUT/PATCH/DELETE) [POST]: ").strip().upper() or "POST"
        purpose = input("Purpose (what does this API do?): ").strip()
        
        # Collect detailed requirements
        fields = collect_fields()
        validation_rules = collect_validation_rules()
        error_scenarios = collect_error_scenarios()
        
        return get_new_api_template(endpoint, purpose, http_method, fields, validation_rules, error_scenarios)
    
    else:
        # Update existing API
        print("UPDATE EXISTING API")
        print("-" * 70)
        endpoint = input("Endpoint to update (e.g., PUT /api/tasks/{id}): ").strip()
        
        print("\nRequired changes (enter each change, empty line to finish):")
        changes = []
        i = 1
        while True:
            change = input(f"  {i}. ").strip()
            if not change:
                break
            changes.append(change)
            i += 1
        
        if not changes:
            changes = ["Update endpoint implementation"]
        
        # Collect detailed requirements
        print("\nDo you need to specify fields for this update? (y/N): ", end="")
        if input().strip().lower() == 'y':
            fields = collect_fields()
        else:
            fields = []
        
        validation_rules = collect_validation_rules()
        error_scenarios = collect_error_scenarios()
        
        print("\nAcceptance criteria (enter each criterion, empty line to finish):")
        criteria = []
        i = 1
        while True:
            criterion = input(f"  {i}. ").strip()
            if not criterion:
                break
            criteria.append(criterion)
            i += 1
        
        if not criteria:
            criteria = ["Updated endpoint works as expected", "Auto-generated OpenAPI spec reflects changes"]
        
        return get_update_api_template(endpoint, changes, criteria, fields, validation_rules, error_scenarios)


def main():
    email = os.environ.get("JIRA_EMAIL")
    api_token = os.environ.get("JIRA_API_TOKEN")

    if not email or not api_token:
        print("ERROR: Set JIRA_EMAIL and JIRA_API_TOKEN environment variables.")
        print("  export JIRA_EMAIL='your-email@example.com'")
        print("  export JIRA_API_TOKEN='your-api-token'")
        print("Get your token at: https://id.atlassian.com/manage-profile/security/api-tokens")
        sys.exit(1)

    auth_header = build_auth_header(email, api_token)

    # Get story details from user
    story_template = get_user_input()
    
    print()
    print("=" * 70)
    print(f"Creating story in JIRA project {PROJECT_KEY}...")
    print(f"Summary: {story_template['summary']}")
    print("=" * 70)
    print()

    try:
        result = create_issue(auth_header, story_template)
        issue_key = result.get("key", "???")
        issue_url = f"{JIRA_BASE_URL}/browse/{issue_key}"
        print(f"✓ Created: {issue_key}")
        print(f"  URL: {issue_url}")
        print(f"\n✓ Story created successfully!")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"✗ HTTP {e.code}: {body[:200]}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
