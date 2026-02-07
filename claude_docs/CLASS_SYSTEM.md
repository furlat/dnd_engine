# Class System

**Last Updated:** February 2026

## 1. Architecture Overview

**Classes are implemented as collections of conditions** applied to entities. A class is essentially `Map<Class, Level> → List<Condition>`. Leveling up adds new conditions. There is no `Class` object - the entity IS the character, and features are conditions.

```
Entity
├── ability_scores          ← Class determines primary stats
├── health                  ← Class determines hit dice (d10 Fighter, d12 Barbarian, d6 Sorcerer)
├── equipment               ← Class determines proficiencies, crit threshold, damage bonuses
├── action_economy          ← Class adds resources (rage, second_wind, spell slots)
├── spellcasting            ← Class sets ability, spell bonuses
├── proficiency_bonus       ← Set by level
├── active_conditions       ← Class features live HERE as conditions
│   ├── "Second Wind Feature"    → resource + action
│   ├── "Fighting Style: Archery" → modifier
│   ├── "Extra Attack Feature"   → resource + handler + action
│   ├── "Raging"                 → modifiers + handlers
│   └── ...
└── registered_actions      ← Class adds actions via conditions
    ├── "Second Wind"
    ├── "Action Surge"
    ├── "Rage"
    └── ...
```

**Key insight**: Every class feature follows the same `BaseCondition` pattern - there's no special-casing for different classes. A fighting style, a rage, and a spell slot are all conditions.

---

## 2. Feature Condition Pattern

Every class feature is a `BaseCondition` subclass. The core pattern:

### 5-Tuple Return Signature

All `_apply()` methods return a 5-tuple:

```python
def _apply(self, declaration_event: Event) -> Tuple[
    List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
    List[UUID],               # event_handler_uuids
    List[UUID],               # subcondition_uuids
    List[UUID],               # spatial_handler_uuids
    Optional[Event]           # completion event
]:
```

### Early-Return Guard

Every `_apply()` starts with a target entity check. If the target is missing, return the 5-tuple with a cancelled event:

```python
def _apply(self, declaration_event: Event) -> Tuple[...]:
    if not self.target_entity_uuid:
        return [], [], [], [], declaration_event.cancel(
            status_message="Target entity UUID is not set"
        )

    target = Entity.get(self.target_entity_uuid)
    if not target:
        return [], [], [], [], declaration_event.cancel(
            status_message=f"Target entity {self.target_entity_uuid} not found"
        )

    # ... actual implementation ...
```

### Complete Example: SecondWindFeature

The simplest feature condition - adds a resource and registers an action:

```python
class SecondWindFeature(BaseCondition):
    name: str = "Second Wind Feature"
    description: str = "Heal 1d10 + fighter level as a bonus action (1/short rest)"
    fighter_level: int = 1

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        # Add resource (recharges on short rest)
        target.action_economy.add_resource(
            name="second_wind",
            maximum=1,
            recharge_type=RechargeType.SHORT_REST
        )

        # Register action template
        second_wind = SecondWind(
            source_entity_uuid=target.uuid,
            fighter_level=self.fighter_level,
            template=True
        )
        target.register_action(second_wind)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Granted Second Wind to {target.name}"
        )

        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up resource and action on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.action_economy.remove_resource("second_wind")
            target.unregister_action("Second Wind")
        return super()._remove(event)
```

### `_remove()` Cleanup Pattern

Every feature condition that adds resources or registers actions **must** override `_remove()` to clean up:

```python
def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
    target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
    if target:
        target.action_economy.remove_resource("resource_name")
        target.unregister_action("Action Name")
    return super()._remove(event)  # Always call super last
```

**Which conditions need `_remove()`:**

