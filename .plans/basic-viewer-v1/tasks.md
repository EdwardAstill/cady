# Tasks

1. Add regression coverage for polygon-hole caps and the simplified viewer
   defaults/batches.
   - Verify: `.venv/bin/pytest -q tests/geometry/test_body3.py tests/view`
2. Restore hole-aware cap triangulation at the mesh construction boundary.
   - Verify: `.venv/bin/pytest -q tests/geometry/test_body3.py tests/geometry/test_regions2.py`
3. Simplify default overlays, lighting, edge batches, canvas background, and
   camera orbit target while preserving public values.
   - Verify: `.venv/bin/pytest -q tests/view`
4. Update viewer documentation and remove stale backend descriptions.
   - Verify: `rg -n "default.*overlay|orientation edge|white" src/cady/view/README.md notes/viewing.md README.md`
5. Run the native framebuffer smoke, focused/convention tests, and full gates.
   - Verify: `.venv/bin/pytest -q && .venv/bin/pyright src/cady && .venv/bin/ruff check src/cady tests && git diff --check`
