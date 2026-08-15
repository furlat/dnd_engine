"""Closed dependency-neutral contracts for authored origin features."""

import pytest
from pydantic import ValidationError

from dnd.types.abilities import AbilityName
from dnd.core.content.durable_characters import (
    ProficiencySubject,
    ProficiencySubjectKind,
)
from dnd.core.content.origin_features import (
    OriginCapability,
    OriginSavingThrowAdvantageRule,
    OriginStructuralFeatureDefinition,
)
from dnd.types.languages import SrdLanguageId
from dnd.types.damage import DamageType
from dnd.types.creatures import Size
from dnd.types.senses import SenseMode, SensesType
from dnd.types.saving_throws import SavingThrowEffectTag


def test_origin_structural_feature_canonicalizes_exact_passive_grants() -> None:
    definition = OriginStructuralFeatureDefinition(
        automatic_proficiencies=(
            ProficiencySubject(
                subject_kind=ProficiencySubjectKind.LANGUAGE,
                subject_id=SrdLanguageId.COMMON.value,
            ),
            ProficiencySubject(
                subject_kind=ProficiencySubjectKind.SKILL,
                subject_id="skill.perception",
            ),
        ),
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
                abilities=(
                    AbilityName.INTELLIGENCE,
                    AbilityName.WISDOM,
                ),
                requires_magical=True,
            ),
        ),
    )

    assert tuple(
        row.identity_key for row in definition.automatic_proficiencies
    ) == (SrdLanguageId.COMMON.value, "skill.perception")
    assert definition.sense_modes[0].sense_type is SensesType.DARKVISION
    assert definition.damage_resistances == (DamageType.FIRE,)
    assert definition.size is Size.SMALL
    assert definition.walking_speed_feet == 25
    assert definition.maximum_hit_points_per_character_level == 1
    assert definition.melee_critical_extra_dice == 1
    assert definition.capabilities == (OriginCapability.TRANCE,)
    assert definition.saving_throw_advantages[0].requires_magical is True


@pytest.mark.parametrize(
    ("field_name", "payload"),
    (
        (
            "automatic_proficiencies",
            (
                ProficiencySubject(
                    subject_kind=ProficiencySubjectKind.LANGUAGE,
                    subject_id=SrdLanguageId.COMMON.value,
                ),
                ProficiencySubject(
                    subject_kind=ProficiencySubjectKind.LANGUAGE,
                    subject_id=SrdLanguageId.COMMON.value,
                ),
            ),
        ),
        (
            "sense_modes",
            (
                SenseMode(
                    sense_type=SensesType.DARKVISION,
                    range_feet=30,
                ),
                SenseMode(
                    sense_type=SensesType.DARKVISION,
                    range_feet=60,
                ),
            ),
        ),
        (
            "damage_resistances",
            (DamageType.FIRE, DamageType.FIRE),
        ),
        (
            "capabilities",
            (OriginCapability.TRANCE, OriginCapability.TRANCE),
        ),
        (
            "saving_throw_advantages",
            (
                OriginSavingThrowAdvantageRule(
                    effect_tags=(SavingThrowEffectTag.POISON,),
                ),
                OriginSavingThrowAdvantageRule(
                    effect_tags=(SavingThrowEffectTag.POISON,),
                ),
            ),
        ),
    ),
)
def test_origin_structural_feature_rejects_duplicate_grants(
    field_name: str,
    payload: object,
) -> None:
    with pytest.raises(ValidationError, match=field_name.replace("_", " ")):
        OriginStructuralFeatureDefinition.model_validate({
            field_name: payload,
        })
