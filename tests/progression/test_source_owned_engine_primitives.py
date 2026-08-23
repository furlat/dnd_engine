"""Focused ownership regressions for reversible character progression."""

from typing import cast
from uuid import uuid4

import pytest

from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import (
    ActionEconomy,
    RechargeType,
    ResourceCapacityPolicy,
)
from dnd.blocks.creature_proficiencies import (
    CreatureProficienciesConfig,
)
from dnd.blocks.equipment import (
    ArmorClassFormulaCandidate,
    Weapon,
)
from dnd.blocks.health import Health, HitDice, HitDiceConfig
from dnd.blocks.skills import Skill
from dnd.blocks.saving_throws import SavingThrow
from dnd.blocks.spellcasting import SpellcastingBlock
from dnd.core.base_actions import (
    BaseAction,
)
from dnd.types.progression import RitualPreparationPolicy
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.types.equipment import ArmorType, WeaponProperty, WeaponSlot
from dnd.types.abilities import AbilityName
from dnd.core.events.resolution_events import (
    Range,
    RangeType,
)
from dnd.core.feature_grants import AttackMultiplicityGrant
from dnd.types.damage import DamageType
from dnd.types.proficiency import ProficiencyMode
from dnd.types.progression import CasterProgression
from dnd.entities.entity import Entity, EntityConfig
from dnd.entities.entity_creation import create_entity


class _OwnedAction(BaseAction):
    """Minimal template used to exercise exact action ownership."""


def test_action_unregister_by_uuid_preserves_same_name_sibling() -> None:
    owner = create_entity(uuid4(), entity_kind_id="test.source_owned_owner")
    first = _OwnedAction(
        source_entity_uuid=owner.uuid,
        name="Shared Name",
        template=True,
        use_register=False,
    )
    second = _OwnedAction(
        source_entity_uuid=owner.uuid,
        name="Shared Name",
        template=True,
        use_register=False,
    )
    owner.registered_actions = [first, second]

    assert owner.unregister_action_by_uuid(first.uuid)
    assert [action.uuid for action in owner.registered_actions] == [second.uuid]
    assert not owner.unregister_action_by_uuid(first.uuid)


def test_skill_proficiency_sources_resolve_strongest_without_stacking() -> None:
    skill = Skill.create(source_entity_uuid=uuid4(), name="arcana")
    half_down = uuid4()
    half_up = uuid4()
    full = uuid4()
    expertise = uuid4()

    skill.add_proficiency_source(half_down, ProficiencyMode.HALF_ROUND_DOWN)
    assert skill._get_proficiency_converter()(3) == 1
    skill.add_proficiency_source(half_up, ProficiencyMode.HALF_ROUND_UP)
    assert skill._get_proficiency_converter()(3) == 2
    skill.add_proficiency_source(full, ProficiencyMode.FULL)
    skill.add_proficiency_source(uuid4(), ProficiencyMode.FULL)
    assert skill._get_proficiency_converter()(3) == 3
    skill.add_proficiency_source(expertise, ProficiencyMode.EXPERTISE)
    assert skill._get_proficiency_converter()(3) == 6

    assert skill.remove_proficiency_source(expertise)
    assert skill._get_proficiency_converter()(3) == 3
    assert skill.remove_proficiency_source(full)
    assert skill._get_proficiency_converter()(3) == 3


def test_expertise_requires_an_applicable_full_proficiency_source() -> None:
    skill = Skill.create(source_entity_uuid=uuid4(), name="arcana")
    expertise = uuid4()
    full = uuid4()

    skill.add_proficiency_source(expertise, ProficiencyMode.EXPERTISE)
    assert skill._get_proficiency_converter()(3) == 0
    skill.add_proficiency_source(full, ProficiencyMode.FULL)
    assert skill._get_proficiency_converter()(3) == 6
    assert skill.remove_proficiency_source(full)
    assert skill._get_proficiency_converter()(3) == 0


