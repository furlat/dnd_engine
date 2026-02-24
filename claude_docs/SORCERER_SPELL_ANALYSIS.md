# Sorcerer Spell Analysis for D&D Engine

**Last Updated:** February 2026

## Overview

This document analyzes all **120 sorcerer spells** from D&D 5e SRD for implementation difficulty in the D&D Engine. It reflects the current state after implementing AoE, concentration, zone spells, the lighting system (Layer 2), stealth/invisibility (Layer 1), and reaction casting.

*Note: A few cross-class spells (Sacred Flame, Guiding Bolt, Call Lightning, Spike Growth, Spirit Guardians, Grease, Eldritch Blast) are tracked here because they are implemented.*

### Spell Count by Level

| Level | Count |
|-------|-------|
| Cantrips | 14 |
| Level 1 | 17 |
| Level 2 | 21 |
| Level 3 | 20 |
| Level 4 | 10 |
| Level 5 | 11 |
| Level 6 | 9 |
| Level 7 | 8 |
| Level 8 | 5 |
| Level 9 | 5 |
| **Total** | **120** |

### Currently Implemented Spells (48)

| Spell | Level | School | Type | Notes |
|-------|-------|--------|------|-------|
| **Cantrips (8)** |
| Fire Bolt | 0 | Evocation | Attack | Cantrip scaling ✓ |
| Sacred Flame | 0 | Evocation | DEX Save | Cantrip scaling ✓ |
| Poison Spray | 0 | Conjuration | CON Save | 10ft range, 1d12 poison ✓ |
| Ray of Frost | 0 | Evocation | Attack | Speed reduction ✓ |
| Acid Splash | 0 | Conjuration | DEX Save | 2-target cantrip ✓ |
| Chill Touch | 0 | Necromancy | Attack | NoHealing condition ✓ |
| Shocking Grasp | 0 | Evocation | Melee Attack | Melee spell attack, NoReactions ✓ |
| Eldritch Blast | 0 | Evocation | Attack | Warlock cantrip, multi-beam scaling ✓ |
| **Level 1 (12)** |
| Magic Missile | 1 | Evocation | Auto-hit | Upcasting, multi-target ✓ |
| Mage Armor | 1 | Abjuration | Buff | AC = 13 + DEX ✓ |
| Burning Hands | 1 | Evocation | Cone AoE | 15ft cone, DEX save ✓ |
| Thunderwave | 1 | Evocation | Cube AoE | 15ft cube, CON save, push ✓ |
| False Life | 1 | Necromancy | Buff | 1d4+4 temp HP, upcasts ✓ |
| Charm Person | 1 | Enchantment | WIS Save | Charmed condition ✓ |
| Sleep | 1 | Enchantment | HP-Pool AoE | 20ft sphere, sorted by HP ✓ |
| Color Spray | 1 | Illusion | HP-Pool Cone | 15ft cone, Blinded ✓ |
| Guiding Bolt | 1 | Evocation | Attack + Mark | 4d6 radiant, next attack has adv ✓ |
| Grease | 1 | Conjuration | Zone | 10ft cube, DEX save → Prone ✓ |
| Fog Cloud | 1 | Conjuration | Zone | 20ft sphere, heavily obscured (Pattern 13) ✓ |
| Shield | 1 | Abjuration | Reaction | +5 AC until start of next turn (Pattern 10) ✓ |
| **Level 2 (10)** |
| Hold Person | 2 | Enchantment | WIS Save | Humanoid only, paralyzed ✓ |
| Shatter | 2 | Evocation | Sphere AoE | 10ft sphere, CON save ✓ |
| Scorching Ray | 2 | Evocation | Multi-attack | 3× 2d6 fire rays ✓ |
| Blur | 2 | Illusion | Buff | Disadvantage on attacks vs you ✓ |
| Misty Step | 2 | Conjuration | Teleport | Bonus action 30ft ✓ |
| Blindness/Deafness | 2 | Necromancy | CON Save | Apply condition ✓ |
| Spike Growth | 2 | Transmutation | Zone | 20ft sphere, 2d4 per 5ft ✓ |
| Web | 2 | Conjuration | Zone | 20ft cube, DEX → Restrained ✓ |
| Invisibility | 2 | Illusion | Buff | Invisible, breaks on action (Pattern 14) ✓ |
| Darkness | 2 | Evocation | Zone | 15ft magical darkness (Pattern 13) ✓ |
| **Level 3 (8)** |
| Call Lightning | 3 | Conjuration | Conc + Action | Grants strike action ✓ |
| Fireball | 3 | Evocation | Sphere AoE | 20ft sphere, DEX save ✓ |
| Lightning Bolt | 3 | Evocation | Line AoE | 100ft×5ft line, DEX save ✓ |
| Protection from Energy | 3 | Abjuration | Buff | Single type resistance ✓ |
| Fear | 3 | Illusion | Cone AoE | Frightened + forced dash ✓ |
| Hypnotic Pattern | 3 | Illusion | Cube AoE | Charmed + incapacitated ✓ |
| Spirit Guardians | 3 | Conjuration | Zone | 15ft sphere, follows caster ✓ |
| Daylight | 3 | Evocation | Light Zone | 60ft bright light sphere (Pattern 13) ✓ |
| **Level 4 (3)** |
| Blight | 4 | Necromancy | CON Save | 8d8 necrotic ✓ |
| Stoneskin | 4 | Abjuration | Buff | B/P/S resistance ✓ |
| Greater Invisibility | 4 | Illusion | Buff | Invisible, Stealth check to maintain (Pattern 15) ✓ |
| **Level 5 (3)** |
| Hold Monster | 5 | Enchantment | WIS Save | Any creature, paralyzed ✓ |
| Cone of Cold | 5 | Evocation | Cone AoE | 60ft cone, 8d8 cold ✓ |
| Cloudkill | 5 | Conjuration | Zone | 20ft sphere, auto-moves ✓ |
| **Level 6 (1)** |
| Circle of Death | 6 | Necromancy | Sphere AoE | 60ft sphere, 8d6 necrotic ✓ |
| **Level 8 (2)** |
| Sunburst | 8 | Evocation | Sphere AoE | 60ft sphere, blind, undead disadv ✓ |
| Power Word Stun | 8 | Enchantment | HP-Threshold | Stunned if ≤150 HP, CON repeat save ✓ |
| **Level 9 (1)** |
| Power Word Kill | 9 | Enchantment | HP-check | Kill if ≤100 HP ✓ |

*Cross-class: Sacred Flame, Guiding Bolt = Cleric. Call Lightning, Spike Growth = Druid. Spirit Guardians = Cleric. Grease = Wizard. Eldritch Blast = Warlock.*

---

## Implementation Patterns Catalog

These patterns document the tricks and techniques already used in the codebase. Recognizing which pattern a spell uses determines its difficulty rating.

### Critical: Event Relationship Pattern (parent_event)

**All sub-events must link to their parent event** via the `parent_event` parameter. This ensures:
1. Combat log entries nest correctly (sub-events appear as `sub_entries` of parent)
2. No orphan events that trigger duplicate combat log callbacks
3. Clear event hierarchy for debugging

**Rule:** Only events with `parent_event=None` trigger the combat log callback. Child events need `parent_event` set.

**Signature differences by method:**

| Method | `parent_event` Type | Pattern |
|--------|---------------------|---------|
| `Entity.add_condition()` | `Event` object | `parent_event=effect_event` or `parent_event=event` |
| `Entity.receive_damage()` | `UUID` | `parent_event=event.uuid` |
| `Entity.create_saving_throw_request()` | `UUID` | `parent_event=event.uuid` |

**In SpellAction._apply(execution_event):**
```python
effect_event = execution_event.phase_to(EventPhase.EFFECT, ...)

# Conditions are children of the effect event
target.add_condition(spell_effect, parent_event=effect_event)
caster.add_condition(concentration, parent_event=effect_event)

# Damage and saves take UUID
target.receive_damage(..., parent_event=effect_event.uuid)
save_request = caster.create_saving_throw_request(..., parent_event=effect_event.uuid)
```

