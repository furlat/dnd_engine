"""Reaction fixtures for action setup and passive movement responses.

These engine extensions are not SRD rules. They exercise two reaction patterns:
Prepare Intercept spends an action and movement to arm a one-round handler, and
Dodge Roll installs a persistent handler that retreats from an incoming attack.
Both validate path walkability when the reaction fires, so current grid state is
authoritative after terrain or door changes.
"""

from typing import List, Optional, Tuple
from uuid import UUID
from pydantic import Field

from dnd.core.base_actions import (
    BaseAction,
    ActionCategory,
    ActionEvent,
    BaseCost,
    TargetType,
    Cost,
)
from dnd.core.base_conditions import BaseCondition, DurationType
from dnd.core.events import (
    Event,
    EventPhase,
    EventType,
    EventHandler,
    Trigger,
    WeaponSlot,
    StepMovementEvent,
)
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.actions import (
    Attack,
    AttackEvent,
    entity_action_economy_cost_evaluator,
    entity_action_economy_cost_applier,
)


def create_intercept_processor(charge_destination: Tuple[int, int]):
    """Create a step-movement processor for a prepared intercept.

    Args:
        charge_destination: Grid cell the interceptor attempts to occupy before
            the mover enters it.

    Returns:
        Event processor that may cancel the triggering step movement.
    """

    def intercept_processor(
        event: StepMovementEvent,
        source_entity_uuid: UUID,
    ) -> Optional[StepMovementEvent]:
        """Resolve an intercept reaction against a single step movement event.

        Args:
            event: Step movement event currently being processed.
            source_entity_uuid: Entity UUID that owns the prepared handler.

        Returns:
            The original event, or a canceled copy when the intercept blocks the
            destination cell.
        """
        interceptor = Entity.get(source_entity_uuid)
        mover = Entity.get(event.source_entity_uuid)
        if not interceptor or not mover:
            return event

        if interceptor.uuid == mover.uuid or interceptor.is_ally(mover):
            return event

        if interceptor.position == charge_destination:
            return event

        if event.to_position != charge_destination:
            return event

        if not interceptor.action_economy.can_afford("reactions", 1):
            return event

        weapon = interceptor.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)
        if weapon is None:
            return event

        cdx = charge_destination[0] - interceptor.position[0]
        cdy = charge_destination[1] - interceptor.position[1]
        if cdx != 0:
            cdx = 1 if cdx > 0 else -1
        if cdy != 0:
            cdy = 1 if cdy > 0 else -1

        grid = get_map()
        current_pos = interceptor.position
        for _ in range(5):
            if current_pos == charge_destination:
                break
            next_pos = (current_pos[0] + cdx, current_pos[1] + cdy)
            if not grid.can_transition(current_pos, next_pos, interceptor.uuid):
                break
            Entity.update_entity_position(interceptor, next_pos, parent_event=event.uuid)
            current_pos = next_pos

        interceptor.update_entity_senses()

        dist_after = interceptor.senses.get_feet_distance(event.from_position)
        if dist_after <= 5:
            reaction_attack = Attack(
                name="Intercept Attack",
                source_entity_uuid=source_entity_uuid,
                target_entity_uuid=event.source_entity_uuid,
                weapon_slot=WeaponSlot.MELEE_MAIN,
                parent_event=event,
                use_register=False,
                costs=[
                    Cost(
                        name="Intercept Attack Cost",
                        cost_type="reactions",
                        cost=1,
                        evaluator=entity_action_economy_cost_evaluator,
                    )
                ],
            )
            if reaction_attack.pre_validate():
                reaction_attack.add_to_register()
                reaction_attack.apply(parent_event=event)
        else:
            interceptor.action_economy.consume("reactions", 1)

        if "Intercepting" in interceptor.active_conditions:
            interceptor.remove_condition("Intercepting")

        if interceptor.position == charge_destination:
            return event.cancel(status_message="Intercepted: path blocked")
        return event

    return intercept_processor


def create_intercept_handler(source_entity_uuid: UUID, charge_destination: Tuple[int, int]) -> EventHandler:
    """Create a handler that reacts to step movement entering the prepared cell.

    Args:
        source_entity_uuid: Entity UUID that owns the handler.
        charge_destination: Grid cell that triggers the intercept attempt.

    Returns:
        Toggleable event handler bound to `STEP_MOVEMENT` effect events.
    """
    return EventHandler(
        name="Intercept",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                name="Intercept Trigger",
                event_type=EventType.STEP_MOVEMENT,
                event_phase=EventPhase.EFFECT,
            )
        ],
        event_processor=create_intercept_processor(charge_destination),
        player_toggleable=True,
    )


