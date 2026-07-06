"""Ready-made Mesh3 examples."""

from __future__ import annotations

from math import atan2, sqrt

from cady import Mesh3

Point3 = tuple[float, float, float]
Face = tuple[int, ...]
Edge = tuple[int, int]


def _face_edges(faces: tuple[Face, ...]) -> tuple[Edge, ...]:
    edges: set[Edge] = set()
    for face in faces:
        for start, end in zip(face, face[1:] + face[:1], strict=True):
            edges.add((min(start, end), max(start, end)))
    return tuple(sorted(edges))


def _mesh(vertices: tuple[Point3, ...], faces: tuple[Face, ...]) -> Mesh3:
    return Mesh3(vertices, faces, _face_edges(faces))


CUBE = _mesh(
    (
        (-1.0, -1.0, -1.0),
        (1.0, -1.0, -1.0),
        (1.0, 1.0, -1.0),
        (-1.0, 1.0, -1.0),
        (-1.0, -1.0, 1.0),
        (1.0, -1.0, 1.0),
        (1.0, 1.0, 1.0),
        (-1.0, 1.0, 1.0),
    ),
    (
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    ),
)

TRAPEZOID_PRISM = _mesh(
    (
        (-1.6, -0.9, -0.6),
        (1.6, -0.9, -0.6),
        (0.9, 0.9, -0.6),
        (-0.9, 0.9, -0.6),
        (-1.1, -0.65, 0.6),
        (1.1, -0.65, 0.6),
        (0.55, 0.65, 0.6),
        (-0.55, 0.65, 0.6),
    ),
    (
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    ),
)

PYRAMID = _mesh(
    (
        (-1.2, -1.2, 0.0),
        (1.2, -1.2, 0.0),
        (1.2, 1.2, 0.0),
        (-1.2, 1.2, 0.0),
        (0.0, 0.0, 1.8),
    ),
    (
        (0, 3, 2, 1),
        (0, 1, 4),
        (1, 2, 4),
        (2, 3, 4),
        (3, 0, 4),
    ),
)

OCTAHEDRON = _mesh(
    (
        (1.3, 0.0, 0.0),
        (-1.3, 0.0, 0.0),
        (0.0, 1.3, 0.0),
        (0.0, -1.3, 0.0),
        (0.0, 0.0, 1.3),
        (0.0, 0.0, -1.3),
    ),
    (
        (0, 2, 4),
        (2, 1, 4),
        (1, 3, 4),
        (3, 0, 4),
        (2, 0, 5),
        (1, 2, 5),
        (3, 1, 5),
        (0, 3, 5),
    ),
)

TRIANGULAR_PRISM = _mesh(
    (
        (-1.2, -0.8, -0.7),
        (1.2, -0.8, -0.7),
        (0.0, 1.0, -0.7),
        (-1.2, -0.8, 0.7),
        (1.2, -0.8, 0.7),
        (0.0, 1.0, 0.7),
    ),
    (
        (0, 2, 1),
        (3, 4, 5),
        (0, 1, 4, 3),
        (1, 2, 5, 4),
        (2, 0, 3, 5),
    ),
)


def _dodecahedron() -> Mesh3:
    phi = (1.0 + sqrt(5.0)) / 2.0
    ico_vertices: tuple[Point3, ...] = (
        (-1.0, phi, 0.0),
        (1.0, phi, 0.0),
        (-1.0, -phi, 0.0),
        (1.0, -phi, 0.0),
        (0.0, -1.0, phi),
        (0.0, 1.0, phi),
        (0.0, -1.0, -phi),
        (0.0, 1.0, -phi),
        (phi, 0.0, -1.0),
        (phi, 0.0, 1.0),
        (-phi, 0.0, -1.0),
        (-phi, 0.0, 1.0),
    )
    ico_faces = (
        (0, 11, 5),
        (0, 5, 1),
        (0, 1, 7),
        (0, 7, 10),
        (0, 10, 11),
        (1, 5, 9),
        (5, 11, 4),
        (11, 10, 2),
        (10, 7, 6),
        (7, 1, 8),
        (3, 9, 4),
        (3, 4, 2),
        (3, 2, 6),
        (3, 6, 8),
        (3, 8, 9),
        (4, 9, 5),
        (2, 4, 11),
        (6, 2, 10),
        (8, 6, 7),
        (9, 8, 1),
    )
    vertices = tuple(
        _normalised(_centroid(tuple(ico_vertices[i] for i in face)))
        for face in ico_faces
    )
    faces: list[Face] = []
    for vertex_index, vertex in enumerate(ico_vertices):
        adjacent = [index for index, face in enumerate(ico_faces) if vertex_index in face]
        normal = _normalised(vertex)
        axis_x = _normalised(_subtract(vertices[adjacent[0]], normal))
        axis_y = _cross(normal, axis_x)
        faces.append(
            tuple(
                sorted(
                    adjacent,
                    key=lambda index: atan2(
                        _dot(vertices[index], axis_y),
                        _dot(vertices[index], axis_x),
                    ),
                )
            )
        )
    return _mesh(vertices, tuple(faces))


def _centroid(points: tuple[Point3, ...]) -> Point3:
    count = float(len(points))
    return (
        sum(point[0] for point in points) / count,
        sum(point[1] for point in points) / count,
        sum(point[2] for point in points) / count,
    )


def _normalised(point: Point3) -> Point3:
    length = sqrt(_dot(point, point))
    return (point[0] / length, point[1] / length, point[2] / length)


def _subtract(a: Point3, b: Point3) -> Point3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Point3, b: Point3) -> Point3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


DODECAHEDRON = _dodecahedron()

MESHES = {
    "cube": CUBE,
    "dodecahedron": DODECAHEDRON,
    "trapezoid_prism": TRAPEZOID_PRISM,
    "pyramid": PYRAMID,
    "octahedron": OCTAHEDRON,
    "triangular_prism": TRIANGULAR_PRISM,
}


def main() -> None:
    for name, mesh in MESHES.items():
        print(f"{name}: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")


if __name__ == "__main__":
    main()
