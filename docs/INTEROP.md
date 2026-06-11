# AudioForge Interop Contract

AudioForge supports deterministic MIDI and MusicXML projection for explicit
note-event IR. MIDI preserves pitch, start, duration, velocity, tempo, and note
order. MusicXML preserves pitch, duration, meter when available, and tempo.

Lossy metadata is reported through `audioforge.interop.interop_diagnostics()`.
Current warning codes include `lossy_articulation` and `lossy_lyrics`.

Session bundles are produced by `export_session_bundle(spec, outdir)` and write:

- `<id>.spec.json`
- `<id>.mid`
- `session.manifest.json`

The manifest uses schema `audioforge.session-bundle/1`, records the spec hash,
file paths, file SHA-256 values, and interop warnings.
