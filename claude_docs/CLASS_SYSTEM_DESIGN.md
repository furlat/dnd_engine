# Class System Design - Fighter Implementation

## Overview

The class system models D&D character classes as collections of **conditions** applied to entities. This leverages the existing condition system which already supports:
- Static and contextual modifiers on any ModifiableValue
- Event handlers for reactive abilities
- Sub-conditions for composite features
- Duration tracking (permanent, rounds, until rest)
- Clean removal via UUID tracking

**Key Insight**: A class is essentially `Map<Class, Level> → List<Condition>`. Leveling up adds new conditions, respeccing removes class-tagged conditions.

---

## Action System Architecture Analysis

Before designing how class features add new actions (like Second Wind), we need to understand the current action architecture thoroughly.

### Current Architecture: Three Disconnected Layers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SERVER ENDPOINTS                                   │
│  server/event_server.py                                                     │
│                                                                             │
│  @app.post("/action/move")     → manually creates Move(...)                 │
│  @app.post("/action/attack")   → manually creates Attack(...)               │
│  @app.post("/action/dash")     → manually creates Dash(...)                 │
│  @app.post("/action/dodge")    → manually creates Dodge(...)                │
│  @app.post("/action/disengage")→ manually creates Disengage(...)            │
│  @app.post("/action/end-turn") → manages turn flow                          │
│                                                                             │
│  HARDCODED: Each endpoint manually maps action_id → action class            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↑
                    No registry connection - just string matching
                                    ↑
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AVAILABLE ACTIONS QUERY                                │
│  dnd/available_actions.py                                                   │
│                                                                             │
│  get_available_actions(entity) → AvailableActionsResult                     │
│                                                                             │
│  HARDCODED functions:                                                       │
│  - _get_attack_options()   → iterates WeaponSlots, creates AvailableAction  │
│  - _get_movement_options() → queries entity.senses.paths                    │
│  - _get_other_actions()    → hardcoded Dash, Dodge, Disengage               │
│  - _get_prone_actions()    → Stand Up, Drop Prone                           │
│                                                                             │
│  Returns DATA MODELS (AvailableAction), NOT action classes                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↑
                        No connection to action classes
                                    ↑
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ACTION CLASSES                                     │
│  dnd/actions.py                                                             │
│                                                                             │
│  class Move(BaseAction)       - end_position, use_movement_cost             │
│  class Attack(BaseAction)     - target_uuid, weapon_slot                    │
│  class Dash(BaseAction)       - applies Dashing condition                   │
│  class Dodge(BaseAction)      - applies Dodging condition                   │
│  class Disengage(BaseAction)  - applies Disengaging condition               │
│                                                                             │
│  dnd/reactions.py                                                           │
│  - opportunity_attack_processor() - creates Attack with reactions cost      │
│  - EventHandler triggers on MovementEvent                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Complete Action Inventory

| Action | Class | Location | Cost | Parameters | Targets |
|--------|-------|----------|------|------------|---------|
| **Move** | `Move` | actions.py:43 | movement (variable) | `end_position: Tuple[int,int]` | Position |
| **Attack** | `Attack` | actions.py:170 | 1 action (main) / 1 bonus (off-hand) | `target_uuid`, `weapon_slot` | Entity |
| **Dash** | `Dash` | actions.py:524 | 1 action | - | Self |
| **Dodge** | `Dodge` | actions.py:583 | 1 action | - | Self |
| **Disengage** | `Disengage` | actions.py:644 | 1 action | - | Self |
| **Opportunity Attack** | `Attack` | reactions.py:31 | 1 reaction | Same as Attack | Entity |
| *(missing)* Stand Up | - | - | half movement | - | Self |
| *(missing)* Drop Prone | - | - | free | - | Self |
| *(missing)* Unarmed Strike | - | - | 1 action | `target_uuid` | Entity |

### How Weapon Attacks Work

```python
# In available_actions.py:_get_attack_options()

for slot in [WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF,
             WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF]:
    weapon = entity.equipment._get_weapon_by_slot(slot)
    if weapon is None:
        continue

    valid_targets = _get_valid_attack_targets(entity, slot)  # Range check

    # Off-hand = bonus action, main = action
    is_off_hand = slot in (WeaponSlot.MELEE_OFF, WeaponSlot.RANGED_OFF)
    cost_type = "bonus_actions" if is_off_hand else "actions"

    # Return AvailableAction data (NOT Attack class)
    attacks.append(AvailableAction(
        action_id=f"attack_{slot.value.lower()}",  # "attack_melee_main"
        weapon_slot=slot,
        valid_targets=valid_targets,
        cost_type=cost_type,
        ...
    ))
```

**Key insight**: Weapons don't "register" actions. The query system iterates equipment slots and generates `AvailableAction` data on the fly.

### How Server Executes Attacks

```python
# In server/event_server.py:execute_attack()

@app.post("/action/attack")
async def execute_attack(request: AttackRequest):
    entity = validate_session_action(request.session_id, request.entity_uuid)

    # Manual slot parsing from string
    slot_mapping = {
        "melee_main": WeaponSlot.MELEE_MAIN,
        "melee_off": WeaponSlot.MELEE_OFF,
        ...
    }
    slot = slot_mapping[request.weapon_slot]

    # Manually construct Attack instance
    attack = Attack(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=target_uuid,
        weapon_slot=slot,
        name=f"{entity.name} attacks {target.name}"
    )
    event = attack.apply()
    # ... build response
```

**No registry**: The endpoint hardcodes the mapping from weapon_slot string → Attack class construction.

### How Reactions Work

```python
# In reactions.py

def opportunity_attack_processor(event: MovementEvent, source_entity_uuid: UUID):
    """Called when ANY MovementEvent fires in EFFECT phase."""

    reaction_source = Entity.get(source_entity_uuid)  # The potential attacker
    event_source = Entity.get(event.source_entity_uuid)  # The mover

    # Check if mover is leaving reaction_source's threatened area
    threatened = reaction_source.senses.get_threathened_positions()
    if event.start_position in threatened and any(pos not in threatened for pos in event.path):

        # Create Attack with REACTION cost instead of ACTION
        reaction_attack = Attack(
            name="Opportunity Attack",
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=event.source_entity_uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
            costs=[Cost(name="Opportunity Attack Cost",
                       cost_type="reactions", cost=1,
                       evaluator=entity_action_economy_cost_evaluator)]
        )

        if reaction_attack.pre_validate():
            reaction_attack.apply(parent_event=event)
```

**Key pattern**: Reactions are EventHandlers that trigger on specific events and can create/execute actions dynamically.

### What's Missing for Class Features

