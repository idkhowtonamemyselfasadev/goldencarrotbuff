#!/usr/bin/env python3
"""Custom 3D models and textures for the 100 foods, packed as a resource pack.

    python3 pack.py            writes pack/ and release/goldencarrotbuff-pack.zip, prints the SHA-1

Every food gets a real 3D model in Minecraft's model format (the same JSON Blockbench
and the Blender plugin export): a handful of cuboids per shape, each face mapped onto a
32x32 texture that carries four dithered colour swatches (main, second, accent, dark).
Shapes are shared archetypes -- muffin, pie, bottle, bowl, skewer and so on -- and each
food picks a shape plus its own four colours below.

The server points a food's `item_model` at `goldencarrotbuff:<id>`, which resolves to
  assets/goldencarrotbuff/items/<id>.json          -> model goldencarrotbuff:item/<id>
  assets/goldencarrotbuff/models/item/<id>.json    -> the cuboids
  assets/goldencarrotbuff/textures/item/<id>.png   -> the swatches
"""
import hashlib
import json
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

# Texture layout: four 16x16 swatches in a 32x32 image.
ROLES = {"main": (0, 0), "second": (16, 0), "accent": (0, 16), "dark": (16, 16)}


# ---------------------------------------------------------------------------------
# Shapes. Each returns a list of (from, to, role) cuboids inside the 16x16x16 box,
# y up, the item standing on y=0 and centred on x=8, z=8.
# ---------------------------------------------------------------------------------
def box(x1, y1, z1, x2, y2, z2, role):
    return ([x1, y1, z1], [x2, y2, z2], role)


def muffin():
    return [box(5, 0, 5, 11, 5, 11, "accent"),        # paper cup
            box(4, 5, 4, 12, 9, 12, "main"),          # dome
            box(5, 9, 5, 11, 10, 11, "main"),
            box(6, 10, 7, 8, 11, 9, "second"),        # a berry on top
            box(9, 8, 5, 11, 9, 7, "second")]


def loaf():
    return [box(3, 0, 5, 13, 5, 11, "main"),
            box(4, 5, 6, 12, 7, 10, "second"),        # crust ridge
            box(6, 7, 7, 10, 8, 9, "accent")]


def bagel():
    return [box(3, 0, 3, 13, 4, 6, "main"), box(3, 0, 10, 13, 4, 13, "main"),
            box(3, 0, 6, 6, 4, 10, "main"), box(10, 0, 6, 13, 4, 10, "main"),
            box(4, 4, 4, 12, 5, 6, "second"), box(4, 4, 10, 12, 5, 12, "second")]


def croissant():
    return [box(2, 0, 6, 6, 4, 10, "main"), box(5, 0, 5, 11, 5, 11, "main"),
            box(10, 0, 6, 14, 4, 10, "main"), box(6, 5, 6, 10, 6, 10, "second")]


def pie():
    return [box(2, 0, 2, 14, 3, 14, "accent"),        # dish
            box(3, 3, 3, 13, 5, 13, "main"),          # filling
            box(3, 5, 3, 13, 6, 5, "second"), box(3, 5, 11, 13, 6, 13, "second"),
            box(3, 5, 5, 5, 6, 11, "second"), box(11, 5, 5, 13, 6, 11, "second"),
            box(7, 5, 3, 9, 6, 13, "second"), box(3, 5, 7, 13, 6, 9, "second")]


def cake():
    return [box(2, 0, 2, 14, 4, 14, "main"),
            box(2, 4, 2, 14, 5, 14, "second"),        # jam layer
            box(2, 5, 2, 14, 9, 14, "main"),
            box(2, 9, 2, 14, 10, 14, "accent"),       # frosting
            box(4, 10, 4, 6, 12, 6, "dark"), box(10, 10, 10, 12, 12, 12, "dark")]


def slice_():
    return [box(4, 0, 4, 12, 4, 12, "main"), box(4, 4, 4, 12, 5, 12, "second"),
            box(4, 5, 4, 12, 8, 12, "main"), box(4, 8, 4, 12, 9, 12, "accent"),
            box(7, 9, 7, 9, 11, 9, "dark")]


def steak():
    return [box(2, 0, 4, 14, 3, 12, "main"), box(3, 3, 5, 13, 4, 11, "second"),
            box(5, 4, 6, 7, 5, 8, "accent"), box(9, 4, 8, 11, 5, 10, "accent")]


