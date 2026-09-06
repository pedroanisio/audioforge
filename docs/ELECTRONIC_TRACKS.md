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

Five compositions under `docs/examples/electronic/house-*/house_*.af` exercise the toolkit ADR-0015 added:
modulation effects, the bus vocoder, sample editing and the pre-existing house core
(drum machine, sidechain duck, filter sweeps). They are the executable proof that the
engine renders the idiom end to end; the manifest values below come from
`audioforge render <spec> --analyze` and are reproducible with `audioforge verify`.

Render them from the repository root (the chop tracks read `samples/house_source_loop.wav`,
itself the render of `house_00_source_loop.af`, mixed to mono 16-bit):

```
for f in docs/examples/electronic/house-0[1-5]-*/house_0*.af; do .venv/bin/python -m audioforge.cli render "$f" -o renders/$(basename "$f" .af) --analyze; done
```

<!-- manifests:start -->

Rendered 2026-09-06 with engine 3.0.0 on the reference machine (12 cores), one track at a time;
masters carry `peak: -1db`, `lufs: -10` (`-11` for the dense chop track), multiband glue and light saturation:

| Track | What it proves | Duration | Loudness | True peak | Limiter GR | Width (full band / >200 Hz) | Output sha256 | Plan sha256 |
|---|---|---|---|---|---|---|---|---|
| `house_01_filter` | four-on-the-floor machine with swing groove, wide percussion bus, bus `duck:` pumping under the kick, resonant low-pass on the music bus and a whole-mix low-pass on the master, both swept across the form, arpeggiated saw bass, stereo chorus | 62 s | -10.1 LUFS | -1.12 dBFS | 3.4 dB | 0.081 / 0.147 | `5b20eaf51aa7e7529ccb45e5635947e1330e618061c33e073037380bd48c3fbc` | `5c2ec818a062cfbdf7151afb1cc4e87f442911d2b0b3fb4f4a688ac7b8e01f40` |
| `house_02_robot` | bus `vocoder:` — a saw-chord carrier shaped by a hidden `mouth` bus (a rhythmic square phrase and snare syllables through a formant-swept band-pass); duck on the robot and keys buses | 62 s | -10.1 LUFS | -1.06 dBFS | 2.0 dB | 0.117 / 0.128 | `b8174afb64448635e8c735a4d7349018c95024d0fd7985d0eab801eca3aaacdf` | `b53242a00788fa42a0dd36ffec9e6c07949ccdad105b31bc93600d7bfce1a5ce` |
| `house_03_chop` | sampling workflow on the engine's own loop: 16 `slices` re-sequenced by pattern digits, `offset`/`length` stutters through `bitcrush`, a `reverse` + `stretch: 2` swell, a `pitch: -12st` half-time bed | 62 s | -11.1 LUFS | -1.10 dBFS | 5.5 dB | 0.024 / 0.241 | `ac3204c80847e8c252920ba74a2ac5ff7e8fd2766996d13425745d055eb87182` | `4707eb1061fed1e9a431eb720498ccee2b5ee38ebafcc7a990207aa36b16f1bb` |
| `house_04_phase` | `phaser` (stereo) on the pads bus, `flanger` (stereo) on the hats bus, stereo `chorus` on the arps bus, a `bitcrush` breakdown bus, a `tape` lead, `updown`/`downup` arps, a key change | 62 s | -10.1 LUFS | -1.06 dBFS | 2.9 dB | 0.042 / 0.090 | `d9723a00eaee1da5d54a8038e365ed86e163adf0449cabb928a55c78367de282` | `9d464f70cdde1cf7ffaabe0d4fc4a418af475d371ec32345ce11f2d542c7aac2` |
| `house_05_full` | everything above in one arrangement: filter intro, vocoder verse, chopped drop, crushed bridge, stretched outro; key map, tempo ramp, seven form sections | 124 s | -10.1 LUFS | -1.09 dBFS | 4.5 dB | 0.059 / 0.098 | `b55b536885879d0cc6dc42425cf9b92b03d9ae30f3da9232f7d8f9ca97f6ec04` | `98f82dedba75cfb18075e64c5b4d53218b70bb8aa361559878719fa5490484ab` |

<!-- manifests:end -->

## Inspection (signal measurements on the renders)

What each construct should do is measured, not assumed. Numbers below come from the
rendered files (mono sum unless stated); the isolated-bus figures come from rendering the
named bus alone with the same engine.

| Claim | Measurement | Result |
|---|---|---|
| Filter sweep is audible (01) | spectral centroid per 8 s over the master sweep `280 Hz → 18 kHz → 250 Hz` | 385 → 609 → 1307 → 2759 → 3346 → 3345 → 1119 → 454 Hz (ratio 15.7) |
| Sidechain pump (01) | RMS 150–250 ms after each downbeat vs 20–120 ms before the next | −4.2 dB after the kick |
| Vocoder gates the carrier (02) | robot bus alone, 95th/10th-percentile 10 ms RMS ratio, vocoder on vs off | 22.1 dB vs 3.2 dB; spectral-centroid std 448 Hz vs 207 Hz |
| Chop track has no holes (03) | 5 ms RMS minimum over bars 4–24 | −24.6 dBFS, zero frames below −60 dBFS |
| Bit-crush breakdown changes the spectrum (04) | share of 1.6–3.2 kHz energy, arps section vs breakdown | 0.111 → 0.187 |
| Key change (05) | chroma (60–2000 Hz) of the F-minor and A♭-major sections | top pitch classes C F G G♯ → E♭ B♭ A♭ C |
| Tempo ramp 124 → 112 bpm (05) | median spacing of loud onsets, steady vs outro | 0.46 s vs 0.50 s |
| Stereo modulation decorrelates (04) | pads bus alone (phaser `stereo=0.5` + plate), hats bus alone (flanger `stereo=0.5`) | width 0.68 and 0.42 |

**Stereo width.** The engine's `stereo_width` is `1 − corr(L, R)` over the full band and it
flags anything under 0.08 as `mono_image`. Tracks 01 and 02 clear it; 03, 04 and 05 read
0.02–0.06 because the kick and bass are centred and mono by design and dominate the
correlation, while their content above 200 Hz measures 0.09–0.25. That advisory is reported,
not suppressed. Getting the full-band figure higher would mean widening the low end, which
this idiom does not do.

**Fixes the inspection forced.** Five render passes: pans (first renders were dead centre),
a rhythmic modulator for the vocoder (a continuous pink-noise modulator moved the spectrum but
never gated the carrier), a whole-mix master sweep (the bus-only sweep was masked by unfiltered
drums), a peak-relative `bitcrush` (absolute quantization barely touched a −30 dBFS bus), the
`stereo` LFO offset on chorus/phaser/flanger with percussion on its own wide bus, and a lower
loudness target so the limiter stops working 6 dB deep.

## Musical merit

These renders prove the constructs work and combine; whether they *sound* like the idiom
is a listening judgement the engine's own analysis reports explicitly decline to make
(`assessment_scope`). No statement above claims otherwise.
