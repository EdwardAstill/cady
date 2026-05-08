# pyseas-cad — initial ideas

A pure-Python CAD writer library for 2D engineering drawings (DXF) and
3D solids (STEP), shaped for use by `pyseas-yard` and other pyseas-*
packages.

This document captures the rationale and a first-pass design. No code
yet — pyseas-yard will run on `ezdxf` for 2D in the meantime.

---

## Why DIY

Reasons to roll a custom writer instead of long-term `ezdxf` + an
imported STEP kernel:

- **Single dependency tree.** ezdxf brings numpy + fontTools + pyparsing.
  A pure-stdlib writer keeps pyseas-cad small and predictable.
- **Tighter integration with pyseas geometry.** pyseas-yard already
  models padeye, shackle, sling, weld, bolt-group as typed dataclasses.
  A native writer can consume those domain types directly without an
  intermediate "build a CadQuery workplane" step.
- **No GPL/LGPL footguns.** Distribute under MIT, no dynamic-linking
  questions.
- **Format ownership.** When a customer wants R2018-only or AP242-only,
  we control exactly what comes out. No upstream surprises.
- **Learning leverage.** DXF and STEP are file formats that pyseas
  authors should understand anyway.

Reasons to *not* DIY:

- DXF DIMENSION rendering is fiddly — different CAD viewers interpret
  dimension blocks differently. ezdxf already solved this.
- STEP (ISO 10303) is *enormous*. Even a minimal AP203 solid writer is
  weeks of work. Real ROI only if pyseas-cad becomes a long-term
  product.

**Strategy:** ezdxf in pyseas-yard now. Build pyseas-cad in parallel,
behind a feature flag. Switch pyseas-yard's draw backend over once the
custom writer reaches feature parity for the lifting-gear primitives.

---

## Scope — what pyseas-cad needs to draw

Driven by pyseas-yard's domain:

**2D primitives (DXF):**
- Line, polyline (open/closed), arc, circle, spline (rare).
- Layered output (hidden lines, weld lines, dimension lines, hatch,
  text, viewport).
- DIMENSION (linear, aligned, angular, radius/diameter).
- MTEXT for annotations.
- HATCH for cross-hatching welds and section views.
- INSERT (block reference) for shackles, bolt heads, weld symbols.

**3D primitives (STEP):**
- Extrusion of a 2D profile through a thickness (covers padeye plate,
  cheek plate, gusset, base).
- Revolution (covers shackle pins, bolt shanks, washers).
- Boolean cut (pin hole through plate).
- Translation / rotation / mirror.
- That's enough for ~all lifting-gear parts.
- Out of scope (initially): fillets, blends, swept profiles, NURBS
  surfaces.

**Outputs we want eventually:**
- DXF (R2018 baseline, R12 fallback for legacy CAD)
- STEP (AP242 baseline, AP203 fallback)
- STL (trivial — triangles only)
- SVG (trivial — XML)

---

## Architecture sketch

```
pyseas-cad/
  src/cad/
    geom/              # core geometry types
      vec.py           # Vec2, Vec3
      polyline.py
      arc.py
      circle.py
      surface.py       # extruded, revolved
      solid.py
    write/
      dxf/             # DXF writer
        document.py
        entities.py    # LINE, LWPOLYLINE, CIRCLE, ARC, MTEXT, HATCH, DIMENSION
        codes.py       # group code constants
        layers.py
      step/            # STEP writer (later)
        ap203.py       # minimal AP203 schema
        entities.py    # CARTESIAN_POINT, EDGE_CURVE, ADVANCED_FACE…
        header.py
      stl/             # trivial
      svg/             # trivial
    annotate/          # dimension placement helpers
      linear.py
      angular.py
      radial.py
    sheet/             # title-block and template support
      template.py
      titleblock.py
  tests/
  examples/
```

Each writer is independent of the others — no shared geometry kernel
needed beyond `geom/`. All output is text (DXF and STEP are ASCII; STL
has both; SVG is XML).

---

## DXF writer — detailed plan

### Wire format

