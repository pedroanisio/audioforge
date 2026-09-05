"""Render objective musical acceptance cases and a self-contained listening page.

Run ``python -m audioforge.tools.musical_acceptance --out /tmp/music-review``.
An optional ``--baseline-root`` points to an isolated checkout of an older
revision. Neither numerical results nor golden hashes supply listener ratings.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import html
import json
import os
from pathlib import Path
import subprocess
import sys
import wave

import numpy as np


def _source(notes: str, directives: str = "", gain: float = -18) -> str:
    return f'''asset case {{ kind: cue
 duration: 2s
 tempo: 120bpm
 {directives}
 layer part : notes {{ osc: sine
  gain: {gain}db
  env: a=0.001s d=0s s=1 r=0.2s
  notes: {notes}
 }}
 master {{ peak: -1db
  fadeout: 0s
 }}
}}'''


def cases(library_ref: dict) -> list[dict]:
    sampled = {"id": "case", "kind": "cue", "duration_s": 1, "sample_rate": 48000,
               "bpm": 120, "library": library_ref, "layers": [{"name": "part", "type": "instrument",
               "instrument": "alias", "gain_db": -12, "notes": [
                   {"note": "C5", "start_beat": 0, "dur_beats": .5}]}],
               "master": {"target_peak_dbfs": -1, "fade_out_s": 0}}
    gain = copy.deepcopy(sampled)
    gain["layers"][0].update(instrument="gain", gain_db=0)
    gain["layers"][0]["notes"][0]["note"] = "C4"
    return [
        {"id": "seventh", "title": "Preserve an authored major seventh",
         "listen_for": "Chord quality: an extra minor seventh changes the harmony.",
         "source": _source("C3maj7 @ 0b for 2b", "key: C major\n voicing: richness=0.7 extensions=7")},
        {"id": "phrase", "title": "Preserve gates in a chordal phrase",
         "listen_for": "Phrase balance and voice endings; no automatic slurs between chord tones.",
         "source": _source("C3maj @ 0b for 1b, F3maj @ 1b for 1b", "perform: expressivity=0.8")},
        {"id": "repeat", "title": "Repeat a verse, then continue",
         "listen_for": "The C note plays twice before the D ending.",
         "source": _source("C4 @ 0b for 0.5b, D4 @ 2b for 0.5b", "form: verse 0b for 2b\n repeat: verse x2")},
        {"id": "release", "title": "Release follows note-off",
         "listen_for": "The held note releases after its half-second gate.",
         "source": _source("C4 @ 0b for 1b")},
        {"id": "quiet", "title": "Respect deliberate quiet levels",
         "listen_for": "Absolute level matters in this case; avoid turning up only one revision.",
         "source": _source("C4 @ 0b for 2b", gain=-30)},
        {"id": "alias", "title": "Suppress transposition aliasing",
         "listen_for": "An 18 kHz source transposed up an octave should be filtered, not turn into a loud 12 kHz tone.",
         "spec": sampled},
        {"id": "sample_gain", "title": "Apply sampled-instrument gain once",
         "listen_for": "The numerical probe compares a stem before and after a -6 dB edit.",
         "spec": gain},
    ]


_RUNNER = r'''
import copy, json, sys
from pathlib import Path
import numpy as np
from audioforge import AudioForge, library
from audioforge.render import _write_wav
from audioforge.version import ENGINE_VERSION
request = json.loads(sys.stdin.read())
library._LIBRARY_PATHS.insert(0, Path(request["library_parent"]))
case = request["case"]
af = AudioForge()
if "source" in case:
    compiled = af.compile(case["source"])
    if not compiled.ok:
        raise RuntimeError([d.message for d in compiled.diagnostics])
    asset = compiled.assets[0]
else:
    asset = af.load_spec(case["spec"])
x, sr, meta, stems = asset.render(return_stems=True)
metrics = {"duration_s": len(x)/sr, "rms": float(np.sqrt(np.mean(x*x))),
           "peak": float(np.max(abs(x)))}
notes = asset.spec["layers"][0].get("notes", [])
if case["id"] == "seventh":
    from audioforge.theory import note_to_semis
    metrics["pitch_classes"] = sorted({note_to_semis(n["note"]) % 12 for n in notes})
if case["id"] == "phrase":
    metrics["gates_preserved"] = all(n["dur_beats"] == 1 and "slur" not in n for n in notes)
if case["id"] == "release":
    active = np.flatnonzero(abs(stems["part"]).max(axis=1) > 1e-7)
    metrics["last_active_s"] = float(active[-1]/sr)
if case["id"] in {"quiet", "sample_gain"}:
    changed = copy.deepcopy(asset.spec)
    delta = 20 if case["id"] == "quiet" else -6
    changed["layers"][0]["gain_db"] += delta
    y, _, _, alt_stems = af.load_spec(changed).render(return_stems=True)
    a, b = (x,y) if case["id"] == "quiet" else (stems["part"], alt_stems["part"])
    metrics["gain_delta_db"] = float(10*np.log10(np.mean(b*b)/np.mean(a*a)))
if case["id"] == "alias":
    metrics["interior_rms"] = float(np.sqrt(np.mean(stems["part"][int(.03*sr):int(.2*sr)]**2)))
path = Path(request["wav"])
_write_wav(path, x, sr, 24, "musical_acceptance", case["id"])
Path(request["result"]).write_text(json.dumps({"engine_version": ENGINE_VERSION,
    "spec_hash": meta["spec_hash"], "metrics": metrics}, indent=2)+"\n")
'''


def _verdict(case_id: str, metrics: dict) -> tuple[bool, str]:
    checks = {
        "seventh": (metrics.get("pitch_classes") == [0, 4, 7, 11], "Pitch classes exactly C, E, G, B"),
        "phrase": (metrics.get("gates_preserved") is True, "All authored gates and un-slurred chord voices preserved"),
        "repeat": (abs(metrics["duration_s"] - 3) < 1e-5, "Three seconds after verse x2, with continuation"),
        "release": (abs(metrics.get("last_active_s", 0) - .7) < .01, "0.5 s gate followed by 0.2 s release"),
        "quiet": (abs(metrics.get("gain_delta_db", 0) - 20) < .05, "20 dB layer edit remains 20 dB at output"),
        "alias": (metrics.get("interior_rms", 1) < .001, "Out-of-band transposition residue below RMS 0.001"),
        "sample_gain": (abs(metrics.get("gain_delta_db", 0) + 6) < .05, "-6 dB edit changes the sample stem by -6 dB"),
    }
    return checks[case_id]


def _library(out: Path) -> dict:
    from audioforge.library import generate_manifest
    root = out / "fixtures" / "acceptance_samples"
    root.mkdir(parents=True, exist_ok=True)
    for name, frequency in (("alias", 18000), ("gain", 261.625565)):
        samples = .25 * np.sin(2*np.pi*frequency*np.arange(48000)/48000)
        with wave.open(str(root / f"{name}.wav"), "wb") as wav:
            wav.setparams((1, 2, 48000, 48000, "NONE", "not compressed"))
            wav.writeframes((samples * 32767).astype("<i2").tobytes())
        (root / f"{name}.sfz").write_text(f"<region> sample={name}.wav pitch_keycenter=60 lokey=0 hikey=127 ampeg_attack=0.001 ampeg_release=0.2\n")
    manifest = generate_manifest(root)
    return {"name": root.name, "manifest_sha256": manifest["manifest_sha256"]}


def _page(report: dict, out: Path) -> str:
    cards = []
    for index, case in enumerate(report["cases"]):
        revisions = list(case["revisions"].items())
        if index % 2:
            revisions.reverse()
        players = []
        for label, (revision, result) in zip(("A", "B"), revisions):
            wav = base64.b64encode((out / result["file"]).read_bytes()).decode()
            players.append(f'<div><strong>{label}</strong> <span class="reveal">{html.escape(revision)} · {html.escape(result["engine_version"])}</span><audio controls preload="none" src="data:audio/wav;base64,{wav}"></audio><details><summary>Measured results</summary><pre>{html.escape(json.dumps(result["metrics"], indent=2))}</pre></details></div>')
        cards.append(f'<article><h2>{index+1}. {html.escape(case["title"])}</h2><p>{html.escape(case["listen_for"])}</p><div class="players">{"".join(players)}</div><p class="evidence">Current acceptance: {"PASS" if case["passed"] else "FAIL"} — {html.escape(case["criterion"])}</p><label>Listening judgment <select data-case="{case["id"]}"><option value="">Not reviewed</option><option>A preferred</option><option>B preferred</option><option>No preference</option><option>Cannot judge</option></select></label><label>Reason / audible issue<textarea data-note="{case["id"]}" rows="2"></textarea></label></article>')
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>AudioForge · Musical acceptance</title>
<style>:root{color-scheme:light dark;font:16px/1.55 system-ui;background:#f3f1ec;color:#252d2b}body{max-width:1060px;margin:48px auto;padding:0 24px}h1{font-size:2.8rem;letter-spacing:-.05em;line-height:1.1}h2{font-size:1.3rem}p{max-width:75ch}article{padding:24px;margin:24px 0;background:#fff;border:1px solid #ccd1ca;border-radius:10px}.players{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px}audio{display:block;width:100%;margin:12px 0}.reveal{visibility:hidden}body.revealed .reveal{visibility:visible}button,select,textarea{font:inherit;border:1px solid #88948a;border-radius:5px;padding:8px;background:#fff;color:inherit}button{cursor:pointer;margin:8px 8px 8px 0}label{display:block;margin-top:12px}textarea{display:block;width:95%;margin-top:6px}.evidence{color:#176348}pre{white-space:pre-wrap;font-size:.82rem}@media(prefers-color-scheme:dark){:root{background:#17201e;color:#e6eee5}article{background:#202b28;border-color:#526157}button,select,textarea{background:#17201e}.evidence{color:#92d8b3}}@media print{button,audio,textarea,select{display:none}article{break-inside:avoid}.reveal{visibility:visible}}</style>
<h1>Musical acceptance</h1><p>Numerical correctness and listening judgment are separate. These cases test specific behavior; they do not establish that an engine composes good music. No listening scores have been supplied.</p><p>Use the same playback level for both revisions. Compare pitch and harmony, timing, note endings, timbre, and fitness for the intended role. Listen at a comfortable level; the alias test may contain a high tone. Labels are concealed until revealed. All audio is embedded; nothing is uploaded.</p><button id="reveal">Reveal revisions</button><button id="save">Download listening notes</button>
''' + "".join(cards) + '''<script>
const values={};document.querySelector('#reveal').onclick=()=>document.body.classList.toggle('revealed');
document.querySelector('#save').onclick=()=>{document.querySelectorAll('[data-case]').forEach(e=>{const k=e.dataset.case;values[k]={judgment:e.value||null,notes:document.querySelector(`[data-note="${k}"]`).value}});const blob=new Blob([JSON.stringify({schema:'audioforge.listening-review/1',ratings:values},null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='listening-review.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};
</script></html>'''


def generate(out: Path, baseline_root: Path | None = None) -> dict:
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    ref = _library(out)
    root = Path(__file__).resolve().parents[2]
    revisions = {"current": root}
    if baseline_root:
        revisions["baseline"] = baseline_root.resolve()
    report = {"schema": "audioforge.musical-acceptance/1", "listening_status": "not_reviewed", "cases": []}
    for case in cases(ref):
        item = {key: case[key] for key in ("id", "title", "listen_for")}
        item["revisions"] = {}
        for revision, checkout in revisions.items():
            name = f'{case["id"]}-{revision}'
            request = {"case": case, "library_parent": str(out / "fixtures"),
                       "wav": str(out / f"{name}.wav"), "result": str(out / f"{name}.json")}
            subprocess.run([sys.executable, "-c", _RUNNER], input=json.dumps(request), text=True,
                           cwd=checkout, env={**os.environ, "PYTHONPATH": str(checkout)},
                           check=True, capture_output=True)
            result = json.loads((out / f"{name}.json").read_text())
            result.update(file=f"{name}.wav", output_sha256=hashlib.sha256((out / f"{name}.wav").read_bytes()).hexdigest())
            result["passed"], result["criterion"] = _verdict(case["id"], result["metrics"])
            item["revisions"][revision] = result
        item["passed"] = item["revisions"]["current"]["passed"]
        item["criterion"] = item["revisions"]["current"]["criterion"]
        report["cases"].append(item)
    report["passed"] = all(case["passed"] for case in report["cases"])
    (out / "manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (out / "index.html").write_text(_page(report, out))
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--baseline-root", type=Path)
    args = parser.parse_args(argv)
    try:
        report = generate(args.out, args.baseline_root)
    except subprocess.CalledProcessError as error:
        print(error.stderr, file=sys.stderr)
        return 1
    print(json.dumps({"passed": report["passed"], "cases": len(report["cases"]),
                      "report": str(args.out / "index.html")}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
