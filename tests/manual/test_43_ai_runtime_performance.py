"""Regression contracts for latency-sensitive agent runtime infrastructure."""

from collections import Counter
import json
from types import SimpleNamespace
from typing import Any, Sequence, cast
from uuid import UUID, uuid4

import pytest

from dnd.ai.runtime import subjective_projection
from dnd.ai.contracts.observation import KnowledgeState
from dnd.ai.contracts.control import (
    ActionAffordance,
    AffordanceSet,
)
from dnd.ai.contracts.semantics import action_semantics_ref
from dnd.ai.runtime import decision_epoch as subjective_epochs
from dnd.ai.runtime.decision_epoch import _build_affordance_set_from_actions
from dnd.action_timing import reset_action_timing_recorder, set_action_timing_recorder
from dnd.actions import SpellAction, SpellEvent
from dnd.core.combat_log import SpellSaveLogData
from dnd.actions_functional import (execute_by_index, register_spell, free_aim_target,
    preview_available_selection, get_available_actions)
from dnd.spells.evocation import IceStorm
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena
from dnd.core.base_actions import BaseAction, TargetType
from dnd.core.aoe import AoEShape, Sphere, line_of_effect_reach
from dnd.core.base_block import LightLevel
from dnd.core.base_block import MovementMode
from dnd.core.base_tiles import Tile
from dnd.core.navigation import route_cost, route_destinations
from tests.engine.support import search_tables
from dnd.core.events import (
    Event,
    SavingThrowEvent,
    EventPhase,
    EventType,
    EventQueue,
    SensesUpdateHint,
    SpatialChangeEvent,
)
from dnd.core.geometry import (
    _centered_rectangle_offsets,
    _circle_relative_offsets,
    _supercover_line_cached,
    _supercover_line_relative_cached,
    circle_positions,
    rectangle_positions,
    supercover_line,
)
from dnd.core.gridmap import get_map
from dnd.types.world import SpatialChannel
from dnd.core.modifiers import NumericalModifier
from dnd.blocks.sensory import spatial_senses_system, capture_senses_snapshot
import dnd.core.gridmap as gridmap_module
from dnd.entity import Entity
from tests.manual.authored_encounter_support import (
    assemble_authored_encounter,
    reset_authored_encounter_state,
)
from dnd.core.values import Channel, Kind, add_modifier
from dnd.types.cells import no_cells
from dnd.core.cells import mask_positions


@pytest.fixture(autouse=True)
def fresh_engine_runtime() -> None:
    """Each case builds its own world on an empty runtime."""
    reset_authored_encounter_state()


def test_filtered_event_callbacks_skip_unrelated_events() -> None:
    """Passive event filters avoid callback churn without changing observers."""
    EventQueue.reset()
    filtered_calls: list[EventType] = []
    unfiltered_calls: list[EventType] = []
    filtered_sequences: list[tuple[EventType, ...]] = []
    unfiltered_sequences: list[tuple[EventType, ...]] = []

    def filtered_callback(event: Event) -> None:
        filtered_calls.append(event.event_type)

    def unfiltered_callback(event: Event) -> None:
        unfiltered_calls.append(event.event_type)

    def filtered_sequence(events: Sequence[Event]) -> None:
        filtered_sequences.append(tuple(event.event_type for event in events))

    def unfiltered_sequence(events: Sequence[Event]) -> None:
        unfiltered_sequences.append(tuple(event.event_type for event in events))

    EventQueue.add_on_event_callback(unfiltered_callback)
    EventQueue.add_on_event_callback(
        filtered_callback,
        event_types={EventType.SPATIAL_ENTITY_ENTERED},
        phases={EventPhase.COMPLETION},
    )
    EventQueue.add_on_event_sequence_callback(unfiltered_sequence)
    EventQueue.add_on_event_sequence_callback(
        filtered_sequence,
        phases={EventPhase.COMPLETION},
    )
    try:
        Event(
            source_entity_uuid=uuid4(),
            event_type=EventType.ATTACK,
            phase=EventPhase.COMPLETION,
        )
        Event(
            source_entity_uuid=uuid4(),
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            phase=EventPhase.DECLARATION,
        )
        Event(
            source_entity_uuid=uuid4(),
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            phase=EventPhase.COMPLETION,
        )
    finally:
        EventQueue.remove_on_event_callback(unfiltered_callback)
        EventQueue.remove_on_event_callback(filtered_callback)
        EventQueue.remove_on_event_sequence_callback(unfiltered_sequence)
        EventQueue.remove_on_event_sequence_callback(filtered_sequence)

    assert unfiltered_calls == [
        EventType.ATTACK,
        EventType.SPATIAL_ENTITY_ENTERED,
        EventType.SPATIAL_ENTITY_ENTERED,
    ]
    assert filtered_calls == [EventType.SPATIAL_ENTITY_ENTERED]
    assert unfiltered_sequences == [
        (EventType.ATTACK,),
        (EventType.SPATIAL_ENTITY_ENTERED,),
        (EventType.SPATIAL_ENTITY_ENTERED,),
    ]
    assert filtered_sequences == [
        (EventType.ATTACK,),
        (EventType.SPATIAL_ENTITY_ENTERED,),
    ]
    assert filtered_callback not in EventQueue._on_event_callback_filters
    assert filtered_sequence not in EventQueue._on_event_sequence_callback_filters









