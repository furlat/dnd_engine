# Zone Spells Implementation Plan

## Overview

Five zone spells requiring three different architectural patterns:

| Spell | Pattern | Zone Movement | Key Challenge |
|-------|---------|---------------|---------------|
| **Spike Growth** | Static Tile-Based | None | Per-5ft damage tracking |
| **Grease** | Static Tile-Based | None | Turn-end handler, Prone |
| **Web** | Static Tile-Based | None | Restrained + escape action |
| **Cloudkill** | Controlled Movement | Auto (start of turn) | Zone auto-moves away from caster |
| **Spirit Guardians** | Caster-Centered | Follows caster | Not tile-based at all |

---

## Architecture Patterns

### Pattern 1: Static Tile-Based (Spike Growth, Grease, Web)

Current infrastructure works. Zone is fixed at cast position.

```
Caster: Concentrating(spell_name="Web")
    └── external_conditions ──► WebZone (on caster)
                                    └── terrain_conditions ──► WebTileEffect (on each tile)
```

### Pattern 2: Controlled Movement (Cloudkill)

Zone can be moved. For Cloudkill, movement is **automatic** at start of caster's turn.

```
Caster: Concentrating(spell_name="Cloudkill")
    └── external_conditions ──► CloudkillZone (on caster)
                                    ├── terrain_conditions ──► CloudkillTileEffect (on each tile)
                                    └── EventHandler: TURN_START (caster) → move_zone()
```

**Implementation:**
- Add EventHandler in ZoneControlCondition._apply() that listens for TURN_START
- Handler checks if event.source_entity_uuid == caster.uuid
- Handler calls `self.move_zone(new_position)` with calculated direction

**Movement Direction:** "10 feet away from caster" = calculate vector from caster to zone center, normalize, multiply by 2 tiles.

### Pattern 3: Caster-Centered (Spirit Guardians)

**Critical Insight:** Tile-based is inefficient here. Every caster movement would require:
- Remove N tile conditions from old positions
- Add N tile conditions to new positions
- Delete/recreate N EventHandlers

**Better Approach:** Entity-distance-based handlers, no tile conditions.

```
Caster: Concentrating(spell_name="Spirit Guardians")
    └── external_conditions ──► SpiritGuardiansAura (on caster)
                                    ├── EventHandler: SPATIAL_ENTITY_ENTERED → check distance, save/damage
                                    ├── EventHandler: TURN_START → check distance, save/damage
                                    └── Speed modifier (aura-style) on affected entities
```

**New Class:** `AuraCondition` - doesn't use tiles, uses distance checks

```python
class AuraCondition(BaseCondition):
    """Aura centered on an entity that affects nearby creatures."""
    aura_radius_feet: int = 15

    def is_in_aura(self, entity: Entity) -> bool:
        """Check if entity is within aura radius of the caster."""
        caster = Entity.get(self.source_entity_uuid)
        distance = caster.senses.get_feet_distance(entity.senses.position)
        return distance <= self.aura_radius_feet
```

**Speed Halving:** This is tricky. Options:
1. Add/remove speed modifier dynamically as entities enter/leave
2. Use contextual modifier that checks distance at evaluation time

Option 2 is cleaner - use `ContextualNumericalModifier` on movement that checks aura presence.

**"First time on a turn" tracking:**
- Store `triggered_this_round: Set[UUID]` on the condition
- Clear at start of caster's turn
- Check before triggering save

---

## Infrastructure Additions Needed

### 1. TileEffectCondition Extensions

