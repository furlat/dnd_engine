"""Direct character content over the entity composition boundary."""

from uuid import uuid4

import pytest

from dnd.content.characters.character_builds import create_character
from dnd.content.characters.class_definitions import ClassLevelRequest
from dnd.content.characters.class_level_content import (
    add_class_level,
    resolve_initial_level_steps,
)
from dnd.content.characters.character_definitions import (
    BACKGROUND_DEFINITIONS,
    SPECIES_DEFINITIONS,
    SPECIES_VARIANT_DEFINITIONS,
)
from dnd.core.events.events_registry import EventQueue, EventType
from dnd.entities.entity import Entity
from dnd.entities.entity_progression import remove_last_level
from dnd.types.abilities import AbilityName
from dnd.types.creatures import (
    Background,
    OriginCapability,
    Species,
    SpeciesVariant,
)
from dnd.types.damage import DamageType, ResistanceStatus
from dnd.types.languages import SrdLanguageId
from dnd.types.progression import (
    AppliedOriginState,
    CharacterClass,
    ClassChoiceSelection,
    OriginChoiceSelection,
)
from dnd.types.rolls import AdvantageStatus
from dnd.types.saving_throws import (
    SAVING_THROW_CONTEXT_KEY,
    SavingThrowContext,
    SavingThrowEffectTag,
)
from dnd.origins.half_orc import HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE
from dnd.origins.dragonborn import (
    DRAGONBORN_BREATH_RESOURCE,
    DragonbornBreathWeapon,
)
from dnd.types.dragonborn import (
    DragonbornAncestry,
    DragonbornBreathGeometry,
)


@pytest.fixture(autouse=True)
def _reset_event_history() -> None:
    EventQueue.reset()


def _human_state() -> AppliedOriginState:
    return AppliedOriginState(
        base_ability_scores=tuple((ability, 10) for ability in AbilityName),
        flexible_ability_bonuses=(
            (AbilityName.STRENGTH, 2),
            (AbilityName.DEXTERITY, 1),
        ),
        choices=(OriginChoiceSelection(
            "species.human.additional_language",
            (SrdLanguageId.ELVISH.value,),
        ),),
    )


def _human_acolyte_state() -> AppliedOriginState:
    return AppliedOriginState(
        base_ability_scores=tuple((ability, 10) for ability in AbilityName),
        flexible_ability_bonuses=(
            (AbilityName.STRENGTH, 2),
            (AbilityName.DEXTERITY, 1),
        ),
        choices=(
            OriginChoiceSelection(
                "species.human.additional_language",
                (SrdLanguageId.ELVISH.value,),
            ),
            OriginChoiceSelection(
                "background.acolyte.languages",
                (
                    SrdLanguageId.DWARVISH.value,
                    SrdLanguageId.CELESTIAL.value,
                ),
            ),
        ),
    )


def _origin_state_without_choices() -> AppliedOriginState:
    return AppliedOriginState(
        base_ability_scores=tuple((ability, 10) for ability in AbilityName),
        flexible_ability_bonuses=(
            (AbilityName.STRENGTH, 2),
            (AbilityName.DEXTERITY, 1),
        ),
    )


def _fighter_requests_to_five() -> tuple[ClassLevelRequest, ...]:
    choice = ClassChoiceSelection
    return (
        ClassLevelRequest(CharacterClass.FIGHTER, choices=(
            choice(
                "class.fighter.first_class.starting_equipment",
                ("starting_equipment.fighter.sword_shield",),
            ),
            choice(
                "class.fighter.proficiencies.skills",
                ("skill.athletics", "skill.perception"),
            ),
            choice(
                "class.fighter.level_1.fighting_style",
                ("class_feature.fighter.fighting_style.defense",),
            ),
        )),
        ClassLevelRequest(CharacterClass.FIGHTER),
        ClassLevelRequest(CharacterClass.FIGHTER, choices=(choice(
            "class.fighter.level_3.subclass",
            ("subclass.fighter.champion",),
        ),)),
        ClassLevelRequest(CharacterClass.FIGHTER, choices=(choice(
            "class.fighter.level_4.asi_or_feat",
            ("ability.strength:+2",),
        ),)),
        ClassLevelRequest(CharacterClass.FIGHTER),
    )


