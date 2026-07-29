"""Active regression coverage restored from ``to_archive/examples/test_slow.py``.

The July test rework archived the executable Slow suite without replacing all
of its behavioral assertions.  Each test below names the legacy case it keeps
active so future reorganizations can prove one-for-one coverage.
"""

from uuid import UUID, uuid4

import pytest

from dnd.actions import (
    Attack,
    AttackEvent,
    Dodge,
    DropProne,
    Jump,
    Move,
)
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.equipment import Weapon
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.classes.fighter import (
    ActionSurge,
    ActionSurgeFeature,
    ExtraAttack,
    ExtraAttackFeature,
)
from dnd.conditions import Concentrating
from dnd.core.base_actions import Cost
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventPhase
from dnd.core.gridmap import get_map
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import NumericalModifier
from dnd.entity import Entity, EntityConfig
from dnd.items.weapons import GREATSWORD_RECIPE
from tests.spell_test_exports import FireBolt
from dnd.spells.transmutation import Slow
from tests.engine.support import (
    deal_damage_to,
    force_attack_miss,
    reset_combat_state,
    set_hp,
)


def _reset_state() -> None:
    reset_combat_state()
    get_map().create_rectangle(0, 0, 20, 20)


def _create_caster() -> Entity:
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            wisdom=AbilityConfig(ability_score=20),
        ),
        action_economy=ActionEconomyConfig(spell_slots={3: 3}),
        spellcasting=SpellcastingConfig(spellcasting_ability="wisdom"),
        health=HealthConfig(
            hit_dices=[
                HitDiceConfig(
                    hit_dice_value=8,
                    hit_dice_count=8,
                    mode="maximums",
                )
            ]
        ),
        proficiency_bonus=4,
        position=(1, 1),
        faction="heroes",
    )
    return Entity.create(
        source_entity_uuid=uuid4(),
        name="Slow Caster",
        config=config,
    )


def _create_target(
    name: str,
    position: tuple[int, int],
    *,
    wisdom: int = 6,
    faction: str = "monsters",
) -> Entity:
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=14),
            dexterity=AbilityConfig(ability_score=14),
            wisdom=AbilityConfig(ability_score=wisdom),
        ),
        action_economy=ActionEconomyConfig(),
        spellcasting=SpellcastingConfig(spellcasting_ability="wisdom"),
        health=HealthConfig(
            hit_dices=[
                HitDiceConfig(
                    hit_dice_value=10,
                    hit_dice_count=20,
                    mode="maximums",
                )
            ]
        ),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    target = Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=config,
    )
    setup_standard_actions(target)
    return target


def _create_fighter(
    position: tuple[int, int],
    *,
    action_surge: bool = False,
) -> Entity:
    fighter = _create_target("Slowed Fighter", position)
    fighter.equipment.equip(
        materialize_item(
            GREATSWORD_RECIPE,
            fighter.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        ),
        WeaponSlot.MELEE_MAIN,
    )
    fighter.add_condition(
        ExtraAttackFeature(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=fighter.uuid,
            extra_attacks=1,
        )
    )
    if action_surge:
        fighter.add_condition(
            ActionSurgeFeature(
                source_entity_uuid=fighter.uuid,
                target_entity_uuid=fighter.uuid,
                num_uses=1,
            )
        )
    return fighter


def _add_wisdom_save_modifier(entity: Entity, value: int) -> UUID:
    modifier = NumericalModifier.create(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        name="Deterministic Slow save",
        value=value,
    )
    entity.saving_throws.get_saving_throw(
        "wisdom"
    ).bonus.self_static.add_value_modifier(modifier)
    return modifier.uuid


def _remove_wisdom_save_modifier(entity: Entity, modifier_uuid: UUID) -> None:
    entity.saving_throws.get_saving_throw(
        "wisdom"
    ).bonus.self_static.remove_value_modifier(modifier_uuid)


