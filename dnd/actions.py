"""Concrete action implementations for combat, movement, spells, and objects."""

from dnd.core.base_actions import (
    BaseAction, CostType, Cost, BaseCost, ActionEvent, TargetType,
    ActionCategory, SPELL_SLOT_TEMPLATE_SEPARATOR, spell_slot_cost_type,
)
from dnd.core.values import ModifiableValue
from dnd.core.base_conditions import DurationType
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus

from dnd.core.dice import  DiceRoll, AttackOutcome, RollType
from dnd.core.events import RangeType, Event, EventType, WeaponSlot, Range, Damage, EventPhase, DamageRollResultEvent, StepMovementEvent, ForcedMovementEvent, SkillCheckEvent, SpatialChangeEvent, AbilityName
from dnd.core.modifiers import DamageType
from dnd.core.gridmap import get_map
from dnd.core.base_tiles import Tile
from dnd.core.aoe import Sphere, Cone, Line, Cube, Cylinder
from dnd.core.naming import normalize_spell_id
from dnd.core.base_block import BaseBlock, MovementMode
from dnd.core.base_block import LightLevel
from dnd.core.combat_log import (
    CombatLogEntry, CombatLogEntryType, ModifierBreakdown, DiceRollDisplay,
    DamageRollDisplay, AttackLogData, MovementLogData, SpellSaveLogData,
    format_attack_compact, format_attack_verbose, format_attack_detailed,
    md_color
)
from pydantic import Field, model_validator
from typing import Any, Dict, Optional, List, Set, TypeVar, Tuple, Self, cast
from uuid import UUID, uuid4
from dnd.entity import Entity, determine_attack_outcome
from dnd.blocks.base_item import BaseItem
from dnd.blocks.equipment import Weapon
from dnd.conditions import Dashing, Dodging, Disengaging, Prone, Hidden, Concentrating


def entity_resource_cost_evaluator(entity_uuid: UUID, resource_name: str, resource_cost: int) -> bool:
    """Check whether an entity can afford a named resource cost.

    Args:
        entity_uuid: Entity that would pay the resource.
        resource_name: Action economy resource name.
        resource_cost: Resource amount required.

    Returns:
        True if the entity exists and can afford the resource.
    """
    entity = Entity.get(entity_uuid)
    if entity is None or not isinstance(entity, Entity):
        return False
    return entity.action_economy.can_afford_resource(resource_name, resource_cost)


def entity_action_economy_cost_evaluator(source_entity_uuid: UUID, cost_type: CostType, cost: int) -> bool:
    """Check whether an entity can afford an action economy cost.

    Args:
        source_entity_uuid: Entity that would pay the cost.
        cost_type: Action economy bucket to inspect.
        cost: Amount required.

    Returns:
        True if the entity exists and can afford the cost.
    """
    entity = Entity.get(source_entity_uuid)
    if entity is None or not isinstance(entity, Entity):
        return False
    return entity.action_economy.can_afford(cost_type, cost)

PolymorphicActionEvent = TypeVar('PolymorphicActionEvent', bound='ActionEvent')

def validate_line_of_sight(declaration_event: PolymorphicActionEvent, source_entity_uuid: UUID) -> Optional[PolymorphicActionEvent]:
    """Validate that the action target is visible to the source entity.

    Args:
        declaration_event: Declaration event being validated.
        source_entity_uuid: Acting entity UUID.

    Returns:
        Updated declaration event, canceled event, or `None` if a subclass does.
    """
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
    """Consume turn-based and named-resource costs after action completion.

    Args:
        completion_event: Completion event carrying serialized costs.
        source_entity_uuid: Entity that pays the costs.

    Returns:
        Completion event advanced after costs, or canceled on failed resource
        consumption.
    """
    entity = Entity.get(source_entity_uuid)
    if entity is None or not isinstance(entity, Entity):
        return completion_event.cancel(status_message=f"Entity not found for {completion_event.name}")
    for cost in completion_event.costs:
        if cost.cost > 0:
            entity.action_economy.consume(cost.cost_type, cost.cost)
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
    """Event payload for path-based movement actions."""

    name: str = Field(default="Movement", description="Human-readable movement event label.")
    event_type: EventType = Field(default=EventType.MOVEMENT, description="Movement event category.")
    costs: List[BaseCost] = Field(default_factory=list, description="Serialized movement costs.")
    start_position: Tuple[int, int] = Field(description="Position occupied before movement starts.")
    end_position: Tuple[int, int] = Field(description="Intended or actual final movement position.")
    path: Optional[List[Tuple[int, int]]] = Field(default=None, description="Grid path used by the movement.")

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Return movement positions relevant to spatial handlers."""
        positions = {self.start_position, self.end_position}
        if self.path:
            positions.update(self.path)
        return positions

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for this movement event.

        Uses self.* fields only - no external lookups. Entity name must be
        populated when the event is created.
        """
        source_name = self.source_entity_name or "Unknown"

        path = self.path or []
        distance_feet = (len(path) - 1) * 5 if len(path) > 1 else 0

        movement_cost = 0
        for cost in self.costs:
            if cost.cost_type == "movement":
                movement_cost = cost.cost

        path_str = " -> ".join(f"({p[0]}, {p[1]})" for p in path) if path else ""

        end_pos = f"({self.end_position[0]},{self.end_position[1]})"
        start_pos = f"({self.start_position[0]},{self.start_position[1]})"

        compact_text = f"{md_color(source_name, 'cyan')} moves {md_color(f'{distance_feet}ft', 'green')} to {md_color(end_pos, 'yellow')}"
        verbose_text = f"{md_color(source_name, 'cyan')} moves {start_pos} → {md_color(end_pos, 'green')}"
        if movement_cost > 0:
            verbose_text += f" ({movement_cost}ft)"

        detailed_text = verbose_text
        if path_str:
            detailed_text += f"\n  Path: {path_str}"

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
    """Path-based movement action that walks cell by cell.

    When used as a template (template=True), end_position can be None and should be set via set_target_position()
    before pre_validate() or instantiate().
    """

    name: str = Field(default="Move", description="Human-readable movement action name.")
    description: str = Field(default="Move to a position", description="Movement action description.")
    target_type: TargetType = Field(default=TargetType.POSITION_PATH, description="Move targets a path-reachable position.")
    action_category: ActionCategory = Field(default=ActionCategory.MOVEMENT, description="Movement action category.")
    end_position: Optional[Tuple[int, int]] = Field(default=None, description="Requested movement destination.")
    path: Optional[List[Tuple[int, int]]] = Field(default=None, description="Resolved path from source to destination.")
    use_movement_cost: bool = Field(default=True, description="Whether movement costs are generated from the path.")
    prefer_safe: bool = Field(default=True, description="Whether a safe path is preferred when available.")
    movement_mode: MovementMode = Field(default=MovementMode.WALKING, description="Movement mode used for terrain costs and transitions.")

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.end_position is not None and not self.template:
            self._setup_path()
            self._setup_costs_from_path()

    def _setup_costs_from_path(self) -> None:
        """Rebuild the movement cost from the resolved path and terrain."""
        if self.path is not None and self.use_movement_cost:
            grid = get_map()
            total_cost = 0

            source_entity = Entity.get(self.source_entity_uuid)
            ign_terrain = source_entity.ignore_difficult_terrain if source_entity else False

            for i in range(1, len(self.path)):
                tile = grid.get_tile(*self.path[i])
                total_cost += self._get_step_cost_units(tile, source_entity, ign_terrain)

            feet_cost = int(total_cost * 5)
            self.costs.append(
                Cost(
                    name="Movement Cost",
                    cost_type="movement",
                    cost=feet_cost,
                    evaluator=entity_action_economy_cost_evaluator,
                )
            )

    def _get_step_cost_units(self, tile: Optional[Tile], source_entity: Optional[Entity], ignore_difficult_terrain: bool = False) -> float:
        """Return movement-cost units for one step in this action's mode.

        Args:
            tile: Destination tile or block-like terrain object.
            source_entity: Entity paying the movement cost.
            ignore_difficult_terrain: Whether difficult-terrain costs are capped.

        Returns:
            Movement cost in grid cost units before conversion to feet.
        """
        if tile:
            cost = tile.get_movement_cost(self.movement_mode)
        else:
            cost = 1.0

        if self.movement_mode == MovementMode.WALKING and ignore_difficult_terrain:
            cost = min(cost, 1.0)

        if (
            self.movement_mode == MovementMode.SWIMMING
            and source_entity is not None
            and source_entity.swimming_speed <= 0
            and not source_entity.ignore_underwater_penalties
        ):
            cost *= 2

        return cost

    def _setup_path(self) -> None:
        """Resolve the movement path from current senses data."""
        if self.path is None and self.end_position is not None:
            source_entity = Entity.get(self.source_entity_uuid)
            if source_entity is None or not isinstance(source_entity, Entity):
                return None
            if self.movement_mode == MovementMode.WALKING and self.prefer_safe and self.end_position in source_entity.senses.safe_paths:
                self.path = source_entity.senses.safe_paths[self.end_position]
            elif self.movement_mode == MovementMode.WALKING and self.end_position in source_entity.senses.paths:
                self.path = source_entity.senses.paths[self.end_position]
            elif self.movement_mode != MovementMode.WALKING:
                grid = get_map()
                _, paths = grid.compute_paths(
                    source_entity.position,
                    requesting_entity_uuid=source_entity.uuid,
                    movement_mode=self.movement_mode,
                    subjective=True,
                )
                self.path = paths.get(self.end_position)

    def set_target_position(self, position: Tuple[int, int]) -> None:
        """Set target position and compute path/costs for validation.

        Overrides base implementation to also compute path and costs,
        so that pre_validate() can properly check movement affordability.
        """
        self.path = None
        self.costs = []

        super().set_target_position(position)

        self._setup_path()
        self._setup_costs_from_path()

    def instantiate(self, **overrides) -> "Move":
        """Create an executable Move instance from this template.

        Uses model_copy() to preserve object types. Path/costs are reset
        for recomputation based on new end_position.
        """
        if not self.template:
            raise ValueError("Can only instantiate from a template")

        update_dict: dict = {
            "uuid": uuid4(),
            "template": False,
            "use_register": False,
            "path": None,
            "costs": [],
        }
        update_dict.update(overrides)

        instance = self.model_copy(deep=True, update=update_dict)

        if instance.end_position is not None:
            instance._setup_path()
            instance._setup_costs_from_path()

        return instance

    @staticmethod
    def validate_path(
        declaration_event: MovementEvent,
        source_entity_uuid: UUID,
        movement_mode: MovementMode = MovementMode.WALKING,
    ) -> MovementEvent:
        """Validate that a movement event carries a usable path.

        Args:
            declaration_event: Movement declaration event to validate.
            source_entity_uuid: Moving entity UUID.
            movement_mode: Movement mode required for each transition.

        Returns:
            Posted declaration event or canceled event.
        """
        source_entity = Entity.get(source_entity_uuid)
        if not source_entity or not isinstance(source_entity, Entity):
            return declaration_event.cancel(status_message=f"Source entity not found for {declaration_event.name}")
        if declaration_event.path is None or len(declaration_event.path) == 0:
            return declaration_event.cancel(status_message=f"No valid path found for {declaration_event.name}")

        else:
            if movement_mode == MovementMode.WALKING and declaration_event.path == source_entity.senses.paths[declaration_event.end_position]:
                return declaration_event.post(
                    status_message=f"Validated path for {declaration_event.name}"
                )
            elif movement_mode == MovementMode.WALKING:
                for path_position in declaration_event.path:
                    if path_position not in source_entity.senses.paths:
                        return declaration_event.cancel(status_message=f"Invalid path for {declaration_event.name} at position {path_position}")

                return declaration_event.post(
                    status_message=f"Validated path for {declaration_event.name}"
                )
            else:
                grid = get_map()
                if declaration_event.path[0] != source_entity.position:
                    return declaration_event.cancel(status_message=f"Invalid path start for {declaration_event.name}")
                if declaration_event.path[-1] != declaration_event.end_position:
                    return declaration_event.cancel(status_message=f"Invalid path end for {declaration_event.name}")
                for from_pos, to_pos in zip(declaration_event.path, declaration_event.path[1:]):
                    if not grid.can_transition(from_pos, to_pos, source_entity.uuid, movement_mode, subjective=True):
                        return declaration_event.cancel(status_message=f"Invalid {movement_mode.value} transition for {declaration_event.name} at position {to_pos}")
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
            return None

        end_position: Tuple[int, int] = self.end_position

        path = self.path
        if path is None and self.movement_mode == MovementMode.WALKING and end_position in source_entity.senses.paths:
            path = source_entity.senses.paths[end_position]
        elif path is None and self.movement_mode != MovementMode.WALKING:
            grid = get_map()
            _, paths = grid.compute_paths(
                source_entity.position,
                requesting_entity_uuid=source_entity.uuid,
                movement_mode=self.movement_mode,
                subjective=True,
            )
            path = paths.get(end_position)

        costs = list(self.costs)
        if path is not None and self.use_movement_cost:
            has_movement_cost = any(c.cost_type == "movement" for c in costs)
            if not has_movement_cost:
                grid = get_map()
                total_cost = 0

                for i in range(1, len(path)):
                    tile = grid.get_tile(*path[i])
                    total_cost += self._get_step_cost_units(tile, source_entity, source_entity.ignore_difficult_terrain)

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
            source_entity_name=source_entity.name,
        )

    def _validate(self, declaration_event: MovementEvent) -> MovementEvent:
        """Validate the movement action."""
        validated_event = Move.validate_path(declaration_event, self.source_entity_uuid, self.movement_mode)
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

        grid = get_map()
        path = self.path or []
        total_path_length = len(path)
        actual_end_position = source_entity.position
        interrupted_by_condition = False

        try:
            for i in range(1, total_path_length):
                from_pos = path[i - 1]
                to_pos = path[i]

                if not grid.can_transition(from_pos, to_pos, source_entity.uuid, self.movement_mode):
                    if grid.can_transition(from_pos, to_pos, source_entity.uuid, self.movement_mode, subjective=True):
                        cell_blocked = not grid.is_walkable_for(to_pos[0], to_pos[1], source_entity.uuid, self.movement_mode)
                        directions = []
                        from_tile = grid.get_tile(*from_pos)
                        if from_tile:
                            directions = list(from_tile.directions_toward(to_pos))
                        if cell_blocked:
                            source_entity.senses.collision_blocked.add(to_pos)
                        else:
                            for direction in directions:
                                source_entity.senses.directional_collision_blocked.add((from_pos, direction))
                        collision_event = SpatialChangeEvent.movement_collision(
                            position=to_pos, mover_uuid=source_entity.uuid,
                            parent_event=effect_event.uuid,
                            transition_from=from_pos,
                            transition_to=to_pos,
                            directional_position=from_pos if directions else None,
                            directional_directions=directions or None,
                            directional_channels=["movement"] if directions and not cell_blocked else None,
                            )
                        grid._fire_spatial_event(collision_event)
                    break

                tile = grid.get_tile(*to_pos)
                step_cost_units = self._get_step_cost_units(tile, source_entity, source_entity.ignore_difficult_terrain)
                step_cost_feet = int(step_cost_units * 5)

                remaining_movement = source_entity.action_economy.movement.normalized_score
                if remaining_movement < step_cost_feet:
                    break

                step_event = StepMovementEvent(
                    source_entity_uuid=self.source_entity_uuid,
                    source_entity_name=source_entity.name,
                    from_position=from_pos,
                    to_position=to_pos,
                    path_index=i,
                    total_path_length=total_path_length,
                    movement_cost=step_cost_feet,
                    phase=EventPhase.EFFECT,
                    parent_event=effect_event.uuid,
                    use_register=False
                )
                processed_step = step_event.post(use_register=True)

                if processed_step.canceled:
                    break

                if "Dead" in source_entity.active_conditions or "Incapacitated" in source_entity.active_conditions:
                    interrupted_by_condition = True
                    break

                if not grid.can_transition(from_pos, to_pos, source_entity.uuid, self.movement_mode):
                    break

                Entity.update_entity_position(source_entity, to_pos, parent_event=processed_step.uuid)
                actual_end_position = to_pos

                processed_step.phase_to(EventPhase.COMPLETION)

                if "Dead" in source_entity.active_conditions:
                    break

                source_entity.action_economy.consume("movement", step_cost_feet)

        finally:
            source_entity.update_entity_senses(max_distance=20)

        if source_entity.position == execution_event.start_position:
            if interrupted_by_condition:
                return execution_event.phase_to(
                    new_phase=EventPhase.COMPLETION,
                    status_message=f"Partial movement for {execution_event.name}, stopped at {source_entity.position}",
                    end_position=actual_end_position
                )
            return effect_event.cancel(status_message=f"Failed to move for {execution_event.name}")
        elif source_entity.position != execution_event.end_position:
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
            if cost.cost_type == "movement":
                continue
            if cost.cost > 0:
                entity.action_economy.consume(cost.cost_type, cost.cost)
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


