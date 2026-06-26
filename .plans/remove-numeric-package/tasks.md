# Remove Numeric Package Tasks

## 1. Baseline

Run numeric-package, geometry, operations, product, view, and smoke tests before moving
files.

Verification:

```bash
.venv/bin/pytest -q tests/operations tests/geometry2d tests/geometry3d tests/product tests/view tests/test_smoke_import.py
```

## 2. Move Modules

- Move `numeric/types.py` to `operations/types.py`.
- Move `numeric/validation.py` to `operations/validation.py`.
- Move `numeric/bounds.py` to `operations/bounds.py`.
- Move `numeric/paths2d.py` and `numeric/curves2d.py` into
  `operations/arrays2d.py`.
- Move `numeric/mesh3d.py` to `operations/arrays3d.py`.
- Merge `numeric/transform.py` into `operations/transforms.py`.

Verification:

```bash
rg -n "cady\\.numeric|from cady\\.numeric|import cady\\.numeric" src/cady tests
```

## 3. Delete Numeric

- Delete `src/cady/numeric`.
- Rename/update tests that targeted the old package path.
- Update docs and plans that refer to the old package path.

Verification:

```bash
test ! -e src/cady/numeric
rg -n "cady\\.numeric|from cady\\.numeric|import cady\\.numeric" src/cady tests docs .plans README.md new-api.md
```

## 4. Final Gates

Run full test and static checks.

Verification:

```bash
.venv/bin/pytest -q
.venv/bin/pyright src/cady
.venv/bin/ruff check src/cady tests
git diff --check
```