**In BaseCondition._apply(declaration_event):**
```python
execution_event = declaration_event.phase_to(EventPhase.EXECUTION, ...)

# Sub-conditions are children of the execution event
target.add_condition(paralyzed, parent_event=execution_event)
```

**In EventHandler processors (zone spells):**
```python
def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
    # The event passed to processor is the parent
    entity.add_condition(prone, parent_event=event)
    entity.receive_damage(..., parent_event=event.uuid)
    save_request = entity.create_saving_throw_request(..., parent_event=event.uuid)
```

**Important:** `parent_event` for add_condition is the Event object, NOT the UUID!

### Pattern 1: Single-Target Attack Spell
**Used by:** Fire Bolt, Eldritch Blast
**Effort:** TRIVIAL for new spells using this pattern

```
1. Get spell_attack_bonus from caster
2. Cross-propagate with target AC via set_from_target()
3. roll_d20() → determine_attack_outcome()
4. Apply damage on hit (with crit handling)
```

### Pattern 2: Single-Target Save Spell
**Used by:** Sacred Flame
**Effort:** TRIVIAL for new spells using this pattern

```python
def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
    dc = caster.spell_save_dc()

    effect_event = execution_event.phase_to(EventPhase.EFFECT, ...)

    # Save request takes UUID (parent_event=effect_event.uuid)
    save_request = caster.create_saving_throw_request(
        target_entity_uuid=target.uuid,
        ability_name="dexterity",
        dc=dc,
        parent_event=effect_event.uuid  # UUID!
    )
    _, save_roll, success = target.saving_throw(save_request)

    # Damage takes UUID (parent_event=effect_event.uuid)
    final_damage = damage_roll.total if not success else damage_roll.total // 2
    target.receive_damage(final_damage, damage_type, caster.uuid, parent_event=effect_event.uuid)

    return effect_event.phase_to(EventPhase.COMPLETION, ...)
```

**Key:** `receive_damage()` and `create_saving_throw_request()` take `event.uuid` (UUID), not the Event object.

### Pattern 3: AoE Save Spell (Convolution)
**Used by:** Fireball, Lightning Bolt, Burning Hands, Thunderwave, Shatter
**Effort:** EASY - just clone and change shape/damage/save

```python
class MyAoE(SpellAction):
    target_type: TargetType = Field(default=TargetType.POSITION_AOE)
    aoe_shape: AoEShape = Field(default_factory=lambda: AoEShape(type="sphere", radius=20))

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        # Called once per affected entity via convolution
        dc = caster.spell_save_dc()

        effect_event = execution_event.phase_to(EventPhase.EFFECT, ...)

        # Save request takes UUID
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=dc,
            parent_event=effect_event.uuid  # UUID!
        )
        _, save_roll, success = target.saving_throw(save_request)

        # Damage takes UUID
        final_damage = damage_roll.total if not success else damage_roll.total // 2
        target.receive_damage(final_damage, damage_type, caster.uuid, parent_event=effect_event.uuid)

        # If applying conditions (e.g., Thunderwave push), use Event object
        if not success and self.has_push_effect:
            # Forced movement or conditions take Event object
            # ... forced movement handling ...

        return effect_event.phase_to(EventPhase.COMPLETION, ...)
```
**Key insight:** FOV from explosion center blocks entities behind walls. Each target gets its own event chain via convolution.

### Pattern 4: Multi-Target Explicit Selection
**Used by:** Magic Missile
**Effort:** EASY for similar spells

```
1. target_type = MULTI_ENTITY
2. Override get_all_targets() to handle dart/projectile distribution
3. Convolution loop applies per-projectile
```

### Pattern 5: Buff Condition (Concentration)
**Used by:** Mage Armor, Hold Person, Call Lightning
**Effort:** EASY once condition is written

```python
def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
    # ... validation ...

    effect_event = execution_event.phase_to(EventPhase.EFFECT, ...)

    # 1. Apply spell-effect condition to target (MUST pass parent_event)
    spell_effect = MySpellEffect(source=caster.uuid, target=target.uuid)
    target.add_condition(spell_effect, parent_event=effect_event)

    # 2. Apply Concentrating to caster (MUST pass parent_event)
    concentration = Concentrating(source=caster.uuid, target=caster.uuid, spell_name="My Spell")
    caster.add_condition(concentration, parent_event=effect_event)

    # 3. Link via external_conditions for auto-cleanup
    concentration.add_external_condition(target.uuid, spell_effect.uuid)

    # 4. Optional: repeat saves via EventHandler on TURN_END (in spell_effect._apply())

    return effect_event.phase_to(EventPhase.COMPLETION, ...)
```

**Key:** Always pass `parent_event=effect_event` to `add_condition()` - this links condition events to the spell event for proper combat log nesting.

### Pattern 6: Granted Action
**Used by:** Call Lightning (grants CallLightningStrike action)
**Effort:** MEDIUM - requires new action class

```
1. Concentration spell applies condition to caster
2. Condition's _apply() registers new action template
3. Action available each turn while concentrating
4. Cleanup: unregister action when concentration breaks
```

### Pattern 7: Forced Movement (Push/Pull)
**Used by:** Thunderwave
**Effort:** EASY - pattern is established

```
1. On failed save, calculate push direction (away from caster)
2. Move target tile by tile checking walkable
3. Use FORCED_MOVEMENT event type (no opportunity attacks)
```

### Pattern 8: Zone Spells (Position-Indexed Spatial Handlers)
**Used by:** Spike Growth, Grease, Web, Cloudkill, Spirit Guardians, Fog Cloud, Darkness, Daylight
**Effort:** EASY - established pattern with ZoneControlCondition base class

**Architecture:** Uses O(1) position-indexed handler lookup instead of O(tiles) handlers:
```
Caster: Concentrating(spell_name="Web")
    └── external_conditions → WebZone (ZoneControlCondition on caster)
                                 ├── _entry_handler_uuid (ONE handler for ALL positions)
                                 ├── _exit_handler_uuid  (ONE handler for ALL positions)
                                 ├── _turn_start_handler_uuid (regular event handler)
                                 └── _terrain_modifier_uuids (modifiers on tiles)
```

**Implementation (subclass ZoneControlCondition):**
```python
class MyZone(ZoneControlCondition):
    name: str = "My Zone"
    zone_shape: str = "sphere"  # or "cube", "cone", "line"
    zone_radius_feet: int = 20
    adds_difficult_terrain: bool = True  # Built-in
    spell_dc: int = 15

    def _has_entry_effect(self) -> bool:
        return True  # Triggers _create_zone_entry_handler()

    def _has_turn_start_effect(self) -> bool:
        return True  # Triggers _create_zone_turn_start_handler()

    def _create_zone_entry_handler(self) -> EventHandler:
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            entity_uuid = getattr(event, 'entity_uuid', None)
            entity = Entity.get(entity_uuid)
            if not entity:
                return None

            # Saves take UUID (parent_event=event.uuid)
            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="dexterity",
                dc=dc,
                parent_event=event.uuid  # UUID!
            )
            _, _, success = entity.saving_throw(save_request)

            if not success:
                # Conditions take Event object (parent_event=event)
                prone = Prone(source_entity_uuid=source_uuid, target_entity_uuid=entity.uuid)
                entity.add_condition(prone, parent_event=event)  # Event object!

                # Damage takes UUID (parent_event=event.uuid)
                entity.receive_damage(10, DamageType.FIRE, source_uuid, parent_event=event.uuid)

            return None

        return EventHandler(...)
```

**Key:** In handler processors, the `event` parameter IS the parent. Pass `event` (object) to `add_condition`, `event.uuid` to damage/saves.

