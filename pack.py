#!/usr/bin/env python3
"""Pixel-art sprites for the 100 foods, packed as a resource pack.

    python3 pack.py            writes pack/ and release/goldencarrotbuff-pack.zip, prints the SHA-1

Every food gets a 16x16 sprite painted the way vanilla items are: a silhouette with a
dark outline, light falling from the top left, a specular glint, then details on top
(berries, grill marks, lattice, bubbles, drips). The game extrudes the sprite into the
usual thin 3D item in hand, exactly like a vanilla apple or bread.

Sprites are built from a handful of painted shapes -- muffin, pie, bottle, bowl,
skewer and so on -- each taking a palette, and each food picks a shape plus its own
colours in LOOKS below.

The server points a food's `item_model` at `goldencarrotbuff:<id>`, which resolves to
  assets/goldencarrotbuff/items/<id>.json          -> model goldencarrotbuff:item/<id>
  assets/goldencarrotbuff/models/item/<id>.json    -> item/generated with the sprite
  assets/goldencarrotbuff/textures/item/<id>.png   -> the sprite
"""
import hashlib
import json
import math
import os
import random
import shutil
import zipfile

from PIL import Image

from foods import FOODS

ROOT = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.join(ROOT, "pack")
NS = "goldencarrotbuff"
ASSETS = os.path.join(PACK, "assets", NS)
ZIP = os.path.join(ROOT, "release", "goldencarrotbuff-pack.zip")

# Resource pack format of 1.21.11 (version.json in the server jar says 75.0).
PACK_FORMAT = 75

S = 16


# ---------------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------------
def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mul(c, f):
    return tuple(max(0, min(255, int(round(v * f)))) for v in c)


def mix(a, b, t):
    return tuple(int(round(a[i] * (1 - t) + b[i] * t)) for i in range(3))


