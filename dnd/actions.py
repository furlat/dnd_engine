from dnd.core.base_actions import BaseAction, StructuredAction, CostType, Cost, BaseCost, ActionEvent, TargetType, ActionCategory
from dnd.core.values import ModifiableValue
from dnd.core.base_conditions import DurationType
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus

from dnd.core.dice import  DiceRoll, AttackOutcome, RollType
from dnd.core.events import RangeType, Event, EventType, WeaponSlot, Range, Damage, EventPhase, DamageRollResultEvent, StepMovementEvent, ForcedMovementEvent
from dnd.core.gridmap import get_map
from dnd.core.base_block import BaseBlock, MovementMode
from dnd.core.combat_log import (
    CombatLogEntry, CombatLogEntryType, ModifierBreakdown, DiceRollDisplay,
    DamageRollDisplay, AttackLogData, MovementLogData, SpellSaveLogData,
    format_attack_compact, format_attack_verbose, format_attack_detailed,
    md_color
)
from pydantic import Field, model_validator
from typing import Optional, List, TypeVar, Tuple, Self, cast
from uuid import UUID, uuid4
from dnd.entity import Entity, determine_attack_outcome
from dnd.blocks.base_item import BaseItem
from dnd.conditions import Dashing, Dodging, Disengaging, Prone, Hidden
from collections import OrderedDict


#here we create event processors for the validation of the attack
def entity_action_economy_cost_evaluator(source_entity_uuid: UUID,cost_type: CostType,cost: int) -> bool:
        """Evaluate the costs of the action"""
        entity = Entity.get(source_entity_uuid)
        if entity is None or not isinstance(entity, Entity):
            return False
        return entity.action_economy.can_afford(cost_type,cost)

PolymorphicActionEvent = TypeVar('PolymorphicActionEvent', bound='ActionEvent')

def validate_line_of_sight(declaration_event: PolymorphicActionEvent, source_entity_uuid: UUID) -> Optional[PolymorphicActionEvent]:
    """Validate if the source entity and target entity are in line of sight"""
    source_entity = Entity.get(source_entity_uuid)
    if not source_entity:
        return declaration_event.cancel(status_message=f"Source entity not found for {declaration_event.name}")
    if not isinstance(source_entity, Entity):
        return declaration_event.cancel(status_message=f"Source entity not found for {declaration_event.name}")
    if not declaration_event.target_entity_uuid:
        return declaration_event.cancel(status_message=f"Target entity uuid not present for {declaration_event.name}")
    target_entity = Entity.get(declaration_event.target_entity_uuid)
    if not target_entity:
        return declaration_event.cancel(status_message=f"Target entity not found for {declaration_event.name}")
    if not isinstance(target_entity, Entity):
        return declaration_event.cancel(status_message=f"Target entity not found for {declaration_event.name}")
    
    if target_entity.uuid not in source_entity.senses.entities.keys():
        return declaration_event.cancel(status_message=f"Target entity not in line of sight for {declaration_event.name}")
    return declaration_event.phase_to(
        new_phase=EventPhase.DECLARATION,
        status_message=f"Validated line of sight for {declaration_event.name}"
    )

def entity_action_economy_cost_applier(completion_event: PolymorphicActionEvent, source_entity_uuid: UUID) -> PolymorphicActionEvent:
    """Apply the costs of the action (turn-based and resource-based)."""
    entity = Entity.get(source_entity_uuid)
    if entity is None or not isinstance(entity, Entity):
        return completion_event.cancel(status_message=f"Entity not found for {completion_event.name}")
    for cost in completion_event.costs:
        # Apply turn-based cost
        if cost.cost > 0:
            entity.action_economy.consume(cost.cost_type, cost.cost)
        # Apply resource cost if present
        if cost.resource_cost > 0 and cost.resource_name:
            if not entity.action_economy.consume_resource(cost.resource_name, cost.resource_cost):
                return completion_event.cancel(
                    status_message=f"Failed to consume resource {cost.resource_name} for {completion_event.name}"
                )
    return completion_event.phase_to(
        new_phase=EventPhase.COMPLETION,
        status_message=f"Successfully applied costs for {completion_event.name} for {completion_event.source_entity_uuid}"
    )


