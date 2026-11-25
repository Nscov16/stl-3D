"""Front-profile preview in local millimeters (X right, Y depth, Z up).
"""
import argparse
import json
import math
from pathlib import Path

from stl import load_stl


def local_projector(origin, axes):
    if len(axes) != 3 or any(len(a) != 3 for a in axes) or len(origin) != 3:
        raise ValueError('Expected a 3D origin and three axes')
    if not all(math.isfinite(v) for row in (origin, *axes) for v in row):
        raise ValueError('Frame origin and axes must be finite')
    for i, a in enumerate(axes):
        for j, b in enumerate(axes):
            if not math.isclose(sum(x*y for x, y in zip(a, b)), float(i == j), rel_tol=0, abs_tol=1e-9):
                raise ValueError('Frame axes must be orthonormal')
    x, y, z = axes
    cross = tuple(x[(i+1)%3]*y[(i+2)%3] - x[(i+2)%3]*y[(i+1)%3] for i in range(3))
    if sum(a*b for a, b in zip(cross, z)) <= 0:
        raise ValueError('Frame must be right-handed')

    def project(point):
        result = tuple(sum((p-o)*v for p, o, v in zip(point, origin, axis)) for axis in axes)
        if not all(map(math.isfinite, result)):
            raise ValueError('Projected coordinates must be finite')
        return tuple(0.0 if abs(v) < 1e-9 else v for v in result)
    return project


def frame_from_file(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(data, dict) or set(data) != {'origin', 'axes'}:
            raise ValueError('Expected origin and axes keys')
        return local_projector(data['origin'], data['axes'])
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f'Invalid frame: {error}') from error


def project_mesh(mesh, project):
    return [tuple(project(point) for point in triangle) for triangle in mesh]


def to_local_mesh(world_mesh, origin, axes):
    return project_mesh(world_mesh, local_projector(origin, axes))


def section(triangles, axis, level):
    """Return 3D section segments, snapping vertices less than 1e-9 mm away.

    Skip point-only intersections. Reject coplanar faces and edges.
    """
    tolerance = 1e-9
    segments = []
    tangent_vertex = False
    for triangle in triangles:
        delta = [p[axis] - level for p in triangle]
        delta = [0 if abs(d) < tolerance else d for d in delta]
        on_plane = [i for i, d in enumerate(delta) if d == 0]
        if len(on_plane) == 3:
            raise ValueError('Section is coplanar with a triangle')
        if len(on_plane) == 2:
            raise ValueError('Section overlaps a triangle edge')
        if not (min(delta) < 0 < max(delta)):
            tangent_vertex = tangent_vertex or bool(on_plane)
            continue
        points = []
        for i in on_plane:
            point = list(triangle[i])
            point[axis] = level
            points.append(tuple(point))
        for i, j in ((0, 1), (1, 2), (2, 0)):
            if delta[i] < 0 < delta[j] or delta[j] < 0 < delta[i]:
                t = delta[i] / (delta[i] - delta[j])
                a, b = triangle[i], triangle[j]
                points.append(tuple(u + t * (v - u) for u, v in zip(a, b)))
        if len(points) == 2 and points[0] != points[1]:
            segments.append(points)
    if not segments:
        if tangent_vertex:
            raise ValueError('Section touches a triangle only at a vertex')
        raise ValueError('No mesh section at requested level')
    return segments


def prism(polygon, axis, start, end, cap_faces):
    """Extrude a fixture polygon, with explicit cap triangulation for concave shapes."""
    def vertex(pair, depth):
        p = list(pair)
        p.insert(axis, depth)
        return tuple(p)
    low = [vertex(p, start) for p in polygon]
    high = [vertex(p, end) for p in polygon]
    faces = []
    for i in range(len(low)):
        j = (i + 1) % len(low)
        faces.extend(((low[i], low[j], high[j]), (low[i], high[j], high[i])))
    for i, j, k in cap_faces:
        faces.extend(((low[k], low[j], low[i]), (high[i], high[j], high[k])))
    return faces