def drumstick():
    return [box(2, 1, 7, 8, 3, 9, "accent"),          # bone
            box(1, 0, 6, 3, 4, 10, "accent"),
            box(7, 0, 4, 14, 6, 12, "main"),          # meat
            box(8, 6, 5, 13, 7, 11, "second")]


def nuggets():
    return [box(2, 0, 3, 7, 3, 8, "main"), box(8, 0, 2, 13, 3, 6, "main"),
            box(4, 0, 9, 9, 3, 13, "main"), box(10, 0, 8, 14, 3, 12, "main"),
            box(3, 3, 4, 6, 4, 7, "second"), box(9, 3, 3, 12, 4, 5, "second"),
            box(5, 3, 10, 8, 4, 12, "second")]


def bowl():
    return [box(3, 0, 3, 13, 1, 13, "accent"),        # base
            box(2, 1, 2, 14, 5, 3, "accent"), box(2, 1, 13, 14, 5, 14, "accent"),
            box(2, 1, 3, 3, 5, 13, "accent"), box(13, 1, 3, 14, 5, 13, "accent"),
            box(3, 1, 3, 13, 4, 13, "main"),          # soup
            box(5, 4, 5, 7, 5, 7, "second"), box(9, 4, 8, 11, 5, 10, "second"),
            box(6, 4, 10, 8, 5, 12, "dark")]


def bottle():
    return [box(5, 0, 5, 11, 1, 11, "accent"),        # glass base
            box(5, 1, 5, 11, 8, 11, "main"),          # liquid
            box(6, 8, 6, 10, 10, 10, "accent"),       # shoulder
            box(6, 10, 6, 10, 13, 10, "accent"),      # neck
            box(6, 13, 6, 10, 14, 10, "dark"),        # cork
            box(4, 3, 7, 5, 6, 9, "second"), box(11, 3, 7, 12, 6, 9, "second")]  # label edges


def jar():
    return [box(4, 0, 4, 12, 7, 12, "main"), box(3, 7, 3, 13, 9, 13, "accent"),
            box(4, 9, 4, 12, 10, 12, "dark"), box(4, 2, 3, 12, 5, 4, "second")]


def lollipop():
    return [box(7, 0, 7, 9, 8, 9, "accent"), box(5, 8, 6, 11, 14, 10, "main"),
            box(6, 14, 7, 10, 15, 9, "main"), box(6, 9, 5, 10, 13, 6, "second"),
            box(6, 9, 10, 10, 13, 11, "second")]


def drop():
    return [box(5, 0, 5, 11, 4, 11, "main"), box(6, 4, 6, 10, 7, 10, "main"),
            box(7, 7, 7, 9, 9, 9, "second")]


def bar():
    return [box(2, 0, 5, 14, 2, 11, "main"),
            box(3, 2, 6, 5, 3, 10, "second"), box(6, 2, 6, 8, 3, 10, "second"),
            box(9, 2, 6, 11, 3, 10, "second"), box(12, 2, 6, 13, 3, 10, "second")]


def skewer():
    return [box(7, 0, 7, 9, 15, 9, "accent"), box(5, 3, 5, 11, 6, 11, "main"),
            box(5, 7, 5, 11, 10, 11, "second"), box(5, 11, 5, 11, 14, 11, "main")]


def fruit():
    return [box(4, 0, 4, 12, 7, 12, "main"), box(5, 7, 5, 11, 9, 11, "main"),
            box(7, 9, 7, 9, 12, 9, "dark"), box(9, 10, 8, 12, 11, 9, "second")]


def ball():
    return [box(4, 0, 4, 12, 7, 12, "main"), box(5, 7, 5, 11, 9, 11, "main"),
            box(4, 2, 3, 12, 5, 4, "second")]


def pile():
    return [box(3, 0, 3, 13, 3, 13, "main"), box(4, 3, 4, 12, 5, 12, "main"),
            box(5, 5, 6, 7, 6, 8, "second"), box(8, 5, 5, 10, 6, 7, "accent"),
            box(7, 5, 9, 9, 6, 11, "dark"), box(10, 5, 9, 12, 6, 11, "second")]


def plant():
    return [box(7, 0, 7, 9, 9, 9, "dark"), box(3, 6, 7, 13, 12, 9, "main"),
            box(7, 6, 3, 9, 12, 13, "main"), box(6, 12, 6, 10, 14, 10, "second")]


def crystal():
    return [box(6, 0, 6, 10, 10, 10, "main"), box(7, 10, 7, 9, 12, 9, "second"),
            box(3, 0, 8, 6, 6, 11, "main"), box(10, 0, 4, 13, 5, 7, "second")]


