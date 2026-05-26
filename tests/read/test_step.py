"""Tests for cady.read.step — pure-Python STEP reader."""

from __future__ import annotations

from cady.read.step import read_step

# ---------------------------------------------------------------------------
# A minimal valid STEP file with one cylindrical surface
# ---------------------------------------------------------------------------

MINIMAL_CYLINDER_STEP = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('Minimal cylinder test'),'2;1');
FILE_NAME('test.stp','2026-01-01',('author'),('org'),'preprocessor','system');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;
DATA;
#1=CARTESIAN_POINT('',(0.0,0.0,0.0));
#2=DIRECTION('',(0.0,0.0,1.0));
#3=DIRECTION('',(1.0,0.0,0.0));
#4=AXIS2_PLACEMENT_3D('',#1,#2,#3);
#5=CYLINDRICAL_SURFACE('',#4,0.15);
#6=CARTESIAN_POINT('',(0.0,0.15,50.0));
#7=VECTOR('',#2,50.0);
#8=LINE('',#1,#7);
#9=CIRCLE('',#4,0.15);
#10=EDGE_CURVE('',#8,#9,#6);
#11=ORIENTED_EDGE('',*,*,#10,.T.);
#12=EDGE_LOOP('',(#11));
#13=FACE_OUTER_BOUND('',#12,.T.);
#14=ADVANCED_FACE('',(#13),#5,.T.);
#15=CLOSED_SHELL('',(#14));
#16=MANIFOLD_SOLID_BREP('',#15);
ENDSEC;
END-ISO-10303-21;
"""

# A STEP file with one planar face
MINIMAL_PLANE_STEP = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('Minimal plane test'),'2;1');
FILE_NAME('test.stp','2026-01-01',('author'),('org'),'preprocessor','system');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;
DATA;
#1=CARTESIAN_POINT('',(0.0,0.0,0.0));
#2=DIRECTION('',(0.0,0.0,1.0));
#3=DIRECTION('',(1.0,0.0,0.0));
#4=AXIS2_PLACEMENT_3D('',#1,#2,#3);
#5=PLANE('',#4);
#6=CARTESIAN_POINT('',(10.0,0.0,0.0));
#7=CARTESIAN_POINT('',(10.0,10.0,0.0));
#10=CARTESIAN_POINT('',(0.0,0.0,0.0));
#11=CARTESIAN_POINT('',(0.0,10.0,0.0));
#12=VERTEX_POINT('',#6);
#13=VERTEX_POINT('',#7);
#14=VERTEX_POINT('',#10);
#15=VERTEX_POINT('',#11);
#16=LINE('',#1,#1);
#17=LINE('',#1,#1);
#18=LINE('',#1,#1);
#19=LINE('',#1,#1);
#20=EDGE_CURVE('',#12,#13,#6,.T.);
#21=EDGE_CURVE('',#13,#14,#7,.T.);
#22=EDGE_CURVE('',#14,#15,#10,.T.);
#23=EDGE_CURVE('',#15,#12,#11,.T.);
#24=ORIENTED_EDGE('',*,*,#20,.T.);
#25=ORIENTED_EDGE('',*,*,#21,.T.);
#26=ORIENTED_EDGE('',*,*,#22,.T.);
#27=ORIENTED_EDGE('',*,*,#23,.T.);
#28=EDGE_LOOP('',(#24,#25,#26,#27));
#29=FACE_OUTER_BOUND('',#28,.T.);
#30=ADVANCED_FACE('',(#29),#5,.T.);
#31=CLOSED_SHELL('',(#30));
#32=MANIFOLD_SOLID_BREP('',#31);
ENDSEC;
END-ISO-10303-21;
"""


class TestReadCylinder:
    def test_reads_cylindrical_face(self, tmp_path):
        p = tmp_path / "cylinder.stp"
        p.write_text(MINIMAL_CYLINDER_STEP)
        faces = read_step(str(p))
        assert len(faces) == 1
        assert faces[0].surface_type == "cylinder"

    def test_extracts_cylinder_radius(self, tmp_path):
        p = tmp_path / "cylinder.stp"
        p.write_text(MINIMAL_CYLINDER_STEP)
        faces = read_step(str(p))
        assert faces[0].cylinder_radius == 0.15

    def test_extracts_cylinder_axis(self, tmp_path):
        p = tmp_path / "cylinder.stp"
        p.write_text(MINIMAL_CYLINDER_STEP)
        faces = read_step(str(p))
        axis = faces[0].cylinder_axis
        assert axis is not None
        # Axis should be (0, 0, 1) — the Z direction
        assert abs(axis[0]) < 1e-6
        assert abs(axis[1]) < 1e-6
        assert abs(axis[2] - 1.0) < 1e-6


class TestReadPlane:
    def test_reads_planar_face(self, tmp_path):
        p = tmp_path / "plane.stp"
        p.write_text(MINIMAL_PLANE_STEP)
        faces = read_step(str(p))
        assert len(faces) == 1
        assert faces[0].surface_type == "plane"

    def test_extracts_plane_normal(self, tmp_path):
        p = tmp_path / "plane.stp"
        p.write_text(MINIMAL_PLANE_STEP)
        faces = read_step(str(p))
        normal = faces[0].normal
        assert normal is not None
        # Normal should be (0, 0, 1) — Z direction
        assert abs(normal[0]) < 1e-6
        assert abs(normal[1]) < 1e-6
        assert abs(normal[2] - 1.0) < 1e-6

    def test_extracts_centroid(self, tmp_path):
        p = tmp_path / "plane.stp"
        p.write_text(MINIMAL_PLANE_STEP)
        faces = read_step(str(p))
        c = faces[0].centroid
        # Centroid of a 10x10 square at z=0 should be near (5, 5, 0)
        assert abs(c[0] - 5.0) < 1.0
        assert abs(c[1] - 5.0) < 1.0
        assert abs(c[2]) < 0.01


class TestReadEmpty:
    def test_empty_file(self, tmp_path):
        p = tmp_path / "empty.stp"
        p.write_text("ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n")
        faces = read_step(str(p))
        assert faces == []

    def test_no_advanced_faces(self, tmp_path):
        p = tmp_path / "noface.stp"
        p.write_text("""ISO-10303-21;
HEADER;FILE_DESCRIPTION(('test'),'2;1');FILE_NAME('t','2026',('a'),('o'),'p','s');FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));ENDSEC;
DATA;
#1=CARTESIAN_POINT('',(0.0,0.0,0.0));
ENDSEC;END-ISO-10303-21;""")
        faces = read_step(str(p))
        assert faces == []
