import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import test from "node:test";

// Use the dashboard's installed Svelte, without a second package/install in
// the game repository. Override for checkouts with a different directory name.
const frontend = process.env.MODAL_DOJO_FRONTEND || fileURLToPath(new URL("../../modal-dojo/dashboards/frontend", import.meta.url));
const require = createRequire(resolve(frontend, "package.json"));
const { compile } = require("svelte/compiler");
const { render } = await import(pathToFileURL(require.resolve("svelte/server")));
const source = readFileSync(new URL("./TrajectoryViewer.svelte", import.meta.url), "utf8");
const compiled = compile(source, { generate: "server", filename: "TrajectoryViewer.svelte" });
const code = compiled.js.code.replace(/from '(svelte[^']*)'/g, (_, id) => `from '${pathToFileURL(require.resolve(id))}'`);
const { default: Viewer } = await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);
const helpers = new Function(`${source.slice(source.indexOf("  // Sprite coordinates"), source.indexOf("  let replay ="))}; return { gameReplay, chipProgress, chips, statesFrom, actionsFrom, spriteVisual, modifierBadges, JOKER_SPRITES, CARD_ATLASES, calculateHand, calculatorJokers, calculatorCard, upstreamCalculator };`)();

test("game replay joins ordered segments and recovers boundary results from full snapshots", () => {
  const first = { metadata: { balatro: { episode_id: 42, final_ante: 5 }, segment_id: 0, segment_count: 2, segment_turn_start: 1 },
    prompt: 'Gamestate: {"ante":1,"phase":"hand","shop":["stale"],"hand":["S_A"]}',
    response: '{"method":"select","params":{}}<balatro_state>{"round":1}</balatro_state>{"method":"play","params":{"cards":[0]}}' };
  const second = { metadata: { balatro: { episode_id: 42, final_ante: 5 }, segment_id: 1, segment_count: 2, segment_turn_start: 3 },
    prompt: 'Gamestate: {"ante":5,"phase":"hand","hand":["H_K"]}',
    response: '{"method":"play","params":{"cards":[0]}}<balatro_state>{"phase":"GAME_OVER"}</balatro_state>' };
  const unrelated = { ...second, metadata: { ...second.metadata, balatro: { episode_id: 99 } } };
  const replay = helpers.gameReplay(first, [second, unrelated, first, second]);
  assert.deepEqual(replay.states.map(s => s.ante), [1, 5, 5]);
  assert.deepEqual(replay.actions.map(a => a.method), ["select", "play", "play"]);
  assert.deepEqual(replay.turns, [1, 2, 3]);
  assert.deepEqual(replay.inputs[1].hand, ["S_A"]);
  assert.deepEqual(replay.inputs[2].hand, ["H_K"]);
  assert.equal(replay.states[1].shop, undefined, "full snapshot must discard stale fields");
  assert.equal(replay.missingResults, 0);
  assert.equal(replay.segments, 2);
  const html = render(Viewer, { props: { sample: first, samples: [second, first] } }).body;
  for (const label of ["Final ante 5", "ante 5", "Last recorded frame", "3 recorded moves"]) assert.ok(html.includes(label), label);
  assert.deepEqual(helpers.gameReplay(second, [first, second]).states, replay.states);
});

test("missing segments and unsaved final results are disclosed without inventing states", () => {
  const sample = { metadata: { balatro: { episode_id: 42, final_ante: 5 }, segment_id: 0, segment_count: 3, segment_turn_start: 1 },
    prompt: 'Gamestate: {"ante":1}',
    response: '{"method":"select","params":{}}<balatro_state>{"phase":"hand"}</balatro_state>{"method":"play","params":{"cards":[0]}}' };
  const later = { ...sample, metadata: { ...sample.metadata, segment_id: 2, segment_turn_start: 10 }, prompt: 'Gamestate: {"ante":5}' };
  const replay = helpers.gameReplay(sample, [later, sample]);
  assert.deepEqual(replay.turns, [1, 10]);
  assert.equal(replay.missingResults, 2);
  const html = render(Viewer, { props: { sample, samples: [sample] } }).body;
  assert.ok(html.includes("Partial replay: 1 of 3 game segments available."));
  assert.ok(html.includes("1 move result was not saved."));
});

