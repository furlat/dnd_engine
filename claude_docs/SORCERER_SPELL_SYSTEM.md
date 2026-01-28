# Sorcerer & Spell System Implementation Plan

Comprehensive plan for implementing the Sorcerer class and foundational spell system.

---

## KEY DESIGN DECISIONS (Updated)

These decisions supersede older sections in this document.

### 1. SpellcastingBlock is ALWAYS Present (Non-Optional)

```python
# Entity.spellcasting is NOT Optional
spellcasting: SpellcastingBlock = Field(...)  # Always present, defaults harmless for non-casters
```

**Why**:
- Items can grant spell uses to non-casters (e.g., wand that casts Fireball)
- Conditions that affect attacks (Blinded, Poisoned) should affect item-granted spells
- Avoids None-checks everywhere
- Default values (spellcasting_ability="charisma", all bonuses=0) are harmless for non-casters

### 2. Spell Slots are ModifiableValue in ActionEconomy (Not SpellcastingBlock)

```python
# In ActionEconomy:
spell_slot_1: ModifiableValue  # base=0 for non-casters
spell_slot_2: ModifiableValue
# ... through spell_slot_9

# CostType extended:
CostType = Literal["actions", "bonus_actions", "reactions", "movement",
                   "spell_slot_1", "spell_slot_2", ..., "spell_slot_9"]
```

**Why**:
- Follows existing pattern (actions, bonus_actions use ModifiableValue)
- Class conditions add permanent modifiers to increase max slots
- `consume()` adds negative "cost" modifier (same as existing actions)
- `reset_spell_slot_costs()` for long rest restoration

### 3. Spells ARE Actions (SpellAction Base Class)

Spells are `SpellAction` subclasses registered as **templates**, NOT a separate registry.

```python
class FireBolt(SpellAction):
    name: str = "Fire Bolt"
    spell_level: int = 0
    # ... _apply() implements the spell effect

# Registration:
entity.register_action(FireBolt(source_entity_uuid=entity.uuid, template=True))

# Known spells live in Entity.registered_actions, NOT SpellcastingBlock
```

### 4. Variant-Generation for Upcasting (NOT Cost Interception)

```python
# Base spell defines level, effects, upcast scaling
# get_available_actions() generates variants:

# MagicMissile (L1 base) with slots {1:4, 2:3, 3:2}:
# - MagicMissile@L1 - costs [action:1, spell_slot_1:1], 3 darts
# - MagicMissile@L2 - costs [action:1, spell_slot_2:1], 4 darts
# - MagicMissile@L3 - costs [action:1, spell_slot_3:1], 5 darts

# User picks variant explicitly → costs consumed → no ambiguity
```

### 5. Full Modifier Stacking with Equipment

Spell attacks combine:
1. `Entity.proficiency_bonus`
2. `ability_scores.get_ability(spellcasting_ability).modifier_bonus`
3. `Equipment.attack_bonus` ← Blinded, Poisoned disadvantage lives HERE
4. `SpellcastingBlock.spell_attack_bonus` ← Wand of War Mage lives HERE

```python
# Crit threshold stacking:
spell_crit = 20 - (Equipment.crit_threshold + SpellcastingBlock.spell_crit_threshold)
# So Improved Critical (Equipment.crit_threshold +1) affects spells!
```

### 6. SpellcastingBlock Fields (Current)

```
SpellcastingBlock:
├── spellcasting_ability: AbilityName    # CHA/INT/WIS
├── spell_attack_bonus: ModifiableValue  # Wand of War Mage (+1/2/3)
├── spell_damage_bonus: ModifiableValue  # Elemental Affinity (add CHA to fire)
├── spell_dc_bonus: ModifiableValue      # DC modifier beyond 8+prof+ability
├── spell_crit_threshold: ModifiableValue # Spell-specific crit range
├── spell_crit_extra_dice: ModifiableValue # Extra dice on spell crits
│
├── # Extra spell damage (parallel to Equipment.extra_attack_damage_*)
├── extra_spell_damage_dices: List[Literal[4,6,8,10,12,20]]
├── extra_spell_damage_dices_numbers: List[int]
├── extra_spell_damage_bonus: List[ModifiableValue]
└── extra_spell_damage_type: List[DamageType]
```

