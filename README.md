# GoldenCarrotBuff (Fabric mod)

Golden carrots and golden apples retuned, plus **100 new foods** to find, craft
and eat, on a **Fabric 1.21.11 server**. Players install nothing.

| Golden carrot | Default |
| --- | --- |
| Edible with a full hunger bar | yes (like a golden apple) |
| Regeneration I | 10 seconds |
| Absorption | 1 heart, fades after 2 minutes |

| Golden apple | Default |
| --- | --- |
| Absorption | 4 hearts (vanilla: 2), fades after 2 minutes |
| Resistance I | 4 seconds |
| Regeneration II | vanilla, 5 seconds, unchanged |
| Cooldown after eating | 3 seconds, greyed out on the hotbar |

Nutrition and saturation stay vanilla for both.

## The 100 foods

The full list with hunger, effects, recipes and where each one turns up is in
[FOODS.md](FOODS.md). In short:

| Group | Examples |
| --- | --- |
| Bakery | blueberry muffin, carrot cake, apple pie, glow berry tart, croissant |
| Meals | wagyu steak, fried chicken, fish and chips, salmon sushi, meat lovers pizza, hearty stew |
| Soups | tomato soup, chicken noodle soup, miso soup, spicy chili, blaze stew |
| Snacks and candy | caramel apple, gummy slime, rock candy, four lollipops, chocolate bar, jerky, popcorn |
| Fruit and foraging | jams, mushroom skewer, lotus root, glowing cave cap, warped and crimson fruit, dragon fruit |
| Seafood | grilled squid, glow squid skewer, nautilus chowder, fried pufferfish, cod cakes |
| Drinks | apple cider, hot cocoa, berry smoothie, coffee, golden milk, lava shot, ghast milk, ender tonic |
| Rare | sculk truffle, phantom pudding, dragon pepper, golden sundae, breeze meringue, celebration cake |

Every food has a crafting recipe from vanilla ingredients (it shows up in the
recipe book once you have an ingredient) and most also turn up in the world:

* **Chests**: villages, dungeons, mineshafts, strongholds, mansions, desert and
  jungle temples, shipwrecks and ocean ruins, buried treasure, nether fortresses
  and bastions, end cities, ancient cities, trial chambers, igloos.
* **Mob drops**: 35 mobs drop a themed food when a player kills them, from
  bacon off pigs and honey drops off bees to a Sculk Truffle off the Warden and
  Dragon Peppers off the Ender Dragon.
* **Fishing** can pull up sushi, cod cakes, lotus root and the like.
* **Archaeology** (brushing suspicious sand and gravel) can turn up the
  Ancient Grain Loaf and the Torchflower Omelette.
* **Villagers**: farmers, butchers, fishermen, shepherds and clerics each sell a
  few of them for emeralds.

Soups give the bowl back and drinks give the glass bottle back, like vanilla.
Drinks are bottles tinted their own colour, candy is tinted too, and everything
else borrows a vanilla item or block texture that fits.

### How a vanilla client sees a new item

There are no new item IDs, because a vanilla client cannot know any. Every food
is a vanilla **bread** carrying components the client already understands:
`item_name`, `item_model` (any vanilla texture), `lore`, `rarity`, `food`,
`consumable` with its effects, potion or firework colours, and a `custom_data`
tag naming the food. Bread is the base because nothing in vanilla crafts,
smelts or brews with bread, so a custom food can never sneak into another
recipe. The custom foods do not stack with plain bread.

Operators get `/gcbfood give <players> <food> [count]`, `/gcbfood list` and
`/gcbfood verify` (checks every food, recipe and loot table loaded).

### Editing the list

`foods.py` is the single source of truth. Edit it, run `python3 foods.py`, and
rebuild: it writes the recipe and loot JSON into the jar's datapack, the
`foods.json` the mod reads, and `FOODS.md`.

**Players install nothing.** The mod is `environment: server`; everyone joins with
a vanilla client. The client sends its right-click before it decides for itself
whether it may eat, and then follows the server's "eating" state for the
animation, so eating at full hunger looks exactly like eating hungry.

