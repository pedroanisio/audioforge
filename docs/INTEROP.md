# AudioForge Interop Contract

AudioForge supports deterministic MIDI and MusicXML projection for explicit
note-event IR. MIDI preserves pitch, start, duration, velocity, tempo, and note
order. MusicXML preserves pitch, duration, meter when available, and tempo.
MIDI pitch-bend import is normalized to layer-scope `pitch_cents` automation;
RPN pitch-bend sensitivity (`0,0`) is honored when present, otherwise the
default range is +/-200 cents.

Lossy metadata is reported through `audioforge.interop.interop_diagnostics()`.
Current warning codes include:

- `lossy_articulation`: MIDI export drops note articulation metadata.
- `lossy_lyrics`: lyric metadata is outside the current MIDI/MusicXML export
  contract.
- `lossy_pitch_curve`: the exporter does not project arbitrary AudioForge
  `pitch_cents` note or automation curves.
- `lossy_dynamic_curve`: the exporter preserves notes but not AudioForge
  through-note or layer `dynamic` curves.

Session bundles are produced by `export_session_bundle(spec, outdir)` and write:

- `<id>.spec.json`
- `<id>.mid`
- `<id>.plan.json`
- `session.manifest.json`

The manifest uses schema `audioforge.session-bundle/1`, records the spec hash,
the render `plan_hash`, file paths, file SHA-256 values, and interop warnings.