| Has `_remove()` | Doesn't need `_remove()` |
|---|---|
| SecondWindFeature (resource + action) | FightingStyleArchery (pure modifier) |
| ActionSurgeFeature (resource + action) | FightingStyleDefense (pure modifier) |
| ExtraAttackFeature (resource + handler + actions) | ImprovedCritical (pure modifier) |
| Indomitable (resource) | SuperiorCritical (pure modifier) |
| RageFeature (resource + 2 actions) | BrutalCritical (handler only - auto-cleaned) |
| Frenzied (action) | PersistentRage (marker) |
| FrenzyFeature (action) | FeralInstinct (modifier) |
| RecklessAttackFeature (action) | DangerSense (modifier) |
| MindlessRage (contextual immunities) | FastMovement (modifier) |
| RelentlessRage (resource) | Retaliation (handler only - auto-cleaned) |
| IntimidatingPresenceFeature (actions) | IndomitableMight (handler only) |
| LuckyFeature (resource) | PrimalChampion (modifier) |

**Rule of thumb**: If `_apply()` calls `add_resource()` or `register_action()`, you need `_remove()`. Pure modifiers and event handlers returned in the 5-tuple are auto-cleaned by the base class.

---

## 3. Event Handler Patterns

Feature conditions that need to react to game events register `EventHandler` instances.

### Dice Manipulation: Great Weapon Fighting

Listens for `DAMAGE_ROLL_RESULT` events to reroll 1s and 2s:

```python
class GreatWeaponFighting(BaseCondition):
    name: str = "Great Weapon Fighting"

    def _apply(self, declaration_event: Event) -> Tuple[...]:
        # ... early-return guard ...

        handler = EventHandler(
            name="Great Weapon Fighting",
            source_entity_uuid=self.target_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.DAMAGE_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=self.target_entity_uuid
                )
            ],
            event_processor=gwf_processor
        )
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(EventPhase.EFFECT, ...)
        return [], [handler.uuid], [], [], effect_event
```

**Key**: Handler UUID goes in the second tuple position. The base class auto-removes it on condition cleanup.

### Save Reroll: Indomitable

Listens for `SAVE_D20_ROLL_RESULT` to reroll failed saves:

```python
class Indomitable(BaseCondition):
    def _apply(self, declaration_event: Event) -> Tuple[...]:
        # ... early-return guard ...

        # Add resource
        target.action_economy.add_resource("indomitable", maximum=self.uses,
                                           recharge_type=RechargeType.LONG_REST)

        handler = EventHandler(
            name="Indomitable",
            source_entity_uuid=self.target_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.SAVE_D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=self.target_entity_uuid
                )
            ],
            event_processor=indomitable_processor
        )
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(EventPhase.EFFECT, ...)
        return [], [handler.uuid], [], [], effect_event
```

### Turn Start Trigger: Survivor

Listens for `TURN_START` to heal when HP is low:

```python
class Survivor(BaseCondition):
    def _apply(self, declaration_event: Event) -> Tuple[...]:
        # ... early-return guard ...

        handler = EventHandler(
            name="Survivor",
            source_entity_uuid=self.target_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_START,
                    event_phase=EventPhase.EXECUTION,
                    event_source_entity_uuid=self.target_entity_uuid
                )
            ],
            event_processor=survivor_processor
        )
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(EventPhase.EFFECT, ...)
        return [], [handler.uuid], [], [], effect_event
```

---

## 4. Modifier Condition Patterns

### Static Modifier: Archery

Adds a flat numerical bonus:

```python
class FightingStyleArchery(BaseCondition):
    def _apply(self, declaration_event: Event) -> Tuple[...]:
        # ... early-return guard ...

        outs = []
        modifier = NumericalModifier(
            name="Archery", value=2,
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        mod_uuid = target.equipment.attack_bonus.self_static.add_value_modifier(modifier)
        outs.append((target.equipment.attack_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(EventPhase.EFFECT, ...)
        return outs, [], [], [], effect_event
```

### Critical Threshold: Improved Critical

Modifies crit range via `NumericalModifier` on `crit_threshold`:

```python
class ImprovedCritical(BaseCondition):
    crit_range_reduction: int = 1  # 19-20

    def _apply(self, declaration_event: Event) -> Tuple[...]:
        # ... early-return guard ...

        outs = []
        modifier = NumericalModifier(
            name="Improved Critical", value=self.crit_range_reduction,
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        mod_uuid = target.equipment.crit_threshold.self_static.add_value_modifier(modifier)
        outs.append((target.equipment.crit_threshold.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(EventPhase.EFFECT, ...)
        return outs, [], [], [], effect_event
```

