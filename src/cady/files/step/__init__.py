from __future__ import annotations

from pathlib import Path

from cady.domain.model import Model
from cady.files.step.document import render_step
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

read_step_faces = read_step


def write_model(model: Model, path: str | Path) -> Model:
    return model.write_step(Path(path))


def read_faces(path: str | Path) -> list[StepFace]:
    return read_step(path)


def read_members(path: str | Path) -> list[ExtrudedMember]:
    return extract_members_from_faces(read_faces(path))

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
    "render_step",
    "write_model",
]
