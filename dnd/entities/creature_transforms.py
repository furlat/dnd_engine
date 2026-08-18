"""Reusable transforms over an entity-shaped set of creature capabilities.

This module deliberately does not import :mod:`dnd.entities.entity`.  Both the entity
aggregate and concrete rules objects may depend on these functions without
creating an upward dependency or a circular import.  Every transform returns
the ordinary ``(modifiable_value_uuid, modifier_uuid)`` ownership rows used
for exact, source-owned cleanup.
"""

from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol, runtime_checkable
from uuid import UUID

from dnd.blocks.action_economy import ActionEconomy
from dnd.blocks.equipment import (
    Equipment,
)
from dnd.blocks.saving_throws import SavingThrowSet
from dnd.blocks.sensory import Senses
from dnd.core.base_block import BaseBlock
from dnd.types.creatures import Size
from dnd.types.life import LifeState
from dnd.core.modifiers import (
    AdvantageModifier,
    AutoHitModifier,
    ContextualAdvantageModifier,
    ContextualCriticalModifier,
    CriticalModifier,
    NumericalModifier,
)
from dnd.types.rolls import AdvantageStatus, AutoHitStatus, CriticalStatus
from dnd.types.abilities import AbilityName
from dnd.core.values import ModifiableValue


ModifierOwnership = list[tuple[UUID, UUID]]


@dataclass(frozen=True, slots=True)
class EntityTransformReceipt:
    """One exact inverse returned after an entity transform succeeds."""

    transform_id: str
    undo: Callable[[], None]


@dataclass(frozen=True, slots=True)
class EntityTransform:
    """One named, reversible entity-to-entity operation."""

    transform_id: str
    apply_operation: Callable[["CreatureTransformTarget"], Callable[[], None]]

    def apply(self, target: "CreatureTransformTarget") -> EntityTransformReceipt:
        """Apply the operation and retain its exact inverse."""
        if not self.transform_id:
            raise ValueError("entity transform_id cannot be empty")
        return EntityTransformReceipt(
            transform_id=self.transform_id,
            undo=self.apply_operation(target),
        )


def apply_entity_transforms(
    target: "CreatureTransformTarget",
    transforms: tuple[EntityTransform, ...],
) -> tuple[EntityTransformReceipt, ...]:
    """Apply ordered transforms and reverse every completed step on failure."""
    receipts: list[EntityTransformReceipt] = []
    try:
        for transform in transforms:
            receipts.append(transform.apply(target))
    except Exception:
        rollback_entity_transforms(tuple(receipts))
        raise
    return tuple(receipts)


def rollback_entity_transforms(
    receipts: tuple[EntityTransformReceipt, ...],
) -> None:
    """Undo an exact transform transaction in reverse application order."""
    for receipt in reversed(receipts):
        receipt.undo()


@runtime_checkable
class CreatureTransformTarget(Protocol):
    """Structural capability surface required by creature transforms."""

    uuid: UUID
    position: tuple[int, int]
    size: Size
    action_economy: ActionEconomy
    equipment: Equipment
    saving_throws: SavingThrowSet
    senses: Senses

    def distance_to_entity(self, target: "CreatureTransformTarget") -> int:
        """Return objective creature-volume distance to another target."""
        ...


def remove_modifier_ownership(ownership: ModifierOwnership) -> None:
    """Remove only modifiers represented by the supplied ownership rows."""
    for value_uuid, modifier_uuid in ownership:
        value = ModifiableValue.get(value_uuid)
        if value is not None:
            value.remove_modifier(modifier_uuid)


def _zero_max_constraint(
    value: ModifiableValue,
    *,
    name: str,
    target: CreatureTransformTarget,
    effect_source_uuid: UUID,
) -> tuple[UUID, UUID]:
    """Install one source-owned zero cap and return its cleanup identity."""
    modifier_uuid = value.self_static.add_max_constraint(
        NumericalModifier(
            name=name,
            value=0,
            source_entity_uuid=target.uuid,
            target_entity_uuid=effect_source_uuid,
        )
    )
    return value.uuid, modifier_uuid


