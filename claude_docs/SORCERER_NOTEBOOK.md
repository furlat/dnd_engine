# Sorcerer Implementation Notebook

Working notes for implementing the Sorcerer class and spell system.

---

## SPELL SYSTEM DECOMPOSITION

### Existing Infrastructure vs New Requirements

| Component | Martial (Attack) | Spell | Status |
|-----------|------------------|-------|--------|
| **Attack Roll** | `entity.attack_bonus()` → `roll_d20()` | `spell_attack_bonus` → `roll_d20()` | **NEED** new spell attack bonus |
| **DC Calculation** | N/A (vs AC) | 8 + prof + CHA | **NEED** new spell_save_dc |
| **Damage Dice** | `Weapon.damage_dice` | `SpellDefinition.damage_dice` | **NEED** spell damage structure |
| **Range Validation** | `Attack.validate_range()` | Same pattern | **REUSE** - adapt for spell ranges |
| **LOS Validation** | `validate_line_of_sight()` | Same | **REUSE** directly |
| **Target Selection** | `TargetType.ENTITY/POSITION` | Same + AREA types | **EXTEND** TargetType enum |
| **Resource Cost** | `action_economy.consume()` | Spell slot consumption | **NEED** new slot system |
| **Saving Throws** | `entity.saving_throw(request)` | Same | **REUSE** directly |
| **Conditions** | `entity.add_condition()` with saves | Same | **REUSE** directly |
| **Modifier Propagation** | `set_from_target()` / `reset_from_target()` | Same for spell attack vs AC | **REUSE** pattern |

---

### Equipment Block: Current Attack Modifiers

From `dnd/blocks/equipment.py`:

```
Equipment
├── attack_bonus: ModifiableValue           # General attack bonus (applies to all)
├── melee_attack_bonus: ModifiableValue     # Melee-specific
├── ranged_attack_bonus: ModifiableValue    # Ranged-specific
├── damage_bonus: ModifiableValue           # General damage bonus
├── melee_damage_bonus: ModifiableValue     # Melee-specific
├── ranged_damage_bonus: ModifiableValue    # Ranged-specific
├── ac_bonus: ModifiableValue               # AC bonus (target)
├── crit_threshold: ModifiableValue         # Crit range modifier
├── crit_threshold_melee/ranged             # Specific crit range
└── crit_extra_dice_melee/ranged            # Brutal Critical
```

**Key insight**: Equipment holds martial combat modifiers. Spellcasting needs a parallel structure.

**For Spells, We Need**:
```
SpellcastingBlock (new)
├── spell_attack_bonus: ModifiableValue     # prof + CHA (or INT for Wizard)
├── spell_save_dc: ModifiableValue          # 8 + prof + CHA
├── spell_damage_bonus: ModifiableValue     # General spell damage (Elemental Affinity)
├── spell_slots: Dict[int, int]             # level -> current
├── max_spell_slots: Dict[int, int]         # level -> maximum
├── cantrips_known: List[str]               # Cantrip names
├── spells_known: List[str]                 # Spell names
└── concentration_spell: Optional[UUID]     # Active concentration condition
```

---

### Entity Methods: Attack Bonus Pattern

From `dnd/entity.py`:

```python
def attack_bonus(self, weapon_slot: WeaponSlot, target_entity_uuid: Optional[UUID]) -> ModifiableValue:
    # 1. Set target for modifier propagation
    self.set_target_entity(target_entity_uuid)

    # 2. Get component bonuses
    proficiency_bonus, weapon_bonus, attack_bonuses, ability_bonuses, _ = self._get_attack_bonuses(weapon_slot)

    # 3. Combine into single ModifiableValue
    source_attack_bonus = proficiency_bonus.combine_values([weapon_bonus] + attack_bonuses + ability_bonuses)

    # 4. Clean up
    self.clear_target_entity()
    return source_attack_bonus
```

**For Spell Attack, We Need**:
```python
def spell_attack_bonus(self, target_entity_uuid: Optional[UUID]) -> ModifiableValue:
    self.set_target_entity(target_entity_uuid)

    # Components: prof + CHA modifier + any spell attack bonuses
    proficiency = self.proficiency_bonus
    cha_modifier = self.ability_scores.charisma.modifier_bonus
    spell_bonus = self.spellcasting.spell_attack_bonus  # From SpellcastingBlock

    combined = proficiency.combine_values([cha_modifier, spell_bonus])

    self.clear_target_entity()
    return combined
```

---

### Saving Throws: Condition + Save Integration

From `dnd/core/base_conditions.py`:

```python
class BaseCondition(BaseObject):
    application_saving_throw: Optional[SavingThrowEvent] = None
    removal_saving_throw: Optional[SavingThrowEvent] = None
```

From `dnd/entity.py`:

```python
def add_condition(self, condition: BaseCondition, ...):
    # Check immunity first
    if self.check_condition_immunity(condition.name):
        return declaration_event.cancel(...)

    # Then check application save
    if check_save_throw and condition.application_saving_throw is not None:
        (_, _, success) = self.saving_throw(condition.application_saving_throw)
        if success:
            return declaration_event.cancel(...)

    # Apply condition
    condition.apply(declaration_event)
```

**Spell Pattern for Save Spells**:
```python
# Hold Person example
def _apply(self, execution_event: SpellEvent):
    caster = Entity.get(self.source_entity_uuid)
    target = Entity.get(self.target_entity_uuid)

    # Create save request with spell DC
    dc = caster.spellcasting.spell_save_dc.normalized_score
    request = caster.create_saving_throw_request(
        target_entity_uuid=target.uuid,
        ability_name="wisdom",
        dc=dc
    )

    # Execute save
    _, roll, success = target.saving_throw(request)

    if not success:
        # Apply Paralyzed condition with concentration tracking
        paralyzed = Paralyzed(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            duration=Duration(duration_type=DurationType.ROUNDS, duration=10)
        )
        target.add_condition(paralyzed, check_save_throw=False)  # Already failed

        # Add removal save at end of each turn
        paralyzed.removal_saving_throw = caster.create_saving_throw_request(...)
```

**Key**: Conditions already support `removal_saving_throw` for end-of-turn saves!

---

### Range System: Current Implementation

From `dnd/core/events.py`:

```python
class RangeType(str, Enum):
    REACH = "reach"   # Melee - adjacent cells
    RANGE = "range"   # Ranged - normal/long ranges

class Range(BaseModel):
    type: RangeType
    normal: int      # Normal range in feet
    long: Optional[int] = None  # Long range (disadvantage)
```

From `dnd/actions.py` - Attack.validate_range():

```python
distance_feet = source_entity.senses.get_feet_distance(target_entity.position)

if weapon_range.type == RangeType.RANGE:
    if distance_feet <= weapon_range.normal:
        pass  # In range
    elif weapon_range.long and distance_feet <= weapon_range.long:
        is_long_range = True  # Disadvantage
    else:
        return declaration_event.cancel(...)  # Out of range
```

**For Spells**:
- Most spells don't have "long range" disadvantage
- Touch spells = RangeType.REACH with normal=5
- Self spells = range=0 or special handling
- Ranged spells = RangeType.RANGE with just normal (no long)

```python
# Fire Bolt: 120ft
spell_range = Range(type=RangeType.RANGE, normal=120)

# Shocking Grasp: Touch
spell_range = Range(type=RangeType.REACH, normal=5)

# Burning Hands: Self (15ft cone)
# Need new: Range(type=RangeType.SELF, aoe_shape=AoEShape.CONE, aoe_size=15)
```

**Extend RangeType**:
```python
class RangeType(str, Enum):
    REACH = "reach"
    RANGE = "range"
    SELF = "self"    # NEW - spell originates from caster
```

---

### Line of Sight: Already Implemented

From `dnd/actions.py`:

```python
def validate_line_of_sight(declaration_event, source_entity_uuid):
    source_entity = Entity.get(source_entity_uuid)
    target_entity = Entity.get(declaration_event.target_entity_uuid)

    # Check if target is in visible entities
    if target_entity.uuid not in source_entity.senses.entities.keys():
        return declaration_event.cancel(status_message="Not in line of sight")

    return declaration_event.phase_to(EventPhase.DECLARATION, status_message="LOS validated")
```

**For Spells**: Reuse directly! Same pattern works.

---

### Resource System: Action Economy

From `dnd/blocks/action_economy.py`:

```python
class ActionEconomy(BaseBlock):
    resources: Dict[str, Resource] = {}

    def add_resource(self, name: str, maximum: int, recharge_type: RechargeType):
        self.resources[name] = Resource(name=name, maximum=maximum, current=maximum, recharge_type=recharge_type)

    def can_afford_resource(self, name: str, cost: int) -> bool:
        return self.resources[name].current >= cost

    def consume_resource(self, name: str, cost: int) -> bool:
        if self.can_afford_resource(name, cost):
            self.resources[name].current -= cost
            return True
        return False
```

**For Spell Slots - Option A** (Use existing resource system):
```python
# Add 9 resources
for level in range(1, 10):
    entity.action_economy.add_resource(
        name=f"spell_slot_{level}",
        maximum=SPELL_SLOTS[sorcerer_level][level],
        recharge_type=RechargeType.LONG_REST
    )
```

**For Spell Slots - Option B** (Dedicated SpellcastingBlock):
```python
class SpellcastingBlock(BaseBlock):
    spell_slots: Dict[int, int] = {}  # level -> current
    max_spell_slots: Dict[int, int] = {}

    def has_slot(self, level: int) -> bool:
        return self.spell_slots.get(level, 0) > 0

    def consume_slot(self, level: int) -> bool:
        if self.has_slot(level):
            self.spell_slots[level] -= 1
            return True
        return False

    def get_lowest_available_slot(self, min_level: int) -> Optional[int]:
        """For upcasting - find cheapest slot that can cast the spell."""
        for level in range(min_level, 10):
            if self.has_slot(level):
                return level
        return None
```

**Recommendation**: Option B is cleaner for spell-specific logic (upcasting, Flexible Casting).

---

### Modifier Propagation: Cross-Entity Pattern

From `dnd/entity.py` and `dnd/actions.py`:

```python
# In Attack.attack_consequences():

# 1. Set target relationships
source_entity.set_target_entity(target_entity_uuid)
target_entity.set_target_entity(source_entity_uuid)

# 2. Get attack bonus and AC
attack_bonus = source_entity.attack_bonus(weapon_slot, target_entity_uuid)
ac = target_entity.ac_bonus(source_entity.uuid)

# 3. Propagate to_target modifiers between entities
ac.set_from_target(attack_bonus)        # AC gains attack's to_target modifiers
attack_bonus.set_from_target(ac)        # Attack gains AC's to_target modifiers

# 4. Roll with combined modifiers
dice_roll = source_entity.roll_d20(attack_bonus, RollType.ATTACK)

# 5. Clean up
ac.reset_from_target()
attack_bonus.reset_from_target()
source_entity.clear_target_entity()
target_entity.clear_target_entity()
```

**For Spell Attacks**: Same pattern!
```python
# Fire Bolt example
spell_attack = caster.spell_attack_bonus(target.uuid)
ac = target.ac_bonus(caster.uuid)

ac.set_from_target(spell_attack)
spell_attack.set_from_target(ac)

roll = caster.roll_d20(spell_attack, RollType.SPELL_ATTACK)
outcome = determine_attack_outcome(roll, ac)

spell_attack.reset_from_target()
ac.reset_from_target()
```

