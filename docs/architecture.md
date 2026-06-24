# Architecture

## Overview

cady separates semantic CAD objects from numeric algorithms. Domain objects
preserve design intent; ops and numeric modules handle evaluated geometry.

## Details

## Packages

```text
cady.build         factories
cady.domain        semantic geometry, drawings, parts, models
cady.ops           object-agnostic geometry algorithms
cady.numeric       NumPy-backed evaluated geometry
cady.files         DXF, STL, STEP I/O
cady.plotting      optional static plotting
cady.visualisation optional interactive viewing
cady.errors        shared exceptions
```

## Conversion Boundary

The intended path is:

```text
domain object.to_array(tolerance=...) -> ops primitive function -> numeric result
```

Domain methods unpack fields such as centre, radius, vertices, axis, and
distance. Ops functions work on arrays, tuples, lists, scalars, and primitive
axis values. Numeric classes validate and store the evaluated result.

## Semantic Layer

Use domain objects when shape meaning matters:

- `Circle` should export as a DXF circle;
- `Spline` should keep Bezier control points;
- closed profiles should keep holes;
- `Extrusion` should remember its profile, axis, and distance;
- `Model` should keep drawings, parts, assemblies, and metadata.

## Numeric Layer

Use numeric objects for:

- vectorised calculation;
- matrix transforms;
- mesh cutting;
- plotting and viewer conversion;
- STL-style triangle output;
- bounds and validation over point arrays.

## Import Boundaries

CI enforces the important dependencies:

- `cady.domain` does not import NumPy, plotting, or visualisation at module
  scope;
- `cady.numeric` does not import `cady.domain`;
- new `cady.ops` modules do not import `cady.domain`;
- `cady.files` stays import-light and does not import plotting/viewer modules
  at module scope.

Use local imports for conversion paths that would otherwise violate those
boundaries.