1. **No Action Registry**: Can't add new actions (like Second Wind) without modifying:
   - `available_actions.py` (hardcoded query)
   - `server/event_server.py` (hardcoded endpoints)

2. **No Action-Entity Association**: Actions are stateless classes instantiated on-demand. There's no "this entity HAS this action" relationship.

3. **No Extension Points**: Conditions can add modifiers and event handlers, but NOT actions.

4. **Missing Actions**: Stand Up, Drop Prone, Unarmed Strike are in the query but have no corresponding action classes.

---

## Proposed Action Registry Design

Keep it simple: **no new wrapper classes**. Use `pre_validate()` from existing action classes, and extend `ActionEconomy` to track ALL resources.

### Design Goals

1. **Minimal changes to existing action classes** - Just add `target_type` field
2. **Simple dictionary registry** - `Dict[str, RegisteredAction]` on Entity (like `active_conditions`)
3. **Unified resource system** - ActionEconomy handles turn-based + limited-use resources
4. **Use `pre_validate()`** - Action instances validate themselves, no duplicate logic
5. **Follow Entity patterns** - Similar to how conditions are managed

---

### TargetType Enum

```python
# dnd/core/base_actions.py

class TargetType(str, Enum):
    SELF = "self"          # Dash, Dodge, Disengage, Second Wind
    ENTITY = "entity"      # Attack
    POSITION = "position"  # Move
```

### Add target_type to BaseAction

```python
class BaseAction(BaseObject):
    # Existing fields
    name: str
    description: str
    costs: List[Cost]

    # NEW: declare what kind of target this action needs
    target_type: TargetType = Field(default=TargetType.SELF)
```

Subclasses set their target_type:

```python
class Attack(BaseAction):
    target_type: TargetType = Field(default=TargetType.ENTITY)
    weapon_slot: WeaponSlot
    # ... rest unchanged

class Move(BaseAction):
    target_type: TargetType = Field(default=TargetType.POSITION)
    end_position: Tuple[int, int]
    # ... rest unchanged

class Dash(BaseAction):
    target_type: TargetType = Field(default=TargetType.SELF)
    # ... rest unchanged
```

---

### Extended Resource System (ActionEconomy)

The current `ActionEconomy` handles turn-based resources:
- `actions`, `bonus_actions`, `reactions`, `movement`

Extend it to also track **limited-use resources** that recharge on rest or other triggers.

#### RechargeType Enum

```python
# dnd/blocks/action_economy.py

class RechargeType(str, Enum):
    TURN_START = "turn_start"      # Recharge at start of turn (action economy)
    TURN_END = "turn_end"          # Recharge at end of turn
    SHORT_REST = "short_rest"      # Recharge on short rest
    LONG_REST = "long_rest"        # Recharge on long rest
    NEVER = "never"                # Never recharges (single use)
```

#### Resource Model

```python
# dnd/blocks/action_economy.py

class Resource(BaseModel):
    """A limited-use resource (spell slots, Second Wind, Action Surge, etc.)."""
    name: str = Field(description="Resource name: 'second_wind', 'action_surge', 'spell_slot_1'")
    current: int = Field(description="Current available uses")
    maximum: int = Field(description="Maximum uses")
    recharge_type: RechargeType = Field(description="When this resource recharges")

    def can_afford(self, amount: int = 1) -> bool:
        return self.current >= amount

    def consume(self, amount: int = 1) -> bool:
        if not self.can_afford(amount):
            return False
        self.current -= amount
        return True

    def recharge(self, trigger: RechargeType) -> None:
        """Recharge if trigger matches (long_rest also triggers short_rest)."""
        if self.recharge_type == trigger:
            self.current = self.maximum
        elif trigger == RechargeType.LONG_REST and self.recharge_type == RechargeType.SHORT_REST:
            self.current = self.maximum
```

#### Extended ActionEconomy

```python
class ActionEconomy(BaseBlock):
    # Existing turn-based resources
    actions: ModifiableValue
    bonus_actions: ModifiableValue
    reactions: ModifiableValue
    movement: ModifiableValue

    # NEW: Limited-use resources
    resources: Dict[str, Resource] = Field(default_factory=dict)

    # --- Resource management ---

    def add_resource(self, name: str, maximum: int, recharge_type: RechargeType) -> None:
        """Add a limited-use resource (e.g., 'second_wind', 'action_surge')."""
        self.resources[name] = Resource(
            name=name,
            current=maximum,
            maximum=maximum,
            recharge_type=recharge_type
        )

    def remove_resource(self, name: str) -> None:
        """Remove a resource."""
        self.resources.pop(name, None)

    def get_resource(self, name: str) -> Optional[Resource]:
        return self.resources.get(name)

    def can_afford_resource(self, name: str, amount: int = 1) -> bool:
        resource = self.resources.get(name)
        if resource is None:
            return False
        return resource.can_afford(amount)

    def consume_resource(self, name: str, amount: int = 1) -> bool:
        resource = self.resources.get(name)
        if resource is None:
            return False
        return resource.consume(amount)

    # --- Recharge triggers ---

    def on_short_rest(self) -> None:
        """Recharge resources on short rest."""
        for resource in self.resources.values():
            resource.recharge(RechargeType.SHORT_REST)

    def on_long_rest(self) -> None:
        """Recharge resources on long rest."""
        for resource in self.resources.values():
            resource.recharge(RechargeType.LONG_REST)

    def on_turn_start(self) -> None:
        """Reset turn-based resources + recharge turn_start resources."""
        self.reset_all_costs()  # Existing method
        for resource in self.resources.values():
            resource.recharge(RechargeType.TURN_START)

    def on_turn_end(self) -> None:
        """Recharge turn_end resources."""
        for resource in self.resources.values():
            resource.recharge(RechargeType.TURN_END)
```

---

### Cost System Extension

Actions need to declare **what resources they consume** (not just action economy).

#### ActionCost Model

```python
# dnd/core/base_actions.py

class ActionCost(BaseModel):
    """A cost for an action - can be turn-based OR resource-based."""

    # Turn-based cost (existing pattern)
    cost_type: Optional[CostType] = Field(default=None, description="'actions', 'bonus_actions', 'reactions', 'movement'")
    cost_amount: int = Field(default=0)

    # Resource-based cost (new)
    resource_name: Optional[str] = Field(default=None, description="Name of limited-use resource")
    resource_amount: int = Field(default=0)

    def is_turn_based(self) -> bool:
        return self.cost_type is not None and self.cost_amount > 0

    def is_resource_based(self) -> bool:
        return self.resource_name is not None and self.resource_amount > 0
```

#### Cost Validation in BaseAction

