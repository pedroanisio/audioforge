"""Draw a compiled AudioForge spec as a proportional *proof sheet* PDF.

This is not a typeset score (ADR-0009): LilyPond typesetting is delegated to
`audioforge/lilypond.py` (`audioforge score --lilypond-pdf`, engine 3.1 line). The
proof sheet exists to show what the engine knows and a staff cannot.

This lives **outside the render path** — like analysis and the MIDI/MusicXML
interop, it observes the IR and produces a human-facing artifact; it never feeds
back into synthesis, so determinism is untouched.

It is not a generic notation dump. A normal score shows notes; an AudioForge
score also shows what the engine knows that a page of staves cannot:

  · a **stage plot** — every layer's `seat:` azimuth/distance in the hall;
  · a per-system **intensity ribbon** — the deterministic dramatic arc;
  · **dynamics** (pp…fff) and **performance** marks (articulation, and
    `humanize` — e.g. *rigid* where humanize is 0, "oppression does not breathe");
  · a **provenance block** — engine version and the content-addressed library /
    hall pins: the byte-identical, verifiable moat.

Notation style is *proportional*: staves and clefs give pitch, barlines give
meter, and each note is a notehead at (beat, pitch) with a duration bar — honest
to the event-based IR. Backend: matplotlib (vector PDF); music glyphs from Noto
Music when present.
"""
from __future__ import annotations

import math
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.patches import Ellipse, Wedge, Polygon, Rectangle

from . import theory

from .version import ENGINE_VERSION

# ----------------------------------------------------------------- fonts ----
# The clef glyphs need a music font. matplotlib measures every text's line metrics
# with the probe string "lp" in the text's own font, and music fonts carry no Latin
# letters — so the music font is listed with a Latin fallback family (matplotlib's
# per-glyph fallback, >= 3.6) instead of alone. That is what silenced the
# "Glyph 108 (l) missing from font(s) Noto Music" warnings (RN-P-002, HARNESS-NENG-004);
# no warning filter hides them any more.
_NOTO = None
for _cand in ("Noto Music", "Bravura", "Leland"):
    try:
        fm.findfont(_cand, fallback_to_default=False)
        _NOTO = fm.FontProperties(family=[_cand, "DejaVu Sans"])
        break
    except Exception:
        continue
_SERIF = fm.FontProperties(family="serif")
_ACCFONT = fm.FontProperties(family="DejaVu Sans")     # has ♯ ♭ ♮

_CLEF = {"treble": "\U0001D11E", "bass": "\U0001D122"}
_ACC = {1: "♯", -1: "♭", 0: "♮"}
_DYN = [("ppp", .10), ("pp", .22), ("p", .35), ("mp", .48),
        ("mf", .60), ("f", .74), ("ff", .87), ("fff", 1.0)]

# ----------------------------------------------------------------- theory ---
_LETTER = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}
_FLATS = ["B", "E", "A", "D", "G", "C", "F"]
_SHARPS = ["F", "C", "G", "D", "A", "E", "B"]
_MAJ = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7,
        "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5, "Gb": -6, "Cb": -7}
_MIN = {"A": 0, "E": 1, "B": 2, "F#": 3, "C#": 4, "G#": 5, "D#": 6,
        "D": -1, "G": -2, "C": -3, "F": -4, "Bb": -5, "Eb": -6, "Ab": -7}
_TREBLE_MID = 4 * 7 + 6
_BASS_MID = 3 * 7 + 1
_MIDDLE_C = 4 * 7 + 0


def _parse_pitch(name):
    m = re.match(r"^([A-Ga-g])([#b]?)(-?\d+)$", name)
    if not m:
        return None
    return (m.group(1).upper(), {"#": 1, "b": -1, "": 0}[m.group(2)],
            int(m.group(3)),
            int(m.group(3)) * 7 + _LETTER[m.group(1).upper()])


def _event_pitch(ev):
    name = ev.get("note")
    if name is None and "freq_hz" in ev and ev["freq_hz"]:
        name = theory.semis_to_note(round(57 + 12 * math.log2(ev["freq_hz"] / 440.0)))
    return name


def _key_sig(tonic, mode):
    f = (_MIN if (mode or "").lower() == "minor" else _MAJ).get(tonic, 0)
    exp = {}
    if f < 0:
        for L in _FLATS[:-f]:
            exp[L] = -1
    elif f > 0:
        for L in _SHARPS[:f]:
            exp[L] = 1
    return f, exp