**Zone movement (Spirit Guardians, Cloudkill):**
```python
def move_zone(self, new_center):
    self._remove_terrain_modifiers()
    self.zone_center = new_center
    new_positions = self._compute_affected_positions()
    EventQueue.update_spatial_handler_positions(  # O(delta) update
        self._entry_handler_uuid, new_positions, ...
    )
    self._apply_terrain_modifiers()
```

**Key insight:** Zone spells are now EASY - just subclass ZoneControlCondition and override `_has_*_effect()` + `_create_*_handler()` methods.

**Phase ordering for turn start handlers:** Zone spell turn-start effects (Grease prone, Cloudkill damage) must use `EventPhase.EXECUTION` so they fire BEFORE the entity's action_economy resets. This allows Prone auto-stand (at `EFFECT` phase) to properly consume movement. See "Turn Start Phase Ordering" section below.

### Pattern 9: HP-Threshold Effect
**Used by:** Power Word Kill, Power Word Stun
**Effort:** EASY - simple HP check

```
For threshold: Check target.get_hp() against threshold → instant effect
  - Power Word Kill: HP ≤ 100 → instant death
  - Power Word Stun: HP ≤ 150 → Stunned + CON repeat save at turn end
No saving throw - just HP check determines success.
```

### Pattern 10: Reaction Spell
**Used by:** Shield
**Effort:** EASY - uses existing EventHandler pattern (same as Protection fighting style)

**Key insight:** Reaction spells use the EXACT same pattern as opportunity attacks and Protection fighting style. NO new trigger system needed!

```
1. EventHandler listens for trigger event (ATTACK at EXECUTION phase)
2. Check conditions (target is me, have reaction, have spell slot)
3. Modify event (add AC modifier, add disadvantage, or cancel spell)
4. Consume reaction + spell slot
5. Apply duration condition if needed (Shield: "until start of next turn")
```

**Example - Shield (same pattern as Protection):**
- Protection: listens for ATTACK at EXECUTION, adds disadvantage to attack_bonus
- Shield: listens for ATTACK at EXECUTION, adds +5 to AC

Both `attack_bonus` and `ac` are attached to the ATTACK event at EXECUTION phase.

**Counterspell** will use the same pattern on `CAST_SPELL` event: listen at EXECUTION, check spell level vs Counterspell slot level, cancel or ability check.

### Pattern 11: Melee Spell Attack
**Used by:** Shocking Grasp
**Effort:** EASY once pattern established

```
1. Use RangeType.REACH with normal=5 (melee range)
2. Get spell_attack_bonus from caster (NOT weapon attack)
3. Cross-propagate with target AC via set_from_target()
4. roll_d20() → determine_attack_outcome()
5. Apply damage on hit + additional effects (NoReactions for Shocking Grasp)
6. Optional: Conditional advantage (metal armor detection)
```
**Key insight:** Uses spell attack bonus, not weapon attack. Can check equipment for conditional effects.

### Pattern 12: HP-Pool AoE
**Used by:** Sleep, Color Spray
**Effort:** EASY - straightforward algorithm

```
1. Get AoE candidates (sphere/cone based on shape)
2. Filter by immunity (undead, charm-immune for Sleep)
3. Sort targets by current HP (ascending)
4. Select targets until HP pool exhausted
5. Apply condition to each selected target (Unconscious/Blinded)
```
**Key insight:** Override `get_all_targets()` to implement HP-pool selection. Works with any AoE shape.

### Pattern 13: Light-Level Zone
**Used by:** Fog Cloud, Darkness, Daylight
**Effort:** EASY - built into ZoneControlCondition

Zone spells that modify light levels on affected tiles. No event handlers needed for the light effect — the `sets_light_level` field on `ZoneControlCondition` handles everything.

**Key fields on ZoneControlCondition:**
```python
sets_light_level: Optional[LightLevel] = None     # Light level to apply to zone tiles
light_is_obscurement: bool = False                  # True = add_obscurement(), False = add_illumination()
```

**LightLevel values** (`dnd/core/base_block.py`):
- `MAGICAL_DARKNESS = 0` — Blocks all vision including darkvision (Darkness spell)
- `DARKNESS = 1` — No light, blocks normal vision (Fog Cloud as obscurement)
- `VERY_BRIGHT = 4` — Bright light, reveals hidden entities (Daylight spell)

**Implementation — just set two fields:**
```python
class FogCloudZone(ZoneControlCondition):
    name: str = "Fog Cloud"
    zone_shape: str = "sphere"
    zone_radius_feet: int = 20
    sets_light_level: Optional[LightLevel] = LightLevel.DARKNESS
    light_is_obscurement: bool = True    # Uses tile.add_obscurement()

class DarknessZone(ZoneControlCondition):
    name: str = "Darkness"
    zone_shape: str = "sphere"
    zone_radius_feet: int = 15
    sets_light_level: Optional[LightLevel] = LightLevel.MAGICAL_DARKNESS
    light_is_obscurement: bool = True    # Blocks darkvision too

class DaylightZone(ZoneControlCondition):
    name: str = "Daylight"
    zone_shape: str = "sphere"
    zone_radius_feet: int = 60
    sets_light_level: Optional[LightLevel] = LightLevel.VERY_BRIGHT
    light_is_obscurement: bool = False   # Uses tile.add_illumination()
```

**Under the hood:** `ZoneControlCondition._apply_light_modifiers()` iterates affected positions, calls `tile.add_obscurement()` or `tile.add_illumination()`, and fires a batch `SPATIAL_LIGHT_CHANGED` event. Cleanup via `_remove_light_modifiers()`.

### Pattern 14: Break-on-Action Invisibility
**Used by:** Invisibility spell (`InvisibilityEffect`)
**Effort:** MEDIUM - condition + reveal handler + lineage tracking

Self-buff condition that grants Invisible and auto-removes on attack/spell/revealing action. Uses `creation_lineage_uuid` to prevent the casting action from immediately breaking the invisibility.

```python
class InvisibilityEffect(BaseCondition):
    name: str = "Invisible"
    creation_lineage_uuid: Optional[UUID] = None  # Lineage of the event that created this

    def _apply(self, declaration_event: Event) -> ...:
        target_entity = Entity.get(self.target_entity_uuid)
        target_entity.set_invisible(True)

        # Store creation lineage to prevent self-triggering
        self.creation_lineage_uuid = declaration_event.lineage_uuid

        # Add unseen attacker advantage (contextual - only when target can't see us)
        # Add unseen target disadvantage (contextual - only when attacker can't see us)

        # Register reveal handler on ATTACK/CAST_SPELL/BASE_ACTION at EFFECT phase
        handler = EventHandler(
            name="Invisibility: Reveal",
            source_entity_uuid=target_entity.uuid,
            trigger_conditions=[
                Trigger(event_type=EventType.ATTACK, event_phase=EventPhase.EFFECT,
                        event_source_entity_uuid=target_entity.uuid),
                Trigger(event_type=EventType.CAST_SPELL, event_phase=EventPhase.EFFECT,
                        event_source_entity_uuid=target_entity.uuid),
                Trigger(event_type=EventType.BASE_ACTION, event_phase=EventPhase.EFFECT,
                        event_source_entity_uuid=target_entity.uuid),
            ],
            event_processor=invisibility_reveal_processor
        )
```

**Reveal processor logic:**
```python
NON_REVEALING_ACTIONS = {"Dash", "Dodge", "Disengage", "Hide", "Stand Up", "Drop Prone",
                         "Open Door", "Close Door", "Ignite Torch", ...}

def invisibility_reveal_processor(event, source_entity_uuid):
    if not event.is_last:           # Only on last EFFECT event
        return None
    if event.event_type == EventType.BASE_ACTION:
        if event.name in NON_REVEALING_ACTIONS:
            return None             # Quiet actions don't break invisibility
    # Check creation lineage to prevent self-triggering
    if condition.creation_lineage_uuid == event.lineage_uuid:
        return None
    entity.remove_condition("Invisible", parent_event=event)
```