### Contextual Modifier: Defense (AC when armored)

Uses a callable that checks armor state at runtime:

```python
def defense_ac_check(source_entity_uuid, target_entity_uuid=None, context=None):
    """Only add +1 AC if wearing armor."""
    entity = Entity.get(source_entity_uuid)
    if not entity or not entity.equipment.body_armor:
        return None
    return NumericalModifier.create(
        name="Defense", value=1,
        source_entity_uuid=source_entity_uuid
    )

class FightingStyleDefense(BaseCondition):
    def _apply(self, declaration_event: Event) -> Tuple[...]:
        # ... early-return guard ...

        outs = []
        modifier = ContextualNumericalModifier(
            name="Defense",
            source_entity_uuid=self.target_entity_uuid,
            callable=defense_ac_check
        )
        mod_uuid = target.equipment.ac_bonus.self_contextual.add_value_modifier(modifier)
        outs.append((target.equipment.ac_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(EventPhase.EFFECT, ...)
        return outs, [], [], [], effect_event
```

---

## 5. Modern Implementation Patterns

### Marker Conditions

Some conditions exist solely for their **presence** - they carry no modifiers or handlers. Other code checks for them via `"ConditionName" in entity.active_conditions`.

| Marker | Purpose | Checked By |
|--------|---------|------------|
| `ActionSurging` | Prevents 2x Action Surge per turn | ActionSurge action's `_validate()` |
| `ExtraAttacksGranted` | Tracks extra attacks granted this turn | `extra_attack_resource_processor` |
| `PersistentRage` | Skips rage maintenance check | Rage maintenance handler |
| `IntimidatingPresenceImmunity` | 24h immunity after successful save | IntimidatingPresence action |
| `HasAttacked` | Tracks any attack this round | Rage maintenance handler |
| `HasTakenDamage` | Tracks damage taken this round | Rage maintenance handler |

**HasAttacked/HasTakenDamage** are special - they're generic markers applied by `setup_standard_actions()` globally, with 1-round duration. The rage maintenance handler checks for their presence at `TURN_START EXECUTION` (before they expire).

### Compound Conditions: Frenzy Chain

The Frenzy system demonstrates parent-child condition linkage for cascade removal:

```python
# In Frenzy._apply() (the action, not the condition):
def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
    entity = Entity.get(self.source_entity_uuid)

    # 1. Apply Raging condition first (will be the parent)
    raging = Raging(
        source_entity_uuid=self.source_entity_uuid,
        target_entity_uuid=self.source_entity_uuid,
        rage_damage=self.rage_damage
    )
    entity.add_condition(raging)

    # 2. Apply Frenzied as sub-condition of Raging
    frenzied = Frenzied(
        source_entity_uuid=self.source_entity_uuid,
        target_entity_uuid=self.source_entity_uuid,
        rage_damage=self.rage_damage,
        parent_condition=raging.uuid  # Links child to parent
    )
    entity.add_condition(frenzied)

    # 3. Add to parent's sub_conditions for cascade removal
    raging.sub_conditions.append(frenzied.uuid)
```

**Why this order?** Rage maintenance removes `Raging` when the barbarian doesn't attack. Since `Frenzied` is a sub-condition of `Raging`, `Entity._remove_condition_tree()` automatically cascades to remove `Frenzied` too. If the relationship were inverted, rage decay wouldn't clean up the frenzy.

### `partial()` for Handler Binding

When an `EventProcessor` needs extra state beyond the standard `(event, source_entity_uuid)` signature, use `functools.partial()`:

