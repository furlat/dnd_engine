"""Composite tactical actions with refresh and interruption checks."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from ai.interface import GameInterface
from ai.models import ActionResult, TacticalState


class InterruptType(Enum):
    """Board-state changes that can interrupt a composite tactic."""

    NEW_ENEMY = "new_enemy"
    DAMAGE_TAKEN = "damage_taken"
    TARGET_DIED = "target_died"
    CONDITION_GAINED = "condition"


class InterruptPolicy(Enum):
    """Composite response to a detected interruption."""

    ABORT = "abort"
    CONTINUE = "continue"


def detect_interrupts(
    before: TacticalState,
    result: ActionResult,
    after: TacticalState,
) -> List[InterruptType]:
    """Detect tactical changes between two snapshots.

    Args:
        before: Tactical snapshot before an action executes.
        result: Action execution result.
        after: Tactical snapshot after the action resolves.

    Returns:
        Interrupt types observed between the snapshots.
    """
    interrupts: List[InterruptType] = []

    if result.entity_hp is not None and before.me.hp > result.entity_hp:
        interrupts.append(InterruptType.DAMAGE_TAKEN)

    if result.deaths:
        interrupts.append(InterruptType.TARGET_DIED)

    before_uuids = {enemy.uuid for enemy in before.enemies}
    after_uuids = {enemy.uuid for enemy in after.enemies}
    if after_uuids - before_uuids:
        interrupts.append(InterruptType.NEW_ENEMY)

    before_conditions = set(before.me.conditions)
    after_conditions = set(after.me.conditions)
    if after_conditions - before_conditions:
        interrupts.append(InterruptType.CONDITION_GAINED)

    return interrupts


class CompositeResult(BaseModel):
    """Result returned by a multi-step tactical composite."""

    success: bool = Field(description="Whether the composite completed successfully.")
    actions_taken: int = Field(
        default=0,
        description="Number of interface executions performed by the composite.",
    )
    interrupted_by: Optional[str] = Field(
        default=None,
        description="Interrupt value that stopped the composite, if any.",
    )
    description: str = Field(
        default="",
        description="Human-readable summary of the composite outcome.",
    )


class CompositeAction(ABC):
    """Base class for tactics that execute more than one engine action."""

    interrupt_policies: Dict[InterruptType, InterruptPolicy] = {}

    @abstractmethod
    def execute(
        self,
        iface: GameInterface,
        state: TacticalState,
        entity_uuid: str,
    ) -> CompositeResult:
        """Execute this composite from an initial tactical state.

        Args:
            iface: Game interface used to execute selected action rows.
            state: Initial tactical snapshot.
            entity_uuid: Controlled actor UUID serialized as text.

        Returns:
            Composite execution result.
        """
        raise NotImplementedError

    def _should_abort(
        self,
        before: TacticalState,
        result: ActionResult,
        after: TacticalState,
    ) -> Optional[InterruptType]:
        """Return the first detected interrupt configured to abort."""
        for interrupt in detect_interrupts(before, result, after):
            if self.interrupt_policies.get(interrupt) == InterruptPolicy.ABORT:
                return interrupt
        return None


class MoveAndAttack(CompositeAction):
    """Move adjacent to a target, refresh state, then attack."""

    interrupt_policies = {
        InterruptType.DAMAGE_TAKEN: InterruptPolicy.ABORT,
        InterruptType.TARGET_DIED: InterruptPolicy.ABORT,
        InterruptType.NEW_ENEMY: InterruptPolicy.CONTINUE,
        InterruptType.CONDITION_GAINED: InterruptPolicy.ABORT,
    }

    def __init__(self, target_uuid: str):
        self.target_uuid = target_uuid

    def execute(
        self,
        iface: GameInterface,
        state: TacticalState,
        entity_uuid: str,
    ) -> CompositeResult:
        """Execute the move-and-attack tactic."""
        attack = state.find_attack_targeting(self.target_uuid)
        if attack:
            result = iface.execute(entity_uuid, attack[0].template_name, attack[1].index)
            return CompositeResult(
                success=result.success,
                actions_taken=1,
                description="Attacked (already in range)",
            )

        move = state.find_move_adjacent_to(self.target_uuid)
        if not move:
            return CompositeResult(
                success=False,
                actions_taken=0,
                description="No path to target",
            )

        before = state
        move_result = iface.execute(entity_uuid, move[0].template_name, move[1].index)
        after = iface.get_tactical_state(entity_uuid)

        interrupt = self._should_abort(before, move_result, after)
        if interrupt:
            return CompositeResult(
                success=False,
                actions_taken=1,
                interrupted_by=interrupt.value,
                description=f"Move interrupted: {interrupt.value}",
            )

        attack = after.find_attack_targeting(self.target_uuid)
        if attack:
            result = iface.execute(entity_uuid, attack[0].template_name, attack[1].index)
            return CompositeResult(
                success=result.success,
                actions_taken=2,
                description="Moved and attacked",
            )

        return CompositeResult(
            success=False,
            actions_taken=1,
            description="Moved but can't reach target",
        )


class Retreat(CompositeAction):
    """Disengage when threatened, then move away from the nearest enemy."""

    interrupt_policies = {
        InterruptType.DAMAGE_TAKEN: InterruptPolicy.ABORT,
        InterruptType.CONDITION_GAINED: InterruptPolicy.ABORT,
    }

    def execute(
        self,
        iface: GameInterface,
        state: TacticalState,
        entity_uuid: str,
    ) -> CompositeResult:
        """Execute the retreat tactic."""
        actions_taken = 0

        if state.is_threatened:
            disengage = state.find_self_action("Disengage")
            if disengage and disengage.can_afford:
                iface.execute(entity_uuid, disengage.template_name, 0)
                actions_taken += 1
                state = iface.get_tactical_state(entity_uuid)

        nearest = state.nearest_enemy()
        if not nearest:
            return CompositeResult(
                success=False,
                actions_taken=actions_taken,
                description="No enemies to retreat from",
            )

        move = state.find_move_away_from(nearest.position)
        if not move:
            return CompositeResult(
                success=False,
                actions_taken=actions_taken,
                description="No retreat path available",
            )

        before = state
        move_result = iface.execute(entity_uuid, move[0].template_name, move[1].index)
        after = iface.get_tactical_state(entity_uuid)
        actions_taken += 1

        interrupt = self._should_abort(before, move_result, after)
        if interrupt:
            return CompositeResult(
                success=False,
                actions_taken=actions_taken,
                interrupted_by=interrupt.value,
                description=f"Retreat interrupted: {interrupt.value}",
            )

        return CompositeResult(
            success=True,
            actions_taken=actions_taken,
            description="Retreated from enemies",
        )


class FocusFire(CompositeAction):
    """Attack a selected target until no matching attack row remains."""

    interrupt_policies = {
        InterruptType.TARGET_DIED: InterruptPolicy.ABORT,
        InterruptType.CONDITION_GAINED: InterruptPolicy.ABORT,
    }

    def __init__(self, target_uuid: str):
        self.target_uuid = target_uuid

    def execute(
        self,
        iface: GameInterface,
        state: TacticalState,
        entity_uuid: str,
    ) -> CompositeResult:
        """Execute repeated attacks against the selected target."""
        actions_taken = 0

        while True:
            state = iface.get_tactical_state(entity_uuid)
            attack = state.find_attack_targeting(self.target_uuid)
            if not attack:
                break

            before = state
            result = iface.execute(entity_uuid, attack[0].template_name, attack[1].index)
            actions_taken += 1
            after = iface.get_tactical_state(entity_uuid)

            interrupt = self._should_abort(before, result, after)
            if interrupt:
                return CompositeResult(
                    success=actions_taken > 0,
                    actions_taken=actions_taken,
                    interrupted_by=interrupt.value,
                    description=f"Focus fire interrupted: {interrupt.value}",
                )

        description = (
            f"Focus fired {actions_taken} attacks"
            if actions_taken > 0
            else "No attacks available"
        )
        return CompositeResult(
            success=actions_taken > 0,
            actions_taken=actions_taken,
            description=description,
        )


class DashToward(CompositeAction):
    """Dash when possible, then move toward a selected target."""

    interrupt_policies = {
        InterruptType.DAMAGE_TAKEN: InterruptPolicy.ABORT,
        InterruptType.CONDITION_GAINED: InterruptPolicy.ABORT,
    }

    def __init__(self, target_uuid: str):
        self.target_uuid = target_uuid

    def execute(
        self,
        iface: GameInterface,
        state: TacticalState,
        entity_uuid: str,
    ) -> CompositeResult:
        """Execute the dash-and-move tactic."""
        actions_taken = 0

        dash = state.find_self_action("Dash")
        if dash and dash.can_afford:
            iface.execute(entity_uuid, dash.template_name, 0)
            actions_taken += 1
            state = iface.get_tactical_state(entity_uuid)

        move = state.find_move_toward(self.target_uuid)
        if not move:
            return CompositeResult(
                success=actions_taken > 0,
                actions_taken=actions_taken,
                description="No path toward target",
            )

        before = state
        move_result = iface.execute(entity_uuid, move[0].template_name, move[1].index)
        after = iface.get_tactical_state(entity_uuid)
        actions_taken += 1

        interrupt = self._should_abort(before, move_result, after)
        if interrupt:
            return CompositeResult(
                success=True,
                actions_taken=actions_taken,
                interrupted_by=interrupt.value,
                description=f"Dash interrupted: {interrupt.value}",
            )

        return CompositeResult(
            success=True,
            actions_taken=actions_taken,
            description="Dashed toward target",
        )