test("recorded ante-five game replays all 15 segments through move 136", () => {
  // Reduced state fields from independent-slab rollout 0, episode
  // 1789759001521903355. Its final action (137) has no saved result.
  const parts = JSON.parse(readFileSync(new URL("./fixtures/ante-five-segments.json", import.meta.url), "utf8"));
  const replay = helpers.gameReplay(parts[0], [...parts].reverse());
  assert.equal(replay.initial.ante, 1);
  assert.equal(replay.states.length, 136);
  assert.deepEqual(replay.turns, Array.from({ length: 136 }, (_, i) => i + 1));
  assert.equal(replay.states.at(-1).ante, 5);
  assert.deepEqual([...new Set(replay.states.map(s => s.ante))], [1, 2, 3, 4, 5]);
  assert.equal(replay.missingResults, 1);
  assert.equal(replay.segments, 15);
  for (let i = 1; i < parts.length; i++) {
    const boundary = parts[i].metadata.segment_turn_start - 2;
    const snapshot = JSON.parse(parts[i].prompt.slice('Gamestate: '.length));
    assert.deepEqual(replay.states[boundary], snapshot);
    assert.deepEqual(replay.inputs[boundary + 1], snapshot);
  }
  const html = render(Viewer, { props: { sample: parts[0], samples: parts } }).body;
  for (const ante of [1, 2, 3, 4, 5]) assert.ok(html.includes(`ante ${ante}`));
  assert.ok(html.includes("136 recorded moves"));
  assert.ok(html.includes("Final ante 5"));
  assert.ok(!html.includes("Partial replay"));
});

const blinds = {
  small: { name: "Small Blind", type: "small", status: "SELECT", score: 300, tag: "Investment Tag", tag_effect: "After defeating the Boss Blind, gain $25." },
  big: { name: "Big Blind", type: "big", status: "UPCOMING", score: 450, tag: "Coupon Tag", tag_effect: "Initial cards and booster packs in the next shop are free." },
  boss: { name: "The Hook", type: "boss", status: "UPCOMING", score: 600, effect: "Discards 2 random cards per hand played." },
};
const initial = { phase: "BLIND_SELECT", ante: 1, round: 0, blinds };
const stateMessage = (state) => ({ role: "tool", content: `<balatro_state>${JSON.stringify(state)}</balatro_state>` });
const htmlFor = (state, action = null) => render(Viewer, { props: {
  trajectory: [...(action ? [{ role: "assistant", content: JSON.stringify(action) }] : []), stateMessage(state)],
} }).body.replace(/data:image\/png;base64,[A-Za-z0-9+/=]+/g, "data:image/png;base64,[embedded]");

test("both Svelte targets compile without warnings", () => {
  assert.deepEqual(compiled.warnings, []);
  assert.deepEqual(compile(source, { generate: "client" }).warnings, []);
});

test("initial blind selection is visible before the first action", () => {
  const html = render(Viewer, { props: { trajectory: [{ role: "user", content: `Gamestate: ${JSON.stringify(initial)}` }] } }).body;
  for (const label of ["Initial state", "AVAILABLE NOW", "300 chips", "450 chips", "600 chips", "Investment Tag", "gain $25", "Coupon Tag", "Cannot skip the Boss Blind"])
    assert.ok(html.includes(label), label);
  assert.ok(!html.includes("No structured Balatro state"));
});

test("hand displays explicit scored, required and remaining chips", () => {
  const html = htmlFor({ phase: "hand", blind: { type: "big", score: [1200, 2400] } });
  for (const label of ["CHIPS SCORED", "CHIPS REQUIRED TO CLEAR", "CHIPS STILL NEEDED", "1,200", "2,400"])
    assert.ok(html.includes(label), label);
});

test("selection resets displayed score instead of inheriting the last hand", () => {
  assert.deepEqual(helpers.chipProgress({ ...initial, blind: { score: [999, 300] } }), {
    current: 0, target: 300, label: "Small Blind", pending: true,
  });
});

