"""The examples catalog accounts for scores and survives a source-only checkout."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "docs" / "examples"


def catalog():
    return json.loads((EXAMPLES / "catalog.json").read_text())["examples"]


def test_catalog_accounts_for_every_score_once():
    entries = catalog()
    sources = [item["source"] for item in entries]
    assert len(entries) >= 35
    assert len({item["id"] for item in entries}) == len(entries)
    assert len(sources) == len(set(sources))
    assert set(sources) == {str(p.relative_to(ROOT)) for p in EXAMPLES.rglob("*.af")}
    moved = json.loads((EXAMPLES / "migration.json").read_text())["files"]
    assert {item["new"] for item in moved if item["old"].endswith(".af")} <= set(sources)
    for item in entries:
        path = ROOT / item["source"]
        assert path.is_relative_to(EXAMPLES)
        assert (path.parent / "index.md").is_file()
        assert not (ROOT / item["legacy_source"]).exists()


def test_archived_scores_keep_their_recorded_compile_status():
    from audioforge import AudioForge

    forge = AudioForge()
    for item in catalog():
        result = forge.compile((ROOT / item["source"]).read_text())
        assert result.ok == item["compiles"], (item["id"], result.diagnostics)


def test_quickstart_is_a_small_self_contained_example():
    from audioforge import AudioForge

    item = next(item for item in catalog() if item["id"] == "transition-sweep")
    asset = AudioForge().compile((ROOT / item["source"]).read_text()).assets[0]
    assert not asset.validate()
    assert asset.spec["duration_s"] <= 5
    assert "library" not in asset.spec


def test_migration_inventory_is_complete_and_preserves_audio():
    moved = json.loads((EXAMPLES / "migration.json").read_text())["files"]
    assert len({item["old"] for item in moved}) == len(moved)
    assert len({item["new"] for item in moved}) == len(moved)
    for item in moved:
        assert not (ROOT / item["old"]).is_file(), item["old"]
        if item["new"].endswith((".wav", ".mp3")):
            assert item["before_sha256"] == item["after_sha256"]


def test_example_links_resolve_without_optional_audio():
    import re

    pages = list(EXAMPLES.rglob("index.md"))
    assert pages
    for page in pages:
        for target in re.findall(r"\]\(([^)]+)\)", page.read_text()):
            if "://" in target or target.startswith("#"):
                continue
            assert (page.parent / target.split("#")[0]).exists(), (page, target)


def test_gallery_has_no_remote_dependencies():
    template = (ROOT / "scripts" / "examples_gallery.html").read_text()
    assert '<audio' in template
    assert 'preload="none"' in template
    assert '<script src=' not in template
    assert 'https://' not in template


def test_new_render_takes_priority_over_stale_mp3_preview(tmp_path, monkeypatch):
    import os
    from scripts import examples

    source = tmp_path / "score.af"
    output = tmp_path / "audio/current"
    output.mkdir(parents=True)
    wav, mp3 = output / "score.wav", output / "score.mp3"
    wav.write_bytes(b"fresh render")
    mp3.write_bytes(b"older preview")
    os.utime(mp3, ns=(1_000_000_000, 1_000_000_000))
    os.utime(wav, ns=(2_000_000_000, 2_000_000_000))
    monkeypatch.setattr(examples, "ROOT", tmp_path)
    assert examples.audio_files({"source": source.name}) == [wav]
    os.utime(mp3, ns=(3_000_000_000, 3_000_000_000))
    assert examples.audio_files({"source": source.name}) == [mp3]


def test_documentation_drift_is_part_of_the_test_gate():
    from scripts import examples

    for path, content in examples.documents(catalog()):
        assert path.read_text() == content, f"Regenerate example docs: {path}"


def test_render_records_failures_and_continues_without_overwriting_history(tmp_path, monkeypatch):
    from scripts import examples

    base = tmp_path / "docs/examples"
    base.mkdir(parents=True)
    good = base / "good.af"
    source = next(item for item in catalog() if item["id"] == "transition-sweep")
    good.write_text((ROOT / source["source"]).read_text())
    bad = base / "bad.af"
    bad.write_text("this is not an AudioForge score")
    history = base / "audio/transition_sweep.wav"
    history.parent.mkdir()
    history.write_bytes(b"preserved historical artifact")
    monkeypatch.setattr(examples, "ROOT", tmp_path)
    monkeypatch.setattr(examples, "BASE", base)
    # Subprocesses need the real engine even when the example root is isolated.
    monkeypatch.setenv("PYTHONPATH", str(ROOT))
    results = examples.render_examples([
        {"id": "bad", "source": str(bad.relative_to(tmp_path))},
        {"id": "good", "source": str(good.relative_to(tmp_path))},
    ])
    assert [row["status"] for row in results] == ["failed", "rendered"]
    assert history.read_bytes() == b"preserved historical artifact"
    assert (base / "audio/current/transition_sweep.wav").is_file()
    assert json.loads((base / "render-report.json").read_text())["results"] == results


def test_gallery_works_in_source_only_checkout(tmp_path, monkeypatch):
    from scripts import examples

    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/examples_gallery.html").write_text(
        (ROOT / "scripts/examples_gallery.html").read_text())
    base = tmp_path / "docs/examples"
    base.mkdir(parents=True)
    item = dict(catalog()[0], source="docs/examples/score.af")
    (base / "score.af").write_text("# </script> source text must stay inert\n")
    monkeypatch.setattr(examples, "ROOT", tmp_path)
    monkeypatch.setattr(examples, "BASE", base)
    page = examples.gallery([item]).read_text()
    assert '"audio": []' in page
    assert "# </script>" not in page
    assert "\\u003c/script>" in page