```python
class BaseAction(BaseObject):
    costs: List[ActionCost] = Field(default_factory=list)

    def check_all_costs(self, entity: Entity) -> bool:
        """Check if entity can afford ALL costs (turn-based + resources)."""
        for cost in self.costs:
            if cost.is_turn_based():
                if not entity.action_economy.can_afford(cost.cost_type, cost.cost_amount):
                    return False
            if cost.is_resource_based():
                if not entity.action_economy.can_afford_resource(cost.resource_name, cost.resource_amount):
                    return False
        return True

    def apply_all_costs(self, entity: Entity) -> None:
        """Apply ALL costs after action completes."""
        for cost in self.costs:
            if cost.is_turn_based():
                entity.action_economy.consume(cost.cost_type, cost.cost_amount)
            if cost.is_resource_based():
                entity.action_economy.consume_resource(cost.resource_name, cost.resource_amount)
```

---

### Action Registry on Entity

Follow the `active_conditions` pattern but for actions.

#### RegisteredAction Model

```python
# dnd/entity.py or dnd/core/base_actions.py

class RegisteredAction(BaseModel):
    """An action registered on an entity."""
    action_id: str = Field(description="Unique identifier: 'attack_melee_main', 'dash', 'second_wind'")
    action_class: Type[BaseAction] = Field(description="The action class to instantiate")
    config: Dict[str, Any] = Field(default_factory=dict, description="Default kwargs for the action")
    # NOTE: No source_condition_uuid needed - conditions track their own action_ids
    # and BaseCondition._remove() handles cleanup automatically
```

#### Entity Action Registry

```python
class Entity(BaseBlock):
    # Existing blocks
    ability_scores: AbilityScores
    action_economy: ActionEconomy
    active_conditions: Dict[str, BaseCondition]
    # ...

    # NEW: Action registry (like active_conditions)
    registered_actions: Dict[str, RegisteredAction] = Field(default_factory=dict)

    # --- Action management ---

    def register_action(
        self,
        action_id: str,
        action_class: Type[BaseAction],
        config: Optional[Dict] = None
    ) -> None:
        """Register an action on this entity."""
        self.registered_actions[action_id] = RegisteredAction(
            action_id=action_id,
            action_class=action_class,
            config=config or {}
        )

    def unregister_action(self, action_id: str) -> None:
        """Unregister an action."""
        self.registered_actions.pop(action_id, None)

    def get_registered_action(self, action_id: str) -> Optional[RegisteredAction]:
        return self.registered_actions.get(action_id)

    # NOTE: No unregister_actions_by_condition() needed
    # Conditions track their own action_ids and BaseCondition._remove() calls
    # unregister_action() for each one automatically
```

---

### Available Actions Flow (Using pre_validate)

The key insight: **create action instances with each potential target, call `pre_validate()`, collect valid ones.**

#### Target-Finding Methods

```python
class Entity:
    def get_potential_targets(self, target_type: TargetType, action_config: Dict) -> List[Any]:
        """Get potential targets based on target_type."""
        if target_type == TargetType.SELF:
            return [None]  # Self-targeted, no target needed

        elif target_type == TargetType.ENTITY:
            # Get range from config (e.g., weapon range for attacks)
            max_range = action_config.get("max_range", 5)
            weapon_slot = action_config.get("weapon_slot")
            if weapon_slot:
                weapon = self.equipment._get_weapon_by_slot(weapon_slot)
                if weapon:
                    max_range = weapon.range.long if weapon.range.long else weapon.range.normal

            targets = []
            for uuid, pos in self.senses.entities.items():
                if uuid == self.uuid:
                    continue
                if self.senses.get_feet_distance(pos) <= max_range:
                    targets.append(uuid)
            return targets

        elif target_type == TargetType.POSITION:
            remaining = self.action_economy.movement.normalized_score
            is_prone = "Prone" in self.active_conditions
            multiplier = 2 if is_prone else 1

            positions = []
            for pos, path in self.senses.paths.items():
                cost = len(path) * 5 * multiplier
                if cost <= remaining and pos != self.senses.position:
                    positions.append(pos)
            return positions

        return []
```

#### Create Action Instance (Factory)

```python
class Entity:
    def create_action_instance(
        self,
        registered: RegisteredAction,
        target: Any = None
    ) -> BaseAction:
        """Create an action instance with the given target."""
        kwargs = {
            "source_entity_uuid": self.uuid,
            **registered.config
        }

        target_type = registered.action_class.model_fields.get("target_type")
        if target_type:
            target_type_value = target_type.default
            if target_type_value == TargetType.ENTITY and target is not None:
                kwargs["target_entity_uuid"] = target
            elif target_type_value == TargetType.POSITION and target is not None:
                kwargs["end_position"] = target

        return registered.action_class(**kwargs)
```

#### Get Available Actions (Main Query)

```python
def get_available_actions(entity: Entity) -> AvailableActionsResult:
    """Query available actions using pre_validate()."""

    can_act, can_move, blocking = _get_blocking_conditions(entity)
    result = AvailableActionsResult(entity_uuid=entity.uuid, blocking_conditions=blocking)

    for action_id, registered in entity.registered_actions.items():
        action_class = registered.action_class
        config = registered.config

        # Get target_type from the action class
        target_type_field = action_class.model_fields.get("target_type")
        target_type = target_type_field.default if target_type_field else TargetType.SELF

        # Get potential targets
        potential_targets = entity.get_potential_targets(target_type, config)

        # Validate each potential target using pre_validate()
        valid_targets = []
        valid_positions = []

        for target in potential_targets:
            action_instance = entity.create_action_instance(registered, target)

            if action_instance.pre_validate():
                if target_type == TargetType.ENTITY:
                    valid_targets.append(target)
                elif target_type == TargetType.POSITION:
                    valid_positions.append(target)

        # Check if at least one valid target/self
        can_afford = False
        if target_type == TargetType.SELF:
            # For self-targeted, create one instance and validate
            action_instance = entity.create_action_instance(registered, None)
            can_afford = action_instance.pre_validate()
        else:
            can_afford = len(valid_targets) > 0 or len(valid_positions) > 0

        # Apply blocking conditions
        if target_type != TargetType.POSITION and not can_act:
            can_afford = False
        if target_type == TargetType.POSITION and not can_move:
            can_afford = False

        # Build AvailableAction
        available = AvailableAction(
            action_id=action_id,
            name=_get_action_name(action_class, config, entity),
            description=_get_action_description(action_class, config, entity),
            cost_type=_get_primary_cost_type(action_class),
            cost_amount=1,
            can_afford=can_afford,
            requires_target=(target_type == TargetType.ENTITY),
            valid_targets=valid_targets,
            valid_positions=valid_positions,
            category=_target_type_to_category(target_type),
            weapon_slot=config.get("weapon_slot")
        )

        _add_to_result(result, action_id, available)

    return result
```