**NOT in SpellcastingBlock** (avoiding redundancy):
- Spell slots → `ActionEconomy.spell_slot_X`
- Known spells → `Entity.registered_actions`
- Proficiency bonus → `Entity.proficiency_bonus`
- Generic attack modifiers → `Equipment.attack_bonus`

---

## Executive Summary

The Sorcerer is a Charisma-based spellcaster with unique resource mechanics (sorcery points, metamagic). Unlike Fighter/Barbarian which primarily use conditions with modifiers and event handlers, the Sorcerer requires a **new foundational spell system** that can later support Wizard, Cleric, and other casters.

### New Systems Required

| System | Complexity | Description |
|--------|------------|-------------|
| **SpellcastingBlock** | Medium | Spell attack, spell DC, spell-specific modifiers |
| **ActionEconomy spell slots** | Low | ModifiableValue fields for slots 1-9 |
| **SpellAction Base** | Medium | Base class for all spells with variant generation |
| **Concentration** | Medium | Track + break on damage |
| **Area of Effect** | High | Cone, sphere, line, cube targeting |
| **Metamagic** | Medium | Spell modifiers using sorcery points |

### Timeline Estimate

- **Phase 1** (Foundation): ActionEconomy slots + SpellcastingBlock + SpellAction base
- **Phase 2** (Core Combat): Fire Bolt, Sacred Flame, Magic Missile, Mage Armor
- **Phase 3** (AoE): Fireball, Lightning Bolt, Burning Hands
- **Phase 4** (Sorcerer Features): Sorcery points, metamagic, Draconic Bloodline
- **Phase 5** (Polish): Factory, remaining spells, testing

### Spell Slot Table (Sorcerer)

```python
SORCERER_SPELL_SLOTS = {
    1:  {1: 2},
    2:  {1: 3},
    3:  {1: 4, 2: 2},
    4:  {1: 4, 2: 3},
    5:  {1: 4, 2: 3, 3: 2},
    6:  {1: 4, 2: 3, 3: 3},
    7:  {1: 4, 2: 3, 3: 3, 4: 1},
    8:  {1: 4, 2: 3, 3: 3, 4: 2},
    9:  {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    10: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
    11: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    12: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    13: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
    14: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
    15: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
    16: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
    17: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1},
    18: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 1, 7: 1, 8: 1, 9: 1},
    19: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 1, 8: 1, 9: 1},
    20: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 2, 8: 1, 9: 1},
}
```

---

## Part 2: SpellAction Base Class (Spells ARE Actions)

**NOTE: We do NOT use a SpellDefinition registry. Spells are SpellAction subclasses.**

### SpellAction Base Class

```python
class SpellAction(BaseAction):
    """Base class for all spell actions."""

    # Spell metadata (class-level defaults, instance can override)
    spell_level: int = 0  # Base level (0 for cantrips)
    spell_school: str = "evocation"
    concentration: bool = False

    # Variant tracking (instance-level)
    cast_at_level: int = 0  # Actual slot level (0 = cantrip, no slot)
    is_variant: bool = False  # True if this is a generated variant

    # Targeting (reuse existing Range/TargetType)
    spell_range: Range
    target_type: TargetType

    # Costs built dynamically per variant
    # (NOT static - variants have different spell slot costs)

    def generate_variants(self, entity: 'Entity') -> List['SpellAction']:
        """Generate all castable variants of this spell."""
        # Cantrip: single variant, no slot cost
        # Leveled: one variant per available slot level

    def _create_variant(self, cast_at_level: int, **overrides) -> 'SpellAction':
        """Create variant with modified costs/effects."""

    def get_upcast_bonus(self) -> int:
        """Levels above base: cast_at_level - spell_level."""
```

### Example Spell Implementation

