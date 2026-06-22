from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from cady.domain.shapes3d import Extrusion, Prism
from cady.errors import WriteError
from cady.files.step.brep import extrusion_brep, prism_brep
from cady.files.step.ids import IdAllocator

if TYPE_CHECKING:
    from cady.domain.model import Part


_HEADER_TMPL = """\
ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('PySeas CAD'),'2;1');
FILE_NAME('{name}','{ts}',(''),(''),'','PySeas CAD','');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;
DATA;
"""

_FOOTER = "ENDSEC;\nEND-ISO-10303-21;\n"


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")


def render_step(parts: list[Part], model_name: str, *, timestamp: str | None = None) -> str:
    """Render an AP214 STEP file for the given parts.

    Each Part must contain only Prism solids. Any other Shape3D raises WriteError.
    Parts with no solids are skipped silently.
    Raises WriteError if no part has any supported solids.
    """
    ts = timestamp or _now_iso()
    ids = IdAllocator()

    app_ctx = ids.add(
        "APPLICATION_CONTEXT"
        "('core data for automotive mechanical design processes')"
    )
    ids.add(
        f"APPLICATION_PROTOCOL_DEFINITION"
        f"('international standard','automotive_design',2000,#{app_ctx})"
    )
    prod_ctx = ids.add(f"PRODUCT_CONTEXT('',#{app_ctx},'mechanical')")

    len_unit = ids.add("(LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT($,.METRE.))")
    angle_unit = ids.add("(NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.))")
    solid_angle_unit = ids.add("(NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT())")
    uncertainty = ids.add(
        f"UNCERTAINTY_MEASURE_WITH_UNIT"
        f"(LENGTH_MEASURE(1.E-6),#{len_unit},'distance accuracy value','')"
    )
    geom_ctx = ids.add(
        f"(GEOMETRIC_REPRESENTATION_CONTEXT(3)"
        f" GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{uncertainty}))"
        f" GLOBAL_UNIT_ASSIGNED_CONTEXT((#{len_unit},#{angle_unit},#{solid_angle_unit}))"
        f" REPRESENTATION_CONTEXT('',''))"
    )

    any_solid = False

    for part in parts:
        if not part.solids:
            continue

        solid_ids: list[int] = []
        for solid in part.solids:
            if isinstance(solid, Prism):
                solid_ids.append(prism_brep(ids, solid))
            elif isinstance(solid, Extrusion):
                solid_ids.append(extrusion_brep(ids, solid))
            else:
                raise WriteError(
                    f"STEP export does not support {type(solid).__name__}; "
                    f"only Prism and Extrusion are supported"
                )

        any_solid = True

        product = ids.add(
            f"PRODUCT('{part.name}','{part.name}','',(#{prod_ctx}))"
        )
        prod_form = ids.add(f"PRODUCT_DEFINITION_FORMATION('','',#{product})")
        pdc = ids.add(
            f"PRODUCT_DEFINITION_CONTEXT('part definition',#{app_ctx},'design')"
        )
        prod_def = ids.add(f"PRODUCT_DEFINITION('','',#{prod_form},#{pdc})")
        pds = ids.add(f"PRODUCT_DEFINITION_SHAPE('','',#{prod_def})")

        cp0 = ids.add("CARTESIAN_POINT('',(0.,0.,0.))")
        dz = ids.add("DIRECTION('',(0.,0.,1.))")
        dx = ids.add("DIRECTION('',(1.,0.,0.))")
        placement = ids.add(f"AXIS2_PLACEMENT_3D('',#{cp0},#{dz},#{dx})")

        solid_refs = ",".join(f"#{i}" for i in solid_ids)
        brep_rep = ids.add(
            f"ADVANCED_BREP_SHAPE_REPRESENTATION"
            f"('',(#{placement},{solid_refs}),#{geom_ctx})"
        )
        ids.add(f"SHAPE_DEFINITION_REPRESENTATION(#{pds},#{brep_rep})")

    if not any_solid:
        raise WriteError("no supported solids in any part; cannot write STEP file")

    header = _HEADER_TMPL.format(name=model_name, ts=ts)
    return header + ids.render_data() + "\n" + _FOOTER