def test_imperative_skill_and_save_setters_write_owned_sources() -> None:
    skill = Skill.create(source_entity_uuid=uuid4(), name="arcana")
    skill.set_expertise(True)
    assert skill._get_proficiency_converter()(3) == 6

    saving_throw = SavingThrow.create(
        source_entity_uuid=uuid4(),
        name="wisdom_saving_throw",
    )
    legacy_source = uuid4()
    source = uuid4()
    saving_throw.set_proficiency(True)
    saving_throw.add_proficiency_source(legacy_source, ProficiencyMode.FULL)
    saving_throw.add_proficiency_source(source, ProficiencyMode.EXPERTISE)
    assert saving_throw._get_proficiency_converter()(3) == 6
    assert saving_throw.remove_proficiency_source(source)
    assert saving_throw._get_proficiency_converter()(3) == 3


def test_ability_check_source_applies_to_untrained_skills_without_stacking() -> None:
    entity = create_entity(
        uuid4(),
        entity_kind_id="test.ability_check_entity",
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=14),
            ),
            proficiency_bonus=3,
        ),
    )
    remarkable_athlete = uuid4()
    athletics_training = uuid4()
    entity.ability_scores.strength.add_check_proficiency_source(
        remarkable_athlete,
        ProficiencyMode.HALF_ROUND_UP,
    )

    assert entity.ability_check_bonus(None, "strength").normalized_score == 4
    assert entity.skill_bonus(None, "athletics").normalized_score == 4

    entity.skill_set.athletics.add_proficiency_source(
        athletics_training,
        ProficiencyMode.FULL,
    )
    assert entity.skill_bonus(None, "athletics").normalized_score == 5
    assert entity.ability_scores.strength.remove_check_proficiency_source(
        remarkable_athlete,
    )
    assert entity.ability_check_bonus(None, "strength").normalized_score == 2
    assert entity.skill_bonus(None, "athletics").normalized_score == 5


def test_extra_attack_uses_highest_applicable_rank_and_exact_removal() -> None:
    economy = ActionEconomy.create(source_entity_uuid=uuid4())
    lower_source = uuid4()
    higher_source = uuid4()
    lower_ref = ContentRef(
        pack_id="content.srd_5_1_cc",
        definition_kind=ContentDefinitionKind.CLASS_FEATURE,
        content_id="class_feature.extra_attack.lower",
        content_version=1,
        definition_contract_hash="a" * 64,
    )
    higher_ref = lower_ref.model_copy(
        update={
            "content_id": "class_feature.extra_attack.higher",
            "definition_contract_hash": "b" * 64,
        },
    )
    economy.add_attack_multiplicity_grant(
        AttackMultiplicityGrant(
            grant_id=lower_source,
            provider_id=lower_ref.content_id,
            attacks_per_attack_action=2,
            acquisition_ordinal=5,
        ),
    )
    economy.add_attack_multiplicity_grant(
        AttackMultiplicityGrant(
            grant_id=higher_source,
            provider_id=higher_ref.content_id,
            attacks_per_attack_action=3,
            acquisition_ordinal=11,
        ),
    )

    assert economy.resolve_attacks_per_attack_action() == 3
    assert economy.remove_attack_multiplicity_grant(higher_source)
    assert economy.resolve_attacks_per_attack_action() == 2
    assert economy.remove_attack_multiplicity_grant(lower_source)
    assert economy.resolve_attacks_per_attack_action() == 1


def test_resource_contributions_preserve_spent_uses_on_rebuild() -> None:
    economy = ActionEconomy.create(source_entity_uuid=uuid4())
    first = uuid4()
    second = uuid4()

    economy.add_resource_contribution(
        "channel_divinity",
        first,
        maximum=2,
        recharge_type=RechargeType.SHORT_REST,
        capacity_policy=ResourceCapacityPolicy.MAXIMUM,
    )
    economy.add_resource_contribution(
        "channel_divinity",
        second,
        maximum=3,
        recharge_type=RechargeType.SHORT_REST,
        capacity_policy=ResourceCapacityPolicy.MAXIMUM,
    )
    assert economy.consume_resource("channel_divinity", 2)
    assert economy.resources["channel_divinity"].current == 1

    assert economy.remove_resource_contribution("channel_divinity", second)
    resource = economy.resources["channel_divinity"]
    assert (resource.maximum, resource.current, resource.spent) == (2, 0, 2)
    assert economy.remove_resource_contribution("channel_divinity", first)
    assert "channel_divinity" not in economy.resources


