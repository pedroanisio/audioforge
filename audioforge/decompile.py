"""Best-effort canonical IR -> .af decompiler."""
from __future__ import annotations


def _fmt_num(v) -> str:
    if isinstance(v, int) or float(v).is_integer():
        return str(int(v))
    return f"{float(v):.6g}"


def _note(ev: dict) -> str:
    pitch = ev.get("note")
    if pitch is None:
        if "freq_hz" in ev:
            pitch = f"{_fmt_num(ev['freq_hz'])}hz"
        elif "chord_root" in ev and "chord" in ev:
            pitch = f"{ev['chord_root']}{ev['chord']}"
        else:
            pitch = "C4"
    s = f"{pitch} @ {_fmt_num(ev['start_beat'])}b for {_fmt_num(ev['dur_beats'])}b"
    if "vel" in ev:
        s += f" vel {_fmt_num(ev['vel'])}"
    if "art" in ev:
        s += f" art {ev['art']}"
    tech = ev.get("technique") or ev.get("tech")
    if tech:
        params = ev.get("tech_params") or {}
        if params:
            body = ", ".join(
                f"{k}={_fmt_num(v) if isinstance(v, (int, float)) else v}"
                for k, v in sorted(params.items())
            )
            s += f" tech {tech}({body})"
        else:
            s += f" tech {tech}"
    for mod in ev.get("curve_mods", []) or []:
        name = mod["name"]
        value = mod["value"]
        suffix = "hz" if name == "cutoff" else "db" if name == "level" else ""
        s += f" {name}({_fmt_num(value)}{suffix})"
    if "string" in ev:
        s += f" string {int(ev['string'])}"
    if "fret" in ev:
        s += f" fret {ev['fret']}"
    if "generated" in ev:
        s += f" gen {ev['generated']}"
    return s


def _curve_time_suffix(time_basis: str) -> str:
    return "b" if time_basis.endswith("beats") else "s"


def _curve_value_suffix(target: str) -> str:
    return "c" if target == "pitch_cents" else ""


def _curve_point(curve: dict, point: list) -> str:
    target = curve["target"]
    time_basis = curve.get("time_basis", "note_beats")
    t_suf = _curve_time_suffix(time_basis)
    v_suf = _curve_value_suffix(target)
    out = f"{_fmt_num(point[0])}{t_suf}={_fmt_num(point[1])}{v_suf}"
    if len(point) > 2:
        out += f"@{point[2]}"
    return out


def _note_curve_lines(events: list[dict],
                      suppressed_targets: set[str] | None = None,
                      suppressed_by_index: dict[int, set[str]] | None = None
                      ) -> list[str]:
    suppressed_targets = suppressed_targets or set()
    suppressed_by_index = suppressed_by_index or {}
    lines = []
    for idx, ev in enumerate(events):
        for curve in ev.get("curves", []) or []:
            target = curve["target"]
            if (target in suppressed_targets
                    or target in suppressed_by_index.get(idx, set())):
                continue
            basis = curve.get("time_basis", "note_beats")
            prefix = f"curves: note {idx} {target} basis={basis}"
            if "points" in curve:
                pts = ", ".join(_curve_point(curve, p)
                                for p in curve["points"])
                lines.append(f"{prefix} {pts}")
            else:
                values = ",".join(_fmt_num(v) for v in curve["values"])
                lines.append(
                    f"{prefix} sampled t0={_fmt_num(curve['t0'])}"
                    f"{_curve_time_suffix(basis)} "
                    f"rate={_fmt_num(curve['rate_hz'])}hz "
                    f"values={values}")
    return lines


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


_CURVE_MOD_TARGETS = {
    "cutoff": "cutoff_hz",
    "level": "gain_db",
    "scan": "scan",
}

_TECHNIQUE_CURVE_TARGETS = {
    "palm_mute": {"cutoff_hz", "gain_db"},
    "dead_note": {"cutoff_hz", "gain_db"},
    "accent": {"dynamic"},
    "harmonic": {"pitch_cents"},
    "sul_ponticello": {"cutoff_hz"},
    "sul_tasto": {"cutoff_hz"},
}


