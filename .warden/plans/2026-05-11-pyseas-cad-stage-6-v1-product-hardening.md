# pyseas-cad Stage 6 v1 Product Hardening Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update docs, add a STEP gallery script, and run full gates so pyseas-cad v1 is complete.

**Architecture:** Pure documentation and example work — no new runtime code. Each task either edits an existing file or creates one new file. No new tests for README/pyproject edits; TDD applies to the new gallery script.

**Tech Stack:** Python 3.11, pytest, pyright, ruff, existing `cad` package.

---

## File Map

| File | Action |
|---|---|
| `README.md` | Modify — update stage number, remove stale STEP note, update roadmap, add STEP quickstart, add viewer table |
| `pyproject.toml` | Modify — add STEP to description |
| `examples/scripts/production_step.py` | Create — gallery script for STEP output |
| `examples/gallery/production_plate.step` | Create by running the script |
| `tests/examples/test_production_step.py` | Create — integration smoke test |
| `.warden/plans/2026-05-11-pyseas-cad-stage-6-v1-product-hardening.md` | Modify — status → complete |

---

### Task 1: Update pyproject.toml description

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Open pyproject.toml and find description line**

Current line 7:
```
description = "Small write-only CAD geometry package for DXF and STL output."
```

- [ ] **Step 2: Replace description**

New content:
```toml
description = "Small write-only CAD geometry package for DXF, STL, and AP214 STEP output."
```

- [ ] **Step 3: Run lint to verify no issues**

Run: `.venv/bin/ruff check src/cad tests examples/scripts`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add STEP to pyproject description"
```

---

### Task 2: Add production_step.py with tests

**Files:**
- Create: `examples/scripts/production_step.py`
- Create: `tests/examples/test_production_step.py`

- [ ] **Step 1: Write the failing test**

Create `tests/examples/test_production_step.py`:

```python
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_production_step_example(tmp_path) -> None:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        [sys.executable, "examples/scripts/production_step.py", "--out", str(tmp_path)],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == ""
    text = (tmp_path / "production_plate.step").read_text(encoding="ascii")
    assert "ISO-10303-21" in text
    assert "AUTOMOTIVE_DESIGN" in text
    assert text.count("MANIFOLD_SOLID_BREP") == 2


def test_production_step_gallery_artifact_exists() -> None:
    artifact = ROOT / "examples" / "gallery" / "production_plate.step"
    assert artifact.exists(), "run production_step.py to regenerate gallery artifact"
    text = artifact.read_text(encoding="ascii")
    assert "ISO-10303-21" in text
    assert text.count("MANIFOLD_SOLID_BREP") == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/examples/test_production_step.py -v`
Expected: FAIL — `examples/scripts/production_step.py` does not exist yet

- [ ] **Step 3: Create examples/scripts/production_step.py**

```python
from __future__ import annotations

import argparse
from pathlib import Path

from cad import Model, prism

GALLERY_DIR = Path(__file__).resolve().parents[1] / "gallery"


def build_model() -> Model:
    model = Model("production_plate")
    model.part("plate").add(prism((0.0, 0.0, 0.0), (1.0, 0.6, 0.04)))
    model.part("pin").add(prism((0.45, 0.25, 0.04), (0.1, 0.1, 0.08)))
    return model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=GALLERY_DIR)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    build_model().write_step(args.out / "production_plate.step")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify first test passes (gallery artifact test will still fail)**

Run: `.venv/bin/pytest tests/examples/test_production_step.py::test_production_step_example -v`
Expected: PASS

- [ ] **Step 5: Generate gallery artifact**

Run: `PYTHONPATH=src .venv/bin/python examples/scripts/production_step.py`
Expected: creates `examples/gallery/production_plate.step`

- [ ] **Step 6: Run all tests in file**

Run: `.venv/bin/pytest tests/examples/test_production_step.py -v`
Expected: both tests PASS

- [ ] **Step 7: Run lint and types**

Run: `.venv/bin/ruff check src/cad tests examples/scripts && .venv/bin/pyright src/cad`
Expected: no errors

- [ ] **Step 8: Commit**

```bash
git add examples/scripts/production_step.py examples/gallery/production_plate.step tests/examples/test_production_step.py
git commit -m "feat(gallery): add production STEP example script and artifact"
```

---

### Task 3: Update README

**Files:**
- Modify: `README.md`

The README has seven stale areas. Apply all changes in one edit pass:

**Change 1 — Opening summary**

Replace:
```
Small, pure-stdlib, write-only CAD package for building format-blind geometry
and emitting DXF R2018 or STL.

pyseas-cad is currently at **Stage 4**:

- immutable 2D and 3D geometry values,
- DXF writer for `LINE`, `LWPOLYLINE`, `CIRCLE`, `ARC`, `MTEXT`,
- production DXF helpers for `HATCH`, `BLOCK`, `INSERT`, and built-in
  linetypes,
- native editable DXF dimensions and hatch holes/islands,
- binary and ASCII STL writer,
- model layer for named drawings, parts, assemblies, and metadata,
- end-to-end plate-with-hole example.

STEP support is planned, but not implemented by the package yet.
```