```python
class FireBolt(SpellAction):
    """Spell attack cantrip."""
    name: str = "Fire Bolt"
    spell_level: int = 0
    spell_range: Range = Range(type=RangeType.RANGE, normal=120)
    target_type: TargetType = TargetType.ENTITY

    def _apply(self, event):
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid)

        # Spell attack roll (uses same set_from_target pattern as Attack)
        spell_attack = caster.spell_attack_bonus(target.uuid)
        target_ac = target.ac_bonus(caster.uuid)
        spell_attack.set_from_target(target_ac)

        dice_roll = caster.roll_d20(spell_attack, RollType.ATTACK)
        crit_threshold = caster.get_spell_crit_threshold()
        outcome = determine_attack_outcome(dice_roll, target_ac, crit_threshold)

        if outcome in [AttackOutcome.HIT, AttackOutcome.CRIT]:
            num_dice = self._get_damage_dice(caster.level)
            # Roll damage, apply to target...

        spell_attack.reset_from_target()

    def _get_damage_dice(self, caster_level: int) -> int:
        """Cantrip scaling: 1d10 at L1, 2d10 at L5, etc."""
        if caster_level >= 17: return 4
        if caster_level >= 11: return 3
        if caster_level >= 5: return 2
        return 1


class MagicMissile(SpellAction):
    """Auto-hit spell with upcast scaling."""
    name: str = "Magic Missile"
    spell_level: int = 1  # Base level
    spell_range: Range = Range(type=RangeType.RANGE, normal=120)
    target_type: TargetType = TargetType.ENTITY

    def _apply(self, event):
        num_darts = 3 + self.get_upcast_bonus()  # +1 dart per upcast level
        for _ in range(num_darts):
            # 1d4+1 force damage per dart, auto-hit
            ...
```

### Spell Schools (for reference)

```python
class SpellSchool(Enum):
    ABJURATION = "abjuration"
    CONJURATION = "conjuration"
    DIVINATION = "divination"
    ENCHANTMENT = "enchantment"
    EVOCATION = "evocation"
    ILLUSION = "illusion"
    NECROMANCY = "necromancy"
    TRANSMUTATION = "transmutation"
    classes: List[str]  # ["sorcerer", "wizard", ...]
```

### Spell Registry Structure

```python
SPELL_REGISTRY: Dict[str, SpellDefinition] = {
    "fire_bolt": SpellDefinition(
        name="Fire Bolt",
        level=0,
        school=SpellSchool.EVOCATION,
        casting_time=CastingTime.ACTION,
        range_type=SpellRangeType.RANGED,
        range_feet=120,
        attack_type="ranged",
        damage_dice=1,  # Scales with level
        damage_die_size=10,
        damage_type=DamageType.FIRE,
        description="Ranged spell attack. 1d10 fire damage.",
        classes=["sorcerer", "wizard"]
    ),
    "fireball": SpellDefinition(
        name="Fireball",
        level=3,
        school=SpellSchool.EVOCATION,
        casting_time=CastingTime.ACTION,
        range_type=SpellRangeType.RANGED,
        range_feet=150,
        aoe_shape=AoEShape.SPHERE,
        aoe_size=20,
        save_ability="dexterity",
        save_effect="half",
        damage_dice=8,
        damage_die_size=6,
        damage_type=DamageType.FIRE,
        upcast_dice_per_level=1,
        description="8d6 fire damage, DEX save for half. +1d6 per slot above 3rd.",
        classes=["sorcerer", "wizard"]
    ),
    # ... more spells
}
```

---

## Part 3: Base Spell Action

### SpellAction Base Class

```python
class SpellAction(BaseAction):
    """Base class for all spell actions."""

    spell_name: str
    spell_level: int
    slot_level: Optional[int] = None  # For leveled spells
    concentration: bool = False

    def check_costs(self) -> CostCheckResult:
        """Override to check spell slot availability."""
        caster = Entity.get(self.source_entity_uuid)

        # Cantrips don't need slots
        if self.spell_level == 0:
            return super().check_costs()

        # Check for available slot
        if not caster.spellcasting.has_slot(self.spell_level):
            return CostCheckResult(affordable=False, reason="No spell slots available")

        return super().check_costs()

    def _apply_costs(self, completion_event):
        """Consume spell slot after successful cast."""
        if self.slot_level and self.slot_level > 0:
            caster = Entity.get(self.source_entity_uuid)
            caster.spellcasting.consume_slot(self.slot_level)
        return super()._apply_costs(completion_event)
```

