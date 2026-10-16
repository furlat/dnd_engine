"""Force boundaries, wall contact cadence and remote sword actions through paid casts."""

from uuid import uuid4

import pytest

from dnd.actions import Attack, Dodge, Move
from dnd.blocks.base_item import BaseItem
from dnd.core.creature_types import CreatureType, DamageType, Size
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    ForcedMovementEvent,
    SpatialChangeEvent,
    Trigger,
)
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.spells.abjuration import AntilifeShell
from dnd.spells.conjuration import DimensionDoor, MistyStep
from dnd.spells.divination import SeeInvisibility
from dnd.spells.enchantment import CharmMonster, PowerWordKill
from dnd.spells.evocation import (
    ArcaneSword,
    ArcaneSwordStrike,
    BladeBarrier,
    HealingWord,
    MoveArcaneSword,
    ResilientSphere,
    VitriolicSphere,
)
from dnd.spells.transmutation import Disintegrate
from dnd.spells.wall_constructions import Forcecage, ForcecageZone, WallSection
from dnd.spells.wall_fields import BladeBarrierZone
from dnd.types.physical_access import PhysicalAccess
from dnd.types.world import MovementMode
from tests.engine.test_high_level_spell_controls import (
    cast,
    conditions,
    game,
    high_actor,
)
from tests.manual.spell_regression_support import force_save_result


def test_blade_barrier_cast_entry_start_once_per_turn_and_native_terrain(game):
    caster = high_actor(game)
    target = high_actor(game, "Target", (6, 5), "foes")
    force_save_result(target, "dexterity", succeeds=False)
    hp = target.get_hp()
    turn = EventQueue.begin_turn_execution()
    try:
        with fixed_dice_faces(*([2] * 50)):
            cast(
                BladeBarrier,
                caster,
                end_position=(4, 5),
                extra_target_positions=[(10, 5)],
            )
        assert target.get_hp() == hp - 12
        assert get_map().get_tile(6, 5).get_movement_cost(MovementMode.WALKING) == 2
        target.move((6, 6))
        with fixed_dice_faces(*([2] * 30)):
            target.move((6, 5))
        assert target.get_hp() == hp - 12
    finally:
        EventQueue.end_turn_execution(turn)
    turn = EventQueue.begin_turn_execution()
    try:
        hp = target.get_hp()
        with fixed_dice_faces(*([2] * 30)):
            target.on_turn_start()
        assert target.get_hp() == hp - 12
        with fixed_dice_faces(*([2] * 30)):
            target.on_turn_end()
        assert target.get_hp() == hp - 12
    finally:
        EventQueue.end_turn_execution(turn)
    caster.remove_condition("Concentrating")
    assert not any(
        isinstance(zone, BladeBarrierZone)
        for zone in get_map().get_spatial_conditions()
    )
    assert get_map().get_tile(6, 5).get_movement_cost(MovementMode.WALKING) == 1


@pytest.mark.parametrize(
    "creature_type,blocked",
    [
        (CreatureType.HUMANOID, True),
        (CreatureType.UNDEAD, False),
        (CreatureType.CONSTRUCT, False),
    ],
)
def test_antilife_shell_creature_boundary_and_permeable_weapon_channel(
    game, creature_type, blocked
):
    caster = high_actor(game, position=(8, 4))
    target = high_actor(game, "Target", (11, 4), "foes", creature_type=creature_type)
    cast(AntilifeShell, caster)
    assert get_map().spatial_crossing_allows(
        (11, 4), (10, 4), "movement", target.uuid
    ) == (not blocked)
    assert get_map().spatial_crossing_allows(
        (11, 4), (10, 4), "propagation", target.uuid
    )
    assert get_map().spatial_crossing_allows((9, 4), (10, 4), "movement", target.uuid)


def test_antilife_shell_committed_caster_movement_ends_on_living_sweep(game):
    caster = high_actor(game, position=(5, 5))
    target = high_actor(game, "Target", (8, 5), "foes")
    cast(AntilifeShell, caster)
    caster.move((7, 5))
    assert "Concentrating" not in conditions(caster)


