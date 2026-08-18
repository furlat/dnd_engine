"""Observable class progression through direct entity composition."""

from uuid import uuid4

import pytest

from dnd.content.characters.character_builds import create_character
from dnd.content.characters.class_definitions import (
    CLASS_DEFINITIONS,
    SUBCLASS_DEFINITIONS,
    ClassLevelRequest,
)
from dnd.content.characters.class_level_content import (
    add_class_level,
    resolve_initial_level_steps,
)
from dnd.core.events.events_registry import EventQueue, EventType
from dnd.entities.entity_progression import remove_last_level
from dnd.types.abilities import AbilityName
from dnd.types.creatures import Background, Species
from dnd.types.languages import SrdLanguageId
from dnd.types.progression import (
    AppliedOriginState,
    CharacterClass,
    CharacterSubclass,
    ClassChoiceSelection,
    OriginChoiceSelection,
)


@pytest.fixture(autouse=True)
def _reset_event_history() -> None:
    EventQueue.reset()


def _human_state(
    *,
    primary: AbilityName,
    secondary: AbilityName,
) -> AppliedOriginState:
    scores = {
        ability: 10
        for ability in AbilityName
    }
    scores[primary] = 15
    scores[secondary] = 14
    bonuses = tuple(sorted(
        ((primary, 2), (secondary, 1)),
        key=lambda row: tuple(AbilityName).index(row[0]),
    ))
    return AppliedOriginState(
        base_ability_scores=tuple((ability, scores[ability]) for ability in AbilityName),
        flexible_ability_bonuses=bonuses,
        choices=(OriginChoiceSelection(
            "species.human.additional_language",
            (SrdLanguageId.ELVISH.value,),
        ),),
    )


def _create_with_first_level(
    state: AppliedOriginState,
    request: ClassLevelRequest,
):
    entity = create_character(
        uuid4(),
        name="Progression probe",
        species=Species.HUMAN,
        background=Background.ADVENTURER,
        origin_state=state,
        initial_levels=resolve_initial_level_steps(state, (request,)),
    )
    return entity


def _action_ids(entity) -> set[str]:
    return {
        action.behavior_id
        for action in entity.registered_actions
        if action.behavior_id is not None
    }


def test_every_authored_class_and_subclass_keeps_twenty_levels() -> None:
    assert set(CLASS_DEFINITIONS) == set(CharacterClass)
    assert set(SUBCLASS_DEFINITIONS) == set(CharacterSubclass)
    assert all(len(definition.levels) == 20 for definition in CLASS_DEFINITIONS.values())
    assert all(
        len(definition.levels) == 20
        for definition in SUBCLASS_DEFINITIONS.values()
    )


def test_fighter_levels_apply_and_remove_as_entity_transactions() -> None:
    state = _human_state(
        primary=AbilityName.STRENGTH,
        secondary=AbilityName.CONSTITUTION,
    )
    choice = ClassChoiceSelection
    entity = _create_with_first_level(state, ClassLevelRequest(
        CharacterClass.FIGHTER,
        choices=(
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
        ),
    ))
    try:
        add_class_level(entity, ClassLevelRequest(CharacterClass.FIGHTER))
        add_class_level(entity, ClassLevelRequest(
            CharacterClass.FIGHTER,
            choices=(choice(
                "class.fighter.level_3.subclass",
                ("subclass.fighter.champion",),
            ),),
        ))
        add_class_level(entity, ClassLevelRequest(
            CharacterClass.FIGHTER,
            choices=(choice(
                "class.fighter.level_4.asi_or_feat",
                ("ability.strength:+2",),
            ),),
        ))
        add_class_level(entity, ClassLevelRequest(CharacterClass.FIGHTER))

        assert len(entity.applied_class_levels) == 5
        assert entity.ability_scores.strength.ability_score.score == 19
        assert entity.has_feature("class_feature.extra_attack")
        assert "action.class.fighter.second_wind" in _action_ids(entity)
        assert "action.class.fighter.action_surge" in _action_ids(entity)
        assert [event.event_type for event in EventQueue.get_events_chronological()] == [
            EventType.ENTITY_CREATED,
            EventType.ENTITY_LEVEL_ADDED,
            EventType.ENTITY_LEVEL_ADDED,
            EventType.ENTITY_LEVEL_ADDED,
            EventType.ENTITY_LEVEL_ADDED,
        ]
        level_five_fact = EventQueue.get_events_by_type(
            EventType.ENTITY_LEVEL_ADDED,
        )[-1]
        assert dict(level_five_fact.ability_scores)[AbilityName.STRENGTH] == 19
        assert "class_feature.extra_attack" in level_five_fact.feature_ids
        assert level_five_fact.attacks_per_action == 2
        assert not hasattr(level_five_fact, "transform_ids")

        removed = remove_last_level(entity)
        assert removed.resulting_class_level == 5
        assert not entity.has_feature("class_feature.extra_attack")
        assert len(entity.applied_class_levels) == 4
    finally:
        entity.discard_unpublished_runtime()


