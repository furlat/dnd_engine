# D&D Engine - Project Summary

## Current State (January 2026)

The engine has a **complete foundation** for tactical combat with a working PvP CLI. Core systems are implemented and tested through human vs Claude gameplay.

### What's Implemented

| System | Status | Notes |
|--------|--------|-------|
| **Core Engine** | Complete | Entity/component model, ModifiableValue 6-channel system, event lifecycle, cross-entity conditions |
| **Combat** | Complete | Action economy, attacks, movement, opportunity attacks, initiative |
| **Special Actions** | Complete | Jump (BG3-style), Shove (BG3-style with Athletics contest) |
| **Conditions** | 13/15 SRD | All except Exhaustion, Petrified |
| **Fighter Class** | Complete | All features L1-L18 including Champion archetype |
| **Barbarian Class** | Complete | All features L1-L20 + Berserker path (BG3-style) |
| **Spell System** | Foundation | Attack/save/buff spells, slots, upcasting, concentration |
| **Spatial** | Complete | GridMap, FOV (shadowcast), pathfinding (Dijkstra) |
| **Server** | Complete | FastAPI REST API, session-based PvP authority |
| **CLI** | Complete | Human TUI + Claude agent interface |
| **Combat Log** | Complete | Auto-generated from events, 3 verbosity levels, markdown formatting |
| **Faction System** | Complete | Multi-entity combat with ally/enemy detection |

### Faction System

- `Entity.faction` field for ally/enemy detection
- `is_ally()`, `is_enemy()` instance methods
- `get_visible_enemies()`, `get_visible_allies()` with `include_dead` parameter
- `Entity.get_entities_by_faction()`, `Entity.get_alive_by_faction()` class methods
- `get_available_actions(target_filter="enemies"|"allies"|"all")` for faction-based targeting
- Encounter ends when only one faction has survivors
- Backward compatible: `faction=None` means "enemy to everyone"

### Special Actions (BG3-Style)

**Jump Action**
- Cost: Bonus Action + Movement (distance jumped)
- Range: 15ft base + 5ft per 2 STR above 10 (max based on STR)
- Requirements: Target must be visible + walkable + unoccupied
- Does NOT require path (can jump over gaps/enemies)

**Shove Action**
- Cost: Bonus Action
- Range: 5ft (adjacent only)
- Contest: Shover's Athletics CHECK vs target's passive skill DC
- Target DC: `10 + max(Athletics, Acrobatics) + advantage modifier`
- Weight limit: Can't shove targets heavier than `STR × 12` lbs
- Push distance: `5ft base + 5ft per positive STR modifier` (max 20ft)
- Allies auto-succeed (no check required)
- Option to knock prone instead of push (`knock_prone=True`)
- Forced movement does NOT trigger opportunity attacks (uses `ForcedMovementEvent`)

### Test Utilities (`dnd/utils/test_utils.py`)

Reusable helpers for testing and debugging:
- `reset_combat_state()` - Clear all registries for fresh test
- `setup_combat_arena(attacker, target)` - Create encounter with two entities
- `force_attack_hit/miss/crit(entity)` - Force deterministic attack outcomes
- `get_hp()`, `set_hp()`, `deal_damage_to()` - HP manipulation
- `has_condition()`, `count_conditions()` - Condition checks
- `print_combat_state()` - Debug output

### Combat Log System (`dnd/core/combat_log.py`)

Events auto-generate structured combat log entries at COMPLETION phase:

- **CombatLogEntry**: Three verbosity levels (compact, verbose, detailed) with markdown formatting
- **Structured data models**: `AttackLogData`, `MovementLogData`, `SavingThrowLogData`, `SkillCheckLogData`, etc.
- **Dice display**: `DiceRollDisplay`, `DamageRollDisplay` with advantage/disadvantage handling
- **Markdown helpers**: `md_color()`, `md_d20_roll()`, `md_breakdown()` for Rich rendering
- **Auto-capture**: `Encounter.add_event_to_combat_log(event)` pulls from `event.combat_log`

Events that generate combat logs:
- `AttackEvent`, `MovementEvent`, `JumpEvent`, `ShoveEvent`
- `SavingThrowEvent`, `SkillCheckEvent`
- `TurnStartEvent`, `TurnEndEvent`, `DeathEvent`
- `ForcedMovementEvent` (for shove/push effects)

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

### Barbarian Features (All Complete)