test("shop and pack never display stale active-blind chips", () => {
  for (const phase of ["shop", "pack"]) {
    assert.equal(helpers.chipProgress({ phase, blind: { score: [999, 300] } }), null);
    const html = htmlFor({ phase, blind: { score: [999, 300] } });
    assert.ok(html.includes("No active blind score"));
    assert.ok(!html.includes("CHIPS SCORED"));
  }
});

test("zero and missing scores stay distinct; overshoot needs zero more chips", () => {
  assert.equal(helpers.chips(0), "0");
  for (const value of [null, undefined, "", "not recorded", Infinity]) assert.equal(helpers.chips(value), "—");
  const html = htmlFor({ phase: "hand", blind: { score: [650, 600] } });
  assert.match(html, /CHIPS STILL NEEDED<\/small>\s*<strong[^>]*>0<\/strong>/);
});

test("missing tag effects are acknowledged, not invented", () => {
  const html = htmlFor({ ...initial, blinds: { small: { ...blinds.small, tag_effect: null } } });
  assert.ok(html.includes("Effect not recorded in this trajectory."));
});

test("skip outcome shows the earned tag separately from the next offer", () => {
  const html = htmlFor({ ...initial,
    blinds: { ...blinds, small: { ...blinds.small, status: "SKIPPED" }, big: { ...blinds.big, status: "SELECT" } },
    action_result: { method: "skip", skipped: { name: "Small Blind" }, tag: blinds.small.tag, tag_effect: blinds.small.tag_effect, next: blinds.big },
  }, { method: "skip", params: {} });
  for (const label of ["TAG TAKEN · IN-GAME SKIP REWARD", "Investment Tag", "gain $25", "Coupon Tag", "450 chips required"])
    assert.ok(html.includes(label), label);
});

test("a failed skip does not claim a tag was earned", () => {
  const html = htmlFor(initial, { method: "skip", params: {} });
  assert.ok(!html.includes("TAG TAKEN · IN-GAME SKIP REWARD"));
});

test("initial snapshot seeds sparse deltas without shifting actions", () => {
  const messages = [
    { role: "assistant", content: '{"method":"select","params":{}}' },
    stateMessage({ phase: "hand", blind: { type: "small", score: [0, 300] } }),
    stateMessage({ blind: null, phase: "shop" }),
  ];
  const states = helpers.statesFrom(messages, initial);
  assert.equal(states.length, 2);
  assert.equal(states[0].ante, 1);
  assert.equal(states[0].blinds.small.tag, "Investment Tag");
  assert.equal(states[1].blind, undefined);
  assert.deepEqual(helpers.actionsFrom(messages), [{ method: "select", params: {} }]);
});

test("all 52 playing cards map to the correct rank and suit cells", () => {
  for (const [y, suit] of [..."HCDS"].entries()) {
    for (const [x, rank] of ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"].entries()) {
      const visual = helpers.spriteVisual(`${suit}_${rank}`);
      assert.equal(visual.layers.length, 2);
      assert.ok(visual.layers[1].style.includes(`background-position:${x / 12 * 100}% ${y / 3 * 100}%`));
    }
  }
});

test("all 150 standard jokers have bounded coordinates and real artwork", () => {
  assert.equal(Object.keys(helpers.JOKER_SPRITES).length, 150);
  for (const [key, position] of Object.entries(helpers.JOKER_SPRITES)) {
    assert.ok(position.x >= 0 && position.x < 10 && position.y >= 0 && position.y < 16, key);
    const visual = helpers.spriteVisual({ id: key }, true);
    assert.ok(visual.layers[0].style.includes("--atlas-Jokers"), key);
    assert.ok(visual.mask.includes("mask-image"), key);
  }
  assert.deepEqual(helpers.JOKER_SPRITES.j_drivers_license, { x: 0, y: 7 });
  assert.equal(helpers.spriteVisual({ id: "j_hologram" }, true).layers[1].kind, "soul");
  assert.equal(helpers.spriteVisual({ id: "j_modded_unknown" }, true), null);
});

