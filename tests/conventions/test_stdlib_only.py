from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "cady"
RUNTIME_ALLOWED = {"cady", "numpy", "steputils"}
OPTIONAL_BY_PACKAGE = {
    "plotting": {"matplotlib", "mpl_toolkits"},
    "visualisation": {"matplotlib", "mpl_toolkits", "vispy"},
}
STDLIB = set(sys.stdlib_module_names)


def test_runtime_imports_use_declared_allowlist() -> None:
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        package = path.relative_to(SRC).parts[0]
        allowed = set(RUNTIME_ALLOWED)
        allowed.update(OPTIONAL_BY_PACKAGE.get(package, set()))
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            else:
                continue
            for name in names:
                if name not in STDLIB and name not in allowed and name != "__future__":
                    offenders.append(f"{path.relative_to(ROOT)} imports {name}")
    assert offenders == []