def test_footprint_limited_propagation_matches_full_fov_for_candidates() -> None:
    """Bounded propagation filtering is exact for a supplied AoE footprint."""
    assemble_authored_encounter("standard_skeleton_doors")
    grid = get_map()
    origin = (9, 7)
    candidate_positions = circle_positions(origin, radius=4)

    full_fov = set(grid.compute_propagation_fov(origin, 4))
    bounded = line_of_effect_reach(origin, candidate_positions)

    assert bounded == candidate_positions.intersection(full_fov)










def test_static_aoe_geometry_reuses_relative_offset_caches() -> None:
    """Repeated circle/square geometry should reuse immutable relative offsets."""
    _circle_relative_offsets.cache_clear()
    _centered_rectangle_offsets.cache_clear()

    first_circle = circle_positions((0, 0), radius=4)
    second_circle = circle_positions((10, 10), radius=4)
    first_rectangle = rectangle_positions((0, 0), size=5, centered=True)
    second_rectangle = rectangle_positions((10, 10), size=5, centered=True)

    first_circle.add((999, 999))
    first_rectangle.add((999, 999))

    assert (999, 999) not in second_circle
    assert (999, 999) not in second_rectangle
    assert _circle_relative_offsets.cache_info().hits == 1
    assert _centered_rectangle_offsets.cache_info().hits == 1


def test_supercover_line_reuses_immutable_geometry_cache() -> None:
    """Repeated ray geometry should reuse cached tuples while returning lists."""
    _supercover_line_relative_cached.cache_clear()
    _supercover_line_cached.cache_clear()

    first = supercover_line((0, 0), (8, 5))
    second = supercover_line((0, 0), (8, 5))
    first.append((999, 999))

    assert (999, 999) not in second
    assert _supercover_line_cached.cache_info().hits == 1


def test_supercover_line_reuses_relative_geometry_for_translated_rays() -> None:
    """Translated rays with the same delta should share line-generation work."""
    _supercover_line_relative_cached.cache_clear()
    _supercover_line_cached.cache_clear()

    first = supercover_line((0, 0), (8, 5))
    second = supercover_line((20, 30), (28, 35))

    assert first == [(x - 20, y - 30) for x, y in second]
    assert _supercover_line_cached.cache_info().misses == 2
    assert _supercover_line_relative_cached.cache_info().hits == 1


