# Remove Numeric Package

## Goal

Move the code currently under `src/cady/numeric` into `operations`/`geometry`
ownership so `src/cady/numeric` can be deleted.

## Target Ownership

- `operations.types`: NumPy type aliases.
- `operations.validation`: array validation/coercion helpers.
- `operations.bounds`: array bounds helpers.
- `operations.arrays2d`: `ArrayPolyline2`, `ArrayPolygon2`,
  `ArrayBezierSpline2`, and Bezier sampling helpers.
- `operations.arrays3d`: `ArrayMesh3`, `ArrayPolyline3`.
- `operations.transforms`: existing tuple point transform helpers plus
  `Transform2`, `Transform3`, and `Pose3`.

## Acceptance Criteria

- `src/cady/numeric` no longer exists.
- No source, test, docs, or plan references import the old package path.
- Public top-level exports such as `Pose3D` still work.
- Geometry methods still return the same array value types, from their new
  homes.
- Array/transform modules under `operations` do not import semantic geometry
  modules.
- Tests, pyright, ruff, and `git diff --check` pass.

## Non-goals

- No compatibility wrapper for the old package path.
- No behaviour changes to array validation, transforms, or geometry output.
- No dependency changes.