def _dyn_mark(v):
    return min(_DYN, key=lambda d: abs(d[1] - v))[0]


# ----------------------------------------------------------------- model ----
_PRETTY = {
    "peso": "O Peso", "peso_sub": "O Peso 8vb", "voz": "A Voz",
    "voz_oitava": "A Voz 8vb", "murmurio_1": "Murmúrio I",
    "murmurio_2": "Murmúrio II", "embate_trem": "Embate trem.",
    "embate_defesa": "Embate marc.", "vozes_altas": "Vozes alt.",
    "vozes_baixas": "Vozes grav.",
}


def _pretty(name):
    return _PRETTY.get(name, name.replace("_", " ").title())


def _title_from_id(aid):
    """Title-case an asset id, preserving roman-numeral movement markers."""
    return " ".join(tok.upper() if re.fullmatch(r"[ivx]+", tok, re.I)
                    else tok.capitalize() for tok in aid.split("_"))


def _source(lay):
    if lay.get("instrument"):
        return str(lay["instrument"])
    osc = lay.get("osc")
    if osc:
        u = lay.get("unison")
        return f"{osc}×{int(u)}" if u else osc
    return lay.get("type", "")


def _staves(spec):
    out = []
    for lay in spec.get("layers", []):
        notes = []
        for ev in lay.get("notes", []) or []:
            name = _event_pitch(ev)
            p = _parse_pitch(name) if name else None
            if not p:
                continue
            notes.append({"diat": p[3], "letter": p[0], "acc": p[1],
                          "beat": float(ev.get("start_beat", 0.0)),
                          "dur": float(ev.get("dur_beats", 1.0)),
                          "vel": float(ev.get("vel", 0.7))})
        if not notes:
            continue
        diats = sorted(n["diat"] for n in notes)
        hz = lay.get("humanize")
        rigid = isinstance(hz, dict) and hz.get("timing_s", 1) == 0
        out.append({
            "name": lay.get("name", ""), "label": _pretty(lay.get("name", "")),
            "clef": "treble" if diats[len(diats) // 2] >= _MIDDLE_C else "bass",
            "notes": notes, "seat": lay.get("seat"),
            "art": lay.get("articulation"), "rigid": rigid,
            "dynamic": lay.get("dynamic"), "source": _source(lay),
        })
    return out


# ------------------------------------------------------------- geometry -----
SS = 0.085                       # staff space (inches)
STAFF_H = 4 * SS
PAGE_W, PAGE_H = 11.0, 8.5       # landscape Letter
TM = BM = 0.5                    # page top/bottom margin
LM, RM = 1.82, 0.45             # left (label+clef+key) / right
RIBBON_H = 0.30                  # intensity lane height
HEAD = RIBBON_H + 0.30           # system head: ribbon + rehearsal marks
SYS_GAP = 0.34
BEATS_PER_BAR = 4

_INK = "#1a1a1a"
_FAINT = "#9a9aa2"
_ACCENT = "#7d2b2b"
_ARC = "#c9c9d0"
_RIB = "#b5544f"


def _clamp_lines(lines: list[str], max_lines: int) -> list[str]:
    """Clamp a wrapped text block to at most ``max_lines`` lines so it cannot
    overrun its allotted column and collide with whatever sits below it. When
    truncation happens the last kept line gets an ellipsis so the reader knows
    the blurb continues (the full text lives in the source .af header)."""
    if max_lines < 1:
        return []
    if len(lines) <= max_lines:
        return list(lines)
    kept = list(lines[:max_lines])
    kept[-1] = kept[-1].rstrip(" .·–—") + " …"
    return kept


def _declutter(ys: list[float], min_gap: float) -> list[float]:
    """Spread label anchor positions so consecutive ones differ by at least
    ``min_gap``, preserving each item's identity. Resolves vertical overlap of
    labels for sources seated at near-identical azimuth/distance.

    Returns a list parallel to ``ys`` (input order) with adjusted positions.
    Items are processed in ascending order and pushed upward only as needed,
    then the whole block is recentred on the original mean so it does not
    drift off one edge."""
    n = len(ys)
    if n <= 1:
        return list(ys)
    order = sorted(range(n), key=lambda i: ys[i])
    adj = [0.0] * n
    prev = None
    for i in order:
        y = ys[i] if prev is None else max(ys[i], prev + min_gap)
        adj[i] = y
        prev = y
    # recentre to keep the cluster around its original centroid
    shift = (sum(ys) - sum(adj)) / n
    return [a + shift for a in adj]


def _layout(n_staves, bars_per_sys):
    beats = bars_per_sys * BEATS_PER_BAR
    width = PAGE_W - LM - RM
    beatw = width / beats
    usable = PAGE_H - TM - BM
    block = min(0.82, max(0.40, (usable - HEAD - 0.25) / n_staves))
    sys_h = HEAD + n_staves * block
    per_page = max(1, int((usable + SYS_GAP) // (sys_h + SYS_GAP)))
    return dict(beats=beats, width=width, beatw=beatw, usable=usable,
                block=block, sys_h=sys_h, per_page=per_page)


def _y_of(diat, clef, mid_y):
    ref = _TREBLE_MID if clef == "treble" else _BASS_MID
    return mid_y + (diat - ref) * (SS / 2.0)


# --------------------------------------------------------------- glyphs -----
def _note(ax, x, y, dur, vel, beatw, xmax):
    """Proportional glyph: a uniform onset notehead + a bar whose *length* is
    the duration. No filled/open/whole distinction and no stems — those imply
    metric figures, but these durations are non-metric by design. Duration is
    read off the bar against the beat grid; silence is the space between bars."""
    alpha = 0.5 + 0.5 * max(0.0, min(1.0, vel))
    xend = min(x + dur * beatw, xmax)
    h = SS * 0.55
    if xend - x > 0.025:                          # the sustain bar = duration
        ax.add_patch(Rectangle((x, y - h / 2), xend - x, h, facecolor=_INK,
                               edgecolor="none", alpha=0.22 * (0.6 + alpha),
                               zorder=3))
    ax.add_patch(Ellipse((x, y), SS * 1.0, SS * 0.8, angle=-22,
                         facecolor=_INK, edgecolor=_INK, lw=0.7, alpha=alpha,
                         zorder=5))


def _ledger(ax, x, diat, ref, mid_y):
    off = diat - ref
    rng = range(6, off + 1, 2) if off > 4 else range(-6, off - 1, -2) if off < -4 else []
    for d in rng:
        yy = mid_y + d * (SS / 2)
        ax.add_line(Line2D([x - SS * 0.95, x + SS * 0.95], [yy, yy],
                           color=_INK, lw=0.7, zorder=2))


def _accidental(ax, x, y, n, keyexp):
    if n["acc"] != keyexp.get(n["letter"], 0):
        ax.text(x - SS * 1.6, y, _ACC[n["acc"]], fontproperties=_ACCFONT,
                fontsize=11, color=_INK, va="center", ha="center", zorder=6)


def _keysig(ax, clef, mid_y, x, ktype):
    if not ktype:
        return
    order = _FLATS if ktype < 0 else _SHARPS
    base = 4 if clef == "treble" else 3
    ref = _TREBLE_MID if clef == "treble" else _BASS_MID
    xi = x
    for L in order[:abs(ktype)]:
        octv = base if _LETTER[L] >= _LETTER["E"] else base + 1
        if clef == "bass":
            octv -= 1
        diat = octv * 7 + _LETTER[L]
        while diat - ref > 5:
            diat -= 7
        while diat - ref < -5:
            diat += 7
        ax.text(xi, mid_y + (diat - ref) * (SS / 2),
                _ACC[-1 if ktype < 0 else 1], fontproperties=_ACCFONT,
                fontsize=10, color=_INK, va="center", ha="center", zorder=6)
        xi += 0.085


# ----------------------------------------------------- intensity ribbon -----
def _ribbon(ax, x0, width, y_bot, curve, total_beats, b0, b1):
    """Filled area of the intensity curve over this system's beat span."""
    ax.add_line(Line2D([x0, x0 + width], [y_bot, y_bot], color=_ARC, lw=0.6))
    ax.text(x0 - 0.05, y_bot + RIBBON_H * 0.5, "intensity", fontproperties=_SERIF,
            fontsize=6, style="italic", color=_FAINT, ha="right", va="center")
    if not curve or total_beats <= 0:
        return

    def val(beat):
        t = beat / total_beats
        pts = curve
        if t <= pts[0][0]:
            return pts[0][1]
        if t >= pts[-1][0]:
            return pts[-1][1]
        for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
            if t0 <= t <= t1:
                f = 0 if t1 == t0 else (t - t0) / (t1 - t0)
                return v0 + f * (v1 - v0)
        return pts[-1][1]

    xs, ys, N = [], [], 64
    for i in range(N + 1):
        b = b0 + (b1 - b0) * i / N
        xs.append(x0 + (b - b0) / (b1 - b0) * width)
        ys.append(y_bot + 0.04 + val(b) * (RIBBON_H - 0.06))
    ax.fill_between(xs, y_bot + 0.02, ys, color=_RIB, alpha=0.16, zorder=1)
    ax.add_line(Line2D(xs, ys, color=_RIB, lw=1.1, alpha=0.8, zorder=2))


# ----------------------------------------------------------- one system -----
def _system(ax, staves, b0, b1, y_top, markers, bpm, total_beats, curve,
            keyexp, ktype, geo):
    x0, width, beatw, block = LM, geo["width"], geo["beatw"], geo["block"]
    ribbon_bot = y_top - RIBBON_H
    first_top = y_top - HEAD
    sys_bottom = first_top - (len(staves) - 1) * block - STAFF_H

    _ribbon(ax, x0, width, ribbon_bot, curve, total_beats, b0, b1)

    # beat grid (faint, every beat) — so bar lengths are measurable as duration
    top_ref = first_top + STAFF_H * 0.4
    b = math.ceil(b0)
    while b <= b1 + 1e-6:
        if b % BEATS_PER_BAR:
            x = x0 + (b - b0) * beatw
            ax.add_line(Line2D([x, x], [sys_bottom, top_ref], color="#ececf0",
                               lw=0.4, zorder=0))
        b += 1
    # barlines
    bar = math.ceil(b0 / BEATS_PER_BAR) * BEATS_PER_BAR
    while bar <= b1 + 1e-6:
        x = x0 + (bar - b0) * beatw
        ax.add_line(Line2D([x, x], [sys_bottom, top_ref],
                           color=_FAINT, lw=0.7, zorder=1))
        bar += BEATS_PER_BAR
    ax.add_line(Line2D([x0 + width, x0 + width],
                       [sys_bottom, first_top + STAFF_H * 0.4],
                       color=_INK, lw=1.3, zorder=1))

    # rehearsal markers + key-change
    mk_y = ribbon_bot - 0.12
    for mk in markers:
        mb = mk["time_s"] * bpm / 60.0
        if b0 - 1e-6 <= mb < b1 - 1e-6:
            x = x0 + (mb - b0) * beatw
            ax.add_line(Line2D([x, x], [sys_bottom, ribbon_bot - 0.02],
                               color=_ACCENT, lw=0.7, ls=(0, (2, 2)),
                               alpha=0.5, zorder=2))
            ax.add_patch(Ellipse((x, mk_y), 0.038, 0.038, facecolor=_ACCENT,
                                 edgecolor="none", zorder=7))
            ax.text(x + 0.06, mk_y, mk["name"].replace("_", " "),
                    fontproperties=_SERIF, fontsize=7, style="italic",
                    color=_ACCENT, va="center", ha="left", zorder=7)

    for k, st in enumerate(staves):
        top = first_top - k * block
        mid_y = top - 2 * SS
        ref = _TREBLE_MID if st["clef"] == "treble" else _BASS_MID
        for j in range(5):
            ly = top - j * SS
            ax.add_line(Line2D([x0, x0 + width], [ly, ly], color=_INK,
                               lw=0.6, alpha=0.5, zorder=1))
        # label · clef · key · performance annotation
        ax.text(LM - 0.70, mid_y + SS * 0.5, st["label"], fontproperties=_SERIF,
                fontsize=8, style="italic", color=_INK, va="center",
                ha="right", zorder=7)
        ann = []
        if st["seat"]:
            ann.append(f"{st['seat']['az_deg']:+.0f}° {st['seat']['dist_m']:g}m")
        if st["rigid"]:
            ann.append("rigid")
        elif st["art"] and st["art"] != "sustain":
            ann.append(st["art"])
        if ann:
            ax.text(LM - 0.70, mid_y - SS * 1.7, " · ".join(ann),
                    fontproperties=_SERIF, fontsize=5.6, color=_FAINT,
                    va="center", ha="right", zorder=7)
        if _NOTO:
            ax.text(LM - 0.62, mid_y, _CLEF[st["clef"]], fontproperties=_NOTO,
                    fontsize=22, color=_INK, va="center", ha="left", zorder=6)
        _keysig(ax, st["clef"], mid_y, LM - 0.30, ktype)

        # dynamics marks under the staff
        for (tb, v) in (st["dynamic"] or []):
            if b0 - 1e-6 <= tb < b1 - 1e-6:
                x = x0 + (tb - b0) * beatw
                ax.text(x, top - STAFF_H - 0.07, _dyn_mark(v),
                        fontproperties=_SERIF, fontsize=7.5, style="italic",
                        weight="bold", color="#444", va="top", ha="center",
                        zorder=6)

        for n in st["notes"]:
            if not (b0 - 1e-6 <= n["beat"] < b1 - 1e-6):
                continue
            x = x0 + (n["beat"] - b0) * beatw
            y = _y_of(n["diat"], st["clef"], mid_y)
            _ledger(ax, x, n["diat"], ref, mid_y)
            _accidental(ax, x, y, n, keyexp)
            _note(ax, x, y, n["dur"], n["vel"], beatw, x0 + width)


# -------------------------------------------------------------- title -------
def _stage_plot(ax, rx, ry, rw, rh, staves, stage):
    """Top-down seating diagram from each layer's seat azimuth/distance."""
    seats = [s for s in staves if s["seat"]]
    if not seats:
        return
    lx, ly = rx + rw / 2, ry + 0.28
    dmax = max(s["seat"]["dist_m"] for s in seats)
    sc = min((rh - 0.55) / dmax, (rw / 2 - 0.45) / (dmax * 0.55))
    # distance arcs + radial guides
    for d in range(2, int(dmax) + 2, 2):
        ax.add_patch(Wedge((lx, ly), d * sc, 55, 125, width=0.004,
                           facecolor=_ARC, edgecolor=_ARC, lw=0.5, zorder=1))
        ax.text(lx, ly + d * sc + 0.02, f"{d}m", fontproperties=_SERIF,
                fontsize=5, color=_FAINT, ha="center", va="bottom")
    for a in (-30, 0, 30):
        r = (dmax + 0.6) * sc
        ax.add_line(Line2D([lx, lx + r * math.sin(math.radians(a))],
                           [ly, ly + r * math.cos(math.radians(a))],
                           color=_ARC, lw=0.5, ls=(0, (1, 3)), zorder=1))
    # listener
    ax.add_patch(Polygon([[lx - 0.07, ly - 0.12], [lx + 0.07, ly - 0.12],
                          [lx, ly]], closed=True, facecolor=_INK, zorder=4))
    ax.text(lx, ly - 0.17, "listener", fontproperties=_SERIF, fontsize=5.5,
            color=_FAINT, ha="center", va="top")
    # Place the seat dots, then declutter the labels per side (left/right) so
    # sources at near-identical azimuth/distance do not overprint each other.
    placed = []
    for s in seats:
        a = math.radians(s["seat"]["az_deg"])
        r = s["seat"]["dist_m"] * sc
        px, py = lx + r * math.sin(a), ly + r * math.cos(a)
        ax.add_patch(Ellipse((px, py), 0.05, 0.05, facecolor=_ACCENT,
                             edgecolor="white", lw=0.5, zorder=5))
        side = "left" if s["seat"]["az_deg"] >= 0 else "right"
        placed.append({"label": s["label"], "px": px, "py": py, "side": side})
    for side in ("left", "right"):
        grp = [p for p in placed if p["side"] == side]
        if not grp:
            continue
        new_y = _declutter([p["py"] for p in grp], 0.115)
        for p, ly2 in zip(grp, new_y):
            ha = "left" if p["side"] == "left" else "right"
            dx = 0.06 if ha == "left" else -0.06
            if abs(ly2 - p["py"]) > 0.015:      # nudged: draw a faint leader
                ax.add_line(Line2D([p["px"], p["px"] + dx], [p["py"], ly2],
                                   color=_ARC, lw=0.4, zorder=4))
            ax.text(p["px"] + dx, ly2, p["label"], fontproperties=_SERIF,
                    fontsize=5.4, color=_INK, ha=ha, va="center", zorder=6)
    cap = "Stage"
    if stage:
        dims = stage.get("dims")
        if dims:
            cap += f" — {dims[0]:g}×{dims[1]:g}×{dims[2]:g} m"
        mics = stage.get("mics", {})
        if mics:
            cap += "   ·   mics " + " ".join(f"{k[:4]} {v:g}"
                                             for k, v in mics.items())
    ax.text(rx + rw / 2, ry + rh - 0.02, cap, fontproperties=_SERIF,
            fontsize=7, style="italic", color=_ACCENT, ha="center", va="top")


def _instrumentation(ax, rx, ry, rw, rh, staves):
    """Fallback panel when the spec has no stage: list the voices + sources."""
    ax.text(rx, ry + rh - 0.02, "Instrumentation", fontproperties=_SERIF,
            fontsize=8.5, style="italic", color=_ACCENT, va="top")
    yy = ry + rh - 0.30
    step = min(0.27, (rh - 0.4) / max(1, len(staves)))
    for st in staves:
        ax.text(rx + 0.08, yy, st["label"], fontproperties=_SERIF,
                fontsize=8, color=_INK, va="center")
        src = st.get("source")
        if src:
            ax.text(rx + 1.7, yy, str(src), fontproperties=_SERIF, fontsize=7,
                    style="italic", color=_FAINT, va="center")
        yy -= step


def _emotion_bars(ax, x, y, emotion):
    ax.text(x, y, "Emotion", fontproperties=_SERIF, fontsize=8.5,
            style="italic", color=_ACCENT)
    yy = y - 0.22
    for name, v in sorted(emotion.items(), key=lambda kv: -kv[1]):
        ax.text(x, yy, name, fontproperties=_SERIF, fontsize=7.5, color=_INK,
                va="center")
        ax.add_patch(Rectangle((x + 1.05, yy - 0.035), 1.6, 0.07,
                               facecolor="#eee", edgecolor="none"))
        ax.add_patch(Rectangle((x + 1.05, yy - 0.035), 1.6 * v, 0.07,
                               facecolor=_RIB, edgecolor="none"))
        ax.text(x + 2.72, yy, f"{v:.2f}", fontproperties=_SERIF, fontsize=6.5,
                color=_FAINT, va="center")
        yy -= 0.205
    return yy


def _provenance(ax, x, y, spec):
    lines = [("AudioForge", f"engine {ENGINE_VERSION}")]
    km = spec.get("key_map")
    key = (" → ".join(f"{k[1]} {k[2]}" for k in km) if km and len(km) > 1
           else spec.get("key", ""))
    lines.append(("tempo · key", f"{int(round(spec.get('bpm', 120)))} bpm · {key}"))
    lib = spec.get("library")
    if lib:
        lines.append(("library", f"{lib['name']} @ {lib['manifest_sha256'][:10]}…"))
    stg = spec.get("stage")
    if stg and stg.get("hall_sha256"):
        lines.append(("hall IR", f"{stg.get('hall_file', 'ir')} @ "
                                 f"{stg['hall_sha256'][:10]}…"))
    ax.text(x, y, "Provenance", fontproperties=_SERIF, fontsize=8.5,
            style="italic", color=_ACCENT)
    yy = y - 0.22
    for k, v in lines:
        ax.text(x, yy, k, fontproperties=_SERIF, fontsize=7, color=_FAINT)
        ax.text(x + 0.95, yy, v, fontproperties=_SERIF, fontsize=7, color=_INK)
        yy -= 0.185
    ax.text(x, yy - 0.04,
            "deterministic — same spec → byte-identical audio, verifiable.",
            fontproperties=_SERIF, fontsize=6.5, style="italic", color=_FAINT)
    return yy


def _new_page():
    fig = plt.figure(figsize=(PAGE_W, PAGE_H))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, PAGE_W)
    ax.set_ylim(0, PAGE_H)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    return fig, ax


def _title_page(pdf, title, subtitle, meta, program, staves, spec):
    import textwrap
    fig, ax = _new_page()
    cx = PAGE_W / 2
    ax.add_line(Line2D([1.2, PAGE_W - 1.2], [PAGE_H - 1.55, PAGE_H - 1.55],
                       color=_ACCENT, lw=1.2))
    ax.text(cx, PAGE_H - 1.2, title, fontproperties=_SERIF, fontsize=30,
            color=_INK, ha="center", va="center")
    ax.text(cx, PAGE_H - 1.9, subtitle, fontproperties=_SERIF, fontsize=13,
            style="italic", color=_ACCENT, ha="center")
    ax.text(cx, PAGE_H - 2.28, meta, fontproperties=_SERIF, fontsize=10,
            color=_INK, ha="center")

    # two columns: program (left) · stage / emotion / provenance (right)
    colL, colR, top = 0.85, 6.05, PAGE_H - 2.95
    if program:
        # reflow the source comment's hard line breaks into clean prose, and
        # drop a redundant ALL-CAPS title banner ("CONTRA O SILÊNCIO — …")
        lines = [ln for ln in program.split("\n") if ln.strip()]
        if lines and "—" in lines[0]:
            head = lines[0].split("—")[0].strip().strip('"').strip()
            if head and head == head.upper() and len(head) <= 40:
                lines = lines[1:]
        flow = re.sub(r"\s+", " ", " ".join(lines)).strip()
        # Clamp the blurb to the space between `top` and the footer caption so
        # a long source header cannot overrun and collide with it.
        p_size, p_wrap, p_lsp = 7.8, 60, 1.55
        prog_floor = 0.95                       # safe gap above the footer line
        line_h = p_size * p_lsp / 72.0          # 1 data unit == 1 inch here
        max_lines = max(4, int((top - prog_floor) / line_h))
        wrapped = _clamp_lines(textwrap.fill(flow, p_wrap).split("\n"),
                               max_lines)
        ax.text(colL, top, "\n".join(wrapped), fontproperties=_SERIF,
                fontsize=p_size, color="#2b2b2b", ha="left", va="top",
                linespacing=p_lsp)
    rw = PAGE_W - RM - colR
    if any(s["seat"] for s in staves):
        _stage_plot(ax, colR, 2.95, rw, top - 2.95 + 0.15, staves,
                    spec.get("stage"))
    else:
        _instrumentation(ax, colR, 2.95, rw, top - 2.95 + 0.15, staves)
    ye = _emotion_bars(ax, colR, 2.62, spec.get("emotion", {}))
    _provenance(ax, colR, ye - 0.30, spec)

    ax.text(colL, 0.5, "Proportional notation — a note's horizontal length is "
            "its duration; the space\nbetween notes is silence (no metric "
            "rests). Durations are non-metric by design.",
            fontproperties=_SERIF, fontsize=6.8, style="italic", color=_FAINT,
            ha="left", va="center", linespacing=1.4)
    ax.text(PAGE_W - RM, 0.5, "proof sheet by AudioForge", fontproperties=_SERIF,
            fontsize=8, style="italic", color=_FAINT, ha="right")
    pdf.savefig(fig)
    plt.close(fig)


# --------------------------------------------------------- family layout ----
_FAMILY_ORDER = ("Strings", "Woodwinds", "Brass", "Percussion")
_FAMILY_KEYS = {
    "Strings":   ("violin", "viola", "cello", "contrabass", "doublebass",
                  "double bass"),
    "Woodwinds": ("flute", "piccolo", "oboe", "english horn", "cor anglais",
                  "clarinet", "bassoon", "contrabassoon", "sax", "recorder"),
    "Brass":     ("trumpet", "cornet", "horn", "fhorn", "french horn",
                  "trombone", "tuba", "euphonium"),
}


def _family_of(st) -> str:
    """Classify a staff into an orchestral family from its instrument/source
    and layer name. Anything unmatched (timpani, mallets, harp, drums, synths)
    falls to Percussion — the catch-all study-score group."""
    key = f"{st.get('source', '')} {st.get('name', '')}".lower()
    for fam in ("Strings", "Woodwinds", "Brass"):
        if any(w in key for w in _FAMILY_KEYS[fam]):
            # 'bassoon'/'contrabass' both contain 'bass' — keyword order above
            # already disambiguates (woodwind keys are checked on their own
            # words), so a direct membership test is safe here.
            return fam
    return "Percussion"


def _group_families(staves):
    """Partition staves into families, preserving spec order within each and a
    fixed family order overall. Returns a list of (family_name, [staves]) for
    non-empty families only."""
    buckets = {fam: [] for fam in _FAMILY_ORDER}
    for st in staves:
        buckets[_family_of(st)].append(st)
    return [(fam, buckets[fam]) for fam in _FAMILY_ORDER if buckets[fam]]


def _family_geo(n_staves, bars_per_system):
    """Layout geometry for a single family page: a few staves spread to fill
    the page so each gets a tall, well-separated lane (wide-range parts like
    the harp no longer collide with neighbours or the footer)."""
    geo = dict(_layout(n_staves, bars_per_system))
    avail = geo["usable"] - HEAD - 0.30
    block = max(0.58, min(1.55, avail / max(1, n_staves)))
    geo["block"] = block
    geo["sys_h"] = HEAD + n_staves * block
    return geo


# ------------------------------------------------------------- entry --------
def _render_asset(pdf, spec, title, subtitle, program, bars_per_system):
    """Render one asset (title page + score systems) into an open PdfPages."""
    staves = _staves(spec)
    if not staves:
        return False
    bpm = float(spec.get("bpm", 120.0))
    tonic, mode = (spec.get("key", "C major").split() + ["major"])[:2]
    ktype, keyexp = _key_sig(tonic, mode)
    markers = spec.get("markers", [])
    curve = spec.get("intensity_curve")

    total_beats = max([n["beat"] + n["dur"] for st in staves for n in st["notes"]]
                      + [spec.get("duration_s", 0) * bpm / 60.0])
    families = _group_families(staves)
    beats_per_sys = _layout(len(staves), bars_per_system)["beats"]
    n_sys = max(1, math.ceil(total_beats / beats_per_sys))

    title = title or _title_from_id(spec.get("id", "untitled"))
    if subtitle is None:
        km = spec.get("key_map")
        keys = (" → ".join(f"{k[1]} {k[2]}" for k in km) if km and len(km) > 1
                else spec.get("key", ""))
        subtitle = f"{spec.get('kind', 'asset')} · {keys}"
    dur = spec.get("duration_s", 0)
    meta = (f"{int(round(bpm))} bpm   ·   {BEATS_PER_BAR}/4   ·   "
            f"{int(dur // 60)}'{int(dur % 60):02d}\"   ·   {len(staves)} staves")

    _title_page(pdf, title, subtitle, meta, program, staves, spec)
    # Study-score layout: each time-window is drawn once per instrument
    # family, on its own page, so a few staves get roomy, well-separated lanes
    # instead of 17 staves merging into one over-packed grid. A family page is
    # skipped for windows in which that family has no note onset.
    for s in range(n_sys):
        b0, b1 = s * beats_per_sys, (s + 1) * beats_per_sys
        bar0 = int(b0 // BEATS_PER_BAR) + 1
        bar1 = int(math.ceil(b1 / BEATS_PER_BAR))
        for fam_name, fam_staves in families:
            if not any(b0 - 1e-6 <= n["beat"] < b1 - 1e-6
                       for st in fam_staves for n in st["notes"]):
                continue
            geo = _family_geo(len(fam_staves), bars_per_system)
            fig, ax = _new_page()
            ax.text(LM - 0.70, PAGE_H - 0.34, fam_name, fontproperties=_SERIF,
                    fontsize=12, color=_ACCENT, ha="left", va="center")
            ax.text(LM - 0.70, PAGE_H - 0.56, f"bars {bar0}–{bar1}",
                    fontproperties=_SERIF, fontsize=8, style="italic",
                    color=_FAINT, ha="left", va="center")
            ax.text(PAGE_W - RM, PAGE_H - 0.3, title, fontproperties=_SERIF,
                    fontsize=8, style="italic", color=_FAINT, ha="right")
            ax.text(LM, 0.26, "proportional · bar length = duration · "
                    "space = silence", fontproperties=_SERIF, fontsize=6.5,
                    style="italic", color=_FAINT, ha="left")
            y_top = PAGE_H - TM - max(0.0, (geo["usable"] - geo["sys_h"]) / 2)
            _system(ax, fam_staves, b0, b1, y_top, markers, bpm, total_beats,
                    curve, keyexp, ktype, geo)
            pdf.savefig(fig)
            plt.close(fig)
    return True


def score_pdf(spec, out_path, *, title=None, subtitle=None, program=None,
              bars_per_system=8):
    """Draw one spec — or a list of specs (e.g. multi-movement work) — to a
    single proof-sheet PDF. The program note is shown once, on the first movement."""
    specs = spec if isinstance(spec, list) else [spec]
    with PdfPages(out_path) as pdf:
        drawn = 0
        for i, sp in enumerate(specs):
            if _render_asset(pdf, sp, title if len(specs) == 1 else None,
                             subtitle, program if i == 0 else None,
                             bars_per_system):
                drawn += 1
        if not drawn:
            raise ValueError("no pitched layers to draw")
    return out_path
