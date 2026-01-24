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

## Action System Architecture (CURRENT IMPLEMENTATION)

The action system uses a **template-based architecture** where actions are registered on entities as templates and validated/executed through a unified API.

### Current Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SERVER ENDPOINTS                                   │
│  server/event_server.py                                                     │
│                                                                             │
│  GET  /entity/{uuid}/available-actions → entity.get_available_actions()     │
│  POST /action/execute                  → execute_action(template_name, idx) │
│  POST /action/end-turn                 → manages turn flow                  │
│                                                                             │
│  UNIFIED: Single execute endpoint uses entity's registered templates        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↑
                          Uses entity's action_templates
                                    ↑
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ENTITY ACTION REGISTRY                             │
│  dnd/entity.py                                                              │
│                                                                             │
│  Entity.action_templates: Dict[str, BaseAction]  # Registered templates     │
│  Entity.register_action(action)    → adds action with template=True         │
│  Entity.unregister_action(name)    → removes action template                │
│  Entity.get_action_template(name)  → retrieves template                     │
│  Entity.get_available_actions()    → validates all templates with targets   │
│                                                                             │
│  Templates are BaseAction instances with template=True                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↑
                          Uses TargetType for validation
                                    ↑
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ACTION CLASSES                                     │
│  dnd/actions.py + dnd/core/base_actions.py                                  │
│                                                                             │
│  class BaseAction:                                                          │
│    target_type: TargetType  # SELF, ENTITY, POSITION                        │
│    template: bool           # True = registered template, False = executable│
│    pre_validate() → bool    # Check if action can execute                   │
│    instantiate(**overrides) → BaseAction  # Create executable from template │
│                                                                             │
│  class Attack(BaseAction):  target_type = ENTITY                            │
│  class Move(BaseAction):    target_type = POSITION                          │
│  class Dash(BaseAction):    target_type = SELF                              │
│  class Dodge(BaseAction):   target_type = SELF                              │
│  class Disengage(BaseAction): target_type = SELF                            │
│  class StandUp(BaseAction): target_type = SELF                              │
│  class DropProne(BaseAction): target_type = SELF                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↑
                          Functional API for convenience
                                    ↑
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FUNCTIONAL API                                     │
│  dnd/actions_functional.py                                                  │
│                                                                             │
│  setup_standard_actions(entity)  → Registers Move, Dash, Dodge, Disengage   │
│                                    + weapon attacks from equipment          │
│  get_available_actions(entity)   → Wrapper for entity.get_available_actions │
│  execute_action(entity, name, target)  → Execute with specific target       │
│  execute_by_index(entity, name, idx)   → Execute by target index            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Action Inventory (All Implemented)

| Action | Class | Cost | TargetType | Notes |
|--------|-------|------|------------|-------|
| **Move** | `Move` | movement (variable) | POSITION | Path computed from senses.paths |
| **Attack** | `Attack` | 1 action (main) / 1 bonus (off-hand) | ENTITY | Per-weapon-slot templates |
| **Dash** | `Dash` | 1 action | SELF | Applies Dashing condition |
| **Dodge** | `Dodge` | 1 action | SELF | Applies Dodging condition |
| **Disengage** | `Disengage` | 1 action | SELF | Applies Disengaging condition |
| **Stand Up** | `StandUp` | half movement | SELF | Removes Prone condition |
| **Drop Prone** | `DropProne` | free | SELF | Applies Prone condition |
| **Opportunity Attack** | `Attack` | 1 reaction | ENTITY | Triggered via EventHandler |

### Template Registration Flow

```python
# In dnd/actions_functional.py:setup_standard_actions()

def setup_standard_actions(entity: Entity):
    # Self-targeted actions
    entity.register_action(Move(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(Dash(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(Dodge(source_entity_uuid=entity.uuid, template=True))
    entity.register_action(Disengage(source_entity_uuid=entity.uuid, template=True))

    # Weapon attacks (one template per equipped weapon slot)
    for slot in WeaponSlot:
        weapon = entity.equipment._get_weapon_by_slot(slot)
        if weapon:
            entity.register_action(Attack(
                source_entity_uuid=entity.uuid,
                weapon_slot=slot,
                name=f"Attack_{slot.value}",
                template=True
            ))
```