class MovementEvent(ActionEvent):
    """An event that represents a movement"""
    name: str = Field(default="Movement",description="A movement event")
    event_type: EventType = Field(default=EventType.MOVEMENT,description="The type of event")
    costs: List[BaseCost] = Field(default_factory=list,description="A list of costs for the action")
    start_position: Tuple[int,int] = Field(description="The start position of the movement")
    end_position: Tuple[int,int] = Field(description="The end position of the movement")
    path: Optional[List[Tuple[int,int]]] = Field(default=None,description="The path of the movement")

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for this movement event.

        Uses self.* fields only - no external lookups. Entity name must be
        populated when the event is created.
        """
        # Use entity name from self - no external lookups
        source_name = self.source_entity_name or "Unknown"

        # Calculate distance
        path = self.path or []
        distance_feet = (len(path) - 1) * 5 if len(path) > 1 else 0

        # Get movement cost
        movement_cost = 0
        for cost in self.costs:
            if cost.cost_type == "movement":
                movement_cost = cost.cost

        # Build path string for detail line
        path_str = " -> ".join(f"({p[0]}, {p[1]})" for p in path) if path else ""

        # Build markdown-formatted verbosity levels
        end_pos = f"({self.end_position[0]},{self.end_position[1]})"
        start_pos = f"({self.start_position[0]},{self.start_position[1]})"

        # Compact: "{cyan:Hero} moves {green:15ft} to {yellow:(5,3)}"
        compact_text = f"{md_color(source_name, 'cyan')} moves {md_color(f'{distance_feet}ft', 'green')} to {md_color(end_pos, 'yellow')}"

        # Verbose: same as compact + position change
        verbose_text = f"{md_color(source_name, 'cyan')} moves {start_pos} → {md_color(end_pos, 'green')}"
        if movement_cost > 0:
            verbose_text += f" ({movement_cost}ft)"

        # Detailed: includes path
        detailed_text = verbose_text
        if path_str:
            detailed_text += f"\n  Path: {path_str}"

        # Build structured data
        data = MovementLogData(
            entity_name=source_name,
            entity_uuid=str(self.source_entity_uuid),
            start_position=self.start_position,
            end_position=self.end_position,
            path=path,
            distance_feet=distance_feet,
            movement_cost=movement_cost
        )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.MOVEMENT,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data=data.model_dump(),
            success=True
        )


class Move(BaseAction):
    """An action that represents a movement with a path it will automatically compute the path from the source entity position to the end position
    the cost is automatically computed from the path length and the use_movement_cost flag is true

    This is a simplified implmenetation that does not move the character through the path, hence not triggering any movement specific.

    When used as a template (template=True), end_position can be None and should be set via set_target_position()
    before pre_validate() or instantiate().
    """
    name: str = Field(default="Move", description="A movement action")
    description: str = Field(default="Move to a position", description="A description of the movement action")
    target_type: TargetType = Field(default=TargetType.POSITION_PATH, description="Move targets a position via path")
    action_category: ActionCategory = Field(default=ActionCategory.MOVEMENT)
    end_position: Optional[Tuple[int, int]] = Field(default=None, description="The end position of the movement")
    path: Optional[List[Tuple[int, int]]] = Field(default=None, description="The path of the movement")
    use_movement_cost: bool = Field(default=True, description="Whether to use the movement cost")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Only compute path and costs if we have an end_position (not a template)
        if self.end_position is not None and not self.template:
            self._setup_path()
            self._setup_costs_from_path()

    def _setup_costs_from_path(self):
        if self.path is not None and self.use_movement_cost:
            # Calculate cost from actual terrain, not just path length
            grid = get_map()
            total_cost = 0

            # Path includes starting position, so iterate from index 1
            for i in range(1, len(self.path)):
                tile = grid.get_tile(*self.path[i])
                if tile:
                    total_cost += tile.get_movement_cost(MovementMode.WALKING)
                else:
                    total_cost += 1  # Default cost if no tile exists

            # Each cost unit = 5 feet in D&D 5e
            feet_cost = int(total_cost * 5)
            self.costs.append(Cost(name="Movement Cost",cost_type="movement",cost=feet_cost,evaluator=entity_action_economy_cost_evaluator))

    def _setup_path(self):
        """Check if the costs of the action are valid and sets up the path and the costs"""
        if self.path is None and self.end_position is not None:
            source_entity = Entity.get(self.source_entity_uuid)
            if source_entity is None or not isinstance(source_entity, Entity):
                return None
            if self.end_position in source_entity.senses.paths:
                self.path = source_entity.senses.paths[self.end_position]

    def set_target_position(self, position: Tuple[int, int]) -> None:
        """Set target position and compute path/costs for validation.

        Overrides base implementation to also compute path and costs,
        so that pre_validate() can properly check movement affordability.
        """
        # Clear previous path/costs if re-targeting
        self.path = None
        self.costs = []

        # Set position via parent
        super().set_target_position(position)

        # Compute path and costs so check_costs() works
        self._setup_path()
        self._setup_costs_from_path()

    def instantiate(self, **overrides) -> "Move":
        """Create an executable Move instance from this template.

        Uses model_copy() to preserve object types. Path/costs are reset
        for recomputation based on new end_position.
        """
        if not self.template:
            raise ValueError("Can only instantiate from a template")

        # Instance config: new UUID, not a template, not registered (ephemeral)
        # Reset path and costs for recomputation
        update_dict: dict = {
            "uuid": uuid4(),
            "template": False,
            "use_register": False,  # Instances are ephemeral, don't need registry
            "path": None,  # Force recompute
            "costs": [],   # Force recompute
        }
        update_dict.update(overrides)

        # model_copy preserves object types but bypasses __init__()
        instance = self.model_copy(deep=True, update=update_dict)

        # FIX: Explicitly compute path and costs since model_copy() bypasses __init__()
        if instance.end_position is not None:
            instance._setup_path()
            instance._setup_costs_from_path()

        return instance

    @staticmethod
    def validate_path(declaration_event: MovementEvent,source_entity_uuid: UUID) -> MovementEvent:
        """Validate the path of the movement"""
        source_entity = Entity.get(source_entity_uuid)
        if not source_entity or not isinstance(source_entity, Entity):
            return declaration_event.cancel(status_message=f"Source entity not found for {declaration_event.name}")
        if declaration_event.path is None or len(declaration_event.path) == 0:
            #get the path from the source entity to the end position
            return declaration_event.cancel(status_message=f"No valid path found for {declaration_event.name}")
           
        else:
            if declaration_event.path == source_entity.senses.paths[declaration_event.end_position]:
                return declaration_event.post(
                    status_message=f"Validated path for {declaration_event.name}"
                )
            else:
                #we must check that all the positions in the path have a valid path
                for path_position in declaration_event.path:
                    if path_position not in source_entity.senses.paths:
                        return declaration_event.cancel(status_message=f"Invalid path for {declaration_event.name} at position {path_position}")
                    
                return declaration_event.post(
                    status_message=f"Validated path for {declaration_event.name}"
                )
            
    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the declaration event for the movement action.

        For templates, this computes the path and costs on the fly based on the
        current end_position.
        """
        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity or not isinstance(source_entity, Entity):
            return None

        if self.end_position is None:
            return None  # Can't create movement event without destination

        # Store in local variable to help type checker
        end_position: Tuple[int, int] = self.end_position

        # Compute path on the fly if not already set (for templates)
        path = self.path
        if path is None and end_position in source_entity.senses.paths:
            path = source_entity.senses.paths[end_position]

        # Compute costs from path if using movement cost
        costs = list(self.costs)  # Copy existing costs
        if path is not None and self.use_movement_cost:
            # Check if we already have a movement cost
            has_movement_cost = any(c.cost_type == "movement" for c in costs)
            if not has_movement_cost:
                # Calculate cost from actual terrain, not just path length
                grid = get_map()
                total_cost = 0

                # Path includes starting position, so iterate from index 1
                for i in range(1, len(path)):
                    tile = grid.get_tile(*path[i])
                    if tile:
                        total_cost += tile.get_movement_cost(MovementMode.WALKING)
                    else:
                        total_cost += 1  # Default cost if no tile exists

                # Each cost unit = 5 feet in D&D 5e
                feet_cost = int(total_cost * 5)
                costs.append(Cost(name="Movement Cost", cost_type="movement", cost=feet_cost, evaluator=entity_action_economy_cost_evaluator))

        return MovementEvent(
            name=f"{self.name}",
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            start_position=source_entity.position,
            end_position=end_position,
            path=path,
            costs=[BaseCost.model_validate(cost) for cost in costs],
            use_register=use_register,
            source_entity_name=source_entity.name  # Populate for combat log generation
        )
    
    def _validate(self, declaration_event: MovementEvent) -> MovementEvent:
        """Validate the movement action"""
        validated_event = Move.validate_path(declaration_event,self.source_entity_uuid)
        if not validated_event.canceled:
            return validated_event.phase_to(
                new_phase=EventPhase.EXECUTION,
                status_message=f"Validated  {declaration_event.name}"
            )
        else:
            return validated_event
        
    def _apply(self, execution_event: MovementEvent) -> MovementEvent:
        """Apply the movement action using cell-by-cell movement.

        Iterates through path, firing StepMovementEvent for each cell transition.
        This allows OA handlers and terrain effects to interrupt movement.
        """
        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity or not isinstance(source_entity, Entity):
            return execution_event.cancel(status_message=f"Source entity not found for {execution_event.name}")

        # First check if we have path
        if self.path is None and execution_event.path is None:
            return execution_event.cancel(status_message=f"No path found for {execution_event.name}")
        elif self.path is None and execution_event.path is not None:
            self.path = execution_event.path
            if self.use_movement_cost:
                self._setup_costs_from_path()
            execution_event = execution_event.post(
                path=self.path,
                status_message=f"Added paths to {execution_event.uuid}"
            )

        costs = [BaseCost.model_validate(cost) for cost in self.costs]
        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            costs=costs,
            status_message=f"Added costs to {execution_event.uuid}"
        )
        if effect_event.canceled:
            return effect_event

        # Cell-by-cell movement
        grid = get_map()
        path = self.path or []
        total_path_length = len(path)
        actual_end_position = source_entity.position  # Track where we actually end up

        # Set is_moving flag on senses so SpatialSensesCallback does visibility-only updates per step
        source_entity.senses.is_moving = True

        try:
            for i in range(1, total_path_length):
                from_pos = path[i - 1]
                to_pos = path[i]

                # Check if next step is still valid (tile walkable, not blocked by entity)
                # Handles: tile destroyed, enemy moved into path, etc.
                if not grid.is_walkable_for(to_pos[0], to_pos[1], source_entity.uuid):
                    break

                # Get step cost from terrain
                tile = grid.get_tile(*to_pos)
                step_cost_units = tile.get_movement_cost(MovementMode.WALKING) if tile else 1.0
                step_cost_feet = int(step_cost_units * 5)

                # Check if entity has enough movement remaining (conditions affect this via modifiers)
                remaining_movement = source_entity.action_economy.movement.normalized_score
                if remaining_movement < step_cost_feet:
                    break

                # Fire StepMovementEvent (OA and terrain handlers see this)
                step_event = StepMovementEvent(
                    source_entity_uuid=self.source_entity_uuid,
                    source_entity_name=source_entity.name,
                    from_position=from_pos,
                    to_position=to_pos,
                    path_index=i,
                    total_path_length=total_path_length,
                    movement_cost=step_cost_feet,
                    phase=EventPhase.EFFECT,
                    parent_event=effect_event.uuid
                )
                # post() returns the processed event (which may have been canceled by handlers)
                processed_step = step_event.post()

                # Check if step was canceled (e.g., by a reaction or trap)
                if processed_step.canceled:
                    break

                # Actually move the entity - pass step event UUID so terrain damage links to it
                # NOTE: We pass the EFFECT phase UUID here, and complete the step AFTER
                # spatial events fire. This ensures terrain damage (TakeDamageEvent) is
                # collected as a child of this step when combat_log is generated.
                Entity.update_entity_position(source_entity, to_pos, parent_event=processed_step.uuid)
                actual_end_position = to_pos

                # Now progress to COMPLETION - generates combat_log with all children
                # (including TakeDamageEvents from terrain that just fired)
                processed_step.phase_to(EventPhase.COMPLETION)

                # Check for death during movement (e.g., from terrain damage like spikes)
                # receive_damage() applies Dead condition → Incapacitated → movement=0
                # We need to break BEFORE trying to consume movement
                if "Dead" in source_entity.active_conditions:
                    break

                # Deduct movement cost for this step
                source_entity.action_economy.consume("movement", step_cost_feet)

        finally:
            # ALWAYS clear flag and do full senses update, regardless of how loop exits:
            # - Normal completion
            # - break (step canceled, path invalid, not enough movement, death)
            # - Exception
            source_entity.senses.is_moving = False
            source_entity.update_entity_senses(max_distance=20)

        # Determine final result
        if source_entity.position == execution_event.start_position:
            return effect_event.cancel(status_message=f"Failed to move for {execution_event.name}")
        elif source_entity.position != execution_event.end_position:
            # Partial movement (stopped early due to death, OA, etc.)
            return execution_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"Partial movement for {execution_event.name}, stopped at {source_entity.position}",
                end_position=actual_end_position
            )

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Applied movement for {execution_event.name}"
        )
    
    def _apply_costs(self, completion_event: MovementEvent) -> Optional[MovementEvent]:
        """Apply costs - movement is already consumed per-step in _apply().

        Skip movement cost here since cell-by-cell movement already deducts
        movement per step. Only apply non-movement costs (if any).
        """
        entity = Entity.get(self.source_entity_uuid)
        if entity is None or not isinstance(entity, Entity):
            return completion_event.cancel(status_message=f"Entity not found for {completion_event.name}")

        for cost in completion_event.costs:
            # Skip movement cost - already consumed per-step in _apply()
            if cost.cost_type == "movement":
                continue
            # Apply other costs (actions, bonus_actions, reactions)
            if cost.cost > 0:
                entity.action_economy.consume(cost.cost_type, cost.cost)
            # Apply resource costs
            if cost.resource_cost > 0 and cost.resource_name:
                if not entity.action_economy.consume_resource(cost.resource_name, cost.resource_cost):
                    return completion_event.cancel(
                        status_message=f"Failed to consume resource {cost.resource_name} for {completion_event.name}"
                    )

        return completion_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Successfully applied costs for {completion_event.name}"
        )

    def apply(self, parent_event: Optional[Event] = None) -> Optional[MovementEvent]:
        """Override to provide specific return type."""
        result = super().apply(parent_event)
        return cast(MovementEvent, result) if result else None


