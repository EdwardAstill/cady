"""Tests for cady.files.step — structural member reconstruction from faces."""

from __future__ import annotations

from cady.files.step import (
    StepFace,
    classify_section_from_faces,
    extract_members_from_faces,
    find_end_caps,
    group_cylinders_into_members,
)

# ── Helpers ─────────────────────────────────────────────────────────────────


def _plane(centroid, normal, area=1.0):
    return StepFace(
        surface_type="plane",
        centroid=centroid,
        normal=normal,
        area=area,
        cylinder_axis=None,
        cylinder_radius=None,
        cone_apex=None,
        cone_axis=None,
        cone_semi_angle=None,
    )


def _cylinder(centroid, axis, radius=0.15, area=1.0):
    return StepFace(
        surface_type="cylinder",
        centroid=centroid,
        normal=None,
        area=area,
        cylinder_axis=axis,
        cylinder_radius=radius,
        cone_apex=None,
        cone_axis=None,
        cone_semi_angle=None,
    )


# ── find_end_caps ───────────────────────────────────────────────────────────


class TestFindEndCaps:
    def test_single_pair(self):
        """Two parallel planes with opposite normals and similar area → one pair."""
        cap_a = _plane((0, 0, 0), (0, 0, 1), area=1.0)
        cap_b = _plane((0, 0, 5), (0, 0, -1), area=1.0)
        pairs = find_end_caps([cap_a, cap_b])
        assert len(pairs) == 1

    def test_rejects_non_parallel(self):
        """Non-parallel planes are not paired."""
        cap_a = _plane((0, 0, 0), (0, 0, 1), area=1.0)
        cap_b = _plane((0, 0, 5), (1, 0, 0), area=1.0)
        pairs = find_end_caps([cap_a, cap_b])
        assert len(pairs) == 0

    def test_rejects_dissimilar_area(self):
        """Planes with very different areas are not paired."""
        cap_a = _plane((0, 0, 0), (0, 0, 1), area=1.0)
        cap_b = _plane((0, 0, 5), (0, 0, -1), area=0.001)
        pairs = find_end_caps([cap_a, cap_b])
        assert len(pairs) == 0

    def test_keeps_largest_area_pairs(self):
        """Only pairs near the maximum area are kept."""
        big_a = _plane((0, 0, 0), (0, 0, 1), area=100.0)
        big_b = _plane((0, 0, 5), (0, 0, -1), area=100.0)
        small_a = _plane((10, 0, 0), (0, 0, 1), area=1.0)
        small_b = _plane((10, 0, 2), (0, 0, -1), area=1.0)
        pairs = find_end_caps([big_a, big_b, small_a, small_b])
        assert len(pairs) == 1
        assert pairs[0][0].area == 100.0

    def test_empty_list(self):
        assert find_end_caps([]) == []


# ── classify_section_from_faces ─────────────────────────────────────────────


class TestClassifySection:
    def test_tubular_from_cylinders(self):
        side = [_cylinder((0, 0, 2.5), (0, 0, 1), radius=0.15)]
        cap_a = _plane((0, 0, 0), (0, 0, 1))
        cap_b = _plane((0, 0, 5), (0, 0, -1))
        sec = classify_section_from_faces(side, cap_a, cap_b)
        assert sec.section_type == "tubular"
        assert sec.dimensions["diameter"] == 0.30

    def test_box_from_four_planes(self):
        side = [_plane((0, 0, 2.5), (1, 0, 0)) for _ in range(4)]
        cap_a = _plane((0, 0, 0), (0, 0, 1))
        cap_b = _plane((0, 0, 5), (0, 0, -1))
        sec = classify_section_from_faces(side, cap_a, cap_b)
        assert sec.section_type == "box"

    def test_i_beam_from_many_planes(self):
        side = [_plane((0, 0, 2.5), (1, 0, 0)) for _ in range(8)]
        cap_a = _plane((0, 0, 0), (0, 0, 1))
        cap_b = _plane((0, 0, 5), (0, 0, -1))
        sec = classify_section_from_faces(side, cap_a, cap_b)
        assert sec.section_type == "i_beam"

    def test_channel_from_six_planes(self):
        side = [_plane((0, 0, 2.5), (1, 0, 0)) for _ in range(6)]
        cap_a = _plane((0, 0, 0), (0, 0, 1))
        cap_b = _plane((0, 0, 5), (0, 0, -1))
        sec = classify_section_from_faces(side, cap_a, cap_b)
        assert sec.section_type == "channel"

    def test_unknown_fallback(self):
        side: list[StepFace] = []
        cap_a = _plane((0, 0, 0), (0, 0, 1))
        cap_b = _plane((0, 0, 5), (0, 0, -1))
        sec = classify_section_from_faces(side, cap_a, cap_b)
        assert sec.section_type == "unknown"


