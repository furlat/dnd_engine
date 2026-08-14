"""Maintained product battlefield coverage for elevation traversal."""

import pytest

from dnd.core.base_block import BaseBlock, MovementMode
from dnd.core.equipment_types import WeaponSlot
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.events import EventPhase, EventQueue, EventType
from dnd.core.elevation import support_distance_feet
from dnd.core.content import battlefields as battlefield_contracts
from dnd.core.content.battlefields import (
    BattlefieldDefinition,
    BattlefieldElevationCell,
    BattlefieldPreview,
)
from dnd.core.gridmap import get_map
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.core.traversal_connectors import TraversalConnectorKind
from dnd.items.environment import DirectionalDoor, OpenDirectionalDoorAction
from dnd.actions import (
    Attack,
    AttackEvent,
    Jump,
    JumpEvent,
    Move,
    MovementEvent,
    TraverseConnectorEvent,
)
from dnd.actions_functional import execute_available_action
from dnd.encounter import EncounterState
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield, get_battlefield
from dnd.scenarios.encounter_assembler import assemble_encounter_recipe
from dnd.scenarios.encounter_catalog import encounter_recipe
from dnd.spatial_effects import SpatialEffect
from server.world_projection import project_encounter, project_grid


PROVING_BATTLEFIELD_ID = "battlefield.elevation_proving_ground"


def test_elevation_proving_battlefield_cold_preview_matches_runtime() -> None:
    definition = get_battlefield(PROVING_BATTLEFIELD_ID)
    reset_engine_runtime(grid_size=(definition.width, definition.height))
    built = build_battlefield(PROVING_BATTLEFIELD_ID)
    grid = get_map()

    assert built.definition is definition
    assert set(definition.capabilities) >= {
        "bright-light",
        "closed-door",
        "progressive-stairs",
        "progressive-ramp",
        "cliff",
        "jump-gap",
        "landing-hazard",
        "ladder",
        "rope",
        "lift",
        "vertical-stairs",
        "passage",
    }
    for authored in definition.preview.elevation_cells:
        tile = grid.get_tile(*authored.position)
        assert tile is not None
        assert (
            tile.height,
            tile.elevation_surface_kind,
            tile.slope_axis,
        ) == (
            authored.elevation_steps,
            authored.surface_kind,
            authored.slope_axis,
        )

    gap = grid.get_tile(10, 9)
    assert gap is not None and gap.walkable is False
    preview_gap = next(
        cell for cell in definition.preview.cells if cell.position == (10, 9)
    )
    projected_gap = next(
        tile for tile in project_grid(grid).tiles if (tile.x, tile.y) == (10, 9)
    )
    assert preview_gap.terrain == "gap"
    assert gap.name == "Gap"
    assert gap.sprite_name == "gap.png"
    assert gap.get_movement_cost(MovementMode.WALKING) == 0
    assert gap.get_movement_cost(MovementMode.SWIMMING) == 0
    assert projected_gap.visual_key == "gap.png"
    assert projected_gap.walkable is False
    landing = grid.get_tile(11, 9)
    assert landing is not None and landing.height == 1
    assert SpatialEffect.get_effect(built.object_uuids["landing_hazard"]) is not None
    authored_connectors = definition.preview.connectors
    runtime_connectors = grid.get_all_connectors()
    assert {row.kind for row in authored_connectors} == set(TraversalConnectorKind)
    assert [row.authored_id for row in runtime_connectors] == sorted(
        row.authored_id for row in authored_connectors
    )
    assert {
        row.authored_id: row.definition()
        for row in runtime_connectors
    } == {
        row.authored_id: row
        for row in authored_connectors
    }
    projected_by_id = {
        row.authored_id: row
        for row in project_grid(grid).connectors
    }
    assert set(projected_by_id) == {
        row.authored_id for row in authored_connectors
    }
    for connector in runtime_connectors:
        projected = projected_by_id[connector.authored_id]
        assert projected.uuid == str(connector.uuid)
        assert projected.objective_digest == connector.objective_digest
        assert tuple(endpoint.position for endpoint in projected.endpoints) == tuple(
            endpoint.position for endpoint in connector.endpoints
        )