class AttackEvent(ActionEvent):
    """An event that represents an attack"""
    name: str = Field(default="Attack",description="An attack event")
    costs: List[BaseCost] = Field(default_factory=list,description="A list of costs for the action")
    weapon_slot: WeaponSlot = Field(description="The slot of the weapon used to attack")
    range: Optional[Range] = Field(default=None,description="The range of the attack")
    is_long_range: bool = Field(default=False,description="True if attack is at long range (beyond normal, within long)")
    is_threatened: bool = Field(default=False,description="True if attacker has hostile entity within 5ft")
    attack_bonus: Optional[ModifiableValue] = Field(default=None,description="The attack bonus of the attack")
    ac: Optional[ModifiableValue] = Field(default=None,description="The ac of the target")
    dice_roll: Optional[DiceRoll] = Field(default=None,description="The result of the dice roll")
    attack_outcome: Optional[AttackOutcome] = Field(default=None,description="The outcome of the attack")
    damages: Optional[List[Damage]] = Field(default=None,description="The damages of the attack")
    damage_rolls: Optional[List[DiceRoll]] = Field(default=None,description="The rolls of the damages")
    event_type: EventType = Field(default=EventType.ATTACK,description="The type of event")

    # Weapon info for combat log generation (populated during event creation)
    weapon_name: Optional[str] = Field(default=None, description="Name of the weapon used")

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for this attack event.

        Uses self.* fields only - no external lookups. Entity names and weapon name
        must be populated when the event is created.
        """
        # Use entity names from self - no external lookups
        source_name = self.source_entity_name or "Unknown"
        target_name = self.target_entity_name or "Unknown"
        weapon_name = self.weapon_name or "Unarmed"

        # We still need target entity for HP lookup (this is acceptable as it's
        # current state, not creation-time state)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        # Build attack roll display
        attack_roll = DiceRollDisplay(
            dice_str="d20",
            results=[],
            bonus=0,
            total=0
        )

        if self.dice_roll:
            results = self.dice_roll.results
            if isinstance(results, list):
                attack_roll.results = list(results)
                attack_roll.all_d20_rolls = list(results)

                # Determine advantage status and which d20 was used
                adv_status = getattr(self.dice_roll, 'advantage_status', None)
                if adv_status:
                    adv_value = adv_status.value.lower() if hasattr(adv_status, 'value') else str(adv_status).lower()
                    attack_roll.advantage_status = adv_value
                    if len(results) >= 2:
                        if adv_value == "advantage":
                            attack_roll.d20_used = max(results)
                        elif adv_value == "disadvantage":
                            attack_roll.d20_used = min(results)
                        else:
                            attack_roll.d20_used = results[0]
                    elif len(results) == 1:
                        attack_roll.d20_used = results[0]
                else:
                    attack_roll.d20_used = results[0] if results else 0
            elif isinstance(results, int):
                attack_roll.results = [results]
                attack_roll.d20_used = results

            attack_roll.bonus = getattr(self.dice_roll, 'bonus', 0)
            attack_roll.total = self.dice_roll.total

        # Build attack breakdown from ModifiableValue
        attack_breakdown: List[ModifierBreakdown] = []
        if self.attack_bonus and hasattr(self.attack_bonus, 'get_breakdown'):
            for mod in self.attack_bonus.get_breakdown():
                attack_breakdown.append(ModifierBreakdown(
                    name=mod.get('name', 'Unknown'),
                    value=mod.get('value', 0),
                    source=mod.get('source', 'self')
                ))

        # Get target AC
        target_ac = 0
        if self.ac:
            target_ac = self.ac.normalized_score
        elif target_entity:
            target_ac = target_entity.ac_bonus().normalized_score

        # Build AC breakdown
        ac_breakdown: List[ModifierBreakdown] = []
        if self.ac and hasattr(self.ac, 'get_breakdown'):
            for mod in self.ac.get_breakdown():
                ac_breakdown.append(ModifierBreakdown(
                    name=mod.get('name', 'Unknown'),
                    value=mod.get('value', 0),
                    source=mod.get('source', 'self')
                ))

        # Determine outcome
        outcome = "unknown"
        is_hit = False
        is_crit = False
        if self.attack_outcome:
            outcome_value = self.attack_outcome.value if hasattr(self.attack_outcome, 'value') else str(self.attack_outcome)
            outcome = outcome_value.lower()
            is_hit = outcome in ("hit", "crit")
            is_crit = outcome == "crit"

        # Build damage roll displays
        damage_roll_displays: List[DamageRollDisplay] = []
        total_damage = 0

        if self.damage_rolls and self.damages:
            for i, dr in enumerate(self.damage_rolls):
                damage = self.damages[i] if i < len(self.damages) else None
                damage_type = damage.damage_type.value if damage and hasattr(damage.damage_type, 'value') else "unknown"

                # Get dice results
                dice_results = []
                if hasattr(dr, 'results'):
                    if isinstance(dr.results, list):
                        dice_results = list(dr.results)
                    elif isinstance(dr.results, int):
                        dice_results = [dr.results]

                # Get damage bonus breakdown
                damage_bonus_breakdown: List[ModifierBreakdown] = []
                if damage and damage.damage_bonus and hasattr(damage.damage_bonus, 'get_breakdown'):
                    for mod in damage.damage_bonus.get_breakdown():
                        damage_bonus_breakdown.append(ModifierBreakdown(
                            name=mod.get('name', 'Unknown'),
                            value=mod.get('value', 0),
                            source=mod.get('source', 'self')
                        ))

                # Build dice string (e.g., "1d6" or "2d6" for crits)
                num_dice = len(dice_results)
                dice_size = damage.damage_dice if damage else 6
                dice_str = f"{num_dice}d{dice_size}"

                damage_roll_displays.append(DamageRollDisplay(
                    dice_str=dice_str,
                    dice_results=dice_results,
                    bonus=dr.bonus if hasattr(dr, 'bonus') else 0,
                    total=dr.total,
                    damage_type=damage_type,
                    bonus_breakdown=damage_bonus_breakdown
                ))

                total_damage += dr.total

        # Get target HP after attack
        target_hp = target_entity.get_hp() if target_entity else None

        # Check for opportunity attack marker in name
        is_opportunity_attack = "opportunity" in (self.name or "").lower()

        # Build markdown-formatted verbosity levels
        compact_text = format_attack_compact(
            source_name, target_name, outcome, total_damage
        )

        verbose_text = format_attack_verbose(
            source_name, target_name, weapon_name,
            attack_roll, target_ac, outcome,
            damage_roll_displays, total_damage,
            is_opportunity_attack
        )

        detailed_text = format_attack_detailed(
            source_name, target_name, weapon_name,
            attack_roll, attack_breakdown,
            target_ac, ac_breakdown, outcome,
            damage_roll_displays, total_damage,
            is_opportunity_attack
        )

        # Build structured data
        data = AttackLogData(
            attacker_name=source_name,
            attacker_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
            weapon_name=weapon_name,
            weapon_slot=self.weapon_slot.value if self.weapon_slot else None,
            attack_roll=attack_roll,
            attack_breakdown=attack_breakdown,
            target_ac=target_ac,
            ac_breakdown=ac_breakdown,
            outcome=outcome,
            is_hit=is_hit,
            is_crit=is_crit,
            damage_rolls=damage_roll_displays,
            total_damage=total_damage,
            target_hp=target_hp,
            is_opportunity_attack=is_opportunity_attack,
            is_long_range=self.is_long_range,
            is_threatened=self.is_threatened
        )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.ATTACK,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else None,
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data=data.model_dump(),
            success=is_hit
        )


class Attack(BaseAction):
    """An action that represents an attack using a weapon
    validation requires the source entity and target entity to be in range and the target entity to be in the line of sight
    of the source entity.

    Two-Weapon Fighting: Off-hand attacks (MELEE_OFF, RANGED_OFF) cost a bonus action instead of an action,
    and don't add ability modifier to damage.

    When used as a template (template=True), target_entity_uuid should be set via set_target_entity()
    before pre_validate() or instantiate().
    """
    name: str = Field(default="Attack", description="An attack action")
    description: str = Field(default="Attack a target", description="A description of the attack action")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Attack targets an entity")
    weapon_slot: WeaponSlot = Field(description="The slot of the weapon used to attack")
    action_category: ActionCategory = Field(default=ActionCategory.ATTACK)
    costs: List[Cost] = Field(default_factory=lambda: [Cost(name="Attack Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)], description="A list of costs for the action")

    @model_validator(mode="after")
    def adjust_cost_for_off_hand(self) -> Self:
        """Off-hand attacks cost bonus_action instead of action (Two-Weapon Fighting)."""
        if self.weapon_slot in (WeaponSlot.MELEE_OFF, WeaponSlot.RANGED_OFF):
            # Replace action cost with bonus_action cost
            self.costs = [Cost(name="Off-Hand Attack Cost", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)]
        return self
    
    
    @staticmethod
    def validate_range(declaration_event: AttackEvent, source_entity_uuid: UUID) -> Optional[AttackEvent]:
        """Validate if the source entity and target entity are in range.

        For ranged weapons:
        - Within normal range: attack allowed
        - Beyond normal but within long range: attack allowed with is_long_range=True (disadvantage)
        - Beyond long range: attack blocked

        For melee weapons:
        - Within reach: attack allowed
        - Beyond reach: attack blocked
        """
        source_entity = Entity.get(source_entity_uuid)
        if not source_entity:
            return declaration_event.cancel(status_message=f"Source entity not found for {declaration_event.name}")
        if not isinstance(source_entity, Entity):
            return declaration_event.cancel(status_message=f"Source entity not found for {declaration_event.name}")
        if not declaration_event.target_entity_uuid:
            return declaration_event.cancel(status_message=f"Target entity uuid not present for {declaration_event.name}")
        target_entity = Entity.get(declaration_event.target_entity_uuid)
        if not target_entity or not isinstance(target_entity, Entity):
            return declaration_event.cancel(status_message=f"Target entity not found for {declaration_event.name}")

        weapon_range = source_entity.get_weapon_range(declaration_event.weapon_slot)
        if weapon_range is None:
            return declaration_event.cancel(status_message=f"Weapon range not found for {declaration_event.name}")

        distance_feet = source_entity.senses.get_feet_distance(target_entity.position)
        is_long_range = False

        if weapon_range.type == RangeType.RANGE:
            # Ranged weapon: check normal and long range
            if distance_feet <= weapon_range.normal:
                # Within normal range - no disadvantage from range
                pass
            elif weapon_range.long is not None and distance_feet <= weapon_range.long:
                # Beyond normal but within long range - disadvantage
                is_long_range = True
            else:
                # Beyond long range (or no long range defined and beyond normal)
                return declaration_event.cancel(status_message=f"Target entity not in range for {declaration_event.name}")

        elif weapon_range.type == RangeType.REACH:
            # Melee weapon: must be within reach (usually 5ft)
            if distance_feet > weapon_range.normal:
                return declaration_event.cancel(status_message=f"Target entity not in reach for {declaration_event.name}")

        return declaration_event.phase_to(
            new_phase=EventPhase.DECLARATION,
            status_message=f"Validated range for {declaration_event.name}",
            range=weapon_range,
            is_long_range=is_long_range
        )

    @staticmethod
    def check_ranged_conditions(declaration_event: AttackEvent, source_entity_uuid: UUID) -> Optional[AttackEvent]:
        """Check conditions that affect ranged attacks.

        Sets is_threatened=True if:
        - Weapon is ranged AND
        - Attacker has a hostile entity within 5ft (threatened)

        This causes disadvantage on the ranged attack roll.
        """
        source_entity = Entity.get(source_entity_uuid)
        if not source_entity or not isinstance(source_entity, Entity):
            return declaration_event.cancel(status_message=f"Source entity not found for {declaration_event.name}")

        is_threatened = False

        # Only check for ranged weapons
        if declaration_event.range and declaration_event.range.type == RangeType.RANGE:
            is_threatened = source_entity.is_threatened()

        return declaration_event.phase_to(
            new_phase=EventPhase.DECLARATION,
            status_message=f"Checked ranged conditions for {declaration_event.name}",
            is_threatened=is_threatened
        )
    
    

    @staticmethod
    def attack_consequences(execution_event: AttackEvent,source_entity_uuid: UUID) -> Optional[AttackEvent]:
            """
            Event-based implementation of an attack.
            This method creates an attack event and processes it through the event system,
            allowing reactions to modify or cancel the attack at various stages.
            
            Returns:
                Optional[AttackEvent]: The completed attack event, or None if the attack was canceled
            """
            source_entity = Entity.get(source_entity_uuid)
            target_entity_uuid = execution_event.target_entity_uuid
            weapon_slot = execution_event.weapon_slot
            if not source_entity:
                return execution_event.cancel(status_message=f"Source entity not found for {execution_event.name}")
            if not isinstance(source_entity, Entity):
                return execution_event.cancel(status_message=f"Source entity not found for {execution_event.name}")
            if not target_entity_uuid:
                return execution_event.cancel(status_message=f"Target entity uuid not present for {execution_event.name}")
            target_entity = Entity.get(target_entity_uuid)
            if not target_entity:
                return execution_event.cancel(status_message=f"Target entity not found for {execution_event.name}")
            if not isinstance(target_entity, Entity):
                return execution_event.cancel(status_message=f"Target entity not found for {execution_event.name}")
            should_clear_source_target = False
            should_clear_target_target = False
            if source_entity.target_entity_uuid != target_entity_uuid:
                should_clear_source_target = True
                source_entity.set_target_entity(target_entity_uuid)
            if target_entity.target_entity_uuid != source_entity_uuid:
                should_clear_target_target = True
                target_entity.set_target_entity(source_entity_uuid)
            
            
            
            # Move to EXECUTION phase
            # Calculate attack bonus and target's AC
            attack_bonus = source_entity.attack_bonus(weapon_slot=weapon_slot, target_entity_uuid=target_entity_uuid)
            ac = target_entity.ac_bonus(source_entity.uuid)
            ac.set_from_target(attack_bonus)
            attack_bonus.set_from_target(ac)

            # Apply ranged attack disadvantages (long range or threatened)
            ranged_disadvantage_modifiers: List[UUID] = []
            is_ranged = execution_event.range is not None and execution_event.range.type == RangeType.RANGE

            if is_ranged and execution_event.is_long_range:
                # Disadvantage for attacking beyond normal range
                modifier_uuid = attack_bonus.self_static.add_advantage_modifier(
                    AdvantageModifier(
                        name="Long Range",
                        value=AdvantageStatus.DISADVANTAGE,
                        source_entity_uuid=source_entity_uuid,
                        target_entity_uuid=target_entity_uuid
                    )
                )
                ranged_disadvantage_modifiers.append(modifier_uuid)

            if is_ranged and execution_event.is_threatened:
                # Disadvantage for ranged attack while hostile within 5ft
                modifier_uuid = attack_bonus.self_static.add_advantage_modifier(
                    AdvantageModifier(
                        name="Threatened (Ranged)",
                        value=AdvantageStatus.DISADVANTAGE,
                        source_entity_uuid=source_entity_uuid,
                        target_entity_uuid=target_entity_uuid
                    )
                )
                ranged_disadvantage_modifiers.append(modifier_uuid)

            # Transition to EXECUTION with attack values
            attack_event = execution_event.phase_to(
                new_phase=EventPhase.EXECUTION,
                status_message="Rolling attack",
                attack_bonus=attack_bonus,
                ac=ac
            )
            
            # If attack was canceled during phase transition, return early
            if attack_event.canceled:
                return attack_event
            
            # Roll attack and post results using the helper methods
            dice_roll = source_entity.roll_d20(attack_bonus,RollType.ATTACK)
            crit_threshold = source_entity.get_crit_threshold(weapon_slot)
            attack_outcome = determine_attack_outcome(dice_roll, ac, crit_threshold)
            
            attack_event = attack_event.post(
                dice_roll=dice_roll,
                attack_outcome=attack_outcome,
                status_message=f"Attack rolled {dice_roll.total} and {attack_outcome}"
            )
            ac.reset_from_target()
            attack_bonus.reset_from_target()
            
            
            # If attack was canceled, return early
            if attack_event.canceled:
                return attack_event

            # On miss: still go through EFFECT phase (so handlers like Guiding Bolt removal fire)
            if attack_event.attack_outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
                attack_event = attack_event.phase_to(
                    EventPhase.EFFECT,
                    status_message=f"Attack missed"
                )
                return attack_event.phase_to(
                    new_phase=EventPhase.COMPLETION,
                    status_message=f"Attack missed"
                )

            # Move to EFFECT phase for damage
            damages = source_entity.get_damages(weapon_slot, target_entity_uuid)
            attack_event = attack_event.phase_to(
                EventPhase.EFFECT,
                is_last=False,  # More EFFECT events coming (post-damage)
                status_message=f"Damages: {[(damage.dice_numbers,damage.damage_dice,damage.damage_bonus.normalized_score if damage.damage_bonus else 0,damage.damage_type) for damage in damages]}",
                damages=damages
            )

            # If attack was canceled during phase transition, return early
            if attack_event.canceled:
                return attack_event

            # Apply damage if there is an attack outcome
            if attack_event.attack_outcome is not None and attack_event.attack_outcome not in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
                # Step 1: Roll damage dice (creates immutable DiceRoll objects)
                # Get extra crit dice (for Brutal Critical, etc.)
                crit_extra_dice = source_entity.get_crit_extra_dice(weapon_slot)
                original_rolls = []
                for damage in damages:
                    dice = damage.get_dice(attack_outcome=attack_event.attack_outcome, crit_extra_dice=crit_extra_dice)
                    roll = dice.roll
                    original_rolls.append(roll)

                # Step 2: Create DAMAGE_ROLL_RESULT event
                # final_rolls starts as copy of original_rolls - handlers will replace entries
                damage_roll_event = DamageRollResultEvent(
                    source_entity_uuid=source_entity.uuid,
                    target_entity_uuid=target_entity.uuid,
                    weapon_slot=weapon_slot,
                    attack_outcome=attack_event.attack_outcome,
                    damages=damages,
                    original_rolls=original_rolls,
                    final_rolls=list(original_rolls),  # Copy - handlers will replace
                    parent_event=attack_event.uuid,
                    phase=EventPhase.DECLARATION
                )

                # Step 3: Transition to EFFECT phase - handlers intercept here
                damage_roll_event = damage_roll_event.phase_to(
                    EventPhase.EFFECT,
                    status_message="Damage dice rolled"
                )

                # Step 4: Apply final_rolls (possibly modified by handlers)
                damage_rolls = damage_roll_event.final_rolls
                total_damage = sum(roll.total for roll in damage_rolls)

                # Step 5: Apply damage (fires TakeDamageEvent internally)
                # Use primary damage type for the event (handlers see total damage)
                target_entity.receive_damage(
                    amount=total_damage,
                    damage_type=damages[0].damage_type,
                    source_entity_uuid=source_entity.uuid,
                    damage_rolls=damage_rolls,
                    damages=damages,
                    parent_event=attack_event.uuid
                )

                attack_event = attack_event.phase_to(
                    new_phase=EventPhase.EFFECT,
                    is_first=False,  # Not the first EFFECT (post-damage)
                    damage_rolls=damage_rolls,
                    status_message=f"Damages taken: {[damage.total for damage in damage_rolls]}"
                )
            else:
                damage_rolls = None
                
            if should_clear_source_target:
                source_entity.clear_target_entity()
            if should_clear_target_target:
                target_entity.clear_target_entity()
            
            # Move to COMPLETION phase
            return attack_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message="Attack completed",
                damage_rolls=damage_rolls,
            )

    def _create_declaration_event(self,parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """ Create the declaration event for the attack action"""
        # Populate entity names and weapon name for combat log generation
        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        source_name = source_entity.name if source_entity else None
        target_name = target_entity.name if target_entity else None

        # Get weapon name
        weapon_name = None
        if source_entity:
            weapon = source_entity.equipment._get_weapon_by_slot(self.weapon_slot)
            weapon_name = weapon.name if weapon and hasattr(weapon, 'name') else "Unarmed"

        return AttackEvent(
            name=f"{self.name}",
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            weapon_slot=self.weapon_slot,
            costs=[BaseCost.model_validate(cost) for cost in self.costs],
            use_register=use_register,
            source_entity_name=source_name,
            target_entity_name=target_name,
            weapon_name=weapon_name
        )
    
    def _validate(self, declaration_event: AttackEvent) -> Optional[AttackEvent]:
        """Validate the attack action"""
        # 1. Validate range (sets is_long_range for ranged weapons)
        range_validated_event = Attack.validate_range(declaration_event, self.source_entity_uuid)
        if range_validated_event is None:
            return declaration_event.cancel(status_message=f"Range validation returned None for {self.name}")
        elif range_validated_event.canceled:
            return range_validated_event

        # 2. Validate line of sight
        line_of_sight_validated_event = validate_line_of_sight(range_validated_event, self.source_entity_uuid)
        if line_of_sight_validated_event is None:
            return declaration_event.cancel(status_message=f"Line of sight validation returned None for {self.name}")
        elif line_of_sight_validated_event.canceled:
            return line_of_sight_validated_event

        # 3. Check ranged conditions (sets is_threatened for ranged attacks)
        ranged_conditions_event = Attack.check_ranged_conditions(line_of_sight_validated_event, self.source_entity_uuid)
        if ranged_conditions_event is None:
            return declaration_event.cancel(status_message=f"Ranged conditions check returned None for {self.name}")
        elif ranged_conditions_event.canceled:
            return ranged_conditions_event

        return ranged_conditions_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Attack validated for {self.name}"
        )
    
    def _apply(self, execution_event: AttackEvent) -> Optional[AttackEvent]:
        """Apply the attack action"""
        return Attack.attack_consequences(execution_event,self.source_entity_uuid)

    def _apply_costs(self, completion_event: AttackEvent) -> Optional[AttackEvent]:
        """Apply the costs of the action"""
        return entity_action_economy_cost_applier(completion_event,self.source_entity_uuid)

    def apply(self, parent_event: Optional[Event] = None) -> Optional[AttackEvent]:
        """Override to provide specific return type."""
        result = super().apply(parent_event)
        return cast(AttackEvent, result) if result else None


# =============================================================================
# Turn-Based Actions: Dash, Dodge, Disengage
# =============================================================================

class Dash(BaseAction):
    """
    Take the Dash action - gain extra movement equal to your speed.

    Applies the Dashing condition which adds movement equal to base speed.
    Lasts until the start of your next turn (duration=1, advanced at turn start).
    """
    name: str = Field(default="Dash")
    description: str = Field(default="Gain extra movement equal to your speed")
    target_type: TargetType = Field(default=TargetType.SELF, description="Dash targets self")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Dash Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ])

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        # Populate entity name for combat log generation
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Dash",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,  # Self-targeted
            costs=[BaseCost.model_validate(cost) for cost in self.costs],
            use_register=use_register,
            source_entity_name=source_name  # Populate for combat log generation
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        # Create Dashing condition with 1 round duration
        dashing = Dashing(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid
        )
        dashing.duration.duration_type = DurationType.ROUNDS
        dashing.duration.duration = 1

        entity.add_condition(dashing)

        base_movement = entity.action_economy.get_base_value("movement")
        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Applied Dashing - gained {base_movement}ft extra movement"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class Dodge(BaseAction):
    """
    Take the Dodge action - focus on avoiding attacks.

    Applies the Dodging condition which gives:
    - Disadvantage on attack rolls against you (if you can see the attacker)
    - Advantage on Dexterity saving throws

    Lasts until the start of your next turn (duration=1, advanced at turn start).
    """
    name: str = Field(default="Dodge")
    description: str = Field(default="Attackers have disadvantage, advantage on DEX saves")
    target_type: TargetType = Field(default=TargetType.SELF, description="Dodge targets self")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Dodge Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ])

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        # Populate entity name for combat log generation
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Dodge",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.costs],
            use_register=use_register,
            source_entity_name=source_name  # Populate for combat log generation
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        # Create Dodging condition with 1 round duration
        dodging = Dodging(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid
        )
        dodging.duration.duration_type = DurationType.ROUNDS
        dodging.duration.duration = 1

        entity.add_condition(dodging)

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message="Applied Dodging - attackers have disadvantage"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class Disengage(BaseAction):
    """
    Take the Disengage action - your movement doesn't provoke opportunity attacks.

    Applies the Disengaging condition which prevents opportunity attacks.
    Lasts until the start of your next turn (duration=1, advanced at turn start).
    """
    name: str = Field(default="Disengage")
    description: str = Field(default="Movement doesn't provoke opportunity attacks")
    target_type: TargetType = Field(default=TargetType.SELF, description="Disengage targets self")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Disengage Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ])

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        # Populate entity name for combat log generation
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Disengage",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.costs],
            use_register=use_register,
            source_entity_name=source_name  # Populate for combat log generation
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        # Create Disengaging condition with 1 round duration
        disengaging = Disengaging(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid
        )
        disengaging.duration.duration_type = DurationType.ROUNDS
        disengaging.duration.duration = 1

        entity.add_condition(disengaging)

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message="Applied Disengaging - movement won't provoke OAs"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


# =============================================================================
# Hide Action
# =============================================================================

class Hide(BaseAction):
    """Take the Hide action - roll Stealth to become Hidden.

    Applies the Hidden condition with stealth_result = d20 + Stealth bonus.
    Hidden entities are not perceivable by observers with passive perception
    below the stealth result. Hidden also grants Unseen Attacker advantage.

    Hidden is removed automatically when the entity attacks, takes damage,
    or becomes incapacitated.
    """
    name: str = Field(default="Hide")
    description: str = Field(default="Attempt to hide (Stealth check)")
    target_type: TargetType = Field(default=TargetType.SELF, description="Hide targets self")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Hide Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ])

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Hide",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.costs],
            use_register=use_register,
            source_entity_name=source_name
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        # Cannot hide while visible to any enemy
        grid = get_map()
        subscribers = grid.get_subscribers_at(entity.position)
        for sub_uuid in subscribers:
            if sub_uuid == entity.uuid:
                continue
            sub = Entity.get(sub_uuid)
            if sub and isinstance(sub, Entity) and entity.is_enemy(sub):
                if entity.uuid in sub.senses.entities:
                    return declaration_event.cancel(
                        status_message="Cannot hide - visible to enemies"
                    )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity or not isinstance(entity, Entity):
            return execution_event.cancel(status_message="Entity not found")

        # Roll Stealth check (d20 + stealth bonus, fires D20RollResultEvent for handlers)
        skill_bonus = entity.skill_bonus(target_entity_uuid=None, skill_name="stealth")
        stealth_roll = entity.roll_d20(skill_bonus, RollType.CHECK, skill_name="stealth")
        stealth_result = stealth_roll.total

        # Apply Hidden condition (no duration — removed by triggers)
        hidden = Hidden(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            stealth_result=stealth_result
        )
        entity.add_condition(hidden)

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Applied Hidden (Stealth DC {stealth_result})"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


# =============================================================================
# Prone Actions: Stand Up, Drop Prone
# =============================================================================

class StandUp(BaseAction):
    """
    Stand up from prone - costs half your movement speed.

    Removes the Prone condition. Can only be used while Prone.
    """
    name: str = Field(default="Stand Up")
    description: str = Field(default="Stand up from prone")
    target_type: TargetType = Field(default=TargetType.SELF, description="Stand Up targets self")
    # Cost is set dynamically based on entity's base movement

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Calculate cost based on entity's base movement
        entity = Entity.get(self.source_entity_uuid)
        if entity:
            base_movement = entity.action_economy.get_base_value("movement")
            half_movement = base_movement // 2
            self.costs = [Cost(
                name="Stand Up Cost",
                cost_type="movement",
                cost=half_movement,
                evaluator=entity_action_economy_cost_evaluator
            )]
        else:
            self.costs = [Cost(
                name="Stand Up Cost",
                cost_type="movement",
                cost=15,  # Default half of 30
                evaluator=entity_action_economy_cost_evaluator
            )]

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        # Populate entity name for combat log generation
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Stand Up",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.costs],
            use_register=use_register,
            source_entity_name=source_name  # Populate for combat log generation
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        # Must be Prone to stand up
        if "Prone" not in entity.active_conditions:
            return declaration_event.cancel(status_message="Not prone - cannot stand up")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        # Remove Prone condition
        entity.remove_condition("Prone")

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message="Stood up from prone"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class DropProne(BaseAction):
    """
    Drop prone - free action (no cost).

    Applies the Prone condition. Can only be used while not Prone.
    """
    name: str = Field(default="Drop Prone")
    description: str = Field(default="Drop to the ground")
    target_type: TargetType = Field(default=TargetType.SELF, description="Drop Prone targets self")
    costs: List[Cost] = Field(default_factory=list)  # Free action

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        # Populate entity name for combat log generation
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Drop Prone",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.costs],
            use_register=use_register,
            source_entity_name=source_name  # Populate for combat log generation
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        # Must not be Prone already
        if "Prone" in entity.active_conditions:
            return declaration_event.cancel(status_message="Already prone")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        # Apply Prone condition (permanent until removed by StandUp)
        prone = Prone(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid
        )
        # Prone is permanent (no duration) - removed by StandUp action
        entity.add_condition(prone)

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message="Dropped prone"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        # No costs for free action, but still call the applier for consistency
        return completion_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message="No costs for Drop Prone"
        )


# =============================================================================
# Jump Action: LOS-Based Position Targeting
# =============================================================================

class JumpEvent(ActionEvent):
    """An event that represents a jump movement."""
    name: str = Field(default="Jump", description="A jump event")
    event_type: EventType = Field(default=EventType.MOVEMENT, description="Movement type event")
    costs: List[BaseCost] = Field(default_factory=list, description="Movement cost for the jump")
    start_position: Tuple[int, int] = Field(description="Starting position")
    end_position: Tuple[int, int] = Field(description="Landing position")
    jump_distance: int = Field(default=0, description="Distance jumped in feet")
    path: Optional[List[Tuple[int, int]]] = Field(default=None, description="Straight-line path through air")

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for this jump event."""
        source_name = self.source_entity_name or "Unknown"

        end_pos = f"({self.end_position[0]},{self.end_position[1]})"
        start_pos = f"({self.start_position[0]},{self.start_position[1]})"

        # Compact: "{cyan:Hero} {yellow:jumps} {green:15ft} to {yellow:(5,3)}"
        compact_text = f"{md_color(source_name, 'cyan')} {md_color('jumps', 'yellow')} {md_color(f'{self.jump_distance}ft', 'green')} to {md_color(end_pos, 'yellow')}"

        # Verbose: includes start position
        verbose_text = f"{md_color(source_name, 'cyan')} {md_color('jumps', 'yellow')} {start_pos} → {md_color(end_pos, 'green')} ({self.jump_distance}ft)"

        # Detailed: includes path if available
        detailed_text = verbose_text
        if self.path and len(self.path) > 2:
            path_str = " -> ".join(f"({p[0]},{p[1]})" for p in self.path)
            detailed_text += f"\n  Air path: {path_str}"

        data = MovementLogData(
            entity_name=source_name,
            entity_uuid=str(self.source_entity_uuid),
            start_position=self.start_position,
            end_position=self.end_position,
            path=self.path or [self.start_position, self.end_position],
            distance_feet=self.jump_distance,
            movement_cost=self.jump_distance
        )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.MOVEMENT,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data=data.model_dump(),
            success=True
        )


