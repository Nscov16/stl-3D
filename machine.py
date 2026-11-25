"""Synthetic mesh machining with a local XZ trapezoid and bounded Y range."""
import argparse
import itertools
import json
import math
from pathlib import Path

from igs import horizontal_edge, read_line
from mesh_boolean import subtract_cutter
from preview import frame_from_file, preview, project_mesh
from stl import load_stl


def machine(mesh, upper_edge, *, yellow_z, angle, y_start, y_end,
            offset=None, igs_vertical_gap=None, ab_y_range=None):
    """Keep all stock outside the Y interval, and below/inside the profile within it."""
    (left, right), (front, back), (bottom, top) = (
        (min(coords), max(coords)) for coords in zip(*itertools.chain.from_iterable(mesh))
    )
    upper_edge = horizontal_edge(upper_edge)
    if igs_vertical_gap is not None and offset is not None:
        raise ValueError('Specify either offset or IGES vertical gap, not both')
    if igs_vertical_gap is not None:
        if not math.isfinite(igs_vertical_gap) or igs_vertical_gap <= 0:
            raise ValueError('IGES vertical gap must be finite and positive')
        offset = upper_edge[0][2] - igs_vertical_gap - yellow_z
    elif offset is None:
        offset = 7.5
    if not all(map(math.isfinite, (yellow_z, offset, angle, y_start, y_end))):
        raise ValueError('Machining parameters must be finite')
    if not front < y_start < y_end < back:
        raise ValueError('Example requires the machining Y interval strictly inside stock')
    (igs_left, igs_y, upper), (igs_right, _, _) = upper_edge
    base = yellow_z + offset
    if not bottom < base < upper < top or not bottom <= yellow_z < top:
        raise ValueError('Require yellow datum in stock and bottom < base < IGES upper Z < top')
    if not y_start <= igs_y <= y_end:
        raise ValueError('IGES upper edge Y must be within the machining interval')
    result = preview(mesh, datum_z=yellow_z, offset=offset, angle=angle, upper_z=upper,
                     ab_y_range=ab_y_range)
    profile = result['candidate_profile_xz_mm']
    a, b, c, d = (profile[key] for key in 'ABCD')
    tolerance = 1e-6  # mm; accept roundoff at the finite segment endpoints.
    if c[0] < igs_left - tolerance or d[0] > igs_right + tolerance:
        raise ValueError('Trapezoid sides intersect outside the finite IGES reference segment')

    # CCW polygon in XZ. The indent follows the two candidate side lines and
    # the upper edge. Extend the other edges beyond stock in X and Z.
    margin = max(right - left, top - bottom)
    cutter = [(left - margin, base), a, c, d, b, (right + margin, base),
              (right + margin, top + margin), (left - margin, top + margin)]
    finished = subtract_cutter(mesh, cutter, y_start, y_end)

    result['igs_upper_edge_xyz_mm'] = upper_edge
    result['machining_y_range_mm'] = (y_start, y_end)
    result['yellow_datum_z_mm'] = yellow_z
    result['coordinate_system'] = 'local_mm'
    result['height_mode'] = 'igs_vertical_gap' if igs_vertical_gap is not None else 'datum_offset'
    # Vertical measurement is anchored at each end of the finite line.
    result['igs_vertical_measurements_xyz_mm'] = [((x, y, base), (x, y, z)) for x, y, z in upper_edge]
    return finished, result


def encode_stl(mesh):
    lines = ['solid synthetic_machined_stock']
    for a, b, c in mesh:
        u = [q - p for p, q in zip(a, b)]
        v = [q - p for p, q in zip(a, c)]
        cross = tuple(u[(i+1) % 3]*v[(i+2) % 3] - u[(i+2) % 3]*v[(i+1) % 3] for i in range(3))
        length = math.hypot(*cross)
        if not math.isfinite(length) or length == 0:
            raise ValueError('Output triangle normal cannot be represented')
        lines.extend(['  facet normal {} {} {}'.format(*(x / length for x in cross)), '    outer loop'])
        lines.extend('      vertex {} {} {}'.format(*p) for p in (a, b, c))
        lines.extend(['    endloop', '  endfacet'])
    lines.append('endsolid synthetic_machined_stock')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('stl', 'igs', 'out'):
        parser.add_argument(f'--{name}', type=Path, required=True)
    parser.add_argument('--yellow-z', type=float, required=True, help='Local yellow datum Z in millimeters')
    height = parser.add_mutually_exclusive_group()
    height.add_argument('--offset', type=float, help='Section height above yellow datum in mm (default: 7.5)')
    height.add_argument('--igs-vertical-gap', type=float, help='Positive local Z distance from AB plane to IGES line in mm')
    parser.add_argument('--frame', type=Path, help='Shared STL/IGES origin and axes JSON; output stays local')
    parser.add_argument('--ab-y-range', type=float, nargs=2, metavar=('MIN', 'MAX'), help='Restrict A/B to a local Y strip (mm)')
    parser.add_argument('--angle', type=float, default=53, help='Side angle from horizontal, in degrees')
    parser.add_argument('--y-start', type=float, required=True, help='Start of example machining depth, mm')
    parser.add_argument('--y-end', type=float, required=True, help='End of example machining depth, mm')
    args = parser.parse_args()
    if args.out.suffix.lower() != '.stl':
        parser.error('Output filename must end in .stl')
    try:
        mesh, edge = load_stl(args.stl), read_line(args.igs)
        if args.frame is not None:
            project = frame_from_file(args.frame)
            mesh = project_mesh(mesh, project)
            edge = horizontal_edge(tuple(map(project, edge)), tolerance=1e-9)
        triangles, report = machine(mesh, edge, yellow_z=args.yellow_z,
                                    offset=args.offset, igs_vertical_gap=args.igs_vertical_gap,
                                    ab_y_range=args.ab_y_range, angle=args.angle,
                                    y_start=args.y_start, y_end=args.y_end)
        document = encode_stl(triangles)
        summary = json.dumps(report, indent=2, allow_nan=False)
        with args.out.open('x', encoding='ascii') as output:
            output.write(document)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(summary)


if __name__ == '__main__':
    main()
