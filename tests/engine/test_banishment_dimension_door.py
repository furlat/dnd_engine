"""Paid absence/teleport commands preserve identity, clocks and committed outcomes."""

import pytest

from dnd.actions_functional import execute_available_action, get_available_actions, get_extra_position_options, register_spell
from dnd.conditions import Concentrating, Poisoned
from dnd.core.base_conditions import Duration
from dnd.core.condition_types import DurationType
from dnd.core.creature_types import Size, DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, PortalTransferEvent, Trigger
from dnd.core.gridmap import get_map
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.entity import Entity
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.abjuration import AntimagicField, Banishment
from dnd.spells.conjuration import DimensionDoor
from dnd.types.actor import SpatialDisposition
from tests.manual.spell_regression_support import create_spell_regression_actor, force_save_result, reset_spell_regression_arena


@pytest.fixture
def scene():
    reset_spell_regression_arena(18, 8)
    caster = create_spell_regression_actor("Caster", (2, 2), "heroes", spell_slots={4: 3, 5: 1})
    companion = create_spell_regression_actor("Companion", (3, 2), "heroes")
    enemy = create_spell_regression_actor("Enemy", (5, 2), "enemies")
    force_save_result(enemy, "charisma", succeeds=False)
    Entity.update_all_entities_senses(max_distance=125)
    yield caster, companion, enemy
    reset_engine_runtime()


def door(caster, companion, destination):
    with fixed_dice_faces(*([2] * 80)):
        return DimensionDoor(source_entity_uuid=caster.uuid, target_entity_uuid=companion.uuid,
            end_position=destination).apply()


def banish(caster, target, *, extra=()):
    with fixed_dice_faces(*([2] * 80)):
        result = Banishment(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
            extra_target_entity_uuids=list(extra), cast_at_level=5 if extra else 4).apply()
    assert result is not None and not result.canceled
    return result


@pytest.mark.parametrize("with_companion", [False, True])
def test_dimension_door_commits_all_travelers_before_arrival_reactions(scene, with_companion):
    caster, companion, _ = scene
    item = build_authored_item("weapon.club", companion.uuid)
    assert companion.loot_item(item)
    destination = (12, 2)
    for point in (destination, (13, 2)):
        get_map().set_tile_elevation(point, height=2,
            surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)
    Entity.update_all_entities_senses(max_distance=125)
    observed = []
    def arrival(event, _):
        observed.append((caster.position, companion.position))
        return None
    caster.add_event_handler(EventHandler(name="Observe atomic arrival", source_entity_uuid=caster.uuid,
        event_processor=arrival, trigger_conditions=[Trigger(event_type=EventType.SPATIAL_ENTITY_ENTERED,
            event_phase=EventPhase.EFFECT, event_source_entity_uuid=caster.uuid)]))
    cursor = EventQueue.event_cursor()
    result = door(caster, companion if with_companion else caster, destination)
    assert result is not None and not result.canceled
    expected_companion = (13, 2) if with_companion else (3, 2)
    assert (caster.position, companion.position) == (destination, expected_companion)
    assert observed and all(row == (destination, expected_companion) for row in observed)
    assert item.uuid in companion.inventory.items
    transfers = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, PortalTransferEvent) and event.phase is EventPhase.COMPLETION]
    assert len(transfers) == (2 if with_companion else 1)
    assert all(event.committed and event.portal_uuid is None for event in transfers)
    assert len({event.parent_event for event in transfers}) == 1
    assert all(event.effect_origin is not None and event.effect_origin.source_id == "dimension_door" for event in transfers)
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_4.normalized_score == 2


@pytest.mark.parametrize("blocker", ["occupant", "support", "missing"])
def test_unseen_destination_is_selectable_and_paid_mishap_damages_both(scene, blocker):
    caster, companion, enemy = scene
    destination = (16, 6)
    if blocker == "occupant":
        Entity.update_entity_position(enemy, destination)
    elif blocker == "support":
        get_map().set_tile(*destination, walking_cost=0)
    else:
        get_map().remove_tile(*destination)
    for y in range(8):
        get_map().set_tile(9, y, walking_cost=0, blocks_optics=True)
    Entity.update_all_entities_senses(max_distance=125)
    assert not caster.senses.visible.get(destination, False)
    register_spell(caster, DimensionDoor)
    actions = get_available_actions(caster)
    row = next(row for row in actions.entity_actions if row.behavior_id == "spell.dimension_door")
    selected = next(option for option in row.valid_targets if option.target_uuid == companion.uuid)
    assert destination in get_extra_position_options(caster, row, selected)
    hp = caster.get_normal_hp(), companion.get_normal_hp()
    with fixed_dice_faces(*([2] * 80)):
        result = execute_available_action(caster, row, selected, extra_target_positions=[destination])
    assert result is not None and not result.canceled
    assert (caster.position, companion.position) == ((2, 2), (3, 2))
    assert (caster.get_normal_hp(), companion.get_normal_hp()) == (hp[0] - 8, hp[1] - 8)
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_4.normalized_score == 2


