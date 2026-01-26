from dnd.core.base_actions import BaseAction, StructuredAction, CostType, Cost, BaseCost, ActionEvent, TargetType
from dnd.core.values import ModifiableValue
from dnd.core.base_conditions import DurationType
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus

from dnd.core.dice import  DiceRoll, AttackOutcome, RollType
from dnd.core.events import RangeType, Event, EventType, WeaponSlot, Range, Damage, EventPhase, DamageRolledEvent, TakeDamageEvent
from dnd.core.combat_log import (
    CombatLogEntry, CombatLogEntryType, ModifierBreakdown, DiceRollDisplay,
    DamageRollDisplay, AttackLogData, MovementLogData,
    format_attack_roll_line, format_damage_line
)
from pydantic import Field, model_validator
from typing import Optional, List, TypeVar, Tuple, Self, cast
from uuid import UUID
from dnd.entity import Entity, determine_attack_outcome
from dnd.conditions import Dashing, Dodging, Disengaging, Prone
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

        # Build summary
        summary = f"{source_name} moves {distance_feet}ft to ({self.end_position[0]}, {self.end_position[1]})"

        # Build detail lines
        detail_lines = []
        if path_str:
            detail_lines.append(f"Path: {path_str}")
        if movement_cost > 0:
            detail_lines.append(f"Cost: {movement_cost}ft movement")

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
            summary=summary,
            detail_lines=detail_lines,
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
    target_type: TargetType = Field(default=TargetType.POSITION, description="Move targets a position")
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
            # Path includes starting position, so actual squares moved = len - 1
            # Each square = 5 feet in D&D 5e
            feet_cost = (len(self.path) - 1) * 5
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

        Overrides base to ensure path/costs are recomputed for new end_position,
        not carried over from template's previous state.
        """
        if not self.template:
            raise ValueError("Can only instantiate from a template")

        # Copy all fields except uuid and path-related fields
        # Path and costs must be recomputed for the new end_position
        kwargs = self.model_dump(exclude={"uuid", "path", "costs"})
        kwargs["template"] = False
        kwargs["path"] = None  # Force recompute
        kwargs["costs"] = []   # Force recompute
        kwargs.update(overrides)

        return Move(**kwargs)

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
                feet_cost = (len(path) - 1) * 5
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
        
        costs = [BaseCost.model_validate(cost) for cost in self.costs]
        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            costs=costs,
            status_message=f"Added costs to {execution_event.uuid}"
        )
        if effect_event.canceled:
            return effect_event
            
        Entity.update_entity_position(source_entity,execution_event.end_position)
        Entity.update_all_entities_senses(max_distance=20)  # Use consistent vision range 
        #now we declare the application of the effect
        

        if source_entity.position == execution_event.start_position:
            # here is a good opportunity to recompute the cost if for some resason the movement failed
            return effect_event.cancel(status_message=f"Failed to move to {execution_event.end_position} for {execution_event.name}")
        elif source_entity.position != execution_event.start_position and source_entity.position != execution_event.end_position:
            # here we have a movement that failed
            return  execution_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"Failed to move to {execution_event.end_position} for {execution_event.name}, moved to {source_entity.position} instead",
                end_position=source_entity.position
            )
            

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Applied movement for {execution_event.name}"
        )
    
    def _apply_costs(self, completion_event: MovementEvent) -> Optional[MovementEvent]:
        """Apply the costs of the action"""
        return entity_action_economy_cost_applier(completion_event,self.source_entity_uuid)

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

        # Build summary
        if is_crit:
            summary = f"{source_name} CRITS {target_name} for {total_damage} damage!"
        elif is_hit:
            summary = f"{source_name} hits {target_name} for {total_damage} damage"
        else:
            summary = f"{source_name} misses {target_name}"

        # Build detail lines
        detail_lines = []

        # Attack roll line
        attack_line = format_attack_roll_line(
            attack_roll, attack_breakdown, target_ac, ac_breakdown, outcome
        )
        detail_lines.append(attack_line)

        # Damage line (only on hit)
        if is_hit and damage_roll_displays:
            damage_line = format_damage_line(damage_roll_displays)
            if damage_line:
                detail_lines.append(damage_line)

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
            summary=summary,
            detail_lines=detail_lines,
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
            attack_event = attack_event.phase_to(
                EventPhase.EFFECT,
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

                # Step 2: Create DAMAGE_ROLLED event
                # final_rolls starts as copy of original_rolls - handlers will replace entries
                damage_rolled_event = DamageRolledEvent(
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
                damage_rolled_event = damage_rolled_event.phase_to(
                    EventPhase.EFFECT,
                    status_message="Damage dice rolled"
                )

                # Step 4: Apply final_rolls (possibly modified by handlers)
                damage_rolls = damage_rolled_event.final_rolls
                total_damage = sum(roll.total for roll in damage_rolls)

                # Step 5: Create TAKE_DAMAGE event (allows handlers to track/modify/cancel)
                take_damage_event = TakeDamageEvent(
                    name="Take Damage",
                    source_entity_uuid=source_entity.uuid,
                    target_entity_uuid=target_entity.uuid,
                    total_damage=total_damage,
                    damage_rolls=damage_rolls,
                    damages=damages,
                    parent_event=attack_event.uuid,
                    phase=EventPhase.DECLARATION
                )

                # Progress through phases - handlers can intercept at EFFECT
                take_damage_event = take_damage_event.phase_to(EventPhase.EXECUTION)
                take_damage_event = take_damage_event.phase_to(EventPhase.EFFECT)

                # Step 6: Apply damage if not canceled
                if not take_damage_event.canceled:
                    effective_damage = take_damage_event.get_effective_damage()
                    # Apply damage for each roll, proportionally if modified
                    if take_damage_event.final_damage is not None and total_damage > 0:
                        # Damage was modified - apply as single amount with first damage type
                        target_entity.health.take_damage(
                            effective_damage,
                            damages[0].damage_type,
                            source_entity_uuid=source_entity.uuid
                        )
                    else:
                        # Apply each damage roll individually
                        for i, roll in enumerate(damage_rolls):
                            damage_type = damages[i].damage_type
                            target_entity.health.take_damage(
                                roll.total,
                                damage_type,
                                source_entity_uuid=source_entity.uuid
                            )

                take_damage_event = take_damage_event.phase_to(EventPhase.COMPLETION)

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
            name=self.name,
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
            name=self.name,
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
            name=self.name,
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
            name=self.name,
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
            name=self.name,
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