class Jump(BaseAction):
    """
    Jump to a visible position within range - uses bonus action, costs movement.

    Jump range = 15ft base + STR bonus (5ft per point of STR modifier above 10).
    This is a simplified implementation combining long jump and high jump concepts.

    Key differences from Move:
    - Uses POSITION_LOS targeting (visible positions, not path-reachable)
    - Can bypass obstacles, difficult terrain, and gaps
    - Still costs movement equal to distance jumped
    - Landing position must be walkable and unoccupied

    When used as a template (template=True), end_position should be set via set_target_position()
    before pre_validate() or instantiate().
    """
    name: str = Field(default="Jump", description="A jump action")
    description: str = Field(default="Jump to a visible position", description="Description")
    target_type: TargetType = Field(default=TargetType.POSITION_LOS, description="Jump uses LOS targeting")
    action_category: ActionCategory = Field(default=ActionCategory.MOVEMENT)
    end_position: Optional[Tuple[int, int]] = Field(default=None, description="Landing position")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Jump Cost", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ])

    def get_range(self) -> Optional[Range]:
        """Calculate jump range based on STR.

        Base range: 15ft
        STR bonus: +5ft per point of STR modifier above 0

        Examples:
        - STR 10 (mod +0): 15ft
        - STR 14 (mod +2): 25ft
        - STR 18 (mod +4): 35ft
        - STR 20 (mod +5): 40ft
        """
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return Range(type=RangeType.REACH, normal=15)

        base_range = 15
        str_mod = entity.ability_scores.strength.modifier
        str_bonus = max(0, str_mod) * 5  # +5ft per positive STR mod point

        total_range = base_range + str_bonus
        return Range(type=RangeType.REACH, normal=total_range)

    def get_valid_positions(self) -> List[Tuple[int, int]]:
        """Get valid landing positions for jump.

        Valid if:
        1. Visible (LOS)
        2. Within jump range
        3. Within available movement
        4. Walkable tile
        5. Unoccupied by other entities
        """
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return []

        action_range = self.get_range()
        max_range = action_range.normal if action_range else 15
        movement_available = entity.action_economy.movement.normalized_score
        grid = get_map()
        valid: List[Tuple[int, int]] = []

        for pos, is_visible in entity.senses.visible.items():
            if not is_visible:
                continue
            if pos == entity.senses.position:
                continue

            # Check distance against jump range
            distance = entity.senses.get_feet_distance(pos)
            if distance > max_range:
                continue

            # Check movement budget (jump costs movement)
            if distance > movement_available:
                continue

            # Check walkability (for landing) - this handles non-blocking entities (dead)
            if not grid.is_walkable_for(pos[0], pos[1], entity.uuid):
                continue

            # Note: is_walkable_for already checks occupancy excluding non-blocking entities,
            # so we don't need a separate occupancy check here

            valid.append(pos)

        return valid

    def set_target_position(self, position: Tuple[int, int]) -> None:
        """Set target position for jump."""
        super().set_target_position(position)
        # Recalculate movement cost
        self._setup_movement_cost()

    def _setup_movement_cost(self) -> None:
        """Set up movement cost based on jump distance."""
        if self.end_position is None:
            return

        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return

        # Calculate distance and add movement cost
        distance = entity.senses.get_feet_distance(self.end_position)

        # Remove existing movement costs
        self.costs = [c for c in self.costs if c.cost_type != "movement"]

        # Add movement cost for the jump distance
        self.costs.append(Cost(
            name="Jump Movement Cost",
            cost_type="movement",
            cost=int(distance),
            evaluator=entity_action_economy_cost_evaluator
        ))

    def instantiate(self, **overrides) -> "Jump":
        """Create an executable Jump instance from this template.

        Uses model_copy() to preserve object types. Costs are reset and
        movement cost is recalculated based on new end_position.
        """
        if not self.template:
            raise ValueError("Can only instantiate from a template")

        # Instance config: new UUID, not a template, not registered (ephemeral)
        # Reset costs to just the bonus action - movement cost added after copy
        update_dict: dict = {
            "uuid": uuid4(),
            "template": False,
            "use_register": False,  # Instances are ephemeral, don't need registry
            "costs": [Cost(name="Jump Cost", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)],
        }
        update_dict.update(overrides)

        # model_copy preserves object types
        instance = self.model_copy(deep=True, update=update_dict)
        # Recalculate movement cost for the new position
        instance._setup_movement_cost()
        return instance

    @staticmethod
    def _get_line_path(start: Tuple[int, int], end: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Get all cells in a straight line from start to end (Bresenham's algorithm)."""
        x0, y0 = start
        x1, y1 = end
        path: List[Tuple[int, int]] = []

        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            path.append((x0, y0))
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

        return path

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[JumpEvent]:
        """Create the declaration event for the jump action."""
        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity:
            return None

        if self.end_position is None:
            return None

        end_position: Tuple[int, int] = self.end_position
        distance = source_entity.senses.get_feet_distance(end_position)

        # Ensure movement cost is set
        self._setup_movement_cost()

        # Calculate straight-line path for opportunity attacks
        line_path = self._get_line_path(source_entity.position, end_position)

        return JumpEvent(
            name=self.name,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            start_position=source_entity.position,
            end_position=end_position,
            jump_distance=int(distance),
            path=line_path,
            costs=[BaseCost.model_validate(cost) for cost in self.costs],
            use_register=use_register,
            source_entity_name=source_entity.name
        )

    def _validate(self, declaration_event: JumpEvent) -> JumpEvent:
        """Validate the jump action."""
        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity:
            return declaration_event.cancel(status_message="Entity not found")

        end_pos = declaration_event.end_position
        grid = get_map()

        # Check visibility (LOS)
        if end_pos not in source_entity.senses.visible or not source_entity.senses.visible[end_pos]:
            return declaration_event.cancel(status_message=f"Position {end_pos} not visible")

        # Check range
        action_range = self.get_range()
        max_range = action_range.normal if action_range else 15
        distance = source_entity.senses.get_feet_distance(end_pos)
        if distance > max_range:
            return declaration_event.cancel(status_message=f"Position {end_pos} out of jump range ({distance}ft > {max_range}ft)")

        # Check movement available
        movement_available = source_entity.action_economy.movement.normalized_score
        if distance > movement_available:
            return declaration_event.cancel(status_message=f"Not enough movement ({distance}ft > {movement_available}ft)")

        # Check walkability - this handles occupancy (excluding non-blocking entities like dead)
        if not grid.is_walkable_for(end_pos[0], end_pos[1], source_entity.uuid):
            return declaration_event.cancel(status_message=f"Position {end_pos} not walkable or occupied")

        # Note: is_walkable_for already checks occupancy excluding non-blocking entities,
        # so we don't need a separate occupancy check here

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated jump to {end_pos}"
        )

    def _apply(self, execution_event: JumpEvent) -> JumpEvent:
        """Apply the jump - teleport entity to target position."""
        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity:
            return execution_event.cancel(status_message="Entity not found")

        # Move to effect phase
        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Jumping to {execution_event.end_position}"
        )
        if effect_event.canceled:
            return effect_event

        # Teleport entity (bypasses path - that's the point of jumping!)
        # Note: Senses updated reactively via SPATIAL events from GridMap.move_entity()
        Entity.update_entity_position(source_entity, execution_event.end_position)

        # Verify landing
        if source_entity.position != execution_event.end_position:
            return effect_event.cancel(status_message=f"Failed to land at {execution_event.end_position}")

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Jumped to {execution_event.end_position}"
        )

    def _apply_costs(self, completion_event: JumpEvent) -> JumpEvent:
        """Apply the costs of the jump (bonus action + movement)."""
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


