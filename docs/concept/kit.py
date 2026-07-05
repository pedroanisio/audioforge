"""Vector design kit: one visual language for the concept paper and diagrams.

Pure SVG primitives with accurate text wrapping (measured against the real Fira
font files via Pillow) so hand-authored layouts never overflow. Pages and
diagrams are assembled as SVG, converted to vector PDF with cairosvg, and merged
with pdfunite — zero raster anywhere.
"""
from __future__ import annotations

import html
import subprocess
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

# --------------------------------------------------------------------------- #
# palette — limited, purposeful. one primary, two accents, neutrals.
# --------------------------------------------------------------------------- #
INK = "#171B22"          # primary text
INK_SOFT = "#3C444F"     # secondary text
SLATE = "#66707C"        # tertiary / captions
FAINT = "#98A0AB"        # de-emphasized
PAPER = "#FCFBF8"        # page background
PANEL = "#F4F1EA"        # panel fill
PANEL2 = "#ECE7DC"       # deeper panel
HAIR = "#DED9CE"         # hairlines
HAIR2 = "#CFC8B8"        # stronger hairline

PRIMARY = "#1F6F8B"      # deterministic contract — deep teal-blue
PRIMARY_D = "#12586F"
PRIMARY_T = "#E7F0F2"    # primary tint fill
AMBER = "#C6852F"        # creative intent / agents — warm
AMBER_T = "#F6EBD8"
VIOLET = "#6B5495"       # verification
VIOLET_T = "#ECE6F2"
TEAL = "#2E8B72"         # value / success
TEAL_T = "#E2F0EA"
DANGER = "#AF4E3C"       # risk
WARN = "#C07A2E"

# --------------------------------------------------------------------------- #
# type — Fira Sans / Fira Mono, measured for wrapping
# --------------------------------------------------------------------------- #
_FIRA = "/usr/share/fonts/opentype/fira/"
_FACES = {
    (400, False): "FiraSans-Regular.otf",
    (450, False): "FiraSans-Book.otf",
    (500, False): "FiraSans-Medium.otf",
    (600, False): "FiraSans-SemiBold.otf",
    (700, False): "FiraSans-Bold.otf",
    (400, True): "FiraSans-Italic.otf",
    (450, True): "FiraSans-BookItalic.otf",
    ("mono", False): "FiraMono-Regular.otf",
    ("mono-500", False): "FiraMono-Medium.otf",
}
SANS = "Fira Sans"
MONO = "Fira Mono"


@lru_cache(maxsize=256)
def _font(weight, italic, size_px: int) -> ImageFont.FreeTypeFont:
    face = _FACES.get((weight, italic)) or _FACES[(400, False)]
    return ImageFont.truetype(_FIRA + face, size_px)


def measure(text: str, size: float, weight=400, italic=False,
            spacing: float = 0.0) -> float:
    f = _font(weight, italic, max(4, round(size)))
    w = f.getlength(text)
    if spacing:
        w += spacing * max(0, len(text) - 1)
    return w * (size / max(4, round(size)))


def wrap(text: str, size: float, max_w: float, weight=400,
         italic=False) -> list[str]:
    out: list[str] = []
    for para in text.split("\n"):
        words = para.split(" ")
        line = ""
        for w in words:
            trial = w if not line else line + " " + w
            if measure(trial, size, weight, italic) <= max_w or not line:
                line = trial
            else:
                out.append(line)
                line = w
        out.append(line)
    return out


def esc(s: str) -> str:
    return html.escape(s, quote=True)


# --------------------------------------------------------------------------- #
# svg primitives
# --------------------------------------------------------------------------- #
def rect(x, y, w, h, fill="none", stroke="none", sw=1.0, rx=0, opacity=None,
         dash=None):
    o = f' opacity="{opacity}"' if opacity is not None else ""
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
            f'rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{o}{d}/>')


def line(x1, y1, x2, y2, stroke=HAIR, sw=1.0, dash=None, cap="butt"):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="{stroke}" stroke-width="{sw}" stroke-linecap="{cap}"{d}/>')


def circle(cx, cy, r, fill="none", stroke="none", sw=1.0):
    return (f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"/>')


def path(d, fill="none", stroke="none", sw=1.0, cap="round", join="round",
         dash=None):
    da = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="{cap}" stroke-linejoin="{join}"{da}/>')


def text(x, y, s, size=10.8, weight=400, fill=INK, anchor="start",
         italic=False, spacing=0.0, mono=False, upper=False):
    if upper:
        s = s.upper()
    fam = MONO if mono else SANS
    style = (f'font-family:{fam};font-size:{size}px;font-weight:{weight};'
             f'fill:{fill}')
    if italic:
        style += ";font-style:italic"
    if spacing:
        style += f";letter-spacing:{spacing}px"
    return (f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}" '
            f'style="{style}">{esc(s)}</text>')


