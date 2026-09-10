#!/usr/bin/env python3
"""Voxel-sculpted 3D models for the foods.

Each food is built from solid primitives on a 32x32x32 grid (half-unit voxels, so the
model still fits Minecraft's 16-unit item box): spheres, ellipsoids, rounded boxes,
cylinders, cones and tori, each painted with a palette role. The voxels are then
greedily merged into as few cuboids as possible and written as a Minecraft model,
every face mapped onto a colour swatch in the food's texture.

The result is the chunky, rounded voxel look: a real donut is a torus, an apple is a
sphere with a stem, a bottle is a stack of cylinders with the drink inside.
"""
import math
import random

from PIL import Image

G = 32            # grid size; one voxel is half a Minecraft unit
SCALE = 16.0 / G

# Colour roles and where their swatch sits in the 64x64 texture (16x16 each).
SWATCH = 16
ROLE_SLOTS = {}   # filled per model from the palette order


# ---------------------------------------------------------------------------------
# A voxel volume
# ---------------------------------------------------------------------------------
class Volume:
    def __init__(self):
        self.v = {}   # (x, y, z) -> role

    def _put(self, x, y, z, role):
        if 0 <= x < G and 0 <= y < G and 0 <= z < G:
            self.v[(x, y, z)] = role

    def each(self, fn, role, bounds=None):
        x0, y0, z0, x1, y1, z1 = bounds or (0, 0, 0, G, G, G)
        for x in range(max(0, int(x0)), min(G, int(math.ceil(x1)))):
            for y in range(max(0, int(y0)), min(G, int(math.ceil(y1)))):
                for z in range(max(0, int(z0)), min(G, int(math.ceil(z1)))):
                    if fn(x + 0.5, y + 0.5, z + 0.5):
                        self._put(x, y, z, role)

    # --- primitives -------------------------------------------------------------------
    def ellipsoid(self, cx, cy, cz, rx, ry, rz, role, p=2.0):
        self.each(lambda x, y, z: (abs((x - cx) / rx) ** p + abs((y - cy) / ry) ** p
                                   + abs((z - cz) / rz) ** p) <= 1.0,
                  role, (cx - rx, cy - ry, cz - rz, cx + rx + 1, cy + ry + 1, cz + rz + 1))

    def sphere(self, cx, cy, cz, r, role):
        self.ellipsoid(cx, cy, cz, r, r, r, role)

    def rbox(self, cx, cy, cz, hx, hy, hz, role, p=4.0):
        """Rounded box (superellipsoid)."""
        self.ellipsoid(cx, cy, cz, hx, hy, hz, role, p=p)

    def box(self, x0, y0, z0, x1, y1, z1, role):
        self.each(lambda x, y, z: x0 <= x <= x1 and y0 <= y <= y1 and z0 <= z <= z1,
                  role, (x0, y0, z0, x1 + 1, y1 + 1, z1 + 1))

    def cyl(self, cx, cz, r, y0, y1, role, rz=None, p=2.0):
        rz = rz or r
        self.each(lambda x, y, z: y0 <= y <= y1 and (abs((x - cx) / r) ** p + abs((z - cz) / rz) ** p) <= 1.0,
                  role, (cx - r, y0, cz - rz, cx + r + 1, y1 + 1, cz + rz + 1))

    def cone(self, cx, cz, r0, r1, y0, y1, role):
        """Frustum: radius r0 at y0, r1 at y1."""
        def f(x, y, z):
            if not (y0 <= y <= y1):
                return False
            t = (y - y0) / max(y1 - y0, 1e-6)
            r = r0 + (r1 - r0) * t
            return (x - cx) ** 2 + (z - cz) ** 2 <= r * r
        rm = max(r0, r1)
        self.each(f, role, (cx - rm, y0, cz - rm, cx + rm + 1, y1 + 1, cz + rm + 1))

    def torus(self, cx, cy, cz, R, r, role, ymin=None, ymax=None):
        def f(x, y, z):
            if ymin is not None and y < ymin:
                return False
            if ymax is not None and y > ymax:
                return False
            q = math.hypot(x - cx, z - cz) - R
            return q * q + (y - cy) ** 2 <= r * r
        self.each(f, role, (cx - R - r, cy - r, cz - R - r, cx + R + r + 1, cy + r + 1, cz + R + r + 1))

    def wedge(self, cx, cz, r, y0, y1, a0, a1, role):
        """Cylinder sector between angles a0..a1 (degrees)."""
        def f(x, y, z):
            if not (y0 <= y <= y1):
                return False
            dx, dz = x - cx, z - cz
            if dx * dx + dz * dz > r * r:
                return False
            a = math.degrees(math.atan2(dz, dx)) % 360
            return a0 <= a <= a1
        self.each(f, role, (cx - r, y0, cz - r, cx + r + 1, y1 + 1, cz + r + 1))

    def stick(self, x0, y0, z0, x1, y1, z1, r, role):
        """A thick line."""
        n = int(max(abs(x1 - x0), abs(y1 - y0), abs(z1 - z0)) * 2) + 1
        for i in range(n + 1):
            t = i / n
            self.sphere(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, z0 + (z1 - z0) * t, r, role)

    def carve(self, fn):
        for k in [k for k in self.v if fn(k[0] + 0.5, k[1] + 0.5, k[2] + 0.5)]:
            del self.v[k]

    def speckle(self, role, count, seed, only=None, y_min=0):
        """Sprinkle `count` surface voxels of an existing role with another colour."""
        rng = random.Random(seed)
        candidates = [k for k, r in self.v.items() if (only is None or r == only) and k[1] >= y_min
                      and (k[0], k[1] + 1, k[2]) not in self.v]
        rng.shuffle(candidates)
        for k in candidates[:count]:
            self.v[k] = role