def test_cold_origin_maps_cover_every_supported_identity() -> None:
    assert set(SPECIES_DEFINITIONS) == set(Species)
    assert set(SPECIES_VARIANT_DEFINITIONS) == set(SpeciesVariant)
    assert set(BACKGROUND_DEFINITIONS) == set(Background)


def test_human_character_composes_without_registry_or_server() -> None:
    entity = create_character(
        uuid4(),
        name="Ada",
        species=Species.HUMAN,
        background=Background.ADVENTURER,
        origin_state=_human_state(),
    )
    try:
        assert entity.creation_committed
        assert not entity.is_deployed
        assert entity.species is Species.HUMAN
        assert entity.background is Background.ADVENTURER
        assert entity.ability_scores.strength.ability_score.score == 12
        assert entity.ability_scores.dexterity.ability_score.score == 11
        assert entity.creature_proficiencies.knows_language(
            SrdLanguageId.COMMON.value,
        )
        assert entity.creature_proficiencies.knows_language(
            SrdLanguageId.ELVISH.value,
        )
        assert [
            event.event_type for event in EventQueue.get_events_chronological()
        ] == [EventType.ENTITY_CREATED]
    finally:
        entity.discard_unpublished_runtime()


def test_dwarf_structural_origin_uses_direct_weapon_and_tool_ids() -> None:
    entity = create_character(
        uuid4(),
        name="Dain",
        species=Species.DWARF,
        background=Background.ADVENTURER,
        origin_state=AppliedOriginState(
            base_ability_scores=tuple(
                (ability, 10) for ability in AbilityName
            ),
            flexible_ability_bonuses=(
                (AbilityName.STRENGTH, 2),
                (AbilityName.DEXTERITY, 1),
            ),
            choices=(OriginChoiceSelection(
                "species.dwarf.artisans_tool",
                ("tool.artisan.smiths_tools",),
            ),),
        ),
    )
    try:
        for weapon_id in (
            "weapon.battleaxe",
            "weapon.handaxe",
            "weapon.light_hammer",
            "weapon.warhammer",
        ):
            assert entity.creature_proficiencies.is_weapon_proficient(
                (),
                weapon_id,
            )
        assert entity.creature_proficiencies.is_tool_proficient(
            "tool.artisan.smiths_tools",
        )
        assert (
            entity.health.get_resistance(DamageType.POISON)
            is ResistanceStatus.RESISTANCE
        )
        birth = EventQueue.get_events_by_type(EventType.ENTITY_CREATED)[0]
        assert set(birth.weapon_proficiencies) >= {
            "weapon.battleaxe",
            "weapon.handaxe",
            "weapon.light_hammer",
            "weapon.warhammer",
        }
        assert birth.tools == ("tool.artisan.smiths_tools",)
        assert (DamageType.POISON, ResistanceStatus.RESISTANCE) in (
            birth.damage_affinities
        )
    finally:
        entity.discard_unpublished_runtime()


