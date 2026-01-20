# D&D Engine - Master Implementation Summary

## Current State Assessment

Our engine has a **solid foundation** for tactical combat. The core systems are in place - what's missing is the **orchestration layer** that ties everything together into a proper turn-based encounter.

### What We Have (Strong)

| System | Status | Location |
|--------|--------|----------|
| **Entity/Component Model** | Complete | `entity.py`, `core/base_block.py` |
| **ModifiableValue System** | Complete | `core/values.py` - 6 modifier channels |
| **Ability Scores** | Complete | `blocks/abilities.py` - all 6 with modifiers |
| **Skills** | Complete | `blocks/skills.py` - all 18 with proficiency/expertise |
| **Saving Throws** | Complete | `blocks/saving_throws.py` |
| **Equipment (ARPG-style)** | Complete | `blocks/equipment.py` - 11 slots! |
| **Weapons** | Complete | Damage, properties, finesse, extra damage |
| **Armor** | Complete | AC, types, DEX caps, requirements |
| **Health/HP** | Complete | HP, temp HP, damage, healing, resistances |
| **Action Economy** | Complete | Actions, bonus, reactions, movement + consume/reset |
| **Conditions** | 13/15 SRD | `conditions.py` - missing Exhaustion, Petrified |
| **Attack Action** | Complete | `actions.py` - full flow with validation |
| **Move Action** | Complete | `actions.py` - path following, cost deduction |
| **Opportunity Attacks** | Complete | `reactions.py` |
| **GridMap/Spatial** | Complete | `core/gridmap.py` - positions, FOV, pathfinding |
| **Event System** | Complete | `core/events.py` - full lifecycle, handlers |

### What's Missing (Priority)

| System | Priority | Complexity |
|--------|----------|------------|
| **Turn-Based Combat Manager** | CRITICAL | Medium |
| **Available Actions Query** | CRITICAL | Medium |
| **Perception/Stealth/Hidden** | HIGH | Medium |
| **Interactable Objects** | HIGH | Medium |
| **Traps** | HIGH | Medium |
| **Condition Duration** | HIGH | Easy |
| **Passive Checks** | MEDIUM | Easy |
| **Cover System** | MEDIUM | Medium |
| **Difficult Terrain** | MEDIUM | Easy |
| **Inventory System** | LOW | Medium |

---

## Priority 1: Combat Encounter System

### New Files to Create

```
dnd/
├── encounter.py       # Encounter management (entities in combat)
├── combat.py          # Turn-based combat loop
├── perception.py      # Stealth, hiding, detection
└── interactables.py   # Objects, traps, items on ground
```

### encounter.py - Encounter Management

```python
"""
Manages a tactical combat encounter.
Tracks combatants, initiative, turns, rounds.
"""

class Encounter(BaseModel):
    """A tactical combat encounter."""

    uuid: UUID
    name: str

    # Combatants
    combatants: Dict[UUID, CombatantState]  # entity_uuid -> state

    # Turn order
    initiative_order: List[UUID]  # Sorted by initiative
    current_turn_index: int = 0
    round_number: int = 1

    # State
    active: bool = False
    started_at: Optional[datetime] = None

    @classmethod
    def create(cls, entities: List[Entity], name: str = "Combat") -> 'Encounter':
        """Create encounter, roll initiative, sort combatants."""

    def start(self) -> EncounterStartEvent:
        """Begin the encounter. Roll initiative if not done."""

    def get_current_combatant(self) -> Entity:
        """Get entity whose turn it is."""

    def start_turn(self) -> TurnStartEvent:
        """
        Begin current combatant's turn:
        1. Fire TurnStartEvent
        2. Reset action economy
        3. Update sensory state
        4. Check condition expirations
        5. Death saves if at 0 HP
        """

    def end_turn(self) -> TurnEndEvent:
        """
        End current combatant's turn:
        1. Fire TurnEndEvent
        2. Check end-of-turn effects
        3. Advance to next combatant
        """

    def next_turn(self) -> UUID:
        """Advance to next turn, handle round transitions."""

    def end_encounter(self) -> EncounterEndEvent:
        """End combat, clean up states."""

    def remove_combatant(self, entity_uuid: UUID) -> None:
        """Remove from combat (dead, fled, etc.)"""

    def add_combatant(self, entity: Entity, initiative: Optional[int] = None):
        """Add mid-combat (reinforcements)."""


class CombatantState(BaseModel):
    """Per-combatant state within an encounter."""

    entity_uuid: UUID
    initiative_roll: int
    initiative_bonus: int

    # Turn tracking
    has_acted_this_round: bool = False
    turn_start_time: Optional[datetime] = None

    # Special states
    surprised: bool = False  # Can't act first round
    delaying: bool = False   # Holding turn

    # Concentration tracking (for spells)
    concentrating_on: Optional[UUID] = None
```