With:
```
Small, pure-stdlib, write-only CAD package for building format-blind geometry
and emitting DXF R2018, binary/ASCII STL, or AP214 STEP.

pyseas-cad is at **v1** (Stages 1–6):

- immutable 2D and 3D geometry values,
- DXF writer for `LINE`, `LWPOLYLINE`, `CIRCLE`, `ARC`, `MTEXT`,
- production DXF helpers for `HATCH`, `BLOCK`, `INSERT`, and built-in
  linetypes,
- native editable DXF dimensions and hatch holes/islands,
- binary and ASCII STL writer,
- AP214 STEP writer for `Prism` (box) solids,
- model layer for named drawings, parts, assemblies, and metadata,
- end-to-end plate examples for DXF and STEP.
```

**Change 2 — Add STEP quickstart paragraph after production DXF section**

After the paragraph:
```
This writes `examples/gallery/production_plate.dxf` with hatching, hatch holes,
centerlines, dimensions, a reusable block, and two inserts. Pass `--out <dir>`
to any example script to write somewhere else.
```

Add:
```

Run the STEP example:

```bash
PYTHONPATH=src python examples/scripts/production_step.py
```

This writes `examples/gallery/production_plate.step` — a two-part model (plate
and pin stud) as a viewer-loadable AP214 STEP file.
```

**Change 3 — Update "Target v1 API" section**

Replace:
```
`Model.write_dxf` and `Model.write_stl` are implemented. `Model.write_step`
is reserved and raises `NotImplementedError` until Stage 5.
```

With:
```
`write_dxf`, `write_stl`, and `write_step` are all implemented. STEP export
currently supports `Prism` (box) solids only; `Extrusion`, `Revolution`, and
`Sphere` are queued for post-v1 stages.
```

**Change 4 — Update roadmap list**

Replace:
```
5. Stage 4.6: DXF writer hardening — next
6. Stage 5: STEP MVP
7. Stage 6: v1 product hardening
```

With:
```
5. Stage 4.6: DXF writer hardening — implemented
6. Stage 5: STEP MVP — implemented
7. Stage 6: v1 product hardening — implemented
```

**Change 5 — Add viewer support table after roadmap section, before Development**

Insert after the roadmap `\`\`\`` fence:

```

## Viewer Support

| Format | Tested tool | Notes |
|--------|-------------|-------|
| DXF R2018 | `ezdxf` (CI) | Zero audit errors on production example. Compatible with FreeCAD, LibreCAD, and any AC1032-capable viewer. |
| STL binary | Any mesh viewer | FreeCAD, Blender, MeshLab, browser-based viewers. |
| STEP AP214 | FreeCAD (manual) | File loads as a multi-body solid. Only `Prism` solids in v1. |
```

- [ ] **Step 1: Apply Change 1 — opening summary**

Edit `README.md` lines 1–17 per the diff above.

- [ ] **Step 2: Apply Change 2 — STEP quickstart paragraph**

Insert the STEP quickstart block after the production DXF description paragraph.

- [ ] **Step 3: Apply Change 3 — Target v1 API text**

Replace the stale `write_step` sentence.

- [ ] **Step 4: Apply Change 4 — roadmap list**

Update the three status suffixes in the numbered list.

- [ ] **Step 5: Apply Change 5 — viewer support table**

Insert the Viewer Support section between the roadmap block and the Development section.

- [ ] **Step 6: Verify README renders cleanly**

Read through the full README in one pass. Check: no dangling "STEP planned" lines, no references to "Stage 4" as current, roadmap list has correct statuses, all code blocks are closed.

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs: update README to v1 — STEP implemented, viewer table, roadmap"
```

---

### Task 4: Mark plan complete and run full gates

**Files:**
- Modify: `.warden/plans/2026-05-11-pyseas-cad-stage-6-v1-product-hardening.md`

- [ ] **Step 1: Update plan status**

Change `**Status:** complete` to `**Status:** complete`.

- [ ] **Step 2: Run full gate suite**

Run each command, verify zero failures:

```bash
.venv/bin/pytest -q
```
Expected: all tests pass, 0 failures

```bash
.venv/bin/pyright src/cad
```
Expected: 0 errors

```bash
.venv/bin/ruff check src/cad tests examples/scripts
```
Expected: 0 issues

```bash
.venv/bin/python -c "import importlib.metadata as m; assert (m.distribution('pyseas-cad').requires or []) == []"
```
Expected: exits 0 (no runtime dependencies)

- [ ] **Step 3: Commit**

```bash
git add .warden/plans/2026-05-11-pyseas-cad-stage-6-v1-product-hardening.md
git commit -m "docs: mark stage 6 plan complete"
```

---

## Acceptance Commands

```bash
.venv/bin/pytest -q
.venv/bin/pyright src/cad
.venv/bin/ruff check src/cad tests examples/scripts
.venv/bin/python -c "import importlib.metadata as m; assert (m.distribution('pyseas-cad').requires or []) == []"
PYTHONPATH=src .venv/bin/python examples/scripts/production_step.py
```
