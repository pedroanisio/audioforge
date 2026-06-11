"""Deterministic style-pack registry for Smart DSL expansion."""
from __future__ import annotations

import copy


STYLE_PACKS = {
    "baroque": {"perform": {"style": "baroque", "expressivity": 0.45},
                "ensemble": {"family": "chamber", "size": 3, "spread": 0.25,
                             "octaves": 0},
                "voicing": {"richness": 0.35, "extensions": [7]},
                "space": {"hall": "room", "depth": 0.25}},
    "romantic": {"perform": {"style": "romantic", "expressivity": 0.75},
                 "ensemble": {"family": "orchestra", "size": 6, "spread": 0.55,
                              "octaves": 1},
                 "voicing": {"richness": 0.65, "extensions": [7, 9]},
                 "space": {"hall": "hall", "depth": 0.55}},
    "cinematic": {"perform": {"style": "cinematic", "expressivity": 0.7},
                  "ensemble": {"family": "hybrid", "size": 5, "spread": 0.5,
                               "octaves": 1},
                  "voicing": {"richness": 0.7, "extensions": [7, 9]},
                  "space": {"hall": "studio", "depth": 0.5}},
    "jazz": {"perform": {"style": "jazz", "expressivity": 0.6},
             "ensemble": {"family": "combo", "size": 2, "spread": 0.35,
                          "octaves": 0},
             "voicing": {"richness": 0.8, "extensions": [7, 9, 13]},
             "space": {"hall": "club", "depth": 0.25}},
    "ambient": {"perform": {"style": "ambient", "expressivity": 0.5},
                "ensemble": {"family": "synth", "size": 4, "spread": 0.7,
                             "octaves": 1},
                "voicing": {"richness": 0.55, "extensions": [9]},
                "space": {"hall": "large", "depth": 0.75}},
    "pop": {"perform": {"style": "pop", "expressivity": 0.45},
            "ensemble": {"family": "band", "size": 2, "spread": 0.3,
                         "octaves": 0},
            "voicing": {"richness": 0.45, "extensions": [7]},
            "space": {"hall": "studio", "depth": 0.35}},
    "trap": {"perform": {"style": "trap", "expressivity": 0.38},
             "ensemble": {"family": "electronic", "size": 3, "spread": 0.42,
                          "octaves": 1},
             "voicing": {"richness": 0.35, "extensions": [7]},
             "space": {"hall": "tight", "depth": 0.18}},
    "techno": {"perform": {"style": "techno", "expressivity": 0.25},
               "ensemble": {"family": "electronic", "size": 4, "spread": 0.35,
                            "octaves": 1},
               "voicing": {"richness": 0.25, "extensions": [9]},
               "space": {"hall": "warehouse", "depth": 0.32}},
    "choral": {"perform": {"style": "choral", "expressivity": 0.72},
               "ensemble": {"family": "voices", "size": 8, "spread": 0.6,
                            "octaves": 1},
               "voicing": {"richness": 0.7, "extensions": [7, 9]},
               "space": {"hall": "cathedral", "depth": 0.8}},
    "metal": {"perform": {"style": "metal", "expressivity": 0.42},
              "ensemble": {"family": "band", "size": 3, "spread": 0.28,
                           "octaves": 1},
              "voicing": {"richness": 0.3, "extensions": [7]},
              "space": {"hall": "stage", "depth": 0.22}},
    "minimalism": {"perform": {"style": "minimalism", "expressivity": 0.34},
                   "ensemble": {"family": "pattern", "size": 4, "spread": 0.5,
                                "octaves": 1},
                   "voicing": {"richness": 0.45, "extensions": [9]},
                   "space": {"hall": "gallery", "depth": 0.45}},
    "folk": {"perform": {"style": "folk", "expressivity": 0.58},
             "ensemble": {"family": "acoustic", "size": 2, "spread": 0.3,
                          "octaves": 0},
             "voicing": {"richness": 0.35, "extensions": [7]},
             "space": {"hall": "room", "depth": 0.2}},
}


def list_style_packs() -> list[str]:
    return sorted(STYLE_PACKS)


def style_pack(name: str) -> dict:
    if name not in STYLE_PACKS:
        raise KeyError(f"unknown style pack {name!r}")
    return copy.deepcopy(STYLE_PACKS[name])

