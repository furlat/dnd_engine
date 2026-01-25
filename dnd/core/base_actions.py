from pydantic import BaseModel, Field, ConfigDict
from dnd.core.events import Event, EventType, EventPhase, EventProcessor
from dnd.core.base_object import BaseObject
from dnd.core.base_block import BaseBlock
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType, SelfActionLogData
from typing import Optional, Callable, OrderedDict, List, Literal, Tuple
from uuid import UUID
from enum import Enum

CostType = Literal["actions", "bonus_actions", "reactions", "movement"]


class TargetType(str, Enum):
    """What kind of target an action requires."""
    SELF = "self"          # Dash, Dodge, Disengage - no target needed
    ENTITY = "entity"      # Attack - targets another entity
    POSITION = "position"  # Move - targets a grid position

CostEvaluator = Callable[[UUID,CostType,int],bool]

class BaseCost(BaseModel):
    """Cost for an action - can include both turn-based and resource costs."""
    name: str = Field(default="A Cost", description="The name of the cost")
    cost_type: CostType
    cost: int
    # Optional resource cost (can have both turn-based AND resource cost)
    resource_name: Optional[str] = Field(default=None, description="Name of resource to consume (e.g., 'second_wind')")
    resource_cost: int = Field(default=0, description="Amount of resource to consume")


class Cost(BaseCost):
    evaluator: Optional[CostEvaluator] = Field(default=None, description="The evaluator for the cost")

class ActionEvent(Event):
    costs: List[BaseCost] = Field(default_factory=list,description="A list of costs for the action")
    event_type: EventType = Field(default=EventType.BASE_ACTION,description="The type of event")

    def add_cost(self, cost: Cost):
        base_cost = BaseCost.model_validate(cost)
        self.costs.append(base_cost)

    @classmethod
    def from_costs(cls,costs: List[Cost], source_entity_uuid: UUID, target_entity_uuid: Optional[UUID] = None, parent_event: Optional[Event] = None, use_register: bool = True):
        base_costs = [BaseCost.model_validate(cost) for cost in costs]
        return cls(source_entity_uuid=source_entity_uuid, target_entity_uuid=target_entity_uuid, costs=base_costs, parent_event=parent_event.uuid if parent_event else None, use_register=use_register)

    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        """Generate a combat log entry for generic actions (Dash, Dodge, Disengage, etc.).

        This is the default implementation for ActionEvent. Subclasses like AttackEvent
        and MovementEvent override this with more detailed implementations.

        Uses self.* fields only - no external lookups. Entity name must be
        populated when the event is created.

        Returns:
            CombatLogEntry for self-targeting actions, or None for base events.
        """
        # Use entity name from self - no external lookups
        source_name = self.source_entity_name or "Unknown"
        action_name = self.name or "Action"

        # Build summary
        summary = f"{source_name} uses {action_name}"

        # Determine effect description based on action name
        effect_description = ""
        action_lower = action_name.lower()
        if "dash" in action_lower:
            effect_description = "Movement speed doubled for this turn"
        elif "dodge" in action_lower:
            effect_description = "Attacks against have disadvantage, advantage on DEX saves"
        elif "disengage" in action_lower:
            effect_description = "Movement doesn't provoke opportunity attacks"
        elif "second wind" in action_lower:
            effect_description = "Heals for 1d10 + fighter level"
        elif "action surge" in action_lower:
            effect_description = "Gains an additional action this turn"
        else:
            effect_description = f"{action_name} effect applied"

        # Build structured data
        data = SelfActionLogData(
            entity_name=source_name,
            entity_uuid=str(self.source_entity_uuid),
            action_name=action_name,
            effect_description=effect_description
        )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.ACTION,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            summary=summary,
            detail_lines=[effect_description] if effect_description else [],
            data=data.model_dump(),
            success=True
        )