test("enhancements, editions and seals layer independently", () => {
  for (const enhancement of ["BONUS", "MULT", "WILD", "LUCKY", "GLASS", "STEEL", "GOLD", "STONE"]) {
    const visual = helpers.spriteVisual({ id: "S_A", mod: { enhancement, edition: "POLYCHROME", seal: "RED" } });
    assert.equal(visual.layers.some(l => l.kind === "face"), enhancement !== "STONE");
    assert.ok(visual.layers.some(l => l.kind === "edition" && l.style.includes("--atlas-Editions")));
    assert.ok(visual.layers.some(l => l.kind === "seal" && l.style.includes("--atlas-Enhancers")));
  }
});

test("editions and modifiers are visible on cards and jokers without hovering", () => {
  for (const edition of ["FOIL", "HOLO", "POLYCHROME", "NEGATIVE"]) {
    const html = htmlFor({ phase: "hand", hand: [{ id: "H_K", mod: { edition, enhancement: "STEEL", seal: "RED" } }], jokers: [{ id: "j_blueprint", effect: "Copies ability", mod: { edition, eternal: true, rental: true, perishable: 2 } }] });
    assert.ok(html.includes(`data-edition="${edition.toLowerCase()}"`));
    assert.ok(html.includes('class="sprite-art'));
    assert.ok(html.includes('data-kind="edition"'));
    for (const label of ["Steel", "Red Seal", "Eternal", "Rental", "Perishable · 2 rounds", "Blueprint"]) assert.ok(html.includes(label), label);
    assert.ok(!html.includes("Object.keys"));
  }
});

test("unknown cards keep text fallback and debuffed cards show the cross overlay", () => {
  assert.equal(helpers.spriteVisual({ id: "unknown", mod: { edition: "FOIL" } }), null);
  assert.ok(htmlFor({ phase: "hand", hand: [{ id: "unknown", mod: { edition: "FOIL" } }] }).includes("Foil"));
  const visual = helpers.spriteVisual({ id: "S_A", debuff: true });
  assert.equal(visual.layers.at(-1).kind, "debuff");
});

test("sprite sheets are embedded PNGs of the expected dimensions, within upload limit", () => {
  const dimensions = { "8BitDeck": [923, 380], Jokers: [710, 1520], Enhancers: [497, 475], Editions: [355, 94] };
  for (const [name, data] of Object.entries(helpers.CARD_ATLASES)) {
    const png = Buffer.from(data.split(",")[1], "base64");
    assert.equal(png.subarray(1, 4).toString(), "PNG");
    assert.deepEqual([png.readUInt32BE(16), png.readUInt32BE(20)], dimensions[name]);
  }
  assert.ok(Buffer.byteLength(source) < 2 * 1024 * 1024);
  assert.ok(source.includes("prefers-reduced-motion: reduce"));
});

const scoreOf = result => result.low.score[0] * 10 ** result.low.score[1];
test("embedded engine matches the pinned upstream code apart from the compiler annotation", () => {
  const engine = source.split("  function upstreamCalculator() {\n")[1].split("\n    return { Hand, handChips };")[0]
    .replace("// svelte-ignore perf_avoid_nested_class (Each calculation needs isolated mutable hand-value tables.)\n", "") + "\n";
  assert.equal(createHash("sha256").update(engine).digest("hex"), "27ada8d35202a698ebd30b803e13dd1c765222f2e36ba54e806b5d69f69302a8");
});
test("upstream calculator scores a high card, pair and foil joker", () => {
  assert.equal(scoreOf(helpers.calculateHand({ hand: ["S_A"] }, [0])), 16);
  assert.equal(scoreOf(helpers.calculateHand({ hand: ["H_K", "D_K"] }, [0, 1])), 60);
  const result = helpers.calculateHand({ hand: ["S_A"], jokers: [{ id: "j_joker", mod: { edition: "FOIL" } }] }, [0]);
  assert.equal(scoreOf(result), 330);
});

test("upstream calculator applies Shortcut and Four Fingers", () => {
  const shortcut = helpers.calculateHand({ hand: ["S_2", "H_4", "D_6", "C_8", "S_T"], jokers: [{ id: "j_shortcut" }] }, [0, 1, 2, 3, 4]);
  assert.equal(shortcut.low.hand, "Straight");
  assert.equal(scoreOf(shortcut), 240);
  const four = helpers.calculateHand({ hand: ["S_2", "H_3", "D_4", "C_5"], jokers: [{ id: "j_four_fingers" }] }, [0, 1, 2, 3]);
  assert.equal(four.low.hand, "Straight");
  assert.equal(scoreOf(four), 176);
});

