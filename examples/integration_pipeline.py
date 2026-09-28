"""Pipeline integration example: AudioForge inside a production workflow.

Models a real agency scenario: a campaign needs one brand signature and a
set of delivery variants per channel, rendered as a batch with a machine-
readable ledger (spec hash -> output hash) suitable for CI verification
and asset management.

Run:  python examples/integration_pipeline.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge, verify

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).parent / "out" / "campaign"

CHANNELS = {            # channel -> export preset
    "instagram": "social_video",
    "youtube": "broadcast",
    "cinema_dcp": "cinematic_master",
}


def main():
    forge = AudioForge()
    asset = forge.load_file(ROOT / "docs" / "examples" / "sound-design" / "transition-sweep" / "transition_sweep.af").assets[0]

    ledger = {"campaign": "spring_launch", "assets": []}
    for channel, preset in CHANNELS.items():
        meta = asset.export(OUT / channel, preset=preset)
        ledger["assets"].append({
            "channel": channel,
            "file": meta["file"],
            "spec_hash": meta["spec_hash"],
            "output_sha256": meta["output_sha256"],
            "sample_rate": meta["sample_rate"],
            "bit_depth": meta["bit_depth"],
            "loudness": meta.get("loudness"),
        })
        print(f"{channel:12s} {meta['file']:44s} {meta['output_sha256'][:12]}")

    # CI-style gate: re-render one deliverable and check byte identity
    spec_path = OUT / "transition_sweep_v2.spec.json"
    spec_path.write_text(asset.to_json())
    print("\nverify (re-render == manifest)?",
          "OK" if _verify_one(forge, asset, OUT / "instagram") else "MISMATCH")

    (OUT / "ledger.json").write_text(json.dumps(ledger, indent=2))
    print(f"ledger -> {OUT / 'ledger.json'}")


def _verify_one(forge, asset, out_dir: Path) -> bool:
    manifest = json.loads(
        next(out_dir.glob("*__social_video.manifest.json")).read_text())
    import copy
    spec = copy.deepcopy(asset.spec)
    cfg = forge.export_presets["social_video"]
    spec["sample_rate"] = cfg["sample_rate"]
    spec["bit_depth"] = cfg["bit_depth"]
    spec.setdefault("master", {})["target_lufs"] = cfg["target_lufs"]
    spec["id"] = spec["id"] + "__social_video"
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        return verify(spec, manifest["output_sha256"], td)


if __name__ == "__main__":
    main()
