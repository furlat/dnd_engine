"""Reversible runtime installer for one Dragonborn ancestry selection."""

from __future__ import annotations

from uuid import UUID, uuid5

from dnd.blocks.action_economy import (
    RechargeType,
    ResourceCapacityPolicy,
)
from dnd.content_system.character_grant_types import (
    CharacterGrantReceipt,
    ModifierHandle,
    ModifierHandleKind,
)
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.core.content.dragonborn import DragonbornAncestryFeatureDefinition
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import (
    ResistanceModifier,
    ResistanceStatus,
)
from dnd.entity import Entity
from dnd.origins.dragonborn import (
    DRAGONBORN_BREATH_RESOURCE,
    DragonbornBreathWeapon,
)


def install_dragonborn_ancestry_feature(
    *,
    entity: Entity,
    character_id: UUID,
    grant_token: str,
    definition_ref: ContentRef,
    character_level: int,
    definition: DragonbornAncestryFeatureDefinition,
    runtime: ContentSystemRuntime,
) -> CharacterGrantReceipt:
    """Install ancestry resistance, Breath Weapon, and its rest resource."""
    if definition_ref.definition_kind is not ContentDefinitionKind.TRAIT:
        raise ValueError("Dragonborn ancestry must reference a trait definition")

    grant_id = uuid5(
        character_id,
        f"dnd-engine:character-structural-grant:v1:{grant_token}",
    )
    resistance = ResistanceModifier(
        name=f"{definition.ancestry.value.title()} Draconic Ancestry",
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        value=ResistanceStatus.RESISTANCE,
        damage_type=DamageType(definition.damage_type),
    )
    action = DragonbornBreathWeapon.from_definition(
        source_entity_uuid=entity.uuid,
        ancestry_ref=definition_ref,
        definition=definition,
        character_level=character_level,
        template=True,
    )

    resistance_installed = False
    resource_installed = False
    action_installed = False
    try:
        entity.health.damage_reduction.self_static.add_resistance_modifier(
            resistance,
        )
        resistance_installed = True
        entity.action_economy.add_resource_contribution(
            DRAGONBORN_BREATH_RESOURCE,
            grant_id,
            maximum=1,
            recharge_type=RechargeType.SHORT_REST,
            capacity_policy=ResourceCapacityPolicy.MAXIMUM,
        )
        resource_installed = True
        runtime.bind_granted_behavior(
            action,
            provider_id=definition_ref.content_id,
            runtime_owner_uuid=entity.uuid,
        )
        entity.register_action(action)
        action_installed = True
    except Exception:
        if action_installed:
            entity.unregister_action_by_uuid(action.uuid)
        else:
            action.remove_from_register()
        if resource_installed:
            entity.action_economy.remove_resource_contribution(
                DRAGONBORN_BREATH_RESOURCE,
                grant_id,
            )
        if resistance_installed:
            entity.health.damage_reduction.self_static.remove_resistance_modifier(
                resistance.uuid,
            )
        raise

    return CharacterGrantReceipt(
        grant_id=grant_id,
        grant_token=grant_token,
        definition_ref=definition_ref,
        modifier_handles=(
            ModifierHandle(
                value_uuid=entity.health.damage_reduction.uuid,
                modifier_uuid=resistance.uuid,
                kind=ModifierHandleKind.RESISTANCE,
            ),
        ),
        action_uuids=(action.uuid,),
        resource_contribution_ids=(
            (DRAGONBORN_BREATH_RESOURCE, grant_id),
        ),
    )


__all__ = [
    "DRAGONBORN_BREATH_RESOURCE",
    "install_dragonborn_ancestry_feature",
]
