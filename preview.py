#!/usr/bin/env python3
"""Draw every pack model on one sheet: 3D models as an isometric render, sprites scaled
up.   python3 preview.py -> release/preview.png"""
import json
import math
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(ROOT, "pack", "assets", "goldencarrotbuff")
MODELS = os.path.join(ASSETS, "models", "item")
TEX = os.path.join(ASSETS, "textures", "item")
OUT = os.path.join(ROOT, "release", "preview.png")

CELL = 110
COLS = 10
SS = 3   # supersampling


def project(x, y, z, scale):
    sx = (x - z) * math.cos(math.radians(30)) * scale
    sy = (x + z) * math.sin(math.radians(30)) * scale - y * scale
    return sx, sy


def swatch_colour(tex, uv):
    x1, y1, x2, y2 = [c * tex.width / 16 for c in uv]
    crop = tex.crop((int(x1), int(y1), int(max(x1 + 1, x2)), int(max(y1 + 1, y2)))).convert("RGB")
    px = list(crop.getdata())
    return tuple(sum(p[i] for p in px) // len(px) for i in range(3))


def draw_model(draw, ox, oy, model, tex, scale):
    boxes = sorted(model["elements"], key=lambda e: (e["from"][0] + e["from"][2] + e["from"][1] * 0.6))
    for e in boxes:
        x1, y1, z1 = e["from"]
        x2, y2, z2 = e["to"]
        f = e["faces"]
        top = [project(x1, y2, z1, scale), project(x2, y2, z1, scale), project(x2, y2, z2, scale), project(x1, y2, z2, scale)]
        south = [project(x1, y1, z2, scale), project(x2, y1, z2, scale), project(x2, y2, z2, scale), project(x1, y2, z2, scale)]
        east = [project(x2, y1, z1, scale), project(x2, y1, z2, scale), project(x2, y2, z2, scale), project(x2, y2, z1, scale)]
        for poly, side, shade in ((top, "up", 1.0), (south, "south", 0.8), (east, "east", 0.62)):
            c = swatch_colour(tex, f[side]["uv"])
            c = tuple(int(v * shade) for v in c)
            draw.polygon([(ox + px, oy + py) for px, py in poly], fill=c)


def main():
    names = sorted(n[:-5] for n in os.listdir(MODELS))
    rows = (len(names) + COLS - 1) // COLS
    W, H = COLS * CELL, rows * (CELL + 14)
    sheet = Image.new("RGB", (W * SS, H * SS), (60, 60, 60))
    draw = ImageDraw.Draw(sheet)
    for i, name in enumerate(names):
        model = json.load(open(os.path.join(MODELS, name + ".json")))
        tex = Image.open(os.path.join(TEX, name + ".png"))
        cx = ((i % COLS) * CELL + CELL // 2) * SS
        cy = ((i // COLS) * (CELL + 14) + CELL // 2 + 22) * SS
        if "elements" in model:
            draw_model(draw, cx, cy, model, tex, 3.0 * SS)
        else:
            big = tex.convert("RGBA").resize((16 * 5 * SS, 16 * 5 * SS), Image.NEAREST)
            sheet.paste(big, (cx - 40 * SS, cy - 60 * SS), big)
    sheet = sheet.resize((W, H), Image.LANCZOS)
    draw = ImageDraw.Draw(sheet)
    for i, name in enumerate(names):
        cx = (i % COLS) * CELL + CELL // 2
        cy = (i // COLS) * (CELL + 14) + CELL - 4
        label = name.replace("_", " ")[:18]
        draw.text((cx - len(label) * 3, cy), label, fill=(230, 230, 230))
    sheet.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