---

### Event System: Spell Events Needed

Current attack events from `dnd/core/events.py`:

```python
EventType.ATTACK
EventType.DAMAGE_ROLLED
EventType.TAKE_DAMAGE
```

**For Spells, Add**:
```python
EventType.CAST_SPELL  # Already exists!
EventType.SPELL_ATTACK  # New - for spell attack rolls
EventType.SPELL_DAMAGE  # New - for spell damage
EventType.CONCENTRATION_BREAK  # New - concentration fails
```

**SpellEvent Structure**:
```python
class SpellEvent(ActionEvent):
    spell_name: str
    spell_level: int                    # Base level of spell
    slot_level: Optional[int]           # Actual slot used (for upcasting)
    caster_uuid: UUID
    spell_attack_bonus: Optional[ModifiableValue] = None
    spell_save_dc: Optional[int] = None
    save_ability: Optional[AbilityName] = None

class SpellAttackEvent(SpellEvent):
    dice_roll: Optional[DiceRoll] = None
    target_ac: Optional[ModifiableValue] = None
    attack_outcome: Optional[AttackOutcome] = None

class SpellDamageEvent(SpellEvent):
    damage_dice: List[Damage] = []
    damage_rolls: List[DiceRoll] = []
    total_damage: int = 0
    targets_affected: Dict[UUID, int] = {}  # entity -> damage taken
```

---

### Damage Resistance System: Already Implemented

From `dnd/blocks/health.py`:

```python
class Health(BaseBlock):
    damage_reduction: DamageReduction  # Contains resistance per damage type

    def get_resistance(self, damage_type: DamageType) -> ResistanceStatus:
        return self.damage_reduction.resistance[damage_type]

    def calculate_damage_multiplier(self, damage_type: DamageType) -> float:
        resistance = self.get_resistance(damage_type)
        if resistance == ResistanceStatus.IMMUNITY:
            return 0.0
        elif resistance == ResistanceStatus.RESISTANCE:
            return 0.5
        elif resistance == ResistanceStatus.VULNERABILITY:
            return 2.0
        return 1.0

    def take_damage(self, damage: int, damage_type: DamageType, source_entity_uuid: UUID) -> int:
        # Applies multiplier automatically
        multiplier = self.calculate_damage_multiplier(damage_type)
        actual_damage = int(damage * multiplier)
        # ... apply to temp HP then current HP
```

**For Spells**: This works perfectly! Fire Bolt deals `DamageType.FIRE`, resistances auto-apply.

Raging Barbarian adds `ResistanceStatus.RESISTANCE` to B/P/S - spells bypass this!

---

### Area of Effect: NEW SYSTEM NEEDED

**GridMap already has entity tracking**:
```python
self._entities_by_position: DefaultDict[Tuple[int, int], Set[UUID]]
```

**Need to add AoE query methods**:
```python
class GridMap:
    def get_entities_in_radius(self, center: Tuple[int, int], radius_feet: int) -> List[UUID]:
        """Sphere/circle AoE - Fireball, etc."""
        radius_squares = radius_feet // 5
        affected = []
        for pos, entity_uuids in self._entities_by_position.items():
            dx = abs(pos[0] - center[0])
            dy = abs(pos[1] - center[1])
            # Use Euclidean distance for true circles
            if (dx*dx + dy*dy) <= radius_squares*radius_squares:
                affected.extend(entity_uuids)
        return affected

    def get_entities_in_cone(
        self,
        origin: Tuple[int, int],
        direction: Tuple[int, int],  # Unit vector
        length_feet: int
    ) -> List[UUID]:
        """Cone AoE - Burning Hands, Cone of Cold."""
        # Cone: width = length at the end
        # Check if position is within cone angle (90 degrees typically)
        ...

    def get_entities_in_line(
        self,
        origin: Tuple[int, int],
        direction: Tuple[int, int],
        length_feet: int,
        width_feet: int = 5
    ) -> List[UUID]:
        """Line AoE - Lightning Bolt."""
        # Bresenham's line or simple rectangular check
        ...

    def get_entities_in_cube(
        self,
        corner: Tuple[int, int],  # Point of origin corner
        size_feet: int
    ) -> List[UUID]:
        """Cube AoE - Thunderwave."""
        size_squares = size_feet // 5
        affected = []
        for x in range(corner[0], corner[0] + size_squares):
            for y in range(corner[1], corner[1] + size_squares):
                affected.extend(self._entities_by_position.get((x, y), []))
        return affected
```

**AoE Shape Enum**:
```python
class AoEShape(str, Enum):
    SPHERE = "sphere"    # Centered on point, radius
    CONE = "cone"        # Originates from caster, length = width at end
    LINE = "line"        # Originates from caster, length x width
    CUBE = "cube"        # Point of origin (corner), size
    CYLINDER = "cylinder"  # Centered on point, radius x height
```

**Direction for Cones/Lines**:
```python
class Direction(str, Enum):
    NORTH = "north"      # (0, -1)
    SOUTH = "south"      # (0, 1)
    EAST = "east"        # (1, 0)
    WEST = "west"        # (-1, 0)
    NORTHEAST = "northeast"  # (1, -1)
    # ... etc
```

---

### Concentration: NEW SYSTEM NEEDED

**Key Rules**:
1. Only one concentration spell at a time
2. Casting new concentration spell ends the old one
3. Taking damage → CON save (DC = max(10, damage/2)) or lose concentration
4. Becoming incapacitated ends concentration

**Implementation**:

```python
class Concentrating(BaseCondition):
    """Tracks concentration on a spell."""
    name: str = "Concentrating"
    spell_name: str
    spell_effect_uuid: Optional[UUID] = None  # The condition being maintained

    def _apply(self, declaration_event):
        target = Entity.get(self.target_entity_uuid)

        # End any existing concentration
        if "Concentrating" in target.active_conditions:
            target.remove_condition("Concentrating")

        # Register damage handler for CON saves
        handler = EventHandler(
            name="Concentration Check",
            source_entity_uuid=target.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TAKE_DAMAGE,
                    event_phase=EventPhase.EFFECT
                )
            ],
            event_processor=concentration_check_processor
        )
        target.add_event_handler(handler)

        return [], [handler.uuid], [], effect_event

    def _remove(self, event=None):
        # When concentration ends, also remove the spell effect
        if self.spell_effect_uuid:
            target = Entity.get(self.target_entity_uuid)
            for cond_name, cond in list(target.active_conditions.items()):
                if cond.uuid == self.spell_effect_uuid:
                    target.remove_condition(cond_name)
                    break
        return super()._remove(event)

def concentration_check_processor(event: TakeDamageEvent, source_entity_uuid: UUID):
    """CON save on damage or lose concentration."""
    if event.target_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if "Concentrating" not in entity.active_conditions:
        return None

    # Calculate DC: 10 or half damage, whichever is higher
    damage = event.total_damage
    dc = max(10, damage // 2)

    # CON save
    request = entity.create_saving_throw_request(
        target_entity_uuid=source_entity_uuid,
        ability_name="constitution",
        dc=dc
    )
    _, roll, success = entity.saving_throw(request)

    if not success:
        entity.remove_condition("Concentrating")
        return event.model_copy(update={
            "status_message": f"{entity.name} lost concentration (failed DC {dc})"
        })

    return None
```

**Concentration-Ending Conditions**:
- Register handler for `EventType.CONDITION_APPLICATION` with "Incapacitated"
- Or just check in Incapacitated._apply() if entity has Concentrating

---

### Multi-Target Save Pattern (AoE Spells)

```python
def apply_aoe_save_spell(
    caster: Entity,
    center: Tuple[int, int],
    radius_feet: int,
    damage_dice: Dice,
    damage_type: DamageType,
    save_ability: AbilityName,
    half_on_success: bool = True
) -> Dict[UUID, int]:
    """Generic AoE save spell application."""

    # Get all entities in area
    grid = get_map()
    affected_uuids = grid.get_entities_in_radius(center, radius_feet)

    # Calculate DC once
    dc = caster.spellcasting.spell_save_dc.normalized_score

    # Roll damage once (same roll for all targets)
    damage_roll = damage_dice.roll
    full_damage = damage_roll.total
    half_damage = full_damage // 2

    results: Dict[UUID, int] = {}

    for entity_uuid in affected_uuids:
        entity = Entity.get(entity_uuid)
        if not entity:
            continue

        # Each creature makes a save
        request = caster.create_saving_throw_request(
            target_entity_uuid=entity_uuid,
            ability_name=save_ability,
            dc=dc
        )
        _, _, success = entity.saving_throw(request)

        if success:
            damage_taken = half_damage if half_on_success else 0
        else:
            damage_taken = full_damage

        entity.health.take_damage(damage_taken, damage_type, caster.uuid)
        results[entity_uuid] = damage_taken

    return results
```

---

## ARCHITECTURE DECISION: SpellcastingBlock vs ActionEconomy vs Entity

### Current Architecture Analysis

**BaseBlock Pattern**:
- Blocks hold `values: Dict[UUID, ModifiableValue]` (auto-populated from attributes)
- Blocks hold `blocks: Dict[UUID, BaseBlock]` (sub-blocks)
- `set_target_entity()` propagates to all values/sub-blocks
- Blocks are data containers; Entity orchestrates interactions

**Entity Wrapper Pattern** (from entity.py):
```python
def attack_bonus(self, weapon_slot, target_entity_uuid) -> ModifiableValue:
    # 1. Set target
    self.set_target_entity(target_entity_uuid)

    # 2. Gather bonuses from various blocks
    proficiency_bonus, weapon_bonus, attack_bonuses, ability_bonuses, _ = self._get_attack_bonuses(weapon_slot)

    # 3. Combine into single ModifiableValue
    source_attack_bonus = proficiency_bonus.combine_values([weapon_bonus] + attack_bonuses + ability_bonuses)

    # 4. Clean up
    self.clear_target_entity()
    return source_attack_bonus
```

**Key insight**: Entity COMBINES modifiers from multiple sources. Blocks HOLD their piece of the puzzle.

**ActionEconomy Pattern**:
- `resources: Dict[str, Resource]` - simple name → Resource mapping
- `Resource` has: `current`, `maximum`, `recharge_type`
- Methods: `add_resource()`, `consume_resource()`, `can_afford_resource()`
- No ModifiableValue for resources - just simple int tracking

**Self-Targeting Actions** (Dash, Dodge, Disengage):
- `target_type: TargetType = TargetType.SELF`
- `target_entity_uuid = source_entity_uuid` in event creation
- No special validation needed for targeting self
- Spells like Mage Armor will follow this exact pattern

---

### Spell Slots as ModifiableValues in ActionEconomy

**Key Insight**: Looking at how actions/bonus_actions/reactions work:
- ModifiableValue stores the MAX (base_value + permanent modifiers)
- Consumption adds NEGATIVE "cost" modifiers
- Recharge removes all "cost" modifiers

Spell slots should follow the EXACT same pattern, just with LONG_REST recharge instead of TURN_START.

