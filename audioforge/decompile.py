"""Best-effort canonical IR -> .af decompiler."""
from __future__ import annotations


def _fmt_num(v) -> str:
    if isinstance(v, int) or float(v).is_integer():
        return str(int(v))
    return f"{float(v):.6g}"


def _note(ev: dict) -> str:
    pitch = ev.get("note")
    if pitch is None:
        pitch = f"{_fmt_num(ev['freq_hz'])}hz"
    s = f"{pitch} @ {_fmt_num(ev['start_beat'])}b for {_fmt_num(ev['dur_beats'])}b"
    if "vel" in ev:
        s += f" vel {_fmt_num(ev['vel'])}"
    if "art" in ev:
        s += f" art {ev['art']}"
    if "generated" in ev:
        s += f" gen {ev['generated']}"
    return s


def _notes_list(events: list[dict]) -> str:
    parts = []
    emitted_slurs = set()
    for ev in events:
        gid = ev.get("slur")
        if gid:
            if gid in emitted_slurs:
                continue
            group = [e for e in events if e.get("slur") == gid]
            if len(group) > 1:
                parts.append("slur(" + ", ".join(_note(e) for e in group) + ")")
            else:
                parts.append(_note(ev))
            emitted_slurs.add(gid)
        else:
            parts.append(_note(ev))
    return ", ".join(parts)


def _env(env: dict) -> str:
    return ("a={attack}s d={decay}s s={sustain} r={release}s"
            .format(**{k: _fmt_num(v) for k, v in env.items()}))


def _fx(fx: dict) -> str:
    t = fx["type"]
    if t == "filter":
        return f"{fx['mode']}({_fmt_num(fx['cutoff_hz'])}hz)"
    if t == "reverb":
        return f"reverb(decay={_fmt_num(fx.get('decay_s', 1.2))}s, mix={_fmt_num(fx.get('mix', 0.25))})"
    if t == "hall":
        return f"hall(rt60={_fmt_num(fx.get('rt60', 2.5))}, mix={_fmt_num(fx.get('mix', 0.3))})"
    if t == "delay":
        return f"delay(time={_fmt_num(fx.get('time_s', 0.25))}s, feedback={_fmt_num(fx.get('feedback', 0.3))}, mix={_fmt_num(fx.get('mix', 0.3))})"
    if t == "saturate":
        return f"saturate(amount={_fmt_num(fx.get('amount', 0.3))}, mix={_fmt_num(fx.get('mix', 1.0))})"
    if t == "comp":
        return f"comp(threshold={_fmt_num(fx.get('threshold', -18))}, ratio={_fmt_num(fx.get('ratio', 2.5))})"
    if t == "peak":
        return f"peak({_fmt_num(fx.get('freq_hz', 1000))}hz, gain={_fmt_num(fx.get('gain_db', 0))}, q={_fmt_num(fx.get('q', 0.7071))})"
    return t + "()"


def _auto(au: dict) -> str:
    target = {"gain_db": "gain", "cutoff_hz": "cutoff",
              "scan": "scan"}.get(au["target"], au["target"])
    unit = "db" if target == "gain" else ""
    pts = ", ".join(f"{_fmt_num(t)}s={_fmt_num(v)}{unit}"
                    for t, v in au["points"])
    return f"auto {target}: {pts}"


def _dynamic(points: list[list]) -> str:
    return ", ".join(f"{_fmt_num(b)}b={_fmt_num(v)}" for b, v in points)


def spec_to_dsl(spec: dict) -> str:
    """Emit a canonical .af representation for the render-layer IR.

    The decompiler preserves renderable events and parameters. High-level sugar
    such as motifs and smart directives is intentionally not reconstructed from
    expanded IR; agents can edit this concrete DSL and recompile it.
    """
    lines = [f"asset {spec['id']} {{"]
    lines.append(f"  kind: {spec['kind']}")
    lines.append(f"  duration: {_fmt_num(spec['duration_s'])}s")
    if "bpm" in spec:
        lines.append(f"  tempo: {_fmt_num(spec['bpm'])}bpm")
    if "key" in spec:
        lines.append(f"  key: {spec['key']}")
    score = spec.get("score", {})
    if "meter" in score:
        m = score["meter"]
        lines.append(f"  meter: {m['beats']} {m['unit']}")
    if "pickup_beats" in score:
        lines.append(f"  pickup: {_fmt_num(score['pickup_beats'])}b")
    if score.get("sections"):
        parts = [
            f"{s['name']} {_fmt_num(s['start_beat'])}b for {_fmt_num(s['dur_beats'])}b"
            for s in score["sections"]
        ]
        lines.append("  form: " + ", ".join(parts))
    for r in score.get("repeats", []):
        lines.append(f"  repeat: {r['section']} x{r['count']}")
    for lname, m in score.get("polymeter", {}).items():
        lines.append(f"  polymeter: {lname} {m['beats']} {m['unit']}")
    for m in spec.get("markers", []):
        lines.append(f"  marker {m['name']} @ {_fmt_num(m['time_s'])}s")
    lines.append("")
    for bus in spec.get("buses", []):
        lines.append(f"  bus {bus['name']} {{")
        if "gain_db" in bus:
            lines.append(f"    gain: {_fmt_num(bus['gain_db'])}db")
        if "fx" in bus:
            lines.append("    fx: " + ", ".join(_fx(fx) for fx in bus["fx"]))
        for au in bus.get("automation", []):
            lines.append(f"    {_auto(au)}")
        lines.append("  }")
    for layer in spec["layers"]:
        lines.append(f"  layer {layer.get('name', 'layer')} : {layer['type']} {{")
        for k in ("osc", "voice", "color", "shape", "model", "instrument"):
            if k in layer:
                lines.append(f"    {k}: {layer[k]}")
        if "gain_db" in layer:
            lines.append(f"    gain: {_fmt_num(layer['gain_db'])}db")
        if "pan" in layer:
            lines.append(f"    pan: {_fmt_num(layer['pan'])}")
        if "bus" in layer:
            lines.append(f"    bus: {layer['bus']}")
        if "env" in layer:
            lines.append(f"    env: {_env(layer['env'])}")
        if "dynamic" in layer:
            lines.append(f"    dynamic: {_dynamic(layer['dynamic'])}")
        if "notes" in layer:
            lines.append(f"    notes: {_notes_list(layer['notes'])}")
        if "pattern" in layer:
            lines.append(f"    pattern: {layer['pattern']}")
        if "fx" in layer:
            lines.append("    fx: " + ", ".join(_fx(fx) for fx in layer["fx"]))
        for au in layer.get("automation", []):
            lines.append(f"    {_auto(au)}")
        lines.append("  }")
    master = spec.get("master", {})
    if master:
        lines.append("  master {")
        if "stereo_width" in master:
            lines.append(f"    width: {_fmt_num(master['stereo_width'])}")
        if "target_peak_dbfs" in master:
            lines.append(f"    peak: {_fmt_num(master['target_peak_dbfs'])}db")
        if "target_lufs" in master:
            lines.append(f"    lufs: {_fmt_num(master['target_lufs'])}")
        if "fx" in master:
            lines.append("    fx: " + ", ".join(_fx(fx) for fx in master["fx"]))
        for au in master.get("automation", []):
            lines.append(f"    {_auto(au)}")
        lines.append("  }")
    lines.append("}")
    return "\n".join(lines) + "\n"
