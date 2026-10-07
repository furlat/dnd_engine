"""Native owner clocks and authorized spatial evidence survive public replay."""

from uuid import uuid4

import pytest

from dnd.actions_functional import execute_use_action
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.base_conditions import Duration
from dnd.core.condition_types import DurationType
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.consumables import build_timed_fire_weapon_coat
from dnd.player.audience import PlayerAudience
from dnd.player.capture import capture_interval, capture_lineages
from dnd.player.projection import begin_projection, project_lineage
from dnd.player.reduction import reduce_initialization, reduce_lineage
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.conjuration import (
    GreaseZone, GuardianOfFaithZone, HeroesFeastLifetime,
    build_guardian_of_faith_object, build_heroes_feast_object,
)


@pytest.fixture
def world():
    reset_engine_runtime()
    game = Game()
    try:
        yield game
    finally:
        game.close()
        reset_engine_runtime()


def actor(game, name, position):
    value = Entity.create(uuid4(), name, config=EntityConfig(position=position))
    value.compose_entity()
    game.deploy_entity(value, position)
    return value


def view(built, members):
    audience = PlayerAudience(tuple(member.uuid for member in members), tuple(member.uuid for member in members))
    projection, initial = begin_projection(capture_interval(name="duration review", start_cursor=0,
        end_cursor=EventQueue.event_cursor(), observer_uuid=members[0].uuid,
        audience=audience, battlefield_id=built.definition.battlefield_id))
    return projection, reduce_initialization(initial)


def consume(projection, state, roots):
    delivered = []
    for native in capture_lineages(roots, observer_uuid=state.observer_uuid,
            audience=state.viewing_audience, known_actor_uuids=frozenset(state.actors)):
        public = project_lineage(projection, native)
        if public is not None:
            delivered.append(public)
            state = reduce_lineage(state, public)
    return state, delivered


def activate(zone, owner):
    cause = Event(source_entity_uuid=owner.uuid, event_type=EventType.BASE_ACTION, phase=EventPhase.EXECUTION)
    zone.activate(parent_event=cause)
    return cause.phase_to(EventPhase.COMPLETION)


def test_item_duration_survival_updates_owned_equipment_without_reapplying(world):
    built = build_battlefield("battlefield.open_floor_bright")
    owner = actor(world, "Owner", (5, 5))
    weapon = build_authored_item("weapon.dagger", owner.uuid)
    assert owner.loot_item(weapon) and owner.equip_item(weapon.uuid, WeaponSlot.MELEE_MAIN)
    coating = build_timed_fire_weapon_coat(owner.uuid, rounds=3)
    assert owner.loot_item(coating)
    applied = execute_use_action(owner, coating.uuid, "Coat Main Hand")
    assert applied is not None and not applied.canceled
    condition = weapon.active_conditions["Flaming Coat"]
    projection, state = view(built, (owner,))
    encounter_uuid = uuid4()
    turn = owner.on_turn_start(encounter_uuid, round_number=1)
    state, _ = consume(projection, state, (turn,))
    item = next(item for item in state.actors[owner.uuid].controlled_items if item.item_uuid == weapon.uuid)
    effect = next(effect for effect in item.item_effects if effect.effect_uuid == condition.uuid)
    assert condition.duration.duration == 2
    assert effect.duration is not None and effect.duration.remaining_rounds == 2
    assert len(weapon.get_extra_damages()) == 1
    owner.on_turn_start(encounter_uuid, round_number=1)
    assert condition.duration.duration == 2