### Spell Event Types

```python
class SpellEvent(ActionEvent):
    spell_name: str
    spell_level: int
    slot_level: int
    caster_uuid: UUID
    targets: List[UUID] = []
    target_position: Optional[Tuple[int, int]] = None

class SpellAttackEvent(SpellEvent):
    attack_roll: Optional[DiceRoll] = None
    attack_bonus: int
    target_ac: int
    hit: bool = False

class SpellSaveEvent(SpellEvent):
    save_ability: AbilityName
    save_dc: int
    save_results: Dict[UUID, bool] = {}  # entity -> success

class SpellDamageEvent(SpellEvent):
    damage_roll: DiceRoll
    total_damage: int
    damage_type: DamageType
    targets_damaged: Dict[UUID, int] = {}  # entity -> damage taken
```

---

## Part 4: Concentration System

### Concentrating Condition

```python
class Concentrating(BaseCondition):
    """Tracks concentration on a spell. Breaking concentration ends the spell effect."""

    name: str = "Concentrating"
    spell_name: str
    spell_effect_uuid: Optional[UUID] = None  # The condition being maintained

    def _apply(self, declaration_event):
        target = Entity.get(self.target_entity_uuid)
        handler_uuids = []

        # End any existing concentration
        if "Concentrating" in target.active_conditions:
            target.remove_condition("Concentrating")

        # Register damage handler
        handler = create_concentration_break_handler(target.uuid, self.uuid)
        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        return [], handler_uuids, [], effect_event

    def _remove(self, event=None):
        # When concentration ends, also remove the spell effect
        if self.spell_effect_uuid:
            target = Entity.get(self.target_entity_uuid)
            for cond_name, cond in list(target.active_conditions.items()):
                if cond.uuid == self.spell_effect_uuid:
                    target.remove_condition(cond_name)
                    break
        return super()._remove(event)
```

### Concentration Break Handler

```python
def concentration_break_handler_processor(
    event: TakeDamageEvent,
    source_entity_uuid: UUID
) -> Optional[Event]:
    """On damage, make CON save or lose concentration."""

    if event.target_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if "Concentrating" not in entity.active_conditions:
        return None

    # Calculate DC: 10 or half damage, whichever is higher
    damage = event.total_damage
    dc = max(10, damage // 2)

    # Make Constitution saving throw
    request = entity.create_saving_throw_request(
        target_entity_uuid=source_entity_uuid,
        ability_name="constitution",
        dc=dc
    )
    _, dice_roll, success = entity.saving_throw(request)

    if not success:
        entity.remove_condition("Concentrating")
        return event.model_copy(update={
            "concentration_broken": True,
            "status_message": f"{entity.name} lost concentration"
        })

    return None
```

---

## Part 5: Area of Effect System

### AoE Shapes

```python
class AoEShape(Enum):
    CONE = "cone"
    SPHERE = "sphere"
    LINE = "line"
    CUBE = "cube"
    CYLINDER = "cylinder"
```

### GridMap AoE Methods

```python
# In dnd/core/gridmap.py

def get_entities_in_sphere(
    self,
    center: Tuple[int, int],
    radius_feet: int,
    include_center: bool = True
) -> List[UUID]:
    """Get all entities within radius of center point."""
    radius_squares = radius_feet // 5
    affected = []
    for pos, entity_uuids in self._entities_by_position.items():
        dist = self._distance(center, pos)
        if dist <= radius_squares:
            if not include_center and pos == center:
                continue
            affected.extend(entity_uuids)
    return affected

def get_entities_in_cone(
    self,
    origin: Tuple[int, int],
    direction: Tuple[int, int],  # Normalized direction vector
    length_feet: int
) -> List[UUID]:
    """Get entities in a cone originating from origin."""
    # Cone width = length at the end
    # Check if position is within cone angle
    ...

def get_entities_in_line(
    self,
    origin: Tuple[int, int],
    direction: Tuple[int, int],
    length_feet: int,
    width_feet: int = 5
) -> List[UUID]:
    """Get entities along a line."""
    ...

def get_entities_in_cube(
    self,
    corner: Tuple[int, int],
    size_feet: int
) -> List[UUID]:
    """Get entities in a cube."""
    size_squares = size_feet // 5
    affected = []
    for x in range(corner[0], corner[0] + size_squares):
        for y in range(corner[1], corner[1] + size_squares):
            affected.extend(self._entities_by_position.get((x, y), []))
    return affected
```