#### Execute Chosen Action

```python
class Entity:
    def execute_action(self, action_id: str, target: Any = None) -> Optional[Event]:
        """Execute a registered action with the chosen target."""
        registered = self.get_registered_action(action_id)
        if not registered:
            return None

        action_instance = self.create_action_instance(registered, target)
        return action_instance.apply()
```

---

### Default Actions Registration

```python
def register_default_actions(entity: Entity) -> None:
    """Register standard D&D actions every entity has."""

    # Movement
    entity.register_action("move", Move, {})

    # Standard actions (self-targeted)
    entity.register_action("dash", Dash, {})
    entity.register_action("dodge", Dodge, {})
    entity.register_action("disengage", Disengage, {})


def register_weapon_attacks(entity: Entity) -> None:
    """Register attack actions based on equipped weapons."""

    for slot in WeaponSlot:
        weapon = entity.equipment._get_weapon_by_slot(slot)
        if not weapon:
            continue

        entity.register_action(
            f"attack_{slot.value.lower()}",
            Attack,
            {"weapon_slot": slot}
        )
```

---

### Condition Registering an Action (Second Wind Example)

**Pattern**: Conditions return registered action IDs and resource names in `_apply()`, just like they return sub-condition UUIDs. The base class handles automatic cleanup on removal.

#### Updated `_apply()` Return Signature

```python
# dnd/core/base_conditions.py

def _apply(self, declaration_event: Event) -> Tuple[
    List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
    List[UUID],               # event_handler_uuids
    List[UUID],               # subcondition_uuids
    List[str],                # NEW: registered_action_ids
    List[str],                # NEW: registered_resource_names
    Optional[Event]           # completion event
]:
```

#### BaseCondition Tracks and Auto-Cleans

```python
class BaseCondition(BaseObject):
    # Existing tracking
    modifier_uuids: List[Tuple[UUID, UUID]] = Field(default_factory=list)
    event_handler_uuids: List[UUID] = Field(default_factory=list)
    subcondition_uuids: List[UUID] = Field(default_factory=list)

    # NEW: Track registered actions and resources
    registered_action_ids: List[str] = Field(default_factory=list)
    registered_resource_names: List[str] = Field(default_factory=list)

    def apply(self, declaration_event: Event) -> Optional[Event]:
        # ... existing logic ...

        (modifier_pairs, handler_uuids, subcond_uuids,
         action_ids, resource_names, completion_event) = self._apply(declaration_event)

        self.modifier_uuids = modifier_pairs
        self.event_handler_uuids = handler_uuids
        self.subcondition_uuids = subcond_uuids
        self.registered_action_ids = action_ids      # NEW
        self.registered_resource_names = resource_names  # NEW

        return completion_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        target = Entity.get(self.target_entity_uuid)

        # Existing cleanup: modifiers, handlers, sub-conditions...

        # NEW: Auto-cleanup registered actions
        for action_id in self.registered_action_ids:
            target.unregister_action(action_id)

        # NEW: Auto-cleanup registered resources
        for resource_name in self.registered_resource_names:
            target.action_economy.remove_resource(resource_name)

        return event
```

#### SecondWind Example (Clean Pattern)

```python
class SecondWind(BaseCondition):
    name: str = "Second Wind"
    tags: List[str] = Field(default=["class:fighter", "level:1"])
    fighter_level: int = Field(default=1)

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID],
        List[str], List[str], Optional[Event]
    ]:
        target = Entity.get(self.target_entity_uuid)

        # Track what we register
        registered_actions: List[str] = []
        registered_resources: List[str] = []

        # Add the resource to action economy
        target.action_economy.add_resource(
            name="second_wind",
            maximum=1,
            recharge_type=RechargeType.SHORT_REST
        )
        registered_resources.append("second_wind")

        # Register the action
        target.register_action(
            action_id="second_wind",
            action_class=SecondWindAction,
            config={"fighter_level": self.fighter_level}
        )
        registered_actions.append("second_wind")

        effect_event = declaration_event.phase_to(EventPhase.EFFECT, ...)

        # Return all tracked items - base class handles cleanup automatically
        return [], [], [], registered_actions, registered_resources, effect_event

    # No need to override _remove() - base class handles cleanup!
```

**Benefits**:
- Consistent with sub-conditions pattern
- No need to override `_remove()` for cleanup
- Base class guarantees cleanup happens
- Condition just declares what it registered, base class handles the rest


class SecondWindAction(BaseAction):
    """Heal 1d10 + fighter level as a bonus action."""
    name: str = Field(default="Second Wind")
    target_type: TargetType = Field(default=TargetType.SELF)
    fighter_level: int = Field(default=1)

    # Costs: 1 bonus action + 1 second_wind resource
    costs: List[ActionCost] = Field(default_factory=lambda: [
        ActionCost(cost_type="bonus_actions", cost_amount=1),
        ActionCost(resource_name="second_wind", resource_amount=1)
    ])

    def _validate(self, declaration_event):
        entity = Entity.get(self.source_entity_uuid)

        # Cost checking is done by pre_validate() -> check_all_costs()
        # Here we can add action-specific validation if needed

        return declaration_event.phase_to(EventPhase.EXECUTION)

    def _apply(self, execution_event):
        entity = Entity.get(self.source_entity_uuid)

        # Roll healing: 1d10 + fighter level
        healing = DiceRoll.roll(1, 10) + self.fighter_level
        entity.health.heal(healing)

        effect_event = execution_event.phase_to(EventPhase.EFFECT, status_message=f"Healed {healing} HP")
        return effect_event.phase_to(EventPhase.COMPLETION)

    def _apply_costs(self, completion_event):
        entity = Entity.get(self.source_entity_uuid)
        self.apply_all_costs(entity)  # Uses the new unified cost method
        return completion_event