def test_elf_fey_ancestry_uses_direct_charm_save_semantics() -> None:
    entity = create_character(
        uuid4(),
        name="Lethariel",
        species=Species.ELF,
        background=Background.ADVENTURER,
        origin_state=_origin_state_without_choices(),
    )
    wisdom = entity.saving_throws.get_saving_throw(AbilityName.WISDOM).bonus
    try:
        wisdom.set_context({
            SAVING_THROW_CONTEXT_KEY: SavingThrowContext(
                cause_id="spell.fixture_charm",
                effect_id="effect.fixture_charm",
                condition_id="condition.charmed",
                is_magical=True,
                effect_tags=(SavingThrowEffectTag.CHARM,),
            ),
        })
        assert wisdom.advantage is AdvantageStatus.ADVANTAGE
        wisdom.set_context({
            SAVING_THROW_CONTEXT_KEY: SavingThrowContext(
                cause_id="hazard.fixture_poison",
                effect_id="effect.fixture_poison",
                is_magical=False,
                effect_tags=(SavingThrowEffectTag.POISON,),
            ),
        })
        assert wisdom.advantage is AdvantageStatus.NONE
    finally:
        wisdom.clear_context()
        entity.discard_unpublished_runtime()


def test_gnome_cunning_applies_only_to_magical_mental_saves() -> None:
    entity = create_character(
        uuid4(),
        name="Nissa",
        species=Species.GNOME,
        background=Background.ADVENTURER,
        origin_state=_origin_state_without_choices(),
    )
    intelligence = entity.saving_throws.get_saving_throw(
        AbilityName.INTELLIGENCE,
    ).bonus
    strength = entity.saving_throws.get_saving_throw(AbilityName.STRENGTH).bonus
    magical = {
        SAVING_THROW_CONTEXT_KEY: SavingThrowContext(
            cause_id="spell.fixture_illusion",
            effect_id="effect.fixture_illusion",
            is_magical=True,
        ),
    }
    nonmagical = {
        SAVING_THROW_CONTEXT_KEY: SavingThrowContext(
            cause_id="hazard.fixture_noise",
            effect_id="effect.fixture_noise",
            is_magical=False,
        ),
    }
    try:
        intelligence.set_context(magical)
        strength.set_context(magical)
        assert intelligence.advantage is AdvantageStatus.ADVANTAGE
        assert strength.advantage is AdvantageStatus.NONE
        intelligence.set_context(nonmagical)
        assert intelligence.advantage is AdvantageStatus.NONE
    finally:
        intelligence.clear_context()
        strength.clear_context()
        entity.discard_unpublished_runtime()


def test_active_half_orc_and_halfling_traits_install_by_semantic_identity() -> None:
    half_orc = create_character(
        uuid4(),
        name="Gara",
        species=Species.HALF_ORC,
        background=Background.ADVENTURER,
        origin_state=_origin_state_without_choices(),
    )
    halfling = create_character(
        uuid4(),
        name="Milo",
        species=Species.HALFLING,
        background=Background.ADVENTURER,
        origin_state=_origin_state_without_choices(),
    )
    try:
        assert half_orc.has_feature(
            "species.half_orc.relentless_endurance",
        )
        assert half_orc.action_economy.get_resource_current(
            HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
        ) == 1
        assert {
            handler.behavior_id
            for handler in half_orc.event_handlers.values()
        } >= {"species.half_orc.relentless_endurance"}

        assert halfling.has_feature("species.halfling.lucky")
        assert halfling.has_feature("species.halfling.brave")
        assert halfling.has_origin_capability(
            OriginCapability.HALFLING_NIMBLENESS,
        )
        assert {
            handler.behavior_id
            for handler in halfling.event_handlers.values()
        } >= {"species.halfling.lucky"}
    finally:
        half_orc.discard_unpublished_runtime()
        halfling.discard_unpublished_runtime()