def apply_incapacitated_transform(
    target: CreatureTransformTarget,
    *,
    name: str,
    effect_source_uuid: UUID,
) -> ModifierOwnership:
    """Deny all action channels and movement for one owning effect."""
    return [
        _zero_max_constraint(
            value,
            name=name,
            target=target,
            effect_source_uuid=effect_source_uuid,
        )
        for value in (
            target.action_economy.action_permission,
            target.action_economy.actions,
            target.action_economy.bonus_actions,
            target.action_economy.reactions,
            target.action_economy.movement,
        )
    ]


def apply_turn_spent_transform(
    target: CreatureTransformTarget,
    *,
    name: str,
    effect_source_uuid: UUID,
) -> ModifierOwnership:
    """Spend one commanded turn without suppressing the reaction channel.

    The neutral action-permission gate closes zero-cost and restricted actions,
    while the ordinary action, bonus-action, and movement resources are capped
    explicitly. Pure reaction actions remain governed by the separate reaction
    resource, so a rule that spends a turn does not imply incapacitation.
    """
    return [
        _zero_max_constraint(
            value,
            name=name,
            target=target,
            effect_source_uuid=effect_source_uuid,
        )
        for value in (
            target.action_economy.action_permission,
            target.action_economy.actions,
            target.action_economy.bonus_actions,
            target.action_economy.movement,
        )
    ]


def apply_visual_denial_transform(
    target: CreatureTransformTarget,
    *,
    name: str,
    effect_source_uuid: UUID,
) -> ModifierOwnership:
    """Deny ordinary and special visual access for one owning effect."""
    return [
        _zero_max_constraint(
            target.senses.visual_access,
            name=name,
            target=target,
            effect_source_uuid=effect_source_uuid,
        )
    ]


def apply_opportunity_attack_immunity_transform(
    target: CreatureTransformTarget,
    *,
    name: str,
    effect_source_uuid: UUID,
) -> ModifierOwnership:
    """Prevent this mover from provoking opportunity attacks."""
    return [
        _zero_max_constraint(
            target.action_economy.provokes_opportunity_attacks,
            name=name,
            target=target,
            effect_source_uuid=effect_source_uuid,
        )
    ]


def apply_failed_strength_dexterity_saves(
    target: CreatureTransformTarget,
    *,
    name: str,
    effect_source_uuid: UUID,
) -> ModifierOwnership:
    """Make Strength and Dexterity saving throws fail automatically."""
    ownership: ModifierOwnership = []
    for ability_name in (AbilityName.STRENGTH, AbilityName.DEXTERITY):
        save_bonus = target.saving_throws.get_saving_throw(ability_name).bonus
        modifier_uuid = save_bonus.self_static.add_auto_hit_modifier(
            AutoHitModifier(
                name=name,
                value=AutoHitStatus.AUTOMISS,
                source_entity_uuid=target.uuid,
                target_entity_uuid=effect_source_uuid,
            )
        )
        ownership.append((save_bonus.uuid, modifier_uuid))
    return ownership


def apply_attacker_advantage_transform(
    target: CreatureTransformTarget,
    *,
    name: str,
    effect_source_uuid: UUID,
) -> ModifierOwnership:
    """Give attacks against the target advantage."""
    armor_class = target.equipment.ac_bonus
    modifier_uuid = armor_class.to_target_static.add_advantage_modifier(
        AdvantageModifier(
            name=name,
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=target.uuid,
            target_entity_uuid=effect_source_uuid,
        )
    )
    return [(armor_class.uuid, modifier_uuid)]


def _transform_target(uuid: UUID) -> Optional[CreatureTransformTarget]:
    """Resolve one structurally compatible target without importing Entity."""
    candidate = BaseBlock.get(uuid)
    return candidate if isinstance(candidate, CreatureTransformTarget) else None


def close_range_auto_critical(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict[str, Any]] = None,
) -> Optional[CriticalModifier]:
    """Return automatic critical status for an attacker within five feet."""
    del context
    if target_entity_uuid is None:
        return None
    source = _transform_target(source_entity_uuid)
    attacker = _transform_target(target_entity_uuid)
    if source is None or attacker is None:
        return None
    if source.distance_to_entity(attacker) > 5:
        return None
    return CriticalModifier(
        name="Close Range Auto-Critical",
        value=CriticalStatus.AUTOCRIT,
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=target_entity_uuid,
    )