def test_elevation_proving_battlefield_exercises_reciprocal_edge_rules() -> None:
    reset_engine_runtime()
    built = build_battlefield(PROVING_BATTLEFIELD_ID)
    grid = get_map()

    for left, right in (((5, 4), (6, 4)), ((6, 4), (7, 4))):
        assert grid.can_transition(left, right, movement_mode=MovementMode.WALKING)
        assert grid.can_transition(right, left, movement_mode=MovementMode.WALKING)
    for left, right in (((6, 10), (7, 10)), ((7, 10), (8, 10))):
        assert grid.can_transition(left, right, movement_mode=MovementMode.WALKING)
        assert grid.can_transition(right, left, movement_mode=MovementMode.WALKING)
    assert not grid.can_transition(
        (10, 5),
        (11, 5),
        movement_mode=MovementMode.WALKING,
    )
    assert grid.can_transition(
        (10, 5),
        (11, 5),
        movement_mode=MovementMode.FLYING,
    )

    door = BaseBlock.get(built.object_uuids["door"])
    assert isinstance(door, DirectionalDoor)
    assert not grid.can_transition(
        (3, 7),
        (4, 7),
        movement_mode=MovementMode.WALKING,
    )
    closed = grid.get_world_edge((3, 7), (4, 7))
    door.open()
    opened = grid.get_world_edge((4, 7), (3, 7))
    assert grid.can_transition(
        (3, 7),
        (4, 7),
        movement_mode=MovementMode.WALKING,
    )
    assert closed.key == opened.key
    assert any(row.provider_uuid == door.uuid for row in closed.structural_contributions)
    assert any(row.provider_uuid == door.uuid for row in opened.structural_contributions)


def test_elevation_proving_battlefield_surface_axes_are_authored_not_inferred() -> None:
    definition = get_battlefield(PROVING_BATTLEFIELD_ID)
    by_position = {
        cell.position: cell for cell in definition.preview.elevation_cells
    }
    assert by_position[(5, 4)].surface_kind is ElevationSurfaceKind.STAIRS
    assert by_position[(5, 4)].slope_axis is SlopeAxis.EAST_WEST
    assert by_position[(6, 10)].surface_kind is ElevationSurfaceKind.RAMP
    assert by_position[(6, 10)].slope_axis is SlopeAxis.EAST_WEST
    assert by_position[(11, 5)].surface_kind is ElevationSurfaceKind.ORDINARY
    assert by_position[(11, 5)].slope_axis is None


def test_cold_battlefield_rejects_contradictory_progressive_run() -> None:
    with pytest.raises(ValueError, match="contradictory progressive elevation"):
        BattlefieldDefinition(
            battlefield_id="battlefield.invalid_progressive",
            title="Invalid Progressive",
            width=3,
            height=1,
            preview=BattlefieldPreview(elevation_cells=(
                BattlefieldElevationCell(
                    position=(0, 0),
                    elevation_steps=0,
                    surface_kind=ElevationSurfaceKind.RAMP,
                    slope_axis=SlopeAxis.EAST_WEST,
                ),
                BattlefieldElevationCell(
                    position=(1, 0),
                    elevation_steps=2,
                    surface_kind=ElevationSurfaceKind.RAMP,
                    slope_axis=SlopeAxis.EAST_WEST,
                ),
            )),
        )


def test_empty_cold_battlefield_preflight_is_linear_in_authored_elevation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inspected_sizes: list[int] = []

    def inspect_authored(cells, **_kwargs):
        inspected_sizes.append(len(cells))
        return None

    monkeypatch.setattr(
        battlefield_contracts,
        "contradictory_progressive_elevation_edge",
        inspect_authored,
    )
    BattlefieldDefinition(
        battlefield_id="battlefield.large_empty",
        title="Large Empty",
        width=1_000_000,
        height=1_000_000,
    )

    assert inspected_sizes == [0]