Absorption is granted through the real Absorption effect, so the player sees
the icon and timer and it survives a relog. Each level of the effect is worth
two hearts and starts you at its ceiling, so the mod picks the smallest level
that fits (I for the carrot, II for the apple) and writes the amount back down
right after. It only ever goes up: a second carrot tops you back up to one
heart but never stacks, a golden apple after a carrot gives its four hearts,
and a carrot after an apple leaves those four hearts alone. Vanilla's own
Absorption I is stripped from the apple at boot so the config owns the number.

The apple cooldown is the vanilla item cooldown, the same thing an ender pearl
uses: the server refuses the use and the client greys the apple out by itself.

Verified against a real Fabric 1.21.11 dedicated server, see [Testing](#testing).

## Install on the server

1. Stop the server
2. `mods/` → upload `release/goldencarrotbuff-1.0.0.jar`
3. Make sure **Fabric API** is in `mods/` too (`0.141.3+1.21.11` or newer)
4. Start the server

The console prints on start:

```
Golden carrot: edible at full hunger, Regeneration 1 for 10.0s, 1.0 absorption heart(s) for 120.0s
Golden apple: 4.0 absorption heart(s) for 120.0s, Resistance 1 for 4.0s, 3.0s cooldown
```

If **AdminKit** is on the same server, set its `golden_carrot_effects` to `false`:
it has an older version of the same buff and the two would both fire.

## Config

`config/goldencarrotbuff.json`, written with defaults on first start:

```json
{
  "carrot_always_edible": true,
  "carrot_regen_seconds": 10.0,
  "carrot_regen_level": 1,
  "carrot_absorption_hearts": 1.0,
  "carrot_absorption_seconds": 120.0,
  "apple_enabled": true,
  "apple_absorption_hearts": 4.0,
  "apple_absorption_seconds": 120.0,
  "apple_resistance_seconds": 4.0,
  "apple_resistance_level": 1,
  "apple_cooldown_seconds": 3.0,
  "custom_foods": true,
  "debug": false
}
```

`custom_foods: false` turns the 100 foods, their recipes, drops and trades off.

Any hearts value picks the Absorption level it needs automatically. Setting a
seconds value to 0 turns that part off; `apple_enabled: false` leaves the apple
fully vanilla. Changes need a server restart.

## Build

```
./run.sh build          # -> build/libs/goldencarrotbuff-1.0.0.jar
```

Needs the Adoptium JDK 21 Gradle already downloaded under `~/.gradle/jdks`; the
`run.sh` points at the Gradle 9.6.1 wrapper distribution there.

## Testing

`run/` is a Fabric 1.21.11 dedicated server on port 25613 (offline mode).

```
./run.sh start          # build, install the jar, boot the server
./run.sh test           # mineflayer bot: 20 checks on the carrot and the apple
node bots/foods.js      # mineflayer bot: eats all 100 foods, crafts, loots, trades (~6 min)
./run.sh stop
```

`bots/foods.js` needs `"debug": true` in `run/config/goldencarrotbuff.json`.

The bot joins with full hunger, eats carrots and golden apples, tries an apple
inside the cooldown, and reads the result back with `/data get` through the
console. mineflayer's own `consume()`
refuses to eat at full hunger, which is exactly the client-side check the mod
gets around, so the test calls `activateItem()` directly.

## How it works

* `GoldenCarrotBuff` rewrites item components at boot (Fabric's
  `DefaultItemComponentEvents.MODIFY`): the carrot's FOOD gets
  `canAlwaysEat = true`, and the apple's CONSUMABLE loses its Absorption I.
* `ConsumableMixin` hooks `Consumable.onConsume`, which every food goes through
  at the moment it is finished, and applies the effects and the cooldown.
* `CustomFoods` reads `foods.json`, builds the stacks for `/gcbfood` and the
  villager trades, and adds our loot pools to the vanilla tables with Fabric's
  `LootTableEvents.MODIFY`. The recipes and loot pools themselves are datapack
  JSON inside the jar.
