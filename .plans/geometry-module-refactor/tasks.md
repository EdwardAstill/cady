# Geometry Module Refactor Tasks

1. [x] Record a clean baseline with focused geometry and operations tests.
2. [x] Add `geometry/curve.py`, move the protocols, and extract suitable polyline
   algorithms into `operations/polylines.py`.
3. [x] Extract spline evaluation into `operations/curve_sampling.py` and keep
   `Spline2`/`Spline3` as thin semantic values.
4. [x] Extract mesh algorithms into focused `operations/mesh/` modules without
   growing the existing topology hotspot.
5. [x] Integrate imports and exports, review dependency direction, and remove dead
   private helpers.
6. [x] Run focused tests, convention tests, full pytest, Pyright, Ruff, and
   `git diff --check`.
7. [x] Remove `geometry/_coordinates.py`, moving coordinate validation to
   `cady.utils` and point/vector coercion to their owning geometry modules.

## Verification

- `.venv/bin/pytest -q`: 436 passed
- `.venv/bin/pyright src/cady`: 0 errors
- `.venv/bin/ruff check src/cady tests`: passed
- `git diff --check`: passed