### combat.py - Available Actions System

This is **critical for both UI and AI**. Given the current game state, what can an entity do?

```python
"""
Combat action resolution and available action queries.
"""

class ActionType(str, Enum):
    """All possible action types."""
    # Standard Actions
    ATTACK = "attack"
    DASH = "dash"
    DISENGAGE = "disengage"
    DODGE = "dodge"
    HELP = "help"
    HIDE = "hide"
    READY = "ready"
    SEARCH = "search"
    USE_OBJECT = "use_object"

    # Bonus Actions
    TWO_WEAPON_ATTACK = "two_weapon_attack"

    # Movement
    MOVE = "move"
    STAND_UP = "stand_up"
    DROP_PRONE = "drop_prone"

    # Reactions
    OPPORTUNITY_ATTACK = "opportunity_attack"

    # Free Actions
    DROP_ITEM = "drop_item"
    INTERACT_OBJECT = "interact_object"


class AvailableAction(BaseModel):
    """A single action the entity can take."""

    action_type: ActionType
    cost_type: str  # "action", "bonus_action", "reaction", "movement", "free"
    cost_amount: int

    # Targeting
    requires_target: bool = False
    valid_targets: List[UUID] = []  # Entity UUIDs
    valid_positions: List[Tuple[int, int]] = []  # For movement

    # Metadata for UI/AI
    name: str
    description: str
    range: Optional[int] = None

    # Pre-computed outcomes (optional, for AI)
    expected_damage: Optional[float] = None
    hit_chance: Optional[float] = None


def get_available_actions(
    entity: Entity,
    encounter: Encounter
) -> List[AvailableAction]:
    """
    Get all actions available to entity given current state.

    Considers:
    - Action economy (has action, bonus action, reaction, movement?)
    - Conditions (incapacitated can't act, grappled can't move, etc.)
    - Position (who's in range?)
    - Equipment (has weapon? has shield?)
    - Senses (who can they see?)
    - Environment (valid movement positions?)

    Returns list of AvailableAction with valid targets pre-computed.
    """
    actions = []

    # Check action economy
    can_action = entity.action_economy.can_afford("actions", 1)
    can_bonus = entity.action_economy.can_afford("bonus_actions", 1)
    can_react = entity.action_economy.can_afford("reactions", 1)
    remaining_movement = entity.action_economy.movement.normalized_score

    # Check conditions
    is_incapacitated = "Incapacitated" in entity.active_conditions
    is_grappled = "Grappled" in entity.active_conditions
    is_prone = "Prone" in entity.active_conditions
    is_hidden = entity.is_hidden  # Need to add this

    if is_incapacitated:
        return []  # Can't do anything

    # === MOVEMENT ===
    if remaining_movement > 0 and not is_grappled:
        # Get reachable positions from senses
        for pos, path in entity.senses.paths.items():
            cost = len(path) * 5  # 5ft per tile
            if is_prone:
                cost *= 2  # Crawling
            if cost <= remaining_movement:
                actions.append(AvailableAction(
                    action_type=ActionType.MOVE,
                    cost_type="movement",
                    cost_amount=cost,
                    valid_positions=[pos],
                    name=f"Move to {pos}",
                    description=f"Move {cost}ft"
                ))

    # === STAND UP ===
    if is_prone and remaining_movement >= entity.action_economy.movement.base_value // 2:
        actions.append(AvailableAction(
            action_type=ActionType.STAND_UP,
            cost_type="movement",
            cost_amount=entity.action_economy.movement.base_value // 2,
            name="Stand Up",
            description="Use half your movement to stand"
        ))

    # === ATTACK ===
    if can_action:
        weapon = entity.equipment.weapon_main_hand
        if weapon:
            # Get valid targets in range
            valid_targets = []
            for target_uuid, target_pos in entity.senses.entities.items():
                target = Entity.get(target_uuid)
                if target and is_valid_attack_target(entity, target, weapon):
                    valid_targets.append(target_uuid)

            if valid_targets:
                actions.append(AvailableAction(
                    action_type=ActionType.ATTACK,
                    cost_type="action",
                    cost_amount=1,
                    requires_target=True,
                    valid_targets=valid_targets,
                    name=f"Attack with {weapon.name}",
                    description=f"{weapon.dice_numbers}d{weapon.damage_dice} {weapon.damage_type.value}",
                    range=weapon.range.normal
                ))

        # Unarmed strike always available
        # ... similar logic

        # DASH
        actions.append(AvailableAction(
            action_type=ActionType.DASH,
            cost_type="action",
            cost_amount=1,
            name="Dash",
            description=f"Gain {entity.action_economy.movement.base_value}ft extra movement"
        ))

        # DISENGAGE
        actions.append(AvailableAction(
            action_type=ActionType.DISENGAGE,
            cost_type="action",
            cost_amount=1,
            name="Disengage",
            description="Your movement doesn't provoke opportunity attacks"
        ))

        # DODGE
        actions.append(AvailableAction(
            action_type=ActionType.DODGE,
            cost_type="action",
            cost_amount=1,
            name="Dodge",
            description="Attackers have disadvantage, advantage on DEX saves"
        ))

        # HIDE (if not visible to enemies)
        if can_hide(entity, encounter):
            actions.append(AvailableAction(
                action_type=ActionType.HIDE,
                cost_type="action",
                cost_amount=1,
                name="Hide",
                description="Stealth check to become hidden"
            ))

        # HELP
        allies_in_range = get_allies_in_range(entity, encounter, 5)
        if allies_in_range:
            actions.append(AvailableAction(
                action_type=ActionType.HELP,
                cost_type="action",
                cost_amount=1,
                requires_target=True,
                valid_targets=allies_in_range,
                name="Help",
                description="Give ally advantage on next attack or check"
            ))

    # === BONUS ACTIONS ===
    if can_bonus:
        # Two-weapon fighting
        off_hand = entity.equipment.weapon_off_hand
        if (isinstance(off_hand, Weapon) and
            WeaponProperty.LIGHT in off_hand.properties and
            entity_attacked_this_turn(entity, encounter)):
            # ... similar to attack
            pass

    return actions


def is_valid_attack_target(attacker: Entity, target: Entity, weapon: Weapon) -> bool:
    """Check if target is valid for attack."""
    # Check range
    distance = attacker.senses.get_feet_distance(target.senses.position)
    if weapon.range.type == RangeType.REACH:
        if distance > weapon.range.normal:
            return False
    else:  # Ranged
        if distance > weapon.range.long:
            return False

    # Check line of sight
    if target.uuid not in attacker.senses.entities:
        return False

    # Check Charmed (can't attack charmer)
    charmed = attacker.active_conditions.get("Charmed")
    if charmed and charmed.source_entity_uuid == target.uuid:
        return False

    return True
```