def test_subjective_aoe_preview_intersects_visibility_and_propagation() -> None:
    """A selected area discloses visible, reachable cells and perceived recipients."""
    reset_spell_regression_arena(12, 10)
    caster = create_spell_regression_actor("Preview Caster", (2, 4), "heroes", spell_slots={4: 1})
    target = create_spell_regression_actor("Visible Target", (5, 4), "monsters")
    hidden = create_spell_regression_actor("Hidden Target", (8, 4), "monsters")
    hidden.set_stealth_dc(100)
    for y in range(10):
        get_map().set_tile(7, y, blocks_optics=True, blocks_propagation=True, walking_cost=0)
    register_spell(caster, IceStorm)
    Entity.update_all_entities_senses(max_distance=100)
    actions = get_available_actions(caster, include_aoe_preview=False)
    row = next(row for row in actions.position_actions if row.base_template_name == "Ice Storm")
    aim = free_aim_target(row, target.position)
    preview = preview_available_selection(caster, row, (aim,))
    assert preview.can_confirm and preview.area_preview == "computed"
    assert target.uuid in preview.affected_entity_uuids
    assert hidden.uuid not in preview.affected_entity_uuids
    visible = set(mask_positions(capture_senses_snapshot(caster.senses).visible))
    assert set(preview.affected_positions) <= visible
    assert all(x <= 7 for x, _ in preview.affected_positions)


def test_observation_tile_projection_skips_hazard_scan_on_safe_maps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No-hazard maps should not perform entity-aware hazard checks per tile."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    actor.update_entity_senses(max_distance=20)
    grid = get_map()
    assert grid.has_any_hazards() is False

    def reject_hazard_scan(*_args: Any, **_kwargs: Any) -> bool:
        raise AssertionError("safe maps should use the projection hazard fast path")

    monkeypatch.setattr(grid, "is_position_hazardous_for", reject_hazard_scan)

    facts = tuple(
        subjective_projection.project_known_tiles(
            observers=[actor],
            prior_world=None,
        ).values()
    )

    assert facts
    assert all(fact.is_hazardous is False for fact in facts if fact.knowledge_state == KnowledgeState.VISIBLE)


def test_observation_tile_projection_keeps_entity_aware_hazard_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hazard-bearing maps must still resolve hazards for the observer entity."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    actor.update_entity_senses(max_distance=20)
    grid = get_map()
    calls = 0

    monkeypatch.setattr(grid, "has_any_hazards", lambda: True)

    def track_hazard_scan(*_args: Any, **_kwargs: Any) -> bool:
        nonlocal calls
        calls += 1
        return False

    monkeypatch.setattr(grid, "is_position_hazardous_for", track_hazard_scan)

    facts = tuple(
        subjective_projection.project_known_tiles(
            observers=[actor],
            prior_world=None,
        ).values()
    )

    assert facts
    assert calls > 0


def test_fireball_reports_each_resolved_save_roll_bonus() -> None:
    """Every actual creature recipient's event carries the resolved roll bonus."""
    arena = assemble_authored_encounter("caster_crossfire")
    mage = next(monster for monster in arena.monsters if "Mage" in monster.name)
    mage.update_entity_senses(max_distance=20)
    actions = mage.get_available_actions()
    row = next(row for row in actions.position_actions if row.base_template_name == "Fireball")
    aim = max(row.valid_targets, key=lambda candidate: candidate.affected_count or 0)
    expected_targets = set(aim.affected_entity_uuids or ())
    assert expected_targets
    cursor = EventQueue.event_cursor()
    event = execute_by_index(mage, row.template_name, aim.index, available=actions)
    assert event is not None and not event.canceled
    assert event.combat_log is not None
    applications = [child for child in event.combat_log.sub_entries
                    if isinstance(child.data, SpellSaveLogData)]
    assert {child.target_uuid for child in applications} == {str(identity) for identity in expected_targets}
    saves = [save for _, save in EventQueue.iter_events_since(cursor)
             if isinstance(save, SavingThrowEvent) and save.phase is EventPhase.COMPLETION]
    assert saves
    for child in applications:
        assert isinstance(child.data, SpellSaveLogData)
        resolved = next(save for save in saves if str(save.target_entity_uuid) == child.target_uuid)
        assert resolved.dice_roll is not None
        assert child.data.save_roll.bonus == resolved.dice_roll.bonus
        assert child.data.save_roll.total == resolved.dice_roll.total