def paragraph(x, y, s, size=10.8, max_w=400, weight=400, fill=INK_SOFT,
              leading=1.55, anchor="start", italic=False, spacing=0.0):
    """Return (svg, height). Left/anchor-aligned wrapped block."""
    lines = wrap(s, size, max_w, weight, italic)
    lh = size * leading
    parts = [text(x, y + i * lh, ln, size, weight, fill, anchor, italic,
                  spacing) for i, ln in enumerate(lines)]
    return "\n".join(parts), lh * len(lines)


def arrow(x1, y1, x2, y2, stroke=SLATE, sw=1.4, head=5.0, dash=None):
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    bx, by = x2 - head * math.cos(ang), y2 - head * math.sin(ang)
    a1 = ang + math.radians(150)
    a2 = ang - math.radians(150)
    p1 = (x2 + head * math.cos(a1), y2 + head * math.sin(a1))
    p2 = (x2 + head * math.cos(a2), y2 + head * math.sin(a2))
    seg = line(x1, y1, bx, by, stroke, sw, dash)
    hd = (f'<path d="M{x2:.2f},{y2:.2f} L{p1[0]:.2f},{p1[1]:.2f} '
          f'L{p2[0]:.2f},{p2[1]:.2f} Z" fill="{stroke}"/>')
    return seg + hd


def chip(x, y, label, fill=PANEL, tx=INK_SOFT, size=8.2, pad=7, h=17,
         weight=500, stroke="none", mono=False, spacing=0.4):
    w = measure(label.upper() if not mono else label, size, weight,
                spacing=spacing) + pad * 2
    r = (rect(x, y, w, h, fill=fill, stroke=stroke, sw=1, rx=h / 2)
         + text(x + w / 2, y + h / 2 + size * 0.36, label, size, weight, tx,
                "middle", spacing=spacing, mono=mono, upper=not mono))
    return r, w


def card(x, y, w, h, fill=PAPER, stroke=HAIR, sw=1.2, rx=9, accent=None,
         accent_w=3.0):
    s = rect(x, y, w, h, fill=fill, stroke=stroke, sw=sw, rx=rx)
    if accent:
        s += (f'<path d="M{x+rx},{y} h0 a{rx},{rx} 0 0 0 -{rx},{rx} '
              f'v{h-2*rx} a{rx},{rx} 0 0 0 {rx},{rx}" fill="none" '
              f'stroke="{accent}" stroke-width="{accent_w}"/>')
        s += rect(x, y + rx, accent_w, h - 2 * rx, fill=accent)
    return s