### Pattern 15: Stealth-Check Buff (Greater Invisibility)
**Used by:** Greater Invisibility spell (`GreaterInvisibilityEffect`)
**Effort:** MEDIUM - like Pattern 14 but with escalating DC check

BG3-style Greater Invisibility: instead of auto-removing on action, rolls a Stealth check vs escalating DC. Fails = invisibility breaks. Succeeds = stays invisible but DC increases.

```python
class GreaterInvisibilityEffect(BaseCondition):
    name: str = "Invisible"          # Same name as InvisibilityEffect (shared flag)
    check_count: int = 0             # Number of successful stealth checks
    base_dc: int = 15                # Starting DC for stealth check
    creation_lineage_uuid: Optional[UUID] = None

    def _apply(self, declaration_event: Event) -> ...:
        # Same as InvisibilityEffect: set_invisible(True), advantage/disadvantage modifiers
        # But handler calls greater_invisibility_check_processor instead
```

**Check processor logic:**
```python
def greater_invisibility_check_processor(event, source_entity_uuid):
    # Same guards as Pattern 14 (is_last, NON_REVEALING_ACTIONS, creation_lineage)
    dc = condition.base_dc + condition.check_count   # DC escalates: 15, 16, 17...
    stealth_roll = entity.roll_stealth_check()
    if stealth_roll >= dc:
        condition.check_count += 1   # Success: DC increases next time
    else:
        entity.remove_condition("Invisible", parent_event=event)  # Failure: breaks
```

**Key differences from Pattern 14:**
| Feature | Pattern 14 (Invisibility) | Pattern 15 (Greater Invisibility) |
|---------|---------------------------|-----------------------------------|
| On action | Auto-removes | Stealth check vs DC |
| DC | N/A | base_dc + check_count (escalating) |
| Concentration | Yes | Yes |

---

## Systems Status

| System | Status | Spells Enabled |
|--------|--------|----------------|
| **AoE Shapes (Sphere)** | ✅ COMPLETE | Fireball, Shatter, Circle of Death, Sunburst |
| **AoE Shapes (Cone)** | ✅ COMPLETE | Burning Hands, Cone of Cold, Fear |
| **AoE Shapes (Line)** | ✅ COMPLETE | Lightning Bolt, Sunbeam |
| **AoE Shapes (Cube)** | ✅ COMPLETE | Thunderwave, Hypnotic Pattern, Slow |
| **Multi-Entity Targeting** | ✅ COMPLETE | Magic Missile, Scorching Ray |
| **Concentration** | ✅ COMPLETE | Hold Person, Call Lightning, all conc. spells |
| **Cantrip Scaling** | ✅ COMPLETE | All cantrips |
| **Upcasting** | ✅ COMPLETE | All leveled spells |
| **Forced Movement** | ✅ COMPLETE | Thunderwave, Gust of Wind |
| **Spatial Events** | ✅ COMPLETE | Full 4-phase lifecycle for zone spells |
| **Dead Entity Filter** | ✅ COMPLETE | AoE spells skip dead entities |
| **Zone/Terrain Spells** | ✅ COMPLETE | Spike Growth, Grease, Web, Cloudkill, Spirit Guardians, Fog Cloud, Darkness, Daylight |
| **Position-Indexed Handlers** | ✅ COMPLETE | O(1) lookup for zone spell effects |
| **Zone Movement** | ✅ COMPLETE | Spirit Guardians follows caster, Cloudkill auto-moves |
| **Prone Auto-Stand (BG3)** | ✅ COMPLETE | Auto-stand at turn start, costs half movement |
| **HP-Pool Mechanics** | ✅ COMPLETE | Sleep, Color Spray |
| **Simple Teleportation** | ✅ COMPLETE | Misty Step (bonus action 30ft) |
| **Reaction Casting** | ✅ COMPLETE | Shield (Pattern 10). Counterspell uses same pattern. |
| **Vision/Light System** | ✅ COMPLETE | Fog Cloud, Darkness, Daylight (Pattern 13). Per-tile light levels, sense modes, darkvision. |
| **Stealth/Invisibility** | ✅ COMPLETE | Invisibility (Pattern 14), Greater Invisibility (Pattern 15). Hidden, Invisible, GreaterInvisible conditions. |
| **Complex Teleportation** | ❌ NOT STARTED | Teleport (accuracy table, familiarity system) |
| **Mind Control/AI** | ❌ OUT OF SCOPE | Dominate spells, Confusion |
| **Summoning** | ❌ OUT OF SCOPE | Animate Objects |
| **Polymorph** | ❌ OUT OF SCOPE | Complete stat replacement |

---

## Difficulty Categories

| Category | Definition | Implementation Effort |
|----------|------------|----------------------|
| **DONE** | Already implemented | N/A |
| **TRIVIAL** | Clone existing spell, change parameters only | < 30 min |
| **EASY** | Uses established pattern with minor additions | 30 min - 2 hours |
| **MEDIUM** | New condition or moderate new code | 2-6 hours |
| **HARD** | New subsystem or significant architecture | 1-2 days |
| **VERY HARD** | Major new architecture (summoning, polymorph) | 1+ weeks |
| **BLOCKED** | No mechanical combat effect or requires GM adjudication | N/A |

---

## Cantrips (14 SRD + 1 cross-class)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| **Acid Splash** | Conjuration | DEX Save | 1d6 acid, 2 targets within 5ft | **DONE** | 2-target cantrip ✓ |
| **Chill Touch** | Necromancy | Attack | 1d8 necrotic, prevents healing | **DONE** | Pattern 1 + NoHealing condition ✓ |
| **Dancing Lights** | Evocation | Utility | Creates lights | BLOCKED | No combat effect |
| **Eldritch Blast†** | Evocation | Attack | 1d10 force, multi-beam | **DONE** | Pattern 1, beam scaling ✓ |
| **Fire Bolt** | Evocation | Attack | 1d10 fire | **DONE** | Pattern 1 ✓ |
| **Light** | Evocation | Utility | Object sheds light | BLOCKED | No combat effect |
| **Mage Hand** | Conjuration | Utility | Spectral hand | BLOCKED | No combat effect |
| **Mending** | Transmutation | Utility | Repair objects | BLOCKED | No combat effect |
| **Message** | Transmutation | Utility | Whispered communication | BLOCKED | No combat effect |
| **Minor Illusion** | Illusion | Utility | Create sound/image | BLOCKED | No combat effect |
| **Poison Spray** | Conjuration | CON Save | 1d12 poison, 10ft range | **DONE** | 10ft cantrip ✓ |
| **Prestidigitation** | Transmutation | Utility | Minor tricks | BLOCKED | No combat effect |
| **Ray of Frost** | Evocation | Attack | 1d8 cold, -10 speed | **DONE** | Speed reduction ✓ |
| **Shocking Grasp** | Evocation | Melee Attack | 1d8 lightning, no reactions | **DONE** | Pattern 11, metal armor adv ✓ |
| **True Strike** | Divination | Buff | Advantage on next attack | MEDIUM | Delayed buff condition |

### Cantrip Summary
- **DONE**: 8 (Fire Bolt, Sacred Flame*, Poison Spray, Ray of Frost, Acid Splash, Chill Touch, Shocking Grasp, Eldritch Blast†)
- **MEDIUM**: 1 (True Strike)
- **BLOCKED**: 6 (utility cantrips)

*Sacred Flame is Cleric but implemented. †Eldritch Blast is Warlock but implemented.

---

