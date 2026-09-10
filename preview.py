#!/usr/bin/env python3
"""Tile every sprite of the pack, scaled up, on one sheet.   python3 preview.py -> release/preview.png"""
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(ROOT, "pack", "assets", "goldencarrotbuff", "textures", "item")
OUT = os.path.join(ROOT, "release", "preview.png")

SCALE = 5
CELL = 16 * SCALE + 16
COLS = 10


def main():
    names = sorted(n[:-4] for n in os.listdir(TEX))
    rows = (len(names) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * CELL, rows * (CELL + 12)), (139, 139, 139))
    draw = ImageDraw.Draw(sheet)
    for i, name in enumerate(names):
        img = Image.open(os.path.join(TEX, name + ".png")).convert("RGBA")
        big = img.resize((16 * SCALE, 16 * SCALE), Image.NEAREST)
        x = (i % COLS) * CELL + 8
        y = (i // COLS) * (CELL + 12) + 4
        # inventory-slot grey behind each sprite, like the creative menu
        draw.rectangle((x - 2, y - 2, x + 16 * SCALE + 1, y + 16 * SCALE + 1), fill=(60, 60, 60))
        sheet.paste(big, (x, y), big)
        label = name.replace("_", " ")[:17]
        draw.text((x, y + 16 * SCALE + 3), label, fill=(240, 240, 240))
    sheet.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
