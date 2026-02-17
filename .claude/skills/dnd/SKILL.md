---
name: dnd
description: Play as the agent in a PvP D&D combat session via the agent CLI
allowed-tools: Bash(source .venv/bin/activate && python -m cli.agent *)
---

# D&D Agent PvP — Play Skill

You are playing as the monster faction in a PvP D&D combat game. All commands go through the agent CLI: `source .venv/bin/activate && python -m cli.agent <command>`.

## Command Reference

| Command | Purpose |
|---------|---------|
| `connect` | Connect to game, create session |
| `watch` | Wait for your turn (blocks until it's your turn, shows state + actions) |
| `state` | Show map, entities, HP, conditions |
| `actions` | Show all available actions with full target lists |
| `move X Y` | Move to position (X, Y) — pick from listed targets |
| `jump X Y` | Jump to position (X, Y) |
| `attack N` | Attack entity target by index |
| `cast <spell> [N\|X Y]` | Cast spell at target index or position |
| `self <name>` | Execute self-action (Dash, Dodge, Disengage, Hide) |
| `dash` / `dodge` / `disengage` | Shortcuts for common self-actions |
| `use <name\|N>` | Use object/item action (Open Door, Pull Lever, etc.) |
| `inspect X Y` | Inspect tile at position — check what objects/symbols are |
| `end` | End your turn |

## Turn Flow

```
connect → watch → [play turn] → end → watch → repeat
```

After `end`, you MUST `watch` again to wait for your next turn.

## Critical Rules

1. **Always pick positions from the listed targets.** Never guess positions. Run `actions` to see valid targets before moving.
2. **After dashing, run `actions` again** to see the updated (larger) target list.
3. **Inspect unknown map symbols** with `inspect X Y` before rushing past them. They could be levers, traps, or interactive objects.
4. **Use environment objects.** Levers, doors, and other objects can change the battlefield. Check `use` actions after moving near objects.
5. **Read the combat log** after each action — it tells you what happened (damage, saves, conditions).
6. **Dead units don't block movement.** You can walk over dead entities.
7. **Allies don't trigger opportunity attacks** against each other.

## Tactical Priorities

1. **Scout first**: Use `inspect` on unknown symbols, check the map layout
2. **Control the environment**: Open/close doors, pull levers, deactivate traps
3. **Focus fire**: Concentrate attacks on one target
4. **Avoid traps**: If an ally dies on a path, don't send the next one the same way
5. **Use dash wisely**: Dash to close distance, but remember you lose your action

## Map Symbols

| Symbol | Meaning |
|--------|---------|
| `@` | Your active entity |
| `S` | Your other entities (same faction) |
| `H` | Enemy entity |
| `#` | Wall |
| `.` | Floor |
| `~` | Water |
| `π` | Door (interactable) |
| `θ`, `λ`, `♦` | Objects — use `inspect X Y` to identify |
