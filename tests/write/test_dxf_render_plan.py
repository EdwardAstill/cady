from __future__ import annotations

import re

from cady import DxfDrawing
from cady.write.dxf.plan import DxfRenderPlan, make_render_plan
from cady.write.dxf.sections import render_dxf


def test_make_render_plan_allocates_dimension_block_names() -> None:
    drawing = DxfDrawing()
    drawing.linear_dimension((0, 0), (1, 0), offset=0.1)
    drawing.aligned_dimension((0, 0), (1, 1), offset=0.1)

    plan = make_render_plan(drawing)

    assert isinstance(plan, DxfRenderPlan)
    assert len(plan.dimension_block_names) == 2
    assert plan.uses_dimstyle is True
    assert len(set(plan.dimension_block_names)) == 2


def test_render_plan_block_names_skip_existing_user_blocks() -> None:
    drawing = DxfDrawing()
    drawing.block("*D1")
    drawing.linear_dimension((0, 0), (1, 0), offset=0.1)

    plan = make_render_plan(drawing)

    assert "*D1" not in plan.dimension_block_names


def test_render_plan_uses_dimstyle_false_when_no_dimensions() -> None:
    drawing = DxfDrawing()
    from cady import circle

    drawing.layer("A").add(circle((0, 0), 1))
    plan = make_render_plan(drawing)

    assert plan.uses_dimstyle is False


def test_every_dimension_block_ref_exists_in_blocks_section() -> None:
    drawing = DxfDrawing()
    drawing.linear_dimension((0, 0), (1, 0), offset=0.1)
    drawing.aligned_dimension((0, 0), (1, 1), offset=0.2)
    drawing.radius_dimension((0.5, 0.5), 0.2)
    drawing.diameter_dimension((1.5, 0.5), 0.2)

    text = render_dxf(drawing)

    # Collect all block names defined in BLOCKS section
    blocks_section = re.search(
        r"0\nSECTION\n2\nBLOCKS\n(.*?)0\nENDSEC", text, re.DOTALL
    )
    assert blocks_section is not None
    block_names = set(re.findall(r"0\nBLOCK\n.*?2\n(\*D\d+)\n", blocks_section.group(1), re.DOTALL))

    # Collect all block refs from DIMENSION entities in ENTITIES section
    entities_section = re.search(
        r"0\nSECTION\n2\nENTITIES\n(.*?)0\nENDSEC", text, re.DOTALL
    )
    assert entities_section is not None
    dim_block_refs = set(
        re.findall(
            r"0\nDIMENSION\n.*?2\n(\*D\d+)\n",
            entities_section.group(1),
            re.DOTALL,
        )
    )

    assert dim_block_refs, "expected at least one DIMENSION entity"
    assert dim_block_refs <= block_names, (
        f"DIMENSION block refs {dim_block_refs - block_names} not in BLOCKS section"
    )