### perception.py - Stealth and Detection

```python
"""
Perception, stealth, and hidden state management.
Critical for tactical combat and AI.
"""

class HiddenState(BaseModel):
    """Tracks an entity's hidden status."""

    entity_uuid: UUID
    stealth_roll: int  # Result of Stealth check
    hidden_from: Set[UUID]  # Entities this one is hidden from
    position_when_hidden: Tuple[int, int]

    def is_hidden_from(self, observer_uuid: UUID) -> bool:
        return observer_uuid in self.hidden_from


def calculate_passive_perception(entity: Entity) -> int:
    """
    Passive Perception = 10 + Perception modifier
    +5 if advantage, -5 if disadvantage on Perception
    """
    perception_skill = entity.skill_set.get_skill("perception")
    base = 10 + perception_skill.get_total_bonus().normalized_score

    # Check for advantage/disadvantage on Perception
    if perception_skill.has_advantage():
        base += 5
    elif perception_skill.has_disadvantage():
        base -= 5

    return base


def attempt_hide(entity: Entity, encounter: Encounter) -> HideAttemptEvent:
    """
    Entity attempts to hide.

    Requirements:
    - Must be heavily obscured OR have cover from observer
    - Stealth check vs Passive Perception of observers
    """
    # Check if hiding is possible
    observers = get_hostile_entities(entity, encounter)
    can_hide_from = []

    for observer in observers:
        # Check if entity has cover/obscurement from this observer
        if has_cover_from(entity, observer) or is_heavily_obscured(entity, observer):
            can_hide_from.append(observer.uuid)

    if not can_hide_from:
        return HideAttemptEvent(success=False, reason="No cover or obscurement")

    # Roll Stealth
    stealth_roll = entity.roll_skill("stealth")

    # Compare vs each observer's Passive Perception
    hidden_from = set()
    for observer_uuid in can_hide_from:
        observer = Entity.get(observer_uuid)
        passive_perception = calculate_passive_perception(observer)
        if stealth_roll.total >= passive_perception:
            hidden_from.add(observer_uuid)

    # Create hidden state
    if hidden_from:
        entity.hidden_state = HiddenState(
            entity_uuid=entity.uuid,
            stealth_roll=stealth_roll.total,
            hidden_from=hidden_from,
            position_when_hidden=entity.senses.position
        )
        return HideAttemptEvent(success=True, hidden_from=hidden_from)

    return HideAttemptEvent(success=False, reason="Observers noticed you")


def check_detection(hidden_entity: Entity, observer: Entity) -> bool:
    """
    Check if observer detects hidden entity.

    Called when:
    - Hidden entity moves
    - Hidden entity attacks (auto-reveals)
    - Observer uses Search action
    - Start of observer's turn (passive check)
    """
    if not hidden_entity.hidden_state:
        return True  # Already detected

    if observer.uuid not in hidden_entity.hidden_state.hidden_from:
        return True  # Already detected by this observer

    # Compare Stealth roll to observer's Passive Perception
    passive = calculate_passive_perception(observer)
    if hidden_entity.hidden_state.stealth_roll < passive:
        hidden_entity.hidden_state.hidden_from.discard(observer.uuid)
        return True

    return False


def on_attack_from_hidden(attacker: Entity, target: Entity) -> None:
    """
    When attacking from hidden:
    1. Attacker has advantage (Unseen Attacker)
    2. Attack reveals attacker's location
    """
    # Advantage is handled in attack roll via Invisible-like modifier

    # Reveal attacker
    attacker.hidden_state = None

    # Fire revelation event
    RevealedEvent(entity_uuid=attacker.uuid, reason="attack")
```

