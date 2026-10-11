"""Tests for content-pinned .af includes (audioforge.includes)."""
import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audioforge import AudioForge, render, spec_hash  # noqa: E402
from audioforge.includes import IncludeError, resolve_includes  # noqa: E402

_RIFF = """motif riff {
  C4 @ 0b for 1b vel 0.8
  E4 @ 1b for 1b vel 0.8
  G4 @ 2b for 2b vel 0.9
}
"""

_ASSET = """asset song {{
  kind: cue
  duration: 4s
  tempo: 120bpm
  key: C major
  layer lead : notes {{
    osc: saw
    env: a=0.01s d=0.2s s=0.5 r=0.2s
    play riff @ 0b
  }}
  master {{ peak: -1db }}
}}
"""


def _write(d: Path, name: str, text: str) -> str:
    """Write a fragment and return its sha256 (for pinning)."""
    p = d / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _song(d: Path, sha: str, path: str = "lib.afi") -> Path:
    src = f'import "{path}" @ sha256:{sha}\n\n' + _ASSET.format()
    p = d / "song.af"
    p.write_text(src)
    return p


def test_import_equals_inline_hash_and_audio(tmp_path):
    """The core guarantee: a patch built from an import is byte-identical to the
    same patch written inline — same spec hash, same audio."""
    sha = _write(tmp_path, "lib.afi", _RIFF)
    imported = AudioForge().load_file(_song(tmp_path, sha))
    inline_src = _ASSET.format().replace(
        "  layer lead", "  " + _RIFF.replace("\n", "\n  ").rstrip() + "\n  layer lead")
    inline = AudioForge().compile(inline_src)
    assert imported.ok and inline.ok, [d.message for d in
                                       imported.diagnostics + inline.diagnostics]
    si, sl = imported.assets[0].spec, inline.assets[0].spec
    assert spec_hash(si) == spec_hash(sl)
    assert np.array_equal(render(si)[0], render(sl)[0])


def test_imports_recorded_as_provenance(tmp_path):
    sha = _write(tmp_path, "lib.afi", _RIFF)
    res = AudioForge().load_file(_song(tmp_path, sha))
    imports = res.assets[0].spec["_meta"]["imports"]
    assert imports[0]["path"] == "lib.afi"
    assert imports[0]["sha256"] == sha


def test_hash_mismatch_refuses(tmp_path):
    _write(tmp_path, "lib.afi", _RIFF)
    wrong = "0" * 64
    res = AudioForge().load_file(_song(tmp_path, wrong))
    assert not res.ok
    assert any("hash mismatch" in d.message for d in res.diagnostics)


def test_missing_import_refuses(tmp_path):
    res = AudioForge().load_file(_song(tmp_path, "a" * 64))
    assert not res.ok
    assert any("not found" in d.message for d in res.diagnostics)


def test_collision_refuses(tmp_path):
    sha = _write(tmp_path, "lib.afi", _RIFF)
    # the asset also defines `riff` -> collides with the imported one
    src = (f'import "lib.afi" @ sha256:{sha}\n\n'
           "asset song {\n  kind: cue\n  duration: 4s\n  tempo: 120bpm\n"
           "  key: C major\n  motif riff { C4 @ 0b for 1b }\n"
           "  layer l : notes { osc: saw\n    env: a=0.01s d=0.1s s=0.5 r=0.1s\n"
           "    play riff @ 0b }\n  master { peak: -1db }\n}\n")
    p = tmp_path / "song.af"
    p.write_text(src)
    res = AudioForge().load_file(p)
    assert not res.ok
    assert any("collides" in d.message for d in res.diagnostics)