```python
class TileEffectCondition(BaseCondition):
    # EXISTING
    adds_difficult_terrain: bool = False
    damage_on_entry_dice: Optional[str] = None
    damage_on_entry_type: DamageType = DamageType.FIRE
    damage_on_turn_start_dice: Optional[str] = None
    damage_on_turn_start_type: DamageType = DamageType.FIRE

    # NEW: Per-5ft movement damage (Spike Growth)
    damage_per_5ft_dice: Optional[str] = None
    damage_per_5ft_type: DamageType = DamageType.PIERCING

    # NEW: Turn-end triggers (Grease)
    save_on_turn_end_ability: Optional[str] = None  # "dexterity"
    save_on_turn_end_dc: Optional[int] = None
    condition_on_turn_end_failed_save: Optional[str] = None  # "Prone"

    # NEW: Save-based entry effects (Web, Grease)
    save_on_entry_ability: Optional[str] = None
    save_on_entry_dc: Optional[int] = None
    condition_on_entry_failed_save: Optional[str] = None  # "Restrained"
    save_on_entry_damage_dice: Optional[str] = None  # For Cloudkill (damage on save)
    save_on_entry_damage_type: DamageType = DamageType.POISON
    save_on_entry_half_on_success: bool = False  # Cloudkill does half on success

    # NEW: Save-based turn start effects (Web)
    save_on_turn_start_ability: Optional[str] = None
    save_on_turn_start_dc: Optional[int] = None
    condition_on_turn_start_failed_save: Optional[str] = None
    save_on_turn_start_damage_dice: Optional[str] = None
    save_on_turn_start_damage_type: DamageType = DamageType.POISON
    save_on_turn_start_half_on_success: bool = False
```

### 2. ZoneControlCondition Extensions

```python
class ZoneControlCondition(BaseCondition):
    # EXISTING
    zone_center: Tuple[int, int]
    zone_shape: str
    zone_radius_feet: int
    zone_direction: Optional[Tuple[int, int]]
    affected_positions: List[Tuple[int, int]]

    # NEW: Auto-movement (Cloudkill)
    auto_move_on_caster_turn: bool = False
    auto_move_distance_feet: int = 10
    auto_move_direction: str = "away_from_caster"  # or "toward_caster", "fixed_direction"

    # NEW: Handler tracking for auto-movement
    _movement_handler_uuid: Optional[UUID] = None
```

### 3. New Base Class: AuraCondition

```python
class AuraCondition(BaseCondition):
    """
    Aura effect centered on an entity.

    Unlike ZoneControlCondition, this doesn't use tile conditions.
    Instead, uses distance checks from the source entity.
    More efficient for effects that move with the caster.
    """
    aura_radius_feet: int = 15

    # Damage configuration
    save_ability: Optional[str] = None  # "wisdom"
    save_dc: Optional[int] = None
    damage_dice: Optional[str] = None  # "3d8"
    damage_type: DamageType = DamageType.RADIANT
    half_damage_on_success: bool = True

    # Speed modifier
    speed_modifier: Optional[str] = None  # "half" or numerical

    # Trigger tracking
    triggers_on_entry: bool = True
    triggers_on_turn_start: bool = True
    once_per_turn: bool = True  # Spirit Guardians: "first time on a turn"

    # Ally/enemy filtering
    affects_allies: bool = False
    affects_enemies: bool = True
    designated_unaffected: List[UUID] = []  # Spirit Guardians: caster chooses

    # Internal tracking
    _triggered_this_round: Set[UUID] = set()  # For once_per_turn
    _entry_handler_uuid: Optional[UUID] = None
    _turn_start_handler_uuid: Optional[UUID] = None
```

### 4. Escape Action Mechanism

For Web's "use action to make STR check to escape":

```python
class EscapeRestrainedAction(BaseAction):
    """Action to attempt escaping from a restraining effect."""
    name: str = "Break Free"
    action_type: str = "action"

    # Reference to the condition to remove on success
    restraining_condition_uuid: UUID
    check_ability: str = "strength"  # Could be STR or DEX
    dc: int

    def _apply(self, event: ActionEvent) -> ActionEvent:
        # Make ability check
        entity = Entity.get(event.source_entity_uuid)
        check_result = entity.ability_check(self.check_ability, self.dc)

        if check_result.success:
            # Remove the restraining condition
            condition = BaseObject.get(self.restraining_condition_uuid)
            if condition:
                entity.remove_condition(condition.name)
            # Also remove this action template
            entity.remove_action_template(self.uuid)
```

