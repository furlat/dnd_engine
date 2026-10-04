"""One paid telekinetic transfer ends on support and retains only repeat permission."""

import pytest

from dnd.actions import Shove, Jump, SpellEvent
from dnd.items.environment import DirectionalWall
from dnd.spells.evocation import Thunderwave
from dnd.spells.conjuration import MistyStep
from dnd.spells.abjuration import SanctuaryEffect
from dnd.core.modifiers import NumericalModifier, ResistanceModifier, ResistanceStatus
from dnd.types.event_facts import LandingKind
from dnd.types.world import CardinalDirection, WorldEdgeChannel, OccupancyLayer
from dnd.core.creature_types import Size, DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import DamageAppliedEvent, ForcedMovementEvent, SpatialChangeEvent, SpatialChangeType, SavingThrowEvent, TakeDamageEvent, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.transmutation import Telekinesis
from dnd.core.world_edges import ElevationSurfaceKind
from tests.manual.spell_regression_support import (
    create_spell_regression_actor, force_save_result, reset_spell_regression_arena,
)


@pytest.fixture
def scene():
    reset_spell_regression_arena(24, 10)
    caster = create_spell_regression_actor("Caster", (2, 2), "heroes", spell_slots={5: 2})
    target = create_spell_regression_actor("Target", (4, 2), "enemies")
    force_save_result(target, "strength", succeeds=False)
    force_save_result(target, "dexterity", succeeds=False)
    Entity.update_all_entities_senses(max_distance=125)
    yield caster, target
    reset_engine_runtime()


def cast(caster, target, destination):
    with fixed_dice_faces(*([2] * 64)):
        result = Telekinesis(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
            end_position=destination).apply()
    assert result is not None
    return result


def damage_since(cursor):
    return [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, DamageAppliedEvent) and event.phase is EventPhase.COMPLETION]


def test_initial_and_repeat_each_pay_one_action_and_only_initial_pays_slot(scene):
    caster, target = scene
    target.faction = caster.faction
    before = target.get_normal_hp()
    result = cast(caster, target, (7, 2))
    assert result is not None and not result.canceled
    assert target.position == (7, 2) and target.get_normal_hp() == before
    assert "Prone" not in target.active_conditions and "Restrained" not in target.active_conditions
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_5.normalized_score == 1
    repeat = caster.get_action_template("Telekinesis: Move")
    assert repeat is not None
    caster.action_economy.reset_all_costs()
    with fixed_dice_faces(*([2] * 64)):
        moved = repeat.instantiate(target_entity_uuid=target.uuid, end_position=(8, 2)).apply()
    assert moved is not None and not moved.canceled
    assert target.position == (8, 2)
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_5.normalized_score == 1
    assert caster.get_action_template("Telekinesis: Restrain") is None


@pytest.mark.parametrize("dexterity_succeeds", [False, True])
def test_hostile_landing_keeps_full_damage_and_uses_dexterity_only_for_prone(scene, dexterity_succeeds):
    caster, target = scene
    if dexterity_succeeds:
        force_save_result(target, "dexterity", succeeds=True)
        force_save_result(target, "dexterity", succeeds=True)
    before = target.get_normal_hp()
    cursor = EventQueue.event_cursor()
    result = cast(caster, target, (7, 2))
    assert result is not None and not result.canceled
    assert target.position == (7, 2) and before - target.get_normal_hp() == 12
    assert ("Prone" in target.active_conditions) is not dexterity_succeeds
    assert "Restrained" not in target.active_conditions and "Stunned" not in target.active_conditions
    damage = damage_since(cursor)
    assert [event.applied_damage for event in damage] == [8, 4]
    assert all(event.source_entity_uuid == caster.uuid for event in damage)


def test_resisted_initial_cast_still_grants_paid_repeat(scene):
    caster, target = scene
    force_save_result(target, "strength", succeeds=True)
    force_save_result(target, "strength", succeeds=True)
    cursor = EventQueue.event_cursor()
    result = cast(caster, target, (7, 2))
    assert result is not None and not result.canceled
    assert target.position == (4, 2) and not damage_since(cursor)
    assert caster.get_action_template("Telekinesis: Move") is not None
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_5.normalized_score == 1


@pytest.mark.parametrize("invalid", ["missing", "occupied", "displacement", "range", "size"])
def test_invalid_selection_is_rejected_before_spending(scene, invalid):
    caster, target = scene
    destination = None if invalid == "missing" else (12, 2) if invalid == "displacement" else (18, 2) if invalid == "range" else (7, 2)
    if invalid == "occupied":
        assert destination is not None
        create_spell_regression_actor("Occupant", destination, "heroes")
    elif invalid == "size":
        target.size = Size.GARGANTUAN
    Entity.update_all_entities_senses(max_distance=125)
    result = cast(caster, target, destination)
    assert result is None or result.canceled
    assert caster.action_economy.actions.normalized_score == 1
    assert caster.action_economy.spell_slot_5.normalized_score == 2
    assert caster.get_action_template("Telekinesis: Move") is None