### interactables.py - Objects and Traps

```python
"""
Interactable environment objects: destructible objects, traps, items.
"""

class Material(str, Enum):
    CLOTH = "Cloth"      # AC 11
    GLASS = "Glass"      # AC 13
    WOOD = "Wood"        # AC 15
    STONE = "Stone"      # AC 17
    IRON = "Iron"        # AC 19
    MITHRAL = "Mithral"  # AC 21
    ADAMANTINE = "Adamantine"  # AC 23

MATERIAL_AC = {
    Material.CLOTH: 11,
    Material.GLASS: 13,
    Material.WOOD: 15,
    Material.STONE: 17,
    Material.IRON: 19,
    Material.MITHRAL: 21,
    Material.ADAMANTINE: 23,
}


class InteractableObject(BaseBlock):
    """
    A destructible/interactable object in the world.
    Can be attacked, has HP, can be destroyed.
    """

    name: str
    position: Tuple[int, int]

    # Physical properties
    material: Material
    size: Size
    fragile: bool = False

    # Health
    hp: ModifiableValue
    max_hp: int
    damage_threshold: int = 0  # Minimum damage to affect

    # Immunities (objects are immune to poison/psychic)
    immunities: List[DamageType] = Field(
        default_factory=lambda: [DamageType.POISON, DamageType.PSYCHIC]
    )

    # Interaction
    interactable: bool = True  # Can be interacted with
    interaction_dc: Optional[int] = None  # DC to interact (locks, etc.)

    # State
    destroyed: bool = False

    @property
    def ac(self) -> int:
        return MATERIAL_AC[self.material]

    def take_damage(self, damage: int, damage_type: DamageType) -> ObjectDamageEvent:
        """Apply damage to object."""
        if damage_type in self.immunities:
            return ObjectDamageEvent(damage_dealt=0, reason="immune")

        if damage < self.damage_threshold:
            return ObjectDamageEvent(damage_dealt=0, reason="below threshold")

        # Apply damage
        self.hp.base_value = max(0, self.hp.base_value - damage)

        if self.hp.normalized_score <= 0:
            self.destroyed = True
            return ObjectDamageEvent(damage_dealt=damage, destroyed=True)

        return ObjectDamageEvent(damage_dealt=damage)

    @classmethod
    def create_by_size(cls, name: str, position: Tuple[int, int],
                       material: Material, size: Size, fragile: bool = False):
        """Create object with HP based on size."""
        hp_table = {
            Size.TINY: (2, 5),      # fragile, resilient
            Size.SMALL: (3, 10),
            Size.MEDIUM: (4, 18),
            Size.LARGE: (5, 27),
        }
        hp = hp_table[size][0 if fragile else 1]
        return cls(
            name=name, position=position, material=material,
            size=size, fragile=fragile, max_hp=hp,
            hp=ModifiableValue.create(base_value=hp, ...)
        )


class Trap(BaseBlock):
    """
    A trap that can be triggered, detected, and disabled.
    """

    name: str
    position: Tuple[int, int]
    trap_type: Literal["mechanical", "magical"]

    # Detection
    perception_dc: int
    investigation_dc: Optional[int] = None
    arcana_dc: Optional[int] = None  # For magical traps

    # Disabling
    disable_dc: int
    disable_skill: str = "thieves_tools"  # or "arcana" for magical

    # Trigger
    trigger_type: str  # "pressure_plate", "trip_wire", "proximity"
    trigger_weight_lbs: int = 20
    trigger_radius: int = 0  # For proximity traps

    # Effect
    attack_bonus: Optional[int] = None  # For attack traps
    save_ability: Optional[str] = None  # "dexterity", "constitution"
    save_dc: Optional[int] = None
    damage_dice: int = 10
    damage_count: int = 2
    damage_type: DamageType = DamageType.PIERCING
    condition_on_fail: Optional[str] = None

    # State
    detected_by: Set[UUID] = Field(default_factory=set)
    triggered: bool = False
    disabled: bool = False

    def check_trigger(self, entity: Entity) -> bool:
        """Check if entity triggers this trap."""
        if self.triggered or self.disabled:
            return False

        if self.trigger_type == "pressure_plate":
            return entity.senses.position == self.position
        elif self.trigger_type == "proximity":
            distance = calculate_distance(entity.senses.position, self.position)
            return distance <= self.trigger_radius
        elif self.trigger_type == "trip_wire":
            # Check if entity passed through the wire
            pass

        return False

    def activate(self, target: Entity) -> TrapActivationEvent:
        """Trigger the trap."""
        self.triggered = True

        if self.attack_bonus is not None:
            # Attack roll vs target AC
            roll = roll_d20() + self.attack_bonus
            if roll >= target.equipment.ac_bonus.normalized_score:
                damage = roll_damage(self.damage_count, self.damage_dice)
                target.health.take_damage([Damage(...)])
                return TrapActivationEvent(hit=True, damage=damage)
            return TrapActivationEvent(hit=False)

        elif self.save_dc is not None:
            # Saving throw
            success, roll, passed = target.saving_throw(
                SavingThrowRequest(ability=self.save_ability, dc=self.save_dc)
            )
            damage = roll_damage(self.damage_count, self.damage_dice)
            if not passed:
                target.health.take_damage([Damage(...)])
                if self.condition_on_fail:
                    # Apply condition
                    pass
                return TrapActivationEvent(saved=False, damage=damage)
            else:
                # Half damage on save (usually)
                target.health.take_damage([Damage(amount=damage//2, ...)])
                return TrapActivationEvent(saved=True, damage=damage//2)

    def attempt_detect(self, entity: Entity, active: bool = False) -> bool:
        """
        Check if entity detects this trap.
        active=True means Search action, uses Perception or Investigation.
        active=False means passive perception.
        """
        if entity.uuid in self.detected_by:
            return True

        if active:
            # Roll Investigation or Perception
            roll = max(
                entity.roll_skill("perception").total,
                entity.roll_skill("investigation").total
            )
            dc = min(self.perception_dc, self.investigation_dc or 999)
        else:
            # Passive Perception
            roll = calculate_passive_perception(entity)
            dc = self.perception_dc

        if roll >= dc:
            self.detected_by.add(entity.uuid)
            return True
        return False

    def attempt_disable(self, entity: Entity) -> DisableTrapEvent:
        """Attempt to disable the trap."""
        if self.trap_type == "magical":
            # Arcana check or dispel magic
            roll = entity.roll_skill("arcana")
        else:
            # Thieves' tools + DEX
            roll = entity.roll_skill("sleight_of_hand")  # Simplified

        if roll.total >= self.disable_dc:
            self.disabled = True
            return DisableTrapEvent(success=True)
        else:
            # Failure might trigger the trap
            return DisableTrapEvent(success=False, triggered=self.check_trigger(entity))


class GroundItem(BaseModel):
    """An item on the ground that can be picked up."""

    position: Tuple[int, int]
    item: Union[Weapon, Armor, Consumable]  # Item types

    def pickup(self, entity: Entity) -> PickupEvent:
        """Entity picks up the item."""
        # Add to inventory or equip
        pass
```