### Available Actions Query

```python
# In Entity.get_available_actions()

# For each registered template:
# 1. Get potential targets based on target_type
# 2. For each target, set it on template and call pre_validate()
# 3. Collect valid targets with indices

# Returns AvailableActionsResult with:
# - entity_actions: Attack templates with valid target UUIDs
# - position_actions: Move template with valid positions
# - self_actions: Dash, Dodge, Disengage, etc.
```

### Server Execution

```python
# POST /action/execute with { template_name, target_index, session_id, entity_uuid }

# 1. Validate session owns entity
# 2. Get template: entity.get_action_template(template_name)
# 3. Get target: available_actions.valid_targets[target_index]
# 4. Instantiate and execute: template.instantiate(target=...).apply()
```

### What's Working ✅

1. **Action Registry**: Entities have `action_templates` dict, can register/unregister
2. **Template System**: Actions have `template=True`, can be instantiated with targets
3. **TargetType**: Actions declare SELF/ENTITY/POSITION targeting
4. **Available Actions Query**: Validates each template with each potential target
5. **Unified Execution**: Single `/action/execute` endpoint
6. **Functional API**: `setup_standard_actions()`, `execute_by_index()`

---

## Remaining Implementation: Resource System + Condition Extensions

The action registry is **complete**. What remains:

1. **Resource System** - Limited-use features (Second Wind, spell slots)
2. **BaseCost Extension** - Resource-based costs alongside turn-based costs
3. **Condition Extensions** - Tags for filtering, auto-cleanup of registered actions/resources

---

### Resource System (ActionEconomy)

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

### Phase 0: Action Registry Infrastructure ✅ COMPLETE

| Step | Status | Notes |
|------|--------|-------|
| **0.1 TargetType enum** | ✅ DONE | In `dnd/core/base_actions.py` |
| **0.2 Template system** | ✅ DONE | `BaseAction.template`, `instantiate()` |
| **0.3 Action registry on Entity** | ✅ DONE | `Entity.action_templates`, `register_action()` |
| **0.4 Available actions query** | ✅ DONE | `Entity.get_available_actions()` |
| **0.5 Functional API** | ✅ DONE | `dnd/actions_functional.py` |
| **0.6 Server endpoint** | ✅ DONE | `POST /action/execute` |

### Phase 1: Resource System ✅ COMPLETE

| Step | Status | Notes |
|------|--------|-------|
| **1.1 RechargeType enum** | ✅ DONE | `dnd/blocks/action_economy.py` |
| **1.2 Resource model** | ✅ DONE | `can_afford()`, `consume()`, `recharge()` |
| **1.3 ActionEconomy.resources** | ✅ DONE | `Dict[str, Resource]` |
| **1.4 Resource methods** | ✅ DONE | `add_resource()`, `remove_resource()`, `can_afford_resource()`, `consume_resource()` |
| **1.5 Rest triggers** | ✅ DONE | `on_short_rest()`, `on_long_rest()`, `on_turn_start()` |
| **1.6 BaseCost extension** | ✅ DONE | `resource_name`, `resource_cost` fields |
| **1.7 check_costs() update** | ✅ DONE | Validates both turn-based and resource costs |
| **1.8 Cost applier update** | ✅ DONE | Consumes both turn-based and resource costs |

### Phase 2: Second Wind Proof of Concept ✅ COMPLETE

| Step | Status | Notes |
|------|--------|-------|
| **2.1 SecondWind action** | ✅ DONE | `examples/test_second_wind.py` |
| **2.2 Integration test** | ✅ DONE | Full resource lifecycle verified |

### Bug Fixes During Implementation

| Fix | Description |
|-----|-------------|
| `check_costs()` registry | Was using `BaseObject.get()`, fixed to `BaseBlock.get()` |
| `get_available_actions()` | Now shows unaffordable actions with `can_afford=False` |

---

## Next Steps: Fighter Implementation