@pytest.mark.parametrize("ending", ["concentration", "expiry"])
def test_ending_permission_removes_only_its_repeat_and_stale_copy_cannot_move(scene, ending):
    caster, target = scene
    target.faction = caster.faction
    result = cast(caster, target, (7, 2))
    assert result is not None and not result.canceled
    repeat = caster.get_action_template("Telekinesis: Move")
    assert repeat is not None
    stale = repeat.instantiate(target_entity_uuid=target.uuid, end_position=(8, 2))
    if ending == "concentration":
        caster.remove_condition("Concentrating")
    else:
        for _ in range(100):
            caster.advance_duration("Telekinesis")
    assert caster.get_action_template("Telekinesis: Move") is None
    caster.action_economy.reset_all_costs()
    result = stale.apply()
    assert result is None or result.canceled
    assert target.position == (7, 2)
    assert caster.action_economy.actions.normalized_score == 1


def test_zero_distance_and_canceled_movement_have_no_impact(scene):
    caster, target = scene
    cursor = EventQueue.event_cursor()
    result = cast(caster, target, target.position)
    assert result is not None and not result.canceled
    assert not damage_since(cursor) and "Prone" not in target.active_conditions
    repeat = caster.get_action_template("Telekinesis: Move")
    assert repeat is not None
    target.add_event_handler(EventHandler(name="Reject transfer", source_entity_uuid=target.uuid,
        trigger_conditions=[Trigger(event_type=EventType.FORCED_MOVEMENT, event_phase=EventPhase.EXECUTION)],
        event_processor=lambda event, _: event.cancel(status_message="Transfer prevented")))
    caster.action_economy.reset_all_costs()
    with fixed_dice_faces(*([2] * 64)):
        repeat.instantiate(target_entity_uuid=target.uuid, end_position=(7, 2)).apply()
    assert target.position == (4, 2) and not damage_since(cursor)


@pytest.mark.parametrize("drop_feet", [0, 10, 20])
@pytest.mark.parametrize("allied", [False, True])
def test_only_actual_lower_support_adds_fall_damage_and_allies_are_controlled(scene, drop_feet, allied):
    caster, target = scene
    if allied:
        target.faction = caster.faction
    for x in range(2, 5):
        get_map().set_tile_elevation((x, 2), height=drop_feet // 5,
            surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)
    Entity.update_all_entities_senses(max_distance=125)
    before = target.get_normal_hp()
    result = cast(caster, target, (7, 2))
    assert result is not None and not result.canceled
    assert target.position == (7, 2)
    assert before - target.get_normal_hp() == (0 if allied else 12 + 2 * (drop_feet // 10))
    assert ("Prone" in target.active_conditions) is not allied


def raise_support(positions, feet):
    for position in positions:
        get_map().set_tile_elevation(position, height=feet // 5,
            surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)


def forced_events_since(cursor):
    return [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, ForcedMovementEvent) and event.phase is EventPhase.COMPLETION]


@pytest.mark.parametrize("drop_feet", [5, 10, 20, 250])
def test_shove_off_supported_ledge_stops_at_landing_and_caps_actual_fall(scene, drop_feet):
    caster, target = scene
    target.faction = caster.faction
    Entity.update_entity_position(caster, (3, 2))
    raise_support([(3, 2), (4, 2)], drop_feet)
    Entity.update_all_entities_senses(max_distance=300)
    before = target.get_normal_hp()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([2] * 64)):
        result = Shove(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid).apply()
    assert result is not None and not result.canceled
    assert target.position == (5, 2)
    assert before - target.get_normal_hp() == min(20, drop_feet // 10) * 2
    assert ("Prone" in target.active_conditions) is (drop_feet >= 10)
    movement, = forced_events_since(cursor)
    assert movement.landing_kind is LandingKind.FALL
    assert movement.drop_feet == drop_feet
    assert movement.disclosed_path == ((4, 2), (5, 2))
    assert (movement.start_elevation_feet, movement.end_elevation_feet) == (drop_feet, 0)
    assert not get_map().can_transition((4, 2), (5, 2), target.uuid)


@pytest.mark.parametrize("blocker", ["wall", "occupied", "missing"])
def test_blocked_ledge_has_no_sideways_fallback_or_fall(scene, blocker):
    caster, target = scene
    target.faction = caster.faction
    Entity.update_entity_position(caster, (3, 2))
    raise_support([(3, 2), (4, 2)], 20)
    if blocker == "wall":
        wall = DirectionalWall(item_id="test.landing.wall", source_entity_uuid=caster.uuid,
            blocked_channels=(WorldEdgeChannel.MOVEMENT,))
        wall.place_on_grid((4, 2), boundary_direction=CardinalDirection.EAST)
    elif blocker == "occupied":
        create_spell_regression_actor("Occupied landing", (5, 2), "enemies")
    else:
        get_map().remove_tile(5, 2)
    Entity.update_all_entities_senses(max_distance=125)
    before = target.get_normal_hp()
    with fixed_dice_faces(*([2] * 64)):
        result = Shove(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid).apply()
    assert result is not None and not result.canceled
    assert target.position == (4, 2) and target.get_normal_hp() == before
    assert "Prone" not in target.active_conditions


def test_downward_jump_uses_actual_support_loss_once(scene):
    _, target = scene
    raise_support([target.position], 10)
    Entity.update_all_entities_senses(max_distance=125)
    before = target.get_normal_hp()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([2] * 64)):
        result = Jump(source_entity_uuid=target.uuid, end_position=(6, 2)).apply()
    assert result is not None and not result.canceled
    assert target.position == (6, 2)
    assert before - target.get_normal_hp() == 2
    assert "Prone" in target.active_conditions
    assert len(damage_since(cursor)) == 1