---

## Part 6: Sorcerer Class Features

### Level 1: Spellcasting + Sorcerous Origin

```python
class SpellcastingFeature(BaseCondition):
    """Grants spellcasting ability."""
    name: str = "Spellcasting"
    sorcerer_level: int

    def _apply(self, declaration_event):
        target = Entity.get(self.target_entity_uuid)

        # Initialize SpellcastingBlock if not present
        if not target.spellcasting:
            target.spellcasting = SpellcastingBlock(
                owner=target,
                spellcasting_ability="charisma"
            )

        # Set spell slots for level
        target.spellcasting.max_spell_slots = SORCERER_SPELL_SLOTS[self.sorcerer_level]
        target.spellcasting.spell_slots = dict(target.spellcasting.max_spell_slots)

        # Register known spells as action templates
        for spell_name in target.spellcasting.spells_known:
            spell_action = create_spell_action(spell_name, target.uuid)
            target.register_action(spell_action)

        return [], [], [], effect_event
```

### Level 1: Draconic Resilience

```python
class DraconicResilience(BaseCondition):
    """AC = 13 + DEX when unarmored. +1 HP per level."""
    name: str = "Draconic Resilience"
    sorcerer_level: int

    def _apply(self, declaration_event):
        target = Entity.get(self.target_entity_uuid)
        outs = []

        # +1 HP per sorcerer level (add to max HP)
        hp_mod = NumericalModifier.create(
            source_entity_uuid=self.target_entity_uuid,
            name="Draconic Resilience",
            value=self.sorcerer_level
        )
        mod_uuid = target.health.max_hit_points.self_static.add_value_modifier(hp_mod)
        outs.append((target.health.max_hit_points.uuid, mod_uuid))

        # Contextual AC bonus (only when unarmored)
        ac_mod = ContextualNumericalModifier(
            name="Draconic Resilience",
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            callable=draconic_resilience_ac_check
        )
        ac_mod_uuid = target.equipment.ac_bonus.self_contextual.add_value_modifier(ac_mod)
        outs.append((target.equipment.ac_bonus.uuid, ac_mod_uuid))

        return outs, [], [], effect_event

def draconic_resilience_ac_check(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID],
    context: Optional[dict]
) -> Optional[NumericalModifier]:
    """AC = 13 + DEX when not wearing armor."""
    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # Check if wearing armor
    if entity.equipment.body_armor and entity.equipment.body_armor.type != ArmorType.CLOTH:
        return None

    # Calculate: 13 + DEX - 10 (since base AC is 10)
    dex_mod = entity.ability_scores.dexterity.modifier
    bonus = 3 + dex_mod  # 13 + DEX - 10 base
    return NumericalModifier.create(source_entity_uuid, "Draconic Resilience", bonus)
```

### Level 2: Font of Magic

```python
class FontOfMagic(BaseCondition):
    """Grants sorcery points resource and Flexible Casting actions."""
    name: str = "Font of Magic"
    sorcerer_level: int

    def _apply(self, declaration_event):
        target = Entity.get(self.target_entity_uuid)

        # Add sorcery points resource
        target.action_economy.add_resource(
            name="sorcery_points",
            maximum=self.sorcerer_level,
            recharge_type=RechargeType.LONG_REST
        )

        # Register Flexible Casting actions
        target.register_action(CreateSpellSlot(
            source_entity_uuid=target.uuid,
            template=True
        ))
        target.register_action(ConvertSlotToPoints(
            source_entity_uuid=target.uuid,
            template=True
        ))

        return [], [], [], effect_event
```

### Level 3: Metamagic

```python
class MetamagicFeature(BaseCondition):
    """Grants selected metamagic options."""
    name: str = "Metamagic"
    options: List[str]  # ["quickened", "empowered", ...]

    def _apply(self, declaration_event):
        target = Entity.get(self.target_entity_uuid)

        for option in self.options:
            if option == "quickened":
                target.add_condition(MetamagicQuickened(...))
            elif option == "empowered":
                target.add_condition(MetamagicEmpowered(...))
            # ... etc

        return [], [], [], effect_event
```

