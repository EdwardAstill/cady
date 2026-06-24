from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, is_dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "cady"


def _imports(path: Path) -> set[str]:
    """Return module-level import names from a Python file.

    Only top-level imports are collected — imports inside function bodies
    (lazy imports) are excluded.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            names.update(alias.name for alias in statement.names)
        elif isinstance(statement, ast.ImportFrom) and statement.module:
            names.add(statement.module)
    return names


def _python_files(package: str) -> list[Path]:
    return sorted((SRC / package).rglob("*.py"))


def test_domain_does_not_import_visualisation_or_numpy_at_module_scope() -> None:
    offenders = [
        f"{path.relative_to(ROOT)} imports {name}"
        for path in _python_files("domain")
        for name in _imports(path)
        if name == "numpy"
        or name.startswith("cady.plotting")
        or name.startswith("cady.visualisation")
    ]
    assert offenders == []


def test_numeric_does_not_import_domain() -> None:
    offenders = [
        f"{path.relative_to(ROOT)} imports {name}"
        for path in _python_files("numeric")
        for name in _imports(path)
        if name.startswith("cady.domain")
    ]
    assert offenders == []


def test_files_do_not_import_visualisation_or_numpy_at_module_scope() -> None:
    offenders = [
        f"{path.relative_to(ROOT)} imports {name}"
        for path in _python_files("files")
        for name in _imports(path)
        if name == "numpy"
        or name.startswith("cady.plotting")
        or name.startswith("cady.visualisation")
    ]
    assert offenders == []


def test_new_ops_modules_do_not_import_domain() -> None:
    legacy_compat = {
        SRC / "ops" / "profiles.py",
        SRC / "ops" / "tessellate.py",
        SRC / "ops" / "transforms.py",
    }
    offenders = [
        f"{path.relative_to(ROOT)} imports {name}"
        for path in _python_files("ops")
        if path not in legacy_compat
        for name in _imports(path)
        if name.startswith("cady.domain")
    ]
    assert offenders == []


def test_drawing_value_records_are_frozen_and_builders_are_mutable() -> None:
    from cady.domain.drawing import (
        DimensionEntity,
        DxfDrawing,
        HatchEntity,
        InsertEntity,
        Layer,
        TextEntity,
    )
    from cady.domain.shapes2d import Rectangle
    from cady.domain.vec import Vec2

    value_records = (
        TextEntity("label", Vec2(0, 0), 0.1, "0"),
        DimensionEntity("aligned", Vec2(0, 0), Vec2(1, 0), 0.2, "DIM", "1", 0.1),
        HatchEntity(Rectangle(Vec2(0, 0), Vec2(1, 1)), "0"),
        InsertEntity("BLOCK", Vec2(0, 0)),
    )
    for record in value_records:
        assert is_dataclass(record)
        with pytest.raises(FrozenInstanceError):
            record.layer = "changed"  # type: ignore[misc]

    drawing = DxfDrawing()
    assert drawing.layer("0").add(Rectangle(Vec2(0, 0), Vec2(1, 1))) is drawing.layers["0"]

    layer = Layer("mutable")
    layer.color = 3
    assert layer.color == 3


def test_export_and_bounds_code_do_not_hide_discretisation_constants() -> None:
    checked = [
        SRC / "domain" / "shapes3d.py",
        *(SRC / "files" / "dxf").glob("*.py"),
    ]
    offenders: list[str] = []
    for path in checked:
        text = path.read_text(encoding="utf-8")
        if "tolerance=1e-2" in text:
            offenders.append(f"{path.relative_to(ROOT)} hard-codes tolerance=1e-2")
        if "curves_to_polyline(boundary, tolerance=1e-3)" in text:
            offenders.append(f"{path.relative_to(ROOT)} hard-codes DXF boundary flattening")
        if "curves_to_polyline(shape, tolerance=1e-3)" in text:
            offenders.append(f"{path.relative_to(ROOT)} hard-codes DXF shape flattening")
    assert offenders == []
