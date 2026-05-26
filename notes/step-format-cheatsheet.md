# STEP (ISO 10303-21) cheatsheet

Working notes for the future STEP writer. Pulled from ISO 10303-21
spec + reverse-engineered from CadQuery/build123d STEP output.

## File structure

```
ISO-10303-21;
HEADER;
…header entities…
ENDSEC;
DATA;
…data entities, each with #N = TYPE(...) ;
ENDSEC;
END-ISO-10303-21;
```

Each line ends with `;`. Whitespace is significant only inside string
literals. Strings use single quotes; doubled quotes escape.

## Minimal HEADER

```
HEADER;
FILE_DESCRIPTION (('cady export'), '2;1');
FILE_NAME (
  'padeye.step',
  '2026-05-08T14:30:00',
  ('cady'),
  ('pyseas'),
  'cady v0.0.1',
  '',
  ''
);
FILE_SCHEMA (('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));
ENDSEC;
```

Schema string above is AP214; AP242 is `AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF`.

## Minimal DATA — a tetrahedron MANIFOLD_SOLID_BREP

The smallest non-trivial solid. Walk-through:

```
#1 = APPLICATION_PROTOCOL_DEFINITION('international standard',
       'automotive_design', 2010, #2);
#2 = APPLICATION_CONTEXT('core data for automotive mechanical design processes');

#10 = CARTESIAN_POINT('', (0., 0., 0.));
#11 = CARTESIAN_POINT('', (1., 0., 0.));
#12 = CARTESIAN_POINT('', (0., 1., 0.));
#13 = CARTESIAN_POINT('', (0., 0., 1.));

#20 = VERTEX_POINT('', #10);
#21 = VERTEX_POINT('', #11);
#22 = VERTEX_POINT('', #12);
#23 = VERTEX_POINT('', #13);

… (DIRECTION, AXIS2_PLACEMENT_3D, LINE, EDGE_CURVE, ORIENTED_EDGE,
     EDGE_LOOP, FACE_BOUND, ADVANCED_FACE …)

#100 = CLOSED_SHELL('', (#face1, #face2, #face3, #face4));
#101 = MANIFOLD_SOLID_BREP('padeye', #100);

#200 = ADVANCED_BREP_SHAPE_REPRESENTATION(
         'padeye', (#101, #axis_origin), #shape_context);

#300 = PRODUCT('padeye', 'padeye', '', (#context));
#301 = PRODUCT_DEFINITION_FORMATION('', '', #300);
#302 = PRODUCT_DEFINITION('design', '', #301, #def_context);
```

Yes, every vertex/edge/face is its own numbered entity. A simple cube
is ~50 entities. A padeye-with-hole could easily be 200+.

## Entity reference graph

```
PRODUCT
  └─ PRODUCT_DEFINITION_FORMATION
       └─ PRODUCT_DEFINITION
            └─ ADVANCED_BREP_SHAPE_REPRESENTATION
                 └─ MANIFOLD_SOLID_BREP
                      └─ CLOSED_SHELL
                           └─ ADVANCED_FACE × n
                                ├─ surface (PLANE / CYLINDRICAL_SURFACE)
                                └─ FACE_BOUND
                                     └─ EDGE_LOOP
                                          └─ ORIENTED_EDGE × n
                                               └─ EDGE_CURVE
                                                    ├─ VERTEX_POINT × 2
                                                    └─ curve (LINE / CIRCLE)
```

## What we need for pyseas-yard primitives

For a padeye main plate (extruded disk with cylindrical hole) the BREP is:

- 2 flat circular annular faces (top, bottom) — each is a PLANE bounded
  by 2 EDGE_CURVE circles (outer + inner).
- 1 outer cylindrical face — CYLINDRICAL_SURFACE bounded by 2 circle
  edges.
- 1 inner cylindrical face (the pin hole) — same.

Total: 4 faces, 4 circle edges, 8 vertices. Plus the wrapping nodes
(SHAPE_REPRESENTATION, PRODUCT, etc).

That's the simplest solid pyseas-yard would emit. Keep this case as
the v1 acceptance test.

## Shortcuts

- All numeric values are floats. Integer-looking values still need a
  decimal point: write `0.` not `0`.
- All entity arrays use parentheses: `(#1, #2, #3)`.
- Empty strings for the optional `name` field: `''`.
- The `'' (...)` constructor pattern is universal.
- Reference IDs can be sparse — `#10`, `#100`, `#1000` are fine.

## Boolean operations — the wall

Computing the BREP topology of `solid_a − solid_b` (e.g., plate minus
hole) requires:

1. Compute intersection curves of each face pair.
2. Split faces along intersection curves.
3. Classify resulting face fragments as inside / outside the other solid.
4. Stitch retained fragments into a new closed shell.

This is a real CAD-kernel feature. OpenCascade has 30 years of edge-case
fixes for this; rolling our own is naive.

**Workaround:** for a padeye, we don't have to do the boolean. The
final topology is computable by hand: 4 faces, the inner cylinder is
its own face. So we can author the post-cut BREP directly. This works
for any primitive whose post-boolean topology is fixed and simple.

That covers ~all of pyseas-yard's parts. If we ever need genuinely
arbitrary booleans, that's the point to delegate to CadQuery/OCP.

## Validation

Any STEP file we write should be checked with:

- An online STEP viewer (e.g., https://stepviewer.com).
- FreeCAD Open File (loose checking).
- ChannelDispatcher's stepcode validator if available.

Validation matters because broken STEP files often *open* in viewers
but with subtle topology errors.

## References

- ISO 10303-21:2016 specification (paywalled but findable).
- Free reference implementation surveys: https://github.com/stepcode/stepcode
- A clear walkthrough by William Adams:
  https://williamadams.org/stepfiles.html (general explainer; use as
  starting point only — cady will need the AP242 spec for new
  code).
- CadQuery example outputs: open any `*.step` file CadQuery writes
  and read it as plain text; the output is excellent reference.