def test_proving_battlefield_traverses_every_connector_kind_through_one_action() -> None:
    definition = get_battlefield(PROVING_BATTLEFIELD_ID)
    reset_engine_runtime(grid_size=(definition.width, definition.height))
    build_battlefield(PROVING_BATTLEFIELD_ID)
    actor = create_skeleton(
        name="Connector Prover",
        position=definition.preview.connectors[0].endpoint_positions[0],
        faction="heroes",
    )

    seen_kinds: set[TraversalConnectorKind] = set()
    for authored in definition.preview.connectors:
        Entity.update_entity_position(actor, authored.endpoint_positions[0])
        actor.action_economy.reset_all_costs()
        Entity.update_all_entities_senses(max_distance=30)
        row = next(
            row
            for row in actor.get_available_actions(legal_only=True).self_actions
            if row.connector_traversal is not None
            and row.connector_traversal.authored_id == authored.authored_id
        )

        result = execute_available_action(actor, row, row.valid_targets[0])

        assert type(result) is TraverseConnectorEvent
        assert result.phase is EventPhase.COMPLETION
        assert result.end_position == authored.endpoint_positions[1]
        assert actor.position == authored.endpoint_positions[1]
        assert result.combat_log is not None
        assert result.combat_log.data["distance_feet"] == support_distance_feet(
            authored.endpoint_positions[0],
            result.start_elevation_feet,
            authored.endpoint_positions[1],
            result.end_elevation_feet,
        )
        assert result.combat_log.data["movement_cost"] == (
            authored.movement_cost_feet
        )
        seen_kinds.add(result.connector_kind)

    assert seen_kinds == set(TraversalConnectorKind)