def pizza():
    return [box(1, 0, 1, 15, 2, 15, "accent"), box(2, 2, 2, 14, 3, 14, "main"),
            box(3, 3, 4, 6, 4, 7, "second"), box(9, 3, 3, 12, 4, 6, "dark"),
            box(5, 3, 9, 8, 4, 12, "second"), box(10, 3, 9, 13, 4, 12, "dark")]


def fish():
    return [box(4, 1, 6, 13, 6, 10, "main"), box(1, 0, 7, 4, 7, 9, "second"),
            box(5, 6, 7, 11, 7, 9, "second"), box(11, 3, 5, 12, 4, 6, "dark")]


def sushi():
    return [box(4, 0, 5, 12, 5, 11, "dark"), box(5, 5, 6, 11, 7, 10, "main"),
            box(6, 2, 4, 10, 4, 5, "second")]


def wrap():
    return [box(3, 0, 5, 13, 5, 11, "dark"), box(3, 1, 4, 5, 4, 5, "main"),
            box(11, 1, 4, 13, 4, 5, "main"), box(6, 5, 7, 10, 6, 9, "second")]


def cheese():
    return [box(2, 0, 2, 14, 6, 14, "main"), box(2, 6, 2, 14, 7, 14, "second"),
            box(9, 0, 9, 14, 7, 14, "accent")]


def bacon():
    return [box(2, 0, 6, 14, 1, 10, "main"), box(3, 1, 5, 6, 2, 11, "second"),
            box(7, 1, 5, 10, 2, 11, "main"), box(11, 1, 5, 14, 2, 11, "second"),
            box(2, 2, 7, 14, 3, 9, "accent")]


def eggs():
    return [box(2, 0, 6, 14, 1, 10, "main"), box(3, 1, 3, 9, 2, 9, "accent"),
            box(5, 2, 5, 8, 4, 8, "second"), box(9, 1, 8, 14, 2, 13, "accent"),
            box(10, 2, 9, 13, 4, 12, "second")]


def potato():
    return [box(3, 0, 5, 13, 6, 11, "main"), box(4, 6, 6, 12, 7, 10, "second"),
            box(6, 7, 7, 10, 8, 9, "accent"), box(5, 7, 6, 7, 8, 7, "dark")]


def taco():
    return [box(2, 0, 6, 14, 6, 10, "main"), box(3, 6, 7, 13, 8, 9, "second"),
            box(5, 8, 7, 7, 9, 9, "accent"), box(9, 8, 7, 11, 9, 9, "dark")]


def pepper():
    return [box(6, 0, 6, 10, 9, 10, "main"), box(7, 9, 7, 9, 12, 9, "dark"),
            box(5, 2, 7, 6, 7, 9, "second")]


def shell():
    return [box(3, 0, 4, 13, 5, 12, "main"), box(4, 5, 5, 12, 7, 11, "second"),
            box(6, 7, 6, 10, 9, 10, "main"), box(10, 1, 2, 13, 4, 4, "accent")]


def heart():
    return [box(4, 0, 4, 12, 8, 12, "main"), box(3, 3, 3, 13, 6, 13, "second"),
            box(6, 8, 6, 10, 11, 10, "accent")]


def truffle():
    return [box(4, 0, 4, 12, 6, 12, "main"), box(5, 6, 5, 11, 8, 11, "main"),
            box(3, 2, 6, 4, 5, 10, "second"), box(12, 2, 6, 13, 5, 10, "second"),
            box(6, 8, 6, 10, 9, 10, "accent")]


def pudding():
    return [box(3, 0, 3, 13, 1, 13, "accent"), box(4, 1, 4, 12, 6, 12, "main"),
            box(5, 6, 5, 11, 8, 11, "main"), box(6, 8, 6, 10, 9, 10, "second")]


def meringue():
    return [box(4, 0, 4, 12, 3, 12, "main"), box(5, 3, 5, 11, 6, 11, "main"),
            box(6, 6, 6, 10, 9, 10, "main"), box(7, 9, 7, 9, 11, 9, "second")]