DXF is **just structured ASCII**: a sequence of `(group code, value)`
pairs. The writer is a state machine that emits sections in order:

```
HEADER → TABLES → BLOCKS → ENTITIES → OBJECTS → EOF
```

### Minimum viable subset (pyseas-yard's needs)

| Entity | Group code family | Why we need it |
|---|---|---|
| LINE | 0=LINE, 10/20=start, 11/21=end | construction lines |
| LWPOLYLINE | 0=LWPOLYLINE, 90=count, 10/20*N=verts, 70=flags | plate outlines |
| CIRCLE | 0=CIRCLE, 10/20=centre, 40=r | pin hole, cheek plate |
| ARC | 0=ARC, 10/20=centre, 40=r, 50/51=start/end | rounded corners |
| MTEXT | 0=MTEXT, 1=text, 10/20=insertion, 40=height | annotations |
| HATCH | 0=HATCH + boundary path data | weld hatching |
| DIMENSION | 0=DIMENSION + complex block-driven | manufacturing dims |
| INSERT | 0=INSERT, 2=blockname, 10/20=insertion | reused symbols |

DIMENSION is the hardest entity — it points at a BLOCK that contains
the rendered geometry of the dimension lines, arrows, and text. We can
either (a) compute that block ourselves, or (b) emit "anonymous"
dimensions and let the CAD viewer regenerate them. AutoCAD-family
viewers regenerate; some lighter viewers don't. ezdxf computes them.

### API sketch

```python
from cad.write.dxf import DxfDocument, Layer

doc = DxfDocument()
plate = doc.layer("PLATE", color=7)
holes = doc.layer("HOLES", color=1)
dims = doc.layer("DIMS", color=3)

doc.lwpolyline([(0, 0), (0.3, 0), (0.3, 0.3), (0, 0.3), (0, 0)], layer=plate, closed=True)
doc.circle((0.15, 0.15), 0.025, layer=holes)
doc.linear_dim(start=(0, 0), end=(0.3, 0), offset=0.05, layer=dims)
doc.write("padeye.dxf")
```

The document type owns layers, blocks, dimstyles. Entities are emitted
into the ENTITIES section in insertion order. No deferred resolution
— each entity writes immediately to a string buffer.

### Open questions

- DIMENSION blocks: render ourselves or emit anonymous? Renders are
  ~30 lines of arrow-and-text math; doable.
- DXF version: lock to R2018? R12 has the smallest spec but lacks LWPOLYLINE.
- HATCH boundary patterns: ANSI31 (45° lines) covers weld hatching;
  full pattern lib is large.

---

## STEP writer — detailed plan (later)

### Wire format

STEP files (.stp / .step) are **ISO 10303-21** ASCII:

```
ISO-10303-21;
HEADER;
FILE_DESCRIPTION(...);
FILE_NAME(...);
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;
DATA;
#1 = APPLICATION_PROTOCOL_DEFINITION(...);
#2 = CARTESIAN_POINT('',(0., 0., 0.));
#3 = DIRECTION('',(1., 0., 0.));
…
ENDSEC;
END-ISO-10303-21;
```

Each entity has an integer ID (`#N`) and references other entities by
ID. The parser is straightforward; the *schema* is the hard part — the
chosen Application Protocol (AP203, AP214, AP242) defines which
entities are legal and how they compose.

### Minimum viable subset

For pyseas-yard's primitives we need only:

- `CARTESIAN_POINT`, `DIRECTION`, `VECTOR`
- `AXIS2_PLACEMENT_3D`
- `LINE`, `CIRCLE` (as 3D curves)
- `EDGE_CURVE`, `ORIENTED_EDGE`, `EDGE_LOOP`
- `FACE_BOUND`, `ADVANCED_FACE`, `PLANE`, `CYLINDRICAL_SURFACE`
- `MANIFOLD_SOLID_BREP`, `CLOSED_SHELL`
- `ADVANCED_BREP_SHAPE_REPRESENTATION`
- `PRODUCT`, `PRODUCT_DEFINITION`, `PRODUCT_DEFINITION_FORMATION`
- `APPLICATION_PROTOCOL_DEFINITION`, `APPLICATION_CONTEXT`

