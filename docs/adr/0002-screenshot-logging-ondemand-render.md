# Screenshot logging: two `BB_RENDER` flips per request in ondemand mode

When screenshot logging is enabled, a successful API response triggers a screenshot of the post-action game state. In `ondemand` render mode, rendering only happens when `BB_RENDER` is set to `true`. This requires **two** separate `BB_RENDER = true` assignments within a single request lifecycle, and both are load-bearing.

**Why two flips:**

1. **Dispatch-start flip** (`src/lua/core/dispatcher.lua`, top of `dispatch()`): set before `execute` runs. This renders the frame that draws *during* request handling, and is the trigger the standalone `screenshot` endpoint relies on — `love.graphics.captureScreenshot`'s callback only fires after a present, and present only runs when `did_render` is true. **Without this flip, the standalone `screenshot` endpoint hangs forever in ondemand** (callback never fires).

2. **`send_response` flip** (`src/lua/utils/screenshot.lua`, inside the capture path): set when a successful response is ready, so the next `love.draw` renders the *settled* post-action state. By the time `send_response` fires (typically deferred via `G.E_MANAGER:add_event`, not synchronously in `execute`), the dispatch-start flip has already been consumed and reset to `false`. Without this second flip, the logged screenshot would capture a stale pre-action frame.

**Do not deduplicate.** These look redundant but are not: the first exists for the standalone endpoint and the pre-action framebuffer; the second re-arms the trigger so the post-action screenshot is correct. Removing either breaks a different thing silently.

**Considered Options:**

- **Two flips (chosen):** correct in all three render modes. `headfull` ignores `BB_RENDER` entirely (continuous rendering); `ondemand` uses both flips for their respective purposes.
- **Accept stale frame:** re-use the dispatch-start framebuffer for the after-shot. Rejected — defeats the purpose of logging the action's *result*.
- **`headfull`-only feature:** drop `ondemand` support. Rejected — contradicts the feature's goal of working wherever rendering is possible.

**Consequences:**

- Any refactor that consolidates or removes a `BB_RENDER` assignment must be reviewed against both code paths. The failure mode (standalone `screenshot` endpoint hanging) is silent — no error, no log, just a request that never returns.
- `headless` mode is unaffected: the feature is warn-and-disabled there (see `src/lua/settings.lua` `setup()`), so neither flip is ever reached.
