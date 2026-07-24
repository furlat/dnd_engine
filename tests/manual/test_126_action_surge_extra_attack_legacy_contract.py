"""Active coverage restored from the archived Action Surge/Extra Attack suite.

Unlike the archived helper, these cases use the real ``ActionSurge`` resource
action rather than manufacturing an action modifier.  The four test docstrings
retain the one-for-one legacy coverage map, including the Surge-first order.
"""

from dnd.actions import Attack
from dnd.classes.fighter import (
    ActionSurge,
    ActionSurgeFeature,
    ExtraAttack,
    ExtraAttackFeature,
)
from dnd.core.equipment_types import WeaponSlot
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.utils import force_attack_miss, reset_combat_state, set_hp


def _reset_state() -> None:
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)


def _create_fighter(*, extra_attacks: int) -> Entity:
    fighter = create_skeleton(
        name="Action Surge Fighter",
        position=(5, 5),
        faction="heroes",
    )
    fighter.add_condition(
        ExtraAttackFeature(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=fighter.uuid,
            extra_attacks=extra_attacks,
        )
    )
    fighter.add_condition(
        ActionSurgeFeature(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=fighter.uuid,
            num_uses=1,
        )
    )
    fighter.on_turn_start()
    return fighter


def _create_target() -> Entity:
    target = create_goblin(
        name="Action Surge Target",
        position=(5, 6),
        faction="monsters",
    )
    set_hp(target, 500)
    return target


def _attack(fighter: Entity, target: Entity) -> None:
    event = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=False,
    ).apply()
    assert event is not None
    assert not event.canceled


def _extra_attack(fighter: Entity, target: Entity) -> None:
    event = ExtraAttack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=False,
    ).apply()
    assert event is not None
    assert not event.canceled


def _action_surge(fighter: Entity) -> None:
    event = ActionSurge(
        source_entity_uuid=fighter.uuid,
        template=False,
    ).apply()
    assert event is not None
    assert not event.canceled


def _spend_extra_batch(
    fighter: Entity,
    target: Entity,
    *,
    expected_count: int,
) -> int:
    resource = fighter.action_economy.resources["extra_attacks"]
    assert resource.current == expected_count
    for expected_remaining in range(expected_count - 1, -1, -1):
        _extra_attack(fighter, target)
        assert resource.current == expected_remaining
    return expected_count


def test_level_five_normal_attack_action_produces_two_attacks() -> None:
    """Legacy ``test_action_surge_extra_attack.py::test_normal_turn_two_attacks``."""
    _reset_state()
    fighter = _create_fighter(extra_attacks=1)
    target = _create_target()
    Entity.update_all_entities_senses()
    force_attack_miss(fighter)

    _attack(fighter, target)
    attack_count = 1 + _spend_extra_batch(
        fighter,
        target,
        expected_count=1,
    )

    assert attack_count == 2
    assert fighter.action_economy.actions.normalized_score == 0


def test_action_surge_refreshes_extra_attack_after_first_batch_is_spent() -> None:
    """Legacy ``test_action_surge_extra_attack.py::test_action_surge_interleaved``."""
    _reset_state()
    fighter = _create_fighter(extra_attacks=1)
    target = _create_target()
    Entity.update_all_entities_senses()
    force_attack_miss(fighter)

    _attack(fighter, target)
    attack_count = 1 + _spend_extra_batch(
        fighter,
        target,
        expected_count=1,
    )
    _action_surge(fighter)
    _attack(fighter, target)
    attack_count += 1 + _spend_extra_batch(
        fighter,
        target,
        expected_count=1,
    )

    assert attack_count == 4
    assert fighter.action_economy.actions.normalized_score == 0
    assert fighter.action_economy.resources["action_surge"].current == 0


def test_action_surge_first_accumulates_both_pending_extra_attack_batches() -> None:
    """Legacy ``test_action_surge_extra_attack.py::test_action_surge_first``."""
    _reset_state()
    fighter = _create_fighter(extra_attacks=1)
    target = _create_target()
    Entity.update_all_entities_senses()
    force_attack_miss(fighter)

    _action_surge(fighter)
    assert fighter.action_economy.actions.normalized_score == 2
    _attack(fighter, target)
    assert fighter.action_economy.resources["extra_attacks"].current == 1
    _attack(fighter, target)
    assert fighter.action_economy.resources["extra_attacks"].current == 2
    attack_count = 2 + _spend_extra_batch(
        fighter,
        target,
        expected_count=2,
    )

    assert attack_count == 4
    assert fighter.action_economy.actions.normalized_score == 0


def test_level_eleven_action_surge_produces_two_three_attack_batches() -> None:
    """Legacy ``test_action_surge_extra_attack.py::test_level_11_with_action_surge``."""
    _reset_state()
    fighter = _create_fighter(extra_attacks=2)
    target = _create_target()
    Entity.update_all_entities_senses()
    force_attack_miss(fighter)

    _attack(fighter, target)
    attack_count = 1 + _spend_extra_batch(
        fighter,
        target,
        expected_count=2,
    )
    _action_surge(fighter)
    _attack(fighter, target)
    attack_count += 1 + _spend_extra_batch(
        fighter,
        target,
        expected_count=2,
    )

    assert attack_count == 6
    assert fighter.action_economy.actions.normalized_score == 0
    assert fighter.action_economy.resources["extra_attacks"].current == 0
