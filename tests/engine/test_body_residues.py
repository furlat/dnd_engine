"""Native wounds record releases; tiles retain and execute their own residue."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.actions import Jump, Move
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, BONE_BODY_RESPONSE, CORROSIVE_BODY_RESPONSE, install_body_response
from dnd.content.characters.premades import FIGHTER_PREMADE_ID, create_premade_character
from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.events import Damage, DamageAppliedEvent, EventPhase, EventQueue, EventType, SpatialChangeEvent
from dnd.core.gridmap import get_map
from dnd.core.values import ModifiableValue
from dnd.entity import Entity, EntityConfig
from dnd.items.environment import DirectionalDoor
from dnd.game import Game
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.monsters.demon_variants import CORROSIVE_DEMON_RECIPE, DREAD_DEMON_RECIPE
from dnd.monsters.srd_roster import SRD_CREATURE_RECIPES_BY_ID
from dnd.residues import BLOOD_RESIDUE, BONE_RESIDUE, CORROSIVE_RESIDUE, deposit_residue
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.environmental_conditions import materialize_spike_trap_condition
from dnd.types.world import CardinalDirection, OccupancyLayer
from dnd.core.world_edges import ElevationSurfaceKind


@pytest.fixture
def world() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(6, 3))
    game = Game()
    try:
        yield game
    finally:
        game.close()
        reset_engine_runtime()


def actor(world: Game, *, health: HealthConfig | None = None) -> Entity:
    creature = Entity.create(uuid4(), "Traveler", config=EntityConfig(
        position=(0, 1),
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=18)),
        health=health or HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=10, hit_dice_count=8, mode="maximums",
        )]),
    ))
    setup_standard_actions(creature)
    creature.compose_entity()
    world.deploy_entity(creature, creature.position)
    return creature


def injuries_since(cursor: int) -> list[DamageAppliedEvent]:
    return [event for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, DamageAppliedEvent) and event.phase is EventPhase.COMPLETION]


@pytest.mark.parametrize("damage_type,temporary_hp,immunity,expected", (
    (DamageType.PIERCING, 0, False, True),
    (DamageType.BLUDGEONING, 0, False, True),
    (DamageType.SLASHING, 0, False, True),
    (DamageType.FIRE, 0, False, False),
    (DamageType.PSYCHIC, 0, False, False),
    (DamageType.PIERCING, 8, False, False),
    (DamageType.PIERCING, 0, True, False),
))
def test_only_resolved_physical_normal_hp_injury_releases(
    world: Game, damage_type: DamageType, temporary_hp: int, immunity: bool, expected: bool,
) -> None:
    creature = actor(world, health=HealthConfig(
        hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=2)],
        temporary_hit_points=temporary_hp, immunities=[damage_type] if immunity else [],
    ))
    install_body_response(creature, BLOOD_BODY_RESPONSE)
    cursor = EventQueue.event_cursor()
    creature.receive_damage(3, damage_type, creature.uuid)
    releases = [event.body_release for event in injuries_since(cursor) if event.body_release is not None]
    assert len(releases) == int(expected)
    tile = get_map().get_tile(*creature.position)
    assert tile is not None
    assert tuple(row.residue_id for row in tile.to_world_tile_state().residues) == (
        ("residue.blood",) if expected else ()
    )


@pytest.mark.parametrize("physical_immune", (False, True))
def test_mixed_packet_uses_post_affinity_physical_component(world: Game, physical_immune: bool) -> None:
    creature = actor(world, health=HealthConfig(
        hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=2)],
        immunities=[DamageType.PIERCING] if physical_immune else [],
    ))
    install_body_response(creature, BLOOD_BODY_RESPONSE)
    components = [Damage(source_entity_uuid=creature.uuid, damage_type=kind, damage_dice=4, dice_numbers=1,
                         damage_bonus=ModifiableValue.create(source_entity_uuid=creature.uuid, base_value=0))
                  for kind in (DamageType.PIERCING, DamageType.POISON)]
    with fixed_dice_faces(2, 2):
        rolls = [damage.get_dice(AttackOutcome.HIT).roll for damage in components]
    cursor = EventQueue.event_cursor()
    creature.receive_damage(4, DamageType.PIERCING, creature.uuid, damages=components, damage_rolls=rolls)
    injury = injuries_since(cursor)[0]
    assert injury.normal_hit_point_damage == (2 if physical_immune else 4)
    assert (injury.body_release is not None) is (not physical_immune)


def test_repeated_and_lethal_wounds_leave_one_tile_owned_residue(world: Game) -> None:
    creature = actor(world)
    install_body_response(creature, BLOOD_BODY_RESPONSE)
    tile = get_map().get_tile(*creature.position)
    assert tile is not None
    cursor = EventQueue.event_cursor()
    creature.receive_damage(1, DamageType.PIERCING, creature.uuid)
    first = tile.to_world_tile_state().residues
    creature.receive_damage(500, DamageType.PIERCING, creature.uuid)
    assert len([event for event in injuries_since(cursor) if event.body_release is not None]) == 2
    current, = tile.to_world_tile_state().residues
    assert current.condition_uuid == first[0].condition_uuid and current.amount == 2
    assert current.contributions[0].ellipses == first[0].contributions[0].ellipses
    assert current.contributions[0].amount == 2
    condition = tile.active_conditions_by_uuid[first[0].condition_uuid]
    assert condition.source_entity_uuid == tile.uuid
    assert condition.target_entity_uuid == tile.uuid
    assert not creature.is_encounter_alive


@pytest.mark.parametrize("profile,amounts", (
    (BLOOD_BODY_RESPONSE, (1, 2, 3, 4, 5, 5, 5)),
    (BONE_BODY_RESPONSE, (1, 1, 1, 1, 1, 1, 1)),
    (CORROSIVE_BODY_RESPONSE, (1, 1, 1, 1, 1, 1, 1)),
))
def test_repeated_injuries_record_authored_amount_without_changing_membership_or_paths(world, profile, amounts):
    creature = actor(world)
    install_body_response(creature, profile)
    grid = get_map()
    tile = grid.get_tile(*creature.position)
    assert tile is not None
    identity = None
    for amount in amounts:
        cursor = EventQueue.event_cursor()
        revisions = grid.optical_revision, grid.movement_revision
        prior = tile.to_world_tile_state().residues
        creature.receive_damage(1, DamageType.PIERCING, creature.uuid)
        residue, = tile.to_world_tile_state().residues
        identity = identity or residue.condition_uuid
        assert residue.amount == amount and residue.condition_uuid == identity
        injury, = injuries_since(cursor)
        assert injury.body_release is not None
        if prior:
            assert (grid.optical_revision, grid.movement_revision) == revisions
            changes = [event for _, event in EventQueue.iter_events_since(cursor)
                       if isinstance(event, SpatialChangeEvent) and event.phase is EventPhase.COMPLETION
                       and event.tile_state is not None]
            cells = {cell for region in injury.body_release.regions for cell in region.positions}
            assert len(changes) == len(cells) * int(prior[0].amount != amount)
            if changes:
                at_origin, = [change for change in changes if change.tile_state.position == creature.position]
                assert at_origin.tile_state.residues == (residue,)
                parent = EventQueue.get_event_by_uuid(changes[0].parent_event)
                assert parent is not None and parent.lineage_uuid == injury.lineage_uuid


def test_release_in_air_retains_origin_without_ground_deposition(world: Game) -> None:
    creature = actor(world)
    install_body_response(creature, BONE_BODY_RESPONSE)
    Entity.update_entity_position(creature, creature.position, occupancy_layer=OccupancyLayer.AIR)
    cursor = EventQueue.event_cursor()
    creature.receive_damage(1, DamageType.PIERCING, creature.uuid)
    release = injuries_since(cursor)[0].body_release
    assert release is not None
    assert (release.release_id, release.position, release.occupancy_layer, release.deposited_position) == (
        "body.bone", (0, 1), OccupancyLayer.AIR, None,
    )
    tile = get_map().get_tile(0, 1)
    assert tile is not None and tile.to_world_tile_state().residues == ()


def test_distinct_residues_coexist_with_floor_spikes(world: Game) -> None:
    tile = get_map().get_tile(2, 1)
    assert tile is not None
    trap = materialize_spike_trap_condition({tile.position})
    for profile in (BLOOD_RESIDUE, BONE_RESIDUE, CORROSIVE_RESIDUE, BLOOD_RESIDUE):
        deposit_residue(tile, profile)
    assert {row.residue_id for row in tile.to_world_tile_state().residues} == {
        "residue.blood", "residue.bone_fragments", "residue.corrosive_demonic_blood",
    }
    assert trap.uuid in tile.get_conditions()


@pytest.mark.parametrize("movement,residue_position,loss", (
    ("walk", (1, 1), 2), ("jump", (1, 1), 0), ("jump", (3, 1), 2),
))
def test_corrosive_residue_requires_actual_ground_entry(
    world: Game, movement: str, residue_position: tuple[int, int], loss: int,
) -> None:
    creature = actor(world)
    tile = get_map().get_tile(*residue_position)
    assert tile is not None
    deposit_residue(tile, CORROSIVE_RESIDUE)
    creature.update_entity_senses()
    hp = creature.get_hp()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(2):
        if movement == "jump":
            result = Jump(source_entity_uuid=creature.uuid, end_position=(3, 1)).apply()
        else:
            result = Move(source_entity_uuid=creature.uuid, end_position=(3, 1),
                          path=[(0, 1), (1, 1), (2, 1), (3, 1)], prefer_safe=False).apply()
    assert result is not None and not result.canceled
    assert creature.get_hp() == hp - loss
    injuries = injuries_since(cursor)
    assert len(injuries) == int(loss > 0)
    if injuries:
        assert injuries[0].parent_event is not None
        incoming = EventQueue.get_event_by_uuid(injuries[0].parent_event)
        assert incoming is not None and incoming.parent_event is not None
        entry = EventQueue.get_event_by_uuid(incoming.parent_event)
        assert entry is not None and entry.event_type is EventType.SPATIAL_ENTITY_ENTERED


def test_deposition_is_inert_until_entry_and_removal_restores_safe_route(world: Game) -> None:
    creature = actor(world)
    install_body_response(creature, CORROSIVE_BODY_RESPONSE)
    tile = get_map().get_tile(*creature.position)
    assert tile is not None
    hp = creature.get_hp()
    creature.receive_damage(1, DamageType.PIERCING, creature.uuid)
    creature.receive_damage(1, DamageType.PIERCING, creature.uuid)
    assert creature.get_hp() == hp - 2
    residue = tile.to_world_tile_state().residues[0]
    for _ in range(2):
        Entity.update_entity_position(creature, (1, 1))
        with fixed_dice_faces(2):
            Entity.update_entity_position(creature, (0, 1))
    assert creature.get_hp() == hp - 6
    Entity.update_entity_position(creature, (1, 1))
    grid = get_map()
    _, unsafe_paths = grid.compute_paths(creature.position, requesting_entity_uuid=creature.uuid,
                                          walk_in_danger=False)
    assert tile.position not in unsafe_paths
    assert tile.remove_condition_by_uuid(residue.condition_uuid)
    _, safe_paths = grid.compute_paths(creature.position, requesting_entity_uuid=creature.uuid,
                                      walk_in_danger=False)
    assert tile.position in safe_paths
    Entity.update_entity_position(creature, tile.position)
    assert creature.get_hp() == hp - 6
    assert tile.to_world_tile_state().residues == ()


@pytest.mark.parametrize("factory,release_id,residue_id", (
    (create_goblin, "body.blood", "residue.blood"),
    (create_skeleton, "body.bone", "residue.bone_fragments"),
))
def test_authored_bestiary_composition_installs_its_body_response(world: Game, factory, release_id: str, residue_id: str) -> None:
    creature = factory(position=(1, 1))
    creature.compose_entity()
    world.deploy_entity(creature, creature.position)
    cursor = EventQueue.event_cursor()
    creature.receive_damage(1, DamageType.PIERCING, creature.uuid)
    release = injuries_since(cursor)[0].body_release
    assert release is not None and release.release_id == release_id
    tile = get_map().get_tile(*creature.position)
    assert tile is not None and tile.to_world_tile_state().residues[0].residue_id == residue_id


@pytest.mark.parametrize("recipe,release_id", (
    (CORROSIVE_DEMON_RECIPE, "body.corrosive_blood"),
    (DREAD_DEMON_RECIPE, "body.dread_blood"),
    (SRD_CREATURE_RECIPES_BY_ID["dretch"], None),
))
def test_explicit_demon_variants_preserve_canonical_dretch(world: Game, recipe, release_id: str | None) -> None:
    creature = materialize_creature(
        recipe, runtime_entity_uuid=uuid4(), display_name="Demon", position=(1, 1), faction="demons",
        deployment_role=CreatureDeploymentRole(role_id="tests.residue"),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
    )
    creature.compose_entity()
    world.deploy_entity(creature, creature.position)
    cursor = EventQueue.event_cursor()
    creature.receive_damage(1, DamageType.PIERCING, creature.uuid)
    release = injuries_since(cursor)[0].body_release
    assert (release.release_id if release is not None else None) == release_id


def test_inert_residue_changes_tile_facts_without_rebuilding_routes(world: Game) -> None:
    actor(world)
    tile = get_map().get_tile(2, 1)
    assert tile is not None
    revision = get_map().movement_revision
    cursor = EventQueue.event_cursor()
    state = deposit_residue(tile, BLOOD_RESIDUE)
    assert state is not None
    assert tile.remove_condition_by_uuid(state.condition_uuid)
    assert get_map().movement_revision == revision
    changes = [event for _, event in EventQueue.iter_events_since(cursor)
               if event.phase is EventPhase.COMPLETION]
    assert [event.event_type for event in changes] == [
        EventType.CONDITION_APPLICATION, EventType.CONDITION_REMOVAL,
    ]


@pytest.mark.parametrize("affinity,expected", (("normal", 2), ("resistant", 1), ("immune", 0)))
def test_corrosive_entry_uses_normal_damage_defenses(world: Game, affinity: str, expected: int) -> None:
    creature = actor(world, health=HealthConfig(
        hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=2)],
        resistances=[DamageType.ACID] if affinity == "resistant" else [],
        immunities=[DamageType.ACID] if affinity == "immune" else [],
    ))
    tile = get_map().get_tile(1, 1)
    assert tile is not None
    deposit_residue(tile, CORROSIVE_RESIDUE)
    hp = creature.get_hp()
    with fixed_dice_faces(2):
        Entity.update_entity_position(creature, tile.position)
    assert creature.get_hp() == hp - expected


def test_direct_player_composition_has_ordinary_blood(world: Game) -> None:
    creature = create_premade_character(FIGHTER_PREMADE_ID, position=(1, 1))
    world.deploy_entity(creature, creature.position)
    cursor = EventQueue.event_cursor()
    creature.receive_damage(1, DamageType.PIERCING, creature.uuid)
    release = injuries_since(cursor)[0].body_release
    assert release is not None and release.release_id == "body.blood"


@pytest.mark.parametrize("kind,pattern", (
    (DamageType.PIERCING, "piercing"), (DamageType.SLASHING, "slashing"),
    (DamageType.BLUDGEONING, "blunt"),
))
@pytest.mark.parametrize("direction", ((1, 0), (0, 1), (-1, 0), (0, -1)))
def test_native_injury_retains_directional_receiving_regions(world, kind, pattern, direction):
    creature = actor(world)
    Entity.update_entity_position(creature, (2, 1))
    install_body_response(creature, BLOOD_BODY_RESPONSE)
    cursor = EventQueue.event_cursor()
    creature.receive_damage(1, kind, creature.uuid, impact_direction=direction)
    release = injuries_since(cursor)[0].body_release
    assert release is not None and release.pattern == pattern
    cells = {cell for region in release.regions for cell in region.positions}
    ahead = (2 + direction[0], 1 + direction[1])
    assert (2, 1) in cells and ahead in cells
    for cell in cells:
        tile = get_map().get_tile(*cell)
        residue, = tile.to_world_tile_state().residues
        assert residue.amount == 1 and sum(row.amount for row in residue.contributions) == 1
        world_shapes = tuple((shape.center[0] + cell[0], shape.center[1] + cell[1], shape.radius_x, shape.radius_y, shape.angle)
            for row in residue.contributions for shape in row.ellipses)
        expected = tuple((*region.ellipse.center, region.ellipse.radius_x, region.ellipse.radius_y, region.ellipse.angle)
            for region in release.regions if cell in region.positions)
        assert len(world_shapes) == len(expected)
        for actual, reference in zip(world_shapes, expected):
            assert actual == pytest.approx(reference)


@pytest.mark.parametrize("door_open", (False, True))
def test_blood_footprint_uses_real_door_state(world, door_open):
    creature = actor(world)
    install_body_response(creature, BLOOD_BODY_RESPONSE)
    door = DirectionalDoor(source_entity_uuid=creature.uuid, item_id="test.door", is_open=door_open)
    door.place_on_grid((0, 1), boundary_direction=CardinalDirection.EAST)
    cursor = EventQueue.event_cursor()
    creature.receive_damage(1, DamageType.PIERCING, creature.uuid, impact_direction=(1, 0))
    release = injuries_since(cursor)[0].body_release
    assert release is not None
    assert ((1, 1) in {cell for region in release.regions for cell in region.positions}) is door_open


@pytest.mark.parametrize("origin_height,receiver_height,admitted", ((0, 1, False), (1, 0, False), (2, 2, True)))
def test_deposits_require_same_support_elevation(world, origin_height, receiver_height, admitted):
    grid = get_map()
    for cell, height in (((0, 1), origin_height), ((1, 1), receiver_height)):
        grid.set_tile_elevation(cell, height=height, surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)
    creature = actor(world)
    install_body_response(creature, BLOOD_BODY_RESPONSE)
    cursor = EventQueue.event_cursor()
    creature.receive_damage(1, DamageType.PIERCING, creature.uuid, impact_direction=(1, 0))
    release = injuries_since(cursor)[0].body_release
    assert release is not None and all(row.elevation_steps == origin_height for row in release.regions)
    assert ((1, 1) in {cell for region in release.regions for cell in region.positions}) is admitted


def test_different_directions_accumulate_current_geometry_then_freeze_at_cap(world):
    creature = actor(world)
    Entity.update_entity_position(creature, (2, 1))
    install_body_response(creature, BLOOD_BODY_RESPONSE)
    tile = get_map().get_tile(*creature.position)
    snapshots = []
    for direction in ((1, 0), (0, 1), (1, 0), (0, 1), (1, 0), (-1, 0), (0, -1)):
        creature.receive_damage(1, DamageType.PIERCING, creature.uuid, impact_direction=direction)
        snapshots.append(tile.to_world_tile_state().residues[0])
    assert [row.amount for row in snapshots] == [1, 2, 3, 4, 5, 5, 5]
    assert len({row.condition_uuid for row in snapshots}) == 1
    assert [row.amount for row in snapshots[4].contributions] == [3, 2]
    assert snapshots[4] == snapshots[5] == snapshots[6]