**Implementation in ActionEconomy:**
```python
class ActionEconomy(BaseBlock):
    # Existing (recharge on TURN_START)
    actions: ModifiableValue        # base=1
    bonus_actions: ModifiableValue  # base=1
    reactions: ModifiableValue      # base=1
    movement: ModifiableValue       # base=30

    # NEW: Spell slots (recharge on LONG_REST)
    spell_slot_1: ModifiableValue  # base=0 (non-casters have no slots)
    spell_slot_2: ModifiableValue  # base=0
    spell_slot_3: ModifiableValue  # base=0
    spell_slot_4: ModifiableValue  # base=0
    spell_slot_5: ModifiableValue  # base=0
    spell_slot_6: ModifiableValue  # base=0
    spell_slot_7: ModifiableValue  # base=0
    spell_slot_8: ModifiableValue  # base=0
    spell_slot_9: ModifiableValue  # base=0

    resources: Dict[str, Resource]  # For things like sorcery_points, rage, etc.
```

**How it works:**
```python
# Sorcerer L1 condition adds permanent modifier:
entity.action_economy.spell_slot_1.self_static.add_value_modifier(
    NumericalModifier(name="Sorcerer L1", value=2)
)
# Max 1st-level slots = 2

# Sorcerer L3 adds more:
entity.action_economy.spell_slot_1.self_static.add_value_modifier(
    NumericalModifier(name="Sorcerer L3", value=2)  # Now max = 4
)
entity.action_economy.spell_slot_2.self_static.add_value_modifier(
    NumericalModifier(name="Sorcerer L3", value=2)  # 2nd-level slots unlocked
)

# Casting a spell - uses existing consume():
entity.action_economy.consume("spell_slot_1", 1)
# Adds -1 "cost" modifier, available = max - 1

# Long rest - new method:
entity.action_economy.reset_spell_slot_costs()
# Removes all "cost" modifiers from spell slots, restoring to max
```

**CostType Extension:**
```python
CostType = Literal[
    "actions", "bonus_actions", "reactions", "movement",
    "spell_slot_1", "spell_slot_2", "spell_slot_3", "spell_slot_4", "spell_slot_5",
    "spell_slot_6", "spell_slot_7", "spell_slot_8", "spell_slot_9"
]
```

**Benefits:**
1. **Consistent** - Same pattern as actions/bonus_actions
2. **Modifiable max** - Level-up conditions add permanent modifiers
3. **Items work naturally** - Pearl of Power adds +1 to spell_slot_3
4. **No new systems** - Reuses ModifiableValue, Cost, consume()
5. **Upcasting** - Just use a higher slot's cost type

**Sorcery points ARE a simple resource** (fixed max per level):
```python
entity.action_economy.add_resource("sorcery_points", level, RechargeType.LONG_REST)
```

---

### Dynamic Cost Modification (Metamagic Quickened, Haste Action)

**Current Cost System**:
```python
class Cost(BaseCost):
    cost_type: CostType  # "actions", "bonus_actions", "reactions", "movement"
    cost: int
    resource_name: Optional[str]
    resource_cost: int
    evaluator: Optional[CostEvaluator]
```

Actions define costs at construction time. Problem: Metamagic changes costs dynamically.

**Option A: Event Handler on DECLARATION**
```python
def quickened_spell_cost_modifier(event: ActionEvent, source_uuid: UUID):
    # Check if Quickened Spell is active and this is a spell
    # Modify event.costs to change action → bonus_action
    # Consume sorcery points
```
- Pro: Uses existing event system
- Con: Costs already evaluated before DECLARATION phase

**Option B: Cost as ModifiableValue**
```python
class ActionEconomy(BaseBlock):
    action_cost_modifier: ModifiableValue  # Conditions add modifiers here
```
- Pro: Fits existing modifier pattern
- Con: Cost modifiers are per-action-type, not per-action-instance

**Option C: Cost evaluation hook**
The `check_costs()` method in BaseAction calls `cost.evaluator()`. We could:
```python
class Cost(BaseCost):
    cost_modifier: Optional[Callable[[UUID, CostType, int], Tuple[CostType, int]]] = None
```
- The modifier can change cost_type and/or cost amount
- Quickened Spell adds a modifier that changes `actions` → `bonus_actions`

**Option D: Spell action checks metamagic state**
```python
class FireBolt(SpellAction):
    def _get_effective_costs(self) -> List[Cost]:
        entity = Entity.get(self.source_entity_uuid)
        base_costs = self.costs.copy()

        # Check for Quickened Spell
        if "MetamagicQuickenedActive" in entity.active_conditions:
            # Replace action cost with bonus_action
            for cost in base_costs:
                if cost.cost_type == "actions":
                    cost.cost_type = "bonus_actions"
            # Add sorcery point cost
            base_costs.append(Cost(resource_name="sorcery_points", resource_cost=2))

        return base_costs
```
- Pro: Explicit, easy to understand
- Con: Every spell needs this logic

**Recommended: Option D with base class support**

```python
class SpellAction(BaseAction):
    def check_costs(self) -> bool:
        """Override to apply metamagic cost modifications."""
        effective_costs = self._get_effective_costs()
        for cost in effective_costs:
            if cost.evaluator and not cost.evaluator(self.source_entity_uuid, cost.cost_type, cost.cost):
                return False
            # ... resource check
        return True

    def _get_effective_costs(self) -> List[Cost]:
        """Apply metamagic modifications to base costs."""
        entity = Entity.get(self.source_entity_uuid)
        costs = [cost.model_copy() for cost in self.costs]

        # Check for Quickened Spell activation
        if self._is_metamagic_active(entity, "quickened"):
            costs = self._apply_quickened(costs)

        return costs
```

---

### Separation of Concerns: Final Design

#### SpellcastingBlock (new) - Minimal, No Redundancy

**Key Insight**: Spell knowledge is tracked via `Entity.registered_actions` (which SpellAction templates are registered). SpellcastingBlock does NOT duplicate this - it only holds what it uniquely needs.

**Holds**:
- `spellcasting_ability: AbilityName` - "charisma" for Sorcerer, "intelligence" for Wizard
- `spell_attack_bonus: ModifiableValue` - **SPELL-SPECIFIC** attack modifier (Wand of War Mage)
- `spell_damage_bonus: ModifiableValue` - **SPELL-SPECIFIC** damage modifier (Elemental Affinity)
- `spell_save_dc_bonus: ModifiableValue` - DC modifier beyond 8+prof+ability

**NOT in SpellcastingBlock**:
- Spell slots → `ActionEconomy.spell_slot_1` through `spell_slot_9` (ModifiableValues)
- Known spells → `Entity.registered_actions` (filter for SpellAction instances)
- Proficiency bonus → `Entity.proficiency_bonus`
- Ability modifiers → `Entity.ability_scores`
- Generic attack modifiers → `Equipment.attack_bonus` (Blinded, Poisoned apply here)
- Sorcery points → `ActionEconomy.resources["sorcery_points"]`

**IMPORTANT - Modifier Chain Clarification**:
- Generic attack modifiers (Blinded, Poisoned) → `Equipment.attack_bonus`
- Spell-specific attack modifiers (Wand of War Mage) → `SpellcastingBlock.spell_attack_bonus`
- `Entity.spell_attack_bonus()` COMBINES both!

**No learn/unlearn methods** - spell knowledge managed via Entity action registration:
```python
# Learning a spell = registering an action template
entity.register_action(FireBolt(source_entity_uuid=entity.uuid, template=True))

# Unlearning a spell = unregistering the action
entity.unregister_action("Fire Bolt")
```

#### ActionEconomy (extend) - Resources

**Existing**: actions, bonus_actions, reactions, movement, resources

**Add for Sorcerer**:
```python
entity.action_economy.add_resource("sorcery_points", level, RechargeType.LONG_REST)
```

**NOT adding spell slots here** - they go in SpellcastingBlock.

#### Entity (extend) - Orchestration

**Add fields:**
```python
class Entity(BaseBlock):
    spellcasting: Optional[SpellcastingBlock] = None  # None for non-casters
```

**Add properties for spell knowledge** (source of truth = registered_actions):
```python
@property
def is_spellcaster(self) -> bool:
    return self.spellcasting is not None

@property
def known_spells(self) -> List[SpellAction]:
    """Get all known spells (SpellAction templates in registered_actions)."""
    return [a for a in self.registered_actions if isinstance(a, SpellAction)]

@property
def known_cantrips(self) -> List[SpellAction]:
    """Get all known cantrips."""
    return [s for s in self.known_spells if s.spell_level == 0]

@property
def known_leveled_spells(self) -> List[SpellAction]:
    """Get all known leveled spells."""
    return [s for s in self.known_spells if s.spell_level > 0]

def knows_spell(self, spell_name: str) -> bool:
    """Check if entity knows a spell by name."""
    return any(s.name == spell_name for s in self.known_spells)
```

**Add methods for spell combat:**
```python
def spell_attack_bonus(self, target_entity_uuid: Optional[UUID] = None) -> ModifiableValue:
    """
    Combines prof + ability mod + generic attack bonus + spell bonus.

    CRITICAL: Includes Equipment.attack_bonus for conditions like Blinded/Poisoned!
    """
    if not self.spellcasting:
        raise ValueError(f"{self.name} is not a spellcaster")

    self.set_target_entity(target_entity_uuid)

    proficiency = self.proficiency_bonus
    ability_name = self.spellcasting.spellcasting_ability
    ability_mod = self.ability_scores.get_ability(ability_name).modifier_bonus
    generic_attack = self.equipment.attack_bonus  # Blinded, Poisoned apply here!
    spell_bonus = self.spellcasting.spell_attack_bonus  # Wand of War Mage, etc.

    combined = proficiency.combine_values([ability_mod, generic_attack, spell_bonus])

    self.clear_target_entity()
    return combined

def spell_save_dc(self) -> int:
    """Returns 8 + prof + ability mod + any DC bonuses."""
    if not self.spellcasting:
        raise ValueError(f"{self.name} is not a spellcaster")

    base = 8
    prof = self.proficiency_bonus.normalized_score
    ability_name = self.spellcasting.spellcasting_ability
    ability_mod = self.ability_scores.get_ability(ability_name).modifier
    dc_bonus = self.spellcasting.spell_save_dc_bonus.normalized_score

    return base + prof + ability_mod + dc_bonus
```

**Convenience wrappers for spell slots** (slots live in ActionEconomy):
```python
def has_spell_slot(self, level: int) -> bool:
    """Check if entity has an available spell slot of given level."""
    return self.action_economy.can_afford(f"spell_slot_{level}", 1)

def get_lowest_spell_slot(self, min_level: int) -> Optional[int]:
    """Get lowest available slot >= min_level (for upcasting UI)."""
    for level in range(min_level, 10):
        if self.has_spell_slot(level):
            return level
    return None
```

---

### Attack Modifiers: Revised Design (Post-Feedback)

**IMPORTANT CORRECTION**: After analyzing the existing code, `Equipment.attack_bonus` is semantically a **GENERIC attack modifier** that conditions already expect to apply to ALL attacks.

