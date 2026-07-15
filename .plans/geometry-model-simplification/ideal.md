# Ideal Geometry Model

## Purpose

cady should let callers construct immutable semantic geometry, compose it into
higher-level objects, and convert it explicitly into sampled arrays or meshes
for measurement, files, and viewing.

## Inputs And Outputs

- Inputs: coordinate values, curves, closed boundaries, surface placements,
  body feature records, transforms, and explicit conversion tolerances.
- Semantic outputs: new immutable geometry values produced by construction,
  composition, and transformation.
- Numeric outputs: sampled arrays and triangle meshes produced only at explicit
  conversion boundaries.
- Application outputs: drawings, products, file data, and prepared view buffers
  that consume semantic geometry without becoming dependencies of geometry or
  operations.

## Invariants

- Public geometry remains immutable and tuple-backed.
- Dimension-specific values remain type-distinct where their operations differ.
- Sampling and meshing require an explicit positive finite tolerance.
- Application layers depend on geometry; geometry and operations do not depend
  on application layers.
- Optional viewer dependencies remain lazy.
- Each conversion has one canonical path.

## Target Relationships

1. Use concrete frozen value classes for semantic concepts.
2. Prefer composition for real ownership relationships:
   polylines contain curves, regions contain closed boundaries, bodies contain
   feature history, and parts contain independent bodies.
3. Use small structural capability protocols only when callers genuinely need
   uniform behavior. Candidate capabilities are bounded, sampleable curve,
   meshable, and transformable behavior, split by dimension where necessary.
4. Do not introduce a universal `Shape` or `Geometry` base class unless it owns
   a meaningful invariant or implementation shared by nearly every subtype.
   Marker inheritance and methods that raise `NotImplementedError` are not a
   useful relationship.
5. Give every value in the same public capability one consistent conversion
   method. In particular, a curve capability should expose one array-sampling
   boundary so callers do not enumerate analytic versus linear curve classes.
6. Keep algorithms in focused operation modules and keep semantic methods thin.
7. Keep dispatch local and explicit when the supported set is small; introduce
   shared dispatch only when multiple independent consumers duplicate the same
   semantic conversion.

## Desired Data Flow

```text
coordinates -> immutable semantic value -> composition
                                      |
                                      +-> to_array(tolerance=...) -> numeric array
                                      +-> to_mesh(tolerance=...)  -> Mesh2 / Mesh3
                                      +-> transformed(...)        -> new semantic value

semantic target -> file/view/product boundary -> canonical conversion above
```

## Error Model

- Reject malformed semantic state at construction.
- Reject invalid tolerance at the public conversion boundary.
- Use domain errors where a valid object cannot perform a requested geometric
  operation; use `TypeError` for values that do not provide the promised
  capability.

## Success Criteria

- A caller can reason about objects from their semantic names and small,
  consistent capabilities.
- Adding a curve does not require edits in every consumer merely because its
  sampling algorithm is analytic rather than linear.
- No base class exists solely to make unrelated geometry appear related.
- Simplification removes branches or duplicate conversion logic rather than
  relocating it behind a larger abstraction.
