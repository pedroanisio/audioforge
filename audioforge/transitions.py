"""Pinned recordings of note changes, shared by planning and playback.

The manifest declares recording provenance and interval identity; hashes verify
bytes, not musical authenticity. A recording must include the transition and
the following sustain. This deliberately does not infer recordings from slurs,
SFZ loop points, filenames, or synthetic pitch ramps.
"""
from __future__ import annotations

import math

from .sampler import Region


def resolve_transition(lib, instrument: str, previous, current,
                       articulation: str = 'sustain') -> dict | None:
    """Resolve one explicitly mapped interval, with no nearest-interval guess."""
    if previous is None or current is None:
        return None
    a, b = int(round(previous['midi'])), int(round(current['midi']))
    entries = lib.manifest['instruments'][instrument].get('recorded_transitions', [])
    if not isinstance(entries, list):
        raise ValueError('recorded_transitions must be a list')
    hits = []
    for raw in entries:
        if not isinstance(raw, dict):
            raise ValueError('recorded transition must be an object')
        if (raw.get('from_midi'), raw.get('to_midi'), raw.get('articulation', 'sustain')) != (a, b, articulation):
            continue
        sample = raw.get('sample')
        provenance = raw.get('provenance', {})
        if not isinstance(sample, str) or not sample or not isinstance(provenance, dict) or not provenance.get('source_url') or not provenance.get('description'):
            raise ValueError('recorded transition requires sample and explicit provenance')
        offset = raw.get('offset_frames', 0)
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValueError('recorded transition offset_frames must be a nonnegative integer')
        lead = float(raw.get('lead_s', 0))
        crossfade = float(raw.get('crossfade_s', .02))
        release = float(raw.get('release_s', .1))
        if not all(math.isfinite(x) for x in (lead, crossfade, release)) or not (0 <= lead <= 1 and 0 < crossfade <= .5 and 0 <= release <= 5):
            raise ValueError('recorded transition timing is outside supported bounds')
        available_lead = (max(0, current['start_time_s'])
                          - max(0, previous['start_time_s']))
        if lead > available_lead + 1e-9:
            raise ValueError('recorded transition lead starts before the previous note')
        source_from, source_to = raw.get('recorded_from_midi', a), raw.get('recorded_to_midi', b)
        if not all(isinstance(x, int) and not isinstance(x, bool) and 0 <= x <= 127 for x in (a, b, source_from, source_to)) or b-a != source_to-source_from:
            raise ValueError('recorded transition transposition must preserve the recorded interval')
        data, rate = lib.audio(sample)  # verifies the pinned bytes before use
        if offset >= len(data):
            raise ValueError('recorded transition offset is outside the sample')
        hits.append(dict(fidelity='recorded', method='recorded_interval',
                         from_midi=a, to_midi=b, recorded_from_midi=source_from,
                         recorded_to_midi=source_to, sample=sample,
                         sample_sha256=lib._by_path[sample], offset_frames=offset,
                         source_rate=rate, source_frames=len(data), lead_s=lead,
                         crossfade_s=crossfade, release_s=release,
                         provenance=dict(provenance)))
    if len(hits) > 1:
        raise ValueError(f'ambiguous recorded transition for {instrument}: {a}->{b}')
    return hits[0] if hits else None


def transition_region(transition: dict) -> Region:
    """The transition and its sustain replace the stationary destination sample."""
    return Region(sample=transition['sample'], lokey=transition['to_midi'],
                  hikey=transition['to_midi'], pitch_keycenter=transition['recorded_to_midi'],
                  ampeg_attack=0, ampeg_release=transition['release_s'])