```python
from functools import partial

def intimidating_presence_end_check_processor(
    event: Event,
    source_entity_uuid: UUID,
    barbarian_uuid: UUID  # Extra parameter!
) -> Optional[Event]:
    # ... check if frightened creature is out of range of barbarian ...

# EventHandler expects Callable[[Event, UUID], Optional[Event]]
# Use partial to bind the extra barbarian_uuid parameter:
bound_processor = partial(
    intimidating_presence_end_check_processor,
    barbarian_uuid=barbarian_uuid
)

handler = EventHandler(
    name="Intimidating Presence End Check",
    source_entity_uuid=source_entity_uuid,
    trigger_conditions=[Trigger(...)],
    event_processor=bound_processor  # Matches expected signature
)
```

### `pre_validate()` for Action Visibility

Actions can override `pre_validate()` to control whether they appear in `get_available_actions()`. This is called **before** the action is shown to the player - it doesn't replace `_validate()`.

```python
class Rage(BaseAction):
    def pre_validate(self) -> bool:
        """Hide Rage action when conditions aren't met."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return False
        # Cannot rage in heavy armor
        if entity.equipment.body_armor and entity.equipment.body_armor.type == ArmorType.HEAVY:
            return False
        # Cannot already be raging
        if "Raging" in entity.active_conditions:
            return False
        # Check resource availability
        if not entity.action_economy.can_afford_resource("rage", 1):
            return False
        return True
```

**Use cases**: Rage (hidden when already raging or in heavy armor), Frenzy (hidden when Raging/Frenzied), FrenziedStrike (hidden when not frenzied).

---

## 6. Fighter Implementation (Complete L1-L20)

### Level Progression

| Level | Feature | Type | Implementation |
|-------|---------|------|----------------|
| 1 | Fighting Style | Modifier condition | 6 styles, each a separate condition |
| 1 | Second Wind | Feature condition | Resource + bonus action heal |
| 2 | Action Surge | Feature condition | Resource + extra action (1/turn) |
| 3 | Champion: Improved Critical | Modifier condition | Crit on 19-20 |
| 5 | Extra Attack (1) | Feature condition | Resource + handler + attack templates |
| 9 | Indomitable (1) | Feature condition | Resource + save reroll handler |
| 11 | Extra Attack (2) | Feature condition | 2 extra attacks |
| 13 | Indomitable (2) | Feature condition | 2 uses |
| 15 | Champion: Superior Critical | Modifier condition | Crit on 18-20 |
| 17 | Action Surge (2) | Feature condition | 2 uses |
| 17 | Indomitable (3) | Feature condition | 3 uses |
| 18 | Champion: Survivor | Handler condition | Heal at turn start when HP ≤ 50% |
| 20 | Extra Attack (3) | Feature condition | 3 extra attacks |

### Fighting Styles

| Style | Type | Channel | Effect |
|-------|------|---------|--------|
| Archery | Static | `equipment.attack_bonus.self_static` | +2 ranged attacks |
| Defense | Contextual | `equipment.ac_bonus.self_contextual` | +1 AC (armored only) |
| Dueling | Contextual | `equipment.damage_bonus.self_contextual` | +2 damage (one-handed) |
| Great Weapon Fighting | Handler | `DAMAGE_ROLL_RESULT` | Reroll 1s/2s on damage dice |
| Protection | Handler | `ATTACK EXECUTION` | Impose disadvantage on attacks vs adjacent allies |
| Two Weapon Fighting | Contextual | `equipment.damage_bonus.self_contextual` | Add ability mod to off-hand |

### Factory

```python
from dnd.classes.fighter_factory import create_fighter, FighterConfig

config = FighterConfig(
    level=5,
    name="Champion",
    position=(3, 3),
    faction="heroes",
    fighting_style="defense",       # archery/defense/dueling/great_weapon/protection/two_weapon
)
fighter = create_fighter(config)
```

**Signature**: `create_fighter(config: FighterConfig, source_id: Optional[UUID] = None) -> Entity`

---

## 7. Barbarian Implementation (Complete L1-L20)

### Level Progression

