"""Deployment-time reconstruction of one durable character revision pair."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID, uuid4, uuid5

from dnd.actions_functional import update_weapon_templates
from dnd.blocks.base_item import BaseItem, EquippableItem, UsableItem
from dnd.blocks.health import HitDice, HitDiceConfig
from dnd.content_system.character_build_validation import (
    CharacterBuildPreview,
    CharacterBuildValidator,
    CharacterGrantScheduleKind,
)
from dnd.content_system.character_appearance import (
    apply_player_character_appearance,
)
from dnd.content_system.builtin_character_grant_appliers import (
    apply_builtin_character_grant,
)
from dnd.content_system.character_grant_context import (
    BuiltinCharacterGrantContext,
)
from dnd.content_system.character_grant_types import (
    CharacterGrantReceipt,
    LearnedReactionSpellHandle,
    ModifierHandle,
    ModifierHandleChannel,
    ModifierHandleKind,
    ProficiencyHandle,
)
from dnd.content_system.installed_creature_materialization import (
    materialize_installed_creature,
)
from dnd.content_system.creature_bindings import (
    CREATURE_RUNTIME_BINDINGS,
    CreatureRuntimeBindingRegistry,
)
from dnd.content_system.extra_attack_character_grant_appliers import (
    install_extra_attack_family,
)
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content_system.origin_character_grant_appliers import (
    install_origin_structural_feature,
)
from dnd.content_system.origin_innate_spellcasting import (
    install_origin_innate_spellcasting,
)
from dnd.content_system.runtime import (
    SERVER_CONTENT_SYSTEM_RUNTIME,
    ContentSystemRuntime,
)
from dnd.content_system.spell_catalog_composition import (
    SPELL_CATALOG_COMPOSITION_ROWS,
)
from dnd.core.content.durable_characters import (
    AbilityScoreName,
    AbilityScoreImprovementChoice,
    BuildChoiceSelection,
    CantripChoice,
    CharacterDefinitionRevisionV2,
    CharacterHoldingsRevision,
    CharacterItemV2,
    CharacterLoadoutRevisionV1,
    ClassDefinition,
    ClassSkillChoice,
    ElementalAncestryChoice,
    FeatChoice,
    FightingStyleChoice,
    MetamagicChoice,
    OriginTraitChoice,
    ProficiencySubject,
    ProficiencySubjectKind,
    SpellKnownChoice,
    SpellReplacementChoice,
    StartingApparelPackageChoice,
    StartingEquipmentPackageChoice,
    StartingProficiencyChoice,
    SubclassChoice,
)
from dnd.core.content.identities import ContentRef
from dnd.core.content.origin_features import OriginStructuralFeatureDefinition
from dnd.core.base_block import BaseBlock
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.equipment_types import ArmorType, WeaponProperty
from dnd.core.events import AbilityName, SkillName
from dnd.core.modifiers import NumericalModifier
from dnd.core.proficiency_types import ProficiencyMode
from dnd.core.progression import (
    MulticlassSlotRoundingPolicy,
    proficiency_bonus_for_level,
)
from dnd.core.values import ModifiableValue
from dnd.entity import Entity
from dnd.items.torches import Torch


_SPELL_RUNTIME_ROW_BY_REF_KEY = {
    row.declaration.ref.identity_key: row
    for row in SPELL_CATALOG_COMPOSITION_ROWS
}


def _choice_semantic_values(
    choice: BuildChoiceSelection,
) -> tuple[str, ...]:
    """Preserve one durable build choice as ordered semantic values."""
    if isinstance(choice, ClassSkillChoice):
        return choice.skills
    if isinstance(choice, StartingProficiencyChoice):
        return tuple(
            f"{subject.subject_kind.value}:{subject.identity_key}"
            for subject in choice.proficiencies
        )
    if isinstance(
        choice,
        (
            FightingStyleChoice,
            SubclassChoice,
            ElementalAncestryChoice,
            OriginTraitChoice,
            FeatChoice,
            StartingEquipmentPackageChoice,
            StartingApparelPackageChoice,
        ),
    ):
        return (choice.selected_ref.identity_key,)
    if isinstance(
        choice,
        (CantripChoice, SpellKnownChoice, MetamagicChoice),
    ):
        return tuple(ref.identity_key for ref in choice.selected_refs)
    if isinstance(choice, SpellReplacementChoice):
        return (
            choice.replaced_spell_ref.identity_key,
            choice.learned_spell_ref.identity_key,
        )
    if isinstance(choice, AbilityScoreImprovementChoice):
        return tuple(
            f"{ability.value}:{amount}"
            for ability, amount in choice.increases
        )
    raise TypeError(f"Unsupported class-level choice: {choice!r}")


def _selected_feature_ids(
    definition: CharacterDefinitionRevisionV2,
) -> set[str]:
    """Return feature-like identities selected explicitly by level choices."""
    selected: set[str] = set()
    for level in definition.class_levels:
        for choice in level.choices:
            if isinstance(
                choice,
                (FightingStyleChoice, ElementalAncestryChoice, FeatChoice),
            ):
                selected.add(choice.selected_ref.identity_key)
            elif isinstance(choice, MetamagicChoice):
                selected.update(
                    ref.identity_key for ref in choice.selected_refs
                )
    return selected


@dataclass(frozen=True, slots=True)
class CharacterCompositionReceipt:
    """All reversible structural handles installed on one runtime Entity."""

    runtime_entity_uuid: UUID
    character_id: UUID
    grants: tuple[CharacterGrantReceipt, ...]
    automatic_grant_refs: tuple[ContentRef, ...]
    owns_character_origin_identity: bool = False


@dataclass(frozen=True, slots=True)
class MaterializedCharacter:
    """Runtime actor plus exact persistent-item to runtime-item lineage."""

    entity: Entity
    item_lineage: tuple[tuple[UUID, UUID], ...]
    composition_receipt: CharacterCompositionReceipt | None = None


def _grant_source_id(character_id: UUID, token: str) -> UUID:
    """Derive one retry-stable runtime source from the immutable build ledger."""
    return uuid5(
        character_id,
        f"dnd-engine:character-structural-grant:v1:{token}",
    )


def _add_numerical_grant(
    *,
    entity: Entity,
    character_id: UUID,
    token: str,
    value: ModifiableValue,
    amount: int,
    definition_ref: ContentRef | None = None,
    grant_id: UUID | None = None,
    grant_token: str | None = None,
) -> CharacterGrantReceipt:
    resolved_grant_id = grant_id or _grant_source_id(character_id, token)
    modifier = NumericalModifier.create(
        source_entity_uuid=entity.uuid,
        name=f"Character structural grant {resolved_grant_id}",
        value=amount,
    )
    value.self_static.add_value_modifier(modifier)
    return CharacterGrantReceipt(
        grant_id=resolved_grant_id,
        grant_token=grant_token,
        definition_ref=definition_ref,
        modifier_handles=(
            ModifierHandle(
                value_uuid=value.uuid,
                modifier_uuid=modifier.uuid,
            ),
        ),
    )


def _install_proficiency(
    *,
    entity: Entity,
    character_id: UUID,
    token: str,
    subject: ProficiencySubject,
    definition_ref: ContentRef | None,
    source_id: UUID | None = None,
    grant_token: str | None = None,
) -> CharacterGrantReceipt:
    resolved_source_id = source_id or _grant_source_id(character_id, token)
    subject_id = subject.subject_id
    if subject.subject_kind == ProficiencySubjectKind.ABILITY_CHECK:
        if (
            subject_id is None
            or not subject_id.startswith("ability_check.")
        ):
            raise ValueError(
                "ability-check proficiency requires "
                "ability_check.<ability>",
            )
        ability_name = subject_id.removeprefix("ability_check.")
        entity.ability_scores.get_ability(
            cast(AbilityName, ability_name),
        ).add_check_proficiency_source(
            resolved_source_id,
            ProficiencyMode.FULL,
        )
    elif subject.subject_kind == ProficiencySubjectKind.SKILL:
        if subject_id is None or not subject_id.startswith("skill."):
            raise ValueError("skill proficiency requires skill.<name>")
        skill_name = subject_id.removeprefix("skill.")
        entity.skill_set.get_skill(
            cast(SkillName, skill_name),
        ).add_proficiency_source(
            resolved_source_id,
            ProficiencyMode.FULL,
        )
    elif subject.subject_kind == ProficiencySubjectKind.SAVING_THROW:
        if (
            subject_id is None
            or not subject_id.startswith("saving_throw.")
        ):
            raise ValueError(
                "saving-throw proficiency requires saving_throw.<ability>",
            )
        ability_name = subject_id.removeprefix("saving_throw.")
        entity.saving_throws.get_saving_throw(
            cast(AbilityName, ability_name),
        ).add_proficiency_source(resolved_source_id, ProficiencyMode.FULL)
    elif subject.subject_kind == ProficiencySubjectKind.WEAPON:
        if subject_id.startswith("weapon.") and subject_id not in {
            "weapon.simple",
            "weapon.martial",
        }:
            entity.creature_proficiencies.add_specific_weapon_source(
                resolved_source_id,
                subject_id,
            )
        elif subject_id == "weapon.simple":
            entity.creature_proficiencies.add_weapon_source(
                resolved_source_id,
                WeaponProperty.SIMPLE,
            )
        elif subject_id == "weapon.martial":
            entity.creature_proficiencies.add_weapon_source(
                resolved_source_id,
                WeaponProperty.MARTIAL,
            )
        else:
            raise ValueError(
                "weapon proficiency requires an exact item reference or "
                "weapon.simple/weapon.martial",
            )
    elif subject.subject_kind == ProficiencySubjectKind.ARMOR:
        if subject_id is None:
            raise ValueError("armor proficiency requires an armor subject ID")
        armor_types = {
            "armor.light": ArmorType.LIGHT,
            "armor.medium": ArmorType.MEDIUM,
            "armor.heavy": ArmorType.HEAVY,
        }
        try:
            armor_type = armor_types[subject_id]
        except KeyError as error:
            raise ValueError(
                "armor proficiency requires armor.light, armor.medium, or "
                "armor.heavy",
            ) from error
        entity.creature_proficiencies.add_armor_source(
            resolved_source_id,
            armor_type,
        )
    elif subject.subject_kind == ProficiencySubjectKind.SHIELD:
        if subject_id != "shield.shield":
            raise ValueError("shield proficiency requires shield.shield")
        entity.creature_proficiencies.add_shield_source(resolved_source_id)
    elif subject.subject_kind == ProficiencySubjectKind.TOOL:
        if subject_id is None or not subject_id.startswith("tool."):
            raise ValueError("tool proficiency requires tool.<identity>")
        entity.creature_proficiencies.add_tool_source(
            resolved_source_id,
            subject_id,
        )
    elif subject.subject_kind == ProficiencySubjectKind.LANGUAGE:
        if subject_id is None or not subject_id.startswith("language."):
            raise ValueError("language knowledge requires language.<identity>")
        entity.creature_proficiencies.add_language_source(
            resolved_source_id,
            subject_id,
        )
    else:
        raise ValueError(
            f"runtime proficiency subject {subject.subject_kind.value} is not "
            "implemented",
        )
    return CharacterGrantReceipt(
        grant_id=resolved_source_id,
        grant_token=grant_token,
        definition_ref=definition_ref,
        proficiency_handles=(
            ProficiencyHandle(
                subject=subject,
                source_id=resolved_source_id,
            ),
        ),
    )


def _remove_proficiency_handle(
    entity: Entity,
    handle: ProficiencyHandle,
) -> None:
    subject = handle.subject
    subject_id = subject.subject_id
    if subject.subject_kind == ProficiencySubjectKind.ABILITY_CHECK:
        if subject_id is None or not subject_id.startswith("ability_check."):
            raise RuntimeError(
                "ability-check receipt has an invalid subject identity",
            )
        entity.ability_scores.get_ability(
            cast(
                AbilityName,
                subject_id.removeprefix("ability_check."),
            ),
        ).remove_check_proficiency_source(handle.source_id)
        return
    if subject.subject_kind == ProficiencySubjectKind.SKILL:
        if subject_id is None or not subject_id.startswith("skill."):
            raise RuntimeError("skill receipt has an invalid subject identity")
        entity.skill_set.get_skill(
            cast(SkillName, subject_id.removeprefix("skill.")),
        ).remove_proficiency_source(handle.source_id)
        return
    if subject.subject_kind == ProficiencySubjectKind.SAVING_THROW:
        if subject_id is None or not subject_id.startswith("saving_throw."):
            raise RuntimeError(
                "saving-throw receipt has an invalid subject identity",
            )
        entity.saving_throws.get_saving_throw(
            cast(
                AbilityName,
                subject_id.removeprefix("saving_throw."),
            ),
        ).remove_proficiency_source(handle.source_id)
        return
    entity.creature_proficiencies.remove_source(handle.source_id)


def remove_character_composition(
    entity: Entity,
    receipt: CharacterCompositionReceipt,
) -> None:
    """Remove one cold structural composition without replacing the Entity."""
    if receipt.runtime_entity_uuid != entity.uuid:
        raise ValueError(
            "character composition receipt belongs to a different runtime "
            "entity",
        )
    for grant in reversed(receipt.grants):
        cleanup_condition_ids = {
            ref.content_id
            for ref in grant.transient_condition_refs_to_remove
        }
        if cleanup_condition_ids:
            for condition_owner in Entity.get_all_entities():
                for condition in tuple(
                    condition_owner.active_conditions_by_uuid.values()
                ):
                    binding = condition.behavior_binding
                    if (
                        binding is not None
                        and binding.behavior_id in cleanup_condition_ids
                        and condition.source_entity_uuid == entity.uuid
                    ):
                        condition_owner.remove_condition_by_uuid(
                            condition.uuid,
                        )
        for action_uuid in reversed(grant.action_uuids):
            entity.unregister_action_by_uuid(action_uuid)
        for handler_uuid in reversed(grant.handler_uuids):
            handler = entity.event_handlers.get(handler_uuid)
            if handler is not None:
                entity.remove_event_handler(handler)
        for handle in reversed(grant.learned_reaction_spell_handles):
            remove_handler = (
                entity.spellcasting.remove_learned_reaction_spell_source(
                    spell_ref=handle.spell_ref,
                    source_id=handle.spellcasting_source_id,
                    handler_uuid=handle.handler_uuid,
                )
            )
            if remove_handler:
                handler = entity.event_handlers.get(handle.handler_uuid)
                if handler is None:
                    raise RuntimeError(
                        "learned reaction spell handler "
                        f"{handle.handler_uuid} is missing",
                    )
                entity.remove_event_handler(handler)
        for handle in reversed(grant.condition_immunity_handles):
            block = BaseBlock.get(handle.block_uuid)
            if block is None:
                raise RuntimeError(
                    f"composition immunity block {handle.block_uuid} is "
                    "missing",
                )
            block.remove_condition_immunity_source(
                handle.condition_name,
                handle.source_id,
            )
        for source_id in reversed(grant.sense_mode_source_ids):
            entity.senses.remove_sense_mode_source(source_id)
        for source_id in reversed(grant.structural_size_source_ids):
            entity.remove_structural_size_source(source_id)
        for capability, source_id in reversed(
            grant.origin_capability_source_ids,
        ):
            entity.remove_origin_capability_source(capability, source_id)
        for resource_name, source_id in reversed(
            grant.resource_recovery_contribution_ids,
        ):
            entity.action_economy.remove_resource_recovery_contribution(
                resource_name,
                source_id,
            )
        for resource_name, source_id in reversed(
            grant.resource_contribution_ids,
        ):
            entity.action_economy.remove_resource_contribution(
                resource_name,
                source_id,
            )
        for formula_id in reversed(grant.armor_class_formula_ids):
            entity.equipment.remove_armor_class_formula_candidate(formula_id)
        for source_id in reversed(grant.attack_multiplicity_grant_ids):
            entity.action_economy.remove_attack_multiplicity_grant(source_id)
        for source_id in reversed(grant.normal_spell_slot_capacity_source_ids):
            entity.action_economy.remove_normal_spell_slot_capacity(source_id)
        for source_id in reversed(
            grant.spell_damage_affinity_contribution_ids,
        ):
            entity.spellcasting.remove_spell_damage_affinity_contribution(
                source_id,
            )
        for source_id in reversed(grant.spellcasting_source_ids):
            entity.spellcasting.remove_source(source_id)
        for hit_die_uuid in reversed(grant.hit_die_uuids):
            entity.health.remove_hit_dice_by_uuid(hit_die_uuid)
        for handle in reversed(grant.proficiency_handles):
            _remove_proficiency_handle(entity, handle)
        for handle in reversed(grant.modifier_handles):
            value = ModifiableValue.get(handle.value_uuid)
            if value is None:
                raise RuntimeError(
                    f"composition value {handle.value_uuid} is missing",
                )
            if handle.channel == ModifierHandleChannel.SELF_STATIC:
                channel = value.self_static
            elif handle.channel == ModifierHandleChannel.SELF_CONTEXTUAL:
                channel = value.self_contextual
            else:
                raise RuntimeError(
                    f"unsupported composition modifier channel "
                    f"{handle.channel.value}",
                )
            if handle.kind == ModifierHandleKind.VALUE:
                channel.remove_value_modifier(handle.modifier_uuid)
            elif handle.kind == ModifierHandleKind.MIN_CONSTRAINT:
                channel.remove_min_constraint(handle.modifier_uuid)
            elif handle.kind == ModifierHandleKind.MAX_CONSTRAINT:
                channel.remove_max_constraint(handle.modifier_uuid)
            elif handle.kind == ModifierHandleKind.ADVANTAGE:
                channel.remove_advantage_modifier(handle.modifier_uuid)
            elif handle.kind == ModifierHandleKind.CRITICAL:
                channel.remove_critical_modifier(handle.modifier_uuid)
            elif handle.kind == ModifierHandleKind.AUTO_HIT:
                channel.remove_auto_hit_modifier(handle.modifier_uuid)
            elif handle.kind == ModifierHandleKind.RESISTANCE:
                channel.remove_resistance_modifier(handle.modifier_uuid)
            else:
                raise RuntimeError(
                    f"unsupported composition modifier kind "
                    f"{handle.kind.value}",
                )
    if receipt.owns_character_origin_identity:
        entity.clear_character_origin_identity()


def apply_character_composition(
    *,
    entity: Entity,
    definition: CharacterDefinitionRevisionV2,
    loadout: CharacterLoadoutRevisionV1,
    preview: CharacterBuildPreview,
    runtime: ContentSystemRuntime,
) -> CharacterCompositionReceipt:
    """Install one already-validated source-owned structural composition."""
    registry = runtime.require().registry
    receipts: list[CharacterGrantReceipt] = []
    character_id = definition.character_id
    initial_dexterity_modifier = entity.ability_scores.dexterity.modifier
    entity.set_character_origin_identity(
        species_ref=definition.species_ref,
        species_variant_ref=definition.species_variant_ref,
        background_ref=definition.background_ref,
    )
    try:
        for ability in AbilityScoreName:
            ability_name = cast(AbilityName, ability.value)
            score = getattr(definition.base_ability_scores, ability.value)
            receipts.append(
                _add_numerical_grant(
                    entity=entity,
                    character_id=character_id,
                    token=f"ability.base:{ability.value}",
                    value=entity.ability_scores.get_ability(
                        ability_name,
                    ).ability_score,
                    amount=score,
                ),
            )
        for bonus_name, ability, amount in (
            (
                "plus_two",
                definition.flexible_ability_bonuses.plus_two,
                2,
            ),
            (
                "plus_one",
                definition.flexible_ability_bonuses.plus_one,
                1,
            ),
        ):
            receipts.append(
                _add_numerical_grant(
                    entity=entity,
                    character_id=character_id,
                    token=f"ability.flexible:{bonus_name}:{ability.value}",
                    value=entity.ability_scores.get_ability(
                        cast(AbilityName, ability.value),
                    ).ability_score,
                    amount=amount,
                ),
            )

        receipts.append(
            _add_numerical_grant(
                entity=entity,
                character_id=character_id,
                token="proficiency_bonus",
                value=entity.proficiency_bonus,
                amount=proficiency_bonus_for_level(
                    definition.earned_character_level,
                ),
            ),
        )

        for scheduled_grant in preview.grant_schedule:
            grant_id = uuid5(
                character_id,
                scheduled_grant.grant_token,
            )
            if (
                scheduled_grant.kind
                == CharacterGrantScheduleKind.PROFICIENCY
            ):
                subject = scheduled_grant.proficiency
                if subject is None:
                    raise RuntimeError(
                        "validated proficiency grant has no subject",
                    )
                receipts.append(
                    _install_proficiency(
                        entity=entity,
                        character_id=character_id,
                        token=scheduled_grant.grant_token,
                        subject=subject,
                        definition_ref=(
                            scheduled_grant.content_ref
                            or scheduled_grant.provenance.source_ref
                        ),
                        source_id=grant_id,
                        grant_token=scheduled_grant.grant_token,
                    ),
                )
                continue
            if (
                scheduled_grant.kind
                == CharacterGrantScheduleKind.ABILITY_SCORE_INCREASE
            ):
                ability = scheduled_grant.ability
                amount = scheduled_grant.amount
                if ability is None or amount is None:
                    raise RuntimeError(
                        "validated ability-score grant has no payload",
                    )
                receipts.append(
                    _add_numerical_grant(
                        entity=entity,
                        character_id=character_id,
                        token=scheduled_grant.grant_token,
                        value=entity.ability_scores.get_ability(
                            cast(AbilityName, ability.value),
                        ).ability_score,
                        amount=amount,
                        definition_ref=(
                            scheduled_grant.provenance.source_ref
                        ),
                        grant_id=grant_id,
                        grant_token=scheduled_grant.grant_token,
                    ),
                )

        grant_context = BuiltinCharacterGrantContext(
            entity=entity,
            character_id=character_id,
            preview=preview,
            runtime=runtime,
        )
        for scheduled_grant in preview.grant_schedule:
            content_ref = scheduled_grant.content_ref
            if (
                scheduled_grant.kind
                is CharacterGrantScheduleKind.AUTOMATIC_CONTENT
                and content_ref is not None
            ):
                declaration = registry.resolve_definition(content_ref)
                feature = declaration.definition_payload
                if isinstance(feature, OriginStructuralFeatureDefinition):
                    receipts.append(
                        install_origin_structural_feature(
                            entity=entity,
                            character_id=character_id,
                            grant_token=scheduled_grant.grant_token,
                            definition_ref=content_ref,
                            character_level=definition.earned_character_level,
                            definition=feature,
                        ),
                    )
                    continue
            receipt = apply_builtin_character_grant(
                context=grant_context,
                entry=scheduled_grant,
            )
            if receipt is not None:
                receipts.append(receipt)
        extra_attack_family = install_extra_attack_family(grant_context)
        if extra_attack_family is not None:
            receipts.append(extra_attack_family)

        for level in definition.class_levels:
            class_definition = registry.resolve_typed_definition(
                level.class_ref,
                ClassDefinition,
            )

            hit_die = HitDice.create(
                source_entity_uuid=entity.uuid,
                name=(
                    f"{level.class_ref.content_id} "
                    f"{level.class_level_id.value}"
                ),
                config=HitDiceConfig(
                    hit_dice_value=class_definition.hit_die,
                    hit_dice_count=1,
                    mode=(
                        "maximums"
                        if level.character_level == 1
                        else "average"
                    ),
                    ignore_first_level=level.character_level != 1,
                ),
            )
            entity.health.add_hit_dice(hit_die)
            receipts.append(
                CharacterGrantReceipt(
                    grant_id=_grant_source_id(
                        character_id,
                        f"hit_die:{level.class_level_id.value}",
                    ),
                    definition_ref=level.class_ref,
                    hit_die_uuids=(hit_die.uuid,),
                ),
            )

        final_dexterity_modifier = entity.ability_scores.dexterity.modifier
        initiative_delta = (
            final_dexterity_modifier - initial_dexterity_modifier
        )
        if initiative_delta:
            receipts.append(
                _add_numerical_grant(
                    entity=entity,
                    character_id=character_id,
                    token="initiative_from_dexterity",
                    value=entity.initiative,
                    amount=initiative_delta,
                ),
            )

        for contribution in preview.caster_contributions:
            feature_level = contribution.spellcasting_feature_class_level
            source = contribution.spellcasting_source_id
            ability = contribution.spellcasting_ability
            if (
                source is None
                or ability is None
                or feature_level is None
                or contribution.class_level < feature_level
            ):
                continue
            source_id = _grant_source_id(
                character_id,
                f"spellcasting_source:{source.value}",
            )
            entity.spellcasting.add_source(
                source_id,
                cast(AbilityName, ability.value),
                provider_ref=contribution.class_ref,
                caster_progression=contribution.progression,
                provider_level=contribution.class_level,
                maximum_spell_rank=contribution.maximum_spell_rank,
                ritual_policy=contribution.ritual_policy,
            )
            receipts.append(
                CharacterGrantReceipt(
                    grant_id=source_id,
                    definition_ref=contribution.class_ref,
                    spellcasting_source_ids=(source_id,),
                ),
            )

        source_runtime_ids = {
            contribution.spellcasting_source_id.value: _grant_source_id(
                character_id,
                (
                    "spellcasting_source:"
                    f"{contribution.spellcasting_source_id.value}"
                ),
            )
            for contribution in preview.caster_contributions
            if (
                contribution.spellcasting_source_id is not None
                and contribution.spellcasting_feature_class_level is not None
                and contribution.class_level
                >= contribution.spellcasting_feature_class_level
            )
        }
        receipts.extend(
            install_origin_innate_spellcasting(grant_context),
        )
        provider_levels = {
            contribution.class_ref.identity_key: contribution.class_level
            for contribution in preview.caster_contributions
        }
        for known_spell in preview.final_known_spells:
            runtime_source_id = source_runtime_ids.get(
                known_spell.spellcasting_source_id.value,
            )
            if runtime_source_id is None:
                raise RuntimeError(
                    "validated known spell references an inactive casting "
                    f"source {known_spell.spellcasting_source_id.value}",
                )
            row = _SPELL_RUNTIME_ROW_BY_REF_KEY.get(
                known_spell.spell_ref.identity_key,
            )
            installed_declaration = registry.resolve_definition(
                known_spell.spell_ref,
            )
            if (
                row is None
                or row.declaration.ref != known_spell.spell_ref
                or installed_declaration.ref != row.declaration.ref
            ):
                raise RuntimeError(
                    "Known spell has no exact installed runtime class for "
                    f"{known_spell.spell_ref.identity_key}",
                )
            provider_level = provider_levels.get(
                known_spell.provider_ref.identity_key,
            )
            if provider_level is None:
                raise RuntimeError(
                    "Known spell provider is not an active class contribution",
                )
            if row.spell_type is not None:
                spell = row.spell_type(
                    source_entity_uuid=entity.uuid,
                    caster_level=provider_level,
                    spellcasting_source_id=runtime_source_id,
                    template=True,
                )
                runtime.bind_granted_behavior(
                    spell,
                    provider_id=known_spell.provider_ref.content_id,
                    runtime_owner_uuid=entity.uuid,
                )
                entity.register_action(spell)
                receipts.append(
                    CharacterGrantReceipt(
                        grant_id=uuid5(
                            character_id,
                            known_spell.grant_token,
                        ),
                        grant_token=known_spell.grant_token,
                        definition_ref=known_spell.spell_ref,
                        action_uuids=(spell.uuid,),
                    ),
                )
                continue

            handler_factory = row.reaction_handler_factory
            if handler_factory is None:
                raise RuntimeError(
                    "Known spell composition owns no playable runtime surface "
                    f"for {known_spell.spell_ref.identity_key}",
                )
            handler_uuid = (
                entity.spellcasting.learned_reaction_spell_handler_uuid(
                    known_spell.spell_ref,
                )
            )
            created_handler = None
            if handler_uuid is None:
                created_handler = handler_factory(entity.uuid)
                runtime.bind_granted_behavior(
                    created_handler,
                    provider_id=known_spell.spell_ref.content_id,
                    runtime_owner_uuid=entity.uuid,
                )
                entity.add_event_handler(created_handler)
                handler_uuid = created_handler.uuid
            elif handler_uuid not in entity.event_handlers:
                raise RuntimeError(
                    "Learned reaction spell ownership references a missing "
                    f"handler {handler_uuid}",
                )
            try:
                entity.spellcasting.add_learned_reaction_spell_source(
                    spell_ref=known_spell.spell_ref,
                    source_id=runtime_source_id,
                    handler_uuid=handler_uuid,
                )
            except Exception:
                if created_handler is not None:
                    entity.remove_event_handler(created_handler)
                raise
            receipts.append(
                CharacterGrantReceipt(
                    grant_id=uuid5(
                        character_id,
                        known_spell.grant_token,
                    ),
                    grant_token=known_spell.grant_token,
                    definition_ref=known_spell.spell_ref,
                    learned_reaction_spell_handles=(
                        LearnedReactionSpellHandle(
                            spell_ref=known_spell.spell_ref,
                            spellcasting_source_id=runtime_source_id,
                            handler_uuid=handler_uuid,
                        ),
                    ),
                ),
            )

        if preview.normal_spell_slots:
            source_id = _grant_source_id(
                character_id,
                "normal_spell_slot_capacity",
            )
            entity.action_economy.set_normal_spell_slot_capacity(
                source_id,
                dict(preview.normal_spell_slots),
            )
            receipts.append(
                CharacterGrantReceipt(
                    grant_id=source_id,
                    normal_spell_slot_capacity_source_ids=(source_id,),
                ),
            )
    except Exception:
        partial = CharacterCompositionReceipt(
            runtime_entity_uuid=entity.uuid,
            character_id=character_id,
            grants=tuple(receipts),
            automatic_grant_refs=preview.automatic_grant_refs,
            owns_character_origin_identity=True,
        )
        remove_character_composition(entity, partial)
        raise

    return CharacterCompositionReceipt(
        runtime_entity_uuid=entity.uuid,
        character_id=character_id,
        grants=tuple(receipts),
        automatic_grant_refs=preview.automatic_grant_refs,
        owns_character_origin_identity=True,
    )


def _restore_item_state(item: BaseItem, durable_item: CharacterItemV2) -> None:
    """Restore authored durable state before the item enters owner containers."""

    if item.stack_id is None and durable_item.quantity != 1:
        raise ValueError("Non-stackable durable items must have quantity one")
    if durable_item.quantity > item.max_stack:
        raise ValueError(
            f"Durable quantity {durable_item.quantity} exceeds max stack "
            f"{item.max_stack}",
        )
    item.stack_count = durable_item.quantity

    if durable_item.remaining_charges is not None:
        if not isinstance(item, UsableItem):
            raise TypeError("remaining_charges requires a usable item")
        if (
            item.max_charges >= 0
            and durable_item.remaining_charges > item.max_charges
        ):
            raise ValueError(
                "remaining_charges exceeds the authored per-item maximum",
            )
        item.charges = durable_item.remaining_charges

    if durable_item.durability_damage is not None:
        health = item.health
        if health is None:
            raise TypeError("durability_damage requires a breakable item")
        maximum = health.get_max_hit_dices_points(0)
        if durable_item.durability_damage >= maximum:
            raise ValueError(
                "Destroyed items cannot enter durable character holdings",
            )
        health.damage_taken = durable_item.durability_damage


def materialize_character(
    *,
    definition: CharacterDefinitionRevisionV2,
    holdings: CharacterHoldingsRevision,
    loadout: CharacterLoadoutRevisionV1 | None = None,
    runtime_entity_uuid: UUID | None,
    display_name: str,
    faction: str | None,
    position: tuple[int, int],
    deployment_role: CreatureDeploymentRole,
    expected_ruleset_digest: str | None = None,
    multiclass_slot_rounding_policy: MulticlassSlotRoundingPolicy = (
        MulticlassSlotRoundingPolicy.SRD_5_2_ROUND_UP
    ),
    permissive_multiclass_prerequisites: bool = True,
    runtime: ContentSystemRuntime = SERVER_CONTENT_SYSTEM_RUNTIME,
    creature_binding_registry: CreatureRuntimeBindingRegistry = (
        CREATURE_RUNTIME_BINDINGS
    ),
    runtime_content_ref: ContentRef | None = None,
) -> MaterializedCharacter:
    """Build structural creature state, then hydrate exact persisted possessions."""

    definition.verify_integrity()
    holdings.verify_integrity()
    if definition.character_id != holdings.character_id:
        raise ValueError(
            "Character definition and holdings belong to different characters",
        )
    loaded = runtime.require()
    if definition.content_set_digest != loaded.content_set_digest:
        raise ValueError(
            "Character definition content set differs from this worker",
        )

    composition_receipt: CharacterCompositionReceipt | None = None
    if loadout is None:
        raise ValueError("character materialization requires a loadout")
    loadout.verify_integrity()
    if expected_ruleset_digest is None:
        raise ValueError(
            "character materialization requires the pinned ruleset digest",
        )
    validation = CharacterBuildValidator(
        loaded,
        expected_ruleset_digest=expected_ruleset_digest,
        multiclass_slot_rounding_policy=(
            multiclass_slot_rounding_policy
        ),
        permissive_multiclass_prerequisites=(
            permissive_multiclass_prerequisites
        ),
    ).validate(definition, loadout)
    if not validation.valid or validation.preview is None:
        details = "; ".join(
            (
                f"{issue.code.value}@{'.'.join(issue.path)}"
                + (f": {issue.detail}" if issue.detail else "")
            )
            for issue in validation.issues
        )
        raise ValueError(f"invalid character build: {details}")
    creature_recipe = definition.body_recipe

    entity = materialize_installed_creature(
        creature_recipe,
        runtime_entity_uuid=runtime_entity_uuid or uuid4(),
        display_name=display_name,
        faction=faction,
        position=position,
        deployment_role=deployment_role,
        possession_mode=(
            CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY
        ),
        binding_registry=creature_binding_registry,
        entity_content_ref=runtime_content_ref,
        runtime=runtime,
    )
    lineage: list[tuple[UUID, UUID]] = []
    starting_torches: list[Torch] = []
    try:
        apply_player_character_appearance(
            entity.appearance,
            body_ref=definition.body_recipe.ref,
            species_ref=definition.species_ref,
            selection=definition.appearance,
        )
        composition_receipt = apply_character_composition(
            entity=entity,
            definition=definition,
            loadout=loadout,
            preview=validation.preview,
            runtime=runtime,
        )
        placements = []
        for durable_item in holdings.items:
            item = build_authored_item(durable_item.item_id, entity.uuid)
            _restore_item_state(item, durable_item)
            placements.append((item, durable_item.equipped_slot))
            if isinstance(item, Torch):
                starting_torches.append(item)
            lineage.append((durable_item.character_item_id, item.uuid))
        entity.install_initial_items(tuple(placements))
        update_weapon_templates(entity)
        for torch in starting_torches:
            torch.ignite(entity.uuid)
        entity.character_origin_state = (
            (
                ("strength", definition.base_ability_scores.strength),
                ("dexterity", definition.base_ability_scores.dexterity),
                (
                    "constitution",
                    definition.base_ability_scores.constitution,
                ),
                (
                    "intelligence",
                    definition.base_ability_scores.intelligence,
                ),
                ("wisdom", definition.base_ability_scores.wisdom),
                ("charisma", definition.base_ability_scores.charisma),
            ),
            (
                (definition.flexible_ability_bonuses.plus_two.value, 2),
                (definition.flexible_ability_bonuses.plus_one.value, 1),
            ),
            tuple(
                (
                    choice.choice_id,
                    _choice_semantic_values(choice),
                )
                for choice in definition.immutable_origin_choices
            ),
        )
        entity.character_class_levels = tuple(
            (
                level.class_level_id.value,
                level.character_level,
                level.class_ref.identity_key,
                level.resulting_class_level,
                (
                    level.subclass_ref.identity_key
                    if level.subclass_ref is not None
                    else None
                ),
                tuple(
                    (
                        choice.choice_id,
                        _choice_semantic_values(choice),
                    )
                    for choice in level.choices
                ),
            )
            for level in definition.class_levels
        )
        entity.character_feature_ids = tuple(sorted({
            *(
                ref.identity_key
                for ref in validation.preview.automatic_grant_refs
            ),
            *_selected_feature_ids(definition),
        }))
        entity.character_prepared_spell_ids = tuple(sorted(
            spell_ref.identity_key
            for source in loadout.prepared_spells
            for spell_ref in source.spell_refs
        ))
        entity.character_feature_toggle_ids = tuple(
            toggle.feature_ref.identity_key
            for toggle in loadout.feature_toggles
            if toggle.enabled
        )
    except Exception:
        if (
            composition_receipt is not None
            and Entity.get(entity.uuid) is entity
        ):
            remove_character_composition(entity, composition_receipt)
        creature_binding_registry.discard(entity.uuid)
        if Entity.get(entity.uuid) is entity and not entity.creation_committed:
            entity.discard_uncommitted()
        raise

    return MaterializedCharacter(
        entity=entity,
        item_lineage=tuple(lineage),
        composition_receipt=composition_receipt,
    )


__all__ = [
    "MaterializedCharacter",
    "CharacterCompositionReceipt",
    "CharacterGrantReceipt",
    "ModifierHandle",
    "ProficiencyHandle",
    "apply_character_composition",
    "materialize_character",
    "remove_character_composition",
]