**See**: `claude_docs/FIGHTER_IMPLEMENTATION_PLAN.md` for detailed feature analysis.

### Summary of Fighter Features by Difficulty

| Difficulty | Features |
|------------|----------|
| **Simple** | Archery, Defense, Dueling, Two-Weapon Fighting, Action Surge, ASI |
| **Medium** | Extra Attack, Improved/Superior Critical, Protection, Indomitable |
| **Complex** | Great Weapon Fighting (dice reroll), Survivor (turn start) |

### Key Design Decisions

1. **Optional reactions**: Auto-trigger for now (like Opportunity Attacks). Player choice mechanism later.

2. **Dice rerolling**: Use EventHandler on new `DAMAGE_ROLLED` event type between roll and apply.

3. **Critical threshold**: `crit_range = 20 - crit_threshold_modifier` where modifier defaults to 0.

4. **Extra Attack**: Use `HasAttacked` marker condition + separate `ExtraAttack` action + resource.

### Event Handler Constraint

**IMPORTANT**: Handlers can only respond BEFORE the COMPLETION phase.

Once an event reaches COMPLETION, it cannot be modified or spawn sub-events.
Reactions must trigger on DECLARATION, EXECUTION, or EFFECT phases.

---

### Phase 3: Extend BaseCondition (FUTURE)

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

    # UPDATE: _remove() auto-cleans actions and resources
    def _remove(self, event):
        target = Entity.get(self.target_entity_uuid)
        for action_id in self.registered_action_ids:
            target.unregister_action(action_id)
        for resource_name in self.registered_resource_names:
            target.action_economy.remove_resource(resource_name)
```

**File**: `dnd/entity.py`

```python
def get_conditions_by_tag(self, tag: str) -> List[BaseCondition]:
    """Get all active conditions with a specific tag."""
    return [c for c in self.active_conditions.values() if tag in c.tags]
```

### Phase 4: Implement Fighting Styles (FUTURE)

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

### Phase 5: Implement Second Wind (FUTURE)

**Resource Tracking**: Uses the resource system from Phase 1.

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

| File | Changes | Status |
|------|---------|--------|
| **Phase 0: Action Registry (COMPLETE)** |  |  |
| `dnd/core/base_actions.py` | `TargetType` enum, template system, `AvailableActionsResult` | ✅ DONE |
| `dnd/actions.py` | `target_type` on all actions | ✅ DONE |
| `dnd/entity.py` | `action_templates` dict, `register_action()`, `get_available_actions()` | ✅ DONE |
| `dnd/actions_functional.py` | `setup_standard_actions()`, `execute_action()`, `execute_by_index()` | ✅ DONE |
| `server/event_server.py` | `/action/execute` endpoint | ✅ DONE |
| **Phase 1: Resource System (IN PROGRESS)** |  |  |
| `dnd/blocks/action_economy.py` | `RechargeType` enum, `Resource` model, resource methods, rest triggers | 🔨 TODO |
| `dnd/core/base_actions.py` | Add `resource_name`, `resource_cost` to `BaseCost` | 🔨 TODO |
| `dnd/actions.py` | Update cost applier to handle resource costs | 🔨 TODO |
| **Phase 2: SecondWind (Proof of Concept)** |  |  |
| `dnd/actions.py` | Add `SecondWind` action class | 🔨 TODO |
| `examples/test_second_wind.py` | Test script | 🔨 TODO |
| **Phase 3: Extend BaseCondition (FUTURE)** |  |  |
| `dnd/core/base_conditions.py` | Add `tags`, `registered_action_ids`, `registered_resource_names`; update `_apply()` return | ❌ TODO |
| `dnd/conditions.py` | Update all conditions' `_apply()` to return 6-tuple | ❌ TODO |
| `dnd/entity.py` | Add `get_conditions_by_tag()` | ❌ TODO |
| **Phase 4-5: Fighter Class (FUTURE)** |  |  |
| `dnd/classes/__init__.py` | **NEW** - Module init | ❌ TODO |
| `dnd/classes/fighter.py` | **NEW** - Fighting styles, SecondWind condition | ❌ TODO |
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
