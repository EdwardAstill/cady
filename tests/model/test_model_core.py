from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cady import Assembly, Drawing2D, Model, ModelMetadata, Part


def test_model_imports_from_top_level() -> None:
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    assert model.name == "demo"
    assert isinstance(model.metadata, ModelMetadata)


def test_model_rejects_invalid_metadata() -> None:
    with pytest.raises(ValueError, match="model name"):
        Model("")
    with pytest.raises(ValueError, match="units"):
        Model("demo", units="mm")
    with pytest.raises(ValueError, match="timezone"):
        Model("demo", created_at=datetime(2026, 5, 8))


def test_model_normalizes_created_at() -> None:
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    assert model.metadata.created_at == datetime(2026, 5, 8, tzinfo=UTC)


def test_named_containers_are_reused() -> None:
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    assert isinstance(model.drawing("front"), Drawing2D)
    assert model.drawing("front") is model.drawing("front")
    assert isinstance(model.part("plate"), Part)
    assert model.part("plate") is model.part("plate")
    assert isinstance(model.assembly("assy"), Assembly)
    assert model.assembly("assy") is model.assembly("assy")


def test_model_to_dict_is_debug_shape_only() -> None:
    model = Model(
        "demo",
        author="Edward",
        source="unit-test",
        created_at="2026-05-08T00:00:00Z",
    )
    model.drawing("front")
    model.part("plate")
    model.assembly("assy").add("plate")

    data = model.to_dict()

    assert data["name"] == "demo"
    assert data["metadata"] == {
        "units": "m",
        "author": "Edward",
        "source": "unit-test",
        "created_at": "2026-05-08T00:00:00+00:00",
    }
    assert data["drawings"] == [{"name": "front", "layers": []}]
    assert data["parts"] == [{"name": "plate", "solids": 0}]
    assert data["assemblies"] == [{"name": "assy", "parts": ["plate"]}]


def test_assembly_accepts_parts_and_part_names() -> None:
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    plate = model.part("plate")
    assy = model.assembly("assy")

    assert assy.add(plate, "future_part", "plate") is assy
    assert model.to_dict()["assemblies"] == [
        {"name": "assy", "parts": ["plate", "future_part"]}
    ]


def test_assembly_rejects_empty_part_reference() -> None:
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    with pytest.raises(ValueError, match="part reference"):
        model.assembly("assy").add("")