@pytest.mark.parametrize("hostile,saved", [(False, True), (True, False), (True, True)])
def test_resilient_sphere_admission_damage_action_matrix_and_exact_deadline(
    game, hostile, saved
):
    caster = high_actor(game)
    target = high_actor(game, "Target", (3, 2), "foes" if hostile else "heroes")
    other = high_actor(game, "Other", (4, 2), "others")
    force_save_result(target, "dexterity", succeeds=saved)
    cast(ResilientSphere, caster, target)
    if hostile and saved:
        assert "Resilient Sphere" not in conditions(target)
        return
    assert "Resilient Sphere" in conditions(target)
    assert target.action_economy.current_speed() == 15
    hp = target.get_hp()
    target.receive_damage(30, DamageType.FORCE, other.uuid)
    assert target.get_hp() == hp
    target.action_economy.reset_all_costs()
    blocked = HealingWord(
        source_entity_uuid=target.uuid, target_entity_uuid=target.uuid
    ).apply()
    assert blocked is not None and blocked.canceled
    assert target.action_economy.bonus_actions.normalized_score == 1
    blocked = Attack(
        source_entity_uuid=target.uuid,
        target_entity_uuid=other.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    ).apply()
    assert blocked is not None and blocked.canceled
    assert target.action_economy.actions.normalized_score == 1
    assert Dodge(source_entity_uuid=target.uuid).apply() is not None
    caster.action_economy.reset_all_costs()
    PowerWordKill(
        source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid
    ).apply()
    assert target.get_hp() == hp
    for _ in range(2):
        target.on_turn_start()
        target.on_turn_end()
        assert "Resilient Sphere" in conditions(target)
    target.on_turn_start()
    target.on_turn_end()
    assert "Resilient Sphere" not in conditions(target)
    assert target.action_economy.current_speed() == 30


def test_resilient_sphere_disintegrate_ends_force_creation_without_harming_occupant(
    game,
):
    caster = high_actor(game)
    target = high_actor(game, "Target", (3, 2))
    ray_caster = high_actor(game, "Enemy", (4, 2), "foes")
    cast(ResilientSphere, caster, target)
    hp = target.get_hp()
    cast(Disintegrate, ray_caster, target)
    assert target.get_hp() == hp and "Resilient Sphere" not in conditions(target)


def test_sword_initial_and_moving_bonus_attack_use_remote_anchor_and_cleanup(game):
    caster = high_actor(game)
    first = high_actor(game, "First", (10, 2), "foes")
    second = high_actor(game, "Second", (14, 2), "foes")
    hp = first.get_hp()
    with fixed_dice_faces(15, 2, 2, 2):
        cast(ArcaneSword, caster, first, end_position=(9, 2))
    assert first.get_hp() == hp - 6
    owner = conditions(caster)["Arcane Sword"]
    assert owner.position == (9, 2)
    Entity.update_entity_position(caster, (5, 2))
    Entity.update_all_entities_senses()
    hp = second.get_hp()
    with fixed_dice_faces(15, 2, 2, 2):
        result = ArcaneSwordStrike(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=second.uuid,
            grant_condition_uuid=owner.uuid,
            end_position=(13, 2),
        ).apply()
    assert result is not None and not result.canceled, (
        result.status_message if result else "No action"
    )
    assert second.get_hp() == hp - 6
    assert caster.action_economy.bonus_actions.normalized_score == 0
    caster.action_economy.reset_all_costs()
    result = MoveArcaneSword(
        source_entity_uuid=caster.uuid,
        grant_condition_uuid=owner.uuid,
        end_position=(12, 3),
    ).apply()
    assert result is not None and not result.canceled
    assert owner.position == (12, 3)
    caster.remove_condition("Concentrating")
    caster.action_economy.reset_all_costs()
    result = MoveArcaneSword(
        source_entity_uuid=caster.uuid,
        grant_condition_uuid=owner.uuid,
        end_position=(13, 3),
    ).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.bonus_actions.normalized_score == 1