# =============================================================================
# Shove Action: BG3-Style Push or Knock Prone
# =============================================================================

class ShoveEvent(ActionEvent):
    """An event that represents a shove action.

    Shove is a BG3-style bonus action that pushes adjacent enemies.
    Key mechanics:
    - Cost: Bonus Action
    - Range: 5ft (adjacent only)
    - Contest: Shover's Athletics CHECK vs target's passive skill DC
    - Allies: Auto-succeed (no check required)
    - Weight limit: STR score × 12
    """
    name: str = Field(default="Shove", description="A shove event")
    event_type: EventType = Field(default=EventType.BASE_ACTION, description="Event type")
    costs: List[BaseCost] = Field(default_factory=list, description="Costs for the action")

    # Target info
    target_weight: int = Field(default=0, description="Target's weight in pounds")
    max_shove_weight: int = Field(default=0, description="Max weight shover can push (STR × 12)")

    # Contest info
    shover_athletics: Optional[ModifiableValue] = Field(default=None, description="Shover's Athletics bonus")
    target_passive: int = Field(default=10, description="Target's passive Athletics or Acrobatics")
    target_resistance_skill: str = Field(default="athletics", description="Which skill target used")
    dice_roll: Optional[DiceRoll] = Field(default=None, description="Shover's Athletics check roll")
    contest_success: Optional[bool] = Field(default=None, description="Whether the contest was won")

    # Push result
    push_distance: int = Field(default=0, description="How far target was pushed (feet)")
    push_direction: Tuple[int, int] = Field(default=(0, 0), description="Direction of push (dx, dy)")
    end_position: Optional[Tuple[int, int]] = Field(default=None, description="Target's final position after push")
    knocked_prone: bool = Field(default=False, description="Whether target was knocked prone instead")
    is_ally: bool = Field(default=False, description="Whether target is an ally (auto-succeed)")

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate combat log for shove."""
        source_name = self.source_entity_name or "Unknown"
        target_name = self.target_entity_name or "Unknown"

        # Build markdown-formatted verbosity levels

        # COMPACT: Just the outcome with arrival position
        if self.contest_success is False:
            compact_text = f"{md_color(source_name, 'cyan')} fails to shove {md_color(target_name, 'yellow')}"
        elif self.knocked_prone:
            compact_text = f"{md_color(source_name, 'cyan')} knocks {md_color(target_name, 'yellow')} {md_color('prone', 'red')}!"
        elif self.push_distance > 0:
            pos_str = f"→ {self.end_position}" if self.end_position else ""
            compact_text = f"{md_color(source_name, 'cyan')} shoves {md_color(target_name, 'yellow')} {md_color(f'{self.push_distance}ft', 'green')} {pos_str}"
        else:
            compact_text = f"{md_color(source_name, 'cyan')} shoves {md_color(target_name, 'yellow')} (blocked)"

        # VERBOSE: Add the roll info
        verbose_text = compact_text
        if not self.is_ally and self.dice_roll is not None:
            roll_total = self.dice_roll.total
            success_str = md_color("success", "green") if self.contest_success else md_color("fail", "red")
            verbose_text += f"\n  Athletics: d20({md_color(str(roll_total), 'cyan')}) vs DC {self.target_passive} → {success_str}"
        elif self.is_ally:
            verbose_text += f" ({md_color('ally', 'green')})"

        # DETAILED: Add more context
        detailed_text = verbose_text
        if self.contest_success:
            if self.knocked_prone:
                detailed_text += f"\n  Effect: Target knocked {md_color('prone', 'red')}"
            else:
                detailed_text += f"\n  Direction: {self.push_direction}"
                detailed_text += f"\n  Weight: {self.target_weight}lbs (max: {self.max_shove_weight}lbs)"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.ACTION,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else None,
            compact=compact_text,
            verbose=verbose_text,
            detailed=detailed_text,
            data={
                "action_type": "shove",
                "target_weight": self.target_weight,
                "max_shove_weight": self.max_shove_weight,
                "contest_success": self.contest_success,
                "push_distance": self.push_distance,
                "push_direction": list(self.push_direction),
                "end_position": list(self.end_position) if self.end_position else None,
                "knocked_prone": self.knocked_prone,
                "is_ally": self.is_ally
            },
            success=self.contest_success or False
        )


class Shove(BaseAction):
    """BG3-style Shove action - push adjacent enemies.

    Costs a bonus action. Pushes target 5-20ft based on STR, or knocks prone.

    Mechanics (BG3-style):
    - Range: 5ft (adjacent only)
    - Contest: Shover's Athletics CHECK vs target's passive DC
    - Target DC: 10 + max(Athletics, Acrobatics) bonus + advantage modifier
    - Allies: Auto-succeed (no check required)
    - Weight limit: Can't shove targets heavier than STR × 12 lbs
    - Distance: 5ft base + 5ft per positive STR modifier (max 20ft)

    Forced movement does NOT trigger opportunity attacks.
    """
    name: str = Field(default="Shove", description="Shove action")
    description: str = Field(default="Push an adjacent enemy", description="Description")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Shove targets an entity")
    knock_prone: bool = Field(default=False, description="If True, knock prone instead of push")
    include_allies: bool = Field(default=True, description="Whether to include allies as valid targets")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Shove Cost", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ])

    @staticmethod
    def get_max_shove_weight(entity: 'Entity') -> int:
        """Calculate max weight entity can shove (STR × 12)."""
        return entity.ability_scores.strength.ability_score.score * 12

    @staticmethod
    def get_push_distance(entity: 'Entity') -> int:
        """Calculate push distance based on STR.

        Base: 5ft
        Bonus: +5ft per positive STR modifier point
        Max: 20ft
        """
        str_mod = entity.ability_scores.strength.modifier
        bonus = max(0, str_mod) * 5
        return min(20, max(5, 5 + bonus))

    @staticmethod
    def get_push_direction(source_pos: Tuple[int, int], target_pos: Tuple[int, int]) -> Tuple[int, int]:
        """Calculate push direction as unit vector from source to target."""
        dx = target_pos[0] - source_pos[0]
        dy = target_pos[1] - source_pos[1]

        # Normalize to unit direction
        if dx != 0:
            dx = 1 if dx > 0 else -1
        if dy != 0:
            dy = 1 if dy > 0 else -1

        return (dx, dy)

    @staticmethod
    def calculate_final_position(
        start: Tuple[int, int],
        direction: Tuple[int, int],
        distance_feet: int,
        target_uuid: 'UUID'
    ) -> Tuple[Tuple[int, int], int, bool]:
        """Calculate where target lands after being pushed.

        Walks cells in push direction until:
        - Reached desired distance, OR
        - Hit unwalkable tile, OR
        - Hit cell occupied by another entity

        Target MUST land on a walkable tile.

        Args:
            start: Target's current position
            direction: Push direction as (dx, dy)
            distance_feet: How far to push in feet
            target_uuid: UUID of entity being pushed (excluded from occupancy check)

        Returns:
            (final_position, actual_distance_feet, was_blocked)
        """
        grid = get_map()
        current = start
        cells_to_move = distance_feet // 5  # 5ft per cell
        actual_cells = 0
        blocked = False

        for _ in range(cells_to_move):
            next_pos = (current[0] + direction[0], current[1] + direction[1])

            # Check if next cell is walkable for the target
            if not grid.is_walkable_for(next_pos[0], next_pos[1], target_uuid):
                blocked = True
                break

            current = next_pos
            actual_cells += 1

        return current, actual_cells * 5, blocked

    def pre_validate(self) -> bool:
        """Quick validation for template filtering."""
        if not super().pre_validate():
            return False

        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source or not target:
            return False

        # Check adjacency (5ft)
        distance = source.senses.get_feet_distance(target.position)
        if distance > 5:
            return False

        # Check weight limit
        max_weight = self.get_max_shove_weight(source)
        if target.weight > max_weight:
            return False

        # Check visibility (LOS)
        if target.uuid not in source.senses.entities:
            return False

        return True

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[ShoveEvent]:
        """Create declaration event for shove."""
        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source or not target:
            return None

        return ShoveEvent(
            name=self.name,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.costs],
            use_register=use_register,
            source_entity_name=source.name,
            target_entity_name=target.name,
            target_weight=target.weight,
            max_shove_weight=self.get_max_shove_weight(source),
            is_ally=source.is_ally(target)
        )

    def _validate(self, declaration_event: ShoveEvent) -> ShoveEvent:
        """Validate the shove action."""
        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(declaration_event.target_entity_uuid) if declaration_event.target_entity_uuid else None

        if not source or not target:
            return declaration_event.cancel(status_message="Entity not found")

        # Check adjacency
        distance = source.senses.get_feet_distance(target.position)
        if distance > 5:
            return declaration_event.cancel(status_message=f"Target not adjacent ({distance}ft)")

        # Check weight
        if target.weight > declaration_event.max_shove_weight:
            return declaration_event.cancel(
                status_message=f"Target too heavy ({target.weight}lbs > {declaration_event.max_shove_weight}lbs)"
            )

        # Check LOS
        if target.uuid not in source.senses.entities:
            return declaration_event.cancel(status_message="Target not visible")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message="Shove validated"
        )

    def _apply(self, execution_event: ShoveEvent) -> ShoveEvent:
        """Apply the shove - contest and push/prone."""
        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not source or not target:
            return execution_event.cancel(status_message="Entity not found")

        # ALLIES AUTO-SUCCEED (BG3 Patch 6 behavior)
        if source.is_ally(target):
            contest_success = True
            dice_roll = None
            target_passive = 0
            target_skill = "none"
        else:
            # CONTESTED CHECK: Active Athletics roll vs Passive DC
            athletics_bonus = source.skill_bonus(target.uuid, "athletics")

            # Target uses best of Athletics or Acrobatics passive
            passive_athletics = target.passive_skill("athletics")
            passive_acrobatics = target.passive_skill("acrobatics")

            if passive_athletics >= passive_acrobatics:
                target_passive = passive_athletics
                target_skill = "athletics"
            else:
                target_passive = passive_acrobatics
                target_skill = "acrobatics"

            # Roll Athletics check
            dice_roll = source.roll_d20(athletics_bonus, RollType.CHECK)
            contest_success = dice_roll.total >= target_passive

        # Update event with contest results
        execution_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            shover_athletics=athletics_bonus if not source.is_ally(target) else None,
            dice_roll=dice_roll,
            target_passive=target_passive,
            target_resistance_skill=target_skill,
            contest_success=contest_success,
            status_message=f"Contest {'succeeded' if contest_success else 'failed'}"
        )

        if execution_event.canceled:
            return execution_event

        # CONTEST FAILED
        if not contest_success:
            return execution_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message="Shove failed - target resisted"
            )

        # CONTEST SUCCEEDED - PUSH OR PRONE
        if self.knock_prone:
            # Knock prone instead of push
            prone_condition = Prone(
                source_entity_uuid=source.uuid,
                target_entity_uuid=target.uuid
            )
            target.add_condition(prone_condition)

            return execution_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                knocked_prone=True,
                status_message=f"{target.name} knocked prone"
            )

        # PUSH
        direction = self.get_push_direction(source.position, target.position)
        distance = self.get_push_distance(source)
        final_pos, actual_dist, blocked = self.calculate_final_position(
            target.position, direction, distance, target.uuid
        )

        push_direction = direction
        push_distance = actual_dist

        if actual_dist > 0:
            # Create ForcedMovementEvent (does NOT trigger OA) - child of shove effect
            forced_event = ForcedMovementEvent(
                source_entity_uuid=source.uuid,
                target_entity_uuid=target.uuid,
                source_entity_name=source.name,
                target_entity_name=target.name,
                start_position=target.position,
                end_position=final_pos,
                direction=direction,
                intended_distance=distance,
                actual_distance=actual_dist,
                blocked_by_obstacle=blocked,
                cause="shove",
                phase=EventPhase.DECLARATION,
                parent_event=execution_event.uuid
            )

            # Move to completion (triggers GridMap spatial events via Entity.update_entity_position)
            forced_event = forced_event.phase_to(EventPhase.COMPLETION)

            # Actually move the target - spatial events are children of ForcedMovementEvent
            # Note: Senses updated reactively via SPATIAL events from GridMap.move_entity()
            Entity.update_entity_position(target, final_pos, parent_event=forced_event.uuid)

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            push_distance=push_distance,
            push_direction=push_direction,
            end_position=final_pos,
            status_message=f"Shoved {target.name} {push_distance}ft" + (" (blocked)" if blocked else "")
        )

    def _apply_costs(self, completion_event: ShoveEvent) -> ShoveEvent:
        """Apply shove costs (bonus action)."""
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


# =============================================================================
# Spell System: SpellAction Base Class
# =============================================================================

class SpellEvent(ActionEvent):
    """An event that represents a spell being cast."""
    name: str = Field(default="Spell Cast", description="A spell cast event")
    event_type: EventType = Field(default=EventType.CAST_SPELL, description="The type of event")
    spell_level: int = Field(default=0, description="Base spell level (0 = cantrip)")
    cast_at_level: int = Field(default=0, description="Actual slot level used (0 = cantrip)")
    spell_school: str = Field(default="evocation", description="School of magic")

    # Attack spell fields (optional)
    attack_bonus: Optional[ModifiableValue] = Field(default=None, description="The spell attack bonus")
    ac: Optional[ModifiableValue] = Field(default=None, description="The target's AC")
    dice_roll: Optional[DiceRoll] = Field(default=None, description="The attack roll result")
    attack_outcome: Optional[AttackOutcome] = Field(default=None, description="The attack outcome")

    # Save spell fields (optional)
    save_ability: Optional[str] = Field(default=None, description="Ability for saving throw")
    save_dc: Optional[int] = Field(default=None, description="Save DC")
    save_success: Optional[bool] = Field(default=None, description="Whether the save succeeded")
    save_roll: Optional[DiceRoll] = Field(default=None, description="The save roll result")
    save_bonus: Optional[int] = Field(default=None, description="Target's save bonus")

    # Damage fields
    damages: Optional[List[Damage]] = Field(default=None, description="The damages dealt")
    damage_rolls: Optional[List[DiceRoll]] = Field(default=None, description="The damage roll results")

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate combat log for spell effects.

        Handles:
        - Multi-target spells via parent's _generate_multi_target_log()
        - Save-based spells (Fireball, etc.) with save rolls and damage
        - Attack spells (Fire Bolt) - delegate to generic format for now
        """
        # Multi-target spells use summary log - sub_entries come from child events
        if self.total_targets > 0:
            return self._generate_multi_target_log()

        # Save-based spell (has save_dc and save_success)
        if self.save_dc is not None and self.save_success is not None:
            return self._generate_save_spell_log()

        # Auto-hit spell with damage (Magic Missile darts)
        if self.damage_rolls and self.target_entity_name:
            return self._generate_autohit_spell_log()

        # Attack spell (has attack_outcome) - use generic action log for now
        # Could add _generate_attack_spell_log() following AttackEvent pattern

        # Fallback to generic action log
        parent_log = super().generate_combat_log()
        if parent_log is not None:
            return parent_log
        # If parent returns None, create a minimal log
        return CombatLogEntry(
            entry_type=CombatLogEntryType.ACTION,
            source_name=self.source_entity_name or "Unknown",
            source_uuid=str(self.source_entity_uuid) if self.source_entity_uuid else "",
            compact=f"{self.source_entity_name or 'Unknown'} casts {self.name or 'spell'}",
            verbose=f"{self.source_entity_name or 'Unknown'} casts {self.name or 'spell'}",
            detailed=f"{self.source_entity_name or 'Unknown'} casts {self.name or 'spell'}",
            data={},
            success=True
        )

    def _generate_save_spell_log(self) -> CombatLogEntry:
        """Generate combat log for save-based spell (single target)."""
        target_name = self.target_entity_name or "Unknown"
        caster_name = self.source_entity_name or "Unknown"
        spell_name = self.name or "Spell"
        ability = (self.save_ability or "dexterity").upper()[:3]  # "DEX", "WIS", etc.
        dc = self.save_dc or 10
        success = self.save_success or False
        total_dmg = self.total_damage or 0

        # Build save roll display
        save_roll_display = DiceRollDisplay(dice_str="d20", results=[], bonus=0, total=0)
        if self.save_roll:
            results = self.save_roll.results
            if isinstance(results, list):
                results_list = list(results)
            else:
                results_list = [results] if results else []
            save_roll_display = DiceRollDisplay(
                dice_str="d20",
                results=results_list,
                bonus=self.save_bonus or 0,
                total=self.save_roll.total,
                d20_used=results_list[0] if results_list else None
            )

        # Build damage roll displays
        damage_displays: List[DamageRollDisplay] = []
        damage_type = "damage"
        base_damage = 0
        if self.damage_rolls:
            for i, dr in enumerate(self.damage_rolls):
                dmg_type = self.damages[i].damage_type.value if self.damages and i < len(self.damages) else "damage"
                damage_type = dmg_type  # Use last damage type
                dr_results = dr.results
                if isinstance(dr_results, list):
                    dice_results = list(dr_results)
                else:
                    dice_results = [dr_results] if dr_results else []
                base_damage = dr.total  # Before halving
                damage_displays.append(DamageRollDisplay(
                    dice_str=f"{len(dice_results)}d{self.damages[i].damage_dice if self.damages and i < len(self.damages) else 6}",
                    dice_results=dice_results,
                    bonus=0,
                    total=dr.total,
                    damage_type=dmg_type
                ))

        # COMPACT: One-liner outcome
        outcome_str = md_color("SAVE", "green") if success else md_color("FAIL", "red")
        half_note = " (half)" if success and total_dmg > 0 else ""
        compact = f"{md_color(target_name, 'yellow')}: {ability} save {outcome_str}, {md_color(str(total_dmg), 'red')} {damage_type}{half_note}"

        # VERBOSE: Save roll + damage
        verbose_lines = [compact]
        if save_roll_display.total > 0:
            d20_val = save_roll_display.d20_used or (save_roll_display.results[0] if save_roll_display.results else "?")
            bonus_str = f"+{save_roll_display.bonus}" if save_roll_display.bonus >= 0 else str(save_roll_display.bonus)
            verbose_lines.append(f"  Save: d20({d20_val}) {bonus_str} = {save_roll_display.total} vs DC {dc}")
        if damage_displays:
            dr = damage_displays[0]
            dice_str = ",".join(str(d) for d in dr.dice_results) if dr.dice_results else "?"
            verbose_lines.append(f"  Damage: {dr.dice_str}({dice_str}) = {dr.total} {dr.damage_type}")
        verbose = "\n".join(verbose_lines)

        # DETAILED: Same as verbose for now (could add modifier breakdowns)
        detailed = verbose

        # Build structured data
        data = SpellSaveLogData(
            caster_name=caster_name,
            caster_uuid=str(self.source_entity_uuid) if self.source_entity_uuid else "",
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
            spell_name=spell_name,
            spell_level=self.spell_level,
            save_ability=self.save_ability or "dexterity",
            save_dc=dc,
            save_roll=save_roll_display,
            save_success=success,
            damage_rolls=damage_displays,
            base_damage=base_damage,
            final_damage=total_dmg,
            damage_type=damage_type
        )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.SPELL_SAVE,
            source_name=caster_name,
            source_uuid=str(self.source_entity_uuid) if self.source_entity_uuid else "",
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
            compact=compact,
            verbose=verbose,
            detailed=detailed,
            data=data.model_dump(),
            success=not success  # Spell "succeeds" when target fails save
        )

    def _generate_autohit_spell_log(self) -> CombatLogEntry:
        """Generate combat log for auto-hit spell (Magic Missile darts)."""
        target_name = self.target_entity_name or "Unknown"
        caster_name = self.source_entity_name or "Unknown"
        spell_name = self.name or "Spell"
        total_dmg = self.total_damage or 0

        # Get damage type from first damage
        damage_type = "force"
        if self.damages and len(self.damages) > 0:
            damage_type = self.damages[0].damage_type.value

        # Build damage roll display string
        dice_str = ""
        if self.damage_rolls and len(self.damage_rolls) > 0:
            dr = self.damage_rolls[0]
            results = dr.results if isinstance(dr.results, list) else [dr.results]
            # Format: "1d4+1: 3+1"
            num_dice = len(results)
            die_size = self.damages[0].damage_dice if self.damages else 4
            bonus = self.damages[0].damage_bonus.normalized_score if self.damages and self.damages[0].damage_bonus else 1
            dice_part = f"{num_dice}d{die_size}"
            if bonus != 0:
                dice_part += f"+{bonus}"
            results_str = "+".join(str(r) for r in results)
            if bonus != 0:
                results_str += f"+{bonus}"
            dice_str = f" ({dice_part}: {results_str})"

        # COMPACT: "Magic Missile hits Skeleton for 4 force damage"
        compact = f"{md_color(spell_name, 'yellow')} {md_color('hits', 'green')} {md_color(target_name, 'cyan')} for {md_color(str(total_dmg), 'red')} {damage_type} damage"

        # VERBOSE: Add dice details
        verbose = compact + dice_str

        # DETAILED: Same as verbose for auto-hit spells
        detailed = verbose

        return CombatLogEntry(
            entry_type=CombatLogEntryType.SPELL_DAMAGE,
            source_name=caster_name,
            source_uuid=str(self.source_entity_uuid) if self.source_entity_uuid else "",
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
            compact=compact,
            verbose=verbose,
            detailed=detailed,
            data={
                "spell_name": spell_name,
                "target_name": target_name,
                "damage": total_dmg,
                "damage_type": damage_type
            },
            success=True
        )