class BaseAction(BaseObject):
    """Base class for all actions in the game. This class provides the basic structure
    for actions, allowing both direct implementation through _validate and _apply methods,
    as well as structured implementation through the StructuredAction subclass.

    Actions can be created as templates (template=True) which are bound to a source entity
    with fixed configuration (e.g., weapon_slot), but without a specific target. Templates
    support pre_validate() but cannot be applied directly - use instantiate() to create
    an executable instance with a specific target.
    """
    description: str = Field(default="", description="The description of the action, this is going to be displayed in the ui as a tooltip")
    parent_event: Optional[Event] = Field(default=None, description="The parent event of the action, the first event to be created in the action will be a child of this event used to keep track of sub-actions triggered by other events")
    costs: List[Cost] = Field(default_factory=list, description="A list of costs for the action")

    # Template system fields
    target_type: TargetType = Field(default=TargetType.SELF, description="What kind of target this action requires")
    template: bool = Field(default=False, description="If True, this is a template that cannot be applied directly - use instantiate()")

    # For POSITION actions (like Move), stored separately from target_entity_uuid
    end_position: Optional[Tuple[int, int]] = Field(default=None, description="Target position for POSITION type actions")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def set_target_entity(self, target_uuid: UUID) -> None:
        """Set target entity for ENTITY type actions.

        Used with templates to set the target before pre_validate() or instantiate().
        """
        if self.target_type != TargetType.ENTITY:
            raise ValueError(f"Action {self.name} doesn't target entities (target_type={self.target_type})")
        self.target_entity_uuid = target_uuid

    def set_target_position(self, position: Tuple[int, int]) -> None:
        """Set target position for POSITION type actions.

        Used with templates to set the target before pre_validate() or instantiate().
        """
        if self.target_type != TargetType.POSITION:
            raise ValueError(f"Action {self.name} doesn't target positions (target_type={self.target_type})")
        self.end_position = position

    def instantiate(self, **overrides) -> "BaseAction":
        """Create an executable instance from this template.

        The instance will have the same configuration as the template but with
        template=False, allowing it to be applied.

        Args:
            **overrides: Additional fields to override (e.g., target_entity_uuid, end_position)

        Returns:
            BaseAction: A new instance that can be applied

        Raises:
            ValueError: If this is not a template
        """
        if not self.template:
            raise ValueError("Can only instantiate from a template")

        # Copy all fields except uuid (which will be regenerated)
        kwargs = self.model_dump(exclude={"uuid"})
        kwargs["template"] = False
        kwargs.update(overrides)

        return type(self)(**kwargs)

    def check_costs(self) -> bool:
        """Check if entity can afford all costs (turn-based and resource-based)."""
        for cost in self.costs:
            # Check turn-based cost via evaluator
            if cost.evaluator is not None and not cost.evaluator(self.source_entity_uuid, cost.cost_type, cost.cost):
                return False
            # Check resource cost if present
            if cost.resource_cost > 0 and cost.resource_name:
                # Use BaseBlock.get() since Entity registers in BaseBlock._registry
                entity = BaseBlock.get(self.source_entity_uuid)
                if entity is None:
                    return False
                # Entity has action_economy, use getattr for type safety
                action_economy = getattr(entity, 'action_economy', None)
                if action_economy is None:
                    return False
                if not action_economy.can_afford_resource(cost.resource_name, cost.resource_cost):
                    return False
        return True

    def _create_declaration_event(self,parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[ActionEvent]:
        """Create the declaration event for this action. Override in subclasses if needed."""
        
        return ActionEvent.from_costs(self.costs,self.source_entity_uuid,self.target_entity_uuid,parent_event,use_register=use_register)

    
    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        """Validate if the action can be performed. Override this in subclasses to implement
        custom validation logic. Similar to BaseCondition._apply pattern."""
        
        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message=f"Succesfully validated action{self.name} for {declaration_event.source_entity_uuid}"
        )
    
    def pre_validate(self)-> bool:
        """Pre-validate the action. creates a non-registered event that is not added to the event queue and calls _validate"""
        if not self.check_costs():
            return False
        declaration_event = self._create_declaration_event(parent_event=None, use_register=False)
        if declaration_event is None:
            return False
        if declaration_event.phase != EventPhase.DECLARATION:
            return False
        validation_event = self._validate(declaration_event)
        if validation_event is None or validation_event.canceled:
            return False
        return True
    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        """Apply the action's effects. Override this in subclasses to implement
        custom application logic. Similar to BaseCondition._apply pattern."""
        
        #during the apply the effect is applied
        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applying effect for {self.name}"
        )
        return effect_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"Succesfully applied action {self.name} for {execution_event.source_entity_uuid}"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> Optional[ActionEvent]:
        """Apply the costs of the action - implemented in subclasses"""
        return completion_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"Succesfully applied costs for {self.name} for {completion_event.source_entity_uuid}"
        )

    def apply(self, parent_event: Optional[Event] = None) -> Optional[Event]:
        """Main entry point for applying an action. This method orchestrates the flow
        through declaration, validation, and application phases.

        Raises:
            ValueError: If this is a template (use instantiate() first)
        """
        if self.template:
            raise ValueError(f"Cannot apply template action '{self.name}' - use instantiate() first")
        if not self.check_costs():
            return None
        # Create declaration event
        declaration_event = self._create_declaration_event(parent_event)
        if declaration_event is None:
            return None
        elif declaration_event.canceled:
            return declaration_event

        # Validate
        if declaration_event.phase != EventPhase.DECLARATION:
            raise ValueError(f"Action {self.name} can only be validated in the declaration phase")
        execution_event = self._validate(declaration_event)
        if execution_event is None or execution_event.canceled:
            return execution_event
        if execution_event.phase not in [EventPhase.EXECUTION]:
            raise ValueError(f"Action {self.name} can only be applied in the execution phase")
        # Apply
        completion_event = self._apply(execution_event)
        if completion_event is None or completion_event.canceled:
            return completion_event
        if completion_event.phase not in [EventPhase.COMPLETION]:
            raise ValueError(f"Action {self.name} can only be completed in the completion phase")
        cost_event = self._apply_costs(completion_event)
        if cost_event is None or cost_event.canceled:
            return cost_event
        if cost_event.phase not in [EventPhase.COMPLETION]:
            raise ValueError(f"Action {self.name} can only be completed in the completion phase")
        return cost_event


