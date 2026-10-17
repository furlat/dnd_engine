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
from dnd.actions import SpellAction
from dnd.actions_functional import execute_by_index
from dnd.core.base_actions import BaseAction, TargetType
from dnd.core.aoe import AoEShape, Sphere
from dnd.core.base_block import LightLevel
from dnd.core.base_block import MovementMode
from dnd.core.base_tiles import Tile
from dnd.core.dijkstra import dijkstra
from dnd.core.events import (
    Event,
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


def test_epoch_build_expands_registered_action_variants_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One epoch reuses one fresh discovery snapshot across rows and capabilities."""
    arena = assemble_authored_encounter("high_level_spell_resource_duel")
    archmage = next(monster for monster in arena.monsters if "Archmage" in monster.name)
    archmage.update_entity_senses(max_distance=20)
    base_variant_calls: Counter[str] = Counter()
    spell_variant_calls: Counter[str] = Counter()
    make_info_calls = 0
    original_base_variants = BaseAction.get_discovery_variants
    original_spell_variants = SpellAction.get_discovery_variants
    original_make_info = Entity._make_action_info

    def track_base_variants(self: BaseAction, entity: Any) -> list[BaseAction]:
        base_variant_calls[str(self.uuid)] += 1
        return original_base_variants(self, entity)

    def track_spell_variants(self: SpellAction, entity: Any) -> list[BaseAction]:
        spell_variant_calls[str(self.uuid)] += 1
        return original_spell_variants(self, entity)

    def track_make_info(self: Entity, *args: Any, **kwargs: Any):
        nonlocal make_info_calls
        make_info_calls += 1
        return original_make_info(self, *args, **kwargs)

    monkeypatch.setattr(BaseAction, "get_discovery_variants", track_base_variants)
    monkeypatch.setattr(SpellAction, "get_discovery_variants", track_spell_variants)
    monkeypatch.setattr(Entity, "_make_action_info", track_make_info)

    actions = archmage.get_available_actions(legal_only=True)
    row_build_make_info_calls = make_info_calls
    affordances = _build_affordance_set_from_actions(archmage, actions, 42)
    capability_make_info_calls = make_info_calls - row_build_make_info_calls
    discovered_sources = {
        (
            row.template_name,
            row.target_type.value,
            str(row.source_item_uuid) if row.source_item_uuid is not None else None,
        )
        for row in actions.all_actions
    }
    capability_sources = [
        (variant, None)
        for variant in actions.registered_action_variants
    ] + [
        (
            variant,
            str(variant.source_item_uuid) if variant.source_item_uuid is not None else None,
        )
        for variant in actions.inventory_use_action_sources
    ]
    missing_capability_rows = sum(
        (
            variant.get_discovery_template_name(),
            variant.effective_target_type.value,
            source_item_uuid,
        ) not in discovered_sources
        for variant, source_item_uuid in capability_sources
    )

    assert affordances.capabilities
    regular_rows = tuple(
        row
        for row in affordances.all_rows
        if row.bucket != "special_commands"
    )
    source_counts = Counter(row.source_action_id for row in regular_rows)
    assert None not in source_counts
    assert len(source_counts) == len(actions.all_actions)
    assert max(source_counts.values()) > 1
    registered_spells = tuple(
        template
        for template in archmage.registered_actions
        if isinstance(template, SpellAction)
    )
    registered_non_spells = tuple(
        template
        for template in archmage.registered_actions
        if not isinstance(template, SpellAction)
    )
    assert set(spell_variant_calls) == {
        str(template.uuid)
        for template in registered_spells
    }
    assert set(spell_variant_calls.values()) == {1}
    assert set(base_variant_calls) == {
        str(template.uuid)
        for template in registered_non_spells
    } | {
        str(variant.uuid)
        for variant in actions.registered_action_variants
        if isinstance(variant, SpellAction)
    }
    assert set(base_variant_calls.values()) == {1}
    assert capability_make_info_calls == missing_capability_rows


def test_epoch_derives_semantics_and_cost_once_per_source_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capabilities and affordances reuse one build-local row descriptor."""
    arena = assemble_authored_encounter("high_level_spell_resource_duel")
    archmage = next(monster for monster in arena.monsters if "Archmage" in monster.name)
    archmage.update_entity_senses(max_distance=20)
    actions = archmage.get_available_actions()
    subjective_epochs.clear_epoch_value_caches()
    original_semantics = subjective_epochs.action_semantics_for_available_action
    original_cost = subjective_epochs._action_cost_profile_from_action
    semantics_calls = 0
    cost_calls = 0

    def track_semantics(row: Any):
        nonlocal semantics_calls
        semantics_calls += 1
        return original_semantics(row)

    def track_cost(row: Any):
        nonlocal cost_calls
        cost_calls += 1
        return original_cost(row)

    monkeypatch.setattr(
        subjective_epochs,
        "action_semantics_for_available_action",
        track_semantics,
    )
    monkeypatch.setattr(
        subjective_epochs,
        "_action_cost_profile_from_action",
        track_cost,
    )

    available_source_keys = {
        subjective_epochs._capability_row_lookup_key(row)
        for row in actions.all_actions
    }
    capability_sources = [
        (variant, None)
        for variant in actions.registered_action_variants
    ] + [
        (
            variant,
            str(variant.source_item_uuid) if variant.source_item_uuid is not None else None,
        )
        for variant in actions.inventory_use_action_sources
    ]
    missing_capability_count = sum(
        subjective_epochs._capability_template_lookup_key(variant, source_item_uuid)
        not in available_source_keys
        for variant, source_item_uuid in capability_sources
    )
    expected_derivations = len(actions.all_actions) + missing_capability_count

    affordances = _build_affordance_set_from_actions(archmage, actions, 42)

    assert affordances.capabilities
    assert semantics_calls == expected_derivations
    assert cost_calls == expected_derivations


def test_aoe_shape_definition_is_not_serialized_per_candidate_cell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AoE discovery reuses one immutable shape key across candidate cells."""
    arena = assemble_authored_encounter("caster_crossfire")
    mage = next(monster for monster in arena.monsters if "Mage" in monster.name)
    mage.update_entity_senses(max_distance=20)
    original_shape_key = Entity._aoe_shape_definition_key
    shape_key_calls = 0

    def track_shape_key(shape: Any) -> tuple[Any, ...]:
        nonlocal shape_key_calls
        shape_key_calls += 1
        return original_shape_key(shape)

    monkeypatch.setattr(
        Entity,
        "_aoe_shape_definition_key",
        staticmethod(track_shape_key),
    )

    actions = mage.get_available_actions()
    aoe_rows = [
        row
        for row in actions.position_actions
        if row.target_type is TargetType.POSITION_AOE
    ]
    aoe_variants = [
        variant
        for variant in actions.registered_action_variants
        if variant.effective_target_type is TargetType.POSITION_AOE
        and variant.check_costs()
    ]

    assert aoe_rows
    assert sum(len(row.valid_targets) for row in aoe_rows) > 10
    assert shape_key_calls == len(aoe_variants)


def test_footprint_limited_propagation_matches_full_fov_for_candidates() -> None:
    """Bounded propagation filtering is exact for a supplied AoE footprint."""
    assemble_authored_encounter("standard_skeleton_doors")
    grid = get_map()
    origin = (9, 7)
    candidate_positions = circle_positions(origin, radius=4)

    full_fov = set(grid.compute_propagation_fov(origin, 4))
    bounded = grid.filter_propagation_positions(origin, candidate_positions, 4)

    assert bounded == candidate_positions.intersection(full_fov)


def test_footprint_limited_propagation_reuses_identical_candidate_filters() -> None:
    """Repeated spell footprints should share one physical-propagation filter."""
    assemble_authored_encounter("standard_skeleton_doors")
    grid = get_map()
    origin = (9, 7)
    candidate_positions = circle_positions(origin, radius=4)
    phases: list[str] = []

    token = set_action_timing_recorder(lambda phase, _started: phases.append(phase))
    try:
        first = grid.filter_propagation_positions(origin, candidate_positions, 4)
        second = grid.filter_propagation_positions(origin, set(candidate_positions), 4)
    finally:
        reset_action_timing_recorder(token)

    assert second == first
    assert "grid.filter_propagation_positions.cache_miss_ms" in phases
    assert "grid.filter_propagation_positions.cache_hit_ms" in phases
    assert len(grid._propagation_filter_cache) == 1

    grid._bump_spatial_revisions(frozenset({SpatialChannel.PROPAGATION}))

    assert grid._propagation_filter_cache == {}


def test_aoe_preview_filters_footprints_without_full_origin_fov(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AoE previews filter known footprints instead of scanning full origin FOV."""
    arena = assemble_authored_encounter("caster_crossfire")
    mage = next(monster for monster in arena.monsters if "Mage" in monster.name)
    mage.update_entity_senses(max_distance=20)
    grid = get_map()
    original_filter_propagation_positions = grid.filter_propagation_positions
    original_compute_propagation_fov = grid.compute_propagation_fov
    filter_calls = 0
    propagation_fov_calls = 0

    def track_filter_propagation_positions(
        origin: tuple[int, int],
        positions: set[tuple[int, int]],
        max_distance: float | None = None,
    ) -> set[tuple[int, int]]:
        nonlocal filter_calls
        filter_calls += 1
        return original_filter_propagation_positions(origin, positions, max_distance)

    def track_compute_propagation_fov(
        origin: tuple[int, int],
        max_distance: float | None = None,
    ) -> list[tuple[int, int]]:
        nonlocal propagation_fov_calls
        propagation_fov_calls += 1
        return original_compute_propagation_fov(origin, max_distance)

    monkeypatch.setattr(
        grid,
        "filter_propagation_positions",
        track_filter_propagation_positions,
    )
    monkeypatch.setattr(grid, "compute_propagation_fov", track_compute_propagation_fov)

    actions = mage.get_available_actions()
    aoe_target_count = sum(
        len(row.valid_targets)
        for row in actions.position_actions
        if row.target_type is TargetType.POSITION_AOE
    )

    assert aoe_target_count > 10
    assert filter_calls > 0
    assert propagation_fov_calls == 0


def test_aoe_discovery_reuses_one_preview_shape_per_variant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AoE preview discovery should not clone a shape for every candidate cell."""
    arena = assemble_authored_encounter("caster_crossfire")
    mage = next(monster for monster in arena.monsters if "Mage" in monster.name)
    mage.update_entity_senses(max_distance=20)
    original_model_copy = AoEShape.model_copy
    shape_copy_calls = 0
    target_update_copy_calls = 0

    def track_shape_copy(self: AoEShape, *args: Any, **kwargs: Any) -> AoEShape:
        nonlocal shape_copy_calls, target_update_copy_calls
        shape_copy_calls += 1
        update = kwargs.get("update")
        if isinstance(update, dict) and "target" in update:
            target_update_copy_calls += 1
        return original_model_copy(self, *args, **kwargs)

    monkeypatch.setattr(AoEShape, "model_copy", track_shape_copy)

    actions = mage.get_available_actions()
    aoe_target_count = sum(
        len(row.valid_targets)
        for row in actions.position_actions
        if row.target_type is TargetType.POSITION_AOE
    )
    affordable_aoe_variant_count = sum(
        1
        for variant in actions.registered_action_variants
        if variant.effective_target_type is TargetType.POSITION_AOE
        and variant.aoe_shape is not None
        and variant.check_costs()
    )

    assert aoe_target_count > affordable_aoe_variant_count
    assert 0 < shape_copy_calls < affordable_aoe_variant_count
    assert shape_copy_calls < aoe_target_count
    assert target_update_copy_calls == 0


def test_directional_aoe_discovery_compacts_duplicate_target_rays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line-style AoEs should expose semantic rays, not every cell on a ray."""
    arena = assemble_authored_encounter("standard_skeleton_doors")
    actor = arena.hero
    actor.update_entity_senses(max_distance=20)
    actions = actor.get_available_actions()
    move = next(row for row in actions.position_actions if row.template_name == "Move")
    target = next(candidate for candidate in move.valid_targets if candidate.position == (7, 12))
    execute_by_index(actor, "Move", target.index, available=actions)
    original_compute = Entity._compute_aoe_at_position
    call_counts: Counter[str] = Counter()

    def track_compute(
        self: Entity,
        shape: Any,
        shape_definition_key: tuple[Any, ...],
        pos: tuple[int, int],
        template: BaseAction,
        include_dead: bool,
        caster_visible_positions: Any,
        fov_cache: dict,
        barrier_positions: set[tuple[int, int]],
        idx: int,
    ) -> Any:
        call_counts[template.get_discovery_template_name()] += 1
        return original_compute(
            self,
            shape,
            shape_definition_key,
            pos,
            template,
            include_dead,
            caster_visible_positions,
            fov_cache,
            barrier_positions,
            idx,
        )

    monkeypatch.setattr(Entity, "_compute_aoe_at_position", track_compute)

    post_move_actions = actor.get_available_actions()
    lightning = next(
        row
        for row in post_move_actions.position_actions
        if row.template_name == "Lightning Bolt__slot_3"
    )

    assert len(lightning.valid_targets) == 3
    assert call_counts["Lightning Bolt__slot_3"] < 100
    assert all(target.affected_entity_uuids for target in lightning.valid_targets)


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
    """AoE preview optimization must preserve both subjective filters."""
    shape = Sphere(
        source_entity_uuid=uuid4(),
        target=(5, 5),
        radius_feet=10,
    )
    caster_fov = {(5, 5), (6, 5), (7, 5), (100, 100)}
    origin_fov = {(5, 5), (6, 5), (4, 5), (5, 6)}
    fov_cache = {((5, 5), 2): origin_fov}
    senses = SimpleNamespace(visible={}, entities={})

    shape.compute_subjective(
        caster_pos=(0, 0),
        senses=cast(Any, senses),
        fov_cache=fov_cache,
        barrier_positions={(5, 5)},
        caster_visible_positions=caster_fov,
    )

    expected = circle_positions((5, 5), radius=2).intersection(
        caster_fov,
        origin_fov,
    )
    assert shape.affected_positions == expected


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


def test_fireball_uses_resolved_save_roll_bonus_without_second_bonus_rebuild(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fireball should not rebuild the same save bonus after each target rolls."""
    arena = assemble_authored_encounter("caster_crossfire")
    mage = next(monster for monster in arena.monsters if "Mage" in monster.name)
    mage.update_entity_senses(max_distance=20)
    actions = mage.get_available_actions()
    fireball = next(
        row
        for row in actions.position_actions
        if row.template_name == "Fireball__slot_3"
    )
    target = max(fireball.valid_targets, key=lambda candidate: candidate.affected_count or 0)
    target_uuids = set(target.affected_entity_uuids or [])
    assert len(target_uuids) == 2

    original = Entity.saving_throw_bonus
    saving_throw_bonus_calls = 0

    def count_saving_throw_bonus(
        self: Entity,
        target_entity_uuid: UUID | None,
        ability_name: Any,
    ) -> Any:
        nonlocal saving_throw_bonus_calls
        if self.uuid in target_uuids and target_entity_uuid == mage.uuid and ability_name == "dexterity":
            saving_throw_bonus_calls += 1
        return original(self, target_entity_uuid, ability_name)

    monkeypatch.setattr(Entity, "saving_throw_bonus", count_saving_throw_bonus)

    event = execute_by_index(
        mage,
        fireball.template_name,
        target.index,
        available=actions,
    )

    assert event is not None
    assert not event.canceled
    # Exposed walls and objects are Fireball recipients too, so the event's
    # application count can exceed the two creature targets.
    assert event.total_targets >= len(target_uuids)
    assert saving_throw_bonus_calls == len(target_uuids)


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


def test_bright_visibility_skips_per_tile_effective_light(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fully bright FOVs should not resolve observer-specific light per tile."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero

    def reject_effective_light(*_args: Any, **_kwargs: Any) -> LightLevel:
        raise AssertionError("bright maps should use the objective light fast path")

    monkeypatch.setattr(Tile, "get_effective_light_for", reject_effective_light)

    actor.update_entity_visibility(max_distance=20)

    assert not no_cells(capture_senses_snapshot(actor.senses).visible)


def test_dark_visibility_still_uses_subjective_light_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dark FOVs must still apply observer-specific senses such as darkvision."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    for tile in get_map().get_all_tiles().values():
        tile.default_light = LightLevel.DARKNESS
    calls = 0
    original = Tile.get_effective_light_for

    def track_effective_light(self: Tile, *args: Any, **kwargs: Any) -> LightLevel:
        nonlocal calls
        calls += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Tile, "get_effective_light_for", track_effective_light)

    actor.update_entity_visibility(max_distance=20)

    assert calls > 0



def test_bright_light_refresh_skips_per_tile_effective_light(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incremental bright light updates should use objective light directly."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    actor.update_entity_senses(max_distance=20)
    grid = get_map()
    changed_positions = {
        position
        for position in grid.get_entity_subscriptions(actor.uuid)
        if (tile := grid.get_tile(*position)) is not None
        and tile.resolved_light_level.value >= LightLevel.BRIGHT_LIGHT.value
    }
    assert changed_positions
    changed_positions = set(sorted(changed_positions)[:3])
    callback = actor.senses.create_spatial_callback(actor.uuid)

    def reject_effective_light(*_args: Any, **_kwargs: Any) -> LightLevel:
        raise AssertionError("bright light refresh should not resolve subjective light")

    monkeypatch.setattr(Tile, "get_effective_light_for", reject_effective_light)

    callback._light_positions_requiring_visibility_refresh(changed_positions)
    callback._update_visibility_for_light_positions(changed_positions)

    assert changed_positions <= set(mask_positions(capture_senses_snapshot(actor.senses).visible))


def test_dark_light_refresh_still_uses_subjective_light_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incremental dark light updates must still respect observer senses."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    actor.update_entity_senses(max_distance=20)
    grid = get_map()
    position = next(
        position
        for position in sorted(grid.get_entity_subscriptions(actor.uuid))
        if grid.get_tile(*position) is not None
    )
    tile = grid.get_tile(*position)
    assert tile is not None
    tile.default_light = LightLevel.DARKNESS
    tile.add_obscurement(uuid4(), LightLevel.DARKNESS, fire_event=False)
    assert tile.resolved_light_level.value <= LightLevel.DARKNESS.value
    calls = 0
    original = Tile.get_effective_light_for

    def track_effective_light(self: Tile, *args: Any, **kwargs: Any) -> LightLevel:
        nonlocal calls
        calls += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Tile, "get_effective_light_for", track_effective_light)
    callback = actor.senses.create_spatial_callback(actor.uuid)

    callback._light_positions_requiring_visibility_refresh({position})
    callback._update_visibility_for_light_positions({position})

    assert calls >= 2


def test_dirty_action_discovery_limits_path_radius_to_movement_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dirty movement rows should not recompute full visibility-radius paths."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    actor.update_entity_senses(max_distance=20)
    actor.senses._paths_dirty = True
    grid = get_map()
    original_compute_paths = grid.compute_paths
    requested_distances: list[int | None] = []

    def track_compute_paths(*args: Any, **kwargs: Any) -> Any:
        max_distance = kwargs.get("max_distance")
        if max_distance is None and len(args) > 1:
            max_distance = args[1]
        requested_distances.append(max_distance)
        return original_compute_paths(*args, **kwargs)

    monkeypatch.setattr(grid, "compute_paths", track_compute_paths)

    actor.get_available_actions()

    assert actor.senses.path_max_distance == 6
    assert 6 in requested_distances
    assert 20 not in requested_distances


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
    original_dijkstra = gridmap_module.dijkstra
    original_bfs = gridmap_module.breadth_first_paths

    def track_dijkstra(*args: Any, **kwargs: Any) -> Any:
        nonlocal solver_calls
        solver_calls += 1
        return original_dijkstra(*args, **kwargs)

    def track_bfs(*args: Any, **kwargs: Any) -> Any:
        nonlocal solver_calls
        solver_calls += 1
        return original_bfs(*args, **kwargs)

    monkeypatch.setattr(gridmap_module, "dijkstra", track_dijkstra)
    monkeypatch.setattr(gridmap_module, "breadth_first_paths", track_bfs)

    first_distances, first_paths = grid.compute_paths(
        actor.position,
        max_distance=20,
        requesting_entity_uuid=actor.uuid,
        subjective=True,
    )
    second_distances, second_paths = grid.compute_paths(
        actor.position,
        max_distance=20,
        requesting_entity_uuid=actor.uuid,
        subjective=True,
    )

    assert solver_calls == 1
    assert second_distances == first_distances
    assert second_paths == first_paths
    sample_destination = next(iter(second_paths))
    second_paths[sample_destination].append((999, 999))
    _, third_paths = grid.compute_paths(
        actor.position,
        max_distance=20,
        requesting_entity_uuid=actor.uuid,
        subjective=True,
    )
    assert third_paths[sample_destination] == first_paths[sample_destination]


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
    original_bfs = gridmap_module.breadth_first_paths

    def reject_dijkstra(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal dijkstra_calls
        dijkstra_calls += 1
        raise AssertionError("unit-cost maps should not use Dijkstra")

    def track_bfs(*args: Any, **kwargs: Any) -> Any:
        nonlocal bfs_calls
        bfs_calls += 1
        return original_bfs(*args, **kwargs)

    monkeypatch.setattr(gridmap_module, "dijkstra", reject_dijkstra)
    monkeypatch.setattr(gridmap_module, "breadth_first_paths", track_bfs)

    distances, paths = grid.compute_paths(
        actor.position,
        max_distance=6,
        requesting_entity_uuid=actor.uuid,
        subjective=True,
    )

    assert dijkstra_calls == 0
    assert bfs_calls == 1
    assert distances[actor.position] == 0
    assert paths[actor.position] == [actor.position]


def test_weighted_paths_keep_dijkstra_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-unit movement costs must keep weighted Dijkstra semantics."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    grid = get_map()
    grid._path_cache.clear()
    difficult_position = next(
        position for position in grid.get_all_tiles()
        if position != actor.position
    )
    difficult_tile = grid.get_tile(*difficult_position)
    assert difficult_tile is not None
    difficult_tile.edit_movement_cost(MovementMode.WALKING).self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=difficult_tile.uuid,
            name="Performance Test Difficult Terrain",
            value=1,
        )
    )
    dijkstra_calls = 0
    bfs_calls = 0
    original_dijkstra = gridmap_module.dijkstra

    def track_dijkstra(*args: Any, **kwargs: Any) -> Any:
        nonlocal dijkstra_calls
        dijkstra_calls += 1
        return original_dijkstra(*args, **kwargs)

    def reject_bfs(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal bfs_calls
        bfs_calls += 1
        raise AssertionError("weighted maps must use Dijkstra")

    monkeypatch.setattr(gridmap_module, "dijkstra", track_dijkstra)
    monkeypatch.setattr(gridmap_module, "breadth_first_paths", reject_bfs)

    distances, _ = grid.compute_paths(
        actor.position,
        max_distance=6,
        requesting_entity_uuid=actor.uuid,
        movement_mode=MovementMode.WALKING,
        subjective=True,
    )

    assert dijkstra_calls == 1
    assert bfs_calls == 0
    if difficult_position in distances:
        assert distances[difficult_position] >= 2


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
    assert actor.senses.path_costs
    for target in move_info.valid_targets:
        assert target.position is not None
        assert target.path_cost == actor.senses.path_costs[target.position]


def test_weighted_move_discovery_uses_cached_senses_path_costs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cached path costs preserve weighted terrain in movement rows."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    grid = get_map()
    actor.update_entity_senses(max_distance=20)
    difficult_position = next(
        position for position, cost in actor.senses.path_costs.items()
        if position != actor.position
        and 0 < cost <= actor.action_economy.movement_remaining()
    )
    difficult_tile = grid.get_tile(*difficult_position)
    assert difficult_tile is not None
    difficult_tile.edit_movement_cost(MovementMode.WALKING).self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=difficult_tile.uuid,
            name="Cached Cost Difficult Terrain",
            value=1,
        )
    )
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

    assert actor.senses.path_costs[difficult_position] >= 10
    assert target.path_cost == actor.senses.path_costs[difficult_position]


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
    original_dijkstra = gridmap_module.dijkstra
    original_bfs = gridmap_module.breadth_first_paths

    def track_dijkstra(*args: Any, **kwargs: Any) -> Any:
        nonlocal solver_calls
        solver_calls += 1
        return original_dijkstra(*args, **kwargs)

    def track_bfs(*args: Any, **kwargs: Any) -> Any:
        nonlocal solver_calls
        solver_calls += 1
        return original_bfs(*args, **kwargs)

    monkeypatch.setattr(gridmap_module, "dijkstra", track_dijkstra)
    monkeypatch.setattr(gridmap_module, "breadth_first_paths", track_bfs)

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

    grid.move_entity(blocker.uuid, (blocker.position[0], blocker.position[1] + 1))
    grid.compute_paths(
        actor.position,
        max_distance=20,
        requesting_entity_uuid=actor.uuid,
        subjective=True,
    )

    assert solver_calls == 2


def test_dijkstra_hot_loop_does_not_allocate_neighbor_lists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pathfinder iterates bounded offsets without its allocating helper."""
    def reject_neighbor_list(*_args: Any, **_kwargs: Any) -> list[tuple[int, int]]:
        raise AssertionError("dijkstra allocated a per-node neighbor list")

    monkeypatch.setitem(dijkstra.__globals__, "get_neighbors", reject_neighbor_list)
    distances, paths = dijkstra(
        (0, 0),
        lambda x, y: (x, y) != (1, 1),
        width=4,
        height=3,
        diagonal=True,
        max_distance=4,
        cost_func=lambda x, y: 2 if (x, y) == (2, 0) else 1,
        can_enter=lambda source, target: (source, target) != ((1, 0), (2, 0)),
    )

    assert distances[(3, 0)] == 3
    assert paths[(3, 0)][0] == (0, 0)
    assert paths[(3, 0)][-1] == (3, 0)
    assert (1, 1) not in paths
