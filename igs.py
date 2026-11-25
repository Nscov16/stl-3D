"""Read the single untransformed type-110 line used by the machining example."""
import math
from pathlib import Path


def read_line(path):
    records = Path(path).read_text(encoding='ascii').splitlines()
    sections = {name: [] for name in 'SGDPT'}
    order = []
    for record in records:
        if len(record) != 80 or record[72] not in sections:
            raise ValueError('Expected 80-column IGES records in S/G/D/P/T sections')
        name = record[72]
        if int(record[73:]) != len(sections[name]) + 1:
            raise ValueError('Invalid IGES section sequence number')
        sections[name].append(record[:72])
        order.append(name)
    if order != sorted(order, key='SGDPT'.index) or not all(sections.values()) or len(sections['T']) != 1:
        raise ValueError('Expected complete, ordered IGES sections')
    counts = ''.join(f'{name}{len(sections[name]):7}' for name in 'SGDP')
    if sections['T'][0].strip() != counts:
        raise ValueError('IGES termination counts do not match section lengths')

    # The supported global subset uses the default comma/semicolon delimiters.
    global_data = ''.join(sections['G']).rstrip()
    if not global_data.endswith(';'):
        raise ValueError('Missing IGES global record terminator')
    fields = []
    cursor = 0
    # Hollerith strings are length-prefixed, so internal commas are data.
    while cursor < len(global_data):
        start = cursor
        while cursor < len(global_data) and global_data[cursor].isdigit():
            cursor += 1
        if start < cursor and global_data[cursor:cursor + 1] == 'H':
            cursor += 1 + int(global_data[start:cursor])
        else:
            while cursor < len(global_data) and global_data[cursor] not in ',;':
                cursor += 1
        if cursor >= len(global_data) or global_data[cursor] not in ',;':
            raise ValueError('Malformed IGES global parameter')
        fields.append(global_data[start:cursor].strip())
        cursor += 1
        if global_data[cursor - 1] == ';':
            break
    if cursor != len(global_data) or fields[:2] not in (['1H,', '1H;'], ['', '']):
        raise ValueError('Expected default IGES comma and semicolon delimiters')
    if len(fields) < 15 or float(fields[12]) != 1 or fields[13:15] != ['2', '2HMM']:
        raise ValueError('IGES must declare millimeters and model scale 1')

    if len(sections['D']) != 2:
        raise ValueError('Expected exactly one IGES entity (type 110 line)')
    first, second = ([row[i:i+8] for i in range(0, 72, 8)] for row in sections['D'])
    if int(first[0]) != 110 or int(second[0]) != 110 or int(second[4]) != 0:
        raise ValueError('Expected an IGES type 110 line with form 0')
    if first[6].strip() not in ('', '0'):
        raise ValueError('IGES line transformation is unsupported')
    parameters = sections['P']
    if int(first[1]) != 1 or int(second[3]) != len(parameters) or any(int(row[64:72]) != 1 for row in parameters):
        raise ValueError('IGES parameter records do not match the line directory')
    data = ''.join(row[:64] for row in parameters).rstrip()
    values = data[:-1].split(',')
    if not data.endswith(';') or len(values) != 7 or values[0].strip() != '110':
        raise ValueError('Expected IGES line endpoints in the parameter section')
    xyz = tuple(float(value.strip().upper().replace('D', 'E')) for value in values[1:])
    if not all(map(math.isfinite, xyz)):
        raise ValueError('IGES endpoints must be finite')
    return xyz[:3], xyz[3:]


def horizontal_edge(points, tolerance=0):
    a, b = sorted(points)
    if not all(math.isfinite(v) for p in (a, b) for v in p):
        raise ValueError('IGES endpoints must be finite')
    if not b[0]-a[0] > tolerance or any(abs(a[i]-b[i]) > tolerance for i in (1, 2)):
        raise ValueError('IGES upper edge must run parallel to local X')
    y, z = (a[i]/2 + b[i]/2 for i in (1, 2))
    return (a[0], y, z), (b[0], y, z)


def read_top_edge(path):
    return horizontal_edge(read_line(path))
