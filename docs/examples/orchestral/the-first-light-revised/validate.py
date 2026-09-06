"""Acceptance checks for the delivered First Light audio, score and provenance.

These checks establish technical delivery and explicit musical structure.
They do not substitute for a human listening judgment of the interpretation.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import platform
import re
import subprocess
import wave
from pathlib import Path

import numpy as np
from scipy.integrate import quad
from scipy.io import wavfile

from audioforge.determinism import spec_hash
from audioforge.dsl import compile_dsl
from audioforge.library import load_library
from audioforge.loudness import integrated_lufs
from audioforge.plan import build_render_plan
from audioforge.schema import validate_spec
from audioforge.sdk import AudioAsset
from audioforge.sequencer import TempoMap

HERE = Path(__file__).resolve().parent
ID = "the_first_light"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as file:
        while chunk := file.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def db(value):
    return float(20 * np.log10(max(float(value), 1e-12)))


def read_wav(path):
    sr, pcm = wavfile.read(path)
    assert pcm.dtype == np.int32, (path, pcm.dtype)
    return sr, pcm.astype(np.float64) / 2**31


def longest(mask, hop):
    best = current = 0
    for item in mask:
        current = current + 1 if item else 0
        best = max(best, current)
    return float(best * hop)


def meter(path):
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
           "-af", "ebur128=peak=true", "-f", "null", "-"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    text = result.stderr.rsplit("Summary:", 1)[-1]
    return {"integrated_lufs": float(re.search(r"I:\s+([-\d.]+) LUFS", text)[1]),
            "loudness_range_lu": float(re.search(r"LRA:\s+([-\d.]+) LU", text)[1]),
            "true_peak_dbtp": float(re.search(r"Peak:\s+([-\d.]+) dBFS", text)[1]),
            "measurement": "FFmpeg ebur128 with oversampled true peak", "summary": text.strip()}


def validate(audio_dir, gate_log=None, verify_log=None, final=False):
    checks = []

    def check(name, condition, evidence):
        checks.append({"name": name, "passed": bool(condition), "evidence": evidence})
        print(("PASS " if condition else "FAIL ") + name, flush=True)

    source = HERE / f"{ID}.af"
    ir = HERE / f"{ID}.ir.json"
    program_path = HERE / "program.json"
    spec = json.loads(ir.read_text())
    program = json.loads(program_path.read_text())
    compiled, diagnostics = compile_dsl(source.read_text())
    check("DSL compiles without warnings", len(compiled) == 1 and not diagnostics, diagnostics)
    check("Source and delivered IR have identical render contracts",
          spec_hash(validate_spec(compiled[0])) == spec_hash(spec), spec_hash(spec))
    issues = [d.as_dict() for d in AudioAsset(spec).validate()]
    check("Schema, timeline and resource bindings", not issues, issues)
    planned = build_render_plan(spec)
    check("Strict render plan", not planned.diagnostics and spec["routing"]["fallbacks"] == "forbid"
          and spec["routing"]["sustain_gaps"] == "forbid", planned.diagnostics)
    routes = collections.Counter(s["route"] for s in planned.plan["segments"])
    note_count = sum(len(layer["notes"]) for layer in spec["layers"])
    check("Every written note has a recorded-sample route", routes == {"sample": note_count}
          and note_count == program["notes"], dict(routes))
    distances = [s["evidence"]["keycenter_distance_semitones"] for s in planned.plan["segments"]]
    check("Sample pitch stretching stays within three semitones", max(distances) <= 3, max(distances))

    lib = load_library(spec["library"])
    used_samples = set()
    for segment in planned.plan["segments"]:
        velocity = segment["decision"]["velocity"]
        bands = velocity.get("bands", [velocity])
        for band in bands:
            for region in band["selected_regions"]:
                used_samples.add(region["sample"])
    resources = {}
    for path in sorted(used_samples):
        data = lib._verified_bytes(path)
        resources[path] = hashlib.sha256(data).hexdigest()
    for layer in spec["layers"]:
        lib.regions(layer["instrument"])
    check("All selected sample bytes match the library pin", len(resources) > 0,
          {"unique_samples": len(resources), "library": spec["library"]})
    check("No unaccounted SFZ opcodes", lib.ignored_opcodes <= {"ampeg_dynamic", "group_label"},
          {"reported": sorted(lib.ignored_opcodes),
           "scope": "The supplied SFZ group labels and ampeg_dynamic are ignored by AudioForge. This score uses explicit dynamic curves and the engine's tested velocity crossfades; it does not require those opcodes."})

    # Decode independently with scipy and compare every original channel before
    # any mixing. Stereo headers alone do not establish stereo information.
    native = []
    for path in sorted(used_samples):
        rsr, pcm = wavfile.read(lib.root/path)
        decoded, dsr = lib.audio(path)
        reference = pcm.astype(float) / (2 ** (pcm.dtype.itemsize*8-1))
        native.append(dict(sample=path, shape=list(decoded.shape),
            exact=rsr == dsr and np.array_equal(decoded, reference),
            distinct=bool(decoded.ndim == 2 and np.linalg.norm(decoded[:,0]-decoded[:,1]) > 1e-6)))
    check('Every selected stereo recording retains both original channels',
          all(x['exact'] and x['distinct'] for x in native),
          {'recordings':len(native), 'failures':[x for x in native if not x['exact'] or not x['distinct']]})

    transitions = [s['decision']['transition'] for s in planned.plan['segments']
                   if s['decision'].get('transition',{}).get('fidelity') == 'recorded']
    transition_files = sorted({t['sample'] for t in transitions})
    check('Twelve recorded transitions from four actual source intervals',
          len(transitions) == 12 and len(transition_files) == 4 and
          all(t['sample_sha256'] == resources[t['sample']] and t['provenance']['source_url'].startswith('https://www.youtube.com/') for t in transitions),
          transitions)
    from scipy.signal import find_peaks
    interval_measurements = []
    for file in transition_files:
        t = next(t for t in transitions if t['sample'] == file)
        x, rate = lib.audio(file)
        x = x.mean(axis=1) if x.ndim == 2 else x
        pitches = []
        for center in (.70,1.50):
            segment = x[int((center-.06)*rate):int((center+.06)*rate)]
            segment = segment - segment.mean()
            autocorr = np.fft.irfft(abs(np.fft.rfft(segment,16384))**2)
            lo, hi = int(rate/250), int(rate/130)
            peaks = find_peaks(autocorr[lo:hi])[0]+lo
            peak = peaks[np.argmax(autocorr[peaks])]
            # Parabolic interpolation improves the integer-lag estimate.
            delta = .5*(autocorr[peak-1]-autocorr[peak+1])/(autocorr[peak-1]-2*autocorr[peak]+autocorr[peak+1])
            pitches.append(float(69+12*np.log2(rate/(peak+delta)/440)))
        errors = [abs(a-b)*100 for a,b in zip(pitches,(t['recorded_from_midi'],t['recorded_to_midi']))]
        interval_measurements.append(dict(sample=file, expected=[t['recorded_from_midi'],t['recorded_to_midi']],
                                          measured_midi=pitches,error_cents=errors))
    check('Independent pitch analysis confirms source and destination in each recording',
          all(max(x['error_cents']) < 65 for x in interval_measurements), interval_measurements)

    original = json.loads((HERE.parent/'the-first-light/the_first_light.ir.json').read_text())
    def repetition(contract):
        layer = next(l for l in contract['layers'] if l['name']=='violin_spiccato')
        signatures=[]
        for bar in range(116):
            signatures.append(tuple(sorted((round(e['start_beat']-4*bar,3),round(e['dur_beats'],3))
                for e in layer['notes'] if 4*bar <= e['start_beat'] < 4*(bar+1))))
        run=best=0;prev=None
        for signature in signatures:
            run=run+1 if signature and signature==prev else 1 if signature else 0
            best=max(best,run);prev=signature
        return dict(longest_repeated_nonempty_rhythm_bars=best,
                    distinct_nonempty_rhythms=len(set(signatures)-{()}),
                    silent_bars=signatures.count(()),notes=len(layer['notes']))
    comparison=dict(original=repetition(original),revised=repetition(spec))
    check('Repeated backing figures replaced by varied rhythms and rests',
          comparison['revised']['longest_repeated_nonempty_rhythm_bars'] <= 3 and
          comparison['revised']['distinct_nonempty_rhythms'] >= 12 and
          comparison['revised']['silent_bars'] > comparison['original']['silent_bars'], comparison)

    tm = TempoMap(spec["tempo_map"])
    tempo = np.array(spec["tempo_map"])
    timings = []
    for section in program["sections"]:
        b = section["end_bar"] * 4
        knots = tempo[(tempo[:, 0] > 0) & (tempo[:, 0] < b), 0]
        seconds, error = quad(lambda beat: 60 / np.interp(beat, tempo[:, 0], tempo[:, 1]),
                              0, b, points=knots, epsabs=1e-8, limit=150)
        timings.append({"section": section["name"], "numerical_seconds": seconds,
                        "analytic_seconds": tm.sec(b), "error_s": abs(seconds - tm.sec(b))})
    check("Independent tempo integration agrees at every section", max(x["error_s"] for x in timings) < 1e-6, timings)
    last_gate = max(tm.sec(e["start_beat"] + e["dur_beats"]) for l in spec["layers"] for e in l["notes"])
    check("Music ends before the reserved release tail", last_gate <= 294 and 293 <= last_gate,
          {"last_note_off_s": last_gate, "remaining_seconds": 300 - last_gate})
    ledger = program["note_ledger"]
    check("No missing, duplicate or unaccounted note identities",
          len({e["id"] for l in spec["layers"] for e in l["notes"]}) == note_count
          and {e["id"] for l in spec["layers"] for e in l["notes"]} == {e["id"] for e in ledger}, note_count)
    harmony = program["harmony"]
    from compose import CHORDS, midi
    harmony_errors = [e for e in ledger if e["function"] in ("harmony", "final_tonic")
                      and e["midi"] % 12 not in CHORDS[harmony[e["bar"]]["chord"]][0]]
    check("Accompaniment and final tonic match the authored harmony", not harmony_errors, harmony_errors)
    replies = [e for e in ledger if e['function']=='diatonic_passing_reply']
    check('Viola passing notes are diatonic and resolve on the dominant of D minor',
          len(replies)==15 and all(e['midi']%12 in (2,4,5,7,9) and harmony[e['bar']]['chord']=='Dm' for e in replies)
          and all(e['midi']==57 for e in replies[4::5]), replies)
    for part in ("solo_viola", "flute", "oboe", "clarinet", "bassoon", "violins_1", "cellos"):
        layer = next(l for l in spec["layers"] if l["name"] == part)
        events = sorted(layer["notes"], key=lambda e: e["start_beat"])
        overlaps = [(a["id"], b["id"]) for a, b in zip(events, events[1:])
                    if a["start_beat"] + a["dur_beats"] > b["start_beat"] + 1e-7]
        check(f"{part}: monophonic written line", not overlaps, overlaps)
    check("Two authored themes and six contrasting sections",
          len(program["themes"]) == 2 and len(program["sections"]) == 6
          and harmony[-1]["chord"] == "D", {"bars": len(harmony), "final_chord": harmony[-1]["chord"]})

    wav = audio_dir / f"{ID}.wav"
    manifest_path = audio_dir / f"{ID}.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    with wave.open(str(wav)) as f:
        fmt = {"sample_rate": f.getframerate(), "channels": f.getnchannels(),
               "bits": f.getsampwidth() * 8, "frames": f.getnframes(),
               "duration_s": f.getnframes() / f.getframerate()}
    check("Exact 300-second stereo 48 kHz 24-bit WAV", fmt == {"sample_rate": 48000, "channels": 2,
          "bits": 24, "frames": 14_400_000, "duration_s": 300}, fmt)
    check("Manifest identifies this exact audio and score", sha(wav) == manifest["output_sha256"]
          and manifest["spec_hash"] == spec_hash(spec), {"audio_sha256": sha(wav), "spec_hash": spec_hash(spec)})
    check("Committed render plan matches the planned contract",
          manifest["plan_hash"] == planned.plan_hash
          and sha(audio_dir / manifest["plan_file"]) == manifest["plan_sha256"], manifest["plan_hash"])
    sr, audio = read_wav(wav)
    check("No non-finite samples or clipping", np.isfinite(audio).all() and np.max(abs(audio)) < 1,
          {"sample_peak_dbfs": db(np.max(abs(audio))), "clipped_samples": int(np.sum(abs(audio) >= 1))})
    engine_lufs = integrated_lufs(audio, sr)
    independent = meter(wav)
    check("Loudness target reached without heavy limiting", abs(engine_lufs + 20) < .25
          and manifest["loudness"]["limiter"]["gain_reduction_db_max"] <= 2.0,
          {"engine_lufs": engine_lufs, "mastering": manifest["loudness"]})
    check("Independent loudness and true-peak measurement", abs(independent["integrated_lufs"] + 20) < .8
          and independent["true_peak_dbtp"] <= -1.0, independent)
    corr = float(np.corrcoef(audio.T)[0, 1])
    mono_rms = np.sqrt(np.mean(audio.mean(axis=1) ** 2))
    stereo_rms = np.sqrt(np.mean(audio ** 2))
    check("Stable stereo and mono fold-down", .05 < corr < .99 and db(mono_rms / stereo_rms) > -4,
          {"channel_correlation": corr, "mono_fold_down_db": db(mono_rms / stereo_rms)})
    check("Negligible DC offset", np.max(abs(audio.mean(axis=0))) < 1e-5,
          {"mean_per_channel": audio.mean(axis=0).tolist()})
    tail_db = db(np.sqrt(np.mean(audio[-sr:] ** 2)))
    check("Ending decays before the file boundary", tail_db < -65
          and np.max(abs(audio[-48:])) < 1e-5, {"last_second_rms_dbfs": tail_db, "final_ms_peak_dbfs": db(np.max(abs(audio[-48:])))})
    hop_s = .1
    rms = np.sqrt(np.mean(audio.reshape(-1, int(sr * hop_s), 2) ** 2, axis=(1, 2)))
    times = np.arange(len(rms)) * hop_s + hop_s / 2
    expected = np.zeros(len(rms), dtype=bool)
    for layer in spec["layers"]:
        for e in layer["notes"]:
            a, b = tm.sec(e["start_beat"]), tm.sec(e["start_beat"] + e["dur_beats"])
            expected |= (times > a + .08) & (times < b)
    gap_s = longest((rms < 10**(-65 / 20)) & expected, hop_s)
    check("No unexplained interior silence", gap_s == 0, {"longest_silent_written_activity_s": gap_s, "floor_dbfs": -65})
    sections = []
    for section in program["sections"]:
        seg = audio[int(section["start_s"] * sr):int(section["end_s"] * sr)]
        sections.append({"name": section["name"], "start_s": section["start_s"], "end_s": section["end_s"],
                         "rms_dbfs": db(np.sqrt(np.mean(seg ** 2))), "peak_dbfs": db(np.max(abs(seg)))})
    section_contrast = max(s["rms_dbfs"] for s in sections) - min(s["rms_dbfs"] for s in sections)
    check("Measured section-level dynamic contrast", section_contrast >= 4.0,
          {"contrast_db": section_contrast, "sections": sections})

    solo_notes = next(l['notes'] for l in spec['layers'] if l['name']=='solo_viola')
    reply_windows=[]
    for group in sorted({e['slur'] for e in solo_notes}):
        events=[e for e in solo_notes if e['slur']==group]
        a=tm.sec(min(e['start_beat'] for e in events))
        b=tm.sec(max(e['start_beat']+e['dur_beats'] for e in events))
        reply_windows.append((int(a*sr),int(b*sr)))
    reply_sums=[np.zeros((b-a,2)) for a,b in reply_windows]
    reply_solo=[]
    stem_reports = {}
    for layer in spec["layers"]:
        name = layer["name"]
        path = audio_dir / f"{ID}_stems" / f"{name}.wav"
        ssr, stem = read_wav(path)
        for i,(a,b) in enumerate(reply_windows):
            if name=='solo_viola':
                reply_solo.append(stem[a:b].copy())
            else:
                reply_sums[i]+=stem[a:b]
        level = []
        for section in program["sections"]:
            seg = stem[int(section["start_s"] * sr):int(section["end_s"] * sr)]
            level.append(db(np.sqrt(np.mean(seg ** 2))))
        stem_reports[name] = {"section_rms_dbfs": level, "peak_dbfs": db(np.max(abs(stem))), "sha256": sha(path)}
        check(f"{name}: complete, audible, hash-verified stem", ssr == sr and stem.shape == audio.shape
              and max(level) > -65 and sha(path) == manifest["stems"][name], stem_reports[name])

    reply_balances=[dict(start_s=a/sr,end_s=b/sr,
                        solo_to_orchestra_db=db(np.linalg.norm(solo)/np.linalg.norm(rest)))
                    for (a,b),solo,rest in zip(reply_windows,reply_solo,reply_sums)]
    check('Recorded viola replies have sufficient level against the orchestra',
          len(reply_balances)==3 and all(-10 < b['solo_to_orchestra_db'] < 3 for b in reply_balances),
          {'scope':'Premaster energy ratio during each written reply; this is a balance check, not a perceptual listening score.',
           'replies':reply_balances})

    gate_evidence = gate_log.read_text() if gate_log and gate_log.exists() else ""
    match = re.search(r"(\d+) passed(?:, (\d+) skipped)?(?:, (\d+) warnings)? in", gate_evidence)
    check("Full repository gate", bool(match) and "all 5 golden specs reproduce byte-for-byte" in gate_evidence
          and not re.search(r"^FAILED |^ERROR |make: \*\*\*", gate_evidence, re.M),
          {"pytest_summary": match[0] if match else None, "log_sha256": sha(gate_log) if gate_evidence else None})
    verification = verify_log.read_text().strip() if verify_log and verify_log.exists() else ""
    check("Fresh-process byte-identical rerender", verification == "REPRODUCIBLE", verification)

    mp3 = audio_dir / f"{ID}.mp3"
    encoded = None
    if mp3.exists():
        decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp3), "-f", "f32le", "-acodec", "pcm_f32le", "-"],
                                 capture_output=True, check=True).stdout
        decoded_audio = np.frombuffer(decoded, dtype="<f4").reshape(-1, 2)
        encoded = meter(mp3)
        check("Listening copy decodes to exactly 300 seconds", decoded_audio.shape == audio.shape
              and np.isfinite(decoded_audio).all() and np.max(abs(decoded_audio)) < 1,
              {"decoded_frames": decoded_audio.shape[0], "sha256": sha(mp3), "meter": encoded})
    elif final:
        check("Listening copy exists", False, str(mp3))

    result = {"title": program["title"], "status": "passed" if all(c["passed"] for c in checks) else "failed",
              "scope": "Technical delivery, score structure, sample provenance, measured audio, regression gates and reproducibility. Musical merit and listening preference are not certified by these checks.",
              "checks": checks, "format": fmt, "independent_meter": independent,
              "sections": sections, "stems": stem_reports, "selected_sample_hashes": resources,
              "comparison": comparison, "source_interval_measurements": interval_measurements,
              "native_sample_checks": native,
              "artifacts": {"source_sha256": sha(source), "ir_sha256": sha(ir), "audio_sha256": sha(wav),
                            "program_sha256": sha(program_path), "composer_sha256": sha(HERE / "compose.py"),
                            "validator_sha256": sha(HERE / "validate.py"), "manifest_sha256": sha(manifest_path)}}
    import scipy
    import lark
    from audioforge.version import ENGINE_VERSION
    engine_files = sorted(p for p in Path("audioforge").rglob("*") if p.suffix in (".py", ".c", ".h"))
    result["environment"] = {"engine_version": ENGINE_VERSION, "python": platform.python_version(),
                             "numpy": np.__version__, "scipy": scipy.__version__, "lark": lark.__version__,
                             "render_jobs": 4, "verification_jobs": 2}
    result["engine_source_hashes"] = {p.as_posix(): sha(p) for p in engine_files}
    if final:
        assert result["status"] == "passed", [c["name"] for c in checks if not c["passed"]]
        (HERE / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
    else:
        Path("/tmp/audioforge-first-light-revised-analysis.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "failures": [c["name"] for c in checks if not c["passed"]],
                      "meter": independent, "sections": sections, "stems": stem_reports}, indent=2), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("audio_dir", type=Path)
    parser.add_argument("--gate-log", type=Path)
    parser.add_argument("--verify-log", type=Path)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    result = validate(args.audio_dir, args.gate_log, args.verify_log, args.final)
    if args.final and result["status"] != "passed":
        raise SystemExit(1)
