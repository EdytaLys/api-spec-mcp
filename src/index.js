import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import axios from "axios";
import * as dotenv from "dotenv";

dotenv.config();

// --- JIRA client ---

function getJiraClient() {
  const baseUrl = process.env.JIRA_BASE_URL;
  const email = process.env.JIRA_EMAIL;
  const apiToken = process.env.JIRA_API_TOKEN;

  if (!baseUrl || !email || !apiToken) {
    throw new Error(
      "Missing JIRA configuration. Set JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN environment variables."
    );
  }

  const token = Buffer.from(`${email}:${apiToken}`).toString("base64");

  return axios.create({
    baseURL: `${baseUrl.replace(/\/$/, "")}/rest/api/3`,
    headers: {
      Authorization: `Basic ${token}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
  });
}

async function searchIssues(jql, fields = ["summary", "status", "assignee", "priority", "issuetype"], maxResults = 50) {
  const client = getJiraClient();
  const response = await client.post("/search", {
    jql,
    maxResults,
    fields,
  });
  return response.data;
}

// --- MCP Server ---

const server = new McpServer({
  name: "jira-mcp-server",
  version: "1.0.0",
});

// Tool: count tasks to be done
server.tool(
  "jira_count_tasks_todo",
  "Count the number of tasks/issues in a JIRA project that are yet to be done (status = To Do or Backlog). Optionally filter by project key.",
  {
    project: z
      .string()
      .optional()
      .describe('JIRA project key (e.g. "MYPROJ"). Leave empty to count across all projects.'),
    status: z
      .array(z.string())
      .optional()
      .describe('Status names to count as "to do". Defaults to ["To Do", "Backlog", "Open"].'),
  },
  async ({ project, status }) => {
    const statusList = status ?? ["To Do", "Backlog", "Open"];
    const statusJql = statusList.map((s) => `"${s}"`).join(", ");
    const projectClause = project ? `project = "${project}" AND ` : "";
    const jql = `${projectClause}status in (${statusJql}) ORDER BY created DESC`;

    let data;
    try {
      data = await searchIssues(jql, ["summary", "status", "issuetype"], 100);
    } catch (err) {
      const message = err.response?.data?.errorMessages?.join(", ") ?? err.message;
      return {
        content: [{ type: "text", text: `Error querying JIRA: ${message}` }],
        isError: true,
      };
    }

    const total = data.total;
    const returned = data.issues.length;
    const projectLabel = project ? ` in project "${project}"` : " across all projects";

    const lines = [
      `Tasks to be done${projectLabel}: **${total}**`,
      `(Statuses counted: ${statusList.join(", ")})`,
      "",
    ];

    if (returned > 0) {
      lines.push("Sample issues:");
      data.issues.slice(0, 10).forEach((issue) => {
        lines.push(`  • [${issue.key}] ${issue.fields.summary} — ${issue.fields.status.name}`);
      });
      if (total > returned) {
        lines.push(`  … and ${total - returned} more`);
      }
    }

    return {
      content: [{ type: "text", text: lines.join("\n") }],
    };
  }
);

// Tool: get tasks (list issues)
server.tool(
  "jira_get_tasks",
  "Retrieve a list of JIRA issues using a JQL query or by project/status filters.",
  {
    project: z.string().optional().describe('JIRA project key (e.g. "MYPROJ").'),
    status: z.string().optional().describe('Filter by status name (e.g. "To Do", "In Progress", "Done").'),
    assignee: z
      .string()
      .optional()
      .describe('Filter by assignee account ID or "currentUser()".'),
    jql: z
      .string()
      .optional()
      .describe("Raw JQL query string. Overrides project/status/assignee filters if provided."),
    maxResults: z
      .number()
      .int()
      .min(1)
      .max(100)
      .optional()
      .default(20)
      .describe("Maximum number of issues to return (1–100, default 20)."),
  },
  async ({ project, status, assignee, jql: rawJql, maxResults }) => {
    let jql = rawJql;

    if (!jql) {
      const clauses = [];
      if (project) clauses.push(`project = "${project}"`);
      if (status) clauses.push(`status = "${status}"`);
      if (assignee) clauses.push(`assignee = ${assignee}`);
      jql = clauses.length > 0 ? clauses.join(" AND ") + " ORDER BY updated DESC" : "ORDER BY updated DESC";
    }

    let data;
    try {
      data = await searchIssues(jql, ["summary", "status", "assignee", "priority", "issuetype", "description"], maxResults);
    } catch (err) {
      const message = err.response?.data?.errorMessages?.join(", ") ?? err.message;
      return {
        content: [{ type: "text", text: `Error querying JIRA: ${message}` }],
        isError: true,
      };
    }

    if (data.issues.length === 0) {
      return {
        content: [{ type: "text", text: `No issues found for JQL: \`${jql}\`` }],
      };
    }

    const lines = [`Found ${data.total} issue(s) (showing ${data.issues.length}):`, ""];

    data.issues.forEach((issue) => {
      const assigneeName = issue.fields.assignee?.displayName ?? "Unassigned";
      const priority = issue.fields.priority?.name ?? "None";
      lines.push(`**${issue.key}**: ${issue.fields.summary}`);
      lines.push(`  Status: ${issue.fields.status.name} | Priority: ${priority} | Assignee: ${assigneeName}`);
      lines.push("");
    });

    return {
      content: [{ type: "text", text: lines.join("\n") }],
    };
  }
);