## Level 1 Spells (17 SRD + 2 cross-class)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| **Burning Hands** | Evocation | Cone AoE | 3d6 fire, 15ft cone | **DONE** | Pattern 3 ✓ |
| **Charm Person** | Enchantment | WIS Save | Charmed condition | **DONE** | Pattern 5 + duration ✓ |
| **Color Spray** | Illusion | HP-pool | Blinds by HP pool, cone | **DONE** | Pattern 12 (HP-pool cone) ✓ |
| **Comprehend Languages** | Divination | Utility | Understand languages | BLOCKED | No combat effect |
| **Detect Magic** | Divination | Utility | Sense magic | BLOCKED | No combat effect |
| **Disguise Self** | Illusion | Utility | Change appearance | BLOCKED | No combat effect |
| **Expeditious Retreat** | Transmutation | Buff | Bonus action Dash each turn | EASY | Pattern 6, Dash exists |
| **False Life** | Necromancy | Buff | 1d4+4 temp HP | **DONE** | Temp HP, upcasting ✓ |
| **Feather Fall** | Transmutation | Reaction | Slow falling | BLOCKED | Requires Z-axis & falling damage |
| **Fog Cloud** | Conjuration | Zone | 20ft sphere obscured | **DONE** | Pattern 8 + 13 (light-level zone) ✓ |
| **Grease†** | Conjuration | Zone | 10ft cube, DEX → Prone | **DONE** | Pattern 8, difficult terrain ✓ |
| **Guiding Bolt†** | Evocation | Attack + Mark | 4d6 radiant, next attack adv | **DONE** | Pattern 1 + mark condition ✓ |
| **Jump** | Transmutation | Buff | Triple jump distance | EASY | Jump distance modifiers (needs `jump_bonus_multiply`) |
| **Mage Armor** | Abjuration | Buff | AC = 13 + DEX | **DONE** | Pattern 5 ✓ |
| **Magic Missile** | Evocation | Auto-hit | 3× 1d4+1 force | **DONE** | Pattern 4 ✓ |
| **Shield** | Abjuration | Reaction | +5 AC | **DONE** | Pattern 10 (reaction spell) ✓ |
| **Silent Image** | Illusion | Utility | Create illusion | BLOCKED | No combat effect |
| **Sleep** | Enchantment | HP-pool | Unconscious by HP | **DONE** | Pattern 12 (HP-pool sphere) ✓ |
| **Thunderwave** | Evocation | Cube AoE | 2d8 thunder, push | **DONE** | Pattern 3 + 7 ✓ |

### Level 1 Summary
- **DONE**: 12 (Burning Hands, Mage Armor, Magic Missile, Thunderwave, False Life, Charm Person, Sleep, Color Spray, Guiding Bolt†, Grease†, Fog Cloud, Shield)
- **EASY**: 2 (Expeditious Retreat, Jump)
- **BLOCKED**: 5 (utility spells + Feather Fall)

†Guiding Bolt = Cleric, Grease = Wizard (but implemented)

---

## Level 2 Spells (21 SRD + 1 cross-class)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| **Alter Self** | Transmutation | Buff | Aquatic/Weapons/Appearance | MEDIUM | Natural Weapons option |
| **Blindness/Deafness** | Necromancy | CON Save | Blinded or Deafened | **DONE** | Conditions exist ✓ |
| **Blur** | Illusion | Buff | Disadvantage on attacks vs you | **DONE** | to_target modifier ✓ |
| **Darkness** | Evocation | Zone | 15ft magical darkness | **DONE** | Pattern 8 + 13 (light-level zone) ✓ |
| **Darkvision** | Transmutation | Buff | 60ft darkvision | EASY | Grant Darkvision sense mode (lighting system complete) |
| **Detect Thoughts** | Divination | Utility | Read minds | BLOCKED | No combat effect |
| **Enhance Ability** | Transmutation | Buff | Advantage on ability checks | EASY | Ability check modifier |
| **Enlarge/Reduce** | Transmutation | Buff | Size change, ±1d4 damage | MEDIUM | BG3-style: damage/STR effects, Entity.size field |
| **Gust of Wind** | Evocation | Line | 60ft line, push 15ft | EASY | Pattern 3 + 7 + 8 (line push zone) |
| **Hold Person** | Enchantment | WIS Save | Paralyzed | **DONE** | Pattern 5, humanoid check ✓ |
| **Invisibility** | Illusion | Buff | Invisible, ends on attack | **DONE** | Pattern 14 (break-on-action) ✓ |
| **Knock** | Transmutation | Utility | Unlock objects | BLOCKED | No combat effect |
| **Levitate** | Transmutation | Control | Lift creature 20ft | MEDIUM | Hovering state |
| **Mirror Image** | Illusion | Buff | 3 duplicates absorb attacks | MEDIUM | d20 redirect handler, duplicate tracking |
| **Misty Step** | Conjuration | Teleport | Bonus action 30ft teleport | **DONE** | Bonus action teleport ✓ |
| **Scorching Ray** | Evocation | Multi-attack | 3× 2d6 fire | **DONE** | Pattern 4 ✓ |
| **See Invisibility** | Divination | Buff | See invisible/ethereal | EASY | Grant see-invisible sense (senses system complete) |
| **Shatter** | Evocation | Sphere AoE | 3d8 thunder, 10ft sphere | **DONE** | Pattern 3 ✓ |
| **Spider Climb** | Transmutation | Buff | Climb speed | BLOCKED | Not combat-relevant |
| **Spike Growth†** | Transmutation | Zone | 20ft sphere, 2d4/5ft | **DONE** | Pattern 8, entry damage ✓ |
| **Suggestion** | Enchantment | WIS Save | Compel action | VERY HARD | Mind control/AI |
| **Web** | Conjuration | Zone | 20ft cube, restrained | **DONE** | Pattern 8, escape action ✓ |

### Level 2 Summary
- **DONE**: 10 (Hold Person, Shatter, Scorching Ray, Blur, Misty Step, Blindness/Deafness, Spike Growth†, Web, Invisibility, Darkness)
- **EASY**: 4 (Enhance Ability, Darkvision, See Invisibility, Gust of Wind)
- **MEDIUM**: 4 (Alter Self, Enlarge/Reduce, Levitate, Mirror Image)
- **VERY HARD**: 1 (Suggestion)
- **BLOCKED**: 3 (utility spells)

†Spike Growth = Druid/Ranger (but implemented)

---

## Level 3 Spells (20 SRD + 2 cross-class)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| **Blink** | Transmutation | Buff | 50% vanish to Ethereal | HARD | Untargetable state |
| **Call Lightning†** | Conjuration | Conc + Action | Grants strike action | **DONE** | Pattern 6 ✓ |
| **Clairvoyance** | Divination | Utility | Remote sensor | BLOCKED | No combat effect |
| **Counterspell** | Abjuration | Reaction | Cancel spell | EASY | Pattern 10 on CAST_SPELL event (clone Shield) |
| **Daylight** | Evocation | Light Zone | 60ft bright light | **DONE** | Pattern 8 + 13 (light-level zone) ✓ |
| **Dispel Magic** | Abjuration | Utility | End spells on target | MEDIUM | Condition removal by level check |
| **Fear** | Illusion | Cone AoE | Frightened + forced Dash | **DONE** | Pattern 3 + conditions ✓ |
| **Fireball** | Evocation | Sphere AoE | 8d6 fire, 20ft | **DONE** | Pattern 3 ✓ |
| **Fly** | Transmutation | Buff | 60ft fly speed | EASY | MovementMode.FLYING buff (senses system supports it) |
| **Gaseous Form** | Transmutation | Transform | 10ft fly, resist, can't attack | HARD | Major stat transformation |
| **Haste** | Transmutation | Buff | Double speed, +2 AC, extra action | MEDIUM | Multi-buff + lethargy on concentration end |
| **Hypnotic Pattern** | Illusion | Cube AoE | Charmed + Incapacitated | **DONE** | Pattern 3 + conditions ✓ |
| **Lightning Bolt** | Evocation | Line AoE | 8d6 lightning, 100ft | **DONE** | Pattern 3 ✓ |
| **Major Image** | Illusion | Utility | Detailed illusion | BLOCKED | No combat effect |
| **Protection from Energy** | Abjuration | Buff | Resistance to one type | **DONE** | Single type resistance ✓ |
| **Sleet Storm** | Conjuration | Zone | 40ft, obscured, prone, conc. break | MEDIUM | Pattern 8 + multiple effects |
| **Slow** | Transmutation | Cube AoE | Half speed, -2 AC, limited actions | MEDIUM | Pattern 3 + complex debuff |
| **Spirit Guardians†** | Conjuration | Zone | 15ft sphere follows caster, 3d8 dmg | **DONE** | Pattern 8, zone follows caster ✓ |
| **Stinking Cloud** | Conjuration | Zone | Waste action on CON fail | MEDIUM | Pattern 8 |
| **Tongues** | Divination | Utility | Understand/speak all | BLOCKED | No combat effect |
| **Water Breathing** | Transmutation | Utility | Breathe underwater | BLOCKED | No combat effect |
| **Water Walk** | Transmutation | Utility | Walk on liquids | BLOCKED | No combat effect |

