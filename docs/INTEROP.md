---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "audioforge.tools.gen_interop (Claude Fable 5.1 via Claude Code)"
  date: "2026-09-06"
---

<!-- GENERATED — do not hand-edit. Run `python -m audioforge.tools.gen_interop --write`. -->

# AudioForge Interop Contract

AudioForge projects the explicit note-event IR to Standard MIDI Files and MusicXML 3.1
and reads both back. The projections are deterministic. The matrix below is generated
from the same registry (`audioforge.interop.COVERAGE`) that drives
`interop_diagnostics()`, so every construct is either preserved, quantized in a
documented way, or reported with a registered diagnostic code — never dropped silently.
The behaviour is asserted by `tests/test_interop.py` and `tests/test_notation_oracles.py`
(the latter against the vendored MusicXML 3.1 XSD, music21 and LilyPond;
`make oracle-check`).

## Formats

* **MIDI** (`export_midi_bytes` / `import_midi_bytes`) — format-1 file, 480 ticks per
  quarter, of the spec *as performed* (repeats expanded). Track 0 is the conductor:
  sequence name, time signature (the anacrusis as its own signature when it is a whole
  number of 64ths), a key signature per key change, one tempo event per `tempo_map`
  point (ramps are stepped at their points) and a marker per section. Every pitched
  layer is its own track on a port/channel pair (channel 10 is skipped; a new
  MIDI port is selected after each 15 pitched parts) with its notes and
  lyric events. Import creates one `notes` layer per `(track, channel)` that carries
  notes, named from the track name and voiced from its GM program; pitch bend becomes
  layer-scope `pitch_cents` automation (RPN sensitivity honoured, else ±200 cents).
* **MusicXML (exact-tick)** (`export_musicxml`) — interchange of the performed timeline:
  one part per pitched layer, one measure per part, `<chord/>` for simultaneous onsets
  (one group per duration, joined with `<backup>`), rests for gaps, `<backup>` for
  overlaps, every tempo point and section as directions. Nothing is quantized; music21
  reads back exactly the IR's note time.
* **MusicXML (notated)** (`export_notated_musicxml`) — the formal score. Durations snap
  to a grid (default a 16th) and become standard figures with dots; measures follow the
  spec meter (beats *and* unit; polymeter reports `lossy_polymeter`); `pickup` is an implicit measure 0;
  `key_map` changes are key signatures at their authored offsets, including within bars;
  `tempo_map` points are thinned to one per grid slot (sub-0.1 bpm changes collapse) and
  written as metronome directions; layer `dynamic` points are dynamic marks with hairpins
  between differing marks; articulations, slurs (including `art legato` runs), tuplets
  (`<time-modification>`), lyrics, fermatas (from `holds`), rehearsal marks (from
  `score.sections`) and repeat barlines (when the repeated section sits on barlines) are
  written; notes tie across barlines; a clef is chosen per part from its median pitch.
  Equal-duration chord tones share a voice. Overlapping groups retain independent
  voices and durations; later onsets never shorten earlier notes.

`import_musicxml` reads `score-partwise` documents: one layer per `<part>` named from
`part-name`; the MusicXML cursor is followed exactly (`<chord/>`, `<backup>`,
`<forward>`, voices); `divisions`, `<time>`, `<key>`, `<sound tempo>` and metronome
directions are honoured per measure (metronome marks import as tempo *steps*); tied
notes merge into one event; a short or `implicit` first measure becomes
`score.pickup_beats`; dynamics, articulations, slurs, tuplets, lyrics, rehearsal marks,
repeat barlines and the note `dynamics` attribute come back as their IR counterparts;
a fermata records `fermata_duration` in `_meta.import.dropped`: its pause length is
unspecified, so import does not invent seconds. Written duration and the duration
after expanding repeats are distinct; the renderer expands `score.repeats`.
Constructs the IR cannot hold — unpitched or grace notes, mid-piece time-signature
changes, microtonal alters, unknown marks, empty parts — are listed under
`_meta.import.dropped` rather than vanishing. Only the first time signature is kept.

## Calling the projection

```python
xml = asset.to_musicxml(notated=True)
from audioforge.agent_tools import run_tool
result = run_tool("export", {"spec": asset.spec, "format": "musicxml_notated"})
```

The SDK returns the XML string; `interop_diagnostics` exposes the projection warnings.
The CLI writes warnings to stderr. Agent tools and MCP return the same registered codes
in their response envelope. `grid` is measured in quarter-note beats, must be a positive multiple of 1/32,
and defaults to 0.25.

