# pyseas-cad Stage 1 — DXF + STL writer

**Status:** spec, awaiting plan.
**Date:** 2026-05-08.
**Author:** Edward Astill (with Claude as drafting partner).
**Scope:** Stage 1 of pyseas-cad — a pure-Python, write-only CAD library that turns
format-blind geometry primitives into DXF (R2018) and STL (binary + ASCII) files.

---

## Bootstrap exception

This is a greenfield project. At spec-write time the repository contained only
`IDEAS.md` and this spec — no `src/`, no tests, no prior commits. Bootstrap
(`git init -b main`, two commits carrying `IDEAS.md`, this spec,
`.warden/preference-lock.json`, `notes/` cheatsheets, `.gitignore`, then
`git worktree add -b stage-1 .worktrees/stage-1`) was executed by the
`writing-plans` skill before plan tasks begin, so all plan tasks run inside
`.worktrees/stage-1/` on branch `stage-1`. The plan therefore starts directly
at the first source-code task; no in-plan `git init` step is required.

---

## 1. Goal

Ship a small, pure-stdlib Python package that lets a caller (typically pyseas-yard)
build geometric primitives once and emit them as either a 2D DXF drawing or a 3D
STL mesh. The library knows about lines, polylines, arcs, circles, splines,
extrusions, revolutions, spheres, and prisms. It does not know about padeyes,
shackles, or any other lifting-gear domain object.

Stage 1 is the foundation for the staged plan in `IDEAS.md`: DXF coverage grows in
Stages 2–3 (HATCH, INSERT, DIMENSION); STL is locked at this stage; STEP is a
separate spec from Stage 5 onward.

> **Note on `IDEAS.md` staging drift:** the original `IDEAS.md` table groups
> `MTEXT` with HATCH/INSERT in Stage 2. This spec promotes `MTEXT` (text
> annotation) into Stage 1 because pyseas-yard recipes need part labels in the
> first end-to-end drawing. HATCH and INSERT remain Stage 2. Where the spec and
> `IDEAS.md` disagree, the spec wins.

## 2. Why this scope

Per `IDEAS.md`, pyseas-cad replaces ezdxf inside pyseas-yard once feature parity is
reached. Stage 1 picks the smallest end-to-end slice that proves the architecture
works across two formats:

- DXF exercises the entity-stream / scene-state / annotation pattern.
- STL exercises the geometry layer (transforms + tessellation) and forces
  `geom/` to stay format-blind.

If the geom layer is correct enough to feed both writers from one source, adding
STEP later is a matter of writing a third scene + writer pair, not a refactor.

## 3. Locked Decisions

These decisions are the contract between this spec and the implementation plan.
The plan and executing agent must not silently override them. Every item is
mirrored in `.warden/preference-lock.json` (see `warden preference list`).

### 3.1 Architecture

- **Three layers, one-way dependency**: `write/` → `scene/` → `geom/` →
  `_vendor/`. No upward arrows. `geom/` never imports from `scene/` or `write/`.
- **Geom layer is format-blind value types** — frozen slots dataclasses,
  transforms return new instances, validation in `__post_init__`.
- **Scene layer is per-format**: `DxfDrawing` and `StlMesh` are separate types,
  each owning only the scene state its format needs (layers/blocks/dim styles for
  DXF; tessellation tolerance for STL). No shared "Document" abstraction.
- **Writers** live under `write/dxf/` and `write/stl/`; each scene calls its own
  writer. Adding STEP later is a third independent pair, not a refactor.

### 3.2 Scope of "parts"

- Domain-blind primitives only. The library never imports from `pyseas-yard`
  and has no `Padeye`, `Shackle`, etc. Recipes ("how to draw a padeye") live in
  pyseas-yard, which imports `cad.geom` and `cad.scene`.

### 3.3 Stage 1 deliverables

- Working DXF writer covering `LINE`, `LWPOLYLINE`, `CIRCLE`, `ARC`, `MTEXT`.
- Working STL writer (binary by default, ASCII flag for tests).
- Geom layer with two disjoint type families:
  - **Shape2D**: `Line`, `Arc`, `Circle`, `Rectangle`, `Polyline`, `Spline`,
    `Path` (the compound result of `+`-composing 2D segments).
  - **Shape3D**: `Sphere`, `Prism`, `Extrusion`, `Revolution`.
- Lowercase factory functions: `line`, `arc`, `circle`, `rectangle`, `polyline`,
  `spline`, `sphere`, `prism`. (`extrude` and `revolve` are methods on Shape2D
  that return Shape3D — see §3.4.)
