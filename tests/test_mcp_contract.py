"""Contract tests for the MCP server over agent_tools (roadmap item AF-R10)."""
from __future__ import annotations

import json
from pathlib import Path

from audioforge import agent_tools
from audioforge.mcp.server import MCPServer

ROOT = Path(__file__).resolve().parents[1]
DSL = (ROOT / "static" / "samples" / "transition_sweep.af").read_text()


def _rpc(server, method, params=None, rid=1):
    return server.handle({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})


def test_every_agent_tools_op_is_exposed_as_a_tool():
    server = MCPServer()
    names = server.tool_names()
    missing = set(agent_tools.tool_schemas()) - names
    assert not missing, f"agent_tools ops not exposed over MCP: {sorted(missing)}"
    assert {"capabilities", "verify"} <= names


def test_tools_list_matches_tool_names():
    server = MCPServer()
    listed = {t["name"] for t in _rpc(server, "tools/list")["result"]["tools"]}
    assert listed == server.tool_names()
    for t in _rpc(server, "tools/list")["result"]["tools"]:
        assert t["inputSchema"]["type"] == "object" and t["description"]


def test_initialize_handshake():
    server = MCPServer()
    r = _rpc(server, "initialize")["result"]
    assert r["protocolVersion"]
    assert r["serverInfo"]["name"] == "audioforge"
    assert "tools" in r["capabilities"] and "resources" in r["capabilities"]


def test_initialized_notification_gets_no_response():
    assert MCPServer().handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_tools_call_compile_returns_envelope():
    server = MCPServer()
    out = _rpc(server, "tools/call", {"name": "compile", "arguments": {"dsl": DSL}})["result"]
    assert out["isError"] is False
    envelope = json.loads(out["content"][0]["text"])
    assert envelope["schema"] == agent_tools.TOOL_SCHEMA_VERSION and envelope["ok"] is True


def test_render_roundtrip_exposes_manifest_and_waveform_png():
    server = MCPServer()
    _rpc(server, "tools/call", {"name": "compile", "arguments": {"dsl": DSL}})
    _rpc(server, "tools/call", {"name": "validate", "arguments": {"dsl": DSL}})
    call = _rpc(server, "tools/call", {"name": "render", "arguments": {"dsl": DSL}})["result"]
    assert call["isError"] is False
    resources = _rpc(server, "resources/list")["result"]["resources"]
    uris = {r["uri"].rsplit("/", 1)[-1]: r["uri"] for r in resources}
    assert "manifest.json" in uris and "waveform.png" in uris
    # read the manifest back
    man = _rpc(server, "resources/read", {"uri": uris["manifest.json"]})["result"]["contents"][0]
    assert "output_sha256" in man["text"]
    # read the waveform PNG back (base64 blob, PNG magic header)
    png = _rpc(server, "resources/read", {"uri": uris["waveform.png"]})["result"]["contents"][0]
    import base64
    assert base64.b64decode(png["blob"])[:8] == b"\x89PNG\r\n\x1a\n"


def test_capabilities_tool_returns_manifest():
    server = MCPServer()
    out = _rpc(server, "tools/call", {"name": "capabilities", "arguments": {}})["result"]
    assert out["isError"] is False
    assert json.loads(out["content"][0]["text"])["schema"].startswith("audioforge.capabilities")


def test_server_reuses_run_tool_not_a_forked_path(monkeypatch):
    server = MCPServer()
    calls = []
    real = agent_tools.run_tool
    monkeypatch.setattr(agent_tools, "run_tool", lambda op, req: calls.append(op) or real(op, req))
    _rpc(server, "tools/call", {"name": "plan", "arguments": {"dsl": DSL}})
    assert calls == ["plan"], "MCP op did not dispatch through agent_tools.run_tool"


def test_verify_tool_requires_spec_and_hash():
    out = _rpc(MCPServer(), "tools/call", {"name": "verify", "arguments": {}})["result"]
    assert out["isError"] is True and "requires" in out["content"][0]["text"]


def test_verify_tool_reports_reproducible():
    from audioforge import AudioForge

    server = MCPServer()
    res = AudioForge().compile(DSL)
    spec = res.assets[0].spec
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        meta = res.assets[0].export(d)
    out = _rpc(server, "tools/call",
               {"name": "verify", "arguments": {"spec": spec, "expected_sha256": meta["output_sha256"]}})["result"]
    assert out["isError"] is False and out["content"][0]["text"] == "REPRODUCIBLE"


def test_unknown_method_errors():
    r = MCPServer().handle({"jsonrpc": "2.0", "id": 9, "method": "does/not/exist"})
    assert r["error"]["code"] == -32601


def test_resource_read_unknown_uri_errors():
    r = _rpc(MCPServer(), "resources/read", {"uri": "audioforge://session/nope"})
    assert r["error"]["code"] == -32602
