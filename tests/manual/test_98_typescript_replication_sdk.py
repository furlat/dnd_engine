"""Contract and reset checks for the standalone TypeScript replication SDK."""

import json
from pathlib import Path

from devtools.generate_typescript_sdk import build_sdk_manifest, render_typescript
from dnd.core.content.descriptors import EquipmentSpritePresentation
from dnd.core.base_actions import AvailableActionInfo
from dnd.core.equipment_types import EquipmentRenderLayer
from dnd.core.events import EventQueue, SensoryUpdateEvent
from dnd.core.combat_log import AttackLogData, DiceRollDisplay
from fastapi.routing import APIRoute
from server.api_models import (
    APIAvailableActions,
    APIEntityHandlersResponse,
    APIEquippableItems,
    EquipmentMutationResult,
    GameCreationActivateResponse,
    GameCreationStartResponse,
    ToggleHandlerResponse,
)
from server.content_catalog import ContentCatalogResponse
from server.character_directory_contracts import (
    CharacterListResponse,
    CharacterProfileResponse,
)
from server.world_contracts import APIEntityVisibility
from server.event_server import app
from server.objective_replay import ObjectiveReplayBundle
from server.player_replay import (
    SubjectivePlayerReplayArchive,
    SubjectivePlayerReplayBundle,
    SubjectiveReplaySegment,
)
from server.player_replication_contract import (
    MovementPresentationCue,
    PLAYER_REPLICATION_CONTRACT_HASH,
    PLAYER_REPLICATION_CONTRACT_VERSION,
    SpellPresentationCue,
    SubjectiveFloorObject,
    SubjectiveCombatLogFramesResponse,
    SubjectiveFramesResponse,
    SubjectiveReplicationBootstrap,
)


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