### Level 6: Elemental Affinity

```python
class ElementalAffinity(BaseCondition):
    """Add CHA to damage of ancestry type. Spend 1 SP for resistance."""
    name: str = "Elemental Affinity"
    damage_type: DamageType  # From dragon ancestry

    def _apply(self, declaration_event):
        target = Entity.get(self.target_entity_uuid)
        handler_uuids = []

        # Create handler to add CHA to matching damage
        handler = create_elemental_affinity_handler(target.uuid, self.damage_type)
        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        # Register Elemental Resistance action (1 SP for 1 hour resistance)
        target.register_action(ElementalResistance(
            source_entity_uuid=target.uuid,
            damage_type=self.damage_type,
            template=True
        ))

        return [], handler_uuids, [], effect_event
```

---

## Part 7: Spell Implementation Priority

### Tier 1: MVP (Must Have)

| Spell | Level | Type | Why |
|-------|-------|------|-----|
| Fire Bolt | 0 | Attack cantrip | Basic spell attack |
| Ray of Frost | 0 | Attack cantrip | Speed reduction test |
| Mage Armor | 1 | Buff | AC condition |
| Magic Missile | 1 | Auto-hit | No attack/save needed |
| Shield | 1 | Reaction | Reaction spell test |
| Burning Hands | 1 | Cone AoE | AoE + save |
| Hold Person | 2 | Save | Paralyzed condition |
| Misty Step | 2 | Teleport | Bonus action teleport |
| Fireball | 3 | Sphere AoE | Iconic spell |
| Lightning Bolt | 3 | Line AoE | Different AoE shape |

### Tier 2: Core (Should Have)

| Spell | Level | Type | Why |
|-------|-------|------|-----|
| Acid Splash | 0 | Save cantrip | DEX save cantrip |
| Chill Touch | 0 | Attack cantrip | Necrotic + healing block |
| Sleep | 1 | HP-based | Unique mechanic |
| Thunderwave | 1 | Cube AoE | Push effect |
| Blindness/Deafness | 2 | Save | Condition application |
| Invisibility | 2 | Buff | Existing Invisible condition |
| Scorching Ray | 2 | Multi-attack | Multiple spell attacks |
| Counterspell | 3 | Reaction | Counter other spells |
| Fly | 3 | Buff | Movement type change |
| Haste | 3 | Buff | Complex action economy |

### Tier 3: Extended (Nice to Have)

| Spell | Level | Type | Complexity |
|-------|-------|------|------------|
| Blur | 2 | Buff | Disadvantage on attackers |
| Web | 2 | Zone | Terrain effect |
| Slow | 3 | Debuff | Multi-target save |
| Cone of Cold | 5 | Cone AoE | Large damage |
| Disintegrate | 6 | Single target | Massive damage |
| Chain Lightning | 6 | Multi-target | Bouncing mechanic |

### Not Implementing (Out of Scope)

| Spell | Reason |
|-------|--------|
| Polymorph | Requires form/stat tracking |
| Dominate Person | NPC AI control |
| Animate Objects | Summon system |
| Teleport | Multi-location system |
| Wish | GM-level mechanics |
| Any summoning spell | Entity creation mid-combat |

---

## Part 8: Metamagic Implementation

### Implementable Metamagic

| Option | Cost | Implementation | Pattern |
|--------|------|----------------|---------|
| **Empowered Spell** | 1 SP | Reroll damage dice | DAMAGE_ROLLED handler (like GWF) |
| **Heightened Spell** | 3 SP | Disadvantage on save | Modifier on save roll |
| **Quickened Spell** | 2 SP | Action → bonus action | Change cost type |
| **Distant Spell** | 1 SP | Double range | Modify spell parameter |
| **Extended Spell** | 1 SP | Double duration | Modify condition duration |
| **Subtle Spell** | 1 SP | No V/S components | Skip component validation |

### Complex Metamagic (Later)

