# Settings via balatrosettings profiles instead of individual CLI flags

BalatroBot v2 replaces 12+ individual CLI flags/env vars for game settings (`--fast`, `--gamespeed`, `--fps-cap`, `--animation-fps`, `--audio`, `--no-reduced-motion`, `--pixel-art-smoothing`, etc.) with a single `--settings` flag that points to a balatrosettings profile directory. The mod is gated on the in-game profile being named exactly "BalatroBot" — if no such profile exists, the HTTP server does not start and no overrides are applied. Render modes are consolidated into a single `--render [headfull|headless|ondemand]` enum. Only two hardcoded overrides remain: `G.F_SKIP_TUTORIAL = true` and `all_unlocked = true`, applied only when the "BalatroBot" profile is detected.

**Considered Options:**

- **Individual flags** (v1 approach): flexible and composable, but the surface grew to 19 flags. Most were thin wrappers around `G.SETTINGS` fields that Balatro already has a mechanism for. Maintenance burden grew with every new setting.
- **balatrosettings profile** (chosen): reuses the existing balatrosettings format (plain `return {...}` Lua files). A profile is a directory with `settings.lua` and `1/profile.lua`, deep-merged into `G.SETTINGS` and `G.PROFILES`. Simpler CLI surface (one flag), and profiles are shareable across users.
- **Sidecar Lua file in profile dir**: a `balatrobot.lua` alongside `settings.lua` that could patch `G` globals directly. Rejected — arbitrary Lua execution defeats the simplicity goal and is hard to validate.

**Why the "BalatroBot" profile gate:** BalatroBot needs `all_unlocked = true` and tutorial skipped to function as a bot platform. These can't be profile settings because they affect meta state that's consumed before SMODS loads (see boot sequence: `init_item_prototypes` runs at step 7, SMODS at step 8). Rather than hooking earlier via Lovely patches, we gate on the in-game profile name — the user creates a dedicated "BalatroBot" profile, and the mod only activates when that profile is selected. This protects the user's real save data (no accidental overwrites) and makes the activation condition visible in the game's own UI.