def test_party_combines_disjoint_observations_of_one_spatial_effect(world):
    built = build_battlefield("battlefield.visibility_doorway_closed")
    first = actor(world, "First", (5, 7))
    second = actor(world, "Second", (8, 7))
    projection, state = view(built, (first, second))
    positions = {(5, 6), (8, 6)}
    zone = GreaseZone(source_entity_uuid=first.uuid, position=(5, 6), affected_positions=positions,
        duration=Duration(duration_type=DurationType.ROUNDS, duration=3))
    root = activate(zone, first)
    state, _ = consume(projection, state, (root,))
    assert state.senses is not None
    assert set(state.senses.spatial_effects[zone.uuid].positions) == positions
    # Changing only the first room must retain the second member's admitted
    # cells while correlating both slices of the same owner revision.
    positions = positions | {(4, 6)}
    cause = Event(source_entity_uuid=first.uuid, event_type=EventType.BASE_ACTION, phase=EventPhase.EXECUTION)
    assert zone.change_footprint(positions, parent_event=cause)
    state, _ = consume(projection, state, (cause.phase_to(EventPhase.COMPLETION),))
    assert set(state.senses.spatial_effects[zone.uuid].positions) == positions


def test_spatial_duration_tick_is_visible_to_owner_and_hidden_from_witness(world):
    built = build_battlefield("battlefield.open_floor_bright")
    owner = actor(world, "Owner", (5, 5))
    witness = actor(world, "Witness", (6, 5))
    owned_projection, owned = view(built, (owner,))
    other_projection, other = view(built, (witness,))
    zone = GreaseZone(source_entity_uuid=owner.uuid, position=(5, 7), affected_positions={(5, 7)},
        duration=Duration(duration_type=DurationType.ROUNDS, duration=3))
    root = activate(zone, owner)
    owned, _ = consume(owned_projection, owned, (root,))
    other, _ = consume(other_projection, other, (root,))
    assert owned.senses is not None and other.senses is not None
    assert owned.senses.spatial_effects[zone.uuid].duration.remaining_rounds == 3
    assert other.senses.spatial_effects[zone.uuid].duration is None
    prior_revision = other.senses.spatial_effects[zone.uuid].owner_revision
    prior_cursor = other.reducer_cursor
    cause = Event(source_entity_uuid=owner.uuid, event_type=EventType.BASE_ACTION, phase=EventPhase.EXECUTION)
    assert not zone.progress_spatial_duration(parent_event=cause)
    root = cause.phase_to(EventPhase.COMPLETION)
    owned, _ = consume(owned_projection, owned, (root,))
    other, delivered = consume(other_projection, other, (root,))
    assert zone.duration.duration == 2
    assert owned.senses.spatial_effects[zone.uuid].duration.remaining_rounds == 2
    assert other.senses.spatial_effects[zone.uuid].duration is None
    assert other.senses.spatial_effects[zone.uuid].owner_revision == prior_revision
    assert not delivered, "A private duration tick must not create a public occurrence for its witness"
    assert other.reducer_cursor == prior_cursor


@pytest.mark.parametrize("zone_type,builder", [
    (GuardianOfFaithZone, build_guardian_of_faith_object),
    (HeroesFeastLifetime, build_heroes_feast_object),
])
def test_authored_world_object_lifetime_publishes_surviving_duration(world, zone_type, builder):
    built = build_battlefield("battlefield.open_floor_bright")
    owner = actor(world, "Owner", (5, 5))
    projection, state = view(built, (owner,))
    anchor = builder(owner.uuid)
    cause = Event(source_entity_uuid=owner.uuid, event_type=EventType.BASE_ACTION, phase=EventPhase.EXECUTION)
    anchor.place_on_grid((5, 7), parent_event=cause.uuid)
    zone = zone_type(source_entity_uuid=owner.uuid, position=(5, 7), anchor_uuid=anchor.uuid,
        duration=Duration(duration_type=DurationType.ROUNDS, duration=3))
    zone.activate(parent_event=cause)
    state, _ = consume(projection, state, (cause.phase_to(EventPhase.COMPLETION),))
    assert state.senses is not None
    assert state.senses.spatial_effects[zone.uuid].duration.remaining_rounds == 3
    cause = Event(source_entity_uuid=owner.uuid, event_type=EventType.BASE_ACTION, phase=EventPhase.EXECUTION)
    assert not zone.progress_spatial_duration(parent_event=cause)
    state, _ = consume(projection, state, (cause.phase_to(EventPhase.COMPLETION),))
    assert zone.duration.duration == 2
    assert state.senses.spatial_effects[zone.uuid].duration.remaining_rounds == 2