test("calculator scores held Steel and exposes random outcome ranges", () => {
  assert.equal(scoreOf(helpers.calculateHand({ hand: ["S_A", { id: "H_K", mod: { enhancement: "STEEL" } }] }, [0])), 24);
  const result = helpers.calculateHand({ hand: ["S_A"], jokers: [{ id: "j_misprint" }] }, [0]);
  assert.equal(scoreOf(result), 16);
  assert.equal(result.high.score[0] * 10 ** result.high.score[1], 384);
  assert.equal(result.range, true);
});

test("calculator refuses unknown counters instead of silently assuming zero", () => {
  const state = { hand: ["S_A"], jokers: [{ id: "j_hologram", effect: "Currently X2 Mult" }] };
  assert.match(helpers.calculateHand(state, [0]).error, /Hologram.*Cards Added/);
  assert.equal(scoreOf(helpers.calculateHand(state, [0], { 0: 4 })), 32);
  assert.match(helpers.calculateHand({ hand: ["S_A"], jokers: [{ id: "j_modded_unknown" }] }, [0]).error, /unsupported joker/);
});

test("calculator auto-loads known counters and recorded hand values without mutating state", () => {
  const state = { hand: ["S_A"], money: 10, jokers: [{ id: "j_bull", sell: 3 }], hand_values: { "High Card": [2, 25, 3] } };
  const before = JSON.stringify(state);
  assert.equal(helpers.calculatorJokers(state)[0].value, 10);
  assert.equal(scoreOf(helpers.calculateHand(state, [0])), (25 + 11 + 20) * 3);
  assert.equal(JSON.stringify(state), before);
  assert.equal(scoreOf(helpers.calculateHand({ hand: ["S_A"] }, [0])), 16, "custom base values must not leak into later calculations");
});

test("calculator preserves selected play order and validates unsupported input", () => {
  const state = { hand: ["H_2", "D_K"], jokers: [{ id: "j_hanging_chad" }, { id: "j_splash" }] };
  const a = helpers.calculateHand(state, [0, 1]), b = helpers.calculateHand(state, [1, 0]);
  assert.notEqual(scoreOf(a), scoreOf(b));
  for (const cards of [[], [0, 0], [9], [0, 1, 2, 3, 4, 5]]) assert.ok(helpers.calculateHand(state, cards).error);
  assert.match(helpers.calculateHand({ hand: [{ id: "S_A", mod: { edition: "MODDED" } }] }, [0]).error, /unsupported modifier/);
});

test("joker info is an accessible hover/focus tooltip and calculation is UI-only", () => {
  const html = htmlFor({ phase: "hand", hand: ["S_A"], jokers: [{ id: "j_joker", effect: "+4 Mult", sell: 2 }] });
  for (const label of ['role="tooltip"', 'aria-describedby=', "+4 Mult", "Sell value: $2", "EFHIII scoring engine", "UI estimate, not a live-game prediction", 'aria-pressed="false"']) assert.ok(html.includes(label), label);
  assert.ok(source.includes(".joker-slot:hover .joker-tooltip, .joker-slot:focus-within .joker-tooltip"));
  assert.ok(source.includes("#3a5055"));
  assert.ok(!source.includes("--felt:"));
});

test("compact game layout keeps replay and inspectors without expanding them", () => {
  const html = htmlFor({ phase: "hand", ante: 3, round: 7, money: 29, hand: ["S_A"], blind: { score: [42, 2000], hands: 3, discards: 2 } });
  for (const label of ['aria-label="Recorded game status"', 'aria-label="Ante, round, and blind"', 'aria-label="Turns in selected blind"', 'aria-label="Previous frame"', 'aria-label="Next frame"', "Hands left", "Discards left", "$29", "Run info", "Trace &amp; rewards", "UI CALCULATOR · ESTIMATE"]) assert.ok(html.includes(label), label);
  assert.match(html, /class="inspector-panel[^\"]*" hidden/);
  assert.ok(!html.includes('type="range"'));
  assert.ok(html.indexOf('class="blind-strip') < html.indexOf('class="game-layout'));
  assert.ok(html.indexOf('class="turn-strip') < html.indexOf('class="game-layout'));
  assert.ok(html.includes("ante 3") && html.includes("round 7"));
  assert.ok(html.indexOf('class="game-hud') < html.indexOf('class="game-table'));
  assert.ok(html.indexOf('class="top-racks') < html.indexOf('class="hand-zone'));
  assert.ok(source.includes("@container (max-width: 480px)"));
});

