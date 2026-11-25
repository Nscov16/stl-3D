import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from preview import box
from stl import load_stl


ROOT = Path(__file__).resolve().parent
ASCII = ROOT / 'examples/box-ascii.stl'
BINARY = ROOT / 'examples/box-binary.stl'


def run_preview(*args):
    return subprocess.run([sys.executable, '-B', str(ROOT / 'preview.py'), *args],
                          capture_output=True, text=True)


class FilePreviewTests(unittest.TestCase):
    def test_both_samples_match_box(self):
        for path in (ASCII, BINARY):
            with self.subTest(path=path):
                self.assertEqual(load_stl(path), box())
        self.assertTrue(BINARY.read_bytes().startswith(b'solid'))

    def test_cli_samples_match_builtin_and_hand_calculation(self):
        options = ('--datum-z', '2', '--offset', '3', '--upper-z', '10', '--angle', '45')
        outputs = []
        for args in ((), ('--stl', str(ASCII)), ('--stl', str(BINARY))):
            with self.subTest(args=args):
                result = run_preview(*args, *options)
                self.assertEqual(result.returncode, 0, result.stderr)
                outputs.append(json.loads(result.stdout))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], outputs[2])
        output = outputs[0]
        self.assertEqual(output['datum_to_base_mm'], 3)
        segments = output['section_segments_xyz_mm']
        self.assertTrue(segments)
        self.assertTrue(all(p[2] == 5 for segment in segments for p in segment))
        expected = {'A': (-15, 5), 'B': (15, 5), 'C': (-10, 10), 'D': (10, 10)}
        for label, point in expected.items():
            for actual, target in zip(output['candidate_profile_xz_mm'][label], point):
                self.assertAlmostEqual(actual, target)
        self.assertAlmostEqual(output['top_width_mm'], 20)

    def test_invalid_stl(self):
        binary = BINARY.read_bytes()
        ascii_data = ASCII.read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'invalid.stl'
            for label, data, error in (
                ('empty', b'', 'empty'),
                ('text', b'not a mesh', 'Malformed STL'),
                ('no ASCII facets', b'solid empty\nendsolid empty\n', 'no triangles'),
                ('no binary facets', bytes(84), 'no triangles'),
                ('bad coordinates', ascii_data.replace(b'vertex -15 0 0', b'vertex nope 0 0', 1), 'coordinate'),
                ('ASCII overflow', ascii_data.replace(b'vertex -15 0 0', b'vertex 1e999 0 0', 1), 'non-finite'),
                ('broken facet', ascii_data.replace(b'outer loop', b'inner loop', 1), 'expected outer loop'),
                ('missing endsolid', ascii_data.rsplit(b'endsolid', 1)[0], 'missing endsolid'),
                ('truncated binary', binary[:-1], 'binary size mismatch'),
                ('binary with extra byte', binary + b'\x00', 'binary size mismatch'),
                ('non-finite binary vertex', binary[:96] + struct.pack('<f', float('nan')) + binary[100:], 'non-finite'),
            ):
                with self.subTest(label=label):
                    path.write_bytes(data)
                    with self.assertRaisesRegex(ValueError, error):
                        load_stl(path)

    def test_cli_rejects_missing_bad_and_outside_section(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'invalid.stl'
            missing = run_preview('--stl', str(path))
            path.write_bytes(b'not a mesh')
            invalid = run_preview('--stl', str(path))
        outside = run_preview('--stl', str(ASCII), '--offset', '16', '--upper-z', '25')
        for result, message in ((missing, str(path)), (invalid, 'Malformed STL'),
                                (outside, 'No mesh section')):
            with self.subTest(message=message):
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                self.assertIn(message, result.stderr)
                self.assertNotIn('Traceback', result.stderr)
