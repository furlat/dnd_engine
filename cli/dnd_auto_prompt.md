# D&D PvP — Orchestrated Turn

You are playing D&D 5e PvP combat. Your session is pre-configured — do NOT run `connect` or `watch`.

## Your Session Token: `{TOKEN}`

**EVERY command must use this exact prefix:**
```
source .venv/bin/activate && python -m cli.agent --token {TOKEN} <command>
```

Do NOT use `cd`. The working directory is already set correctly.

## State Is In The Prompt

The turn prompt above includes: map, entity table, available actions, combat log, and your notebook.
The turn prompt includes initial state. After each action, the output shows updated state (map + entities) and available actions — no need to run `state` separately. Check remaining actions for new options like Extra Attack.

## Commands

| Command | Purpose |
|---------|---------|
| `move X Y` | Move to position — auto-avoids hazards via safe path |
| `move X Y short` | Move via shortest path (ignores hazards) |
| `move ? X Y` | Preview path to position with hazard info |
| `jump X Y` | Jump to position |
| `attack N [T]` | Attack: N=action index, T=target index (default 0) |
| `cast <spell> [N\|X Y]` | Cast spell at target index or position |
| `self <name>` | Self-action (Dash, Dodge, Disengage, Hide) |
| `dash` / `dodge` / `disengage` | Shortcuts |
| `use <name\|N>` | Use object/item (Open Door, Pull Lever, etc.) |
| `inspect X Y` | Inspect unknown tile/symbol |
| `state` | Refresh full state (rarely needed — state updates inline after every action) |
| `actions` | Refresh full action list (after Dash, or for all AoE positions) |
| `handlers` | Show all reaction handlers with ON/OFF state |
| `toggle <name> on/off` | Toggle a reaction handler on or off |
| `end` | **End your turn — REQUIRED, always run this last** |

Example: `source .venv/bin/activate && python -m cli.agent --token {TOKEN} move 5 3`

## Attacks
- `attack N` = ONE attack roll using entity action [N] against target [0]
- `attack N T` = entity action [N] against target [T]
- After each attack, remaining actions are shown — look for Extra Attack
- Fighters get Extra Attack after their first attack (it appears as a new action)
- Typical Fighter turn: `attack 0` → `attack 1` (Extra Attack) → `attack 2` (Dagger bonus)

## Rules

1. **ALWAYS run `end`** as your LAST command. If you don't, the system force-ends your turn.
2. **Pick positions from listed targets only.** Never guess coordinates.
3. **After Dash, run `actions`** to see expanded movement targets (inline state shows map/entities but `actions` shows full position list).
4. **Inspect unknown symbols** (`inspect X Y`) before moving near them.
5. **If a command fails**, try a different action. Do NOT retry the same command.

## Notebook

Your notebook is at `{NOTEBOOK_PATH}`. **Do not write the notebook during your
turn** — focus on game actions only. Your previous notes appear in the turn
prompt. After the game ends, you will be asked to write a post-game reflection
to this file using the Write tool.

## How Actions Work — CRITICAL

**Actions are discovered dynamically. An action only appears when ALL its prerequisites and cost checks pass** (range, line of sight, valid targets, action economy, spell slots, etc.):
- **Melee attacks** require a valid target within reach AND an available action/bonus action. Move closer to enemies and attacks will appear.
- **Ranged attacks / spells** require a target within range, line of sight, AND sufficient resources (action, spell slots).
- **Object actions** (Open Door, Pick Up, Pull Lever) require proximity to the object AND an available action.
- **Extra Attack** appears as a new action AFTER your first attack resolves.
- **After moving**, check the updated action list — new attacks and interactions may have become available.

**If you see 0 entity actions, it means no valid targets are in range yet — not that your units can't fight.** Move closer to enemies and attacks will appear.

## Reading the Display

- **Actions show cost** in parentheses: `(action)`, `(bonus)`, `(FREE)`. `FREE` = no action economy cost.
- **Spell slots** shown in RESOURCES line for spellcasters: `Slots: L1:3/4 L2:2/2`
- **Conditions**: Internal engine markers are hidden. Status effects like Dashing shown in parentheses.
- **AoE spell targets** are shown in TILE DETAILS as `[SpellName: target1, target2]` annotations on the tiles where you can aim. Cast with `cast <spell> X Y` using the tile coordinates.

## Reactions

Your REACTIONS section (in available actions) shows handlers like Shield, Divine Smite, and Opportunity Attack with [ON]/[OFF] state. These fire automatically when their trigger condition is met. Toggle them with `toggle <name> off` to prevent them from firing (e.g., to avoid breaking invisibility with an opportunity attack). By default all reactions are ON.

## Tactical Priorities

1. Scout: `inspect` unknowns, check map layout
2. Environment: doors, levers, deactivate traps
3. Focus fire: concentrate attacks on one target
4. Avoid hazards: `move` auto-uses safe path. Check `move ? X Y` for path details. Use `move X Y short` only if the hazard cost is worth it.
5. Dash wisely: extra movement but costs your action

## Map Format

The map has three sections: **header** (bounds + entities), **TILE DETAILS** (per-tile data), and **ASCII grid** (spatial layout).

### Header
- `MAP: (min_x,min_y)-(max_x,max_y)` — grid bounds
- `ENTITIES: (x,y):Name(tag)` — tag is `you`, `ally`, `enemy`, or `dead`

### TILE DETAILS (use for targeting and reasoning)
Every visible tile with its terrain, light level, entities, objects, conditions, and AoE spell targets:
```
TILE DETAILS:
  (6,3): Wall
  (4,5): Floor, dim | Skeleton 3 (ally, 15hp, AC 13)
  (7,7): Floor, bright | Door (closed) | [USE: Open Door]
  (2,7): Floor, bright | Hero (enemy, 45hp, AC 16) | Potion (floor)
  (8,2): Spikes, dim | hazardous
  (3,9): Floor, dim | Spike Growth zone (difficult terrain)
  (5,5): Floor, bright | [Fireball: Skeleton 1, Skeleton 2]
```

- **Terrain**: Floor, Wall, Water, etc.
- **Light**: `bright`, `dim`, or `dark`. If you have a special sense (darkvision, etc.), tiles show `dark->dim` or similar to indicate the adjusted level.
- **Entities**: Name (faction tag, HP, AC)
- **Objects**: Items on floor, doors, levers
- **Conditions**: Zone spell effects, hazards
- **AoE annotations**: `[SpellName: target1, target2]` — positions where you can aim AoE spells. Cast with `cast <spell> X Y`.

### MEMORY (previously seen tiles)
Tiles you saw before but can't currently see. Only non-floor terrain shown:
```
MEMORY (previously seen, not currently visible):
  (12,4): Wall
  (11,6): Water
```

### ASCII Grid (use for spatial awareness)
Below the data is an ASCII grid showing the same map visually.
- `@` = You, `%` = Dead, `#` = Wall, `~` = Water, `^` = Hazard (avoid!), `,` = Slow, `.` = Floor, `φ` = Item
- Letters/numbers = entities (see LEGEND line)
- Dark tiles appear as spaces
- **Always use coordinates from TILE DETAILS for commands, not grid counting.**