**Evidence from conditions.py**:
- `Blinded` (line 191): Adds DISADVANTAGE to `equipment.attack_bonus` - RAW says "creature's attack rolls have disadvantage" (ALL attacks)
- `Poisoned` (line 619): Adds DISADVANTAGE to `equipment.attack_bonus` - RAW says "disadvantage on attack rolls" (ALL attacks)
- `Invisible` (line 496): Adds ADVANTAGE to `equipment.attack_bonus` - RAW says "advantage on attack rolls" (ALL attacks)
- `Frightened`, `Prone`, `Restrained`: Same pattern

**If spell attacks DON'T use `Equipment.attack_bonus`**, these conditions would incorrectly NOT affect spell attacks!

**Evidence from Equipment block structure**:
```
Equipment ModifiableValues:
├── attack_bonus         → "Attack Bonus" (GENERIC - all attacks)
├── melee_attack_bonus   → "Melee Attack Bonus" (weapon-specific)
├── ranged_attack_bonus  → "Ranged Attack Bonus" (weapon-specific)
└── damage_bonus         → "Damage Bonus" (GENERIC - all damage)
```

The naming convention already distinguishes generic (`attack_bonus`) from type-specific (`melee_attack_bonus`, `ranged_attack_bonus`).

**Correct Design**:
1. Spell attacks SHOULD include `Equipment.attack_bonus` (for conditions like Blinded/Poisoned)
2. Spell attacks should NOT include `melee_attack_bonus` or `ranged_attack_bonus` (those are weapon-specific)
3. `SpellcastingBlock.spell_attack_bonus` adds SPELL-SPECIFIC modifiers (like Wand of the War Mage)

**Entity.spell_attack_bonus() should combine**:
```python
def spell_attack_bonus(self, target_entity_uuid: Optional[UUID] = None) -> ModifiableValue:
    # Components:
    # 1. Proficiency bonus
    # 2. Spellcasting ability modifier (CHA for Sorcerer)
    # 3. Generic attack bonus (from Equipment.attack_bonus - Blinded etc apply here!)
    # 4. Spell-specific bonus (from SpellcastingBlock.spell_attack_bonus)

    proficiency = self.proficiency_bonus
    ability_mod = self.ability_scores.get_ability(self.spellcasting.spellcasting_ability).modifier_bonus
    generic_attack = self.equipment.attack_bonus  # <-- Conditions like Blinded apply here!
    spell_bonus = self.spellcasting.spell_attack_bonus  # <-- Wand of War Mage etc.

    return proficiency.combine_values([ability_mod, generic_attack, spell_bonus])
```

**This matches D&D RAW**: Blinded gives disadvantage on ALL attack rolls, not just weapon attacks.

---

### Spells as Equipped Objects (Alternative Architecture)

**User suggestion**: Could spells be objects similar to Weapons, with a generic "Cast Spell" action?

**The Pattern**:
```
Weapon is to Attack Action
    as
Spell is to Cast Spell Action
```

**How it would work**:
1. Spells are objects (like `Weapon` class) that define:
   - Range, targets, damage/effects
   - Save type and ability
   - Concentration flag
   - Upcast scaling rules

2. Entity has `known_spells: List[Spell]` (similar to weapon slots)

3. A generic `CastSpell` action:
   - Takes a spell object as parameter
   - Handles common logic: slot consumption, concentration, range validation
   - Delegates the actual effect to the spell object's `apply_effect()` method

**Advantages**:
- Mirrors Equipment/Weapon pattern the user already knows
- Centralized casting logic (DRY)
- Spells can have their own ModifiableValues for bonuses (like magic weapons)
- Easy to implement "spell as item" (scrolls, wands)

**Example structure**:
```python
class Spell(BaseBlock):
    name: str
    level: int  # 0 for cantrips
    school: SpellSchool
    range: Range
    target_type: TargetType
    concentration: bool

    # Each spell defines its effect
    def apply_effect(self, caster: Entity, target: Entity, slot_level: int) -> Event:
        """Spell-specific effect. Override in subclass."""
        raise NotImplementedError

class FireBolt(Spell):
    name: str = "Fire Bolt"
    level: int = 0
    range: Range = Range(type=RangeType.RANGE, normal=120)
    target_type: TargetType = TargetType.ENTITY

    def apply_effect(self, caster: Entity, target: Entity, slot_level: int) -> Event:
        # Spell attack roll
        attack_bonus = caster.spell_attack_bonus(target.uuid)
        ac = target.ac_bonus(caster.uuid)
        # ... roll and damage ...

class CastSpell(BaseAction):
    """Generic spell casting action."""
    spell: Spell  # The spell being cast
    slot_level: Optional[int] = None  # For leveled spells

    def _validate(self, event) -> Event:
        # 1. Check spell is known
        # 2. Check range/LOS
        # 3. Check slot availability (for leveled spells)
        # 4. Check concentration conflicts
        ...

    def _apply(self, event) -> Event:
        # 1. Consume slot (if leveled)
        # 2. Handle concentration (if applicable)
        # 3. Delegate to spell.apply_effect()
        return self.spell.apply_effect(caster, target, self.slot_level)
```

**Decision**: This is cleaner architecture. Spells as objects allows:
- Spell-specific bonuses (like weapon bonuses on magic weapons)
- Scrolls/wands that "contain" a spell object
- Consistent pattern with existing weapon system

---

### Concentration: Simple Design

**What we need**:
1. Track that entity is concentrating (and on what)
2. On damage → CON save or break
3. On new concentration spell → break old one
4. On incapacitated → break

**Implementation**:
```python
class Concentrating(BaseCondition):
    spell_name: str
    spell_effect_uuid: Optional[UUID]  # The condition being maintained

    def _apply(self, event):
        target = Entity.get(self.target_entity_uuid)

        # Break existing concentration
        if "Concentrating" in target.active_conditions:
            target.remove_condition("Concentrating")

        # Register CON save handler
        handler = EventHandler(
            name="Concentration Check",
            trigger_conditions=[Trigger(EventType.TAKE_DAMAGE, EventPhase.EFFECT)],
            event_processor=concentration_check_processor
        )
        target.add_event_handler(handler)

        return [], [handler.uuid], [], effect_event

    def _remove(self, event=None):
        # Cascade: remove the spell effect
        if self.spell_effect_uuid:
            # Find and remove the spell effect condition
            ...
        return super()._remove(event)
```

**How spells use it**:
```python
class HoldPerson(SpellAction):
    def _apply(self, event):
        # ... save check ...
        if not success:
            # Apply Paralyzed with reference
            paralyzed = Paralyzed(...)
            target.add_condition(paralyzed)

            # Apply Concentrating with reference to paralyzed
            concentrating = Concentrating(
                spell_name="Hold Person",
                spell_effect_uuid=paralyzed.uuid,
                source_entity_uuid=caster.uuid,
                target_entity_uuid=caster.uuid  # Caster concentrates!
            )
            caster.add_condition(concentrating)
```

---

### AoE System (LATER - Big Chunk)

**Scope**: Targeting multiple entities in geometric shapes.

**Requires**:
1. GridMap methods for shape queries
2. Direction/targeting UI (which way is the cone facing?)
3. Multi-target damage application
4. Save-for-half pattern

**Deferred to separate implementation phase**.

---

### Summary: What's New vs Reusable

| Component | Status | Notes |
|-----------|--------|-------|
| **Saving Throws** | REUSE | `entity.saving_throw()` works perfectly |
| **Conditions** | REUSE | `add_condition()` with saves |
| **Damage Resistances** | REUSE | `Health.take_damage()` handles |
| **Range/LOS** | REUSE | `validate_range()`, `validate_line_of_sight()` |
| **Modifier Propagation** | REUSE | `set_from_target()` pattern |
| **Resources** | EXTEND | Add spell slots to `ActionEconomy` or new block |
| **Attack Roll** | EXTEND | Add `spell_attack_bonus()` method |
| **Spell DC** | NEW | `spell_save_dc` property/method |
| **AoE Targeting** | NEW | GridMap methods for shapes |
| **Concentration** | NEW | Condition + damage handler |
| **Spell Registry** | NEW | Spell definitions + actions |

---

## SPELLCASTINGBLOCK - MINIMAL GENERIC DESIGN

### Design Principles

1. **Generic for all casters** - Works for Sorcerer, Wizard, Cleric, Warlock, etc.
2. **Follow existing patterns** - Same structure as Equipment, Health, ActionEconomy
3. **Minimal** - Only what's needed for basic spellcasting
4. **Extensible** - Class-specific features added via conditions (like Fighter/Barbarian)

### SpellcastingConfig

```python
class SpellcastingConfig(BaseModel):
    """Configuration for creating a SpellcastingBlock."""

    # Required: which ability powers spells
    spellcasting_ability: AbilityName  # "charisma", "intelligence", "wisdom"

    # Spell slots per level (level -> count)
    # Example for L5 full caster: {1: 4, 2: 3, 3: 2}
    spell_slots: Dict[int, int] = Field(default_factory=dict)

    # Known spells (names)
    cantrips: List[str] = Field(default_factory=list)
    spells: List[str] = Field(default_factory=list)

    # Optional: static modifiers to spell attack/damage/DC
    # (Magic items, feats would add these)
    spell_attack_modifiers: List[Tuple[str, int]] = Field(default_factory=list)
    spell_damage_modifiers: List[Tuple[str, int]] = Field(default_factory=list)
    spell_dc_modifiers: List[Tuple[str, int]] = Field(default_factory=list)
```

### SpellcastingBlock

