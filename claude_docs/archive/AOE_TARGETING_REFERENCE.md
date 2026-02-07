# AoE Targeting Reference

Quick reference for implementing AoE spells in this engine.

## Shape Classes (`dnd/core/aoe.py`)

| Shape | Origin | Key Parameters | Example Spell |
|-------|--------|----------------|---------------|
| Sphere | target position | `radius_feet=20` | Fireball |
| Cone | caster position | `length_feet=15`, `angle_degrees=53` | Burning Hands |
| Line | caster position | `length_feet=100`, `width_feet=5` | Lightning Bolt |
| Cube | varies | `size_feet=15`, `centered=bool` | Thunderwave |

All shapes inherit from `AoEShape` base class and implement:
- `compute_objective(caster_pos)` - Fresh FOV from origin (for damage resolution)
- `compute_subjective(caster_pos, senses)` - Uses caster's existing senses (for targeting preview)

## Target Filtering Fields

These fields on `BaseAction` control who gets affected:

| Field | Default | Purpose |
|-------|---------|---------|
| `include_self` | `False` | Can caster be affected by their own AoE? |
| `valid_target_filter` | `"enemies"` | Who to affect: `"all"`, `"enemies"`, `"allies"`, `"self_or_allies"` |
| `include_dead` | `False` | Target dead entities? (for corpse explosion, resurrection) |

## Implementing an AoE Spell

### 1. Define the Spell Class

```python
from dnd.actions import SpellAction, SpellEvent
from dnd.core.base_actions import TargetType
from dnd.core.aoe import Sphere
from dnd.core.events import Range, RangeType

class Fireball(SpellAction):
    name: str = "Fireball"
    description: str = "20ft radius sphere of fire"
    spell_level: int = 3
    target_type: TargetType = TargetType.POSITION_AOE
    template: bool = True

    # AoE spells hit everyone by default
    include_self: bool = True
    valid_target_filter: str = "all"

    def __init__(self, **data):
        if 'aoe_shape' not in data:
            data['aoe_shape'] = Sphere(
                source_entity_uuid=data.get('source_entity_uuid'),
                radius_feet=20
            )
        super().__init__(**data)

    def get_range(self) -> Range:
        return Range(type=RangeType.RANGE, normal=150)
```

### 2. Implement `_apply()` for Per-Target Effects

The engine calls `_apply()` once per target via convolution. Set `self.target_entity_uuid` before each call.

```python
def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
    """Apply damage to current target (convolution calls this per-target)."""
    target = Entity.get(self.target_entity_uuid)
    caster = Entity.get(self.source_entity_uuid)

    # Roll damage
    damage_dice = Dice(count=8 + upcast_levels, value=6, roll_type=RollType.DAMAGE)
    damage_roll = damage_dice.roll

    # DEX save for half
    save_request = caster.create_saving_throw_request(
        target.uuid, "dexterity", caster.spell_save_dc()
    )
    save_result = target.saving_throw(save_request)

    if save_result.success:
        actual_damage = damage_roll.total // 2
    else:
        actual_damage = damage_roll.total

    target.health.take_damage(actual_damage, DamageType.FIRE, caster.uuid)

    # Return completion event with damage info
    return execution_event.phase_to(
        EventPhase.COMPLETION,
        total_damage=actual_damage,
        save_roll=save_result.roll.total if save_result.roll else None,
        save_bonus=save_result.bonus_breakdown
    )
```

### 3. Register the Spell

```python
from dnd.actions_functional import register_spell, setup_standard_actions

# After creating entity
setup_standard_actions(entity)
register_spell(entity, Fireball, caster_level=5)
```

## How Convolution Works

When `apply()` is called on a POSITION_AOE action:

```
apply()
  ├── _create_declaration_event()  → DECLARATION
  ├── _validate()                   → EXECUTION
  │
  ├── get_all_targets()            → [target_uuid_1, target_uuid_2, ...]
  │     ├── shape.compute_objective()
  │     ├── filter by include_self
  │     ├── filter by valid_target_filter
  │     └── filter by include_dead
  │
  └── FOR EACH target in targets:
        ├── self.target_entity_uuid = target
        └── result = _apply(execution_event)
            └── accumulate: total_damage += result.total_damage

  └── Return COMPLETION event with:
        ├── target_results: List[Event]  (per-target results)
        ├── total_targets: int
        └── total_damage: int
```

## Shape Details

### Sphere

```python
Sphere(
    source_entity_uuid=caster.uuid,
    target=(5, 5),      # Center of explosion
    radius_feet=20      # 4 tiles
)
```

- Origin: target position (explosion center)
- FOV computed from center outward
- Walls block damage (FOV-based)

### Cone

```python
Cone(
    source_entity_uuid=caster.uuid,
    target=(10, 5),     # Direction to point
    length_feet=15,     # 3 tiles
    angle_degrees=53    # D&D 5e standard cone angle
)
```

- Origin: caster position
- Points toward target
- 53° is the D&D 5e standard cone width

### Line

```python
Line(
    source_entity_uuid=caster.uuid,
    target=(100, 5),    # Direction/endpoint
    length_feet=100,    # 20 tiles
    width_feet=5        # 1 tile wide (default)
)
```

- Origin: caster position
- Travels toward target
- Stops at walls or max length

### Cube

```python
Cube(
    source_entity_uuid=caster.uuid,
    target=(10, 5),     # Cube position
    size_feet=15,       # 3x3 tiles
    centered=False      # If True, centered on target; if False, edge at caster
)
```

- `centered=True`: Target is center of cube
- `centered=False`: One edge at caster, extends toward target

## Implemented AoE Spells

| Spell | Level | Shape | Save | Range | Notes |
|-------|-------|-------|------|-------|-------|
| Fireball | 3 | Sphere 20ft | DEX half | 150ft | include_self=True, +1d6/upcast |
| Burning Hands | 1 | Cone 15ft | DEX half | Self | Origin at caster |
| Lightning Bolt | 1 | Line 100ft×5ft | DEX half | 100ft | Stops at walls |
| Thunderwave | 1 | Cube 15ft | CON half | Self | Pushes on fail, cube from caster |
| Shatter | 2 | Sphere 10ft | CON half | 60ft | Smaller radius |

## Testing AoE Spells

Key test files:
- `examples/test_fireball.py` - Comprehensive Fireball tests (10 scenarios)
- `examples/test_aoe_shapes.py` - Shape geometry tests
- `examples/test_aoe_integration.py` - POSITION_AOE + available actions
- `examples/test_burning_hands.py`, `test_lightning_bolt.py`, `test_thunderwave.py`, `test_shatter.py`

Run all AoE tests:
```bash
python examples/test_fireball.py
python examples/test_aoe_shapes.py
python examples/test_aoe_integration.py
```

## Common Patterns

### Enemies-Only AoE (Healing Word AoE variant)

```python
class MassHealingWord(SpellAction):
    include_self: bool = False
    valid_target_filter: str = "allies"  # Only heal allies
```

### AoE That Targets Corpses

```python
class CorpseExplosion(SpellAction):
    include_dead: bool = True  # Targets dead entities
    valid_target_filter: str = "all"
```

### Different Shape for Upcast

Override `__init__` to scale shape size:

```python
def __init__(self, **data):
    upcast = data.get('upcast_levels', 0)
    radius = 20 + (upcast * 5)  # +5ft per level
    data['aoe_shape'] = Sphere(radius_feet=radius, ...)
    super().__init__(**data)
```
