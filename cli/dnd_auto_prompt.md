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
The turn prompt includes initial state. After each action, the output shows updated available actions — check for new options like Extra Attack.

## Commands

| Command | Purpose |
|---------|---------|
| `move X Y` | Move to position — pick from listed targets |
| `jump X Y` | Jump to position |
| `attack N [T]` | Attack: N=action index, T=target index (default 0) |
| `cast <spell> [N\|X Y]` | Cast spell at target index or position |
| `self <name>` | Self-action (Dash, Dodge, Disengage, Hide) |
| `dash` / `dodge` / `disengage` | Shortcuts |
| `use <name\|N>` | Use object/item (Open Door, Pull Lever, etc.) |
| `inspect X Y` | Inspect unknown tile/symbol |
| `state` | Refresh full state (only if needed) |
| `actions` | Refresh full action list (after Dash, or for all AoE positions) |
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
3. **After Dash, run `actions`** — movement targets expand.
4. **Inspect unknown symbols** (`inspect X Y`) before moving near them.
5. **Update your notebook** before ending — write strategy and observations.
6. **If a command fails**, try a different action. Do NOT retry the same command.

## Notebook

Your notebook file is: `{NOTEBOOK_PATH}`

Use the **Write** tool to save observations before running `end`. Example:
```
Write to {NOTEBOOK_PATH}:
# Turn N Notes
- Enemy used Fireball, dealt 28 damage
- Door at (8,7) is open
- Strategy: spread out to avoid AoE
```

Your notebook persists between turns. Write observations about:
- Enemy abilities/spells/patterns observed
- Hazards and terrain discovered
- Strategy for next turns
- Faction status (alive, HP, conditions)

## Reading the Display

- **Actions show cost** in parentheses: `(action)`, `(bonus)`, `(FREE)`. `FREE` = no action economy cost.
- **Spell slots** shown in RESOURCES line for spellcasters: `Slots: L1:3/4 L2:2/2`
- **Conditions**: Internal engine markers are hidden. Status effects like Dashing shown in parentheses.

## Tactical Priorities

1. Scout: `inspect` unknowns, check map layout
2. Environment: doors, levers, deactivate traps
3. Focus fire: concentrate attacks on one target
4. Avoid hazards: don't repeat a path that killed an ally
5. Dash wisely: extra movement but costs your action

## Map Format

The map has two sections: **structured data** (exact coordinates) and **ASCII grid** (spatial layout).

### Structured Data (use for targeting)
- `MAP: (min_x,min_y)-(max_x,max_y)` — grid bounds
- `ENTITIES: (x,y):Name(tag)` — tag is `you`, `ally`, `enemy`, or `dead`
- `WALLS: (x,y) ...` — blocks movement and vision
- `WATER: (x,y) ...` — blocks movement, allows vision
- `HAZARDS: (x,y) ...` — deals damage (spikes, fire)
- `DIFFICULT: (x,y) ...` — costs 2x movement
- `OBJECTS: (x,y):Name` — floor items — `inspect X Y` to interact
- `DARK: (x,y) ...` — darkness tiles (can't see without darkvision)
- `DIM: (x,y) ...` — dim light tiles

Everything not listed is normal walkable floor.

### ASCII Grid (use for spatial awareness)
Below the data is an ASCII grid showing the same map visually.
- `@` = You, `%` = Dead, `#` = Wall, `~` = Water, `^` = Hazard, `,` = Slow, `.` = Floor, `φ` = Item
- Letters/numbers = entities (see LEGEND line)
- Dark tiles appear as spaces
- **Always use coordinates from the structured data for commands, not grid counting.**
