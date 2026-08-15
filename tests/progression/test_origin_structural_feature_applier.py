"""Runtime installation and reversal of data-driven origin features."""

from uuid import UUID, uuid4

import pytest

from dnd.content_system.character_materialization import (
    CharacterCompositionReceipt,
    remove_character_composition,
)
from dnd.content_system.origin_character_grant_appliers import (
    install_origin_structural_feature,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.origin_features import (
    OriginCapability,
    OriginSavingThrowAdvantageRule,
    OriginStructuralFeatureDefinition,
)
from dnd.types.abilities import AbilityName
from dnd.types.damage import DamageType
from dnd.types.creatures import Size
from dnd.types.rolls import AdvantageStatus
from dnd.types.damage import ResistanceStatus
from dnd.types.saving_throws import SAVING_THROW_CONTEXT_KEY, SavingThrowEffectTag
from dnd.core.content.saving_throws import SavingThrowContext
from dnd.types.senses import SenseMode, SensesType
from dnd.entity import Entity


def _feature_ref() -> ContentRef:
    return ContentRef(
        pack_id="content.srd_5_1_cc",
        definition_kind=ContentDefinitionKind.TRAIT,
        content_id="trait.origin.fixture",
        content_version=1,
        definition_contract_hash="a" * 64,
    )


def test_origin_structural_feature_installs_and_reverses_exact_sources() -> None:
    entity = Entity.create(source_entity_uuid=uuid4())
    character_id = uuid4()
    definition = OriginStructuralFeatureDefinition(
        sense_modes=(
            SenseMode(
                sense_type=SensesType.DARKVISION,
                range_feet=60,
            ),
        ),
        damage_resistances=(DamageType.FIRE,),
        size=Size.SMALL,
        walking_speed_feet=25,
        maximum_hit_points_per_character_level=1,
        melee_critical_extra_dice=1,
        capabilities=(OriginCapability.TRANCE,),
        saving_throw_advantages=(
            OriginSavingThrowAdvantageRule(
                effect_tags=(SavingThrowEffectTag.POISON,),
            ),
            OriginSavingThrowAdvantageRule(
                abilities=(AbilityName.WISDOM,),
                requires_magical=True,
            ),
        ),
    )

    receipt = install_origin_structural_feature(
        entity=entity,
        character_id=character_id,
        grant_token="species:fixture",
        definition_ref=_feature_ref(),
        character_level=5,
        definition=definition,
    )

    assert entity.senses.get_sense_range(SensesType.DARKVISION) == 60
    assert (
        entity.health.get_resistance(DamageType.FIRE)
        is ResistanceStatus.RESISTANCE
    )
    assert entity.size is Size.SMALL
    assert entity.action_economy.current_speed() == 25
    assert entity.health.max_hit_points_bonus.normalized_score == 5
    assert entity.equipment.crit_extra_dice_melee.normalized_score == 1
    assert entity.has_origin_capability(OriginCapability.TRANCE)
    wisdom_save = entity.saving_throws.get_saving_throw("wisdom").bonus
    wisdom_save.set_context({
        SAVING_THROW_CONTEXT_KEY: SavingThrowContext(
            cause_ref=_feature_ref(),
            effect_id="origin.fixture.magical_effect",
            is_magical=True,
        ),
    })
    assert wisdom_save.advantage is AdvantageStatus.ADVANTAGE
    wisdom_save.set_context({
        SAVING_THROW_CONTEXT_KEY: SavingThrowContext(
            cause_ref=_feature_ref(),
            effect_id="origin.fixture.poison",
            is_magical=False,
            effect_tags=(SavingThrowEffectTag.POISON,),
        ),
    })
    assert wisdom_save.advantage is AdvantageStatus.ADVANTAGE
    wisdom_save.clear_context()

    remove_character_composition(
        entity,
        CharacterCompositionReceipt(
            runtime_entity_uuid=entity.uuid,
            character_id=character_id,
            grants=(receipt,),
        ),
    )

    assert entity.senses.get_sense_range(SensesType.DARKVISION) == -1
    assert (
        entity.health.get_resistance(DamageType.FIRE)
        is ResistanceStatus.NONE
    )
    assert entity.size is Size.MEDIUM
    assert entity.action_economy.current_speed() == 30
    assert entity.health.max_hit_points_bonus.normalized_score == 0
    assert entity.equipment.crit_extra_dice_melee.normalized_score == 0
    assert not entity.has_origin_capability(OriginCapability.TRANCE)
    wisdom_save.set_context({
        SAVING_THROW_CONTEXT_KEY: SavingThrowContext(
            cause_ref=_feature_ref(),
            effect_id="origin.fixture.magical_effect",
            is_magical=True,
        ),
    })
    assert wisdom_save.advantage is AdvantageStatus.NONE
    wisdom_save.clear_context()


def test_origin_structural_feature_failure_rolls_back_every_prior_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entity = Entity.create(source_entity_uuid=uuid4())
    original_add_capability = Entity.add_origin_capability_source

    def reject_second_capability(
        target: Entity,
        capability: OriginCapability,
        source_id: UUID,
    ) -> None:
        if capability is OriginCapability.TRANCE:
            raise RuntimeError("fixture capability failure")
        original_add_capability(target, capability, source_id)

    monkeypatch.setattr(
        Entity,
        "add_origin_capability_source",
        reject_second_capability,
    )
    definition = OriginStructuralFeatureDefinition(
        damage_resistances=(DamageType.FIRE,),
        capabilities=(
            OriginCapability.ARTIFICERS_LORE,
            OriginCapability.TRANCE,
        ),
        saving_throw_advantages=(
            OriginSavingThrowAdvantageRule(
                abilities=(AbilityName.WISDOM,),
                requires_magical=True,
            ),
        ),
    )

    with pytest.raises(RuntimeError, match="fixture capability failure"):
        install_origin_structural_feature(
            entity=entity,
            character_id=uuid4(),
            grant_token="species:rollback-fixture",
            definition_ref=_feature_ref(),
            character_level=1,
            definition=definition,
        )

    assert entity.origin_capability_sources == {}
    assert (
        entity.health.get_resistance(DamageType.FIRE)
        is ResistanceStatus.NONE
    )
    wisdom_save = entity.saving_throws.get_saving_throw("wisdom").bonus
    assert wisdom_save.self_contextual.advantage_modifiers == {}
