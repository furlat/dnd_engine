from tkinter import NO
from dnd.core.base_actions import BaseAction, StructuredAction, CostType, Cost,BaseCost, ActionEvent
from dnd.core.values import ModifiableValue

from dnd.core.modifiers import NumericalModifier, DamageType , ResistanceStatus, ContextAwareCondition, BaseObject, saving_throws, ResistanceModifier, AutoHitStatus, CriticalStatus
from dnd.core.dice import Dice, DiceRoll, AttackOutcome, RollType
from dnd.core.events import RangeType,Event, EventType, WeaponSlot, Range, Damage, EventHandler,EventProcessor, EventPhase
from pydantic import Field
from typing import Optional, List, TypeVar, Generic, Union, Tuple
from uuid import UUID
from dnd.entity import Entity, determine_attack_outcome
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
    """Apply the costs of the action"""
    entity = Entity.get(source_entity_uuid)
    if entity is None or not isinstance(entity, Entity):
        return completion_event.cancel(status_message=f"Entity not found for {completion_event.name}")
    for cost in completion_event.costs:
        entity.action_economy.consume(cost.cost_type,cost.cost)
    return completion_event.phase_to(
        new_phase=EventPhase.COMPLETION,
        status_message=f"Succesfully applied costs for {completion_event.name} for {completion_event.source_entity_uuid}"
    )


class MovementEvent(ActionEvent):
    """An event that represents a movement"""
    name: str = Field(default="Movement",description="A movement event")
    event_type: EventType = Field(default=EventType.MOVEMENT,description="The type of event")
    start_position: Tuple[int,int] = Field(description="The start position of the movement")
    end_position: Tuple[int,int] = Field(description="The end position of the movement")
    path: Optional[List[Tuple[int,int]]] = Field(default=None,description="The path of the movement")

class Movement(BaseAction):
    """An action that represents a movement with a path it will automatically compute the path from the source entity position to the end position
    the cost is automatically computed from the path length and the use_movement_cost flag is true
    
    This is a simplified implmenetation that does not move the character through the path, hence not triggering any movement specific"""
    name: str = Field(default="Movement",description="A movement action")
    description: str = Field(default="A movement action",description="A description of the movement action")
    end_position: Tuple[int,int] = Field(description="The end position of the movement")
    path:Optional[List[Tuple[int,int]]] = Field(default=None,description="The path of the movement")
    use_movement_cost: bool = Field(default=True,description="Whether to use the movement cost")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._setup_path()
        self._setup_costs_from_path()

    def _setup_costs_from_path(self):
        if self.path is not None and self.use_movement_cost:
            self.costs.append(Cost(name="Movement Cost",cost_type="movement",cost=len(self.path),evaluator=entity_action_economy_cost_evaluator))

    def _setup_path(self):
        """Check if the costs of the action are valid and sets up the path and the costs"""
        if self.path is None:
            source_entity = Entity.get(self.source_entity_uuid)
            if source_entity is None or not isinstance(source_entity, Entity):
                return None
            self.path = source_entity.senses.paths[self.end_position]
            
        

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
            
    def _create_declaration_event(self,parent_event: Optional[Event] = None) -> Optional[Event]:
        """Create the declaration event for the movement action"""
        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity or not isinstance(source_entity, Entity):
            return None

        

        return MovementEvent(
            name=f"{self.name}",
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            start_position=source_entity.position,
            end_position=self.end_position,
            path=self.path
        )
    
    def _validate(self, declaration_event: MovementEvent) -> MovementEvent:
        """Validate the movement action"""
        validated_event = Movement.validate_path(declaration_event,self.source_entity_uuid)
        if not validated_event.canceled:
            return validated_event.phase_to(
                new_phase=EventPhase.EXECUTION,
                status_message=f"Validated  {declaration_event.name}"
            )
        else:
            return validated_event
        
    def _apply(self, execution_event: MovementEvent) -> MovementEvent:
        """Apply the movement action"""
        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity or not isinstance(source_entity, Entity):
            return execution_event.cancel(status_message=f"Source entity not found for {execution_event.name}")

        ## first check if we have path and if not it means there are no costs for it
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
        #now we add the costs to the event
        execution_event = execution_event.post(
            costs=self.costs,
            status_message=f"Added costs to {execution_event.uuid}"
        )

        Entity.update_entity_position(source_entity,execution_event.end_position)
        Entity.update_all_entities_senses() #later we will only update the senses of the entities that are affected by the movement 
        
        if source_entity.position != execution_event.end_position:
            # here is a good opportunity to recompute the cost if for some resason the movement failed
            return execution_event.cancel(status_message=f"Failed to move to {execution_event.end_position} for {execution_event.name}")
        else:
            effect_event = execution_event.post(
                status_message=f"Moved to {execution_event.end_position} for {execution_event.name}"
            )

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Applied movement for {execution_event.name}"
        )
    
    def _apply_costs(self, completion_event: MovementEvent) -> Optional[MovementEvent]:
        """Apply the costs of the action"""
        return entity_action_economy_cost_applier(completion_event,self.source_entity_uuid)
        

