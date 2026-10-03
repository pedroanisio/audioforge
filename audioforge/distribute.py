"""Package a rendered WAV as a distributable, tagged MP3 with cover art.

This is a *delivery* step, deliberately outside AudioForge's byte-hash
determinism guarantee (lossy MP3 encoding is encoder-dependent — see the engine
README's "Honest limits"). It takes one of the engine's WAV renders, rasterizes
a cover from an SVG or PDF source, encodes to MP3, and writes ID3v2 metadata
with the embedded front cover.

Provenance carries through: when a render manifest sits next to the WAV, the
spec hash, engine version, and markers are folded into the ID3 comment so the
distributable file still points back at its deterministic source.

External tools (ffmpeg, cairosvg/convert/pdftoppm, Pillow) are treated as
untrusted: every step's output is verified and failures are loud and local, not
silent. Encoders/rasterizers are discovered at run time; a missing one is a
clear error naming what to install, never a silent skip.

  python -m audioforge.distribute to_be_alive.wav -o dist/to_be_alive.mp3 \\
      --cover cover.svg --title "To Be Alive" --artist "AudioForge" \\
      --album "Renders" --year 2026 --genre "Cinematic"
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

DEFAULT_BITRATE = "320k"
DEFAULT_COVER_SIZE = 1400
RASTER_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}


class DistributeError(RuntimeError):
    """A packaging step failed; the message names the cause and the fix."""


# --------------------------------------------------------------------------- #
# subprocess helpers
# --------------------------------------------------------------------------- #
def _run(cmd: list[str], *, what: str) -> subprocess.CompletedProcess:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as e:  # binary vanished between which() and run
        raise DistributeError(f"{what}: command not found: {cmd[0]} ({e})")
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-6:]
        raise DistributeError(
            f"{what} failed (exit {proc.returncode}):\n"
            + f"  $ {' '.join(cmd)}\n  " + "\n  ".join(tail))
    return proc


def _tool(name: str) -> str | None:
    return shutil.which(name)


# --------------------------------------------------------------------------- #
# cover: SVG / PDF / raster  ->  square JPEG
# --------------------------------------------------------------------------- #
def _rasterize(src: Path, out_png: Path, size: int) -> None:
    """Render a vector (SVG/PDF) or copy a raster source to a PNG."""
    ext = src.suffix.lower()
    if ext in RASTER_EXTS:
        shutil.copyfile(src, out_png) if ext == ".png" else _raster_to_png(
            src, out_png)
        return
    if ext == ".svg":
        if _tool("cairosvg"):
            _run(["cairosvg", str(src), "-o", str(out_png),
                  "--output-width", str(size), "--output-height", str(size)],
                 what="SVG rasterize (cairosvg)")
            return
        if _tool("rsvg-convert"):
            _run(["rsvg-convert", "-w", str(size), "-h", str(size),
                  "-o", str(out_png), str(src)], what="SVG rasterize (rsvg)")
            return
        if _tool("convert"):
            _run(["convert", "-background", "none", "-density", "300",
                  "-resize", f"{size}x{size}", str(src), str(out_png)],
                 what="SVG rasterize (ImageMagick)")
            return
        raise DistributeError(
            "no SVG rasterizer found — install one of: cairosvg "
            "(pip install cairosvg), rsvg-convert, or ImageMagick")
    if ext == ".pdf":
        if _tool("pdftoppm"):
            prefix = out_png.with_suffix("")
            _run(["pdftoppm", "-png", "-r", "200", "-f", "1", "-l", "1",
                  "-singlefile", str(src), str(prefix)],
                 what="PDF rasterize (pdftoppm)")
            produced = prefix.with_suffix(".png")
            if produced != out_png and produced.exists():
                produced.replace(out_png)
            return
        if _tool("convert"):
            _run(["convert", "-density", "200", f"{src}[0]", str(out_png)],
                 what="PDF rasterize (ImageMagick)")
            return
        raise DistributeError(
            "no PDF rasterizer found — install poppler (pdftoppm) or ImageMagick")
    raise DistributeError(
        f"unsupported cover source '{src.name}': expected .svg, .pdf, or a "
        f"raster image ({', '.join(sorted(RASTER_EXTS))})")


def _raster_to_png(src: Path, out_png: Path) -> None:
    from PIL import Image
    Image.open(src).convert("RGBA").save(out_png)


def prepare_cover(src: Path, out_jpg: Path, *, size: int = DEFAULT_COVER_SIZE,
                  fit: str = "contain", bg: str = "#0b0b0f") -> Path:
    """Rasterize the source and normalize it to a square JPEG suitable for
    ID3 front-cover embedding. ``contain`` letterboxes (keeps all art);
    ``cover`` center-crops to fill."""
    from PIL import Image

    if not src.exists():
        raise DistributeError(f"cover source not found: {src}")
    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / "cover.png"
        _rasterize(src, png, size)
        with Image.open(png) as source:
            rgba = source.convert("RGBA")
        background = Image.new("RGBA", rgba.size, bg)
        im = Image.alpha_composite(background, rgba).convert("RGB")
        w, h = im.size
        if fit == "cover":
            side = min(w, h)
            im = im.crop(((w - side) // 2, (h - side) // 2,
                          (w - side) // 2 + side, (h - side) // 2 + side))
            im = im.resize((size, size), Image.LANCZOS)
        else:  # contain: scale to fit, pad to square
            scale = min(size / w, size / h)
            im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))),
                           Image.LANCZOS)
            canvas = Image.new("RGB", (size, size), bg)
            canvas.paste(im, ((size - im.size[0]) // 2,
                              (size - im.size[1]) // 2))
            im = canvas
        im.save(out_jpg, "JPEG", quality=90, optimize=True)
    return out_jpg


# --------------------------------------------------------------------------- #
# metadata
# --------------------------------------------------------------------------- #
def load_manifest(wav: Path) -> dict:
    """The AudioForge render manifest next to the WAV, if present."""
    cand = wav.with_name(wav.stem + ".manifest.json")
    if cand.exists():
        try:
            return json.loads(cand.read_text())
        except (OSError, ValueError):
            return {}
    return {}


def build_metadata(args, manifest: dict) -> dict[str, str]:
    """ID3 tag map: CLI values win; the manifest fills provenance defaults."""
    tags: dict[str, str] = {}
    tags["title"] = args.title or manifest.get("id") or Path(args.input).stem
    if args.artist:
        tags["artist"] = args.artist
    if args.album:
        tags["album"] = args.album
    if args.year:
        tags["date"] = str(args.year)
    if args.genre:
        tags["genre"] = args.genre
    if args.track:
        tags["track"] = str(args.track)

    provenance = []
    if manifest.get("engine_version"):
        provenance.append(f"AudioForge engine {manifest['engine_version']}")
    if manifest.get("spec_hash"):
        provenance.append(f"spec {manifest['spec_hash'][:12]}")
    if manifest.get("plan_hash"):
        provenance.append(f"plan {manifest['plan_hash'][:12]}")
    markers = manifest.get("markers") or []
    if markers:
        provenance.append("markers " + ", ".join(
            f"{m['name']}@{m['time_s']:g}s" for m in markers))
    comment_parts = [p for p in (args.comment,) if p] + provenance
    if comment_parts:
        tags["comment"] = " · ".join(comment_parts)
    return tags


# --------------------------------------------------------------------------- #
# encode + verify
# --------------------------------------------------------------------------- #
def _wav_duration_s(wav: Path) -> float:
    with wave.open(str(wav), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def encode_mp3(wav: Path, out: Path, tags: dict[str, str], *,
               cover_jpg: Path | None, bitrate: str) -> None:
    ffmpeg = _tool("ffmpeg")
    if not ffmpeg:
        raise DistributeError("ffmpeg not found — install ffmpeg (libmp3lame) "
                              "to encode MP3")
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-y", "-i", str(wav)]
    if cover_jpg is not None:
        cmd += ["-i", str(cover_jpg), "-map", "0:a", "-map", "1:v",
                "-c:v", "copy", "-disposition:v", "attached_pic",
                "-metadata:s:v", "title=Album cover",
                "-metadata:s:v", "comment=Cover (front)"]
    else:
        cmd += ["-map", "0:a"]
    cmd += ["-c:a", "libmp3lame", "-b:a", bitrate,
            "-id3v2_version", "3", "-write_id3v1", "1"]
    for k, v in tags.items():
        cmd += ["-metadata", f"{k}={v}"]
    cmd += [str(out)]
    _run(cmd, what="MP3 encode (ffmpeg)")


def ffprobe(path: Path) -> dict:
    probe = _tool("ffprobe")
    if not probe:
        raise DistributeError("ffprobe not found (ships with ffmpeg)")
    p = _run([probe, "-v", "quiet", "-print_format", "json",
              "-show_format", "-show_streams", str(path)], what="ffprobe")
    return json.loads(p.stdout)


def verify(out: Path, tags: dict[str, str], *, want_cover: bool,
           src_duration_s: float) -> dict:
    """Treat the encoder's output as untrusted: confirm the file is a real MP3
    of the right length, carries the tags we asked for, and (if requested)
    embeds a cover. Raise loudly on any mismatch."""
    if not out.exists() or out.stat().st_size == 0:
        raise DistributeError(f"output not written or empty: {out}")
    info = ffprobe(out)
    streams = info.get("streams", [])
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    if not audio or audio[0].get("codec_name") != "mp3":
        raise DistributeError(
            f"verification: no MP3 audio stream in {out.name}")
    dur = float(info.get("format", {}).get("duration", 0.0))
    if abs(dur - src_duration_s) > 0.75:
        raise DistributeError(
            f"verification: duration drift — source {src_duration_s:.2f}s "
            f"vs mp3 {dur:.2f}s")
    have = {k.lower(): v for k, v in
            info.get("format", {}).get("tags", {}).items()}
    for k, v in tags.items():
        got = have.get(k.lower())
        if got is None or str(v) != str(got):
            raise DistributeError(
                f"verification: tag '{k}' missing or wrong "
                f"(wanted {v!r}, got {got!r})")
    cover = [s for s in streams
             if s.get("codec_type") == "video"
             and s.get("disposition", {}).get("attached_pic") == 1]
    if want_cover and not cover:
        raise DistributeError("verification: cover art not embedded")
    return {
        "bytes": out.stat().st_size,
        "duration_s": round(dur, 3),
        "bitrate_kbps": round(int(info["format"].get("bit_rate", 0)) / 1000),
        "has_cover": bool(cover),
        "tags": tags,
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def pack(args) -> dict:
    wav = Path(args.input)
    if wav.suffix.lower() != ".wav" or not wav.exists():
        raise DistributeError(f"input must be an existing .wav: {wav}")
    out = Path(args.output) if args.output else wav.with_suffix(".mp3")
    manifest = load_manifest(wav)
    tags = build_metadata(args, manifest)

    with tempfile.TemporaryDirectory() as td:
        cover_jpg = None
        if args.cover:
            cover_jpg = prepare_cover(
                Path(args.cover), Path(td) / "cover.jpg",
                size=args.cover_size, fit=args.cover_fit)
        # Encode and verify on the destination filesystem. Only verified bytes
        # replace the delivery, and failed attempts cannot destroy an old file.
        out.parent.mkdir(parents=True, exist_ok=True)
        fd, staging_name = tempfile.mkstemp(prefix=f".{out.stem}-", suffix=".mp3",
                                            dir=out.parent)
        os.close(fd)
        staging = Path(staging_name)
        try:
            encode_mp3(wav, staging, tags, cover_jpg=cover_jpg, bitrate=args.bitrate)
            report = verify(staging, tags, want_cover=cover_jpg is not None,
                            src_duration_s=_wav_duration_s(wav))
            staging.replace(out)
        finally:
            staging.unlink(missing_ok=True)
    report["output"] = str(out)
    return report


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="audioforge.distribute",
        description="Package a rendered WAV as a tagged MP3 with cover art.")
    ap.add_argument("input", help="source .wav (a render output)")
    ap.add_argument("-o", "--output", help="output .mp3 (default: alongside input)")
    ap.add_argument("--cover", help="cover source: .svg, .pdf, or a raster image")
    ap.add_argument("--cover-size", type=int, default=DEFAULT_COVER_SIZE,
                    help=f"square cover pixels (default {DEFAULT_COVER_SIZE})")
    ap.add_argument("--cover-fit", choices=("contain", "cover"),
                    default="contain",
                    help="contain=letterbox all art (default), cover=crop to fill")
    ap.add_argument("--bitrate", default=DEFAULT_BITRATE,
                    help=f"MP3 bitrate (default {DEFAULT_BITRATE})")
    ap.add_argument("--title")
    ap.add_argument("--artist")
    ap.add_argument("--album")
    ap.add_argument("--year")
    ap.add_argument("--genre")
    ap.add_argument("--track")
    ap.add_argument("--comment", help="prepended to auto provenance note")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = pack(args)
    except DistributeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    kb = report["bytes"] / 1024
    print(f"OK: {report['output']}  "
          f"({kb:.0f} KiB, {report['bitrate_kbps']}kbps, "
          f"{report['duration_s']:.1f}s, "
          f"cover={'yes' if report['has_cover'] else 'no'})")
    for k, v in report["tags"].items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
