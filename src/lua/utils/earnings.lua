---Per-game money earnings tracker.
---
---Captures every dollar earned during a run, attributed to its source
---(joker / tag / interest / hands / discards / blind / playing-card).
---Stored on G.GAME.jackpotts_earnings for the gamestate serializer to expose.
---
---Hooks three sites:
---  1. add_round_eval_row — round-end income (jokers via calc_dollar_bonus,
---     tags, interest, hand/discard money, blind reward).
---     Skips name=='bottom' which is the Balatro round-summary total
---     (would double-count every other row).
---  2. Card:get_p_dollars — per-played-card income (Lucky, Gold seal, Gold
---     enhancement) accumulated during scoring.
---  3. Card:calculate_joker + ease_dollars — mid-round joker triggers
---     (Faceless, Rough Gem, Business, Reserved Parking, etc.). The
---     calculate_joker wrapper pushes the joker onto a stack before its
---     effect runs; the ease_dollars wrapper attributes the $ to whatever
---     joker is on top of the stack. Outside any joker scope, ease_dollars
---     is ignored (the $ is captured by another path or is non-earnings,
---     e.g. shop sells/buys, rentals).

local earnings = {}

local function ensure_store()
    if not G or not G.GAME then return nil end
    if not G.GAME.jackpotts_earnings then
        G.GAME.jackpotts_earnings = { entries = {}, next_id = 1 }
    end
    return G.GAME.jackpotts_earnings
end

local function current_round_num()
    if G and G.GAME and G.GAME.round then return G.GAME.round end
    return 0
end

local function current_ante()
    if G and G.GAME and G.GAME.round_resets and G.GAME.round_resets.ante then
        return G.GAME.round_resets.ante
    end
    return 0
end

local function record(entry)
    local store = ensure_store()
    if not store then return end
    entry.id = store.next_id
    entry.round = entry.round or current_round_num()
    entry.ante = entry.ante or current_ante()
    store.next_id = store.next_id + 1
    table.insert(store.entries, entry)
end

local function joker_key(card)
    if card and card.config and card.config.center and card.config.center.key then
        return card.config.center.key
    end
    return nil
end

local function tag_key(tag)
    if tag and tag.key then return tag.key end
    return nil
end

---Map add_round_eval_row's `name` field to a stable source category.
---Names like "joker1", "joker2", "tag1", "tag2" become "joker"/"tag";
---"hands"/"discards"/"interest"/"blind1" pass through trimmed.
local function classify_eval_row(name)
    if not name then return "unknown" end
    if name:match("^joker%d*$") then return "joker" end
    if name:match("^tag%d*$") then return "tag" end
    if name == "interest" then return "interest" end
    if name == "hands" then return "hands" end
    if name == "discards" then return "discards" end
    if name:match("^blind") then return "blind" end
    return name
end

function earnings.install()
    if earnings._installed then return end

    -- 1. add_round_eval_row — round-end income
    -- Skip name=='bottom' (the round-summary total row that sums all the
    -- joker/blind/interest/hands rows above it — recording it would
    -- double-count every other source).
    if type(add_round_eval_row) == "function" then
        local _orig = add_round_eval_row
        add_round_eval_row = function(args) ---@diagnostic disable-line: duplicate-set-field
            args = args or {}
            local dollars = args.dollars or 0
            if dollars ~= 0 and not args.saved and args.name ~= "bottom" then
                record({
                    source = classify_eval_row(args.name),
                    raw_name = args.name,
                    dollars = dollars,
                    joker_key = joker_key(args.card),
                    tag_key = tag_key(args.tag),
                    phase = "round_eval",
                })
            end
            return _orig(args)
        end
    end

    -- 2. Card:get_p_dollars — per-card scoring income (Lucky, Gold seal,
    --    Gold enhancement). Hook returns the dollar amount.
    if Card and Card.get_p_dollars then
        local _orig = Card.get_p_dollars
        Card.get_p_dollars = function(self) ---@diagnostic disable-line: duplicate-set-field
            local ret = _orig(self)
            if ret and ret ~= 0 then
                local enh = self.config and self.config.center and self.config.center.key
                local seal = self.seal
                local source = "card"
                if self.lucky_trigger then
                    source = "lucky"
                elseif seal == "Gold" then
                    source = "gold_seal"
                elseif enh == "m_gold" then
                    source = "gold_enhancement"
                end
                record({
                    source = source,
                    dollars = ret,
                    enhancement = enh,
                    seal = seal,
                    rank = self.base and self.base.value,
                    suit = self.base and self.base.suit,
                    phase = "scoring",
                })
            end
            return ret
        end
    end

    -- 3. Card:calculate_joker + ease_dollars — mid-round joker triggers.
    --    Faceless, Rough Gem, Business, Reserved Parking, Trading Card,
    --    To the Moon-style payouts all call ease_dollars() directly inside
    --    their joker calculate function — they do NOT route through
    --    card_eval_status_text. To attribute the $ to the right joker we
    --    push self onto a stack at the start of calculate_joker and pop
    --    when it returns; ease_dollars then credits the joker on top of
    --    the stack. ease_dollars calls outside any joker scope (rentals,
    --    shop sells/buys, blind reward) are ignored — they're either
    --    captured elsewhere (round_eval path) or aren't earnings.
    earnings._joker_stack = {}
    if Card and Card.calculate_joker then
        local _orig = Card.calculate_joker
        Card.calculate_joker = function(self, context) ---@diagnostic disable-line: duplicate-set-field
            table.insert(earnings._joker_stack, self)
            local ok, a, b = pcall(_orig, self, context)
            table.remove(earnings._joker_stack)
            if not ok then error(a) end
            return a, b
        end
    end
    if type(ease_dollars) == "function" then
        local _orig = ease_dollars
        ease_dollars = function(mod, instant) ---@diagnostic disable-line: duplicate-set-field
            local stack = earnings._joker_stack
            local top = stack[#stack]
            if top and mod and mod ~= 0 then
                record({
                    source = "joker_trigger",
                    dollars = mod,
                    joker_key = joker_key(top),
                    phase = "play",
                })
            end
            return _orig(mod, instant)
        end
    end

    earnings._installed = true
end

---Reset accumulator (called at game start). Safe to call when G.GAME absent.
function earnings.reset()
    if G and G.GAME then
        G.GAME.jackpotts_earnings = { entries = {}, next_id = 1 }
    end
end

return earnings
