# STEP Format Cheatsheet

Implementation notes for the current STEP facade. For public support levels,
see [File formats](index.md).

## Current writer

The current writer emits a minimal ISO-10303-21 text file from evaluated mesh
geometry:

```text
ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('cady mesh export'),'2;1');
FILE_NAME('cady.step','',('cady'),('cady'),'cady','cady','');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN_CC2'));
ENDSEC;
DATA;
#1=CARTESIAN_POINT('',(...));
#2=CARTESIAN_POINT('',(...));
#3=CARTESIAN_POINT('',(...));
#4=POLY_LOOP('',(#1,#2,#3));
ENDSEC;
END-ISO-10303-21;
```

It is not a full B-rep writer. It does not currently emit product structure,
closed shells, advanced faces, edge curves, or `MANIFOLD_SOLID_BREP` records.

## File structure

```text
ISO-10303-21;
HEADER;
...header entities...
ENDSEC;
DATA;
...numbered entities...
ENDSEC;
END-ISO-10303-21;
```

Each entity line ends with `;`. Entity references use `#<integer>`.

## Mesh export mapping

The facade first resolves a mesh:

```text
Mesh3D                -> Mesh3D
ArrayMesh3            -> Mesh3D.from_array(...)
Body3D                -> Body3D.to_mesh(tolerance=...)
Part                  -> Part.to_mesh(tolerance=...)
Assembly              -> Assembly.to_mesh(tolerance=...)
Document              -> merged meshable parts and assemblies
```

Then it writes:

- one `CARTESIAN_POINT` per mesh vertex;
- one `POLY_LOOP` per triangular face, referencing the three vertex IDs.

The writer rejects empty meshes.

## Reader helpers

Read support lives in `cady.files.step.faces` and
`cady.files.step.members`, re-exported through `cady.files.step`:

```python
faces = step.read_faces("member.step")
members = step.read_members("member.step")
```

The reader is analysis-oriented. It extracts elementary surfaces and simple
extruded-member candidates where enough information is present. It does not
reconstruct arbitrary STEP product trees or editable cady bodies.

## B-rep reference graph

If cady later grows a true STEP solid writer, a typical AP214/AP242 B-rep graph
will need this shape:

```text
PRODUCT
  PRODUCT_DEFINITION_FORMATION
    PRODUCT_DEFINITION
      ADVANCED_BREP_SHAPE_REPRESENTATION
        MANIFOLD_SOLID_BREP
          CLOSED_SHELL
            ADVANCED_FACE
              PLANE / CYLINDRICAL_SURFACE / ...
              FACE_BOUND
                EDGE_LOOP
                  ORIENTED_EDGE
                    EDGE_CURVE
                      VERTEX_POINT
                      LINE / CIRCLE / ...
```

That is a different implementation path from the current mesh-oriented writer.

## Validation

For writer changes, check:

- the generated file is valid ASCII text ending in `END-ISO-10303-21;`;
- every `POLY_LOOP` references existing point IDs;
- mesh targets produce non-empty vertices and faces;
- a STEP viewer or CAD tool can load the generated file, if the target tool is
  known.

For reader changes, keep fixtures small and assert both the parsed face/member
data and the skipped/unsupported behavior.