---

## Integration: Update Sensory State per Turn

The `Senses` block needs to be updated at key moments:

```python
# In Encounter.start_turn():
def start_turn(self) -> TurnStartEvent:
    entity = self.get_current_combatant()

    # 1. Reset action economy
    entity.action_economy.reset_all_costs()

    # 2. Update sensory state
    entity.update_entity_senses(max_distance=60)  # Already exists

    # 3. Check trap detection (passive)
    for trap in self.traps:
        trap.attempt_detect(entity, active=False)

    # 4. Check hidden entities detection
    for combatant_uuid in self.combatants:
        other = Entity.get(combatant_uuid)
        if other.hidden_state:
            check_detection(other, entity)

    # 5. Check condition expirations
    for condition_name, condition in entity.active_conditions.items():
        if condition.should_expire(self.round_number, entity.uuid):
            entity.remove_condition(condition_name)

    # 6. Death saving throw if at 0 HP
    if entity.health.current_hp <= 0 and not entity.is_stable:
        entity.death_saving_throw()

    # 7. Fire event
    return TurnStartEvent(
        entity_uuid=entity.uuid,
        round_number=self.round_number,
        available_actions=get_available_actions(entity, self)
    )
```

---

## Available Actions for UI/AI

The `get_available_actions()` function is the **key interface** for both:

1. **UI**: Show player what they can do, with valid targets highlighted
2. **AI**: Evaluate options and choose actions

```python
# Example usage in UI
actions = get_available_actions(player_entity, encounter)

for action in actions:
    if action.action_type == ActionType.ATTACK:
        # Show attack button, highlight valid targets
        ui.show_attack_option(action.name, action.valid_targets)
    elif action.action_type == ActionType.MOVE:
        # Highlight reachable tiles
        ui.highlight_tiles(action.valid_positions, color="blue")

# Example usage in AI
actions = get_available_actions(ai_entity, encounter)

# Evaluate each action
best_action = None
best_score = -inf

for action in actions:
    score = evaluate_action(action, ai_entity, encounter)
    if score > best_score:
        best_score = score
        best_action = action

# Execute best action
execute_action(best_action, ai_entity, encounter)
```

---

## Implementation Phases

### Phase 1: Core Combat Loop (PRIORITY)
1. Create `encounter.py` with Encounter class
2. Create `combat.py` with `get_available_actions()`
3. Add `initiative` ModifiableValue to Entity
4. Add `TurnStartEvent` / `TurnEndEvent` to events.py
5. Add condition duration tracking

### Phase 2: Perception System
1. Create `perception.py`
2. Add `passive_perception` property to Entity
3. Add `hidden_state` to Entity
4. Implement Hide action
5. Implement Stealth vs Perception checks

