"""The prebuilt cue library: music beds, stings, transitions, UI, foley, ambience.

Every builder turns resolved parameters into `.af` source. Beds loop a phrase with
`loop:` (notes) and repeating drum patterns, so any duration is exact; the master
fades the ending. Keys are expressed as scale degrees and transposed here, so every
musical cue works in any major or minor key. Randomness only enters through `seed`
(the asset's performance seed) or a `random.Random(seed)` used at build time, so the
same parameters always produce the same source and the same audio.
"""
from __future__ import annotations

import random

from .. import theory
from . import LOUDNESS, Cue, Param, register

MAJOR = (0, 2, 4, 5, 7, 9, 11)
MINOR = (0, 2, 3, 5, 7, 8, 10)


# --------------------------------------------------------------------- helpers
def _dur(default, lo, hi, doc="length in seconds"):
    return Param("duration", "float", default, doc, lo, hi)


SEED = Param("seed", "int", 1, "performance seed: a different take of the same cue", 0, 2**31 - 1)
INTENSITY = Param("intensity", "float", 0.6, "0 = sparse, 1 = full arrangement", 0.0, 1.0)


def _bpm(default, lo=50, hi=180):
    return Param("bpm", "float", default, "tempo", lo, hi)


def _key(default):
    return Param("key", "key", default, "key, e.g. 'A minor' or 'C major'")


