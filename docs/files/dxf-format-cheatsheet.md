# DXF format cheatsheet

Working notes for implementing the DXF writer. Pulled from Autodesk
DXF reference + ezdxf docs as crib sheet.

## File structure

```
SECTION HEADER     — system variables, version, units
SECTION CLASSES    — class definitions (R13+)
SECTION TABLES     — layer table, linetype table, dimstyle table, …
SECTION BLOCKS     — block definitions
SECTION ENTITIES   — drawn things (the main payload)
SECTION OBJECTS    — non-graphical objects (R13+)
EOF
```

Each section is wrapped with `0\nSECTION\n2\n<NAME>\n…\n0\nENDSEC`.

## Group codes (the ones we need)

| Code | Meaning |
|---|---|
| 0 | Entity type marker (LINE, CIRCLE, …) |
| 1 | Primary text (MTEXT content) |
| 2 | Name (block name, layer name, dimstyle name) |
| 5 | Handle (hex string, unique) |
| 6 | Linetype name |
| 8 | Layer name |
| 10, 20, 30 | X, Y, Z of primary point |
| 11, 21, 31 | X, Y, Z of secondary point (e.g., LINE end) |
| 39 | Thickness (extrusion) |
| 40 | Float — radius, height, scale |
| 41, 42, 43 | More floats — varies by entity |
| 50, 51 | Angles (degrees) |
| 62 | Color number (ACI 0–256) |
| 70 | Integer flags |
| 90 | Integer count |
| 100 | Subclass marker (`AcDbEntity`, `AcDbCircle`, etc.) |
| 1000 | Extended data (ASCII) |

## Minimum HEADER section

```
0\nSECTION\n2\nHEADER\n
9\n$ACADVER\n1\nAC1027\n        <- R2013, AC1032 = R2018
9\n$INSUNITS\n70\n4\n            <- 4 = millimetres, 6 = metres
9\n$EXTMIN\n10\n0\n20\n0\n30\n0\n
9\n$EXTMAX\n10\n1\n20\n1\n30\n0\n
0\nENDSEC\n
```

## Minimum TABLES section (layer table)

```
0\nSECTION\n2\nTABLES\n
0\nTABLE\n2\nLAYER\n70\n1\n
0\nLAYER\n2\nPLATE\n70\n0\n62\n7\n6\nCONTINUOUS\n
0\nENDTAB\n
0\nENDSEC\n
```

## Minimum ENTITIES section (a circle)

```
0\nSECTION\n2\nENTITIES\n
0\nCIRCLE\n8\nPLATE\n10\n0.0\n20\n0.0\n30\n0.0\n40\n0.025\n
0\nENDSEC\n
0\nEOF\n
```

## Entities by group code recipe

### LINE
```
0   LINE
8   <layer>
10  x1
20  y1
30  z1
11  x2
21  y2
31  z2
```

### LWPOLYLINE
```
0   LWPOLYLINE
8   <layer>
90  <vertex count>
70  <flags: 1=closed>
10  x1
20  y1
10  x2
20  y2
…
```

### CIRCLE
```
0   CIRCLE
8   <layer>
10  cx
20  cy
30  cz
40  radius
```

### ARC
```
0   ARC
8   <layer>
10  cx
20  cy
30  cz
40  radius
50  start_angle (deg)
51  end_angle (deg)
```

### MTEXT
```
0   MTEXT
8   <layer>
10  ix
20  iy
30  iz
40  height
1   <text>
```

### HATCH
Complex — needs boundary path data. Defer to stage 2.

### DIMENSION
Complex — needs an associated BLOCK with the rendered geometry.
Defer to stage 3.

### 3DFACE
```
0   3DFACE
8   <layer>
10  x1
20  y1
30  z1
11  x2
21  y2
31  z2
12  x3
22  y3
32  z3
13  x4
23  y4
33  z4
```

`3DFACE` is an evaluated face, not a semantic solid. cady imports triangles
and quads into `FacetedMesh`; if the fourth point repeats the third point, the
face is treated as a triangle.

### Polyface POLYLINE
```
0   POLYLINE
70  <flags: 64=polyface mesh>
0   VERTEX          <- coordinate record
70  64
10  x
20  y
30  z
0   VERTEX          <- face record
70  128
71  v1
72  v2
73  v3
74  v4
0   SEQEND
```

Face indices are 1-based; negative indices mark invisible edges. cady imports
the absolute values and triangulates quad face records deterministically.

### 3D POLYLINE
```
0   POLYLINE
70  <flags: 8=3D polyline, 1=closed>
0   VERTEX
10  x
20  y
30  z
0   SEQEND
```

3D wire polylines import as `Polyline3D` via `dxf.read_3d(...)`.

### ACIS-backed 3D entities

`3DSOLID`, `BODY`, `REGION`, and `SURFACE` commonly store embedded ACIS/SAT
payloads. cady reports these as skipped import records instead of pretending
ordinary DXF group-code parsing can reconstruct the solid.

## Coordinate handedness

DXF uses a right-handed coordinate system: +X right, +Y up, +Z out of
the page. Engineering drawings are in the XY plane; Z=0 throughout.

## Units

`$INSUNITS` controls interpretation:
- 1 = inches
- 4 = mm
- 6 = m

pyseas-yard works in metres internally. Emit metres (6) and let the
viewer convert if needed.

## Version targets

| Code | Version | Notes |
|---|---|---|
| AC1009 | R12 | Smallest spec; no LWPOLYLINE, no MTEXT |
| AC1012 | R13 | Adds LWPOLYLINE, MTEXT, BLOCK_RECORD |
| AC1015 | R2000 | Most legacy CAD reads this |
| AC1018 | R2004 | Fine for modern CAD |
| AC1024 | R2010 | Default for many tools |
| AC1027 | R2013 | Recent and widely supported |
| AC1032 | R2018 | Current |

**Recommendation:** target R2018 (AC1032) for new files; offer R2000
(AC1015) fallback for legacy compatibility if asked.

## References

- Autodesk DXF Reference (any version):
  https://help.autodesk.com/view/OARX/2024/ENU/?guid=GUID-235B22E0-A567-4CF6-92D3-38A2306D73F3
- ezdxf source as a working implementation:
  https://github.com/mozman/ezdxf/tree/master/src/ezdxf/entities
- DXF comparison forum threads: many gotchas around DIMENSION blocks
  and MTEXT formatting codes.