def test_product_proving_encounter_plays_every_vertical_surface_and_terminates() -> None:
    """The participant-neutral composition remains playable through owners."""
    recipe = encounter_recipe("encounter.elevation_proving_ground")
    assert all(slot.participant_name for slot in recipe.roster_slots)
    assembled = assemble_encounter_recipe(recipe, start_encounter=True)
    encounter = assembled.encounter
    hero = assembled.entities_by_roster_slot["roster_1"][0]
    monsters = assembled.entities_by_roster_slot["roster_2"]
    grid = get_map()
    landing_hazard = SpatialEffect.get_effect(
        assembled.battlefield.object_uuids["landing_hazard"]
    )
    assert landing_hazard is not None
    landing_hazard_identity = landing_hazard.content_ref.identity_key

    assert encounter.state is EncounterState.ACTIVE
    assert hero.position == (2, 7)
    assert [monster.position for monster in monsters] == [
        (8, 4),
        (11, 5),
        (12, 7),
    ]
    for monster, position in zip(monsters, ((13, 1), (13, 2), (13, 3))):
        Entity.update_entity_position(monster, position)

    def stage_actor(position: tuple[int, int]) -> None:
        Entity.update_entity_position(hero, position)
        hero.action_economy.reset_all_costs()
        Entity.update_all_entities_senses(max_distance=30)

    def complete_move(path: tuple[tuple[int, int], ...]) -> MovementEvent:
        result = Move(
            source_entity_uuid=hero.uuid,
            end_position=path[-1],
            path=path,
            prefer_safe=False,
        ).apply()
        assert type(result) is MovementEvent
        assert result.phase is EventPhase.COMPLETION
        assert result.end_position == path[-1]
        assert hero.position == path[-1]
        return result

    stage_actor((1, 1))
    complete_move(((1, 1), (2, 1)))

    stage_actor((3, 7))
    door = BaseBlock.get(assembled.battlefield.object_uuids["door"])
    assert isinstance(door, DirectionalDoor)
    opened = OpenDirectionalDoorAction(
        source_entity_uuid=hero.uuid,
        source_item_uuid=door.uuid,
    ).apply()
    assert opened is not None and opened.phase is EventPhase.COMPLETION
    assert door.is_open is True
    Entity.update_all_entities_senses(max_distance=30)
    complete_move(((3, 7), (4, 7)))

    stage_actor((5, 4))
    complete_move(((5, 4), (6, 4), (7, 4), (8, 4)))
    stage_actor((5, 10))
    complete_move(((5, 10), (6, 10), (7, 10), (8, 10)))

    stage_actor((10, 5))
    cliff = Move(
        source_entity_uuid=hero.uuid,
        end_position=(11, 5),
        path=((10, 5), (11, 5)),
        prefer_safe=False,
    ).apply()
    assert type(cliff) is MovementEvent
    assert cliff.phase is EventPhase.CANCEL
    assert hero.position == (10, 5)

    elevated_target = monsters[0]
    Entity.update_entity_position(elevated_target, (11, 5))
    stage_actor((10, 5))
    legal_attack = Attack(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=elevated_target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    ).apply()
    assert type(legal_attack) is AttackEvent
    assert legal_attack.phase is EventPhase.COMPLETION
    assert hero.distance_to_entity(elevated_target) == 5

    stage_actor((9, 5))
    illegal_attack = Attack(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=elevated_target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    ).apply()
    assert type(illegal_attack) is AttackEvent
    assert illegal_attack.phase is EventPhase.CANCEL
    assert hero.distance_to_entity(elevated_target) == 10

    Entity.update_entity_position(elevated_target, (9, 8))
    elevated_target.action_economy.reset_all_costs()
    stage_actor((9, 9))
    hp_before_landing = hero.get_hp()
    landing_event_cursor = EventQueue.event_cursor()
    jumped = Jump(
        source_entity_uuid=hero.uuid,
        end_position=(11, 9),
    ).apply()
    assert type(jumped) is JumpEvent
    assert jumped.phase is EventPhase.COMPLETION
    assert jumped.end_position == (11, 9)
    assert hero.position == (11, 9)
    assert elevated_target.action_economy.reactions.normalized_score == 0
    assert hero.get_hp() < hp_before_landing
    trap_damage = [
        event
        for _, event in EventQueue.iter_events_since(landing_event_cursor)
        if event.event_type is EventType.TAKE_DAMAGE
        and event.phase is EventPhase.COMPLETION
        and getattr(event, "effect_id", None)
        == landing_hazard_identity
    ]
    assert len(trap_damage) == 1
    assert trap_damage[0].combat_log is not None
    assert getattr(trap_damage[0], "resulting_hp", None) == hero.get_hp()
    assert jumped.combat_log is not None

    def nested_logs(entry: CombatLogEntry) -> tuple[CombatLogEntry, ...]:
        return (
            entry,
            *(
                child
                for sub_entry in entry.sub_entries
                for child in nested_logs(sub_entry)
            ),
        )

    assert any(
        entry.entry_type is CombatLogEntryType.DAMAGE_TAKEN
        and entry.data.get("effect_id")
        == landing_hazard_identity
        for entry in nested_logs(jumped.combat_log)
    )

    for monster, position in zip(monsters, ((13, 1), (13, 2), (13, 3))):
        Entity.update_entity_position(monster, position)
    seen_kinds: set[TraversalConnectorKind] = set()
    for authored in assembled.battlefield.definition.preview.connectors:
        stage_actor(authored.endpoint_positions[0])
        row = next(
            row
            for row in hero.get_available_actions(legal_only=True).self_actions
            if row.connector_traversal is not None
            and row.connector_traversal.authored_id == authored.authored_id
        )
        traversed = execute_available_action(hero, row, row.valid_targets[0])
        assert type(traversed) is TraverseConnectorEvent
        assert traversed.phase is EventPhase.COMPLETION
        assert traversed.end_position == authored.endpoint_positions[1]
        seen_kinds.add(traversed.connector_kind)
    assert seen_kinds == set(TraversalConnectorKind)

    projected_grid = project_grid(grid)
    projected_encounter = project_encounter(encounter, (hero, *monsters))
    assert type(projected_grid).model_validate_json(
        projected_grid.model_dump_json(),
    ) == projected_grid
    assert type(projected_encounter).model_validate_json(
        projected_encounter.model_dump_json(),
    ) == projected_encounter
    assert len(projected_grid.connectors) == len(TraversalConnectorKind)
    assert projected_encounter.state == EncounterState.ACTIVE.value

    end_event = encounter.end_encounter("Elevation proving flow complete")
    assert end_event.phase is EventPhase.COMPLETION
    assert encounter.state is EncounterState.ENDED
    assert project_encounter(encounter, (hero, *monsters)).state == (
        EncounterState.ENDED.value
    )