class StructuredAction(BaseAction):
    """Implementation of BaseAction that uses the structured pipeline approach with
    prerequisites, consequences, and cost checking through event processors."""
    prerequisites: OrderedDict[str,EventProcessor] = Field(
        default_factory=OrderedDict,
        description="A dictionary of prerequisites, the key is the name of the prerequisite and the value is a callable that returns a boolean"
    )
    consequences: OrderedDict[str,EventProcessor] = Field(
        default_factory=OrderedDict,
        description="A dictionary of consequences, the key is the name of the consequence and the value is a callable that returns an Event"
    )
    revalidate_prerequisites: bool = Field(
        default=True,
        description="If true, the prerequisites will be revalidated when the event is applied"
    )
    cost_applier: Optional[EventProcessor] = Field(
        default=None,
        description="The event processor that will be used to apply costs"
    )
    
    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        """Implements the prerequisite checking pipeline."""
        if declaration_event.phase != EventPhase.DECLARATION:
            raise ValueError(f"Action {self.name} prerequisites can only be checked in declaration phase")

        current_event = declaration_event
        # Apply the prerequisites
        for prerequisite_name, prerequisite_function in self.prerequisites.items():
            prerequisite_event = prerequisite_function(current_event, current_event.source_entity_uuid)
            if prerequisite_event is None:
                return current_event.cancel(status_message=f"Prerequisite {prerequisite_name} failed for {self.name}")
            if prerequisite_event.canceled:
                return prerequisite_event
            current_event = prerequisite_event

        # Move to execution phase after all validations pass
        return current_event.phase_to(
            EventPhase.EXECUTION,
            status_message=f"Successfully validated structured action {self.name} for {current_event.source_entity_uuid}"
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        """Implements the consequence application pipeline."""
        if execution_event.phase != EventPhase.EXECUTION:
            raise ValueError(f"Action {self.name} consequences can only be applied in execution phase")

        current_event = execution_event
        # Move to effect phase for applying consequences
        effect_event = current_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applying consequences for {self.name}"
        )
        if effect_event.canceled:
            return effect_event

        current_event = effect_event
        # Apply consequences
        for consequence_name, consequence_function in self.consequences.items():
            consequence_event = consequence_function(current_event, current_event.source_entity_uuid)
            if consequence_event is None:
                return current_event.cancel(status_message=f"Consequence {consequence_name} failed for {self.name}")
            elif consequence_event.canceled:
                return consequence_event
            
            # Validate the consequence result if needed
            if self.revalidate_prerequisites:
                if consequence_event.phase not in [EventPhase.EXECUTION, EventPhase.EFFECT]:
                    raise ValueError(f"Consequence {consequence_name} returned event in invalid phase {consequence_event.phase}")
                validated_event = self._validate(consequence_event)
                if validated_event is None or validated_event.canceled:
                    return validated_event
                current_event = validated_event
            else:
                current_event = consequence_event

        # Move to completion phase
        return current_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"Successfully completed structured action {self.name} for {current_event.source_entity_uuid}"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> Optional[ActionEvent]:
        """Apply the costs using the cost_applier if provided"""
        if self.cost_applier is not None:
            return self.cost_applier(completion_event, self.source_entity_uuid)
        return completion_event


