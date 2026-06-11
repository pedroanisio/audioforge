import json
from pathlib import Path

from audioforge import cli


class _Diag:
    def __init__(self, severity, message):
        self.severity = severity
        self.message = message


class _Asset:
    def __init__(self, spec=None, diagnostics=None):
        self.spec = spec or {"id": "fake"}
        self._diagnostics = diagnostics or []
        self.intensity = None

    def validate(self, resolve=True):
        return self._diagnostics

    def to_json(self):
        return json.dumps(self.spec, sort_keys=True)

    def to_dsl(self):
        return "asset fake {\n  kind: cue\n}\n"

    def with_intensity(self, value):
        clone = _Asset(self.spec, self._diagnostics)
        clone.intensity = value
        return clone

    def export(self, out, preset=None, stems=False, analyze=False):
        return {
            "file": str(Path(out) / "fake.wav"),
            "output_sha256": "a" * 64,
            "preset": preset,
            "stems": stems,
            "analyze": analyze,
            "intensity": self.intensity,
        }

    def export_cutdowns(self, out, preset=None):
        return [
            {
                "file": str(Path(out) / "fake_15.wav"),
                "cutdown": {"length_s": 15},
                "preset": preset,
            }
        ]


def test_cli_validate_compile_decompile_and_grammar(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli, "_assets", lambda *args, **kwargs: [_Asset()])
    spec = tmp_path / "fake.af"
    spec.write_text("asset fake {\n  kind: cue\n}\n")

    assert cli.main(["validate", str(spec), "--no-resolve"]) == 0
    assert "OK: valid (structural only)" in capsys.readouterr().out

    assert cli.main(["compile", str(spec)]) == 0
    assert '"id": "fake"' in capsys.readouterr().out

    assert cli.main(["decompile", str(spec)]) == 0
    assert "asset fake" in capsys.readouterr().out

    assert cli.main(["grammar", "--format", "gbnf"]) == 0
    assert "root ::=" in capsys.readouterr().out


def test_cli_validate_reports_errors(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        cli,
        "_assets",
        lambda *args, **kwargs: [_Asset(diagnostics=[_Diag("error", "bad pin")])],
    )
    spec = tmp_path / "fake.af"
    spec.write_text("asset fake {\n  kind: cue\n}\n")

    import pytest

    with pytest.raises(SystemExit) as exc:
        cli.main(["validate", str(spec)])
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "ERROR: bad pin" in out
    assert "FAILED: not render-ready" in out


def test_cli_render_campaign_and_batch_use_asset_exports(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli, "_assets", lambda *args, **kwargs: [_Asset()])
    spec = tmp_path / "fake.af"
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    spec.write_text("asset fake {\n  kind: cue\n}\n")
    (specs_dir / "one.json").write_text("{}")

    assert cli.main(["render", str(spec), "-o", str(tmp_path), "--preset", "p", "--stems", "--analyze", "--intensity", "0.5"]) == 0
    render_out = capsys.readouterr().out
    assert '"preset": "p"' in render_out
    assert '"intensity": 0.5' in render_out

    assert cli.main(["campaign", str(spec), "-o", str(tmp_path), "--preset", "p", "--intensity", "0.7"]) == 0
    campaign_out = capsys.readouterr().out
    assert "full" in campaign_out
    assert "15s cut" in campaign_out

    assert cli.main(["batch", str(specs_dir), "-o", str(tmp_path)]) == 0
    assert "aaaaaaaaaaaaaaaa" in capsys.readouterr().out


def test_cli_ingest_and_libgen(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        "audioforge.samples.ingest",
        lambda directory: [
            {"file": "bad.flac", "error": "unsupported"},
            {
                "file": "hit.wav",
                "duration_s": 1.0,
                "guess": "impact",
                "sha256": "b" * 64,
                "snippet": "layer hit : sample {\\n}",
            },
        ],
    )
    monkeypatch.setattr(
        "audioforge.library.generate_manifest",
        lambda directory, name, version, license_str: {
            "name": name,
            "version": version,
            "license": license_str,
            "files": [{"path": "hit.wav"}],
            "instruments": {},
            "manifest_sha256": "c" * 64,
        },
    )

    catalog = tmp_path / "catalog.json"
    assert cli.main(["ingest", str(tmp_path), "-o", str(catalog)]) == 0
    ingest_out = capsys.readouterr().out
    assert "SKIP bad.flac" in ingest_out
    assert "catalog ->" in ingest_out
    assert catalog.exists()

    assert cli.main(["libgen", str(tmp_path), "--name", "kit", "--version", "1.2.3", "--license", "CC0"]) == 0
    libgen_out = capsys.readouterr().out
    assert "library 'kit' v1.2.3 (CC0)" in libgen_out
    assert "pin: kit@" in libgen_out