class SpellAction(BaseAction):
    """Base class for all spells. Handles metadata and variant generation.

    Each spell subclass must implement _apply() with its own logic.
    This base class provides:
    - Spell metadata (level, school, concentration)
    - Variant generation for upcasting
    - Cost generation (action + spell slot)

    Note: Unlike weapon attacks, spells handle their own _apply() logic entirely.
    Attack spells should borrow the pattern from Attack._apply() for set_from_target().
    """

    action_category: ActionCategory = Field(default=ActionCategory.SPELL)

    # Spell metadata
    spell_level: int = Field(default=0, description="Base spell level (0 = cantrip)")
    spell_school: str = Field(default="evocation", description="School of magic")
    concentration: bool = Field(default=False, description="Whether spell requires concentration")

    # Spell range (similar to weapon range)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Range of the spell"
    )

    # Variant tracking (set by variant generation)
    cast_at_level: int = Field(default=0, description="Actual slot level used (0 = cantrip)")
    is_variant: bool = Field(default=False, description="Whether this is an upcast variant")

    # Caster level (for cantrip scaling)
    caster_level: int = Field(default=1, description="Level of the caster (for cantrip scaling)")

    # Default cost is 1 action (no spell slot for cantrips)
    costs: List[Cost] = Field(
        default_factory=lambda: [Cost(name="Cast Spell", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)],
        description="Action cost for casting"
    )

    def get_upcast_bonus(self) -> int:
        """Get levels above base spell level (for upcast scaling)."""
        return max(0, self.cast_at_level - self.spell_level)

    def generate_variants(self, entity: 'Entity') -> List['SpellAction']:
        """Generate spell variants for available spell slots.

        For cantrips: returns a single variant with cast_at_level=0
        For leveled spells: returns a variant for each available slot >= spell_level

        Args:
            entity: The entity that would cast the spell

        Returns:
            List of SpellAction variants with appropriate costs
        """
        variants: List['SpellAction'] = []

        if self.spell_level == 0:
            # Cantrip - single variant, no slot cost
            variants.append(self._create_variant(cast_at_level=0))
        else:
            # Leveled spell - variant per available slot
            for slot_level in range(self.spell_level, 10):
                if entity.has_spell_slot(slot_level):
                    variants.append(self._create_variant(cast_at_level=slot_level))

        return variants

    def _create_variant(self, cast_at_level: int, **overrides) -> 'SpellAction':
        """Clone self with modified cast level and appropriate costs.

        Uses model_copy() to preserve object types (e.g., AoE shape subclasses).

        Args:
            cast_at_level: The spell slot level to use (0 for cantrips)
            **overrides: Additional field overrides

        Returns:
            A new SpellAction instance configured for this cast level
        """
        # Variant config: new UUID, not a template, not registered (ephemeral)
        update_dict: dict = {
            "uuid": uuid4(),
            "cast_at_level": cast_at_level,
            "is_variant": True,
            "template": False,
            "use_register": False,  # Variants are ephemeral, don't need registry
            "costs": self._get_costs_for_level(cast_at_level),
        }
        update_dict.update(overrides)

        # model_copy preserves object types (aoe_shape subclasses, etc.)
        return self.model_copy(deep=True, update=update_dict)

    def _get_costs_for_level(self, level: int) -> List[Cost]:
        """Get costs for casting at a specific level.

        Args:
            level: The spell slot level (0 for cantrips)

        Returns:
            List of Cost objects (action + spell slot if level > 0)
        """
        costs = [Cost(name="Cast Spell", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)]
        if level > 0:
            cost_type = cast(CostType, f"spell_slot_{level}")
            costs.append(Cost(name=f"Spell Slot L{level}", cost_type=cost_type, cost=1, evaluator=entity_action_economy_cost_evaluator))
        return costs

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the declaration event for this spell."""
        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        source_name = source_entity.name if source_entity else None
        target_name = target_entity.name if target_entity else None

        return SpellEvent(
            name=f"{self.name}",
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.costs],
            use_register=use_register,
            source_entity_name=source_name,
            target_entity_name=target_name,
            spell_level=self.spell_level,
            cast_at_level=self.cast_at_level,
            spell_school=self.spell_school
        )

    def _apply_costs(self, completion_event: ActionEvent) -> Optional[ActionEvent]:
        """Apply the costs of the spell."""
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)

    def _get_cantrip_dice_count(self, caster_level: int) -> int:
        """Get number of damage dice for cantrips based on caster level.

        Cantrips scale at levels 5, 11, and 17.
        """
        if caster_level >= 17:
            return 4
        if caster_level >= 11:
            return 3
        if caster_level >= 5:
            return 2
        return 1


#factories, these are redundant examples to create the same actions using the structured action approach
# used for prompting LLMs that most likely will use the StructuredAction approach when implementing Content

def attack_factory(source_entity_uuid: UUID, target_entity_uuid: UUID, weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN) -> Optional[BaseAction]:
    attack = StructuredAction(
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=target_entity_uuid,
        name="Attack",
        description="An attack action",
        costs=[Cost(name="Attack Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)],
        prerequisites=OrderedDict({
            "validate_range": Attack.validate_range,
            "validate_line_of_sight": validate_line_of_sight
        }),
        consequences=OrderedDict({
            "attack_consequences": Attack.attack_consequences
        }),
        cost_applier=entity_action_economy_cost_applier
    )
    return attack


# =============================================================================
# OBJECT Actions (Items on Grid)
# =============================================================================

class PickUp(BaseAction):
    """Pick up an item from the ground. Free action (no cost).

    Uses target_entity_uuid to hold the item UUID (items are BaseBlocks
    registered in _registry, so BaseBlock.get(uuid) finds them).
    """
    name: str = Field(default="Pick Up")
    description: str = Field(default="Pick up an item from the ground")
    target_type: TargetType = Field(default=TargetType.OBJECT)
    costs: List[Cost] = Field(default_factory=list)  # Free action

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        item = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not isinstance(item, BaseItem) or not item.is_pickable:
            return declaration_event.cancel(status_message="Cannot pick up this object")

        if not entity.inventory.can_add(item):
            return declaration_event.cancel(status_message="Inventory full")

        item_pos = get_map().get_object_position(item.uuid)
        if item_pos is None:
            return declaration_event.cancel(status_message="Item not on the ground")
        if entity.senses.get_feet_distance(item_pos) > 5:
            return declaration_event.cancel(status_message="Item too far away")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated Pick Up {item.name}"
        )

    def _apply(self, execution_event: ActionEvent, **kwargs) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        item = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not entity or not isinstance(item, BaseItem):
            return execution_event.cancel(status_message="Entity or item not found")

        entity.loot_item(item)
        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Picked up {item.name}"
        )


class AttackObject(BaseAction):
    """Attack a breakable object. Costs 1 action. Auto-hit, rolls weapon damage.

    Uses target_entity_uuid to hold the item UUID.
    """
    name: str = Field(default="Attack Object")
    description: str = Field(default="Attack a breakable object")
    target_type: TargetType = Field(default=TargetType.OBJECT)
    action_category: ActionCategory = Field(default=ActionCategory.ATTACK)
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Attack Object Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ])

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        item = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not isinstance(item, BaseItem) or not item.is_targetable or not item.is_breakable():
            return declaration_event.cancel(status_message="Cannot attack this object")

        item_pos = get_map().get_object_position(item.uuid)
        if item_pos is None:
            return declaration_event.cancel(status_message="Object not on the ground")
        if entity.senses.get_feet_distance(item_pos) > 5:
            return declaration_event.cancel(status_message="Object too far away")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated Attack Object {item.name}"
        )

    def _apply(self, execution_event: ActionEvent, **kwargs) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        item = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not entity or not isinstance(item, BaseItem):
            return execution_event.cancel(status_message="Entity or item not found")

        # Auto-hit: roll weapon damage directly
        weapon_slot = WeaponSlot.MELEE_MAIN
        damages = entity.equipment.get_damages(weapon_slot, entity.ability_scores)
        total_damage = 0
        for dmg in damages:
            dice = dmg.get_dice(AttackOutcome.HIT)
            total_damage += dice.roll.total
        main_type = entity.equipment.get_main_damage_type(weapon_slot)

        actual = item.receive_damage(total_damage, main_type, entity.uuid)
        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Dealt {actual} {main_type.value} damage to {item.name}"
        )


class Drop(BaseAction):
    """Drop an item from inventory onto the ground at a position.

    Position-target action (POSITION_LOS) bound to a specific item.
    Valid positions: entity's own cell + adjacent cells (range 5ft).
    Created on-the-fly via execute_drop() — same pattern as future Use actions.

    The item_uuid is bound at creation time (one Drop per item).
    """
    name: str = Field(default="Drop")
    description: str = Field(default="Drop an item from inventory")
    target_type: TargetType = Field(default=TargetType.POSITION_LOS)
    costs: List[Cost] = Field(default_factory=list)  # Free action
    item_uuid: Optional[UUID] = Field(default=None, description="UUID of the item to drop (bound at creation)")

    def get_range(self) -> Optional[Range]:
        return Range(type=RangeType.REACH, normal=5)

    def get_valid_positions(self) -> List[Tuple[int, int]]:
        """Adjacent + own position, must be walkable."""
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return []
        valid: List[Tuple[int, int]] = [entity.position]  # Can drop at own feet
        for pos, is_visible in entity.senses.visible.items():
            if not is_visible:
                continue
            if pos == entity.position:
                continue
            if entity.senses.get_feet_distance(pos) <= 5:
                valid.append(pos)
        return valid

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        if self.item_uuid is None:
            return declaration_event.cancel(status_message="No item specified")
        if not entity.inventory.has_item(self.item_uuid):
            return declaration_event.cancel(status_message="Item not in inventory")

        if self.end_position is None:
            return declaration_event.cancel(status_message="No drop position specified")

        # Validate distance
        dx = abs(self.end_position[0] - entity.position[0])
        dy = abs(self.end_position[1] - entity.position[1])
        if dx > 1 or dy > 1:
            return declaration_event.cancel(status_message="Drop position too far (max 5ft)")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message="Validated Drop"
        )

    def _apply(self, execution_event: ActionEvent, **kwargs) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity or self.item_uuid is None:
            return execution_event.cancel(status_message="Entity or item not found")

        dropped = entity.drop_item(self.item_uuid, position=self.end_position)
        if dropped is None:
            return execution_event.cancel(status_message="Failed to drop item")

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Dropped {dropped.name}"
        )

