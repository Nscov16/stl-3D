"""Subtract an extruded cutter from the original closed triangle mesh."""
from collections import Counter
import math
from pathlib import Path


def _closed_edges(triangles, label):
    edges = Counter()
    for face in triangles:
        if len(set(face)) != 3:
            raise ValueError(f'{label} contains a degenerate triangle')
        edges.update(zip(face, face[1:] + face[:1]))
    if any(count != 1 or edges[b, a] != 1 for (a, b), count in edges.items()):
        raise ValueError(f'{label} must be a closed, consistently oriented triangle mesh')


def subtract_cutter(triangles, polygon_xz, y_start, y_end):
    _closed_edges(triangles, 'Stock')
    try:
        import numpy as np
        from manifold3d import CrossSection, Error, Manifold, Mesh64
    except (ImportError, OSError) as error:
        raise ValueError(f'Machining dependencies unavailable: {error}; install the project requirements') from error

    vertex_ids = {}
    faces = [[vertex_ids.setdefault(point, len(vertex_ids)) for point in face] for face in triangles]
    stock = Manifold(Mesh64(np.array(list(vertex_ids), dtype=np.float64), np.array(faces, dtype=np.uint64)))
    if stock.status() != Error.NoError:
        raise ValueError(f'Unsupported stock mesh: {stock.status()}')
    if len(stock.decompose()) != 1 or not stock.volume() > 0:
        raise ValueError('Stock must have one connected outward-facing shell of positive volume')

    # The proper rotation sends planar (u,v) to world (x,z), and extrusion
    # coordinate w to y_end - w, preserving the cutter solid orientation.
    section = CrossSection([np.array(polygon_xz, dtype=np.float64)])
    cutter = section.extrude(y_end - y_start).transform(((1, 0, 0, 0), (0, 0, -1, y_end), (0, 1, 0, 0)))
    if cutter.status() != Error.NoError or cutter.is_empty():
        raise ValueError('Could not construct the bounded machining cutter')
    finished = stock - cutter
    if finished.status() != Error.NoError or finished.is_empty():
        raise ValueError(f'Machining did not produce a valid solid: {finished.status()}')
    volume_before, volume_after = stock.volume(), finished.volume()
    if not all(map(math.isfinite, (volume_before, volume_after))) or not 0 < volume_after < volume_before:
        raise ValueError('Machining must remove positive volume and leave a nonempty solid')

    mesh = finished.to_mesh64()
    points = [tuple(map(float, point[:3])) for point in mesh.vert_properties]
    result = [tuple(points[index] for index in face) for face in mesh.tri_verts]
    _closed_edges(result, 'Finished mesh')
    return result
