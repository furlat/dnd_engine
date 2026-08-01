"""Dependency-neutral action meaning and restricted-budget types.

These values describe stable engine meaning carried by cold event facts. The
module intentionally imports no other project package so actions, items,
servers, and replay tooling can depend on it without reversing ownership.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID


class ActionPresentationKind(str, Enum):
    """Stable presentation semantics for an action event."""

    DEFAULT = "default"
    DRINK = "drink"


class RestrictedActionKind(str, Enum):
    """Rule-level action families that a restricted budget may authorize."""

    STANDARD_ACTION = "standard_action"
    WEAPON_ATTACK = "weapon_attack"
    DASH = "dash"
    DISENGAGE = "disengage"
    HIDE = "hide"


class ActionEconomyCostType(str, Enum):
    """Action-economy channels that a restricted grant may replace."""

    ACTIONS = "actions"
    BONUS_ACTIONS = "bonus_actions"
    REACTIONS = "reactions"
    MOVEMENT = "movement"


class HasteActionPolicy(str, Enum):
    """Which action families may spend Haste's independent turn budget."""

    BG3_HONOUR = "bg3_honour"
    SRD_5_1 = "srd_5_1"


CostType = Literal[
    "actions",
    "bonus_actions",
    "reactions",
    "movement",
    "spell_slot_1",
    "spell_slot_2",
    "spell_slot_3",
    "spell_slot_4",
    "spell_slot_5",
    "spell_slot_6",
    "spell_slot_7",
    "spell_slot_8",
    "spell_slot_9",
]

SPELL_SLOT_COST_TYPES: dict[int, CostType] = {
    1: "spell_slot_1",
    2: "spell_slot_2",
    3: "spell_slot_3",
    4: "spell_slot_4",
    5: "spell_slot_5",
    6: "spell_slot_6",
    7: "spell_slot_7",
    8: "spell_slot_8",
    9: "spell_slot_9",
}


def spell_slot_cost_type(level: int) -> CostType:
    """Convert a spell-slot rank into its action-economy channel."""
    result = SPELL_SLOT_COST_TYPES.get(level)
    if result is None:
        raise ValueError(f"Invalid spell slot level: {level}")
    return result


@dataclass(frozen=True)
class RestrictedActionGrant:
    """One explicitly named, turn-recharging restricted action budget."""

    grant_id: str
    owner_uuid: UUID
    resource_name: str
    display_name: str
    allowed_kinds: frozenset[RestrictedActionKind]
    replaced_cost_types: frozenset[ActionEconomyCostType] = frozenset(
        {ActionEconomyCostType.ACTIONS}
    )
    uses_per_turn: int = 1

    def __post_init__(self) -> None:
        """Reject incomplete grants before they enter runtime state."""
        if not self.grant_id:
            raise ValueError("restricted action grant_id cannot be empty")
        if not self.resource_name:
            raise ValueError("restricted action resource_name cannot be empty")
        if not self.display_name:
            raise ValueError("restricted action display_name cannot be empty")
        if not self.allowed_kinds:
            raise ValueError("restricted action allowed_kinds cannot be empty")
        if not self.replaced_cost_types:
            raise ValueError(
                "restricted action replaced_cost_types cannot be empty"
            )
        if self.uses_per_turn < 1:
            raise ValueError("restricted action uses_per_turn must be positive")


@runtime_checkable
class RestrictedActionGrantProvider(Protocol):
    """Structural owner surface consumed by dependency-neutral actions."""

    def get_restricted_action_grants(
        self,
    ) -> tuple[RestrictedActionGrant, ...]:
        """Return the owner's current restricted action grants."""
        ...


__all__ = [
    "ActionEconomyCostType",
    "ActionPresentationKind",
    "CostType",
    "HasteActionPolicy",
    "RestrictedActionGrant",
    "RestrictedActionGrantProvider",
    "RestrictedActionKind",
    "SPELL_SLOT_COST_TYPES",
    "spell_slot_cost_type",
]