# ---------------------------------------------------------------------------------
# A tiny painter. Shapes are painted as masks, then shaded: light top-left, dark
# bottom-right, a 1px outline, a glint. Details are drawn on top with plain pixels.
# ---------------------------------------------------------------------------------
class Canvas:
    def __init__(self, seed):
        self.px = {}          # (x, y) -> (r, g, b)
        self.rng = random.Random(seed)

    # --- masks -------------------------------------------------------------------
    @staticmethod
    def ellipse(cx, cy, rx, ry):
        return {(x, y) for x in range(S) for y in range(S)
                if ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1.0}

    @staticmethod
    def rect(x1, y1, x2, y2, r=0):
        m = set()
        for x in range(x1, x2):
            for y in range(y1, y2):
                if r:
                    # rounded corners
                    dx = max(x1 + r - x - 1, x - (x2 - r), 0)
                    dy = max(y1 + r - y - 1, y - (y2 - r), 0)
                    if dx * dx + dy * dy > r * r:
                        continue
                m.add((x, y))
        return m

    @staticmethod
    def poly(points):
        m = set()
        n = len(points)
        for x in range(S):
            for y in range(S):
                px, py = x + 0.5, y + 0.5
                inside = False
                for i in range(n):
                    ax, ay = points[i]
                    bx, by = points[(i + 1) % n]
                    if (ay > py) != (by > py):
                        ix = ax + (py - ay) * (bx - ax) / (by - ay)
                        if px < ix:
                            inside = not inside
                if inside:
                    m.add((x, y))
        return m

    # --- painting ------------------------------------------------------------------
    def fill(self, mask, base, outline=True, glint=True, light=0.22, dark=0.28, noise=0.04):
        """Shade a mask: light from the top-left, an outline, and a glint."""
        if not mask:
            return
        xs = [p[0] for p in mask]
        ys = [p[1] for p in mask]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        w, h = max(1, x1 - x0), max(1, y1 - y0)
        lightc, darkc = mul(base, 1 + light), mul(base, 1 - dark)
        for (x, y) in mask:
            t = ((x - x0) / w + (y - y0) / h) / 2
            c = mix(lightc, darkc, t)
            if noise:
                c = mul(c, 1 + self.rng.uniform(-noise, noise))
            self.px[(x, y)] = c
        if outline:
            edge = {(x, y) for (x, y) in mask
                    if any((x + dx, y + dy) not in mask for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
            for p in edge:
                self.px[p] = mul(base, 0.42)
        if glint:
            gx, gy = x0 + max(1, w // 4), y0 + max(1, h // 4)
            for p in ((gx, gy), (gx + 1, gy), (gx, gy + 1)):
                if p in mask and p not in self._edge(mask):
                    self.px[p] = mix(self.px[p], (255, 255, 255), 0.45)

    @staticmethod
    def _edge(mask):
        return {(x, y) for (x, y) in mask
                if any((x + dx, y + dy) not in mask for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}

    def dot(self, x, y, c):
        if 0 <= x < S and 0 <= y < S:
            self.px[(x, y)] = c

    def dots(self, points, c):
        for x, y in points:
            self.dot(x, y, c)

    def line(self, x1, y1, x2, y2, c):
        n = max(abs(x2 - x1), abs(y2 - y1), 1)
        for i in range(n + 1):
            self.dot(round(x1 + (x2 - x1) * i / n), round(y1 + (y2 - y1) * i / n), c)

    def paint(self, mask, c):
        for p in mask:
            self.px[p] = c

    def image(self):
        img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        for (x, y), c in self.px.items():
            img.putpixel((x, y), c + (255,))
        return img


# ---------------------------------------------------------------------------------
# Shapes. Each takes the canvas and a palette dict (main, second, accent, dark).
# ---------------------------------------------------------------------------------
def muffin(c, p):
    cup = c.poly([(4, 8), (12, 8), (11, 15), (5, 15)])
    c.fill(cup, p["accent"], glint=False)
    for x in (6, 8, 10):                                   # pleats
        c.line(x, 9, x, 14, mul(p["accent"], 0.7))
    top = c.ellipse(8, 7.2, 5.6, 4.0)
    c.fill(top, p["main"])
    c.dots([(6, 5), (9, 4), (11, 7), (7, 8)], p["second"])   # berries / chips
    c.dots([(6, 6), (9, 5)], mul(p["second"], 0.6))


def loaf(c, p):
    body = c.rect(2, 5, 14, 13, r=3)
    c.fill(body, p["main"])
    top = c.rect(3, 4, 13, 7, r=2)
    c.fill(top, mul(p["main"], 1.08), outline=False, glint=False)
    for x in (5, 8, 11):                                   # scoring
        c.line(x, 5, x + 1, 6, mul(p["main"], 0.6))
    c.dots([(4, 11), (7, 12), (10, 11)], p["second"])


def bagel(c, p):
    ring = c.ellipse(8, 8, 6.5, 6.0) - c.ellipse(8, 8, 2.2, 2.0)
    c.fill(ring, p["main"])
    c.dots([(5, 5), (9, 4), (12, 8), (6, 11), (10, 12)], p["second"])


def croissant(c, p):
    body = c.poly([(2, 10), (5, 5), (11, 5), (14, 10), (11, 13), (5, 13)])
    c.fill(body, p["main"])
    for x in (5, 8, 11):
        c.line(x, 6, x - 1, 12, mul(p["main"], 0.62))
    c.dots([(7, 7), (9, 7)], mul(p["main"], 1.25))


def pie(c, p):
    dish = c.ellipse(8, 10, 7.5, 4.5)
    c.fill(dish, p["accent"], glint=False)
    filling = c.ellipse(8, 8.5, 6.2, 3.6)
    c.fill(filling, p["main"], outline=False, glint=False)
    lat = mul(p["accent"], 1.1)
    for x in (5, 8, 11):
        c.line(x, 5, x, 12, lat)
    for y in (7, 10):
        c.line(2, y, 14, y, lat)
    rim = c.ellipse(8, 8.5, 6.6, 4.0) - c.ellipse(8, 8.5, 5.6, 3.1)
    c.fill(rim, p["accent"], outline=False, glint=False)


def cake(c, p):
    base = c.rect(2, 7, 14, 14, r=1)
    c.fill(base, p["main"], glint=False)
    c.paint(c.rect(3, 10, 13, 11), p["second"])            # jam layer
    top = c.rect(2, 4, 14, 8, r=2)
    c.fill(top, p["accent"])
    c.dots([(4, 8), (7, 9), (10, 8), (12, 9)], p["accent"])  # drips
    c.dots([(8, 3), (8, 2)], p["dark"])                     # cherry
    c.dot(8, 1, mul(p["dark"], 0.6))


def slice_(c, p):
    wedge = c.poly([(3, 4), (13, 8), (13, 14), (3, 14)])
    c.fill(wedge, p["main"], glint=False)
    c.line(4, 10, 12, 12, p["second"])
    c.line(4, 8, 12, 10, mul(p["main"], 0.7))
    top = c.poly([(3, 3), (13, 7), (13, 9), (3, 5)])
    c.fill(top, p["accent"], outline=False)
    c.dots([(6, 2), (6, 1)], p["dark"])


def steak(c, p):
    body = c.poly([(2, 7), (5, 4), (12, 4), (14, 8), (12, 13), (4, 13)])
    c.fill(body, p["main"])
    grill = mul(p["main"], 0.5)
    c.line(5, 6, 10, 11, grill)
    c.line(8, 5, 12, 9, grill)
    c.dots([(6, 9), (9, 7)], p["second"])
    c.dots([(3, 8), (13, 9)], p["accent"])                  # fat rim


def drumstick(c, p):
    bone = c.rect(2, 10, 8, 12)
    c.fill(bone, p["accent"], glint=False)
    c.fill(c.ellipse(2.5, 11, 1.8, 2.0), p["accent"])
    meat = c.ellipse(10, 7.5, 5.0, 5.0)
    c.fill(meat, p["main"])
    c.dots([(9, 5), (12, 8), (10, 10)], p["second"])


def nuggets(c, p):
    for cx, cy, rx, ry in ((5, 5, 3.4, 2.6), (11, 6, 3.2, 2.8), (6, 11, 3.2, 2.6), (11.5, 11.5, 2.8, 2.4)):
        c.fill(c.ellipse(cx, cy, rx, ry), p["main"])
    c.dots([(4, 5), (11, 5), (6, 11), (12, 11)], p["second"])


def bowl(c, p):
    body = c.poly([(1, 8), (15, 8), (13, 14), (3, 14)])
    c.fill(body, p["accent"], glint=False)
    c.line(2, 12, 14, 12, mul(p["accent"], 0.7))
    soup = c.ellipse(8, 8, 7.0, 2.6)
    c.fill(soup, p["main"], glint=True)
    c.dots([(5, 7), (9, 9), (11, 7)], p["second"])
    c.dots([(7, 8), (12, 8)], p["dark"])


def bottle(c, p):
    glass = rgb("BFD9E8")
    c.fill(c.rect(6, 1, 10, 4), p["dark"], glint=False)       # cork
    body = c.rect(4, 6, 12, 15, r=3) | c.rect(6, 3, 10, 7)
    c.fill(body, glass, light=0.05, dark=0.2, noise=0)
    liquid = c.rect(5, 8, 11, 14, r=2) | c.rect(7, 6, 9, 9)
    c.fill(liquid, p["main"], outline=False, glint=False)
    c.dots([(6, 10), (9, 12)], mul(p["main"], 1.3))           # bubbles
    c.dots([(5, 7), (5, 8)], (240, 250, 255))                 # glass sheen


def jar(c, p):
    c.fill(c.rect(4, 2, 12, 5), p["dark"], glint=False)       # lid
    body = c.rect(3, 4, 13, 15, r=2)
    c.fill(body, p["main"])
    c.fill(c.rect(4, 8, 12, 11), p["second"], outline=False, glint=False)  # label
    c.line(6, 9, 10, 9, mul(p["second"], 0.6))
    c.dots([(4, 6), (4, 7)], (240, 250, 255))


def lollipop(c, p):
    c.line(8, 9, 8, 15, p["accent"])
    c.line(9, 9, 9, 15, mul(p["accent"], 0.8))
    ball = c.ellipse(8.5, 6, 4.8, 4.8)
    c.fill(ball, p["main"])
    swirl = p["second"]
    for x, y in ((6, 4), (8, 3), (10, 4), (11, 6), (10, 8), (8, 9), (6, 8), (5, 6), (8, 6)):
        c.dot(x, y, swirl)


def drop(c, p):
    c.fill(c.ellipse(8, 8.5, 5.0, 4.5), p["main"])
    c.fill(c.ellipse(8, 5.5, 2.5, 2.5), p["main"], outline=False, glint=False)
    c.dots([(6, 5), (7, 4)], mul(p["main"], 1.35))
    c.dots([(8, 9), (9, 10)], p["second"])


def bar(c, p):
    body = c.rect(2, 4, 14, 12, r=1)
    c.fill(body, p["main"], glint=False)
    seg = mul(p["main"], 0.65)
    for x in (5, 8, 11):
        c.line(x, 5, x, 10, seg)
    c.line(3, 8, 12, 8, seg)
    for x in (3, 6, 9, 12):
        c.dot(x, 5, mul(p["main"], 1.3))
    c.fill(c.rect(2, 11, 14, 13), p["accent"], outline=False, glint=False)  # wrapper edge


def skewer(c, p):
    stick = p["accent"]
    c.line(2, 14, 14, 2, stick)
    c.line(3, 14, 15, 3, mul(stick, 0.75))
    for cx, cy, col in ((5, 11, p["main"]), (8, 8, p["second"]), (11, 5, p["main"])):
        c.fill(c.ellipse(cx, cy, 2.6, 2.3), col)
    c.dots([(4, 10), (7, 7), (10, 4)], mul(p["dark"], 1.2))


def fruit(c, p):
    body = c.ellipse(8, 9, 5.8, 5.3)
    c.fill(body, p["main"])
    c.line(8, 3, 8, 5, p["dark"])                              # stem
    c.dots([(9, 3), (10, 2), (11, 2)], p["second"])              # leaf
    c.dot(8, 4, mul(p["dark"], 0.7))


def ball(c, p):
    c.fill(c.ellipse(8, 8.5, 5.8, 5.6), p["main"], noise=0.06)
    c.paint(c.rect(6, 11, 10, 14), p["second"])                  # wrap strip
    c.dots([(6, 6), (10, 8), (8, 10)], mul(p["main"], 0.85))


def pile(c, p):
    for cx, cy, col in ((5, 10, p["main"]), (9, 11, p["second"]), (12, 9, p["accent"]),
                        (7, 7, p["dark"]), (10, 6, p["main"]), (4, 6, p["second"]), (8, 12, p["accent"])):
        c.fill(c.ellipse(cx, cy, 2.2, 1.9), col, glint=False)


def plant(c, p):
    c.line(8, 15, 8, 7, p["dark"])
    c.line(8, 12, 5, 10, p["dark"])
    c.line(8, 10, 11, 8, p["dark"])
    for cx, cy in ((8, 4), (5, 6), (11, 6), (6, 9), (10, 10)):
        c.fill(c.ellipse(cx, cy, 2.2, 2.0), p["main"])
    c.dots([(8, 4), (5, 6), (11, 6)], p["second"])


def crystal(c, p):
    big = c.poly([(8, 1), (12, 7), (10, 14), (6, 14), (4, 7)])
    c.fill(big, p["main"], light=0.35, dark=0.35)
    c.line(8, 2, 7, 13, mul(p["main"], 1.35))                  # facet edge
    small = c.poly([(12, 8), (15, 11), (13, 15), (11, 14)])
    c.fill(small, p["second"], light=0.35, dark=0.35)
    c.paint(c.rect(4, 14, 13, 16), p["accent"])


def pizza(c, p):
    crust = c.ellipse(8, 8, 7.5, 7.5)
    c.fill(crust, p["accent"], glint=False)
    sauce = c.ellipse(8, 8, 6.0, 6.0)
    c.fill(sauce, p["main"], outline=False, glint=False, noise=0.08)
    for cx, cy, col in ((5, 6, p["second"]), (10, 5, p["dark"]), (6, 11, p["dark"]), (11, 10, p["second"]), (8, 8, p["second"])):
        c.fill(c.ellipse(cx, cy, 1.5, 1.5), col, outline=False, glint=False)
    c.line(8, 1, 8, 15, mul(p["accent"], 0.8))                 # cut lines
    c.line(1, 8, 15, 8, mul(p["accent"], 0.8))


def fish(c, p):
    body = c.ellipse(7, 8, 5.5, 3.2)
    c.fill(body, p["main"])
    tail = c.poly([(12, 8), (15, 5), (15, 11)])
    c.fill(tail, p["second"])
    c.dots([(5, 7)], p["dark"])                                  # eye
    c.line(7, 6, 8, 9, mul(p["main"], 0.6))
    c.line(9, 6, 10, 9, mul(p["main"], 0.6))


def sushi(c, p):
    roll = c.ellipse(8, 8, 6.2, 6.2)
    c.fill(roll, p["dark"], glint=False)
    rice = c.ellipse(8, 8, 4.4, 4.4)
    c.fill(rice, p["accent"], outline=False, glint=False, noise=0.08)
    c.fill(c.ellipse(8, 8, 2.0, 2.0), p["main"], outline=False)
    c.dots([(6, 5), (10, 10)], p["second"])


def wrap(c, p):
    body = c.rect(2, 5, 14, 12, r=2)
    c.fill(body, p["dark"])
    c.fill(c.rect(2, 4, 4, 13), p["main"], outline=False, glint=False)
    c.fill(c.rect(12, 4, 14, 13), p["main"], outline=False, glint=False)
    c.dots([(3, 6), (13, 6)], p["second"])
    c.line(6, 6, 10, 6, mul(p["dark"], 1.4))


def cheese(c, p):
    wedge = c.poly([(1, 11), (8, 3), (15, 11), (15, 14), (1, 14)])
    c.fill(wedge, p["main"])
    c.paint(c.rect(2, 12, 14, 14), p["accent"])
    c.dots([(6, 8), (9, 6), (11, 10), (5, 11)], mul(p["main"], 0.7))   # holes


def bacon(c, p):
    for y0 in (3, 9):
        strip = set()
        for x in range(1, 15):
            wave = round(1.2 * math.sin(x / 2.2))
            for y in range(y0 + wave, y0 + wave + 4):
                strip.add((x, y))
        c.fill(strip, p["main"], glint=False)
        for x in range(2, 14):
            c.dot(x, y0 + 1 + round(1.2 * math.sin(x / 2.2)), p["second"])


def eggs(c, p):
    plate = c.ellipse(8, 9, 7.5, 5.5)
    c.fill(plate, p["dark"], glint=False, light=0.1, dark=0.15)
    white = c.ellipse(7, 8, 5.0, 3.5)
    c.fill(white, p["accent"], outline=True)
    c.fill(c.ellipse(7, 8, 2.2, 2.0), p["second"])
    strip = {(x, y) for x in range(10, 15) for y in range(10, 13)}
    c.fill(strip, p["main"], glint=False)


def potato(c, p):
    body = c.ellipse(8, 9, 6.5, 4.5)
    c.fill(body, p["main"])
    c.line(6, 7, 10, 7, p["dark"])                              # split
    c.dots([(6, 5), (7, 4), (8, 5), (9, 4)], p["second"])          # cream
    c.dots([(5, 8), (10, 9), (7, 10)], p["accent"])                 # bits


def pepper(c, p):
    body = c.poly([(6, 4), (10, 4), (11, 8), (9, 14), (8, 15), (6, 9)])
    c.fill(body, p["main"])
    c.line(8, 1, 8, 4, p["dark"])
    c.dots([(9, 1), (10, 2)], p["dark"])
    c.line(7, 5, 7, 11, mul(p["main"], 1.3))


def shell(c, p):
    body = c.ellipse(8, 9, 6.5, 5.5)
    c.fill(body, p["main"])
    for r in (4.5, 2.5):
        ring = c.ellipse(9, 9, r, r - 0.5) - c.ellipse(9, 9, r - 1, r - 1.5)
        c.paint(ring & body, p["second"])
    c.dots([(3, 10), (4, 12)], p["accent"])


def heart(c, p):
    m = c.ellipse(5.5, 6, 3.5, 3.2) | c.ellipse(10.5, 6, 3.5, 3.2) | c.poly([(2, 7), (14, 7), (8, 14)])
    c.fill(m, p["main"])
    c.dots([(5, 5), (6, 4)], p["accent"])
    c.dots([(9, 9), (7, 10)], p["second"])


def truffle(c, p):
    body = c.ellipse(8, 9, 5.5, 5.0)
    c.fill(body, p["main"], noise=0.1)
    for x, y in ((5, 7), (9, 6), (11, 10), (7, 11), (8, 8)):
        c.dot(x, y, p["second"])
    c.dots([(4, 12), (12, 6)], p["accent"])


def pudding(c, p):
    plate = c.ellipse(8, 12, 7.0, 2.5)
    c.fill(plate, p["accent"], glint=False)
    body = c.poly([(4, 11), (12, 11), (11, 4), (5, 4)])
    c.fill(body, p["main"])
    c.fill(c.ellipse(8, 4.5, 3.6, 1.8), p["second"], outline=False)
    c.dots([(8, 2)], p["dark"])


def meringue(c, p):
    for cy, r in ((12, 6.0), (9, 4.6), (6, 3.2), (3.5, 1.8)):
        c.fill(c.ellipse(8, cy, r, r * 0.55 + 0.6), p["main"], noise=0.02)
    c.dots([(6, 12), (10, 9)], p["second"])


def ration(c, p):
    pouch = c.rect(3, 4, 13, 14, r=2)
    c.fill(pouch, p["accent"], glint=False)
    c.paint(c.rect(3, 3, 13, 5), p["dark"])
    c.fill(c.rect(5, 7, 11, 12), p["second"], outline=False, glint=False)
    c.dots([(6, 9), (8, 9), (10, 9)], p["main"])


def taco(c, p):
    shell_ = c.ellipse(8, 9, 6.5, 5.5) - c.ellipse(8, 6, 6.5, 3.5)
    c.fill(shell_, p["main"])
    c.dots([(5, 6), (7, 5), (9, 5), (11, 6)], p["second"])
    c.dots([(6, 6), (8, 5), (10, 6)], p["dark"])


SHAPES = {
    "muffin": muffin, "loaf": loaf, "bagel": bagel, "croissant": croissant, "pie": pie, "cake": cake,
    "slice": slice_, "steak": steak, "drumstick": drumstick, "nuggets": nuggets, "bowl": bowl,
    "bottle": bottle, "jar": jar, "lollipop": lollipop, "drop": drop, "bar": bar, "skewer": skewer,
    "fruit": fruit, "ball": ball, "pile": pile, "plant": plant, "crystal": crystal, "pizza": pizza,
    "fish": fish, "sushi": sushi, "wrap": wrap, "cheese": cheese, "bacon": bacon, "eggs": eggs,
    "potato": potato, "taco": taco, "pepper": pepper, "shell": shell, "heart": heart,
    "truffle": truffle, "pudding": pudding, "meringue": meringue, "ration": ration,
}

# ---------------------------------------------------------------------------------
# Food -> (shape, main, second, accent, dark). Colours are hex RGB.
# ---------------------------------------------------------------------------------
LOOKS = {
    # bakery
    "blueberry_muffin": ("muffin", "D9A066", "4A5BB5", "E8DCC0", "8A5A2B"),
    "honey_bun": ("loaf", "D28B3E", "F2C14E", "F7E1A0", "8A5A2B"),
    "cinnamon_roll": ("bagel", "C98A4B", "F4E6C8", "8A5A2B", "5C3A1E"),
    "chocolate_chip_cookie": ("drop", "C8964E", "3B2314", "3B2314", "8A5A2B"),
    "pumpkin_bread": ("loaf", "C9772E", "E39B4A", "F7D9A8", "7A4A1E"),
    "carrot_cake": ("cake", "C9A46A", "E4782A", "F2F0E6", "E4782A"),
    "chocolate_cake_slice": ("slice", "4A2C17", "7A3F1E", "8A4E2A", "F2A0C0"),
    "apple_pie": ("pie", "D8B268", "C98A4B", "E8C58A", "8A5A2B"),
    "sweet_berry_pie": ("pie", "B3243E", "D9A066", "E8C58A", "6A1424"),
    "glow_berry_tart": ("pie", "F5B231", "D9A066", "E8C58A", "8A5A2B"),
    "cheese_wheel": ("cheese", "F2C14E", "F7DC8A", "D89B2E", "8A5A2B"),
    "toast_with_jam": ("loaf", "C98A4B", "B3243E", "E8C58A", "6A1424"),
    "croissant": ("croissant", "D9A066", "B8773B", "E8C58A", "8A5A2B"),
    "bagel": ("bagel", "C98A4B", "E8C58A", "B8773B", "8A5A2B"),
    # meals
    "wagyu_steak": ("steak", "8A3A2A", "C25C42", "F2E6D8", "4A1E14"),
    "bacon": ("bacon", "B23A2E", "F2D3B8", "7A2A1E", "4A1E14"),
    "bacon_and_eggs": ("eggs", "B23A2E", "F5B231", "F7F3EA", "D9C7B0"),
    "chicken_nuggets": ("nuggets", "D9A050", "E8C58A", "F7E1A0", "8A5A2B"),
    "fried_chicken": ("drumstick", "B87333", "D9A050", "F2E6D8", "8A5A2B"),
    "roast_lamb": ("steak", "8A5A3A", "B8773B", "5DA33A", "4A2C17"),
    "rabbit_pie": ("pie", "A8743B", "D9A066", "E8C58A", "8A5A2B"),
    "fish_and_chips": ("nuggets", "D9A050", "F2C14E", "F7E1A0", "8A5A2B"),
    "salmon_sushi": ("sushi", "F0855A", "F7F3EA", "F7F3EA", "1F4A2A"),
    "reef_roll": ("sushi", "F2A02E", "2E7BD6", "F7F3EA", "1F4A2A"),
    "meat_lovers_pizza": ("pizza", "D8402A", "B23A2E", "E8C58A", "5C3A1E"),
    "veggie_stir_fry": ("bowl", "E4782A", "5DA33A", "6E4A2A", "B8773B"),
    "shepherds_pie": ("pie", "E8C58A", "8A5A3A", "D9A050", "5C3A1E"),
    "hearty_stew": ("bowl", "8A4A2A", "E4782A", "6E4A2A", "5C3A1E"),
    "baked_beans": ("bowl", "B34A2A", "8A3A1E", "6E4A2A", "5C3A1E"),
    "loaded_potato": ("potato", "C9A46A", "F7F3EA", "B23A2E", "5DA33A"),
    "mushroom_risotto": ("bowl", "E8DCC0", "8A6A4A", "6E4A2A", "5C3A1E"),
    "golden_roast": ("drumstick", "F2C14E", "D89B2E", "F7E1A0", "8A5A2B"),
    # soups
    "tomato_soup": ("bowl", "C8332A", "E8DCC0", "6E4A2A", "8A1E1A"),
    "chicken_noodle_soup": ("bowl", "E8B84A", "F7F3EA", "6E4A2A", "E4782A"),
    "pumpkin_soup": ("bowl", "E4782A", "F2C14E", "6E4A2A", "8A5A2B"),
    "fish_chowder": ("bowl", "F2E6D8", "F0855A", "6E4A2A", "5DA33A"),
    "miso_soup": ("bowl", "B8773B", "F7F3EA", "6E4A2A", "1F4A2A"),
    "spicy_chili": ("bowl", "B3243E", "8A3A2A", "6E4A2A", "F5B231"),
    "bone_broth": ("bowl", "D9B98A", "F2E6D8", "6E4A2A", "E4782A"),
    "blaze_stew": ("bowl", "F26A1E", "F5B231", "6E4A2A", "B3243E"),
    # snacks and candy
    "caramel_apple": ("fruit", "B8773B", "5DA33A", "B3243E", "5C3A1E"),
    "candied_carrot": ("pepper", "F2A02E", "5DA33A", "F7E1A0", "1F6A14"),
    "gummy_slime": ("ball", "6BE05A", "9CF58C", "3B8A2E", "2E6A24"),
    "rock_candy": ("crystal", "B58CF2", "E2CCFF", "8A5A2B", "6A3FB5"),
    "red_lollipop": ("lollipop", "F03B3B", "FFFFFF", "F7F3EA", "8A1E1A"),
    "blue_lollipop": ("lollipop", "3B7BFF", "FFFFFF", "F7F3EA", "1E3A8A"),
    "green_lollipop": ("lollipop", "5DFF3B", "FFFFFF", "F7F3EA", "1F6A14"),
    "purple_lollipop": ("lollipop", "B23BFF", "FFFFFF", "F7F3EA", "5A1E8A"),
    "honey_drop": ("drop", "FFC02E", "FFE58A", "D89B2E", "8A5A2B"),
    "chocolate_bar": ("bar", "5C3A1E", "3B2314", "B3243E", "3B2314"),
    "trail_mix": ("pile", "C9A46A", "B3243E", "5DA33A", "5C3A1E"),
    "jerky": ("bacon", "6E3A22", "8A4A2A", "4A2C17", "2E1A0E"),
    "popcorn": ("pile", "F7F3EA", "F2C14E", "E8DCC0", "D89B2E"),
    "rice_ball": ("ball", "F7F3EA", "1F4A2A", "E8DCC0", "1F4A2A"),
    "dried_apricots": ("pile", "F2A02E", "E4782A", "D89B2E", "B8632E"),
    "cactus_candy": ("crystal", "3B8A2E", "9CF58C", "F7E1A0", "1F6A14"),
    # fruit and foraging
    "cherry_blossom_jam": ("jar", "F2A0C0", "F7F3EA", "D9A066", "8A5A2B"),
    "sweet_berry_jam": ("jar", "B3243E", "F7F3EA", "D9A066", "8A5A2B"),
    "glow_berry_jam": ("jar", "F5B231", "F7F3EA", "D9A066", "8A5A2B"),
    "mushroom_skewer": ("skewer", "C8332A", "B8773B", "8A5A2B", "F7F3EA"),
    "pine_nuts": ("pile", "E8DCC0", "C9A46A", "B8773B", "8A5A2B"),
    "lotus_root": ("bagel", "F2E6D8", "D9B98A", "D9B98A", "8A5A2B"),
    "seagrass_salad": ("bowl", "3B8A2E", "5DA33A", "6E4A2A", "1F6A14"),
    "wild_honeycomb": ("cheese", "F2A02E", "FFC02E", "D89B2E", "8A5A2B"),
    "cave_cap": ("plant", "F5B231", "FFE58A", "E8DCC0", "B8773B"),
    "warped_fruit": ("fruit", "1FB5A0", "3BD6C6", "2E7BD6", "0E5A50"),
    "crimson_fruit": ("fruit", "B3243E", "F03B3B", "5C1E2A", "6A1424"),
    "dragon_fruit": ("fruit", "B23BFF", "5DA33A", "F2A0C0", "5A1E8A"),
    # seafood
    "grilled_squid": ("skewer", "6E5A8A", "F2E6D8", "8A5A2B", "3A2E4A"),
    "glow_squid_skewer": ("skewer", "3BD6C6", "9CF5E8", "8A5A2B", "1FB5A0"),
    "nautilus_chowder": ("shell", "F2E6D8", "C9A46A", "B8773B", "6E5A8A"),
    "fried_pufferfish": ("fish", "D9A050", "F2C14E", "F7E1A0", "8A5A2B"),
    "cod_cakes": ("nuggets", "D9A050", "F2E6D8", "F7E1A0", "8A5A2B"),
    "seaweed_wrap": ("wrap", "F0855A", "F7F3EA", "F7F3EA", "1F4A2A"),
    # drinks
    "apple_cider": ("bottle", "C97A1F", "F7F3EA", "D8E8F0", "5C3A1E"),
    "hot_cocoa": ("bottle", "5C3317", "F7F3EA", "D8E8F0", "3B2314"),
    "berry_smoothie": ("bottle", "C2185B", "F7F3EA", "D8E8F0", "6A1424"),
    "melon_juice": ("bottle", "FF5C5C", "5DA33A", "D8E8F0", "8A1E1A"),
    "carrot_juice": ("bottle", "FF8C1A", "F7F3EA", "D8E8F0", "8A5A2B"),
    "milkshake": ("bottle", "F5F0DC", "F2A0C0", "D8E8F0", "8A5A2B"),
    "dandelion_tea": ("bottle", "E0C26A", "F2C14E", "D8E8F0", "8A5A2B"),
    "golden_milk": ("bottle", "FFD700", "F7F3EA", "D8E8F0", "8A5A2B"),
    "lava_shot": ("bottle", "FF4500", "F5B231", "D8E8F0", "3B2314"),
    "slime_soda": ("bottle", "7CFC00", "9CF58C", "D8E8F0", "1F6A14"),
    "ender_tonic": ("bottle", "1B1B3A", "B23BFF", "D8E8F0", "0E0E24"),
    "ghast_milk": ("bottle", "EDEDED", "F7F3EA", "D8E8F0", "8A8A8A"),
    "coffee": ("bottle", "3B2314", "F7F3EA", "D8E8F0", "1E120A"),
    "ocean_breeze": ("bottle", "00CED1", "9CF5E8", "D8E8F0", "0E5A50"),
    # rare
    "sculk_truffle": ("truffle", "0E2A3A", "1FB5A0", "3BD6C6", "071A24"),
    "phantom_pudding": ("pudding", "B8D0E0", "F7F3EA", "E8DCC0", "6E7A8A"),
    "dragon_pepper": ("pepper", "F03B3B", "B23BFF", "F7E1A0", "1F6A14"),
    "golden_sundae": ("pudding", "F7F3EA", "FFD700", "FFD700", "B3243E"),
    "ancient_grain_loaf": ("loaf", "A8743B", "F2A02E", "E8C58A", "5C3A1E"),
    "deep_sea_delicacy": ("heart", "2E7BD6", "3BD6C6", "F7F3EA", "1E3A8A"),
    "breeze_meringue": ("meringue", "F7F3EA", "B8D0E0", "E8DCC0", "8A8A8A"),
    "trial_ration": ("ration", "B23A2E", "D9A050", "E8DCC0", "5C3A1E"),
    "resin_toffee": ("crystal", "E4782A", "F2A02E", "8A5A2B", "B8632E"),
    "spore_salad": ("plant", "F2A0C0", "5DA33A", "E8DCC0", "3B8A2E"),
    "torchflower_omelette": ("eggs", "F26A1E", "F5B231", "F7F3EA", "D9C7B0"),
    "celebration_cake": ("cake", "F7F3EA", "F2A0C0", "FFD700", "B3243E"),
}


def sprite(food_id):
    shape, main, second, accent, dark = LOOKS[food_id]
    palette = {"main": rgb(main), "second": rgb(second), "accent": rgb(accent), "dark": rgb(dark)}
    canvas = Canvas(food_id)
    SHAPES[shape](canvas, palette)
    return canvas.image()


def dump(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def main():
    missing = [f["id"] for f in FOODS if f["id"] not in LOOKS]
    assert not missing, "no look for: " + ", ".join(missing)

    if os.path.isdir(PACK):
        shutil.rmtree(PACK)
    dump(os.path.join(PACK, "pack.mcmeta"), {"pack": {
        "pack_format": PACK_FORMAT,
        "min_format": [PACK_FORMAT, 0],
        "max_format": [PACK_FORMAT, 99],
        "description": "GoldenCarrotBuff: sprites for the 100 foods"}})

    for f in FOODS:
        fid = f["id"]
        tex_path = os.path.join(ASSETS, "textures", "item", fid + ".png")
        os.makedirs(os.path.dirname(tex_path), exist_ok=True)
        sprite(fid).save(tex_path)
        # item/generated: the sprite extruded into a thin 3D item, like every vanilla food.
        dump(os.path.join(ASSETS, "models", "item", fid + ".json"),
             {"parent": "minecraft:item/generated", "textures": {"layer0": f"{NS}:item/{fid}"}})
        dump(os.path.join(ASSETS, "items", fid + ".json"),
             {"model": {"type": "minecraft:model", "model": f"{NS}:item/{fid}"}})

    os.makedirs(os.path.dirname(ZIP), exist_ok=True)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, _, files in os.walk(PACK):
            for name in sorted(files):
                full = os.path.join(dirpath, name)
                z.write(full, os.path.relpath(full, PACK))
    sha1 = hashlib.sha1(open(ZIP, "rb").read()).hexdigest()
    with open(ZIP + ".sha1", "w") as f:
        f.write(sha1 + "\n")
    print(f"{len(FOODS)} sprites, {len(SHAPES)} shapes -> {os.path.relpath(ZIP, ROOT)} "
          f"({os.path.getsize(ZIP) // 1024} KB) sha1 {sha1}")


if __name__ == "__main__":
    main()
