# Handler System Documentation

## Overview

EventHandlers and SpatialHandlers are the reactive backbone of the engine. They intercept events at specific phases and can modify, cancel, or spawn child events.

### Hierarchy

```
BaseHandler (dnd/core/events.py)
  ├── EventHandler     — trigger-matched, fires when event matches trigger conditions
  └── SpatialHandler   — position-indexed, fires at specific grid positions via O(1) lookup
```

### The `enabled` Toggle

Every handler has an `enabled: bool` field (default `True`). When `False`, the handler's `__call__` returns `None` immediately — same as a trigger mismatch.

**API**:
- `entity.set_handler_enabled("Shield", False)` — toggle by name
- `entity.set_handler_enabled_by_uuid(handler_uuid, False)` — toggle by UUID
- `entity.get_event_handler_by_name("Shield")` — find single handler
- `entity.get_event_handlers_by_name("Divine Smite")` — find all matching

**Server**:
- `GET /entity/{uuid}/handlers` — list all handlers with state
- `POST /entity/{uuid}/handlers/{name}/toggle` — toggle by name
- `handler_details` in `AvailableActionsResult` — flows through `get_available_actions()`

**CLI**:
- `handlers` — display all handlers with [ON]/[OFF] state
- `toggle "<name>" on/off` — toggle a handler

---

## Handler Catalog

### Reactions

Handlers that respond to events targeting or affecting the entity. These consume resources (reaction, spell slot) and represent player choices.

| Handler | File | Trigger | Phase | Description |
|---------|------|---------|-------|-------------|
| Opportunity Attack Handler | `reactions.py:60` | STEP_MOVEMENT | EFFECT | OA when enemy leaves threatened position |
| Shield | `spells/abjuration.py:152` | ATTACK | EXECUTION | +5 AC reaction, costs reaction + spell slot |
| Protection | `classes/fighter.py:517` | ATTACK | EXECUTION | Impose disadvantage on attacks against nearby ally |
| Intercept | `items/test_reactions.py:132` | STEP_MOVEMENT | EFFECT | Charge to intercept moving enemy |
| Dodge Roll | `items/test_reactions.py:339` | ATTACK | EFFECT | Dodge away from attacker |
| Retaliation | `classes/barbarian.py:1195` | TAKE_DAMAGE | EFFECT | Reaction melee attack when hit (Berserker L14) |

### Dice Manipulation

Handlers that modify dice rolls (d20 or damage dice) after rolling but before the outcome is applied.

| Handler | File | Trigger | Phase | Description |
|---------|------|---------|-------|-------------|
| Great Weapon Fighting | `classes/fighter.py:408` | DAMAGE_ROLL_RESULT | EFFECT | Reroll 1-2 on weapon damage dice |
| Divine Smite (L1-L5) | `classes/paladin.py:127` | DAMAGE_ROLL_RESULT | EFFECT | Add radiant damage (per spell slot level) |
| Lucky | `classes/feats.py:104` | *_D20_ROLL_RESULT | EFFECT | Reroll any d20, limited uses |
| Indomitable | `classes/fighter.py:1533` | SAVE_D20_ROLL_RESULT | EFFECT | Reroll failed save, limited uses |
| Unseen Strike | `items/weapons.py:443` | DAMAGE_ROLL_RESULT | EFFECT | +1d4 damage when attacking unseen target |

### Self-Triggers

Handlers that fire in response to the entity's own actions or state changes.

| Handler | File | Trigger | Phase | Description |
|---------|------|---------|-------|-------------|
| HasAttacked Tracker | `conditions.py:154` | ATTACK | EXECUTION | Marks entity as having attacked (for Extra Attack, Rage) |
| HasTakenDamage Tracker | `conditions.py:167` | TAKE_DAMAGE | EFFECT | Marks entity as having taken damage (for Rage) |
| Death Condition Handler | `conditions.py:966` | DEATH | EXECUTION | Applies Dead condition |
| Prone Auto-Stand | `actions_functional.py:120` | TURN_START | EFFECT | Auto-stand at turn start (BG3 style) |
| Extra Attack Resource | `classes/fighter.py:1242` | ATTACK | EXECUTION | Manage extra_attacks resource on attack |
| Survivor | `classes/fighter.py:1719` | TURN_START | EXECUTION | Heal at turn start if HP < max (Champion L18) |
| Rage Maintenance | `classes/rage.py:183` | TURN_START | EFFECT | Check attack/damage to maintain rage |
| Rage Armor Watch | `classes/rage.py:198` | ARMOR_EQUIP | EXECUTION | End rage if heavy armor equipped |
| Rage Death End | `classes/rage.py:246` | DEATH | EXECUTION | End rage on death |
| Relentless Rage | `classes/barbarian.py:906` | TAKE_DAMAGE | EFFECT | CON save to stay at 1 HP instead of dying |
| Indomitable Might | `classes/barbarian.py:1018` | SKILL_CHECK | EXECUTION | STR check minimum roll |
| Intimidating Presence End | `classes/barbarian.py:1347` | TURN_END | EFFECT | Remove Frightened if out of range/LOS |

### Spell Effect Handlers

Handlers registered by spell conditions for duration management and repeat saves.

