# Interactive Ruleset Implementation Plan

This document outlines the project to create tested Python code snippets for each part of the D&D 5e SRD, validating our engine implementation against the official rules.

## Project Goals

1. **Verify Rule Coverage**: Test that our engine correctly implements D&D 5e rules
2. **Debug Existing Code**: Find and fix discrepancies between our implementation and the SRD
3. **Document Gaps**: Identify rules that are not yet implemented
4. **Create Searchable Test Suite**: Each test function contains the SRD text in its docstring for matching

## Project Structure

```
interactive_ruleset/
├── IMPLEMENTATION_PLAN.md          # This file
├── COVERAGE_REPORT.md              # Auto-generated coverage tracking
│
├── tests/                          # Python test modules (mirrors SRD structure)
│   ├── __init__.py
│   │
│   ├── gameplay/                   # Core mechanics
│   │   ├── __init__.py
│   │   ├── test_abilities.py       # Abilities.md
│   │   ├── test_adventuring.py     # Adventuring.md
│   │   └── test_combat.py          # Combat.md
│   │
│   ├── equipment/                  # Equipment rules
│   │   ├── __init__.py
│   │   ├── test_armor.py           # Armor.md
│   │   └── test_weapons.py         # Weapons.md
│   │
│   ├── gamemastering/              # GM rules (conditions, etc.)
│   │   ├── __init__.py
│   │   └── test_conditions.py      # Conditions.md
│   │
│   ├── characterizations/          # Character building
│   │   └── ...
│   │
│   ├── classes/                    # Class features
│   │   └── ...
│   │
│   ├── races/                      # Racial traits
│   │   └── ...
│   │
│   ├── monsters/                   # Monster stat blocks
│   │   └── ...
│   │
│   └── spells/                     # Spell effects
│       └── ...
│
└── [SRD markdown folders remain as-is]
    ├── Gameplay/
    ├── Equipment/
    ├── Gamemastering/
    └── ...
```

## Test Function Pattern

Each test function follows this pattern:

```python
def test_blinded_attack_disadvantage():
    """
    SRD Reference: Conditions.md > Blinded

    > A blinded creature can't see and automatically fails any ability check
    > that requires sight.
    > Attack rolls against the creature have advantage, and the creature's
    > attack rolls have disadvantage.

    Test: Verify blinded creature has disadvantage on attack rolls.
    Status: IMPLEMENTED
    """
    # Setup
    from dnd.entity import Entity, EntityConfig
    from dnd.conditions import Blinded
    from dnd.blocks.equipment import WeaponSlot

    attacker = Entity.create(...)
    target = Entity.create(...)

    # Apply condition
    blinded = Blinded(
        source_entity_uuid=target.uuid,
        target_entity_uuid=attacker.uuid
    )
    attacker.add_condition(blinded)

    # Verify
    attack_bonus = attacker.attack_bonus(WeaponSlot.MAIN_HAND, target.uuid)
    attack_bonus.set_from_target(target.ac_bonus(attacker.uuid))

    assert attack_bonus.advantage == AdvantageStatus.DISADVANTAGE, \
        "Blinded creature should have disadvantage on attacks"

    # Cleanup
    attack_bonus.reset_from_target()
```

## Docstring Structure

Each test docstring contains:

1. **SRD Reference**: File path and section name
2. **Quoted SRD Text**: The exact rule text (with `>` prefix for quoting)
3. **Test Description**: What this specific test verifies
4. **Status**: One of:
   - `IMPLEMENTED` - Rule is implemented and test passes
   - `PARTIAL` - Rule is partially implemented
   - `NOT_IMPLEMENTED` - Rule not yet in engine
   - `BLOCKED` - Depends on unimplemented feature
   - `N/A` - Rule doesn't apply to our engine scope

## Priority Order

### Phase 1: Core Mechanics (Highest Priority)

These are the foundational rules that everything else depends on:

| File | SRD Source | Priority | Notes |
|------|------------|----------|-------|
| `test_abilities.py` | `Gameplay/Abilities.md` | P0 | Ability scores, modifiers, advantage/disadvantage |
| `test_conditions.py` | `Gamemastering/Conditions.md` | P0 | All 14 conditions - we have most |
| `test_combat.py` | `Gameplay/Combat.md` | P0 | Attack rolls, damage, AC, actions |
| `test_weapons.py` | `Equipment/Weapons.md` | P0 | Weapon properties, damage types |
| `test_armor.py` | `Equipment/Armor.md` | P0 | AC calculation, armor types |

### Phase 2: Character Options (Medium Priority)

| File | SRD Source | Priority | Notes |
|------|------------|----------|-------|
| `test_races.py` | `Races/*.md` | P1 | Racial traits and abilities |
| `test_classes.py` | `Classes/*.md` | P1 | Class features |
| `test_backgrounds.py` | `Characterizations/Backgrounds.md` | P1 | Background features |