def _semantic_curve_suppression(events: list[dict]) -> dict[int, set[str]]:
    out: dict[int, set[str]] = {}
    for idx, ev in enumerate(events):
        targets: set[str] = set()
        for mod in ev.get("curve_mods", []) or []:
            target = _CURVE_MOD_TARGETS.get(mod.get("name"))
            if target:
                targets.add(target)
        tech = ev.get("technique") or ev.get("tech")
        targets.update(_TECHNIQUE_CURVE_TARGETS.get(tech, set()))
        if "string" in ev and "fret" in ev and ev.get("fret") != "x":
            targets.add("cutoff_hz")
        if targets:
            out[idx] = targets
    return out


def _play_stmt(play: dict) -> str:
    s = f"play {play['motif']} @ {_fmt_num(play['at_beat'])}b"
    if play.get("legato"):
        s += " legato"
    if "art" in play:
        s += f" art {play['art']}"
    if play.get("invert"):
        s += " invert"
    if play.get("retrograde"):
        s += " retrograde"
    if "stretch" in play:
        s += f" stretch {_fmt_num(play['stretch'])}"
    if "diatonic" in play:
        s += f" diatonic {int(play['diatonic'])}"
    if play.get("transpose_st", 0.0):
        s += f" transpose {_fmt_num(play['transpose_st'])}st"
    if play.get("vel_scale", 1.0) != 1.0:
        s += f" vel {_fmt_num(play['vel_scale'])}"
    return s


def _env(env: dict) -> str:
    return ("a={attack}s d={decay}s s={sustain} r={release}s"
            .format(**{k: _fmt_num(v) for k, v in env.items()}))


def _fx(fx: dict) -> str:
    """Table-driven, lossless fx serialization: every stored parameter
    is emitted (the IR holds explicit values; round-trip fidelity wants
    all of them — hall damp and saturate warmth were silently dropped by
    the hand-listed version, found by the merge battery)."""
    t = fx["type"]
    if t == "filter":
        return (f"{fx['mode']}({_fmt_num(fx['cutoff_hz'])}hz"
                + (f", q={_fmt_num(fx['q'])}" if "q" in fx else "") + ")")
    TABLE = {
        "reverb":   [("decay_s", "decay", "s"), ("mix", "mix", "")],
        "hall":     [("rt60", "rt60", ""), ("damp", "damp", ""),
                     ("mix", "mix", "")],
        "plate":    [("decay", "decay", ""), ("damp", "damp", ""),
                     ("predelay", "predelay", ""), ("mod", "mod", ""),
                     ("modrate", "modrate", ""), ("mix", "mix", "")],
        "fdn":      [("rt60", "rt60", ""), ("rt60_high", "rt60_high", ""),
                     ("crossover", "crossover", ""), ("size", "size", ""),
                     ("mix", "mix", "")],
        "delay":    [("time_s", "time", "s"), ("feedback", "feedback", ""),
                     ("mix", "mix", "")],
        "saturate": [("amount", "amount", ""), ("mix", "mix", ""),
                     ("warmth", "warmth", "")],
        "drive":    [("amount", "amount", "")],
        "comp":     [("threshold", "threshold", ""), ("ratio", "ratio", ""),
                     ("attack", "attack", ""), ("release", "release", ""),
                     ("knee", "knee", ""), ("makeup", "makeup", "")],
        "mbcomp":   [("threshold", "threshold", ""), ("ratio", "ratio", ""),
                     ("low", "low", ""), ("high", "high", "")],
        "transient": [("attack", "attack", ""), ("sustain", "sustain", "")],
        "tremolo":  [("rate", "rate", ""), ("depth", "depth", "")],
        "peak":     [("freq_hz", None, "hz"), ("gain_db", "gain", ""),
                     ("q", "q", "")],
        "lowshelf": [("freq_hz", None, "hz"), ("gain_db", "gain", "")],
        "highshelf": [("freq_hz", None, "hz"), ("gain_db", "gain", "")],
        "convolve": [("file", "file", "STR"), ("sha256", "sha256", "STR"),
                     ("mix", "mix", ""), ("gain_db", "gain", "")],
        "gain":     [("gain_db", None, "db")],
    }
    if t in TABLE:
        parts = []
        for key, name, unit in TABLE[t]:
            if key not in fx:
                continue
            v = fx[key]
            if unit == "STR":
                val = f'"{v}"'
            else:
                val = f"{_fmt_num(v)}{unit}"
            parts.append(val if name is None else f"{name}={val}")
        return f"{t}({', '.join(parts)})"
    # unknown/plugin fx: serialize every non-type field as a named arg
    parts = []
    for k in sorted(fx):
        if k == "type":
            continue
        v = fx[k]
        parts.append(f'{k}="{v}"' if isinstance(v, str)
                     else f"{k}={_fmt_num(v)}")
    return f"{t}({', '.join(parts)})"