| Handler | File | Trigger | Phase | Description |
|---------|------|---------|-------|-------------|
| Shield: Turn Start Removal | `spells/abjuration.py:68` | TURN_START | EXECUTION | Remove Shield buff at caster's turn start |
| Mage Armor Watch | `spells/abjuration.py:252` | ARMOR_EQUIP | EFFECT | Cancel Mage Armor if armor equipped |
| Hold Person Repeat Save | `spells/enchantment.py:316` | TURN_END | EFFECT | WIS save to break paralysis |
| Hold Monster Repeat Save | `spells/enchantment.py:556` | TURN_END | EFFECT | WIS save to break paralysis |
| Sleep Wake Handler | `spells/enchantment.py:938` | TAKE_DAMAGE | EFFECT | Wake on damage |
| Power Word Stun Repeat Save | `spells/enchantment.py:1199` | TURN_END | EFFECT | CON save to break stun |
| Fear Repeat Save | `spells/illusion.py:216` | TURN_END | EFFECT | WIS save to break fear |
| Hypnotic Pattern Damage Break | `spells/illusion.py:421` | TAKE_DAMAGE | EFFECT | Break incapacitated on damage |
| Guiding Bolt Remove | `spells/evocation.py:2335` | ATTACK | EFFECT | Remove advantage on next attack |
| Blindness/Deafness Repeat Save | `spells/necromancy.py:637` | TURN_END | EFFECT | CON save to end condition |
| Sunburst Blindness Repeat Save | `spells/evocation.py:1912` | TURN_END | EFFECT | CON save to end blindness |
| Call Lightning Cleanup | `spells/conjuration.py:312` | CONDITION_REMOVAL | EXECUTION | Unregister spell action |

### Zone/Spatial Handlers

SpatialHandlers indexed by grid position for zone spell effects.

| Handler | File | Event Type | Phase | Description |
|---------|------|------------|-------|-------------|
| Spike Growth Entry | `spells/transmutation.py:71` | SPATIAL_ENTITY_ENTERED | EFFECT | 1d4 piercing per cell moved through |
| Grease Entry | `spells/conjuration.py:728` | SPATIAL_ENTITY_ENTERED | EFFECT | DEX save vs prone |
| Grease Turn Start | `spells/conjuration.py:781` | TURN_START | EXECUTION | DEX save vs prone each turn |
| Web Entry | `spells/conjuration.py:1123` | SPATIAL_ENTITY_ENTERED | EFFECT | DEX save vs restrained |
| Cloudkill Entry | `spells/conjuration.py:1352` | SPATIAL_ENTITY_ENTERED | EFFECT | Poison damage on entry |
| Cloudkill Turn Start | `spells/conjuration.py:1401` | TURN_START | EFFECT | Poison damage each turn |
| Cloudkill Auto-Move | `spells/conjuration.py:1451` | TURN_START | EFFECT | Move zone on caster's turn |
| Spirit Guardians Entry | `spells/conjuration.py:1807` | SPATIAL_ENTITY_ENTERED | EFFECT | Save vs radiant damage |
| Spirit Guardians Turn Start | `spells/conjuration.py:1877` | TURN_START | EFFECT | Save vs radiant damage each turn |
| Spirit Guardians Exit | `spells/conjuration.py:1905` | SPATIAL_ENTITY_LEFT | EFFECT | Remove slow on exit |
| Spirit Guardians Follow | `spells/conjuration.py:1931` | SPATIAL_ENTITY_ENTERED | EFFECT | Move zone with caster |
| Spike Zone | `tiles.py:80` | SPATIAL_ENTITY_ENTERED | EFFECT | Tile-based spike damage |
| Spikes Entry | `tiles.py:154` | SPATIAL_ENTITY_ENTERED | EFFECT | Spike trap on single tile |

### Hidden/Invisibility Reveal Handlers

Registered by Hidden, InvisibilityEffect, and GreaterInvisibilityEffect conditions.

| Handler | File | Trigger | Phase | Description |
|---------|------|---------|-------|-------------|
| Hidden Reveal | `conditions.py` | ATTACK/CAST_SPELL/BASE_ACTION | EFFECT | Remove Hidden on attack/spell/action |
| Invisibility Reveal | `conditions.py` | ATTACK/CAST_SPELL/BASE_ACTION | EFFECT | Remove Invisible on attack/spell/action |
| Greater Invisibility Check | `conditions.py` | ATTACK/CAST_SPELL/BASE_ACTION | EFFECT | Stealth check vs escalating DC |
| Concentration Check | `conditions.py` | TAKE_DAMAGE | EFFECT | CON save DC max(10, dmg/2) to maintain concentration |

---

## Registration Patterns

### Single Registration Rule

**Only call ONE method** per handler:
- `entity.add_event_handler(handler)` — preferred, auto-registers with EventQueue AND tracks on entity
- `EventQueue.add_event_handler(handler)` — direct, doesn't track on entity

Calling both registers the handler twice, causing it to fire twice.

### Reaction Cost Patterns

Two patterns exist for consuming reaction resources:

**1. Action-based (OA, Intercept)**: Cost declared in action's `pre_validate()`, consumed at COMPLETION.
```python
# OA creates an Attack action with reaction cost — standard action flow
```

**2. Handler-based (Shield, Protection, Divine Smite)**: Cost checked and consumed directly in the processor.
```python
# Shield processor checks can_afford("reactions", 1), then entity.action_economy.consume()
```

### Per-Level Handler Pattern (Divine Smite)

Register multiple handlers, one per spell slot level, highest first:
```python
for level in range(max_level, 0, -1):
    handler = create_divine_smite_handler(entity.uuid, level)
    entity.add_event_handler(handler)
```

Highest fires first. Sets a flag in `event.context` to prevent lower handlers from double-dipping. Disabling the highest causes the next-highest to fire.

---

## Condition Return Tuple

Conditions return handler UUIDs from `_apply()` for automatic cleanup:

```python
def _apply(self, declaration_event: Event) -> Tuple[
    List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
    List[UUID],               # event_handler_uuids — cleaned up on condition removal
    List[UUID],               # subcondition_uuids
    List[UUID],               # spatial_handler_uuids — cleaned up on condition removal
    Optional[Event]           # completion event
]:
```
