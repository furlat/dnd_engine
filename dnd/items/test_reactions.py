"""Homebrew reaction definitions for testing the incremental senses / _paths_dirty system.

Contains: Intercept (action-setup reaction) and Dodge Roll (passive reaction).
These are NOT SRD rules — they're proof-of-concept reactions that validate
per-cell walkability checks at reaction time, proving the _paths_dirty pattern works.

Pattern examples, not final game mechanics.
"""

from typing import Optional, List, Tuple
from uuid import UUID
from pydantic import Field

from dnd.core.base_actions import BaseAction, ActionEvent, BaseCost, TargetType, Cost
from dnd.core.base_conditions import BaseCondition, DurationType
from dnd.core.events import (
    Event, EventPhase, EventType,
    EventHandler, Trigger,
    WeaponSlot, StepMovementEvent,
)
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.actions import Attack, AttackEvent, entity_action_economy_cost_evaluator, entity_action_economy_cost_applier


# =============================================================================
# INTERCEPT — Action-Setup Reaction
# =============================================================================
# Pattern: Player spends 1 action + movement to declare a charge destination.
# When an enemy steps INTO that cell, the interceptor charges there first,
# occupying the cell and making a melee attack against the enemy (who is
# still at from_position, one cell away). The step is canceled — the enemy
# stops with remaining movement but can't enter the blocked cell.

def create_intercept_processor(charge_destination: Tuple[int, int]):
    """Create a closure-based processor that knows the declared charge destination."""

    def intercept_processor(event: StepMovementEvent, source_entity_uuid: UUID) -> Optional[StepMovementEvent]:
        interceptor = Entity.get(source_entity_uuid)
        mover = Entity.get(event.source_entity_uuid)
        if not interceptor or not mover:
            return event

        # Don't intercept self or allies
        if interceptor.uuid == mover.uuid or interceptor.is_ally(mover):
            return event

        # Already at destination (e.g., triggered earlier in same movement)
        if interceptor.position == charge_destination:
            return event

        # Trigger: enemy stepping directly INTO the charge destination cell
        if event.to_position != charge_destination:
            return event

        # Check reaction available
        if not interceptor.action_economy.can_afford("reactions", 1):
            return event

        # Check we have a melee weapon
        weapon = interceptor.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)
        if weapon is None:
            return event

        # Charge: straight line from current position toward charge_destination
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
                break  # Arrived
            next_pos = (current_pos[0] + cdx, current_pos[1] + cdy)
            # Per-cell walkability check — reflects environment changes via _paths_dirty system
            if not grid.is_walkable_for(next_pos[0], next_pos[1], interceptor.uuid):
                break  # Path blocked (e.g., door closed between preparation and trigger)
            Entity.update_entity_position(interceptor, next_pos, parent_event=event.uuid)
            current_pos = next_pos

        # Refresh senses after charge so Attack's LOS validation sees the enemy
        interceptor.update_entity_senses()

        # Enemy is at from_position (their current cell). Since a step is exactly
        # 1 cell, from_position is always adjacent to to_position = charge_destination.
        # If interceptor reached charge_destination, distance to from_position is 5ft.
        dist_after = interceptor.senses.get_feet_distance(event.from_position)
        if dist_after <= 5:
            reaction_attack = Attack(
                name="Intercept Attack",
                source_entity_uuid=source_entity_uuid,
                target_entity_uuid=event.source_entity_uuid,
                weapon_slot=WeaponSlot.MELEE_MAIN,
                parent_event=event,
                use_register=False,
                costs=[Cost(
                    name="Intercept Attack Cost",
                    cost_type="reactions",
                    cost=1,
                    evaluator=entity_action_economy_cost_evaluator
                )]
            )
            if reaction_attack.pre_validate():
                reaction_attack.add_to_register()
                reaction_attack.apply(parent_event=event)
        else:
            # Charged but couldn't reach — consume reaction anyway (attempt was made)
            interceptor.action_economy.consume("reactions", 1)

        # Remove Intercepting condition (and its handler) after firing.
        # Charge was attempted — whether it reached the destination or not, intercept is spent.
        if "Intercepting" in interceptor.active_conditions:
            interceptor.remove_condition("Intercepting")

        # If interceptor reached the charge destination, cancel the step so the enemy
        # stays at from_position. The cancel propagates through EventQueue.register() →
        # post() → processed_step.canceled check in Move._apply().
        if interceptor.position == charge_destination:
            return event.cancel(status_message="Intercepted — path blocked")
        return event

    return intercept_processor


def create_intercept_handler(source_entity_uuid: UUID, charge_destination: Tuple[int, int]) -> EventHandler:
    """Create an intercept handler that triggers on STEP_MOVEMENT events."""
    return EventHandler(
        name="Intercept",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[Trigger(
            name="Intercept Trigger",
            event_type=EventType.STEP_MOVEMENT,
            event_phase=EventPhase.EFFECT
        )],
        event_processor=create_intercept_processor(charge_destination),
        player_toggleable=True
    )


class Intercepting(BaseCondition):
    """Prepared to intercept approaching enemies at a declared charge destination.

    Applied by PrepareIntercept action. Costs 1 reaction when triggered.
    1-round duration (expires at start of next turn).
    """
    name: str = "Intercepting"
    description: str = "Ready to charge and attack approaching enemies"
    charge_destination: Tuple[int, int] = Field(description="Declared charge target cell")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID is not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")

        handler = create_intercept_handler(target.uuid, self.charge_destination)
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Intercepting to {target.name} (destination: {self.charge_destination})"
        )
        return [], [handler.uuid], [], [], effect_event


