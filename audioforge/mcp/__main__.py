"""stdio entry point for the AudioForge MCP server (``python -m audioforge.mcp``).

Reads newline-delimited JSON-RPC 2.0 requests on stdin, writes responses on
stdout (the MCP stdio transport). Notifications (no ``id``) get no response.
"""
from __future__ import annotations

import json
import sys

from audioforge.mcp.server import MCPServer


def main() -> int:  # pragma: no cover - exercised via the server unit tests
    server = MCPServer()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = server.handle(request)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