def _auto(au: dict) -> str:
    target = {"gain_db": "gain", "cutoff_hz": "cutoff",
              "scan": "scan"}.get(au["target"], au["target"])
    unit = "db" if target == "gain" else ""
    pts = ", ".join(f"{_fmt_num(t)}s={_fmt_num(v)}{unit}"
                    for t, v in au["points"])
    return f"auto {target}: {pts}"


def _dynamic(points: list[list]) -> str:
    return ", ".join(f"{_fmt_num(b)}b={_fmt_num(v)}" for b, v in points)


def _quote_value(value: str) -> str:
    if any(ch.isspace() for ch in value) or value == "":
        return '"' + value.replace('"', '\\"') + '"'
    return value


def _structured_intent_lines(intent: dict | None) -> list[str]:
    if not isinstance(intent, dict):
        return []
    structured = intent.get("structured")
    if not isinstance(structured, dict):
        return []
    render = structured.get("render_affecting", {})
    metadata = structured.get("metadata", {})
    if not render and not metadata:
        return []
    lines = ["  intent {"]
    for field in ("density", "contour", "texture"):
        if field in render:
            lines.append(f"    {field}: {render[field]}")
    for field in ("affect", "avoid", "style_text", "repair"):
        if field not in metadata:
            continue
        value = metadata[field]
        if isinstance(value, list):
            rendered = ", ".join(_quote_value(str(v)) for v in value)
        else:
            rendered = _quote_value(str(value))
        lines.append(f"    {field}: {rendered}")
    lines.append("  }")
    return lines


def _directive_value(value) -> str:
    if isinstance(value, list):
        return ",".join(_fmt_num(v) if isinstance(v, (int, float)) else str(v)
                        for v in value)
    if isinstance(value, (int, float)):
        return _fmt_num(value)
    return str(value)


def _perform_part(key: str, value) -> str:
    suffix = "b" if key == "segment" else ""
    return f"{key}={_directive_value(value)}{suffix}"


def _smart_directive_lines(intent: dict | None, semantic: dict) -> list[str]:
    if not isinstance(intent, dict) or not semantic.get("smart_directives"):
        return []
    fields = set(semantic["smart_directives"])
    lines = []
    if "style" in fields and "style" in intent:
        lines.append(f"  style: {intent['style']}")
    if "perform" in fields and isinstance(intent.get("perform"), dict):
        perform = intent["perform"]
        parts = [
            _perform_part(key, perform[key])
            for key in ("rubato", "amount", "segment", "style", "expressivity")
            if key in perform and key != "rubato_compiled"
        ]
        lines.append("  perform: " + " ".join(parts))
    if "ensemble" in fields and isinstance(intent.get("ensemble"), dict):
        ensemble = intent["ensemble"]
        parts = []
        if "family" in ensemble:
            parts.append(str(ensemble["family"]))
        parts.extend(
            f"{key}={_directive_value(ensemble[key])}"
            for key in ("size", "spread", "octaves")
            if key in ensemble
        )
        lines.append("  ensemble: " + " ".join(parts))
    if "voicing" in fields and isinstance(intent.get("voicing"), dict):
        voicing = intent["voicing"]
        parts = [
            f"{key}={_directive_value(voicing[key])}"
            for key in ("richness", "extensions")
            if key in voicing
        ]
        lines.append("  voicing: " + " ".join(parts))
    if "space" in fields and isinstance(intent.get("space"), dict):
        space = intent["space"]
        parts = [
            f"{key}={_directive_value(space[key])}"
            for key in ("hall", "depth")
            if key in space
        ]
        lines.append("  space: " + " ".join(parts))
    return lines


