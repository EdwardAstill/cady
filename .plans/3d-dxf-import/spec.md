# 3D DXF Import Plan

## Problem

cady can now parse a small ASCII DXF 2D subset into `DxfDrawing`, but 3D DXF
geometry has no clean import target. Existing 3D domain objects (`Prism`,
`Extrusion`, `Sphere`, `Revolution`) are semantic solids. They are a poor match
for faceted DXF entities such as `3DFACE`, `POLYFACE MESH`, and `MESH`, which
already describe evaluated vertices and faces.

The project already has `ArrayMesh3` and `ArrayPolyline3` in `cady.numeric`,
but `cady.files.dxf` should not need to pretend imported faceted geometry is a
parametric solid. It needs a small domain/import representation that can convert
to the numeric mesh boundary explicitly.

## Decision

Add faceted 3D import support in stages:

1. Add domain-level faceted geometry types for imported 3D data.
2. Add `cady.files.dxf.read_mesh(...)` for mesh-oriented DXF import.
3. Support `3DFACE` first, then `POLYLINE`/`VERTEX` polyface meshes.
4. Report unsupported 3D solid-kernel entities instead of silently treating
   them as meshes.

Do not attempt native `3DSOLID`, `BODY`, `REGION`, or `SURFACE` import in this
plan. These entities commonly contain embedded ACIS/SAT data and would require
a solid-kernel parser rather than ordinary DXF group-code handling.

## Target API

Mesh-first import:

```python
from cady.files import dxf

mesh = dxf.read_mesh("faceted-part.dxf")
```

Inspection-oriented import:

```python
result = dxf.read_3d("faceted-part.dxf")

result.meshes
result.wires
result.skipped
```

Domain object construction:

```python
from cady import Face3D, FacetedMesh, Vec3

mesh = FacetedMesh.from_faces(
    [
        Face3D((Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0))),
    ]
)
array_mesh = mesh.to_array(tolerance=1e-3)
```

## Supported Entities

Initial:

- `3DFACE`: import triangles and quads. Quads triangulate deterministically
  into two triangles.

Next:

- `POLYLINE` plus `VERTEX` and `SEQEND` for polyface meshes.
- 3D wire `POLYLINE` plus `VERTEX` as `Polyline3D`.

Later if needed:

- `MESH`, if test fixtures show a common enough group-code subset.
- `POINT`, as a `Point3D` or import marker type.

Explicit non-goals:

- `3DSOLID`, `BODY`, `REGION`, `SURFACE` ACIS import.
- Reconstructing semantic solids from faceted meshes.
- DWG import.
- Binary DXF.
- Inferring units or repairing arbitrary malformed CAD exports.

## New Domain Types

### `Face3D`

Frozen dataclass representing one planar polygonal face:

- fields: `vertices: tuple[Vec3, ...]`;
- requires at least 3 vertices;
- provides `triangles()` using fan triangulation for now;
- provides `bounds()`.

This is useful for direct `3DFACE` import and for clear tests.

### `Polyline3D`

Frozen dataclass representing wire geometry:

- fields: `vertices: tuple[Vec3, ...]`, `closed: bool = False`;
- requires at least 1 vertex;
- provides `to_array(tolerance=...) -> ArrayPolyline3`;
- provides `bounds()`.

This maps to 3D DXF polylines that are not faces.

### `FacetedMesh`

Frozen dataclass representing imported or user-authored faceted geometry:

- fields: `vertices: tuple[Vec3, ...]`, `faces: tuple[tuple[int, int, int], ...]`;
- validates face indices and non-empty triangular faces;
- supports `from_faces(...)`;
- provides `to_array(tolerance=...) -> ArrayMesh3`;
- provides `bounds()`;
- optionally subclass `Shape3D` only if it can satisfy the current `Shape3D`
  contract without forcing mesh tolerance semantics. Otherwise keep it as a
  domain mesh object and wire it into STL/file APIs explicitly.

## Import Result

Add a small immutable result object:

```python
@dataclass(frozen=True, slots=True)
class Dxf3DImportResult:
    meshes: tuple[FacetedMesh, ...]
    wires: tuple[Polyline3D, ...]
    skipped: tuple[DxfSkippedEntity, ...]
```

`DxfSkippedEntity` should include:

- `entity_type`;
- `reason`;
- optional `layer`.

This makes partial imports honest and testable.

## Data Flow

```text
ASCII DXF text
  -> dxf.reader group-code pairs
  -> entity chunks
  -> 3D import builders
  -> Face3D / FacetedMesh / Polyline3D
  -> ArrayMesh3 / ArrayPolyline3 at explicit conversion boundaries
```

`read_mesh(path)` should call `read_3d(path)`, merge supported meshes into one
`ArrayMesh3` or `FacetedMesh` result, and raise `ReadError` if no mesh geometry
was imported.

## Dependency Rules

- `cady.files.dxf` may import domain objects, but not NumPy at module scope.
- `cady.domain` must keep NumPy imports lazy inside `to_array(...)`.
- `cady.numeric` must not import domain objects.
- `cady.ops` should not receive domain objects for this feature.
- Do not add runtime dependencies.

## Acceptance Criteria

- `dxf.read_mesh(path)` imports a simple ASCII DXF with one `3DFACE` triangle.
- `dxf.read_mesh(path)` imports a quad `3DFACE` as two triangles.
- `dxf.read_3d(path)` reports skipped `3DSOLID` rather than importing it.
- `FacetedMesh.to_array(tolerance=...)` returns `ArrayMesh3`.
- `Polyline3D.to_array(tolerance=...)` returns `ArrayPolyline3`.
- Existing DXF 2D reader tests still pass.
- Import-boundary and stdlib-only convention tests pass.
- README documents the 3D DXF support subset and ACIS non-goal.

## Risks

- DXF polyface mesh flags are stateful and easy to parse incorrectly. Keep
  `3DFACE` separate and ship that first.
- `3DFACE` can repeat the third and fourth point for triangles; tests should
  cover both triangle encodings.
- Imported meshes may be open, non-manifold, or inconsistently wound. The
  importer should preserve geometry, not try to repair it in v1.
- Making `FacetedMesh` a `Shape3D` would let existing `StlMesh.add(...)` work,
  but it may blur semantic-vs-evaluated boundaries. Decide deliberately during
  implementation.

## Rollback

Each stage can be rolled back independently:

- remove new domain faceted types and exports;
- remove `dxf.read_3d` / `dxf.read_mesh` facade functions;
- remove tests/docs for the corresponding stage.

