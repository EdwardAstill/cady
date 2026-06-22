from __future__ import annotations

from cady import Model, prism
from cady.files import step

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


def test_write_model_creates_step_file(tmp_path) -> None:
    path = tmp_path / "model.step"
    model = Model("demo")
    model.part("plate").add(prism((0, 0, 0), (1, 0.5, 0.01)))

    assert step.write_model(model, path) is model
    assert "MANIFOLD_SOLID_BREP" in path.read_text(encoding="ascii")


def test_read_faces_names_step_return_target(tmp_path) -> None:
    path = tmp_path / "cylinder.step"
    path.write_text(MINIMAL_CYLINDER_STEP, encoding="ascii")

    faces = step.read_faces(path)

    assert len(faces) == 1
    assert faces[0].surface_type == "cylinder"


def test_read_members_names_step_return_target(tmp_path) -> None:
    path = tmp_path / "cylinder.step"
    path.write_text(MINIMAL_CYLINDER_STEP, encoding="ascii")

    members = step.read_members(path)

    assert len(members) == 1
    assert members[0].section.section_type == "tubular"


def test_step_facade_has_no_vague_read_function() -> None:
    assert not hasattr(step, "read")
