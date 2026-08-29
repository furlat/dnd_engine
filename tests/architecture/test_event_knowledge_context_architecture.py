"""Architecture gates for the event knowledge-context boundary."""

import ast
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

from dnd.blocks.sensory import PartyKnowledge
from dnd.core.events.events_registry import Event, EventPhase, EventQueue
from dnd.core.events.knowledge import (
    CapturedEvent,
    EventArchive,
    EventKnowledge,
    KnowledgeDiagnostic,
)
from dnd.core.events.world_events import SensoryUpdateEvent, StepMovementEvent
from dnd.event_reduction import (
    BASE_EVENT_INTENTIONALLY_SILENT_REASON,
    _CONCRETE_EVENT_MANIFEST,
    EventReducer,
    party_event_delivery,
    party_event_router,
)


ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_PATH = ROOT / "dnd/core/events/knowledge.py"
SENSORY_PATH = ROOT / "dnd/blocks/sensory.py"
REDUCTION_PATH = ROOT / "dnd/event_reduction.py"


def parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def function_node(tree: ast.Module, class_name: str, function_name: str) -> ast.FunctionDef:
    owner = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return next(
        node
        for node in owner.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )


def test_knowledge_boundary_has_no_live_world_transport_or_renderer_dependency() -> None:
    modules = imported_modules(parsed(KNOWLEDGE_PATH))
    forbidden_prefixes = (
        "server",
        "deprecated",
        "pygame",
        "renderer",
        "dnd.core.gridmap",
        "dnd.entities",
    )

    assert not {
        module
        for module in modules
        if module.startswith(forbidden_prefixes)
    }


def test_knowledge_boundary_does_not_define_a_parallel_event_schema() -> None:
    forbidden_names = {
        "CanonicalEventView",
        "CanonicalKind",
        "FactAtom",
        "CanonicalEvent",
    }
    active_sources = (ROOT / "dnd").rglob("*.py")
    declared = {
        node.name
        for path in active_sources
        for node in parsed(path).body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    }

    assert declared.isdisjoint(forbidden_names)
    assert not issubclass(CapturedEvent, (Event, BaseModel))
    assert not issubclass(EventKnowledge, (Event, BaseModel))


def test_router_uses_actual_class_without_event_type_switch_or_serialization() -> None:
    source = KNOWLEDGE_PATH.read_text(encoding="utf-8")
    tree = parsed(KNOWLEDGE_PATH)
    dispatch = function_node(tree, "EventKnowledgeRouter", "dispatch")
    dispatch_source = ast.get_source_segment(source, dispatch) or ""

    assert "knowledge.event_class" in dispatch_source
    assert "event_type" not in dispatch_source
    assert "model_dump" not in source
    assert "singledispatch" not in source


def test_live_and_cold_sensory_replay_share_one_delta_reducer() -> None:
    source = SENSORY_PATH.read_text(encoding="utf-8")
    tree = parsed(SENSORY_PATH)
    reducer_definitions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "reduce_sensory_snapshot"
    ]
    live_apply = function_node(tree, "Senses", "apply_sensory_update")
    live_source = ast.get_source_segment(source, live_apply) or ""

    assert len(reducer_definitions) == 1
    assert "reduce_sensory_snapshot" in live_source
    assert "visible_cells_removed" not in live_source
    assert "entity_contacts_removed" not in live_source
    assert "effective_light_levels_changed" not in live_source


def test_reduction_composition_root_owns_e2_policy_assembly() -> None:
    reduction_source = REDUCTION_PATH.read_text(encoding="utf-8")
    reduction_tree = parsed(REDUCTION_PATH)
    sensory_source = SENSORY_PATH.read_text(encoding="utf-8")
    declared_classes = [
        node.name for node in reduction_tree.body if isinstance(node, ast.ClassDef)
    ]

    assert declared_classes == ["EventReducer"]
    assert "def party_event_router" in reduction_source
    assert "def party_event_delivery" in reduction_source
    assert "def party_event_router" not in sensory_source
    assert "def party_event_delivery" not in sensory_source
    assert "dnd.core.gridmap" not in imported_modules(reduction_tree)
    assert "dnd.entities.entity" not in imported_modules(reduction_tree)
    assert "dnd.encounters.encounter" not in imported_modules(reduction_tree)