def prone_distance_advantage(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict[str, Any]] = None,
) -> Optional[AdvantageModifier]:
    """Return prone-style advantage within five feet, else disadvantage."""
    del context
    if target_entity_uuid is None:
        return None
    source = _transform_target(source_entity_uuid)
    attacker = _transform_target(target_entity_uuid)
    if source is None or attacker is None:
        return None
    status = (
        AdvantageStatus.ADVANTAGE
        if source.distance_to_entity(attacker) <= 5
        else AdvantageStatus.DISADVANTAGE
    )
    return AdvantageModifier(
        name="Prone Geometry",
        value=status,
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=target_entity_uuid,
    )


def apply_close_range_auto_critical_transform(
    target: CreatureTransformTarget,
    *,
    name: str,
    effect_source_uuid: UUID,
) -> ModifierOwnership:
    """Give close attackers automatic critical hits against the target."""
    armor_class = target.equipment.ac_bonus
    modifier_uuid = armor_class.to_target_contextual.add_critical_modifier(
        ContextualCriticalModifier(
            name=name,
            source_entity_uuid=target.uuid,
            target_entity_uuid=effect_source_uuid,
            callable=close_range_auto_critical,
        )
    )
    return [(armor_class.uuid, modifier_uuid)]


def apply_prone_geometry_transform(
    target: CreatureTransformTarget,
    *,
    name: str,
    effect_source_uuid: UUID,
) -> ModifierOwnership:
    """Apply distance-sensitive prone-style attack geometry."""
    armor_class = target.equipment.ac_bonus
    modifier_uuid = armor_class.to_target_contextual.add_advantage_modifier(
        ContextualAdvantageModifier(
            name=name,
            source_entity_uuid=target.uuid,
            target_entity_uuid=effect_source_uuid,
            callable=prone_distance_advantage,
        )
    )
    return [(armor_class.uuid, modifier_uuid)]


def apply_stunned_transform(
    target: CreatureTransformTarget,
    *,
    name: str,
    effect_source_uuid: UUID,
) -> ModifierOwnership:
    """Apply the shared mechanics owned by a stunned-like effect."""
    return [
        *apply_incapacitated_transform(target, name=name, effect_source_uuid=effect_source_uuid),
        *apply_failed_strength_dexterity_saves(target, name=name, effect_source_uuid=effect_source_uuid),
        *apply_attacker_advantage_transform(target, name=name, effect_source_uuid=effect_source_uuid),
    ]


def apply_paralyzed_transform(
    target: CreatureTransformTarget,
    *,
    name: str,
    effect_source_uuid: UUID,
) -> ModifierOwnership:
    """Apply incapacitation, failed saves, attacker advantage, and auto-crits."""
    return [
        *apply_stunned_transform(target, name=name, effect_source_uuid=effect_source_uuid),
        *apply_close_range_auto_critical_transform(target, name=name, effect_source_uuid=effect_source_uuid),
    ]


def apply_unconscious_transform(
    target: CreatureTransformTarget,
    *,
    name: str,
    effect_source_uuid: UUID,
) -> ModifierOwnership:
    """Apply the full independently owned unconscious mechanical transform."""
    return [
        *apply_paralyzed_transform(target, name=name, effect_source_uuid=effect_source_uuid),
        *apply_visual_denial_transform(target, name=name, effect_source_uuid=effect_source_uuid),
        *apply_prone_geometry_transform(target, name=name, effect_source_uuid=effect_source_uuid),
    ]


def apply_life_state_transform(
    target: CreatureTransformTarget,
    state: LifeState,
    *,
    effect_source_uuid: UUID,
) -> ModifierOwnership:
    """Install the capabilities derived from one authoritative life state."""
    if state in {LifeState.DYING, LifeState.STABLE}:
        return apply_unconscious_transform(
            target,
            name=f"Life State: {state.value}",
            effect_source_uuid=effect_source_uuid,
        )
    if state is LifeState.DEAD:
        return [
            *apply_incapacitated_transform(
                target,
                name="Life State: dead",
                effect_source_uuid=effect_source_uuid,
            ),
            *apply_visual_denial_transform(
                target,
                name="Life State: dead",
                effect_source_uuid=effect_source_uuid,
            ),
        ]
    return []