def _semantic_motif_lines(semantic: dict) -> list[str]:
    lines = []
    for name, events in semantic.get("motifs", {}).items():
        lines.append(f"  motif {name} {{")
        for event in events:
            lines.append(f"    {_note(event)}")
        lines.append("  }")
    return lines


def decompile_diagnostics(spec: dict) -> list[str]:
    """Return warnings for semantic information that cannot be reconstructed."""
    semantic = spec.get("_meta", {}).get("semantic", {})
    warnings = []
    if not semantic and spec.get("intent"):
        warnings.append(
            "lossy decompile: semantic sidecar is missing; smart directives "
            "and authored intent may be emitted only as canonical render IR"
        )
    if not semantic:
        for layer in spec.get("layers", []):
            if any(ev.get("generated") for ev in layer.get("notes", [])):
                warnings.append(
                    "lossy decompile: generated note provenance is present but "
                    "authored motifs/play statements are unavailable"
                )
                break
    return warnings


def spec_to_dsl(spec: dict) -> str:
    """Emit a canonical .af representation for the render-layer IR.

    The decompiler preserves renderable events and parameters. When the IR
    carries ``_meta.semantic`` from a DSL compile, authored motifs, play
    statements, structured intent, and smart directives are emitted at the same
    semantic altitude; otherwise the output is canonical render-layer DSL.
    """
    lines = [f"asset {spec['id']} {{"]
    semantic = spec.get("_meta", {}).get("semantic", {})
    authored_curve_targets: dict[str, set[str]] = {}
    for item in semantic.get("authored_expression", []) or []:
        lname = item.get("layer")
        field = item.get("field")
        if not lname:
            continue
        targets = authored_curve_targets.setdefault(lname, set())
        if field == "dynamic":
            targets.add("dynamic")
        elif field in {"vibrato", "glide_s"}:
            targets.add("pitch_cents")
    smart_preserved = bool(semantic.get("smart_directives"))
    preserve_authored_layers = smart_preserved or not spec.get("intent", {}).get("style")
    semantic_layers = semantic.get("layers", {}) if preserve_authored_layers else {}
    master_props = set(semantic.get("master_props", []))
    lines.append(f"  kind: {spec['kind']}")
    lines.append(f"  duration: {_fmt_num(spec['duration_s'])}s")
    if "bpm" in spec:
        lines.append(f"  tempo: {_fmt_num(spec['bpm'])}bpm")
    if spec.get("holds"):
        parts = [
            f"{_fmt_num(h['beat'])}b={_fmt_num(h['duration_s'])}s"
            for h in spec["holds"]
        ]
        lines.append("  fermata: " + ", ".join(parts))
    if "key" in spec:
        lines.append(f"  key: {spec['key']}")
    smart_lines = _smart_directive_lines(spec.get("intent"), semantic)
    if smart_lines:
        lines.extend(smart_lines)
    intent_lines = _structured_intent_lines(spec.get("intent"))
    if intent_lines:
        lines.extend(intent_lines)
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
    motif_lines = _semantic_motif_lines(semantic) if preserve_authored_layers else []
    if motif_lines:
        lines.append("")
        lines.extend(motif_lines)
    lines.append("")
    for bus in spec.get("buses", []):
        if smart_preserved and bus.get("name", "").startswith("af_"):
            continue
        lines.append(f"  bus {bus['name']} {{")
        if "gain_db" in bus:
            lines.append(f"    gain: {_fmt_num(bus['gain_db'])}db")
        if "fx" in bus:
            lines.append("    fx: " + ", ".join(_fx(fx) for fx in bus["fx"]))
        for au in bus.get("automation", []):
            lines.append(f"    {_auto(au)}")
        lines.append("  }")
    for layer in spec["layers"]:
        layer_semantic = semantic_layers.get(layer.get("name", ""), {})
        authored_props = set(layer_semantic.get("props", []))
        lines.append(f"  layer {layer.get('name', 'layer')} : {layer['type']} {{")
        for k in ("osc", "voice", "color", "shape", "model", "instrument"):
            if k in layer:
                lines.append(f"    {k}: {layer[k]}")
        if "tuning" in layer:
            lines.append("    tuning: " + ", ".join(layer["tuning"]))
        if "max_fret" in layer:
            lines.append(f"    max_fret: {int(layer['max_fret'])}")
        if "gain_db" in layer:
            lines.append(f"    gain: {_fmt_num(layer['gain_db'])}db")
        if "pan" in layer:
            lines.append(f"    pan: {_fmt_num(layer['pan'])}")
        if "bus" in layer and not (
                smart_preserved and "bus" not in authored_props
                and str(layer["bus"]).startswith("af_")):
            lines.append(f"    bus: {layer['bus']}")
        if "env" in layer:
            lines.append(f"    env: {_env(layer['env'])}")
        if "unison" in layer and not (
                smart_preserved and "unison" not in authored_props):
            lines.append(f"    unison: {int(layer['unison'])}")
        if "spread_cents" in layer and not (
                smart_preserved and "spread" not in authored_props):
            lines.append(f"    spread: "
                         f"{_fmt_num(layer['spread_cents'])}c")
        if "phrasing" in layer and not (
                smart_preserved and "phrasing" not in authored_props):
            lines.append(f"    phrasing: {_fmt_num(layer['phrasing'])}")
        if "vel_brightness" in layer and not (
                smart_preserved and "velbright" not in authored_props):
            lines.append(f"    velbright: "
                         f"{_fmt_num(layer['vel_brightness'])}")
        vb = layer.get("vibrato")
        if isinstance(vb, dict) and not (
                smart_preserved and "vibrato" not in authored_props):
            lines.append(f"    vibrato: rate={_fmt_num(vb['rate_hz'])}hz "
                         f"depth={_fmt_num(vb['depth_cents'])}c "
                         f"delay={_fmt_num(vb['delay_s'])}s")
        hz = layer.get("humanize")
        if isinstance(hz, dict) and not (
                smart_preserved and "humanize" not in authored_props):
            lines.append(f"    humanize: time="
                         f"{_fmt_num(hz.get('timing_s', 0))}s "
                         f"vel={_fmt_num(hz.get('vel', 0))}")
        if "dynamic" in layer and not (
                smart_preserved and "dynamic" not in authored_props):
            lines.append(f"    dynamic: {_dynamic(layer['dynamic'])}")
        if "notes" in layer_semantic:
            lines.append(f"    notes: {_notes_list(layer_semantic['notes'])}")
        elif "notes" in layer:
            lines.append(f"    notes: {_notes_list(layer['notes'])}")
        suppressed = authored_curve_targets.get(layer.get("name", ""), set())
        semantic_suppressed = _semantic_curve_suppression(
            layer_semantic.get("notes", []))
        for curve_line in _note_curve_lines(layer.get("notes", []), suppressed,
                                           semantic_suppressed):
            lines.append(f"    {curve_line}")
        for play in layer_semantic.get("plays", []):
            lines.append(f"    {_play_stmt(play)}")
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
            fxs = [
                fx for fx in master["fx"]
                if not (smart_preserved and "fx" not in master_props)
            ]
            if fxs:
                lines.append("    fx: " + ", ".join(_fx(fx) for fx in fxs))
        for au in master.get("automation", []):
            if au.get("from_intent") and "auto" not in master_props:
                continue
            lines.append(f"    {_auto(au)}")
        lines.append("  }")
    lines.append("}")
    return "\n".join(lines) + "\n"