class Key:
    def __init__(self, text: str):
        tonic, mode = text.split()
        self.tonic = theory.note_to_semis(tonic + "0") % 12
        self.scale = MINOR if mode == "minor" else MAJOR
        self.text = text

    def note(self, degree: int, octave: int) -> str:
        """Scale degree (0-based, may exceed 6) in `octave` of the tonic."""
        step = self.scale[degree % 7] + 12 * (degree // 7)
        return theory.semis_to_note(12 * octave + self.tonic + step)

    def chord(self, degree: int, quality: str, octave: int) -> str:
        return self.note(degree, octave) + quality


def _chords(k: Key, prog, octave, beats, voicing="spread", vel=None):
    parts = []
    for i, (deg, q) in enumerate(prog):
        ev = f"{k.chord(deg, q, octave)} @ {i * beats}b for {beats}b"
        if voicing:
            ev += f" voicing {voicing}"
        if vel is not None:
            ev += f" vel {vel}"
        parts.append(ev)
    return ",\n           ".join(parts)


def _events(evs):
    """[(pitch, start_beat, dur_beats, vel)] -> DSL note list."""
    return ",\n           ".join(
        f"{p} @ {round(s, 4)}b for {round(d, 4)}b" + (f" vel {v}" if v is not None else "")
        for p, s, d, v in evs)


def _roots(k: Key, prog, octave, beats, pattern):
    """Bass line: for each chord, notes at `pattern` = [(offset, dur, vel, degree_shift)]."""
    evs = []
    for i, (deg, _q) in enumerate(prog):
        for off, d, v, shift in pattern:
            evs.append((k.note(deg + shift, octave), i * beats + off, d, v))
    return _events(evs)


def _gate(p, threshold):
    return p["intensity"] >= threshold


def _asset(name: str, kind: str, category: str, p: dict, body: list[str], *,
           bpm: float = 120.0, key: str | None = None, markers=(), fadein=0.0,
           fadeout=0.0, width: float | None = None) -> str:
    loud = LOUDNESS[category]
    lines = [f"asset {name} {{", f"  kind: {kind}", f"  duration: {round(p['duration'], 4)}s",
             f"  tempo: {round(bpm, 3)}bpm", f"  seed: {p['seed']}"]
    if key:
        lines.append(f"  key: {key}")
    for mname, t in markers:
        lines.append(f"  marker {mname} @ {round(t, 4)}s")
    lines += ["", *body, "  master {"]
    if "lufs" in loud:
        lines.append(f"    lufs: {loud['lufs']}")
    else:
        lines.append(f"    normalize: {loud['normalize']}")
    lines.append(f"    peak: {loud['peak']}db")
    if fadein:
        lines.append(f"    fadein: {round(fadein, 3)}s")
    if fadeout:
        lines.append(f"    fadeout: {round(fadeout, 3)}s")
    if width is not None:
        lines.append(f"    width: {width}")
    lines += ["  }", "}", ""]
    return "\n".join(lines)


def _layer(name: str, ltype: str, props: list[str]) -> str:
    return "\n".join([f"  layer {name} : {ltype} {{", *[f"    {x}" for x in props], "  }", ""])


def _bed_fades(p):
    d = p["duration"]
    return min(1.5, 0.08 * d), min(4.0, max(1.0, 0.12 * d))


def _bed(cid, title, description, tags, key, bpm, build):
    params = (_dur(30.0, 5.0, 600.0), _bpm(bpm), _key(key), INTENSITY, SEED)
    return register(Cue(cid, "music", "bed", title, description, params, build, tags))


# ------------------------------------------------------------------ music beds
def _ambient_calm(p):
    k = Key(p["key"])
    prog = [(0, "maj7"), (3, "maj7")]
    fi, fo = _bed_fades(p)
    body = [_layer("pad", "notes", [
        "osc: pad", "bandwidth: 50c", "gain: -10db", "env: a=3s d=2s s=0.85 r=4s",
        f"notes: {_chords(k, prog, 3, 8)}", "loop: 16b",
        "fx: lowpass(2200hz), reverb(decay=6s, mix=0.4)"])]
    if _gate(p, 0.3):
        body.append(_layer("glint", "notes", [
            "osc: pluck", "damping: 0.35", "brightness: 0.55", "gain: -23db",
            "env: a=0.005s d=0.6s s=0.0 r=0.9s",
            "notes: " + _events([(k.note(4, 5), 2, 1, 0.6), (k.note(2, 5), 5.5, 1, 0.5),
                                 (k.note(8, 5), 10, 1, 0.55), (k.note(6, 5), 13.5, 1, 0.45)]),
            "loop: 16b", "pan: 0.3", "fx: delay(time=0.75, feedback=0.35, mix=0.3), reverb(decay=5s, mix=0.45)"]))
    if _gate(p, 0.55):
        body.append(_layer("low", "notes", [
            "osc: sine", "gain: -17db", "env: a=2s d=1s s=0.9 r=3s",
            f"notes: {_roots(k, prog, 2, 8, [(0, 8, 0.8, 0)])}", "loop: 16b"]))
    return _asset("bed_ambient_calm", "bed", "bed", p, body, bpm=p["bpm"], key=k.text,
                  fadein=max(fi, 1.0), fadeout=fo, width=0.9)


_bed("bed/ambient-calm", "Ambient calm",
     "Slow major-seventh pads with sparse plucked glints; unobtrusive under narration.",
     ("calm", "ambient", "narration", "wellness"), "D major", 70, _ambient_calm)


def _documentary_airy(p):
    k = Key(p["key"])
    prog = [(0, "min7"), (5, "maj7"), (2, "maj7"), (6, "maj")]
    fi, fo = _bed_fades(p)
    body = [
        _layer("pad", "notes", [
            "osc: pad", "bandwidth: 45c", "gain: -14db", "env: a=1.5s d=1s s=0.85 r=2.5s",
            f"notes: {_chords(k, prog, 3, 4)}", "loop: 16b",
            "fx: lowpass(1800hz), reverb(decay=4s, mix=0.3)"]),
        _layer("arp", "notes", [
            "osc: pluck", "damping: 0.5", "brightness: 0.5", "gain: -19db", "velbright: 0.4",
            "env: a=0.004s d=0.25s s=0.3 r=0.3s", "arp: updown rate=0.5b octaves=2",
            f"notes: {_chords(k, prog, 3, 4, voicing=None)}", "loop: 16b", "pan: -0.2",
            "fx: delay(time=0.47, feedback=0.3, mix=0.2), reverb(decay=3s, mix=0.25)"]),
    ]
    if _gate(p, 0.3):
        body.append(_layer("bass", "notes", [
            "osc: triangle", "gain: -15db", "env: a=0.02s d=0.4s s=0.7 r=0.4s",
            f"notes: {_roots(k, prog, 2, 4, [(0, 3.5, 0.9, 0)])}", "loop: 16b",
            "fx: lowpass(420hz)"]))
    if _gate(p, 0.5):
        body += [
            _layer("kick", "drums", ["voice: kick", "pattern: x.......x.......", "gain: -18db"]),
            _layer("hat", "drums", ["voice: hat", "pattern: ..x...x...x...x.", "gain: -27db",
                                    "humanize: 0.3", "pan: 0.25"])]
    return _asset("bed_documentary_airy", "bed", "bed", p, body, bpm=p["bpm"], key=k.text,
                  fadein=fi, fadeout=fo)


_bed("bed/documentary-airy", "Documentary airy",
     "Airy minor pads, a gentle plucked arpeggio and a soft pulse — explainer and science narration.",
     ("documentary", "explainer", "science", "narration"), "A minor", 96, _documentary_airy)


def _corporate_uplift(p):
    k = Key(p["key"])
    prog = [(0, "maj"), (4, "maj"), (5, "min"), (3, "add9")]
    fi, fo = _bed_fades(p)
    body = [
        _layer("arp", "notes", [
            "osc: pluck", "damping: 0.45", "brightness: 0.65", "gain: -16db", "velbright: 0.5",
            "env: a=0.003s d=0.2s s=0.35 r=0.25s", "arp: up rate=0.25b octaves=1",
            f"notes: {_chords(k, prog, 4, 4, voicing=None)}", "loop: 16b",
            "fx: delay(time=0.4, feedback=0.25, mix=0.15)"]),
        _layer("bass", "notes", [
            "osc: pluck", "damping: 0.7", "brightness: 0.35", "gain: -15db",
            "env: a=0.005s d=0.3s s=0.5 r=0.2s",
            f"notes: {_roots(k, prog, 2, 4, [(o, 0.45, 0.9 if o == 0 else 0.7, 0) for o in (0, 1, 2, 3)])}",
            "loop: 16b", "fx: lowpass(900hz)"]),
    ]
    if _gate(p, 0.3):
        body.append(_layer("pad", "notes", [
            "osc: saw", "unison: 5", "spread: 14c", "gain: -21db", "env: a=0.6s d=1s s=0.8 r=1.2s",
            f"notes: {_chords(k, prog, 3, 4)}", "loop: 16b",
            "fx: lowpass(1600hz), reverb(decay=2.5s, mix=0.25)"]))
    if _gate(p, 0.5):
        body += [
            _layer("kick", "drums", ["voice: kick", "pattern: x...x...x...x...", "gain: -16db"]),
            _layer("clap", "drums", ["voice: clap", "pattern: ....x.......x...", "gain: -21db"]),
            _layer("hat", "drums", ["voice: hat", "pattern: ..x...x...x...x.", "gain: -26db",
                                    "humanize: 0.25", "pan: 0.2"])]
    return _asset("bed_corporate_uplift", "bed", "bed", p, body, bpm=p["bpm"], key=k.text,
                  fadein=fi, fadeout=fo)


_bed("bed/corporate-uplift", "Corporate uplift",
     "Bright I–V–vi–IV plucks over a four-on-the-floor pulse — product demos, launches, brand stories.",
     ("corporate", "upbeat", "product", "positive"), "C major", 112, _corporate_uplift)


def _tension_underscore(p):
    k = Key(p["key"])
    d = p["duration"]
    fi, fo = _bed_fades(p)
    body = [
        _layer("drone", "notes", [
            "osc: saw", "unison: 3", "spread: 10c", "gain: -14db", "env: a=2s d=1s s=0.9 r=3s",
            "notes: " + _events([(k.note(0, 1), 0, 16, 0.9), (k.note(4, 1), 0, 16, 0.6)]),
            "loop: 16b", "fx: lowpass(280hz), reverb(decay=4s, mix=0.3)",
            f"auto cutoff: 0s=240, {round(d, 3)}s=900"]),
        _layer("ostinato", "notes", [
            "osc: pluck", "damping: 0.85", "brightness: 0.3", "gain: -18db",
            "env: a=0.003s d=0.15s s=0.0 r=0.12s",
            "notes: " + _events([(k.note(0, 3), i * 0.5, 0.4, 0.95 if i % 4 == 0 else 0.7)
                                 for i in range(8)]),
            "loop: 4b", "pan: -0.25"]),
    ]
    if _gate(p, 0.4):
        body.append(_layer("pulse", "drums", [
            "voice: tom", "tune: -5st", "decay: 1.6", "pattern: x.......x.x.....", "gain: -18db",
            "fx: reverb(decay=2.5s, mix=0.25)"]))
    if _gate(p, 0.65):
        body.append(_layer("cluster", "notes", [
            "osc: saw", "gain: -30db", "env: a=4s d=1s s=0.9 r=3s",
            "notes: " + _events([(k.note(7, 4), 0, 16, 0.6), (k.note(8, 4), 0, 16, 0.5)]),
            "loop: 16b", "pan: 0.35", "fx: lowpass(2400hz), tremolo(rate=6, depth=0.3), reverb(decay=5s, mix=0.4)",
            f"auto gain: 0s=-36db, {round(d * 0.6, 3)}s=-30db, {round(d, 3)}s=-27db"]))
    return _asset("bed_tension_underscore", "bed", "bed", p, body, bpm=p["bpm"], key=k.text,
                  fadein=fi, fadeout=fo)


_bed("bed/tension-underscore", "Tension underscore",
     "Low drone with a muted ostinato and a filter that opens over the cue — investigations, suspense, war stories.",
     ("tension", "suspense", "dark", "documentary"), "D minor", 80, _tension_underscore)


def _cinematic_epic(p):
    k = Key(p["key"])
    prog = [(0, "min"), (5, "maj"), (2, "maj"), (6, "maj")]
    fi, fo = _bed_fades(p)
    body = [
        _layer("strings", "notes", [
            "osc: saw", "unison: 7", "spread: 18c", "gain: -14db", "env: a=1.2s d=1s s=0.85 r=2s",
            f"notes: {_chords(k, prog, 3, 8)}", "loop: 32b",
            "fx: lowpass(2600hz), hall(rt60=3s, mix=0.3)"]),
        _layer("low", "notes", [
            "osc: organ", "gain: -16db", "env: a=0.8s d=1s s=0.9 r=2s",
            f"notes: {_roots(k, prog, 2, 8, [(0, 8, 0.9, 0)])}", "loop: 32b",
            "fx: lowpass(700hz)"]),
    ]
    if _gate(p, 0.4):
        body += [
            _layer("toms", "drums", ["voice: tom", "tune: -4st", "decay: 1.8",
                                     "pattern: X..x..x.X...x.x.", "gain: -14db",
                                     "fx: hall(rt60=2.2s, mix=0.25)"]),
            _layer("kick", "drums", ["voice: kick", "decay: 1.5", "pattern: X.......X..x....",
                                     "gain: -14db"])]
    if _gate(p, 0.7):
        body.append(_layer("brass", "notes", [
            "osc: saw", "unison: 3", "spread: 8c", "gain: -20db", "env: a=0.25s d=0.6s s=0.8 r=1s",
            "notes: " + _events([(k.note(0, 4), 0, 3, 0.9), (k.note(4, 4), 3, 1, 0.8),
                                 (k.note(2, 4), 4, 4, 0.85), (k.note(1, 4), 8, 2, 0.8),
                                 (k.note(0, 4), 10, 6, 0.9)]),
            "loop: 32b", "fx: lowpass(1800hz), hall(rt60=2.5s, mix=0.3)"]))
    return _asset("bed_cinematic_epic", "bed", "bed", p, body, bpm=p["bpm"], key=k.text,
                  fadein=fi, fadeout=fo)


_bed("bed/cinematic-epic", "Cinematic epic",
     "Wide string pads over organ lows and tom ensembles — trailers, historical reveals, big statements.",
     ("cinematic", "epic", "trailer", "history"), "D minor", 90, _cinematic_epic)


def _lofi_chill(p):
    k = Key(p["key"])
    prog = [(3, "maj7"), (2, "min7"), (1, "min7"), (0, "maj7")]
    fi, fo = _bed_fades(p)
    body = [
        _layer("keys", "notes", [
            "osc: fm", "fmratio: 1", "fmindex: 1.2", "gain: -14db", "humanize: 0.35",
            "env: a=0.01s d=1.2s s=0.4 r=0.8s",
            f"notes: {_chords(k, prog, 3, 4, voicing='drop2')}", "loop: 16b",
            "fx: lowpass(2400hz), tremolo(rate=4, depth=0.15), reverb(decay=2s, mix=0.2)"]),
        _layer("bass", "notes", [
            "osc: sine", "gain: -14db", "env: a=0.01s d=0.5s s=0.6 r=0.3s",
            f"notes: {_roots(k, prog, 2, 4, [(0, 1.5, 0.9, 0), (2.5, 1, 0.7, 4)])}", "loop: 16b"]),
    ]
    if _gate(p, 0.3):
        body += [
            _layer("kick", "drums", ["voice: kick", "pattern: x......x..x.....", "gain: -16db"]),
            _layer("snare", "drums", ["voice: snare", "pattern: ....x.......x...", "gain: -20db",
                                      "fx: lowpass(3500hz)"])]
    if _gate(p, 0.5):
        body.append(_layer("hat", "drums", ["voice: hat", "pattern: x.x.x.x.x.x.x.x.",
                                            "gain: -27db", "humanize: 0.4",
                                            "fx: lowpass(6000hz)"]))
    body.append(_layer("vinyl", "noise", ["color: pink", "gain: -44db",
                                          "env: a=1s d=0.1s s=1 r=1s",
                                          "fx: highpass(1200hz), lowpass(5000hz)"]))
    return _asset("bed_lofi_chill", "bed", "bed", p, body, bpm=p["bpm"], key=k.text,
                  fadein=fi, fadeout=fo)


_bed("bed/lofi-chill", "Lo-fi chill",
     "Soft electric-piano sevenths, round bass and a laid-back beat — vlogs, tutorials, study content.",
     ("lofi", "chill", "vlog", "tutorial"), "C major", 78, _lofi_chill)


def _electronic_drive(p):
    k = Key(p["key"])
    prog = [(0, "min"), (5, "maj"), (3, "min"), (4, "min")]
    d = p["duration"]
    fi, fo = _bed_fades(p)
    bass = []
    for i, (deg, _q) in enumerate(prog):
        for s in range(16):
            bass.append((k.note(deg, 1), i * 4 + s * 0.25, 0.2, 0.95 if s % 4 == 0 else 0.7))
    body = [
        _layer("bass", "notes", [
            "osc: saw", "gain: -15db", "env: a=0.002s d=0.12s s=0.5 r=0.08s",
            f"notes: {_events(bass)}", "loop: 16b",
            "fx: lowpass(700hz, q=2.5), saturate(amount=0.2)",
            f"auto cutoff: 0s=450, {round(d * 0.5, 3)}s=1400, {round(d, 3)}s=900"]),
        _layer("kick", "drums", ["voice: kick", "pattern: x...x...x...x...", "gain: -13db"]),
    ]
    if _gate(p, 0.35):
        body.append(_layer("clap", "drums", ["voice: clap", "pattern: ....x.......x...",
                                             "gain: -19db"]))
    if _gate(p, 0.5):
        body += [
            _layer("hat", "drums", ["voice: open_hat", "pattern: ..x...x...x...x.",
                                    "gain: -25db", "pan: 0.2"]),
            _layer("pad", "notes", [
                "osc: saw", "unison: 5", "spread: 16c", "gain: -22db",
                "env: a=0.3s d=0.8s s=0.7 r=1s",
                f"notes: {_chords(k, prog, 3, 4)}", "loop: 16b",
                "fx: lowpass(2200hz), reverb(decay=2.5s, mix=0.3)"])]
    return _asset("bed_electronic_drive", "bed", "bed", p, body, bpm=p["bpm"], key=k.text,
                  fadein=fi, fadeout=fo)


_bed("bed/electronic-drive", "Electronic drive",
     "Sixteenth-note saw bass under a four-on-the-floor kick with an opening filter — tech, motion graphics, sport.",
     ("electronic", "energetic", "tech", "motion-graphics"), "A minor", 124, _electronic_drive)


def _playful_quirky(p):
    k = Key(p["key"])
    prog = [(0, "maj"), (3, "maj"), (4, "maj"), (0, "maj")]
    fi, fo = _bed_fades(p)
    melody = [(0, 0), (2, 0.5), (4, 1), (2, 1.5), (5, 2), (4, 3),
              (3, 4), (5, 4.5), (7, 5), (5, 5.5), (4, 6), (2, 7),
              (1, 8), (4, 8.5), (6, 9), (4, 9.5), (8, 10), (7, 11),
              (4, 12), (2, 12.5), (0, 13), (4, 13.5), (7, 14)]
    body = [
        _layer("marimba", "notes", [
            "osc: modal", "material: marimba", "gain: -13db", "env: a=0.001s d=0.4s s=0.0 r=0.4s",
            "notes: " + _events([(k.note(dg, 4), s, 0.45, 0.85 if s % 1 == 0 else 0.65)
                                 for dg, s in melody]),
            "loop: 16b", "pan: 0.15", "fx: reverb(decay=1.6s, mix=0.2)"]),
        _layer("bass", "notes", [
            "osc: pluck", "damping: 0.8", "brightness: 0.4", "gain: -15db",
            "env: a=0.003s d=0.2s s=0.2 r=0.15s",
            f"notes: {_roots(k, prog, 2, 4, [(0, 0.4, 0.9, 0), (1, 0.4, 0.7, 4), (2, 0.4, 0.8, 0), (3, 0.4, 0.7, 4)])}",
            "loop: 16b"]),
    ]
    if _gate(p, 0.4):
        body += [
            _layer("clap", "drums", ["voice: clap", "pattern: ....x.......x...", "gain: -20db"]),
            _layer("tick", "drums", ["voice: hat", "tune: 5st", "pattern: x.xxx.x.x.xxx.x.",
                                     "gain: -28db", "humanize: 0.3", "pan: -0.3"])]
    return _asset("bed_playful_quirky", "bed", "bed", p, body, bpm=p["bpm"], key=k.text,
                  fadein=fi, fadeout=fo)


_bed("bed/playful-quirky", "Playful quirky",
     "Bouncy marimba melody over a plucked bass and claps — kids, how-to, light-hearted explainers.",
     ("playful", "kids", "light", "explainer"), "F major", 118, _playful_quirky)


def _dark_ambient(p):
    k = Key(p["key"])
    fi, fo = _bed_fades(p)
    body = [
        _layer("drone", "notes", [
            "osc: pad", "bandwidth: 70c", "gain: -13db", "env: a=4s d=2s s=0.9 r=5s",
            f"notes: {_chords(k, [(0, 'min'), (5, 'maj')], 2, 16)}", "loop: 32b",
            "fx: lowpass(900hz), reverb(decay=8s, mix=0.45)"]),
        _layer("air", "noise", ["color: brown", "gain: -31db", "env: a=3s d=1s s=1 r=3s",
                                "fx: lowpass(320hz), tremolo(rate=0.12, depth=0.5)"]),
    ]
    if _gate(p, 0.35):
        body.append(_layer("dust", "grain", [
            "source: sine", f"note: {k.note(4, 4)}", "gain: -27db", "srcdur: 0.5s",
            "grainsize: 0.08s", "density: 18", "pitchspread: 40c", "scatter: 0.8",
            "env: a=3s d=1s s=0.9 r=3s", "fx: highpass(500hz), reverb(decay=6s, mix=0.5)"]))
    if _gate(p, 0.55):
        body.append(_layer("gong", "notes", [
            "osc: modal", "material: gong", "gain: -21db", "env: a=0.001s d=4s s=0.0 r=4s",
            "notes: " + _events([(k.note(0, 2), 0, 8, 0.8), (k.note(4, 2), 24, 8, 0.6)]),
            "loop: 32b", "fx: reverb(decay=9s, mix=0.5)"]))
    return _asset("bed_dark_ambient", "bed", "bed", p, body, bpm=p["bpm"], key=k.text,
                  fadein=max(fi, 1.5), fadeout=fo)


_bed("bed/dark-ambient", "Dark ambient",
     "Deep minor drones, grain dust and distant gong swells — mystery, space, true crime.",
     ("dark", "ambient", "mystery", "space"), "C minor", 60, _dark_ambient)


def _news_pulse(p):
    k = Key(p["key"])
    prog = [(0, "min"), (5, "maj"), (3, "min"), (4, "min")]
    fi, fo = _bed_fades(p)
    body = [
        _layer("tick", "notes", [
            "osc: pluck", "damping: 0.8", "brightness: 0.55", "gain: -24db",
            "env: a=0.002s d=0.08s s=0.0 r=0.06s",
            "notes: " + _events([(k.note(0, 5), s * 0.25, 0.2, 0.9 if s % 4 == 0 else 0.55)
                                 for s in range(16)]),
            "loop: 4b", "pan: 0.3"]),
        _layer("sub", "notes", [
            "osc: sine", "gain: -15db", "env: a=0.005s d=0.35s s=0.2 r=0.2s",
            f"notes: {_roots(k, prog, 1, 4, [(o, 0.6, 0.9, 0) for o in (0, 1, 2, 3)])}",
            "loop: 16b"]),
        _layer("stabs", "notes", [
            "osc: saw", "unison: 3", "spread: 10c", "gain: -21db",
            "env: a=0.005s d=0.35s s=0.0 r=0.3s",
            "notes: " + ",\n           ".join(
                f"{k.chord(deg, q, 3)} @ {i * 4 + off}b for 0.5b"
                for i, (deg, q) in enumerate(prog) for off in (0, 2.5)),
            "loop: 16b", "fx: lowpass(2000hz), reverb(decay=1.8s, mix=0.2)"]),
    ]
    if _gate(p, 0.5):
        body += [
            _layer("kick", "drums", ["voice: kick", "pattern: x...x...x...x...", "gain: -17db"]),
            _layer("hat", "drums", ["voice: hat", "pattern: xxxxxxxxxxxxxxxx", "gain: -31db",
                                    "humanize: 0.2"])]
    return _asset("bed_news_pulse", "bed", "bed", p, body, bpm=p["bpm"], key=k.text,
                  fadein=fi, fadeout=fo)


_bed("bed/news-pulse", "News pulse",
     "Ticking sixteenths, sub pulses and minor stabs — news, data stories, countdowns.",
     ("news", "data", "urgent", "tech"), "E minor", 120, _news_pulse)


# ---------------------------------------------------------------------- stings
def _sting(cid, title, description, tags, key, dur, build, lo=0.8, hi=10.0):
    params = (_dur(dur, lo, hi), _key(key), SEED)
    return register(Cue(cid, "music", "sting", title, description, params, build, tags))


def _opener(p):
    k = Key(p["key"])
    d = p["duration"]
    hit = min(1.0, 0.3 * d)
    tail = round(d - hit, 3)
    body = [
        _layer("rise", "sweep", ["shape: sine", "from: 200hz", "to: 1600hz", "curve: exp",
                                 f"duration: {hit}s", "gain: -20db",
                                 f"env: a={hit}s d=0.01s s=1 r=0.02s"]),
        _layer("bloom", "notes", [
            "osc: pad", "bandwidth: 40c", "gain: -12db", f"start: {hit}s",
            "env: a=0.05s d=1s s=0.7 r=1.5s",
            f"notes: {k.chord(0, 'add9', 3)} @ 0b for {max(1.0, tail * 2)}b voicing spread",
            "fx: reverb(decay=4s, mix=0.35)"]),
        _layer("sparkle", "notes", [
            "osc: pluck", "damping: 0.4", "brightness: 0.7", "gain: -17db", f"start: {hit}s",
            "env: a=0.003s d=0.3s s=0.2 r=0.6s", "arp: up rate=0.25b octaves=2",
            f"notes: {k.chord(0, 'add9', 4)} @ 0b for 2b",
            "fx: delay(time=0.3, feedback=0.3, mix=0.25), reverb(decay=3s, mix=0.3)"]),
        _layer("hit", "drums", ["voice: kick", "decay: 1.5", "tune: -3st",
                                "pattern: X...............", f"start: {hit}s", "gain: -12db",
                                "fx: reverb(decay=2s, mix=0.2)"]),
    ]
    return _asset("sting_opener", "jingle", "sting", p, body, bpm=120, key=k.text,
                  markers=[("hit", hit)], fadeout=min(1.0, 0.3 * d))


_sting("sting/opener", "Opener", "Rising sweep into a bright chord bloom with a soft hit — title cards.",
       ("opener", "title", "intro"), "C major", 3.5, _opener, lo=1.5)


def _closer(p):
    k = Key(p["key"])
    d = p["duration"]
    body = [
        _layer("cadence", "notes", [
            "osc: pluck", "damping: 0.4", "brightness: 0.55", "gain: -14db",
            "env: a=0.003s d=0.5s s=0.4 r=1.2s",
            f"notes: {k.chord(4, '7', 3)} @ 0b for 1b voicing drop2 vel 0.8,\n"
            f"           {k.chord(0, 'maj', 3)} @ 1b for {max(2.0, d * 2 - 1)}b voicing spread",
            "fx: reverb(decay=3.5s, mix=0.35)"]),
        _layer("pad", "notes", [
            "osc: pad", "gain: -16db", "env: a=0.6s d=1s s=0.8 r=2s",
            f"notes: {k.chord(0, 'maj', 3)} @ 1b for {max(2.0, d * 2 - 1)}b voicing spread",
            "fx: lowpass(2000hz), reverb(decay=4s, mix=0.4)"]),
        _layer("bell", "notes", [
            "osc: modal", "material: bell", "gain: -22db", "env: a=0.001s d=2s s=0.0 r=2s",
            f"notes: {k.note(0, 5)} @ 1b for 3b", "fx: reverb(decay=4s, mix=0.4)"]),
    ]
    return _asset("sting_closer", "jingle", "sting", p, body, bpm=120, key=k.text,
                  fadeout=min(1.5, 0.35 * d))


_sting("sting/closer", "Closer", "V–I cadence with a bell on the resolution — end cards, sign-offs.",
       ("closer", "outro", "end"), "C major", 3.0, _closer, lo=1.5)


def _logo(p):
    k = Key(p["key"])
    d = p["duration"]
    body = [
        _layer("motif", "notes", [
            "osc: modal", "material: bell", "gain: -13db", "env: a=0.001s d=1.5s s=0.0 r=2s",
            "notes: " + _events([(k.note(4, 5), 0, 0.5, 0.8), (k.note(2, 5), 0.5, 0.5, 0.75),
                                 (k.note(7, 5), 1, 3, 0.95)]),
            "fx: hall(rt60=3.2s, mix=0.35)"]),
        _layer("boom", "drums", ["voice: kick", "tune: -7st", "decay: 3", "bend: 1",
                                 "pattern: ....X...........", "gain: -12db"]),
        _layer("shimmer", "notes", [
            "osc: pad", "bandwidth: 30c", "gain: -21db", "env: a=0.4s d=1s s=0.7 r=2s",
            f"notes: {k.chord(0, 'maj', 5)} @ 1b for {max(2.0, d * 2 - 1)}b",
            "fx: highpass(900hz), reverb(decay=5s, mix=0.5)"]),
    ]
    return _asset("sting_logo", "signature", "sting", p, body, bpm=120, key=k.text,
                  markers=[("reveal", 0.5)], fadeout=min(1.2, 0.3 * d))


_sting("sting/logo", "Logo reveal", "Three-note bell motif, sub boom and a shimmer tail — logo and brand reveals.",
       ("logo", "brand", "reveal"), "E major", 3.5, _logo, lo=2.0)


def _success(p):
    k = Key(p["key"])
    body = [_layer("chime", "notes", [
        "osc: pluck", "damping: 0.3", "brightness: 0.75", "gain: -12db",
        "env: a=0.002s d=0.25s s=0.3 r=0.5s",
        "notes: " + _events([(k.note(0, 5), 0, 0.5, 0.8), (k.note(2, 5), 0.25, 0.5, 0.85),
                             (k.note(4, 5), 0.5, 0.5, 0.9), (k.note(7, 5), 0.75, 1.5, 1.0)]),
        "fx: reverb(decay=1.5s, mix=0.25)"])]
    return _asset("sting_success", "sfx", "sting", p, body, bpm=140, key=k.text,
                  fadeout=min(0.4, 0.3 * p["duration"]))


_sting("sting/success", "Success", "Bright rising major arpeggio — completion, correct answer, unlock.",
       ("ui", "success", "positive"), "C major", 1.4, _success)


def _error(p):
    k = Key(p["key"])
    body = [_layer("buzz", "notes", [
        "osc: square", "gain: -16db", "env: a=0.002s d=0.15s s=0.6 r=0.12s",
        "notes: " + _events([(k.note(4, 3), 0, 0.3, 0.9), (k.note(0, 3), 0.35, 0.6, 0.9),
                             (theory.semis_to_note(theory.note_to_semis(k.note(0, 3)) + 1),
                              0.35, 0.6, 0.6)]),
        "fx: lowpass(1800hz)"])]
    return _asset("sting_error", "sfx", "sting", p, body, bpm=120,
                  fadeout=min(0.15, 0.2 * p["duration"]))


_sting("sting/error", "Error", "Short descending buzz with a rub — wrong answer, failure, warning.",
       ("ui", "error", "negative"), "C minor", 0.9, _error, lo=0.6)


def _notification(p):
    k = Key(p["key"])
    body = [_layer("chime", "notes", [
        "osc: modal", "material: glass", "gain: -12db", "env: a=0.001s d=0.8s s=0.0 r=0.8s",
        "notes: " + _events([(k.note(4, 5), 0, 0.5, 0.8), (k.note(7, 5), 0.3, 1.5, 0.9)]),
        "fx: reverb(decay=1.2s, mix=0.2)"])]
    return _asset("sting_notification", "sfx", "sting", p, body, bpm=120, key=k.text,
                  fadeout=min(0.3, 0.3 * p["duration"]))


_sting("sting/notification", "Notification", "Two-note glass chime — messages, pop-ups, callouts.",
       ("ui", "notification", "chime"), "A major", 1.2, _notification, lo=0.6)


def _section(p):
    k = Key(p["key"])
    body = [
        _layer("flick", "sweep", ["shape: sine", "from: 900hz", "to: 2400hz", "curve: exp",
                                  "duration: 0.12s", "gain: -18db",
                                  "env: a=0.005s d=0.1s s=0.0 r=0.02s"]),
        _layer("tone", "notes", [
            "osc: pluck", "damping: 0.4", "brightness: 0.6", "gain: -14db", "start: 0.08s",
            "env: a=0.002s d=0.3s s=0.2 r=0.5s",
            "notes: " + _events([(k.note(4, 4), 0, 0.5, 0.8), (k.note(0, 5), 0.25, 1, 0.9)]),
            "fx: reverb(decay=1.5s, mix=0.25)"]),
    ]
    return _asset("sting_section", "sfx", "sting", p, body, bpm=120, key=k.text,
                  fadeout=min(0.3, 0.3 * p["duration"]))


_sting("sting/section", "Section tab", "Quick flick and a two-note pluck — chapter cards, section changes.",
       ("section", "chapter", "divider"), "C major", 1.2, _section, lo=0.6)


# ----------------------------------------------------------------- transitions
def _sfx(cid, kind, category, title, description, tags, params, build):
    return register(Cue(cid, kind, category, title, description, (*params, SEED), build, tags))


DIRECTION = Param("direction", "choice", "up", "sweep direction", choices=("up", "down"))


def _whoosh(p):
    d = p["duration"]
    lo, hi = (300, 4200) if p["direction"] == "up" else (4200, 300)
    peak = round(d * 0.55, 3)
    body = [
        _layer("air", "noise", [
            "color: white", "gain: -10db", f"env: a={peak}s d={round(d - peak, 3)}s s=0.0 r=0.01s",
            "fx: bandpass(1200hz, q=1.4), reverb(decay=0.9s, mix=0.2)",
            f"auto cutoff: 0s={lo}, {peak}s={int((lo * hi) ** 0.5)}, {round(d, 3)}s={hi}"]),
        _layer("body", "noise", [
            "color: pink", "gain: -16db", f"env: a={peak}s d={round(d - peak, 3)}s s=0.0 r=0.01s",
            "fx: lowpass(600hz)"]),
    ]
    return _asset("transition_whoosh", "transition", "transition", p, body, width=1.0)


_sfx("transition/whoosh", "sound-effect", "transition", "Whoosh",
     "Filtered air rush that swells and passes — cuts, slides, fast camera moves.",
     ("whoosh", "swish", "cut"), (_dur(0.9, 0.2, 4.0), DIRECTION), _whoosh)


def _riser(p):
    d = p["duration"]
    body = [
        _layer("tone", "sweep", ["shape: saw", "from: 110hz", "to: 1760hz", "curve: exp",
                                 f"duration: {round(d, 3)}s", "gain: -16db",
                                 f"env: a={round(d * 0.9, 3)}s d=0.01s s=1 r=0.01s",
                                 "fx: lowpass(600hz), reverb(decay=1.5s, mix=0.25)",
                                 f"auto cutoff: 0s=400, {round(d, 3)}s=7000"]),
        _layer("noise", "noise", ["color: white", "gain: -18db",
                                  f"env: a={round(d * 0.95, 3)}s d=0.01s s=1 r=0.01s",
                                  "fx: highpass(300hz)",
                                  f"auto cutoff: 0s=300, {round(d, 3)}s=6000"]),
    ]
    return _asset("transition_riser", "transition", "transition", p, body,
                  markers=[("hit", d)])


_sfx("transition/riser", "sound-effect", "transition", "Riser",
     "Pitch and noise build that ends exactly at `duration` — set duration = seconds until the cut.",
     ("riser", "build", "tension"), (_dur(3.0, 0.5, 20.0, "seconds until the hit point"),), _riser)


def _downlifter(p):
    d = p["duration"]
    body = [
        _layer("tone", "sweep", ["shape: saw", "from: 1760hz", "to: 70hz", "curve: exp",
                                 f"duration: {round(d, 3)}s", "gain: -16db",
                                 f"env: a=0.005s d={round(d, 3)}s s=0.0 r=0.01s",
                                 "fx: lowpass(6000hz), reverb(decay=2s, mix=0.3)",
                                 f"auto cutoff: 0s=6000, {round(d, 3)}s=300"]),
        _layer("noise", "noise", ["color: white", "gain: -18db",
                                  f"env: a=0.005s d={round(d, 3)}s s=0.0 r=0.01s",
                                  "fx: lowpass(8000hz)",
                                  f"auto cutoff: 0s=8000, {round(d, 3)}s=250"]),
    ]
    return _asset("transition_downlifter", "transition", "transition", p, body)


_sfx("transition/downlifter", "sound-effect", "transition", "Downlifter",
     "Falling sweep that releases energy after a drop or reveal.",
     ("downlifter", "fall", "release"), (_dur(2.5, 0.5, 12.0),), _downlifter)


def _impact(p):
    body = [
        _layer("boom", "drums", ["voice: kick", "tune: -12st", "decay: 4", "bend: 1",
                                 "pattern: X...............", "gain: -6db"]),
        _layer("body", "drums", ["voice: tom", "tune: -8st", "decay: 2.5",
                                 "pattern: X...............", "gain: -12db"]),
        _layer("crack", "noise", ["color: white", "gain: -12db",
                                  "env: a=0.001s d=0.25s s=0.0 r=0.05s",
                                  "fx: lowpass(3500hz), hall(rt60=2.4s, mix=0.35)"]),
    ]
    return _asset("transition_impact", "transition", "transition", p, body,
                  markers=[("hit", 0.0)])


_sfx("transition/impact", "sound-effect", "transition", "Impact",
     "Deep cinematic hit with a crack and a hall tail — reveals, title slams, scene changes.",
     ("impact", "hit", "boom", "trailer"), (_dur(3.0, 0.8, 8.0),), _impact)


def _reverse_swell(p):
    d = p["duration"]
    k = Key(p["key"])
    body = [
        _layer("cymbal", "noise", ["color: white", "gain: -14db",
                                   f"env: a={round(d, 3)}s d=0.01s s=1 r=0.01s",
                                   "fx: highpass(2500hz), reverb(decay=1s, mix=0.2)"]),
        _layer("pad", "notes", [
            "osc: pad", "gain: -16db", f"env: a={round(d, 3)}s d=0.01s s=1 r=0.01s",
            f"notes: {k.chord(0, 'maj', 3)} @ 0b for {max(1.0, d * 2)}b voicing spread",
            "fx: lowpass(3000hz)"]),
    ]
    return _asset("transition_reverse_swell", "transition", "transition", p, body,
                  bpm=120, key=k.text, markers=[("cut", d)])


_sfx("transition/reverse-swell", "sound-effect", "transition", "Reverse swell",
     "Reverse-cymbal style swell that stops dead at `duration` — suck-in before a cut.",
     ("reverse", "swell", "suck"), (_dur(1.5, 0.4, 8.0), _key("C major")), _reverse_swell)


def _glitch(p):
    d = p["duration"]
    rng = random.Random(p["seed"])
    steps = max(4, int(d / 0.0625))
    evs = []
    for i in range(steps):
        if rng.random() < 0.55:
            f = rng.choice((220, 330, 440, 660, 880, 1320, 1760))
            evs.append((f"{f}hz", i * 0.125, 0.1, round(0.6 + 0.4 * rng.random(), 2)))
    if not evs:
        evs.append(("880hz", 0, 0.1, 0.9))
    body = [
        _layer("blips", "notes", ["osc: square", "gain: -16db",
                                  "env: a=0.001s d=0.04s s=0.3 r=0.01s",
                                  f"notes: {_events(evs)}", "fx: bandpass(1500hz, q=0.8)"]),
        _layer("noise", "drums", ["voice: hat", "tune: -6st", "pattern: euclid(7,16)",
                                  "gain: -18db"]),
    ]
    return _asset("transition_glitch", "transition", "transition", p, body, bpm=240)


_sfx("transition/glitch", "sound-effect", "transition", "Glitch",
     "Stuttering digital blips (seed picks the pattern) — tech cuts, data transitions.",
     ("glitch", "digital", "tech"), (_dur(0.6, 0.2, 3.0),), _glitch)


# ------------------------------------------------------------------ UI & foley
def _click(p):
    body = [
        _layer("tick", "noise", ["color: white", "gain: -8db",
                                 "env: a=0.0005s d=0.012s s=0.0 r=0.005s", "fx: highpass(2500hz)"]),
        _layer("tone", "tone", ["osc: sine", f"freq: {p['pitch']}hz", "gain: -14db",
                                "env: a=0.0005s d=0.02s s=0.0 r=0.005s"]),
    ]
    return _asset("ui_click", "sfx", "ui", p, body)


_sfx("ui/click", "sound-effect", "ui", "Click", "Crisp interface click — buttons, cursor taps, toggles.",
     ("click", "button", "tap"),
     (_dur(0.08, 0.05, 0.5), Param("pitch", "float", 2000.0, "tone in Hz", 300.0, 8000.0)), _click)


def _pop(p):
    body = [_layer("pop", "sweep", ["shape: sine", f"from: {p['pitch']}hz",
                                    f"to: {round(p['pitch'] / 3, 1)}hz", "curve: exp",
                                    f"duration: {round(p['duration'], 3)}s", "gain: -8db",
                                    "env: a=0.001s d=0.06s s=0.2 r=0.02s"])]
    return _asset("ui_pop", "sfx", "ui", p, body)


_sfx("ui/pop", "sound-effect", "ui", "Pop", "Bubble-like pitch drop — elements appearing, likes, counters.",
     ("pop", "appear", "bubble"),
     (_dur(0.1, 0.05, 0.5), Param("pitch", "float", 900.0, "start pitch in Hz", 200.0, 4000.0)), _pop)


def _paper_swish(p):
    d = p["duration"]
    a = round(d * 0.3, 3)
    body = [_layer("swish", "noise", [
        "color: pink", "gain: -8db", f"env: a={a}s d={round(d - a, 3)}s s=0.0 r=0.01s",
        "fx: bandpass(2500hz, q=1.1)", f"auto cutoff: 0s=1500, {a}s=4200, {round(d, 3)}s=2600"])]
    return _asset("foley_paper_swish", "sfx", "foley", p, body)


_sfx("foley/paper-swish", "sound-effect", "foley", "Paper swish",
     "Paper or card sliding across a desk — page turns, cards sliding in.",
     ("paper", "slide", "swish"), (_dur(0.45, 0.15, 2.0),), _paper_swish)


def _paper_tap(p):
    body = [
        _layer("tap", "noise", ["color: white", "gain: -10db",
                                "env: a=0.0005s d=0.03s s=0.0 r=0.01s", "fx: bandpass(1800hz, q=1.2)"]),
        _layer("thump", "drums", ["voice: kick", "tune: 5st", "decay: 0.3",
                                  "pattern: x...............", "gain: -18db"]),
    ]
    return _asset("foley_paper_tap", "sfx", "foley", p, body, bpm=60)


_sfx("foley/paper-tap", "sound-effect", "foley", "Paper tap",
     "A card or sheet set down on a table — placing items, stacking.",
     ("paper", "place", "tap"), (_dur(0.25, 0.1, 1.0),), _paper_tap)


def _pin_tap(p):
    body = [
        _layer("ping", "notes", ["osc: modal", "material: steel", "gain: -14db",
                                 "env: a=0.0005s d=0.15s s=0.0 r=0.1s",
                                 f"notes: {p['pitch']}hz @ 0b for 0.5b"]),
        _layer("tick", "noise", ["color: white", "gain: -12db",
                                 "env: a=0.0003s d=0.008s s=0.0 r=0.004s", "fx: highpass(3000hz)"]),
    ]
    return _asset("foley_pin_tap", "sfx", "foley", p, body)


_sfx("foley/pin-tap", "sound-effect", "foley", "Pin tap",
     "Small metallic tap — map pins, markers, clips.",
     ("pin", "metal", "tap", "map"),
     (_dur(0.3, 0.1, 1.0), Param("pitch", "float", 2600.0, "ring pitch in Hz", 600.0, 6000.0)), _pin_tap)


def _pencil_scratch(p):
    d = p["duration"]
    body = [_layer("scratch", "noise", [
        "color: white", "gain: -10db", f"env: a=0.02s d=0.05s s=0.8 r={round(min(0.1, d / 4), 3)}s",
        "fx: bandpass(3500hz, q=1.8), tremolo(rate=21, depth=0.85), highpass(1200hz)"])]
    return _asset("foley_pencil_scratch", "sfx", "foley", p, body)


_sfx("foley/pencil-scratch", "sound-effect", "foley", "Pencil scratch",
     "Graphite on paper — drawing lines, annotations, handwriting reveals.",
     ("pencil", "writing", "draw"), (_dur(0.8, 0.2, 6.0),), _pencil_scratch)


def _stamp(p):
    body = [
        _layer("thud", "drums", ["voice: kick", "tune: -3st", "decay: 0.6",
                                 "pattern: X...............", "gain: -6db"]),
        _layer("slap", "noise", ["color: white", "gain: -12db",
                                 "env: a=0.0005s d=0.06s s=0.0 r=0.02s",
                                 "fx: bandpass(900hz, q=1.0), reverb(decay=0.5s, mix=0.15)"]),
    ]
    return _asset("foley_stamp", "sfx", "foley", p, body, bpm=60)


_sfx("foley/stamp", "sound-effect", "foley", "Stamp", "Rubber stamp or heavy object hitting a desk — approvals, verdicts.",
     ("stamp", "thud", "desk"), (_dur(0.5, 0.15, 2.0),), _stamp)


def _typing(p):
    rng = random.Random(p["seed"])
    rot = rng.randrange(16)
    body = [
        _layer("keys", "drums", ["voice: hat", "tune: -4st", "decay: 0.4",
                                 f"pattern: euclid(11,16,{rot})", "gain: -12db", "humanize: 0.6",
                                 "fx: bandpass(2600hz, q=0.9)"]),
        _layer("thock", "drums", ["voice: tom", "tune: 12st", "decay: 0.25",
                                  f"pattern: euclid(5,16,{(rot + 3) % 16})", "gain: -20db",
                                  "humanize: 0.6"]),
    ]
    return _asset("foley_typing", "sfx", "foley", p, body, bpm=p["speed"] * 15)


_sfx("foley/typing", "sound-effect", "foley", "Typing", "Keyboard typing texture — terminals, chat, writing on screen.",
     ("typing", "keyboard", "computer"),
     (_dur(2.0, 0.3, 30.0), Param("speed", "float", 8.0, "keystrokes per second (approx.)", 2.0, 14.0)),
     _typing)


# ------------------------------------------------------------------- ambience
def _room_tone(p):
    body = [
        _layer("air", "noise", ["color: brown", "gain: -12db", "env: a=0.5s d=0.1s s=1 r=0.5s",
                                "fx: lowpass(900hz), highpass(40hz)"]),
        _layer("hiss", "noise", ["color: pink", "gain: -30db", "env: a=0.5s d=0.1s s=1 r=0.5s",
                                 "fx: highpass(2000hz), lowpass(8000hz)"]),
        _layer("hum", "tone", ["osc: sine", f"freq: {p['hum']}hz", "gain: -34db",
                               "env: a=0.5s d=0.1s s=1 r=0.5s"]),
    ]
    return _asset("ambience_room_tone", "bed", "ambience", p, body, fadein=0.3, fadeout=0.5)


_sfx("ambience/room-tone", "sound-effect", "ambience", "Room tone",
     "Quiet interior air with a faint mains hum — fills silence under narration, glues cuts.",
     ("room", "tone", "interior", "silence"),
     (_dur(30.0, 2.0, 600.0), Param("hum", "float", 50.0, "mains hum in Hz (50 or 60)", 40.0, 70.0)),
     _room_tone)


def _foley_ambience(model, title, description, tags):
    def build(p):
        body = [_layer("bed", "foley", [f"model: {model}", f"intensity: {p['intensity']}",
                                        f"brightness: {p['brightness']}", "gain: -6db"])]
        return _asset(f"ambience_{model}", "bed", "ambience", p, body, fadein=1.0,
                      fadeout=min(2.0, 0.1 * p["duration"]))
    _sfx(f"ambience/{title.lower()}", "sound-effect", "ambience", title, description, tags,
         (_dur(30.0, 2.0, 600.0),
          Param("intensity", "float", 0.5, "how heavy/busy", 0.0, 1.0),
          Param("brightness", "float", 0.5, "tone colour", 0.0, 1.0)), build)


_foley_ambience("rain", "Rain", "Procedural rain wash with droplets — weather, moods, cosy interiors.",
                ("rain", "weather", "nature"))
_foley_ambience("wind", "Wind", "Procedural wind with gusts — landscapes, exteriors, isolation.",
                ("wind", "weather", "nature", "exterior"))
_foley_ambience("fire", "Fire", "Crackling fire — campfire, fireplace, warmth, destruction.",
                ("fire", "crackle", "warm"))
_foley_ambience("surf", "Ocean", "Surf and waves — coastline, travel, calm.",
                ("ocean", "surf", "water", "nature"))
