"""Public notation entry points expose the same projection and diagnostics."""
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from audioforge import AudioForge, interop
from audioforge.agent_tools import run_tool, tool_schemas


FIX = Path(__file__).parent / "fixtures" / "notation"


def test_notated_sdk_agent_and_mcp_export_contract():
    asset = AudioForge().compile((FIX / "polymeter.af").read_text()).assets[0]
    expected = interop.export_notated_musicxml(asset.spec)
    assert asset.to_musicxml(notated=True) == expected
    result = run_tool("export", {"spec": asset.spec, "format": "musicxml_notated"})
    assert result["ok"] and result["artifacts"][0]["data"] == expected
    assert "lossy_polymeter" in {d["code"] for d in result["diagnostics"]}
    import json
    from audioforge.mcp.server import MCPServer
    response = MCPServer().handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                   "params": {"name": "export", "arguments": {
                                       "spec": asset.spec, "format": "musicxml_notated"}}})
    envelope = json.loads(response["result"]["content"][0]["text"])
    assert envelope == result
    assert "musicxml_notated" in tool_schemas()["export"]["request"]["properties"]["format"]["enum"]
    assert not run_tool("export", {"spec": asset.spec, "format": "unknown"})["ok"]


def test_cli_reports_lossy_notated_conversion(tmp_path, capsys):
    from audioforge.cli import main
    out = tmp_path / "score.musicxml"
    main(["export-musicxml", str(FIX / "polymeter.af"), "-o", str(out), "--notated"])
    assert ET.fromstring(out.read_text()).tag == "score-partwise"
    assert "lossy_polymeter" in capsys.readouterr().err


def test_midi_import_honours_all_tempo_events():
    spec = dict(id="steps", kind="cue", duration_s=6, bpm=120,
                tempo_map=[[0, 120], [4, 60]], layers=[dict(name="v", type="notes", notes=[
                    dict(note="C4", start_beat=0, dur_beats=8)])])
    back = interop.import_midi_bytes(interop.export_midi_bytes(spec))
    assert back["duration_s"] == pytest.approx(6)
    assert back["tempo_map"][-1] == [4, 60]


def test_oracle_gate_rejects_skipped_or_empty_evidence(tmp_path, monkeypatch, capsys):
    from audioforge.tools import oracle_check
    report = tmp_path / "junit.xml"
    assert not oracle_check.junit_passed(report)
    for body in ("", "<testcase><skipped/></testcase>",
                 "<testcase><failure/></testcase>", "<testcase><error/></testcase>"):
        report.write_text(f"<testsuites><testsuite>{body}</testsuite></testsuites>")
        assert not oracle_check.junit_passed(report)
    report.write_text("<testsuites><testsuite><testcase/></testsuite></testsuites>")
    assert oracle_check.junit_passed(report)
    monkeypatch.setattr(oracle_check, "missing_dependencies", lambda: ["music21"])
    assert oracle_check.main() == 0
    assert capsys.readouterr().out.strip() == "oracle-check: SKIPPED — install '.[oracles]'"


def test_documented_contract_and_fixture_inventory():
    import json
    import numpy as np
    from audioforge.analysis import analyze_audio
    from audioforge.capabilities import capability_manifest
    from audioforge.tools.notation_acceptance import registry
    root = Path(__file__).resolve().parents[1]
    assert len(registry()) == 53
    assert analyze_audio(np.zeros((8000, 2)), 8000)["assessment_scope"]
    assert "engrav" not in (root / "audioforge/score.py").read_text().lower()
    assert "## Notation and analysis" in (root / "README.md").read_text()
    adr = (root / "docs/adr/0011-notation-interchange-oracles.md").read_text()
    assert all(word in adr for word in ("## Decision", "music21", "LilyPond", "M5"))
    gap = (root / "docs/DSL_GAP_SPEC.md").read_text()
    assert "HARNESS-NTUN" in gap and "HARNESS-NIMP" in gap
    manifest = capability_manifest()
    assert {"tuning", "tuplet", "lyrics"} <= manifest["notation"]["directives"].keys()
    assert manifest["interop"]["coverage"] == interop.coverage()
    assert manifest["score"]["proof_sheet"]
    fixtures = sorted(FIX.glob("*.af"))
    assert len(fixtures) >= 8
    for path in fixtures:
        expected = json.loads(path.with_suffix(".expected.json").read_text())
        compiled = AudioForge().compile(path.read_text())
        assert compiled.ok and expected["constructs"], path.name
        assert len(compiled.assets[0].spec["layers"]) == expected["parts"]


@pytest.mark.parametrize("oracles,skip_case,skip_full", [(True, False, False),
                                                       (True, True, False),
                                                       (False, False, True)])
def test_acceptance_runner_accounts_for_all_rows_and_rejects_incomplete_proof(
        tmp_path, monkeypatch, oracles, skip_case, skip_full):
    import json
    from types import SimpleNamespace
    from audioforge.tools import notation_acceptance as harness
    rows = harness.registry()
    monkeypatch.setattr(harness, "ROOT", tmp_path)
    monkeypatch.setattr(harness, "registry", lambda: rows)
    monkeypatch.setattr(harness.subprocess, "check_output", lambda *a, **kw: "a" * 40)

    def execute(command, **kwargs):
        if "import music21, xmlschema, lilypond" in command:
            return SimpleNamespace(returncode=0 if oracles else 1)
        report = next((c.split("=", 1)[1] for c in command if c.startswith("--junitxml=")), None)
        if report:
            skipped = "<skipped/>" if skip_case and "NXML-006" in report else ""
            Path(report).write_text(f"<testsuites><testsuite><testcase>{skipped}</testcase></testsuite></testsuites>")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(harness.subprocess, "run", execute)
    args = ["T3", str(tmp_path / "evidence")]
    if skip_full:
        args.append("--skip-full")
    assert harness.main(args) == (1 if skip_case or not oracles or skip_full else 0)
    result = json.loads((tmp_path / "evidence/T3/results.json").read_text())
    assert len(result) == 53 and len({r["id"] for r in result}) == 53
    statuses = {r["id"]: r["result"] for r in result}
    assert statuses["HARNESS-NORA-004"] == "N/A"
    if skip_case:
        assert statuses["HARNESS-NXML-006"] == "FAIL"
    if not oracles:
        assert statuses["HARNESS-NXML-001"] == "BLOCKED"
    if skip_full:
        assert statuses["HARNESS-NGATE-003"] == "BLOCKED"


def test_interop_generator_detects_and_repairs_drift(tmp_path, monkeypatch):
    from audioforge.tools import gen_interop
    monkeypatch.setattr(gen_interop, "ROOT", tmp_path)
    monkeypatch.setattr(gen_interop, "INTEROP", tmp_path / "INTEROP.md")
    assert gen_interop.main(["--check"]) == 1
    assert gen_interop.main(["--write"]) == 0
    assert gen_interop.main(["--check"]) == 0
    gen_interop.INTEROP.write_text("stale")
    assert gen_interop.main(["--check"]) == 1
