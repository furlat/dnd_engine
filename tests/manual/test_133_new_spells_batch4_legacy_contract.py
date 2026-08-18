"""Deterministic parity for the archived Batch 4 spell matrix.

This is the maintained replacement for
``to_archive/examples/test_new_spells_batch4.py``.  The archived file used a
level-five bestiary caster for fifth-, sixth-, and seventh-level spells and
silently counted failed ``check()`` calls as passing pytest tests.  These tests
use explicit legal resources and hard assertions.
"""

from uuid import UUID

from dnd.actions.standard import (
    AttackEvent,
    SpellEvent,
)
from dnd.actions.operations import (
    execute_by_index,
    get_available_actions,
    setup_standard_actions,
)
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.dice import fixed_dice_faces
from dnd.types.equipment import WeaponSlot
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)
from dnd.types.damage import DamageType
from dnd.core.modifiers import AutoHitModifier
from dnd.types.rolls import AutoHitStatus
from dnd.entities.entity import Entity
from dnd.spells.abjuration import (
    Banishment,
    GlobeOfInvulnerability,
    GlobeZone,
)
from dnd.spells.conjuration import Web
from dnd.spells.evocation import Fireball, FireBolt, register_true_strike
from dnd.spells.necromancy import FingerOfDeath
from dnd.spells.transmutation import Telekinesis
from dnd.core.gridmap import get_map
from tests.engine.support import get_hp, has_condition
from tests.manual.spell_regression_support import (
    create_spell_regression_actor,
    force_save_result,
    reset_spell_regression_arena,
)


def _force_attack_outcome(entity: Entity, outcome: AutoHitStatus) -> UUID:
    modifier = AutoHitModifier(
        name=f"Batch 4 {outcome.value}",
        value=outcome,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
    )
    entity.equipment.attack_bonus.self_static.add_auto_hit_modifier(modifier)
    return modifier.uuid


def _remove_attack_outcome(entity: Entity, modifier_uuid: UUID) -> None:
    entity.equipment.attack_bonus.self_static.remove_modifier(modifier_uuid)


def _action_row(entity: Entity, template_name: str):
    available = get_available_actions(entity)
    return available, next(
        row for row in available.all_actions
        if row.template_name == template_name
    )


def _true_strike_scene(caster_level: int) -> tuple[Entity, Entity]:
    reset_spell_regression_arena(12, 7)
    caster = create_spell_regression_actor(
        "True Strike Caster",
        (2, 3),
        "heroes",
        strength=8,
        intelligence=18,
    )
    target = create_spell_regression_actor(
        "True Strike Target",
        (3, 3),
        "monsters",
    )
    caster.equipment.equip(
        build_authored_item("weapon.dagger", caster.uuid),
        WeaponSlot.MELEE_MAIN,
    )
    setup_standard_actions(caster)
    register_true_strike(caster, caster_level=caster_level)
    Entity.update_all_entities_senses(max_distance=60)
    return caster, target


def test_true_strike_uses_spellcasting_ability() -> None:
    """Old case 1: weapon damage uses the casting ability, not Strength."""
    caster, target = _true_strike_scene(caster_level=1)
    hp_before = get_hp(target)
    modifier_uuid = _force_attack_outcome(caster, AutoHitStatus.AUTOHIT)

    available, row = _action_row(caster, "True Strike (Melee)")
    target_row = next(
        choice for choice in row.valid_targets
        if choice.target_uuid == target.uuid
    )
    with fixed_dice_faces(10, 2):
        result = execute_by_index(
            caster,
            row.template_name,
            target_row.index,
            available=available,
        )
    _remove_attack_outcome(caster, modifier_uuid)

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert hp_before - get_hp(target) == 6


def test_true_strike_cantrip_scaling_adds_radiant_die() -> None:
    """Old case 2: level five adds one d6 to the weapon damage."""
    caster, target = _true_strike_scene(caster_level=5)
    hp_before = get_hp(target)
    modifier_uuid = _force_attack_outcome(caster, AutoHitStatus.AUTOHIT)

    available, row = _action_row(caster, "True Strike (Melee)")
    target_row = next(
        choice for choice in row.valid_targets
        if choice.target_uuid == target.uuid
    )
    with fixed_dice_faces(10, 2, 3):
        result = execute_by_index(
            caster,
            row.template_name,
            target_row.index,
            available=available,
        )
    _remove_attack_outcome(caster, modifier_uuid)

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert hp_before - get_hp(target) == 9


