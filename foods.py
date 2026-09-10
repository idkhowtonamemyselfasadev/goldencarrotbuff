#!/usr/bin/env python3
"""The 100 custom foods, and the generator that turns them into data.

Run it after editing the list:

    python3 foods.py

It writes
  src/main/resources/data/goldencarrotbuff/recipe/<id>.json        one crafting recipe each
  src/main/resources/data/goldencarrotbuff/loot_table/...          the loot pools the mod injects
  src/main/resources/foods.json                                    what the Java side reads
  FOODS.md                                                         the table for humans

Every food is a vanilla item (bread, or the base the look needs) dressed in vanilla
components: item_name, item_model, lore, food, consumable, colours, and a custom_data
tag that says which food it is. A vanilla client renders all of that on its own.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(ROOT, "src", "main", "resources")
NS = "goldencarrotbuff"

# True: every food points at its own 3D model from the resource pack (pack.py), which the
# server hands to every client. False: foods borrow the vanilla item looks named below
# and need no pack at all.
CUSTOM_MODELS = True

# ---------------------------------------------------------------------------------
# Where things are found. Each chest group is one loot table of ours, injected into
# every vanilla table listed. `chance` is the chance the chest gets anything at all.
# ---------------------------------------------------------------------------------
CHEST_GROUPS = {
    "village": dict(chance=0.8, rolls=(1, 2), tables=[
        "chests/village/village_plains_house", "chests/village/village_desert_house",
        "chests/village/village_savanna_house", "chests/village/village_snowy_house",
        "chests/village/village_taiga_house", "chests/village/village_butcher",
        "chests/village/village_shepherd", "chests/village/village_temple",
        "chests/village/village_tannery", "chests/village/village_mason",
        "chests/village/village_toolsmith", "chests/village/village_cartographer",
        "chests/village/village_fletcher", "chests/village/village_armorer",
        "chests/village/village_weaponsmith"]),
    "fisher": dict(chance=0.8, rolls=(1, 2), tables=["chests/village/village_fisher"]),
    "snowy": dict(chance=0.7, rolls=(1, 1), tables=[
        "chests/village/village_snowy_house", "chests/village/village_taiga_house", "chests/igloo_chest"]),
    "dungeon": dict(chance=0.6, rolls=(1, 2), tables=[
        "chests/simple_dungeon", "chests/abandoned_mineshaft", "chests/stronghold_corridor",
        "chests/stronghold_crossing", "chests/stronghold_library", "chests/pillager_outpost",
        "chests/ruined_portal", "chests/spawn_bonus_chest"]),
    "mineshaft": dict(chance=0.5, rolls=(1, 1), tables=["chests/abandoned_mineshaft"]),
    "mansion": dict(chance=0.6, rolls=(1, 2), tables=["chests/woodland_mansion"]),
    "desert": dict(chance=0.6, rolls=(1, 2), tables=["chests/desert_pyramid", "chests/jungle_temple"]),
    "ocean": dict(chance=0.6, rolls=(1, 2), tables=[
        "chests/shipwreck_supply", "chests/shipwreck_treasure", "chests/underwater_ruin_small",
        "chests/underwater_ruin_big"]),
    "treasure": dict(chance=0.7, rolls=(1, 1), tables=["chests/buried_treasure"]),
    "nether": dict(chance=0.6, rolls=(1, 2), tables=[
        "chests/nether_bridge", "chests/bastion_other", "chests/bastion_bridge",
        "chests/bastion_hoglin_stable", "chests/bastion_treasure"]),
    "end": dict(chance=0.6, rolls=(1, 2), tables=["chests/end_city_treasure"]),
    "deep": dict(chance=0.6, rolls=(1, 2), tables=["chests/ancient_city", "chests/ancient_city_ice_box"]),
    "trial": dict(chance=0.6, rolls=(1, 2), tables=[
        "chests/trial_chambers/supply", "chests/trial_chambers/corridor", "chests/trial_chambers/intersection",
        "chests/trial_chambers/intersection_barrel", "chests/trial_chambers/entrance",
        "chests/trial_chambers/reward", "chests/trial_chambers/reward_common", "chests/trial_chambers/reward_rare"]),
    "fishing": dict(chance=0.06, rolls=(1, 1), type="fishing", tables=["gameplay/fishing"]),
    "archaeology": dict(chance=0.2, rolls=(1, 1), type="archaeology", tables=[
        "archaeology/desert_pyramid", "archaeology/desert_well", "archaeology/trail_ruins_common",
        "archaeology/trail_ruins_rare", "archaeology/ocean_ruin_cold", "archaeology/ocean_ruin_warm"]),
}

# Mob drops: mob -> [(food, chance, count)]. Only when a player made the kill.
MOB_DROPS = {
    "cow": [("wagyu_steak", 0.04, 1)],
    "pig": [("bacon", 0.06, 2)],
    "hoglin": [("bacon", 0.12, 3)],
    "chicken": [("chicken_nuggets", 0.06, 2)],
    "sheep": [("roast_lamb", 0.04, 1)],
    "rabbit": [("rabbit_pie", 0.06, 1)],
    "slime": [("gummy_slime", 0.2, 2)],
    "bee": [("honey_drop", 0.3, 2), ("wild_honeycomb", 0.2, 1)],
    "squid": [("grilled_squid", 0.15, 1)],
    "glow_squid": [("glow_squid_skewer", 0.15, 1)],
    "phantom": [("phantom_pudding", 0.2, 1)],
    "zombie": [("jerky", 0.03, 1)],
    "husk": [("dried_apricots", 0.1, 2), ("cactus_candy", 0.1, 2)],
    "drowned": [("seaweed_wrap", 0.04, 1)],
    "stray": [("hot_cocoa", 0.1, 1)],
    "wither_skeleton": [("bone_broth", 0.08, 1)],
    "ghast": [("ghast_milk", 0.1, 1)],
    "blaze": [("blaze_stew", 0.08, 1)],
    "magma_cube": [("lava_shot", 0.05, 1)],
    "strider": [("crimson_fruit", 0.1, 2)],
    "piglin": [("golden_roast", 0.03, 1)],
    "enderman": [("ender_tonic", 0.05, 1)],
    "shulker": [("dragon_fruit", 0.1, 1)],
    "breeze": [("breeze_meringue", 0.25, 2)],
    "polar_bear": [("fish_chowder", 0.2, 1)],
    "fox": [("sweet_berry_jam", 0.15, 1)],
    "panda": [("rice_ball", 0.15, 2)],
    "dolphin": [("ocean_breeze", 0.15, 1)],
    "pillager": [("trail_mix", 0.1, 2), ("jerky", 0.1, 2)],
    "vindicator": [("jerky", 0.1, 2)],
    "ravager": [("meat_lovers_pizza", 0.3, 1)],
    "evoker": [("celebration_cake", 0.2, 1)],
    "warden": [("sculk_truffle", 1.0, 3)],
    "elder_guardian": [("deep_sea_delicacy", 1.0, 2)],
    "ender_dragon": [("dragon_pepper", 1.0, 5)],
}

# Villager trades: (profession, level, food, count, emeralds)
TRADES = [
    ("farmer", 2, "blueberry_muffin", 4, 3),
    ("farmer", 2, "apple_pie", 1, 2),
    ("farmer", 3, "carrot_cake", 1, 5),
    ("farmer", 4, "celebration_cake", 1, 24),
    ("butcher", 2, "bacon", 6, 3),
    ("butcher", 3, "fried_chicken", 2, 4),
    ("butcher", 4, "wagyu_steak", 1, 8),
    ("fisherman", 2, "fish_and_chips", 2, 3),
    ("fisherman", 3, "salmon_sushi", 3, 4),
    ("shepherd", 2, "roast_lamb", 1, 4),
    ("cleric", 3, "golden_milk", 1, 6),
]

# ---------------------------------------------------------------------------------
# The foods.
#
# F(id, name, look, nutrition, saturation, effects, lore, recipe, loot, kind, rarity)
#   look     vanilla item whose model is used ("minecraft:" implied)
#   effects  [(effect, seconds, level)] applied when eaten; level 1 = I
#   recipe   ("shapeless", [ingredients], count)  or  ("shaped", [rows], {key: item}, count)
#   loot     {chest group: weight}
#   kind     food | drink (bottle, drink animation) | soup (bowl back) | jar (bottle back)
#            | candy:RRGGBB (tinted firework star) | potion:RRGGBB (tinted bottle)
#   extra    always | teleport | clear
# ---------------------------------------------------------------------------------
FOODS = []


def F(id, name, look, nutrition, saturation, effects, lore, recipe, loot=None, kind="food",
      rarity="common", extra=(), stack=None):
    FOODS.append(dict(id=id, name=name, look=look, nutrition=nutrition, saturation=saturation,
                      effects=effects, lore=lore, recipe=recipe, loot=loot or {}, kind=kind,
                      rarity=rarity, extra=tuple(extra), stack=stack))


SL = "shapeless"
SH = "shaped"

# --- Bakery ------------------------------------------------------------------------
F("blueberry_muffin", "Blueberry Muffin", "cookie", 6, 7.2, [],
  "Fluffy, warm, and bursting with berries.",
  (SL, ["wheat", "sweet_berries", "egg", "sugar"], 2), {"village": 10})
F("honey_bun", "Honey Bun", "bread", 7, 9.6, [],
  "Sticky enough to glue a villager's mouth shut.",
  (SL, ["bread", "honey_bottle"], 1), {"village": 8})
F("cinnamon_roll", "Cinnamon Roll", "pumpkin_pie", 7, 8.4, [("speed", 20, 1)],
  "Still warm from the oven.",
  (SL, ["wheat", "wheat", "sugar", "cocoa_beans", "egg"], 2), {"village": 6})
F("chocolate_chip_cookie", "Chocolate Chip Cookie", "cookie", 3, 2.4, [],
  "The chips are the good part.",
  (SL, ["cookie", "cocoa_beans", "sugar"], 4), {"village": 10})
F("pumpkin_bread", "Pumpkin Bread", "bread", 8, 9.6, [],
  "Autumn in a loaf.",
  (SL, ["wheat", "wheat", "pumpkin", "sugar"], 2), {"village": 6})
F("carrot_cake", "Carrot Cake", "cake", 10, 12.0, [("haste", 30, 1)],
  "Vegetables count if there is frosting.",
  (SH, ["CMC", "SES", "WWW"], {"C": "carrot", "M": "milk_bucket", "S": "sugar", "E": "egg", "W": "wheat"}, 1),
  {"village": 3, "mansion": 4}, rarity="uncommon")
F("chocolate_cake_slice", "Chocolate Cake Slice", "cake", 6, 6.0, [("jump_boost", 15, 1)],
  "One slice. Maybe two.",
  (SL, ["cake", "cocoa_beans"], 4), {"village": 5})
F("apple_pie", "Apple Pie", "pumpkin_pie", 8, 9.6, [],
  "Best served with a view.",
  (SL, ["apple", "apple", "sugar", "egg", "wheat"], 1), {"village": 8})
F("sweet_berry_pie", "Sweet Berry Pie", "pumpkin_pie", 8, 9.6, [("regeneration", 5, 1)],
  "Worth every thorn.",
  (SL, ["sweet_berries", "sweet_berries", "sugar", "egg", "wheat"], 1), {"village": 6, "snowy": 6})
F("glow_berry_tart", "Glow Berry Tart", "pumpkin_pie", 6, 7.2, [("night_vision", 30, 1)],
  "Faintly glows in the dark.",
  (SL, ["glow_berries", "glow_berries", "sugar", "wheat"], 1), {"mineshaft": 8, "deep": 6}, rarity="uncommon")
F("cheese_wheel", "Cheese Wheel", "honeycomb", 7, 9.6, [],
  "Aged in a cellar nobody remembers digging.",
  (SL, ["milk_bucket", "milk_bucket", "egg"], 2), {"village": 8})
F("toast_with_jam", "Toast with Jam", "bread", 6, 7.2, [],
  "Lands jam side down every time.",
  (SL, ["bread", "sweet_berries", "sugar"], 1), {"village": 8})
F("croissant", "Croissant", "bread", 5, 6.0, [],
  "Flaky. Buttery. Gone in seconds.",
  (SL, ["wheat", "wheat", "milk_bucket", "egg"], 2), {"village": 6})
F("bagel", "Bagel", "bread", 6, 7.2, [],
  "A bread with a hole in its heart.",
  (SL, ["wheat", "wheat", "egg", "sugar"], 2), {"village": 6})

# --- Meals ---------------------------------------------------------------------------
F("wagyu_steak", "Wagyu Steak", "cooked_beef", 10, 16.0, [("strength", 20, 1)],
  "Marbled like a museum floor.",
  (SL, ["cooked_beef", "cooked_beef", "honey_bottle"], 1), {"village": 3}, rarity="uncommon")
F("bacon", "Bacon", "cooked_porkchop", 4, 4.8, [],
  "Crispy strips of joy.",
  (SL, ["cooked_porkchop", "sugar"], 3), {"village": 8})
F("bacon_and_eggs", "Bacon and Eggs", "cooked_porkchop", 9, 12.0, [],
  "The only correct breakfast.",
  (SL, ["cooked_porkchop", "egg", "egg"], 1), {"village": 6})
F("chicken_nuggets", "Chicken Nuggets", "cooked_chicken", 3, 3.6, [],
  "Shaped like nothing in particular.",
  (SL, ["cooked_chicken", "wheat", "egg"], 4), {"village": 8})
F("fried_chicken", "Fried Chicken", "cooked_chicken", 9, 12.0, [],
  "Eleven herbs. Twelve, if you count the dirt.",
  (SL, ["chicken", "wheat", "wheat", "egg"], 1), {"village": 6})
F("roast_lamb", "Roast Lamb", "cooked_mutton", 9, 12.0, [],
  "Sunday dinner, any day of the week.",
  (SL, ["cooked_mutton", "cooked_mutton", "carrot", "potato"], 1), {"village": 5})
F("rabbit_pie", "Rabbit Pie", "pumpkin_pie", 8, 9.6, [("jump_boost", 20, 2)],
  "You will feel a spring in your step.",
  (SL, ["cooked_rabbit", "carrot", "wheat", "egg"], 1), {"snowy": 5, "village": 3})
F("fish_and_chips", "Fish and Chips", "cooked_cod", 9, 12.0, [],
  "Wrapped in yesterday's map.",
  (SL, ["cooked_cod", "baked_potato", "baked_potato"], 1), {"fisher": 8, "ocean": 4})
F("salmon_sushi", "Salmon Sushi", "salmon", 6, 7.2, [("water_breathing", 30, 1)],
  "Rolled tight with kelp.",
  (SL, ["salmon", "dried_kelp", "wheat"], 2), {"fisher": 6, "ocean": 5, "fishing": 8})
F("reef_roll", "Reef Roll", "tropical_fish", 5, 6.0, [("dolphins_grace", 20, 1)],
  "Every colour of the reef in one bite.",
  (SL, ["tropical_fish", "dried_kelp", "wheat"], 2), {"fisher": 5, "ocean": 5, "fishing": 8})
F("meat_lovers_pizza", "Meat Lovers Pizza", "cake", 10, 14.0, [],
  "Three meats. No regrets.",
  (SH, ["BPC", "WWW"], {"B": "cooked_beef", "P": "cooked_porkchop", "C": "cooked_chicken", "W": "wheat"}, 1),
  {"village": 4, "mansion": 4}, rarity="uncommon")
F("veggie_stir_fry", "Veggie Stir Fry", "beetroot_soup", 8, 9.6, [],
  "Tossed hot and fast.",
  (SL, ["carrot", "potato", "beetroot", "brown_mushroom", "bowl"], 1), {"village": 6}, kind="soup")
F("shepherds_pie", "Shepherd's Pie", "pumpkin_pie", 10, 14.0, [("resistance", 15, 1)],
  "Mash on top, comfort underneath.",
  (SL, ["cooked_mutton", "baked_potato", "carrot", "wheat", "egg"], 1), {"village": 4, "snowy": 4})
F("hearty_stew", "Hearty Stew", "rabbit_stew", 12, 16.0, [("regeneration", 5, 1)],
  "Sticks to your ribs.",
  (SL, ["cooked_beef", "potato", "carrot", "brown_mushroom", "bowl"], 1), {"village": 6, "dungeon": 5}, kind="soup")
F("baked_beans", "Baked Beans", "cocoa_beans", 5, 6.0, [],
  "Simmered slow in sweet sauce.",
  (SL, ["cocoa_beans", "sugar", "honey_bottle"], 2), {"village": 5, "dungeon": 6})
F("loaded_potato", "Loaded Potato", "baked_potato", 9, 12.0, [],
  "Bacon, cheese, and more bacon.",
  (SL, ["baked_potato", "cooked_porkchop", "milk_bucket"], 1), {"village": 5})
F("mushroom_risotto", "Mushroom Risotto", "mushroom_stew", 9, 12.0, [],
  "Stirred for an hour by a very patient cook.",
  (SL, ["brown_mushroom", "red_mushroom", "wheat", "milk_bucket", "bowl"], 1), {"village": 5}, kind="soup")
F("golden_roast", "Golden Roast", "cooked_chicken", 10, 14.0, [("absorption", 30, 1), ("regeneration", 5, 1)],
  "Glazed with actual gold.",
  (SL, ["cooked_chicken", "gold_nugget", "gold_nugget", "honey_bottle"], 1),
  {"mansion": 5, "dungeon": 3, "nether": 3}, rarity="rare")

# --- Soups -----------------------------------------------------------------------------
F("tomato_soup", "Tomato Soup", "beetroot_soup", 6, 7.2, [],
  "Red, warm, and suspiciously beetroot-flavoured.",
  (SL, ["beetroot", "beetroot", "sugar", "bowl"], 1), {"village": 6}, kind="soup")
F("chicken_noodle_soup", "Chicken Noodle Soup", "rabbit_stew", 8, 9.6, [("regeneration", 3, 1)],
  "Cures colds and bad moods.",
  (SL, ["cooked_chicken", "wheat", "carrot", "bowl"], 1), {"village": 6, "snowy": 6}, kind="soup")
F("pumpkin_soup", "Pumpkin Soup", "mushroom_stew", 7, 8.4, [],
  "Smooth and a little sweet.",
  (SL, ["pumpkin", "milk_bucket", "bowl"], 1), {"village": 5}, kind="soup")
F("fish_chowder", "Fish Chowder", "mushroom_stew", 8, 9.6, [],
  "Thick enough to stand a spoon in.",
  (SL, ["cooked_cod", "milk_bucket", "potato", "bowl"], 1), {"fisher": 6, "snowy": 4}, kind="soup")
F("miso_soup", "Miso Soup", "suspicious_stew", 6, 7.2, [("water_breathing", 20, 1)],
  "Kelp, sea pickle, and patience.",
  (SL, ["dried_kelp", "dried_kelp", "sea_pickle", "bowl"], 1), {"fisher": 5, "ocean": 5}, kind="soup")
F("spicy_chili", "Spicy Chili", "beetroot_soup", 9, 12.0, [("strength", 15, 1), ("fire_resistance", 30, 1)],
  "Hot enough to walk through lava. Briefly.",
  (SL, ["cooked_beef", "beetroot", "nether_wart", "bowl"], 1), {"village": 3, "nether": 6}, kind="soup", rarity="uncommon")
F("bone_broth", "Bone Broth", "mushroom_stew", 6, 7.2, [("resistance", 10, 1)],
  "Don't ask whose bones.",
  (SL, ["bone", "bone", "carrot", "bowl"], 1), {"dungeon": 6}, kind="soup")
F("blaze_stew", "Blaze Stew", "rabbit_stew", 8, 9.6, [("fire_resistance", 60, 1)],
  "Served at exactly one temperature: too hot.",
  (SL, ["blaze_powder", "cooked_mutton", "red_mushroom", "bowl"], 1), {"nether": 8}, kind="soup", rarity="uncommon")

# --- Snacks and candy -------------------------------------------------------------------
F("caramel_apple", "Caramel Apple", "apple", 6, 7.2, [("speed", 10, 1)],
  "Sticky on the outside, crunchy inside.",
  (SL, ["apple", "sugar", "sugar"], 1), {"village": 6})
F("candied_carrot", "Candied Carrot", "carrot", 5, 6.0, [("night_vision", 10, 1)],
  "Good for the eyes, apparently.",
  (SL, ["carrot", "sugar", "honey_bottle"], 2), {"village": 5})
F("gummy_slime", "Gummy Slime", "slime_ball", 3, 2.4, [("jump_boost", 20, 1), ("slow_falling", 10, 1)],
  "Bouncy all the way down.",
  (SL, ["slime_ball", "sugar", "sweet_berries"], 4), {"dungeon": 4}, rarity="uncommon")
F("rock_candy", "Rock Candy", "amethyst_shard", 4, 2.4, [("haste", 20, 1)],
  "Crystallised sugar, geologist approved.",
  (SL, ["amethyst_shard", "sugar", "sugar"], 3), {"trial": 6, "mineshaft": 4})
F("red_lollipop", "Red Lollipop", "firework_star", 3, 2.0, [("speed", 5, 1)],
  "Cherry, probably.",
  (SL, ["sugar", "sugar", "stick", "red_dye"], 2), {"village": 4}, kind="candy:FF3B3B")
F("blue_lollipop", "Blue Lollipop", "firework_star", 3, 2.0, [("water_breathing", 10, 1)],
  "Tastes blue.",
  (SL, ["sugar", "sugar", "stick", "blue_dye"], 2), {"village": 4}, kind="candy:3B7BFF")
F("green_lollipop", "Green Lollipop", "firework_star", 3, 2.0, [("jump_boost", 10, 1)],
  "Lime, or apple, or both.",
  (SL, ["sugar", "sugar", "stick", "lime_dye"], 2), {"village": 4}, kind="candy:5DFF3B")
F("purple_lollipop", "Purple Lollipop", "firework_star", 3, 2.0, [("luck", 60, 1)],
  "Grape flavoured luck.",
  (SL, ["sugar", "sugar", "stick", "purple_dye"], 2), {"village": 4}, kind="candy:B23BFF")
F("honey_drop", "Honey Drop", "firework_star", 2, 2.0, [("regeneration", 3, 1)],
  "A single golden bead.",
  (SL, ["honey_bottle", "sugar"], 4), {"village": 6}, kind="candy:FFC02E")
F("chocolate_bar", "Chocolate Bar", "firework_star", 4, 3.6, [],
  "Snaps cleanly along the lines.",
  (SL, ["cocoa_beans", "cocoa_beans", "sugar", "milk_bucket"], 2), {"village": 8}, kind="candy:5C3A1E")
F("trail_mix", "Trail Mix", "pumpkin_seeds", 4, 4.8, [],
  "Seeds, berries, and something unidentifiable.",
  (SL, ["pumpkin_seeds", "melon_seeds", "sweet_berries", "dried_kelp"], 2), {"mineshaft": 8, "dungeon": 6})
F("jerky", "Jerky", "leather", 5, 7.2, [],
  "Chewy enough to last the whole trip.",
  (SL, ["beef", "sugar", "dried_kelp"], 2), {"mineshaft": 8, "dungeon": 8, "desert": 6})
F("popcorn", "Popcorn", "wheat_seeds", 3, 2.4, [],
  "Half of it ends up on the floor.",
  (SL, ["wheat_seeds", "wheat_seeds", "sugar"], 4), {"mansion": 6, "village": 5})
F("rice_ball", "Rice Ball", "snowball", 5, 6.0, [],
  "Wrapped in a strip of kelp.",
  (SL, ["wheat", "wheat", "dried_kelp"], 2), {"fisher": 5, "village": 3})
F("dried_apricots", "Dried Apricots", "orange_dye", 4, 4.8, [],
  "Sun-dried on a hot roof.",
  (SL, ["apple", "sugar"], 2), {"desert": 8})
F("cactus_candy", "Cactus Candy", "cactus", 4, 4.8, [],
  "The spines were removed. Mostly.",
  (SL, ["cactus", "sugar"], 2), {"desert": 10})

# --- Fruit and foraging --------------------------------------------------------------
F("cherry_blossom_jam", "Cherry Blossom Jam", "honey_bottle", 6, 7.2, [("regeneration", 5, 1)],
  "Pink petals, pressed and sweetened.",
  (SL, ["pink_petals", "pink_petals", "sugar", "glass_bottle"], 1), {"village": 5}, kind="jar")
F("sweet_berry_jam", "Sweet Berry Jam", "honey_bottle", 6, 7.2, [],
  "The fox's favourite.",
  (SL, ["sweet_berries", "sweet_berries", "sugar", "glass_bottle"], 1), {"village": 6, "snowy": 6}, kind="jar")
F("glow_berry_jam", "Glow Berry Jam", "honey_bottle", 6, 7.2, [("night_vision", 20, 1)],
  "Lights up the pantry.",
  (SL, ["glow_berries", "glow_berries", "sugar", "glass_bottle"], 1), {"mineshaft": 6}, kind="jar")
F("mushroom_skewer", "Mushroom Skewer", "red_mushroom", 6, 7.2, [],
  "Forest floor on a stick.",
  (SL, ["red_mushroom", "brown_mushroom", "stick"], 2), {"snowy": 6, "mansion": 6})
F("pine_nuts", "Pine Nuts", "beetroot_seeds", 3, 3.6, [],
  "Pried out of a cone one by one.",
  (SL, ["spruce_sapling", "bone_meal"], 3), {"snowy": 8})
F("lotus_root", "Lotus Root", "lily_pad", 4, 4.8, [("water_breathing", 15, 1)],
  "Crunchy, with holes all the way through.",
  (SL, ["lily_pad", "lily_pad", "water_bucket"], 2), {"fisher": 6, "fishing": 10})
F("seagrass_salad", "Seagrass Salad", "seagrass", 5, 6.0, [("dolphins_grace", 15, 1)],
  "Tastes like the tide.",
  (SL, ["seagrass", "seagrass", "dried_kelp"], 2), {"ocean": 6, "fishing": 8})
F("wild_honeycomb", "Wild Honeycomb", "honeycomb", 4, 4.8, [("regeneration", 3, 1)],
  "Still has a bee's footprint in it.",
  (SL, ["honeycomb", "honeycomb"], 2), {"village": 4})
F("cave_cap", "Glowing Cave Cap", "shroomlight", 5, 6.0, [("night_vision", 30, 1)],
  "Found where the torches run out.",
  (SL, ["brown_mushroom", "glowstone_dust"], 2), {"mineshaft": 8, "deep": 6})
F("warped_fruit", "Warped Fruit", "warped_fungus", 5, 6.0, [],
  "Eat it and see where you end up.",
  (SL, ["warped_fungus", "chorus_fruit"], 1), {"nether": 6, "end": 6}, rarity="uncommon", extra=("teleport",))
F("crimson_fruit", "Crimson Fruit", "crimson_fungus", 5, 6.0, [("strength", 10, 1)],
  "Pulses faintly. Best not to think about it.",
  (SL, ["crimson_fungus", "nether_wart", "sugar"], 1), {"nether": 8}, rarity="uncommon")
F("dragon_fruit", "Dragon Fruit", "chorus_flower", 7, 8.4, [("slow_falling", 30, 1)],
  "Grown at the edge of the world.",
  (SL, ["popped_chorus_fruit", "chorus_fruit", "sugar"], 1), {"end": 10}, rarity="rare")

# --- Seafood ----------------------------------------------------------------------------
F("grilled_squid", "Grilled Squid", "ink_sac", 6, 7.2, [],
  "Charred tentacles on a stick.",
  (SL, ["ink_sac", "ink_sac", "stick"], 2), {"fisher": 5, "fishing": 6})
F("glow_squid_skewer", "Glow Squid Skewer", "glow_ink_sac", 6, 7.2, [("night_vision", 20, 1), ("glowing", 15, 1)],
  "Makes you shine. Literally.",
  (SL, ["glow_ink_sac", "glow_ink_sac", "stick"], 2), {"fisher": 3, "ocean": 3}, rarity="uncommon")
F("nautilus_chowder", "Nautilus Chowder", "nautilus_shell", 8, 9.6, [("conduit_power", 30, 1)],
  "Served in the shell.",
  (SL, ["nautilus_shell", "cooked_cod", "milk_bucket", "bowl"], 1), {"ocean": 5, "treasure": 5, "fishing": 2}, kind="soup", rarity="rare")
F("fried_pufferfish", "Fried Pufferfish", "pufferfish", 7, 8.4, [("water_breathing", 60, 1)],
  "Prepared by someone who knew what they were doing.",
  (SL, ["pufferfish", "wheat", "egg"], 1), {"fisher": 4, "fishing": 4}, rarity="uncommon")
F("cod_cakes", "Cod Cakes", "cooked_cod", 6, 7.2, [],
  "Golden on the outside, flaky within.",
  (SL, ["cod", "wheat", "egg"], 2), {"fisher": 6, "fishing": 8})
F("seaweed_wrap", "Seaweed Wrap", "dried_kelp", 6, 7.2, [],
  "Salmon, rolled tight in kelp.",
  (SL, ["dried_kelp", "cooked_salmon", "wheat"], 2), {"fisher": 6, "ocean": 4, "fishing": 6})

# --- Drinks -------------------------------------------------------------------------------
F("apple_cider", "Apple Cider", "potion", 4, 4.8, [("regeneration", 3, 1)],
  "Warm and spiced.",
  (SL, ["apple", "apple", "sugar", "glass_bottle"], 1), {"village": 8}, kind="potion:C97A1F")
F("hot_cocoa", "Hot Cocoa", "potion", 4, 4.8, [("regeneration", 5, 1), ("fire_resistance", 10, 1)],
  "Warms you from the inside.",
  (SL, ["cocoa_beans", "milk_bucket", "sugar", "glass_bottle"], 1), {"snowy": 8}, kind="potion:5C3317")
F("berry_smoothie", "Berry Smoothie", "potion", 5, 6.0, [("speed", 20, 1)],
  "Blended with the last of the ice.",
  (SL, ["sweet_berries", "sweet_berries", "milk_bucket", "glass_bottle"], 1), {"village": 6}, kind="potion:C2185B")
F("melon_juice", "Melon Juice", "potion", 4, 4.8, [],
  "Summer in a bottle.",
  (SL, ["melon_slice", "melon_slice", "glass_bottle"], 1), {"village": 6, "desert": 8}, kind="potion:FF5C5C")
F("carrot_juice", "Carrot Juice", "potion", 4, 4.8, [("night_vision", 30, 1)],
  "See in the dark. Taste the orange.",
  (SL, ["carrot", "carrot", "glass_bottle"], 1), {"village": 5}, kind="potion:FF8C1A")
F("milkshake", "Milkshake", "potion", 5, 6.0, [],
  "Thick enough to need a wide straw.",
  (SL, ["milk_bucket", "sugar", "snowball", "glass_bottle"], 1), {"village": 5}, kind="potion:F5F0DC")
F("dandelion_tea", "Dandelion Iced Tea", "potion", 3, 2.4, [("speed", 10, 1)],
  "Brewed from weeds, and proud of it.",
  (SL, ["dandelion", "ice", "glass_bottle"], 1), {"village": 5}, kind="potion:E0C26A")
F("golden_milk", "Golden Milk", "potion", 6, 7.2, [("absorption", 60, 1), ("regeneration", 5, 1)],
  "Shimmers when you swirl it.",
  (SL, ["milk_bucket", "gold_nugget", "honey_bottle", "glass_bottle"], 1), {"village": 3, "mansion": 4},
  kind="potion:FFD700", rarity="uncommon")
F("lava_shot", "Lava Shot", "potion", 2, 1.0, [("fire_resistance", 90, 1), ("strength", 10, 1)],
  "Do not sip. Do not savour.",
  (SL, ["magma_cream", "blaze_powder", "glass_bottle"], 1), {"nether": 8}, kind="potion:FF4500", rarity="rare")
F("slime_soda", "Slime Soda", "potion", 3, 2.4, [("jump_boost", 30, 2)],
  "Fizzes green. Bounces you higher.",
  (SL, ["slime_ball", "sugar", "glass_bottle"], 1), {"dungeon": 5}, kind="potion:7CFC00")
F("ender_tonic", "Ender Tonic", "potion", 2, 1.0, [("slow_falling", 20, 1)],
  "Drink it and hold on.",
  (SL, ["ender_pearl", "sugar", "glass_bottle"], 1), {"end": 8, "dungeon": 3}, kind="potion:1B1B3A", rarity="rare",
  extra=("teleport",))
F("ghast_milk", "Ghast Milk", "potion", 4, 4.8, [("regeneration", 5, 1)],
  "Washes everything away. Everything.",
  (SL, ["ghast_tear", "milk_bucket", "glass_bottle"], 1), {"nether": 4}, kind="potion:EDEDED", rarity="rare",
  extra=("clear",))
F("coffee", "Coffee", "potion", 3, 2.4, [("speed", 30, 1), ("haste", 30, 1)],
  "The mine digs itself.",
  (SL, ["cocoa_beans", "cocoa_beans", "water_bucket", "glass_bottle"], 1), {"village": 6, "mansion": 6},
  kind="potion:3B2314")
F("ocean_breeze", "Ocean Breeze", "potion", 4, 4.8, [("dolphins_grace", 30, 1), ("water_breathing", 30, 1)],
  "Salt, spray, and a hint of pickle.",
  (SL, ["prismarine_crystals", "sea_pickle", "glass_bottle"], 1), {"ocean": 6, "treasure": 4, "fishing": 3},
  kind="potion:00CED1", rarity="uncommon")

# --- Rare and legendary -----------------------------------------------------------------
F("sculk_truffle", "Sculk Truffle", "sculk", 8, 9.6, [("resistance", 15, 1), ("strength", 15, 1)],
  "Dug up where nothing should grow.",
  (SL, ["echo_shard", "brown_mushroom", "sugar"], 1), {"deep": 12}, rarity="epic", extra=("always",))
F("phantom_pudding", "Phantom Pudding", "phantom_membrane", 6, 7.2, [("slow_falling", 60, 1), ("night_vision", 30, 1)],
  "Light as air. Lighter, actually.",
  (SL, ["phantom_membrane", "milk_bucket", "sugar", "egg"], 1), {"mansion": 3}, rarity="rare")
F("dragon_pepper", "Dragon Pepper", "fire_charge", 4, 4.8, [("strength", 20, 2), ("fire_resistance", 20, 1)],
  "Ripened in dragon's breath.",
  (SL, ["dragon_breath", "beetroot", "sugar"], 1), {"end": 8}, rarity="epic")
F("golden_sundae", "Golden Sundae", "golden_apple", 8, 9.6, [("absorption", 60, 2), ("regeneration", 10, 1)],
  "Ice cream, but make it expensive.",
  (SL, ["milk_bucket", "gold_ingot", "sugar", "sweet_berries"], 1), {"nether": 4, "end": 5}, rarity="epic",
  extra=("always",))
F("ancient_grain_loaf", "Ancient Grain Loaf", "bread", 8, 12.0, [("luck", 120, 1)],
  "Baked from seeds a sniffer dug up.",
  (SL, ["wheat", "torchflower_seeds", "egg", "milk_bucket"], 1), {"archaeology": 15}, rarity="rare")
F("deep_sea_delicacy", "Deep Sea Delicacy", "heart_of_the_sea", 10, 14.0, [("conduit_power", 120, 1), ("dolphins_grace", 60, 1)],
  "Only the old guardians know the recipe.",
  (SL, ["nautilus_shell", "prismarine_crystals", "cooked_salmon", "sugar"], 1), {"treasure": 10, "ocean": 3, "fishing": 1},
  rarity="epic")
F("breeze_meringue", "Breeze Meringue", "wind_charge", 5, 6.0, [("jump_boost", 30, 2), ("slow_falling", 30, 1)],
  "Whipped by an actual breeze.",
  (SL, ["breeze_rod", "egg", "sugar"], 2), {"trial": 10}, rarity="rare")
F("trial_ration", "Trial Ration", "cooked_rabbit", 10, 16.0, [("resistance", 10, 1), ("absorption", 30, 1)],
  "Packed for whoever makes it through.",
  (SL, ["cooked_beef", "cooked_chicken", "bread", "glow_berries"], 1), {"trial": 12}, rarity="uncommon")
F("resin_toffee", "Resin Toffee", "resin_clump", 5, 6.0, [("haste", 60, 1)],
  "Chewy, amber, and faintly creaky.",
  (SL, ["resin_clump", "sugar", "honey_bottle"], 3), {"village": 3, "mansion": 4}, rarity="uncommon")
F("spore_salad", "Spore Salad", "spore_blossom", 6, 7.2, [("regeneration", 10, 1)],
  "Picked from the ceiling of a lush cave.",
  (SL, ["spore_blossom", "hanging_roots", "sweet_berries"], 1), {"mineshaft": 4, "deep": 4}, rarity="uncommon")
F("torchflower_omelette", "Torchflower Omelette", "torchflower", 8, 9.6, [("fire_resistance", 30, 1)],
  "Folded around a flower that was once thought lost.",
  (SL, ["torchflower", "egg", "egg", "milk_bucket"], 1), {"archaeology": 8}, rarity="rare")
F("celebration_cake", "Celebration Cake", "cake", 12, 16.0, [("regeneration", 10, 1), ("absorption", 60, 1), ("speed", 30, 1)],
  "Someone did something worth celebrating.",
  (SH, ["SMS", "EGE", "WWW"], {"S": "sugar", "M": "milk_bucket", "E": "egg", "G": "golden_apple", "W": "wheat"}, 1),
  {"mansion": 3, "end": 3}, rarity="epic", extra=("always",))

# ---------------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------------
BASE = "minecraft:bread"


def mc(name):
    return name if ":" in name or name.startswith("#") else "minecraft:" + name


def components(food):
    kind = food["kind"]
    tint = None
    if ":" in kind:
        kind, tint = kind.split(":", 1)
        tint = int(tint, 16)
    drink = kind in ("drink", "potion")
    effects = [{"type": "minecraft:apply_effects",
                "effects": [{"id": mc(e), "duration": int(s * 20), "amplifier": lvl - 1} for e, s, lvl in food["effects"]],
                "probability": 1.0}] if food["effects"] else []
    if "clear" in food["extra"]:
        effects.insert(0, {"type": "minecraft:clear_all_effects"})
    if "teleport" in food["extra"]:
        effects.append({"type": "minecraft:teleport_randomly", "diameter": 16.0})
    c = {
        "minecraft:custom_data": {"gcb_food": food["id"]},
        "minecraft:item_name": food["name"],
        "minecraft:item_model": f"{NS}:{food['id']}" if CUSTOM_MODELS else mc(food["look"]),
        "minecraft:lore": [{"text": food["lore"], "color": "gray", "italic": False}],
        "minecraft:rarity": food["rarity"],
        "minecraft:food": {"nutrition": food["nutrition"], "saturation": food["saturation"],
                           "can_always_eat": "always" in food["extra"]},
        "minecraft:consumable": {
            "consume_seconds": 1.6,
            "animation": "drink" if drink else "eat",
            "sound": "minecraft:entity.generic.drink" if drink else "minecraft:entity.generic.eat",
            "has_consume_particles": not drink,
            "on_consume_effects": effects,
        },
    }
    hidden = []
    if CUSTOM_MODELS:
        # The pack model carries its own colours; nothing vanilla needs tinting or hiding.
        kind = {"potion": "drink", "candy": "food"}.get(kind, kind)
    if kind == "potion":
        c["minecraft:potion_contents"] = {"custom_color": tint}
        hidden.append("minecraft:potion_contents")
    if kind == "candy":
        c["minecraft:firework_explosion"] = {"shape": "small_ball", "colors": [tint], "fade_colors": [],
                                             "has_trail": False, "has_twinkle": False}
        hidden.append("minecraft:firework_explosion")
    if food["look"] == "suspicious_stew" and not CUSTOM_MODELS:
        c["minecraft:suspicious_stew_effects"] = []
        hidden.append("minecraft:suspicious_stew_effects")
    if hidden:
        c["minecraft:tooltip_display"] = {"hide_tooltip": False, "hidden_components": hidden}
    if kind in ("drink", "potion", "jar"):
        c["minecraft:use_remainder"] = {"id": "minecraft:glass_bottle", "count": 1}
        c["minecraft:max_stack_size"] = 16
    if kind == "soup":
        c["minecraft:use_remainder"] = {"id": "minecraft:bowl", "count": 1}
        c["minecraft:max_stack_size"] = 16
    if food["stack"]:
        c["minecraft:max_stack_size"] = food["stack"]
    return c


def result(food, count=1):
    return {"id": BASE, "count": count, "components": components(food)}


def recipe(food):
    r = food["recipe"]
    if r[0] == SL:
        return {"type": "minecraft:crafting_shapeless", "category": "misc", "group": "gcb_food",
                "ingredients": [mc(i) for i in r[1]], "result": result(food, r[2])}
    return {"type": "minecraft:crafting_shaped", "category": "misc", "group": "gcb_food",
            "pattern": r[1], "key": {k: mc(v) for k, v in r[2].items()}, "result": result(food, r[3])}


def loot_entry(food, weight, count):
    functions = [{"function": "minecraft:set_components", "components": components(food)}]
    if count[1] > 1:
        functions.append({"function": "minecraft:set_count",
                          "count": {"type": "minecraft:uniform", "min": count[0], "max": count[1]}})
    return {"type": "minecraft:item", "name": BASE, "weight": weight, "functions": functions}


def dump(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def main():
    by_id = {f["id"]: f for f in FOODS}
    assert len(FOODS) == 100, len(FOODS)
    assert len(by_id) == 100, "duplicate ids"
    for f in FOODS:
        assert re.fullmatch(r"[a-z0-9_]+", f["id"]), f["id"]
        for g in f["loot"]:
            assert g in CHEST_GROUPS, (f["id"], g)
    for mob, drops in MOB_DROPS.items():
        for food, _, _ in drops:
            assert food in by_id, (mob, food)
    for _, _, food, _, _ in TRADES:
        assert food in by_id, food

    # Wipe what an earlier run generated, so removed foods leave nothing behind.
    for sub in ("recipe", "loot_table"):
        d = os.path.join(RES, "data", NS, sub)
        if os.path.isdir(d):
            for dirpath, _, files in os.walk(d):
                for name in files:
                    os.remove(os.path.join(dirpath, name))

    for f in FOODS:
        dump(os.path.join(RES, "data", NS, "recipe", f["id"] + ".json"), recipe(f))

    injections = {}
    for group, spec in CHEST_GROUPS.items():
        entries = []
        for f in FOODS:
            w = f["loot"].get(group)
            if w:
                count = (1, 1) if f["rarity"] in ("rare", "epic") or f["kind"] not in ("food", "candy") else (1, 2)
                entries.append(loot_entry(f, w, count))
        if not entries:
            continue
        table = {"type": "minecraft:" + spec.get("type", "chest"), "pools": [{
            "rolls": {"type": "minecraft:uniform", "min": spec["rolls"][0], "max": spec["rolls"][1]},
            "conditions": [{"condition": "minecraft:random_chance", "chance": spec["chance"]}],
            "entries": entries}]}
        ours = f"{NS}:{spec.get('type', 'chests')}/{group}" if spec.get("type") else f"{NS}:chests/{group}"
        dump(os.path.join(RES, "data", NS, "loot_table", ours.split(":", 1)[1] + ".json"), table)
        for t in spec["tables"]:
            injections.setdefault("minecraft:" + t, []).append(ours)

    for mob, drops in MOB_DROPS.items():
        pools = []
        for food, chance, count in drops:
            pools.append({"rolls": 1, "conditions": [
                {"condition": "minecraft:killed_by_player"},
                {"condition": "minecraft:random_chance", "chance": chance}],
                "entries": [loot_entry(by_id[food], 1, (count, count) if count == 1 else (1, count))]})
        ours = f"{NS}:entities/{mob}"
        dump(os.path.join(RES, "data", NS, "loot_table", "entities", mob + ".json"),
             {"type": "minecraft:entity", "pools": pools})
        injections.setdefault("minecraft:entities/" + mob, []).append(ours)

    dump(os.path.join(RES, "foods.json"), {
        "foods": [{"id": f["id"], "name": f["name"], "stack": result(f)} for f in FOODS],
        "loot_injections": injections,
        "trades": [{"profession": p, "level": lvl, "food": food, "count": n, "emeralds": e}
                   for p, lvl, food, n, e in TRADES],
    })

    # Human table
    found_in = {}
    for f in FOODS:
        found_in[f["id"]] = sorted(f["loot"])
    for mob, drops in MOB_DROPS.items():
        for food, chance, _ in drops:
            found_in[food].append(f"{mob} {int(chance * 100)}%")
    for p, lvl, food, n, e in TRADES:
        found_in[food].append(f"{p} trade")
    lines = ["# The 100 foods", "",
             "Generated by `foods.py`. Effects are applied when the food is finished.", "",
             "| Food | Hunger | Sat. | Effects | Recipe | Found in |", "| --- | --- | --- | --- | --- | --- |"]
    for f in FOODS:
        eff = ", ".join(f"{e.replace('_', ' ').title()} {'I' * lvl if lvl < 4 else lvl} {s}s" for e, s, lvl in f["effects"])
        eff = ", ".join(x for x in [eff] + [{"teleport": "random teleport", "clear": "clears effects",
                                              "always": "edible when full"}[x] for x in f["extra"]] if x)
        r = f["recipe"]
        if r[0] == SL:
            rec = " + ".join(r[1]) + (f" x{r[2]}" if r[2] > 1 else "")
        else:
            rec = " / ".join(r[1]) + " with " + ", ".join(f"{k}={v}" for k, v in r[2].items())
        lines.append(f"| {f['name']} | {f['nutrition']} | {f['saturation']} | {eff or '-'} | {rec} | {', '.join(found_in[f['id']])} |")
    with open(os.path.join(ROOT, "FOODS.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"{len(FOODS)} foods, {len(injections)} loot tables injected, {len(TRADES)} trades")


if __name__ == "__main__":
    main()