def test_dense_epoch_wire_factors_shared_action_metadata_and_round_trips() -> None:
    """Dense legal rows travel as source definitions plus compact target references."""
    arena = assemble_authored_encounter("high_level_spell_resource_duel")
    archmage = next(monster for monster in arena.monsters if "Archmage" in monster.name)
    archmage.update_entity_senses(max_distance=20)
    affordances = _build_affordance_set_from_actions(
        archmage,
        archmage.get_available_actions(),
        42,
    )

    expanded_payload = {
        "actor_uuid": affordances.actor_uuid,
        "computed_at_observation_cursor": affordances.computed_at_observation_cursor,
        **{
            bucket: [row.model_dump(mode="json") for row in getattr(affordances, bucket)]
            for bucket in (
                "entity_actions",
                "position_actions",
                "self_actions",
                "object_actions",
                "special_commands",
            )
        },
        "capabilities": [row.model_dump(mode="json") for row in affordances.capabilities],
        "semantic_catalog": {
            reference: semantics.model_dump(mode="json")
            for reference, semantics in affordances.semantic_catalog.items()
        },
    }
    expanded_size = len(json.dumps(expanded_payload, separators=(",", ":")))
    wire_json = affordances.model_dump_json()
    wire_payload = json.loads(wire_json)
    restored = AffordanceSet.model_validate_json(wire_json)

    assert len(affordances.all_rows) > len(wire_payload["action_sources"])
    assert len(wire_json) < expanded_size * 0.55
    assert set(wire_payload["entity_actions"][0]) == {
        "row_id",
        "source_action_id",
        "target_indices",
    }
    assert wire_payload["target_catalog"]
    assert restored == affordances
    assert tuple(row.row_id for row in restored.all_rows) == tuple(
        row.row_id for row in affordances.all_rows
    )
    assert all(isinstance(row, ActionAffordance) for row in restored.all_rows)


def test_dense_epoch_factors_action_sources_in_memory() -> None:
    """Executable rows retain only row-local data and share source definitions."""
    arena = assemble_authored_encounter("high_level_spell_resource_duel")
    archmage = next(monster for monster in arena.monsters if "Archmage" in monster.name)
    archmage.update_entity_senses(max_distance=20)

    affordances = _build_affordance_set_from_actions(
        archmage,
        archmage.get_available_actions(),
        42,
    )
    regular_rows = tuple(
        row
        for row in affordances.all_rows
        if row.bucket != "special_commands"
    )
    source_by_id = {}
    for row in regular_rows:
        source = source_by_id.setdefault(row.source_action_id, row.source)
        assert row.source is source
        assert set(row.__dict__) == {"row_id", "source", "targets"}

    assert len(regular_rows) > len(source_by_id)
    assert len(source_by_id) == len(affordances.action_sources) - 1


def test_dense_epoch_wire_round_trip_preserves_factored_source_identity() -> None:
    """Wire parsing rebuilds one immutable source object per discovered action."""
    arena = assemble_authored_encounter("high_level_spell_resource_duel")
    archmage = next(monster for monster in arena.monsters if "Archmage" in monster.name)
    archmage.update_entity_senses(max_distance=20)
    affordances = _build_affordance_set_from_actions(
        archmage,
        archmage.get_available_actions(),
        42,
    )

    restored = AffordanceSet.model_validate_json(affordances.model_dump_json())
    source_by_id = {}
    for row in restored.all_rows:
        source = source_by_id.setdefault(row.source_action_id, row.source)
        assert row.source is source

    assert restored == affordances
    assert tuple(source_by_id.values()) == restored.action_sources


