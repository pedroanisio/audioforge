"""Routing proof uses identifiable fixtures, not a claim of acoustic realism."""
import hashlib

import numpy as np
import pytest

from audioforge import AudioForge, library
from test_sampler_stereo import wav_bytes


@pytest.fixture
def transition_library(tmp_path):
    root = tmp_path / 'transition_probe'
    root.mkdir()
    t = np.arange(16000) / 8000
    (root / 'sustain.wav').write_bytes(wav_bytes(.2 * np.sin(2*np.pi*220*t)))
    # An unmistakable marker absent from the sustain. Real recordings are
    # validated separately in the composition delivery, never synthesized here.
    (root / 'transition.wav').write_bytes(wav_bytes(.2 * np.sin(2*np.pi*733*t)))
    (root / 'viola.sfz').write_text('<region> sample=sustain.wav lokey=48 hikey=72 pitch_keycenter=60')
    mapping = dict(sfz='viola.sfz', articulations={'sustain': 'viola.sfz'}, recorded_transitions=[dict(
        from_midi=60, to_midi=62, sample='transition.wav', offset_frames=400,
        lead_s=.04, crossfade_s=.02, release_s=.05,
        provenance=dict(source_url='https://example.org/test-fixture',
                        description='Synthetic routing fixture; not an acoustic recording.'))])
    m = library.generate_manifest(root, name='transition_probe', instruments={'viola': mapping})
    library.add_library_path(tmp_path)
    return root, m


def asset_for(manifest, reverse=False, gap=False):
    notes = ('D4', 'C4') if reverse else ('C4', 'D4')
    src = f'''asset transitions {{
kind: cue
duration: 2s
tempo: 120bpm
library: "transition_probe@{manifest['manifest_sha256']}"
layer v : instrument {{
instrument: viola
notes: {notes[0]} @ 0b for 1b vel 0.5, {notes[1]} @ {1.5 if gap else 1}b for 1b vel 0.5
}}
master {{ peak: -1db }}
}}'''
    compiled = AudioForge().compile(src)
    assert compiled.ok, compiled.diagnostics
    a = compiled.assets[0]
    for event in a.spec['layers'][0]['notes']:
        event['slur'] = 1
        event['voice'] = 'solo'
    a.spec['routing'] = dict(fallbacks='forbid', sustain_gaps='forbid')
    return a


def test_recording_selected_and_hash_evidenced(transition_library):
    root, manifest = transition_library
    a = asset_for(manifest)
    plan = a.plan()['plan']
    incoming = plan['segments'][1]['decision']['transition']
    assert incoming['fidelity'] == 'recorded'
    assert incoming['sample_sha256'] == hashlib.sha256((root/'transition.wav').read_bytes()).hexdigest()
    assert (incoming['from_midi'], incoming['to_midi'], incoming['offset_frames']) == (60, 62, 400)
    assert plan['segments'][1]['decision']['velocity']['selected_regions'][0]['sample'] == 'transition.wav'
    st, sr, _ = a.render()
    x = st[int(.6*sr):int(.9*sr), 0]
    frequency = np.fft.rfftfreq(len(x), 1/sr)[np.argmax(np.abs(np.fft.rfft(x)))]
    assert abs(frequency-733) < 5


def test_missing_interval_fails_strict_policy(transition_library):
    _, m = transition_library
    with pytest.raises(ValueError, match='fallback_forbid'):
        asset_for(m, reverse=True).plan()


def test_phrase_break_uses_sustain(transition_library):
    _, m = transition_library
    plan = asset_for(m, gap=True).plan()['plan']
    assert all('transition' not in s['decision'] for s in plan['segments'])


def test_transition_bytes_verified_before_plan(transition_library):
    root, m = transition_library
    (root/'transition.wav').write_bytes(wav_bytes(np.zeros(16000)))
    with pytest.raises(ValueError, match='hash mismatch'):
        asset_for(m).plan()


def test_offset_counts_against_playable_duration(transition_library):
    root, m = transition_library
    entry = m['instruments']['viola']['recorded_transitions'][0]
    entry['offset_frames'] = 15000
    m = library.generate_manifest(root, name='transition_probe', instruments=m['instruments'])
    with pytest.raises(ValueError, match='sustain_gap'):
        asset_for(m).plan()


@pytest.mark.parametrize('field,value,message', [
    ('offset_frames', -1, 'offset_frames'),
    ('offset_frames', 16000, 'outside'),
    ('lead_s', float('nan'), 'timing'),
    ('crossfade_s', 0, 'timing'),
    ('recorded_to_midi', 64, 'preserve'),
    ('provenance', {}, 'provenance'),
])
def test_invalid_transition_contract_fails(transition_library, field, value, message):
    root, m = transition_library
    m['instruments']['viola']['recorded_transitions'][0][field]=value
    m=library.generate_manifest(root,name='transition_probe',instruments=m['instruments'])
    with pytest.raises(ValueError,match=message):
        asset_for(m).plan()


def test_ambiguous_interval_fails(transition_library):
    root,m=transition_library
    entries=m['instruments']['viola']['recorded_transitions']
    entries.append(dict(entries[0]))
    m=library.generate_manifest(root,name='transition_probe',instruments=m['instruments'])
    with pytest.raises(ValueError,match='ambiguous'):
        asset_for(m).plan()


def test_plan_rejects_transition_lead_before_preceding_note(transition_library):
    root,m=transition_library
    m['instruments']['viola']['recorded_transitions'][0]['lead_s']=.8
    m=library.generate_manifest(root,name='transition_probe',instruments=m['instruments'])
    with pytest.raises(ValueError,match='lead.*previous note'):
        asset_for(m).plan()


def test_dynamic_curve_and_stereo_transition_have_no_generated_glide(transition_library, monkeypatch):
    from audioforge import sampler
    root,m=transition_library
    t=np.arange(16000)/8000
    stereo=np.column_stack([.2*np.sin(2*np.pi*733*t), .1*np.sin(2*np.pi*977*t)])
    (root/'transition.wav').write_bytes(wav_bytes(stereo))
    m=library.generate_manifest(root,name='transition_probe',instruments=m['instruments'])
    a=asset_for(m)
    event=a.spec['layers'][0]['notes'][1]
    event['curves']=[dict(target='dynamic',time_basis='note_seconds',points=[[0,.4],[.5,.8]])]
    calls=[]
    real=sampler.render_region
    def traced(region,*args,**kwargs):
        if region.sample=='transition.wav':
            calls.append(dict(kwargs))
        return real(region,*args,**kwargs)
    monkeypatch.setattr(sampler,'render_region',traced)
    st,sr,_=a.render()
    assert calls and all(k.get('ramp_from_midi') is None for k in calls)
    assert st.ndim==2 and np.linalg.norm(st[:,0]-st[:,1])>1