def ration():
    return [box(2, 0, 4, 14, 5, 12, "accent"), box(3, 5, 5, 13, 6, 11, "dark"),
            box(6, 6, 6, 10, 7, 10, "main"), box(4, 1, 3, 12, 4, 4, "second")]


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
    "bacon_and_eggs": ("eggs", "B23A2E", "F5B231", "F7F3EA", "4A1E14"),
    "chicken_nuggets": ("nuggets", "D9A050", "E8C58A", "F7E1A0", "8A5A2B"),
    "fried_chicken": ("drumstick", "B87333", "D9A050", "F2E6D8", "8A5A2B"),
    "roast_lamb": ("steak", "8A5A3A", "B8773B", "5DA33A", "4A2C17"),
    "rabbit_pie": ("pie", "A8743B", "D9A066", "E8C58A", "8A5A2B"),
    "fish_and_chips": ("nuggets", "D9A050", "F2C14E", "F7E1A0", "8A5A2B"),
    "salmon_sushi": ("sushi", "F0855A", "F7F3EA", "F7F3EA", "1F4A2A"),
    "reef_roll": ("sushi", "F2A02E", "F7F3EA", "2E7BD6", "1F4A2A"),
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
    "caramel_apple": ("fruit", "B8773B", "5C3A1E", "B3243E", "5C3A1E"),
    "candied_carrot": ("pepper", "F2A02E", "5DA33A", "F7E1A0", "1F4A2A"),
    "gummy_slime": ("ball", "6BE05A", "9CF58C", "3B8A2E", "2E6A24"),
    "rock_candy": ("crystal", "B58CF2", "E2CCFF", "8A5A2B", "6A3FB5"),
    "red_lollipop": ("lollipop", "F03B3B", "FFFFFF", "F7F3EA", "8A1E1A"),
    "blue_lollipop": ("lollipop", "3B7BFF", "FFFFFF", "F7F3EA", "1E3A8A"),
    "green_lollipop": ("lollipop", "5DFF3B", "FFFFFF", "F7F3EA", "1F6A14"),
    "purple_lollipop": ("lollipop", "B23BFF", "FFFFFF", "F7F3EA", "5A1E8A"),
    "honey_drop": ("drop", "FFC02E", "FFE58A", "D89B2E", "8A5A2B"),
    "chocolate_bar": ("bar", "5C3A1E", "3B2314", "8A5A2B", "3B2314"),
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
    "mushroom_skewer": ("skewer", "C8332A", "B8773B", "8A5A2B", "5C3A1E"),
    "pine_nuts": ("pile", "E8DCC0", "C9A46A", "B8773B", "8A5A2B"),
    "lotus_root": ("bagel", "F2E6D8", "E8DCC0", "D9B98A", "8A5A2B"),
    "seagrass_salad": ("bowl", "3B8A2E", "5DA33A", "6E4A2A", "1F6A14"),
    "wild_honeycomb": ("cheese", "F2A02E", "FFC02E", "D89B2E", "8A5A2B"),
    "cave_cap": ("plant", "F5B231", "FFE58A", "E8DCC0", "B8773B"),
    "warped_fruit": ("fruit", "1FB5A0", "3BD6C6", "2E7BD6", "0E5A50"),
    "crimson_fruit": ("fruit", "B3243E", "F03B3B", "5C1E2A", "6A1424"),
    "dragon_fruit": ("fruit", "B23BFF", "F2A0C0", "5DA33A", "5A1E8A"),
    # seafood
    "grilled_squid": ("skewer", "6E5A8A", "F2E6D8", "8A5A2B", "3A2E4A"),
    "glow_squid_skewer": ("skewer", "3BD6C6", "9CF5E8", "8A5A2B", "1FB5A0"),
    "nautilus_chowder": ("shell", "F2E6D8", "E8DCC0", "B8773B", "6E5A8A"),
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
    "golden_sundae": ("pudding", "F7F3EA", "B3243E", "FFD700", "8A5A2B"),
    "ancient_grain_loaf": ("loaf", "A8743B", "F2A02E", "E8C58A", "5C3A1E"),
    "deep_sea_delicacy": ("heart", "2E7BD6", "3BD6C6", "F7F3EA", "1E3A8A"),
    "breeze_meringue": ("meringue", "F7F3EA", "B8D0E0", "E8DCC0", "8A8A8A"),
    "trial_ration": ("ration", "B23A2E", "D9A050", "E8DCC0", "5C3A1E"),
    "resin_toffee": ("crystal", "E4782A", "F2A02E", "8A5A2B", "B8632E"),
    "spore_salad": ("plant", "F2A0C0", "5DA33A", "E8DCC0", "3B8A2E"),
    "torchflower_omelette": ("eggs", "F5B231", "F26A1E", "F7F3EA", "5DA33A"),
    "celebration_cake": ("cake", "F7F3EA", "F2A0C0", "FFD700", "B3243E"),
}


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def shade(rgb, f):
    return tuple(max(0, min(255, int(c * f))) for c in rgb)


