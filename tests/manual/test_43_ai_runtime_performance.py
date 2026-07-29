"""Regression contracts for latency-sensitive agent runtime infrastructure."""

import gc
from collections import Counter
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
import time
from types import SimpleNamespace
import weakref
from typing import Any, Sequence, cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ai.knowledge import derive_agent_facts
from ai.knowledge.models import TargetEffectBlockHypothesis
from ai.knowledge.topology import grid_distance_feet, known_line_of_sight
from ai.codex_tools.hot_runtime import HotCodexSession
from dnd.ai.runtime import subjective_projection
from server.agent_runtime import observation_journal
from dnd.ai.contracts.observation import AdjacentOffset, KnowledgeState, ObservationFrame, ObservationSnapshot
from ai.policy import PolicyHost
from ai.policy import candidates as policy_candidates
from ai.policy.economy import AffordabilityWorkspace
from ai.policy.generations.registry import (
    get_active_policy_implementation,
)
from ai.policy.memory import RoutineProgress, SemanticActionGoal
from ai.policy.routines import RoutinePlanningInstrumentation, plan_enable_then_act
from dnd.ai.contracts.control import (
    ActionAffordance,
    ActionOutcomeProfile,
    ActionResolutionStatus,
    AffordanceSet,
    CommandResult,
    CommandResultStatus,
)
from dnd.ai.contracts.semantics import (
    ActionSemantics,
    ActionTag,
    TruthValue,
    action_semantics_ref,
)
from server.agent_protocol.observation_legacy import (
    migrate_legacy_frame_semantics,
    migrate_legacy_snapshot_semantics,
)
from server.runtime_performance import MINIMUM_FULL_COLLECTION_INTERVAL, latency_sensitive_gc
from dnd.ai.runtime import decision_epoch as subjective_epochs
from dnd.ai.runtime.decision_epoch import _build_affordance_set_from_actions
from ai.subjective.store import SubjectiveStore
from ai.subjective.models import AgentState
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
    SensoryUpdateEvent,
    SensoryUpdateReason,
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
from dnd.core.modifiers import NumericalModifier
from dnd.blocks.sensory import spatial_senses_system
import dnd.core.gridmap as gridmap_module
from dnd.entity import Entity
from tests.manual.authored_encounter_support import (
    assemble_authored_encounter,
)
from dnd.spells.evocation import Fireball
from tests.manual.server_test_client import (
    ServerTestClient,
    reset_server_test_runtime,
)
from server.session import SessionManager
from tests.manual.test_28_subjective_observation_stream import create_observation_game


class _RequestLocalMarker:
    """Weak-referenceable marker used to detect retained request callers."""


def _upgrade_historical_semantic_contracts(payload: dict[str, Any]) -> dict[str, Any]:
    """Apply canonical legacy migrations and refresh their content addresses."""
    migrated = migrate_legacy_frame_semantics(payload)
    migrated = migrate_legacy_snapshot_semantics(migrated)
    assert isinstance(migrated, dict)

    def refresh_epoch(epoch: dict[str, Any]) -> dict[str, Any]:
        affordances = epoch.get("affordances")
        if not isinstance(affordances, dict):
            return epoch
        raw_catalog = affordances.get("semantic_catalog")
        if not isinstance(raw_catalog, dict):
            return epoch

        reference_updates: dict[str, str] = {}
        upgraded_catalog: dict[str, dict[str, Any]] = {}
        for old_reference, raw_semantics in raw_catalog.items():
            semantics = ActionSemantics.model_validate(raw_semantics)
            new_reference = action_semantics_ref(semantics)
            reference_updates[str(old_reference)] = new_reference
            upgraded_catalog[new_reference] = semantics.model_dump(mode="json")

        upgraded_affordances = {
            **affordances,
            "semantic_catalog": upgraded_catalog,
        }
        for collection_name in ("action_sources", "capabilities"):
            sources = affordances.get(collection_name)
            if not isinstance(sources, list):
                continue
            upgraded_affordances[collection_name] = [
                {
                    **source,
                    "semantics_ref": reference_updates.get(
                        str(source.get("semantics_ref")),
                        source.get("semantics_ref"),
                    ),
                }
                if isinstance(source, dict)
                else source
                for source in sources
            ]
        return {**epoch, "affordances": upgraded_affordances}

    def refresh_container(container: dict[str, Any]) -> dict[str, Any]:
        upgraded = dict(container)
        for epoch_name in ("decision_epoch", "current_epoch"):
            epoch = container.get(epoch_name)
            if isinstance(epoch, dict):
                upgraded[epoch_name] = refresh_epoch(epoch)
        replacement = container.get("state_replacement")
        if isinstance(replacement, dict):
            upgraded["state_replacement"] = refresh_container(replacement)
        return upgraded

    return refresh_container(cast(dict[str, Any], migrated))


def _load_v194_world_at_cursor_105() -> Any:
    """Replay the retained v194 subjective stream through its dense epoch."""
    artifact_path = (
        Path(__file__).resolve().parents[2]
        / "ai/evidence/direct_codex_runs"
        / "20260715-rotation-7-04-codex-monsters-vs-ai-sorcerer-darkness-reveal-v194.json"
    )
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    store = SubjectiveStore()
    store.load_snapshot(
        ObservationSnapshot.model_validate(
            _upgrade_historical_semantic_contracts(
                artifact["initial_subjective_snapshot"]
            )
        )
    )
    for raw_frame in artifact["observation_frames_response"]["frames"]:
        if raw_frame["observation_cursor"] > 105:
            break
        store.apply_frame(
            ObservationFrame.model_validate(
                _upgrade_historical_semantic_contracts(raw_frame)
            )
        )
    assert store.world is not None
    return store.world