def test_true_strike_never_mutates_shared_equipment_damage_state() -> None:
    """Reactive handlers never observe a temporary radiant equipment rider."""
    caster, target = _true_strike_scene(caster_level=5)
    modifier_uuid = _force_attack_outcome(caster, AutoHitStatus.AUTOHIT)
    equipment = caster.equipment
    baseline = (
        tuple(equipment.extra_attack_damage_dices),
        tuple(equipment.extra_attack_damage_dices_numbers),
        tuple(equipment.extra_attack_damage_bonus),
        tuple(equipment.extra_attack_damage_type),
    )
    observed = []

    def capture_equipment_state(event: Event, _: UUID) -> Event:
        observed.append((
            tuple(equipment.extra_attack_damage_dices),
            tuple(equipment.extra_attack_damage_dices_numbers),
            tuple(equipment.extra_attack_damage_bonus),
            tuple(equipment.extra_attack_damage_type),
        ))
        return event

    caster.add_event_handler(
        EventHandler(
            name="Observe True Strike equipment state",
            source_entity_uuid=caster.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK,
                    event_phase=EventPhase.EXECUTION,
                    event_source_entity_uuid=caster.uuid,
                ),
            ],
            event_processor=capture_equipment_state,
        )
    )

    available, row = _action_row(caster, "True Strike (Melee)")
    target_row = next(
        choice for choice in row.valid_targets
        if choice.target_uuid == target.uuid
    )
    with fixed_dice_faces(10, 2, 3):
        result = execute_by_index(
            caster,
            row.template_name,
            target_row.index,
            available=available,
        )
    _remove_attack_outcome(caster, modifier_uuid)

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert observed
    assert all(snapshot == baseline for snapshot in observed)
    assert (
        tuple(equipment.extra_attack_damage_dices),
        tuple(equipment.extra_attack_damage_dices_numbers),
        tuple(equipment.extra_attack_damage_bonus),
        tuple(equipment.extra_attack_damage_type),
    ) == baseline


def test_true_strike_miss_deals_no_damage() -> None:
    """Old case 3: a miss deals nothing but keeps every presentation category."""
    caster, target = _true_strike_scene(caster_level=5)
    hp_before = get_hp(target)
    modifier_uuid = _force_attack_outcome(caster, AutoHitStatus.AUTOMISS)

    available, row = _action_row(caster, "True Strike (Melee)")
    target_row = next(
        choice for choice in row.valid_targets
        if choice.target_uuid == target.uuid
    )
    with fixed_dice_faces(10):
        result = execute_by_index(
            caster,
            row.template_name,
            target_row.index,
            available=available,
        )
    _remove_attack_outcome(caster, modifier_uuid)

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert get_hp(target) == hp_before
    completed_attacks = [
        event
        for event in EventQueue.get_events_by_type(EventType.ATTACK)
        if event.phase == EventPhase.COMPLETION
    ]
    assert completed_attacks
    attack_event = completed_attacks[-1]
    assert isinstance(attack_event, AttackEvent)
    assert attack_event.damage_types == [
        DamageType.PIERCING,
        DamageType.RADIANT,
    ]


def test_finger_of_death_full_and_half_damage() -> None:
    """Old cases 4-5: failed saves take full 7d8+30 and successes half."""
    for succeeds, expected_damage in ((False, 58), (True, 29)):
        reset_spell_regression_arena(16, 7)
        caster = create_spell_regression_actor(
            "Finger Caster",
            (2, 3),
            "heroes",
            spell_slots={7: 1},
        )
        target = create_spell_regression_actor(
            "Finger Target",
            (8, 3),
            "monsters",
        )
        force_save_result(target, "constitution", succeeds=succeeds)
        Entity.update_all_entities_senses(max_distance=100)
        hp_before = get_hp(target)

        with fixed_dice_faces(10, *([4] * 7)):
            result = FingerOfDeath(
                source_entity_uuid=caster.uuid,
                target_entity_uuid=target.uuid,
                cast_at_level=7,
            ).apply()

        assert isinstance(result, SpellEvent)
        assert not result.canceled
        assert hp_before - get_hp(target) == expected_damage
        assert caster.action_economy.spell_slot_7.normalized_score == 0


