# Class System Design

Character classes are implemented as **collections of conditions** applied to entities. This leverages the existing condition system for modifiers, event handlers, and auto-cleanup.

**Key Insight**: A class is `Map<Class, Level> → List<Condition>`. Leveling up adds new conditions.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FEATURE CONDITIONS                                  │
│  dnd/classes/fighter.py                                                      │
│                                                                              │
│  SecondWindFeature    → adds Resource + registers SecondWind Action          │
│  ActionSurgeFeature   → adds Resource + registers ActionSurge Action         │
│  ExtraAttackFeature   → adds Resource + registers ExtraAttack Action         │
│  Indomitable          → adds Resource + registers EventHandler               │
│  Survivor             → registers EventHandler (TURN_START)                  │
│                                                                              │
│  FightingStyleDefense → adds AC modifier                                     │
│  FightingStyleArchery → adds ranged attack modifier                          │
│  GreatWeaponFighting  → registers EventHandler (DAMAGE_ROLLED)               │
│  ImprovedCritical     → adds critical threshold modifier                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                      Uses Resource System + Action Registry
                                    │
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ACTION ECONOMY                                      │
│  dnd/blocks/action_economy.py                                                │
│                                                                              │
│  ActionEconomy.resources: Dict[str, Resource]                                │
│  ActionEconomy.add_resource(name, maximum, recharge_type)                    │
│  ActionEconomy.consume_resource(name, amount)                                │
│  ActionEconomy.recharge_resources(trigger)  # SHORT_REST, LONG_REST         │
│                                                                              │
│  RechargeType: TURN_START, SHORT_REST, LONG_REST, NEVER                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Fighter Implementation (Complete)

All Fighter features + Champion archetype are implemented in `dnd/classes/fighter.py`.

### Level Progression

| Level | Feature | Implementation Type | Class |
|-------|---------|---------------------|-------|
| 1 | Fighting Styles | Condition | `FightingStyle*` |
| 1 | Second Wind | Feature Condition + Action | `SecondWindFeature`, `SecondWind` |
| 2 | Action Surge | Feature Condition + Action | `ActionSurgeFeature`, `ActionSurge` |
| 3 | Improved Critical | Condition | `ImprovedCritical` |
| 5 | Extra Attack | Feature Condition + Action | `ExtraAttackFeature`, `ExtraAttack` |
| 9 | Indomitable | Condition + EventHandler | `Indomitable` |
| 15 | Superior Critical | Condition | `SuperiorCritical` |
| 18 | Survivor | Condition + EventHandler | `Survivor` |

### Fighting Styles

| Style | Effect | Type |
|-------|--------|------|
| `FightingStyleArchery` | +2 to ranged attack rolls | Numerical modifier on `attack_bonus` |
| `FightingStyleDefense` | +1 AC when wearing armor | Contextual modifier on `ac_bonus` |
| `FightingStyleDueling` | +2 damage with one-handed weapon | Contextual modifier on `damage_bonus` |
| `GreatWeaponFighting` | Reroll 1s and 2s on damage dice | EventHandler on `DAMAGE_ROLLED` |
| `FightingStyleProtection` | Impose disadvantage on ally attacks | EventHandler on `ATTACK` (reaction) |
| `FightingStyleTwoWeaponFighting` | Add ability mod to off-hand damage | Numerical modifier on off-hand damage |

---

## Feature Condition Pattern

Feature conditions:
1. Add resources to `action_economy`
2. Register actions to `action_templates`
3. Optionally register event handlers

```python
class SecondWindFeature(BaseCondition):
    """Grants Second Wind: 1d10+level heal, bonus action, short rest recharge."""
    name: str = "Second Wind Feature"
    fighter_level: int = 1

    def _apply(self, declaration_event: Event) -> Tuple[...]:
        target = Entity.get(self.target_entity_uuid)
        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []

        # 1. Add resource
        target.action_economy.add_resource(
            name="second_wind",
            maximum=1,
            recharge_type=RechargeType.SHORT_REST
        )

        # 2. Register action template
        action = SecondWind(
            source_entity_uuid=target.uuid,
            fighter_level=self.fighter_level,
            template=True
        )
        target.register_action(action)

        effect_event = declaration_event.phase_to(EventPhase.EFFECT, ...)
        return outs, handler_uuids, [], effect_event
```

