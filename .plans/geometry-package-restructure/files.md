# File Mapping

## New Geometry Package

| Target | Source | Notes |
|---|---|---|
| `src/cady/geometry/__init__.py` | New | Re-export semantic objects only. Do not export constructor helpers unless deliberately mirroring current package behaviour. |
| `src/cady/geometry/line2d.py` | `geometry2d/curves.py` | Move `Line2D` and shared point/bounds helpers only if local. |
| `src/cady/geometry/arc2d.py` | `geometry2d/curves.py` | Move `Arc2D`; imports focused sampling helpers where needed. |
| `src/cady/geometry/polyline2d.py` | `geometry2d/curves.py` | Move `Polyline2D`, `ClosedPolyline2D`, and dedupe helpers. |
| `src/cady/geometry/conic2d.py` | `geometry2d/curves.py` | Move `Circle2D`, `Ellipse2D`, ellipse sample helper. |
| `src/cady/geometry/spline2d.py` | `geometry2d/curves.py` | Recommended addition even though not in the initial sketch; otherwise `Spline2D` has no clear home. |
| `src/cady/geometry/curves2d.py` | `geometry2d/curves.py` | Recommended protocol module for `Curve2D`, `ClosedCurve2D`, and `Point2Like`. |
| `src/cady/geometry/profile2d.py` | `geometry2d/profile.py` | Move `Profile2D`. |
| `src/cady/geometry/mesh2d.py` | `geometry2d/mesh.py` | Move semantic `Mesh2D`, not numeric arrays. |
| `src/cady/geometry/frame3d.py` | `geometry3d/frame.py` | Move `Frame3D` and `Point3Like`. |
| `src/cady/geometry/face3d.py` | `geometry3d/face.py` | Move `Face3D`; call geometry-local or operations helpers. |
| `src/cady/geometry/body3d.py` | `geometry3d/body.py` | Move `Body3D`; keep feature evaluation behaviour unchanged. |
| `src/cady/geometry/mesh3d.py` | `geometry3d/mesh.py` | Move semantic `Mesh3D`. |
| `src/cady/geometry/wireframe3d.py` | `geometry3d/wireframe.py` | Move `Wireframe3D`; consider later extraction of triangulation helpers. |
| `src/cady/geometry/polyline3d.py` | `geometry3d/curves.py` | Recommended clearer name for `Polyline3D` and `ClosedPolyline3D`. |
| `src/cady/geometry/features.py` | `geometry3d/features.py` | Move feature records. |
| `src/cady/geometry/_mesh_builders.py` | `geometry3d/_mesh_builders.py` | Temporary private helper if needed. Do not move into `operations` unless object imports are removed. |

## New Operations Package

| Target | Source | Notes |
|---|---|---|
| `src/cady/operations/__init__.py` | `ops/__init__.py` | Re-export operation helpers. |
| `src/cady/operations/sampling2d.py` | `ops/curves2d.py` | 2D curve sampling helpers. |
| `src/cady/operations/profiles.py` | `ops/profiles.py` | Profile point helpers only. |
| `src/cady/operations/triangulation.py` | `ops/triangulation.py` | Direct move. |
| `src/cady/operations/mesh_primitives.py` | `ops/meshes3d.py` | Object-free primitive mesh algorithms extracted from `_mesh_builders.py`. |
| `src/cady/operations/mesh_clipping.py` | `ops/mesh_cut.py` | Mesh clipping entry point. |
| `src/cady/operations/mesh_caps.py` | `ops/mesh_cut.py` | Mesh cap and planar boundary closing helpers. |
| `src/cady/operations/mesh_boundaries.py` | `ops/mesh_cut.py` | Boundary edge and loop helpers. |
| `src/cady/operations/planes.py` | `ops/mesh_cut.py` | Plane vector, projection, and fitting helpers. |
| `src/cady/operations/transforms.py` | `ops/point_transforms.py` | Rename for readability. |
| `src/cady/operations/linesplan.py` | `ops/linesplan.py` if it exists | Verify missing/stale linesplan state before migration. |

## New Constructor Helpers Package

| Target | Source | Notes |
|---|---|---|
| `src/cady/operations/__init__.py` | New | Re-export all public constructor helpers. |
| `src/cady/operations/constructors.py` | `geometry2d/constructor helpers.py` and `geometry3d/constructor helpers.py` | Move `line2d`, `arc2d`, `circle2d`, `polyline2d`, `profile_rectangle`, `profile_circle`, `box`, `cylinder`, and `sphere`. |

## Compatibility Shims

| Package | Target Behaviour |
|---|---|
| `src/cady/geometry2d/__init__.py` | Re-export old 2D names from `cady.geometry` and constructor helpers from `cady.operations`. |
| `src/cady/geometry2d/curves.py` | Temporary module-level re-export for imports like `cady.geometry2d.curves.Line2D`. |
| `src/cady/geometry2d/profile.py` | Temporary re-export from `cady.geometry.profile2d`. |
| `src/cady/geometry2d/mesh.py` | Temporary re-export from `cady.geometry.mesh2d`. |
| `src/cady/geometry2d/constructor helpers.py` | Temporary re-export from `cady.operations`. |
| `src/cady/geometry3d/__init__.py` | Re-export old 3D names from `cady.geometry` and constructor helpers from `cady.operations`. |
| `src/cady/geometry3d/*.py` | Temporary module-level re-exports from new geometry modules. |
| `src/cady/ops/__init__.py` | Temporary re-export from `cady.operations`. |
| `src/cady/ops/*.py` | Temporary module-level re-exports from matching `cady.operations` modules where direct module imports exist. |

## Tests And Docs To Update

| Area | Required Update |
|---|---|
| `tests/conventions/test_import_boundaries.py` | Replace `geometry2d`/`geometry3d` authoring package checks with `geometry`; replace `ops` check with `operations`; verify no standalone constructor package exists. |
| `tests/conventions/test_stdlib_only.py` | No conceptual change; verify new packages still satisfy allowlist. |
| Geometry tests | Prefer new imports from `cady.geometry`; keep a small compatibility test for old imports. |
| Ops tests | Prefer new imports from `cady.operations`; keep a small compatibility test for `cady.ops`. |
| Constructor tests | Prefer `cady.operations`; keep top-level `cady` constructor tests. |
| Docs | Update object model, API reference, and examples to mention `geometry`, `operations`, and `constructor helpers`. |