def texture(food_id, colours):
    """32x32: four 16x16 dithered swatches, one per role."""
    rng = random.Random(food_id)
    img = Image.new("RGBA", (32, 32))
    px = img.load()
    for role, (ox, oy) in ROLES.items():
        base = hex_rgb(colours[role])
        tones = [shade(base, 0.86), shade(base, 0.93), base, base, shade(base, 1.07)]
        for y in range(16):
            for x in range(16):
                t = rng.choice(tones)
                # A darker rim on the swatch edge reads as a bevel on every face.
                if x == 0 or y == 15:
                    t = shade(t, 0.8)
                px[ox + x, oy + y] = t + (255,)
    return img


def face_uv(role, w, h):
    ox, oy = ROLES[role]
    return [ox, oy, ox + max(1, min(16, w)), oy + max(1, min(16, h))]


def model(food_id, shape):
    elements = []
    for frm, to, role in SHAPES[shape]():
        dx, dy, dz = to[0] - frm[0], to[1] - frm[1], to[2] - frm[2]
        faces = {}
        for side, (w, h) in {"north": (dx, dy), "south": (dx, dy), "east": (dz, dy), "west": (dz, dy),
                             "up": (dx, dz), "down": (dx, dz)}.items():
            faces[side] = {"uv": face_uv(role, w, h), "texture": "#t"}
        elements.append({"from": frm, "to": to, "faces": faces})
    return {
        "credit": "GoldenCarrotBuff, generated by pack.py",
        "texture_size": [32, 32],
        "textures": {"t": f"{NS}:item/{food_id}", "particle": f"{NS}:item/{food_id}"},
        "gui_light": "side",
        "elements": elements,
        # Held and drawn like a small block: tilted in the inventory, scaled down in hand.
        "display": {
            "gui": {"rotation": [30, 225, 0], "translation": [0, -1, 0], "scale": [0.7, 0.7, 0.7]},
            "ground": {"translation": [0, 3, 0], "scale": [0.4, 0.4, 0.4]},
            "fixed": {"rotation": [-90, 0, 0], "scale": [0.6, 0.6, 0.6]},
            "firstperson_righthand": {"rotation": [0, 45, 0], "translation": [0, 2, 0], "scale": [0.45, 0.45, 0.45]},
            "firstperson_lefthand": {"rotation": [0, 225, 0], "translation": [0, 2, 0], "scale": [0.45, 0.45, 0.45]},
            "thirdperson_righthand": {"rotation": [75, 45, 0], "translation": [0, 2.5, 0], "scale": [0.375, 0.375, 0.375]},
            "thirdperson_lefthand": {"rotation": [75, 45, 0], "translation": [0, 2.5, 0], "scale": [0.375, 0.375, 0.375]},
            "head": {"translation": [0, 10, 0], "scale": [1, 1, 1]},
        },
    }


def dump(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def main():
    missing = [f["id"] for f in FOODS if f["id"] not in LOOKS]
    assert not missing, "no look for: " + ", ".join(missing)
    for fid, (shape, *_rest) in LOOKS.items():
        assert shape in SHAPES, (fid, shape)

    if os.path.isdir(PACK):
        shutil.rmtree(PACK)
    dump(os.path.join(PACK, "pack.mcmeta"), {"pack": {
        "pack_format": PACK_FORMAT,
        "min_format": [PACK_FORMAT, 0],
        "max_format": [PACK_FORMAT, 99],
        "description": "GoldenCarrotBuff: 3D models for the 100 foods"}})

    for f in FOODS:
        fid = f["id"]
        shape, main, second, accent, dark = LOOKS[fid]
        colours = {"main": main, "second": second, "accent": accent, "dark": dark}
        tex_path = os.path.join(ASSETS, "textures", "item", fid + ".png")
        os.makedirs(os.path.dirname(tex_path), exist_ok=True)
        texture(fid, colours).save(tex_path)
        dump(os.path.join(ASSETS, "models", "item", fid + ".json"), model(fid, shape))
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
    print(f"{len(FOODS)} models, {len(SHAPES)} shapes -> {os.path.relpath(ZIP, ROOT)} "
          f"({os.path.getsize(ZIP) // 1024} KB) sha1 {sha1}")


if __name__ == "__main__":
    main()