Maybe ~20 entity types. Enough to express:
- Box (extruded rectangle)
- Cylinder (extruded circle, or revolved rectangle)
- Boolean cut of cylinder from box (the padeye main plate with hole)

That's painful but bounded. AP242 is preferred over AP203 for new code
(and is what most modern CAD imports).

### API sketch

```python
from cad.geom import Vec3, Polygon
from cad.write.step import StepDocument

doc = StepDocument()
plate = doc.extrude(
    profile=Polygon.circle((0, 0), radius=0.3),
    direction=Vec3(0, 0, 1),
    distance=0.04,
)
hole = doc.extrude(
    profile=Polygon.circle((0, 0), radius=0.025),
    direction=Vec3(0, 0, 1),
    distance=0.04,
)
padeye = doc.boolean_cut(plate, hole)
doc.write("padeye.step")
```

**Boolean cut is the hard part.** Without an OpenCascade-equivalent
kernel, we'd have to compute the resulting B-rep topology ourselves —
that is real CAD-kernel territory (months of work). Cheaper option:
emit the two solids as separate `MANIFOLD_SOLID_BREP` instances and
let the receiving CAD do the boolean. CAD-side import handles that
fine for visual review; manufacturing CAM may not.

### Open questions

- Schema choice: AP203 (older, broad support) or AP242 (modern, harder).
- Boolean ops: skip them and emit pre-cut topology, or build a tiny
  CSG-on-mesh kernel and tessellate-then-stitch?
- Tolerance bands: STEP supports geometric tolerances (GD&T); skip for
  v1.

---

## STL and SVG writers

Both trivial. Defer until needed. ~50 lines each.

---

## Suggested staging

| Stage | Deliverable | Time est. |
|---|---|---|
| 0 | Use ezdxf in pyseas-yard for padeye/shackle 2D drawings | days |
| 1 | pyseas-cad scaffolded; DXF writer with LINE/LWPOLYLINE/CIRCLE/ARC | 1 week |
| 2 | DXF MTEXT, HATCH, INSERT (blocks) | 1 week |
| 3 | DXF DIMENSION (linear + radial); pyseas-yard switches to pyseas-cad for 2D | 2 weeks |
| 4 | STL writer (fast win, useful for 3D preview) | 2 days |
| 5 | STEP writer — basic extruded prisms, no booleans | 3–4 weeks |
| 6 | STEP writer — boolean cut via emitted "two solids, CAD does boolean" approach | 1 week |
| 7 | Optional: kernel-quality boolean / fillet | open-ended |

Stage 0–3 has the biggest leverage and is the realistic 2026 target.
Stage 5+ is "build vs. delegate to CadQuery/build123d" decision to
make later.

---

## Comparison with the alternatives

| Path | Effort | License | Annot. | STEP | Maintenance burden |
|---|---|---|---|---|---|
| **ezdxf only** (Tier 1) | ~zero | MIT (vendored) | full | none | external lib |
| **ezdxf + cadquery** (Tier 2) | small | Apache+MIT | manual via ezdxf | full | external libs |
| **pyseas-cad DXF only** (stages 1–3) | medium | MIT (own) | own DIMENSION | none | ours |
| **pyseas-cad DXF + STEP** (stages 1–6) | large | MIT (own) | own DIMENSION | own basic | ours, real |

The middle option (own DXF only) is interesting: most of pyseas-yard's
output value is 2D drawings, and STEP can stay on cadquery if we ever
need it. That's a reasonable long-term equilibrium.

---

## What lives where

- `pyseas-yard` — calculation library. Domain types (Padeye, Shackle…).
  Imports ezdxf today, eventually pyseas-cad.
- `pyseas-cad` — drawing-format writers. Format-aware, geometry-aware,
  domain-blind.
- Domain "how to draw a padeye" recipes live in `pyseas-yard`, using
  `pyseas-cad` primitives. pyseas-cad does not know what a padeye is.

This boundary is the single most important architecture call. Keep
pyseas-cad as a *generic CAD writer* — never let lifting-gear leak in.