class Swim(Move):
    """Path-based swimming action that uses swimming terrain costs."""

    name: str = Field(default="Swim", description="Human-readable swimming action name.")
    description: str = Field(default="Swim to a water position", description="Swimming action description.")
    movement_mode: MovementMode = Field(default=MovementMode.SWIMMING, description="Movement mode used for terrain costs and transitions.")


class AttackEvent(ActionEvent):
    """Event payload for one weapon attack lifecycle."""

    name: str = Field(default="Attack", description="Human-readable attack event label.")
    costs: List[BaseCost] = Field(default_factory=list, description="Costs attached to this attack event.")
    weapon_slot: WeaponSlot = Field(description="Weapon slot used for the attack.")
    range: Optional[Range] = Field(default=None, description="Range band used by the attack.")
    is_long_range: bool = Field(default=False, description="Whether the target is beyond normal range.")
    is_threatened: bool = Field(default=False, description="Whether a hostile creature threatens the attacker.")
    attack_bonus: Optional[ModifiableValue] = Field(default=None, description="Attack-roll bonus used for this attack.")
    ac: Optional[ModifiableValue] = Field(default=None, description="Target armor class used for this attack.")
    dice_roll: Optional[DiceRoll] = Field(default=None, description="Attack d20 roll after result handlers.")
    attack_outcome: Optional[AttackOutcome] = Field(default=None, description="Resolved attack outcome.")
    damages: Optional[List[Damage]] = Field(default=None, description="Damage packets used on hit.")
    damage_rolls: Optional[List[DiceRoll]] = Field(default=None, description="Damage rolls after result handlers.")
    event_type: EventType = Field(default=EventType.ATTACK, description="Event category for attacks.")
    weapon_name: Optional[str] = Field(default=None, description="Display name of the weapon used.")
    override_ability: Optional[AbilityName] = Field(
        default=None,
        description="Ability override for attack and damage rolls.",
    )
    damage_types: List[DamageType] = Field(
        default_factory=list,
        description="Damage types exposed to visual effects and clients.",
    )

    def phase_to(self, new_phase: Optional[EventPhase] = None, status_message: Optional[str] = None, **updates: Any) -> Self:
        """Override to auto-update damage_types when damages are set."""
        if 'damages' in updates and updates['damages'] and 'damage_types' not in updates:
            updates['damage_types'] = list(dict.fromkeys(d.damage_type for d in updates['damages']))
        return super().phase_to(new_phase, status_message, **updates)

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for this attack event.

        Uses self.* fields only - no external lookups. Entity names and weapon name
        must be populated when the event is created.
        """
        source_name = self.source_entity_name or "Unknown"
        target_name = self.target_entity_name or "Unknown"
        weapon_name = self.weapon_name or "Unarmed"

        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

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

                adv_status = self.dice_roll.advantage_status
                if adv_status:
                    adv_value = adv_status.value.lower()
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

            attack_roll.bonus = self.dice_roll.bonus
            attack_roll.total = self.dice_roll.total

        attack_breakdown: List[ModifierBreakdown] = []
        if self.attack_bonus:
            for mod in self.attack_bonus.get_breakdown():
                attack_breakdown.append(ModifierBreakdown(
                    name=mod.get('name', 'Unknown'),
                    value=mod.get('value', 0),
                    source=mod.get('source', 'self')
                ))

        advantage_breakdown: List[ModifierBreakdown] = []
        if self.attack_bonus:
            for mod in self.attack_bonus.get_full_advantage_breakdown():
                adv_val = mod.get('value', 'inactive')
                if adv_val == 'advantage':
                    advantage_breakdown.append(ModifierBreakdown(
                        name=mod.get('name', 'Unknown'), value=1, source=mod.get('source', 'self')
                    ))
                elif adv_val == 'disadvantage':
                    advantage_breakdown.append(ModifierBreakdown(
                        name=mod.get('name', 'Unknown'), value=-1, source=mod.get('source', 'self')
                    ))

        target_ac = 0
        if self.ac:
            target_ac = self.ac.normalized_score
        elif target_entity:
            target_ac = target_entity.ac_bonus().normalized_score

        ac_breakdown: List[ModifierBreakdown] = []
        if self.ac:
            for mod in self.ac.get_breakdown():
                ac_breakdown.append(ModifierBreakdown(
                    name=mod.get('name', 'Unknown'),
                    value=mod.get('value', 0),
                    source=mod.get('source', 'self')
                ))

        outcome = "unknown"
        is_hit = False
        is_crit = False
        if self.attack_outcome:
            outcome_value = self.attack_outcome.value
            outcome = outcome_value.lower()
            is_hit = outcome in ("hit", "crit")
            is_crit = outcome == "crit"

        damage_roll_displays: List[DamageRollDisplay] = []
        total_damage = 0

        if self.damage_rolls and self.damages:
            for i, dr in enumerate(self.damage_rolls):
                damage = self.damages[i] if i < len(self.damages) else None
                damage_type = damage.damage_type.value if damage else "unknown"

                dice_results = []
                if dr.results is not None:
                    if isinstance(dr.results, list):
                        dice_results = list(dr.results)
                    elif isinstance(dr.results, int):
                        dice_results = [dr.results]

                damage_bonus_breakdown: List[ModifierBreakdown] = []
                if damage and damage.damage_bonus:
                    for mod in damage.damage_bonus.get_breakdown():
                        damage_bonus_breakdown.append(ModifierBreakdown(
                            name=mod.get('name', 'Unknown'),
                            value=mod.get('value', 0),
                            source=mod.get('source', 'self')
                        ))

                num_dice = len(dice_results)
                dice_size = damage.damage_dice if damage else 6
                dice_str = f"{num_dice}d{dice_size}"

                damage_roll_displays.append(DamageRollDisplay(
                    dice_str=dice_str,
                    dice_results=dice_results,
                    bonus=dr.bonus,
                    total=dr.total,
                    damage_type=damage_type,
                    bonus_breakdown=damage_bonus_breakdown
                ))

                total_damage += dr.total

        target_hp = target_entity.get_hp() if target_entity else None

        is_opportunity_attack = "opportunity" in (self.name or "").lower()

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

        data = AttackLogData(
            attacker_name=source_name,
            attacker_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
            weapon_name=weapon_name,
            weapon_slot=self.weapon_slot.value if self.weapon_slot else None,
            attack_roll=attack_roll,
            attack_breakdown=attack_breakdown,
            advantage_breakdown=advantage_breakdown,
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
    """Weapon attack action.

    Validation requires the target to be visible and inside the equipped weapon's
    range or reach. Off-hand attacks cost a bonus action instead of an action.
    Templates should receive a target through `set_target_entity()` before
    `pre_validate()` or `instantiate()`.
    """

    name: str = Field(default="Attack", description="Human-readable attack action name.")
    description: str = Field(default="Attack a target", description="Attack action description.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Attack targets one entity.")
    weapon_slot: WeaponSlot = Field(description="Weapon slot used by the attack.")
    action_category: ActionCategory = Field(default=ActionCategory.ATTACK, description="Attack action category.")
    costs: List[Cost] = Field(
        default_factory=lambda: [
            Cost(name="Attack Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
        ],
        description="Action economy costs required by this attack.",
    )
    override_ability: Optional[AbilityName] = Field(
        default=None,
        description="Ability override for attack and damage rolls.",
    )

    @model_validator(mode="after")
    def adjust_cost_for_off_hand(self) -> Self:
        """Convert off-hand attack cost from action to bonus action."""
        if self.weapon_slot in (WeaponSlot.MELEE_OFF, WeaponSlot.RANGED_OFF):
            self.costs = [Cost(name="Off-Hand Attack Cost", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)]
        return self

    @staticmethod
    def validate_range(declaration_event: AttackEvent, source_entity_uuid: UUID) -> Optional[AttackEvent]:
        """Validate if the source entity and target entity are in range.

        Ranged attacks inside normal range are allowed without the long-range
        flag. Ranged attacks between normal and long range are allowed with
        `is_long_range=True`. Melee attacks require distance within weapon reach.

        Args:
            declaration_event: Attack declaration event to validate.
            source_entity_uuid: Attacking entity UUID.

        Returns:
            Updated declaration event, canceled event, or `None`.
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
            if distance_feet <= weapon_range.normal:
                pass
            elif weapon_range.long is not None and distance_feet <= weapon_range.long:
                is_long_range = True
            else:
                return declaration_event.cancel(status_message=f"Target entity not in range for {declaration_event.name}")

        elif weapon_range.type == RangeType.REACH:
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

        Sets `is_threatened=True` for ranged attacks made while an enemy
        threatens the attacker.

        Args:
            declaration_event: Attack declaration event to inspect.
            source_entity_uuid: Attacking entity UUID.

        Returns:
            Updated declaration event, canceled event, or `None`.
        """
        source_entity = Entity.get(source_entity_uuid)
        if not source_entity or not isinstance(source_entity, Entity):
            return declaration_event.cancel(status_message=f"Source entity not found for {declaration_event.name}")

        is_threatened = False

        if declaration_event.range and declaration_event.range.type == RangeType.RANGE:
            is_threatened = source_entity.is_threatened()

        return declaration_event.phase_to(
            new_phase=EventPhase.DECLARATION,
            status_message=f"Checked ranged conditions for {declaration_event.name}",
            is_threatened=is_threatened
        )

    @staticmethod
    def attack_consequences(execution_event: AttackEvent, source_entity_uuid: UUID) -> Optional[AttackEvent]:
            """
            Resolve an attack roll, damage rolls, and damage application.

            Args:
                execution_event: Execution-phase attack event.
                source_entity_uuid: Attacking entity UUID.

            Returns:
                Completed attack event, canceled event, or `None`.
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

            def clear_temporary_targets() -> None:
                if should_clear_source_target:
                    source_entity.clear_target_entity()
                if should_clear_target_target:
                    target_entity.clear_target_entity()

            override_ability = execution_event.override_ability
            attack_bonus = source_entity.attack_bonus(weapon_slot=weapon_slot, target_entity_uuid=target_entity_uuid, override_ability=override_ability)
            ac = target_entity.ac_bonus(source_entity.uuid)
            ac.set_from_target(attack_bonus)
            attack_bonus.set_from_target(ac)
            attack_bonus.set_event_lineage(execution_event.lineage_uuid)
            ac.set_event_lineage(execution_event.lineage_uuid)
            weapon = source_entity.equipment._get_weapon_by_slot(weapon_slot)
            attack_context: Dict[str, Any] = {
                "weapon_slot": weapon_slot.value,
                "weapon_name": weapon.name if weapon else "Unarmed",
                "range_type": execution_event.range.type.value if execution_event.range else None,
                "is_long_range": execution_event.is_long_range,
            }
            attack_bonus.set_context(attack_context)

            ranged_disadvantage_modifiers: List[UUID] = []
            is_ranged = execution_event.range is not None and execution_event.range.type == RangeType.RANGE

            if is_ranged and execution_event.is_long_range:
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
                modifier_uuid = attack_bonus.self_static.add_advantage_modifier(
                    AdvantageModifier(
                        name="Threatened (Ranged)",
                        value=AdvantageStatus.DISADVANTAGE,
                        source_entity_uuid=source_entity_uuid,
                        target_entity_uuid=target_entity_uuid
                    )
                )
                ranged_disadvantage_modifiers.append(modifier_uuid)

            attack_event = execution_event.phase_to(
                new_phase=EventPhase.EXECUTION,
                status_message="Rolling attack",
                attack_bonus=attack_bonus,
                ac=ac
            )

            if attack_event.canceled:
                attack_bonus.clear_context()
                clear_temporary_targets()
                return attack_event

            dice_roll = source_entity.roll_d20(
                attack_bonus,
                RollType.ATTACK,
                weapon_slot=weapon_slot,
                parent_event=attack_event.uuid,
            )
            crit_threshold = source_entity.get_crit_threshold(weapon_slot)
            attack_outcome = determine_attack_outcome(dice_roll, ac, crit_threshold)

            attack_event = attack_event.post(
                dice_roll=dice_roll,
                attack_outcome=attack_outcome,
                status_message=f"Attack rolled {dice_roll.total} and {attack_outcome}"
            )
            ac.reset_from_target()
            attack_bonus.reset_from_target()
            attack_bonus.clear_event_lineage()
            ac.clear_event_lineage()
            attack_bonus.clear_context()

            if attack_event.canceled:
                clear_temporary_targets()
                return attack_event

            if attack_event.attack_outcome in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
                attack_event = attack_event.phase_to(
                    EventPhase.EFFECT,
                    status_message=f"Attack missed"
                )
                completion_event = attack_event.phase_to(
                    new_phase=EventPhase.COMPLETION,
                    status_message=f"Attack missed"
                )
                clear_temporary_targets()
                return completion_event

            damages = source_entity.get_damages(weapon_slot, target_entity_uuid, override_ability=override_ability)
            attack_event = attack_event.phase_to(
                EventPhase.EFFECT,
                is_last=False,
                status_message=f"Damages: {[(damage.dice_numbers,damage.damage_dice,damage.damage_bonus.normalized_score if damage.damage_bonus else 0,damage.damage_type) for damage in damages]}",
                damages=damages
            )

            if attack_event.canceled:
                clear_temporary_targets()
                return attack_event

            if attack_event.attack_outcome is not None and attack_event.attack_outcome not in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]:
                crit_extra_dice = source_entity.get_crit_extra_dice(weapon_slot)
                original_rolls = []
                for damage in damages:
                    dice = damage.get_dice(attack_outcome=attack_event.attack_outcome, crit_extra_dice=crit_extra_dice)
                    roll = dice.roll
                    original_rolls.append(roll)

                damage_roll_event = DamageRollResultEvent(
                    source_entity_uuid=source_entity.uuid,
                    target_entity_uuid=target_entity.uuid,
                    weapon_slot=weapon_slot,
                    attack_outcome=attack_event.attack_outcome,
                    damages=damages,
                    original_rolls=original_rolls,
                    final_rolls=list(original_rolls),
                    parent_event=attack_event.uuid,
                    phase=EventPhase.DECLARATION
                )

                damage_roll_event = damage_roll_event.phase_to(
                    EventPhase.EFFECT,
                    status_message="Damage dice rolled"
                )

                damage_rolls = damage_roll_event.final_rolls

                damage_roll_event.phase_to(EventPhase.COMPLETION)
                total_damage = sum(roll.total for roll in damage_rolls)

                target_entity.receive_damage(
                    amount=total_damage,
                    damage_type=damages[0].damage_type,
                    source_entity_uuid=source_entity.uuid,
                    damage_rolls=damage_rolls,
                    damages=damages,
                    parent_event=attack_event.uuid,
                    critical_hit=execution_event.attack_outcome == AttackOutcome.CRIT
                )

                attack_event = attack_event.phase_to(
                    new_phase=EventPhase.EFFECT,
                    is_first=False,
                    damage_rolls=damage_rolls,
                    status_message=f"Damages taken: {[damage.total for damage in damage_rolls]}"
                )
            else:
                damage_rolls = None

            clear_temporary_targets()

            return attack_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message="Attack completed",
                damage_rolls=damage_rolls,
            )

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the declaration event for the attack action."""
        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        source_name = source_entity.name if source_entity else None
        target_name = target_entity.name if target_entity else None

        weapon_name = None
        weapon_damage_types: List[DamageType] = []
        if source_entity:
            weapon = source_entity.equipment._get_weapon_by_slot(self.weapon_slot)
            weapon_name = weapon.name if weapon else "Unarmed"
            if isinstance(weapon, Weapon):
                weapon_damage_types = [weapon.damage_type] + list(weapon.extra_damage_type)
            else:
                weapon_damage_types = [source_entity.equipment.unarmed_damage_type]

        return AttackEvent(
            name=f"{self.name}",
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            weapon_slot=self.weapon_slot,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register,
            source_entity_name=source_name,
            target_entity_name=target_name,
            weapon_name=weapon_name,
            override_ability=self.override_ability,
            damage_types=weapon_damage_types
        )

    def _validate(self, declaration_event: AttackEvent) -> Optional[AttackEvent]:
        """Validate range, line of sight, and ranged-attack conditions."""
        range_validated_event = Attack.validate_range(declaration_event, self.source_entity_uuid)
        if range_validated_event is None:
            return declaration_event.cancel(status_message=f"Range validation returned None for {self.name}")
        elif range_validated_event.canceled:
            return range_validated_event

        line_of_sight_validated_event = validate_line_of_sight(range_validated_event, self.source_entity_uuid)
        if line_of_sight_validated_event is None:
            return declaration_event.cancel(status_message=f"Line of sight validation returned None for {self.name}")
        elif line_of_sight_validated_event.canceled:
            return line_of_sight_validated_event

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
        """Apply the attack action."""
        return Attack.attack_consequences(execution_event, self.source_entity_uuid)

    def _apply_costs(self, completion_event: AttackEvent) -> Optional[AttackEvent]:
        """Apply attack costs after completion."""
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)

    def apply(self, parent_event: Optional[Event] = None) -> Optional[AttackEvent]:
        """Override to provide specific return type."""
        result = super().apply(parent_event)
        return cast(AttackEvent, result) if result else None


class Dash(BaseAction):
    """Dash action that grants extra movement for the current turn.

    Applies the Dashing condition which adds movement equal to base speed.
    Lasts until the start of your next turn (duration=1, advanced at turn start).
    """

    name: str = Field(default="Dash", description="Human-readable dash action name.")
    description: str = Field(default="Gain extra movement equal to your speed", description="Dash action description.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Dash targets self")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Dash Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs required by Dash.")

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the declaration event for Dash."""
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Dash",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register,
            source_entity_name=source_name,
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        """Validate that the acting entity exists."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        """Apply Dashing for one round."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        dashing = Dashing(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid
        )
        dashing.duration.duration_type = DurationType.ROUNDS
        dashing.duration.duration = 1

        entity.add_condition(dashing, parent_event=execution_event)

        base_movement = entity.action_economy.get_base_value("movement")
        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Applied Dashing - gained {base_movement}ft extra movement"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        """Apply Dash action costs."""
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class Dodge(BaseAction):
    """Dodge action that applies the Dodging condition for one round.

    Applies the Dodging condition which gives:
    - Disadvantage on attack rolls against you (if you can see the attacker)
    - Advantage on Dexterity saving throws

    Lasts until the start of your next turn (duration=1, advanced at turn start).
    """

    name: str = Field(default="Dodge", description="Human-readable dodge action name.")
    description: str = Field(default="Attackers have disadvantage, advantage on DEX saves", description="Dodge action description.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Dodge targets self")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Dodge Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs required by Dodge.")

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the declaration event for Dodge."""
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Dodge",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register,
            source_entity_name=source_name,
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        """Validate that the acting entity exists."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        """Apply Dodging for one round."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        dodging = Dodging(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid
        )
        dodging.duration.duration_type = DurationType.ROUNDS
        dodging.duration.duration = 1

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message="Applying Dodging condition"
        )

        entity.add_condition(dodging, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message="Applied Dodging - attackers have disadvantage"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        """Apply Dodge action costs."""
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class Disengage(BaseAction):
    """Disengage action that suppresses opportunity attacks for one round.

    Applies the Disengaging condition which prevents opportunity attacks.
    Lasts until the start of your next turn (duration=1, advanced at turn start).
    """

    name: str = Field(default="Disengage", description="Human-readable disengage action name.")
    description: str = Field(default="Movement doesn't provoke opportunity attacks", description="Disengage action description.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Disengage targets self")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Disengage Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs required by Disengage.")

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the declaration event for Disengage."""
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Disengage",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register,
            source_entity_name=source_name,
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        """Validate that the acting entity exists."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        """Apply Disengaging for one round."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        disengaging = Disengaging(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid
        )
        disengaging.duration.duration_type = DurationType.ROUNDS
        disengaging.duration.duration = 1

        entity.add_condition(disengaging, parent_event=execution_event)

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message="Applied Disengaging - movement won't provoke OAs"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        """Apply Disengage action costs."""
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class DropConcentration(BaseAction):
    """Drop concentration on a spell voluntarily.

    D&D 5e allows ending concentration at any time (no action required).
    If target_spell is set, drops only that spell's slot (multi-slot support).
    Otherwise removes the entire Concentrating condition and all linked spell effects.
    """

    name: str = Field(default="Drop Concentration", description="Action name for voluntarily ending concentration.")
    description: str = Field(
        default="End concentration on current spell",
        description="Action description shown for voluntary concentration removal.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="DropConcentration targets the concentrating caster.",
    )
    action_category: ActionCategory = Field(
        default=ActionCategory.ABILITY,
        description="DropConcentration is a utility ability action.",
    )
    costs: List[Cost] = Field(
        default_factory=list,
        description="No-cost payload because dropping concentration is free.",
    )
    target_spell: Optional[str] = Field(default=None, description="Specific spell to drop (multi-slot). None = drop all.")

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the action declaration event for voluntary concentration drop."""
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Drop Concentration",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register,
            source_entity_name=source_name
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        if "Concentrating" not in entity.active_conditions:
            return declaration_event.cancel(status_message="Not concentrating on any spell")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        """Remove the requested concentration slot or the whole condition."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        if self.target_spell:
            conc = entity.active_conditions.get("Concentrating")
            if conc and isinstance(conc, Concentrating):
                slot_uuid = conc.get_slot_by_spell_name(self.target_spell)
                if slot_uuid is not None:
                    conc.drop_slot(slot_uuid, parent_event=execution_event)
        else:
            entity.remove_condition("Concentrating", parent_event=execution_event)

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Dropped concentration{' on ' + self.target_spell if self.target_spell else ''}"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        """Return completion unchanged because dropping concentration is free."""
        return completion_event


class ShakeAwake(BaseAction):
    """Wake a magically sleeping creature by spending an action."""
    name: str = Field(default="Shake Awake", description="Action name for waking a sleeping creature.")
    description: str = Field(
        default="Wake an adjacent creature affected by magical sleep",
        description="Rules-facing action summary.",
    )
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Creature target to wake.")
    action_category: ActionCategory = Field(default=ActionCategory.ABILITY, description="Utility action category.")
    costs: List[Cost] = Field(
        default_factory=lambda: [
            Cost(name="Shake Awake Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
        ],
        description="Action cost paid to wake the sleeper.",
    )
    valid_target_filter: str = Field(default="all", description="Allow any visible creature to be considered.")

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        """Validate that an adjacent other creature is magically asleep."""
        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not source or not target:
            return declaration_event.cancel(status_message="Source or target not found")
        if source.uuid == target.uuid:
            return declaration_event.cancel(status_message="Cannot shake yourself awake")
        if source.senses.get_feet_distance(target.position) > 5:
            return declaration_event.cancel(status_message="Target is not adjacent")
        if "Sleep" not in target.active_conditions and "Eyebite Asleep" not in target.active_conditions:
            return declaration_event.cancel(status_message="Target is not magically asleep")
        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        """Remove the matching magical sleep condition from the target."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return execution_event.cancel(status_message="Target not found")
        if "Eyebite Asleep" in target.active_conditions:
            target.remove_condition("Eyebite Asleep", parent_event=execution_event)
        elif "Sleep" in target.active_conditions:
            target.remove_condition("Sleep", parent_event=execution_event)
        else:
            return execution_event.cancel(status_message="Target is not magically asleep")
        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} wakes up"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        """Apply the action cost for waking the sleeper."""
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class Hide(BaseAction):
    """Take the Hide action - roll Stealth to become Hidden.

    Applies the Hidden condition with stealth_result = d20 + Stealth bonus.
    Hidden entities are not perceivable by observers with passive perception
    below the stealth result. Hidden also grants Unseen Attacker advantage.

    Hidden is removed automatically when the entity attacks, takes damage,
    or becomes incapacitated.
    """
    name: str = Field(default="Hide", description="Human-readable hide action name.")
    description: str = Field(default="Attempt to hide (Stealth check)", description="Player-facing hide action summary.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Hide targets self")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Hide Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid when taking the Hide action.")

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
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register,
            source_entity_name=source_name
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        grid = get_map()
        tile = grid.get_tile(*entity.position)
        if tile:
            light = tile.resolved_light_level
            if light == LightLevel.VERY_BRIGHT:
                return declaration_event.cancel(
                    status_message="Cannot hide in very bright light"
                )
            if light.value <= LightLevel.DIM_LIGHT.value:
                return declaration_event.phase_to(
                    new_phase=EventPhase.EXECUTION,
                    status_message=f"Validated {self.name}"
                )

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

        skill_bonus = entity.skill_bonus(target_entity_uuid=None, skill_name="stealth")
        stealth_roll = entity.roll_d20(skill_bonus, RollType.CHECK, skill_name="stealth", parent_event=execution_event.uuid)
        stealth_result = stealth_roll.total

        check_event = SkillCheckEvent(
            name="Stealth Check",
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            skill_name="stealth",
            bonus=skill_bonus,
            dice_roll=stealth_roll,
            parent_event=execution_event.uuid,
            source_entity_name=entity.name,
            phase=EventPhase.EFFECT,
        )
        check_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Stealth check: {stealth_result}"
        )

        hidden = Hidden(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            stealth_result=stealth_result  # type: ignore[call-arg]
        )
        entity.add_condition(hidden, parent_event=execution_event)

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Applied Hidden (Stealth DC {stealth_result})"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)

class StandUp(BaseAction):
    """
    Stand up from prone - costs half your movement speed.

    Removes the Prone condition. Can only be used while Prone.
    """
    name: str = Field(default="Stand Up", description="Human-readable stand-up action name.")
    description: str = Field(default="Stand up from prone", description="Player-facing stand-up action summary.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Stand Up targets self")

    def model_post_init(self, __context: Any) -> None:
        """Set movement cost to half of the acting entity's base movement."""
        super().model_post_init(__context)
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
            default_half_movement = 15
            self.costs = [Cost(
                name="Stand Up Cost",
                cost_type="movement",
                cost=default_half_movement,
                evaluator=entity_action_economy_cost_evaluator
            )]

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the stand-up declaration event."""
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Stand Up",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register,
            source_entity_name=source_name
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

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

        entity.remove_condition("Prone", parent_event=execution_event)

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
    name: str = Field(default="Drop Prone", description="Human-readable drop-prone action name.")
    description: str = Field(default="Drop to the ground", description="Player-facing drop-prone action summary.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Drop Prone targets self")
    costs: List[Cost] = Field(default_factory=list, description="Drop Prone has no action economy cost.")

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the drop-prone declaration event."""
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Drop Prone",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register,
            source_entity_name=source_name
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

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

        prone = Prone(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid
        )
        entity.add_condition(prone, parent_event=execution_event)

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message="Dropped prone"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        """Return a completed no-cost action event."""
        return completion_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message="No costs for Drop Prone"
        )