---

## Event Handler Patterns

### Dice Manipulation (DAMAGE_ROLLED)

Used by Great Weapon Fighting to reroll 1s and 2s:

```python
def great_weapon_fighting_processor(
    event: DamageRolledEvent,
    source_entity_uuid: UUID
) -> Optional[DamageRolledEvent]:
    if event.source_entity_uuid != source_entity_uuid:
        return None

    # Check weapon is two-handed or versatile (used two-handed)
    entity = Entity.get(source_entity_uuid)
    weapon = entity.equipment._get_weapon_by_slot(event.weapon_slot)
    if not _is_gwf_eligible(weapon):
        return None

    # Process each damage roll
    any_modified = False
    for i, original_roll in enumerate(event.final_rolls):
        results = original_roll.results
        new_results = []
        for r in results:
            if r <= 2:  # Reroll 1s and 2s
                new_results.append(random.randint(1, weapon.damage_dice))
                any_modified = True
            else:
                new_results.append(r)

        if new_results != results:
            new_roll = create_modified_dice_roll(original_roll, new_results)
            event.replace_roll(i, new_roll, "Great Weapon Fighting", "Rerolled")

    return event.model_copy(update={"modified": True}) if any_modified else None
```

### Save Reroll (SAVING_THROW)

Used by Indomitable to reroll failed saves:

```python
def indomitable_processor(
    event: SavingThrowEvent,
    source_entity_uuid: UUID
) -> Optional[SavingThrowEvent]:
    if event.target_entity_uuid != source_entity_uuid:
        return None
    if event.success:  # Only reroll failures
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity.action_economy.can_afford_resource("indomitable", 1):
        return None

    # Consume resource and reroll
    entity.action_economy.consume_resource("indomitable", 1)

    # Roll new d20
    new_roll = random.randint(1, 20)
    new_total = new_roll + event.bonus

    # Update event with new roll
    return event.model_copy(update={
        "dice_roll": new_roll,
        "total": new_total,
        "success": new_total >= event.dc,
        "modified": True
    })
```

### Turn Start (TURN_START)

Used by Survivor to heal at turn start:

```python
def survivor_processor(
    event: Event,
    source_entity_uuid: UUID
) -> Optional[Event]:
    if event.source_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)

    # Check HP is > 0 and <= half max
    current_hp = entity.get_hp()
    max_hp = entity.health.max_hit_points.normalized_score
    if current_hp <= 0 or current_hp > max_hp // 2:
        return None

    # Heal 5 + CON modifier
    con_mod = entity.ability_scores.constitution.modifier
    healing = 5 + con_mod

    entity.health.heal(healing)
    return event.model_copy(update={"modified": True})
```

---

## Modifier Condition Patterns

### Static Modifier (Archery)

```python
class FightingStyleArchery(BaseCondition):
    name: str = "Fighting Style: Archery"

    def _apply(self, declaration_event: Event) -> Tuple[...]:
        target = Entity.get(self.target_entity_uuid)
        outs = []

        # Add +2 to ranged attack bonus (self_static)
        mod_uuid = target.equipment.attack_bonus.self_static.add_value_modifier(
            NumericalModifier(
                name="Archery",
                value=2,
                source_entity_uuid=self.target_entity_uuid,
                target_entity_uuid=self.target_entity_uuid
            )
        )
        outs.append((target.equipment.attack_bonus.uuid, mod_uuid))

        return outs, [], [], effect_event
```

### Contextual Modifier (Defense)

```python
def defense_ac_check(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None
) -> Optional[NumericalModifier]:
    """Only applies when wearing armor."""
    entity = Entity.get(source_entity_uuid)
    if not entity or not entity.equipment.armor:
        return None
    if entity.equipment.armor.type == ArmorType.CLOTH:
        return None
    return NumericalModifier.create(source_entity_uuid, "Defense", value=1)


class FightingStyleDefense(BaseCondition):
    def _apply(self, declaration_event: Event) -> Tuple[...]:
        target = Entity.get(self.target_entity_uuid)
        outs = []

        # Contextual +1 AC (only when wearing armor)
        mod = ContextualNumericalModifier(
            name="Defense",
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            callable=defense_ac_check
        )
        mod_uuid = target.equipment.ac_bonus.self_contextual.add_value_modifier(mod)
        outs.append((target.equipment.ac_bonus.uuid, mod_uuid))

        return outs, [], [], effect_event
```

