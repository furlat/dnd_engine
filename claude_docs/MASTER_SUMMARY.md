# D&D Engine - Project Summary

## Current State (January 2026)

The engine has a **complete foundation** for tactical combat with a working PvP CLI. Core systems are implemented and tested through human vs Claude gameplay.

### What's Implemented

| System | Status | Notes |
|--------|--------|-------|
| **Core Engine** | Complete | Entity/component model, ModifiableValue 6-channel system, event lifecycle |
| **Combat** | Complete | Action economy, attacks, movement, opportunity attacks, initiative |
| **Conditions** | 13/15 SRD | All except Exhaustion, Petrified |
| **Fighter Class** | Complete | All features L1-L20 including Champion archetype |
| **Spatial** | Complete | GridMap, FOV (shadowcast), pathfinding (Dijkstra) |
| **Server** | Complete | FastAPI REST API, session-based PvP authority |
| **CLI** | Complete | Human TUI + Claude agent interface |

### Fighter Features (All Complete)

| Level | Feature |
|-------|---------|
| 1 | All 6 Fighting Styles, Second Wind |
| 2 | Action Surge |
| 3 | Champion: Improved Critical (19-20) |
| 5/11/20 | Extra Attack (1/2/3 extra) |
| 9/13/17 | Indomitable (1/2/3 uses) |
| 15 | Champion: Superior Critical (18-20) |
| 18 | Champion: Survivor |

---

## Potential Next Features

| Feature | Priority | Complexity |
|---------|----------|------------|
| Scenario Testing Framework | HIGH | Medium |
| Perception/Stealth/Hidden | HIGH | Medium |
| Interactable Objects (traps, destructibles) | HIGH | Medium |
| Cover System (+2/+5 AC) | MEDIUM | Medium |
| Difficult Terrain | MEDIUM | Easy |
| Ranged Long Range Disadvantage | MEDIUM | Easy |
| Fighter Factory Function | MEDIUM | Easy |
| Spellcasting | LOW | High |

---

## Development Workflow

### PvP Testing (Primary)

```bash
# Terminal 1: Server
source .venv/bin/activate
uvicorn server.event_server:app --reload

# Terminal 2: Human player
python -m cli playpvp

# Claude agent
python -m cli.agent connect
python -m cli.agent watch
```

### Quick Local Testing

```bash
python examples/combat_basic.py
python examples/combat_conditions.py
```

### Type Checking

```bash
pyright
```

---

## Documentation

| Document | Purpose |
|----------|---------|
| `CLAUDE.md` | **Read first** - Codebase overview, rules, patterns |
| `CLI_GUIDE.md` | How to use CLI and Agent commands |
| `IMPLEMENTATION_GUIDE.md` | How to implement conditions, actions, handlers |
| `CLASS_SYSTEM.md` | Fighter implementation, feature condition patterns |
| `EXAMPLE_PATTERNS.md` | Code snippets for writing examples/tests |
| `archive/` | Completed planning docs (historical reference) |

---

## File Structure

```
dnd/
├── core/           # Base classes, events, dice, gridmap, values
├── blocks/         # Entity components (abilities, health, equipment, etc.)
├── classes/        # Character classes (fighter.py)
├── monsters/       # Creature factories (bestiary.py)
├── actions.py      # Attack, Move, Dash, Dodge, Disengage
├── conditions.py   # All D&D conditions
├── entity.py       # Main Entity class
└── encounter.py    # Turn-based combat management

server/
├── event_server.py # FastAPI endpoints
├── session.py      # Session/game management
└── api_models.py   # API response models

cli/
├── main.py         # Human CLI (play, playpvp)
├── agent.py        # Claude agent CLI
├── display.py      # Rich TUI rendering
└── api_client.py   # HTTP client

examples/           # Test scripts for features
```

---

## Key Design Decisions

1. **All state changes flow through events** - Enables handlers, logging, reactions
2. **Conditions are the extension mechanism** - Classes, features, status effects all use conditions
3. **Template-based actions** - Actions registered on entities, validated per-target
4. **6-channel modifiers** - Self/to-target × static/contextual + propagation channels
5. **Session-based authority** - PvP uses session validation for entity control
