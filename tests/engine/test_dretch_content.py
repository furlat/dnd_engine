"""The finite Dretch composition participates in native combat and discovery."""

from uuid import uuid4

import pytest

from dnd.actions import AttackEvent
from dnd.actions_functional import execute_by_index, get_available_actions
from dnd.blocks.equipment import Weapon
from dnd.conditions import Poisoned
from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.base_block import SensesType
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.creature_types import CreatureType, DamageType, Size
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventPhase, EventQueue
from dnd.entity import Entity
from dnd.game import Game
from dnd.monsters.srd_roster import SRD_CREATURE_RECIPES_BY_ID
from dnd.runtime_reset import reset_engine_runtime


def materialize(creature_id: str, position: tuple[int, int],
                mode: CreaturePossessionMode = CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS) -> Entity:
    return materialize_creature(
        SRD_CREATURE_RECIPES_BY_ID[creature_id], runtime_entity_uuid=uuid4(),
        display_name=creature_id, faction=creature_id, position=position,
        deployment_role=CreatureDeploymentRole(role_id="tests.dretch"), possession_mode=mode,
    )


@pytest.mark.parametrize("mode", tuple(CreaturePossessionMode))
def test_dretch_keeps_native_fiend_facts_and_intrinsic_equipment(mode: CreaturePossessionMode) -> None:
    reset_engine_runtime(grid_size=(8, 8))
    actor = materialize("dretch", (2, 2), mode)
    assert actor.content_ref == SRD_CREATURE_RECIPES_BY_ID["dretch"].ref
    assert (actor.creature_type, actor.size) == (CreatureType.FIEND, Size.SMALL)
    # The established roster uses character hit-die conversion: 22, not the
    # printed SRD average 18. The source ledger explicitly records this limit.
    assert (actor.get_max_hp(), actor.ac_bonus().normalized_score) == (22, 11)
    assert actor.action_economy.movement.normalized_score == 20
    scores = actor.ability_scores
    assert tuple(score.ability_score.score for score in (
        scores.strength, scores.dexterity, scores.constitution,
        scores.intelligence, scores.wisdom, scores.charisma,
    )) == (11, 11, 12, 5, 8, 3)
    assert any(sense.sense_type is SensesType.DARKVISION and sense.range_feet == 60
               for sense in actor.senses.sense_modes)
    assert {item.item_id for item in actor.equipment.get_all_equipped_items()} == {
        "weapon.creature.dretch_bite", "weapon.creature.dretch_claws", "armor.creature.dretch_natural",
    }
    bite, claws = actor.equipment.weapon_melee_main, actor.equipment.weapon_melee_off
    assert bite is not None and isinstance(claws, Weapon)
    assert (bite.dice_numbers, bite.damage_dice, bite.damage_type) == (1, 6, DamageType.PIERCING)
    assert (claws.dice_numbers, claws.damage_dice, claws.damage_type) == (2, 4, DamageType.SLASHING)


@pytest.mark.parametrize("damage_type,loss", (
    (DamageType.COLD, 4), (DamageType.FIRE, 4), (DamageType.LIGHTNING, 4),
    (DamageType.POISON, 0), (DamageType.SLASHING, 8),
))
def test_dretch_native_damage_and_condition_defenses(damage_type: DamageType, loss: int) -> None:
    reset_engine_runtime(grid_size=(8, 8))
    actor, source = materialize("dretch", (2, 2)), materialize("commoner", (3, 2))
    game = Game()
    for entity in (actor, source):
        entity.compose_entity()
        game.deploy_entity(entity, entity.position)
    hp = actor.get_hp()
    actor.receive_damage(8, damage_type, source.uuid)
    assert actor.get_hp() == hp - loss
    actor.add_condition(Poisoned(source_entity_uuid=source.uuid, target_entity_uuid=actor.uuid),
                        check_save_throw=False)
    assert "Poisoned" not in actor.active_conditions


def test_discovered_dretch_multiattack_spends_one_action_for_bite_then_claws() -> None:
    reset_engine_runtime(grid_size=(8, 8))
    actor, target = materialize("dretch", (2, 2)), materialize("commoner", (3, 2))
    game = Game()
    for entity in (actor, target):
        entity.compose_entity()
        game.deploy_entity(entity, entity.position)
    Entity.update_all_entities_senses()
    available = get_available_actions(actor)
    attack = next(row for row in available.all_actions
                  if row.template_name == "Dretch Multiattack")
    destination = next(row for row in attack.valid_targets if row.position == target.position)
    cursor = EventQueue.event_cursor()
    # Two misses keep the target alive so both ordered native children run.
    with fixed_dice_faces(1, 1):
        root = execute_by_index(actor, attack.template_name, destination.index, available=available)
    assert root is not None and not root.canceled
    children = [event for _, event in EventQueue.iter_events_since(cursor)
                if isinstance(event, AttackEvent) and event.phase is EventPhase.COMPLETION]
    assert [event.weapon_slot for event in children] == [WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF]
    assert all(event.parent_lineage == root.lineage_uuid for event in children)
    assert actor.action_economy.actions.normalized_score == 0
    assert actor.action_economy.bonus_actions.normalized_score == 1