def _load_v216_world_at_cursor_68() -> Any:
    """Replay the retained v216 stream through its dense spacing epoch."""
    artifact_path = (
        Path(__file__).resolve().parents[2]
        / "ai/evidence/direct_codex_runs"
        / "20260715-rotation-10-04-codex-monsters-vs-ai-sorcerer-high-level-duel-v216.json"
    )
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    store = SubjectiveStore()
    store.load_snapshot(
        ObservationSnapshot.model_validate(
            _upgrade_historical_semantic_contracts(
                artifact["initial_subjective_snapshot"]
            )
        )
    )
    for raw_frame in artifact["observation_frames_response"]["frames"]:
        if raw_frame["observation_cursor"] > 68:
            break
        store.apply_frame(
            ObservationFrame.model_validate(
                _upgrade_historical_semantic_contracts(raw_frame)
            )
        )
    assert store.world is not None
    return store.world


def _load_v219_world_at_cursor(cursor: int) -> Any:
    """Replay the retained v219 stream through one recorded decision cursor."""
    artifact_path = (
        Path(__file__).resolve().parents[2]
        / "ai/evidence/direct_codex_runs"
        / "20260715-rotation-11-01-codex-barbarian-vs-ai-buff-ambush-v219.json"
    )
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    store = SubjectiveStore()
    store.load_snapshot(
        ObservationSnapshot.model_validate(
            _upgrade_historical_semantic_contracts(
                artifact["initial_subjective_snapshot"]
            )
        )
    )
    for raw_frame in artifact["observation_frames_response"]["frames"]:
        if raw_frame["observation_cursor"] > cursor:
            break
        store.apply_frame(
            ObservationFrame.model_validate(
                _upgrade_historical_semantic_contracts(raw_frame)
            )
        )
    assert store.world is not None
    return store.world


def _load_hazard_bridge_world_at_cursor_104() -> Any:
    """Replay the retained post-pressure target-switch defect decision."""
    artifact_path = (
        Path(__file__).resolve().parents[2]
        / "ai/evidence/direct_codex_runs"
        / "20260715T184716_277980_0000-forced_movement_hazard_bridge-direct-codex-62cc7755.json"
    )
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    store = SubjectiveStore()
    store.load_snapshot(
        ObservationSnapshot.model_validate(
            _upgrade_historical_semantic_contracts(
                artifact["initial_subjective_snapshot"]
            )
        )
    )
    for raw_frame in artifact["observation_frames_response"]["frames"]:
        if raw_frame["observation_cursor"] > 104:
            break
        store.apply_frame(
            ObservationFrame.model_validate(
                _upgrade_historical_semantic_contracts(raw_frame)
            )
        )
    assert store.world is not None
    return store.world


def _load_double_door_world_at_cursor_60() -> Any:
    """Replay the retained same-turn frontier-reversal defect decision."""
    artifact_path = (
        Path(__file__).resolve().parents[2]
        / "ai/evidence/direct_codex_runs"
        / "20260715T192726_150909_0000-double_door_dark_hunt-direct-codex-173a1063.json"
    )
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    store = SubjectiveStore()
    store.load_snapshot(
        ObservationSnapshot.model_validate(
            _upgrade_historical_semantic_contracts(
                artifact["initial_subjective_snapshot"]
            )
        )
    )
    for raw_frame in artifact["observation_frames_response"]["frames"]:
        if raw_frame["observation_cursor"] > 60:
            break
        store.apply_frame(
            ObservationFrame.model_validate(
                _upgrade_historical_semantic_contracts(raw_frame)
            )
        )
    assert store.world is not None
    return store.world


def _load_double_door_monster_world_at_cursor_104() -> Any:
    """Replay the retained actor-local line-of-sight pursuit defect."""
    artifact_path = (
        Path(__file__).resolve().parents[2]
        / "ai/evidence/direct_codex_runs"
        / "20260715T194319_336197_0000-double_door_dark_hunt-direct-codex-f9bdb011.json"
    )
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    store = SubjectiveStore()
    store.load_snapshot(
        ObservationSnapshot.model_validate(
            _upgrade_historical_semantic_contracts(
                artifact["initial_subjective_snapshot"]
            )
        )
    )
    for raw_frame in artifact["observation_frames_response"]["frames"]:
        if raw_frame["observation_cursor"] > 104:
            break
        store.apply_frame(
            ObservationFrame.model_validate(
                _upgrade_historical_semantic_contracts(raw_frame)
            )
        )
    assert store.world is not None
    return store.world


def _load_reckless_bridge_world_at_cursor(cursor: int) -> Any:
    """Replay the retained move-then-Reckless ordering defect."""
    artifact_path = (
        Path(__file__).resolve().parents[2]
        / "ai/evidence/direct_codex_runs"
        / "20260715T200825_392460_0000-forced_movement_hazard_bridge-direct-codex-27d0f93c.json"
    )
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    store = SubjectiveStore()
    store.load_snapshot(
        ObservationSnapshot.model_validate(
            _upgrade_historical_semantic_contracts(
                artifact["initial_subjective_snapshot"]
            )
        )
    )
    for raw_frame in artifact["observation_frames_response"]["frames"]:
        if raw_frame["observation_cursor"] > cursor:
            break
        store.apply_frame(
            ObservationFrame.model_validate(
                _upgrade_historical_semantic_contracts(raw_frame)
            )
        )
    assert store.world is not None
    return store.world


