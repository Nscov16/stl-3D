import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from igs import read_line, read_top_edge
from machine import machine
from preview import box, frame_from_file, preview, to_local_mesh
from stl import load_stl

ROOT = Path(__file__).resolve().parent


def signed_volume_for_test(mesh):
    return sum(sum(a[i]*(b[(i+1)%3]*c[(i+2)%3]-b[(i+2)%3]*c[(i+1)%3])
                   for i in range(3)) for a,b,c in mesh) / 6


class DeliveryTests(unittest.TestCase):
    def test_right_handed_shared_frame_preserves_machine_result(self):
        stock = load_stl(ROOT / 'examples/sloped-stock.stl')
        edge = read_line(ROOT / 'examples/wide-reference.igs')
        expected, expected_report = machine(stock, edge, yellow_z=0, offset=7.5, angle=53, y_start=4, y_end=16)
        theta = math.pi / 2
        c, s = round(math.cos(theta)), round(math.sin(theta))
        axes = [(c, s, 0), (-s, c, 0), (0, 0, 1)]
        origin = (1, 2, 3)

        def world(p):
            return tuple(origin[j] + sum(p[i]*axes[i][j] for i in range(3)) for j in range(3))

        moved_stock = [[world(p) for p in face] for face in stock]
        moved_edge = [world(p) for p in edge]
        recovered = to_local_mesh(moved_stock, origin, axes)
        recovered_edge = tuple(tuple(sum((v-o)*a for v,o,a in zip(p,origin,axis)) for axis in axes)
                               for p in moved_edge)
        recovered_edge = tuple(tuple(0.0 if abs(v) < 1e-12 else v for v in p) for p in recovered_edge)
        got, report = machine(recovered, recovered_edge, yellow_z=0, offset=7.5, angle=53,
                              y_start=4, y_end=16)
        self.assertAlmostEqual(signed_volume_for_test(expected), signed_volume_for_test(got), delta=1e-5)
        for key in ('A', 'B', 'C', 'D'):
            for actual, target in zip(report['candidate_profile_xz_mm'][key],
                                      expected_report['candidate_profile_xz_mm'][key]):
                self.assertAlmostEqual(actual, target, delta=1e-9)
        self.assertEqual(report['coordinate_system'], 'local_mm')
        with self.assertRaisesRegex(ValueError, 'right-handed'):
            to_local_mesh(box(), (0,0,0), [(1,0,0),(0,1,0),(0,0,-1)])

    def test_scope_resolves_connected_protrusion_and_rejects_empty_scope(self):
        from preview import prism
        outline = [(-15,0),(15,0),(15,20),(-15,20),(19,8)]
        mesh = prism(outline,2,0,15,[(0,1,2),(0,2,3),(0,3,4)])
        all_result = preview(mesh)
        scoped = preview(mesh, ab_y_range=(0,7))
        self.assertEqual(all_result['candidate_profile_xz_mm']['B'][0], 19)
        self.assertEqual(scoped['candidate_profile_xz_mm']['B'][0], 15.0)
        with self.assertRaisesRegex(ValueError, 'contains no nonzero'):
            preview(mesh, ab_y_range=(40,50))

    def test_igs_vertical_gap_is_distinct_from_datum_offset(self):
        edge = read_top_edge(ROOT / 'examples/wide-reference.igs')
        offset_mesh, offset_report = machine(load_stl(ROOT / 'examples/sloped-stock.stl'), edge,
                                             yellow_z=0, offset=7.5, angle=53, y_start=4, y_end=16)
        gap_mesh, gap_report = machine(load_stl(ROOT / 'examples/sloped-stock.stl'), edge,
                                       yellow_z=0, igs_vertical_gap=6.5, angle=53, y_start=4, y_end=16)
        self.assertEqual(offset_report['datum_to_base_mm'], 7.5)
        self.assertEqual(offset_report['base_to_upper_mm'], 6.5)
        self.assertEqual(gap_report['height_mode'], 'igs_vertical_gap')
        self.assertEqual(gap_report['datum_to_base_mm'], 7.5)
        self.assertEqual([[[*a], [*b]] for a, b in gap_report['igs_vertical_measurements_xyz_mm']],
                         [[[-15,10,7.5],[-15,10,14]], [[15,10,7.5],[15,10,14]]])
        self.assertAlmostEqual(sum(math.dist(p,q) for f,g in zip(offset_mesh,gap_mesh) for p,q in zip(f,g)),0)
        with self.assertRaisesRegex(ValueError, 'either offset or IGES'):
            machine(load_stl(ROOT / 'examples/sloped-stock.stl'), edge, yellow_z=0, offset=7.5,
                    igs_vertical_gap=6.5, angle=53, y_start=4, y_end=16)

    def test_cli_applies_same_frame_to_stl_and_iges(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            frame = root/'frame.json'
            theta = math.pi / 2
            c, s = round(math.cos(theta)), round(math.sin(theta))
            axes = [(c,s,0),(-s,c,0),(0,0,1)]
            origin = (31,-12,8)
            frame.write_text(json.dumps({'origin':origin,'axes':axes}))

            def world(p):
                return [origin[j]+sum(p[i]*axes[i][j] for i in range(3)) for j in range(3)]
            mesh = load_stl(ROOT/'examples/sloped-stock.stl')
            from machine import encode_stl
            moved = [[world(p) for p in face] for face in mesh]
            stl = root/'moved.stl'
            stl.write_text(encode_stl(moved))
            text = (ROOT/'examples/wide-reference.igs').read_text()
            rows=text.splitlines()
            params='110,'+','.join(str(x) for p in ((-15,10,14),(15,10,14)) for x in world(p))+';'
            rows[6]=f'{params:<64}{rows[6][64:]}'
            igs = root/'moved.igs'
            igs.write_text('\n'.join(rows)+'\n')
            out=root/'out.stl'
            command=[sys.executable,'-B',str(ROOT/'machine.py'),'--stl',str(stl),'--igs',str(igs),
                     '--yellow-z','0','--offset','7.5','--angle','53','--y-start','4','--y-end','16',
                     '--frame',str(frame),'--out',str(out)]
            run=subprocess.run(command,text=True,capture_output=True)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertIn('"coordinate_system": "local_mm"',run.stdout)


if __name__ == '__main__':
    unittest.main()