**Linking:** When WebTileEffect applies Restrained, also register EscapeRestrainedAction template.

---

## Spell Implementations

### Phase 1: Spike Growth (Simplest - No Saves)

**New Infrastructure:**
- `damage_per_5ft_dice` field in TileEffectCondition
- Handler on `StepMovementEvent` (not SPATIAL_ENTITY_ENTERED)

**Spell Files:**
- `dnd/spells/transmutation.py` → `SpikeGrowth`, `SpikeGrowthZone`, `SpikeGrowthTileEffect`

**Key Code:**
```python
class SpikeGrowthTileEffect(TileEffectCondition):
    name: str = "Spike Growth"
    adds_difficult_terrain: bool = True
    damage_per_5ft_dice: str = "2d4"
    damage_per_5ft_type: DamageType = DamageType.PIERCING
```

**Handler Logic:**
```python
def _create_movement_damage_handler(self, tile_uuid: UUID) -> EventHandler:
    """Deal damage for each 5ft of movement through this tile."""
    def processor(event: Event, _) -> Optional[Event]:
        if event.event_type != EventType.STEP_MOVEMENT:
            return None
        # StepMovementEvent has: entity_uuid, from_pos, to_pos
        # Check if to_pos matches this tile
        # If so, deal 2d4 damage (each step is 5ft)
```

**Note:** Need to verify `StepMovementEvent` exists and has the right fields. If not, may need to use SPATIAL_ENTITY_ENTERED which fires per cell anyway.

### Phase 2: Grease (Save + Prone + Turn End)

**New Infrastructure:**
- `save_on_entry_*` fields
- `save_on_turn_end_*` fields
- `_create_turn_end_handler()` method

**Spell Files:**
- `dnd/spells/conjuration.py` → `Grease`, `GreaseZone`, `GreaseTileEffect`

**Key Code:**
```python
class GreaseTileEffect(TileEffectCondition):
    name: str = "Grease"
    adds_difficult_terrain: bool = True  # Slick surface

    # Entry save
    save_on_entry_ability: str = "dexterity"
    save_on_entry_dc: int  # Set from spell
    condition_on_entry_failed_save: str = "Prone"

    # Turn end save
    save_on_turn_end_ability: str = "dexterity"
    save_on_turn_end_dc: int
    condition_on_turn_end_failed_save: str = "Prone"
```

**Initial Cast:** Also need to trigger saves for creatures already in the area when spell is cast.

### Phase 3: Web (Restrained + Escape Action)

**New Infrastructure:**
- Escape action mechanism
- Linking condition to action template

**Spell Files:**
- `dnd/spells/conjuration.py` → `Web`, `WebZone`, `WebTileEffect`, `WebRestrained`

**Special Condition:**
```python
class WebRestrained(BaseCondition):
    """
    Restrained by Web spell.

    Unlike generic Restrained, this:
    - Grants "Break Free" action
    - Can be escaped via STR check vs spell DC
    """
    name: str = "Web Restrained"
    spell_dc: int

    def _apply(self, event):
        # Apply Restrained as sub-condition
        restrained = Restrained(...)
        target.add_condition(restrained)
        sub_conditions.append(restrained.uuid)

        # Register escape action
        escape_action = EscapeRestrainedAction(
            restraining_condition_uuid=self.uuid,
            check_ability="strength",
            dc=self.spell_dc,
            template=True
        )
        target.add_action_template(escape_action)
        # Track for cleanup
        self._escape_action_uuid = escape_action.uuid
```

### Phase 4: Cloudkill (Auto-Movement)

**New Infrastructure:**
- `auto_move_on_caster_turn` in ZoneControlCondition
- TURN_START handler that moves zone