```

---

### Summary

| Component | What It Does |
|-----------|--------------|
| `TargetType` enum | SELF, ENTITY, POSITION - declares what target an action needs |
| `RechargeType` enum | TURN_START, SHORT_REST, LONG_REST, etc. - when resources recharge |
| `Resource` model | Tracks limited-use resources (current, max, recharge_type) |
| `ActionCost` model | Unified cost - can be turn-based OR resource-based |
| `RegisteredAction` model | Links action_id to action class + config + source condition |
| `ActionEconomy.resources` | Dict of limited-use resources |
| `Entity.registered_actions` | Dict of actions this entity can perform |
| `Entity.create_action_instance()` | Factory method to create action with target |
| `Entity.execute_action()` | Execute a registered action |
| `pre_validate()` | Check if action is valid without side effects |
| `get_available_actions()` | Iterate registry, use `pre_validate()` per target |

**Key patterns**:
- Resources live in `ActionEconomy` (extended to handle all resource types)
- Actions are registered on `Entity` (like conditions)
- Validation uses `pre_validate()` - no duplicate logic
- Costs are unified: turn-based + resource-based in same model
- Conditions register actions AND resources together

---

## Design Decisions Summary

### 1. Hit Dice Tagging (Future)

**Problem**: `HitDice` blocks need to track their source for multiclassing.

**Solution**: Add `source_tag` field to `HitDice` with convention like `"class:fighter:1"`. Not required for initial Fighter implementation.

### 2. Action Association with Entities ✓ DESIGNED

**Solution**: `Entity.registered_actions: Dict[str, RegisteredAction]` following the `active_conditions` pattern.

Key components:
- `RegisteredAction` model: links `action_id` → `action_class` + `config`
- `Entity.register_action()` / `unregister_action()` methods
- `Entity.create_action_instance(registered, target)` factory method
- `Entity.execute_action(action_id, target)` for execution
- **Conditions return registered action IDs in `_apply()` return tuple** (like sub-conditions)
- **BaseCondition auto-cleans actions in `_remove()`** - no override needed

### 3. Resource System ✓ DESIGNED

**Solution**: Extend `ActionEconomy` to handle ALL resource types.

Key components:
- `RechargeType` enum: `TURN_START`, `SHORT_REST`, `LONG_REST`, `NEVER`
- `Resource` model: `current`, `maximum`, `recharge_type`
- `ActionEconomy.resources: Dict[str, Resource]`
- `ActionEconomy.add_resource()` / `remove_resource()` / `consume_resource()`
- `ActionEconomy.on_short_rest()` / `on_long_rest()` triggers

Resources live in `ActionEconomy`, NOT on conditions. Conditions register their resources when applied.

### 4. Cost System ✓ DESIGNED

**Solution**: Unified `ActionCost` model that handles both turn-based AND resource-based costs.

```python
class ActionCost(BaseModel):
    cost_type: Optional[CostType] = None      # Turn-based: "actions", "bonus_actions", etc.
    cost_amount: int = 0
    resource_name: Optional[str] = None       # Resource-based: "second_wind", "spell_slot_1"
    resource_amount: int = 0
```

Actions declare their costs, `pre_validate()` checks them, `_apply_costs()` consumes them.

### 5. Available Actions Query ✓ DESIGNED

**Solution**: Use `pre_validate()` to validate each action with each potential target.

Flow:
1. Iterate `entity.registered_actions`
2. For each action, get potential targets based on `target_type`
3. Create action instance for each target
4. Call `pre_validate()` - returns `True` if action is valid
5. Collect valid targets
6. Return `AvailableActionsResult` with valid actions + targets

---

## Tagging Mechanism for Class Conditions

### Proposal: Add `tags` field to BaseCondition

```python
class BaseCondition(BaseObject):
    # ... existing fields ...
    tags: List[str] = Field(default_factory=list, description="Tags for categorizing conditions (e.g., 'class:fighter', 'level:1')")
```

### Tag Format Convention

```
class:<class_name>           # e.g., "class:fighter"
level:<level>                # e.g., "level:1"
feature:<feature_name>       # e.g., "feature:fighting_style"
subfeature:<name>            # e.g., "subfeature:defense"
archetype:<archetype_name>   # e.g., "archetype:champion"
```

### Example Tags for Fighter Level 1

```python
FightingStyleDefense(
    tags=["class:fighter", "level:1", "feature:fighting_style", "subfeature:defense"]
)

SecondWind(
    tags=["class:fighter", "level:1", "feature:second_wind"]
)
```

### Entity Methods for Class Management

```python
# In Entity class
def get_conditions_by_tag(self, tag: str) -> List[BaseCondition]:
    """Get all conditions with a specific tag."""

def remove_conditions_by_tag(self, tag: str) -> int:
    """Remove all conditions with a specific tag. Returns count removed."""

def get_class_level(self, class_name: str) -> int:
    """Get highest level tag for a class."""
```

---

## Fighter Level 1 Features

### 1. Fighting Style (choose one)

| Style | Effect | Implementation |
|-------|--------|----------------|
| **Archery** | +2 to ranged attack rolls | Static modifier on ranged attack bonus |
| **Defense** | +1 AC when wearing armor | Contextual modifier on AC (checks armor equipped) |
| **Dueling** | +2 damage with single melee weapon | Contextual modifier on damage (checks weapon slots) |
| **Great Weapon Fighting** | Reroll 1s and 2s on damage | Event handler on damage rolls (complex) |
| **Protection** | Reaction to impose disadvantage | New action + reaction consumption |
| **Two-Weapon Fighting** | Add ability mod to off-hand damage | Contextual modifier on off-hand damage |

### 2. Second Wind

**Effect**: Bonus action to heal 1d10 + fighter level, once per short/long rest.

**Implementation**:
- **Condition**: `SecondWind` condition tracks usage (via `uses_remaining` field)
- **Action**: `SecondWindAction` consumes bonus action, rolls healing
- **Resource Reset**: Condition's `short_rest()` / `long_rest()` methods reset uses

---

## Implementation Plan

### Phase 0: Resource System + Action Registry Infrastructure

Extend ActionEconomy with resources, add action registry to Entity, add TargetType to actions.

#### Step 0.1: Resource System in ActionEconomy

**File**: `dnd/blocks/action_economy.py`

```python
# Add RechargeType enum
class RechargeType(str, Enum):
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    SHORT_REST = "short_rest"
    LONG_REST = "long_rest"
    NEVER = "never"

# Add Resource model
class Resource(BaseModel):
    name: str
    current: int
    maximum: int
    recharge_type: RechargeType

    def can_afford(self, amount: int = 1) -> bool: ...
    def consume(self, amount: int = 1) -> bool: ...
    def recharge(self, trigger: RechargeType) -> None: ...

# Extend ActionEconomy
class ActionEconomy(BaseBlock):
    # Existing: actions, bonus_actions, reactions, movement

    # NEW
    resources: Dict[str, Resource] = Field(default_factory=dict)

    def add_resource(self, name: str, maximum: int, recharge_type: RechargeType) -> None: ...
    def remove_resource(self, name: str) -> None: ...
    def can_afford_resource(self, name: str, amount: int = 1) -> bool: ...
    def consume_resource(self, name: str, amount: int = 1) -> bool: ...
    def on_short_rest(self) -> None: ...
    def on_long_rest(self) -> None: ...
    def on_turn_start(self) -> None: ...  # Also resets turn-based costs
