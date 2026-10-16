"""Finite Divine Intervention branches through actual paid class actions."""

from dataclasses import replace
import pytest

from dnd.classes.divine_intervention import (
    SunderHeretical,
    OpulentRevival,
    ArmThyServant,
    GoldenGenerosity,
    INTERVENTION_ID,
)
from dnd.content.characters.builds import create_character
from dnd.content.characters.progression import remove_last_class_level, add_class_level
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.gridmap import get_map
from dnd.core.life_types import LifeState
from dnd.core.events import EventHandler, EventType, EventPhase, Trigger
from dnd.spells.transmutation import Haste, HasteEffect
from dnd.core.equipment_types import WeaponSlot
from dnd.entity import Entity
from dnd.items.divine_rewards import DevoteesMace, HealingIncense
from dnd.items.divine_rewards import build_devotees_mace
from dnd.types.character_progression import CharacterClass
from tests.progression.prepared_class_support import prepared_build, prepared_level
from tests.engine.test_roster_support_spells import game as game
from tests.engine.test_bg3_rank_one_two_spells import combatant
from tests.manual.spell_regression_support import force_save_result


def cleric(game, *, used=()):
    actor = create_character(
        replace(
            prepared_build(CharacterClass.CLERIC, 10),
            faction="heroes",
            permanent_feature_uses=used,
        )
    )
    game.deploy_entity(actor, (2, 2))
    Entity.update_all_entities_senses()
    return actor


def use(actor, kind):
    return (
        next(action for action in actor.registered_actions if isinstance(action, kind))
        .instantiate()
        .apply()
    )


def test_sunder_paid_once_uses_radiant_half_save_and_explicit_rebuild_state(game):
    actor = cleric(game)
    enemy = combatant(game, "Enemy", (4, 2), "foes")
    saved = combatant(game, "Saved enemy", (5, 2), "foes")
    ally = combatant(game, "Ally", (3, 2))
    force_save_result(enemy, "wisdom", succeeds=False)
    force_save_result(saved, "wisdom", succeeds=True)
    before = {target.uuid: target.get_hp() for target in (enemy, saved, ally)}
    with fixed_dice_faces(*([2] * 30)):
        result = use(actor, SunderHeretical)
    assert result is not None and not result.canceled
    assert enemy.get_hp() == before[enemy.uuid] - 16
    assert (
        saved.get_hp() == before[saved.uuid] - 8 and ally.get_hp() == before[ally.uuid]
    )
    assert actor.permanent_feature_uses == (INTERVENTION_ID,)
    actor.on_long_rest()
    assert actor.action_economy.resources["divine_intervention"].current == 0
    assert use(actor, ArmThyServant) is None
    rebuilt = create_character(
        replace(
            prepared_build(CharacterClass.CLERIC, 10),
            permanent_feature_uses=actor.permanent_feature_uses,
        )
    )
    assert rebuilt.action_economy.resources["divine_intervention"].current == 0


def test_opulent_preserves_spent_action_and_durations_and_does_not_make_dead_full_hp(
    game,
):
    actor = cleric(game)
    ally = create_character(
        replace(prepared_build(CharacterClass.PALADIN, 2), faction="heroes")
    )
    game.deploy_entity(ally, (3, 2))
    dead = create_character(
        replace(prepared_build(CharacterClass.WIZARD, 2), faction="heroes")
    )
    dead.is_player_companion = True
    game.deploy_entity(dead, (4, 2))
    ally.receive_damage(5, DamageType.FORCE, actor.uuid)
    ally.action_economy.consume("spell_slot_1", 1)
    ally.action_economy.consume_resource("lay_on_hands", 2)
    ally.action_economy.consume("bonus_actions", 1)
    caster = combatant(game, "Haste caster", (2, 3))
    result = Haste(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid).apply()
    assert result is not None and not result.canceled
    haste = next(
        c for c in ally.active_conditions_by_uuid.values() if isinstance(c, HasteEffect)
    )
    duration = haste.snapshot_duration()
    concentration_ids = set(caster.active_conditions_by_uuid)
    dead.receive_damage(1000, DamageType.FORCE, actor.uuid)
    assert dead.health.life_state is LifeState.DEAD
    result = use(actor, OpulentRevival)
    assert result is not None and not result.canceled
    assert actor.action_economy.actions.normalized_score == 0
    assert (
        ally.get_hp() == ally.get_max_hp()
        and ally.action_economy.spell_slot_1.normalized_score == 2
    )
    assert ally.action_economy.resources["lay_on_hands"].current == 3
    assert ally.action_economy.bonus_actions.normalized_score == 0
    assert (
        dead.health.life_state is LifeState.ALIVE
        and dead.get_hp() == dead.get_max_hp() // 2
    )
    assert actor.action_economy.resources["divine_intervention"].current == 0
    assert haste.applied and haste.snapshot_duration() == duration
    assert set(caster.active_conditions_by_uuid) == concentration_ids