### Level 3 Summary
- **DONE**: 8 (Fireball, Lightning Bolt, Fear, Hypnotic Pattern, Protection from Energy, Call Lightning†, Spirit Guardians†, Daylight)
- **EASY**: 2 (Counterspell, Fly)
- **MEDIUM**: 5 (Dispel Magic, Haste, Sleet Storm, Slow, Stinking Cloud)
- **HARD**: 2 (Blink, Gaseous Form)
- **BLOCKED**: 5 (utility spells)

†Call Lightning = Druid, Spirit Guardians = Cleric (but implemented)

---

## Level 4 Spells (10 spells)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| **Banishment** | Abjuration | CHA Save | Remove from plane | MEDIUM | Remove from gridmap, restore on concentration end |
| **Blight** | Necromancy | CON Save | 8d8 necrotic | **DONE** | Pattern 2 ✓ |
| **Confusion** | Enchantment | WIS Save AoE | Random behavior | VERY HARD | AI behavior control |
| **Dimension Door** | Conjuration | Teleport | 500ft teleport + ally | MEDIUM | Hybrid targeting (position + optional ally), collision handling |
| **Dominate Beast** | Enchantment | WIS Save | Control beast | VERY HARD | Mind control/AI |
| **Greater Invisibility** | Illusion | Buff | Invisible, Stealth check | **DONE** | Pattern 15 (stealth-check buff) ✓ |
| **Ice Storm** | Evocation | Cylinder AoE | 2d8+4d6, difficult terrain | EASY | Pattern 3 (cylinder = tall sphere) + temp difficult terrain |
| **Polymorph** | Transmutation | Transform | Transform into beast | VERY HARD | Complete stat replacement |
| **Stoneskin** | Abjuration | Buff | B/P/S resistance | **DONE** | Resistance buff ✓ |
| **Wall of Fire** | Evocation | Zone | 60ft wall, 5d8 fire | MEDIUM | Pattern 8 + directional damage |

### Level 4 Summary
- **DONE**: 3 (Blight, Stoneskin, Greater Invisibility)
- **EASY**: 1 (Ice Storm)
- **MEDIUM**: 3 (Banishment, Dimension Door, Wall of Fire)
- **VERY HARD**: 3 (Confusion, Dominate Beast, Polymorph)

---

## Level 5 Spells (11 spells)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| **Animate Objects** | Transmutation | Summon | Animate up to 10 objects | VERY HARD | Summoning system |
| **Cloudkill** | Conjuration | Zone | 20ft moving sphere, 5d8 poison | **DONE** | Pattern 8 + auto-move ✓ |
| **Cone of Cold** | Evocation | Cone AoE | 8d8 cold, 60ft cone | **DONE** | 60ft cone ✓ |
| **Creation** | Illusion | Utility | Create objects | BLOCKED | No combat effect |
| **Dominate Person** | Enchantment | WIS Save | Control humanoid | VERY HARD | Mind control/AI |
| **Hold Monster** | Enchantment | WIS Save | Paralyzed, any creature | **DONE** | Undead immunity ✓ |
| **Insect Plague** | Conjuration | Zone | 20ft sphere, 4d10 piercing | EASY | Clone Cloudkill pattern (Pattern 8) |
| **Seeming** | Illusion | Utility | Disguise multiple | BLOCKED | No combat effect |
| **Telekinesis** | Transmutation | Control | Move/restrain | MEDIUM | Contested check + move/restrain |
| **Teleportation Circle** | Conjuration | Utility | Portal to circle | BLOCKED | No combat effect |
| **Wall of Stone** | Evocation | Zone | Create stone wall | MEDIUM | Pattern 8 + destructible wall panels |

### Level 5 Summary
- **DONE**: 3 (Cone of Cold, Hold Monster, Cloudkill)
- **EASY**: 1 (Insect Plague)
- **MEDIUM**: 2 (Telekinesis, Wall of Stone)
- **VERY HARD**: 2 (Animate Objects, Dominate Person)
- **BLOCKED**: 3 (utility spells)

---

## Level 6 Spells (9 spells)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| **Chain Lightning** | Evocation | Multi-target | 10d8, jumps to 3 targets | MEDIUM | Pattern 4 + chaining logic |
| **Circle of Death** | Necromancy | Sphere AoE | 8d6 necrotic, 60ft sphere | **DONE** | 60ft sphere ✓ |
| **Disintegrate** | Transmutation | DEX Save | 10d6+40 force | EASY | Pattern 2 + dust on kill |
| **Eyebite** | Necromancy | WIS Save | Asleep/Panicked/Sickened | MEDIUM | Pattern 6 (granted action), 3 condition choices |
| **Globe of Invulnerability** | Abjuration | Zone | Block spells ≤5th in zone | MEDIUM | Zone handler on CAST_SPELL, cancel spells ≤ L5 |
| **Mass Suggestion** | Enchantment | WIS Save | Suggest to 12 | VERY HARD | Mass mind control |
| **Move Earth** | Transmutation | Terrain | Reshape terrain | BLOCKED | No immediate effect |
| **Sunbeam** | Evocation | Line AoE | 6d8 radiant + blind | EASY | Pattern 3 + 6 (line AoE + granted action each turn) |
| **True Seeing** | Divination | Buff | Truesight 120ft | EASY | Grant Truesight sense mode (senses system complete) |

### Level 6 Summary
- **DONE**: 1 (Circle of Death)
- **EASY**: 3 (Disintegrate, Sunbeam, True Seeing)
- **MEDIUM**: 3 (Chain Lightning, Eyebite, Globe of Invulnerability)
- **VERY HARD**: 1 (Mass Suggestion)
- **BLOCKED**: 1 (Move Earth)

---

## Level 7 Spells (8 spells)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| **Delayed Blast Fireball** | Evocation | Sphere AoE | 12d6+ accumulates | MEDIUM | Condition with accumulating damage counter |
| **Etherealness** | Transmutation | Transform | Enter Ethereal | VERY HARD | Plane mechanics |
| **Finger of Death** | Necromancy | CON Save | 7d8+30, creates zombie | HARD | Pattern 2 + summon zombie on kill |
| **Fire Storm** | Evocation | Multi-cube | 7d10 fire, 10 cubes | MEDIUM | Multi-position AoE targeting |
| **Plane Shift** | Conjuration | Teleport | Teleport/banish | VERY HARD | Plane mechanics |
| **Prismatic Spray** | Evocation | Cone AoE | Random effects | MEDIUM | Pattern 3 + random effect table per target |
| **Reverse Gravity** | Transmutation | Cylinder | Fall upward | HARD | Vertical position |
| **Teleport** | Conjuration | Teleport | Long-range + accuracy | HARD | Accuracy table, familiarity system |

### Level 7 Summary
- **MEDIUM**: 3 (Delayed Blast Fireball, Fire Storm, Prismatic Spray)
- **HARD**: 3 (Finger of Death, Reverse Gravity, Teleport)
- **VERY HARD**: 2 (Etherealness, Plane Shift)

