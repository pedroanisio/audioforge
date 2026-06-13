from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from audioforge.sampler import parse_sfz

from .group import assign_key_ranges

GENERATED_SFZ_OPCODES = (
    "ampeg_attack",
    "ampeg_release",
    "hikey",
    "hivel",
    "lokey",
    "lovel",
    "pitch_keycenter",
    "sample",
    "seq_length",
    "seq_position",
)


@dataclass(frozen=True)
class SfzRegion:
    sample: str
    pitch_keycenter: int
    lokey: int
    hikey: int
    articulation: str = "sustain"
    lovel: int = 1
    hivel: int = 127
    seq_length: int | None = None
    seq_position: int | None = None

    def sort_key(self) -> tuple[int, int, str, int, str]:
        return (
            self.pitch_keycenter, self.lovel, self.articulation,
            self.seq_position or 0, self.sample)


def build_regions(analyses: list[dict[str, Any]], *,
                  sample_prefix: str = "samples") -> list[SfzRegion]:
    regions = []
    for row in assign_key_ranges(analyses):
        sample = Path(row["path"]).name
        regions.append(SfzRegion(
            sample=f"{sample_prefix}/{sample}",
            pitch_keycenter=int(row["midi_note"]),
            lokey=int(row["lokey"]),
            hikey=int(row["hikey"]),
            articulation=row.get("articulation", "sustain"),
            lovel=int(row.get("lovel", 1)),
            hivel=int(row.get("hivel", 127)),
            seq_length=row.get("seq_length"),
            seq_position=row.get("seq_position"),
        ))
    return sorted(regions, key=lambda r: r.sort_key())


def build_region_sets(analyses: list[dict[str, Any]], *,
                      sample_prefix: str = "samples") -> dict[str, list[SfzRegion]]:
    sets: dict[str, list[SfzRegion]] = {}
    for region in build_regions(analyses, sample_prefix=sample_prefix):
        sets.setdefault(region.articulation, []).append(region)
    return {k: sorted(v, key=lambda r: r.sort_key()) for k, v in sorted(sets.items())}


def write_sfz(regions: list[SfzRegion], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["<group>", "ampeg_attack=0", "ampeg_release=0.1", ""]
    for r in sorted(regions, key=lambda item: item.sort_key()):
        lines.extend([
            "<region>",
            f"sample={r.sample}",
            f"pitch_keycenter={r.pitch_keycenter}",
            f"lokey={r.lokey}",
            f"hikey={r.hikey}",
            f"lovel={r.lovel}",
            f"hivel={r.hivel}",
        ])
        if r.seq_length is not None:
            lines.append(f"seq_length={r.seq_length}")
        if r.seq_position is not None:
            lines.append(f"seq_position={r.seq_position}")
        lines.append("")
    text = "\n".join(lines).rstrip() + "\n"
    _, ignored = parse_sfz(text)
    if ignored:
        raise ValueError(f"generated SFZ contains ignored opcodes: {sorted(ignored)}")
    path.write_text(text)
    return path