```python
class SpellcastingBlock(BaseBlock):
    """
    Generic spellcasting block for any caster class.

    Handles:
    - Spell slot tracking (consume, restore, check availability)
    - Spell attack/damage/DC modifiers (for magic items, class features)
    - Known cantrips and spells

    Does NOT handle (Entity's job):
    - Proficiency bonus (Entity.proficiency_bonus)
    - Ability score modifier (Entity.ability_scores)
    - Combining all bonuses into final attack/DC
    """

    name: str = Field(default="Spellcasting")

    # Which ability powers spells
    spellcasting_ability: AbilityName = Field(default="charisma")

    # Spell slots: level (1-9) -> current available
    spell_slots: Dict[int, int] = Field(default_factory=dict)
    max_spell_slots: Dict[int, int] = Field(default_factory=dict)

    # Known/prepared spells
    cantrips: List[str] = Field(default_factory=list)
    spells: List[str] = Field(default_factory=list)

    # Modifiers for spell combat (magic items add here)
    spell_attack_bonus: ModifiableValue = Field(...)  # Default 0
    spell_damage_bonus: ModifiableValue = Field(...)  # Default 0
    spell_dc_bonus: ModifiableValue = Field(...)      # Default 0

    # =========================================================================
    # Spell Slot Management
    # =========================================================================

    def has_slot(self, level: int) -> bool:
        """Check if a spell slot of given level is available."""
        return self.spell_slots.get(level, 0) > 0

    def consume_slot(self, level: int) -> bool:
        """Consume a spell slot. Returns False if none available."""
        if not self.has_slot(level):
            return False
        self.spell_slots[level] -= 1
        return True

    def restore_slot(self, level: int, count: int = 1) -> None:
        """Restore spell slots (for Arcane Recovery, etc.)."""
        current = self.spell_slots.get(level, 0)
        maximum = self.max_spell_slots.get(level, 0)
        self.spell_slots[level] = min(current + count, maximum)

    def restore_all_slots(self) -> None:
        """Restore all spell slots to maximum (long rest)."""
        for level in self.max_spell_slots:
            self.spell_slots[level] = self.max_spell_slots[level]

    def get_lowest_available_slot(self, min_level: int) -> Optional[int]:
        """Get the lowest level slot >= min_level that's available.
        Used for upcasting - find cheapest slot that can cast the spell.
        """
        for level in range(min_level, 10):  # 1-9
            if self.has_slot(level):
                return level
        return None

    def get_slot_count(self, level: int) -> int:
        """Get current slots at a level."""
        return self.spell_slots.get(level, 0)

    def get_max_slot_count(self, level: int) -> int:
        """Get maximum slots at a level."""
        return self.max_spell_slots.get(level, 0)

    # =========================================================================
    # Spell Knowledge
    # =========================================================================

    def knows_cantrip(self, name: str) -> bool:
        """Check if entity knows a cantrip."""
        return name.lower() in [c.lower() for c in self.cantrips]

    def knows_spell(self, name: str) -> bool:
        """Check if entity knows/has prepared a spell."""
        return name.lower() in [s.lower() for s in self.spells]

    def add_cantrip(self, name: str) -> None:
        """Learn a cantrip."""
        if not self.knows_cantrip(name):
            self.cantrips.append(name)

    def add_spell(self, name: str) -> None:
        """Learn/prepare a spell."""
        if not self.knows_spell(name):
            self.spells.append(name)

    def remove_spell(self, name: str) -> None:
        """Forget/unprepare a spell."""
        self.spells = [s for s in self.spells if s.lower() != name.lower()]

    # =========================================================================
    # Factory
    # =========================================================================

    @classmethod
    def create(
        cls,
        source_entity_uuid: UUID,
        config: SpellcastingConfig,
        name: str = "Spellcasting"
    ) -> 'SpellcastingBlock':
        """Create a SpellcastingBlock from config."""

        # Create modifier values
        spell_attack_bonus = ModifiableValue.create(
            source_entity_uuid=source_entity_uuid,
            base_value=0,
            value_name="Spell Attack Bonus"
        )
        for mod_name, mod_value in config.spell_attack_modifiers:
            spell_attack_bonus.self_static.add_value_modifier(
                NumericalModifier.create(source_entity_uuid, mod_name, mod_value)
            )

        spell_damage_bonus = ModifiableValue.create(
            source_entity_uuid=source_entity_uuid,
            base_value=0,
            value_name="Spell Damage Bonus"
        )
        for mod_name, mod_value in config.spell_damage_modifiers:
            spell_damage_bonus.self_static.add_value_modifier(
                NumericalModifier.create(source_entity_uuid, mod_name, mod_value)
            )

        spell_dc_bonus = ModifiableValue.create(
            source_entity_uuid=source_entity_uuid,
            base_value=0,
            value_name="Spell DC Bonus"
        )
        for mod_name, mod_value in config.spell_dc_modifiers:
            spell_dc_bonus.self_static.add_value_modifier(
                NumericalModifier.create(source_entity_uuid, mod_name, mod_value)
            )

        return cls(
            source_entity_uuid=source_entity_uuid,
            name=name,
            spellcasting_ability=config.spellcasting_ability,
            spell_slots=dict(config.spell_slots),
            max_spell_slots=dict(config.spell_slots),  # Start at max
            cantrips=list(config.cantrips),
            spells=list(config.spells),
            spell_attack_bonus=spell_attack_bonus,
            spell_damage_bonus=spell_damage_bonus,
            spell_dc_bonus=spell_dc_bonus
        )
```

### Entity Extensions

```python
# In EntityConfig, add optional:
class EntityConfig(BaseModel):
    # ... existing fields ...
    spellcasting: Optional[SpellcastingConfig] = None

# In Entity class, add:
class Entity(BaseBlock):
    # ... existing fields ...
    spellcasting: Optional[SpellcastingBlock] = None

    @property
    def is_spellcaster(self) -> bool:
        """Check if entity has spellcasting ability."""
        return self.spellcasting is not None

    def spell_attack_bonus(self, target_entity_uuid: Optional[UUID] = None) -> ModifiableValue:
        """
        Get total spell attack bonus: prof + ability mod + GENERIC attack bonus + spell bonus.

        CRITICAL: Includes equipment.attack_bonus so conditions like Blinded/Poisoned apply!
        """
        if not self.spellcasting:
            raise ValueError(f"{self.name} is not a spellcaster")

        should_clear = False
        if target_entity_uuid and target_entity_uuid != self.target_entity_uuid:
            self.set_target_entity(target_entity_uuid)
            should_clear = True

        # Get components
        proficiency = self.proficiency_bonus
        ability_name = self.spellcasting.spellcasting_ability
        ability_mod = self.ability_scores.get_ability(ability_name).modifier_bonus
        generic_attack = self.equipment.attack_bonus  # Blinded, Poisoned, etc.
        spell_bonus = self.spellcasting.spell_attack_bonus  # Wand of War Mage, etc.

        # Combine all four
        combined = proficiency.combine_values([ability_mod, generic_attack, spell_bonus])

        if should_clear:
            self.clear_target_entity()

        return combined

    def spell_save_dc(self) -> int:
        """
        Get spell save DC: 8 + prof + ability mod + dc bonus.
        """
        if not self.spellcasting:
            raise ValueError(f"{self.name} is not a spellcaster")

        base = 8
        prof = self.proficiency_bonus.normalized_score
        ability_name = self.spellcasting.spellcasting_ability
        ability_mod = self.ability_scores.get_ability(ability_name).modifier
        dc_bonus = self.spellcasting.spell_dc_bonus.normalized_score

        return base + prof + ability_mod + dc_bonus

# In Entity.create(), add handling:
if config.spellcasting is not None:
    spellcasting = SpellcastingBlock.create(
        source_entity_uuid=source_entity_uuid,
        config=config.spellcasting
    )
else:
    spellcasting = None
```

### Standard Spell Slot Tables

```python
# Full caster progression (Sorcerer, Wizard, Cleric, Druid, Bard)
FULL_CASTER_SLOTS = {
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

def get_full_caster_slots(level: int) -> Dict[int, int]:
    """Get spell slots for a full caster at given level."""
    return dict(FULL_CASTER_SLOTS.get(level, {}))
```

### Usage Example

```python
from dnd.entity import Entity, EntityConfig
from dnd.blocks.spellcasting import SpellcastingConfig, get_full_caster_slots

# Create a level 5 Sorcerer
config = EntityConfig(
    ability_scores=AbilityScoresConfig(
        charisma=AbilityConfig(ability_score=16),  # +3 mod
        # ... other abilities
    ),
    proficiency_bonus=3,  # Level 5
    spellcasting=SpellcastingConfig(
        spellcasting_ability="charisma",
        spell_slots=get_full_caster_slots(5),  # {1: 4, 2: 3, 3: 2}
        cantrips=["fire_bolt", "ray_of_frost", "light", "mage_hand"],
        spells=["magic_missile", "shield", "scorching_ray", "hold_person"]
    )
)

sorcerer = Entity.create(uuid4(), name="Sorcerer", config=config)

# Check spellcasting
assert sorcerer.is_spellcaster
assert sorcerer.spellcasting.has_slot(1)  # Has 1st level slots
assert sorcerer.spellcasting.has_slot(3)  # Has 3rd level slots
assert not sorcerer.spellcasting.has_slot(4)  # No 4th level slots yet

# Get spell attack bonus (prof + CHA mod + spell bonus)
# = 3 + 3 + 0 = +6
attack = sorcerer.spell_attack_bonus()
assert attack.normalized_score == 6

# Get spell save DC (8 + prof + CHA mod + dc bonus)
# = 8 + 3 + 3 + 0 = 14
dc = sorcerer.spell_save_dc()
assert dc == 14

# Cast a spell
if sorcerer.spellcasting.has_slot(2):
    sorcerer.spellcasting.consume_slot(2)
    # Execute spell effect...

# Long rest
sorcerer.spellcasting.restore_all_slots()
```

---

## SPELL TARGETING & AVAILABLE ACTIONS INTEGRATION

### Current Available Actions System

**How it works**:
1. Entity has `registered_actions: List[BaseAction]` - all templates
2. Properties filter by `target_type`: `entity_actions`, `position_actions`, `self_actions`
3. `get_available_actions()` iterates each category:
   - **SELF actions**: Validate once, no targets (Dash, Dodge)
   - **ENTITY actions**: Loop through `potential_targets` (visible enemies/allies), `pre_validate()` each
   - **POSITION actions**: Loop through `self.senses.paths`, `pre_validate()` each reachable position

**Current TargetType enum**:
```python
class TargetType(str, Enum):
    SELF = "self"          # Dash, Dodge, Disengage
    ENTITY = "entity"      # Attack
    POSITION = "position"  # Move (requires path)
```

---

### All D&D Spell Target Types Analyzed

| D&D Range/Target | Example Spells | Maps To | Notes |
|------------------|----------------|---------|-------|
| **Self** | Mage Armor, Shield, Blade Ward | `SELF` | Already exists, works perfectly |
| **Touch (enemy)** | Shocking Grasp, Inflict Wounds | `ENTITY` | Range ≤ 5ft in `_validate()` |
| **Touch (ally)** | Cure Wounds, Lesser Restoration | `ENTITY` | Range ≤ 5ft + `target_filter="allies"` |
| **Ranged (enemy)** | Fire Bolt, Hold Person | `ENTITY` | `target_filter="enemies"` |
| **Ranged (ally)** | Haste, Invisibility | `ENTITY` | `target_filter="allies"` |
| **Self or Ally** | Mage Armor (RAW), Shield of Faith | `ENTITY` | Include self in potential_targets |
| **Any Creature** | Dispel Magic, Counterspell | `ENTITY` | `target_filter="all"` |
| **Point in Space** | Fireball, Cloudkill | **NEW: `POINT`** | LOS + range, no path needed |
| **Cone from Self** | Burning Hands, Cone of Cold | **NEW: `DIRECTION`** or `POINT` | Direction determines shape |
| **Line from Self** | Lightning Bolt | **NEW: `DIRECTION`** or `POINT` | Direction determines shape |
| **Cube from Self** | Thunderwave | `SELF` + AoE | Centered on caster, pick direction |

---

### Key Insight: Target Filter is AI/UI Helper, NOT a Hard Restriction

**Important clarification**: The `target_filter` is a convenience for UI display and AI decision-making. It is NOT a hard restriction on what's legally targetable!

**Valid edge cases that must work:**
- Fireball your own fire elemental (immune to fire) to damage enemies around it
- Cast a "living bomb" debuff on an ally who runs into enemies
- Heal an enemy (weird but legal in D&D)
- Target yourself with a damaging spell (suicide is valid)

**Current system**: `target_filter` parameter to `get_available_actions()` filters what's SHOWN, not what's VALID.

**For spells**: Each spell has a PREFERRED filter for default display:
- Fire Bolt: show enemies by default (but can target allies)
- Cure Wounds: show allies by default (but can target enemies)
- Hold Person: show enemies by default

