from pydantic import BaseModel, Field, ConfigDict
from dnd.core.events import Event,EventType, EventHandler, EventPhase, EventProcessor
from dnd.core.values import BaseObject
from typing import Optional, Dict, Callable, OrderedDict, List, Literal
from uuid import UUID

CostType =  Literal["actions", "bonus_actions", "reactions", "movement"]

CostEvaluator = Callable[[UUID,CostType,int],bool]

class BaseCost(BaseModel):
    name: str = Field(default="A Cost",description="The name of the cost")
    cost_type: CostType
    cost: int

class Cost(BaseCost):
    evaluator: Optional[CostEvaluator] = Field(default=None,description="The evaluator for the cost")

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

class BaseAction(BaseObject):
    """Base class for all actions in the game. This class provides the basic structure
    for actions, allowing both direct implementation through _validate and _apply methods,
    as well as structured implementation through the StructuredAction subclass."""
    description: str  = Field(description="The description of the action, this is going to be displayed in the ui as a tooltip")
    parent_event: Optional[Event] = Field(default=None,description="The parent event of the action, the first event to be created in the action will be a child of this event used to keep track of sub-actions triggered by other events")
    costs: List[Cost] = Field(default_factory=list,description="A list of costs for the action")
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def check_costs(self) -> bool:
        for cost in self.costs:
                if cost.evaluator is not None and not cost.evaluator(self.source_entity_uuid,cost.cost_type,cost.cost):
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

    def apply(self,parent_event: Optional[Event] = None) -> Optional[Event]:
        """Main entry point for applying an action. This method orchestrates the flow
        through declaration, validation, and application phases."""
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