```

#### Step 0.2: TargetType + ActionCost in BaseAction

**File**: `dnd/core/base_actions.py`

```python
# Add TargetType enum
class TargetType(str, Enum):
    SELF = "self"
    ENTITY = "entity"
    POSITION = "position"

# Add unified ActionCost model
class ActionCost(BaseModel):
    cost_type: Optional[CostType] = None       # Turn-based
    cost_amount: int = 0
    resource_name: Optional[str] = None        # Resource-based
    resource_amount: int = 0

# Update BaseAction
class BaseAction(BaseObject):
    target_type: TargetType = Field(default=TargetType.SELF)
    costs: List[ActionCost] = Field(default_factory=list)  # Updated type

    def check_all_costs(self, entity: Entity) -> bool: ...
    def apply_all_costs(self, entity: Entity) -> None: ...
```

**File**: `dnd/actions.py`

```python
# Set target_type on each action class
class Attack(BaseAction):
    target_type: TargetType = Field(default=TargetType.ENTITY)

class Move(BaseAction):
    target_type: TargetType = Field(default=TargetType.POSITION)

class Dash(BaseAction):
    target_type: TargetType = Field(default=TargetType.SELF)
# etc.
```

#### Step 0.3: Action Registry on Entity

**File**: `dnd/entity.py`

```python
# Add RegisteredAction model
class RegisteredAction(BaseModel):
    action_id: str
    action_class: Type[BaseAction]
    config: Dict[str, Any] = Field(default_factory=dict)

# Add to Entity class
class Entity(BaseBlock):
    registered_actions: Dict[str, RegisteredAction] = Field(default_factory=dict)

    def register_action(self, action_id, action_class, config=None): ...
    def unregister_action(self, action_id): ...
    def get_registered_action(self, action_id): ...
    def get_potential_targets(self, target_type, config): ...
    def create_action_instance(self, registered, target): ...
    def execute_action(self, action_id, target=None): ...
```

**File**: `dnd/default_actions.py` (new)

```python
def register_default_actions(entity: Entity) -> None:
    """Register Move, Dash, Dodge, Disengage."""

def register_weapon_attacks(entity: Entity) -> None:
    """Register attack actions from equipped weapons."""
```

#### Step 0.4: Refactor available_actions.py

**File**: `dnd/available_actions.py`

- Iterate `entity.registered_actions` instead of hardcoded functions
- Use `entity.get_potential_targets()` to get candidates
- Use `entity.create_action_instance()` + `pre_validate()` to filter valid ones
- Keep same `AvailableActionsResult` output for backwards compatibility

#### Step 0.5: Server endpoint

**File**: `server/event_server.py`

- Add generic `/action/execute` endpoint that uses `entity.execute_action()`
- Keep existing endpoints (`/action/attack`, `/action/move`, etc.) as wrappers

### Phase 1: Extend BaseCondition

**File**: `dnd/core/base_conditions.py`

```python
class BaseCondition(BaseObject):
    # NEW: Tags for class/feature filtering
    tags: List[str] = Field(default_factory=list)

    # NEW: Track registered actions and resources (like subcondition_uuids)
    registered_action_ids: List[str] = Field(default_factory=list)
    registered_resource_names: List[str] = Field(default_factory=list)

    # UPDATE: _apply() return signature adds action_ids and resource_names
    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # modifier pairs
        List[UUID],               # handler uuids
        List[UUID],               # subcondition uuids
        List[str],                # NEW: action_ids
        List[str],                # NEW: resource_names
        Optional[Event]
    ]: ...

    # UPDATE: apply() stores the new return values
    def apply(self, declaration_event): ...

    # UPDATE: _remove() auto-cleans actions and resources
    def _remove(self, event):
        target = Entity.get(self.target_entity_uuid)
        for action_id in self.registered_action_ids:
            target.unregister_action(action_id)
        for resource_name in self.registered_resource_names:
            target.action_economy.remove_resource(resource_name)
        # ... existing cleanup ...
```

**File**: `dnd/entity.py`

```python
def get_conditions_by_tag(self, tag: str) -> List[BaseCondition]:
    """Get all active conditions with a specific tag."""
    return [c for c in self.active_conditions.values() if tag in c.tags]

def remove_conditions_by_tag(self, tag: str) -> int:
    """Remove all conditions with a specific tag."""
    to_remove = [name for name, c in self.active_conditions.items() if tag in c.tags]
    for name in to_remove:
        self.remove_condition(name)
    return len(to_remove)
```

**File**: `dnd/conditions.py` - Update existing conditions

All existing conditions need their `_apply()` return updated to include empty lists for action_ids and resource_names:

```python
# Before:
return outs, [], [], effect_event

# After:
return outs, [], [], [], [], effect_event
```

### Phase 2: Implement Fighting Styles

**File**: `dnd/classes/fighter.py`

Start with simpler styles:

#### Defense Fighting Style

```python
def is_wearing_armor(source_uuid: UUID, target_uuid: Optional[UUID], context: Optional[Dict]) -> Optional[NumericalModifier]:
    """Returns +1 AC if wearing any armor."""
    entity = Entity.get(source_uuid)
    if entity and entity.equipment.armor is not None:
        return NumericalModifier.create(source_uuid, target_uuid, "Defense", 1)
    return None

