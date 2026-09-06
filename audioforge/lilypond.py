"""Optional LilyPond engraving backend for `audioforge score --engrave` (ADR-0009, D4).

AudioForge does not engrave. When the `engrave` extra (the `lilypond` PyPI wheel) is
installed, this module hands the *notated* MusicXML export to `musicxml2ly` and
`lilypond` and returns the PDF they produce, attributing the result to LilyPond. Without
the extra it raises :class:`EngraverUnavailable` with the install hint; the CLI maps that
to exit code 3 (optional dependency missing).
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .musicxml import export_notated_musicxml

INSTALL_HINT = "score: install the engrave extra (uv pip install -e '.[engrave]') to engrave with LilyPond; " \
               "without it `audioforge score` draws the proportional proof sheet"
EXIT_OPTIONAL_DEPENDENCY_MISSING = 3


class EngraverUnavailable(RuntimeError):
    """The `lilypond` wheel is not installed (or ships no usable binaries)."""


@dataclass
class EngraveResult:
    pdf: Path
    lilypond_version: str
    warnings: list[str] = field(default_factory=list)
    ly: Path | None = None


def executables() -> tuple[Path, Path]:
    """(lilypond, musicxml2ly) from the wheel, or raise EngraverUnavailable."""
    try:
        import lilypond   # type: ignore
    except ImportError as exc:
        raise EngraverUnavailable(INSTALL_HINT) from exc
    exe = Path(lilypond.executable())
    musicxml2ly = exe.parent / "musicxml2ly"
    if not exe.exists() or not musicxml2ly.exists():
        raise EngraverUnavailable(f"{INSTALL_HINT} (wheel found but binaries missing at {exe.parent})")
    return exe, musicxml2ly


def lilypond_version() -> str:
    exe, _ = executables()
    out = subprocess.run([str(exe), "--version"], capture_output=True, text=True, timeout=120).stdout
    m = re.search(r"LilyPond\s+([\d.]+)", out)
    return m.group(1) if m else out.strip().splitlines()[0] if out.strip() else "unknown"


def _noise(text: str) -> list[str]:
    return [line for line in text.splitlines() if re.search(r"\b(warning|error)\b\s*:", line, re.IGNORECASE)]


def engrave(spec: dict, out_pdf: str | Path, *, keep_ly: bool = False, timeout: float = 600.0) -> EngraveResult:
    """Notated MusicXML → musicxml2ly → lilypond → `out_pdf`. Raises EngraverUnavailable
    without the extra and RuntimeError (with the tool's stderr) when a tool fails."""
    exe, musicxml2ly = executables()
    out_pdf = Path(out_pdf)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    xml = export_notated_musicxml(spec)
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        stem = re.sub(r"[^A-Za-z0-9_]+", "_", str(spec.get("id", "score"))) or "score"
        xml_path = work / f"{stem}.musicxml"
        xml_path.write_text(xml)
        ly = work / f"{stem}.ly"
        r1 = subprocess.run([str(musicxml2ly), "-o", str(ly), str(xml_path)],
                            capture_output=True, text=True, timeout=timeout)
        if r1.returncode != 0:
            raise RuntimeError(f"musicxml2ly failed ({r1.returncode}):\n{r1.stderr[-2000:]}")
        r2 = subprocess.run([str(exe), "-dno-point-and-click", "-o", str(work / stem), str(ly)],
                            capture_output=True, text=True, timeout=timeout)
        produced = work / f"{stem}.pdf"
        if r2.returncode != 0 or not produced.exists():
            raise RuntimeError(f"lilypond failed ({r2.returncode}):\n{r2.stderr[-2000:]}")
        out_pdf.write_bytes(produced.read_bytes())
        kept = None
        if keep_ly:
            kept = out_pdf.with_suffix(".ly")
            kept.write_text(ly.read_text())
    return EngraveResult(pdf=out_pdf, lilypond_version=lilypond_version(),
                         warnings=_noise(r1.stderr + r2.stderr), ly=kept)
