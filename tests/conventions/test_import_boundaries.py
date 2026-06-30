from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "cady"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            names.update(alias.name for alias in statement.names)
        elif isinstance(statement, ast.ImportFrom) and statement.module:
            names.add(statement.module)
    return names


def _python_files(package: str) -> list[Path]:
    root = SRC / package
    if not root.exists():
        return []
    return sorted(root.rglob("*.py"))


def test_legacy_domain_and_build_packages_are_removed() -> None:
    assert not (SRC / "domain").exists()
    assert not (SRC / "build").exists()
    assert not (SRC / "factories").exists()
    assert not (SRC / "numeric").exists()
    assert not (SRC / "algorithms").exists()
    assert not (SRC / "visualisation").exists()


def test_new_value_packages_do_not_import_legacy_domain() -> None:
    packages = ("geometry", "drawing", "product", "view")
    offenders = [
        f"{path.relative_to(ROOT)} imports {name}"
        for package in packages
        for path in _python_files(package)
        for name in _imports(path)
        if name.startswith("cady.domain")
    ]
    assert offenders == []


def test_operations_do_not_import_domain_or_application_packages() -> None:
    forbidden = (
        "cady.domain",
        "cady.drawing",
        "cady.product",
        "cady.view",
        "cady.files",
    )
    offenders = [
        f"{path.relative_to(ROOT)} imports {name}"
        for path in _python_files("operations")
        for name in _imports(path)
        if name.startswith(forbidden)
    ]
    assert offenders == []


def test_files_do_not_import_viewer_or_numpy_at_module_scope() -> None:
    offenders = [
        f"{path.relative_to(ROOT)} imports {name}"
        for path in _python_files("files")
        for name in _imports(path)
        if name == "numpy"
        or name.startswith("cady.view.mesh_buffers")
        or name.startswith("cady.view.vispy_viewer")
    ]
    assert offenders == []


def test_export_code_does_not_hide_discretization_constants() -> None:
    checked = [
        SRC / "files" / "dxf.py",
        SRC / "files" / "stl.py",
        SRC / "files" / "step.py",
    ]
    offenders: list[str] = []
    for path in checked:
        text = path.read_text(encoding="utf-8")
        if "tolerance=1e-2" in text:
            offenders.append(f"{path.relative_to(ROOT)} hard-codes tolerance=1e-2")
        if "tolerance=1e-3" in text and "def " not in text:
            offenders.append(f"{path.relative_to(ROOT)} may hard-code tolerance=1e-3")
    assert offenders == []