---

## Level 8 Spells (5 spells)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| **Dominate Monster** | Enchantment | WIS Save | Control any creature | VERY HARD | Mind control/AI |
| **Earthquake** | Evocation | Zone | 100ft, prone, fissures | HARD | Massive AoE + terrain destruction |
| **Incendiary Cloud** | Conjuration | Zone | 20ft moving, 10d8 fire | EASY | Clone Cloudkill (Pattern 8, fire damage, auto-move) |
| **Power Word Stun** | Enchantment | HP-based | Stunned if ≤150 HP | **DONE** | Pattern 9 + repeat save ✓ |
| **Sunburst** | Evocation | Sphere AoE | 12d6 radiant + blind | **DONE** | 60ft sphere, undead disadv ✓ |

### Level 8 Summary
- **DONE**: 2 (Sunburst, Power Word Stun)
- **EASY**: 1 (Incendiary Cloud)
- **HARD**: 1 (Earthquake)
- **VERY HARD**: 1 (Dominate Monster)

---

## Level 9 Spells (5 spells)

| Spell | School | Type | Effect Summary | Difficulty | Pattern/Notes |
|-------|--------|------|----------------|------------|---------------|
| **Gate** | Conjuration | Portal | Interplanar portal + summon | VERY HARD | Plane mechanics |
| **Meteor Swarm** | Evocation | Multi-sphere | 40d6, 4×40ft spheres | MEDIUM | 4 × 40ft sphere multi-AoE |
| **Power Word Kill** | Enchantment | HP-based | Death if ≤100 HP | **DONE** | HP check + instant death ✓ |
| **Time Stop** | Transmutation | Control | Extra turns | VERY HARD | Turn manipulation |
| **Wish** | Conjuration | Ultimate | Anything | VERY HARD | GM adjudication |

### Level 9 Summary
- **DONE**: 1 (Power Word Kill)
- **MEDIUM**: 1 (Meteor Swarm)
- **VERY HARD**: 3 (Gate, Time Stop, Wish)

---

## Overall Summary by Difficulty

| Difficulty | Count | Percentage |
|------------|-------|------------|
| **DONE** | 48 | 38% |
| **EASY** | 14 | 11% |
| **MEDIUM** | 22 | 17% |
| **HARD** | 6 | 5% |
| **VERY HARD** | 13 | 10% |
| **BLOCKED** | 24 | 19% |

*Counts include 7 cross-class spells tracked because they are implemented.*

**Implementable with existing patterns**: 84 spells (DONE + EASY + MEDIUM)
**Require new subsystems**: 19 spells (HARD + VERY HARD)
**Out of scope for combat engine**: 24 spells (BLOCKED)

### Progress: 48 of 103 combat-relevant spells implemented (47%)
### With existing patterns: 84 of 103 combat-relevant spells implementable (82%)

---

## Implementation Priority

### Tier 0: Already Done (48 spells)

**Cantrips (8):** Fire Bolt, Sacred Flame*, Poison Spray, Ray of Frost, Acid Splash, Chill Touch, Shocking Grasp, Eldritch Blast†

**Level 1 (12):** Magic Missile, Mage Armor, Burning Hands, Thunderwave, False Life, Charm Person, Sleep, Color Spray, Guiding Bolt*, Grease†, Fog Cloud, Shield

**Level 2 (10):** Hold Person, Shatter, Scorching Ray, Blur, Misty Step, Blindness/Deafness, Spike Growth*, Web, Invisibility, Darkness

**Level 3 (8):** Fireball, Lightning Bolt, Call Lightning*, Fear, Hypnotic Pattern, Protection from Energy, Spirit Guardians*, Daylight

**Level 4 (3):** Blight, Stoneskin, Greater Invisibility

**Level 5 (3):** Hold Monster, Cone of Cold, Cloudkill

**Level 6 (1):** Circle of Death

**Level 8 (2):** Sunburst, Power Word Stun

**Level 9 (1):** Power Word Kill

*Cross-class: Sacred Flame = Cleric, Guiding Bolt = Cleric, Call Lightning = Druid, Spike Growth = Druid/Ranger, Spirit Guardians = Cleric, Grease = Wizard, Eldritch Blast = Warlock*

### Batch 1: Handler-Heavy Spells (needs design, implement first)

These spells need fancy handlers and design decisions — prioritized because they push the engine architecture forward.

| # | Spell | Lvl | Key Challenge | Approach |
|---|-------|-----|---------------|----------|
| 1 | **Slow** | 3 | Action limitation | Cube AoE, WIS save. Condition: -2 AC, half speed (max constraint), no reactions (max = 0), one weapon attack only (extra_attacks max to 0), action OR bonus action not both (handler consumes the other on use). WIS repeat save each turn. |
| 2 | **Haste** | 3 | Extra action suppression | Buff: +2 AC, double speed, DEX save advantage. Extra action via +1 to action_economy.actions. Handler on ATTACK at EXECUTION suppresses extra attacks from haste action, self-removes after first action taken. Lethargy on concentration end: apply 1-turn Incapacitated. |
| 3 | **Mirror Image** | 2 | d20 redirect | Self-buff, NOT concentration. Condition tracks `duplicates: int = 3`. Handler on ATTACK at EXECUTION targeting self: roll d20 (threshold 6/8/11 for 3/2/1 duplicates). If redirect → check attack vs duplicate AC (10 + DEX mod). Hit destroys duplicate (decrement). Miss = attack wasted. Remove condition when duplicates = 0. |
| 4 | **Jump** (spell) | 1 | Jump action modifier | Add `jump_bonus_sum` and `jump_bonus_multiply` to Jump action formula. Spell sets multiply = 3. Jump action's `get_range()` reads multiplier. |
| 5 | **Counterspell** | 3 | Reaction on CAST_SPELL | Reaction handler on CAST_SPELL at EXECUTION. Read `event.cast_at_level`. If spell level ≤ Counterspell slot level → cancel. If higher → ability check DC = 10 + spell_level. Costs reaction + spell slot. Clone Shield pattern. |
| 6 | **Sunbeam** | 6 | Granted repeatable action | Line AoE: 60ft line, 6d8 radiant, CON save half + blind on fail. Grants `SunbeamStrikeAction` each turn (like Call Lightning). Pattern 3 + Pattern 6. Concentration. |
| 7 | **Globe of Invulnerability** | 6 | Spell filtering zone | 10ft sphere zone centered on caster, follows caster (Spirit Guardians pattern). Handler on CAST_SPELL at EXECUTION: if target in zone AND spell_level ≤ 5 → cancel. Also intercept AoE spells that include zone positions. Concentration. |
| 8 | **Enlarge/Reduce** | 2 | Size field + BG3 effects | Add `Entity.size: CreatureSize` field (enum: TINY→GARGANTUAN). BG3 approach: change size category + ±1d4 damage modifier + advantage/disadvantage on STR checks. No multi-tile grid changes. |

### Batch 2: Simple Buff/Clone Spells (after Batch 1)

These are mechanical — use established patterns, no design decisions needed:

| # | Spell | Lvl | Pattern | Notes |
|---|-------|-----|---------|-------|
| 9 | Expeditious Retreat | 1 | Pattern 6 | Bonus action Dash each turn |
| 10 | Enhance Ability | 2 | Buff | Advantage on ability checks |
| 11 | Darkvision | 2 | Buff | Grant Darkvision sense mode |
| 12 | See Invisibility | 2 | Buff | See invisible creatures |
| 13 | Fly | 3 | Buff | 60ft fly speed |
| 14 | True Seeing | 6 | Buff | Grant Truesight 120ft |
| 15 | Disintegrate | 6 | Pattern 2 | 10d6+40, dust on kill |
| 16 | Insect Plague | 5 | Pattern 8 | Clone Cloudkill |
| 17 | Incendiary Cloud | 8 | Pattern 8 | Clone Cloudkill (fire) |
| 18 | Gust of Wind | 2 | Pattern 3+7+8 | Line push + persistent zone |
| 19 | Ice Storm | 4 | Pattern 3 | Cylinder AoE + temp difficult terrain |