# =============================================================================
# Available Actions Data Models
# =============================================================================

class AvailableTarget(BaseModel):
    """A valid target for an action, with index for selection.

    Used in CLI/UI patterns like 'attack 0' or 'move 3' to select targets.
    """
    index: int = Field(description="Index for selection (e.g., 'attack 0')")
    target_uuid: Optional[UUID] = Field(default=None, description="For ENTITY actions")
    position: Optional[Tuple[int, int]] = Field(default=None, description="For POSITION actions")
    # Additional info for display
    target_name: Optional[str] = Field(default=None, description="Entity name if ENTITY action")
    distance: Optional[int] = Field(default=None, description="Distance in feet")
    path_cost: Optional[int] = Field(default=None, description="Movement cost if POSITION action")


class AvailableActionInfo(BaseModel):
    """Information about an available action and its valid targets.

    This is returned by Entity.get_available_actions() and contains everything
    needed to display the action in UI and execute it.
    """
    template_name: str = Field(description="Name of the template for execution")
    target_type: TargetType = Field(description="What kind of target this action needs")
    valid_targets: List[AvailableTarget] = Field(default_factory=list, description="All valid targets with indices")
    can_afford: bool = Field(description="Can afford base cost (action/bonus/etc)")

    # Display info
    display_name: str = Field(description="Human-readable name (e.g., 'Scimitar')")
    description: str = Field(default="", description="Action description")
    cost_type: CostType = Field(description="Type of cost (actions, bonus_actions, etc.)")
    cost_amount: int = Field(default=1, description="Cost amount (usually 1)")

    # For attacks - optional weapon info
    weapon_slot: Optional[str] = Field(default=None, description="Weapon slot for attacks")
    weapon_name: Optional[str] = Field(default=None, description="Weapon name for display (e.g., 'Scimitar')")


class AvailableActionsResult(BaseModel):
    """Complete available actions query result.

    Returned by Entity.get_available_actions(). Groups actions by type for
    easy iteration and UI rendering.
    """
    entity_uuid: UUID = Field(description="UUID of the entity these actions are for")

    # Grouped by target type for easy iteration
    entity_actions: List[AvailableActionInfo] = Field(default_factory=list, description="Actions targeting entities (Attack)")
    position_actions: List[AvailableActionInfo] = Field(default_factory=list, description="Actions targeting positions (Move)")
    self_actions: List[AvailableActionInfo] = Field(default_factory=list, description="Self-targeting actions (Dash, Dodge, etc.)")

    # State info
    remaining_movement: int = Field(default=0, description="Remaining movement in feet")

    @property
    def all_actions(self) -> List[AvailableActionInfo]:
        """Get all available actions as a flat list."""
        return self.entity_actions + self.position_actions + self.self_actions
