"""Public build/level operations prove the prepared-class structural substrate."""

from dataclasses import replace

import pytest

from dnd.content.characters.builds import create_character
from dnd.content.characters.progression import add_class_level, remove_last_class_level
from dnd.content.characters.spellcasting_grants import class_casting_source
from dnd.core.base_actions import spell_slot_cost_type
from dnd.core.events import EventHandler, EventPhase, EventType, Trigger
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.character_progression import CharacterClass
from dnd.types.character_progression import FeatureToggleSelection
from tests.progression.prepared_class_support import prepared_build, prepared_level


@pytest.fixture(autouse=True)
def clean_runtime():
    reset_engine_runtime(grid_size=(8, 8))
    yield
    reset_engine_runtime()


@pytest.mark.parametrize(
    "class_id,die,ability,saves",
    [
        (CharacterClass.CLERIC, 8, "wisdom", ("wisdom", "charisma")),
        (CharacterClass.PALADIN, 10, "charisma", ("wisdom", "charisma")),
        (CharacterClass.WIZARD, 6, "intelligence", ("intelligence", "wisdom")),
    ],
)
def test_real_prepared_class_builds_and_twenty_level_roundtrip(
    class_id, die, ability, saves
):
    build = prepared_build(class_id, 20)
    actor = create_character(replace(build, class_levels=build.class_levels[:1]))
    assert actor.get_max_hp() == die + 2
    for name in saves:
        assert actor.saving_throws.get_saving_throw(name).proficiency_sources.sources
    for row in build.class_levels[1:]:
        add_class_level(actor, row)
    assert len(actor.health.hit_dices) == 20
    assert actor.get_max_hp() == die + 19 * (die // 2 + 1) + 20 * 3
    source = actor.spellcasting.sources.get(class_casting_source(actor, class_id))
    assert source.ability == ability and source.provider_level == 20
    assert source.maximum_spell_rank == (5 if class_id is CharacterClass.PALADIN else 9)
    assert actor.proficiency_bonus.score == 6
    for _ in range(19):
        remove_last_class_level(actor)
    assert len(actor.applied_class_levels) == 1
    assert actor.get_max_hp() == die + 2
    assert actor.action_economy.get_normal_spell_slot_capacities() == (
        {} if class_id is CharacterClass.PALADIN else {1: 2}
    )


def test_mixed_sources_share_one_slot_table_and_preserve_spending():
    actor = create_character(prepared_build(CharacterClass.CLERIC, 2))
    actor.action_economy.consume(spell_slot_cost_type(1), 1)
    add_class_level(
        actor, prepared_level(CharacterClass.WIZARD, actor.applied_class_levels)
    )
    assert actor.action_economy.get_normal_spell_slot_capacities() == {1: 4, 2: 2}
    assert actor.action_economy.spell_slot_value(1).normalized_score == 3
    cleric = actor.spellcasting.sources.get(
        class_casting_source(actor, CharacterClass.CLERIC)
    )
    wizard = actor.spellcasting.sources.get(
        class_casting_source(actor, CharacterClass.WIZARD)
    )
    assert (cleric.ability, wizard.ability) == ("wisdom", "intelligence")
    assert (cleric.maximum_spell_rank, wizard.maximum_spell_rank) == (1, 1)
    remove_last_class_level(actor)
    assert actor.action_economy.spell_slot_value(1).normalized_score == 2
    assert (
        actor.spellcasting.sources.get(
            class_casting_source(actor, CharacterClass.WIZARD)
        )
        is None
    )
    assert (
        actor.spellcasting.sources.get(
            class_casting_source(actor, CharacterClass.CLERIC)
        )
        == cleric
    )


def test_paladin_sole_and_multiclass_slot_rounding():
    actor = create_character(prepared_build(CharacterClass.PALADIN, 3))
    assert actor.action_economy.get_normal_spell_slot_capacities() == {1: 3}
    add_class_level(
        actor, prepared_level(CharacterClass.CLERIC, actor.applied_class_levels)
    )
    assert actor.action_economy.get_normal_spell_slot_capacities() == {1: 3}
    remove_last_class_level(actor)
    assert actor.action_economy.get_normal_spell_slot_capacities() == {1: 3}


def test_rejected_level_event_and_lost_handle_leave_character_unchanged():
    actor = create_character(prepared_build(CharacterClass.WIZARD, 2))
    old_levels = actor.applied_class_levels
    old_hp = actor.get_max_hp()
    old_slots = actor.action_economy.get_normal_spell_slot_capacities()

    def reject(event, context):
        return event.cancel(status_message="Rejected level")

    veto = EventHandler(
        source_entity_uuid=actor.uuid,
        name="Reject level",
        event_processor=reject,
        validation_only=True,
        trigger_conditions=[
            Trigger(
                event_type=EventType.ENTITY_LEVEL_ADDED,
                event_phase=EventPhase.EXECUTION,
                event_source_entity_uuid=actor.uuid,
            )
        ],
    )
    actor.add_event_handler(veto)
    with pytest.raises(ValueError):
        add_class_level(actor, prepared_level(CharacterClass.WIZARD, old_levels))
    actor.remove_event_handler(veto)
    receipt = actor.character_grant_receipt(old_levels[-1].step_id)
    feature, owner = receipt.chassis.feature_sources[0]
    actor.remove_feature_source(feature, owner)
    with pytest.raises(RuntimeError, match="feature ownership"):
        remove_last_class_level(actor)
    assert actor.applied_class_levels == old_levels
    assert actor.get_max_hp() == old_hp
    assert actor.action_economy.get_normal_spell_slot_capacities() == old_slots


@pytest.mark.parametrize(
    "first,second",
    [
        (CharacterClass.PALADIN, CharacterClass.FIGHTER),
        (CharacterClass.FIGHTER, CharacterClass.PALADIN),
    ],
)
def test_equivalent_fighting_style_is_rejected_in_both_class_orders(first, second):
    build = prepared_build(first, 2 if first is CharacterClass.PALADIN else 1)
    levels = build.class_levels
    for _ in range(2 if second is CharacterClass.PALADIN else 1):
        levels = (*levels, prepared_level(second, levels))
    levels = tuple(
        replace(
            row,
            choices=tuple(
                replace(
                    choice,
                    values=(
                        f"class_feature.{row.class_id.value.rsplit('.', 1)[1]}.fighting_style.dueling",
                    ),
                )
                if choice.choice_id.endswith("fighting_style")
                else choice
                for choice in row.choices
            ),
        )
        for row in levels
    )
    with pytest.raises(ValueError, match="Equivalent fighting style"):
        create_character(replace(build, class_levels=levels))


@pytest.mark.parametrize(
    "class_id,level,feature,enabled",
    [
        (CharacterClass.CLERIC, 8, "class_feature.cleric.divine_strike", False),
        (CharacterClass.WIZARD, 14, "class_feature.wizard.overchannel", True),
        (CharacterClass.PALADIN, 2, "class_feature.paladin.divine_smite", False),
    ],
)
def test_authored_feature_preferences_apply_to_actual_owned_handlers(
    class_id, level, feature, enabled
):
    actor = create_character(
        replace(
            prepared_build(class_id, level),
            feature_toggles=(
                FeatureToggleSelection(feature_id=feature, enabled=enabled),
            ),
        )
    )
    handlers = [
        handler
        for handler in actor.event_handlers.values()
        if handler.player_toggleable
        and (
            handler.semantic_key == feature
            or feature.endswith(".divine_smite")
            and handler.semantic_key == "reaction.class_feature.paladin.divine_smite"
        )
    ]
    assert handlers and all(handler.enabled is enabled for handler in handlers)


@pytest.mark.parametrize("suffix", ["great_weapon_fighting", "protection"])
def test_paladin_style_preferences_and_exact_handler_cleanup(suffix):
    build = prepared_build(CharacterClass.PALADIN, 2)
    feature = "class_feature.paladin.fighting_style." + suffix
    row = build.class_levels[-1]
    row = replace(
        row,
        choices=tuple(
            replace(choice, values=(feature,))
            if choice.choice_id.endswith("fighting_style")
            else choice
            for choice in row.choices
        ),
    )
    actor = create_character(
        replace(
            build,
            class_levels=(*build.class_levels[:-1], row),
            feature_toggles=(FeatureToggleSelection(feature, False),),
        )
    )
    handlers = [
        handler
        for handler in actor.event_handlers.values()
        if handler.player_toggleable
        and handler.behavior_binding.provided_by_id == feature
    ]
    assert len(handlers) == 1 and not handlers[0].enabled
    identity = handlers[0].uuid
    remove_last_class_level(actor)
    assert identity not in actor.event_handlers