### Phase 3: Interactable Environment
1. Create `interactables.py`
2. Implement `InteractableObject` (barrels, doors, etc.)
3. Implement `Trap` class
4. Implement `GroundItem` for loot
5. Add object/trap tracking to Encounter

### Phase 4: Missing Actions
1. Disengage action
2. Help action
3. Search action
4. Use Object action
5. Two-weapon fighting

### Phase 5: Terrain Features
1. Add `difficult` flag to TileData
2. Modify Dijkstra for terrain costs
3. Add cover calculation
4. Add light levels

---

## File Structure After Implementation

```
dnd/
├── core/
│   ├── base_object.py
│   ├── base_block.py
│   ├── base_actions.py
│   ├── base_conditions.py
│   ├── dice.py
│   ├── events.py          # + TurnStartEvent, TurnEndEvent
│   ├── gridmap.py          # + difficult terrain
│   ├── modifiers.py
│   ├── values.py
│   ├── shadowcast.py
│   └── dijkstra.py         # + terrain cost multiplier
│
├── blocks/
│   ├── abilities.py
│   ├── skills.py           # + passive checks
│   ├── saving_throws.py
│   ├── health.py
│   ├── equipment.py
│   ├── action_economy.py
│   └── sensory.py          # + hidden state
│
├── actions.py              # Attack, Move, + new actions
├── conditions.py           # + duration tracking
├── reactions.py
├── entity.py               # + initiative, hidden_state
│
├── encounter.py            # NEW - Encounter management
├── combat.py               # NEW - Available actions
├── perception.py           # NEW - Stealth/detection
└── interactables.py        # NEW - Objects, traps, items
```

---

## Summary

**The engine is 70% complete for tactical combat.** The missing 30% is:

1. **Orchestration** (encounter.py, combat.py) - How turns flow
2. **Information** (available actions) - What can entities do
3. **Environment** (interactables.py) - What's in the world
4. **Stealth** (perception.py) - Hidden information game

The foundation (entities, actions, conditions, spatial, events) is solid. We're building the **game loop** on top of it.
