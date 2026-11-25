from collections import Counter
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from igs import read_top_edge
from machine import machine
from stl import load_stl


ROOT = Path(__file__).resolve().parent
STL = ROOT / 'examples/box-binary.stl'
IGS = ROOT / 'examples/box-edge.igs'
OPTIONS = dict(yellow_z=0, offset=5, angle=45, y_start=4, y_end=16)


def signed_volume(triangles):
    return math.fsum(a[i] * (b[(i+1) % 3]*c[(i+2) % 3] - b[(i+2) % 3]*c[(i+1) % 3])
                     for a, b, c in triangles for i in range(3)) / 6


def contains(triangles, point):
    # Cast a ray along +Z. Test probes avoid projected edges and vertices.
    x, y, z = point
    crossings = 0
    for a, b, c in triangles:
        u = tuple(q - p for p, q in zip(a, b))
        v = tuple(q - p for p, q in zip(a, c))
        det = u[0]*v[1] - u[1]*v[0]
        if det == 0:
            continue
        s = ((x-a[0])*v[1] - (y-a[1])*v[0]) / det
        t = (u[0]*(y-a[1]) - u[1]*(x-a[0])) / det
        if min(s, t, 1-s-t) > 0 and a[2]+s*u[2]+t*v[2] > z:
            crossings += 1
    return crossings % 2 == 1


class MachiningTests(unittest.TestCase):
    def test_pair_and_output_from_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'machined.stl'
            command = [sys.executable, '-B', str(ROOT / 'machine.py'), '--stl', str(STL), '--igs', str(IGS),
                       '--out', str(out), '--yellow-z', '0', '--offset', '5', '--angle', '45',
                       '--y-start', '4', '--y-end', '16']
            args = dict(capture_output=True, text=True)
            run = subprocess.run(command, **args)
            self.assertEqual(run.returncode, 0, run.stderr)
            summary = json.loads(run.stdout)
            self.assertEqual(summary['machining_y_range_mm'], [4, 16])
            self.assertEqual(summary['igs_upper_edge_xyz_mm'], [[-10, 10, 10], [10, 10, 10]])
            output = load_stl(out)
            oriented_edges = Counter((a, b) for triangle in output
                                     for a, b in zip(triangle, triangle[1:] + triangle[:1]))
            for (a, b), count in oriented_edges.items():
                self.assertEqual(count, 1)
                self.assertEqual(oriented_edges[b, a], 1)
            self.assertAlmostEqual(signed_volume(output), 6900)
            for point, expected in (((1, 2.3, 13), True), ((1, 18.3, 13), True),
                                    ((1, 8.3, 13), False), ((1, 8.3, 8), True),
                                    ((14, 8.3, 8), False), ((14, 8.3, 4), True)):
                with self.subTest(point=point):
                    self.assertEqual(contains(output, point), expected)
            original_bytes = out.read_bytes()
            retry = subprocess.run(command, **args)
            self.assertEqual(retry.returncode, 2)
            self.assertEqual(out.read_bytes(), original_bytes)
            invalid_out = Path(folder) / 'invalid.stl'
            command[command.index('--out') + 1] = str(invalid_out)
            command[command.index('--angle') + 1] = '55'
            failure = subprocess.run(command, **args)
            self.assertEqual(failure.returncode, 2)
            self.assertIn('outside the finite IGES reference segment', failure.stderr)
            self.assertFalse(invalid_out.exists())

    def test_adjusted_profile_on_same_pair(self):
        options = dict(OPTIONS, offset=6, angle=math.degrees(math.atan2(4, 5)))
        output, report = machine(load_stl(STL), read_top_edge(IGS), **options)
        self.assertEqual(report['candidate_profile_xz_mm']['A'], (-15, 6))
        self.assertAlmostEqual(report['candidate_profile_xz_mm']['C'][0], -10)
        self.assertAlmostEqual(signed_volume(output), 6960)

    def test_fixed_reference_sloped_stock_independent_adjustments(self):
        stock_path = ROOT / 'examples/sloped-stock.stl'
        reference_path = ROOT / 'examples/wide-reference.igs'
        stock = load_stl(stock_path)
        edge = read_top_edge(reference_path)
        self.assertEqual(edge, ((-15, 10, 14), (15, 10, 14)))
        self.assertAlmostEqual(signed_volume(stock), 13200)
        defaults = dict(OPTIONS, offset=7.5, angle=53)
        for offset, angle in ((7.5, 53), (7.5, 55), (5, 53), (5, 52), (10, 55), (10, 52)):
            with self.subTest(offset=offset, angle=angle):
                options = dict(defaults, offset=offset, angle=angle)
                output, report = machine(stock, edge, **options)
                inset = (14 - offset) / math.tan(math.radians(angle))
                self.assertAlmostEqual(report['candidate_profile_xz_mm']['C'][0], -15 + inset)
                retained_area = 30*offset + (30 - inset)*(14 - offset)
                # Full sloping stock integrated over the middle 12 mm is 7920 mm³.
                self.assertAlmostEqual(signed_volume(output), 13200 - 7920 + 12*retained_area, delta=1e-5)
                for point, expected in (
                    ((1.23, 2.31, 20.3), True), ((1.23, 2.31, 20.6), False),
                    ((1.23, 18.31, 23.5), True), ((1.23, 18.31, 23.8), False),
                    ((1.23, 8.31, 15), False), ((1.23, 8.31, 12), True),
                    ((14.83, 8.31, 13.5), False), ((14.83, 8.31, 4), True),
                ):
                    self.assertEqual(contains(output, point), expected, point)

    def test_unsupported_stock_and_igs(self):
        edge = read_top_edge(IGS)
        with self.assertRaisesRegex(ValueError, 'closed, consistently oriented'):
            machine(load_stl(STL)[:-1], edge, **OPTIONS)
        with self.assertRaisesRegex(ValueError, 'strictly inside stock'):
            machine(load_stl(STL), edge, **dict(OPTIONS, y_start=0))
        template = IGS.read_text(encoding='ascii')
        with tempfile.TemporaryDirectory() as folder:
            invalid = Path(folder) / 'invalid.igs'
            for text, message in (
                (template.replace('2HMM', '2HIN'), 'declare millimeters'),
                (template.replace('110,-10,10,10,10,10,10;', '110,-10,10,10,10,11,10;'), 'parallel to local X'),
                (template.replace('110,-10,10,10,10,10,10;', '126,-10,10,10,10,10,10;'), 'line endpoints'),
                ('plain text\n', '80-column'),
            ):
                with self.subTest(message=message):
                    invalid.write_text(text, encoding='ascii')
                    with self.assertRaisesRegex(ValueError, message):
                        read_top_edge(invalid)
