---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 5.5 via Claude Code"
  date: "2026-09-28"
---

# Cues for video: prebuilt soundtracks and sound effects

AudioForge ships a library of **cues**: prebuilt, parameterized compositions — music
beds, stings, transitions, UI and foley sounds, ambiences — that render to WAV on
demand at the exact length a video needs. Each cue compiles to ordinary `.af` source
(`audioforge cue dsl ID` prints it), so nothing is a black box: the same parameters and
seed always give the same bytes, and any cue can be copied into a custom composition.

Cues plug straight into the scene-render format used by our video engines (Python,
Rust, C and JS implementations of `scene-render 1.1`) through its `<generated>` asset:
AudioForge is the resolver that fills the cache the renderer reads.

## Quick start

Add a music bed sized to the whole video, ducking under the voice-over bus, and a
whoosh at a cut:

```bash
audioforge scene add scene.xml bed/documentary-airy "key='E minor' intensity=0.5" \
    --id mus-bed --start 0 --gain -4 --duck-under bus-vo
audioforge scene add scene.xml transition/whoosh duration=0.8 --id fx-cut1 --start 12.4 --bus bus-sfx
```

`scene add` inserts a `<generated provider="audioforge">` asset into `<assets>` and an
`<audioTrack>` into `<audioMix>`, renders the cue next to the scene
(`assets/audio/audioforge/<id>.wav` unless `--cache` says otherwise) and pins its
SHA-256. Render the video as usual; the scene engine verifies the hash and mixes it.

To audition everything first:

```bash
audioforge cue list                      # all cues; --category bed|sting|..., --tag
audioforge cue show bed/lofi-chill       # parameters, ranges, loudness
audioforge cue gallery -o /tmp/cues      # renders every cue + index.html with players
```

## Three ways to use a cue

**1. Resolved `<generated>` assets (recommended).** Write the asset yourself or let
`scene add` do it:

```xml
<generated id="mus-bed" kind="music" provider="audioforge"
           model="bed/documentary-airy" prompt="duration=auto bpm=96 key='A minor' intensity=0.6"
           seed="7" cache="assets/audio/audioforge/mus-bed.wav"
           cacheSha256="0000000000000000000000000000000000000000000000000000000000000000"/>
...
<audioTrack id="trk-mus-bed" asset="mus-bed" role="music" start="0" gain="-4"
            duckUnder="bus-vo" fadeIn="1" fadeOut="2" fadeCurve="equal-power"/>
```

then run `audioforge scene resolve scene.xml`. The resolver reads `@model` (cue id),
parameters from `@prompt` (`name=value`, quote values with spaces), `@seed` (the
performance seed — a different take of the same cue) and optionally `@duration`; it
renders to `@cache` at the scene's `audioMix` sample rate and bit depth and writes the
file's SHA-256 into `@cacheSha256`, changing nothing else in the document. Re-running
is incremental: assets whose cache, provenance sidecar (`<cache>.audioforge.json`) and
hash agree are skipped. Change a prompt and only that asset re-renders.

