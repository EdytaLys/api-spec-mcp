#!/usr/bin/env python3
"""
Script to create JIRA user stories for testing an automatic API specification creation tool.
Based on the task_manager_with_copilot project (Spring Boot REST API).

Usage:
    export JIRA_EMAIL="your-email@example.com"
    export JIRA_API_TOKEN="your-api-token"
    python create_jira_stories.py

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

# ---------------------------------------------------------------------------
# User stories — mix of NEW API and UPDATING EXISTING endpoints
# ---------------------------------------------------------------------------
STORIES = [
    # ── NEW API stories ──────────────────────────────────────────────────────
    {
        "summary": "Create Labels API endpoint for task categorization",
        "story_type": "new_api",
        "description": {
            "version": 1,
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "As a developer, I want a Labels API so that tasks can be organised by category and filtered efficiently."}]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": "Background"}]
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "The current task manager API (task_manager_with_copilot) only supports title, description, status, and dueDate. Adding labels will allow teams to group tasks by feature, team, or priority tier without changing the existing status workflow."}]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": "New endpoints to create"}]
                },
                {
                    "type": "bulletList",
                    "content": [
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "POST /api/labels — create a label"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "GET /api/labels — list all labels"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "DELETE /api/labels/{id} — remove a label"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "POST /api/tasks/{id}/labels/{labelId} — attach label to task"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "DELETE /api/tasks/{id}/labels/{labelId} — detach label from task"}]}]},
                    ]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": "Acceptance criteria"}]
                },
                {
                    "type": "bulletList",
                    "content": [
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Label entity has id (Long), name (String, unique, max 50 chars), color (String hex, optional)"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "GET /api/tasks response includes a labels array for each task"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "GET /api/tasks?label=backend filters tasks by label name"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Deleting a label removes it from all tasks (cascade)"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "OpenAPI spec is auto-generated and reflects all new endpoints"}]}]},
                    ]
                },
            ]
        },
        "labels": ["new-api", "api-spec", "labels"],
        "story_points": 5,
    },
    {
        "summary": "Create Comments API to enable task collaboration",
        "story_type": "new_api",
        "description": {
            "version": 1,
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "As a team member, I want to add comments to tasks so that I can communicate progress and blockers without leaving the task manager."}]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": "New endpoints to create"}]
                },
                {
                    "type": "bulletList",
                    "content": [
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "POST /api/tasks/{taskId}/comments — add a comment"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "GET /api/tasks/{taskId}/comments — list comments for a task"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "PUT /api/tasks/{taskId}/comments/{commentId} — edit own comment"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "DELETE /api/tasks/{taskId}/comments/{commentId} — delete comment"}]}]},
                    ]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": "Acceptance criteria"}]
                },
                {
                    "type": "bulletList",
                    "content": [
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Comment entity has id, taskId (FK), body (max 1000 chars), author, createdAt, updatedAt"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Comments are returned ordered by createdAt ascending"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "POST returns 201 Created with the created comment body"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Deleting the parent task cascades to delete its comments"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Auto-generated OpenAPI spec documents request/response schemas correctly"}]}]},
                    ]
                },
            ]
        },
        "labels": ["new-api", "api-spec", "comments"],
        "story_points": 5,
    },
    {
        "summary": "Create Assignees API to assign tasks to team members",
        "story_type": "new_api",
        "description": {
            "version": 1,
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "As a project lead, I want to assign tasks to specific users so that ownership and responsibility are clear in the Kanban board."}]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": "New endpoints to create"}]
                },
                {
                    "type": "bulletList",
                    "content": [
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "POST /api/users — register a user"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "GET /api/users — list all users"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "PUT /api/tasks/{id}/assignee — assign/reassign a user to a task"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "DELETE /api/tasks/{id}/assignee — unassign"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "GET /api/users/{userId}/tasks — tasks assigned to a user"}]}]},
                    ]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": "Acceptance criteria"}]
                },
                {
                    "type": "bulletList",
                    "content": [
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "User entity has id, username (unique), email (unique), displayName"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "GET /api/tasks/{id} response includes assignee object (nullable)"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Assigning non-existent user returns 404 with descriptive message"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Auto-generated spec includes all user endpoints with correct schemas"}]}]},
                    ]
                },
            ]
        },
        "labels": ["new-api", "api-spec", "users"],
        "story_points": 8,
    },

    # ── UPDATE EXISTING API stories ──────────────────────────────────────────
    {
        "summary": "Update GET /api/tasks to support pagination and sorting",
        "story_type": "update_existing_api",
        "description": {
            "version": 1,
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "As a frontend developer, I want the GET /api/tasks endpoint to return paginated results so that the UI remains performant as the number of tasks grows."}]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": "Existing endpoint"}]
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "GET /api/tasks — currently returns all tasks as a flat array with no pagination."}]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": "Required changes"}]
                },
                {
                    "type": "bulletList",
                    "content": [
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Add query params: page (default 0), size (default 20, max 100), sort (e.g. createdAt,desc)"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Wrap response in Page<Task> envelope: { content, totalElements, totalPages, number, size }"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Add optional filter params: status, dueBefore, dueAfter"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Maintain backwards compatibility via Accept-Version header (v1 returns array, v2 returns paged)"}]}]},
                    ]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": "Acceptance criteria"}]
                },
                {
                    "type": "bulletList",
                    "content": [
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "GET /api/tasks?page=0&size=5 returns at most 5 tasks"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "GET /api/tasks?sort=dueDate,asc returns tasks sorted by due date ascending"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "GET /api/tasks?status=TODO returns only TODO tasks"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Requesting size > 100 returns 400 Bad Request"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Updated OpenAPI spec accurately describes new query parameters and paged response schema"}]}]},
                    ]
                },
            ]
        },
        "labels": ["update-existing-api", "api-spec", "pagination"],
        "story_points": 3,
    },
    {
        "summary": "Update Task entity and API to include a priority field",
        "story_type": "update_existing_api",
        "description": {
            "version": 1,
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "As a user, I want to set a priority level on tasks so that I can quickly identify what needs attention first."}]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": "Affected endpoints (all require schema update)"}]
                },
                {
                    "type": "bulletList",
                    "content": [
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "POST /api/tasks — accept priority in request body"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "PUT /api/tasks/{id} — allow updating priority"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "GET /api/tasks — include priority in response"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "GET /api/tasks/{id} — include priority in response"}]}]},
                    ]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": "Acceptance criteria"}]
                },
                {
                    "type": "bulletList",
                    "content": [
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Priority enum has values: LOW, MEDIUM, HIGH, CRITICAL with default MEDIUM"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Existing tasks without priority default to MEDIUM (migration script required)"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "POST /api/tasks without priority field uses default MEDIUM (no breaking change)"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Invalid priority value returns 400 with message listing valid values"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Auto-generated OpenAPI spec reflects updated Task schema including priority enum"}]}]},
                    ]
                },
            ]
        },
        "labels": ["update-existing-api", "api-spec", "task-model"],
        "story_points": 3,
    },
    {
        "summary": "Update DELETE /api/tasks/{id} to support soft delete with restore",
        "story_type": "update_existing_api",
        "description": {
            "version": 1,
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "As a user, I want deleted tasks to be recoverable within 30 days so that accidental deletions do not result in permanent data loss."}]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": "Affected & new endpoints"}]
                },
                {
                    "type": "bulletList",
                    "content": [
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "DELETE /api/tasks/{id} — change to soft delete (set deletedAt timestamp)"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "GET /api/tasks — by default excludes soft-deleted tasks"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "GET /api/tasks?includeDeleted=true — admin view including deleted tasks"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "POST /api/tasks/{id}/restore — NEW endpoint to undelete a task"}]}]},
                    ]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": "Acceptance criteria"}]
                },
                {
                    "type": "bulletList",
                    "content": [
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "DELETE /api/tasks/{id} returns 204 and sets deletedAt; row remains in DB"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "GET /api/tasks/{id} for a soft-deleted task returns 404 unless includeDeleted=true"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "POST /api/tasks/{id}/restore returns 200 and clears deletedAt"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Restoring an already-active task returns 409 Conflict"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Auto-generated OpenAPI spec documents the restore endpoint and deletedAt field"}]}]},
                    ]
                },
            ]
        },
        "labels": ["update-existing-api", "api-spec", "soft-delete"],
        "story_points": 5,
    },
    {
        "summary": "Add PATCH /api/tasks/{id} for partial task updates",
        "story_type": "update_existing_api",
        "description": {
            "version": 1,
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "As a frontend developer, I want a PATCH endpoint so that I can update only the changed fields of a task without fetching and resending the full object."}]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": "Context"}]
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "The existing PUT /api/tasks/{id} requires all task fields. Drag-and-drop status updates on the Kanban board should only need to send { \"status\": \"IN_PROGRESS\" } rather than the full payload."}]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": "Required changes"}]
                },
                {
                    "type": "bulletList",
                    "content": [
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Add PATCH /api/tasks/{id} accepting a partial TaskUpdateRequest"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Only fields present in the request body are updated (null means 'no change', not 'clear field')"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Keep PUT /api/tasks/{id} for full-replacement semantics (no breaking change)"}]}]},
                    ]
                },
                {
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": "Acceptance criteria"}]
                },
                {
                    "type": "bulletList",
                    "content": [
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "PATCH /api/tasks/{id} with { \"status\": \"DONE\" } updates only status, other fields unchanged"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "PATCH with empty body {} returns 200 with unchanged task"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "PATCH with title that already exists returns 409 Conflict"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "updatedAt is refreshed on every successful PATCH"}]}]},
                        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Auto-generated OpenAPI spec lists PATCH separately from PUT with correct schema"}]}]},
                    ]
                },
            ]
        },
        "labels": ["update-existing-api", "api-spec", "patch"],
        "story_points": 3,
    },
]


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

    new_api_stories = [s for s in STORIES if s["story_type"] == "new_api"]
    update_stories = [s for s in STORIES if s["story_type"] == "update_existing_api"]

    print(f"Creating {len(STORIES)} user stories in JIRA project {PROJECT_KEY}...")
    print(f"  {len(new_api_stories)} × New API  |  {len(update_stories)} × Update Existing API\n")

    created = []
    failed = []

    for story in STORIES:
        tag = "[NEW API]" if story["story_type"] == "new_api" else "[UPDATE]"
        print(f"  {tag} {story['summary'][:70]}...", end=" ", flush=True)
        try:
            result = create_issue(auth_header, story)
            issue_key = result.get("key", "???")
            issue_url = f"{JIRA_BASE_URL}/browse/{issue_key}"
            print(f"✓ {issue_key}")
            created.append({"key": issue_key, "url": issue_url, "summary": story["summary"]})
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f"✗ HTTP {e.code}: {body[:120]}")
            failed.append({"summary": story["summary"], "error": f"HTTP {e.code}: {body[:120]}"})
        except Exception as e:
            print(f"✗ {e}")
            failed.append({"summary": story["summary"], "error": str(e)})

    print(f"\n{'='*60}")
    print(f"Created {len(created)}/{len(STORIES)} stories successfully.\n")

    if created:
        print("Created issues:")
        for item in created:
            print(f"  {item['key']}  {item['url']}")
            print(f"       {item['summary']}")

    if failed:
        print(f"\nFailed ({len(failed)}):")
        for item in failed:
            print(f"  - {item['summary']}")
            print(f"    {item['error']}")


if __name__ == "__main__":
    main()
