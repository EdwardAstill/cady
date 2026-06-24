# Architecture

cady separates authoring objects from evaluated numeric data and file writers.
The authoring packages are small, immutable, and import-light; numeric and ops
packages own the array-heavy work.

## Package layout

```text
cady.geometry2d   2D curves, closed curves, profiles, and factories
cady.geometry3d   3D frames, faces, bodies, mesh builders, meshes, primitives
cady.drawing      2D drawing documents, layers, text, hatches, blocks, dimensions
cady.product      parts, materials, assemblies, and flattening
cady.view         backend-independent scene/camera/light/style values
cady.document     optional named registry for project contents
cady.numeric      NumPy-backed arrays, validation, bounds, transforms
cady.ops          object-agnostic geometry algorithms
cady.files        DXF, STL, and STEP facades
cady.visualisation optional scene helper layer
cady.errors       shared exception hierarchy
```

The removed `cady.domain`, `cady.build`, `cady.plotting`, and old top-level
model packages are not compatibility targets in this branch.

## Conversion boundaries

Authoring objects keep CAD meaning until a caller asks for evaluated geometry:

```text
Line2D.to_array(tolerance=...)      -> ArrayPolyline2
Profile2D.to_array(tolerance=...)   -> ArrayPolygon2
Body3D.to_mesh(tolerance=...)       -> Mesh3D
Part.to_mesh(tolerance=...)         -> ArrayMesh3
Assembly.to_mesh(tolerance=...)     -> ArrayMesh3
Mesh3D.to_array(tolerance=...)      -> ArrayMesh3
```

Every conversion that can sample curves or meshes takes an explicit
`tolerance` keyword. File facades may provide user-facing defaults, but internal
conversion code should still pass tolerance explicitly.

## Dependency direction

The intended dependency direction is:

```text
authoring object -> ops primitive function -> numeric result
files -> authoring/numeric
visualisation -> view/authoring/numeric
```

`cady.numeric` and `cady.ops` do not import authoring packages. Authoring
methods adapt their fields into primitive tuples, arrays, and scalar arguments
before calling numeric or ops functions.

`cady.files` does not import NumPy or viewer packages at module scope. Writers
convert through public object methods and local imports where needed.

## Authoring packages

`geometry2d` owns curves and profiles. It may use `cady.ops.curves2d` for
sampling but keeps public objects semantic.

`geometry3d` owns frames, faces, bodies, features, and `Mesh3D`. `Body3D`
features currently mesh primitives and profile extrusions. Boolean, revolve,
fillet, and chamfer feature records exist but are not evaluated yet.

`drawing` owns drafting-level state. It is not a view scene and it is not a
product part.

`product` owns part and assembly structure. It flattens assemblies by composing
transforms and then delegates mesh generation to parts.

`view` owns presentation values only. It deliberately does not render.

`document` is a registry of named drawings, parts, assemblies, and scenes.

## Runtime dependencies

Runtime imports are limited to the project itself, NumPy, and steputils.
Optional viewer or plotting dependencies are allowed only in optional leaf
packages. Convention tests enforce this boundary.
