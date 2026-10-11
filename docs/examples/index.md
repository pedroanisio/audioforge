---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# Composition examples

Read the DSL, reproduce a render, and compare the available recordings. Each composition has one directory containing its score, documentation, supporting scripts and local audio. Variants retain their own identities.

Start with [Transition sweep](sound-design/transition-sweep/index.md), a two-second example with no external instrument library.

## Listen locally

```sh
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html`. The gallery provides search, category filters, audio playback, source previews and links to full scores. Audio is loaded only when requested. Rebuild the gallery after adding renders.

## Reproduce an example

```sh
.venv/bin/python scripts/examples.py render transition-sweep
.venv/bin/python scripts/examples.py check
```

Pass one or more catalog IDs to `render`, or use `--all` explicitly. It writes fresh output into `audio/current/`, preserves earlier renders and records every selected example's outcome. Add `--stems` when separate parts are needed. Pinned sample libraries must be installed locally.

A compilable score may still need an instrument library. Historical examples with invalid DSL or placeholder pins are retained for study and regression coverage; their pages disclose those limitations. Existing renders may belong to earlier engine versions; consult their manifests before claiming reproduction.

## Start here: sound design

| Composition | Source status |
|---|---|
| [Transition sweep](sound-design/transition-sweep/index.md) | Compiles; self-contained |
| [Reference piano — baseline](sound-design/reference-piano/index.md) | Compiles; self-contained |
| [Reference piano — produced](sound-design/reference-piano-pro/index.md) | Compiles; self-contained |

## Electronic music

| Composition | Source status |
|---|---|
| [2030 — synthesis study](electronic/2030-synth/index.md) | Compiles; self-contained |
| [The Last 24 Hours](electronic/last-24h/index.md) | Compiles; self-contained |
| [Neon Voltage](electronic/neon-voltage/index.md) | Compiles; self-contained |
| [House 00 — source loop](electronic/house-00-source-loop/index.md) | Compiles; self-contained |
| [House 01 — filter house](electronic/house-01-filter/index.md) | Compiles; self-contained |
| [House 02 — talking synth](electronic/house-02-robot/index.md) | Compiles; self-contained |
| [House 03 — chop shop](electronic/house-03-chop/index.md) | Compiles; self-contained |
| [House 04 — phase & flange](electronic/house-04-phase/index.md) | Compiles; self-contained |
| [House 05 — around the block](electronic/house-05-full/index.md) | Compiles; self-contained |

## Orchestral compositions

| Composition | Source status |
|---|---|
| [2030 — orchestral theme](orchestral/2030/index.md) | Compiles; pinned library required |
| [Fable Symphony — synthesis](orchestral/fable-symphony/index.md) | Historical DSL; migration required |
| [Fable Symphony — orchestra](orchestral/fable-symphony-orchestral/index.md) | Compiles; pinned library required |
| [Fable Symphony — orchestra, revision 2](orchestral/fable-symphony-orchestral-v2/index.md) | Compiles; pinned library required |
| [Ode to Fable — original](orchestral/ode-to-fable/index.md) | Compiles; pinned library required |
| [Ode to Fable — symphonic rewrite](orchestral/ode-to-fable-symphonic/index.md) | Compiles; pinned library required |
| [Ode to Fable — symphonic rewrite, revision 2](orchestral/ode-to-fable-symphonic-v2/index.md) | Compiles; pinned library required |
| [To Be Alive](orchestral/to-be-alive/index.md) | Compiles; pinned library required |
| [The First Light — original](orchestral/the-first-light/index.md) | Compiles; pinned library required |
| [The First Light — revised](orchestral/the-first-light-revised/index.md) | Compiles; pinned library required |

## Five Seats, One Horizon: road trip suite

| Composition | Source status |
|---|---|
| [S01 Departure](road-trip/s01-departure/index.md) | Compiles; self-contained |
| [S02 Leaving Town](road-trip/s02-leaving-town/index.md) | Compiles; self-contained |
| [S03 Highway Opens](road-trip/s03-highway-opens/index.md) | Compiles; self-contained |
| [S04 Daydream](road-trip/s04-daydream/index.md) | Compiles; self-contained |
| [S05A Road Game Pt1](road-trip/s05a-road-game-pt1/index.md) | Compiles; self-contained |
| [S05B Road Game Pt2](road-trip/s05b-road-game-pt2/index.md) | Compiles; self-contained |
| [S06 Big View](road-trip/s06-big-view/index.md) | Compiles; self-contained |
| [S07 Rest Stop](road-trip/s07-rest-stop/index.md) | Compiles; self-contained |
| [S08 Golden Hour](road-trip/s08-golden-hour/index.md) | Compiles; self-contained |
| [S09 Arrival](road-trip/s09-arrival/index.md) | Compiles; self-contained |

## Guitar studies

| Composition | Source status |
|---|---|
| [Expressive hard-rock solo](guitar/slash-inspired-v3/index.md) | Compiles; pinned library required |
| [Sampled guitar experiment](guitar/slash-sfz-guitar-experiment/index.md) | Compiles; pinned library required |
| [Rock-ballad solo — historical target](guitar/slash-style-solo/index.md) | Historical DSL; migration required |

## Jazz compositions

| Composition | Source status |
|---|---|
| [Blue in Five](jazz/blue-in-five/index.md) | Compiles; self-contained |

## Arrangements and import studies

| Composition | Source status |
|---|---|
| [Sweet Child o’ Mine — MIDI transcription](arrangements/sweet-child-o-mine/index.md) | Compiles; self-contained |
| [Sweet Child o’ Mine — sampled arrangement](arrangements/sweet-child-o-mine-library/index.md) | Compiles; pinned library required |
| [Sweet Child o’ Mine — tuned synthesis](arrangements/sweet-child-o-mine-tuned/index.md) | Compiles; self-contained |
| [Untitled band arrangement](arrangements/mysong/index.md) | Compiles; pinned library required |

## Historical scores and diagnostic examples

| Composition | Source status |
|---|---|
| [BWV 949 — Fugue in A major](archive/bwv949/index.md) | Historical DSL; migration required |
| [Canções do Sertão](archive/cancoes-sertao/index.md) | Historical DSL; migration required |
| [Unser Leben ist ein Schatten](archive/unser-leben/index.md) | Historical DSL; migration required |

## Other retained material

The historical [riff image](archive/unassigned-assets/riff.png) and [vector version](archive/unassigned-assets/riff.svg) are retained separately; their association with a particular score is not recorded.

## Build the documentation site

The site configuration excludes local WAV masters, stems and Python caches. MP3 listening copies are included when available.

```sh
.venv/bin/python scripts/examples.py previews
.venv/bin/python scripts/examples.py gallery
uv run --no-project --with mkdocs-material mkdocs build --strict
```

## Organization and maintenance

The [layout decision](../adr/0010-composition-examples-layout.md) explains source ownership, generated artifacts and historical recordings.

`catalog.json` owns the IDs, categories, descriptions and recorded source status. `scripts/examples.py docs` generates this index and each example page. `scripts/examples.py check` checks coverage, compile expectations and documentation drift.

`migration.json` records every relocated file, its old and new paths and byte hashes. Historical evidence retains its original content and recorded paths. The old `compositions/` and `renders/` directories are no longer authoring locations.

Python SDK recipes remain in the repository's `examples/` directory. Purpose-built acceptance and rejection fixtures remain under `static/fixtures/` and `tests/fixtures/`; they are not listening examples.