| Level | Feature | Type | Implementation |
|-------|---------|------|----------------|
| 1 | Rage | Feature condition | Resource + Rage/End Rage actions |
| 1 | Unarmored Defense | Contextual modifier | AC = 10 + DEX + CON (no armor) |
| 2 | Reckless Attack | Feature condition | Action grants advantage + exposed |
| 2 | Danger Sense | Contextual modifier | ADV on DEX saves vs visible |
| 3 | Berserker: Frenzy | Feature condition | Action enters frenzied rage |
| 5 | Extra Attack | Feature condition | Reuses Fighter's ExtraAttackFeature |
| 5 | Fast Movement | Contextual modifier | +10 speed (no heavy armor) |
| 6 | Berserker: Mindless Rage | Modifier condition | Immune charm/frighten while raging |
| 7 | Feral Instinct | Modifier condition | ADV on initiative |
| 9/13/17 | Brutal Critical | Handler condition | +1/2/3 extra melee crit dice |
| 10 | Berserker: Intimidating Presence | Feature condition | Action to frighten enemies |
| 11 | Relentless Rage | Feature condition | Resource + CON save to survive at 0 HP |
| 14 | Berserker: Retaliation | Handler condition | Reaction attack when hit in melee |
| 15 | Persistent Rage | Marker condition | Rage doesn't end from inactivity |
| 18 | Indomitable Might | Handler condition | STR checks can't be below STR score |
| 20 | Primal Champion | Modifier condition | +4 STR and CON |

### Rage System

```
RageFeature (permanent condition)
├── Adds "rage" resource (2-6+ uses, long rest recharge)
├── Registers Rage action (bonus action)
└── Registers End Rage action (bonus action)

Rage action → applies Raging condition
                 ├── STR advantage (modifier)
                 ├── Rage damage bonus (modifier)
                 ├── B/P/S resistance (modifier)
                 ├── Maintenance handler (TURN_START EXECUTION)
                 │   └── Checks HasAttacked/HasTakenDamage markers
                 │       If neither → remove Raging (unless PersistentRage)
                 └── HasAttacked/HasTakenDamage registration handler

Frenzy action → applies Raging + Frenzied (compound)
                 ├── Raging (parent) - all rage benefits
                 └── Frenzied (sub-condition of Raging)
                     └── Registers FrenziedStrike action (bonus action melee)
```

### Factory

```python
from dnd.classes.barbarian_factory import create_barbarian, BarbarianConfig, PrimalPathChoice

config = BarbarianConfig(
    level=5,
    name="Berserker",
    position=(3, 3),
    faction="heroes",
    primal_path=PrimalPathChoice.BERSERKER,
)
barbarian = create_barbarian(config)
```

**Signature**: `create_barbarian(config: BarbarianConfig, source_id: Optional[UUID] = None) -> Entity`

---

## 8. Feats

Feats use the same `BaseCondition` pattern as class features. Currently implemented:

### Lucky Feat (`dnd/classes/feats.py`)

- **Resource**: 3 luck points (long rest recharge)
- **Handler**: Listens for `ATTACK_D20_ROLL_RESULT`, `SAVE_D20_ROLL_RESULT`, `CHECK_D20_ROLL_RESULT` at EFFECT phase
- **Logic**: If own roll < 10, spend 1 luck point, reroll d20, keep better result
- **Pattern**: Resource + multi-trigger handler (same pattern as Indomitable but for all d20 rolls)

```python
from dnd.classes.feats import LuckyFeature

lucky = LuckyFeature(
    source_entity_uuid=entity.uuid,
    target_entity_uuid=entity.uuid
)
entity.add_condition(lucky)
```

Future feats would follow the same pattern - a `BaseCondition` that adds resources, handlers, and/or modifiers.

---

## 9. Spellcasting Infrastructure

### SpellcastingBlock (`dnd/blocks/spellcasting.py`)

Every entity has a `SpellcastingBlock` (non-optional). This allows items to grant spell uses even to non-caster classes.

**Fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `spellcasting_ability` | `AbilityName` | `"charisma"`, `"intelligence"`, or `"wisdom"` |
| `spell_attack_bonus` | `ModifiableValue` | Spell-specific attack bonus (e.g., Wand of War Mage) |
| `spell_damage_bonus` | `ModifiableValue` | Spell-specific damage bonus (e.g., Elemental Affinity) |
| `spell_dc_bonus` | `ModifiableValue` | Spell save DC bonus (e.g., Robe of Archmagi) |
| `spell_crit_threshold` | `ModifiableValue` | Spell crit range (stacks with Equipment) |
| `spell_crit_extra_dice` | `ModifiableValue` | Extra dice on spell crits (stacks with Equipment) |
| `extra_spell_damage_dices` | `List[int]` | Extra spell damage dice values |
| `extra_spell_damage_dices_numbers` | `List[int]` | Extra spell damage dice counts |
| `extra_spell_damage_bonus` | `List[ModifiableValue]` | Extra spell damage bonuses |
| `extra_spell_damage_type` | `List[DamageType]` | Extra spell damage types |

**Design decisions:**
- **Always present on Entity** - Items can grant spell uses to non-casters
- **Spell slots live in ActionEconomy** - `spell_slot_1` through `spell_slot_9` as `ModifiableValue` fields
- **Spells ARE actions** - `SpellAction` subclasses registered as templates via `register_action()`
- **Proficiency bonus is NOT duplicated** - Uses `Entity.proficiency_bonus` directly
- **Critical stacking** - `Equipment.crit_threshold` affects ALL attacks (including spells); `spell_crit_threshold` adds ONLY for spells

### Entity Spell Methods (`dnd/entity.py`)

| Method | Returns | Purpose |
|--------|---------|---------|
| `spell_attack_bonus(target_uuid?)` | `ModifiableValue` | Prof + ability mod + equipment attack + spell attack bonus. Cross-propagates with target. |
| `spell_save_dc()` | `int` | `8 + proficiency + ability_modifier + spell_dc_bonus` |
| `get_spell_crit_threshold()` | `int` | `20 - (equipment_crit + spell_crit)`. Default 20. |
| `get_spell_crit_extra_dice()` | `int` | Equipment extra dice + spell extra dice |
| `get_spell_damage_bonus()` | `ModifiableValue` | Equipment damage + spell damage combined |
| `has_spell_slot(level)` | `bool` | Checks `action_economy.spell_slot_{level}` >= 1 |
| `get_lowest_spell_slot(min_level)` | `int | None` | First available slot at or above min_level |
| `is_spellcaster` (property) | `bool` | True if any spell slot has non-zero base value |

### Spell Registration

```python
from dnd.actions_functional import register_spell, register_spells_by_name
from dnd.spells import FireBolt, MagicMissile, ALL_SPELLS

# Register individual spell class
register_spell(entity, FireBolt, caster_level=5)

# Register multiple by name (looks up in ALL_SPELLS dict)
register_spells_by_name(entity, ["Fire Bolt", "Magic Missile", "Fireball"], caster_level=5)
```

Both create `SpellAction` instances with `template=True` and register them on the entity.

### Spell Slot Configuration

Spell slots are configured via `ActionEconomyConfig`:

```python
entity_config = EntityConfig(
    # ...
    action_economy=ActionEconomyConfig(
        spell_slots={1: 4, 2: 3, 3: 2}  # Level 5 caster
    ),
)
```

At runtime, slots are `ModifiableValue` fields: `entity.action_economy.spell_slot_1`, etc.

### Upcasting / Variant Generation

Spells with upcasting automatically generate variant actions for each available slot level. The `SpellAction` base class handles this via `get_variants()` - each variant has a different `spell_slot_level` field.

### Concentration

See `CLAUDE.md` for full concentration system documentation. Key points:
- `Concentrating` condition on caster with `external_conditions` to spell effects on targets
- CON save on damage: `DC = max(10, damage/2)`
- One-spell limit: casting a new concentration spell ends the old one
- Full cleanup chain via `Entity._remove_condition_tree()`

---

## 10. Sorcerer (Partial Implementation)

### Current State: Bestiary Factory Only

The sorcerer exists as a `create_sorcerer()` function in `dnd/monsters/bestiary.py` - a minimal factory for testing AoE spells. It has **no class features**.

