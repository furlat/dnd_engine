"""Data-driven structural applier for passive character-origin features."""

from functools import partial
from typing import Any
from uuid import UUID, uuid5

from dnd.content_system.character_grant_types import (
    CharacterGrantReceipt,
    ModifierHandle,
    ModifierHandleChannel,
    ModifierHandleKind,
)
from dnd.content_system.character_grant_applier_runtime import (
    remove_modifier_handle,
)
from dnd.core.content.durable_characters import AbilityScoreName
from dnd.core.content.identities import ContentRef
from dnd.core.content.origin_features import (
    OriginCapability,
    OriginSavingThrowAdvantageRule,
    OriginStructuralFeatureDefinition,
)
from dnd.core.modifiers import (
    AdvantageModifier,
    AdvantageStatus,
    ContextualAdvantageModifier,
    NumericalModifier,
    ResistanceModifier,
    ResistanceStatus,
)
from dnd.core.saving_throw_types import (
    SAVING_THROW_CONTEXT_KEY,
    SavingThrowContext,
)
from dnd.entity import Entity


def _child_source_id(grant_id: UUID, identity: str) -> UUID:
    return uuid5(grant_id, f"dnd-engine:origin-structural-source:v1:{identity}")


def _origin_saving_throw_advantage(
    source_entity_uuid: UUID,
    target_entity_uuid: UUID | None,
    modifier_context: dict[str, Any] | None,
    *,
    rule: OriginSavingThrowAdvantageRule,
    modifier_name: str,
) -> AdvantageModifier | None:
    context = (
        modifier_context.get(SAVING_THROW_CONTEXT_KEY)
        if modifier_context is not None
        else None
    )
    if not isinstance(context, SavingThrowContext):
        return None
    if (
        rule.requires_magical is not None
        and context.is_magical is not rule.requires_magical
    ):
        return None
    if (
        rule.effect_tags
        and not set(rule.effect_tags).intersection(context.effect_tags)
    ):
        return None
    return AdvantageModifier(
        name=modifier_name,
        value=AdvantageStatus.ADVANTAGE,
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=target_entity_uuid,
    )