## Coverage matrix

Status vocabulary: **preserved** — round-trips within the format's precision;
**quantized** — kept with the stated approximation; **lossy** / **unsupported** — dropped,
and `interop_diagnostics(spec, format)` emits the named code whenever the construct is
present; **conditional** — preserved when the stated condition holds, else the named code.

| Construct | Description | MIDI | MusicXML (exact-tick) | MusicXML (notated) |
|---|---|---|---|---|
| `pitch` | note pitch | **preserved** — note number | **preserved** — step, alter, octave | **preserved** — step, alter, octave |
| `timing` | note start and duration | **preserved** — exact to the tick (480 per quarter) | **preserved** — exact `<duration>` in divisions | **quantized** — snapped to the grid (default a 16th); independent durations and overlapping voices survive |
| `velocity` | note velocity (`vel`) | **preserved** — velocity 1..127 (vel × 96) | **preserved** — note `dynamics` attribute (% of velocity 90) | **preserved** — note `dynamics` attribute (% of velocity 90) |
| `layers` | one part or track per pitched layer, named after it | **preserved** — one track per layer with an independent MIDI port/channel pair | **preserved** — one `<part>` per layer | **preserved** — one `<part>` per layer |
| `chords` | simultaneous onsets within a layer | **preserved** — same channel, independent note-offs | **preserved** — `<chord/>`; one group per duration, joined with `<backup>` | **quantized** — equal-duration chord tones share a voice; other durations retain independent voices |
| `unpitched_layers` | layers without note events (drums, noise, samples, tone, sweeps) | **unsupported** `unsupported_layer_type` — no note events to write | **unsupported** `unsupported_layer_type` — no note events to write | **unsupported** `unsupported_layer_type` — no note events to write |
| `meter` | `score.meter` (beats and unit) | **conditional** `lossy_meter_unit` — time-signature meta event when the unit is a power of two | **preserved** — `<time>` (declared; the exact-tick view is one measure) | **preserved** — `<time>` and the bar length |
| `pickup` | `score.pickup_beats` (anacrusis) | **conditional** `lossy_pickup` — a partial first bar when the anacrusis is a whole number of 64ths | **lossy** `lossy_pickup` — single measure; no barlines to phase | **preserved** — implicit measure 0 |
| `polymeter` | `score.polymeter` (per-layer meter) | **lossy** `lossy_polymeter` — one time signature per file | **lossy** `lossy_polymeter` — the single-measure view carries the score meter only | **lossy** `lossy_polymeter` — global score meter used for reliable engraving; pitches and timing survive |
| `sections` | `score.sections` (form) | **preserved** — marker meta events | **preserved** — rehearsal-mark directions | **preserved** — rehearsal-mark directions |
| `repeats` | `score.repeats` | **preserved** — expanded as performed | **preserved** — expanded as performed | **conditional** `lossy_repeat` — repeat barlines when the section sits on barlines |
| `key` | `key` and `key_map` | **preserved** — key-signature meta events, one per change | **conditional** `lossy_key_change` — initial key; changes need the notated view | **preserved** — key signatures at their authored offsets, including within measures |
| `tempo` | `bpm` and `tempo_map` | **preserved** — one tempo event per point (ramps stepped) | **preserved** — one metronome direction per point (ramps stepped) | **quantized** — thinned to the grid; changes under 0.1 bpm collapse; ramps stepped |
| `holds` | `holds` (fermata with a length in seconds) | **lossy** `lossy_hold` — no pause is inserted | **lossy** `lossy_hold` — no pause is inserted | **lossy** `lossy_hold` — fermata sign projected; its duration in seconds is not encoded |
| `dynamic_marks` | layer `dynamic` points (pp … fff) | **lossy** `lossy_dynamic_curve` — no controller data is written | **lossy** `lossy_dynamic_curve` — marks are not written in the exact-tick view | **preserved** — dynamic marks, with hairpins between differing marks |
| `note_dynamic_curves` | through-note `dynamic` curves | **lossy** `lossy_dynamic_curve` — through-note shaping is not projected | **lossy** `lossy_dynamic_curve` — through-note shaping is not projected | **lossy** `lossy_dynamic_curve` — through-note shaping is not projected |
| `pitch_curves` | `pitch_cents` note curves and layer automation | **lossy** `lossy_pitch_curve` — arbitrary pitch curves are not projected | **lossy** `lossy_pitch_curve` — arbitrary pitch curves are not projected | **lossy** `lossy_pitch_curve` — arbitrary pitch curves are not projected |
| `articulations` | note `art` | **lossy** `lossy_articulation` — SMF carries no articulation data | **lossy** `lossy_articulation` — marks are not written in the exact-tick view | **conditional** `lossy_articulation` — known articulations project as notation; unknown marks are diagnosed |
| `slurs` | `slur( … )` groups | **lossy** `lossy_slur` — SMF carries no phrasing data | **lossy** `lossy_slur` — slurs are not written in the exact-tick view | **preserved** — `<slur>` start and stop |
| `tuplets` | `notation.tuplets` | **preserved** — sounding durations are exact | **preserved** — sounding durations are exact | **preserved** — `<time-modification>` and tuplet brackets |
| `lyrics` | `notation.lyrics` | **preserved** — lyric meta events, one per syllable | **lossy** `lossy_lyrics` — not written in the exact-tick view | **preserved** — `<lyric>` per syllable |
| `phonemes` | lyric phonemes | **lossy** `lossy_lyrics` — phonemes omitted; lyric text may be retained | **lossy** `lossy_lyrics` — phonemes omitted | **lossy** `lossy_lyrics` — phonemes omitted; lyric text retained |
| `tuning` | `notation.tuning` other than 12-EDO | **conditional** `lossy_tuning` — per-note pitch bend unless a layer needs two bends at once | **preserved** — decimal `<alter>` relative to the 12-TET natural plus the written `<accidental>` | **preserved** — decimal `<alter>` relative to the 12-TET natural plus the written `<accidental>`; `score --engrave` uses the written spelling |
| `string_fret` | note `string` / `fret` fields | **lossy** `lossy_string_fret` — not written | **lossy** `lossy_string_fret` — not written | **lossy** `lossy_string_fret` — not written |
| `markers` | `markers` (labels in real seconds) | **lossy** `lossy_marker` — markers are in seconds and are not converted to ticks | **lossy** `lossy_marker` — not written | **lossy** `lossy_marker` — not written |

