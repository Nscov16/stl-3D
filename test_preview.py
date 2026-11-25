import math
import unittest

from preview import box, preview, prism, section, to_local_mesh


class PreviewTests(unittest.TestCase):
    def test_hand_calculated_profile(self):
        result = preview(box(), offset=5, upper_z=10, angle=45)
        expected = {'A': (-15, 5), 'B': (15, 5), 'C': (-10, 10), 'D': (10, 10)}
        for name, (x, z) in expected.items():
            actual = result['candidate_profile_xz_mm'][name]
            self.assertAlmostEqual(actual[0], x)
            self.assertAlmostEqual(actual[1], z)
        self.assertAlmostEqual(result['top_width_mm'], 20)

    def test_rigid_motion(self):
        c, s = math.cos(.7), math.sin(.7)
        axes = [(c, 0, -s), (0, 1, 0), (s, 0, c)]
        origin = (13, -7, 5)
        def world(p):
            return tuple(origin[j] + sum(p[i]*axes[i][j] for i in range(3)) for j in range(3))
        rotated = [[world(p) for p in tri] for tri in box()]
        recovered = preview(to_local_mesh(rotated, origin, axes))
        for name, expected in preview(box())['candidate_profile_xz_mm'].items():
            for value, target in zip(recovered['candidate_profile_xz_mm'][name], expected):
                self.assertAlmostEqual(value, target)

    def test_connected_protrusion_changes_extreme(self):
        outline = [(-15, 0), (15, 0), (19, 8), (15, 20), (-15, 20)]
        mesh = prism(outline, 2, 0, 15, [(0, 1, 2), (0, 2, 3), (0, 3, 4)])
        result = preview(mesh)
        self.assertEqual(result['extreme_candidates_xyz_mm']['B'], [(19, 8, 7.5)])

    def test_same_volume_wrong_end(self):
        # Side profile in (depth, height), extruded uniformly across x.
        yz = [(0, 0), (20, 0), (20, 15), (10, 15), (10, 10), (0, 10)]
        caps = [(0, 1, 4), (0, 4, 5), (1, 2, 3), (1, 3, 4)]
        front_cut = prism(yz, 0, -15, 15, caps)
        back_cut = [[(x, 20-y, z) for x, y, z in reversed(tri)] for tri in front_cut]
        def volume(mesh):
            terms = []
            for a, b, c in mesh:
                terms.append(sum(a[i]*(b[(i+1)%3]*c[(i+2)%3]-b[(i+2)%3]*c[(i+1)%3]) for i in range(3)))
            return abs(math.fsum(terms))/6
        def retained_at_probes(mesh):
            # Both probes are on x=0, z=12, well inside the footprint.
            return [12 < max(p[2] for seg in section(mesh, 1, y) for p in seg) for y in (5, 15)]
        for mesh in (front_cut, back_cut):
            self.assertAlmostEqual(volume(mesh), 7500)
        self.assertEqual(retained_at_probes(front_cut), [False, True])
        self.assertEqual(retained_at_probes(back_cut), [True, False])

    def test_parameter_limits(self):
        for offset in (5, 10):
            for angle in (52, 55):
                result = preview(box(), offset=offset, angle=angle)
                self.assertEqual(result['datum_to_base_mm'], offset)
                self.assertAlmostEqual(result['top_width_mm'], 30-2*(12-offset)/math.tan(math.radians(angle)))
        for options in ({'angle': 0}, {'offset': math.nan}, {'upper_z': 6}, {'angle': 1}):
            with self.assertRaises(ValueError):
                preview(box(), **options)

    def test_section_through_vertex(self):
        triangle = [(0, 0, 0), (2, 0, 2), (0, 2, -2)]
        for face in (triangle, triangle[::-1]):
            with self.subTest(face=face):
                self.assertEqual(section([face], 2, 0), [[(0, 0, 0), (1, 1, 0)]])

    def test_section_tangent_vertex_only(self):
        tangent = [(0, 0, 0), (2, 0, 2), (0, 2, 2)]
        with self.assertRaisesRegex(ValueError, 'only at a vertex'):
            section([tangent], 2, 0)

    def test_section_skips_tangent_vertex_with_other_segments(self):
        tangent = [(0, 0, 0), (2, 0, 2), (0, 2, 2)]
        crossing = [(4, 0, -2), (6, 0, 2), (4, 2, 2)]
        expected = [[(5, 0, 0), (4, 1, 0)]]
        for mesh in ([tangent, crossing], [crossing, tangent]):
            self.assertEqual(section(mesh, 2, 0), expected)

    def test_section_rejects_shared_edge_in_either_order_or_winding(self):
        first = [(0, 0, 0), (2, 0, 0), (0, 0, -2)]
        second = [(2, 0, 0), (0, 0, 0), (0, 0, 2)]
        for faces in ([first, second], [second, first]):
            for reverse_first in (False, True):
                for reverse_second in (False, True):
                    a = faces[0][::-1] if reverse_first else faces[0]
                    b = faces[1][::-1] if reverse_second else faces[1]
                    with self.subTest(mesh=[a, b]):
                        with self.assertRaisesRegex(ValueError, 'overlaps a triangle edge'):
                            section([a, b], 2, 0)

    def test_section_rejects_coplanar_face(self):
        triangle = [(0, 0, 0), (2, 0, 0), (0, 2, 0)]
        with self.assertRaisesRegex(ValueError, 'coplanar with a triangle'):
            section([triangle], 2, 0)

    def test_section_vertex_snap_tolerance(self):
        for height in (-2e-9, -1e-9, -0.5e-9, 0.5e-9, 1e-9, 2e-9):
            with self.subTest(height=height):
                triangle = [(0, 0, height), (2, 0, 2), (0, 2, -2)]
                segments = section([triangle], 2, 0)
                if abs(height) < 1e-9:
                    self.assertEqual(segments, [[(0, 0, 0), (1, 1, 0)]])
                else:
                    displacement = 2 * abs(height) / (2 + abs(height))
                    near = (displacement, 0, 0) if height < 0 else (0, displacement, 0)
                    self.assertEqual(len(segments), 1)
                    self.assertEqual(len(segments[0]), 2)
                    closest, farthest = sorted(segments[0], key=lambda p: math.hypot(*p))
                    for actual, expected in zip(closest, near):
                        self.assertAlmostEqual(actual, expected, delta=1e-15)
                    self.assertEqual(farthest, (1, 1, 0))


if __name__ == '__main__':
    unittest.main()