class Intercepting(BaseCondition):
    """Prepared to intercept approaching enemies at a declared charge destination.

    Attributes:
        name: Condition registry key.
        description: Short player-facing summary.
        charge_destination: Grid cell the owner attempts to occupy when the
            handler fires.
    """
    name: str = Field(
        default="Intercepting",
        description="Condition registry key for a prepared intercept.",
    )
    description: str = Field(
        default="Ready to charge and attack approaching enemies",
        description="Player-facing summary for the prepared intercept condition.",
    )
    charge_destination: Tuple[int, int] = Field(
        description="Grid cell the owner attempts to occupy when the intercept fires.",
    )

    def _apply(
        self,
        declaration_event: Event,
    ) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Install the intercept movement handler.

        Args:
            declaration_event: Condition application event in progress.

        Returns:
            Condition application bookkeeping and the effect event.
        """
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID is not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found",
            )

        handler = create_intercept_handler(target.uuid, self.charge_destination)
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Intercepting to {target.name} (destination: {self.charge_destination})",
        )
        return [], [handler.uuid], [], [], effect_event


class PrepareIntercept(BaseAction):
    """Prepare to intercept enemies near a declared position.

    Attributes:
        name: Action discovery and combat-log label.
        description: Short player-facing summary.
        target_type: Position targeting mode used by discovery.
        action_category: Broad action classification.
        costs: Action economy costs paid by the preparatory action.
    """
    name: str = Field(
        default="Prepare Intercept",
        description="Action discovery and combat-log label.",
    )
    description: str = Field(
        default="Declare a charge destination to intercept approaching enemies",
        description="Player-facing summary for preparing an intercept.",
    )
    target_type: TargetType = Field(
        default=TargetType.POSITION_LOS,
        description="Position targeting mode used to choose the charge destination.",
    )
    action_category: ActionCategory = Field(
        default=ActionCategory.ABILITY,
        description="Broad action classification for discovery and UI layers.",
    )
    costs: List[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Intercept Action Cost",
                cost_type="actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            )
        ],
        description="Action economy costs paid when preparing an intercept.",
    )

    def _create_declaration_event(
        self,
        parent_event: Optional[Event] = None,
        use_register: bool = True,
    ) -> Optional[ActionEvent]:
        """Build the action declaration event for the preparation step.

        Args:
            parent_event: Optional parent event for event-tree nesting.
            use_register: Whether the declaration should register with the
                event queue.

        Returns:
            Declaration event targeting the preparing entity.
        """
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Prepare Intercept",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.costs],
            use_register=use_register,
            source_entity_name=source_name,
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        """Validate the requested charge destination and prepaid movement.

        Args:
            declaration_event: Declaration event to advance or cancel.

        Returns:
            Execution event when the declared line is legal, otherwise a
            canceled declaration event.
        """
        entity = Entity.get(self.source_entity_uuid)
        if not entity or not self.end_position:
            return declaration_event.cancel(status_message="Entity not found or no target position")

        dx = self.end_position[0] - entity.position[0]
        dy = self.end_position[1] - entity.position[1]
        if dx != 0 and dy != 0 and abs(dx) != abs(dy):
            return declaration_event.cancel(status_message="Must be a straight line")
        distance_cells = max(abs(dx), abs(dy))
        if distance_cells > 5 or distance_cells == 0:
            return declaration_event.cancel(status_message="Must be 1-5 cells away")

        grid = get_map()
        step_dx = (1 if dx > 0 else -1) if dx != 0 else 0
        step_dy = (1 if dy > 0 else -1) if dy != 0 else 0
        current = entity.position
        for _ in range(distance_cells):
            next_pos = (current[0] + step_dx, current[1] + step_dy)
            if not grid.can_transition(current, next_pos, entity.uuid):
                return declaration_event.cancel(status_message=f"Path blocked at {next_pos}")
            current = next_pos

        distance_feet = distance_cells * 5
        remaining = entity.action_economy.movement.normalized_score
        if remaining < distance_feet:
            return declaration_event.cancel(status_message=f"Not enough movement ({remaining}/{distance_feet}ft)")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}",
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        """Apply movement prepayment and install the one-round condition.

        Args:
            execution_event: Validated execution event.

        Returns:
            Completion event when the condition is installed, otherwise a
            canceled event.
        """
        entity = Entity.get(self.source_entity_uuid)
        if not entity or not self.end_position:
            return execution_event.cancel(status_message="Entity not found")

        distance_cells = max(
            abs(self.end_position[0] - entity.position[0]),
            abs(self.end_position[1] - entity.position[1]),
        )
        entity.action_economy.consume("movement", distance_cells * 5)

        intercepting = Intercepting(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            charge_destination=self.end_position,
        )
        intercepting.duration.duration_type = DurationType.ROUNDS
        intercepting.duration.duration = 1

        entity.add_condition(intercepting, parent_event=execution_event)

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Prepared Intercept at {self.end_position}",
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        """Spend the action cost after successful completion.

        Args:
            completion_event: Completed action event.

        Returns:
            Completion event after action-economy cost application.
        """
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


def dodge_roll_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """Move a defender away from an incoming attack and impose disadvantage.

    Args:
        event: Event currently being processed.
        source_entity_uuid: Defender UUID that owns the dodge-roll handler.

    Returns:
        The original event after any movement and attack-bonus mutation.
    """
    defender = Entity.get(source_entity_uuid)
    attacker = Entity.get(event.source_entity_uuid)
    if not defender or not attacker:
        return event

    if event.target_entity_uuid != source_entity_uuid:
        return event

    if not defender.action_economy.can_afford("reactions", 1):
        return event

    dx = defender.position[0] - attacker.position[0]
    dy = defender.position[1] - attacker.position[1]
    if dx != 0:
        dx = 1 if dx > 0 else -1
    if dy != 0:
        dy = 1 if dy > 0 else -1

    if dx == 0 and dy == 0:
        return event

    grid = get_map()
    moved_cells = 0
    current_pos = defender.position

    for _ in range(2):
        next_pos = (current_pos[0] + dx, current_pos[1] + dy)
        if not grid.can_transition(current_pos, next_pos, defender.uuid):
            break
        Entity.update_entity_position(defender, next_pos, parent_event=event.uuid)
        current_pos = next_pos
        moved_cells += 1

    if moved_cells > 0:
        if isinstance(event, AttackEvent) and event.attack_bonus is not None:
            attack_bonus = event.attack_bonus
            attack_bonus.self_static.add_advantage_modifier(
                AdvantageModifier(
                    name="Dodge Roll",
                    value=AdvantageStatus.DISADVANTAGE,
                    source_entity_uuid=defender.uuid,
                    target_entity_uuid=event.source_entity_uuid,
                )
            )
        defender.action_economy.consume("reactions", 1)

    return event


def create_dodge_roll_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create a handler that reacts to incoming attack execution events.

    Args:
        source_entity_uuid: Defender UUID that owns the dodge-roll handler.

    Returns:
        Toggleable event handler bound to attack execution events.
    """
    return EventHandler(
        name="Dodge Roll",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                name="Dodge Roll Trigger",
                event_type=EventType.ATTACK,
                event_phase=EventPhase.EXECUTION,
            )
        ],
        event_processor=dodge_roll_processor,
        player_toggleable=True,
    )


class DodgeRollFeature(BaseCondition):
    """Passive: can dodge roll when attacked, moving away and imposing disadvantage.

    Attributes:
        name: Condition registry key.
        description: Short player-facing summary.
    """
    name: str = Field(
        default="Dodge Roll",
        description="Condition registry key for the dodge-roll feature.",
    )
    description: str = Field(
        default="Reaction: roll away when attacked, imposing disadvantage",
        description="Player-facing summary for the dodge-roll feature.",
    )

    def _apply(
        self,
        declaration_event: Event,
    ) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Install the dodge-roll attack handler.

        Args:
            declaration_event: Condition application event in progress.

        Returns:
            Condition application bookkeeping and the effect event.
        """
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID is not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found",
            )

        handler = create_dodge_roll_handler(target.uuid)
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Dodge Roll feature to {target.name}",
        )
        return [], [handler.uuid], [], [], effect_event
