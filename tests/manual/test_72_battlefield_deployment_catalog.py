"""Canonical battlefield definitions, builders, and deployment contracts."""

from __future__ import annotations

from dnd.content.scenarios.battlefield_builders import (
    BATTLEFIELDS,
    build_battlefield,
    get_battlefield,
)
from dnd.content.scenarios.scenario_catalog import (
    AUTHORED_DEPLOYMENTS,
    AUTHORED_ENCOUNTERS,
)
from dnd.content.scenarios.scenario_compatibility import (
    check_built_encounter_compatibility,
    check_encounter_compatibility,
)
from dnd.blocks.base_item import BaseItem
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.core.events.events_registry import EventPhase, EventQueue, EventType
from dnd.core.events.item_events import ItemLocationStateEvent
from dnd.core.events.world_events import (
    SpatialChangeEvent,
    SpatialEffectInteractionEvent,
    WorldInitializedEvent,
)
from dnd.core.gridmap import get_map
from dnd.items.environment import DirectionalDoor
from dnd.items.torches import WallTorch
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.world import (
    CardinalDirection,
    LightLevel,
    MovementMode,
    WorldEdgeChannel,
)


def test_battlefield_catalog_has_ten_exact_mechanical_states() -> None:
    assert len(BATTLEFIELDS) == 10
    assert len({row.battlefield_id for row in BATTLEFIELDS}) == 10

    bright = get_battlefield("battlefield.open_floor_bright")
    dark = get_battlefield("battlefield.open_floor_dark")
    assert bright.light_level == "bright"
    assert dark.light_level == "darkness"

    reset_engine_runtime()
    build_battlefield(bright.battlefield_id)
    bright_levels = {
        tile.default_light for tile in get_map().get_all_tiles().values()
    }
    reset_engine_runtime()
    build_battlefield(dark.battlefield_id)
    dark_levels = {
        tile.default_light for tile in get_map().get_all_tiles().values()
    }
    assert bright_levels == {LightLevel.BRIGHT_LIGHT}
    assert dark_levels == {LightLevel.DARKNESS}


def test_battlefield_layouts_retain_terrain_barriers_and_objects() -> None:
    closed = get_battlefield("battlefield.standard_hazards_closed")
    terrain = {
        (cell.position, cell.terrain) for cell in closed.layout.tiles
    }
    assert ((2, 0), "water") in terrain
    assert ((6, 0), "difficult_terrain") in terrain
    assert ((0, 11), "spikes") in terrain
    door = next(
        obj for obj in closed.layout.objects if obj.kind == "door"
    )
    assert door.position == (7, 7)
    assert door.boundary_direction is CardinalDirection.WEST
    assert door.is_open is False

    opened = get_battlefield("battlefield.standard_hazards_open")
    open_door = next(
        obj for obj in opened.layout.objects if obj.kind == "door"
    )
    assert open_door.position == door.position
    assert open_door.boundary_direction is CardinalDirection.WEST
    assert open_door.is_open is True

    closed_torches = [
        obj for obj in closed.layout.objects if obj.kind == "wall_torch"
    ]
    assert [
        (
            row.position,
            row.boundary_direction,
            row.base_height_steps,
            row.orientation,
        )
        for row in closed_torches
    ] == [
        ((14, 1), CardinalDirection.EAST, 1, CardinalDirection.WEST),
        ((14, 13), CardinalDirection.EAST, 1, CardinalDirection.WEST),
    ]

    reset_engine_runtime()
    closed_built = build_battlefield("battlefield.standard_hazards_closed")
    closed_runtime = BaseBlock.get(closed_built.object_uuids["door"])
    assert isinstance(closed_runtime, DirectionalDoor)
    assert closed_runtime.get_boundary_structure().blocked_channels == tuple(
        WorldEdgeChannel
    )

    reset_engine_runtime()
    open_built = build_battlefield("battlefield.standard_hazards_open")
    open_runtime = BaseBlock.get(open_built.object_uuids["door"])
    assert isinstance(open_runtime, DirectionalDoor)
    assert open_runtime.get_boundary_structure().blocked_channels == ()

    labyrinth = get_battlefield("battlefield.reveal_labyrinth_dark")
    assert {
        obj.position
        for obj in labyrinth.layout.objects
        if obj.kind == "door"
    } == {(5, 6), (9, 8)}

    control_room = get_battlefield("battlefield.multi_object_dark")
    assert {
        (obj.kind, obj.position) for obj in control_room.layout.objects
    } >= {
        ("fireball_cannon", (6, 11)),
        ("loot_chest", (5, 10)),
        ("trap_lever", (5, 12)),
    }
    control_torch = next(
        obj
        for obj in control_room.layout.objects
        if obj.kind == "wall_torch" and obj.position == (4, 10)
    )
    assert (
        control_torch.position,
        control_torch.boundary_direction,
        control_torch.base_height_steps,
        control_torch.orientation,
    ) == (
        (4, 10),
        CardinalDirection.WEST,
        1,
        CardinalDirection.EAST,
    )
    proving = get_battlefield("battlefield.elevation_proving_ground")
    cliff = next(obj for obj in proving.layout.objects if obj.kind == "cliff")
    assert (
        cliff.position,
        cliff.boundary_direction,
        cliff.base_height_steps,
        cliff.orientation,
    ) == ((11, 5), CardinalDirection.WEST, 0, None)