### Key Design Decisions (resolved)

1. **Haste extra action**: Handler on ATTACK at EXECUTION that removes extra attacks granted from the haste-action, self-removes after first action. Not a separate action type.
2. **Jump spell**: Add `jump_bonus_sum` and `jump_bonus_multiply` to Jump action formula. Spell sets multiply = 3.
3. **Enlarge/Reduce**: BG3-style (damage/STR effects, no grid footprint change). Add `Entity.size` field for tracking.
4. **Mirror Image**: NOT AC modifier stacks. D20 roll to redirect → check vs duplicate AC → destroy on hit. Handler pattern.
5. **Size in RAW**: Large = 2×2 squares. We implement BG3-style (single tile, size enum for tracking only). Multi-tile is future work.

### Remaining Tiers

**Tier 3: Remaining Medium (after Batches 1+2)**
True Strike, Alter Self, Levitate, Dispel Magic, Sleet Storm, Stinking Cloud, Banishment, Dimension Door, Wall of Fire, Telekinesis, Wall of Stone, Chain Lightning, Eyebite, Delayed Blast Fireball, Fire Storm, Prismatic Spray, Meteor Swarm

**Tier 4: Hard (New Subsystems)**

| System | Spells | Notes |
|--------|--------|-------|
| **Teleportation** | Teleport | Accuracy table, familiarity system |
| **Complex Transforms** | Gaseous Form, Blink | Untargetable states |
| **Partial Summon** | Finger of Death | Summon zombie on kill |
| **Terrain Destruction** | Earthquake, Reverse Gravity | Major positional effects |

**Tier 5: Skip (VERY HARD + BLOCKED)**

| Category | Spells |
|----------|--------|
| **Mind Control** | Suggestion, Dominate Beast/Person/Monster, Confusion, Mass Suggestion |
| **Summoning** | Animate Objects |
| **Transformation** | Polymorph |
| **Plane Mechanics** | Etherealness, Plane Shift, Gate |
| **Meta/Ultimate** | Time Stop, Wish |
| **Utility (BLOCKED)** | 24 spells with no combat effect |

---

## Conclusion

With the AoE system, concentration mechanics, zone spells, **lighting system**, **stealth/invisibility**, and **reaction casting** all complete, the engine can now implement the vast majority of combat-relevant spells. Of the spells tracked:

- **48 spells (38%)** already implemented
- **14 more spells (11%)** use existing patterns (EASY)
- **22 spells (17%)** need moderate new work (MEDIUM)
- **6 spells (5%)** need new subsystems (HARD)
- **13 spells (10%)** need major architecture (VERY HARD)
- **24 spells (19%)** have no combat mechanics (BLOCKED)

**Recent additions (7 spells) since last major update:**
- **Shield** — Reaction +5 AC (Pattern 10: reaction spell)
- **Fog Cloud** — 20ft obscured zone (Pattern 13: light-level zone)
- **Darkness** — 15ft magical darkness zone (Pattern 13: light-level zone)
- **Daylight** — 60ft bright light zone (Pattern 13: light-level zone)
- **Invisibility** — Break-on-action invisible (Pattern 14)
- **Greater Invisibility** — BG3-style Stealth check to maintain (Pattern 15)
- **Eldritch Blast** — Warlock cantrip, multi-beam scaling

**New systems unlocked:**
- **Lighting System (Layer 2)** — Per-tile light levels, sense modes (Darkvision, Truesight), incremental senses updates. Unlocks Darkvision, See Invisibility, True Seeing spells as EASY buffs.
- **Stealth/Invisibility (Layer 1)** — Hidden, Invisible, GreaterInvisible conditions with perceivability filtering. Makes Invisibility and Greater Invisibility fully functional.
- **Reaction Casting** — Shield proves the pattern. Counterspell is a clone.

**Three new patterns documented:**
- **Pattern 13 (Light-Level Zone)** — `ZoneControlCondition.sets_light_level` + `light_is_obscurement`. No handlers needed.
- **Pattern 14 (Break-on-Action Invisibility)** — `creation_lineage_uuid` + reveal handler on ATTACK/CAST_SPELL/BASE_ACTION.
- **Pattern 15 (Stealth-Check Buff)** — Escalating DC Stealth check instead of auto-removal.

**Event Relationship Pattern (parent_event) — CRITICAL:**
- All sub-events must link to their parent via `parent_event` parameter
- `add_condition()` takes Event object: `parent_event=effect_event`
- `receive_damage()` and `create_saving_throw_request()` take UUID: `parent_event=event.uuid`
- In handler processors, the `event` parameter IS the parent
- This ensures combat log entries nest correctly and no orphan events

**BG3-style Prone auto-stand** implemented for Grease spell:
- Auto-stand at turn start (costs half movement)
- Immediate stand during own turn if movement available
- Stays prone if no movement or not their turn

### Turn Start Phase Ordering (Critical for Zone + Prone Interaction)

The `on_turn_start()` method has a specific phase sequence that zone spells like Grease must respect:

```
on_turn_start() in dnd/entity.py
─────────────────────────────────────────────────────────
1. DECLARATION - event created

2. phase_to(EXECUTION) ───► Zone handlers fire here (Grease)
   │                        is_my_turn = False (not set yet)
   │                        action_economy NOT reset yet
   │
   └─ Grease applies Prone (entity has no movement to stand)

3. [BETWEEN EXECUTION and EFFECT]:
   └─ advance_duration_condition() - expires Dodge, etc.
   └─ action_economy.reset_all_costs() - movement becomes 30ft
   └─ is_my_turn = True ◄────────────────────────────────────

4. phase_to(EFFECT) ─────► Auto-stand handler fires here
   │                       Entity now has movement, stands up
   │                       Consumes 15ft, removes Prone
   │
   └─ Result: Prone=False, Movement=15ft

5. phase_to(COMPLETION) ─► Handlers blocked (EventQueue skips)
```

**Key Design Points:**
- `is_my_turn` is set AFTER action_economy reset, not before
- This ensures "immediate stand during own turn" only fires mid-turn (after reset)
- Zone spell turn-start effects use EXECUTION phase (before reset)
- Auto-stand uses EFFECT phase (after reset, entity has movement)
- Handlers never register for COMPLETION (EventQueue.register() skips it)

**Why This Matters:**
If `is_my_turn` was set before EXECUTION, Prone's `_apply()` would see it's the entity's turn with full movement and immediately cancel itself - then the action_economy reset would wipe out the movement cost, effectively giving free standing.

**Handler Phase Assignments:**
| Handler | Phase | Reason |
|---------|-------|--------|
| Grease turn start | EXECUTION | Apply Prone BEFORE auto-stand at EFFECT |
| Cloudkill turn start | EFFECT | Damage only, no Prone interaction |
| Spirit Guardians turn start | EFFECT | Damage only, no Prone interaction |
| Prone auto-stand | EFFECT | Fire AFTER action_economy reset, consume movement |
| Survivor (heal at turn start) | EXECUTION | HP-based, doesn't need movement |
| Rage maintenance check | EXECUTION | Check markers before they expire |

**Rule of Thumb:** Zone spells that apply Prone use EXECUTION. Zone spells that only deal damage can use EFFECT.

**Next batch:** Batch 1 (handler-heavy spells: Slow, Haste, Mirror Image, Jump spell, Counterspell, Sunbeam, Globe of Invulnerability, Enlarge/Reduce) followed by Batch 2 (simple buff/clone spells).

**Total implementable:** 84 spells (82% of combat-relevant) are DONE/EASY/MEDIUM with current architecture, up from ~65 (63%).

### Progress: 48 of 103 combat-relevant spells implemented (47%)