def box():
    return prism([(-15, 0), (15, 0), (15, 20), (-15, 20)], 2, 0, 15,
                 [(0, 1, 2), (0, 2, 3)])


def clip_section_y(segments, bounds):
    lo, hi = bounds
    if len(bounds) != 2 or not all(map(math.isfinite, bounds)) or lo >= hi:
        raise ValueError('A/B Y range must have finite, strictly increasing bounds')
    clipped = []
    for p, q in segments:
        if p[1] > q[1]:
            p, q = q, p
        start, end = max(lo, p[1]), min(hi, q[1])
        if p[1] == q[1] and start <= end:
            clipped.append([p, q])
        elif start < end:
            def point(y):
                return p[0] + (q[0]-p[0])*((y-p[1])/(q[1]-p[1])), y, p[2]
            clipped.append([point(start), point(end)])
    if not clipped:
        raise ValueError('A/B Y range contains no nonzero section segments')
    return clipped


def preview(local_mesh, datum_z=0, offset=7.5, upper_z=12, angle=53, ab_y_range=None):
    if not all(map(math.isfinite, (datum_z, offset, upper_z, angle))):
        raise ValueError('Dimensions and angle must be finite')
    base = datum_z + offset
    if offset < 0 or upper_z <= base or not 0 < angle < 90:
        raise ValueError('Require nonnegative offset, positive height and acute angle')
    segments = section(local_mesh, 2, base)
    selected = segments if ab_y_range is None else clip_section_y(segments, ab_y_range)
    points = [p for segment in selected for p in segment]
    left, right = min(p[0] for p in points), max(p[0] for p in points)
    inset = (upper_z - base) / math.tan(math.radians(angle))
    width = right - left - 2 * inset
    if width <= 1e-9:
        raise ValueError('Top edge collapses at selected height and angle')
    return {'section_segments_xyz_mm': segments,
            'ab_y_range_mm': ab_y_range,
            'extreme_candidates_xyz_mm': {label: sorted({p for p in points if abs(p[0]-x) < 1e-9})
                                          for label, x in [('A', left), ('B', right)]},
            'candidate_profile_xz_mm': {'A': (left, base), 'B': (right, base),
                                        'C': (left + inset, upper_z), 'D': (right - inset, upper_z)},
            'datum_to_base_mm': base - datum_z, 'base_to_upper_mm': upper_z - base,
            'top_width_mm': width}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stl', metavar='PATH', help='Read a binary or ASCII STL. Omit for the built-in box.')
    parser.add_argument('--datum-z', type=float, default=0, help='Local datum z (mm, default: 0).')
    parser.add_argument('--offset', type=float, default=7.5, help='Height above datum (mm, default: 7.5).')
    parser.add_argument('--angle', type=float, default=53, help='Side angle to horizontal (degrees, default: 53).')
    parser.add_argument('--upper-z', type=float, default=12, help='Local top edge z (mm, default: 12).')
    parser.add_argument('--frame', type=Path, help='Origin and axes JSON; output stays local')
    parser.add_argument('--ab-y-range', type=float, nargs=2, metavar=('MIN', 'MAX'))
    args = parser.parse_args()
    try:
        if args.stl is None:
            if args.frame is not None:
                raise ValueError('--frame requires --stl')
            mesh = box()
        else:
            try:
                mesh = load_stl(args.stl)
            except (OSError, ValueError) as error:
                parser.error(f'Cannot read STL {args.stl!r}: {error}')
        if args.frame is not None:
            mesh = project_mesh(mesh, frame_from_file(args.frame))
        result = preview(mesh, datum_z=args.datum_z, offset=args.offset,
                         upper_z=args.upper_z, angle=args.angle, ab_y_range=args.ab_y_range)
        print(json.dumps(result, indent=2, allow_nan=False))
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