| Option | Cost | Challenge |
|--------|------|-----------|
| **Twinned Spell** | Level SP | Duplicate spell effect on second target |
| **Careful Spell** | 1 SP | Mark allies to auto-succeed AoE saves |

### Empowered Spell Example

```python
class MetamagicEmpowered(BaseCondition):
    """Can spend 1 SP to reroll damage dice on spells."""
    name: str = "Metamagic: Empowered Spell"

    def _apply(self, declaration_event):
        target = Entity.get(self.target_entity_uuid)

        # Register damage reroll handler
        handler = create_empowered_spell_handler(target.uuid)
        target.add_event_handler(handler)

        return [], [handler.uuid], [], effect_event

def empowered_spell_processor(
    event: SpellDamageEvent,
    source_entity_uuid: UUID
) -> Optional[SpellDamageEvent]:
    """Reroll up to CHA modifier damage dice."""
    if event.caster_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)

    # Check if we have sorcery points
    if not entity.action_economy.can_afford_resource("sorcery_points", 1):
        return None

    # Check if any dice worth rerolling (1s or 2s)
    cha_mod = max(1, entity.ability_scores.charisma.modifier)
    # ... reroll logic similar to GWF ...

    entity.action_economy.consume_resource("sorcery_points", 1)
    return modified_event
```

---

## Part 9: Sorcerer Factory

### SorcererConfig

```python
class DragonAncestry(Enum):
    BLACK = ("black", DamageType.ACID)
    BLUE = ("blue", DamageType.LIGHTNING)
    BRASS = ("brass", DamageType.FIRE)
    BRONZE = ("bronze", DamageType.LIGHTNING)
    COPPER = ("copper", DamageType.ACID)
    GOLD = ("gold", DamageType.FIRE)
    GREEN = ("green", DamageType.POISON)
    RED = ("red", DamageType.FIRE)
    SILVER = ("silver", DamageType.COLD)
    WHITE = ("white", DamageType.COLD)

class MetamagicChoice(Enum):
    CAREFUL = "careful"
    DISTANT = "distant"
    EMPOWERED = "empowered"
    EXTENDED = "extended"
    HEIGHTENED = "heightened"
    QUICKENED = "quickened"
    SUBTLE = "subtle"
    TWINNED = "twinned"

class SorcererConfig(BaseModel):
    level: int = Field(ge=1, le=20)
    name: str
    position: Tuple[int, int]
    faction: Optional[str] = None

    # Ability scores (BG3 style)
    base_charisma: int = 15
    base_constitution: int = 14
    base_dexterity: int = 13
    base_intelligence: int = 10
    base_wisdom: int = 12
    base_strength: int = 8
    bonus_plus_2: AbilityName = "charisma"
    bonus_plus_1: AbilityName = "constitution"

    # Sorcerous Origin
    dragon_ancestry: DragonAncestry = DragonAncestry.RED

    # Spell choices
    cantrips: List[str] = ["fire_bolt", "ray_of_frost", "light", "mage_hand"]
    spells_known: List[str] = ["magic_missile", "shield"]

    # Metamagic (L3+)
    metamagic_3: Optional[List[MetamagicChoice]] = None  # 2 choices
    metamagic_10: Optional[MetamagicChoice] = None       # +1
    metamagic_17: Optional[MetamagicChoice] = None       # +1

    # ASI
    asi_4: Optional[List[Tuple[AbilityName, int]]] = None
    asi_8: Optional[List[Tuple[AbilityName, int]]] = None
    asi_12: Optional[List[Tuple[AbilityName, int]]] = None
    asi_16: Optional[List[Tuple[AbilityName, int]]] = None
    asi_19: Optional[List[Tuple[AbilityName, int]]] = None

    equipment_preset: str = "standard"  # dagger, light crossbow, arcane focus
```

### create_sorcerer Function

