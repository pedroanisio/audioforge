---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "Claude Fable 5.1 via Claude Code"
  date: "2026-09-06"
---

# Electronic production tracks

Five compositions under `static/samples/house_*.af` exercise the toolkit ADR-0011 added:
modulation effects, the bus vocoder, sample editing and the pre-existing house core
(drum machine, sidechain duck, filter sweeps). They are the executable proof that the
engine renders the idiom end to end; the manifest values below come from
`audioforge render <spec> --analyze` and are reproducible with `audioforge verify`.

Render them from the repository root (the chop tracks read `samples/house_source_loop.wav`,
itself the render of `house_00_source_loop.af`, mixed to mono 16-bit):

```
for f in static/samples/house_0{1,2,3,4,5}_*.af; do .venv/bin/python -m audioforge.cli render "$f" -o renders/$(basename "$f" .af) --analyze; done
```

<!-- manifests:start -->

Rendered 2026-09-06 with engine 3.0.0 on the reference machine (12 cores), one track at a time,
master `peak: -1db`, `lufs: -9`, multiband glue and light saturation on every master:

| Track | What it proves | Duration | Integrated loudness | True peak | Output sha256 | Plan sha256 | Render time |
|---|---|---|---|---|---|---|---|
| `house_01_filter` | four-on-the-floor machine with swing groove, bus `duck:` pumping under the kick, resonant low-pass sweep automated across the form, arpeggiated saw bass, chorus on the stabs | 62.0 s | -9.1 LUFS | -1.04 dBFS | `b4903d1b6c02656fc1449cb6a496a67ec92595641390344e3083fda463b90a25` | `30ef3717106062a320524f5ee33d0a74e9938870b1f85cfe4167e421705f3b45` | 38 s |
| `house_02_robot` | bus `vocoder:` — a saw-chord carrier shaped by a hidden `mouth` bus (formant-swept pink noise plus a snare pattern); duck on both buses | 62.0 s | -9.0 LUFS | -1.38 dBFS | `3aaf37c18718f1dca42a57dfb22768de129e0b9c99434231b9a143ce0776e293` | `f91f3a08eced49ef118cc0f422f3760f811412b72525d2839ac77dfcd4192c4a` | 35 s |
| `house_03_chop` | sampling workflow on the engine's own loop: 16 `slices` re-sequenced by pattern digits, `offset`/`length` stutters through `bitcrush`, a `reverse` + `stretch: 2` swell, a `pitch: -12st` half-time bed | 62.0 s | -9.2 LUFS | -1.19 dBFS | `f55f5c144bc48304c41151108f67025cf4d4b5577b733703481b897aa5cbf6f6` | `4c72f28cc640ddbf76482822fa46e9355774163cd270294a920c4c73986a969c` | 42 s |
| `house_04_phase` | `phaser` on the pad, `flanger` on the hats, `chorus` on arpeggiated keys, a `bitcrush` breakdown bus, a `tape` lead, `updown`/`downup` arps, a key change | 62.0 s | -9.1 LUFS | -1.06 dBFS | `4fa9811a06115b7024321b7103c3a453b55213c670746c8e5c58966a5aba51fb` | `44dabba7139c3ad3b5d7cf661ff5a5f831c39b80d6e77d23730fd16178138d2c` | 88 s |
| `house_05_full` | everything above in one arrangement: filter intro, vocoder verse, chopped drop, crushed bridge, stretched outro; key map, tempo ramp, seven form sections | 124.0 s | -9.1 LUFS | -1.07 dBFS | `44d03a2a364f5b4aec0424bdcc17f103514ee3481272bc0c26bcdc2580c94c0e` | `e9795cdb065b659a2d8681136b96cf994ca16a9fac81caa3ed499903c74c0f37` | 248 s |

<!-- manifests:end -->

## Musical merit

These renders prove the constructs work and combine; whether they *sound* like the idiom
is a listening judgement the engine's own analysis reports explicitly decline to make
(`assessment_scope`). No statement above claims otherwise.