```python
from dnd.monsters.bestiary import create_sorcerer

sorcerer = create_sorcerer(
    name="Sorcerer",
    position=(5, 5),
    faction="heroes",
    level=5        # Only level 5 is meaningfully configured
)
```

**Factory configuration (Level 5 defaults):**
- Ability Scores: STR 8, DEX 14, CON 14, INT 10, WIS 10, **CHA 18**
- Health: `level` d6 hit dice
- Proficiency Bonus: 3
- Spell Slots: `{1: 4, 2: 3, 3: 2}`
- Spellcasting: `spellcasting_ability="charisma"`
- Registered Spells: Magic Missile, Fireball, Burning Hands, Lightning Bolt, Shatter, Thunderwave

### What Exists: Full Spell Infrastructure

41 spells are implemented across all schools (see `SORCERER_SPELL_ANALYSIS.md` for complete breakdown):
- 7 cantrips, 10 level 1, 8 level 2, 7 level 3, 2 level 4, 3 level 5, 1 level 6, 2 level 8, 1 level 9
- All spell patterns working: attack, save, AoE, multi-target, buff, concentration, zone, HP-threshold
- Complete upcasting/variant generation
- Full concentration system with cleanup chains

Spell dictionaries in `dnd/spells/__init__.py`: `CANTRIPS`, `LEVEL_1_SPELLS` through `LEVEL_9_SPELLS`, and `ALL_SPELLS`.

### What's Missing: Sorcerer Class Features

No sorcerer-specific class features exist yet. These would follow the same condition pattern as Fighter/Barbarian:

**Font of Magic (L2):**
- Sorcery Points resource in ActionEconomy
- Flexible Casting actions: convert slots to sorcery points and vice versa

**Metamagic (L3):**
- Each metamagic option = an EventHandler on spell events (same pattern as GWF on damage rolls)
- **Empowered Spell**: Reroll damage dice (handler on `DAMAGE_ROLL_RESULT`)
- **Quickened Spell**: Cast as bonus action (modify spell cost)
- **Heightened Spell**: Target has disadvantage on save (modify save event)
- **Careful Spell**: Allies auto-succeed on saves (modify AoE targeting)
- **Twinned Spell**: Duplicate single-target spell (clone spell event)
- **Distant/Extended/Subtle**: Modify spell parameters

