# Event System Combat Log Design

## Overview

**Goal**: Design an event system that automatically generates detailed combat logs without requiring the server/display layer to reach into entity internals.

## Current Problem

The server has a helper function `extract_attack_data_from_event()` in `server/event_server.py` that:

1. Takes a completed `AttackEvent`
2. Reaches into entity internals to extract display data:
   - `target.ac_bonus().normalized_score`
   - `source.equipment._get_weapon_by_slot(weapon_slot)`
   - `attack_bonus_mv.get_breakdown()`
3. Builds formatted combat log entries like:

```
Hero → Skeleton (Scimitar)
  Attack: d20(15) +4 [Prof +2, DEX +2] = 19 vs AC 13 [Armor +13] → HIT
  Damage: 1d6(5) +2 [DEX +2] = 7 slashing
```

### Issues with Current Approach

1. **Coupling**: Server display layer depends on engine internals
2. **Type Safety**: Function uses `getattr()` and `hasattr()` extensively because event types don't guarantee these fields
3. **Duplication**: Same extraction logic needed anywhere combat logs are displayed
4. **Fragility**: Changes to engine internals break display code

### Current Code Example (server/event_server.py)

```python
def extract_attack_data_from_event(event: Event, source: "Entity | None", target: "Entity | None", weapon_name: str) -> dict:
    """
    Extract standardized attack data from an AttackEvent.
    """
    attack_outcome = getattr(event, 'attack_outcome', None)
    damage_rolls = getattr(event, 'damage_rolls', None)
    dice_roll = getattr(event, 'dice_roll', None)
    ac_mv = getattr(event, 'ac', None)
    attack_bonus_mv = getattr(event, 'attack_bonus', None)

    # ... lots of getattr/hasattr checks ...

    # Reaches into entity internals for AC
    if ac_mv:
        target_ac = ac_mv.normalized_score
    elif target:
        target_ac = target.ac_bonus().normalized_score  # <-- coupling to Entity

    # Reaches into equipment internals for dice size
    if source and weapon_slot:
        weapon_obj = source.equipment._get_weapon_by_slot(weapon_slot)  # <-- coupling to Equipment
        if weapon_obj and hasattr(weapon_obj, 'damage_dice'):
            dice_size = weapon_obj.damage_dice
```

## Proposed Design

### Option A: Rich Event Data

Events carry all display data at creation time:

```python
class AttackEvent(Event):
    # Combat data
    attack_outcome: AttackOutcome
    damage_rolls: List[DiceRoll]

    # Pre-computed display data
    display: AttackDisplayData = Field(...)

class AttackDisplayData(BaseModel):
    attacker_name: str
    target_name: str
    weapon_name: str

    # Roll details
    d20_rolls: List[int]
    d20_used: int
    advantage_status: str  # "none", "advantage", "disadvantage"

    # Breakdowns
    attack_bonus_total: int
    attack_breakdown: List[ModifierEntry]  # [{"name": "Prof", "value": 2}, ...]

    target_ac: int
    ac_breakdown: List[ModifierEntry]

    damage_total: int
    damage_dice_str: str  # "1d6"
    damage_breakdown: List[ModifierEntry]
    damage_type: str

    # Formatted strings (optional, for direct display)
    attack_line: str  # "d20(15) +4 [Prof +2, DEX +2] = 19 vs AC 13 → HIT"
    damage_line: str  # "1d6(5) +2 [DEX +2] = 7 slashing"
```

### Option B: Event Formatters

Register formatters that convert events to display data:

```python
class EventFormatter(Protocol):
    def format(self, event: Event) -> DisplayData: ...

# Register formatters by event type
EventQueue.register_formatter(EventType.ATTACK, AttackEventFormatter())
```

### Option C: Display Mixin on Events

Events have a `to_display()` method:

```python
class AttackEvent(Event):
    def to_display(self) -> AttackDisplayData:
        # Event has access to all its own data
        # Can compute display representation
        ...
```

## Tasks for Planner

1. **Analyze** all places where combat log data is extracted/formatted
2. **Catalog** what display data is needed for each event type
3. **Choose** between Option A/B/C (or hybrid)
4. **Design** the display data models
5. **Plan** migration from current `extract_attack_data_from_event()` approach
6. **Consider** extensibility for future event types (spells, conditions, etc.)

## Event Types Needing Combat Log Support

- `ATTACK` - attack rolls, damage, hit/miss/crit
- `MOVEMENT` - position changes, opportunity attacks triggered
- `DAMAGE_ROLLED` - dice manipulation (GWF rerolls)
- `TAKE_DAMAGE` - damage received, resistances applied
- `HEAL` - healing received
- `CONDITION_APPLICATION` - condition added
- `CONDITION_REMOVAL` - condition removed
- `SAVING_THROW` - save rolls and outcomes
- `SKILL_CHECK` - skill check rolls and outcomes

## Success Criteria

1. Server/CLI can format combat logs without accessing entity internals
2. Event types are fully typed (no `getattr`/`hasattr` needed)
3. Display data is computed once at event creation, not on every read
4. Adding new display fields doesn't require changes to server code
