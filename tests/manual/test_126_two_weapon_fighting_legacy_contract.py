"""Active coverage restored from ``to_archive/examples/test_two_weapon_fighting.py``.

Each test maps to one archived case and asserts state directly instead of
returning booleans (which made the legacy file emit pytest warnings).
"""

from uuid import UUID, uuid4

import pytest

from dnd.actions.standard import (
    Attack,
)
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.equipment import (
    Weapon,
)
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.classes.fighter import (
    twf_off_hand_melee_ability_bonus,
    twf_off_hand_ranged_ability_bonus,
)
from dnd.types.equipment import WeaponProperty, WeaponSlot
from dnd.core.events.resolution_events import (
    Range,
    RangeType,
)
from dnd.core.gridmap import get_map
from dnd.types.damage import DamageType
from dnd.core.modifiers import ContextualNumericalModifier
from dnd.core.values import ModifiableValue
from dnd.entities.entity import Entity, EntityConfig
from tests.engine.support import create_test_entity, create_test_monster
from tests.engine.support import force_attack_miss, reset_combat_state, set_hp


def _reset_state() -> None:
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)


def _create_light_dagger(source_uuid: UUID) -> Weapon:
    return Weapon(
        source_entity_uuid=source_uuid,
        name="Legacy Light Dagger",
        damage_dice=4,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        properties=[WeaponProperty.LIGHT, WeaponProperty.FINESSE],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=source_uuid,
            base_value=0,
            value_name="Legacy Light Dagger Attack Bonus",
        ),
    )


def _create_non_light_sword(source_uuid: UUID) -> Weapon:
    return Weapon(
        source_entity_uuid=source_uuid,
        name="Legacy Non-Light Sword",
        damage_dice=8,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        properties=[],
        range=Range(type=RangeType.REACH, normal=5),
        attack_bonus=ModifiableValue.create(
            source_entity_uuid=source_uuid,
            base_value=0,
            value_name="Legacy Non-Light Sword Attack Bonus",
        ),
    )


def _equip_off_hand_dagger(entity: Entity) -> Weapon:
    dagger = _create_light_dagger(entity.uuid)
    entity.equipment.equip(dagger, WeaponSlot.MELEE_OFF)
    return dagger


def _damage_bonus(
    entity: Entity,
    target: Entity,
    slot: WeaponSlot,
) -> int:
    damages = entity.get_damages(slot, target.uuid)
    assert damages
    assert damages[0].damage_bonus is not None
    return damages[0].damage_bonus.normalized_score


def _apply_two_weapon_style(
    entity: Entity,
) -> tuple[tuple[ModifiableValue, UUID], ...]:
    handles: list[tuple[ModifiableValue, UUID]] = []
    for value, callable_ in (
        (
            entity.equipment.off_hand_melee_ability_bonus,
            twf_off_hand_melee_ability_bonus,
        ),
        (
            entity.equipment.off_hand_ranged_ability_bonus,
            twf_off_hand_ranged_ability_bonus,
        ),
    ):
        modifier = ContextualNumericalModifier(
            name="Two-Weapon Fighting fixture",
            callable=callable_,
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
        )
        value.self_contextual.add_value_modifier(modifier)
        handles.append((value, modifier.uuid))
    return tuple(handles)


def _create_finesse_actor(
    *,
    strength: int,
    dexterity: int,
) -> Entity:
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=strength),
            dexterity=AbilityConfig(ability_score=dexterity),
            constitution=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(
            hit_dices=[
                HitDiceConfig(
                    hit_dice_value=8,
                    hit_dice_count=2,
                    mode="maximums",
                )
            ]
        ),
        position=(0, 0),
        faction="heroes",
    )
    return create_test_entity(
        name="Legacy Finesse Fighter",
        config=config,
        entity_kind_id="test.finesse_fighter",
        source_id=uuid4(),
    )


def test_only_light_weapons_are_eligible_for_melee_off_hand() -> None:
    """Legacy ``test_two_weapon_fighting.py::test_light_weapon_requirement``."""
    _reset_state()
    attacker = create_test_monster("monster.goblin", name="Off-Hand Tester", position=(0, 0))
    non_light = _create_non_light_sword(attacker.uuid)

    with pytest.raises(ValueError, match="LIGHT"):
        attacker.equipment.equip(non_light, WeaponSlot.MELEE_OFF)

    light = _equip_off_hand_dagger(attacker)
    assert attacker.equipment.weapon_melee_off is light


def test_off_hand_attack_uses_bonus_action_not_action() -> None:
    """Legacy ``test_two_weapon_fighting.py::test_off_hand_costs_bonus_action``."""
    _reset_state()
    attacker = create_test_monster("monster.goblin", name="Cost Tester", position=(0, 0))
    target = create_test_monster("monster.goblin", name="Cost Target", position=(1, 0))
    _equip_off_hand_dagger(attacker)

    main = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=False,
    )
    off = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_OFF,
        template=False,
    )

    assert [(cost.cost_type, cost.cost) for cost in main.costs] == [
        ("actions", 1)
    ]
    assert [(cost.cost_type, cost.cost) for cost in off.costs] == [
        ("bonus_actions", 1)
    ]