def test_sdk_uses_only_the_canonical_subjective_replication_roots() -> None:
    """The generated player surface is the patch/cue journal, never raw events."""
    manifest = build_sdk_manifest()
    models = manifest["models"]
    actions = models[f"{APIAvailableActions.__module__}.{APIAvailableActions.__qualname__}"]
    action_info = models[
        f"{AvailableActionInfo.__module__}.{AvailableActionInfo.__qualname__}"
    ]
    bootstrap = models[
        f"{SubjectiveReplicationBootstrap.__module__}.{SubjectiveReplicationBootstrap.__qualname__}"
    ]
    frames = models[
        f"{SubjectiveFramesResponse.__module__}.{SubjectiveFramesResponse.__qualname__}"
    ]
    combat_log = models[
        f"{SubjectiveCombatLogFramesResponse.__module__}."
        f"{SubjectiveCombatLogFramesResponse.__qualname__}"
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
    assert action_info["fields"]["configured_action_ref"] == {
        "kind": "union",
        "items": [
            {
                "kind": "model",
                "ref": "dnd.core.content.identities.ContentRef",
            },
            {"kind": "null"},
        ],
    }
    assert set(bootstrap["fields"]) == {
        "protocol",
        "perspective",
        "watermarks",
        "world",
        "combat_log_frames",
    }
    assert set(frames["fields"]) == {
        "source_stream_id",
        "generation_id",
        "perspective_epoch_id",
        "retained_from_observation_cursor",
        "from_watermarks",
        "through_watermarks",
        "captured_watermarks",
        "frames",
    }
    assert "frames" in combat_log["fields"]
    assert manifest["aliases"].keys() == {
        "SubjectiveWorldPatch",
        "SubjectivePresentationCue",
        "SubjectiveStreamDelivery",
        "SubjectiveReplayDelivery",
    }
    assert (
        manifest["player_replication_contract_version"]
        == PLAYER_REPLICATION_CONTRACT_VERSION
    )
    assert (
        manifest["player_replication_contract_hash"]
        == PLAYER_REPLICATION_CONTRACT_HASH
    )
    generated_names = {
        row["typescript"] for row in models.values()
    }
    assert not {
        "ReplicationBootstrapResponse",
        "ReplicationBootstrapResponseV2",
        "ReplicationV2HeartbeatPayload",
        "ReplicationV2StreamSyncPayload",
        "EventHistoryResponse",
        "CombatLogHistoryResponse",
        "GameEventHistoryResponse",
        "GameEventPayload",
    } & generated_names
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


def test_sdk_exports_public_replays_but_not_the_all_memberships_archive() -> None:
    """Public replay routes expose one objective game or one exact membership only."""
    manifest = build_sdk_manifest()
    models = manifest["models"]
    roots = set(manifest["roots"])
    objective_path = (
        f"{ObjectiveReplayBundle.__module__}.{ObjectiveReplayBundle.__qualname__}"
    )
    player_path = (
        f"{SubjectivePlayerReplayBundle.__module__}."
        f"{SubjectivePlayerReplayBundle.__qualname__}"
    )
    segment_path = (
        f"{SubjectiveReplaySegment.__module__}.{SubjectiveReplaySegment.__qualname__}"
    )
    archive_path = (
        f"{SubjectivePlayerReplayArchive.__module__}."
        f"{SubjectivePlayerReplayArchive.__qualname__}"
    )

    assert {objective_path, player_path} <= roots
    assert {objective_path, player_path, segment_path} <= set(models)
    assert archive_path not in roots
    assert archive_path not in models


def test_sdk_character_directory_is_schema2_and_transport_only() -> None:
    """Persistence, migration, and unpinned deployment DTOs stay server-only."""

    manifest = build_sdk_manifest()
    models = manifest["models"]
    generated_names = {
        row["typescript"] for row in models.values()
    }
    assert not {
        "CharacterBootstrapCreate",
        "CharacterDefinitionRevision",
        "CharacterDefinitionRevisionV1",
        "CharacterRecord",
        "CharacterDeploymentLeaseCreate",
        "CharacterDeploymentLeaseRecord",
        "CharacterDeploymentCreate",
        "CharacterDeploymentRecord",
        "CharacterRevisionBundleCommit",
        "DirectoryMutationReceiptCreate",
        "DirectoryMutationReceiptRecord",
        "PinnedCharacterDeploymentCreate",
        "PinnedCharacterDeploymentRecord",
        "WorkerCreate",
        "WorkerRecord",
    } & generated_names
    assert "legacy_pending" not in json.dumps(manifest, sort_keys=True)

    for response_model in (CharacterListResponse, CharacterProfileResponse):
        model_path = (
            f"{response_model.__module__}.{response_model.__qualname__}"
        )
        characters = models[model_path]["fields"]["characters"]
        assert characters["kind"] == "array"
        assert characters["items"] == {
            "kind": "model",
            "ref": (
                "server.game_directory.contracts."
                "CanonicalCharacterRecord"
            ),
        }


def test_sdk_descriptors_preserve_player_field_constraints() -> None:
    """The browser decoder enforces Pydantic integer, length, and range bounds."""
    models = build_sdk_manifest()["models"]
    movement = models[
        f"{MovementPresentationCue.__module__}.{MovementPresentationCue.__qualname__}"
    ]["fields"]
    spell = models[
        f"{SpellPresentationCue.__module__}.{SpellPresentationCue.__qualname__}"
    ]["fields"]

    assert movement["presentation_cursor"] == {
        "kind": "integer",
        "minimum": 1,
    }
    assert movement["presentation_id"] == {
        "kind": "string",
        "min_length": 1,
    }
    assert "trajectory" not in movement
    assert movement["anchors"] == {
        "kind": "array",
        "items": {
            "kind": "model",
            "ref": "server.player_replication_contract.LocomotionAnchor",
        },
        "min_length": 2,
    }
    assert movement["locomotion_family"] == {
        "kind": "enum",
        "ref": "server.player_replication_contract.LocomotionFamily",
    }
    assert movement["trajectory_family"] == {
        "kind": "enum",
        "ref": "server.player_replication_contract.LocomotionTrajectory",
    }
    assert spell["spell_level"] == {
        "kind": "integer",
        "minimum": 0,
        "maximum": 9,
    }
    floor_object = models[
        f"{SubjectiveFloorObject.__module__}.{SubjectiveFloorObject.__qualname__}"
    ]["fields"]
    assert floor_object["bright_radius_feet"] == {
        "kind": "union",
        "items": [
            {"kind": "integer", "minimum": 0},
            {"kind": "null"},
        ],
    }


def test_sdk_preserves_exact_compound_equipment_presentation_contract() -> None:
    """Catalog rows distinguish loadout ownership from rendered actor layers."""
    manifest = build_sdk_manifest()
    models = manifest["models"]
    row_path = (
        f"{EquipmentSpritePresentation.__module__}."
        f"{EquipmentSpritePresentation.__qualname__}"
    )
    fields = models[row_path]["fields"]

    assert set(fields) == {
        "equipment_slot",
        "render_layer",
        "sprite_key",
        "tint_rgb",
    }
    assert fields["equipment_slot"] == {
        "kind": "enum",
        "ref": "dnd.core.equipment_types.VisualLoadoutSlot",
    }
    assert fields["render_layer"] == {
        "kind": "enum",
        "ref": "dnd.core.equipment_types.EquipmentRenderLayer",
    }
    assert fields["tint_rgb"] == {
        "kind": "integer",
        "minimum": 0,
        "maximum": 0xFFFFFF,
    }
    enum_path = (
        f"{EquipmentRenderLayer.__module__}."
        f"{EquipmentRenderLayer.__qualname__}"
    )
    assert manifest["enums"][enum_path]["values"] == [
        "belt",
        "chest",
        "hands",
        "helmet",
        "legs",
        "offhand",
        "shoes",
        "weapon",
    ]
    catalog_path = (
        f"{ContentCatalogResponse.__module__}."
        f"{ContentCatalogResponse.__qualname__}"
    )
    assert models[catalog_path]["fields"]["schema_version"] == {
        "kind": "union",
            "items": [{"kind": "literal", "value": 7}],
    }


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
        ("/game-creation/start", "POST"): GameCreationStartResponse,
        ("/game-creation/activate", "POST"): GameCreationActivateResponse,
        ("/entity/{entity_uuid}/handlers", "GET"): APIEntityHandlersResponse,
        ("/entity/{entity_uuid}/handlers/{handler_uuid}/toggle", "POST"): ToggleHandlerResponse,
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
    assert ("/simulation/start-human", "POST") not in routes
    assert ("/entity/{entity_uuid}/equipment", "GET") not in routes
    assert ("/entity/{entity_uuid}/equipment/item/{item_uuid}", "GET") not in routes
