# Settings profiles bundled in the mod tree

BalatroBot uses bundled **settings profiles** to configure Balatro's game settings (speed, graphics, audio, window, etc.). Profiles live inside the Lua mod tree at `src/lua/profiles/` and are selected by bare name via `--settings fast` or `BALATROBOT_SETTINGS=fast`. A `default` profile is always applied when no profile is specified.

**Considered Options:**

- **Individual flags** (v1 approach): flexible and composable, but the surface grew to 19 flags. Most were thin wrappers around `G.SETTINGS` fields that Balatro already has a mechanism for. Maintenance burden grew with every new setting.
- **External profile directory** (v2 initial approach): pointed `--settings` to an external `balatrosettings` repo checkout. Worked but required users to clone and maintain a separate repo, used absolute paths on the CLI, and introduced platform-specific path issues.
- **Bundled profiles with name-based resolution** (chosen): profiles are directories inside `src/lua/profiles/` with `settings.lua` (required) and `profile.lua` (optional). The CLI accepts bare names; the Lua mod resolves paths via `SMODS.current_mod.path`. Simpler UX, no external dependencies, portable across platforms.
- **Sidecar Lua file in profile dir**: a `balatrobot.lua` alongside `settings.lua` that could patch `G` globals directly. Rejected — arbitrary Lua execution defeats the simplicity goal and is hard to validate.

**Architecture: hybrid resolution**

- **Python side**: lightweight validation only. A typer callback checks that the `--settings` value matches `^[a-zA-Z0-9][a-zA-Z0-9_-]*$` (no `/`, `..`, etc.). Does NOT resolve paths or check if the profile exists.
- **Lua side**: full resolution. Discovers the mod directory via `SMODS.current_mod.path`, looks up `<moddir>/src/lua/profiles/<name>/`, loads files. If not found: sends error message listing available profiles, then aborts mod loading (HTTP server does not start).

**Profile structure:**

```
src/lua/profiles/
├── default/
│   ├── settings.lua      # required — merged into G.SETTINGS
│   └── profile.lua       # optional — merged into G.PROFILES[n]
├── fast/
│   ├── settings.lua
│   └── profile.lua
└── headless/
    ├── settings.lua
    └── profile.lua
```

- `settings.lua` — returns a Lua table deep-merged into `G.SETTINGS`. Required.
- `profile.lua` — returns a Lua table deep-merged into `G.PROFILES[n]`. Optional; if missing, the merge is skipped.

**`default` profile:** Always applied when `--settings` is omitted or `BALATROBOT_SETTINGS` is unset. The fallback to `"default"` happens in the Lua `settings.lua`, not in Python. No escape hatch (`--settings none` does not exist).

**Why the "BalatroBot" profile gate:** BalatroBot needs `all_unlocked = true` and tutorial skipped to function as a bot platform. These can't be profile settings because they affect meta state that's consumed before SMODS loads (see boot sequence: `init_item_prototypes` runs at step 7, SMODS at step 8). Rather than hooking earlier via Lovely patches, we gate on the in-game profile name — the user creates a dedicated "BalatroBot" profile, and the mod only activates when that profile is selected. This protects the user's real save data (no accidental overwrites) and makes the activation condition visible in the game's own UI.