### Critical Threshold (Improved Critical)

```python
class ImprovedCritical(BaseCondition):
    """Champion Level 3: Critical hit on 19-20."""
    name: str = "Improved Critical"

    def _apply(self, declaration_event: Event) -> Tuple[...]:
        target = Entity.get(self.target_entity_uuid)
        outs = []

        # Add modifier that lowers crit threshold
        # (Implementation uses CriticalModifier with threshold property)
        mod_uuid = target.equipment.attack_bonus.self_static.add_critical_modifier(
            CriticalModifier(
                name="Improved Critical",
                value=CriticalStatus.CRIT_ON_19,  # Or threshold property
                source_entity_uuid=self.target_entity_uuid,
                target_entity_uuid=self.target_entity_uuid
            )
        )
        outs.append((target.equipment.attack_bonus.uuid, mod_uuid))

        return outs, [], [], effect_event
```

---

## Applying Fighter Features

```python
from dnd.classes.fighter import (
    SecondWindFeature,
    ActionSurgeFeature,
    ExtraAttackFeature,
    FightingStyleDefense,
    ImprovedCritical,
    Survivor
)

# Apply Level 1 features
fighter.add_condition(SecondWindFeature(
    source_entity_uuid=fighter.uuid,
    target_entity_uuid=fighter.uuid,
    fighter_level=5
))
fighter.add_condition(FightingStyleDefense(
    source_entity_uuid=fighter.uuid,
    target_entity_uuid=fighter.uuid
))

# Apply Level 2 feature
fighter.add_condition(ActionSurgeFeature(
    source_entity_uuid=fighter.uuid,
    target_entity_uuid=fighter.uuid,
    fighter_level=5
))

# Apply Level 3 Champion feature
fighter.add_condition(ImprovedCritical(
    source_entity_uuid=fighter.uuid,
    target_entity_uuid=fighter.uuid
))

# Apply Level 5 feature
fighter.add_condition(ExtraAttackFeature(
    source_entity_uuid=fighter.uuid,
    target_entity_uuid=fighter.uuid,
    extra_attacks=1  # 1 at L5, 2 at L11, 3 at L20
))

# Apply Level 18 Champion feature
fighter.add_condition(Survivor(
    source_entity_uuid=fighter.uuid,
    target_entity_uuid=fighter.uuid
))
```

---

## Dice Processor Utilities

Additional dice manipulation functions in `dnd/classes/dice_processor_utils.py`:

| Function | Use Case |
|----------|----------|
| `floor_results(roll, min)` | Elemental Adept: treat 1s as 2s |
| `ceiling_results(roll, max)` | Damage reduction effects |
| `reroll_below_and_substitute(roll, threshold, dice_size)` | GWF: reroll 1s/2s, must use new |
| `reroll_below_keep_best(roll, threshold, dice_size)` | Halfling Lucky: reroll 1s, keep best |
| `maximize_all(roll, dice_size)` | Testing: all max values |
| `minimize_all(roll)` | Testing: all 1s |

Core utility `create_modified_dice_roll(original, new_results)` is in fighter.py.

---

## Files Reference

| File | Contents |
|------|----------|
| `dnd/classes/__init__.py` | Exports all fighter classes and utilities |
| `dnd/classes/fighter.py` | All Fighter features + Champion archetype |
| `dnd/classes/dice_processor_utils.py` | Reference dice manipulation functions |
| `dnd/blocks/action_economy.py` | Resource system (RechargeType, Resource) |

---

## Implementation Status

### Fighter (Complete)

| Feature | Status | Notes |
|---------|--------|-------|
| Fighting Styles (6) | Complete | All 6 PHB styles |
| Second Wind | Complete | L1, bonus action, short rest |
| Action Surge | Complete | L2, once per turn, short rest |
| Improved Critical | Complete | L3 Champion, 19-20 |
| Extra Attack | Complete | L5/11/20, 1/2/3 attacks |
| Indomitable | Complete | L9/13/17, 1/2/3 uses |
| Superior Critical | Complete | L15 Champion, 18-20 |
| Survivor | Complete | L18 Champion, heal at turn start |

