# Geometry Module Refactor

## Goal

Keep `cady.geometry` as one concept-oriented semantic package while moving
substantial numerical and topology algorithms into focused `cady.operations`
modules. Public classes, import paths, behavior, and immutable semantics remain
unchanged.

## Scope

- Move `Curve2` and `Curve3` protocols from `geometry/polyline.py` to
  `geometry/curve.py`, continuing to re-export them from `cady.geometry` and
  top-level `cady`.
- Move spline sampling, Hermite/Bezier construction, and length algorithms to a
  focused operations module.
- Move polyline discontinuity and curve-discretization algorithms to a focused
  operations module where this produces a clear semantic/algorithm boundary.
- Move mesh face, boundary, snapping, and measurement algorithms out of
  `geometry/mesh.py` into focused modules under `operations/mesh/`.
- Keep geometry methods as thin delegators and keep public construction and
  conversion validation at the semantic boundary.

## Non-goals

- No `geometry2`/`geometry3` packages or dimension-based package split.
- No one-class-per-file rewrite.
- No public API aliases, compatibility modules, new dependencies, or behavior
  changes.
- No unrelated cleanup of existing operations modules.

## Acceptance Criteria

- Existing public imports and geometry behavior pass unchanged.
- `geometry/polyline.py`, `geometry/spline.py`, and especially
  `geometry/mesh.py` contain semantic values and only small local helpers.
- Numeric algorithms have one canonical implementation in focused operations
  modules with allowed dependency direction.
- Geometry, operations, import-boundary, and public-API convention tests pass.
- Pyright, Ruff, the full test suite, and `git diff --check` pass.

## Risks

- Private helpers are extensively interconnected, so extraction can introduce
  cycles or subtle type mismatches.
- Direct imports of geometry modules make file moves visible even when top-level
  public exports remain stable.
- `operations/mesh/topology.py` is already large; new focused modules are
  preferred over adding unrelated algorithms there.