@pytest.mark.parametrize("invalid", ["unwilling", "large", "far", "outside"])
def test_invalid_companion_or_coordinate_rejects_before_payment(scene, invalid):
    caster, companion, enemy = scene
    target = enemy if invalid == "unwilling" else companion
    if invalid == "large":
        companion.size = Size.LARGE
    if invalid == "far":
        Entity.update_entity_position(companion, (4, 2))
    Entity.update_all_entities_senses(max_distance=125)
    result = door(caster, target, (100, 100) if invalid == "outside" else (12, 2))
    assert result is not None and result.canceled
    assert caster.position == (2, 2)
    assert caster.action_economy.actions.normalized_score == 1
    assert caster.action_economy.spell_slot_4.normalized_score == 3


def test_rejected_passenger_cannot_partially_teleport_caster(scene):
    caster, companion, _ = scene
    companion.add_event_handler(EventHandler(name="Prevent transfer", source_entity_uuid=companion.uuid,
        event_processor=lambda event, _: event.cancel(status_message="Prevented"),
        trigger_conditions=[Trigger(event_type=EventType.PORTAL_TRANSFER, event_phase=EventPhase.EXECUTION,
            event_target_entity_uuid=companion.uuid)]))
    result = door(caster, companion, (12, 2))
    assert result is not None and not result.canceled
    assert (caster.position, companion.position) == ((2, 2), (3, 2))
    assert caster.action_economy.spell_slot_4.normalized_score == 2


@pytest.mark.parametrize("destination,blocked", [((8, 4), True), ((5, 2), True), ((12, 2), False)])
def test_dimension_door_checks_each_actual_endpoint_not_intervening_space(scene, destination, blocked):
    caster, companion, _ = scene
    field_owner = create_spell_regression_actor("Field", (8, 2), "enemies", spell_slots={8: 1})
    field = AntimagicField(source_entity_uuid=field_owner.uuid).apply()
    assert field is not None and not field.canceled
    result = door(caster, companion, destination)
    assert result is not None
    if blocked:
        assert (caster.position, companion.position) == ((2, 2), (3, 2))
    else:
        assert (caster.position, companion.position) == ((12, 2), (13, 2))
    assert caster.action_economy.spell_slot_4.normalized_score == 2


@pytest.mark.parametrize("foreign", [False, True])
@pytest.mark.parametrize("ending", ["early", "duration"])
def test_banishment_plane_branch_and_duration_preserve_identity_and_inventory(scene, foreign, ending):
    caster, _, target = scene
    target.native_plane_id = "abyss" if foreign else "material"
    item = build_authored_item("weapon.club", target.uuid)
    assert target.loot_item(item)
    target.add_condition(Concentrating(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid,
        spell_name="Retained concentration"))
    banish(caster, target)
    assert Entity.get(target.uuid) is target and not target.is_deployed and target.is_spatially_suspended
    assert item.uuid in target.inventory.items
    assert ("Concentrating" in target.active_conditions) is foreign
    assert target.action_economy.action_permission.normalized_score == int(foreign)
    assert target.current_plane_id == ("abyss" if foreign else "banishment_demiplane")
    if ending == "early":
        caster.remove_condition("Concentrating")
    else:
        for _ in range(10):
            target.on_turn_start()
    permanent = foreign and ending == "duration"
    assert target.is_deployed is not permanent
    assert target.is_spatially_suspended is permanent
    assert target.current_plane_id == ("abyss" if permanent else "material")
    assert target.spatial_disposition is (SpatialDisposition.HOME_PLANE if permanent else SpatialDisposition.PRESENT)
    assert "Banished" not in target.active_conditions
    assert item.uuid in target.inventory.items


def test_banishment_returns_nearest_without_moving_original_occupant(scene):
    caster, companion, target = scene
    origin = target.position
    banish(caster, target)
    Entity.update_entity_position(companion, origin)
    caster.remove_condition("Concentrating")
    assert companion.position == origin and target.position != origin
    assert max(abs(target.position[i] - origin[i]) for i in (0, 1)) == 1
    assert target.is_deployed and get_map().get_entities_at(origin) == {companion.uuid}


def test_banishment_keeps_pending_return_until_occupancy_changes(scene):
    caster, companion, target = scene
    banish(caster, target)
    # Retain only occupied support; absence must not prevent concentration ending.
    for point in list(get_map().get_all_tiles()):
        if point not in (caster.position, companion.position):
            get_map().remove_tile(*point)
    assert caster.remove_condition("Concentrating")
    assert "Banished" not in target.active_conditions and "Concentrating" not in caster.active_conditions
    assert target.pending_spatial_return is not None
    assert target.spatial_disposition is SpatialDisposition.RETURN_PENDING
    companion.suspend_spatial_presence()
    assert target.is_deployed and target.position == companion.position
    assert target.pending_spatial_return is None and target.pending_spatial_return_handler_uuid is None


