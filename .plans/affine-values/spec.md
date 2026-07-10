# Affine geometry values

## Goal

Restore small public `Point2`, `Point3`, `Vector2`, and `Vector3` values so
authoring APIs distinguish positions from directions while remaining compatible
with tuple-oriented numeric and file boundaries.

## Behaviour

- Values are immutable sequence values backed by coordinate tuples, with finite
  float coordinates and named coordinate properties.
- Point/vector arithmetic follows affine rules: point minus point is a vector,
  point plus or minus vector is a point, and vectors support vector arithmetic,
  scaling, length, normalization, and dot products; `Vector3` also supports
  cross products.
- Core geometry constructors accept either the typed values or coordinate
  iterables and expose typed point/vector fields.
- All four values are exported from `cady.geometry` and top-level `cady`.
- `Vec2` and `Vec3` aliases remain absent.

## Non-goals

- Do not change NumPy, file-facade, drawing, view, or operation-local tuple
  representations.
- Do not add tolerance-based equality or compatibility aliases.

## Verification

- Focused point/vector, geometry, smoke-import, and convention tests.
- Full pytest, Pyright, Ruff, `git diff --check`, and `git status` gates.
