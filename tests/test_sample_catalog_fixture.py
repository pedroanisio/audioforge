from pathlib import Path

from audioforge.catalog import Catalog
from audioforge.library import add_library_path, load_library
from audioforge.sample_catalog.manifest import audit_catalog

ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "fixtures" / "sample_catalog" / "tiny_approved"


def test_tiny_approved_sample_catalog_fixture_is_renderable_and_strict_loadable():
    audit = audit_catalog(FIXTURE, require_approved=True)
    assert audit["ok"] is True
    assert audit["catalog_state"] == "approved"

    cat = Catalog.build(FIXTURE)
    assert len(cat.renderable()) == 1
    assert cat.renderable()[0].id == "instrument"

    manifest = (FIXTURE / "library.manifest.json")
    import json
    data = json.loads(manifest.read_text())
    add_library_path(FIXTURE.parent)
    lib = load_library({
        "name": data["name"],
        "manifest_sha256": data["manifest_sha256"],
    }, require_approved=True)
    regions = lib.regions("tiny_sine")
    assert len(regions) == 1
    assert regions[0].sample == "samples/C4.wav"
    audio, sr = lib.audio("samples/C4.wav")
    assert sr == 44100
    assert audio.size > 0