def _cast_slow(
    caster: Entity,
    center: tuple[int, int],
) -> None:
    Entity.update_all_entities_senses()
    event = Slow(
        source_entity_uuid=caster.uuid,
        end_position=center,
        template=False,
    ).apply()
    assert event is not None
    assert not event.canceled


def _apply_attack(attacker: Entity, target: Entity) -> None:
    event = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=False,
    ).apply()
    assert event is not None
    assert not event.canceled


def test_slow_applies_complete_static_debuff_bundle() -> None:
    """Legacy ``test_slow.py::test_1``: speed/AC/DEX-save/reaction debuffs."""
    _reset_state()
    caster = _create_caster()
    target = _create_target("Slowed Target", (3, 1))
    Entity.update_all_entities_senses()
    base_speed = target.action_economy.movement.normalized_score
    base_ac = target.equipment.ac_bonus.normalized_score
    base_dex_save = target.saving_throws.get_saving_throw(
        "dexterity"
    ).bonus.normalized_score
    failure_modifier = _add_wisdom_save_modifier(target, -100)

    _cast_slow(caster, target.position)

    _remove_wisdom_save_modifier(target, failure_modifier)
    assert "Slowed" in target.active_conditions
    assert "Concentrating" in caster.active_conditions
    assert target.action_economy.movement.normalized_score == base_speed // 2
    assert target.equipment.ac_bonus.normalized_score == base_ac - 2
    assert (
        target.saving_throws.get_saving_throw(
            "dexterity"
        ).bonus.normalized_score
        == base_dex_save - 2
    )
    assert target.action_economy.reactions.normalized_score == 0


@pytest.mark.parametrize(
    "action_kind",
    ["base_action", "attack", "spell", "bonus_action"],
)
def test_slow_allows_either_action_or_bonus_action_but_not_both(
    action_kind: str,
) -> None:
    """Legacy ``test_slow.py::test_2``: every action family shares the lockout."""
    _reset_state()
    caster = _create_caster()
    target = _create_target("Lockout Target", (3, 1))
    other = _create_target("Lockout Other", (4, 1))
    failure_modifier = _add_wisdom_save_modifier(target, -100)
    other_success = _add_wisdom_save_modifier(other, 100)
    _cast_slow(caster, target.position)
    _remove_wisdom_save_modifier(other, other_success)
    target.on_turn_start()

    if action_kind == "base_action":
        event = Dodge(
            source_entity_uuid=target.uuid,
            template=False,
        ).apply()
    elif action_kind == "attack":
        event = Attack(
            source_entity_uuid=target.uuid,
            target_entity_uuid=other.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
            template=False,
        ).apply()
    elif action_kind == "spell":
        event = FireBolt(
            source_entity_uuid=target.uuid,
            target_entity_uuid=other.uuid,
            template=False,
        ).apply()
    else:
        event = Jump(
            source_entity_uuid=target.uuid,
            end_position=(3, 2),
            template=False,
        ).apply()

    assert event is not None
    assert not event.canceled
    if action_kind == "bonus_action":
        assert target.action_economy.actions.normalized_score == 0
    else:
        assert target.action_economy.bonus_actions.normalized_score == 0

    target.on_turn_end()
    target.on_turn_start()

    assert target.action_economy.actions.normalized_score == 1
    assert target.action_economy.bonus_actions.normalized_score == 1
    _remove_wisdom_save_modifier(target, failure_modifier)


