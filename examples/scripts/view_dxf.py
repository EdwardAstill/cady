from pathlib import Path

from cady.files import dxf

DXF_FILE = Path(__file__).resolve().parents[2] / "examples/inputs/example_mesh.dxf"


def view_format(
    mesh: bool = False,
    wireframe: bool = True,
) -> None:
    if mesh:
        dxf.view_mesh(DXF_FILE)
    if wireframe:
        dxf.read_wireframe(DXF_FILE).view()


if __name__ == "__main__":
    view_format()