### Phase 3: Advanced Rules (Lower Priority)

| File | SRD Source | Priority | Notes |
|------|------------|----------|-------|
| `test_adventuring.py` | `Gameplay/Adventuring.md` | P2 | Movement, resting, environment |
| `test_spells.py` | `Spells/*.md` | P2 | Spell effects |
| `test_monsters.py` | `Monsters/*.md` | P2 | Monster stat blocks |
| `test_treasure.py` | `Treasure/*.md` | P3 | Magic items |

## Current Engine Capabilities

Based on our existing codebase, we already support:

### Implemented
- [x] 6 Ability Scores (STR, DEX, CON, INT, WIS, CHA)
- [x] 18 Skills with ability linkage
- [x] 6 Saving Throws
- [x] Proficiency Bonus
- [x] Advantage/Disadvantage system
- [x] Attack rolls with modifiers
- [x] AC calculation (armor + DEX + shield)
- [x] Damage types and resistance/vulnerability/immunity
- [x] 14 Conditions (Blinded, Charmed, Deafened, Frightened, Grappled, Incapacitated, Invisible, Paralyzed, Poisoned, Prone, Restrained, Stunned, Unconscious, Dodging, Dashing)
- [x] Action Economy (actions, bonus actions, reactions, movement)
- [x] Weapon properties (Finesse, Light, Heavy, Two-Handed, Versatile, Thrown, Ammunition, Reach, Loading)
- [x] Range types (Reach, Ranged)
- [x] Spatial system (movement, FOV, pathfinding)
- [x] Event-driven architecture

### Not Yet Implemented
- [ ] Exhaustion (6 levels)
- [ ] Petrified condition
- [ ] Concentration
- [ ] Spell slots and casting
- [ ] Multiattack
- [ ] Opportunity attacks
- [ ] Cover
- [ ] Difficult terrain (movement cost)
- [ ] Creature sizes affecting space
- [ ] Mounted combat
- [ ] Underwater combat

## Immediate Next Steps

1. **Create test directory structure**
2. **Start with `test_conditions.py`** - We have all conditions implemented, good starting point
3. **Create `test_abilities.py`** - Core mechanics we definitely support
4. **Create `test_combat.py`** - Attack/AC/damage flow

## Running Tests

```bash
# Run all interactive ruleset tests
pytest interactive_ruleset/tests/ -v

# Run specific category
pytest interactive_ruleset/tests/gamemastering/ -v

# Run with coverage
pytest interactive_ruleset/tests/ --cov=dnd --cov-report=html

# Generate coverage report
python interactive_ruleset/generate_coverage.py
```

## Coverage Report Generation

A script will parse all test docstrings and generate `COVERAGE_REPORT.md` showing:

- Rules tested per SRD file
- Implementation status breakdown
- Missing rule coverage
- Links between tests and SRD sections

## Contributing Guidelines

When adding new tests:

1. Find the relevant SRD markdown file
2. Copy the exact rule text into the docstring (use `>` for quoting)
3. Write a focused test for ONE specific rule interpretation
4. Use descriptive function names: `test_<topic>_<specific_rule>`
5. Mark the status appropriately
6. If a test reveals a bug, create an issue and mark status as `BUG`

## SRD File Index

Quick reference for what's in each SRD folder:

### Gameplay/ (Core Rules)
- `Abilities.md` - Ability scores, modifiers, checks, saves, skills, advantage/disadvantage
- `Adventuring.md` - Time, movement, environment, resting, between adventures
- `Combat.md` - Initiative, turns, actions, attacks, damage, death, mounted combat

### Equipment/
- `Armor.md` - Armor types, AC calculation, donning/doffing
- `Weapons.md` - Weapon categories, properties, damage
- `Gear.md` - Adventuring gear
- (others: Coinage, Expenses, Tools, etc.)

### Gamemastering/
- `Conditions.md` - All 14 conditions (Blinded through Unconscious)
- `Diseases.md` - Disease rules
- `Poisons.md` - Poison types and effects
- `Traps.md` - Trap mechanics
- (others: Objects, Planes, etc.)

### Characterizations/
- `Backgrounds.md` - Background features
- `Feats.md` - Feat rules
- `Multiclassing.md` - Multiclass rules
- (others: Alignment, Inspiration, Languages)

### Classes/
- One file per class (Barbarian.md through Wizard.md)

### Races/
- One file per race plus `# Racial Traits.md` for common rules

### Monsters/
- 319 monster stat blocks, one per file
- `# Monster Statistics.md` for stat block format

### Spells/
- 322 spells, one per file
- `# Spellcasting.md` for casting rules

### Treasure/
- 200+ magic items, one per file
- `# Magic Items.md` for item rules