def _telekinesis_scene() -> tuple[Entity, Entity]:
    reset_spell_regression_arena(18, 11)
    caster = create_spell_regression_actor(
        "Telekinesis Caster",
        (2, 5),
        "heroes",
        spell_slots={5: 1},
    )
    target = create_spell_regression_actor(
        "Telekinesis Target",
        (6, 5),
        "monsters",
    )
    force_save_result(target, "strength", succeeds=False)
    Entity.update_all_entities_senses(max_distance=100)
    return caster, target


def test_telekinesis_grab_exposes_and_consumes_restrain_followup() -> None:
    """Old case 6: a failed initial contest exposes both typed follow-ups."""
    caster, target = _telekinesis_scene()

    with fixed_dice_faces(10):
        result = Telekinesis(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=5,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert has_condition(caster, "Concentrating")
    available = get_available_actions(caster)
    names = {row.template_name for row in available.all_actions}
    assert {"Telekinesis: Restrain", "Telekinesis: Move"} <= names

    restrain = next(
        row for row in available.all_actions
        if row.template_name == "Telekinesis: Restrain"
    )
    followup = execute_by_index(
        caster,
        restrain.template_name,
        restrain.valid_targets[0].index,
        available=available,
    )

    assert followup is not None
    assert not followup.canceled
    assert has_condition(target, "Restrained")
    remaining_names = {action.name for action in caster.registered_actions}
    assert "Telekinesis: Restrain" not in remaining_names
    assert "Telekinesis: Move" not in remaining_names


def test_telekinesis_move_updates_spatial_indexes_and_cleans_followups() -> None:
    """Old case 7: forced movement updates both entity and grid indexes."""
    caster, target = _telekinesis_scene()
    original_position = target.position

    with fixed_dice_faces(10):
        Telekinesis(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=5,
        ).apply()

    available = get_available_actions(caster)
    move = next(
        row for row in available.position_actions
        if row.template_name == "Telekinesis: Move"
    )
    destination = next(
        choice for choice in move.valid_targets
        if choice.position == (7, 5)
    )
    result = execute_by_index(
        caster,
        move.template_name,
        destination.index,
        available=available,
    )

    assert result is not None
    assert not result.canceled
    assert target.position == (7, 5)
    assert target in Entity._entity_by_position[(7, 5)]
    assert target not in Entity._entity_by_position[original_position]
    assert {"Telekinesis: Restrain", "Telekinesis: Move"}.isdisjoint(
        {action.name for action in caster.registered_actions}
    )


def test_telekinesis_concentration_cleanup_removes_restrain_and_action() -> None:
    """Old case 8: concentration owns both the condition and granted action."""
    caster, target = _telekinesis_scene()

    with fixed_dice_faces(10):
        Telekinesis(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=5,
        ).apply()

    available = get_available_actions(caster)
    restrain = next(
        row for row in available.all_actions
        if row.template_name == "Telekinesis: Restrain"
    )
    execute_by_index(
        caster,
        restrain.template_name,
        restrain.valid_targets[0].index,
        available=available,
    )
    assert has_condition(target, "Restrained")

    caster.remove_condition("Concentrating")

    assert not has_condition(target, "Restrained")
    assert caster.get_action_template("Telekinesis") is None


def _globe_scene() -> tuple[Entity, Entity, Entity]:
    reset_spell_regression_arena(24, 15)
    globe_caster = create_spell_regression_actor(
        "Globe Caster",
        (10, 7),
        "heroes",
        spell_slots={6: 1},
    )
    inside = create_spell_regression_actor(
        "Inside Ally",
        (11, 7),
        "heroes",
    )
    outside_caster = create_spell_regression_actor(
        "Outside Caster",
        (2, 7),
        "monsters",
        spell_slots={2: 1, 3: 2, 6: 1, 7: 1},
    )
    Entity.update_all_entities_senses(max_distance=120)
    result = GlobeOfInvulnerability(
        source_entity_uuid=globe_caster.uuid,
        cast_at_level=6,
    ).apply()
    assert isinstance(result, SpellEvent)
    assert not result.canceled
    return globe_caster, inside, outside_caster


def _active_globe_zone() -> GlobeZone:
    """Resolve the one independently owned active Globe condition."""
    matches = [
        condition
        for condition in get_map().get_spatial_conditions()
        if isinstance(condition, GlobeZone)
    ]
    assert len(matches) == 1
    return matches[0]


def test_globe_direction_level_and_concentration_contract() -> None:
    """Old cases 9-12, 14, and 16: direction, level, and cleanup are exact."""
    globe_caster, inside, outside_caster = _globe_scene()
    inside_hp = get_hp(inside)
    modifier_uuid = _force_attack_outcome(outside_caster, AutoHitStatus.AUTOHIT)

    blocked = FireBolt(
        source_entity_uuid=outside_caster.uuid,
        target_entity_uuid=inside.uuid,
    ).apply()

    assert isinstance(blocked, SpellEvent)
    assert blocked.canceled
    assert get_hp(inside) == inside_hp

    force_save_result(inside, "constitution", succeeds=False)
    outside_caster.action_economy.reset_all_costs()
    with fixed_dice_faces(10, *([4] * 7)):
        high_level = FingerOfDeath(
            source_entity_uuid=outside_caster.uuid,
            target_entity_uuid=inside.uuid,
            cast_at_level=7,
        ).apply()
    assert isinstance(high_level, SpellEvent)
    assert not high_level.canceled
    assert get_hp(inside) == inside_hp - 58

    inside_caster = create_spell_regression_actor(
        "Inside Caster",
        (9, 7),
        "heroes",
    )
    outside_target = create_spell_regression_actor(
        "Outside Target",
        (4, 7),
        "monsters",
    )
    Entity.update_all_entities_senses(max_distance=120)
    inside_modifier = _force_attack_outcome(inside_caster, AutoHitStatus.AUTOHIT)
    outside_hp = get_hp(outside_target)
    with fixed_dice_faces(10, 4):
        outbound = FireBolt(
            source_entity_uuid=inside_caster.uuid,
            target_entity_uuid=outside_target.uuid,
        ).apply()
    assert isinstance(outbound, SpellEvent)
    assert not outbound.canceled
    assert get_hp(outside_target) == outside_hp - 4
    _remove_attack_outcome(inside_caster, inside_modifier)

    globe_caster.remove_condition("Concentrating")
    assert not has_condition(globe_caster, "Globe of Invulnerability Zone")
    assert not any(
        isinstance(condition, GlobeZone)
        for condition in get_map().get_spatial_conditions()
    )
    outside_caster.action_economy.reset_all_costs()
    post_cleanup_hp = get_hp(inside)
    with fixed_dice_faces(10, 4):
        unblocked = FireBolt(
            source_entity_uuid=outside_caster.uuid,
            target_entity_uuid=inside.uuid,
        ).apply()
    assert isinstance(unblocked, SpellEvent)
    assert not unblocked.canceled
    assert get_hp(inside) == post_cleanup_hp - 4
    _remove_attack_outcome(outside_caster, modifier_uuid)


def test_globe_partially_filters_aoe_and_uses_base_spell_level() -> None:
    """Old cases 13 and 15: only protected targets are removed from an AoE."""
    _globe_caster, inside, outside_caster = _globe_scene()
    outside_target = create_spell_regression_actor(
        "Outside Ally",
        (14, 7),
        "heroes",
    )
    force_save_result(inside, "dexterity", succeeds=False)
    force_save_result(outside_target, "dexterity", succeeds=False)
    Entity.update_all_entities_senses(max_distance=120)
    inside_hp = get_hp(inside)
    outside_hp = get_hp(outside_target)

    with fixed_dice_faces(10, *([4] * 11)):
        result = Fireball(
            source_entity_uuid=outside_caster.uuid,
            end_position=(13, 7),
            cast_at_level=6,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert get_hp(inside) == inside_hp
    assert get_hp(outside_target) == outside_hp - 44
    _active_globe_zone()


def test_globe_is_immobile() -> None:
    """Old case 17: the protected geometry remains anchored at cast time."""
    globe_caster, inside, outside_caster = _globe_scene()
    zone = _active_globe_zone()
    original_positions = set(zone.affected_positions)

    Entity.update_entity_position(globe_caster, (20, 12))

    assert zone.position == (10, 7)
    assert set(zone.affected_positions) == original_positions
    inside_hp = get_hp(inside)
    modifier_uuid = _force_attack_outcome(outside_caster, AutoHitStatus.AUTOHIT)
    blocked = FireBolt(
        source_entity_uuid=outside_caster.uuid,
        target_entity_uuid=inside.uuid,
    ).apply()
    _remove_attack_outcome(outside_caster, modifier_uuid)
    assert isinstance(blocked, SpellEvent)
    assert blocked.canceled
    assert get_hp(inside) == inside_hp


def test_globe_excludes_low_level_zone_effects() -> None:
    """Old case 18: a low-level Web cannot apply inside the protected area."""
    _globe_caster, inside, outside_caster = _globe_scene()
    force_save_result(inside, "dexterity", succeeds=False)
    outside_caster.action_economy.reset_all_costs()

    with fixed_dice_faces(10):
        result = Web(
            source_entity_uuid=outside_caster.uuid,
            end_position=(12, 7),
            cast_at_level=2,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert not has_condition(inside, "Restrained")
    _active_globe_zone()


def _banishment_scene(*, save_succeeds: bool) -> tuple[Entity, Entity, Entity]:
    reset_spell_regression_arena(18, 9)
    caster = create_spell_regression_actor(
        "Banishment Caster",
        (2, 4),
        "heroes",
        spell_slots={4: 1},
    )
    target = create_spell_regression_actor(
        "Banishment Target",
        (7, 4),
        "monsters",
    )
    observer = create_spell_regression_actor(
        "Observer",
        (6, 5),
        "neutral",
    )
    force_save_result(target, "charisma", succeeds=save_succeeds)
    Entity.update_all_entities_senses(max_distance=100)
    return caster, target, observer


def test_banishment_removes_and_restores_spatial_perception() -> None:
    """Old cases 19-20: concentration owns grid and sensory removal/restore."""
    caster, target, observer = _banishment_scene(save_succeeds=False)
    original_position = target.position
    assert target.uuid in observer.senses.entities

    with fixed_dice_faces(10):
        result = Banishment(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=4,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert has_condition(target, "Banished")
    assert target.action_economy.action_permission.normalized_score == 0
    assert target not in Entity._entity_by_position[original_position]
    assert target.uuid not in observer.senses.entities
    assert has_condition(caster, "Concentrating")

    caster.remove_condition("Concentrating")

    assert not has_condition(target, "Banished")
    assert target.action_economy.action_permission.normalized_score == 1
    assert target in Entity._entity_by_position[original_position]
    assert target.uuid in observer.senses.entities


def test_banishment_return_displaces_an_occupant() -> None:
    """Old case 21: restoration preserves the banished target's exact cell."""
    caster, target, _observer = _banishment_scene(save_succeeds=False)
    original_position = target.position

    with fixed_dice_faces(10):
        Banishment(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=4,
        ).apply()

    occupant = create_spell_regression_actor(
        "Occupant",
        original_position,
        "neutral",
    )
    caster.remove_condition("Concentrating")

    assert target.position == original_position
    assert occupant.position != original_position
    assert max(
        abs(occupant.position[0] - original_position[0]),
        abs(occupant.position[1] - original_position[1]),
    ) == 1


def test_banishment_successful_save_preserves_spatial_state() -> None:
    """Old case 22: a successful Charisma save applies no removal."""
    caster, target, observer = _banishment_scene(save_succeeds=True)
    original_position = target.position

    with fixed_dice_faces(10):
        result = Banishment(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=4,
        ).apply()

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert not has_condition(target, "Banished")
    assert not has_condition(caster, "Concentrating")
    assert target in Entity._entity_by_position[original_position]
    assert target.uuid in observer.senses.entities