@pytest.mark.parametrize(
    "nonlocking_action_kind",
    ["free", "reaction", "movement"],
)
def test_slow_does_not_lock_for_non_action_or_bonus_costs(
    nonlocking_action_kind: str,
) -> None:
    """Slow lockout ignores free, reaction, and movement-feet cost channels."""
    _reset_state()
    caster = _create_caster()
    target = _create_target("Nonlocking Target", (3, 1))
    other = _create_target("Nonlocking Other", (4, 1))
    failure_modifier = _add_wisdom_save_modifier(target, -100)
    other_success = _add_wisdom_save_modifier(other, 100)
    _cast_slow(caster, target.position)
    _remove_wisdom_save_modifier(other, other_success)
    target.on_turn_start()

    if nonlocking_action_kind == "free":
        event = DropProne(
            source_entity_uuid=target.uuid,
            template=False,
        ).apply()
    elif nonlocking_action_kind == "reaction":
        event = AttackEvent(
            source_entity_uuid=target.uuid,
            target_entity_uuid=other.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
            costs=[
                Cost(
                    name="Test Reaction",
                    cost_type="reactions",
                    cost=1,
                )
            ],
            phase=EventPhase.EFFECT,
        )
    else:
        event = Move(
            source_entity_uuid=target.uuid,
            end_position=(3, 2),
            template=False,
        ).apply()

    assert event is not None
    assert not event.canceled
    assert target.action_economy.actions.normalized_score == 1
    assert target.action_economy.bonus_actions.normalized_score == 1
    _remove_wisdom_save_modifier(target, failure_modifier)


def test_slow_suppresses_extra_attack_after_an_attack_action() -> None:
    """Legacy ``test_slow.py::test_3``: a slowed Attack grants no extra swing."""
    _reset_state()
    caster = _create_caster()
    fighter = _create_fighter((3, 1))
    target = _create_target("Durable Target", (4, 1))
    set_hp(target, 500)
    force_attack_miss(fighter)
    fighter_failure = _add_wisdom_save_modifier(fighter, -100)
    target_success = _add_wisdom_save_modifier(target, 100)
    _cast_slow(caster, fighter.position)
    _remove_wisdom_save_modifier(fighter, fighter_failure)
    _remove_wisdom_save_modifier(target, target_success)
    fighter.on_turn_start()

    _apply_attack(fighter, target)

    resource = fighter.action_economy.resources["extra_attacks"]
    assert resource.current == 0
    extra_event = ExtraAttack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=False,
    ).apply()
    assert extra_event is None or extra_event.canceled


def test_slow_repeat_save_at_turn_end_removes_effect() -> None:
    """Legacy ``test_slow.py::test_4``: a successful repeat WIS save ends Slow."""
    _reset_state()
    caster = _create_caster()
    target = _create_target("Repeat Save Target", (3, 1), wisdom=20)
    initial_failure = _add_wisdom_save_modifier(target, -100)
    _cast_slow(caster, target.position)
    _remove_wisdom_save_modifier(target, initial_failure)
    repeat_success = _add_wisdom_save_modifier(target, 100)

    target.on_turn_end()

    _remove_wisdom_save_modifier(target, repeat_success)
    assert "Slowed" not in target.active_conditions


def test_slow_breaks_on_caster_death_and_cleans_every_target() -> None:
    """Legacy ``test_slow.py::test_5``: breaking concentration cleans Slow."""
    _reset_state()
    caster = _create_caster()
    targets = [
        _create_target("First Slowed Target", (3, 1)),
        _create_target("Second Slowed Target", (3, 2)),
    ]
    failure_modifiers = [
        _add_wisdom_save_modifier(target, -100)
        for target in targets
    ]
    _cast_slow(caster, targets[0].position)
    for target, modifier_uuid in zip(targets, failure_modifiers):
        _remove_wisdom_save_modifier(target, modifier_uuid)
    assert all("Slowed" in target.active_conditions for target in targets)

    set_hp(caster, 1)
    deal_damage_to(caster, 100, DamageType.FORCE, uuid4())

    assert "Concentrating" not in caster.active_conditions
    assert all("Slowed" not in target.active_conditions for target in targets)