class FightingStyleDefense(BaseCondition):
    name: str = "Fighting Style: Defense"
    description: str = "While you are wearing armor, you gain a +1 bonus to AC."
    tags: List[str] = Field(default=["class:fighter", "level:1", "feature:fighting_style", "subfeature:defense"])

    def _apply(self, declaration_event: Event) -> Tuple[...]:
        target = Entity.get(self.target_entity_uuid)
        outs = []

        modifier = ContextualNumericalModifier(
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            name="Defense",
            callable=is_wearing_armor
        )
        mod_uuid = target.equipment.ac_bonus.self_contextual.add_value_modifier(modifier)
        outs.append((target.equipment.ac_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(EventPhase.EFFECT, ...)
        return outs, [], [], effect_event
```

#### Archery Fighting Style

```python
class FightingStyleArchery(BaseCondition):
    name: str = "Fighting Style: Archery"
    description: str = "You gain a +2 bonus to attack rolls you make with ranged weapons."
    tags: List[str] = Field(default=["class:fighter", "level:1", "feature:fighting_style", "subfeature:archery"])

    def _apply(self, declaration_event: Event) -> Tuple[...]:
        target = Entity.get(self.target_entity_uuid)
        outs = []

        # Add +2 to ranged attack bonus
        modifier = NumericalModifier.create(
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            name="Archery",
            value=2
        )
        mod_uuid = target.equipment.ranged_attack_bonus.self_static.add_value_modifier(modifier)
        outs.append((target.equipment.ranged_attack_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(EventPhase.EFFECT, ...)
        return outs, [], [], effect_event
```

#### Dueling Fighting Style

```python
def is_dueling(source_uuid: UUID, target_uuid: Optional[UUID], context: Optional[Dict]) -> Optional[NumericalModifier]:
    """Returns +2 damage if wielding single melee weapon (no off-hand weapon)."""
    entity = Entity.get(source_uuid)
    if entity:
        main_hand = entity.equipment.weapon_main_hand
        off_hand = entity.equipment.weapon_off_hand
        # Has melee main hand, no off-hand weapon (shield OK)
        if (main_hand and WeaponProperty.RANGED not in main_hand.properties
            and (off_hand is None or not isinstance(off_hand, Weapon))):
            return NumericalModifier.create(source_uuid, target_uuid, "Dueling", 2)
    return None

class FightingStyleDueling(BaseCondition):
    name: str = "Fighting Style: Dueling"
    description: str = "When wielding a melee weapon in one hand and no other weapons, +2 damage."
    tags: List[str] = Field(default=["class:fighter", "level:1", "feature:fighting_style", "subfeature:dueling"])

    def _apply(self, declaration_event: Event) -> Tuple[...]:
        target = Entity.get(self.target_entity_uuid)
        outs = []

        modifier = ContextualNumericalModifier(
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            name="Dueling",
            callable=is_dueling
        )
        mod_uuid = target.equipment.damage_bonus.self_contextual.add_value_modifier(modifier)
        outs.append((target.equipment.damage_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(EventPhase.EFFECT, ...)
        return outs, [], [], effect_event
```

### Phase 3: Implement Second Wind

**Resource Tracking**: Add a `uses` field to track limited-use abilities.

```python
class SecondWind(BaseCondition):
    name: str = "Second Wind"
    description: str = "Bonus action to heal 1d10 + fighter level. Recharges on short/long rest."
    tags: List[str] = Field(default=["class:fighter", "level:1", "feature:second_wind"])

    fighter_level: int = Field(default=1, description="Fighter level for healing calculation")
    uses_remaining: int = Field(default=1, description="Uses remaining until rest")
    max_uses: int = Field(default=1, description="Maximum uses per rest")

    def use(self) -> bool:
        """Consume one use. Returns False if no uses remaining."""
        if self.uses_remaining <= 0:
            return False
        self.uses_remaining -= 1
        return True

    def short_rest(self) -> None:
        """Recharge uses on short rest."""
        self.uses_remaining = self.max_uses

    def long_rest(self) -> None:
        """Recharge uses on long rest."""
        self.uses_remaining = self.max_uses

    def _apply(self, declaration_event: Event) -> Tuple[...]:
        # SecondWind doesn't add modifiers, it provides an action
        # The action is registered separately
        effect_event = declaration_event.phase_to(EventPhase.EFFECT, ...)
        return [], [], [], effect_event
```

**Action**:

```python
class SecondWindAction(BaseAction):
    name: str = "Second Wind"
    description: str = "Heal 1d10 + fighter level as a bonus action."
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Second Wind", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ])

    def _validate(self, declaration_event):
        entity = Entity.get(self.source_entity_uuid)
        second_wind = entity.get_condition("Second Wind")
        if not second_wind or second_wind.uses_remaining <= 0:
            return declaration_event.cancel(status_message="Second Wind not available")
        return declaration_event.phase_to(EventPhase.EXECUTION)

    def _apply(self, execution_event):
        entity = Entity.get(self.source_entity_uuid)
        second_wind = entity.get_condition("Second Wind")

        # Roll healing: 1d10 + fighter level
        healing = DiceRoll.roll(1, 10) + second_wind.fighter_level
        entity.health.heal(healing)

        # Consume the use
        second_wind.use()

        effect_event = execution_event.phase_to(EventPhase.EFFECT, status_message=f"Healed {healing} HP")
        return effect_event.phase_to(EventPhase.COMPLETION)
```

### Phase 4: Fighter Factory Function

```python
# dnd/classes/fighter.py

from typing import Literal

FightingStyle = Literal["archery", "defense", "dueling", "great_weapon", "protection", "two_weapon"]

def apply_fighter_level_1(entity: Entity, fighting_style: FightingStyle) -> None:
    """Apply Fighter Level 1 features to an entity."""

    # Apply chosen fighting style
    style_conditions = {
        "archery": FightingStyleArchery,
        "defense": FightingStyleDefense,
        "dueling": FightingStyleDueling,
        # ... more styles
    }

    style_class = style_conditions.get(fighting_style)
    if style_class:
        condition = style_class(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid
        )
        entity.add_condition(condition)

    # Apply Second Wind
    second_wind = SecondWind(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        fighter_level=1
    )
    entity.add_condition(second_wind)

def remove_fighter_class(entity: Entity) -> int:
    """Remove all fighter class features. Returns count removed."""
    return entity.remove_conditions_by_tag("class:fighter")
```

---

## Complex Features (Future Levels)

### Extra Attack (Level 5)

**Challenge**: Attack action should allow 2 attacks instead of 1.

**Options**:
1. **Modify Attack action cost**: Make Attack cost 0.5 actions (complex)
2. **Grant extra action on Attack**: Event handler that grants +1 action when Attack is used
3. **New "Attack Action" wrapper**: Replace Attack with a multi-attack action

**Recommended**: Option 3 - Create `AttackAction` that internally calls `Attack` N times.

### Action Surge (Level 2)

**Effect**: Take one additional action on your turn, once per rest.

**Implementation**:
- Condition tracks uses
- Action grants +1 action (modifier on action economy)

### Indomitable (Level 9)

**Effect**: Reroll a failed saving throw.

**Implementation**:
- Event handler on SAVING_THROW events in EFFECT phase
- If save failed and uses remaining, offer reroll

---

## Proficiencies

Fighter proficiencies (armor, weapons, saving throws) should be handled separately from class conditions:

```python
class Proficiencies(BaseBlock):
    armor_proficiencies: Set[ArmorType]  # LIGHT, MEDIUM, HEAVY, SHIELD
    weapon_proficiencies: Set[WeaponCategory]  # SIMPLE, MARTIAL
    saving_throw_proficiencies: Set[AbilityName]  # STRENGTH, CONSTITUTION
    skill_proficiencies: Set[SkillName]  # chosen skills
```

This is separate from the condition system since proficiencies are binary (have or don't) rather than modifiers.

---

## Files to Create/Modify

| File | Changes |
|------|---------|
| **Phase 0: Resource System + Action Registry** |  |
| `dnd/blocks/action_economy.py` | Add `RechargeType` enum, `Resource` model, extend `ActionEconomy` with `resources` dict, add resource methods, rest triggers |
| `dnd/core/base_actions.py` | Add `TargetType` enum, `ActionCost` model, add `target_type` + `costs` to `BaseAction`, add `check_all_costs()`, `apply_all_costs()` |
| `dnd/actions.py` | Set `target_type` on `Attack`, `Move`, `Dash`, `Dodge`, `Disengage`; update costs to use `ActionCost` |
| `dnd/entity.py` | Add `RegisteredAction` model, add `registered_actions` dict, add `register_action()`, `unregister_action()`, `get_registered_action()`, add target-finding methods, add `create_action_instance()`, `execute_action()` |
| `dnd/default_actions.py` | **NEW** - `register_default_actions()`, `register_weapon_attacks()` |
| `dnd/available_actions.py` | Refactor to iterate registry, use `pre_validate()` per target |
| `server/event_server.py` | Add generic `/action/execute` endpoint |
| **Phase 1: Extend BaseCondition** |  |
| `dnd/core/base_conditions.py` | Add `tags`, `registered_action_ids`, `registered_resource_names` fields; update `_apply()` return signature (add 2 lists); update `apply()` to store new values; update `_remove()` for auto-cleanup |
| `dnd/conditions.py` | Update all existing conditions' `_apply()` to return 6-tuple (add empty `[], []` for actions/resources) |
| `dnd/entity.py` | Add `get_conditions_by_tag()`, `remove_conditions_by_tag()` |
| **Phase 2: Rest System Integration** |  |
| `dnd/entity.py` | Add `short_rest()`, `long_rest()` methods that trigger `action_economy.on_short_rest()`, etc. |
| **Phase 3-4: Fighter Class** |  |
| `dnd/classes/__init__.py` | **NEW** - Module init |
| `dnd/classes/fighter.py` | **NEW** - Fighting styles, `SecondWind` condition, `SecondWindAction`, `apply_fighter_level_1()` |
| `dnd/blocks/health.py` | (Future) Add `source_tag` to HitDice for multiclass support |

---

## Testing Strategy

1. **Unit tests**: Each fighting style condition in isolation
2. **Integration test**: Create fighter, verify modifiers apply correctly
3. **PvP test**: Play with fighter features, verify combat behavior
4. **Level up test**: Add level 2 features, verify both levels work
5. **Respec test**: Remove fighter features, verify clean removal

---

## Next Steps

### Phase 0: Resource System + Action Registry (PREREQUISITE)

**Step 0.1: Resource System** (ActionEconomy)
1. Add `RechargeType` enum to `dnd/blocks/action_economy.py`
2. Add `Resource` model with `can_afford()`, `consume()`, `recharge()`
3. Add `resources: Dict[str, Resource]` to `ActionEconomy`
4. Add `add_resource()`, `remove_resource()`, `can_afford_resource()`, `consume_resource()`
5. Add `on_short_rest()`, `on_long_rest()`, `on_turn_start()` triggers

**Step 0.2: TargetType + ActionCost** (BaseAction)
6. Add `TargetType` enum to `dnd/core/base_actions.py`
7. Add `ActionCost` model (unified turn-based + resource costs)
8. Add `target_type` field to `BaseAction`
9. Update `costs` field to use `List[ActionCost]`
10. Add `check_all_costs()` and `apply_all_costs()` methods
11. Set `target_type` on existing actions (Attack=ENTITY, Move=POSITION, others=SELF)
12. Update existing action costs to use `ActionCost` model

**Step 0.3: Action Registry** (Entity)
13. Add `RegisteredAction` model
14. Add `registered_actions: Dict[str, RegisteredAction]` to Entity
15. Add `register_action()`, `unregister_action()`, `get_registered_action()`
16. Add `get_potential_targets()`, `create_action_instance()`, `execute_action()`
17. Create `dnd/default_actions.py` with `register_default_actions()`, `register_weapon_attacks()`

**Step 0.4: Available Actions Refactor**
18. Refactor `available_actions.py` to iterate `registered_actions`
19. Use `pre_validate()` to validate each action with each target
20. Keep same `AvailableActionsResult` output

**Step 0.5: Server + Testing**
21. Add generic `/action/execute` endpoint to server
22. Test that existing PvP gameplay still works

### Phase 1: Condition Tags
23. Add `tags: List[str]` to `BaseCondition`
24. Add `get_conditions_by_tag()`, `remove_conditions_by_tag()` to Entity

### Phase 2: Rest System
25. Add `short_rest()`, `long_rest()` to Entity (trigger action_economy methods)

### Phase 3: Fighter Class
26. Create `dnd/classes/fighter.py`
27. Implement `FightingStyleDefense` (simplest - +1 AC with armor)
28. Test Defense style in PvP
29. Implement `SecondWind` condition (registers resource + action)
30. Implement `SecondWindAction` (uses resource)
31. Test Second Wind in PvP
32. Add `FightingStyleArchery`, `FightingStyleDueling`
33. Create `apply_fighter_level_1()` factory

---

## Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Class features as...** | Conditions | Leverages existing modifier system, auto-cleanup on remove |
| **Action registration** | `Dict[str, RegisteredAction]` on Entity | Follows `active_conditions` pattern, clean condition-based cleanup |
| **Target type** | `TargetType` field on `BaseAction` | Each action declares what it needs (SELF/ENTITY/POSITION) |
| **Resource tracking** | Extended `ActionEconomy` with `resources` dict | Single place for ALL resources (turn-based + limited-use), unified recharge triggers |
| **Cost system** | Unified `ActionCost` model | Handles both turn-based (actions/bonus) AND resource-based (second_wind) costs in same model |
| **Action validation** | Use `pre_validate()` per target | No duplicate validation logic, actions validate themselves |
| **Available actions query** | Iterate registry, `pre_validate()` per target | Single source of truth, extensible, uses actual action validation |
| **Action execution** | `entity.execute_action(action_id, target)` | Factory pattern, clean interface |
| **Condition→Action link** | `_apply()` returns `action_ids`, base class auto-cleans | Same pattern as sub-conditions - explicit return, automatic cleanup |
| **Condition identification** | `tags: List[str]` | Flexible filtering by class/level/feature |
| **Rest triggers** | `Entity.short_rest()` / `long_rest()` → `ActionEconomy` | Clean layering, entity coordinates rest effects |

---

## Open Questions (Future)

1. **Equipment changes**: When weapons change, should attacks re-register automatically?
2. **Multiclassing**: How do we prevent duplicate fighting styles?
3. **UI updates**: How does the CLI know a new action was registered?
4. **AI behavior**: How should AI know to use class features like Second Wind?
