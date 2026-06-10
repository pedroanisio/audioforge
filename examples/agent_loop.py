"""Agent workflow example: from creative brief to delivered asset.

Demonstrates the loop an AI agent runs with the SDK:
  1. draft DSL from a brief
  2. compile -> structured diagnostics (errors carry line numbers)
  3. repair and re-compile
  4. inspect the compiled IR (the exact deterministic ground truth)
  5. derive A/B variants via schema-checked mutation
  6. export delivery formats; every variant is hash-tracked

Run:  python examples/agent_loop.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge

BRIEF = {
    "goal": "10s product-reveal underscore, hopeful, builds to a soft peak",
    "emotion": {"wonder": 0.6, "triumph": 0.5},
    "tempo": 100, "key": "D major", "duration_s": 10,
}

# --- step 1: the agent drafts DSL from the brief (intentionally flawed
# the way first drafts are: a typo'd property and an out-of-scale note) ----
DRAFT = """
asset reveal_underscore_v1 {{
  kind: bed
  duration: {dur}s
  tempo: {bpm}bpm
  key: {key}
  emotion: wonder={wonder}, triumph={triumph}
  intensity: 0s=0.3, 7s=1.0, 10s=0.4
  marker reveal @ 7s

  layer pad : notes {{
    osc: triangle
    detune: 7c
    gain: -8db
    env: a=1.5s d=1s s=0.8 r=2s
    notes: D3 @ 0b for 16b, A3 @ 0b for 16b, F4 @ 8b for 8b
    fx: lowpass(1800hz), reverb(decay=3s, mix=0.4)
  }}
  layer lead : notes {{
    osc: sine
    gane: -10db
    env: a=0.05s d=0.8s s=0.3 r=0.8s
    notes: D5 @ 4b for 2b, F#5 @ 8b for 2b, A5 @ 12b for 4b vel 1.1
    fx: delay(time=0.3s, feedback=0.3, mix=0.25), reverb(decay=2.5s, mix=0.4)
  }}
  master {{
    width: 0.7
    lufs: -16
    fadein: 0.5s
    fadeout: 1.5s
  }}
}}
""".format(dur=BRIEF["duration_s"], bpm=BRIEF["tempo"], key=BRIEF["key"],
           wonder=BRIEF["emotion"]["wonder"], triumph=BRIEF["emotion"]["triumph"])


def main():
    forge = AudioForge()

    # --- step 2: compile; read diagnostics like an agent would -----------
    result = forge.compile(DRAFT)
    print("first compile diagnostics:")
    for d in result.diagnostics:
        print(f"  [{d.severity}] {d.message}")

    # --- step 3: repair. 'gane' was reported as unknown; F4 was flagged
    # out-of-scale for D major (advisory) — the agent decides F#4 was meant.
    fixed = DRAFT.replace("gane:", "gain:").replace("F4 @ 8b", "F#4 @ 8b")
    result = forge.compile(fixed)
    assert result.ok, [d.message for d in result.errors]
    asset = result.assets[0]
    print(f"\ncompiled OK  id={asset.id}  hash={asset.hash[:16]}")

    # --- step 4: inspect the deterministic IR -----------------------------
    print("\ncompiled IR excerpt (what will actually render):")
    print("\n".join(asset.to_json().splitlines()[:14]), "\n  ...")

    # --- step 5: A/B variants by mutation, each its own reproducible asset
    warmer = asset.mutated("layers.0.fx.0.cutoff_hz", 1200,
                           new_id="reveal_underscore_v1_warm")
    print(f"\nvariant: {warmer.id}  hash={warmer.hash[:16]}")

    # --- step 6: export deliverables ---------------------------------------
    out = Path(__file__).parent / "out"
    for a in (asset, warmer):
        meta = a.export(out, preset="social_video")
        print(f"exported {meta['file']}  sha256={meta['output_sha256'][:16]}  "
              f"lufs={meta.get('loudness', {}).get('final_lufs')}")
    preview = asset.preview(out)
    print(f"preview  {preview['file']} ({preview['sample_rate']} Hz)")


if __name__ == "__main__":
    main()
