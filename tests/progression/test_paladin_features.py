"""Real Paladin builds exercise native paid actions, auras and exact cleanup."""

from dataclasses import replace

from dnd.classes.paladin import LayOnHands, TurnUnholy, PaladinAuraBenefit
from dnd.classes.divine import Turned
from dnd.conditions import Frightened, Charmed, Poisoned
from dnd.content.characters.builds import create_character
from dnd.content.characters.progression import remove_last_class_level
from dnd.core.condition_types import ConditionTag
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.geometry import grid_distance_feet
from dnd.entity import Entity
from dnd.types.character_progression import CharacterClass
from tests.progression.prepared_class_support import prepared_build
from tests.engine.test_roster_support_spells import game as game
from tests.engine.test_bg3_rank_one_two_spells import combatant
from tests.manual.spell_regression_support import force_save_result


def paladin(game, level):
    actor = create_character(
        replace(prepared_build(CharacterClass.PALADIN, level), faction="heroes")
    )
    game.deploy_entity(actor, (2, 2))
    Entity.update_all_entities_senses()
    return actor


def use(actor, kind, **parameters):
    template = next(
        action for action in actor.registered_actions if isinstance(action, kind)
    )
    return template.instantiate(**parameters).apply()


def test_lay_on_hands_modes_and_lesser_uses_only_paladin_level(game):
    actor = paladin(game, 4)
    ally = combatant(game, "Ally", (3, 2))
    ally.receive_damage(40, DamageType.FORCE, actor.uuid)
    before = ally.get_hp()
    result = use(actor, LayOnHands, target_entity_uuid=ally.uuid, mode="lesser")
    assert result is not None and not result.canceled
    assert ally.get_hp() == before + 8
    assert actor.action_economy.resources["lay_on_hands"].current == 3
    actor.action_economy.reset_all_costs()
    result = use(actor, LayOnHands, target_entity_uuid=ally.uuid, mode="greater")
    assert result is not None and not result.canceled
    assert ally.get_hp() == before + 24
    actor.action_economy.reset_all_costs()
    rejected = use(actor, LayOnHands, target_entity_uuid=ally.uuid, mode="cure")
    assert rejected is None or rejected.canceled
    assert actor.action_economy.actions.normalized_score == 1
    actor.on_long_rest()
    poison = Poisoned(source_entity_uuid=ally.uuid, target_entity_uuid=ally.uuid)
    ally.add_condition(poison)
    result = use(actor, LayOnHands, target_entity_uuid=ally.uuid, mode="cure")
    assert result is not None and not result.canceled
    assert poison.uuid not in ally.active_conditions_by_uuid


def test_protection_aura_moves_and_removal_preserves_other_spells(game):
    actor = paladin(game, 6)
    ally = combatant(game, "Ally", (3, 2))
    foe = combatant(game, "Foe", (5, 2), "foes")
    Entity.update_all_entities_senses()
    before = foe.saving_throw_bonus(None, "wisdom", None).normalized_score
    assert (
        ally.saving_throw_bonus(None, "wisdom", None).normalized_score
        == ally.ability_scores.wisdom.modifier + 1
    )
    assert foe.saving_throw_bonus(None, "wisdom", None).normalized_score == before
    Entity.commit_position_transfers(((actor, (14, 6), None),))
    assert (
        ally.saving_throw_bonus(None, "wisdom", None).normalized_score
        == ally.ability_scores.wisdom.modifier
    )
    Entity.commit_position_transfers(((actor, (2, 2), None),))
    assert (
        ally.saving_throw_bonus(None, "wisdom", None).normalized_score
        == ally.ability_scores.wisdom.modifier + 1
    )
    removed = remove_last_class_level(actor)
    assert removed is not None and paladin_level_count(actor) == 5
    assert (
        ally.saving_throw_bonus(None, "wisdom", None).normalized_score
        == ally.ability_scores.wisdom.modifier
    )
    assert not any(
        isinstance(condition, PaladinAuraBenefit)
        for condition in ally.active_conditions_by_uuid.values()
    )


def paladin_level_count(actor):
    return sum(
        level.class_id is CharacterClass.PALADIN for level in actor.applied_class_levels
    )


def test_turn_unholy_flees_without_damage_and_expires_after_three_recipient_turns(game):
    actor = paladin(game, 3)
    undead = combatant(
        game, "Undead", (3, 2), "foes", creature_type=CreatureType.UNDEAD
    )
    force_save_result(undead, "wisdom", succeeds=False)
    hp = undead.get_hp()
    with fixed_dice_faces(2):
        result = use(actor, TurnUnholy)
    assert result is not None and not result.canceled
    assert undead.get_hp() == hp and any(
        isinstance(c, Turned) for c in undead.active_conditions_by_uuid.values()
    )
    before = grid_distance_feet(actor.position, undead.position)
    undead.on_turn_start()
    assert grid_distance_feet(actor.position, undead.position) > before
    assert undead.action_economy.reactions.normalized_score == 0
    for _ in range(3):
        undead.on_turn_end()
    assert not any(
        isinstance(c, Turned) for c in undead.active_conditions_by_uuid.values()
    )


def test_devotion_and_courage_clear_control_and_keep_turned_independent(game):
    paladin(game, 10)
    ally = combatant(game, "Ally", (14, 6))
    foe = combatant(game, "Foe", (15, 6), "foes")
    charm = Charmed(source_entity_uuid=foe.uuid, target_entity_uuid=ally.uuid)
    fear = Frightened(source_entity_uuid=foe.uuid, target_entity_uuid=ally.uuid)
    ally.add_condition(charm)
    ally.add_condition(fear)
    Entity.commit_position_transfers(((ally, (3, 2), None),))
    assert (
        charm.uuid not in ally.active_conditions_by_uuid
        and fear.uuid not in ally.active_conditions_by_uuid
    )
    result = ally.add_condition(
        Frightened(source_entity_uuid=foe.uuid, target_entity_uuid=ally.uuid)
    )
    assert result is None or result.canceled
    result = ally.add_condition(
        Turned(source_entity_uuid=foe.uuid, target_entity_uuid=ally.uuid)
    )
    assert result is not None and not result.canceled


def test_divine_health_blocks_only_disease(game):
    actor = paladin(game, 3)
    disease = Poisoned(
        source_entity_uuid=actor.uuid,
        target_entity_uuid=actor.uuid,
        tags={ConditionTag.DISEASE},
    )
    rejected = actor.add_condition(disease)
    assert rejected is None or rejected.canceled
    poison = Poisoned(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid)
    accepted = actor.add_condition(poison)
    assert accepted is not None and not accepted.canceled