test("shop renders prices, offers, vouchers and boosters without an active score", () => {
  const html = htmlFor({ phase: "shop", money: 15, reroll_cost: 5,
    shop: [{ id: "j_joker", effect: "+4 Mult", cost: 2, mod: { edition: "foil" } }],
    vouchers: [{ id: "v_overstock_norm", effect: "+1 card slot in shop", cost: 10 }],
    packs: [{ id: "p_arcana_normal_1", name: "Arcana Pack", effect: "Choose 1 of 3 Tarot cards", cost: 4 }],
    owned_vouchers: [{ id: "v_hone", effect: "Edition odds doubled" }], blind: { score: [999, 300] },
  });
  for (const label of ["CARDS FOR SALE", "Reroll $5", "VOUCHERS &amp; BOOSTER PACKS", "Arcana Pack", "Choose 1 of 3 Tarot cards", "$4", "$10", "Foil", "Edition odds doubled", "No active blind score"]) assert.ok(html.includes(label), label);
  assert.ok(!html.includes("CHIPS SCORED"));
});

test("booster choices retain effects and modifiers", () => {
  const html = htmlFor({ phase: "pack", pack: [{ id: "S_A", mod: { enhancement: "glass", edition: "polychrome", seal: "red" } }, { id: "c_death", effect: "Convert left card into right card" }] });
  for (const label of ["BOOSTER PACK", "2 recorded choices", "Glass", "Polychrome", "Red Seal", "Convert left card into right card"]) assert.ok(html.includes(label), label);
});

test("discards left never masquerade as discard pile size", () => {
  const state = { phase: "hand", hand: ["S_A"], blind: { score: [0, 300], hands: 4, discards: 3 }, deck_left: 49 };
  assert.ok(htmlFor(state).includes("Discard pile: —"));
  const html = htmlFor({ ...state, discard: ["H_2", "C_3"] });
  assert.match(html, /Discards left<\/small><strong[^>]*>3<\/strong>/);
  assert.ok(html.includes("Discard pile: 2"));
  assert.ok(html.includes("DECK 49"));
});

test("complete trace and inventory stay inspectable, including fields without dedicated widgets", () => {
  const html = htmlFor({ phase: "hand", hand: ["S_A"], deck: ["H_2"], custom_future_field: { unusual: "retained information" }, hand_stats: { Pair: [3, 6, 1] }, owned_vouchers: [{ id: "v_hone", effect: "Edition odds doubled" }] });
  for (const label of ["retained information", "Complete frame state", "Action &amp; input state", "Reward events · entire episode, not frame-aligned", "Deck composition · 1 recorded cards", "Poker hand levels &amp; history", "Edition odds doubled"]) assert.ok(html.includes(label), label);
});

test("empty compact inventory does not render slot metadata as a fake card", () => {
  const html = htmlFor({ phase: "hand", hand: ["S_A"], jokers: { slots: "0/5" }, consumables: { slots: "0/2" } });
  assert.ok(html.includes("No jokers in this frame."));
  assert.ok(html.includes("No consumables"));
  assert.ok(!html.includes("Info: Slots"));
  assert.ok(!html.includes("0/0/5"));
});