# ---------------------------------------------------------------------------------
# Greedy meshing: voxels -> cuboids
# ---------------------------------------------------------------------------------
def mesh(volume):
    v = volume.v
    done = set()
    boxes = []
    for key in sorted(v):
        if key in done:
            continue
        x, y, z = key
        role = v[key]

        def ok(px, py, pz):
            return (px, py, pz) in v and v[(px, py, pz)] == role and (px, py, pz) not in done

        # extend along x
        x1 = x
        while ok(x1 + 1, y, z):
            x1 += 1
        # extend along z
        z1 = z
        while all(ok(px, y, z1 + 1) for px in range(x, x1 + 1)):
            z1 += 1
        # extend along y
        y1 = y
        while all(ok(px, y1 + 1, pz) for px in range(x, x1 + 1) for pz in range(z, z1 + 1)):
            y1 += 1
        for px in range(x, x1 + 1):
            for py in range(y, y1 + 1):
                for pz in range(z, z1 + 1):
                    done.add((px, py, pz))
        boxes.append(((x, y, z), (x1 + 1, y1 + 1, z1 + 1), role))
    return boxes


# ---------------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------------
def texture(palette, seed):
    """64x64: a 16x16 dithered swatch per role, in palette order."""
    rng = random.Random(seed)
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    px = img.load()
    for i, (role, base) in enumerate(palette.items()):
        ox, oy = (i % 4) * SWATCH, (i // 4) * SWATCH
        tones = [tuple(int(c * f) for c in base) for f in (0.92, 0.97, 1.0, 1.0, 1.04)]
        for y in range(SWATCH):
            for x in range(SWATCH):
                t = rng.choice(tones)
                px[ox + x, oy + y] = tuple(min(255, c) for c in t) + (255,)
    return img


def model_json(boxes, palette, tex_ref):
    order = list(palette)
    elements = []
    for (x0, y0, z0), (x1, y1, z1), role in boxes:
        i = order.index(role)
        ox, oy = (i % 4) * SWATCH, (i // 4) * SWATCH
        dx, dy, dz = (x1 - x0), (y1 - y0), (z1 - z0)
        faces = {}
        # Minecraft face UVs run 0..16 over the whole texture whatever its size, so
        # texel coordinates on the 64x64 sheet are divided by four.
        u = 16.0 / 64
        for side, (w, h) in {"north": (dx, dy), "south": (dx, dy), "east": (dz, dy), "west": (dz, dy),
                             "up": (dx, dz), "down": (dx, dz)}.items():
            faces[side] = {"uv": [ox * u, oy * u, (ox + min(SWATCH, w)) * u, (oy + min(SWATCH, h)) * u],
                           "texture": "#t"}
        elements.append({"from": [round(x0 * SCALE, 3), round(y0 * SCALE, 3), round(z0 * SCALE, 3)],
                         "to": [round(x1 * SCALE, 3), round(y1 * SCALE, 3), round(z1 * SCALE, 3)],
                         "faces": faces})
    return {
        "credit": "GoldenCarrotBuff, voxel.py",
        "texture_size": [64, 64],
        "textures": {"t": tex_ref, "particle": tex_ref},
        "gui_light": "side",
        "elements": elements,
        "display": {
            "gui": {"rotation": [30, 225, 0], "translation": [0, -1.5, 0], "scale": [0.66, 0.66, 0.66]},
            "ground": {"translation": [0, 3, 0], "scale": [0.4, 0.4, 0.4]},
            "fixed": {"rotation": [-90, 0, 0], "scale": [0.6, 0.6, 0.6]},
            "firstperson_righthand": {"rotation": [0, 45, 0], "translation": [0, 2, 0], "scale": [0.45, 0.45, 0.45]},
            "firstperson_lefthand": {"rotation": [0, 225, 0], "translation": [0, 2, 0], "scale": [0.45, 0.45, 0.45]},
            "thirdperson_righthand": {"rotation": [75, 45, 0], "translation": [0, 2.5, 0], "scale": [0.375, 0.375, 0.375]},
            "thirdperson_lefthand": {"rotation": [75, 45, 0], "translation": [0, 2.5, 0], "scale": [0.375, 0.375, 0.375]},
            "head": {"translation": [0, 10, 0], "scale": [1, 1, 1]},
        },
    }


# ---------------------------------------------------------------------------------
# Shapes. Coordinates are on the 32 grid, y up, standing on y=0, centred on 16,16.
# Roles: main, second, accent, dark (+ glass for bottles).
# ---------------------------------------------------------------------------------
C = 16


def muffin(v):
    v.cone(C, C, 7, 9, 0, 10, "accent")
    for a in range(0, 360, 30):                       # pleats
        x, z = C + 9.2 * math.cos(math.radians(a)), C + 9.2 * math.sin(math.radians(a))
        v.stick(x, 1, z, x, 9, z, 0.9, "second")
    v.ellipsoid(C, 12, C, 11, 6, 11, "main")
    v.sphere(C, 15, C, 7, "main")
    v.speckle("dark", 12, "muffin", only="main", y_min=12)


def loaf(v):
    v.rbox(C, 6, C, 12, 6, 8, "main", p=3.5)
    v.rbox(C, 10, C, 10, 3, 6, "main", p=3)
    for x in (10, 16, 22):
        v.carve(lambda px, py, pz, x=x: abs(px - x) < 1 and py > 10.5 and abs(pz - C) < 5)
    v.speckle("second", 10, "loaf", y_min=8)


def bagel(v):
    v.torus(C, 5, C, 8, 5, "main")
    v.torus(C, 6, C, 8, 4.6, "second", ymin=7)


def croissant(v):
    v.ellipsoid(6, 4, 15, 5, 4, 5, "main")
    v.ellipsoid(12, 5, 11, 5.5, 5, 6, "main")
    v.ellipsoid(19, 5.5, 11, 6, 5.5, 6.5, "main")
    v.ellipsoid(26, 4, 15, 5, 4, 5, "main")
    v.speckle("second", 14, "croissant", y_min=6)


def pie(v):
    v.cone(C, C, 12, 14, 0, 5, "accent")
    v.carve(lambda x, y, z: y > 3 and (x - C) ** 2 + (z - C) ** 2 < 11.5 ** 2)
    v.cyl(C, C, 11.5, 3, 7, "main")
    for k in (7, 13, 19, 25):                          # lattice
        v.box(k, 7, 5, k + 1.5, 8, 27, "second")
        v.box(5, 7, k, 27, 8, k + 1.5, "second")
    v.torus(C, 7, C, 12.5, 1.8, "accent")              # crust rim
    v.carve(lambda x, y, z: (x - C) ** 2 + (z - C) ** 2 > 14.2 ** 2)


def cake(v):
    v.cyl(C, C, 12, 0, 12, "main")
    v.cyl(C, C, 12.2, 5, 6, "second")
    v.cyl(C, C, 12.6, 11, 14, "accent")
    for a in range(0, 360, 45):                        # frosting blobs
        v.sphere(C + 10 * math.cos(math.radians(a)), 14.5, C + 10 * math.sin(math.radians(a)), 2.2, "accent")
    v.sphere(C, 17, C, 2.5, "dark")


def slice_(v):
    v.wedge(6, 26, 24, 0, 12, 270, 330, "main")
    v.wedge(6, 26, 24.3, 5, 6, 270, 330, "second")
    v.wedge(6, 26, 24.3, 11, 14, 270, 330, "accent")
    v.sphere(12, 16, 20, 2.2, "dark")


def steak(v):
    v.ellipsoid(C, 4, C, 13, 4, 9, "main", p=2.6)
    v.ellipsoid(C, 4, C, 13.5, 3.5, 9.5, "accent", p=2.6)
    v.carve(lambda x, y, z: False)
    v.ellipsoid(C, 4.5, C, 12, 3.8, 8, "main", p=2.6)
    for k in (-6, 0, 6):
        v.stick(C + k - 5, 8, C - 6, C + k + 5, 8, C + 6, 0.9, "dark")
    v.speckle("second", 10, "steak", y_min=7)


def drumstick(v):
    v.ellipsoid(19, 8, C, 11, 8, 9, "main")
    v.stick(9, 6, C, 2, 4, C, 1.6, "accent")
    v.sphere(2, 4, C - 1.5, 2.4, "accent")
    v.sphere(2, 4, C + 1.5, 2.4, "accent")
    v.speckle("second", 16, "drumstick", only="main", y_min=8)


def nuggets(v):
    for cx, cz in ((9, 9), (23, 10), (10, 23), (23, 23)):
        v.ellipsoid(cx, 3, cz, 6.5, 3, 5.5, "main", p=2.4)
    v.speckle("second", 20, "nuggets", y_min=4)


def bowl(v):
    v.cone(C, C, 9, 15, 0, 10, "accent")
    v.carve(lambda x, y, z: y > 2 and (x - C) ** 2 + (z - C) ** 2 < (7 + (y - 2) * 0.72) ** 2)
    v.cyl(C, C, 12.6, 3, 8, "main")
    v.sphere(11, 9, 13, 2.2, "second")
    v.sphere(19, 9, 19, 2.4, "second")
    v.sphere(20, 9, 11, 1.8, "dark")
    v.sphere(12, 9, 21, 1.8, "dark")


def bottle(v):
    v.cyl(C, C, 8, 0, 18, "glass")
    v.cyl(C, C, 5, 18, 22, "glass")
    v.cyl(C, C, 4.5, 22, 27, "glass")
    v.carve(lambda x, y, z: 1.5 < y < 17 and (x - C) ** 2 + (z - C) ** 2 < 6.6 ** 2)
    v.cyl(C, C, 6.6, 1.5, 15, "main")
    v.cyl(C, C, 5, 27, 31, "dark")                     # cork
    v.cyl(C, C, 8.4, 6, 11, "second")                  # label band
    v.carve(lambda x, y, z: 6 <= y <= 11 and (x - C) ** 2 + (z - C) ** 2 < 8 ** 2 and z > C - 8.5 and False)


def jar(v):
    v.cyl(C, C, 10, 0, 20, "main")
    v.cyl(C, C, 10.5, 20, 25, "dark")
    v.cyl(C, C, 10.4, 8, 14, "second")
    v.box(11, 9, 4, 21, 13, 6, "accent")               # label


def lollipop(v):
    v.cyl(C, C, 1.2, 0, 16, "accent")
    v.sphere(C, 22, C, 9, "main")
    v.torus(C, 22, C, 6, 1.6, "second")
    v.sphere(C, 22, C, 2.5, "second")
    v.carve(lambda x, y, z: (x - C) ** 2 + (y - 22) ** 2 + (z - C) ** 2 > 9.3 ** 2 and y > 14)


def drop(v):
    v.sphere(C, 9, C, 9, "main")
    v.sphere(C, 16, C, 5, "main")
    v.sphere(C, 20, C, 2.5, "main")
    v.speckle("second", 8, "drop", y_min=6)


def bar(v):
    v.box(4, 0, 9, 27, 4, 22, "main")
    for x in (10, 16, 22):
        v.carve(lambda px, py, pz, x=x: abs(px - x) < 0.8 and py > 3)
    v.carve(lambda x, y, z: abs(z - 15.5) < 0.8 and y > 3)
    v.box(4, 0, 9, 8, 5, 22, "accent")                 # wrapper end


def skewer(v):
    v.stick(4, 2, 28, 28, 26, 4, 1.1, "accent")
    for t, role in ((0.28, "main"), (0.52, "second"), (0.76, "main")):
        v.sphere(4 + 24 * t, 2 + 24 * t, 28 - 24 * t, 5, role)


def fruit(v):
    v.sphere(C, 11, C, 11, "main")
    v.carve(lambda x, y, z: y > 20.5 and (x - C) ** 2 + (z - C) ** 2 < 3 ** 2)
    v.stick(C, 19, C, C, 25, C, 1.1, "dark")
    v.ellipsoid(20, 24, C, 4, 1, 2.5, "second")


def ball(v):
    v.sphere(C, 10, C, 10, "main")
    v.box(11, 0, 4, 21, 8, 28, "second")
    v.carve(lambda x, y, z: (x - C) ** 2 + (y - 10) ** 2 + (z - C) ** 2 > 10.4 ** 2)


def pile(v):
    rng = random.Random("pile")
    roles = ["main", "second", "accent", "dark"]
    for i in range(14):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(0, 9)
        v.ellipsoid(C + d * math.cos(a), 3 + rng.uniform(0, 3), C + d * math.sin(a), 3.2, 2.6, 3.2, roles[i % 4])


def plant(v):
    v.stick(C, 0, C, C, 20, C, 1.2, "dark")
    v.stick(C, 12, C, 10, 16, 20, 1.0, "dark")
    v.stick(C, 8, C, 22, 13, 12, 1.0, "dark")
    for cx, cy, cz in ((C, 24, C), (10, 18, 21), (22, 15, 11), (C, 16, 10)):
        v.sphere(cx, cy, cz, 4.2, "main")
    v.sphere(C, 26, C, 2, "second")


def crystal(v):
    v.cone(C, C, 6, 1, 0, 24, "main")
    v.cone(C + 8, C + 5, 3.5, 0.5, 0, 12, "second")
    v.cone(C - 7, C - 4, 3, 0.5, 0, 9, "second")
    v.cyl(C, C, 11, 0, 2, "accent")


def pizza(v):
    v.cyl(C, C, 15, 0, 3, "accent")
    v.cyl(C, C, 13, 3, 4, "main")
    for cx, cz, role in ((9, 10, "second"), (21, 8, "dark"), (11, 22, "dark"), (23, 21, "second"), (16, 15, "second")):
        v.cyl(cx, cz, 2.6, 4, 5, role)
    v.carve(lambda x, y, z: y > 2.5 and (abs(x - C) < 0.6 or abs(z - C) < 0.6))


def fish(v):
    v.ellipsoid(13, 6, C, 11, 5.5, 4, "main")
    v.each(lambda x, y, z: 22 <= x <= 30 and abs(z - C) <= (x - 22) * 0.7 and abs(y - 6) < 2.2, "second")
    v.sphere(6, 8, C - 3.5, 1.2, "dark")
    v.sphere(6, 8, C + 3.5, 1.2, "dark")
    v.ellipsoid(13, 11, C, 4, 1.5, 1, "second")        # dorsal fin


def sushi(v):
    v.cyl(C, C, 11, 0, 12, "dark")
    v.cyl(C, C, 9, 0, 12.5, "accent")
    v.cyl(C, C, 4, 0, 13, "main")
    v.speckle("second", 6, "sushi", only="main", y_min=12)


def wrap(v):
    v.rbox(C, 5, C, 13, 5, 7, "dark", p=3)
    v.cyl(3, C, 4, 1, 9, "main", rz=6)
    v.cyl(29, C, 4, 1, 9, "main", rz=6)
    v.carve(lambda x, y, z: x < 0 or x > 32)
    v.speckle("second", 6, "wrap", only="main")


def cheese(v):
    v.each(lambda x, y, z: 0 <= y <= 9 and 2 <= x <= 30 and abs(z - C) <= (x - 2) * 0.45, "main")
    for cx, cy, cz in ((14, 7, 14), (22, 5, 20), (24, 9, 12), (10, 4, 16)):
        v.carve(lambda x, y, z, cx=cx, cy=cy, cz=cz: (x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2 < 5.5)
    v.each(lambda x, y, z: 0 <= y <= 1.5 and 2 <= x <= 30 and abs(z - C) <= (x - 2) * 0.45, "accent")


def bacon(v):
    for z0 in (8, 20):
        for x in range(2, 30):
            y = 2 + 2.2 * math.sin(x / 3.0)
            v.box(x, y, z0, x + 1, y + 3, z0 + 5, "main")
            v.box(x, y + 1.2, z0 + 1.5, x + 1, y + 1.9, z0 + 3.5, "second")


def eggs(v):
    v.cyl(C, C, 15, 0, 2, "dark")
    v.ellipsoid(13, 3, 15, 9, 1.6, 7.5, "accent")
    v.sphere(13, 4, 15, 3.6, "second")
    for x in range(20, 29):
        y = 2 + 1.4 * math.sin(x / 2.5)
        v.box(x, y, 20, x + 1, y + 2.4, 26, "main")


def potato(v):
    v.ellipsoid(C, 6, C, 13, 6, 9, "main")
    v.carve(lambda x, y, z: y > 9 and abs(z - C) < 1.5 and abs(x - C) < 9)
    v.ellipsoid(C, 11, C, 7, 2.2, 3, "second")
    v.speckle("accent", 10, "potato", y_min=9)
    v.speckle("dark", 6, "potato2", y_min=9)


def pepper(v):
    v.each(lambda x, y, z: 2 <= y <= 24 and (x - C) ** 2 + (z - C) ** 2 <= (2 + (y - 2) * 0.28) ** 2, "main")
    v.stick(C, 24, C, C + 2, 30, C, 1.1, "dark")
    v.ellipsoid(C, 24.5, C, 5.2, 1.5, 5.2, "second")


def shell(v):
    v.sphere(C, 9, C, 9.5, "main")
    v.carve(lambda x, y, z: y < 0)
    v.torus(C, 12, C, 5.5, 1.5, "second", ymin=11)
    v.torus(C, 15, C, 2.5, 1.2, "second", ymin=14)
    v.ellipsoid(6, 4, C, 5, 4, 5, "accent")


def heart(v):
    v.sphere(11, 12, C, 6.5, "main")
    v.sphere(21, 12, C, 6.5, "main")
    v.each(lambda x, y, z: 0 <= y <= 12 and abs(z - C) <= 4.5 and abs(x - C) <= 10.5 * (y / 12), "main")
    v.speckle("accent", 6, "heart", y_min=13)
    v.sphere(C, 15, C, 2, "second")


def truffle(v):
    v.sphere(C, 9, C, 9, "main")
    rng = random.Random("truffle")
    for _ in range(9):
        a, b = rng.uniform(0, 2 * math.pi), rng.uniform(0, math.pi)
        v.sphere(C + 8.5 * math.sin(b) * math.cos(a), 9 + 8.5 * math.cos(b), C + 8.5 * math.sin(b) * math.sin(a), 2.4, "main")
    v.speckle("second", 24, "truffle", y_min=4)
    v.speckle("accent", 6, "truffle2", y_min=10)


def pudding(v):
    v.cyl(C, C, 14, 0, 2, "accent")
    v.cone(C, C, 10, 7, 2, 14, "main")
    v.cyl(C, C, 7.2, 14, 15, "second")
    v.ellipsoid(C, 16, C, 5, 2, 5, "second")
    v.sphere(C, 19, C, 2, "dark")


def meringue(v):
    v.sphere(C, 4, C, 11, "main")
    v.carve(lambda x, y, z: y < 0)
    v.sphere(C, 11, C, 8, "main")
    v.sphere(C, 17, C, 5.5, "main")
    v.sphere(C, 22, C, 3.2, "main")
    v.speckle("second", 6, "meringue", y_min=10)


def ration(v):
    v.rbox(C, 8, C, 11, 8, 6, "accent", p=3.5)
    v.box(5, 14, 10, 27, 17, 22, "dark")
    v.box(8, 5, 9.5, 24, 11, 10.5, "second")            # label
    v.box(11, 7, 9, 21, 9, 10, "main")


def taco(v):
    v.each(lambda x, y, z: 2 <= y <= 14 and 9 ** 2 <= (x - C) ** 2 + (y - 14) ** 2 <= 12.5 ** 2 and abs(z - C) <= 7, "main")
    for cx, role in ((9, "second"), (13, "dark"), (17, "second"), (21, "dark"), (24, "second")):
        v.sphere(cx, 12, C, 2.4, role)


SHAPES = {
    "muffin": muffin, "loaf": loaf, "bagel": bagel, "croissant": croissant, "pie": pie, "cake": cake,
    "slice": slice_, "steak": steak, "drumstick": drumstick, "nuggets": nuggets, "bowl": bowl,
    "bottle": bottle, "jar": jar, "lollipop": lollipop, "drop": drop, "bar": bar, "skewer": skewer,
    "fruit": fruit, "ball": ball, "pile": pile, "plant": plant, "crystal": crystal, "pizza": pizza,
    "fish": fish, "sushi": sushi, "wrap": wrap, "cheese": cheese, "bacon": bacon, "eggs": eggs,
    "potato": potato, "taco": taco, "pepper": pepper, "shell": shell, "heart": heart,
    "truffle": truffle, "pudding": pudding, "meringue": meringue, "ration": ration,
}

GLASS = (196, 224, 236)


def build(food_id, shape, colours):
    """colours: dict role -> (r, g, b). Returns (model json, texture image, element count)."""
    palette = dict(colours)
    palette.setdefault("glass", GLASS)
    v = Volume()
    SHAPES[shape](v)
    boxes = mesh(v)
    tex_ref = f"goldencarrotbuff:item/{food_id}"
    return model_json(boxes, palette, tex_ref), texture(palette, food_id), len(boxes)