def test_epoch_hashes_each_distinct_semantic_contract_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capabilities and legal rows share one content address per contract."""
    arena = assemble_authored_encounter("caster_crossfire")
    mage = next(monster for monster in arena.monsters if "Mage" in monster.name)
    mage.update_entity_senses(max_distance=20)
    actions = mage.get_available_actions()
    original_epoch_semantics_ref = subjective_epochs.action_semantics_ref
    hash_calls = 0

    def track_epoch_semantics_ref(semantics: Any) -> str:
        nonlocal hash_calls
        hash_calls += 1
        return original_epoch_semantics_ref(semantics)

    monkeypatch.setattr(
        subjective_epochs,
        "action_semantics_ref",
        track_epoch_semantics_ref,
    )
    affordances = _build_affordance_set_from_actions(mage, actions, 42)

    assert affordances.semantic_catalog
    assert hash_calls == len(affordances.semantic_catalog)


def test_unchanged_epochs_reuse_only_exact_immutable_capability_values() -> None:
    """Fresh discovery can intern equal capabilities without caching legal rows."""
    subjective_epochs.clear_epoch_value_caches()
    arena = assemble_authored_encounter("high_level_spell_resource_duel")
    actor = next(monster for monster in arena.monsters if "Archmage" in monster.name)
    actor.update_entity_senses(max_distance=20)

    first_actions = actor.get_available_actions()
    first = _build_affordance_set_from_actions(actor, first_actions, 40)
    second_actions = actor.get_available_actions()
    second = _build_affordance_set_from_actions(actor, second_actions, 41)

    assert first_actions is not second_actions
    assert first.model_dump(mode="json") | {"computed_at_observation_cursor": 41} == second.model_dump(mode="json")
    assert all(
        first_capability is second_capability
        for first_capability, second_capability in zip(
            first.capabilities,
            second.capabilities,
            strict=True,
        )
    )

    actor.action_economy.consume("actions", 1, "cache invalidation probe")
    changed_actions = actor.get_available_actions()
    changed = _build_affordance_set_from_actions(actor, changed_actions, 42)
    first_by_id = {
        capability.capability_id: capability
        for capability in first.capabilities
    }
    assert any(
        first_by_id.get(capability.capability_id) is not capability
        for capability in changed.capabilities
    )

    changed_dump = changed.model_dump(mode="json")
    subjective_epochs.clear_epoch_value_caches()
    rebuilt = _build_affordance_set_from_actions(
        actor,
        actor.get_available_actions(),
        42,
    )
    assert rebuilt.model_dump(mode="json") == changed_dump


def test_zero_movement_dirty_paths_are_deferred_until_movement_exists() -> None:
    """No-movement epochs should not recompute Dijkstra just to discover rows."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    actor.update_entity_senses(max_distance=20)
    actor.action_economy.consume("movement", actor.action_economy.movement_remaining())
    actor.senses._paths_dirty = True
    phases: list[str] = []
    token = set_action_timing_recorder(lambda phase, _started: phases.append(phase))
    try:
        actions = actor.get_available_actions()
    finally:
        reset_action_timing_recorder(token)

    assert actor.senses._paths_dirty is True
    assert actions.remaining_movement == 0
    assert any(action.template_name == "Dash" for action in actions.self_actions)
    assert all("update_dirty_senses" not in phase for phase in phases)
    assert all("compute_paths" not in phase for phase in phases)
    assert "available_actions.skip_dirty_senses_no_movement_ms" in phases


def test_hazard_free_movement_choices_have_no_hazard_or_safe_alternative() -> None:
    """Local movement discovery reports actual route safety on an empty map."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    actor.update_entity_senses(max_distance=20)
    grid = get_map()
    assert grid.has_any_hazards() is False

    actions = actor.get_available_actions()
    move = next(row for row in actions.position_actions if row.template_name == "Move")
    assert move.valid_targets
    assert all(not target.is_path_hazardous and target.safe_path is None
               for target in move.valid_targets)











def test_dirty_action_discovery_limits_choices_to_movement_budget() -> None:
    """Refreshing dirty paths yields only routes that the current budget can pay."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    actor.update_entity_senses(max_distance=20)
    actor.senses._paths_dirty = True
    actions = actor.get_available_actions()
    move = next(row for row in actions.position_actions if row.template_name == "Move")
    assert move.valid_targets
    assert actor.senses.path_max_distance == actor.action_economy.movement_remaining() // 5
    assert all(target.path_cost is not None and target.path_cost <= actor.action_economy.movement_remaining()
               for target in move.valid_targets)