def test_upcast_banishment_reserves_distinct_returns_in_one_concentration_release(scene):
    caster, companion, target = scene
    companion.faction = "enemies"
    force_save_result(companion, "charisma", succeeds=False)
    Entity.update_all_entities_senses(max_distance=125)
    banish(caster, target, extra=(companion.uuid,))
    assert target.is_spatially_suspended and companion.is_spatially_suspended
    assert "Banished" in target.active_conditions and "Banished" in companion.active_conditions
    occupied = target.position, companion.position
    blockers = [create_spell_regression_actor(f"Blocker {i}", point, "heroes") for i, point in enumerate(occupied)]
    assert caster.remove_condition("Concentrating")
    assert target.is_deployed and companion.is_deployed and target.position != companion.position
    assert all(actor.position == point for actor, point in zip(blockers, occupied))


def test_dimension_door_mishap_can_kill_caster_without_canceling_passenger_damage(scene):
    caster, companion, enemy = scene
    caster.receive_damage(caster.get_normal_hp() - 4, DamageType.FORCE, enemy.uuid)
    hp = companion.get_normal_hp()
    result = door(caster, companion, enemy.position)
    assert result is not None and not result.canceled
    assert caster.get_normal_hp() <= 0 and companion.get_normal_hp() == hp - 8
    assert caster.position == (2, 2) and companion.position == (3, 2)


def test_dimension_door_unseen_open_space_succeeds_but_out_of_range_rejects(scene):
    caster, companion, _ = scene
    for y in range(8):
        get_map().set_tile(9, y, walking_cost=0, blocks_optics=True)
    get_map().set_tile(105, 2)
    Entity.update_all_entities_senses(max_distance=125)
    assert not caster.senses.visible.get((12, 2), False)
    rejected = door(caster, caster, (105, 2))
    assert rejected is not None and rejected.canceled
    assert caster.action_economy.spell_slot_4.normalized_score == 3
    result = door(caster, companion, (12, 2))
    assert result is not None and not result.canceled
    assert caster.position == (12, 2) and companion.position == (13, 2)


def test_banishment_resistance_spends_cast_and_absence_keeps_other_duration_clock(scene):
    caster, _, target = scene
    force_save_result(target, "charisma", succeeds=True)
    force_save_result(target, "charisma", succeeds=True)
    banish(caster, target)
    assert target.is_deployed and "Banished" not in target.active_conditions
    assert caster.action_economy.spell_slot_4.normalized_score == 2
    force_save_result(target, "charisma", succeeds=False)
    force_save_result(target, "charisma", succeeds=False)
    target.add_condition(Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
        duration=Duration(duration_type=DurationType.ROUNDS, duration=2)))
    caster.action_economy.reset_all_costs()
    banish(caster, target)
    target.on_turn_start()
    target.on_turn_start()
    assert "Poisoned" not in target.active_conditions
    assert target.active_conditions["Banished"].duration.duration == 8
    assert target.is_spatially_suspended and not target.has_runtime_agency()


def test_banishment_can_select_allies_and_self_and_self_incapacitation_ends_its_cast(scene):
    caster, companion, _ = scene
    force_save_result(caster, "charisma", succeeds=False)
    force_save_result(companion, "charisma", succeeds=False)
    register_spell(caster, Banishment)
    choices = get_available_actions(caster)
    row = next(row for row in choices.entity_actions
        if row.behavior_id == "spell.banishment" and row.cast_at_level == 4)
    assert {caster.uuid, companion.uuid} <= {option.target_uuid for option in row.valid_targets}
    banish(caster, caster)
    assert caster.is_deployed and caster.current_plane_id == "material"
    assert "Banished" not in caster.active_conditions and "Concentrating" not in caster.active_conditions
    assert caster.action_economy.spell_slot_4.normalized_score == 2


def test_dimension_door_discovery_has_alone_choice_without_disclosing_destination_blockers(scene):
    caster, companion, enemy = scene
    register_spell(caster, DimensionDoor)
    row = next(row for row in get_available_actions(caster).entity_actions
        if row.behavior_id == "spell.dimension_door")
    assert {option.target_uuid for option in row.valid_targets} == {caster.uuid, companion.uuid}
    alone = next(option for option in row.valid_targets if option.target_uuid == caster.uuid)
    assert enemy.position in get_extra_position_options(caster, row, alone)


@pytest.mark.parametrize("self_first", [False, True])
def test_self_banishment_ends_every_target_in_the_same_upcast(scene, self_first):
    caster, _, enemy = scene
    force_save_result(caster, "charisma", succeeds=False)
    first, second = (caster, enemy) if self_first else (enemy, caster)
    banish(caster, first, extra=(second.uuid,))
    assert caster.is_deployed and enemy.is_deployed
    assert "Banished" not in caster.active_conditions and "Banished" not in enemy.active_conditions
    assert "Concentrating" not in caster.active_conditions
    assert caster.action_economy.spell_slot_5.normalized_score == 0
