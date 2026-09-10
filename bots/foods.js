'use strict';

// Live test for the 100 custom foods against the local 1.21.11 server.
//
//   ./run.sh start && node bots/foods.js
//
// Needs "debug": true in run/config/goldencarrotbuff.json, so the "<bot> ate <food>"
// line shows up in the console for every food the bot finishes.

const mineflayer = require('mineflayer');
const fs = require('fs');
const path = require('path');

const HOST = process.env.GCB_HOST || '127.0.0.1';
const PORT = parseInt(process.env.GCB_PORT || '25613', 10);
const VERSION = process.env.GCB_VERSION || '1.21.11';
const ROOT = path.resolve(__dirname, '..');
const RUN = process.env.GCB_RUN || path.join(ROOT, 'run');
const CONSOLE = RUN + '/console.in';
const LOG = RUN + '/server.log';
const BOT = 'FoodBot';

const foodsJson = JSON.parse(fs.readFileSync(path.join(ROOT, 'src/main/resources/foods.json')));
const FOODS = foodsJson.foods;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [];

function check(name, ok, detail) {
  results.push({ name, ok: !!ok, detail: detail || '' });
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  (' + detail + ')' : ''}`);
}

function say(cmd) {
  fs.appendFileSync(CONSOLE, cmd + '\n');
}

const logSize = () => fs.statSync(LOG).size;
const logSince = (offset) => fs.readFileSync(LOG).slice(offset).toString();

/** Run a console command and return the line the server printed for it. */
async function ask(cmd, needle) {
  const offset = logSize();
  say(cmd);
  for (let i = 0; i < 50; i++) {
    await sleep(100);
    const lines = logSince(offset).split('\n').filter((l) => l.includes('[Server thread/INFO]'));
    const hit = lines.find((l) => l.includes(needle));
    if (hit) return hit.replace(/^.*\[Server thread\/INFO\]: /, '');
  }
  return '';
}

const num = (s) => parseFloat((s.match(/data:\s*([-\d.]+)/) || [])[1] || 'NaN');
const food = async () => num(await ask(`data get entity ${BOT} foodLevel`, `${BOT} has the following`));
const effects = async () => await ask(`data get entity ${BOT} active_effects`, BOT);
const inventory = async () => await ask(`data get entity ${BOT} Inventory`, `${BOT} has the following`);

function spawnBot(username) {
  return new Promise((resolve, reject) => {
    const bot = mineflayer.createBot({ host: HOST, port: PORT, username, version: VERSION, auth: 'offline' });
    bot.once('spawn', () => resolve(bot));
    bot.once('error', reject);
    bot.once('kicked', (r) => reject(new Error('kicked: ' + JSON.stringify(r))));
  });
}

async function holdItem(bot, name) {
  for (let i = 0; i < 30; i++) {
    const item = bot.inventory.items().find((it) => it.name === name);
    if (item) { await bot.equip(item, 'hand'); return item; }
    await sleep(100);
  }
  throw new Error('never received ' + name);
}

const count = (bot, name) => bot.inventory.items().filter((it) => it.name === name).reduce((n, it) => n + it.count, 0);

/** /clear, and wait until the bot's own inventory agrees, so the next give is not raced. */
async function clearAndWait(bot) {
  say(`clear ${BOT}`);
  for (let i = 0; i < 30 && bot.inventory.items().length > 0; i++) await sleep(100);
}

/** Give one custom food and right-click it once; returns whether the server logged the eat. */
async function giveAndEat(bot, id) {
  await clearAndWait(bot);
  say(`gcbfood give ${BOT} ${id}`);
  const offset = logSize();
  await holdItem(bot, 'bread');
  bot.activateItem();
  for (let i = 0; i < 30; i++) {
    await sleep(100);
    if (logSince(offset).includes(`${BOT} ate ${id}`)) return true;
  }
  return false;
}

