# AudioForge Interop Contract

AudioForge projects the explicit note-event IR to Standard MIDI Files and MusicXML 3.1
and reads both back. The projections are deterministic; what each keeps is stated here
and asserted by `tests/test_interop.py` and `tests/test_notation_oracles.py` (the latter
against the vendored MusicXML 3.1 XSD and music21; `make oracle-check`).

## MIDI (`export_midi_bytes` / `import_midi_bytes`)

Format-1 file, 480 ticks per quarter. Track 0 is the conductor: sequence name, time
signature (when the meter's unit is a power of two), key signature, and one tempo event
per `tempo_map` point (the IR's linear ramps are stepped at their points). Every pitched
layer is its own track on its own channel (channel 10 is skipped), so equal pitches in
different layers never cut each other off. Pitch, start, duration and velocity are exact
to the tick; note articulation, lyrics, curves and automation are not projected (see the
diagnostic codes below).

Import creates one `notes` layer per `(track, channel)` that carries notes, named from
the track name, voiced from its GM program (percussion channel voiced percussively).
Pitch bend becomes layer-scope `pitch_cents` automation; RPN pitch-bend sensitivity is
honoured, otherwise the range is ±200 cents.

## MusicXML

Two exporters share `audioforge.musicxml`:

* `export_musicxml` — exact-tick interchange: one part per pitched layer, one measure per
  part, `<chord/>` for simultaneous onsets (one group per distinct duration, joined with
  `<backup>`), rests for gaps, `<backup>` for overlaps, every tempo point as a metronome
  direction. Nothing is quantized; music21 reads back exactly the IR's note time.
* `export_notated_musicxml` — the formal score: durations snap to a grid (default a 16th)
  and become standard figures with dots; measures follow the spec meter (beats *and* unit;
  per-part `polymeter`); `pickup` is an implicit measure 0; `key_map` changes appear as
  key signatures at the first barline at or after the change beat; `tempo_map` points are
  thinned to one per grid slot (sub-0.1 bpm changes collapse) and written as metronome
  directions; notes tie across barlines; a clef is chosen per part from its median pitch.
  Same-onset notes in a layer become one chord with the longest duration, truncated at
  the next onset. Dynamics, articulations, slurs, fermatas and rehearsal marks are not
  yet written (roadmap-notation T3).

`import_musicxml` reads `score-partwise` documents: one layer per `<part>` named from
`part-name`; the MusicXML cursor is followed exactly (`<chord/>`, `<backup>`,
`<forward>`, voices); `divisions`, `<time>`, `<key>`, `<sound tempo>` and metronome
directions are honoured per measure; tied notes merge into one event; a short or
`implicit` first measure becomes `score.pickup_beats`; metronome marks import as tempo
steps. Constructs the IR cannot hold — unpitched notes, grace notes, mid-piece time
signature changes, microtonal alters, empty parts — are listed under
`_meta.import.dropped` rather than vanishing. Only the first time signature is kept.

## Lossy diagnostics

`audioforge.interop.interop_diagnostics(spec, format)` reports what an export drops:

- `lossy_articulation`: MIDI export drops note articulation metadata.
- `lossy_lyrics`: lyric metadata is outside the MIDI/MusicXML export contract.
- `lossy_pitch_curve`: the exporter does not project arbitrary `pitch_cents` note or
  automation curves.
- `lossy_dynamic_curve`: the exporter preserves notes but not through-note or layer
  `dynamic` curves.

The generated per-construct coverage matrix (`python -m audioforge.tools.gen_interop`)
is a T3 deliverable of `docs/evolution/roadmap-notation.xlsx`; until then this list is
hand-maintained and checked by `tests/test_interop.py`.

## Session bundles

`export_session_bundle(spec, outdir)` writes `<id>.spec.json`, `<id>.mid`,
`<id>.plan.json` and `session.manifest.json`. The manifest uses schema
`audioforge.session-bundle/1` and records the spec hash, the render `plan_hash`, file
paths, file SHA-256 values and the interop warnings.
