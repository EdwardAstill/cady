# 3D DXF Import Tasks

## 1. Add Domain Faceted Geometry Types

Files:

- `src/cady/domain/mesh.py`
- `src/cady/domain/__init__.py`
- `src/cady/__init__.py`
- `tests/domain/test_faceted_mesh.py`

Work:

- Add `Face3D`.
- Add `Polyline3D`.
- Add `FacetedMesh`.
- Implement bounds and `to_array(tolerance=...)` conversions.
- Export public names from `cady.domain` and top-level `cady`.

Verification:

```bash
.venv/bin/pytest -q tests/domain/test_faceted_mesh.py tests/domain/test_to_array_3d.py
.venv/bin/pyright src/cady
.venv/bin/ruff check src/cady/domain tests/domain/test_faceted_mesh.py
```

## 2. Extend DXF Reader Internals for 3D Entity Parsing

Files:

- `src/cady/files/dxf/reader.py`
- `tests/files/test_dxf_3d_files.py`

Work:

- Reuse existing pair/chunk parsing.
- Add helpers for `Vec3` values using group codes:
  - point 1: `10`, `20`, `30`;
  - point 2: `11`, `21`, `31`;
  - point 3: `12`, `22`, `32`;
  - point 4: `13`, `23`, `33`.
- Add unit tests for direct `3DFACE` parsing.

Verification:

```bash
.venv/bin/pytest -q tests/files/test_dxf_3d_files.py tests/files/test_dxf_files.py
```

## 3. Add `read_3d(...)` Result API

Files:

- `src/cady/files/dxf/reader.py`
- `src/cady/files/dxf/__init__.py`
- `tests/files/test_dxf_3d_files.py`

Work:

- Add `DxfSkippedEntity`.
- Add `Dxf3DImportResult`.
- Add `read_3d(path)` and `parse_dxf_3d(text)`.
- Import `3DFACE` entities into `FacetedMesh`.
- Record unsupported entities such as `3DSOLID`, `BODY`, `REGION`, and
  `SURFACE` as skipped.

Verification:

```bash
.venv/bin/pytest -q tests/files/test_dxf_3d_files.py tests/test_smoke_import.py
```

## 4. Add `read_mesh(...)` Convenience API

Files:

- `src/cady/files/dxf/reader.py`
- `src/cady/files/dxf/__init__.py`
- `tests/files/test_dxf_3d_files.py`

Work:

- Add `read_mesh(path)`.
- Merge imported `FacetedMesh` values into one mesh result.
- Raise `ReadError` when there is no supported mesh geometry.
- Decide return type before implementation:
  - preferred: `FacetedMesh` if domain mesh object is accepted;
  - alternative: `ArrayMesh3` if callers mainly need immediate mesh numerics.

Verification:

```bash
.venv/bin/pytest -q tests/files/test_dxf_3d_files.py tests/files/test_stl_files.py
```

## 5. Support Polyface Mesh DXF

Files:

- `src/cady/files/dxf/reader.py`
- `tests/files/test_dxf_3d_polyface.py`

Work:

- Parse `POLYLINE`/`VERTEX`/`SEQEND` sequences.
- Distinguish polyface meshes from ordinary 3D polylines using DXF flags.
- Build `FacetedMesh` from vertex records and face-index records.
- Preserve unsupported/ambiguous polyline variants as skipped entries.

Verification:

```bash
.venv/bin/pytest -q tests/files/test_dxf_3d_polyface.py tests/files/test_dxf_3d_files.py
```

## 6. Support 3D Wire Polylines

Files:

- `src/cady/files/dxf/reader.py`
- `tests/files/test_dxf_3d_polylines.py`

Work:

- Import non-polyface 3D `POLYLINE`/`VERTEX` sequences into `Polyline3D`.
- Preserve closed flag where present.
- Expose wires via `Dxf3DImportResult.wires`.

Verification:

```bash
.venv/bin/pytest -q tests/files/test_dxf_3d_polylines.py
```

## 7. Document Support Boundaries

Files:

- `README.md`
- `docs/files/dxf-format-cheatsheet.md`
- optionally `docs/objects/domain-objects.md`

Work:

- Document `dxf.read_3d` and `dxf.read_mesh`.
- List supported entities.
- State explicitly that ACIS-backed `3DSOLID`, `BODY`, `REGION`, and `SURFACE`
  are reported/skipped, not imported.

Verification:

```bash
rg -n "read_3d|read_mesh|3DFACE|3DSOLID" README.md docs
```

## 8. Full Regression

Run:

```bash
.venv/bin/pytest -q
.venv/bin/pyright src/cady
.venv/bin/ruff check src/cady tests README.md
git diff --check
```

