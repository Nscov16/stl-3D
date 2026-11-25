"""Generate the original teddy head and its horizontal IGES reference."""
import argparse
from pathlib import Path
import struct
import sys

import numpy as np
from manifold3d import Error, Manifold

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def ellipsoid(center, radii, segments=48):
    return Manifold.sphere(1, segments).scale(radii).translate(center)


def head():
    solid = ellipsoid((0, 0, 31), (29, 24, 29))
    for side in (-1, 1):
        solid += ellipsoid((side * 24, -1, 50), (10, 8, 11))
        solid -= ellipsoid((side * 26, -8, 52), (5.5, 4, 6))
        solid -= ellipsoid((side * 10, -23, 37), (3.8, 3.8, 4.5))
    solid += ellipsoid((0, -21, 25), (14, 7, 9))
    solid += ellipsoid((0, -27, 29), (6.5, 5, 4.2))
    for side in (-1, 1):
        smile = ellipsoid((0, 0, 0), (5.3, 2, 1.25), segments=24)
        solid -= smile.rotate((0, -side * 14, 0)).translate((side * 4.3, -27, 22.5))
    assert solid.status() == Error.NoError and len(solid.decompose()) == 1
    return solid


def write_binary_stl(path, solid):
    mesh = solid.to_mesh64()
    with path.open('xb') as output:
        output.write(b'Synthetic teddy head, mm'.ljust(80, b' '))
        output.write(struct.pack('<I', len(mesh.tri_verts)))
        for face in mesh.tri_verts:
            a, b, c = mesh.vert_properties[face]
            normal = np.cross(b - a, c - a)
            normal /= np.linalg.norm(normal)
            output.write(struct.pack('<12fH', *normal, *a, *b, *c, 0))


def write_reference(path):
    rows = (ROOT / 'examples/wide-reference.igs').read_text(encoding='ascii').splitlines()
    rows[0] = f'{"Synthetic teddy head, finite X reference at Y=12 Z=43 mm":72}{rows[0][72:]}'
    rows[-2] = f'{"110,-31,12,43,31,12,43;":64}{rows[-2][64:]}'
    with path.open('x', encoding='ascii') as output:
        output.write('\n'.join(rows) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    folder = parser.parse_args().directory
    write_binary_stl(folder / 'head-stock.stl', head())
    write_reference(folder / 'head-reference.igs')


if __name__ == '__main__':
    main()
