# 3D DXF Import File Plan

## New Files

### `tests/domain/test_faceted_mesh.py`

Purpose: domain-level tests for `Face3D`, `Polyline3D`, and `FacetedMesh`.

Coverage:

- validation failures;
- bounds;
- `to_array(tolerance=...)`;
- quad face triangulation if `Face3D` supports more than 3 vertices.

### `tests/files/test_dxf_3d_files.py`

Purpose: first DXF 3D reader tests.

Coverage:

- one `3DFACE` triangle;
- one `3DFACE` quad;
- triangle encoded with repeated 3rd/4th vertex;
- skipped `3DSOLID`;
- `read_mesh(...)` no-supported-geometry error.

### `tests/files/test_dxf_3d_polyface.py`

Purpose: polyface mesh fixtures once `POLYLINE`/`VERTEX` parsing is added.

Coverage:

- simple tetrahedron or box polyface;
- invalid face index handling;
- mixed supported and skipped polyline variants.

### `tests/files/test_dxf_3d_polylines.py`

Purpose: 3D wire import tests once `Polyline3D` reading is added.

Coverage:

- open 3D polyline;
- closed 3D polyline;
- mixed wire plus mesh import result.

## Existing Files To Touch

### `src/cady/domain/mesh.py`

Add domain/import-side faceted geometry:

- `Face3D`;
- `Polyline3D`;
- `FacetedMesh`.

Keep NumPy imports lazy by constructing `ArrayMesh3` and `ArrayPolyline3`
inside `to_array(...)`.

### `src/cady/domain/__init__.py`

Re-export:

- `Face3D`;
- `Polyline3D`;
- `FacetedMesh`.

### `src/cady/__init__.py`

Re-export public domain mesh types if they are intended as user-authorable
objects, not just internal file-reader details.

### `src/cady/files/dxf/reader.py`

Extend the existing ASCII DXF reader:

- keep 2D `read_drawing(...)` behavior stable;
- add 3D result dataclasses;
- add `read_3d(...)`, `parse_dxf_3d(...)`, and `read_mesh(...)`;
- parse `3DFACE` first;
- later parse `POLYLINE`/`VERTEX`/`SEQEND`.

If this module becomes too large, split into:

- `src/cady/files/dxf/pairs.py` for group-code parsing;
- `src/cady/files/dxf/reader2d.py`;
- `src/cady/files/dxf/reader3d.py`.

Do this split only when the file actually becomes hard to navigate.

### `src/cady/files/dxf/__init__.py`

Export:

- `read_3d`;
- `parse_dxf_3d`;
- `read_mesh`;
- result dataclasses if public.

### `src/cady/errors.py`

No new error class should be required if `ReadError` already exists. Use
`ReadError` for malformed DXF and no-supported-geometry errors.

### `src/cady/domain/model.py`

Only touch this if `FacetedMesh` becomes a `Shape3D` and should be accepted by
`Part.add(...)` and `Model.write_stl(...)`. If `FacetedMesh` remains a separate
domain mesh object, leave `Model` unchanged.

### `src/cady/domain/base.py`

Only touch if `FacetedMesh` becomes a `Shape3D`. Avoid widening `Shape3D`
unless the implementation needs object-level compatibility with existing part
and STL workflows.

### `src/cady/files/stl/__init__.py`

Only touch if adding a direct `write_array_mesh(...)` or `write_faceted_mesh(...)`
helper. Prefer reusing existing `StlMesh` or triangle conversion helpers first.

### `README.md`

Document the support matrix:

| Entity | Import target | Status |
|--------|---------------|--------|
| `3DFACE` | `FacetedMesh` | stage 1 |
| polyface `POLYLINE` | `FacetedMesh` | stage 2 |
| 3D wire `POLYLINE` | `Polyline3D` | stage 3 |
| `3DSOLID`/`BODY`/`REGION`/`SURFACE` | skipped report | non-goal |

## Suggested Fixture Shape

Use tiny hand-written ASCII DXF fixtures in tests instead of binary or large
CAD exports:

```text
0
SECTION
2
ENTITIES
0
3DFACE
8
MESH
10
0
20
0
30
0
11
1
21
0
31
0
12
0
22
1
32
0
13
0
23
1
33
0
0
ENDSEC
0
EOF
```

This represents one triangle when the third and fourth points are equal.