```python
def create_sorcerer(config: SorcererConfig, source_id: Optional[UUID] = None) -> Entity:
    if source_id is None:
        source_id = uuid4()

    # Calculate final ability scores
    final_scores = calculate_final_ability_scores(config)

    # Create entity config
    entity_config = EntityConfig(
        ability_scores=create_ability_scores_config(final_scores),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=6,
            hit_dice_count=config.level,
            mode="average"
        )]),
        equipment=EquipmentConfig(),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=get_proficiency_bonus(config.level),
        position=config.position,
        faction=config.faction
    )

    # Create entity
    entity = Entity.create(name=config.name, source_entity_uuid=source_id, config=entity_config)

    # Setup standard actions
    setup_standard_actions(entity)

    # Initialize spellcasting
    entity.spellcasting = SpellcastingBlock(
        owner=entity,
        spellcasting_ability="charisma",
        cantrips_known=config.cantrips,
        spells_known=config.spells_known
    )

    # Apply level-gated features
    apply_sorcerer_features(entity, config)

    # Equip
    apply_sorcerer_equipment(entity, config.equipment_preset)

    return entity

def apply_sorcerer_features(entity: Entity, config: SorcererConfig):
    level = config.level

    # Level 1: Spellcasting + Draconic Bloodline
    entity.add_condition(SpellcastingFeature(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        sorcerer_level=level
    ))
    entity.add_condition(DraconicResilience(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        sorcerer_level=level
    ))

    # Level 2: Font of Magic
    if level >= 2:
        entity.add_condition(FontOfMagic(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            sorcerer_level=level
        ))

    # Level 3: Metamagic
    if level >= 3 and config.metamagic_3:
        entity.add_condition(MetamagicFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            options=[m.value for m in config.metamagic_3]
        ))

    # Level 6: Elemental Affinity
    if level >= 6:
        _, damage_type = config.dragon_ancestry.value
        entity.add_condition(ElementalAffinity(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            damage_type=damage_type
        ))

    # Level 14: Dragon Wings
    if level >= 14:
        entity.add_condition(DragonWingsFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))

    # Level 18: Draconic Presence
    if level >= 18:
        entity.add_condition(DraconicPresenceFeature(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))

    # Level 20: Sorcerous Restoration
    if level >= 20:
        entity.add_condition(SorcerousRestoration(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        ))
```

---

## Part 10: File Structure

```
dnd/
├── spells/
│   ├── __init__.py              # Exports
│   ├── base_spell.py            # SpellDefinition, SpellAction, SpellEvent
│   ├── spell_registry.py        # SPELL_REGISTRY dict
│   ├── aoe.py                   # AoE calculations (move from gridmap?)
│   ├── cantrips/
│   │   ├── __init__.py
│   │   ├── fire_bolt.py
│   │   ├── ray_of_frost.py
│   │   └── ...
│   ├── level_1/
│   │   ├── __init__.py
│   │   ├── burning_hands.py
│   │   ├── magic_missile.py
│   │   ├── mage_armor.py
│   │   ├── shield.py
│   │   └── ...
│   ├── level_2/
│   │   └── ...
│   ├── level_3/
│   │   ├── fireball.py
│   │   ├── lightning_bolt.py
│   │   └── ...
│   └── metamagic.py             # Metamagic conditions and processors
│
├── blocks/
│   └── spellcasting.py          # SpellcastingBlock
│
├── classes/
│   ├── sorcerer.py              # Sorcerer feature conditions
│   └── sorcerer_factory.py      # SorcererConfig, create_sorcerer
│
└── core/
    └── gridmap.py               # Add AoE methods (sphere, cone, line, cube)
```

---

## Summary: What We're Building

### New Components
1. **SpellcastingBlock** - Spell slots, attack, DC
2. **Concentration system** - Condition + damage handler
3. **AoE targeting** - GridMap methods for shapes
4. **Spell registry** - Structured spell data

### Reused Patterns
- Feature conditions (like SecondWindFeature)
- Resource system (like rage uses)
- Event handlers (like Great Weapon Fighting)
- Contextual modifiers (like Unarmored Defense)
- Factory pattern (like create_fighter)

### Sorcerer-Specific
- Sorcery points resource
- Flexible Casting actions
- Metamagic options
- Draconic Bloodline features (Resilience, Elemental Affinity, Wings, Presence)

### Initial Spell Count: 10-15
Focusing on combat-relevant spells that test all new systems (attack cantrips, AoE damage, saves, buffs, concentration).