def test_off_hand_damage_omits_ability_modifier_without_style() -> None:
    """Legacy ``test_two_weapon_fighting.py::test_off_hand_no_ability_modifier``."""
    _reset_state()
    attacker = create_test_monster("monster.goblin", name="Damage Tester", position=(0, 0))
    target = create_test_monster("monster.goblin", name="Damage Target", position=(1, 0))
    _equip_off_hand_dagger(attacker)
    Entity.materialize_all_navigation()

    main_bonus = _damage_bonus(attacker, target, WeaponSlot.MELEE_MAIN)
    off_bonus = _damage_bonus(attacker, target, WeaponSlot.MELEE_OFF)

    assert main_bonus == attacker.ability_scores.dexterity.modifier
    assert off_bonus == 0


def test_two_weapon_round_spends_one_action_and_one_bonus_action() -> None:
    """Legacy ``test_two_weapon_fighting.py::test_full_two_weapon_combat``."""
    _reset_state()
    attacker = create_test_monster("monster.goblin", name="Dual Wielder", position=(0, 0))
    target = create_test_monster("monster.goblin", name="Durable Target", position=(1, 0))
    _equip_off_hand_dagger(attacker)
    Entity.materialize_all_navigation()
    set_hp(target, 100)
    force_attack_miss(attacker)

    main_event = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=False,
    ).apply()
    off_event = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_OFF,
        template=False,
    ).apply()

    assert main_event is not None
    assert not main_event.canceled
    assert off_event is not None
    assert not off_event.canceled
    assert attacker.action_economy.actions.normalized_score == 0
    assert attacker.action_economy.bonus_actions.normalized_score == 0


def test_two_weapon_style_adds_off_hand_ability_modifier() -> None:
    """Legacy ``test_two_weapon_fighting.py::test_twf_style_adds_ability_modifier``."""
    _reset_state()
    attacker = create_test_monster("monster.goblin", name="Style Tester", position=(0, 0))
    target = create_test_monster("monster.goblin", name="Style Target", position=(1, 0))
    _equip_off_hand_dagger(attacker)
    Entity.materialize_all_navigation()
    before = _damage_bonus(attacker, target, WeaponSlot.MELEE_OFF)

    _apply_two_weapon_style(attacker)

    after = _damage_bonus(attacker, target, WeaponSlot.MELEE_OFF)
    expected_modifier = max(
        attacker.ability_scores.strength.modifier,
        attacker.ability_scores.dexterity.modifier,
    )
    assert before == 0
    assert after == before + expected_modifier


@pytest.mark.parametrize(
    ("strength", "dexterity"),
    [(18, 10), (10, 18)],
)
def test_two_weapon_style_finesse_uses_higher_ability(
    strength: int,
    dexterity: int,
) -> None:
    """Legacy ``test_two_weapon_fighting.py::test_twf_finesse_uses_higher_ability``."""
    _reset_state()
    attacker = _create_finesse_actor(
        strength=strength,
        dexterity=dexterity,
    )
    target = create_test_monster("monster.goblin", name="Finesse Target", position=(1, 0))
    _equip_off_hand_dagger(attacker)
    Entity.materialize_all_navigation()
    _apply_two_weapon_style(attacker)

    off_bonus = _damage_bonus(attacker, target, WeaponSlot.MELEE_OFF)

    assert off_bonus == max(
        attacker.ability_scores.strength.modifier,
        attacker.ability_scores.dexterity.modifier,
    )


def test_two_weapon_style_does_not_change_main_hand_damage() -> None:
    """Legacy ``test_two_weapon_fighting.py::test_twf_main_hand_unaffected``."""
    _reset_state()
    attacker = create_test_monster("monster.goblin", name="Main-Hand Tester", position=(0, 0))
    target = create_test_monster("monster.goblin", name="Main-Hand Target", position=(1, 0))
    _equip_off_hand_dagger(attacker)
    Entity.materialize_all_navigation()
    before = _damage_bonus(attacker, target, WeaponSlot.MELEE_MAIN)

    _apply_two_weapon_style(attacker)

    after = _damage_bonus(attacker, target, WeaponSlot.MELEE_MAIN)
    assert after == before


def test_removing_two_weapon_style_restores_off_hand_damage() -> None:
    """Legacy ``test_two_weapon_fighting.py::test_twf_condition_removal``."""
    _reset_state()
    attacker = create_test_monster("monster.goblin", name="Style Cleanup Tester", position=(0, 0))
    target = create_test_monster("monster.goblin", name="Style Cleanup Target", position=(1, 0))
    _equip_off_hand_dagger(attacker)
    Entity.materialize_all_navigation()
    before = _damage_bonus(attacker, target, WeaponSlot.MELEE_OFF)
    handles = _apply_two_weapon_style(attacker)
    during = _damage_bonus(attacker, target, WeaponSlot.MELEE_OFF)

    for value, modifier_uuid in handles:
        value.self_contextual.remove_value_modifier(modifier_uuid)

    after = _damage_bonus(attacker, target, WeaponSlot.MELEE_OFF)
    assert during > before
    assert after == before