def test_hit_dice_remove_by_uuid_preserves_other_blocks_and_spend() -> None:
    owner_uuid = uuid4()
    d10 = HitDice.create(
        source_entity_uuid=owner_uuid,
        config=HitDiceConfig(hit_dice_value=10, hit_dice_count=2),
    )
    d6 = HitDice.create(
        source_entity_uuid=owner_uuid,
        config=HitDiceConfig(hit_dice_value=6, hit_dice_count=3),
    )
    health = Health(source_entity_uuid=owner_uuid, hit_dices=[d10, d6])
    d6.spend()

    assert health.remove_hit_dice_by_uuid(d10.uuid)
    assert health.hit_dices == [d6]
    assert d6.spent_hit_dice == 1
    assert not health.remove_hit_dice_by_uuid(d10.uuid)


def test_equipment_selects_highest_owned_ac_formula_and_reverts_exactly() -> None:
    entity = create_entity(
        uuid4(),
        entity_kind_id="test.equipment_entity",
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                dexterity=AbilityConfig(ability_score=14),
                wisdom=AbilityConfig(ability_score=16),
            ),
            proficiency_bonus=2,
        ),
    )
    source = uuid4()
    entity.equipment.add_armor_class_formula_candidate(
        ArmorClassFormulaCandidate(
            source_id=source,
            base_ac=10,
            ability_names=("dexterity", "wisdom"),
            requires_unarmored=True,
            allows_shield=False,
        )
    )

    assert entity.ac_bonus().normalized_score == 15
    assert entity.equipment.remove_armor_class_formula_candidate(source)
    assert entity.ac_bonus().normalized_score == 12


def test_spellcasting_sources_resolve_ability_without_replacing_legacy_default() -> None:
    entity = create_entity(
        uuid4(),
        entity_kind_id="test.spellcasting_entity",
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                charisma=AbilityConfig(ability_score=8),
                wisdom=AbilityConfig(ability_score=16),
            ),
            proficiency_bonus=3,
        ),
    )
    cleric_source = uuid4()
    wizard_source = uuid4()
    for source_id, ability, content_id in (
        (cleric_source, "wisdom", "class.cleric"),
        (wizard_source, "intelligence", "class.wizard"),
    ):
        entity.spellcasting.add_source(
            source_id,
            cast(AbilityName, ability),
            provider_id=content_id,
            caster_progression=CasterProgression.FULL_CASTER,
            provider_level=5,
            maximum_spell_rank=3,
            ritual_policy=RitualPreparationPolicy.NONE,
        )

    assert entity.spell_save_dc() == 10
    assert entity.spell_save_dc(spellcasting_source_id=cleric_source) == 14
    assert entity.spell_attack_bonus().normalized_score == 2
    assert entity.spell_attack_bonus(
        spellcasting_source_id=cleric_source
    ).normalized_score == 6
    assert entity.spellcasting.remove_source(cleric_source)
    with pytest.raises(KeyError, match="spellcasting source"):
        entity.spell_save_dc(spellcasting_source_id=cleric_source)

    legacy = SpellcastingBlock.create(source_entity_uuid=uuid4())
    assert legacy.resolve_spellcasting_ability() == legacy.spellcasting_ability


