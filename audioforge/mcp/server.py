"""Minimal MCP server over the agent_tools facade (roadmap item AF-R10).

Exposes AudioForge's in-process agent surface
(:func:`audioforge.agent_tools.run_tool`) over the Model Context Protocol so an
external agent can drive compile / validate / plan / render / analyze /
decompile / import / export / repair — plus ``capabilities`` and ``verify`` —
over stdio, without a human-operated CLI.

The nine ops are pure pass-throughs to ``run_tool`` (no forked logic path). The
``render`` tool additionally emits inspectable **session resources** (WAV,
manifest, waveform PNG) via the SDK export path, so a vision-capable agent can
*see* the output the way a VLM verifies a rendered image.

Transport: JSON-RPC 2.0, newline-delimited messages (the MCP stdio convention).
Entry point: ``python -m audioforge.mcp``.

⚠ ARCHITECTURAL CONTRACT (PALS's LAW): the server is a thin protocol adapter over
verified facade functions; it adds no new render/validate logic that could
disagree with the engine.
"""
from __future__ import annotations

import base64
import io
import json
import tempfile
import wave
from pathlib import Path

from audioforge import agent_tools
from audioforge.capabilities import capability_manifest
from audioforge.version import ENGINE_VERSION

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "audioforge"

_EXTRA_TOOLS = {
    "capabilities": "Return the AudioForge capability manifest (ops, statuses, diagnostic codes).",
    "verify": "Re-render a spec and compare output_sha256 to an expected hash (reproducibility gate).",
}


def _result(rid, result):
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _error(rid, code, message):
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


class MCPServer:
    """Stateful MCP server: dispatches JSON-RPC requests and holds session resources."""

    def __init__(self) -> None:
        self._resources: dict[str, dict] = {}
        self._seq = 0

    # -- tool surface --------------------------------------------------------
    def tool_defs(self) -> list[dict]:
        ops = {
            op: f"AudioForge agent-tools op '{op}' (envelope {agent_tools.TOOL_SCHEMA_VERSION}); "
                "arguments are the agent-tools request, e.g. {\"dsl\": \"asset ...\"}."
            for op in agent_tools.tool_schemas()
        }
        return [
            {
                "name": name,
                "description": desc,
                "inputSchema": {"type": "object", "additionalProperties": True},
            }
            for name, desc in {**ops, **_EXTRA_TOOLS}.items()
        ]

    def tool_names(self) -> set[str]:
        return set(agent_tools.tool_schemas()) | set(_EXTRA_TOOLS)

    # -- dispatch ------------------------------------------------------------
    def _register(self, uri, mime, *, text=None, blob=None):
        self._resources[uri] = {"mimeType": mime, "text": text, "blob": blob}

    def _render_session_resources(self, dsl: str) -> list[str]:
        """Render *dsl* to WAV + manifest + waveform PNG; register + return their URIs."""
        from audioforge import AudioForge

        res = AudioForge().compile(dsl)
        if not res.ok:
            return []
        self._seq += 1
        base = f"audioforge://session/s{self._seq}"
        outdir = Path(tempfile.mkdtemp(prefix="af_mcp_"))
        meta = res.assets[0].export(str(outdir))
        uris = [f"{base}/manifest.json"]
        self._register(f"{base}/manifest.json", "application/json", text=json.dumps(meta, indent=2, default=str))
        wavs = sorted(outdir.glob("*.wav"))
        if wavs:
            wav = wavs[0]
            self._register(f"{base}/render.wav", "audio/wav",
                           blob=base64.b64encode(wav.read_bytes()).decode())
            self._register(f"{base}/waveform.png", "image/png",
                           blob=base64.b64encode(_waveform_png(wav)).decode())
            uris += [f"{base}/render.wav", f"{base}/waveform.png"]
        return uris

    def _call_tool(self, name: str, arguments: dict) -> dict:
        if name in agent_tools.tool_schemas():
            envelope = agent_tools.run_tool(name, arguments)  # REUSE — no forked path
            content = [{"type": "text", "text": json.dumps(envelope, indent=2, default=str)}]
            if name == "render" and envelope.get("ok") and arguments.get("dsl"):
                for uri in self._render_session_resources(arguments["dsl"]):
                    content.append({"type": "resource", "resource": {"uri": uri}})
            return {"content": content, "isError": not envelope.get("ok", False)}
        if name == "capabilities":
            return {"content": [{"type": "text",
                                 "text": json.dumps(capability_manifest(), indent=2, default=str)}],
                    "isError": False}
        if name == "verify":
            ok, text = self._verify(arguments)
            return {"content": [{"type": "text", "text": text}], "isError": not ok}
        return {"content": [{"type": "text", "text": f"unknown tool {name!r}"}], "isError": True}

    def _verify(self, arguments: dict) -> tuple[bool, str]:
        # import from the submodule path — `audioforge.render` the attribute is
        # the exported render() function, not the module.
        from audioforge.render import verify as render_verify

        spec = arguments.get("spec")
        expected = arguments.get("expected_sha256")
        if not isinstance(spec, dict) or not expected:
            return False, "verify requires {spec: <ir dict>, expected_sha256: <hex>}"
        with tempfile.TemporaryDirectory() as d:
            ok = render_verify(spec, expected, d)
        return ok, "REPRODUCIBLE" if ok else "MISMATCH — output drifted"

    # -- JSON-RPC ------------------------------------------------------------
    def handle(self, request: dict) -> dict | None:
        method = request.get("method")
        rid = request.get("id")
        if method == "initialize":
            return _result(rid, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": SERVER_NAME, "version": ENGINE_VERSION},
            })
        if method in ("notifications/initialized", "initialized"):
            return None  # a notification — no response
        if method == "tools/list":
            return _result(rid, {"tools": self.tool_defs()})
        if method == "tools/call":
            params = request.get("params") or {}
            return _result(rid, self._call_tool(params.get("name"), params.get("arguments") or {}))
        if method == "resources/list":
            return _result(rid, {"resources": [
                {"uri": u, "name": u.rsplit("/", 1)[-1], "mimeType": r["mimeType"]}
                for u, r in self._resources.items()
            ]})
        if method == "resources/read":
            uri = (request.get("params") or {}).get("uri")
            r = self._resources.get(uri)
            if r is None:
                return _error(rid, -32602, f"unknown resource {uri!r}")
            entry = {"uri": uri, "mimeType": r["mimeType"]}
            if r.get("text") is not None:
                entry["text"] = r["text"]
            if r.get("blob") is not None:
                entry["blob"] = r["blob"]
            return _result(rid, {"contents": [entry]})
        if rid is not None:
            return _error(rid, -32601, f"method not found: {method}")
        return None


def _waveform_png(wav_path: Path) -> bytes:
    """A small waveform thumbnail (left channel) for VLM inspection."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    with wave.open(str(wav_path)) as w:
        n, ch, sw = w.getnframes(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}.get(sw, np.int16)
    data = np.frombuffer(raw, dtype=dtype).astype(np.float64)
    if ch > 1:
        data = data[::ch]
    fig, ax = plt.subplots(figsize=(6, 2))
    ax.plot(data, linewidth=0.5)
    ax.set_axis_off()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=72, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