---

## Barbarian Implementation (In Progress)

All Barbarian features are in `dnd/classes/barbarian.py`. Uses BG3-style adaptations (no exhaustion for Frenzy).

### Level Progression

| Level | Feature | Implementation Type | Class | Status |
|-------|---------|---------------------|-------|--------|
| 1 | Rage | Feature Condition + Action | `RageFeature`, `Rage`, `Raging` | Complete |
| 1 | Unarmored Defense | Condition (contextual) | `UnarmoredDefense` | Complete |
| 2 | Reckless Attack | Feature Condition + Action | `RecklessAttackFeature`, `RecklessAttack` | Complete |
| 2 | Danger Sense | Condition | `DangerSense` | Complete |
| 3 | Berserker: Frenzy | Feature Condition + Action | `FrenzyFeature`, `Frenzy`, `Frenzied` | Complete |
| 5 | Extra Attack | Reuse Fighter's `ExtraAttackFeature` | — | Complete |
| 5 | Fast Movement | Condition (contextual) | `FastMovement` | Complete |
| 6 | Berserker: Mindless Rage | Condition + EventHandler | `MindlessRage` | Complete |
| 7 | Feral Instinct | Condition | `FeralInstinct` | Complete |
| 9/13/17 | Brutal Critical | Condition (ModifiableValue) | `BrutalCritical` | Complete |
| 10 | Berserker: Intimidating Presence | — | — | **Not Started** |
| 11 | Relentless Rage | Condition + EventHandler | `RelentlessRage` | Partial (needs testing) |
| 14 | Berserker: Retaliation | — | — | **Not Started** |
| 15 | Persistent Rage | Marker Condition | `PersistentRage` | Complete |
| 18 | Indomitable Might | — | — | **Not Started** |
| 20 | Primal Champion | — | — | **Not Started** |

### Rage System

Rage is the core Barbarian mechanic with maintenance tracking:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          RAGE SYSTEM                                         │
│                                                                              │
│  RageFeature       → adds rage Resource + registers Rage Action              │
│  Rage (Action)     → applies Raging condition when activated                 │
│  Raging            → the active rage state with all benefits                 │
│  KeepRage          → marker for rage maintenance (attacked/took damage)      │
│                                                                              │
│  Event Handlers (registered by Raging):                                      │
│    • rage_attack_tracker    → applies KeepRage on ATTACK                     │
│    • rage_damage_tracker    → applies KeepRage on TAKE_DAMAGE                │
│    • rage_maintenance       → ends rage at TURN_END if no KeepRage           │
│    • rage_armor_equip       → ends rage if heavy armor equipped              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Brutal Critical (ModifiableValue Pattern)

Uses `crit_extra_dice_melee` ModifiableValue instead of EventHandler:

```python
class BrutalCritical(BaseCondition):
    """L9: +1 die, L13: +2 dice, L17: +3 dice on melee crits."""
    extra_dice: int = 1

    def _apply(self, declaration_event: Event) -> Tuple[...]:
        target = Entity.get(self.target_entity_uuid)

        # Add to crit_extra_dice_melee (melee-only per SRD)
        brutal_mod = NumericalModifier.create(
            source_entity_uuid=self.target_entity_uuid,
            name="Brutal Critical",
            value=self.extra_dice
        )
        mod_uuid = target.equipment.crit_extra_dice_melee.self_static.add_value_modifier(brutal_mod)
        outs.append((target.equipment.crit_extra_dice_melee.uuid, mod_uuid))

        return outs, [], [], effect_event
```

The `Entity.get_crit_extra_dice(weapon_slot)` method combines general + type-specific modifiers.

### Missing Features

| Feature | Level | Description |
|---------|-------|-------------|
| Intimidating Presence | 10 | Frighten creatures (contested CHA check) |
| Retaliation | 14 | Reaction attack when taking damage |
| Indomitable Might | 18 | Use STR score as minimum for STR checks |
| Primal Champion | 20 | +4 STR and CON (max 24) |

### Test Files

| File | Coverage |
|------|----------|
| `examples/test_barbarian_rage.py` | Rage activation, maintenance, benefits, armor restrictions |
| `examples/test_brutal_critical.py` | crit_extra_dice system, melee-only, dice counts |
