"""Generator + drift gate for the interop contract (ADR-0011, roadmap-notation RN-X-010).

`docs/INTEROP.md` is generated from :data:`audioforge.interop.COVERAGE` — the one
registry the exporters' lossy diagnostics also read — so the documented matrix,
the codes the engine emits and the behaviour of the exporters cannot drift apart:

    python -m audioforge.tools.gen_interop --write   # regenerate
    python -m audioforge.tools.gen_interop --check   # fail on drift

Never hand-edit the page: change the registry or the prose constants here and
rerun `--write`. `make interop-check` runs `--check` inside `make check`.
"""
from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

from audioforge.capabilities import capability_manifest
from audioforge.interop import FORMATS, coverage

ROOT = Path(__file__).resolve().parents[2]
INTEROP = ROOT / "docs" / "INTEROP.md"

_DOC_DATE = "2026-09-06"   # generator authorship date; pinned for byte-stable output
_LABELS = {"midi": "MIDI", "musicxml": "MusicXML (exact-tick)", "musicxml_notated": "MusicXML (notated)"}

_HEAD = f"""---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "audioforge.tools.gen_interop (Claude Fable 5.1 via Claude Code)"
  date: "{_DOC_DATE}"
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
result = run_tool("export", {{"spec": asset.spec, "format": "musicxml_notated"}})
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

"""

_TAIL = """
## Session bundles

`export_session_bundle(spec, outdir)` writes `<id>.spec.json`, `<id>.mid`,
`<id>.plan.json` and `session.manifest.json`. The manifest uses schema
`audioforge.session-bundle/1` and records the spec hash, the render `plan_hash`, file
paths, file SHA-256 values and the interop warnings.
"""


def _cell(cell: dict) -> str:
    status, code, note = cell["status"], cell["code"], cell["note"]
    text = f"**{status}**"
    if code:
        text += f" `{code}`"
    if note:
        text += f" — {note}"
    return text.replace("|", "\\|")


def render() -> str:
    rows = ["| Construct | Description | " + " | ".join(_LABELS[f] for f in FORMATS) + " |",
            "|---|---|" + "---|" * len(FORMATS)]
    for row in coverage():
        rows.append(f"| `{row['construct']}` | {row['description']} | "
                    + " | ".join(_cell(row[f]) for f in FORMATS) + " |")
    codes = capability_manifest()["diagnostic_codes"]
    used = sorted({row[f]["code"] for row in coverage() for f in FORMATS if row[f]["code"]})
    code_rows = ["| Code | Repair hint |", "|---|---|"]
    for code in used:
        hint = (codes.get(code) or {}).get("repair_hint", "").replace("|", "\\|")
        code_rows.append(f"| `{code}` | {hint} |")
    return (_HEAD + "\n".join(rows) + "\n\n## Diagnostic codes the exports emit\n\n"
            "Every code below is registered in the capability manifest "
            "(`docs/capability-manifest.json`) with the repair hint shown.\n\n"
            + "\n".join(code_rows) + "\n" + _TAIL)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true", help="regenerate docs/INTEROP.md")
    g.add_argument("--check", action="store_true", help="exit 1 if docs/INTEROP.md is stale")
    args = ap.parse_args(argv)
    text = render()
    if args.write:
        INTEROP.write_text(text)
        print(f"gen_interop: wrote {INTEROP.relative_to(ROOT)}")
        return 0
    current = INTEROP.read_text() if INTEROP.exists() else ""
    if current == text:
        print("interop-check: docs/INTEROP.md is in sync with audioforge.interop.COVERAGE")
        return 0
    sys.stdout.writelines(difflib.unified_diff(current.splitlines(True), text.splitlines(True),
                                               "docs/INTEROP.md (committed)", "generated"))
    print("\ninterop-check: docs/INTEROP.md is stale — run `python -m audioforge.tools.gen_interop --write`")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
