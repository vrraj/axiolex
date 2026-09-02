"""Jira MCP server (stdio transport) for Axiolex.

Axiolex spawns this script as a subprocess and passes credentials via
environment variables:

- ``JIRA_API_TOKEN``          — the API token (secret, from encrypted store or .env)
- ``JIRA_API_TOKEN_USERNAME`` — the account email (non-secret, from YAML config)
- ``JIRA_SERVER``             — optional, defaults to the site in mcp_providers.yaml

Tools exposed:
  - search_tickets(jql)       — search issues via JQL
  - create_ticket(project, title, body, type) — create a new issue
"""

import os

from jira import JIRA
from mcp.server.fastmcp import FastMCP

_TOKEN = os.environ.get("JIRA_API_TOKEN", "")
_EMAIL = os.environ.get("JIRA_API_TOKEN_USERNAME", "")
_SERVER = os.environ.get("JIRA_SERVER", "https://vrrajkumar99.atlassian.net")

if not _TOKEN or not _EMAIL:
    raise RuntimeError(
        "JIRA_API_TOKEN and JIRA_API_TOKEN_USERNAME environment variables "
        "are required. Axiolex should set these when spawning this server."
    )

mcp = FastMCP("Jira")
jira = JIRA(server=_SERVER, basic_auth=(_EMAIL, _TOKEN))


@mcp.tool()
def search_tickets(jql: str) -> str:
    """Search Jira tickets using a JQL query.

    Args:
        jql: A JQL query string, e.g. "project = SCRUM" or "assignee = currentUser()"

    Returns:
        Up to 10 matching issues as "[KEY] summary (status: ...)" lines.
    """
    issues = jira.search_issues(jql, maxResults=10)
    if not issues:
        return "No issues found."
    return "\n".join(
        f"[{i.key}] {i.fields.summary} (status: {i.fields.status.name})"
        for i in issues
    )


@mcp.tool()
def create_ticket(project: str, title: str, body: str, type: str = "Task") -> str:
    """Create a new ticket in Jira.

    Args:
        project: The Jira project key, e.g. "SCRUM"
        title: The ticket summary / title
        body: The ticket description
        type: Issue type name, e.g. "Task", "Bug", "Story" (default: "Task")

    Returns:
        The created ticket key and permalink, e.g. "Created SCRUM-7: https://..."
    """
    new_issue = jira.create_issue(
        project=project,
        summary=title,
        description=body,
        issuetype={"name": type},
    )
    return f"Created {new_issue.key}: {new_issue.permalink()}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
