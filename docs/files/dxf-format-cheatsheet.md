# DXF Format Cheatsheet

Implementation notes for the current lightweight DXF facade. For public support
levels, see [File formats](index.md).

## File structure

```text
SECTION HEADER
SECTION TABLES
SECTION ENTITIES
EOF
```

The writer currently emits `HEADER`, `TABLES`, and `ENTITIES`. It targets
`AC1032` (AutoCAD R2018).

Each section is wrapped as:

```text
0
SECTION
2
NAME
...
0
ENDSEC
```

## Group codes used

| Code | Meaning |
|---|---|
| `0` | Entity type marker. |
| `1` | Text content. |
| `2` | Section/table/name value. |
| `6` | Linetype name. |
| `8` | Layer name. |
| `10`, `20`, `30` | Primary point coordinates. |
| `11`, `21`, `31` | Secondary point coordinates. |
| `12`, `22`, `32` | Third point coordinates for `3DFACE`. |
| `13`, `23`, `33` | Fourth point coordinates for `3DFACE`. |
| `40` | Radius, text height, or scale-like float. |
| `50`, `51` | Angles in degrees. |
| `62` | AutoCAD Color Index. |
| `70` | Integer flags. |
| `90` | Integer count. |

## Writer recipes

### Layer table

```text
0
TABLE
2
LAYER
70
<layer-count>
0
LAYER
2
PLATE
70
0
62
7
6
CONTINUOUS
0
ENDTAB
```

### LINE

```text
0
LINE
8
<layer>
10
x1
20
y1
11
x2
21
y2
```

### LWPOLYLINE

```text
0
LWPOLYLINE
8
<layer>
90
<vertex-count>
70
<1 if closed else 0>
10
x1
20
y1
...
```

### CIRCLE

```text
0
CIRCLE
8
<layer>
10
cx
20
cy
40
radius
```

### ARC

```text
0
ARC
8
<layer>
10
cx
20
cy
40
radius
50
start_angle_degrees
51
end_angle_degrees
```

### TEXT

```text
0
TEXT
8
<layer>
10
x
20
y
40
height
1
text
```

## Reader notes

The parser walks entity chunks in the `ENTITIES` section.

Supported 2D entities:

- `LINE` -> `Line2`
- `LWPOLYLINE` -> `Polyline2` with `closed` set from DXF flags
- `CIRCLE` -> `Circle2`
- `ARC` -> `Arc2`
- `TEXT` / `MTEXT` -> `Text2`

Supported 3D imports:

- `3DFACE` -> `Mesh3`
- 3D `POLYLINE` vertex sequences -> wire tuples of `(x, y, z)` coordinates

Unsupported ACIS-backed entities such as `3DSOLID`, `BODY`, `REGION`, and
`SURFACE` are returned as skipped records. The parser does not attempt to
decode embedded ACIS/SAT payloads.

## 3DFACE

```text
0
3DFACE
8
<layer>
10
x1
20
y1
30
z1
11
x2
21
y2
31
z2
12
x3
22
y3
32
z3
13
x4
23
y4
33
z4
```

If the fourth point repeats the third point, the face is treated as a triangle.
Otherwise the quad is triangulated deterministically.

## 3D POLYLINE

```text
0
POLYLINE
8
<layer>
66
1
0
VERTEX
10
x
20
y
30
z
0
SEQEND
```

The reader returns supported wires as `tuple[tuple[float, float, float], ...]` values in
`DxfImportResult.wires`.

## Units and versions

The current writer does not emit `$INSUNITS`; callers should manage units at
the drawing/document level. When unit metadata is added to DXF output, common
values are:

- `1`: inches
- `4`: millimetres
- `6`: metres

DXF version codes:

| Code | Version |
|---|---|
| `AC1015` | R2000 |
| `AC1024` | R2010 |
| `AC1027` | R2013 |
| `AC1032` | R2018 |

Use `AC1032` for new output unless a compatibility requirement says otherwise.
