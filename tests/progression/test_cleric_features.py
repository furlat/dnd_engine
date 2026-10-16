"""Cleric class builds exercising native paid actions and owning Life handlers."""

from dataclasses import replace

from dnd.classes.cleric import TurnUndead, PreserveLife
from dnd.classes.divine import Turned
from dnd.content.characters.builds import create_character
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.entity import Entity
from dnd.types.character_progression import CharacterClass
from tests.progression.prepared_class_support import prepared_build
from tests.engine.test_roster_support_spells import game as game
from tests.engine.test_bg3_rank_one_two_spells import combatant
from tests.manual.spell_regression_support import force_save_result


def cleric(game, level):
    actor = create_character(
        replace(prepared_build(CharacterClass.CLERIC, level), faction="heroes")
    )
    game.deploy_entity(actor, (2, 2))
    Entity.update_all_entities_senses()
    return actor


def test_life_healing_source_bonus_and_committed_blessed_healer(game):
    actor = cleric(game, 6)
    ally = combatant(game, "Ally", (3, 2))
    actor.receive_damage(10, DamageType.FORCE, ally.uuid)
    ally.receive_damage(25, DamageType.FORCE, actor.uuid)
    action = next(
        action
        for action in actor.registered_actions
        if action.semantic_key == "spell.cure_wounds"
    )
    old_ally, old_self = ally.get_hp(), actor.get_hp()
    with fixed_dice_faces(4):
        result = action.instantiate(target_entity_uuid=ally.uuid).apply()
    assert result is not None and not result.canceled
    assert ally.get_hp() == old_ally + 9  # 4 + WIS2 + Disciple3.
    assert actor.get_hp() == old_self + 3
    assert actor.action_economy.spell_slot_1.normalized_score == 3
    actor.action_economy.reset_all_costs()
    ally.health.damage_taken = 0
    before = actor.get_hp()
    with fixed_dice_faces(4):
        action.instantiate(target_entity_uuid=ally.uuid).apply()
    assert actor.get_hp() == before


def test_preserve_life_uses_total_level_without_spell_healing_bonuses(game):
    actor = cleric(game, 6)
    ally = combatant(game, "Ally", (3, 2))
    undead = combatant(
        game, "Friendly undead", (4, 2), creature_type=CreatureType.UNDEAD
    )
    for target in (actor, ally, undead):
        target.receive_damage(25, DamageType.FORCE, actor.uuid)
    old = {target.uuid: target.get_hp() for target in (actor, ally, undead)}
    action = next(
        action
        for action in actor.registered_actions
        if isinstance(action, PreserveLife)
    )
    result = action.instantiate().apply()
    assert result is not None and not result.canceled
    assert ally.get_hp() == old[ally.uuid] + 18
    assert actor.get_hp() == old[actor.uuid] + 18
    assert undead.get_hp() == old[undead.uuid]
    assert actor.action_economy.resources["channel_divinity"].current == 1
    actor.on_short_rest()
    assert actor.action_economy.resources["channel_divinity"].current == 2


def test_supreme_healing_maximizes_spell_dice(game):
    actor = cleric(game, 17)
    ally = combatant(game, "Ally", (3, 2))
    ally.receive_damage(40, DamageType.FORCE, actor.uuid)
    old = ally.get_hp()
    action = next(
        action
        for action in actor.registered_actions
        if action.semantic_key == "spell.cure_wounds"
    )
    with fixed_dice_faces(1):
        result = action.instantiate(target_entity_uuid=ally.uuid).apply()
    assert result is not None and not result.canceled
    assert ally.get_hp() == old + 8 + actor.ability_scores.wisdom.modifier + 3


def test_turning_is_separate_from_fear_and_destroy_damage_does_not_end_new_turning(
    game,
):
    actor = cleric(game, 5)
    undead = combatant(game, "Undead", (3, 2), creature_type=CreatureType.UNDEAD)
    saved = combatant(game, "Saved undead", (4, 2), creature_type=CreatureType.UNDEAD)
    immune = combatant(game, "Turn immune", (5, 2), creature_type=CreatureType.UNDEAD)
    undead.add_static_condition_immunity("Frightened", "Fear immune")
    immune.add_static_condition_immunity("Turned", "Turn immune")
    force_save_result(undead, "wisdom", succeeds=False)
    force_save_result(saved, "wisdom", succeeds=True)
    force_save_result(immune, "wisdom", succeeds=False)
    old = {target.uuid: target.get_hp() for target in (undead, saved, immune)}
    action = next(
        action for action in actor.registered_actions if isinstance(action, TurnUndead)
    )
    with fixed_dice_faces(*([2] * 20)):
        result = action.instantiate().apply()
    assert result is not None and not result.canceled
    assert undead.get_hp() == old[undead.uuid] - 8
    assert any(
        isinstance(condition, Turned)
        for condition in undead.active_conditions_by_uuid.values()
    )
    assert saved.get_hp() == old[saved.uuid] and immune.get_hp() == old[immune.uuid]
    assert not any(
        isinstance(condition, Turned)
        for condition in saved.active_conditions_by_uuid.values()
    )
    undead.receive_damage(1, DamageType.FORCE, actor.uuid)
    assert not any(
        isinstance(condition, Turned)
        for condition in undead.active_conditions_by_uuid.values()
    )
