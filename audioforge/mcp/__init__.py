"""AudioForge MCP server (roadmap item AF-R10).

Exposes the ``audioforge.agent_tools`` facade over the Model Context Protocol so
external agents can drive the engine over stdio. Run with
``python -m audioforge.mcp``.
"""
from audioforge.mcp.server import MCPServer

__all__ = ["MCPServer"]