@pytest.mark.parametrize("form,propagation", [("cage", True), ("box", False)])
@pytest.mark.parametrize("travel", [MistyStep, DimensionDoor])
def test_forcecage_blocks_contact_and_paid_escape_failure_then_success(
    game, form, propagation, travel
):
    caster = high_actor(game)
    prisoner = high_actor(game, "Prisoner", (8, 4), "foes")
    cast(Forcecage, caster, end_position=(8, 4), cage_form=form)
    zone = next(
        zone
        for zone in get_map().get_spatial_conditions()
        if isinstance(zone, ForcecageZone)
    )
    assert "Concentrating" not in caster.active_conditions
    assert not get_map().can_reach_between(
        prisoner.position, (11, 4), PhysicalAccess.WEAPON, prisoner.uuid
    )
    assert (
        get_map().can_reach_between(
            prisoner.position, (11, 4), PhysicalAccess.PROJECTILE, prisoner.uuid
        )
        == propagation
    )
    force_save_result(prisoner, "charisma", succeeds=False)
    before = prisoner.action_economy.spell_slot_value(
        2 if travel is MistyStep else 4
    ).normalized_score
    result = travel(
        source_entity_uuid=prisoner.uuid,
        target_entity_uuid=prisoner.uuid if travel is DimensionDoor else None,
        end_position=(11, 4),
    ).apply()
    assert result is not None
    assert (
        prisoner.position == (8, 4)
        and (
            prisoner.action_economy.bonus_actions
            if travel is MistyStep
            else prisoner.action_economy.actions
        ).normalized_score
        == 0
    )
    assert (
        prisoner.action_economy.spell_slot_value(
            2 if travel is MistyStep else 4
        ).normalized_score
        == before - 1
    )
    prisoner.action_economy.reset_all_costs()
    force_save_result(prisoner, "charisma", succeeds=True)
    force_save_result(prisoner, "charisma", succeeds=True)
    result = travel(
        source_entity_uuid=prisoner.uuid,
        target_entity_uuid=prisoner.uuid if travel is DimensionDoor else None,
        end_position=(11, 4),
    ).apply()
    assert result is not None and not result.canceled, (
        result.status_message if result else "No action"
    )
    assert prisoner.position == (11, 4)


def test_forcecage_formation_second_ejection_veto_preserves_both_positions(game):
    caster = high_actor(game)
    left = high_actor(game, "Left", (6, 3), "foes")
    right = high_actor(game, "Right", (10, 5), "foes")
    before = (left.position, right.position)
    count = 0

    def veto(event, _):
        nonlocal count
        if (
            isinstance(event, ForcedMovementEvent)
            and event.cause == "forcecage_formation"
        ):
            count += 1
            if count == 2:
                return event.cancel(status_message="Second displacement refused")
        return None

    caster.add_event_handler(
        EventHandler(
            name="Second displacement veto",
            source_entity_uuid=caster.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.FORCED_MOVEMENT, event_phase=EventPhase.EFFECT
                )
            ],
            event_processor=veto,
        )
    )
    result = Forcecage(source_entity_uuid=caster.uuid, end_position=(8, 4)).apply()
    assert result is not None and result.canceled
    assert count == 2 and (left.position, right.position) == before
    assert not any(
        isinstance(zone, ForcecageZone) for zone in get_map().get_spatial_conditions()
    )
    assert not any(isinstance(item, WallSection) for item in BaseItem.get_all_items())


def test_forcecage_section_placement_veto_leaves_ejected_creature_unmoved(game):
    caster = high_actor(game)
    victim = high_actor(game, "Edge", (6, 3), "foes")
    before = victim.position

    def veto(event, _):
        if isinstance(event, SpatialChangeEvent) and isinstance(
            BaseItem.get(event.object_uuid), WallSection
        ):
            return event.cancel(status_message="Section placement refused")
        return None

    caster.add_event_handler(
        EventHandler(
            name="Section veto",
            source_entity_uuid=caster.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.SPATIAL_OBJECT_PLACED,
                    event_phase=EventPhase.EFFECT,
                )
            ],
            event_processor=veto,
        )
    )
    result = Forcecage(source_entity_uuid=caster.uuid, end_position=(8, 4)).apply()
    assert result is not None and result.canceled
    assert victim.position == before
    assert not any(
        isinstance(zone, ForcecageZone) for zone in get_map().get_spatial_conditions()
    )
    assert not any(isinstance(item, WallSection) for item in BaseItem.get_all_items())