**2. Plain `<audio>` files.** `audioforge cue render bed/news-pulse duration=45 -o news.wav
--snippet audio --id mus-news` writes the WAV and prints an `<audio>` element (with `bpm`
for beds, so the engine's `fitToDuration` edits on bar lines) and a matching
`<audioTrack>`.

**3. Starting point for a custom composition.** `audioforge cue dsl bed/cinematic-epic
key='C minor' > theme.af` gives the full `.af` source to edit and render with
`audioforge render`.

### Durations

- `duration=auto` — or no duration at all for beds and ambiences — sizes the cue to the
  project: `<project duration>` minus the `start` (minus `clipIn`) of the `audioTrack`
  that plays the asset. Beds and ambiences loop their material, so any length from a
  few seconds to 600 s is exact; the master fades the ending.
- Stings, UI and foley use their own default length unless one is given.
- `transition/riser` and `transition/reverse-swell` end exactly at `duration` (marker
  `hit`/`cut`): set the duration to the time left until the cut and start the track so
  it ends on the cut.

### CI and the verification gap

`audioforge scene resolve --check scene.xml` renders and writes nothing and exits **3**
when any AudioForge asset is stale (missing cache, different parameters or engine
version, or a `cacheSha256` that does not match), **1** on errors, **0** when everything
is current. Run it before rendering a video: when a `<generated>` cache fails its hash
check, the Python scene engine logs a warning and **plays silence** for that track
instead of failing the render.

## Loudness standard

So that scene gains are predictable, every cue is delivered at a fixed level:

| Category | Level | Typical scene gain |
|---|---|---|
| `bed` | −18 LUFS integrated, true peak ≤ −1 dBFS | −4 to −8 dB under narration (with `duckUnder`) |
| `sting` | −16 LUFS integrated, true peak ≤ −1 dBFS | 0 to −6 dB |
| `ambience` | −30 LUFS integrated | 0 dB |
| `transition`, `ui`, `foley` | peak-normalized to −3 dBFS | −6 to −14 dB (e.g. via an sfx bus) |

## Catalog

Every cue also takes `seed` (default 1). Beds take `bpm`, `key` (`'A minor'`, `'F#
major'`, `Am`, …) and `intensity` (0 sparse … 1 full arrangement; layers enter as it
rises). `audioforge cue show ID` lists exact ranges.

### Music beds

| Cue | Parameters (defaults) | Use |
|---|---|---|
| `bed/ambient-calm` | `duration=30.0`, `bpm=70`, `key=D major`, `intensity=0.6` | Slow major-seventh pads with sparse plucked glints; unobtrusive under narration. |
| `bed/cinematic-epic` | `duration=30.0`, `bpm=90`, `key=D minor`, `intensity=0.6` | Wide string pads over organ lows and tom ensembles — trailers, historical reveals, big statements. |
| `bed/corporate-uplift` | `duration=30.0`, `bpm=112`, `key=C major`, `intensity=0.6` | Bright I–V–vi–IV plucks over a four-on-the-floor pulse — product demos, launches, brand stories. |
| `bed/dark-ambient` | `duration=30.0`, `bpm=60`, `key=C minor`, `intensity=0.6` | Deep minor drones, grain dust and distant gong swells — mystery, space, true crime. |
| `bed/documentary-airy` | `duration=30.0`, `bpm=96`, `key=A minor`, `intensity=0.6` | Airy minor pads, a gentle plucked arpeggio and a soft pulse — explainer and science narration. |
| `bed/electronic-drive` | `duration=30.0`, `bpm=124`, `key=A minor`, `intensity=0.6` | Sixteenth-note saw bass under a four-on-the-floor kick with an opening filter — tech, motion graphics, sport. |
| `bed/lofi-chill` | `duration=30.0`, `bpm=78`, `key=C major`, `intensity=0.6` | Soft electric-piano sevenths, round bass and a laid-back beat — vlogs, tutorials, study content. |
| `bed/news-pulse` | `duration=30.0`, `bpm=120`, `key=E minor`, `intensity=0.6` | Ticking sixteenths, sub pulses and minor stabs — news, data stories, countdowns. |
| `bed/playful-quirky` | `duration=30.0`, `bpm=118`, `key=F major`, `intensity=0.6` | Bouncy marimba melody over a plucked bass and claps — kids, how-to, light-hearted explainers. |
| `bed/tension-underscore` | `duration=30.0`, `bpm=80`, `key=D minor`, `intensity=0.6` | Low drone with a muted ostinato and a filter that opens over the cue — investigations, suspense, war stories. |

### Stings

| Cue | Parameters (defaults) | Use |
|---|---|---|
| `sting/closer` | `duration=3.0`, `key=C major` | V–I cadence with a bell on the resolution — end cards, sign-offs. |
| `sting/error` | `duration=0.9`, `key=C minor` | Short descending buzz with a rub — wrong answer, failure, warning. |
| `sting/logo` | `duration=3.5`, `key=E major` | Three-note bell motif, sub boom and a shimmer tail — logo and brand reveals. |
| `sting/notification` | `duration=1.2`, `key=A major` | Two-note glass chime — messages, pop-ups, callouts. |
| `sting/opener` | `duration=3.5`, `key=C major` | Rising sweep into a bright chord bloom with a soft hit — title cards. |
| `sting/section` | `duration=1.2`, `key=C major` | Quick flick and a two-note pluck — chapter cards, section changes. |
| `sting/success` | `duration=1.4`, `key=C major` | Bright rising major arpeggio — completion, correct answer, unlock. |

### Transitions

| Cue | Parameters (defaults) | Use |
|---|---|---|
| `transition/downlifter` | `duration=2.5` | Falling sweep that releases energy after a drop or reveal. |
| `transition/glitch` | `duration=0.6` | Stuttering digital blips (seed picks the pattern) — tech cuts, data transitions. |
| `transition/impact` | `duration=3.0` | Deep cinematic hit with a crack and a hall tail — reveals, title slams, scene changes. |
| `transition/reverse-swell` | `duration=1.5`, `key=C major` | Reverse-cymbal style swell that stops dead at `duration` — suck-in before a cut. |
| `transition/riser` | `duration=3.0` | Pitch and noise build that ends exactly at `duration` — set duration = seconds until the cut. |
| `transition/whoosh` | `duration=0.9`, `direction=up` | Filtered air rush that swells and passes — cuts, slides, fast camera moves. |

### UI

| Cue | Parameters (defaults) | Use |
|---|---|---|
| `ui/click` | `duration=0.08`, `pitch=2000.0` | Crisp interface click — buttons, cursor taps, toggles. |
| `ui/pop` | `duration=0.1`, `pitch=900.0` | Bubble-like pitch drop — elements appearing, likes, counters. |

### Foley

| Cue | Parameters (defaults) | Use |
|---|---|---|
| `foley/paper-swish` | `duration=0.45` | Paper or card sliding across a desk — page turns, cards sliding in. |
| `foley/paper-tap` | `duration=0.25` | A card or sheet set down on a table — placing items, stacking. |
| `foley/pencil-scratch` | `duration=0.8` | Graphite on paper — drawing lines, annotations, handwriting reveals. |
| `foley/pin-tap` | `duration=0.3`, `pitch=2600.0` | Small metallic tap — map pins, markers, clips. |
| `foley/stamp` | `duration=0.5` | Rubber stamp or heavy object hitting a desk — approvals, verdicts. |
| `foley/typing` | `duration=2.0`, `speed=8.0` | Keyboard typing texture — terminals, chat, writing on screen. |

### Ambience

| Cue | Parameters (defaults) | Use |
|---|---|---|
| `ambience/fire` | `duration=30.0`, `intensity=0.5`, `brightness=0.5` | Crackling fire — campfire, fireplace, warmth, destruction. |
| `ambience/ocean` | `duration=30.0`, `intensity=0.5`, `brightness=0.5` | Surf and waves — coastline, travel, calm. |
| `ambience/rain` | `duration=30.0`, `intensity=0.5`, `brightness=0.5` | Procedural rain wash with droplets — weather, moods, cosy interiors. |
| `ambience/room-tone` | `duration=30.0`, `hum=50.0` | Quiet interior air with a faint mains hum — fills silence under narration, glues cuts. |
| `ambience/wind` | `duration=30.0`, `intensity=0.5`, `brightness=0.5` | Procedural wind with gusts — landscapes, exteriors, isolation. |

## Determinism and provenance

A cue renders through the same engine and determinism contract as any `.af` file: same
cue version, parameters, seed, format and engine version → byte-identical WAV. The
sidecar `<cache>.audioforge.json` records the cue id and version, resolved parameters,
spec hash, engine version, loudness report, markers and the WAV's SHA-256. A cue's
`version` is bumped whenever its composition changes, which makes the resolver re-render
it.

## Limits

- Cues are synthesized (no samples), so realism is that of the engine's voices; whether
  a mood fits a video is a listening judgment — use the gallery.
- Maximum length is 600 s (the engine's asset limit).
- Every render needs a C compiler (ADR-0012).
- The resolver edits only `@cacheSha256` of `provider="audioforge"` assets and only in the
  scene file itself; assets inside `<include>`d documents are not resolved.

See [ADR-0013](adr/0013-video-cue-library-and-scene-resolver.md) for the design record.
