"""Read the shipped meshes and measure the rear slot independently of the cutter."""
from collections import Counter, defaultdict
from pathlib import Path
import math
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from stl import load_stl

TOL = 0.0001  # mm, synthetic model only
stock, part = (np.array(load_stl(HERE / name)) for name in ('head-stock.stl', 'head-finished.stl'))


def volume(mesh):
    return np.einsum('ij,ij->i', mesh[:, 0], np.cross(mesh[:, 1], mesh[:, 2])).sum() / 6


def face_key(face):
    return tuple(sorted(map(tuple, face)))


def roof(mesh, x, y):
    # Barycentric vertical-ray hits. Shared edges interpolate the same Z.
    a = mesh[:, 0]
    u, v = mesh[:, 1] - a, mesh[:, 2] - a
    det = u[:, 0]*v[:, 1] - u[:, 1]*v[:, 0]
    mask = abs(det) > 1e-12
    a, u, v, det = a[mask], u[mask], v[mask], det[mask]
    s = ((x-a[:, 0])*v[:, 1] - (y-a[:, 1])*v[:, 0]) / det
    t = ((y-a[:, 1])*u[:, 0] - (x-a[:, 0])*u[:, 1]) / det
    hit = (s >= 0) & (t >= 0) & (s+t <= 1)
    return (a[:, 2]+s*u[:, 2]+t*v[:, 2])[hit].max()


edges = defaultdict(list)
for i, face in enumerate(part):
    for a, b in zip(map(tuple, face), map(tuple, np.roll(face, -1, axis=0))):
        edges[min(a,b), max(a,b)].append((i, a < b))
assert all(len(pair)==2 and pair[0][1]!=pair[1][1] for pair in edges.values())
neighbors = defaultdict(list)
for ((a,_),(b,_)) in edges.values():
    neighbors[a].append(b)
    neighbors[b].append(a)
seen, stack = set(), [0]
while stack:
    i = stack.pop()
    if i not in seen:
        seen.add(i)
        stack.extend(neighbors[i])
assert len(seen)==len(part) and volume(part)>0
print('connected shell: faces, edges',len(part),len(edges))
front = [Counter(face_key(f) for f in mesh if f[:,1].max()<0) for mesh in (stock, part)]
assert front[0]==front[1] and sum(front[0].values())==6024
loss = volume(stock)-volume(part)
assert abs(loss-4936.64)<0.01
print('front faces, stock/part/removed mm³',sum(front[0].values()),volume(stock),volume(part),loss)
for y in (6.99,7.01,12,20.99,21.01):
    before, after = roof(stock,0.3,y), roof(part,0.3,y)
    if 7 < y < 21:
        assert abs(after-43)<TOL and before>after
    else:
        assert abs(before-after)<TOL
    print('x=0.3: y, stock/part upper Z',y,before,after)

# Derive the design A/B from the stock slice. On a curved head only a
# portion of each nominal side plane actually intersects material.
zbase = 20 + 7.5
xs=[]
for a,b in zip(stock.transpose(1,0,2), np.roll(stock,-1,axis=1).transpose(1,0,2)):
    crosses=(a[:,2]-zbase)*(b[:,2]-zbase)<0
    aa,bb=a[crosses],b[crosses]
    xs.extend(aa[:,0]+(zbase-aa[:,2])*(bb[:,0]-aa[:,0])/(bb[:,2]-aa[:,2]))
assert not np.any(stock[:,:,2]==zbase)
reference = (min(xs),max(xs))
stock_keys={face_key(f) for f in stock}
new_faces=np.array([f for f in part if face_key(f) not in stock_keys])
n=np.cross(new_faces[:,1]-new_faces[:,0],new_faces[:,2]-new_faces[:,0]); n/=np.linalg.norm(n,axis=1)[:,None]
for y,sign in ((7,1),(21,-1)):
    faces=new_faces[abs(n[:,1]-sign)<1e-9]; assert len(faces) and np.max(abs(faces[:,:,1]-y))<TOL
roof_faces=new_faces[abs(n[:,2]-1)<1e-9]; assert len(roof_faces) and np.max(abs(roof_faces[:,:,2]-43))<TOL
width=np.ptp(roof_faces[:,:,0]); expected=reference[1]-reference[0]-2*(43-zbase)/math.tan(math.radians(53))
assert abs(width-expected)<TOL
print('upper width mm, expected',width,expected)
for sign,xbase in zip((-1,1),reference):
    # Planes parallel to Y with an outward X and upward Z component.
    flank=new_faces[(abs(n[:,1])<1e-9)&(n[:,0]*sign>0.1)&(n[:,2]>0.1)]
    assert len(flank)
    normals=np.cross(flank[:,1]-flank[:,0],flank[:,2]-flank[:,0]); angles=np.degrees(np.arctan2(abs(normals[:,0]),normals[:,2]))
    residual=np.max(abs(flank[:,:,0]-(xbase-sign*(flank[:,:,2]-zbase)/math.tan(math.radians(53)))))
    assert residual<TOL
    print('side, triangles, min/max angle deg, max X error mm',sign,len(flank),angles.min(),angles.max(),residual)