**Spell Files:**
- `dnd/spells/conjuration.py` → `Cloudkill`, `CloudkillZone`, `CloudkillTileEffect`

**Key Code:**
```python
class CloudkillZone(ZoneControlCondition):
    name: str = "Cloudkill Zone"
    zone_shape: str = "sphere"
    zone_radius_feet: int = 20
    auto_move_on_caster_turn: bool = True
    auto_move_distance_feet: int = 10
    auto_move_direction: str = "away_from_caster"

    def _create_movement_handler(self) -> EventHandler:
        def processor(event: Event, _) -> Optional[Event]:
            if event.event_type != EventType.TURN_START:
                return None
            if event.source_entity_uuid != self.source_entity_uuid:
                return None

            # Calculate new position
            caster = Entity.get(self.source_entity_uuid)
            direction = self._get_direction_away_from(caster.senses.position)
            new_center = self._move_in_direction(self.zone_center, direction, 2)  # 10ft = 2 tiles

            self.move_zone(new_center)
            return None
```

**Tile Effect:**
```python
class CloudkillTileEffect(TileEffectCondition):
    name: str = "Cloudkill"
    heavily_obscured: bool = True

    # Entry damage with save
    save_on_entry_ability: str = "constitution"
    save_on_entry_dc: int
    save_on_entry_damage_dice: str = "5d8"
    save_on_entry_damage_type: DamageType = DamageType.POISON
    save_on_entry_half_on_success: bool = True

    # Turn start damage with save
    save_on_turn_start_ability: str = "constitution"
    save_on_turn_start_dc: int
    save_on_turn_start_damage_dice: str = "5d8"
    save_on_turn_start_damage_type: DamageType = DamageType.POISON
    save_on_turn_start_half_on_success: bool = True
```

### Phase 5: Spirit Guardians (Caster-Centered Aura)

**New Infrastructure:**
- `AuraCondition` base class (entirely new pattern)

**Spell Files:**
- `dnd/spells/conjuration.py` → `SpiritGuardians`, `SpiritGuardiansAura`

**Key Code:**
```python
class SpiritGuardiansAura(AuraCondition):
    name: str = "Spirit Guardians"
    aura_radius_feet: int = 15

    save_ability: str = "wisdom"
    save_dc: int
    damage_dice: str = "3d8"
    damage_type: DamageType = DamageType.RADIANT  # Or NECROTIC based on alignment
    half_damage_on_success: bool = True

    triggers_on_entry: bool = True
    triggers_on_turn_start: bool = True
    once_per_turn: bool = True

    speed_modifier: str = "half"
    affects_allies: bool = False
    affects_enemies: bool = True
```

**Handler Logic:**
```python
def _create_entry_handler(self) -> EventHandler:
    def processor(event: Event, _) -> Optional[Event]:
        if event.event_type != EventType.SPATIAL_ENTITY_ENTERED:
            return None

        entity_uuid = event.entity_uuid

        # Skip if already triggered this turn
        if self.once_per_turn and entity_uuid in self._triggered_this_round:
            return None

        # Skip if designated unaffected
        if entity_uuid in self.designated_unaffected:
            return None

        # Check if in aura
        if not self._is_in_aura(entity_uuid):
            return None

        # Check faction
        entity = Entity.get(entity_uuid)
        caster = Entity.get(self.source_entity_uuid)
        if self.affects_enemies and not caster.is_enemy(entity):
            return None

        # Trigger save and damage
        self._trigger_effect(entity)
        self._triggered_this_round.add(entity_uuid)

        return None
```

**Speed Halving via Contextual Modifier:**
```python
# Applied to ALL entities when aura is created
# Uses contextual check to only affect those in range
def speed_half_condition(entity: Entity) -> Optional[NumericalModifier]:
    caster = Entity.get(caster_uuid)
    if caster.senses.get_feet_distance(entity.senses.position) <= 15:
        return NumericalModifier(name="Spirit Guardians", value=-entity.action_economy.movement.base_value // 2)
    return None
```