@pytest.mark.parametrize("form,remaining", [("cage", True), ("box", False)])
def test_forcecage_disintegrate_breaches_cage_and_destroys_small_box(
    game, form, remaining
):
    caster = high_actor(game)
    victim = high_actor(game, "Prisoner", (8, 4), "foes")
    cast(Forcecage, caster, end_position=victim.position, cage_form=form)
    zone = next(
        zone
        for zone in get_map().get_spatial_conditions()
        if isinstance(zone, ForcecageZone)
    )
    cast(SeeInvisibility, caster)
    # The left face lies between this caster and the prisoner.
    section = min(
        (
            BaseItem.get(identity)
            for identity in zone.sections
            if BaseItem.get(identity).geometry.path.start[0]
            == BaseItem.get(identity).geometry.path.end[0]
        ),
        key=lambda item: (
            item.geometry.path.start[0],
            min(item.geometry.path.start[1], item.geometry.path.end[1]),
        ),
    )
    caster.action_economy.reset_all_costs()
    Entity.update_all_entities_senses()
    result = Disintegrate(
        source_entity_uuid=caster.uuid, target_entity_uuid=section.uuid
    ).apply()
    assert result is not None and not result.canceled, (
        result.status_message if result else "No action"
    )
    assert (get_map().get_spatial_condition(zone.uuid) is not None) == remaining
    if remaining:
        assert get_map().can_reach_between(
            victim.position, (4, 2), PhysicalAccess.BODY, victim.uuid
        ), (
            section.geometry.model_dump(),
            [
                (
                    point,
                    get_map().can_reach_between(
                        victim.position, point, PhysicalAccess.BODY, victim.uuid
                    ),
                )
                for point in ((4, 2), (4, 3), (4, 4), (8, 1), (10, 1))
            ],
        )
        assert not get_map().can_reach_between(
            victim.position, (12, 4), PhysicalAccess.BODY, victim.uuid
        )




def test_resilient_sphere_protects_actual_under_threshold_instant_kill(game):
    caster = high_actor(game)
    victim = high_actor(game, "Victim", (3, 2))
    enemy = high_actor(game, "Enemy", (4, 2), "foes")
    victim.receive_damage(victim.get_hp() - 50, DamageType.FORCE, caster.uuid)
    cast(ResilientSphere, caster, victim)
    result = PowerWordKill(
        source_entity_uuid=enemy.uuid, target_entity_uuid=victim.uuid
    ).apply()
    assert result is not None and result.canceled
    assert enemy.action_economy.actions.normalized_score == 0
    assert victim.get_hp() == 50


def test_sword_late_effect_veto_does_not_move_anchor(game):
    caster = high_actor(game)
    enemy = high_actor(game, "Enemy", (7, 2), "foes")
    with fixed_dice_faces(15, 2, 2, 2):
        cast(ArcaneSword, caster, enemy, end_position=(6, 2))
    owner = conditions(caster)["Arcane Sword"]
    caster.action_economy.reset_all_costs()

    def veto(event, _):
        if event.behavior_id == "action.spell.arcane_sword.strike":
            return event.cancel(status_message="Strike refused")
        return None

    caster.add_event_handler(
        EventHandler(
            name="Sword effect veto",
            source_entity_uuid=caster.uuid,
            trigger_conditions=[
                Trigger(event_type=kind, event_phase=EventPhase.EFFECT)
                for kind in (EventType.BASE_ACTION, EventType.CAST_SPELL)
            ],
            event_processor=veto,
        )
    )
    template = next(
        action
        for action in caster.registered_actions
        if isinstance(action, ArcaneSwordStrike)
    )
    result = template.instantiate(
        target_entity_uuid=enemy.uuid, end_position=(7, 3)
    ).apply()
    assert result is not None and result.canceled
    assert owner.position == (6, 2)
