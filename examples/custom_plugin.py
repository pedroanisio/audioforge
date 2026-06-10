"""Plugin example: extending AudioForge without touching the engine.

Registers one of each extension point:
  * oscillator 'glass'      — inharmonic partial stack (bell-like)
  * fx 'bitcrush'           — lo-fi quantizer
  * drum voice 'woodblock'  — short resonant tick
  * exporter 'edl_markers'  — writes markers as a CMX-ish EDL text file
  * validator 'brand_rules' — enforces house delivery rules

Determinism contract: plugins must derive all randomness from the injected
seeded RNG (see 'woodblock'). Plugin names appear in specs, so the spec
hash automatically covers plugin selection.

Run:  python examples/custom_plugin.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import (AudioForge, register_drum_voice, register_exporter,
                        register_fx, register_oscillator, register_validator)


@register_oscillator("glass")
def glass(freq, n, sr):
    """Inharmonic partials -> glassy, bell-like tone. No randomness."""
    ratios = [(1.0, 1.0), (2.32, 0.55), (4.25, 0.3), (6.63, 0.18), (9.38, 0.1)]
    t = np.arange(n) / sr
    out = np.zeros(n)
    for r, a in ratios:
        f = freq * r
        if f < sr / 2:
            out += a * np.sin(2 * np.pi * f * t) * np.exp(-t * r * 0.8)
    return out / (np.max(np.abs(out)) or 1.0)


@register_fx("bitcrush")
def bitcrush(x, sr, params, rng):
    levels = float(params.get("levels", 12))
    hold = max(1, int(params.get("downsample", 1)))
    if hold > 1:
        x = np.repeat(x[::hold], hold)[: x.size]
    return np.round(x * levels) / levels


@register_drum_voice("woodblock")
def woodblock(sr, rng):
    n = int(0.06 * sr)
    t = np.arange(n) / sr
    body = np.sin(2 * np.pi * 1750 * t) * np.exp(-t * 90)
    click = rng.standard_normal(n) * np.exp(-t * 600) * 0.4  # seeded RNG only
    return (body + click) * 0.8


@register_exporter("edl_markers")
def edl_markers(spec, meta, out_dir: Path):
    """Markers -> simple EDL-style text for video editors."""
    if not spec.get("markers"):
        return None
    lines = [f"TITLE: {spec['id']}"]
    for i, m in enumerate(spec["markers"], 1):
        s = m["time_s"]
        hh, mm = int(s // 3600), int(s % 3600 // 60)
        ss, ff = int(s % 60), int((s % 1) * 25)
        lines.append(f"{i:03d}  MARKER  {hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}  "
                     f"* {m['name']}")
    p = out_dir / f"{spec['id']}.edl"
    p.write_text("\n".join(lines) + "\n")
    return p.name


@register_validator("brand_rules")
def brand_rules(spec):
    issues = []
    if spec["kind"] == "signature" and spec["duration_s"] > 3.5:
        issues.append("brand signatures must be <= 3.5s per brand book")
    if spec.get("master", {}).get("target_lufs", -99) > -13:
        issues.append("house rule: never master louder than -13 LUFS")
    return issues


DSL = """
asset glass_ident_v1 {
  kind: signature
  duration: 2.6s
  tempo: 100bpm
  key: E major
  marker logo_lock @ 1s

  layer bell : notes {
    osc: glass
    gain: -5db
    env: a=0.005s d=1.2s s=0 r=0.6s
    notes: E4 @ 0b for 2b, B4 @ 0.5b for 2b, E5 @ 1b for 2.5b vel 0.9
    fx: reverb(decay=2.2s, mix=0.4), bitcrush(levels=24)
  }
  layer tick : drums {
    voice: woodblock
    pattern: x.x.....
    gain: -14db
    pan: 0.3
  }
  master {
    width: 0.7
    lufs: -15
    fadeout: 0.2s
  }
}
"""


def main():
    forge = AudioForge()
    result = forge.compile(DSL)
    assert result.ok, [d.message for d in result.errors]
    asset = result.assets[0]
    for d in asset.validate():            # includes 'brand_rules' plugin
        print(f"[{d.severity}] {d.message}")
    out = Path(__file__).parent / "out"
    meta = asset.export(out)
    print(f"rendered {meta['file']}  sha256={meta['output_sha256'][:16]}")
    print(f"extra exports: {meta.get('extra_exports')}")
    # determinism holds for plugins too:
    again = forge.compile(DSL).assets[0].export(Path(out) / "again")
    print("plugin render reproducible?",
          "OK" if again["output_sha256"] == meta["output_sha256"] else "FAIL")


if __name__ == "__main__":
    main()
