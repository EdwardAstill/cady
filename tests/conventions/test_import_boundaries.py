from __future__ import annotations

import ast
from pathlib import Path

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
        if name == "numpy" or name.startswith("cady.visualisation")
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
        if name == "numpy" or name.startswith("cady.visualisation")
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