def test_hill_dwarf_toughness_tracks_each_reversible_character_level() -> None:
    entity_uuid = uuid4()
    dwarf_state = AppliedOriginState(
        base_ability_scores=tuple((ability, 10) for ability in AbilityName),
        flexible_ability_bonuses=(
            (AbilityName.STRENGTH, 2),
            (AbilityName.DEXTERITY, 1),
        ),
        choices=(OriginChoiceSelection(
            "species.dwarf.artisans_tool",
            ("tool.artisan.smiths_tools",),
        ),),
    )

    entity = create_character(
        entity_uuid,
        name="Dain",
        species=Species.DWARF,
        species_variant=SpeciesVariant.HILL_DWARF,
        background=Background.ADVENTURER,
        origin_state=dwarf_state,
    )
    try:
        assert entity.health.max_hit_points_bonus.normalized_score == 0
        level = add_class_level(entity, ClassLevelRequest(
            CharacterClass.FIGHTER,
            choices=(
                ClassChoiceSelection(
                    "class.fighter.first_class.starting_equipment",
                    ("starting_equipment.fighter.sword_shield",),
                ),
                ClassChoiceSelection(
                    "class.fighter.proficiencies.skills",
                    ("skill.athletics", "skill.perception"),
                ),
                ClassChoiceSelection(
                    "class.fighter.level_1.fighting_style",
                    ("class_feature.fighter.fighting_style.dueling",),
                ),
            ),
        ))
        assert entity.health.max_hit_points_bonus.normalized_score == 1
        remove_last_level(entity, level.step_id)
        assert entity.health.max_hit_points_bonus.normalized_score == 0
    finally:
        entity.discard_unpublished_runtime()


def test_high_elf_cantrip_scales_and_rolls_back_with_character_levels() -> None:
    state = AppliedOriginState(
        base_ability_scores=tuple((ability, 10) for ability in AbilityName),
        flexible_ability_bonuses=(
            (AbilityName.STRENGTH, 2),
            (AbilityName.DEXTERITY, 1),
        ),
        choices=(
            OriginChoiceSelection(
                "species_variant.high_elf.additional_language",
                (SrdLanguageId.DRACONIC.value,),
            ),
            OriginChoiceSelection(
                "species_variant.high_elf.wizard_cantrip",
                ("spell.fire_bolt",),
            ),
        ),
    )
    requests = _fighter_requests_to_five()[:1]
    entity = create_character(
        uuid4(),
        name="Aelar",
        species=Species.ELF,
        species_variant=SpeciesVariant.HIGH_ELF,
        background=Background.ADVENTURER,
        origin_state=state,
        initial_levels=resolve_initial_level_steps(state, requests),
    )
    try:
        fire_bolt = next(
            action for action in entity.registered_actions
            if action.behavior_id == "spell.fire_bolt"
            and action.provided_by_id
            == "species_variant.high_elf.wizard_cantrip"
        )
        assert fire_bolt.caster_level == 1
        source = entity.spellcasting.sources[fire_bolt.spellcasting_source_id]
        assert source.ability is AbilityName.INTELLIGENCE

        added = add_class_level(
            entity,
            ClassLevelRequest(CharacterClass.FIGHTER),
        )
        assert fire_bolt.caster_level == 2
        remove_last_level(entity, added.step_id)
        assert fire_bolt.caster_level == 1
    finally:
        entity.discard_unpublished_runtime()


def test_dragonborn_breath_is_direct_ancestry_data_and_level_scaled() -> None:
    state = AppliedOriginState(
        base_ability_scores=tuple((ability, 10) for ability in AbilityName),
        flexible_ability_bonuses=(
            (AbilityName.STRENGTH, 2),
            (AbilityName.DEXTERITY, 1),
        ),
        choices=(OriginChoiceSelection(
            "species.dragonborn.draconic_ancestry",
            (DragonbornAncestry.GREEN.value,),
        ),),
    )
    requests = _fighter_requests_to_five()[:1]
    entity = create_character(
        uuid4(),
        name="Viridax",
        species=Species.DRAGONBORN,
        background=Background.ADVENTURER,
        origin_state=state,
        initial_levels=resolve_initial_level_steps(state, requests),
    )
    try:
        breath = next(
            action for action in entity.registered_actions
            if isinstance(action, DragonbornBreathWeapon)
        )
        assert breath.behavior_id == "action.origin.dragonborn.breath_weapon"
        assert breath.provided_by_id == "species.dragonborn.breath_weapon"
        assert breath.ancestry is DragonbornAncestry.GREEN
        assert breath.damage_type is DamageType.POISON
        assert breath.breath_geometry is DragonbornBreathGeometry.CONE
        assert breath.save_ability is AbilityName.CONSTITUTION
        assert breath.damage_dice_count == 2
        assert entity.action_economy.get_resource_current(
            DRAGONBORN_BREATH_RESOURCE,
        ) == 1

        added = []
        for request in _fighter_requests_to_five()[1:]:
            added.append(add_class_level(entity, request))
        added.append(add_class_level(
            entity,
            ClassLevelRequest(
                CharacterClass.FIGHTER,
                choices=(ClassChoiceSelection(
                    "class.fighter.level_6.asi_or_feat",
                    ("ability.constitution:+2",),
                ),),
            ),
        ))
        assert breath.character_level == 6
        assert breath.damage_dice_count == 3
        remove_last_level(entity, added[-1].step_id)
        assert breath.character_level == 5
        assert breath.damage_dice_count == 2
    finally:
        entity.discard_unpublished_runtime()