def test_creature_training_owns_weapon_armor_and_shield_proficiency() -> None:
    entity = create_entity(
        uuid4(),
        entity_kind_id="test.creature_training_entity",
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=14),
            ),
            creature_proficiencies=CreatureProficienciesConfig(
                base_simple_weapons=False,
                base_martial_weapons=False,
                base_armor_types=(),
                base_shields=False,
            ),
            proficiency_bonus=3,
        ),
    )
    weapon = Weapon(
        source_entity_uuid=entity.uuid,
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=[WeaponProperty.MARTIAL],
        range=Range(type=RangeType.REACH, normal=5),
    )
    assert entity.equipment.equip(weapon, WeaponSlot.MELEE_MAIN)

    assert entity.attack_bonus().normalized_score == 2
    weapon_source = uuid4()
    armor_source = uuid4()
    shield_source = uuid4()
    entity.creature_proficiencies.add_weapon_source(
        weapon_source,
        WeaponProperty.MARTIAL,
    )
    entity.creature_proficiencies.add_armor_source(
        armor_source,
        ArmorType.HEAVY,
    )
    entity.creature_proficiencies.add_shield_source(shield_source)

    assert entity.attack_bonus().normalized_score == 5
    assert entity.weapon_attack_outcome_baseline().attack_bonus == 5
    assert entity.creature_proficiencies.is_armor_proficient(ArmorType.HEAVY)
    assert entity.creature_proficiencies.is_shield_proficient()

    assert entity.creature_proficiencies.remove_source(weapon_source)
    assert entity.attack_bonus().normalized_score == 2
    assert entity.creature_proficiencies.remove_source(armor_source)
    assert entity.creature_proficiencies.remove_source(shield_source)
    assert not entity.creature_proficiencies.is_armor_proficient(ArmorType.HEAVY)
    assert not entity.creature_proficiencies.is_shield_proficient()


def test_exact_weapon_training_does_not_overgrant_a_whole_category() -> None:
    dagger_ref = ContentRef(
        pack_id="content.srd_5_1_cc",
        definition_kind=ContentDefinitionKind.ITEM,
        content_id="weapon.dagger",
        content_version=1,
        definition_contract_hash="a" * 64,
    )
    quarterstaff_ref = ContentRef(
        pack_id="content.srd_5_1_cc",
        definition_kind=ContentDefinitionKind.ITEM,
        content_id="weapon.quarterstaff",
        content_version=1,
        definition_contract_hash="b" * 64,
    )
    source = uuid4()
    entity = create_entity(
        uuid4(),
        entity_kind_id="test.weapon_training_entity",
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=14),
                dexterity=AbilityConfig(ability_score=14),
            ),
            creature_proficiencies=CreatureProficienciesConfig(
                base_simple_weapons=False,
                base_martial_weapons=False,
                base_armor_types=(),
                base_shields=False,
            ),
            proficiency_bonus=3,
        ),
    )
    dagger = Weapon(
        source_entity_uuid=entity.uuid,
        content_ref=dagger_ref,
        damage_dice=4,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.FINESSE, WeaponProperty.LIGHT],
        range=Range(type=RangeType.REACH, normal=5),
    )
    quarterstaff = Weapon(
        source_entity_uuid=entity.uuid,
        content_ref=quarterstaff_ref,
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.BLUDGEONING,
        properties=[WeaponProperty.VERSATILE],
        range=Range(type=RangeType.REACH, normal=5),
    )

    entity.creature_proficiencies.add_specific_weapon_source(
        source,
        dagger_ref.identity_key,
    )
    assert entity.equipment.equip(dagger, WeaponSlot.MELEE_MAIN)
    assert entity.attack_bonus().normalized_score == 5

    assert entity.equipment.equip(quarterstaff, WeaponSlot.MELEE_MAIN)
    assert entity.attack_bonus().normalized_score == 2

    assert entity.creature_proficiencies.remove_source(source)
    assert entity.equipment.equip(dagger, WeaponSlot.MELEE_MAIN)
    assert entity.attack_bonus().normalized_score == 2


def test_existing_entities_remain_trained_and_unarmed_is_always_proficient() -> None:
    entity = create_entity(
        uuid4(),
        entity_kind_id="test.existing_entity",
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=14),
            ),
            proficiency_bonus=3,
        ),
    )

    assert entity.attack_bonus().normalized_score == 5
    assert entity.creature_proficiencies.is_weapon_proficient(None)
