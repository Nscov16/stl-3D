"""Read STL triangle vertices without transforming the exported coordinates."""
import math
from pathlib import Path
import re
import struct


_BINARY_HEADER_SIZE = 84  # 80-byte header plus uint32 triangle count.
_BINARY_FACET = struct.Struct('<12fH')
_DECIMAL = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?')


def _parse_ascii(data):
    text = data.decode('ascii')
    lines = iter((number, line.split()) for number, line in enumerate(text.splitlines(), 1)
                 if line.strip())

    def expect(keywords, *, values=0, name=False, record=None):
        number, words = next(lines, (None, ())) if record is None else record
        label = ' '.join(keywords)
        if number is None:
            raise ValueError(f'ASCII STL ended before {label}')
        actual = tuple(word.lower() for word in words[:len(keywords)])
        args = words[len(keywords):]
        if actual != keywords or (not name and len(args) != values):
            raise ValueError(f'ASCII STL line {number}: expected {label}')
        if values:
            if not all(_DECIMAL.fullmatch(arg) for arg in args):
                raise ValueError(f'ASCII STL line {number}: invalid {label} coordinate')
            numbers = tuple(map(float, args))
            if not all(map(math.isfinite, numbers)):
                raise ValueError(f'ASCII STL line {number}: non-finite {label} coordinate')
            return numbers

    expect(('solid',), name=True)
    triangles = []
    while True:
        # A facet or endsolid starts each block after the header.
        number, words = next(lines, (None, ()))
        if number is None:
            raise ValueError('ASCII STL missing endsolid')
        if words[0].lower() == 'endsolid':
            if next(lines, None) is not None:
                raise ValueError('ASCII STL has content after endsolid')
            return triangles
        expect(('facet', 'normal'), values=3, record=(number, words))
        expect(('outer', 'loop'))
        triangles.append(tuple(expect(('vertex',), values=3) for _ in range(3)))
        expect(('endloop',))
        expect(('endfacet',))


def load_stl(path):
    """Load a nonempty binary or ASCII STL as triangles in its original frame."""
    data = Path(path).read_bytes()
    count = struct.unpack_from('<I', data, 80)[0] if len(data) >= _BINARY_HEADER_SIZE else None
    # Binary headers can start with `solid`; the exact record length takes precedence.
    if count is not None and len(data) == _BINARY_HEADER_SIZE + count * _BINARY_FACET.size:
        triangles = []
        records = memoryview(data)[_BINARY_HEADER_SIZE:]
        for index, facet in enumerate(_BINARY_FACET.iter_unpack(records), 1):
            if not all(map(math.isfinite, facet[:12])):
                raise ValueError(f'Binary STL facet {index}: non-finite normal or vertex coordinate')
            triangles.append((facet[3:6], facet[6:9], facet[9:12]))
    elif data.lstrip()[:6].lower().split() == [b'solid']:
        try:
            triangles = _parse_ascii(data)
        except UnicodeDecodeError:
            raise ValueError('Malformed STL: binary size mismatch or invalid ASCII text') from None
    elif not data.strip():
        raise ValueError('STL file is empty')
    else:
        raise ValueError('Malformed STL: binary size does not match triangle count or ASCII solid is missing')
    if not triangles:
        raise ValueError('STL contains no triangles')
    return triangles