def install_origin_structural_feature(
    *,
    entity: Entity,
    character_id: UUID,
    grant_token: str,
    definition_ref: ContentRef,
    character_level: int,
    definition: OriginStructuralFeatureDefinition,
) -> CharacterGrantReceipt:
    """Install every non-proficiency fact in one authored passive origin trait.

    Automatic proficiencies are expanded into ordinary proficiency schedule
    rows by the build validator. This keeps one canonical proficiency installer
    and makes each language, tool, skill, and weapon grant visible in previews.
    """

    grant_id = uuid5(
        character_id,
        f"dnd-engine:character-structural-grant:v1:{grant_token}",
    )
    modifier_handles: list[ModifierHandle] = []
    sense_sources: list[UUID] = []
    size_sources: list[UUID] = []
    capability_sources: list[tuple[OriginCapability, UUID]] = []
    try:
        for mode in definition.sense_modes:
            source_id = _child_source_id(
                grant_id,
                f"sense:{mode.sense_type.value}:{mode.range_feet}",
            )
            entity.senses.add_sense_mode_source(source_id, mode)
            sense_sources.append(source_id)

        for damage_type in definition.damage_resistances:
            modifier = ResistanceModifier(
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                name=f"{definition_ref.content_id} resistance",
                value=ResistanceStatus.RESISTANCE,
                damage_type=damage_type,
            )
            entity.health.damage_reduction.self_static.add_resistance_modifier(
                modifier,
            )
            modifier_handles.append(
                ModifierHandle(
                    value_uuid=entity.health.damage_reduction.uuid,
                    modifier_uuid=modifier.uuid,
                    kind=ModifierHandleKind.RESISTANCE,
                ),
            )

        for rule in definition.saving_throw_advantages:
            abilities = rule.abilities or tuple(AbilityScoreName)
            for ability in abilities:
                modifier_name = (
                    f"{definition_ref.content_id} "
                    f"{ability.value} saving throw advantage"
                )
                modifier = ContextualAdvantageModifier(
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid,
                    name=modifier_name,
                    callable=partial(
                        _origin_saving_throw_advantage,
                        rule=rule,
                        modifier_name=modifier_name,
                    ),
                )
                value = entity.saving_throws.get_saving_throw(
                    ability.value,
                ).bonus
                value.self_contextual.add_advantage_modifier(modifier)
                modifier_handles.append(
                    ModifierHandle(
                        value_uuid=value.uuid,
                        modifier_uuid=modifier.uuid,
                        channel=ModifierHandleChannel.SELF_CONTEXTUAL,
                        kind=ModifierHandleKind.ADVANTAGE,
                    ),
                )

        if definition.size is not None:
            source_id = _child_source_id(
                grant_id,
                f"size:{definition.size.value}",
            )
            entity.add_structural_size_source(source_id, definition.size)
            size_sources.append(source_id)

        if definition.walking_speed_feet is not None:
            base_speed = entity.action_economy.get_base_value("movement")
            speed_delta = definition.walking_speed_feet - base_speed
            if speed_delta:
                modifier = NumericalModifier.create(
                    source_entity_uuid=entity.uuid,
                    target_entity_uuid=entity.uuid,
                    name=f"{definition_ref.content_id} walking speed",
                    value=speed_delta,
                )
                entity.action_economy.movement.self_static.add_value_modifier(
                    modifier,
                )
                modifier_handles.append(
                    ModifierHandle(
                        value_uuid=entity.action_economy.movement.uuid,
                        modifier_uuid=modifier.uuid,
                    ),
                )

        hit_point_bonus = (
            definition.maximum_hit_points_per_character_level
            * character_level
        )
        if hit_point_bonus:
            modifier = NumericalModifier.create(
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                name=f"{definition_ref.content_id} maximum hit points",
                value=hit_point_bonus,
            )
            entity.health.max_hit_points_bonus.self_static.add_value_modifier(
                modifier,
            )
            modifier_handles.append(
                ModifierHandle(
                    value_uuid=entity.health.max_hit_points_bonus.uuid,
                    modifier_uuid=modifier.uuid,
                ),
            )

        if definition.melee_critical_extra_dice:
            modifier = NumericalModifier.create(
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                name=(
                    f"{definition_ref.content_id} melee critical extra dice"
                ),
                value=definition.melee_critical_extra_dice,
            )
            entity.equipment.crit_extra_dice_melee.self_static.add_value_modifier(
                modifier,
            )
            modifier_handles.append(
                ModifierHandle(
                    value_uuid=entity.equipment.crit_extra_dice_melee.uuid,
                    modifier_uuid=modifier.uuid,
                ),
            )

        for capability in definition.capabilities:
            source_id = _child_source_id(
                grant_id,
                f"capability:{capability.value}",
            )
            entity.add_origin_capability_source(capability, source_id)
            capability_sources.append((capability, source_id))
    except Exception:
        for capability, source_id in reversed(capability_sources):
            entity.remove_origin_capability_source(capability, source_id)
        for source_id in reversed(size_sources):
            entity.remove_structural_size_source(source_id)
        for source_id in reversed(sense_sources):
            entity.senses.remove_sense_mode_source(source_id)
        for handle in reversed(modifier_handles):
            remove_modifier_handle(handle)
        raise

    return CharacterGrantReceipt(
        grant_id=grant_id,
        grant_token=grant_token,
        definition_ref=definition_ref,
        modifier_handles=tuple(modifier_handles),
        sense_mode_source_ids=tuple(sense_sources),
        structural_size_source_ids=tuple(size_sources),
        origin_capability_source_ids=tuple(capability_sources),
    )


__all__ = ["install_origin_structural_feature"]