def test_reduction_has_only_module_scope_imports_and_never_transitions_events() -> None:
    reduction_source = REDUCTION_PATH.read_text(encoding="utf-8")
    tree = parsed(REDUCTION_PATH)
    nested_imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and any(isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef))
                for parent in ast.walk(tree) if node in ast.iter_child_nodes(parent))
    ]
    # The composition root can consume stored values, but it cannot invoke an
    # event lifecycle method or manufacture a second event path.
    assert nested_imports == []
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {
            "phase_to",
            "post",
            "cancel",
            "generate_combat_log",
        }
        for node in ast.walk(tree)
    )
    assert "EventQueue.get_event_by_uuid" not in reduction_source


def test_cut_4_has_one_pull_boundary_and_no_passive_observer_compatibility() -> None:
    """The journal is pulled directly; deleted push boundaries cannot regrow."""
    retired_queue_api = {
        "add_on_event_callback",
        "remove_on_event_callback",
        "add_on_event_sequence_callback",
        "remove_on_event_sequence_callback",
        "add_on_event_batch_callback",
        "remove_on_event_batch_callback",
        "batch_on_event_callbacks",
        "add_on_handler_dispatch_callback",
        "remove_on_handler_dispatch_callback",
        "add_pre_completion_callback",
        "add_pre_completion_system",
        "register_completion_sequence",
        "set_combat_log_callback",
        "push_combat_log",
    }
    retired_reducer_api = {
        "on_event_batch",
        "on_combat_log",
        "pending_log_evidence",
        "callback_tail",
    }

    assert retired_queue_api.isdisjoint(EventQueue.__dict__)
    assert retired_reducer_api.isdisjoint(EventReducer.__dict__)
    assert callable(EventQueue.next_committed_tree)
    assert callable(EventReducer.reduce_next_committed_tree)
    assert callable(EventReducer.drain_committed_trees)

    governed_paths = (
        ROOT / "dnd/core/events/events_registry.py",
        ROOT / "dnd/core/base_actions.py",
        ROOT / "dnd/encounters/encounter.py",
        REDUCTION_PATH,
    )
    retired_identifiers = retired_queue_api | retired_reducer_api | {
        "_on_event_callbacks",
        "_on_event_sequence_callbacks",
        "_on_event_batch_callbacks",
        "_pending_event_batch",
        "_pending_log_evidence",
    }
    found = {
        node.id
        for path in governed_paths
        for node in ast.walk(parsed(path))
        if isinstance(node, ast.Name) and node.id in retired_identifiers
    } | {
        node.attr
        for path in governed_paths
        for node in ast.walk(parsed(path))
        if isinstance(node, ast.Attribute) and node.attr in retired_identifiers
    }
    assert found == set()


def test_batch_metadata_is_the_single_existing_knowledge_envelope_extension() -> None:
    reduction_tree = parsed(REDUCTION_PATH)
    knowledge_tree = parsed(KNOWLEDGE_PATH)
    reduction_classes = {
        node.name for node in reduction_tree.body if isinstance(node, ast.ClassDef)
    }
    knowledge_classes = {
        node.name for node in knowledge_tree.body if isinstance(node, ast.ClassDef)
    }

    assert reduction_classes == {"EventReducer"}
    assert {"SourceCoverage", "SourceDisposition", "EventDelivery", "EventBatch"} <= knowledge_classes
    assert "CanonicalEventView" not in knowledge_classes
    assert "EventReducer" not in knowledge_classes


def test_slice_3_3_has_one_exact_manifest_for_the_frozen_event_classes() -> None:
    expected = {
        "WorldInitializedEvent",
        "EntityCreatedEvent",
        "SpatialChangeEvent",
        "SensoryUpdateEvent",
        "EncounterStartEvent",
        "RoundStartEvent",
        "TurnStartEvent",
        "MovementEvent",
        "StepMovementEvent",
        "AttackEvent",
        "AttackD20RollResultEvent",
        "DamageRollResultEvent",
        "TakeDamageEvent",
        "DamageAppliedEvent",
        "ConditionApplicationEvent",
        "ConditionRemovalEvent",
        "SpellEvent",
        "TurnEndEvent",
        "RoundEndEvent",
        "EncounterEndEvent",
    }
    names = [row[0].__name__ for row in _CONCRETE_EVENT_MANIFEST]
    assert len(names) == len(set(names)) == len(expected)
    assert set(names) == expected
    assert all(len(row) == 8 for row in _CONCRETE_EVENT_MANIFEST)
    assert all(row[2] is not None and row[3] is not None for row in _CONCRETE_EVENT_MANIFEST)
    assert all(row[4] for row in _CONCRETE_EVENT_MANIFEST)
    assert all(
        row[5] is not None
        and callable(row[6])
        and callable(row[7])
        for row in _CONCRETE_EVENT_MANIFEST
    )
    routed = party_event_router(PartyKnowledge.cold(uuid4(), uuid4()))
    assert {event_class.__name__ for event_class in routed.covered_classes()} == expected | {"Event"}