def test_slow_links_each_failed_target_to_concentration() -> None:
    """Legacy ``test_slow.py::test_6``: all failed targets are linked children."""
    _reset_state()
    caster = _create_caster()
    targets = [
        _create_target(f"Linked Target {index}", (3, index + 1))
        for index in range(3)
    ]
    failure_modifiers = [
        _add_wisdom_save_modifier(target, -100)
        for target in targets
    ]

    _cast_slow(caster, (3, 2))

    for target, modifier_uuid in zip(targets, failure_modifiers):
        _remove_wisdom_save_modifier(target, modifier_uuid)
    assert all("Slowed" in target.active_conditions for target in targets)
    concentration = caster.active_conditions["Concentrating"]
    assert isinstance(concentration, Concentrating)
    assert {
        (target.uuid, target.active_conditions["Slowed"].uuid)
        for target in targets
    } <= set(concentration.linked_conditions)


def test_slow_action_surge_allows_two_single_attacks_without_extra_attacks() -> None:
    """Legacy ``test_slow.py::test_7``: Surge adds an action, never an EA."""
    _reset_state()
    caster = _create_caster()
    fighter = _create_fighter((3, 1), action_surge=True)
    target = _create_target("Action Surge Target", (4, 1))
    set_hp(target, 500)
    force_attack_miss(fighter)
    fighter_failure = _add_wisdom_save_modifier(fighter, -100)
    target_success = _add_wisdom_save_modifier(target, 100)
    _cast_slow(caster, fighter.position)
    _remove_wisdom_save_modifier(target, target_success)
    fighter.on_turn_start()

    surge_event = ActionSurge(
        source_entity_uuid=fighter.uuid,
        template=False,
    ).apply()
    assert surge_event is not None
    assert not surge_event.canceled
    assert fighter.action_economy.actions.normalized_score == 2
    assert fighter.action_economy.bonus_actions.normalized_score == 1

    _apply_attack(fighter, target)
    assert fighter.action_economy.resources["extra_attacks"].current == 0
    _apply_attack(fighter, target)

    assert fighter.action_economy.actions.normalized_score == 0
    assert fighter.action_economy.resources["extra_attacks"].current == 0
    exhausted_attack = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=False,
    ).apply()
    assert exhausted_attack is None or exhausted_attack.canceled
    _remove_wisdom_save_modifier(fighter, fighter_failure)


def test_slow_lockout_constraint_is_idempotent_and_fully_owned() -> None:
    """Repeated action events retain one lock that reset/removal both clean."""
    _reset_state()
    caster = _create_caster()
    fighter = _create_fighter((3, 1), action_surge=True)
    target = _create_target("Lock Ownership Target", (4, 1))
    set_hp(target, 500)
    force_attack_miss(fighter)
    fighter_failure = _add_wisdom_save_modifier(fighter, -100)
    target_success = _add_wisdom_save_modifier(target, 100)
    _cast_slow(caster, fighter.position)
    _remove_wisdom_save_modifier(target, target_success)
    fighter.on_turn_start()

    surge_event = ActionSurge(
        source_entity_uuid=fighter.uuid,
        template=False,
    ).apply()
    assert surge_event is not None
    assert not surge_event.canceled
    assert not fighter.action_economy.bonus_actions.self_static.max_constraints

    _apply_attack(fighter, target)
    first_lock_uuids = set(
        fighter.action_economy.bonus_actions.self_static.max_constraints
    )
    assert len(first_lock_uuids) == 1

    _apply_attack(fighter, target)
    assert (
        set(fighter.action_economy.bonus_actions.self_static.max_constraints)
        == first_lock_uuids
    )

    fighter.on_turn_end()
    fighter.on_turn_start()
    assert "Slowed" in fighter.active_conditions
    assert not fighter.action_economy.bonus_actions.self_static.max_constraints

    _apply_attack(fighter, target)
    second_turn_lock_uuids = set(
        fighter.action_economy.bonus_actions.self_static.max_constraints
    )
    assert len(second_turn_lock_uuids) == 1
    assert second_turn_lock_uuids.isdisjoint(first_lock_uuids)

    fighter.remove_condition("Slowed")
    assert not fighter.action_economy.bonus_actions.self_static.max_constraints
    _remove_wisdom_save_modifier(fighter, fighter_failure)
