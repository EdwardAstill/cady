from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "cady"
ALLOWED = {"cady", "steputils"}
STDLIB = set(sys.stdlib_module_names)


def test_runtime_imports_are_stdlib_only() -> None:
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        if "_vendor" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            else:
                continue
            for name in names:
                if name not in STDLIB and name not in ALLOWED and name != "__future__":
                    offenders.append(f"{path.relative_to(ROOT)} imports {name}")
    assert offenders == []
