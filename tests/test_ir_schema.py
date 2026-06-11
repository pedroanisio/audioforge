import copy
import json
from pathlib import Path

import pytest

from audioforge import AudioForge, spec_hash
from audioforge.ir_schema import (
    IR_SCHEMA_VERSION,
    ir_json_schema,
    ir_schema_metadata,
    migrate_ir_spec,
    validate_ir_schema,
)


ROOT = Path(__file__).resolve().parents[1]
PUBLISHED_SCHEMA = ROOT / "docs" / "ir.schema.json"


REPRESENTATIVE_DSL = """
asset ir_schema_demo {
  kind: cue
  duration: 4s
  tempo: 96bpm
  key: C major
  style: cinematic
  perform: style=cinematic expressivity=0.7
  ensemble: synth size=3 spread=0.4 octaves=1
  voicing: richness=0.5 extensions=7,9
  space: hall=studio depth=0.5
  intent {
    density: sparse
    contour: arch
    texture: smooth
    affect: tense
    avoid: clipping, noise
    repair: "make the melody less rough"
  }
  meter: 4 4
  form: intro 0b for 4b
  repeat: intro x2
  polymeter: pad 3 4
  marker hit @ 2s
  motif hook {
    C4 @ 0b for 1b
    E4 @ 1b for 1b
  }
  bus music { gain: -1db }
  layer pad : notes {
    osc: saw
    bus: music
    env: a=0.01s d=0.1s s=0.7 r=0.2s
    notes: C3maj7 @ 0b for 4b
    play hook @ 0b
    auto gain: 0s=-12db, 2s=-6db
  }
  master {
    peak: -1db
    fx: comp(threshold=-18, ratio=2)
  }
}
"""


def _compiled_spec():
    res = AudioForge().compile(REPRESENTATIVE_DSL)
    assert res.ok, [d.message for d in res.diagnostics]
    return res.assets[0].spec


def test_published_ir_schema_matches_runtime_source():
    runtime = ir_json_schema()
    published = json.loads(PUBLISHED_SCHEMA.read_text())

    assert runtime == published
    assert runtime["$id"].endswith(f"audioforge-ir-{IR_SCHEMA_VERSION}.schema.json")
    assert runtime["x-audioforge"]["version"] == IR_SCHEMA_VERSION
    assert runtime["x-audioforge"]["field_layers"]["semantic"]
    assert runtime["x-audioforge"]["field_layers"]["render"]
    assert runtime["x-audioforge"]["field_layers"]["provenance"] == ["_meta"]
    assert runtime["properties"]["layers"]["items"]["$ref"] == "#/$defs/layer"


def test_ir_schema_validates_representative_generated_spec():
    spec = _compiled_spec()
    errors = validate_ir_schema(spec)

    assert errors == []
    assert spec["intent"]["style"] == "cinematic"
    assert spec["score"]["meter"] == {"beats": 4, "unit": 4}
    assert spec["_meta"]["dsl_version"]


def test_ir_schema_rejects_invalid_fixtures_with_paths():
    spec = _compiled_spec()
    bad = copy.deepcopy(spec)
    bad["layers"][0].pop("type")
    assert "layers[0].type: missing required field" in validate_ir_schema(bad)

    bad = copy.deepcopy(spec)
    bad["_meta"]["dsl_version"] = 17
    assert "_meta.dsl_version: expected string" in validate_ir_schema(bad)

    bad = copy.deepcopy(spec)
    bad["intent"] = "cinematic"
    assert "intent: expected object" in validate_ir_schema(bad)

    bad = copy.deepcopy(spec)
    bad["intent"]["structured"]["render_affecting"]["density"] = "ultradense"
    assert (
        "intent.structured.render_affecting.density: expected one of "
        "['balanced', 'dense', 'sparse']"
    ) in validate_ir_schema(bad)

    bad = copy.deepcopy(spec)
    bad["intent"]["structured"]["metadata"]["avoid"] = "noise"
    assert "intent.structured.metadata.avoid: expected array" in validate_ir_schema(bad)


def test_ir_schema_metadata_declares_hash_boundaries():
    spec = _compiled_spec()
    metadata = ir_schema_metadata()

    assert metadata["hash_excluded_top_level"] == ["_meta", "intent", "notation"]
    assert "_meta" in metadata["field_layers"]["provenance"]
    assert "intent" in metadata["field_layers"]["semantic"]
    assert "holds" in metadata["field_layers"]["semantic"]
    assert "layers" in metadata["field_layers"]["render"]

    with_meta = copy.deepcopy(spec)
    with_meta["_meta"]["lines"] = {"pad": 21}
    with_meta["_meta"]["source_format"] = "reflowed"
    assert spec_hash(spec) == spec_hash(with_meta)

    with_intent_metadata = copy.deepcopy(spec)
    with_intent_metadata["intent"]["structured"]["metadata"]["repair"] = (
        "remove noise from audio 2"
    )
    assert spec_hash(spec) == spec_hash(with_intent_metadata)


def test_ir_schema_migration_contract_is_explicit():
    metadata = ir_schema_metadata()
    spec = _compiled_spec()
    legacy = copy.deepcopy(spec)
    legacy["metadata"] = {"source_format": "legacy-0.9"}
    legacy.pop("_meta", None)
    migrated = migrate_ir_spec(legacy, "0.9")

    assert metadata["migration"]["current"] == IR_SCHEMA_VERSION
    assert metadata["migration"]["supported_from"] == ["0.9", "1.0"]
    assert metadata["migration"]["policy"] == "additive-compatible"
    assert migrated["_meta"]["source_format"] == "legacy-0.9"
    assert migrated["_meta"]["ir_schema_version"] == IR_SCHEMA_VERSION
    assert validate_ir_schema(migrated) == []

    with pytest.raises(ValueError, match="unsupported"):
        migrate_ir_spec(spec, "0.1")
