"""Native retained spell and item packets obey their caster's owning features."""

from dataclasses import replace
from uuid import uuid4

import pytest

from dnd.actions import Attack, SpellAction
from dnd.content.characters.builds import create_character
from dnd.content.characters.progression import remove_last_class_level
from dnd.content.characters.spellcasting_grants import change_prepared_spells
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.entity import Entity
from dnd.spells.evocation import FlameBlade, Moonbeam
from dnd.spells.necromancy import VampiricTouchStrike
from dnd.types.character_progression import (
    CharacterClass,
    PreparedSpellSelection,
    Species,
)
from tests.engine.test_bg3_rank_one_two_spells import combatant
from tests.engine.test_roster_support_spells import game as game
from tests.manual.spell_regression_support import force_save_result
from tests.progression.prepared_class_support import prepared_build, prepared_level


def wizard(game, level, *, prepared=(), **build_changes):
    actor = create_character(
        replace(
            prepared_build(CharacterClass.WIZARD, level),
            faction="heroes",
            scribed_spell_ids=prepared,
            prepared_spells=(
                PreparedSpellSelection("class.wizard.spellcasting", prepared),
            ),
            **build_changes,
        )
    )
    game.deploy_entity(actor, (2, 2))
    Entity.update_all_entities_senses()
    return actor


def cast_prepared(actor, spell_id, rank, target=None):
    template = next(
        action
        for action in actor.registered_actions
        if isinstance(action, SpellAction) and action.semantic_key == spell_id
    )
    variant = next(
        variant
        for variant in template.get_discovery_variants(actor)
        if variant.cast_at_level == rank and variant.cast_cost_grant_id is None
    )
    result = variant.model_copy(
        deep=True,
        update={
            "uuid": uuid4(),
            "template": False,
            "use_register": False,
            "target_entity_uuid": target.uuid if target is not None else None,
        },
    ).apply()
    assert result is not None and not result.canceled
    return result


def set_overchannel(actor, enabled):
    handler = next(
        handler
        for handler in actor.event_handlers.values()
        if handler.semantic_key == "class_feature.wizard.overchannel"
    )
    assert actor.set_handler_enabled_by_uuid(handler.uuid, enabled)


def test_initial_moonbeam_protects_ally_before_save_and_still_hurts_enemy(game):
    actor = wizard(game, 10)
    ally = combatant(game, "Ally", (4, 2))
    enemy = combatant(game, "Enemy", (6, 2), "foes")
    ally_hp = ally.get_hp()
    cursor = EventQueue.event_cursor()

    result = Moonbeam(
        source_entity_uuid=actor.uuid,
        end_position=ally.position,
        alt_skip_slot=True,
    ).apply()

    assert result is not None and not result.canceled
    assert ally.get_hp() == ally_hp
    assert not any(
        event.event_type is EventType.SAVING_THROW
        and event.target_entity_uuid == ally.uuid
        for _, event in EventQueue.iter_events_since(cursor)
    )

    actor.action_economy.reset_all_costs()
    force_save_result(enemy, "constitution", succeeds=False)
    enemy_hp = enemy.get_hp()
    with fixed_dice_faces(5, 2, 2):
        result = Moonbeam(
            source_entity_uuid=actor.uuid,
            end_position=enemy.position,
            alt_skip_slot=True,
        ).apply()

    assert result is not None and not result.canceled
    assert enemy.get_hp() == enemy_hp - 4 - actor.ability_scores.intelligence.modifier