# --------------------------------------------------------------------------- #
# icons — simple geometric line marks, 1.6 stroke, drawn in a 24x24 box at (x,y)
# --------------------------------------------------------------------------- #
def icon(name, x, y, s=22, stroke=PRIMARY, sw=1.7):
    """Minimal line icons scaled into an s×s box at top-left (x,y). Every shape
    is emitted without its own stroke/fill so it inherits from the wrapping
    group — keeping the whole mark one consistent weight and colour."""
    def X(a):
        return x + a * s / 24
    def Y(b):
        return y + b * s / 24

    def P(pts, close=False):
        d = "M" + " L".join(f"{X(a):.2f},{Y(b):.2f}" for a, b in pts)
        return f'<path d="{d}{" Z" if close else ""}"/>'

    def L(a, b, c, d):
        return f'<line x1="{X(a):.2f}" y1="{Y(b):.2f}" x2="{X(c):.2f}" y2="{Y(d):.2f}"/>'

    def C(a, b, r, fill="none"):
        return f'<circle cx="{X(a):.2f}" cy="{Y(b):.2f}" r="{r*s/24:.2f}" fill="{fill}"/>'

    def RAW(d):
        return f'<path d="{d}"/>'

    d = ""
    if name == "contract":
        d = (P([(5, 3), (15, 3), (19, 7), (19, 21), (5, 21)], close=True)
             + P([(15, 3), (15, 7), (19, 7)])
             + L(8, 12, 16, 12) + L(8, 15.5, 15, 15.5))
    elif name == "hash":
        d = L(8, 4, 6, 20) + L(16, 4, 14, 20) + L(4, 9, 20, 9) + L(4, 15, 20, 15)
    elif name == "check":
        d = (P([(12, 3), (20, 6), (20, 12.5), (12, 21), (4, 12.5), (4, 6)], close=True)
             + P([(8.5, 12), (11, 14.5), (16, 8.8)]))
    elif name == "agent":
        d = (P([(12, 3), (20, 7.5), (20, 16.5), (12, 21), (4, 16.5), (4, 7.5)], close=True)
             + C(12, 12, 2.6))
    elif name == "person":
        d = C(12, 8, 3.4) + P([(5, 20), (5, 17.5), (7, 15.5), (17, 15.5), (19, 17.5), (19, 20)])
    elif name == "wave":
        d = P([(4, 12), (7, 6), (10, 18), (13, 4), (16, 20), (19, 12)])
    elif name == "layers":
        d = (P([(12, 4), (20, 8), (12, 12), (4, 8)], close=True)
             + P([(4, 12), (12, 16), (20, 12)]) + P([(4, 16), (12, 20), (20, 16)]))
    elif name == "branch":
        d = (C(6, 6, 2.4) + C(18, 7, 2.4) + C(6, 18, 2.4)
             + L(6, 8.4, 6, 15.6) + P([(6, 8.4), (12, 8.4), (16, 8)]))
    elif name == "shield":
        d = (P([(12, 3), (20, 6), (20, 12), (12, 21), (4, 12), (4, 6)], close=True)
             + L(12, 8, 12, 13.5) + C(12, 16.5, 0.7, stroke))
    elif name == "gauge":
        d = (RAW("M{:.2f},{:.2f} A{:.2f},{:.2f} 0 0 1 {:.2f},{:.2f}".format(
            X(4), Y(17), 8 * s / 24, 8 * s / 24, X(20), Y(17)))
            + L(12, 17, 16, 10) + C(12, 17, 0.8, stroke))
    elif name == "swap":
        d = (L(5, 9, 18, 9) + P([(15, 6), (18, 9), (15, 12)])
             + L(19, 15, 6, 15) + P([(9, 12), (6, 15), (9, 18)]))
    elif name == "box":
        d = (P([(12, 3), (20, 7), (20, 16), (12, 21), (4, 16), (4, 7)], close=True)
             + P([(4, 7), (12, 11), (20, 7)]) + L(12, 11, 12, 21))
    elif name == "eye":
        d = (RAW("M{:.2f},{:.2f} Q{:.2f},{:.2f} {:.2f},{:.2f} Q{:.2f},{:.2f} {:.2f},{:.2f} Z".format(
            X(4), Y(12), X(12), Y(4.5), X(20), Y(12), X(12), Y(19.5), X(4), Y(12)))
            + C(12, 12, 2.6))
    elif name == "scope":
        d = C(12, 12, 8) + L(6.3, 17.7, 17.7, 6.3)
    elif name == "compass":
        d = C(12, 12, 8.5) + P([(12, 8), (14.5, 14.5), (8, 12.5)], close=True)
    g = (f'<g fill="none" stroke="{stroke}" stroke-width="{sw}" '
         f'stroke-linecap="round" stroke-linejoin="round">{d}</g>')
    return g


# --------------------------------------------------------------------------- #
# page + PDF assembly
# --------------------------------------------------------------------------- #
PAGE_W, PAGE_H = 794, 1123          # A4 at 96 dpi (px)
MARGIN_X, MARGIN_TOP, MARGIN_BOT = 70, 74, 66
CONTENT_W = PAGE_W - 2 * MARGIN_X   # 654


def svg_doc(w, h, body, bg=PAPER):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">'
            f'{rect(0, 0, w, h, fill=bg) if bg else ""}{body}</svg>')


def to_pdf(svg_path: Path, pdf_path: Path):
    subprocess.run(["cairosvg", str(svg_path), "-o", str(pdf_path)],
                   check=True, capture_output=True, text=True)


def merge_pdfs(parts: list[Path], out: Path):
    subprocess.run(["pdfunite", *[str(p) for p in parts], str(out)],
                   check=True, capture_output=True, text=True)


def rasterize(svg_path: Path, png_path: Path, width=900):
    subprocess.run(["cairosvg", str(svg_path), "-o", str(png_path),
                    "--output-width", str(width)], check=True,
                   capture_output=True, text=True)