def test_dash_expands_limited_path_radius_when_movement_budget_grows() -> None:
    """Dash should force path expansion after a movement-budget-limited refresh."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    actor.update_entity_senses(max_distance=20)
    actor.senses._paths_dirty = True

    before_dash = actor.get_available_actions()
    assert actor.senses.path_max_distance == 6

    dash_event = execute_by_index(actor, "Dash", 0, available=before_dash)
    assert dash_event is not None
    assert "Dashing" in actor.active_conditions

    after_dash = actor.get_available_actions()

    assert after_dash.remaining_movement >= 60
    assert actor.senses.path_max_distance is not None
    assert actor.senses.path_max_distance >= 12


def test_full_budget_move_refreshes_visibility_without_full_path_radius() -> None:
    """A completed move should not recompute full-radius paths after movement is spent."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    actor.update_entity_senses(max_distance=20)
    available = actor.get_available_actions()
    move_info = next(
        action for action in available.position_actions
        if action.template_name == "Move"
    )
    full_budget_target = next(
        target for target in move_info.valid_targets
        if target.path_cost == available.remaining_movement
    )

    result = execute_by_index(
        actor,
        "Move",
        full_budget_target.index,
        available=available,
    )
    after = actor.get_available_actions()

    assert result is not None
    assert actor.action_economy.movement_remaining() == 0
    assert actor.senses.path_max_distance == 0
    assert actor.senses._paths_dirty is False
    assert not no_cells(capture_senses_snapshot(actor.senses).visible)
    assert after.remaining_movement == 0
    exhausted_move = next(
        action
        for action in after.position_actions
        if action.template_name == "Move"
    )
    assert exhausted_move.can_afford is True
    assert exhausted_move.availability_status == "target_cost_unaffordable"
    assert exhausted_move.valid_targets == []


def test_grid_compute_paths_reuses_same_revision_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated identical path queries should not rerun Dijkstra."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    grid = get_map()
    grid._path_cache.clear()
    solver_calls = 0
    original_dijkstra = gridmap_module.GridMap._dijkstra
    original_bfs = gridmap_module.GridMap._breadth_first

    def track_dijkstra(*args: Any, **kwargs: Any) -> Any:
        nonlocal solver_calls
        solver_calls += 1
        return original_dijkstra(*args, **kwargs)

    def track_bfs(*args: Any, **kwargs: Any) -> Any:
        nonlocal solver_calls
        solver_calls += 1
        return original_bfs(*args, **kwargs)

    monkeypatch.setattr(gridmap_module.GridMap, "_dijkstra", staticmethod(track_dijkstra))
    monkeypatch.setattr(gridmap_module.GridMap, "_breadth_first", staticmethod(track_bfs))

    first_distances, first_paths = search_tables(grid.compute_paths(
        actor.position,
        max_distance=20,
        requesting_entity_uuid=actor.uuid,
        subjective=True,
    ))
    second_distances, second_paths = search_tables(grid.compute_paths(
        actor.position,
        max_distance=20,
        requesting_entity_uuid=actor.uuid,
        subjective=True,
    ))

    assert solver_calls == 1
    assert second_distances == first_distances
    assert second_paths == first_paths
    kept = grid.compute_paths(actor.position, max_distance=20, requesting_entity_uuid=actor.uuid, subjective=True)
    assert not kept.tree.pred.flags.writeable and not kept.destinations.flags.writeable