def test_barbarian_berserker_frenzy_undo_restores_rage() -> None:
    state = _human_state(
        primary=AbilityName.STRENGTH,
        secondary=AbilityName.CONSTITUTION,
    )
    choice = ClassChoiceSelection
    entity = _create_with_first_level(state, ClassLevelRequest(
        CharacterClass.BARBARIAN,
        choices=(
            choice(
                "class.barbarian.first_class.starting_equipment",
                ("starting_equipment.barbarian.greataxe",),
            ),
            choice(
                "class.barbarian.proficiencies.skills",
                ("skill.athletics", "skill.survival"),
            ),
        ),
    ))
    try:
        add_class_level(entity, ClassLevelRequest(CharacterClass.BARBARIAN))
        add_class_level(entity, ClassLevelRequest(
            CharacterClass.BARBARIAN,
            choices=(choice(
                "class.barbarian.level_3.subclass",
                ("subclass.barbarian.berserker",),
            ),),
        ))

        assert "action.class.barbarian.frenzy" in _action_ids(entity)
        assert "action.class.barbarian.rage" not in _action_ids(entity)

        remove_last_level(entity)

        assert "action.class.barbarian.frenzy" not in _action_ids(entity)
        assert "action.class.barbarian.rage" in _action_ids(entity)
        assert len(entity.applied_class_levels) == 2
    finally:
        entity.discard_unpublished_runtime()


def test_sorcerer_spell_source_slots_learning_and_replacement_are_reversible() -> None:
    state = _human_state(
        primary=AbilityName.CHARISMA,
        secondary=AbilityName.CONSTITUTION,
    )
    choice = ClassChoiceSelection
    entity = _create_with_first_level(state, ClassLevelRequest(
        CharacterClass.SORCERER,
        choices=(
            choice(
                "class.sorcerer.first_class.starting_equipment",
                ("starting_equipment.sorcerer.quarterstaff",),
            ),
            choice(
                "class.sorcerer.proficiencies.skills",
                ("skill.arcana", "skill.deception"),
            ),
            choice(
                "class.sorcerer.level_1.subclass",
                ("subclass.sorcerer.draconic_bloodline",),
            ),
            choice(
                "class.sorcerer.level_1.cantrips",
                (
                    "spell.acid_splash",
                    "spell.fire_bolt",
                    "spell.light",
                    "spell.ray_of_frost",
                ),
            ),
            choice(
                "class.sorcerer.level_1.spell_known",
                ("spell.magic_missile", "spell.shield"),
            ),
            choice(
                "subclass.sorcerer.draconic_bloodline.level_1.ancestry",
                ("class_feature.sorcerer.draconic_ancestry.red",),
            ),
        ),
    ))
    try:
        add_class_level(entity, ClassLevelRequest(
            CharacterClass.SORCERER,
            choices=(
                choice(
                    "class.sorcerer.level_2.spell_known",
                    ("spell.burning_hands",),
                ),
                choice(
                    "class.sorcerer.level_2.spell_replacement",
                    ("spell.magic_missile->spell.charm_person",),
                ),
            ),
        ))

        source = next(iter(entity.spellcasting.sources.values()))
        assert (source.provider_id, source.provider_level) == ("class.sorcerer", 2)
        assert entity.action_economy.get_normal_spell_slot_capacities() == {1: 3}
        assert entity.health.max_hit_points_bonus.score == 2
        assert "spell.magic_missile" not in _action_ids(entity)
        assert {"spell.burning_hands", "spell.charm_person"} <= _action_ids(entity)
        level_fact = EventQueue.get_events_by_type(EventType.ENTITY_LEVEL_ADDED)[-1]
        assert level_fact.spell_sources == (
            (
                "class",
                "class.sorcerer",
                AbilityName.CHARISMA,
                2,
                1,
                "full_caster",
                "none",
            ),
        )
        assert {"spell.burning_hands", "spell.charm_person"} <= set(
            level_fact.known_spell_ids,
        )
        assert level_fact.reaction_spell_ids == ("spell.shield",)
        assert dict(level_fact.spell_slots)[1] == 3

        remove_last_level(entity)

        source = next(iter(entity.spellcasting.sources.values()))
        assert (source.provider_id, source.provider_level) == ("class.sorcerer", 1)
        assert entity.action_economy.get_normal_spell_slot_capacities() == {1: 2}
        assert entity.health.max_hit_points_bonus.score == 1
        assert "spell.magic_missile" in _action_ids(entity)
        assert "spell.burning_hands" not in _action_ids(entity)
        assert "spell.charm_person" not in _action_ids(entity)
    finally:
        entity.discard_unpublished_runtime()