class PrepareIntercept(BaseAction):
    """Prepare to intercept enemies near a declared position.

    Costs 1 action + movement (distance to charge destination in feet).
    Player selects a cell up to 5 cells away in a straight line (cardinal or diagonal).
    All cells on the path must be walkable. Applies Intercepting condition (1 round).
    """
    name: str = Field(default="Prepare Intercept")
    description: str = Field(default="Declare a charge destination to intercept approaching enemies")
    target_type: TargetType = Field(default=TargetType.POSITION_LOS)
    action_category: str = "ability"
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Intercept Action Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ])

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[ActionEvent]:
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
            source_entity_name=source_name
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity or not self.end_position:
            return declaration_event.cancel(status_message="Entity not found or no target position")

        # Validate: straight line, max 5 cells
        dx = self.end_position[0] - entity.position[0]
        dy = self.end_position[1] - entity.position[1]
        # Must be a straight line (cardinal or diagonal)
        if dx != 0 and dy != 0 and abs(dx) != abs(dy):
            return declaration_event.cancel(status_message="Must be a straight line")
        distance_cells = max(abs(dx), abs(dy))
        if distance_cells > 5 or distance_cells == 0:
            return declaration_event.cancel(status_message="Must be 1-5 cells away")

        # Check all cells in the line are walkable
        grid = get_map()
        step_dx = (1 if dx > 0 else -1) if dx != 0 else 0
        step_dy = (1 if dy > 0 else -1) if dy != 0 else 0
        current = entity.position
        for _ in range(distance_cells):
            next_pos = (current[0] + step_dx, current[1] + step_dy)
            if not grid.is_walkable_for(next_pos[0], next_pos[1], entity.uuid):
                return declaration_event.cancel(status_message=f"Path blocked at {next_pos}")
            current = next_pos

        # Check enough movement
        distance_feet = distance_cells * 5
        remaining = entity.action_economy.movement.normalized_score
        if remaining < distance_feet:
            return declaration_event.cancel(status_message=f"Not enough movement ({remaining}/{distance_feet}ft)")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity or not self.end_position:
            return execution_event.cancel(status_message="Entity not found")

        # Consume movement cost (pre-pay the charge distance)
        distance_cells = max(
            abs(self.end_position[0] - entity.position[0]),
            abs(self.end_position[1] - entity.position[1])
        )
        entity.action_economy.consume("movement", distance_cells * 5)

        # Apply Intercepting condition with the declared destination
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
            status_message=f"Prepared Intercept at {self.end_position}"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


# =============================================================================
# DODGE ROLL — Passive Reaction
# =============================================================================
# Pattern: Permanent condition applied via entity setup. When attacked,
# moves up to 2 cells away from attacker and imposes disadvantage.

def dodge_roll_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """When attacked, move up to 2 cells away from attacker and impose disadvantage."""
    defender = Entity.get(source_entity_uuid)
    attacker = Entity.get(event.source_entity_uuid)
    if not defender or not attacker:
        return event

    # Only when WE are the target
    if event.target_entity_uuid != source_entity_uuid:
        return event

    # Check reaction available
    if not defender.action_economy.can_afford("reactions", 1):
        return event

    # Calculate flee direction (away from attacker)
    dx = defender.position[0] - attacker.position[0]
    dy = defender.position[1] - attacker.position[1]
    if dx != 0:
        dx = 1 if dx > 0 else -1
    if dy != 0:
        dy = 1 if dy > 0 else -1

    # Edge case: attacker and defender on same position
    if dx == 0 and dy == 0:
        return event

    grid = get_map()
    moved_cells = 0
    current_pos = defender.position

    # Straight-line retreat — if blocked, dodge stops
    for _ in range(2):
        next_pos = (current_pos[0] + dx, current_pos[1] + dy)
        # Per-cell walkability check — reflects environment changes
        if not grid.is_walkable_for(next_pos[0], next_pos[1], defender.uuid):
            break  # Blocked
        Entity.update_entity_position(defender, next_pos, parent_event=event.uuid)
        current_pos = next_pos
        moved_cells += 1

    if moved_cells > 0:
        # Impose disadvantage on the attack
        if isinstance(event, AttackEvent) and event.attack_bonus is not None:
            attack_bonus = event.attack_bonus
            attack_bonus.self_static.add_advantage_modifier(
                AdvantageModifier(
                    name="Dodge Roll",
                    value=AdvantageStatus.DISADVANTAGE,
                    source_entity_uuid=defender.uuid,
                    target_entity_uuid=event.source_entity_uuid
                )
            )
        # Consume reaction
        defender.action_economy.consume("reactions", 1)

    return event


def create_dodge_roll_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create a dodge roll handler that triggers on ATTACK events."""
    return EventHandler(
        name="Dodge Roll",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[Trigger(
            name="Dodge Roll Trigger",
            event_type=EventType.ATTACK,
            event_phase=EventPhase.EXECUTION
        )],
        event_processor=dodge_roll_processor,
        player_toggleable=True
    )


class DodgeRollFeature(BaseCondition):
    """Passive: can dodge roll when attacked, moving away and imposing disadvantage.

    Permanent duration. Applied via entity setup or item equip.
    """
    name: str = "Dodge Roll"
    description: str = "Reaction: roll away when attacked, imposing disadvantage"

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID is not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")

        handler = create_dodge_roll_handler(target.uuid)
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Dodge Roll feature to {target.name}"
        )
        return [], [handler.uuid], [], [], effect_event