| Level | Feature |
|-------|---------|
| 1 | Rage, Unarmored Defense |
| 2 | Reckless Attack, Danger Sense |
| 3 | Berserker: Frenzy (BG3-style, no exhaustion) |
| 5 | Extra Attack (reuses Fighter's), Fast Movement |
| 6 | Berserker: Mindless Rage |
| 7 | Feral Instinct |
| 9/13/17 | Brutal Critical (+1/+2/+3 dice) |
| 10 | Berserker: Intimidating Presence + Extend |
| 11 | Relentless Rage |
| 14 | Berserker: Retaliation |
| 15 | Persistent Rage |
| 18 | Indomitable Might |
| 20 | Primal Champion (+4 STR/CON) |

---

## Spell System

### Implemented
- `SpellAction` base class with variant generation for upcasting
- `SpellEvent` for spell-specific event data
- Spell slot consumption and long rest restoration
- Entity spell helpers: `spell_attack_bonus()`, `spell_save_dc()`, etc.
- `SpellcastingBlock` for spell-specific modifiers
- **Concentration system** - `Concentrating` condition, CON save on damage, one-spell limit, automatic cleanup via `external_conditions`
- **Spell-specific effect conditions** - Allow spell-specific immunity (e.g., immune to "Hold Person" but not paralysis)

### Implemented Spells
| Spell | Level | Type | Effect |
|-------|-------|------|--------|
| Fire Bolt | Cantrip | Attack | 1d10 fire, scales with level |
| Sacred Flame | Cantrip | DEX Save | 1d8 radiant, scales with level |
| Magic Missile | 1 | Auto-hit | 3 darts (1d4+1), +1/upcast |
| Mage Armor | 1 | Buff | AC = 13 + DEX |
| Hold Person | 2 | WIS Save + Concentration | Paralyzed on fail, repeat save each turn |
| Call Lightning | 3 | DEX Save + Concentration | 3d10 lightning, grants strike action each turn |
| Fireball | 3 | DEX Save + AoE | 8d6 fire in 20ft sphere, half on save, +1d6/upcast |

### AoE System (Complete)

The AoE (Area of Effect) system provides multi-target spell/action support:

- **AoE Shapes** (`dnd/core/aoe.py`): `Sphere`, `Cone`, `Line`, `Cube` with FOV blocking
- **Target Filtering**: `valid_target_filter` ("all", "enemies", "allies") filters who gets affected
- **Self-Inclusion**: `include_self` controls whether caster can be hit by their own AoE
- **Convolution**: Base action system calls `_apply()` once per target, aggregates results
- **Self-Targeting Saves**: Fixed - caster making saves against own spell works correctly

### Missing (Next Priority)
- Spell durations (timed, short rest, long rest expiration)
- More AoE spells to test different shapes (Cone of Cold, Lightning Bolt, etc.)
- More concentration spells (e.g., Haste, Bless)

---

## Potential Next Features

| Feature | Priority | Complexity |
|---------|----------|------------|
| **More AoE Spells** (Cone of Cold, Lightning Bolt, etc.) | HIGH | Easy |
| Scenario Testing Framework | HIGH | Medium |
| Perception/Stealth/Hidden | HIGH | Medium |
| Interactable Objects (traps, destructibles) | HIGH | Medium |
| Cover System (+2/+5 AC) | MEDIUM | Medium |
| Difficult Terrain | MEDIUM | Easy |
| Ranged Long Range Disadvantage | MEDIUM | Easy |

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
| ~~`EXAMPLE_PATTERNS.md`~~ | Merged into `IMPLEMENTATION_GUIDE.md` (Section 14) |
| `archive/` | Completed planning docs (historical reference) |

---

## File Structure

```
dnd/
├── core/           # Base classes, events, dice, gridmap, values
│   ├── combat_log.py   # CombatLogEntry, structured data models, markdown helpers
│   └── events.py       # Event types including ForcedMovementEvent
├── blocks/         # Entity components (abilities, health, equipment, spellcasting)
├── classes/        # Character classes
│   ├── fighter.py, fighter_factory.py      # Fighter + Champion archetype
│   └── barbarian.py, barbarian_factory.py  # Barbarian + Berserker path
├── items/          # Weapon/armor factories (WEAPONS, ARMORS, SHIELDS dicts)
├── spells/         # Spell implementations by school
│   ├── evocation.py    # FireBolt, SacredFlame, MagicMissile, Fireball
│   ├── abjuration.py   # MageArmor, MageArmorCondition
│   ├── enchantment.py  # HoldPerson, HoldPersonEffect
│   └── conjuration.py  # CallLightning, CallLightningStrike
├── monsters/       # Creature factories (bestiary.py)
├── actions.py      # Attack, Move, Jump, Shove, Dash, Dodge, Disengage, SpellAction
├── conditions.py   # All D&D conditions + Concentrating
├── entity.py       # Main Entity class (includes weight, passive_skill)
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
6. **Cross-entity condition cleanup** - `external_conditions` tracks causal relationships between entities (e.g., concentration → spell effect on target)
