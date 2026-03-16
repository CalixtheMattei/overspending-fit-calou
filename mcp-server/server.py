"""
MCP server for personal-expense — thin HTTP proxy over the FastAPI backend.

Usage:
  python server.py                         # stdio (Claude Code / Claude Desktop)
  python server.py --transport sse         # SSE on port 3001 (Docker / remote clients)
  python server.py --transport sse --port 3001

Environment variables:
  API_BASE_URL   Backend base URL (default: http://localhost:8000)
"""
import argparse
import sys
import os

# Ensure tools/ is importable
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP
from tools import transactions, analytics, moments, categories, payees, rules, internal_accounts

_transport = os.getenv("MCP_TRANSPORT", "stdio")
_port = int(os.getenv("MCP_PORT", "3001"))
_host = "0.0.0.0" if _transport == "sse" else "127.0.0.1"

mcp = FastMCP("personal-expense", host=_host, port=_port)

transactions.register(mcp)
analytics.register(mcp)
moments.register(mcp)
categories.register(mcp)
payees.register(mcp)
rules.register(mcp)
internal_accounts.register(mcp)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="personal-expense MCP server")
    parser.add_argument(
        "--transport",
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        choices=["stdio", "sse"],
        help="Transport mode: stdio (default, for Claude Code) or sse (for Docker/remote)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_PORT", "3001")),
        help="Port for SSE transport (default: 3001)",
    )
    args = parser.parse_args()

    mcp.run(transport=args.transport)