@pytest.mark.parametrize('immune', [False, True])
def test_fall_absorbed_by_temporary_hp_still_knocks_prone_unless_no_damage(scene, immune):
    caster, target = scene
    target.faction = caster.faction
    Entity.update_entity_position(caster, (3, 2))
    raise_support([(3, 2), (4, 2)], 10)
    target.health.add_temporary_hit_points(10, target.uuid)
    if immune:
        target.health.damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(
            name='No bludgeoning damage', value=ResistanceStatus.IMMUNITY,
            damage_type=DamageType.BLUDGEONING, source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid))
    Entity.update_all_entities_senses(max_distance=125)
    before = target.get_normal_hp()
    with fixed_dice_faces(*([2] * 64)):
        result = Shove(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid).apply()
    assert result is not None and not result.canceled
    assert target.position == (5, 2) and target.get_normal_hp() == before
    assert target.health.temporary_hit_points.normalized_score == (10 if immune else 8)
    assert ('Prone' in target.active_conditions) is not immune


def test_thunderwave_uses_same_ledge_landing(scene):
    caster, target = scene
    Entity.update_entity_position(caster, (3, 2))
    raise_support([(3, 2), (4, 2)], 20)
    force_save_result(target, "constitution", succeeds=False)
    Entity.update_all_entities_senses(max_distance=125)
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([2] * 64)):
        result = Thunderwave(source_entity_uuid=caster.uuid, end_position=(5, 2),
            cast_at_level=5).apply()
    assert result is not None and not result.canceled
    assert target.position == (5, 2)
    landing, = forced_events_since(cursor)
    assert landing.drop_feet == 20 and landing.landing_kind is LandingKind.FALL
    assert any(event.applied_damage == 4 for event in damage_since(cursor))


def test_recast_replaces_exact_repeat_without_stale_action_authority(scene):
    caster, target = scene
    target.faction = caster.faction
    assert not cast(caster, target, (7, 2)).canceled
    old = caster.get_action_template("Telekinesis: Move")
    assert old is not None
    stale = old.instantiate(target_entity_uuid=target.uuid, end_position=(9, 2))
    caster.action_economy.reset_all_costs()
    assert not cast(caster, target, (8, 2)).canceled
    current = caster.get_action_template("Telekinesis: Move")
    assert current is not None and current.uuid != old.uuid
    caster.action_economy.reset_all_costs()
    rejected = stale.apply()
    assert rejected is None or rejected.canceled
    assert caster.action_economy.actions.normalized_score == 1
    assert caster.get_action_template("Telekinesis: Move").uuid == current.uuid


@pytest.mark.parametrize("distance", [0, 5])
def test_shortened_transfer_has_one_actual_contact_and_no_canceled_impact(scene, distance):
    caster, target = scene
    target.add_event_handler(EventHandler(name="Shorten transfer", source_entity_uuid=target.uuid,
        trigger_conditions=[Trigger(event_type=EventType.FORCED_MOVEMENT, event_phase=EventPhase.EFFECT)],
        event_processor=lambda event, _: event.with_updates(actual_distance=distance)))
    before = target.get_normal_hp()
    cursor = EventQueue.event_cursor()
    result = cast(caster, target, (7, 2))
    assert result is not None and not result.canceled
    assert target.position == ((5, 2) if distance else (4, 2))
    assert before - target.get_normal_hp() == (12 if distance else 0)
    movement, = forced_events_since(cursor)
    assert movement.actual_distance == distance and movement.end_position == target.position
    contacts = [event.position for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent) and event.phase is EventPhase.COMPLETION
        and event.change_type is SpatialChangeType.ENTITY_ENTERED
        and event.entity_uuid == target.uuid and event.occupancy_layer is OccupancyLayer.GROUND]
    assert contacts == ([(5, 2)] if distance else [])