def test_slice_3_3_manifest_paths_are_exact_model_paths_and_collection_paths() -> None:
    for event_class, _selector, scalar_paths, collection_paths, _role, provenance_paths, policy, formatter in _CONCRETE_EVENT_MANIFEST:
        assert callable(policy)
        assert callable(formatter)
        field_names = set(event_class.model_fields)
        for path in (*scalar_paths, *collection_paths, *provenance_paths):
            assert isinstance(path, tuple) and path
            assert isinstance(path[0], str)
            assert path[0] in field_names
        assert all(isinstance(path, tuple) for path in scalar_paths)
        assert all(isinstance(path, tuple) for path in collection_paths)
        assert all(isinstance(path, tuple) for path in provenance_paths)
    spatial_row = next(
        row for row in _CONCRETE_EVENT_MANIFEST
        if row[0].__name__ == "SpatialChangeEvent"
    )
    assert spatial_row[3] == (("light_level_map",),)


def test_slice_3_3_masks_cannot_admit_paths_absent_from_their_manifest_rows() -> None:
    sensory_paths = {
        ("source_entity_uuid",),
        ("source_entity_name",),
        ("target_entity_uuid",),
        ("target_entity_name",),
        ("observer_uuid",),
        ("observer_position",),
        ("observer_position_changed",),
        ("cause_event_uuid",),
        ("update_reason",),
        ("sense_modes_changed",),
        ("passive_perception_changed",),
        ("passive_perception",),
        ("visual_access_changed",),
        ("visual_access",),
        ("paths_dirty",),
    }
    sensory_collection_paths = {
        ("visible_cells_added",),
        ("visible_cells_removed",),
        ("seen_cells_added",),
        ("entity_contacts_changed",),
        ("entity_contacts_removed",),
        ("object_contacts_changed",),
        ("object_contacts_removed",),
        ("effective_light_levels_changed",),
        ("sense_modes",),
    }
    step_scalar_paths = {
        ("source_entity_uuid",),
        ("source_entity_name",),
        ("target_entity_uuid",),
        ("target_entity_name",),
        ("committed",),
        ("from_position",),
        ("from_elevation_feet",),
        ("to_position",),
        ("to_elevation_feet",),
        ("disclosed_path",),
        ("trajectory",),
    }
    step_collection_paths: set[tuple[str, ...]] = set()
    rows = {
        row[0]: row
        for row in _CONCRETE_EVENT_MANIFEST
        if row[0] in {SensoryUpdateEvent, StepMovementEvent}
    }
    assert set(rows[SensoryUpdateEvent][2]) == sensory_paths
    assert set(rows[SensoryUpdateEvent][3]) == sensory_collection_paths
    assert set(rows[StepMovementEvent][2]) == step_scalar_paths
    assert set(rows[StepMovementEvent][3]) == step_collection_paths

    base_paths = {
        ("uuid",),
        ("lineage_uuid",),
        ("timestamp",),
        ("event_type",),
        ("phase",),
        ("name",),
        ("canceled",),
        ("canceled_from_phase",),
        ("parent_event",),
        ("parent_lineage",),
        ("status_message",),
        ("outcome_code",),
    }
    for event_class, selector, scalar_paths, collection_paths, role, provenance_paths, policy, formatter in _CONCRETE_EVENT_MANIFEST:
        scalar = tuple(scalar_paths)
        collections = tuple(collection_paths)
        provenance = tuple(provenance_paths)
        assert scalar and len(scalar) == len(set(scalar))
        assert len(collections) == len(set(collections))
        assert set(scalar).isdisjoint(collections)
        assert all(
            isinstance(path, tuple)
            and path
            and isinstance(path[0], str)
            and path[0] in event_class.model_fields
            for path in (*scalar, *collections, *provenance)
        )
        assert callable(selector)
        assert isinstance(role, str) and role
        assert callable(policy)
        assert callable(formatter)

    assert base_paths

    EventQueue.reset()
    observer_uuid = uuid4()
    sensory = SensoryUpdateEvent(
        source_entity_uuid=observer_uuid,
        target_entity_uuid=observer_uuid,
        observer_uuid=observer_uuid,
        cause_event_uuid=uuid4(),
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    step = StepMovementEvent(
        source_entity_uuid=observer_uuid,
        from_position=(0, 0),
        to_position=(1, 0),
        disclosed_path=((0, 0), (1, 0)),
        committed=True,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    party = PartyKnowledge.cold(observer_uuid, uuid4())
    router = party_event_router(party)
    generation = EventQueue.generation_id()
    archive = EventArchive(tuple(
        CapturedEvent(
            generation_id=generation,
            source_index=index,
            _snapshot=event.model_copy(deep=True),
        )
        for index, event in enumerate((sensory, step))
    ))
    runtime_base_paths = {
        ("uuid",),
        ("lineage_uuid",),
        ("timestamp",),
        ("event_type",),
        ("phase",),
        ("name",),
        ("canceled",),
        ("canceled_from_phase",),
        ("parent_event",),
        ("parent_lineage",),
        ("status_message",),
        ("outcome_code",),
    }
    for captured in archive.entries:
        delivery = party_event_delivery(captured, router)
        assert delivery is not None
        assert not isinstance(delivery, KnowledgeDiagnostic)
        row = rows[captured.event_class]
        assert delivery.knowledge.mask.paths <= runtime_base_paths | set(row[2])
        assert delivery.knowledge.mask.collection_paths <= set(row[3])


def test_slice_3_3_reducer_has_no_live_world_or_second_policy_source() -> None:
    source = REDUCTION_PATH.read_text(encoding="utf-8")
    assert "get_map(" not in source
    assert "get_event_by_uuid" not in source
    assert source.count("_CONCRETE_EVENT_MANIFEST") == 4
    assert "_PROVENANCE_POLICIES" not in source


def test_slice_4_formatters_are_manifest_bound_and_detached() -> None:
    source = REDUCTION_PATH.read_text(encoding="utf-8")
    tree = parsed(REDUCTION_PATH)
    function_definitions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }
    formatter_nodes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("_format_")
    ]
    assert formatter_nodes
    formatter_names = {row[7].__name__ for row in _CONCRETE_EVENT_MANIFEST}
    assert formatter_names <= function_definitions.keys()
    detached_forbidden = (
        "_snapshot",
        "combat_log",
        ".data",
        "EventQueue",
        "get_map",
        "registry",
        "handler",
    )
    visiting: set[str] = set()
    reached_reader: set[str] = set()

    def visit_formatter(name: str) -> bool:
        if name in reached_reader:
            return True
        if name in visiting:
            raise AssertionError("formatter call graph contains a cycle")
        node = function_definitions[name]
        formatter_source = ast.get_source_segment(source, node) or ""
        assert not any(marker in formatter_source for marker in detached_forbidden)
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            if isinstance(call.func, ast.Attribute):
                if (
                    isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "knowledge"
                ):
                    assert call.func.attr in {"read", "known_items"}
        visiting.add(name)
        calls = {
            call.func.id
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id in function_definitions
            and call.func.id.startswith("_format_")
        }
        if any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "knowledge"
            and call.func.attr in {"read", "known_items"}
            for call in ast.walk(node)
        ):
            reached_reader.add(name)
            visiting.remove(name)
            return True
        result = bool(calls) and all(visit_formatter(call) for call in calls)
        visiting.remove(name)
        if result:
            reached_reader.add(name)
        return result

    assert all(visit_formatter(name) for name in formatter_names)

    assert "KnowledgeMask.top()" in source
    assert "format_event_knowledge(delivery.knowledge)" in source
    assert all(callable(row[7]) for row in _CONCRETE_EVENT_MANIFEST)
    roles = [row[4] for row in _CONCRETE_EVENT_MANIFEST]
    assert len(roles) == len(set(roles)) == 20
    assert all(isinstance(role, str) and role for role in roles)
    assert "intentionally_silent" not in roles
    assert BASE_EVENT_INTENTIONALLY_SILENT_REASON
    assert "base Event has no admitted exact-class presentation policy" in source