# ── extract_members_from_faces ──────────────────────────────────────────────


class TestExtractMembers:
    def test_box_extrusion(self):
        """A box: two parallel end caps + four side planes.

        End caps must be the largest-area planar faces for the heuristic
        to identify them.
        """
        faces = [
            _plane(centroid=(0, 0, 0), normal=(0, 0, 1), area=100.0),   # end cap A
            _plane(centroid=(0, 0, 5), normal=(0, 0, -1), area=100.0),  # end cap B
            _plane(centroid=(0.5, 0, 2.5), normal=(1, 0, 0), area=5.0),  # side 1
            _plane(centroid=(-0.5, 0, 2.5), normal=(-1, 0, 0), area=5.0),  # side 2
            _plane(centroid=(0, 0.5, 2.5), normal=(0, 1, 0), area=5.0),  # side 3
            _plane(centroid=(0, -0.5, 2.5), normal=(0, -1, 0), area=5.0),  # side 4
        ]
        members = extract_members_from_faces(faces)
        assert len(members) == 1
        m = members[0]
        assert m.name == "M1"
        assert m.section.section_type == "box"
        # Centreline from (0,0,0) to (0,0,5)
        assert abs(m.axis_start[0]) < 1e-6
        assert abs(m.axis_start[1]) < 1e-6
        assert abs(m.axis_start[2]) < 1e-6
        assert abs(m.axis_end[0]) < 1e-6
        assert abs(m.axis_end[1]) < 1e-6
        assert abs(m.axis_end[2] - 5.0) < 1e-6

    def test_tubular_fallback(self):
        """When no end caps are found, fall back to cylinder grouping."""
        faces = [
            _cylinder(centroid=(0, 0, 0), axis=(0, 0, 1), radius=0.15),
            _cylinder(centroid=(0, 0, 5), axis=(0, 0, 1), radius=0.15),
        ]
        members = extract_members_from_faces(faces)
        assert len(members) == 1
        m = members[0]
        assert m.section.section_type == "tubular"

    def test_empty_faces(self):
        assert extract_members_from_faces([]) == []


# ── group_cylinders_into_members ───────────────────────────────────────────


class TestGroupCylinders:
    def test_single_member_two_faces(self):
        faces = [
            _cylinder(centroid=(0, 0, 0), axis=(0, 0, 1), radius=0.15),
            _cylinder(centroid=(0, 0, 5), axis=(0, 0, 1), radius=0.15),
        ]
        members = group_cylinders_into_members(faces)
        assert len(members) == 1
        m = members[0]
        assert m.section.section_type == "tubular"

    def test_different_radii_split(self):
        faces = [
            _cylinder(centroid=(0, 0, 0), axis=(0, 0, 1), radius=0.15),
            _cylinder(centroid=(0, 0, 5), axis=(0, 0, 1), radius=0.30),
        ]
        members = group_cylinders_into_members(faces)
        assert len(members) == 2

    def test_different_axes_split(self):
        faces = [
            _cylinder(centroid=(0, 0, 0), axis=(0, 0, 1), radius=0.15),
            _cylinder(centroid=(5, 0, 0), axis=(0, 1, 0), radius=0.15),
        ]
        members = group_cylinders_into_members(faces)
        assert len(members) == 2

    def test_non_cylinders_ignored(self):
        faces = [
            _cylinder(centroid=(0, 0, 0), axis=(0, 0, 1), radius=0.15),
            _plane(centroid=(0, 0, 5), normal=(0, 0, 1)),
        ]
        members = group_cylinders_into_members(faces)
        assert len(members) == 1

    def test_empty(self):
        assert group_cylinders_into_members([]) == []

    def test_no_cylinders(self):
        faces = [_plane(centroid=(0, 0, 0), normal=(0, 0, 1))]
        assert group_cylinders_into_members(faces) == []
