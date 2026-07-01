# Screenshot settling: delay the API response until the frame is quiescent

When screenshot logging is enabled, capturing the frame at the moment `send_response` fires yields a **mid-animation** image: card flights, score/dollar count-ups, and juice wiggles are still in progress. This is because the API response is driven by **game-state transitions** (e.g. `G.STATE == ROUND_EVAL`), which settle *logically* well before they settle *visually*.

## Why the obvious fixes do not work under rapid-fire clients

The client typically fires request N+1 immediately upon receiving N's response. The "settled result frame" for request N therefore only exists on screen during the window **[N's animations finished → N+1's action begins]**. Under rapid fire that window is empty — N+1 begins before N finishes.

This defeats both naive alternatives:

- **Deferred capture (wait after sending the response):** N's HTTP response returns → the server accepts N+1 next frame → N+1's endpoint starts mutating the screen → by the time N's deferred quiescence fires, the framebuffer is mid-N+1. You capture neither action correctly.
- **Pre-request capture:** captures the frame immediately after `send_response(N)` — which is the *start* of N's count-up animation (the very motion that caused the problem). Still wrong.

The only lever that can make N's settled frame exist is **holding N+1 back until N's screen has settled.** The only thing the client waits on is the HTTP response.

## Decision

When screenshots are enabled, **delay `send_response` until the screen is quiescent**, then capture and respond in that same settled frame. When screenshots are disabled, `send_response` is immediate — zero impact on existing API consumers.

This serializes requests by construction: the server is single-client with one connection per request (`Connection: close`, `accept()` gated on no active client — see `src/lua/core/server.lua`). Request N+1 cannot be dispatched until N's response is sent and the socket closed. Delaying N's response therefore holds N+1 at the accept gate until N's screen has settled. No race, no lost frames.

## The quiescence signal

Balatro runs two independent per-frame animation systems (`Game:update`):

1. **`G.E_MANAGER`** — the event queue. Holds `ease`/`after`/`condition` events that drive logic and value tweens (e.g. the dollar/chip count-ups are `ease` events).
2. **`G.MOVEABLES`** — the tween layer. Every card, UIBox, and `DynaText` gets `Moveable:move(dt)` each frame, easing its Visible Transform (VT) toward its target Transform (T).

A drained event queue does **not** imply a still screen, because the tween layer keeps gliding after the last event completes. The reliable per-object signal is the **Visible Transform (VT) converging to the target Transform (T)**, checked across every `m` in `G.MOVEABLES`. A moveable is settled when its position (`x`, `y`) and rotation (`r`) are at target and no `juice` (active wiggle) is running. `DynaText = Moveable:extend()`, so the floating score/dollar text is covered — its `T.w` mutates while the string counts, keeping it unsettled until the count finishes.

### Why `Moveable.STATIONARY` is not used directly

`STATIONARY` (set in `move()`) looked like the ideal flag, but it is defeated by the **hover-scale term** in `move_scale`:

```lua
local des_scale = self.T.scale + (self.zoom and (... + (self.states.hover.is and 0.05 or 0)) ...) + ...
```

Empirically, even with no mouse, Balatro keeps a default-focused UI element hovered at steady state (`states.hover.is == true`), producing a perpetual `0.05` scale delta. The easing chases this static zoom but never converges to `STATIONARY`, so every call would deadman at 15 s. (A first implementation using `STATIONARY` directly exhibited exactly this: 15 s per call, deadman on every request.) This scale offset is a *static* zoom, not animation, so the predicate tolerates it by checking position + rotation + juice only.

The capture predicate is therefore:

```lua
for each m in G.MOVEABLES: m.juice == nil and |T.x-VT.x| < 0.01 and |T.y-VT.y| < 0.01 and |T.r-VT.r| < 0.001
```

This is checked via the same `G.E_MANAGER:add_event({ trigger = "condition" })` mechanism every endpoint already uses to wait on `G.STATE`.

`Game:update` (and thus both animation systems) runs every frame in **all** render modes — ondemand only gates `love.draw` / `love.graphics.present`, not `love.update`. So the predicate progresses and settles identically in headfull and ondemand. Empirically a 9-call run settles in ~1 s/call average with zero deadman hits.

## Composition with ADR 0002

This ADR adds the *wait*; ADR 0002 still handles the ondemand *render arming*. When quiescence is reached: in ondemand, set `BB_RENDER = true` (ADR 0002's second flip) so the next `love.draw` renders the settled frame, then call `captureScreenshot`. The PNG encode/write completes asynchronously on the next present; the HTTP response can be sent immediately after `captureScreenshot` is initiated, since the capture is already bound to the quiescent frame and N+1 cannot mutate the screen until the response is on the wire.

## Why no correctness timeout is needed

Every motion source surveyed is finite and self-draining:

- `juice_up` sets `end_time = G.TIMERS.REAL + 0.4` then clears `self.juice` (`moveable.lua:254,269`). Every wiggle ends.
- `ease` events `complete` when their target value is reached and are removed from the queue.
- Position/rotation easing converges to within the predicate's thresholds (0.01 / 0.001) in finite time; the only perpetual delta is the tolerated hover-scale offset (see above).

The only perpetual motion found is a cosmetic `0.02*sin(2*REAL)` shimmer on **rotated** DynaText *letters* (`engine/text.lua:215`). It writes `letter.r` directly, bypassing the moveable's VT, so it does **not** keep `STATIONARY` false and does not hang the wait.

A long **deadman switch** (e.g. 10–15 s) is still advisable — not to "give up and capture wrong early," but to ensure a future Balatro update introducing a perpetual moveable cannot hang the API forever. It should essentially never fire.

## Consequences

- **Latency trade-off (opt-in):** with screenshots on, every successful response incurs the screen's settling time (~0.3–1.5 s per call, action-dependent). This is the *unavoidable* cost of photographing a frame that only exists once the result has finished animating. Paid only by users who opted into screenshots; the default path is unchanged.
- **Rapid-fire safe:** response-gating serializes the client, so each captured frame is the genuine settled result of its action. No id-shift tricks, no client-side delays required.
- **Failure mode:** if quiescence is somehow never reached, the deadman switch captures-and-responds to avoid a permanent hang. The log records the timeout so it is diagnosable rather than silent (contrast ADR 0002, whose failure mode *is* silent).