def test_arm_reward_is_real_transferable_mace_with_item_owned_healing_charge(game):
    actor = cleric(game)
    result = use(actor, ArmThyServant)
    assert result is not None and not result.canceled
    mace = actor.equipment.weapon_melee_main
    assert isinstance(mace, DevoteesMace) and mace.attack_bonus.normalized_score == 3
    actor.receive_damage(12, DamageType.FORCE, actor.uuid)
    action = next(
        action
        for action in mace.get_use_actions(actor.uuid)
        if isinstance(action, HealingIncense)
    )
    result = action.instantiate().apply()
    assert result is not None and not result.canceled and mace.charges == 0
    before = actor.get_hp()
    with fixed_dice_faces(2):
        actor.on_turn_start()
    assert actor.get_hp() == before + 2  # Item heal receives no Life spell bonuses.
    removed = remove_last_class_level(actor)
    assert removed is not None and isinstance(
        actor.equipment.weapon_melee_main, DevoteesMace
    )
    actor.on_long_rest()
    assert mace.charges == 1
    ally = combatant(game, "New holder", (3, 2))
    assert actor.unequip_item(WeaponSlot.MELEE_MAIN) is mace
    assert ally.loot_item(mace) and ally.equip_item(mace.uuid, WeaponSlot.MELEE_MAIN)
    action = next(
        action
        for action in mace.get_use_actions(ally.uuid)
        if isinstance(action, HealingIncense)
    )
    assert not action.instantiate().apply().canceled and mace.charges == 0


def test_generosity_creates_permanent_native_chest_with_exact_seven_potions(game):
    actor = cleric(game)
    result = use(actor, GoldenGenerosity)
    assert result is not None and not result.canceled
    chest = next(
        BaseBlock.get(identity)
        for identity in get_map().get_all_object_positions()
        if BaseBlock.get(identity).name == "Golden Generosity"
    )
    potions = tuple(chest.get_storage_block().items.values())
    assert sum(item.stack_count for item in potions) == 7
    healing = next(
        item for item in potions if item.item_id == "consumable.healing_potion"
    )
    assert healing.stack_count == 4
    actor.receive_damage(30, DamageType.FORCE, actor.uuid)
    assert actor.loot_item(healing)
    actor.action_economy.reset_all_costs()
    before = actor.get_hp()
    action = healing.get_use_actions(actor.uuid)[0]
    with fixed_dice_faces(1, 2, 3, 4):
        result = action.instantiate().apply()
    assert result is not None and not result.canceled
    assert actor.get_hp() == before + 14
    assert healing.stack_count == 3
    actor.on_long_rest()
    assert get_map().get_object_position(chest.uuid) is not None


def test_permanent_intervention_use_survives_removing_and_readding_level_ten(game):
    actor = cleric(game)
    assert not use(actor, ArmThyServant).canceled
    row = remove_last_class_level(actor)
    assert row is not None
    add_class_level(
        actor, prepared_level(CharacterClass.CLERIC, actor.applied_class_levels)
    )
    assert actor.permanent_feature_uses == (INTERVENTION_ID,)
    assert actor.action_economy.resources["divine_intervention"].current == 0
    actor.on_short_rest()
    actor.on_long_rest()
    assert use(actor, GoldenGenerosity) is None


def test_opulent_does_not_revive_a_corpse_whose_tile_becomes_occupied_after_admission(
    game,
):
    actor = cleric(game)
    corpse = create_character(
        replace(prepared_build(CharacterClass.WIZARD, 2), faction="heroes")
    )
    corpse.is_player_companion = True
    game.deploy_entity(corpse, (4, 2))
    corpse.receive_damage(1000, DamageType.FORCE, actor.uuid)

    def block(event, _):
        combatant(game, "Late blocker", (4, 2), "foes")

    handler = EventHandler(
        source_entity_uuid=actor.uuid,
        name="World changed after paid costs",
        event_processor=block,
        trigger_conditions=[
            Trigger(
                event_type=EventType.ACTION_COSTS_COMMITTED,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=actor.uuid,
            )
        ],
    )
    actor.add_event_handler(handler)
    result = use(actor, OpulentRevival)
    assert result is not None and not result.canceled
    assert corpse.health.life_state is LifeState.DEAD
    assert actor.action_economy.resources["divine_intervention"].current == 0


def test_rejected_mace_inventory_admission_does_not_spend_permanent_use(game):
    actor = cleric(game)
    actor.inventory.max_slots = 0
    result = use(actor, ArmThyServant)
    assert result is not None and result.canceled
    assert actor.permanent_feature_uses == ()
    assert actor.action_economy.resources["divine_intervention"].current == 1
    assert actor.action_economy.actions.normalized_score == 1
    assert not any(
        isinstance(item, DevoteesMace) for item in actor.inventory.items.values()
    )


def test_earlier_cost_observer_failure_cannot_reopen_intervention_after_level_removal(
    game,
):
    actor = create_character(
        replace(prepared_build(CharacterClass.CLERIC, 9), faction="heroes")
    )
    game.deploy_entity(actor, (2, 2))

    def fail(event, _):
        raise RuntimeError("Committed cost observer failed")

    handler = EventHandler(
        source_entity_uuid=actor.uuid,
        name="Earlier committed cost observer",
        event_processor=fail,
        trigger_conditions=[
            Trigger(
                event_type=EventType.ACTION_COSTS_COMMITTED,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=actor.uuid,
            )
        ],
    )
    actor.add_event_handler(handler)
    add_class_level(
        actor, prepared_level(CharacterClass.CLERIC, actor.applied_class_levels)
    )
    with pytest.raises(RuntimeError, match="Committed cost observer failed"):
        use(actor, ArmThyServant)
    assert actor.permanent_feature_uses == (INTERVENTION_ID,)
    actor.remove_event_handler(handler)
    remove_last_class_level(actor)
    add_class_level(
        actor, prepared_level(CharacterClass.CLERIC, actor.applied_class_levels)
    )
    assert actor.action_economy.resources["divine_intervention"].current == 0


def test_native_item_retirement_releases_its_exact_authored_use_templates(game):
    actor = cleric(game)
    mace = build_devotees_mace(actor.uuid)
    identity = mace.use_action_templates[0].uuid
    assert BaseObject.get(identity) is not None
    assert mace.retire()
    assert BaseBlock.get(mace.uuid) is None and BaseObject.get(identity) is None