def test_every_battlefield_has_one_builder_and_layout_matches_runtime() -> None:
    for definition in BATTLEFIELDS:
        reset_engine_runtime()
        built = build_battlefield(definition.battlefield_id)
        assert built.definition is definition
        grid = get_map()
        for cell in definition.layout.tiles:
            tile = grid.get_tile(*cell.position)
            assert tile is not None, (definition.battlefield_id, cell.position)
            assert (
                tile.get_movement_cost(MovementMode.WALKING),
                tile.get_movement_cost(MovementMode.FLYING),
                tile.get_movement_cost(MovementMode.SWIMMING),
                tile.get_movement_cost(MovementMode.BURROWING),
            ) == (
                cell.walking_cost,
                cell.flying_cost,
                cell.swimming_cost,
                cell.burrowing_cost,
            )
        for authored in definition.layout.objects:
            if authored.kind not in {"wall_torch", "cliff"}:
                continue
            assert authored.boundary_direction is not None
            matching = [
                BaseBlock.get(object_uuid)
                for object_uuid in grid.get_boundary_objects_at(
                    authored.position,
                    authored.boundary_direction,
                )
                if BaseBlock.get(object_uuid) is not None
            ]
            assert len(matching) == 1, (
                definition.battlefield_id,
                authored,
            )
            placement = grid.get_object_placement(matching[0].uuid)
            assert placement is not None
            assert (
                placement.position,
                placement.boundary_direction,
                placement.base_height_steps,
                placement.orientation,
            ) == (
                authored.position,
                authored.boundary_direction,
                authored.base_height_steps,
                authored.orientation,
            )
        events = EventQueue.get_events_chronological()
        assert isinstance(events[0], WorldInitializedEvent)
        assert events[0].phase is EventPhase.COMPLETION
        assert sum(
            event.event_type is EventType.WORLD_INITIALIZED
            for event in events
        ) == 1
        if built.environment is not None:
            condition = BaseCondition.get(built.environment.spike_condition_uuid)
            assert condition is not None
            assert condition.applied
            assert set(condition.affected_positions) == {
                (x, y) for x in range(5) for y in range(11, 15)
            }
        elif "landing_hazard" in built.object_uuids:
            condition = BaseCondition.get(built.object_uuids["landing_hazard"])
            assert condition is not None
            assert condition.applied
            assert set(condition.affected_positions) == {(11, 9)}
        else:
            assert get_map().get_spatial_conditions() == []
        torch_rows = [
            placement
            for placement in get_map().get_all_object_placements()
            if isinstance(BaseItem.get(placement.object_uuid), WallTorch)
        ]
        previous_item_fact_index = 0
        for placement in sorted(
            torch_rows,
            key=lambda row: (row.position, str(row.object_uuid)),
        ):
            torch = BaseItem.get(placement.object_uuid)
            assert isinstance(torch, WallTorch)
            assert torch.is_lit
            item_facts = [
                (index, event)
                for index, event in enumerate(events)
                if isinstance(event, ItemLocationStateEvent)
                and event.item_state.item_uuid == torch.uuid
            ]
            assert len(item_facts) == 1
            item_fact_index, item_fact = item_facts[0]
            torch_events = [
                (index, event)
                for index, event in enumerate(
                    events[previous_item_fact_index + 1:item_fact_index],
                    start=previous_item_fact_index + 1,
                )
                if index > previous_item_fact_index
                and (
                    (
                        isinstance(event, SpatialChangeEvent)
                        and event.event_type is EventType.SPATIAL_LIGHT_CHANGED
                        and event.phase is EventPhase.COMPLETION
                    )
                    or (
                        isinstance(event, SpatialEffectInteractionEvent)
                        and event.event_type is EventType.SPATIAL_EFFECT_INTERACTION
                        and event.operation.value == "ignite"
                        and event.source_object_uuid == torch.uuid
                        and event.target_entity_uuid == torch.uuid
                        and event.phase is EventPhase.COMPLETION
                    )
                )
            ]
            light_index = next(
                index for index, event in torch_events
                if isinstance(event, SpatialChangeEvent)
                and event.event_type is EventType.SPATIAL_LIGHT_CHANGED
            )
            ignite_index = next(
                index for index, event in torch_events
                if isinstance(event, SpatialEffectInteractionEvent)
            )
            assert light_index < ignite_index
            assert item_fact.item_state == torch.to_item_state()
            assert item_fact.world_placement == placement
            assert item_fact.parent_event == events[ignite_index].uuid
            previous_item_fact_index = item_fact_index
    reset_engine_runtime()


def test_reusable_deployments_fit_every_authored_roster() -> None:
    largest = max(
        len(slot.roster.members)
        for encounter in AUTHORED_ENCOUNTERS
        for slot in encounter.roster_slots
    )
    assert len(AUTHORED_DEPLOYMENTS) == 10
    for deployment in AUTHORED_DEPLOYMENTS:
        assert len(deployment.zones) == 2
        assert all(
            (zone.max_members or len(zone.ordered_slots)) >= largest
            for zone in deployment.zones
        )


def test_canonical_static_and_built_compatibility_agree() -> None:
    for recipe in AUTHORED_ENCOUNTERS:
        definition = get_battlefield(recipe.battlefield_id)
        static = check_encounter_compatibility(recipe, definition)
        assert static.admitted, (recipe.encounter_id, static.issues)
        reset_engine_runtime()
        build_battlefield(definition.battlefield_id)
        built = check_built_encounter_compatibility(
            static,
            recipe,
            get_map(),
        )
        assert built.admitted, (recipe.encounter_id, built.issues)
    reset_engine_runtime()


def test_battlefield_contract_is_renderer_neutral() -> None:
    payload = [row.model_dump(mode="json") for row in BATTLEFIELDS]
    serialized = repr(payload)
    assert "content_digest" not in serialized
    assert "sprite" not in serialized
    assert "visual_key" not in serialized