Actually, this is complex. Simpler: apply/remove modifier dynamically when entities enter/leave. Track in `_entities_in_aura: Set[UUID]`.

---

## Implementation Order

### Week 1: Static Zones

1. **TileEffectCondition extensions** (all new fields)
2. **Spike Growth** - test per-5ft damage
3. **Grease** - test turn-end handler
4. **Web** - test escape action

### Week 2: Moving Zones

5. **ZoneControlCondition auto-movement**
6. **Cloudkill** - test auto-movement
7. **AuraCondition base class**
8. **Spirit Guardians** - test caster-following

---

## Open Questions

### Q1: Per-5ft Damage - Use StepMovementEvent or SPATIAL_ENTITY_ENTERED?

Need to check if `StepMovementEvent` has the right fields. If SPATIAL_ENTITY_ENTERED fires per cell (which it does via Move action), we might just use that.

**Answer needed:** Verify StepMovementEvent exists and what fields it has.

### Q2: How to Handle "First Time on a Turn"?

Options:
1. Store `Set[UUID]` on condition, clear at caster turn start
2. Add marker condition on affected entity, remove at their turn end

Option 1 is simpler but requires handler on caster's TURN_START to clear the set.

### Q3: Speed Halving in Spirit Guardians - Dynamic or Contextual?

Options:
1. **Dynamic:** Add modifier when entity enters, remove when leaves
   - Requires tracking `_entities_in_aura`
   - Handler on SPATIAL_ENTITY_LEFT to remove modifier

2. **Contextual:** Global modifier that checks distance each time
   - Simpler but evaluated every time movement is calculated
   - May have issues with which entity's movement we're checking

Recommendation: **Dynamic** - cleaner semantics, clearer when it applies.

### Q4: Escape Action - How to Link to Condition?

When entity is restrained by Web:
1. WebTileEffect creates WebRestrained on entity
2. WebRestrained creates EscapeRestrainedAction template
3. Action stores condition UUID
4. On success, action removes condition
5. Condition removal removes action template

Need to ensure cleanup works both ways:
- If condition removed (dispel): action template removed
- If action succeeds: condition removed, action removed

### Q5: Grease Initial Cast - How to Trigger Saves for Existing Creatures?

When Grease is cast, creatures already in the area make saves immediately.

Options:
1. In `GreaseZone._apply()`, iterate affected positions, find entities, trigger saves
2. Fire a special "zone created" event that handlers react to

Option 1 is simpler and more explicit.

---

## Test Files Needed

| Spell | Test File | Key Tests |
|-------|-----------|-----------|
| Spike Growth | `test_spike_growth.py` | Per-5ft damage, difficult terrain |
| Grease | `test_grease.py` | Entry save, turn-end save, Prone |
| Web | `test_web.py` | Restrained, escape action, difficult terrain |
| Cloudkill | `test_cloudkill.py` | Auto-movement, damage/save |
| Spirit Guardians | `test_spirit_guardians.py` | Following caster, once-per-turn, speed halving |

---

## File Changes Summary

### New Files
- `dnd/spells/transmutation.py` (Spike Growth)
- `dnd/tile_conditions.py` - AuraCondition class (or new file `dnd/aura_conditions.py`)

### Modified Files
- `dnd/tile_conditions.py` - TileEffectCondition + ZoneControlCondition extensions
- `dnd/spells/conjuration.py` - Grease, Web, Cloudkill, Spirit Guardians
- `dnd/spells/__init__.py` - exports
- `dnd/actions.py` or new file - EscapeRestrainedAction

### Test Files
- `examples/test_spike_growth.py`
- `examples/test_grease.py`
- `examples/test_web.py`
- `examples/test_cloudkill.py`
- `examples/test_spirit_guardians.py`
