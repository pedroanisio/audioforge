from audioforge.sample_catalog.licenses import (
    LICENSE_EVIDENCE_SCHEMA,
    decide_license,
    evidence_hash,
    make_evidence,
)


def test_license_policy_accepts_cc0_and_requires_evidence_for_public_domain():
    cc0 = decide_license(
        license_name="Creative Commons 0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        source_url="https://example.test/sound/1",
        source_id="1",
    )
    assert cc0.accepted
    assert cc0.license_id == "CC0-1.0"

    pdm_missing_source = decide_license(
        license_name="Public Domain Mark",
        license_url="https://creativecommons.org/public-domain/pdm/",
    )
    assert not pdm_missing_source.accepted
    assert "public_domain_requires_stable_source_evidence" in pdm_missing_source.reasons

    pdm = decide_license(
        license_name="Public Domain Mark",
        license_url="https://creativecommons.org/public-domain/pdm/",
        source_url="https://example.test/item/2",
        source_id="2",
    )
    assert pdm.accepted
    assert pdm.license_id == "PDM"


def test_license_policy_quarantines_attribution_nc_and_unclear_rights():
    for name in ["CC-BY", "CC-BY-SA", "CC-BY-NC", "free download", ""]:
        decision = decide_license(
            license_name=name,
            license_url="https://example.test/license",
            source_url="https://example.test/sound",
            source_id="sound",
        )
        assert not decision.accepted, name


def test_public_domain_license_quarantines_contradictory_rights_text():
    decision = decide_license(
        license_name="Public domain",
        rights_text="Copyright 2024 Example Studio. All rights reserved.",
        source_url="https://example.test/sound",
        source_id="sound",
    )

    assert not decision.accepted
    assert "public_domain_contradictory_rights" in decision.reasons


def test_cc0_license_quarantines_contradictory_rights_text():
    decision = decide_license(
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        rights_text="Copyright 2024 Example Studio. All rights reserved.",
        source_url="https://example.test/sound",
        source_id="sound",
    )

    assert not decision.accepted
    assert decision.license_id == "CC0-1.0"
    assert "license_contradictory_rights" in decision.reasons


def test_license_evidence_hash_is_stable_and_excludes_hash_field():
    ev = make_evidence(
        source="freesound",
        source_id="123",
        source_url="https://freesound.org/s/123/",
        download_url="https://freesound.org/apiv2/sounds/123/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        creator="tester",
        fetched_at="2026-06-12T00:00:00+00:00",
    )
    data = ev.to_dict()
    assert data["evidence_hash"] == evidence_hash(data)
    data["evidence_hash"] = "x" * 64
    assert ev.evidence_hash == evidence_hash(data)


def test_license_evidence_records_carry_schema_in_hash():
    ev = make_evidence(
        source="freesound",
        source_id="123",
        source_url="https://freesound.org/s/123/",
        download_url="https://freesound.org/apiv2/sounds/123/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    )

    data = ev.to_dict()
    assert data["schema"] == LICENSE_EVIDENCE_SCHEMA
    changed = dict(data, schema="audioforge.sample-catalog.evidence/0")
    assert evidence_hash(changed) != data["evidence_hash"]