**Draconic Bloodline (Subclass):**
- L1 Draconic Resilience: AC = 13 + DEX when unarmored (same pattern as Barbarian's UnarmoredDefense)
- L6 Elemental Affinity: Add CHA to chosen element damage (spell damage modifier)
- L14 Dragon Wings: Fly speed (movement modifier)
- L18 Draconic Presence: AoE frighten/charm (same pattern as Intimidating Presence)

**Implementation approach**: Same `BaseCondition` pattern used for Fighter/Barbarian:
- Each feature = a condition
- Sorcery Points = resource in ActionEconomy (like rage uses)
- Metamagic = event handlers (like GWF, Indomitable)
- Subclass features = modifier conditions (like fighting styles)

### Sorcerer Factory (Future)

Would follow the same `Config` + `create_` pattern as Fighter/Barbarian:

```python
# Future pattern (not yet implemented):
from dnd.classes.sorcerer_factory import create_sorcerer, SorcererConfig

config = SorcererConfig(
    level=5,
    name="Draconic Sorcerer",
    position=(5, 5),
    faction="heroes",
    sorcerous_origin="draconic_bloodline",
    dragon_ancestor_element="fire",
)
sorcerer = create_sorcerer(config)
```

---

## 11. Implementation Status

### Fighter (Complete)

| Level | Feature | Status |
|-------|---------|--------|
| 1 | All 6 Fighting Styles | Done |
| 1 | Second Wind | Done |
| 2 | Action Surge | Done |
| 3 | Improved Critical | Done |
| 4/6/8/12/14/16/19 | ASI | Done (via factory) |
| 5/11/20 | Extra Attack (1/2/3) | Done |
| 9/13/17 | Indomitable (1/2/3) | Done |
| 15 | Superior Critical | Done |
| 17 | Action Surge (2 uses) | Done |
| 18 | Survivor | Done |

### Barbarian (Complete)

| Level | Feature | Status |
|-------|---------|--------|
| 1 | Rage + Unarmored Defense | Done |
| 2 | Reckless Attack + Danger Sense | Done |
| 3 | Berserker: Frenzy | Done |
| 4/8/12/16/19 | ASI | Done (via factory) |
| 5 | Extra Attack + Fast Movement | Done |
| 6 | Berserker: Mindless Rage | Done |
| 7 | Feral Instinct | Done |
| 9/13/17 | Brutal Critical (+1/+2/+3) | Done |
| 10 | Berserker: Intimidating Presence | Done |
| 11 | Relentless Rage | Done |
| 14 | Berserker: Retaliation | Done |
| 15 | Persistent Rage | Done |
| 18 | Indomitable Might | Done |
| 20 | Primal Champion | Done |

### Sorcerer (Infrastructure Only)

| Component | Status |
|-----------|--------|
| SpellcastingBlock | Done |
| Spell slots in ActionEconomy | Done |
| Spell registration API | Done |
| 41 spells across all schools | Done |
| Bestiary factory (create_sorcerer L5) | Done |
| Sorcerer class features | Not started |
| Font of Magic / Sorcery Points | Not started |
| Metamagic | Not started |
| Draconic Bloodline subclass | Not started |
| Sorcerer factory (SorcererConfig) | Not started |

### Feats

| Feat | Status |
|------|--------|
| Lucky | Done |

---

## 12. Files Reference

### Class Implementation Files

| File | Purpose |
|------|---------|
| `dnd/classes/fighter.py` | All Fighter features + Champion archetype conditions |
| `dnd/classes/fighter_factory.py` | `FighterConfig` + `create_fighter()` factory |
| `dnd/classes/barbarian.py` | All Barbarian features + Berserker path conditions |
| `dnd/classes/barbarian_factory.py` | `BarbarianConfig` + `create_barbarian()` factory |
| `dnd/classes/rage.py` | Rage system: RageFeature, Raging, Frenzied, FrenzyFeature |
| `dnd/classes/feats.py` | Lucky feat |
| `dnd/classes/dice_processor_utils.py` | Shared dice manipulation utilities (GWF, Brutal Critical) |
| `dnd/classes/__init__.py` | Module exports |

### Spellcasting Files

| File | Purpose |
|------|---------|
| `dnd/blocks/spellcasting.py` | SpellcastingBlock + SpellcastingConfig |
| `dnd/actions_functional.py` | `register_spell()`, `register_spells_by_name()` |
| `dnd/spells/__init__.py` | Spell dictionaries (CANTRIPS through LEVEL_9_SPELLS, ALL_SPELLS) |
| `dnd/spells/evocation.py` | Fire Bolt, Fireball, Lightning Bolt, etc. |
| `dnd/spells/abjuration.py` | Mage Armor, Protection from Energy, Stoneskin |
| `dnd/spells/enchantment.py` | Hold Person, Hold Monster, Charm Person, Sleep, etc. |
| `dnd/spells/conjuration.py` | Call Lightning, Grease, Web, Cloudkill, Spirit Guardians |
| `dnd/spells/necromancy.py` | Chill Touch, False Life, Blight, Blindness/Deafness |
| `dnd/spells/illusion.py` | Blur, Fear, Hypnotic Pattern, Color Spray |
| `dnd/spells/transmutation.py` | Spike Growth |
| `dnd/monsters/bestiary.py` | `create_sorcerer()` bestiary factory |

### Reference Documentation

| File | Purpose |
|------|---------|
| `claude_docs/SORCERER_SPELL_ANALYSIS.md` | All 120 sorcerer spells analyzed by difficulty |
| `claude_docs/IMPLEMENTATION_GUIDE.md` | How to implement conditions, actions, handlers (Section 14: test patterns) |
