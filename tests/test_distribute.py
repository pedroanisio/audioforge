"""Distributable-MP3 packaging.

The packager wraps external tools (ffmpeg, an SVG rasterizer, Pillow); these
tests exercise the real pipeline and are skipped when a tool is absent rather
than faked, so a pass means the delivery step actually works here.
"""
from __future__ import annotations

import shutil
import struct
import wave
from pathlib import Path

import pytest

from audioforge import distribute as D

pytestmark = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="ffmpeg/ffprobe not installed")

_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300">'
        '<rect width="300" height="300" fill="#123"/>'
        '<circle cx="150" cy="150" r="90" fill="#f6c"/></svg>')


def _sine_wav(path: Path, seconds: float = 1.0, sr: int = 8000) -> None:
    import math
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        frames = bytearray()
        for i in range(int(seconds * sr)):
            v = int(12000 * math.sin(2 * math.pi * 220 * i / sr))
            frames += struct.pack("<h", v)
        w.writeframes(bytes(frames))


def _args(tmp: Path, **over):
    argv = [str(over.pop("input")), "-o", str(over.pop("output"))]
    for k, v in over.items():
        argv += [f"--{k.replace('_', '-')}", str(v)]
    return D.build_parser().parse_args(argv)


def _has_svg_rasterizer() -> bool:
    """A rasterizer that can actually read SVG here — not merely a binary on
    PATH: ImageMagick's `convert` reads SVG only through a delegate
    (librsvg/MSVG), so its presence alone does not mean the step works."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "probe.svg"
        src.write_text(_SVG)
        try:
            D._rasterize(src, Path(tmp) / "probe.png", 16)
        except D.DistributeError:
            return False
        return (Path(tmp) / "probe.png").is_file()


def test_pack_wav_only(tmp_path: Path):
    wav = tmp_path / "tone.wav"
    _sine_wav(wav)
    out = tmp_path / "tone.mp3"
    report = D.pack(_args(tmp_path, input=wav, output=out,
                          title="Tone", artist="Tester"))
    assert out.exists() and report["has_cover"] is False
    assert abs(report["duration_s"] - 1.0) < 0.75
    assert report["tags"]["title"] == "Tone"
    # verify() already ffprobe-confirmed the tags; re-read to be explicit
    tags = D.ffprobe(out)["format"]["tags"]
    assert tags["title"] == "Tone" and tags["artist"] == "Tester"


@pytest.mark.skipif(not _has_svg_rasterizer(), reason="no SVG rasterizer")
def test_pack_with_svg_cover(tmp_path: Path):
    wav = tmp_path / "tone.wav"
    _sine_wav(wav)
    (tmp_path / "cover.svg").write_text(_SVG)
    out = tmp_path / "tone.mp3"
    report = D.pack(_args(tmp_path, input=wav, output=out,
                          cover=tmp_path / "cover.svg", title="Cover Tone"))
    assert report["has_cover"] is True
    streams = D.ffprobe(out)["streams"]
    assert any(s.get("disposition", {}).get("attached_pic") == 1
               for s in streams)


def test_manifest_provenance_in_comment(tmp_path: Path):
    wav = tmp_path / "cue.wav"
    _sine_wav(wav)
    (tmp_path / "cue.manifest.json").write_text(
        '{"id": "cue", "engine_version": "2.16.0", '
        '"spec_hash": "abcdef0123456789", "markers": '
        '[{"name": "hit", "time_s": 0.5}]}')
    out = tmp_path / "cue.mp3"
    report = D.pack(_args(tmp_path, input=wav, output=out))
    assert report["tags"]["title"] == "cue"          # from manifest id
    comment = report["tags"]["comment"]
    assert "engine 2.16.0" in comment and "spec abcdef012345" in comment
    assert "hit@0.5s" in comment


def test_bad_input_is_loud(tmp_path: Path):
    args = _args(tmp_path, input=tmp_path / "nope.wav", output=tmp_path / "x.mp3")
    with pytest.raises(D.DistributeError, match="existing .wav"):
        D.pack(args)


def test_unsupported_cover_is_loud(tmp_path: Path):
    bad = tmp_path / "c.txt"
    bad.write_text("not an image")
    with pytest.raises(D.DistributeError, match="unsupported cover source"):
        D.prepare_cover(bad, tmp_path / "o.jpg")
