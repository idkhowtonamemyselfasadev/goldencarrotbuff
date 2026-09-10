#!/usr/bin/env python3
"""Draw every pack model as a little isometric picture, all on one sheet, so the shapes
can be eyeballed without a Minecraft client.   python3 preview.py -> release/preview.png"""
import json
import math
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(ROOT, "pack", "assets", "goldencarrotbuff", "models", "item")
TEX = os.path.join(ROOT, "pack", "assets", "goldencarrotbuff", "textures", "item")
OUT = os.path.join(ROOT, "release", "preview.png")

CELL = 96
SCALE = 3.2


def project(x, y, z):
    # Classic 2:1 isometric, camera at the south-east-up corner like the inventory view.
    sx = (x - z) * math.cos(math.radians(30)) * SCALE
    sy = (x + z) * math.sin(math.radians(30)) * SCALE - y * SCALE
    return sx, sy


def face_colour(img, uv, shade):
    x1, y1, x2, y2 = uv
    crop = img.crop((x1, y1, x2, y2)).convert("RGB")
    px = list(crop.getdata())
    r = sum(p[0] for p in px) // len(px)
    g = sum(p[1] for p in px) // len(px)
    b = sum(p[2] for p in px) // len(px)
    return tuple(int(c * shade) for c in (r, g, b))


def draw_model(draw, ox, oy, model, tex):
    boxes = model["elements"]
    # Painter's order: far corners first.
    boxes = sorted(boxes, key=lambda e: (e["from"][0] + e["from"][2] + e["from"][1] * 0.5))
    for e in boxes:
        x1, y1, z1 = e["from"]
        x2, y2, z2 = e["to"]
        f = e["faces"]
        top = [project(x1, y2, z1), project(x2, y2, z1), project(x2, y2, z2), project(x1, y2, z2)]
        south = [project(x1, y1, z2), project(x2, y1, z2), project(x2, y2, z2), project(x1, y2, z2)]
        east = [project(x2, y1, z1), project(x2, y1, z2), project(x2, y2, z2), project(x2, y2, z1)]
        for poly, side, shade in ((top, "up", 1.0), (south, "south", 0.8), (east, "east", 0.62)):
            colour = face_colour(tex, f[side]["uv"], shade)
            draw.polygon([(ox + px, oy + py) for px, py in poly], fill=colour)


def main():
    names = sorted(n[:-5] for n in os.listdir(MODELS))
    cols = 10
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * CELL, rows * (CELL + 14)), (54, 54, 54))
    draw = ImageDraw.Draw(sheet)
    for i, name in enumerate(names):
        model = json.load(open(os.path.join(MODELS, name + ".json")))
        tex = Image.open(os.path.join(TEX, name + ".png"))
        cx = (i % cols) * CELL + CELL // 2
        cy = (i // cols) * (CELL + 14) + CELL // 2 + 18
        draw_model(draw, cx, cy, model, tex)
        label = name.replace("_", " ")[:16]
        draw.text((cx - len(label) * 3, cy + CELL // 2 - 14), label, fill=(220, 220, 220))
    sheet.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
