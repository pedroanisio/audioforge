"""Regressions for MCP request recovery, PCM previews and CLI argv parsing."""
import json
import subprocess
import sys
import wave
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from audioforge.cli import main
from audioforge.mcp.server import MCPServer, _waveform_png


def test_invalid_verify_does_not_terminate_stdio_server():
    requests = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {
            'name': 'verify', 'arguments': {'spec': {}, 'expected_sha256': '0' * 64}}},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
    ]
    process = subprocess.run([sys.executable, '-m', 'audioforge.mcp'],
                             input=''.join(json.dumps(r) + '\n' for r in requests),
                             text=True, capture_output=True, timeout=20)
    assert process.returncode == 0, process.stderr
    responses = [json.loads(line) for line in process.stdout.splitlines()]
    assert [r['id'] for r in responses] == [1, 2]
    assert responses[0]['result']['isError'] is True
    assert 'missing' in responses[0]['result']['content'][0]['text']
    assert responses[1]['result']['tools']


def test_render_failure_is_tool_error_and_server_recovers(monkeypatch):
    server = MCPServer()
    monkeypatch.setattr('audioforge.mcp.server.agent_tools.run_tool',
                        lambda *args: {'ok': True})

    def fail(dsl):
        raise RuntimeError('native compiler unavailable')

    monkeypatch.setattr(server, '_render_session_resources', fail)
    response = server.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                              'params': {'name': 'render', 'arguments': {'dsl': 'asset ...'}}})
    assert response['result']['isError'] is True
    assert 'native compiler unavailable' in response['result']['content'][0]['text']
    assert server.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})['result']['tools']


@pytest.mark.parametrize('width', [2, 3, 4])
def test_waveform_decodes_signed_pcm_before_selecting_left_channel(tmp_path, monkeypatch, width):
    from matplotlib.axes import Axes
    left = [1 << (8 * width - 3), -(1 << (8 * width - 3)), 0]
    right = [0, 0, 1 << (8 * width - 2)]
    wav = tmp_path / 'preview.wav'
    raw = b''.join(x.to_bytes(width, 'little', signed=True)
                   for pair in zip(left, right) for x in pair)
    with wave.open(str(wav), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(width)
        w.setframerate(48000)
        w.writeframes(raw)
    plotted = []
    real = Axes.plot

    def capture(self, data, *args, **kwargs):
        plotted.append(np.asarray(data))
        return real(self, data, *args, **kwargs)

    monkeypatch.setattr(Axes, 'plot', capture)
    assert _waveform_png(wav).startswith(b'\x89PNG')
    np.testing.assert_array_equal(plotted[0], np.array([0.25, -0.25, 0]))


@pytest.mark.parametrize('params', [['key=C minor'], ["key='C minor' duration=3"]])
def test_cue_dsl_accepts_shell_tokens_and_grouped_params(capsys, params):
    assert main(['cue', 'dsl', 'sting/closer', *params]) == 0
    assert 'asset' in capsys.readouterr().out


def test_cue_render_preserves_shell_quoted_key(tmp_path):
    out = tmp_path / 'sting.wav'
    assert main(['cue', 'render', 'sting/closer', 'key=C minor', '-o', str(out)]) == 0
    info = json.loads((tmp_path / 'sting.wav.audioforge.json').read_text())
    assert info['params']['key'] == 'C minor'


def test_scene_add_preserves_shell_quoted_key(tmp_path):
    scene = tmp_path / 'scene.xml'
    scene.write_text('<scene><assets></assets></scene>')
    assert main(['scene', 'add', str(scene), 'sting/closer', 'key=C minor', '--no-resolve']) == 0
    asset = ET.parse(scene).find('assets/generated')
    assert asset.get('prompt') == "key='C minor'"