// Tool: get a single task by key
server.tool(
  "jira_get_task",
  "Get details of a single JIRA issue by its key (e.g. PROJ-123).",
  {
    key: z.string().describe('JIRA issue key (e.g. "PROJ-123").'),
  },
  async ({ key }) => {
    let response;
    try {
      const client = getJiraClient();
      response = await client.get(`/issue/${key}`, {
        params: { fields: "summary,status,assignee,priority,issuetype,description,comment,created,updated" },
      });
    } catch (err) {
      const message = err.response?.data?.errorMessages?.join(", ") ?? err.message;
      return {
        content: [{ type: "text", text: `Error fetching issue "${key}": ${message}` }],
        isError: true,
      };
    }

    const { fields } = response.data;
    const assigneeName = fields.assignee?.displayName ?? "Unassigned";
    const description = extractTextFromADF(fields.description) ?? "No description";

    const lines = [
      `**${key}**: ${fields.summary}`,
      `Type: ${fields.issuetype.name} | Status: ${fields.status.name} | Priority: ${fields.priority?.name ?? "None"}`,
      `Assignee: ${assigneeName}`,
      `Created: ${fields.created} | Updated: ${fields.updated}`,
      "",
      "**Description:**",
      description,
    ];

    const comments = fields.comment?.comments ?? [];
    if (comments.length > 0) {
      lines.push("", `**Comments (${comments.length}):**`);
      comments.slice(-3).forEach((c) => {
        const author = c.author?.displayName ?? "Unknown";
        const text = extractTextFromADF(c.body) ?? "";
        lines.push(`- ${author}: ${text.slice(0, 200)}`);
      });
    }

    return {
      content: [{ type: "text", text: lines.join("\n") }],
    };
  }
);

// Tool: test JIRA connection
server.tool(
  "jira_test_connection",
  "Test the JIRA connection and return the authenticated user's info.",
  {},
  async () => {
    let response;
    try {
      const client = getJiraClient();
      response = await client.get("/myself");
    } catch (err) {
      const message = err.response?.data?.message ?? err.response?.data?.errorMessages?.join(", ") ?? err.message;
      return {
        content: [{ type: "text", text: `JIRA connection failed: ${message}` }],
        isError: true,
      };
    }

    const { displayName, emailAddress, accountId } = response.data;
    return {
      content: [
        {
          type: "text",
          text: `JIRA connection successful!\nUser: ${displayName} (${emailAddress})\nAccount ID: ${accountId}`,
        },
      ],
    };
  }
);

// --- Helper: extract plain text from Atlassian Document Format (ADF) ---

function extractTextFromADF(adf) {
  if (!adf) return null;
  if (typeof adf === "string") return adf;

  const texts = [];

  function walk(node) {
    if (!node) return;
    if (node.type === "text") {
      texts.push(node.text ?? "");
    }
    if (Array.isArray(node.content)) {
      node.content.forEach(walk);
    }
  }

  walk(adf);
  return texts.join(" ").trim() || null;
}

// --- Start server ---

const transport = new StdioServerTransport();
await server.connect(transport);
console.error("JIRA MCP Server running on stdio");
