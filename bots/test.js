'use strict';

// Live test for GoldenCarrotBuff against the local 1.21.11 server.
//
//   ./run.sh start && ./run.sh test
//
// The bot joins with full hunger, which is the case a vanilla server refuses to
// eat a golden carrot in, and the buff is read back with /data get through the
// server console.

const mineflayer = require('mineflayer');
const fs = require('fs');

const HOST = process.env.GCB_HOST || '127.0.0.1';
const PORT = parseInt(process.env.GCB_PORT || '25613', 10);
const VERSION = process.env.GCB_VERSION || '1.21.11';
const RUN = process.env.GCB_RUN || '/home/tim/claude/goldencarrot/run';
const CONSOLE = RUN + '/console.in';
const LOG = RUN + '/server.log';
const BOT = 'CarrotBot';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [];

function check(name, ok, detail) {
  results.push({ name, ok: !!ok, detail: detail || '' });
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  (' + detail + ')' : ''}`);
}

function say(cmd) {
  fs.appendFileSync(CONSOLE, cmd + '\n');
}

/** Run a console command and return the line the server printed for it. */
async function ask(cmd) {
  const offset = fs.statSync(LOG).size;
  say(cmd);
  for (let i = 0; i < 40; i++) {
    await sleep(100);
    const text = fs.readFileSync(LOG).slice(offset).toString();
    const lines = text.split('\n').filter((l) => l.includes('[Server thread/INFO]'));
    const hit = lines.find((l) => l.includes(BOT + ' has the following') || l.includes('No entity was found')
      || l.includes('Found no elements') || l.includes('Unknown or incomplete'));
    if (hit) return hit.replace(/^.*\[Server thread\/INFO\]: /, '');
  }
  return '';
}

const num = (s) => parseFloat((s.match(/data:\s*([-\d.]+)/) || [])[1] || 'NaN');
const absorption = async () => num(await ask(`data get entity ${BOT} AbsorptionAmount`));
const food = async () => num(await ask(`data get entity ${BOT} foodLevel`));
const effects = async () => await ask(`data get entity ${BOT} active_effects`);

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

/** Right-click once and let the server run the 1.6s eat on its own, like a held mouse button. */
async function eat(bot, name) {
  await holdItem(bot, name);
  bot.activateItem();
  await sleep(2200);
}

async function main() {
  const bot = await spawnBot(BOT);
  console.log('bot spawned');
  await sleep(1500);
  say(`gamemode survival ${BOT}`);
  say(`effect clear ${BOT}`);
  say(`clear ${BOT}`);
  say(`give ${BOT} golden_carrot 4`);
  say(`give ${BOT} golden_apple 3`);
  await sleep(1000);

  // --- 1. eat at full hunger ------------------------------------------------
  const foodBefore = await food();
  check('bot starts with full hunger', foodBefore === 20, `foodLevel=${foodBefore}`);
  check('no absorption before eating', (await absorption()) === 0);
  const carrotsBefore = count(bot, 'golden_carrot');

  await eat(bot, 'golden_carrot');
  const carrotsAfter = count(bot, 'golden_carrot');
  check('carrot was eaten at full hunger', carrotsAfter === carrotsBefore - 1, `${carrotsBefore} -> ${carrotsAfter}`);

  let fx = await effects();
  check('regeneration I applied', /regeneration/.test(fx) && !/regeneration[^}]*amplifier: [1-9]/.test(fx), fx.slice(0, 160));
  const regenDur = parseInt((fx.match(/duration: (\d+)[^}]*id: "minecraft:regeneration"|id: "minecraft:regeneration"[^}]*duration: (\d+)/) || []).slice(1).find(Boolean) || '0', 10);
  check('regeneration lasts about 10s', regenDur > 140 && regenDur <= 200, `${regenDur} ticks left`);
  check('absorption effect applied', /minecraft:absorption/.test(fx));
  let abs = await absorption();
  check('exactly one absorption heart', abs === 2, `AbsorptionAmount=${abs}`);

  // --- 2. a second carrot does not stack ----------------------------------------
  await eat(bot, 'golden_carrot');
  abs = await absorption();
  check('second carrot does not stack past one heart', abs === 2, `AbsorptionAmount=${abs}`);
  check('second carrot was still eaten', count(bot, 'golden_carrot') === carrotsBefore - 2);

  // --- 3. golden apple: four hearts, resistance, vanilla regen kept -------------
  await eat(bot, 'golden_apple');
  abs = await absorption();
  check('golden apple gives four absorption hearts', abs === 8, `AbsorptionAmount=${abs}`);
  fx = await effects();
  check('resistance I applied by apple', /minecraft:resistance/.test(fx) && !/resistance[^}]*amplifier: [1-9]/.test(fx));
  const resDur = parseInt((fx.match(/duration: (\d+)[^}]*id: "minecraft:resistance"|id: "minecraft:resistance"[^}]*duration: (\d+)/) || []).slice(1).find(Boolean) || '0', 10);
  check('resistance lasts about 4s', resDur > 40 && resDur <= 80, `${resDur} ticks left`);
  check('vanilla regeneration II kept on apple', /amplifier: 1b[^}]*id: "minecraft:regeneration"|id: "minecraft:regeneration"[^}]*amplifier: 1b/.test(fx), fx.slice(0, 200));
  check('absorption II under the hood', /amplifier: 1b[^}]*id: "minecraft:absorption"|id: "minecraft:absorption"[^}]*amplifier: 1b/.test(fx));

  // --- 4. apple cooldown ---------------------------------------------------------
  let apples = count(bot, 'golden_apple');
  bot.activateItem();
  await sleep(2200);
  check('second apple blocked by the 3s cooldown', count(bot, 'golden_apple') === apples, `${apples} -> ${count(bot, 'golden_apple')}`);
  await sleep(1500);
  await eat(bot, 'golden_apple');
  check('apple eats again once the cooldown is over', count(bot, 'golden_apple') === apples - 1, `${apples} -> ${count(bot, 'golden_apple')}`);

  // --- 5. a carrot after the apple leaves the four hearts alone -------------------
  await eat(bot, 'golden_carrot');
  abs = await absorption();
  check('carrot after apple keeps four hearts', abs === 8, `AbsorptionAmount=${abs}`);

  // --- 6. timed effects run out ---------------------------------------------------
  await sleep(11000);
  fx = await effects();
  check('regeneration gone after ~10s', !/minecraft:regeneration/.test(fx));
  check('resistance gone after ~4s', !/minecraft:resistance/.test(fx));
  check('absorption still running', /minecraft:absorption/.test(fx));

  bot.quit();
  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} passed`);
  process.exit(failed.length ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(2); });