test("inventory sections default collapsed and render cards instead of JSON walls", () => {
  const html = htmlFor({ phase: "hand", jokers: [{ id: "j_joker", mod: { edition: "foil" } }], consumables: [{ id: "c_fool", effect: "Create last Tarot" }], deck: ["H_2"], discard: ["C_3"], hand_values: { Pair: [3, 40, 4] }, hand_stats: { Pair: [3, 6, 0], Flush: [1, 0, 0] } });
  for (const label of ["Owned vouchers · 0", "Jokers · 1", "Consumables · 1", "Deck composition · 1 recorded cards", "Discard pile · 1", "Poker hand levels &amp; history · current state"])
    assert.ok(new RegExp(`<details[^>]*><summary[^>]*>${label}</summary>`).test(html), label);
  assert.ok(!/<details[^>]*\bopen\b[^>]*><summary[^>]*>(Owned vouchers|Jokers|Consumables|Deck composition|Discard pile|Poker hand levels)/.test(html));
  for (const kind of ["joker", "consumable", "deck", "discard"]) assert.ok(html.includes(`data-kind="${kind}"`), kind);
  for (const label of ["No owned vouchers recorded.", "Create last Tarot", "2♥", "3♣", "Foil", "Played total", "This round", "Recorded data"]) assert.ok(html.includes(label), label);
  const rows = html.match(/<tbody>([\s\S]*?)<\/tbody>/)[1].replace(/<!--[\s\S]*?-->/g, "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ");
  assert.ok(rows.includes("Pair 3 40 4 6 0"), rows);
  assert.ok(rows.includes("Flush 1 — — 0 0"), rows);
});

// Exercise the same reactive replay state at a selected frame via SSR. This
// changes only initial navigation state in the test build, not viewer logic.
const replayTestComponents = new Map();
async function replayHtml(before, action, after, groupIndex = 0, frameIndex = 1) {
  const key = `${groupIndex}:${frameIndex}`;
  if (!replayTestComponents.has(key)) {
    const fixtureSource = source.replace('let activeGroupIndex = $state(0);', `let activeGroupIndex = $state(${groupIndex});`).replace('let activeFrameIndex = $state(0);', `let activeFrameIndex = $state(${frameIndex});`);
    const built = compile(fixtureSource, { generate: "server" }).js.code.replace(/from '(svelte[^']*)'/g, (_, id) => `from '${pathToFileURL(require.resolve(id))}'`);
    const { default: component } = await import(`data:text/javascript;base64,${Buffer.from(built).toString("base64")}`);
    replayTestComponents.set(key, component);
  }
  return render(replayTestComponents.get(key), { props: { trajectory: [{ role: "user", content: `Gamestate: ${JSON.stringify(before)}` }, { role: "assistant", content: JSON.stringify(action) }, stateMessage(after)] } }).body.replace(/data:image\/png;base64,[A-Za-z0-9+/=]+/g, "[embedded]");
}