def test_repeat_uses_original_dc_and_damage_origin(scene):
    caster, target = scene
    target.faction = caster.faction
    original_dc = caster.spell_save_dc()
    assert not cast(caster, target, (7, 2)).canceled
    repeat = caster.get_action_template("Telekinesis: Move")
    assert repeat is not None
    origin = caster.active_conditions["Telekinesis"].effect_origin
    caster.spellcasting.spell_dc_bonus.self_static.add_value_modifier(NumericalModifier.create(
        source_entity_uuid=caster.uuid, name="Changed DC", value=5))
    assert caster.spell_save_dc() == original_dc + 5
    target.faction = "enemies"
    caster.action_economy.reset_all_costs()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([2] * 64)):
        repeat.instantiate(target_entity_uuid=target.uuid, end_position=(8, 2)).apply()
    saves = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SavingThrowEvent) and event.phase is EventPhase.COMPLETION]
    assert [event.get_dc() for event in saves] == [original_dc, original_dc]
    impacts = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, TakeDamageEvent) and event.phase is EventPhase.COMPLETION]
    assert len(impacts) == 2 and all(event.effect_origin == origin for event in impacts)
    activation, = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpellEvent) and event.phase is EventPhase.COMPLETION]
    assert activation.event_type is EventType.BASE_ACTION and not activation.verbal
    assert activation.get_effect_origin() == origin
    assert activation.cast_at_level == 5


def test_teleport_to_lower_support_is_controlled(scene):
    caster, _ = scene
    raise_support([caster.position], 20)
    Entity.update_all_entities_senses(max_distance=125)
    before = caster.get_normal_hp()
    result = MistyStep(source_entity_uuid=caster.uuid, end_position=(5, 2), cast_at_level=5).apply()
    assert result is not None and not result.canceled
    assert caster.position == (5, 2) and caster.get_normal_hp() == before
    assert "Prone" not in caster.active_conditions


def test_fall_defenses_prevent_ordinary_prone_when_no_damage_is_taken(scene):
    caster, target = scene
    target.faction = caster.faction
    Entity.update_entity_position(caster, (3, 2))
    raise_support([(3, 2), (4, 2)], 10)
    target.health.damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(
        source_entity_uuid=target.uuid, target_entity_uuid=target.uuid,
        damage_type=DamageType.BLUDGEONING, value=ResistanceStatus.IMMUNITY, name="Test immunity"))
    Entity.update_all_entities_senses(max_distance=125)
    before = target.get_normal_hp()
    with fixed_dice_faces(*([2] * 64)):
        result = Shove(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid).apply()
    assert result is not None and not result.canceled
    assert target.position == (5, 2) and target.get_normal_hp() == before
    assert "Prone" not in target.active_conditions


def test_telekinesis_cannot_claim_unselected_extra_creatures(scene):
    caster, target = scene
    extra = create_spell_regression_actor("Extra creature", (5, 3), "heroes")
    Entity.update_all_entities_senses(max_distance=125)
    result = Telekinesis(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
        extra_target_entity_uuids=[extra.uuid], end_position=(7, 2)).apply()
    assert result is None or result.canceled
    assert caster.action_economy.actions.normalized_score == 1
    assert caster.action_economy.spell_slot_5.normalized_score == 2


@pytest.mark.parametrize("repeat_hostile", [False, True])
def test_sanctuary_allows_safe_allies_and_checks_hostile_repeat(scene, repeat_hostile):
    caster, target = scene
    target.faction = caster.faction
    force_save_result(caster, "wisdom", succeeds=False)
    if repeat_hostile:
        assert not cast(caster, target, (7, 2)).canceled
        target.faction = "enemies"
    target.add_condition(SanctuaryEffect(source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid, spell_dc=15))
    caster.action_economy.reset_all_costs()
    if repeat_hostile:
        repeat = caster.get_action_template("Telekinesis: Move")
        assert repeat is not None
        with fixed_dice_faces(*([2] * 64)):
            result = repeat.instantiate(target_entity_uuid=target.uuid, end_position=(8, 2)).apply()
        assert result is not None and result.canceled
        assert target.position == (7, 2)
        assert caster.action_economy.actions.normalized_score == 1
    else:
        assert not cast(caster, target, (7, 2)).canceled
        assert target.position == (7, 2)
