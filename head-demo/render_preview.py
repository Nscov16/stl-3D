"""Draw two orthographic STL views and a measured side section from the mesh."""
import math
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preview import section
from stl import load_stl


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def render_mesh(draw, mesh, center_x, center_y, yaw_degrees):
    yaw = math.radians(yaw_degrees)
    right = (math.cos(yaw), math.sin(yaw), 0)
    forward = (math.sin(yaw), -math.cos(yaw), 0.22)
    up = (-0.22*math.sin(yaw), 0.22*math.cos(yaw), 1)
    lamp = tuple(f + 0.7*u - 0.4*r for f, u, r in zip(forward, up, right))
    lamp = tuple(x/math.hypot(*lamp) for x in lamp)
    for face in sorted(mesh, key=lambda tri: sum(dot(p, forward) for p in tri)):
        a, b, c = face
        u, v = [tuple(q-p for p, q in zip(a, point)) for point in (b, c)]
        normal = tuple(u[(i+1)%3]*v[(i+2)%3] - u[(i+2)%3]*v[(i+1)%3] for i in range(3))
        if dot(normal, forward) <= 0:
            continue
        lighting = min(1, 0.43 + 0.62*max(0, dot(normal, lamp)/math.hypot(*normal)))
        cut_face = (all(abs(p[2]-43) < 1e-4 for p in face) or
                    any(all(abs(p[1]-y) < 1e-4 for p in face) for y in (7, 21)))
        base = (119, 198, 211) if cut_face else (237, 166, 96)
        color = tuple(round(x*lighting) for x in base)
        draw.polygon([(center_x+5.7*dot(p, right), center_y-5.7*dot(p, up)) for p in face], fill=color)


def main(folder):
    stock = load_stl(folder / 'head-stock.stl')
    finished = load_stl(folder / 'head-finished.stl')
    im = Image.new('RGB', (1480, 625), '#111b27')
    draw = ImageDraw.Draw(im)
    font = ImageFont.load_default(size=23)
    detail = ImageFont.load_default(size=16)
    draw.text((30, 24), 'TEDDY HEAD / MACHINED STL', font=font, fill='#f2f6fa')
    for x, title in ((30, '01  FACE'), (513, '02  REAR THREE-QUARTER'), (996, '03  SIDE SECTION AT X = 0.3 mm')):
        draw.rounded_rectangle((x, 85, x+454, 595), 12, fill='#1b2938')
        draw.text((x+18, 109), title, font=detail, fill='#f2f6fa')
    render_mesh(draw, finished, 257, 511, 8)
    render_mesh(draw, finished, 740, 511, 150)
    draw.text((48, 553), 'Front features retained', font=detail, fill='#c1cfda')
    draw.text((531, 553), 'Blue marks horizontal cut and end walls', font=detail, fill='#a9d8e7')

    def yz(y, z):
        return (1243 + 6.4*y, 511 - 5.5*z)

    draw.rectangle((*yz(7, 64), *yz(21, 0)), fill='#23394d')
    for y in range(-30, 31, 10):
        draw.line([yz(y, 0), yz(y, 64)], fill='#30485c')
        draw.text((yz(y, 0)[0]-10, 521), str(y), fill='#b8c8d5', font=detail)
    for label, mesh, color, weight in (('Stock', stock, '#8194a7', 3), ('Machined', finished, '#71d9e8', 4)):
        for segment in section(mesh, 0, 0.3):
            draw.line([yz(y, z) for _, y, z in segment], fill=color, width=weight)
    draw.line([yz(-33, 20), yz(29, 20)], fill='#d7b754', width=2)
    draw.text((1015, 553), 'Gray stock   /   Blue finished   /   Yellow datum', font=detail, fill='#c1cfda')
    draw.text((1015, 571), 'Front (-Y)                       Rear (+Y)   Y in mm', font=detail, fill='#c1cfda')
    im.save(folder / 'head-preview.png')


if __name__ == '__main__':
    main(Path(sys.argv[1]))