- Vector types `Vec2` and `Vec3` are internal value types; user code uses
  tuples `(x, y)` and `(x, y, z)` and the library promotes them.
- Tessellator with `curves_to_polyline`, `polygon_to_triangles` (via vendored
  earcut), and `extrusion_to_triangles` / `revolution_to_triangles`.
- One end-to-end example (`examples/plate_with_hole.py`) producing both formats
  from one geom source.
- Test suite at three layers (geom unit / scene assembly / writer output).

### 3.4 API shape

The user-facing surface is built around four ideas: lowercase factory functions
that return immutable shape values, `+` for composing 2D segments, methods on
shapes for transforms and the 2D→3D bridge, and per-format scenes that accept
only the dimensionality they represent.

**Hard rule — 2D and 3D are disjoint type families.** A `Shape2D` never has
3D-only operations (no `translate(dx, dy, dz)`, no `extrude` cannot be called
*on* a 3D shape). A `Shape3D` never has 2D-only operations (no `with_hole`, no
`extrude` is callable *on* a `Shape3D`). The only bridges from 2D to 3D are
the `extrude` and `revolve` methods on closed 2D shapes; there is no bridge
the other way in Stage 1.

**2D factory functions** (lowercase, accept tuples or `Vec2`):

```python
line(a, b)                      # open 2-point segment
arc(centre, radius, start, end) # arc segment, radians
circle(centre, radius)          # closed circle (one entity, exact)
rectangle(corner, size)         # closed rectangle
polyline(points, closed=False)  # general polyline
spline(control_points)          # cubic-Bezier spline (3n+1 control points)
```

**Shape2D operations** (methods, all return new immutable values):

```python
a + b                  # compose adjacent segments → Path (head-to-tail)
shape.close()          # → closed Shape2D; auto-adds closing line if last≠first
shape.with_hole(h)     # closed Shape2D with one inner hole (h must be closed Shape2D)
shape.with_holes([…])  # closed Shape2D with multiple inner holes
shape.translate(dx, dy)
shape.rotate(centre, angle)                   # centre = (x, y) tuple, angle in rad
shape.mirror(through=Line)                    # mirror across a Line; pass via cad.line(a, b)
shape.bounds()         # → (Vec2, Vec2)
shape.extrude(axis, distance)    # closed Shape2D → Extrusion (3D)
shape.revolve(axis, angle=2*pi)  # any Shape2D → Revolution (3D); axis = Line in same XY plane as profile
```

**Closability is a runtime attribute, not a type.** Every Shape2D carries a
`closed: bool` flag. `close()` returns the same concrete type with
`closed=True` (and an auto-added closing `Line` segment if the last point
differs from the first). `Circle` and `Rectangle` are always closed by
construction. `Path` (the result of `+`) starts open and becomes closed via
`.close()`. `with_hole` / `with_holes` / `extrude` require `closed=True`
and raise `ValueError` otherwise.

`+` is **not commutative** — `line(a,b) + line(b,c)` traces a→b→c, while
`line(b,c) + line(a,b)` traces b→c then a→b (a discontinuous path which the
Path validator rejects unless segments share endpoints).

`axis` accepts either a string in `{"+x","-x","+y","-y","+z","-z"}` or a
`Vec3`. Strings cover 99 % of engineering cases; the `Vec3` form is the
escape hatch for arbitrary axes.

**Profile-plane convention for `extrude`** (axis-aligned cases). The 2D
profile's local `(x, y)` maps to specific world axes based on the
extrusion direction:

| `axis` | profile.x → | profile.y → | extrusion sweep |
|--------|-------------|-------------|-----------------|
| `+z`   | world.x     | world.y     | along world.z   |
| `-z`   | world.x     | world.y     | along world.-z  |
| `+y`   | world.x     | world.z     | along world.y   |
| `-y`   | world.x     | world.z     | along world.-y  |
| `+x`   | world.y     | world.z     | along world.x   |
| `-x`   | world.y     | world.z     | along world.-x  |

The profile plane is the plane perpendicular to the sweep axis; the
profile's y-axis maps to world-z whenever the sweep is in the XY plane
(so a "side view" extrudes naturally into a vertically-standing plate).
For arbitrary `Vec3` axes, the in-plane u/v basis is chosen
deterministically as `cross(world.+z, axis).normalised()` (falling back
to `cross(world.+y, axis)` when axis is parallel to z).

**3D factory functions**:

```python
sphere(centre, radius)
prism(origin, size)              # axis-aligned box
```

**Shape3D operations** (methods):

```python
solid.translate(dx, dy, dz)
solid.rotate(axis_origin, axis_dir, angle)   # tuples or Vec3, angle in rad
solid.mirror(plane_origin, plane_normal)     # tuples or Vec3
solid.bounds()                               # → (Vec3, Vec3)
# Stage 6+: solid.cut(other), solid.union(other), solid.intersect(other)
```

**Scenes**:

```python
d = DxfDrawing()
d.layer("PLATE", color=7).add(shape2d)             # accepts only Shape2D
d.add_text("LABEL", at=(0,0), height=0.01, layer=…)
d.write(path)                                       # → DXF file

s = StlMesh()                                       # tolerance default 1e-3
s.add(*shapes3d)                                    # accepts only Shape3D; variadic
s.write(path, ascii=False)                          # → STL file
```

`DxfDrawing.layer(name: str, color: int = 7)` — `color` is positional-or-keyword
with a default of `7` (AutoCAD's "white" / colour-by-context). Creates the
layer if it does not yet exist and returns a mutable `Layer` reference whose
`add(...)` returns the layer itself for chaining. Default
`linetype="CONTINUOUS"`. Passing a Shape3D to `Layer.add(...)` is a static
type error (and a `SceneError` if the type checker is bypassed).

`StlMesh(tolerance: float = 1e-3)` — `tolerance` is keyword-or-positional with
a default of `1 mm`. `add(*solids)` is variadic and returns the mesh for
chaining. It tessellates lazily on add; the same `Extrusion` value can be
added to two meshes at different tolerances and produce different triangle
counts.

`DxfDrawing` Stage 1 annotation API: `add_text(text, at, height, layer)`.
Placeholder `add_dimension(...)` documented but not implemented; reserved
for Stage 3.

### 3.5 Geom value types

- Two abstract base classes: `Shape2D` and `Shape3D`. Concrete types inherit
  from one and only one. The two hierarchies share no methods.
- All concrete types are frozen, slots, immutable. Validation in
  `__post_init__` raises `ValueError`.
- `Vec2` and `Vec3` are internal value types. They support `+`, `-`, unary
  `-`, `* scalar`, `length()`, `normalised()`, `dot(other)`; `Vec3`
  additionally has `cross(other)`. User code writes tuples `(x, y)` /
  `(x, y, z)` and the factory functions promote them.
- **Shape2D concrete types**: `Line` (two points), `Arc` (centre, radius,
  start_rad, end_rad), `Circle` (centre, radius — always closed), `Rectangle`
  (origin, size — always closed), `Polyline` (point sequence, open or closed),
  `Spline` (cubic Bezier, multi-segment, open or closed), and `Path` (the
  compound type produced by `+`-composing other 2D segments). A closed
  Shape2D may carry an inner-loop tuple (set via `with_hole`/`with_holes`);
  open ones may not.
- **Shape3D concrete types**: `Sphere`, `Prism`, `Extrusion`, `Revolution`.
  `Extrusion` carries `profile: Shape2D` (must be closed), `axis: Axis`
  (validated string or `Vec3`), `distance: float`. `Revolution` carries
  `profile: Shape2D`, `axis_origin: Vec3`, `axis_direction: Vec3`,
  `angle_rad: float`.
- Every concrete shape exposes `bounds()` returning `(Vec2, Vec2)` for
  Shape2D and `(Vec3, Vec3)` for Shape3D.

### 3.6 Transforms

- Transforms are **methods on the shape**, not free functions:
  `shape.translate(...)`, `shape.rotate(...)`, `shape.mirror(...)`.
- Method signatures differ between Shape2D and Shape3D:
  `Shape2D.translate(dx: float, dy: float)` vs
  `Shape3D.translate(dx: float, dy: float, dz: float)`. Wrong arity is a
  static type error.
- All transforms return new instances of the same shape type; geom values
  are never mutated.
- Convenience: methods accept individual scalars (`shape.translate(0.1, 0.2)`)
  rather than vector arguments — fewer parens, no need to construct a `Vec2`
  in user code.

### 3.7 Triangulation

- Vendor the pure-Python port of mapbox-earcut at `src/cad/_vendor/earcut.py`,
  MIT licensed. Add a `NOTICE` file at the project root with attribution.
- `tessellate.polygon_to_triangles(closed_shape2d)` is the single entry point;
  callers never reach into `_vendor` directly.
- The tessellator accepts any closed `Shape2D` (not only `Polyline`). Curved
  segments (`Arc`, `Circle`, curved `Path` segments) are flattened first via
  `curves_to_polyline` at the requested tolerance; earcut runs on the result.

### 3.8 Solid-model semantics

- `Extrusion` and `Revolution` are *intent* descriptions, not B-reps or meshes.
- `StlMesh.add(extrusion)` tessellates lazily on add (not on construction).
- Future STEP writer interprets the same intent values as B-rep topology — no
  shared kernel.
- **No boolean operations in Stage 1.** "Plate with hole" is a 2D-side
  concept: a closed Shape2D with one or more inner-loop holes via
  `.with_hole(...)`. The tessellator handles holes natively. There is no
  `Shape3D.cut(other)` in Stage 1; calling such a method (or attempting
  `solid - solid`) is a `TypeError` with a message pointing at the future
  STEP / boolean spec.

### 3.9 Tessellator contract

`tessellate.py` exposes:

- `curves_to_polyline(shape: Shape2D, *, tolerance: float) -> Polyline` —
  flatten any Shape2D containing curved segments (`Arc`, `Circle`, curved
  `Path` segments, `Spline`) into a polyline whose chord error stays under
  `tolerance`. A pure-line input is returned as a `Polyline` unchanged.
- `polygon_to_triangles(shape: Shape2D, *, tolerance: float) -> list[Triangle2]`
  — earcut-backed; **accepts any closed Shape2D** (curves are flattened
  internally via `curves_to_polyline` first). Returns triangles. Raises
  `ValueError` if the shape is open.
- `extrusion_to_triangles(extrusion: Extrusion, *, tolerance: float) -> list[Triangle3]`
  — cap-and-wall builder over the tessellated profile.
- `revolution_to_triangles(revolution: Revolution, *, tolerance: float) -> list[Triangle3]`
  — profile points × angular samples (count derived from tolerance), stitched
  into triangle bands.

**Cap and side tessellation strategy.** For axis-aligned `Prism` and any
straight-walled `Extrusion`, each rectangular face is split into exactly two
triangles along one diagonal (deterministic choice: corner with smaller
sorting key first). A unit `Prism` therefore produces exactly 12 triangles —
2 per cap × 2 caps + 2 per side × 4 sides. For `Extrusion` profiles with
holes, caps come from `polygon_to_triangles` (earcut output) and sides come
from one quad-as-two-tris band per profile edge.

### 3.10 Annotations placement

- Annotations are scene-level entities on `DxfDrawing`, never on geom values.
  Stage 1 implements `add_text(...)`. `add_dimension(...)` is reserved as a
  documented placeholder for Stage 3.

### 3.11 Conventions

- **Units:** SI metres. DXF `$INSUNITS = 6` (metres).
- **Coord system:** Z-up, right-handed.
- **DXF version:** R2018 (`AC1032`). No R12 fallback in Stage 1.
- **STL format:** binary by default; `ascii=True` flag for tests and inspection.
- **Number formatting:** 8 significant figures in any ASCII output.
- **Python version:** 3.11 or newer.
- **Runtime deps:** pure stdlib. `ezdxf` is a dev-only test dependency.

### 3.12 Error model

- **Tier 1 — construction:** `ValueError` from concrete shape `__post_init__`.
  Catches empty/degenerate primitives, negative radii, zero direction
  vectors, holes on open Shape2D, NaN/inf coordinates, `+`-composition of
  segments whose endpoints don't match, malformed `axis` strings.
- **Tier 2 — scene assembly:** `cad.SceneError` at `scene.add(...)`. Catches
  type mismatches that escape the static checker (passing a `Sphere` to a
  `DxfDrawing`, passing a `Layer` from a different drawing).
- **Tier 3 — writer:** `cad.WriteError` during serialisation. Catches empty
  drawings, profiles earcut rejects (self-intersecting), and surfaces the
  offending entity in the message.
- All three tiers (except Tier 1) derive from `cad.CadError` so callers can
  `except CadError:` once. Tier 1 stays plain `ValueError` to match dataclass
  conventions.
- **No silent recovery.** No auto-close, no NaN-replacement, no version
  downgrade, no entity-skipping. Engineering CAD that mutates inputs silently
  is how broken parts reach manufacturing.

### 3.13 Library direction

- pyseas-cad is **write-only**. No DXF parser, no STL parser, no round-trip.
  Tests use `ezdxf` to verify our output, but pyseas-cad ships no read path.

### 3.14 Worked example — padeye recipe

This recipe is the canonical example of how a pyseas-yard caller uses the
library. It is **not** part of the package; it lives in pyseas-yard or in
`examples/`. The implementer should cross-check the API surface against this
example: every line below must compile and run against the Stage-1
implementation.

The example is API-illustrative only — the exact placement math (cheek
offsets, layer colours) is not part of the spec contract. Engineering
correctness of the padeye geometry is pyseas-yard's responsibility.

```python
from cad import line, arc, circle, DxfDrawing, StlMesh
from math import pi
from dataclasses import dataclass

@dataclass(frozen=True)
class PadeyeParams:
    half_width: float; height_below_pin: float
    pin_height: float; pin_radius: float; cheek_radius: float
    plate_thickness: float; cheek_thickness: float

def build_padeye(p: PadeyeParams):
    # ── 2D world ─────────────────────────────────────────────
    side = (
          line((-p.half_width, 0),                  (p.half_width, 0))
        + line((p.half_width, 0),                   (p.half_width, p.height_below_pin))
        + arc((0, p.height_below_pin), p.half_width, 0, pi)
        + line((-p.half_width, p.height_below_pin), (-p.half_width, 0))
    ).close()

    pin_hole   = circle((0, p.pin_height), p.pin_radius)
    cheek_face = circle((0, p.pin_height), p.cheek_radius)

    # ── 2D → 3D ──────────────────────────────────────────────
    main  = side.with_hole(pin_hole).extrude(axis="+y", distance=p.plate_thickness)
    cheek = cheek_face.with_hole(pin_hole).extrude(axis="+y", distance=p.cheek_thickness)

    # ── 3D world ─────────────────────────────────────────────
    cheek_a = cheek.translate(0,  p.plate_thickness/2,                    0)
    cheek_b = cheek.translate(0, -p.plate_thickness/2 - p.cheek_thickness, 0)

    return [side, pin_hole, cheek_face], [main, cheek_a, cheek_b]


def draw_padeye_dxf(p: PadeyeParams, path: str):
    twoD, _ = build_padeye(p)
    side, pin_hole, cheek_face = twoD
    d = DxfDrawing()
    d.layer("PLATE",  color=7).add(side)
    d.layer("HOLES",  color=1).add(pin_hole)
    d.layer("CHEEKS", color=2).add(cheek_face)
    d.write(path)


def model_padeye_stl(p: PadeyeParams, path: str):
    _, solids = build_padeye(p)
    StlMesh(tolerance=1e-4).add(*solids).write(path)
```

Notice: the *same* `pin_hole = circle(...)` value is used twice — once as a
2D entity drawn on the HOLES layer in DXF, and once as a hole inside two
different 3D extrusions. Geom values are immutable and reusable.

### 3.15 Testing strategy

- `tests/geom/`: pure-function unit tests on value types, transforms, and
  tessellation (area / containment / chord-error invariants, not
  point-by-point golden tris).
- `tests/scene/`: assemble `DxfDrawing` and `StlMesh` in memory and assert
  scene state without I/O.
- `tests/write/`: golden-file byte-exact tests for stable cases plus
  `ezdxf`-round-trip behavioural tests for things golden bytes can't express
  (e.g., AutoCAD reads our circle at the right centre/radius). STL parsed
  with stdlib `struct`.
- `tests/examples/`: end-to-end run of `examples/plate_with_hole.py` to prove
  the full pipeline.

## 4. Open Assumptions

These are provisional. The plan must validate or escalate before locking.

- **Vendor source for earcut.** Assumption: a pure-Python MIT-licensed port
  exists and is small enough to vendor (~300 LOC). The plan must locate the
  exact upstream (likely a port of `mapbox/earcut.hpp` to Python by a
  third-party), verify the licence, and pin a specific commit/version in
  `NOTICE`. If no acceptable pure-Python port exists, escalate — option B is
  hand-rolling ear-clipping with holes, which expands Stage 1 by ~3–4 days.
- **DXF R2018 minimum group-code surface.** Assumption: emitting `LINE`,
  `LWPOLYLINE`, `CIRCLE`, `ARC`, `MTEXT` plus `HEADER` (`$ACADVER`,
  `$INSUNITS`, bounds), `TABLES` (LAYER table), and `EOF` is enough for AutoCAD
  / LibreCAD / DraftSight to open the file without warnings. Verify with the
  ezdxf round-trip test against each entity.
- **STL binary header.** Assumption: an empty 80-byte header plus uint32
  triangle count plus N×50-byte triangle records is sufficient. Verify against
  the canonical binary STL spec and a known-good slicer.
- **Z-up for STL.** Assumption: emitting Z-up triangles is correct for
  downstream consumers (slicers, CAM). Slicers normally accept any axis
  convention but it is worth a smoke test with one slicer (e.g., PrusaSlicer)
  during the example run.

## 5. Rejected Alternatives

- **Option A: imperative document-only API** (`doc.line(...)`, no geom
  values). Rejected because it forces separate `DxfDocument` / `StlDocument`
  with overlapping but mismatched method sets, makes cross-format reuse hard,
  and gives no inspectable geom layer for testing.
- **Option B: pure geometry-first API** (geom values, writer takes a list).
  Rejected because DXF scene state (layers, blocks, header vars, dimstyles) has
  nowhere natural to live, and tacking `layer=` onto every geom value pollutes
  3D primitives that have no layer concept.
- **Option C: one Document, multiple writers** (`doc.write_dxf()`,
  `doc.write_stl()`). Rejected because it forces awkward decisions about
  mismatched primitives (what does STL do with HATCH?). Per-format scenes
  (chosen option D) keep each format honest.
- **Domain-aware parts in pyseas-cad** (Padeye, Shackle as first-class types).
  Rejected because it collapses the boundary that makes pyseas-cad reusable
  outside lifting-gear and forces every other pyseas package to depend on
  lifting-gear vocabulary.
- **Hand-rolled ear-clipping with holes.** Rejected as the default because
  edge-case correctness (collinear points, near-degenerate triangles) is weeks
  of work that mapbox-earcut has already paid. Held in reserve only if no
  acceptable pure-Python port exists.
- **Boolean ops on geom values in Stage 1.** Rejected because real boolean
  CSG needs a kernel; tessellation with holes via earcut covers the Stage 1
  use case (plate-with-hole) without that complexity.
- **DXF R12 baseline.** Rejected because R12 lacks `LWPOLYLINE`, which we
  need for plate outlines. Optional R12 emit is a future deferral, not Stage 1.
- **Sheet templates / title blocks in core.** Rejected; they belong in
  recipe code (pyseas-yard or `examples/`), built from primitives.
- **Capital-letter dataclass-constructor API surface** (e.g.,
  `Polyline(points=(Vec2(0,0), Vec2(1,0)))`). Rejected as the user-facing
  surface because real recipe code reads as engineering, not Java —
  lowercase factory functions and tuple-promoted points produce dramatically
  shorter and more readable recipes. Dataclasses still exist internally;
  the factory functions are the surface.
- **Shared 2D/3D operator overloads** (`shape - hole` for both 2D
  hole-cut and 3D boolean). Rejected because the same operator means two
  semantically different things, with one of them deferred to Stage 6.
  Holes use `with_hole(...)` (2D-only method); future 3D booleans use
  named methods (`.cut`, `.union`, `.intersect`). Different words for
  different operations.
- **Shared `translate(geom, vector)` free function with overloaded vector
  type** for both 2D and 3D. Rejected in favour of method-style transforms
  with arity-distinct signatures (`shape2d.translate(dx, dy)` vs
  `shape3d.translate(dx, dy, dz)`) — clearer call sites, no ambiguity.

## 6. Recommended Skills

The plan-writer and executing agent should consider these skills. The list is a
starting point; each task may add or drop skills.

- `superpowers:writing-plans` — to consume this spec into a TDD plan.
- `superpowers:test-driven-development` — every geom value type and tessellator
  function is test-first; writers use golden-file + round-trip tests.
- `python` (warden language skill, if present) — implementation language.
- `library-docs` — for the DXF R2018 group-code reference and binary STL spec.
- `code-import` — to vendor `mapbox-earcut`'s pure-Python port with
  provenance, licence check, and `NOTICE` entry.
- `simplify` — pass after Stage 1 finishes to remove premature abstractions.
- `superpowers:requesting-code-review` — at the end of Stage 1.
- `superpowers:verification-before-completion` — for the post-implementation
  block below.
- `audit` — eventual sanity check on the manifest once skills/hooks/tools are
  added.

## 7. Non-goals

Out of scope for this spec (full list in `.warden/preference-lock.json`):

**Format / file work (deferred to later staged specs):**
- DXF `DIMENSION` rendering — Stage 3 spec.
- DXF `HATCH` / `INSERT` / `BLOCK` — Stage 2 spec.
- STEP writer (any AP) — Stage 5+ spec.
- DXF R12 emit, AP203 fallback for STEP, GD&T tolerance bands.
- DXF or STL parsing / round-trip (write-only library).

**Geometry / kernel work (deferred):**
- 3D boolean operations (`.cut`, `.union`, `.intersect`) — Stage 6 spec.
- `Sweep` type for swept profiles (shackle bodies, U-bolts, pipe elbows,
  threads) — Stage 5+ alongside STEP.
- 3D fillets, chamfers, blends on extruded edges — Stage 6+. (2D chamfers
  remain available today by building 45° lines into the outline.)
- NURBS surfaces.

**Editing operations (deferred):**
- TRIM (cut intersecting entities at click point, remove closest piece) —
  Stage 4 spec. Requires ~10 pairwise intersection algorithms.
- `split_at(t)` on 2D segments — Stage 1.5 or Stage 4 (cheapest precursor
  to TRIM).
- `intersect(a, b)` pair-wise intersection function — Stage 4.
- `Path.simplify()` to auto-merge collinear adjacent segments — Stage 1.5.

**Helpers (deferred):**
- Construction-line helpers (`midpoint`, `perpendicular`, `tangent_circle`,
  `offset_curve`) — Stage 3 alongside DIMENSION (which needs midpoint and
  perpendicular).
- `Sheet` type hosting multiple views — explicitly outside pyseas-cad's
  scope; layout work belongs in pyseas-yard or a separate package.

**Other:**
- A CLI. Stage 1 is library-only; pyseas-yard drives it.

The deferred items above are tracked in `.warden/preference-lock.json`
under the `Deferred` list. Each will get its own spec when scheduled.
This Stage-1 spec must not silently absorb any of them — they belong to
their target stage.

## Acceptance Criteria

Mechanical, runnable checks every Stage-1 implementation must satisfy.

### Package shape

- [ ] File `src/cad/__init__.py` exists and re-exports the lowercase factory
      functions (`line`, `arc`, `circle`, `rectangle`, `polyline`, `spline`,
      `sphere`, `prism`), the scene types (`DxfDrawing`, `StlMesh`, `Layer`),
      and the error types (`CadError`, `SceneError`, `WriteError`).
- [ ] `Shape2D` and `Shape3D` abstract base classes live in
      `src/cad/geom/base.py`; concrete shapes inherit from one and only one.
- [ ] File `src/cad/_vendor/earcut.py` exists, contains MIT-licensed pure-Python
      earcut, and `NOTICE` at the repo root attributes its origin and commit.
- [ ] `python -c "import cad; from cad import line, arc, circle, sphere, prism, DxfDrawing, StlMesh"` exits 0 with no warnings.

### Runtime dependency promise

- [ ] `pyproject.toml` declares **no runtime dependencies** under
      `[project.dependencies]` (or equivalent build-system field). `ezdxf` and
      `pytest` appear only under `[project.optional-dependencies] dev`.

### Geom layer correctness

- [ ] `pytest tests/geom/ -q` exits 0 with ≥ 30 passing tests.
- [ ] `polyline([])` raises `ValueError`.
- [ ] `polyline([(0,0)], closed=True)` raises `ValueError`.
- [ ] `circle((0,0), -1.0)` raises `ValueError`.
- [ ] `open_path.extrude(axis="+z", distance=0.04)` raises `ValueError`
      (extrude requires a closed Shape2D).
- [ ] `circle((0,0), 1.0).extrude(axis="+z", distance=0.0)` raises
      `ValueError` (zero distance).
- [ ] `circle((0,0), 1.0).extrude(axis="diagonal", distance=0.04)` raises
      `ValueError` (unknown axis string).
- [ ] `(line((0,0),(1,0)) + line((0.5,0),(2,0)))` raises `ValueError`
      (segment endpoints don't match).
- [ ] `rectangle((0,0),(1,1)).translate(2,0).bounds()` returns
      `((2,0), (3,1))` (tuple comparison).
- [ ] `rectangle((0,0),(1,1)).translate(2,0,0)` is a static type error
      (verified via `pyright --strict tests/geom/transform_typing.py` —
      Shape2D has no 3-argument translate).
- [ ] `prism((0,0,0),(1,1,1)).translate(1,0)` is a static type error
      (Shape3D requires three arguments).
- [ ] `circle((0,0), 1.0) - circle((0,0), 0.5)` raises `TypeError` with a
      message referencing `with_hole(...)` and the deferred 3D boolean spec.
- [ ] `prism((0,0,0),(1,1,1)) - prism((0,0,0),(0.5,0.5,0.5))` raises
      `TypeError` with a message pointing at the Stage 6 boolean spec.

### Tessellation correctness

- [ ] `polygon_to_triangles(rectangle((0,0),(1,1)).with_hole(circle((0.5,0.5), 0.2)),
      tolerance=1e-3)` accepts the closed Shape2D (curves flattened internally)
      and returns triangles whose summed area equals `1 - π·0.2²` to within 1 %.
- [ ] No returned triangle has any vertex inside the hole.
- [ ] `curves_to_polyline(circle((0,0), 1.0), tolerance=1e-3)` produces a
      polyline whose maximum chord error against the analytic circle is < 1e-3.
- [ ] Tessellating `prism((0,0,0),(2,2,1))` returns exactly 12 triangles
      (6 faces × 2). (Use `StlMesh.add(prism)` then inspect.)
- [ ] Tessellating a revolution of a unit-square profile around the +Z axis
      produces a watertight closed mesh (every edge shared by exactly 2 tris).

### Scene layer

- [ ] `DxfDrawing().layer("X").add(sphere((0,0,0), 1.0))` raises `SceneError`
      and is also a static type error (`Layer.add` is typed `Shape2D` only).
- [ ] `StlMesh().add(circle((0,0), 1.0))` raises `SceneError` and is also a
      static type error.
- [ ] `DxfDrawing()` after `d.layer("PLATE", 7); d.layer("HOLES", 1)` exposes
      `len(d.layers) == 2` and the two layers carry the colours given.
- [ ] `Layer.add(...)` returns the layer for chaining;
      `d.layer("PLATE", 7).add(line((0,0),(1,0))).add(line((1,0),(1,1)))`
      adds two entities to one layer in one expression.
- [ ] `StlMesh().add(prism((0,0,0),(2,2,1))).write(tmp/"x.stl")` chains and
      writes a non-empty file.

### Writers

- [ ] `dxf.write(tmp / "out.dxf")` produces a file that `ezdxf.readfile` opens
      without raising and that contains exactly the expected entity count by
      type (one CIRCLE, one LWPOLYLINE, one MTEXT for the smoke case).
- [ ] Round-tripped circle has centre and radius equal to the inputs to
      `pytest.approx(rel=1e-9)`.
- [ ] DXF golden file for the smoke case matches byte-for-byte; regenerate
      with `pytest --update-goldens`.
- [ ] Binary STL of `prism_2x2x1` is exactly `84 + 12*50 = 684` bytes.
- [ ] Reading the binary STL with `struct` finds 12 triangles, each with a
      unit-norm normal vector.
- [ ] ASCII STL of the same prism contains the literal token `solid` and ends
      with `endsolid`, with 12 `facet normal` blocks.

### Error model

- [ ] `pytest tests/errors/ -q` covers each tier (3 tests minimum: ValueError
      from geom, SceneError from scene, WriteError from writer).
- [ ] `WriteError` raised on a self-intersecting profile includes the offending
      polyline's first 3 points in its `str(e)`.

### Examples

- [ ] `python examples/plate_with_hole.py --out tmp/` produces both
      `tmp/plate.dxf` and `tmp/plate.stl`.
- [ ] The DXF, opened via `ezdxf`, has at least one LWPOLYLINE (or LINE
      segments composing the rectangle outline) and at least one CIRCLE.
- [ ] The STL parses with `struct` and is non-empty.
- [ ] `examples/plate_with_hole.py` uses lowercase factory functions and
      method-chained writers — verified by a grep test that asserts no
      `Polyline(`, `Circle(`, `Vec2(`, or `Vec3(` constructor calls appear
      in the example file (these belong only inside `cad/`).

### Quality gates

- [ ] `pytest -q` exits 0 with all tests passing.
- [ ] `pyright --strict src/cad` exits 0 with no errors and no warnings.
- [ ] `ruff check src/cad tests` exits 0.
- [ ] No file under `src/cad/` (excluding `_vendor`) imports from any external
      package other than the stdlib (verify with a `grep` script in tests).

## Known Limitations

Empty at spec-write time. The executing agent populates this during
implementation when an acceptance item cannot be satisfied after 2-3 distinct
approaches. An empty list at completion means everything passed.

## Post-Implementation Review

Empty at spec-write time. Filled by the executing agent as the final step
before claiming done.

### Acceptance results

(Re-state every acceptance item with verification evidence.)

### Scope drift

(List every change beyond the spec; justify or revert.)

### Refactor proposals

(Things noticed but not executed; include trigger conditions.)