class AttackEvent(ActionEvent):
    """An event that represents an attack"""
    name: str = Field(default="Attack",description="An attack event")
    weapon_slot: WeaponSlot = Field(description="The slot of the weapon used to attack")
    range: Optional[Range] = Field(default=None,description="The range of the attack")
    attack_bonus: Optional[ModifiableValue] = Field(default=None,description="The attack bonus of the attack")
    ac: Optional[ModifiableValue] = Field(default=None,description="The ac of the target")
    dice_roll: Optional[DiceRoll] = Field(default=None,description="The result of the dice roll")
    attack_outcome: Optional[AttackOutcome] = Field(default=None,description="The outcome of the attack")
    damages: Optional[List[Damage]] = Field(default=None,description="The damages of the attack")
    damage_rolls: Optional[List[DiceRoll]] = Field(default=None,description="The rolls of the damages")
    event_type: EventType = Field(default=EventType.ATTACK,description="The type of event")



class Attack(BaseAction):
    """An action that represents an attack using a weapon
    validation requires the source entity and target entity to be in range and the target entity to be in the line of sight
    of the source entity"""
    name: str = Field(default="Attack",description="An attack action")
    description: str = Field(default="An attack action",description="A description of the attack action")
    weapon_slot: WeaponSlot = Field(description="The slot of the weapon used to attack")
    costs: List[Cost] = Field(default_factory=lambda: [Cost(name="Attack Cost",cost_type="actions",cost=1,evaluator=entity_action_economy_cost_evaluator)],description="A list of costs for the action")
    
    
    @staticmethod
    def validate_range(declaration_event: AttackEvent,source_entity_uuid: UUID) -> Optional[AttackEvent]:
        """Validate if the source entity and target entity are in range"""
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
        
        range = source_entity.get_weapon_range(declaration_event.weapon_slot)
        if range is None:
            return declaration_event.cancel(status_message=f"Weapon range not found for {declaration_event.name}")
        if range.type == RangeType.RANGE:
            if range.normal < source_entity.senses.get_distance(target_entity.position):
                return declaration_event.cancel(status_message=f"Target entity not in range for {declaration_event.name}")
        elif range.type == RangeType.REACH:
            if source_entity.senses.get_feet_distance(target_entity.position) > 5:
                return declaration_event.cancel(status_message=f"Target entity not in reach for {declaration_event.name}")
        return declaration_event.phase_to(
            new_phase=EventPhase.DECLARATION,
            status_message=f"Validated range for {declaration_event.name} - added range to event",
            range=range
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
            attack_outcome = determine_attack_outcome(dice_roll, ac)
            
            attack_event = attack_event.post(
                dice_roll=dice_roll,
                attack_outcome=attack_outcome,
                status_message=f"Attack rolled {dice_roll.total} and {attack_outcome}"
            )
            ac.reset_from_target()
            attack_bonus.reset_from_target()
            
            
            # If attack was canceled or missed, skip to COMPLETION
            if attack_event.canceled:
                return attack_event
            elif attack_event.attack_outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
                return attack_event.phase_to(
                    new_phase=EventPhase.COMPLETION,
                    status_message=f"Attack missed"
                )
            
            # Move to EFFECT phase for damage
            damages = source_entity.get_damages(weapon_slot, target_entity_uuid)
            attack_event = attack_event.post(
                new_phase=EventPhase.EFFECT,
                status_message=f"Damages: {[(damage.dice_numbers,damage.damage_dice,damage.damage_bonus.normalized_score if damage.damage_bonus else 0,damage.damage_type) for damage in damages]}",
                damages=damages
            )
            
            # If attack was canceled during phase transition, return early
            if attack_event.canceled:
                return attack_event
            
            # Apply damage if there is an attack outcome
            if attack_event.attack_outcome is not None and attack_event.attack_outcome not in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
                damage_rolls = target_entity.take_damage(damages, attack_event.attack_outcome)
                attack_event = attack_event.phase_to(
                    new_phase=EventPhase.EFFECT,
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

    def _create_declaration_event(self,parent_event: Optional[Event] = None) -> Optional[Event]:
        """ Create the declaration event for the attack action"""
        return AttackEvent(
            name=f"{self.name}",
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            weapon_slot=self.weapon_slot,
            costs=[BaseCost.model_validate(cost) for cost in self.costs]
            
        )
    
    def _validate(self, declaration_event: AttackEvent) -> Optional[AttackEvent]:
        """Validate the attack action"""
        range_validated_event = Attack.validate_range(declaration_event,self.source_entity_uuid)
        if range_validated_event is None:
            return declaration_event.cancel(status_message=f"Range validation returned None for {self.name}")
        elif range_validated_event.canceled:
            return range_validated_event
        line_of_sight_validated_event = validate_line_of_sight(range_validated_event,self.source_entity_uuid)
        if line_of_sight_validated_event is None:
            return declaration_event.cancel(status_message=f"Line of sight validation returned None for {self.name}")
        elif line_of_sight_validated_event.canceled:
            return line_of_sight_validated_event
        return line_of_sight_validated_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Attack validated for {self.name}"
        )
    
    def _apply(self, execution_event: AttackEvent) -> Optional[AttackEvent]:
        """Apply the attack action"""
        return Attack.attack_consequences(execution_event,self.source_entity_uuid)

    def _apply_costs(self, completion_event: AttackEvent) -> Optional[AttackEvent]:
        """Apply the costs of the action"""
        return entity_action_economy_cost_applier(completion_event,self.source_entity_uuid)



#factories, these are redundant examples to create the same actions using the structured action approach
# used for prompting LLMs that most likely will use the StructuredAction approach when implementing Content

def attack_factory(source_entity_uuid: UUID, target_entity_uuid: UUID, weapon_slot: WeaponSlot = WeaponSlot.MAIN_HAND) -> Optional[BaseAction]:
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