```python
class SpellAction(BaseAction):
    # UI/AI hint - what to show by default, NOT a hard restriction
    preferred_target_filter: str = Field(default="enemies")
```

**In get_available_actions()**: Use the preferred filter for display, but the actual spell's `_validate()` only checks:
1. Is target visible? (LOS)
2. Is target in range?
3. Is target a valid creature? (not dead, unless spell allows)

It does NOT check "is target an enemy" - that would prevent valid edge cases.

---

### Touch Spells = Range 5ft (Same as Melee)

Touch spells are simply ENTITY actions with `spell_range=5`. The range validation works exactly like melee attacks:

```python
class ShockingGrasp(SpellAction):
    target_type: TargetType = TargetType.ENTITY
    spell_range: int = 5  # Touch = 5ft, same as melee reach

    def _validate(self, event):
        # Same range check pattern as melee Attack
        distance = caster.senses.get_feet_distance(target.position)
        if distance > self.spell_range:
            return event.cancel("Target out of touch range")
        # ...
```

No new mechanics needed - touch is just "ENTITY with short range".

---

### Position-Based Targeting for AoE (DEFERRED)

**Status**: Deferred until we implement AoE spells (Fireball, Burning Hands, etc.)

**The problem**: Current POSITION targeting requires a walkable path (for Move action). AoE spells need to target any visible position within range, regardless of path.

**Future solution options**:
1. Add targeting MODE to POSITION: `position_mode: "path" | "sight"`
2. Add new TargetType like `RANGED_POSITION` or `VISIBLE_POSITION`
3. Handle AoE differently (not through available_actions enumeration)

**Why defer**:
- Most early spells (Fire Bolt, Magic Missile, Hold Person) are single-target ENTITY
- AoE position enumeration is expensive (100+ valid cells)
- UI for "pick a point" is different from "pick from list"

We'll design this when implementing Fireball/Burning Hands.

---

### Complete Spell Target Type Summary (Current Scope)

**Using existing TargetTypes only** (AoE deferred):

| Spell Type | TargetType | Range | Preferred Filter | Example |
|------------|------------|-------|------------------|---------|
| Self buff | `SELF` | N/A | N/A | Shield, Blade Ward |
| Touch attack | `ENTITY` | 5ft | `"enemies"` | Shocking Grasp |
| Touch buff | `ENTITY` | 5ft | `"allies"` | Cure Wounds |
| Touch (any) | `ENTITY` | 5ft | `"all"` | Mage Armor |
| Ranged attack | `ENTITY` | 30-120ft | `"enemies"` | Fire Bolt, Hold Person |
| Ranged buff | `ENTITY` | 30ft | `"allies"` | Haste, Invisibility |
| Any creature | `ENTITY` | varies | `"all"` | Dispel Magic |

**DEFERRED (needs AoE system)**:

| Spell Type | Notes | Example |
|------------|-------|---------|
| Point AoE | Target visible position, damage area | Fireball |
| Cone from self | Direction selection | Burning Hands |
| Line from self | Direction selection | Lightning Bolt |
| Emanation | Centered on caster | Spirit Guardians |

**Remember**: `preferred_filter` is AI/UI hint only! Any visible, in-range creature is a valid target regardless of faction.

---

### Spells ARE Actions (SpellAction Base Class)

Each spell is its own action subclass. No generic "CastSpell" wrapper needed.

```python
class SpellAction(BaseAction):
    """
    Base class for all spells. Each spell is a subclass with its own _apply().

    Handles common spell logic:
    - Slot validation (via costs)
    - Range/LOS validation (reuses attack patterns)
    - Concentration management

    Subclasses implement _apply() with spell-specific effects.
    """

    # Inherited from BaseAction
    target_type: TargetType
    costs: List[Cost]  # Action cost + spell slot cost

    # Spell identification
    spell_level: int = Field(default=0)  # 0 = cantrip

    # Targeting - reuse existing Range class
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60))
    preferred_target_filter: str = Field(default="enemies")  # AI/UI hint only

    # Mechanics
    concentration: bool = Field(default=False)

    # For tracking upcast level (set when instantiating)
    slot_level_used: Optional[int] = Field(default=None)
```

**Spell Cost Examples:**
```python
class FireBolt(SpellAction):
    """Cantrip - no slot cost."""
    spell_level: int = 0
    costs: List[Cost] = [
        Cost(cost_type="actions", cost=1)
    ]

class MagicMissile(SpellAction):
    """1st level spell."""
    spell_level: int = 1
    costs: List[Cost] = [
        Cost(cost_type="actions", cost=1),
        Cost(cost_type="spell_slot_1", cost=1)
    ]

class HoldPerson(SpellAction):
    """2nd level spell."""
    spell_level: int = 2
    costs: List[Cost] = [
        Cost(cost_type="actions", cost=1),
        Cost(cost_type="spell_slot_2", cost=1)
    ]

class Shield(SpellAction):
    """1st level reaction spell."""
    spell_level: int = 1
    costs: List[Cost] = [
        Cost(cost_type="reactions", cost=1),
        Cost(cost_type="spell_slot_1", cost=1)
    ]

class MistyStep(SpellAction):
    """2nd level bonus action spell."""
    spell_level: int = 2
    costs: List[Cost] = [
        Cost(cost_type="bonus_actions", cost=1),
        Cost(cost_type="spell_slot_2", cost=1)
    ]
```

**Upcasting:**
```python
# To upcast Magic Missile at 3rd level, create instance with higher slot cost:
magic_missile = MagicMissile(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=target.uuid,
    costs=[
        Cost(cost_type="actions", cost=1),
        Cost(cost_type="spell_slot_3", cost=1)  # Using 3rd level slot
    ],
    slot_level_used=3  # Track for damage scaling in _apply()
)
```

---

### Entity Extension for Spells

```python
@property
def spell_actions(self) -> List[BaseAction]:
    """Spell actions (subset of entity/self/point actions that are spells)."""
    return [a for a in self.registered_actions if isinstance(a, SpellAction)]

@property
def point_actions(self) -> List[BaseAction]:
    """Actions that target a point in space (AoE spells)."""
    return [a for a in self.registered_actions if a.target_type == TargetType.POINT]
```

---

### AvailableActionsResult Extension

```python
class AvailableActionsResult(BaseModel):
    # Existing
    entity_actions: List[AvailableActionInfo]
    position_actions: List[AvailableActionInfo]
    self_actions: List[AvailableActionInfo]

    # New for spells
    point_actions: List[AvailableActionInfo]  # AoE spells targeting a point

    @property
    def all_actions(self) -> List[AvailableActionInfo]:
        return self.entity_actions + self.position_actions + self.self_actions + self.point_actions
```

---

### Example: Registering Spell Actions

```python
def setup_sorcerer_spells(entity: Entity):
    """Register spell actions for a sorcerer."""

    # Cantrips (always available, no slot cost)
    entity.register_action(FireBolt(
        source_entity_uuid=entity.uuid,
        template=True,
        target_type=TargetType.ENTITY,
        target_filter="enemies",
        spell_range=120
    ))

    # Touch heal (if multiclass or spell)
    entity.register_action(CureWounds(
        source_entity_uuid=entity.uuid,
        template=True,
        target_type=TargetType.ENTITY,
        target_filter="allies",  # Can only target allies
        spell_range=5  # Touch
    ))

    # AoE spell
    entity.register_action(Fireball(
        source_entity_uuid=entity.uuid,
        template=True,
        target_type=TargetType.POINT,  # Target a point
        spell_range=150,
        aoe_shape=AoEShape.SPHERE,
        aoe_size=20  # 20ft radius
    ))

    # Self or ally buff
    entity.register_action(MageArmor(
        source_entity_uuid=entity.uuid,
        template=True,
        target_type=TargetType.ENTITY,
        target_filter="self_and_allies",  # Can target self or ally
        spell_range=0  # Touch
    ))
```

---

### Changes Required to Entity.get_available_actions()

1. **Add `point_actions` property** filtering by `TargetType.POINT`

2. **Per-action target_filter** instead of global:
```python
for template in self.entity_actions:
    action_filter = getattr(template, 'target_filter', default_target_filter)
    # ... use action_filter instead of global
```