## Diagnostic codes the exports emit

Every code below is registered in the capability manifest (`docs/capability-manifest.json`) with the repair hint shown.

| Code | Repair hint |
|---|---|
| `lossy_articulation` | Use MusicXML for notation metadata or accept MIDI loss. |
| `lossy_dynamic_curve` | Layer dynamic marks survive only in the notated MusicXML export; through-note dynamic curves are not projected. |
| `lossy_hold` | Fermata lengths are not written; the notated MusicXML export keeps the sign. |
| `lossy_key_change` | Key changes need the notated MusicXML export or MIDI; the exact-tick view keeps the initial key. |
| `lossy_lyrics` | Lyrics survive in MIDI (lyric events) and the notated MusicXML export; the exact-tick view drops them. |
| `lossy_marker` | Markers live in real seconds and are not written by the exports; use sections for beat-based labels. |
| `lossy_meter_unit` | MIDI time signatures need a power-of-two unit; change the meter or use MusicXML. |
| `lossy_pickup` | Declare a pickup that is a whole number of 64ths for MIDI, or use the notated MusicXML export. |
| `lossy_pitch_curve` | Arbitrary pitch_cents curves are not projected by any export; bake them into notes or accept the loss. |
| `lossy_polymeter` | Only the notated MusicXML export writes per-part meters; other formats keep the score meter. |
| `lossy_repeat` | Start and end repeated sections on barlines so the notated export can write repeat signs, or export the performed form (MIDI, exact-tick). |
| `lossy_slur` | Slurs survive only in the notated MusicXML export; use `--notated` or accept the loss. |
| `lossy_string_fret` | String and fret fields are not projected by any export yet. |
| `lossy_tuning` | Non-12-EDO tuning is metadata until the resolver lands (RN-T-002/003); exports carry 12-TET pitches. |
| `unsupported_layer_type` | Only layers with note events export; render other layers to audio or leave them out of the interchange. |

## Session bundles

`export_session_bundle(spec, outdir)` writes `<id>.spec.json`, `<id>.mid`,
`<id>.plan.json` and `session.manifest.json`. The manifest uses schema
`audioforge.session-bundle/1` and records the spec hash, the render `plan_hash`, file
paths, file SHA-256 values and the interop warnings.