def test_tiefling_infernal_legacy_is_level_gated_and_reversible() -> None:
    state = _origin_state_without_choices()
    requests = _fighter_requests_to_five()
    entity = create_character(
        uuid4(),
        name="Melech",
        species=Species.TIEFLING,
        background=Background.ADVENTURER,
        origin_state=state,
        initial_levels=resolve_initial_level_steps(state, requests),
    )
    feature_id = "species.tiefling.infernal_legacy"
    try:
        action_ids = {
            action.behavior_id
            for action in entity.registered_actions
            if action.provided_by_id == feature_id
        }
        assert action_ids == {"spell.thaumaturgy", "spell.darkness"}
        assert {
            handler.behavior_id
            for handler in entity.event_handlers.values()
            if handler.provided_by_id == feature_id
        } == {"reaction.spell.hellish_rebuke"}
        assert entity.action_economy.get_resource_current(
            "origin_innate_spell:tiefling:hellish_rebuke",
        ) == 1
        assert entity.action_economy.get_resource_current(
            "origin_innate_spell:tiefling:darkness",
        ) == 1

        remove_last_level(entity)
        assert not any(
            action.behavior_id == "spell.darkness"
            for action in entity.registered_actions
        )
        assert "origin_innate_spell:tiefling:darkness" not in (
            entity.action_economy.resources
        )
        remove_last_level(entity)
        remove_last_level(entity)
        assert not any(
            handler.behavior_id == "reaction.spell.hellish_rebuke"
            for handler in entity.event_handlers.values()
        )
        assert "origin_innate_spell:tiefling:hellish_rebuke" not in (
            entity.action_economy.resources
        )
    finally:
        entity.discard_unpublished_runtime()


def test_acolyte_holdings_commit_inside_the_single_character_birth_fact() -> None:
    entity = create_character(
        uuid4(),
        name="Iria",
        species=Species.HUMAN,
        background=Background.ACOLYTE,
        origin_state=_human_acolyte_state(),
    )
    try:
        assert tuple(
            item.semantic_key for item in entity.inventory.items.values()
        ) == (
            "gear.holy_symbol",
            "gear.prayer_book",
            "gear.incense",
            "gear.vestments",
            "gear.common_clothes",
        )
        incense = next(
            item
            for item in entity.inventory.items.values()
            if item.semantic_key == "gear.incense"
        )
        assert incense.stack_count == 5
        events = EventQueue.get_events_chronological()
        assert [event.event_type for event in events] == [EventType.ENTITY_CREATED]
        assert sorted(state.semantic_key for state in events[0].items) == sorted((
            "gear.holy_symbol",
            "gear.prayer_book",
            "gear.incense",
            "gear.vestments",
            "gear.common_clothes",
        ))
        assert set(events[0].inventory_item_uuids) == set(entity.inventory.items)
    finally:
        entity.discard_unpublished_runtime()