test("discard replay highlights removed input cards, not their replacements", async () => {
  const html = await replayHtml({ phase: "hand", ante: 1, round: 1, blind: { type: "small", score: [0,300] }, hand: ["S_A", "H_2", "C_3"] }, { method: "discard", params: { cards: [1,2] } }, { hand: ["S_A", "D_K", "D_Q"], discard: ["H_2", "C_3"] });
  assert.equal((html.match(/class="playing-card[^\"]*recorded-discard/g) || []).length, 2);
  assert.ok(html.includes("Discarded this turn. Select 2♥"));
  assert.ok(html.includes("DISCARD INPUT"));
  assert.ok(html.includes('aria-label="Inspect discard pile"'));
  assert.ok(source.includes('open={inventoryFocus === "discard"}'));
  assert.ok(!html.includes("ACTUAL PLAY · RECORDED"));
});

test("play frames auto-calculate and show recorded score independently", async () => {
  const html = await replayHtml({ phase: "hand", ante: 1, round: 1, blind: { type: "small", score: [0,300] }, hand: ["S_A", "H_K"], jokers: { slots: "0/5" } }, { method: "play", params: { cards: [0] } }, { blind: { score: [16,300] }, hand: ["C_2", "H_K"], play_commit: { score: 16, hand: "High Card", cards: [0] } });
  for (const label of ["ACTUAL PLAY · RECORDED", "16 chips", "UI CALCULATOR · ESTIMATE", "High Card"]) assert.ok(html.includes(label), label);
  assert.match(html, /class="hud-calculation[\s\S]*?<strong[^>]*>16<\/strong>/);
  assert.ok(!html.includes("Select cards to calculate"));
});

test("winning play auto-calculates pre-shop inputs and preserves actual random outcome", async () => {
  const html = await replayHtml({ phase: "hand", ante: 1, round: 1, blind: { type: "small", score: [280,300] }, hand: ["S_A"], jokers: [{ id: "j_misprint" }] }, { method: "play", params: { cards: [0] } }, { phase: "shop", blind: null, hand: null, play_commit: { score: 128, hand: "High Card", cards: [0] } }, 1, 0);
  assert.ok(html.includes("128 chips"));
  assert.ok(html.includes("16 – 384"));
  assert.ok(html.includes("PLAY INPUT · PRE-SHOP STATE"));
  assert.ok(!html.includes("CHIPS SCORED"));
});

test("missing calculator inputs never hide the actual recorded play score", async () => {
  const html = await replayHtml({ phase: "hand", ante: 1, round: 1, blind: { type: "small", score: [0,300] }, hand: ["S_A"], jokers: [{ id: "j_hologram" }] }, { method: "play", params: { cards: [0] } }, { blind: { score: [32,300] }, play_commit: { score: 32, hand: "High Card", cards: [0] } });
  assert.ok(html.includes("32 chips"));
  assert.ok(html.includes("Estimate needs inputs"));
});

test("Idol targets auto-populate all 52 upstream Card IDs from structured snapshots", () => {
  for (const [rankIndex, rank] of ["2","3","4","5","6","7","8","9","T","J","Q","K","A"].entries()) {
    for (const [suitIndex, suit] of [..."HCDS"].entries()) {
      const joker = { id: "j_idol", scoring_state: { target: { rank, suit } } };
      assert.equal(helpers.calculatorJokers({ jokers: [joker] })[0].value, rankIndex * 4 + suitIndex);
      const plain = scoreOf(helpers.calculateHand({ hand: [suit + "_" + rank] }, [0]));
      assert.equal(scoreOf(helpers.calculateHand({ hand: [suit + "_" + rank], jokers: [joker] }, [0])), plain * 2);
    }
  }
});

test("old trace Idol descriptions supply actual round targets without guessing", () => {
  const joker = { id: "j_idol", effect: "Each played 3 of Hearts gives X2 Mult when scored Card changes every round" };
  assert.equal(helpers.calculatorJokers({ jokers: [joker] })[0].value, 4);
  assert.equal(scoreOf(helpers.calculateHand({ hand: ["H_3"], jokers: [joker] }, [0])), 16);
  assert.equal(scoreOf(helpers.calculateHand({ hand: ["C_3"], jokers: [joker] }, [0])), 8);
  const unknown = { id: "j_idol", effect: "Each played [rank] of [suit] gives X2 Mult" };
  assert.match(helpers.calculateHand({ hand: ["H_3"], jokers: [unknown] }, [0]).error, /Enter missing calculator inputs/);
});

test("structured targets override text and refresh across sparse round deltas", () => {
  const first = { jokers: { items: [{ id: "j_idol", effect: "Each played 3 of Hearts gives X2 Mult", scoring_state: { target: { rank: "K", suit: "S" } } }] } };
  const states = helpers.statesFrom([stateMessage(first), stateMessage({ jokers: { items: [{ id: "j_idol", scoring_state: { target: { rank: "2", suit: "H" } } }] } })]);
  assert.equal(helpers.calculatorJokers(states[0])[0].value, 47);
  assert.equal(helpers.calculatorJokers(states[1])[0].value, 0);
});

test("Ancient suit and Castle accumulated chips populate their calculator inputs", () => {
  const ancient = { id: "j_ancient", scoring_state: { target: { suit: "C" } } };
  assert.equal(helpers.calculatorJokers({ jokers: [ancient] })[0].value, 1);
  assert.equal(scoreOf(helpers.calculateHand({ hand: ["C_A"], jokers: [ancient] }, [0])), 24);
  const castle = { id: "j_castle", scoring_state: { target: { suit: "D" }, chips: 27, chip_gain: 3 } };
  assert.equal(scoreOf(helpers.calculateHand({ hand: ["C_A"], jokers: [castle] }, [0])), 43);
});
