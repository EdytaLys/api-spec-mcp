# JIRA MCP Server

A Model Context Protocol (MCP) server that connects to JIRA and exposes tools for reading and counting tasks.

## Setup

### 1. Install dependencies

```bash
npm install
```

### 2. Configure credentials

Copy `.env.example` to `.env` and fill in your JIRA credentials:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `JIRA_BASE_URL` | Your JIRA instance URL, e.g. `https://your-domain.atlassian.net` |
| `JIRA_EMAIL` | Your Atlassian account email |
| `JIRA_API_TOKEN` | API token from [Atlassian account settings](https://id.atlassian.com/manage-profile/security/api-tokens) |

### 3. Run the server

```bash
npm start
```

## Available Tools

| Tool | Description |
|---|---|
| `jira_test_connection` | Verify the JIRA connection and return the authenticated user |
| `jira_count_tasks_todo` | Count tasks with status "To Do", "Backlog", or "Open" in a project |
| `jira_get_tasks` | List issues by project, status, assignee, or a raw JQL query |
| `jira_get_task` | Get full details of a single issue by key (e.g. `PROJ-123`) |

## Usage with Claude Desktop

Add to your `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "jira": {
      "command": "node",
      "args": ["/absolute/path/to/this/project/src/index.js"],
      "env": {
        "JIRA_BASE_URL": "https://your-domain.atlassian.net",
        "JIRA_EMAIL": "you@example.com",
        "JIRA_API_TOKEN": "your_api_token_here"
      }
    }
  }
}
```

## Example Queries

- "How many tasks are left to do in project MYPROJ?"
- "Show me all in-progress tasks assigned to me"
- "Get details for ticket MYPROJ-42"
- "Test the JIRA connection"