def test_flame_blade_native_spell_attack_receives_empowered_evocation(game):
    actor = wizard(game, 10)
    enemy = combatant(game, "Enemy", (3, 2), "foes")
    result = FlameBlade(source_entity_uuid=actor.uuid, alt_skip_slot=True).apply()
    assert result is not None and not result.canceled
    actor.action_economy.reset_all_costs()
    enemy_hp = enemy.get_hp()

    with fixed_dice_faces(15, 2, 2, 2):
        result = Attack(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=enemy.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    assert result is not None and not result.canceled
    assert enemy.get_hp() == enemy_hp - 6 - actor.ability_scores.intelligence.modifier


def test_overchanneled_fire_shield_maximizes_retaliation_without_another_use(game):
    actor = wizard(game, 14, prepared=("spell.fire_shield",))
    enemy = combatant(game, "Enemy", (3, 2), "foes")
    set_overchannel(actor, True)
    cast_prepared(actor, "spell.fire_shield", 4)
    assert actor.spellcasting.overchannel_uses == 1
    enemy_hp = enemy.get_hp()

    with fixed_dice_faces(15, *([2] * 20)):
        result = Attack(
            source_entity_uuid=enemy.uuid,
            target_entity_uuid=actor.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    assert result is not None and not result.canceled
    assert enemy.get_hp() == enemy_hp - 16 - actor.ability_scores.intelligence.modifier
    assert actor.spellcasting.overchannel_uses == 1


@pytest.mark.parametrize("selected", [False, True])
def test_repeat_survives_unchanged_preparation_and_keeps_original_overchannel_choice(
    game, selected
):
    selection = PreparedSpellSelection(
        "class.wizard.spellcasting", ("spell.vampiric_touch",)
    )
    actor = wizard(game, 14, prepared=selection.spell_ids)
    enemy = combatant(game, "Enemy", (3, 2), "foes")
    set_overchannel(actor, selected)
    enemy_hp = enemy.get_hp()
    with fixed_dice_faces(15, 2, 2, 2):
        cast_prepared(actor, "spell.vampiric_touch", 3, enemy)
    expected_damage = 18 if selected else 6
    assert enemy.get_hp() == enemy_hp - expected_damage

    change_prepared_spells(actor, selection)
    repeat = next(
        action
        for action in actor.registered_actions
        if isinstance(action, VampiricTouchStrike)
    )
    set_overchannel(actor, not selected)
    actor.action_economy.reset_all_costs()
    actor_hp = actor.get_hp()
    with fixed_dice_faces(15, 2, 2, 2):
        result = repeat.instantiate(target_entity_uuid=enemy.uuid).apply()

    assert result is not None and not result.canceled
    assert enemy.get_hp() == enemy_hp - 2 * expected_damage
    assert actor.spellcasting.overchannel_uses == int(selected)
    assert actor.get_hp() == actor_hp


def test_retained_repeat_keeps_original_casting_ability_after_source_removal(game):
    build = prepared_build(CharacterClass.CLERIC, 4)
    fourth = build.class_levels[-1]
    choices = tuple(
        replace(choice, values=("ability_score.intelligence.2",))
        if choice.choice_id.endswith(".asi_or_feat")
        else choice
        for choice in fourth.choices
    )
    levels = (*build.class_levels[:-1], replace(fourth, choices=choices))
    levels = (*levels, prepared_level(CharacterClass.WIZARD, levels))
    actor = create_character(
        replace(
            build,
            class_levels=levels,
            faction="heroes",
            scribed_spell_ids=("spell.vampiric_touch",),
            prepared_spells=(
                PreparedSpellSelection(
                    "class.wizard.spellcasting", ("spell.vampiric_touch",)
                ),
            ),
        )
    )
    game.deploy_entity(actor, (2, 2))
    enemy = combatant(game, "Enemy", (3, 2), "foes")
    with fixed_dice_faces(15, 2, 2, 2):
        cast_prepared(actor, "spell.vampiric_touch", 3, enemy)

    remove_last_class_level(actor)
    assert not any(
        source.provider_id == "class.wizard"
        for source in actor.spellcasting.sources.values()
    )
    assert (
        actor.ability_scores.intelligence.modifier
        != actor.ability_scores.wisdom.modifier
    )
    actor.action_economy.reset_all_costs()
    repeat = next(
        action
        for action in actor.registered_actions
        if isinstance(action, VampiricTouchStrike)
    )
    enemy_hp = enemy.get_hp()
    with fixed_dice_faces(15, 2, 2, 2):
        result = repeat.instantiate(target_entity_uuid=enemy.uuid).apply()

    assert result is not None and not result.canceled
    assert result.dice_roll.bonus == (
        actor.proficiency_bonus.normalized_score
        + actor.ability_scores.intelligence.modifier
    )
    assert enemy.get_hp() == enemy_hp - 6


@pytest.mark.parametrize("saved", [False, True])
def test_tiefling_rebuke_receives_empowered_before_actual_save_half(game, saved):
    actor = wizard(game, 10, species=Species.TIEFLING, origin_choices=())
    enemy = combatant(game, "Enemy", (3, 2), "foes")
    force_save_result(enemy, "dexterity", succeeds=saved)
    enemy_hp = enemy.get_hp()

    with fixed_dice_faces(5, 2, 2, 2):
        actor.receive_damage(1, DamageType.FORCE, enemy.uuid)

    raw = 6 + actor.ability_scores.intelligence.modifier
    assert enemy.get_hp() == enemy_hp - (raw // 2 if saved else raw)
    assert actor.action_economy.reactions.normalized_score == 0


def test_cost_observer_failure_still_records_accepted_overchannel_use(game):
    actor = wizard(game, 14, prepared=("spell.magic_missile",))
    enemy = combatant(game, "Enemy", (4, 2), "foes")
    set_overchannel(actor, True)

    def failing_observer(event, source_uuid):
        raise RuntimeError("Accepted-cost observer failed")

    observer = EventHandler(
        source_entity_uuid=actor.uuid,
        name="Accepted-cost observer",
        trigger_conditions=[
            Trigger(
                event_type=EventType.ACTION_COSTS_COMMITTED,
                event_phase=EventPhase.EFFECT,
            )
        ],
        event_processor=failing_observer,
    )
    actor.add_event_handler(observer)
    remaining_slots = actor.action_economy.spell_slot_1.normalized_score

    with pytest.raises(Exception):
        cast_prepared(actor, "spell.magic_missile", 1, enemy)

    assert actor.action_economy.actions.normalized_score == 0
    assert actor.action_economy.spell_slot_1.normalized_score == remaining_slots - 1
    assert actor.spellcasting.overchannel_uses == 1