class JumpEvent(ActionEvent):
    """Event payload for a jump movement."""

    name: str = Field(default="Jump", description="Human-readable jump event label.")
    event_type: EventType = Field(default=EventType.MOVEMENT, description="Movement event category.")
    costs: List[BaseCost] = Field(default_factory=list, description="Serialized jump costs.")
    start_position: Tuple[int, int] = Field(description="Position occupied before the jump starts.")
    end_position: Tuple[int, int] = Field(description="Intended or actual landing position.")
    jump_distance: int = Field(default=0, description="Jump distance in feet.")
    path: Optional[List[Tuple[int, int]]] = Field(default=None, description="Straight-line airborne cell path.")

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Return jump path positions relevant to spatial handlers."""
        positions = {self.start_position, self.end_position}
        if self.path:
            positions.update(self.path)
        return positions

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate a combat log entry for this jump event."""
        source_name = self.source_entity_name or "Unknown"

        end_pos = f"({self.end_position[0]},{self.end_position[1]})"
        start_pos = f"({self.start_position[0]},{self.start_position[1]})"

        compact_text = f"{md_color(source_name, 'cyan')} {md_color('jumps', 'yellow')} {md_color(f'{self.jump_distance}ft', 'green')} to {md_color(end_pos, 'yellow')}"
        verbose_text = f"{md_color(source_name, 'cyan')} {md_color('jumps', 'yellow')} {start_pos} → {md_color(end_pos, 'green')} ({self.jump_distance}ft)"

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
    """Jump to a visible position using bonus action and movement.

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

    name: str = Field(default="Jump", description="Human-readable jump action name.")
    description: str = Field(default="Jump to a visible position", description="Jump action description.")
    target_type: TargetType = Field(default=TargetType.POSITION_LOS, description="Jump targets visible positions.")
    action_category: ActionCategory = Field(default=ActionCategory.MOVEMENT, description="Movement action category.")
    end_position: Optional[Tuple[int, int]] = Field(default=None, description="Requested landing position.")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Jump Cost", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs required by Jump.")

    def get_range(self) -> Optional[Range]:
        """Calculate jump range: (15 + STR_bonus + additive) * multiplier.

        STR component computed dynamically (like AC reads DEX).
        jump_distance_additive (base=0): extra flat bonus from spells/conditions.
        jump_distance_multiplier (base=1): Jump spell adds +2 → 3x.

        Examples (no modifiers):
        - STR 10 (mod +0): 15ft
        - STR 14 (mod +2): 25ft
        - STR 20 (mod +5): 40ft
        With Jump spell (multiplier=3): all values tripled.
        """
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return Range(type=RangeType.REACH, normal=15)

        base = 15 + max(0, entity.ability_scores.strength.modifier) * 5
        additive = entity.jump_distance_additive.normalized_score
        multiplier = entity.jump_distance_multiplier.normalized_score
        total_range = (base + additive) * multiplier
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

            distance = entity.senses.get_feet_distance(pos)
            if distance > max_range:
                continue

            if distance > movement_available:
                continue

            if not grid.is_walkable_for(pos[0], pos[1], entity.uuid):
                continue

            if not grid.raycast_clear(entity.position, pos, channel="propagation", observer_uuid=entity.uuid):
                continue

            valid.append(pos)

        return valid

    def set_target_position(self, position: Tuple[int, int]) -> None:
        """Set target position for jump."""
        super().set_target_position(position)
        self._setup_movement_cost()

    def _setup_movement_cost(self) -> None:
        """Set up movement cost based on jump distance."""
        if self.end_position is None:
            return

        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return

        distance = entity.senses.get_feet_distance(self.end_position)

        self.costs = [c for c in self.costs if c.cost_type != "movement"]

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

        update_dict: dict = {
            "uuid": uuid4(),
            "template": False,
            "use_register": False,
            "costs": [Cost(name="Jump Cost", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)],
        }
        update_dict.update(overrides)

        instance = self.model_copy(deep=True, update=update_dict)
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

        self._setup_movement_cost()

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
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
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

        if end_pos not in source_entity.senses.visible or not source_entity.senses.visible[end_pos]:
            return declaration_event.cancel(status_message=f"Position {end_pos} not visible")

        action_range = self.get_range()
        max_range = action_range.normal if action_range else 15
        distance = source_entity.senses.get_feet_distance(end_pos)
        if distance > max_range:
            return declaration_event.cancel(status_message=f"Position {end_pos} out of jump range ({distance}ft > {max_range}ft)")

        movement_available = source_entity.action_economy.movement.normalized_score
        if distance > movement_available:
            return declaration_event.cancel(status_message=f"Not enough movement ({distance}ft > {movement_available}ft)")

        if not grid.is_walkable_for(end_pos[0], end_pos[1], source_entity.uuid):
            return declaration_event.cancel(status_message=f"Position {end_pos} not walkable or occupied")

        if not grid.raycast_clear(source_entity.position, end_pos, channel="propagation", observer_uuid=source_entity.uuid):
            return declaration_event.cancel(status_message=f"Path to {end_pos} is blocked")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated jump to {end_pos}"
        )

    def _apply(self, execution_event: JumpEvent) -> JumpEvent:
        """Apply the jump - step through path cells firing StepMovementEvents.

        Like Move, iterates cell-by-cell so opportunity attacks and reactions
        can fire at each step. Unlike Move, intermediate cells are NOT checked
        for walkability (the entity is airborne). Movement is consumed per-step.
        """
        source_entity = Entity.get(self.source_entity_uuid)
        if not source_entity:
            return execution_event.cancel(status_message="Entity not found")

        path = execution_event.path or []
        total_path_length = len(path)
        actual_end_position = source_entity.position
        interrupted_by_condition = False

        try:
            effect_event = execution_event.phase_to(
                new_phase=EventPhase.EFFECT,
                status_message=f"Jumping to {execution_event.end_position}"
            )
            if effect_event.canceled:
                return effect_event

            for i in range(1, total_path_length):
                from_pos = path[i - 1]
                to_pos = path[i]

                step_cost_feet = 5
                remaining_movement = source_entity.action_economy.movement.normalized_score
                if remaining_movement < step_cost_feet:
                    break

                step_event = StepMovementEvent(
                    source_entity_uuid=self.source_entity_uuid,
                    source_entity_name=source_entity.name,
                    from_position=from_pos,
                    to_position=to_pos,
                    path_index=i,
                    total_path_length=total_path_length,
                    movement_cost=step_cost_feet,
                    phase=EventPhase.EFFECT,
                    parent_event=effect_event.uuid,
                    use_register=False
                )
                processed_step = step_event.post(use_register=True)

                if processed_step.canceled:
                    break

                if "Dead" in source_entity.active_conditions or "Incapacitated" in source_entity.active_conditions:
                    interrupted_by_condition = True
                    break

                Entity.update_entity_position(source_entity, to_pos, parent_event=processed_step.uuid)
                actual_end_position = to_pos

                processed_step.phase_to(EventPhase.COMPLETION)

                if "Dead" in source_entity.active_conditions:
                    break

                source_entity.action_economy.consume("movement", step_cost_feet)

            if source_entity.position == execution_event.start_position:
                if interrupted_by_condition:
                    return execution_event.phase_to(
                        new_phase=EventPhase.COMPLETION,
                        status_message=f"Partial jump, stopped at {source_entity.position}",
                        end_position=actual_end_position
                    )
                return effect_event.cancel(status_message=f"Failed to jump")
            elif source_entity.position != execution_event.end_position:
                return execution_event.phase_to(
                    new_phase=EventPhase.COMPLETION,
                    status_message=f"Partial jump, stopped at {source_entity.position}",
                    end_position=actual_end_position
                )

            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"Jumped to {execution_event.end_position}"
            )
        finally:
            source_entity.update_entity_senses(max_distance=20)

    def _apply_costs(self, completion_event: JumpEvent) -> JumpEvent:
        """Apply the costs of the jump (bonus action). Movement consumed per-step in _apply()."""
        entity = Entity.get(self.source_entity_uuid)
        if entity is None or not isinstance(entity, Entity):
            return completion_event.cancel(status_message=f"Entity not found for {completion_event.name}")

        if "Dead" in entity.active_conditions or "Incapacitated" in entity.active_conditions:
            return completion_event

        for cost in completion_event.costs:
            if cost.cost_type == "movement":
                continue
            if cost.cost > 0:
                entity.action_economy.consume(cost.cost_type, cost.cost)
        return completion_event


class ShoveEvent(ActionEvent):
    """Event payload for a BG3-style shove action.

    Shove is a BG3-style bonus action that pushes adjacent enemies.
    Key mechanics:
    - Cost: Bonus Action
    - Range: 5ft (adjacent only)
    - Contest: Shover's Athletics CHECK vs target's passive skill DC
    - Allies: Auto-succeed (no check required)
    - Weight limit: STR score x 12
    """

    name: str = Field(default="Shove", description="Human-readable shove event label.")
    event_type: EventType = Field(default=EventType.BASE_ACTION, description="Base action event category.")
    costs: List[BaseCost] = Field(default_factory=list, description="Serialized shove costs.")
    target_weight: int = Field(default=0, description="Target's weight in pounds")
    max_shove_weight: int = Field(default=0, description="Maximum weight shover can push in pounds.")
    shover_athletics: Optional[ModifiableValue] = Field(default=None, description="Shover's Athletics bonus")
    target_passive: int = Field(default=10, description="Target's passive Athletics or Acrobatics")
    target_resistance_skill: str = Field(default="athletics", description="Target skill used for passive resistance.")
    dice_roll: Optional[DiceRoll] = Field(default=None, description="Shover's Athletics check roll")
    contest_success: Optional[bool] = Field(default=None, description="Whether the shove contest succeeded.")
    push_distance: int = Field(default=0, description="Distance actually pushed in feet.")
    push_direction: Tuple[int, int] = Field(default=(0, 0), description="Push direction as grid delta.")
    end_position: Optional[Tuple[int, int]] = Field(default=None, description="Target's final position after push.")
    knocked_prone: bool = Field(default=False, description="Whether target was knocked prone instead of pushed.")
    blocked_by: Optional[str] = Field(default=None, description="Obstacle or entity that blocked the push.")
    is_ally: bool = Field(default=False, description="Whether target is an ally and auto-succeeds.")

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Return final shove position relevant to spatial handlers."""
        positions = super().get_affected_positions()
        if self.end_position:
            positions.add(self.end_position)
        return positions

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate combat log for a shove event."""
        source_name = self.source_entity_name or "Unknown"
        target_name = self.target_entity_name or "Unknown"

        if self.contest_success is False:
            compact_text = f"{md_color(source_name, 'cyan')} fails to shove {md_color(target_name, 'yellow')}"
        elif self.knocked_prone:
            compact_text = f"{md_color(source_name, 'cyan')} knocks {md_color(target_name, 'yellow')} {md_color('prone', 'red')}!"
        elif self.push_distance > 0:
            pos_str = f"→ {self.end_position}" if self.end_position else ""
            compact_text = f"{md_color(source_name, 'cyan')} shoves {md_color(target_name, 'yellow')} {md_color(f'{self.push_distance}ft', 'green')} {pos_str}"
        else:
            blocked_suffix = f" (blocked by {self.blocked_by})" if self.blocked_by else " (blocked)"
            compact_text = f"{md_color(source_name, 'cyan')} shoves {md_color(target_name, 'yellow')}{blocked_suffix}"

        verbose_text = compact_text
        if not self.is_ally and self.dice_roll is not None:
            roll_total = self.dice_roll.total
            success_str = md_color("success", "green") if self.contest_success else md_color("fail", "red")
            verbose_text += f"\n  Athletics: d20({md_color(str(roll_total), 'cyan')}) vs DC {self.target_passive} → {success_str}"
        elif self.is_ally:
            verbose_text += f" ({md_color('ally', 'green')})"

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
                "blocked_by": self.blocked_by,
                "is_ally": self.is_ally
            },
            success=self.contest_success or False
        )


class Shove(BaseAction):
    """BG3-style shove action that pushes or knocks prone.

    Costs a bonus action. Pushes target 5-20ft based on STR, or knocks prone.

    Mechanics (BG3-style):
    - Range: 5ft (adjacent only)
    - Contest: Shover's Athletics CHECK vs target's passive DC
    - Target DC: 10 + max(Athletics, Acrobatics) bonus + advantage modifier
    - Allies: Auto-succeed (no check required)
    - Weight limit: Can't shove targets heavier than STR x 12 lbs
    - Distance: 5ft base + 5ft per positive STR modifier (max 20ft)

    Forced movement does NOT trigger opportunity attacks.
    """

    name: str = Field(default="Shove", description="Human-readable shove action name.")
    description: str = Field(default="Push an adjacent enemy", description="Shove action description.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Shove targets one entity.")
    knock_prone: bool = Field(default=False, description="Whether shove knocks prone instead of pushing.")
    include_allies: bool = Field(default=True, description="Whether allies are valid shove targets.")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Shove Cost", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs required by Shove.")

    @staticmethod
    def get_max_shove_weight(entity: Entity) -> int:
        """Calculate max weight entity can shove.

        Args:
            entity: Entity attempting the shove.

        Returns:
            Maximum shoveable weight in pounds.
        """
        return entity.ability_scores.strength.ability_score.score * 12

    @staticmethod
    def get_push_distance(entity: Entity) -> int:
        """Calculate push distance based on Strength.

        Args:
            entity: Entity attempting the shove.

        Returns:
            Push distance in feet.
        """
        str_mod = entity.ability_scores.strength.modifier
        bonus = max(0, str_mod) * 5
        return min(20, max(5, 5 + bonus))

    @staticmethod
    def get_push_direction(source_pos: Tuple[int, int], target_pos: Tuple[int, int]) -> Tuple[int, int]:
        """Calculate push direction as unit vector from source to target.

        Args:
            source_pos: Shoving entity position.
            target_pos: Target entity position.

        Returns:
            Unit direction as `(dx, dy)`.
        """
        dx = target_pos[0] - source_pos[0]
        dy = target_pos[1] - source_pos[1]

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
    ) -> Tuple[Tuple[int, int], int, bool, Optional[str]]:
        """Calculate where target lands after being pushed.

        Walks cells in push direction until:
        - Reached desired distance, OR
        - Hit unwalkable tile, OR
        - Hit cell occupied by another entity

        Target MUST land on a walkable tile.

        Args:
            start: Target's current position
            direction: Push direction as (dx, dy)
            distance_feet: How far to push in feet.
            target_uuid: UUID of entity being pushed, excluded from occupancy checks.

        Returns:
            Final position, actual distance, blocked flag, and blocker label.
        """
        grid = get_map()
        current = start
        cells_to_move = distance_feet // 5
        actual_cells = 0
        blocked = False
        blocked_by: Optional[str] = None

        for _ in range(cells_to_move):
            next_pos = (current[0] + direction[0], current[1] + direction[1])

            if not grid.can_transition(current, next_pos, target_uuid):
                blocked = True
                blocked_by = grid.identify_blocker_at(next_pos, target_uuid)
                break

            current = next_pos
            actual_cells += 1

        return current, actual_cells * 5, blocked, blocked_by

    @staticmethod
    def calculate_forced_movement_path(
        start: Tuple[int, int],
        direction: Tuple[int, int],
        distance_feet: int
    ) -> List[Tuple[int, int]]:
        """Return every traversed cell for a straight forced displacement.

        Args:
            start: Position before forced movement begins.
            direction: Unit displacement direction as `(dx, dy)`.
            distance_feet: Distance to traverse in feet.

        Returns:
            Ordered destination cells, one per 5-foot transition.
        """
        path: List[Tuple[int, int]] = []
        current = start

        for _ in range(distance_feet // 5):
            current = (current[0] + direction[0], current[1] + direction[1])
            path.append(current)

        return path

    def pre_validate(self) -> bool:
        """Run cheap validation for action discovery."""
        if not super().pre_validate():
            return False

        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source or not target:
            return False

        distance = source.senses.get_feet_distance(target.position)
        if distance > 5:
            return False

        max_weight = self.get_max_shove_weight(source)
        if target.weight > max_weight:
            return False

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
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
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

        distance = source.senses.get_feet_distance(target.position)
        if distance > 5:
            return declaration_event.cancel(status_message=f"Target not adjacent ({distance}ft)")

        if target.weight > declaration_event.max_shove_weight:
            return declaration_event.cancel(
                status_message=f"Target too heavy ({target.weight}lbs > {declaration_event.max_shove_weight}lbs)"
            )

        if target.uuid not in source.senses.entities:
            return declaration_event.cancel(status_message="Target not visible")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message="Shove validated"
        )

    def _apply(self, execution_event: ShoveEvent) -> ShoveEvent:
        """Resolve the shove contest and apply push or prone effects."""
        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(execution_event.target_entity_uuid) if execution_event.target_entity_uuid else None

        if not source or not target:
            return execution_event.cancel(status_message="Entity not found")

        if source.is_ally(target):
            contest_success = True
            dice_roll = None
            target_passive = 0
            target_skill = "none"
        else:
            athletics_bonus = source.skill_bonus(target.uuid, "athletics")

            passive_athletics = target.passive_skill("athletics")
            passive_acrobatics = target.passive_skill("acrobatics")

            if passive_athletics >= passive_acrobatics:
                target_passive = passive_athletics
                target_skill = "athletics"
            else:
                target_passive = passive_acrobatics
                target_skill = "acrobatics"

            dice_roll = source.roll_d20(athletics_bonus, RollType.CHECK, parent_event=execution_event.uuid)
            contest_success = dice_roll.total >= target_passive

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

        if not contest_success:
            return execution_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message="Shove failed - target resisted"
            )

        if self.knock_prone:
            prone_condition = Prone(
                source_entity_uuid=source.uuid,
                target_entity_uuid=target.uuid
            )
            target.add_condition(prone_condition, parent_event=execution_event)

            return execution_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                knocked_prone=True,
                status_message=f"{target.name} knocked prone"
            )

        direction = self.get_push_direction(source.position, target.position)
        distance = self.get_push_distance(source)
        final_pos, actual_dist, blocked, blocked_by = self.calculate_final_position(
            target.position, direction, distance, target.uuid
        )

        push_direction = direction
        push_distance = actual_dist

        if actual_dist > 0:
            movement_path = self.calculate_forced_movement_path(target.position, direction, actual_dist)
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
                blocked_by=blocked_by,
                cause="shove",
                phase=EventPhase.DECLARATION,
                parent_event=execution_event.uuid
            )

            forced_event = forced_event.phase_to(EventPhase.EXECUTION)
            forced_event = forced_event.phase_to(EventPhase.EFFECT)

            moved_cells = 0
            interrupted_by_condition = False

            if not forced_event.canceled:
                for next_pos in movement_path:
                    Entity.update_entity_position(target, next_pos, parent_event=forced_event.uuid)
                    moved_cells += 1

                    if "Dead" in target.active_conditions or "Incapacitated" in target.active_conditions:
                        interrupted_by_condition = True
                        break

            push_distance = moved_cells * 5
            final_pos = target.position

            if interrupted_by_condition:
                blocked = False
                blocked_by = None

            forced_event.phase_to(
                EventPhase.COMPLETION,
                end_position=final_pos,
                actual_distance=push_distance,
                blocked_by_obstacle=blocked,
                blocked_by=blocked_by,
                status_message=(
                    f"Forced movement interrupted at {final_pos}"
                    if interrupted_by_condition
                    else f"Forced movement completed at {final_pos}"
                )
            )

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            push_distance=push_distance,
            push_direction=push_direction,
            end_position=final_pos,
            blocked_by=blocked_by,
            status_message=f"Shoved {target.name} {push_distance}ft" + (f" (blocked by {blocked_by})" if blocked and blocked_by else " (blocked)" if blocked else "")
        )

    def _apply_costs(self, completion_event: ShoveEvent) -> ShoveEvent:
        """Apply shove costs (bonus action)."""
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)

class SpellEvent(ActionEvent):
    """Event payload for spell casting and spell effect logs."""

    name: str = Field(default="Spell Cast", description="A spell cast event")
    event_type: EventType = Field(default=EventType.CAST_SPELL, description="The type of event")
    spell_id: Optional[str] = Field(default=None, description="Stable spell catalog id")
    spell_level: int = Field(default=0, description="Base spell level (0 = cantrip)")
    cast_at_level: int = Field(default=0, description="Actual slot level used (0 = cantrip)")
    spell_school: str = Field(default="evocation", description="School of magic")
    verbal: bool = Field(default=True, description="Whether spell has a verbal component")

    attack_bonus: Optional[ModifiableValue] = Field(default=None, description="The spell attack bonus")
    ac: Optional[ModifiableValue] = Field(default=None, description="The target's AC")
    dice_roll: Optional[DiceRoll] = Field(default=None, description="The attack roll result")
    attack_outcome: Optional[AttackOutcome] = Field(default=None, description="The attack outcome")

    save_ability: Optional[AbilityName] = Field(default=None, description="Ability for saving throw")
    save_dc: Optional[int] = Field(default=None, description="Save DC")
    save_success: Optional[bool] = Field(default=None, description="Whether the save succeeded")
    save_roll: Optional[DiceRoll] = Field(default=None, description="The save roll result")
    save_bonus: Optional[int] = Field(default=None, description="Target's save bonus")

    damages: Optional[List[Damage]] = Field(default=None, description="The damages dealt")
    damage_rolls: Optional[List[DiceRoll]] = Field(default=None, description="The damage roll results")

    aoe_shape_type: Optional[str] = Field(default=None, description="AoE shape: sphere, cone, line, cube, cylinder")
    aoe_radius_ft: Optional[int] = Field(default=None, description="AoE size in feet")
    range_type: Optional[str] = Field(default=None, description="Delivery type: self, touch, ranged")
    range_ft: Optional[int] = Field(default=None, description="Spell range in feet")
    projectile_type: Optional[str] = Field(default=None, description="Visual projectile delivery type")
    damage_types: List[DamageType] = Field(default_factory=list, description="Damage types for VFX (populated at declaration, updated on hit)")

    def phase_to(self, new_phase: Optional[EventPhase] = None, status_message: Optional[str] = None, **updates: Any) -> Self:
        """Override to auto-update damage_types when damages are set."""
        if 'damages' in updates and updates['damages'] and 'damage_types' not in updates:
            updates['damage_types'] = list(dict.fromkeys(d.damage_type for d in updates['damages']))
        return super().phase_to(new_phase, status_message, **updates)

    def generate_combat_log(self) -> CombatLogEntry:
        """Generate combat log for spell effects.

        Returns:
            Spell-specific combat log entry for multi-target, saving throw,
            spell attack, auto-hit, or generic cast events.
        """
        if self.total_targets > 0:
            return self._generate_multi_target_log()

        if self.save_dc is not None and self.save_success is not None:
            return self._generate_save_spell_log()

        if self.attack_outcome is not None:
            return self._generate_attack_spell_log()

        if self.damage_rolls and self.target_entity_name:
            return self._generate_autohit_spell_log()

        parent_log = super().generate_combat_log()
        if parent_log is not None:
            return parent_log
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
        """Generate a combat log entry for a single-target save spell."""
        target_name = self.target_entity_name or "Unknown"
        caster_name = self.source_entity_name or "Unknown"
        spell_name = self.name or "Spell"
        ability = (self.save_ability or "dexterity").upper()[:3]
        dc = self.save_dc or 10
        success = self.save_success or False
        total_dmg = self.total_damage or 0

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

        damage_displays: List[DamageRollDisplay] = []
        damage_type = "damage"
        base_damage = 0
        if self.damage_rolls:
            for i, dr in enumerate(self.damage_rolls):
                dmg_type = self.damages[i].damage_type.value if self.damages and i < len(self.damages) else "damage"
                damage_type = dmg_type
                dr_results = dr.results
                if isinstance(dr_results, list):
                    dice_results = list(dr_results)
                else:
                    dice_results = [dr_results] if dr_results else []
                base_damage = dr.total
                damage_displays.append(DamageRollDisplay(
                    dice_str=f"{len(dice_results)}d{self.damages[i].damage_dice if self.damages and i < len(self.damages) else 6}",
                    dice_results=dice_results,
                    bonus=0,
                    total=dr.total,
                    damage_type=dmg_type
                ))

        outcome_str = md_color("SAVE", "green") if success else md_color("FAIL", "red")
        half_note = " (half)" if success and total_dmg > 0 else ""
        compact = f"{md_color(target_name, 'yellow')}: {ability} save {outcome_str}, {md_color(str(total_dmg), 'red')} {damage_type}{half_note}"

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

        detailed = verbose

        save_bonus_breakdown: List[ModifierBreakdown] = []
        save_advantage_breakdown: List[ModifierBreakdown] = []
        if self.target_entity_uuid and self.save_ability:
            target_entity = Entity.get(self.target_entity_uuid)
            if target_entity:
                save_mv = target_entity.saving_throw_bonus(
                    self.source_entity_uuid, self.save_ability
                )
                for mod in save_mv.get_breakdown():
                    save_bonus_breakdown.append(ModifierBreakdown(
                        name=mod.get('name', 'Unknown'),
                        value=mod.get('value', 0),
                        source=mod.get('source', 'self')
                    ))
                for mod in save_mv.get_full_advantage_breakdown():
                    adv_val = mod.get('value', 'inactive')
                    if adv_val == 'advantage':
                        save_advantage_breakdown.append(ModifierBreakdown(
                            name=mod.get('name', 'Unknown'), value=1, source=mod.get('source', 'self')
                        ))
                    elif adv_val == 'disadvantage':
                        save_advantage_breakdown.append(ModifierBreakdown(
                            name=mod.get('name', 'Unknown'), value=-1, source=mod.get('source', 'self')
                        ))

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
            save_bonus_breakdown=save_bonus_breakdown,
            save_advantage_breakdown=save_advantage_breakdown,
            save_success=success,
            damage_rolls=damage_displays,
            base_damage=base_damage,
            final_damage=total_dmg,
            damage_type=damage_type
        )

        spell_effect_succeeded = not success
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
            success=spell_effect_succeeded
        )

    def _generate_attack_spell_log(self) -> CombatLogEntry:
        """Generate combat log for attack-based spell (Fire Bolt, Guiding Bolt, etc.).

        Follows AttackEvent.generate_combat_log() pattern but uses spell name
        instead of weapon name.
        """
        source_name = self.source_entity_name or "Unknown"
        target_name = self.target_entity_name or "Unknown"
        spell_name = self.name or "Spell"

        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        attack_roll = DiceRollDisplay(dice_str="d20", results=[], bonus=0, total=0)
        if self.dice_roll:
            results = self.dice_roll.results
            if isinstance(results, list):
                attack_roll.results = list(results)
                attack_roll.all_d20_rolls = list(results)
                adv_status = self.dice_roll.advantage_status
                if adv_status:
                    adv_value = adv_status.value.lower()
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
            attack_roll.bonus = self.dice_roll.bonus
            attack_roll.total = self.dice_roll.total

        attack_breakdown: List[ModifierBreakdown] = []
        if self.attack_bonus:
            for mod in self.attack_bonus.get_breakdown():
                attack_breakdown.append(ModifierBreakdown(
                    name=mod.get('name', 'Unknown'),
                    value=mod.get('value', 0),
                    source=mod.get('source', 'self')
                ))

        advantage_breakdown: List[ModifierBreakdown] = []
        if self.attack_bonus:
            for mod in self.attack_bonus.get_full_advantage_breakdown():
                adv_val = mod.get('value', 'inactive')
                if adv_val == 'advantage':
                    advantage_breakdown.append(ModifierBreakdown(
                        name=mod.get('name', 'Unknown'), value=1, source=mod.get('source', 'self')
                    ))
                elif adv_val == 'disadvantage':
                    advantage_breakdown.append(ModifierBreakdown(
                        name=mod.get('name', 'Unknown'), value=-1, source=mod.get('source', 'self')
                    ))

        target_ac = 0
        if self.ac:
            target_ac = self.ac.normalized_score
        elif target_entity:
            target_ac = target_entity.ac_bonus().normalized_score

        ac_breakdown: List[ModifierBreakdown] = []
        if self.ac:
            for mod in self.ac.get_breakdown():
                ac_breakdown.append(ModifierBreakdown(
                    name=mod.get('name', 'Unknown'),
                    value=mod.get('value', 0),
                    source=mod.get('source', 'self')
                ))

        outcome = "unknown"
        is_hit = False
        is_crit = False
        if self.attack_outcome:
            outcome_value = self.attack_outcome.value
            outcome = outcome_value.lower()
            is_hit = outcome in ("hit", "crit")
            is_crit = outcome == "crit"

        damage_roll_displays: List[DamageRollDisplay] = []
        total_damage = 0
        if self.damage_rolls and self.damages:
            for i, dr in enumerate(self.damage_rolls):
                damage = self.damages[i] if i < len(self.damages) else None
                damage_type = damage.damage_type.value if damage else "unknown"
                dice_results = []
                if dr.results is not None:
                    if isinstance(dr.results, list):
                        dice_results = list(dr.results)
                    elif isinstance(dr.results, int):
                        dice_results = [dr.results]
                damage_bonus_breakdown: List[ModifierBreakdown] = []
                if damage and damage.damage_bonus:
                    for mod in damage.damage_bonus.get_breakdown():
                        damage_bonus_breakdown.append(ModifierBreakdown(
                            name=mod.get('name', 'Unknown'),
                            value=mod.get('value', 0),
                            source=mod.get('source', 'self')
                        ))
                num_dice = len(dice_results)
                dice_size = damage.damage_dice if damage else 6
                dice_str = f"{num_dice}d{dice_size}"
                damage_roll_displays.append(DamageRollDisplay(
                    dice_str=dice_str,
                    dice_results=dice_results,
                    bonus=dr.bonus,
                    total=dr.total,
                    damage_type=damage_type,
                    bonus_breakdown=damage_bonus_breakdown
                ))
                total_damage += dr.total

        compact_text = format_attack_compact(
            source_name, target_name, outcome, total_damage
        )
        verbose_text = format_attack_verbose(
            source_name, target_name, spell_name,
            attack_roll, target_ac, outcome,
            damage_roll_displays, total_damage
        )
        detailed_text = format_attack_detailed(
            source_name, target_name, spell_name,
            attack_roll, attack_breakdown,
            target_ac, ac_breakdown, outcome,
            damage_roll_displays, total_damage
        )

        target_hp = target_entity.get_hp() if target_entity else None
        data = AttackLogData(
            attacker_name=source_name,
            attacker_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else "",
            weapon_name=spell_name,
            attack_roll=attack_roll,
            attack_breakdown=attack_breakdown,
            advantage_breakdown=advantage_breakdown,
            target_ac=target_ac,
            ac_breakdown=ac_breakdown,
            outcome=outcome,
            is_hit=is_hit,
            is_crit=is_crit,
            damage_rolls=damage_roll_displays,
            total_damage=total_damage,
            target_hp=target_hp
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

    def _generate_autohit_spell_log(self) -> CombatLogEntry:
        """Generate a combat log entry for an auto-hit damaging spell."""
        target_name = self.target_entity_name or "Unknown"
        caster_name = self.source_entity_name or "Unknown"
        spell_name = self.name or "Spell"
        total_dmg = self.total_damage or 0

        damage_type = "force"
        if self.damages and len(self.damages) > 0:
            damage_type = self.damages[0].damage_type.value

        dice_str = ""
        if self.damage_rolls and len(self.damage_rolls) > 0:
            dr = self.damage_rolls[0]
            results = dr.results if isinstance(dr.results, list) else [dr.results]
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

        compact = f"{md_color(spell_name, 'yellow')} {md_color('hits', 'green')} {md_color(target_name, 'cyan')} for {md_color(str(total_dmg), 'red')} {damage_type} damage"

        verbose = compact + dice_str

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

    Spell subclasses implement their own `_apply()` logic. This base class
    provides spell metadata, upcast variant generation, action and slot costs,
    concentration bookkeeping, and client-facing declaration metadata.
    """

    action_category: ActionCategory = Field(default=ActionCategory.SPELL, description="Classifies this action as a spell.")

    spell_level: int = Field(default=0, description="Base spell level (0 = cantrip)")
    spell_school: str = Field(default="evocation", description="School of magic")
    concentration: bool = Field(default=False, description="Whether spell requires concentration")
    verbal: bool = Field(default=True, description="Whether spell has a verbal component")

    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Range of the spell"
    )

    cast_at_level: int = Field(default=0, description="Actual slot level used (0 = cantrip)")
    is_variant: bool = Field(default=False, description="Whether this is an upcast variant")

    caster_level: int = Field(default=1, description="Level of the caster (for cantrip scaling)")

    cast_concentrating_uuid: Optional[UUID] = Field(
        default=None,
        exclude=True,
        description="Concentrating condition UUID reused across one convolution cast.",
    )

    alt_range: Optional[int] = Field(default=None, description="Override spell_range.normal")

    projectile_type: Optional[str] = Field(default=None, description="VFX projectile delivery type")
    spell_damage_type: Optional[DamageType] = Field(default=None, description="Primary damage type for VFX")

    costs: List[Cost] = Field(
        default_factory=lambda: [Cost(name="Cast Spell", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)],
        description="Action cost for casting"
    )

    def model_post_init(self, __context: Any) -> None:
        """Set concentration flags and append slot costs for leveled spells."""
        super().model_post_init(__context)
        if self.concentration:
            self.requires_concentration = True
        if self.spell_level > 0:
            if self.cast_at_level == 0:
                self.cast_at_level = self.spell_level
            has_slot_cost = any(c.cost_type.startswith("spell_slot") for c in self.costs)
            if not has_slot_cost:
                cost_type = spell_slot_cost_type(self.cast_at_level)
                self.costs.append(Cost(
                    name=f"Spell Slot L{self.cast_at_level}",
                    cost_type=cost_type,
                    cost=1,
                    evaluator=entity_action_economy_cost_evaluator
                ))

    @property
    def effective_range(self) -> int:
        """Spell range with alt override applied."""
        if self.alt_range is not None:
            return self.alt_range
        return self.spell_range.normal

    def get_range(self) -> Range:
        """Return spell range with alt_range override for position filtering."""
        return Range(type=self.spell_range.type, normal=self.effective_range, long=self.spell_range.long)

    def get_upcast_bonus(self) -> int:
        """Get levels above base spell level (for upcast scaling)."""
        return max(0, self.cast_at_level - self.spell_level)

    def ensure_concentration(self, parent_event: Event) -> "Concentrating":
        """Create or reuse Concentrating for this cast. Safe for convolution loop.

        The first call for a cast creates Concentrating and replaces any older
        concentration. Later calls in the same convolution loop reuse the UUID
        created by the first target.
        """
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            raise ValueError("Caster not found")

        if self.cast_concentrating_uuid:
            existing = caster.active_conditions_by_uuid.get(self.cast_concentrating_uuid)
            if existing and isinstance(existing, Concentrating):
                return existing

        conc = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name=self.name or "Unknown",
        )
        caster.add_condition(conc, parent_event=parent_event)
        self.cast_concentrating_uuid = conc.uuid
        result = caster.active_conditions["Concentrating"]
        assert isinstance(result, Concentrating)
        return result

    def _cleanup_concentration(self, completion_event: ActionEvent) -> None:
        """Remove Concentrating if all targets saved (0-children bug fix).

        Also clean up empty slots in multi-slot scenarios."""
        if not self.cast_concentrating_uuid:
            return
        caster = Entity.get(self.source_entity_uuid)
        if not caster or "Concentrating" not in caster.active_conditions:
            return
        conc = caster.active_conditions["Concentrating"]
        if not isinstance(conc, Concentrating) or conc.uuid != self.cast_concentrating_uuid:
            return
        conc.cleanup_if_no_effects(parent_event=completion_event)
        if "Concentrating" in caster.active_conditions:
            empty_slot_uuids = [slot_uuid for slot_uuid, slot in conc.concentration_slots.items() if not slot.linked_entries]
            for slot_uuid in empty_slot_uuids:
                conc.concentration_slots[slot_uuid].remove_from_register()
                del conc.concentration_slots[slot_uuid]
            if empty_slot_uuids:
                conc._sync_spell_name()

    def _get_aoe_radius_ft(self) -> Optional[int]:
        """Extract AoE size in feet from aoe_shape for VFX metadata."""
        shape = self.aoe_shape
        if shape is None:
            return None
        if isinstance(shape, (Sphere, Cylinder)):
            return shape.radius_feet
        if isinstance(shape, Cone):
            return shape.length_feet
        if isinstance(shape, Line):
            return shape.length_feet
        if isinstance(shape, Cube):
            return shape.size_feet
        return None

    def _get_range_type(self) -> Optional[str]:
        """Map spell range type to VFX delivery string."""
        rt = self.spell_range.type
        if rt == RangeType.SELF:
            return "self"
        if rt == RangeType.REACH:
            return "touch"
        if rt == RangeType.RANGE:
            return "ranged"
        return None

    def generate_variants(self, entity: Entity) -> List['SpellAction']:
        """Generate spell variants for available spell slots.

        Cantrips return a single slotless variant. Leveled spells return one
        variant for each currently available spell slot at or above the base
        spell level.

        Args:
            entity: The entity that would cast the spell

        Returns:
            List of SpellAction variants with appropriate costs
        """
        variants: List['SpellAction'] = []

        if self.spell_level == 0:
            variants.append(self._create_variant(cast_at_level=0))
        else:
            for slot_level in range(self.spell_level, 10):
                if entity.has_spell_slot(slot_level):
                    variants.append(self._create_variant(cast_at_level=slot_level))

        return variants

    def get_discovery_variants(self, entity: Any) -> List[BaseAction]:
        """Return spell forms that should appear in action discovery.

        Args:
            entity: Entity requesting available actions.

        Returns:
            The registered cantrip or slotless override template, or generated
            slot-level variants for leveled spells.
        """
        if self.spell_level == 0 or self.alt_skip_slot:
            return [self]
        return list(self.generate_variants(entity))

    def get_discovery_template_name(self) -> str:
        """Return a stable execution name for this spell discovery row."""
        base_name = self.name or "Unknown"
        if self.is_variant and self.spell_level > 0:
            return f"{base_name}{SPELL_SLOT_TEMPLATE_SEPARATOR}{self.cast_at_level}"
        return base_name

    def get_discovery_display_name(self) -> str:
        """Return a human-facing label for this spell discovery row."""
        base_name = self.name or "Unknown"
        if self.is_variant and self.spell_level > 0:
            return f"{base_name} (Level {self.cast_at_level})"
        return base_name

    def _create_variant(self, cast_at_level: int, **overrides) -> 'SpellAction':
        """Clone self with modified cast level and appropriate costs.

        Uses model_copy() to preserve object types (e.g., AoE shape subclasses).

        Args:
            cast_at_level: The spell slot level to use (0 for cantrips)
            **overrides: Additional field overrides

        Returns:
            A new SpellAction instance configured for this cast level
        """
        update_dict: dict = {
            "uuid": uuid4(),
            "cast_at_level": cast_at_level,
            "is_variant": True,
            "template": False,
            "use_register": False,
            "costs": self._get_costs_for_level(cast_at_level),
        }
        update_dict.update(overrides)

        return self.model_copy(deep=True, update=update_dict)

    def _get_costs_for_level(self, level: int) -> List[Cost]:
        """Get costs for casting at a specific level.

        Preserves the spell's actual action cost type (action vs bonus_action).
        Respects alt overrides (alt_cost_type, alt_skip_slot, alt_extra_costs).

        Args:
            level: The spell slot level (0 for cantrips)

        Returns:
            List of Cost objects (action/bonus_action + spell slot if level > 0)
        """
        base_cost = self.costs[0] if self.costs else Cost(
            name="Cast Spell", cost_type="actions", cost=1,
            evaluator=entity_action_economy_cost_evaluator
        )
        cost = base_cost.model_copy()
        if self.alt_cost_type is not None and cost.cost_type == "actions":
            cost = cost.model_copy(update={"cost_type": self.alt_cost_type})
        costs = [cost]
        if level > 0 and not self.alt_skip_slot:
            slot_cost_type = spell_slot_cost_type(level)
            costs.append(Cost(name=f"Spell Slot L{level}", cost_type=slot_cost_type, cost=1, evaluator=entity_action_economy_cost_evaluator))
        costs.extend(self.alt_extra_costs)
        return costs

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the declaration event for this spell."""
        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        source_name = source_entity.name if source_entity else None
        target_name = target_entity.name if target_entity else None

        return SpellEvent(
            name=f"{self.name}",
            spell_id=normalize_spell_id(self.name or ""),
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.effective_costs],
            use_register=use_register,
            source_entity_name=source_name,
            target_entity_name=target_name,
            spell_level=self.spell_level,
            cast_at_level=self.cast_at_level,
            spell_school=self.spell_school,
            verbal=self.verbal,
            aoe_position=self.end_position if self.effective_target_type == TargetType.POSITION_AOE else None,
            aoe_shape_type=self.aoe_shape.name.lower() if self.aoe_shape and self.aoe_shape.name else None,
            aoe_radius_ft=self._get_aoe_radius_ft(),
            range_type=self._get_range_type(),
            range_ft=self.spell_range.normal,
            projectile_type=self.projectile_type,
            damage_types=[self.spell_damage_type] if self.spell_damage_type else [],
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


class PickUp(BaseAction):
    """Pick up an item from the ground. Free action (no cost).

    Uses target_entity_uuid to hold the item UUID (items are BaseBlocks
    registered in _registry, so BaseBlock.get(uuid) finds them).
    """
    name: str = Field(default="Pick Up", description="Action name for ground-item pickup.")
    description: str = Field(
        default="Pick up an item from the ground",
        description="Action description shown for ground-item pickup.",
    )
    target_type: TargetType = Field(
        default=TargetType.OBJECT,
        description="PickUp targets a floor object.",
    )
    costs: List[Cost] = Field(
        default_factory=list,
        description="No-cost action-economy payload for pickup.",
    )

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

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
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
    name: str = Field(default="Attack Object", description="Action name for attacking an object.")
    description: str = Field(
        default="Attack a breakable object",
        description="Action description shown for object attacks.",
    )
    target_type: TargetType = Field(
        default=TargetType.OBJECT,
        description="AttackObject targets a floor object.",
    )
    action_category: ActionCategory = Field(
        default=ActionCategory.ATTACK,
        description="Classifies object attacks as attack actions.",
    )
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Attack Object Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action cost for attacking a breakable object.")

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

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        item = BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not entity or not isinstance(item, BaseItem):
            return execution_event.cancel(status_message="Entity or item not found")

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

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        """Apply Attack Object action costs after successful object damage."""
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class Drop(BaseAction):
    """Drop an item from inventory onto the ground at a position.

    Position-target action (POSITION_LOS) bound to a specific item.
    Valid positions: entity's own cell + adjacent cells (range 5ft).

    The item_uuid is bound at creation time (one Drop per item).
    """
    name: str = Field(default="Drop", description="Action name for dropping an inventory item.")
    description: str = Field(
        default="Drop an item from inventory",
        description="Action description shown for inventory item drops.",
    )
    target_type: TargetType = Field(
        default=TargetType.POSITION_LOS,
        description="Drop targets a visible position.",
    )
    costs: List[Cost] = Field(
        default_factory=list,
        description="No-cost action-economy payload for item drops.",
    )
    item_uuid: Optional[UUID] = Field(default=None, description="UUID of the item to drop (bound at creation)")

    def get_range(self) -> Optional[Range]:
        return Range(type=RangeType.REACH, normal=5)

    def get_valid_positions(self) -> List[Tuple[int, int]]:
        """Return own and visible adjacent positions within 5 feet."""
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return []
        valid: List[Tuple[int, int]] = [entity.position]
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

        dx = abs(self.end_position[0] - entity.position[0])
        dy = abs(self.end_position[1] - entity.position[1])
        if dx > 1 or dy > 1:
            return declaration_event.cancel(status_message="Drop position too far (max 5ft)")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message="Validated Drop"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
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