async function main() {
  const bot = await spawnBot(BOT);
  console.log('bot spawned');
  await sleep(1500);
  // The test world is a slime chunk and it gets dark: no monsters, and daylight,
  // or the bot is slain halfway through and every later check fails.
  say('gamerule minecraft:spawn_monsters false');
  say('gamerule spawn_monsters false');
  say('time set day');
  say('kill @e[type=!minecraft:player]');
  say(`gamemode creative ${BOT}`);
  say(`effect clear ${BOT}`);
  say(`clear ${BOT}`);
  await sleep(800);

  // --- 1. every food can be eaten ------------------------------------------------
  // Creative players may always eat, so nothing needs to drain hunger between foods.
  const eaten = [];
  const missed = [];
  for (const f of FOODS) {
    let ok = false;
    try {
      ok = await giveAndEat(bot, f.id);
    } catch (e) {
      missed.push(f.id + ' (' + (e.message || e) + ')');
      continue;
    }
    (ok ? eaten : missed).push(f.id);
  }
  check(`all ${FOODS.length} foods were eaten`, missed.length === 0, missed.length ? 'missed: ' + missed.join(', ') : `${eaten.length} eaten`);

  // --- 2. effects land ---------------------------------------------------------------
  say(`effect clear ${BOT}`);
  await giveAndEat(bot, 'coffee');
  let fx = await effects();
  check('coffee gives speed and haste', /minecraft:speed/.test(fx) && /minecraft:haste/.test(fx), fx.slice(0, 140));
  say(`effect clear ${BOT}`);
  say(`effect give ${BOT} minecraft:poison 60 0`);
  await giveAndEat(bot, 'ghast_milk');
  fx = await effects();
  check('ghast milk clears poison and regenerates', !/minecraft:poison/.test(fx) && /minecraft:regeneration/.test(fx), fx.slice(0, 140));

  // --- 3. survival: hunger is restored, the item is used up, the container comes back --
  say(`effect clear ${BOT}`);
  say(`clear ${BOT}`);
  say(`gamemode survival ${BOT}`);
  say(`effect give ${BOT} minecraft:hunger 8 255 true`);
  await sleep(8500);
  say(`effect clear ${BOT}`);
  const empty = await food();
  check('hunger drained for the survival test', empty < 10, `foodLevel=${empty}`);
  await clearAndWait(bot);
  say(`gcbfood give ${BOT} hearty_stew`);
  await holdItem(bot, 'bread');
  bot.activateItem();
  await sleep(2200);
  const after = await food();
  check('hearty stew restores 12 hunger', after === Math.min(20, empty + 12), `foodLevel ${empty} -> ${after}`);
  check('hearty stew is used up', count(bot, 'bread') === 0);
  check('bowl comes back after the stew', count(bot, 'bowl') === 1);
  await clearAndWait(bot);
  say(`gcbfood give ${BOT} apple_cider`);
  await holdItem(bot, 'bread');
  bot.activateItem();
  await sleep(2200);
  check('glass bottle comes back after the cider', count(bot, 'glass_bottle') === 1);

  // --- 4. crafting -------------------------------------------------------------------
  const id = (name) => bot.registry.itemsByName[name].id;
  const breadId = id('bread');
  say(`clear ${BOT}`);
  say(`give ${BOT} wheat 8`);
  say(`give ${BOT} sweet_berries 8`);
  say(`give ${BOT} egg 8`);
  say(`give ${BOT} sugar 8`);
  say(`give ${BOT} apple 8`);
  say(`give ${BOT} glass_bottle 8`);
  say(`give ${BOT} carrot 8`);
  say(`give ${BOT} milk_bucket 1`);
  await sleep(1000);
  const shapeless = (names, n) => ({ requiresTable: false, inShape: null, outShape: null,
    ingredients: names.map((x) => ({ id: id(x), count: 1 })), result: { id: breadId, count: n } });
  try {
    await bot.craft(shapeless(['wheat', 'sweet_berries', 'egg', 'sugar'], 2), 1, null);
    await sleep(500);
    let inv = await inventory();
    check('blueberry muffin crafts in the 2x2 grid', /gcb_food: "blueberry_muffin"/.test(inv));
  } catch (e) {
    check('blueberry muffin crafts in the 2x2 grid', false, String(e.message || e));
  }
  try {
    await bot.craft(shapeless(['apple', 'apple', 'sugar', 'glass_bottle'], 1), 1, null);
    await sleep(500);
    let inv = await inventory();
    check('apple cider crafts', /gcb_food: "apple_cider"/.test(inv));
  } catch (e) {
    check('apple cider crafts', false, String(e.message || e));
  }
  // Shaped 3x3 needs a table.
  const p = bot.entity.position.floored();
  say(`setblock ${p.x + 1} ${p.y} ${p.z} minecraft:crafting_table`);
  await sleep(800);
  const table = bot.blockAt(p.offset(1, 0, 0));
  const shapedRow = (names) => names.map((x) => (x ? { id: id(x), count: 1 } : { id: -1 }));
  const carrotCake = { requiresTable: true, outShape: null, ingredients: null, result: { id: breadId, count: 1 },
    inShape: [shapedRow(['carrot', 'milk_bucket', 'carrot']), shapedRow(['sugar', 'egg', 'sugar']), shapedRow(['wheat', 'wheat', 'wheat'])] };
  try {
    await bot.craft(carrotCake, 1, table);
    await sleep(500);
    let inv = await inventory();
    check('carrot cake crafts on a table', /gcb_food: "carrot_cake"/.test(inv));
  } catch (e) {
    check('carrot cake crafts on a table', false, String(e.message || e));
  }
  say(`setblock ${p.x + 1} ${p.y} ${p.z} minecraft:air`);

  // --- 5. loot ---------------------------------------------------------------------------
  // Vanilla loot alone can fill the inventory, so roll a few chests at a time and
  // count the custom stacks before clearing for the next batch.
  const found = async (cmd, times, batch = 3) => {
    let total = 0;
    for (let done = 0; done < times; done += batch) {
      await clearAndWait(bot);
      for (let i = 0; i < batch && done + i < times; i++) say(cmd);
      await sleep(800);
      const inv = await inventory();
      total += (inv.match(/gcb_food: "/g) || []).length;
    }
    return total;
  };
  let n = await found(`loot give ${BOT} loot minecraft:chests/village/village_plains_house`, 15);
  check('village house chests carry custom foods', n > 0, `${n} stacks in 15 chests`);
  n = await found(`loot give ${BOT} loot minecraft:chests/simple_dungeon`, 15);
  check('dungeon chests carry custom foods', n > 0, `${n} stacks in 15 chests`);
  n = await found(`loot give ${BOT} loot minecraft:chests/end_city_treasure`, 15);
  check('end city chests carry custom foods', n > 0, `${n} stacks in 15 chests`);
  n = await found(`loot give ${BOT} loot minecraft:gameplay/fishing`, 120, 20);
  check('fishing can pull up a custom food', n > 0, `${n} in 120 catches`);
  say(`summon minecraft:bee ~ ~ ~ {NoAI:1b}`);
  await sleep(500);
  n = await found(`execute as ${BOT} at ${BOT} run loot give ${BOT} kill @e[type=minecraft:bee,limit=1,sort=nearest]`, 30, 30);
  check('bees drop honey drops or honeycomb', n > 0, `${n} drops in 30 kills`);
  say(`kill @e[type=minecraft:bee]`);
  say(`clear ${BOT}`);

  // --- 6. villager trades -------------------------------------------------------------
  say(`gamemode creative ${BOT}`);
  say(`kill @e[type=minecraft:villager]`);
  await sleep(300);
  // The bee above shoved the bot around, so place the villagers next to wherever it is now.
  for (let i = 0; i < 6; i++) {
    say(`execute at ${BOT} run summon minecraft:villager ~${1 + (i % 3)} ~ ~${Math.floor(i / 3)} {NoAI:1b,VillagerData:{profession:"minecraft:farmer",level:2,type:"minecraft:plains"}}`);
  }
  await sleep(2500);
  let custom = 0;
  let seen = 0;
  const errors = [];
  const villagers = Object.values(bot.entities).filter((e) => e.name === 'villager');
  for (const v of villagers) {
    try {
      const shop = await bot.openVillager(v);
      seen++;
      for (const t of shop.trades) {
        if (t.outputItem && t.outputItem.name === 'bread') custom++;
      }
      bot.closeWindow(shop);
    } catch (e) {
      errors.push(String(e.message || e));
    }
    await sleep(400);
  }
  if (errors.length) console.log('  villager errors: ' + errors.join(' | '));
  // A level-2 farmer never sells vanilla bread, so any bread on offer is one of ours.
  check('farmers offer custom foods', custom > 0, `${custom} custom offers across ${seen} farmers`);
  say(`kill @e[type=minecraft:villager]`);

  bot.quit();
  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} passed`);
  process.exit(failed.length ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(2); });
