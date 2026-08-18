"""Focused security and renderer-seed tests for subjective world projection."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.blocks.equipment import (
    Weapon,
)
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.types.equipment import WeaponSlot
from dnd.types.world import LightLevel
from dnd.core.events.events_registry import (
    EventPhase,
    EventQueue,
)
from dnd.core.events.world_events import (
    SpatialChangeEvent,
)
from dnd.core.gridmap import GridMap
from dnd.presentation import EquippedVisualPolicy
from dnd.types.world import CardinalDirection
from dnd.types.life import LifeState
from dnd.core.traversal_connectors import (
    ConnectorProvocationPolicy,
    TraversalConnectorDefinition,
    TraversalConnectorKind,
)
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.encounters.encounter import CombatantState, Encounter
from dnd.types.encounter_state import EncounterState
from dnd.entities.entity import Entity
from dnd.items.environment_interactables import StorageChest
from dnd.items.torches import TORCH_RECIPE, Torch
from dnd.items.environment import DirectionalDoor, DirectionalWall
from dnd.items.environment_content import (
    directional_door_recipe,
    directional_wall_recipe,
    storage_chest_recipe,
)
from dnd.items.weapons import DAGGER_RECIPE
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.runtime_reset import reset_engine_runtime
from server.player_replication.world_projection import (
    SubjectiveSpatialMemory,
    SubjectiveWorldProjectionError,
    build_entity_visual_loadout,
    build_subjective_world,
    diff_subjective_worlds,
)
from server.player_replication.journal import SubjectiveFrameProjectionContext
from server.player_replication.mapper import (
    CanonicalSubjectivePresentationMapper,
    CausalEventBatch,
    ProjectedEventSlot,
)
from server.player_replication_contract import (
    ActiveWeaponSet,
    ConnectorSetReplacePatch,
    DoorPresentationCue,
    DoorStatePatch,
    EntityRemovePatch,
    EntityUpsertPatch,
    FloorObjectProjectionKind,
    PerspectiveKind,
    PlayerReplicationProtocolIdentity,
    PlayerReplicationWatermarks,
    SubjectivePerspective,
)
from server.world_contracts import StructuralEdgeKind
from server.world_projection import project_grid, project_observed_tile


def _materialize_test_actor(
    *,
    name: str,
    position: tuple[int, int],
    faction: str,
) -> Entity:
    """Build one exact authored actor without unrelated default possessions."""
    runtime_entity_uuid = uuid4()
    return materialize_creature(
        BESTIARY_CREATURE_RECIPES_BY_ID["goblin"],
        runtime_entity_uuid=runtime_entity_uuid,
        display_name=name,
        faction=faction,
        position=position,
        deployment_role=CreatureDeploymentRole(
            role_id=(
                "tests.subjective_world_projection.actor_"
                f"{runtime_entity_uuid.hex}"
            ),
        ),
        possession_mode=CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY,
    )


@pytest.fixture
def subjective_scene() -> Iterator[tuple[GridMap, Entity, Entity, Entity, Torch, Encounter]]:
    """Create three actors where one is outside the first observer's knowledge."""
    grid = reset_engine_runtime(grid_size=(4, 2))
    observer = _materialize_test_actor(
        name="Observer",
        position=(0, 0),
        faction="heroes",
    )
    visible = _materialize_test_actor(
        name="Visible target",
        position=(1, 0),
        faction="monsters",
    )
    hidden = _materialize_test_actor(
        name="Hidden target",
        position=(3, 1),
        faction="monsters",
    )
    torch = materialize_item(
        TORCH_RECIPE,
        observer.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Torch,
    )
    torch.is_lit = True
    grid.place_object(torch.uuid, (1, 1))

    observer.senses.visible = {(0, 0): True, (1, 0): True, (2, 0): False}
    observer.senses.seen = {(0, 0), (1, 0), (2, 0)}
    observer.senses.entities = {visible.uuid: visible.position}
    observer.senses.objects = {torch.uuid: (1, 1)}

    visible.senses.visible = {(1, 0): True, (2, 0): True, (3, 1): True}
    visible.senses.seen = {(1, 0), (2, 0), (3, 1)}
    visible.senses.entities = {hidden.uuid: hidden.position}
    visible.senses.objects = {}

    dagger = materialize_item(
        DAGGER_RECIPE,
        observer.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    assert observer.loot_item(dagger)
    assert observer.equip_item(dagger.uuid, WeaponSlot.MELEE_MAIN)

    encounter = Encounter(name="Subjective encounter", source_entity_uuid=observer.uuid)
    for entity, initiative in ((hidden, 18), (observer, 12), (visible, 8)):
        encounter.combatants[entity.uuid] = CombatantState(
            source_entity_uuid=entity.uuid,
            entity_uuid=entity.uuid,
            controller_uuid=uuid4(),
            initiative_total=initiative,
        )
    encounter.initiative_order = [hidden.uuid, observer.uuid, visible.uuid]
    encounter.current_turn_index = 0
    encounter.round_number = 2
    encounter.state = EncounterState.ACTIVE

    try:
        yield grid, observer, visible, hidden, torch, encounter
    finally:
        reset_engine_runtime()


def _participant(observer: Entity) -> SubjectivePerspective:
    observer_uuid = str(observer.uuid)
    return SubjectivePerspective(
        perspective_epoch_id="participant-epoch",
        kind=PerspectiveKind.CONTROLLED_KNOWLEDGE_UNION,
        controlled_entity_uuids=(observer_uuid,),
        observer_entity_uuids=(observer_uuid,),
        active_observer_uuid=observer_uuid,
    )


def _memory(perspective: SubjectivePerspective) -> SubjectiveSpatialMemory:
    return SubjectiveSpatialMemory(
        perspective_epoch_id=perspective.perspective_epoch_id,
    )


def test_participant_world_excludes_unknown_registry_rows_and_hidden_turn_identity(
    subjective_scene: tuple[GridMap, Entity, Entity, Entity, Torch, Encounter],
) -> None:
    """Objective registries cannot leak actors, initiative identity, or equipment."""
    grid, observer, visible, hidden, torch, encounter = subjective_scene

    perspective = _participant(observer)
    world = build_subjective_world(
        perspective=perspective,
        grid=grid,
        entities=[observer, visible, hidden],
        encounter=encounter,
        memory=_memory(perspective),
    )

    assert {entity.uuid for entity in world.state.entities} == {
        str(observer.uuid),
        str(visible.uuid),
    }
    assert str(hidden.uuid) not in world.model_dump_json()
    assert world.state.encounter is not None
    assert [row.uuid for row in world.state.encounter.initiative_order] == [
        str(observer.uuid),
        str(visible.uuid),
    ]
    assert world.state.encounter.current_entity_uuid is None
    assert world.state.encounter.current_turn_index is None
    assert set(world.equipment_by_entity) == {str(observer.uuid)}
    assert world.visual_loadout_by_entity[str(observer.uuid)].active_weapon_set is ActiveWeaponSet.MELEE
    assert set(world.visual_loadout_by_entity) == {
        str(observer.uuid),
        str(visible.uuid),
    }
    assert set(world.visibility.root) == {str(observer.uuid)}
    assert {(tile.x, tile.y) for tile in world.state.grid.tiles} == {
        (0, 0),
        (1, 0),
    }
    assert all(tile.visual_key == "floor.png" for tile in world.state.grid.tiles)
    assert len(world.state.floor_objects) == 1
    floor_object = world.state.floor_objects[0]
    assert floor_object.uuid == str(torch.uuid)
    assert floor_object.object_kind is FloorObjectProjectionKind.LIGHT_SOURCE
    assert floor_object.is_lit is True
    assert floor_object.bright_radius_feet == torch.bright_radius_feet
    assert "state" not in floor_object.model_dump()


def test_spectator_union_combines_only_its_explicit_observers(
    subjective_scene: tuple[GridMap, Entity, Entity, Entity, Torch, Encounter],
) -> None:
    """A zero-control view unions authorized senses without objective fallback."""
    grid, observer, visible, hidden, _, encounter = subjective_scene
    perspective = SubjectivePerspective(
        perspective_epoch_id="spectator-epoch",
        kind=PerspectiveKind.SPECTATOR_KNOWLEDGE_UNION,
        controlled_entity_uuids=(),
        observer_entity_uuids=(str(observer.uuid), str(visible.uuid)),
        active_observer_uuid=str(visible.uuid),
    )

    world = build_subjective_world(
        perspective=perspective,
        grid=grid,
        entities=[observer, visible, hidden],
        encounter=encounter,
        memory=_memory(perspective),
    )

    assert {entity.uuid for entity in world.state.entities} == {
        str(observer.uuid),
        str(visible.uuid),
        str(hidden.uuid),
    }
    assert world.equipment_by_entity == {}
    assert set(world.visibility.root) == {str(observer.uuid), str(visible.uuid)}
    assert world.state.encounter is not None
    assert world.state.encounter.current_entity_uuid == str(hidden.uuid)
    assert world.state.encounter.current_turn_index == 0


def test_projection_rejects_an_observer_absent_from_the_engine_registry(
    subjective_scene: tuple[GridMap, Entity, Entity, Entity, Torch, Encounter],
) -> None:
    """An invalid grant fails closed instead of silently becoming objective."""
    grid, observer, visible, hidden, _, encounter = subjective_scene
    missing_uuid = str(uuid4())
    perspective = SubjectivePerspective(
        perspective_epoch_id="invalid-epoch",
        kind=PerspectiveKind.SPECTATOR_KNOWLEDGE_UNION,
        observer_entity_uuids=(missing_uuid,),
        active_observer_uuid=missing_uuid,
    )

    with pytest.raises(SubjectiveWorldProjectionError, match="absent"):
        build_subjective_world(
            perspective=perspective,
            grid=grid,
            entities=[observer, visible, hidden],
            encounter=encounter,
            memory=_memory(perspective),
        )


def test_world_diff_emits_typed_entity_replacement(
    subjective_scene: tuple[GridMap, Entity, Entity, Entity, Torch, Encounter],
) -> None:
    """Incremental reducers receive discriminated patches rather than opaque dictionaries."""
    grid, observer, visible, hidden, _, encounter = subjective_scene
    perspective = _participant(observer)
    memory = _memory(perspective)
    previous = build_subjective_world(
        perspective=perspective,
        grid=grid,
        entities=[observer, visible, hidden],
        encounter=encounter,
        memory=memory,
    )
    visible.health.add_damage(1)
    current = build_subjective_world(
        perspective=perspective,
        grid=grid,
        entities=[observer, visible, hidden],
        encounter=encounter,
        memory=memory,
    )

    patches = diff_subjective_worlds(previous, current)

    assert any(
        isinstance(patch, EntityUpsertPatch)
        and patch.entity.uuid == str(visible.uuid)
        for patch in patches
    )


def test_world_diff_replaces_authorized_connector_set() -> None:
    """Connector lifecycle and privacy changes reach incremental replicas."""
    grid = reset_engine_runtime(grid_size=(2, 1))
    assert grid.set_tile_elevation(
        (1, 0),
        height=1,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        slope_axis=None,
    )
    observer = _materialize_test_actor(
        name="Connector delta observer",
        position=(0, 0),
        faction="heroes",
    )
    observer.senses.visible = {(0, 0): True, (1, 0): True}
    perspective = _participant(observer)
    memory = _memory(perspective)

    def world():
        return build_subjective_world(
            perspective=perspective,
            grid=grid,
            entities=[observer],
            encounter=None,
            memory=memory,
        )

    before = world()
    connector = grid.register_connector(TraversalConnectorDefinition(
        authored_id="connector.subjective.delta",
        kind=TraversalConnectorKind.LADDER,
        presentation_key="traversal.ladder",
        endpoint_positions=((0, 0), (1, 0)),
        movement_cost_feet=5,
        action_cost_type=None,
        action_cost_amount=0,
        bidirectional=True,
        enabled=True,
        provocation_policy=ConnectorProvocationPolicy.PROVOKES_SOURCE_EXIT,
    ))
    assert connector is not None
    registered = world()
    patch = next(
        row for row in diff_subjective_worlds(before, registered)
        if isinstance(row, ConnectorSetReplacePatch)
    )
    assert [row.uuid for row in patch.connectors] == [str(connector.uuid)]

    disabled_connector = grid.set_connector_enabled(connector.uuid, False)
    assert disabled_connector is not None
    disabled = world()
    patch = next(
        row for row in diff_subjective_worlds(registered, disabled)
        if isinstance(row, ConnectorSetReplacePatch)
    )
    assert len(patch.connectors) == 1
    assert patch.connectors[0].enabled is False

    observer.senses.visible[(1, 0)] = False
    hidden = world()
    patch = next(
        row for row in diff_subjective_worlds(disabled, hidden)
        if isinstance(row, ConnectorSetReplacePatch)
    )
    assert patch.connectors == ()

    observer.senses.visible[(1, 0)] = True
    revealed = world()
    assert len(next(
        row for row in diff_subjective_worlds(hidden, revealed)
        if isinstance(row, ConnectorSetReplacePatch)
    ).connectors) == 1

    assert grid.remove_connector(connector.uuid) is True
    removed = world()
    patch = next(
        row for row in diff_subjective_worlds(revealed, removed)
        if isinstance(row, ConnectorSetReplacePatch)
    )
    assert patch.connectors == ()


def test_perceived_corpse_persists_privately_until_authoritative_reobservation(
    subjective_scene: tuple[GridMap, Entity, Entity, Entity, Torch, Encounter],
) -> None:
    """A witnessed death stays rendered without leaking an unseen revival."""
    grid, observer, visible, hidden, _, encounter = subjective_scene
    perspective = _participant(observer)
    memory = _memory(perspective)
    living = build_subjective_world(
        perspective=perspective,
        grid=grid,
        entities=[observer, visible, hidden],
        encounter=encounter,
        memory=memory,
    )

    death = visible.receive_instant_death(
        observer.uuid,
        source_description="subjective corpse regression",
    )
    assert death.canceled is False
    observer.senses.entities.pop(visible.uuid, None)
    killed = build_subjective_world(
        perspective=perspective,
        grid=grid,
        entities=[observer, visible, hidden],
        encounter=encounter,
        memory=memory,
    )

    corpse = next(
        entity for entity in killed.state.entities
        if entity.uuid == str(visible.uuid)
    )
    assert corpse.life_state is LifeState.DEAD
    assert corpse.position == visible.position
    assert str(visible.uuid) in killed.visual_loadout_by_entity
    death_patches = diff_subjective_worlds(living, killed)
    assert not any(
        isinstance(patch, EntityRemovePatch)
        and patch.entity_uuid == str(visible.uuid)
        for patch in death_patches
    )
    assert any(
        isinstance(patch, EntityUpsertPatch)
        and patch.entity.uuid == str(visible.uuid)
        and patch.entity.life_state is LifeState.DEAD
        for patch in death_patches
    )

    observer.senses.visible[visible.position] = False
    remembered = build_subjective_world(
        perspective=perspective,
        grid=grid,
        entities=[observer, visible, hidden],
        encounter=encounter,
        memory=memory,
    )
    remembered_corpse = next(
        entity for entity in remembered.state.entities
        if entity.uuid == str(visible.uuid)
    )
    assert remembered_corpse == corpse

    assert visible.revive(hit_points=1)
    revived_but_unseen = build_subjective_world(
        perspective=perspective,
        grid=grid,
        entities=[observer, visible, hidden],
        encounter=encounter,
        memory=memory,
    )
    stale_corpse = next(
        entity for entity in revived_but_unseen.state.entities
        if entity.uuid == str(visible.uuid)
    )
    assert stale_corpse.life_state is LifeState.DEAD
    assert revived_but_unseen.state.encounter is not None
    stale_combatant = next(
        combatant
        for combatant in revived_but_unseen.state.encounter.initiative_order
        if combatant.uuid == str(visible.uuid)
    )
    assert stale_combatant.life_state is LifeState.DEAD

    observer.senses.visible[visible.position] = True
    observer.senses.entities[visible.uuid] = visible.position
    reobserved = build_subjective_world(
        perspective=perspective,
        grid=grid,
        entities=[observer, visible, hidden],
        encounter=encounter,
        memory=memory,
    )
    revived = next(
        entity for entity in reobserved.state.entities
        if entity.uuid == str(visible.uuid)
    )
    assert revived.life_state is LifeState.ALIVE
    assert reobserved.state.encounter is not None
    live_combatant = next(
        combatant
        for combatant in reobserved.state.encounter.initiative_order
        if combatant.uuid == str(visible.uuid)
    )
    assert live_combatant.life_state is LifeState.ALIVE

    observer.senses.visible[visible.position] = False
    observer.senses.entities.pop(visible.uuid, None)
    reset_world = build_subjective_world(
        perspective=perspective.model_copy(
            update={"perspective_epoch_id": "participant-reset-epoch"},
        ),
        grid=grid,
        entities=[observer, visible, hidden],
        encounter=encounter,
        memory=SubjectiveSpatialMemory(
            perspective_epoch_id="participant-reset-epoch",
        ),
    )
    assert str(visible.uuid) not in {
        entity.uuid for entity in reset_world.state.entities
    }


def test_hidden_body_weapon_keeps_logical_active_weapon_set(
    subjective_scene: tuple[GridMap, Entity, Entity, Entity, Torch, Encounter],
) -> None:
    """Natural/body attacks keep melee stance without rendering a weapon layer."""
    _, observer, _, _, _, _ = subjective_scene
    weapon = observer.equipment.weapon_melee_main
    assert weapon is not None
    weapon.equipped_visual_policy = EquippedVisualPolicy.HIDDEN

    loadout = build_entity_visual_loadout(observer)

    assert loadout.active_weapon_set is ActiveWeaponSet.MELEE
    assert loadout.layers[0].equipped_visual_policy is EquippedVisualPolicy.HIDDEN


def test_storage_chest_projects_as_container_with_explicit_visual_key(
    subjective_scene: tuple[GridMap, Entity, Entity, Entity, Torch, Encounter],
) -> None:
    grid, observer, visible, hidden, _, encounter = subjective_scene
    chest = materialize_item(
        storage_chest_recipe(display_name="Oak Chest"),
        observer.uuid,
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=StorageChest,
    )
    grid.place_object(chest.uuid, (0, 1))
    observer.senses.objects[chest.uuid] = (0, 1)

    perspective = _participant(observer)
    world = build_subjective_world(
        perspective=perspective,
        grid=grid,
        entities=[observer, visible, hidden],
        encounter=encounter,
        memory=_memory(perspective),
    )

    projected = next(row for row in world.state.floor_objects if row.uuid == str(chest.uuid))
    assert projected.object_kind is FloorObjectProjectionKind.CONTAINER
    assert projected.visual_item_name == "Oak Chest"
    assert projected.visual_variant_id is None


def test_unseen_cell_uses_last_observed_facts_until_reobserved(
    subjective_scene: tuple[GridMap, Entity, Entity, Entity, Torch, Encounter],
) -> None:
    grid, observer, visible, hidden, _, encounter = subjective_scene
    perspective = _participant(observer)
    memory = _memory(perspective)
    observer.senses.visible[(2, 0)] = True

    observed = build_subjective_world(
        perspective=perspective,
        grid=grid,
        entities=[observer, visible, hidden],
        encounter=encounter,
        memory=memory,
    )
    observed_tile = next(
        tile for tile in observed.state.grid.tiles if (tile.x, tile.y) == (2, 0)
    )

    observer.senses.visible[(2, 0)] = False
    live_tile = grid.get_tile(2, 0)
    assert live_tile is not None
    live_tile.name = "Secret changed terrain"
    live_tile.sprite_name = "secret-terrain.png"
    live_tile.walkable = False
    live_tile.default_light = LightLevel.DARKNESS
    assert live_tile.set_intrinsic_border("movement", "east", False)

    hidden_world = build_subjective_world(
        perspective=perspective,
        grid=grid,
        entities=[observer, visible, hidden],
        encounter=encounter,
        memory=memory,
    )
    remembered_tile = next(
        tile for tile in hidden_world.state.grid.tiles if (tile.x, tile.y) == (2, 0)
    )
    assert remembered_tile == observed_tile.model_copy(update={"visible": False})
    assert "Secret changed terrain" not in hidden_world.model_dump_json()
    assert "secret-terrain.png" not in hidden_world.model_dump_json()

    observer.senses.visible[(2, 0)] = True
    refreshed = build_subjective_world(
        perspective=perspective,
        grid=grid,
        entities=[observer, visible, hidden],
        encounter=encounter,
        memory=memory,
    )
    refreshed_tile = next(
        tile for tile in refreshed.state.grid.tiles if (tile.x, tile.y) == (2, 0)
    )
    assert refreshed_tile.name == "Secret changed terrain"
    assert refreshed_tile.visual_key == "secret-terrain.png"
    assert refreshed_tile.walkable is False
    assert refreshed_tile.light_level == LightLevel.DARKNESS.value
    assert refreshed_tile.directional_blocks_movement.east is True


def test_directional_structure_is_visible_and_remembered_without_senses_object_entry(
    subjective_scene: tuple[GridMap, Entity, Entity, Entity, Torch, Encounter],
) -> None:
    grid, observer, visible, hidden, _, encounter = subjective_scene
    wall = materialize_item(
        directional_wall_recipe(
            display_name="Stone Wall Edge",
            blocked_directions=("east",),
            blocked_channels=("movement", "vision"),
        ),
        observer.uuid,
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=DirectionalWall,
    )
    grid.place_object(wall.uuid, (1, 0))
    assert wall.uuid not in observer.senses.objects
    perspective = _participant(observer)
    memory = _memory(perspective)

    observed = build_subjective_world(
        perspective=perspective,
        grid=grid,
        entities=[observer, visible, hidden],
        encounter=encounter,
        memory=memory,
    )
    projected = next(row for row in observed.state.floor_objects if row.uuid == str(wall.uuid))
    assert projected.object_kind is FloorObjectProjectionKind.DIRECTIONAL_STRUCTURE
    assert projected.visual_item_name == "Stone Wall Edge"

    observer.senses.visible[(1, 0)] = False
    grid.remove_object(wall.uuid)
    hidden_world = build_subjective_world(
        perspective=perspective,
        grid=grid,
        entities=[observer, visible, hidden],
        encounter=encounter,
        memory=memory,
    )
    remembered = next(
        row
        for row in hidden_world.state.floor_objects
        if row.uuid == str(wall.uuid)
    )
    assert remembered == projected
    assert (
        remembered.safe_presentation_ref
        == projected.safe_presentation_ref
    )

    observer.senses.visible[(1, 0)] = True
    refreshed = build_subjective_world(
        perspective=perspective,
        grid=grid,
        entities=[observer, visible, hidden],
        encounter=encounter,
        memory=memory,
    )
    assert str(wall.uuid) not in {row.uuid for row in refreshed.state.floor_objects}


@pytest.mark.parametrize(
    ("wall_position", "wall_direction", "projected_direction"),
    (
        ((2, 1), "west", "east"),
        ((0, 1), "east", "west"),
        ((1, 2), "south", "north"),
        ((1, 0), "north", "south"),
    ),
)
def test_visible_tile_projects_vision_boundary_owned_by_hidden_neighbor(
    wall_position: tuple[int, int],
    wall_direction: CardinalDirection,
    projected_direction: str,
) -> None:
    """The visible side owns knowledge of the wall edge that stops its sight."""
    grid = reset_engine_runtime(grid_size=(3, 3))
    observer = _materialize_test_actor(
        name="Boundary observer",
        position=(1, 1),
        faction="heroes",
    )
    observer.senses.visible = {(1, 1): True}
    observer.senses.seen = {(1, 1)}
    wall = materialize_item(
        directional_wall_recipe(
            blocked_directions=(wall_direction,),
            blocked_channels=("vision",),
        ),
        observer.uuid,
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=DirectionalWall,
    )
    grid.place_object(wall.uuid, wall_position)
    perspective = _participant(observer)

    try:
        world = build_subjective_world(
            perspective=perspective,
            grid=grid,
            entities=[observer],
            encounter=None,
            memory=_memory(perspective),
        )
    finally:
        reset_engine_runtime()

    assert {(tile.x, tile.y) for tile in world.state.grid.tiles} == {(1, 1)}
    projected_tile = world.state.grid.tiles[0]
    assert getattr(
        projected_tile.directional_blocks_vision,
        projected_direction,
    ) is True
    edge = getattr(
        projected_tile.directional_structural_edges,
        projected_direction,
    )
    assert edge is not None
    assert edge.kind is StructuralEdgeKind.WALL
    assert edge.is_open is None
    assert world.state.floor_objects == ()


@pytest.mark.parametrize(
    ("door_position", "door_direction", "projected_direction"),
    (
        ((2, 1), "west", "east"),
        ((0, 1), "east", "west"),
        ((1, 2), "south", "north"),
        ((1, 0), "north", "south"),
    ),
)
def test_distant_closed_door_projects_only_privacy_safe_edge_identity(
    door_position: tuple[int, int],
    door_direction: CardinalDirection,
    projected_direction: str,
) -> None:
    """Every visible boundary direction distinguishes a door without object facts."""

    grid = reset_engine_runtime(grid_size=(3, 3))
    observer = _materialize_test_actor(
        name="Boundary observer",
        position=(1, 1),
        faction="heroes",
    )
    observer.senses.visible = {(1, 1): True}
    observer.senses.seen = {(1, 1)}
    secret_name = f"Private Door {uuid4()}"
    secret_visual = f"PrivateVisual{uuid4()}"
    door = materialize_item(
        directional_door_recipe(
            display_name=secret_name,
            blocked_directions=(door_direction,),
            blocked_channels=("movement", "vision"),
        ),
        observer.uuid,
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=DirectionalDoor,
    )
    door.visual_item_name = secret_visual
    grid.place_object(door.uuid, door_position)
    perspective = _participant(observer)

    try:
        world = build_subjective_world(
            perspective=perspective,
            grid=grid,
            entities=[observer],
            encounter=None,
            memory=_memory(perspective),
        )
    finally:
        reset_engine_runtime()

    assert len(world.state.grid.tiles) == 1
    projected_tile = world.state.grid.tiles[0]
    assert getattr(
        projected_tile.directional_blocks_vision,
        projected_direction,
    ) is True
    edge = getattr(
        projected_tile.directional_structural_edges,
        projected_direction,
    )
    assert edge is not None
    assert edge.kind is StructuralEdgeKind.DOOR
    assert edge.is_open is False
    assert world.state.floor_objects == ()
    payload = world.model_dump_json()
    assert str(door.uuid) not in payload
    assert secret_name not in payload
    assert secret_visual not in payload


def test_visible_door_edge_tracks_authorized_open_and_closed_state() -> None:
    """A known door keeps one typed edge while its blocking channels toggle."""

    grid = reset_engine_runtime(grid_size=(3, 3))
    observer = _materialize_test_actor(
        name="Door observer",
        position=(1, 1),
        faction="heroes",
    )
    observer.senses.visible = {(1, 1): True}
    observer.senses.seen = {(1, 1)}
    door = materialize_item(
        directional_door_recipe(
            blocked_directions=("east",),
            blocked_channels=("movement", "vision"),
        ),
        observer.uuid,
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=DirectionalDoor,
    )
    grid.place_object(door.uuid, (1, 1))
    perspective = _participant(observer)
    memory = _memory(perspective)

    try:
        closed = build_subjective_world(
            perspective=perspective,
            grid=grid,
            entities=[observer],
            encounter=None,
            memory=memory,
        )
        door.open()
        opened = build_subjective_world(
            perspective=perspective,
            grid=grid,
            entities=[observer],
            encounter=None,
            memory=memory,
        )
    finally:
        reset_engine_runtime()

    closed_tile = closed.state.grid.tiles[0]
    closed_edge = closed_tile.directional_structural_edges.east
    assert closed_edge is not None
    assert closed_edge.kind is StructuralEdgeKind.DOOR
    assert closed_edge.is_open is False
    assert closed_tile.directional_blocks_movement.east is True
    assert closed_tile.directional_blocks_vision.east is True

    opened_tile = opened.state.grid.tiles[0]
    opened_edge = opened_tile.directional_structural_edges.east
    assert opened_edge is not None
    assert opened_edge.kind is StructuralEdgeKind.DOOR
    assert opened_edge.is_open is True
    assert opened_tile.directional_blocks_movement.east is False
    assert opened_tile.directional_blocks_vision.east is False


def test_imperceivable_hidden_door_does_not_cross_the_edge_contract() -> None:
    """Private object identity and its derived blocker both fail closed."""

    grid = reset_engine_runtime(grid_size=(3, 3))
    observer = _materialize_test_actor(
        name="Door observer",
        position=(1, 1),
        faction="heroes",
    )
    observer.senses.visible = {(1, 1): True}
    observer.senses.seen = {(1, 1)}
    door = materialize_item(
        directional_door_recipe(
            blocked_directions=("west",),
            blocked_channels=("movement", "vision"),
        ),
        observer.uuid,
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=DirectionalDoor,
    )
    door.is_invisible = True
    grid.place_object(door.uuid, (2, 1))
    perspective = _participant(observer)

    try:
        world = build_subjective_world(
            perspective=perspective,
            grid=grid,
            entities=[observer],
            encounter=None,
            memory=_memory(perspective),
        )
    finally:
        reset_engine_runtime()

    tile = world.state.grid.tiles[0]
    assert tile.directional_blocks_vision.east is False
    assert tile.directional_structural_edges.east is None
    assert world.state.floor_objects == ()


def test_hidden_neighbor_movement_only_boundary_does_not_invent_vision_wall() -> None:
    """A hidden movement-only edge is not promoted into visible wall knowledge."""
    grid = reset_engine_runtime(grid_size=(3, 3))
    observer = _materialize_test_actor(
        name="Boundary observer",
        position=(1, 1),
        faction="heroes",
    )
    observer.senses.visible = {(1, 1): True}
    observer.senses.seen = {(1, 1)}
    wall = materialize_item(
        directional_wall_recipe(
            blocked_directions=("west",),
            blocked_channels=("movement",),
        ),
        observer.uuid,
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=DirectionalWall,
    )
    grid.place_object(wall.uuid, (2, 1))
    perspective = _participant(observer)

    try:
        world = build_subjective_world(
            perspective=perspective,
            grid=grid,
            entities=[observer],
            encounter=None,
            memory=_memory(perspective),
        )
    finally:
        reset_engine_runtime()

    projected_tile = world.state.grid.tiles[0]
    assert projected_tile.directional_blocks_vision.east is False
    assert projected_tile.directional_blocks_movement.east is False
    assert world.state.floor_objects == ()


def test_open_door_world_diff_drives_the_canonical_presentation_cue(
    subjective_scene: tuple[GridMap, Entity, Entity, Entity, Torch, Encounter],
) -> None:
    """The one world diff is the mapper's typed source for door presentation."""
    grid, observer, visible, hidden, _, encounter = subjective_scene
    door = materialize_item(
        directional_door_recipe(
            display_name="Directional Door",
            blocked_directions=("east",),
            blocked_channels=("movement", "vision"),
        ),
        observer.uuid,
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=DirectionalDoor,
    )
    grid.place_object(door.uuid, (1, 0))
    observer.senses.objects[door.uuid] = (1, 0)
    perspective = _participant(observer)
    memory = _memory(perspective)
    previous = build_subjective_world(
        perspective=perspective,
        grid=grid,
        entities=[observer, visible, hidden],
        encounter=encounter,
        memory=memory,
    )

    event_cursor = EventQueue.event_cursor()
    door.open()
    current = build_subjective_world(
        perspective=perspective,
        grid=grid,
        entities=[observer, visible, hidden],
        encounter=encounter,
        memory=memory,
    )
    patches = diff_subjective_worlds(previous, current)
    door_patch = next(patch for patch in patches if isinstance(patch, DoorStatePatch))
    completion = next(
        event
        for _, event in reversed(tuple(EventQueue.iter_events_since(event_cursor)))
        if isinstance(event, SpatialChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.object_uuid == door.uuid
    )

    mapper = CanonicalSubjectivePresentationMapper()
    frame = mapper.project_frame(
        CausalEventBatch(
            slots=(ProjectedEventSlot(source_event_cursor=1, event=completion),),
            through_source_event_cursor=1,
            patches=patches,
        ),
        SubjectiveFrameProjectionContext(
            protocol=PlayerReplicationProtocolIdentity(
                source_stream_id="door-test",
                generation_id="door-generation",
                ),
                perspective=perspective,
                previous_watermarks=PlayerReplicationWatermarks(
                    source_event_cursor=0,
                    observation_cursor=0,
                    presentation_cursor=0,
                    combat_log_cursor=0,
                ),
                next_observation_cursor=1,
        ),
    )

    assert door_patch.is_open is True
    cue = next(cue for cue in frame.presentation if isinstance(cue, DoorPresentationCue))
    assert cue.object_uuid == str(door.uuid)
    assert cue.position == (1, 0)
    assert cue.is_open is True


def test_conflicting_door_appearances_are_conservative_and_observer_order_stable() -> None:
    """Defensive overlap handling can never depend on observer-union order."""

    grid = reset_engine_runtime(grid_size=(1, 1))
    observer_a = _materialize_test_actor(
        name="Observer A",
        position=(0, 0),
        faction="heroes",
    )
    observer_b = _materialize_test_actor(
        name="Observer B",
        position=(0, 0),
        faction="heroes",
    )
    closed = materialize_item(
        directional_door_recipe(
            display_name="ClosedOverlap",
            blocked_directions=("east",),
            blocked_channels=("movement", "vision"),
        ),
        observer_a.uuid,
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=DirectionalDoor,
    )
    opened = materialize_item(
        directional_door_recipe(
            display_name="OpenOverlap",
            blocked_directions=("east",),
            blocked_channels=("movement", "vision"),
        ),
        observer_b.uuid,
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=DirectionalDoor,
    )
    closed.visual_item_name = "ClosedOverlap"
    opened.visual_item_name = "OpenOverlap"
    opened.open()
    grid.place_object(closed.uuid, (0, 0))
    grid.place_object(opened.uuid, (0, 0))

    try:
        forward = project_observed_tile(
            grid,
            (0, 0),
            (observer_a.uuid, observer_b.uuid),
        )
        reverse = project_observed_tile(
            grid,
            (0, 0),
            (observer_b.uuid, observer_a.uuid),
        )

        assert forward == reverse
        assert forward.directional_structural_edges.east is not None
        assert forward.directional_structural_edges.east.kind is StructuralEdgeKind.DOOR
        assert forward.directional_structural_edges.east.is_open is False
    finally:
        reset_engine_runtime()


def test_subjective_connector_projection_requires_both_endpoint_grants() -> None:
    grid = reset_engine_runtime(grid_size=(2, 1))
    grid.set_tile_elevation(
        (1, 0),
        height=1,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        slope_axis=None,
    )
    connector = grid.register_connector(TraversalConnectorDefinition(
        authored_id="connector.subjective.ladder",
        kind=TraversalConnectorKind.LADDER,
        presentation_key="traversal.ladder",
        endpoint_positions=((0, 0), (1, 0)),
        movement_cost_feet=10,
        action_cost_type=None,
        action_cost_amount=0,
        bidirectional=True,
        enabled=True,
        provocation_policy=ConnectorProvocationPolicy.PROVOKES_SOURCE_EXIT,
    ))
    assert connector is not None
    observer = _materialize_test_actor(
        name="Connector Observer",
        position=(0, 0),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=20)

    visible_projection = project_grid(
        grid,
        requesting_entity_uuid=observer.uuid,
    )
    assert [row.authored_id for row in visible_projection.connectors] == [
        connector.authored_id
    ]

    observer.senses.visible[(1, 0)] = False
    hidden_projection = project_grid(
        grid,
        requesting_entity_uuid=observer.uuid,
    )
    assert hidden_projection.connectors == []
    assert (1, 0) not in {(tile.x, tile.y) for tile in hidden_projection.tiles}

    with pytest.raises(ValueError, match="known entity"):
        project_grid(grid, requesting_entity_uuid=uuid4())