def test_cycle_refuses(tmp_path):
    # a.afi imports b.afi imports a.afi
    sha_a_placeholder = "0" * 64
    (tmp_path / "a.afi").write_text(
        f'import "b.afi" @ sha256:{sha_a_placeholder}\nmotif ma {{ C4 @ 0b for 1b }}\n')
    sha_b = _write(tmp_path, "b.afi",
                   'import "a.afi" @ sha256:%s\nmotif mb { D4 @ 0b for 1b }\n'
                   % hashlib.sha256((tmp_path / "a.afi").read_bytes()).hexdigest())
    # fix a.afi's pin of b now that b exists
    (tmp_path / "a.afi").write_text(
        f'import "b.afi" @ sha256:{sha_b}\nmotif ma {{ C4 @ 0b for 1b }}\n')
    sha_a = hashlib.sha256((tmp_path / "a.afi").read_bytes()).hexdigest()
    # b pins a with the now-final hash
    (tmp_path / "b.afi").write_text(
        f'import "a.afi" @ sha256:{sha_a}\nmotif mb {{ D4 @ 0b for 1b }}\n')
    sha_b2 = hashlib.sha256((tmp_path / "b.afi").read_bytes()).hexdigest()
    (tmp_path / "a.afi").write_text(
        f'import "b.afi" @ sha256:{sha_b2}\nmotif ma {{ C4 @ 0b for 1b }}\n')
    sha_a2 = hashlib.sha256((tmp_path / "a.afi").read_bytes()).hexdigest()
    src = (f'import "a.afi" @ sha256:{sha_a2}\n\nasset s {{\n kind: cue\n'
           " duration: 2s\n tempo: 120bpm\n key: C major\n"
           " layer l : notes { osc: sine\n  env: a=0.01s d=0.1s s=0.5 r=0.1s\n"
           "  play ma @ 0b }\n master { peak: -1db }\n}\n")
    p = tmp_path / "main.af"
    p.write_text(src)
    with pytest.raises(IncludeError, match="cyclic"):
        resolve_includes(p.read_text(), tmp_path)


def test_diamond_dedups(tmp_path):
    base_sha = _write(tmp_path, "base.afi", "motif base { C4 @ 0b for 1b }\n")
    a_sha = _write(tmp_path, "a.afi",
                   f'import "base.afi" @ sha256:{base_sha}\n'
                   "motif a_riff { E4 @ 0b for 1b }\n")
    b_sha = _write(tmp_path, "b.afi",
                   f'import "base.afi" @ sha256:{base_sha}\n'
                   "motif b_riff { G4 @ 0b for 1b }\n")
    src = (f'import "a.afi" @ sha256:{a_sha}\n'
           f'import "b.afi" @ sha256:{b_sha}\n\n'
           "asset s {\n kind: cue\n duration: 2s\n tempo: 120bpm\n key: C major\n"
           " layer l : notes { osc: sine\n  env: a=0.01s d=0.1s s=0.5 r=0.1s\n"
           "  play base @ 0b\n  play a_riff @ 1b\n  play b_riff @ 1b }\n"
           " master { peak: -1db }\n}\n")
    p = tmp_path / "main.af"
    p.write_text(src)
    # base reached via both a and b, but included exactly once -> no collision
    res = AudioForge().load_file(p)
    assert res.ok, [d.message for d in res.diagnostics]
    resolved = resolve_includes(src, tmp_path).source
    assert resolved.count("motif base") == 1


def test_expand_strips_imports_and_recompiles_identically(tmp_path):
    sha = _write(tmp_path, "lib.afi", _RIFF)
    p = _song(tmp_path, sha)
    resolved = resolve_includes(p.read_text(), tmp_path).source
    assert "import " not in resolved
    a = AudioForge().load_file(p).assets[0].spec
    b = AudioForge().compile(resolved).assets[0].spec
    assert spec_hash(a) == spec_hash(b)


def test_import_after_asset_refuses(tmp_path):
    sha = _write(tmp_path, "lib.afi", _RIFF)
    src = _ASSET.format() + f'\nimport "lib.afi" @ sha256:{sha}\n'
    with pytest.raises(IncludeError, match="before any asset"):
        resolve_includes(src, tmp_path)


def test_absolute_path_refuses(tmp_path):
    with pytest.raises(IncludeError, match="relative"):
        resolve_includes(f'import "/etc/x.afi" @ sha256:{"0" * 64}\n', tmp_path)


def test_bare_string_without_base_dir_errors(tmp_path):
    sha = _write(tmp_path, "lib.afi", _RIFF)
    # compiling a string (no file context) with an import cannot resolve paths
    res = AudioForge().compile(f'import "lib.afi" @ sha256:{sha}\n' + _ASSET.format())
    assert not res.ok
    assert any("file context" in d.message for d in res.diagnostics)
