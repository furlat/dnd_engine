# Plan: Unified Dice Roll Event Hierarchy

## Status: COMPLETED (Restricted Scope)

**Completed**: February 2026

This plan was implemented with a **restricted scope** focusing on the event hierarchy and Lucky feat. The preset/deterministic dice input system was **rolled back** because it was bloating the codebase with complexity that wasn't immediately needed.

---

## What Was Implemented

### 1. New EventTypes

Added to `dnd/core/events.py`:

```python
# Unified dice roll events
D20_ROLL_RESULT = "d20_roll_result"            # Base D20 type
ATTACK_D20_ROLL_RESULT = "attack_d20_roll"     # Attack rolls
SAVE_D20_ROLL_RESULT = "save_d20_roll"         # Saving throws
CHECK_D20_ROLL_RESULT = "check_d20_roll"       # Skill checks
DAMAGE_ROLL_RESULT = "damage_roll_result"      # Replaces DAMAGE_ROLLED
```

### 2. Event Class Hierarchy

```
DiceRollResultEvent (base class)
│
├── D20RollResultEvent (base for d20 rolls)
│   ├── AttackD20RollResultEvent (attack rolls)
│   ├── SavingThrowD20RollResultEvent (saving throws)
│   └── SkillCheckD20RollResultEvent (skill checks)
│
└── DamageRollResultEvent (renamed from DamageRolledEvent)
```

**Key features of D20RollResultEvent:**
- `roll` / `original_roll` / `final_roll` - Track original and modified rolls
- `replace_roll(new_roll, handler_name, reason)` - Handler helper method
- `get_effective_roll()` - Returns final or original roll
- `roll_modifications` - Audit trail of handler modifications

**Subclass-specific fields:**
- `AttackD20RollResultEvent`: `weapon_slot`
- `SavingThrowD20RollResultEvent`: `ability_name`
- `SkillCheckD20RollResultEvent`: `skill_name`

### 3. Entity.roll_d20() Wiring

Updated `dnd/entity.py` to fire appropriate D20 events:

```python
def roll_d20(
    self,
    bonus: ModifiableValue,
    roll_type: RollType = RollType.ATTACK,
    context: Optional[Dict[str, Any]] = None,
    ability_name: Optional[AbilityName] = None,
    skill_name: Optional[SkillName] = None,
    weapon_slot: Optional[WeaponSlot] = None
) -> DiceRoll:
    # Creates appropriate event subclass based on roll_type
    # Fires through DECLARATION → EFFECT → COMPLETION
    # Handlers can modify the roll at EFFECT phase
    # Returns get_effective_roll() result
```

### 4. Lucky Feat Implementation

Created `dnd/classes/feats.py` with:

- `LuckyFeature` condition - Grants 3 luck points (long rest recharge)
- `lucky_processor` - Rerolls d20 when total < 10, keeps better result
- Registers handlers for ATTACK/SAVE/CHECK D20 roll result events

### 5. EventQueue Bug Fix

Fixed `_get_handlers_for_event()` to properly match handlers with complex triggers (those filtering by `event_source_entity_uuid`). The original code required exact trigger equality, but handler triggers may only specify source UUID while event triggers have both source and target.

**Fix**: Now iterates through all handlers and uses `Trigger.__call__(event)` for proper matching.

### 6. Migration: DamageRolledEvent → DamageRollResultEvent

Updated all usages:
- `dnd/actions.py` - Import and usage
- `dnd/classes/fighter.py` - GWF handler trigger
- `examples/test_great_weapon_fighting.py` - Test references

---

## What Was NOT Implemented (Rolled Back)

### Preset/Deterministic Dice System

The original plan included:
- `DiceRoll.preset` field to mark deterministic rolls
- `preset_d20` field on D20RollResultEvent
- `create_preset_d20_roll()` utility function
- Dice preset queue infrastructure

**Why rolled back**: This system was bloating the codebase with complexity for a testing feature that wasn't immediately needed. The Lucky feat works fine with random dice - deterministic testing can be added later if needed.

---

## Files Modified

| File | Changes |
|------|---------|
| `dnd/core/events.py` | Added EventTypes, event classes, fixed `_get_handlers_for_event()` |
| `dnd/entity.py` | Updated `roll_d20()` to fire D20 events |
| `dnd/actions.py` | DamageRolledEvent → DamageRollResultEvent |
| `dnd/classes/fighter.py` | Updated GWF handler EventType |
| `dnd/classes/feats.py` | **NEW** - Lucky feat implementation |
| `examples/test_lucky_feat.py` | **NEW** - Lucky feat tests |
| `examples/test_great_weapon_fighting.py` | Updated references |

---

## Verification

All tests pass:

```bash
python examples/test_lucky_feat.py           # Lucky feat works
python examples/test_great_weapon_fighting.py # GWF still works
python examples/test_indomitable.py          # Save handlers work
python examples/test_barbarian_rage.py       # No regressions
pyright dnd/core/events.py dnd/classes/feats.py  # 0 errors
```

---

## Future Work (If Needed)

1. **Preset Dice for Testing** - Add deterministic dice input for reproducible tests
2. **More D20 Handlers** - Portent, Silvery Barbs, Halfling Lucky
3. **More Damage Handlers** - Savage Attacker feat
