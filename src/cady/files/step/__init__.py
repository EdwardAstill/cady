from __future__ import annotations

from pathlib import Path

from cady.document import Document
from cady.errors import WriteError
from cady.files.step.faces import StepFace, read_step
from cady.files.step.ids import IdAllocator
from cady.files.step.members import (
    ExtrudedMember,
    ExtrudedSection,
    classify_section_from_faces,
    extract_members_from_faces,
    find_end_caps,
    group_cylinders_into_members,
)
from cady.geometry3d import Mesh3D
from cady.numeric.mesh3d import ArrayMesh3

read_step_faces = read_step


def render(target: object, *, tolerance: float = 1e-3) -> str:
    mesh = _mesh_from_target(target, tolerance=tolerance)
    if not mesh.faces:
        raise WriteError("cannot write empty STEP mesh")
    lines = [
        "ISO-10303-21;",
        "HEADER;",
        "FILE_DESCRIPTION(('cady mesh export'),'2;1');",
        "FILE_NAME('cady.step','',('cady'),('cady'),'cady','cady','');",
        "FILE_SCHEMA(('AUTOMOTIVE_DESIGN_CC2'));",
        "ENDSEC;",
        "DATA;",
    ]
    next_id = 1
    vertex_ids: list[int] = []
    for vertex in mesh.vertices:
        vertex_id = next_id
        next_id += 1
        vertex_ids.append(vertex_id)
        lines.append(
            f"#{vertex_id}=CARTESIAN_POINT('',({vertex.x:.12g},{vertex.y:.12g},{vertex.z:.12g}));"
        )
    for a, b, c in mesh.faces:
        face_id = next_id
        next_id += 1
        lines.append(f"#{face_id}=POLY_LOOP('',(#{vertex_ids[a]},#{vertex_ids[b]},#{vertex_ids[c]}));")
    lines.extend(["ENDSEC;", "END-ISO-10303-21;"])
    return "\n".join(lines) + "\n"


def write(target: object, path: str | Path, *, tolerance: float = 1e-3) -> object:
    Path(path).write_text(render(target, tolerance=tolerance), encoding="ascii")
    return target


def read_faces(path: str | Path) -> list[StepFace]:
    return read_step(path)


def read_members(path: str | Path) -> list[ExtrudedMember]:
    return extract_members_from_faces(read_faces(path))


def _mesh_from_target(target: object, *, tolerance: float) -> Mesh3D:
    if tolerance <= 0:
        raise WriteError("tolerance must be positive")
    if isinstance(target, Mesh3D):
        return target
    if isinstance(target, ArrayMesh3):
        return Mesh3D.from_array(target)
    if isinstance(target, Document):
        meshes: list[Mesh3D] = []
        for item in (*target.parts, *target.assemblies):
            meshes.append(_mesh_from_target(item.value, tolerance=tolerance))
        if not meshes:
            raise WriteError("document contains no meshable parts or assemblies")
        return Mesh3D.merged(meshes)
    to_mesh = getattr(target, "to_mesh", None)
    if callable(to_mesh):
        mesh = to_mesh(tolerance=tolerance)
        if isinstance(mesh, Mesh3D):
            return mesh
        if isinstance(mesh, ArrayMesh3):
            return Mesh3D.from_array(mesh)
    raise WriteError(f"{type(target).__name__} is not meshable")


__all__ = [
    "ExtrudedMember",
    "ExtrudedSection",
    "IdAllocator",
    "StepFace",
    "classify_section_from_faces",
    "extract_members_from_faces",
    "find_end_caps",
    "group_cylinders_into_members",
    "read_faces",
    "read_members",
    "read_step",
    "read_step_faces",
    "render",
    "write",
]
