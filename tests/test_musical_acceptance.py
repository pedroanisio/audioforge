"""The review bundle contains measured passes, auditable audio, and no fake ratings."""
import hashlib
import json

from audioforge.tools.musical_acceptance import generate


def test_acceptance_bundle_renders_every_case_and_embeds_auditable_audio(tmp_path):
    report = generate(tmp_path)
    assert report["passed"] is True
    assert report["listening_status"] == "not_reviewed"
    assert {case["id"] for case in report["cases"]} == {
        "seventh", "phrase", "repeat", "release", "quiet", "alias", "sample_gain"}
    page = (tmp_path / "index.html").read_text()
    assert page.count('src="data:audio/wav;base64,') == 7
    assert "Not reviewed" in page and "Download listening notes" in page
    for case in report["cases"]:
        current = case["revisions"]["current"]
        assert current["passed"]
        assert hashlib.sha256((tmp_path / current["file"]).read_bytes()).hexdigest() == current["output_sha256"]
    assert json.loads((tmp_path / "manifest.json").read_text()) == report