3. **Handle POINT actions** (don't enumerate positions):
```python
# POINT actions - check availability only
for template in self.point_actions:
    can_afford = template.check_costs()
    if can_afford:
        result.point_actions.append(AvailableActionInfo(
            template_name=template.name,
            target_type=TargetType.POINT,
            valid_targets=[],  # Selected during cast
            can_afford=True,
            spell_range=getattr(template, 'spell_range', 60)
        ))
```

4. **Include self in allies** for `"self_and_allies"` filter:
```python
if action_filter == "self_and_allies":
    potential_targets = dict(self.get_visible_allies(include_dead))
    potential_targets[self.uuid] = self.position
```

---

## IMPLEMENTATION CHECKLIST (Updated)

### Phase 1: Spell Slots in ActionEconomy

**Files to modify:**
- [ ] `dnd/blocks/action_economy.py` (EXTEND)
- [ ] `dnd/core/base_actions.py` (EXTEND CostType)

**ActionEconomy tasks:**
- [ ] Add `spell_slot_1` through `spell_slot_9` as ModifiableValues (base=0)
- [ ] Extend `consume()` and `can_afford()` to handle spell slot cost types
- [ ] Add `reset_spell_slot_costs()` for long rest
- [ ] Update `on_long_rest()` to call `reset_spell_slot_costs()`

**CostType extension:**
- [ ] Add `"spell_slot_1"` through `"spell_slot_9"` to CostType Literal

**Test:**
- [ ] Add spell slot modifiers, verify max tracking
- [ ] Consume spell slots, verify cost modifier pattern
- [ ] Long rest, verify slots restored

### Phase 2: SpellcastingBlock (Minimal - No Redundancy)

**Files to create/modify:**
- [ ] `dnd/blocks/spellcasting.py` (NEW)
- [ ] `dnd/entity.py` (EXTEND)

**SpellcastingBlock tasks:**
- [ ] `SpellcastingConfig` class (just spellcasting_ability + modifier configs)
- [ ] `SpellcastingBlock(BaseBlock)` class
- [ ] `spellcasting_ability: AbilityName` field
- [ ] `spell_attack_bonus`, `spell_damage_bonus`, `spell_save_dc_bonus` ModifiableValues
- [ ] `create()` factory classmethod
- [ ] **NO spell knowledge tracking** - that's in Entity.registered_actions

**Entity tasks:**
- [ ] Add `spellcasting: Optional[SpellcastingBlock]` field
- [ ] Add `is_spellcaster` property
- [ ] Add `known_spells`, `known_cantrips`, `known_leveled_spells` properties (filter registered_actions)
- [ ] Add `knows_spell(name)` method
- [ ] Add `spell_attack_bonus()` method (**MUST include Equipment.attack_bonus!**)
- [ ] Add `spell_save_dc()` method
- [ ] Add `has_spell_slot()`, `get_lowest_spell_slot()` convenience methods
- [ ] Update `EntityConfig` with optional `SpellcastingConfig`

**Test:**
- [ ] Create entity with spellcasting
- [ ] Register spell actions, verify `known_spells` property works
- [ ] Verify spell attack bonus includes Equipment.attack_bonus (Blinded test!)
- [ ] Verify spell save DC calculation

### Phase 2: Targeting System Extension (Minimal)

**Files to modify:**
- [ ] `dnd/core/base_actions.py` (add field)
- [ ] `dnd/entity.py` (EXTEND get_available_actions)

**BaseAction/SpellAction fields:**
- [ ] Add `preferred_target_filter: str` field (AI/UI hint, default "enemies")
- [ ] Add `spell_range: int` field for spell actions

**Entity.get_available_actions() changes:**
- [ ] Per-action `preferred_target_filter` support
- [ ] Handle `"self_and_allies"` filter (include self in potential_targets)
- [ ] Handle `"all"` filter properly

**Note**: `preferred_target_filter` is a HINT for UI/AI display, not a hard restriction!
Any visible in-range creature is valid (Fireball on your own fire elemental is legal).

**Test:**
- [ ] Verify preferred_target_filter works per-action
- [ ] Verify self_and_allies includes caster
- [ ] Verify "all" shows all visible creatures

### Phase 3: SpellAction Base Class

**Files to create:**
- [ ] `dnd/spells/__init__.py` (NEW)
- [ ] `dnd/spells/base.py` (NEW)

**SpellAction tasks:**
- [ ] `SpellAction(BaseAction)` base class
- [ ] Range/LOS validation in `_validate()` (reuse attack patterns)
- [ ] Concentration handling in `_apply()` (break existing, apply new)
- [ ] Helper for spell attack roll pattern
- [ ] Helper for spell save pattern
- [ ] `slot_level_used` field for upcast tracking

**SpellEvent tasks:**
- [ ] `SpellEvent(ActionEvent)` class
- [ ] Fields: spell_name, spell_level, slot_level_used, concentration
- [ ] Combat log generation for spells

**Note:** Spell slot costs handled automatically by existing Cost system - no special validation needed!

**Test:**
- [ ] Basic spell attack cantrip (Fire Bolt)
- [ ] Basic leveled spell (Magic Missile)
- [ ] Upcast spell (Magic Missile at 3rd level)

### Phase 4: Concentration System

**Files to modify:**
- [ ] `dnd/conditions.py` (ADD Concentrating condition)

**Concentration tasks:**
- [ ] `Concentrating` condition class
- [ ] CON save handler on TAKE_DAMAGE
- [ ] Auto-break when casting new concentration spell
- [ ] Cascade removal of spell effect when concentration breaks

**Test:**
- [ ] Concentration breaks on damage (failed save)
- [ ] New concentration spell ends old one
- [ ] Spell effect removed when concentration ends

### Phase 5: AoE System (GridMap) - DEFERRED

**Files to modify:**
- [ ] `dnd/core/gridmap.py` (ADD shape queries)

**GridMap methods (when needed):**
- [ ] `get_entities_in_radius(center, radius_feet)`
- [ ] `get_entities_in_cone(origin, direction, length_feet)`
- [ ] `get_entities_in_line(origin, direction, length_feet, width_feet)`
- [ ] `get_entities_in_cube(corner, size_feet)`

### Phase 6: Implement Spells

**Single-target spells (current scope):**
1. Fire Bolt (cantrip, spell attack, ENTITY)
2. Ray of Frost (cantrip, spell attack + slow, ENTITY)
3. Magic Missile (1st, auto-hit force damage, ENTITY)
4. Mage Armor (1st, AC buff, ENTITY with preferred_filter="all")
5. Shield (1st, reaction +5 AC, SELF)
6. Hold Person (2nd, WIS save → Paralyzed, ENTITY, concentration)
7. Scorching Ray (2nd, 3 spell attacks, ENTITY)
8. Invisibility (2nd, buff, ENTITY with preferred_filter="allies", concentration)

**AoE spells (DEFERRED - needs position targeting):**
- Burning Hands (1st, cone)
- Thunderwave (1st, cube)
- Fireball (3rd, sphere)
- Lightning Bolt (3rd, line)
- Cone of Cold (5th, cone)

---

| Component | Status | Notes |
|-----------|--------|-------|
| **Saving Throws** | REUSE | `entity.saving_throw()` works perfectly |
| **Conditions** | REUSE | `add_condition()` with saves |
| **Damage Resistances** | REUSE | `Health.take_damage()` handles |
| **Range/LOS** | REUSE | `validate_range()`, `validate_line_of_sight()` |
| **Modifier Propagation** | REUSE | `set_from_target()` pattern |
| **Generic Attack Modifiers** | REUSE | `Equipment.attack_bonus` for Blinded/Poisoned |
| **ENTITY Targeting** | REUSE | Touch = 5ft range (like melee) |
| **Cost System** | REUSE | Existing `Cost` class for action + slot costs |
| **Spell Slots** | EXTEND | `ActionEconomy.spell_slot_1` through `_9` as ModifiableValues |
| **CostType** | EXTEND | Add `"spell_slot_1"` through `"spell_slot_9"` |
| **Attack Roll** | EXTEND | Add `Entity.spell_attack_bonus()` method |
| **Spell DC** | NEW | `Entity.spell_save_dc()` method |
| **SpellcastingBlock** | NEW | Spell knowledge + spell-specific modifiers |
| **SpellAction** | NEW | Base class for spells (each spell is an action) |
| **Preferred Target Filter** | NEW | AI/UI hint per action (not restriction) |
| **Concentration** | NEW | Condition + damage handler |
| **AoE Position Targeting** | DEFERRED | For Fireball, Burning Hands etc. |
| **AoE GridMap Methods** | DEFERRED | `get_entities_in_radius()` etc. |

---

## Current System Patterns (Reference)

### How Classes Work
Classes are implemented as **collections of conditions** applied to entities:
- Feature conditions grant resources + register actions
- Modifier conditions add static/contextual modifiers
- Event handler conditions react to game events

### Pattern Types Already Implemented

| Pattern | Example | Use For |
|---------|---------|---------|
| Feature + Action | `SecondWindFeature` → `SecondWind` | Activated abilities with resources |
| Static Modifier | `FightingStyleArchery` | Always-on bonuses |
| Contextual Modifier | `FightingStyleDefense` | Conditional bonuses |
| Event Handler | `GreatWeaponFighting` | Dice manipulation |
| Sub-conditions | `Paralyzed` → `Incapacitated` | Composite effects |
| Resource + Recharge | `action_surge` (SHORT_REST) | Limited use abilities |

### Existing Resource System
```python
entity.action_economy.add_resource(
    name="rage",
    maximum=5,
    recharge_type=RechargeType.LONG_REST  # or SHORT_REST, TURN_START, NEVER
)
entity.action_economy.consume_resource("rage", 1)
entity.action_economy.can_afford_resource("rage", 1)
```

---

## Sorcerer-Specific Challenges

### Challenge 1: Spell Slots (Multi-Resource)

**Problem**: Spell slots are 9 separate resources (1st-9th level), not one.

**Current system**: Single resources with `maximum` and `current`.

**Options**:
1. **9 separate resources**: `spell_slot_1`, `spell_slot_2`, ... `spell_slot_9`
   - Pro: Uses existing system
   - Con: Cluttered, harder to manage slot interactions

2. **SpellSlotBlock component**: New block on Entity for spell management
   - Pro: Clean API, can handle upcasting logic
   - Con: More work, new component type

3. **Nested resource structure**: `spell_slots: Dict[int, Resource]`
   - Pro: Single resource name, level-indexed
   - Con: Requires action_economy changes

**Recommended**: Option 2 - New `SpellcastingBlock` component.

```python
# Proposed structure
class SpellcastingBlock(BaseBlock):
    spell_slots: Dict[int, int]  # level -> current slots
    max_spell_slots: Dict[int, int]  # level -> maximum slots

    def has_slot(self, level: int) -> bool
    def consume_slot(self, level: int) -> bool
    def get_available_slot(self, min_level: int) -> Optional[int]  # For upcasting
    def restore_slots(self)  # Long rest
```

### Challenge 2: Spell Attack & Save DC

**Problem**: Need spellcasting ability modifier + proficiency for attacks and DCs.

**Solution**: Add to SpellcastingBlock:
```python
class SpellcastingBlock(BaseBlock):
    spellcasting_ability: AbilityName = "charisma"  # Default for Sorcerer

    @property
    def spell_attack_bonus(self) -> ModifiableValue:
        # proficiency + CHA modifier

    @property
    def spell_save_dc(self) -> ModifiableValue:
        # 8 + proficiency + CHA modifier
```

### Challenge 3: Concentration

**Problem**: Only one concentration spell at a time, breaks on damage (CON save).

**New systems needed**:
1. Track active concentration spell (condition or reference)
2. Event handler for TAKE_DAMAGE to force concentration saves
3. Auto-end concentration when casting new concentration spell

**Implementation**:
```python
class Concentrating(BaseCondition):
    """Tracks concentration on a spell."""
    spell_name: str
    spell_condition_uuid: UUID  # The condition/effect being maintained

    def _apply(self, declaration_event):
        # Register concentration break handler
        handler = create_concentration_handler(self.target_entity_uuid, self.uuid)
        target.add_event_handler(handler)
        return [], [handler.uuid], [], effect_event

def concentration_break_processor(event: TakeDamageEvent, source_entity_uuid: UUID):
    entity = Entity.get(source_entity_uuid)
    damage = event.total_damage
    dc = max(10, damage // 2)

    # Make CON save
    request = entity.create_saving_throw_request(
        target_entity_uuid=source_entity_uuid,
        ability_name="constitution",
        dc=dc
    )
    _, _, success = entity.saving_throw(request)

    if not success:
        # Remove Concentrating condition (cascades to spell effect)
        entity.remove_condition("Concentrating")
```

### Challenge 4: Sorcery Points

**Simple**: Just a resource with LONG_REST recharge.
```python
entity.action_economy.add_resource(
    name="sorcery_points",
    maximum=level,  # Scales with level
    recharge_type=RechargeType.LONG_REST
)
```

### Challenge 5: Metamagic

**Pattern**: Metamagic options are conditions that modify spell casting.

```python
class MetamagicQuickened(BaseCondition):
    """Grants ability to use Quickened Spell metamagic."""
    name: str = "Metamagic: Quickened Spell"

    def _apply(self, declaration_event):
        # Register action for Quickened Spell
        target = Entity.get(self.target_entity_uuid)
        action = QuickenedSpellMetamagic(
            source_entity_uuid=target.uuid,
            template=True
        )
        target.register_action(action)
        return [], [], [], effect_event
```

**Metamagic as spell modifiers**: When casting a spell, optionally apply metamagic that:
- Checks sorcery point cost
- Modifies spell parameters (range, targets, casting time)

### Challenge 6: Area of Effect (AoE)

**Problem**: Need to target multiple entities in shapes (cone, sphere, line, cube).

**Current system**: Actions target single entity or position.

**New systems needed**:
1. AoE shape calculations
2. Multi-target damage application
3. Save-for-half damage pattern

```python
# GridMap additions
def get_entities_in_sphere(center: Tuple[int, int], radius_feet: int) -> List[UUID]
def get_entities_in_cone(origin: Tuple[int, int], direction: Direction, length_feet: int) -> List[UUID]
def get_entities_in_line(origin: Tuple[int, int], direction: Direction, length_feet: int, width_feet: int) -> List[UUID]
def get_entities_in_cube(corner: Tuple[int, int], size_feet: int) -> List[UUID]
```

### Challenge 7: Spell Definitions

**Problem**: Need structured data for 100+ spells.

**Solution**: Spell data model + registry:
```python
class SpellDefinition(BaseModel):
    name: str
    level: int  # 0 for cantrips
    school: SpellSchool
    casting_time: CastingTime  # ACTION, BONUS_ACTION, REACTION, MINUTES, HOURS
    range_type: SpellRangeType  # SELF, TOUCH, RANGED
    range_feet: Optional[int]
    components: List[SpellComponent]  # VERBAL, SOMATIC, MATERIAL
    material_component: Optional[str]
    duration_type: SpellDurationType  # INSTANTANEOUS, ROUNDS, MINUTES, HOURS, CONCENTRATION
    duration_value: Optional[int]
    concentration: bool
    ritual: bool
    description: str
    higher_level: Optional[str]  # Upcasting text

SPELL_REGISTRY: Dict[str, SpellDefinition] = {
    "fireball": SpellDefinition(
        name="Fireball",
        level=3,
        school=SpellSchool.EVOCATION,
        casting_time=CastingTime.ACTION,
        range_type=SpellRangeType.RANGED,
        range_feet=150,
        components=[SpellComponent.VERBAL, SpellComponent.SOMATIC, SpellComponent.MATERIAL],
        material_component="a tiny ball of bat guano and sulfur",
        duration_type=SpellDurationType.INSTANTANEOUS,
        concentration=False,
        ...
    ),
    ...
}
```

---

## Sorcerer Feature Breakdown

### Level 1
- **Spellcasting**: SpellcastingBlock + cantrips + 1st-level spells
- **Sorcerous Origin (Draconic Bloodline)**:
  - Dragon Ancestor: damage type selection, double prof on dragon CHA checks
  - Draconic Resilience: +1 HP/level, AC = 13 + DEX when unarmored

### Level 2
- **Font of Magic**: Sorcery points resource
- **Flexible Casting**: Actions to convert slots ↔ points

### Level 3
- **Metamagic (2 options)**: Choose from 8 options

### Level 4, 8, 12, 16, 19
- **ASI**: Standard ability score improvements

### Level 5
- 3rd-level spells unlocked

### Level 6
- **Elemental Affinity**: +CHA to damage of ancestry type, spend 1 SP for resistance

### Level 7
- 4th-level spells unlocked

### Level 9
- 5th-level spells unlocked

### Level 10
- **Metamagic (+1)**: 3rd option

### Level 11
- 6th-level spells unlocked

### Level 13
- 7th-level spells unlocked

### Level 14
- **Dragon Wings**: Bonus action to gain flying speed

### Level 15
- 8th-level spells unlocked

### Level 17
- **Metamagic (+1)**: 4th option
- 9th-level spells unlocked

### Level 18
- **Draconic Presence**: 5 SP action for 60ft awe/fear aura

### Level 20
- **Sorcerous Restoration**: Regain 4 SP on short rest

---

## Metamagic Options Analysis

| Option | Cost | Effect | Implementation |
|--------|------|--------|----------------|
| Careful Spell | 1 SP | Allies auto-succeed on save | Mark protected entities |
| Distant Spell | 1 SP | Double range (or touch → 30ft) | Modify spell range |
| Empowered Spell | 1 SP | Reroll up to CHA damage dice | DAMAGE_ROLLED handler |
| Extended Spell | 1 SP | Double duration (max 24h) | Modify duration |
| Heightened Spell | 3 SP | One target has disadvantage on save | Apply disadvantage modifier |
| Quickened Spell | 2 SP | Action → bonus action | Change casting cost |
| Subtle Spell | 1 SP | No V/S components | Skip component check |
| Twinned Spell | Spell level SP | Target second creature | Duplicate spell effect |

**Easiest to implement**: Empowered (use GWF pattern), Heightened (modifier), Quickened (cost change)
**Hardest**: Twinned (duplicate effect), Careful (selective AoE)

---

## Spell Implementation Priority

### Phase 1: Core Combat Spells (MVP)
1. **Fire Bolt** (cantrip) - Ranged spell attack, scaling damage
2. **Magic Missile** (1st) - Auto-hit, force damage
3. **Burning Hands** (1st) - Cone AoE, DEX save
4. **Fireball** (3rd) - Sphere AoE, DEX save
5. **Lightning Bolt** (3rd) - Line AoE, DEX save

### Phase 2: Utility & Control
6. **Mage Armor** (1st) - AC buff
7. **Shield** (1st) - Reaction AC buff
8. **Hold Person** (2nd) - WIS save, Paralyzed
9. **Invisibility** (2nd) - Concentration, existing Invisible condition
10. **Fly** (3rd) - Concentration, movement buff

### Phase 3: Advanced
11. **Cone of Cold** (5th) - Cone AoE, CON save
12. **Disintegrate** (6th) - Single target, massive damage
13. **Chain Lightning** (6th) - Multi-target bouncing

### Not Implementing (Too Complex)
- Polymorph (form tracking)
- Dominate Person (NPC control)
- Wish (GM-level reality)
- Time Stop (turn manipulation)
- Any summon spells (entity creation mid-combat)

---

## Cantrip Scaling

Cantrips scale with **character level**, not class level:

| Character Level | Damage Dice |
|-----------------|-------------|
| 1-4 | 1d |
| 5-10 | 2d |
| 11-16 | 3d |
| 17+ | 4d |

```python
def get_cantrip_dice_count(character_level: int) -> int:
    if character_level < 5:
        return 1
    if character_level < 11:
        return 2
    if character_level < 17:
        return 3
    return 4
```

---

## Spell Upcast Scaling

Common patterns:
- **+1dX per level above base**: Burning Hands (+1d6), Fireball (+1d6)
- **+1 target per level**: Hold Person, Magic Missile
- **+duration per level**: Some buffs
- **No scaling**: Some utility spells

```python
def calculate_spell_damage(base_dice: int, dice_size: int, slot_level: int, base_level: int) -> Dice:
    extra_dice = slot_level - base_level
    total_dice = base_dice + extra_dice
    return Dice(count=total_dice, value=dice_size, ...)
```

---

## File Structure Plan

```
dnd/
├── spells/
│   ├── __init__.py
│   ├── base_spell.py          # SpellDefinition, SpellAction base
│   ├── spell_registry.py      # All spell definitions
│   ├── spell_effects.py       # Common effect implementations
│   ├── cantrips.py           # Level 0 spells
│   ├── level_1_spells.py     # 1st level spells
│   ├── level_2_spells.py     # ... etc
│   └── metamagic.py          # Metamagic implementations
├── blocks/
│   └── spellcasting.py       # SpellcastingBlock
├── classes/
│   ├── sorcerer.py           # Sorcerer conditions
│   └── sorcerer_factory.py   # Character factory
```

---

## Questions for User

1. **Concentration system complexity**: Should concentration auto-end spell effects, or should we track manually?

2. **AoE implementation**: Full geometric calculations, or simplified "entities within X squares"?

3. **Spell component tracking**: Do we enforce V/S/M requirements, or skip for simplicity?

4. **Metamagic selection**: Factory config, or dynamic at runtime?

5. **Which subclass first**: Draconic Bloodline (SRD), or skip subclass initially?

6. **Spell list size**: How many spells in initial implementation? (10? 20? All SRD?)

---

## Implementation Order

1. **SpellcastingBlock**: Spell slots, spell attack, spell DC
2. **Base spell infrastructure**: SpellDefinition, SpellAction
3. **Simple cantrips**: Fire Bolt, Ray of Frost
4. **Sorcery Points**: Resource + Flexible Casting
5. **Concentration system**: Condition + handler
6. **AoE system**: GridMap additions
7. **AoE spells**: Burning Hands, Fireball
8. **Metamagic (subset)**: Empowered, Quickened, Heightened
9. **Draconic Bloodline features**: Resilience, Elemental Affinity
10. **Factory**: SorcererConfig, create_sorcerer()

---

## Code Snippets to Adapt

### Fire Bolt (Spell Attack Cantrip)
```python
class FireBolt(SpellAction):
    name: str = "Fire Bolt"
    level: int = 0
    target_type: TargetType = TargetType.ENTITY
    range_feet: int = 120

    def _apply(self, execution_event):
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid)

        # Spell attack roll
        attack_bonus = caster.spellcasting.spell_attack_bonus
        ac = target.ac_bonus(caster.uuid)
        attack_bonus.set_from_target(ac)

        roll = caster.roll_d20(attack_bonus, RollType.SPELL_ATTACK)
        outcome = determine_attack_outcome(roll, ac)

        attack_bonus.reset_from_target()

        if outcome.hit:
            # Scaling damage
            dice_count = get_cantrip_dice_count(caster.level)
            damage = Dice(count=dice_count, value=10, damage_type=DamageType.FIRE)
            damage_roll = damage.roll
            target.health.take_damage(damage_roll.total, DamageType.FIRE)

        return execution_event.phase_to(EventPhase.COMPLETION, ...)
```

### Fireball (AoE Save Spell)
```python
class Fireball(SpellAction):
    name: str = "Fireball"
    level: int = 3
    target_type: TargetType = TargetType.POSITION
    range_feet: int = 150

    def _apply(self, execution_event):
        caster = Entity.get(self.source_entity_uuid)
        target_pos = self.target_position

        # Get entities in 20ft radius sphere
        gridmap = get_map()
        affected = gridmap.get_entities_in_sphere(target_pos, radius_feet=20)

        # Calculate damage (8d6 + upcast)
        slot_level = execution_event.slot_level
        dice_count = 8 + (slot_level - 3)
        damage_dice = Dice(count=dice_count, value=6, damage_type=DamageType.FIRE)
        damage_roll = damage_dice.roll
        full_damage = damage_roll.total
        half_damage = full_damage // 2

        # Each creature makes DEX save
        dc = caster.spellcasting.spell_save_dc.normalized_score
        for entity_uuid in affected:
            entity = Entity.get(entity_uuid)
            request = caster.create_saving_throw_request(
                target_entity_uuid=entity_uuid,
                ability_name="dexterity",
                dc=dc
            )
            _, _, success = entity.saving_throw(request)

            if success:
                entity.health.take_damage(half_damage, DamageType.FIRE)
            else:
                entity.health.take_damage(full_damage, DamageType.FIRE)

        return execution_event.phase_to(EventPhase.COMPLETION, ...)
```

---

## Testing Strategy

1. **Unit tests**: SpellcastingBlock methods
2. **Spell tests**: Each spell in isolation
3. **Integration**: Sorcerer vs Fighter combat
4. **Concentration**: Damage interrupts, multiple concentration attempts
5. **Metamagic**: Each option applied correctly
6. **Upcast**: Damage/effect scaling

Test files:
- `examples/test_spellcasting_block.py`
- `examples/test_fire_bolt.py`
- `examples/test_fireball.py`
- `examples/test_concentration.py`
- `examples/test_metamagic.py`
- `examples/test_sorcerer_factory.py`
- `examples/test_sorcerer_fighter_combat.py`