def _canonical_model_hash(value: Any) -> str:
    """Hash one complete typed model without depending on display formatting."""
    def normalize(item: Any) -> Any:
        if isinstance(item, BaseModel):
            return normalize(item.model_dump(mode="python"))
        if isinstance(item, Enum):
            return item.value
        if isinstance(item, dict):
            return {str(key): normalize(child) for key, child in item.items()}
        if isinstance(item, frozenset):
            normalized = [normalize(child) for child in item]
            return sorted(
                normalized,
                key=lambda child: json.dumps(child, sort_keys=True, separators=(",", ":")),
            )
        if isinstance(item, (list, tuple)):
            return [normalize(child) for child in item]
        if isinstance(item, UUID):
            return str(item)
        return item

    payload = json.dumps(
        normalize(value),
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def test_latency_sensitive_gc_defers_full_scans_and_restores_process_defaults() -> None:
    """Runtime tuning is scoped and leaves young-generation collection enabled."""
    previous = gc.get_threshold()

    with latency_sensitive_gc():
        active = gc.get_threshold()
        assert active[:2] == previous[:2]
        assert active[2] >= MINIMUM_FULL_COLLECTION_INTERVAL

    assert gc.get_threshold() == previous


def _post_session_with_request_local() -> weakref.ReferenceType[_RequestLocalMarker]:
    """Issue one POST while retaining a marker only in the caller frame."""
    marker = _RequestLocalMarker()
    reference = weakref.ref(marker)
    response = ServerTestClient().post(
        "/session/create",
        json={"player_type": "ai", "name": "Request lifetime probe"},
    )
    response.raise_for_status()
    return reference


def test_post_request_does_not_retain_its_caller_until_cyclic_gc() -> None:
    """Completed POST requests release large policy caller frames immediately."""
    reset_server_test_runtime()
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        reference = _post_session_with_request_local()
        retained_without_collection = reference() is not None
    finally:
        if was_enabled:
            gc.enable()
        gc.collect()
        reset_server_test_runtime()

    assert retained_without_collection is False


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


def test_cross_entity_save_evaluation_does_not_clone_an_entire_entity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contextual modifier evaluation binds live context and restores it."""
    _client, _session_id, hero, monster, _encounter = create_observation_game()
    original_model_copy = Entity.model_copy
    deep_entity_copies = 0

    def track_model_copy(self: Entity, *args: Any, **kwargs: Any) -> Entity:
        nonlocal deep_entity_copies
        if kwargs.get("deep") is True:
            deep_entity_copies += 1
        return original_model_copy(self, *args, **kwargs)

    monkeypatch.setattr(Entity, "model_copy", track_model_copy)

    hero.saving_throw_bonus(monster.uuid, "wisdom")

    assert deep_entity_copies == 0
    assert hero.target_entity_uuid is None
    assert monster.target_entity_uuid is None


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

    grid._bump_spatial_revisions({"propagation"})

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


def test_aoe_propagation_footprints_survive_visibility_only_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Light/fog changes should not rebuild propagation footprints."""
    arena = assemble_authored_encounter("caster_crossfire")
    mage = next(monster for monster in arena.monsters if "Mage" in monster.name)
    mage.update_entity_senses(max_distance=20)
    original_compute = Entity._compute_aoe_propagation_footprint
    propagation_footprint_calls = 0

    def track_compute(
        self: Entity,
        shape: Any,
        fov_cache: dict,
        barrier_positions: set[tuple[int, int]],
    ) -> set[tuple[int, int]]:
        nonlocal propagation_footprint_calls
        propagation_footprint_calls += 1
        return original_compute(self, shape, fov_cache, barrier_positions)

    monkeypatch.setattr(
        Entity,
        "_compute_aoe_propagation_footprint",
        track_compute,
    )

    first_actions = mage.get_available_actions()
    first_aoe_target_count = sum(
        len(row.valid_targets)
        for row in first_actions.position_actions
        if row.target_type is TargetType.POSITION_AOE
    )
    first_call_count = propagation_footprint_calls
    assert first_aoe_target_count > 10
    assert first_call_count > 0
    assert mage._aoe_footprint_cache
    cached_target_positions = {
        target.position
        for row in first_actions.position_actions
        if row.target_type is TargetType.POSITION_AOE
        for target in row.valid_targets
        if target.position is not None
    }
    removable_visible_position = next(
        position
        for position in mage.senses.visible
        if position not in cached_target_positions
    )

    mage.senses.visible.pop(removable_visible_position)
    mage._aoe_preview_cache_context = None
    mage._aoe_preview_cache.clear()
    propagation_footprint_calls = 0

    second_actions = mage.get_available_actions()
    second_aoe_target_count = sum(
        len(row.valid_targets)
        for row in second_actions.position_actions
        if row.target_type is TargetType.POSITION_AOE
    )

    assert propagation_footprint_calls == 0
    assert second_aoe_target_count == first_aoe_target_count


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


def test_required_target_aoe_prefilter_uses_action_relationship_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enemy-only AoEs should not generate candidate centers from allies."""
    arena = assemble_authored_encounter("caster_crossfire")
    mage = next(monster for monster in arena.monsters if "Mage" in monster.name)
    mage.update_entity_senses(max_distance=20)
    ally_positions = {
        monster.position
        for monster in arena.monsters
        if monster.uuid != mage.uuid
    }
    assert arena.hero.uuid in mage.senses.entities
    assert ally_positions & set(mage.senses.entities.values())
    probe = Fireball(
        name="Enemy Filter Probe",
        source_entity_uuid=mage.uuid,
        target_type=TargetType.POSITION_AOE,
        template=True,
        aoe_shape=Sphere(
            source_entity_uuid=mage.uuid,
            target=mage.position,
            radius_feet=20,
        ),
        valid_target_filter="enemies",
        include_self=False,
        aoe_require_targets=True,
    )
    mage.register_action(probe)

    original_compute = Entity._compute_aoe_at_position
    probe_candidate_positions: list[tuple[int, int]] = []

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
        if template.get_discovery_template_name().startswith(
            "Enemy Filter Probe",
        ):
            probe_candidate_positions.append(pos)
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

    actions = mage.get_available_actions()
    probe_row = next(
        row
        for row in actions.position_actions
        if row.base_template_name == "Enemy Filter Probe"
    )
    probe_variant = next(
        variant
        for variant in actions.registered_action_variants
        if variant.get_discovery_template_name().startswith(
            "Enemy Filter Probe",
        )
    )
    assert probe_variant.aoe_shape is not None
    radius = probe_variant.aoe_shape._get_max_radius_tiles()
    enemy_candidate_region = set(
        get_map().get_positions_near_entities({arena.hero.position}, radius)
    )

    assert probe_variant.valid_target_filter == "enemies"
    assert mage._aoe_required_target_prefilter_positions(
        probe_variant,
        include_dead=False,
    ) == {arena.hero.position}
    assert probe_candidate_positions
    assert set(probe_candidate_positions) <= enemy_candidate_region
    assert probe_row.valid_targets


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


def test_adjacent_domain_projection_reuses_static_topology_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Visible tile projection should not repeatedly query fixed neighbors."""
    get_map().create_rectangle(0, 0, 4, 4)
    observation_journal.clear_observation_projection_cache()
    grid = get_map()
    original_get_tile = grid.get_tile
    calls = 0

    def count_get_tile(x: int, y: int) -> Any:
        nonlocal calls
        calls += 1
        return original_get_tile(x, y)

    monkeypatch.setattr(grid, "get_tile", count_get_tile)

    first = subjective_projection.adjacent_domain_knowledge((1, 1))
    second = subjective_projection.adjacent_domain_knowledge((1, 1))
    cold_calls = calls
    movement_revision = grid.movement_revision
    grid.set_tile(3, 3)
    third = subjective_projection.adjacent_domain_knowledge((1, 1))
    calls_after_equivalent_replacement = calls
    grid.set_tile(3, 3, walkable=False)
    calls_before_changed_lookup = calls
    fourth = subjective_projection.adjacent_domain_knowledge((1, 1))
    changed_lookup_calls = calls - calls_before_changed_lookup

    assert first == second == third == fourth
    assert cold_calls == len(AdjacentOffset)
    assert grid.movement_revision == movement_revision + 1
    assert calls_after_equivalent_replacement == cold_calls
    assert changed_lookup_calls <= len(AdjacentOffset)


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
    assert getattr(event, "total_targets", 0) == len(target_uuids)
    assert saving_throw_bonus_calls == len(target_uuids)


def test_epoch_normalizes_one_outcome_profile_per_source_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Target flattening reuses one normalized stochastic profile per row."""
    arena = assemble_authored_encounter("caster_crossfire")
    mage = next(monster for monster in arena.monsters if "Mage" in monster.name)
    mage.update_entity_senses(max_distance=20)
    actions = mage.get_available_actions()
    subjective_epochs.clear_epoch_value_caches()
    source_profile_count = sum(
        row.outcome_profile is not None
        for row in actions.all_actions
    )
    flattened_profile_count = sum(
        max(1, len(row.valid_targets))
        for row in actions.all_actions
        if row.outcome_profile is not None
    )
    original_model_validate = ActionOutcomeProfile.model_validate
    original_describe = subjective_epochs._describe_action_row
    validation_calls = 0
    described_profiles = 0

    def track_model_validate(
        _cls: type[ActionOutcomeProfile],
        value: object,
        *args: Any,
        **kwargs: Any,
    ) -> ActionOutcomeProfile:
        nonlocal validation_calls
        validation_calls += 1
        return original_model_validate(value, *args, **kwargs)

    monkeypatch.setattr(
        ActionOutcomeProfile,
        "model_validate",
        classmethod(track_model_validate),
    )

    def track_describe(*args: Any, **kwargs: Any):
        nonlocal described_profiles
        descriptor = original_describe(*args, **kwargs)
        if descriptor.outcome_profile is not None:
            described_profiles += 1
        return descriptor

    monkeypatch.setattr(subjective_epochs, "_describe_action_row", track_describe)

    _build_affordance_set_from_actions(mage, actions, 42)

    assert flattened_profile_count > source_profile_count
    assert described_profiles >= source_profile_count
    assert validation_calls == described_profiles


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
    actor.action_economy.consume("movement", actor.action_economy.movement.normalized_score)
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


def test_no_hazard_map_skips_per_path_hazard_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No-hazard maps should not scan every movement path for hazards."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    actor.update_entity_senses(max_distance=20)
    grid = get_map()
    assert grid.has_any_hazards() is False

    def reject_hazard_scan(*_args: Any, **_kwargs: Any) -> bool:
        raise AssertionError("per-position hazard check should be skipped")

    monkeypatch.setattr(grid, "is_position_hazardous_for", reject_hazard_scan)

    actions = actor.get_available_actions()

    assert actions.position_actions


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

    assert actor.senses.visible


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


def test_light_batch_candidate_selection_uses_bulk_subscriber_union(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Light batches should not copy subscribers once per changed cell."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    actor.update_entity_senses(max_distance=20)
    grid = get_map()
    subscribed_positions = sorted(
        position
        for position in grid.get_entity_subscriptions(actor.uuid)
        if grid.get_tile(*position) is not None
    )
    changed_positions = set(subscribed_positions[:3])
    assert changed_positions
    representative_position = min(changed_positions)
    representative_tile = grid.get_tile(*representative_position)
    assert representative_tile is not None
    event = SpatialChangeEvent.light_changed(
        representative_position,
        representative_tile.uuid,
        senses_hint=SensesUpdateHint(light_changed_positions=changed_positions),
    )

    def reject_per_cell_lookup(_position: tuple[int, int]) -> set[UUID]:
        raise AssertionError("light batches should use the bulk subscriber lookup")

    monkeypatch.setattr(grid, "get_subscribers_at", reject_per_cell_lookup)

    candidates = spatial_senses_system.candidate_observer_uuids(event)

    assert actor.uuid in candidates


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

    assert changed_positions <= set(actor.senses.visible)


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
    assert actor.action_economy.movement.normalized_score == 0
    assert actor.senses.path_max_distance == 0
    assert actor.senses._paths_dirty is False
    assert actor.senses.visible
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
    difficult_tile.walking_cost.self_static.add_value_modifier(
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

    monkeypatch.setattr(Entity, "_movement_path_cost_feet", reject_path_rescan)

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
        and 0 < cost <= actor.action_economy.movement.normalized_score
    )
    difficult_tile = grid.get_tile(*difficult_position)
    assert difficult_tile is not None
    difficult_tile.walking_cost.self_static.add_value_modifier(
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

    monkeypatch.setattr(Entity, "_movement_path_cost_feet", reject_path_rescan)

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


def test_normal_subjective_projection_does_not_run_deep_timing_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Projection timing clocks run only when a diagnostic recorder is supplied."""
    client, session_id, _hero, _monster, encounter = create_observation_game()
    client.get(f"/ai/sessions/{session_id}/observation/snapshot").raise_for_status()
    manager = SessionManager.get()
    session = manager.get_session(UUID(session_id))
    game = manager.get_active_game()
    clock_calls = 0

    def count_clock() -> float:
        nonlocal clock_calls
        clock_calls += 1
        return 1.0

    monkeypatch.setattr(observation_journal.time, "perf_counter", count_clock)
    assert session is not None
    observation_journal._update_projection_cache(session, game, encounter)
    assert clock_calls == 0

    observation_journal._update_projection_cache(
        session,
        game,
        encounter,
        record_timing=lambda _phase, _started: None,
    )
    assert clock_calls > 0


def test_projection_cache_current_cursor_skips_context_rebuild(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A hot current projection should not rebuild observers or pass contexts."""
    client, session_id, _hero, _monster, encounter = create_observation_game()
    client.get(f"/ai/sessions/{session_id}/observation/snapshot").raise_for_status()
    manager = SessionManager.get()
    session = manager.get_session(UUID(session_id))
    game = manager.get_active_game()
    assert session is not None

    def fail_controlled_observers(_session: Any) -> list[Any]:
        raise AssertionError("current projection cursor rebuilt observer context")

    monkeypatch.setattr(
        observation_journal,
        "resolve_controlled_observers",
        fail_controlled_observers,
    )

    entry = observation_journal._update_projection_cache(session, game, encounter)

    assert entry.source_event_cursor == EventQueue.event_cursor()


def test_sensory_projection_skips_combat_log_filtering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sensory frames should not pay combat-log filtering they cannot use."""
    client, session_id, hero, _monster, _encounter = create_observation_game()
    snapshot = client.get(f"/ai/sessions/{session_id}/observation/snapshot").json()

    def fail_filtered_combat_log(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("sensory projection filtered combat logs")

    monkeypatch.setattr(
        observation_journal,
        "_filtered_combat_log",
        fail_filtered_combat_log,
    )

    sensory = SensoryUpdateEvent(
        source_entity_uuid=hero.uuid,
        target_entity_uuid=hero.uuid,
        observer_uuid=hero.uuid,
        cause_event_uuid=uuid4(),
        update_reason=SensoryUpdateReason.SPATIAL,
        visible_cells_added=[(5, 5)],
        phase=EventPhase.DECLARATION,
        use_register=False,
    )
    current = EventQueue.register(sensory)
    current = EventQueue.register(current.phase_to(EventPhase.EXECUTION))
    current = EventQueue.register(current.phase_to(EventPhase.EFFECT))
    EventQueue.register(current.phase_to(EventPhase.COMPLETION))

    response = client.get(
        f"/ai/sessions/{session_id}/observation/frames",
        params={"since": snapshot["observation_cursor"], "limit": 0},
    ).json()

    assert response["frames"][-1]["source_kind"] == "sensory_event"


def test_v191_dense_sorcerer_local_decision_stays_bounded_under_five_ms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The retained 432-row spell epoch has bounded work and CPU latency."""
    artifact_path = (
        Path(__file__).resolve().parents[2]
        / "ai/evidence/direct_codex_runs"
        / "20260715-rotation-7-02-codex-sorcerer-vs-ai-missile-allocation-v191.json"
    )
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    snapshot = ObservationSnapshot.model_validate(
        _upgrade_historical_semantic_contracts(
            artifact["initial_subjective_snapshot"]
        )
    )
    world = SubjectiveStore().load_snapshot(snapshot)
    epoch = world.current_epoch
    assert epoch is not None
    assert len(epoch.affordances.all_rows) == 432

    feature_evaluations = 0
    original_features = policy_candidates._direct_damage_features

    def count_features(*args: Any, **kwargs: Any):
        nonlocal feature_evaluations
        feature_evaluations += 1
        return original_features(*args, **kwargs)

    monkeypatch.setattr(
        policy_candidates,
        "_direct_damage_features",
        count_features,
    )
    facts = derive_agent_facts(world).facts
    decision = PolicyHost().decide(world, facts=facts)

    assert feature_evaluations <= 16
    source_action_count = len({
        row.source_action_id
        for row in facts.affordances.rows
    })
    assert len(decision.candidates) <= source_action_count
    assert decision.selected.goal.value == "direct_pressure"
    assert decision.selected.source_node == "Pressure/DirectDamage"
    assert ActionTag.DAMAGE_AREA in decision.selected.semantic_tags
    target_plan = decision.selected.evidence.target_plan
    assert target_plan is not None
    assert len(target_plan.hostile_entity_uuids) >= 3
    assert not target_plan.controlled_entity_uuids
    assert not target_plan.allied_entity_uuids
    assert len(decision.selected.evidence.damage_outcomes) == len(
        target_plan.hostile_entity_uuids
    )

    PolicyHost().decide(world, facts=derive_agent_facts(world).facts)
    samples_ms: list[float] = []
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(11):
            sample_host = PolicyHost()
            started = time.thread_time_ns()
            sample_facts = derive_agent_facts(world).facts
            sample_host.decide(world, facts=sample_facts)
            samples_ms.append((time.thread_time_ns() - started) / 1_000_000)
    finally:
        if gc_was_enabled:
            gc.enable()

    assert median(samples_ms) < 5.0


def test_v194_dense_epoch_bounds_explicit_planning_and_preempts_dominated_work() -> None:
    """Explicit planning stays bounded while dominant setup skips it in policy."""
    world = _load_v194_world_at_cursor_105()
    epoch = world.current_epoch
    assert epoch is not None
    assert world.observation_cursor == 105
    assert len(epoch.affordances.all_rows) == 1357
    assert len(epoch.affordances.position_actions) == 1343
    assert len(epoch.affordances.capabilities) == 50

    facts = derive_agent_facts(world).facts
    host = PolicyHost()
    context = host.build_context(world, facts=facts)
    planning_instrumentation = RoutinePlanningInstrumentation(
        AffordabilityWorkspace(epoch.economy)
    )
    enable_plan = plan_enable_then_act(
        context,
        None,
        instrumentation=planning_instrumentation,
    )
    explicit_planning = planning_instrumentation.snapshot()
    decision = host.decide(world, facts=facts)
    diagnostics = host.diagnostics_for(
        world.session.session_id,
        epoch.actor_uuid,
        epoch.epoch_id,
    )

    assert decision.selected.goal.value == "self_setup"
    assert decision.selected.source_node == "Preparation/DurableSelfSetup"
    assert decision.selected.reason == "establish_durable_combat_setup"
    assert decision.selected.evidence.self_setup is not None
    assert enable_plan.status.value == "proposed"
    assert enable_plan.step_id == "enable"
    assert enable_plan.proposal is not None
    assert enable_plan.proposal.source_node == "Pressure/EnableThenAct/Enable"
    assert ActionTag.MOVEMENT_VOLUNTARY in enable_plan.proposal.semantic_tags
    assert 0 < explicit_planning.movement_endpoints <= len(
        epoch.affordances.position_actions
    )
    assert 0 < explicit_planning.damage_capabilities <= len(
        epoch.affordances.capabilities
    )
    assert (
        explicit_planning.affordability_pair_evaluations
        > explicit_planning.affordability_pair_cache_misses
    )
    assert (
        explicit_planning.affordability_pair_cache_misses
        <= explicit_planning.damage_capabilities
    )
    assert explicit_planning.replay_token_builds <= len(
        epoch.affordances.capabilities
    )
    assert explicit_planning.line_of_sight_evaluations > 0
    assert explicit_planning.line_of_sight_cache_hits > 0

    assert diagnostics.wall_total_ms >= 0
    assert diagnostics.thread_cpu_total_ms >= 0
    for stage in (
        diagnostics.stages.context,
        diagnostics.stages.candidates,
        diagnostics.stages.routine_revalidation,
        diagnostics.stages.routine_planning,
        diagnostics.stages.tree,
        diagnostics.stages.binding_and_telemetry,
    ):
        assert stage.wall_ms >= 0
        assert stage.thread_cpu_ms >= 0
    routine = diagnostics.routine
    assert all(value == 0 for value in routine.model_dump().values())

    hypothesis = TargetEffectBlockHypothesis(
        target_uuid="observed-target",
        effect_id="observed-effect",
        blocked_episodes=2,
        total_episodes=3,
        blocked_applications=2,
        total_applications=3,
        episode_log_indices=(4, 7),
        latest_log_index=7,
        block_probability=0.75,
    )
    hot_facts = facts.model_copy(update={
        "combat_memory": facts.combat_memory.model_copy(update={
            "hypotheses": (hypothesis,),
        }),
    })

    class RuntimeWithDerivedFacts:
        def __init__(self) -> None:
            self.store = SimpleNamespace(
                world=world,
                agent_state=AgentState(facts=hot_facts),
            )

        def bootstrap(self) -> None:
            pass

        def emit_policy_decision(self, _event: Any) -> None:
            pass

        def close(self) -> None:
            pass

    hot_session = HotCodexSession(
        runtime=RuntimeWithDerivedFacts(),  # type: ignore[arg-type]
        claim_id="performance-evidence",
        faction="monsters",
        controlled_entity_uuids=world.session.controlled_entity_uuids,
    )
    try:
        hot_index = hot_session.bootstrap()
        assert hot_index.combat_memory_hypotheses == (hypothesis,)
        assert hot_index.local_timing.policy_diagnostics is not None
        hot_routine = hot_index.local_timing.policy_diagnostics.routine
        assert all(value == 0 for value in hot_routine.model_dump().values())
    finally:
        hot_session.release()

    PolicyHost().decide(world, facts=derive_agent_facts(world).facts)
    samples_ms: list[float] = []
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(11):
            sample_facts = derive_agent_facts(world).facts
            sample_host = PolicyHost()
            started = time.thread_time_ns()
            sample_host.decide(world, facts=sample_facts)
            samples_ms.append((time.thread_time_ns() - started) / 1_000_000)
    finally:
        if gc_was_enabled:
            gc.enable()

    assert median(samples_ms) < 3.5


def test_v216_dense_spacing_epoch_preserves_exhaustive_choice_under_five_ms() -> None:
    """Dense endpoint geometry stays exhaustive, deterministic, and bounded."""
    world = _load_v216_world_at_cursor_68()
    epoch = world.current_epoch
    assert epoch is not None
    assert world.observation_cursor == 68
    assert len(epoch.affordances.all_rows) == 253
    assert len(epoch.affordances.position_actions) == 247
    assert len(epoch.affordances.capabilities) == 48

    facts = derive_agent_facts(world).facts
    decision = PolicyHost().decide(world, facts=facts)

    assert _canonical_model_hash(decision) == (
        "952f8a3cd07d212b0c46a797093cac95e0cd39f9d4e0c9bbe4f5704fd277f78e"
    )
    assert decision.selected.source_node == "PositionAndSurvival/CapabilityEnvelope"
    assert decision.selected.reason == "enter_future_tactical_envelope"
    assert getattr(decision.selected.intent, "row_id", None) == "position|Move|pos=13,10"
    selected_components = {
        component.name: component.raw_value
        for component in decision.selected.utility_components
    }
    assert selected_components["movement_rows_evaluated"] == 224
    assert selected_components["applicable_movement_rows"] == 200
    assert selected_components["represented_movement_rows"] == 149
    assert selected_components["capability_envelopes_evaluated"] == 12
    assert selected_components["capability_envelopes_retained"] == 4
    assert selected_components["capability_envelopes_selected"] == 1
    assert selected_components["capability_projection_modeled"] == 11
    assert selected_components["capability_projection_unmodeled"] == 1
    assert selected_components["capability_projection_insufficient_facts"] == 0
    assert selected_components["capability_projection_guaranteed_zero"] == 0

    PolicyHost().decide(world, facts=facts)
    samples_ms: list[float] = []
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(101):
            sample_host = PolicyHost()
            started = time.thread_time_ns()
            sample_host.decide(world, facts=facts)
            samples_ms.append((time.thread_time_ns() - started) / 1_000_000)
    finally:
        if gc_was_enabled:
            gc.enable()

    samples_ms.sort()
    assert median(samples_ms) < 5.0
    assert samples_ms[99] < 5.0


def test_v222_high_cardinality_spell_epoch_keeps_median_under_five_ms() -> None:
    """Typed tactical grouping keeps the median under five and tail under six."""
    artifact_path = (
        Path(__file__).resolve().parents[2]
        / "ai/evidence/direct_codex_runs"
        / "20260715-rotation-12-02-codex-sorcerer-vs-ai-high-level-duel-v222.json"
    )
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    snapshot = ObservationSnapshot.model_validate(
        _upgrade_historical_semantic_contracts(
            artifact["initial_subjective_snapshot"]
        )
    )
    world = SubjectiveStore().load_snapshot(snapshot)
    facts = derive_agent_facts(world).facts

    assert len(facts.affordances.rows) == 1763
    assert len({row.source_action_id for row in facts.affordances.rows}) == 65
    assert len(facts.affordances.affected_set_groups) == 161

    decision = PolicyHost().decide(world, facts=facts)

    source_action_count = len({
        row.source_action_id
        for row in facts.affordances.rows
    })
    assert len(decision.candidates) <= source_action_count
    assert decision.selected.goal.value == "direct_pressure"
    assert decision.selected.source_node == "Pressure/DirectDamage"
    assert decision.selected.reason == "cast_visible_area_spell"
    assert ActionTag.DAMAGE_AREA in decision.selected.semantic_tags
    target_plan = decision.selected.evidence.target_plan
    assert target_plan is not None
    assert len(target_plan.hostile_entity_uuids) >= 3
    assert not target_plan.controlled_entity_uuids
    assert not target_plan.allied_entity_uuids
    assert len(decision.selected.evidence.damage_outcomes) == len(
        target_plan.hostile_entity_uuids
    )

    samples_ms: list[float] = []
    gc_was_enabled = gc.isenabled()
    gc.collect()
    gc.disable()
    try:
        for _ in range(101):
            sample_host = PolicyHost()
            started = time.thread_time_ns()
            sample_host.decide(world, facts=facts)
            samples_ms.append((time.thread_time_ns() - started) / 1_000_000)
    finally:
        if gc_was_enabled:
            gc.enable()

    samples_ms.sort()
    assert median(samples_ms) < 5.0
    assert samples_ms[99] < 6.0


def test_v219_known_map_boundary_never_becomes_subjective_frontier() -> None:
    """The retained ambush state investigates memory instead of off-map cells."""
    world = _load_v219_world_at_cursor(93)
    facts = derive_agent_facts(world).facts

    decision = PolicyHost().decide(world, facts=facts)

    assert decision.selected.source_node == "InformationGathering/Explore"
    assert decision.selected.reason == "investigate_remembered_contact"
    assert getattr(decision.selected.intent, "row_id", None) not in {
        "position|Move|pos=14,0",
        "position|Move|pos=14,14",
    }
    evidence = decision.selected.evidence.exploration
    assert evidence is not None
    assert evidence.unknown_frontier_count == 0
    assert evidence.remembered_target_uuid is not None
    assert evidence.current_remembered_distance is not None
    assert evidence.selected_remembered_distance is not None
    assert evidence.selected_remembered_distance < evidence.current_remembered_distance


def test_v219_visible_distant_hostile_starts_bounded_capability_pursuit() -> None:
    """The retained low-health turn approaches the Mage instead of ending."""
    world = _load_v219_world_at_cursor(160)
    facts = derive_agent_facts(world).facts
    epoch = world.current_epoch
    assert epoch is not None
    host = PolicyHost(
        implementation=get_active_policy_implementation()
    )

    decision = host.decide(world, facts=facts)

    assert decision.selected.goal.value == "routine"
    assert decision.selected.source_node == "Pressure/PursueCapability/Approach"
    assert decision.selected.reason == (
        "ordinary movement reduces the known capability route deficit"
    )
    row_id = getattr(decision.selected.intent, "row_id", None)
    assert row_id is not None
    row = facts.affordances.by_id[row_id]
    semantics = facts.affordances.semantics_by_row_id[row_id]
    assert ActionTag.MOVEMENT_VOLUNTARY in semantics.tags
    assert row.targets
    destination = row.targets[0].position
    actor_position = facts.actor.position
    hostile_uuid = facts.contacts.visible_hostile_uuids[0]
    hostile_position = world.known_entities[hostile_uuid].position
    assert destination is not None
    assert actor_position is not None
    assert hostile_position is not None
    assert grid_distance_feet(destination, hostile_position) < grid_distance_feet(
        actor_position,
        hostile_position,
    )

    diagnostics = host.diagnostics_for(
        world.session.session_id,
        epoch.actor_uuid,
        epoch.epoch_id,
    )
    assert diagnostics.routine.movement_endpoints <= len(
        epoch.affordances.position_actions
    )
    assert diagnostics.routine.damage_capabilities <= len(
        epoch.affordances.capabilities
    )
    assert diagnostics.stages.routine_planning.thread_cpu_ms < 5.0


def test_hazard_bridge_spent_barbarian_holds_adjacent_wounded_threat() -> None:
    """The retained cursor-104 decision must not chase a distant healthy target."""
    world = _load_hazard_bridge_world_at_cursor_104()
    facts = derive_agent_facts(world).facts

    decision = PolicyHost().decide(world, facts=facts)

    assert decision.selected.intent.kind == "end_turn"
    assert decision.selected.source_node == (
        "PositionAndSurvival/CapabilityEnvelope"
    )
    spacing = decision.selected.evidence.spacing
    assert spacing is not None
    assert spacing.reference_entity_uuid == "cc11c3c9-cafc-4a79-a472-4cd757a873ec"
    assert spacing.reference_position == (8, 5)
    assert spacing.current_distance_cells == 1
    assert spacing.capability_target_projection is not None
    assert spacing.capability_target_projection.range_state.value == "in_range"


def test_double_door_exploration_does_not_reverse_into_same_turn_path() -> None:
    """The retained cursor-60 decision continues into novel subjective frontier."""
    world = _load_double_door_world_at_cursor_60()
    facts = derive_agent_facts(world).facts

    decision = PolicyHost().decide(world, facts=facts)

    assert getattr(decision.selected.intent, "row_id", None) == (
        "position|Move|pos=8,6"
    )
    exploration = decision.selected.evidence.exploration
    assert exploration is not None
    assert exploration.anchor_position == (8, 6)
    assert exploration.revisited_this_turn is False


def test_pursuit_searches_actor_local_line_of_sight_inside_range() -> None:
    """An in-range blocked actor moves to a fresh LOS envelope instead of yielding."""
    world = _load_double_door_monster_world_at_cursor_104()
    facts = derive_agent_facts(world).facts
    epoch = world.current_epoch
    assert epoch is not None
    host = PolicyHost(
        implementation=get_active_policy_implementation()
    )
    memory = host.memory_for(world.session.session_id, epoch.actor_uuid)
    memory.active_routine = RoutineProgress(
        routine_id="routine.pursue_capability",
        step_id="approach",
        started_epoch_index=1,
        target_uuid="0c12c570-05a4-4039-9121-6a923735b60f",
        target_position=(8, 6),
        goal=SemanticActionGoal(
            required_tags=frozenset({ActionTag.DAMAGE_SINGLE_TARGET}),
            target_uuid="0c12c570-05a4-4039-9121-6a923735b60f",
        ),
        enablers_used=1,
        started_round_number=1,
        started_turn_index=2,
        last_target_distance_feet=5,
    )

    decision = host.decide(world, facts=facts)

    assert decision.selected.source_node == "Pressure/PursueCapability/Approach"
    assert decision.selected.reason == (
        "ordinary movement reduces the known capability route deficit"
    )
    row_id = getattr(decision.selected.intent, "row_id", None)
    assert row_id is not None
    row = facts.affordances.by_id[row_id]
    semantics = facts.affordances.semantics_by_row_id[row_id]
    assert ActionTag.MOVEMENT_VOLUNTARY in semantics.tags
    assert row.targets
    destination = row.targets[0].position
    actor_position = facts.actor.position
    assert destination is not None
    assert actor_position is not None
    assert known_line_of_sight(
        world,
        actor_position,
        (8, 6),
        vision_blocker_positions=facts.topology.vision_blocker_positions,
    ) is TruthValue.FALSE
    assert known_line_of_sight(
        world,
        destination,
        (8, 6),
        vision_blocker_positions=facts.topology.vision_blocker_positions,
    ) is not TruthValue.FALSE

    diagnostics = host.diagnostics_for(
        world.session.session_id,
        epoch.actor_uuid,
        epoch.epoch_id,
    )
    assert diagnostics.routine.line_of_sight_evaluations > 0
    assert diagnostics.routine.line_of_sight_cache_hits > 0


def test_reckless_augmentation_interposes_before_retained_move_attack_goal() -> None:
    """A completed approach may be augmented before its retained attack executes."""
    approach_world = _load_reckless_bridge_world_at_cursor(6)
    approach_epoch = approach_world.current_epoch
    assert approach_epoch is not None
    host = PolicyHost()

    approach = host.decide(approach_world)

    assert getattr(approach.selected.intent, "row_id", None) == (
        "position|Move|pos=5,10"
    )
    host.prepare_submission(
        session_id=approach_world.session.session_id,
        actor_uuid=approach_epoch.actor_uuid,
        epoch_id=approach_epoch.epoch_id,
        command_id="retained-approach",
    )
    host.record_result(CommandResult(
        status=CommandResultStatus.ACCEPTED,
        command_id="retained-approach",
        session_id=approach_world.session.session_id,
        actor_uuid=approach_epoch.actor_uuid,
        requested_epoch_id=approach_epoch.epoch_id,
        current_epoch_id=None,
        row_id="position|Move|pos=5,10",
        action_resolution=ActionResolutionStatus.COMPLETED,
    ))

    attack_world = _load_reckless_bridge_world_at_cursor(12)
    decision = host.decide(attack_world)

    assert getattr(decision.selected.intent, "row_id", None) == (
        "self|Reckless Attack|index=0"
    )
    assert decision.selected.source_node == "Pressure/AugmentThenAct/Augment"


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