def test_unit_cost_paths_use_breadth_first_fast_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unit-cost maps should use BFS while preserving compute_paths output."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    grid = get_map()
    grid._path_cache.clear()
    dijkstra_calls = 0
    bfs_calls = 0
    original_bfs = gridmap_module.GridMap._breadth_first

    def reject_dijkstra(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal dijkstra_calls
        dijkstra_calls += 1
        raise AssertionError("unit-cost maps should not use Dijkstra")

    def track_bfs(*args: Any, **kwargs: Any) -> Any:
        nonlocal bfs_calls
        bfs_calls += 1
        return original_bfs(*args, **kwargs)

    monkeypatch.setattr(gridmap_module.GridMap, "_dijkstra", staticmethod(reject_dijkstra))
    monkeypatch.setattr(gridmap_module.GridMap, "_breadth_first", staticmethod(track_bfs))

    distances, paths = search_tables(grid.compute_paths(
        actor.position,
        max_distance=6,
        requesting_entity_uuid=actor.uuid,
        subjective=True,
    ))

    assert dijkstra_calls == 0
    assert bfs_calls == 1
    assert distances[actor.position] == 0
    assert paths[actor.position] == [actor.position]


def test_weighted_paths_preserve_exact_terrain_costs() -> None:
    """Terrain weights contribute to route costs regardless of solver choice."""
    get_map().create_rectangle(0, 0, 5, 1)
    grid = get_map()
    grid.set_tile(2, 0, walking_cost=3)
    distances, paths = search_tables(grid.compute_paths((0, 0), movement_mode=MovementMode.WALKING))
    easy, _ = search_tables(grid.compute_paths((0, 0), movement_mode=MovementMode.WALKING,
                                               ignore_difficult_terrain=True))
    assert distances[(4, 0)] == 6
    assert easy[(4, 0)] == 4
    assert paths[(4, 0)] == [(x, 0) for x in range(5)]


def test_move_discovery_uses_cached_senses_path_costs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Movement rows should reuse pathfinder distances stored on senses."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    actor.update_entity_senses(max_distance=20)

    def reject_path_rescan(*_args: Any, **_kwargs: Any) -> int:
        raise AssertionError("movement discovery should use cached path costs")

    monkeypatch.setattr(Entity, "movement_path_cost_feet", reject_path_rescan)

    available = actor.get_available_actions()
    move_info = next(
        action for action in available.position_actions
        if action.template_name == "Move"
    )

    assert move_info.valid_targets
    assert route_destinations(actor.senses.paths)
    for target in move_info.valid_targets:
        assert target.position is not None
        assert target.path_cost == route_cost(actor.senses.paths, target.position)


def test_weighted_move_discovery_uses_cached_senses_path_costs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cached path costs preserve weighted terrain in movement rows."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    grid = get_map()
    actor.update_entity_senses(max_distance=20)
    difficult_position = next(
        position for position in route_destinations(actor.senses.paths)
        if position != actor.position
        and 0 < (route_cost(actor.senses.paths, position) or 0) <= actor.action_economy.movement_remaining()
    )
    difficult_tile = grid.get_tile(*difficult_position)
    assert difficult_tile is not None
    add_modifier(difficult_tile.edit_movement_cost(MovementMode.WALKING), Channel.SELF_STATIC, Kind.VALUE, NumericalModifier.create(
            source_entity_uuid=difficult_tile.uuid,
            name="Cached Cost Difficult Terrain",
            value=1,
        ))
    grid._path_cache.clear()
    actor.update_entity_senses(max_distance=20)

    def reject_path_rescan(*_args: Any, **_kwargs: Any) -> int:
        raise AssertionError("weighted movement discovery should use cached path costs")

    monkeypatch.setattr(Entity, "movement_path_cost_feet", reject_path_rescan)

    available = actor.get_available_actions()
    move_info = next(
        action for action in available.position_actions
        if action.template_name == "Move"
    )
    target = next(
        target for target in move_info.valid_targets
        if target.position == difficult_position
    )

    assert (route_cost(actor.senses.paths, difficult_position) or 0) >= 10
    assert target.path_cost == route_cost(actor.senses.paths, difficult_position)


def test_grid_compute_paths_invalidates_on_occupancy_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Entity movement/blocking changes must invalidate cached paths."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    blocker = arena.monsters[0]
    grid = get_map()
    grid._path_cache.clear()
    solver_calls = 0
    original_dijkstra = gridmap_module.GridMap._dijkstra
    original_bfs = gridmap_module.GridMap._breadth_first

    def track_dijkstra(*args: Any, **kwargs: Any) -> Any:
        nonlocal solver_calls
        solver_calls += 1
        return original_dijkstra(*args, **kwargs)

    def track_bfs(*args: Any, **kwargs: Any) -> Any:
        nonlocal solver_calls
        solver_calls += 1
        return original_bfs(*args, **kwargs)

    monkeypatch.setattr(gridmap_module.GridMap, "_dijkstra", staticmethod(track_dijkstra))
    monkeypatch.setattr(gridmap_module.GridMap, "_breadth_first", staticmethod(track_bfs))

    grid.compute_paths(
        actor.position,
        max_distance=20,
        requesting_entity_uuid=actor.uuid,
        subjective=True,
    )
    grid.compute_paths(
        actor.position,
        max_distance=20,
        requesting_entity_uuid=actor.uuid,
        subjective=True,
    )
    assert solver_calls == 1

    Entity.update_entity_position(blocker, (blocker.position[0], blocker.position[1] + 1))
    grid.compute_paths(
        actor.position,
        max_distance=20,
        requesting_entity_uuid=actor.uuid,
        subjective=True,
    )

    assert solver_calls == 2
