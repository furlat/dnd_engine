"""Contract and reset checks for the standalone TypeScript replication SDK."""

import json
from pathlib import Path

from devtools.generate_typescript_sdk import build_sdk_manifest, render_typescript
from dnd.core.events import EventQueue, SensoryUpdateEvent
from dnd.core.combat_log import AttackLogData, DiceRollDisplay
from fastapi.routing import APIRoute
from server.api_models import (
    APIAvailableActions,
    APIEntityVisibility,
    APIEntityHandlersResponse,
    APIEquipmentOverview,
    APIEquippableItems,
    APIItemSummary,
    EquipmentMutationResult,
    ReplicationBootstrapResponse,
    StartHumanSimulationResponse,
    ToggleHandlerResponse,
)
from server.event_server import app


ROOT = Path(__file__).resolve().parents[2]
SDK_MANIFEST = ROOT / "sdk" / "typescript" / "src" / "generated" / "contract.generated.json"
SDK_TYPES = ROOT / "sdk" / "typescript" / "src" / "generated" / "contracts.generated.ts"


def _descriptor_kinds(value: object) -> set[str]:
    """Collect every descriptor kind recursively from a generated manifest."""
    kinds: set[str] = set()
    if isinstance(value, dict):
        kind = value.get("kind")
        if isinstance(kind, str):
            kinds.add(kind)
        for child in value.values():
            kinds.update(_descriptor_kinds(child))
    elif isinstance(value, list):
        for child in value:
            kinds.update(_descriptor_kinds(child))
    return kinds


def test_checked_in_sdk_contract_equals_backend_model_graph() -> None:
    """Generated REST, SSE, event, and combat-log types cannot drift."""
    fresh = build_sdk_manifest()
    checked_in = json.loads(SDK_MANIFEST.read_text(encoding="utf-8"))

    assert fresh == checked_in
    assert SDK_TYPES.read_text(encoding="utf-8") == render_typescript(fresh)
    assert "unknown" not in _descriptor_kinds(fresh)


def test_sdk_reuses_canonical_action_and_bootstrap_models() -> None:
    """The client contract preserves engine action rows and one atomic base state."""
    manifest = build_sdk_manifest()
    models = manifest["models"]
    actions = models[f"{APIAvailableActions.__module__}.{APIAvailableActions.__qualname__}"]
    bootstrap = models[
        f"{ReplicationBootstrapResponse.__module__}.{ReplicationBootstrapResponse.__qualname__}"
    ]

    assert {
        "entity_actions",
        "position_actions",
        "self_actions",
        "object_actions",
        "handler_details",
        "spell_slots",
        "resources",
    } <= set(actions["fields"])
    assert {
        "protocol",
        "event_cursor",
        "combat_log_cursor",
        "state",
        "visibility",
        "combat_log",
        "session",
    } == set(bootstrap["fields"])
    visibility = models[
        f"{APIEntityVisibility.__module__}.{APIEntityVisibility.__qualname__}"
    ]
    sensory_update = models[
        f"{SensoryUpdateEvent.__module__}.{SensoryUpdateEvent.__qualname__}"
    ]
    assert "effective_light_levels" in visibility["fields"]
    assert {"observer_position", "effective_light_levels"} <= set(
        sensory_update["fields"]
    )


def test_event_queue_reset_changes_generation_even_when_cursor_restarts() -> None:
    """Equal numeric cursors from two games remain distinguishable."""
    before = EventQueue.generation_id()
    EventQueue.reset()
    after = EventQueue.generation_id()

    assert before != after
    assert EventQueue.event_cursor() == 0


def test_existing_combat_log_models_are_generated_instead_of_redeclared() -> None:
    """Structured combat-log payloads remain backend-owned SDK types."""
    models = build_sdk_manifest()["models"]

    for model in (AttackLogData, DiceRollDisplay):
        path = f"{model.__module__}.{model.__qualname__}"
        assert path in models


def test_neuroclient_routes_publish_concrete_backend_response_models() -> None:
    """Core startup, handler, and equipment routes have one Pydantic contract."""
    expected = {
        ("/simulation/start-human", "POST"): StartHumanSimulationResponse,
        ("/entity/{entity_uuid}/handlers", "GET"): APIEntityHandlersResponse,
        ("/entity/{entity_uuid}/handlers/{handler_name}/toggle", "POST"): ToggleHandlerResponse,
        ("/entity/{entity_uuid}/equipment", "GET"): APIEquipmentOverview,
        ("/entity/{entity_uuid}/equipment/item/{item_uuid}", "GET"): APIItemSummary,
        ("/entity/{entity_uuid}/equippable-items", "GET"): APIEquippableItems,
        ("/entity/{entity_uuid}/equip", "POST"): EquipmentMutationResult,
        ("/entity/{entity_uuid}/unequip", "POST"): EquipmentMutationResult,
    }
    routes = {
        (route.path, method): route.response_model
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }

    for key, response_model in expected.items():
        assert routes[key] is response_model
